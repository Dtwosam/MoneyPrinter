"""Durable post-1h Standard-4H progression and shared read-side truth.

This coordinator owns no source calls, Scheduler claims, retries, recovery, or
successor loop. It records the exact two-slot progression boundary and delegates
eligible successor creation to the existing atomic Standard-4H planner.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import sqlite3
from typing import Any, Mapping, Sequence

from printer_v1.operator_cli.cadence_authority import (
    CADENCE_AUTHORITY_RESOLVED,
    resolve_campaign_slot_cadence_authority,
)
from printer_v1.operator_cli.campaign_active_work import campaign_active_work_report
from printer_v1.operator_cli.campaign_supervision import inspect_campaign_supervision
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleCampaignBinding,
)
from printer_v1.operator_cli.operational_database_target_binding import (
    OperationalDatabaseTargetBinding,
    load_durable_operational_database_target_expectation,
    validate_operational_database_target_binding,
)
from printer_v1.operator_cli.proof_db_schema_readiness import (
    validate_runtime_schema_connection,
)


ATTEMPT_TABLE = "printer_memory_factory_standard_4h_progression_attempts"
TOKEN_TABLE = "printer_memory_factory_standard_4h_progression_tokens"
POLICY_VERSION = "STANDARD_4H_PROGRESSION_V1"
ATTEMPT_STATES = frozenset(
    {
        "WAITING_FOR_PREDECESSORS",
        "EVALUATING",
        "ELIGIBILITY_COMPLETE",
        "HANDOFF_COMMITTED",
        "TERMINAL_FAILED",
        "TERMINAL_CANCELLED",
        "INTERRUPTED_REVIEW",
    }
)
TOKEN_DISPOSITIONS = frozenset(
    {
        "WAITING_FOR_PREDECESSOR",
        "ELIGIBLE_PENDING_HANDOFF",
        "INELIGIBLE",
        "HANDOFF_CREATED",
        "TERMINAL_FAILED",
    }
)
TERMINALLY_NON_ELIGIBLE = frozenset({"INELIGIBLE", "TERMINAL_FAILED"})
EMPTY_FAULTS = {"primary": None, "secondary": []}


class StandardFourHourProgressionError(RuntimeError):
    """Fail-closed durable progression contract violation."""

    def __init__(
        self,
        message: str,
        *,
        terminal_cause: str | None = None,
        terminal_state: str = "TERMINAL_FAILED",
    ) -> None:
        super().__init__(message)
        self.terminal_cause = terminal_cause
        self.terminal_state = terminal_state


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _safe_fault_text(value: object) -> str:
    text = str(value or "PROGRESSION_FAULT")
    text = re.sub(r"https?://\S+", "<redacted-url>", text, flags=re.IGNORECASE)
    text = re.sub(
        r"(?i)\b(api[_-]?key|token|secret|password|authorization|bearer)"
        r"\s*[:=]\s*[^\s,;]+",
        r"\1=<redacted>",
        text,
    )
    text = re.sub(r"/(?:Users|home|private|var|tmp)/\S+", "<redacted-path>", text)
    return " ".join(text.split())[:512]


def _object(value: object, *, label: str) -> dict[str, Any]:
    try:
        decoded = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise StandardFourHourProgressionError(f"invalid {label}") from exc
    if not isinstance(decoded, dict):
        raise StandardFourHourProgressionError(f"invalid {label}")
    return decoded


def progression_attempt_id_for(
    *, campaign_id: str, campaign_run_id: str, cycle_id: str
) -> str:
    return f"std4h-progression:{campaign_id}:{campaign_run_id}:{cycle_id}"


def progression_token_id_for(
    *, progression_attempt_id: str, token_slot_id: str
) -> str:
    return f"{progression_attempt_id}:{token_slot_id}"


def create_standard_4h_progression_aggregate(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    configuration_id: str,
    campaign_run_id: str,
    cycle_id: str,
    candidates: Sequence[Mapping[str, Any]],
    terminal_exclusions: Sequence[Mapping[str, Any]] = (),
    now: str | None = None,
) -> str | None:
    """Create the exact attempt/two-row aggregate inside the 1h handoff txn."""
    if len(candidates) + len(terminal_exclusions) != 2:
        raise StandardFourHourProgressionError(
            "standard 4h progression requires exactly two normal/excluded slots"
        )
    run = connection.execute(
        """SELECT r.authoritative_run_id,f.config_json
           FROM printer_memory_factory_campaign_runs AS r
           JOIN printer_memory_factory_runs AS f ON f.run_id=r.authoritative_run_id
           WHERE r.campaign_id=? AND r.run_id=?""",
        (campaign_id, campaign_run_id),
    ).fetchone()
    if run is None or run[0] is None:
        raise StandardFourHourProgressionError(
            "standard 4h progression factory-run identity missing"
        )
    factory_run_id = str(run[0])
    config = _object(run[1], label="factory run config")
    if config.get("standard_four_hour_campaign") is not True:
        return None

    slots = connection.execute(
        """SELECT token_slot_id,slot_ordinal,token_identity,token_row_id,
                  mint_identity,pair_identity,pair_row_id,lifecycle_identity,
                  tracking_queue_id,token_state,first_terminal_cause,terminal_at
           FROM printer_memory_factory_campaign_token_slots
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
           ORDER BY slot_ordinal""",
        (campaign_id, campaign_run_id, cycle_id),
    ).fetchall()
    if len(slots) != 2 or [int(row[1]) for row in slots] != [1, 2]:
        raise StandardFourHourProgressionError(
            "standard 4h progression requires the exact two-slot set"
        )
    candidate_by_slot = {
        str(item["info"]["token_slot_id"]): item for item in candidates
    }
    exclusion_by_slot: dict[str, Mapping[str, Any]] = {}
    for exclusion in terminal_exclusions:
        slot_id = str(exclusion.get("token_slot_id") or "")
        if not slot_id or slot_id in exclusion_by_slot:
            raise StandardFourHourProgressionError(
                "standard 4h progression exclusion-slot identity is ambiguous"
            )
        exclusion_by_slot[slot_id] = exclusion
    owned_slot_ids = {str(row[0]) for row in slots}
    if (
        set(candidate_by_slot) & set(exclusion_by_slot)
        or set(candidate_by_slot) | set(exclusion_by_slot) != owned_slot_ids
    ):
        raise StandardFourHourProgressionError(
            "standard 4h progression normal/excluded slot identity mismatch"
        )

    attempt_id = progression_attempt_id_for(
        campaign_id=campaign_id,
        campaign_run_id=campaign_run_id,
        cycle_id=cycle_id,
    )
    timestamp = now or _utc_now()
    connection.execute(
        f"""INSERT INTO {ATTEMPT_TABLE}(
               progression_attempt_id,campaign_id,configuration_id,
               campaign_run_id,factory_run_id,cycle_id,policy_version,
               attempt_state,authority_evidence_json,fault_details_json,
               created_at,updated_at
           ) VALUES (?,?,?,?,?,?,'{POLICY_VERSION}',
               'WAITING_FOR_PREDECESSORS',?,?,?,?)""",
        (
            attempt_id,
            campaign_id,
            configuration_id,
            campaign_run_id,
            factory_run_id,
            cycle_id,
            _json({
                "producer": (
                    "campaign_ownership.persist_standard_first_hour_handoff_set"
                ),
                "standard_four_hour_campaign": True,
                "boundary_categories": {
                    slot_id: (
                        "PRE_15M_TOKEN_LOCAL_TERMINAL_EXCLUSION"
                        if slot_id in exclusion_by_slot
                        else "REAL_15M_TERMINAL_PREDECESSOR"
                    )
                    for slot_id in sorted(owned_slot_ids)
                },
            }),
            _json(EMPTY_FAULTS),
            timestamp,
            timestamp,
        ),
    )
    immediately_ineligible = 0
    for slot in slots:
        slot_id = str(slot[0])
        if slot_id in exclusion_by_slot:
            exclusion = exclusion_by_slot[slot_id]
            if (
                str(exclusion.get("kind") or "")
                != "PRE_15M_TOKEN_LOCAL_TERMINAL_EXCLUSION"
                or str(slot[9]) != "FAILED"
                or str(slot[10] or "") != "TOKEN_LOCAL_TERMINAL_FAILURE"
            ):
                raise StandardFourHourProgressionError(
                    f"pre-15m exclusion state/cause invalid for {slot_id}"
                )
            identity_contract = (
                ("token_row_id", int(slot[3])),
                ("pair_row_id", int(slot[6])),
                ("mint_identity", str(slot[4])),
                ("pair_identity", str(slot[5])),
                ("lifecycle_identity", str(slot[7])),
                ("tracking_queue_id", int(slot[8])),
            )
            for key, expected in identity_contract:
                actual = exclusion.get(key)
                matches = (
                    int(actual) == expected
                    if isinstance(expected, int)
                    else str(actual) == expected
                )
                if not matches:
                    raise StandardFourHourProgressionError(
                        f"pre-15m exclusion identity mismatch for {slot_id}: {key}"
                    )
            queue = connection.execute(
                """SELECT token_id,pair_id,tracking_lane
                   FROM printer_tracking_queue WHERE id=?""",
                (int(slot[8]),),
            ).fetchone()
            if (
                queue is None
                or int(queue[0]) != int(slot[3])
                or queue[1] is None
                or int(queue[1]) != int(slot[6])
                or str(queue[2]) not in {"TRACK_FAST", "TRACK_NORMAL"}
            ):
                raise StandardFourHourProgressionError(
                    f"pre-15m exclusion historical tracking authority invalid for {slot_id}"
                )
            failed_step_id = int(exclusion.get("failed_factory_step_id"))
            failed_step = connection.execute(
                """SELECT id,step_kind,step_status,token_id,pair_id,
                          source_failure_id,memory_window_id
                   FROM printer_memory_factory_run_steps
                   WHERE id=? AND run_id=?""",
                (failed_step_id, factory_run_id),
            ).fetchone()
            if (
                failed_step is None
                or str(failed_step[1]) != str(exclusion.get("failed_step_kind"))
                or str(failed_step[2]) != "FAILED"
                or int(failed_step[3]) != int(slot[3])
                or int(failed_step[4]) != int(slot[6])
                or str(failed_step[1]).startswith("CONTINUATION_")
                or str(failed_step[1]).startswith("LONG_CONTINUATION_")
                or failed_step[6] is not None
            ):
                raise StandardFourHourProgressionError(
                    f"pre-15m exclusion failed-step evidence invalid for {slot_id}"
                )
            source_failure_id = failed_step[5]
            claimed_source_failure_id = exclusion.get("source_failure_id")
            if (
                (source_failure_id is None) != (claimed_source_failure_id is None)
                or (
                    source_failure_id is not None
                    and int(source_failure_id) != int(claimed_source_failure_id)
                )
            ):
                raise StandardFourHourProgressionError(
                    f"pre-15m exclusion source-failure reference mismatch for {slot_id}"
                )
            if source_failure_id is not None and connection.execute(
                "SELECT 1 FROM printer_source_failures WHERE id=?",
                (int(source_failure_id),),
            ).fetchone() is None:
                raise StandardFourHourProgressionError(
                    f"pre-15m exclusion source failure missing for {slot_id}"
                )
            valid_15m = int(
                connection.execute(
                    """SELECT COUNT(*)
                       FROM printer_memory_factory_campaign_windows AS w
                       JOIN printer_memory_factory_run_steps AS s
                         ON s.run_id=?
                        AND s.token_id=w.token_row_id
                        AND s.pair_id=w.pair_row_id
                        AND s.memory_window_id=w.memory_window_row_id
                        AND s.step_kind IN ('WINDOW_CLOSE','WINDOW_CLOSE_AUDIT')
                        AND s.step_status='SUCCEEDED'
                       WHERE w.campaign_id=? AND w.run_id=? AND w.cycle_id=?
                         AND w.token_slot_id=? AND w.window_kind='WINDOW_15M'
                         AND w.memory_window_row_id IS NOT NULL""",
                    (
                        factory_run_id,
                        campaign_id,
                        campaign_run_id,
                        cycle_id,
                        slot_id,
                    ),
                ).fetchone()[0]
            )
            if valid_15m != 0:
                raise StandardFourHourProgressionError(
                    f"pre-15m exclusion conflicts with valid WINDOW_15M for {slot_id}"
                )
            predecessor_window_id = None
            token_disposition = "INELIGIBLE"
            disposition_reasons = ["PRE_15M_TOKEN_LOCAL_TERMINAL_FAILURE"]
            eligibility_evidence = {
                "producer": (
                    "campaign_ownership.persist_standard_first_hour_handoff_set"
                ),
                "boundary_kind": "PRE_15M_TOKEN_LOCAL_TERMINAL_EXCLUSION",
                "campaign_id": campaign_id,
                "campaign_run_id": campaign_run_id,
                "cycle_id": cycle_id,
                "slot_ordinal": int(slot[1]),
                "token_slot_id": slot_id,
                "token_row_id": int(slot[3]),
                "mint_identity": str(slot[4]),
                "pair_row_id": int(slot[6]),
                "pair_identity": str(slot[5]),
                "lifecycle_identity": str(slot[7]),
                "tracking_queue_id": int(slot[8]),
                "tracking_lane": str(queue[2]),
                "failed_factory_step_id": failed_step_id,
                "failed_step_kind": str(failed_step[1]),
                "source_failure_id": (
                    None if source_failure_id is None else int(source_failure_id)
                ),
                "terminal_cause": "TOKEN_LOCAL_TERMINAL_FAILURE",
                "exclusion_reason": "PRE_15M_TOKEN_LOCAL_TERMINAL_FAILURE",
                "terminal_at": str(slot[11]),
                "no_valid_successful_memory_backed_window_15m": True,
            }
            evaluated_at = timestamp
            immediately_ineligible += 1
            tracking_lane = str(queue[2])
        else:
            candidate = candidate_by_slot[slot_id]
            payload = dict(candidate["payload"])
            predecessor_window_id = payload.get("campaign_window_1h_id")
            if predecessor_window_id is None and bool(candidate.get("continue_ok")):
                raise StandardFourHourProgressionError(
                    f"continuing slot lacks WINDOW_1H identity: {slot_id}"
                )
            if predecessor_window_id is None:
                resolution_window_id = str(
                    candidate["info"]["campaign_window_15m_id"]
                )
                token_disposition = "INELIGIBLE"
                disposition_reasons = ["NO_WINDOW_1H_PLANNED"]
                eligibility_evidence = {
                    "producer": (
                        "campaign_ownership.persist_standard_first_hour_handoff_set"
                    ),
                    "predecessor_state": "NOT_PLANNED",
                    "predecessor_reason": "NO_WINDOW_1H_PLANNED",
                    "continuation_reasons": list(payload.get("reasons") or []),
                }
                evaluated_at = timestamp
                immediately_ineligible += 1
            else:
                resolution_window_id = str(predecessor_window_id)
                token_disposition = "WAITING_FOR_PREDECESSOR"
                disposition_reasons = []
                eligibility_evidence = {}
                evaluated_at = None
            cadence = resolve_campaign_slot_cadence_authority(
                connection,
                campaign_window_id=resolution_window_id,
                campaign_id=campaign_id,
                campaign_run_id=campaign_run_id,
                cycle_id=cycle_id,
                token_slot_id=slot_id,
            )
            if (
                cadence.status != CADENCE_AUTHORITY_RESOLVED
                or cadence.tracking_lane not in {"TRACK_FAST", "TRACK_NORMAL"}
                or cadence.tracking_queue_id is None
                or int(cadence.tracking_queue_id) != int(slot[8])
            ):
                raise StandardFourHourProgressionError(
                    f"tracking cadence authority unresolved for {slot_id}: "
                    f"{cadence.reason_code}"
                )
            tracking_lane = str(cadence.tracking_lane)
        connection.execute(
            f"""INSERT INTO {TOKEN_TABLE}(
                   progression_token_id,progression_attempt_id,campaign_id,
                   campaign_run_id,factory_run_id,cycle_id,slot_ordinal,
                   token_slot_id,token_identity,token_row_id,mint_identity,
                   pair_identity,pair_row_id,lifecycle_identity,tracking_queue_id,
                   tracking_lane,predecessor_window_1h_id,token_disposition,
                   disposition_reasons_json,eligibility_evidence_json,
                   fault_details_json,evaluated_at,created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                progression_token_id_for(
                    progression_attempt_id=attempt_id, token_slot_id=slot_id
                ),
                attempt_id,
                campaign_id,
                campaign_run_id,
                factory_run_id,
                cycle_id,
                int(slot[1]),
                slot_id,
                str(slot[2]),
                int(slot[3]),
                str(slot[4]),
                str(slot[5]),
                int(slot[6]),
                str(slot[7]),
                int(slot[8]),
                tracking_lane,
                predecessor_window_id,
                token_disposition,
                _json(disposition_reasons),
                _json(eligibility_evidence),
                _json(EMPTY_FAULTS),
                evaluated_at,
                timestamp,
                timestamp,
            ),
        )
    if immediately_ineligible == 2:
        connection.execute(
            f"""UPDATE {ATTEMPT_TABLE}
                SET attempt_state='ELIGIBILITY_COMPLETE',
                    eligibility_completed_at=?,updated_at=?
                WHERE progression_attempt_id=?
                  AND attempt_state='WAITING_FOR_PREDECESSORS'""",
            (timestamp, timestamp, attempt_id),
        )
    return attempt_id


def load_standard_4h_progression_aggregate(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
    cycle_id: str,
) -> dict[str, Any] | None:
    attempt = connection.execute(
        f"""SELECT * FROM {ATTEMPT_TABLE}
            WHERE campaign_id=? AND campaign_run_id=? AND cycle_id=?""",
        (campaign_id, campaign_run_id, cycle_id),
    ).fetchone()
    if attempt is None:
        return None
    attempt_dict = dict(attempt)
    tokens = [
        dict(row)
        for row in connection.execute(
            f"""SELECT * FROM {TOKEN_TABLE}
                WHERE progression_attempt_id=? ORDER BY slot_ordinal""",
            (str(attempt_dict["progression_attempt_id"]),),
        ).fetchall()
    ]
    if len(tokens) != 2 or [int(row["slot_ordinal"]) for row in tokens] != [1, 2]:
        raise StandardFourHourProgressionError(
            "standard 4h progression two-row aggregate is incomplete"
        )
    attempt_dict["authority_evidence"] = _object(
        attempt_dict["authority_evidence_json"], label="authority evidence"
    )
    attempt_dict["fault_details"] = _object(
        attempt_dict["fault_details_json"], label="attempt fault details"
    )
    for token in tokens:
        token["eligibility_evidence"] = _object(
            token["eligibility_evidence_json"], label="eligibility evidence"
        )
        token["disposition_reasons"] = json.loads(
            str(token["disposition_reasons_json"])
        )
        token["fault_details"] = _object(
            token["fault_details_json"], label="token fault details"
        )
    attempt_dict["tokens"] = tokens
    return attempt_dict


def _fault_envelope(
    *,
    cause: str,
    scope: str,
    stage: str,
    exc: BaseException | None,
    safe_message: str,
    source_reference: str | None,
    observed_at: str,
) -> dict[str, Any]:
    normalized_cause = str(cause or "").strip()
    if not normalized_cause:
        raise StandardFourHourProgressionError("progression fault cause is required")
    return {
        "cause": normalized_cause,
        "scope": str(scope),
        "stage": str(stage),
        "exception_class": None if exc is None else type(exc).__name__,
        "safe_message": _safe_fault_text(safe_message),
        "source_reference": source_reference,
        "observed_at": str(observed_at),
    }


def persist_progression_primary_fault(
    connection: sqlite3.Connection,
    *,
    progression_attempt_id: str,
    cause: str,
    state: str = "TERMINAL_FAILED",
    scope: str = "ATTEMPT",
    stage: str = "PROGRESSION_EVALUATION",
    exc: BaseException | None = None,
    safe_message: str | None = None,
    source_reference: str | None = None,
    authority_evidence: Mapping[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Atomically assign the first attempt primary; the first value wins."""
    if state not in {"TERMINAL_FAILED", "TERMINAL_CANCELLED", "INTERRUPTED_REVIEW"}:
        raise StandardFourHourProgressionError("invalid progression terminal state")
    timestamp = now or _utc_now()
    primary = _fault_envelope(
        cause=cause,
        scope=scope,
        stage=stage,
        exc=exc,
        safe_message=safe_message or str(exc or cause),
        source_reference=source_reference,
        observed_at=timestamp,
    )
    row = connection.execute(
        f"SELECT first_terminal_cause,fault_details_json FROM {ATTEMPT_TABLE} "
        "WHERE progression_attempt_id=?",
        (progression_attempt_id,),
    ).fetchone()
    if row is None:
        raise StandardFourHourProgressionError("progression attempt missing")
    if row[0] is not None:
        existing = _object(row[1], label="attempt fault details")
        return {"persisted": False, "first_terminal_cause": str(row[0]), **existing}
    faults = {"primary": primary, "secondary": []}
    values: list[Any] = [
        state,
        str(cause),
        _json(faults),
        timestamp,
        timestamp,
    ]
    authority_sql = ""
    if authority_evidence is not None:
        authority_sql = ", authority_evidence_json=?"
        values.append(_json(dict(authority_evidence)))
    values.extend([progression_attempt_id])
    cursor = connection.execute(
        f"""UPDATE {ATTEMPT_TABLE}
            SET attempt_state=?,first_terminal_cause=?,fault_details_json=?,
                terminal_at=?,updated_at=?{authority_sql}
            WHERE progression_attempt_id=? AND first_terminal_cause IS NULL
              AND attempt_state NOT IN (
                  'HANDOFF_COMMITTED','TERMINAL_FAILED','TERMINAL_CANCELLED',
                  'INTERRUPTED_REVIEW'
              )""",
        tuple(values),
    )
    if cursor.rowcount != 1:
        raise StandardFourHourProgressionError(
            "progression primary compare-and-set failed"
        )
    return {"persisted": True, "first_terminal_cause": str(cause), **faults}


def append_progression_secondary_fault(
    connection: sqlite3.Connection,
    *,
    progression_attempt_id: str,
    cause: str,
    stage: str,
    exc: BaseException | None = None,
    safe_message: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Append a later fact without changing the canonical progression primary."""
    timestamp = now or _utc_now()
    row = connection.execute(
        f"SELECT first_terminal_cause,fault_details_json FROM {ATTEMPT_TABLE} "
        "WHERE progression_attempt_id=?",
        (progression_attempt_id,),
    ).fetchone()
    if row is None or row[0] is None:
        raise StandardFourHourProgressionError(
            "secondary progression fault requires a durable primary"
        )
    faults = _object(row[1], label="attempt fault details")
    secondary = list(faults.get("secondary") or [])
    secondary.append(
        _fault_envelope(
            cause=cause,
            scope="ATTEMPT",
            stage=stage,
            exc=exc,
            safe_message=safe_message or str(exc or cause),
            source_reference=None,
            observed_at=timestamp,
        )
    )
    faults["secondary"] = secondary
    connection.execute(
        f"UPDATE {ATTEMPT_TABLE} SET fault_details_json=?,updated_at=? "
        "WHERE progression_attempt_id=?",
        (_json(faults), timestamp, progression_attempt_id),
    )
    return faults


def _connection_path(connection: sqlite3.Connection) -> str | None:
    rows = connection.execute("PRAGMA database_list").fetchall()
    main = [row for row in rows if str(row[1]) == "main"]
    return None if len(main) != 1 or not str(main[0][2]) else str(main[0][2])


def _predecessor_states(
    connection: sqlite3.Connection,
    *,
    aggregate: Mapping[str, Any],
) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for token in aggregate["tokens"]:
        if str(token["token_disposition"]) != "WAITING_FOR_PREDECESSOR":
            states.append({
                "kind": "PERSISTED",
                "reason": "TOKEN_DISPOSITION_ALREADY_TERMINAL",
                "token": token,
            })
            continue
        window_id = token["predecessor_window_1h_id"]
        if window_id is None:
            states.append({"kind": "INELIGIBLE", "reason": "NO_WINDOW_1H_PLANNED", "token": token})
            continue
        rows = connection.execute(
            """SELECT w.*,s.token_state
               FROM printer_memory_factory_campaign_windows AS w
               JOIN printer_memory_factory_campaign_token_slots AS s
                 ON s.token_slot_id=w.token_slot_id AND s.campaign_id=w.campaign_id
                AND s.run_id=w.run_id AND s.cycle_id=w.cycle_id
               WHERE w.window_id=? AND w.campaign_id=? AND w.run_id=?
                 AND w.cycle_id=? AND w.token_slot_id=?
                 AND w.window_kind='WINDOW_1H'""",
            (
                str(window_id),
                aggregate["campaign_id"],
                aggregate["campaign_run_id"],
                aggregate["cycle_id"],
                token["token_slot_id"],
            ),
        ).fetchall()
        if len(rows) != 1:
            states.append({"kind": "TOKEN_FAULT", "reason": "PREDECESSOR_WINDOW_MISSING_OR_AMBIGUOUS", "token": token})
            continue
        window = rows[0]
        closes = connection.execute(
            """SELECT s.*,j.status AS scheduler_status,j.last_error,
                      w.work_state,w.first_terminal_cause AS work_terminal_cause
               FROM printer_memory_factory_run_steps AS s
               LEFT JOIN printer_scheduler_jobs AS j ON j.id=s.scheduler_job_id
               LEFT JOIN printer_memory_factory_campaign_scheduler_work AS w
                 ON w.scheduler_job_id=s.scheduler_job_id
                AND w.campaign_id=? AND w.run_id=? AND w.cycle_id=?
                AND w.token_slot_id=? AND w.window_id=?
               WHERE s.run_id=? AND s.token_id=? AND s.pair_id=?
                 AND s.step_kind IN ('CONTINUATION_CLOSE','CONTINUATION_CLOSE_AUDIT')
               ORDER BY s.id""",
            (
                aggregate["campaign_id"],
                aggregate["campaign_run_id"],
                aggregate["cycle_id"],
                token["token_slot_id"],
                window_id,
                aggregate["factory_run_id"],
                int(token["token_row_id"]),
                int(token["pair_row_id"]),
            ),
        ).fetchall()
        if len(closes) != 1:
            states.append({"kind": "TOKEN_FAULT", "reason": "PREDECESSOR_CLOSE_MISSING_OR_AMBIGUOUS", "token": token, "window": window})
            continue
        close = closes[0]
        step_state = str(close["step_status"])
        scheduler_state = str(close["scheduler_status"] or "MISSING")
        work_state = str(close["work_state"] or "MISSING")
        if step_state in {"PENDING", "RUNNING"}:
            states.append({"kind": "ACTIVE", "reason": step_state, "token": token, "window": window, "close": close})
        elif scheduler_state == "CANCELLED" or str(window["window_state"]) == "CANCELLED":
            states.append({"kind": "INELIGIBLE", "reason": "PREDECESSOR_1H_CANCELLED", "token": token, "window": window, "close": close})
        elif step_state != "SUCCEEDED" or scheduler_state == "FAILED" or work_state == "FAILED":
            states.append({"kind": "INELIGIBLE", "reason": "PREDECESSOR_1H_FAILED", "token": token, "window": window, "close": close})
        elif scheduler_state != "SUCCEEDED" or work_state != "SUCCEEDED":
            states.append({"kind": "TOKEN_FAULT", "reason": "PREDECESSOR_TERMINAL_SURFACE_MISMATCH", "token": token, "window": window, "close": close})
        else:
            states.append({"kind": "SUCCEEDED", "reason": "PREDECESSOR_1H_SUCCEEDED", "token": token, "window": window, "close": close})
    return states


def _write_token_disposition(
    connection: sqlite3.Connection,
    *,
    token: Mapping[str, Any],
    disposition: str,
    reasons: Sequence[str],
    evidence: Mapping[str, Any],
    predecessor_memory_window_id: int | None,
    primary: Mapping[str, Any] | None = None,
    now: str,
) -> None:
    if disposition not in TOKEN_DISPOSITIONS:
        raise StandardFourHourProgressionError("invalid token disposition")
    first_cause = None if primary is None else str(primary["cause"])
    faults = EMPTY_FAULTS if primary is None else {"primary": dict(primary), "secondary": []}
    cursor = connection.execute(
        f"""UPDATE {TOKEN_TABLE}
            SET token_disposition=?,disposition_reasons_json=?,
                eligibility_evidence_json=?,predecessor_memory_window_id=?,
                first_terminal_cause=?,fault_details_json=?,evaluated_at=?,updated_at=?
            WHERE progression_token_id=?
              AND token_disposition='WAITING_FOR_PREDECESSOR'""",
        (
            disposition,
            _json(list(reasons)),
            _json(dict(evidence)),
            predecessor_memory_window_id,
            first_cause,
            _json(faults),
            now,
            now,
            token["progression_token_id"],
        ),
    )
    if cursor.rowcount != 1:
        raise StandardFourHourProgressionError(
            f"token progression compare-and-set failed: {token['token_slot_id']}"
        )


def evaluate_standard_4h_progression(
    connection: sqlite3.Connection,
    *,
    db_path: str,
    campaign_id: str,
    configuration_id: str,
    campaign_run_id: str,
    cycle_id: str,
    factory_run_id: str,
    operational_db_binding: OperationalDatabaseTargetBinding | None,
    canonical_authoritative_db_path: str,
    cancellation_probe: Any | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Evaluate exact committed predecessors and persist the complete subset."""
    if connection.in_transaction:
        raise StandardFourHourProgressionError(
            "progression evaluation requires committed predecessor truth"
        )
    timestamp = now or _utc_now()
    aggregate = load_standard_4h_progression_aggregate(
        connection,
        campaign_id=campaign_id,
        campaign_run_id=campaign_run_id,
        cycle_id=cycle_id,
    )
    if aggregate is None or str(aggregate["factory_run_id"]) != factory_run_id:
        raise StandardFourHourProgressionError("exact progression aggregate missing")
    state = str(aggregate["attempt_state"])
    if state in {"ELIGIBILITY_COMPLETE", "HANDOFF_COMMITTED"}:
        eligible = [
            str(token["token_slot_id"])
            for token in aggregate["tokens"]
            if str(token["token_disposition"]) in {
                "ELIGIBLE_PENDING_HANDOFF", "HANDOFF_CREATED"
            }
        ]
        return {
            "attempt_state": state,
            "eligible_token_slot_ids": eligible,
            "authority_evidence": aggregate["authority_evidence"],
            "tokens": aggregate["tokens"],
            "idempotent": True,
        }
    if state != "WAITING_FOR_PREDECESSORS":
        raise StandardFourHourProgressionError(
            f"progression attempt cannot evaluate from {state}"
        )

    predecessor_states = _predecessor_states(connection, aggregate=aggregate)
    if any(item["kind"] == "ACTIVE" for item in predecessor_states):
        return {
            "attempt_state": "WAITING_FOR_PREDECESSORS",
            "eligible_token_slot_ids": [],
            "authority_evidence": aggregate["authority_evidence"],
            "tokens": aggregate["tokens"],
            "idempotent": False,
        }

    pre_evaluation_cancellation = (
        None if cancellation_probe is None else cancellation_probe()
    )
    if pre_evaluation_cancellation:
        authority = {
            "producer": "existing cooperative cancellation probe",
            "supervision": {
                "cancellation_reason": str(pre_evaluation_cancellation),
            },
            "evaluation_started": False,
        }
        with connection:
            persist_progression_primary_fault(
                connection,
                progression_attempt_id=str(aggregate["progression_attempt_id"]),
                cause=str(pre_evaluation_cancellation),
                state="TERMINAL_CANCELLED",
                stage="PRE_EVALUATION_CANCELLATION",
                authority_evidence=authority,
                now=timestamp,
            )
        return {
            "attempt_state": "TERMINAL_CANCELLED",
            "eligible_token_slot_ids": [],
            "authority_evidence": authority,
            "tokens": aggregate["tokens"],
            "idempotent": False,
        }

    with connection:
        cursor = connection.execute(
            f"""UPDATE {ATTEMPT_TABLE} SET attempt_state='EVALUATING',updated_at=?
                WHERE progression_attempt_id=?
                  AND attempt_state='WAITING_FOR_PREDECESSORS'""",
            (timestamp, aggregate["progression_attempt_id"]),
        )
        if cursor.rowcount != 1:
            raise StandardFourHourProgressionError(
                "progression evaluation compare-and-set failed"
            )

    expected = load_durable_operational_database_target_expectation(
        db_path,
        campaign_id=campaign_id,
        campaign_run_id=campaign_run_id,
        cycle_id=cycle_id,
        configuration_id=configuration_id,
    )
    binding_reason = validate_operational_database_target_binding(
        operational_db_binding,
        actual_db_path=db_path,
        canonical_authoritative_db_path=canonical_authoritative_db_path,
        expected=expected or {},
    )
    schema = validate_runtime_schema_connection(connection, raise_on_error=False)
    connected_path = _connection_path(connection)
    graph = connection.execute(
        """SELECT c.campaign_state,r.run_state,r.authoritative_run_id,
                  cy.cycle_state,f.run_status,f.config_json
           FROM printer_memory_factory_campaigns AS c
           JOIN printer_memory_factory_campaign_runs AS r
             ON r.campaign_id=c.campaign_id AND r.run_id=?
           JOIN printer_memory_factory_campaign_cycles AS cy
             ON cy.campaign_id=c.campaign_id AND cy.run_id=r.run_id
            AND cy.cycle_id=?
           JOIN printer_memory_factory_runs AS f
             ON f.run_id=r.authoritative_run_id
           WHERE c.campaign_id=?""",
        (campaign_run_id, cycle_id, campaign_id),
    ).fetchone()
    supervision_row = connection.execute(
        """SELECT supervision_id,owner_id FROM printer_memory_factory_campaign_supervision
           WHERE campaign_id=? AND configuration_id=? AND run_id=?""",
        (campaign_id, configuration_id, campaign_run_id),
    ).fetchall()
    supervision: Mapping[str, Any] | None = None
    if len(supervision_row) == 1:
        supervision = inspect_campaign_supervision(
            db_path,
            supervision_id=str(supervision_row[0][0]),
            campaign_id=campaign_id,
            configuration_id=configuration_id,
            run_id=campaign_run_id,
            owner_id=str(supervision_row[0][1]),
            now=datetime.fromisoformat(timestamp),
        )
    cancellation_reason = None if cancellation_probe is None else cancellation_probe()
    from printer_v1.operator_cli.authoritative_admission_health import (
        project_scheduler_health,
    )
    from printer_v1.operator_cli.one_command_15m_factory import (
        _run_request_count,
        _run_step_job_count,
        _token_request_count,
    )
    from printer_v1.operator_cli.one_token_4h_runtime import (
        cumulative_lifecycle_budget,
        require_projected_capacity,
        runtime_budget,
        standard_campaign_lifecycle_budget,
    )

    health_binding = MultiCycleCampaignBinding(
        campaign_id=campaign_id,
        campaign_run_id=campaign_run_id,
        configuration_id=configuration_id,
        authoritative_factory_run_id=factory_run_id,
    )
    scheduler = project_scheduler_health(
        connection, binding=health_binding, first_cycle_id=cycle_id
    )
    active_work = campaign_active_work_report(
        connection,
        factory_run_id=factory_run_id,
        campaign_id=campaign_id,
        run_id=campaign_run_id,
        cycle_id=cycle_id,
    )
    config = {} if graph is None else _object(graph[5], label="factory run config")
    graph_healthy = bool(
        graph is not None
        and str(graph[0]) == "RUNNING"
        and str(graph[1]) == "RUNNING"
        and str(graph[2]) == factory_run_id
        and str(graph[3]) in {"PLANNED", "TRACKING", "CLOSING", "AUDITING"}
        and str(graph[4]) == "RUNNING"
        and config.get("standard_four_hour_campaign") is True
    )
    supervision_healthy = bool(
        supervision is not None
        and supervision.get("supervision_state") == "ACTIVE"
        and supervision.get("lease_expired") is False
        and supervision.get("new_child_work_allowed") is True
    )
    campaign_stop_requested = bool(
        graph is not None and str(graph[0]) == "STOP_REQUESTED"
    )
    run_stop_requested = bool(
        graph is not None and str(graph[1]) == "STOP_REQUESTED"
    )
    cancelled = bool(
        cancellation_reason
        or campaign_stop_requested
        or run_stop_requested
        or supervision is None
        or supervision.get("cancellation_requested_at") is not None
    )
    lanes = tuple(str(token["tracking_lane"]) for token in aggregate["tokens"])
    run_requests = _run_request_count(connection, factory_run_id)
    run_jobs = _run_step_job_count(connection, factory_run_id)
    authority = {
        "campaign": {
            "campaign_state": None if graph is None else str(graph[0]),
            "run_state": None if graph is None else str(graph[1]),
            "cycle_state": None if graph is None else str(graph[3]),
            "factory_run_state": None if graph is None else str(graph[4]),
            "standard_four_hour_campaign": config.get("standard_four_hour_campaign") is True,
        },
        "database": {
            "binding_validation": "VALID" if binding_reason is None else binding_reason,
            "runtime_schema_ready": schema.get("runtime_ready") is True,
            "connected_path": connected_path,
        },
        "supervision": {
            "supervision_id": None if supervision is None else supervision.get("supervision_id"),
            "state": None if supervision is None else supervision.get("supervision_state"),
            "lease_expired": None if supervision is None else supervision.get("lease_expired"),
            "new_child_work_allowed": None if supervision is None else supervision.get("new_child_work_allowed"),
            "cancellation_reason": cancellation_reason,
        },
        "scheduler": {
            "integrity_healthy": scheduler.scheduler_due_work_healthy,
            "reasons": list(scheduler.reasons),
            "attributable_job_ids": list(scheduler.attributable_job_ids),
            "active_jobs": int(active_work["active_jobs"]),
        },
        "campaign_budget": {
            "evaluated": False,
            "available": None,
            "actual_run_requests": run_requests,
            "actual_scheduler_jobs": run_jobs,
            "reason": "AWAITING_EXACT_ELIGIBLE_MASK",
        },
    }
    shared_cause = None
    terminal_state = "TERMINAL_FAILED"
    if cancelled:
        shared_cause = str(
            cancellation_reason
            or (
                "CAMPAIGN_STOP_REQUESTED"
                if campaign_stop_requested
                else "CAMPAIGN_RUN_STOP_REQUESTED"
                if run_stop_requested
                else "CAMPAIGN_CANCELLATION_REQUESTED"
            )
        )
        terminal_state = "TERMINAL_CANCELLED"
    elif binding_reason is not None or schema.get("runtime_ready") is not True or connected_path is None:
        shared_cause = str(binding_reason or "STANDARD_4H_DATABASE_INTEGRITY_FAILED")
    elif not graph_healthy:
        shared_cause = "STANDARD_4H_CAMPAIGN_GRAPH_NOT_LIVE"
    elif not supervision_healthy:
        shared_cause = "STANDARD_4H_SUPERVISION_OR_LEASE_NOT_HEALTHY"
    elif not scheduler.scheduler_due_work_healthy:
        shared_cause = "STANDARD_4H_SCHEDULER_INTEGRITY_FAILED"
    if shared_cause is not None:
        with connection:
            persist_progression_primary_fault(
                connection,
                progression_attempt_id=str(aggregate["progression_attempt_id"]),
                cause=shared_cause,
                state=terminal_state,
                authority_evidence=authority,
                now=timestamp,
            )
        return {
            "attempt_state": terminal_state,
            "eligible_token_slot_ids": [],
            "authority_evidence": authority,
            "tokens": aggregate["tokens"],
            "idempotent": False,
        }

    from printer_v1.operator_cli.operational_standard_4h import (
        CampaignContinuationContext,
        _continuation_input,
    )
    from printer_v1.scheduler.token_local_continuation import _evaluate_token
    campaign_context = CampaignContinuationContext(
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        campaign_state=str(graph[0]),
        campaign_eligible=graph_healthy,
        shared_db_healthy=binding_reason is None and schema.get("runtime_ready") is True,
        shared_lease_healthy=supervision_healthy,
        shared_integrity_healthy=scheduler.scheduler_due_work_healthy,
        campaign_budget_available=True,
    )
    eligible: list[str] = []
    candidates: dict[str, dict[str, Any]] = {}
    cycle_row = connection.execute(
        """SELECT cycle_ordinal FROM printer_memory_factory_campaign_cycles
           WHERE campaign_id=? AND run_id=? AND cycle_id=?""",
        (campaign_id, campaign_run_id, cycle_id),
    ).fetchone()
    if cycle_row is None or int(cycle_row[0]) <= 0:
        raise StandardFourHourProgressionError("exact cycle ordinal missing")
    cycle_ordinal = int(cycle_row[0])
    decisions: list[dict[str, Any]] = []
    for item in predecessor_states:
        token_row = item["token"]
        slot_id = str(token_row["token_slot_id"])
        if item["kind"] == "PERSISTED":
            decisions.append({
                "token": token_row,
                "disposition": str(token_row["token_disposition"]),
                "already_persisted": True,
            })
            continue
        token_budget = cumulative_lifecycle_budget(str(token_row["tracking_lane"]))
        token_phase_budget = runtime_budget(str(token_row["tracking_lane"]))
        token_prefix = (
            f"t{int(token_row['slot_ordinal'])}"
            if cycle_ordinal == 1
            else f"t{int(token_row['slot_ordinal'])}_c{cycle_ordinal:04d}"
        )
        token_run_requests = _token_request_count(
            connection, factory_run_id, token_prefix
        )
        token_actual_requests = (
            int(token_budget["request_components"]["discovery"])
            + token_run_requests
        )
        token_budget_available = (
            token_actual_requests
            + int(token_phase_budget["phase_request_ceiling"])
            <= int(token_budget["request_ceiling"])
        )
        token_evidence = {
            "predecessor_state": item["kind"],
            "predecessor_reason": item["reason"],
            "predecessor_reference": {
                "window_id": token_row["predecessor_window_1h_id"],
                "window_state": (
                    None
                    if item.get("window") is None
                    else str(item["window"]["window_state"])
                ),
                "close_step_id": (
                    None if item.get("close") is None else int(item["close"]["id"])
                ),
                "step_status": (
                    None
                    if item.get("close") is None
                    else str(item["close"]["step_status"])
                ),
                "scheduler_job_id": (
                    None
                    if item.get("close") is None
                    or item["close"]["scheduler_job_id"] is None
                    else int(item["close"]["scheduler_job_id"])
                ),
                "scheduler_status": (
                    None
                    if item.get("close") is None
                    else str(item["close"]["scheduler_status"] or "MISSING")
                ),
                "work_state": (
                    None
                    if item.get("close") is None
                    else str(item["close"]["work_state"] or "MISSING")
                ),
            },
            "predecessor_terminal_cause": (
                None
                if item.get("close") is None
                else item["close"]["work_terminal_cause"]
                or item["close"]["last_error"]
                or str(item["reason"])
            ),
            "tracking_queue_id": int(token_row["tracking_queue_id"]),
            "tracking_lane": str(token_row["tracking_lane"]),
            "token_budget": {
                "available": token_budget_available,
                "actual_requests": token_actual_requests,
                "actual_run_requests": token_run_requests,
                "request_ceiling": int(token_budget["request_ceiling"]),
                "projected_standard_4h_requests": int(
                    token_phase_budget["phase_request_ceiling"]
                ),
                "token_step_prefix": token_prefix,
            },
        }
        memory_id = (
            None
            if item.get("window") is None
            else item["window"]["memory_window_row_id"]
        )
        if item["kind"] == "INELIGIBLE":
            decisions.append({
                "token": token_row,
                "disposition": "INELIGIBLE",
                "reasons": (str(item["reason"]),),
                "evidence": token_evidence,
                "predecessor_memory_window_id": memory_id,
                "primary": None,
            })
            continue
        try:
            cadence = resolve_campaign_slot_cadence_authority(
                connection,
                campaign_window_id=str(token_row["predecessor_window_1h_id"]),
                campaign_id=campaign_id,
                campaign_run_id=campaign_run_id,
                cycle_id=cycle_id,
                token_slot_id=slot_id,
            )
            if (
                cadence.status != CADENCE_AUTHORITY_RESOLVED
                or cadence.tracking_queue_id != int(token_row["tracking_queue_id"])
                or cadence.tracking_lane != str(token_row["tracking_lane"])
            ):
                raise StandardFourHourProgressionError(
                    f"TOKEN_TRACKING_AUTHORITY_MISMATCH:{cadence.reason_code}"
                )
            if item["kind"] == "TOKEN_FAULT":
                raise StandardFourHourProgressionError(str(item["reason"]))
            token_input, candidate = _continuation_input(
                connection,
                db_path=db_path,
                campaign_id=campaign_id,
                configuration_id=configuration_id,
                run_id=campaign_run_id,
                cycle_id=cycle_id,
                slot=token_row,
                state={"window": item["window"], "close": item["close"]},
                token_budget_available=token_budget_available,
                tracking_lane=str(cadence.tracking_lane),
                token_eligible=True,
                cancelled=False,
                terminal=False,
            )
            candidate["tracking_lane"] = str(cadence.tracking_lane)
            result = _evaluate_token(campaign_context, token_input)
            reasons = tuple(str(reason) for reason in result.reasons)
            disposition = (
                "ELIGIBLE_PENDING_HANDOFF"
                if str(result.verdict.value) == "CONTINUE_TO_WINDOW_4H"
                else "INELIGIBLE"
            )
            decisions.append({
                "token": token_row,
                "disposition": disposition,
                "reasons": reasons,
                "evidence": token_evidence,
                "predecessor_memory_window_id": int(memory_id),
                "primary": None,
            })
            candidates[slot_id] = candidate
            if disposition == "ELIGIBLE_PENDING_HANDOFF":
                eligible.append(slot_id)
        except sqlite3.Error:
            raise
        except Exception as exc:
            primary = _fault_envelope(
                cause="TOKEN_LOCAL_PROGRESSION_INTEGRITY_FAILURE",
                scope="TOKEN",
                stage="TOKEN_ELIGIBILITY",
                exc=exc,
                safe_message=str(exc),
                source_reference=slot_id,
                observed_at=timestamp,
            )
            decisions.append({
                "token": token_row,
                "disposition": "TERMINAL_FAILED",
                "reasons": ("TOKEN_LOCAL_PROGRESSION_INTEGRITY_FAILURE",),
                "evidence": token_evidence,
                "predecessor_memory_window_id": memory_id,
                "primary": primary,
            })

    continuing_mask = tuple(
        str(decision["disposition"]) == "ELIGIBLE_PENDING_HANDOFF"
        for decision in decisions
    )
    campaign_budget = standard_campaign_lifecycle_budget(lanes, continuing_mask)
    budget_owner = "standard_campaign_lifecycle_budget"
    request_ceiling = int(campaign_budget["request_ceiling"])
    scheduler_ceiling = int(campaign_budget["scheduler_ceiling"])
    discovery_reserve = int(campaign_budget["request_components"]["discovery"])
    if config.get("four_token_proof") is True:
        from printer_v1.operator_cli.multi_cycle_memory_growth import (
            scaled_standard_four_hour_capacity_contract,
        )

        scaled = scaled_standard_four_hour_capacity_contract(4)
        budget_owner = "scaled_standard_four_hour_capacity_contract(4)"
        request_ceiling = int(scaled["lifecycle_request_outer_ceiling"])
        scheduler_ceiling = int(scaled["lifecycle_scheduler_outer_ceiling"])
        discovery_reserve = int(scaled["shared_discovery_requests"])
    actual_requests = discovery_reserve + run_requests
    campaign_budget_available = True
    try:
        require_projected_capacity(
            current=actual_requests,
            projected=int(campaign_budget["phase_request_ceiling"]),
            ceiling=request_ceiling,
            label="standard 4h campaign request",
        )
        require_projected_capacity(
            current=run_jobs,
            projected=int(campaign_budget["phase_scheduler_ceiling"]),
            ceiling=scheduler_ceiling,
            label="standard 4h campaign Scheduler",
        )
    except ValueError:
        campaign_budget_available = False
    authority["campaign_budget"] = {
        "evaluated": True,
        "available": campaign_budget_available,
        "owner": budget_owner,
        "continuing_mask": list(continuing_mask),
        "actual_requests": actual_requests,
        "actual_run_requests": run_requests,
        "actual_scheduler_jobs": run_jobs,
        "projected_standard_4h_requests": int(
            campaign_budget["phase_request_ceiling"]
        ),
        "projected_standard_4h_scheduler_jobs": int(
            campaign_budget["phase_scheduler_ceiling"]
        ),
        "request_ceiling": request_ceiling,
        "scheduler_ceiling": scheduler_ceiling,
    }
    if not campaign_budget_available:
        with connection:
            persist_progression_primary_fault(
                connection,
                progression_attempt_id=str(aggregate["progression_attempt_id"]),
                cause="STANDARD_4H_GLOBAL_BUDGET_UNAVAILABLE",
                state="TERMINAL_FAILED",
                authority_evidence=authority,
                now=timestamp,
            )
        return {
            "attempt_state": "TERMINAL_FAILED",
            "eligible_token_slot_ids": [],
            "authority_evidence": authority,
            "tokens": aggregate["tokens"],
            "idempotent": False,
        }

    with connection:
        for decision in decisions:
            if decision.get("already_persisted") is True:
                continue
            _write_token_disposition(
                connection,
                token=decision["token"],
                disposition=str(decision["disposition"]),
                reasons=decision["reasons"],
                evidence=decision["evidence"],
                predecessor_memory_window_id=decision[
                    "predecessor_memory_window_id"
                ],
                primary=decision["primary"],
                now=timestamp,
            )
        connection.execute(
            f"""UPDATE {ATTEMPT_TABLE}
                SET attempt_state='ELIGIBILITY_COMPLETE',authority_evidence_json=?,
                    eligibility_completed_at=?,updated_at=?
                WHERE progression_attempt_id=? AND attempt_state='EVALUATING'""",
            (_json(authority), timestamp, timestamp, aggregate["progression_attempt_id"]),
        )
    refreshed = load_standard_4h_progression_aggregate(
        connection,
        campaign_id=campaign_id,
        campaign_run_id=campaign_run_id,
        cycle_id=cycle_id,
    )
    if refreshed is None or str(refreshed["attempt_state"]) != "ELIGIBILITY_COMPLETE":
        raise StandardFourHourProgressionError("eligibility read-back failed")
    return {
        "attempt_state": "ELIGIBILITY_COMPLETE",
        "eligible_token_slot_ids": sorted(eligible),
        "authority_evidence": authority,
        "tokens": refreshed["tokens"],
        "candidates": [candidates[key] for key in sorted(candidates)],
        "idempotent": False,
    }


def commit_standard_4h_progression_handoff(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
    cycle_id: str,
    factory_run_id: str,
    db_path: str,
    configuration_id: str,
    operational_db_binding: OperationalDatabaseTargetBinding | None,
    canonical_authoritative_db_path: str,
    cancellation_probe: Any | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Delegate the exact durable 0/1/2 subset to the existing atomic planner."""
    if connection.in_transaction:
        raise StandardFourHourProgressionError(
            "standard 4h handoff requires a clean transaction boundary"
        )
    aggregate = load_standard_4h_progression_aggregate(
        connection,
        campaign_id=campaign_id,
        campaign_run_id=campaign_run_id,
        cycle_id=cycle_id,
    )
    if aggregate is None or str(aggregate["factory_run_id"]) != factory_run_id:
        raise StandardFourHourProgressionError("exact progression aggregate missing")
    if str(aggregate["attempt_state"]) not in {
        "ELIGIBILITY_COMPLETE",
        "HANDOFF_COMMITTED",
    }:
        raise StandardFourHourProgressionError(
            "standard 4h handoff requires complete eligibility"
        )

    from printer_v1.operator_cli.operational_selective_1h import (
        campaign_window_id_for,
    )
    from printer_v1.operator_cli.one_token_4h_runtime import (
        FourHourExecutionAuthority,
        cumulative_lifecycle_budget,
        plan_standard_campaign_4h_handoff,
        require_projected_capacity,
        runtime_budget,
        standard_campaign_lifecycle_budget,
    )

    candidates: list[dict[str, Any]] = []
    eligible: list[str] = []
    for token in aggregate["tokens"]:
        slot_id = str(token["token_slot_id"])
        memory_id = token["predecessor_memory_window_id"]
        period_key = (
            str(memory_id)
            if memory_id is not None
            else str(token["progression_token_id"])
        )
        candidates.append(
            {
                "token_slot_id": slot_id,
                "token_row_id": int(token["token_row_id"]),
                "pair_row_id": int(token["pair_row_id"]),
                "mint_identity": str(token["mint_identity"]),
                "pair_identity": str(token["pair_identity"]),
                "lifecycle_identity": str(token["lifecycle_identity"]),
                "campaign_window_1h_id": token["predecessor_window_1h_id"],
                "memory_window_1h_id": memory_id,
                "campaign_window_4h_id": campaign_window_id_for(
                    campaign_id=campaign_id,
                    run_id=campaign_run_id,
                    cycle_id=cycle_id,
                    token_slot_id=slot_id,
                    window_kind="WINDOW_4H",
                    period_key=period_key,
                ),
                "tracking_lane": str(token["tracking_lane"]),
            }
        )
        if str(token["token_disposition"]) in {
            "ELIGIBLE_PENDING_HANDOFF",
            "HANDOFF_CREATED",
        }:
            eligible.append(slot_id)

    # Re-read every shared authority immediately before the atomic handoff.
    expected = load_durable_operational_database_target_expectation(
        db_path,
        campaign_id=campaign_id,
        campaign_run_id=campaign_run_id,
        cycle_id=cycle_id,
        configuration_id=configuration_id,
    )
    binding_reason = validate_operational_database_target_binding(
        operational_db_binding,
        actual_db_path=db_path,
        canonical_authoritative_db_path=canonical_authoritative_db_path,
        expected=expected or {},
    )
    schema = validate_runtime_schema_connection(connection, raise_on_error=False)
    graph = connection.execute(
        """SELECT c.campaign_state,r.run_state,cy.cycle_state,f.run_status,
                  f.config_json,cy.cycle_ordinal
           FROM printer_memory_factory_campaigns AS c
           JOIN printer_memory_factory_campaign_runs AS r
             ON r.campaign_id=c.campaign_id AND r.run_id=?
           JOIN printer_memory_factory_campaign_cycles AS cy
             ON cy.campaign_id=c.campaign_id AND cy.run_id=r.run_id
            AND cy.cycle_id=?
           JOIN printer_memory_factory_runs AS f
             ON f.run_id=r.authoritative_run_id
           WHERE c.campaign_id=? AND r.authoritative_run_id=?""",
        (campaign_run_id, cycle_id, campaign_id, factory_run_id),
    ).fetchone()
    supervision_rows = connection.execute(
        """SELECT supervision_id,owner_id
           FROM printer_memory_factory_campaign_supervision
           WHERE campaign_id=? AND configuration_id=? AND run_id=?""",
        (campaign_id, configuration_id, campaign_run_id),
    ).fetchall()
    supervision = None
    if len(supervision_rows) == 1:
        supervision = inspect_campaign_supervision(
            db_path,
            supervision_id=str(supervision_rows[0][0]),
            campaign_id=campaign_id,
            configuration_id=configuration_id,
            run_id=campaign_run_id,
            owner_id=str(supervision_rows[0][1]),
            now=datetime.fromisoformat(now or _utc_now()),
        )
    cancellation_reason = (
        None if cancellation_probe is None else cancellation_probe()
    )
    from printer_v1.operator_cli.authoritative_admission_health import (
        project_scheduler_health,
    )
    from printer_v1.operator_cli.one_command_15m_factory import (
        _run_request_count,
        _run_step_job_count,
        _token_request_count,
    )
    scheduler = project_scheduler_health(
        connection,
        binding=MultiCycleCampaignBinding(
            campaign_id=campaign_id,
            campaign_run_id=campaign_run_id,
            configuration_id=configuration_id,
            authoritative_factory_run_id=factory_run_id,
        ),
        first_cycle_id=cycle_id,
    )
    lanes = tuple(str(token["tracking_lane"]) for token in aggregate["tokens"])
    mask = tuple(
        str(token["token_slot_id"]) in set(eligible)
        for token in aggregate["tokens"]
    )
    budget = standard_campaign_lifecycle_budget(lanes, mask)
    config = {} if graph is None else _object(graph[4], label="factory run config")
    request_ceiling = int(budget["request_ceiling"])
    scheduler_ceiling = int(budget["scheduler_ceiling"])
    discovery_reserve = int(budget["request_components"]["discovery"])
    budget_owner = "standard_campaign_lifecycle_budget"
    if config.get("four_token_proof") is True:
        from printer_v1.operator_cli.multi_cycle_memory_growth import (
            scaled_standard_four_hour_capacity_contract,
        )

        scaled = scaled_standard_four_hour_capacity_contract(4)
        request_ceiling = int(scaled["lifecycle_request_outer_ceiling"])
        scheduler_ceiling = int(scaled["lifecycle_scheduler_outer_ceiling"])
        discovery_reserve = int(scaled["shared_discovery_requests"])
        budget_owner = "scaled_standard_four_hour_capacity_contract(4)"
    run_requests = _run_request_count(connection, factory_run_id)
    run_jobs = _run_step_job_count(connection, factory_run_id)
    budget_reason = None
    try:
        require_projected_capacity(
            current=discovery_reserve + run_requests,
            projected=int(budget["phase_request_ceiling"]),
            ceiling=request_ceiling,
            label="standard 4h handoff request",
        )
        require_projected_capacity(
            current=run_jobs,
            projected=int(budget["phase_scheduler_ceiling"]),
            ceiling=scheduler_ceiling,
            label="standard 4h handoff Scheduler",
        )
        cycle_ordinal = 0 if graph is None else int(graph[5])
        if cycle_ordinal <= 0:
            raise ValueError("exact cycle ordinal missing")
        for token in aggregate["tokens"]:
            if str(token["token_slot_id"]) not in set(eligible):
                continue
            token_prefix = (
                f"t{int(token['slot_ordinal'])}"
                if cycle_ordinal == 1
                else f"t{int(token['slot_ordinal'])}_c{cycle_ordinal:04d}"
            )
            token_budget = cumulative_lifecycle_budget(str(token["tracking_lane"]))
            token_phase = runtime_budget(str(token["tracking_lane"]))
            token_actual = (
                int(token_budget["request_components"]["discovery"])
                + _token_request_count(connection, factory_run_id, token_prefix)
            )
            require_projected_capacity(
                current=token_actual,
                projected=int(token_phase["phase_request_ceiling"]),
                ceiling=int(token_budget["request_ceiling"]),
                label=f"standard 4h token {token['token_slot_id']} request",
            )
    except ValueError as exc:
        budget_reason = str(exc)
    graph_live = bool(
        graph is not None
        and str(graph[0]) == "RUNNING"
        and str(graph[1]) == "RUNNING"
        and str(graph[2]) in {"PLANNED", "TRACKING", "CLOSING", "AUDITING"}
        and str(graph[3]) == "RUNNING"
    )
    supervision_live = bool(
        supervision is not None
        and supervision.get("supervision_state") == "ACTIVE"
        and supervision.get("lease_expired") is False
        and supervision.get("new_child_work_allowed") is True
    )
    persisted_cancellation = (
        "CAMPAIGN_STOP_REQUESTED"
        if graph is not None and str(graph[0]) == "STOP_REQUESTED"
        else "CAMPAIGN_RUN_STOP_REQUESTED"
        if graph is not None and str(graph[1]) == "STOP_REQUESTED"
        else str(supervision.get("cancellation_reason"))
        if supervision is not None
        and supervision.get("cancellation_requested_at") is not None
        else None
    )
    shared_cancellation = cancellation_reason or persisted_cancellation
    handoff_block = (
        str(shared_cancellation)
        if shared_cancellation
        else binding_reason
        or (None if schema.get("runtime_ready") is True else "RUNTIME_SCHEMA_NOT_READY")
        or (None if graph_live else "CAMPAIGN_GRAPH_NOT_LIVE")
        or (None if supervision_live else "SUPERVISION_OR_LEASE_NOT_LIVE")
        or (None if scheduler.scheduler_due_work_healthy else "SCHEDULER_INTEGRITY_FAILED")
        or budget_reason
    )
    if handoff_block is not None:
        raise StandardFourHourProgressionError(
            f"standard 4h handoff authority blocked: {handoff_block}",
            terminal_cause=str(handoff_block),
            terminal_state=(
                "TERMINAL_CANCELLED"
                if shared_cancellation
                else "TERMINAL_FAILED"
            ),
        )

    def _atomic_precondition(atomic_connection: sqlite3.Connection) -> None:
        atomic_binding_reason = validate_operational_database_target_binding(
            operational_db_binding,
            actual_db_path=db_path,
            canonical_authoritative_db_path=canonical_authoritative_db_path,
            expected=expected or {},
        )
        atomic_schema = validate_runtime_schema_connection(
            atomic_connection, raise_on_error=False
        )
        atomic_graph = atomic_connection.execute(
            """SELECT c.campaign_state,r.run_state,cy.cycle_state,f.run_status,
                      f.config_json,cy.cycle_ordinal
               FROM printer_memory_factory_campaigns AS c
               JOIN printer_memory_factory_campaign_runs AS r
                 ON r.campaign_id=c.campaign_id AND r.run_id=?
               JOIN printer_memory_factory_campaign_cycles AS cy
                 ON cy.campaign_id=c.campaign_id AND cy.run_id=r.run_id
                AND cy.cycle_id=?
               JOIN printer_memory_factory_runs AS f
                 ON f.run_id=r.authoritative_run_id
               WHERE c.campaign_id=? AND r.authoritative_run_id=?""",
            (campaign_run_id, cycle_id, campaign_id, factory_run_id),
        ).fetchone()
        atomic_supervision = None
        if len(supervision_rows) == 1:
            atomic_supervision = inspect_campaign_supervision(
                db_path,
                supervision_id=str(supervision_rows[0][0]),
                campaign_id=campaign_id,
                configuration_id=configuration_id,
                run_id=campaign_run_id,
                owner_id=str(supervision_rows[0][1]),
                now=datetime.fromisoformat(now or _utc_now()),
            )
        atomic_cancellation = (
            None if cancellation_probe is None else cancellation_probe()
        )
        atomic_scheduler = project_scheduler_health(
            atomic_connection,
            binding=MultiCycleCampaignBinding(
                campaign_id=campaign_id,
                campaign_run_id=campaign_run_id,
                configuration_id=configuration_id,
                authoritative_factory_run_id=factory_run_id,
            ),
            first_cycle_id=cycle_id,
        )
        atomic_persisted_cancellation = (
            "CAMPAIGN_STOP_REQUESTED"
            if atomic_graph is not None
            and str(atomic_graph[0]) == "STOP_REQUESTED"
            else "CAMPAIGN_RUN_STOP_REQUESTED"
            if atomic_graph is not None
            and str(atomic_graph[1]) == "STOP_REQUESTED"
            else str(atomic_supervision.get("cancellation_reason"))
            if atomic_supervision is not None
            and atomic_supervision.get("cancellation_requested_at") is not None
            else None
        )
        atomic_stop = atomic_cancellation or atomic_persisted_cancellation
        if atomic_stop:
            raise StandardFourHourProgressionError(
                f"standard 4h atomic cancellation: {atomic_stop}",
                terminal_cause=str(atomic_stop),
                terminal_state="TERMINAL_CANCELLED",
            )
        if (
            atomic_binding_reason is not None
            or atomic_schema.get("runtime_ready") is not True
            or atomic_graph is None
            or tuple(atomic_graph) != tuple(graph)
            or atomic_supervision is None
            or atomic_supervision.get("supervision_state") != "ACTIVE"
            or atomic_supervision.get("lease_expired") is not False
            or atomic_supervision.get("new_child_work_allowed") is not True
            or not atomic_scheduler.scheduler_due_work_healthy
        ):
            raise StandardFourHourProgressionError(
                "standard 4h atomic shared authority changed",
                terminal_cause="STANDARD_4H_ATOMIC_AUTHORITY_CHANGED",
            )
        try:
            require_projected_capacity(
                current=discovery_reserve
                + _run_request_count(atomic_connection, factory_run_id),
                projected=int(budget["phase_request_ceiling"]),
                ceiling=request_ceiling,
                label="standard 4h atomic campaign request",
            )
            require_projected_capacity(
                current=_run_step_job_count(atomic_connection, factory_run_id),
                projected=int(budget["phase_scheduler_ceiling"]),
                ceiling=scheduler_ceiling,
                label="standard 4h atomic campaign Scheduler",
            )
            for token in aggregate["tokens"]:
                if str(token["token_slot_id"]) not in set(eligible):
                    continue
                token_prefix = (
                    f"t{int(token['slot_ordinal'])}"
                    if int(graph[5]) == 1
                    else f"t{int(token['slot_ordinal'])}_c{int(graph[5]):04d}"
                )
                token_budget = cumulative_lifecycle_budget(
                    str(token["tracking_lane"])
                )
                token_phase = runtime_budget(str(token["tracking_lane"]))
                require_projected_capacity(
                    current=int(token_budget["request_components"]["discovery"])
                    + _token_request_count(
                        atomic_connection, factory_run_id, token_prefix
                    ),
                    projected=int(token_phase["phase_request_ceiling"]),
                    ceiling=int(token_budget["request_ceiling"]),
                    label=f"standard 4h atomic token {token['token_slot_id']} request",
                )
        except ValueError as exc:
            raise StandardFourHourProgressionError(
                str(exc), terminal_cause=str(exc)
            ) from exc
    try:
        planned = plan_standard_campaign_4h_handoff(
            connection,
            campaign_id=campaign_id,
            run_id=campaign_run_id,
            cycle_id=cycle_id,
            factory_run_id=factory_run_id,
            candidates=candidates,
            eligible_token_slot_ids=eligible,
            execution_authority=FourHourExecutionAuthority.STANDARD_CAMPAIGN,
            atomic_precondition=_atomic_precondition,
            now=now,
        )
        return {
            **planned,
            "handoff_authority": {
                "database_binding": "VALID",
                "runtime_schema_ready": True,
                "campaign_graph_live": True,
                "supervision_lease_live": True,
                "scheduler_integrity_healthy": True,
                "cancellation_reason": None,
                "budget": {
                    **budget,
                    "owner": budget_owner,
                    "actual_requests": discovery_reserve + run_requests,
                    "actual_scheduler_jobs": run_jobs,
                    "request_ceiling": request_ceiling,
                    "scheduler_ceiling": scheduler_ceiling,
                },
            },
        }
    except sqlite3.Error:
        raise
    except StandardFourHourProgressionError:
        raise
    except Exception as exc:
        raise StandardFourHourProgressionError(str(exc)) from exc


def derive_standard_4h_progression_status(
    connection: sqlite3.Connection,
    *,
    factory_run_id: str,
    campaign_id: str,
    campaign_run_id: str,
    cycle_id: str,
    ownership_active: bool | None = None,
) -> dict[str, Any]:
    """Derive one DB-backed progression/accounting view for every consumer."""
    run = connection.execute(
        "SELECT config_json,run_status FROM printer_memory_factory_runs WHERE run_id=?",
        (factory_run_id,),
    ).fetchone()
    config = {} if run is None else _object(run[0], label="factory run config")
    required = config.get("standard_four_hour_campaign") is True
    if not required:
        return {
            "enabled": False,
            "complete": True,
            "aggregate_state": "NOT_APPLICABLE",
            "requires_review": False,
            "reasons": [],
            "per_token": [],
        }
    aggregate = load_standard_4h_progression_aggregate(
        connection,
        campaign_id=campaign_id,
        campaign_run_id=campaign_run_id,
        cycle_id=cycle_id,
    )
    if aggregate is None:
        return {
            "enabled": True,
            "complete": False,
            "aggregate_state": "INTERRUPTED_AMBIGUOUS",
            "requires_review": True,
            "reasons": ["STANDARD_4H_PROGRESSION_ATTEMPT_MISSING"],
            "per_token": [],
        }
    state = str(aggregate["attempt_state"])
    if ownership_active is None:
        supervision_rows = connection.execute(
            """SELECT supervision_state,lease_expires_at
               FROM printer_memory_factory_campaign_supervision
               WHERE campaign_id=? AND configuration_id=? AND run_id=?""",
            (
                campaign_id,
                str(aggregate["configuration_id"]),
                campaign_run_id,
            ),
        ).fetchall()
        lease_live = False
        if len(supervision_rows) == 1:
            try:
                expiry = datetime.fromisoformat(
                    str(supervision_rows[0]["lease_expires_at"])
                )
                lease_live = (
                    expiry.tzinfo is not None
                    and expiry.astimezone(timezone.utc)
                    > datetime.now(timezone.utc)
                )
            except (TypeError, ValueError):
                lease_live = False
        ownership_active = bool(
            run is not None
            and str(run[1]) == "RUNNING"
            and len(supervision_rows) == 1
            and str(supervision_rows[0]["supervision_state"]) == "ACTIVE"
            and lease_live
        )
    per_token: list[dict[str, Any]] = []
    for token in aggregate["tokens"]:
        disposition = str(token["token_disposition"])
        if disposition == "WAITING_FOR_PREDECESSOR":
            outcome = (
                "CANCELLED"
                if state == "TERMINAL_CANCELLED"
                else "FAILED"
                if state == "TERMINAL_FAILED"
                else "INTERRUPTED_AMBIGUOUS"
                if state == "INTERRUPTED_REVIEW"
                else "WAITING_FOR_PROGRESSION_EVALUATION"
            )
        elif disposition == "ELIGIBLE_PENDING_HANDOFF":
            outcome = "ELIGIBLE_NOT_CREATED"
        elif disposition == "INELIGIBLE":
            outcome = "INELIGIBLE"
        elif disposition == "TERMINAL_FAILED":
            outcome = "FAILED"
        else:
            window = connection.execute(
                """SELECT window_state FROM printer_memory_factory_campaign_windows
                   WHERE window_id=? AND token_slot_id=? AND cycle_id=?
                     AND run_id=? AND campaign_id=?""",
                (
                    token["successor_window_4h_id"],
                    token["token_slot_id"],
                    cycle_id,
                    campaign_run_id,
                    campaign_id,
                ),
            ).fetchone()
            if window is None:
                outcome = "INTERRUPTED_AMBIGUOUS"
            else:
                execution_rows = connection.execute(
                    """SELECT s.step_status,j.status,j.locked_at,j.lock_owner,
                              w.work_state
                       FROM printer_memory_factory_run_steps AS s
                       LEFT JOIN printer_scheduler_jobs AS j
                         ON j.id=s.scheduler_job_id
                       LEFT JOIN printer_memory_factory_campaign_scheduler_work AS w
                         ON w.scheduler_job_id=s.scheduler_job_id
                        AND w.campaign_id=? AND w.run_id=? AND w.cycle_id=?
                        AND w.token_slot_id=? AND w.window_id=?
                       WHERE s.run_id=? AND s.token_id=? AND s.pair_id=?
                         AND s.step_kind LIKE 'LONG_CONTINUATION_%'
                       ORDER BY s.id""",
                    (
                        campaign_id,
                        campaign_run_id,
                        cycle_id,
                        token["token_slot_id"],
                        token["successor_window_4h_id"],
                        factory_run_id,
                        int(token["token_row_id"]),
                        int(token["pair_row_id"]),
                    ),
                ).fetchall()
                window_state = str(window[0])
                scheduler_states = {str(row[1] or "MISSING") for row in execution_rows}
                step_states = {str(row[0]) for row in execution_rows}
                work_states = {str(row[4] or "MISSING") for row in execution_rows}
                claimed_or_running = any(
                    str(row[0]) == "RUNNING"
                    or str(row[1] or "") == "RUNNING"
                    or str(row[4] or "") == "RUNNING"
                    or row[2] is not None
                    or row[3] is not None
                    for row in execution_rows
                )
                if not execution_rows or "MISSING" in scheduler_states or "MISSING" in work_states:
                    outcome = "INTERRUPTED_AMBIGUOUS"
                elif (
                    window_state == "CANCELLED"
                    or "CANCELLED" in scheduler_states
                    or "CANCELLED" in work_states
                ):
                    outcome = "CANCELLED"
                elif (
                    "FAILED" in scheduler_states
                    or "FAILED" in step_states
                    or "FAILED" in work_states
                ):
                    outcome = "FAILED"
                elif claimed_or_running or window_state in {
                    "COLLECTING", "CLOSE_PENDING", "AUDITING"
                }:
                    outcome = (
                        "RUNNING" if ownership_active else "INTERRUPTED_AMBIGUOUS"
                    )
                elif window_state == "PLANNED" and (
                    "PENDING" in scheduler_states
                    or "PENDING" in step_states
                    or "PENDING" in work_states
                ):
                    outcome = "CREATED_PENDING"
                elif window_state in {
                    "CLEAN_PROMOTED",
                    "DIRTY",
                    "NO_PROMOTION",
                    "ALREADY_EXISTS_IDEMPOTENT",
                }:
                    outcome = "SUCCEEDED"
                else:
                    outcome = "INTERRUPTED_AMBIGUOUS"
        per_token.append(
            {
                "token_slot_id": str(token["token_slot_id"]),
                "disposition": disposition,
                "outcome": outcome,
                "reasons": list(token["disposition_reasons"]),
                "first_terminal_cause": token["first_terminal_cause"],
                "predecessor_window_1h_id": token["predecessor_window_1h_id"],
                "successor_window_4h_id": token["successor_window_4h_id"],
            }
        )
    interrupted = (
        state == "INTERRUPTED_REVIEW"
        or (
            state in {
                "WAITING_FOR_PREDECESSORS",
                "EVALUATING",
            }
            and not ownership_active
        )
    )
    if interrupted:
        aggregate_state = "INTERRUPTED_AMBIGUOUS"
        requires_review = True
        for item in per_token:
            if item["outcome"] == "WAITING_FOR_PROGRESSION_EVALUATION":
                item["outcome"] = "INTERRUPTED_AMBIGUOUS"
    else:
        aggregate_state = state
        requires_review = False
    complete = bool(
        state == "HANDOFF_COMMITTED"
        and all(
            item["outcome"] in {"SUCCEEDED", "FAILED", "CANCELLED", "INELIGIBLE"}
            for item in per_token
        )
    )
    reasons = [] if complete else [f"STANDARD_4H_PROGRESSION_{aggregate_state}"]
    return {
        "enabled": True,
        "complete": complete,
        "aggregate_state": aggregate_state,
        "requires_review": requires_review,
        "reasons": reasons,
        "progression_attempt_id": aggregate["progression_attempt_id"],
        "first_terminal_cause": aggregate["first_terminal_cause"],
        "fault_details": aggregate["fault_details"],
        "authority_evidence": aggregate["authority_evidence"],
        "per_token": per_token,
    }


def terminalize_stopped_standard_4h_progression(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
    cycle_id: str,
    stop_cause: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Record stopped ownership only when progression is durably non-terminal."""
    aggregate = load_standard_4h_progression_aggregate(
        connection,
        campaign_id=campaign_id,
        campaign_run_id=campaign_run_id,
        cycle_id=cycle_id,
    )
    if aggregate is None:
        return {"persisted": False, "reason": "PROGRESSION_ATTEMPT_MISSING"}
    if str(aggregate["attempt_state"]) not in {
        "WAITING_FOR_PREDECESSORS",
        "EVALUATING",
        "ELIGIBILITY_COMPLETE",
    }:
        if (
            str(aggregate["attempt_state"])
            in {"TERMINAL_FAILED", "TERMINAL_CANCELLED", "INTERRUPTED_REVIEW"}
            and aggregate["first_terminal_cause"] is not None
            and str(stop_cause) != str(aggregate["first_terminal_cause"])
        ):
            faults = append_progression_secondary_fault(
                connection,
                progression_attempt_id=str(aggregate["progression_attempt_id"]),
                cause=str(stop_cause),
                stage="FACTORY_TERMINAL_RECONCILIATION",
                now=now,
            )
            return {
                "persisted": True,
                "reason": "SECONDARY_STOP_FACT_APPENDED",
                "attempt_state": str(aggregate["attempt_state"]),
                "fault_details": faults,
            }
        return {
            "persisted": False,
            "reason": "PROGRESSION_ALREADY_TERMINAL",
            "attempt_state": str(aggregate["attempt_state"]),
        }
    cause = str(stop_cause or "PROGRESSION_OWNERSHIP_STOPPED")
    upper_cause = cause.upper()
    terminal_state = (
        "INTERRUPTED_REVIEW"
        if cause in {
            "COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
            "SAFE_STOP_OPERATOR_INTERRUPTED",
            "SAFE_STOP_TOTAL_DURATION_EXCEEDED",
            "SAFE_STOP_AMBIGUOUS_PARTIAL_STEP",
            "SAFE_STOP_RUNNING_JOB_REMAINS",
        }
        else "TERMINAL_CANCELLED"
        if "CANCEL" in upper_cause or "EXTERNAL_STOP" in upper_cause
        else "TERMINAL_FAILED"
    )
    return persist_progression_primary_fault(
        connection,
        progression_attempt_id=str(aggregate["progression_attempt_id"]),
        cause=cause,
        state=terminal_state,
        stage="FACTORY_TERMINAL_OWNERSHIP",
        safe_message=cause,
        now=now,
    )


__all__ = [
    "ATTEMPT_STATES",
    "POLICY_VERSION",
    "StandardFourHourProgressionError",
    "TERMINALLY_NON_ELIGIBLE",
    "TOKEN_DISPOSITIONS",
    "append_progression_secondary_fault",
    "commit_standard_4h_progression_handoff",
    "create_standard_4h_progression_aggregate",
    "derive_standard_4h_progression_status",
    "evaluate_standard_4h_progression",
    "load_standard_4h_progression_aggregate",
    "persist_progression_primary_fault",
    "progression_attempt_id_for",
    "terminalize_stopped_standard_4h_progression",
]

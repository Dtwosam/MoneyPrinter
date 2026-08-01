"""Transactional campaign ownership graph persistence for V2-9.7D.6B.1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from typing import Any, Mapping, Sequence

from printer_v1.operator_cli.campaign_identity_state import (
    ALLOWED_CAMPAIGN_TRANSITIONS,
)


class CampaignOwnershipError(ValueError):
    """Raised when ownership or state evidence fails closed."""


@dataclass(frozen=True)
class StateTransitionResult:
    identity: str
    previous_state: str
    current_state: str
    first_terminal_cause: str | None
    terminal_at: str | None
    changed: bool


_RUN_TRANSITIONS = {
    state: set(targets)
    for state, targets in ALLOWED_CAMPAIGN_TRANSITIONS.items()
}
_CYCLE_SEQUENCE = (
    "PLANNED", "DISCOVERING", "SELECTING", "TRACKING", "CLOSING",
    "AUDITING", "ROTATING",
)
_CYCLE_TRANSITIONS = {
    state: ({_CYCLE_SEQUENCE[index + 1]} if index + 1 < len(_CYCLE_SEQUENCE) else set())
    for index, state in enumerate(_CYCLE_SEQUENCE)
}
_TOKEN_TRANSITIONS = {
    "SELECTED": {"WINDOW_15M_ACTIVE"},
    "WINDOW_15M_ACTIVE": {"WINDOW_15M_CLOSED"},
    "WINDOW_15M_CLOSED": {"WINDOW_1H_CONTINUING"},
    "WINDOW_1H_CONTINUING": {"WINDOW_1H_CLOSED"},
    "WINDOW_1H_CLOSED": {"WINDOW_4H_CONTINUING"},
    "WINDOW_4H_CONTINUING": {"WINDOW_4H_CLOSED"},
    "WINDOW_4H_CLOSED": set(),
}
_WINDOW_TRANSITIONS = {
    "PLANNED": {"COLLECTING"},
    "COLLECTING": {"CLOSE_PENDING"},
    "CLOSE_PENDING": {"AUDITING"},
    "AUDITING": set(),
}
_WORK_TRANSITIONS = {
    "PENDING": {"RUNNING", "COOLDOWN"},
    "RUNNING": {"COOLDOWN"},
    "COOLDOWN": {"PENDING", "RUNNING"},
}

_STATE_TABLES = {
    "campaign": (
        "printer_memory_factory_campaigns", "campaign_id", "campaign_state",
        _RUN_TRANSITIONS,
        {"TERMINAL_COMPLETED", "TERMINAL_STOPPED", "TERMINAL_BLOCKED", "TERMINAL_FAILED"},
    ),
    "run": (
        "printer_memory_factory_campaign_runs", "run_id", "run_state",
        _RUN_TRANSITIONS,
        {"TERMINAL_COMPLETED", "TERMINAL_STOPPED", "TERMINAL_BLOCKED", "TERMINAL_FAILED"},
    ),
    "cycle": (
        "printer_memory_factory_campaign_cycles", "cycle_id", "cycle_state",
        _CYCLE_TRANSITIONS,
        {"TERMINAL_COMPLETED", "TERMINAL_STOPPED", "TERMINAL_BLOCKED", "TERMINAL_FAILED"},
    ),
    "token_slot": (
        "printer_memory_factory_campaign_token_slots", "token_slot_id", "token_state",
        _TOKEN_TRANSITIONS, {"COOLDOWN", "ARCHIVED", "MANUAL_REVIEW", "FAILED"},
    ),
    "window": (
        "printer_memory_factory_campaign_windows", "window_id", "window_state",
        _WINDOW_TRANSITIONS,
        {"CLEAN_PROMOTED", "DIRTY", "BLOCKED", "NO_PROMOTION", "ALREADY_EXISTS_IDEMPOTENT", "CANCELLED"},
    ),
    "scheduler_work": (
        "printer_memory_factory_campaign_scheduler_work", "scheduler_work_id", "work_state",
        _WORK_TRANSITIONS, {"SUCCEEDED", "FAILED", "SKIPPED", "CANCELLED"},
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _required(value: object, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise CampaignOwnershipError(f"{label} is required")
    return text


def _write(connection: sqlite3.Connection, sql: str, values: Sequence[object]) -> None:
    try:
        connection.execute(sql, tuple(values))
    except sqlite3.Error as exc:
        raise CampaignOwnershipError(str(exc)) from exc


def create_campaign_run(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    run_ordinal: int,
    authoritative_run_id: str | None = None,
    proof_supervision_id: int | None = None,
    now: str | None = None,
) -> None:
    timestamp = now or _utc_now()
    with connection:
        _write(
            connection,
            """INSERT INTO printer_memory_factory_campaign_runs(
                run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,
                proof_supervision_id,created_at,updated_at
            ) VALUES (?,?,?,'DRAFT',?,?,?,?)""",
            (_required(run_id, "run_id"), _required(campaign_id, "campaign_id"),
             run_ordinal, authoritative_run_id, proof_supervision_id, timestamp, timestamp),
        )


def bind_authoritative_run_id(
    connection: sqlite3.Connection,
    *,
    campaign_run_id: str,
    factory_run_id: str,
    now: str | None = None,
) -> StateTransitionResult:
    """One-shot bind of campaign run → factory run (NULL → value only)."""
    timestamp = now or _utc_now()
    campaign_run = _required(campaign_run_id, "campaign_run_id")
    factory_run = _required(factory_run_id, "factory_run_id")
    try:
        with connection:
            row = connection.execute(
                """SELECT authoritative_run_id, run_state
                   FROM printer_memory_factory_campaign_runs WHERE run_id=?""",
                (campaign_run,),
            ).fetchone()
            if row is None:
                raise CampaignOwnershipError(
                    f"unknown campaign run identity: {campaign_run}"
                )
            current = row[0]
            if current is not None:
                if str(current) == factory_run:
                    return StateTransitionResult(
                        campaign_run, str(row[1]), str(row[1]), None, None, False
                    )
                raise CampaignOwnershipError(
                    "authoritative_run_id already bound to a different factory run"
                )
            factory = connection.execute(
                "SELECT run_id FROM printer_memory_factory_runs WHERE run_id=?",
                (factory_run,),
            ).fetchone()
            if factory is None:
                raise CampaignOwnershipError(
                    f"factory run missing for authoritative bind: {factory_run}"
                )
            cursor = connection.execute(
                """UPDATE printer_memory_factory_campaign_runs
                   SET authoritative_run_id=?, updated_at=?
                   WHERE run_id=? AND authoritative_run_id IS NULL""",
                (factory_run, timestamp, campaign_run),
            )
            if cursor.rowcount != 1:
                raise CampaignOwnershipError(
                    "authoritative_run_id bind failed compare-and-update"
                )
            return StateTransitionResult(
                campaign_run, str(row[1]), str(row[1]), None, None, True
            )
    except sqlite3.Error as exc:
        raise CampaignOwnershipError(str(exc)) from exc


def bind_window_memory_row_id(
    connection: sqlite3.Connection,
    *,
    window_id: str,
    memory_window_row_id: int,
    now: str | None = None,
) -> bool:
    """One-shot bind of campaign window → printer_memory_windows row."""
    timestamp = now or _utc_now()
    identity = _required(window_id, "window_id")
    row_id = int(memory_window_row_id)
    try:
        with connection:
            row = connection.execute(
                """SELECT memory_window_row_id, window_kind, token_row_id, pair_row_id
                   FROM printer_memory_factory_campaign_windows WHERE window_id=?""",
                (identity,),
            ).fetchone()
            if row is None:
                raise CampaignOwnershipError(f"unknown campaign window: {identity}")
            current = row[0]
            if current is not None:
                if int(current) == row_id:
                    return False
                raise CampaignOwnershipError(
                    "memory_window_row_id already bound to a different row"
                )
            memory = connection.execute(
                """SELECT id, token_id, pair_id, window_kind
                   FROM printer_memory_windows WHERE id=?""",
                (row_id,),
            ).fetchone()
            if memory is None:
                raise CampaignOwnershipError(
                    f"memory window missing for bind: {row_id}"
                )
            if (
                int(memory[1]) != int(row[2])
                or int(memory[2]) != int(row[3])
                or str(memory[3]) != str(row[1])
            ):
                raise CampaignOwnershipError(
                    "memory window identity mismatch on bind"
                )
            cursor = connection.execute(
                """UPDATE printer_memory_factory_campaign_windows
                   SET memory_window_row_id=?, updated_at=?
                   WHERE window_id=? AND memory_window_row_id IS NULL""",
                (row_id, timestamp, identity),
            )
            if cursor.rowcount != 1:
                raise CampaignOwnershipError(
                    "memory_window_row_id bind failed compare-and-update"
                )
            return True
    except sqlite3.Error as exc:
        raise CampaignOwnershipError(str(exc)) from exc


def create_cycle_with_two_slots(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    cycle_ordinal: int,
    slots: Sequence[Mapping[str, Any]],
    now: str | None = None,
) -> None:
    if len(slots) != 2:
        raise CampaignOwnershipError("a cycle requires exactly two token slots")
    if {int(slot.get("slot_ordinal", 0)) for slot in slots} != {1, 2}:
        raise CampaignOwnershipError("token slot ordinals must be exactly 1 and 2")
    timestamp = now or _utc_now()
    try:
        with connection:
            connection.execute(
                """INSERT INTO printer_memory_factory_campaign_cycles(
                    cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,
                    created_at,updated_at
                ) VALUES (?,?,?,?,'PLANNED',?,?)""",
                (cycle_id, campaign_id, run_id, cycle_ordinal, timestamp, timestamp),
            )
            for slot in slots:
                connection.execute(
                    """INSERT INTO printer_memory_factory_campaign_token_slots(
                        token_slot_id,campaign_id,run_id,cycle_id,slot_ordinal,
                        token_identity,token_row_id,mint_identity,pair_identity,
                        pair_row_id,lifecycle_identity,tracking_queue_id,
                        replacement_predecessor_slot_id,token_state,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'SELECTED',?,?)""",
                    (
                        _required(slot.get("token_slot_id"), "token_slot_id"),
                        campaign_id, run_id, cycle_id, int(slot["slot_ordinal"]),
                        _required(slot.get("token_identity"), "token_identity"),
                        int(slot["token_row_id"]),
                        _required(slot.get("mint_identity"), "mint_identity"),
                        _required(slot.get("pair_identity"), "pair_identity"),
                        int(slot["pair_row_id"]),
                        _required(slot.get("lifecycle_identity"), "lifecycle_identity"),
                        slot.get("tracking_queue_id"),
                        slot.get("replacement_predecessor_slot_id"), timestamp, timestamp,
                    ),
                )
    except (KeyError, TypeError, ValueError, sqlite3.Error) as exc:
        raise CampaignOwnershipError(str(exc)) from exc


def persist_window(
    connection: sqlite3.Connection,
    *,
    window_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    token_slot_id: str,
    token_row_id: int,
    pair_row_id: int,
    window_kind: str,
    root_15m_lifecycle_identity: str,
    checkpoint_cutoff: str,
    predecessor_window_id: str | None = None,
    containing_main_window_id: str | None = None,
    memory_window_row_id: int | None = None,
    now: str | None = None,
) -> None:
    timestamp = now or _utc_now()
    support_only = int(window_kind == "WINDOW_5M_MICRO_EVENT")
    with connection:
        _write(
            connection,
            """INSERT INTO printer_memory_factory_campaign_windows(
                window_id,campaign_id,run_id,cycle_id,token_slot_id,token_row_id,
                pair_row_id,window_kind,window_state,root_15m_lifecycle_identity,
                predecessor_window_id,containing_main_window_id,memory_window_row_id,
                checkpoint_cutoff,support_only,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,'PLANNED',?,?,?,?,?,?,?,?)""",
            (window_id,campaign_id,run_id,cycle_id,token_slot_id,token_row_id,pair_row_id,
             window_kind,root_15m_lifecycle_identity,predecessor_window_id,
             containing_main_window_id,memory_window_row_id,checkpoint_cutoff,
             support_only,timestamp,timestamp),
        )


def persist_scheduler_work(
    connection: sqlite3.Connection,
    *,
    scheduler_work_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    token_slot_id: str,
    window_id: str,
    work_intent: str,
    deadline_at: str,
    scheduler_job_id: int | None = None,
    source_request_id: int | None = None,
    source_response_id: int | None = None,
    source_failure_id: int | None = None,
    now: str | None = None,
) -> None:
    """Legacy window-bound insert (V1_WINDOW_BOUND contract).

    This predates the V2-9.8B stage-scoped amendment and remains only for
    historical/window-bound rows. Repaired operational Scheduler ownership must
    go through :func:`project_campaign_scheduler_work`, the single scope-aware
    authority, not through this helper.
    """
    timestamp = now or _utc_now()
    with connection:
        _write(
            connection,
            """INSERT INTO printer_memory_factory_campaign_scheduler_work(
                scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,
                window_id,work_intent,deadline_at,work_state,scheduler_job_id,
                source_request_id,source_response_id,source_failure_id,
                ownership_contract_version,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,'PENDING',?,?,?,?,'V1_WINDOW_BOUND',?,?)""",
            (scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,window_id,
             work_intent,deadline_at,scheduler_job_id,source_request_id,
             source_response_id,source_failure_id,timestamp,timestamp),
        )


def canonical_object_payload(payload: Mapping[str, Any]) -> tuple[str, str]:
    try:
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise CampaignOwnershipError(f"object payload is not canonical JSON: {exc}") from exc
    return encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def persist_immutable_object(
    connection: sqlite3.Connection,
    *,
    object_id: str,
    object_kind: str,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    cycle_id: str,
    token_slot_id: str,
    window_id: str,
    payload: Mapping[str, Any],
    scheduler_work_id: str | None = None,
    authoritative_episode_id: int | None = None,
    safety_composite_id: int | None = None,
    lifecycle_event_id: int | None = None,
    now: str | None = None,
) -> str:
    object_json, object_hash = canonical_object_payload(payload)
    with connection:
        _write(
            connection,
            """INSERT INTO printer_memory_factory_campaign_objects(
                object_id,object_kind,campaign_id,configuration_id,run_id,cycle_id,
                token_slot_id,window_id,scheduler_work_id,object_hash,object_json,
                authoritative_episode_id,safety_composite_id,lifecycle_event_id,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (object_id,object_kind,campaign_id,configuration_id,run_id,cycle_id,
             token_slot_id,window_id,scheduler_work_id,object_hash,object_json,
             authoritative_episode_id,safety_composite_id,lifecycle_event_id,
             now or _utc_now()),
        )
    return object_hash


def link_report_object(
    connection: sqlite3.Connection,
    *,
    report_id: str,
    campaign_id: str,
    configuration_id: str,
    object_id: str,
    now: str | None = None,
) -> None:
    with connection:
        _write(
            connection,
            """INSERT INTO printer_memory_factory_campaign_report_objects(
                report_id,campaign_id,configuration_id,object_id,created_at
            ) VALUES (?,?,?,?,?)""",
            (report_id,campaign_id,configuration_id,object_id,now or _utc_now()),
        )


def transition_state(
    connection: sqlite3.Connection,
    *,
    record_kind: str,
    identity: str,
    expected_state: str,
    new_state: str,
    terminal_cause: str | None = None,
    now: str | None = None,
) -> StateTransitionResult:
    if record_kind not in _STATE_TABLES:
        raise CampaignOwnershipError(f"unsupported state owner: {record_kind}")
    table, identity_column, state_column, transitions, terminal_states = _STATE_TABLES[record_kind]
    timestamp = now or _utc_now()
    try:
        with connection:
            row = connection.execute(
                f"SELECT {state_column},first_terminal_cause,terminal_at FROM {table} WHERE {identity_column}=?",
                (identity,),
            ).fetchone()
            if row is None:
                raise CampaignOwnershipError(f"unknown {record_kind} identity: {identity}")
            current, first_cause, terminal_at = map(lambda value: value, row)
            if current in terminal_states:
                if current == new_state and first_cause == terminal_cause:
                    return StateTransitionResult(identity,current,current,first_cause,terminal_at,False)
                raise CampaignOwnershipError("terminal state and first cause are immutable")
            if current != expected_state:
                raise CampaignOwnershipError(
                    f"compare-and-update mismatch: expected {expected_state}, found {current}"
                )
            allowed = set(transitions.get(current, set()))
            if record_kind not in {"campaign", "run"}:
                allowed |= terminal_states
            if new_state not in allowed:
                raise CampaignOwnershipError(f"invalid {record_kind} transition: {current} -> {new_state}")
            if new_state in terminal_states:
                cause = _required(terminal_cause, "terminal_cause")
                terminal_value = timestamp
            else:
                if terminal_cause is not None:
                    raise CampaignOwnershipError("non-terminal transition cannot set a terminal cause")
                cause = None
                terminal_value = None
            cursor = connection.execute(
                f"""UPDATE {table} SET {state_column}=?,first_terminal_cause=?,
                    terminal_at=?,updated_at=?
                    WHERE {identity_column}=? AND {state_column}=?""",
                (new_state,cause,terminal_value,timestamp,identity,current),
            )
            if cursor.rowcount != 1:
                raise CampaignOwnershipError("state changed during compare-and-update")
            return StateTransitionResult(
                identity,current,new_state,cause,terminal_value,True
            )
    except sqlite3.Error as exc:
        raise CampaignOwnershipError(str(exc)) from exc


# ---------------------------------------------------------------------------
# V2-9.8B campaign Scheduler ownership: one scope-aware projection authority.
# ---------------------------------------------------------------------------

WORK_SCOPES = (
    "DISCOVERY_SELECTION",
    "FIRST_15M_HANDOFF",
    "WINDOW_LIFECYCLE",
    "TERMINAL_CLEANUP",
)
_TERMINAL_WORK_STATES = frozenset(
    {"SUCCEEDED", "FAILED", "SKIPPED", "CANCELLED"}
)
_NON_TERMINAL_WORK_STATES = frozenset({"PENDING", "RUNNING", "COOLDOWN"})

# Every column that forms the exact, immutable projection identity. Idempotency
# is allowed only when all of these match; any difference is competing ownership.
_PROJECTION_IDENTITY_COLUMNS = (
    "campaign_id", "run_id", "cycle_id", "token_slot_id", "window_id",
    "work_intent", "deadline_at", "scheduler_job_id", "source_request_id",
    "source_response_id", "source_failure_id", "ownership_contract_version",
    "stage_id", "work_scope", "target_category", "target_identity",
    "factory_run_id",
)


@dataclass(frozen=True)
class SchedulerWorkProjectionResult:
    """Outcome of projecting an existing Central Scheduler job into ownership."""

    scheduler_work_id: str
    campaign_id: str
    work_scope: str
    stage_id: str
    scheduler_job_id: int
    work_state: str
    created: bool


def _opt_int(value: object, label: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise CampaignOwnershipError(f"{label} must be an integer") from exc


def _scheduler_job_belongs_to_campaign(
    connection: sqlite3.Connection, *, campaign_id: str, scheduler_job_id: int
) -> bool:
    """True only when a durable campaign linkage already owns the job."""
    row = connection.execute(
        """SELECT 1 WHERE
            EXISTS (
                SELECT 1 FROM printer_memory_factory_campaign_scheduler_work
                WHERE scheduler_job_id = ? AND campaign_id = ?
            )
         OR EXISTS (
                SELECT 1 FROM printer_discovery_selected_item_links
                WHERE first_window_15m_scheduler_job_id = ? AND campaign_id = ?
            )
         OR EXISTS (
                SELECT 1 FROM printer_memory_factory_run_steps AS s
                JOIN printer_memory_factory_campaign_runs AS r
                  ON r.authoritative_run_id = s.run_id
                WHERE s.scheduler_job_id = ? AND r.campaign_id = ?
            )
        """,
        (scheduler_job_id, campaign_id, scheduler_job_id, campaign_id,
         scheduler_job_id, campaign_id),
    ).fetchone()
    return row is not None


def _validate_discovery_selection_ownership(
    connection: sqlite3.Connection, *, campaign_id: str, run_id: str,
    cycle_id: str, target_category: str, target_identity: str,
) -> None:
    if target_category == "DISCOVERY_BATCH":
        found = connection.execute(
            """SELECT 1 FROM printer_discovery_batches
               WHERE discovery_batch_id = ? AND campaign_id = ?
                 AND run_id = ? AND cycle_id = ?""",
            (target_identity, campaign_id, run_id, cycle_id),
        ).fetchone()
        if found is None:
            raise CampaignOwnershipError(
                "no exact discovery ownership source for DISCOVERY_SELECTION"
            )
    elif target_category == "SELECTION_BATCH":
        found = connection.execute(
            """SELECT 1 FROM printer_discovery_selection_links
               WHERE selection_batch_id = ? AND campaign_id = ?
                 AND run_id = ? AND cycle_id = ?""",
            (target_identity, campaign_id, run_id, cycle_id),
        ).fetchone()
        if found is None:
            raise CampaignOwnershipError(
                "no exact selection ownership source for DISCOVERY_SELECTION"
            )
    else:
        raise CampaignOwnershipError(
            "DISCOVERY_SELECTION target_category must be "
            "DISCOVERY_BATCH or SELECTION_BATCH"
        )


def _validate_first_15m_handoff_ownership(
    connection: sqlite3.Connection, *, campaign_id: str, run_id: str,
    cycle_id: str, scheduler_job_id: int, token_slot_id: str | None,
    target_category: str, target_identity: str,
) -> None:
    row = connection.execute(
        """SELECT selection_item_id, merged_candidate_id, token_slot_id
           FROM printer_discovery_selected_item_links
           WHERE first_window_15m_scheduler_job_id = ?
             AND campaign_id = ? AND run_id = ? AND cycle_id = ?""",
        (scheduler_job_id, campaign_id, run_id, cycle_id),
    ).fetchone()
    if row is None:
        raise CampaignOwnershipError(
            "no lawful first-15m handoff owner for scheduler job"
        )
    link_item_id, link_candidate, link_slot = row[0], row[1], row[2]
    if token_slot_id is not None:
        if link_slot is None or str(link_slot) != str(token_slot_id):
            raise CampaignOwnershipError(
                "first-15m handoff token slot ownership mismatch"
            )
    if target_category == "SELECTED_ITEM":
        if str(target_identity) != str(link_item_id):
            raise CampaignOwnershipError(
                "first-15m handoff target identity mismatch"
            )
    elif target_category == "MERGED_CANDIDATE":
        if str(target_identity) != str(link_candidate):
            raise CampaignOwnershipError(
                "first-15m handoff target identity mismatch"
            )
    else:
        raise CampaignOwnershipError(
            "FIRST_15M_HANDOFF target_category must be "
            "SELECTED_ITEM or MERGED_CANDIDATE"
        )


def _validate_window_lifecycle_ownership(
    connection: sqlite3.Connection, *, campaign_id: str, run_id: str,
    cycle_id: str, token_slot_id: str, window_id: str, factory_run_id: str,
    scheduler_job_id: int,
) -> None:
    window = connection.execute(
        """SELECT 1 FROM printer_memory_factory_campaign_windows
           WHERE window_id = ? AND token_slot_id = ? AND cycle_id = ?
             AND run_id = ? AND campaign_id = ?""",
        (window_id, token_slot_id, cycle_id, run_id, campaign_id),
    ).fetchone()
    if window is None:
        raise CampaignOwnershipError(
            "no exact campaign window/slot for WINDOW_LIFECYCLE"
        )
    step = connection.execute(
        """SELECT 1 FROM printer_memory_factory_run_steps
           WHERE run_id = ? AND scheduler_job_id = ?""",
        (factory_run_id, scheduler_job_id),
    ).fetchone()
    if step is None:
        raise CampaignOwnershipError(
            "no exact factory run-step linkage for WINDOW_LIFECYCLE"
        )


def _validate_terminal_cleanup_ownership(
    connection: sqlite3.Connection, *, campaign_id: str, scheduler_job_id: int,
    captured_campaign_job_ids: object,
) -> None:
    if not captured_campaign_job_ids:
        raise CampaignOwnershipError(
            "TERMINAL_CLEANUP requires a captured campaign-scoped job set"
        )
    try:
        captured = {int(job) for job in captured_campaign_job_ids}
    except (TypeError, ValueError) as exc:
        raise CampaignOwnershipError(
            "captured campaign-scoped job set must contain integers"
        ) from exc
    if int(scheduler_job_id) not in captured:
        raise CampaignOwnershipError(
            "cleanup scheduler job is not in the captured campaign-scoped job set"
        )
    for job in captured:
        if not _scheduler_job_belongs_to_campaign(
            connection, campaign_id=campaign_id, scheduler_job_id=job
        ):
            raise CampaignOwnershipError(
                f"captured cleanup job {job} is not campaign-scoped"
            )


def project_campaign_scheduler_work(
    connection: sqlite3.Connection,
    *,
    scheduler_work_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    work_scope: str,
    stage_id: str,
    work_intent: str,
    deadline_at: str,
    scheduler_job_id: int,
    target_category: str,
    target_identity: str,
    token_slot_id: str | None = None,
    window_id: str | None = None,
    factory_run_id: str | None = None,
    source_request_id: int | None = None,
    source_response_id: int | None = None,
    source_failure_id: int | None = None,
    work_state: str = "PENDING",
    first_terminal_cause: str | None = None,
    terminal_at: str | None = None,
    captured_campaign_job_ids: object = None,
    now: str | None = None,
) -> SchedulerWorkProjectionResult:
    """Project one existing Central Scheduler job into campaign ownership.

    This is the single, scope-aware Scheduler-ownership authority. It never
    creates a Scheduler job; it references an existing
    ``printer_scheduler_jobs`` row and records a ``V2_STAGE_SCOPED`` ownership
    row after validating the scope against its real durable ownership source. It
    is idempotent only for the exact same complete identity, rejects competing
    campaign/scope/stage/target/linkage ownership, and never fabricates a
    window, slot, or factory run-step.
    """
    scheduler_work_id = _required(scheduler_work_id, "scheduler_work_id")
    campaign_id = _required(campaign_id, "campaign_id")
    run_id = _required(run_id, "run_id")
    cycle_id = _required(cycle_id, "cycle_id")
    stage_id = _required(stage_id, "stage_id")
    work_intent = _required(work_intent, "work_intent")
    deadline_at = _required(deadline_at, "deadline_at")
    target_category = _required(target_category, "target_category")
    target_identity = _required(target_identity, "target_identity")
    if work_scope not in WORK_SCOPES:
        raise CampaignOwnershipError(f"unsupported work scope: {work_scope}")
    if scheduler_job_id is None:
        raise CampaignOwnershipError("scheduler_job_id is required for projection")
    scheduler_job_id = int(scheduler_job_id)
    token_slot_id = token_slot_id if token_slot_id else None
    window_id = window_id if window_id else None
    factory_run_id = factory_run_id if factory_run_id else None
    source_request_id = _opt_int(source_request_id, "source_request_id")
    source_response_id = _opt_int(source_response_id, "source_response_id")
    source_failure_id = _opt_int(source_failure_id, "source_failure_id")

    if work_state not in _NON_TERMINAL_WORK_STATES | _TERMINAL_WORK_STATES:
        raise CampaignOwnershipError(f"invalid work_state: {work_state}")
    if work_state in _TERMINAL_WORK_STATES:
        first_terminal_cause = _required(first_terminal_cause, "first_terminal_cause")
        terminal_at = _required(terminal_at, "terminal_at")
    else:
        if first_terminal_cause is not None or terminal_at is not None:
            raise CampaignOwnershipError(
                "non-terminal work cannot carry a terminal cause or terminal_at"
            )

    # Scope-conditional nullability (fail closed before any durable lookup).
    if work_scope == "DISCOVERY_SELECTION":
        if token_slot_id is not None or window_id is not None or factory_run_id is not None:
            raise CampaignOwnershipError(
                "DISCOVERY_SELECTION cannot carry a slot, window, or factory run"
            )
    elif work_scope == "FIRST_15M_HANDOFF":
        if window_id is not None or factory_run_id is not None:
            raise CampaignOwnershipError(
                "FIRST_15M_HANDOFF cannot carry a window or factory run"
            )
    elif work_scope == "WINDOW_LIFECYCLE":
        if token_slot_id is None or window_id is None or factory_run_id is None:
            raise CampaignOwnershipError(
                "WINDOW_LIFECYCLE requires exact factory run, slot, and window"
            )
    elif work_scope == "TERMINAL_CLEANUP":
        if window_id is not None or factory_run_id is not None:
            raise CampaignOwnershipError(
                "TERMINAL_CLEANUP cannot carry a window or factory run"
            )

    desired = {
        "campaign_id": campaign_id,
        "run_id": run_id,
        "cycle_id": cycle_id,
        "token_slot_id": token_slot_id,
        "window_id": window_id,
        "work_intent": work_intent,
        "deadline_at": deadline_at,
        "scheduler_job_id": scheduler_job_id,
        "source_request_id": source_request_id,
        "source_response_id": source_response_id,
        "source_failure_id": source_failure_id,
        "ownership_contract_version": "V2_STAGE_SCOPED",
        "stage_id": stage_id,
        "work_scope": work_scope,
        "target_category": target_category,
        "target_identity": target_identity,
        "factory_run_id": factory_run_id,
    }
    timestamp = now or _utc_now()

    try:
        with connection:
            existing = connection.execute(
                f"""SELECT work_state,
                    {", ".join(_PROJECTION_IDENTITY_COLUMNS)}
                    FROM printer_memory_factory_campaign_scheduler_work
                    WHERE scheduler_work_id = ?""",
                (scheduler_work_id,),
            ).fetchone()
            if existing is not None:
                existing_state = existing[0]
                existing_identity = {
                    column: existing[index + 1]
                    for index, column in enumerate(_PROJECTION_IDENTITY_COLUMNS)
                }
                if existing_identity["ownership_contract_version"] != "V2_STAGE_SCOPED":
                    raise CampaignOwnershipError(
                        "existing scheduler work is not a V2 stage-scoped row"
                    )
                if existing_identity != desired:
                    raise CampaignOwnershipError(
                        "competing campaign/scope/stage/target/linkage ownership "
                        "for scheduler_work_id"
                    )
                # Exact-identity repeat: idempotent; preserve actual work state.
                return SchedulerWorkProjectionResult(
                    scheduler_work_id=scheduler_work_id,
                    campaign_id=campaign_id,
                    work_scope=work_scope,
                    stage_id=stage_id,
                    scheduler_job_id=scheduler_job_id,
                    work_state=str(existing_state),
                    created=False,
                )

            # One canonical Scheduler job to one campaign ownership stage.
            conflict = connection.execute(
                """SELECT 1 FROM printer_memory_factory_campaign_scheduler_work
                   WHERE scheduler_job_id = ? AND scheduler_work_id <> ?""",
                (scheduler_job_id, scheduler_work_id),
            ).fetchone()
            if conflict is not None:
                raise CampaignOwnershipError(
                    "scheduler job already owned by another campaign work row"
                )

            # Reference an existing Central Scheduler job; never create one.
            if connection.execute(
                "SELECT 1 FROM printer_scheduler_jobs WHERE id = ?",
                (scheduler_job_id,),
            ).fetchone() is None:
                raise CampaignOwnershipError(
                    "scheduler job does not exist; projection cannot create one"
                )

            # Validate the scope against its real durable ownership source.
            if work_scope == "DISCOVERY_SELECTION":
                _validate_discovery_selection_ownership(
                    connection, campaign_id=campaign_id, run_id=run_id,
                    cycle_id=cycle_id, target_category=target_category,
                    target_identity=target_identity,
                )
            elif work_scope == "FIRST_15M_HANDOFF":
                _validate_first_15m_handoff_ownership(
                    connection, campaign_id=campaign_id, run_id=run_id,
                    cycle_id=cycle_id, scheduler_job_id=scheduler_job_id,
                    token_slot_id=token_slot_id, target_category=target_category,
                    target_identity=target_identity,
                )
            elif work_scope == "WINDOW_LIFECYCLE":
                _validate_window_lifecycle_ownership(
                    connection, campaign_id=campaign_id, run_id=run_id,
                    cycle_id=cycle_id, token_slot_id=token_slot_id,
                    window_id=window_id, factory_run_id=factory_run_id,
                    scheduler_job_id=scheduler_job_id,
                )
            elif work_scope == "TERMINAL_CLEANUP":
                _validate_terminal_cleanup_ownership(
                    connection, campaign_id=campaign_id,
                    scheduler_job_id=scheduler_job_id,
                    captured_campaign_job_ids=captured_campaign_job_ids,
                )

            connection.execute(
                """INSERT INTO printer_memory_factory_campaign_scheduler_work(
                    scheduler_work_id, campaign_id, run_id, cycle_id, token_slot_id,
                    window_id, work_intent, deadline_at, work_state, scheduler_job_id,
                    source_request_id, source_response_id, source_failure_id,
                    ownership_contract_version, stage_id, work_scope, target_category,
                    target_identity, factory_run_id, first_terminal_cause, terminal_at,
                    created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'V2_STAGE_SCOPED',?,?,?,?,?,?,?,?,?)""",
                (
                    scheduler_work_id, campaign_id, run_id, cycle_id, token_slot_id,
                    window_id, work_intent, deadline_at, work_state, scheduler_job_id,
                    source_request_id, source_response_id, source_failure_id,
                    stage_id, work_scope, target_category, target_identity,
                    factory_run_id, first_terminal_cause, terminal_at,
                    timestamp, timestamp,
                ),
            )
    except sqlite3.Error as exc:
        raise CampaignOwnershipError(str(exc)) from exc

    return SchedulerWorkProjectionResult(
        scheduler_work_id=scheduler_work_id,
        campaign_id=campaign_id,
        work_scope=work_scope,
        stage_id=stage_id,
        scheduler_job_id=scheduler_job_id,
        work_state=work_state,
        created=True,
    )


def project_campaign_scheduler_job(
    connection: sqlite3.Connection,
    *,
    scheduler_work_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    token_slot_id: str,
    window_id: str,
    factory_run_id: str,
    work_intent: str,
    deadline_at: str,
    scheduler_job_id: int,
    stage_id: str,
    target_category: str = "CAMPAIGN_WINDOW",
    target_identity: str | None = None,
    source_request_id: int | None = None,
    source_response_id: int | None = None,
    source_failure_id: int | None = None,
    work_state: str = "PENDING",
    first_terminal_cause: str | None = None,
    terminal_at: str | None = None,
    now: str | None = None,
) -> SchedulerWorkProjectionResult:
    """Compatibility wrapper for WINDOW_LIFECYCLE ownership.

    Retained only so lifecycle callers keep working; it delegates to the single
    scope-aware owner :func:`project_campaign_scheduler_work` and introduces no
    second ownership authority.
    """
    return project_campaign_scheduler_work(
        connection,
        scheduler_work_id=scheduler_work_id,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        work_scope="WINDOW_LIFECYCLE",
        stage_id=stage_id,
        work_intent=work_intent,
        deadline_at=deadline_at,
        scheduler_job_id=scheduler_job_id,
        target_category=target_category,
        target_identity=target_identity if target_identity else window_id,
        token_slot_id=token_slot_id,
        window_id=window_id,
        factory_run_id=factory_run_id,
        source_request_id=source_request_id,
        source_response_id=source_response_id,
        source_failure_id=source_failure_id,
        work_state=work_state,
        first_terminal_cause=first_terminal_cause,
        terminal_at=terminal_at,
        now=now,
    )

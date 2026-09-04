"""Deterministic terminal campaign report over stored authoritative facts."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Mapping

from printer_v1.operator_cli.campaign_active_work import (
    campaign_active_work_report,
)
from printer_v1.operator_cli.campaign_authority_adapters import (
    load_authoritative_checkpoint_safety,
    load_authoritative_promotion_outcome,
)
from printer_v1.operator_cli.campaign_persistence import (
    persist_terminal_report_with_objects,
)
from printer_v1.operator_cli.git_provenance import (
    GitProvenanceError,
    validate_launch_provenance,
)


OBJECT_KINDS = (
    "CONTINUATION_4A",
    "SUPPORT_EVIDENCE_4B",
    "TRAJECTORY_5A",
    "CHECKPOINT_5A",
    "MANIPULATION_CONTEXT_5B",
    "OPPORTUNITY_SEGMENT_5C",
)
LOCKED_CAPABILITY_TABLES = (
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
)
_ACTIVE_WORK = ("PENDING", "RUNNING", "COOLDOWN")


class FinalCampaignReportError(ValueError):
    """Raised when the stored campaign record is incomplete or inconsistent."""


@dataclass(frozen=True)
class AssembledCampaignReport:
    report: dict[str, Any]
    canonical_json: str
    canonical_bytes: bytes
    report_hash: str
    object_ids: tuple[str, ...]


@contextmanager
def _read_only(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    path = Path(db_path).resolve()
    if not path.is_file():
        raise FinalCampaignReportError(f"database missing: {path}")
    connection = sqlite3.connect(
        f"file:{path.as_posix()}?mode=ro", uri=True, timeout=0.0
    )
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        yield connection
        if connection.total_changes:
            raise FinalCampaignReportError("report assembly created database writes")
    finally:
        connection.close()


def _json_object(value: object, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value))
    except (TypeError, json.JSONDecodeError) as exc:
        raise FinalCampaignReportError(f"{label} is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise FinalCampaignReportError(f"{label} must be a JSON object")
    return parsed


def _canonical(value: Mapping[str, Any]) -> tuple[str, bytes, str]:
    try:
        encoded = json.dumps(
            dict(value), sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise FinalCampaignReportError("terminal report is not canonical JSON") from exc
    payload = encoded.encode("utf-8")
    return encoded, payload, hashlib.sha256(payload).hexdigest()


def _root(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
) -> dict[str, Any]:
    rows = connection.execute(
        """SELECT c.campaign_id,c.campaign_state,c.first_terminal_cause,
                  c.terminal_at,c.policy_version,c.db_mode,c.db_target_identity,
                  cfg.configuration_id,cfg.configuration_hash,
                  cfg.configuration_json,cfg.launch_provenance_json,
                  r.run_id,r.run_state,r.first_terminal_cause AS run_first_cause,
                  r.terminal_at AS run_terminal_at,r.authoritative_run_id,
                  authority.run_status AS authoritative_run_status,
                  authority.stop_reason AS authoritative_stop_reason,
                  authority.final_report_json AS authoritative_report_json
           FROM printer_memory_factory_campaigns AS c
           JOIN printer_memory_factory_campaign_configurations AS cfg
             ON cfg.campaign_id=c.campaign_id AND cfg.configuration_id=?
           JOIN printer_memory_factory_campaign_runs AS r
             ON r.campaign_id=c.campaign_id AND r.run_id=?
           LEFT JOIN printer_memory_factory_runs AS authority
             ON authority.run_id=r.authoritative_run_id
           WHERE c.campaign_id=?""",
        (configuration_id, run_id, campaign_id),
    ).fetchall()
    if len(rows) != 1:
        raise FinalCampaignReportError(
            "campaign/configuration/run ownership mismatch"
        )
    root = dict(rows[0])
    if not str(root["campaign_state"]).startswith("TERMINAL_") or not str(
        root["run_state"]
    ).startswith("TERMINAL_"):
        raise FinalCampaignReportError("campaign and run must both be terminal")
    causes = {root["first_terminal_cause"], root["run_first_cause"]}
    if None in causes or len(causes) != 1:
        raise FinalCampaignReportError("campaign/run first terminal cause mismatch")
    insufficient_pool = (
        root["first_terminal_cause"] == "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL"
    )
    if insufficient_pool and not root["authoritative_run_id"]:
        # Discovery-only insufficient-pool campaigns never open an
        # authoritative memory-factory run. Preserve the real discovery
        # accounting while synthesizing only the missing factory-run envelope.
        zero = {table: 0 for table in LOCKED_CAPABILITY_TABLES}
        for table in LOCKED_CAPABILITY_TABLES:
            zero[table] = int(
                connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            )
        (
            discovery_request_ids,
            _,
            _,
            discovery_scheduler_job_ids,
        ) = _discovery_owned_source_usage(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
        )
        configuration = _json_object(
            root["configuration_json"], "campaign configuration"
        )
        ceilings = configuration.get("ceilings")
        if not isinstance(ceilings, Mapping):
            raise FinalCampaignReportError(
                "campaign source/scheduler ceilings are missing"
            )
        source_ceiling = ceilings.get("source_calls")
        scheduler_ceiling = ceilings.get("scheduler_work")
        if (
            isinstance(source_ceiling, bool)
            or not isinstance(source_ceiling, int)
            or source_ceiling < 0
        ):
            raise FinalCampaignReportError(
                "campaign source-call ceiling is missing or invalid"
            )
        if (
            isinstance(scheduler_ceiling, bool)
            or not isinstance(scheduler_ceiling, int)
            or scheduler_ceiling < 0
        ):
            raise FinalCampaignReportError(
                "campaign Scheduler ceiling is missing or invalid"
            )

        root["authoritative_run_id"] = f"synthetic-insufficient-pool:{campaign_id}:{run_id}"
        root["authoritative_run_status"] = "FAILED"
        root["authoritative_stop_reason"] = "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL"
        root["authoritative_report_json"] = json.dumps(
            {
                "counts_before": zero,
                "counts_after": zero,
                "forbidden_deltas": {table: 0 for table in LOCKED_CAPABILITY_TABLES},
                "run_budgets": {
                    "governed_requests_run": len(discovery_request_ids),
                    "governed_requests_run_ceiling": source_ceiling,
                    "scheduler_rows_total": len(discovery_scheduler_job_ids),
                    "scheduler_rows_ceiling": scheduler_ceiling,
                    "automatic_retries": 0,
                },
                "selected_token_count": 0,
                "first_terminal_cause": "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    elif not root["authoritative_run_id"] or not root["authoritative_report_json"]:
        raise FinalCampaignReportError("authoritative run terminal report is missing")
    return root


def _stored_objects(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    allow_empty_objects: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    records: list[dict[str, Any]] = []
    grouped = {kind: [] for kind in OBJECT_KINDS}
    rows = connection.execute(
        """SELECT * FROM printer_memory_factory_campaign_objects
           WHERE campaign_id=? AND configuration_id=? AND run_id=?
           ORDER BY object_kind,cycle_id,token_slot_id,window_id,object_id""",
        (campaign_id, configuration_id, run_id),
    ).fetchall()
    for row in rows:
        record = dict(row)
        kind = str(record["object_kind"])
        if kind not in grouped:
            raise FinalCampaignReportError("unsupported campaign object kind")
        payload = _json_object(record["object_json"], f"{kind} object")
        canonical, _, digest = _canonical(payload)
        if canonical != record["object_json"] or digest != record["object_hash"]:
            raise FinalCampaignReportError("campaign object canonical hash mismatch")
        item = {
            "object_id": record["object_id"],
            "object_hash": record["object_hash"],
            "cycle_id": record["cycle_id"],
            "token_slot_id": record["token_slot_id"],
            "window_id": record["window_id"],
            "scheduler_work_id": record["scheduler_work_id"],
            "authoritative_episode_id": record["authoritative_episode_id"],
            "safety_composite_id": record["safety_composite_id"],
            "lifecycle_event_id": record["lifecycle_event_id"],
            "payload": payload,
        }
        records.append({"object_kind": kind, **item})
        grouped[kind].append(item)
    missing = [kind for kind, items in grouped.items() if not items]
    if missing and not allow_empty_objects:
        raise FinalCampaignReportError(f"required campaign objects missing: {missing}")
    return records, grouped


def _lifecycle(
    connection: sqlite3.Connection,
    *,
    authoritative_run_id: str,
    slots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for slot in slots:
        key = (
            f"{authoritative_run_id}:{int(slot['token_row_id'])}:"
            f"{int(slot['pair_row_id'])}"
        )
        events = connection.execute(
            """SELECT * FROM printer_token_lifecycle_events
               WHERE token_id=? AND pair_id=?
                 AND json_extract(event_payload_json,
                     '$.factory_reconciliation_key')=?
               ORDER BY id""",
            (slot["token_row_id"], slot["pair_row_id"], key),
        ).fetchall()
        if len(events) != 1:
            raise FinalCampaignReportError(
                "exactly one B.3 lifecycle reconciliation event is required"
            )
        event = dict(events[0])
        queue = connection.execute(
            "SELECT queue_status FROM printer_tracking_queue WHERE id=?",
            (slot["tracking_queue_id"],),
        ).fetchone()
        if queue is None:
            raise FinalCampaignReportError("B.3 tracking queue is missing")
        active_jobs = int(connection.execute(
            """SELECT COUNT(*) FROM printer_scheduler_jobs
               WHERE target_table='printer_tracking_queue' AND target_id=?
                 AND (status IN ('PENDING','RUNNING','COOLDOWN')
                      OR locked_at IS NOT NULL OR lock_owner IS NOT NULL)""",
            (slot["tracking_queue_id"],),
        ).fetchone()[0])
        active_work = int(connection.execute(
            """SELECT COUNT(*)
               FROM printer_memory_factory_campaign_scheduler_work AS work
               LEFT JOIN printer_scheduler_jobs AS job
                 ON job.id=work.scheduler_job_id
               WHERE work.campaign_id=? AND work.run_id=?
                 AND work.cycle_id=? AND work.token_slot_id=?
                 AND (work.work_state IN ('PENDING','RUNNING','COOLDOWN')
                      OR job.status IN ('PENDING','RUNNING','COOLDOWN')
                      OR job.locked_at IS NOT NULL OR job.lock_owner IS NOT NULL)""",
            (
                slot["campaign_id"], slot["run_id"], slot["cycle_id"],
                slot["token_slot_id"],
            ),
        ).fetchone()[0])
        if active_jobs or active_work:
            raise FinalCampaignReportError("B.3 cleanup is incomplete")
        results.append({
            "campaign_id": slot["campaign_id"],
            "run_id": slot["run_id"],
            "cycle_id": slot["cycle_id"],
            "token_slot_id": slot["token_slot_id"],
            "token_row_id": int(slot["token_row_id"]),
            "pair_row_id": int(slot["pair_row_id"]),
            "tracking_queue_id": int(slot["tracking_queue_id"]),
            "terminal_disposition": queue["queue_status"],
            "lifecycle_event_id": int(event["id"]),
            "lifecycle_event": event["lifecycle_event"],
            "event_payload": _json_object(
                event["event_payload_json"], "B.3 lifecycle payload"
            ),
            "active_associated_work_after": active_jobs + active_work,
        })
    return results


def _attempt_owned_source_usage(
    connection: sqlite3.Connection,
    *,
    authoritative_run_id: str,
) -> tuple[set[int], set[int], set[int], set[int]]:
    """Return durable pre-admission source identities owned by one factory run."""
    request_ids = {
        int(row[0])
        for row in connection.execute(
            """SELECT l.source_request_id
               FROM printer_pre_admission_discovery_attempts AS a
               JOIN printer_pre_admission_discovery_attempt_source_links AS l
                 ON l.attempt_id=a.attempt_id
               WHERE a.authoritative_factory_run_id=?
               UNION
               SELECT e.source_request_id
               FROM printer_pre_admission_discovery_attempts AS a
               JOIN printer_pre_admission_attempt_evidence AS e
                 ON e.attempt_id=a.attempt_id
               WHERE a.authoritative_factory_run_id=?
                 AND e.source_request_id IS NOT NULL""",
            (authoritative_run_id, authoritative_run_id),
        ).fetchall()
    }
    response_ids = {
        int(row[0])
        for row in connection.execute(
            """SELECT DISTINCT e.source_response_id
               FROM printer_pre_admission_discovery_attempts AS a
               JOIN printer_pre_admission_attempt_evidence AS e
                 ON e.attempt_id=a.attempt_id
               WHERE a.authoritative_factory_run_id=?
                 AND e.source_response_id IS NOT NULL""",
            (authoritative_run_id,),
        ).fetchall()
    }
    failure_ids = {
        int(row[0])
        for row in connection.execute(
            """SELECT DISTINCT e.source_failure_id
               FROM printer_pre_admission_discovery_attempts AS a
               JOIN printer_pre_admission_attempt_evidence AS e
                 ON e.attempt_id=a.attempt_id
               WHERE a.authoritative_factory_run_id=?
                 AND e.source_failure_id IS NOT NULL""",
            (authoritative_run_id,),
        ).fetchall()
    }
    scheduler_job_ids = {
        int(row[0])
        for row in connection.execute(
            """SELECT DISTINCT scheduler_job_id
               FROM printer_pre_admission_discovery_attempts
               WHERE authoritative_factory_run_id=?
                 AND scheduler_job_id IS NOT NULL""",
            (authoritative_run_id,),
        ).fetchall()
    }
    return request_ids, response_ids, failure_ids, scheduler_job_ids


def _discovery_owned_source_usage(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
) -> tuple[set[int], set[int], set[int], set[int]]:
    """Return exact ordinary-discovery source and Scheduler identities."""
    request_ids = {
        int(row[0])
        for row in connection.execute(
            """SELECT DISTINCT l.source_request_id
               FROM printer_discovery_work AS work
               JOIN printer_discovery_work_source_links AS l
                 ON l.discovery_work_id=work.discovery_work_id
               WHERE work.campaign_id=? AND work.run_id=?
                 AND l.source_request_id IS NOT NULL""",
            (campaign_id, run_id),
        ).fetchall()
    }
    response_ids = {
        int(row[0])
        for row in connection.execute(
            """SELECT DISTINCT l.source_response_id
               FROM printer_discovery_work AS work
               JOIN printer_discovery_work_source_links AS l
                 ON l.discovery_work_id=work.discovery_work_id
               WHERE work.campaign_id=? AND work.run_id=?
                 AND l.source_response_id IS NOT NULL""",
            (campaign_id, run_id),
        ).fetchall()
    }
    failure_ids = {
        int(row[0])
        for row in connection.execute(
            """SELECT DISTINCT l.source_failure_id
               FROM printer_discovery_work AS work
               JOIN printer_discovery_work_source_links AS l
                 ON l.discovery_work_id=work.discovery_work_id
               WHERE work.campaign_id=? AND work.run_id=?
                 AND l.source_failure_id IS NOT NULL""",
            (campaign_id, run_id),
        ).fetchall()
    }
    scheduler_job_ids = {
        int(row[0])
        for row in connection.execute(
            """SELECT DISTINCT scheduler_job_id
               FROM printer_discovery_work
               WHERE campaign_id=? AND run_id=?
                 AND scheduler_job_id IS NOT NULL""",
            (campaign_id, run_id),
        ).fetchall()
    }
    return request_ids, response_ids, failure_ids, scheduler_job_ids


def _locked_capabilities(
    connection: sqlite3.Connection, authoritative_report: Mapping[str, Any],
) -> dict[str, Any]:
    before = authoritative_report.get("counts_before")
    after = authoritative_report.get("counts_after")
    deltas = authoritative_report.get("forbidden_deltas")
    if not all(isinstance(value, Mapping) for value in (before, after, deltas)):
        raise FinalCampaignReportError(
            "authoritative locked-capability baseline/final evidence is missing"
        )
    baseline: dict[str, int] = {}
    final: dict[str, int] = {}
    exact_deltas: dict[str, int] = {}
    current: dict[str, int] = {}
    for table in LOCKED_CAPABILITY_TABLES:
        if table not in before or table not in after or table not in deltas:
            raise FinalCampaignReportError(
                "authoritative locked-capability table evidence is incomplete"
            )
        baseline[table] = int(before[table])
        final[table] = int(after[table])
        exact_deltas[table] = int(deltas[table])
        current[table] = int(connection.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0])
        if exact_deltas[table] != final[table] - baseline[table]:
            raise FinalCampaignReportError("locked-capability delta mismatch")
        if current[table] != final[table]:
            raise FinalCampaignReportError(
                "locked-capability count changed after authoritative report"
            )
    return {
        "baseline_counts": baseline,
        "final_counts": final,
        "deltas": exact_deltas,
        "current_counts": current,
        "all_deltas_zero": all(value == 0 for value in exact_deltas.values()),
    }


def assemble_final_campaign_report(
    db_path: str | Path,
    *,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
) -> AssembledCampaignReport:
    """Assemble canonical report bytes using stored facts only."""
    with _read_only(db_path) as connection:
        root = _root(
            connection, campaign_id=campaign_id,
            configuration_id=configuration_id, run_id=run_id,
        )
        configuration = _json_object(
            root["configuration_json"], "campaign configuration"
        )
        provenance_raw = _json_object(
            root["launch_provenance_json"], "stored launch Git provenance"
        )
        try:
            provenance = validate_launch_provenance(provenance_raw)
        except GitProvenanceError as exc:
            raise FinalCampaignReportError(
                "stored launch Git provenance is invalid"
            ) from exc
        authoritative_report = _json_object(
            root["authoritative_report_json"], "authoritative run report"
        )
        cycles = [dict(row) for row in connection.execute(
            """SELECT * FROM printer_memory_factory_campaign_cycles
               WHERE campaign_id=? AND run_id=? ORDER BY cycle_ordinal,cycle_id""",
            (campaign_id, run_id),
        ).fetchall()]
        if not cycles or any(
            not str(cycle["cycle_state"]).startswith("TERMINAL_")
            for cycle in cycles
        ):
            raise FinalCampaignReportError("all campaign cycles must be terminal")
        slots = [dict(row) for row in connection.execute(
            """SELECT * FROM printer_memory_factory_campaign_token_slots
               WHERE campaign_id=? AND run_id=?
               ORDER BY cycle_id,slot_ordinal,token_slot_id""",
            (campaign_id, run_id),
        ).fetchall()]
        cycle_ids = {cycle["cycle_id"] for cycle in cycles}
        insufficient_pool = (
            root["first_terminal_cause"] == "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL"
        )
        for cycle_id in cycle_ids:
            slot_count = sum(slot["cycle_id"] == cycle_id for slot in slots)
            if insufficient_pool:
                # Two-or-none: insufficient pool leaves zero activated slots.
                if slot_count != 0:
                    raise FinalCampaignReportError(
                        "insufficient-pool campaigns must activate zero token slots"
                    )
            elif slot_count != 2:
                raise FinalCampaignReportError(
                    "every campaign cycle requires two tokens"
                )
        windows = [dict(row) for row in connection.execute(
            """SELECT * FROM printer_memory_factory_campaign_windows
               WHERE campaign_id=? AND run_id=?
               ORDER BY cycle_id,token_slot_id,checkpoint_cutoff,window_id""",
            (campaign_id, run_id),
        ).fetchall()]
        work = [dict(row) for row in connection.execute(
            """SELECT * FROM printer_memory_factory_campaign_scheduler_work
               WHERE campaign_id=? AND run_id=?
               ORDER BY cycle_id,token_slot_id,deadline_at,scheduler_work_id""",
            (campaign_id, run_id),
        ).fetchall()]
        records, objects = _stored_objects(
            connection, campaign_id=campaign_id,
            configuration_id=configuration_id, run_id=run_id,
            allow_empty_objects=insufficient_pool,
        )
        supervision_rows = connection.execute(
            """SELECT * FROM printer_memory_factory_campaign_supervision
               WHERE campaign_id=? AND configuration_id=? AND run_id=?""",
            (campaign_id, configuration_id, run_id),
        ).fetchall()
        if len(supervision_rows) != 1:
            raise FinalCampaignReportError("exact campaign supervision is missing")
        supervision = dict(supervision_rows[0])
        if (
            supervision["supervision_state"] != "TERMINAL"
            or supervision["cleanup_completed_at"] is None
            or supervision["lease_released_at"] is None
            or supervision["first_terminal_cause"] != root["first_terminal_cause"]
        ):
            raise FinalCampaignReportError(
                "terminal supervision or first-cause evidence is incomplete"
            )
        lifecycle = _lifecycle(
            connection,
            authoritative_run_id=str(root["authoritative_run_id"]),
            slots=slots,
        )
        locked = _locked_capabilities(connection, authoritative_report)
        active_work = campaign_active_work_report(
            connection,
            factory_run_id=str(root["authoritative_run_id"]),
            campaign_id=campaign_id,
            run_id=run_id,
        )
        if not active_work["clean_terminal"]:
            raise FinalCampaignReportError(
                "campaign active-work cleanup is incomplete"
            )
        (
            attempt_source_request_ids,
            attempt_source_response_ids,
            attempt_source_failure_ids,
            attempt_scheduler_job_ids,
        ) = _attempt_owned_source_usage(
            connection,
            authoritative_run_id=str(root["authoritative_run_id"]),
        )
        (
            discovery_source_request_ids,
            discovery_source_response_ids,
            discovery_source_failure_ids,
            discovery_scheduler_job_ids,
        ) = _discovery_owned_source_usage(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
        )

    main_windows = [
        window for window in windows
        if window["window_kind"] in {"WINDOW_15M", "WINDOW_1H", "WINDOW_4H"}
    ]
    promotion_outcomes = [
        load_authoritative_promotion_outcome(
            db_path,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=str(window["cycle_id"]),
            token_slot_id=str(window["token_slot_id"]),
            window_id=str(window["window_id"]),
        )
        for window in main_windows
    ]
    safety_contexts = [
        load_authoritative_checkpoint_safety(
            db_path,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=str(item["cycle_id"]),
            token_slot_id=str(item["token_slot_id"]),
            window_id=str(item["window_id"]),
            checkpoint_object_id=str(item["object_id"]),
        )
        for item in objects["CHECKPOINT_5A"]
    ]
    backup_reference = configuration.get("backup_preflight_references")
    if backup_reference is None:
        backup_reference = {
            "state": "UNKNOWN",
            "evidence_gap": "stored_backup_preflight_reference_missing",
        }
    usage = {
        "authoritative_run_budgets": authoritative_report.get("run_budgets"),
        "source_request_ids": sorted(
            {
                int(item["source_request_id"]) for item in work
                if item["source_request_id"] is not None
            }
            | attempt_source_request_ids
            | discovery_source_request_ids
        ),
        "source_response_ids": sorted(
            {
                int(item["source_response_id"]) for item in work
                if item["source_response_id"] is not None
            }
            | attempt_source_response_ids
            | discovery_source_response_ids
        ),
        "source_failure_ids": sorted(
            {
                int(item["source_failure_id"]) for item in work
                if item["source_failure_id"] is not None
            }
            | attempt_source_failure_ids
            | discovery_source_failure_ids
        ),
        "scheduler_job_ids": sorted(
            {
                int(item["scheduler_job_id"]) for item in work
                if item["scheduler_job_id"] is not None
            }
            | attempt_scheduler_job_ids
            | discovery_scheduler_job_ids
        ),
        "campaign_scheduler_work_total": len(work),
        "automatic_retries": 0,
    }
    if not isinstance(usage["authoritative_run_budgets"], Mapping):
        raise FinalCampaignReportError("authoritative source/scheduler ceilings missing")
    budgets = usage["authoritative_run_budgets"]
    reported_requests = budgets.get("governed_requests_run")
    if (
        isinstance(reported_requests, bool)
        or not isinstance(reported_requests, int)
        or reported_requests < 0
    ):
        raise FinalCampaignReportError(
            "authoritative source request total is missing or invalid"
        )
    if reported_requests != len(usage["source_request_ids"]):
        raise FinalCampaignReportError(
            "source request identity/total mismatch"
        )

    reported_scheduler_rows = budgets.get("scheduler_rows_total")
    if (
        isinstance(reported_scheduler_rows, bool)
        or not isinstance(reported_scheduler_rows, int)
        or reported_scheduler_rows < 0
    ):
        raise FinalCampaignReportError(
            "authoritative Scheduler total is missing or invalid"
        )
    if reported_scheduler_rows != len(usage["scheduler_job_ids"]):
        raise FinalCampaignReportError(
            "Scheduler identity/total mismatch"
        )

    opportunity_layers = [
        {
            "object_id": item["object_id"],
            "full_window_outcome": item["payload"].get("full_window_outcome"),
            "internal_trade_opportunity_outcome": item["payload"].get(
                "internal_trade_opportunity_outcome"
            ),
            "evidence_gaps": item["payload"].get("evidence_gaps", []),
        }
        for item in objects["OPPORTUNITY_SEGMENT_5C"]
    ]
    visible_unknowns_and_gaps = [
        {
            "object_kind": record["object_kind"],
            "object_id": record["object_id"],
            "unknowns": record["payload"].get("unknowns", []),
            "evidence_gaps": record["payload"].get("evidence_gaps", []),
            "gaps": record["payload"].get("gaps", []),
        }
        for record in records
        if any(
            key in record["payload"] for key in ("unknowns", "evidence_gaps", "gaps")
        )
    ]
    report = {
        "report_schema": "V2_9_7D_6B_6_FINAL_CAMPAIGN_REPORT",
        "identity": {
            "campaign_id": campaign_id,
            "configuration_id": configuration_id,
            "configuration_hash": root["configuration_hash"],
            "run_id": run_id,
            "authoritative_run_id": root["authoritative_run_id"],
            "cycles": cycles,
            "two_token_slots": slots,
            "windows": windows,
        },
        "terminal": {
            "campaign_state": root["campaign_state"],
            "run_state": root["run_state"],
            "first_terminal_cause": root["first_terminal_cause"],
            "campaign_terminal_at": root["terminal_at"],
            "run_terminal_at": root["run_terminal_at"],
            "authoritative_run_status": root["authoritative_run_status"],
            "authoritative_stop_reason": root["authoritative_stop_reason"],
        },
        "launch_git_provenance": provenance,
        "promotion_outcomes_b1": promotion_outcomes,
        "safety_contexts_b2": safety_contexts,
        "lifecycle_b3": lifecycle,
        "operational_supervision": supervision,
        "continuation_4a": objects["CONTINUATION_4A"],
        "support_only_5m_4b": objects["SUPPORT_EVIDENCE_4B"],
        "trajectory_5a": objects["TRAJECTORY_5A"],
        "checkpoints_5a": objects["CHECKPOINT_5A"],
        "manipulation_context_5b": objects["MANIPULATION_CONTEXT_5B"],
        "opportunity_segments_5c": objects["OPPORTUNITY_SEGMENT_5C"],
        "opportunity_outcome_layers": opportunity_layers,
        "visible_unknowns_and_evidence_gaps": visible_unknowns_and_gaps,
        "source_scheduler_ceiling_usage": usage,
        "backup_preflight_references": backup_reference,
        "locked_capabilities": locked,
        "report_object_ids": sorted(record["object_id"] for record in records),
        "hindsight_reconstruction": False,
        "git_provenance_recaptured": False,
    }
    canonical_json, canonical_bytes, report_hash = _canonical(report)
    return AssembledCampaignReport(
        report=report,
        canonical_json=canonical_json,
        canonical_bytes=canonical_bytes,
        report_hash=report_hash,
        object_ids=tuple(report["report_object_ids"]),
    )


def persist_final_campaign_report(
    db_path: str | Path,
    *,
    report_id: str,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
) -> dict[str, Any]:
    """Assemble and atomically persist one immutable final campaign report."""
    assembled = assemble_final_campaign_report(
        db_path,
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        run_id=run_id,
    )
    persisted = persist_terminal_report_with_objects(
        db_path,
        report_id=report_id,
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        report=assembled.report,
        object_ids=assembled.object_ids,
    )
    if persisted["report_hash"] != assembled.report_hash:
        raise FinalCampaignReportError("persisted terminal report hash mismatch")
    return {
        "report_id": report_id,
        "campaign_id": campaign_id,
        "configuration_id": configuration_id,
        "run_id": run_id,
        "report_hash": assembled.report_hash,
        "canonical_json": assembled.canonical_json,
        "canonical_bytes": assembled.canonical_bytes,
        "object_ids": assembled.object_ids,
        "idempotent_replay": bool(persisted["idempotent_replay"]),
    }

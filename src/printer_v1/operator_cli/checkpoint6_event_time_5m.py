"""Checkpoint 6 event-time adapter for support-only WINDOW_5M_MICRO_EVENT.

This module integrates the already-adopted pure support policy with the existing
Scheduler-owned 15m snapshot stream.  It performs no source request and creates
no Scheduler job.  A successful snapshot job may freeze an event-time support
verdict in its own run-step result; after the real parent WINDOW_15M exists the
frozen verdict may be materialized by the existing Lane X8 persistence owner.

Final WINDOW_15M outcome labels are deliberately absent from this module.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.micro_event.classifier import classify_micro_event_move
from printer_v1.micro_event.parser import build_micro_event_payload_from_token_snapshots
from printer_v1.scheduler.support_only_5m_capture import (
    ExpectedSupportCaptureIdentity,
    GovernedSourceProvenance,
    SupportCaptureBudgets,
    SupportCaptureRequest,
    SupportCaptureVerdict,
    SupportTriggerFamily,
    TriggeringSnapshot,
    evaluate_support_only_5m_capture,
)


_FIRST_FIVE_MINUTES_SECONDS = 300.0
_ACTIVE_CAMPAIGN_WINDOW_STATES = frozenset({"PLANNED", "COLLECTING", "CLOSE_PENDING"})

_MOVE_TO_TRIGGER: dict[str, SupportTriggerFamily] = {
    "MOVE_FAST_UP": SupportTriggerFamily.FAST_COORDINATED_PUMP,
    "MOVE_SPIKE_AND_HOLD": SupportTriggerFamily.FAST_COORDINATED_PUMP,
    "MOVE_FAST_DOWN": SupportTriggerFamily.FAST_DUMP_OR_COLLAPSE,
    "MOVE_WICK_ONLY": SupportTriggerFamily.WICK_OR_LATE_BUY_TRAP,
    "MOVE_SPIKE_AND_FADE": SupportTriggerFamily.WICK_OR_LATE_BUY_TRAP,
    "MOVE_ROUND_TRIP": SupportTriggerFamily.FAST_BREAKDOWN_OR_RECLAIM,
}


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("event-time support requires timezone-aware snapshots")
    return parsed.astimezone(timezone.utc)


def _load_config(connection: sqlite3.Connection, factory_run_id: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT config_json FROM printer_memory_factory_runs WHERE run_id=?",
        (factory_run_id,),
    ).fetchone()
    if row is None:
        return {}
    try:
        value = json.loads(str(row[0]) or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _blocked(reason: str, **extra: Any) -> dict[str, Any]:
    return {
        "verdict": SupportCaptureVerdict.BLOCK_SUPPORT_CAPTURE.value,
        "reasons": [reason],
        "capture": None,
        "support_only": True,
        "future_main_window_outcome_used": False,
        **extra,
    }


def _no_capture(reason: str, **extra: Any) -> dict[str, Any]:
    return {
        "verdict": SupportCaptureVerdict.VALID_NO_CAPTURE.value,
        "reasons": [reason],
        "capture": None,
        "support_only": True,
        "future_main_window_outcome_used": False,
        **extra,
    }


def _serialize_capture(
    *,
    capture: Any,
    factory_run_id: str,
    scheduler_job_id: int,
    source_provenance: list[dict[str, Any]],
    pair_address: str,
) -> dict[str, Any]:
    raw = asdict(capture)
    raw["trigger_family"] = str(capture.trigger_family)
    raw["trigger_time"] = capture.trigger_time.isoformat()
    raw["evidence_cutoff"] = capture.evidence_cutoff.isoformat()
    raw["campaign_run_id"] = raw.pop("run_id")
    raw["factory_run_id"] = factory_run_id
    raw["pair_address"] = pair_address
    raw["scheduler_job_id"] = int(scheduler_job_id)
    raw["triggering_snapshot_ids"] = [
        int(item.snapshot_id) for item in capture.triggering_snapshots
    ]
    raw["source_provenance"] = source_provenance
    raw["verdict"] = SupportCaptureVerdict.CAPTURE_SUPPORT.value
    raw["future_main_window_outcome_used"] = False
    raw["support_only"] = True
    raw["main_outcome_memory"] = False
    raw["continuation_authority"] = False
    raw["retrieval_authority"] = False
    raw["decision_authority"] = False
    raw["financial_authority"] = False
    # TriggeringSnapshot dataclass payloads are superseded by the compact exact
    # identity/provenance lists above; do not persist datetime-bearing nested
    # dataclasses twice.
    raw.pop("triggering_snapshots", None)
    return raw


def evaluate_event_time_5m_support_for_snapshot(
    connection: sqlite3.Connection,
    *,
    factory_run_id: str,
    step: sqlite3.Row | Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate one just-completed initial-15m snapshot at its own evidence cutoff.

    The result is safe to store inside the triggering run-step ``result_json``.
    A blocked/no-capture result is support-local and must not fail the main 15m
    lifecycle.
    """
    if not result.get("ok") or result.get("snapshot_id") is None:
        return _blocked("snapshot_not_successful")

    config = _load_config(connection, factory_run_id)
    campaign_id = str(config.get("campaign_id") or "")
    campaign_run_id = str(config.get("campaign_run_id") or "")
    cycle_id = str(config.get("cycle_id") or "")
    if not campaign_id or not campaign_run_id or not cycle_id:
        return _no_capture("campaign_identity_not_available")

    scheduler_job_id = int(step["scheduler_job_id"])
    owners = connection.execute(
        """
        SELECT scheduler_work_id, token_slot_id, window_id
        FROM printer_memory_factory_campaign_scheduler_work
        WHERE scheduler_job_id=? AND campaign_id=? AND run_id=? AND cycle_id=?
          AND ownership_contract_version='V2_STAGE_SCOPED'
          AND work_scope='WINDOW_LIFECYCLE'
        ORDER BY scheduler_work_id
        """,
        (scheduler_job_id, campaign_id, campaign_run_id, cycle_id),
    ).fetchall()
    if len(owners) != 1:
        return _blocked(f"exact_window_lifecycle_scheduler_owner_count={len(owners)}")
    owner = owners[0]
    if owner["token_slot_id"] is None or owner["window_id"] is None:
        return _blocked("window_lifecycle_scheduler_owner_identity_incomplete")

    campaign_window = connection.execute(
        """
        SELECT window_id, token_slot_id, token_row_id, pair_row_id, window_kind,
               window_state, root_15m_lifecycle_identity
        FROM printer_memory_factory_campaign_windows
        WHERE window_id=? AND campaign_id=? AND run_id=? AND cycle_id=?
        """,
        (str(owner["window_id"]), campaign_id, campaign_run_id, cycle_id),
    ).fetchone()
    if campaign_window is None:
        return _blocked("campaign_window_owner_missing")
    if (
        str(campaign_window["window_kind"]) != "WINDOW_15M"
        or str(campaign_window["window_state"]) not in _ACTIVE_CAMPAIGN_WINDOW_STATES
        or int(campaign_window["token_row_id"]) != int(step["token_id"])
        or int(campaign_window["pair_row_id"]) != int(step["pair_id"])
        or str(campaign_window["token_slot_id"]) != str(owner["token_slot_id"])
    ):
        return _blocked("campaign_window_owner_identity_mismatch")

    slot = connection.execute(
        """
        SELECT mint_identity, pair_identity, lifecycle_identity
        FROM printer_memory_factory_campaign_token_slots
        WHERE token_slot_id=? AND campaign_id=? AND run_id=? AND cycle_id=?
        """,
        (str(owner["token_slot_id"]), campaign_id, campaign_run_id, cycle_id),
    ).fetchone()
    if slot is None:
        return _blocked("campaign_token_slot_missing")
    if str(slot["mint_identity"]).lower() != str(step["token_mint"]).lower():
        return _blocked("campaign_token_slot_mint_mismatch")
    root_lifecycle = str(campaign_window["root_15m_lifecycle_identity"] or "")
    if not root_lifecycle or root_lifecycle != str(slot["lifecycle_identity"]):
        return _blocked("root_15m_lifecycle_identity_mismatch")

    prior = connection.execute(
        """
        SELECT id, scheduler_job_id, snapshot_id, source_request_id,
               source_response_id, source_failure_id, result_json
        FROM printer_memory_factory_run_steps
        WHERE run_id=? AND token_id=? AND pair_id=? AND step_kind='SNAPSHOT'
          AND step_status='SUCCEEDED' AND snapshot_id IS NOT NULL
        ORDER BY scheduled_for, id
        """,
        (factory_run_id, int(step["token_id"]), int(step["pair_id"])),
    ).fetchall()
    observations: list[dict[str, Any]] = [dict(row) for row in prior]
    observations.append(
        {
            "id": int(step["id"]),
            "scheduler_job_id": scheduler_job_id,
            "snapshot_id": int(result["snapshot_id"]),
            "source_request_id": result.get("source_request_id"),
            "source_response_id": result.get("source_response_id"),
            "source_failure_id": result.get("source_failure_id"),
        }
    )
    # Exact de-duplication protects a resumed/in-memory current step shape.
    by_snapshot: dict[int, dict[str, Any]] = {}
    for item in observations:
        by_snapshot[int(item["snapshot_id"])] = item
    observations = list(by_snapshot.values())

    rows: list[sqlite3.Row] = []
    for item in observations:
        snapshot = connection.execute(
            "SELECT * FROM printer_token_snapshots WHERE id=?",
            (int(item["snapshot_id"]),),
        ).fetchone()
        if snapshot is None:
            return _blocked("triggering_snapshot_missing")
        if (
            int(snapshot["token_id"]) != int(step["token_id"])
            or int(snapshot["pair_id"]) != int(step["pair_id"])
        ):
            return _blocked("triggering_snapshot_target_mismatch")
        item["snapshot"] = snapshot
        rows.append(snapshot)
    rows.sort(key=lambda row: (str(row["captured_at"]), int(row["id"])))
    if len(rows) < 2:
        return _no_capture("at_least_two_event_time_snapshots_not_yet_available")

    opening_at = _utc(str(rows[0]["captured_at"]))
    trigger_at = _utc(str(rows[-1]["captured_at"]))
    elapsed = (trigger_at - opening_at).total_seconds()
    if elapsed < 0 or elapsed > _FIRST_FIVE_MINUTES_SECONDS:
        return _no_capture("event_time_cutoff_outside_first_5m", elapsed_seconds=elapsed)

    payload = build_micro_event_payload_from_token_snapshots([dict(row) for row in rows])
    move = str(classify_micro_event_move(payload))
    trigger_family = _MOVE_TO_TRIGGER.get(move)
    if trigger_family is None:
        return _no_capture(
            "no_approved_event_time_trigger",
            micro_event_move=move,
            trigger_time=trigger_at.isoformat(),
        )

    evaluation_work_id = str(owner["scheduler_work_id"])
    source_provenance: list[dict[str, Any]] = []
    triggering: list[TriggeringSnapshot] = []
    observation_by_snapshot = {int(item["snapshot_id"]): item for item in observations}
    for snapshot in rows:
        item = observation_by_snapshot[int(snapshot["id"])]
        request_id = item.get("source_request_id")
        response_id = item.get("source_response_id")
        if request_id is None or response_id is None or item.get("source_failure_id") is not None:
            return _blocked("triggering_snapshot_governed_source_provenance_incomplete")
        request = connection.execute(
            "SELECT source_name FROM printer_source_requests WHERE id=?",
            (int(request_id),),
        ).fetchone()
        response = connection.execute(
            """SELECT source_status, data_quality_label
               FROM printer_source_responses WHERE id=? AND source_request_id=?""",
            (int(response_id), int(request_id)),
        ).fetchone()
        if request is None or response is None:
            return _blocked("triggering_snapshot_source_identity_not_traceable")
        source_status = str(response["source_status"])
        data_quality = str(response["data_quality_label"])
        provenance = GovernedSourceProvenance(
            source_name=str(request["source_name"]),
            source_request_id=int(request_id),
            source_response_id=int(response_id),
            scheduler_work_id=evaluation_work_id,
            source_status=source_status,
            data_quality_label=data_quality,
            governor_approved=True,
            traceable=True,
        )
        source_provenance.append(
            {
                "snapshot_id": int(snapshot["id"]),
                "source_name": str(request["source_name"]),
                "source_request_id": int(request_id),
                "source_response_id": int(response_id),
                "scheduler_work_id": evaluation_work_id,
                "source_scheduler_job_id": int(item["scheduler_job_id"]),
                "source_status": source_status,
                "data_quality_label": data_quality,
                "governor_approved": True,
                "traceable": True,
            }
        )
        triggering.append(
            TriggeringSnapshot(
                snapshot_id=int(snapshot["id"]),
                campaign_id=campaign_id,
                run_id=campaign_run_id,
                cycle_id=cycle_id,
                token_slot_id=str(owner["token_slot_id"]),
                token_id=str(step["token_id"]),
                mint_id=str(step["token_mint"]),
                pair_id=str(step["pair_id"]),
                root_15m_lifecycle_id=root_lifecycle,
                containing_main_window_id=str(owner["window_id"]),
                observed_at=_utc(str(snapshot["captured_at"])),
                freshness_within_contract=True,
                provenance=provenance,
            )
        )

    expected = ExpectedSupportCaptureIdentity(
        campaign_id=campaign_id,
        run_id=campaign_run_id,
        cycle_id=cycle_id,
        token_slot_id=str(owner["token_slot_id"]),
        token_id=str(step["token_id"]),
        mint_id=str(step["token_mint"]),
        pair_id=str(step["pair_id"]),
        root_15m_lifecycle_id=root_lifecycle,
        containing_main_window_id=str(owner["window_id"]),
        scheduler_work_id=evaluation_work_id,
    )
    request = SupportCaptureRequest(
        campaign_id=campaign_id,
        run_id=campaign_run_id,
        cycle_id=cycle_id,
        token_slot_id=expected.token_slot_id,
        token_id=expected.token_id,
        mint_id=expected.mint_id,
        pair_id=expected.pair_id,
        root_15m_lifecycle_id=expected.root_15m_lifecycle_id,
        containing_main_window_id=expected.containing_main_window_id,
        containing_main_window_kind="WINDOW_15M",
        containing_main_window_status="WINDOW_OPEN",
        scheduler_work_id=evaluation_work_id,
        expected_identity=expected,
        trigger_family=trigger_family,
        trigger_time=trigger_at,
        evidence_cutoff=trigger_at,
        triggering_snapshots=tuple(triggering),
        budgets=SupportCaptureBudgets(),
        token_state=str(step["tracking_lane"]),
        meaningful_transition_proven=True,
        ordinary_movement=False,
        future_main_window_outcome_used=False,
    )
    decision = evaluate_support_only_5m_capture(request)
    if decision.verdict is not SupportCaptureVerdict.CAPTURE_SUPPORT or decision.capture is None:
        return {
            "verdict": str(decision.verdict),
            "reasons": list(decision.reasons),
            "capture": None,
            "support_only": True,
            "future_main_window_outcome_used": False,
            "micro_event_move": move,
        }
    frozen = _serialize_capture(
        capture=decision.capture,
        factory_run_id=factory_run_id,
        scheduler_job_id=scheduler_job_id,
        source_provenance=source_provenance,
        pair_address=str(step["pair_address"]),
    )
    return {
        "verdict": SupportCaptureVerdict.CAPTURE_SUPPORT.value,
        "reasons": list(decision.reasons),
        "capture": frozen,
        "support_only": True,
        "future_main_window_outcome_used": False,
        "micro_event_move": move,
    }


def materialize_frozen_5m_support(
    connection: sqlite3.Connection,
    *,
    factory_run_id: str,
    close_step: sqlite3.Row | Mapping[str, Any],
    parent_window_id: int,
) -> dict[str, Any]:
    """Materialize the earliest frozen event-time capture for one 15m target."""
    rows = connection.execute(
        """
        SELECT result_json
        FROM printer_memory_factory_run_steps
        WHERE run_id=? AND token_id=? AND pair_id=? AND step_kind='SNAPSHOT'
          AND step_status='SUCCEEDED'
        ORDER BY scheduled_for, id
        """,
        (factory_run_id, int(close_step["token_id"]), int(close_step["pair_id"])),
    ).fetchall()
    frozen: dict[str, Any] | None = None
    for row in rows:
        try:
            step_result = json.loads(str(row["result_json"] or "{}"))
        except (TypeError, json.JSONDecodeError):
            continue
        candidate = step_result.get("support_5m_event_time")
        if not isinstance(candidate, Mapping):
            continue
        capture = candidate.get("capture")
        if (
            candidate.get("verdict") == SupportCaptureVerdict.CAPTURE_SUPPORT.value
            and isinstance(capture, Mapping)
        ):
            frozen = dict(capture)
            break
    if frozen is None:
        return {
            "captured": False,
            "verdict": SupportCaptureVerdict.VALID_NO_CAPTURE.value,
            "reason": "NO_FROZEN_EVENT_TIME_SUPPORT_TRIGGER",
            "window_5m_id": None,
            "support_only": True,
        }

    from printer_v1.operator_cli.lane_x8_5m_support_integration import (
        capture_5m_support_evidence,
    )

    snapshot_ids = [int(value) for value in frozen.get("triggering_snapshot_ids") or ()]
    if len(snapshot_ids) < 2:
        return _blocked("frozen_support_triggering_snapshots_incomplete")
    db_path = str(connection.execute("PRAGMA database_list").fetchone()[2])
    materialized = capture_5m_support_evidence(
        db_path,
        int(parent_window_id),
        int(close_step["token_id"]),
        int(close_step["pair_id"]),
        operator_approved=True,
        snapshot_start_id=snapshot_ids[0],
        snapshot_end_id=snapshot_ids[-1],
        run_id=factory_run_id,
        tracking_lane=str(close_step["tracking_lane"]),
        support_capture=frozen,
    )
    materialized["verdict"] = (
        SupportCaptureVerdict.CAPTURE_SUPPORT.value
        if materialized.get("window_5m_id") is not None
        else SupportCaptureVerdict.BLOCK_SUPPORT_CAPTURE.value
    )
    materialized["event_time_frozen"] = True
    return materialized


__all__ = [
    "evaluate_event_time_5m_support_for_snapshot",
    "materialize_frozen_5m_support",
]

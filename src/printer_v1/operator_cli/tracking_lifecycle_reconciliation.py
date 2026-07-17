"""V2-9.7B.3 terminal tracking and post-cycle lifecycle reconciliation."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
    _ACTIVE_JOB_STATUSES,
    _ACTIVE_QUEUE_STATUSES,
    _ARCHIVE_POLICY_ARCHIVE,
    _ARCHIVE_POLICY_COOLDOWN,
    _EVENT_ARCHIVE_AFTER_MEMORY_WINDOW,
    _EVENT_ENTER_COOLDOWN,
    _HARD_LOCKS,
    _QUEUE_STATUS_ARCHIVED,
    _QUEUE_STATUS_COOLDOWN,
    _STATE_ARCHIVED,
    _STATE_COOLDOWN,
    _TERMINAL_MAIN_STATUSES,
    _utc_now,
)


def reconcile_factory_post_cycle_lifecycle(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    selected_tokens: list[dict[str, Any]],
    discovery_results: list[dict[str, Any]],
    per_token_outcomes: list[dict[str, Any]],
    stop_reason: str,
    archive_policy: str = _ARCHIVE_POLICY_COOLDOWN,
) -> dict[str, Any]:
    """Reconcile every selected token to one auditable terminal disposition.

    Only the main-window outcome chooses the disposition. Support-only 5m steps
    are reported and cleaned with the parent run but cannot affect lifecycle.
    The run/token/pair key makes repeated reconciliation idempotent.
    """
    if archive_policy not in {_ARCHIVE_POLICY_COOLDOWN, _ARCHIVE_POLICY_ARCHIVE}:
        raise ValueError(f"unsupported archive_policy: {archive_policy}")

    conn.row_factory = sqlite3.Row
    outcomes = {
        (int(row["token_id"]), int(row["pair_id"])): row
        for row in per_token_outcomes
        if row.get("token_id") is not None and row.get("pair_id") is not None
    }
    discovery_by_target = {
        (int(row["token_id"]), int(row["pair_id"])): row
        for row in discovery_results
        if row.get("token_id") is not None and row.get("pair_id") is not None
    }
    transitions: list[dict[str, Any]] = []

    for target in selected_tokens:
        token_id = int(target["token_id"])
        pair_id = int(target["pair_id"])
        tracking_lane = str(target["tracking_lane"])
        reconciliation_key = f"{run_id}:{token_id}:{pair_id}"
        outcome = outcomes.get((token_id, pair_id), {})
        terminal_status = str(outcome.get("terminal_status") or "INCOMPLETE")
        main_terminal = (
            terminal_status in _TERMINAL_MAIN_STATUSES
            and bool(outcome.get("reached_terminal_window"))
        )
        if main_terminal and archive_policy == _ARCHIVE_POLICY_ARCHIVE:
            disposition = _QUEUE_STATUS_ARCHIVED
            lifecycle_event = _EVENT_ARCHIVE_AFTER_MEMORY_WINDOW
            new_state = _STATE_ARCHIVED
        elif main_terminal:
            disposition = _QUEUE_STATUS_COOLDOWN
            lifecycle_event = _EVENT_ENTER_COOLDOWN
            new_state = _STATE_COOLDOWN
        else:
            disposition = "SKIPPED"
            lifecycle_event = "MANUAL_REVIEW"
            new_state = tracking_lane

        support_rows = [dict(row) for row in conn.execute(
            "SELECT id,step_status,memory_window_id,scheduler_job_id "
            "FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND token_id=? AND pair_id=? AND step_kind='SUPPORT_5M' "
            "ORDER BY id",
            (run_id, token_id, pair_id),
        ).fetchall()]
        existing_event = _find_reconciliation_event(
            conn, token_id, pair_id, reconciliation_key
        )
        handoff = discovery_by_target.get((token_id, pair_id), {})
        queue_id = _resolve_queue_id(
            conn, token_id, pair_id, tracking_lane, handoff.get("tracking_queue_id")
        )
        cancelled_job_ids = _cancel_associated_jobs(
            conn, queue_id, handoff.get("scheduler_job_id"), support_rows
        )
        now = _utc_now()
        for support in support_rows:
            if support["step_status"] in {"PENDING", "RUNNING"}:
                conn.execute(
                    "UPDATE printer_memory_factory_run_steps "
                    "SET step_status='CANCELLED',error_or_skip_reason=?,"
                    "finished_at=?,updated_at=? WHERE id=?",
                    (
                        f"parent_terminal_reconciliation:{stop_reason}",
                        now, now, int(support["id"]),
                    ),
                )
                support["step_status"] = "CANCELLED"
        if queue_id is not None:
            conn.execute(
                "UPDATE printer_tracking_queue SET queue_status=?,tracking_action=?,"
                "priority_reason=?,last_checked_at=?,updated_at=? WHERE id=? "
                "AND queue_status IN (?,?,?,?) AND queue_status<>?",
                (
                    disposition, lifecycle_event,
                    f"factory_terminal:{stop_reason}:{terminal_status}", now, now,
                    queue_id, *_ACTIVE_QUEUE_STATUSES, disposition,
                ),
            )

        event_id = int(existing_event["id"]) if existing_event is not None else None
        if existing_event is None:
            payload = {
                "factory_reconciliation_key": reconciliation_key,
                "run_id": run_id,
                "stop_reason": stop_reason,
                "terminal_status": terminal_status,
                "main_window_only": True,
                "support_5m_audit_only": True,
                "support_5m_step_ids": [int(row["id"]) for row in support_rows],
                "support_5m_window_ids": [
                    int(row["memory_window_id"])
                    for row in support_rows if row.get("memory_window_id") is not None
                ],
            }
            cursor = conn.execute(
                "INSERT INTO printer_token_lifecycle_events "
                "(token_id,pair_id,previous_state,new_state,lifecycle_event,"
                "priority_reason,source_status,data_quality_label,event_payload_json) "
                "VALUES (?,?,?,?,?,'factory_post_cycle_reconciliation','COMPLETE',?,?)",
                (
                    token_id, pair_id, tracking_lane, new_state, lifecycle_event,
                    "CLEAN_DATA" if main_terminal else "DO_NOT_TRAIN",
                    json.dumps(payload, sort_keys=True),
                ),
            )
            event_id = int(cursor.lastrowid)

        remaining_jobs = _active_jobs_for_queue(conn, queue_id)
        transitions.append({
            "token_id": token_id,
            "pair_id": pair_id,
            "token_mint": target.get("token_mint"),
            "pair_address": target.get("pair_address"),
            "tracking_lane": tracking_lane,
            "tracking_queue_id": queue_id,
            "terminal_disposition": disposition,
            "terminal_reason": f"{stop_reason}:{terminal_status}",
            "lifecycle_event": lifecycle_event,
            "lifecycle_event_id": event_id,
            "idempotent_replay": existing_event is not None,
            "cancelled_scheduler_job_ids": cancelled_job_ids,
            "remaining_active_scheduler_jobs": remaining_jobs,
            "support_5m": {
                "support_only": True,
                "step_count": len(support_rows),
                "steps": support_rows,
                "determined_lifecycle": False,
                "triggered_continuation": False,
            },
        })

    return {
        "policy": archive_policy,
        "selected_token_count": len(selected_tokens),
        "reconciled_token_count": len(transitions),
        "exactly_one_disposition_per_selected_token": len(transitions) == len(selected_tokens),
        "active_scheduler_jobs_after_reconciliation": sum(
            int(row["remaining_active_scheduler_jobs"]) for row in transitions
        ),
        "support_5m_is_audit_only": True,
        "transitions": transitions,
        "hard_locks": dict(_HARD_LOCKS),
    }


def _find_reconciliation_event(
    conn: sqlite3.Connection, token_id: int, pair_id: int, key: str
) -> sqlite3.Row | None:
    for row in conn.execute(
        "SELECT id,event_payload_json FROM printer_token_lifecycle_events "
        "WHERE token_id=? AND pair_id=? ORDER BY id",
        (token_id, pair_id),
    ).fetchall():
        try:
            payload = json.loads(str(row["event_payload_json"] or "{}"))
        except (TypeError, json.JSONDecodeError):
            payload = {}
        if payload.get("factory_reconciliation_key") == key:
            return row
    return None


def _resolve_queue_id(
    conn: sqlite3.Connection,
    token_id: int,
    pair_id: int,
    tracking_lane: str,
    supplied_queue_id: Any,
) -> int | None:
    if supplied_queue_id is not None:
        row = conn.execute(
            "SELECT id FROM printer_tracking_queue WHERE id=? AND token_id=? AND pair_id=?",
            (int(supplied_queue_id), token_id, pair_id),
        ).fetchone()
        if row is not None:
            return int(row["id"])
    row = conn.execute(
        "SELECT id FROM printer_tracking_queue "
        "WHERE token_id=? AND pair_id=? AND tracking_lane=? "
        "AND queue_status IN (?,?,?,?) ORDER BY id DESC LIMIT 1",
        (token_id, pair_id, tracking_lane, *_ACTIVE_QUEUE_STATUSES),
    ).fetchone()
    return int(row["id"]) if row is not None else None


def _cancel_associated_jobs(
    conn: sqlite3.Connection,
    queue_id: int | None,
    supplied_job_id: Any,
    support_rows: list[dict[str, Any]],
) -> list[int]:
    job_ids: set[int] = set()
    if supplied_job_id is not None:
        job_ids.add(int(supplied_job_id))
    if queue_id is not None:
        job_ids.update(
            int(row["id"])
            for row in conn.execute(
                "SELECT id FROM printer_scheduler_jobs "
                "WHERE target_table='printer_tracking_queue' AND target_id=? "
                "AND status IN (?,?,?)",
                (queue_id, *_ACTIVE_JOB_STATUSES),
            ).fetchall()
        )
    job_ids.update(
        int(row["scheduler_job_id"])
        for row in support_rows if row.get("scheduler_job_id") is not None
    )
    now = _utc_now()
    cancelled: list[int] = []
    for job_id in sorted(job_ids):
        row = conn.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id=?", (job_id,)
        ).fetchone()
        if row is not None and str(row["status"]) in _ACTIVE_JOB_STATUSES:
            conn.execute(
                "UPDATE printer_scheduler_jobs SET status='CANCELLED',finished_at=?,"
                "locked_at=NULL,lock_owner=NULL,updated_at=? WHERE id=?",
                (now, now, job_id),
            )
            cancelled.append(job_id)
    return cancelled


def _active_jobs_for_queue(conn: sqlite3.Connection, queue_id: int | None) -> int:
    if queue_id is None:
        return 0
    return int(conn.execute(
        "SELECT COUNT(*) FROM printer_scheduler_jobs "
        "WHERE target_table='printer_tracking_queue' AND target_id=? "
        "AND status IN (?,?,?)",
        (queue_id, *_ACTIVE_JOB_STATUSES),
    ).fetchone()[0])
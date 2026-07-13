"""V2-4 bounded proof-only one-command WINDOW_15M Memory Factory."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import (
    cancel_job,
    claim_due_job,
    complete_job,
    enqueue_job,
    fail_job,
)


COMMAND_NAME = "printer-run-one-command-15m-memory-factory"
POLICY_VERSION = "ONE_COMMAND_15M_FACTORY_V1"
WINDOW_KIND = "WINDOW_15M"
PERSISTENT_DB_NAME = "printer_v1.sqlite3"

STOP_COMPLETED = "COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED"
STOP_EMPTY = "SAFE_STOP_EMPTY_QUALIFIED_POOL"
STOP_PREFLIGHT = "SAFE_STOP_PREFLIGHT_FAILED"
STOP_SOURCE = "SAFE_STOP_SOURCE_FAILURE"
STOP_DURATION = "SAFE_STOP_TOTAL_DURATION_EXCEEDED"
STOP_INTERRUPTED = "SAFE_STOP_OPERATOR_INTERRUPTED"
STOP_AMBIGUOUS = "SAFE_STOP_AMBIGUOUS_PARTIAL_STEP"
STOP_RUNNING = "SAFE_STOP_RUNNING_JOB_REMAINS"
STOP_DB_DELTA = "SAFE_STOP_UNEXPECTED_DB_DELTA"

_COUNT_TABLES = (
    "printer_source_requests", "printer_source_responses", "printer_source_failures",
    "printer_discovery_candidates", "printer_selection_batches",
    "printer_selection_batch_items", "printer_tracking_queue",
    "printer_scheduler_jobs", "printer_token_snapshots", "printer_memory_windows",
    "printer_memories", "printer_memory_fingerprints",
    "printer_memory_retrieval_queries", "printer_memory_retrieval_matches",
    "printer_paper_decisions", "printer_paper_positions",
    "printer_paper_trade_events", "printer_paper_trade_audits",
    "printer_paper_audit_reports", "printer_memory_factory_runs",
    "printer_memory_factory_run_steps",
)

_FORBIDDEN_DELTA_TABLES = (
    "printer_memory_retrieval_queries", "printer_memory_retrieval_matches",
    "printer_paper_decisions", "printer_paper_positions",
    "printer_paper_trade_events", "printer_paper_trade_audits",
    "printer_paper_audit_reports",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _table_count(conn: sqlite3.Connection, table: str) -> int:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) if exists else 0


def _counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {table: _table_count(conn, table) for table in _COUNT_TABLES}


def _deltas(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    return {key: after.get(key, 0) - before.get(key, 0) for key in before}


def _config_hash(config: dict[str, Any]) -> str:
    return hashlib.sha256(_json(config).encode("ascii")).hexdigest()


def _is_persistent_db(path: Path) -> bool:
    expected = (Path.cwd() / "data" / PERSISTENT_DB_NAME).resolve()
    return path.resolve() == expected


def _require_schema(conn: sqlite3.Connection) -> None:
    required = {"printer_memory_factory_runs", "printer_memory_factory_run_steps"}
    present = {
        str(row[0]) for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    missing = sorted(required - present)
    if missing:
        raise ValueError(f"V2-4 migration missing: {missing}")


def _build_discovery_args(
    db_path: Path, *, max_selected_tokens: int, max_source_requests: int,
    timeout_seconds: float, selection_seed: str | None,
) -> argparse.Namespace:
    return argparse.Namespace(
        operator_approved=True, chain="solana", max_candidates=max_selected_tokens,
        enrich_15m_market_evidence=False, enrich_t3_token_age=False,
        t3_solana_rpc_url=None, query="pump", timeout_seconds=timeout_seconds,
        source_name="geckoterminal", request_kind=None,
        request_key="v2-4-one-command-discovery",
        max_source_requests=max_source_requests, selection_seed=selection_seed,
        format="json", db_path=str(db_path), project_root=str(Path.cwd()),
    )


def _selected_targets(conn: sqlite3.Connection, batch_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT i.token_mint, i.pair_address, i.tracking_lane,
               t.id AS token_id, p.id AS pair_id
        FROM printer_selection_batch_items i
        JOIN printer_tokens t ON lower(t.token_mint) = lower(i.token_mint)
        JOIN printer_pairs p ON p.token_id = t.id
                            AND lower(p.pair_address) = lower(i.pair_address)
        WHERE i.batch_id = ? AND i.item_status = 'SELECTED'
          AND i.tracking_lane IN ('TRACK_FAST', 'TRACK_NORMAL')
        ORDER BY lower(i.token_mint), lower(i.pair_address)
        """,
        (batch_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _cancel_discovery_handoffs(conn: sqlite3.Connection, discovery: dict[str, Any]) -> None:
    for item in discovery.get("discovery_results", []):
        job_id = item.get("scheduler_job_id")
        if job_id is not None:
            cancel_job(conn, job_id=int(job_id))


def _schedule_offsets(lane: str, window_seconds: float) -> list[float]:
    attempts = 10 if lane == "TRACK_FAST" else 6
    # The opening and window-close jobs perform the boundary snapshot attempts.
    return [
        round(window_seconds * index / (attempts - 1), 6)
        for index in range(1, attempts - 1)
    ]


def _insert_step_and_job(
    conn: sqlite3.Connection, *, run_id: str, target: dict[str, Any],
    step_key: str, step_kind: str, scheduled_for: datetime,
) -> int:
    job_kind = (
        JobKind.MEMORY_WINDOW_CLOSE
        if step_kind == "WINDOW_CLOSE"
        else (
            JobKind.TRACK_FAST_FIRST_15M
            if target["tracking_lane"] == "TRACK_FAST"
            else JobKind.TRACK_NORMAL_FIRST_15M
        )
    )
    result, job_id = enqueue_job(
        conn, job_name=f"v2_4_{run_id}_{step_key}", job_kind=job_kind,
        target_table="printer_tracking_queue", target_id=None,
        scheduled_for=scheduled_for,
    )
    if result != LockResult.ACQUIRED or job_id is None:
        raise ValueError(f"scheduler enqueue failed for {step_key}: {result}")
    conn.execute(
        """
        INSERT INTO printer_memory_factory_run_steps
          (run_id, step_key, step_kind, step_status, token_id, pair_id,
           token_mint, pair_address, tracking_lane, scheduled_for,
           scheduler_job_id, created_at, updated_at)
        VALUES (?, ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, step_key, step_kind, target["token_id"], target["pair_id"],
            target["token_mint"], target["pair_address"], target["tracking_lane"],
            _iso(scheduled_for), job_id, _iso(), _iso(),
        ),
    )
    return int(job_id)


def _plan_opening_jobs(
    conn: sqlite3.Connection, run_id: str, targets: list[dict[str, Any]],
    scheduled_for: datetime,
) -> None:
    for target_index, target in enumerate(targets):
        prefix = f"t{target_index + 1}"
        _insert_step_and_job(
            conn, run_id=run_id, target=target,
            step_key=f"{prefix}_snapshot_00", step_kind="SNAPSHOT",
            scheduled_for=scheduled_for,
        )


def _plan_anchored_jobs(
    conn: sqlite3.Connection, *, run_id: str, opening_step: sqlite3.Row,
    first_snapshot_captured_at: str, window_seconds: float,
) -> None:
    """Plan one token's remaining work from its persisted opening evidence."""
    anchor = datetime.fromisoformat(first_snapshot_captured_at)
    prefix = str(opening_step["step_key"]).rsplit("_snapshot_", 1)[0]
    target = {
        "token_id": int(opening_step["token_id"]),
        "pair_id": int(opening_step["pair_id"]),
        "token_mint": str(opening_step["token_mint"]),
        "pair_address": str(opening_step["pair_address"]),
        "tracking_lane": str(opening_step["tracking_lane"]),
    }
    for slot_index, offset in enumerate(
        _schedule_offsets(target["tracking_lane"], window_seconds), start=1
    ):
        _insert_step_and_job(
            conn, run_id=run_id, target=target,
            step_key=f"{prefix}_snapshot_{slot_index:02d}", step_kind="SNAPSHOT",
            scheduled_for=anchor + timedelta(seconds=offset),
        )
    _insert_step_and_job(
        conn, run_id=run_id, target=target,
        step_key=f"{prefix}_window_close", step_kind="WINDOW_CLOSE",
        scheduled_for=anchor + timedelta(seconds=window_seconds),
    )


def _evidence_duration_seconds(start_at: str, end_at: str) -> float:
    start = datetime.fromisoformat(start_at)
    end = datetime.fromisoformat(end_at)
    return (end - start).total_seconds()


def _evidence_duration_is_eligible(
    start_at: str, end_at: str, *, minimum_seconds: float = 900.0,
) -> bool:
    return _evidence_duration_seconds(start_at, end_at) >= minimum_seconds


def _execute_snapshot(
    conn: sqlite3.Connection, step: sqlite3.Row, *, adapter_factory: Callable[..., Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    from printer_v1.operator_cli.e2m_snapshot_persistence import (
        E2M_STATUS_PERSISTED, persist_snapshot_from_source_response,
    )
    from printer_v1.sources.budget_accounting import count_recent_source_requests
    from printer_v1.sources.contracts import build_governed_source_request
    from printer_v1.sources.governed_execution import execute_source_request_with_governor

    mint = str(step["token_mint"])
    request = build_governed_source_request(
        "dexscreener", "pair_market_snapshot",
        request_key=f"{step['run_id']}:{step['step_key']}",
        payload={"token_mint": mint, "pair_address": step["pair_address"]},
    )
    adapter = adapter_factory(token_mint=mint, timeout_seconds=timeout_seconds)
    execution = execute_source_request_with_governor(
        conn, request, adapter,
        recent_request_count=count_recent_source_requests(conn, "dexscreener"),
    )
    result: dict[str, Any] = {
        "source_request_id": int(execution.request_record.id),
        "source_response_id": (
            int(execution.response_record.id) if execution.response_record else None
        ),
        "source_failure_id": (
            int(execution.failure_record.id) if execution.failure_record else None
        ),
        "source_status": execution.normalized_result.source_status.value,
        "data_quality_label": execution.normalized_result.data_quality_label.value,
    }
    if execution.response_record is None:
        result["ok"] = False
        result["blocked_reason"] = execution.normalized_result.failure_type or "source_response_missing"
        return result
    persisted = persist_snapshot_from_source_response(
        conn, int(execution.response_record.id), mint,
        expected_pair_address=str(step["pair_address"]),
        tracking_lane=str(step["tracking_lane"]),
    )
    result["snapshot"] = persisted
    result["snapshot_id"] = persisted.get("snapshot_id") or persisted.get("existing_snapshot_id")
    result["ok"] = persisted.get("e2m_status") == E2M_STATUS_PERSISTED
    if not result["ok"]:
        result["blocked_reason"] = "; ".join(persisted.get("blocked_reasons", [])) or persisted.get("e2m_status")
    return result


def _attach_context_and_gate_window(
    conn: sqlite3.Connection, *, step: sqlite3.Row, window_id: int,
    snapshot_start_id: int, snapshot_end_id: int,
) -> dict[str, Any]:
    """Attach existing-engine context and fail closed before clean promotion."""
    from printer_v1.context_evidence import build_window_15m_context_evidence
    from printer_v1.operator_cli.commands import (
        _apply_clean_audit_evidence_labels,
        _classify_first_memory_review,
        _context_freshness_report,
        _context_memory_labels,
        _context_row_ids_for_memory,
        _derive_15m_window_context_from_snapshots,
        _insert_controlled_context_rows,
        _resolve_memory_context_rows,
    )

    snapshots = [dict(row) for row in conn.execute(
        """
        SELECT * FROM printer_token_snapshots
        WHERE token_id=? AND pair_id=? AND id BETWEEN ? AND ?
        ORDER BY captured_at, id
        """,
        (step["token_id"], step["pair_id"], snapshot_start_id, snapshot_end_id),
    ).fetchall()]
    if not snapshots:
        raise ValueError("exact snapshot range is empty")
    target = {
        "token_id": int(step["token_id"]),
        "pair_id": int(step["pair_id"]),
        "token_mint": str(step["token_mint"]),
        "pair_address": str(step["pair_address"]),
    }
    end_snapshot = snapshots[-1]
    _insert_controlled_context_rows(
        conn, target, end_snapshot, str(end_snapshot["captured_at"])
    )
    context_rows = _resolve_memory_context_rows(
        conn, target, int(end_snapshot["id"])
    )
    start_at = str(snapshots[0]["captured_at"])
    end_at = str(end_snapshot["captured_at"])
    freshness = _context_freshness_report(
        context_rows, end_snapshot, start_at, end_at
    )
    labels = _context_memory_labels(context_rows)
    derived = _derive_15m_window_context_from_snapshots(snapshots, WINDOW_KIND)
    labels.update(derived.get("labels") or {})
    evidence = _apply_clean_audit_evidence_labels(
        conn,
        window={
            "id": window_id,
            "token_id": target["token_id"],
            "pair_id": target["pair_id"],
            "snapshot_end_id": snapshot_end_id,
            "window_kind": WINDOW_KIND,
        },
        labels=labels,
    )
    try:
        shared_context = build_window_15m_context_evidence(
            conn,
            token_id=target["token_id"],
            pair_id=target["pair_id"],
            snapshot_start_id=snapshot_start_id,
            snapshot_end_id=snapshot_end_id,
            window_start_at=start_at,
            window_end_at=end_at,
        )
    except ValueError as exc:
        shared_context = {
            "clean_memory_context_ready": False,
            "blockers": [f"SHARED_CONTEXT_WINDOW_INVALID:{exc}"],
            "sections": {},
            "writes_performed": False,
        }
    shared_labels: dict[str, Any] = {}
    for section in shared_context.get("sections", {}).values():
        shared_labels.update(section.get("labels") or {})
    effective_labels = {**evidence["labels"], **shared_labels}
    shared_blockers = list(shared_context.get("blockers") or [])
    combined_evidence_blockers = list(dict.fromkeys(
        list(evidence["overlays"].get("evidence_blockers", []))
        + shared_blockers
    ))
    classification = _classify_first_memory_review(
        snapshots,
        context_rows,
        WINDOW_KIND,
        freshness,
        effective_labels=effective_labels,
        evidence_blockers=combined_evidence_blockers,
        outcome_label=derived.get("outcome_label"),
    )
    remaining = list(dict.fromkeys(
        freshness.get("context_blocking_reasons", [])
        + classification.get("unknown_context_blockers", [])
        + classification.get("evidence_blockers", [])
    ))
    row = conn.execute(
        "SELECT supporting_context_json FROM printer_memory_windows WHERE id=?",
        (window_id,),
    ).fetchone()
    supporting = json.loads(str(row[0]) or "{}") if row else {}
    supporting.update({
        "context_quality_reviewed": True,
        "context_row_ids": _context_row_ids_for_memory(context_rows),
        "context_labels": effective_labels,
        "context_freshness_report": freshness,
        "memory_build_evidence_overlays": evidence["overlays"],
        "shared_window_15m_context_evidence": shared_context,
        "derived_window_context": derived.get("payload"),
        "outcome_label": classification["outcome_label"],
        "remaining_blockers": remaining,
        "window_5m_support_role": "SUPPORT_ONLY_NOT_MAIN_EVIDENCE",
    })
    if classification["memory_quality_label"] == "CLEAN_MEMORY":
        # Lane K owns clean promotion; this row stays a PARTIAL_MEMORY candidate.
        quality = "PARTIAL_MEMORY"
        memory_status = "PARTIAL_MEMORY"
        data_quality = "CLEAN_DATA"
        do_not_train = 0
    else:
        quality = classification["memory_quality_label"]
        memory_status = classification["memory_status"]
        data_quality = classification["data_quality_label"]
        do_not_train = 1
    conn.execute(
        """
        UPDATE printer_memory_windows
        SET memory_quality_label=?, memory_status=?, data_quality_label=?,
            do_not_train=?, outcome_label=?, rejection_reasons_json=?,
            supporting_context_json=?, updated_at=?
        WHERE id=?
        """,
        (
            quality, memory_status, data_quality, do_not_train,
            classification["outcome_label"],
            _json(classification["rejection_reasons"]), _json(supporting),
            _iso(), window_id,
        ),
    )
    return {
        "classification": classification,
        "remaining_blockers": remaining,
        "context_row_ids": supporting["context_row_ids"],
        "context_labels": effective_labels,
        "derived_window_context": derived.get("payload"),
        "shared_context_evidence": shared_context,
        "clean_promotion_candidate": do_not_train == 0,
    }


def _execute_close(
    conn: sqlite3.Connection, step: sqlite3.Row, *, adapter_factory: Callable[..., Any],
    timeout_seconds: float, minimum_evidence_seconds: float,
) -> dict[str, Any]:
    from printer_v1.operator_cli.e2o_memory_window_close import close_15m_memory_window_from_snapshot
    from printer_v1.operator_cli.e2q_memory_window_audit import audit_15m_memory_window
    from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline

    result = _execute_snapshot(
        conn, step, adapter_factory=adapter_factory, timeout_seconds=timeout_seconds
    )
    if not result.get("ok"):
        return result
    first = conn.execute(
        """
        SELECT s.snapshot_id, ts.captured_at
        FROM printer_memory_factory_run_steps s
        JOIN printer_token_snapshots ts ON ts.id=s.snapshot_id
        WHERE s.run_id=? AND s.token_id=? AND s.pair_id=? AND s.step_kind='SNAPSHOT'
          AND step_status='SUCCEEDED' AND snapshot_id IS NOT NULL
        ORDER BY s.scheduled_for, s.id LIMIT 1
        """,
        (step["run_id"], step["token_id"], step["pair_id"]),
    ).fetchone()
    if first is None:
        result.update(ok=False, blocked_reason="no successful opening snapshot")
        return result
    end_row = conn.execute(
        "SELECT captured_at FROM printer_token_snapshots WHERE id=?",
        (int(result["snapshot_id"]),),
    ).fetchone()
    if end_row is None or not _evidence_duration_is_eligible(
        str(first["captured_at"]), str(end_row["captured_at"]),
        minimum_seconds=minimum_evidence_seconds,
    ):
        result.update(
            ok=False,
            blocked_reason="persisted snapshot evidence duration below required window",
            evidence_duration_seconds=(
                _evidence_duration_seconds(
                    str(first["captured_at"]), str(end_row["captured_at"])
                ) if end_row is not None else None
            ),
        )
        return result
    close = close_15m_memory_window_from_snapshot(
        conn, int(result["snapshot_id"]), str(step["token_mint"]),
        snapshot_start_id=int(first["snapshot_id"]),
    )
    window_id = close.get("window_id") or close.get("existing_window_id")
    result["window_close"] = close
    result["memory_window_id"] = window_id
    if window_id is None:
        result.update(ok=False, blocked_reason="; ".join(close.get("blocked_reasons", [])) or "window close blocked")
        return result
    result["context_quality"] = _attach_context_and_gate_window(
        conn,
        step=step,
        window_id=int(window_id),
        snapshot_start_id=int(first["snapshot_id"]),
        snapshot_end_id=int(result["snapshot_id"]),
    )
    result["window_audit"] = audit_15m_memory_window(conn, int(window_id))
    conn.commit()
    result["memory_pipeline"] = run_e2z_pipeline(
        str(conn.execute("PRAGMA database_list").fetchone()[2]),
        operator_approved=True, production_mode=True,
    )
    result["ok"] = True
    return result


def _update_step(
    conn: sqlite3.Connection, step_id: int, status: str, result: dict[str, Any],
    *, error: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE printer_memory_factory_run_steps
        SET step_status=?, source_request_id=?, source_response_id=?,
            source_failure_id=?, snapshot_id=?, memory_window_id=?, result_json=?,
            error_or_skip_reason=?, finished_at=?, updated_at=?
        WHERE id=?
        """,
        (
            status, result.get("source_request_id"), result.get("source_response_id"),
            result.get("source_failure_id"), result.get("snapshot_id"),
            result.get("memory_window_id"), _json(result), error, _iso(), _iso(), step_id,
        ),
    )


def _cancel_pending(conn: sqlite3.Connection, run_id: str, reason: str) -> None:
    rows = conn.execute(
        "SELECT id, scheduler_job_id FROM printer_memory_factory_run_steps WHERE run_id=? AND step_status='PENDING'",
        (run_id,),
    ).fetchall()
    for row in rows:
        if row["scheduler_job_id"] is not None:
            cancel_job(conn, job_id=int(row["scheduler_job_id"]))
        conn.execute(
            "UPDATE printer_memory_factory_run_steps SET step_status='CANCELLED', error_or_skip_reason=?, finished_at=?, updated_at=? WHERE id=?",
            (reason, _iso(), _iso(), int(row["id"])),
        )


def _final_report(
    conn: sqlite3.Connection, *, run_id: str, config: dict[str, Any],
    discovery: dict[str, Any], before: dict[str, int], stop_reason: str,
    started_at: str,
) -> dict[str, Any]:
    after = _counts(conn)
    deltas = _deltas(before, after)
    steps = [dict(row) for row in conn.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE run_id=? ORDER BY scheduled_for, id", (run_id,)
    ).fetchall()]
    jobs = [dict(row) for row in conn.execute(
        "SELECT j.* FROM printer_scheduler_jobs j JOIN printer_memory_factory_run_steps s ON s.scheduler_job_id=j.id WHERE s.run_id=? ORDER BY j.id",
        (run_id,),
    ).fetchall()]
    running = sum(1 for job in jobs if job["status"] == "RUNNING" or job["locked_at"] or job["lock_owner"])
    forbidden = {table: deltas.get(table, 0) for table in _FORBIDDEN_DELTA_TABLES}
    windows = [dict(row) for row in conn.execute(
        "SELECT * FROM printer_memory_windows WHERE id IN (SELECT memory_window_id FROM printer_memory_factory_run_steps WHERE run_id=? AND memory_window_id IS NOT NULL)",
        (run_id,),
    ).fetchall()]
    selected = _selected_targets(conn, discovery.get("selection_handoff_report", {}).get("batch_id") or "")
    return {
        "command": COMMAND_NAME, "policy_version": POLICY_VERSION,
        "run_id": run_id, "run_status": "COMPLETED" if stop_reason == STOP_COMPLETED else "SAFE_STOPPED",
        "stop_reason": stop_reason, "started_at": started_at, "finished_at": _iso(),
        "config": config, "selection_seed": discovery.get("selection_handoff_report", {}).get("selection_seed"),
        "eligible_pool_size": discovery.get("selection_handoff_report", {}).get("eligible_pool_size", 0),
        "selected_tokens": selected, "discovery_report": discovery,
        "scheduler_jobs": jobs, "steps": steps, "memory_windows": windows,
        "memory_results": {
            "clean": sum(1 for row in windows if row.get("memory_quality_label") == "CLEAN_MEMORY"),
            "dirty_or_audit_only": sum(1 for row in windows if row.get("memory_quality_label") in {"DIRTY_MEMORY", "AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN"}),
            "blocked_or_partial": sum(1 for row in windows if row.get("memory_quality_label") not in {"CLEAN_MEMORY", "DIRTY_MEMORY", "AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN"}),
            "zero_clean_is_valid": True,
        },
        "counts_before": before, "counts_after": after, "table_deltas": deltas,
        "forbidden_deltas": forbidden, "running_jobs_after_stop": running,
        "locks_preserved": {
            "retrieval": all(value == 0 for table, value in forbidden.items() if "retrieval" in table),
            "financial": all(value == 0 for table, value in forbidden.items() if "retrieval" not in table),
            "window_15m_only": True, "paper_decisions_off": True,
        },
    }


def load_report_only(db_path: str | Path, run_id: str) -> dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT final_report_json FROM printer_memory_factory_runs WHERE run_id=? AND final_report_json IS NOT NULL",
            (run_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"terminal report not found for run_id={run_id}")
        report = json.loads(str(row[0]))
        report["replay"] = {"mode": "REPORT_ONLY", "new_source_calls": 0, "new_evidence_rows": 0}
        return report
    finally:
        conn.close()


def run_one_command_15m_factory(
    db_path: str | Path, backup_path: str | Path, *, operator_approved: bool,
    proof_mode: bool, window_kind: str = WINDOW_KIND, max_selected_tokens: int = 2,
    max_source_requests: int = 2, timeout_seconds: float = 5.0,
    total_duration_seconds: float = 1200.0, selection_seed: str | None = None,
    discovery_transport: Any = None, discovery_runner: Callable[..., dict[str, Any]] | None = None,
    snapshot_adapter_factory: Callable[..., Any] | None = None,
    _window_seconds: float = 900.0, _sleep: Callable[[float], None] = time.sleep,
    _monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    path = Path(db_path).resolve()
    backup = Path(backup_path).resolve()
    reasons: list[str] = []
    if not operator_approved: reasons.append("operator approval required")
    if not proof_mode: reasons.append("first V2-4 command supports proof mode only")
    if window_kind != WINDOW_KIND: reasons.append(f"unsupported window_kind: {window_kind}")
    if not path.is_file(): reasons.append(f"proof DB missing: {path}")
    if not backup.is_file(): reasons.append(f"backup missing: {backup}")
    if _is_persistent_db(path): reasons.append("persistent DB is forbidden in first proof")
    if not 1 <= max_selected_tokens <= 2: reasons.append("max_selected_tokens must be 1 or 2")
    if not 1 <= max_source_requests <= 2: reasons.append("max_source_requests must be 1 or 2")
    if total_duration_seconds <= _window_seconds: reasons.append("total duration must exceed window duration")
    if reasons:
        return {"command": COMMAND_NAME, "run_status": "SAFE_STOPPED", "stop_reason": STOP_PREFLIGHT, "blocked_reasons": reasons}

    from printer_v1.operator_cli.commands import build_discover_candidates_once_payload
    from printer_v1.operator_cli.e2i_source_transport import build_e2i_dexscreener_adapter

    discovery_callable = discovery_runner or build_discover_candidates_once_payload
    adapter_factory = snapshot_adapter_factory or build_e2i_dexscreener_adapter
    config = {
        "db_mode": "PROOF_ONLY", "db_path": str(path), "backup_path": str(backup),
        "window_kind": window_kind, "max_selected_tokens": max_selected_tokens,
        "max_source_requests": max_source_requests, "timeout_seconds": timeout_seconds,
        "total_duration_seconds": total_duration_seconds, "window_seconds": _window_seconds,
        "automatic_retries": 0, "discovery_source": "geckoterminal",
    }
    run_id = str(uuid.uuid4())
    started_dt = _now()
    started_at = _iso(started_dt)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    _require_schema(conn)
    before = _counts(conn)
    conn.execute(
        "INSERT INTO printer_memory_factory_runs (run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at,created_at,updated_at) VALUES (?,'RUNNING',?,'PROOF_ONLY',?,?,?,?,?)",
        (run_id, window_kind, _config_hash(config), _json(config), started_at, started_at, started_at),
    )
    conn.commit()
    discovery: dict[str, Any] = {}
    stop_reason = STOP_COMPLETED
    start_mono = _monotonic()
    try:
        args = _build_discovery_args(
            path, max_selected_tokens=max_selected_tokens,
            max_source_requests=max_source_requests, timeout_seconds=timeout_seconds,
            selection_seed=selection_seed,
        )
        if discovery_runner is None:
            discovery = discovery_callable(args, transport=discovery_transport)
        else:
            discovery = discovery_callable(args)
        handoff = discovery.get("selection_handoff_report", {})
        batch_id = handoff.get("batch_id")
        targets = _selected_targets(conn, str(batch_id or ""))
        conn.execute(
            "UPDATE printer_memory_factory_runs SET selection_seed=?,selection_batch_id=?,eligible_pool_size=?,selected_token_count=?,updated_at=? WHERE run_id=?",
            (handoff.get("selection_seed"), batch_id, handoff.get("eligible_pool_size", 0), len(targets), _iso(), run_id),
        )
        _cancel_discovery_handoffs(conn, discovery)
        if not targets:
            stop_reason = STOP_EMPTY
        else:
            _plan_opening_jobs(conn, run_id, targets, _now())
        conn.commit()

        while stop_reason == STOP_COMPLETED:
            pending = conn.execute(
                "SELECT s.* FROM printer_memory_factory_run_steps s WHERE s.run_id=? AND s.step_status='PENDING' ORDER BY s.scheduled_for,s.id LIMIT 1",
                (run_id,),
            ).fetchone()
            if pending is None:
                break
            elapsed = _monotonic() - start_mono
            if elapsed >= total_duration_seconds:
                stop_reason = STOP_DURATION
                break
            due = datetime.fromisoformat(str(pending["scheduled_for"]))
            wait = max(0.0, (due - _now()).total_seconds())
            if wait:
                _sleep(min(wait, max(0.0, total_duration_seconds - elapsed)))
                continue
            job_id = int(pending["scheduler_job_id"])
            claimed = claim_due_job(conn, job_id=job_id, lock_owner=f"v2_4:{run_id}")
            if claimed != LockResult.ACQUIRED:
                stop_reason = STOP_AMBIGUOUS
                break
            conn.execute(
                "UPDATE printer_memory_factory_run_steps SET step_status='RUNNING',started_at=?,updated_at=? WHERE id=?",
                (_iso(), _iso(), int(pending["id"])),
            )
            conn.commit()
            try:
                result = (
                    _execute_close(
                        conn, pending, adapter_factory=adapter_factory,
                        timeout_seconds=timeout_seconds,
                        minimum_evidence_seconds=_window_seconds,
                    )
                    if pending["step_kind"] == "WINDOW_CLOSE"
                    else _execute_snapshot(conn, pending, adapter_factory=adapter_factory, timeout_seconds=timeout_seconds)
                )
                if result.get("ok"):
                    if str(pending["step_key"]).endswith("_snapshot_00"):
                        captured = conn.execute(
                            "SELECT captured_at FROM printer_token_snapshots WHERE id=?",
                            (int(result["snapshot_id"]),),
                        ).fetchone()
                        if captured is None:
                            raise ValueError("opening snapshot was not persisted")
                        _plan_anchored_jobs(
                            conn,
                            run_id=run_id,
                            opening_step=pending,
                            first_snapshot_captured_at=str(captured[0]),
                            window_seconds=_window_seconds,
                        )
                    _update_step(conn, int(pending["id"]), "SUCCEEDED", result)
                    complete_job(conn, job_id=job_id)
                else:
                    error = str(result.get("blocked_reason") or "governed step blocked")
                    _update_step(conn, int(pending["id"]), "FAILED", result, error=error)
                    fail_job(conn, job_id=job_id, error=error, max_retries=0)
                    stop_reason = STOP_SOURCE
                conn.commit()
            except Exception as exc:
                result = {"ok": False, "exception": f"{type(exc).__name__}: {exc}"}
                _update_step(conn, int(pending["id"]), "FAILED", result, error=result["exception"])
                fail_job(conn, job_id=job_id, error=result["exception"], max_retries=0)
                conn.commit()
                stop_reason = STOP_SOURCE
    except KeyboardInterrupt:
        stop_reason = STOP_INTERRUPTED
    except Exception as exc:
        stop_reason = STOP_PREFLIGHT
        discovery = {**discovery, "orchestration_error": f"{type(exc).__name__}: {exc}"}
    finally:
        _cancel_pending(conn, run_id, stop_reason)
        conn.commit()
        report = _final_report(
            conn, run_id=run_id, config=config, discovery=discovery, before=before,
            stop_reason=stop_reason, started_at=started_at,
        )
        if report["running_jobs_after_stop"]:
            report["stop_reason"] = STOP_RUNNING
            report["run_status"] = "SAFE_STOPPED"
        if any(report["forbidden_deltas"].values()):
            report["stop_reason"] = STOP_DB_DELTA
            report["run_status"] = "SAFE_STOPPED"
        conn.execute(
            "UPDATE printer_memory_factory_runs SET run_status=?,stop_reason=?,finished_at=?,final_report_json=?,updated_at=? WHERE run_id=?",
            (report["run_status"], report["stop_reason"], report["finished_at"], _json(report), _iso(), run_id),
        )
        conn.commit()
        conn.close()
    return report

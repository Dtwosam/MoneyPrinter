"""Lane K — E2Q-to-E2Z Clean-Memory Pipeline Wiring Boundary.

Connects existing audited 15m windows into the clean-memory creation path:

  E2Q-audited WINDOW_15M
  → E2X eligibility (build_e2x_15m_clean_memory_eligibility_report)
  → E2Y candidate set gate (build_e2y_15m_candidate_set_gate_report)
  → E2Z clean-memory creation (create_clean_memory_from_window)

Requires operator_approved=True and a valid db_path.

Zero clean memories is a valid outcome (E2Y set gate may not pass if fewer
than 5 eligible candidates exist — that is not an error).

Idempotent: a second call for the same DB creates zero new rows (E2Z returns
E2Z_ALREADY_EXISTS for each window it already processed).

Permanently locked (no unlock path in this module):
  retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events,
  paper trade audits, PnL, live trading, wallet/private keys,
  source fetching, scheduler jobs, paid APIs, scoring, embeddings,
  5m as main outcome memory.

New write path introduced: NONE. All writes go through E2Z, which was the
only approved write path before Lane K was implemented.

Classification outcomes:
  LANE_K_COMPLETED  — pipeline ran; clean_memory_rows_created >= 0 (zero valid)
  LANE_K_BLOCKED    — operator_approved not set or db_path missing/invalid
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from printer_v1.operator_cli.e2x_15m_clean_memory_eligibility import (
    E2X_STATUS_BLOCKED as _E2X_STATUS_BLOCKED,
    build_e2x_15m_clean_memory_eligibility_report,
)
from printer_v1.operator_cli.e2y_15m_candidate_set_gate import (
    build_e2y_15m_candidate_set_gate_report,
)
from printer_v1.operator_cli.e2z_clean_memory_creation import (
    E2Z_STATUS_ALREADY_EXISTS,
    E2Z_STATUS_BLOCKED as _E2Z_STATUS_BLOCKED,
    E2Z_STATUS_CREATED,
    create_clean_memory_from_window,
)


LANE_K_STATUS_COMPLETED: str = "LANE_K_COMPLETED"
LANE_K_STATUS_BLOCKED: str = "LANE_K_BLOCKED"

LANE_K_NAME: str = "Lane K — E2Q-to-E2Z Clean-Memory Pipeline Wiring"

_TRACKED_TABLES: tuple[str, ...] = (
    "printer_episodes",
    "printer_source_requests",
    "printer_source_responses",
    "printer_source_failures",
    "printer_scheduler_jobs",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
)

_HARD_LOCKS: dict[str, bool] = {
    "no_retrieval_activation": True,
    "no_paper_decisions": True,
    "no_buy_sell_hold": True,
    "no_positions": True,
    "no_pnl": True,
    "no_live_trading": True,
    "no_wallet_private_key": True,
    "no_paid_api": True,
    "no_source_fetching": True,
    "no_scheduler_runtime_expansion": True,
    "no_scoring_ranking_confidence": True,
    "no_embeddings_vectors": True,
    "no_5m_main_outcome": True,
    "no_new_write_path_outside_e2z": True,
    "no_scheduler_jobs_created": True,
    "no_source_requests_created": True,
    "no_trade_events_created": True,
    "no_paper_trade_audits_created": True,
}

_LOCKED_CAPABILITIES: dict[str, bool] = {
    "retrieval_active": False,
    "paper_decision_creation_active": False,
    "buy_unlock_active": False,
    "sell_unlock_active": False,
    "hold_unlock_active": False,
    "paper_positions_active": False,
    "pnl_active": False,
    "trade_events_active": False,
    "paper_trade_audits_active": False,
    "live_trading_active": False,
    "wallet_active": False,
    "5m_main_outcome_active": False,
    "scheduler_jobs_created": False,
    "source_requests_created": False,
}

_RECOMMENDED_NEXT_ACTION: str = (
    "Rerun to verify idempotency (e2z_already_exists_count should equal "
    "e2z_created_count from the first run). If E2Y set gate did not pass, "
    "verify that at least 5 eligible E2Q-audited WINDOW_15M rows exist with "
    "the same token/pair, CLEAN_DATA, PARTIAL_MEMORY status, do_not_train=0, "
    "snapshot links, and strictly increasing snapshot_ids."
)


def _count_table(db_path: str, table: str) -> int | str:
    try:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if row is None:
                return "table_absent"
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        finally:
            conn.close()
    except Exception:
        return "count_error"


def _snapshot_counts(db_path: str) -> dict[str, int | str]:
    return {t: _count_table(db_path, t) for t in _TRACKED_TABLES}


def _delta_summary(
    before: dict[str, int | str],
    after: dict[str, int | str],
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for table in _TRACKED_TABLES:
        b = before[table]
        a = after[table]
        if isinstance(b, int) and isinstance(a, int):
            summary[table] = {"before": b, "after": a, "delta": a - b}
        else:
            summary[table] = {"before": b, "after": a, "delta": "unknown"}
    return summary


def _blocked_result(reasons: list[str], db_path_str: str) -> dict[str, Any]:
    return {
        "lane_k_status": LANE_K_STATUS_BLOCKED,
        "lane": LANE_K_NAME,
        "operator_approved": False,
        "db_path": db_path_str,
        "blocked_reasons": reasons,
        "e2x_status": _E2X_STATUS_BLOCKED,
        "e2y_status": "E2Y_SET_GATE_BLOCKED",
        "e2y_set_gate_passed": False,
        "e2z_created_count": 0,
        "e2z_already_exists_count": 0,
        "e2z_blocked_count": 0,
        "clean_memory_rows_created": 0,
        "candidate_window_ids": [],
        "zero_clean_memories_valid": True,
        "hard_locks": dict(_HARD_LOCKS),
        "locked_capabilities": dict(_LOCKED_CAPABILITIES),
        "db_delta_summary": {},
        "recommended_next_action": _RECOMMENDED_NEXT_ACTION,
        "retrieval_activated": False,
        "paper_decisions_created": 0,
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "positions_created": 0,
        "pnl_created": 0,
        "trade_events_created": 0,
        "paper_trade_audits_created": 0,
    }


def run_e2z_pipeline(
    db_path: str | Path | None,
    *,
    operator_approved: bool = False,
) -> dict[str, Any]:
    """Wire E2X eligibility → E2Y set gate → E2Z clean-memory creation.

    Requires operator_approved=True and a valid db_path.
    Zero clean memories is always a valid outcome.
    Idempotent: re-running does not duplicate clean-memory rows.
    """
    blocked_reasons: list[str] = []

    if not operator_approved:
        blocked_reasons.append("operator_approved must be True")

    db_path_str: str = ""
    if db_path is None:
        blocked_reasons.append("db_path is required")
    else:
        p = Path(db_path)
        db_path_str = str(p)
        if not p.is_file():
            blocked_reasons.append(f"db_path not found: {db_path}")

    if blocked_reasons:
        return _blocked_result(blocked_reasons, db_path_str)

    before = _snapshot_counts(db_path_str)

    # Step 1: E2X eligibility
    e2x_report = build_e2x_15m_clean_memory_eligibility_report(
        db_path, operator_approved=True
    )
    e2x_status = e2x_report.get("e2x_status", _E2X_STATUS_BLOCKED)

    # Step 2: E2Y set gate
    e2y_report = build_e2y_15m_candidate_set_gate_report(
        db_path, operator_approved=True
    )
    e2y_status = e2y_report.get("e2y_status", "E2Y_SET_GATE_BLOCKED")
    set_gate_passed: bool = bool(e2y_report.get("set_gate_passed", False))

    if not set_gate_passed:
        after = _snapshot_counts(db_path_str)
        return {
            "lane_k_status": LANE_K_STATUS_COMPLETED,
            "lane": LANE_K_NAME,
            "operator_approved": True,
            "db_path": db_path_str,
            "blocked_reasons": [
                "E2Y set gate not passed — zero clean memories is valid"
            ],
            "e2x_status": e2x_status,
            "e2y_status": e2y_status,
            "e2y_set_gate_passed": False,
            "e2z_created_count": 0,
            "e2z_already_exists_count": 0,
            "e2z_blocked_count": 0,
            "clean_memory_rows_created": 0,
            "candidate_window_ids": [],
            "zero_clean_memories_valid": True,
            "hard_locks": dict(_HARD_LOCKS),
            "locked_capabilities": dict(_LOCKED_CAPABILITIES),
            "db_delta_summary": _delta_summary(before, after),
            "recommended_next_action": _RECOMMENDED_NEXT_ACTION,
            "retrieval_activated": False,
            "paper_decisions_created": 0,
            "buy_enabled": False,
            "sell_enabled": False,
            "hold_enabled": False,
            "positions_created": 0,
            "pnl_created": 0,
            "trade_events_created": 0,
            "paper_trade_audits_created": 0,
        }

    # Step 3: E2Z creation for each candidate in the passed set
    candidate_ids: list[int] = (
        e2y_report.get("candidate_set_summary", {}).get("candidate_ids", [])
    )

    created_count = 0
    already_exists_count = 0
    blocked_count = 0
    window_results: list[dict[str, Any]] = []

    for wid in candidate_ids:
        result = create_clean_memory_from_window(
            db_path,
            wid,
            operator_approved=True,
            e2y_report=e2y_report,
        )
        status = result.get("e2z_status")
        if status == E2Z_STATUS_CREATED:
            created_count += 1
        elif status == E2Z_STATUS_ALREADY_EXISTS:
            already_exists_count += 1
        else:
            blocked_count += 1
        window_results.append({
            "window_id": wid,
            "e2z_status": status,
            "episode_id": result.get("episode_id"),
        })

    after = _snapshot_counts(db_path_str)

    return {
        "lane_k_status": LANE_K_STATUS_COMPLETED,
        "lane": LANE_K_NAME,
        "operator_approved": True,
        "db_path": db_path_str,
        "blocked_reasons": [],
        "e2x_status": e2x_status,
        "e2y_status": e2y_status,
        "e2y_set_gate_passed": True,
        "e2z_created_count": created_count,
        "e2z_already_exists_count": already_exists_count,
        "e2z_blocked_count": blocked_count,
        "clean_memory_rows_created": created_count,
        "candidate_window_ids": candidate_ids,
        "zero_clean_memories_valid": True,
        "hard_locks": dict(_HARD_LOCKS),
        "locked_capabilities": dict(_LOCKED_CAPABILITIES),
        "db_delta_summary": _delta_summary(before, after),
        "recommended_next_action": _RECOMMENDED_NEXT_ACTION,
        "e2z_window_results": window_results,
        "retrieval_activated": False,
        "paper_decisions_created": 0,
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "positions_created": 0,
        "pnl_created": 0,
        "trade_events_created": 0,
        "paper_trade_audits_created": 0,
    }

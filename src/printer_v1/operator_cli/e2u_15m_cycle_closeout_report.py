"""E2U Bounded 15m Cycle Report / Memory Factory Readiness Closeout.

Read-only report. No DB mutations. No memory creation. No retrieval activation.
No paper decisions, positions, trade events, trade audits, or PnL.
No BUY/SELL/HOLD unlock. No 5m main outcome window.

All queries are SELECT-only. Row counts are verified before and after to
prove zero delta (read-only contract). Opening a true read-only SQLite
connection (uri mode) is used where supported; the delta guard backs it up.

Permanent hard locks (all enforced here):
- no_buy_sell_hold
- no_paper_decisions
- no_positions
- no_pnl
- no_memory_creation (PARTIAL_MEMORY is NOT clean memory)
- no_retrieval_activation
- no_live_trading
- no_paid_api
- no_generic_search
- no_5m_main_window
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


E2U_COMMAND_NAME: str = "printer-report-e2u-15m-cycle-closeout"
E2U_STATUS_READY: str = "E2U_REPORT_READY"
E2U_STATUS_BLOCKED: str = "E2U_BLOCKED"

_LAST_N: int = 5

_LOCKED_STATE: dict[str, bool] = {
    "buy_unlock": False,
    "sell_unlock": False,
    "hold_unlock": False,
    "paper_positions_unlock": False,
    "pnl_unlock": False,
    "live_execution": False,
    "wallet_private_key": False,
    "paid_api_dependency": False,
}

_HARD_LOCKS: dict[str, bool] = {
    "no_buy_sell_hold": True,
    "no_paper_decisions": True,
    "no_positions": True,
    "no_pnl": True,
    "no_memory_creation": True,
    "no_retrieval_activation": True,
    "no_live_trading": True,
    "no_paid_api": True,
    "no_generic_search": True,
    "no_5m_main_window": True,
}


def _connect_ro(db_path: str | Path) -> sqlite3.Connection:
    """Open DB read-only via SQLite URI mode. Falls back to normal connect."""
    try:
        uri = Path(db_path).resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn


def _safe_count(conn: sqlite3.Connection, table: str) -> int | str:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.OperationalError:
        return "table_absent"


def _safe_ids(conn: sqlite3.Connection, table: str, n: int = _LAST_N) -> list[int]:
    try:
        rows = conn.execute(
            f"SELECT id FROM {table} ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        return [int(r["id"]) for r in reversed(rows)]
    except sqlite3.OperationalError:
        return []


def _last_five_window_15m(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT id, token_id, pair_id, window_kind, window_status,
                   memory_status, data_quality_label, memory_quality_label,
                   supporting_context_json, opened_at, closed_at
            FROM printer_memory_windows
            WHERE window_kind = 'WINDOW_15M'
            ORDER BY id DESC
            LIMIT ?
            """,
            (_LAST_N,),
        ).fetchall()
        result = []
        for r in reversed(rows):
            ctx: dict = {}
            try:
                ctx = json.loads(r["supporting_context_json"] or "{}")
            except (json.JSONDecodeError, TypeError):
                pass
            result.append({
                "id": int(r["id"]),
                "token_id": r["token_id"],
                "pair_id": r["pair_id"],
                "window_kind": r["window_kind"],
                "window_status": r["window_status"],
                "memory_status": r["memory_status"],
                "data_quality_label": r["data_quality_label"],
                "memory_quality_label": r["memory_quality_label"],
                "e2q_audited": bool(ctx.get("e2q_audited", False)),
                "snapshot_id": ctx.get("snapshot_id"),
                "opened_at": r["opened_at"],
                "closed_at": r["closed_at"],
            })
        return result
    except sqlite3.OperationalError:
        return []


def _count_table_snapshot(conn: sqlite3.Connection) -> dict[str, int | str]:
    tables = [
        "printer_scheduler_jobs",
        "printer_source_requests",
        "printer_source_responses",
        "printer_source_failures",
        "printer_token_snapshots",
        "printer_memory_windows",
        "printer_memories",
        "printer_paper_decisions",
        "printer_paper_positions",
        "printer_paper_trade_events",
        "printer_paper_trade_audits",
    ]
    return {t: _safe_count(conn, t) for t in tables}


def build_e2u_closeout_report(
    db_path: str | Path | None,
    *,
    operator_approved: bool = False,
) -> dict[str, Any]:
    """Build the E2U bounded 15m cycle closeout report.

    Read-only. No DB mutations. All operations are SELECT-only.
    Returns a structured summary dict. Does NOT commit.
    """
    blocked_reasons: list[str] = []

    if not operator_approved:
        blocked_reasons.append(
            "operator_approved must be True to run E2U closeout report"
        )

    db_path_str: str = ""
    if db_path is None:
        blocked_reasons.append("db_path is required")
    else:
        p = Path(db_path)
        db_path_str = str(p)
        if not p.is_file():
            blocked_reasons.append(f"db_path not found: {db_path}")

    if blocked_reasons:
        return {
            "command": E2U_COMMAND_NAME,
            "e2u_status": E2U_STATUS_BLOCKED,
            "operator_approved": operator_approved,
            "db_path": db_path_str,
            "blocked_reasons": blocked_reasons,
            "locked_state": dict(_LOCKED_STATE),
            "hard_locks": dict(_HARD_LOCKS),
            "readiness_flags": {
                "repeatable_15m_windows_ready": False,
                "bounded_operator_cycle_ready": False,
                "memory_creation_ready": False,
                "retrieval_ready": False,
                "paper_decision_ready": False,
                "buy_ready": False,
                "position_ready": False,
            },
        }

    conn = _connect_ro(db_path)
    try:
        # Snapshot counts before queries (delta guard).
        counts_before = _count_table_snapshot(conn)

        latest_jobs = _safe_ids(conn, "printer_scheduler_jobs")
        latest_source_requests = _safe_ids(conn, "printer_source_requests")
        latest_source_responses = _safe_ids(conn, "printer_source_responses")
        latest_snapshots = _safe_ids(conn, "printer_token_snapshots")
        latest_memory_windows = _safe_ids(conn, "printer_memory_windows")
        last_five_15m_windows = _last_five_window_15m(conn)

        # Window counts.
        closed_15m_count: int = 0
        e2q_audited_count: int = 0
        clean_data_count: int = 0
        partial_memory_count: int = 0
        try:
            closed_15m_count = int(conn.execute(
                "SELECT COUNT(*) FROM printer_memory_windows"
                " WHERE window_kind = 'WINDOW_15M' AND window_status = 'WINDOW_CLOSED'"
            ).fetchone()[0])

            e2q_audited_count = int(conn.execute(
                "SELECT COUNT(*) FROM printer_memory_windows"
                " WHERE window_kind = 'WINDOW_15M'"
                "   AND memory_quality_label IS NOT NULL"
            ).fetchone()[0])

            clean_data_count = int(conn.execute(
                "SELECT COUNT(*) FROM printer_memory_windows"
                " WHERE window_kind = 'WINDOW_15M'"
                "   AND data_quality_label = 'CLEAN_DATA'"
            ).fetchone()[0])

            partial_memory_count = int(conn.execute(
                "SELECT COUNT(*) FROM printer_memory_windows"
                " WHERE window_kind = 'WINDOW_15M'"
                "   AND memory_quality_label = 'PARTIAL_MEMORY'"
            ).fetchone()[0])
        except sqlite3.OperationalError:
            pass

        # printer_memories table (may not exist).
        clean_memory_count_raw = _safe_count(conn, "printer_memories")
        if isinstance(clean_memory_count_raw, str):
            clean_memory_count: int | str = "table_absent"
            retrieval_eligible_count: int | str = "not_active"
        else:
            clean_memory_count = int(clean_memory_count_raw)
            retrieval_eligible_count = 0

        running_jobs = 0
        active_locks = 0
        try:
            running_jobs = int(conn.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'RUNNING'"
            ).fetchone()[0])
            active_locks = int(conn.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs"
                " WHERE locked_at IS NOT NULL OR lock_owner IS NOT NULL"
            ).fetchone()[0])
        except sqlite3.OperationalError:
            pass

        # Snapshot counts after queries (delta guard).
        counts_after = _count_table_snapshot(conn)

    finally:
        conn.close()

    # Verify zero delta (proves read-only contract).
    delta_violations: list[str] = []
    for t, before_val in counts_before.items():
        after_val = counts_after.get(t)
        if isinstance(before_val, int) and isinstance(after_val, int):
            if after_val != before_val:
                delta_violations.append(
                    f"{t}: before={before_val} after={after_val} DELTA={after_val - before_val}"
                )

    repeatable_15m_proof = closed_15m_count >= 2
    has_true_clean_memory = (
        isinstance(clean_memory_count, int) and clean_memory_count > 0
    )

    readiness_flags = {
        "repeatable_15m_windows_ready": repeatable_15m_proof,
        "bounded_operator_cycle_ready": True,
        "memory_creation_ready": False,
        "retrieval_ready": False,
        "paper_decision_ready": False,
        "buy_ready": False,
        "position_ready": False,
    }

    notes: list[str] = [
        "PARTIAL_MEMORY windows exist and are evidence-eligible but are NOT clean memory.",
        "Zero clean memories is valid — the memory creation lane has not run yet.",
        "Paper decisions and BUY remain locked.",
        "5m window is not active; it remains support-only for the next lane.",
        "Retrieval is not active; no approved retrieval lane exists yet.",
    ]
    if has_true_clean_memory:
        notes.append(
            f"WARNING: {clean_memory_count} printer_memories row(s) found."
            " Review before enabling retrieval."
        )

    return {
        "command": E2U_COMMAND_NAME,
        "e2u_status": E2U_STATUS_READY,
        "operator_approved": operator_approved,
        "db_path": db_path_str,

        # Evidence IDs
        "latest_job_ids": latest_jobs,
        "latest_source_request_ids": latest_source_requests,
        "latest_source_response_ids": latest_source_responses,
        "latest_snapshot_ids": latest_snapshots,
        "latest_memory_window_ids": latest_memory_windows,
        "last_five_window_15m": last_five_15m_windows,

        # Counts
        "table_counts": counts_after,
        "closed_window_15m_count": closed_15m_count,
        "e2q_audited_window_count": e2q_audited_count,
        "clean_data_window_count": clean_data_count,
        "partial_memory_window_count": partial_memory_count,
        "clean_memory_count": clean_memory_count,
        "retrieval_eligible_count": retrieval_eligible_count,

        # State
        "running_jobs": running_jobs,
        "active_locks": active_locks,
        "repeatable_15m_window_proof": repeatable_15m_proof,

        # Readiness
        "readiness_flags": readiness_flags,
        "locked_state": dict(_LOCKED_STATE),
        "hard_locks": dict(_HARD_LOCKS),
        "notes": notes,
        "read_only_delta_violations": delta_violations,

        "next_recommended_lane": (
            "operator decision required:"
            " next lane pending operator review of memory creation boundary"
        ),

        # Explicit false flags for safety
        "paper_decisions_created": 0,
        "positions_created": 0,
        "pnl_created": 0,
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
    }

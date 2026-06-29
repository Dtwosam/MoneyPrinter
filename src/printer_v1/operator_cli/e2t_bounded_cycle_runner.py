"""E2T Bounded Integrated 15m Operator Cycle Runner.

Runs the existing E2J integrated first-15m cycle a bounded number of times
under strict operator control.

Execution contract (per cycle):
  E2J -> E2M (snapshot) -> E2O (window close) -> E2Q (audit/classify) -> done.

Hard rules:
- Operator approval required.
- Token list path, backup proof path, db path all required.
- max_cycles must be 1..E2T_MAX_CYCLES_HARD_CAP (default E2T_DEFAULT_MAX_CYCLES).
- No unbounded loop. No daemon/background/autonomous mode.
- No scheduler bypass.
- Stop immediately on failed/blocked cycle.
- Stop before a cycle if running_jobs or active_locks are present.
- No sleep between cycles (no spacing in this version).
- No memory rows created.
- No retrieval activation.
- No paper decisions, positions, PnL, trade events, paper audits.
- No BUY/SELL/HOLD.
- No 5m main outcome window.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


E2T_DEFAULT_MAX_CYCLES: int = 1
E2T_MAX_CYCLES_HARD_CAP: int = 3
E2T_COMMAND_NAME: str = "printer-run-e2t-bounded-cycle"

E2T_STATUS_COMPLETED: str = "E2T_COMPLETED"
E2T_STATUS_BLOCKED: str = "E2T_BLOCKED"
E2T_STATUS_STOPPED: str = "E2T_STOPPED"

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
    "no_unbounded_loop": True,
    "no_daemon_mode": True,
    "no_scheduler_bypass": True,
}


def _count_running_jobs(db_path: str | Path) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'RUNNING'"
            ).fetchone()[0]
        )
    except Exception:
        return 0
    finally:
        conn.close()


def _count_active_locks(db_path: str | Path) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs"
                " WHERE locked_at IS NOT NULL OR lock_owner IS NOT NULL"
            ).fetchone()[0]
        )
    except Exception:
        return 0
    finally:
        conn.close()


def _extract_source_ids(cycle_result: dict[str, Any]) -> tuple[int | None, int | None]:
    """Pull the first dexscreener source_request_id / source_response_id."""
    for sr in cycle_result.get("handler_result", {}).get("source_results", []):
        if sr.get("source_name") == "dexscreener":
            return sr.get("source_request_id"), sr.get("source_response_id")
    return None, None


def run_bounded_15m_cycles(
    token_list_path: str | Path | None,
    db_path: str | Path | None,
    backup_proof_path: str | Path | None,
    *,
    operator_approved: bool = False,
    max_cycles: int = E2T_DEFAULT_MAX_CYCLES,
    _adapter: Any = None,
) -> dict[str, Any]:
    """Run the E2J integrated 15m cycle up to max_cycles times.

    Returns a summary payload. Never commits or tags. Does not touch data/.
    Caller is responsible for any final commit/tag decisions.
    """
    from printer_v1.operator_cli.e2j_first_15m_cycle import (
        E2J_STATUS_EXECUTED,
        build_e2j_first_15m_cycle_payload,
    )

    blocked_reasons: list[str] = []

    if not operator_approved:
        blocked_reasons.append(
            "operator_approved must be True to run E2T bounded cycle"
        )

    if db_path is None:
        blocked_reasons.append("db_path is required")
    elif not Path(db_path).is_file():
        blocked_reasons.append(f"db_path not found: {db_path}")

    if backup_proof_path is None:
        blocked_reasons.append("backup_proof_path is required")
    elif not Path(backup_proof_path).is_file():
        blocked_reasons.append(f"backup_proof_path not found: {backup_proof_path}")

    if token_list_path is None:
        blocked_reasons.append("token_list_path is required")
    elif not Path(token_list_path).is_file():
        blocked_reasons.append(f"token_list_path not found: {token_list_path}")

    if not isinstance(max_cycles, int) or max_cycles < 1:
        blocked_reasons.append(
            f"max_cycles must be a positive integer >= 1; got {max_cycles!r}"
        )
    elif max_cycles > E2T_MAX_CYCLES_HARD_CAP:
        blocked_reasons.append(
            f"max_cycles {max_cycles} exceeds hard cap {E2T_MAX_CYCLES_HARD_CAP}"
        )

    if blocked_reasons:
        return {
            "command": E2T_COMMAND_NAME,
            "bounded_cycle_status": E2T_STATUS_BLOCKED,
            "requested_cycle_count": max_cycles,
            "completed_cycle_count": 0,
            "stopped_reason": "; ".join(blocked_reasons),
            "blocked_reasons": blocked_reasons,
            "cycles": [],
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "buy_enabled": False,
            "sell_enabled": False,
            "hold_enabled": False,
        }

    # Pre-cycle: ensure no running jobs or active locks exist.
    running = _count_running_jobs(db_path)
    if running:
        return {
            "command": E2T_COMMAND_NAME,
            "bounded_cycle_status": E2T_STATUS_BLOCKED,
            "requested_cycle_count": max_cycles,
            "completed_cycle_count": 0,
            "stopped_reason": (
                f"pre-cycle check: {running} RUNNING job(s) already exist"
            ),
            "blocked_reasons": [
                f"{running} RUNNING job(s) found before first cycle"
            ],
            "cycles": [],
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "buy_enabled": False,
            "sell_enabled": False,
            "hold_enabled": False,
        }

    locked = _count_active_locks(db_path)
    if locked:
        return {
            "command": E2T_COMMAND_NAME,
            "bounded_cycle_status": E2T_STATUS_BLOCKED,
            "requested_cycle_count": max_cycles,
            "completed_cycle_count": 0,
            "stopped_reason": (
                f"pre-cycle check: {locked} active lock(s) already exist"
            ),
            "blocked_reasons": [
                f"{locked} active lock(s) found before first cycle"
            ],
            "cycles": [],
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "buy_enabled": False,
            "sell_enabled": False,
            "hold_enabled": False,
        }

    cycles: list[dict[str, Any]] = []
    completed = 0
    stopped_reason: str | None = None
    final_status = E2T_STATUS_COMPLETED

    for cycle_num in range(1, max_cycles + 1):
        cycle_result = build_e2j_first_15m_cycle_payload(
            token_list_path,
            db_path,
            backup_proof_path,
            operator_approved=True,
            _adapter=_adapter,
        )

        req_id, resp_id = _extract_source_ids(cycle_result)

        cycle_summary: dict[str, Any] = {
            "cycle_num": cycle_num,
            "e2j_status": cycle_result.get("e2j_status"),
            "cycle_status": cycle_result.get("cycle_status"),
            "executed": cycle_result.get("executed", False),
            "job_id": cycle_result.get("job_id"),
            "source_request_id": req_id,
            "source_response_id": resp_id,
            "snapshot_persistence_status": cycle_result.get("snapshot_persistence_status"),
            "snapshot_id": cycle_result.get("snapshot_id"),
            "memory_window_close_status": cycle_result.get("memory_window_close_status"),
            "memory_window_id": cycle_result.get("memory_window_id"),
            "memory_window_audit_status": cycle_result.get("memory_window_audit_status"),
            "memory_quality_label": cycle_result.get("memory_quality_label"),
            "memory_window_audit_row_updated": cycle_result.get("memory_window_audit_row_updated"),
            "deltas": cycle_result.get("deltas", {}),
            "exec_error": cycle_result.get("exec_error"),
            "blocked_reasons": cycle_result.get("blocked_reasons", []),
        }
        cycles.append(cycle_summary)

        if cycle_result.get("e2j_status") == E2J_STATUS_EXECUTED:
            completed += 1
        else:
            stopped_reason = (
                f"cycle {cycle_num} stopped: {cycle_result.get('cycle_status', 'UNKNOWN')}"
                + (
                    f" — {cycle_result.get('exec_error', '')}"
                    if cycle_result.get("exec_error")
                    else ""
                )
            )
            final_status = E2T_STATUS_STOPPED
            break

    if final_status == E2T_STATUS_COMPLETED and stopped_reason is None:
        stopped_reason = f"all {completed} cycle(s) completed successfully"

    return {
        "command": E2T_COMMAND_NAME,
        "bounded_cycle_status": final_status,
        "requested_cycle_count": max_cycles,
        "completed_cycle_count": completed,
        "stopped_reason": stopped_reason,
        "cycles": cycles,
        "hard_locks": dict(_HARD_LOCKS),
        "paper_decisions_created": 0,
        "positions_created": 0,
        "pnl_created": 0,
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
    }

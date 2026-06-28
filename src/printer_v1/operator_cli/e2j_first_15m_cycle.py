"""E2J First Bounded 15m Cycle Operator Execution.

Lane E2J executes the first real bounded TRACK_FAST_FIRST_15M cycle through
the Central Scheduler and Source Governor. This is the actual execution lane,
not a planning gate. Operator approval is required.

Execution order:
1. Gate checks: operator_approved, db_path, backup_proof_path, token list (1 token)
2. E2G boundary gate: must return OPERATOR_RUN_READY
3. Record before DB row counts (audit tables)
4. Create TRACK_FAST_FIRST_15M scheduler job
5. Claim job (RUNNING, lock_owner=lane_e2j)
6. Build token-specific DexScreener adapter (from E2I, approved mint only)
7. Call E2H handler: execute_track_fast_first_15m_job(connection, job, adapter=adapter)
   -- handler gates: transport, no other running jobs, no other locks, Source Governor,
      no forbidden table mutations
   -- source call via governed transport: one DexScreener token endpoint request
8. Complete job (SUCCEEDED) or fail it (FAILED/HANDLER_BLOCKED)
9. Commit
10. Record after counts, compute deltas, check forbidden violations, audit post-run state
11. Return full audit payload

Security constraints (permanent):
- one token only, TRACK_FAST only, WINDOW_15M main target, 5m support-only
- Source Governor only, Central Scheduler only
- token-specific DexScreener transport only; generic search forbidden
- no BUY/SELL/HOLD, no paper decisions, no positions, no PnL
- no wallet/private keys/signing/live trading/real funds
- no paid APIs
- zero clean memories is valid
- do not commit, do not tag, do not stage data/
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


E2J_CYCLE_JOB_KIND: str = "TRACK_FAST_FIRST_15M"
E2J_LOCK_OWNER: str = "lane_e2j_first_15m_cycle"
E2J_JOB_NAME: str = "track_fast_first_15m_e2j_cycle"
E2J_STATUS_EXECUTED: str = "E2J_FIRST_15M_CYCLE_EXECUTED"
E2J_STATUS_BLOCKED: str = "E2J_FIRST_15M_CYCLE_BLOCKED"

_AUDIT_TABLES: tuple[str, ...] = (
    "printer_source_requests",
    "printer_source_responses",
    "printer_source_failures",
    "printer_scheduler_jobs",
    "printer_token_snapshots",
    "printer_memory_windows",
    "printer_memories",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
)

_FORBIDDEN_DELTA_TABLES: tuple[str, ...] = (
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
)

_HARD_LOCKS: dict[str, bool] = {
    "no_buy_sell_hold": True,
    "no_paper_decisions": True,
    "no_positions": True,
    "no_pnl": True,
    "no_live_trading": True,
    "no_paid_api": True,
    "no_generic_search": True,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _count_table_rows(db_path: str | Path, table: str) -> int | str:
    conn = sqlite3.connect(str(db_path))
    try:
        count = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return count
    except Exception as exc:
        return f"error:{exc}"
    finally:
        conn.close()


def _get_audit_counts(db_path: str | Path) -> dict[str, int | str]:
    return {t: _count_table_rows(db_path, t) for t in _AUDIT_TABLES}


def _check_forbidden_deltas(
    before: dict[str, int | str],
    after: dict[str, int | str],
) -> list[str]:
    violations: list[str] = []
    for t in _FORBIDDEN_DELTA_TABLES:
        b = before.get(t, 0)
        a = after.get(t, 0)
        if not isinstance(b, int) or not isinstance(a, int):
            continue
        if a > b:
            violations.append(f"{t}: +{a - b} unexpected row(s)")
    return violations


def _create_e2j_scheduler_job(connection: sqlite3.Connection) -> int:
    running = int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'RUNNING'"
        ).fetchone()[0]
    )
    if running:
        raise ValueError(
            f"E2J: {running} RUNNING job(s) already exist;"
            " cannot create TRACK_FAST_FIRST_15M job while another job is active"
        )
    now = _utc_now()
    cursor = connection.execute(
        """
        INSERT INTO printer_scheduler_jobs (
            job_name, job_kind, target_table, target_id, priority,
            status, scheduled_for, created_at, updated_at
        )
        VALUES (?, ?, NULL, NULL, 5, 'PENDING', ?, ?, ?)
        """,
        (E2J_JOB_NAME, E2J_CYCLE_JOB_KIND, now, now, now),
    )
    return int(cursor.lastrowid)


def _claim_e2j_job(connection: sqlite3.Connection, job_id: int) -> bool:
    now = _utc_now()
    cursor = connection.execute(
        """
        UPDATE printer_scheduler_jobs
        SET status = 'RUNNING',
            lock_owner = ?,
            locked_at = ?,
            started_at = ?,
            updated_at = ?
        WHERE id = ?
          AND status = 'PENDING'
        """,
        (E2J_LOCK_OWNER, now, now, now, job_id),
    )
    return int(cursor.rowcount) == 1


def _complete_e2j_job(connection: sqlite3.Connection, job_id: int) -> None:
    now = _utc_now()
    connection.execute(
        """
        UPDATE printer_scheduler_jobs
        SET status = 'SUCCEEDED',
            finished_at = ?,
            locked_at = NULL,
            lock_owner = NULL,
            last_error = NULL,
            updated_at = ?
        WHERE id = ?
        """,
        (now, now, job_id),
    )


def _fail_e2j_job(connection: sqlite3.Connection, job_id: int, error: str) -> None:
    now = _utc_now()
    connection.execute(
        """
        UPDATE printer_scheduler_jobs
        SET status = 'FAILED',
            finished_at = ?,
            locked_at = NULL,
            lock_owner = NULL,
            retry_count = retry_count + 1,
            last_error = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (now, error[:500], now, job_id),
    )


def _load_job_row(
    connection: sqlite3.Connection, job_id: int
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM printer_scheduler_jobs WHERE id = ?", (job_id,)
    ).fetchone()


def _get_post_run_state(db_path: str | Path) -> dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        running = int(
            conn.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'RUNNING'"
            ).fetchone()[0]
        )
        locked = int(
            conn.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs"
                " WHERE locked_at IS NOT NULL OR lock_owner IS NOT NULL"
            ).fetchone()[0]
        )
        return {
            "running_jobs": running,
            "active_locks": locked,
            "locks_cleared": locked == 0,
            "no_running_jobs": running == 0,
        }
    except Exception as exc:
        return {"error": str(exc), "locks_cleared": False, "no_running_jobs": False}
    finally:
        conn.close()


def build_e2j_first_15m_cycle_payload(
    token_list_path: str | Path | None,
    db_path: str | Path | None,
    backup_proof_path: str | Path | None,
    *,
    operator_approved: bool = False,
    _adapter: Any = None,
) -> dict[str, Any]:
    """Build the E2J first bounded 15m cycle execution payload.

    Runs TRACK_FAST_FIRST_15M through the Central Scheduler and Source Governor
    only if all E2G boundary gates pass. Creates a scheduler job, claims it,
    injects the real token-specific DexScreener adapter (from E2I), executes the
    E2H runtime handler, records source request/response/failure, and audits
    all table deltas and forbidden violations.

    Does NOT create paper decisions, positions, PnL, or BUY/SELL/HOLD rows.
    Does NOT use generic search. One token only.
    """
    from printer_v1.operator_cli.e2g_operator_run import (
        OPERATOR_RUN_READY,
        build_e2g_operator_run_payload,
    )
    from printer_v1.operator_cli.e2i_source_transport import (
        _load_and_validate_token_list,
        build_e2i_dexscreener_adapter,
    )
    from printer_v1.operator_cli.e2h_runtime_handler import (
        execute_track_fast_first_15m_job,
    )

    blocked_reasons: list[str] = []

    if not operator_approved:
        blocked_reasons.append("operator_approved must be True to run E2J first cycle")

    db_path_ok = False
    if db_path is None:
        blocked_reasons.append("db_path is required")
    else:
        db_path_ok = Path(db_path).is_file()
        if not db_path_ok:
            blocked_reasons.append(f"db_path not found: {db_path}")

    backup_proof_ok = False
    if backup_proof_path is None:
        blocked_reasons.append("backup_proof_path is required")
    else:
        backup_proof_ok = Path(backup_proof_path).is_file()
        if not backup_proof_ok:
            blocked_reasons.append(f"backup_proof_path not found: {backup_proof_path}")

    token_list_valid = False
    token_list_reason = "not checked"
    approved_mint = ""
    if token_list_path is None:
        blocked_reasons.append("token_list_path is required")
    else:
        token_list_valid, token_list_reason, _tokens, approved_mint = (
            _load_and_validate_token_list(token_list_path)
        )
        if not token_list_valid:
            blocked_reasons.append(f"token_list invalid: {token_list_reason}")

    e2g_status_val = "NOT_CHECKED"
    e2g_payload: dict[str, Any] = {}
    if not blocked_reasons:
        e2g_payload = build_e2g_operator_run_payload(
            token_list_path,
            db_path,
            approval_confirmed=True,
            backup_confirmed=True,
            backup_proof_path=backup_proof_path,
        )
        e2g_status_val = e2g_payload.get("first_run_status", "UNKNOWN")
        if e2g_status_val != OPERATOR_RUN_READY:
            blocked_reasons.append(f"E2G gate not ready: {e2g_status_val}")

    if blocked_reasons:
        return {
            "command": "printer-run-e2j-first-15m-cycle",
            "e2j_status": E2J_STATUS_BLOCKED,
            "executed": False,
            "blocked_reasons": blocked_reasons,
            "e2g_first_run_status": e2g_status_val,
            "approved_token_mint": approved_mint,
            "token_list_valid": token_list_valid,
            "token_list_reason": token_list_reason,
            "backup_proof_confirmed": backup_proof_ok,
            "operator_approved": operator_approved,
            "snapshot_persistence_status": "NOT_ATTEMPTED",
            "snapshot_id": None,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "buy_enabled": False,
            "sell_enabled": False,
            "hold_enabled": False,
        }

    before_counts = _get_audit_counts(db_path)

    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    job_id: int | None = None
    handler_result: dict[str, Any] = {}
    snapshot_result: dict[str, Any] = {}
    cycle_status = "UNKNOWN"
    exec_error: str | None = None
    snapshot_persistence_status: str = "NOT_ATTEMPTED"

    try:
        job_id = _create_e2j_scheduler_job(connection)
        connection.commit()

        claimed = _claim_e2j_job(connection, job_id)
        if not claimed:
            raise ValueError(
                "E2J: failed to claim TRACK_FAST_FIRST_15M job"
            )
        connection.commit()

        job_row = _load_job_row(connection, job_id)
        if job_row is None:
            raise ValueError(f"E2J: job {job_id} not found after claim")

        real_adapter = (
            _adapter
            if _adapter is not None
            else build_e2i_dexscreener_adapter(token_mint=approved_mint)
        )

        handler_result = execute_track_fast_first_15m_job(
            connection, job_row, adapter=real_adapter
        )

        if handler_result.get("executed", False):
            # Find a COMPLETE/CLEAN_DATA source response to persist as snapshot.
            source_response_id: int | None = None
            for sr in handler_result.get("source_results", []):
                if (
                    sr.get("source_name") == "dexscreener"
                    and sr.get("source_status") == "COMPLETE"
                    and sr.get("data_quality_label") == "CLEAN_DATA"
                    and sr.get("response_recorded")
                    and sr.get("source_response_id") is not None
                ):
                    source_response_id = int(sr["source_response_id"])
                    break

            if source_response_id is not None:
                from printer_v1.operator_cli.e2m_snapshot_persistence import (
                    E2M_STATUS_BLOCKED as _E2M_STATUS_BLOCKED,
                    persist_snapshot_from_source_response,
                )
                snapshot_result = persist_snapshot_from_source_response(
                    connection, source_response_id, approved_mint
                )
                snapshot_persistence_status = str(
                    snapshot_result.get("e2m_status", "UNKNOWN")
                )

                if snapshot_result.get("e2m_status") == _E2M_STATUS_BLOCKED:
                    blocked_reasons = snapshot_result.get(
                        "blocked_reasons", ["snapshot persistence blocked"]
                    )
                    reason = "E2M_BLOCKED: " + "; ".join(blocked_reasons)
                    _fail_e2j_job(connection, job_id, reason)
                    cycle_status = "E2M_BLOCKED"
                    exec_error = reason
                else:
                    # PERSISTED or DUPLICATE — both safe outcomes.
                    _complete_e2j_job(connection, job_id)
                    cycle_status = "SUCCEEDED"
            else:
                # No COMPLETE/CLEAN_DATA response with recorded ID (adapter=None,
                # or failure response) — source layer succeeded without snapshot.
                _complete_e2j_job(connection, job_id)
                cycle_status = "SUCCEEDED"
        else:
            reason = handler_result.get("blocked_reason") or "; ".join(
                handler_result.get("blocked_gates", ["handler blocked"])
            )
            _fail_e2j_job(connection, job_id, reason)
            cycle_status = "HANDLER_BLOCKED"
            exec_error = reason

        connection.commit()

    except Exception as exc:
        exec_error = str(exc)
        cycle_status = "EXCEPTION"
        if job_id is not None:
            try:
                _fail_e2j_job(connection, job_id, str(exc))
                connection.commit()
            except Exception:
                pass
    finally:
        connection.close()

    after_counts = _get_audit_counts(db_path)

    deltas: dict[str, int | str] = {}
    for t in _AUDIT_TABLES:
        b = before_counts.get(t)
        a = after_counts.get(t)
        if isinstance(b, int) and isinstance(a, int):
            deltas[t] = a - b
        else:
            deltas[t] = "unknown"

    forbidden_violations = _check_forbidden_deltas(before_counts, after_counts)
    post_run = _get_post_run_state(db_path)

    executed = cycle_status == "SUCCEEDED"

    return {
        "command": "printer-run-e2j-first-15m-cycle",
        "e2j_status": E2J_STATUS_EXECUTED if executed else E2J_STATUS_BLOCKED,
        "executed": executed,
        "cycle_status": cycle_status,
        "e2g_first_run_status": e2g_status_val,
        "approved_token_mint": approved_mint,
        "job_id": job_id,
        "handler_result": handler_result,
        "snapshot_persistence_status": snapshot_persistence_status,
        "snapshot_id": snapshot_result.get("snapshot_id"),
        "before_counts": before_counts,
        "after_counts": after_counts,
        "deltas": deltas,
        "forbidden_table_violations": forbidden_violations,
        "running_jobs_after": post_run.get("running_jobs", "error"),
        "active_locks_after": post_run.get("active_locks", "error"),
        "locks_cleared": post_run.get("locks_cleared", False),
        "no_running_jobs_after": post_run.get("no_running_jobs", False),
        "exec_error": exec_error,
        "operator_approved": operator_approved,
        "backup_proof_confirmed": backup_proof_ok,
        "token_list_valid": token_list_valid,
        "token_list_reason": token_list_reason,
        "hard_locks": dict(_HARD_LOCKS),
        "paper_decisions_created": 0,
        "positions_created": 0,
        "pnl_created": 0,
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
    }

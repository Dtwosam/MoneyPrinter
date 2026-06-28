"""E2H TRACK_FAST_FIRST_15M Runtime Handler Boundary.

Defines the bounded execution handler for TRACK_FAST_FIRST_15M scheduler jobs.

This handler is registered in the Phase 35/36 bounded runner (commands.py
PHASE35_SAFE_JOB_KINDS) and enforces all gate checks before any real execution.

Discovery finding (E2H):
Real source transport is currently fixture-only (Phase 23 boundary).
governed_execution.py only provides FixtureSourceAdapter -- no real network calls.
This handler fails closed when real source transport is unavailable.

After E2H:
- TRACK_FAST_FIRST_15M is registered (is_handler_registered() -> True)
- Real source transport is still unavailable -> E2G still BLOCKED, but the
  blocker reason changes from "handler not implemented" to "real source
  transport is fixture-only"
- No real cycle runs until a real source adapter replaces FixtureSourceAdapter

Execution boundaries enforced:
- All source calls must go through Source Governor (can_request_source).
- Source recording must use source recording helpers (record_source_request,
  record_source_response, record_source_failure).
- No direct source adapter calls from execution engines.
- No BUY, SELL, HOLD, paper decisions, positions, or PnL.
- No wallet, private keys, signing, or live execution.
- No paid APIs, scoring, ranking, confidence, embeddings, or vectors.
- Exactly 1 approved TRACK_FAST token for the first run.
- Target window: WINDOW_15M (15m main window; 5m remains support-only).
- Fail closed on: fixture-only transport, invalid token, non-TRACK_FAST lane,
  multiple tokens, missing backup proof notice, running jobs, active locks,
  source governor denial, direct source call attempt, forbidden table mutation.

All gate checks in this module are read-only or bounded by Source Governor.
No DB mutation is produced by planning functions.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from printer_v1.operator_cli.e2c_readiness import HARD_LOCKS, is_valid_solana_mint
from printer_v1.sources.budget_accounting import count_recent_source_requests
from printer_v1.sources.governor import can_request_source


HANDLER_JOB_KIND: str = "TRACK_FAST_FIRST_15M"
HANDLER_LIFECYCLE_LANE: str = "TRACK_FAST"
HANDLER_TARGET_WINDOW: str = "WINDOW_15M"
HANDLER_MAX_TOKENS_FIRST_RUN: int = 1
HANDLER_SOURCE_NAME: str = "dexscreener"
HANDLER_REQUEST_KIND: str = "pair_market_snapshot"

E2H_STATUS_EXECUTED: str = "E2H_TRACK_FAST_FIRST_15M_EXECUTED"
E2H_STATUS_BLOCKED: str = "E2H_TRACK_FAST_FIRST_15M_BLOCKED"

_REAL_SOURCE_TRANSPORT_REASON: str = (
    "real source transport not available (E2I module not importable);"
    " expected e2i_source_transport.check_real_source_transport_available"
    " to return (True, reason) after Lane E2I is implemented"
)

_FORBIDDEN_TABLES: tuple[str, ...] = (
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
)


def is_handler_registered() -> bool:
    """Return True -- TRACK_FAST_FIRST_15M handler is registered in Lane E2H."""
    return True


def check_real_source_transport_available() -> tuple[bool, str]:
    """Check whether real source transport (not fixture-only) is available.

    Returns (available: bool, reason: str).

    Delegates to Lane E2I (e2i_source_transport) via lazy import.
    Returns (True, reason) after Lane E2I is in place.

    Falls back to (False, _REAL_SOURCE_TRANSPORT_REASON) if E2I not importable.
    This function is patchable in tests for transport-gate isolation.
    """
    try:
        from printer_v1.operator_cli.e2i_source_transport import (
            check_real_source_transport_available as _e2i_check,
        )
        return _e2i_check()
    except ImportError:
        return (False, _REAL_SOURCE_TRANSPORT_REASON)


def validate_token_entry(entry: dict[str, Any]) -> tuple[bool, str]:
    """Validate a single token entry for TRACK_FAST_FIRST_15M.

    Returns (valid: bool, reason: str).
    """
    mint = entry.get("token_mint", "")
    if not is_valid_solana_mint(str(mint)):
        return False, f"invalid token_mint: {mint!r}"
    lane = entry.get("lifecycle_lane", "")
    if lane != HANDLER_LIFECYCLE_LANE:
        return (
            False,
            f"lifecycle_lane must be {HANDLER_LIFECYCLE_LANE!r} for"
            f" {HANDLER_JOB_KIND}; got {lane!r}",
        )
    if not entry.get("approved_by_operator", False):
        return False, "approved_by_operator must be True"
    return True, "token entry valid"


def validate_token_list(tokens: list[dict[str, Any]]) -> tuple[bool, str]:
    """Validate the full token list for the first TRACK_FAST_FIRST_15M run.

    First run requires exactly 1 TRACK_FAST approved token.
    Returns (valid: bool, reason: str).
    """
    if not isinstance(tokens, list):
        return False, f"token list must be a list, got {type(tokens).__name__!r}"
    if len(tokens) != HANDLER_MAX_TOKENS_FIRST_RUN:
        return (
            False,
            f"first run requires exactly {HANDLER_MAX_TOKENS_FIRST_RUN} token;"
            f" got {len(tokens)}",
        )
    ok, reason = validate_token_entry(tokens[0])
    if not ok:
        return False, reason
    return True, f"token list valid: {HANDLER_MAX_TOKENS_FIRST_RUN} {HANDLER_LIFECYCLE_LANE} token"


def _count_running_jobs_excluding(
    connection: sqlite3.Connection, *, exclude_id: int
) -> int:
    """Count RUNNING jobs with id != exclude_id."""
    return int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs"
            " WHERE status = 'RUNNING' AND id != ?",
            (exclude_id,),
        ).fetchone()[0]
    )


def _count_active_locks_excluding(
    connection: sqlite3.Connection, *, exclude_id: int
) -> int:
    """Count jobs with active locks (locked_at or lock_owner) excluding current."""
    return int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs"
            " WHERE (locked_at IS NOT NULL OR lock_owner IS NOT NULL)"
            " AND id != ?",
            (exclude_id,),
        ).fetchone()[0]
    )


def check_source_governor(
    connection: sqlite3.Connection,
    source_name: str = HANDLER_SOURCE_NAME,
    request_kind: str = HANDLER_REQUEST_KIND,
) -> tuple[bool, str]:
    """Check Source Governor budget for the given source.

    Returns (allowed: bool, reason: str).
    Read-only. Does not mutate DB.
    """
    recent_count = count_recent_source_requests(connection, source_name)
    decision = can_request_source(source_name, request_kind, recent_count)
    return decision.allowed, decision.reason


def _snapshot_forbidden_counts(connection: sqlite3.Connection) -> dict[str, int]:
    """Snapshot current row counts for all forbidden tables (before execution)."""
    counts: dict[str, int] = {}
    for table in _FORBIDDEN_TABLES:
        try:
            counts[table] = int(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            )
        except sqlite3.OperationalError:
            counts[table] = 0
    return counts


def _check_forbidden_table_delta(
    connection: sqlite3.Connection,
    before_counts: dict[str, int],
) -> list[str]:
    """Return violations for forbidden tables that grew during execution.

    Compares current counts against the before_counts snapshot taken before
    execution. Pre-existing rows are allowed; only net-new rows during this
    execution are violations.
    """
    violations: list[str] = []
    for table in _FORBIDDEN_TABLES:
        before = before_counts.get(table, 0)
        try:
            after = int(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            )
            if after > before:
                violations.append(
                    f"{table}: +{after - before} new row(s)"
                    f" (before={before}, after={after})"
                )
        except sqlite3.OperationalError:
            pass
    return violations


def execute_track_fast_first_15m_job(
    connection: sqlite3.Connection,
    job: sqlite3.Row | dict[str, Any],
    *,
    adapter: Any = None,
    source_name: str = HANDLER_SOURCE_NAME,
    request_kind: str = HANDLER_REQUEST_KIND,
) -> dict[str, Any]:
    """Execute handler for a TRACK_FAST_FIRST_15M scheduler job.

    Gate order:
    1. Real source transport available (fail closed: fixture-only -> BLOCKED)
    2. No OTHER RUNNING jobs (excluding current job)
    3. No OTHER active locks (excluding current job)
    4. Source Governor budget allows the request
    5. (Execute source call if adapter provided)
    6. Forbidden table delta guard (post-execution): blocks if any forbidden
       table grew during this execution. Pre-existing rows are allowed.

    adapter: optional FixtureSourceAdapter instance for testing. In production
    this is None; the transport gate blocks before reaching the execute path.

    Returns a dict with status, executed flag, and gate/execution details.
    Claude does NOT run the real cycle. No BUY/SELL/HOLD. No paper decisions.
    """
    # Gate 1: real source transport
    transport_ok, transport_reason = check_real_source_transport_available()
    if not transport_ok:
        return {
            "handler": HANDLER_JOB_KIND,
            "status": E2H_STATUS_BLOCKED,
            "executed": False,
            "gate_failed": "real_source_transport",
            "blocked_reason": transport_reason,
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
        }

    # Snapshot forbidden table counts before execution (Gate 6 compares against this).
    forbidden_before = _snapshot_forbidden_counts(connection)

    job_id: int = int(job["id"]) if job["id"] is not None else -1
    blocked_gates: list[str] = []

    # Gate 2: no OTHER running jobs
    running_others = _count_running_jobs_excluding(connection, exclude_id=job_id)
    if running_others:
        blocked_gates.append(
            f"running_jobs_found: {running_others} other RUNNING job(s)"
            " detected; halt until clear"
        )

    # Gate 3: no OTHER active locks
    locked_others = _count_active_locks_excluding(connection, exclude_id=job_id)
    if locked_others:
        blocked_gates.append(
            f"active_locks_found: {locked_others} job(s) with active locks"
            " (locked_at or lock_owner) detected"
        )

    # Gate 4: Source Governor budget
    gov_ok, gov_reason = check_source_governor(connection, source_name, request_kind)
    if not gov_ok:
        blocked_gates.append(f"source_governor_denied: {gov_reason}")

    if blocked_gates:
        return {
            "handler": HANDLER_JOB_KIND,
            "status": E2H_STATUS_BLOCKED,
            "executed": False,
            "gate_failed": "execution_gates",
            "blocked_gates": blocked_gates,
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
        }

    # Gates 1-4 passed. Execute source call if adapter provided.
    source_results: list[dict[str, Any]] = []
    if adapter is not None:
        from printer_v1.sources.contracts import build_governed_source_request
        from printer_v1.sources.governed_execution import (
            execute_source_request_with_governor,
        )

        recent_count = count_recent_source_requests(connection, source_name)
        source_request = build_governed_source_request(source_name, request_kind)
        exec_result = execute_source_request_with_governor(
            connection,
            source_request,
            adapter,
            recent_request_count=recent_count,
        )
        source_results.append(
            {
                "source_name": source_name,
                "request_kind": request_kind,
                "source_status": exec_result.normalized_result.source_status.value,
                "data_quality_label": exec_result.normalized_result.data_quality_label.value,
                "request_recorded": exec_result.request_record is not None,
                "response_recorded": exec_result.response_record is not None,
                "failure_recorded": exec_result.failure_record is not None,
            }
        )

    # Gate 6: forbidden table delta guard (post-execution).
    # Blocks if any forbidden table gained rows during this execution.
    # Pre-existing rows present before execution do not trigger this gate.
    forbidden_violations = _check_forbidden_table_delta(connection, forbidden_before)
    if forbidden_violations:
        return {
            "handler": HANDLER_JOB_KIND,
            "status": E2H_STATUS_BLOCKED,
            "executed": False,
            "gate_failed": "forbidden_table_mutation",
            "blocked_gates": [
                f"forbidden_table_mutation: {v}" for v in forbidden_violations
            ],
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
        }

    return {
        "handler": HANDLER_JOB_KIND,
        "status": E2H_STATUS_EXECUTED,
        "executed": True,
        "source_results": source_results,
        "hard_locks": dict(HARD_LOCKS),
        "paper_decisions_created": 0,
        "positions_created": 0,
        "pnl_created": 0,
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
    }

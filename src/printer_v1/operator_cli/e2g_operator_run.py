"""E2G First Bounded 15m Cycle Operator Run Boundary.

Wraps the E2F execution boundary and defines the final pre-run gate for the
first bounded source-governed 15m Memory Factory cycle.

Outputs OPERATOR_RUN_READY or BLOCKED.

OPERATOR_RUN_READY means all automated boundary gates have passed AND a real
TRACK_FAST_FIRST_15M runtime job handler is confirmed to exist. The operator
must then run the bounded execution command manually against the real DB after
committing and tagging Lane E2G.

IMPORTANT: This module does NOT run the real cycle. Claude did not run the real
cycle. The real cycle must be run manually by the operator after commit+tag.

Discovery finding (E2G): The real bounded 15m Memory Factory cycle runtime
path does NOT exist in the current build. The Phase 35/36 bounded runner only
handles BACKUP_SOURCE_CHECK jobs. TRACK_FAST_FIRST_15M is not handled.
This module outputs BLOCKED until a real handler is implemented.

Execution boundaries enforced:
- All source calls must go through Source Governor (can_request_source).
- All job scheduling must go through Central Scheduler job tables.
- No direct source adapter calls from execution engines.
- No BUY, SELL, HOLD, paper decisions, positions, or PnL.
- No wallet, private keys, signing, or live execution.
- No paid APIs, scoring, ranking, confidence, embeddings, or vectors.
- Max 1 approved token for the first run (E2G constraint).
- Target window: WINDOW_15M (15m main window only; 5m support-only).

All operations in this module are read-only planning. No source fetching. No
scheduler runtime. No persistent DB mutation. No snapshots, memory, context,
or paper decisions produced by this module.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from printer_v1.operator_cli.e2f_execution_boundary import (
    CYCLE_READY_TO_RUN,
    build_e2f_execution_boundary_payload,
)
from printer_v1.operator_cli.e2c_readiness import HARD_LOCKS


OPERATOR_RUN_READY: str = "OPERATOR_RUN_READY"
OPERATOR_RUN_BLOCKED: str = "BLOCKED"

E2G_STATUS_READY: str = "E2G_OPERATOR_RUN_READY"
E2G_STATUS_BLOCKED: str = "E2G_OPERATOR_RUN_BLOCKED"

# Exact CLI command the operator runs manually after E2G commit/tag.
# Inert text only. This does NOT execute. Claude did not run this.
_EXACT_OPERATOR_RUN_COMMAND: str = (
    "printer-run-e2g-first-bounded-15m-operator-run"
    " --token-list-path <PATH_TO_OPERATOR_APPROVED_TOKEN_LIST_JSON>"
    " --approval-confirmed"
    " --backup-confirmed"
    " --backup-proof-path <PATH_TO_BACKUP_FILE>"
    " --db-path <PATH_TO_DB>"
    " --format json"
    "\n\n"
    "NOTE: This is an inert text preview only. It does NOT execute the command."
    " The operator must run this command manually against the real DB after"
    " committing and tagging Lane E2G. Claude did not run this command."
    " This command will remain BLOCKED until a real TRACK_FAST_FIRST_15M"
    " runtime job handler is implemented in a future lane."
)

# Tables that may receive new rows when the real cycle runs manually.
# Planning documentation only -- nothing is written by this module.
_ALLOWED_TABLE_DELTAS: dict[str, str] = {
    "printer_source_requests": (
        "new rows for each source request governed by Source Governor"
    ),
    "printer_source_responses": "new rows for each governed source response",
    "printer_source_failures": "new rows only if a governed source call fails",
    "printer_scheduler_jobs": (
        "job rows managed by Central Scheduler boundaries only"
    ),
    "printer_token_snapshots": (
        "new rows only if source evidence is clean and quality gates pass"
    ),
    "printer_context_snapshots": (
        "new rows only if table exists and governed context collection runs"
    ),
    "printer_contexts": (
        "new rows only if table exists and context evidence passes existing gates"
    ),
    "printer_memory_windows": (
        "new row only if 15m evidence window closes with sufficient evidence"
    ),
    "printer_memories": (
        "new row only if all clean-memory quality gates pass"
        " (zero clean memories is a valid outcome)"
    ),
}

_FORBIDDEN_TABLE_DELTAS: list[str] = [
    "printer_paper_decisions -- paper decisions remain locked",
    "printer_paper_positions -- paper positions remain locked",
    "printer_paper_trade_events -- trade events remain locked",
    "printer_paper_trade_audits -- paper trade audits remain locked",
    "any BUY/SELL/HOLD decision rows -- remain locked",
]

_STOP_CONDITIONS: list[str] = [
    "E2F cycle_status is not CYCLE_READY_TO_RUN.",
    "TRACK_FAST_FIRST_15M runtime job handler is not implemented.",
    "Backup proof file does not exist at the provided path.",
    "approval_confirmed flag is not explicitly set.",
    "backup_confirmed flag is not explicitly set.",
    "DB backup file does not exist or backup was not confirmed.",
    "DB file does not exist at the expected path.",
    "Token list validation reports valid=false.",
    "Token count is not exactly 1 for first run (E2G constraint).",
    "approved_by_operator is false or missing for the token.",
    "Placeholder mint remains in the token list.",
    "Any source reports allowed=false from Source Governor.",
    "Any governor_decision is rate_limit_exceeded.",
    "Any row with status=RUNNING in printer_scheduler_jobs.",
    "Any row with locked_at IS NOT NULL in printer_scheduler_jobs.",
    "Any row with lock_owner set in printer_scheduler_jobs.",
    "Any hard-lock flag in hard_locks is true when it should be false.",
    "Any direct source adapter call outside Source Governor boundaries.",
    "Any job created outside Central Scheduler job table boundaries.",
    "Any row created in printer_paper_decisions.",
    "Any BUY, SELL, or HOLD decision row created.",
    "Any paper position, trade event, or PnL row created.",
    "Any wallet connection, private key reference, signing, or live execution.",
    "Any paid API dependency activated.",
    "Any scoring, ranking, confidence, or weighted logic triggered.",
    "Any embedding or vector path triggered.",
    "Any 5m window targeted as main window (5m remains support-only).",
    "Any table outside allowed_table_deltas receives new rows.",
]

_ROLLBACK_CHECKLIST: list[str] = [
    "[ ] Stop immediately if any unexpected row is outside allowed_table_deltas.",
    "[ ] Confirm backup file exists: Test-Path <backup_proof_path>",
    "[ ] Rename current DB to preserve state:"
    " Rename-Item data\\printer_v1.sqlite3 data\\printer_v1_unexpected_state_<ts>.sqlite3",
    "[ ] Copy backup to DB path:"
    " Copy-Item -Path <backup_proof_path> -Destination data\\printer_v1.sqlite3",
    "[ ] Confirm restore: Test-Path data\\printer_v1.sqlite3",
    "[ ] Rerun E2C-C preflight to confirm DB state is clean after restore.",
    "[ ] Review git status --short for unexpected changes.",
    "[ ] Review git log --oneline -10 for unexpected commits.",
    "[ ] Do not delete backup until lane is confirmed stable.",
    "[ ] Report any unexpected source calls, row creation, or errors.",
]

# Tables to count before the real run for mutation auditing.
_AUDIT_TABLES: tuple[str, ...] = (
    "printer_source_requests",
    "printer_source_responses",
    "printer_source_failures",
    "printer_scheduler_jobs",
    "printer_token_snapshots",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
)


def _check_15m_cycle_runtime_available() -> tuple[bool, str]:
    """Check if a real TRACK_FAST_FIRST_15M cycle runtime handler is implemented.

    Returns (available: bool, reason: str).

    Currently returns (False, reason) because the handler does not exist.
    Phase 35/36 bounded runner only handles BACKUP_SOURCE_CHECK jobs.
    TRACK_FAST_FIRST_15M is not in PHASE35_SAFE_JOB_KINDS.

    When a real handler is built in a future lane, update this function
    and the gate that depends on it.
    """
    return (
        False,
        (
            "TRACK_FAST_FIRST_15M runtime job handler not implemented;"
            " Phase 35/36 bounded runner only handles BACKUP_SOURCE_CHECK;"
            " a real 15m cycle handler must be built before this gate can pass"
        ),
    )


def _check_backup_proof(backup_proof_path: str | Path | None) -> tuple[bool, str]:
    """Return (exists, reason). Verifies backup proof file physically exists."""
    if backup_proof_path is None:
        return False, "backup_proof_path is None; operator must provide the backup file path"
    path = Path(backup_proof_path)
    if not path.is_file():
        return False, f"backup proof file does not exist: {path}"
    return True, f"backup proof file confirmed: {path}"


def _get_before_counts(db_path: str | Path) -> dict[str, int | str]:
    """Return row counts for audited tables. Returns error string if table missing."""
    counts: dict[str, int | str] = {}
    path = Path(db_path)
    if not path.is_file():
        return {"error": f"DB not found at {path}"}
    conn = sqlite3.connect(path)
    try:
        for table in _AUDIT_TABLES:
            try:
                row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                counts[table] = int(row[0])
            except sqlite3.OperationalError:
                counts[table] = "table_not_found"
    finally:
        conn.close()
    return counts


def _extract_token_count_from_e2f(e2f_payload: dict[str, Any]) -> int:
    """Extract token_count from the nested E2F payload chain."""
    return (
        e2f_payload
        .get("e2e_approval_packet", {})
        .get("e2d_decision", {})
        .get("e2c_f_review", {})
        .get("token_file_review", {})
        .get("token_count", 0)
    )


def _determine_run_status(
    e2f_payload: dict[str, Any],
    *,
    backup_proof_path: str | Path | None,
) -> tuple[str, list[str], str]:
    """Return (run_status, reasons, e2g_status).

    BLOCKED unless:
    - E2F cycle_status is CYCLE_READY_TO_RUN
    - backup proof file exists
    - TRACK_FAST_FIRST_15M runtime handler is available
    - Token count is exactly 1 (first-run constraint)

    Pure function (except for filesystem and _check_15m_cycle_runtime_available).
    """
    reasons: list[str] = []

    e2f_status = e2f_payload.get("cycle_status")
    if e2f_status != CYCLE_READY_TO_RUN:
        reasons.append(
            "E2F cycle_status is "
            + repr(e2f_status)
            + "; must be CYCLE_READY_TO_RUN"
        )
        for r in e2f_payload.get("cycle_status_reasons", []):
            reasons.append("  E2F reason: " + r)

    backup_ok, backup_msg = _check_backup_proof(backup_proof_path)
    if not backup_ok:
        reasons.append(backup_msg)

    runtime_ok, runtime_msg = _check_15m_cycle_runtime_available()
    if not runtime_ok:
        reasons.append(runtime_msg)

    token_count = _extract_token_count_from_e2f(e2f_payload)
    if token_count != 1:
        reasons.append(
            f"token_count is {token_count}; E2G first-run constraint requires exactly 1 token"
        )

    locks = e2f_payload.get("hard_locks", {})
    for key, val in locks.items():
        if val is not False:
            reasons.append(f"hard_locks[{key!r}] is not False: {val!r}")

    if reasons:
        return OPERATOR_RUN_BLOCKED, reasons, E2G_STATUS_BLOCKED

    return OPERATOR_RUN_READY, [
        "E2F cycle_status is CYCLE_READY_TO_RUN",
        "backup proof file exists and confirmed",
        "TRACK_FAST_FIRST_15M runtime handler is available",
        "token count is exactly 1 (E2G first-run constraint satisfied)",
        "all 11 hard-lock flags are False",
        "all Central Scheduler and Source Governor boundaries enforced",
        "zero clean memories is a valid first-run outcome",
        "OPERATOR_RUN_READY: operator must run the exact_operator_run_command"
        " manually against the real DB after committing and tagging Lane E2G",
        "OPERATOR_RUN_READY does NOT mean Claude ran the cycle",
        "BUY, SELL, HOLD, paper decisions, positions, and PnL remain locked",
        "5m remains support-only; WINDOW_15M is the first main target",
        "before_db_counts are included in this payload for post-run audit",
    ], E2G_STATUS_READY


def build_e2g_operator_run_payload(
    token_file_path: str | Path | None,
    db_path: str | Path | None,
    *,
    approval_confirmed: bool,
    backup_confirmed: bool,
    backup_proof_path: str | Path | None,
) -> dict[str, Any]:
    """Build the E2G operator run boundary payload.

    Calls E2F execution boundary, then applies E2G pre-run gates.

    This function is read-only planning. It does NOT run the real cycle.
    No source fetching. No scheduler execution. No persistent DB mutation.
    No snapshots, memory, context, or paper decisions produced here.
    """
    e2f_payload = build_e2f_execution_boundary_payload(
        token_file_path,
        db_path,
        approval_confirmed=approval_confirmed,
        backup_confirmed=backup_confirmed,
    )

    run_status, run_reasons, e2g_status = _determine_run_status(
        e2f_payload,
        backup_proof_path=backup_proof_path,
    )

    runtime_available, runtime_reason = _check_15m_cycle_runtime_available()
    backup_exists, backup_reason = _check_backup_proof(backup_proof_path)

    before_counts: dict[str, int | str] = {}
    if db_path is not None:
        db_p = Path(db_path)
        if db_p.is_file():
            before_counts = _get_before_counts(db_path)

    return {
        "command": "printer-run-e2g-first-bounded-15m-operator-run",
        "dry_run": True,
        "planning_only": True,
        "claude_did_not_run_cycle": True,
        "e2f_execution_boundary": e2f_payload,
        "first_run_status": run_status,
        "first_run_status_reasons": run_reasons,
        "e2g_status": e2g_status,
        "runtime_path_exists": runtime_available,
        "runtime_path_reason": runtime_reason,
        "backup_proof_confirmed": backup_exists,
        "backup_proof_reason": backup_reason,
        "before_db_counts": before_counts,
        "exact_operator_run_command": _EXACT_OPERATOR_RUN_COMMAND,
        "allowed_table_deltas": _ALLOWED_TABLE_DELTAS,
        "forbidden_table_deltas": _FORBIDDEN_TABLE_DELTAS,
        "stop_conditions": _STOP_CONDITIONS,
        "rollback_checklist": _ROLLBACK_CHECKLIST,
        "hard_locks": dict(HARD_LOCKS),
        "next_required_operator_action": (
            "Commit and tag Lane E2G. Then build the real TRACK_FAST_FIRST_15M"
            " runtime job handler (next lane). After the handler exists and is"
            " tested, rerun this command to confirm OPERATOR_RUN_READY."
            " Then run the exact_operator_run_command manually against the real DB."
            if run_status == OPERATOR_RUN_BLOCKED
            else "Commit and tag Lane E2G. Then run the exact_operator_run_command"
            " manually against the real DB. Do not run it without committing"
            " and tagging E2G first."
        ),
    }

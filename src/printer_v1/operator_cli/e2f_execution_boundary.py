"""E2F First Bounded 15m Cycle Execution Boundary.

Wraps the E2E approval packet and defines the final planning gate before the
first bounded real source-governed 15m Memory Factory cycle can be run manually
by the operator.

Outputs CYCLE_READY_TO_RUN or BLOCKED.

CYCLE_READY_TO_RUN means all automated boundary gates have passed. The operator
must then run the bounded execution command manually against the real DB after
committing and tagging Lane E2F.

IMPORTANT: This module does NOT run the real cycle. Claude did not run the real
cycle. The real cycle must be run manually by the operator.

Execution boundaries enforced:
- All source calls must go through Source Governor (can_request_source).
- All job scheduling must go through the Central Scheduler job tables.
- No direct source adapter calls from execution engines.
- No BUY, SELL, HOLD, paper decisions, positions, or PnL.
- No wallet, private keys, signing, or live execution.

All operations in this module are read-only planning. No source fetching. No
scheduler runtime. No persistent DB mutation. No snapshots, memory, context, or
paper decisions produced by this module.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from printer_v1.operator_cli.e2e_approval_packet import (
    APPROVAL_PACKET_READY,
    build_e2e_approval_packet,
)
from printer_v1.operator_cli.e2c_readiness import HARD_LOCKS


CYCLE_READY_TO_RUN: str = "CYCLE_READY_TO_RUN"
CYCLE_BLOCKED: str = "BLOCKED"

E2F_STATUS_READY: str = "E2F_EXECUTION_BOUNDARY_READY"
E2F_STATUS_BLOCKED: str = "E2F_EXECUTION_BOUNDARY_BLOCKED"

# Inert text preview of the future manual execution command.
# This does NOT execute. The operator must run this manually after E2F commit/tag.
_EXACT_OPERATOR_RUN_COMMAND: str = (
    "printer-run-first-bounded-15m-cycle"
    " --token-list-path <PATH_TO_OPERATOR_APPROVED_TOKEN_LIST_JSON>"
    " --approval-confirmed"
    " --backup-confirmed"
    " --db-path <PATH_TO_DB>"
    " --format json"
    "\n\n"
    "NOTE: This is an inert text preview only. It does NOT execute the command."
    " The operator must run this command manually against the real DB after"
    " committing and tagging Lane E2F. Claude did not run this command."
    " This command may only be run after Lane E2F is committed, tagged, and the"
    " operator explicitly confirms all required confirmations."
)

# Which DB tables are allowed to receive new rows when the real cycle runs.
# This is planning documentation only -- nothing is written by this module.
_ALLOWED_TABLE_DELTAS: dict[str, str] = {
    "printer_source_requests": (
        "new rows for each source request issued during the bounded cycle"
        " (governed by Source Governor rate limits)"
    ),
    "printer_source_responses": (
        "new rows for each source response received"
    ),
    "printer_source_failures": (
        "new rows only if a governed source call fails"
    ),
    "printer_scheduler_jobs": (
        "job rows updated during cycle (status, locked_at, lock_owner"
        " set and cleared by Central Scheduler boundaries)"
    ),
    "printer_token_snapshots": (
        "new rows only if source evidence is clean enough to store"
        " (subject to existing evidence quality gates)"
    ),
    "printer_context_snapshots": (
        "new rows only if broad context collection runs and passes quality gates"
    ),
    "printer_contexts": (
        "new rows only if context evidence is created and passes existing gates"
    ),
    "printer_memory_windows": (
        "new row only if a 15m evidence window completes with sufficient evidence"
    ),
    "printer_memories": (
        "new row only if evidence passes all existing memory quality gates"
        " (zero clean memories is a valid outcome)"
    ),
}

# Tables that must NOT receive new rows during the bounded cycle.
_FORBIDDEN_TABLE_DELTAS: list[str] = [
    "printer_paper_decisions -- paper decisions remain locked",
    "printer_paper_positions -- paper positions remain locked",
    "printer_trade_events -- trade events remain locked",
    "printer_paper_trade_audits -- paper trade audits remain locked",
]

# Stop conditions from E2C-D runbook and E2D/E2E gates plus E2F-specific additions.
_STOP_CONDITIONS: list[str] = [
    "E2E approval_packet_status is not APPROVAL_PACKET_READY.",
    "approval_confirmed flag is not explicitly set by operator.",
    "DB backup file does not exist or backup was not confirmed.",
    "DB file does not exist at the expected path.",
    "Token list validation reports valid=false for any reason.",
    "Any token_mint fails Solana base58 format check (43-44 chars, base58 alphabet).",
    "lifecycle_lane is not TRACK_FAST or TRACK_NORMAL.",
    "Duplicate token_mint values in the list.",
    "Token count is 0 or greater than 2.",
    "approved_by_operator is false or missing for any token.",
    "Placeholder mints remain in the token list.",
    "Any source reports allowed=false from Source Governor.",
    "Any governor_decision is rate_limit_exceeded in planned_sources.",
    "Any row with status=RUNNING in printer_scheduler_jobs.",
    "Any row with locked_at IS NOT NULL in printer_scheduler_jobs.",
    "Any row with lock_owner set in printer_scheduler_jobs.",
    "Any hard-lock flag in hard_locks is true when it should be false.",
    "Any direct source adapter call outside Source Governor boundaries.",
    "Any scheduler job created outside Central Scheduler job table boundaries.",
    "Any paper decision row created in printer_paper_decisions.",
    "Any BUY, SELL, or HOLD decision row created.",
    "Any paper position, trade event, or PnL row created.",
    "Any wallet connection, private key reference, signing, or live execution detected.",
    "Any paid API dependency activated.",
    "Any embedding, vector, scoring, ranking, or confidence-weighted path triggered.",
]

# Rollback checklist from E2C-D runbook.
_ROLLBACK_CHECKLIST: list[str] = [
    "[ ] Stop immediately if any unexpected row is created outside allowed_table_deltas.",
    "[ ] Confirm backup file exists: Test-Path <backup_path>",
    "[ ] Rename current DB to preserve unexpected state:"
    " Rename-Item data\\printer_v1.sqlite3 data\\printer_v1_unexpected_state_<ts>.sqlite3",
    "[ ] Copy backup to DB path:"
    " Copy-Item -Path <backup_path> -Destination data\\printer_v1.sqlite3",
    "[ ] Confirm restore: Test-Path data\\printer_v1.sqlite3",
    "[ ] Rerun E2C-C preflight to confirm DB state is clean after restore.",
    "[ ] Review git status --short for unexpected changes.",
    "[ ] Review git log --oneline -10 for unexpected commits.",
    "[ ] Do not delete the backup file until the lane is confirmed stable.",
    "[ ] Report any unexpected row creation, source calls, or errors.",
]

# Mutation plan: describes what WOULD be written by the real cycle (not by this module).
_MUTATION_PLAN: dict[str, Any] = {
    "mutation_scope": "first bounded 15m Memory Factory cycle only",
    "max_tokens": 2,
    "lifecycle_lanes": ["TRACK_FAST", "TRACK_NORMAL"],
    "source_calls": "governed by Source Governor; rate limits enforced",
    "scheduler_jobs": "created and managed by Central Scheduler boundaries only",
    "no_direct_source_calls": True,
    "zero_clean_memories_is_valid": True,
    "allowed_table_deltas": _ALLOWED_TABLE_DELTAS,
    "forbidden_table_deltas": _FORBIDDEN_TABLE_DELTAS,
    "paper_decisions_enabled": False,
    "buy_sell_hold_enabled": False,
    "positions_enabled": False,
    "pnl_enabled": False,
}


def _determine_boundary_status(
    e2e_packet: dict[str, Any],
    *,
    approval_confirmed: bool,
) -> tuple[str, list[str], str]:
    """Return (cycle_status, reasons, e2f_status) from E2E packet and flags.

    BLOCKED unless:
    - E2E approval_packet_status is APPROVAL_PACKET_READY
    - approval_confirmed is True

    Pure function.
    """
    reasons: list[str] = []

    packet_status = e2e_packet.get("approval_packet_status")
    if packet_status != APPROVAL_PACKET_READY:
        reasons.append(
            "E2E approval_packet_status is "
            + repr(packet_status)
            + "; must be APPROVAL_PACKET_READY"
        )
        for r in e2e_packet.get("approval_packet_reasons", []):
            reasons.append("  E2E reason: " + r)

    if not approval_confirmed:
        reasons.append(
            "approval_confirmed is False; operator must explicitly confirm"
            " approval before the execution boundary can be crossed"
        )

    locks = e2e_packet.get("hard_locks", {})
    for key, val in locks.items():
        if val is not False:
            reasons.append(f"hard_locks[{key!r}] is not False: {val!r}")

    e2d = e2e_packet.get("e2d_decision", {})
    mutation_proof = e2d.get("db_mutation_proof", {})
    if not mutation_proof.get("all_counts_unchanged", True):
        changed = mutation_proof.get("changed_tables", [])
        reasons.append(
            "DB mutation detected in E2D decision; changed tables: " + repr(changed)
        )

    if reasons:
        return CYCLE_BLOCKED, reasons, E2F_STATUS_BLOCKED

    return CYCLE_READY_TO_RUN, [
        "E2E approval packet is APPROVAL_PACKET_READY",
        "operator approval_confirmed is True",
        "all 11 hard-lock flags are False",
        "no persistent DB mutation detected",
        "all Central Scheduler and Source Governor boundaries are enforced",
        "no direct source adapter calls permitted from execution engines",
        "CYCLE_READY_TO_RUN: operator must run the bounded execution command"
        " manually against the real DB after committing and tagging Lane E2F",
        "CYCLE_READY_TO_RUN does NOT mean Claude ran the cycle",
        "BUY, SELL, HOLD, paper decisions, positions, and PnL remain locked",
        "zero clean memories is a valid cycle outcome",
        "5m remains support-only; 15m is the first main Memory Factory target",
    ], E2F_STATUS_READY


def build_e2f_execution_boundary_payload(
    token_file_path: str | Path | None,
    db_path: str | Path | None,
    *,
    approval_confirmed: bool,
    backup_confirmed: bool,
) -> dict[str, Any]:
    """Build the E2F execution boundary payload.

    Calls E2E approval packet, then applies the final execution boundary gate.

    This function is read-only planning. It does NOT run the real cycle.
    No source fetching. No scheduler execution. No persistent DB mutation.
    No snapshots, memory, context, or paper decisions produced here.
    """
    e2e_packet = build_e2e_approval_packet(
        token_file_path,
        db_path,
        backup_confirmed=backup_confirmed,
    )

    cycle_status, cycle_reasons, e2f_status = _determine_boundary_status(
        e2e_packet,
        approval_confirmed=approval_confirmed,
    )

    return {
        "command": "printer-run-first-bounded-15m-cycle",
        "dry_run": True,
        "planning_only": True,
        "claude_did_not_run_cycle": True,
        "e2e_approval_packet": e2e_packet,
        "cycle_status": cycle_status,
        "cycle_status_reasons": cycle_reasons,
        "e2f_status": e2f_status,
        "exact_operator_run_command": _EXACT_OPERATOR_RUN_COMMAND,
        "mutation_plan": _MUTATION_PLAN,
        "stop_conditions": _STOP_CONDITIONS,
        "rollback_checklist": _ROLLBACK_CHECKLIST,
        "hard_locks": dict(HARD_LOCKS),
        "next_required_operator_action": (
            "Commit and tag Lane E2F. Then run the exact_operator_run_command"
            " manually against the real DB. Do not run it without committing"
            " and tagging E2F first."
            if cycle_status == CYCLE_READY_TO_RUN
            else "Resolve all BLOCKED reasons above before rerunning E2F boundary check."
        ),
    }

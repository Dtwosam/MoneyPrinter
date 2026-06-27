"""E2E First Bounded Cycle Operator Approval Packet.

Wraps the E2D decision payload and produces a structured approval packet for
the future first bounded real source-governed 15m Memory Factory cycle.

Outputs APPROVAL_PACKET_READY or BLOCKED.

APPROVAL_PACKET_READY means all automated gates passed and the packet is ready
for a human operator approval review only. It does NOT start real execution, source
fetching, scheduler runtime, or any live action.

All operations are read-only. No source fetching. No scheduler runtime.
No persistent DB mutation. No snapshots, memory, context, or paper decisions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from printer_v1.operator_cli.e2d_decision import (
    FINAL_DECISION_GO,
    build_e2d_decision_payload,
)
from printer_v1.operator_cli.e2c_readiness import HARD_LOCKS


APPROVAL_PACKET_READY: str = "APPROVAL_PACKET_READY"
APPROVAL_PACKET_BLOCKED: str = "BLOCKED"

E2E_STATUS_READY: str = "E2E_APPROVAL_PACKET_READY"
E2E_STATUS_BLOCKED: str = "E2E_APPROVAL_PACKET_BLOCKED"

# Inert text-only preview of the future execution command.
# This is documentation only -- it does NOT execute anything.
_FUTURE_COMMAND_PREVIEW: str = (
    "printer-run-bounded"
    " --token-list-path <PATH_TO_OPERATOR_APPROVED_TOKEN_LIST_JSON>"
    " --backup-confirmed"
    " --db-path <PATH_TO_DB>"
    " --format json"
    "\n\n"
    "NOTE: This preview is inert text only. It does NOT execute the command."
    " The command above may only be run after a separately named and explicitly"
    " approved next lane has been opened by the operator."
    " Running this command without a separately approved lane is not authorized."
)

# Stop conditions carried forward from E2C-D runbook and E2D decision doc.
_STOP_CONDITIONS: list[str] = [
    "DB backup command fails or the backup file does not exist after backup.",
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
    "Any source fetching detected outside an approved bounded command.",
    "Any snapshot row created outside the bounded cycle.",
    "Any memory row created in printer_memories unexpectedly.",
    "Any paper decision row created in printer_paper_decisions.",
    "Any BUY, SELL, or HOLD decision row created.",
    "Any paper position, trade event, or PnL row created.",
    "Any wallet connection, private key reference, signing, or live execution detected.",
    "Any paid API dependency activated.",
    "E2D final_decision is not GO_TO_OPERATOR_APPROVAL.",
]

# Rollback checklist carried forward from E2C-D runbook.
_ROLLBACK_CHECKLIST: list[str] = [
    "[ ] Confirm backup file exists: Test-Path <backup_path>",
    "[ ] Rename current DB to preserve unexpected state:"
    " Rename-Item data\\printer_v1.sqlite3 data\\printer_v1_unexpected_state_<ts>.sqlite3",
    "[ ] Copy backup to DB path: Copy-Item -Path <backup_path> -Destination data\\printer_v1.sqlite3",
    "[ ] Confirm restore: Test-Path data\\printer_v1.sqlite3",
    "[ ] Rerun preflight to confirm DB state is clean after restore.",
    "[ ] Review git status --short for unexpected changes.",
    "[ ] Review git log --oneline -10 for unexpected commits.",
    "[ ] Do not delete the backup file until the lane is confirmed stable.",
]

# Confirmations the operator must provide before any execution lane can begin.
_REQUIRED_OPERATOR_CONFIRMATIONS: list[str] = [
    "[ ] I have reviewed the full E2D decision payload and confirm GO_TO_OPERATOR_APPROVAL.",
    "[ ] I have reviewed the full E2C-F operator review payload.",
    "[ ] I have reviewed the token list and confirm all entries are correct and approved.",
    "[ ] I have confirmed no placeholder mints remain in the token list.",
    "[ ] I have created a DB backup and confirmed the backup file exists.",
    "[ ] I confirm the DB backup path is recorded.",
    "[ ] I confirm zero RUNNING jobs in printer_scheduler_jobs.",
    "[ ] I confirm zero active locks (locked_at, lock_owner) in printer_scheduler_jobs.",
    "[ ] I confirm all source budgets are allowed (no rate_limit_exceeded).",
    "[ ] I confirm all 11 hard-lock flags are false.",
    "[ ] I confirm no persistent DB mutation occurred during E2E packet build.",
    "[ ] I have read and accept all stop conditions listed in this packet.",
    "[ ] I have read and accept the rollback checklist.",
    "[ ] I understand that APPROVAL_PACKET_READY does NOT start real execution.",
    "[ ] I understand that a separately named and explicitly approved next lane is"
    " required before any bounded real source-governed 15m cycle can begin.",
]


def _build_approval_packet(
    e2d_decision: dict[str, Any],
) -> tuple[str, list[str], str]:
    """Return (packet_status, reasons, e2e_status) from E2D decision payload.

    BLOCKED unless E2D final_decision is GO_TO_OPERATOR_APPROVAL.
    Pure function.
    """
    reasons: list[str] = []

    final_decision = e2d_decision.get("final_decision")
    if final_decision != FINAL_DECISION_GO:
        reasons.append(
            "E2D final_decision is "
            + repr(final_decision)
            + "; must be GO_TO_OPERATOR_APPROVAL to build approval packet"
        )
        for r in e2d_decision.get("final_decision_reasons", []):
            reasons.append("  E2D reason: " + r)

    locks = e2d_decision.get("hard_locks", {})
    for key, val in locks.items():
        if val is not False:
            reasons.append(f"hard_locks[{key!r}] is not False: {val!r}")

    mutation_proof = e2d_decision.get("db_mutation_proof", {})
    if not mutation_proof.get("all_counts_unchanged", True):
        changed = mutation_proof.get("changed_tables", [])
        reasons.append(
            "DB mutation detected in E2D decision; changed tables: " + repr(changed)
        )

    if reasons:
        return APPROVAL_PACKET_BLOCKED, reasons, E2E_STATUS_BLOCKED

    return APPROVAL_PACKET_READY, [
        "E2D final_decision is GO_TO_OPERATOR_APPROVAL",
        "all 11 hard-lock flags are False",
        "no persistent DB mutation detected",
        "approval packet is complete and ready for operator review",
        "APPROVAL_PACKET_READY does NOT authorize real execution, source fetching,"
        " scheduler runtime, snapshot collection, memory creation, paper decisions,"
        " or any live action",
        "a separately named and explicitly approved next lane is required before any"
        " bounded real source-governed 15m Memory Factory cycle can begin",
    ], E2E_STATUS_READY


def build_e2e_approval_packet(
    token_file_path: str | Path | None,
    db_path: str | Path | None,
    *,
    backup_confirmed: bool,
) -> dict[str, Any]:
    """Build the full E2E first bounded cycle operator approval packet.

    Calls E2D decision payload, then wraps with approval packet content.

    No persistent DB mutation. No source fetching. No scheduler execution.
    No snapshot creation. No memory creation. No paper decisions.
    """
    e2d_decision = build_e2d_decision_payload(
        token_file_path,
        db_path,
        backup_confirmed=backup_confirmed,
    )

    packet_status, packet_reasons, e2e_status = _build_approval_packet(e2d_decision)

    return {
        "command": "printer-build-first-bounded-15m-approval-packet",
        "dry_run": True,
        "approval_packet_only": True,
        "e2d_decision": e2d_decision,
        "approval_packet_status": packet_status,
        "approval_packet_reasons": packet_reasons,
        "exact_future_command_preview": _FUTURE_COMMAND_PREVIEW,
        "required_operator_confirmations": _REQUIRED_OPERATOR_CONFIRMATIONS,
        "stop_conditions": _STOP_CONDITIONS,
        "rollback_checklist": _ROLLBACK_CHECKLIST,
        "hard_locks": dict(HARD_LOCKS),
        "next_lane_boundary": (
            "The next lane must be separately named and explicitly approved by the"
            " operator before any bounded real source-governed 15m Memory Factory"
            " cycle can begin. APPROVAL_PACKET_READY does not authorize execution."
        ),
    }

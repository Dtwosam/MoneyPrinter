"""E2D First Bounded Real Cycle Decision Package.

Wraps the E2C-F operator review payload and applies a final decision gate.

Outputs GO_TO_OPERATOR_APPROVAL or BLOCKED.

GO_TO_OPERATOR_APPROVAL means all automated gates have passed and the package is
ready for a human operator approval review. It does NOT start real execution.

All operations are read-only. No source fetching. No scheduler runtime.
No persistent DB mutation. No snapshots, memory, context, or paper decisions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from printer_v1.operator_cli.e2c_operator_review import (
    FINAL_RECOMMENDATION_READY,
    build_e2c_operator_review_payload,
)
from printer_v1.operator_cli.e2c_readiness import HARD_LOCKS


FINAL_DECISION_GO: str = "GO_TO_OPERATOR_APPROVAL"
FINAL_DECISION_BLOCKED: str = "BLOCKED"

E2D_STATUS_GO: str = "E2D_READY_FOR_OPERATOR_APPROVAL_REVIEW"
E2D_STATUS_BLOCKED: str = "E2D_DECISION_BLOCKED"


def _determine_e2d_decision(
    e2c_f_review: dict[str, Any],
) -> tuple[str, list[str], str]:
    """Return (final_decision, reasons, e2d_status) based on E2C-F review payload.

    Pure function. All gate logic is derived from the E2C-F payload.
    """
    reasons: list[str] = []

    e2c_f_rec = e2c_f_review.get("final_recommendation")
    if e2c_f_rec != FINAL_RECOMMENDATION_READY:
        reasons.append(
            "E2C-F operator review recommendation is "
            + repr(e2c_f_rec)
            + "; must be READY_FOR_OPERATOR_DECISION"
        )

    token_file_review = e2c_f_review.get("token_file_review", {})
    if not token_file_review.get("valid"):
        for err in token_file_review.get("errors", []):
            reasons.append("token file: " + err)

    readiness_review = e2c_f_review.get("e2c_readiness_review", {})
    readiness_rec = readiness_review.get("recommendation")
    if readiness_rec != "LIMITED_GO_FOR_OPERATOR_REVIEW":
        reasons.append(
            "E2C-C readiness recommendation is "
            + repr(readiness_rec)
            + "; must be LIMITED_GO_FOR_OPERATOR_REVIEW"
        )

    fixture_review = e2c_f_review.get("fixture_rehearsal_review", {})
    fixture_rec = fixture_review.get("recommendation")
    if fixture_rec != "FIXTURE_REHEARSAL_PASS":
        reasons.append(
            "E2C-E fixture rehearsal recommendation is "
            + repr(fixture_rec)
            + "; must be FIXTURE_REHEARSAL_PASS"
        )

    locks = e2c_f_review.get("hard_locks", {})
    for key, val in locks.items():
        if val is not False:
            reasons.append(f"hard_locks[{key!r}] is not False: {val!r}")

    mutation_proof = fixture_review.get("mutation_proof", {})
    if not mutation_proof.get("all_counts_unchanged", True):
        changed = mutation_proof.get("changed_tables", [])
        reasons.append(
            "DB mutation detected during fixture rehearsal; changed tables: "
            + repr(changed)
        )

    if reasons:
        return FINAL_DECISION_BLOCKED, reasons, E2D_STATUS_BLOCKED

    return FINAL_DECISION_GO, [
        "E2C-F operator review returned READY_FOR_OPERATOR_DECISION",
        "token file valid (1-2 tokens, all fields, no placeholders, all approved)",
        "E2C-C readiness returned LIMITED_GO_FOR_OPERATOR_REVIEW",
        "E2C-E fixture rehearsal returned FIXTURE_REHEARSAL_PASS",
        "all 11 hard-lock flags are False",
        "no persistent DB mutation detected",
        "GO_TO_OPERATOR_APPROVAL: ready for human operator approval review only",
        "GO_TO_OPERATOR_APPROVAL does NOT authorize real source fetching, scheduler"
        " execution, snapshot collection, memory creation, paper decisions, or any"
        " live execution",
        "operator must explicitly approve and name a next lane before any bounded"
        " real source-governed 15m cycle can begin",
    ], E2D_STATUS_GO


def build_e2d_decision_payload(
    token_file_path: str | Path | None,
    db_path: str | Path | None,
    *,
    backup_confirmed: bool,
) -> dict[str, Any]:
    """Build the full E2D first bounded real cycle decision payload.

    Calls the E2C-F operator review and wraps the result with a final E2D decision.

    No persistent DB mutation. No source fetching. No scheduler execution.
    No snapshot creation. No memory creation. No paper decisions.
    """
    e2c_f_review = build_e2c_operator_review_payload(
        token_file_path,
        db_path,
        backup_confirmed=backup_confirmed,
    )

    mutation_proof = e2c_f_review.get("fixture_rehearsal_review", {}).get(
        "mutation_proof", {}
    )

    final_decision, final_reasons, e2d_status = _determine_e2d_decision(e2c_f_review)

    return {
        "command": "printer-decide-first-bounded-15m-cycle",
        "dry_run": True,
        "decision_only": True,
        "e2d_status": e2d_status,
        "e2c_f_review": e2c_f_review,
        "db_mutation_proof": mutation_proof,
        "final_decision": final_decision,
        "final_decision_reasons": final_reasons,
        "hard_locks": dict(HARD_LOCKS),
        "next_required_operator_action": (
            "Operator must review this payload, confirm GO_TO_OPERATOR_APPROVAL,"
            " and explicitly name and approve a next separately-named lane before"
            " any bounded real source-governed 15m cycle can begin."
            if final_decision == FINAL_DECISION_GO
            else "Resolve all BLOCKED reasons above before rerunning E2D decision."
        ),
    }

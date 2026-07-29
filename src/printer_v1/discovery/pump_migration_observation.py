"""Pure Pump-lineage branch and candidate migration locator contracts.

This module performs no source access and owns no cursor.  It translates exact
cohort facts into one categorical branch and, only for an explicit Pump
graduation branch, selects the most-specific predeclared locator.
"""

from __future__ import annotations

from typing import Any, Mapping


PUMP_GRADUATION_CLAIMED = "PUMP_GRADUATION_CLAIMED"
PUMP_ACTIVE_BONDING_CURVE = "PUMP_ACTIVE_BONDING_CURVE"
NO_PUMP_GRADUATION_CLAIM = "NO_PUMP_GRADUATION_CLAIM"
PUMP_LINEAGE_CONFLICT = "PUMP_LINEAGE_CONFLICT"

MIGRATION_SIGNATURE = "MIGRATION_SIGNATURE"
PUMPSWAP_POOL = "PUMPSWAP_POOL"
PUMP_BONDING_CURVE = "PUMP_BONDING_CURVE"
CANDIDATE_MINT = "CANDIDATE_MINT"


def classify_candidate_lineage_branch(
    *,
    candidate_mint: str,
    exact_pump_origin: Mapping[str, Any] | None = None,
    verified_bonding_curve: Mapping[str, Any] | None = None,
    exact_migration_signature: str | None = None,
    proposed_pumpswap_pool: str | None = None,
    explicit_pump_graduation_claim: bool = False,
    independently_known_non_pump: bool = False,
    current_pool_conflict: bool = False,
) -> dict[str, Any]:
    """Return one exact branch without scores, source preference, or fallback."""
    mint = str(candidate_mint or "")
    if not mint:
        return {
            "branch": PUMP_LINEAGE_CONFLICT,
            "reason": "CANDIDATE_MINT_REQUIRED",
        }

    origin = dict(exact_pump_origin or {})
    curve = dict(verified_bonding_curve or {})
    has_origin = bool(origin)
    origin_mint = str(origin.get("mint") or mint) if has_origin else None
    origin_curve = str(origin.get("bonding_curve") or "") if has_origin else ""
    curve_mint = str(curve.get("base_mint") or mint) if curve else None
    curve_address = str(curve.get("bonding_curve_address") or "") if curve else ""
    pump_claim = bool(
        exact_migration_signature
        or explicit_pump_graduation_claim
        or (has_origin and proposed_pumpswap_pool)
        or (has_origin and curve and curve.get("complete") is True)
    )

    conflict_reason: str | None = None
    if origin_mint is not None and origin_mint != mint:
        conflict_reason = "PUMP_ORIGIN_MINT_CONFLICT"
    elif curve_mint is not None and curve_mint != mint:
        conflict_reason = "PUMP_CURVE_MINT_CONFLICT"
    elif curve and origin_curve and curve_address != origin_curve:
        conflict_reason = "PUMP_CURVE_ADDRESS_CONFLICT"
    elif independently_known_non_pump and (has_origin or pump_claim):
        conflict_reason = "PUMP_AND_NON_PUMP_LINEAGE_CONFLICT"
    elif current_pool_conflict:
        conflict_reason = "CURRENT_POOL_IDENTITY_CONFLICT"
    elif has_origin and not curve and not pump_claim:
        conflict_reason = "PUMP_CURVE_STATE_REQUIRED"

    if conflict_reason is not None:
        return {"branch": PUMP_LINEAGE_CONFLICT, "reason": conflict_reason}
    if pump_claim:
        return {
            "branch": PUMP_GRADUATION_CLAIMED,
            "reason": (
                "EXACT_MIGRATION_SIGNATURE_CLAIM"
                if exact_migration_signature
                else "EXPLICIT_PUMP_GRADUATION_CLAIM"
                if explicit_pump_graduation_claim
                else "EXACT_ORIGIN_AND_PUMPSWAP_POOL_CLAIM"
                if proposed_pumpswap_pool
                else "COMPLETED_PUMP_BONDING_CURVE_CLAIM"
            ),
        }
    if has_origin and curve.get("complete") is False:
        return {
            "branch": PUMP_ACTIVE_BONDING_CURVE,
            "reason": "EXACT_ACTIVE_PUMP_BONDING_CURVE",
        }
    return {
        "branch": NO_PUMP_GRADUATION_CLAIM,
        "reason": "NO_EXACT_PUMP_GRADUATION_CLAIM",
    }


def plan_candidate_migration_locator(
    *,
    candidate_mint: str,
    branch: str,
    finalized_cutoff_slot: int,
    exact_migration_signature: str | None = None,
    exact_pumpswap_pool: str | None = None,
    exact_verified_bonding_curve: str | None = None,
) -> dict[str, Any] | None:
    """Choose signature, Pool, curve, then mint; never plan a broader retry."""
    if branch != PUMP_GRADUATION_CLAIMED:
        return None
    mint = str(candidate_mint or "")
    if not mint:
        raise ValueError("CANDIDATE_MINT_REQUIRED")
    cutoff = int(finalized_cutoff_slot)
    if cutoff < 0:
        raise ValueError("FINALIZED_CUTOFF_SLOT_INVALID")
    if exact_migration_signature:
        kind, target = MIGRATION_SIGNATURE, str(exact_migration_signature)
    elif exact_pumpswap_pool:
        kind, target = PUMPSWAP_POOL, str(exact_pumpswap_pool)
    elif exact_verified_bonding_curve:
        kind, target = PUMP_BONDING_CURVE, str(exact_verified_bonding_curve)
    else:
        kind, target = CANDIDATE_MINT, mint
    return {
        "candidate_mint": mint,
        "locator_kind": kind,
        "locator_target": target,
        "finalized_cutoff_slot": cutoff,
        "fallback_allowed": False,
    }


def validate_candidate_migration_locator(
    *,
    locator: Mapping[str, Any],
    decoded_migration: Mapping[str, Any],
) -> tuple[bool, str]:
    """Bind a decoded exact migrate instruction to its one planned locator."""
    mint = str(locator.get("candidate_mint") or "")
    if str(decoded_migration.get("mint") or "") != mint:
        return False, "CANDIDATE_MIGRATION_MINT_MISMATCH"
    kind = str(locator.get("locator_kind") or "")
    target = str(locator.get("locator_target") or "")
    accounts = decoded_migration.get("accounts")
    if not isinstance(accounts, (list, tuple)) or len(accounts) != 25:
        return False, "CANDIDATE_MIGRATION_LAYOUT_UNSUPPORTED"
    if kind == MIGRATION_SIGNATURE:
        return True, "CANDIDATE_MIGRATION_SIGNATURE_BOUND"
    if kind == PUMPSWAP_POOL:
        return (
            (True, "CANDIDATE_MIGRATION_POOL_BOUND")
            if str(decoded_migration.get("pool_address") or "") == target
            else (False, "CANDIDATE_MIGRATION_POOL_MISMATCH")
        )
    if kind == PUMP_BONDING_CURVE:
        return (
            (True, "CANDIDATE_MIGRATION_BONDING_CURVE_BOUND")
            if str(accounts[3]) == target
            else (False, "CANDIDATE_MIGRATION_BONDING_CURVE_MISMATCH")
        )
    if kind == CANDIDATE_MINT:
        return (
            (True, "CANDIDATE_MIGRATION_MINT_BOUND")
            if target == mint
            else (False, "CANDIDATE_MIGRATION_MINT_LOCATOR_MISMATCH")
        )
    return False, "CANDIDATE_MIGRATION_LOCATOR_UNSUPPORTED"


__all__ = [
    "PUMP_GRADUATION_CLAIMED",
    "PUMP_ACTIVE_BONDING_CURVE",
    "NO_PUMP_GRADUATION_CLAIM",
    "PUMP_LINEAGE_CONFLICT",
    "MIGRATION_SIGNATURE",
    "PUMPSWAP_POOL",
    "PUMP_BONDING_CURVE",
    "CANDIDATE_MINT",
    "classify_candidate_lineage_branch",
    "plan_candidate_migration_locator",
    "validate_candidate_migration_locator",
]

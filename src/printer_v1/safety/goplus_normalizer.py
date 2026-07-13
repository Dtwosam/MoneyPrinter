"""GoPlus token security response → safety evidence row normalizer.

Maps the GoPlus Solana token security API response into the field shape
expected by ``insert_solana_safety_evidence``. All analysis is read-only.
No keys or execution paths are involved.

If critical hard-gate fields are missing, the corresponding label is set to
UNKNOWN, which causes safety_context_label = SAFETY_UNKNOWN and prevents clean
memory. Some source-coverage gaps are allowed for 15m memory learning only, but
they are never labeled SAFETY_CLEAN.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Mapping

from printer_v1.safety.evidence import (
    ALLOWED_CALLER,
    SolanaSafetyEvidenceInsertResult,
    insert_solana_safety_evidence,
)


GOPLUS_SOURCE_NAME = "goplus"


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_empty_authority(authority: Any) -> bool:
    """Return True if authority is absent, null, empty list, or empty string."""
    if authority is None:
        return True
    if isinstance(authority, (list, tuple)):
        return len(authority) == 0
    if isinstance(authority, str):
        return authority.strip() in ("", "null", "none")
    return False


def _mint_authority_status(token_data: Mapping[str, Any]) -> str:
    # Real GoPlus Solana shape: mintable is a status object
    mintable = token_data.get("mintable")
    if isinstance(mintable, Mapping):
        status = str(mintable.get("status") or "")
        authority = mintable.get("authority")
        if status == "0" and _is_empty_authority(authority):
            return "MINT_AUTHORITY_RENOUNCED"
        return "MINT_AUTHORITY_PRESENT"
    # Legacy/flat fixture format: mint_authority field
    if "mint_authority" not in token_data:
        return "MINT_AUTHORITY_UNKNOWN"
    value = token_data.get("mint_authority")
    if value in (None, "", False, "null"):
        return "MINT_AUTHORITY_RENOUNCED"
    if str(value).lower() in {"null", "none"}:
        return "MINT_AUTHORITY_RENOUNCED"
    return "MINT_AUTHORITY_PRESENT"


def _freeze_authority_status(token_data: Mapping[str, Any]) -> str:
    # Real GoPlus Solana shape: freezable is a status object
    freezable = token_data.get("freezable")
    if isinstance(freezable, Mapping):
        status = str(freezable.get("status") or "")
        authority = freezable.get("authority")
        if status == "0" and _is_empty_authority(authority):
            return "FREEZE_AUTHORITY_DISABLED"
        return "FREEZE_AUTHORITY_PRESENT"
    # Legacy/flat fixture format: freeze_authority field
    if "freeze_authority" not in token_data:
        return "FREEZE_AUTHORITY_UNKNOWN"
    value = token_data.get("freeze_authority")
    if value in (None, "", False, "null"):
        return "FREEZE_AUTHORITY_DISABLED"
    if str(value).lower() in {"null", "none"}:
        return "FREEZE_AUTHORITY_DISABLED"
    return "FREEZE_AUTHORITY_PRESENT"


def _metadata_mutability_status(token_data: Mapping[str, Any]) -> str:
    mutable = token_data.get("metadata_mutable")
    if mutable is None:
        return "METADATA_UNKNOWN"
    # Real GoPlus Solana shape: metadata_mutable is a status object
    if isinstance(mutable, Mapping):
        status = str(mutable.get("status") or "")
        upgrade_authority = mutable.get("metadata_upgrade_authority")
        if status == "0" and _is_empty_authority(upgrade_authority):
            return "METADATA_IMMUTABLE"
        return "METADATA_MUTABLE"
    # Legacy/flat fixture format: bool or string
    if isinstance(mutable, bool):
        return "METADATA_MUTABLE" if mutable else "METADATA_IMMUTABLE"
    if str(mutable).lower() in {"false", "0", "no"}:
        return "METADATA_IMMUTABLE"
    if str(mutable).lower() in {"true", "1", "yes"}:
        return "METADATA_MUTABLE"
    return "METADATA_UNKNOWN"


def _supply_sanity_label(token_data: Mapping[str, Any]) -> str:
    # Real GoPlus Solana payload includes total_supply directly
    total_supply = token_data.get("total_supply")
    if total_supply is not None:
        try:
            if float(total_supply) > 0:
                return "SUPPLY_SANITY_OK"
        except (TypeError, ValueError):
            pass
        return "SUPPLY_SANITY_CAUTION"
    # GoPlus signals open minting via is_open_minting
    is_open = token_data.get("is_open_minting")
    if is_open is True:
        return "SUPPLY_SANITY_CAUTION"
    return "SUPPLY_SANITY_UNKNOWN"


def _holder_concentration_label(token_data: Mapping[str, Any]) -> str:
    top_10 = token_data.get("top_10_holders")
    total_pct: float | None = None
    if isinstance(top_10, list) and top_10:
        values: list[float] = []
        for holder in top_10[:10]:
            if not isinstance(holder, Mapping):
                return "HOLDER_CONCENTRATION_UNKNOWN"
            value = _to_float(holder.get("percent") or holder.get("balance_percent"))
            if value is None or value < 0:
                return "HOLDER_CONCENTRATION_UNKNOWN"
            values.append(value)
        total_pct = sum(values)
    else:
        # Live GoPlus Solana shape: holder balances plus validated total supply.
        holders = token_data.get("holders")
        supply = _to_float(token_data.get("total_supply"))
        if not isinstance(holders, list) or not holders or supply is None or supply <= 0:
            return "HOLDER_CONCENTRATION_UNKNOWN"
        balances: list[float] = []
        for holder in holders:
            if not isinstance(holder, Mapping):
                return "HOLDER_CONCENTRATION_UNKNOWN"
            balance = _to_float(holder.get("balance") or holder.get("amount"))
            if balance is None or balance < 0:
                return "HOLDER_CONCENTRATION_UNKNOWN"
            balances.append(balance)
        total_pct = (sum(sorted(balances, reverse=True)[:10]) / supply) * 100.0
    if total_pct >= 80:
        return "HOLDER_CONCENTRATION_EXTREME"
    if total_pct >= 55:
        return "HOLDER_CONCENTRATION_CONCENTRATED"
    return "HOLDER_CONCENTRATION_HEALTHY"


def holder_concentration_label_from_goplus(token_data: Mapping[str, Any]) -> str:
    """Expose the fail-closed GoPlus holder calculation to governed collectors."""
    return _holder_concentration_label(token_data)


def _liquidity_lock_or_burn_label(token_data: Mapping[str, Any]) -> str:
    # GoPlus token-level LP fields do not identify the selected exact pair.
    # Pair-specific dangerous evidence is evaluated by the composite contract.
    return "LIQUIDITY_LOCK_OR_BURN_UNKNOWN"


def _known_risk_flag_label(token_data: Mapping[str, Any]) -> str:
    # Use explicit key presence check — empty list [] is falsy but means "no flags".
    for key in ("risky_flags", "risk_flags", "risks"):
        if key in token_data:
            flags = token_data[key]
            if flags is None:
                return "KNOWN_RISK_FLAGS_UNKNOWN"
            if isinstance(flags, (list, tuple)):
                return "KNOWN_RISK_FLAGS_PRESENT" if flags else "NO_KNOWN_RISK_FLAGS"
            if isinstance(flags, bool):
                return "KNOWN_RISK_FLAGS_PRESENT" if flags else "NO_KNOWN_RISK_FLAGS"
    return "KNOWN_RISK_FLAGS_UNKNOWN"


REQUIRED_CLEAN_SAFETY_FIELDS: dict[str, str] = {
    "mint_authority_status": "MINT_AUTHORITY_RENOUNCED",
    "freeze_authority_status": "FREEZE_AUTHORITY_DISABLED",
    "metadata_mutability_status": "METADATA_IMMUTABLE",
    "supply_sanity_label": "SUPPLY_SANITY_OK",
    "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
    "liquidity_lock_or_burn_label": "LIQUIDITY_LOCK_OR_BURN_CONFIRMED",
    "known_risk_flag_label": "NO_KNOWN_RISK_FLAGS",
    "token_program_label": "SPL_TOKEN_OR_TOKEN_2022_VERIFIED",
}

SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY = "SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY"

HARD_SAFETY_FIELD_EXPECTATIONS: dict[str, str] = {
    "mint_authority_status": "MINT_AUTHORITY_RENOUNCED",
    "freeze_authority_status": "FREEZE_AUTHORITY_DISABLED",
    "metadata_mutability_status": "METADATA_IMMUTABLE",
    "supply_sanity_label": "SUPPLY_SANITY_OK",
    "token_program_label": "SPL_TOKEN_OR_TOKEN_2022_VERIFIED",
}

SOURCE_COVERAGE_PENDING_VALUES: dict[str, str] = {
    "holder_concentration_label": "HOLDER_CONCENTRATION_UNKNOWN",
    "liquidity_lock_or_burn_label": "LIQUIDITY_LOCK_OR_BURN_UNKNOWN",
    "known_risk_flag_label": "KNOWN_RISK_FLAGS_UNKNOWN",
}

RESOLVED_HOLDER_CONCENTRATION_LABELS = {
    "HOLDER_CONCENTRATION_HEALTHY",
    "HOLDER_CONCENTRATION_CONCENTRATED",
    "HOLDER_CONCENTRATION_EXTREME",
}

EXPLICIT_SAFETY_BLOCKERS: dict[str, set[str]] = {
    "mint_authority_status": {"MINT_AUTHORITY_PRESENT"},
    "freeze_authority_status": {"FREEZE_AUTHORITY_PRESENT"},
    "metadata_mutability_status": {"METADATA_MUTABLE"},
    "supply_sanity_label": {"SUPPLY_SANITY_CAUTION", "SUPPLY_SANITY_FAILED"},
    "token_program_label": {"TOKEN_PROGRAM_UNSUPPORTED"},
    "liquidity_lock_or_burn_label": {"LIQUIDITY_UNLOCKED_OR_DANGEROUS"},
    "known_risk_flag_label": {"KNOWN_RISK_FLAGS_PRESENT"},
}


def safety_memory_policy_summary(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Categorize safety evidence for memory use without turning it fully clean.

    The 15m policy lets Printer learn from real memecoin behavior when hard
    safety gates pass but some free-source coverage is still pending. This is
    not a trading approval and not a SAFETY_CLEAN label.
    """
    hard_blocking: list[str] = []
    unresolved: list[str] = []
    source_coverage_pending: list[str] = []
    observed_risk: list[str] = []
    resolved: list[str] = []

    for field, expected in HARD_SAFETY_FIELD_EXPECTATIONS.items():
        value = evidence.get(field)
        if value == expected:
            resolved.append(field)
            continue
        if value is None or str(value).endswith("_UNKNOWN"):
            unresolved.append(field)
        hard_blocking.append(field)

    holder_value = evidence.get("holder_concentration_label")
    if holder_value in RESOLVED_HOLDER_CONCENTRATION_LABELS:
        resolved.append("holder_concentration_label")
        if holder_value != "HOLDER_CONCENTRATION_HEALTHY":
            observed_risk.append("holder_concentration_label")
            hard_blocking.append("holder_concentration_label")
    elif holder_value == SOURCE_COVERAGE_PENDING_VALUES["holder_concentration_label"]:
        unresolved.append("holder_concentration_label")
        hard_blocking.append("holder_concentration_label")
    else:
        hard_blocking.append("holder_concentration_label")

    for field in ("liquidity_lock_or_burn_label", "known_risk_flag_label"):
        value = evidence.get(field)
        if value == REQUIRED_CLEAN_SAFETY_FIELDS[field]:
            resolved.append(field)
        elif value == SOURCE_COVERAGE_PENDING_VALUES[field]:
            source_coverage_pending.append(field)
        else:
            hard_blocking.append(field)

    for field, blocked_values in EXPLICIT_SAFETY_BLOCKERS.items():
        if evidence.get(field) in blocked_values and field not in hard_blocking:
            hard_blocking.append(field)

    return {
        "resolved_safety_fields": list(dict.fromkeys(resolved)),
        "unresolved_safety_fields": list(dict.fromkeys(unresolved)),
        "source_coverage_pending_fields": list(dict.fromkeys(source_coverage_pending)),
        "observed_risk_fields": list(dict.fromkeys(observed_risk)),
        "hard_blocking_safety_fields": list(dict.fromkeys(hard_blocking)),
        "safety_15m_memory_policy_label": (
            SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY
            if not hard_blocking
            else "SAFETY_BLOCKED_FOR_15M_MEMORY"
        ),
        "safety_acceptable_for_15m_memory": not hard_blocking,
    }


def compute_safety_context_label(evidence: Mapping[str, Any]) -> str:
    """Compute the safety_context_label from an evidence field dict.

    SAFETY_CLEAN requires every required field to be its clean value.
    Optional unavailable source coverage remains SAFETY_UNKNOWN in storage,
    while safety_memory_policy_summary exposes 15m-only memory eligibility.
    TOKEN_PROGRAM_UNSUPPORTED forces SAFETY_UNSAFE.
    Otherwise SAFETY_CAUTION.
    """
    if all(evidence.get(k) == v for k, v in REQUIRED_CLEAN_SAFETY_FIELDS.items()):
        return "SAFETY_CLEAN"
    # A missing field (None) and an explicit _UNKNOWN value both block clean safety.
    if any(
        evidence.get(k) is None or str(evidence.get(k, "")).endswith("_UNKNOWN")
        for k in REQUIRED_CLEAN_SAFETY_FIELDS
    ):
        return "SAFETY_UNKNOWN"
    if evidence.get("token_program_label") == "TOKEN_PROGRAM_UNSUPPORTED":
        return "SAFETY_UNSAFE"
    return "SAFETY_CAUTION"


def _safety_context_label(evidence: Mapping[str, Any]) -> str:
    return compute_safety_context_label(evidence)


def normalize_goplus_safety_response(
    token_data: Mapping[str, Any],
    *,
    token_id: int,
    snapshot_id: int,
    source_request_id: int,
    source_response_id: int | None = None,
    source_failure_id: int | None = None,
    pair_id: int | None = None,
    memory_window_id: int | None = None,
    evidence_window_id: int | None = None,
    source_status: str = "COMPLETE",
    data_quality_label: str = "CLEAN_DATA",
    captured_at: str = "",
) -> dict[str, Any]:
    """Map GoPlus token security data into the safety evidence insert shape."""
    evidence = {
        "token_id": token_id,
        "pair_id": pair_id,
        "snapshot_id": snapshot_id,
        "memory_window_id": memory_window_id,
        "evidence_window_id": evidence_window_id,
        "safety_evidence_role": "TOKEN_SAFETY_CONTEXT",
        "source_name": GOPLUS_SOURCE_NAME,
        "source_status": source_status,
        "data_quality_label": data_quality_label,
        "target_status": str(token_data.get("target_status") or "TARGET_MATCH"),
        "evidence_captured_at": str(token_data.get("captured_at") or captured_at or ""),
        "freshness_label": str(token_data.get("freshness_label") or "SAFETY_EVIDENCE_FRESH"),
        "mint_authority_status": _mint_authority_status(token_data),
        "freeze_authority_status": _freeze_authority_status(token_data),
        "metadata_mutability_status": _metadata_mutability_status(token_data),
        "supply_sanity_label": _supply_sanity_label(token_data),
        "holder_concentration_label": _holder_concentration_label(token_data),
        "liquidity_lock_or_burn_label": _liquidity_lock_or_burn_label(token_data),
        "known_risk_flag_label": _known_risk_flag_label(token_data),
        "token_program_label": "SPL_TOKEN_OR_TOKEN_2022_VERIFIED",
        "source_request_id": source_request_id,
        "source_response_id": source_response_id,
        "source_failure_id": source_failure_id,
        "paper_only_context": True,
    }
    if not evidence["evidence_captured_at"]:
        evidence["freshness_label"] = "SAFETY_EVIDENCE_UNKNOWN"
    evidence["safety_context_label"] = _safety_context_label(evidence)
    if source_status in {"FAILED", "STALE", "CONFLICTING"} or data_quality_label not in {
        "CLEAN_DATA",
        "ACCEPTABLE_PARTIAL_DATA",
    }:
        evidence["safety_context_label"] = "SAFETY_UNKNOWN"
    return evidence


def insert_goplus_safety_evidence_from_source_response(
    connection: sqlite3.Connection,
    *,
    source_response_id: int,
    token_id: int,
    pair_id: int | None,
    snapshot_id: int,
    memory_window_id: int | None = None,
    evidence_window_id: int | None = None,
    scheduler_boundary_label: str,
    operator_approval_label: str,
    caller: str = ALLOWED_CALLER,
) -> SolanaSafetyEvidenceInsertResult:
    """Build and insert safety evidence from a recorded GoPlus source response."""
    import json as _json

    row = connection.execute(
        """
        SELECT response.*, request.request_kind
        FROM printer_source_responses AS response
        JOIN printer_source_requests AS request
          ON request.id = response.source_request_id
        WHERE response.id = ?
        """,
        (source_response_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Source response not found: {source_response_id}")
    if row["source_name"] != GOPLUS_SOURCE_NAME:
        raise ValueError("GoPlus safety response must come from goplus source")
    if row["request_kind"] != "safety_reference":
        raise ValueError("GoPlus response must use safety_reference request kind")

    payload = _json.loads(row["normalized_payload_json"] or "{}")
    if not isinstance(payload, Mapping):
        raise ValueError("Normalized GoPlus safety payload must be an object")

    evidence = normalize_goplus_safety_response(
        payload,
        token_id=token_id,
        pair_id=pair_id,
        snapshot_id=snapshot_id,
        memory_window_id=memory_window_id,
        evidence_window_id=evidence_window_id,
        source_request_id=int(row["source_request_id"]),
        source_response_id=int(row["id"]),
        source_status=str(row["source_status"]),
        data_quality_label=str(row["data_quality_label"]),
        captured_at=str(row["received_at"] or ""),
    )
    return insert_solana_safety_evidence(
        connection,
        evidence,
        scheduler_boundary_label=scheduler_boundary_label,
        operator_approval_label=operator_approval_label,
        caller=caller,
    )

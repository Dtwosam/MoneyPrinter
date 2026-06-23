"""Fixture-only Solana RPC safety evidence normalizer.

This module has no RPC client and no default network target. It converts caller-
provided, Source-Governor-recorded fixture payloads into the guarded
``printer_solana_safety_evidence`` insert helper shape.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from typing import Any

from printer_v1.safety.evidence import (
    ALLOWED_CALLER,
    SolanaSafetyEvidenceInsertResult,
    insert_solana_safety_evidence,
)


SOLANA_RPC_SOURCE_NAME = "solana_rpc"
SAFETY_REQUEST_KINDS = frozenset(
    {"onchain_reference", "mint_account_reference", "pool_reference"}
)


def _present(payload: Mapping[str, Any], key: str) -> bool:
    return key in payload and payload.get(key) is not None


def _nested(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1", "present", "mutable"}:
            return True
        if lowered in {"false", "no", "0", "none", "disabled", "immutable"}:
            return False
    return bool(value)


def _mint_authority_status(mint_account: Mapping[str, Any]) -> str:
    if "mint_authority" not in mint_account and "mintAuthority" not in mint_account:
        return "MINT_AUTHORITY_UNKNOWN"
    value = mint_account.get("mint_authority", mint_account.get("mintAuthority"))
    return "MINT_AUTHORITY_RENOUNCED" if value in {None, "", False} else "MINT_AUTHORITY_PRESENT"


def _freeze_authority_status(mint_account: Mapping[str, Any]) -> str:
    if "freeze_authority" not in mint_account and "freezeAuthority" not in mint_account:
        return "FREEZE_AUTHORITY_UNKNOWN"
    value = mint_account.get("freeze_authority", mint_account.get("freezeAuthority"))
    return "FREEZE_AUTHORITY_DISABLED" if value in {None, "", False} else "FREEZE_AUTHORITY_PRESENT"


def _metadata_mutability_status(metadata: Mapping[str, Any]) -> str:
    if "mutable" not in metadata and "is_mutable" not in metadata:
        return "METADATA_UNKNOWN"
    mutable = _bool_value(metadata.get("mutable", metadata.get("is_mutable")))
    if mutable is None:
        return "METADATA_UNKNOWN"
    return "METADATA_MUTABLE" if mutable else "METADATA_IMMUTABLE"


def _token_program_label(mint_account: Mapping[str, Any]) -> str:
    program = str(
        mint_account.get("token_program")
        or mint_account.get("program")
        or mint_account.get("owner")
        or ""
    ).lower()
    if not program:
        return "TOKEN_PROGRAM_UNKNOWN"
    if program in {
        "spl_token",
        "spl-token",
        "token",
        "tokenkegqfezyinwajbnbgkpfxcwubvf9ss623vq5da",
        "token_2022",
        "token-2022",
        "tokenzqdn98q4kqizjvh8qdjr8jqhb3qvzcxaq5y",
    }:
        return "SPL_TOKEN_OR_TOKEN_2022_VERIFIED"
    return "TOKEN_PROGRAM_UNSUPPORTED"


def _supply_sanity_label(payload: Mapping[str, Any]) -> str:
    supply = _nested(payload, "supply")
    explicit = supply.get("supply_sanity_label") or payload.get("supply_sanity_label")
    if explicit:
        return str(explicit)
    if _present(supply, "supply") or _present(payload, "supply"):
        return "SUPPLY_SANITY_OK"
    return "SUPPLY_SANITY_UNKNOWN"


def _holder_concentration_label(payload: Mapping[str, Any]) -> str:
    holders = _nested(payload, "holders")
    explicit = holders.get("holder_concentration_label") or payload.get("holder_concentration_label")
    if explicit:
        return str(explicit)
    top_holder = holders.get("top_holder_percent", payload.get("top_holder_percent"))
    top_10 = holders.get("top_10_holder_percent", payload.get("top_10_holder_percent"))
    if top_holder is None and top_10 is None:
        return "HOLDER_CONCENTRATION_UNKNOWN"
    top_holder_f = float(top_holder or 0)
    top_10_f = float(top_10 or 0)
    if top_holder_f >= 30 or top_10_f >= 80:
        return "HOLDER_CONCENTRATION_EXTREME"
    if top_holder_f >= 15 or top_10_f >= 55:
        return "HOLDER_CONCENTRATION_CONCENTRATED"
    return "HOLDER_CONCENTRATION_HEALTHY"


def _liquidity_lock_or_burn_label(payload: Mapping[str, Any]) -> str:
    liquidity = _nested(payload, "liquidity")
    explicit = (
        liquidity.get("liquidity_lock_or_burn_label")
        or payload.get("liquidity_lock_or_burn_label")
    )
    if explicit:
        return str(explicit)
    value = str(
        liquidity.get("lock_or_burn_status")
        or liquidity.get("lock_status")
        or payload.get("lock_or_burn_status")
        or ""
    ).lower()
    if value in {"confirmed", "locked", "burned", "burnt", "lock_or_burn_confirmed"}:
        return "LIQUIDITY_LOCK_OR_BURN_CONFIRMED"
    if value in {"unlocked", "dangerous", "removed"}:
        return "LIQUIDITY_UNLOCKED_OR_DANGEROUS"
    return "LIQUIDITY_LOCK_OR_BURN_UNKNOWN"


def _known_risk_flag_label(payload: Mapping[str, Any]) -> str:
    if "known_risk_flag_label" in payload:
        return str(payload["known_risk_flag_label"])
    if "risk_flags" not in payload:
        return "KNOWN_RISK_FLAGS_UNKNOWN"
    flags = payload.get("risk_flags")
    if flags is None:
        return "KNOWN_RISK_FLAGS_UNKNOWN"
    return "KNOWN_RISK_FLAGS_PRESENT" if flags else "NO_KNOWN_RISK_FLAGS"


def _safety_context_label(evidence: Mapping[str, Any]) -> str:
    clean = (
        evidence["mint_authority_status"] == "MINT_AUTHORITY_RENOUNCED"
        and evidence["freeze_authority_status"] == "FREEZE_AUTHORITY_DISABLED"
        and evidence["metadata_mutability_status"] == "METADATA_IMMUTABLE"
        and evidence["supply_sanity_label"] == "SUPPLY_SANITY_OK"
        and evidence["holder_concentration_label"] == "HOLDER_CONCENTRATION_HEALTHY"
        and evidence["liquidity_lock_or_burn_label"] == "LIQUIDITY_LOCK_OR_BURN_CONFIRMED"
        and evidence["known_risk_flag_label"] == "NO_KNOWN_RISK_FLAGS"
        and evidence["token_program_label"] == "SPL_TOKEN_OR_TOKEN_2022_VERIFIED"
    )
    if clean:
        return "SAFETY_CLEAN"
    if any(
        evidence[field].endswith("_UNKNOWN")
        for field in (
            "mint_authority_status",
            "freeze_authority_status",
            "metadata_mutability_status",
            "supply_sanity_label",
            "holder_concentration_label",
            "liquidity_lock_or_burn_label",
            "known_risk_flag_label",
            "token_program_label",
        )
    ):
        return "SAFETY_UNKNOWN"
    if evidence["token_program_label"] == "TOKEN_PROGRAM_UNSUPPORTED":
        return "SAFETY_UNSAFE"
    return "SAFETY_CAUTION"


def normalize_solana_rpc_safety_fixture_payload(
    payload: Mapping[str, Any],
    *,
    token_id: int,
    snapshot_id: int,
    source_request_id: int,
    source_response_id: int | None = None,
    source_failure_id: int | None = None,
    pair_id: int | None = None,
    memory_window_id: int | None = None,
    evidence_window_id: int | None = None,
) -> dict[str, Any]:
    """Map an explicit fixture payload into safety evidence fields."""

    mint_account = _nested(payload, "mint_account")
    metadata = _nested(payload, "metadata")
    source_status = str(payload.get("source_status") or "COMPLETE")
    data_quality = str(payload.get("data_quality_label") or "CLEAN_DATA")
    evidence = {
        "token_id": token_id,
        "pair_id": pair_id,
        "snapshot_id": snapshot_id,
        "memory_window_id": memory_window_id,
        "evidence_window_id": evidence_window_id,
        "safety_evidence_role": "TOKEN_SAFETY_CONTEXT",
        "source_name": SOLANA_RPC_SOURCE_NAME,
        "source_status": source_status,
        "data_quality_label": data_quality,
        "target_status": str(payload.get("target_status") or "TARGET_MATCH"),
        "evidence_captured_at": str(payload.get("evidence_captured_at") or payload.get("captured_at") or ""),
        "freshness_label": str(payload.get("freshness_label") or "SAFETY_EVIDENCE_FRESH"),
        "mint_authority_status": _mint_authority_status(mint_account),
        "freeze_authority_status": _freeze_authority_status(mint_account),
        "metadata_mutability_status": _metadata_mutability_status(metadata),
        "supply_sanity_label": _supply_sanity_label(payload),
        "holder_concentration_label": _holder_concentration_label(payload),
        "liquidity_lock_or_burn_label": _liquidity_lock_or_burn_label(payload),
        "known_risk_flag_label": _known_risk_flag_label(payload),
        "token_program_label": _token_program_label(mint_account),
        "source_request_id": source_request_id,
        "source_response_id": source_response_id,
        "source_failure_id": source_failure_id,
        "paper_only_context": True,
    }
    if not evidence["evidence_captured_at"]:
        evidence["freshness_label"] = "SAFETY_EVIDENCE_UNKNOWN"
    evidence["safety_context_label"] = _safety_context_label(evidence)
    if source_status in {"FAILED", "STALE", "CONFLICTING"} or data_quality not in {
        "CLEAN_DATA",
        "ACCEPTABLE_PARTIAL_DATA",
    }:
        evidence["safety_context_label"] = "SAFETY_UNKNOWN"
    return evidence


def insert_solana_rpc_safety_evidence_from_source_response(
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
    if row["source_name"] != SOLANA_RPC_SOURCE_NAME:
        raise ValueError("Safety fixture response must come from solana_rpc")
    if row["request_kind"] not in SAFETY_REQUEST_KINDS:
        raise ValueError("Solana RPC response kind is not safety evidence compatible")
    payload = json.loads(row["normalized_payload_json"] or "{}")
    if not isinstance(payload, Mapping):
        raise ValueError("Normalized Solana RPC safety payload must be an object")
    payload = dict(payload)
    payload.setdefault("source_status", row["source_status"])
    payload.setdefault("data_quality_label", row["data_quality_label"])
    payload.setdefault("captured_at", row["received_at"])
    evidence = normalize_solana_rpc_safety_fixture_payload(
        payload,
        token_id=token_id,
        pair_id=pair_id,
        snapshot_id=snapshot_id,
        memory_window_id=memory_window_id,
        evidence_window_id=evidence_window_id,
        source_request_id=int(row["source_request_id"]),
        source_response_id=int(row["id"]),
    )
    return insert_solana_safety_evidence(
        connection,
        evidence,
        scheduler_boundary_label=scheduler_boundary_label,
        operator_approval_label=operator_approval_label,
        caller=caller,
    )

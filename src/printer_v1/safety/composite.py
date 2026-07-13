"""Bounded multi-source safety evidence composition for WINDOW_15M."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.safety.goplus_normalizer import (
    SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY,
    compute_safety_context_label,
    normalize_goplus_safety_response,
    safety_memory_policy_summary,
)


POLICY_VERSION = "V2_4_1_COMPOSITE_SAFETY_V1"
MAX_CONTRIBUTIONS = 2
MAX_AGE_SECONDS = 1800
SAFETY_BLOCKED = "SAFETY_BLOCKED_FOR_15M_MEMORY"

SAFETY_FIELDS = (
    "mint_authority_status",
    "freeze_authority_status",
    "metadata_mutability_status",
    "supply_sanity_label",
    "holder_concentration_label",
    "liquidity_lock_or_burn_label",
    "known_risk_flag_label",
    "token_program_label",
)


def _time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _enum(value: Any) -> str:
    return str(getattr(value, "value", value))


def _execution_contribution(
    connection: sqlite3.Connection,
    execution: Any,
    *,
    category: str,
    token_mint: str,
    pair_address: str,
    fields: Mapping[str, Any],
    evaluated_at: datetime,
) -> dict[str, Any]:
    request_id = int(execution.request_record.id)
    response_id = int(execution.response_record.id) if execution.response_record else None
    failure_id = int(execution.failure_record.id) if execution.failure_record else None
    trace = connection.execute(
        """
        SELECT request.source_name AS request_source,
               response.source_name AS response_source,
               response.source_request_id AS response_request_id
        FROM printer_source_requests request
        LEFT JOIN printer_source_responses response ON response.id = ?
        WHERE request.id = ?
        """,
        (response_id, request_id),
    ).fetchone()
    source_name = str(execution.request_record.source_name)
    captured_at = str(
        execution.response_record.received_at
        if execution.response_record
        else execution.failure_record.failed_at
        if execution.failure_record
        else evaluated_at.isoformat()
    )
    captured = _time(captured_at)
    age = (evaluated_at - captured).total_seconds() if captured else None
    fresh = age is not None and 0 <= age <= MAX_AGE_SECONDS
    payload = dict(execution.normalized_result.normalized_payload or {})
    returned_mint = str(payload.get("token_mint") or token_mint)
    target_match = returned_mint.lower() == token_mint.lower()
    trace_ok = bool(
        trace
        and trace["request_source"] == source_name
        and (
            response_id is None
            or (
                trace["response_source"] == source_name
                and int(trace["response_request_id"]) == request_id
            )
        )
    )
    status = _enum(execution.normalized_result.source_status)
    quality = _enum(execution.normalized_result.data_quality_label)
    rejection = None
    if not trace_ok:
        rejection = "SOURCE_TRACE_MISMATCH"
    elif not target_match:
        rejection = "TARGET_MINT_MISMATCH"
    elif not fresh:
        rejection = "SAFETY_EVIDENCE_STALE"
    elif failure_id is not None or response_id is None:
        rejection = str(execution.normalized_result.failure_type or "SOURCE_FAILED")
    return {
        "source_name": source_name,
        "evidence_category": category,
        "source_request_id": request_id,
        "source_response_id": response_id,
        "source_failure_id": failure_id,
        "captured_at": captured_at,
        "freshness_label": "SAFETY_EVIDENCE_FRESH" if fresh else "SAFETY_EVIDENCE_STALE",
        "token_mint": returned_mint,
        "pair_address": pair_address,
        "fields_supplied": dict(fields),
        "source_status": status,
        "data_quality_label": quality,
        "target_status": "TARGET_MATCH" if target_match else "TARGET_MISMATCH",
        "rejection_reason": rejection,
        "trace_complete": trace_ok and (response_id is not None or failure_id is not None),
        "usable": rejection is None and status in {"COMPLETE", "PARTIAL"} and quality in {"CLEAN_DATA", "ACCEPTABLE_PARTIAL_DATA"},
    }


def _exact_liquidity_danger(payload: Mapping[str, Any], pair_address: str) -> str:
    returned_pair = str(payload.get("pair_address") or payload.get("pool_address") or "")
    state = str(payload.get("liquidity_state") or "").upper()
    if returned_pair.lower() != pair_address.lower():
        return "LIQUIDITY_LOCK_OR_BURN_UNKNOWN"
    if state in {"LP_UNLOCKED", "LIQUIDITY_UNLOCKED", "LIQUIDITY_REMOVED"}:
        return "LIQUIDITY_UNLOCKED_OR_DANGEROUS"
    return "LIQUIDITY_LOCK_OR_BURN_UNKNOWN"


def _provider_risk_evidence(payload: Mapping[str, Any]) -> dict[str, Any]:
    for field in ("risky_flags", "risk_flags", "risks"):
        if field in payload:
            return {"provider_risk_field": field, "provider_risk_value": payload[field]}
    return {"provider_risk_field": None, "provider_risk_value": None}


def persist_safety_composite(
    connection: sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int,
    snapshot_id: int,
    token_mint: str,
    pair_address: str,
    evaluated_at: str,
    goplus_execution: Any,
    holder_execution: Any | None = None,
    memory_window_id: int | None = None,
) -> dict[str, Any]:
    """Persist one bounded safety composite and its independent source traces."""
    connection.row_factory = sqlite3.Row
    evaluated = _time(evaluated_at)
    if evaluated is None:
        raise ValueError("composite safety evaluated_at must be a valid timestamp")

    goplus_payload = dict(goplus_execution.normalized_result.normalized_payload or {})
    if goplus_execution.response_record is not None:
        base = normalize_goplus_safety_response(
            goplus_payload,
            token_id=token_id,
            pair_id=pair_id,
            snapshot_id=snapshot_id,
            memory_window_id=memory_window_id,
            source_request_id=int(goplus_execution.request_record.id),
            source_response_id=int(goplus_execution.response_record.id),
            captured_at=str(goplus_execution.response_record.received_at),
            source_status=_enum(goplus_execution.normalized_result.source_status),
            data_quality_label=_enum(goplus_execution.normalized_result.data_quality_label),
        )
    else:
        base = {
            "mint_authority_status": "MINT_AUTHORITY_UNKNOWN",
            "freeze_authority_status": "FREEZE_AUTHORITY_UNKNOWN",
            "metadata_mutability_status": "METADATA_UNKNOWN",
            "supply_sanity_label": "SUPPLY_SANITY_UNKNOWN",
            "holder_concentration_label": "HOLDER_CONCENTRATION_UNKNOWN",
            "liquidity_lock_or_burn_label": "LIQUIDITY_LOCK_OR_BURN_UNKNOWN",
            "known_risk_flag_label": "KNOWN_RISK_FLAGS_UNKNOWN",
            "token_program_label": "TOKEN_PROGRAM_UNKNOWN",
            "safety_context_label": "SAFETY_UNKNOWN",
        }

    # Pool-specific lock/burn claims are unsupported. Only an exact-pair,
    # explicit unlocked/removed state is retained as dangerous evidence.
    base["liquidity_lock_or_burn_label"] = _exact_liquidity_danger(
        goplus_payload, pair_address
    )
    goplus_fields = {field: base.get(field) for field in SAFETY_FIELDS}
    goplus_fields.update(_provider_risk_evidence(goplus_payload))
    contributions = [
        _execution_contribution(
            connection,
            goplus_execution,
            category="TOKEN_SAFETY",
            token_mint=token_mint,
            pair_address=pair_address,
            fields=goplus_fields,
            evaluated_at=evaluated,
        )
    ]

    holder_labels: list[tuple[str, str]] = []
    if contributions[0]["usable"] and base.get("holder_concentration_label") != "HOLDER_CONCENTRATION_UNKNOWN":
        holder_labels.append(("goplus", str(base["holder_concentration_label"])))
    if holder_execution is not None:
        holder_payload = dict(holder_execution.normalized_result.normalized_payload or {})
        holder_fields = {
            "holder_concentration_label": str(
                holder_payload.get("holder_concentration_label")
                or "HOLDER_CONCENTRATION_UNKNOWN"
            )
        }
        contribution = _execution_contribution(
            connection,
            holder_execution,
            category="HOLDER_CONCENTRATION",
            token_mint=token_mint,
            pair_address=pair_address,
            fields=holder_fields,
            evaluated_at=evaluated,
        )
        contributions.append(contribution)
        if contribution["usable"] and holder_fields["holder_concentration_label"] != "HOLDER_CONCENTRATION_UNKNOWN":
            holder_labels.append(("solana_rpc", holder_fields["holder_concentration_label"]))
    if len(contributions) > MAX_CONTRIBUTIONS:
        raise ValueError("composite safety contribution budget exceeded")

    conflicts: list[str] = []
    distinct_holder_labels = {label for _source, label in holder_labels}
    if len(distinct_holder_labels) > 1:
        conflicts.append("HOLDER_CONCENTRATION_SOURCE_CONFLICT")
        base["holder_concentration_label"] = "HOLDER_CONCENTRATION_UNKNOWN"
    elif holder_labels:
        base["holder_concentration_label"] = holder_labels[0][1]

    base["safety_context_label"] = compute_safety_context_label(base)

    field_bindings = {
        field: "goplus"
        for field in SAFETY_FIELDS
        if field != "holder_concentration_label"
    }
    if holder_labels and not conflicts:
        field_bindings["holder_concentration_label"] = holder_labels[0][0]
    else:
        field_bindings["holder_concentration_label"] = None

    policy = safety_memory_policy_summary(base)
    blockers = list(policy["hard_blocking_safety_fields"])
    if conflicts:
        blockers.extend(conflicts)
    if not contributions[0]["usable"]:
        blockers.append("GOPLUS_MANDATORY_SAFETY_SOURCE_NOT_USABLE")
    provenance_complete = all(item["trace_complete"] for item in contributions)
    if not provenance_complete:
        blockers.append("SAFETY_COMPOSITE_PROVENANCE_INCOMPLETE")
    blockers = list(dict.fromkeys(blockers))
    optional_unknowns = list(policy["source_coverage_pending_fields"])
    contract_label = (
        "SAFETY_CLEAN"
        if not blockers and base.get("safety_context_label") == "SAFETY_CLEAN"
        else SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY
        if not blockers
        else SAFETY_BLOCKED
    )
    target_status = contributions[0]["target_status"]
    freshness_label = contributions[0]["freshness_label"]
    source_status = "CONFLICTING" if conflicts else "COMPLETE" if not blockers else "PARTIAL"
    data_quality = "CONFLICTING_DATA" if conflicts else "CLEAN_DATA" if not blockers else "ACCEPTABLE_PARTIAL_DATA"

    connection.execute(
        """
        INSERT INTO printer_safety_evidence_composites (
            token_id, pair_id, snapshot_id, memory_window_id, policy_version,
            token_mint, pair_address, evidence_captured_at, source_status,
            data_quality_label, target_status, freshness_label,
            mint_authority_status, freeze_authority_status,
            metadata_mutability_status, supply_sanity_label,
            holder_concentration_label, liquidity_lock_or_burn_label,
            known_risk_flag_label, token_program_label, safety_context_label,
            safety_contract_label, provenance_complete, conflicts_json,
            blockers_json, optional_unknowns_json, field_bindings_json,
            paper_only_context
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(token_id, pair_id, snapshot_id, policy_version) DO NOTHING
        """,
        (
            token_id, pair_id, snapshot_id, memory_window_id, POLICY_VERSION,
            token_mint, pair_address, evaluated.isoformat(), source_status,
            data_quality, target_status, freshness_label,
            *(base.get(field) for field in SAFETY_FIELDS),
            base.get("safety_context_label", "SAFETY_UNKNOWN"), contract_label,
            1 if provenance_complete else 0, json.dumps(conflicts),
            json.dumps(blockers), json.dumps(optional_unknowns),
            json.dumps(field_bindings, sort_keys=True),
        ),
    )
    row = connection.execute(
        """
        SELECT * FROM printer_safety_evidence_composites
        WHERE token_id=? AND pair_id=? AND snapshot_id=? AND policy_version=?
        """,
        (token_id, pair_id, snapshot_id, POLICY_VERSION),
    ).fetchone()
    composite_id = int(row["id"])
    for item in contributions:
        connection.execute(
            """
            INSERT OR IGNORE INTO printer_safety_evidence_contributions (
                composite_id, source_name, evidence_category, source_request_id,
                source_response_id, source_failure_id, captured_at,
                freshness_label, token_mint, pair_address, fields_supplied_json,
                source_status, data_quality_label, target_status, rejection_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                composite_id, item["source_name"], item["evidence_category"],
                item["source_request_id"], item["source_response_id"],
                item["source_failure_id"], item["captured_at"],
                item["freshness_label"], item["token_mint"], item["pair_address"],
                json.dumps(item["fields_supplied"], sort_keys=True),
                item["source_status"], item["data_quality_label"],
                item["target_status"], item["rejection_reason"],
            ),
        )
    return {
        "composite_id": composite_id,
        "safety_contract_label": contract_label,
        "holder_concentration_label": base["holder_concentration_label"],
        "liquidity_lock_or_burn_label": base["liquidity_lock_or_burn_label"],
        "known_risk_flag_label": base["known_risk_flag_label"],
        "contribution_count": len(contributions),
        "conflicts": conflicts,
        "blockers": blockers,
        "optional_unknowns": optional_unknowns,
        "inserted": True,
    }


def composite_row_is_acceptable(row: Mapping[str, Any] | None) -> bool:
    return bool(
        row
        and row.get("target_status") == "TARGET_MATCH"
        and row.get("freshness_label") in {"SAFETY_EVIDENCE_FRESH", "SAFETY_EVIDENCE_ACCEPTABLE"}
        and bool(row.get("provenance_complete"))
        and row.get("safety_contract_label") in {"SAFETY_CLEAN", SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY}
        and not json.loads(str(row.get("blockers_json") or "[]"))
    )

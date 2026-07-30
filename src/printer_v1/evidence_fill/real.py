"""Governed real evidence collection path.

Orchestrates Source-Governor-controlled collection of:
1. Solana token safety evidence (via GoPlus free public API)
2. Solana RPC holder concentration fallback (when GoPlus omits top-holder data)
3. Jupiter paper quote realism evidence ENTRY and EXIT (via Jupiter Quote API)

All collection is read-only. No private keys or
execution of any kind. Evidence is stored only when guards pass.
Downstream unlocks (retrieval, paper decisions, positions, PnL) remain false.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3
from typing import Any

from printer_v1.paper_quote.jupiter_fixture import (
    insert_jupiter_quote_fixture_evidence,
    normalize_jupiter_quote_fixture_result,
)
from printer_v1.safety.evidence import insert_solana_safety_evidence
from printer_v1.safety.goplus_normalizer import (
    REQUIRED_CLEAN_SAFETY_FIELDS,
    compute_safety_context_label,
    insert_goplus_safety_evidence_from_source_response,
    normalize_goplus_safety_response,
)
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.governed_execution import execute_source_request_with_governor
from printer_v1.sources.goplus import build_goplus_adapter, build_goplus_token_safety_transport
from printer_v1.sources.jupiter_quote import (
    DEFAULT_PAPER_AMOUNT_LAMPORTS,
    DEFAULT_SLIPPAGE_BPS,
    WSOL_MINT,
    build_jupiter_paper_quote_transport,
    build_jupiter_quote_adapter,
)
from printer_v1.sources.operational_source_contracts import (
    resolve_solana_rpc_configuration,
)
from printer_v1.sources.solana_rpc_holder import (
    SOLANA_PUBLIC_RPC_URL,
    SOLANA_RPC_RATE_LIMIT_FAILURE_TYPE,
    build_solana_rpc_holder_adapter,
    build_solana_rpc_holder_transport,
    redacted_solana_rpc_source,
)


SCHEDULER_BOUNDARY_LABEL = "SCHEDULER_BOUNDARY_PRESENT"
OPERATOR_APPROVAL_LABEL = "OPERATOR_APPROVED_MANUAL_PROOF"
SAFETY_ALLOWED_CALLER = "source_governor_scheduler_operator_flow"
QUOTE_ALLOWED_CALLER = "source_governor_scheduler_operator_flow"


@dataclass(frozen=True)
class RealEvidenceTarget:
    token_id: int
    snapshot_id: int
    token_mint: str
    pair_id: int | None = None
    memory_window_id: int | None = None
    evidence_window_id: int | None = None


@dataclass(frozen=True)
class RealEvidenceItemResult:
    evidence_type: str
    inserted: bool
    evidence_id: int | None
    clean_eligible: bool
    audit_status: str
    rejection_reasons: tuple[str, ...]
    source_request_id: int | None
    source_response_id: int | None
    source_failure_id: int | None
    downstream_unlocks: dict[str, bool]
    holder_rpc_status: str | None = None
    holder_rpc_failure_type: str | None = None
    holder_rpc_rate_limited: bool = False
    holder_rpc_source_used: str | None = None


@dataclass(frozen=True)
class RealEvidenceFillResult:
    safety_evidence_inserted: int
    quote_evidence_inserted: int
    clean_evidence_inserted: int
    audit_only_evidence_inserted: int
    rejected_or_failed: int
    item_results: tuple[RealEvidenceItemResult, ...]


def _downstream_unlocks_false() -> dict[str, bool]:
    return {
        "clean_memory": False,
        "retrieval": False,
        "paper_decision": False,
        "buy": False,
        "paper_position": False,
        "paper_trade_event": False,
        "pnl": False,
        "lane7": False,
    }


def _read_safety_evidence_row(
    connection: sqlite3.Connection, evidence_id: int
) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM printer_solana_safety_evidence WHERE id = ?", (evidence_id,)
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def _collect_holder_concentration_fallback(
    connection: sqlite3.Connection,
    target: RealEvidenceTarget,
    *,
    goplus_evidence_id: int,
    rpc_transport=None,
    rpc_url: str | None = None,
    fallback_rpc_url: str | None = None,
    timeout_seconds: float = 10.0,
) -> RealEvidenceItemResult | None:
    """Solana RPC holder concentration fallback, used when GoPlus omits top-holder data.

    Only runs when the GoPlus safety evidence row has HOLDER_CONCENTRATION_UNKNOWN.
    If the RPC call succeeds, inserts a new merged safety evidence row with updated
    holder_concentration_label. No downstream unlocks are triggered.
    Returns None if the fallback is not needed (GoPlus already provided holder data).
    """
    goplus_row = _read_safety_evidence_row(connection, goplus_evidence_id)
    if goplus_row is None:
        return None
    if goplus_row.get("holder_concentration_label") != "HOLDER_CONCENTRATION_UNKNOWN":
        return None  # GoPlus already provided holder data

    resolved_rpc_url = (
        str(rpc_url).strip()
        if rpc_url is not None and str(rpc_url).strip()
        else resolve_solana_rpc_configuration().url
    )
    attempts: list[tuple[str, str, Any]] = []
    if rpc_transport is not None:
        attempts.append(("configured_transport", "configured_transport", rpc_transport))
    else:
        attempts.append((
            "primary",
            redacted_solana_rpc_source(resolved_rpc_url),
            build_solana_rpc_holder_transport(
                target.token_mint,
                rpc_url=resolved_rpc_url,
                timeout_seconds=timeout_seconds,
            ),
        ))
        if fallback_rpc_url:
            attempts.append((
                "fallback",
                redacted_solana_rpc_source(fallback_rpc_url),
                build_solana_rpc_holder_transport(
                    target.token_mint,
                    rpc_url=fallback_rpc_url,
                    timeout_seconds=timeout_seconds,
                ),
            ))

    rate_limited_seen = False
    last_failure: RealEvidenceItemResult | None = None
    for attempt_label, redacted_source, transport in attempts:
        adapter = build_solana_rpc_holder_adapter(enabled=True, fixture_transport=transport)
        source_request = build_governed_source_request(
            "solana_rpc",
            "holder_concentration_reference",
            request_key=f"real-holder-rpc-{attempt_label}-token-{target.token_id}-snap-{target.snapshot_id}",
            payload={
                "token_mint": target.token_mint,
                "token_id": target.token_id,
                "snapshot_id": target.snapshot_id,
                "rpc_source": redacted_source,
            },
        )
        governed = execute_source_request_with_governor(connection, source_request, adapter)

        req_id = governed.request_record.id
        resp_id = governed.response_record.id if governed.response_record else None
        fail_id = governed.failure_record.id if governed.failure_record else None

        if governed.response_record is None:
            failure_type = governed.normalized_result.failure_type or "rpc_source_failed"
            rate_limited_seen = rate_limited_seen or failure_type == SOLANA_RPC_RATE_LIMIT_FAILURE_TYPE
            last_failure = RealEvidenceItemResult(
                evidence_type="solana_rpc_holder",
                inserted=False,
                evidence_id=None,
                clean_eligible=False,
                audit_status="SOURCE_REQUEST_FAILED",
                rejection_reasons=(failure_type,),
                source_request_id=req_id,
                source_response_id=None,
                source_failure_id=fail_id,
                downstream_unlocks=_downstream_unlocks_false(),
                holder_rpc_status="FAILED",
                holder_rpc_failure_type=failure_type,
                holder_rpc_rate_limited=rate_limited_seen,
                holder_rpc_source_used=redacted_source,
            )
            continue

        norm = governed.normalized_result.normalized_payload
        holder_label = str(norm.get("holder_concentration_label") or "HOLDER_CONCENTRATION_UNKNOWN")

        # Validate token_mint from RPC payload matches target (mismatch means wrong account set)
        rpc_mint = str(norm.get("token_mint") or "")
        if rpc_mint and rpc_mint != target.token_mint:
            return RealEvidenceItemResult(
                evidence_type="solana_rpc_holder",
                inserted=False,
                evidence_id=None,
                clean_eligible=False,
                audit_status="REJECTED_TARGET_MINT_MISMATCH",
                rejection_reasons=("RPC_HOLDER_TARGET_MINT_MISMATCH",),
                source_request_id=req_id,
                source_response_id=resp_id,
                source_failure_id=fail_id,
                downstream_unlocks=_downstream_unlocks_false(),
                holder_rpc_status="FAILED",
                holder_rpc_failure_type="RPC_HOLDER_TARGET_MINT_MISMATCH",
                holder_rpc_rate_limited=rate_limited_seen,
                holder_rpc_source_used=redacted_source,
            )

        if holder_label == "HOLDER_CONCENTRATION_UNKNOWN":
            return RealEvidenceItemResult(
                evidence_type="solana_rpc_holder",
                inserted=False,
                evidence_id=None,
                clean_eligible=False,
                audit_status="HOLDER_CONCENTRATION_UNRESOLVED_FROM_RPC",
                rejection_reasons=("RPC_HOLDER_CONCENTRATION_STILL_UNKNOWN",),
                source_request_id=req_id,
                source_response_id=resp_id,
                source_failure_id=fail_id,
                downstream_unlocks=_downstream_unlocks_false(),
                holder_rpc_status="COMPLETE",
                holder_rpc_failure_type=None,
                holder_rpc_rate_limited=rate_limited_seen,
                holder_rpc_source_used=redacted_source,
            )

        # Build merged safety evidence row: all GoPlus fields + RPC holder label
        from datetime import datetime, timezone as _tz
        merged: dict[str, Any] = {
            "token_id": target.token_id,
            "pair_id": target.pair_id,
            "snapshot_id": target.snapshot_id,
            "memory_window_id": target.memory_window_id,
            "evidence_window_id": target.evidence_window_id,
            "safety_evidence_role": "TOKEN_SAFETY_CONTEXT",
            "source_name": goplus_row.get("source_name", "goplus"),
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
            "target_status": "TARGET_MATCH",
            "evidence_captured_at": datetime.now(_tz.utc).isoformat(),
            "freshness_label": "SAFETY_EVIDENCE_FRESH",
            "mint_authority_status": goplus_row.get("mint_authority_status", "MINT_AUTHORITY_UNKNOWN"),
            "freeze_authority_status": goplus_row.get("freeze_authority_status", "FREEZE_AUTHORITY_UNKNOWN"),
            "metadata_mutability_status": goplus_row.get("metadata_mutability_status", "METADATA_UNKNOWN"),
            "supply_sanity_label": goplus_row.get("supply_sanity_label", "SUPPLY_SANITY_UNKNOWN"),
            "holder_concentration_label": holder_label,  # filled by RPC
            "liquidity_lock_or_burn_label": goplus_row.get("liquidity_lock_or_burn_label", "LIQUIDITY_LOCK_OR_BURN_UNKNOWN"),
            "known_risk_flag_label": goplus_row.get("known_risk_flag_label", "KNOWN_RISK_FLAGS_UNKNOWN"),
            "token_program_label": goplus_row.get("token_program_label", "SPL_TOKEN_OR_TOKEN_2022_VERIFIED"),
            # Source trace: point to the RPC governed request (this is the evidence enrichment step)
            "source_request_id": req_id,
            "source_response_id": resp_id,
            "source_failure_id": None,
            "paper_only_context": True,
        }
        merged["safety_context_label"] = compute_safety_context_label(merged)

        insert_result = insert_solana_safety_evidence(
            connection,
            merged,
            scheduler_boundary_label=SCHEDULER_BOUNDARY_LABEL,
            operator_approval_label=OPERATOR_APPROVAL_LABEL,
            caller=SAFETY_ALLOWED_CALLER,
        )
        return RealEvidenceItemResult(
            evidence_type="solana_rpc_holder",
            inserted=insert_result.inserted,
            evidence_id=insert_result.evidence_id,
            clean_eligible=insert_result.clean_eligible,
            audit_status=insert_result.audit_status,
            rejection_reasons=insert_result.rejection_reasons,
            source_request_id=req_id,
            source_response_id=resp_id,
            source_failure_id=fail_id,
            downstream_unlocks=insert_result.downstream_unlocks,
            holder_rpc_status="COMPLETE",
            holder_rpc_failure_type=None,
            holder_rpc_rate_limited=rate_limited_seen,
            holder_rpc_source_used=redacted_source,
        )

    return last_failure


def _collect_safety_evidence(
    connection: sqlite3.Connection,
    target: RealEvidenceTarget,
    *,
    goplus_transport=None,
    timeout_seconds: float = 10.0,
) -> RealEvidenceItemResult:
    transport = goplus_transport or build_goplus_token_safety_transport(
        target.token_mint, timeout_seconds=timeout_seconds
    )
    adapter = build_goplus_adapter(enabled=True, fixture_transport=transport)
    source_request = build_governed_source_request(
        "goplus",
        "safety_reference",
        request_key=f"real-safety-token-{target.token_id}-snap-{target.snapshot_id}",
        payload={
            "token_mint": target.token_mint,
            "token_id": target.token_id,
            "snapshot_id": target.snapshot_id,
        },
    )
    governed = execute_source_request_with_governor(connection, source_request, adapter)

    req_id = governed.request_record.id
    resp_id = governed.response_record.id if governed.response_record else None
    fail_id = governed.failure_record.id if governed.failure_record else None

    if governed.response_record is None:
        return RealEvidenceItemResult(
            evidence_type="goplus_safety",
            inserted=False,
            evidence_id=None,
            clean_eligible=False,
            audit_status="SOURCE_REQUEST_FAILED",
            rejection_reasons=(governed.normalized_result.failure_type or "source_failed",),
            source_request_id=req_id,
            source_response_id=None,
            source_failure_id=fail_id,
            downstream_unlocks=_downstream_unlocks_false(),
        )

    insert_result = insert_goplus_safety_evidence_from_source_response(
        connection,
        source_response_id=int(governed.response_record.id),
        token_id=target.token_id,
        pair_id=target.pair_id,
        snapshot_id=target.snapshot_id,
        memory_window_id=target.memory_window_id,
        evidence_window_id=target.evidence_window_id,
        scheduler_boundary_label=SCHEDULER_BOUNDARY_LABEL,
        operator_approval_label=OPERATOR_APPROVAL_LABEL,
        caller=SAFETY_ALLOWED_CALLER,
    )
    return RealEvidenceItemResult(
        evidence_type="goplus_safety",
        inserted=insert_result.inserted,
        evidence_id=insert_result.evidence_id,
        clean_eligible=insert_result.clean_eligible,
        audit_status=insert_result.audit_status,
        rejection_reasons=insert_result.rejection_reasons,
        source_request_id=req_id,
        source_response_id=resp_id,
        source_failure_id=fail_id,
        downstream_unlocks=insert_result.downstream_unlocks,
    )


def _collect_quote_evidence(
    connection: sqlite3.Connection,
    target: RealEvidenceTarget,
    *,
    quote_direction: str,
    input_mint: str,
    output_mint: str,
    amount_lamports: int = DEFAULT_PAPER_AMOUNT_LAMPORTS,
    slippage_bps: int = DEFAULT_SLIPPAGE_BPS,
    quote_transport=None,
    timeout_seconds: float = 8.0,
) -> RealEvidenceItemResult:
    direction = quote_direction.upper()
    transport = quote_transport or build_jupiter_paper_quote_transport(
        input_mint=input_mint,
        output_mint=output_mint,
        amount_lamports=amount_lamports,
        slippage_bps=slippage_bps,
        timeout_seconds=timeout_seconds,
    )
    adapter = build_jupiter_quote_adapter(enabled=True, fixture_transport=transport)
    source_request = build_governed_source_request(
        "jupiter_quote",
        "paper_quote_realism",
        request_key=f"real-quote-{direction.lower()}-token-{target.token_id}-snap-{target.snapshot_id}",
        payload={
            "token_mint": target.token_mint,
            "token_id": target.token_id,
            "snapshot_id": target.snapshot_id,
            "quote_direction": direction,
            "input_mint": input_mint,
            "output_mint": output_mint,
            "amount_lamports": amount_lamports,
        },
    )
    governed = execute_source_request_with_governor(connection, source_request, adapter)

    req_id = governed.request_record.id
    resp_id = governed.response_record.id if governed.response_record else None
    fail_id = governed.failure_record.id if governed.failure_record else None

    insert_result = insert_jupiter_quote_fixture_evidence(
        connection,
        governed.normalized_result,
        request_record=governed.request_record,
        response_record=governed.response_record,
        failure_record=governed.failure_record,
        quote_direction=direction,
        token_id=target.token_id,
        pair_id=target.pair_id,
        snapshot_id=target.snapshot_id,
        memory_window_id=target.memory_window_id,
        evidence_window_id=target.evidence_window_id,
        scheduler_boundary_label=SCHEDULER_BOUNDARY_LABEL,
        operator_approval_label=OPERATOR_APPROVAL_LABEL,
        caller=QUOTE_ALLOWED_CALLER,
    )
    return RealEvidenceItemResult(
        evidence_type=f"jupiter_quote_{direction.lower()}",
        inserted=insert_result.inserted,
        evidence_id=insert_result.evidence_id,
        clean_eligible=insert_result.clean_eligible,
        audit_status=insert_result.audit_status,
        rejection_reasons=insert_result.rejection_reasons,
        source_request_id=req_id,
        source_response_id=resp_id,
        source_failure_id=fail_id,
        downstream_unlocks=insert_result.downstream_unlocks,
    )


def collect_real_evidence(
    connection: sqlite3.Connection,
    target: RealEvidenceTarget,
    *,
    paper_amount_lamports: int = DEFAULT_PAPER_AMOUNT_LAMPORTS,
    slippage_bps: int = DEFAULT_SLIPPAGE_BPS,
    paper_quote_currency_mint: str = WSOL_MINT,
    safety_transport=None,
    holder_rpc_transport=None,
    holder_rpc_url: str | None = None,
    holder_rpc_fallback_url: str | None = None,
    entry_quote_transport=None,
    exit_quote_transport=None,
    safety_timeout_seconds: float = 10.0,
    holder_rpc_timeout_seconds: float = 10.0,
    quote_timeout_seconds: float = 8.0,
) -> RealEvidenceFillResult:
    """Collect safety + (optional RPC holder) + entry/exit quote evidence for one target.

    All collection is read-only and Source Governor controlled.
    Downstream tables (memory, retrieval, paper decisions, positions, PnL)
    are not touched. Only printer_solana_safety_evidence and
    printer_paper_quote_evidence rows may be written when guards pass.

    If GoPlus returns HOLDER_CONCENTRATION_UNKNOWN, a Solana RPC fallback is
    attempted. The fallback inserts a new merged safety evidence row when it
    can improve holder_concentration_label. Downstream unlocks remain False.
    """
    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("real evidence collection requires a caller-provided SQLite connection")

    item_results: list[RealEvidenceItemResult] = []

    safety_result = _collect_safety_evidence(
        connection,
        target,
        goplus_transport=safety_transport,
        timeout_seconds=safety_timeout_seconds,
    )
    item_results.append(safety_result)

    # Holder concentration RPC fallback — only when GoPlus evidence was inserted
    # and has HOLDER_CONCENTRATION_UNKNOWN.
    if safety_result.inserted and safety_result.evidence_id is not None:
        holder_fallback = _collect_holder_concentration_fallback(
            connection,
            target,
            goplus_evidence_id=safety_result.evidence_id,
            rpc_transport=holder_rpc_transport,
            rpc_url=holder_rpc_url,
            fallback_rpc_url=holder_rpc_fallback_url,
            timeout_seconds=holder_rpc_timeout_seconds,
        )
        if holder_fallback is not None:
            item_results.append(holder_fallback)

    entry_result = _collect_quote_evidence(
        connection,
        target,
        quote_direction="ENTRY",
        input_mint=paper_quote_currency_mint,
        output_mint=target.token_mint,
        amount_lamports=paper_amount_lamports,
        slippage_bps=slippage_bps,
        quote_transport=entry_quote_transport,
        timeout_seconds=quote_timeout_seconds,
    )
    item_results.append(entry_result)

    exit_result = _collect_quote_evidence(
        connection,
        target,
        quote_direction="EXIT",
        input_mint=target.token_mint,
        output_mint=paper_quote_currency_mint,
        amount_lamports=paper_amount_lamports,
        slippage_bps=slippage_bps,
        quote_transport=exit_quote_transport,
        timeout_seconds=quote_timeout_seconds,
    )
    item_results.append(exit_result)

    safety_inserted = sum(1 for r in item_results if r.evidence_type in {"goplus_safety", "solana_rpc_holder"} and r.inserted)
    quote_inserted = sum(1 for r in item_results if r.evidence_type.startswith("jupiter_quote_") and r.inserted)
    clean_inserted = sum(1 for r in item_results if r.inserted and r.clean_eligible)
    audit_inserted = sum(1 for r in item_results if r.inserted and not r.clean_eligible)
    rejected_or_failed = sum(1 for r in item_results if not r.inserted)

    return RealEvidenceFillResult(
        safety_evidence_inserted=safety_inserted,
        quote_evidence_inserted=quote_inserted,
        clean_evidence_inserted=clean_inserted,
        audit_only_evidence_inserted=audit_inserted,
        rejected_or_failed=rejected_or_failed,
        item_results=tuple(item_results),
    )

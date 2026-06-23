"""Fixture-only Jupiter paper quote evidence normalizer.

This module converts caller-supplied governed fixture payloads into the
existing paper quote evidence insert helper shape. It has no external source
client and performs no collection by itself.
"""

from __future__ import annotations

from collections.abc import Mapping
import sqlite3
from typing import Any

from printer_v1.paper_quote.evidence import (
    ALLOWED_CALLER,
    PaperQuoteEvidenceInsertResult,
    insert_paper_quote_evidence,
)
from printer_v1.sources.contracts import (
    NormalizedSourceResult,
    SourceFailureRecord,
    SourceRequestRecord,
    SourceResponseRecord,
)


SOURCE_NAME = "jupiter_quote"
REQUEST_KIND = "paper_quote_realism"
QUOTE_PURPOSE = "PAPER_REALISM_ONLY"

ACCEPTABLE_SLIPPAGE_BPS = 100
ACCEPTABLE_PRICE_IMPACT_BPS = 100


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _direction_payload(payload: Mapping[str, Any], quote_direction: str) -> Mapping[str, Any]:
    nested = payload.get(quote_direction.lower())
    if isinstance(nested, Mapping):
        return nested
    quotes = payload.get("quotes")
    if isinstance(quotes, Mapping):
        quoted = quotes.get(quote_direction.lower()) or quotes.get(quote_direction)
        if isinstance(quoted, Mapping):
            return quoted
    return payload


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1", "available"}:
            return True
        if lowered in {"false", "no", "0", "unavailable"}:
            return False
    return None


def _numeric_bps(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _slippage_label(quote: Mapping[str, Any]) -> str:
    explicit = quote.get("slippage_context_label")
    if explicit:
        return str(explicit)
    bps = _numeric_bps(quote.get("slippage_bps"))
    if bps is None:
        return "SLIPPAGE_UNKNOWN"
    if bps <= ACCEPTABLE_SLIPPAGE_BPS:
        return "SLIPPAGE_ACCEPTABLE"
    return "SLIPPAGE_CAUTION"


def _price_impact_label(quote: Mapping[str, Any]) -> str:
    explicit = quote.get("price_impact_context_label")
    if explicit:
        return str(explicit)
    bps = _numeric_bps(quote.get("price_impact_bps"))
    if bps is None:
        return "PRICE_IMPACT_UNKNOWN"
    if bps <= ACCEPTABLE_PRICE_IMPACT_BPS:
        return "PRICE_IMPACT_ACCEPTABLE"
    return "PRICE_IMPACT_CAUTION"


def _quote_failure_label(
    *,
    source_status: str,
    target_status: str,
    paper_only_context: bool,
    freshness_label: str,
    route_available: bool | None,
    route_plan_present: bool | None,
) -> str | None:
    if paper_only_context is not True:
        return "QUOTE_NOT_PAPER_ONLY_FAILURE"
    if target_status != "TARGET_MATCH":
        return "QUOTE_TARGET_MISMATCH_FAILURE"
    if source_status == "FAILED":
        return "QUOTE_SOURCE_FAILED"
    if freshness_label == "QUOTE_STALE":
        return "QUOTE_STALE_FAILURE"
    if route_available is False or route_plan_present is False:
        return "NO_ROUTE_AVAILABLE"
    if route_available is None or route_plan_present is None:
        return "QUOTE_UNKNOWN_FAILURE"
    return None


def _quote_context_label(
    *,
    source_status: str,
    target_status: str,
    paper_only_context: bool,
    freshness_label: str,
    route_available: bool | None,
    route_plan_present: bool | None,
) -> str:
    if paper_only_context is not True:
        return "QUOTE_NOT_PAPER_ONLY"
    if target_status != "TARGET_MATCH":
        return "QUOTE_TARGET_MISMATCH"
    if source_status == "FAILED":
        return "QUOTE_FAILED"
    if freshness_label == "QUOTE_STALE":
        return "QUOTE_STALE"
    if route_available is True and route_plan_present is True:
        return "QUOTE_ROUTE_AVAILABLE"
    if route_available is False or route_plan_present is False:
        return "QUOTE_ROUTE_UNAVAILABLE"
    return "QUOTE_UNKNOWN"


def _realism_labels(
    *,
    quote_direction: str,
    quote_context_label: str,
    slippage_context_label: str,
    price_impact_context_label: str,
) -> tuple[str, str]:
    entry_label = "ENTRY_UNKNOWN"
    exit_label = "EXIT_UNKNOWN"
    if quote_context_label == "QUOTE_ROUTE_AVAILABLE":
        caution = (
            slippage_context_label != "SLIPPAGE_ACCEPTABLE"
            or price_impact_context_label != "PRICE_IMPACT_ACCEPTABLE"
        )
        if quote_direction == "ENTRY":
            entry_label = "ENTRY_REALISM_CAUTION" if caution else "ENTRY_ROUTE_AVAILABLE"
        else:
            exit_label = "EXIT_REALISM_CAUTION" if caution else "EXIT_ROUTE_AVAILABLE"
    elif quote_context_label == "QUOTE_ROUTE_UNAVAILABLE":
        if quote_direction == "ENTRY":
            entry_label = "ENTRY_ROUTE_UNAVAILABLE"
        else:
            exit_label = "EXIT_ROUTE_UNAVAILABLE"
    return entry_label, exit_label


def normalize_jupiter_quote_fixture_payload(
    payload: Mapping[str, Any],
    *,
    quote_direction: str,
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
) -> dict[str, Any]:
    """Build one paper quote evidence row from an explicit fixture payload."""

    direction = quote_direction.upper()
    if direction not in {"ENTRY", "EXIT"}:
        raise ValueError("quote_direction must be ENTRY or EXIT")

    quote = _direction_payload(payload, direction)
    paper_only_context = quote.get("paper_only_context", payload.get("paper_only_context", True))
    target_status = str(quote.get("target_status", payload.get("target_status", "TARGET_MATCH")))
    freshness_label = str(
        quote.get("freshness_label", payload.get("freshness_label", "QUOTE_FRESH"))
    )
    if source_status == "STALE":
        freshness_label = "QUOTE_STALE"
    if source_status == "FAILED":
        freshness_label = "QUOTE_FAILED"
    route_available = _bool_or_none(quote.get("route_available"))
    route_plan_present = _bool_or_none(quote.get("route_plan_present"))
    slippage_context_label = _slippage_label(quote)
    price_impact_context_label = _price_impact_label(quote)

    quote_context_label = _quote_context_label(
        source_status=source_status,
        target_status=target_status,
        paper_only_context=paper_only_context is True,
        freshness_label=freshness_label,
        route_available=route_available,
        route_plan_present=route_plan_present,
    )
    entry_realism_label, exit_realism_label = _realism_labels(
        quote_direction=direction,
        quote_context_label=quote_context_label,
        slippage_context_label=slippage_context_label,
        price_impact_context_label=price_impact_context_label,
    )
    if route_available is True and route_plan_present is True:
        route_available_label = "ROUTE_AVAILABLE"
    elif route_available is False or route_plan_present is False:
        route_available_label = "ROUTE_UNAVAILABLE"
    else:
        route_available_label = "ROUTE_UNKNOWN"

    captured_at = (
        quote.get("quote_captured_at")
        or quote.get("evidence_captured_at")
        or payload.get("quote_captured_at")
        or payload.get("evidence_captured_at")
        or payload.get("received_at")
    )
    if captured_at is None:
        captured_at = "1970-01-01T00:00:00+00:00"
        if freshness_label == "QUOTE_FRESH":
            freshness_label = "QUOTE_UNKNOWN"

    return {
        "token_id": token_id,
        "pair_id": pair_id,
        "snapshot_id": snapshot_id,
        "memory_window_id": memory_window_id,
        "evidence_window_id": evidence_window_id,
        "quote_evidence_role": f"{direction}_QUOTE_CONTEXT",
        "quote_direction": direction,
        "quote_purpose": str(quote.get("quote_purpose", payload.get("quote_purpose", QUOTE_PURPOSE))),
        "source_name": SOURCE_NAME,
        "source_status": source_status,
        "data_quality_label": data_quality_label,
        "target_status": target_status,
        "evidence_captured_at": str(captured_at),
        "freshness_label": freshness_label,
        "quote_context_label": quote_context_label,
        "entry_realism_label": entry_realism_label,
        "exit_realism_label": exit_realism_label,
        "route_available_label": route_available_label,
        "slippage_context_label": slippage_context_label,
        "price_impact_context_label": price_impact_context_label,
        "liquidity_context_label": quote.get("liquidity_context_label"),
        "quote_failure_label": _quote_failure_label(
            source_status=source_status,
            target_status=target_status,
            paper_only_context=paper_only_context is True,
            freshness_label=freshness_label,
            route_available=route_available,
            route_plan_present=route_plan_present,
        ),
        "source_request_id": source_request_id,
        "source_response_id": source_response_id,
        "source_failure_id": source_failure_id,
        "paper_only_context": paper_only_context is True,
    }


def normalize_jupiter_quote_fixture_result(
    result: NormalizedSourceResult,
    *,
    quote_direction: str,
    token_id: int,
    snapshot_id: int,
    source_request_id: int,
    source_response_id: int | None = None,
    source_failure_id: int | None = None,
    pair_id: int | None = None,
    memory_window_id: int | None = None,
    evidence_window_id: int | None = None,
) -> dict[str, Any]:
    payload = dict(result.normalized_payload or {})
    payload.setdefault("received_at", result.received_at)
    return normalize_jupiter_quote_fixture_payload(
        payload,
        quote_direction=quote_direction,
        token_id=token_id,
        pair_id=pair_id,
        snapshot_id=snapshot_id,
        memory_window_id=memory_window_id,
        evidence_window_id=evidence_window_id,
        source_request_id=source_request_id,
        source_response_id=source_response_id,
        source_failure_id=source_failure_id,
        source_status=str(_value(result.source_status)),
        data_quality_label=str(_value(result.data_quality_label)),
    )


def insert_jupiter_quote_fixture_evidence(
    db_or_connection: sqlite3.Connection,
    result: NormalizedSourceResult,
    *,
    request_record: SourceRequestRecord,
    response_record: SourceResponseRecord | None,
    failure_record: SourceFailureRecord | None = None,
    quote_direction: str,
    token_id: int,
    snapshot_id: int,
    pair_id: int | None = None,
    memory_window_id: int | None = None,
    evidence_window_id: int | None = None,
    scheduler_boundary_label: str,
    operator_approval_label: str,
    caller: str = ALLOWED_CALLER,
) -> PaperQuoteEvidenceInsertResult:
    if request_record.source_name != SOURCE_NAME or request_record.request_kind != REQUEST_KIND:
        raise ValueError("Jupiter paper quote evidence requires a governed jupiter_quote request")
    evidence = normalize_jupiter_quote_fixture_result(
        result,
        quote_direction=quote_direction,
        token_id=token_id,
        pair_id=pair_id,
        snapshot_id=snapshot_id,
        memory_window_id=memory_window_id,
        evidence_window_id=evidence_window_id,
        source_request_id=request_record.id,
        source_response_id=response_record.id if response_record else None,
        source_failure_id=failure_record.id if failure_record else None,
    )
    return insert_paper_quote_evidence(
        db_or_connection,
        evidence,
        scheduler_boundary_label=scheduler_boundary_label,
        operator_approval_label=operator_approval_label,
        caller=caller,
    )

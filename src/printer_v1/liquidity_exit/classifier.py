"""Deterministic Liquidity + Exit classification helpers."""

from datetime import datetime
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.liquidity_exit.contracts import (
    EntryRealismLabel,
    ExitRealismLabel,
    LiquidityDrainLabel,
    LiquidityExitPayloadQualityLabel,
    LiquidityStateLabel,
    PriceImpactLabel,
    QuoteAgeLabel,
    RealismGateLabel,
    RouteLabel,
    SlippageLabel,
)
from printer_v1.liquidity_exit.parser import (
    liquidity_exit_payload_has_required_fields,
    liquidity_exit_payload_is_stale,
)


def max_known(*values: float | None) -> float | None:
    known = [value for value in values if value is not None]
    return max(known) if known else None


def classify_slippage(normalized_payload: Mapping[str, Any]) -> SlippageLabel:
    value = max_known(
        normalized_payload.get("estimated_entry_slippage_percent"),
        normalized_payload.get("estimated_exit_slippage_percent"),
    )
    if value is None:
        return SlippageLabel.SLIPPAGE_UNKNOWN
    if value <= 1.0:
        return SlippageLabel.SLIPPAGE_LOW
    if value <= 3.0:
        return SlippageLabel.SLIPPAGE_MODERATE
    if value <= 8.0:
        return SlippageLabel.SLIPPAGE_HIGH
    return SlippageLabel.SLIPPAGE_EXTREME


def classify_price_impact(normalized_payload: Mapping[str, Any]) -> PriceImpactLabel:
    value = max_known(
        normalized_payload.get("estimated_entry_price_impact_percent"),
        normalized_payload.get("estimated_exit_price_impact_percent"),
    )
    if value is None:
        return PriceImpactLabel.PRICE_IMPACT_UNKNOWN
    if value <= 1.0:
        return PriceImpactLabel.PRICE_IMPACT_LOW
    if value <= 3.0:
        return PriceImpactLabel.PRICE_IMPACT_MODERATE
    if value <= 8.0:
        return PriceImpactLabel.PRICE_IMPACT_HIGH
    return PriceImpactLabel.PRICE_IMPACT_EXTREME


def classify_route_availability(normalized_payload: Mapping[str, Any]) -> RouteLabel:
    route_status = str(normalized_payload.get("route_status") or "").lower()
    route_available = normalized_payload.get("route_available")
    if route_status in {"failed", "error"}:
        return RouteLabel.ROUTE_FAILED
    if route_status in {"stale", "expired"}:
        return RouteLabel.ROUTE_STALE
    if route_available == 0 or route_status in {"not_available", "none", "missing"}:
        return RouteLabel.ROUTE_NOT_AVAILABLE
    if route_status in {"limited", "partial"}:
        return RouteLabel.ROUTE_LIMITED
    if route_available == 1 or route_status in {"available", "ok", "complete"}:
        return RouteLabel.ROUTE_AVAILABLE
    return RouteLabel.ROUTE_UNKNOWN


def classify_quote_age(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> QuoteAgeLabel:
    del now
    age = normalized_payload.get("quote_age_seconds")
    status = str(normalized_payload.get("quote_status") or "").lower()
    if status in {"missing", "none"} or age is None:
        return QuoteAgeLabel.QUOTE_MISSING
    if status in {"expired"}:
        return QuoteAgeLabel.QUOTE_EXPIRED
    if status in {"stale"}:
        return QuoteAgeLabel.QUOTE_STALE
    if age <= 30:
        return QuoteAgeLabel.QUOTE_FRESH
    if age <= 120:
        return QuoteAgeLabel.QUOTE_ACCEPTABLE
    if age <= 300:
        return QuoteAgeLabel.QUOTE_STALE
    return QuoteAgeLabel.QUOTE_EXPIRED


def classify_liquidity_drain(normalized_payload: Mapping[str, Any]) -> LiquidityDrainLabel:
    change = normalized_payload.get("liquidity_change_percent")
    before = normalized_payload.get("liquidity_before_usd")
    after = normalized_payload.get("liquidity_after_usd")
    if change is None and before not in (None, 0) and after is not None:
        change = ((after - before) / before) * 100
    if change is None:
        return LiquidityDrainLabel.LIQUIDITY_DRAIN_UNKNOWN
    if change >= -5:
        return LiquidityDrainLabel.NO_LIQUIDITY_DRAIN
    if change >= -15:
        return LiquidityDrainLabel.MINOR_LIQUIDITY_DRAIN
    if change >= -40:
        return LiquidityDrainLabel.MAJOR_LIQUIDITY_DRAIN
    return LiquidityDrainLabel.SEVERE_LIQUIDITY_DRAIN


def classify_liquidity_state(normalized_payload: Mapping[str, Any]) -> LiquidityStateLabel:
    liquidity = normalized_payload.get("liquidity_usd")
    drain = classify_liquidity_drain(normalized_payload)
    if liquidity is None:
        return LiquidityStateLabel.LIQUIDITY_UNKNOWN
    if drain == LiquidityDrainLabel.SEVERE_LIQUIDITY_DRAIN:
        return LiquidityStateLabel.LIQUIDITY_DANGEROUS
    if drain == LiquidityDrainLabel.MAJOR_LIQUIDITY_DRAIN:
        return LiquidityStateLabel.LIQUIDITY_DRAINING
    if liquidity < 2_500:
        return LiquidityStateLabel.LIQUIDITY_DANGEROUS
    if liquidity < 15_000:
        return LiquidityStateLabel.LIQUIDITY_THIN
    if drain == LiquidityDrainLabel.MINOR_LIQUIDITY_DRAIN:
        return LiquidityStateLabel.LIQUIDITY_UNSTABLE
    if liquidity >= 150_000:
        return LiquidityStateLabel.LIQUIDITY_DEEP
    return LiquidityStateLabel.LIQUIDITY_USABLE


def classify_entry_realism(normalized_payload: Mapping[str, Any]) -> EntryRealismLabel:
    route = classify_route_availability(normalized_payload)
    slippage = classify_slippage(normalized_payload)
    impact = classify_price_impact(normalized_payload)
    liquidity = classify_liquidity_state(normalized_payload)
    quote = classify_quote_age(normalized_payload)
    if route in {RouteLabel.ROUTE_NOT_AVAILABLE, RouteLabel.ROUTE_FAILED}:
        return EntryRealismLabel.ENTRY_BLOCKED_BY_ROUTE
    if route == RouteLabel.ROUTE_UNKNOWN or quote == QuoteAgeLabel.QUOTE_MISSING:
        return EntryRealismLabel.ENTRY_UNKNOWN
    if quote in {QuoteAgeLabel.QUOTE_STALE, QuoteAgeLabel.QUOTE_EXPIRED}:
        return EntryRealismLabel.ENTRY_UNREALISTIC
    if liquidity in {LiquidityStateLabel.LIQUIDITY_DANGEROUS, LiquidityStateLabel.LIQUIDITY_UNKNOWN}:
        return EntryRealismLabel.ENTRY_UNREALISTIC
    if slippage == SlippageLabel.SLIPPAGE_EXTREME or impact == PriceImpactLabel.PRICE_IMPACT_EXTREME:
        return EntryRealismLabel.ENTRY_UNREALISTIC
    if slippage in {SlippageLabel.SLIPPAGE_HIGH, SlippageLabel.SLIPPAGE_MODERATE} or impact in {
        PriceImpactLabel.PRICE_IMPACT_HIGH,
        PriceImpactLabel.PRICE_IMPACT_MODERATE,
    } or route == RouteLabel.ROUTE_LIMITED or liquidity == LiquidityStateLabel.LIQUIDITY_THIN:
        return EntryRealismLabel.ENTRY_POSSIBLE_WITH_SLIPPAGE
    return EntryRealismLabel.ENTRY_REALISTIC


def classify_exit_realism(normalized_payload: Mapping[str, Any]) -> ExitRealismLabel:
    route = classify_route_availability(normalized_payload)
    slippage = classify_slippage(normalized_payload)
    impact = classify_price_impact(normalized_payload)
    liquidity = classify_liquidity_state(normalized_payload)
    quote = classify_quote_age(normalized_payload)
    drain = classify_liquidity_drain(normalized_payload)
    if route in {RouteLabel.ROUTE_NOT_AVAILABLE, RouteLabel.ROUTE_FAILED}:
        return ExitRealismLabel.EXIT_BLOCKED_BY_ROUTE
    if route == RouteLabel.ROUTE_UNKNOWN or quote == QuoteAgeLabel.QUOTE_MISSING:
        return ExitRealismLabel.EXIT_UNKNOWN
    if quote in {QuoteAgeLabel.QUOTE_STALE, QuoteAgeLabel.QUOTE_EXPIRED}:
        return ExitRealismLabel.EXIT_UNREALISTIC
    if liquidity == LiquidityStateLabel.LIQUIDITY_DANGEROUS or drain == LiquidityDrainLabel.SEVERE_LIQUIDITY_DRAIN:
        return ExitRealismLabel.EXIT_UNREALISTIC
    if slippage == SlippageLabel.SLIPPAGE_EXTREME or impact == PriceImpactLabel.PRICE_IMPACT_EXTREME:
        return ExitRealismLabel.EXIT_UNREALISTIC
    if drain == LiquidityDrainLabel.MAJOR_LIQUIDITY_DRAIN or liquidity in {
        LiquidityStateLabel.LIQUIDITY_DRAINING,
        LiquidityStateLabel.LIQUIDITY_UNSTABLE,
        LiquidityStateLabel.LIQUIDITY_THIN,
    }:
        return ExitRealismLabel.EXIT_AT_RISK
    if slippage in {SlippageLabel.SLIPPAGE_HIGH, SlippageLabel.SLIPPAGE_MODERATE} or impact in {
        PriceImpactLabel.PRICE_IMPACT_HIGH,
        PriceImpactLabel.PRICE_IMPACT_MODERATE,
    } or route == RouteLabel.ROUTE_LIMITED:
        return ExitRealismLabel.EXIT_POSSIBLE_WITH_SLIPPAGE
    return ExitRealismLabel.EXIT_REALISTIC


def classify_liquidity_exit_payload_quality(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> LiquidityExitPayloadQualityLabel:
    source_status = SourceStatus(normalized_payload.get("source_status") or SourceStatus.COMPLETE)
    data_quality = DataQualityLabel(
        normalized_payload.get("data_quality_label") or DataQualityLabel.CLEAN_DATA
    )
    if source_status == SourceStatus.CONFLICTING or data_quality == DataQualityLabel.CONFLICTING_DATA:
        return LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_CONFLICTING
    if source_status == SourceStatus.STALE or data_quality == DataQualityLabel.STALE_DATA:
        return LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_STALE
    if source_status == SourceStatus.FAILED or data_quality in {
        DataQualityLabel.DIRTY_DATA,
        DataQualityLabel.MISSING_CRITICAL_DATA,
        DataQualityLabel.DO_NOT_TRAIN,
    }:
        return LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_DO_NOT_USE_FOR_MEMORY
    if liquidity_exit_payload_is_stale(normalized_payload, now):
        return LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_STALE
    if not liquidity_exit_payload_has_required_fields(normalized_payload):
        return LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_UNKNOWN
    required_for_clean = (
        normalized_payload.get("route_available"),
        normalized_payload.get("quote_age_seconds"),
        normalized_payload.get("estimated_entry_slippage_percent"),
        normalized_payload.get("estimated_exit_slippage_percent"),
        normalized_payload.get("estimated_entry_price_impact_percent"),
        normalized_payload.get("estimated_exit_price_impact_percent"),
    )
    if source_status == SourceStatus.PARTIAL or data_quality == DataQualityLabel.ACCEPTABLE_PARTIAL_DATA or any(
        value is None for value in required_for_clean
    ):
        return LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_PARTIAL
    if classify_quote_age(normalized_payload, now) in {
        QuoteAgeLabel.QUOTE_STALE,
        QuoteAgeLabel.QUOTE_EXPIRED,
        QuoteAgeLabel.QUOTE_MISSING,
    }:
        return LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_STALE
    return LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_CLEAN


def classify_realism_gate(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> RealismGateLabel:
    quality = classify_liquidity_exit_payload_quality(normalized_payload, now)
    entry = classify_entry_realism(normalized_payload)
    exit_label = classify_exit_realism(normalized_payload)
    drain = classify_liquidity_drain(normalized_payload)
    if quality == LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_DO_NOT_USE_FOR_MEMORY:
        return RealismGateLabel.REALISM_CONTEXT_DO_NOT_TRAIN
    if quality in {
        LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_STALE,
        LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_CONFLICTING,
        LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_UNKNOWN,
    }:
        return RealismGateLabel.REALISM_CONTEXT_AUDIT_ONLY
    if (
        entry in {EntryRealismLabel.ENTRY_UNREALISTIC, EntryRealismLabel.ENTRY_BLOCKED_BY_ROUTE}
        or exit_label
        in {
            ExitRealismLabel.EXIT_UNREALISTIC,
            ExitRealismLabel.EXIT_BLOCKED_BY_ROUTE,
        }
        or drain == LiquidityDrainLabel.SEVERE_LIQUIDITY_DRAIN
    ):
        return RealismGateLabel.REALISM_CONTEXT_BLOCKED
    if (
        entry == EntryRealismLabel.ENTRY_POSSIBLE_WITH_SLIPPAGE
        or exit_label
        in {
            ExitRealismLabel.EXIT_POSSIBLE_WITH_SLIPPAGE,
            ExitRealismLabel.EXIT_AT_RISK,
        }
        or quality == LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_PARTIAL
    ):
        return RealismGateLabel.REALISM_CONTEXT_CAUTION
    return RealismGateLabel.REALISM_CONTEXT_ACCEPTABLE


def liquidity_exit_context_can_support_clean_memory(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> bool:
    return (
        classify_liquidity_exit_payload_quality(normalized_payload, now)
        == LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_CLEAN
        and classify_realism_gate(normalized_payload, now) == RealismGateLabel.REALISM_CONTEXT_ACCEPTABLE
    )


def liquidity_exit_context_blocks_clean_paper_profit(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> bool:
    return classify_realism_gate(normalized_payload, now) in {
        RealismGateLabel.REALISM_CONTEXT_BLOCKED,
        RealismGateLabel.REALISM_CONTEXT_DO_NOT_TRAIN,
    }

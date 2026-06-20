"""Deterministic market regime classification helpers."""

from datetime import datetime
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.market_regime.contracts import (
    MarketPayloadQualityLabel,
    MarketRegimeLabel,
    MarketTransitionLabel,
)
from printer_v1.market_regime.parser import market_payload_has_required_fields, market_payload_is_stale


def fear_greed_regime(value: int | None) -> MarketRegimeLabel | None:
    if value is None:
        return None
    if value <= 24:
        return MarketRegimeLabel.EXTREME_FEAR
    if value <= 44:
        return MarketRegimeLabel.FEAR
    if value <= 55:
        return MarketRegimeLabel.NEUTRAL
    if value <= 74:
        return MarketRegimeLabel.GREED
    return MarketRegimeLabel.EXTREME_GREED


def classify_market_regime(normalized_payload: Mapping[str, Any]) -> MarketRegimeLabel:
    btc_24h = normalized_payload.get("btc_change_24h")
    sol_24h = normalized_payload.get("sol_change_24h")
    fear_greed_value = normalized_payload.get("fear_greed_value")
    fear_regime = fear_greed_regime(fear_greed_value)

    if btc_24h is None and sol_24h is None:
        return fear_regime or MarketRegimeLabel.UNKNOWN

    btc = float(btc_24h or 0)
    sol = float(sol_24h or 0)
    if abs(btc - sol) >= 8 and (abs(btc) >= 4 or abs(sol) >= 4):
        return MarketRegimeLabel.VOLATILE
    if btc <= -3 and sol <= -4:
        return MarketRegimeLabel.RISK_OFF
    if btc >= 2 and sol >= 3 and (
        fear_regime in {MarketRegimeLabel.GREED, MarketRegimeLabel.EXTREME_GREED}
        or fear_greed_value is None
    ):
        return MarketRegimeLabel.RISK_ON
    if abs(btc) <= 1.5 and abs(sol) <= 2.0:
        return MarketRegimeLabel.CHOPPY
    return fear_regime or MarketRegimeLabel.UNKNOWN


def row_label(snapshot: Mapping[str, Any] | None) -> MarketRegimeLabel | None:
    if snapshot is None:
        return None
    value = (
        snapshot.get("market_regime_label")
        if hasattr(snapshot, "get")
        else snapshot["market_regime_label"]
    )
    return MarketRegimeLabel(value) if value else None


def classify_market_transition(
    previous_snapshot: Mapping[str, Any] | None,
    current_snapshot: Mapping[str, Any],
) -> MarketTransitionLabel:
    previous = row_label(previous_snapshot)
    current = row_label(current_snapshot)
    known = {
        (MarketRegimeLabel.FEAR, MarketRegimeLabel.NEUTRAL): MarketTransitionLabel.FEAR_TO_NEUTRAL,
        (MarketRegimeLabel.NEUTRAL, MarketRegimeLabel.GREED): MarketTransitionLabel.NEUTRAL_TO_GREED,
        (MarketRegimeLabel.GREED, MarketRegimeLabel.EXTREME_GREED): MarketTransitionLabel.GREED_TO_EXTREME_GREED,
        (MarketRegimeLabel.EXTREME_GREED, MarketRegimeLabel.GREED): MarketTransitionLabel.EXTREME_GREED_TO_GREED,
        (MarketRegimeLabel.GREED, MarketRegimeLabel.NEUTRAL): MarketTransitionLabel.GREED_TO_NEUTRAL,
        (MarketRegimeLabel.NEUTRAL, MarketRegimeLabel.FEAR): MarketTransitionLabel.NEUTRAL_TO_FEAR,
        (MarketRegimeLabel.FEAR, MarketRegimeLabel.EXTREME_FEAR): MarketTransitionLabel.FEAR_TO_EXTREME_FEAR,
        (MarketRegimeLabel.RISK_OFF, MarketRegimeLabel.RISK_ON): MarketTransitionLabel.RISK_OFF_TO_RISK_ON,
        (MarketRegimeLabel.RISK_ON, MarketRegimeLabel.RISK_OFF): MarketTransitionLabel.RISK_ON_TO_RISK_OFF,
    }
    if previous == MarketRegimeLabel.CHOPPY and current in {
        MarketRegimeLabel.RISK_ON,
        MarketRegimeLabel.RISK_OFF,
        MarketRegimeLabel.GREED,
        MarketRegimeLabel.FEAR,
    }:
        return MarketTransitionLabel.CHOPPY_TO_TRENDING
    if previous in {
        MarketRegimeLabel.RISK_ON,
        MarketRegimeLabel.RISK_OFF,
        MarketRegimeLabel.GREED,
        MarketRegimeLabel.FEAR,
    } and current == MarketRegimeLabel.CHOPPY:
        return MarketTransitionLabel.TRENDING_TO_CHOPPY
    return known.get((previous, current), MarketTransitionLabel.UNKNOWN_TRANSITION)


def classify_market_payload_quality(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> MarketPayloadQualityLabel:
    source_status = SourceStatus(normalized_payload.get("source_status") or SourceStatus.COMPLETE)
    data_quality = DataQualityLabel(
        normalized_payload.get("data_quality_label") or DataQualityLabel.CLEAN_DATA
    )
    if source_status == SourceStatus.CONFLICTING or data_quality == DataQualityLabel.CONFLICTING_DATA:
        return MarketPayloadQualityLabel.MARKET_CONTEXT_CONFLICTING
    if source_status == SourceStatus.STALE or data_quality == DataQualityLabel.STALE_DATA:
        return MarketPayloadQualityLabel.MARKET_CONTEXT_STALE
    if source_status == SourceStatus.FAILED or data_quality in {
        DataQualityLabel.DIRTY_DATA,
        DataQualityLabel.MISSING_CRITICAL_DATA,
        DataQualityLabel.DO_NOT_TRAIN,
    }:
        return MarketPayloadQualityLabel.MARKET_CONTEXT_DO_NOT_USE_FOR_MEMORY
    if market_payload_is_stale(normalized_payload, now):
        return MarketPayloadQualityLabel.MARKET_CONTEXT_STALE
    if not market_payload_has_required_fields(normalized_payload):
        return MarketPayloadQualityLabel.MARKET_CONTEXT_UNKNOWN
    missing_major_context = normalized_payload.get("btc_price_usd") is None or normalized_payload.get(
        "sol_price_usd"
    ) is None
    if source_status == SourceStatus.PARTIAL or data_quality == DataQualityLabel.ACCEPTABLE_PARTIAL_DATA or missing_major_context:
        return MarketPayloadQualityLabel.MARKET_CONTEXT_PARTIAL
    return MarketPayloadQualityLabel.MARKET_CONTEXT_CLEAN


def market_context_can_support_clean_memory(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> bool:
    return (
        classify_market_payload_quality(normalized_payload, now)
        == MarketPayloadQualityLabel.MARKET_CONTEXT_CLEAN
    )

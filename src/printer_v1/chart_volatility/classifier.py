"""Deterministic Chart / Volatility classification helpers."""

from datetime import datetime
from typing import Any, Mapping

from printer_v1.chart_volatility.contracts import (
    CandlePathLabel,
    ChartMemoryGateLabel,
    ChartPayloadQualityLabel,
    DrawdownRecoveryLabel,
    MomentumLabel,
    RangeBehaviorLabel,
    TrendStructureLabel,
    VolatilityLabel,
)
from printer_v1.chart_volatility.parser import chart_payload_has_required_fields, chart_payload_is_stale
from printer_v1.contracts.enums import DataQualityLabel, SourceStatus


def value(payload: Mapping[str, Any], field: str) -> float | None:
    current = payload.get(field)
    return float(current) if current is not None else None


def classify_volatility(normalized_payload: Mapping[str, Any]) -> VolatilityLabel:
    volatility = value(normalized_payload, "volatility_percent")
    if volatility is None:
        return VolatilityLabel.VOLATILITY_UNKNOWN
    if volatility >= 80:
        return VolatilityLabel.VOLATILITY_EXTREME
    if volatility >= 45:
        return VolatilityLabel.VOLATILITY_HIGH
    if volatility >= 25:
        return VolatilityLabel.VOLATILITY_ELEVATED
    if volatility >= 8:
        return VolatilityLabel.VOLATILITY_NORMAL
    return VolatilityLabel.VOLATILITY_LOW


def classify_trend_structure(normalized_payload: Mapping[str, Any]) -> TrendStructureLabel:
    change = value(normalized_payload, "price_change_percent")
    runup = value(normalized_payload, "max_runup_percent")
    drawdown = value(normalized_payload, "max_drawdown_percent")
    higher_highs = normalized_payload.get("higher_high_count")
    lower_lows = normalized_payload.get("lower_low_count")
    green = normalized_payload.get("green_candle_count")
    red = normalized_payload.get("red_candle_count")
    if change is None:
        return TrendStructureLabel.TREND_UNKNOWN
    if change >= 80 or (runup is not None and runup >= 120):
        return TrendStructureLabel.TREND_PARABOLIC_UP
    if change <= -55 or (drawdown is not None and drawdown <= -55):
        return TrendStructureLabel.TREND_PARABOLIC_DOWN
    if abs(change) <= 5 and (value(normalized_payload, "range_width_percent") or 0) <= 12:
        return TrendStructureLabel.TREND_SIDEWAYS
    if green is not None and red is not None and abs(green - red) <= 1 and (value(normalized_payload, "volatility_percent") or 0) >= 20:
        return TrendStructureLabel.TREND_CHOPPY
    if change > 8 and (higher_highs is None or higher_highs >= max(1, lower_lows or 0)):
        return TrendStructureLabel.TREND_UP
    if change < -8 and (lower_lows is None or lower_lows >= max(1, higher_highs or 0)):
        return TrendStructureLabel.TREND_DOWN
    return TrendStructureLabel.TREND_CHOPPY


def classify_range_behavior(normalized_payload: Mapping[str, Any]) -> RangeBehaviorLabel:
    breakout = value(normalized_payload, "breakout_percent")
    breakdown = value(normalized_payload, "breakdown_percent")
    range_width = value(normalized_payload, "range_width_percent")
    fade = value(normalized_payload, "high_to_close_fade_percent")
    change = value(normalized_payload, "price_change_percent")
    if breakout is not None and breakout >= 15 and fade is not None and fade <= -35:
        return RangeBehaviorLabel.RANGE_FAKEOUT
    if breakout is not None and breakout >= 10:
        return RangeBehaviorLabel.RANGE_BREAKOUT
    if breakdown is not None and breakdown <= -10:
        return RangeBehaviorLabel.RANGE_BREAKDOWN
    if range_width is None:
        return RangeBehaviorLabel.RANGE_UNKNOWN
    if range_width >= 35:
        return RangeBehaviorLabel.RANGE_EXPANDING
    if range_width <= 8 and change is not None and abs(change) <= 5:
        return RangeBehaviorLabel.RANGE_COMPRESSING
    return RangeBehaviorLabel.RANGE_UNKNOWN


def classify_momentum(normalized_payload: Mapping[str, Any]) -> MomentumLabel:
    change = value(normalized_payload, "price_change_percent")
    fade = value(normalized_payload, "high_to_close_fade_percent")
    green_run = normalized_payload.get("consecutive_green_candles")
    red_run = normalized_payload.get("consecutive_red_candles")
    if change is None:
        return MomentumLabel.MOMENTUM_UNKNOWN
    if fade is not None and fade <= -35:
        return MomentumLabel.MOMENTUM_FADING
    if abs(change) <= 5:
        return MomentumLabel.MOMENTUM_STABLE
    if change >= 20 and (green_run or 0) >= 3:
        return MomentumLabel.MOMENTUM_ACCELERATING_UP
    if change <= -20 and (red_run or 0) >= 3:
        return MomentumLabel.MOMENTUM_ACCELERATING_DOWN
    if abs(change) <= 8 and (value(normalized_payload, "volatility_percent") or 0) >= 35:
        return MomentumLabel.MOMENTUM_EXHAUSTED
    return MomentumLabel.MOMENTUM_STABLE


def classify_drawdown_recovery(normalized_payload: Mapping[str, Any]) -> DrawdownRecoveryLabel:
    drawdown = value(normalized_payload, "max_drawdown_percent")
    recovery = value(normalized_payload, "recovery_from_low_percent")
    if drawdown is None:
        return DrawdownRecoveryLabel.DRAWDOWN_RECOVERY_UNKNOWN
    if drawdown >= -3:
        return DrawdownRecoveryLabel.DRAWDOWN_NONE
    if recovery is not None and recovery >= 50:
        return DrawdownRecoveryLabel.RECOVERY_STRONG
    if drawdown <= -35 and (recovery is None or recovery < 10):
        return DrawdownRecoveryLabel.RECOVERY_FAILED
    if recovery is not None and recovery >= 15:
        return DrawdownRecoveryLabel.RECOVERY_WEAK
    if drawdown <= -30:
        return DrawdownRecoveryLabel.DRAWDOWN_SEVERE
    if drawdown <= -12:
        return DrawdownRecoveryLabel.DRAWDOWN_MODERATE
    return DrawdownRecoveryLabel.DRAWDOWN_MINOR


def classify_candle_path(normalized_payload: Mapping[str, Any]) -> CandlePathLabel:
    change = value(normalized_payload, "price_change_percent")
    fade = value(normalized_payload, "high_to_close_fade_percent")
    round_trip = value(normalized_payload, "round_trip_percent")
    recovery = value(normalized_payload, "recovery_from_low_percent")
    green_run = normalized_payload.get("consecutive_green_candles") or 0
    red_run = normalized_payload.get("consecutive_red_candles") or 0
    green = normalized_payload.get("green_candle_count")
    red = normalized_payload.get("red_candle_count")
    if change is None:
        return CandlePathLabel.PATH_UNKNOWN
    if round_trip is not None and round_trip >= 80:
        return CandlePathLabel.PATH_ROUND_TRIP
    if recovery is not None and recovery >= 50 and change >= 10:
        return CandlePathLabel.PATH_V_SHAPED_RECOVERY
    if fade is not None and fade <= -35:
        return CandlePathLabel.PATH_SPIKE_AND_FADE
    if (value(normalized_payload, "max_runup_percent") or 0) >= 30 and change >= 20:
        return CandlePathLabel.PATH_SPIKE_AND_HOLD
    if change >= 12 and green_run >= 3:
        return CandlePathLabel.PATH_STEADY_CLIMB
    if change <= -12 and red_run >= 3:
        return CandlePathLabel.PATH_GRIND_DOWN
    if green is not None and red is not None and abs(green - red) <= 1:
        return CandlePathLabel.PATH_CHOPPY_NOISE
    return CandlePathLabel.PATH_UNKNOWN


def classify_chart_payload_quality(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> ChartPayloadQualityLabel:
    source_status = SourceStatus(normalized_payload.get("source_status") or SourceStatus.COMPLETE)
    data_quality = DataQualityLabel(
        normalized_payload.get("data_quality_label") or DataQualityLabel.CLEAN_DATA
    )
    if source_status == SourceStatus.CONFLICTING or data_quality == DataQualityLabel.CONFLICTING_DATA:
        return ChartPayloadQualityLabel.CHART_CONTEXT_CONFLICTING
    if source_status == SourceStatus.STALE or data_quality == DataQualityLabel.STALE_DATA:
        return ChartPayloadQualityLabel.CHART_CONTEXT_STALE
    if source_status == SourceStatus.FAILED or data_quality in {
        DataQualityLabel.DIRTY_DATA,
        DataQualityLabel.MISSING_CRITICAL_DATA,
        DataQualityLabel.DO_NOT_TRAIN,
    }:
        return ChartPayloadQualityLabel.CHART_CONTEXT_DO_NOT_USE_FOR_MEMORY
    if chart_payload_is_stale(normalized_payload, now):
        return ChartPayloadQualityLabel.CHART_CONTEXT_STALE
    if not chart_payload_has_required_fields(normalized_payload):
        return ChartPayloadQualityLabel.CHART_CONTEXT_UNKNOWN
    clean_fields = (
        "price_change_percent",
        "max_runup_percent",
        "max_drawdown_percent",
        "volatility_percent",
        "candle_count",
    )
    if source_status == SourceStatus.PARTIAL or data_quality == DataQualityLabel.ACCEPTABLE_PARTIAL_DATA or any(
        normalized_payload.get(field) is None for field in clean_fields
    ):
        return ChartPayloadQualityLabel.CHART_CONTEXT_PARTIAL
    return ChartPayloadQualityLabel.CHART_CONTEXT_CLEAN


def chart_context_blocks_clean_memory(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> bool:
    del now
    return classify_volatility(normalized_payload) == VolatilityLabel.VOLATILITY_EXTREME or classify_candle_path(
        normalized_payload
    ) == CandlePathLabel.PATH_ROUND_TRIP


def classify_chart_memory_gate(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> ChartMemoryGateLabel:
    quality = classify_chart_payload_quality(normalized_payload, now)
    if quality == ChartPayloadQualityLabel.CHART_CONTEXT_DO_NOT_USE_FOR_MEMORY:
        return ChartMemoryGateLabel.CHART_CONTEXT_DO_NOT_TRAIN
    if quality in {
        ChartPayloadQualityLabel.CHART_CONTEXT_STALE,
        ChartPayloadQualityLabel.CHART_CONTEXT_CONFLICTING,
        ChartPayloadQualityLabel.CHART_CONTEXT_UNKNOWN,
    }:
        return ChartMemoryGateLabel.CHART_CONTEXT_AUDIT_ONLY
    if chart_context_blocks_clean_memory(normalized_payload, now):
        return ChartMemoryGateLabel.CHART_CONTEXT_DO_NOT_TRAIN
    if quality == ChartPayloadQualityLabel.CHART_CONTEXT_PARTIAL:
        return ChartMemoryGateLabel.CHART_CONTEXT_CAUTION
    return ChartMemoryGateLabel.CHART_CONTEXT_ACCEPTABLE


def chart_context_can_support_clean_memory(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> bool:
    return (
        classify_chart_payload_quality(normalized_payload, now)
        == ChartPayloadQualityLabel.CHART_CONTEXT_CLEAN
        and classify_chart_memory_gate(normalized_payload, now)
        == ChartMemoryGateLabel.CHART_CONTEXT_ACCEPTABLE
    )

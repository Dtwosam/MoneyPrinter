"""Deterministic Micro-Event classification helpers."""

from datetime import datetime
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.micro_event.contracts import (
    HeldTo15mResultLabel,
    LateBuyTrapLabel,
    MicroEventMemoryGateLabel,
    MicroEventMoveLabel,
    MicroEventPayloadQualityLabel,
    MicroEventStateLabel,
    MicroExitRealismLabel,
)
from printer_v1.micro_event.parser import micro_event_payload_has_required_fields, micro_event_payload_is_stale


def number(payload: Mapping[str, Any], field: str) -> float | None:
    value = payload.get(field)
    return float(value) if value is not None else None


def has_usable_exit(payload: Mapping[str, Any]) -> bool:
    return classify_micro_exit_realism(payload) in {
        MicroExitRealismLabel.MICRO_EXIT_REALISTIC,
        MicroExitRealismLabel.MICRO_EXIT_POSSIBLE_WITH_SLIPPAGE,
    }


def classify_micro_exit_realism(normalized_payload: Mapping[str, Any]) -> MicroExitRealismLabel:
    route = normalized_payload.get("route_label")
    slippage = normalized_payload.get("slippage_label")
    impact = normalized_payload.get("price_impact_label")
    exit_label = normalized_payload.get("liquidity_exit_realism_label")
    liquidity_state = normalized_payload.get("liquidity_state_label")
    if route in {"ROUTE_NOT_AVAILABLE", "ROUTE_FAILED"} or exit_label in {"EXIT_BLOCKED_BY_ROUTE", "EXIT_UNREALISTIC"}:
        return MicroExitRealismLabel.MICRO_EXIT_NO_EXIT
    if route is None and exit_label is None and slippage is None and impact is None:
        return MicroExitRealismLabel.MICRO_EXIT_UNKNOWN
    if slippage in {"SLIPPAGE_EXTREME"} or impact in {"PRICE_IMPACT_EXTREME"}:
        return MicroExitRealismLabel.MICRO_EXIT_UNREALISTIC
    if liquidity_state in {"LIQUIDITY_THIN", "LIQUIDITY_UNSTABLE", "LIQUIDITY_DRAINING"} or slippage in {"SLIPPAGE_HIGH"} or impact in {"PRICE_IMPACT_HIGH"}:
        return MicroExitRealismLabel.MICRO_EXIT_FRAGILE
    if slippage in {"SLIPPAGE_MODERATE"} or impact in {"PRICE_IMPACT_MODERATE"}:
        return MicroExitRealismLabel.MICRO_EXIT_POSSIBLE_WITH_SLIPPAGE
    if route in {"ROUTE_AVAILABLE", "ROUTE_LIMITED"} or exit_label in {"EXIT_REALISTIC", "EXIT_POSSIBLE_WITH_SLIPPAGE"}:
        return MicroExitRealismLabel.MICRO_EXIT_REALISTIC
    return MicroExitRealismLabel.MICRO_EXIT_UNKNOWN


def classify_micro_event_move(normalized_payload: Mapping[str, Any]) -> MicroEventMoveLabel:
    change = number(normalized_payload, "price_change_5m_percent")
    fade = number(normalized_payload, "high_to_end_fade_percent")
    wick = number(normalized_payload, "wick_percent")
    drawdown = number(normalized_payload, "max_drawdown_5m_percent")
    if change is None:
        return MicroEventMoveLabel.MOVE_UNKNOWN
    if change <= -12 or (drawdown is not None and drawdown <= -25 and change < 0):
        return MicroEventMoveLabel.MOVE_FAST_DOWN
    if abs(change) <= 5 and fade is not None and fade <= -30:
        return MicroEventMoveLabel.MOVE_WICK_ONLY
    if wick is not None and wick >= 80:
        return MicroEventMoveLabel.MOVE_WICK_ONLY
    if change >= 19.9 and fade is not None and fade <= -30:
        return MicroEventMoveLabel.MOVE_SPIKE_AND_FADE
    if change >= 19.9 and (fade is None or fade > -20):
        return MicroEventMoveLabel.MOVE_SPIKE_AND_HOLD
    if change >= 12:
        return MicroEventMoveLabel.MOVE_FAST_UP
    if abs(change) <= 5 and wick is not None and wick >= 60:
        return MicroEventMoveLabel.MOVE_ROUND_TRIP
    return MicroEventMoveLabel.MOVE_NO_CLEAR_EVENT


def classify_holding_to_15m_result(normalized_payload: Mapping[str, Any]) -> HeldTo15mResultLabel:
    held_change = number(normalized_payload, "held_to_15m_price_change_percent")
    held_liquidity = number(normalized_payload, "held_to_15m_liquidity_usd")
    if held_change is None:
        return HeldTo15mResultLabel.HELD_TO_15M_UNKNOWN
    if held_liquidity is not None and held_liquidity <= 1000:
        return HeldTo15mResultLabel.HELD_TO_15M_DEAD
    if held_change >= 25:
        return HeldTo15mResultLabel.HELD_TO_15M_CONTINUED
    if -5 <= held_change <= 5:
        return HeldTo15mResultLabel.HELD_TO_15M_CONSOLIDATED
    if held_change > 5:
        return HeldTo15mResultLabel.HELD_TO_15M_UNKNOWN
    if held_change <= -45:
        return HeldTo15mResultLabel.HELD_TO_15M_DEAD
    if held_change <= -25:
        return HeldTo15mResultLabel.HELD_TO_15M_DUMPED
    if held_change < -10:
        return HeldTo15mResultLabel.HELD_TO_15M_FADED
    return HeldTo15mResultLabel.HELD_TO_15M_CONSOLIDATED


def classify_late_buy_trap(normalized_payload: Mapping[str, Any]) -> LateBuyTrapLabel:
    held = classify_holding_to_15m_result(normalized_payload)
    fade = number(normalized_payload, "high_to_end_fade_percent")
    change = number(normalized_payload, "price_change_5m_percent")
    if held == HeldTo15mResultLabel.HELD_TO_15M_UNKNOWN:
        return LateBuyTrapLabel.LATE_BUY_TRAP_UNKNOWN
    if change is not None and change >= 20 and held in {
        HeldTo15mResultLabel.HELD_TO_15M_DUMPED,
        HeldTo15mResultLabel.HELD_TO_15M_DEAD,
    }:
        return LateBuyTrapLabel.CONFIRMED_LATE_BUY_TRAP
    if fade is not None and fade <= -30 and held == HeldTo15mResultLabel.HELD_TO_15M_FADED:
        return LateBuyTrapLabel.POSSIBLE_LATE_BUY_TRAP
    return LateBuyTrapLabel.NO_LATE_BUY_TRAP


def classify_micro_event_state(normalized_payload: Mapping[str, Any]) -> MicroEventStateLabel:
    move = classify_micro_event_move(normalized_payload)
    exit_realism = classify_micro_exit_realism(normalized_payload)
    held = classify_holding_to_15m_result(normalized_payload)
    late = classify_late_buy_trap(normalized_payload)
    change = number(normalized_payload, "price_change_5m_percent")
    wick = number(normalized_payload, "wick_percent")
    if change is None:
        return MicroEventStateLabel.MICRO_EVENT_UNKNOWN
    if abs(change) < 8 and (wick is None or wick < 50):
        return MicroEventStateLabel.NO_MICRO_EVENT
    if late == LateBuyTrapLabel.CONFIRMED_LATE_BUY_TRAP:
        return MicroEventStateLabel.LATE_BUY_TRAP
    if change >= 12 and exit_realism == MicroExitRealismLabel.MICRO_EXIT_NO_EXIT:
        return MicroEventStateLabel.FAKE_PUMP_NO_EXIT
    if change >= 12 and exit_realism in {MicroExitRealismLabel.MICRO_EXIT_UNREALISTIC, MicroExitRealismLabel.MICRO_EXIT_FRAGILE}:
        return MicroEventStateLabel.UNTRADABLE_MICRO_PUMP
    if held == HeldTo15mResultLabel.HELD_TO_15M_CONTINUED and change >= 12:
        return MicroEventStateLabel.MICRO_PUMP_TO_SUSTAINED_PUMP
    if held == HeldTo15mResultLabel.HELD_TO_15M_CONSOLIDATED and change >= 12:
        return MicroEventStateLabel.MICRO_PUMP_TO_CONSOLIDATION
    if held in {HeldTo15mResultLabel.HELD_TO_15M_DEAD, HeldTo15mResultLabel.HELD_TO_15M_DUMPED} and change >= 12:
        return MicroEventStateLabel.MICRO_PUMP_TO_DEAD_TOKEN
    if move == MicroEventMoveLabel.MOVE_WICK_ONLY:
        return MicroEventStateLabel.WICK_ONLY_PUMP
    if move == MicroEventMoveLabel.MOVE_FAST_DOWN and number(normalized_payload, "price_high") is not None:
        return MicroEventStateLabel.FAST_PUMP_DUMP
    if move == MicroEventMoveLabel.MOVE_SPIKE_AND_FADE:
        return MicroEventStateLabel.FAKE_PUMP_WITH_EXIT if has_usable_exit(normalized_payload) else MicroEventStateLabel.FAKE_PUMP_NO_EXIT
    if change >= 12 and has_usable_exit(normalized_payload):
        return MicroEventStateLabel.TRADABLE_MICRO_PUMP
    if change >= 12:
        return MicroEventStateLabel.FAST_MICRO_PUMP
    return MicroEventStateLabel.MICRO_EVENT_UNKNOWN


def classify_micro_event_payload_quality(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> MicroEventPayloadQualityLabel:
    source_status = SourceStatus(normalized_payload.get("source_status") or SourceStatus.COMPLETE)
    data_quality = DataQualityLabel(normalized_payload.get("data_quality_label") or DataQualityLabel.CLEAN_DATA)
    if source_status == SourceStatus.CONFLICTING or data_quality == DataQualityLabel.CONFLICTING_DATA:
        return MicroEventPayloadQualityLabel.MICRO_EVENT_CONTEXT_CONFLICTING
    if source_status == SourceStatus.STALE or data_quality == DataQualityLabel.STALE_DATA:
        return MicroEventPayloadQualityLabel.MICRO_EVENT_CONTEXT_STALE
    if source_status == SourceStatus.FAILED or data_quality in {
        DataQualityLabel.DIRTY_DATA,
        DataQualityLabel.MISSING_CRITICAL_DATA,
        DataQualityLabel.DO_NOT_TRAIN,
    }:
        return MicroEventPayloadQualityLabel.MICRO_EVENT_CONTEXT_DO_NOT_USE_FOR_MEMORY
    if micro_event_payload_is_stale(normalized_payload, now):
        return MicroEventPayloadQualityLabel.MICRO_EVENT_CONTEXT_STALE
    if not micro_event_payload_has_required_fields(normalized_payload):
        return MicroEventPayloadQualityLabel.MICRO_EVENT_CONTEXT_UNKNOWN
    if classify_micro_exit_realism(normalized_payload) == MicroExitRealismLabel.MICRO_EXIT_UNKNOWN:
        return MicroEventPayloadQualityLabel.MICRO_EVENT_CONTEXT_PARTIAL
    if source_status == SourceStatus.PARTIAL or data_quality == DataQualityLabel.ACCEPTABLE_PARTIAL_DATA:
        return MicroEventPayloadQualityLabel.MICRO_EVENT_CONTEXT_PARTIAL
    return MicroEventPayloadQualityLabel.MICRO_EVENT_CONTEXT_CLEAN


def micro_event_context_blocks_clean_micro_profit(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> bool:
    del now
    return classify_micro_exit_realism(normalized_payload) in {
        MicroExitRealismLabel.MICRO_EXIT_NO_EXIT,
        MicroExitRealismLabel.MICRO_EXIT_UNREALISTIC,
    } or classify_micro_event_state(normalized_payload) in {
        MicroEventStateLabel.UNTRADABLE_MICRO_PUMP,
        MicroEventStateLabel.FAKE_PUMP_NO_EXIT,
        MicroEventStateLabel.WICK_ONLY_PUMP,
    }


def classify_micro_event_memory_gate(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> MicroEventMemoryGateLabel:
    quality = classify_micro_event_payload_quality(normalized_payload, now)
    state = classify_micro_event_state(normalized_payload)
    if state == MicroEventStateLabel.NO_MICRO_EVENT:
        return MicroEventMemoryGateLabel.MICRO_EVENT_IGNORE
    if quality == MicroEventPayloadQualityLabel.MICRO_EVENT_CONTEXT_DO_NOT_USE_FOR_MEMORY or micro_event_context_blocks_clean_micro_profit(normalized_payload, now):
        return MicroEventMemoryGateLabel.MICRO_EVENT_DO_NOT_TRAIN
    if quality in {
        MicroEventPayloadQualityLabel.MICRO_EVENT_CONTEXT_STALE,
        MicroEventPayloadQualityLabel.MICRO_EVENT_CONTEXT_CONFLICTING,
        MicroEventPayloadQualityLabel.MICRO_EVENT_CONTEXT_UNKNOWN,
    }:
        return MicroEventMemoryGateLabel.MICRO_EVENT_AUDIT_ONLY
    return MicroEventMemoryGateLabel.MICRO_EVENT_SUPPORT_EVIDENCE


def micro_event_context_can_support_clean_memory(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> bool:
    return (
        classify_micro_event_payload_quality(normalized_payload, now)
        == MicroEventPayloadQualityLabel.MICRO_EVENT_CONTEXT_CLEAN
        and classify_micro_event_memory_gate(normalized_payload, now)
        == MicroEventMemoryGateLabel.MICRO_EVENT_SUPPORT_EVIDENCE
    )


def micro_event_context_is_tradable_support_evidence(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> bool:
    return (
        classify_micro_event_state(normalized_payload) == MicroEventStateLabel.TRADABLE_MICRO_PUMP
        and classify_micro_exit_realism(normalized_payload)
        in {MicroExitRealismLabel.MICRO_EXIT_REALISTIC, MicroExitRealismLabel.MICRO_EXIT_POSSIBLE_WITH_SLIPPAGE}
        and micro_event_context_can_support_clean_memory(normalized_payload, now)
    )

"""Deterministic Trading Flow classification helpers."""

from datetime import datetime
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.trading_flow.contracts import (
    FlowDirectionLabel,
    FlowMemoryGateLabel,
    FlowPressureLabel,
    ImbalanceLabel,
    TradingFlowPayloadQualityLabel,
    TxActivityLabel,
    VolumeActivityLabel,
    WalletParticipationLabel,
)
from printer_v1.trading_flow.parser import (
    trading_flow_payload_has_required_fields,
    trading_flow_payload_is_stale,
)


def safe_ratio(left: float | int | None, right: float | int | None) -> float | None:
    if left is None or right is None or right == 0:
        return None
    return float(left) / float(right)


def observed_zero_pair(left: float | int | None, right: float | int | None) -> bool:
    return left == 0 and right == 0


def buy_sell_totals(payload: Mapping[str, Any]) -> tuple[int | None, int | None]:
    buys = payload.get("buys_5m") if payload.get("buys_5m") is not None else payload.get("buys_15m")
    sells = payload.get("sells_5m") if payload.get("sells_5m") is not None else payload.get("sells_15m")
    return buys, sells


def volume_totals(payload: Mapping[str, Any]) -> tuple[float | None, float | None]:
    buy_volume = payload.get("buy_volume_5m") if payload.get("buy_volume_5m") is not None else payload.get("buy_volume_15m")
    sell_volume = payload.get("sell_volume_5m") if payload.get("sell_volume_5m") is not None else payload.get("sell_volume_15m")
    return buy_volume, sell_volume


def classify_imbalance(normalized_payload: Mapping[str, Any]) -> ImbalanceLabel:
    buys, sells = buy_sell_totals(normalized_payload)
    buy_volume, sell_volume = volume_totals(normalized_payload)
    if observed_zero_pair(buys, sells) or observed_zero_pair(buy_volume, sell_volume):
        return ImbalanceLabel.IMBALANCE_BALANCED
    count_ratio = safe_ratio(buys, sells)
    volume_ratio = safe_ratio(buy_volume, sell_volume)
    if count_ratio is None and volume_ratio is None:
        return ImbalanceLabel.IMBALANCE_UNKNOWN
    ratios = [ratio for ratio in (count_ratio, volume_ratio) if ratio is not None]
    if count_ratio is not None and volume_ratio is not None:
        if count_ratio >= 1.5 and volume_ratio <= 0.75:
            return ImbalanceLabel.IMBALANCE_NOISY
        if count_ratio <= 0.75 and volume_ratio >= 1.5:
            return ImbalanceLabel.IMBALANCE_NOISY
    strongest = max(ratios)
    weakest = min(ratios)
    if strongest >= 1.5 and weakest >= 1.15:
        return ImbalanceLabel.IMBALANCE_BUY_HEAVY
    if weakest <= 0.67 and strongest <= 0.87:
        return ImbalanceLabel.IMBALANCE_SELL_HEAVY
    if 0.8 <= weakest and strongest <= 1.25:
        return ImbalanceLabel.IMBALANCE_BALANCED
    return ImbalanceLabel.IMBALANCE_NOISY


def classify_flow_pressure(normalized_payload: Mapping[str, Any]) -> FlowPressureLabel:
    buy_volume, sell_volume = volume_totals(normalized_payload)
    if observed_zero_pair(buy_volume, sell_volume):
        return FlowPressureLabel.PRESSURE_BALANCED
    ratio = safe_ratio(buy_volume, sell_volume)
    if ratio is None:
        buys, sells = buy_sell_totals(normalized_payload)
        if observed_zero_pair(buys, sells):
            return FlowPressureLabel.PRESSURE_BALANCED
        ratio = safe_ratio(buys, sells)
    if ratio is None:
        return FlowPressureLabel.PRESSURE_UNKNOWN
    if ratio >= 2.0:
        return FlowPressureLabel.PRESSURE_STRONG_INFLOW
    if ratio >= 1.25:
        return FlowPressureLabel.PRESSURE_MODERATE_INFLOW
    if ratio <= 0.5:
        return FlowPressureLabel.PRESSURE_STRONG_OUTFLOW
    if ratio <= 0.8:
        return FlowPressureLabel.PRESSURE_MODERATE_OUTFLOW
    return FlowPressureLabel.PRESSURE_BALANCED


def classify_volume_activity(normalized_payload: Mapping[str, Any]) -> VolumeActivityLabel:
    volume = normalized_payload.get("volume_5m") if normalized_payload.get("volume_5m") is not None else normalized_payload.get("volume_15m")
    if volume is None:
        return VolumeActivityLabel.VOLUME_UNKNOWN
    if volume >= 100_000:
        return VolumeActivityLabel.VOLUME_SURGING
    if volume >= 25_000:
        return VolumeActivityLabel.VOLUME_ELEVATED
    if volume >= 5_000:
        return VolumeActivityLabel.VOLUME_NORMAL
    if volume >= 500:
        return VolumeActivityLabel.VOLUME_WEAK
    return VolumeActivityLabel.VOLUME_DEAD


def classify_tx_activity(normalized_payload: Mapping[str, Any]) -> TxActivityLabel:
    txns = normalized_payload.get("txns_5m") if normalized_payload.get("txns_5m") is not None else normalized_payload.get("txns_15m")
    if txns is None:
        return TxActivityLabel.TX_ACTIVITY_UNKNOWN
    if txns >= 120:
        return TxActivityLabel.TX_ACTIVITY_SURGING
    if txns >= 40:
        return TxActivityLabel.TX_ACTIVITY_ELEVATED
    if txns >= 12:
        return TxActivityLabel.TX_ACTIVITY_NORMAL
    if txns >= 3:
        return TxActivityLabel.TX_ACTIVITY_WEAK
    return TxActivityLabel.TX_ACTIVITY_DEAD


def classify_wallet_participation(normalized_payload: Mapping[str, Any]) -> WalletParticipationLabel:
    unique_wallets = normalized_payload.get("unique_wallets_5m") or normalized_payload.get("unique_wallets_15m")
    repeat_wallets = normalized_payload.get("repeat_wallets_5m") or normalized_payload.get("repeat_wallets_15m")
    txns = normalized_payload.get("txns_5m") or normalized_payload.get("txns_15m")
    if unique_wallets is None:
        return WalletParticipationLabel.WALLETS_UNKNOWN
    repeat_ratio = safe_ratio(repeat_wallets, unique_wallets)
    txn_wallet_ratio = safe_ratio(txns, unique_wallets)
    if (repeat_ratio is not None and repeat_ratio >= 3.0) or (
        txn_wallet_ratio is not None and txn_wallet_ratio >= 6.0
    ):
        return WalletParticipationLabel.WALLETS_WASH_LIKE
    if unique_wallets <= 3:
        return WalletParticipationLabel.WALLETS_CONCENTRATED
    if unique_wallets <= 12:
        return WalletParticipationLabel.WALLETS_NARROW_PARTICIPATION
    return WalletParticipationLabel.WALLETS_BROAD_PARTICIPATION


def classify_flow_direction(normalized_payload: Mapping[str, Any]) -> FlowDirectionLabel:
    wallet_label = classify_wallet_participation(normalized_payload)
    imbalance = classify_imbalance(normalized_payload)
    pressure = classify_flow_pressure(normalized_payload)
    volume = classify_volume_activity(normalized_payload)
    tx = classify_tx_activity(normalized_payload)
    if wallet_label == WalletParticipationLabel.WALLETS_WASH_LIKE:
        return FlowDirectionLabel.FLOW_WASH_LIKE
    if imbalance == ImbalanceLabel.IMBALANCE_UNKNOWN and pressure == FlowPressureLabel.PRESSURE_UNKNOWN:
        return FlowDirectionLabel.FLOW_UNKNOWN
    if (
        imbalance == ImbalanceLabel.IMBALANCE_BUY_HEAVY
        and pressure
        in {
            FlowPressureLabel.PRESSURE_STRONG_INFLOW,
            FlowPressureLabel.PRESSURE_MODERATE_INFLOW,
        }
        and volume in {VolumeActivityLabel.VOLUME_SURGING, VolumeActivityLabel.VOLUME_ELEVATED}
    ):
        return FlowDirectionLabel.FLOW_ACCUMULATION
    if imbalance == ImbalanceLabel.IMBALANCE_SELL_HEAVY and pressure in {
        FlowPressureLabel.PRESSURE_STRONG_OUTFLOW,
        FlowPressureLabel.PRESSURE_MODERATE_OUTFLOW,
    }:
        return FlowDirectionLabel.FLOW_DISTRIBUTION
    if volume in {VolumeActivityLabel.VOLUME_WEAK, VolumeActivityLabel.VOLUME_DEAD} and tx in {
        TxActivityLabel.TX_ACTIVITY_WEAK,
        TxActivityLabel.TX_ACTIVITY_DEAD,
    }:
        return FlowDirectionLabel.FLOW_EXHAUSTION
    if imbalance == ImbalanceLabel.IMBALANCE_NOISY and volume in {
        VolumeActivityLabel.VOLUME_SURGING,
        VolumeActivityLabel.VOLUME_ELEVATED,
    }:
        return FlowDirectionLabel.FLOW_ROTATION
    if imbalance == ImbalanceLabel.IMBALANCE_BALANCED:
        return FlowDirectionLabel.FLOW_CHOPPY
    return FlowDirectionLabel.FLOW_CHOPPY


def classify_trading_flow_payload_quality(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> TradingFlowPayloadQualityLabel:
    source_status = SourceStatus(normalized_payload.get("source_status") or SourceStatus.COMPLETE)
    data_quality = DataQualityLabel(
        normalized_payload.get("data_quality_label") or DataQualityLabel.CLEAN_DATA
    )
    if source_status == SourceStatus.CONFLICTING or data_quality == DataQualityLabel.CONFLICTING_DATA:
        return TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CONFLICTING
    if source_status == SourceStatus.STALE or data_quality == DataQualityLabel.STALE_DATA:
        return TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_STALE
    if source_status == SourceStatus.FAILED or data_quality in {
        DataQualityLabel.DIRTY_DATA,
        DataQualityLabel.MISSING_CRITICAL_DATA,
        DataQualityLabel.DO_NOT_TRAIN,
    }:
        return TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_DO_NOT_USE_FOR_MEMORY
    if trading_flow_payload_is_stale(normalized_payload, now):
        return TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_STALE
    if not trading_flow_payload_has_required_fields(normalized_payload):
        return TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_UNKNOWN
    required_for_clean = (
        normalized_payload.get("buys_5m"),
        normalized_payload.get("sells_5m"),
        normalized_payload.get("buy_volume_5m"),
        normalized_payload.get("sell_volume_5m"),
        normalized_payload.get("unique_wallets_5m"),
    )
    if source_status == SourceStatus.PARTIAL or data_quality == DataQualityLabel.ACCEPTABLE_PARTIAL_DATA or any(
        value is None for value in required_for_clean
    ):
        return TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_PARTIAL
    return TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CLEAN


def classify_flow_memory_gate(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> FlowMemoryGateLabel:
    quality = classify_trading_flow_payload_quality(normalized_payload, now)
    direction = classify_flow_direction(normalized_payload)
    if quality == TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_DO_NOT_USE_FOR_MEMORY:
        return FlowMemoryGateLabel.FLOW_CONTEXT_DO_NOT_TRAIN
    if quality in {
        TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_STALE,
        TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CONFLICTING,
        TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_UNKNOWN,
    }:
        return FlowMemoryGateLabel.FLOW_CONTEXT_AUDIT_ONLY
    if direction == FlowDirectionLabel.FLOW_WASH_LIKE:
        return FlowMemoryGateLabel.FLOW_CONTEXT_DO_NOT_TRAIN
    if quality == TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_PARTIAL:
        return FlowMemoryGateLabel.FLOW_CONTEXT_CAUTION
    return FlowMemoryGateLabel.FLOW_CONTEXT_ACCEPTABLE


def trading_flow_context_can_support_clean_memory(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> bool:
    return (
        classify_trading_flow_payload_quality(normalized_payload, now)
        == TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CLEAN
        and classify_flow_memory_gate(normalized_payload, now)
        == FlowMemoryGateLabel.FLOW_CONTEXT_ACCEPTABLE
    )

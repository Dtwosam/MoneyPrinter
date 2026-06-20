"""Deterministic Solana Chain Heat classification helpers."""

from datetime import datetime
from typing import Any, Mapping

from printer_v1.chain_heat.contracts import (
    ChainHeatLabel,
    ChainHeatPayloadQualityLabel,
    SolanaActivityLabel,
    SolanaCongestionLabel,
    SolanaLiquidityLabel,
)
from printer_v1.chain_heat.parser import (
    chain_heat_payload_has_required_fields,
    chain_heat_payload_is_stale,
)
from printer_v1.contracts.enums import DataQualityLabel, SourceStatus


def text_contains(value: Any, *needles: str) -> bool:
    text = str(value or "").lower()
    return any(needle in text for needle in needles)


def classify_solana_activity(normalized_payload: Mapping[str, Any]) -> SolanaActivityLabel:
    hot_pairs = normalized_payload.get("solana_hot_pair_count")
    new_pairs = normalized_payload.get("solana_meme_new_pair_count")
    new_tokens = normalized_payload.get("solana_new_token_count")
    meme_volume = normalized_payload.get("solana_meme_volume_24h")
    tx_count = normalized_payload.get("solana_tx_count_24h")
    observed = [value for value in (hot_pairs, new_pairs, new_tokens, meme_volume, tx_count) if value is not None]
    if not observed:
        return SolanaActivityLabel.ACTIVITY_UNKNOWN
    if (hot_pairs or 0) >= 40 or (new_pairs or 0) >= 80 or (meme_volume or 0) >= 50_000_000:
        return SolanaActivityLabel.ACTIVITY_SURGING
    if (hot_pairs or 0) >= 20 or (new_pairs or 0) >= 35 or (tx_count or 0) >= 25_000_000:
        return SolanaActivityLabel.ACTIVITY_ELEVATED
    if (hot_pairs or 0) <= 2 and (new_pairs or 0) <= 5 and (meme_volume or 0) <= 1_000_000:
        return SolanaActivityLabel.ACTIVITY_DEAD
    if (hot_pairs or 0) <= 8 and (new_pairs or 0) <= 15 and (meme_volume or 0) <= 5_000_000:
        return SolanaActivityLabel.ACTIVITY_WEAK
    return SolanaActivityLabel.ACTIVITY_NORMAL


def classify_solana_liquidity(normalized_payload: Mapping[str, Any]) -> SolanaLiquidityLabel:
    dex_volume = normalized_payload.get("solana_dex_volume_24h")
    meme_liquidity = normalized_payload.get("solana_meme_liquidity_usd")
    stablecoins = normalized_payload.get("solana_stablecoin_supply")
    tvl = normalized_payload.get("solana_tvl_usd")
    observed = [value for value in (dex_volume, meme_liquidity, stablecoins, tvl) if value is not None]
    if not observed:
        return SolanaLiquidityLabel.LIQUIDITY_UNKNOWN
    if (meme_liquidity or 0) >= 10_000_000 and (dex_volume or 0) >= 1_000_000_000:
        return SolanaLiquidityLabel.LIQUIDITY_EXPANDING
    if (meme_liquidity or 0) <= 500_000 or (dex_volume is not None and dex_volume <= 100_000_000):
        return SolanaLiquidityLabel.LIQUIDITY_STRESSED
    if (meme_liquidity or 0) <= 2_000_000 or (stablecoins is not None and stablecoins <= 1_000_000_000):
        return SolanaLiquidityLabel.LIQUIDITY_THINNING
    return SolanaLiquidityLabel.LIQUIDITY_STABLE


def classify_solana_congestion(normalized_payload: Mapping[str, Any]) -> SolanaCongestionLabel:
    fee_context = normalized_payload.get("solana_priority_fee_context")
    congestion_context = normalized_payload.get("solana_congestion_context")
    if text_contains(fee_context, "severe", "very_high") or text_contains(
        congestion_context,
        "severe",
    ):
        return SolanaCongestionLabel.CONGESTION_SEVERE
    if text_contains(fee_context, "high", "elevated") or text_contains(
        congestion_context,
        "high",
        "congested",
    ):
        return SolanaCongestionLabel.CONGESTION_HIGH
    if text_contains(fee_context, "low") or text_contains(congestion_context, "low"):
        return SolanaCongestionLabel.CONGESTION_LOW
    if fee_context is not None or congestion_context is not None:
        return SolanaCongestionLabel.CONGESTION_NORMAL
    return SolanaCongestionLabel.CONGESTION_UNKNOWN


def classify_chain_heat(normalized_payload: Mapping[str, Any]) -> ChainHeatLabel:
    activity = classify_solana_activity(normalized_payload)
    liquidity = classify_solana_liquidity(normalized_payload)
    congestion = classify_solana_congestion(normalized_payload)
    sol_change = normalized_payload.get("sol_change_24h")

    if congestion in {
        SolanaCongestionLabel.CONGESTION_HIGH,
        SolanaCongestionLabel.CONGESTION_SEVERE,
    }:
        return ChainHeatLabel.SOLANA_CONGESTED
    if activity == SolanaActivityLabel.ACTIVITY_UNKNOWN and liquidity == SolanaLiquidityLabel.LIQUIDITY_UNKNOWN and sol_change is None:
        return ChainHeatLabel.SOLANA_UNKNOWN
    if activity == SolanaActivityLabel.ACTIVITY_DEAD:
        return ChainHeatLabel.SOLANA_QUIET
    if activity == SolanaActivityLabel.ACTIVITY_WEAK and liquidity == SolanaLiquidityLabel.LIQUIDITY_STRESSED:
        return ChainHeatLabel.SOLANA_COLD
    if activity == SolanaActivityLabel.ACTIVITY_WEAK or liquidity in {
        SolanaLiquidityLabel.LIQUIDITY_THINNING,
        SolanaLiquidityLabel.LIQUIDITY_STRESSED,
    }:
        return ChainHeatLabel.SOLANA_COOL
    if (
        (sol_change or 0) >= 4
        and activity == SolanaActivityLabel.ACTIVITY_SURGING
        and liquidity == SolanaLiquidityLabel.LIQUIDITY_EXPANDING
    ):
        return ChainHeatLabel.SOLANA_HOT
    if activity in {
        SolanaActivityLabel.ACTIVITY_SURGING,
        SolanaActivityLabel.ACTIVITY_ELEVATED,
    } or (sol_change or 0) >= 2:
        return ChainHeatLabel.SOLANA_WARM
    return ChainHeatLabel.SOLANA_NEUTRAL


def classify_chain_heat_payload_quality(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> ChainHeatPayloadQualityLabel:
    source_status = SourceStatus(normalized_payload.get("source_status") or SourceStatus.COMPLETE)
    data_quality = DataQualityLabel(
        normalized_payload.get("data_quality_label") or DataQualityLabel.CLEAN_DATA
    )
    if source_status == SourceStatus.CONFLICTING or data_quality == DataQualityLabel.CONFLICTING_DATA:
        return ChainHeatPayloadQualityLabel.CHAIN_HEAT_CONTEXT_CONFLICTING
    if source_status == SourceStatus.STALE or data_quality == DataQualityLabel.STALE_DATA:
        return ChainHeatPayloadQualityLabel.CHAIN_HEAT_CONTEXT_STALE
    if source_status == SourceStatus.FAILED or data_quality in {
        DataQualityLabel.DIRTY_DATA,
        DataQualityLabel.MISSING_CRITICAL_DATA,
        DataQualityLabel.DO_NOT_TRAIN,
    }:
        return ChainHeatPayloadQualityLabel.CHAIN_HEAT_CONTEXT_DO_NOT_USE_FOR_MEMORY
    if chain_heat_payload_is_stale(normalized_payload, now):
        return ChainHeatPayloadQualityLabel.CHAIN_HEAT_CONTEXT_STALE
    if not chain_heat_payload_has_required_fields(normalized_payload):
        return ChainHeatPayloadQualityLabel.CHAIN_HEAT_CONTEXT_UNKNOWN
    required_clean_fields = (
        normalized_payload.get("sol_price_usd"),
        normalized_payload.get("solana_tx_count_24h"),
        normalized_payload.get("solana_meme_volume_24h"),
    )
    if source_status == SourceStatus.PARTIAL or data_quality == DataQualityLabel.ACCEPTABLE_PARTIAL_DATA or any(
        value is None for value in required_clean_fields
    ):
        return ChainHeatPayloadQualityLabel.CHAIN_HEAT_CONTEXT_PARTIAL
    return ChainHeatPayloadQualityLabel.CHAIN_HEAT_CONTEXT_CLEAN


def chain_heat_context_can_support_clean_memory(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> bool:
    return (
        classify_chain_heat_payload_quality(normalized_payload, now)
        == ChainHeatPayloadQualityLabel.CHAIN_HEAT_CONTEXT_CLEAN
    )

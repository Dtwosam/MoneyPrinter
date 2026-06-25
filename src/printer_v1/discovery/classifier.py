"""Rule-only discovery classification for Printer V1."""

from dataclasses import dataclass
from typing import Mapping, Any

from printer_v1.contracts.rules import PRINTER_CHAIN
from printer_v1.discovery.contracts import DiscoveryCandidateLabel, DiscoveryChannelLabel, DiscoveryOutputAction
from printer_v1.lifecycle.contracts import TokenLifecycleState
from printer_v1.discovery.parser import candidate_has_required_fields, candidate_is_solana


MIN_TRACK_NORMAL_LIQUIDITY_USD = 1_000.0
MIN_TRACK_FAST_LIQUIDITY_USD = 5_000.0
MIN_TRACK_FAST_VOLUME_5M_USD = 1_000.0
MIN_TRACK_FAST_TXNS_5M = 10
MIN_MEMORY_GROWTH_VOLUME_1H_USD = 100.0
MIN_MEMORY_GROWTH_TXNS_1H = 3
MIN_MEMORY_GROWTH_VOLUME_24H_USD = 100.0
MIN_MEMORY_GROWTH_TXNS_24H = 5
TINY_VOLUME_24H_USD = 10.0
TINY_TXNS_24H = 2

# Channels that confirm a token graduated or migrated to a real pool.
# These channels justify a lower TRACK_FAST liquidity floor because graduation
# itself is evidence of real activity — the high-liquidity threshold is not
# the primary gate when the channel proves the token already crossed a bridge.
_GRADUATION_CHANNELS = frozenset({
    DiscoveryChannelLabel.PUMPFUN_MIGRATION.value,
    DiscoveryChannelLabel.PUMPSWAP_GRADUATED.value,
})
CHANNEL_MIGRATION_MINIMUM_LIQUIDITY_USD = 2_000.0


@dataclass(frozen=True)
class DiscoveryClassification:
    discovery_label: DiscoveryCandidateLabel
    discovery_action: DiscoveryOutputAction
    reason: str


def classify_discovery_candidate(candidate: Mapping[str, Any]) -> DiscoveryClassification:
    if should_instant_reject_candidate(candidate):
        return DiscoveryClassification(
            DiscoveryCandidateLabel.INSTANT_REJECT,
            DiscoveryOutputAction.INSTANT_REJECT_MEMORY_ONLY,
            "unsupported_chain_or_unusable_pair",
        )
    if should_ignore_candidate(candidate):
        return DiscoveryClassification(
            DiscoveryCandidateLabel.DUPLICATE_IGNORED,
            DiscoveryOutputAction.IGNORE,
            "missing_token_or_pair",
        )
    if should_track_fast_candidate(candidate):
        return DiscoveryClassification(
            DiscoveryCandidateLabel.TRACK_FAST_CANDIDATE,
            DiscoveryOutputAction.TRACK_FAST,
            "fresh_solana_candidate_with_liquidity_and_activity",
        )
    if should_track_normal_candidate(candidate):
        return DiscoveryClassification(
            DiscoveryCandidateLabel.TRACK_NORMAL_CANDIDATE,
            DiscoveryOutputAction.TRACK_NORMAL,
            "clean_solana_candidate_with_basic_market_fields",
        )
    if is_dead_or_near_zero_activity_candidate(candidate):
        return DiscoveryClassification(
            DiscoveryCandidateLabel.WATCH_ONLY_CANDIDATE,
            DiscoveryOutputAction.WATCH_ONLY,
            "insufficient_activity_for_memory_growth",
        )
    if should_watch_only_candidate(candidate):
        return DiscoveryClassification(
            DiscoveryCandidateLabel.WATCH_ONLY_CANDIDATE,
            DiscoveryOutputAction.WATCH_ONLY,
            "partial_market_fields_or_low_activity",
        )
    if has_basic_market_fields(candidate) and has_track_normal_liquidity(candidate):
        return DiscoveryClassification(
            DiscoveryCandidateLabel.WATCH_ONLY_CANDIDATE,
            DiscoveryOutputAction.WATCH_ONLY,
            "no_recent_activity_pulse_for_memory_growth",
        )
    return DiscoveryClassification(
        DiscoveryCandidateLabel.DUPLICATE_IGNORED,
        DiscoveryOutputAction.IGNORE,
        "unusable_candidate",
    )


def choose_initial_lifecycle_state(
    candidate: Mapping[str, Any],
    classification: DiscoveryClassification,
) -> TokenLifecycleState:
    del candidate
    return {
        DiscoveryOutputAction.TRACK_FAST: TokenLifecycleState.TRACK_FAST,
        DiscoveryOutputAction.TRACK_NORMAL: TokenLifecycleState.TRACK_NORMAL,
        DiscoveryOutputAction.WATCH_ONLY: TokenLifecycleState.WATCH_ONLY,
        DiscoveryOutputAction.INSTANT_REJECT_MEMORY_ONLY: TokenLifecycleState.INSTANT_REJECT_MEMORY_ONLY,
        DiscoveryOutputAction.IGNORE: TokenLifecycleState.ARCHIVED,
    }[classification.discovery_action]


def choose_tracking_lane(
    candidate: Mapping[str, Any],
    classification: DiscoveryClassification,
) -> TokenLifecycleState | None:
    del candidate
    if classification.discovery_action == DiscoveryOutputAction.TRACK_FAST:
        return TokenLifecycleState.TRACK_FAST
    if classification.discovery_action == DiscoveryOutputAction.TRACK_NORMAL:
        return TokenLifecycleState.TRACK_NORMAL
    if classification.discovery_action == DiscoveryOutputAction.WATCH_ONLY:
        return TokenLifecycleState.WATCH_ONLY
    return None


def build_priority_reason(
    candidate: Mapping[str, Any],
    classification: DiscoveryClassification,
) -> str:
    return f"{classification.discovery_action.value}:{classification.reason}:{candidate.get('source_name')}"


def should_ignore_candidate(candidate: Mapping[str, Any]) -> bool:
    return not candidate.get("token_mint") or not candidate.get("pair_address")


def should_instant_reject_candidate(candidate: Mapping[str, Any]) -> bool:
    if candidate.get("chain") != PRINTER_CHAIN and candidate.get("chain") is not None:
        return True
    if candidate.get("pair_address") in (None, "") and candidate.get("token_mint"):
        return True
    return False


def channel_specific_minimum_liquidity_floor(source_channel: str | None) -> float:
    """Return the minimum liquidity floor for TRACK_FAST based on source channel.

    This is a deterministic hard gate. Graduation channels (PUMPFUN_MIGRATION,
    PUMPSWAP_GRADUATED) use a lower floor because the graduation event itself
    confirms real pool activity. All other channels use the standard floor.
    """
    if source_channel in _GRADUATION_CHANNELS:
        return CHANNEL_MIGRATION_MINIMUM_LIQUIDITY_USD
    return MIN_TRACK_FAST_LIQUIDITY_USD


def has_recent_activity_pulse(candidate: Mapping[str, Any]) -> bool:
    """Return True if the candidate shows meaningful activity in the recent 5m or 1h window.

    A token that only passes 24h thresholds with zero 5m/1h activity is likely
    stale and should not qualify for TRACK_NORMAL. TRACK_NORMAL requires a
    recent signal, not just historical 24h residue.
    """
    return (
        _numeric_or_zero(candidate.get("volume_5m")) > 0
        or _numeric_or_zero(candidate.get("txns_5m")) > 0
        or _numeric_or_zero(candidate.get("volume_1h")) >= MIN_MEMORY_GROWTH_VOLUME_1H_USD
        or _numeric_or_zero(candidate.get("txns_1h")) >= MIN_MEMORY_GROWTH_TXNS_1H
    )


def should_watch_only_candidate(candidate: Mapping[str, Any]) -> bool:
    if not candidate_has_required_fields(candidate) or not candidate_is_solana(candidate):
        return False
    return not has_basic_market_fields(candidate) or not has_track_normal_liquidity(candidate)


def should_track_normal_candidate(candidate: Mapping[str, Any]) -> bool:
    return (
        candidate_has_required_fields(candidate)
        and candidate_is_solana(candidate)
        and has_basic_market_fields(candidate)
        and has_track_normal_liquidity(candidate)
        and has_recent_activity_pulse(candidate)
        and is_activity_sufficient_for_memory_growth(candidate)
    )


def should_track_fast_candidate(candidate: Mapping[str, Any]) -> bool:
    volume_5m = candidate.get("volume_5m") or 0
    txns_5m = candidate.get("txns_5m") or 0
    liquidity = candidate.get("liquidity_usd") or 0
    min_liquidity = channel_specific_minimum_liquidity_floor(candidate.get("source_channel"))
    return (
        should_track_normal_candidate(candidate)
        and liquidity >= min_liquidity
        and (volume_5m >= MIN_TRACK_FAST_VOLUME_5M_USD or txns_5m >= MIN_TRACK_FAST_TXNS_5M)
    )


def has_basic_market_fields(candidate: Mapping[str, Any]) -> bool:
    return candidate.get("price_usd") is not None and candidate.get("liquidity_usd") is not None


def has_track_normal_liquidity(candidate: Mapping[str, Any]) -> bool:
    return (candidate.get("liquidity_usd") or 0) >= MIN_TRACK_NORMAL_LIQUIDITY_USD


def _numeric_or_zero(value: Any) -> float:
    return 0.0 if value is None else float(value)


def is_dead_or_near_zero_activity_candidate(candidate: Mapping[str, Any]) -> bool:
    volume_5m = _numeric_or_zero(candidate.get("volume_5m"))
    txns_5m = _numeric_or_zero(candidate.get("txns_5m"))
    volume_1h = _numeric_or_zero(candidate.get("volume_1h"))
    txns_1h = _numeric_or_zero(candidate.get("txns_1h"))
    volume_24h = _numeric_or_zero(candidate.get("volume_24h"))
    txns_24h = _numeric_or_zero(candidate.get("txns_24h"))
    return (
        volume_5m <= 0
        and txns_5m <= 0
        and volume_1h <= 0
        and txns_1h <= 0
        and volume_24h <= TINY_VOLUME_24H_USD
        and txns_24h <= TINY_TXNS_24H
    )


def is_activity_sufficient_for_memory_growth(candidate: Mapping[str, Any]) -> bool:
    if is_dead_or_near_zero_activity_candidate(candidate):
        return False
    volume_1h = _numeric_or_zero(candidate.get("volume_1h"))
    txns_1h = _numeric_or_zero(candidate.get("txns_1h"))
    volume_24h = _numeric_or_zero(candidate.get("volume_24h"))
    txns_24h = _numeric_or_zero(candidate.get("txns_24h"))
    return (
        volume_1h >= MIN_MEMORY_GROWTH_VOLUME_1H_USD
        or txns_1h >= MIN_MEMORY_GROWTH_TXNS_1H
        or volume_24h >= MIN_MEMORY_GROWTH_VOLUME_24H_USD
        or txns_24h >= MIN_MEMORY_GROWTH_TXNS_24H
    )

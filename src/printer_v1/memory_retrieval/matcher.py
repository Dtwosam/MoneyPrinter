"""Deterministic memory fingerprint comparison without numeric scoring."""

from typing import Any, Mapping

from printer_v1.memory.contracts import MemoryQualityLabel
from printer_v1.memory_retrieval.contracts import MatchReasonLabel, MatchStrengthLabel


MATCH_FIELD_REASONS = {
    "window_kind": MatchReasonLabel.MATCH_WINDOW_KIND,
    "outcome_label": MatchReasonLabel.MATCH_OUTCOME_LABEL,
    "market_regime_label": MatchReasonLabel.MATCH_MARKET_REGIME,
    "chain_heat_label": MatchReasonLabel.MATCH_CHAIN_HEAT,
    "safety_status_label": MatchReasonLabel.MATCH_SAFETY_CONTEXT,
    "liquidity_state_label": MatchReasonLabel.MATCH_LIQUIDITY_EXIT_CONTEXT,
    "exit_realism_label": MatchReasonLabel.MATCH_LIQUIDITY_EXIT_CONTEXT,
    "realism_gate_label": MatchReasonLabel.MATCH_LIQUIDITY_EXIT_CONTEXT,
    "flow_direction_label": MatchReasonLabel.MATCH_TRADING_FLOW_CONTEXT,
    "flow_pressure_label": MatchReasonLabel.MATCH_TRADING_FLOW_CONTEXT,
    "trend_structure_label": MatchReasonLabel.MATCH_CHART_VOLATILITY_CONTEXT,
    "volatility_label": MatchReasonLabel.MATCH_CHART_VOLATILITY_CONTEXT,
    "candle_path_label": MatchReasonLabel.MATCH_CHART_VOLATILITY_CONTEXT,
    "micro_event_state_label": MatchReasonLabel.MATCH_MICRO_EVENT_SUPPORT,
    "held_to_15m_result_label": MatchReasonLabel.MATCH_MICRO_EVENT_SUPPORT,
    "token_age_bucket": MatchReasonLabel.MATCH_TOKEN_AGE_BUCKET,
    "pair_age_bucket": MatchReasonLabel.MATCH_PAIR_AGE_BUCKET,
    "discovery_label": MatchReasonLabel.MATCH_DISCOVERY_CONTEXT,
}

MISMATCH_FIELD_REASONS = {
    "outcome_label": MatchReasonLabel.MISMATCH_OUTCOME_LABEL,
    "safety_status_label": MatchReasonLabel.MISMATCH_SAFETY_CONTEXT,
    "liquidity_state_label": MatchReasonLabel.MISMATCH_LIQUIDITY_EXIT_CONTEXT,
    "exit_realism_label": MatchReasonLabel.MISMATCH_LIQUIDITY_EXIT_CONTEXT,
    "realism_gate_label": MatchReasonLabel.MISMATCH_LIQUIDITY_EXIT_CONTEXT,
    "flow_direction_label": MatchReasonLabel.MISMATCH_TRADING_FLOW_CONTEXT,
    "flow_pressure_label": MatchReasonLabel.MISMATCH_TRADING_FLOW_CONTEXT,
    "trend_structure_label": MatchReasonLabel.MISMATCH_CHART_CONTEXT,
    "volatility_label": MatchReasonLabel.MISMATCH_CHART_CONTEXT,
    "candle_path_label": MatchReasonLabel.MISMATCH_CHART_CONTEXT,
}

CORE_FIELDS = (
    "safety_status_label",
    "liquidity_state_label",
    "exit_realism_label",
    "flow_direction_label",
    "trend_structure_label",
    "candle_path_label",
)


def collect_match_reasons(current_fingerprint: Mapping[str, Any], memory_fingerprint: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    for field, reason in MATCH_FIELD_REASONS.items():
        if current_fingerprint.get(field) is not None and current_fingerprint.get(field) == memory_fingerprint.get(field):
            value = reason.value
            if value not in reasons:
                reasons.append(value)
    return reasons


def collect_mismatch_reasons(current_fingerprint: Mapping[str, Any], memory_fingerprint: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    for field, reason in MISMATCH_FIELD_REASONS.items():
        current = current_fingerprint.get(field)
        memory = memory_fingerprint.get(field)
        if current is None:
            reasons.append(MatchReasonLabel.MISSING_CURRENT_CONTEXT.value)
        elif memory is None:
            reasons.append(MatchReasonLabel.MISSING_MEMORY_CONTEXT.value)
        elif current != memory:
            reasons.append(reason.value)
    return list(dict.fromkeys(reasons))


def classify_match_strength(current_fingerprint: Mapping[str, Any], memory_fingerprint: Mapping[str, Any]) -> MatchStrengthLabel:
    available = [field for field in MATCH_FIELD_REASONS if current_fingerprint.get(field) is not None and memory_fingerprint.get(field) is not None]
    if not available:
        return MatchStrengthLabel.NO_USABLE_MATCH
    matched = [field for field in available if current_fingerprint.get(field) == memory_fingerprint.get(field)]
    core_available = [field for field in CORE_FIELDS if current_fingerprint.get(field) is not None and memory_fingerprint.get(field) is not None]
    core_matched = [field for field in core_available if current_fingerprint.get(field) == memory_fingerprint.get(field)]
    if len(available) >= 4 and len(matched) == len(available):
        return MatchStrengthLabel.EXACT_CONDITION_MATCH
    if len(core_available) >= 4 and len(core_matched) >= 4:
        return MatchStrengthLabel.STRONG_CONDITION_MATCH
    if len(core_matched) >= 2 or len(matched) >= 4:
        return MatchStrengthLabel.PARTIAL_CONDITION_MATCH
    if matched:
        return MatchStrengthLabel.WEAK_CONDITION_MATCH
    return MatchStrengthLabel.NO_USABLE_MATCH


def memory_episode_is_eligible_for_clean_retrieval(episode_or_row: Mapping[str, Any]) -> bool:
    return MemoryQualityLabel(episode_or_row["memory_quality_label"]) == MemoryQualityLabel.CLEAN_MEMORY


def memory_match_can_be_clean_evidence(match_payload: Mapping[str, Any]) -> bool:
    return (
        match_payload.get("memory_quality_label") == MemoryQualityLabel.CLEAN_MEMORY.value
        and match_payload.get("match_strength_label")
        in {
            MatchStrengthLabel.EXACT_CONDITION_MATCH.value,
            MatchStrengthLabel.STRONG_CONDITION_MATCH.value,
            MatchStrengthLabel.PARTIAL_CONDITION_MATCH.value,
        }
    )


def compare_fingerprints(current_fingerprint: Mapping[str, Any], memory_fingerprint: Mapping[str, Any]) -> dict[str, Any]:
    strength = classify_match_strength(current_fingerprint, memory_fingerprint)
    return {
        "match_strength_label": strength.value,
        "match_reasons": collect_match_reasons(current_fingerprint, memory_fingerprint),
        "mismatch_reasons": collect_mismatch_reasons(current_fingerprint, memory_fingerprint),
    }

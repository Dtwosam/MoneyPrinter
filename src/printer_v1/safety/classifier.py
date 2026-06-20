"""Deterministic Safety / Rug classification helpers."""

from datetime import datetime
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.safety.contracts import (
    AuthorityLabel,
    DistributionLabel,
    LiquiditySafetyLabel,
    RugRiskLabel,
    SafetyGateLabel,
    SafetyPayloadQualityLabel,
    SafetyStatusLabel,
)
from printer_v1.safety.parser import safety_payload_has_required_fields, safety_payload_is_stale


def truthy(payload: Mapping[str, Any], field: str) -> bool:
    return payload.get(field) == 1 or payload.get(field) is True


def has_dangerous_restriction(payload: Mapping[str, Any]) -> bool:
    return any(
        truthy(payload, field)
        for field in (
            "honeypot_like_behavior",
            "sell_restriction_detected",
            "blacklist_function_present",
        )
    )


def classify_liquidity_safety(normalized_payload: Mapping[str, Any]) -> LiquiditySafetyLabel:
    liquidity = normalized_payload.get("liquidity_usd")
    locked = normalized_payload.get("liquidity_locked")
    if liquidity is None:
        return LiquiditySafetyLabel.LIQUIDITY_SAFETY_UNKNOWN
    if liquidity < 2_500:
        return LiquiditySafetyLabel.LIQUIDITY_DANGEROUS
    if liquidity < 10_000:
        return LiquiditySafetyLabel.LIQUIDITY_THIN
    if locked is None:
        return LiquiditySafetyLabel.LIQUIDITY_LOCK_UNKNOWN
    if locked == 0 and liquidity < 50_000:
        return LiquiditySafetyLabel.LIQUIDITY_UNSTABLE
    return LiquiditySafetyLabel.LIQUIDITY_SAFE


def classify_authority_safety(normalized_payload: Mapping[str, Any]) -> AuthorityLabel:
    if has_dangerous_restriction(normalized_payload):
        return AuthorityLabel.AUTHORITY_DANGEROUS
    observed = [
        normalized_payload.get(field)
        for field in (
            "mint_authority_present",
            "freeze_authority_present",
            "update_authority_present",
            "transfer_fee_present",
        )
    ]
    if all(value is None for value in observed):
        return AuthorityLabel.AUTHORITY_UNKNOWN
    if truthy(normalized_payload, "freeze_authority_present") or truthy(
        normalized_payload,
        "transfer_fee_present",
    ):
        return AuthorityLabel.AUTHORITY_SUSPICIOUS
    if truthy(normalized_payload, "mint_authority_present") or truthy(
        normalized_payload,
        "update_authority_present",
    ):
        return AuthorityLabel.AUTHORITY_PRESENT
    return AuthorityLabel.AUTHORITY_RENOUNCED_OR_SAFE


def classify_distribution_safety(normalized_payload: Mapping[str, Any]) -> DistributionLabel:
    top_holder = normalized_payload.get("top_holder_percent")
    top_10 = normalized_payload.get("top_10_holder_percent")
    creator = normalized_payload.get("creator_percent")
    if top_holder is None and top_10 is None and creator is None:
        return DistributionLabel.DISTRIBUTION_UNKNOWN
    if (top_holder or 0) >= 30 or (top_10 or 0) >= 80 or (creator or 0) >= 20:
        return DistributionLabel.DISTRIBUTION_EXTREME_CONCENTRATION
    if (top_holder or 0) >= 15 or (top_10 or 0) >= 55 or (creator or 0) >= 10:
        return DistributionLabel.DISTRIBUTION_CONCENTRATED
    return DistributionLabel.DISTRIBUTION_HEALTHY


def classify_rug_risk(normalized_payload: Mapping[str, Any]) -> RugRiskLabel:
    liquidity = classify_liquidity_safety(normalized_payload)
    authority = classify_authority_safety(normalized_payload)
    distribution = classify_distribution_safety(normalized_payload)
    if has_dangerous_restriction(normalized_payload) or authority == AuthorityLabel.AUTHORITY_DANGEROUS:
        return RugRiskLabel.RUG_RISK_CRITICAL
    if (
        liquidity == LiquiditySafetyLabel.LIQUIDITY_DANGEROUS
        or distribution == DistributionLabel.DISTRIBUTION_EXTREME_CONCENTRATION
    ):
        return RugRiskLabel.RUG_RISK_HIGH
    if (
        authority == AuthorityLabel.AUTHORITY_SUSPICIOUS
        or liquidity
        in {
            LiquiditySafetyLabel.LIQUIDITY_THIN,
            LiquiditySafetyLabel.LIQUIDITY_UNSTABLE,
        }
        or distribution == DistributionLabel.DISTRIBUTION_CONCENTRATED
        or truthy(normalized_payload, "mutable_metadata")
        or truthy(normalized_payload, "suspicious_metadata")
        or truthy(normalized_payload, "suspicious_creator_activity")
    ):
        return RugRiskLabel.RUG_RISK_MEDIUM
    if (
        liquidity == LiquiditySafetyLabel.LIQUIDITY_SAFETY_UNKNOWN
        or authority == AuthorityLabel.AUTHORITY_UNKNOWN
        or distribution == DistributionLabel.DISTRIBUTION_UNKNOWN
    ):
        return RugRiskLabel.RUG_RISK_UNKNOWN
    return RugRiskLabel.RUG_RISK_LOW


def classify_safety_status(normalized_payload: Mapping[str, Any]) -> SafetyStatusLabel:
    risk = classify_rug_risk(normalized_payload)
    if risk == RugRiskLabel.RUG_RISK_CRITICAL:
        return SafetyStatusLabel.SAFETY_UNSAFE
    if risk == RugRiskLabel.RUG_RISK_HIGH:
        return SafetyStatusLabel.SAFETY_SUSPICIOUS
    if risk == RugRiskLabel.RUG_RISK_MEDIUM:
        return SafetyStatusLabel.SAFETY_CAUTION
    if risk == RugRiskLabel.RUG_RISK_UNKNOWN:
        return SafetyStatusLabel.SAFETY_UNKNOWN
    return SafetyStatusLabel.SAFETY_CLEAN


def classify_safety_payload_quality(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> SafetyPayloadQualityLabel:
    source_status = SourceStatus(normalized_payload.get("source_status") or SourceStatus.COMPLETE)
    data_quality = DataQualityLabel(
        normalized_payload.get("data_quality_label") or DataQualityLabel.CLEAN_DATA
    )
    if source_status == SourceStatus.CONFLICTING or data_quality == DataQualityLabel.CONFLICTING_DATA:
        return SafetyPayloadQualityLabel.SAFETY_CONTEXT_CONFLICTING
    if source_status == SourceStatus.STALE or data_quality == DataQualityLabel.STALE_DATA:
        return SafetyPayloadQualityLabel.SAFETY_CONTEXT_STALE
    if source_status == SourceStatus.FAILED or data_quality in {
        DataQualityLabel.DIRTY_DATA,
        DataQualityLabel.MISSING_CRITICAL_DATA,
        DataQualityLabel.DO_NOT_TRAIN,
    }:
        return SafetyPayloadQualityLabel.SAFETY_CONTEXT_DO_NOT_USE_FOR_MEMORY
    if safety_payload_is_stale(normalized_payload, now):
        return SafetyPayloadQualityLabel.SAFETY_CONTEXT_STALE
    if not safety_payload_has_required_fields(normalized_payload):
        return SafetyPayloadQualityLabel.SAFETY_CONTEXT_UNKNOWN
    required = (
        normalized_payload.get("liquidity_usd"),
        normalized_payload.get("mint_authority_present"),
        normalized_payload.get("top_holder_percent"),
    )
    if source_status == SourceStatus.PARTIAL or data_quality == DataQualityLabel.ACCEPTABLE_PARTIAL_DATA or any(
        value is None for value in required
    ):
        return SafetyPayloadQualityLabel.SAFETY_CONTEXT_PARTIAL
    return SafetyPayloadQualityLabel.SAFETY_CONTEXT_CLEAN


def classify_safety_gate(normalized_payload: Mapping[str, Any]) -> SafetyGateLabel:
    quality = classify_safety_payload_quality(normalized_payload)
    safety = classify_safety_status(normalized_payload)
    if quality == SafetyPayloadQualityLabel.SAFETY_CONTEXT_DO_NOT_USE_FOR_MEMORY:
        return SafetyGateLabel.DO_NOT_TRAIN_SAFETY_CONTEXT
    if quality in {
        SafetyPayloadQualityLabel.SAFETY_CONTEXT_STALE,
        SafetyPayloadQualityLabel.SAFETY_CONTEXT_CONFLICTING,
        SafetyPayloadQualityLabel.SAFETY_CONTEXT_UNKNOWN,
    }:
        return SafetyGateLabel.MANUAL_REVIEW_REQUIRED
    if safety == SafetyStatusLabel.SAFETY_UNSAFE:
        return SafetyGateLabel.BLOCK_UNSAFE_CONTEXT
    if safety in {
        SafetyStatusLabel.SAFETY_CAUTION,
        SafetyStatusLabel.SAFETY_SUSPICIOUS,
        SafetyStatusLabel.SAFETY_UNKNOWN,
    }:
        return SafetyGateLabel.CAUTION_SAFETY_CONTEXT
    return SafetyGateLabel.ALLOW_SAFETY_CONTEXT


def safety_context_can_support_clean_memory(
    normalized_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> bool:
    return (
        classify_safety_payload_quality(normalized_payload, now)
        == SafetyPayloadQualityLabel.SAFETY_CONTEXT_CLEAN
        and classify_safety_status(normalized_payload) == SafetyStatusLabel.SAFETY_CLEAN
    )

"""Pure source governance decisions for Printer V1."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.sources.registry import SOURCE_REGISTRY, SourceDefinition


TOKEN_LEVEL_REQUEST_KINDS = frozenset(
    {
        "token_discovery",
        "pair_market_snapshot",
        "token_market_snapshot",
        "pair_market_reference",
        "ohlc_reference",
        "liquidity_reference",
        "safety_reference",
        "onchain_reference",
        "mint_account_reference",
        "pool_reference",
        "paper_quote_realism",
        "candidate_nomination",
        "candidate_market_batch",
        "birdeye_new_listing_nomination",
        "candidate_mint_account_batch",
        "pumpfun_migration_signature_page",
        "pumpfun_migration_transaction",
        "pumpswap_pool_account_batch",
    }
)

PRIORITY_CLASS_ORDER = MappingProxyType(
    {
        "paper_realism": 1,
        "token_level": 2,
        "protection": 3,
        "discovery": 4,
        "broad_context": 8,
    }
)


@dataclass(frozen=True)
class SourceRequestDecision:
    allowed: bool
    source_name: str
    request_kind: str
    reason: str
    source_status: SourceStatus
    data_quality_label: DataQualityLabel
    retry_after_seconds: int | None = None


def get_source_definition(source_name: str) -> SourceDefinition:
    try:
        return SOURCE_REGISTRY[source_name]
    except KeyError as exc:
        raise ValueError(f"Unknown Printer V1 source: {source_name}") from exc


def is_source_allowed(source_name: str) -> bool:
    try:
        definition = get_source_definition(source_name)
    except ValueError:
        return False
    return not definition.requires_paid_plan


def validate_request_kind(source_name: str, request_kind: str) -> bool:
    definition = get_source_definition(source_name)
    if request_kind not in definition.allowed_request_kinds:
        return False
    if definition.source_name == "jupiter_quote":
        return request_kind == "paper_quote_realism"
    return True


def classify_source_status(
    *,
    source_known: bool = True,
    required_fields_present: bool = True,
    stale: bool = False,
    conflicting: bool = False,
) -> SourceStatus:
    if not source_known or not required_fields_present:
        return SourceStatus.FAILED
    if stale:
        return SourceStatus.STALE
    if conflicting:
        return SourceStatus.CONFLICTING
    return SourceStatus.COMPLETE


def classify_data_quality(source_status: SourceStatus) -> DataQualityLabel:
    if source_status == SourceStatus.COMPLETE:
        return DataQualityLabel.CLEAN_DATA
    if source_status == SourceStatus.PARTIAL:
        return DataQualityLabel.ACCEPTABLE_PARTIAL_DATA
    if source_status == SourceStatus.STALE:
        return DataQualityLabel.STALE_DATA
    if source_status == SourceStatus.CONFLICTING:
        return DataQualityLabel.CONFLICTING_DATA
    return DataQualityLabel.MISSING_CRITICAL_DATA


def is_response_stale(
    source_name: str, received_at: datetime, now: datetime | None = None
) -> bool:
    definition = get_source_definition(source_name)
    current_time = now or datetime.now(timezone.utc)
    return current_time - received_at > timedelta(seconds=definition.stale_after_seconds)


def get_retry_after(source_name: str, consecutive_failures: int) -> int:
    definition = get_source_definition(source_name)
    failure_count = max(consecutive_failures, 1)
    return definition.retry_after_seconds * failure_count


def should_cooldown_source(source_name: str, consecutive_failures: int) -> bool:
    definition = get_source_definition(source_name)
    return consecutive_failures >= definition.max_retries


def can_request_source(
    source_name: str,
    request_kind: str,
    recent_request_count: int,
    now: datetime | None = None,
) -> SourceRequestDecision:
    del now
    try:
        definition = get_source_definition(source_name)
    except ValueError:
        return SourceRequestDecision(
            allowed=False,
            source_name=source_name,
            request_kind=request_kind,
            reason="unknown_source",
            source_status=SourceStatus.FAILED,
            data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        )

    if definition.requires_paid_plan:
        return SourceRequestDecision(
            allowed=False,
            source_name=source_name,
            request_kind=request_kind,
            reason="paid_dependency_rejected",
            source_status=SourceStatus.FAILED,
            data_quality_label=DataQualityLabel.DO_NOT_TRAIN,
        )

    if not validate_request_kind(source_name, request_kind):
        return SourceRequestDecision(
            allowed=False,
            source_name=source_name,
            request_kind=request_kind,
            reason="request_kind_not_allowed",
            source_status=SourceStatus.FAILED,
            data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        )

    if (
        request_kind in TOKEN_LEVEL_REQUEST_KINDS
        and definition.supports_solana == "not_chain_specific"
    ):
        return SourceRequestDecision(
            allowed=False,
            source_name=source_name,
            request_kind=request_kind,
            reason="not_solana_token_level_source",
            source_status=SourceStatus.FAILED,
            data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        )

    if (
        definition.source_name == "jupiter_quote"
        and definition.restriction == "paper_simulation_only"
        and request_kind != "paper_quote_realism"
    ):
        return SourceRequestDecision(
            allowed=False,
            source_name=source_name,
            request_kind=request_kind,
            reason="jupiter_quote_paper_only",
            source_status=SourceStatus.FAILED,
            data_quality_label=DataQualityLabel.DO_NOT_TRAIN,
        )

    if recent_request_count >= definition.default_rate_limit_per_minute:
        return SourceRequestDecision(
            allowed=False,
            source_name=source_name,
            request_kind=request_kind,
            reason="rate_limit_exceeded",
            source_status=SourceStatus.STALE,
            data_quality_label=DataQualityLabel.STALE_DATA,
            retry_after_seconds=definition.retry_after_seconds,
        )

    return SourceRequestDecision(
        allowed=True,
        source_name=source_name,
        request_kind=request_kind,
        reason="allowed",
        source_status=SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.CLEAN_DATA,
    )


def source_priority_value(source_name: str) -> int:
    definition = get_source_definition(source_name)
    return PRIORITY_CLASS_ORDER[definition.priority_class]


def normalize_source_payload(source_name: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    get_source_definition(source_name)
    return MappingProxyType(dict(payload))

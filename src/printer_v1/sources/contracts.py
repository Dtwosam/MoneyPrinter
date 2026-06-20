"""Phase 23 source adapter execution boundary contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.sources.governor import SourceRequestDecision, can_request_source
from printer_v1.sources.registry import SOURCE_REGISTRY


STALE_DATA_BEHAVIOR = "record_stale_context_only"
MALFORMED_DATA_BEHAVIOR = "record_failure_missing_critical_data"
RATE_LIMIT_BEHAVIOR = "record_rate_limited_failure"
GOVERNOR_ONLY_EXECUTION_PATH = "source_governor_record_then_adapter_boundary"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SourceAdapterContract:
    source_name: str
    allowed_request_kinds: tuple[str, ...]
    enabled_by_default: bool = False
    fixture_only: bool = True
    supports_network_execution: bool = False
    requires_governor_context: bool = True
    stale_data_behavior: str = STALE_DATA_BEHAVIOR
    malformed_data_behavior: str = MALFORMED_DATA_BEHAVIOR
    rate_limit_behavior: str = RATE_LIMIT_BEHAVIOR


@dataclass(frozen=True)
class SourceRequest:
    source_name: str
    request_kind: str
    requested_at: str = field(default_factory=utc_now_iso)
    request_key: str | None = None
    tracking_priority: int | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceRequestRecord:
    id: int
    source_name: str
    request_kind: str
    requested_at: str
    request_key: str | None
    tracking_priority: int | None
    source_status: SourceStatus
    data_quality_label: DataQualityLabel


@dataclass(frozen=True)
class SourceResponseRecord:
    id: int
    source_request_id: int
    source_name: str
    received_at: str
    status_code: int | None
    source_status: SourceStatus
    data_quality_label: DataQualityLabel
    response_hash: str | None
    normalized_payload: Mapping[str, Any]


@dataclass(frozen=True)
class SourceFailureRecord:
    id: int
    source_name: str
    request_kind: str
    failed_at: str
    failure_type: str
    failure_message: str | None
    source_status: SourceStatus
    data_quality_label: DataQualityLabel
    retry_after_at: str | None = None


@dataclass(frozen=True)
class NormalizedSourceResult:
    source_name: str
    request_kind: str
    source_status: SourceStatus
    data_quality_label: DataQualityLabel
    normalized_payload: Mapping[str, Any] = field(default_factory=dict)
    status_code: int | None = None
    failure_type: str | None = None
    failure_message: str | None = None
    retry_after_at: str | None = None
    received_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class SourceAdapterContext:
    request: SourceRequest
    request_record: SourceRequestRecord
    decision: SourceRequestDecision
    governor_approved: bool
    execution_path: str = GOVERNOR_ONLY_EXECUTION_PATH


def build_source_adapter_contract(source_name: str) -> SourceAdapterContract:
    definition = SOURCE_REGISTRY[source_name]
    return SourceAdapterContract(
        source_name=definition.source_name,
        allowed_request_kinds=definition.allowed_request_kinds,
    )


def validate_source_adapter_contract(contract: SourceAdapterContract) -> bool:
    if contract.source_name not in SOURCE_REGISTRY:
        return False
    definition = SOURCE_REGISTRY[contract.source_name]
    return (
        contract.allowed_request_kinds == definition.allowed_request_kinds
        and contract.enabled_by_default is False
        and contract.fixture_only is True
        and contract.supports_network_execution is False
        and contract.requires_governor_context is True
    )


def source_request_has_allowed_kind(source_request: SourceRequest) -> bool:
    definition = SOURCE_REGISTRY.get(source_request.source_name)
    return bool(definition and source_request.request_kind in definition.allowed_request_kinds)


def build_governed_source_request(
    source_name: str,
    request_kind: str,
    *,
    request_key: str | None = None,
    tracking_priority: int | None = None,
    payload: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> SourceRequest:
    requested_at = (now or datetime.now(timezone.utc)).isoformat()
    return SourceRequest(
        source_name=source_name,
        request_kind=request_kind,
        requested_at=requested_at,
        request_key=request_key,
        tracking_priority=tracking_priority,
        payload=MappingProxyType(dict(payload or {})),
    )


def build_governor_decision(
    source_request: SourceRequest,
    *,
    recent_request_count: int = 0,
    now: datetime | None = None,
) -> SourceRequestDecision:
    return can_request_source(
        source_request.source_name,
        source_request.request_kind,
        recent_request_count=recent_request_count,
        now=now,
    )

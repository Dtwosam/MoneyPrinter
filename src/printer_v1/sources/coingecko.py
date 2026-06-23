"""Governed CoinGecko broad market and asset context adapter shell."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any, Callable, Mapping

from printer_v1.chain_heat.parser import chain_heat_payload_has_required_fields, normalize_chain_heat_payload
from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.market_regime.parser import market_payload_has_required_fields, normalize_market_payload
from printer_v1.sources.contracts import (
    GOVERNOR_ONLY_EXECUTION_PATH,
    NormalizedSourceResult,
    SourceAdapterContext,
    SourceAdapterContract,
    build_source_adapter_contract,
    validate_source_adapter_contract,
)


COINGECKO_SOURCE_NAME = "coingecko"


@dataclass(frozen=True)
class CoinGeckoAdapterMetadata:
    source_name: str = COINGECKO_SOURCE_NAME
    display_name: str = "CoinGecko"
    enabled_by_default: bool = False
    requires_governor_context: bool = True
    supports_network_execution: bool = False
    fixture_transport_only: bool = True


class CoinGeckoAdapter:
    """CoinGecko adapter shell, disabled unless a governed caller injects transport."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
    ) -> None:
        self.metadata = CoinGeckoAdapterMetadata()
        self.contract = build_coingecko_adapter_contract()
        self.enabled = enabled
        self.transport = fixture_transport
        self.call_count = 0

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not self.enabled:
            raise PermissionError("CoinGecko adapter is disabled by default")
        if self.transport is None:
            raise PermissionError("CoinGecko adapter requires an explicit transport")
        _validate_context(context, COINGECKO_SOURCE_NAME, self.contract)

        self.call_count += 1
        try:
            payload = self.transport(context)
        except Exception as exc:
            return _failure_result(context.request.request_kind, "coingecko_transport_error", str(exc))
        return normalize_coingecko_payload(payload, request_kind=context.request.request_kind)


def build_coingecko_adapter_contract() -> SourceAdapterContract:
    contract = build_source_adapter_contract(COINGECKO_SOURCE_NAME)
    if not validate_source_adapter_contract(contract):
        raise ValueError("CoinGecko contract violates Source Governor boundary")
    return contract


def build_coingecko_adapter(
    *,
    enabled: bool = False,
    fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
) -> CoinGeckoAdapter:
    return CoinGeckoAdapter(enabled=enabled, fixture_transport=fixture_transport)


def fixture_success_transport(payload: Mapping[str, Any]) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType(dict(payload))

    return transport


def fixture_failure_transport(message: str = "CoinGecko fixture failure") -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType(
            {
                "fixture_status": "failure",
                "failure_type": "coingecko_fixture_failure",
                "failure_message": message,
            }
        )

    return transport


def normalize_coingecko_payload(
    payload: Mapping[str, Any],
    *,
    request_kind: str,
) -> NormalizedSourceResult:
    if request_kind not in {"broad_market_context", "asset_context"}:
        return _failure_result(request_kind, "coingecko_request_kind_not_allowed", "CoinGecko request kind is not allowed")
    fixture_status = payload.get("fixture_status")
    if fixture_status == "failure":
        return _failure_result(
            request_kind,
            str(payload.get("failure_type") or "coingecko_fixture_failure"),
            str(payload.get("failure_message") or "CoinGecko fixture failure"),
        )
    if fixture_status == "rate_limited":
        retry_at = (datetime.now(timezone.utc) + timedelta(seconds=int(payload.get("retry_after_seconds") or 120))).isoformat()
        return NormalizedSourceResult(
            source_name=COINGECKO_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.STALE,
            data_quality_label=DataQualityLabel.STALE_DATA,
            failure_type="coingecko_rate_limited_fixture",
            failure_message="CoinGecko fixture rate limit",
            retry_after_at=retry_at,
        )

    normalized_market = normalize_market_payload(payload)
    normalized_chain = normalize_chain_heat_payload(payload)
    if not (
        market_payload_has_required_fields(normalized_market)
        or chain_heat_payload_has_required_fields(normalized_chain)
    ):
        return _failure_result(
            request_kind,
            "coingecko_missing_public_context",
            "CoinGecko fixture missing BTC/SOL market or chain heat context",
        )
    return NormalizedSourceResult(
        source_name=COINGECKO_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.STALE if payload.get("fixture_stale") else SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.STALE_DATA if payload.get("fixture_stale") else DataQualityLabel.CLEAN_DATA,
        normalized_payload=MappingProxyType(
            {
                **dict(payload),
                "source_name": COINGECKO_SOURCE_NAME,
                "request_kind": request_kind,
            }
        ),
        status_code=int(payload.get("_source_status_code") or 200),
    )


def _validate_context(context: SourceAdapterContext, source_name: str, contract: SourceAdapterContract) -> None:
    if not context or not context.governor_approved:
        raise PermissionError("source adapter execution requires Source Governor approval")
    if context.execution_path != GOVERNOR_ONLY_EXECUTION_PATH:
        raise PermissionError("source adapter execution requires governed recording path")
    if context.request.source_name != source_name:
        raise ValueError("source request does not match adapter")
    if context.request.request_kind not in contract.allowed_request_kinds:
        raise ValueError("source request kind is not allowed for adapter")


def _failure_result(request_kind: str, failure_type: str, failure_message: str) -> NormalizedSourceResult:
    return NormalizedSourceResult(
        source_name=COINGECKO_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.FAILED,
        data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        failure_type=failure_type,
        failure_message=failure_message,
    )

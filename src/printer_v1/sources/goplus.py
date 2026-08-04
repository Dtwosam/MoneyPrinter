"""Governed GoPlus token safety reference adapter.

GoPlus provides free, read-only Solana token security data including
mint authority, freeze authority, holder concentration, liquidity lock
status, metadata mutability, and known risk signals.

No API key is required. No private key or transaction
building is performed. Data is read-only safety context for paper trading.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any, Callable, Mapping
from urllib import error as url_error
from urllib import request as url_request

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.sources.contracts import (
    GOVERNOR_ONLY_EXECUTION_PATH,
    NormalizedSourceResult,
    SourceAdapterContext,
    SourceAdapterContract,
    build_source_adapter_contract,
    validate_source_adapter_contract,
)
from printer_v1.sources.operational_source_contracts import (
    GOPLUS_SOLANA_SECURITY_URL,
)


GOPLUS_SOURCE_NAME = "goplus"
GOPLUS_SOLANA_TOKEN_SECURITY_URL = GOPLUS_SOLANA_SECURITY_URL
GOPLUS_TIMEOUT_SECONDS = 10.0
GOPLUS_PROVIDER_RATE_LIMIT_PER_MINUTE = 30
GOPLUS_TRANSPORT_OPERATION_COST = 1
GOPLUS_PUBLIC_API_HEADERS = {
    "User-Agent": "PrinterV1/0.1 (+paper-only safety check)",
    "Accept": "application/json",
}

ALLOWED_REQUEST_KINDS = frozenset({"safety_reference"})


@dataclass(frozen=True)
class GoPlusAdapterMetadata:
    source_name: str = GOPLUS_SOURCE_NAME
    display_name: str = "GoPlus"
    enabled_by_default: bool = False
    requires_governor_context: bool = True
    supports_network_execution: bool = False
    fixture_transport_only: bool = True


class GoPlusAdapter:
    """GoPlus adapter shell — disabled unless a governed caller injects transport.

    Read-only token safety data only. No execution or key operations.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
    ) -> None:
        self.metadata = GoPlusAdapterMetadata()
        self.contract = build_goplus_adapter_contract()
        self.enabled = enabled
        self.transport = fixture_transport
        self.call_count = 0

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not self.enabled:
            raise PermissionError("GoPlus adapter is disabled by default")
        if self.transport is None:
            raise PermissionError("GoPlus adapter requires an explicit transport")
        _validate_context(context, GOPLUS_SOURCE_NAME, self.contract)

        self.call_count += 1
        try:
            payload = self.transport(context)
        except Exception as exc:
            return _failure_result(
                context.request.request_kind, "goplus_transport_error", str(exc)
            )
        return normalize_goplus_payload(payload, request_kind=context.request.request_kind)


def build_goplus_adapter_contract() -> SourceAdapterContract:
    contract = build_source_adapter_contract(GOPLUS_SOURCE_NAME)
    if not validate_source_adapter_contract(contract):
        raise ValueError("GoPlus contract violates Source Governor boundary")
    return contract


def build_goplus_adapter(
    *,
    enabled: bool = False,
    fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
) -> GoPlusAdapter:
    return GoPlusAdapter(enabled=enabled, fixture_transport=fixture_transport)


def fixture_success_transport(
    payload: Mapping[str, Any],
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType(dict(payload))

    return transport


def fixture_failure_transport(
    message: str = "GoPlus fixture failure",
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType(
            {
                "fixture_status": "failure",
                "failure_type": "goplus_fixture_failure",
                "failure_message": message,
            }
        )

    return transport


def build_goplus_token_safety_transport(
    token_mint: str,
    *,
    timeout_seconds: float = GOPLUS_TIMEOUT_SECONDS,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """Return a real HTTP transport that fetches GoPlus token security data.

    Read-only GET request only. No API key required. No authentication.
    Returns raw GoPlus response for normalization.
    """
    endpoint = GOPLUS_SOLANA_TOKEN_SECURITY_URL.format(token_mint=token_mint)

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        payload = dict(_load_public_json(endpoint, timeout_seconds=timeout_seconds))
        payload["_requested_token_mint"] = token_mint
        return MappingProxyType(payload)

    return transport


def normalize_goplus_payload(
    payload: Mapping[str, Any],
    *,
    request_kind: str,
) -> NormalizedSourceResult:
    if request_kind not in ALLOWED_REQUEST_KINDS:
        return _failure_result(
            request_kind,
            "goplus_request_kind_not_allowed",
            "GoPlus request kind is not allowed",
        )

    fixture_status = payload.get("fixture_status")
    if fixture_status == "failure":
        return _failure_result(
            request_kind,
            str(payload.get("failure_type") or "goplus_fixture_failure"),
            str(payload.get("failure_message") or "GoPlus fixture failure"),
        )
    if fixture_status == "rate_limited":
        retry_at = (
            datetime.now(timezone.utc)
            + timedelta(seconds=int(payload.get("retry_after_seconds") or 120))
        ).isoformat()
        # One measured HTTP transport was attempted; surface the count so
        # holder-stage accounting can remain complete without inventing fallsbacks.
        measured_count = int(
            payload.get("underlying_operation_count")
            if payload.get("underlying_operation_count") is not None
            else GOPLUS_TRANSPORT_OPERATION_COST
        )
        return NormalizedSourceResult(
            source_name=GOPLUS_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.STALE,
            data_quality_label=DataQualityLabel.STALE_DATA,
            failure_type="goplus_rate_limited",
            failure_message="GoPlus rate limit",
            retry_after_at=retry_at,
            normalized_payload=MappingProxyType(
                {
                    "underlying_operation_count": measured_count,
                    "redacted_host": "api.gopluslabs.io",
                    "request_kind": request_kind,
                }
            ),
        )

    # GoPlus API returns {"code": 1, "message": "OK", "result": {...}}
    # The result may be pre-normalized (for fixtures) or raw API shape.
    code = payload.get("code")
    if code is not None and int(code) != 1:
        return _failure_result(
            request_kind,
            "goplus_api_error",
            f"GoPlus API returned code {code}: {payload.get('message', '')}",
        )

    requested_mint = str(payload.get("_requested_token_mint") or "").strip()
    result_data = payload.get("result") or payload
    # Extract token data — GoPlus wraps by mint address: {"<mint>": {...data...}}
    token_data: dict[str, Any] = {}
    if isinstance(result_data, dict) and requested_mint:
        matched_key = next(
            (
                key
                for key in result_data
                if str(key).lower() == requested_mint.lower()
                and isinstance(result_data.get(key), dict)
            ),
            None,
        )
        if matched_key is None and payload.get("result") is not None:
            return _failure_result(
                request_kind,
                "goplus_target_mint_mismatch",
                "GoPlus response did not contain the requested token mint",
            )
        if matched_key is not None:
            token_data = dict(result_data[matched_key])
    if isinstance(result_data, dict) and not token_data:
        values = list(result_data.values())
        if values and isinstance(values[0], dict):
            token_data = dict(values[0])
        elif "mint_authority" in result_data or "freeze_authority" in result_data:
            token_data = dict(result_data)

    if not token_data:
        return _failure_result(
            request_kind,
            "goplus_missing_token_data",
            "GoPlus response contained no token security data",
        )

    stale = bool(payload.get("fixture_stale"))
    normalized = dict(token_data)
    if requested_mint:
        normalized["token_mint"] = requested_mint
    normalized["source_name"] = GOPLUS_SOURCE_NAME
    normalized["request_kind"] = request_kind
    normalized["captured_at"] = datetime.now(timezone.utc).isoformat()
    # Authoritative single-HTTP measured cost for holder-stage accounting.
    if "underlying_operation_count" not in normalized or normalized[
        "underlying_operation_count"
    ] is None:
        if payload.get("underlying_operation_count") is not None:
            normalized["underlying_operation_count"] = int(
                payload["underlying_operation_count"]
            )
        else:
            normalized["underlying_operation_count"] = int(
                GOPLUS_TRANSPORT_OPERATION_COST
            )

    return NormalizedSourceResult(
        source_name=GOPLUS_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.STALE if stale else SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.STALE_DATA if stale else DataQualityLabel.CLEAN_DATA,
        normalized_payload=MappingProxyType(normalized),
        status_code=int(payload.get("_source_status_code") or 200),
    )


def _validate_context(
    context: SourceAdapterContext,
    source_name: str,
    contract: SourceAdapterContract,
) -> None:
    if not context or not context.governor_approved:
        raise PermissionError("source adapter execution requires Source Governor approval")
    if context.execution_path != GOVERNOR_ONLY_EXECUTION_PATH:
        raise PermissionError("source adapter execution requires governed recording path")
    if context.request.source_name != source_name:
        raise ValueError("source request does not match adapter")
    if context.request.request_kind not in contract.allowed_request_kinds:
        raise ValueError("source request kind is not allowed for adapter")


def _failure_result(
    request_kind: str,
    failure_type: str,
    failure_message: str,
) -> NormalizedSourceResult:
    return NormalizedSourceResult(
        source_name=GOPLUS_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.FAILED,
        data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        failure_type=failure_type,
        failure_message=failure_message,
    )


def _load_public_json(endpoint: str, *, timeout_seconds: float) -> Mapping[str, Any]:
    req = url_request.Request(
        endpoint,
        headers=GOPLUS_PUBLIC_API_HEADERS,
        method="GET",
    )
    try:
        with url_request.urlopen(req, timeout=timeout_seconds) as response:
            raw_body = response.read(512_000)
            data = json.loads(raw_body.decode("utf-8"))
            if isinstance(data, dict):
                data["_source_status_code"] = getattr(response, "status", None)
                return MappingProxyType(data)
            return MappingProxyType(
                {
                    "fixture_status": "failure",
                    "failure_type": "goplus_non_object_payload",
                    "failure_message": "GoPlus returned non-object payload",
                }
            )
    except url_error.HTTPError as exc:
        if exc.code == 429:
            return MappingProxyType({"fixture_status": "rate_limited", "retry_after_seconds": 120})
        return MappingProxyType(
            {
                "fixture_status": "failure",
                "failure_type": "goplus_http_error",
                "failure_message": f"GoPlus HTTP error {exc.code}",
            }
        )
    except (OSError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return MappingProxyType(
            {
                "fixture_status": "failure",
                "failure_type": "goplus_transport_failure",
                "failure_message": str(exc),
            }
        )

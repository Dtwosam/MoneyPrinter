"""Fixed Helius Free RPC holder-concentration backup.

The adapter is disabled unless an explicit transport is supplied and can only
run through Source Governor. Production transport uses one fixed Helius mainnet
host, two read-only finalized methods, and no retry or endpoint rotation.
"""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
from typing import Any, Callable, Mapping
from urllib import parse as url_parse

from printer_v1.sources.contracts import (
    GOVERNOR_ONLY_EXECUTION_PATH,
    NormalizedSourceResult,
    SourceAdapterContext,
    SourceAdapterContract,
    build_source_adapter_contract,
    validate_source_adapter_contract,
)
from printer_v1.sources.solana_rpc_holder import (
    SOLANA_RPC_TIMEOUT_SECONDS,
    _fetch_holder_data,
    normalize_solana_rpc_holder_response,
)
from printer_v1.sources.operational_source_contracts import (
    HELIUS_FIXED_MAINNET_URL as SHARED_HELIUS_FIXED_MAINNET_URL,
)


HELIUS_SOURCE_NAME = "helius_free"
HELIUS_FIXED_MAINNET_HOST = "mainnet.helius-rpc.com"
HELIUS_FIXED_MAINNET_URL = SHARED_HELIUS_FIXED_MAINNET_URL
HELIUS_API_KEY_ENV = "PRINTER_HELIUS_API_KEY"
HELIUS_FREE_RPC_RATE_LIMIT_PER_SECOND = 10
HELIUS_STANDARD_RPC_CREDITS_PER_OPERATION = 1


class HeliusHolderConfigurationError(RuntimeError):
    pass


class HeliusHolderAdapter:
    def __init__(
        self,
        *,
        enabled: bool = False,
        fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
    ) -> None:
        self.contract = build_helius_holder_adapter_contract()
        self.enabled = enabled
        self.transport = fixture_transport
        self.call_count = 0

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not self.enabled:
            raise PermissionError("Helius holder adapter is disabled by default")
        if self.transport is None:
            raise PermissionError("Helius holder adapter requires an explicit transport")
        if not context.governor_approved or context.execution_path != GOVERNOR_ONLY_EXECUTION_PATH:
            raise PermissionError("Helius holder execution requires Source Governor approval")
        if context.request.source_name != HELIUS_SOURCE_NAME:
            raise ValueError("source request does not match Helius holder adapter")
        if context.request.request_kind not in self.contract.allowed_request_kinds:
            raise ValueError("request kind is not allowed for Helius holder adapter")
        self.call_count += 1
        try:
            payload = self.transport(context)
        except Exception as exc:
            payload = MappingProxyType({
                "fixture_status": "failure",
                "failure_type": "helius_transport_failure",
                "failure_message": str(exc),
                "underlying_operation_count": 1,
            })
        return normalize_helius_holder_response(
            payload, request_kind=context.request.request_kind
        )


def build_helius_holder_adapter_contract() -> SourceAdapterContract:
    contract = build_source_adapter_contract(HELIUS_SOURCE_NAME)
    if not validate_source_adapter_contract(contract):
        raise ValueError("Helius holder contract violates Source Governor boundary")
    return contract


def build_helius_holder_adapter(
    *,
    enabled: bool = False,
    fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
) -> HeliusHolderAdapter:
    return HeliusHolderAdapter(enabled=enabled, fixture_transport=fixture_transport)


def build_helius_holder_transport(
    token_mint: str,
    *,
    api_key: str,
    timeout_seconds: float = SOLANA_RPC_TIMEOUT_SECONDS,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """Build the sole fixed-host transport; the returned closure retries zero times."""
    key = str(api_key).strip()
    if not key:
        raise HeliusHolderConfigurationError("HELIUS_FREE_API_KEY_REQUIRED")
    rpc_url = HELIUS_FIXED_MAINNET_URL + "?" + url_parse.urlencode({"api-key": key})

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        result = dict(_fetch_holder_data(
            token_mint, rpc_url=rpc_url, timeout_seconds=timeout_seconds
        ))
        for field in ("failure_message", "retry_after"):
            if isinstance(result.get(field), str):
                result[field] = result[field].replace(key, "[REDACTED]")
        return MappingProxyType(result)

    return transport


def normalize_helius_holder_response(
    payload: Mapping[str, Any], *, request_kind: str
) -> NormalizedSourceResult:
    base = normalize_solana_rpc_holder_response(payload, request_kind=request_kind)
    normalized_payload = dict(base.normalized_payload or {})
    normalized_payload["source_name"] = HELIUS_SOURCE_NAME
    normalized_payload["endpoint_role"] = "BACKUP"
    normalized_payload["redacted_host"] = HELIUS_FIXED_MAINNET_HOST
    failure_type = base.failure_type
    if failure_type:
        failure_type = failure_type.replace("solana_rpc", "helius", 1)
        normalized_payload["failure_type"] = failure_type
    return replace(
        base,
        source_name=HELIUS_SOURCE_NAME,
        failure_type=failure_type,
        normalized_payload=MappingProxyType(normalized_payload),
    )


def resolve_holder_concentration_facts(
    facts: tuple[Mapping[str, Any], ...],
) -> Mapping[str, Any]:
    """Resolve clean exact facts; disagreements fail closed without weighting."""
    usable = [
        fact for fact in facts
        if fact.get("eligible")
        and fact.get("holder_concentration_label")
        not in (None, "HOLDER_CONCENTRATION_UNKNOWN")
    ]
    labels = {str(fact["holder_concentration_label"]) for fact in usable}
    if len(labels) > 1:
        return MappingProxyType({
            "eligible": False,
            "reason": "HOLDER_EVIDENCE_CONFLICT",
            "source_name": None,
        })
    if usable:
        return MappingProxyType(dict(usable[0]))
    return MappingProxyType({
        "eligible": False,
        "reason": "HOLDER_EVIDENCE_UNAVAILABLE",
        "source_name": None,
    })

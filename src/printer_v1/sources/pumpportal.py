"""Governed PumpPortal free-stream discovery adapter.

Supports only the two allowed free public streams:
  - pumpfun_launch_stream  (subscribeNewToken events)
  - pumpfun_migration_stream  (subscribeMigration events)

Metered, paid, or trading-related streams such as subscribeTokenTrade
and subscribeAccountTrade are outside the allowed_request_kinds and
are rejected at the Source Governor boundary.

This adapter is fixture-transport-only. No persistent streaming loop
is started here. Controlled collection is bounded and operator-approved.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Callable, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.sources.contracts import (
    GOVERNOR_ONLY_EXECUTION_PATH,
    NormalizedSourceResult,
    SourceAdapterContext,
    SourceAdapterContract,
    build_source_adapter_contract,
    validate_source_adapter_contract,
)


PUMPPORTAL_SOURCE_NAME = "pumpportal"

ALLOWED_REQUEST_KINDS = frozenset({
    "pumpfun_launch_stream",
    "pumpfun_migration_stream",
})

_SOLANA_CHAIN = "solana"


@dataclass(frozen=True)
class PumpPortalAdapterMetadata:
    source_name: str = PUMPPORTAL_SOURCE_NAME
    display_name: str = "PumpPortal"
    enabled_by_default: bool = False
    requires_governor_context: bool = True
    supports_network_execution: bool = False
    fixture_transport_only: bool = True


class PumpPortalAdapter:
    """PumpPortal adapter shell, disabled unless a governed caller injects transport.

    Only free launch and migration stream data is accepted. No metered
    streams, no trading endpoints, no transaction building, no swaps.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
    ) -> None:
        self.metadata = PumpPortalAdapterMetadata()
        self.contract = build_pumpportal_adapter_contract()
        self.enabled = enabled
        self.transport = fixture_transport
        self.call_count = 0

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not self.enabled:
            raise PermissionError("PumpPortal adapter is disabled by default")
        if self.transport is None:
            raise PermissionError("PumpPortal adapter requires an explicit transport")
        _validate_context(context, PUMPPORTAL_SOURCE_NAME, self.contract)

        self.call_count += 1
        try:
            payload = self.transport(context)
        except Exception as exc:
            return _failure_result(
                context.request.request_kind, "pumpportal_transport_error", str(exc)
            )
        return normalize_pumpportal_payload(payload, request_kind=context.request.request_kind)


def build_pumpportal_adapter_contract() -> SourceAdapterContract:
    contract = build_source_adapter_contract(PUMPPORTAL_SOURCE_NAME)
    if not validate_source_adapter_contract(contract):
        raise ValueError("PumpPortal contract violates Source Governor boundary")
    return contract


def build_pumpportal_adapter(
    *,
    enabled: bool = False,
    fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
) -> PumpPortalAdapter:
    return PumpPortalAdapter(enabled=enabled, fixture_transport=fixture_transport)


def fixture_success_transport(
    payload: Mapping[str, Any],
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType(dict(payload))

    return transport


def fixture_failure_transport(
    message: str = "PumpPortal fixture failure",
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType(
            {
                "fixture_status": "failure",
                "failure_type": "pumpportal_fixture_failure",
                "failure_message": message,
            }
        )

    return transport


def normalize_pumpportal_payload(
    payload: Mapping[str, Any],
    *,
    request_kind: str,
) -> NormalizedSourceResult:
    if request_kind not in ALLOWED_REQUEST_KINDS:
        return _failure_result(
            request_kind,
            "pumpportal_request_kind_not_allowed",
            "PumpPortal request kind is not allowed",
        )

    fixture_status = payload.get("fixture_status")
    if fixture_status == "failure":
        return _failure_result(
            request_kind,
            str(payload.get("failure_type") or "pumpportal_fixture_failure"),
            str(payload.get("failure_message") or "PumpPortal fixture failure"),
        )
    if fixture_status == "stale":
        return NormalizedSourceResult(
            source_name=PUMPPORTAL_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.STALE,
            data_quality_label=DataQualityLabel.STALE_DATA,
            failure_type="pumpportal_stale_data",
            failure_message="PumpPortal fixture stale data",
        )

    # Accept pre-normalized "tokens" list (matches existing pumpportal_payload fixture format)
    # or raw "events" list (batch of PumpPortal stream events)
    pre_normalized = payload.get("tokens")
    if isinstance(pre_normalized, list):
        solana_tokens = [
            t for t in pre_normalized
            if isinstance(t, Mapping) and str(t.get("chain") or "").lower() == _SOLANA_CHAIN
        ]
    else:
        raw_events = payload.get("events") or []
        if not isinstance(raw_events, list):
            return _failure_result(
                request_kind,
                "pumpportal_missing_event_list",
                "PumpPortal payload missing tokens or events list",
            )
        solana_tokens = []
        for event in raw_events:
            if not isinstance(event, Mapping):
                continue
            normalized = _normalize_pumpportal_event(event, request_kind)
            if normalized:
                solana_tokens.append(normalized)

    if not solana_tokens:
        return _failure_result(
            request_kind,
            "pumpportal_no_valid_solana_events",
            "PumpPortal payload contained no valid Solana events",
        )

    stale = bool(payload.get("fixture_stale"))
    return NormalizedSourceResult(
        source_name=PUMPPORTAL_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.STALE if stale else SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.STALE_DATA if stale else DataQualityLabel.CLEAN_DATA,
        normalized_payload=MappingProxyType(
            {
                "source_name": PUMPPORTAL_SOURCE_NAME,
                "request_kind": request_kind,
                "tokens": solana_tokens,
            }
        ),
        status_code=200,
    )


def _normalize_pumpportal_event(
    event: Mapping[str, Any],
    request_kind: str,
) -> dict[str, Any] | None:
    """Normalize one raw PumpPortal stream event into the discovery pipeline format."""
    token_mint = event.get("mint") or event.get("tokenMint") or event.get("token_mint")
    if not token_mint:
        return None

    # For migration events, prefer the post-migration pool address
    pair_address = (
        event.get("newRaydiumPool")
        or event.get("pairAddress")
        or event.get("pair_address")
        or event.get("bondingCurveKey")
    )

    # Estimate liquidity from bonding curve SOL reserves if available
    liquidity_usd = _to_float(
        event.get("liquidity_usd")
        or event.get("liquidityUsd")
        or _sol_to_approx_usd(event.get("vSolInBondingCurve") or event.get("solAmount"))
    )

    return {
        "chain": _SOLANA_CHAIN,
        "mint": token_mint,
        "pairAddress": pair_address,
        "symbol": event.get("symbol"),
        "name": event.get("name"),
        "dex": "pumpfun" if request_kind == "pumpfun_launch_stream" else "raydium",
        "poolSource": PUMPPORTAL_SOURCE_NAME,
        "price_usd": _to_str_or_none(
            event.get("priceUsd") or event.get("price_usd")
        ),
        "liquidity_usd": liquidity_usd,
        "captured_at": _current_iso() if not event.get("captured_at") and not event.get("timestamp") else (
            event.get("captured_at") or event.get("timestamp")
        ),
    }


def _sol_to_approx_usd(sol_amount: Any) -> float | None:
    """Approximate SOL amount to USD using a conservative fixed rate for gate comparison only."""
    amount = _to_float(sol_amount)
    if amount is None:
        return None
    return amount * 150.0


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_str_or_none(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _current_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        source_name=PUMPPORTAL_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.FAILED,
        data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        failure_type=failure_type,
        failure_message=failure_message,
    )

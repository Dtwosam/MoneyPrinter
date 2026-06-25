"""Governed Jupiter paper quote realism adapter.

Jupiter provides a free, public quote API that returns route and price
information for paper simulation purposes. This adapter fetches read-only
quote data only. It does NOT build, sign, simulate, or send transactions.
No private key or key operation is involved.

The quote is used exclusively for paper realism evidence: whether a
realistic entry or exit was available at this price and liquidity level.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
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


JUPITER_QUOTE_SOURCE_NAME = "jupiter_quote"
# Primary free/no-key endpoint. lite-api.jup.ag is the current no-key quote path.
JUPITER_QUOTE_API_URL = "https://lite-api.jup.ag/swap/v1/quote"
# Legacy endpoint — kept only as a named constant so tests can assert it is NOT the default.
JUPITER_QUOTE_LEGACY_V6_URL = "https://quote-api.jup.ag/v6/quote"
JUPITER_QUOTE_TIMEOUT_SECONDS = 8.0
JUPITER_QUOTE_PUBLIC_API_HEADERS = {
    "User-Agent": "PrinterV1/0.1 (+paper-only quote check)",
    "Accept": "application/json",
}

# Default paper simulation amount: 0.001 SOL in lamports (safe, small amount)
DEFAULT_PAPER_AMOUNT_LAMPORTS = 1_000_000
DEFAULT_SLIPPAGE_BPS = 50

# Wrapped SOL mint address (used as quote currency for paper simulations)
WSOL_MINT = "So11111111111111111111111111111111111111112"

ALLOWED_REQUEST_KINDS = frozenset({"paper_quote_realism"})


@dataclass(frozen=True)
class JupiterQuoteAdapterMetadata:
    source_name: str = JUPITER_QUOTE_SOURCE_NAME
    display_name: str = "Jupiter Quote"
    enabled_by_default: bool = False
    requires_governor_context: bool = True
    supports_network_execution: bool = False
    fixture_transport_only: bool = True
    read_only: bool = True


class JupiterQuoteAdapter:
    """Jupiter Quote adapter — paper quote realism only, disabled unless transport injected.

    Fetches read-only quote data for paper simulation realism checks.
    Does not build or submit transactions of any kind.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
    ) -> None:
        self.metadata = JupiterQuoteAdapterMetadata()
        self.contract = build_jupiter_quote_adapter_contract()
        self.enabled = enabled
        self.transport = fixture_transport
        self.call_count = 0

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not self.enabled:
            raise PermissionError("Jupiter Quote adapter is disabled by default")
        if self.transport is None:
            raise PermissionError("Jupiter Quote adapter requires an explicit transport")
        _validate_context(context, JUPITER_QUOTE_SOURCE_NAME, self.contract)

        self.call_count += 1
        try:
            payload = self.transport(context)
        except Exception as exc:
            return _failure_result(
                context.request.request_kind, "jupiter_quote_transport_error", str(exc)
            )
        return normalize_jupiter_quote_response(payload, request_kind=context.request.request_kind)


def build_jupiter_quote_adapter_contract() -> SourceAdapterContract:
    contract = build_source_adapter_contract(JUPITER_QUOTE_SOURCE_NAME)
    if not validate_source_adapter_contract(contract):
        raise ValueError("Jupiter Quote contract violates Source Governor boundary")
    return contract


def build_jupiter_quote_adapter(
    *,
    enabled: bool = False,
    fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
) -> JupiterQuoteAdapter:
    return JupiterQuoteAdapter(enabled=enabled, fixture_transport=fixture_transport)


def fixture_success_transport(
    payload: Mapping[str, Any],
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType(dict(payload))

    return transport


def fixture_failure_transport(
    message: str = "Jupiter Quote fixture failure",
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType(
            {
                "fixture_status": "failure",
                "failure_type": "jupiter_quote_fixture_failure",
                "failure_message": message,
            }
        )

    return transport


def build_jupiter_paper_quote_transport(
    *,
    input_mint: str,
    output_mint: str,
    amount_lamports: int = DEFAULT_PAPER_AMOUNT_LAMPORTS,
    slippage_bps: int = DEFAULT_SLIPPAGE_BPS,
    timeout_seconds: float = JUPITER_QUOTE_TIMEOUT_SECONDS,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """Return a real HTTP transport that fetches a read-only Jupiter paper quote.

    This requests quote information only — no transaction building,
    no key operations, no execution. The response is used purely for paper
    realism evidence (route availability, slippage, price impact).
    """
    params = (
        f"?inputMint={input_mint}"
        f"&outputMint={output_mint}"
        f"&amount={amount_lamports}"
        f"&slippageBps={slippage_bps}"
        f"&onlyDirectRoutes=false"
    )
    endpoint = JUPITER_QUOTE_API_URL + params

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return _load_public_json(endpoint, timeout_seconds=timeout_seconds)

    return transport


def normalize_jupiter_quote_response(
    payload: Mapping[str, Any],
    *,
    request_kind: str,
) -> NormalizedSourceResult:
    if request_kind not in ALLOWED_REQUEST_KINDS:
        return _failure_result(
            request_kind,
            "jupiter_quote_request_kind_not_allowed",
            "Jupiter Quote request kind is not allowed",
        )

    fixture_status = payload.get("fixture_status")
    if fixture_status == "failure":
        return _failure_result(
            request_kind,
            str(payload.get("failure_type") or "jupiter_quote_fixture_failure"),
            str(payload.get("failure_message") or "Jupiter Quote fixture failure"),
        )
    if fixture_status == "rate_limited":
        return _failure_result(
            request_kind,
            "jupiter_quote_rate_limited",
            "Jupiter Quote rate limited",
        )
    if fixture_status == "no_route":
        # Jupiter returned no route — valid paper evidence of route unavailability
        normalized = {
            "route_available": False,
            "route_plan_present": False,
            "quote_captured_at": datetime.now(timezone.utc).isoformat(),
            "freshness_label": "QUOTE_FRESH",
            "target_status": "TARGET_MATCH",
            "paper_only_context": True,
            "liquidity_context_label": "LIQUIDITY_CONTEXT_CAUTION",
            "source_name": JUPITER_QUOTE_SOURCE_NAME,
            "request_kind": request_kind,
        }
        return NormalizedSourceResult(
            source_name=JUPITER_QUOTE_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.ACCEPTABLE_PARTIAL_DATA,
            normalized_payload=MappingProxyType(normalized),
            status_code=200,
        )

    # Real Jupiter v6 quote response or a pre-normalized fixture
    route_plan = payload.get("routePlan") or payload.get("route_plan") or []
    has_route = isinstance(route_plan, list) and len(route_plan) > 0
    price_impact_pct = payload.get("priceImpactPct") or payload.get("price_impact_pct") or "0"
    slippage_bps = payload.get("slippageBps") or payload.get("slippage_bps") or 0

    try:
        price_impact_bps = float(price_impact_pct) * 100
    except (TypeError, ValueError):
        price_impact_bps = 0.0

    # If the payload already has pre-normalized quote fields, pass through
    if payload.get("route_available") is not None:
        normalized = dict(payload)
        normalized.setdefault("source_name", JUPITER_QUOTE_SOURCE_NAME)
        normalized.setdefault("request_kind", request_kind)
        stale = bool(payload.get("fixture_stale"))
        return NormalizedSourceResult(
            source_name=JUPITER_QUOTE_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.STALE if stale else SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.STALE_DATA if stale else DataQualityLabel.CLEAN_DATA,
            normalized_payload=MappingProxyType(normalized),
            status_code=int(payload.get("_source_status_code") or 200),
        )

    # Normalize raw Jupiter v6 API response
    normalized = {
        "route_available": has_route,
        "route_plan_present": has_route,
        "slippage_bps": int(slippage_bps),
        "price_impact_bps": round(price_impact_bps, 2),
        "quote_captured_at": datetime.now(timezone.utc).isoformat(),
        "freshness_label": "QUOTE_FRESH",
        "target_status": "TARGET_MATCH",
        "paper_only_context": True,
        "liquidity_context_label": (
            "LIQUIDITY_CONTEXT_ACCEPTABLE" if has_route else "LIQUIDITY_CONTEXT_CAUTION"
        ),
        "source_name": JUPITER_QUOTE_SOURCE_NAME,
        "request_kind": request_kind,
    }

    stale = bool(payload.get("fixture_stale"))
    return NormalizedSourceResult(
        source_name=JUPITER_QUOTE_SOURCE_NAME,
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
        source_name=JUPITER_QUOTE_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.FAILED,
        data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        failure_type=failure_type,
        failure_message=failure_message,
    )


def _load_public_json(endpoint: str, *, timeout_seconds: float) -> Mapping[str, Any]:
    req = url_request.Request(
        endpoint,
        headers=JUPITER_QUOTE_PUBLIC_API_HEADERS,
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
                    "failure_type": "jupiter_quote_non_object_payload",
                    "failure_message": "Jupiter Quote returned non-object payload",
                }
            )
    except url_error.HTTPError as exc:
        if exc.code == 429:
            return MappingProxyType({"fixture_status": "rate_limited"})
        if exc.code == 400:
            # 400 often means no route available
            return MappingProxyType({"fixture_status": "no_route", "http_status": 400})
        return MappingProxyType(
            {
                "fixture_status": "failure",
                "failure_type": "jupiter_quote_http_error",
                "failure_message": f"Jupiter Quote HTTP error {exc.code}",
            }
        )
    except (OSError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return MappingProxyType(
            {
                "fixture_status": "failure",
                "failure_type": "jupiter_quote_transport_failure",
                "failure_message": str(exc),
            }
        )

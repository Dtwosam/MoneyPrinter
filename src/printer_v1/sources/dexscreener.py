"""Disabled-by-default DexScreener source adapter boundary."""

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


DEXSCREENER_SOURCE_NAME = "dexscreener"

# Solana infrastructure / native-quote mints. A DexScreener pair whose
# baseToken.address resolves to one of these is an infrastructure/quote asset
# (WSOL / USDC / USDT), never a memecoin discovery target. These must be
# excluded before a candidate is emitted so an infrastructure mint can never
# occupy a memecoin tracking slot. This mirrors
# geckoterminal._SOLANA_NATIVE_QUOTE_MINTS exactly. Source of truth:
# docs/solana-builder-source-of-truth/solana-mint-addresses.md
_SOLANA_INFRASTRUCTURE_MINTS = frozenset({
    "So11111111111111111111111111111111111111112",   # WSOL (Wrapped SOL / native SOL)
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC (Circle official Solana mainnet)
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT / USDt (Tether Solana)
})

DEXSCREENER_SMOKE_URL = "https://api.dexscreener.com/latest/dex/search?q=SOL"
DEXSCREENER_PAIR_URL_TEMPLATE = "https://api.dexscreener.com/latest/dex/pairs/solana/{pair_address}"
DEXSCREENER_TOKEN_URL_TEMPLATE = "https://api.dexscreener.com/latest/dex/tokens/{token_mint}"
DEXSCREENER_SMOKE_TIMEOUT_SECONDS = 5.0
DEXSCREENER_PUBLIC_API_HEADERS = {
    "User-Agent": "PrinterV1/0.1 (+paper-only source check)",
    "Accept": "application/json",
}


@dataclass(frozen=True)
class DexScreenerAdapterMetadata:
    source_name: str = DEXSCREENER_SOURCE_NAME
    display_name: str = "DexScreener"
    enabled_by_default: bool = False
    requires_governor_context: bool = True
    supports_network_execution: bool = False
    fixture_transport_only: bool = True


class DexScreenerAdapter:
    """DexScreener adapter shell, disabled unless an operator path enables it."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
        smoke_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
    ) -> None:
        self.metadata = DexScreenerAdapterMetadata()
        self.contract = build_dexscreener_adapter_contract()
        self.enabled = enabled
        self.transport = fixture_transport or smoke_transport
        self.call_count = 0

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not self.enabled:
            raise PermissionError("DexScreener adapter is disabled by default")
        if self.transport is None:
            raise PermissionError("DexScreener adapter requires an explicit transport")
        if not context or not context.governor_approved:
            raise PermissionError("DexScreener adapter execution requires Source Governor approval")
        if context.execution_path != GOVERNOR_ONLY_EXECUTION_PATH:
            raise PermissionError("DexScreener adapter execution requires governed recording path")
        if context.request.source_name != DEXSCREENER_SOURCE_NAME:
            raise ValueError("source request does not match DexScreener")
        if context.request.request_kind not in self.contract.allowed_request_kinds:
            raise ValueError("source request kind is not allowed for DexScreener")

        self.call_count += 1
        try:
            payload = self.transport(context)
        except Exception as exc:
            return NormalizedSourceResult(
                source_name=DEXSCREENER_SOURCE_NAME,
                request_kind=context.request.request_kind,
                source_status=SourceStatus.FAILED,
                data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
                failure_type="dexscreener_transport_error",
                failure_message=str(exc),
            )
        return normalize_dexscreener_fixture_result(payload, request_kind=context.request.request_kind)


def build_dexscreener_adapter_contract() -> SourceAdapterContract:
    contract = build_source_adapter_contract(DEXSCREENER_SOURCE_NAME)
    if not validate_source_adapter_contract(contract):
        raise ValueError("DexScreener contract violates Source Governor boundary")
    return contract


def get_dexscreener_adapter_metadata() -> DexScreenerAdapterMetadata:
    return DexScreenerAdapterMetadata()


def build_dexscreener_adapter(
    *,
    enabled: bool = False,
    fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
    smoke_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
) -> DexScreenerAdapter:
    return DexScreenerAdapter(
        enabled=enabled,
        fixture_transport=fixture_transport,
        smoke_transport=smoke_transport,
    )


def fixture_success_transport(payload: Mapping[str, Any]) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType(dict(payload))

    return transport


def fixture_rate_limited_transport() -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType({"fixture_status": "rate_limited", "retry_after_seconds": 60})

    return transport


def build_dexscreener_smoke_transport(
    *,
    timeout_seconds: float = DEXSCREENER_SMOKE_TIMEOUT_SECONDS,
    endpoint: str = DEXSCREENER_SMOKE_URL,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        request = url_request.Request(
            endpoint,
            headers=DEXSCREENER_PUBLIC_API_HEADERS,
            method="GET",
        )
        try:
            with url_request.urlopen(request, timeout=timeout_seconds) as response:
                raw_body = response.read(512_000)
                payload = json.loads(raw_body.decode("utf-8"))
                if isinstance(payload, dict):
                    payload["_source_status_code"] = getattr(response, "status", None)
                    return MappingProxyType(payload)
                return MappingProxyType({"fixture_status": "failure", "failure_message": "DexScreener returned non-object payload"})
        except url_error.HTTPError as exc:
            if exc.code == 429:
                return MappingProxyType({"fixture_status": "rate_limited", "retry_after_seconds": 60})
            return MappingProxyType(
                {
                    "fixture_status": "failure",
                    "failure_type": "dexscreener_http_error",
                    "failure_message": f"DexScreener HTTP error {exc.code}",
                }
            )
        except (OSError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return MappingProxyType(
                {
                    "fixture_status": "failure",
                    "failure_type": "dexscreener_transport_failure",
                    "failure_message": str(exc),
                }
            )

    return transport


def build_dexscreener_token_transport(
    token_mint: str,
    *,
    timeout_seconds: float = DEXSCREENER_SMOKE_TIMEOUT_SECONDS,
    endpoint_template: str = DEXSCREENER_TOKEN_URL_TEMPLATE,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """Build a real transport callable for a specific token mint address.

    Uses the free/public DexScreener tokens endpoint, not the generic SOL search.
    No authentication. No paid tier. Suitable for E2I one-shot governed smoke.
    """
    endpoint = endpoint_template.format(token_mint=token_mint)
    return build_dexscreener_smoke_transport(
        timeout_seconds=timeout_seconds,
        endpoint=endpoint,
    )


def build_dexscreener_pair_snapshot_transport(
    pair_address: str,
    *,
    timeout_seconds: float = DEXSCREENER_SMOKE_TIMEOUT_SECONDS,
    endpoint_template: str = DEXSCREENER_PAIR_URL_TEMPLATE,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    endpoint = endpoint_template.format(pair_address=pair_address)
    return build_dexscreener_smoke_transport(
        timeout_seconds=timeout_seconds,
        endpoint=endpoint,
    )


def normalize_dexscreener_fixture_result(
    payload: Mapping[str, Any],
    *,
    request_kind: str,
) -> NormalizedSourceResult:
    fixture_status = payload.get("fixture_status")
    if fixture_status == "failure":
        return NormalizedSourceResult(
            source_name=DEXSCREENER_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.FAILED,
            data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
            failure_type=str(payload.get("failure_type") or "dexscreener_fixture_failure"),
            failure_message=str(payload.get("failure_message") or "DexScreener fixture failure"),
        )
    if fixture_status == "rate_limited":
        retry_after = int(payload.get("retry_after_seconds") or 60)
        retry_at = (datetime.now(timezone.utc) + timedelta(seconds=retry_after)).isoformat()
        return NormalizedSourceResult(
            source_name=DEXSCREENER_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.STALE,
            data_quality_label=DataQualityLabel.STALE_DATA,
            failure_type="dexscreener_rate_limited_fixture",
            failure_message="DexScreener fixture rate limit",
            retry_after_at=retry_at,
        )

    pairs = payload.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        return NormalizedSourceResult(
            source_name=DEXSCREENER_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.FAILED,
            data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
            failure_type="dexscreener_malformed_fixture",
            failure_message="DexScreener fixture missing pairs",
        )

    normalized_pairs = []
    for pair in pairs:
        if not isinstance(pair, Mapping):
            continue
        base = pair.get("baseToken") if isinstance(pair.get("baseToken"), Mapping) else {}
        normalized_pairs.append(
            {
                "chain": pair.get("chainId"),
                "pair_address": pair.get("pairAddress"),
                "token_mint": base.get("address"),
                "symbol": base.get("symbol"),
                "name": base.get("name"),
                "price_usd": _to_float(pair.get("priceUsd")),
                "liquidity_usd": _to_float((pair.get("liquidity") or {}).get("usd") if isinstance(pair.get("liquidity"), Mapping) else None),
                "volume_5m": _to_float((pair.get("volume") or {}).get("m5") if isinstance(pair.get("volume"), Mapping) else None),
                "volume_1h": _to_float((pair.get("volume") or {}).get("h1") if isinstance(pair.get("volume"), Mapping) else None),
                "volume_24h": _to_float((pair.get("volume") or {}).get("h24") if isinstance(pair.get("volume"), Mapping) else None),
                "txns_5m": _to_int(_transaction_count((pair.get("txns") or {}).get("m5") if isinstance(pair.get("txns"), Mapping) else None)),
                "txns_1h": _to_int(_transaction_count((pair.get("txns") or {}).get("h1") if isinstance(pair.get("txns"), Mapping) else None)),
                "txns_24h": _to_int(_transaction_count((pair.get("txns") or {}).get("h24") if isinstance(pair.get("txns"), Mapping) else None)),
                "buys_5m": _transaction_buys((pair.get("txns") or {}).get("m5") if isinstance(pair.get("txns"), Mapping) else None),
                "sells_5m": _transaction_sells((pair.get("txns") or {}).get("m5") if isinstance(pair.get("txns"), Mapping) else None),
                "buys_1h": _transaction_buys((pair.get("txns") or {}).get("h1") if isinstance(pair.get("txns"), Mapping) else None),
                "sells_1h": _transaction_sells((pair.get("txns") or {}).get("h1") if isinstance(pair.get("txns"), Mapping) else None),
                "buys_24h": _transaction_buys((pair.get("txns") or {}).get("h24") if isinstance(pair.get("txns"), Mapping) else None),
                "sells_24h": _transaction_sells((pair.get("txns") or {}).get("h24") if isinstance(pair.get("txns"), Mapping) else None),
                "fdv": _to_float(pair.get("fdv")),
                "market_cap": _to_float(pair.get("marketCap")),
                "price_change_5m": _to_float((pair.get("priceChange") or {}).get("m5") if isinstance(pair.get("priceChange"), Mapping) else None),
                "price_change_1h": _to_float((pair.get("priceChange") or {}).get("h1") if isinstance(pair.get("priceChange"), Mapping) else None),
                "price_change_24h": _to_float((pair.get("priceChange") or {}).get("h24") if isinstance(pair.get("priceChange"), Mapping) else None),
                "pair_created_at": pair.get("pairCreatedAt"),
            }
        )

    # Categorical productivity/safety filter (Stage 2 repair): drop non-Solana
    # pairs and infrastructure quote-mints at the source boundary so the
    # downstream candidate stream carries only Solana memecoin candidates.
    # Every excluded pair is recorded with an explicit categorical reason —
    # never silently dropped. No scores, ranks, or weighted logic are applied.
    kept_pairs: list[dict[str, Any]] = []
    excluded_pairs: list[dict[str, Any]] = []
    for item in normalized_pairs:
        exclusion_reason: str | None = None
        if item.get("chain") != "solana":
            exclusion_reason = "non_solana_pair"
        elif not item.get("pair_address") or not item.get("token_mint"):
            exclusion_reason = "missing_pair_or_mint_identity"
        elif item.get("token_mint") in _SOLANA_INFRASTRUCTURE_MINTS:
            exclusion_reason = "infrastructure_quote_mint"
        if exclusion_reason:
            excluded_pairs.append({
                "chain": item.get("chain"),
                "pair_address": item.get("pair_address"),
                "token_mint": item.get("token_mint"),
                "symbol": item.get("symbol"),
                "exclusion_reason": exclusion_reason,
            })
        else:
            kept_pairs.append(item)

    if not kept_pairs:
        return NormalizedSourceResult(
            source_name=DEXSCREENER_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.FAILED,
            data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
            failure_type="dexscreener_missing_critical_fixture_fields",
            failure_message="DexScreener fixture missing Solana memecoin pair identity",
        )

    stale = bool(payload.get("fixture_stale"))
    return NormalizedSourceResult(
        source_name=DEXSCREENER_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.STALE if stale else SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.STALE_DATA if stale else DataQualityLabel.CLEAN_DATA,
        normalized_payload=MappingProxyType(
            {
                "source_name": DEXSCREENER_SOURCE_NAME,
                "request_kind": request_kind,
                "pairs": kept_pairs,
                "excluded_pairs": excluded_pairs,
                "excluded_pair_count": len(excluded_pairs),
            }
        ),
        status_code=int(payload.get("_source_status_code") or 200),
    )


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _transaction_count(value: Any) -> int | None:
    if not isinstance(value, Mapping):
        return None
    buys = _to_int(value.get("buys")) or 0
    sells = _to_int(value.get("sells")) or 0
    return buys + sells


def _transaction_buys(value: Any) -> int | None:
    if not isinstance(value, Mapping):
        return None
    return _to_int(value.get("buys"))


def _transaction_sells(value: Any) -> int | None:
    if not isinstance(value, Mapping):
        return None
    return _to_int(value.get("sells"))

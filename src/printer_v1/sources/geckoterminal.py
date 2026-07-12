"""Governed GeckoTerminal Solana pool discovery adapter."""

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


GECKOTERMINAL_SOURCE_NAME = "geckoterminal"
GECKOTERMINAL_NEW_POOLS_URL = (
    "https://api.geckoterminal.com/api/v2/networks/solana/new_pools?page=1"
)
GECKOTERMINAL_TRENDING_POOLS_URL = (
    "https://api.geckoterminal.com/api/v2/networks/solana/trending_pools?page=1"
)
GECKOTERMINAL_TIMEOUT_SECONDS = 8.0
GECKOTERMINAL_PUBLIC_API_HEADERS = {
    "User-Agent": "PrinterV1/0.1 (+paper-only source check)",
    "Accept": "application/json;version=20230302",
}

ALLOWED_REQUEST_KINDS = frozenset({
    "geckoterminal_new_pool_discovery",
    "geckoterminal_trending_pool_reference",
    "geckoterminal_ohlcv_15m",
    "geckoterminal_pool_trades_15m",
})

_SOLANA_NETWORK_IDS = frozenset({"solana", "sol"})

# Native, reserve, and stablecoin mint addresses that are not Solana memecoins.
# GeckoTerminal sometimes lists pools where one of these is the base_token
# (e.g. a WSOL/USDC pool or a WSOL/memecoin pool inverted).  Pools whose
# base_token resolves to one of these mints must be skipped: the extracted
# token_mint would be a quote/infrastructure asset, not a memecoin candidate.
_SOLANA_NATIVE_QUOTE_MINTS = frozenset({
    "So11111111111111111111111111111111111111112",   # WSOL (Wrapped SOL / native SOL)
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC (Circle official Solana mainnet)
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
})


@dataclass(frozen=True)
class GeckoTerminalAdapterMetadata:
    source_name: str = GECKOTERMINAL_SOURCE_NAME
    display_name: str = "GeckoTerminal"
    enabled_by_default: bool = False
    requires_governor_context: bool = True
    supports_network_execution: bool = False
    fixture_transport_only: bool = True


class GeckoTerminalAdapter:
    """GeckoTerminal adapter shell, disabled unless a governed caller injects transport."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
    ) -> None:
        self.metadata = GeckoTerminalAdapterMetadata()
        self.contract = build_geckoterminal_adapter_contract()
        self.enabled = enabled
        self.transport = fixture_transport
        self.call_count = 0

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not self.enabled:
            raise PermissionError("GeckoTerminal adapter is disabled by default")
        if self.transport is None:
            raise PermissionError("GeckoTerminal adapter requires an explicit transport")
        _validate_context(context, GECKOTERMINAL_SOURCE_NAME, self.contract)

        self.call_count += 1
        try:
            payload = self.transport(context)
        except Exception as exc:
            return _failure_result(
                context.request.request_kind, "geckoterminal_transport_error", str(exc)
            )
        return normalize_geckoterminal_payload(payload, request_kind=context.request.request_kind)


def build_geckoterminal_adapter_contract() -> SourceAdapterContract:
    contract = build_source_adapter_contract(GECKOTERMINAL_SOURCE_NAME)
    if not validate_source_adapter_contract(contract):
        raise ValueError("GeckoTerminal contract violates Source Governor boundary")
    return contract


def build_geckoterminal_adapter(
    *,
    enabled: bool = False,
    fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
) -> GeckoTerminalAdapter:
    return GeckoTerminalAdapter(enabled=enabled, fixture_transport=fixture_transport)


def fixture_success_transport(
    payload: Mapping[str, Any],
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType(dict(payload))

    return transport


def fixture_failure_transport(
    message: str = "GeckoTerminal fixture failure",
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType(
            {
                "fixture_status": "failure",
                "failure_type": "geckoterminal_fixture_failure",
                "failure_message": message,
            }
        )

    return transport


def build_geckoterminal_pools_transport(
    *,
    timeout_seconds: float = GECKOTERMINAL_TIMEOUT_SECONDS,
    endpoint: str = GECKOTERMINAL_NEW_POOLS_URL,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return _load_public_json(endpoint, timeout_seconds=timeout_seconds)

    return transport


def normalize_geckoterminal_payload(
    payload: Mapping[str, Any],
    *,
    request_kind: str,
) -> NormalizedSourceResult:
    if request_kind not in ALLOWED_REQUEST_KINDS:
        return _failure_result(
            request_kind,
            "geckoterminal_request_kind_not_allowed",
            "GeckoTerminal request kind is not allowed",
        )

    fixture_status = payload.get("fixture_status")
    if fixture_status == "failure":
        return _failure_result(
            request_kind,
            str(payload.get("failure_type") or "geckoterminal_fixture_failure"),
            str(payload.get("failure_message") or "GeckoTerminal fixture failure"),
        )
    if fixture_status == "rate_limited":
        retry_at = (
            datetime.now(timezone.utc)
            + timedelta(seconds=int(payload.get("retry_after_seconds") or 120))
        ).isoformat()
        return NormalizedSourceResult(
            source_name=GECKOTERMINAL_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.STALE,
            data_quality_label=DataQualityLabel.STALE_DATA,
            failure_type="geckoterminal_rate_limited",
            failure_message="GeckoTerminal rate limit",
            retry_after_at=retry_at,
        )

    raw_pools = payload.get("data")
    if not isinstance(raw_pools, list):
        return _failure_result(
            request_kind,
            "geckoterminal_missing_data_list",
            "GeckoTerminal response missing data list",
        )

    solana_pools = []
    for pool in raw_pools:
        if not isinstance(pool, Mapping):
            continue
        flat = _normalize_geckoterminal_pool(pool)
        if flat:
            solana_pools.append(flat)

    if not solana_pools:
        return _failure_result(
            request_kind,
            "geckoterminal_no_valid_solana_pools",
            "GeckoTerminal response contained no valid Solana pools",
        )

    stale = bool(payload.get("fixture_stale"))
    return NormalizedSourceResult(
        source_name=GECKOTERMINAL_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.STALE if stale else SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.STALE_DATA if stale else DataQualityLabel.CLEAN_DATA,
        normalized_payload=MappingProxyType(
            {
                "source_name": GECKOTERMINAL_SOURCE_NAME,
                "request_kind": request_kind,
                "pairs": solana_pools,
            }
        ),
        status_code=int(payload.get("_source_status_code") or 200),
    )


def _normalize_geckoterminal_pool(pool: Mapping[str, Any]) -> dict[str, Any] | None:
    """Flatten one GeckoTerminal pool item into a discovery-pipeline-compatible dict."""
    attrs = pool.get("attributes") if isinstance(pool.get("attributes"), Mapping) else pool
    rels = pool.get("relationships") or {}

    pool_address = (
        attrs.get("address") or attrs.get("pair_address") or attrs.get("pairAddress")
    )
    if not pool_address:
        return None

    chain_val = attrs.get("chain") or attrs.get("chainId")
    if not chain_val:
        network_rel = rels.get("network") or {}
        network_data = (network_rel.get("data") or {}) if isinstance(network_rel, Mapping) else {}
        chain_val = network_data.get("id") if isinstance(network_data, Mapping) else None
    if not chain_val:
        # GeckoTerminal network-scoped endpoints (e.g. /networks/solana/new_pools) omit the
        # network relationship because the chain is already implied by the URL.  The pool id
        # field always carries the network prefix: "<network>_<pool_address>".
        pool_id = pool.get("id")
        if isinstance(pool_id, str) and "_" in pool_id:
            chain_val = pool_id.split("_")[0]
    if str(chain_val or "").lower() not in _SOLANA_NETWORK_IDS:
        return None

    base_mint = (
        attrs.get("base_token_address")
        or attrs.get("baseTokenAddress")
        or attrs.get("token_mint")
    )
    if not base_mint:
        base_rel = rels.get("base_token") or {}
        base_data = (base_rel.get("data") or {}) if isinstance(base_rel, Mapping) else {}
        raw_id = base_data.get("id") if isinstance(base_data, Mapping) else None
        if raw_id:
            base_mint = _strip_network_prefix(str(raw_id), "solana")
    if not base_mint:
        return None
    if base_mint in _SOLANA_NATIVE_QUOTE_MINTS:
        # base_token is a native/reserve/stablecoin asset, not a memecoin.
        # Skip this pool rather than recording a quote asset as a discovery target.
        return None

    price = (
        attrs.get("base_token_price_usd")
        or attrs.get("price_usd")
        or attrs.get("priceUsd")
    )
    liquidity = attrs.get("reserve_in_usd") or attrs.get("liquidity_usd")
    fdv = attrs.get("fdv_usd") or attrs.get("fdv")
    market_cap = attrs.get("market_cap_usd") or attrs.get("marketCap")
    captured_at = attrs.get("captured_at") or attrs.get("pool_created_at")

    volume_usd = attrs.get("volume_usd") or {}
    vol_m5 = _get_volume(attrs, volume_usd, "volume_5m", "m5")
    vol_h1 = _get_volume(attrs, volume_usd, "volume_1h", "h1")
    vol_h24 = _get_volume(attrs, volume_usd, "volume_24h", "h24")

    txns_dict = attrs.get("transactions") or {}
    txns_m5 = _get_txn_count(attrs, txns_dict, "txns_5m", "m5")
    txns_h1 = _get_txn_count(attrs, txns_dict, "txns_1h", "h1")
    txns_h24 = _get_txn_count(attrs, txns_dict, "txns_24h", "h24")

    # Price change percentages — GeckoTerminal stores these under price_change_percentage
    _pc = attrs.get("price_change_percentage") if isinstance(attrs.get("price_change_percentage"), Mapping) else {}
    price_change_5m = _to_float(_pc.get("m5"))
    price_change_1h = _to_float(_pc.get("h1"))
    price_change_24h = _to_float(_pc.get("h24"))

    return {
        "chainId": "solana",
        "pairAddress": pool_address,
        "baseToken": {"address": base_mint},
        "name": attrs.get("name"),
        "symbol": attrs.get("symbol"),
        "dex": attrs.get("dex"),
        "pool_source": GECKOTERMINAL_SOURCE_NAME,
        "priceUsd": str(price) if price is not None else None,
        "liquidity": {"usd": _to_float(liquidity)},
        "volume": {
            "m5": _to_float(vol_m5),
            "h1": _to_float(vol_h1),
            "h24": _to_float(vol_h24),
        },
        # Use integer totals (not buy/sell dicts) so the discovery parser's nested_int handles them
        "txns": {
            "m5": txns_m5,
            "h1": txns_h1,
            "h24": txns_h24,
        },
        "fdv": _to_float(fdv),
        "marketCap": _to_float(market_cap),
        "captured_at": captured_at,
        # V2-2H.3: pair creation timestamp and price-change fields (100% missing in live audit)
        "pair_created_at": attrs.get("pool_created_at"),
        "price_change_5m": price_change_5m,
        "price_change_1h": price_change_1h,
        "price_change_24h": price_change_24h,
    }


def _get_volume(
    attrs: Mapping[str, Any],
    volume_usd: Any,
    flat_key: str,
    nested_key: str,
) -> Any:
    flat = attrs.get(flat_key)
    if flat is not None:
        return flat
    if isinstance(volume_usd, Mapping):
        return volume_usd.get(nested_key)
    return None


def _get_txn_count(
    attrs: Mapping[str, Any],
    txns_dict: Any,
    flat_key: str,
    nested_key: str,
) -> int | None:
    flat = attrs.get(flat_key)
    if flat is not None:
        try:
            return int(float(flat))
        except (TypeError, ValueError):
            return None
    if not isinstance(txns_dict, Mapping):
        return None
    bucket = txns_dict.get(nested_key)
    if bucket is None:
        return None
    if isinstance(bucket, (int, float)):
        return int(bucket)
    if isinstance(bucket, Mapping):
        return int((bucket.get("buys") or 0) + (bucket.get("sells") or 0))
    return None


def _strip_network_prefix(gt_id: str, network: str) -> str:
    prefix = f"{network}_"
    return gt_id[len(prefix):] if gt_id.startswith(prefix) else gt_id


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
        source_name=GECKOTERMINAL_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.FAILED,
        data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        failure_type=failure_type,
        failure_message=failure_message,
    )


def _load_public_json(endpoint: str, *, timeout_seconds: float) -> Mapping[str, Any]:
    req = url_request.Request(
        endpoint,
        headers=GECKOTERMINAL_PUBLIC_API_HEADERS,
        method="GET",
    )
    try:
        with url_request.urlopen(req, timeout=timeout_seconds) as response:
            raw_body = response.read(512_000)
            payload = json.loads(raw_body.decode("utf-8"))
            if isinstance(payload, dict):
                payload["_source_status_code"] = getattr(response, "status", None)
                return MappingProxyType(payload)
            return MappingProxyType(
                {
                    "fixture_status": "failure",
                    "failure_type": "geckoterminal_non_object_payload",
                    "failure_message": "GeckoTerminal returned non-object payload",
                }
            )
    except url_error.HTTPError as exc:
        if exc.code == 429:
            return MappingProxyType({"fixture_status": "rate_limited", "retry_after_seconds": 120})
        return MappingProxyType(
            {
                "fixture_status": "failure",
                "failure_type": "geckoterminal_http_error",
                "failure_message": f"GeckoTerminal HTTP error {exc.code}",
            }
        )
    except (OSError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return MappingProxyType(
            {
                "fixture_status": "failure",
                "failure_type": "geckoterminal_transport_failure",
                "failure_message": str(exc),
            }
        )

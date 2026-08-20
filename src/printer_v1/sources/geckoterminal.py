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
from printer_v1.sources.geckoterminal_15m import (
    GECKOTERMINAL_PUBLIC_API_HEADERS,
    GECKOTERMINAL_OHLCV_REQUEST_KIND,
    GECKOTERMINAL_POOL_TRADES_REQUEST_KIND,
    build_gt15m_ohlcv_url,
    build_gt15m_trades_url,
    redact_geckoterminal_trades_tx_from_addresses,
)
from printer_v1.sources.operational_source_contracts import (
    GECKOTERMINAL_EXACT_PAIR_URL,
    GECKOTERMINAL_TOKEN_POOLS_URL,
)


GECKOTERMINAL_SOURCE_NAME = "geckoterminal"
GECKOTERMINAL_NEW_POOLS_URL = (
    "https://api.geckoterminal.com/api/v2/networks/solana/new_pools?page=1"
)
GECKOTERMINAL_TRENDING_POOLS_URL = (
    "https://api.geckoterminal.com/api/v2/networks/solana/trending_pools?page=1"
)
GECKOTERMINAL_TIMEOUT_SECONDS = 8.0

# V2-9.5 exact-pair snapshot fallback: a single Solana pool lookup. Same request
# kind as DexScreener's primary snapshot; source_name distinguishes the provider.
GECKOTERMINAL_PAIR_SNAPSHOT_REQUEST_KIND = "pair_market_snapshot"
GECKOTERMINAL_READINESS_BASE_REQUEST_KIND = "geckoterminal_readiness_base_snapshot"
GECKOTERMINAL_POOL_URL_TEMPLATE = GECKOTERMINAL_EXACT_PAIR_URL
GECKOTERMINAL_TOKEN_POOLS_URL_TEMPLATE = GECKOTERMINAL_TOKEN_POOLS_URL

ALLOWED_REQUEST_KINDS = frozenset({
    "candidate_nomination",
    "candidate_market_batch",
    "geckoterminal_new_pool_discovery",
    "geckoterminal_trending_pool_reference",
    "geckoterminal_ohlcv_15m",
    "geckoterminal_pool_trades_15m",
    GECKOTERMINAL_PAIR_SNAPSHOT_REQUEST_KIND,
    GECKOTERMINAL_READINESS_BASE_REQUEST_KIND,
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
        return normalize_geckoterminal_payload(
            payload,
            request_kind=context.request.request_kind,
            expected_pool_address=context.request.payload.get("pool_address"),
            expected_token_mint=context.request.payload.get("token_mint"),
        )


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
        payload = dict(_load_public_json(endpoint, timeout_seconds=timeout_seconds))
        return _attach_measured_geckoterminal_transport(
            payload,
            request_kind="geckoterminal_new_pool_discovery",
            endpoint="GET /api/v2/networks/solana/new_pools",
            target_category="fresh_solana_pools",
        )

    return transport


def build_geckoterminal_token_pools_transport(
    token_mint: str,
    *,
    timeout_seconds: float = GECKOTERMINAL_TIMEOUT_SECONDS,
    endpoint_template: str = GECKOTERMINAL_TOKEN_POOLS_URL_TEMPLATE,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """Build one keyless, exact-mint GeckoTerminal pool-resolution attempt."""
    mint = str(token_mint or "").strip()
    if not mint:
        raise ValueError("GeckoTerminal token pools requires token_mint")
    endpoint = endpoint_template.format(token_mint=mint)

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        requested = str(context.request.payload.get("token_mint") or "").strip()
        if requested != mint:
            raise ValueError("GECKOTERMINAL_TOKEN_POOL_TARGET_MISMATCH")
        payload = dict(_load_public_json(endpoint, timeout_seconds=timeout_seconds))
        payload["_requested_token_mint"] = mint
        payload["_requested_network"] = "solana"
        payload["_requested_endpoint"] = endpoint
        return _attach_measured_geckoterminal_transport(
            payload,
            request_kind="candidate_market_batch",
            endpoint="GET /api/v2/networks/solana/tokens/{mint}/pools",
            target_category="mint_pool_reconciliation",
            target_identity=mint,
        )

    return transport


def build_geckoterminal_15m_transport(
    *,
    request_kind: str,
    pool_address: str,
    timeout_seconds: float = GECKOTERMINAL_TIMEOUT_SECONDS,
) -> tuple[str, Callable[[SourceAdapterContext], Mapping[str, Any]]]:
    """Build one pool-bound live transport for a governed 15m request."""
    pool_address = str(pool_address or "").strip()
    if not pool_address:
        raise ValueError("GeckoTerminal 15m request requires pool_address")
    if request_kind == GECKOTERMINAL_OHLCV_REQUEST_KIND:
        endpoint = build_gt15m_ohlcv_url(pool_address)
    elif request_kind == GECKOTERMINAL_POOL_TRADES_REQUEST_KIND:
        endpoint = build_gt15m_trades_url(pool_address)
    else:
        raise ValueError("Unsupported GeckoTerminal 15m request kind")

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        requested_pool = str(context.request.payload.get("pool_address") or "").strip()
        if requested_pool != pool_address:
            raise ValueError("GeckoTerminal 15m transport pool mismatch")
        payload = dict(_load_public_json(endpoint, timeout_seconds=timeout_seconds))
        payload["_requested_pool_address"] = pool_address
        payload["_requested_network"] = "solana"
        payload["_requested_endpoint"] = endpoint
        return MappingProxyType(payload)

    return endpoint, transport


def build_geckoterminal_pair_snapshot_transport(
    pool_address: str,
    token_mint: str,
    *,
    timeout_seconds: float = GECKOTERMINAL_TIMEOUT_SECONDS,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """Build one live transport for a single Solana pool exact-pair snapshot.

    Uses the free/public GeckoTerminal single-pool endpoint. Embeds the
    requested pool/mint/network so normalization can enforce exact-pair
    identity. No paid tier, no authentication.
    """
    pool_address = str(pool_address or "").strip()
    token_mint = str(token_mint or "").strip()
    if not pool_address or not token_mint:
        raise ValueError("GeckoTerminal pair snapshot requires pool_address and token_mint")
    endpoint = GECKOTERMINAL_POOL_URL_TEMPLATE.format(pool_address=pool_address)

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        requested_pool = str(context.request.payload.get("pool_address") or "").strip()
        if requested_pool != pool_address:
            raise ValueError("GeckoTerminal pair snapshot transport pool mismatch")
        payload = dict(_load_public_json(endpoint, timeout_seconds=timeout_seconds))
        payload["_requested_pool_address"] = pool_address
        payload["_requested_token_mint"] = token_mint
        payload["_requested_network"] = "solana"
        payload["_requested_endpoint"] = endpoint
        return MappingProxyType(payload)

    return transport


def normalize_geckoterminal_payload(
    payload: Mapping[str, Any],
    *,
    request_kind: str,
    expected_pool_address: Any = None,
    expected_token_mint: Any = None,
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

    if request_kind in {
        GECKOTERMINAL_PAIR_SNAPSHOT_REQUEST_KIND,
        GECKOTERMINAL_READINESS_BASE_REQUEST_KIND,
    }:
        return _normalize_geckoterminal_pair_snapshot(
            payload,
            request_kind=request_kind,
            expected_pool_address=expected_pool_address,
            expected_token_mint=expected_token_mint,
        )

    if request_kind in {
        GECKOTERMINAL_OHLCV_REQUEST_KIND,
        GECKOTERMINAL_POOL_TRADES_REQUEST_KIND,
    }:
        return _normalize_geckoterminal_15m_payload(
            payload,
            request_kind=request_kind,
            expected_pool_address=expected_pool_address,
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

    if not solana_pools and request_kind == "candidate_market_batch":
        return NormalizedSourceResult(
            source_name=GECKOTERMINAL_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.CLEAN_DATA,
            normalized_payload=MappingProxyType(
                {
                    **_measured_geckoterminal_metadata(payload),
                    "source_name": GECKOTERMINAL_SOURCE_NAME,
                    "request_kind": request_kind,
                    "pairs": [],
                    "no_matching_pools": True,
                    "requested_token_mint": payload.get("_requested_token_mint"),
                }
            ),
            status_code=int(payload.get("_source_status_code") or 200),
        )
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
                **_measured_geckoterminal_metadata(payload),
                "source_name": GECKOTERMINAL_SOURCE_NAME,
                "request_kind": request_kind,
                "pairs": solana_pools,
            }
        ),
        status_code=int(payload.get("_source_status_code") or 200),
    )


def _normalize_geckoterminal_15m_payload(
    payload: Mapping[str, Any],
    *,
    request_kind: str,
    expected_pool_address: Any,
) -> NormalizedSourceResult:
    expected = str(expected_pool_address or "").strip()
    observed = str(payload.get("_requested_pool_address") or "").strip()
    network = str(payload.get("_requested_network") or "solana").lower()
    endpoint = str(payload.get("_requested_endpoint") or "")
    if not expected or observed != expected or network != "solana":
        return _failure_result(
            request_kind,
            "geckoterminal_15m_pool_mismatch",
            "GeckoTerminal 15m response did not match the requested Solana pool",
        )
    if payload.get("fixture_stale"):
        return NormalizedSourceResult(
            source_name=GECKOTERMINAL_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.STALE,
            data_quality_label=DataQualityLabel.STALE_DATA,
            normalized_payload=MappingProxyType({}),
            status_code=int(payload.get("_source_status_code") or 200),
        )

    raw_data = payload.get("data")
    if request_kind == GECKOTERMINAL_OHLCV_REQUEST_KIND:
        attrs = raw_data.get("attributes") if isinstance(raw_data, Mapping) else None
        if not isinstance(attrs, Mapping) or not isinstance(attrs.get("ohlcv_list"), list):
            return _failure_result(
                request_kind,
                "geckoterminal_15m_missing_ohlcv",
                "GeckoTerminal 15m response missing OHLCV list",
            )
    elif not isinstance(raw_data, list):
        return _failure_result(
            request_kind,
            "geckoterminal_15m_missing_trades",
            "GeckoTerminal 15m response missing trades list",
        )

    provider_payload = {
        key: value for key, value in payload.items() if not str(key).startswith("_requested_")
    }
    if request_kind == GECKOTERMINAL_POOL_TRADES_REQUEST_KIND:
        # Derive-capable callers must enrich from the pre-redaction transport
        # payload. Durable normalized_payload_json must never retain
        # tx_from_address values.
        provider_payload = redact_geckoterminal_trades_tx_from_addresses(
            provider_payload
        )
    return NormalizedSourceResult(
        source_name=GECKOTERMINAL_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.CLEAN_DATA,
        normalized_payload=MappingProxyType(
            {
                "source_name": GECKOTERMINAL_SOURCE_NAME,
                "request_kind": request_kind,
                "network": network,
                "pool_address": observed,
                "endpoint": endpoint,
                "provider_payload": provider_payload,
            }
        ),
        status_code=int(payload.get("_source_status_code") or 200),
    )


def _txn_bucket_total(bucket: Any) -> int | None:
    if isinstance(bucket, (int, float)):
        return int(bucket)
    if isinstance(bucket, Mapping):
        buys = bucket.get("buys")
        sells = bucket.get("sells")
        if buys is None and sells is None:
            return None
        return int((buys or 0) + (sells or 0))
    return None


def _txn_bucket_side(bucket: Any, side: str) -> int | None:
    if isinstance(bucket, Mapping):
        value = bucket.get(side)
        return int(value) if value is not None else None
    return None


def _normalize_geckoterminal_pair_snapshot(
    payload: Mapping[str, Any],
    *,
    request_kind: str = GECKOTERMINAL_PAIR_SNAPSHOT_REQUEST_KIND,
    expected_pool_address: Any,
    expected_token_mint: Any,
) -> NormalizedSourceResult:
    """Normalize one Solana single-pool response into an exact-pair snapshot.

    Enforces exact-pair identity (network=solana, pool address, base token mint)
    and requires every mandatory market field. Any mismatch, missing mandatory
    field, staleness, or malformed body fails closed with MISSING_CRITICAL_DATA
    so the V2-9.5 fallback never persists partial or wrong-pair evidence.
    """
    kind = request_kind
    expected_pool = str(expected_pool_address or "").strip()
    expected_mint = str(expected_token_mint or "").strip()
    if not expected_pool or not expected_mint:
        return _failure_result(
            kind,
            "geckoterminal_pair_snapshot_missing_expected_identity",
            "GeckoTerminal pair snapshot requires expected pool_address and token_mint",
        )

    network = str(payload.get("_requested_network") or "solana").lower()
    observed_pool = str(payload.get("_requested_pool_address") or "").strip()
    if network != "solana" or observed_pool != expected_pool:
        return _failure_result(
            kind,
            "geckoterminal_pair_snapshot_pool_mismatch",
            "GeckoTerminal pair snapshot did not match the requested Solana pool",
        )
    if payload.get("fixture_stale"):
        return _failure_result(
            kind,
            "geckoterminal_pair_snapshot_stale",
            "GeckoTerminal pair snapshot response is stale",
        )

    data = payload.get("data")
    if not isinstance(data, Mapping):
        return _failure_result(
            kind,
            "geckoterminal_pair_snapshot_missing_data",
            "GeckoTerminal pair snapshot response missing pool object",
        )
    resource_id = str(data.get("id") or "").strip()
    if resource_id != f"solana_{expected_pool}":
        return _failure_result(
            kind,
            "geckoterminal_pair_snapshot_resource_mismatch",
            "GeckoTerminal pool resource id did not match the requested Solana pool",
        )

    flat = _normalize_geckoterminal_pool(data)
    if not flat:
        return _failure_result(
            kind,
            "geckoterminal_pair_snapshot_unparseable_pool",
            "GeckoTerminal pair snapshot pool object could not be parsed",
        )

    observed_pair_address = str(flat.get("pairAddress") or "").strip()
    base = flat.get("baseToken") if isinstance(flat.get("baseToken"), Mapping) else {}
    observed_mint = str(base.get("address") or "").strip()
    if flat.get("chainId") != "solana":
        return _failure_result(
            kind,
            "geckoterminal_pair_snapshot_non_solana",
            "GeckoTerminal pair snapshot pool is not a Solana pool",
        )
    if observed_pair_address != expected_pool or observed_mint != expected_mint:
        return _failure_result(
            kind,
            "geckoterminal_pair_snapshot_identity_mismatch",
            "GeckoTerminal pair snapshot pool/token identity did not match the request",
        )

    attrs = data.get("attributes") if isinstance(data.get("attributes"), Mapping) else data
    txns = attrs.get("transactions") if isinstance(attrs.get("transactions"), Mapping) else {}
    volume_usd = attrs.get("volume_usd") if isinstance(attrs.get("volume_usd"), Mapping) else {}

    price_usd = _to_float(flat.get("priceUsd"))
    liquidity = flat.get("liquidity") if isinstance(flat.get("liquidity"), Mapping) else {}
    liquidity_usd = _to_float(liquidity.get("usd"))
    fdv = _to_float(flat.get("fdv"))
    market_cap = _to_float(flat.get("marketCap"))
    volume_24h = _to_float(_get_volume(attrs, volume_usd, "volume_24h", "h24"))
    txns_24h = _txn_bucket_total(txns.get("h24"))
    pair_created_at = flat.get("pair_created_at") or attrs.get("pool_created_at")

    reserve = _to_float(attrs.get("reserve_in_usd"))
    base_component = _to_float(attrs.get("base_token_liquidity_usd"))
    quote_component = _to_float(attrs.get("quote_token_liquidity_usd"))
    if reserve is not None and base_component is not None and quote_component is not None:
        component_total = base_component + quote_component
        tolerance = max(0.01, abs(reserve) * 0.000001)
        if abs(component_total - reserve) > tolerance:
            return _failure_result(
                kind,
                "geckoterminal_pair_snapshot_liquidity_conflict",
                "GeckoTerminal reserve_in_usd conflicts with pool composition",
            )

    # Mandatory exact-pair contract fields. Missing any one fails closed —
    # required fields are never weakened and never combined across providers.
    missing: list[str] = []
    if price_usd is None:
        missing.append("price_usd")
    if liquidity_usd is None:
        missing.append("liquidity_usd")
    if kind == GECKOTERMINAL_PAIR_SNAPSHOT_REQUEST_KIND and fdv is None and market_cap is None:
        missing.append("fdv_or_market_cap")
    if volume_24h is None:
        missing.append("volume_24h")
    if txns_24h is None:
        missing.append("txns_24h")
    if kind == GECKOTERMINAL_PAIR_SNAPSHOT_REQUEST_KIND and not pair_created_at:
        missing.append("pair_created_at")
    if missing:
        return _failure_result(
            kind,
            "geckoterminal_pair_snapshot_missing_mandatory_fields",
            f"GeckoTerminal pair snapshot missing mandatory fields: {sorted(missing)}",
        )

    volume_dict = flat.get("volume") if isinstance(flat.get("volume"), Mapping) else {}
    snapshot_pair = {
        "chain": "solana",
        "pair_address": observed_pair_address,
        "token_mint": observed_mint,
        "symbol": flat.get("symbol"),
        "name": flat.get("name"),
        "price_usd": price_usd,
        "liquidity_usd": liquidity_usd,
        "volume_5m": _to_float(volume_dict.get("m5")),
        "volume_1h": _to_float(volume_dict.get("h1")),
        "volume_24h": volume_24h,
        "txns_5m": _txn_bucket_total(txns.get("m5")),
        "txns_1h": _txn_bucket_total(txns.get("h1")),
        "txns_24h": txns_24h,
        "buys_5m": _txn_bucket_side(txns.get("m5"), "buys"),
        "sells_5m": _txn_bucket_side(txns.get("m5"), "sells"),
        "buys_1h": _txn_bucket_side(txns.get("h1"), "buys"),
        "sells_1h": _txn_bucket_side(txns.get("h1"), "sells"),
        "buys_24h": _txn_bucket_side(txns.get("h24"), "buys"),
        "sells_24h": _txn_bucket_side(txns.get("h24"), "sells"),
        "fdv": fdv,
        "market_cap": market_cap,
        "price_change_5m": flat.get("price_change_5m"),
        "price_change_1h": flat.get("price_change_1h"),
        "price_change_24h": flat.get("price_change_24h"),
        "pair_created_at": pair_created_at,
        "liquidity_provenance": {
            "source": GECKOTERMINAL_SOURCE_NAME,
            "raw_field": "reserve_in_usd",
            "network": "solana",
            "pool_address": observed_pair_address,
            "token_mint": observed_mint,
            "endpoint": str(payload.get("_requested_endpoint") or ""),
            "composition_checked": base_component is not None and quote_component is not None,
        },
    }
    return NormalizedSourceResult(
        source_name=GECKOTERMINAL_SOURCE_NAME,
        request_kind=kind,
        source_status=SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.CLEAN_DATA,
        normalized_payload=MappingProxyType(
            {
                "source_name": GECKOTERMINAL_SOURCE_NAME,
                "request_kind": kind,
                "pairs": [snapshot_pair],
                "exact_pair_fallback": kind == GECKOTERMINAL_PAIR_SNAPSHOT_REQUEST_KIND,
                "readiness_base": kind == GECKOTERMINAL_READINESS_BASE_REQUEST_KIND,
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

    quote_mint = (
        attrs.get("quote_token_address")
        or attrs.get("quoteTokenAddress")
        or attrs.get("quote_mint")
    )
    if not quote_mint:
        quote_rel = rels.get("quote_token") or {}
        quote_data = (quote_rel.get("data") or {}) if isinstance(quote_rel, Mapping) else {}
        raw_quote_id = quote_data.get("id") if isinstance(quote_data, Mapping) else None
        if raw_quote_id:
            quote_mint = _strip_network_prefix(str(raw_quote_id), "solana")
    dex_id = attrs.get("dex") or attrs.get("dex_id")
    if not dex_id:
        dex_rel = rels.get("dex") or {}
        dex_data = (dex_rel.get("data") or {}) if isinstance(dex_rel, Mapping) else {}
        dex_id = dex_data.get("id") if isinstance(dex_data, Mapping) else None

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
        "quoteToken": {"address": quote_mint} if quote_mint else {},
        "base_mint": base_mint,
        "quote_mint": quote_mint,
        "dex_id": dex_id,
        "name": attrs.get("name"),
        "symbol": attrs.get("symbol"),
        "dex": dex_id,
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
            raw_body = response.read(512_001)
            if len(raw_body) > 512_000:
                return MappingProxyType(
                    {
                        "fixture_status": "failure",
                        "failure_type": "geckoterminal_response_byte_ceiling",
                        "failure_message": "GeckoTerminal response exceeded 512000 bytes",
                        "_source_response_bytes": len(raw_body),
                    }
                )
            payload = json.loads(raw_body.decode("utf-8"))
            if isinstance(payload, dict):
                payload["_source_status_code"] = getattr(response, "status", None)
                payload["_source_response_bytes"] = len(raw_body)
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


def _measured_geckoterminal_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    from printer_v1.sources.measured_transport import merge_transport_payload_metadata

    return merge_transport_payload_metadata(payload)


def _attach_measured_geckoterminal_transport(
    payload: Mapping[str, Any],
    *,
    request_kind: str,
    endpoint: str,
    target_category: str,
    target_identity: str | None = None,
) -> Mapping[str, Any]:
    """Attach one exact identity to an actual keyless GeckoTerminal GET."""
    from printer_v1.sources.measured_transport import (
        build_transport_identity,
        measured_payload_fields,
    )

    rows = payload.get("data")
    row_count = len(rows) if isinstance(rows, list) else 0
    identity = build_transport_identity(
        stage=(
            "FRESH_POOL_NOMINATION"
            if request_kind == "geckoterminal_new_pool_discovery"
            else "MINT_MARKET_BATCH"
        ),
        source_name="geckoterminal",
        endpoint_owner="geckoterminal",
        governed_request_kind=request_kind,
        method_or_endpoint=endpoint,
        within_request_ordinal=1,
        target_category=target_category,
        target_identity=target_identity,
        response_bytes=int(payload.get("_source_response_bytes") or 0),
        normalized_rows=row_count,
        result="FAILED" if payload.get("fixture_status") else "OK",
    )
    return MappingProxyType({**dict(payload), **measured_payload_fields([identity])})

"""Governed PumpSwap read-only pool confirmation adapter.

PumpSwap is the post-migration AMM for graduated Pump.fun tokens.
This adapter is read-only confirmation and provenance metadata only.

Supported request kinds (read-only confirmation):
  - pumpswap_pool_confirmation
  - pumpswap_migration_pool_reference
  - pumpswap_liquidity_reference

This adapter must never be used for:
  - live execution
  - instruction building
  - transaction signing
  - buy or sell operations
  - route calculation for execution
  - any form of fund movement

Adapter is fixture-transport-only. No persistent loop is started here.
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


PUMPSWAP_SOURCE_NAME = "pumpswap"

ALLOWED_REQUEST_KINDS = frozenset({
    "pumpswap_pool_confirmation",
    "pumpswap_migration_pool_reference",
    "pumpswap_liquidity_reference",
})

_SOLANA_CHAIN = "solana"


@dataclass(frozen=True)
class PumpSwapAdapterMetadata:
    source_name: str = PUMPSWAP_SOURCE_NAME
    display_name: str = "PumpSwap"
    enabled_by_default: bool = False
    requires_governor_context: bool = True
    supports_network_execution: bool = False
    fixture_transport_only: bool = True
    read_only: bool = True


class PumpSwapAdapter:
    """PumpSwap adapter shell — read-only confirmation, disabled unless transport injected.

    Only pool confirmation, migration pool reference, and liquidity reference
    request kinds are accepted. No execution, instruction, or fund-movement
    operations are present or possible through this adapter.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
    ) -> None:
        self.metadata = PumpSwapAdapterMetadata()
        self.contract = build_pumpswap_adapter_contract()
        self.enabled = enabled
        self.transport = fixture_transport
        self.call_count = 0

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not self.enabled:
            raise PermissionError("PumpSwap adapter is disabled by default")
        if self.transport is None:
            raise PermissionError("PumpSwap adapter requires an explicit transport")
        _validate_context(context, PUMPSWAP_SOURCE_NAME, self.contract)

        self.call_count += 1
        try:
            payload = self.transport(context)
        except Exception as exc:
            return _failure_result(
                context.request.request_kind, "pumpswap_transport_error", str(exc)
            )
        return normalize_pumpswap_payload(payload, request_kind=context.request.request_kind)


def build_pumpswap_adapter_contract() -> SourceAdapterContract:
    contract = build_source_adapter_contract(PUMPSWAP_SOURCE_NAME)
    if not validate_source_adapter_contract(contract):
        raise ValueError("PumpSwap contract violates Source Governor boundary")
    return contract


def build_pumpswap_adapter(
    *,
    enabled: bool = False,
    fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
) -> PumpSwapAdapter:
    return PumpSwapAdapter(enabled=enabled, fixture_transport=fixture_transport)


def fixture_success_transport(
    payload: Mapping[str, Any],
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType(dict(payload))

    return transport


def fixture_failure_transport(
    message: str = "PumpSwap fixture failure",
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType(
            {
                "fixture_status": "failure",
                "failure_type": "pumpswap_fixture_failure",
                "failure_message": message,
            }
        )

    return transport


def normalize_pumpswap_payload(
    payload: Mapping[str, Any],
    *,
    request_kind: str,
) -> NormalizedSourceResult:
    if request_kind not in ALLOWED_REQUEST_KINDS:
        return _failure_result(
            request_kind,
            "pumpswap_request_kind_not_allowed",
            "PumpSwap request kind is not allowed",
        )

    fixture_status = payload.get("fixture_status")
    if fixture_status == "failure":
        return _failure_result(
            request_kind,
            str(payload.get("failure_type") or "pumpswap_fixture_failure"),
            str(payload.get("failure_message") or "PumpSwap fixture failure"),
        )
    if fixture_status == "stale":
        return NormalizedSourceResult(
            source_name=PUMPSWAP_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.STALE,
            data_quality_label=DataQualityLabel.STALE_DATA,
            failure_type="pumpswap_stale_data",
            failure_message="PumpSwap fixture stale data",
        )

    # Accept pre-normalized "tokens" list or raw "pools" list
    pre_normalized = payload.get("tokens")
    if isinstance(pre_normalized, list):
        solana_pools = [
            p for p in pre_normalized
            if isinstance(p, Mapping) and str(p.get("chain") or "").lower() == _SOLANA_CHAIN
        ]
    else:
        raw_pools = payload.get("pools") or payload.get("pool_list") or []
        if not isinstance(raw_pools, list):
            return _failure_result(
                request_kind,
                "pumpswap_missing_pool_list",
                "PumpSwap payload missing tokens or pools list",
            )
        solana_pools = []
        for pool in raw_pools:
            if not isinstance(pool, Mapping):
                continue
            normalized = _normalize_pumpswap_pool(pool)
            if normalized:
                solana_pools.append(normalized)

    if not solana_pools:
        return _failure_result(
            request_kind,
            "pumpswap_no_valid_solana_pools",
            "PumpSwap payload contained no valid Solana pool entries",
        )

    stale = bool(payload.get("fixture_stale"))
    return NormalizedSourceResult(
        source_name=PUMPSWAP_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.STALE if stale else SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.STALE_DATA if stale else DataQualityLabel.CLEAN_DATA,
        normalized_payload=MappingProxyType(
            {
                "source_name": PUMPSWAP_SOURCE_NAME,
                "request_kind": request_kind,
                "tokens": solana_pools,
            }
        ),
        status_code=200,
    )


def _normalize_pumpswap_pool(pool: Mapping[str, Any]) -> dict[str, Any] | None:
    """Normalize one PumpSwap pool entry into the discovery pipeline format.

    Read-only confirmation only. No execution fields are extracted or returned.
    """
    token_mint = (
        pool.get("base_mint")
        or pool.get("baseMint")
        or pool.get("mint")
        or pool.get("token_mint")
    )
    if not token_mint:
        return None

    pool_address = (
        pool.get("pool_address")
        or pool.get("poolAddress")
        or pool.get("pool_id")
        or pool.get("address")
    )
    if not pool_address:
        return None

    chain = str(pool.get("chain") or pool.get("network") or "").lower()
    if chain and chain not in {_SOLANA_CHAIN, "sol"}:
        return None

    liquidity_usd = _to_float(
        pool.get("liquidity_usd")
        or pool.get("liquidityUsd")
        or pool.get("tvl_usd")
        or pool.get("tvlUsd")
    )
    price_usd = _to_float(
        pool.get("price_usd")
        or pool.get("priceUsd")
        or pool.get("base_price_usd")
    )
    volume_1h = _to_float(pool.get("volume_1h") or pool.get("volume_usd_1h"))
    volume_24h = _to_float(pool.get("volume_24h") or pool.get("volume_usd_24h"))
    txns_1h = _to_int(pool.get("txns_1h") or pool.get("tx_count_1h"))
    txns_24h = _to_int(pool.get("txns_24h") or pool.get("tx_count_24h"))

    return {
        "chain": _SOLANA_CHAIN,
        "mint": token_mint,
        "pairAddress": pool_address,
        "symbol": pool.get("symbol") or pool.get("base_symbol"),
        "name": pool.get("name") or pool.get("base_name"),
        "dex": "pumpswap",
        "poolSource": PUMPSWAP_SOURCE_NAME,
        "price_usd": str(price_usd) if price_usd is not None else None,
        "liquidity_usd": liquidity_usd,
        "volume_1h": volume_1h,
        "volume_24h": volume_24h,
        "txns_1h": txns_1h,
        "txns_24h": txns_24h,
        "captured_at": pool.get("captured_at") or _current_iso(),
    }


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    f = _to_float(value)
    return int(f) if f is not None else None


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
        source_name=PUMPSWAP_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.FAILED,
        data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        failure_type=failure_type,
        failure_message=failure_message,
    )

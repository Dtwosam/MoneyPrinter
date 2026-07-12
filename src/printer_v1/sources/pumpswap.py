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

import base64
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


PUMPSWAP_SOURCE_NAME = "pumpswap"

ALLOWED_REQUEST_KINDS = frozenset({
    "pumpswap_pool_confirmation",
    "pumpswap_migration_pool_reference",
    "pumpswap_liquidity_reference",
    # Governed on-chain read-only confirmation (Solana RPC getAccountInfo):
    # confirms a pool account is owned by the PumpSwap AMM program and that the
    # expected mint is the pool's base_mint. Read-only. Never executes.
    "pumpswap_onchain_pool_confirmation",
})

_SOLANA_CHAIN = "solana"

# Official PumpSwap AMM on-chain program (Solana mainnet). Verified 2026-07-12:
#   - on-chain: getAccountInfo(program) -> executable=True, owner=BPFLoaderUpgradeab1e
#   - corroborated by pump-fun pump-swap SDK and Bitquery PumpSwap API docs (A7).
# A pool account whose getAccountInfo owner == this program is a PumpSwap pool.
PUMPSWAP_AMM_PROGRAM_ID = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"

# PumpSwap Pool account layout offset of base_mint (verified live against two
# distinct real pools, both mint bytes present at offset 43):
#   8 (anchor discriminator) + 1 (pool_bump u8) + 2 (index u16) + 32 (creator)
# = 43. base_mint occupies bytes [43, 75); quote_mint bytes [75, 107).
_PUMPSWAP_POOL_BASE_MINT_OFFSET = 43
_PUMPSWAP_POOL_QUOTE_MINT_OFFSET = 75
_PUMPSWAP_PUBKEY_LEN = 32
_RPC_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}
_DEFAULT_RPC_URL = "https://api.mainnet-beta.solana.com"

_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58decode(value: str) -> bytes | None:
    """Minimal, dependency-free base58 decode. Returns None on invalid input."""
    if not isinstance(value, str) or not value:
        return None
    num = 0
    for ch in value:
        idx = _BASE58_ALPHABET.find(ch)
        if idx < 0:
            return None
        num = num * 58 + idx
    body = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    pad = len(value) - len(value.lstrip("1"))
    return b"\x00" * pad + body


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

    # Governed on-chain confirmation payloads route to the confirmation
    # normalizer, which enforces program-owner and exact-mint identity.
    if request_kind == "pumpswap_onchain_pool_confirmation" or "pumpswap_confirmation" in payload:
        return normalize_pumpswap_confirmation_payload(payload, request_kind=request_kind)

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


# ---------------------------------------------------------------------------
# Governed on-chain PumpSwap pool confirmation (read-only)
# ---------------------------------------------------------------------------

def confirm_pumpswap_pool_from_account(
    account_value: Mapping[str, Any] | None,
    *,
    expected_mint: str,
    pool_address: str,
) -> dict[str, Any]:
    """Confirm a pool account is a PumpSwap pool for the expected mint.

    Pure/deterministic — takes the `value` object from a Solana RPC
    getAccountInfo (base64 encoding) response and checks, categorically:

      1. the account exists,
      2. its owner == PUMPSWAP_AMM_PROGRAM_ID (correct program identity),
      3. its base_mint (bytes [43,75)) == expected_mint (exact mint binding).

    Returns a dict with `confirmed` (bool) and a `reason`. Never raises. Every
    check is a hard categorical equality; no numeric magnitude is compared.
    """
    result: dict[str, Any] = {
        "confirmed": False,
        "reason": None,
        "pool_address": pool_address,
        "expected_mint": expected_mint,
        "program_id": PUMPSWAP_AMM_PROGRAM_ID,
        "owner": None,
        "base_mint": None,
        "base_mint_offset": _PUMPSWAP_POOL_BASE_MINT_OFFSET,
    }
    if not account_value:
        result["reason"] = "pool_account_not_found"
        return result

    owner = account_value.get("owner")
    result["owner"] = owner
    if owner != PUMPSWAP_AMM_PROGRAM_ID:
        result["reason"] = "pool_owner_not_pumpswap_program"
        return result

    data_field = account_value.get("data")
    raw: bytes | None = None
    if isinstance(data_field, (list, tuple)) and data_field and isinstance(data_field[0], str):
        try:
            raw = base64.b64decode(data_field[0])
        except (ValueError, TypeError):
            raw = None
    if raw is None:
        result["reason"] = "pool_account_data_undecodable"
        return result

    end = _PUMPSWAP_POOL_BASE_MINT_OFFSET + _PUMPSWAP_PUBKEY_LEN
    if len(raw) < end:
        result["reason"] = "pool_account_data_too_short"
        return result

    expected_bytes = _b58decode(expected_mint)
    if expected_bytes is None or len(expected_bytes) != _PUMPSWAP_PUBKEY_LEN:
        result["reason"] = "expected_mint_undecodable"
        return result

    base_mint_bytes = raw[_PUMPSWAP_POOL_BASE_MINT_OFFSET:end]
    if base_mint_bytes != expected_bytes:
        result["reason"] = "base_mint_mismatch"
        return result

    result["confirmed"] = True
    result["reason"] = "confirmed_pumpswap_pool"
    result["base_mint"] = expected_mint
    return result


def build_pumpswap_confirmation_transport(
    *,
    expected_mint: str,
    pool_address: str,
    migration_signature: str | None = None,
    rpc_url: str = _DEFAULT_RPC_URL,
    timeout_seconds: float = 10.0,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """Bounded governed transport: confirm a PumpSwap pool on-chain (read-only).

    One getAccountInfo(pool) call, plus at most one getTransaction(signature)
    call for migration block-time when a migration signature is supplied. The
    migration block time is stored as migration evidence ONLY and must never
    stamp token_created_at. No writes, no execution, no signing.
    """

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        acct = _rpc_post(rpc_url, "getAccountInfo", [pool_address, {"encoding": "base64"}], timeout_seconds=timeout_seconds)
        if acct.get("fixture_status") == "failure":
            return MappingProxyType(dict(acct))
        account_value = (acct.get("result") or {}).get("value")
        confirmation = confirm_pumpswap_pool_from_account(
            account_value, expected_mint=expected_mint, pool_address=pool_address
        )

        migration_block_time: int | None = None
        migration_slot: int | None = None
        if migration_signature:
            tx = _rpc_post(
                rpc_url,
                "getTransaction",
                [migration_signature, {"maxSupportedTransactionVersion": 0, "encoding": "json"}],
                timeout_seconds=timeout_seconds,
            )
            tx_result = tx.get("result") if isinstance(tx, Mapping) else None
            if isinstance(tx_result, Mapping):
                bt = tx_result.get("blockTime")
                migration_block_time = int(bt) if isinstance(bt, (int, float)) else None
                sl = tx_result.get("slot")
                migration_slot = int(sl) if isinstance(sl, (int, float)) else None

        return MappingProxyType({
            "pumpswap_confirmation": confirmation,
            "migration_signature": migration_signature,
            "migration_block_time": migration_block_time,
            "migration_slot": migration_slot,
        })

    return transport


def normalize_pumpswap_confirmation_payload(
    payload: Mapping[str, Any],
    *,
    request_kind: str,
) -> NormalizedSourceResult:
    """Normalize a governed on-chain PumpSwap confirmation payload.

    Fails closed on any unconfirmed result (wrong program owner, mint mismatch,
    missing account, malformed data). On success emits one confirmed pool token
    entry carrying confirmation provenance. token_created_at is NEVER set —
    migration/pool time is stored under pumpswap_migration_block_time as
    migration evidence only.
    """
    if payload.get("fixture_status") == "failure":
        return _failure_result(
            request_kind,
            str(payload.get("failure_type") or "pumpswap_confirmation_transport_failure"),
            str(payload.get("failure_message") or "PumpSwap confirmation transport failure"),
        )

    confirmation = payload.get("pumpswap_confirmation")
    if not isinstance(confirmation, Mapping):
        return _failure_result(
            request_kind,
            "pumpswap_confirmation_missing",
            "PumpSwap confirmation payload missing confirmation result",
        )

    if not confirmation.get("confirmed"):
        return _failure_result(
            request_kind,
            f"pumpswap_confirmation_rejected_{confirmation.get('reason') or 'unknown'}",
            f"PumpSwap pool not confirmed: {confirmation.get('reason')}",
        )

    mint = confirmation.get("expected_mint")
    pool = confirmation.get("pool_address")
    token_entry = {
        "chain": _SOLANA_CHAIN,
        "mint": mint,
        "pairAddress": pool,
        "symbol": None,
        "name": None,
        "dex": "pumpswap",
        "poolSource": PUMPSWAP_SOURCE_NAME,
        "price_usd": None,
        "liquidity_usd": None,
        "captured_at": _current_iso(),
        # Confirmation provenance (audit only; never selection criteria).
        "pumpswap_confirmed": True,
        "pumpswap_program_id": confirmation.get("program_id"),
        "pumpswap_pool_owner": confirmation.get("owner"),
        "pumpswap_base_mint_offset": confirmation.get("base_mint_offset"),
        # Migration evidence ONLY — must never become token_created_at.
        "pumpswap_migration_signature": payload.get("migration_signature"),
        "pumpswap_migration_block_time": payload.get("migration_block_time"),
        "pumpswap_migration_slot": payload.get("migration_slot"),
    }
    return NormalizedSourceResult(
        source_name=PUMPSWAP_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.CLEAN_DATA,
        normalized_payload=MappingProxyType({
            "source_name": PUMPSWAP_SOURCE_NAME,
            "request_kind": request_kind,
            "tokens": [token_entry],
            "pumpswap_confirmation": dict(confirmation),
        }),
        status_code=200,
    )


def _rpc_post(
    rpc_url: str,
    method: str,
    params: list[Any],
    *,
    timeout_seconds: float,
) -> Mapping[str, Any]:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = url_request.Request(rpc_url, data=body, headers=_RPC_HEADERS, method="POST")
    try:
        with url_request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read(1_048_576)
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                return {"fixture_status": "failure", "failure_type": "pumpswap_rpc_malformed", "failure_message": f"RPC {method} returned non-object"}
            return data
    except url_error.HTTPError as exc:
        code = exc.code
        exc.close()
        return {"fixture_status": "failure", "failure_type": "pumpswap_rpc_http_error", "failure_message": f"Solana RPC HTTP error {code}"}
    except (OSError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {"fixture_status": "failure", "failure_type": "pumpswap_rpc_transport_error", "failure_message": str(exc)}


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

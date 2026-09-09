"""Governed exact present-pool confirmation for non-Pump Solana markets.

One Source-Governed request owns at most two measured RPC transports:
1. exact candidate mint + pool account batch;
2. exact pool-owner program account batch.

Provider venue labels are retained only as labels.  Admission authority comes
from supported mint-program evidence plus the exact on-chain pool owner whose
program account is executable.  Pump/PumpSwap owners remain on their specialized
verifier and are never promoted by this generic path.
"""

from __future__ import annotations

import base64
import json
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence
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
from printer_v1.sources.measured_transport import (
    BYTE_CEILINGS,
    GET_MULTIPLE_ACCOUNTS_BATCH_SIZE,
)
from printer_v1.sources.operational_source_contracts import (
    redact_https_url,
    resolve_solana_rpc_configuration,
)
from printer_v1.sources.pump_contracts import (
    SYSTEM_PROGRAM_ID,
    TOKEN_2022_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
)
from printer_v1.sources.pumpfun_direct import PUMP_PROGRAM_ID
from printer_v1.sources.pumpswap import PUMPSWAP_AMM_PROGRAM_ID
from printer_v1.sources.solana_rpc_token_age import (
    _decode_spl_token_base_mint_state,
    _decode_token_2022_mint_state,
)

SOURCE_NAME = "solana_rpc"
REQUEST_KIND = "generic_present_pool_account_batch"
CONTRACT_VERSION = "SOLANA_GENERIC_PRESENT_POOL_OWNER_EXECUTABLE_V1_2026_09_09"
FINALIZED_COMMITMENT = "finalized"
MAX_BATCH_CANDIDATES = GET_MULTIPLE_ACCOUNTS_BATCH_SIZE // 2
RPC_TIMEOUT_SECONDS = 20.0
_RPC_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}
WSOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
ALLOWED_QUOTE_MINTS = frozenset({WSOL_MINT, USDC_MINT})
SUPPORTED_TOKEN_PROGRAMS = frozenset({TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID})
FORBIDDEN_GENERIC_POOL_OWNERS = frozenset(
    {
        SYSTEM_PROGRAM_ID,
        TOKEN_PROGRAM_ID,
        TOKEN_2022_PROGRAM_ID,
        PUMP_PROGRAM_ID,
        PUMPSWAP_AMM_PROGRAM_ID,
    }
)


def _strict_base64(account: Any) -> bytes | None:
    if not isinstance(account, Mapping):
        return None
    data = account.get("data")
    if (
        not isinstance(data, (list, tuple))
        or len(data) < 2
        or not isinstance(data[0], str)
        or data[1] != "base64"
    ):
        return None
    try:
        return base64.b64decode(data[0], validate=True)
    except (ValueError, TypeError):
        return None


def _mint_program_result(account: Any) -> tuple[str, str]:
    if not isinstance(account, Mapping):
        return "MINT_ACCOUNT_NOT_FOUND", ""
    owner = str(account.get("owner") or "")
    raw = _strict_base64(account)
    if owner not in SUPPORTED_TOKEN_PROGRAMS:
        return "UNSUPPORTED_TOKEN_PROGRAM", owner
    if raw is None:
        return "MINT_ACCOUNT_DATA_MALFORMED", owner
    if owner == TOKEN_PROGRAM_ID:
        valid = len(raw) == 82 and _decode_spl_token_base_mint_state(raw)[0]
    else:
        valid = len(raw) >= 166 and _decode_token_2022_mint_state(raw)[0]
    return ("MINT_PROGRAM_CONFIRMED" if valid else "MINT_ACCOUNT_DATA_MALFORMED"), owner


def _ordered_primary_addresses(
    candidates: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        for key in ("mint", "pool"):
            value = str(item.get(key) or "").strip()
            if value and value not in seen:
                ordered.append(value)
                seen.add(value)
    if len(ordered) > GET_MULTIPLE_ACCOUNTS_BATCH_SIZE:
        raise ValueError("GENERIC_PRESENT_POOL_PRIMARY_BATCH_EXCEEDS_100")
    return tuple(ordered)


def _rpc_get_multiple_accounts(
    rpc_url: str,
    addresses: Sequence[str],
    *,
    commitment: str,
    timeout_seconds: float,
) -> Mapping[str, Any]:
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getMultipleAccounts",
            "params": [
                list(addresses),
                {"encoding": "base64", "commitment": commitment},
            ],
        }
    ).encode("utf-8")
    request = url_request.Request(
        rpc_url, data=body, headers=_RPC_HEADERS, method="POST"
    )
    byte_ceiling = int(BYTE_CEILINGS.get("solana_rpc", 1_048_576))
    try:
        with url_request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read(byte_ceiling + 1)
            response_bytes = len(raw)
            if response_bytes > byte_ceiling:
                return {
                    "fixture_status": "failure",
                    "failure_type": "generic_present_pool_account_batch_byte_ceiling",
                    "failure_message": "getMultipleAccounts exceeded byte ceiling",
                    "response_bytes": response_bytes,
                }
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("RPC response is not an object")
            data = dict(data)
            data["response_bytes"] = response_bytes
            return data
    except url_error.HTTPError as exc:
        return {
            "fixture_status": "failure",
            "failure_type": "generic_present_pool_account_batch_http_error",
            "failure_message": f"HTTP {exc.code}",
            "response_bytes": 0,
        }
    except url_error.URLError as exc:
        return {
            "fixture_status": "failure",
            "failure_type": "generic_present_pool_account_batch_url_error",
            "failure_message": str(exc.reason),
            "response_bytes": 0,
        }
    except (TimeoutError, json.JSONDecodeError, UnicodeDecodeError, OSError, ValueError) as exc:
        return {
            "fixture_status": "failure",
            "failure_type": "generic_present_pool_account_batch_transport_error",
            "failure_message": str(exc),
            "response_bytes": 0,
        }


def _values(envelope: Mapping[str, Any], expected: int) -> tuple[list[Any], int | None]:
    if envelope.get("fixture_status") == "failure":
        raise ValueError(str(envelope.get("failure_type") or "RPC_FAILURE"))
    if envelope.get("error") is not None:
        raise ValueError("RPC_ERROR")
    result = envelope.get("result")
    if not isinstance(result, Mapping):
        raise ValueError("RPC_RESULT_MISSING")
    values = result.get("value")
    if not isinstance(values, list) or len(values) != expected:
        raise ValueError("RPC_ACCOUNT_COUNT_MISMATCH")
    context = result.get("context")
    slot = int(context.get("slot")) if isinstance(context, Mapping) and context.get("slot") is not None else None
    return values, slot


def build_generic_present_pool_account_batch_transport(
    *,
    candidates: Sequence[Mapping[str, Any]],
    rpc_url: str | None = None,
    timeout_seconds: float = RPC_TIMEOUT_SECONDS,
    commitment: str = FINALIZED_COMMITMENT,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    frozen = tuple(dict(item) for item in candidates)
    if not frozen or len(frozen) > MAX_BATCH_CANDIDATES:
        raise ValueError("INVALID_GENERIC_PRESENT_POOL_BATCH_SIZE")
    resolved = resolve_solana_rpc_configuration()
    endpoint = rpc_url or resolved.url
    redact_https_url(endpoint)

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        primary_addresses = _ordered_primary_addresses(frozen)
        primary = _rpc_get_multiple_accounts(
            endpoint,
            primary_addresses,
            commitment=commitment,
            timeout_seconds=timeout_seconds,
        )
        try:
            primary_values, _ = _values(primary, len(primary_addresses))
        except ValueError:
            return {
                "fixture_status": "failure",
                "failure_stage": "PRIMARY_ACCOUNT_BATCH",
                "primary": primary,
                "response_bytes": int(primary.get("response_bytes") or 0),
            }
        by_address = dict(zip(primary_addresses, primary_values, strict=True))
        owner_addresses = tuple(
            sorted(
                {
                    str((by_address.get(str(item.get("pool") or "")) or {}).get("owner") or "")
                    for item in frozen
                    if isinstance(by_address.get(str(item.get("pool") or "")), Mapping)
                    and str((by_address.get(str(item.get("pool") or "")) or {}).get("owner") or "")
                    not in FORBIDDEN_GENERIC_POOL_OWNERS
                }
                - {""}
            )
        )
        owners: Mapping[str, Any] | None = None
        if owner_addresses:
            owners = _rpc_get_multiple_accounts(
                endpoint,
                owner_addresses,
                commitment=commitment,
                timeout_seconds=timeout_seconds,
            )
            try:
                _values(owners, len(owner_addresses))
            except ValueError:
                return {
                    "fixture_status": "failure",
                    "failure_stage": "OWNER_PROGRAM_BATCH",
                    "primary": primary,
                    "owners": owners,
                    "owner_addresses": list(owner_addresses),
                    "response_bytes": int(primary.get("response_bytes") or 0)
                    + int(owners.get("response_bytes") or 0),
                }
        return {
            "primary": primary,
            "owners": owners,
            "owner_addresses": list(owner_addresses),
            "response_bytes": int(primary.get("response_bytes") or 0)
            + (0 if owners is None else int(owners.get("response_bytes") or 0)),
        }

    return transport


def fixture_generic_present_pool_account_batch_transport(
    *,
    accounts_by_address: Mapping[str, Mapping[str, Any] | None],
    owner_program_accounts: Mapping[str, Mapping[str, Any] | None],
    slot: int = 1,
    response_bytes: int = 2048,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        candidates = [
            dict(item)
            for item in ((context.request.payload or {}).get("candidates") or ())
            if isinstance(item, Mapping)
        ]
        primary_addresses = _ordered_primary_addresses(candidates)
        primary_values = [accounts_by_address.get(address) for address in primary_addresses]
        owner_addresses = tuple(
            sorted(
                {
                    str((accounts_by_address.get(str(item.get("pool") or "")) or {}).get("owner") or "")
                    for item in candidates
                    if isinstance(accounts_by_address.get(str(item.get("pool") or "")), Mapping)
                    and str((accounts_by_address.get(str(item.get("pool") or "")) or {}).get("owner") or "")
                    not in FORBIDDEN_GENERIC_POOL_OWNERS
                }
                - {""}
            )
        )
        primary = {
            "result": {"context": {"slot": int(slot)}, "value": primary_values},
            "response_bytes": int(response_bytes),
        }
        owners = (
            None
            if not owner_addresses
            else {
                "result": {
                    "context": {"slot": int(slot)},
                    "value": [owner_program_accounts.get(address) for address in owner_addresses],
                },
                "response_bytes": int(response_bytes),
            }
        )
        return {
            "primary": primary,
            "owners": owners,
            "owner_addresses": list(owner_addresses),
            "response_bytes": int(response_bytes) * (1 + int(bool(owner_addresses))),
        }

    return transport


def _transport_identity(
    *,
    ordinal: int,
    category: str,
    targets: Sequence[str],
    response_bytes: int,
    normalized_rows: int,
    result: str,
) -> dict[str, Any]:
    return {
        "stage": "PROTOCOL_CONFIRMATION",
        "source_name": SOURCE_NAME,
        "endpoint_owner": "solana",
        "governed_request_kind": REQUEST_KIND,
        "method_or_endpoint": "getMultipleAccounts",
        "within_request_ordinal": int(ordinal),
        "target_category": category,
        "target_identity": ",".join(str(item) for item in targets),
        "response_bytes": int(response_bytes),
        "normalized_rows": int(normalized_rows),
        "result": result,
    }


def _failure(
    failure_type: str,
    message: str,
    *,
    identities: Sequence[Mapping[str, Any]] = (),
    response_bytes: int = 0,
) -> NormalizedSourceResult:
    return NormalizedSourceResult(
        source_name=SOURCE_NAME,
        request_kind=REQUEST_KIND,
        source_status=SourceStatus.FAILED,
        data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        failure_type=failure_type,
        failure_message=message,
        normalized_payload=MappingProxyType(
            {
                "transport_operations_used": len(identities),
                "transport_operation_count": len(identities),
                "transport_operation_identities": tuple(dict(item) for item in identities),
                "response_bytes": int(response_bytes),
                "normalized_rows": 0,
                "shared_source_failure": True,
            }
        ),
    )


def normalize_generic_present_pool_payload(
    payload: Mapping[str, Any] | None,
    *,
    candidates: Sequence[Mapping[str, Any]],
) -> NormalizedSourceResult:
    frozen = tuple(dict(item) for item in candidates)
    if not isinstance(payload, Mapping):
        return _failure("generic_present_pool_payload_malformed", "payload is not an object")
    primary_addresses = _ordered_primary_addresses(frozen)
    primary = payload.get("primary")
    if not isinstance(primary, Mapping):
        return _failure("generic_present_pool_primary_missing", "primary RPC evidence missing")
    identities: list[dict[str, Any]] = []
    primary_result = "FAILED" if payload.get("failure_stage") == "PRIMARY_ACCOUNT_BATCH" else "OK"
    try:
        primary_values, slot = _values(primary, len(primary_addresses))
    except ValueError as exc:
        identities.append(
            _transport_identity(
                ordinal=1,
                category="generic_mint_pool_account_batch",
                targets=primary_addresses,
                response_bytes=int(primary.get("response_bytes") or 0),
                normalized_rows=0,
                result="FAILED",
            )
        )
        return _failure(
            "generic_present_pool_primary_invalid",
            str(exc),
            identities=identities,
            response_bytes=int(payload.get("response_bytes") or 0),
        )
    identities.append(
        _transport_identity(
            ordinal=1,
            category="generic_mint_pool_account_batch",
            targets=primary_addresses,
            response_bytes=int(primary.get("response_bytes") or 0),
            normalized_rows=len(primary_values),
            result=primary_result,
        )
    )
    by_address = dict(zip(primary_addresses, primary_values, strict=True))
    owner_addresses = tuple(str(item) for item in (payload.get("owner_addresses") or ()))
    owner_by_address: dict[str, Any] = {}
    if owner_addresses:
        owners = payload.get("owners")
        if not isinstance(owners, Mapping):
            return _failure(
                "generic_present_pool_owner_program_batch_missing",
                "owner program RPC evidence missing",
                identities=identities,
                response_bytes=int(payload.get("response_bytes") or 0),
            )
        try:
            owner_values, _ = _values(owners, len(owner_addresses))
        except ValueError as exc:
            identities.append(
                _transport_identity(
                    ordinal=2,
                    category="generic_pool_owner_program_batch",
                    targets=owner_addresses,
                    response_bytes=int(owners.get("response_bytes") or 0),
                    normalized_rows=0,
                    result="FAILED",
                )
            )
            return _failure(
                "generic_present_pool_owner_program_batch_invalid",
                str(exc),
                identities=identities,
                response_bytes=int(payload.get("response_bytes") or 0),
            )
        owner_by_address = dict(zip(owner_addresses, owner_values, strict=True))
        identities.append(
            _transport_identity(
                ordinal=2,
                category="generic_pool_owner_program_batch",
                targets=owner_addresses,
                response_bytes=int(owners.get("response_bytes") or 0),
                normalized_rows=len(owner_values),
                result="OK",
            )
        )

    members: list[dict[str, Any]] = []
    for index, item in enumerate(frozen):
        mint = str(item.get("mint") or "").strip()
        pool = str(item.get("pool") or "").strip()
        base = str(item.get("base_mint") or mint).strip()
        quote = str(item.get("quote_mint") or "").strip()
        venue = str(item.get("venue") or "").strip()
        mint_account = by_address.get(mint)
        pool_account = by_address.get(pool)
        mint_outcome, token_program = _mint_program_result(mint_account)
        pool_owner = (
            str(pool_account.get("owner") or "")
            if isinstance(pool_account, Mapping)
            else ""
        )
        owner_program_account = owner_by_address.get(pool_owner)
        if not mint or not pool:
            outcome = "MISSING_POOL_OR_MINT"
        elif base != mint:
            outcome = "BASE_MINT_MISMATCH"
        elif quote not in ALLOWED_QUOTE_MINTS:
            outcome = "QUOTE_MINT_UNSUPPORTED"
        elif mint_outcome != "MINT_PROGRAM_CONFIRMED":
            outcome = mint_outcome
        elif not isinstance(pool_account, Mapping):
            outcome = "ACCOUNT_NOT_FOUND"
        elif not pool_owner:
            outcome = "POOL_OWNER_MISSING"
        elif pool_owner in FORBIDDEN_GENERIC_POOL_OWNERS:
            outcome = "POOL_OWNER_REQUIRES_SPECIALIZED_VERIFIER"
        elif not isinstance(owner_program_account, Mapping):
            outcome = "POOL_OWNER_PROGRAM_ACCOUNT_NOT_FOUND"
        elif owner_program_account.get("executable") is not True:
            outcome = "POOL_OWNER_PROGRAM_NOT_EXECUTABLE"
        else:
            outcome = "GENERIC_POOL_CONFIRMED"
        members.append(
            {
                "mint": mint,
                "pool": pool,
                "venue": venue,
                "base_mint": base,
                "quote_mint": quote,
                "token_program": token_program or None,
                "pool_program": pool_owner or None,
                "batch_index": int(index),
                "outcome": outcome,
                "context_slot": slot,
                "owner_program_executable": (
                    owner_program_account.get("executable")
                    if isinstance(owner_program_account, Mapping)
                    else None
                ),
            }
        )
    return NormalizedSourceResult(
        source_name=SOURCE_NAME,
        request_kind=REQUEST_KIND,
        source_status=SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.CLEAN_DATA,
        normalized_payload=MappingProxyType(
            {
                "contract_version": CONTRACT_VERSION,
                "member_count": len(members),
                "members": members,
                "local_validation_steps": len(members),
                "context_slot": slot,
                "response_bytes": int(payload.get("response_bytes") or 0),
                "normalized_rows": len(members),
                "transport_operations_used": len(identities),
                "transport_operation_count": len(identities),
                "transport_operation_identities": tuple(identities),
                "reserves": None,
                "liquidity": None,
                "holder_safety": None,
                "eligibility": None,
            }
        ),
        status_code=200,
    )


class GenericPresentPoolAccountBatchAdapter:
    def __init__(
        self,
        *,
        enabled: bool = False,
        transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
    ) -> None:
        self.contract = build_generic_present_pool_account_batch_adapter_contract()
        self.enabled = enabled
        self.transport = transport
        self.call_count = 0

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not self.enabled:
            raise PermissionError("generic present-pool account batch adapter is disabled")
        if self.transport is None:
            raise PermissionError("generic present-pool account batch requires transport")
        if not context.governor_approved or context.execution_path != GOVERNOR_ONLY_EXECUTION_PATH:
            raise PermissionError("generic present-pool account batch requires governed path")
        if context.request.source_name != SOURCE_NAME or context.request.request_kind != REQUEST_KIND:
            raise ValueError("generic present-pool account batch request identity mismatch")
        candidates = [
            dict(item)
            for item in ((context.request.payload or {}).get("candidates") or ())
            if isinstance(item, Mapping)
        ]
        if not candidates or len(candidates) > MAX_BATCH_CANDIDATES:
            raise ValueError("INVALID_GENERIC_PRESENT_POOL_BATCH_SIZE")
        self.call_count += 1
        try:
            payload = self.transport(context)
        except Exception as exc:
            return _failure(
                "generic_present_pool_account_batch_transport_error",
                str(exc),
            )
        return normalize_generic_present_pool_payload(
            payload if isinstance(payload, Mapping) else None,
            candidates=candidates,
        )


def build_generic_present_pool_account_batch_adapter(
    *,
    enabled: bool = False,
    transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
) -> GenericPresentPoolAccountBatchAdapter:
    return GenericPresentPoolAccountBatchAdapter(enabled=enabled, transport=transport)


def build_generic_present_pool_account_batch_adapter_contract() -> SourceAdapterContract:
    contract = build_source_adapter_contract(SOURCE_NAME)
    if not validate_source_adapter_contract(contract):
        raise ValueError("solana_rpc contract violates Governor boundary")
    if REQUEST_KIND not in contract.allowed_request_kinds:
        raise ValueError("generic_present_pool_account_batch is not registered on solana_rpc")
    return contract


__all__ = [
    "ALLOWED_QUOTE_MINTS",
    "CONTRACT_VERSION",
    "MAX_BATCH_CANDIDATES",
    "REQUEST_KIND",
    "SOURCE_NAME",
    "SUPPORTED_TOKEN_PROGRAMS",
    "build_generic_present_pool_account_batch_adapter",
    "build_generic_present_pool_account_batch_transport",
    "fixture_generic_present_pool_account_batch_transport",
    "normalize_generic_present_pool_payload",
]

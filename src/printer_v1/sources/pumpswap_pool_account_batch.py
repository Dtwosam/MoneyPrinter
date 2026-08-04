"""Governed Solana getMultipleAccounts batch for PumpSwap pool confirmation.

Source: solana_rpc
Request kind: pumpswap_pool_account_batch (already registered)

Proves only:
  - exact pool account existence
  - owner == PumpSwap AMM program
  - base_mint at [43,75) equals candidate mint

Does not derive quote mint, reserves, liquidity, age, migration lineage,
holder/safety, or eligibility.
"""

from __future__ import annotations

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
    OFFICIAL_SOLANA_PUBLIC_RPC_URL,
    redact_https_url,
    resolve_solana_rpc_configuration,
)
from printer_v1.sources.pumpswap import (
    PUMPSWAP_AMM_PROGRAM_ID,
    _PUMPSWAP_POOL_BASE_MINT_OFFSET,
    confirm_pumpswap_pool_from_account,
)


SOURCE_NAME = "solana_rpc"
REQUEST_KIND = "pumpswap_pool_account_batch"
ALLOWED_REQUEST_KINDS = frozenset({REQUEST_KIND})
CONTRACT_VERSION = "SOLANA_GET_MULTIPLE_ACCOUNTS_PUMPSWAP_BASE_MINT_2026_08_04"
FINALIZED_COMMITMENT = "finalized"
MAX_BATCH_ADDRESSES = GET_MULTIPLE_ACCOUNTS_BATCH_SIZE  # 100
RPC_TIMEOUT_SECONDS = 20.0
_RPC_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

# confirm_pumpswap_pool_from_account reason → protocol outcome codes
_CONFIRM_REASON_TO_OUTCOME = {
    "confirmed_pumpswap_pool": "CURRENT_POOL_CONFIRMED",
    "pool_account_not_found": "ACCOUNT_NOT_FOUND",
    "pool_owner_not_pumpswap_program": "POOL_OWNER_MISMATCH",
    "pool_account_data_undecodable": "POOL_DATA_UNDECODABLE",
    "pool_account_data_too_short": "POOL_DATA_UNDECODABLE",
    "base_mint_mismatch": "BASE_MINT_MISMATCH",
    "expected_mint_undecodable": "CONTRACT_BLOCKED",
}


def build_ordered_unique_addresses(
    candidates: Sequence[Mapping[str, Any]],
    *,
    max_addresses: int = MAX_BATCH_ADDRESSES,
) -> tuple[list[str], dict[str, list[dict[str, str]]], list[dict[str, str]]]:
    """Deterministic unique pool ordering with candidate-to-address mapping.

    Returns (addresses, address_to_candidates, skipped_invalid).
    Duplicate pool addresses are transported once; all candidates for that
    pool share the same batch index.
    """
    if max_addresses < 1 or max_addresses > MAX_BATCH_ADDRESSES:
        raise ValueError("INVALID_ACCOUNT_BATCH_CAP")
    addresses: list[str] = []
    mapping: dict[str, list[dict[str, str]]] = {}
    skipped: list[dict[str, str]] = []
    for raw in candidates:
        mint = str(raw.get("mint") or raw.get("mint_identity") or "").strip()
        pool = str(raw.get("pool") or raw.get("pool_address") or "").strip()
        venue = str(raw.get("venue") or "")
        if not mint or not pool:
            skipped.append(
                {
                    "mint": mint,
                    "pool": pool,
                    "venue": venue,
                    "reason": "MISSING_POOL_OR_MINT",
                }
            )
            continue
        entry = {"mint": mint, "pool": pool, "venue": venue}
        if pool in mapping:
            mapping[pool].append(entry)
            continue
        if len(addresses) >= max_addresses:
            skipped.append({**entry, "reason": "BATCH_CAP_EXCEEDED"})
            continue
        addresses.append(pool)
        mapping[pool] = [entry]
    return addresses, mapping, skipped


def protocol_outcome_from_confirm(confirm: Mapping[str, Any]) -> str:
    reason = str(confirm.get("reason") or "unknown")
    if confirm.get("confirmed"):
        return "CURRENT_POOL_CONFIRMED"
    return _CONFIRM_REASON_TO_OUTCOME.get(reason, "CONTRACT_BLOCKED")


def member_evidence(
    *,
    mint: str,
    pool: str,
    index: int,
    account: Mapping[str, Any] | None,
    confirm: Mapping[str, Any],
    outcome: str,
) -> dict[str, Any]:
    owner = None
    data_length = None
    if isinstance(account, Mapping):
        owner = account.get("owner")
        data = account.get("data")
        if isinstance(data, (list, tuple)) and data and isinstance(data[0], str):
            try:
                import base64

                data_length = len(base64.b64decode(data[0]))
            except (ValueError, TypeError):
                data_length = None
    return {
        "mint": mint,
        "pool": pool,
        "batch_index": int(index),
        "owner": owner,
        "data_length": data_length,
        "confirm_reason": confirm.get("reason"),
        "outcome": outcome,
        "program_id": PUMPSWAP_AMM_PROGRAM_ID,
        "base_mint_offset": _PUMPSWAP_POOL_BASE_MINT_OFFSET,
        # Explicit non-evidence: never emit forbidden fields
        "quote_mint": None,
        "reserves": None,
        "virtual_quote_reserves": None,
        "token_age": None,
        "migration_time": None,
        "holder_safety": None,
        "eligibility": None,
    }


def normalize_pumpswap_pool_account_batch_payload(
    payload: Mapping[str, Any] | None,
    *,
    request_kind: str,
    requested_addresses: Sequence[str],
    address_to_candidates: Mapping[str, Sequence[Mapping[str, str]]],
) -> NormalizedSourceResult:
    """Normalize one getMultipleAccounts response into per-member outcomes."""
    if request_kind != REQUEST_KIND:
        return _failure(
            "pumpswap_pool_account_batch_kind_mismatch",
            "request kind is not pumpswap_pool_account_batch",
        )
    if not isinstance(payload, Mapping):
        return _failure(
            "pumpswap_pool_account_batch_malformed",
            "RPC payload is not an object",
        )
    if payload.get("fixture_status") == "failure":
        return _failure(
            str(payload.get("failure_type") or "pumpswap_pool_account_batch_rpc_failure"),
            str(payload.get("failure_message") or "PumpSwap account batch RPC failure"),
            response_bytes=int(payload.get("response_bytes") or 0),
        )
    if payload.get("error") is not None:
        return _failure(
            "pumpswap_pool_account_batch_rpc_error",
            "Solana RPC returned an error envelope",
            response_bytes=int(payload.get("response_bytes") or 0),
        )
    if "result" not in payload:
        return _failure(
            "pumpswap_pool_account_batch_result_missing",
            "Solana RPC omitted result",
            response_bytes=int(payload.get("response_bytes") or 0),
        )
    result = payload.get("result")
    if not isinstance(result, Mapping):
        return _failure(
            "pumpswap_pool_account_batch_result_not_object",
            "result is not an object",
            response_bytes=int(payload.get("response_bytes") or 0),
        )
    context = result.get("context")
    values = result.get("value")
    if not isinstance(context, Mapping) or "value" not in result:
        return _failure(
            "pumpswap_pool_account_batch_envelope_incomplete",
            "result.context or result.value missing",
            response_bytes=int(payload.get("response_bytes") or 0),
        )
    if not isinstance(values, list):
        return _failure(
            "pumpswap_pool_account_batch_value_not_list",
            "result.value is not a list",
            response_bytes=int(payload.get("response_bytes") or 0),
        )
    addresses = list(requested_addresses)
    if len(values) != len(addresses):
        return _failure(
            "pumpswap_pool_account_batch_count_mismatch",
            f"result.value length {len(values)} != requested {len(addresses)}",
            response_bytes=int(payload.get("response_bytes") or 0),
        )

    members: list[dict[str, Any]] = []
    local_validations = 0
    for index, pool in enumerate(addresses):
        account = values[index]
        account_map = account if isinstance(account, Mapping) else None
        for candidate in address_to_candidates.get(pool, ()):
            mint = str(candidate.get("mint") or "")
            confirm = confirm_pumpswap_pool_from_account(
                account_map,
                expected_mint=mint,
                pool_address=pool,
            )
            outcome = protocol_outcome_from_confirm(confirm)
            local_validations += 1
            members.append(
                member_evidence(
                    mint=mint,
                    pool=pool,
                    index=index,
                    account=account_map,
                    confirm=confirm,
                    outcome=outcome,
                )
            )

    response_bytes = int(payload.get("response_bytes") or 0)
    slot = context.get("slot")
    identity = {
        "stage": "PROTOCOL_CONFIRMATION",
        "source_name": SOURCE_NAME,
        "endpoint_owner": "solana",
        "governed_request_kind": REQUEST_KIND,
        "method_or_endpoint": "getMultipleAccounts",
        "within_request_ordinal": 1,
        "target_category": "pumpswap_pool_batch",
        "target_identity": ",".join(addresses[:8])
        + (f"...(+{len(addresses) - 8})" if len(addresses) > 8 else ""),
        "response_bytes": response_bytes,
        "normalized_rows": len(members),
        "result": "OK",
    }
    return NormalizedSourceResult(
        source_name=SOURCE_NAME,
        request_kind=REQUEST_KIND,
        source_status=SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.CLEAN_DATA,
        normalized_payload=MappingProxyType(
            {
                "contract_version": CONTRACT_VERSION,
                "requested_addresses": list(addresses),
                "context_slot": slot,
                "member_count": len(members),
                "members": members,
                "local_validation_steps": local_validations,
                "response_bytes": response_bytes,
                "normalized_rows": len(members),
                "transport_operations_used": 1,
                "transport_operation_count": 1,
                "transport_operation_identities": (identity,),
                # Forbidden fields must not appear as derived facts
                "reserves": None,
                "virtual_quote_reserves": None,
                "liquidity": None,
                "token_age": None,
                "holder_safety": None,
            }
        ),
        status_code=200,
    )


def build_pumpswap_pool_account_batch_transport(
    *,
    addresses: Sequence[str],
    rpc_url: str | None = None,
    timeout_seconds: float = RPC_TIMEOUT_SECONDS,
    commitment: str = FINALIZED_COMMITMENT,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """One-attempt live transport for getMultipleAccounts(addresses)."""
    if len(addresses) > MAX_BATCH_ADDRESSES:
        raise ValueError("ACCOUNT_BATCH_EXCEEDS_100")
    if len(addresses) < 1:
        raise ValueError("ACCOUNT_BATCH_EMPTY")
    resolved = resolve_solana_rpc_configuration()
    endpoint = rpc_url or resolved.url
    redact_https_url(endpoint)  # validates/redacts; discard redacted host

    ordered = list(addresses)

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return _rpc_get_multiple_accounts(
            endpoint,
            ordered,
            commitment=commitment,
            timeout_seconds=timeout_seconds,
        )

    return transport


def fixture_account_batch_transport(
    values_by_address: Mapping[str, Mapping[str, Any] | None],
    *,
    slot: int = 1,
    response_bytes: int = 2048,
    force_error: Mapping[str, Any] | None = None,
    force_count_mismatch: bool = False,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """Deterministic offline transport for tests."""

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        if force_error is not None:
            return dict(force_error)
        payload = context.request.payload or {}
        addresses = list(payload.get("addresses") or ())
        values = [values_by_address.get(addr) for addr in addresses]
        if force_count_mismatch:
            values = values[:-1] if values else [None]
        return {
            "result": {"context": {"slot": int(slot)}, "value": values},
            "response_bytes": int(response_bytes),
        }

    return transport


class PumpSwapPoolAccountBatchAdapter:
    """Source Governor adapter for pumpswap_pool_account_batch on solana_rpc."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
    ) -> None:
        self.contract = build_pumpswap_pool_account_batch_adapter_contract()
        self.enabled = enabled
        self.transport = transport
        self.call_count = 0

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not self.enabled:
            raise PermissionError("PumpSwap pool account batch adapter is disabled")
        if self.transport is None:
            raise PermissionError("PumpSwap pool account batch requires transport")
        _validate_context(context)
        self.call_count += 1
        try:
            payload = self.transport(context)
        except Exception as exc:
            return _failure(
                "pumpswap_pool_account_batch_transport_error",
                str(exc),
            )
        requested = list((context.request.payload or {}).get("addresses") or ())
        mapping_raw = (context.request.payload or {}).get("address_to_candidates") or {}
        address_to_candidates: dict[str, list[dict[str, str]]] = {}
        if isinstance(mapping_raw, Mapping):
            for key, items in mapping_raw.items():
                address_to_candidates[str(key)] = [
                    dict(item) for item in (items or ()) if isinstance(item, Mapping)
                ]
        return normalize_pumpswap_pool_account_batch_payload(
            payload if isinstance(payload, Mapping) else None,
            request_kind=context.request.request_kind,
            requested_addresses=requested,
            address_to_candidates=address_to_candidates,
        )


def build_pumpswap_pool_account_batch_adapter(
    *,
    enabled: bool = False,
    transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
) -> PumpSwapPoolAccountBatchAdapter:
    return PumpSwapPoolAccountBatchAdapter(enabled=enabled, transport=transport)


def build_pumpswap_pool_account_batch_adapter_contract() -> SourceAdapterContract:
    contract = build_source_adapter_contract(SOURCE_NAME)
    if not validate_source_adapter_contract(contract):
        raise ValueError("solana_rpc contract violates Governor boundary")
    if REQUEST_KIND not in contract.allowed_request_kinds:
        raise ValueError("pumpswap_pool_account_batch is not registered on solana_rpc")
    return contract


def _validate_context(context: SourceAdapterContext) -> None:
    if not context or not context.governor_approved:
        raise PermissionError("account batch requires Governor approval")
    if context.execution_path != GOVERNOR_ONLY_EXECUTION_PATH:
        raise PermissionError("account batch requires governed path")
    if context.request.source_name != SOURCE_NAME:
        raise ValueError("account batch source identity mismatch")
    if context.request.request_kind != REQUEST_KIND:
        raise ValueError("account batch request kind mismatch")


def _failure(
    failure_type: str,
    failure_message: str,
    *,
    response_bytes: int = 0,
) -> NormalizedSourceResult:
    identity = {
        "stage": "PROTOCOL_CONFIRMATION",
        "source_name": SOURCE_NAME,
        "endpoint_owner": "solana",
        "governed_request_kind": REQUEST_KIND,
        "method_or_endpoint": "getMultipleAccounts",
        "within_request_ordinal": 1,
        "target_category": "pumpswap_pool_batch",
        "target_identity": None,
        "response_bytes": int(response_bytes),
        "normalized_rows": 0,
        "result": "FAILED",
    }
    return NormalizedSourceResult(
        source_name=SOURCE_NAME,
        request_kind=REQUEST_KIND,
        source_status=SourceStatus.FAILED,
        data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        failure_type=failure_type,
        failure_message=failure_message,
        normalized_payload=MappingProxyType(
            {
                "transport_operations_used": 1,
                "response_bytes": int(response_bytes),
                "normalized_rows": 0,
                "transport_operation_identities": (identity,),
                "shared_source_failure": True,
                "outcome": "SOURCE_UNAVAILABLE",
            }
        ),
    )


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
                    "failure_type": "pumpswap_pool_account_batch_byte_ceiling",
                    "failure_message": "getMultipleAccounts exceeded byte ceiling",
                    "response_bytes": response_bytes,
                }
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                return {
                    "fixture_status": "failure",
                    "failure_type": "pumpswap_pool_account_batch_malformed",
                    "failure_message": "getMultipleAccounts returned non-object",
                    "response_bytes": response_bytes,
                }
            data = dict(data)
            data["response_bytes"] = response_bytes
            return data
    except url_error.HTTPError as exc:
        return {
            "fixture_status": "failure",
            "failure_type": "pumpswap_pool_account_batch_http_error",
            "failure_message": f"HTTP {exc.code}",
            "response_bytes": 0,
        }
    except url_error.URLError as exc:
        return {
            "fixture_status": "failure",
            "failure_type": "pumpswap_pool_account_batch_url_error",
            "failure_message": str(exc.reason),
            "response_bytes": 0,
        }
    except (TimeoutError, json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        return {
            "fixture_status": "failure",
            "failure_type": "pumpswap_pool_account_batch_transport_error",
            "failure_message": str(exc),
            "response_bytes": 0,
        }


__all__ = [
    "SOURCE_NAME",
    "REQUEST_KIND",
    "CONTRACT_VERSION",
    "MAX_BATCH_ADDRESSES",
    "PumpSwapPoolAccountBatchAdapter",
    "build_ordered_unique_addresses",
    "build_pumpswap_pool_account_batch_adapter",
    "build_pumpswap_pool_account_batch_transport",
    "fixture_account_batch_transport",
    "member_evidence",
    "normalize_pumpswap_pool_account_batch_payload",
    "protocol_outcome_from_confirm",
]

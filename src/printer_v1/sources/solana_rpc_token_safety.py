"""Governed Solana mint-account core safety evidence.

This adapter resolves only facts the finalized mint account can prove directly:
mint authority, freeze authority, current supply sanity, and SPL Token versus
Token-2022 program identity. It deliberately does not claim metadata mutability,
LP lock/burn status, provider risk flags, wallet clustering, or tradeability.

One governed request uses one read-only ``getAccountInfo`` JSON-RPC operation.
No wallet, signing, transaction construction, paid API, retry loop, endpoint
rotation, or independent scheduler loop is introduced.
"""

from __future__ import annotations

import base64
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
from printer_v1.sources.measured_transport import (
    MeasuredTransportLedger,
    TransportOperationIdentity,
)
from printer_v1.sources.operational_source_contracts import (
    resolve_solana_rpc_configuration,
)
from printer_v1.sources.pump_contracts import TOKEN_2022_PROGRAM_ID, TOKEN_PROGRAM_ID
from printer_v1.sources.solana_rpc_holder import (
    SOLANA_RPC_SOURCE_NAME,
    SOLANA_RPC_TIMEOUT_SECONDS,
    _rpc_post,
    redacted_solana_rpc_source,
)
from printer_v1.sources.solana_rpc_token_age import (
    _decode_spl_token_base_mint_state,
    _decode_token_2022_mint_state,
)


SOLANA_RPC_TOKEN_SAFETY_REQUEST_KIND = "mint_account_reference"
SOLANA_RPC_TOKEN_SAFETY_TRANSPORT_OPERATION_COST = 1
_ALLOWED_REQUEST_KINDS = frozenset({SOLANA_RPC_TOKEN_SAFETY_REQUEST_KIND})


@dataclass(frozen=True)
class SolanaRpcTokenSafetyAdapterMetadata:
    source_name: str = SOLANA_RPC_SOURCE_NAME
    display_name: str = "Solana RPC Token Core Safety"
    enabled_by_default: bool = False
    requires_governor_context: bool = True
    supports_network_execution: bool = False
    fixture_transport_only: bool = True
    read_only: bool = True


class SolanaRpcTokenSafetyAdapter:
    def __init__(
        self,
        *,
        enabled: bool = False,
        fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
    ) -> None:
        self.metadata = SolanaRpcTokenSafetyAdapterMetadata()
        self.contract = build_solana_rpc_token_safety_adapter_contract()
        self.enabled = enabled
        self.transport = fixture_transport
        self.call_count = 0

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not self.enabled:
            raise PermissionError("Solana RPC token-safety adapter is disabled by default")
        if self.transport is None:
            raise PermissionError("Solana RPC token-safety adapter requires an explicit transport")
        _validate_context(context, self.contract)
        self.call_count += 1
        try:
            payload = self.transport(context)
        except Exception as exc:
            return _failure_result(
                context.request.request_kind,
                "solana_rpc_token_safety_transport_error",
                str(exc),
            )
        return normalize_solana_rpc_token_safety_response(
            payload, request_kind=context.request.request_kind
        )


def build_solana_rpc_token_safety_adapter_contract() -> SourceAdapterContract:
    contract = build_source_adapter_contract(SOLANA_RPC_SOURCE_NAME)
    if not validate_source_adapter_contract(contract):
        raise ValueError("Solana RPC token-safety contract violates Source Governor boundary")
    return contract


def build_solana_rpc_token_safety_adapter(
    *,
    enabled: bool = False,
    fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
) -> SolanaRpcTokenSafetyAdapter:
    return SolanaRpcTokenSafetyAdapter(enabled=enabled, fixture_transport=fixture_transport)


def build_solana_rpc_token_safety_transport(
    token_mint: str,
    *,
    rpc_url: str | None = None,
    timeout_seconds: float = SOLANA_RPC_TIMEOUT_SECONDS,
    measured_transport_ledger: MeasuredTransportLedger | None = None,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    endpoint = (
        str(rpc_url)
        if rpc_url is not None and str(rpc_url).strip()
        else resolve_solana_rpc_configuration().url
    )

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        response = _rpc_post(
            endpoint,
            "getAccountInfo",
            [
                token_mint,
                {
                    "encoding": "base64",
                    "commitment": "finalized",
                },
            ],
            timeout_seconds=timeout_seconds,
        )
        result = "FAILED" if response.get("fixture_status") == "failure" else "COMPLETED"
        identity = TransportOperationIdentity(
            stage="HOLDER_SAFETY",
            source_name=SOLANA_RPC_SOURCE_NAME,
            endpoint_owner=redacted_solana_rpc_source(endpoint),
            governed_request_kind=SOLANA_RPC_TOKEN_SAFETY_REQUEST_KIND,
            method_or_endpoint="getAccountInfo",
            within_request_ordinal=1,
            target_category="TOKEN_MINT",
            target_identity=token_mint,
            response_bytes=int(
                response.get("_transport_response_bytes")
                if response.get("_transport_response_bytes") is not None
                else 0
            ),
            normalized_rows=0 if result == "FAILED" else 1,
            result=result,
        )
        if measured_transport_ledger is not None:
            measured_transport_ledger.record_transport(identity)
        if response.get("fixture_status") == "failure":
            return MappingProxyType(
                {
                    **dict(response),
                    "token_mint": token_mint,
                    "commitment": "finalized",
                    "transport_operation_identities": [identity.as_dict()],
                    "transport_operations_used": 1,
                }
            )
        return MappingProxyType(
            {
                "token_mint": token_mint,
                "account_info_result": response,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "rpc_method": "getAccountInfo",
                "commitment": "finalized",
                "context_slot": (
                    response.get("result", {}).get("context", {}).get("slot")
                    if isinstance(response.get("result"), Mapping)
                    else None
                ),
                "underlying_operation_count": 1,
                "transport_operation_identities": [identity.as_dict()],
                "transport_operations_used": 1,
            }
        )

    return transport


def _decode_account_data(value: Mapping[str, Any]) -> bytes | None:
    data = value.get("data")
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


def _coption_status(raw: bytes, offset: int, *, empty: str, present: str) -> str | None:
    if len(raw) < offset + 4:
        return None
    tag = int.from_bytes(raw[offset : offset + 4], "little")
    if tag == 0:
        return empty
    if tag == 1:
        return present
    return None


def normalize_solana_rpc_token_safety_response(
    payload: Mapping[str, Any],
    *,
    request_kind: str,
) -> NormalizedSourceResult:
    if request_kind not in _ALLOWED_REQUEST_KINDS:
        return _failure_result(
            request_kind,
            "solana_rpc_token_safety_request_kind_not_allowed",
            "Solana RPC token-safety request kind is not allowed",
        )
    if payload.get("fixture_status") == "failure":
        return _failure_result(
            request_kind,
            str(payload.get("failure_type") or "solana_rpc_token_safety_failure"),
            str(payload.get("failure_message") or "Solana RPC token-safety failure"),
            payload=payload,
        )

    token_mint = str(payload.get("token_mint") or "")
    rpc_result = payload.get("account_info_result")
    if not token_mint or not isinstance(rpc_result, Mapping) or rpc_result.get("error"):
        return _failure_result(
            request_kind,
            "solana_rpc_token_safety_missing_account_result",
            "Solana RPC token-safety response missing a valid account result",
        )
    result = rpc_result.get("result")
    value = result.get("value") if isinstance(result, Mapping) else None
    if not isinstance(value, Mapping):
        return _failure_result(
            request_kind,
            "solana_rpc_token_safety_mint_account_missing",
            "Finalized mint account is missing",
        )

    owner = str(value.get("owner") or "")
    raw = _decode_account_data(value)
    if raw is None:
        return _failure_result(
            request_kind,
            "solana_rpc_token_safety_malformed_account_data",
            "Finalized mint account data is not valid base64",
        )

    if owner == TOKEN_PROGRAM_ID:
        valid_layout = len(raw) == 82 and _decode_spl_token_base_mint_state(raw)[0]
    elif owner == TOKEN_2022_PROGRAM_ID:
        valid_layout = len(raw) >= 166 and _decode_token_2022_mint_state(raw)[0]
    else:
        return _failure_result(
            request_kind,
            "solana_rpc_token_safety_unsupported_program",
            "Mint account is not owned by SPL Token or Token-2022",
        )
    if not valid_layout:
        return _failure_result(
            request_kind,
            "solana_rpc_token_safety_invalid_mint_layout",
            "Mint account layout is invalid for its token program",
        )

    mint_authority_status = _coption_status(
        raw,
        0,
        empty="MINT_AUTHORITY_RENOUNCED",
        present="MINT_AUTHORITY_PRESENT",
    )
    freeze_authority_status = _coption_status(
        raw,
        46,
        empty="FREEZE_AUTHORITY_DISABLED",
        present="FREEZE_AUTHORITY_PRESENT",
    )
    if mint_authority_status is None or freeze_authority_status is None:
        return _failure_result(
            request_kind,
            "solana_rpc_token_safety_invalid_authority_tag",
            "Mint account contains an invalid authority option tag",
        )
    supply = int.from_bytes(raw[36:44], "little")
    normalized = {
        "token_mint": token_mint,
        "mint_authority_status": mint_authority_status,
        "freeze_authority_status": freeze_authority_status,
        "supply_sanity_label": "SUPPLY_SANITY_OK" if supply > 0 else "SUPPLY_SANITY_CAUTION",
        "token_program_label": "SPL_TOKEN_OR_TOKEN_2022_VERIFIED",
        "source_name": SOLANA_RPC_SOURCE_NAME,
        "request_kind": request_kind,
        "captured_at": str(payload.get("captured_at") or datetime.now(timezone.utc).isoformat()),
        "paper_only_context": True,
        "rpc_method": str(payload.get("rpc_method") or "getAccountInfo"),
        "commitment": str(payload.get("commitment") or "finalized"),
        "context_slot": payload.get("context_slot"),
        "underlying_operation_count": int(payload.get("underlying_operation_count") or 1),
        "transport_operation_identities": list(
            payload.get("transport_operation_identities") or []
        ),
        "transport_operations_used": payload.get("transport_operations_used"),
    }
    return NormalizedSourceResult(
        source_name=SOLANA_RPC_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.CLEAN_DATA,
        normalized_payload=MappingProxyType(normalized),
    )


def _validate_context(context: SourceAdapterContext, contract: SourceAdapterContract) -> None:
    if not context or not context.governor_approved:
        raise PermissionError("source adapter execution requires Source Governor approval")
    if context.execution_path != GOVERNOR_ONLY_EXECUTION_PATH:
        raise PermissionError("source adapter execution requires governed recording path")
    if context.request.source_name != SOLANA_RPC_SOURCE_NAME:
        raise ValueError("source request does not match adapter")
    if context.request.request_kind not in contract.allowed_request_kinds:
        raise ValueError("source request kind is not allowed for adapter")


def _failure_result(
    request_kind: str,
    failure_type: str,
    failure_message: str,
    *,
    payload: Mapping[str, Any] | None = None,
) -> NormalizedSourceResult:
    return NormalizedSourceResult(
        source_name=SOLANA_RPC_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.FAILED,
        data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        failure_type=failure_type,
        failure_message=failure_message,
        normalized_payload=MappingProxyType(dict(payload or {})),
    )

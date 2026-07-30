"""Narrow Source-Governed direct Pump migration live-tail adapter.

The adapter owns no cursor, backfill, recovery, candidate admission, selection,
tracking or persistence.  Each execution performs exactly one finalized Solana
JSON-RPC operation through an injected transport.
"""

from __future__ import annotations

import json
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
from printer_v1.sources.operational_source_contracts import (
    redact_https_url,
    resolve_solana_rpc_configuration,
)
from printer_v1.sources.pump_contracts import (
    PUMP_PROGRAM_ID,
    decode_supported_pump_migration_transaction,
)


SOURCE_NAME = "solana_rpc"
SIGNATURE_PAGE_REQUEST_KIND = "restored_pump_migration_signature_page"
TRANSACTION_REQUEST_KIND = "restored_pump_migration_transaction"
ALLOWED_REQUEST_KINDS = frozenset(
    {SIGNATURE_PAGE_REQUEST_KIND, TRANSACTION_REQUEST_KIND}
)
FINALIZED_COMMITMENT = "finalized"
SIGNATURE_PAGE_LIMIT = 12
MAX_TRANSACTION_LOOKUPS = 12
RPC_TIMEOUT_SECONDS = 12.0
RPC_BYTE_CEILING = 1_048_576
RPC_HEADERS = {
    "User-Agent": "PrinterV1/0.1 (+paper-only direct Pump migration locator)",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


class DirectPumpMigrationAdapter:
    def __init__(
        self,
        *,
        enabled: bool = False,
        transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
    ) -> None:
        self.contract = build_direct_pump_migration_adapter_contract()
        self.enabled = enabled
        self.transport = transport
        self.call_count = 0

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not self.enabled:
            raise PermissionError("direct Pump migration adapter is disabled")
        if self.transport is None:
            raise PermissionError("direct Pump migration adapter requires transport")
        _validate_context(context, self.contract)
        self.call_count += 1
        try:
            payload = self.transport(context)
        except Exception as exc:
            return _failure(
                context.request.request_kind,
                "direct_pump_migration_transport_error",
                str(exc),
            )
        return normalize_direct_pump_migration_response(
            payload,
            request_kind=context.request.request_kind,
            expected_signature=context.request.payload.get("signature"),
        )


def build_direct_pump_migration_adapter_contract() -> SourceAdapterContract:
    contract = build_source_adapter_contract(SOURCE_NAME)
    if not validate_source_adapter_contract(contract):
        raise ValueError("direct Pump migration contract violates Governor boundary")
    if not ALLOWED_REQUEST_KINDS.issubset(contract.allowed_request_kinds):
        raise ValueError("direct Pump migration request kinds are not registered")
    return contract


def build_direct_pump_migration_adapter(
    *,
    enabled: bool = False,
    transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
) -> DirectPumpMigrationAdapter:
    return DirectPumpMigrationAdapter(enabled=enabled, transport=transport)


def build_direct_pump_migration_transport(
    *,
    rpc_url: str | None = None,
    timeout_seconds: float = RPC_TIMEOUT_SECONDS,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """Build the one-operation live transport used only under the adapter."""

    resolved = resolve_solana_rpc_configuration()
    endpoint = rpc_url or resolved.url
    # Validate an explicitly injected endpoint through the same contract used by
    # runtime/preflight. The redacted value is intentionally discarded.
    redact_https_url(endpoint)

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        kind = context.request.request_kind
        if kind == SIGNATURE_PAGE_REQUEST_KIND:
            params: list[Any] = [
                PUMP_PROGRAM_ID,
                {
                    "commitment": FINALIZED_COMMITMENT,
                    "limit": SIGNATURE_PAGE_LIMIT,
                },
            ]
            return _rpc_post(
                endpoint,
                "getSignaturesForAddress",
                params,
                timeout_seconds=timeout_seconds,
            )
        if kind == TRANSACTION_REQUEST_KIND:
            signature = context.request.payload.get("signature")
            if not isinstance(signature, str) or not signature.strip():
                return MappingProxyType(
                    {
                        "fixture_status": "failure",
                        "failure_type": "direct_pump_signature_missing",
                        "failure_message": "transaction lookup requires exact signature",
                    }
                )
            return _rpc_post(
                endpoint,
                "getTransaction",
                [
                    signature,
                    {
                        "encoding": "json",
                        "commitment": FINALIZED_COMMITMENT,
                        "maxSupportedTransactionVersion": 0,
                    },
                ],
                timeout_seconds=timeout_seconds,
            )
        return MappingProxyType(
            {
                "fixture_status": "failure",
                "failure_type": "direct_pump_request_kind_not_allowed",
                "failure_message": f"unsupported request kind: {kind}",
            }
        )

    return transport


def normalize_direct_pump_migration_response(
    payload: Mapping[str, Any] | None,
    *,
    request_kind: str,
    expected_signature: object = None,
) -> NormalizedSourceResult:
    if request_kind not in ALLOWED_REQUEST_KINDS:
        return _failure(
            request_kind,
            "direct_pump_request_kind_not_allowed",
            "direct Pump request kind is not allowed",
        )
    if not isinstance(payload, Mapping):
        return _failure(
            request_kind,
            "direct_pump_rpc_malformed",
            "Solana RPC payload is not an object",
        )
    if payload.get("fixture_status") == "failure":
        return _failure(
            request_kind,
            str(payload.get("failure_type") or "direct_pump_rpc_failure"),
            str(payload.get("failure_message") or "direct Pump RPC failure"),
        )
    if payload.get("error") is not None or "result" not in payload:
        return _failure(
            request_kind,
            "direct_pump_rpc_error_or_result_missing",
            "Solana RPC returned an error or omitted result",
        )

    result = payload.get("result")
    if request_kind == SIGNATURE_PAGE_REQUEST_KIND:
        if not isinstance(result, list):
            return _failure(
                request_kind,
                "direct_pump_signature_page_malformed",
                "getSignaturesForAddress result is not a list",
            )
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in result:
            if not isinstance(row, Mapping):
                return _failure(
                    request_kind,
                    "direct_pump_signature_row_malformed",
                    "signature page contains a non-object row",
                )
            signature = row.get("signature")
            slot = row.get("slot")
            if (
                not isinstance(signature, str)
                or not signature.strip()
                or not isinstance(slot, int)
                or row.get("confirmationStatus") != FINALIZED_COMMITMENT
            ):
                return _failure(
                    request_kind,
                    "direct_pump_signature_row_not_finalized",
                    "signature row lacks exact finalized identity",
                )
            if row.get("err") is not None:
                continue
            if signature in seen:
                continue
            seen.add(signature)
            rows.append({"signature": signature, "slot": slot})
            if len(rows) >= MAX_TRANSACTION_LOOKUPS:
                break
        return NormalizedSourceResult(
            source_name=SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.CLEAN_DATA,
            normalized_payload=MappingProxyType(
                {
                    "signatures": rows,
                    "signature_count": len(rows),
                    "commitment": FINALIZED_COMMITMENT,
                    "cursor_used": False,
                    "transport_operation_count": 1,
                }
            ),
            status_code=200,
        )

    if result is None:
        return _failure(
            request_kind,
            "direct_pump_migration_transaction_null",
            "finalized getTransaction returned null",
        )
    if not isinstance(result, Mapping):
        return _failure(
            request_kind,
            "direct_pump_migration_transaction_malformed",
            "getTransaction result is not an object",
        )
    decoded = decode_supported_pump_migration_transaction(result)
    if not decoded.get("supported"):
        return _failure(
            request_kind,
            f"direct_pump_migration_rejected_{decoded.get('reason') or 'unknown'}",
            "transaction is not the exact pinned Pump migrate instruction",
        )
    signature = expected_signature
    if not isinstance(signature, str) or not signature.strip():
        return _failure(
            request_kind,
            "direct_pump_signature_identity_missing",
            "transaction response lacks requested signature identity",
        )
    token = {
        "mint": str(decoded["mint"]),
        "migration_signature": signature,
        "pool_address": str(decoded["pool_address"]),
        "slot": int(decoded["slot"]),
        "block_time": int(decoded["block_time"]),
        "commitment": FINALIZED_COMMITMENT,
        "pump_instruction_verified": True,
    }
    return NormalizedSourceResult(
        source_name=SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.CLEAN_DATA,
        normalized_payload=MappingProxyType(
            {
                "tokens": [token],
                "commitment": FINALIZED_COMMITMENT,
                "transport_operation_count": 1,
            }
        ),
        status_code=200,
    )


def _validate_context(
    context: SourceAdapterContext,
    contract: SourceAdapterContract,
) -> None:
    if not context or not context.governor_approved:
        raise PermissionError("direct Pump execution requires Governor approval")
    if context.execution_path != GOVERNOR_ONLY_EXECUTION_PATH:
        raise PermissionError("direct Pump execution requires governed path")
    if context.request.source_name != SOURCE_NAME:
        raise ValueError("direct Pump source identity mismatch")
    if context.request.request_kind not in ALLOWED_REQUEST_KINDS:
        raise ValueError("direct Pump request kind mismatch")
    if context.request.request_kind not in contract.allowed_request_kinds:
        raise ValueError("direct Pump request kind is not registered")


def _failure(
    request_kind: str,
    failure_type: str,
    failure_message: str,
) -> NormalizedSourceResult:
    return NormalizedSourceResult(
        source_name=SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.FAILED,
        data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        failure_type=failure_type,
        failure_message=failure_message,
    )


def _rpc_post(
    rpc_url: str,
    method: str,
    params: list[Any],
    *,
    timeout_seconds: float,
) -> Mapping[str, Any]:
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    ).encode("utf-8")
    request = url_request.Request(
        rpc_url,
        data=body,
        headers=RPC_HEADERS,
        method="POST",
    )
    try:
        with url_request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read(RPC_BYTE_CEILING + 1)
            if len(raw) > RPC_BYTE_CEILING:
                return MappingProxyType(
                    {
                        "fixture_status": "failure",
                        "failure_type": "direct_pump_rpc_byte_ceiling",
                        "failure_message": "Solana RPC response exceeded byte ceiling",
                    }
                )
            decoded = json.loads(raw.decode("utf-8"))
            if not isinstance(decoded, Mapping):
                raise ValueError("Solana RPC returned non-object")
            return MappingProxyType(dict(decoded))
    except url_error.HTTPError as exc:
        status = int(exc.code)
        exc.close()
        return MappingProxyType(
            {
                "fixture_status": "failure",
                "failure_type": (
                    "direct_pump_rpc_rate_limited"
                    if status == 429
                    else "direct_pump_rpc_http_error"
                ),
                "failure_message": f"Solana RPC HTTP {status}",
            }
        )
    except (
        OSError,
        TimeoutError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        return MappingProxyType(
            {
                "fixture_status": "failure",
                "failure_type": "direct_pump_rpc_transport_or_shape_error",
                "failure_message": (
                    f"{type(exc).__name__}: Solana RPC transport/shape failure"
                ),
            }
        )


__all__ = [
    "SOURCE_NAME",
    "SIGNATURE_PAGE_REQUEST_KIND",
    "TRANSACTION_REQUEST_KIND",
    "FINALIZED_COMMITMENT",
    "SIGNATURE_PAGE_LIMIT",
    "MAX_TRANSACTION_LOOKUPS",
    "DirectPumpMigrationAdapter",
    "build_direct_pump_migration_adapter",
    "build_direct_pump_migration_transport",
    "normalize_direct_pump_migration_response",
]

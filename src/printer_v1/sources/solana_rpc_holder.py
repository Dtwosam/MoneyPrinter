"""Governed Solana RPC holder concentration fallback adapter.

Uses getTokenLargestAccounts + getTokenSupply (public Solana JSON-RPC calls)
to compute a deterministic holder concentration label when GoPlus does not
provide top-holder data.

No private key or paid API is involved. All operations are read-only.
All results go through Source Governor.
If the RPC is unavailable, the label stays HOLDER_CONCENTRATION_UNKNOWN.

Thresholds (deterministic, no scoring):
  top-10 share >= 80 %  → HOLDER_CONCENTRATION_EXTREME
  top-10 share >= 55 %  → HOLDER_CONCENTRATION_CONCENTRATED
  top-10 share <  55 %  → HOLDER_CONCENTRATION_HEALTHY
  any failure / missing  → HOLDER_CONCENTRATION_UNKNOWN
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any, Callable, Mapping
from urllib import error as url_error
from urllib import parse as url_parse
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


SOLANA_RPC_SOURCE_NAME = "solana_rpc"
SOLANA_PUBLIC_RPC_URL = "https://api.mainnet-beta.solana.com"
SOLANA_RPC_TIMEOUT_SECONDS = 10.0
SOLANA_RPC_PUBLIC_HEADERS = {
    "User-Agent": "PrinterV1/0.1 (+paper-only holder check)",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
SOLANA_RPC_RATE_LIMIT_FAILURE_TYPE = "solana_rpc_rate_limited"

HOLDER_CONCENTRATION_EXTREME_THRESHOLD = 80.0
HOLDER_CONCENTRATION_CONCENTRATED_THRESHOLD = 55.0

ALLOWED_REQUEST_KINDS = frozenset({"holder_concentration_reference"})


@dataclass(frozen=True)
class SolanaRpcHolderAdapterMetadata:
    source_name: str = SOLANA_RPC_SOURCE_NAME
    display_name: str = "Solana RPC Holder"
    enabled_by_default: bool = False
    requires_governor_context: bool = True
    supports_network_execution: bool = False
    fixture_transport_only: bool = True
    read_only: bool = True


class SolanaRpcHolderAdapter:
    """Solana RPC holder concentration adapter — read-only, disabled unless transport injected.

    Calls getTokenLargestAccounts + getTokenSupply for a mint address and returns
    a deterministic holder concentration label. No key operations.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
    ) -> None:
        self.metadata = SolanaRpcHolderAdapterMetadata()
        self.contract = build_solana_rpc_holder_adapter_contract()
        self.enabled = enabled
        self.transport = fixture_transport
        self.call_count = 0

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not self.enabled:
            raise PermissionError("Solana RPC holder adapter is disabled by default")
        if self.transport is None:
            raise PermissionError("Solana RPC holder adapter requires an explicit transport")
        _validate_context(context, SOLANA_RPC_SOURCE_NAME, self.contract)

        self.call_count += 1
        try:
            payload = self.transport(context)
        except Exception as exc:
            return _failure_result(
                context.request.request_kind, "solana_rpc_holder_transport_error", str(exc)
            )
        return normalize_solana_rpc_holder_response(payload, request_kind=context.request.request_kind)


def build_solana_rpc_holder_adapter_contract() -> SourceAdapterContract:
    contract = build_source_adapter_contract(SOLANA_RPC_SOURCE_NAME)
    if not validate_source_adapter_contract(contract):
        raise ValueError("Solana RPC holder contract violates Source Governor boundary")
    return contract


def build_solana_rpc_holder_adapter(
    *,
    enabled: bool = False,
    fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
) -> SolanaRpcHolderAdapter:
    return SolanaRpcHolderAdapter(enabled=enabled, fixture_transport=fixture_transport)


def fixture_success_transport(
    payload: Mapping[str, Any],
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType(dict(payload))

    return transport


def fixture_failure_transport(
    message: str = "Solana RPC holder fixture failure",
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType(
            {
                "fixture_status": "failure",
                "failure_type": "solana_rpc_holder_fixture_failure",
                "failure_message": message,
            }
        )

    return transport


def build_solana_rpc_holder_transport(
    token_mint: str,
    *,
    rpc_url: str = SOLANA_PUBLIC_RPC_URL,
    timeout_seconds: float = SOLANA_RPC_TIMEOUT_SECONDS,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """Return a real HTTP transport that fetches holder concentration from Solana RPC.

    Calls getTokenLargestAccounts and getTokenSupply — read-only, no key.
    """

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return _fetch_holder_data(token_mint, rpc_url=rpc_url, timeout_seconds=timeout_seconds)

    return transport


def redacted_solana_rpc_source(rpc_url: str | None) -> str:
    """Return host-only RPC source text for operator output.

    The full URL may contain query-string tokens for some free endpoints, so
    never surface path/query/fragment values in reports.
    """
    parsed = url_parse.urlparse(rpc_url or SOLANA_PUBLIC_RPC_URL)
    return parsed.hostname or "unknown_rpc_host"


def _rpc_post(
    rpc_url: str,
    method: str,
    params: list[Any],
    *,
    timeout_seconds: float,
) -> Mapping[str, Any]:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = url_request.Request(rpc_url, data=body, headers=SOLANA_RPC_PUBLIC_HEADERS, method="POST")
    try:
        with url_request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read(512_000)
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                return {
                    "fixture_status": "failure",
                    "failure_type": "solana_rpc_non_object_response",
                    "failure_message": f"RPC {method} returned non-object",
                    "rpc_method": method,
                    "underlying_operation_count": 1,
                }
            return data
    except url_error.HTTPError as exc:
        code = int(exc.code)
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        exc.close()
        # V2-9.6 eligibility split: 429 and temporary 5xx are transient and
        # backup-eligible; 4xx is a deterministic client error and is not.
        if code == 429:
            return {
                "fixture_status": "failure",
                "failure_type": SOLANA_RPC_RATE_LIMIT_FAILURE_TYPE,
                "failure_message": "Solana RPC HTTP 429 rate limit",
                "status_code": 429,
                "retry_after": retry_after,
                "rpc_method": method,
                "underlying_operation_count": 1,
            }
        if 500 <= code <= 599:
            return {
                "fixture_status": "failure",
                "failure_type": "solana_rpc_http_server_error",
                "failure_message": f"Solana RPC HTTP error {code}",
                "status_code": code,
                "retry_after": retry_after,
                "rpc_method": method,
                "underlying_operation_count": 1,
            }
        return {
            "fixture_status": "failure",
            "failure_type": "solana_rpc_http_client_error",
            "failure_message": f"Solana RPC HTTP error {code}",
            "status_code": code,
            "retry_after": retry_after,
            "rpc_method": method,
            "underlying_operation_count": 1,
        }
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        # Parser/decode defect — a payload problem, never backup-eligible.
        return {
            "fixture_status": "failure",
            "failure_type": "solana_rpc_malformed_response",
            "failure_message": str(exc),
            "rpc_method": method,
            "underlying_operation_count": 1,
        }
    except (OSError, TimeoutError) as exc:
        # TLS/connection interruption or connect/read timeout. Transient and
        # backup-eligible.
        return {
            "fixture_status": "failure",
            "failure_type": "solana_rpc_transport_failure",
            "failure_message": str(exc),
            "rpc_method": method,
            "underlying_operation_count": 1,
        }


def _fetch_holder_data(
    token_mint: str,
    *,
    rpc_url: str = SOLANA_PUBLIC_RPC_URL,
    timeout_seconds: float = SOLANA_RPC_TIMEOUT_SECONDS,
) -> Mapping[str, Any]:
    largest_resp = _rpc_post(
        rpc_url,
        "getTokenLargestAccounts",
        [token_mint, {"commitment": "finalized"}],
        timeout_seconds=timeout_seconds,
    )
    if largest_resp.get("fixture_status") == "failure":
        return MappingProxyType({**dict(largest_resp), "commitment": "finalized"})

    supply_resp = _rpc_post(
        rpc_url,
        "getTokenSupply",
        [token_mint, {"commitment": "finalized"}],
        timeout_seconds=timeout_seconds,
    )
    if supply_resp.get("fixture_status") == "failure":
        return MappingProxyType({
            **dict(supply_resp),
            "commitment": "finalized",
            "underlying_operation_count": 2,
        })

    return MappingProxyType(
        {
            "token_mint": token_mint,
            "largest_accounts_result": largest_resp,
            "token_supply_result": supply_resp,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "rpc_method": "getTokenLargestAccounts+getTokenSupply",
            "commitment": "finalized",
            "context_slot": max(
                int(largest_resp.get("result", {}).get("context", {}).get("slot") or 0),
                int(supply_resp.get("result", {}).get("context", {}).get("slot") or 0),
            ) or None,
            "underlying_operation_count": 2,
        }
    )


def _compute_holder_concentration(
    largest_accounts_result: Mapping[str, Any],
    token_supply_result: Mapping[str, Any],
    token_mint: str,
) -> str:
    """Compute deterministic holder concentration label from RPC results."""
    supply_value = (
        token_supply_result.get("result", {})
        .get("value", {})
        .get("amount")
    )
    if supply_value is None:
        return "HOLDER_CONCENTRATION_UNKNOWN"
    try:
        total_supply = float(supply_value)
    except (TypeError, ValueError):
        return "HOLDER_CONCENTRATION_UNKNOWN"
    if total_supply <= 0:
        return "HOLDER_CONCENTRATION_UNKNOWN"

    accounts = (
        largest_accounts_result.get("result", {})
        .get("value") or []
    )
    if not isinstance(accounts, list) or not accounts:
        return "HOLDER_CONCENTRATION_UNKNOWN"

    top_accounts = accounts[:10]
    top_total = 0.0
    for acct in top_accounts:
        if not isinstance(acct, dict):
            return "HOLDER_CONCENTRATION_UNKNOWN"
        amt = acct.get("amount")
        if amt is None:
            return "HOLDER_CONCENTRATION_UNKNOWN"
        try:
            top_total += float(amt)
        except (TypeError, ValueError):
            return "HOLDER_CONCENTRATION_UNKNOWN"

    top_pct = (top_total / total_supply) * 100.0
    if top_pct >= HOLDER_CONCENTRATION_EXTREME_THRESHOLD:
        return "HOLDER_CONCENTRATION_EXTREME"
    if top_pct >= HOLDER_CONCENTRATION_CONCENTRATED_THRESHOLD:
        return "HOLDER_CONCENTRATION_CONCENTRATED"
    return "HOLDER_CONCENTRATION_HEALTHY"


def normalize_solana_rpc_holder_response(
    payload: Mapping[str, Any],
    *,
    request_kind: str,
) -> NormalizedSourceResult:
    if request_kind not in ALLOWED_REQUEST_KINDS:
        return _failure_result(
            request_kind,
            "solana_rpc_holder_request_kind_not_allowed",
            "Solana RPC holder request kind is not allowed",
        )

    fixture_status = payload.get("fixture_status")
    if fixture_status == "failure":
        return _failure_result(
            request_kind,
            str(payload.get("failure_type") or "solana_rpc_holder_fixture_failure"),
            str(payload.get("failure_message") or "Solana RPC holder fixture failure"),
            payload=payload,
        )

    # If we have a pre-normalized holder_concentration_label (from a test fixture),
    # pass it through directly.
    if "holder_concentration_label" in payload:
        label = str(payload["holder_concentration_label"])
        normalized = {
            "holder_concentration_label": label,
            "token_mint": str(payload.get("token_mint") or ""),
            "source_name": SOLANA_RPC_SOURCE_NAME,
            "request_kind": request_kind,
            "captured_at": str(payload.get("captured_at") or datetime.now(timezone.utc).isoformat()),
            "paper_only_context": True,
            "rpc_method": str(payload.get("rpc_method") or "getTokenLargestAccounts+getTokenSupply"),
            "commitment": str(payload.get("commitment") or "finalized"),
            "context_slot": payload.get("context_slot"),
            "underlying_operation_count": int(payload.get("underlying_operation_count") or 2),
        }
        stale = bool(payload.get("fixture_stale"))
        return NormalizedSourceResult(
            source_name=SOLANA_RPC_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.STALE if stale else SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.STALE_DATA if stale else DataQualityLabel.CLEAN_DATA,
            normalized_payload=MappingProxyType(normalized),
        )

    token_mint = str(payload.get("token_mint") or "")
    largest_accounts_result = payload.get("largest_accounts_result")
    token_supply_result = payload.get("token_supply_result")

    if not isinstance(largest_accounts_result, Mapping) or not isinstance(token_supply_result, Mapping):
        return _failure_result(
            request_kind,
            "solana_rpc_holder_missing_rpc_results",
            "Solana RPC holder response missing RPC result data",
        )

    if largest_accounts_result.get("error") or token_supply_result.get("error"):
        return _failure_result(
            request_kind,
            "solana_rpc_holder_rpc_error",
            "Solana RPC returned error in holder concentration response",
        )

    holder_label = _compute_holder_concentration(
        largest_accounts_result, token_supply_result, token_mint
    )

    normalized = {
        "holder_concentration_label": holder_label,
        "token_mint": token_mint,
        "source_name": SOLANA_RPC_SOURCE_NAME,
        "request_kind": request_kind,
        "captured_at": str(payload.get("captured_at") or datetime.now(timezone.utc).isoformat()),
        "paper_only_context": True,
        "rpc_method": str(payload.get("rpc_method") or "getTokenLargestAccounts+getTokenSupply"),
        "commitment": str(payload.get("commitment") or "finalized"),
        "context_slot": payload.get("context_slot"),
        "underlying_operation_count": int(payload.get("underlying_operation_count") or 2),
    }

    stale = bool(payload.get("fixture_stale"))
    return NormalizedSourceResult(
        source_name=SOLANA_RPC_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.STALE if stale else SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.STALE_DATA if stale else DataQualityLabel.CLEAN_DATA,
        normalized_payload=MappingProxyType(normalized),
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
    *,
    payload: Mapping[str, Any] | None = None,
) -> NormalizedSourceResult:
    details = dict(payload or {})
    retry_after_at = None
    retry_after = details.get("retry_after")
    if retry_after is not None:
        try:
            retry_after_at = (
                datetime.now(timezone.utc) + timedelta(seconds=int(retry_after))
            ).isoformat()
        except (TypeError, ValueError):
            retry_after_at = None
    return NormalizedSourceResult(
        source_name=SOLANA_RPC_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.FAILED,
        data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        failure_type=failure_type,
        failure_message=failure_message,
        status_code=details.get("status_code"),
        retry_after_at=retry_after_at,
        normalized_payload=MappingProxyType(details),
    )

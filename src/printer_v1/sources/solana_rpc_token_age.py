"""Governed Solana RPC T3 token-age enrichment adapter.

Derives token creation time from on-chain mint-initialization evidence using a
bounded read-only sequence: getAccountInfo → getSignaturesForAddress (≤3 pages)
→ getTransaction (≤3 calls) → optional getBlockTime (≤1 call).

Budget: ≤ 8 RPC requests per token, 10s timeout, 0 retries.
Request kind: mint_creation_time_reference
Source: solana_rpc

Evidence is accepted ONLY when:
  - Mint account confirmed (SPL Token or Token-2022 program owner)
  - Signature history end reachable within page cap (full history available)
  - initializeMint or initializeMint2 instruction found targeting the exact mint
  - Valid, non-future block time derived

All failures leave token_created_at, token_age_seconds, and tier unset (fail-closed).
No fallback to pair age, captured_at, migration time, or OBSERVED_LIVE_LAUNCH.
"""

from __future__ import annotations

import base64
import json
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
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
SOLANA_RPC_TOKEN_AGE_REQUEST_KIND = "mint_creation_time_reference"
SOLANA_PUBLIC_RPC_URL = "https://api.mainnet-beta.solana.com"

_T3_MAX_REQUESTS_PER_TOKEN = 8
_T3_MAX_SIGNATURE_PAGES = 3
_T3_SIGNATURES_PER_PAGE = 20
_T3_MAX_INIT_CANDIDATES = 3
_T3_MAX_TRANSACTION_CALLS = 3
_T3_MAX_BLOCK_TIME_CALLS = 1
_T3_RPC_TIMEOUT_SECONDS = 10.0

_SPL_TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
_TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
_ALLOWED_TOKEN_PROGRAMS = frozenset({_SPL_TOKEN_PROGRAM_ID, _TOKEN_2022_PROGRAM_ID})
_INIT_MINT_INSTRUCTION_TYPES = frozenset({"initializeMint", "initializeMint2"})
_SPL_TOKEN_MINT_SIZE = 82            # Mint::LEN — base SPL Token Mint fixed size
_SPL_MINT_IS_INITIALIZED_OFFSET = 45  # is_initialized bool offset in the 82-byte Mint layout
# SPL Token-2022 extended-mint layout (source: solana-program-library,
# token/program-2022/src/extension/mod.rs, constants BASE_ACCOUNT_LENGTH and
# BASE_ACCOUNT_AND_TYPE_LENGTH):
#   [0..82]   Base SPL Token Mint (Mint::LEN = 82 bytes)
#   [82..165] Padding region (Account::LEN - Mint::LEN = 83 zero bytes)
#             Aligns AccountType to BASE_ACCOUNT_LENGTH for backward compatibility
#   [165]     AccountType discriminant (BASE_ACCOUNT_LENGTH; 1 = Mint, 2 = Account)
#   [166..]   Extension TLV entries: 2-byte LE type + 2-byte LE length + data bytes
_SPL_TOKEN_ACCOUNT_SIZE = 165           # Account::LEN / BASE_ACCOUNT_LENGTH in Token-2022
_TOKEN_2022_ACCOUNT_TYPE_OFFSET = _SPL_TOKEN_ACCOUNT_SIZE       # = 165 — AccountType position
_TOKEN_2022_EXTENSION_DATA_START = _SPL_TOKEN_ACCOUNT_SIZE + 1  # = 166 — TLV region start
_TOKEN_2022_ACCOUNT_TYPE_MINT = 1       # AccountType::Mint discriminant value
_TOKEN_2022_EXTENSION_TLV_HEADER_SIZE = 4  # TLV entry header: 2-byte type + 2-byte length

_T3_ALLOWED_REQUEST_KINDS = frozenset({SOLANA_RPC_TOKEN_AGE_REQUEST_KIND})

_RPC_HEADERS = {
    "User-Agent": "PrinterV1/0.1 (+paper-only T3 mint-age reference)",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


@dataclass(frozen=True)
class SolanaRpcTokenAgeAdapterMetadata:
    source_name: str = SOLANA_RPC_SOURCE_NAME
    display_name: str = "Solana RPC Token Age"
    enabled_by_default: bool = False
    requires_governor_context: bool = True
    supports_network_execution: bool = True   # live-capable; bounded transport injected for proof
    fixture_transport_only: bool = False       # live transport defined; fixture used until proof lane
    read_only: bool = True


class SolanaRpcTokenAgeAdapter:
    """Solana RPC T3 token-age enrichment adapter — governed, read-only, fail-closed."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
    ) -> None:
        self.metadata = SolanaRpcTokenAgeAdapterMetadata()
        self.contract = build_solana_rpc_token_age_adapter_contract()
        self.enabled = enabled
        self.transport = fixture_transport
        self.call_count = 0

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not self.enabled:
            raise PermissionError("Solana RPC token-age adapter is disabled by default")
        if self.transport is None:
            raise PermissionError("Solana RPC token-age adapter requires an explicit transport")
        _validate_t3_context(context, self.contract)
        self.call_count += 1
        try:
            payload = self.transport(context)
        except Exception as exc:
            return _t3_failure_result(
                context.request.request_kind,
                "solana_rpc_token_age_transport_error",
                str(exc),
            )
        return normalize_solana_rpc_token_age_response(
            payload, request_kind=context.request.request_kind
        )


def build_solana_rpc_token_age_adapter_contract() -> SourceAdapterContract:
    contract = build_source_adapter_contract(SOLANA_RPC_SOURCE_NAME)
    if not validate_source_adapter_contract(contract):
        raise ValueError("Solana RPC token-age contract violates Source Governor boundary")
    return contract


def build_solana_rpc_token_age_adapter(
    *,
    enabled: bool = False,
    fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
) -> SolanaRpcTokenAgeAdapter:
    return SolanaRpcTokenAgeAdapter(enabled=enabled, fixture_transport=fixture_transport)


def fixture_t3_success_transport(
    payload: Mapping[str, Any],
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """Return a transport that always succeeds with a pre-built T3 evidence payload."""
    frozen = MappingProxyType(dict(payload))

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return frozen

    return transport


def fixture_t3_failure_transport(
    failure_type: str,
    failure_message: str = "T3 fixture failure",
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """Return a transport that always returns a pre-built T3 failure payload."""
    frozen = MappingProxyType({
        "fixture_status": "failure",
        "failure_type": failure_type,
        "failure_message": failure_message,
    })

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return frozen

    return transport


def build_solana_rpc_token_age_transport(
    token_mint: str,
    captured_at: str,
    *,
    rpc_url: str = SOLANA_PUBLIC_RPC_URL,
    timeout_seconds: float = _T3_RPC_TIMEOUT_SECONDS,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """Return a live HTTP transport that executes the full T3 evidence pipeline.

    Not used in V2-2AK fixture proof. Defined for V2-2AL bounded live proof.
    All RPC calls are read-only; no private key, no wallet, no transaction send.
    """

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return _fetch_token_age_data(
            token_mint, captured_at, rpc_url=rpc_url, timeout_seconds=timeout_seconds
        )

    return transport


def redacted_rpc_host(rpc_url: str | None) -> str:
    parsed = url_parse.urlparse(rpc_url or SOLANA_PUBLIC_RPC_URL)
    return parsed.hostname or "unknown_rpc_host"


def normalize_solana_rpc_token_age_response(
    payload: Mapping[str, Any],
    *,
    request_kind: str,
) -> NormalizedSourceResult:
    """Interpret a T3 adapter payload (success or failure) as a NormalizedSourceResult."""
    if request_kind not in _T3_ALLOWED_REQUEST_KINDS:
        return _t3_failure_result(
            request_kind,
            "solana_rpc_token_age_request_kind_not_allowed",
            "T3 adapter only accepts mint_creation_time_reference",
        )

    # Explicit failure path (fixture_t3_failure_transport or live pipeline failure)
    if payload.get("fixture_status") == "failure":
        return _t3_failure_result(
            request_kind,
            str(payload.get("failure_type") or "solana_rpc_token_age_unknown_failure"),
            str(payload.get("failure_message") or "T3 failure with no message"),
        )

    # Success path requires t3_status="success"
    if payload.get("t3_status") != "success":
        return _t3_failure_result(
            request_kind,
            "solana_rpc_token_age_malformed_response",
            "T3 payload has no t3_status=success and no fixture_status=failure",
        )

    token_created_at = payload.get("token_created_at")
    token_age_seconds = payload.get("token_age_seconds")
    t3_requested_mint = payload.get("t3_requested_mint")

    if not token_created_at or not isinstance(token_created_at, str):
        return _t3_failure_result(
            request_kind,
            "solana_rpc_token_age_malformed_response",
            "T3 success payload missing or invalid token_created_at",
        )
    if token_age_seconds is None or float(token_age_seconds) < 0:
        return _t3_failure_result(
            request_kind,
            "solana_rpc_token_age_malformed_response",
            "T3 success payload missing or negative token_age_seconds",
        )
    if not t3_requested_mint:
        return _t3_failure_result(
            request_kind,
            "solana_rpc_token_age_malformed_response",
            "T3 success payload missing t3_requested_mint",
        )

    captured_at_val = str(payload.get("captured_at") or datetime.now(timezone.utc).isoformat())
    normalized: dict[str, Any] = {
        "token_mint": str(t3_requested_mint),
        "token_created_at": str(token_created_at),
        "token_age_seconds": float(token_age_seconds),
        "token_age_evidence_tier": "T3",
        "source_name": SOLANA_RPC_SOURCE_NAME,
        "request_kind": SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
        "captured_at": captured_at_val,
        "paper_only_context": True,
        # Provenance fields (15 t3_* fields from design Section 9.1)
        "t3_requested_mint": str(payload.get("t3_requested_mint") or ""),
        "t3_rpc_host_redacted": str(payload.get("t3_rpc_host_redacted") or ""),
        "t3_rpc_methods_attempted": list(payload.get("t3_rpc_methods_attempted") or []),
        "t3_request_ids": list(payload.get("t3_request_ids") or []),
        "t3_pages_fetched": payload.get("t3_pages_fetched"),
        "t3_signatures_inspected": payload.get("t3_signatures_inspected"),
        "t3_accepted_signature": payload.get("t3_accepted_signature"),
        "t3_accepted_slot": payload.get("t3_accepted_slot"),
        "t3_block_time_raw": payload.get("t3_block_time_raw"),
        "t3_block_time_source": payload.get("t3_block_time_source"),
        "t3_instruction_type": payload.get("t3_instruction_type"),
        "t3_token_program": payload.get("t3_token_program"),
        "t3_derived_token_created_at": str(token_created_at),
        "t3_derived_token_age_seconds": float(token_age_seconds),
        "t3_captured_at": captured_at_val,
    }

    return NormalizedSourceResult(
        source_name=SOLANA_RPC_SOURCE_NAME,
        request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
        source_status=SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.CLEAN_DATA,
        normalized_payload=MappingProxyType(normalized),
    )


# ---------------------------------------------------------------------------
# Live transport pipeline (not executed in V2-2AK fixture proof)
# ---------------------------------------------------------------------------

def _rpc_post(
    rpc_url: str,
    method: str,
    params: list[Any],
    *,
    timeout_seconds: float,
    request_id: int = 1,
) -> Mapping[str, Any]:
    body = json.dumps(
        {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    ).encode()
    req = url_request.Request(rpc_url, data=body, headers=_RPC_HEADERS, method="POST")
    try:
        with url_request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read(1_048_576)
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                return {
                    "fixture_status": "failure",
                    "failure_type": "solana_rpc_token_age_malformed_response",
                    "failure_message": f"RPC {method} returned non-object",
                }
            return data
    except url_error.HTTPError as exc:
        exc.close()
        if exc.code == 429:
            return {
                "fixture_status": "failure",
                "failure_type": "solana_rpc_token_age_rate_limited",
                "failure_message": "Solana RPC HTTP 429 rate limit",
            }
        return {
            "fixture_status": "failure",
            "failure_type": "solana_rpc_token_age_transport_error",
            "failure_message": f"Solana RPC HTTP error {exc.code}",
        }
    except (OSError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {
            "fixture_status": "failure",
            "failure_type": "solana_rpc_token_age_transport_error",
            "failure_message": str(exc),
        }


def _decode_spl_token_base_mint_state(raw_bytes: bytes) -> tuple[bool, str | None]:
    """Validate the 82-byte SPL Token base Mint layout.

    Checks minimum length and the is_initialized flag (byte 45).
    Returns (valid, error_message_or_None).
    """
    if len(raw_bytes) < _SPL_TOKEN_MINT_SIZE:
        return False, f"Too short for base Mint layout: {len(raw_bytes)} < {_SPL_TOKEN_MINT_SIZE}"
    is_initialized = raw_bytes[_SPL_MINT_IS_INITIALIZED_OFFSET]
    if is_initialized != 1:
        return False, f"Mint not initialized: is_initialized byte = {is_initialized!r}"
    return True, None


def _decode_token_2022_mint_state(raw_bytes: bytes) -> tuple[bool, str | None]:
    """Validate a Token-2022 extended mint account.

    Authoritative layout (solana-program-library token/program-2022/src/extension/mod.rs,
    constants BASE_ACCOUNT_LENGTH = Account::LEN = 165, BASE_ACCOUNT_AND_TYPE_LENGTH = 166):
      [0..82]   Base SPL Token Mint (Mint::LEN = 82 bytes, same fields as SPL Token)
      [82..165] Padding region (83 zero bytes = Account::LEN - Mint::LEN)
      [165]     AccountType discriminant (must be 1 = Mint; stored at BASE_ACCOUNT_LENGTH)
      [166..]   Extension TLV entries: 2-byte LE type + 2-byte LE length + data bytes

    Minimum valid Token-2022 extended mint: 166 bytes (= BASE_ACCOUNT_AND_TYPE_LENGTH).
    Returns (valid, error_message_or_None).
    """
    # Step 1: validate 82-byte base SPL Token Mint (is_initialized at offset 45)
    ok, err = _decode_spl_token_base_mint_state(raw_bytes)
    if not ok:
        return False, err

    # Step 2: must have at least 166 bytes (base + padding + AccountType)
    if len(raw_bytes) < _TOKEN_2022_EXTENSION_DATA_START:
        return False, (
            f"Token-2022 extended mint too short: {len(raw_bytes)} bytes; "
            f"need ≥ {_TOKEN_2022_EXTENSION_DATA_START} "
            f"(base {_SPL_TOKEN_MINT_SIZE} + padding {_TOKEN_2022_ACCOUNT_TYPE_OFFSET - _SPL_TOKEN_MINT_SIZE} + AccountType 1)"
        )

    # Step 3: padding region [82..165] must be all zero bytes
    padding = raw_bytes[_SPL_TOKEN_MINT_SIZE:_TOKEN_2022_ACCOUNT_TYPE_OFFSET]
    if any(b != 0 for b in padding):
        first_bad = next(
            _SPL_TOKEN_MINT_SIZE + i for i, b in enumerate(padding) if b != 0
        )
        return False, (
            f"Token-2022 mint padding region "
            f"[{_SPL_TOKEN_MINT_SIZE}..{_TOKEN_2022_ACCOUNT_TYPE_OFFSET}] "
            f"has non-zero byte at offset {first_bad}"
        )

    # Step 4: AccountType at offset 165 must be 1 (Mint)
    account_type = raw_bytes[_TOKEN_2022_ACCOUNT_TYPE_OFFSET]
    if account_type != _TOKEN_2022_ACCOUNT_TYPE_MINT:
        return False, (
            f"Token-2022 AccountType byte {account_type!r} at offset "
            f"{_TOKEN_2022_ACCOUNT_TYPE_OFFSET} is not Mint "
            f"(expected {_TOKEN_2022_ACCOUNT_TYPE_MINT})"
        )

    # Step 5: walk TLV extension region starting at 166
    ext_offset = _TOKEN_2022_EXTENSION_DATA_START
    while ext_offset < len(raw_bytes):
        remaining = len(raw_bytes) - ext_offset
        if remaining < _TOKEN_2022_EXTENSION_TLV_HEADER_SIZE:
            # Trailing zero-padding is acceptable after the last valid TLV entry
            if all(b == 0 for b in raw_bytes[ext_offset:]):
                break
            return False, (
                f"Partial TLV header at offset {ext_offset}: "
                f"{remaining} bytes remaining (need ≥ {_TOKEN_2022_EXTENSION_TLV_HEADER_SIZE})"
            )
        ext_type, ext_len = struct.unpack_from("<HH", raw_bytes, ext_offset)
        ext_data_start = ext_offset + _TOKEN_2022_EXTENSION_TLV_HEADER_SIZE
        if ext_data_start + ext_len > len(raw_bytes):
            return False, (
                f"TLV extension type={ext_type} at offset {ext_offset}: "
                f"claimed length {ext_len} overflows buffer end ({len(raw_bytes)})"
            )
        ext_offset = ext_data_start + ext_len

    return True, None


def _is_init_mint_instruction(
    instruction: Mapping[str, Any],
    token_mint: str,
) -> tuple[bool, str | None, str | None]:
    """Check if a jsonParsed instruction is initializeMint/initializeMint2 for the exact mint.

    Returns (matched, instruction_type, token_program_label) or (False, None, None).
    """
    program = instruction.get("program") or instruction.get("programId") or ""
    parsed = instruction.get("parsed") or {}
    if not isinstance(parsed, dict):
        return False, None, None
    inst_type = parsed.get("type") or ""
    if inst_type not in _INIT_MINT_INSTRUCTION_TYPES:
        return False, None, None
    info = parsed.get("info") or {}
    mint_in_inst = info.get("mint") or info.get("account") or ""
    if mint_in_inst != token_mint:
        return False, None, None
    is_token_2022 = program in (_TOKEN_2022_PROGRAM_ID, "spl-token-2022")
    prog_label = "token_2022" if is_token_2022 else "spl_token"
    return True, inst_type, prog_label


def _fetch_token_age_data(
    token_mint: str,
    captured_at: str,
    *,
    rpc_url: str = SOLANA_PUBLIC_RPC_URL,
    timeout_seconds: float = _T3_RPC_TIMEOUT_SECONDS,
) -> Mapping[str, Any]:
    """Execute the full T3 multi-step RPC pipeline.

    Not called in V2-2AK fixture tests. Defined for V2-2AL bounded live proof.
    """
    request_count = 0
    request_ids: list[int] = []
    methods_attempted: list[str] = []

    def _call(method: str, params: list[Any]) -> Mapping[str, Any]:
        nonlocal request_count
        if request_count >= _T3_MAX_REQUESTS_PER_TOKEN:
            return {
                "fixture_status": "failure",
                "failure_type": "solana_rpc_token_age_budget_exhausted",
                "failure_message": f"T3 budget exhausted after {request_count} calls",
            }
        request_count += 1
        rid = request_count
        request_ids.append(rid)
        methods_attempted.append(method)
        return _rpc_post(rpc_url, method, params, timeout_seconds=timeout_seconds, request_id=rid)

    host_redacted = redacted_rpc_host(rpc_url)

    # Step 1: Validate mint account
    account_resp = _call(
        "getAccountInfo",
        [token_mint, {"encoding": "base64", "commitment": "confirmed"}],
    )
    if account_resp.get("fixture_status") == "failure":
        return MappingProxyType(dict(account_resp))
    if account_resp.get("error"):
        return MappingProxyType({
            "fixture_status": "failure",
            "failure_type": "solana_rpc_token_age_transport_error",
            "failure_message": str(account_resp.get("error")),
        })

    result_value = (account_resp.get("result") or {}).get("value")
    if not result_value:
        return MappingProxyType({
            "fixture_status": "failure",
            "failure_type": "solana_rpc_token_age_account_not_found",
            "failure_message": f"Mint account not found on-chain: {token_mint}",
        })

    owner = result_value.get("owner")
    if owner not in _ALLOWED_TOKEN_PROGRAMS:
        return MappingProxyType({
            "fixture_status": "failure",
            "failure_type": "solana_rpc_token_age_not_a_mint",
            "failure_message": f"Account owner {owner!r} is not SPL Token or Token-2022 program",
        })

    data_field = result_value.get("data")
    if not isinstance(data_field, list) or not data_field:
        return MappingProxyType({
            "fixture_status": "failure",
            "failure_type": "solana_rpc_token_age_not_a_mint",
            "failure_message": "Account data missing or not in expected base64 list format",
        })
    try:
        raw_bytes = base64.b64decode(data_field[0])
    except Exception as exc:
        return MappingProxyType({
            "fixture_status": "failure",
            "failure_type": "solana_rpc_token_age_not_a_mint",
            "failure_message": f"Mint data base64 decode failed: {exc}",
        })
    if owner == _SPL_TOKEN_PROGRAM_ID:
        if len(raw_bytes) != _SPL_TOKEN_MINT_SIZE:
            return MappingProxyType({
                "fixture_status": "failure",
                "failure_type": "solana_rpc_token_age_not_a_mint",
                "failure_message": f"SPL Token Mint must be exactly {_SPL_TOKEN_MINT_SIZE} bytes",
            })
        spl_valid, spl_err = _decode_spl_token_base_mint_state(raw_bytes)
        if not spl_valid:
            return MappingProxyType({
                "fixture_status": "failure",
                "failure_type": "solana_rpc_token_age_not_a_mint",
                "failure_message": f"SPL Token mint-state decode failed: {spl_err}",
            })
    else:
        # Token-2022: validate AccountType byte and TLV extension structure
        t22_valid, t22_err = _decode_token_2022_mint_state(raw_bytes)
        if not t22_valid:
            return MappingProxyType({
                "fixture_status": "failure",
                "failure_type": "solana_rpc_token_age_not_a_mint",
                "failure_message": f"Token-2022 mint-state decode failed: {t22_err}",
            })

    # Step 2: Walk signature history to oldest available page
    pages_fetched = 0
    before_cursor: str | None = None
    oldest_page: list[Any] = []
    reached_end = False

    while pages_fetched < _T3_MAX_SIGNATURE_PAGES:
        sig_params: list[Any] = [
            token_mint,
            {"limit": _T3_SIGNATURES_PER_PAGE, "commitment": "confirmed"},
        ]
        if before_cursor:
            sig_params[1]["before"] = before_cursor

        sig_resp = _call("getSignaturesForAddress", sig_params)
        if sig_resp.get("fixture_status") == "failure":
            return MappingProxyType(dict(sig_resp))
        if sig_resp.get("error"):
            return MappingProxyType({
                "fixture_status": "failure",
                "failure_type": "solana_rpc_token_age_transport_error",
                "failure_message": str(sig_resp.get("error")),
            })

        sig_list = sig_resp.get("result") or []
        pages_fetched += 1

        if not sig_list:
            if pages_fetched == 1:
                return MappingProxyType({
                    "fixture_status": "failure",
                    "failure_type": "solana_rpc_token_age_no_signatures",
                    "failure_message": f"No signature history for mint: {token_mint}",
                })
            reached_end = True
            break

        oldest_page = list(sig_list)
        if len(sig_list) < _T3_SIGNATURES_PER_PAGE:
            reached_end = True
            break
        before_cursor = (sig_list[-1] or {}).get("signature") or ""
        if not before_cursor:
            break

    if not reached_end:
        return MappingProxyType({
            "fixture_status": "failure",
            "failure_type": "solana_rpc_token_age_page_cap_exhausted",
            "failure_message": (
                f"Signature page cap ({_T3_MAX_SIGNATURE_PAGES}) exhausted before "
                "reaching mint history start"
            ),
        })

    # Take up to _T3_MAX_INIT_CANDIDATES from the oldest end of the page
    raw_candidates = [
        row for row in reversed(oldest_page[-_T3_MAX_INIT_CANDIDATES:])
        if (row or {}).get("signature") and not (row or {}).get("err")
    ]
    if not raw_candidates:
        return MappingProxyType({
            "fixture_status": "failure",
            "failure_type": "solana_rpc_token_age_no_signatures",
            "failure_message": "No successful candidate signatures in oldest page",
        })

    # Step 3: Inspect candidate transactions
    tx_calls = 0
    block_time_calls = 0  # enforce _T3_MAX_BLOCK_TIME_CALLS directly
    found_sig: str | None = None
    found_slot: int | None = None
    found_block_time: int | None = None
    found_inst_type: str | None = None
    found_prog_label: str | None = None
    block_time_source: str | None = None

    for sig_row in raw_candidates:
        if tx_calls >= _T3_MAX_TRANSACTION_CALLS:
            break
        sig = (sig_row or {}).get("signature") or ""
        if not sig:
            continue

        tx_resp = _call(
            "getTransaction",
            [
                sig,
                {
                    "encoding": "jsonParsed",
                    "commitment": "confirmed",
                    "maxSupportedTransactionVersion": 0,
                },
            ],
        )
        tx_calls += 1

        if tx_resp.get("fixture_status") == "failure":
            return MappingProxyType(dict(tx_resp))

        tx_result = tx_resp.get("result")
        if tx_result is None:
            continue

        meta_err = (tx_result.get("meta") or {}).get("err")
        if meta_err is not None:
            continue

        msg = (tx_result.get("transaction") or {}).get("message") or {}
        instructions = msg.get("instructions") or []
        matched = False
        for inst in instructions:
            ok, inst_type, prog_label = _is_init_mint_instruction(inst, token_mint)
            if ok:
                found_inst_type = inst_type
                found_prog_label = prog_label
                matched = True
                break
        if not matched:
            continue

        block_time = tx_result.get("blockTime")
        slot = tx_result.get("slot")
        if block_time is not None and int(block_time) > 0:
            found_sig = sig
            found_slot = slot
            found_block_time = int(block_time)
            block_time_source = "getTransaction"
            break

        # blockTime null — getBlockTime fallback, capped at _T3_MAX_BLOCK_TIME_CALLS
        if slot is not None and block_time_calls < _T3_MAX_BLOCK_TIME_CALLS:
            bt_resp = _call("getBlockTime", [int(slot)])
            block_time_calls += 1
            if bt_resp.get("fixture_status") == "failure":
                return MappingProxyType(dict(bt_resp))
            bt = bt_resp.get("result")
            if bt is not None and int(bt) > 0:
                found_sig = sig
                found_slot = slot
                found_block_time = int(bt)
                block_time_source = "getBlockTime"
                break

    if found_block_time is None or found_sig is None:
        return MappingProxyType({
            "fixture_status": "failure",
            "failure_type": "solana_rpc_token_age_no_init_instruction",
            "failure_message": (
                "No successful initializeMint/initializeMint2 with valid block time found"
            ),
        })

    # Derive timestamps and validate non-future
    try:
        captured_dt = datetime.fromisoformat(
            captured_at.replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        token_created_dt = datetime.fromtimestamp(found_block_time, tz=timezone.utc)
    except Exception as exc:
        return MappingProxyType({
            "fixture_status": "failure",
            "failure_type": "solana_rpc_token_age_malformed_response",
            "failure_message": f"Timestamp derivation failed: {exc}",
        })

    if token_created_dt > captured_dt:
        return MappingProxyType({
            "fixture_status": "failure",
            "failure_type": "solana_rpc_token_age_future_block_time",
            "failure_message": (
                f"Block time {found_block_time} is in the future relative to captured_at"
            ),
        })

    age_seconds = (captured_dt - token_created_dt).total_seconds()
    token_created_at_iso = token_created_dt.isoformat()

    return MappingProxyType({
        "t3_status": "success",
        "token_mint": token_mint,
        "captured_at": captured_at,
        "token_created_at": token_created_at_iso,
        "token_age_seconds": age_seconds,
        "token_age_evidence_tier": "T3",
        "t3_requested_mint": token_mint,
        "t3_rpc_host_redacted": host_redacted,
        "t3_rpc_methods_attempted": list(methods_attempted),
        "t3_request_ids": list(request_ids),
        "t3_pages_fetched": pages_fetched,
        "t3_signatures_inspected": tx_calls,
        "t3_accepted_signature": found_sig,
        "t3_accepted_slot": found_slot,
        "t3_block_time_raw": found_block_time,
        "t3_block_time_source": block_time_source,
        "t3_instruction_type": found_inst_type,
        "t3_token_program": found_prog_label,
        "t3_derived_token_created_at": token_created_at_iso,
        "t3_derived_token_age_seconds": age_seconds,
        "t3_captured_at": captured_at,
    })


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_t3_context(
    context: SourceAdapterContext,
    contract: SourceAdapterContract,
) -> None:
    if not context or not context.governor_approved:
        raise PermissionError("T3 adapter execution requires Source Governor approval")
    if context.execution_path != GOVERNOR_ONLY_EXECUTION_PATH:
        raise PermissionError("T3 adapter execution requires governed recording path")
    if context.request.source_name != SOLANA_RPC_SOURCE_NAME:
        raise ValueError("T3 source request source_name does not match adapter")
    if context.request.request_kind not in _T3_ALLOWED_REQUEST_KINDS:
        raise ValueError(
            f"T3 adapter only accepts {_T3_ALLOWED_REQUEST_KINDS}, "
            f"got {context.request.request_kind!r}"
        )
    if context.request.request_kind not in contract.allowed_request_kinds:
        raise ValueError("T3 request kind not in adapter contract")


def _t3_failure_result(
    request_kind: str,
    failure_type: str,
    failure_message: str,
) -> NormalizedSourceResult:
    return NormalizedSourceResult(
        source_name=SOLANA_RPC_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.FAILED,
        data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        failure_type=failure_type,
        failure_message=failure_message,
    )

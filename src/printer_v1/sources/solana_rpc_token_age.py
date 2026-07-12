"""Governed Solana RPC T3 token-age enrichment adapter.

Derives token creation time from on-chain mint-initialization evidence using a
bounded read-only sequence: getAccountInfo → getSignaturesForAddress (≤3 pages)
→ getTransaction (≤3 calls) → optional getBlockTime (≤1 call).

Budget: ≤ 8 RPC requests per token, 10s timeout, 0 retries.
Request kind: mint_creation_time_reference
Source: solana_rpc

Evidence is accepted ONLY when:
  - Mint account finalized (SPL Token or Token-2022 program owner)
  - Signature history end reachable within page cap (full history available)
  - exactly one initializeMint or initializeMint2 targets the exact mint
  - parsed/compiled, top-level/inner, and legacy/v0 account keys resolve safely
  - Valid, non-future block time derived

All failures leave token_created_at, token_age_seconds, and tier unset (fail-closed).
No fallback to pair age, captured_at, migration time, or OBSERVED_LIVE_LAUNCH.

Failure provenance: partial trace fields (t3_requested_mint, t3_rpc_host_redacted,
t3_rpc_methods_attempted, t3_request_ids, t3_pages_fetched, t3_tx_calls_attempted,
t3_block_time_calls_attempted, t3_failure_stage) are preserved in the failure result
normalized_payload for audit. They never produce token-age evidence or unlock A3.
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
_INIT_MINT_OPCODE_TYPES = {0: "initializeMint", 20: "initializeMint2"}
_T3_COMMITMENT = "finalized"
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {char: index for index, char in enumerate(_BASE58_ALPHABET)}
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

# Partial failure provenance fields carried in NormalizedSourceResult.normalized_payload
# on every T3 failure. These are audit/trace fields only — they never produce token-age
# evidence, never populate token_created_at/token_age_seconds/tier, and never unlock A3.
_T3_FAIL_PROVENANCE_FIELDS = (
    "t3_requested_mint",
    "t3_rpc_host_redacted",
    "t3_rpc_methods_attempted",
    "t3_request_ids",
    "t3_pages_fetched",
    "t3_tx_calls_attempted",
    "t3_block_time_calls_attempted",
    "t3_failure_stage",
)

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
    *,
    failure_provenance: Mapping[str, Any] | None = None,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """Return a transport that always returns a pre-built T3 failure payload.

    Pass failure_provenance to include partial trace fields (t3_requested_mint,
    t3_rpc_methods_attempted, etc.) in the fixture failure for testing provenance paths.
    """
    payload: dict[str, Any] = {
        "fixture_status": "failure",
        "failure_type": failure_type,
        "failure_message": failure_message,
    }
    if failure_provenance:
        payload.update(failure_provenance)
    frozen = MappingProxyType(payload)

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
            failure_provenance=_extract_failure_provenance(payload),
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
        # Provenance fields, including explicit finalized-evidence state.
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
        "t3_commitment": str(payload.get("t3_commitment") or ""),
        "t3_finality_status": str(payload.get("t3_finality_status") or ""),
    }

    if normalized["t3_commitment"] != _T3_COMMITMENT or normalized["t3_finality_status"] != _T3_COMMITMENT:
        return _t3_failure_result(
            request_kind,
            "solana_rpc_token_age_non_finalized_evidence",
            "T3 success payload must carry finalized commitment and finality status",
        )

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


def _account_key_string(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        pubkey = value.get("pubkey")
        return str(pubkey) if pubkey else None
    return None


def _transaction_account_keys(tx_result: Mapping[str, Any]) -> list[str] | None:
    message = ((tx_result.get("transaction") or {}).get("message") or {})
    meta = tx_result.get("meta") or {}
    raw_keys = list(message.get("accountKeys") or [])
    loaded = meta.get("loadedAddresses") or {}
    raw_keys.extend(loaded.get("writable") or [])
    raw_keys.extend(loaded.get("readonly") or [])
    keys = [_account_key_string(value) for value in raw_keys]
    return None if any(key is None for key in keys) else [str(key) for key in keys]


def _decode_base58(value: str) -> bytes | None:
    if not isinstance(value, str) or not value:
        return None
    number = 0
    try:
        for char in value:
            number = number * 58 + _BASE58_INDEX[char]
    except KeyError:
        return None
    decoded = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return (b"\x00" * (len(value) - len(value.lstrip("1")))) + decoded


def _is_init_mint_instruction(
    instruction: Mapping[str, Any],
    token_mint: str,
    account_keys: list[str] | None = None,
) -> tuple[bool, str | None, str | None]:
    """Match one parsed or compiled token-program mint initialization exactly."""
    program = instruction.get("program") or ""
    program_id = instruction.get("programId") or ""
    parsed = instruction.get("parsed")
    if isinstance(parsed, Mapping):
        if program_id not in _ALLOWED_TOKEN_PROGRAMS:
            if program == "spl-token":
                program_id = _SPL_TOKEN_PROGRAM_ID
            elif program == "spl-token-2022":
                program_id = _TOKEN_2022_PROGRAM_ID
            else:
                return False, None, None
        inst_type = parsed.get("type") or ""
        info = parsed.get("info") or {}
        mint_in_inst = info.get("mint") or info.get("account") or ""
        if inst_type not in _INIT_MINT_INSTRUCTION_TYPES or mint_in_inst != token_mint:
            return False, None, None
        label = "token_2022" if program_id == _TOKEN_2022_PROGRAM_ID else "spl_token"
        return True, str(inst_type), label

    if account_keys is None:
        return False, None, None
    try:
        program_id = account_keys[int(instruction["programIdIndex"])]
        account_indexes = list(instruction["accounts"])
        mint_in_inst = account_keys[int(account_indexes[0])]
    except (KeyError, TypeError, ValueError, IndexError):
        return False, None, None
    if program_id not in _ALLOWED_TOKEN_PROGRAMS or mint_in_inst != token_mint:
        return False, None, None
    data = _decode_base58(instruction.get("data"))
    if not data or data[0] not in _INIT_MINT_OPCODE_TYPES:
        return False, None, None
    label = "token_2022" if program_id == _TOKEN_2022_PROGRAM_ID else "spl_token"
    return True, _INIT_MINT_OPCODE_TYPES[data[0]], label


def _transaction_init_matches(
    tx_result: Mapping[str, Any], token_mint: str
) -> list[tuple[str, str]] | None:
    account_keys = _transaction_account_keys(tx_result)
    if account_keys is None:
        return None
    message = ((tx_result.get("transaction") or {}).get("message") or {})
    meta = tx_result.get("meta") or {}
    instructions = list(message.get("instructions") or [])
    for inner_group in meta.get("innerInstructions") or []:
        if not isinstance(inner_group, Mapping):
            return None
        instructions.extend(inner_group.get("instructions") or [])
    matches: list[tuple[str, str]] = []
    for instruction in instructions:
        if not isinstance(instruction, Mapping):
            return None
        matched, instruction_type, program_label = _is_init_mint_instruction(
            instruction, token_mint, account_keys
        )
        if matched and instruction_type and program_label:
            matches.append((instruction_type, program_label))
    return matches


def _fetch_token_age_data(
    token_mint: str,
    captured_at: str,
    *,
    rpc_url: str = SOLANA_PUBLIC_RPC_URL,
    timeout_seconds: float = _T3_RPC_TIMEOUT_SECONDS,
) -> Mapping[str, Any]:
    """Execute the full T3 multi-step RPC pipeline.

    Not called in V2-2AK fixture tests. Defined for V2-2AL bounded live proof.
    On failure, carries partial provenance in the returned dict so callers can
    pass it through to NormalizedSourceResult.normalized_payload for audit.
    """
    request_count = 0
    request_ids: list[int] = []
    methods_attempted: list[str] = []
    pages_fetched = 0
    tx_calls = 0
    block_time_calls = 0

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

    def _pfail(failure_type: str, failure_message: str, *, stage: str) -> Mapping[str, Any]:
        """Build a failure payload carrying current partial provenance for audit."""
        return MappingProxyType({
            "fixture_status": "failure",
            "failure_type": failure_type,
            "failure_message": failure_message,
            "t3_requested_mint": token_mint,
            "t3_rpc_host_redacted": host_redacted,
            "t3_rpc_methods_attempted": list(methods_attempted),
            "t3_request_ids": list(request_ids),
            "t3_pages_fetched": pages_fetched,
            "t3_tx_calls_attempted": tx_calls,
            "t3_block_time_calls_attempted": block_time_calls,
            "t3_failure_stage": stage,
        })

    # Step 1: Validate mint account
    account_resp = _call(
        "getAccountInfo",
        [token_mint, {"encoding": "base64", "commitment": _T3_COMMITMENT}],
    )
    if account_resp.get("fixture_status") == "failure":
        ft = str(account_resp.get("failure_type") or "solana_rpc_token_age_transport_error")
        fm = str(account_resp.get("failure_message") or "")
        return _pfail(ft, fm, stage="account_validation")
    if account_resp.get("error"):
        return _pfail(
            "solana_rpc_token_age_transport_error",
            str(account_resp.get("error")),
            stage="account_validation",
        )

    result_value = (account_resp.get("result") or {}).get("value")
    if not result_value:
        return _pfail(
            "solana_rpc_token_age_account_not_found",
            f"Mint account not found on-chain: {token_mint}",
            stage="account_validation",
        )

    owner = result_value.get("owner")
    if owner not in _ALLOWED_TOKEN_PROGRAMS:
        return _pfail(
            "solana_rpc_token_age_not_a_mint",
            f"Account owner {owner!r} is not SPL Token or Token-2022 program",
            stage="account_validation",
        )

    data_field = result_value.get("data")
    if not isinstance(data_field, list) or not data_field:
        return _pfail(
            "solana_rpc_token_age_not_a_mint",
            "Account data missing or not in expected base64 list format",
            stage="account_validation",
        )
    try:
        raw_bytes = base64.b64decode(data_field[0])
    except Exception as exc:
        return _pfail(
            "solana_rpc_token_age_not_a_mint",
            f"Mint data base64 decode failed: {exc}",
            stage="account_validation",
        )
    if owner == _SPL_TOKEN_PROGRAM_ID:
        if len(raw_bytes) != _SPL_TOKEN_MINT_SIZE:
            return _pfail(
                "solana_rpc_token_age_not_a_mint",
                f"SPL Token Mint must be exactly {_SPL_TOKEN_MINT_SIZE} bytes",
                stage="account_validation",
            )
        spl_valid, spl_err = _decode_spl_token_base_mint_state(raw_bytes)
        if not spl_valid:
            return _pfail(
                "solana_rpc_token_age_not_a_mint",
                f"SPL Token mint-state decode failed: {spl_err}",
                stage="account_validation",
            )
    else:
        # Token-2022: validate AccountType byte and TLV extension structure
        t22_valid, t22_err = _decode_token_2022_mint_state(raw_bytes)
        if not t22_valid:
            return _pfail(
                "solana_rpc_token_age_not_a_mint",
                f"Token-2022 mint-state decode failed: {t22_err}",
                stage="account_validation",
            )

    # Step 2: Walk signature history to oldest available page
    before_cursor: str | None = None
    oldest_page: list[Any] = []
    reached_end = False

    while pages_fetched < _T3_MAX_SIGNATURE_PAGES:
        sig_params: list[Any] = [
            token_mint,
            {"limit": _T3_SIGNATURES_PER_PAGE, "commitment": _T3_COMMITMENT},
        ]
        if before_cursor:
            sig_params[1]["before"] = before_cursor

        sig_resp = _call("getSignaturesForAddress", sig_params)
        if sig_resp.get("fixture_status") == "failure":
            ft = str(sig_resp.get("failure_type") or "solana_rpc_token_age_transport_error")
            fm = str(sig_resp.get("failure_message") or "")
            return _pfail(ft, fm, stage="signature_history")
        if sig_resp.get("error"):
            return _pfail(
                "solana_rpc_token_age_transport_error",
                str(sig_resp.get("error")),
                stage="signature_history",
            )

        sig_list = sig_resp.get("result") or []
        pages_fetched += 1

        if not sig_list:
            if pages_fetched == 1:
                return _pfail(
                    "solana_rpc_token_age_no_signatures",
                    f"No signature history for mint: {token_mint}",
                    stage="signature_history",
                )
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
        return _pfail(
            "solana_rpc_token_age_page_cap_exhausted",
            (
                f"Signature page cap ({_T3_MAX_SIGNATURE_PAGES}) exhausted before "
                "reaching mint history start"
            ),
            stage="signature_history",
        )

    # Take up to _T3_MAX_INIT_CANDIDATES from the oldest end of the page
    raw_candidates = [
        row for row in reversed(oldest_page[-_T3_MAX_INIT_CANDIDATES:])
        if (
            (row or {}).get("signature")
            and not (row or {}).get("err")
            and (row or {}).get("confirmationStatus") == _T3_COMMITMENT
        )
    ]
    if not raw_candidates:
        return _pfail(
            "solana_rpc_token_age_no_signatures",
            "No successful candidate signatures in oldest page",
            stage="signature_history",
        )

    # Step 3: Inspect candidate transactions
    accepted_matches: list[dict[str, Any]] = []

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
                    "commitment": _T3_COMMITMENT,
                    "maxSupportedTransactionVersion": 0,
                },
            ],
        )
        tx_calls += 1

        if tx_resp.get("fixture_status") == "failure":
            ft = str(tx_resp.get("failure_type") or "solana_rpc_token_age_transport_error")
            fm = str(tx_resp.get("failure_message") or "")
            return _pfail(ft, fm, stage="transaction_inspection")

        tx_result = tx_resp.get("result")
        if tx_result is None:
            continue

        meta_err = (tx_result.get("meta") or {}).get("err")
        if meta_err is not None:
            continue

        matches = _transaction_init_matches(tx_result, token_mint)
        if matches is None:
            return _pfail(
                "solana_rpc_token_age_malformed_transaction",
                "Transaction account keys or instructions could not be resolved safely",
                stage="transaction_inspection",
            )
        if len(matches) > 1:
            return _pfail(
                "solana_rpc_token_age_ambiguous_init_instruction",
                "Multiple matching mint-initialization instructions found in one transaction",
                stage="transaction_inspection",
            )
        if not matches:
            continue

        block_time = tx_result.get("blockTime")
        slot = tx_result.get("slot")
        resolved_block_time: int | None = None
        resolved_source: str | None = None
        if block_time is not None and int(block_time) > 0:
            resolved_block_time = int(block_time)
            resolved_source = "getTransaction"

        # blockTime null — getBlockTime fallback, capped at _T3_MAX_BLOCK_TIME_CALLS
        if resolved_block_time is None and slot is not None and block_time_calls < _T3_MAX_BLOCK_TIME_CALLS:
            bt_resp = _call("getBlockTime", [int(slot)])
            block_time_calls += 1
            if bt_resp.get("fixture_status") == "failure":
                ft = str(bt_resp.get("failure_type") or "solana_rpc_token_age_transport_error")
                fm = str(bt_resp.get("failure_message") or "")
                return _pfail(ft, fm, stage="block_time_fallback")
            bt = bt_resp.get("result")
            if bt is not None and int(bt) > 0:
                resolved_block_time = int(bt)
                resolved_source = "getBlockTime"

        if resolved_block_time is not None:
            accepted_matches.append({
                "signature": sig,
                "slot": slot,
                "block_time": resolved_block_time,
                "block_time_source": resolved_source,
                "instruction_type": matches[0][0],
                "program_label": matches[0][1],
            })

    if len(accepted_matches) > 1:
        return _pfail(
            "solana_rpc_token_age_ambiguous_init_instruction",
            "Multiple finalized mint-initialization transactions matched the requested mint",
            stage="transaction_inspection",
        )
    if not accepted_matches:
        return _pfail(
            "solana_rpc_token_age_no_init_instruction",
            "No successful initializeMint/initializeMint2 with valid block time found",
            stage="transaction_inspection",
        )
    accepted = accepted_matches[0]
    found_sig = str(accepted["signature"])
    found_slot = accepted["slot"]
    found_block_time = int(accepted["block_time"])
    block_time_source = str(accepted["block_time_source"])
    found_inst_type = str(accepted["instruction_type"])
    found_prog_label = str(accepted["program_label"])

    # Derive timestamps and validate non-future
    try:
        captured_dt = datetime.fromisoformat(
            captured_at.replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        token_created_dt = datetime.fromtimestamp(found_block_time, tz=timezone.utc)
    except Exception as exc:
        return _pfail(
            "solana_rpc_token_age_malformed_response",
            f"Timestamp derivation failed: {exc}",
            stage="timestamp_derivation",
        )

    if token_created_dt > captured_dt:
        return _pfail(
            "solana_rpc_token_age_future_block_time",
            f"Block time {found_block_time} is in the future relative to captured_at",
            stage="timestamp_derivation",
        )

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
        "t3_commitment": _T3_COMMITMENT,
        "t3_finality_status": _T3_COMMITMENT,
    })


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_failure_provenance(
    payload: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    """Extract safe partial trace fields from a failure payload for audit persistence.

    Only copies fields listed in _T3_FAIL_PROVENANCE_FIELDS. Never copies
    token_created_at, token_age_seconds, token_age_evidence_tier, or any
    success-path field that could be misread as T3 evidence.
    """
    result: dict[str, Any] = {}
    for field in _T3_FAIL_PROVENANCE_FIELDS:
        val = payload.get(field)
        if val is not None:
            result[field] = val
    return MappingProxyType(result) if result else None


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
    *,
    failure_provenance: Mapping[str, Any] | None = None,
) -> NormalizedSourceResult:
    """Build a fail-closed NormalizedSourceResult.

    If failure_provenance is provided, its fields are stored in normalized_payload
    for audit. They are audit-only: no token_created_at, token_age_seconds,
    token_age_evidence_tier, or A3-unlocking field is ever included.
    """
    payload: dict[str, Any] = dict(failure_provenance) if failure_provenance else {}
    return NormalizedSourceResult(
        source_name=SOLANA_RPC_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.FAILED,
        data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        failure_type=failure_type,
        failure_message=failure_message,
        normalized_payload=MappingProxyType(payload),
    )

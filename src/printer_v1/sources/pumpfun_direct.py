"""Fixture-only direct Pump.fun create decoder, continuity, and origin owner.

There is deliberately no transport, persistence, command, or runtime entry
point. Every externally observed value enters through FixtureOperation.

V2-9.7E.4C adds create-capture productivity rules (failed-signature filtering
before decode budget, refined continuity faults, early-create stop) and bounded
mint-scoped origin lookup via adopted origin request kinds.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from printer_v1.scheduler.contracts import JobKind
from printer_v1.sources.governor import can_request_source


PUMP_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PUMP_REPOSITORY_COMMIT = "9c82f61cb711b044a17f770ab8ce9f9bdf78f333"
PUMP_IDL_SHA256 = "b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49"
CREATE_DISCRIMINATOR = bytes((24, 30, 200, 40, 5, 28, 7, 119))
CREATE_V2_DISCRIMINATOR = bytes((214, 144, 76, 236, 95, 139, 49, 180))
CREATE_EVENT_DISCRIMINATOR = bytes((27, 114, 169, 77, 222, 235, 99, 118))
EVENT_CPI_WRAPPER = bytes((228, 69, 165, 46, 81, 203, 154, 29))

SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
ASSOCIATED_TOKEN_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
RENT_SYSVAR_ID = "SysvarRent111111111111111111111111111111111"
TOKEN_METADATA_PROGRAM_ID = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"
MINT_AUTHORITY_ID = "TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM"
GLOBAL_ID = "4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf"
EVENT_AUTHORITY_ID = "Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1"

SOURCE_NAME = "solana_rpc"
SCHEDULER_JOB_KIND = JobKind.DISCOVERY_REFRESH.value
SCHEDULER_WORK_TYPE = "DISCOVERY_PUMPFUN_LATEST"
ORIGIN_SCHEDULER_WORK_TYPE = "DISCOVERY_ORIGIN_VERIFICATION"
SESSION_REQUEST = "pumpfun_create_event_subscription"
BACKFILL_REQUEST = "pumpfun_create_signature_backfill"
TRANSACTION_REQUEST = "pumpfun_create_transaction_reference"
ORIGIN_SIGNATURE_REQUEST = "pumpfun_origin_signature_reference"
ORIGIN_TRANSACTION_REQUEST = "pumpfun_origin_transaction_reference"
DIRECT_REQUEST_CEILINGS = MappingProxyType(
    {
        SESSION_REQUEST: 1,
        BACKFILL_REQUEST: 2,
        TRANSACTION_REQUEST: 16,
    }
)
ORIGIN_REQUEST_CEILINGS = MappingProxyType(
    {
        ORIGIN_SIGNATURE_REQUEST: 8,
        ORIGIN_TRANSACTION_REQUEST: 8,
    }
)
# Union of adopted direct + origin ceilings (registry-aligned documentation map).
REQUEST_CEILINGS = MappingProxyType(
    {**DIRECT_REQUEST_CEILINGS, **ORIGIN_REQUEST_CEILINGS}
)
_REQUEST_KIND_WORK_TYPE = MappingProxyType(
    {
        SESSION_REQUEST: SCHEDULER_WORK_TYPE,
        BACKFILL_REQUEST: SCHEDULER_WORK_TYPE,
        TRANSACTION_REQUEST: SCHEDULER_WORK_TYPE,
        ORIGIN_SIGNATURE_REQUEST: ORIGIN_SCHEDULER_WORK_TYPE,
        ORIGIN_TRANSACTION_REQUEST: ORIGIN_SCHEDULER_WORK_TYPE,
    }
)
UNDERLYING_OPERATION_CEILING = 45
BACKFILL_PAGE_CEILING = 2
BACKFILL_PAGE_SIZE = 16
TRANSACTION_DECODE_CEILING = 16
EARLY_CREATE_STOP = 8
ORIGIN_SIGNATURE_PAGE_CEILING = 1
ORIGIN_SIGNATURE_PAGE_SIZE = 16
ORIGIN_TRANSACTION_PER_MINT = 1
# Codes that are factual market noise / productivity stops — not continuity faults.
_NON_FAULT_CLASSIFICATIONS = frozenset(
    {
        "FAILED_TRANSACTION",
        "NOT_SUPPORTED_CREATE",
        "EARLY_CREATE_STOP",
        "POST_CUTOFF",
    }
)

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_INDEX = {character: index for index, character in enumerate(_B58_ALPHABET)}


class PumpContractError(RuntimeError):
    """Fail-closed direct Pump contract violation."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}: {detail}")


class ContinuityState(StrEnum):
    CONTIGUOUS = "CONTIGUOUS"
    GAPPED = "GAPPED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, order=True)
class CursorBoundary:
    slot: int
    signature: str


@dataclass(frozen=True)
class FinalizedCursor:
    boundary: CursorBoundary | None
    continuity: ContinuityState


@dataclass(frozen=True)
class SignatureReference:
    signature: str
    slot: int
    confirmation_status: str
    err: object | None = None


@dataclass(frozen=True)
class PumpCreateObservation:
    mint: str
    bonding_curve: str
    associated_bonding_curve: str
    creator_address: str
    signature: str
    slot: int
    block_time: int
    program_id: str = PUMP_PROGRAM_ID
    creator_evidence_scope: str = "OBSERVED_EVIDENCE_ONLY"


@dataclass(frozen=True)
class FixtureOperation:
    """One synthetic response carrying explicit Governor/Scheduler ownership."""

    request_id: str
    request_kind: str
    rpc_operation: str
    response: Any
    source_name: str = SOURCE_NAME
    scheduler_job_kind: str = SCHEDULER_JOB_KIND
    scheduler_work_type: str = SCHEDULER_WORK_TYPE


@dataclass(frozen=True)
class AccountingSnapshot:
    governed_requests: Mapping[str, int]
    underlying_rpc_operations: int


@dataclass(frozen=True)
class Rejection:
    code: str
    signature: str | None
    slot: int | None


@dataclass(frozen=True)
class DirectPumpCycleResult:
    cutoff_slot: int
    observations: tuple[PumpCreateObservation, ...]
    rejections: tuple[Rejection, ...]
    cursor: FinalizedCursor
    accounting: AccountingSnapshot
    live_disconnected: bool
    backfill_pages: int
    duplicate_signatures: int
    failed_signature_count: int = 0
    non_create_count: int = 0
    decode_attempts: int = 0

    def canonical(self) -> tuple[object, ...]:
        """Stable replay identity without mutable or wall-clock values."""
        return (
            self.cutoff_slot,
            tuple(self.observations),
            tuple(self.rejections),
            self.cursor,
            tuple(sorted(self.accounting.governed_requests.items())),
            self.accounting.underlying_rpc_operations,
            self.live_disconnected,
            self.backfill_pages,
            self.duplicate_signatures,
            self.failed_signature_count,
            self.non_create_count,
            self.decode_attempts,
        )


@dataclass(frozen=True)
class MintOriginLookupResult:
    """Bounded mint-scoped finalized origin lookup outcome."""

    expected_mint: str
    observation: PumpCreateObservation | None
    rejections: tuple[Rejection, ...]
    accounting: AccountingSnapshot
    signature_rows: int
    decode_attempts: int

    def canonical(self) -> tuple[object, ...]:
        return (
            self.expected_mint,
            self.observation,
            tuple(self.rejections),
            tuple(sorted(self.accounting.governed_requests.items())),
            self.accounting.underlying_rpc_operations,
            self.signature_rows,
            self.decode_attempts,
        )


def _b58decode(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise PumpContractError("MALFORMED_TRANSACTION", "invalid base58 value")
    number = 0
    try:
        for character in value:
            number = number * 58 + _B58_INDEX[character]
    except KeyError as exc:
        raise PumpContractError("MALFORMED_TRANSACTION", "invalid base58 value") from exc
    raw = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return bytes(len(value) - len(value.lstrip("1"))) + raw


def _b58encode(value: bytes) -> str:
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = _B58_ALPHABET[remainder] + encoded
    return "1" * (len(value) - len(value.lstrip(bytes(1)))) + (encoded or "")


def _is_ed25519_point(value: bytes) -> bool:
    if len(value) != 32:
        return False
    prime = 2**255 - 19
    encoded = int.from_bytes(value, "little")
    sign = encoded >> 255
    y = encoded & (2**255 - 1)
    if y >= prime:
        return False
    y_squared = y * y % prime
    d = -121665 * pow(121666, prime - 2, prime) % prime
    denominator = (d * y_squared + 1) % prime
    if denominator == 0:
        return False
    x_squared = (y_squared - 1) * pow(denominator, prime - 2, prime) % prime
    if x_squared == 0:
        return sign == 0
    return pow(x_squared, (prime - 1) // 2, prime) == 1


def derive_program_address(seeds: Sequence[bytes], program_id: str) -> str:
    if any(len(seed) > 32 for seed in seeds):
        raise PumpContractError("MALFORMED_TRANSACTION", "PDA seed exceeds 32 bytes")
    program = _b58decode(program_id)
    if len(program) != 32:
        raise PumpContractError("MALFORMED_TRANSACTION", "program is not a pubkey")
    for bump in range(255, -1, -1):
        digest = hashlib.sha256(
            b"".join((*seeds, bytes((bump,)), program, b"ProgramDerivedAddress"))
        ).digest()
        if not _is_ed25519_point(digest):
            return _b58encode(digest)
    raise PumpContractError("MALFORMED_TRANSACTION", "no PDA bump")


def _read_u32(data: bytes, offset: int) -> tuple[int, int]:
    if offset + 4 > len(data):
        raise PumpContractError("MALFORMED_TRANSACTION", "truncated u32")
    return int.from_bytes(data[offset : offset + 4], "little"), offset + 4


def _read_string(data: bytes, offset: int) -> tuple[str, int]:
    length, offset = _read_u32(data, offset)
    end = offset + length
    if end > len(data):
        raise PumpContractError("MALFORMED_TRANSACTION", "truncated string")
    try:
        return data[offset:end].decode("utf-8"), end
    except UnicodeDecodeError as exc:
        raise PumpContractError("MALFORMED_TRANSACTION", "invalid UTF-8") from exc


def _read_pubkey(data: bytes, offset: int) -> tuple[str, int]:
    end = offset + 32
    if end > len(data):
        raise PumpContractError("MALFORMED_TRANSACTION", "truncated pubkey")
    return _b58encode(data[offset:end]), end


def _decode_create_args(data: bytes) -> tuple[str, str, str, str]:
    offset = len(CREATE_DISCRIMINATOR)
    name, offset = _read_string(data, offset)
    symbol, offset = _read_string(data, offset)
    uri, offset = _read_string(data, offset)
    creator, offset = _read_pubkey(data, offset)
    if offset != len(data):
        raise PumpContractError("MALFORMED_TRANSACTION", "trailing create bytes")
    return name, symbol, uri, creator

def _decode_event(data: bytes) -> Mapping[str, object]:
    offset = len(EVENT_CPI_WRAPPER) if data.startswith(EVENT_CPI_WRAPPER) else 0
    if data[offset : offset + 8] != CREATE_EVENT_DISCRIMINATOR:
        raise PumpContractError("MALFORMED_TRANSACTION", "bad event discriminator")
    offset += 8
    name, offset = _read_string(data, offset)
    symbol, offset = _read_string(data, offset)
    uri, offset = _read_string(data, offset)
    pubkeys: list[str] = []
    for _ in range(4):
        value, offset = _read_pubkey(data, offset)
        pubkeys.append(value)
    scalars: list[int] = []
    for _ in range(5):
        if offset + 8 > len(data):
            raise PumpContractError("MALFORMED_TRANSACTION", "truncated event scalar")
        scalars.append(int.from_bytes(data[offset : offset + 8], "little"))
        offset += 8
    token_program, offset = _read_pubkey(data, offset)
    if offset + 2 > len(data) or any(value not in (0, 1) for value in data[offset : offset + 2]):
        raise PumpContractError("MALFORMED_TRANSACTION", "invalid event boolean")
    mayhem, cashback = bool(data[offset]), bool(data[offset + 1])
    offset += 2
    quote_mint, offset = _read_pubkey(data, offset)
    if offset + 8 != len(data):
        raise PumpContractError("MALFORMED_TRANSACTION", "invalid event length")
    virtual_quote = int.from_bytes(data[offset : offset + 8], "little")
    return MappingProxyType(
        {
            "name": name,
            "symbol": symbol,
            "uri": uri,
            "mint": pubkeys[0],
            "bonding_curve": pubkeys[1],
            "user": pubkeys[2],
            "creator": pubkeys[3],
            "timestamp": scalars[0],
            "virtual_token_reserves": scalars[1],
            "virtual_sol_reserves": scalars[2],
            "real_token_reserves": scalars[3],
            "token_total_supply": scalars[4],
            "token_program": token_program,
            "is_mayhem_mode": mayhem,
            "is_cashback_enabled": cashback,
            "quote_mint": quote_mint,
            "virtual_quote_reserves": virtual_quote,
        }
    )


def _pubkey(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping) and isinstance(value.get("pubkey"), str):
        return str(value["pubkey"])
    raise PumpContractError("MALFORMED_TRANSACTION", "unresolved account key")


def _compiled_instructions(result: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    try:
        message = result["transaction"]["message"]
        top_level = tuple(message["instructions"])
        groups = result["meta"].get("innerInstructions") or ()
    except (KeyError, TypeError) as exc:
        raise PumpContractError("MALFORMED_TRANSACTION", "missing instruction envelope") from exc
    inner: list[Mapping[str, Any]] = []
    for group in groups:
        if not isinstance(group, Mapping) or not isinstance(group.get("instructions"), list):
            raise PumpContractError("MALFORMED_TRANSACTION", "bad inner instructions")
        inner.extend(group["instructions"])
    if not all(isinstance(item, Mapping) for item in (*top_level, *inner)):
        raise PumpContractError("MALFORMED_TRANSACTION", "bad compiled instruction")
    return tuple((*top_level, *inner))


def _resolved_keys(result: Mapping[str, Any]) -> tuple[str, ...]:
    try:
        static = result["transaction"]["message"]["accountKeys"]
        loaded = result["meta"].get("loadedAddresses") or {"writable": [], "readonly": []}
        raw = (*static, *loaded.get("writable", ()), *loaded.get("readonly", ()))
    except (KeyError, TypeError) as exc:
        raise PumpContractError("MALFORMED_TRANSACTION", "unresolved account keys") from exc
    return tuple(_pubkey(value) for value in raw)


def _instruction_data(instruction: Mapping[str, Any]) -> bytes:
    if not isinstance(instruction.get("data"), str):
        raise PumpContractError("MALFORMED_TRANSACTION", "parsed instruction has no raw data")
    return _b58decode(str(instruction["data"]))


def _instruction_program(instruction: Mapping[str, Any], keys: Sequence[str]) -> str:
    index = instruction.get("programIdIndex")
    if type(index) is not int or index < 0 or index >= len(keys):
        raise PumpContractError("MALFORMED_TRANSACTION", "bad program index")
    return keys[index]


def _instruction_accounts(
    instruction: Mapping[str, Any], keys: Sequence[str]
) -> tuple[str, ...]:
    indices = instruction.get("accounts")
    if not isinstance(indices, list) or len(indices) != 14:
        raise PumpContractError("MALFORMED_TRANSACTION", "create requires 14 accounts")
    if any(type(index) is not int or index < 0 or index >= len(keys) for index in indices):
        raise PumpContractError("MALFORMED_TRANSACTION", "bad create account index")
    return tuple(keys[index] for index in indices)


def _validate_account_identities(accounts: Sequence[str]) -> None:
    exact = {
        1: MINT_AUTHORITY_ID,
        4: GLOBAL_ID,
        5: TOKEN_METADATA_PROGRAM_ID,
        8: SYSTEM_PROGRAM_ID,
        9: TOKEN_PROGRAM_ID,
        10: ASSOCIATED_TOKEN_PROGRAM_ID,
        11: RENT_SYSVAR_ID,
        12: EVENT_AUTHORITY_ID,
        13: PUMP_PROGRAM_ID,
    }
    if any(accounts[index] != expected for index, expected in exact.items()):
        raise PumpContractError("MALFORMED_TRANSACTION", "fixed create account mismatch")
    mint_bytes = _b58decode(accounts[0])
    if len(mint_bytes) != 32:
        raise PumpContractError("MALFORMED_TRANSACTION", "mint is not a pubkey")
    expected_curve = derive_program_address((b"bonding-curve", mint_bytes), PUMP_PROGRAM_ID)
    if accounts[2] != expected_curve:
        raise PumpContractError("MALFORMED_TRANSACTION", "bonding curve PDA mismatch")
    expected_ata = derive_program_address(
        (_b58decode(accounts[2]), _b58decode(TOKEN_PROGRAM_ID), mint_bytes),
        ASSOCIATED_TOKEN_PROGRAM_ID,
    )
    if accounts[3] != expected_ata:
        raise PumpContractError("MALFORMED_TRANSACTION", "bonding curve ATA mismatch")
    expected_metadata = derive_program_address(
        (b"metadata", _b58decode(TOKEN_METADATA_PROGRAM_ID), mint_bytes),
        TOKEN_METADATA_PROGRAM_ID,
    )
    if accounts[6] != expected_metadata:
        raise PumpContractError("MALFORMED_TRANSACTION", "metadata PDA mismatch")


def decode_finalized_create(
    result: Mapping[str, Any],
    *,
    reference: SignatureReference,
    cutoff_slot: int,
    expected_mint: str | None = None,
) -> PumpCreateObservation:
    """Decode exactly one finalized, successful, supported Pump create."""
    if reference.confirmation_status != "finalized":
        raise PumpContractError("MISSING_FINALITY")
    if reference.err is not None:
        raise PumpContractError("FAILED_TRANSACTION")
    if type(cutoff_slot) is not int or cutoff_slot < 0:
        raise PumpContractError("MALFORMED_TRANSACTION", "invalid cutoff")
    if not isinstance(result, Mapping):
        raise PumpContractError("UNAVAILABLE_HISTORY")
    version = result.get("version")
    if version not in ("legacy", 0) or isinstance(version, bool):
        raise PumpContractError("UNSUPPORTED_VERSION")
    try:
        slot = result["slot"]
        block_time = result["blockTime"]
        meta = result["meta"]
        signatures = result["transaction"]["signatures"]
    except (KeyError, TypeError) as exc:
        raise PumpContractError("MALFORMED_TRANSACTION", "missing transaction field") from exc
    if type(slot) is not int or slot < 0 or slot != reference.slot:
        raise PumpContractError("SIGNATURE_OR_SLOT_MISMATCH")
    if slot > cutoff_slot:
        raise PumpContractError("POST_CUTOFF")
    if meta is None:
        raise PumpContractError("UNAVAILABLE_HISTORY")
    if not isinstance(meta, Mapping):
        raise PumpContractError("MALFORMED_TRANSACTION", "bad meta")
    if meta.get("err") is not None:
        raise PumpContractError("FAILED_TRANSACTION")
    if type(block_time) is not int:
        raise PumpContractError("UNAVAILABLE_HISTORY")
    if not isinstance(signatures, list) or not signatures or signatures[0] != reference.signature:
        raise PumpContractError("SIGNATURE_OR_SLOT_MISMATCH")

    keys = _resolved_keys(result)
    creates: list[tuple[Mapping[str, Any], bytes]] = []
    events: list[Mapping[str, object]] = []
    wrong_program = False
    unsupported = False
    for instruction in _compiled_instructions(result):
        data = _instruction_data(instruction)
        program = _instruction_program(instruction, keys)
        if data.startswith(CREATE_DISCRIMINATOR):
            if program != PUMP_PROGRAM_ID:
                wrong_program = True
            else:
                creates.append((instruction, data))
        elif data.startswith(CREATE_V2_DISCRIMINATOR) and program == PUMP_PROGRAM_ID:
            unsupported = True
        elif (
            program == PUMP_PROGRAM_ID
            and (
                data.startswith(CREATE_EVENT_DISCRIMINATOR)
                or data.startswith(EVENT_CPI_WRAPPER + CREATE_EVENT_DISCRIMINATOR)
            )
        ):
            events.append(_decode_event(data))
    if wrong_program:
        raise PumpContractError("WRONG_PROGRAM")
    if unsupported:
        raise PumpContractError("UNSUPPORTED_VERSION")
    if not creates:
        raise PumpContractError("NOT_SUPPORTED_CREATE")
    if len(creates) != 1:
        raise PumpContractError("AMBIGUOUS_CREATE")

    instruction, data = creates[0]
    name, symbol, uri, creator = _decode_create_args(data)
    accounts = _instruction_accounts(instruction, keys)
    _validate_account_identities(accounts)
    if expected_mint is not None and accounts[0] != expected_mint:
        raise PumpContractError("MINT_MISMATCH")
    for event in events:
        expected_event = {
            "name": name,
            "symbol": symbol,
            "uri": uri,
            "mint": accounts[0],
            "bonding_curve": accounts[2],
            "creator": creator,
            "token_program": TOKEN_PROGRAM_ID,
        }
        if any(event[field] != value for field, value in expected_event.items()):
            raise PumpContractError("EVENT_MISMATCH")
    return PumpCreateObservation(
        mint=accounts[0],
        bonding_curve=accounts[2],
        associated_bonding_curve=accounts[3],
        creator_address=creator,
        signature=reference.signature,
        slot=slot,
        block_time=block_time,
    )

_DIRECT_OPERATION_CEILINGS = MappingProxyType(
    {
        "getSlot": 1,
        "logsSubscribe": 1,
        "logsUnsubscribe": 1,
        "getSignaturesForAddress": 2,
        "getTransaction": 16,
    }
)
_ORIGIN_OPERATION_CEILINGS = MappingProxyType(
    {
        "getSignaturesForAddress": 8,
        "getTransaction": 8,
    }
)


def enforce_underlying_operation_ceiling(used: int, added: int = 1) -> int:
    if (
        type(used) is not int
        or type(added) is not int
        or used < 0
        or added < 0
        or used + added > UNDERLYING_OPERATION_CEILING
    ):
        raise PumpContractError("UNDERLYING_OPERATION_CEILING")
    return used + added


def _is_continuity_fault(code: str) -> bool:
    return code not in _NON_FAULT_CLASSIFICATIONS


class _Accounting:
    def __init__(
        self,
        *,
        request_ceilings: Mapping[str, int] | None = None,
        operation_ceilings: Mapping[str, int] | None = None,
    ) -> None:
        ceilings = request_ceilings or DIRECT_REQUEST_CEILINGS
        self._request_ceilings = ceilings
        self.request_ids: dict[str, set[str]] = {
            request_kind: set() for request_kind in ceilings
        }
        ops = operation_ceilings or _DIRECT_OPERATION_CEILINGS
        self._operation_ceilings = ops
        self.operation_counts = {operation: 0 for operation in ops}
        self.underlying = 0

    def consume(self, operation: FixtureOperation) -> None:
        if operation.request_kind not in self._request_ceilings:
            raise PumpContractError("SOURCE_GOVERNOR_BYPASS", "unadopted request kind")
        decision = can_request_source(
            operation.source_name,
            operation.request_kind,
            len(self.request_ids[operation.request_kind]),
        )
        if not decision.allowed:
            raise PumpContractError("SOURCE_GOVERNOR_BYPASS", decision.reason)
        request_ids = self.request_ids[operation.request_kind]
        if operation.request_id not in request_ids:
            if len(request_ids) >= self._request_ceilings[operation.request_kind]:
                raise PumpContractError("GOVERNED_REQUEST_CEILING")
            request_ids.add(operation.request_id)
        if operation.rpc_operation not in self.operation_counts:
            raise PumpContractError("UNADOPTED_RPC_OPERATION")
        if (
            self.operation_counts[operation.rpc_operation]
            >= self._operation_ceilings[operation.rpc_operation]
        ):
            raise PumpContractError("RPC_OPERATION_CEILING")
        self.operation_counts[operation.rpc_operation] += 1
        self.underlying = enforce_underlying_operation_ceiling(self.underlying)

    def snapshot(self) -> AccountingSnapshot:
        return AccountingSnapshot(
            governed_requests=MappingProxyType(
                {
                    request_kind: len(request_ids)
                    for request_kind, request_ids in self.request_ids.items()
                }
            ),
            underlying_rpc_operations=self.underlying,
        )


class FixtureOperationPort:
    """Sequential fixture port that rejects owner bypass before consumption."""

    def __init__(
        self,
        operations: Iterable[FixtureOperation],
        *,
        request_ceilings: Mapping[str, int] | None = None,
        operation_ceilings: Mapping[str, int] | None = None,
    ) -> None:
        self._operations = tuple(operations)
        self._index = 0
        self.accounting = _Accounting(
            request_ceilings=request_ceilings,
            operation_ceilings=operation_ceilings,
        )

    def peek(self) -> FixtureOperation | None:
        return (
            self._operations[self._index]
            if self._index < len(self._operations)
            else None
        )

    def take(self, rpc_operation: str, request_kind: str) -> Any:
        operation = self.peek()
        if operation is None:
            raise PumpContractError("UNAVAILABLE_HISTORY", f"missing {rpc_operation} fixture")
        if (
            operation.source_name != SOURCE_NAME
            or operation.request_kind != request_kind
        ):
            raise PumpContractError("SOURCE_GOVERNOR_BYPASS")
        expected_work = _REQUEST_KIND_WORK_TYPE.get(request_kind)
        if (
            operation.scheduler_job_kind != SCHEDULER_JOB_KIND
            or expected_work is None
            or operation.scheduler_work_type != expected_work
        ):
            raise PumpContractError("CENTRAL_SCHEDULER_BYPASS")
        if operation.rpc_operation != rpc_operation:
            raise PumpContractError(
                "MALFORMED_FIXTURE_OPERATION",
                f"expected {rpc_operation}, got {operation.rpc_operation}",
            )
        self.accounting.consume(operation)
        self._index += 1
        return operation.response

    def assert_consumed(self) -> None:
        if self.peek() is not None:
            raise PumpContractError("UNPLANNED_OPERATION", self.peek().rpc_operation)


def _signature_reference(row: Mapping[str, Any]) -> SignatureReference:
    try:
        signature = row["signature"]
        slot = row["slot"]
        status = row["confirmationStatus"]
    except (KeyError, TypeError) as exc:
        raise PumpContractError("MALFORMED_TRANSACTION", "bad signature row") from exc
    if not isinstance(signature, str) or type(slot) is not int or not isinstance(status, str):
        raise PumpContractError("MALFORMED_TRANSACTION", "bad signature row")
    return SignatureReference(signature, slot, status, row.get("err"))


def run_fixture_cycle(
    operations: Iterable[FixtureOperation],
    *,
    prior_cursor: FinalizedCursor,
) -> DirectPumpCycleResult:
    """Run one bounded fixture-only live session plus planned finalized backfill."""
    port = FixtureOperationPort(operations)
    cutoff = port.take("getSlot", SESSION_REQUEST)
    if type(cutoff) is not int or cutoff < 0:
        raise PumpContractError("MALFORMED_TRANSACTION", "bad finalized cutoff")
    live = port.take("logsSubscribe", SESSION_REQUEST)
    if not isinstance(live, Mapping) or not isinstance(live.get("notifications", []), list):
        raise PumpContractError("MALFORMED_TRANSACTION", "bad live session fixture")
    live_disconnected = bool(live.get("disconnected", False))
    live_rows = tuple(_signature_reference(row) for row in live.get("notifications", ()))
    if port.peek() is not None and port.peek().rpc_operation == "logsUnsubscribe":
        port.take("logsUnsubscribe", SESSION_REQUEST)

    page_rows: list[SignatureReference] = []
    pages = 0
    interval_complete = False
    history_unavailable = False
    while (
        port.peek() is not None
        and port.peek().rpc_operation == "getSignaturesForAddress"
    ):
        if pages >= BACKFILL_PAGE_CEILING:
            raise PumpContractError("BACKFILL_PAGE_CEILING")
        page = port.take("getSignaturesForAddress", BACKFILL_REQUEST)
        pages += 1
        if not isinstance(page, Mapping) or not isinstance(page.get("rows"), list):
            raise PumpContractError("MALFORMED_TRANSACTION", "bad backfill page")
        if len(page["rows"]) > BACKFILL_PAGE_SIZE:
            raise PumpContractError("BACKFILL_PAGE_SIZE_CEILING")
        if not page["rows"]:
            history_unavailable = True
        page_rows.extend(_signature_reference(row) for row in page["rows"])
        interval_complete = bool(page["rows"]) and bool(
            page.get("complete_to_prior_cursor", False)
        )
        if interval_complete:
            break

    rejections: list[Rejection] = []
    duplicates = 0
    references: dict[str, SignatureReference] = {}
    conflicting_signatures: set[str] = set()
    continuity_fault = live_disconnected or not interval_complete
    history_unknown = (
        prior_cursor.boundary is None
        or prior_cursor.continuity is not ContinuityState.CONTIGUOUS
    )

    def admit(reference: SignatureReference) -> None:
        nonlocal duplicates, continuity_fault
        if reference.slot > cutoff:
            rejections.append(Rejection("POST_CUTOFF", reference.signature, reference.slot))
            return
        if reference.signature in conflicting_signatures:
            duplicates += 1
            return
        previous = references.get(reference.signature)
        if previous is not None:
            duplicates += 1
            if previous != reference:
                references.pop(reference.signature)
                conflicting_signatures.add(reference.signature)
                rejections.append(
                    Rejection("CONFLICTING_DUPLICATE", reference.signature, reference.slot)
                )
                continuity_fault = True
            return
        references[reference.signature] = reference

    for reference in page_rows:
        admit(reference)
    finalized_history_signatures = frozenset(reference.signature for reference in page_rows)
    for reference in live_rows:
        if reference.slot <= cutoff and reference.signature not in finalized_history_signatures:
            rejections.append(
                Rejection("UNRECONCILED_LIVE_SIGNATURE", reference.signature, reference.slot)
            )
            continuity_fault = True
            continue
        admit(reference)

    admitted_ordered = sorted(
        references.values(), key=lambda item: (item.slot, item.signature)
    )

    failed_signature_count = 0
    non_create_count = 0
    decode_attempts = 0
    decode_eligible: list[SignatureReference] = []
    for reference in admitted_ordered:
        if reference.err is not None:
            rejections.append(
                Rejection("FAILED_TRANSACTION", reference.signature, reference.slot)
            )
            failed_signature_count += 1
            continue
        if reference.confirmation_status != "finalized":
            rejections.append(
                Rejection("MISSING_FINALITY", reference.signature, reference.slot)
            )
            continuity_fault = True
            continue
        decode_eligible.append(reference)

    if len(decode_eligible) > TRANSACTION_DECODE_CEILING:
        for reference in decode_eligible[TRANSACTION_DECODE_CEILING:]:
            rejections.append(
                Rejection(
                    "TRANSACTION_DECODE_CEILING",
                    reference.signature,
                    reference.slot,
                )
            )
        decode_eligible = decode_eligible[:TRANSACTION_DECODE_CEILING]
        continuity_fault = True
        rejections.append(Rejection("TRANSACTION_DECODE_CEILING", None, None))

    observations: list[PumpCreateObservation] = []
    for reference in decode_eligible:
        if len(observations) >= EARLY_CREATE_STOP:
            rejections.append(
                Rejection("EARLY_CREATE_STOP", reference.signature, reference.slot)
            )
            continue
        transaction = port.take("getTransaction", TRANSACTION_REQUEST)
        decode_attempts += 1
        try:
            observation = decode_finalized_create(
                transaction, reference=reference, cutoff_slot=cutoff
            )
        except PumpContractError as exc:
            rejections.append(Rejection(exc.code, reference.signature, reference.slot))
            if exc.code == "NOT_SUPPORTED_CREATE":
                non_create_count += 1
            elif _is_continuity_fault(exc.code):
                continuity_fault = True
        else:
            observations.append(observation)

    port.assert_consumed()
    if history_unknown or history_unavailable:
        state = ContinuityState.UNKNOWN
        boundary = prior_cursor.boundary
    elif continuity_fault:
        state = ContinuityState.GAPPED
        boundary = prior_cursor.boundary
    else:
        state = ContinuityState.CONTIGUOUS
        boundary = (
            CursorBoundary(admitted_ordered[-1].slot, admitted_ordered[-1].signature)
            if admitted_ordered
            else prior_cursor.boundary
        )
    return DirectPumpCycleResult(
        cutoff_slot=cutoff,
        observations=tuple(observations),
        rejections=tuple(rejections),
        cursor=FinalizedCursor(boundary, state),
        accounting=port.accounting.snapshot(),
        live_disconnected=live_disconnected,
        backfill_pages=pages,
        duplicate_signatures=duplicates,
        failed_signature_count=failed_signature_count,
        non_create_count=non_create_count,
        decode_attempts=decode_attempts,
    )


def run_mint_origin_lookup(
    operations: Iterable[FixtureOperation],
    *,
    expected_mint: str,
    cutoff_slot: int,
) -> MintOriginLookupResult:
    """Bounded mint-scoped finalized origin lookup (fixture-only).

    Uses adopted origin request kinds only. One signature page and at most one
    transaction per mint. Exact mint match required. Zero retries.
    """
    if not isinstance(expected_mint, str) or not expected_mint:
        raise PumpContractError("MALFORMED_TRANSACTION", "expected_mint required")
    if type(cutoff_slot) is not int or cutoff_slot < 0:
        raise PumpContractError("MALFORMED_TRANSACTION", "invalid cutoff")

    origin_request_ceilings = MappingProxyType(
        {
            ORIGIN_SIGNATURE_REQUEST: 1,
            ORIGIN_TRANSACTION_REQUEST: 1,
        }
    )
    port = FixtureOperationPort(
        operations,
        request_ceilings=origin_request_ceilings,
        operation_ceilings=MappingProxyType(
            {"getSignaturesForAddress": 1, "getTransaction": 1}
        ),
    )
    rejections: list[Rejection] = []
    page = port.take("getSignaturesForAddress", ORIGIN_SIGNATURE_REQUEST)
    if not isinstance(page, Mapping) or not isinstance(page.get("rows"), list):
        raise PumpContractError("MALFORMED_TRANSACTION", "bad origin signature page")
    if len(page["rows"]) > ORIGIN_SIGNATURE_PAGE_SIZE:
        raise PumpContractError("BACKFILL_PAGE_SIZE_CEILING")

    rows = [_signature_reference(row) for row in page["rows"]]
    for reference in rows:
        if reference.slot > cutoff_slot:
            rejections.append(
                Rejection("POST_CUTOFF", reference.signature, reference.slot)
            )

    candidates = [
        reference
        for reference in rows
        if reference.slot <= cutoff_slot
    ]
    candidates.sort(key=lambda item: (item.slot, item.signature))

    decode_target: SignatureReference | None = None
    for reference in candidates:
        if reference.err is not None:
            rejections.append(
                Rejection("FAILED_TRANSACTION", reference.signature, reference.slot)
            )
            continue
        if reference.confirmation_status != "finalized":
            rejections.append(
                Rejection("MISSING_FINALITY", reference.signature, reference.slot)
            )
            continue
        decode_target = reference
        break

    observation: PumpCreateObservation | None = None
    decode_attempts = 0
    if decode_target is None:
        rejections.append(Rejection("NOT_SUPPORTED_CREATE", None, None))
    else:
        transaction = port.take("getTransaction", ORIGIN_TRANSACTION_REQUEST)
        decode_attempts = 1
        try:
            observation = decode_finalized_create(
                transaction,
                reference=decode_target,
                cutoff_slot=cutoff_slot,
                expected_mint=expected_mint,
            )
        except PumpContractError as exc:
            rejections.append(
                Rejection(exc.code, decode_target.signature, decode_target.slot)
            )
            observation = None

    port.assert_consumed()
    return MintOriginLookupResult(
        expected_mint=expected_mint,
        observation=observation,
        rejections=tuple(rejections),
        accounting=port.accounting.snapshot(),
        signature_rows=len(rows),
        decode_attempts=decode_attempts,
    )
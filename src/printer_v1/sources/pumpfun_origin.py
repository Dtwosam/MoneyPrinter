"""Signature-anchored finalized Pump origin acquisition owner (V2-9.7E.5).

This is the single primary Pump-origin acquisition architecture. It replaces
the retired cross-call ``getSlot`` cutoff plus whole-program signature polling.

Two architecture defects motivated the reset (see
``docs/printer-v1-v2-9-7e-5-pump-origin-acquisition-architecture.md``):

1. The retired path froze one ``getSlot(finalized)`` value and rejected any
   signature row with ``slot > cutoff``. ``api.mainnet-beta.solana.com`` is a
   multi-backend pool, so that cutoff came from a different node than the
   signature pages. A genuinely finalized row could — and repeatedly did —
   exceed it, emptying the entire usable sample (4D: 32/32, 4H: 32/32).
   The cutoff added no safety the row did not already carry.

2. The retired path polled ``getSignaturesForAddress(PUMP_PROGRAM_ID)``, where
   creates are roughly one percent of activity and are indistinguishable from
   buys and sells without spending one ``getTransaction`` each.

Here the finalized signature row **is** the anchor, and the index address is
the create-exclusive Pump ``mint_authority`` PDA, which appears in ``create``
and not in ``buy``/``sell``.

Fixture-only: every externally observed value enters through FixtureOperation.
There is no transport, no loop, no retry, and no reconnect.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from printer_v1.scheduler.contracts import JobKind
from printer_v1.sources.governor import can_request_source
from printer_v1.sources.pumpfun_direct import (
    CREATE_DISCRIMINATOR,
    CREATE_LAYOUT_LEGACY,
    CREATE_LAYOUT_V2,
    CREATE_V2_DISCRIMINATOR,
    PUMP_IDL_SHA256,
    PUMP_PROGRAM_ID,
    PUMP_REPOSITORY_COMMIT,
    TOKEN_2022_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    PumpContractError,
    PumpCreateObservation,
    SignatureReference,
    decode_finalized_create,
)

# V2-9.7E.6: registry provenance for each adopted layout.
_LAYOUT_DISCRIMINATOR_HEX = MappingProxyType(
    {
        CREATE_LAYOUT_LEGACY: CREATE_DISCRIMINATOR.hex(),
        CREATE_LAYOUT_V2: CREATE_V2_DISCRIMINATOR.hex(),
    }
)
_LAYOUT_TOKEN_PROGRAM = MappingProxyType(
    {
        CREATE_LAYOUT_LEGACY: TOKEN_PROGRAM_ID,
        CREATE_LAYOUT_V2: TOKEN_2022_PROGRAM_ID,
    }
)


# ---------------------------------------------------------------------------
# Contract identities
# ---------------------------------------------------------------------------

# Pump `create` account index 1 (`mint_authority`). Create-exclusive: it signs
# the initial supply mint during `create` and is not an account of buy/sell.
# Already enforced as a fixed identity by the pinned create decoder.
PUMP_CREATE_INDEX_ADDRESS = "TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM"

CONTRACT_VERSION = "V2-9.7E.5"
ACQUISITION_MODE_PROSPECTIVE = "SIGNATURE_ANCHORED_PROSPECTIVE"
ACQUISITION_MODE_SUPPORT_ONLY = "SUPPORT_ONLY_HISTORICAL"

SOURCE_NAME = "solana_rpc"
SCHEDULER_JOB_KIND = JobKind.DISCOVERY_REFRESH.value
SCHEDULER_WORK_TYPE = "DISCOVERY_PUMPFUN_LATEST"

SIGNATURE_PAGE_REQUEST = "pumpfun_create_index_signature_page"
TRANSACTION_REQUEST = "pumpfun_create_index_transaction"

# Minimum-sufficient ceilings; see architecture doc section 3.10. Worst-case
# underlying consumption is 3 + 12 = 15, down from the retired path's 45.
CREATE_INDEX_PAGE_CEILING = 3
CREATE_INDEX_PAGE_SIZE = 16
CREATE_INDEX_DECODE_CEILING = 12
EARLY_CREATE_STOP = 8
UNDERLYING_OPERATION_CEILING = 45

REQUEST_CEILINGS = MappingProxyType(
    {
        SIGNATURE_PAGE_REQUEST: CREATE_INDEX_PAGE_CEILING,
        TRANSACTION_REQUEST: CREATE_INDEX_DECODE_CEILING,
    }
)
_OPERATION_CEILINGS = MappingProxyType(
    {
        "getSignaturesForAddress": CREATE_INDEX_PAGE_CEILING,
        "getTransaction": CREATE_INDEX_DECODE_CEILING,
    }
)

# Factual market noise / productivity stops — never continuity faults.
_NON_FAULT_CLASSIFICATIONS = frozenset(
    {
        "FAILED_TRANSACTION",
        "NOT_SUPPORTED_CREATE",
        "UNSUPPORTED_TRANSACTION_VERSION",
        "UNSUPPORTED_PUMP_CREATE_V2",
        "UNSUPPORTED_PUMP_CREATE_LAYOUT",
        "EARLY_CREATE_STOP",
        "DECODE_CEILING",
    }
)


class RetiredPrimaryPathError(RuntimeError):
    """A retired pre-V2-9.7E.5 acquisition path was invoked as primary."""


class OriginRegistryError(RuntimeError):
    """Fail-closed durable origin registry fault."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}: {detail}")


class ContinuityState(StrEnum):
    CONTIGUOUS = "CONTIGUOUS"
    GAPPED = "GAPPED"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, order=True)
class CursorBoundary:
    slot: int
    signature: str


@dataclass(frozen=True)
class FinalizedOriginCursor:
    boundary: CursorBoundary | None
    continuity: ContinuityState = ContinuityState.UNKNOWN
    index_address: str = PUMP_CREATE_INDEX_ADDRESS


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
class AcquisitionCycleResult:
    """Outcome of one bounded signature-anchored acquisition cycle."""

    index_address: str
    anchor: CursorBoundary | None
    observations: tuple[PumpCreateObservation, ...]
    rejections: tuple[Rejection, ...]
    cursor: FinalizedOriginCursor
    accounting: AccountingSnapshot
    pages_used: int = 0
    signature_rows: int = 0
    admitted_rows: int = 0
    duplicate_signatures: int = 0
    failed_signature_count: int = 0
    non_create_count: int = 0
    create_v2_count: int = 0
    unsupported_transaction_version_count: int = 0
    unsupported_create_layout_count: int = 0
    decode_attempts: int = 0
    stale_page: bool = False

    def canonical(self) -> tuple[object, ...]:
        """Stable replay identity without mutable or wall-clock values."""
        return (
            self.index_address,
            self.anchor,
            tuple(self.observations),
            tuple(self.rejections),
            self.cursor,
            tuple(sorted(self.accounting.governed_requests.items())),
            self.accounting.underlying_rpc_operations,
            self.pages_used,
            self.signature_rows,
            self.admitted_rows,
            self.duplicate_signatures,
            self.failed_signature_count,
            self.non_create_count,
            self.create_v2_count,
            self.unsupported_transaction_version_count,
            self.unsupported_create_layout_count,
            self.decode_attempts,
            self.stale_page,
        )


# ---------------------------------------------------------------------------
# Governed accounting and fixture port
# ---------------------------------------------------------------------------


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


class _Accounting:
    def __init__(self) -> None:
        self.request_ids: dict[str, set[str]] = {
            request_kind: set() for request_kind in REQUEST_CEILINGS
        }
        self.operation_counts = {operation: 0 for operation in _OPERATION_CEILINGS}
        self.underlying = 0

    def consume(self, operation: FixtureOperation) -> None:
        if operation.request_kind not in REQUEST_CEILINGS:
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
            if len(request_ids) >= REQUEST_CEILINGS[operation.request_kind]:
                raise PumpContractError("GOVERNED_REQUEST_CEILING")
            request_ids.add(operation.request_id)
        if operation.rpc_operation not in self.operation_counts:
            raise PumpContractError("UNADOPTED_RPC_OPERATION")
        if (
            self.operation_counts[operation.rpc_operation]
            >= _OPERATION_CEILINGS[operation.rpc_operation]
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

    def __init__(self, operations: Iterable[FixtureOperation]) -> None:
        self._operations = tuple(operations)
        self._index = 0
        self.accounting = _Accounting()

    def peek(self) -> FixtureOperation | None:
        return (
            self._operations[self._index]
            if self._index < len(self._operations)
            else None
        )

    def take(self, rpc_operation: str, request_kind: str) -> Any:
        operation = self.peek()
        if operation is None:
            raise PumpContractError("UNAVAILABLE_HISTORY", f"missing {rpc_operation}")
        if operation.source_name != SOURCE_NAME or operation.request_kind != request_kind:
            raise PumpContractError("SOURCE_GOVERNOR_BYPASS")
        if (
            operation.scheduler_job_kind != SCHEDULER_JOB_KIND
            or operation.scheduler_work_type != SCHEDULER_WORK_TYPE
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
        remaining = self.peek()
        if remaining is not None:
            raise PumpContractError("UNPLANNED_OPERATION", remaining.rpc_operation)


def _signature_reference(row: Mapping[str, Any]) -> SignatureReference:
    try:
        signature = row["signature"]
        slot = row["slot"]
        status = row["confirmationStatus"]
    except (KeyError, TypeError) as exc:
        raise PumpContractError("MALFORMED_TRANSACTION", "bad signature row") from exc
    if (
        not isinstance(signature, str)
        or not signature
        or type(slot) is not int
        or slot < 0
        or not isinstance(status, str)
    ):
        raise PumpContractError("MALFORMED_TRANSACTION", "bad signature row")
    return SignatureReference(signature, slot, status, row.get("err"))


# ---------------------------------------------------------------------------
# Primary acquisition cycle
# ---------------------------------------------------------------------------


def run_acquisition_cycle(
    operations: Iterable[FixtureOperation],
    *,
    prior_cursor: FinalizedOriginCursor | None = None,
    index_address: str = PUMP_CREATE_INDEX_ADDRESS,
) -> AcquisitionCycleResult:
    """Run one bounded signature-anchored finalized create acquisition cycle.

    The anchor is the newest admitted finalized signature row. No independent
    ``getSlot`` snapshot is taken, so no cross-backend cutoff race exists.
    """
    prior = prior_cursor or FinalizedOriginCursor(None, ContinuityState.UNKNOWN)
    port = FixtureOperationPort(operations)

    pages_used = 0
    page_rows: list[SignatureReference] = []
    boundary_reached = prior.boundary is None
    history_unavailable = False
    saw_short_page = False

    while (
        pages_used < CREATE_INDEX_PAGE_CEILING
        and port.peek() is not None
        and port.peek().rpc_operation == "getSignaturesForAddress"
    ):
        page = port.take("getSignaturesForAddress", SIGNATURE_PAGE_REQUEST)
        pages_used += 1
        if not isinstance(page, Mapping) or not isinstance(page.get("rows"), list):
            raise PumpContractError("MALFORMED_TRANSACTION", "bad signature page")
        rows = page["rows"]
        if len(rows) > CREATE_INDEX_PAGE_SIZE:
            raise PumpContractError("SIGNATURE_PAGE_SIZE_CEILING")
        if not rows:
            # Empty page: history unavailable or fully walked. Never a retry.
            history_unavailable = True
            break
        references = [_signature_reference(row) for row in rows]
        page_rows.extend(references)
        if prior.boundary is not None and any(
            reference.signature == prior.boundary.signature for reference in references
        ):
            boundary_reached = True
            break
        if len(rows) < CREATE_INDEX_PAGE_SIZE:
            # Short page and boundary not seen: retention ended before it.
            saw_short_page = True
            break

    # --- Admission: the finalized row is its own anchor. -------------------
    rejections: list[Rejection] = []
    duplicates = 0
    failed_signature_count = 0
    references: dict[str, SignatureReference] = {}
    conflicting: set[str] = set()
    continuity_fault = False

    for reference in page_rows:
        if reference.signature in conflicting:
            duplicates += 1
            continue
        previous = references.get(reference.signature)
        if previous is not None:
            duplicates += 1
            if previous != reference:
                # Same signature, different slot: fork or backend disagreement.
                references.pop(reference.signature)
                conflicting.add(reference.signature)
                rejections.append(
                    Rejection("CONFLICTING_DUPLICATE", reference.signature, reference.slot)
                )
                continuity_fault = True
            continue
        if reference.confirmation_status != "finalized":
            rejections.append(
                Rejection("MISSING_FINALITY", reference.signature, reference.slot)
            )
            continue
        if reference.err is not None:
            rejections.append(
                Rejection("FAILED_TRANSACTION", reference.signature, reference.slot)
            )
            failed_signature_count += 1
            continue
        references[reference.signature] = reference

    admitted_ordered = sorted(
        references.values(), key=lambda item: (item.slot, item.signature)
    )

    # Newest admitted row is the cycle anchor.
    anchor = (
        CursorBoundary(admitted_ordered[-1].slot, admitted_ordered[-1].signature)
        if admitted_ordered
        else None
    )

    # A page entirely older than the stored boundary must not rewind it.
    stale_page = bool(
        prior.boundary is not None
        and anchor is not None
        and (anchor.slot, anchor.signature) <= (prior.boundary.slot, prior.boundary.signature)
    )

    # --- Bounded finalized confirmation and decode -------------------------
    # Rows at or older than the stored boundary were already confirmed by an
    # earlier cycle. Re-decoding them would spend budget to relearn a fact the
    # registry already holds.
    if prior.boundary is None:
        decode_queue = list(admitted_ordered)
    else:
        floor = (prior.boundary.slot, prior.boundary.signature)
        decode_queue = [
            reference
            for reference in admitted_ordered
            if (reference.slot, reference.signature) > floor
        ]
    if len(decode_queue) > CREATE_INDEX_DECODE_CEILING:
        for reference in decode_queue[CREATE_INDEX_DECODE_CEILING:]:
            rejections.append(
                Rejection("DECODE_CEILING", reference.signature, reference.slot)
            )
        decode_queue = decode_queue[:CREATE_INDEX_DECODE_CEILING]

    observations: list[PumpCreateObservation] = []
    decode_attempts = 0
    non_create_count = 0
    create_v2_count = 0
    unsupported_transaction_version_count = 0
    unsupported_create_layout_count = 0
    for reference in decode_queue:
        if len(observations) >= EARLY_CREATE_STOP:
            rejections.append(
                Rejection("EARLY_CREATE_STOP", reference.signature, reference.slot)
            )
            continue
        if port.peek() is None or port.peek().rpc_operation != "getTransaction":
            # No planned confirmation remains. Never invent a fetch.
            break
        transaction = port.take("getTransaction", TRANSACTION_REQUEST)
        decode_attempts += 1
        try:
            # cutoff_slot is the row's own slot: the retired POST_CUTOFF branch
            # is unreachable from this path by construction.
            observation = decode_finalized_create(
                transaction, reference=reference, cutoff_slot=reference.slot
            )
        except PumpContractError as exc:
            rejections.append(Rejection(exc.code, reference.signature, reference.slot))
            if exc.code == "NOT_SUPPORTED_CREATE":
                non_create_count += 1
            elif exc.code == "UNSUPPORTED_PUMP_CREATE_V2":
                create_v2_count += 1
            elif exc.code == "UNSUPPORTED_TRANSACTION_VERSION":
                unsupported_transaction_version_count += 1
            elif exc.code == "UNSUPPORTED_PUMP_CREATE_LAYOUT":
                unsupported_create_layout_count += 1
            elif exc.code not in _NON_FAULT_CLASSIFICATIONS:
                continuity_fault = True
        else:
            observations.append(observation)

    port.assert_consumed()

    # --- Continuity resolution --------------------------------------------
    if history_unavailable and not page_rows:
        state = ContinuityState.UNAVAILABLE
    elif prior.boundary is None:
        # Cold start: the interval before this page was never observed.
        state = ContinuityState.UNKNOWN
    elif continuity_fault or saw_short_page or history_unavailable or not boundary_reached:
        state = ContinuityState.GAPPED
    else:
        state = ContinuityState.CONTIGUOUS

    if anchor is not None and not stale_page:
        boundary = anchor
    else:
        boundary = prior.boundary

    return AcquisitionCycleResult(
        index_address=index_address,
        anchor=anchor,
        observations=tuple(observations),
        rejections=tuple(rejections),
        cursor=FinalizedOriginCursor(boundary, state, index_address),
        accounting=port.accounting.snapshot(),
        pages_used=pages_used,
        signature_rows=len(page_rows),
        admitted_rows=len(admitted_ordered),
        duplicate_signatures=duplicates,
        failed_signature_count=failed_signature_count,
        non_create_count=non_create_count,
        create_v2_count=create_v2_count,
        unsupported_transaction_version_count=unsupported_transaction_version_count,
        unsupported_create_layout_count=unsupported_create_layout_count,
        decode_attempts=decode_attempts,
        stale_page=stale_page,
    )


# ---------------------------------------------------------------------------
# Durable prospective origin registry
# ---------------------------------------------------------------------------


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def origin_evidence_hash(observation: PumpCreateObservation) -> str:
    """sha256 of the canonical decoded payload. Never a raw RPC response."""
    payload = {
        "mint": observation.mint,
        "signature": observation.signature,
        "slot": observation.slot,
        "block_time": observation.block_time,
        "program_id": observation.program_id,
        "bonding_curve": observation.bonding_curve,
        "associated_bonding_curve": observation.associated_bonding_curve,
        "creator_address": observation.creator_address,
        "create_layout": observation.create_layout,
        "contract_version": CONTRACT_VERSION,
        "idl_sha256": PUMP_IDL_SHA256,
        "repository_commit": PUMP_REPOSITORY_COMMIT,
    }
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def record_confirmed_origin(
    connection: Any,
    observation: PumpCreateObservation,
    *,
    now: str,
    acquisition_mode: str = ACQUISITION_MODE_PROSPECTIVE,
    index_address: str = PUMP_CREATE_INDEX_ADDRESS,
) -> bool:
    """Insert one immutable confirmed origin. Returns True when newly written.

    Idempotent for a byte-identical re-confirmation. A different signature or
    slot for a known mint is fail-closed as ORIGIN_REGISTRY_CONFLICT.
    """
    if observation.program_id != PUMP_PROGRAM_ID:
        raise OriginRegistryError("ORIGIN_REGISTRY_PROGRAM_MISMATCH")
    if acquisition_mode not in (
        ACQUISITION_MODE_PROSPECTIVE,
        ACQUISITION_MODE_SUPPORT_ONLY,
    ):
        raise OriginRegistryError("ORIGIN_REGISTRY_UNKNOWN_MODE", acquisition_mode)
    evidence_hash = origin_evidence_hash(observation)
    existing = connection.execute(
        """
        SELECT transaction_signature, slot, block_time, bonding_curve,
               associated_bonding_curve, creator_address, evidence_hash
        FROM printer_pumpfun_finalized_origin_registry
        WHERE mint_identity = ?
        """,
        (observation.mint,),
    ).fetchone()
    if existing is not None:
        if (
            existing["transaction_signature"] == observation.signature
            and int(existing["slot"]) == int(observation.slot)
            and existing["evidence_hash"] == evidence_hash
        ):
            return False
        raise OriginRegistryError(
            "ORIGIN_REGISTRY_CONFLICT",
            f"conflicting confirmed origin for mint {observation.mint}",
        )
    connection.execute(
        """
        INSERT INTO printer_pumpfun_finalized_origin_registry(
            mint_identity, transaction_signature, slot, block_time, program_id,
            bonding_curve, associated_bonding_curve, creator_address,
            creator_evidence_scope, origin_state, acquisition_mode,
            create_layout, create_discriminator_hex, token_program,
            index_address, contract_version, idl_sha256, evidence_hash,
            first_confirmed_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            observation.mint,
            observation.signature,
            int(observation.slot),
            int(observation.block_time),
            observation.program_id,
            observation.bonding_curve,
            observation.associated_bonding_curve,
            observation.creator_address,
            observation.creator_evidence_scope,
            "PUMPFUN_ORIGIN_CONFIRMED",
            acquisition_mode,
            observation.create_layout,
            _LAYOUT_DISCRIMINATOR_HEX[observation.create_layout],
            _LAYOUT_TOKEN_PROGRAM[observation.create_layout],
            index_address,
            CONTRACT_VERSION,
            PUMP_IDL_SHA256,
            evidence_hash,
            now,
        ),
    )
    return True


def lookup_confirmed_origin(connection: Any, mint_identity: str) -> Mapping[str, Any] | None:
    """Exact-mint durable origin lookup. Zero RPC, zero historical rediscovery."""
    if not isinstance(mint_identity, str) or not mint_identity:
        return None
    row = connection.execute(
        """
        SELECT mint_identity, transaction_signature, slot, block_time, program_id,
               bonding_curve, associated_bonding_curve, creator_address,
               acquisition_mode, create_layout, create_discriminator_hex,
               token_program, evidence_hash, first_confirmed_at
        FROM printer_pumpfun_finalized_origin_registry
        WHERE mint_identity = ?
        """,
        (mint_identity,),
    ).fetchone()
    if row is None:
        return None
    return MappingProxyType(dict(row))


def load_origin_cursor(
    connection: Any, index_address: str = PUMP_CREATE_INDEX_ADDRESS
) -> FinalizedOriginCursor:
    row = connection.execute(
        """
        SELECT boundary_slot, boundary_signature, continuity_state
        FROM printer_pumpfun_origin_cursor WHERE index_address = ?
        """,
        (index_address,),
    ).fetchone()
    if row is None:
        return FinalizedOriginCursor(None, ContinuityState.UNKNOWN, index_address)
    boundary = (
        CursorBoundary(int(row["boundary_slot"]), str(row["boundary_signature"]))
        if row["boundary_slot"] is not None
        else None
    )
    return FinalizedOriginCursor(
        boundary, ContinuityState(row["continuity_state"]), index_address
    )


def save_origin_cursor(
    connection: Any, cursor: FinalizedOriginCursor, *, now: str
) -> None:
    connection.execute(
        """
        INSERT INTO printer_pumpfun_origin_cursor(
            index_address, boundary_slot, boundary_signature,
            continuity_state, updated_at
        ) VALUES (?,?,?,?,?)
        ON CONFLICT(index_address) DO UPDATE SET
            boundary_slot = excluded.boundary_slot,
            boundary_signature = excluded.boundary_signature,
            continuity_state = excluded.continuity_state,
            updated_at = excluded.updated_at
        """,
        (
            cursor.index_address,
            cursor.boundary.slot if cursor.boundary else None,
            cursor.boundary.signature if cursor.boundary else None,
            str(cursor.continuity),
            now,
        ),
    )

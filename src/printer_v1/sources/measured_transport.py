"""Measured transport-operation identities for ordinary discovery/selection.

Six independent budget units (never mixed into one counter):

* SOURCE_TRANSPORT_OPERATION
* LOCAL_VALIDATION_STEP
* SCHEDULER_WORK_ITEM
* SOURCE_RESPONSE_BYTES
* NORMALIZED_SOURCE_ROWS
* LIFECYCLE_RESERVED_TRANSPORT_OPERATION

A transport identity is one actual outbound HTTP or JSON-RPC call. Parsing,
decoding and validation never count. Missing, duplicate or over-ceiling
identities fail closed before continuation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, Sequence


UNIT_SOURCE_TRANSPORT_OPERATION = "SOURCE_TRANSPORT_OPERATION"
UNIT_LOCAL_VALIDATION_STEP = "LOCAL_VALIDATION_STEP"
UNIT_SCHEDULER_WORK_ITEM = "SCHEDULER_WORK_ITEM"
UNIT_SOURCE_RESPONSE_BYTES = "SOURCE_RESPONSE_BYTES"
UNIT_NORMALIZED_SOURCE_ROWS = "NORMALIZED_SOURCE_ROWS"
UNIT_LIFECYCLE_RESERVED_TRANSPORT_OPERATION = (
    "LIFECYCLE_RESERVED_TRANSPORT_OPERATION"
)

SIX_UNITS = (
    UNIT_SOURCE_TRANSPORT_OPERATION,
    UNIT_LOCAL_VALIDATION_STEP,
    UNIT_SCHEDULER_WORK_ITEM,
    UNIT_SOURCE_RESPONSE_BYTES,
    UNIT_NORMALIZED_SOURCE_ROWS,
    UNIT_LIFECYCLE_RESERVED_TRANSPORT_OPERATION,
)

# Single source of truth for governed calls reserved by lifecycle close work.
# WINDOW_CLOSE retains the established 15m bundle. CONTINUATION_CLOSE reserves
# its exact-pair close observation plus the worst-case fresh first-hour safety
# bundle: GoPlus + Solana core mint-account + holder primary + one approved
# holder backup.
PRECLOSE_CONTEXT_REQUEST_COUNT = 6
FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT = 4
LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND = MappingProxyType(
    {
        "SNAPSHOT": 1,
        "WINDOW_CLOSE": 1 + PRECLOSE_CONTEXT_REQUEST_COUNT,
        "CONTINUATION_CLOSE": 1 + FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT,
    }
)

# Stage transport ceilings (measured budget architecture).
STAGE_CEILINGS = MappingProxyType(
    {
        "DIRECT_PUMP_NOMINATION": 13,
        "PUMPSWAP_EXACT_VERIFICATION": 20,
        "DEXSCREENER_DISCOVERY": 30,
        "CANDIDATE_SUPPLY_AGGREGATE": 46,
        "HOLDER_SAFETY": 10,
        "READINESS_ONLY": 6,
        "WINDOW_15M_OBSERVATIONS": 64,
        "PRE_CLOSE_CONTEXT": 16,
    }
)

# Per-operation response byte ceilings.
BYTE_CEILINGS = MappingProxyType(
    {
        "solana_rpc": 1_048_576,
        "dexscreener_profiles": 2_000_000,
        "dexscreener_pair": 512_000,
        "default": 1_048_576,
    }
)

# Normalized row ceilings (fail closed when undeclared for multi-row adapters).
ROW_CEILINGS = MappingProxyType(
    {
        "pump_migration_observations": 12,
        "pumpswap_confirmations": 5,
        "dexscreener_fresh_profile_mints": 30,
        "dexscreener_exact_pair_rows": 8,
        "holder_facts": 2,
        "readiness_snapshots": 2,
        "lifecycle_snapshots": 32,
    }
)

MAX_PUMPSWAP_ACCOUNT_BATCHES = 3
GET_MULTIPLE_ACCOUNTS_BATCH_SIZE = 100


class MeasuredTransportError(RuntimeError):
    """Fail-closed measured-transport accounting fault."""


def pumpswap_account_batch_count(account_key_count: int) -> int:
    """Return 1..3 getMultipleAccounts batches for a transaction key set."""
    if account_key_count < 0:
        raise MeasuredTransportError("NEGATIVE_ACCOUNT_KEY_COUNT")
    if account_key_count == 0:
        return 1
    batches = (account_key_count + GET_MULTIPLE_ACCOUNTS_BATCH_SIZE - 1) // (
        GET_MULTIPLE_ACCOUNTS_BATCH_SIZE
    )
    if batches > MAX_PUMPSWAP_ACCOUNT_BATCHES:
        raise MeasuredTransportError("PUMPSWAP_ACCOUNT_BATCH_CEILING")
    return max(1, batches)


def pumpswap_verification_transport_count(account_key_count: int) -> int:
    """One getTransaction plus required account batches."""
    return 1 + pumpswap_account_batch_count(account_key_count)


@dataclass(frozen=True)
class TransportOperationIdentity:
    """One actual outbound HTTP/RPC attempt identity."""

    stage: str
    source_name: str
    endpoint_owner: str
    governed_request_kind: str
    method_or_endpoint: str
    within_request_ordinal: int
    target_category: str
    target_identity: str | None = None
    response_bytes: int = 0
    normalized_rows: int = 0
    result: str = "ATTEMPTED"
    reserved_from: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "source_name": self.source_name,
            "endpoint_owner": self.endpoint_owner,
            "governed_request_kind": self.governed_request_kind,
            "method_or_endpoint": self.method_or_endpoint,
            "within_request_ordinal": int(self.within_request_ordinal),
            "target_category": self.target_category,
            "target_identity": self.target_identity,
            "response_bytes": int(self.response_bytes),
            "normalized_rows": int(self.normalized_rows),
            "result": self.result,
            "reserved_from": self.reserved_from,
            "unit": UNIT_SOURCE_TRANSPORT_OPERATION,
        }


def canonical_transport_identity_key(identity: Any) -> tuple[object, ...]:
    """Return the single canonical transport identity key used across Printer.

    The key intentionally excludes mutable measurements and presentation fields.
    Historical twelve-field serialized keys remain readable and are projected
    onto the approved seven-field identity shape.
    """
    if isinstance(identity, TransportOperationIdentity):
        raw: Any = identity.as_dict()
    else:
        raw = identity

    if isinstance(raw, Mapping):
        values = (
            raw.get("stage"),
            raw.get("source_name"),
            raw.get("governed_request_kind"),
            raw.get("method_or_endpoint"),
            raw.get("within_request_ordinal"),
            raw.get("target_category"),
            raw.get("target_identity"),
        )
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        parts = list(raw)
        if len(parts) == 7:
            values = tuple(parts)
        elif len(parts) == 12:
            # Historical durable key:
            # stage, source, endpoint_owner, request_kind, method, ordinal,
            # target_category, target_identity, bytes, rows, result, reservation.
            values = (
                parts[0], parts[1], parts[3], parts[4], parts[5], parts[6], parts[7]
            )
        else:
            raise MeasuredTransportError("TRANSPORT_IDENTITY_MALFORMED")
    else:
        raise MeasuredTransportError("TRANSPORT_IDENTITY_MALFORMED")

    stage, source, request_kind, method, ordinal_raw, target_category, target = values
    required = (stage, source, request_kind, method, target_category)
    if any(not str(value or "").strip() for value in required):
        raise MeasuredTransportError("TRANSPORT_IDENTITY_MALFORMED")
    if isinstance(ordinal_raw, bool):
        raise MeasuredTransportError("TRANSPORT_IDENTITY_MALFORMED")
    try:
        ordinal = int(ordinal_raw)
    except (TypeError, ValueError) as exc:
        raise MeasuredTransportError("TRANSPORT_IDENTITY_MALFORMED") from exc
    if ordinal < 0:
        raise MeasuredTransportError("TRANSPORT_IDENTITY_MALFORMED")
    return (
        str(stage),
        str(source),
        str(request_kind),
        str(method),
        ordinal,
        str(target_category),
        None if target is None else str(target),
    )


@dataclass
class MeasuredTransportLedger:
    """In-memory ledger for one campaign stage or discovery attempt.

    ``on_transport_recorded`` is an optional verification-only observer fired
    after a transport identity is accepted into this ledger. It is not a second
    campaign accounting authority. Coordinators use it to collect action-local
    transport identities at measurement time, before and separately from stage
    sealing / campaign-owner ingestion.
    """

    campaign_id: str | None = None
    run_id: str | None = None
    cycle_id: str | None = None
    transports: list[TransportOperationIdentity] = field(default_factory=list)
    local_validations: int = 0
    scheduler_work_items: int = 0
    lifecycle_reservations: int = 0
    on_transport_recorded: Callable[[TransportOperationIdentity], None] | None = field(
        default=None, repr=False, compare=False
    )
    _seen_keys: set[tuple[Any, ...]] = field(default_factory=set, repr=False)

    def record_transport(
        self,
        identity: TransportOperationIdentity,
        *,
        stage_ceiling: int | None = None,
        byte_ceiling: int | None = None,
    ) -> None:
        key = canonical_transport_identity_key(identity)
        if key in self._seen_keys:
            raise MeasuredTransportError("DUPLICATE_TRANSPORT_IDENTITY")
        ceiling = (
            STAGE_CEILINGS.get(identity.stage)
            if stage_ceiling is None
            else int(stage_ceiling)
        )
        stage_count = sum(1 for item in self.transports if item.stage == identity.stage)
        if ceiling is not None and stage_count + 1 > int(ceiling):
            raise MeasuredTransportError(
                f"STAGE_TRANSPORT_CEILING:{identity.stage}:{ceiling}"
            )
        bytes_ceiling = (
            BYTE_CEILINGS.get(identity.source_name, BYTE_CEILINGS["default"])
            if byte_ceiling is None
            else int(byte_ceiling)
        )
        if int(identity.response_bytes) > int(bytes_ceiling):
            raise MeasuredTransportError(
                f"SOURCE_RESPONSE_BYTE_CEILING:{identity.source_name}"
            )
        if int(identity.response_bytes) < 0 or int(identity.normalized_rows) < 0:
            raise MeasuredTransportError("NEGATIVE_TRANSPORT_MEASURE")
        self._seen_keys.add(key)
        self.transports.append(identity)
        # Verification-only fan-out: fires at measurement time, before seal.
        if self.on_transport_recorded is not None:
            self.on_transport_recorded(identity)

    def record_local_validation(self, count: int = 1) -> None:
        if count < 0:
            raise MeasuredTransportError("NEGATIVE_LOCAL_VALIDATION")
        self.local_validations += int(count)

    def record_scheduler_work_item(self, count: int = 1) -> None:
        if count < 0:
            raise MeasuredTransportError("NEGATIVE_SCHEDULER_WORK_ITEM")
        self.scheduler_work_items += int(count)

    def reserve_lifecycle_transports(self, count: int) -> None:
        if count < 0:
            raise MeasuredTransportError("NEGATIVE_LIFECYCLE_RESERVATION")
        self.lifecycle_reservations += int(count)

    def release_lifecycle_reservations(self, count: int | None = None) -> None:
        if count is None:
            self.lifecycle_reservations = 0
            return
        if count < 0 or count > self.lifecycle_reservations:
            raise MeasuredTransportError("INVALID_RESERVATION_RELEASE")
        self.lifecycle_reservations -= int(count)

    def extend(self, other: "MeasuredTransportLedger") -> None:
        for item in other.transports:
            self.record_transport(item)
        self.local_validations += other.local_validations
        self.scheduler_work_items += other.scheduler_work_items
        self.lifecycle_reservations += other.lifecycle_reservations

    @property
    def source_transport_operations(self) -> int:
        return len(self.transports)

    @property
    def source_response_bytes(self) -> int:
        return sum(int(item.response_bytes) for item in self.transports)

    @property
    def normalized_source_rows(self) -> int:
        return sum(int(item.normalized_rows) for item in self.transports)

    def six_unit_totals(self) -> dict[str, int]:
        return {
            UNIT_SOURCE_TRANSPORT_OPERATION: self.source_transport_operations,
            UNIT_LOCAL_VALIDATION_STEP: int(self.local_validations),
            UNIT_SCHEDULER_WORK_ITEM: int(self.scheduler_work_items),
            UNIT_SOURCE_RESPONSE_BYTES: self.source_response_bytes,
            UNIT_NORMALIZED_SOURCE_ROWS: self.normalized_source_rows,
            UNIT_LIFECYCLE_RESERVED_TRANSPORT_OPERATION: int(
                self.lifecycle_reservations
            ),
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "run_id": self.run_id,
            "cycle_id": self.cycle_id,
            "six_unit_totals": self.six_unit_totals(),
            "transport_operations": [item.as_dict() for item in self.transports],
            "transport_operation_count": self.source_transport_operations,
        }


@dataclass(frozen=True)
class SchedulerWorkIdentity:
    """One campaign-owned Scheduler work item identity (non-transport unit).

    Identity key is ``stage_id + scheduler_job_id + job_kind + target``. Two
    distinct stages may reference distinct jobs; the same job id must never be
    projected into two accounting stages under a different identity.
    """

    stage_id: str
    scheduler_job_id: int
    job_kind: str
    target_category: str
    target_identity: str | None = None

    def identity_key(self) -> tuple[Any, ...]:
        return (
            str(self.stage_id or ""),
            int(self.scheduler_job_id),
            str(self.job_kind or ""),
            str(self.target_category or ""),
            None if self.target_identity is None else str(self.target_identity),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "scheduler_job_id": int(self.scheduler_job_id),
            "job_kind": self.job_kind,
            "target_category": self.target_category,
            "target_identity": self.target_identity,
            "unit": UNIT_SCHEDULER_WORK_ITEM,
        }


@dataclass(frozen=True)
class LifecycleReservationIdentity:
    """One lifecycle transport reservation identity (non-transport unit).

    Identity key is
    ``stage_id + factory_run_id + token/pair + window_kind + reservation_ordinal``.
    """

    stage_id: str
    factory_run_id: str
    token_id: int
    pair_id: int
    window_kind: str
    reservation_ordinal: int

    def identity_key(self) -> tuple[Any, ...]:
        return (
            str(self.stage_id or ""),
            str(self.factory_run_id or ""),
            int(self.token_id),
            int(self.pair_id),
            str(self.window_kind or ""),
            int(self.reservation_ordinal),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "factory_run_id": self.factory_run_id,
            "token_id": int(self.token_id),
            "pair_id": int(self.pair_id),
            "window_kind": self.window_kind,
            "reservation_ordinal": int(self.reservation_ordinal),
            "unit": UNIT_LIFECYCLE_RESERVED_TRANSPORT_OPERATION,
        }


@dataclass(frozen=True)
class LocalValidationIdentity:
    """One named local validation identity (non-transport unit).

    Identity key is
    ``stage_id + subject_identity + validation_kind + validation_ordinal``. The
    subject is a factory step or window identity that the validation ran against.
    """

    stage_id: str
    subject_identity: str
    validation_kind: str
    validation_ordinal: int

    def identity_key(self) -> tuple[Any, ...]:
        return (
            str(self.stage_id or ""),
            str(self.subject_identity or ""),
            str(self.validation_kind or ""),
            int(self.validation_ordinal),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "subject_identity": self.subject_identity,
            "validation_kind": self.validation_kind,
            "validation_ordinal": int(self.validation_ordinal),
            "unit": UNIT_LOCAL_VALIDATION_STEP,
        }


def enforce_normalized_row_ceiling(
    kind: str, row_count: int, *, declared: Mapping[str, int] | None = None
) -> None:
    ceilings = ROW_CEILINGS if declared is None else declared
    if kind not in ceilings:
        raise MeasuredTransportError(f"NORMALIZED_ROW_CEILING_UNDECLARED:{kind}")
    if int(row_count) > int(ceilings[kind]):
        raise MeasuredTransportError(f"NORMALIZED_ROW_CEILING:{kind}")


def reconcile_six_unit_totals(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> dict[str, Any]:
    """Return equality report for report/replay six-unit totals."""
    left_totals = dict(left.get("six_unit_totals") or left)
    right_totals = dict(right.get("six_unit_totals") or right)
    mismatches: dict[str, dict[str, int]] = {}
    for unit in SIX_UNITS:
        lv = int(left_totals.get(unit) or 0)
        rv = int(right_totals.get(unit) or 0)
        if lv != rv:
            mismatches[unit] = {"left": lv, "right": rv}
    return {
        "equal": not mismatches,
        "mismatches": mismatches,
        "left": {unit: int(left_totals.get(unit) or 0) for unit in SIX_UNITS},
        "right": {unit: int(right_totals.get(unit) or 0) for unit in SIX_UNITS},
    }


def merge_transport_payload_metadata(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Extract measured metadata from a transport/normalized payload."""
    if not isinstance(payload, Mapping):
        return {
            "transport_operations_used": 0,
            "response_bytes": 0,
            "normalized_rows": 0,
            "transport_operation_identities": (),
        }
    identities = payload.get("transport_operation_identities") or ()
    if not isinstance(identities, Sequence) or isinstance(identities, (str, bytes)):
        identities = ()
    used = payload.get("transport_operations_used")
    if used is None:
        used = len(identities) if identities else 0
    return {
        "transport_operations_used": int(used or 0),
        "response_bytes": int(payload.get("response_bytes") or 0),
        "normalized_rows": int(payload.get("normalized_rows") or 0),
        "transport_operation_identities": tuple(identities),
    }


def empty_six_unit_totals() -> dict[str, int]:
    return {unit: 0 for unit in SIX_UNITS}


def build_transport_identity(
    *,
    stage: str,
    source_name: str,
    endpoint_owner: str,
    governed_request_kind: str,
    method_or_endpoint: str,
    within_request_ordinal: int,
    target_category: str,
    target_identity: str | None = None,
    response_bytes: int = 0,
    normalized_rows: int = 0,
    result: str = "OK",
    reserved_from: str | None = None,
) -> TransportOperationIdentity:
    """Construct one measured transport identity for an actual outbound call."""
    return TransportOperationIdentity(
        stage=stage,
        source_name=source_name,
        endpoint_owner=endpoint_owner,
        governed_request_kind=governed_request_kind,
        method_or_endpoint=method_or_endpoint,
        within_request_ordinal=int(within_request_ordinal),
        target_category=target_category,
        target_identity=target_identity,
        response_bytes=int(response_bytes),
        normalized_rows=int(normalized_rows),
        result=str(result),
        reserved_from=reserved_from,
    )


def measured_payload_fields(
    identities: Sequence[TransportOperationIdentity | Mapping[str, Any]],
    *,
    response_bytes: int | None = None,
    normalized_rows: int | None = None,
) -> dict[str, Any]:
    """Serialize measured metadata attached to a transport/normalized payload."""
    identity_dicts: list[dict[str, Any]] = []
    for item in identities:
        if isinstance(item, TransportOperationIdentity):
            identity_dicts.append(item.as_dict())
        elif isinstance(item, Mapping):
            identity_dicts.append(dict(item))
        else:
            raise MeasuredTransportError("INVALID_TRANSPORT_IDENTITY_PAYLOAD")
    bytes_total = (
        int(response_bytes)
        if response_bytes is not None
        else sum(int(item.get("response_bytes") or 0) for item in identity_dicts)
    )
    rows_total = (
        int(normalized_rows)
        if normalized_rows is not None
        else sum(int(item.get("normalized_rows") or 0) for item in identity_dicts)
    )
    return {
        "transport_operations_used": len(identity_dicts),
        "response_bytes": bytes_total,
        "normalized_rows": rows_total,
        "transport_operation_identities": identity_dicts,
    }


def identities_from_payload(
    payload: Mapping[str, Any] | None,
) -> list[TransportOperationIdentity]:
    """Rehydrate transport identities declared on a payload."""
    meta = merge_transport_payload_metadata(payload)
    out: list[TransportOperationIdentity] = []
    for raw in meta["transport_operation_identities"]:
        if not isinstance(raw, Mapping):
            raise MeasuredTransportError("MALFORMED_TRANSPORT_IDENTITY")
        out.append(
            TransportOperationIdentity(
                stage=str(raw.get("stage") or ""),
                source_name=str(raw.get("source_name") or ""),
                endpoint_owner=str(raw.get("endpoint_owner") or ""),
                governed_request_kind=str(raw.get("governed_request_kind") or ""),
                method_or_endpoint=str(raw.get("method_or_endpoint") or ""),
                within_request_ordinal=int(raw.get("within_request_ordinal") or 0),
                target_category=str(raw.get("target_category") or ""),
                target_identity=(
                    None
                    if raw.get("target_identity") is None
                    else str(raw.get("target_identity"))
                ),
                response_bytes=int(raw.get("response_bytes") or 0),
                normalized_rows=int(raw.get("normalized_rows") or 0),
                result=str(raw.get("result") or "ATTEMPTED"),
                reserved_from=(
                    None
                    if raw.get("reserved_from") is None
                    else str(raw.get("reserved_from"))
                ),
            )
        )
    used = int(meta["transport_operations_used"] or 0)
    if used and not out:
        raise MeasuredTransportError("TRANSPORT_IDENTITIES_MISSING")
    if out and used != len(out):
        raise MeasuredTransportError("TRANSPORT_IDENTITY_COUNT_MISMATCH")
    return out


def record_payload_transports(
    ledger: MeasuredTransportLedger,
    payload: Mapping[str, Any] | None,
    *,
    default_stage: str | None = None,
) -> int:
    """Record every declared transport identity from a payload onto a ledger."""
    identities = identities_from_payload(payload)
    for identity in identities:
        if default_stage and not identity.stage:
            identity = TransportOperationIdentity(
                stage=default_stage,
                source_name=identity.source_name,
                endpoint_owner=identity.endpoint_owner,
                governed_request_kind=identity.governed_request_kind,
                method_or_endpoint=identity.method_or_endpoint,
                within_request_ordinal=identity.within_request_ordinal,
                target_category=identity.target_category,
                target_identity=identity.target_identity,
                response_bytes=identity.response_bytes,
                normalized_rows=identity.normalized_rows,
                result=identity.result,
                reserved_from=identity.reserved_from,
            )
        ledger.record_transport(identity)
    return len(identities)


def six_unit_totals_from_mapping(payload: Mapping[str, Any] | None) -> dict[str, int]:
    """Normalize a six-unit totals mapping from report/activity payloads."""
    if not isinstance(payload, Mapping):
        return empty_six_unit_totals()
    raw = payload.get("six_unit_totals") if "six_unit_totals" in payload else payload
    if not isinstance(raw, Mapping):
        return empty_six_unit_totals()
    return {unit: int(raw.get(unit) or 0) for unit in SIX_UNITS}


def enforce_response_byte_ceiling(
    source_name: str, response_bytes: int, *, ceiling: int | None = None
) -> None:
    limit = (
        BYTE_CEILINGS.get(source_name, BYTE_CEILINGS["default"])
        if ceiling is None
        else int(ceiling)
    )
    if int(response_bytes) > int(limit):
        raise MeasuredTransportError(f"SOURCE_RESPONSE_BYTE_CEILING:{source_name}")
    if int(response_bytes) < 0:
        raise MeasuredTransportError("NEGATIVE_TRANSPORT_MEASURE")


__all__ = [
    "BYTE_CEILINGS",
    "FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT",
    "GET_MULTIPLE_ACCOUNTS_BATCH_SIZE",
    "MAX_PUMPSWAP_ACCOUNT_BATCHES",
    "LifecycleReservationIdentity",
    "LocalValidationIdentity",
    "MeasuredTransportError",
    "MeasuredTransportLedger",
    "ROW_CEILINGS",
    "SIX_UNITS",
    "STAGE_CEILINGS",
    "SchedulerWorkIdentity",
    "TransportOperationIdentity",
    "UNIT_LIFECYCLE_RESERVED_TRANSPORT_OPERATION",
    "UNIT_LOCAL_VALIDATION_STEP",
    "UNIT_NORMALIZED_SOURCE_ROWS",
    "UNIT_SCHEDULER_WORK_ITEM",
    "UNIT_SOURCE_RESPONSE_BYTES",
    "UNIT_SOURCE_TRANSPORT_OPERATION",
    "build_transport_identity",
    "empty_six_unit_totals",
    "enforce_normalized_row_ceiling",
    "enforce_response_byte_ceiling",
    "identities_from_payload",
    "measured_payload_fields",
    "merge_transport_payload_metadata",
    "pumpswap_account_batch_count",
    "pumpswap_verification_transport_count",
    "record_payload_transports",
    "reconcile_six_unit_totals",
    "six_unit_totals_from_mapping",
]

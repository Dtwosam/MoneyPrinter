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
from typing import Any, Iterable, Mapping, Sequence


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


@dataclass
class MeasuredTransportLedger:
    """In-memory ledger for one campaign stage or discovery attempt."""

    campaign_id: str | None = None
    run_id: str | None = None
    cycle_id: str | None = None
    transports: list[TransportOperationIdentity] = field(default_factory=list)
    local_validations: int = 0
    scheduler_work_items: int = 0
    lifecycle_reservations: int = 0
    _seen_keys: set[tuple[Any, ...]] = field(default_factory=set, repr=False)

    def record_transport(
        self,
        identity: TransportOperationIdentity,
        *,
        stage_ceiling: int | None = None,
        byte_ceiling: int | None = None,
    ) -> None:
        key = (
            identity.stage,
            identity.source_name,
            identity.governed_request_kind,
            identity.method_or_endpoint,
            identity.within_request_ordinal,
            identity.target_category,
            identity.target_identity,
        )
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


__all__ = [
    "BYTE_CEILINGS",
    "GET_MULTIPLE_ACCOUNTS_BATCH_SIZE",
    "MAX_PUMPSWAP_ACCOUNT_BATCHES",
    "MeasuredTransportError",
    "MeasuredTransportLedger",
    "ROW_CEILINGS",
    "SIX_UNITS",
    "STAGE_CEILINGS",
    "TransportOperationIdentity",
    "UNIT_LIFECYCLE_RESERVED_TRANSPORT_OPERATION",
    "UNIT_LOCAL_VALIDATION_STEP",
    "UNIT_NORMALIZED_SOURCE_ROWS",
    "UNIT_SCHEDULER_WORK_ITEM",
    "UNIT_SOURCE_RESPONSE_BYTES",
    "UNIT_SOURCE_TRANSPORT_OPERATION",
    "empty_six_unit_totals",
    "enforce_normalized_row_ceiling",
    "merge_transport_payload_metadata",
    "pumpswap_account_batch_count",
    "pumpswap_verification_transport_count",
    "reconcile_six_unit_totals",
]

"""Campaign-wide six-unit accounting owner for ordinary discovery/selection.

Durable evidence is the ordered transport identities plus non-transport unit
counters. Report totals are derived from that evidence. Replay reconstructs
totals only from durable evidence and compares them to stored report totals —
never self-compares the same totals field.
"""

from __future__ import annotations

import copy
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from printer_v1.sources.measured_transport import (
    SIX_UNITS,
    UNIT_LIFECYCLE_RESERVED_TRANSPORT_OPERATION,
    UNIT_LOCAL_VALIDATION_STEP,
    UNIT_SCHEDULER_WORK_ITEM,
    LifecycleReservationIdentity,
    LocalValidationIdentity,
    MeasuredTransportError,
    MeasuredTransportLedger,
    SchedulerWorkIdentity,
    TransportOperationIdentity,
    empty_six_unit_totals,
    reconcile_six_unit_totals,
)


class CampaignSixUnitError(RuntimeError):
    """Fail-closed campaign six-unit accounting fault."""


STAGE_TERMINAL_STATUSES = frozenset({"COMPLETED", "BLOCKED", "FAILED"})

# Identity-bearing full-run evidence version. V1 remains readable and replayable
# as historical evidence; V2 additionally carries durable non-transport unit
# identities so totals derive from unique identity sets rather than counters.
EVIDENCE_KIND_V1 = "CAMPAIGN_SIX_UNIT_EVIDENCE_V1"
EVIDENCE_KIND_V2 = "CAMPAIGN_SIX_UNIT_EVIDENCE_V2"

# Non-transport identity list field names carried by V2 evidence.
_SCHEDULER_IDENTITY_FIELD = "scheduler_work_identities"
_RESERVATION_IDENTITY_FIELD = "lifecycle_reservation_identities"
_VALIDATION_IDENTITY_FIELD = "local_validation_identities"
_NON_TRANSPORT_IDENTITY_FIELDS = (
    _SCHEDULER_IDENTITY_FIELD,
    _RESERVATION_IDENTITY_FIELD,
    _VALIDATION_IDENTITY_FIELD,
)


def _scheduler_identity_key(
    raw: Mapping[str, Any] | SchedulerWorkIdentity,
) -> tuple[Any, ...]:
    if isinstance(raw, SchedulerWorkIdentity):
        return raw.identity_key()
    return (
        str(raw.get("stage_id") or ""),
        int(raw.get("scheduler_job_id") or 0),
        str(raw.get("job_kind") or ""),
        str(raw.get("target_category") or ""),
        None if raw.get("target_identity") is None else str(raw.get("target_identity")),
    )


def _reservation_identity_key(
    raw: Mapping[str, Any] | LifecycleReservationIdentity,
) -> tuple[Any, ...]:
    if isinstance(raw, LifecycleReservationIdentity):
        return raw.identity_key()
    return (
        str(raw.get("stage_id") or ""),
        str(raw.get("factory_run_id") or ""),
        int(raw.get("token_id") or 0),
        int(raw.get("pair_id") or 0),
        str(raw.get("window_kind") or ""),
        int(raw.get("reservation_ordinal") or 0),
    )


def _validation_identity_key(
    raw: Mapping[str, Any] | LocalValidationIdentity,
) -> tuple[Any, ...]:
    if isinstance(raw, LocalValidationIdentity):
        return raw.identity_key()
    return (
        str(raw.get("stage_id") or ""),
        str(raw.get("subject_identity") or ""),
        str(raw.get("validation_kind") or ""),
        int(raw.get("validation_ordinal") or 0),
    )


_NON_TRANSPORT_IDENTITY_KEY_FUNCS = {
    _SCHEDULER_IDENTITY_FIELD: _scheduler_identity_key,
    _RESERVATION_IDENTITY_FIELD: _reservation_identity_key,
    _VALIDATION_IDENTITY_FIELD: _validation_identity_key,
}

_NON_TRANSPORT_IDENTITY_UNIT = {
    _SCHEDULER_IDENTITY_FIELD: UNIT_SCHEDULER_WORK_ITEM,
    _RESERVATION_IDENTITY_FIELD: UNIT_LIFECYCLE_RESERVED_TRANSPORT_OPERATION,
    _VALIDATION_IDENTITY_FIELD: UNIT_LOCAL_VALIDATION_STEP,
}

SEALED_STAGE_METADATA_FIELDS = (
    "stage_id",
    "stage_kind",
    "stage_sequence",
    "stage_terminal_status",
    "stage_first_terminal_cause",
    "sealed_at",
    "campaign_id",
    "run_id",
    "cycle_id",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _require_nonempty_text(value: Any, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CampaignSixUnitError(
            f"SIX_UNIT_STAGE_EVIDENCE_MALFORMED:MISSING_{field_name.upper()}"
        )
    return text


def build_campaign_stage_id(
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    stage_kind: str,
    stage_sequence: int,
) -> str:
    """Return a deterministic stage identity for one sealed operational stage."""
    return (
        f"{_require_nonempty_text(campaign_id, field_name='campaign_id')}"
        f"|{_require_nonempty_text(run_id, field_name='run_id')}"
        f"|{_require_nonempty_text(cycle_id, field_name='cycle_id')}"
        f"|{_require_nonempty_text(stage_kind, field_name='stage_kind')}"
        f"|{int(stage_sequence)}"
    )


def seal_campaign_stage_evidence(
    *,
    stage_id: str,
    stage_kind: str,
    stage_sequence: int,
    stage_terminal_status: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    stage_first_terminal_cause: str | None = None,
    sealed_at: str | None = None,
    ledger: MeasuredTransportLedger | None = None,
    evidence: Mapping[str, Any] | None = None,
    scheduler_work_identities: Sequence[
        SchedulerWorkIdentity | Mapping[str, Any]
    ]
    | None = None,
    lifecycle_reservation_identities: Sequence[
        LifecycleReservationIdentity | Mapping[str, Any]
    ]
    | None = None,
    local_validation_identities: Sequence[
        LocalValidationIdentity | Mapping[str, Any]
    ]
    | None = None,
) -> dict[str, Any]:
    """Seal one immutable stage evidence block for campaign-owner ingestion.

    Copies source evidence rather than mutating it. Preserves transport
    identities and non-transport counters. Attaches exact stage and campaign
    identities. Rejects missing IDs, invalid sequence/status, negative counters,
    malformed transports, and empty started-stage evidence. All-zero evidence is
    permitted only for the existing PRE_OPERATION_NO_WORK contract.

    When any non-transport identity list is supplied, the stage is sealed as
    identity-bearing ``CAMPAIGN_SIX_UNIT_EVIDENCE_V2``: the three non-transport
    counters are derived from the unique identity lists so totals cannot be
    forged from a bare integer.
    """
    stage_id_text = _require_nonempty_text(stage_id, field_name="stage_id")
    stage_kind_text = _require_nonempty_text(stage_kind, field_name="stage_kind")
    campaign_id_text = _require_nonempty_text(campaign_id, field_name="campaign_id")
    run_id_text = _require_nonempty_text(run_id, field_name="run_id")
    cycle_id_text = _require_nonempty_text(cycle_id, field_name="cycle_id")
    try:
        sequence = int(stage_sequence)
    except (TypeError, ValueError) as exc:
        raise CampaignSixUnitError(
            "SIX_UNIT_STAGE_EVIDENCE_MALFORMED:INVALID_STAGE_SEQUENCE"
        ) from exc
    if sequence < 1:
        raise CampaignSixUnitError(
            "SIX_UNIT_STAGE_EVIDENCE_MALFORMED:INVALID_STAGE_SEQUENCE"
        )
    status = _require_nonempty_text(
        stage_terminal_status, field_name="stage_terminal_status"
    ).upper()
    if status not in STAGE_TERMINAL_STATUSES:
        raise CampaignSixUnitError(
            "SIX_UNIT_STAGE_EVIDENCE_MALFORMED:INVALID_STAGE_TERMINAL_STATUS"
        )

    if ledger is not None and evidence is not None:
        raise CampaignSixUnitError(
            "SIX_UNIT_STAGE_EVIDENCE_MALFORMED:SEAL_SOURCE_AMBIGUOUS"
        )
    if ledger is None and evidence is None:
        raise CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_MISSING")

    if ledger is not None:
        payload: dict[str, Any] = {
            "evidence_kind": EVIDENCE_KIND_V1,
            "transport_operations": [
                item.as_dict() for item in ledger.transports
            ],
            "local_validations": int(ledger.local_validations),
            "scheduler_work_items": int(ledger.scheduler_work_items),
            "lifecycle_reservations": int(ledger.lifecycle_reservations),
        }
    else:
        if not isinstance(evidence, Mapping) or not evidence:
            raise CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_EMPTY")
        payload = copy.deepcopy(dict(evidence))

    identity_lists = {
        _SCHEDULER_IDENTITY_FIELD: scheduler_work_identities,
        _RESERVATION_IDENTITY_FIELD: lifecycle_reservation_identities,
        _VALIDATION_IDENTITY_FIELD: local_validation_identities,
    }
    counter_field = {
        _SCHEDULER_IDENTITY_FIELD: "scheduler_work_items",
        _RESERVATION_IDENTITY_FIELD: "lifecycle_reservations",
        _VALIDATION_IDENTITY_FIELD: "local_validations",
    }
    is_identity_bearing = any(value is not None for value in identity_lists.values())
    if is_identity_bearing:
        for field_name, supplied in identity_lists.items():
            if supplied is None:
                continue
            if isinstance(supplied, (str, bytes)) or not isinstance(
                supplied, Sequence
            ):
                raise CampaignSixUnitError(
                    f"SIX_UNIT_STAGE_EVIDENCE_MALFORMED:{field_name.upper()}"
                )
            key_func = _NON_TRANSPORT_IDENTITY_KEY_FUNCS[field_name]
            payload_list: list[dict[str, Any]] = []
            seen: set[tuple[Any, ...]] = set()
            for item in supplied:
                record = item.as_dict() if hasattr(item, "as_dict") else dict(item)
                key = key_func(record)
                if key in seen:
                    raise CampaignSixUnitError(
                        f"SIX_UNIT_STAGE_EVIDENCE_DUPLICATE_IDENTITY:{field_name}:{key}"
                    )
                seen.add(key)
                payload_list.append(record)
            payload[field_name] = payload_list
            payload[counter_field[field_name]] = len(payload_list)

    is_pre_operation_no_work = payload.get("phase") == "PRE_OPERATION_NO_WORK"
    try:
        stage_totals = reconstruct_six_unit_totals_from_evidence(payload)
    except CampaignSixUnitError as exc:
        if str(exc).startswith("SIX_UNIT_STAGE_EVIDENCE_"):
            raise
        raise CampaignSixUnitError(
            f"SIX_UNIT_STAGE_EVIDENCE_MALFORMED:{exc}"
        ) from exc

    if is_pre_operation_no_work:
        if (
            payload.get("source_transport_attempted") is not False
            or int(payload.get("source_governor_requests") or 0) != 0
            or payload.get("scheduler_work_exists") is not False
            or payload.get("lifecycle_began") is not False
            or not str(payload.get("no_work_reason") or "").strip()
            or any(int(value) != 0 for value in stage_totals.values())
        ):
            raise CampaignSixUnitError(
                "SIX_UNIT_STAGE_EVIDENCE_MALFORMED:PRE_OPERATION_NO_WORK_CONTRACT"
            )
    elif all(int(value) == 0 for value in stage_totals.values()):
        raise CampaignSixUnitError(
            "SIX_UNIT_STAGE_EVIDENCE_MALFORMED:EMPTY_STARTED_STAGE_EVIDENCE"
        )

    sealed = dict(payload)
    sealed["evidence_kind"] = (
        EVIDENCE_KIND_V2 if is_identity_bearing else EVIDENCE_KIND_V1
    )
    sealed["stage_id"] = stage_id_text
    sealed["stage_kind"] = stage_kind_text
    sealed["stage_sequence"] = sequence
    sealed["stage_terminal_status"] = status
    sealed["stage_first_terminal_cause"] = (
        None
        if stage_first_terminal_cause is None
        else str(stage_first_terminal_cause)
    )
    sealed["sealed_at"] = sealed_at or _utc_now_iso()
    sealed["campaign_id"] = campaign_id_text
    sealed["run_id"] = run_id_text
    sealed["cycle_id"] = cycle_id_text
    # Re-validate after seal metadata is attached (JSON-serializable copy).
    reconstruct_six_unit_totals_from_evidence(sealed)
    return sealed


@dataclass
class CampaignSixUnitOwner:
    """Single owner for one ordinary campaign/discovery attempt's six units."""

    campaign_id: str | None = None
    run_id: str | None = None
    cycle_id: str | None = None
    owner_id: str | None = None
    started_at: str = field(default_factory=_utc_now_iso)
    ended_at: str | None = None
    ledger: MeasuredTransportLedger = field(default_factory=MeasuredTransportLedger)
    stage_evidence_count: int = field(default=0, init=False)
    pre_operation_no_work: bool = field(default=False, init=False)
    pre_operation_no_work_reason: str | None = field(default=None, init=False)
    accounting_block_reason: str | None = field(default=None, init=False)
    ingested_stage_ids: list[str] = field(default_factory=list, init=False)
    sealed_stage_diagnostics: list[dict[str, Any]] = field(
        default_factory=list, init=False
    )
    _ingested_stage_id_set: set[str] = field(default_factory=set, init=False, repr=False)
    # Identity-bearing non-transport unit evidence (V2). Each list is the durable
    # identity record; the paired key set enforces cross-stage uniqueness so unit
    # totals derive from unique identities rather than free integers.
    scheduler_work_identities: list[dict[str, Any]] = field(
        default_factory=list, init=False
    )
    lifecycle_reservation_identities: list[dict[str, Any]] = field(
        default_factory=list, init=False
    )
    local_validation_identities: list[dict[str, Any]] = field(
        default_factory=list, init=False
    )
    identity_mode_units: set[str] = field(default_factory=set, init=False, repr=False)
    _scheduler_identity_keys: set[tuple[Any, ...]] = field(
        default_factory=set, init=False, repr=False
    )
    _reservation_identity_keys: set[tuple[Any, ...]] = field(
        default_factory=set, init=False, repr=False
    )
    _validation_identity_keys: set[tuple[Any, ...]] = field(
        default_factory=set, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if self.owner_id is None:
            self.owner_id = (
                f"six-unit-owner|{self.campaign_id}|{self.run_id}|{self.cycle_id}"
            )
        self.ledger.campaign_id = self.campaign_id
        self.ledger.run_id = self.run_id
        self.ledger.cycle_id = self.cycle_id

    def extend_ledger(self, other: MeasuredTransportLedger) -> None:
        self.ledger.extend(other)

    def record_transport(self, identity: TransportOperationIdentity) -> None:
        self.ledger.record_transport(identity)

    def record_local_validation(self, count: int = 1) -> None:
        self.ledger.record_local_validation(count)

    def record_scheduler_work_item(self, count: int = 1) -> None:
        self.ledger.record_scheduler_work_item(count)

    def reserve_lifecycle_transports(self, count: int) -> None:
        self.ledger.reserve_lifecycle_transports(count)

    def record_scheduler_work_identity(
        self, identity: SchedulerWorkIdentity | Mapping[str, Any]
    ) -> None:
        """Record one durable Scheduler work item identity (non-transport unit).

        The paired counter is bumped so ``six_unit_totals`` derives the
        ``SCHEDULER_WORK_ITEM`` total from unique identities. A duplicate identity
        fails closed before it can inflate the total.
        """
        key = _scheduler_identity_key(identity)
        if key in self._scheduler_identity_keys:
            raise CampaignSixUnitError(
                f"SIX_UNIT_DUPLICATE_SCHEDULER_WORK_IDENTITY:{key}"
            )
        payload = (
            identity.as_dict()
            if isinstance(identity, SchedulerWorkIdentity)
            else dict(identity)
        )
        self._scheduler_identity_keys.add(key)
        self.scheduler_work_identities.append(payload)
        self.ledger.record_scheduler_work_item(1)
        self.identity_mode_units.add(UNIT_SCHEDULER_WORK_ITEM)

    def record_lifecycle_reservation_identity(
        self, identity: LifecycleReservationIdentity | Mapping[str, Any]
    ) -> None:
        """Record one durable lifecycle transport reservation identity."""
        key = _reservation_identity_key(identity)
        if key in self._reservation_identity_keys:
            raise CampaignSixUnitError(
                f"SIX_UNIT_DUPLICATE_LIFECYCLE_RESERVATION_IDENTITY:{key}"
            )
        payload = (
            identity.as_dict()
            if isinstance(identity, LifecycleReservationIdentity)
            else dict(identity)
        )
        self._reservation_identity_keys.add(key)
        self.lifecycle_reservation_identities.append(payload)
        self.ledger.reserve_lifecycle_transports(1)
        self.identity_mode_units.add(UNIT_LIFECYCLE_RESERVED_TRANSPORT_OPERATION)

    def record_local_validation_identity(
        self, identity: LocalValidationIdentity | Mapping[str, Any]
    ) -> None:
        """Record one durable named local validation identity."""
        key = _validation_identity_key(identity)
        if key in self._validation_identity_keys:
            raise CampaignSixUnitError(
                f"SIX_UNIT_DUPLICATE_LOCAL_VALIDATION_IDENTITY:{key}"
            )
        payload = (
            identity.as_dict()
            if isinstance(identity, LocalValidationIdentity)
            else dict(identity)
        )
        self._validation_identity_keys.add(key)
        self.local_validation_identities.append(payload)
        self.ledger.record_local_validation(1)
        self.identity_mode_units.add(UNIT_LOCAL_VALIDATION_STEP)

    def non_transport_identity_keys(self) -> dict[str, set[tuple[Any, ...]]]:
        """Return the owner's exact non-transport identity key sets."""
        return {
            UNIT_SCHEDULER_WORK_ITEM: set(self._scheduler_identity_keys),
            UNIT_LIFECYCLE_RESERVED_TRANSPORT_OPERATION: set(
                self._reservation_identity_keys
            ),
            UNIT_LOCAL_VALIDATION_STEP: set(self._validation_identity_keys),
        }

    def _identity_key_set_for_field(self, field_name: str) -> set[tuple[Any, ...]]:
        return {
            _SCHEDULER_IDENTITY_FIELD: self._scheduler_identity_keys,
            _RESERVATION_IDENTITY_FIELD: self._reservation_identity_keys,
            _VALIDATION_IDENTITY_FIELD: self._validation_identity_keys,
        }[field_name]

    def _identity_list_for_field(self, field_name: str) -> list[dict[str, Any]]:
        return {
            _SCHEDULER_IDENTITY_FIELD: self.scheduler_work_identities,
            _RESERVATION_IDENTITY_FIELD: self.lifecycle_reservation_identities,
            _VALIDATION_IDENTITY_FIELD: self.local_validation_identities,
        }[field_name]

    def _prepare_stage_non_transport_identities(
        self, evidence: Mapping[str, Any]
    ) -> dict[str, list[tuple[tuple[Any, ...], dict[str, Any]]]]:
        """Validate a stage's non-transport identity lists without committing.

        Each present list must match its paired integer counter and contain no
        within-stage or cross-stage duplicate identity. Returns per-field
        ``(key, payload)`` entries to apply atomically once the whole stage is
        validated.
        """
        counter_field = {
            _SCHEDULER_IDENTITY_FIELD: "scheduler_work_items",
            _RESERVATION_IDENTITY_FIELD: "lifecycle_reservations",
            _VALIDATION_IDENTITY_FIELD: "local_validations",
        }
        prepared: dict[str, list[tuple[tuple[Any, ...], dict[str, Any]]]] = {
            field_name: [] for field_name in _NON_TRANSPORT_IDENTITY_FIELDS
        }
        for field_name in _NON_TRANSPORT_IDENTITY_FIELDS:
            raw_list = evidence.get(field_name)
            if raw_list is None:
                continue
            if not isinstance(raw_list, Sequence) or isinstance(
                raw_list, (str, bytes)
            ):
                raise CampaignSixUnitError(
                    f"SIX_UNIT_STAGE_EVIDENCE_MALFORMED:{field_name.upper()}"
                )
            counter = int(evidence.get(counter_field[field_name]) or 0)
            if len(raw_list) != counter:
                raise CampaignSixUnitError(
                    "SIX_UNIT_STAGE_EVIDENCE_IDENTITY_COUNT_MISMATCH:"
                    f"{field_name}:{len(raw_list)}!={counter}"
                )
            key_func = _NON_TRANSPORT_IDENTITY_KEY_FUNCS[field_name]
            committed = self._identity_key_set_for_field(field_name)
            within_stage: set[tuple[Any, ...]] = set()
            for raw in raw_list:
                if not isinstance(raw, Mapping):
                    raise CampaignSixUnitError(
                        f"SIX_UNIT_STAGE_EVIDENCE_MALFORMED:{field_name.upper()}"
                    )
                try:
                    key = key_func(raw)
                except (TypeError, ValueError) as exc:
                    raise CampaignSixUnitError(
                        f"SIX_UNIT_STAGE_EVIDENCE_MALFORMED:{field_name}:{exc}"
                    ) from exc
                if key in within_stage or key in committed:
                    raise CampaignSixUnitError(
                        f"SIX_UNIT_STAGE_EVIDENCE_DUPLICATE_IDENTITY:{field_name}:{key}"
                    )
                within_stage.add(key)
                prepared[field_name].append((key, dict(raw)))
        return prepared

    @property
    def sealed_stage_count(self) -> int:
        return len(self.sealed_stage_diagnostics)

    @property
    def owner_transport_operation_count(self) -> int:
        return int(self.ledger.source_transport_operations)

    def accounting_diagnostics(self) -> dict[str, Any]:
        """Coordinator-facing sealed-stage diagnostics."""
        return {
            "sealed_stage_count": self.sealed_stage_count,
            "sealed_stage_diagnostics": [
                dict(item) for item in self.sealed_stage_diagnostics
            ],
            "ingested_stage_count": int(self.stage_evidence_count),
            "ingested_stage_ids": list(self.ingested_stage_ids),
            "owner_transport_operation_count": self.owner_transport_operation_count,
            "accounting_block_reason": self.accounting_block_reason,
            "sealed_stage_diagnostics": [
                dict(item) for item in self.sealed_stage_diagnostics
            ],
        }

    def next_stage_sequence(self, stage_kind: str) -> int:
        """Allocate the next sequence from this exact cycle owner's evidence.

        Stage identity is cycle-scoped accounting state.  Refresh ordinals and
        durable source-request rows are deliberately not sequence authorities.
        """
        canonical_kind = _require_nonempty_text(
            stage_kind, field_name="stage_kind"
        )
        sequences = [
            int(item["stage_sequence"])
            for item in self.sealed_stage_diagnostics
            if str(item.get("stage_kind") or "") == canonical_kind
        ]
        return max(sequences, default=0) + 1

    def ingest_stage_evidence(self, evidence: Mapping[str, Any] | None) -> None:
        """Aggregate one active stage's durable evidence onto this owner.

        The top-level owner is the single accounting authority: stage results
        may *expose* evidence, but only the owner aggregates it. A missing,
        malformed, duplicate, or negative stage evidence block fails closed
        (raising) before it can contribute silently. Rehydrated transport
        identities are recorded (the ledger enforces duplicate detection); the
        three non-transport counters are summed.

        Operational sealed stages must carry sealed-stage metadata. Legacy
        offline evidence without ``stage_id`` remains accepted only for existing
        tests; it never weakens sealed operational uniqueness rules.
        """
        try:
            self._ingest_stage_evidence_impl(evidence)
        except CampaignSixUnitError as exc:
            self.block(str(exc))
            raise

    def _ingest_stage_evidence_impl(
        self, evidence: Mapping[str, Any] | None
    ) -> None:
        if not isinstance(evidence, Mapping):
            raise CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_MISSING")
        if not evidence:
            raise CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_EMPTY")
        required_fields = {
            "evidence_kind",
            "transport_operations",
            "local_validations",
            "scheduler_work_items",
            "lifecycle_reservations",
        }
        if (
            evidence.get("evidence_kind") not in {EVIDENCE_KIND_V1, EVIDENCE_KIND_V2}
            or not required_fields.issubset(evidence)
        ):
            raise CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_MALFORMED")

        sealed_present = any(
            field_name in evidence for field_name in SEALED_STAGE_METADATA_FIELDS
            if field_name not in {"campaign_id", "run_id", "cycle_id"}
        )
        stage_id: str | None = None
        if sealed_present or evidence.get("stage_id") is not None:
            stage_id = _require_nonempty_text(
                evidence.get("stage_id"), field_name="stage_id"
            )
            _require_nonempty_text(evidence.get("stage_kind"), field_name="stage_kind")
            try:
                sequence = int(evidence.get("stage_sequence"))
            except (TypeError, ValueError) as exc:
                raise CampaignSixUnitError(
                    "SIX_UNIT_STAGE_EVIDENCE_MALFORMED:INVALID_STAGE_SEQUENCE"
                ) from exc
            if sequence < 1:
                raise CampaignSixUnitError(
                    "SIX_UNIT_STAGE_EVIDENCE_MALFORMED:INVALID_STAGE_SEQUENCE"
                )
            status = _require_nonempty_text(
                evidence.get("stage_terminal_status"),
                field_name="stage_terminal_status",
            ).upper()
            if status not in STAGE_TERMINAL_STATUSES:
                raise CampaignSixUnitError(
                    "SIX_UNIT_STAGE_EVIDENCE_MALFORMED:INVALID_STAGE_TERMINAL_STATUS"
                )
            _require_nonempty_text(evidence.get("sealed_at"), field_name="sealed_at")
            for field_name in ("campaign_id", "run_id", "cycle_id"):
                _require_nonempty_text(evidence.get(field_name), field_name=field_name)
            if stage_id in self._ingested_stage_id_set:
                raise CampaignSixUnitError(
                    f"SIX_UNIT_STAGE_EVIDENCE_DUPLICATE_STAGE_ID:{stage_id}"
                )

        for field_name, owner_value in (
            ("campaign_id", self.campaign_id),
            ("run_id", self.run_id),
            ("cycle_id", self.cycle_id),
        ):
            evidence_value = evidence.get(field_name)
            if (
                owner_value is not None
                and evidence_value is not None
                and str(evidence_value) != str(owner_value)
            ):
                raise CampaignSixUnitError(
                    "SIX_UNIT_STAGE_EVIDENCE_IDENTITY_MISMATCH:"
                    f"{field_name}:{evidence_value!r}!={owner_value!r}"
                )
        # Structural validation (malformed / duplicate-within-stage / negative).
        try:
            stage_totals = reconstruct_six_unit_totals_from_evidence(evidence)
        except CampaignSixUnitError as exc:
            if str(exc).startswith("SIX_UNIT_STAGE_EVIDENCE_"):
                raise
            raise CampaignSixUnitError(
                f"SIX_UNIT_STAGE_EVIDENCE_MALFORMED:{exc}"
            ) from exc
        is_pre_operation_no_work = evidence.get("phase") == "PRE_OPERATION_NO_WORK"
        if is_pre_operation_no_work:
            if (
                self.stage_evidence_count != 0
                or self.pre_operation_no_work
                or evidence.get("source_transport_attempted") is not False
                or int(evidence.get("source_governor_requests") or 0) != 0
                or evidence.get("scheduler_work_exists") is not False
                or evidence.get("lifecycle_began") is not False
                or not str(evidence.get("no_work_reason") or "").strip()
                or any(int(value) != 0 for value in stage_totals.values())
            ):
                raise CampaignSixUnitError(
                    "SIX_UNIT_STAGE_EVIDENCE_MALFORMED:"
                    "PRE_OPERATION_NO_WORK_CONTRACT"
                )
        elif self.pre_operation_no_work:
            raise CampaignSixUnitError(
                "SIX_UNIT_STAGE_EVIDENCE_MALFORMED:"
                "PRE_OPERATION_NO_WORK_MIXED_WITH_OPERATION"
            )
        stage_ledger = MeasuredTransportLedger(
            campaign_id=self.campaign_id,
            run_id=self.run_id,
            cycle_id=self.cycle_id,
        )
        transports = evidence.get("transport_operations") or ()
        for raw in transports:
            if not isinstance(raw, Mapping):
                raise CampaignSixUnitError("SIX_UNIT_STAGE_IDENTITY_MALFORMED")
            try:
                stage_ledger.record_transport(
                    TransportOperationIdentity(
                        stage=str(raw.get("stage") or ""),
                        source_name=str(raw.get("source_name") or ""),
                        endpoint_owner=str(raw.get("endpoint_owner") or ""),
                        governed_request_kind=str(
                            raw.get("governed_request_kind") or ""
                        ),
                        method_or_endpoint=str(
                            raw.get("method_or_endpoint") or ""
                        ),
                        within_request_ordinal=int(
                            raw.get("within_request_ordinal") or 0
                        ),
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
            except (TypeError, ValueError, MeasuredTransportError) as exc:
                raise CampaignSixUnitError(
                    f"SIX_UNIT_STAGE_EVIDENCE_MALFORMED:{exc}"
                ) from exc
        stage_ledger.record_local_validation(
            int(evidence.get("local_validations") or 0)
        )
        stage_ledger.record_scheduler_work_item(
            int(evidence.get("scheduler_work_items") or 0)
        )
        stage_ledger.reserve_lifecycle_transports(
            int(evidence.get("lifecycle_reservations") or 0)
        )
        # V2 identity-bearing non-transport evidence. When an identity list is
        # present its length must equal the paired integer counter so unit totals
        # derive from unique identities. Within-stage and cross-stage duplicate
        # identities fail closed before the stage commits.
        prepared_identities = self._prepare_stage_non_transport_identities(evidence)
        # Make one stage atomic in memory. A duplicate against an earlier stage
        # or a combined ceiling failure must not partially alter the owner.
        candidate_ledger = copy.deepcopy(self.ledger)
        try:
            candidate_ledger.extend(stage_ledger)
        except MeasuredTransportError as exc:
            if "DUPLICATE_TRANSPORT_IDENTITY" in str(exc):
                raise CampaignSixUnitError(
                    f"SIX_UNIT_STAGE_EVIDENCE_DUPLICATE_TRANSPORT:{exc}"
                ) from exc
            raise CampaignSixUnitError(
                f"SIX_UNIT_STAGE_EVIDENCE_MALFORMED:{exc}"
            ) from exc

        # Commit atomically only after full validation succeeds.
        self.ledger = candidate_ledger
        for field_name, entries in prepared_identities.items():
            key_set = self._identity_key_set_for_field(field_name)
            identity_list = self._identity_list_for_field(field_name)
            for key, payload in entries:
                key_set.add(key)
                identity_list.append(payload)
            if entries:
                self.identity_mode_units.add(
                    _NON_TRANSPORT_IDENTITY_UNIT[field_name]
                )
        self.stage_evidence_count += 1
        self.pre_operation_no_work = is_pre_operation_no_work
        self.pre_operation_no_work_reason = (
            str(evidence["no_work_reason"])
            if is_pre_operation_no_work
            else None
        )
        if stage_id is not None:
            self._ingested_stage_id_set.add(stage_id)
            self.ingested_stage_ids.append(stage_id)
            self.sealed_stage_diagnostics.append(
                {
                    "stage_id": stage_id,
                    "stage_kind": str(evidence.get("stage_kind") or ""),
                    "stage_sequence": int(evidence.get("stage_sequence") or 0),
                    "stage_terminal_status": str(
                        evidence.get("stage_terminal_status") or ""
                    ),
                    "stage_first_terminal_cause": evidence.get(
                        "stage_first_terminal_cause"
                    ),
                    "sealed_at": str(evidence.get("sealed_at") or ""),
                    "transport_operations": int(
                        stage_totals["SOURCE_TRANSPORT_OPERATION"]
                    ),
                }
            )

    def close(self, *, ended_at: str | None = None) -> None:
        if self.ended_at is None:
            self.ended_at = ended_at or _utc_now_iso()

    def block(self, reason: str) -> None:
        candidate = str(reason or "").strip()
        if not candidate:
            raise CampaignSixUnitError("SIX_UNIT_ACCOUNTING_BLOCKED")
        if self.accounting_block_reason is None:
            self.accounting_block_reason = candidate

    def elapsed_seconds(self) -> float:
        end = self.ended_at or _utc_now_iso()
        return max(0.0, (_parse_iso(end) - _parse_iso(self.started_at)).total_seconds())

    def durable_evidence(self) -> dict[str, Any]:
        """Return durable six-unit evidence (not the derived totals alone).

        Emits identity-bearing ``CAMPAIGN_SIX_UNIT_EVIDENCE_V2`` whenever any
        non-transport identity has been recorded, so the durable evidence carries
        the exact Scheduler/reservation/validation identities that produce the
        three non-transport unit totals. Otherwise it stays byte-compatible V1.
        """
        if self.ended_at is None:
            self.close()
        evidence: dict[str, Any] = {
            "evidence_kind": EVIDENCE_KIND_V1,
            "campaign_id": self.campaign_id,
            "run_id": self.run_id,
            "cycle_id": self.cycle_id,
            "owner_id": self.owner_id,
            "stage_evidence_count": self.stage_evidence_count,
            "pre_operation_no_work": self.pre_operation_no_work,
            "pre_operation_no_work_reason": self.pre_operation_no_work_reason,
            "accounting_block_reason": self.accounting_block_reason,
            "ingested_stage_ids": list(self.ingested_stage_ids),
            "sealed_stage_count": self.sealed_stage_count,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "elapsed_seconds": round(self.elapsed_seconds(), 6),
            "transport_operations": [
                item.as_dict() for item in self.ledger.transports
            ],
            "local_validations": int(self.ledger.local_validations),
            "scheduler_work_items": int(self.ledger.scheduler_work_items),
            "lifecycle_reservations": int(self.ledger.lifecycle_reservations),
        }
        if self.identity_mode_units:
            # V2 contract: non-transport counters derive from unique identity
            # lists. Bare integer contributions from V1 stages must not outrun
            # the identity set (IDENTITY_COUNT_MISMATCH).
            evidence["evidence_kind"] = EVIDENCE_KIND_V2
            evidence[_SCHEDULER_IDENTITY_FIELD] = list(self.scheduler_work_identities)
            evidence[_RESERVATION_IDENTITY_FIELD] = list(
                self.lifecycle_reservation_identities
            )
            evidence[_VALIDATION_IDENTITY_FIELD] = list(
                self.local_validation_identities
            )
            if "SCHEDULER_WORK_ITEM" in self.identity_mode_units:
                evidence["scheduler_work_items"] = len(self.scheduler_work_identities)
            if "LIFECYCLE_RESERVED_TRANSPORT_OPERATION" in self.identity_mode_units:
                evidence["lifecycle_reservations"] = len(
                    self.lifecycle_reservation_identities
                )
            if "LOCAL_VALIDATION_STEP" in self.identity_mode_units:
                evidence["local_validations"] = len(self.local_validation_identities)
        return evidence

    def six_unit_totals(self) -> dict[str, int]:
        return self.ledger.six_unit_totals()


def _transport_identity_key(raw: Mapping[str, Any] | TransportOperationIdentity) -> tuple[Any, ...]:
    """Stable exact-record key for owner/action-local set or multiset comparison."""
    if isinstance(raw, TransportOperationIdentity):
        return (
            str(raw.stage or ""),
            str(raw.source_name or ""),
            str(raw.endpoint_owner or ""),
            str(raw.governed_request_kind or ""),
            str(raw.method_or_endpoint or ""),
            int(raw.within_request_ordinal or 0),
            str(raw.target_category or ""),
            None if raw.target_identity is None else str(raw.target_identity),
            int(raw.response_bytes),
            int(raw.normalized_rows),
            str(raw.result or ""),
            None if raw.reserved_from is None else str(raw.reserved_from),
        )
    return (
        str(raw.get("stage") or ""),
        str(raw.get("source_name") or ""),
        str(raw.get("endpoint_owner") or ""),
        str(raw.get("governed_request_kind") or ""),
        str(raw.get("method_or_endpoint") or ""),
        int(raw.get("within_request_ordinal") or 0),
        str(raw.get("target_category") or ""),
        (
            None
            if raw.get("target_identity") is None
            else str(raw.get("target_identity"))
        ),
        int(raw.get("response_bytes") or 0),
        int(raw.get("normalized_rows") or 0),
        str(raw.get("result") or ""),
        None if raw.get("reserved_from") is None else str(raw.get("reserved_from")),
    )


class CampaignSixUnitProjection:
    """Read-only campaign projection derived from strict cycle owners.

    Stage evidence is ingested exactly once by its cycle owner. This projection
    only validates and concatenates those already-owned ledgers for terminal
    reconciliation/reporting; it has no evidence-ingestion or cycle-registration
    authority.
    """

    def __init__(
        self,
        *,
        campaign_id: str,
        run_id: str,
        primary_cycle_id: str,
        cycle_owners: Sequence[CampaignSixUnitOwner],
    ) -> None:
        self.campaign_id = _require_nonempty_text(
            campaign_id, field_name="campaign_id"
        )
        self.run_id = _require_nonempty_text(run_id, field_name="run_id")
        self.primary_cycle_id = _require_nonempty_text(
            primary_cycle_id, field_name="cycle_id"
        )
        if not cycle_owners:
            raise CampaignSixUnitError("SIX_UNIT_CAMPAIGN_CYCLE_OWNERS_MISSING")

        owners = tuple(cycle_owners)
        cycle_ids: list[str] = []
        stage_ids: set[str] = set()
        combined_transports: list[TransportOperationIdentity] = []
        combined_local_validations = 0
        combined_scheduler_work_items = 0
        combined_lifecycle_reservations = 0
        combined_non_transport: dict[str, list[dict[str, Any]]] = {
            field_name: [] for field_name in _NON_TRANSPORT_IDENTITY_FIELDS
        }
        combined_non_transport_keys: dict[str, set[tuple[Any, ...]]] = {
            field_name: set() for field_name in _NON_TRANSPORT_IDENTITY_FIELDS
        }
        cycle_evidences: list[dict[str, Any]] = []
        cycle_owner_ids: list[str | None] = []
        sealed_stage_diagnostics: list[dict[str, Any]] = []
        accounting_block_reason: str | None = None

        for owner in owners:
            if (
                owner.campaign_id != self.campaign_id
                or owner.run_id != self.run_id
            ):
                raise CampaignSixUnitError(
                    "SIX_UNIT_CAMPAIGN_OWNER_IDENTITY_MISMATCH"
                )
            owner_cycle_id = _require_nonempty_text(
                owner.cycle_id, field_name="cycle_id"
            )
            if owner_cycle_id in cycle_ids:
                raise CampaignSixUnitError(
                    f"SIX_UNIT_CAMPAIGN_DUPLICATE_CYCLE_OWNER:{owner_cycle_id}"
                )
            cycle_ids.append(owner_cycle_id)
            duplicate_stage_ids = stage_ids.intersection(owner.ingested_stage_ids)
            if duplicate_stage_ids:
                raise CampaignSixUnitError(
                    "SIX_UNIT_CAMPAIGN_DUPLICATE_STAGE_ID:"
                    + sorted(duplicate_stage_ids)[0]
                )
            stage_ids.update(owner.ingested_stage_ids)
            owner_evidence = owner.durable_evidence()
            owner_totals = reconstruct_six_unit_totals_from_evidence(
                owner_evidence
            )
            if owner_totals != owner.six_unit_totals():
                raise CampaignSixUnitError(
                    "SIX_UNIT_CAMPAIGN_CYCLE_OWNER_TOTAL_MISMATCH:"
                    f"{owner_cycle_id}"
                )
            # Each owner has already applied the strict single-cycle duplicate,
            # ceiling, and measurement laws. Campaign projection is a read-only
            # concatenation: the same canonical transport key in two different
            # cycle owners represents two lawful operations and must retain
            # multiplicity rather than being re-ingested through ``extend``.
            combined_transports.extend(copy.deepcopy(owner.ledger.transports))
            combined_local_validations += int(owner.ledger.local_validations)
            combined_scheduler_work_items += int(owner.ledger.scheduler_work_items)
            combined_lifecycle_reservations += int(
                owner.ledger.lifecycle_reservations
            )
            cycle_evidences.append(copy.deepcopy(owner_evidence))
            cycle_owner_ids.append(owner.owner_id)
            for field_name in _NON_TRANSPORT_IDENTITY_FIELDS:
                key_func = _NON_TRANSPORT_IDENTITY_KEY_FUNCS[field_name]
                for raw in owner_evidence.get(field_name) or ():
                    if not isinstance(raw, Mapping):
                        raise CampaignSixUnitError(
                            f"SIX_UNIT_CAMPAIGN_IDENTITY_MALFORMED:{field_name}"
                        )
                    key = key_func(raw)
                    if key in combined_non_transport_keys[field_name]:
                        raise CampaignSixUnitError(
                            "SIX_UNIT_CAMPAIGN_DUPLICATE_NON_TRANSPORT_IDENTITY:"
                            f"{field_name}:{key}"
                        )
                    combined_non_transport_keys[field_name].add(key)
                    combined_non_transport[field_name].append(dict(raw))
            for diagnostic in owner.sealed_stage_diagnostics:
                sealed_stage_diagnostics.append(
                    {"cycle_id": owner_cycle_id, **dict(diagnostic)}
                )
            if accounting_block_reason is None and owner.accounting_block_reason:
                accounting_block_reason = str(owner.accounting_block_reason)

        if self.primary_cycle_id not in cycle_ids:
            raise CampaignSixUnitError(
                "SIX_UNIT_CAMPAIGN_PRIMARY_CYCLE_OWNER_MISSING"
            )

        combined_ledger = MeasuredTransportLedger(
            campaign_id=self.campaign_id,
            run_id=self.run_id,
            cycle_id="CAMPAIGN_MULTI_CYCLE",
            transports=combined_transports,
            local_validations=combined_local_validations,
            scheduler_work_items=combined_scheduler_work_items,
            lifecycle_reservations=combined_lifecycle_reservations,
        )
        totals = combined_ledger.six_unit_totals()
        identity_units = {
            _SCHEDULER_IDENTITY_FIELD: UNIT_SCHEDULER_WORK_ITEM,
            _RESERVATION_IDENTITY_FIELD: (
                UNIT_LIFECYCLE_RESERVED_TRANSPORT_OPERATION
            ),
            _VALIDATION_IDENTITY_FIELD: UNIT_LOCAL_VALIDATION_STEP,
        }
        any_identity_mode = any(
            combined_non_transport[field_name]
            for field_name in _NON_TRANSPORT_IDENTITY_FIELDS
        )
        if any_identity_mode:
            for field_name, unit in identity_units.items():
                if len(combined_non_transport[field_name]) != int(totals[unit]):
                    raise CampaignSixUnitError(
                        "SIX_UNIT_CAMPAIGN_NON_TRANSPORT_IDENTITY_INCOMPLETE:"
                        f"{field_name}:{len(combined_non_transport[field_name])}"
                        f"!={int(totals[unit])}"
                    )

        self.projection_id = (
            f"six-unit-campaign-projection|{self.campaign_id}|{self.run_id}"
        )
        self._cycle_ids = tuple(cycle_ids)
        self._cycle_owners = tuple(owners)
        self._cycle_evidences = tuple(cycle_evidences)
        self._cycle_owner_ids = tuple(cycle_owner_ids)
        self._ledger = combined_ledger
        self._non_transport = combined_non_transport
        self._non_transport_keys = combined_non_transport_keys
        self.ingested_stage_ids = [
            stage_id
            for owner in owners
            for stage_id in owner.ingested_stage_ids
        ]
        self.sealed_stage_diagnostics = sealed_stage_diagnostics
        self.stage_evidence_count = sum(
            int(owner.stage_evidence_count) for owner in owners
        )
        self.accounting_block_reason = accounting_block_reason
        self.started_at = min(owner.started_at for owner in owners)
        self.ended_at = max(
            str(owner.ended_at or owner.started_at) for owner in owners
        )

    @property
    def ledger(self) -> MeasuredTransportLedger:
        return copy.deepcopy(self._ledger)

    @property
    def registered_cycle_ids(self) -> tuple[str, ...]:
        return self._cycle_ids

    def owner_for_cycle(self, cycle_id: str) -> CampaignSixUnitOwner:
        exact = _require_nonempty_text(cycle_id, field_name="cycle_id")
        matches = [
            owner for owner in self._cycle_owners if str(owner.cycle_id) == exact
        ]
        if len(matches) != 1:
            raise CampaignSixUnitError(
                f"SIX_UNIT_CAMPAIGN_CYCLE_OWNER_MISSING:{exact}"
            )
        return matches[0]

    @property
    def owner_transport_operation_count(self) -> int:
        return int(self._ledger.source_transport_operations)

    @property
    def sealed_stage_count(self) -> int:
        return len(self.sealed_stage_diagnostics)

    def close(self, *, ended_at: str | None = None) -> None:
        del ended_at

    def non_transport_identity_keys(self) -> dict[str, set[tuple[Any, ...]]]:
        return {
            _NON_TRANSPORT_IDENTITY_UNIT[field_name]: set(keys)
            for field_name, keys in self._non_transport_keys.items()
        }

    def accounting_diagnostics(self) -> dict[str, Any]:
        return {
            "accounting_scope": "CAMPAIGN_MULTI_CYCLE_PROJECTION",
            "registered_cycle_ids": list(self._cycle_ids),
            "cycle_owner_ids": list(self._cycle_owner_ids),
            "sealed_stage_count": self.sealed_stage_count,
            "sealed_stage_diagnostics": [
                dict(item) for item in self.sealed_stage_diagnostics
            ],
            "ingested_stage_count": self.stage_evidence_count,
            "ingested_stage_ids": list(self.ingested_stage_ids),
            "owner_transport_operation_count": self.owner_transport_operation_count,
            "accounting_block_reason": self.accounting_block_reason,
        }

    def six_unit_totals(self) -> dict[str, int]:
        return self._ledger.six_unit_totals()

    def durable_evidence(self) -> dict[str, Any]:
        totals = self.six_unit_totals()
        cycle_evidences = copy.deepcopy(list(self._cycle_evidences))
        pre_operation_no_work = all(
            bool(item.get("pre_operation_no_work")) for item in cycle_evidences
        )
        pre_operation_no_work_reason = None
        if pre_operation_no_work:
            pre_operation_no_work_reason = (
                "MULTI_CYCLE_PRE_OPERATION_NO_WORK:"
                + "|".join(
                    f"{item['cycle_id']}:{item['pre_operation_no_work_reason']}"
                    for item in cycle_evidences
                )
            )
        evidence: dict[str, Any] = {
            "evidence_kind": (
                EVIDENCE_KIND_V2
                if any(
                    self._non_transport[field_name]
                    for field_name in _NON_TRANSPORT_IDENTITY_FIELDS
                )
                else EVIDENCE_KIND_V1
            ),
            "accounting_scope": "CAMPAIGN_MULTI_CYCLE_PROJECTION",
            "campaign_id": self.campaign_id,
            "run_id": self.run_id,
            "cycle_ids": list(self._cycle_ids),
            "cycle_evidences": cycle_evidences,
            "cycle_owner_ids": list(self._cycle_owner_ids),
            "projection_id": self.projection_id,
            "stage_evidence_count": self.stage_evidence_count,
            "ingested_stage_ids": list(self.ingested_stage_ids),
            "sealed_stage_count": self.sealed_stage_count,
            "sealed_stage_diagnostics": [
                dict(item) for item in self.sealed_stage_diagnostics
            ],
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "elapsed_seconds": max(
                0.0,
                (_parse_iso(self.ended_at) - _parse_iso(self.started_at)).total_seconds(),
            ),
            "pre_operation_no_work": pre_operation_no_work,
            "pre_operation_no_work_reason": pre_operation_no_work_reason,
            "accounting_block_reason": self.accounting_block_reason,
            "transport_operations": [
                item.as_dict() for item in self._ledger.transports
            ],
            "local_validations": int(totals[UNIT_LOCAL_VALIDATION_STEP]),
            "scheduler_work_items": int(totals[UNIT_SCHEDULER_WORK_ITEM]),
            "lifecycle_reservations": int(
                totals[UNIT_LIFECYCLE_RESERVED_TRANSPORT_OPERATION]
            ),
        }
        if evidence["evidence_kind"] == EVIDENCE_KIND_V2:
            for field_name in _NON_TRANSPORT_IDENTITY_FIELDS:
                evidence[field_name] = [
                    dict(item) for item in self._non_transport[field_name]
                ]
        reconstructed = reconstruct_six_unit_totals_from_evidence(evidence)
        if reconstructed != totals:
            raise CampaignSixUnitError(
                "SIX_UNIT_CAMPAIGN_PROJECTION_TOTAL_MISMATCH"
            )
        return evidence


class _CycleStageEvidenceSink:
    """Callable cycle router that also exposes its owner's sequence allocator."""

    def __init__(
        self, registry: "CampaignCycleAccountingRegistry", cycle_id: str
    ) -> None:
        self._registry = registry
        self._cycle_id = cycle_id

    def __call__(self, evidence: Mapping[str, Any]) -> None:
        if not isinstance(evidence, Mapping):
            self._registry.ingest_stage_evidence(evidence)
            return
        evidence_cycle_id = str(evidence.get("cycle_id") or "")
        if evidence_cycle_id != self._cycle_id:
            raise CampaignSixUnitError(
                "SIX_UNIT_STAGE_EVIDENCE_IDENTITY_MISMATCH:"
                f"cycle_id:{evidence_cycle_id!r}!={self._cycle_id!r}"
            )
        self._registry.ingest_stage_evidence(evidence)

    def next_stage_sequence(self, stage_kind: str) -> int:
        return self._registry.owner_for_cycle(self._cycle_id).next_stage_sequence(
            stage_kind
        )


class CampaignCycleAccountingRegistry:
    """Explicit registry and fail-closed router for cycle-bound owners."""

    def __init__(
        self,
        *,
        campaign_id: str,
        run_id: str,
        initial_cycle_id: str,
        started_at: str | None = None,
    ) -> None:
        self.campaign_id = _require_nonempty_text(
            campaign_id, field_name="campaign_id"
        )
        self.run_id = _require_nonempty_text(run_id, field_name="run_id")
        self.initial_cycle_id = _require_nonempty_text(
            initial_cycle_id, field_name="cycle_id"
        )
        self._cycle_accounting_owners: dict[str, CampaignSixUnitOwner] = {
            self.initial_cycle_id: CampaignSixUnitOwner(
                campaign_id=self.campaign_id,
                run_id=self.run_id,
                cycle_id=self.initial_cycle_id,
                started_at=started_at or _utc_now_iso(),
            )
        }

    @property
    def registered_cycle_ids(self) -> tuple[str, ...]:
        return tuple(self._cycle_accounting_owners)

    def owner_for_cycle(self, cycle_id: str) -> CampaignSixUnitOwner:
        canonical_cycle_id = _require_nonempty_text(
            cycle_id, field_name="cycle_id"
        )
        owner = self._cycle_accounting_owners.get(canonical_cycle_id)
        if owner is None:
            raise CampaignSixUnitError(
                f"SIX_UNIT_STAGE_EVIDENCE_CYCLE_UNREGISTERED:{canonical_cycle_id}"
            )
        return owner

    def register_authoritative_cycle(
        self,
        *,
        campaign_id: str,
        run_id: str,
        cycle_id: str,
        started_at: str | None = None,
    ) -> CampaignSixUnitOwner:
        for field_name, supplied, expected in (
            ("campaign_id", campaign_id, self.campaign_id),
            ("run_id", run_id, self.run_id),
        ):
            if str(supplied) != str(expected):
                raise CampaignSixUnitError(
                    "SIX_UNIT_STAGE_EVIDENCE_IDENTITY_MISMATCH:"
                    f"{field_name}:{supplied!r}!={expected!r}"
                )
        canonical_cycle_id = _require_nonempty_text(
            cycle_id, field_name="cycle_id"
        )
        existing = self._cycle_accounting_owners.get(canonical_cycle_id)
        if existing is not None:
            return existing
        owner = CampaignSixUnitOwner(
            campaign_id=self.campaign_id,
            run_id=self.run_id,
            cycle_id=canonical_cycle_id,
            started_at=started_at or _utc_now_iso(),
        )
        self._cycle_accounting_owners[canonical_cycle_id] = owner
        return owner

    def ingest_stage_evidence(self, evidence: Mapping[str, Any]) -> None:
        if not isinstance(evidence, Mapping):
            raise CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_MISSING")
        for field_name, expected in (
            ("campaign_id", self.campaign_id),
            ("run_id", self.run_id),
        ):
            supplied = evidence.get(field_name)
            if str(supplied or "") != str(expected):
                raise CampaignSixUnitError(
                    "SIX_UNIT_STAGE_EVIDENCE_IDENTITY_MISMATCH:"
                    f"{field_name}:{supplied!r}!={expected!r}"
                )
        cycle_id = _require_nonempty_text(
            evidence.get("cycle_id"), field_name="cycle_id"
        )
        self.owner_for_cycle(cycle_id).ingest_stage_evidence(evidence)

    def stage_evidence_sink_for_cycle(
        self, cycle_id: str
    ) -> Callable[[Mapping[str, Any]], None]:
        canonical_cycle_id = _require_nonempty_text(
            cycle_id, field_name="cycle_id"
        )
        self.owner_for_cycle(canonical_cycle_id)

        return _CycleStageEvidenceSink(self, canonical_cycle_id)

    def registered_stage_evidence_sink(
        self,
        *,
        campaign_id: str,
        run_id: str,
        cycle_id: str,
        started_at: str | None = None,
    ) -> Callable[[Mapping[str, Any]], None]:
        owner = self.register_authoritative_cycle(
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            started_at=started_at,
        )
        return self.stage_evidence_sink_for_cycle(str(owner.cycle_id))

    def campaign_projection(self) -> CampaignSixUnitProjection:
        return CampaignSixUnitProjection(
            campaign_id=self.campaign_id,
            run_id=self.run_id,
            primary_cycle_id=self.initial_cycle_id,
            cycle_owners=tuple(self._cycle_accounting_owners.values()),
        )


@dataclass
class CampaignActionLocalLedger:
    """Independent action-local observation ledger (verification only).

    Created before operational work starts. It observes operations directly at
    their execution boundaries — measured transport, Scheduler enqueue/claim/
    terminal, lifecycle reservation, named local validation — and never becomes an
    accounting authority. It must not be built by copying sealed stage evidence or
    by querying the final report; the equality contract fails closed if it is.
    """

    campaign_id: str | None = None
    run_id: str | None = None
    cycle_id: str | None = None
    ledger_id: str | None = None
    lifecycle_started: bool = False
    transport_identities: list[dict[str, Any]] = field(default_factory=list)
    scheduler_work_identities: list[dict[str, Any]] = field(default_factory=list)
    lifecycle_reservation_identities: list[dict[str, Any]] = field(
        default_factory=list
    )
    local_validation_identities: list[dict[str, Any]] = field(default_factory=list)
    scheduler_transition_events: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.ledger_id is None:
            suffix = self.cycle_id if self.cycle_id is not None else "CAMPAIGN"
            self.ledger_id = (
                f"action-local-ledger|{self.campaign_id}|{self.run_id}|{suffix}"
            )

    @staticmethod
    def _stage_belongs_to_cycle(stage_id: Any, cycle_id: str) -> bool:
        parts = str(stage_id or "").split("|")
        return len(parts) >= 3 and parts[2] == str(cycle_id)

    def slice_for_cycle(self, cycle_id: str) -> "CampaignActionLocalLedger":
        """Return the exact cycle-bearing action-local evidence slice.

        Stage identity, not token id or list position, owns the partition.  The
        returned ledger is an independent verification view and cannot ingest
        evidence into the campaign ledger.
        """
        exact_cycle = _require_nonempty_text(cycle_id, field_name="cycle_id")
        sliced = CampaignActionLocalLedger(
            campaign_id=self.campaign_id,
            run_id=self.run_id,
            cycle_id=exact_cycle,
        )
        sliced.lifecycle_started = self.lifecycle_started
        sliced.transport_identities = [
            dict(item)
            for item in self.transport_identities
            if self._stage_belongs_to_cycle(item.get("stage"), exact_cycle)
        ]
        sliced.scheduler_work_identities = [
            dict(item)
            for item in self.scheduler_work_identities
            if self._stage_belongs_to_cycle(item.get("stage_id"), exact_cycle)
        ]
        sliced.lifecycle_reservation_identities = [
            dict(item)
            for item in self.lifecycle_reservation_identities
            if self._stage_belongs_to_cycle(item.get("stage_id"), exact_cycle)
        ]
        sliced.local_validation_identities = [
            dict(item)
            for item in self.local_validation_identities
            if self._stage_belongs_to_cycle(item.get("stage_id"), exact_cycle)
        ]
        sliced.scheduler_transition_events = [
            dict(item)
            for item in self.scheduler_transition_events
            if self._stage_belongs_to_cycle(item.get("stage_id"), exact_cycle)
            or str(item.get("cycle_id") or "") == exact_cycle
        ]
        return sliced

    def observe_transport(
        self, identity: TransportOperationIdentity | Mapping[str, Any]
    ) -> None:
        self.transport_identities.append(
            identity.as_dict()
            if isinstance(identity, TransportOperationIdentity)
            else dict(identity)
        )

    def observe_scheduler_work(
        self, identity: SchedulerWorkIdentity | Mapping[str, Any]
    ) -> None:
        self.lifecycle_started = True
        self.scheduler_work_identities.append(
            identity.as_dict()
            if isinstance(identity, SchedulerWorkIdentity)
            else dict(identity)
        )

    def observe_scheduler_transition(self, event: Mapping[str, Any]) -> None:
        self.lifecycle_started = True
        self.scheduler_transition_events.append(dict(event))

    def scheduler_transition_coverage(self) -> dict[str, Any]:
        by_job: dict[int, set[str]] = {}
        terminal_states: dict[int, str] = {}
        for event in self.scheduler_transition_events:
            job_id = int(event.get("scheduler_job_id") or 0)
            by_job.setdefault(job_id, set()).add(str(event.get("boundary") or ""))
            if event.get("terminal_state") is not None:
                terminal_states[job_id] = str(event["terminal_state"])
        incomplete: dict[str, list[str]] = {}
        for job_id, boundaries in sorted(by_job.items()):
            required = {"SCHEDULER_ENQUEUE", "SCHEDULER_TERMINAL"}
            if terminal_states.get(job_id) != "CANCELLED":
                required.add("SCHEDULER_CLAIM")
            if not required.issubset(boundaries):
                incomplete[str(job_id)] = sorted(required - boundaries)
        return {
            "job_count": len(by_job),
            "complete": bool(by_job) and not incomplete,
            "incomplete_jobs": incomplete,
            "events": [dict(item) for item in self.scheduler_transition_events],
        }

    def observe_lifecycle_reservation(
        self, identity: LifecycleReservationIdentity | Mapping[str, Any]
    ) -> None:
        self.lifecycle_started = True
        self.lifecycle_reservation_identities.append(
            identity.as_dict()
            if isinstance(identity, LifecycleReservationIdentity)
            else dict(identity)
        )

    def observe_local_validation(
        self, identity: LocalValidationIdentity | Mapping[str, Any]
    ) -> None:
        self.lifecycle_started = True
        self.local_validation_identities.append(
            identity.as_dict()
            if isinstance(identity, LocalValidationIdentity)
            else dict(identity)
        )

    def transport_observer(self):
        """Return a ``MeasuredTransportLedger.on_transport_recorded`` callback."""
        return self.observe_transport

    def non_transport_identity_lists(self) -> dict[str, list[dict[str, Any]]]:
        return {
            _SCHEDULER_IDENTITY_FIELD: list(self.scheduler_work_identities),
            _RESERVATION_IDENTITY_FIELD: list(self.lifecycle_reservation_identities),
            _VALIDATION_IDENTITY_FIELD: list(self.local_validation_identities),
        }


def _keys_and_duplicate(
    entries: Sequence[Mapping[str, Any]], key_func
) -> tuple[set[tuple[Any, ...]], bool]:
    """Return the identity key set and whether any duplicate was present."""
    keys: set[tuple[Any, ...]] = set()
    duplicate = False
    for item in entries:
        if not isinstance(item, Mapping):
            raise CampaignSixUnitError("ACTION_LOCAL_IDENTITY_MALFORMED")
        key = key_func(item)
        if key in keys:
            duplicate = True
        keys.add(key)
    return keys, duplicate


def reconcile_full_run_owner_to_action_local(
    owner: CampaignSixUnitOwner | CampaignSixUnitProjection,
    action_local: CampaignActionLocalLedger | None,
    *,
    required_stage_kinds: Sequence[str] | None = None,
    owner_equality_stage_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Prove exact six-unit equality between owner and an independent observer.

    Every unit is compared as an exact identity set in both directions, except
    projection transport records, which use an exact multiset so one identical
    canonical operation owned by each of two cycles retains multiplicity two. A
    lifecycle-started run with a missing action-local surface, a missing mandatory
    sealed stage, a forbidden single-cycle duplicate, or a count/identity mismatch
    fails closed. This never returns ``equal=True`` merely because an argument is
    absent.

    ``required_stage_kinds`` is the mandatory sealed-stage manifest (every listed
    kind must have been sealed on the owner or the run fails closed).

    ``owner_equality_stage_ids`` optionally scopes which owner identities enter the
    per-unit equality comparison to the stages an independent execution-time
    observer could actually witness (the lifecycle slot stages). Owner-only
    mandatory stages proven from durable ownership/terminal evidence
    (``DISCOVERY_SELECTION_SCHEDULER``, ``CAMPAIGN_TERMINAL_RECONCILIATION``) stay
    required-present but are excluded from action-local equality so the equality
    contract is neither vacuous nor forced to invent observations. When omitted
    (default), every owner identity participates, preserving the original
    all-stages equality contract.
    """
    unit_results: dict[str, Any] = {}
    blocked_reason: str | None = None

    if owner.accounting_block_reason is not None:
        blocked_reason = str(owner.accounting_block_reason)

    if blocked_reason is None and action_local is None:
        blocked_reason = "ACTION_LOCAL_LIFECYCLE_EVIDENCE_MISSING"

    # Required mandatory sealed lifecycle stages.
    sealed_kinds = {
        str(item.get("stage_kind") or "")
        for item in owner.sealed_stage_diagnostics
    }
    missing_stages = [
        kind for kind in (required_stage_kinds or ()) if kind not in sealed_kinds
    ]
    if blocked_reason is None and missing_stages:
        blocked_reason = "MISSING_MANDATORY_LIFECYCLE_STAGE:" + ",".join(
            sorted(missing_stages)
        )

    equality_scope = (
        None
        if owner_equality_stage_ids is None
        else {str(stage_id) for stage_id in owner_equality_stage_ids}
    )

    def _in_scope(key: tuple[Any, ...]) -> bool:
        # Every owner identity key carries its owning stage id as element 0
        # (transport ``stage`` field and non-transport ``stage_id``).
        return equality_scope is None or (key and key[0] in equality_scope)

    projection_transport_multiset = isinstance(owner, CampaignSixUnitProjection)
    if projection_transport_multiset:
        owner_transport_keys: set[tuple[Any, ...]] | Counter[tuple[Any, ...]] = (
            Counter(
                key
                for key in (
                    _transport_identity_key(item) for item in owner.ledger.transports
                )
                if _in_scope(key)
            )
        )
    else:
        owner_transport_keys = {
            key
            for key in (
                _transport_identity_key(item) for item in owner.ledger.transports
            )
            if _in_scope(key)
        }
    owner_non_transport = {
        unit: {key for key in keys if _in_scope(key)}
        for unit, keys in owner.non_transport_identity_keys().items()
    }

    comparisons = (
        (
            "SOURCE_TRANSPORT_OPERATION",
            owner_transport_keys,
            None if action_local is None else action_local.transport_identities,
            _transport_identity_key,
        ),
        (
            UNIT_SCHEDULER_WORK_ITEM,
            owner_non_transport[UNIT_SCHEDULER_WORK_ITEM],
            None if action_local is None else action_local.scheduler_work_identities,
            _scheduler_identity_key,
        ),
        (
            UNIT_LIFECYCLE_RESERVED_TRANSPORT_OPERATION,
            owner_non_transport[UNIT_LIFECYCLE_RESERVED_TRANSPORT_OPERATION],
            None
            if action_local is None
            else action_local.lifecycle_reservation_identities,
            _reservation_identity_key,
        ),
        (
            UNIT_LOCAL_VALIDATION_STEP,
            owner_non_transport[UNIT_LOCAL_VALIDATION_STEP],
            None if action_local is None else action_local.local_validation_identities,
            _validation_identity_key,
        ),
    )

    for unit, owner_keys, action_entries, key_func in comparisons:
        multiplicity_aware = bool(
            projection_transport_multiset
            and unit == "SOURCE_TRANSPORT_OPERATION"
        )
        owner_count = (
            sum(owner_keys.values())
            if multiplicity_aware and isinstance(owner_keys, Counter)
            else len(owner_keys)
        )
        result: dict[str, Any] = {
            "owner_count": owner_count,
            "action_local_count": None,
            "identity_sets_equal": None,
            "unit_block_reason": None,
        }
        if action_entries is None:
            result["unit_block_reason"] = (
                None if action_local is None else "ACTION_LOCAL_UNIT_SURFACE_MISSING"
            )
        else:
            try:
                if multiplicity_aware:
                    action_keys = Counter(
                        key_func(item)
                        for item in action_entries
                        if isinstance(item, Mapping)
                    )
                    if sum(action_keys.values()) != len(action_entries):
                        raise CampaignSixUnitError(
                            "ACTION_LOCAL_IDENTITY_MALFORMED"
                        )
                    duplicate = False
                else:
                    action_keys, duplicate = _keys_and_duplicate(
                        action_entries, key_func
                    )
            except CampaignSixUnitError:
                result["unit_block_reason"] = "ACTION_LOCAL_IDENTITY_MALFORMED"
            else:
                result["action_local_count"] = len(action_entries)
                result["identity_sets_equal"] = owner_keys == action_keys
                if multiplicity_aware and owner_keys != action_keys:
                    result["unit_block_reason"] = "UNIT_IDENTITY_MULTISET_MISMATCH"
                elif duplicate:
                    result["unit_block_reason"] = "DUPLICATE_ACTION_LOCAL_IDENTITY"
                elif (
                    not multiplicity_aware
                    and len(action_keys) != len(action_entries)
                ):
                    result["unit_block_reason"] = "DUPLICATE_ACTION_LOCAL_IDENTITY"
                elif owner_keys != action_keys:
                    result["unit_block_reason"] = "UNIT_IDENTITY_SET_MISMATCH"
        unit_results[unit] = result
        if blocked_reason is None and result["unit_block_reason"] is not None:
            blocked_reason = f"{unit}:{result['unit_block_reason']}"

    equal = blocked_reason is None
    return {
        "equal": equal,
        "mismatch_reason": blocked_reason,
        "lifecycle_started": bool(
            owner.stage_evidence_count > 0
            or (action_local is not None and action_local.lifecycle_started)
        ),
        "required_stage_kinds": list(required_stage_kinds or ()),
        "missing_mandatory_stage_kinds": sorted(missing_stages),
        "equality_scoped_stage_ids": (
            None if equality_scope is None else sorted(equality_scope)
        ),
        "unit_results": unit_results,
        "diagnostics": owner.accounting_diagnostics(),
    }


def reconcile_owner_to_action_local(
    owner: CampaignSixUnitOwner | CampaignSixUnitProjection,
    *,
    action_local_source_operations: int | None = None,
    action_local_transport_identities: Sequence[Mapping[str, Any]] | None = None,
    lifecycle_started: bool = False,
    action_local_ledger: "CampaignActionLocalLedger | None" = None,
    required_stage_kinds: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Verify owner transport identities and counts against action-local truth.

    Action-local evidence is verification only. Missing stage evidence is never
    manufactured from durable source rows or request counts. Action-local
    identities must originate at measurement time
    (``MeasuredTransportLedger.record_transport`` / transport_identity_observer)
    before and separately from stage sealing — never by mirroring sealed-stage
    handoff into both reconciliation sides.

    Exact equality is required in both directions:

    * ``owner > action_local`` blocks
    * ``action_local > owner`` blocks
    * equal counts with different identity sets block

    When the action-local surface provides only governed-request counts and
    cannot prove exact transport identity equality, return
    ``ACTION_LOCAL_TRANSPORT_IDENTITY_DESIGN_BLOCKED`` rather than weakening
    the contract with count-only multi-hop asymmetry.

    A lifecycle-started run (``lifecycle_started=True`` or an
    ``action_local_ledger`` argument) requires a non-empty action-local surface
    for every unit. It is delegated to
    :func:`reconcile_full_run_owner_to_action_local`, which fails closed on a
    missing surface, missing mandatory stage, duplicate identity, or any
    count/identity mismatch. It never returns ``equal=True`` because both
    optional arguments happen to be absent.
    """
    if lifecycle_started or action_local_ledger is not None:
        return reconcile_full_run_owner_to_action_local(
            owner,
            action_local_ledger,
            required_stage_kinds=required_stage_kinds,
        )
    owner_ops = int(owner.owner_transport_operation_count)
    projection_transport_multiset = isinstance(owner, CampaignSixUnitProjection)
    owner_identity_keys: set[tuple[Any, ...]] | Counter[tuple[Any, ...]]
    if projection_transport_multiset:
        owner_identity_keys = Counter(
            _transport_identity_key(item) for item in owner.ledger.transports
        )
    else:
        owner_identity_keys = {
            _transport_identity_key(item) for item in owner.ledger.transports
        }
    action_local_count = (
        None
        if action_local_source_operations is None
        else int(action_local_source_operations)
    )
    diagnostics = owner.accounting_diagnostics()
    mismatch_reason: str | None = None
    action_local_identity_count: int | None = None
    action_local_identity_keys: (
        set[tuple[Any, ...]] | Counter[tuple[Any, ...]] | None
    ) = None

    if owner.accounting_block_reason is not None:
        mismatch_reason = str(owner.accounting_block_reason)
    elif action_local_transport_identities is not None:
        if not isinstance(action_local_transport_identities, Sequence) or isinstance(
            action_local_transport_identities, (str, bytes)
        ):
            mismatch_reason = "CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH"
        else:
            try:
                if projection_transport_multiset:
                    action_local_identity_keys = Counter(
                        _transport_identity_key(item)
                        for item in action_local_transport_identities
                        if isinstance(item, Mapping)
                    )
                    observed_identity_count = sum(
                        action_local_identity_keys.values()
                    )
                else:
                    action_local_identity_keys = {
                        _transport_identity_key(item)
                        for item in action_local_transport_identities
                        if isinstance(item, Mapping)
                    }
                    observed_identity_count = len(action_local_identity_keys)
                if observed_identity_count != len(action_local_transport_identities):
                    # Malformed or non-mapping entries cannot prove equality.
                    mismatch_reason = (
                        "CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH"
                    )
                else:
                    action_local_identity_count = observed_identity_count
                    if action_local_count is None:
                        action_local_count = action_local_identity_count
                    if owner_ops != action_local_identity_count:
                        mismatch_reason = (
                            "CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH"
                        )
                    elif action_local_count != action_local_identity_count:
                        mismatch_reason = (
                            "CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH"
                        )
                    elif owner_ops != action_local_count:
                        mismatch_reason = (
                            "CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH"
                        )
                    elif owner_identity_keys != action_local_identity_keys:
                        mismatch_reason = (
                            "CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH"
                        )
            except (TypeError, ValueError):
                mismatch_reason = "CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH"
    elif action_local_count is not None:
        # Count-only governed-request surfaces cannot prove exact transport
        # identity equality. Do not weaken to asymmetric multi-hop totals.
        mismatch_reason = "ACTION_LOCAL_TRANSPORT_IDENTITY_DESIGN_BLOCKED"

    equal = mismatch_reason is None
    return {
        "equal": equal,
        "mismatch_reason": mismatch_reason,
        "owner_transport_operation_count": owner_ops,
        "action_local_source_operations": action_local_count,
        "action_local_transport_identity_count": action_local_identity_count,
        "owner_transport_identity_count": (
            sum(owner_identity_keys.values())
            if isinstance(owner_identity_keys, Counter)
            else len(owner_identity_keys)
        ),
        "identity_sets_equal": (
            None
            if action_local_identity_keys is None
            else owner_identity_keys == action_local_identity_keys
        ),
        "diagnostics": diagnostics,
    }


def aggregate_campaign_six_unit_owner(
    *,
    campaign_id: str | None = None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
    stage_evidences: Sequence[Mapping[str, Any] | None] | None,
) -> CampaignSixUnitOwner:
    """Build one top-level owner that reconciles every active stage's evidence.

    This is the single accounting authority for a campaign attempt. Each active
    stage (direct Pump, PumpSwap, DexScreener, holder/safety, local validations,
    Scheduler work, response bytes, normalized rows, lifecycle reservations)
    contributes exactly one durable evidence block. An omitted or malformed
    block fails closed via ``ingest_stage_evidence``.
    """
    if stage_evidences is None:
        raise CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_MISSING")
    if (
        not isinstance(stage_evidences, Sequence)
        or isinstance(stage_evidences, (str, bytes))
    ):
        raise CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_MALFORMED")
    if len(stage_evidences) == 0:
        raise CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_EMPTY")
    owner = CampaignSixUnitOwner(
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        started_at=started_at or _utc_now_iso(),
    )
    for evidence in stage_evidences:
        owner.ingest_stage_evidence(evidence)
    owner.close(ended_at=ended_at)
    return owner


def reconstruct_six_unit_totals_from_evidence(
    evidence: Mapping[str, Any] | None,
) -> dict[str, int]:
    """Independently rebuild six-unit totals from durable evidence only.

    For identity-bearing ``CAMPAIGN_SIX_UNIT_EVIDENCE_V2`` the three
    non-transport unit totals are derived from the unique identity list sizes and
    cross-checked against the paired integer counters. A duplicate identity or a
    counter/identity mismatch fails closed so the total cannot be forged.

    A multi-cycle projection is reconstructed from its independently strict nested
    cycle evidence. Its top-level transport list is compared to the nested records
    as a multiset, allowing lawful cross-cycle multiplicity without weakening the
    duplicate law inside any one cycle owner.
    """
    if not isinstance(evidence, Mapping):
        raise CampaignSixUnitError("SIX_UNIT_EVIDENCE_MISSING")
    if str(evidence.get("evidence_kind") or "") not in {
        EVIDENCE_KIND_V1,
        EVIDENCE_KIND_V2,
        "",
    } and "transport_operations" not in evidence:
        raise CampaignSixUnitError("SIX_UNIT_EVIDENCE_KIND_UNSUPPORTED")

    transports = evidence.get("transport_operations") or ()
    if not isinstance(transports, Sequence) or isinstance(transports, (str, bytes)):
        raise CampaignSixUnitError("SIX_UNIT_EVIDENCE_TRANSPORTS_MALFORMED")

    projection_cycle_totals: dict[str, int] | None = None
    if evidence.get("accounting_scope") == "CAMPAIGN_MULTI_CYCLE_PROJECTION":
        raw_cycle_evidences = evidence.get("cycle_evidences")
        if (
            not isinstance(raw_cycle_evidences, Sequence)
            or isinstance(raw_cycle_evidences, (str, bytes))
            or not raw_cycle_evidences
        ):
            raise CampaignSixUnitError(
                "SIX_UNIT_CAMPAIGN_PROJECTION_CYCLE_EVIDENCE_MALFORMED"
            )
        projection_cycle_totals = empty_six_unit_totals()
        nested_transports: list[Mapping[str, Any]] = []
        nested_cycle_ids: list[str] = []
        for raw_cycle_evidence in raw_cycle_evidences:
            if (
                not isinstance(raw_cycle_evidence, Mapping)
                or raw_cycle_evidence.get("accounting_scope")
                == "CAMPAIGN_MULTI_CYCLE_PROJECTION"
            ):
                raise CampaignSixUnitError(
                    "SIX_UNIT_CAMPAIGN_PROJECTION_CYCLE_EVIDENCE_MALFORMED"
                )
            if (
                raw_cycle_evidence.get("campaign_id") != evidence.get("campaign_id")
                or raw_cycle_evidence.get("run_id") != evidence.get("run_id")
            ):
                raise CampaignSixUnitError(
                    "SIX_UNIT_CAMPAIGN_PROJECTION_CYCLE_IDENTITY_MISMATCH"
                )
            cycle_id = _require_nonempty_text(
                raw_cycle_evidence.get("cycle_id"), field_name="cycle_id"
            )
            if cycle_id in nested_cycle_ids:
                raise CampaignSixUnitError(
                    f"SIX_UNIT_CAMPAIGN_DUPLICATE_CYCLE_OWNER:{cycle_id}"
                )
            nested_cycle_ids.append(cycle_id)
            cycle_totals = reconstruct_six_unit_totals_from_evidence(
                raw_cycle_evidence
            )
            for unit in SIX_UNITS:
                projection_cycle_totals[unit] += int(cycle_totals[unit])
            raw_nested_transports = (
                raw_cycle_evidence.get("transport_operations") or ()
            )
            nested_transports.extend(raw_nested_transports)

        raw_cycle_ids = evidence.get("cycle_ids")
        if (
            not isinstance(raw_cycle_ids, Sequence)
            or isinstance(raw_cycle_ids, (str, bytes))
            or [str(item) for item in raw_cycle_ids] != nested_cycle_ids
        ):
            raise CampaignSixUnitError(
                "SIX_UNIT_CAMPAIGN_PROJECTION_CYCLE_PROVENANCE_MISMATCH"
            )
        try:
            top_transport_multiset = Counter(
                _transport_identity_key(raw) for raw in transports
            )
            nested_transport_multiset = Counter(
                _transport_identity_key(raw) for raw in nested_transports
            )
        except (TypeError, ValueError) as exc:
            raise CampaignSixUnitError(
                "SIX_UNIT_EVIDENCE_IDENTITY_MALFORMED"
            ) from exc
        if (
            len(transports) != len(nested_transports)
            or top_transport_multiset != nested_transport_multiset
        ):
            raise CampaignSixUnitError(
                "SIX_UNIT_CAMPAIGN_PROJECTION_TRANSPORT_MULTISET_MISMATCH"
            )

    def _integer(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError) as exc:
            raise CampaignSixUnitError(
                "SIX_UNIT_EVIDENCE_MALFORMED_COUNTER"
            ) from exc

    seen: set[tuple[Any, ...]] = set()
    response_bytes = 0
    normalized_rows = 0
    for raw in transports:
        if not isinstance(raw, Mapping):
            raise CampaignSixUnitError("SIX_UNIT_EVIDENCE_IDENTITY_MALFORMED")
        key = (
            raw.get("stage"),
            raw.get("source_name"),
            raw.get("governed_request_kind"),
            raw.get("method_or_endpoint"),
            raw.get("within_request_ordinal"),
            raw.get("target_category"),
            raw.get("target_identity"),
        )
        if key in seen and projection_cycle_totals is None:
            raise CampaignSixUnitError("SIX_UNIT_EVIDENCE_DUPLICATE_IDENTITY")
        seen.add(key)
        response_bytes += _integer(raw.get("response_bytes"))
        normalized_rows += _integer(raw.get("normalized_rows"))
        if _integer(raw.get("response_bytes")) < 0 or _integer(
            raw.get("normalized_rows")
        ) < 0:
            raise CampaignSixUnitError("SIX_UNIT_EVIDENCE_NEGATIVE_MEASURE")

    counters = {
        "local_validations": _integer(evidence.get("local_validations")),
        "scheduler_work_items": _integer(evidence.get("scheduler_work_items")),
        "lifecycle_reservations": _integer(
            evidence.get("lifecycle_reservations")
        ),
    }
    if any(value < 0 for value in counters.values()):
        raise CampaignSixUnitError("SIX_UNIT_EVIDENCE_NEGATIVE_MEASURE")

    # Identity-bearing (V2): non-transport totals must equal the unique identity
    # count, and the paired counter must agree with it.
    field_to_counter = {
        _SCHEDULER_IDENTITY_FIELD: "scheduler_work_items",
        _RESERVATION_IDENTITY_FIELD: "lifecycle_reservations",
        _VALIDATION_IDENTITY_FIELD: "local_validations",
    }
    for field_name, counter_key in field_to_counter.items():
        raw_list = evidence.get(field_name)
        if raw_list is None:
            continue
        if not isinstance(raw_list, Sequence) or isinstance(raw_list, (str, bytes)):
            raise CampaignSixUnitError(
                f"SIX_UNIT_EVIDENCE_IDENTITY_MALFORMED:{field_name}"
            )
        key_func = _NON_TRANSPORT_IDENTITY_KEY_FUNCS[field_name]
        identity_seen: set[tuple[Any, ...]] = set()
        for raw in raw_list:
            if not isinstance(raw, Mapping):
                raise CampaignSixUnitError(
                    f"SIX_UNIT_EVIDENCE_IDENTITY_MALFORMED:{field_name}"
                )
            key = key_func(raw)
            if key in identity_seen:
                raise CampaignSixUnitError(
                    f"SIX_UNIT_EVIDENCE_DUPLICATE_IDENTITY:{field_name}"
                )
            identity_seen.add(key)
        if len(identity_seen) != counters[counter_key]:
            raise CampaignSixUnitError(
                f"SIX_UNIT_EVIDENCE_IDENTITY_COUNT_MISMATCH:{field_name}"
            )

    reconstructed = {
        "SOURCE_TRANSPORT_OPERATION": len(transports),
        "LOCAL_VALIDATION_STEP": counters["local_validations"],
        "SCHEDULER_WORK_ITEM": counters["scheduler_work_items"],
        "SOURCE_RESPONSE_BYTES": response_bytes,
        "NORMALIZED_SOURCE_ROWS": normalized_rows,
        "LIFECYCLE_RESERVED_TRANSPORT_OPERATION": counters[
            "lifecycle_reservations"
        ],
    }
    if (
        projection_cycle_totals is not None
        and reconstructed != projection_cycle_totals
    ):
        raise CampaignSixUnitError(
            "SIX_UNIT_CAMPAIGN_PROJECTION_TOTAL_MISMATCH"
        )
    return reconstructed


def compare_report_totals_to_evidence(
    report_totals: Mapping[str, Any] | None,
    evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Compare stored report totals to independent evidence reconstruction."""
    reconstructed = reconstruct_six_unit_totals_from_evidence(evidence)
    stored = dict(report_totals or {})
    if "six_unit_totals" in stored:
        stored = dict(stored["six_unit_totals"])
    comparison = reconcile_six_unit_totals(
        {"six_unit_totals": {unit: int(stored.get(unit) or 0) for unit in SIX_UNITS}},
        {"six_unit_totals": reconstructed},
    )
    return {
        "equal": bool(comparison["equal"]),
        "mismatches": comparison["mismatches"],
        "report_totals": comparison["left"],
        "reconstructed_from_evidence": comparison["right"],
        "self_comparison": False,
    }


def assert_identity_count_matches_claimed(
    *,
    claimed_transport_operations: int,
    identities: Sequence[Mapping[str, Any] | TransportOperationIdentity],
) -> None:
    count = len(identities)
    if int(claimed_transport_operations) != count:
        raise MeasuredTransportError(
            f"TRANSPORT_IDENTITY_COUNT_MISMATCH:claimed={claimed_transport_operations}:identities={count}"
        )


def empty_six_unit_evidence() -> dict[str, Any]:
    now = _utc_now_iso()
    return {
        "evidence_kind": "CAMPAIGN_SIX_UNIT_EVIDENCE_V1",
        "campaign_id": None,
        "run_id": None,
        "cycle_id": None,
        "started_at": now,
        "ended_at": now,
        "elapsed_seconds": 0.0,
        "transport_operations": [],
        "local_validations": 0,
        "scheduler_work_items": 0,
        "lifecycle_reservations": 0,
    }


def pre_operation_no_work_evidence(
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    reason: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Deliberate zero evidence for a proven pre-operation no-work terminal."""
    if not all(str(value).strip() for value in (campaign_id, run_id, cycle_id, reason)):
        raise CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_MALFORMED")
    stamp = observed_at or _utc_now_iso()
    return {
        "evidence_kind": "CAMPAIGN_SIX_UNIT_EVIDENCE_V1",
        "campaign_id": campaign_id,
        "run_id": run_id,
        "cycle_id": cycle_id,
        "phase": "PRE_OPERATION_NO_WORK",
        "no_work_reason": reason,
        "source_transport_attempted": False,
        "source_governor_requests": 0,
        "scheduler_work_exists": False,
        "lifecycle_began": False,
        "started_at": stamp,
        "ended_at": stamp,
        "elapsed_seconds": 0.0,
        "transport_operations": [],
        "local_validations": 0,
        "scheduler_work_items": 0,
        "lifecycle_reservations": 0,
    }


__all__ = [
    "CampaignActionLocalLedger",
    "CampaignCycleAccountingRegistry",
    "CampaignSixUnitError",
    "CampaignSixUnitOwner",
    "CampaignSixUnitProjection",
    "EVIDENCE_KIND_V1",
    "EVIDENCE_KIND_V2",
    "SEALED_STAGE_METADATA_FIELDS",
    "STAGE_TERMINAL_STATUSES",
    "aggregate_campaign_six_unit_owner",
    "assert_identity_count_matches_claimed",
    "build_campaign_stage_id",
    "compare_report_totals_to_evidence",
    "empty_six_unit_evidence",
    "empty_six_unit_totals",
    "pre_operation_no_work_evidence",
    "reconcile_full_run_owner_to_action_local",
    "reconcile_owner_to_action_local",
    "reconstruct_six_unit_totals_from_evidence",
    "seal_campaign_stage_evidence",
]

"""Campaign-wide six-unit accounting owner for ordinary discovery/selection.

Durable evidence is the ordered transport identities plus non-transport unit
counters. Report totals are derived from that evidence. Replay reconstructs
totals only from durable evidence and compares them to stored report totals —
never self-compares the same totals field.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

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
            "ingested_stage_count": int(self.stage_evidence_count),
            "ingested_stage_ids": list(self.ingested_stage_ids),
            "owner_transport_operation_count": self.owner_transport_operation_count,
            "accounting_block_reason": self.accounting_block_reason,
            "sealed_stage_diagnostics": [
                dict(item) for item in self.sealed_stage_diagnostics
            ],
        }

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
            evidence["evidence_kind"] = EVIDENCE_KIND_V2
            evidence[_SCHEDULER_IDENTITY_FIELD] = list(self.scheduler_work_identities)
            evidence[_RESERVATION_IDENTITY_FIELD] = list(
                self.lifecycle_reservation_identities
            )
            evidence[_VALIDATION_IDENTITY_FIELD] = list(
                self.local_validation_identities
            )
        return evidence

    def six_unit_totals(self) -> dict[str, int]:
        return self.ledger.six_unit_totals()


def _transport_identity_key(raw: Mapping[str, Any] | TransportOperationIdentity) -> tuple[Any, ...]:
    """Stable identity key for exact owner/action-local set comparison."""
    if isinstance(raw, TransportOperationIdentity):
        return (
            str(raw.stage or ""),
            str(raw.source_name or ""),
            str(raw.governed_request_kind or ""),
            str(raw.method_or_endpoint or ""),
            int(raw.within_request_ordinal or 0),
            str(raw.target_category or ""),
            None if raw.target_identity is None else str(raw.target_identity),
        )
    return (
        str(raw.get("stage") or ""),
        str(raw.get("source_name") or ""),
        str(raw.get("governed_request_kind") or ""),
        str(raw.get("method_or_endpoint") or ""),
        int(raw.get("within_request_ordinal") or 0),
        str(raw.get("target_category") or ""),
        (
            None
            if raw.get("target_identity") is None
            else str(raw.get("target_identity"))
        ),
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
    lifecycle_started: bool = False
    transport_identities: list[dict[str, Any]] = field(default_factory=list)
    scheduler_work_identities: list[dict[str, Any]] = field(default_factory=list)
    lifecycle_reservation_identities: list[dict[str, Any]] = field(
        default_factory=list
    )
    local_validation_identities: list[dict[str, Any]] = field(default_factory=list)

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
    owner: CampaignSixUnitOwner,
    action_local: CampaignActionLocalLedger | None,
    *,
    required_stage_kinds: Sequence[str] | None = None,
    owner_equality_stage_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Prove exact six-unit equality between owner and an independent observer.

    Every unit is compared as an exact identity set in both directions. A
    lifecycle-started run with a missing action-local surface, a missing mandatory
    sealed stage, a duplicate identity, or a count/identity mismatch fails closed.
    This never returns ``equal=True`` merely because an argument is absent.

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

    owner_transport_keys = {
        key
        for key in (_transport_identity_key(item) for item in owner.ledger.transports)
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
        result: dict[str, Any] = {
            "owner_count": len(owner_keys),
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
                action_keys, duplicate = _keys_and_duplicate(action_entries, key_func)
            except CampaignSixUnitError:
                result["unit_block_reason"] = "ACTION_LOCAL_IDENTITY_MALFORMED"
            else:
                result["action_local_count"] = len(action_entries)
                result["identity_sets_equal"] = owner_keys == action_keys
                if duplicate:
                    result["unit_block_reason"] = "DUPLICATE_ACTION_LOCAL_IDENTITY"
                elif len(action_keys) != len(action_entries):
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
    owner: CampaignSixUnitOwner,
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
    action_local_identity_keys: set[tuple[Any, ...]] | None = None

    if owner.accounting_block_reason is not None:
        mismatch_reason = str(owner.accounting_block_reason)
    elif action_local_transport_identities is not None:
        if not isinstance(action_local_transport_identities, Sequence) or isinstance(
            action_local_transport_identities, (str, bytes)
        ):
            mismatch_reason = "CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH"
        else:
            try:
                action_local_identity_keys = {
                    _transport_identity_key(item)
                    for item in action_local_transport_identities
                    if isinstance(item, Mapping)
                }
                if len(action_local_identity_keys) != len(
                    action_local_transport_identities
                ):
                    # Malformed or non-mapping entries cannot prove equality.
                    mismatch_reason = (
                        "CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH"
                    )
                else:
                    action_local_identity_count = len(action_local_identity_keys)
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
        "owner_transport_identity_count": len(owner_identity_keys),
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
        if key in seen:
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

    return {
        "SOURCE_TRANSPORT_OPERATION": len(transports),
        "LOCAL_VALIDATION_STEP": counters["local_validations"],
        "SCHEDULER_WORK_ITEM": counters["scheduler_work_items"],
        "SOURCE_RESPONSE_BYTES": response_bytes,
        "NORMALIZED_SOURCE_ROWS": normalized_rows,
        "LIFECYCLE_RESERVED_TRANSPORT_OPERATION": counters[
            "lifecycle_reservations"
        ],
    }


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
    "CampaignSixUnitError",
    "CampaignSixUnitOwner",
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

"""Persisted bounded coordinator for overlapping exact two-token cycles.

This Task-3 adapter extends the existing campaign/run/cycle/token-slot ownership
model without creating a second campaign, factory run, Scheduler, Source
Governor, or schema owner. It performs no source fetching and no lifecycle work.
A caller presents an already-selected exact two-token pair; this module only
checks the immutable session authority and admission gates, then delegates the
cycle/token-slot write to ``create_cycle_with_two_slots``.

The current public operational command is intentionally not wired to this
module in the implementation lane. Four-token and six-token runtime activation
remain separate bounded-proof work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Mapping, Sequence

from printer_v1.operator_cli.campaign_identity_state import validate_identity
from printer_v1.operator_cli.campaign_ownership import create_cycle_with_two_slots
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    MAX_ACTIVE_TWO_TOKEN_CYCLES,
    MAX_THROUGH_4H_TOKENS,
    TOKENS_PER_CYCLE,
    AdmissionDecision,
    AdmissionEvaluation,
    MultiCycleAdmissionState,
    MultiCycleCapacityPolicy,
    MultiCycleSessionPhase,
    MultiCycleSessionSnapshot,
    evaluate_cycle_admission,
    evaluate_session_phase,
)


_ACTIVE_CYCLE_STATES = frozenset(
    {
        "PLANNED",
        "DISCOVERING",
        "SELECTING",
        "TRACKING",
        "CLOSING",
        "AUDITING",
        "ROTATING",
    }
)
_TERMINAL_CYCLE_STATES = frozenset(
    {
        "TERMINAL_COMPLETED",
        "TERMINAL_STOPPED",
        "TERMINAL_BLOCKED",
        "TERMINAL_FAILED",
    }
)
_ACTIVE_THROUGH_4H_TOKEN_STATES = frozenset(
    {
        "SELECTED",
        "WINDOW_15M_ACTIVE",
        "WINDOW_15M_CLOSED",
        "WINDOW_1H_CONTINUING",
        "WINDOW_1H_CLOSED",
        "WINDOW_4H_CONTINUING",
    }
)
_RELEASED_THROUGH_4H_TOKEN_STATES = frozenset(
    {
        "WINDOW_4H_CLOSED",
        "COOLDOWN",
        "ARCHIVED",
        "MANUAL_REVIEW",
        "FAILED",
    }
)
_KNOWN_TOKEN_STATES = (
    _ACTIVE_THROUGH_4H_TOKEN_STATES | _RELEASED_THROUGH_4H_TOKEN_STATES
)


class MultiCycleCoordinatorError(ValueError):
    """Fail-closed persisted session ownership/admission violation."""


@dataclass(frozen=True)
class MultiCycleCampaignBinding:
    campaign_id: str
    campaign_run_id: str
    configuration_id: str
    authoritative_factory_run_id: str


@dataclass(frozen=True)
class MultiCycleAdmissionHealth:
    source_budget_available: bool = True
    provider_budgets_available: bool = True
    scheduler_budget_available: bool = True
    scheduler_due_work_healthy: bool = True
    close_reserve_available: bool = True
    campaign_supervision_healthy: bool = True
    lease_healthy: bool = True
    db_healthy: bool = True
    shared_terminal_condition: bool = False
    cancellation_requested: bool = False
    discovery_capacity_available: bool = True
    protected_work_capacity_available: bool = True


@dataclass(frozen=True)
class MultiCycleCampaignSnapshot:
    campaign_id: str
    campaign_run_id: str
    configuration_id: str
    authoritative_factory_run_id: str
    cycle_ids: tuple[str, ...]
    active_cycle_ids: tuple[str, ...]
    active_token_slot_ids: tuple[str, ...]
    first_cycle_id: str
    session: MultiCycleSessionSnapshot
    admission_evaluation: AdmissionEvaluation


@dataclass(frozen=True)
class PersistedCycleAdmissionResult:
    evaluation: AdmissionEvaluation
    cycle_id: str | None
    cycle_ordinal: int | None
    mutation_performed: bool
    snapshot_before: MultiCycleCampaignSnapshot


def _required(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise MultiCycleCoordinatorError(f"{label} must be a non-empty exact string")
    return value


def _normalize_time(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise MultiCycleCoordinatorError("session time must be a datetime")
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_time(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise MultiCycleCoordinatorError(f"{label} is missing")
    try:
        return _normalize_time(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError as exc:
        raise MultiCycleCoordinatorError(f"{label} is malformed") from exc


def multi_cycle_configuration_contract(
    policy: MultiCycleCapacityPolicy,
    *,
    intake_started_at: datetime,
) -> dict[str, Any]:
    """Return the immutable multi-cycle authority embedded in campaign config."""
    try:
        policy.validate()
    except ValueError as exc:
        raise MultiCycleCoordinatorError(str(exc)) from exc
    started = _normalize_time(intake_started_at)
    return {
        "configured_through_4h_token_ceiling": (
            policy.configured_through_4h_token_ceiling
        ),
        "configured_active_cycle_ceiling": policy.configured_active_cycle_ceiling,
        "total_cycle_admission_ceiling": policy.total_cycle_admission_ceiling,
        "intake_duration_seconds": policy.intake_duration_seconds,
        "minimum_cycle_admission_spacing_seconds": (
            policy.min_admission_spacing_seconds
        ),
        "tokens_per_cycle": TOKENS_PER_CYCLE,
        "implementation_max_through_4h_tokens": MAX_THROUGH_4H_TOKENS,
        "implementation_max_active_cycles": MAX_ACTIVE_TWO_TOKEN_CYCLES,
        "intake_started_at": started.isoformat(),
        "provider_rate_ceilings_changed": False,
        "long_windows_activated": False,
    }


def _validate_binding(binding: MultiCycleCampaignBinding) -> None:
    try:
        validate_identity("campaign", binding.campaign_id)
        validate_identity("configuration", binding.configuration_id)
    except ValueError as exc:
        raise MultiCycleCoordinatorError(str(exc)) from exc
    _required(binding.campaign_run_id, "campaign_run_id")
    _required(binding.authoritative_factory_run_id, "authoritative_factory_run_id")


def _configuration_and_start(
    connection: sqlite3.Connection,
    *,
    binding: MultiCycleCampaignBinding,
    policy: MultiCycleCapacityPolicy,
) -> tuple[Mapping[str, Any], datetime, bool]:
    rows = connection.execute(
        """
        SELECT c.campaign_state,r.run_state,r.authoritative_run_id,
               cfg.configuration_json
        FROM printer_memory_factory_campaigns AS c
        JOIN printer_memory_factory_campaign_runs AS r
          ON r.campaign_id=c.campaign_id AND r.run_id=?
        JOIN printer_memory_factory_campaign_configurations AS cfg
          ON cfg.campaign_id=c.campaign_id AND cfg.configuration_id=?
        WHERE c.campaign_id=?
        """,
        (
            binding.campaign_run_id,
            binding.configuration_id,
            binding.campaign_id,
        ),
    ).fetchall()
    if len(rows) != 1:
        raise MultiCycleCoordinatorError(
            "campaign/configuration/run ownership mismatch"
        )
    row = rows[0]
    campaign_state = str(row[0])
    run_state = str(row[1])
    authoritative = row[2]
    if campaign_state not in {"RUNNING", "STOP_REQUESTED"}:
        raise MultiCycleCoordinatorError("campaign is not an active bounded session")
    if run_state not in {"RUNNING", "STOP_REQUESTED"}:
        raise MultiCycleCoordinatorError("campaign run is not an active bounded session")
    if str(authoritative or "") != binding.authoritative_factory_run_id:
        raise MultiCycleCoordinatorError("authoritative factory run mismatch")
    factory = connection.execute(
        "SELECT 1 FROM printer_memory_factory_runs WHERE run_id=?",
        (binding.authoritative_factory_run_id,),
    ).fetchone()
    if factory is None:
        raise MultiCycleCoordinatorError("authoritative factory run is missing")

    try:
        configuration = json.loads(str(row[3]))
    except json.JSONDecodeError as exc:
        raise MultiCycleCoordinatorError("campaign configuration is malformed") from exc
    if not isinstance(configuration, Mapping):
        raise MultiCycleCoordinatorError("campaign configuration is malformed")
    if configuration.get("token_capacity") != TOKENS_PER_CYCLE:
        raise MultiCycleCoordinatorError(
            "persisted campaign token capacity must remain exactly two per cycle"
        )
    ceilings = configuration.get("ceilings")
    if (
        not isinstance(ceilings, Mapping)
        or ceilings.get("cycle_count") != policy.total_cycle_admission_ceiling
    ):
        raise MultiCycleCoordinatorError(
            "persisted campaign cycle ceiling does not match session policy"
        )
    persisted = configuration.get("multi_cycle_capacity")
    if not isinstance(persisted, Mapping):
        raise MultiCycleCoordinatorError("persisted multi-cycle policy is missing")
    started = _parse_time(persisted.get("intake_started_at"), "intake_started_at")
    expected = multi_cycle_configuration_contract(
        policy,
        intake_started_at=started,
    )
    if dict(persisted) != expected:
        raise MultiCycleCoordinatorError("persisted multi-cycle policy mismatch")
    cancellation_requested = (
        campaign_state == "STOP_REQUESTED" or run_state == "STOP_REQUESTED"
    )
    return configuration, started, cancellation_requested


def _cycle_rows(
    connection: sqlite3.Connection,
    *,
    binding: MultiCycleCampaignBinding,
) -> list[dict[str, Any]]:
    cursor = connection.execute(
        """SELECT cycle_id,cycle_ordinal,cycle_state,created_at
           FROM printer_memory_factory_campaign_cycles
           WHERE campaign_id=? AND run_id=?
           ORDER BY cycle_ordinal,cycle_id""",
        (binding.campaign_id, binding.campaign_run_id),
    )
    columns = tuple(str(item[0]) for item in cursor.description or ())
    return [dict(zip(columns, tuple(row))) for row in cursor.fetchall()]


def _slot_rows(
    connection: sqlite3.Connection,
    *,
    binding: MultiCycleCampaignBinding,
    cycle_id: str,
) -> list[dict[str, Any]]:
    cursor = connection.execute(
        """SELECT token_slot_id,slot_ordinal,token_identity,token_row_id,
                  mint_identity,pair_identity,pair_row_id,lifecycle_identity,
                  token_state,created_at
           FROM printer_memory_factory_campaign_token_slots
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
           ORDER BY slot_ordinal,token_slot_id""",
        (binding.campaign_id, binding.campaign_run_id, cycle_id),
    )
    columns = tuple(str(item[0]) for item in cursor.description or ())
    return [dict(zip(columns, tuple(row))) for row in cursor.fetchall()]


def _historical_slot_identity_sets(
    connection: sqlite3.Connection,
    *,
    binding: MultiCycleCampaignBinding,
) -> dict[str, set[object]]:
    fields = (
        "token_slot_id",
        "token_identity",
        "token_row_id",
        "mint_identity",
        "pair_identity",
        "pair_row_id",
        "lifecycle_identity",
    )
    values = {field: set() for field in fields}
    cursor = connection.execute(
        """SELECT token_slot_id,token_identity,token_row_id,mint_identity,
                  pair_identity,pair_row_id,lifecycle_identity
           FROM printer_memory_factory_campaign_token_slots
           WHERE campaign_id=? AND run_id=?""",
        (binding.campaign_id, binding.campaign_run_id),
    )
    for row in cursor.fetchall():
        for index, field in enumerate(fields):
            values[field].add(row[index])
    return values


def _validate_cycle_history(
    connection: sqlite3.Connection,
    *,
    binding: MultiCycleCampaignBinding,
    policy: MultiCycleCapacityPolicy,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    str,
    datetime,
]:
    cycles = _cycle_rows(connection, binding=binding)
    if not cycles:
        raise MultiCycleCoordinatorError(
            "multi-cycle coordinator requires the already-admitted first cycle"
        )
    if len(cycles) > policy.total_cycle_admission_ceiling:
        raise MultiCycleCoordinatorError("persisted cycle count exceeds session ceiling")
    expected_ordinals = list(range(1, len(cycles) + 1))
    actual_ordinals = [int(cycle["cycle_ordinal"]) for cycle in cycles]
    if actual_ordinals != expected_ordinals:
        raise MultiCycleCoordinatorError("cycle ordinals are not monotonic and contiguous")

    cycle_ids: list[str] = []
    active_cycle_ids: list[str] = []
    active_token_slot_ids: list[str] = []
    admission_times: list[datetime] = []
    seen_cycle_ids: set[str] = set()
    historical: dict[str, set[object]] = {
        field: set()
        for field in (
            "token_slot_id",
            "token_identity",
            "token_row_id",
            "mint_identity",
            "pair_identity",
            "pair_row_id",
            "lifecycle_identity",
        )
    }

    for cycle in cycles:
        cycle_id = str(cycle["cycle_id"])
        try:
            validate_identity("cycle", cycle_id)
        except ValueError as exc:
            raise MultiCycleCoordinatorError(str(exc)) from exc
        if cycle_id in seen_cycle_ids:
            raise MultiCycleCoordinatorError("duplicate cycle identity")
        seen_cycle_ids.add(cycle_id)
        cycle_ids.append(cycle_id)

        cycle_state = str(cycle["cycle_state"])
        if cycle_state not in _ACTIVE_CYCLE_STATES | _TERMINAL_CYCLE_STATES:
            raise MultiCycleCoordinatorError("unknown persisted cycle state")
        slots = _slot_rows(connection, binding=binding, cycle_id=cycle_id)
        if len(slots) != TOKENS_PER_CYCLE:
            raise MultiCycleCoordinatorError("every admitted cycle requires exactly two slots")
        if {int(slot["slot_ordinal"]) for slot in slots} != {1, 2}:
            raise MultiCycleCoordinatorError("persisted slot ordinals must be exactly 1 and 2")
        created = {_parse_time(slot["created_at"], "slot created_at") for slot in slots}
        if len(created) != 1:
            raise MultiCycleCoordinatorError("pair-atomic slot admission timestamp mismatch")
        admitted_at = next(iter(created))
        admission_times.append(admitted_at)

        cycle_active_slots: list[str] = []
        for slot in slots:
            token_state = str(slot["token_state"])
            if token_state not in _KNOWN_TOKEN_STATES:
                raise MultiCycleCoordinatorError("unknown persisted token-slot state")
            for field in historical:
                value = slot[field]
                if value in historical[field]:
                    raise MultiCycleCoordinatorError(
                        "historical campaign slot identity is duplicated"
                    )
                historical[field].add(value)
            if token_state in _ACTIVE_THROUGH_4H_TOKEN_STATES:
                cycle_active_slots.append(str(slot["token_slot_id"]))

        if cycle_state in _ACTIVE_CYCLE_STATES:
            if not cycle_active_slots:
                raise MultiCycleCoordinatorError(
                    "active cycle has no through-4h token but is not terminal"
                )
            active_cycle_ids.append(cycle_id)
            active_token_slot_ids.extend(cycle_active_slots)
        elif cycle_active_slots:
            raise MultiCycleCoordinatorError(
                "terminal cycle retains active through-4h token capacity"
            )

    for previous, current in zip(admission_times, admission_times[1:]):
        if (current - previous).total_seconds() < policy.min_admission_spacing_seconds:
            raise MultiCycleCoordinatorError(
                "persisted cycle admissions violate minimum spacing"
            )

    return (
        tuple(cycle_ids),
        tuple(active_cycle_ids),
        tuple(active_token_slot_ids),
        cycle_ids[0],
        admission_times[-1],
    )


def _admission_state(
    *,
    now: datetime,
    intake_started_at: datetime,
    cycle_count: int,
    active_cycle_count: int,
    active_token_count: int,
    last_cycle_admitted_at: datetime,
    health: MultiCycleAdmissionHealth,
    persisted_cancellation_requested: bool,
) -> MultiCycleAdmissionState:
    return MultiCycleAdmissionState(
        now=_normalize_time(now),
        intake_started_at=intake_started_at,
        active_through_4h_tokens=active_token_count,
        active_cycles=active_cycle_count,
        admissions_completed=cycle_count,
        last_cycle_admitted_at=last_cycle_admitted_at,
        source_budget_available=health.source_budget_available,
        provider_budgets_available=health.provider_budgets_available,
        scheduler_budget_available=health.scheduler_budget_available,
        scheduler_due_work_healthy=health.scheduler_due_work_healthy,
        close_reserve_available=health.close_reserve_available,
        campaign_supervision_healthy=health.campaign_supervision_healthy,
        lease_healthy=health.lease_healthy,
        db_healthy=health.db_healthy,
        shared_terminal_condition=health.shared_terminal_condition,
        cancellation_requested=(
            health.cancellation_requested or persisted_cancellation_requested
        ),
        discovery_capacity_available=health.discovery_capacity_available,
        protected_work_capacity_available=health.protected_work_capacity_available,
    )


def load_multi_cycle_campaign_snapshot(
    connection: sqlite3.Connection,
    *,
    binding: MultiCycleCampaignBinding,
    policy: MultiCycleCapacityPolicy,
    now: datetime,
    health: MultiCycleAdmissionHealth | None = None,
) -> MultiCycleCampaignSnapshot:
    """Read and validate one exact persisted multi-cycle session without writes."""
    _validate_binding(binding)
    try:
        policy.validate()
    except ValueError as exc:
        raise MultiCycleCoordinatorError(str(exc)) from exc
    current_health = health or MultiCycleAdmissionHealth()
    _, intake_started_at, persisted_cancel = _configuration_and_start(
        connection,
        binding=binding,
        policy=policy,
    )
    (
        cycle_ids,
        active_cycle_ids,
        active_token_slot_ids,
        first_cycle_id,
        last_admitted_at,
    ) = _validate_cycle_history(
        connection,
        binding=binding,
        policy=policy,
    )
    state = _admission_state(
        now=now,
        intake_started_at=intake_started_at,
        cycle_count=len(cycle_ids),
        active_cycle_count=len(active_cycle_ids),
        active_token_count=len(active_token_slot_ids),
        last_cycle_admitted_at=last_admitted_at,
        health=current_health,
        persisted_cancellation_requested=persisted_cancel,
    )
    phase = evaluate_session_phase(policy, state)
    evaluation = evaluate_cycle_admission(policy, state)
    session = MultiCycleSessionSnapshot(
        intake_started_at=intake_started_at,
        intake_deadline=(
            intake_started_at
            + __import__("datetime").timedelta(seconds=policy.intake_duration_seconds)
        ),
        configured_through_4h_token_ceiling=(
            policy.configured_through_4h_token_ceiling
        ),
        configured_active_cycle_ceiling=policy.configured_active_cycle_ceiling,
        total_cycle_admission_ceiling=policy.total_cycle_admission_ceiling,
        active_through_4h_tokens=len(active_token_slot_ids),
        active_cycles=len(active_cycle_ids),
        admissions_completed=len(cycle_ids),
        last_cycle_admitted_at=last_admitted_at,
        phase=phase,
    )
    return MultiCycleCampaignSnapshot(
        campaign_id=binding.campaign_id,
        campaign_run_id=binding.campaign_run_id,
        configuration_id=binding.configuration_id,
        authoritative_factory_run_id=binding.authoritative_factory_run_id,
        cycle_ids=cycle_ids,
        active_cycle_ids=active_cycle_ids,
        active_token_slot_ids=active_token_slot_ids,
        first_cycle_id=first_cycle_id,
        session=session,
        admission_evaluation=evaluation,
    )


def _validate_candidate_slots(
    connection: sqlite3.Connection,
    *,
    binding: MultiCycleCampaignBinding,
    slots: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    if len(slots) != TOKENS_PER_CYCLE:
        raise MultiCycleCoordinatorError("fresh admission requires exactly two token slots")
    ordered = tuple(slots)
    try:
        ordinals = {int(slot.get("slot_ordinal", 0)) for slot in ordered}
    except (TypeError, ValueError) as exc:
        raise MultiCycleCoordinatorError("candidate slot ordinal is invalid") from exc
    if ordinals != {1, 2}:
        raise MultiCycleCoordinatorError("candidate slot ordinals must be exactly 1 and 2")

    identity_kinds = {
        "token_slot_id": "token_slot",
        "token_identity": "token",
        "mint_identity": "mint",
        "pair_identity": "pair",
        "lifecycle_identity": "lifecycle",
    }
    row_fields = ("token_row_id", "pair_row_id")
    for slot in ordered:
        for field, kind in identity_kinds.items():
            try:
                validate_identity(kind, slot.get(field))
            except ValueError as exc:
                raise MultiCycleCoordinatorError(str(exc)) from exc
        for field in row_fields:
            value = slot.get(field)
            if type(value) is not int or value <= 0:
                raise MultiCycleCoordinatorError(f"{field} must be a positive integer")

    distinct_fields = tuple(identity_kinds) + row_fields
    for field in distinct_fields:
        if len({slot.get(field) for slot in ordered}) != TOKENS_PER_CYCLE:
            raise MultiCycleCoordinatorError(
                "candidate two-token slot identities must be distinct"
            )

    historical = _historical_slot_identity_sets(connection, binding=binding)
    for slot in ordered:
        for field in distinct_fields:
            if slot.get(field) in historical[field]:
                raise MultiCycleCoordinatorError(
                    f"historical identity reuse is forbidden: {field}"
                )
    return ordered[0], ordered[1]


def _next_cycle_identity(first_cycle_id: str, ordinal: int) -> str:
    if ordinal <= 1:
        raise MultiCycleCoordinatorError("additional cycle ordinal must exceed one")
    candidate = f"{first_cycle_id}-{ordinal}"
    try:
        return validate_identity("cycle", candidate)
    except ValueError as exc:
        raise MultiCycleCoordinatorError(str(exc)) from exc


def admit_two_token_cycle(
    connection: sqlite3.Connection,
    *,
    binding: MultiCycleCampaignBinding,
    policy: MultiCycleCapacityPolicy,
    now: datetime,
    slots: Sequence[Mapping[str, Any]],
    health: MultiCycleAdmissionHealth | None = None,
) -> PersistedCycleAdmissionResult:
    """Atomically gate and persist one additional exact two-token cycle.

    The caller must supply a connection with no open transaction. ``BEGIN
    IMMEDIATE`` protects the admission-count/concurrency check through the one
    delegated cycle/token-slot write. This function never discovers, fetches,
    schedules, or executes lifecycle work.
    """
    if connection.in_transaction:
        raise MultiCycleCoordinatorError(
            "coordinator admission requires ownership of a fresh transaction"
        )
    current_health = health or MultiCycleAdmissionHealth()
    try:
        connection.execute("BEGIN IMMEDIATE")
        snapshot = load_multi_cycle_campaign_snapshot(
            connection,
            binding=binding,
            policy=policy,
            now=now,
            health=current_health,
        )
        evaluation = snapshot.admission_evaluation
        if evaluation.decision != AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE:
            connection.rollback()
            return PersistedCycleAdmissionResult(
                evaluation=evaluation,
                cycle_id=None,
                cycle_ordinal=None,
                mutation_performed=False,
                snapshot_before=snapshot,
            )

        validated_slots = _validate_candidate_slots(
            connection,
            binding=binding,
            slots=slots,
        )
        next_ordinal = snapshot.session.admissions_completed + 1
        if next_ordinal > policy.total_cycle_admission_ceiling:
            raise MultiCycleCoordinatorError("next cycle would exceed session ceiling")
        cycle_id = _next_cycle_identity(snapshot.first_cycle_id, next_ordinal)
        if connection.execute(
            "SELECT 1 FROM printer_memory_factory_campaign_cycles WHERE cycle_id=?",
            (cycle_id,),
        ).fetchone() is not None:
            raise MultiCycleCoordinatorError("derived cycle identity already exists")

        create_cycle_with_two_slots(
            connection,
            campaign_id=binding.campaign_id,
            run_id=binding.campaign_run_id,
            cycle_id=cycle_id,
            cycle_ordinal=next_ordinal,
            slots=validated_slots,
            now=_normalize_time(now).isoformat(),
        )
        return PersistedCycleAdmissionResult(
            evaluation=evaluation,
            cycle_id=cycle_id,
            cycle_ordinal=next_ordinal,
            mutation_performed=True,
            snapshot_before=snapshot,
        )
    except MultiCycleCoordinatorError:
        if connection.in_transaction:
            connection.rollback()
        raise
    except sqlite3.Error as exc:
        if connection.in_transaction:
            connection.rollback()
        raise MultiCycleCoordinatorError(
            f"multi-cycle admission persistence failed: {exc}"
        ) from exc
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise

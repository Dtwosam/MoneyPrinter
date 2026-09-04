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
from printer_v1.operator_cli.campaign_ownership import (
    create_cycle_with_two_slots,
    cycle_scoped_token_slot_id,
)
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


_CAMPAIGN_HISTORICAL_SLOT_IDENTITY_FIELDS = (
    "token_slot_id",
    "token_identity",
    "token_row_id",
    "mint_identity",
    "pair_identity",
    "pair_row_id",
)

# Candidate-resolvable fields enforced at later-cycle fresh selection.
# token_slot_id remains admission-only: a not-yet-admitted candidate has no new
# persisted slot to compare. lifecycle_identity is not a pairwise-disjoint rule.
_CAMPAIGN_HISTORICAL_DISJOINT_CANDIDATE_FIELDS = (
    "mint_identity",
    "pair_identity",
    "token_row_id",
    "pair_row_id",
    "token_identity",
)


def _historical_slot_identity_sets_for_campaign_run(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
) -> dict[str, set[object]]:
    values = {field: set() for field in _CAMPAIGN_HISTORICAL_SLOT_IDENTITY_FIELDS}
    cursor = connection.execute(
        """SELECT token_slot_id,token_identity,token_row_id,mint_identity,
                  pair_identity,pair_row_id
           FROM printer_memory_factory_campaign_token_slots
           WHERE campaign_id=? AND run_id=?""",
        (campaign_id, campaign_run_id),
    )
    for row in cursor.fetchall():
        for index, field in enumerate(_CAMPAIGN_HISTORICAL_SLOT_IDENTITY_FIELDS):
            values[field].add(row[index])
    return values


def _historical_slot_identity_sets(
    connection: sqlite3.Connection,
    *,
    binding: MultiCycleCampaignBinding,
) -> dict[str, set[object]]:
    return _historical_slot_identity_sets_for_campaign_run(
        connection,
        campaign_id=binding.campaign_id,
        campaign_run_id=binding.campaign_run_id,
    )


def load_campaign_historical_slot_identity_sets(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
) -> dict[str, set[object]]:
    """Read-only campaign/run historical admitted-slot identity sets.

    Reuses the exact slot-table semantics owned by this coordinator. Callers must
    not reconstruct a parallel campaign-history policy elsewhere.
    """
    return _historical_slot_identity_sets_for_campaign_run(
        connection,
        campaign_id=_required(campaign_id, "campaign_id"),
        campaign_run_id=_required(campaign_run_id, "campaign_run_id"),
    )


def require_established_campaign_historical_identity_sets(
    historical: Mapping[str, set[object]] | None,
) -> dict[str, set[object]]:
    """Fail closed when required later-cycle history is missing or empty.

    A genuine later cycle must observe earlier admitted-slot identity evidence.
    Structurally valid empty sets must not silently become no exclusions.
    """
    if historical is None or not isinstance(historical, Mapping):
        raise MultiCycleCoordinatorError(
            "INTERNAL_CAMPAIGN_HISTORICAL_IDENTITY_UNAVAILABLE"
        )
    established: dict[str, set[object]] = {}
    for field in _CAMPAIGN_HISTORICAL_SLOT_IDENTITY_FIELDS:
        values = historical.get(field)
        if not isinstance(values, set):
            raise MultiCycleCoordinatorError(
                "INTERNAL_CAMPAIGN_HISTORICAL_IDENTITY_UNAVAILABLE"
            )
        established[field] = values
    if not established["mint_identity"]:
        raise MultiCycleCoordinatorError(
            "INTERNAL_CAMPAIGN_HISTORICAL_IDENTITY_UNAVAILABLE"
        )
    return established


def _candidate_resolvable_historical_identity(
    candidate: Mapping[str, Any],
    *,
    field: str,
) -> object | None:
    if field == "mint_identity":
        for key in ("mint_identity", "mint"):
            value = candidate.get(key)
            if value is not None and str(value).strip() != "":
                return value
        return None
    if field == "pair_identity":
        for key in ("pair_identity", "pool", "pair_address", "pumpswap_pool"):
            value = candidate.get(key)
            if value is not None and str(value).strip() != "":
                return value
        return None
    value = candidate.get(field)
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def filter_candidates_by_campaign_historical_disjointness(
    candidates: Sequence[Mapping[str, Any]],
    *,
    historical: Mapping[str, set[object]],
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """Split eligible inventory into fresh vs campaign-history collisions.

    Historical candidates remain available as diagnostic/rejection evidence. They
    must not consume a later-cycle fresh selection slot. Filter first; callers
    then invoke the existing seeded selector/freeze authority over fresh only.
    """
    if not isinstance(historical, Mapping):
        raise MultiCycleCoordinatorError(
            "campaign historical identity sets are unavailable"
        )
    fresh: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for raw in candidates:
        item = dict(raw)
        collided_field: str | None = None
        for field in _CAMPAIGN_HISTORICAL_DISJOINT_CANDIDATE_FIELDS:
            history_values = historical.get(field)
            if not isinstance(history_values, set):
                raise MultiCycleCoordinatorError(
                    "campaign historical identity sets are unavailable"
                )
            value = _candidate_resolvable_historical_identity(item, field=field)
            if value is None:
                continue
            if value in history_values:
                collided_field = field
                break
        if collided_field is not None:
            exclusion = dict(item)
            exclusion["campaign_historical_disjointness_rejected"] = True
            exclusion["campaign_historical_disjointness_field"] = collided_field
            excluded.append(exclusion)
        else:
            fresh.append(item)
    return tuple(fresh), tuple(excluded)


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

    distinct_fields = tuple(
        field for field in identity_kinds if field != "lifecycle_identity"
    ) + row_fields
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
        result = _admit_two_token_cycle_in_transaction(
            connection,
            binding=binding,
            policy=policy,
            now=now,
            health=current_health,
            slots=slots,
        )
        if not result.mutation_performed:
            connection.rollback()
            return result
        connection.commit()
        return result
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


def _admit_two_token_cycle_in_transaction(
    connection: sqlite3.Connection,
    *,
    binding: MultiCycleCampaignBinding,
    policy: MultiCycleCapacityPolicy,
    now: datetime,
    slots: Sequence[Mapping[str, Any]],
    health: MultiCycleAdmissionHealth,
    required_cycle_id: str | None = None,
) -> PersistedCycleAdmissionResult:
    snapshot = load_multi_cycle_campaign_snapshot(
        connection,
        binding=binding,
        policy=policy,
        now=now,
        health=health,
    )
    evaluation = snapshot.admission_evaluation
    if evaluation.decision != AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE:
        return PersistedCycleAdmissionResult(
            evaluation=evaluation,
            cycle_id=None,
            cycle_ordinal=None,
            mutation_performed=False,
            snapshot_before=snapshot,
        )
    validated_slots = _validate_candidate_slots(
        connection, binding=binding, slots=slots
    )
    next_ordinal = snapshot.session.admissions_completed + 1
    if next_ordinal > policy.total_cycle_admission_ceiling:
        raise MultiCycleCoordinatorError("next cycle would exceed session ceiling")
    cycle_id = _next_cycle_identity(snapshot.first_cycle_id, next_ordinal)
    if required_cycle_id is not None and cycle_id != required_cycle_id:
        raise MultiCycleCoordinatorError("proposed cycle identity mismatch")
    if connection.execute(
        "SELECT 1 FROM printer_memory_factory_campaign_cycles WHERE cycle_id=?",
        (cycle_id,),
    ).fetchone() is not None:
        raise MultiCycleCoordinatorError("derived cycle identity already exists")
    cycle_scoped_slots = tuple(
        {
            **slot,
            "token_slot_id": cycle_scoped_token_slot_id(
                cycle_id=cycle_id,
                slot_ordinal=int(slot["slot_ordinal"]),
            ),
        }
        for slot in validated_slots
    )
    create_cycle_with_two_slots(
        connection,
        campaign_id=binding.campaign_id,
        run_id=binding.campaign_run_id,
        cycle_id=cycle_id,
        cycle_ordinal=next_ordinal,
        slots=cycle_scoped_slots,
        now=_normalize_time(now).isoformat(),
        commit_transaction=False,
    )
    return PersistedCycleAdmissionResult(
        evaluation=evaluation,
        cycle_id=cycle_id,
        cycle_ordinal=next_ordinal,
        mutation_performed=True,
        snapshot_before=snapshot,
    )


def _frozen_pair_requalification_authority(
    connection: sqlite3.Connection,
    item: Any,
    *,
    attempt_id: str,
    campaign_id: str,
    campaign_run_id: str,
    cycle_id: str,
    tracking_lane: str,
    assessed_at: datetime,
) -> tuple[bool, dict[str, object] | None]:
    """Derive cooldown reopening from the exact frozen lane plus frozen evidence.

    The earlier holder/tracking precheck is intentionally lane-agnostic.  It
    therefore cannot own the final requalification decision for a later exact
    FAST/NORMAL lane.  Re-read the exact frozen lane inside the same admission
    transaction.  A fresh lane needs no requalification.  An expired cooldown
    may reopen only when this PAIR_READY item carries current holder evidence
    from the same durable attempt.
    """
    from printer_v1.lifecycle.tracking_queue import assess_tracking_handoff

    exact = assess_tracking_handoff(
        connection,
        token_id=int(item.token_row_id),
        pair_id=int(item.pair_row_id),
        tracking_lane=tracking_lane,
        assessed_at=assessed_at,
    )
    if not exact.eligible:
        raise MultiCycleCoordinatorError(
            "pre-admission frozen tracking lane is no longer claimable"
        )
    if not exact.requalification_eligible:
        return False, None

    try:
        payload = json.loads(str(item.canonical_evidence_json))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MultiCycleCoordinatorError(
            "pre-admission frozen holder evidence is invalid"
        ) from exc
    if not isinstance(payload, Mapping):
        raise MultiCycleCoordinatorError(
            "pre-admission frozen holder evidence is invalid"
        )
    holder = payload.get("holder_evidence")
    if not isinstance(holder, Mapping) or holder.get("eligible") is not True:
        raise MultiCycleCoordinatorError(
            "expired cooldown requires frozen current holder evidence"
        )
    return True, {
        "campaign_id": campaign_id,
        "run_id": campaign_run_id,
        "cycle_id": cycle_id,
        "pre_admission_attempt_id": attempt_id,
        "frozen_tracking_lane": tracking_lane,
        "predecessor_queue_id": exact.queue_id,
        "frozen_evidence_hash": str(item.canonical_evidence_hash),
        "fresh_evidence_evaluated_at": item.observed_at.isoformat(),
        "holder_source_name": holder.get("source_name"),
        "holder_evidence_reason": holder.get("reason"),
    }


def admit_two_token_cycle_from_attempt(
    connection: sqlite3.Connection,
    *,
    binding: MultiCycleCampaignBinding,
    policy: MultiCycleCapacityPolicy,
    now: datetime,
    attempt_id: str,
    health: MultiCycleAdmissionHealth,
) -> PersistedCycleAdmissionResult:
    """Atomically create exact cycle 2 and consume its frozen discovery pair."""
    from printer_v1.operator_cli.pre_admission_discovery_attempt import (
        PreAdmissionAttemptError,
        PreAdmissionAttemptState,
        load_pre_admission_attempt,
        load_pre_admission_pair,
    )

    if connection.in_transaction:
        raise MultiCycleCoordinatorError(
            "coordinator admission requires ownership of a fresh transaction"
        )
    if not isinstance(health, MultiCycleAdmissionHealth):
        raise MultiCycleCoordinatorError("authoritative admission health is required")
    try:
        connection.execute("BEGIN IMMEDIATE")
        attempt = load_pre_admission_attempt(connection, attempt_id=attempt_id)
        if attempt.state is not PreAdmissionAttemptState.PAIR_READY:
            raise MultiCycleCoordinatorError("pre-admission attempt is not unconsumed PAIR_READY")
        if (
            attempt.campaign_id != binding.campaign_id
            or attempt.campaign_run_id != binding.campaign_run_id
            or attempt.configuration_id != binding.configuration_id
            or attempt.authoritative_factory_run_id
            != binding.authoritative_factory_run_id
            or attempt.proposed_cycle_ordinal != 2
        ):
            raise MultiCycleCoordinatorError("pre-admission attempt ownership mismatch")
        try:
            items = load_pre_admission_pair(connection, attempt_id=attempt_id)
        except PreAdmissionAttemptError as exc:
            if str(exc) == "FROZEN_TRACKING_LANE_MISSING":
                raise MultiCycleCoordinatorError(
                    "pre-admission frozen tracking lane missing or invalid"
                ) from exc
            raise
        # Shared Cycle-N cadence activation: claim exact tracking authority and
        # project token_status before immutable slot INSERT binds tracking_queue_id.
        # Lane must come from immutable PAIR_READY frozen provenance — never a default.
        from printer_v1.operator_cli.cadence_authority import (
            CadenceAuthorityError,
            claim_tracking_authority_for_slot_insert,
        )

        claimed_queue_ids: list[int] = []
        try:
            for item in items:
                frozen_lane = item.frozen_tracking_lane
                if frozen_lane not in {"TRACK_FAST", "TRACK_NORMAL"}:
                    raise MultiCycleCoordinatorError(
                        "pre-admission frozen tracking lane missing or invalid"
                    )
                (
                    fresh_requalification,
                    requalification_lineage,
                ) = _frozen_pair_requalification_authority(
                    connection,
                    item,
                    attempt_id=attempt_id,
                    campaign_id=binding.campaign_id,
                    campaign_run_id=binding.campaign_run_id,
                    cycle_id=attempt.proposed_cycle_id,
                    tracking_lane=frozen_lane,
                    assessed_at=now,
                )
                claimed_queue_ids.append(
                    claim_tracking_authority_for_slot_insert(
                        connection,
                        token_row_id=int(item.token_row_id),
                        pair_row_id=int(item.pair_row_id),
                        tracking_lane=frozen_lane,
                        now=now,
                        priority_reason="later_cycle_slot_tracking_activation",
                        fresh_evidence_requalification=fresh_requalification,
                        requalification_lineage=requalification_lineage,
                    )
                )
        except CadenceAuthorityError as exc:
            raise MultiCycleCoordinatorError(
                f"later-cycle tracking activation failed: {exc}"
            ) from exc
        slots = tuple(
            {
                "token_slot_id": cycle_scoped_token_slot_id(
                    cycle_id=attempt.proposed_cycle_id,
                    slot_ordinal=item.slot_ordinal,
                ),
                "slot_ordinal": item.slot_ordinal,
                "token_identity": item.token_identity,
                "token_row_id": item.token_row_id,
                "mint_identity": item.mint_identity,
                "pair_identity": item.pair_identity,
                "pair_row_id": item.pair_row_id,
                "lifecycle_identity": item.lifecycle_identity,
                "tracking_queue_id": queue_id,
                "replacement_predecessor_slot_id": None,
            }
            for item, queue_id in zip(items, claimed_queue_ids, strict=True)
        )
        result = _admit_two_token_cycle_in_transaction(
            connection,
            binding=binding,
            policy=policy,
            now=now,
            slots=slots,
            health=health,
            required_cycle_id=attempt.proposed_cycle_id,
        )
        if not result.mutation_performed:
            connection.rollback()
            return result
        instant = _normalize_time(now).isoformat()
        consumed = connection.execute(
            """UPDATE printer_pre_admission_discovery_attempts
               SET attempt_state='CONSUMED',consumed_cycle_id=?,consumed_at=?,updated_at=?
               WHERE attempt_id=? AND attempt_state='PAIR_READY'
                 AND consumed_cycle_id IS NULL AND consumed_at IS NULL""",
            (result.cycle_id, instant, instant, attempt_id),
        )
        if consumed.rowcount != 1:
            raise MultiCycleCoordinatorError("pre-admission attempt consumption conflict")
        connection.commit()
        return result
    except (MultiCycleCoordinatorError, PreAdmissionAttemptError):
        if connection.in_transaction:
            connection.rollback()
        raise
    except sqlite3.Error as exc:
        if connection.in_transaction:
            connection.rollback()
        raise MultiCycleCoordinatorError(
            f"pre-admission cycle consumption failed: {exc}"
        ) from exc
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise

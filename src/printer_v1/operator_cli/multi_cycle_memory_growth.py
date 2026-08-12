"""Pure bounded multi-cycle capacity policy for Printer V1 V2-9.8B.

This module does not fetch sources, schedule or execute work, mutate SQLite,
create memory, activate 12h/24h, retrieve memory, or create financial actions.
It defines the six-capable through-4h admission/session envelope that later
operational integration and bounded proofs may consume.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any

from printer_v1.operator_cli.operational_standard_4h import (
    standard_four_hour_capacity_contract,
)


TOKENS_PER_CYCLE = 2
MAX_THROUGH_4H_TOKENS = 6
MAX_ACTIVE_TWO_TOKEN_CYCLES = 3
MIN_CYCLE_ADMISSION_SPACING_SECONDS = 300
_ALLOWED_CONFIGURED_CAPACITIES = frozenset({2, 4, 6})


class AdmissionDecision(StrEnum):
    ADMIT_TWO_TOKEN_CYCLE = "ADMIT_TWO_TOKEN_CYCLE"
    DEFER = "DEFER"
    DRAIN = "DRAIN"
    COMPLETE = "COMPLETE"
    BLOCKED = "BLOCKED"


class MultiCycleSessionPhase(StrEnum):
    ACTIVE_INTAKE = "ACTIVE_INTAKE"
    DRAIN = "DRAIN"
    COMPLETE = "COMPLETE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class AdmissionEvaluation:
    decision: AdmissionDecision
    reason: str


@dataclass(frozen=True)
class MultiCycleCapacityPolicy:
    configured_through_4h_token_ceiling: int
    configured_active_cycle_ceiling: int
    intake_duration_seconds: int
    min_admission_spacing_seconds: int = MIN_CYCLE_ADMISSION_SPACING_SECONDS

    def validate(self) -> None:
        tokens = self.configured_through_4h_token_ceiling
        cycles = self.configured_active_cycle_ceiling
        if type(tokens) is not int or tokens not in _ALLOWED_CONFIGURED_CAPACITIES:
            raise ValueError("configured through-4h token ceiling must be 2, 4, or 6")
        if type(cycles) is not int or cycles <= 0 or cycles > MAX_ACTIVE_TWO_TOKEN_CYCLES:
            raise ValueError("configured active cycle ceiling must be between 1 and 3")
        if tokens != cycles * TOKENS_PER_CYCLE:
            raise ValueError("configured token and cycle ceilings must describe exact two-token cycles")
        if type(self.intake_duration_seconds) is not int or self.intake_duration_seconds <= 0:
            raise ValueError("intake duration must be a positive integer")
        if (
            type(self.min_admission_spacing_seconds) is not int
            or self.min_admission_spacing_seconds < MIN_CYCLE_ADMISSION_SPACING_SECONDS
        ):
            raise ValueError("admission spacing cannot be less than 300 seconds")


@dataclass(frozen=True)
class MultiCycleAdmissionState:
    now: datetime
    intake_started_at: datetime
    active_through_4h_tokens: int
    active_cycles: int
    last_cycle_admitted_at: datetime | None = None
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
class MultiCycleSessionSnapshot:
    intake_started_at: datetime
    intake_deadline: datetime
    configured_through_4h_token_ceiling: int
    configured_active_cycle_ceiling: int
    active_through_4h_tokens: int
    active_cycles: int
    admissions_completed: int
    last_cycle_admitted_at: datetime | None
    phase: MultiCycleSessionPhase


def _normalize_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _invalid_state_reason(
    policy: MultiCycleCapacityPolicy, state: MultiCycleAdmissionState
) -> str | None:
    try:
        policy.validate()
    except ValueError as exc:
        return str(exc)

    if type(state.active_through_4h_tokens) is not int or state.active_through_4h_tokens < 0:
        return "active through-4h token count is invalid"
    if type(state.active_cycles) is not int or state.active_cycles < 0:
        return "active cycle count is invalid"
    if state.active_through_4h_tokens > policy.configured_through_4h_token_ceiling:
        return "active through-4h token count exceeds configured ceiling"
    if state.active_cycles > policy.configured_active_cycle_ceiling:
        return "active cycle count exceeds configured ceiling"
    if state.active_cycles == 0 and state.active_through_4h_tokens != 0:
        return "active tokens cannot exist without an active cycle"
    if state.active_cycles > 0:
        if state.active_through_4h_tokens < state.active_cycles:
            return "each active cycle must retain at least one active through-4h token"
        if state.active_through_4h_tokens > state.active_cycles * TOKENS_PER_CYCLE:
            return "active token count exceeds two-token cycle ownership"

    now = _normalize_time(state.now)
    started = _normalize_time(state.intake_started_at)
    if now < started:
        return "current time precedes intake start"
    if state.last_cycle_admitted_at is not None:
        admitted = _normalize_time(state.last_cycle_admitted_at)
        if admitted < started or admitted > now:
            return "last admission time is outside the current session interval"
    return None


def evaluate_session_phase(
    policy: MultiCycleCapacityPolicy,
    state: MultiCycleAdmissionState,
) -> MultiCycleSessionPhase:
    """Return the fail-closed phase of one bounded intake/drain session."""
    invalid = _invalid_state_reason(policy, state)
    if invalid is not None:
        return MultiCycleSessionPhase.BLOCKED
    if (
        not state.campaign_supervision_healthy
        or not state.lease_healthy
        or not state.db_healthy
        or state.shared_terminal_condition
    ):
        return MultiCycleSessionPhase.BLOCKED

    now = _normalize_time(state.now)
    deadline = _normalize_time(state.intake_started_at) + timedelta(
        seconds=policy.intake_duration_seconds
    )
    if state.cancellation_requested or now >= deadline:
        if state.active_cycles == 0 and state.active_through_4h_tokens == 0:
            return MultiCycleSessionPhase.COMPLETE
        return MultiCycleSessionPhase.DRAIN
    return MultiCycleSessionPhase.ACTIVE_INTAKE


def evaluate_cycle_admission(
    policy: MultiCycleCapacityPolicy,
    state: MultiCycleAdmissionState,
) -> AdmissionEvaluation:
    """Decide whether one new exact two-token cycle may enter the session."""
    invalid = _invalid_state_reason(policy, state)
    if invalid is not None:
        return AdmissionEvaluation(
            AdmissionDecision.BLOCKED,
            f"invalid_state:{invalid}",
        )

    if not state.campaign_supervision_healthy:
        return AdmissionEvaluation(AdmissionDecision.BLOCKED, "campaign_supervision_unhealthy")
    if not state.lease_healthy:
        return AdmissionEvaluation(AdmissionDecision.BLOCKED, "campaign_lease_unhealthy")
    if not state.db_healthy:
        return AdmissionEvaluation(AdmissionDecision.BLOCKED, "authoritative_db_unhealthy")
    if state.shared_terminal_condition:
        return AdmissionEvaluation(AdmissionDecision.BLOCKED, "shared_terminal_condition")

    phase = evaluate_session_phase(policy, state)
    if phase == MultiCycleSessionPhase.COMPLETE:
        return AdmissionEvaluation(AdmissionDecision.COMPLETE, "bounded_drain_complete")
    if phase == MultiCycleSessionPhase.DRAIN:
        return AdmissionEvaluation(AdmissionDecision.DRAIN, "intake_closed_drain_only")
    if phase == MultiCycleSessionPhase.BLOCKED:
        return AdmissionEvaluation(AdmissionDecision.BLOCKED, "session_blocked")

    if (
        state.active_through_4h_tokens + TOKENS_PER_CYCLE
        > policy.configured_through_4h_token_ceiling
    ):
        return AdmissionEvaluation(AdmissionDecision.DEFER, "through_4h_capacity_full")
    if state.active_cycles + 1 > policy.configured_active_cycle_ceiling:
        return AdmissionEvaluation(AdmissionDecision.DEFER, "active_cycle_capacity_full")

    if state.last_cycle_admitted_at is not None:
        elapsed = (
            _normalize_time(state.now) - _normalize_time(state.last_cycle_admitted_at)
        ).total_seconds()
        if elapsed < policy.min_admission_spacing_seconds:
            return AdmissionEvaluation(
                AdmissionDecision.DEFER,
                "minimum_admission_spacing_not_elapsed",
            )

    defer_gates = (
        (state.source_budget_available, "source_budget_unavailable"),
        (state.provider_budgets_available, "provider_budget_unavailable"),
        (state.scheduler_budget_available, "scheduler_budget_unavailable"),
        (state.scheduler_due_work_healthy, "scheduler_due_work_unhealthy"),
        (state.close_reserve_available, "close_reserve_unavailable"),
        (state.discovery_capacity_available, "discovery_capacity_unavailable"),
        (state.protected_work_capacity_available, "protected_work_capacity_unavailable"),
    )
    for available, reason in defer_gates:
        if not available:
            return AdmissionEvaluation(AdmissionDecision.DEFER, reason)

    return AdmissionEvaluation(
        AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE,
        "all_pair_admission_requirements_met",
    )


def scaled_standard_four_hour_capacity_contract(
    configured_through_4h_tokens: int,
) -> dict[str, Any]:
    """Project 2/4/6-token ceilings from the canonical two-token 4h contract."""
    if configured_through_4h_tokens not in _ALLOWED_CONFIGURED_CAPACITIES:
        raise ValueError("configured through-4h capacity must be 2, 4, or 6")
    cycles = configured_through_4h_tokens // TOKENS_PER_CYCLE
    policy = MultiCycleCapacityPolicy(
        configured_through_4h_token_ceiling=configured_through_4h_tokens,
        configured_active_cycle_ceiling=cycles,
        intake_duration_seconds=1,
    )
    policy.validate()

    base = standard_four_hour_capacity_contract()
    return {
        "implementation_max_through_4h_tokens": MAX_THROUGH_4H_TOKENS,
        "implementation_max_active_cycles": MAX_ACTIVE_TWO_TOKEN_CYCLES,
        "configured_through_4h_tokens": configured_through_4h_tokens,
        "configured_active_cycles": cycles,
        "tokens_per_cycle": TOKENS_PER_CYCLE,
        "minimum_cycle_admission_spacing_seconds": MIN_CYCLE_ADMISSION_SPACING_SECONDS,
        "shared_discovery_requests": cycles * int(base["shared_discovery_requests"]),
        "lifecycle_request_outer_ceiling": cycles
        * int(base["lifecycle_request_outer_ceiling"]),
        "lifecycle_requests_per_token": int(base["lifecycle_requests_per_token"]),
        "lifecycle_scheduler_outer_ceiling": cycles
        * int(base["lifecycle_scheduler_outer_ceiling"]),
        "automatic_retries": 0,
        "endpoint_rotation": False,
        "long_windows_activated": False,
    }

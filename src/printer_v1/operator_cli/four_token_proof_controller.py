"""Proof-only second-cycle controller for the bounded four-token capacity proof.

The controller does not implement discovery. It calls one injected callback only
after exact capacity/spacing/health gates pass. That callback must be the existing
operational discovery owner for the newly reserved cycle. The combined discovery
executor remains the sole owner of atomic slot activation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from typing import Callable

from printer_v1.operator_cli.four_token_factory_adapter import (
    FourTokenFactoryAdapterError,
    reserve_second_proof_cycle,
    terminalize_unfilled_reserved_cycle,
    validate_second_cycle_atomic_activation,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    FOUR_TOKEN_PROOF_MIN_SPACING_SECONDS,
    build_four_token_proof_policy,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
)
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    AdmissionDecision,
    MultiCycleAdmissionState,
    evaluate_cycle_admission,
)


class FourTokenProofControllerError(ValueError):
    """Fail-closed proof-controller contract violation."""


@dataclass(frozen=True)
class LaterCycleDiscoveryRequest:
    campaign_id: str
    campaign_run_id: str
    factory_run_id: str
    cycle_id: str
    cycle_ordinal: int
    requested_at: datetime


@dataclass(frozen=True)
class LaterCycleDiscoveryResult:
    cycle_id: str
    terminal_status: str
    first_terminal_cause: str
    selected_count: int
    selection_batch_id: str | None
    source_calls: int
    scheduler_work: int


@dataclass(frozen=True)
class SecondCycleAdmissionResult:
    status: str
    reason: str
    cycle_id: str | None = None
    selected_count: int = 0
    source_calls: int = 0
    scheduler_work: int = 0


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise FourTokenProofControllerError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _required(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise FourTokenProofControllerError(f"{label} must be a non-empty exact string")
    return value


def _first_cycle_state(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
    first_cycle_id: str,
) -> tuple[datetime, int, int]:
    cycles = connection.execute(
        """SELECT cycle_id,cycle_ordinal,cycle_state
           FROM printer_memory_factory_campaign_cycles
           WHERE campaign_id=? AND run_id=? ORDER BY cycle_ordinal""",
        (campaign_id, campaign_run_id),
    ).fetchall()
    if len(cycles) > 2:
        raise FourTokenProofControllerError(
            "four-token proof cannot contain more than two cycles"
        )
    if len(cycles) == 2:
        return datetime.min.replace(tzinfo=timezone.utc), 2, 0
    if len(cycles) != 1:
        raise FourTokenProofControllerError(
            "four-token proof requires exactly one first cycle before second admission"
        )
    row = cycles[0]
    if str(row[0]) != first_cycle_id or int(row[1]) != 1:
        raise FourTokenProofControllerError("first cycle identity/ordinal mismatch")
    if str(row[2]).startswith("TERMINAL_"):
        raise FourTokenProofControllerError(
            "first cycle is already terminal before second-cycle proof admission"
        )
    slots = connection.execute(
        """SELECT slot_ordinal,token_state,created_at
           FROM printer_memory_factory_campaign_token_slots
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
           ORDER BY slot_ordinal""",
        (campaign_id, campaign_run_id, first_cycle_id),
    ).fetchall()
    if len(slots) != 2 or tuple(int(item[0]) for item in slots) != (1, 2):
        raise FourTokenProofControllerError(
            "first cycle does not own the exact initial two-slot pair"
        )
    active_states = {
        "SELECTED",
        "WINDOW_15M_ACTIVE",
        "WINDOW_15M_CLOSED",
        "WINDOW_1H_CONTINUING",
        "WINDOW_1H_CLOSED",
        "WINDOW_4H_CONTINUING",
    }
    active = sum(1 for item in slots if str(item[1]) in active_states)
    if active != 2:
        raise FourTokenProofControllerError(
            "four-token proof requires both first-cycle tokens active at second admission"
        )
    times: set[datetime] = set()
    for item in slots:
        try:
            parsed = datetime.fromisoformat(str(item[2]))
        except ValueError as exc:
            raise FourTokenProofControllerError(
                "first-cycle admission timestamp is malformed"
            ) from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise FourTokenProofControllerError(
                "first-cycle admission timestamp must be timezone-aware"
            )
        times.add(parsed.astimezone(timezone.utc))
    if len(times) != 1:
        raise FourTokenProofControllerError(
            "first-cycle pair does not share one atomic admission timestamp"
        )
    return next(iter(times)), 1, active


def attempt_second_cycle_admission(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
    factory_run_id: str,
    first_cycle_id: str,
    now: datetime,
    next_due_lifecycle_at: datetime | None,
    health: MultiCycleAdmissionHealth,
    discovery_callback: Callable[[LaterCycleDiscoveryRequest], LaterCycleDiscoveryResult],
) -> SecondCycleAdmissionResult:
    """Attempt the one allowed second-cycle admission for the four-token proof."""
    campaign = _required(campaign_id, "campaign_id")
    run = _required(campaign_run_id, "campaign_run_id")
    factory = _required(factory_run_id, "factory_run_id")
    first_cycle = _required(first_cycle_id, "first_cycle_id")
    instant = _utc(now, "now")
    if not isinstance(health, MultiCycleAdmissionHealth):
        raise FourTokenProofControllerError("health must be MultiCycleAdmissionHealth")
    if not callable(discovery_callback):
        raise FourTokenProofControllerError("discovery_callback must be callable")
    if connection.in_transaction:
        raise FourTokenProofControllerError(
            "proof controller requires a connection with no open transaction"
        )

    first_admitted_at, cycle_count, active_tokens = _first_cycle_state(
        connection,
        campaign_id=campaign,
        campaign_run_id=run,
        first_cycle_id=first_cycle,
    )
    if cycle_count == 2:
        return SecondCycleAdmissionResult(
            status="COMPLETE",
            reason="FOUR_TOKEN_PROOF_CYCLE_CEILING_REACHED",
        )

    elapsed = (instant - first_admitted_at).total_seconds()
    if elapsed < FOUR_TOKEN_PROOF_MIN_SPACING_SECONDS:
        return SecondCycleAdmissionResult(
            status="DEFERRED",
            reason="MINIMUM_ADMISSION_SPACING_NOT_ELAPSED",
        )
    if next_due_lifecycle_at is not None:
        due = _utc(next_due_lifecycle_at, "next_due_lifecycle_at")
        if due <= instant:
            return SecondCycleAdmissionResult(
                status="DEFERRED",
                reason="LIFECYCLE_WORK_DUE_FIRST",
            )

    policy = build_four_token_proof_policy()
    state = MultiCycleAdmissionState(
        now=instant,
        intake_started_at=first_admitted_at,
        active_through_4h_tokens=active_tokens,
        active_cycles=1,
        admissions_completed=1,
        last_cycle_admitted_at=first_admitted_at,
        source_budget_available=health.source_budget_available,
        provider_budgets_available=health.provider_budgets_available,
        scheduler_budget_available=health.scheduler_budget_available,
        scheduler_due_work_healthy=health.scheduler_due_work_healthy,
        close_reserve_available=health.close_reserve_available,
        campaign_supervision_healthy=health.campaign_supervision_healthy,
        lease_healthy=health.lease_healthy,
        db_healthy=health.db_healthy,
        shared_terminal_condition=health.shared_terminal_condition,
        cancellation_requested=health.cancellation_requested,
        discovery_capacity_available=health.discovery_capacity_available,
        protected_work_capacity_available=health.protected_work_capacity_available,
    )
    evaluation = evaluate_cycle_admission(policy, state)
    if evaluation.decision != AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE:
        if evaluation.decision == AdmissionDecision.BLOCKED:
            status = "BLOCKED"
        else:
            status = "DEFERRED"
        return SecondCycleAdmissionResult(status=status, reason=evaluation.reason)

    try:
        reserved = reserve_second_proof_cycle(
            connection,
            campaign_id=campaign,
            campaign_run_id=run,
            factory_run_id=factory,
            first_cycle_id=first_cycle,
            now=instant,
        )
    except FourTokenFactoryAdapterError as exc:
        raise FourTokenProofControllerError(str(exc)) from exc

    request = LaterCycleDiscoveryRequest(
        campaign_id=campaign,
        campaign_run_id=run,
        factory_run_id=factory,
        cycle_id=reserved.cycle_id,
        cycle_ordinal=reserved.cycle_ordinal,
        requested_at=instant,
    )
    try:
        result = discovery_callback(request)
    except Exception as exc:
        try:
            terminalize_unfilled_reserved_cycle(
                connection,
                campaign_id=campaign,
                campaign_run_id=run,
                cycle_id=reserved.cycle_id,
                cause="LATER_CYCLE_DISCOVERY_EXCEPTION",
                now=instant,
            )
        except Exception:
            pass
        raise FourTokenProofControllerError(
            f"later-cycle discovery callback failed: {type(exc).__name__}:{exc}"
        ) from exc

    if not isinstance(result, LaterCycleDiscoveryResult):
        raise FourTokenProofControllerError(
            "later-cycle discovery callback returned an unsupported result"
        )
    if result.cycle_id != reserved.cycle_id:
        raise FourTokenProofControllerError("later-cycle discovery returned wrong cycle id")
    if type(result.selected_count) is not int or result.selected_count not in (0, 2):
        raise FourTokenProofControllerError(
            "later-cycle discovery must activate exactly two tokens or zero"
        )
    if type(result.source_calls) is not int or result.source_calls < 0:
        raise FourTokenProofControllerError("later-cycle source accounting is invalid")
    if type(result.scheduler_work) is not int or result.scheduler_work < 0:
        raise FourTokenProofControllerError("later-cycle Scheduler accounting is invalid")

    if result.terminal_status == "COMPLETED" and result.selected_count == 2:
        try:
            validate_second_cycle_atomic_activation(
                connection,
                campaign_id=campaign,
                campaign_run_id=run,
                factory_run_id=factory,
                cycle_id=reserved.cycle_id,
            )
        except FourTokenFactoryAdapterError as exc:
            raise FourTokenProofControllerError(str(exc)) from exc
        if not result.selection_batch_id:
            raise FourTokenProofControllerError(
                "admitted second cycle lacks selection batch identity"
            )
        return SecondCycleAdmissionResult(
            status="ADMITTED",
            reason="SECOND_TWO_TOKEN_CYCLE_ADMITTED",
            cycle_id=reserved.cycle_id,
            selected_count=2,
            source_calls=result.source_calls,
            scheduler_work=result.scheduler_work,
        )

    if result.selected_count == 0 and result.terminal_status in {"FAILED", "BLOCKED"}:
        try:
            terminalize_unfilled_reserved_cycle(
                connection,
                campaign_id=campaign,
                campaign_run_id=run,
                cycle_id=reserved.cycle_id,
                cause=result.first_terminal_cause,
                now=instant,
            )
        except FourTokenFactoryAdapterError as exc:
            raise FourTokenProofControllerError(str(exc)) from exc
        return SecondCycleAdmissionResult(
            status="BLOCKED",
            reason=result.first_terminal_cause,
            cycle_id=reserved.cycle_id,
            selected_count=0,
            source_calls=result.source_calls,
            scheduler_work=result.scheduler_work,
        )

    raise FourTokenProofControllerError(
        "later-cycle discovery result is not a lawful two-or-none terminal outcome"
    )

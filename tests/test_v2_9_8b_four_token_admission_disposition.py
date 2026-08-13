from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from printer_v1.operator_cli import four_token_proof_integration as integration
from printer_v1.operator_cli.authoritative_admission_health import (
    AdmissionHealthProjection,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
    MultiCycleCampaignSnapshot,
)
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    AdmissionDecision,
    AdmissionEvaluation,
    MultiCycleSessionPhase,
    MultiCycleSessionSnapshot,
)


NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
DEADLINE = NOW + timedelta(minutes=20)


def _health(**changes: bool) -> MultiCycleAdmissionHealth:
    health = MultiCycleAdmissionHealth(
        source_budget_available=True,
        provider_budgets_available=True,
        scheduler_budget_available=True,
        scheduler_due_work_healthy=True,
        close_reserve_available=True,
        campaign_supervision_healthy=True,
        lease_healthy=True,
        db_healthy=True,
        shared_terminal_condition=False,
        cancellation_requested=False,
        discovery_capacity_available=True,
        protected_work_capacity_available=True,
    )
    return replace(health, **changes)


def _projection(
    *,
    health: MultiCycleAdmissionHealth | None = None,
    recheck_at: datetime | None = None,
    recheck_on_lifecycle_change: bool = False,
) -> AdmissionHealthProjection:
    return AdmissionHealthProjection(
        health=health or _health(),
        recheck_at=recheck_at,
        recheck_on_lifecycle_change=recheck_on_lifecycle_change,
        evidence=(),
        reasons=(),
    )


def _readiness(
    decision: AdmissionDecision,
    reason: str,
    *,
    last_admitted_at: datetime | None = NOW - timedelta(minutes=10),
) -> integration.FourTokenControllerReadiness:
    session = MultiCycleSessionSnapshot(
        intake_started_at=NOW - timedelta(minutes=10),
        intake_deadline=DEADLINE,
        configured_through_4h_token_ceiling=4,
        configured_active_cycle_ceiling=2,
        total_cycle_admission_ceiling=2,
        active_through_4h_tokens=2,
        active_cycles=1,
        admissions_completed=1,
        last_cycle_admitted_at=last_admitted_at,
        phase=MultiCycleSessionPhase.ACTIVE_INTAKE,
    )
    snapshot = MultiCycleCampaignSnapshot(
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        configuration_id="configuration-1",
        authoritative_factory_run_id="factory-1",
        cycle_ids=("cycle-1",),
        active_cycle_ids=("cycle-1",),
        active_token_slot_ids=("slot-1", "slot-2"),
        first_cycle_id="cycle-1",
        session=session,
        admission_evaluation=AdmissionEvaluation(decision, reason),
    )
    return integration.FourTokenControllerReadiness(
        snapshot=snapshot,
        wake=integration.FourTokenFactoryWake(at=NOW, reason="CYCLE_ADMISSION"),
    )


def _decide(
    readiness: integration.FourTokenControllerReadiness,
    *,
    projection: AdmissionHealthProjection | None = None,
    now: datetime = NOW,
    next_due_work_at: datetime | None = None,
    proof_deadline: datetime = DEADLINE,
    relevant_pending_lifecycle_work: bool = False,
):
    return integration.decide_four_token_admission_disposition(
        readiness=readiness,
        health_projection=projection or _projection(),
        policy=integration.build_four_token_proof_policy(),
        now=now,
        next_due_work_at=next_due_work_at,
        proof_deadline=proof_deadline,
        relevant_pending_lifecycle_work=relevant_pending_lifecycle_work,
    )


def test_stop_health_precedes_lifecycle_deadline_and_admission() -> None:
    admit = _readiness(
        AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE,
        "all_pair_admission_requirements_met",
    )
    cancelled = _decide(
        admit,
        projection=_projection(health=_health(cancellation_requested=True)),
        next_due_work_at=NOW,
        proof_deadline=NOW,
        relevant_pending_lifecycle_work=True,
    )
    assert cancelled.kind == integration.FourTokenAdmissionDispositionKind.DRAIN
    assert cancelled.reason == "CANCELLATION_REQUESTED"
    assert cancelled.at is None
    assert cancelled.admission_allowed is False

    for field, reason in (
        ("lease_healthy", "LEASE_UNHEALTHY"),
        ("db_healthy", "DB_UNHEALTHY"),
        ("shared_terminal_condition", "SHARED_TERMINAL_CONDITION"),
    ):
        value = True if field == "shared_terminal_condition" else False
        result = _decide(
            admit,
            projection=_projection(health=_health(**{field: value})),
            next_due_work_at=NOW,
            proof_deadline=NOW,
            relevant_pending_lifecycle_work=True,
        )
        assert result.kind == integration.FourTokenAdmissionDispositionKind.BLOCKED
        assert result.reason == reason
        assert result.at is None
        assert result.admission_allowed is False


def test_lifecycle_and_deadline_ties_both_outrank_admission() -> None:
    admit = _readiness(
        AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE,
        "all_pair_admission_requirements_met",
    )
    lifecycle = _decide(
        admit,
        next_due_work_at=NOW,
        proof_deadline=NOW,
        relevant_pending_lifecycle_work=True,
    )
    assert lifecycle.kind == integration.FourTokenAdmissionDispositionKind.LIFECYCLE_WORK
    assert lifecycle.at == NOW
    assert lifecycle.admission_allowed is False

    deadline = _decide(admit, proof_deadline=NOW)
    assert deadline.kind == integration.FourTokenAdmissionDispositionKind.PROOF_DEADLINE
    assert deadline.at == NOW
    assert deadline.admission_allowed is False


def test_valid_due_admission_is_the_only_admitting_disposition() -> None:
    result = _decide(
        _readiness(
            AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE,
            "all_pair_admission_requirements_met",
        )
    )
    assert result.kind == integration.FourTokenAdmissionDispositionKind.CYCLE_ADMISSION
    assert result.reason == "ADMISSION_READY"
    assert result.at == NOW
    assert result.admission_allowed is True


def test_spacing_defer_uses_only_persisted_spacing_boundary() -> None:
    last_admitted_at = NOW - timedelta(seconds=100)
    readiness = _readiness(
        AdmissionDecision.DEFER,
        "minimum_admission_spacing_not_elapsed",
        last_admitted_at=last_admitted_at,
    )
    result = _decide(
        readiness,
        projection=_projection(recheck_at=NOW + timedelta(seconds=5)),
    )
    assert result.kind == integration.FourTokenAdmissionDispositionKind.REARM
    assert result.reason == "PERSISTED_ADMISSION_SPACING_BOUNDARY"
    assert result.at == last_admitted_at + timedelta(seconds=300)
    assert result.admission_allowed is False

    deadline_tie = _decide(
        readiness,
        proof_deadline=last_admitted_at + timedelta(seconds=300),
    )
    assert deadline_tie.kind == integration.FourTokenAdmissionDispositionKind.PROOF_DEADLINE


def test_capacity_defer_uses_authoritative_health_recheck_only() -> None:
    recheck = NOW + timedelta(seconds=37, microseconds=1)
    result = _decide(
        _readiness(AdmissionDecision.DEFER, "provider_budget_unavailable"),
        projection=_projection(recheck_at=recheck),
    )
    assert result.kind == integration.FourTokenAdmissionDispositionKind.REARM
    assert result.reason == "AUTHORITATIVE_HEALTH_RECHECK"
    assert result.at == recheck


def test_lifecycle_change_rearm_requires_actual_relevant_pending_work() -> None:
    deferred = _readiness(
        AdmissionDecision.DEFER,
        "protected_work_capacity_unavailable",
    )
    blocked = _decide(
        deferred,
        projection=_projection(recheck_on_lifecycle_change=True),
        next_due_work_at=NOW + timedelta(minutes=2),
        relevant_pending_lifecycle_work=False,
    )
    assert blocked.kind == integration.FourTokenAdmissionDispositionKind.BLOCKED
    assert blocked.reason == "NO_AUTHORITATIVE_REARM_BOUNDARY"
    assert blocked.at is None

    lifecycle = _decide(
        deferred,
        projection=_projection(recheck_on_lifecycle_change=True),
        next_due_work_at=NOW + timedelta(minutes=2),
        relevant_pending_lifecycle_work=True,
    )
    assert lifecycle.kind == integration.FourTokenAdmissionDispositionKind.LIFECYCLE_WORK
    assert lifecycle.at == NOW + timedelta(minutes=2)


def test_blocked_drain_and_complete_never_rearm_or_admit() -> None:
    for decision, expected in (
        (AdmissionDecision.BLOCKED, integration.FourTokenAdmissionDispositionKind.BLOCKED),
        (AdmissionDecision.DRAIN, integration.FourTokenAdmissionDispositionKind.DRAIN),
        (AdmissionDecision.COMPLETE, integration.FourTokenAdmissionDispositionKind.COMPLETE),
    ):
        result = _decide(
            _readiness(decision, f"{decision.value.lower()}_reason"),
            projection=_projection(
                recheck_at=NOW + timedelta(seconds=1),
                recheck_on_lifecycle_change=True,
            ),
            next_due_work_at=NOW + timedelta(seconds=1),
            relevant_pending_lifecycle_work=True,
        )
        assert result.kind == expected
        assert result.at is None
        assert result.admission_allowed is False

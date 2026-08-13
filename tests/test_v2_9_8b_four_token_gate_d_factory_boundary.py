from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from printer_v1.operator_cli.authoritative_admission_health import (
    AdmissionHealthProjection,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    FourTokenAdmissionDisposition,
    FourTokenAdmissionDispositionKind,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
    MultiCycleCampaignBinding,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    _run_four_token_admission_boundary,
)


NOW = datetime(2026, 8, 13, 12, 5, tzinfo=timezone.utc)


def _health(**changes):
    value = MultiCycleAdmissionHealth(
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
    return replace(value, **changes)


def _projection(health=None):
    return AdmissionHealthProjection(
        health=health or _health(),
        recheck_at=None,
        recheck_on_lifecycle_change=False,
        evidence=(),
        reasons=(),
    )


def test_boundary_projects_fresh_health_before_and_after_one_shot_discovery() -> None:
    calls = []
    projections = iter((_projection(), _projection()))
    disposition = FourTokenAdmissionDisposition(
        FourTokenAdmissionDispositionKind.CYCLE_ADMISSION,
        "ADMISSION_READY",
        NOW,
        True,
    )

    result = _run_four_token_admission_boundary(
        connection=SimpleNamespace(),
        controller=SimpleNamespace(policy=SimpleNamespace()),
        binding=MultiCycleCampaignBinding("campaign", "run", "config", "factory"),
        first_cycle_id="cycle-1",
        now=NOW,
        next_due_work_at=None,
        proof_deadline=NOW + timedelta(hours=5),
        project_health=lambda: (calls.append("health"), next(projections))[1],
        evaluate=lambda projection: (calls.append("evaluate"), disposition)[1],
        later_cycle_callback=lambda **kwargs: (
            calls.append(("discovery", kwargs["admission_health"])),
            SimpleNamespace(attempt_id="attempt-1", state="PAIR_READY"),
        )[1],
        admit=lambda **kwargs: (
            calls.append(("admit", kwargs["health"])),
            SimpleNamespace(mutation_performed=True, cycle_id="cycle-1-2", cycle_ordinal=2),
        )[1],
        materialize=lambda **kwargs: calls.append("materialize"),
        plan_opening=lambda **kwargs: calls.append("plan"),
    )

    assert result.admitted is True
    assert calls == [
        "health",
        "evaluate",
        ("discovery", _health()),
        "health",
        "evaluate",
        ("admit", _health()),
        "materialize",
        "plan",
    ]


def test_post_discovery_health_blocks_stale_admission_without_retry() -> None:
    calls = []
    projections = iter((
        _projection(),
        _projection(_health(provider_budgets_available=False)),
    ))
    dispositions = iter((
        FourTokenAdmissionDisposition(
            FourTokenAdmissionDispositionKind.CYCLE_ADMISSION,
            "ADMISSION_READY", NOW, True,
        ),
        FourTokenAdmissionDisposition(
            FourTokenAdmissionDispositionKind.BLOCKED,
            "PROVIDER_BUDGET_UNAVAILABLE", None, False,
        ),
    ))
    result = _run_four_token_admission_boundary(
        connection=SimpleNamespace(),
        controller=SimpleNamespace(policy=SimpleNamespace()),
        binding=MultiCycleCampaignBinding("campaign", "run", "config", "factory"),
        first_cycle_id="cycle-1",
        now=NOW,
        next_due_work_at=None,
        proof_deadline=NOW + timedelta(hours=5),
        project_health=lambda: next(projections),
        evaluate=lambda projection: next(dispositions),
        later_cycle_callback=lambda **kwargs: (
            calls.append("discovery"),
            SimpleNamespace(attempt_id="attempt-1", state="PAIR_READY"),
        )[1],
        admit=lambda **kwargs: calls.append("admit"),
        materialize=lambda **kwargs: calls.append("materialize"),
        plan_opening=lambda **kwargs: calls.append("plan"),
    )
    assert result.admitted is False
    assert result.attempt_state == "PAIR_READY"
    assert calls == ["discovery"]

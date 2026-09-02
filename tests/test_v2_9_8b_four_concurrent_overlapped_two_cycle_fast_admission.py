"""Focused frozen proofs for four-concurrent overlapped two-cycle fast admission."""

from __future__ import annotations

import inspect
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.discovery.eligible_token_supply import (
    AcquisitionQuantumKind,
    acquisition_governed_request_bound,
    acquisition_quantum_bound,
)
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    ACQUISITION_DEADLINE_EXHAUSTED,
    REFRESH_COMPLETED,
    WAITING_FOR_ELIGIBLE_SUPPLY,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    later_cycle_gate_quantum_seconds,
)
from printer_v1.operator_cli.four_token_operational_composition import (
    exact_operational_policy,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    cycle_step_key,
)
from printer_v1.operator_cli.four_token_proof_zero_state_gate import (
    project_four_token_proof_zero_state,
)
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    AdmissionDecision,
    MultiCycleAdmissionState,
    MultiCycleCapacityPolicy,
    evaluate_cycle_admission,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    FourTokenAdmissionBoundaryResult,
    _cooperative_later_cycle_recheck,
    _later_cycle_acquisition_deadline_conflict,
    run_one_command_15m_factory,
)
from printer_v1.operator_cli.pre_lifecycle_persistent_refresh_owner import (
    PreLifecycleTemporalRefreshOwner,
    abandon_scoped_refresh_waits,
)
from printer_v1.scheduler.contracts import JobKind, JOB_RESOURCE_CATEGORY_ORDER


NOW = datetime(2026, 9, 2, 12, 44, 59, tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def test_operational_policy_is_four_through_4h_two_cycles() -> None:
    policy = exact_operational_policy()
    assert policy["configured_through_4h_tokens"] == 4
    assert policy["configured_active_cycles"] == 2
    assert policy["tokens_per_cycle"] == 2
    assert policy["total_cycle_admission_ceiling"] == 2
    assert policy["minimum_cycle_admission_spacing_seconds"] == 300
    assert policy["lifecycle_request_outer_ceiling"] == 476
    assert policy["lifecycle_requests_per_token"] == 118
    assert policy["lifecycle_scheduler_outer_ceiling"] == 444
    assert policy["automatic_retries"] == 0
    assert policy["endpoint_rotation"] is False
    assert "WINDOW_12H" in policy["locked_windows"]
    assert "WINDOW_24H" in policy["locked_windows"]


def test_third_cycle_and_fifth_token_are_deferred() -> None:
    policy = MultiCycleCapacityPolicy(
        configured_through_4h_token_ceiling=4,
        configured_active_cycle_ceiling=2,
        total_cycle_admission_ceiling=2,
        intake_duration_seconds=18_000,
    )
    state = MultiCycleAdmissionState(
        now=NOW + timedelta(minutes=10),
        intake_started_at=NOW,
        active_through_4h_tokens=4,
        active_cycles=2,
        admissions_completed=2,
        last_cycle_admitted_at=NOW + timedelta(minutes=5),
    )
    evaluation = evaluate_cycle_admission(policy, state)
    assert evaluation.decision in {
        AdmissionDecision.DEFER,
        AdmissionDecision.DRAIN,
        AdmissionDecision.COMPLETE,
    }
    assert evaluation.decision != AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE


def test_cycle_step_keys_isolate_four_tokens() -> None:
    keys = {
        cycle_step_key(slot_ordinal=1, cycle_ordinal=1, suffix="snapshot_00"),
        cycle_step_key(slot_ordinal=2, cycle_ordinal=1, suffix="snapshot_00"),
        cycle_step_key(slot_ordinal=1, cycle_ordinal=2, suffix="snapshot_00"),
        cycle_step_key(slot_ordinal=2, cycle_ordinal=2, suffix="snapshot_00"),
    }
    assert keys == {
        "t1_snapshot_00",
        "t2_snapshot_00",
        "t1_c0002_snapshot_00",
        "t2_c0002_snapshot_00",
    }


def test_initial_later_cycle_gate_keeps_auxiliary_intake_bound() -> None:
    bound = later_cycle_gate_quantum_seconds({})
    assert bound == acquisition_quantum_bound(
        AcquisitionQuantumKind.AUXILIARY_FRESH_INTAKE
    ).worst_case_seconds
    assert bound < 115.0


def test_waiting_refresh_gate_uses_one_request_bound_not_115s() -> None:
    full = acquisition_quantum_bound(AcquisitionQuantumKind.PERSISTED_REFRESH)
    one = acquisition_governed_request_bound(
        AcquisitionQuantumKind.PERSISTED_REFRESH,
        request_kind="DIRECT_PUMP_SIGNATURE_PAGE",
        checkpoint_reserve_seconds=5.0,
    )
    assert full.worst_case_seconds == 115.0
    bound = later_cycle_gate_quantum_seconds(
        {"c2": {"waiting_for_refresh": True, "refresh_ordinal": 1}}
    )
    assert bound == one.worst_case_seconds
    assert bound < 115.0
    now = datetime(2026, 9, 2, 13, 0, 0, tzinfo=timezone.utc)
    next_due = datetime(2026, 9, 2, 13, 1, 28, tzinfo=timezone.utc)
    assert _later_cycle_acquisition_deadline_conflict(
        now=now,
        earliest_lifecycle_deadline=next_due,
        worst_case_quantum_seconds=115.0,
    )
    assert not _later_cycle_acquisition_deadline_conflict(
        now=now,
        earliest_lifecycle_deadline=next_due,
        worst_case_quantum_seconds=bound,
    )


def test_declared_next_request_bound_wins_over_refresh_fallback() -> None:
    bound = later_cycle_gate_quantum_seconds(
        {
            "c2": {
                "waiting_for_refresh": True,
                "next_governed_request_worst_case_seconds": 8.0,
            }
        }
    )
    assert bound == 8.0


def test_already_due_lifecycle_category_outranks_discovery_refresh() -> None:
    order = list(JOB_RESOURCE_CATEGORY_ORDER)
    assert order.index(JobKind.TRACK_FAST_MICRO_EVENT) < order.index(
        JobKind.DISCOVERY_REFRESH
    )
    assert order.index(JobKind.MEMORY_WINDOW_CLOSE) < order.index(
        JobKind.DISCOVERY_REFRESH
    )


def test_acquisition_deadline_wake_is_not_proof_deadline() -> None:
    base = datetime(2026, 9, 2, 13, 20, tzinfo=timezone.utc)
    boundary = FourTokenAdmissionBoundaryResult(
        disposition=object(),
        admitted=False,
        attempt_id="attempt-2",
        attempt_state="RUNNING",
        attempt_wake_at=base + timedelta(minutes=10),
        attempt_acquisition_deadline_at=base + timedelta(minutes=1),
    )
    proof_deadline = base + timedelta(hours=4)
    should_recheck, wake_at = _cooperative_later_cycle_recheck(
        boundary,
        next_due_work_at=base + timedelta(minutes=5),
        proof_deadline=proof_deadline,
        acquisition_deadline_at=base + timedelta(minutes=1),
    )
    assert should_recheck
    assert wake_at == base + timedelta(minutes=1)
    assert wake_at != proof_deadline
    source = inspect.getsource(run_one_command_15m_factory)
    assert "PROOF_DEADLINE" in source
    assert "acquisition_deadline_at=" in source
    proof_stop = source.index("FourTokenAdmissionDispositionKind.PROOF_DEADLINE")
    stop_duration = source.index("stop_reason = STOP_DURATION", proof_stop)
    assert stop_duration > proof_stop


def test_past_due_waiting_insert_claims_without_waiter(tmp_path: Path) -> None:
    db_path = tmp_path / "past-due.sqlite3"
    apply_migrations(db_path)
    started = datetime(2026, 9, 2, 12, 44, 59, tzinfo=timezone.utc)
    due_past = started + timedelta(seconds=600)
    now = due_past + timedelta(seconds=301)
    calls: list[int] = []

    def refresh_stage(connection, **kwargs):
        del connection
        calls.append(int(kwargs["refresh_ordinal"]))
        return {
            "source_operations": 1,
            "provider_failures": 0,
            "channels_unavailable": (),
            "channels_attempted": ("fixture-source-1",),
            "channels_skipped": (),
            "newly_observed_exact_identities": (),
            "promoted_observation_eligible": (),
        }

    owner = PreLifecycleTemporalRefreshOwner(
        db_path,
        campaign_id="campaign-past-due",
        run_id="run-past-due",
        cycle_id="cycle-2",
        supervision_id="supervision-past-due",
        source_governor=True,
        central_scheduler=True,
        acquisition_deadline_at=_iso(started + timedelta(seconds=2400)),
        work_deadline_at=_iso(started + timedelta(seconds=18000)),
        refresh_stage=refresh_stage,
        acquisition_started_at=_iso(started),
        supervision_probe=lambda: {
            "supervision_active": True,
            "cancellation_requested": False,
        },
        waiter=None,
        clock=lambda: _iso(now),
        refresh_interval_seconds=600,
    )
    outcome = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=4,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=9,
        now=_iso(now),
    )
    assert outcome.status == REFRESH_COMPLETED
    assert calls == [1]
    connection = sqlite3.connect(db_path)
    try:
        wait_state = connection.execute(
            "SELECT wait_state FROM printer_pre_lifecycle_discovery_refresh_waits"
        ).fetchone()[0]
    finally:
        connection.close()
    assert wait_state == "SUCCEEDED"


def test_deadline_exhaustion_cancels_wait_without_factory_proof_deadline(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "deadline.sqlite3"
    apply_migrations(db_path)
    started = datetime(2026, 9, 2, 12, 44, 59, tzinfo=timezone.utc)
    owner = PreLifecycleTemporalRefreshOwner(
        db_path,
        campaign_id="campaign-deadline",
        run_id="run-deadline",
        cycle_id="cycle-2",
        supervision_id="supervision-deadline",
        source_governor=True,
        central_scheduler=True,
        acquisition_deadline_at=_iso(started + timedelta(seconds=2400)),
        work_deadline_at=_iso(started + timedelta(seconds=18000)),
        refresh_stage=lambda connection, **kwargs: (_ for _ in ()).throw(
            AssertionError("refresh stage must not run after deadline")
        ),
        acquisition_started_at=_iso(started),
        supervision_probe=lambda: {
            "supervision_active": True,
            "cancellation_requested": False,
        },
        waiter=None,
        clock=lambda: _iso(started + timedelta(seconds=2400)),
        refresh_interval_seconds=600,
    )
    first = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=4,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=9,
        now=_iso(started + timedelta(seconds=10)),
    )
    assert first.status == WAITING_FOR_ELIGIBLE_SUPPLY
    expired = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=4,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=9,
        now=_iso(started + timedelta(seconds=2400)),
    )
    assert expired.status == ACQUISITION_DEADLINE_EXHAUSTED
    assert expired.status != "PROOF_DEADLINE"


def test_abandon_scoped_refresh_waits_terminalizes_waiting_row(tmp_path: Path) -> None:
    db_path = tmp_path / "abandon.sqlite3"
    apply_migrations(db_path)
    started = datetime(2026, 9, 2, 12, 44, 59, tzinfo=timezone.utc)
    owner = PreLifecycleTemporalRefreshOwner(
        db_path,
        campaign_id="campaign-abandon",
        run_id="run-abandon",
        cycle_id="cycle-2",
        supervision_id="supervision-abandon",
        source_governor=True,
        central_scheduler=True,
        acquisition_deadline_at=_iso(started + timedelta(seconds=2400)),
        work_deadline_at=_iso(started + timedelta(seconds=18000)),
        refresh_stage=lambda **kwargs: {},
        acquisition_started_at=_iso(started),
        supervision_probe=lambda: {
            "supervision_active": True,
            "cancellation_requested": False,
        },
        waiter=None,
        refresh_interval_seconds=600,
    )
    waiting = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=4,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=9,
        now=_iso(started + timedelta(seconds=10)),
    )
    assert waiting.status == WAITING_FOR_ELIGIBLE_SUPPLY
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        abandoned = abandon_scoped_refresh_waits(
            connection,
            campaign_id="campaign-abandon",
            run_id="run-abandon",
            cause="PARENT_CAMPAIGN_INTERRUPTED:TEST",
            now=_iso(started + timedelta(seconds=20)),
        )
        connection.commit()
        wait = connection.execute(
            "SELECT wait_state, first_terminal_cause FROM "
            "printer_pre_lifecycle_discovery_refresh_waits"
        ).fetchone()
        job = connection.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id=?",
            (waiting.scheduler_job_id,),
        ).fetchone()
    finally:
        connection.close()
    assert abandoned == (waiting.wait_id,)
    assert wait["wait_state"] == "CANCELLED"
    assert wait["first_terminal_cause"] == "PARENT_CAMPAIGN_INTERRUPTED:TEST"
    assert str(job["status"]) == "CANCELLED"


def test_official_zero_state_detects_waiting_and_claimed(tmp_path: Path) -> None:
    path = tmp_path / "zero-state-waits.sqlite3"
    apply_migrations(path)
    stamp = NOW.isoformat()
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            INSERT INTO printer_pre_lifecycle_discovery_refresh_waits (
                wait_id, campaign_id, run_id, cycle_id, supervision_id,
                scheduler_job_id, refresh_ordinal, wait_state, scheduled_for,
                acquisition_deadline_at, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "wait-waiting",
                "campaign-z",
                "run-z",
                "cycle-2",
                "supervision-z",
                1,
                1,
                "WAITING",
                stamp,
                stamp,
                stamp,
                stamp,
            ),
        )
        connection.commit()
        projection = project_four_token_proof_zero_state(connection)
        assert projection["active_pre_lifecycle_discovery_refresh_waits"] == 1
        connection.execute(
            "UPDATE printer_pre_lifecycle_discovery_refresh_waits "
            "SET wait_state='CLAIMED'"
        )
        connection.commit()
        projection = project_four_token_proof_zero_state(connection)
        assert projection["active_pre_lifecycle_discovery_refresh_waits"] == 1
        connection.execute(
            "UPDATE printer_pre_lifecycle_discovery_refresh_waits "
            "SET wait_state='CANCELLED', first_terminal_cause='TEST', terminal_at=?",
            (stamp,),
        )
        connection.commit()
        projection = project_four_token_proof_zero_state(connection)
        assert projection["active_pre_lifecycle_discovery_refresh_waits"] == 0
    finally:
        connection.close()




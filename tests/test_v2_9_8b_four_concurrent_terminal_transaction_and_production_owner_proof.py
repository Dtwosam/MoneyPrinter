"""Terminal transaction safety + production-owner overlap/close/source proofs."""

from __future__ import annotations

import inspect
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    StageBudget,
    derive_campaign_source_request_key_root,
)
from printer_v1.discovery.pre_lifecycle_refresh_composition import (
    build_pre_lifecycle_refresh_stage,
)
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    ACQUISITION_DEADLINE_EXHAUSTED,
    WAITING_FOR_ELIGIBLE_SUPPLY,
    insert_refresh_wait,
    mark_refresh_wait_claimed,
)
from printer_v1.discovery.pre_lifecycle_refresh_work import insert_refresh_work

from printer_v1.operator_cli.cadence_authority import (
    claim_tracking_authority_for_slot_insert,
)
from printer_v1.operator_cli.close_phases import close_phase_metadata
from printer_v1.operator_cli.campaign_ownership import (
    CampaignOwnershipError,
    bind_window_memory_row_id,
    create_cycle_with_two_slots,
    cycle_scoped_token_slot_id,
    persist_standard_first_hour_handoff_set,
    persist_standard_four_hour_handoff_set,
    transition_state,
)
from printer_v1.operator_cli.four_token_factory_adapter import (
    parent_interrupted_attempt_cause,
    reconcile_four_token_cycle_terminal,
    reconcile_parent_interrupted_open_pre_admission_attempts,
)
from printer_v1.operator_cli.four_token_operational_composition import (
    exact_operational_policy,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    FourTokenAdmissionDisposition,
    FourTokenAdmissionDispositionKind,
    cycle_step_key,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
    MultiCycleCampaignBinding,
    admit_two_token_cycle,
    load_multi_cycle_campaign_snapshot,
    multi_cycle_configuration_contract,
)
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    AdmissionDecision,
    MultiCycleCapacityPolicy,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    _advance_owned_proof_15m_window,
    _execute_close_evidence_phase,
    _execute_snapshot,
    _insert_step_and_job,
    _later_cycle_attempt_is_terminal,
    _plan_opening_jobs,
    _run_four_token_admission_boundary,
    _select_next_pending_step,
    _update_step,
)
from printer_v1.operator_cli.operational_selective_1h import campaign_window_id_for
from printer_v1.operator_cli.pre_admission_attempt_evidence import (
    append_pre_admission_attempt_evidence,
)
from printer_v1.operator_cli.pre_admission_discovery_attempt import (
    PreAdmissionAttemptState,
    create_scheduled_pre_admission_attempt,
    mark_pre_admission_attempt_running,
    pre_admission_attempt_lock_owner,
    terminalize_pre_admission_attempt,
)
from printer_v1.operator_cli.pre_lifecycle_persistent_refresh_owner import (
    PreLifecycleTemporalRefreshOwner,
)
from printer_v1.operator_cli import unified_terminal_closure as terminal_mod
from printer_v1.operator_cli.unified_terminal_closure import (
    _transition,
    reconcile_campaign_terminal,
)
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import (
    claim_due_job,
    complete_job,
    enqueue_job,
    fail_job,
)
from printer_v1.sources.governed_execution import build_fixture_source_adapter
from printer_v1.sources.measured_transport import (
    build_transport_identity,
    measured_payload_fields,
)


NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
PARENT_CAUSE = "LEASE_RENEWAL_SQLITE_LOCKED"
EXPECTED_CAUSE = parent_interrupted_attempt_cause(PARENT_CAUSE)
POLICY = MultiCycleCapacityPolicy(
    configured_through_4h_token_ceiling=4,
    configured_active_cycle_ceiling=2,
    total_cycle_admission_ceiling=2,
    intake_duration_seconds=18_000,
)
BINDING = MultiCycleCampaignBinding(
    campaign_id="campaign-1",
    campaign_run_id="campaign-run-1",
    configuration_id="configuration-1",
    authoritative_factory_run_id="factory-1",
)
HEALTH = MultiCycleAdmissionHealth()
LIFECYCLE = "PUMPSWAP_GRADUATED_CONFIRMED"
MINT = "G9j8WWDeJXZdvwQgP82ooDuHmpc3Gy8NCSins71Lpump"


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _open(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _integrity(connection: sqlite3.Connection) -> None:
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def _insert_token_pair(
    connection: sqlite3.Connection, *, token_id: int, pair_id: int, mint: str | None = None
) -> None:
    connection.execute(
        "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?, 'solana')",
        (token_id, mint or f"mint-{token_id}"),
    )
    connection.execute(
        "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
        "VALUES (?,?,?,?)",
        (pair_id, token_id, f"pool-{token_id}", mint or f"mint-{token_id}"),
    )


def _seed_campaign(path: Path, *, cycle_state: str = "TRACKING") -> Path:
    apply_migrations(path)
    connection = _open(path)
    stamp = _iso(NOW)
    configuration = {
        "token_capacity": 2,
        "ceilings": {"cycle_count": 2},
        "multi_cycle_capacity": multi_cycle_configuration_contract(
            POLICY, intake_started_at=NOW
        ),
    }
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        ("campaign-1", "RUNNING", "OPERATIONAL_PERSISTENT", "db-1", "policy-1", stamp, stamp),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json,created_at) VALUES (?,?,?,?,?,?)",
        (
            "configuration-1",
            "campaign-1",
            "a" * 64,
            json.dumps(configuration, sort_keys=True),
            "{}",
            stamp,
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "factory-1",
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            json.dumps(
                {
                    "four_token_proof": True,
                    "campaign_id": "campaign-1",
                    "campaign_run_id": "campaign-run-1",
                    "configuration_id": "configuration-1",
                },
                sort_keys=True,
            ),
            stamp,
            stamp,
            stamp,
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        ("campaign-run-1", "campaign-1", 1, "RUNNING", "factory-1", stamp, stamp),
    )
    terminal = cycle_state.startswith("TERMINAL_")
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_cycles("
        "cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,first_terminal_cause,"
        "terminal_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "cycle-1",
            "campaign-1",
            "campaign-run-1",
            1,
            cycle_state,
            PARENT_CAUSE if terminal else None,
            stamp if terminal else None,
            stamp,
            stamp,
        ),
    )
    connection.commit()
    connection.close()
    return path


def _insert_cycle1_slot(
    connection: sqlite3.Connection, *, token_state: str
) -> None:
    _insert_token_pair(connection, token_id=11, pair_id=111)
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_token_slots("
        "token_slot_id,campaign_id,run_id,cycle_id,slot_ordinal,token_identity,"
        "token_row_id,mint_identity,pair_identity,pair_row_id,lifecycle_identity,"
        "token_state,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "slot-cycle-1-1",
            "campaign-1",
            "campaign-run-1",
            "cycle-1",
            1,
            "solana-mainnet:mint-11",
            11,
            "mint-11",
            "pool-11",
            111,
            LIFECYCLE,
            token_state,
            _iso(NOW),
            _iso(NOW),
        ),
    )
    connection.commit()


def _insert_refresh(
    connection: sqlite3.Connection,
    *,
    wait_state: str,
    cycle_id: str = "cycle-2",
    campaign_id: str = "campaign-1",
    run_id: str = "campaign-run-1",
    with_work: bool = False,
) -> tuple[str, int]:
    result, job_id = enqueue_job(
        connection,
        job_name=f"PRE_LIFECYCLE_DISCOVERY_REFRESH:{campaign_id}:{run_id}:{cycle_id}:1",
        job_kind=JobKind.DISCOVERY_REFRESH,
        scheduled_for=NOW,
    )
    assert job_id is not None
    wait_id = f"prelifecycle-refresh-wait:{campaign_id}:{run_id}:{cycle_id}:1"
    insert_refresh_wait(
        connection,
        wait_id=wait_id,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        supervision_id="supervision-1",
        scheduler_job_id=int(job_id),
        refresh_ordinal=1,
        scheduled_for=_iso(NOW),
        acquisition_deadline_at=_iso(NOW + timedelta(seconds=2400)),
        now=_iso(NOW),
    )
    if wait_state == "CLAIMED":
        mark_refresh_wait_claimed(connection, wait_id=wait_id, now=_iso(NOW))
        if with_work:
            insert_refresh_work(
                connection,
                refresh_work_id=(
                    f"prelifecycle-refresh-work:{campaign_id}:{run_id}:{cycle_id}:1"
                ),
                wait_id=wait_id,
                campaign_id=campaign_id,
                run_id=run_id,
                cycle_id=cycle_id,
                supervision_id="supervision-1",
                scheduler_job_id=int(job_id),
                refresh_ordinal=1,
                work_deadline_at=_iso(NOW + timedelta(seconds=18000)),
                now=_iso(NOW),
            )
    connection.commit()
    return wait_id, int(job_id)


def _assert_terminal_cleanup(
    path: Path,
    *,
    wait_id: str,
    refresh_job_id: int,
    slot_id: str,
    expect_work: bool,
) -> None:
    connection = _open(path)
    try:
        wait = connection.execute(
            "SELECT wait_state FROM printer_pre_lifecycle_discovery_refresh_waits "
            "WHERE wait_id=?",
            (wait_id,),
        ).fetchone()
        job = connection.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id=?",
            (refresh_job_id,),
        ).fetchone()
        slot = connection.execute(
            "SELECT token_state FROM printer_memory_factory_campaign_token_slots "
            "WHERE token_slot_id=?",
            (slot_id,),
        ).fetchone()
        campaign = connection.execute(
            "SELECT campaign_state FROM printer_memory_factory_campaigns "
            "WHERE campaign_id='campaign-1'"
        ).fetchone()
        cycle = connection.execute(
            "SELECT cycle_state FROM printer_memory_factory_campaign_cycles "
            "WHERE cycle_id='cycle-1'"
        ).fetchone()
        run = connection.execute(
            "SELECT run_state FROM printer_memory_factory_campaign_runs "
            "WHERE run_id='campaign-run-1'"
        ).fetchone()
        factory = connection.execute(
            "SELECT run_status FROM printer_memory_factory_runs WHERE run_id='factory-1'"
        ).fetchone()
        assert wait["wait_state"] in {"CANCELLED", "FAILED", "SUCCEEDED"}
        assert job["status"] == "CANCELLED"
        assert slot["token_state"] in {"MANUAL_REVIEW", "COOLDOWN", "FAILED"}
        assert str(campaign["campaign_state"]).startswith("TERMINAL_")
        assert str(cycle["cycle_state"]).startswith("TERMINAL_")
        assert str(run["run_state"]).startswith("TERMINAL_")
        assert factory["run_status"] in {"SAFE_STOPPED", "COMPLETED"}
        if expect_work:
            work = connection.execute(
                "SELECT work_state FROM printer_pre_lifecycle_discovery_refresh_work "
                "WHERE wait_id=?",
                (wait_id,),
            ).fetchone()
            assert work["work_state"] in {"FAILED", "CANCELLED"}
        active = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_pre_lifecycle_discovery_refresh_waits "
                "WHERE campaign_id='campaign-1' AND run_id='campaign-run-1' "
                "AND wait_state IN ('WAITING','CLAIMED')"
            ).fetchone()[0]
        )
        assert active == 0
        _integrity(connection)
    finally:
        connection.close()


def test_successful_phase_a_preserves_completed_four_hour_slot_evidence(
    tmp_path: Path,
) -> None:
    path = _seed_campaign(tmp_path / "phase-a-success.sqlite3")
    connection = _open(path)
    try:
        for ordinal, token_id in ((1, 11), (2, 12)):
            _insert_token_pair(
                connection,
                token_id=token_id,
                pair_id=100 + token_id,
            )
            connection.execute(
                """
                INSERT INTO printer_memory_factory_campaign_token_slots(
                    token_slot_id,campaign_id,run_id,cycle_id,slot_ordinal,
                    token_identity,token_row_id,mint_identity,pair_identity,
                    pair_row_id,lifecycle_identity,token_state,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    f"slot-cycle-1-{ordinal}",
                    "campaign-1",
                    "campaign-run-1",
                    "cycle-1",
                    ordinal,
                    f"solana-mainnet:mint-{token_id}",
                    token_id,
                    f"mint-{token_id}",
                    f"pool-{token_id}",
                    100 + token_id,
                    LIFECYCLE,
                    "WINDOW_4H_CLOSED",
                    _iso(NOW),
                    _iso(NOW),
                ),
            )
        connection.commit()
        with (
            patch(
                "printer_v1.operator_cli.four_token_factory_adapter."
                "derive_cycle_terminal_accounting_result",
                return_value={
                    "execution_outcome": "TERMINAL_SUCCESS",
                    "primary_fault": None,
                },
            ),
            patch(
                "printer_v1.operator_cli.four_token_factory_adapter."
                "_validate_pre_lifecycle_zero_attempt_provenance_shape",
                return_value=False,
            ),
            patch(
                "printer_v1.operator_cli.four_token_proof_integration."
                "cycle_scoped_factory_step_ids",
                return_value=(),
            ),
        ):
            result = reconcile_four_token_cycle_terminal(
                connection,
                campaign_id="campaign-1",
                campaign_run_id="campaign-run-1",
                factory_run_id="factory-1",
                cycle_id="cycle-1",
                configuration_id="configuration-1",
                now=NOW + timedelta(hours=4),
            )

        assert result["cycle_state"] == "TERMINAL_COMPLETED"
        states = [
            str(row[0])
            for row in connection.execute(
                "SELECT token_state FROM printer_memory_factory_campaign_token_slots "
                "WHERE campaign_id='campaign-1' AND run_id='campaign-run-1' "
                "AND cycle_id='cycle-1' ORDER BY slot_ordinal"
            ).fetchall()
        ]
        assert states == ["WINDOW_4H_CLOSED", "WINDOW_4H_CLOSED"]
    finally:
        connection.close()


def test_pair_ready_cycle2_attempt_survives_temporary_post_discovery_defer(
    tmp_path: Path,
) -> None:
    path = _seed_campaign(tmp_path / "pair-ready-rearm.sqlite3")
    connection = _open(path)
    callback_calls: list[str] = []
    planned: list[tuple[str, int]] = []
    materialized: list[str] = []

    def callback(**kwargs):
        callback_calls.append(str(kwargs["cycle_id"]))
        return SimpleNamespace(
            attempt_id="pre-admission:campaign-1:campaign-run-1:factory-1:c0002",
            state="PAIR_READY",
            first_terminal_cause="",
        )

    lifecycle_first = FourTokenAdmissionDisposition(
        FourTokenAdmissionDispositionKind.LIFECYCLE_WORK,
        "DUE_LIFECYCLE_WORK",
        NOW,
        False,
    )
    admission_ready = FourTokenAdmissionDisposition(
        FourTokenAdmissionDispositionKind.CYCLE_ADMISSION,
        "ADMISSION_READY",
        NOW,
        True,
    )
    first_evaluations = iter((admission_ready, lifecycle_first))

    first = _run_four_token_admission_boundary(
        connection=connection,
        controller=SimpleNamespace(policy=POLICY),
        binding=BINDING,
        first_cycle_id="cycle-1",
        now=NOW,
        next_due_work_at=NOW,
        proof_deadline=NOW + timedelta(hours=4),
        project_health=lambda: SimpleNamespace(health=HEALTH),
        evaluate=lambda projection: next(first_evaluations),
        later_cycle_callback=callback,
        admit=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("PAIR_READY must defer, not admit, while lifecycle wins")
        ),
        materialize=lambda **kwargs: None,
        plan_opening=lambda **kwargs: None,
    )

    assert first.admitted is False
    assert first.attempt_state == "PAIR_READY"
    assert first.disposition.kind is FourTokenAdmissionDispositionKind.LIFECYCLE_WORK
    assert not _later_cycle_attempt_is_terminal(first.attempt_state)

    second_evaluations = iter((admission_ready, admission_ready))
    with patch(
        "printer_v1.operator_cli.cadence_authority."
        "require_cycle_slot_tracking_authorities",
        return_value=None,
    ):
        second = _run_four_token_admission_boundary(
            connection=connection,
            controller=SimpleNamespace(policy=POLICY),
            binding=BINDING,
            first_cycle_id="cycle-1",
            now=NOW + timedelta(seconds=1),
            next_due_work_at=NOW + timedelta(minutes=1),
            proof_deadline=NOW + timedelta(hours=4),
            project_health=lambda: SimpleNamespace(health=HEALTH),
            evaluate=lambda projection: next(second_evaluations),
            later_cycle_callback=callback,
            admit=lambda **kwargs: SimpleNamespace(
                mutation_performed=True,
                cycle_id="cycle-1-2",
            ),
            materialize=lambda **kwargs: materialized.append(str(kwargs["attempt_id"])),
            plan_opening=lambda **kwargs: planned.append(
                (str(kwargs["cycle_id"]), int(kwargs["cycle_ordinal"]))
            ),
        )

    assert second.admitted is True
    assert second.attempt_state == "CONSUMED"
    assert second.cycle_id == "cycle-1-2"
    assert callback_calls == ["cycle-1-2", "cycle-1-2"]
    assert materialized == [
        "pre-admission:campaign-1:campaign-run-1:factory-1:c0002"
    ]
    assert planned == [("cycle-1-2", 2)]
    connection.close()


def test_pair_ready_admission_does_not_require_future_discovery_capacity(
    tmp_path: Path,
) -> None:
    path = _seed_campaign(tmp_path / "pair-ready-discovery-budget.sqlite3")
    connection = _open(path)
    healthy = MultiCycleAdmissionHealth()
    post_discovery = MultiCycleAdmissionHealth(
        provider_budgets_available=False,
        discovery_capacity_available=False,
    )
    projections = iter(
        (
            SimpleNamespace(health=healthy),
            SimpleNamespace(health=post_discovery),
        )
    )
    admitted_health: list[MultiCycleAdmissionHealth] = []

    def evaluate(projection):
        health = projection.health
        if not health.provider_budgets_available:
            return FourTokenAdmissionDisposition(
                FourTokenAdmissionDispositionKind.REARM,
                "provider_budget_unavailable",
                NOW + timedelta(minutes=1),
                False,
            )
        if not health.discovery_capacity_available:
            return FourTokenAdmissionDisposition(
                FourTokenAdmissionDispositionKind.REARM,
                "discovery_capacity_unavailable",
                NOW + timedelta(minutes=1),
                False,
            )
        return FourTokenAdmissionDisposition(
            FourTokenAdmissionDispositionKind.CYCLE_ADMISSION,
            "ADMISSION_READY",
            NOW,
            True,
        )

    with patch(
        "printer_v1.operator_cli.cadence_authority."
        "require_cycle_slot_tracking_authorities",
        return_value=None,
    ):
        result = _run_four_token_admission_boundary(
            connection=connection,
            controller=SimpleNamespace(policy=POLICY),
            binding=BINDING,
            first_cycle_id="cycle-1",
            now=NOW,
            next_due_work_at=NOW + timedelta(minutes=1),
            proof_deadline=NOW + timedelta(hours=4),
            project_health=lambda: next(projections),
            evaluate=evaluate,
            later_cycle_callback=lambda **kwargs: SimpleNamespace(
                attempt_id=(
                    "pre-admission:campaign-1:campaign-run-1:factory-1:c0002"
                ),
                state="PAIR_READY",
                first_terminal_cause="",
            ),
            admit=lambda **kwargs: (
                admitted_health.append(kwargs["health"])
                or SimpleNamespace(
                    mutation_performed=True,
                    cycle_id="cycle-1-2",
                )
            ),
            materialize=lambda **kwargs: None,
            plan_opening=lambda **kwargs: None,
        )

    assert result.admitted is True
    assert result.cycle_id == "cycle-1-2"
    assert len(admitted_health) == 1
    assert admitted_health[0].provider_budgets_available is True
    assert admitted_health[0].discovery_capacity_available is True
    assert admitted_health[0].source_budget_available is True
    assert admitted_health[0].scheduler_budget_available is True
    assert admitted_health[0].close_reserve_available is True
    connection.close()


def test_existing_pair_ready_reenters_before_spent_discovery_gates(
    tmp_path: Path,
) -> None:
    path = _seed_campaign(tmp_path / "pair-ready-next-wake.sqlite3")
    connection = _open(path)
    spent_discovery = MultiCycleAdmissionHealth(
        provider_budgets_available=False,
        discovery_capacity_available=False,
    )
    projections = iter(
        (
            SimpleNamespace(health=spent_discovery),
            SimpleNamespace(health=spent_discovery),
        )
    )
    callback_calls: list[str] = []

    def evaluate(projection):
        health = projection.health
        if not (
            health.provider_budgets_available
            and health.discovery_capacity_available
        ):
            return FourTokenAdmissionDisposition(
                FourTokenAdmissionDispositionKind.REARM,
                "future_discovery_capacity_spent",
                NOW + timedelta(minutes=1),
                False,
            )
        return FourTokenAdmissionDisposition(
            FourTokenAdmissionDispositionKind.CYCLE_ADMISSION,
            "ADMISSION_READY",
            NOW,
            True,
        )

    with (
        patch(
            "printer_v1.operator_cli.one_command_15m_factory."
            "_existing_later_cycle_pair_ready_attempt",
            return_value=(
                "pre-admission:campaign-1:campaign-run-1:factory-1:c0002"
            ),
        ),
        patch(
            "printer_v1.operator_cli.cadence_authority."
            "require_cycle_slot_tracking_authorities",
            return_value=None,
        ),
    ):
        result = _run_four_token_admission_boundary(
            connection=connection,
            controller=SimpleNamespace(policy=POLICY),
            binding=BINDING,
            first_cycle_id="cycle-1",
            now=NOW,
            next_due_work_at=NOW + timedelta(minutes=1),
            proof_deadline=NOW + timedelta(hours=4),
            project_health=lambda: next(projections),
            evaluate=evaluate,
            later_cycle_callback=lambda **kwargs: (
                callback_calls.append(str(kwargs["cycle_id"]))
                or SimpleNamespace(
                    attempt_id=(
                        "pre-admission:campaign-1:campaign-run-1:factory-1:c0002"
                    ),
                    state="PAIR_READY",
                    first_terminal_cause="",
                )
            ),
            admit=lambda **kwargs: SimpleNamespace(
                mutation_performed=True,
                cycle_id="cycle-1-2",
            ),
            materialize=lambda **kwargs: None,
            plan_opening=lambda **kwargs: None,
        )

    assert result.admitted is True
    assert result.cycle_id == "cycle-1-2"
    assert callback_calls == ["cycle-1-2"]
    connection.close()


def test_existing_pair_ready_skips_future_acquisition_quantum_conflict(
    tmp_path: Path,
) -> None:
    path = _seed_campaign(tmp_path / "pair-ready-no-acquisition-deferral.sqlite3")
    connection = _open(path)
    callback_calls: list[str] = []
    admission_ready = FourTokenAdmissionDisposition(
        FourTokenAdmissionDispositionKind.CYCLE_ADMISSION,
        "ADMISSION_READY",
        NOW,
        True,
    )
    with (
        patch(
            "printer_v1.operator_cli.one_command_15m_factory."
            "_existing_later_cycle_pair_ready_attempt",
            return_value=(
                "pre-admission:campaign-1:campaign-run-1:factory-1:c0002"
            ),
        ),
        patch(
            "printer_v1.operator_cli.cadence_authority."
            "require_cycle_slot_tracking_authorities",
            return_value=None,
        ),
    ):
        result = _run_four_token_admission_boundary(
            connection=connection,
            controller=SimpleNamespace(policy=POLICY),
            binding=BINDING,
            first_cycle_id="cycle-1",
            now=NOW,
            # Inside the ordinary acquisition quantum, but not yet due.
            next_due_work_at=NOW + timedelta(seconds=30),
            proof_deadline=NOW + timedelta(hours=4),
            project_health=lambda: SimpleNamespace(health=HEALTH),
            evaluate=lambda projection: admission_ready,
            later_cycle_callback=lambda **kwargs: (
                callback_calls.append(str(kwargs["cycle_id"]))
                or SimpleNamespace(
                    attempt_id=(
                        "pre-admission:campaign-1:campaign-run-1:factory-1:c0002"
                    ),
                    state="PAIR_READY",
                    first_terminal_cause="",
                )
            ),
            admit=lambda **kwargs: SimpleNamespace(
                mutation_performed=True,
                cycle_id="cycle-1-2",
            ),
            materialize=lambda **kwargs: None,
            plan_opening=lambda **kwargs: None,
            acquisition_quantum_worst_case_seconds=60.0,
        )

    assert result.admitted is True
    assert result.cycle_id == "cycle-1-2"
    assert callback_calls == ["cycle-1-2"]
    connection.close()


def test_pair_ready_survives_nonmutating_atomic_admission_recheck(
    tmp_path: Path,
) -> None:
    path = _seed_campaign(tmp_path / "pair-ready-nonmutating-admit.sqlite3")
    connection = _open(path)
    admission_ready = FourTokenAdmissionDisposition(
        FourTokenAdmissionDispositionKind.CYCLE_ADMISSION,
        "ADMISSION_READY",
        NOW,
        True,
    )
    callback_calls: list[str] = []
    admit_calls: list[int] = []

    def callback(**kwargs):
        callback_calls.append(str(kwargs["cycle_id"]))
        return SimpleNamespace(
            attempt_id="pre-admission:campaign-1:campaign-run-1:factory-1:c0002",
            state="PAIR_READY",
            first_terminal_cause="",
        )

    def first_admit(**kwargs):
        admit_calls.append(1)
        return SimpleNamespace(mutation_performed=False, cycle_id=None)

    first = _run_four_token_admission_boundary(
        connection=connection,
        controller=SimpleNamespace(policy=POLICY),
        binding=BINDING,
        first_cycle_id="cycle-1",
        now=NOW,
        next_due_work_at=NOW + timedelta(minutes=2),
        proof_deadline=NOW + timedelta(hours=4),
        project_health=lambda: SimpleNamespace(health=HEALTH),
        evaluate=lambda projection: admission_ready,
        later_cycle_callback=callback,
        admit=first_admit,
        materialize=lambda **kwargs: None,
        plan_opening=lambda **kwargs: None,
        acquisition_quantum_worst_case_seconds=30.0,
    )

    assert first.admitted is False
    assert first.attempt_state == "PAIR_READY"
    assert not _later_cycle_attempt_is_terminal(first.attempt_state)

    with patch(
        "printer_v1.operator_cli.cadence_authority."
        "require_cycle_slot_tracking_authorities",
        return_value=None,
    ):
        second = _run_four_token_admission_boundary(
            connection=connection,
            controller=SimpleNamespace(policy=POLICY),
            binding=BINDING,
            first_cycle_id="cycle-1",
            now=NOW + timedelta(seconds=1),
            next_due_work_at=NOW + timedelta(minutes=2),
            proof_deadline=NOW + timedelta(hours=4),
            project_health=lambda: SimpleNamespace(health=HEALTH),
            evaluate=lambda projection: admission_ready,
            later_cycle_callback=callback,
            admit=lambda **kwargs: (
                admit_calls.append(2)
                or SimpleNamespace(
                    mutation_performed=True,
                    cycle_id="cycle-1-2",
                )
            ),
            materialize=lambda **kwargs: None,
            plan_opening=lambda **kwargs: None,
            acquisition_quantum_worst_case_seconds=30.0,
        )

    assert second.admitted is True
    assert second.cycle_id == "cycle-1-2"
    assert callback_calls == ["cycle-1-2", "cycle-1-2"]
    assert admit_calls == [1, 2]
    connection.close()


def test_transition_helper_does_not_speculate_candidate_states() -> None:
    source = inspect.getsource(_transition)
    assert "for expected_state in" not in source
    assert "candidate_states" not in source


def test_campaign_terminal_1h_slot_retains_cycle2_wait_after_reopen(tmp_path: Path) -> None:
    path = _seed_campaign(tmp_path / "term-1h.sqlite3")
    connection = _open(path)
    _insert_cycle1_slot(connection, token_state="WINDOW_1H_CONTINUING")
    wait_id, refresh_job = _insert_refresh(connection, wait_state="WAITING")
    connection.close()
    report = reconcile_campaign_terminal(
        path,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        terminal_cause=PARENT_CAUSE,
        run_status="SAFE_STOPPED",
        factory_run_id="factory-1",
        lifecycle_started=True,
        now=_iso(NOW),
    )
    assert report.get("clean_terminal") is True
    _assert_terminal_cleanup(
        path,
        wait_id=wait_id,
        refresh_job_id=refresh_job,
        slot_id="slot-cycle-1-1",
        expect_work=False,
    )


def test_campaign_terminal_4h_slot_retains_cycle2_wait_after_reopen(tmp_path: Path) -> None:
    path = _seed_campaign(tmp_path / "term-4h.sqlite3")
    connection = _open(path)
    _insert_cycle1_slot(connection, token_state="WINDOW_4H_CONTINUING")
    wait_id, refresh_job = _insert_refresh(connection, wait_state="WAITING")
    connection.close()
    report = reconcile_campaign_terminal(
        path,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        terminal_cause=PARENT_CAUSE,
        run_status="SAFE_STOPPED",
        factory_run_id="factory-1",
        lifecycle_started=True,
        now=_iso(NOW),
    )
    assert report.get("clean_terminal") is True
    _assert_terminal_cleanup(
        path,
        wait_id=wait_id,
        refresh_job_id=refresh_job,
        slot_id="slot-cycle-1-1",
        expect_work=False,
    )


def test_campaign_terminal_claimed_wait_not_rolled_back(tmp_path: Path) -> None:
    path = _seed_campaign(tmp_path / "term-claimed.sqlite3")
    connection = _open(path)
    _insert_cycle1_slot(connection, token_state="WINDOW_1H_CONTINUING")
    wait_id, refresh_job = _insert_refresh(
        connection, wait_state="CLAIMED", with_work=True
    )
    other_wait, other_job = _insert_refresh(
        connection,
        wait_state="WAITING",
        cycle_id="other-cycle",
        campaign_id="other-campaign",
        run_id="other-run",
    )
    connection.close()
    reconcile_campaign_terminal(
        path,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        terminal_cause=PARENT_CAUSE,
        run_status="SAFE_STOPPED",
        factory_run_id="factory-1",
        lifecycle_started=True,
        now=_iso(NOW),
    )
    _assert_terminal_cleanup(
        path,
        wait_id=wait_id,
        refresh_job_id=refresh_job,
        slot_id="slot-cycle-1-1",
        expect_work=True,
    )
    connection = _open(path)
    try:
        other = connection.execute(
            "SELECT wait_state FROM printer_pre_lifecycle_discovery_refresh_waits "
            "WHERE wait_id=?",
            (other_wait,),
        ).fetchone()
        other_status = connection.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id=?",
            (other_job,),
        ).fetchone()
        assert other["wait_state"] == "WAITING"
        assert other_status["status"] == "PENDING"
    finally:
        connection.close()


def test_forced_later_transition_failure_does_not_report_clean_with_live_wait(
    tmp_path: Path,
) -> None:
    path = _seed_campaign(tmp_path / "term-fail.sqlite3")
    connection = _open(path)
    _insert_cycle1_slot(connection, token_state="WINDOW_1H_CONTINUING")
    wait_id, _refresh_job = _insert_refresh(connection, wait_state="WAITING")
    connection.close()
    real = terminal_mod.transition_state

    def boom(connection, *, record_kind, identity, expected_state, new_state, **kwargs):
        if record_kind == "campaign":
            raise CampaignOwnershipError("injected later terminal failure")
        return real(
            connection,
            record_kind=record_kind,
            identity=identity,
            expected_state=expected_state,
            new_state=new_state,
            **kwargs,
        )

    with patch.object(terminal_mod, "transition_state", boom):
        with pytest.raises(CampaignOwnershipError, match="injected later terminal failure"):
            reconcile_campaign_terminal(
                path,
                campaign_id="campaign-1",
                run_id="campaign-run-1",
                cycle_id="cycle-1",
                terminal_cause=PARENT_CAUSE,
                run_status="SAFE_STOPPED",
                factory_run_id="factory-1",
                lifecycle_started=True,
                now=_iso(NOW),
            )
    connection = _open(path)
    try:
        wait = connection.execute(
            "SELECT wait_state FROM printer_pre_lifecycle_discovery_refresh_waits "
            "WHERE wait_id=?",
            (wait_id,),
        ).fetchone()
        campaign = connection.execute(
            "SELECT campaign_state FROM printer_memory_factory_campaigns "
            "WHERE campaign_id='campaign-1'"
        ).fetchone()
        assert wait["wait_state"] == "CANCELLED"
        assert campaign["campaign_state"] == "RUNNING"
        _integrity(connection)
    finally:
        connection.close()


def _dex_adapter(mint: str, pair: str):
    def adapter_factory(*, token_mint, timeout_seconds):
        del timeout_seconds
        assert token_mint == mint
        return build_fixture_source_adapter(
            "dexscreener",
            fixture_payload={
                "pairs": [
                    {
                        "chain": "solana",
                        "token_mint": mint,
                        "pair_address": pair,
                        "price_usd": 1.25,
                        "liquidity_usd": 15000.0,
                        "volume_5m": 500.0,
                        "volume_1h": 2000.0,
                        "volume_24h": 10000.0,
                        "txns_5m": 10,
                        "txns_1h": 50,
                        "txns_24h": 500,
                        "price_change_5m": 1.0,
                        "price_change_1h": 2.0,
                        "price_change_24h": 3.0,
                    }
                ]
            },
        )

    return adapter_factory


def _window_id(cycle_id: str, slot_id: str, kind: str) -> str:
    return campaign_window_id_for(
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id=cycle_id,
        token_slot_id=slot_id,
        window_kind=kind,
        period_key="factory-root",
    )


def _slot_payloads(
    cycle_id: str, token_ids: tuple[int, int], queue_ids: tuple[int, int]
) -> tuple[dict[str, object], dict[str, object]]:
    return tuple(
        {
            "token_slot_id": cycle_scoped_token_slot_id(
                cycle_id=cycle_id, slot_ordinal=slot
            ),
            "slot_ordinal": slot,
            "token_identity": f"solana-mainnet:mint-{token_id}",
            "token_row_id": token_id,
            "mint_identity": f"mint-{token_id}",
            "pair_identity": f"pool-{token_id}",
            "pair_row_id": 100 + token_id,
            "lifecycle_identity": LIFECYCLE,
            "tracking_queue_id": queue_id,
            "replacement_predecessor_slot_id": None,
        }
        for slot, token_id, queue_id in zip((1, 2), token_ids, queue_ids)
    )


def _promote_window(
    connection: sqlite3.Connection, window_id: str, *, now: str, cause: str
) -> None:
    current = str(
        connection.execute(
            "SELECT window_state FROM printer_memory_factory_campaign_windows "
            "WHERE window_id=?",
            (window_id,),
        ).fetchone()[0]
    )
    sequence = ("PLANNED", "COLLECTING", "CLOSE_PENDING", "AUDITING", "CLEAN_PROMOTED")
    start = sequence.index(current)
    for nxt in sequence[start + 1 :]:
        kwargs = {
            "record_kind": "window",
            "identity": window_id,
            "expected_state": current,
            "new_state": nxt,
            "now": now,
        }
        if nxt == "CLEAN_PROMOTED":
            kwargs["terminal_cause"] = cause
        transition_state(connection, **kwargs)
        current = nxt


def _insert_closed_memory(
    connection: sqlite3.Connection,
    *,
    memory_id: int,
    token_id: int,
    pair_id: int,
    kind: str,
    opened: datetime,
    closed: datetime,
    start_snap: int,
    end_snap: int,
) -> None:
    connection.execute(
        """INSERT INTO printer_memory_windows(
            id,token_id,pair_id,window_kind,opened_at,closed_at,window_start_at,
            window_end_at,snapshot_start_id,snapshot_end_id,memory_status,
            data_quality_label,window_status,memory_quality_label,outcome_label,
            do_not_train
        ) VALUES (?,?,?,?,?,?,?,?,?,?,'CLEAN_MEMORY','CLEAN_DATA','WINDOW_CLOSED',
            'CLEAN_MEMORY','CONSOLIDATION',0)""",
        (
            memory_id,
            token_id,
            pair_id,
            kind,
            _iso(opened),
            _iso(closed),
            _iso(opened),
            _iso(closed),
            start_snap,
            end_snap,
        ),
    )
    if kind == "WINDOW_1H":
        connection.execute(
            """INSERT INTO printer_episodes(
                memory_window_id,token_id,pair_id,episode_kind,episode_status,
                memory_status,data_quality_label,do_not_train,window_kind,
                memory_quality_label,episode_outcome_label
            ) VALUES (?,?,?,'WINDOW_1H_CLEAN_MEMORY','COMPLETE','CLEAN_MEMORY',
                'CLEAN_DATA',0,'WINDOW_1H','CLEAN_MEMORY','CONSOLIDATION')""",
            (memory_id, token_id, pair_id),
        )


def test_production_owner_four_token_overlap_15m_1h_4h(tmp_path: Path) -> None:
    path = tmp_path / "overlap-prod.sqlite3"
    apply_migrations(path)
    connection = _open(path)
    stamp = _iso(NOW)
    configuration = {
        "token_capacity": 2,
        "ceilings": {"cycle_count": 2},
        "multi_cycle_capacity": multi_cycle_configuration_contract(
            POLICY, intake_started_at=NOW
        ),
    }
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        ("campaign-1", "RUNNING", "OPERATIONAL_PERSISTENT", "db-1", "policy-1", stamp, stamp),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json,created_at) VALUES (?,?,?,?,?,?)",
        (
            "configuration-1",
            "campaign-1",
            "a" * 64,
            json.dumps(configuration, sort_keys=True),
            "{}",
            stamp,
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "factory-1",
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            json.dumps(
                {
                    "four_token_proof": True,
                    "campaign_id": "campaign-1",
                    "campaign_run_id": "campaign-run-1",
                    "configuration_id": "configuration-1",
                },
                sort_keys=True,
            ),
            stamp,
            stamp,
            stamp,
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        ("campaign-run-1", "campaign-1", 1, "RUNNING", "factory-1", stamp, stamp),
    )
    queues: list[int] = []
    for token_id in (1, 2, 3, 4):
        _insert_token_pair(connection, token_id=token_id, pair_id=100 + token_id)
        queues.append(
            claim_tracking_authority_for_slot_insert(
                connection,
                token_row_id=token_id,
                pair_row_id=100 + token_id,
                tracking_lane="TRACK_NORMAL",
                now=NOW,
            )
        )
    connection.commit()
    create_cycle_with_two_slots(
        connection,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        cycle_ordinal=1,
        slots=_slot_payloads("cycle-1", (1, 2), (queues[0], queues[1])),
        now=_iso(NOW),
        commit_transaction=True,
    )
    _plan_opening_jobs(
        connection,
        "factory-1",
        [
            {
                "token_id": 1,
                "pair_id": 101,
                "token_mint": "mint-1",
                "pair_address": "pool-1",
                "tracking_lane": "TRACK_NORMAL",
            },
            {
                "token_id": 2,
                "pair_id": 102,
                "token_mint": "mint-2",
                "pair_address": "pool-2",
                "tracking_lane": "TRACK_NORMAL",
            },
        ],
        NOW,
        cycle_ordinal=1,
        four_token_proof=True,
    )
    connection.commit()
    t2 = NOW + timedelta(seconds=300)
    admitted = admit_two_token_cycle(
        connection,
        binding=BINDING,
        policy=POLICY,
        now=t2,
        slots=_slot_payloads("unused", (3, 4), (queues[2], queues[3])),
        health=HEALTH,
    )
    assert admitted.mutation_performed is True
    assert admitted.cycle_id == "cycle-1-2"
    _plan_opening_jobs(
        connection,
        "factory-1",
        [
            {
                "token_id": 3,
                "pair_id": 103,
                "token_mint": "mint-3",
                "pair_address": "pool-3",
                "tracking_lane": "TRACK_NORMAL",
            },
            {
                "token_id": 4,
                "pair_id": 104,
                "token_mint": "mint-4",
                "pair_address": "pool-4",
                "tracking_lane": "TRACK_NORMAL",
            },
        ],
        t2,
        cycle_ordinal=2,
        four_token_proof=True,
    )
    connection.commit()
    snapshot_ids: dict[int, int] = {}
    for step in connection.execute(
        "SELECT * FROM printer_memory_factory_run_steps "
        "WHERE step_kind='SNAPSHOT' AND step_status='PENDING' ORDER BY id"
    ):
        claimed = claim_due_job(
            connection,
            job_id=int(step["scheduler_job_id"]),
            lock_owner="v2_4:factory-1",
            now=t2 + timedelta(minutes=1),
        )
        assert claimed is LockResult.ACQUIRED
        executed = _execute_snapshot(
            connection,
            step,
            adapter_factory=_dex_adapter(str(step["token_mint"]), str(step["pair_address"])),
            timeout_seconds=1.0,
        )
        assert executed.get("snapshot_id") is not None
        snapshot_ids[int(step["token_id"])] = int(executed["snapshot_id"])
        _advance_owned_proof_15m_window(
            connection,
            scheduler_job_id=int(step["scheduler_job_id"]),
            step_kind="SNAPSHOT",
        )
        _update_step(
            connection,
            int(step["id"]),
            "SUCCEEDED",
            {"snapshot_id": int(executed["snapshot_id"])},
        )
        complete_job(
            connection,
            job_id=int(step["scheduler_job_id"]),
            now=NOW + timedelta(minutes=1),
        )
    connection.commit()
    assert len(snapshot_ids) == 4
    snap = load_multi_cycle_campaign_snapshot(
        connection, binding=BINDING, policy=POLICY, now=t2 + timedelta(minutes=1)
    )
    assert snap.session.active_cycles == 2
    assert snap.session.active_through_4h_tokens == 4

    t15 = NOW + timedelta(minutes=15)
    for cycle_id, token_ids, cycle_ordinal in (
        ("cycle-1", (1, 2), 1),
        ("cycle-1-2", (3, 4), 2),
    ):
        candidates = []
        for slot_ordinal, token_id in zip((1, 2), token_ids):
            slot_id = cycle_scoped_token_slot_id(
                cycle_id=cycle_id, slot_ordinal=slot_ordinal
            )
            window_id = _window_id(cycle_id, slot_id, "WINDOW_15M")
            memory_id = 600 + token_id
            _insert_closed_memory(
                connection,
                memory_id=memory_id,
                token_id=token_id,
                pair_id=100 + token_id,
                kind="WINDOW_15M",
                opened=NOW,
                closed=t15,
                start_snap=snapshot_ids[token_id],
                end_snap=snapshot_ids[token_id],
            )
            bind_window_memory_row_id(
                connection, window_id=window_id, memory_window_row_id=memory_id
            )
            _promote_window(
                connection, window_id, now=_iso(t15), cause="CLEAN_15M"
            )
            candidates.append(
                {
                    "object_id": f"cont4a:campaign-1:campaign-run-1:{cycle_id}:{slot_id}:{memory_id}",
                    "continue_ok": True,
                    "payload": {
                        "verdict": "CONTINUE_TO_WINDOW_1H",
                        "campaign_window_1h_id": _window_id(
                            cycle_id, slot_id, "WINDOW_1H"
                        ),
                    },
                    "info": {
                        "token_slot_id": slot_id,
                        "token_row_id": token_id,
                        "pair_row_id": 100 + token_id,
                        "mint_identity": f"mint-{token_id}",
                        "pair_identity": f"pool-{token_id}",
                        "lifecycle_identity": LIFECYCLE,
                        "campaign_window_15m_id": window_id,
                        "memory_window_15m_id": memory_id,
                    },
                }
            )
        persist_standard_first_hour_handoff_set(
            connection,
            campaign_id="campaign-1",
            configuration_id="configuration-1",
            run_id="campaign-run-1",
            cycle_id=cycle_id,
            object_kind="CONTINUATION_4A",
            candidates=candidates,
            now=_iso(t15),
        )
        for slot_ordinal, token_id in zip((1, 2), token_ids):
            key = cycle_step_key(
                slot_ordinal=slot_ordinal,
                cycle_ordinal=cycle_ordinal,
                suffix="continuation_snapshot_00",
            )
            _insert_step_and_job(
                connection,
                run_id="factory-1",
                target={
                    "token_id": token_id,
                    "pair_id": 100 + token_id,
                    "token_mint": f"mint-{token_id}",
                    "pair_address": f"pool-{token_id}",
                    "tracking_lane": "TRACK_NORMAL",
                },
                step_key=key,
                step_kind="CONTINUATION_SNAPSHOT",
                scheduled_for=t15,
            )
    connection.commit()
    states = {
        str(row["token_state"])
        for row in connection.execute(
            "SELECT token_state FROM printer_memory_factory_campaign_token_slots "
            "WHERE campaign_id='campaign-1'"
        )
    }
    assert states == {"WINDOW_1H_CONTINUING"}
    continuation_count = 0
    for step in connection.execute(
        "SELECT * FROM printer_memory_factory_run_steps "
        "WHERE step_kind='CONTINUATION_SNAPSHOT' AND step_status='PENDING' ORDER BY id"
    ):
        claimed = claim_due_job(
            connection,
            job_id=int(step["scheduler_job_id"]),
            lock_owner="v2_4:factory-1",
            now=t15 + timedelta(minutes=1),
        )
        assert claimed is LockResult.ACQUIRED
        executed = _execute_snapshot(
            connection,
            step,
            adapter_factory=_dex_adapter(str(step["token_mint"]), str(step["pair_address"])),
            timeout_seconds=1.0,
        )
        assert executed.get("snapshot_id") is not None
        snapshot_ids[int(step["token_id"])] = int(executed["snapshot_id"])
        _update_step(
            connection,
            int(step["id"]),
            "SUCCEEDED",
            {"snapshot_id": int(executed["snapshot_id"])},
        )
        complete_job(
            connection,
            job_id=int(step["scheduler_job_id"]),
            now=t15 + timedelta(minutes=1),
        )
        continuation_count += 1
    assert continuation_count == 4

    t1h = NOW + timedelta(hours=1)
    for cycle_id, token_ids, cycle_ordinal in (
        ("cycle-1", (1, 2), 1),
        ("cycle-1-2", (3, 4), 2),
    ):
        candidates = []
        for slot_ordinal, token_id in zip((1, 2), token_ids):
            slot_id = cycle_scoped_token_slot_id(
                cycle_id=cycle_id, slot_ordinal=slot_ordinal
            )
            window_1h = _window_id(cycle_id, slot_id, "WINDOW_1H")
            memory_id = 1300 + token_id
            _insert_closed_memory(
                connection,
                memory_id=memory_id,
                token_id=token_id,
                pair_id=100 + token_id,
                kind="WINDOW_1H",
                opened=t15,
                closed=t1h,
                start_snap=snapshot_ids[token_id],
                end_snap=snapshot_ids[token_id],
            )
            bind_window_memory_row_id(
                connection, window_id=window_1h, memory_window_row_id=memory_id
            )
            _promote_window(
                connection, window_1h, now=_iso(t1h), cause="CLEAN_1H"
            )
            transition_state(
                connection,
                record_kind="token_slot",
                identity=slot_id,
                expected_state="WINDOW_1H_CONTINUING",
                new_state="WINDOW_1H_CLOSED",
                now=_iso(t1h),
            )
            candidates.append(
                {
                    "token_slot_id": slot_id,
                    "token_row_id": token_id,
                    "pair_row_id": 100 + token_id,
                    "mint_identity": f"mint-{token_id}",
                    "pair_identity": f"pool-{token_id}",
                    "lifecycle_identity": LIFECYCLE,
                    "campaign_window_1h_id": window_1h,
                    "campaign_window_4h_id": _window_id(cycle_id, slot_id, "WINDOW_4H"),
                    "memory_window_1h_id": memory_id,
                    "tracking_lane": "TRACK_NORMAL",
                }
            )
        persist_standard_four_hour_handoff_set(
            connection,
            campaign_id="campaign-1",
            run_id="campaign-run-1",
            cycle_id=cycle_id,
            candidates=candidates,
            now=_iso(t1h),
        )
        for slot_ordinal, token_id in zip((1, 2), token_ids):
            _insert_step_and_job(
                connection,
                run_id="factory-1",
                target={
                    "token_id": token_id,
                    "pair_id": 100 + token_id,
                    "token_mint": f"mint-{token_id}",
                    "pair_address": f"pool-{token_id}",
                    "tracking_lane": "TRACK_NORMAL",
                },
                step_key=cycle_step_key(
                    slot_ordinal=slot_ordinal,
                    cycle_ordinal=cycle_ordinal,
                    suffix="long_continuation_snapshot_00",
                ),
                step_kind="LONG_CONTINUATION_SNAPSHOT",
                scheduled_for=t1h,
            )
    connection.commit()
    states = {
        str(row["token_state"])
        for row in connection.execute(
            "SELECT token_state FROM printer_memory_factory_campaign_token_slots "
            "WHERE campaign_id='campaign-1'"
        )
    }
    assert states == {"WINDOW_4H_CONTINUING"}
    long_count = 0
    for step in connection.execute(
        "SELECT * FROM printer_memory_factory_run_steps "
        "WHERE step_kind='LONG_CONTINUATION_SNAPSHOT' AND step_status='PENDING' "
        "ORDER BY id"
    ):
        claimed = claim_due_job(
            connection,
            job_id=int(step["scheduler_job_id"]),
            lock_owner="v2_4:factory-1",
            now=t1h + timedelta(minutes=1),
        )
        assert claimed is LockResult.ACQUIRED
        executed = _execute_snapshot(
            connection,
            step,
            adapter_factory=_dex_adapter(str(step["token_mint"]), str(step["pair_address"])),
            timeout_seconds=1.0,
        )
        assert executed.get("snapshot_id") is not None
        _update_step(
            connection,
            int(step["id"]),
            "SUCCEEDED",
            {"snapshot_id": int(executed["snapshot_id"])},
        )
        complete_job(
            connection,
            job_id=int(step["scheduler_job_id"]),
            now=t1h + timedelta(minutes=1),
        )
        long_count += 1
    assert long_count == 4
    kinds = {
        str(row["window_kind"])
        for row in connection.execute(
            "SELECT window_kind FROM printer_memory_factory_campaign_windows "
            "WHERE campaign_id='campaign-1'"
        )
    }
    assert kinds == {"WINDOW_15M", "WINDOW_1H", "WINDOW_4H"}
    step_keys = [
        str(row["step_key"])
        for row in connection.execute(
            "SELECT step_key FROM printer_memory_factory_run_steps"
        )
    ]
    assert len(step_keys) == len(set(step_keys))
    connection.commit()
    fifth = admit_two_token_cycle(
        connection,
        binding=BINDING,
        policy=POLICY,
        now=t1h + timedelta(minutes=10),
        slots=_slot_payloads("cycle-x", (5, 6), (1, 2)),
        health=HEALTH,
    )
    assert fifth.mutation_performed is False
    assert fifth.evaluation.decision != AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE
    assert int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles"
        ).fetchone()[0]
    ) == 2
    policy = exact_operational_policy()
    assert policy["lifecycle_request_outer_ceiling"] == 476
    assert policy["lifecycle_requests_per_token"] == 118
    assert policy["lifecycle_scheduler_outer_ceiling"] == 444
    assert policy["automatic_retries"] == 0
    assert policy["endpoint_rotation"] is False
    locked = int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
            "WHERE step_key LIKE '%12h%' OR step_key LIKE '%24h%'"
        ).fetchone()[0]
    )
    assert locked == 0
    _integrity(connection)
    connection.close()


def test_cycle2_deadline_then_cycle1_snapshot_progress(tmp_path: Path) -> None:
    path = tmp_path / "deadline-progress.sqlite3"
    apply_migrations(path)
    connection = _open(path)
    stamp = _iso(NOW)
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        ("campaign-1", "RUNNING", "OPERATIONAL_PERSISTENT", "db-1", "policy-1", stamp, stamp),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json,created_at) VALUES (?,?,?,?,?,?)",
        ("configuration-1", "campaign-1", "a" * 64, "{}", "{}", stamp),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "factory-1",
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            json.dumps(
                {
                    "four_token_proof": True,
                    "campaign_id": "campaign-1",
                    "campaign_run_id": "campaign-run-1",
                },
                sort_keys=True,
            ),
            stamp,
            stamp,
            stamp,
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        ("campaign-run-1", "campaign-1", 1, "RUNNING", "factory-1", stamp, stamp),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_cycles("
        "cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("cycle-1", "campaign-1", "campaign-run-1", 1, "TRACKING", stamp, stamp),
    )
    _insert_token_pair(connection, token_id=11, pair_id=111, mint=MINT)
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_token_slots("
        "token_slot_id,campaign_id,run_id,cycle_id,slot_ordinal,token_identity,"
        "token_row_id,mint_identity,pair_identity,pair_row_id,lifecycle_identity,"
        "token_state,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "slot-cycle-1-1",
            "campaign-1",
            "campaign-run-1",
            "cycle-1",
            1,
            f"solana-mainnet:{MINT}",
            11,
            MINT,
            "pool-11",
            111,
            LIFECYCLE,
            "WINDOW_1H_CONTINUING",
            stamp,
            stamp,
        ),
    )
    connection.commit()
    started = NOW
    deadline = started + timedelta(seconds=2400)
    owner = PreLifecycleTemporalRefreshOwner(
        path,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1-2",
        supervision_id="supervision-1",
        source_governor=True,
        central_scheduler=True,
        acquisition_deadline_at=_iso(deadline),
        work_deadline_at=_iso(started + timedelta(seconds=18000)),
        refresh_stage=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("deadline must not run refresh stage")
        ),
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
    attempt = create_scheduled_pre_admission_attempt(
        connection,
        attempt_id="attempt-c2",
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        configuration_id="configuration-1",
        authoritative_factory_run_id="factory-1",
        proposed_cycle_ordinal=2,
        proposed_cycle_id="cycle-1-2",
        cycle_cutoff=NOW,
        evaluated_at=NOW,
        selection_seed_identity="seed-2",
        scheduled_for=NOW,
        now=NOW,
    )
    claimed = claim_due_job(
        connection,
        job_id=attempt.scheduler_job_id,
        lock_owner=pre_admission_attempt_lock_owner(attempt.attempt_id),
        now=NOW,
    )
    assert claimed is LockResult.ACQUIRED
    mark_pre_admission_attempt_running(
        connection, attempt_id=attempt.attempt_id, now=NOW
    )
    cycle1_key = cycle_step_key(
        slot_ordinal=1, cycle_ordinal=1, suffix="continuation_snapshot_00"
    )
    _insert_step_and_job(
        connection,
        run_id="factory-1",
        target={
            "token_id": 11,
            "pair_id": 111,
            "token_mint": MINT,
            "pair_address": "pool-11",
            "tracking_lane": "TRACK_FAST",
        },
        step_key=cycle1_key,
        step_kind="CONTINUATION_SNAPSHOT",
        scheduled_for=deadline,
    )
    connection.commit()

    def callback(**kwargs):
        outcome = owner.request_temporal_refresh(
            reserve_depth=0,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=9,
            now=str(kwargs["evaluated_at"]),
        )
        if outcome.status == ACQUISITION_DEADLINE_EXHAUSTED:
            terminalize_pre_admission_attempt(
                connection,
                attempt_id=attempt.attempt_id,
                state=PreAdmissionAttemptState.CANCELLED,
                cause=ACQUISITION_DEADLINE_EXHAUSTED,
                now=deadline,
            )
        return SimpleNamespace(
            attempt_id=attempt.attempt_id,
            state="CANCELLED",
            first_terminal_cause=outcome.status,
        )

    result = _run_four_token_admission_boundary(
        connection=connection,
        controller=SimpleNamespace(policy=POLICY),
        binding=BINDING,
        first_cycle_id="cycle-1",
        now=deadline,
        next_due_work_at=deadline + timedelta(seconds=87),
        proof_deadline=deadline + timedelta(hours=4),
        project_health=lambda: SimpleNamespace(health=SimpleNamespace()),
        evaluate=lambda projection: FourTokenAdmissionDisposition(
            FourTokenAdmissionDispositionKind.CYCLE_ADMISSION,
            "ADMISSION_READY",
            deadline,
            True,
        ),
        later_cycle_callback=callback,
        admit=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not admit")),
        materialize=lambda **kwargs: None,
        plan_opening=lambda **kwargs: None,
        acquisition_quantum_worst_case_seconds=115.0,
    )
    connection.commit()
    assert result.admitted is False
    assert result.attempt_terminal_cause == ACQUISITION_DEADLINE_EXHAUSTED
    assert result.disposition.kind is not FourTokenAdmissionDispositionKind.PROOF_DEADLINE
    assert _later_cycle_attempt_is_terminal(result.attempt_state)
    pending = _select_next_pending_step(connection, run_id="factory-1", now=deadline)
    assert pending is not None
    assert str(pending["step_key"]) == cycle1_key
    claimed_step = claim_due_job(
        connection,
        job_id=int(pending["scheduler_job_id"]),
        lock_owner="v2_4:factory-1",
        now=deadline,
    )
    assert claimed_step is LockResult.ACQUIRED
    executed = _execute_snapshot(
        connection,
        pending,
        adapter_factory=_dex_adapter(MINT, "pool-11"),
        timeout_seconds=1.0,
    )
    assert executed.get("snapshot_id") is not None
    _update_step(
        connection,
        int(pending["id"]),
        "SUCCEEDED",
        {"snapshot_id": int(executed["snapshot_id"])},
    )
    complete_job(
        connection, job_id=int(pending["scheduler_job_id"]), now=deadline
    )
    connection.commit()
    connection.close()
    reopened = _open(path)
    try:
        wait = reopened.execute(
            "SELECT wait_state FROM printer_pre_lifecycle_discovery_refresh_waits "
            "WHERE cycle_id='cycle-1-2'"
        ).fetchone()
        step = reopened.execute(
            "SELECT step_status,snapshot_id FROM printer_memory_factory_run_steps "
            "WHERE step_key=?",
            (cycle1_key,),
        ).fetchone()
        factory = reopened.execute(
            "SELECT run_status,stop_reason FROM printer_memory_factory_runs "
            "WHERE run_id='factory-1'"
        ).fetchone()
        slot = reopened.execute(
            "SELECT token_state FROM printer_memory_factory_campaign_token_slots "
            "WHERE token_slot_id='slot-cycle-1-1'"
        ).fetchone()
        assert wait["wait_state"] == "CANCELLED"
        assert step["step_status"] == "SUCCEEDED"
        assert step["snapshot_id"] is not None
        assert factory["run_status"] == "RUNNING"
        assert factory["stop_reason"] is None
        assert slot["token_state"] == "WINDOW_1H_CONTINUING"
        _integrity(reopened)
    finally:
        reopened.close()


def test_serial_close_evidence_owner_marks_missed_close_failed(tmp_path: Path) -> None:
    path = tmp_path / "closes-prod.sqlite3"
    apply_migrations(path)
    connection = _open(path)
    stamp = _iso(NOW)
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "factory-1",
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            json.dumps({"four_token_proof": False}, sort_keys=True),
            stamp,
            stamp,
            stamp,
        ),
    )
    due = NOW + timedelta(seconds=1)
    keys = []
    for cycle, token in ((1, 1), (1, 2), (2, 1), (2, 2)):
        token_id = cycle * 10 + token
        pair_id = cycle * 100 + token
        mint = f"mint-{token_id}"
        _insert_token_pair(connection, token_id=token_id, pair_id=pair_id, mint=mint)
        key = cycle_step_key(
            slot_ordinal=token,
            cycle_ordinal=cycle,
            suffix="window_close_evidence",
        )
        keys.append(key)
        prefix = cycle_step_key(
            slot_ordinal=token, cycle_ordinal=cycle, suffix="token"
        )
        _insert_step_and_job(
            connection,
            run_id="factory-1",
            target={
                "token_id": token_id,
                "pair_id": pair_id,
                "token_mint": mint,
                "pair_address": f"pool-{token_id}",
                "tracking_lane": "TRACK_FAST",
            },
            step_key=key,
            step_kind="WINDOW_CLOSE_EVIDENCE",
            scheduled_for=due,
            result_projection=close_phase_metadata(
                family="WINDOW_CLOSE",
                phase="EVIDENCE",
                evidence_step_key=key,
                context_step_key=f"{prefix}_window_close_context",
                preclose_step_key=f"{prefix}_window_close_pre_close_critical",
            ),
        )
    connection.commit()
    served: list[str] = []
    outcomes: dict[str, str] = {}
    now = due + timedelta(seconds=1)
    for index in range(4):
        pending = _select_next_pending_step(connection, run_id="factory-1", now=now)
        assert pending is not None
        key = str(pending["step_key"])
        served.append(key)
        claimed = claim_due_job(
            connection,
            job_id=int(pending["scheduler_job_id"]),
            lock_owner="v2_4:factory-1",
            now=now,
        )
        assert claimed is LockResult.ACQUIRED
        connection.execute(
            "UPDATE printer_memory_factory_run_steps SET step_status='RUNNING',"
            "updated_at=? WHERE id=?",
            (_iso(now), int(pending["id"])),
        )
        connection.commit()
        pending = connection.execute(
            "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
            (int(pending["id"]),),
        ).fetchone()
        if index == 3:
            adapter = lambda **kwargs: build_fixture_source_adapter(
                "dexscreener",
                fixture_kind="fixture_failure",
                fixture_payload={
                    "fixture_status": "failure",
                    "failure_type": "dexscreener_timeout",
                    "failure_message": "close evidence missed",
                },
            )
        else:
            adapter = _dex_adapter(
                str(pending["token_mint"]), str(pending["pair_address"])
            )
        result = _execute_close_evidence_phase(
            connection,
            pending,
            adapter_factory=adapter,
            timeout_seconds=1.0,
        )
        if result.get("ok"):
            _update_step(connection, int(pending["id"]), "SUCCEEDED", result)
            complete_job(
                connection, job_id=int(pending["scheduler_job_id"]), now=now
            )
            outcomes[key] = "SUCCEEDED"
        else:
            _update_step(
                connection,
                int(pending["id"]),
                "FAILED",
                result,
                error=str(result.get("blocked_reason") or "close evidence missed"),
            )
            fail_job(
                connection,
                job_id=int(pending["scheduler_job_id"]),
                error=str(result.get("blocked_reason") or "close evidence missed"),
                max_retries=0,
                now=now,
            )
            outcomes[key] = str(result.get("blocked_reason") or "FAILED")
        connection.commit()
    assert sorted(served) == sorted(keys)
    leftover = _select_next_pending_step(connection, run_id="factory-1", now=now)
    assert leftover is None
    failed = [key for key, status in outcomes.items() if status != "SUCCEEDED"]
    succeeded = [key for key, status in outcomes.items() if status == "SUCCEEDED"]
    assert len(succeeded) == 3, outcomes
    assert len(failed) == 1, outcomes
    failed_row = connection.execute(
        "SELECT step_status,result_json FROM printer_memory_factory_run_steps "
        "WHERE step_key=?",
        (failed[0],),
    ).fetchone()
    payload = json.loads(str(failed_row["result_json"] or "{}"))
    assert failed_row["step_status"] == "FAILED"
    assert payload.get("ok") is not True
    _integrity(connection)
    connection.close()


def test_cooperative_resume_reuses_governed_source_request(tmp_path: Path) -> None:
    path = _seed_campaign(tmp_path / "gov-resume.sqlite3")
    connection = _open(path)
    attempt = create_scheduled_pre_admission_attempt(
        connection,
        attempt_id="attempt-resume",
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        configuration_id="configuration-1",
        authoritative_factory_run_id="factory-1",
        proposed_cycle_ordinal=2,
        proposed_cycle_id="cycle-1-2",
        cycle_cutoff=NOW,
        evaluated_at=NOW,
        selection_seed_identity="seed-resume",
        scheduled_for=NOW,
        now=NOW,
    )
    connection.commit()
    root = derive_campaign_source_request_key_root("campaign-1:campaign-run-1")
    request_prefix = f"{root}:cycle-2"
    transport_calls: list[str] = []

    def locator_transport(_ctx):
        transport_calls.append("dex")
        identity = build_transport_identity(
            stage="DEXSCREENER_DISCOVERY",
            source_name="dexscreener_profiles",
            endpoint_owner="dexscreener",
            governed_request_kind="dexscreener_fresh_profiles",
            method_or_endpoint="GET /token-profiles/latest/v1",
            within_request_ordinal=1,
            target_category="fresh_profiles",
            target_identity="MintABC1111111111111111111111111111111",
            response_bytes=64,
            normalized_rows=1,
            result="OK",
        )
        payload = {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": "pool-resume",
                    "baseToken": {
                        "address": "MintABC1111111111111111111111111111111",
                        "symbol": "TOK",
                        "name": "Token",
                    },
                    "priceUsd": "0.01",
                    "liquidity": {"usd": 5000},
                }
            ]
        }
        payload.update(
            measured_payload_fields(
                [identity], response_bytes=64, normalized_rows=1
            )
        )
        return payload

    stage = build_pre_lifecycle_refresh_stage(
        db_path=path,
        request_key_prefix=request_prefix,
        locator_transport=locator_transport,
    )
    first = stage(
        connection,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1-2",
        discovery_work_id="work-1",
        scheduler_job_id=1,
        refresh_ordinal=2,
        source_operations_remaining=9,
        now=_iso(NOW),
        cooperative_yield=True,
        cooperative_stage_budget=StageBudget.permanent_discovery_default(),
    )
    assert first.get("cooperative_incomplete") is True
    assert int(first.get("source_operations") or 0) == 1
    requests = list(
        connection.execute(
            "SELECT id,request_key FROM printer_source_requests ORDER BY id"
        )
    )
    assert len(requests) == 1
    request_id = int(requests[0]["id"])
    request_key = str(requests[0]["request_key"])
    assert request_key.startswith(root)
    responses = int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_source_responses WHERE source_request_id=?",
            (request_id,),
        ).fetchone()[0]
    )
    assert responses == 1
    append_pre_admission_attempt_evidence(
        connection,
        attempt_id=attempt.attempt_id,
        event_key=f"source-request:{request_id}",
        opportunity_ordinal=2,
        claim_ordinal=1,
        evidence_kind="SOURCE_REQUEST_TERMINAL",
        observed_at=_iso(NOW),
        source_request_id=request_id,
        categorical_reason="SOURCE_RESPONSE",
        payload={"logical_stage": "DEXSCREENER_FRESH"},
    )
    connection.commit()
    second = stage(
        connection,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1-2",
        discovery_work_id="work-1",
        scheduler_job_id=1,
        refresh_ordinal=2,
        source_operations_remaining=8,
        now=_iso(NOW + timedelta(seconds=8)),
        cooperative_yield=True,
        cooperative_stage_budget=StageBudget.permanent_discovery_default(),
    )
    replay = second.get("stage_reports", {}).get("dexscreener_fresh_profiles", {})
    assert replay.get("status") == "COOPERATIVE_CHECKPOINT_REPLAY"
    assert int(replay.get("source_requests") or 0) == 0
    assert transport_calls == ["dex"]
    assert int(
        connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]
    ) == 1
    assert int(
        connection.execute("SELECT COUNT(*) FROM printer_source_responses").fetchone()[0]
    ) == 1
    policy = exact_operational_policy()
    assert policy["automatic_retries"] == 0
    assert policy["endpoint_rotation"] is False
    _integrity(connection)
    connection.close()


def test_parent_interrupt_waiting_still_durable(tmp_path: Path) -> None:
    path = _seed_campaign(tmp_path / "pi.sqlite3", cycle_state="TERMINAL_BLOCKED")
    connection = _open(path)
    _insert_cycle1_slot(connection, token_state="WINDOW_1H_CONTINUING")
    attempt = create_scheduled_pre_admission_attempt(
        connection,
        attempt_id="attempt-c2",
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        configuration_id="configuration-1",
        authoritative_factory_run_id="factory-1",
        proposed_cycle_ordinal=2,
        proposed_cycle_id="cycle-2",
        cycle_cutoff=NOW,
        evaluated_at=NOW,
        selection_seed_identity="seed-2",
        scheduled_for=NOW,
        now=NOW,
    )
    claimed = claim_due_job(
        connection,
        job_id=attempt.scheduler_job_id,
        lock_owner=pre_admission_attempt_lock_owner(attempt.attempt_id),
        now=NOW,
    )
    assert claimed is LockResult.ACQUIRED
    mark_pre_admission_attempt_running(
        connection, attempt_id=attempt.attempt_id, now=NOW
    )
    wait_id, refresh_job = _insert_refresh(connection, wait_state="WAITING")
    report = reconcile_parent_interrupted_open_pre_admission_attempts(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        now=NOW,
    )
    connection.close()
    assert report["replay_state"] == "A"
    connection = _open(path)
    try:
        attempt_row = connection.execute(
            "SELECT attempt_state FROM printer_pre_admission_discovery_attempts "
            "WHERE attempt_id=?",
            (attempt.attempt_id,),
        ).fetchone()
        wait = connection.execute(
            "SELECT wait_state FROM printer_pre_lifecycle_discovery_refresh_waits "
            "WHERE wait_id=?",
            (wait_id,),
        ).fetchone()
        job = connection.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id=?",
            (refresh_job,),
        ).fetchone()
        slot = connection.execute(
            "SELECT token_state FROM printer_memory_factory_campaign_token_slots "
            "WHERE token_slot_id='slot-cycle-1-1'"
        ).fetchone()
        assert attempt_row["attempt_state"] == "CANCELLED"
        assert wait["wait_state"] == "CANCELLED"
        assert job["status"] == "CANCELLED"
        assert slot["token_state"] == "WINDOW_1H_CONTINUING"
        _integrity(connection)
    finally:
        connection.close()

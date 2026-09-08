from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import shutil
import sqlite3
from types import SimpleNamespace

from printer_v1.db import apply_migrations
from printer_v1.db.migrate import canonical_migration_count, canonical_migration_names
from printer_v1.operator_cli.authoritative_admission_health import (
    AdmissionHealthProjection,
)
from printer_v1.operator_cli.campaign_ownership import create_cycle_with_two_slots
from printer_v1.operator_cli.four_token_proof_integration import (
    FourTokenAdmissionDisposition,
    FourTokenAdmissionDispositionKind,
    FourTokenControllerReadiness,
    build_four_token_proof_policy,
    next_four_token_factory_wake,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
    MultiCycleCampaignBinding,
    MultiCycleCampaignSnapshot,
    multi_cycle_configuration_contract,
)
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    AdmissionDecision,
    AdmissionEvaluation,
    MultiCycleSessionPhase,
    MultiCycleSessionSnapshot,
)
from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli import four_token_factory_adapter as four_token_adapter
from printer_v1.operator_cli.window_15m_concrete_composition import (
    ordinary_window_15m_builder_identities,
)
from printer_v1.operator_cli.window_15m_disposable_public_composition_proof import (
    build_disposable_public_composition_proof_binding,
    build_disposable_public_composition_proof_plan,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    SOURCE_GOVERNOR_OWNER,
    OwnerPort,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    LaterCycleCandidateSupply,
)
from printer_v1.discovery.eligible_token_supply import (
    ACQUISITION_QUANTUM_YIELDED,
    AcquisitionQuantumKind,
    acquisition_quantum_bound,
)
from printer_v1.discovery.permanent_discovery_availability import StageBudget
from printer_v1.sources.governed_execution import (
    FIXTURE_FAILURE,
    build_fixture_source_adapter,
)
from printer_v1.sources import contracts as source_contracts


START = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
POLICY = build_four_token_proof_policy()
CAMPAIGN_ID = "wake-order-campaign"
CAMPAIGN_RUN_ID = "wake-order-campaign-run"
CYCLE_ID = "wake-order-cycle-1"
CONFIGURATION_ID = "wake-order-configuration"
FACTORY_RUN_ID = "wake-order-factory"


def _sha256(path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _slot(
    row_id: int,
    ordinal: int,
    *,
    tracking_queue_id: int | None = None,
) -> dict[str, object]:
    return {
        "token_slot_id": f"t{ordinal}_c0001_slot",
        "slot_ordinal": ordinal,
        "token_identity": f"solana-mainnet:mint-{row_id}",
        "token_row_id": row_id,
        "mint_identity": f"mint-{row_id}",
        "pair_identity": f"pool-{row_id}",
        "pair_row_id": 100 + row_id,
        "lifecycle_identity": "PUMPSWAP_GRADUATED_CONFIRMED",
        "tracking_queue_id": tracking_queue_id,
        "replacement_predecessor_slot_id": None,
    }


def _prepare(
    tmp_path,
    *,
    tracking_lanes=("TRACK_NORMAL", "TRACK_NORMAL"),
):
    db = tmp_path / "wake-order.sqlite3"
    backup = tmp_path / "wake-order.backup.sqlite3"
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    apply_migrations(db)
    connection = sqlite3.connect(db)
    configuration = {
        "token_capacity": 2,
        "ceilings": {"cycle_count": POLICY.total_cycle_admission_ceiling},
        "multi_cycle_capacity": multi_cycle_configuration_contract(
            POLICY, intake_started_at=START
        ),
    }
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES (?,?,?,?,?)",
        (CAMPAIGN_ID, "RUNNING", "OPERATIONAL_PERSISTENT", "db-1", "policy-1"),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json) VALUES (?,?,?,?,?)",
        (
            CONFIGURATION_ID,
            CAMPAIGN_ID,
            "a" * 64,
            json.dumps(configuration, sort_keys=True),
            '{"commit":"disposable"}',
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            CAMPAIGN_RUN_ID,
            CAMPAIGN_ID,
            1,
            "RUNNING",
            None,
            START.isoformat(),
            START.isoformat(),
        ),
    )
    from printer_v1.operator_cli.cadence_authority import (
        claim_tracking_authority_for_slot_insert,
    )

    for row_id in (1, 2):
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?,'solana')",
            (row_id, f"mint-{row_id}"),
        )
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
            "VALUES (?,?,?,?)",
            (100 + row_id, row_id, f"pool-{row_id}", f"mint-{row_id}"),
        )
    # Design Lane 1: Cycle-1 fixtures must insert-bind exact tracking authority
    # before WINDOW_15M opening (slot.tracking_queue_id is immutable after insert).
    if tuple(tracking_lanes) not in {
        ("TRACK_NORMAL", "TRACK_NORMAL"),
        ("TRACK_FAST", "TRACK_NORMAL"),
        ("TRACK_NORMAL", "TRACK_FAST"),
        ("TRACK_FAST", "TRACK_FAST"),
    }:
        raise ValueError("test fixture requires exact FAST/NORMAL tracking lanes")
    queue_ids = tuple(
        claim_tracking_authority_for_slot_insert(
            connection,
            token_row_id=row_id,
            pair_row_id=100 + row_id,
            tracking_lane=lane,
            now=START,
        )
        for row_id, lane in zip((1, 2), tracking_lanes, strict=True)
    )
    create_cycle_with_two_slots(
        connection,
        campaign_id=CAMPAIGN_ID,
        run_id=CAMPAIGN_RUN_ID,
        cycle_id=CYCLE_ID,
        cycle_ordinal=1,
        slots=(_slot(1, 1, tracking_queue_id=queue_ids[0]), _slot(2, 2, tracking_queue_id=queue_ids[1])),
        now=START.isoformat(),
    )
    connection.commit()
    connection.close()
    shutil.copy2(db, backup)

    digest = _sha256(db)
    plan = build_disposable_public_composition_proof_plan(
        proof_id="FOUR_TOKEN_WAKE_ORDERING_RED",
        db_path=db,
        db_sha256=digest,
        migration_count=canonical_migration_count(),
        migration_head=canonical_migration_names()[-1],
        artifact_root=artifacts,
        composition_labels=ordinary_window_15m_builder_identities(),
        provider_execution_allowed=False,
        automatic_retry_allowed=False,
        manual_rerun_allowed=False,
        resume_allowed=False,
        restart_allowed=False,
        successor_allowed=False,
    )
    binding = build_disposable_public_composition_proof_binding(
        plan,
        execution_id="wake-order-execution",
        campaign_id=CAMPAIGN_ID,
        campaign_run_id=CAMPAIGN_RUN_ID,
        cycle_id=CYCLE_ID,
        configuration_id=CONFIGURATION_ID,
        db_target_identity=f"sha256:{digest}",
        fixture_composition_manifest_sha256="b" * 64,
    )
    return db, backup, binding


def _healthy_projection() -> AdmissionHealthProjection:
    return AdmissionHealthProjection(
        health=MultiCycleAdmissionHealth(
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
        ),
        recheck_at=None,
        recheck_on_lifecycle_change=False,
        evidence=(),
        reasons=(),
    )


@dataclass
class _SpacingController:
    policy: object = POLICY

    def evaluate_factory_wake(
        self, connection, *, binding, now, next_due_work_at, proof_deadline,
        admission_health,
    ) -> FourTokenControllerReadiness:
        del connection, binding, admission_health
        session = MultiCycleSessionSnapshot(
            intake_started_at=START,
            intake_deadline=proof_deadline,
            configured_through_4h_token_ceiling=4,
            configured_active_cycle_ceiling=2,
            total_cycle_admission_ceiling=2,
            active_through_4h_tokens=2,
            active_cycles=1,
            admissions_completed=1,
            last_cycle_admitted_at=START,
            phase=MultiCycleSessionPhase.ACTIVE_INTAKE,
        )
        return FourTokenControllerReadiness(
            snapshot=MultiCycleCampaignSnapshot(
                campaign_id=CAMPAIGN_ID,
                campaign_run_id=CAMPAIGN_RUN_ID,
                configuration_id=CONFIGURATION_ID,
                authoritative_factory_run_id=FACTORY_RUN_ID,
                cycle_ids=(CYCLE_ID,),
                active_cycle_ids=(CYCLE_ID,),
                active_token_slot_ids=("t1_c0001_slot", "t2_c0001_slot"),
                first_cycle_id=CYCLE_ID,
                session=session,
                admission_evaluation=AdmissionEvaluation(
                    AdmissionDecision.DEFER,
                    "minimum_admission_spacing_not_elapsed",
                ),
            ),
            wake=next_four_token_factory_wake(
                now=now,
                next_due_work_at=next_due_work_at,
                next_admission_at=START + timedelta(seconds=300),
                proof_deadline=proof_deadline,
            ),
        )


def test_real_factory_loop_wakes_future_lifecycle_before_spacing_boundary(
    tmp_path, monkeypatch
) -> None:
    db, backup, disposable_binding = _prepare(tmp_path)
    clock = [START]
    waits: list[float] = []

    def discovery(_args):
        connection = sqlite3.connect(db)
        connection.execute(
            "INSERT INTO printer_selection_batches("
            "batch_id,batch_status,window_kind,candidate_pool_total,selected_count,"
            "operator_approved) VALUES ('wake-batch','ASSEMBLED','WINDOW_15M',2,2,1)"
        )
        for row_id in (1, 2):
            connection.execute(
                "INSERT INTO printer_selection_batch_items("
                "batch_id,item_status,token_id,pair_id,token_mint,pair_address,"
                "tracking_lane,operator_approved) VALUES "
                "('wake-batch','SELECTED',?,?,?,?, 'TRACK_NORMAL',1)",
                (row_id, 100 + row_id, f"mint-{row_id}", f"pool-{row_id}"),
            )
        connection.commit()
        connection.close()
        return {
            "selection_handoff_report": {
                "batch_id": "wake-batch",
                "selection_seed": "wake-seed",
                "eligible_pool_size": 2,
            },
            "discovery_results": [],
        }

    original_plan = factory._plan_opening_jobs

    def plan_future_lifecycle(connection, run_id, targets, now, **kwargs):
        original_plan(connection, run_id, targets, now, **kwargs)
        due = (now + timedelta(seconds=100)).isoformat()
        connection.execute(
            "UPDATE printer_memory_factory_run_steps SET scheduled_for=? WHERE run_id=?",
            (due, run_id),
        )
        connection.execute(
            "UPDATE printer_scheduler_jobs SET scheduled_for=? WHERE id IN ("
            "SELECT scheduler_job_id FROM printer_memory_factory_run_steps WHERE run_id=?)",
            (due, run_id),
        )

    def stop_at_first_wait(seconds: float, *, sleep, probe) -> None:
        del sleep, probe
        waits.append(seconds)
        raise factory._ExternalStop("FOCUSED_WAKE_OBSERVED")

    monkeypatch.setattr(factory, "_now", lambda: clock[0])
    monkeypatch.setattr(factory, "_plan_opening_jobs", plan_future_lifecycle)
    monkeypatch.setattr(factory, "_sleep_with_cancellation", stop_at_first_wait)
    monkeypatch.setattr(
        four_token_adapter,
        "finalize_four_token_shared_terminal",
        lambda *args, **kwargs: {
            "shared_terminalized": True,
            "shared_cleanup_count": 1,
        },
    )

    report = factory.run_one_command_15m_factory(
        db,
        backup,
        operator_approved=True,
        proof_mode=False,
        operational_persistent_mode=True,
        disposable_public_composition_proof_binding=disposable_binding,
        discovery_runner=discovery,
        launch_provenance={
            "git_head": "c" * 40,
            "git_tracked_tree_clean": True,
            "git_staged_changes_present": False,
            "git_unstaged_changes_present": False,
            "git_untracked_present": True,
            "git_provenance_captured_at": START.isoformat(),
        },
        standard_four_hour_campaign=True,
        selective_1h_continuation=True,
        continuous_first_hour=True,
        continuous_four_hour=True,
        total_duration_seconds=20_000,
        _window_seconds=900,
        _continuation_seconds=3_600,
        max_selected_tokens=2,
        campaign_id=CAMPAIGN_ID,
        campaign_run_id=CAMPAIGN_RUN_ID,
        cycle_id=CYCLE_ID,
        configuration_id=CONFIGURATION_ID,
        factory_run_id=FACTORY_RUN_ID,
        four_token_proof_controller=_SpacingController(),
        later_cycle_discovery_callback=lambda **_: None,
        four_token_health_projector=lambda _connection, _now: _healthy_projection(),
        four_token_shared_terminalizer=lambda **_: {
            "clean_terminal": True,
            "lease_released": True,
        },
        source_governor_owner=OwnerPort(SOURCE_GOVERNOR_OWNER, True),
        central_scheduler_owner=OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
        _sleep=lambda _seconds: None,
        _monotonic=lambda: 0.0,
    )

    assert waits == [100], json.dumps(report, sort_keys=True, default=str)
    assert report["stop_reason"] == "FOCUSED_WAKE_OBSERVED"


@dataclass
class _CadenceReadyController:
    policy: object = POLICY

    def evaluate_factory_wake(
        self, connection, *, binding, now, next_due_work_at, proof_deadline,
        admission_health,
    ) -> FourTokenControllerReadiness:
        del connection, binding, admission_health
        session = MultiCycleSessionSnapshot(
            intake_started_at=START,
            intake_deadline=proof_deadline,
            configured_through_4h_token_ceiling=4,
            configured_active_cycle_ceiling=2,
            total_cycle_admission_ceiling=2,
            active_through_4h_tokens=2,
            active_cycles=1,
            admissions_completed=1,
            last_cycle_admitted_at=START,
            phase=MultiCycleSessionPhase.ACTIVE_INTAKE,
        )
        return FourTokenControllerReadiness(
            snapshot=MultiCycleCampaignSnapshot(
                campaign_id=CAMPAIGN_ID,
                campaign_run_id=CAMPAIGN_RUN_ID,
                configuration_id=CONFIGURATION_ID,
                authoritative_factory_run_id=FACTORY_RUN_ID,
                cycle_ids=(CYCLE_ID,),
                active_cycle_ids=(CYCLE_ID,),
                active_token_slot_ids=("t1_c0001_slot", "t2_c0001_slot"),
                first_cycle_id=CYCLE_ID,
                session=session,
                admission_evaluation=AdmissionEvaluation(
                    AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE,
                    "capacity_available",
                ),
            ),
            wake=next_four_token_factory_wake(
                now=now,
                next_due_work_at=next_due_work_at,
                next_admission_at=now,
                proof_deadline=proof_deadline,
            ),
        )


def test_latest_lawful_cycle2_start_reaches_discovery_at_exact_reserve_boundary(
    tmp_path,
) -> None:
    db, _backup, _disposable_binding = _prepare(tmp_path)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    callback_calls = 0

    def boundary_callback(**_kwargs):
        nonlocal callback_calls
        callback_calls += 1
        return SimpleNamespace(
            attempt_id="boundary-attempt",
            state="NO_PAIR",
            first_terminal_cause="BOUNDARY_FIXTURE_NO_PAIR",
        )

    try:
        now = START + timedelta(seconds=900)
        deadline = START + timedelta(seconds=18_000)
        result = factory._run_four_token_admission_boundary(
            connection=connection,
            controller=_CadenceReadyController(),
            binding=MultiCycleCampaignBinding(
                campaign_id=CAMPAIGN_ID,
                campaign_run_id=CAMPAIGN_RUN_ID,
                configuration_id=CONFIGURATION_ID,
                authoritative_factory_run_id=FACTORY_RUN_ID,
            ),
            first_cycle_id=CYCLE_ID,
            now=now,
            next_due_work_at=None,
            proof_deadline=deadline,
            project_health=_healthy_projection,
            evaluate=lambda _projection: FourTokenAdmissionDisposition(
                FourTokenAdmissionDispositionKind.CYCLE_ADMISSION,
                "ADMISSION_READY",
                now,
                True,
            ),
            later_cycle_callback=boundary_callback,
            admit=lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("NO_PAIR boundary fixture must not admit")
            ),
            materialize=lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("NO_PAIR boundary fixture must not materialize")
            ),
            plan_opening=lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("NO_PAIR boundary fixture must not plan lifecycle")
            ),
        )
        assert callback_calls == 1
        assert result.admitted is False
        assert result.attempt_state == "NO_PAIR"
        assert result.attempt_terminal_cause == "BOUNDARY_FIXTURE_NO_PAIR"
    finally:
        connection.close()


def test_late_new_cycle2_start_is_blocked_before_discovery(tmp_path) -> None:
    db, _backup, _disposable_binding = _prepare(tmp_path)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    callback_calls = 0

    def forbidden_callback(**_kwargs):
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("late Cycle-2 discovery must not start")

    try:
        now = START + timedelta(seconds=901)
        deadline = START + timedelta(seconds=18_000)
        result = factory._run_four_token_admission_boundary(
            connection=connection,
            controller=_CadenceReadyController(),
            binding=MultiCycleCampaignBinding(
                campaign_id=CAMPAIGN_ID,
                campaign_run_id=CAMPAIGN_RUN_ID,
                configuration_id=CONFIGURATION_ID,
                authoritative_factory_run_id=FACTORY_RUN_ID,
            ),
            first_cycle_id=CYCLE_ID,
            now=now,
            next_due_work_at=None,
            proof_deadline=deadline,
            project_health=_healthy_projection,
            evaluate=lambda _projection: FourTokenAdmissionDisposition(
                FourTokenAdmissionDispositionKind.CYCLE_ADMISSION,
                "ADMISSION_READY",
                now,
                True,
            ),
            later_cycle_callback=forbidden_callback,
            admit=lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("late Cycle-2 admission must not run")
            ),
            materialize=lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("late Cycle-2 materialization must not run")
            ),
            plan_opening=lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("late Cycle-2 lifecycle planning must not run")
            ),
        )
        assert callback_calls == 0
        assert result.admitted is False
        assert (
            result.disposition.kind
            is FourTokenAdmissionDispositionKind.BLOCKED
        )
        assert (
            result.disposition.reason
            == "INSUFFICIENT_LATER_CYCLE_COMPLETION_RESERVE"
        )
    finally:
        connection.close()


def test_real_factory_controlled_clock_interleaves_scheduler_yields_and_snapshots(
    tmp_path, monkeypatch
) -> None:
    db, backup, disposable_binding = _prepare(tmp_path)

    class Clock:
        def __init__(self):
            self.instant = START
            self.elapsed = 0.0

        def now(self):
            return self.instant

        def monotonic(self):
            return self.elapsed

        def sleep(self, seconds):
            self.elapsed += float(seconds)
            self.instant += timedelta(seconds=float(seconds))

    clock = Clock()

    class ClockDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = clock.now()
            return value if tz is None else value.astimezone(tz)
    snapshot_times = {"mint-1": [], "mint-2": []}
    quantum_phases = (
        AcquisitionQuantumKind.AUXILIARY_FRESH_INTAKE,
        AcquisitionQuantumKind.AUXILIARY_LIQUIDITY_BACKUP,
        AcquisitionQuantumKind.AUXILIARY_PROTOCOL_CONFIRMATION,
        AcquisitionQuantumKind.DIRECT_MIGRATION,
        AcquisitionQuantumKind.MARKET_DISCOVERY,
        AcquisitionQuantumKind.PROTOCOL_CONFIRMATION,
        AcquisitionQuantumKind.PROTOCOL_RESUME_MARKET,
    )
    quantum_calls: list[AcquisitionQuantumKind] = []
    bound_resolutions: list[AcquisitionQuantumKind] = []
    stage_budget = StageBudget.permanent_discovery_default()
    stage_snapshots = [stage_budget.snapshot()]

    def supply(**_context):
        phase = quantum_phases[min(len(quantum_calls), len(quantum_phases) - 1)]
        if phase is AcquisitionQuantumKind.AUXILIARY_FRESH_INTAKE:
            stage_budget.consume("intake", 2)
        elif phase is AcquisitionQuantumKind.AUXILIARY_LIQUIDITY_BACKUP:
            stage_budget.consume("reconciliation", 1)
        elif phase is AcquisitionQuantumKind.AUXILIARY_PROTOCOL_CONFIRMATION:
            stage_budget.consume("protocol_confirmation", 1)
        elif phase is AcquisitionQuantumKind.DIRECT_MIGRATION:
            stage_budget.consume("intake", 1)
            stage_budget.consume("protocol_confirmation", 1)
        elif phase is AcquisitionQuantumKind.MARKET_DISCOVERY:
            stage_budget.consume("market_batching", 1)
            stage_budget.consume("reconciliation", 2)
        elif phase is AcquisitionQuantumKind.PROTOCOL_CONFIRMATION:
            stage_budget.consume("protocol_confirmation", 1)
        elif phase is AcquisitionQuantumKind.PROTOCOL_RESUME_MARKET:
            stage_budget.consume("market_batching", 1)
        quantum_calls.append(phase)
        stage_snapshots.append(stage_budget.snapshot())
        clock.sleep(acquisition_quantum_bound(phase).worst_case_seconds)
        return LaterCycleCandidateSupply(
            (),
            (),
            ACQUISITION_QUANTUM_YIELDED,
            {
                "stage_local_source_requests": stage_budget.snapshot()["total_used"],
                "provider_failures": 0,
                "shortage_classification": None,
                "stage_capacity": stage_budget.snapshot(),
            },
        )

    def next_quantum_seconds() -> float:
        phase = quantum_phases[min(len(quantum_calls), len(quantum_phases) - 1)]
        bound_resolutions.append(phase)
        return acquisition_quantum_bound(phase).worst_case_seconds

    callback = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=supply
    )._build_later_cycle_discovery_callback(
        db_path=db, configuration_id=CONFIGURATION_ID
    )

    def snapshot_factory(*, token_mint, timeout_seconds):
        del timeout_seconds
        snapshot_times[token_mint].append(clock.now())
        pool = "pool-1" if token_mint == "mint-1" else "pool-2"
        return build_fixture_source_adapter(
            "dexscreener",
            fixture_payload={"pairs": [{
                "chain": "solana",
                "token_mint": token_mint,
                "pair_address": pool,
                "price_usd": 1.0,
                "liquidity_usd": 10_000.0,
                "volume_5m": 10.0,
                "volume_1h": 20.0,
                "volume_24h": 30.0,
                "txns_5m": 2,
                "txns_1h": 4,
                "txns_24h": 6,
                "buys_5m": 1,
                "sells_5m": 1,
                "buys_1h": 2,
                "sells_1h": 2,
                "buys_24h": 3,
                "sells_24h": 3,
                "price_change_5m": 0.0,
                "price_change_1h": 0.0,
                "price_change_24h": 0.0,
            }]},
        )

    context_factories = {
        name: (lambda _name=name, **_kwargs: build_fixture_source_adapter(
            _name, fixture_kind=FIXTURE_FAILURE
        ))
        for name in ("coingecko", "goplus", "jupiter_quote")
    } | {
        "solana_rpc_holder": lambda **_kwargs: build_fixture_source_adapter(
            "solana_rpc", fixture_kind=FIXTURE_FAILURE
        )
    }

    monkeypatch.setattr(factory, "_now", clock.now)
    monkeypatch.setattr(source_contracts, "datetime", ClockDateTime)
    monkeypatch.setattr(
        four_token_adapter,
        "finalize_four_token_shared_terminal",
        lambda *args, **kwargs: {
            "shared_terminalized": True,
            "shared_cleanup_count": 1,
        },
    )

    def discovery(_args):
        connection = sqlite3.connect(db)
        connection.execute(
            "INSERT INTO printer_selection_batches("
            "batch_id,batch_status,window_kind,candidate_pool_total,selected_count,"
            "operator_approved) VALUES ('cadence-batch','ASSEMBLED','WINDOW_15M',2,2,1)"
        )
        for row_id in (1, 2):
            connection.execute(
                "INSERT INTO printer_selection_batch_items("
                "batch_id,item_status,token_id,pair_id,token_mint,pair_address,"
                "tracking_lane,operator_approved) VALUES "
                "('cadence-batch','SELECTED',?,?,?,?, 'TRACK_NORMAL',1)",
                (row_id, 100 + row_id, f"mint-{row_id}", f"pool-{row_id}"),
            )
        connection.commit()
        connection.close()
        return {
            "selection_handoff_report": {
                "batch_id": "cadence-batch",
                "selection_seed": "cadence-seed",
                "eligible_pool_size": 2,
            },
            "discovery_results": [],
        }

    report = factory.run_one_command_15m_factory(
        db,
        backup,
        operator_approved=True,
        proof_mode=False,
        operational_persistent_mode=True,
        disposable_public_composition_proof_binding=disposable_binding,
        discovery_runner=discovery,
        launch_provenance={
            "git_head": "c" * 40,
            "git_tracked_tree_clean": True,
            "git_staged_changes_present": False,
            "git_unstaged_changes_present": False,
            "git_untracked_present": True,
            "git_provenance_captured_at": START.isoformat(),
        },
        standard_four_hour_campaign=True,
        selective_1h_continuation=True,
        continuous_first_hour=True,
        continuous_four_hour=True,
        total_duration_seconds=20_000,
        _window_seconds=1_800,
        _continuation_seconds=3_600,
        max_selected_tokens=2,
        campaign_id=CAMPAIGN_ID,
        campaign_run_id=CAMPAIGN_RUN_ID,
        cycle_id=CYCLE_ID,
        configuration_id=CONFIGURATION_ID,
        factory_run_id=FACTORY_RUN_ID,
        four_token_proof_controller=_CadenceReadyController(),
        later_cycle_discovery_callback=callback,
        later_cycle_acquisition_quantum_seconds=next_quantum_seconds,
        four_token_health_projector=lambda _connection, _now: _healthy_projection(),
        four_token_shared_terminalizer=lambda **_: {
            "clean_terminal": True,
            "lease_released": True,
        },
        source_governor_owner=OwnerPort(SOURCE_GOVERNOR_OWNER, True),
        central_scheduler_owner=OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
        snapshot_adapter_factory=snapshot_factory,
        context_adapter_factories=context_factories,
        _sleep=clock.sleep,
        _monotonic=clock.monotonic,
        cancellation_probe=lambda: (
            "FOCUSED_CADENCE_COMPLETE" if clock.elapsed >= 1_600 else None
        ),
    )

    assert len(quantum_calls) >= 3, json.dumps(report, sort_keys=True, default=str)
    max_gaps: dict[str, float] = {}
    for mint, observed in snapshot_times.items():
        assert len(observed) >= 2, (mint, observed, report)
        gaps = [
            (right - left).total_seconds()
            for left, right in zip(observed, observed[1:], strict=False)
        ]
        max_gaps[mint] = max(gaps)
        assert max_gaps[mint] <= 240.0, (mint, gaps)
    assert abs(len(snapshot_times["mint-1"]) - len(snapshot_times["mint-2"])) <= 1
    assert max_gaps == {"mint-1": 225.0, "mint-2": 225.0}
    assert quantum_calls[:7] == list(quantum_phases)
    assert len(bound_resolutions) > len(quantum_calls)
    assert all(
        later["remaining_by_stage"][stage]
        <= earlier["remaining_by_stage"][stage]
        for earlier, later in zip(stage_snapshots, stage_snapshots[1:])
        for stage in earlier["remaining_by_stage"]
    )
    assert stage_budget.used_by_stage["market_batching"] <= 2
    assert stage_budget.used_by_stage["reconciliation"] <= 6
    assert stage_budget.used_by_stage["protocol_confirmation"] <= 7
    connection = sqlite3.connect(db)
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_scheduler_jobs "
        "WHERE job_kind='PRE_ADMISSION_DISCOVERY_SELECTION'"
    ).fetchone()[0] == 1
    connection.close()

def test_spacing_hold_allows_cycle2_acquisition_without_early_admission(
    tmp_path,
) -> None:
    db, _backup, _disposable_binding = _prepare(tmp_path)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    callback_calls = 0
    admission_calls = 0
    now = START + timedelta(seconds=60)

    def callback(**_kwargs):
        nonlocal callback_calls
        callback_calls += 1
        return SimpleNamespace(
            attempt_id="early-attempt",
            state="RUNNING",
            first_terminal_cause="",
        )

    def forbidden_admit(**_kwargs):
        nonlocal admission_calls
        admission_calls += 1
        raise AssertionError("Cycle 2 cannot admit before the 300s spacing boundary")

    try:
        result = factory._run_four_token_admission_boundary(
            connection=connection,
            controller=_SpacingController(),
            binding=MultiCycleCampaignBinding(
                campaign_id=CAMPAIGN_ID,
                campaign_run_id=CAMPAIGN_RUN_ID,
                configuration_id=CONFIGURATION_ID,
                authoritative_factory_run_id=FACTORY_RUN_ID,
            ),
            first_cycle_id=CYCLE_ID,
            now=now,
            next_due_work_at=None,
            proof_deadline=START + timedelta(hours=5),
            project_health=_healthy_projection,
            evaluate=lambda _projection: FourTokenAdmissionDisposition(
                FourTokenAdmissionDispositionKind.REARM,
                "PERSISTED_ADMISSION_SPACING_BOUNDARY",
                START + timedelta(seconds=300),
                False,
            ),
            later_cycle_callback=callback,
            admit=forbidden_admit,
            materialize=lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("early Cycle-2 acquisition cannot materialize")
            ),
            plan_opening=lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("early Cycle-2 acquisition cannot plan lifecycle")
            ),
            admission_deadline_seconds_after_first_cycle=600,
        )
        assert callback_calls == 1
        assert admission_calls == 0
        assert result.admitted is False
        assert result.attempt_state == "RUNNING"
        assert (
            result.disposition.kind
            is FourTokenAdmissionDispositionKind.REARM
        )
    finally:
        connection.close()

def test_spacing_hold_does_not_bypass_source_or_capacity_health(
    tmp_path,
) -> None:
    db, _backup, _disposable_binding = _prepare(tmp_path)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    callback_calls = 0
    now = START + timedelta(seconds=60)

    unhealthy = AdmissionHealthProjection(
        health=MultiCycleAdmissionHealth(
            source_budget_available=False,
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
        ),
        recheck_at=None,
        recheck_on_lifecycle_change=False,
        evidence=(),
        reasons=("source_budget_unavailable",),
    )

    def forbidden_callback(**_kwargs):
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("spacing hold must not bypass source budget health")

    try:
        result = factory._run_four_token_admission_boundary(
            connection=connection,
            controller=_SpacingController(),
            binding=MultiCycleCampaignBinding(
                campaign_id=CAMPAIGN_ID,
                campaign_run_id=CAMPAIGN_RUN_ID,
                configuration_id=CONFIGURATION_ID,
                authoritative_factory_run_id=FACTORY_RUN_ID,
            ),
            first_cycle_id=CYCLE_ID,
            now=now,
            next_due_work_at=None,
            proof_deadline=START + timedelta(hours=5),
            project_health=lambda: unhealthy,
            evaluate=lambda _projection: FourTokenAdmissionDisposition(
                FourTokenAdmissionDispositionKind.REARM,
                "PERSISTED_ADMISSION_SPACING_BOUNDARY",
                START + timedelta(seconds=300),
                False,
            ),
            later_cycle_callback=forbidden_callback,
            admit=lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("unhealthy spacing hold cannot admit")
            ),
            materialize=lambda **_kwargs: None,
            plan_opening=lambda **_kwargs: None,
        )
        assert callback_calls == 0
        assert result.admitted is False
        assert result.attempt_id is None
        assert (
            result.disposition.kind
            is FourTokenAdmissionDispositionKind.REARM
        )
    finally:
        connection.close()

def test_cycle2_deadline_terminalizes_without_starting_unsafe_quantum(
    tmp_path,
) -> None:
    db, _backup, _disposable_binding = _prepare(tmp_path)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at"
        ") VALUES (?,?,?,?,?,?,?)",
        (
            FACTORY_RUN_ID,
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "c" * 64,
            "{}",
            START.isoformat(),
        ),
    )
    connection.execute(
        "UPDATE printer_memory_factory_campaign_runs SET authoritative_run_id=? "
        "WHERE run_id=? AND campaign_id=?",
        (FACTORY_RUN_ID, CAMPAIGN_RUN_ID, CAMPAIGN_ID),
    )
    connection.commit()
    callback_calls = 0
    now = START + timedelta(seconds=590)

    def forbidden_callback(**_kwargs):
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("quantum crossing +10m deadline must not start")

    try:
        result = factory._run_four_token_admission_boundary(
            connection=connection,
            controller=_CadenceReadyController(),
            binding=MultiCycleCampaignBinding(
                campaign_id=CAMPAIGN_ID,
                campaign_run_id=CAMPAIGN_RUN_ID,
                configuration_id=CONFIGURATION_ID,
                authoritative_factory_run_id=FACTORY_RUN_ID,
            ),
            first_cycle_id=CYCLE_ID,
            now=now,
            next_due_work_at=None,
            proof_deadline=START + timedelta(hours=5),
            project_health=_healthy_projection,
            evaluate=lambda _projection: FourTokenAdmissionDisposition(
                FourTokenAdmissionDispositionKind.CYCLE_ADMISSION,
                "ADMISSION_READY",
                now,
                True,
            ),
            later_cycle_callback=forbidden_callback,
            admit=lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("deadline-terminal Cycle 2 cannot admit")
            ),
            materialize=lambda **_kwargs: None,
            plan_opening=lambda **_kwargs: None,
            acquisition_quantum_worst_case_seconds=18.0,
            admission_deadline_seconds_after_first_cycle=600,
        )
        assert callback_calls == 0
        assert result.admitted is False
        assert result.attempt_state == "BLOCKED"
        assert (
            result.attempt_terminal_cause
            == factory.LATER_CYCLE_ADMISSION_DEADLINE_EXHAUSTED
        )
        assert result.attempt_acquisition_deadline_at == START + timedelta(seconds=600)
        row = connection.execute(
            "SELECT attempt_state,first_terminal_cause FROM "
            "printer_pre_admission_discovery_attempts"
        ).fetchone()
        assert tuple(row) == (
            "BLOCKED",
            factory.LATER_CYCLE_ADMISSION_DEADLINE_EXHAUSTED,
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles "
            "WHERE cycle_ordinal=2"
        ).fetchone()[0] == 0
    finally:
        connection.close()

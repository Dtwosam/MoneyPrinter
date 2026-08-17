from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import shutil
import sqlite3

from printer_v1.db import apply_migrations
from printer_v1.db.migrate import canonical_migration_count, canonical_migration_names
from printer_v1.operator_cli.authoritative_admission_health import (
    AdmissionHealthProjection,
)
from printer_v1.operator_cli.campaign_ownership import create_cycle_with_two_slots
from printer_v1.operator_cli.four_token_proof_integration import (
    FourTokenControllerReadiness,
    build_four_token_proof_policy,
    next_four_token_factory_wake,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
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
from printer_v1.discovery.eligible_token_supply import ACQUISITION_QUANTUM_YIELDED
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


def _slot(row_id: int, ordinal: int) -> dict[str, object]:
    return {
        "token_slot_id": f"t{ordinal}_c0001_slot",
        "slot_ordinal": ordinal,
        "token_identity": f"solana-mainnet:mint-{row_id}",
        "token_row_id": row_id,
        "mint_identity": f"mint-{row_id}",
        "pair_identity": f"pool-{row_id}",
        "pair_row_id": 100 + row_id,
        "lifecycle_identity": "PUMPSWAP_GRADUATED_CONFIRMED",
        "tracking_queue_id": None,
        "replacement_predecessor_slot_id": None,
    }


def _prepare(tmp_path):
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
    create_cycle_with_two_slots(
        connection,
        campaign_id=CAMPAIGN_ID,
        run_id=CAMPAIGN_RUN_ID,
        cycle_id=CYCLE_ID,
        cycle_ordinal=1,
        slots=(_slot(1, 1), _slot(2, 2)),
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
    quantum_bounds = (25.0, 115.0, 65.0, 65.0, 65.0)
    quantum_calls: list[float] = []

    def supply(**_context):
        bound = quantum_bounds[min(len(quantum_calls), len(quantum_bounds) - 1)]
        quantum_calls.append(bound)
        clock.sleep(bound)
        return LaterCycleCandidateSupply(
            (),
            (),
            ACQUISITION_QUANTUM_YIELDED,
            {
                "stage_local_source_requests": len(quantum_calls),
                "provider_failures": 0,
                "shortage_classification": None,
            },
        )

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
        later_cycle_acquisition_quantum_seconds=lambda: quantum_bounds[
            min(len(quantum_calls), len(quantum_bounds) - 1)
        ],
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
            "FOCUSED_CADENCE_COMPLETE" if clock.elapsed >= 620 else None
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
    assert max_gaps == {"mint-1": 225.0, "mint-2": 225.0}
    assert abs(len(snapshot_times["mint-1"]) - len(snapshot_times["mint-2"])) <= 1
    connection = sqlite3.connect(db)
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_scheduler_jobs "
        "WHERE job_kind='PRE_ADMISSION_DISCOVERY_SELECTION'"
    ).fetchone()[0] == 1
    connection.close()

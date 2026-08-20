from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3
from types import SimpleNamespace

import pytest

from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    SOURCE_GOVERNOR_OWNER,
    OwnerPort,
)
from printer_v1.operator_cli.campaign_ownership import create_cycle_with_two_slots
from printer_v1.operator_cli.unified_terminal_closure import reconcile_campaign_terminal
from printer_v1.sources.governed_execution import (
    FIXTURE_FAILURE,
    build_fixture_source_adapter,
)
from tests.test_v2_9_8b_four_token_factory_terminal_integration import (
    _ReadyController,
)
from tests.test_v2_9_8b_four_token_factory_wake_ordering import (
    CAMPAIGN_ID,
    CAMPAIGN_RUN_ID,
    CONFIGURATION_ID,
    CYCLE_ID,
    FACTORY_RUN_ID,
    START,
    _healthy_projection,
    _prepare,
    _slot,
)


CYCLE2_ID = f"{CYCLE_ID}-2"
CYCLE2_LOCAL_CAUSE = (
    "CYCLE2_MATERIALIZATION_FAILED_UNSUPPORTED_MERGED_CANDIDATE_CHANNEL"
)


def _candidate(authority: str, channels: set[str]):
    return SimpleNamespace(
        admission_authority=SimpleNamespace(value=authority),
        channels=frozenset(channels),
    )


def test_market_present_dexscreener_freezes_canonical_channel():
    from printer_v1.operator_cli.authoritative_live_operational_campaign import (
        _canonical_pre_admission_channel_labels,
    )
    assert _canonical_pre_admission_channel_labels(
        _candidate("MARKET_PRESENT_POOL", {"dexscreener"})
    ) == ("FRESH_AGGREGATOR_PROTOCOL_CONFIRMED",)


def test_market_present_geckoterminal_freezes_canonical_channel():
    from printer_v1.operator_cli.authoritative_live_operational_campaign import (
        _canonical_pre_admission_channel_labels,
    )
    assert _canonical_pre_admission_channel_labels(
        _candidate("MARKET_PRESENT_POOL", {"geckoterminal"})
    ) == ("FRESH_AGGREGATOR_PROTOCOL_CONFIRMED",)


def test_direct_pump_preserves_existing_canonical_channels():
    from printer_v1.operator_cli.authoritative_live_operational_campaign import (
        _canonical_pre_admission_channel_labels,
    )
    assert _canonical_pre_admission_channel_labels(
        _candidate("DIRECT_PUMP_PUMPSWAP", {"ACTIVE_PUMPFUN", "LATEST_PUMPFUN"})
    ) == ("ACTIVE_PUMPFUN", "LATEST_PUMPFUN")


def test_materialization_error_exposes_bounded_typed_reason():
    from printer_v1.discovery.pre_admission_materialization import (
        PreAdmissionMaterializationError,
    )
    exc = PreAdmissionMaterializationError(
        "MATERIALIZATION_PERSISTENCE_FAILED",
        persistence_reason="UNSUPPORTED_MERGED_CANDIDATE_CHANNEL",
    )
    assert exc.code == "MATERIALIZATION_PERSISTENCE_FAILED"
    assert exc.persistence_reason == "UNSUPPORTED_MERGED_CANDIDATE_CHANNEL"
    assert str(exc) == (
        "MATERIALIZATION_PERSISTENCE_FAILED:"
        "UNSUPPORTED_MERGED_CANDIDATE_CHANNEL"
    )


def test_discovery_persistence_unsupported_channel_maps_to_typed_reason():
    """D2 direct mapping: unsupported channel label -> typed persistence_reason."""
    from printer_v1.discovery.persistence import DiscoveryPersistenceError
    from printer_v1.discovery.pre_admission_materialization import (
        PreAdmissionMaterializationError,
        _safe_persistence_reason,
    )

    source = DiscoveryPersistenceError("unsupported channel label: dexscreener")
    persistence_reason = _safe_persistence_reason(source)
    wrapped = PreAdmissionMaterializationError(
        "MATERIALIZATION_PERSISTENCE_FAILED",
        persistence_reason=persistence_reason,
    )
    assert wrapped.code == "MATERIALIZATION_PERSISTENCE_FAILED"
    assert wrapped.persistence_reason == "UNSUPPORTED_MERGED_CANDIDATE_CHANNEL"
    assert persistence_reason == "UNSUPPORTED_MERGED_CANDIDATE_CHANNEL"


def test_sqlite_error_maps_to_unclassified_persistence_reason():
    """Unclassified SQLite failures stay outside the cycle-local allow-list."""
    from printer_v1.discovery.pre_admission_materialization import (
        _safe_persistence_reason,
    )

    assert _safe_persistence_reason(sqlite3.Error("disk I/O error")) == (
        "SQLITE_PERSISTENCE_ERROR"
    )


def _cycle_db():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE printer_memory_factory_campaign_cycles(
            cycle_id TEXT PRIMARY KEY,
            cycle_state TEXT NOT NULL,
            first_terminal_cause TEXT,
            terminal_at TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE printer_memory_factory_campaign_token_slots(
            token_slot_id TEXT PRIMARY KEY,
            cycle_id TEXT NOT NULL,
            slot_ordinal INTEGER NOT NULL,
            token_state TEXT NOT NULL,
            tracking_queue_id INTEGER,
            first_terminal_cause TEXT,
            terminal_at TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE printer_memory_factory_campaign_windows(
            window_id TEXT PRIMARY KEY,
            cycle_id TEXT NOT NULL
        );
        CREATE TABLE printer_memory_factory_campaign_scheduler_work(
            scheduler_work_id TEXT PRIMARY KEY,
            cycle_id TEXT NOT NULL
        );
        INSERT INTO printer_memory_factory_campaign_cycles
        VALUES ('cycle-2','PLANNED',NULL,NULL,'2026-08-20T00:00:00+00:00');
        INSERT INTO printer_memory_factory_campaign_token_slots
        VALUES
          ('slot-1','cycle-2',1,'SELECTED',NULL,NULL,NULL,'2026-08-20T00:00:00+00:00'),
          ('slot-2','cycle-2',2,'SELECTED',NULL,NULL,NULL,'2026-08-20T00:00:00+00:00');
        """
    )
    con.commit()
    return con


def _boundary_inputs(con, persistence_reason):
    from printer_v1.discovery.pre_admission_materialization import (
        PreAdmissionMaterializationError,
    )
    from printer_v1.operator_cli.four_token_proof_integration import (
        FourTokenAdmissionDispositionKind,
    )
    disposition = SimpleNamespace(kind=FourTokenAdmissionDispositionKind.CYCLE_ADMISSION)
    projection = SimpleNamespace(health=SimpleNamespace())
    binding = SimpleNamespace(
        campaign_id="campaign",
        campaign_run_id="run",
        configuration_id="configuration",
        authoritative_factory_run_id="factory",
    )
    controller = SimpleNamespace(policy=SimpleNamespace())
    calls = {"opening": 0}

    def project_health():
        return projection

    def evaluate(_projection):
        return disposition

    def later_cycle_callback(**_kwargs):
        return SimpleNamespace(
            attempt_id="attempt-2",
            state="PAIR_READY",
            first_terminal_cause="EXACT_PAIR_FROZEN",
        )

    def admit(**_kwargs):
        return SimpleNamespace(mutation_performed=True, cycle_id="cycle-2")

    def materialize(**_kwargs):
        raise PreAdmissionMaterializationError(
            "MATERIALIZATION_PERSISTENCE_FAILED",
            persistence_reason=persistence_reason,
        )

    def plan_opening(**_kwargs):
        calls["opening"] += 1
        raise AssertionError("Cycle-2 opening must not run after local failure")

    return dict(
        connection=con,
        controller=controller,
        binding=binding,
        first_cycle_id="cycle",
        now=datetime(2026, 8, 20, tzinfo=timezone.utc),
        next_due_work_at=None,
        proof_deadline=datetime(2026, 8, 21, tzinfo=timezone.utc),
        project_health=project_health,
        evaluate=evaluate,
        later_cycle_callback=later_cycle_callback,
        admit=admit,
        materialize=materialize,
        plan_opening=plan_opening,
        source_governor=SimpleNamespace(),
        central_scheduler=SimpleNamespace(),
        clock=lambda: datetime(2026, 8, 20, tzinfo=timezone.utc),
        acquisition_quantum_worst_case_seconds=1.0,
    ), calls


def test_known_cycle_local_materialization_failure_isolates_cycle2():
    from printer_v1.operator_cli.one_command_15m_factory import (
        _run_four_token_admission_boundary,
    )
    con = _cycle_db()
    kwargs, calls = _boundary_inputs(con, "UNSUPPORTED_MERGED_CANDIDATE_CHANNEL")
    result = _run_four_token_admission_boundary(**kwargs)
    assert result.admitted is False
    assert result.attempt_state == "CONSUMED"
    assert result.cycle_id == "cycle-2"
    assert result.attempt_terminal_cause == (
        "CYCLE2_MATERIALIZATION_FAILED_"
        "UNSUPPORTED_MERGED_CANDIDATE_CHANNEL"
    )
    assert calls["opening"] == 0
    cycle = con.execute(
        "SELECT cycle_state,first_terminal_cause FROM "
        "printer_memory_factory_campaign_cycles WHERE cycle_id='cycle-2'"
    ).fetchone()
    assert tuple(cycle) == (
        "TERMINAL_FAILED",
        "CYCLE2_MATERIALIZATION_FAILED_UNSUPPORTED_MERGED_CANDIDATE_CHANNEL",
    )
    slots = con.execute(
        "SELECT token_state,tracking_queue_id FROM "
        "printer_memory_factory_campaign_token_slots "
        "WHERE cycle_id='cycle-2' ORDER BY slot_ordinal"
    ).fetchall()
    assert [row["token_state"] for row in slots] == ["MANUAL_REVIEW", "MANUAL_REVIEW"]
    assert [row["tracking_queue_id"] for row in slots] == [None, None]


def test_unclassified_persistence_failure_remains_global_fail_closed():
    from printer_v1.discovery.pre_admission_materialization import (
        PreAdmissionMaterializationError,
    )
    from printer_v1.operator_cli.one_command_15m_factory import (
        _run_four_token_admission_boundary,
    )
    con = _cycle_db()
    kwargs, calls = _boundary_inputs(con, "SQLITE_PERSISTENCE_ERROR")
    with pytest.raises(PreAdmissionMaterializationError) as caught:
        _run_four_token_admission_boundary(**kwargs)
    assert caught.value.persistence_reason == "SQLITE_PERSISTENCE_ERROR"
    assert calls["opening"] == 0
    assert con.execute(
        "SELECT cycle_state FROM printer_memory_factory_campaign_cycles "
        "WHERE cycle_id='cycle-2'"
    ).fetchone()[0] == "PLANNED"
    assert [
        row[0]
        for row in con.execute(
            "SELECT token_state FROM printer_memory_factory_campaign_token_slots "
            "WHERE cycle_id='cycle-2' ORDER BY slot_ordinal"
        ).fetchall()
    ] == ["SELECTED", "SELECTED"]


def _discovery(db):
    def run(_args):
        connection = sqlite3.connect(db)
        connection.execute(
            "INSERT INTO printer_selection_batches("
            "batch_id,batch_status,window_kind,candidate_pool_total,selected_count,"
            "operator_approved) VALUES "
            "('d123-drain-batch','ASSEMBLED','WINDOW_15M',2,2,1)"
        )
        for row_id in (1, 2):
            connection.execute(
                "INSERT INTO printer_selection_batch_items("
                "batch_id,item_status,token_id,pair_id,token_mint,pair_address,"
                "tracking_lane,operator_approved) VALUES "
                "('d123-drain-batch','SELECTED',?,?,?,?, 'TRACK_NORMAL',1)",
                (row_id, 100 + row_id, f"mint-{row_id}", f"pool-{row_id}"),
            )
        connection.commit()
        connection.close()
        return {
            "selection_handoff_report": {
                "batch_id": "d123-drain-batch",
                "selection_seed": "d123-drain-seed",
                "eligible_pool_size": 2,
            },
            "discovery_results": [],
        }

    return run


def _snapshot_factory(*, token_mint, timeout_seconds):
    del timeout_seconds
    pool = "pool-1" if token_mint == "mint-1" else "pool-2"
    return build_fixture_source_adapter(
        "dexscreener",
        fixture_payload={
            "pairs": [
                {
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
                }
            ]
        },
    )


def test_factory_loop_cycle2_local_failure_preserves_and_drains_cycle1(
    tmp_path, monkeypatch
) -> None:
    """D3 real factory-loop proof: Cycle-2 local fail, Cycle-1 survives/drains."""
    from printer_v1.discovery.pre_admission_materialization import (
        PreAdmissionMaterializationError,
    )
    from printer_v1.operator_cli import one_command_15m_factory as factory
    from printer_v1.operator_cli import multi_cycle_campaign_coordinator as coordinator
    from printer_v1.discovery import pre_admission_materialization as materialization

    db, backup, disposable_binding = _prepare(tmp_path)
    cycle2_id = CYCLE2_ID
    observations: dict[str, object] = {
        "mid_loop_cycle2_state": None,
        "mid_loop_cycle1_pending": None,
        "mid_loop_cycle2_opening_jobs": None,
        "mid_loop_cycle_count": None,
        "claims": [],
        "cycle2_opening_plans": 0,
        "stop_reason_while_cycle1_active": None,
    }

    class Clock:
        def __init__(self) -> None:
            self.instant = START
            self.elapsed = 0.0

        def now(self) -> datetime:
            return self.instant

        def monotonic(self) -> float:
            return self.elapsed

        def sleep(self, seconds: float) -> None:
            self.elapsed += float(seconds)
            self.instant += timedelta(seconds=float(seconds))

    clock = Clock()
    original_plan = factory._plan_opening_jobs

    def plan_future_cycle1_opening(connection, run_id, targets, now, **kwargs):
        cycle_ordinal = int(kwargs.get("cycle_ordinal") or 1)
        if cycle_ordinal != 1:
            observations["cycle2_opening_plans"] = (
                int(observations["cycle2_opening_plans"]) + 1
            )
            raise AssertionError("Cycle-2 opening must not be planned after local failure")
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

    def admit(**kwargs):
        connection = kwargs["connection"]
        for row_id in (3, 4):
            connection.execute(
                "INSERT OR IGNORE INTO printer_tokens(id,token_mint,chain) "
                "VALUES (?,?,'solana')",
                (row_id, f"mint-{row_id}"),
            )
            connection.execute(
                "INSERT OR IGNORE INTO printer_pairs("
                "id,token_id,pair_address,base_token_mint) VALUES (?,?,?,?)",
                (100 + row_id, row_id, f"pool-{row_id}", f"mint-{row_id}"),
            )
        slots = []
        for ordinal, row_id in enumerate((3, 4), start=1):
            slot = _slot(row_id, ordinal)
            slot["token_slot_id"] = f"t{ordinal}_c0002_slot"
            slots.append(slot)
        create_cycle_with_two_slots(
            connection,
            campaign_id=CAMPAIGN_ID,
            run_id=CAMPAIGN_RUN_ID,
            cycle_id=cycle2_id,
            cycle_ordinal=2,
            slots=tuple(slots),
            now=clock.now().isoformat(),
            commit_transaction=True,
        )
        return SimpleNamespace(mutation_performed=True, cycle_id=cycle2_id)

    def materialize(**_kwargs):
        raise PreAdmissionMaterializationError(
            "MATERIALIZATION_PERSISTENCE_FAILED",
            persistence_reason="UNSUPPORTED_MERGED_CANDIDATE_CHANNEL",
        )

    def observe(event: dict) -> None:
        if event.get("boundary") != "SCHEDULER_CLAIM":
            return
        connection = sqlite3.connect(db)
        connection.row_factory = sqlite3.Row
        try:
            cycle2 = connection.execute(
                "SELECT cycle_state,first_terminal_cause FROM "
                "printer_memory_factory_campaign_cycles WHERE cycle_id=?",
                (cycle2_id,),
            ).fetchone()
            pending_cycle1 = connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_run_steps s "
                "JOIN printer_scheduler_jobs j ON j.id=s.scheduler_job_id "
                "WHERE s.run_id=? AND s.step_status='PENDING' "
                "AND j.status IN ('PENDING','COOLDOWN')",
                (FACTORY_RUN_ID,),
            ).fetchone()[0]
            cycle2_opening = connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work "
                "WHERE cycle_id=?",
                (cycle2_id,),
            ).fetchone()[0]
            cycle_count = connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles "
                "WHERE campaign_id=? AND run_id=?",
                (CAMPAIGN_ID, CAMPAIGN_RUN_ID),
            ).fetchone()[0]
            claims = list(observations["claims"])
            claims.append(
                {
                    "scheduler_job_id": event.get("scheduler_job_id"),
                    "step_key": event.get("step_key"),
                    "cycle2_state": None if cycle2 is None else str(cycle2[0]),
                    "cycle2_cause": None if cycle2 is None else str(cycle2[1]),
                    "cycle1_pending_at_claim": int(pending_cycle1),
                    "cycle2_opening_jobs": int(cycle2_opening),
                    "cycle_count": int(cycle_count),
                }
            )
            observations["claims"] = claims
            if observations["mid_loop_cycle2_state"] is None:
                observations["mid_loop_cycle2_state"] = (
                    None if cycle2 is None else tuple(cycle2)
                )
                observations["mid_loop_cycle1_pending"] = int(pending_cycle1)
                observations["mid_loop_cycle2_opening_jobs"] = int(cycle2_opening)
                observations["mid_loop_cycle_count"] = int(cycle_count)
                observations["stop_reason_while_cycle1_active"] = (
                    "still_running_with_pending_or_claimed_cycle1_work"
                )
        finally:
            connection.close()

    def shared_terminalizer(*, terminal_cause, run_status):
        reconciled = reconcile_campaign_terminal(
            db,
            campaign_id=CAMPAIGN_ID,
            run_id=CAMPAIGN_RUN_ID,
            cycle_id=CYCLE_ID,
            terminal_cause=str(terminal_cause),
            run_status=run_status,
            factory_run_id=FACTORY_RUN_ID,
            lifecycle_started=True,
            now=clock.now().isoformat(),
        )
        return {**reconciled, "clean_terminal": True, "lease_released": True}

    context_factories = {
        name: (
            lambda _name=name, **_kwargs: build_fixture_source_adapter(
                _name, fixture_kind=FIXTURE_FAILURE
            )
        )
        for name in ("coingecko", "goplus", "jupiter_quote")
    } | {
        "solana_rpc_holder": lambda **_kwargs: build_fixture_source_adapter(
            "solana_rpc", fixture_kind=FIXTURE_FAILURE
        )
    }

    monkeypatch.setattr(factory, "_now", clock.now)
    monkeypatch.setattr(factory, "_plan_opening_jobs", plan_future_cycle1_opening)
    monkeypatch.setattr(factory, "_plan_anchored_jobs", lambda *args, **kwargs: None)
    monkeypatch.setattr(coordinator, "admit_two_token_cycle_from_attempt", admit)
    monkeypatch.setattr(
        materialization, "materialize_consumed_pre_admission_pair", materialize
    )

    report = factory.run_one_command_15m_factory(
        db,
        backup,
        operator_approved=True,
        proof_mode=False,
        operational_persistent_mode=True,
        disposable_public_composition_proof_binding=disposable_binding,
        discovery_runner=_discovery(db),
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
        four_token_proof_controller=_ReadyController(),
        later_cycle_discovery_callback=lambda **_: SimpleNamespace(
            attempt_id="attempt-cycle-2",
            state="PAIR_READY",
            first_terminal_cause="EXACT_PAIR_FROZEN",
        ),
        later_cycle_acquisition_quantum_seconds=60.0,
        four_token_health_projector=lambda _connection, _now: _healthy_projection(),
        four_token_shared_terminalizer=shared_terminalizer,
        source_governor_owner=OwnerPort(SOURCE_GOVERNOR_OWNER, True),
        central_scheduler_owner=OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
        snapshot_adapter_factory=_snapshot_factory,
        context_adapter_factories=context_factories,
        lifecycle_operation_observer=observe,
        _sleep=clock.sleep,
        _monotonic=clock.monotonic,
    )

    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        cycles = connection.execute(
            "SELECT cycle_ordinal,cycle_id,cycle_state,first_terminal_cause "
            "FROM printer_memory_factory_campaign_cycles "
            "WHERE campaign_id=? AND run_id=? ORDER BY cycle_ordinal",
            (CAMPAIGN_ID, CAMPAIGN_RUN_ID),
        ).fetchall()
        cycle2 = connection.execute(
            "SELECT cycle_state,first_terminal_cause FROM "
            "printer_memory_factory_campaign_cycles WHERE cycle_id=?",
            (cycle2_id,),
        ).fetchone()
        cycle2_slots = connection.execute(
            "SELECT token_state,tracking_queue_id FROM "
            "printer_memory_factory_campaign_token_slots "
            "WHERE cycle_id=? ORDER BY slot_ordinal",
            (cycle2_id,),
        ).fetchall()
        cycle2_work = connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work "
            "WHERE cycle_id=?",
            (cycle2_id,),
        ).fetchone()[0]
        cycle1_succeeded = connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND step_status='SUCCEEDED'",
            (FACTORY_RUN_ID,),
        ).fetchone()[0]
        cycle1_cancelled = connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND step_status='CANCELLED'",
            (FACTORY_RUN_ID,),
        ).fetchone()[0]
        pending_left = connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND step_status='PENDING'",
            (FACTORY_RUN_ID,),
        ).fetchone()[0]
    finally:
        connection.close()

    assert observations["cycle2_opening_plans"] == 0
    assert observations["mid_loop_cycle2_state"] == (
        "TERMINAL_FAILED",
        CYCLE2_LOCAL_CAUSE,
    )
    assert int(observations["mid_loop_cycle2_opening_jobs"]) == 0
    assert int(observations["mid_loop_cycle_count"]) == 2
    assert observations["stop_reason_while_cycle1_active"] == (
        "still_running_with_pending_or_claimed_cycle1_work"
    )
    assert len(observations["claims"]) >= 1
    assert all(
        claim["cycle2_state"] == "TERMINAL_FAILED"
        and claim["cycle2_cause"] == CYCLE2_LOCAL_CAUSE
        and claim["cycle2_opening_jobs"] == 0
        and claim["cycle_count"] == 2
        for claim in observations["claims"]
    )
    assert tuple(cycle2) == ("TERMINAL_FAILED", CYCLE2_LOCAL_CAUSE)
    assert [row["token_state"] for row in cycle2_slots] == [
        "MANUAL_REVIEW",
        "MANUAL_REVIEW",
    ]
    assert [row["tracking_queue_id"] for row in cycle2_slots] == [None, None]
    assert cycle2_work == 0
    assert len(cycles) == 2
    assert [int(row["cycle_ordinal"]) for row in cycles] == [1, 2]
    assert cycle1_succeeded >= 1
    assert cycle1_cancelled == 0
    assert pending_left == 0
    assert report["stop_reason"] == CYCLE2_LOCAL_CAUSE, json.dumps(
        {
            "report_stop_reason": report.get("stop_reason"),
            "observations": observations,
            "cycle1_succeeded": cycle1_succeeded,
        },
        sort_keys=True,
        default=str,
    )

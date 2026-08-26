from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import json
import sqlite3

import pytest

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.authoritative_admission_health import (
    AdmissionHealthProjection,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
)
from printer_v1.operator_cli.campaign_ownership import create_cycle_with_two_slots
from printer_v1.operator_cli.four_token_factory_adapter import (
    FourTokenFactoryAdapterError,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    FourTokenControllerReadiness,
    LaterCycleCandidateSupply,
    next_four_token_factory_wake,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleCampaignSnapshot,
)
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    AdmissionDecision,
    AdmissionEvaluation,
    MultiCycleSessionPhase,
    MultiCycleSessionSnapshot,
)
from printer_v1.operator_cli.unified_terminal_closure import (
    reconcile_campaign_terminal,
)
from tests.test_v2_9_8b_four_token_factory_wake_ordering import (
    CAMPAIGN_ID,
    CAMPAIGN_RUN_ID,
    CONFIGURATION_ID,
    CYCLE_ID,
    FACTORY_RUN_ID,
    POLICY,
    START,
    _healthy_projection,
    _prepare,
    _slot,
)
from tests.test_v2_9_8b_callback_consume_materialize_integration import (
    GOVERNOR,
    SCHEDULER,
)


@dataclass
class _ReadyController:
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


def _discovery(db):
    def run(_args):
        connection = sqlite3.connect(db)
        connection.execute(
            "INSERT INTO printer_selection_batches("
            "batch_id,batch_status,window_kind,candidate_pool_total,selected_count,"
            "operator_approved) VALUES "
            "('terminal-batch','ASSEMBLED','WINDOW_15M',2,2,1)"
        )
        for row_id in (1, 2):
            connection.execute(
                "INSERT INTO printer_selection_batch_items("
                "batch_id,item_status,token_id,pair_id,token_mint,pair_address,"
                "tracking_lane,operator_approved) VALUES "
                "('terminal-batch','SELECTED',?,?,?,?, 'TRACK_NORMAL',1)",
                (row_id, 100 + row_id, f"mint-{row_id}", f"pool-{row_id}"),
            )
        connection.commit()
        connection.close()
        return {
            "selection_handoff_report": {
                "batch_id": "terminal-batch",
                "selection_seed": "terminal-seed",
                "eligible_pool_size": 2,
            },
            "discovery_results": [],
        }

    return run


def _add_second_cycle(db) -> None:
    connection = sqlite3.connect(db)
    for row_id in (3, 4):
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?,'solana')",
            (row_id, f"mint-{row_id}"),
        )
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
            "VALUES (?,?,?,?)",
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
        cycle_id=f"{CYCLE_ID}-2",
        cycle_ordinal=2,
        slots=tuple(slots),
        now=(START + timedelta(seconds=300)).isoformat(),
    )
    connection.commit()
    connection.close()


@pytest.mark.parametrize("two_cycles", (True, False))
def test_real_factory_terminal_path_runs_cycle_phase_then_shared_owner_once(
    tmp_path, monkeypatch, two_cycles
) -> None:
    db, backup, disposable_binding = _prepare(tmp_path)
    if two_cycles:
        _add_second_cycle(db)
    monkeypatch.setattr(factory, "_plan_opening_jobs", lambda *args, **kwargs: None)
    shared_calls: list[str] = []

    if two_cycles:
        later_callback = lambda **_: None
    else:
        later_callback = AuthoritativeLiveOperationalCampaignOwner(
            later_cycle_candidate_supply=lambda **_: LaterCycleCandidateSupply(
                (), (), "NO_EXACT_PAIR"
            )
        )._build_later_cycle_discovery_callback(
            db_path=db, configuration_id=CONFIGURATION_ID
        )

    def shared_terminalizer(*, terminal_cause, run_status):
        shared_calls.append(str(terminal_cause))
        phase_a_connection = sqlite3.connect(db)
        phase_a_states = phase_a_connection.execute(
            "SELECT cycle_state FROM printer_memory_factory_campaign_cycles "
            "ORDER BY cycle_ordinal"
        ).fetchall()
        phase_a_connection.close()
        assert phase_a_states
        assert all(
            str(row[0]).startswith("TERMINAL_") for row in phase_a_states
        )
        reconciled = reconcile_campaign_terminal(
            db,
            campaign_id=CAMPAIGN_ID,
            run_id=CAMPAIGN_RUN_ID,
            cycle_id=CYCLE_ID,
            terminal_cause=str(terminal_cause),
            run_status=run_status,
            factory_run_id=FACTORY_RUN_ID,
            lifecycle_started=True,
            now=START.isoformat(),
        )
        return {**reconciled, "clean_terminal": True, "lease_released": True}

    run_kwargs = dict(
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
        later_cycle_discovery_callback=later_callback,
        four_token_health_projector=lambda _connection, _now: _healthy_projection(),
        four_token_shared_terminalizer=shared_terminalizer,
        source_governor_owner=GOVERNOR,
        central_scheduler_owner=SCHEDULER,
        _sleep=lambda _seconds: None,
        _monotonic=lambda: 0.0,
    )
    if two_cycles:
        # This fixture merely pre-creates Cycle 2; it never runs Cycle-2
        # lifecycle work.  A campaign completion cause must therefore not be
        # projected onto that incomplete cycle.
        with pytest.raises(
            FourTokenFactoryAdapterError,
            match="incomplete cycle cannot consume a completion stop cause",
        ):
            factory.run_one_command_15m_factory(db, backup, **run_kwargs)
        connection = sqlite3.connect(db)
        try:
            cycle_two_state = connection.execute(
                "SELECT cycle_state FROM printer_memory_factory_campaign_cycles "
                "WHERE cycle_ordinal=2"
            ).fetchone()[0]
            assert cycle_two_state != "TERMINAL_COMPLETED"
        finally:
            connection.close()
        assert shared_calls == []
        return

    report = factory.run_one_command_15m_factory(db, backup, **run_kwargs)

    connection = sqlite3.connect(db)
    states = connection.execute(
        "SELECT cycle_ordinal,cycle_state FROM printer_memory_factory_campaign_cycles "
        "ORDER BY cycle_ordinal"
    ).fetchall()
    assert [str(row[1]) for row in states] == ["TERMINAL_BLOCKED"]
    assert len(states) == 1
    assert connection.execute(
        "SELECT run_state FROM printer_memory_factory_campaign_runs"
    ).fetchone()[0] == "TERMINAL_BLOCKED"
    assert connection.execute(
        "SELECT run_status FROM printer_memory_factory_runs"
    ).fetchone()[0] == "SAFE_STOPPED"
    attempt = connection.execute(
            "SELECT attempt_state,first_terminal_cause,consumed_cycle_id "
            "FROM printer_pre_admission_discovery_attempts"
    ).fetchall()
    assert attempt == [("NO_PAIR", "NO_EXACT_PAIR", None)]
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles"
    ).fetchone()[0] == 1
    assert shared_calls == ["NO_EXACT_PAIR"]
    assert report["four_token_terminal"]["shared_cleanup_count"] == 1
    assert len(report["four_token_terminal"]["phase_a"]) == 1
    assert report["four_token_terminal"]["admitted_shape"] == (
        "ONE_CYCLE_HONEST_NO_ADMISSION"
    )
    connection.close()

from __future__ import annotations

from datetime import timedelta
import inspect
import json
import sqlite3
from types import SimpleNamespace

from printer_v1.discovery.pre_admission_materialization import (
    materialize_consumed_pre_admission_pair,
)
from printer_v1.operator_cli.authoritative_admission_health import (
    AdmissionHealthProjection,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
)
from printer_v1.operator_cli.four_token_factory_adapter import (
    build_four_token_cycle_accounting_package,
    finalize_four_token_shared_terminal,
    reconcile_four_token_cycle_terminal,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    FourTokenAdmissionDisposition,
    FourTokenAdmissionDispositionKind,
    LaterCycleCandidateSupply,
    LaterCycleSourceEvidence,
    aggregate_four_token_cycle_acceptance,
    cycle_scoped_factory_step_ids,
    next_four_token_factory_wake,
    resolve_owned_cycle_for_scheduler_job,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    admit_two_token_cycle_from_attempt,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    _authoritative_terminal_15m_closes,
    _operational_activated_token_count,
    _plan_anchored_jobs,
    _plan_opening_jobs,
    _run_four_token_admission_boundary,
    _token_request_count,
    run_one_command_15m_factory,
)
from tests.test_v2_9_8b_callback_consume_materialize_integration import (
    BINDING,
    GOVERNOR,
    HEALTH,
    NOW,
    POLICY,
    SCHEDULER,
    START,
    _candidate,
    _prepare_database,
)


def test_one_disposable_factory_graph_proves_four_token_integration(tmp_path) -> None:
    path, request_id, response_id = _prepare_database(tmp_path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "UPDATE printer_memory_factory_runs SET config_json=? WHERE run_id='factory-1'",
        (json.dumps({
            "four_token_proof": True,
            "campaign_id": BINDING.campaign_id,
            "campaign_run_id": BINDING.campaign_run_id,
            "configuration_id": BINDING.configuration_id,
        }, sort_keys=True),),
    )
    cycle_one_targets = [
        {
            "token_id": ordinal,
            "pair_id": 100 + ordinal,
            "token_mint": f"mint-{ordinal}",
            "pair_address": f"pool-{ordinal}",
            "tracking_lane": "TRACK_NORMAL",
        }
        for ordinal in (1, 2)
    ]
    _plan_opening_jobs(
        connection,
        BINDING.authoritative_factory_run_id,
        cycle_one_targets,
        START,
        cycle_ordinal=1,
        four_token_proof=True,
    )
    connection.commit()

    supply_calls = 0

    def supply(**_):
        nonlocal supply_calls
        supply_calls += 1
        return LaterCycleCandidateSupply(
            candidates=(_candidate(3, "LATEST_PUMPFUN"), _candidate(4, "TOP_PUMPFUN")),
            source_evidence=(LaterCycleSourceEvidence(
                logical_stage="ELIGIBLE_SUPPLY",
                source_request_id=request_id,
                source_response_id=response_id,
            ),),
            terminal_cause=None,
        )

    callback = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=supply
    )._build_later_cycle_discovery_callback(
        db_path=path, configuration_id=BINDING.configuration_id
    )
    health_calls: list[str] = []
    events: list[str] = []
    disposition = FourTokenAdmissionDisposition(
        FourTokenAdmissionDispositionKind.CYCLE_ADMISSION,
        "ADMISSION_READY",
        NOW,
        True,
    )

    def project() -> AdmissionHealthProjection:
        health_calls.append("health")
        return AdmissionHealthProjection(HEALTH, None, False, (), ())

    def plan_cycle_two(*, cycle_id: str, cycle_ordinal: int, now) -> None:
        events.append("plan")
        targets = [dict(row) for row in connection.execute(
            "SELECT s.token_row_id AS token_id,s.pair_row_id AS pair_id,"
            "s.mint_identity AS token_mint,s.pair_identity AS pair_address,"
            "'TRACK_NORMAL' AS tracking_lane "
            "FROM printer_memory_factory_campaign_token_slots AS s "
            "WHERE s.cycle_id=? ORDER BY s.slot_ordinal",
            (cycle_id,),
        ).fetchall()]
        _plan_opening_jobs(
            connection,
            BINDING.authoritative_factory_run_id,
            targets,
            now,
            cycle_ordinal=cycle_ordinal,
            four_token_proof=True,
        )

    def materialize(**kwargs):
        events.append("materialize")
        return materialize_consumed_pre_admission_pair(**kwargs)

    def admit(**kwargs):
        events.append("admit")
        return admit_two_token_cycle_from_attempt(**kwargs)

    source_rows_before = int(connection.execute(
        "SELECT COUNT(*) FROM printer_source_requests"
    ).fetchone()[0])
    result = _run_four_token_admission_boundary(
        connection=connection,
        controller=SimpleNamespace(policy=POLICY),
        binding=BINDING,
        first_cycle_id="cycle-1",
        now=NOW,
        next_due_work_at=None,
        proof_deadline=START + timedelta(hours=5),
        project_health=project,
        evaluate=lambda projection: disposition,
        later_cycle_callback=callback,
        admit=admit,
        materialize=materialize,
        plan_opening=plan_cycle_two,
        source_governor=GOVERNOR,
        central_scheduler=SCHEDULER,
    )
    assert result.admitted is True
    assert health_calls == ["health", "health"]
    assert events == ["admit", "materialize", "plan"]
    assert supply_calls == 1
    assert (NOW - START).total_seconds() == 300
    assert int(connection.execute(
        "SELECT COUNT(*) FROM printer_source_requests"
    ).fetchone()[0]) == source_rows_before
    assert tuple(connection.execute(
        "SELECT COUNT(*),COUNT(DISTINCT token_row_id),COUNT(DISTINCT pair_row_id) "
        "FROM printer_memory_factory_campaign_token_slots"
    ).fetchone()) == (4, 4, 4)

    wake = next_four_token_factory_wake(
        now=NOW,
        next_due_work_at=NOW,
        next_admission_at=NOW,
        proof_deadline=START + timedelta(hours=5),
    )
    assert wake.reason == "LIFECYCLE_WORK"

    for opening in connection.execute(
        "SELECT * FROM printer_memory_factory_run_steps "
        "WHERE run_id='factory-1' AND step_key LIKE '%snapshot_00' ORDER BY id"
    ).fetchall():
        _plan_anchored_jobs(
            connection,
            run_id="factory-1",
            opening_step=opening,
            first_snapshot_captured_at=NOW.isoformat(),
            window_seconds=900.0,
        )

    cycle_steps: dict[str, tuple[int, ...]] = {}
    for cycle in ("cycle-1", "cycle-1-2"):
        ids = cycle_scoped_factory_step_ids(
            connection,
            campaign_id=BINDING.campaign_id,
            campaign_run_id=BINDING.campaign_run_id,
            factory_run_id=BINDING.authoritative_factory_run_id,
            cycle_id=cycle,
        )
        assert ids
        cycle_steps[cycle] = ids
        assert _operational_activated_token_count(
            connection, BINDING.authoritative_factory_run_id, cycle_id=cycle
        ) == 2
        assert _authoritative_terminal_15m_closes(
            connection, BINDING.authoritative_factory_run_id, cycle_id=cycle
        ) == []
        for step_id in ids:
            job_id = int(connection.execute(
                "SELECT scheduler_job_id FROM printer_memory_factory_run_steps WHERE id=?",
                (step_id,),
            ).fetchone()[0])
            owner = resolve_owned_cycle_for_scheduler_job(
                connection,
                scheduler_job_id=job_id,
                campaign_id=BINDING.campaign_id,
                campaign_run_id=BINDING.campaign_run_id,
                factory_run_id=BINDING.authoritative_factory_run_id,
            )
            assert owner.cycle_id == cycle
    assert set(cycle_steps["cycle-1"]).isdisjoint(cycle_steps["cycle-1-2"])
    assert all(not str(row[0]).startswith(("t1_c0001_", "t2_c0001_")) for row in connection.execute(
        "SELECT step_key FROM printer_memory_factory_run_steps WHERE id IN (%s)"
        % ",".join("?" for _ in cycle_steps["cycle-1"]),
        cycle_steps["cycle-1"],
    ))
    assert all("_c0002_" in str(row[0]) for row in connection.execute(
        "SELECT step_key FROM printer_memory_factory_run_steps WHERE id IN (%s)"
        % ",".join("?" for _ in cycle_steps["cycle-1-2"]),
        cycle_steps["cycle-1-2"],
    ))

    for request_key in (
        "factory-1:t1_snapshot_00:proof",
        "factory-1:t1_c0002_snapshot_00:proof",
    ):
        connection.execute(
            "INSERT INTO printer_source_requests("
            "source_name,request_kind,requested_at,request_key,source_status,data_quality_label) "
            "VALUES ('dexscreener','pair',?,?, 'COMPLETE','CLEAN_DATA')",
            (NOW.isoformat(), request_key),
        )
    assert _token_request_count(connection, "factory-1", "t1") == 1
    assert _token_request_count(connection, "factory-1", "t1_c0002") == 1

    packages = [
        build_four_token_cycle_accounting_package(
            connection,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            cycle_id=cycle,
        )
        for cycle in ("cycle-1", "cycle-1-2")
    ]
    aggregate = aggregate_four_token_cycle_acceptance(
        packages,
        shared={
            "campaign_id": "campaign-1",
            "campaign_run_id": "campaign-run-1",
            "factory_run_id": "factory-1",
            "admission_spacing_seconds": 300,
            "active_through_4h_peak": 4,
            "aggregate_budget_within_ceiling": True,
            "zero_active_work": True,
            "zero_forbidden_deltas": True,
            "restart_created": False,
            "successor_created": False,
            "long_windows_activated": False,
        },
    )
    assert aggregate["accounting_package_count"] == 2
    connection.commit()

    for cycle in ("cycle-1", "cycle-1-2"):
        reconcile_four_token_cycle_terminal(
            connection,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            cycle_id=cycle,
            cause="COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
            run_status="COMPLETED",
            now=NOW,
        )
    cleanup_calls: list[str] = []

    def shared_terminalizer():
        cleanup_calls.append("cleanup")
        connection.execute(
            "UPDATE printer_memory_factory_campaign_runs SET "
            "run_state='TERMINAL_COMPLETED',first_terminal_cause=?,terminal_at=?,updated_at=? "
            "WHERE run_id='campaign-run-1'",
            ("COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED", NOW.isoformat(), NOW.isoformat()),
        )
        connection.execute(
            "UPDATE printer_memory_factory_campaigns SET "
            "campaign_state='TERMINAL_COMPLETED',first_terminal_cause=?,terminal_at=?,updated_at=? "
            "WHERE campaign_id='campaign-1'",
            ("COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED", NOW.isoformat(), NOW.isoformat()),
        )
        connection.execute(
            "UPDATE printer_memory_factory_runs SET run_status='COMPLETED',"
            "finished_at=?,updated_at=? WHERE run_id='factory-1'",
            (NOW.isoformat(), NOW.isoformat()),
        )
        connection.commit()
        return {"clean_terminal": True, "lease_released": True}

    terminal = finalize_four_token_shared_terminal(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        shared_terminalizer=shared_terminalizer,
    )
    assert terminal["shared_cleanup_count"] == 1
    assert cleanup_calls == ["cleanup"]
    assert inspect.signature(run_one_command_15m_factory).parameters[
        "four_token_proof_controller"
    ].default is None
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts"
    ).fetchone()[0] == 1
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles"
    ).fetchone()[0] == 2
    connection.close()

"""Bounded offline proof of the OPERATIONAL four-token 4/2/2 command boundary.

This is the implementation-lane bounded proof required before any host-local
authorization preparation. It is strictly offline and disposable:

* disposable temporary SQLite database, never the authoritative campaign DB;
* deterministic frozen time (no wall clock drives any decision);
* fake/frozen candidate supply (no provider, no RPC, no WebSocket, no network);
* no authorization is created or consumed and no Printer process is started.

It proves the NEW operational command boundary rather than the proof-only one:
capacity, controller and admission all come from the operational authority.
"""

from __future__ import annotations

from datetime import timedelta
import json
import sqlite3
from types import SimpleNamespace

from printer_v1.discovery.pre_admission_materialization import (
    materialize_consumed_pre_admission_pair,
)
from printer_v1.operator_cli import four_token_operational_composition as operational
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli.authoritative_admission_health import (
    AdmissionHealthProjection,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
)
from printer_v1.operator_cli.four_token_factory_adapter import (
    finalize_four_token_shared_terminal,
    reconcile_four_token_cycle_terminal,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    FourTokenAdmissionDisposition,
    FourTokenAdmissionDispositionKind,
    LaterCycleCandidateSupply,
    LaterCycleSourceEvidence,
    cycle_scoped_factory_step_ids,
    resolve_owned_cycle_for_scheduler_job,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    admit_two_token_cycle_from_attempt,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    _operational_activated_token_count,
    _plan_anchored_jobs,
    _plan_opening_jobs,
    _run_four_token_admission_boundary,
)
from tests.test_v2_9_8b_callback_consume_materialize_integration import (
    BINDING,
    GOVERNOR,
    HEALTH,
    NOW,
    SCHEDULER,
    START,
    _candidate,
    _prepare_database,
)


def test_one_operational_invocation_proves_four_two_two(tmp_path) -> None:
    # --- exact derived operational capacity, before any state exists ---------
    policy = operational.exact_operational_policy()
    capacity = operational.OPERATIONAL_CAPACITY
    assert policy["configured_through_4h_tokens"] == 4
    assert policy["configured_active_cycles"] == 2
    assert policy["tokens_per_cycle"] == 2
    assert policy["total_cycle_admission_ceiling"] == 2
    assert policy["lifecycle_requests_per_token"] == int(
        capacity["lifecycle_requests_per_token"]
    )
    assert policy["lifecycle_request_outer_ceiling"] == int(
        capacity["lifecycle_request_outer_ceiling"]
    )
    assert policy["lifecycle_scheduler_outer_ceiling"] == int(
        capacity["lifecycle_scheduler_outer_ceiling"]
    )
    assert policy["automatic_retries"] == 0
    assert policy["endpoint_rotation"] is False
    assert policy["long_windows_activated"] is False
    assert policy["locked_windows"] == ["WINDOW_12H", "WINDOW_24H"]

    controller = operational.build_operational_multi_cycle_controller()
    assert controller.policy.configured_through_4h_token_ceiling == 4
    assert controller.policy.configured_active_cycle_ceiling == 2
    assert controller.policy.total_cycle_admission_ceiling == 2

    # --- disposable graph ---------------------------------------------------
    path, request_id, response_id = _prepare_database(tmp_path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "UPDATE printer_memory_factory_runs SET config_json=? WHERE run_id='factory-1'",
        (
            json.dumps(
                {
                    "four_token_proof": True,
                    "campaign_id": BINDING.campaign_id,
                    "campaign_run_id": BINDING.campaign_run_id,
                    "configuration_id": BINDING.configuration_id,
                },
                sort_keys=True,
            ),
        ),
    )

    # --- Cycle 1: exactly two fresh slots -----------------------------------
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
    assert tuple(
        connection.execute(
            "SELECT COUNT(*),COUNT(DISTINCT token_row_id),COUNT(DISTINCT pair_row_id) "
            "FROM printer_memory_factory_campaign_token_slots"
        ).fetchone()
    ) == (2, 2, 2)

    # --- Cycle 2: fresh governed later-cycle supply, never carry-forward -----
    supply_calls = 0

    def frozen_supply(**_kwargs):
        """Fake/frozen later-cycle supply. No provider, RPC or WebSocket."""
        nonlocal supply_calls
        supply_calls += 1
        return LaterCycleCandidateSupply(
            candidates=(
                _candidate(3, "LATEST_PUMPFUN"),
                _candidate(4, "TOP_PUMPFUN"),
            ),
            source_evidence=(
                LaterCycleSourceEvidence(
                    logical_stage="ELIGIBLE_SUPPLY",
                    source_request_id=request_id,
                    source_response_id=response_id,
                ),
            ),
            terminal_cause=None,
        )

    callback = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=frozen_supply
    )._build_later_cycle_discovery_callback(
        db_path=path, configuration_id=BINDING.configuration_id
    )
    ordered_events: list[str] = []

    def plan_cycle_two(*, cycle_id: str, cycle_ordinal: int, now) -> None:
        ordered_events.append("plan")
        targets = [
            dict(row)
            for row in connection.execute(
                "SELECT s.token_row_id AS token_id,s.pair_row_id AS pair_id,"
                "s.mint_identity AS token_mint,s.pair_identity AS pair_address,"
                "'TRACK_NORMAL' AS tracking_lane "
                "FROM printer_memory_factory_campaign_token_slots AS s "
                "WHERE s.cycle_id=? ORDER BY s.slot_ordinal",
                (cycle_id,),
            ).fetchall()
        ]
        _plan_opening_jobs(
            connection,
            BINDING.authoritative_factory_run_id,
            targets,
            now,
            cycle_ordinal=cycle_ordinal,
            four_token_proof=True,
        )

    def materialize(**kwargs):
        ordered_events.append("materialize")
        return materialize_consumed_pre_admission_pair(**kwargs)

    def admit(**kwargs):
        ordered_events.append("admit")
        return admit_two_token_cycle_from_attempt(**kwargs)

    source_rows_before = int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_source_requests"
        ).fetchone()[0]
    )
    deadline = START + timedelta(
        seconds=operational.POST_SUPPLY_LIFECYCLE_DURATION_SECONDS
    )
    result = _run_four_token_admission_boundary(
        connection=connection,
        controller=SimpleNamespace(policy=controller.policy),
        binding=BINDING,
        first_cycle_id="cycle-1",
        now=NOW,
        next_due_work_at=None,
        proof_deadline=deadline,
        project_health=lambda: AdmissionHealthProjection(HEALTH, None, False, (), ()),
        evaluate=lambda projection: FourTokenAdmissionDisposition(
            FourTokenAdmissionDispositionKind.CYCLE_ADMISSION,
            "ADMISSION_READY",
            NOW,
            True,
        ),
        later_cycle_callback=callback,
        admit=admit,
        materialize=materialize,
        plan_opening=plan_cycle_two,
        source_governor=GOVERNOR,
        central_scheduler=SCHEDULER,
    )

    # One same-invocation admission, not a successor campaign.
    assert result.admitted is True
    assert supply_calls == 1
    assert ordered_events == ["admit", "materialize", "plan"]
    # Lawful minimum admission spacing was honoured with deterministic time.
    assert (NOW - START).total_seconds() == (
        operational.MINIMUM_CYCLE_ADMISSION_SPACING_SECONDS
    )
    # No live source call happened anywhere in this proof.
    assert int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_source_requests"
        ).fetchone()[0]
    ) == source_rows_before

    # --- exactly 4 distinct slots / 2 cycles / 2 per cycle -------------------
    assert tuple(
        connection.execute(
            "SELECT COUNT(*),COUNT(DISTINCT token_row_id),COUNT(DISTINCT pair_row_id),"
            "COUNT(DISTINCT mint_identity),COUNT(DISTINCT pair_identity) "
            "FROM printer_memory_factory_campaign_token_slots"
        ).fetchone()
    ) == (4, 4, 4, 4, 4)
    assert int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles"
        ).fetchone()[0]
    ) == 2
    for cycle in ("cycle-1", "cycle-1-2"):
        assert int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots "
                "WHERE cycle_id=?",
                (cycle,),
            ).fetchone()[0]
        ) == 2

    # --- anchor the 15m lifecycle for both cycles (deterministic time) ------
    for opening in connection.execute(
        "SELECT * FROM printer_memory_factory_run_steps "
        "WHERE run_id='factory-1' AND step_key LIKE '%snapshot_00' ORDER BY id"
    ).fetchall():
        _plan_anchored_jobs(
            connection,
            run_id=BINDING.authoritative_factory_run_id,
            opening_step=opening,
            first_snapshot_captured_at=NOW.isoformat(),
            window_seconds=900.0,
        )

    # --- per-cycle lifecycle / Scheduler ownership stays exact ---------------
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
        assert (
            _operational_activated_token_count(
                connection, BINDING.authoritative_factory_run_id, cycle_id=cycle
            )
            == 2
        )
        for step_id in ids:
            job_id = int(
                connection.execute(
                    "SELECT scheduler_job_id FROM printer_memory_factory_run_steps "
                    "WHERE id=?",
                    (step_id,),
                ).fetchone()[0]
            )
            owner = resolve_owned_cycle_for_scheduler_job(
                connection,
                scheduler_job_id=job_id,
                campaign_id=BINDING.campaign_id,
                campaign_run_id=BINDING.campaign_run_id,
                factory_run_id=BINDING.authoritative_factory_run_id,
            )
            assert owner.cycle_id == cycle
    assert set(cycle_steps["cycle-1"]).isdisjoint(cycle_steps["cycle-1-2"])

    # --- no 12h/24h planning anywhere ---------------------------------------
    long_window_steps = int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
            "WHERE step_key LIKE '%12h%' OR step_key LIKE '%24h%'"
        ).fetchone()[0]
    )
    assert long_window_steps == 0

    # --- one terminal closure, no successor / retry -------------------------
    connection.commit()
    for cycle in ("cycle-1", "cycle-1-2"):
        reconcile_four_token_cycle_terminal(
            connection,
            campaign_id=BINDING.campaign_id,
            campaign_run_id=BINDING.campaign_run_id,
            factory_run_id=BINDING.authoritative_factory_run_id,
            cycle_id=cycle,
            cause="COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
            run_status="COMPLETED",
            now=NOW,
        )
    cleanup_calls: list[str] = []

    def shared_terminalizer():
        cleanup_calls.append("cleanup")
        stamp = NOW.isoformat()
        connection.execute(
            "UPDATE printer_memory_factory_campaign_runs SET "
            "run_state='TERMINAL_COMPLETED',first_terminal_cause=?,terminal_at=?,"
            "updated_at=? WHERE run_id=?",
            (
                "COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
                stamp,
                stamp,
                BINDING.campaign_run_id,
            ),
        )
        connection.execute(
            "UPDATE printer_memory_factory_campaigns SET "
            "campaign_state='TERMINAL_COMPLETED',first_terminal_cause=?,terminal_at=?,"
            "updated_at=? WHERE campaign_id=?",
            (
                "COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
                stamp,
                stamp,
                BINDING.campaign_id,
            ),
        )
        connection.execute(
            "UPDATE printer_memory_factory_runs SET run_status='COMPLETED',"
            "finished_at=?,updated_at=? WHERE run_id=?",
            (stamp, stamp, BINDING.authoritative_factory_run_id),
        )
        connection.commit()
        return {"clean_terminal": True, "lease_released": True}

    terminal = finalize_four_token_shared_terminal(
        connection,
        campaign_id=BINDING.campaign_id,
        campaign_run_id=BINDING.campaign_run_id,
        factory_run_id=BINDING.authoritative_factory_run_id,
        shared_terminalizer=shared_terminalizer,
    )
    assert terminal["shared_cleanup_count"] == 1
    assert cleanup_calls == ["cleanup"]

    # A terminal campaign spawns nothing: no third cycle, no successor run.
    assert int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles"
        ).fetchone()[0]
    ) == 2
    assert int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_runs"
        ).fetchone()[0]
    ) == 1
    assert int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_runs "
            "WHERE run_state NOT LIKE 'TERMINAL_%'"
        ).fetchone()[0]
    ) == 0

    # --- the operational command policy matches this proven envelope --------
    campaign_policy = command.FOUR_TOKEN_STANDARD_FOUR_HOUR_POLICY
    assert campaign_policy.mode == "four-token-standard-four-hour-run"
    assert campaign_policy.governed_request_ceiling == int(
        capacity["lifecycle_request_outer_ceiling"]
    )
    assert campaign_policy.governed_requests_per_token == int(
        capacity["lifecycle_requests_per_token"]
    )
    assert campaign_policy.scheduler_row_ceiling == int(
        capacity["lifecycle_scheduler_outer_ceiling"]
    )
    assert campaign_policy.locked_windows == ("WINDOW_12H", "WINDOW_24H")

    connection.close()

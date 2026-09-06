"""End-to-end disposable audit of the Standard-4H memory lifecycle.

This file intentionally drives real production orchestration with the existing
accelerated fixture-source clock. It does not contact providers, prepare an
authorization, or touch the authoritative database.
"""
from __future__ import annotations

import sqlite3

from tests.test_v2_9_8b_lane3_standard_4h_progression import (
    _FactoryLoopDateTime,
    _run_standard_factory_loop,
)


def test_shared_terminal_rejects_third_admitted_cycle_before_mutation(
    tmp_path,
) -> None:
    import pytest

    from printer_v1.db.migrate import apply_migrations
    from printer_v1.operator_cli.unified_terminal_closure import (
        TerminalClosureError,
        reconcile_admitted_campaign_terminal,
    )

    db = tmp_path / "shared-terminal-shape.sqlite3"
    apply_migrations(db)
    connection = sqlite3.connect(db)
    try:
        with connection:
            connection.execute(
                """INSERT INTO printer_memory_factory_campaigns(
                       campaign_id,campaign_state,db_mode,db_target_identity,
                       proof_source_db_identity,policy_version,created_at,updated_at
                   ) VALUES (
                       'camp','RUNNING','PROOF_ISOLATED','isolated','source',
                       'audit',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
                   )"""
            )
            connection.execute(
                """INSERT INTO printer_memory_factory_campaign_configurations(
                       configuration_id,campaign_id,configuration_hash,
                       configuration_json,launch_provenance_json,created_at
                   ) VALUES (
                       'cfg','camp',?,'{}','{}',CURRENT_TIMESTAMP
                   )""",
                ("c" * 64,),
            )
            connection.execute(
                """INSERT INTO printer_memory_factory_campaign_runs(
                       run_id,campaign_id,run_ordinal,run_state,created_at,updated_at
                   ) VALUES (
                       'run','camp',1,'RUNNING',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
                   )"""
            )
            for ordinal in (1, 2, 3):
                connection.execute(
                    """INSERT INTO printer_memory_factory_campaign_cycles(
                           cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,
                           created_at,updated_at
                       ) VALUES (
                           ?,'camp','run',?,'PLANNED',
                           CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
                       )""",
                    (f"cycle-{ordinal}", ordinal),
                )
    finally:
        connection.close()

    with pytest.raises(
        TerminalClosureError,
        match="SHARED_TERMINAL_ADMITTED_CYCLE_SHAPE_INVALID:1,2,3",
    ):
        reconcile_admitted_campaign_terminal(
            db,
            campaign_id="camp",
            run_id="run",
            primary_cycle_id="cycle-1",
            terminal_cause="SHOULD_NOT_MUTATE",
            run_status="FAILED",
            lifecycle_started=True,
        )

    connection = sqlite3.connect(db)
    try:
        assert connection.execute(
            "SELECT campaign_state FROM printer_memory_factory_campaigns "
            "WHERE campaign_id='camp'"
        ).fetchone()[0] == "RUNNING"
        assert connection.execute(
            "SELECT run_state FROM printer_memory_factory_campaign_runs "
            "WHERE run_id='run'"
        ).fetchone()[0] == "RUNNING"
        assert [
            str(row[0])
            for row in connection.execute(
                "SELECT cycle_state FROM printer_memory_factory_campaign_cycles "
                "ORDER BY cycle_ordinal"
            ).fetchall()
        ] == ["PLANNED", "PLANNED", "PLANNED"]
    finally:
        connection.close()


def test_single_cycle_real_factory_reaches_two_terminal_four_hour_closes(
    tmp_path,
    monkeypatch,
) -> None:
    # The legacy Lane-3 harness binds the factory and source contracts to its
    # accelerated clock. Bind the long-window planner too so this audit proves
    # production control flow rather than mixing fake August time with the
    # runner's real wall clock.
    monkeypatch.setattr(
        "printer_v1.operator_cli.one_token_4h_runtime.datetime",
        _FactoryLoopDateTime,
    )
    db, report = _run_standard_factory_loop(
        tmp_path,
        monkeypatch,
        operational_binding="VALID",
        disposable_binding=None,
    )

    validation = dict(report.get("standard_four_hour_terminal_validation") or {})
    assert validation.get("enabled") is True
    assert validation.get("complete") is True, validation
    assert validation.get("reasons") == [], validation

    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        windows = connection.execute(
            """SELECT w.window_id,w.window_state,w.memory_window_row_id,
                      s.token_state,s.token_row_id,s.pair_row_id
                 FROM printer_memory_factory_campaign_windows AS w
                 JOIN printer_memory_factory_campaign_token_slots AS s
                   ON s.campaign_id=w.campaign_id
                  AND s.run_id=w.run_id
                  AND s.cycle_id=w.cycle_id
                  AND s.token_slot_id=w.token_slot_id
                WHERE w.window_kind='WINDOW_4H'
                ORDER BY s.slot_ordinal"""
        ).fetchall()
        assert len(windows) == 2
        assert all(row["memory_window_row_id"] is not None for row in windows)
        assert all(str(row["token_state"]) == "WINDOW_4H_CLOSED" for row in windows)
        assert all(
            str(row["window_state"])
            in {"CLEAN_PROMOTED", "DIRTY", "NO_PROMOTION", "ALREADY_EXISTS_IDEMPOTENT"}
            for row in windows
        )

        closes = connection.execute(
            """SELECT s.step_status,j.status,w.work_state
                 FROM printer_memory_factory_run_steps AS s
                 JOIN printer_scheduler_jobs AS j ON j.id=s.scheduler_job_id
                 JOIN printer_memory_factory_campaign_scheduler_work AS w
                   ON w.scheduler_job_id=s.scheduler_job_id
                WHERE s.step_kind='LONG_CONTINUATION_CLOSE_AUDIT'
                ORDER BY s.id"""
        ).fetchall()
        assert len(closes) == 2
        assert all(tuple(row) == ("SUCCEEDED", "SUCCEEDED", "SUCCEEDED") for row in closes)

        active_jobs = connection.execute(
            """SELECT COUNT(*)
                 FROM printer_scheduler_jobs
                WHERE status IN ('PENDING','RUNNING')"""
        ).fetchone()[0]
        active_steps = connection.execute(
            """SELECT COUNT(*)
                 FROM printer_memory_factory_run_steps
                WHERE step_status IN ('PENDING','RUNNING')"""
        ).fetchone()[0]
        assert int(active_jobs) == 0
        assert int(active_steps) == 0
    finally:
        connection.close()


def test_two_cycle_four_token_real_factory_reaches_shared_terminal_standard4h(
    tmp_path,
    monkeypatch,
) -> None:
    """Drive the missing real overlap seam on disposable fixture-only state."""
    import json

    from printer_v1.operator_cli.authoritative_live_operational_campaign import (
        AuthoritativeLiveOperationalCampaignOwner,
    )
    from printer_v1.operator_cli.campaign_supervision import (
        cleanup_campaign_supervision,
    )
    from printer_v1.operator_cli.four_token_proof_integration import (
        FourTokenProofController,
        LaterCycleCandidateSupply,
        LaterCycleSourceEvidence,
    )
    from printer_v1.operator_cli.unified_terminal_closure import (
        reconcile_admitted_campaign_terminal,
    )
    from tests.test_v2_9_8b_callback_consume_materialize_integration import (
        GOVERNOR,
        NOW,
        SCHEDULER,
        _candidate,
    )
    from tests.test_v2_9_8b_four_token_factory_wake_ordering import (
        CAMPAIGN_ID,
        CAMPAIGN_RUN_ID,
        CONFIGURATION_ID,
        CYCLE_ID,
        FACTORY_RUN_ID,
        _healthy_projection,
    )

    supply_calls = 0
    aggregate_observations = []

    from printer_v1.operator_cli import campaign_full_run_accounting as full_accounting

    real_derive_campaign_terminal = (
        full_accounting.derive_two_cycle_campaign_terminal_accounting
    )

    def observe_campaign_terminal(*args, **kwargs):
        result = real_derive_campaign_terminal(*args, **kwargs)
        aggregate_observations.append(result)
        return result

    monkeypatch.setattr(
        full_accounting,
        "derive_two_cycle_campaign_terminal_accounting",
        observe_campaign_terminal,
    )

    def four_token_setup(db):
        connection = sqlite3.connect(db)
        try:
            for row_id in (3, 4):
                connection.execute(
                    "INSERT INTO printer_tokens(id,token_mint,chain) "
                    "VALUES (?,?, 'solana')",
                    (row_id, f"mint-{row_id}"),
                )
                connection.execute(
                    "INSERT INTO printer_pairs("
                    "id,token_id,pair_address,base_token_mint) VALUES (?,?,?,?)",
                    (100 + row_id, row_id, f"pool-{row_id}", f"mint-{row_id}"),
                )
            request_id = int(
                connection.execute(
                    "INSERT INTO printer_source_requests("
                    "source_name,request_kind,requested_at,source_status,"
                    "data_quality_label) "
                    "VALUES ('dexscreener','fresh_profiles',?,"
                    "'COMPLETE','CLEAN_DATA')",
                    (NOW.isoformat(),),
                ).lastrowid
            )
            payload = json.dumps(
                {
                    "pairs": [
                        {
                            "token_mint": f"mint-{row_id}",
                            "candidate_mint": f"mint-{row_id}",
                            "base_mint": f"mint-{row_id}",
                            "quote_mint": (
                                "So11111111111111111111111111111111111111112"
                            ),
                            "pair_address": f"pool-{row_id}",
                            "chain": "solana",
                            "dex_id": "pumpswap",
                            "liquidity_usd": 10_000.0,
                            "price_usd": 1.0,
                            "volume_5m": 2_000.0,
                            "volume_1h": 7_000.0,
                            "volume_24h": 22_000.0,
                            "txns_5m": 21,
                            "txns_1h": 55,
                            "txns_24h": 140,
                            "captured_at": NOW.isoformat(),
                        }
                        for row_id in (3, 4)
                    ]
                },
                sort_keys=True,
            )
            response_id = int(
                connection.execute(
                    "INSERT INTO printer_source_responses("
                    "source_request_id,source_name,received_at,source_status,"
                    "data_quality_label,normalized_payload_json) "
                    "VALUES (?,'dexscreener',?,'COMPLETE','CLEAN_DATA',?)",
                    (request_id, NOW.isoformat(), payload),
                ).lastrowid
            )
            connection.commit()
        finally:
            connection.close()

        def supply(**_kwargs):
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

        later_callback = AuthoritativeLiveOperationalCampaignOwner(
            later_cycle_candidate_supply=supply
        )._build_later_cycle_discovery_callback(
            db_path=db,
            configuration_id=CONFIGURATION_ID,
        )

        def shared_terminalizer(*, terminal_cause, run_status):
            reconciliation = reconcile_admitted_campaign_terminal(
                db,
                campaign_id=CAMPAIGN_ID,
                run_id=CAMPAIGN_RUN_ID,
                primary_cycle_id=CYCLE_ID,
                terminal_cause=str(terminal_cause),
                run_status=run_status,
                factory_run_id=FACTORY_RUN_ID,
                lifecycle_started=True,
            )
            cleanup = cleanup_campaign_supervision(
                db,
                supervision_id="lane3-factory-loop-supervision",
                campaign_id=CAMPAIGN_ID,
                configuration_id=CONFIGURATION_ID,
                run_id=CAMPAIGN_RUN_ID,
                owner_id="lane3-factory-loop-owner",
                terminal_status=(
                    "COMPLETED" if str(run_status) == "COMPLETED" else "FAILED"
                ),
                first_terminal_cause=str(terminal_cause),
            )
            return {
                "cleanup": cleanup,
                "reconciliation": reconciliation,
                "clean_terminal": bool(
                    cleanup.get("cleanup_completed") is True
                    and reconciliation.get("reconciled") is True
                    and reconciliation.get("clean_terminal") is True
                ),
                "lease_released": cleanup.get("lease_released") is True,
            }

        return {
            "four_token_proof_controller": FourTokenProofController.exact(),
            "later_cycle_discovery_callback": later_callback,
            "four_token_health_projector": (
                lambda _connection, _now: _healthy_projection()
            ),
            "four_token_shared_terminalizer": shared_terminalizer,
            "source_governor_owner": GOVERNOR,
            "central_scheduler_owner": SCHEDULER,
        }

    monkeypatch.setattr(
        "printer_v1.operator_cli.one_token_4h_runtime.datetime",
        _FactoryLoopDateTime,
    )
    try:
        db, report = _run_standard_factory_loop(
            tmp_path,
            monkeypatch,
            operational_binding="VALID",
            disposable_binding=None,
            four_token_setup=four_token_setup,
        )
    except Exception as exc:
        latest = aggregate_observations[-1] if aggregate_observations else {}
        diagnostic = [
            {
                "cycle_id": item.get("cycle_id"),
                "cycle_ordinal": item.get("cycle_ordinal"),
                "execution_outcome": item.get("execution_outcome"),
                "persisted_cycle_state": item.get("persisted_cycle_state"),
                "primary_fault": item.get("primary_fault"),
                "incomplete_reasons": item.get("incomplete_reasons"),
                "standard_four_hour_terminal": item.get(
                    "standard_four_hour_terminal"
                ),
            }
            for item in latest.get("cycles", [])
            if isinstance(item, dict)
        ]
        raise AssertionError(
            json.dumps(
                {
                    "aggregate_execution_outcome": latest.get(
                        "execution_outcome"
                    ),
                    "aggregate_accounting_complete": latest.get(
                        "accounting_complete"
                    ),
                    "cycles": diagnostic,
                },
                sort_keys=True,
                default=str,
            )
        ) from exc

    assert supply_calls == 1
    terminal = dict(report.get("four_token_terminal") or {})
    assert terminal.get("shared_terminalized") is True, terminal
    assert terminal.get("shared_cleanup_count") == 1, terminal
    assert terminal.get("admitted_shape") == "TWO_CYCLE_COMPLETION", terminal
    accounting = dict(terminal.get("terminal_accounting") or {})
    cycle_diagnostics = [
        {
            "cycle_id": item.get("cycle_id"),
            "cycle_ordinal": item.get("cycle_ordinal"),
            "execution_outcome": item.get("execution_outcome"),
            "persisted_cycle_state": item.get("persisted_cycle_state"),
            "primary_fault": item.get("primary_fault"),
            "incomplete_reasons": item.get("incomplete_reasons"),
            "standard_four_hour_terminal": item.get("standard_four_hour_terminal"),
        }
        for item in accounting.get("cycles", [])
        if isinstance(item, dict)
    ]
    assert accounting.get("execution_outcome") == "TERMINAL_SUCCESS", json.dumps(
        cycle_diagnostics, sort_keys=True, default=str
    )
    assert accounting.get("accounting_complete") is True, accounting
    assert [
        int(item["cycle_ordinal"]) for item in accounting.get("admitted_cycles", [])
    ] == [1, 2]
    pre_terminal_tokens = [
        token
        for cycle in accounting.get("cycles", [])
        if isinstance(cycle, dict)
        for token in cycle.get("tokens", [])
        if isinstance(token, dict)
    ]
    assert len(pre_terminal_tokens) == 4, pre_terminal_tokens
    assert all(
        str(token.get("persisted_slot_state")) == "WINDOW_4H_CLOSED"
        for token in pre_terminal_tokens
    ), pre_terminal_tokens
    assert all(
        dict(token.get("standard_four_hour_progression") or {}).get("outcome")
        == "SUCCEEDED"
        for token in pre_terminal_tokens
    ), pre_terminal_tokens

    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        cycles = connection.execute(
            "SELECT cycle_id,cycle_ordinal,cycle_state,first_terminal_cause "
            "FROM printer_memory_factory_campaign_cycles ORDER BY cycle_ordinal"
        ).fetchall()
        assert len(cycles) == 2
        assert [int(row["cycle_ordinal"]) for row in cycles] == [1, 2]
        assert all(str(row["cycle_state"]) == "TERMINAL_COMPLETED" for row in cycles)

        targets = connection.execute(
            "SELECT cycle_id,slot_ordinal,token_row_id,pair_row_id,token_state,"
            "first_terminal_cause,terminal_at,tracking_queue_id "
            "FROM printer_memory_factory_campaign_token_slots "
            "ORDER BY cycle_id,slot_ordinal"
        ).fetchall()
        assert len(targets) == 4
        assert len(
            {(int(row["token_row_id"]), int(row["pair_row_id"])) for row in targets}
        ) == 4
        assert all(str(row["token_state"]) == "COOLDOWN" for row in targets), [
            dict(row) for row in targets
        ]
        assert all(
            str(row["first_terminal_cause"]) == "OWNED_TERMINAL_WINDOW_COOLDOWN"
            and row["terminal_at"] is not None
            and row["tracking_queue_id"] is not None
            for row in targets
        ), [dict(row) for row in targets]
        queues = connection.execute(
            "SELECT id,queue_status,tracking_action FROM printer_tracking_queue "
            "WHERE id IN ("
            "SELECT tracking_queue_id FROM printer_memory_factory_campaign_token_slots "
            "WHERE campaign_id=? AND run_id=? AND tracking_queue_id IS NOT NULL"
            ") ORDER BY id",
            (CAMPAIGN_ID, CAMPAIGN_RUN_ID),
        ).fetchall()
        assert len(queues) == 4
        assert all(
            (str(row["queue_status"]), str(row["tracking_action"]))
            == ("COOLDOWN", "COOLDOWN")
            for row in queues
        ), [dict(row) for row in queues]

        attempt = connection.execute(
            "SELECT attempt_state,consumed_cycle_id FROM "
            "printer_pre_admission_discovery_attempts"
        ).fetchall()
        assert len(attempt) == 1
        assert tuple(attempt[0]) == ("CONSUMED", str(cycles[1]["cycle_id"]))
        admission_job = connection.execute(
            "SELECT status,retry_count FROM printer_scheduler_jobs "
            "WHERE job_kind='PRE_ADMISSION_DISCOVERY_SELECTION'"
        ).fetchall()
        assert [tuple(row) for row in admission_job] == [("SUCCEEDED", 0)]

        windows = connection.execute(
            "SELECT cycle_id,window_kind,window_state,memory_window_row_id "
            "FROM printer_memory_factory_campaign_windows "
            "WHERE window_kind IN ('WINDOW_15M','WINDOW_1H','WINDOW_4H') "
            "ORDER BY cycle_id,window_kind,token_slot_id"
        ).fetchall()
        for kind in ("WINDOW_15M", "WINDOW_1H", "WINDOW_4H"):
            owned = [row for row in windows if str(row["window_kind"]) == kind]
            assert len(owned) == 4, (kind, [tuple(row) for row in owned])
            assert {str(row["cycle_id"]) for row in owned} == {
                str(cycles[0]["cycle_id"]),
                str(cycles[1]["cycle_id"]),
            }
            assert all(row["memory_window_row_id"] is not None for row in owned)

        physical_four_hour = connection.execute(
            """SELECT cw.cycle_id,slot.slot_ordinal,cw.memory_window_row_id,
                      mw.id AS physical_id,mw.token_id,mw.pair_id,
                      mw.window_kind AS physical_window_kind,mw.window_status,
                      mw.supporting_context_json,slot.token_row_id,slot.pair_row_id
                 FROM printer_memory_factory_campaign_windows AS cw
                 JOIN printer_memory_factory_campaign_token_slots AS slot
                   ON slot.campaign_id=cw.campaign_id
                  AND slot.run_id=cw.run_id
                  AND slot.cycle_id=cw.cycle_id
                  AND slot.token_slot_id=cw.token_slot_id
                 JOIN printer_memory_windows AS mw
                   ON mw.id=cw.memory_window_row_id
                WHERE cw.window_kind='WINDOW_4H'
                ORDER BY cw.cycle_id,slot.slot_ordinal"""
        ).fetchall()
        assert len(physical_four_hour) == 4
        assert len({int(row["physical_id"]) for row in physical_four_hour}) == 4
        for row in physical_four_hour:
            assert int(row["memory_window_row_id"]) == int(row["physical_id"])
            assert int(row["token_id"]) == int(row["token_row_id"])
            assert int(row["pair_id"]) == int(row["pair_row_id"])
            assert str(row["physical_window_kind"]) == "WINDOW_4H"
            assert str(row["window_status"]) == "WINDOW_CLOSED"
            context = json.loads(str(row["supporting_context_json"] or "{}"))
            assert (
                context.get("full_four_hour_outcome_source")
                == "EXACT_CURRENT_RUN_MAIN_LIFECYCLE"
            ), context
            snapshot_ids = list(context.get("full_four_hour_outcome_snapshot_ids") or [])
            assert snapshot_ids, context
            assert int(context.get("full_four_hour_outcome_snapshot_count") or 0) == len(
                snapshot_ids
            ), context
            assert context.get("full_four_hour_outcome_path_start_at"), context
            assert context.get("full_four_hour_outcome_path_end_at"), context

        long_closes = connection.execute(
            """SELECT cw.cycle_id,slot.slot_ordinal,rs.step_key,rs.step_status,
                      rs.scheduler_job_id,cw.scheduler_work_id,cw.work_state
                 FROM printer_memory_factory_run_steps AS rs
                 JOIN printer_memory_factory_campaign_scheduler_work AS cw
                   ON cw.scheduler_job_id=rs.scheduler_job_id
                  AND cw.ownership_contract_version='V2_STAGE_SCOPED'
                  AND cw.stage_id='WINDOW_4H'
                  AND cw.work_scope='WINDOW_LIFECYCLE'
                 JOIN printer_memory_factory_campaign_token_slots AS slot
                   ON slot.campaign_id=cw.campaign_id
                  AND slot.run_id=cw.run_id
                  AND slot.cycle_id=cw.cycle_id
                  AND slot.token_slot_id=cw.token_slot_id
                WHERE rs.step_kind='LONG_CONTINUATION_CLOSE_AUDIT'
                ORDER BY cw.cycle_id,slot.slot_ordinal"""
        ).fetchall()
        assert len(long_closes) == 4
        assert all(
            (str(row["step_status"]), str(row["work_state"]))
            == ("SUCCEEDED", "SUCCEEDED")
            for row in long_closes
        ), [dict(row) for row in long_closes]
        assert {
            str(row["cycle_id"]) for row in long_closes
        } == {str(cycles[0]["cycle_id"]), str(cycles[1]["cycle_id"])}
        for cycle in cycles:
            owned = [
                row
                for row in long_closes
                if str(row["cycle_id"]) == str(cycle["cycle_id"])
            ]
            assert [int(row["slot_ordinal"]) for row in owned] == [1, 2], [
                dict(row) for row in owned
            ]
        assert len({int(row["scheduler_job_id"]) for row in long_closes}) == 4
        assert len({str(row["scheduler_work_id"]) for row in long_closes}) == 4
        assert len({str(row["step_key"]) for row in long_closes}) == 4

        progression = connection.execute(
            "SELECT cycle_id,attempt_state FROM "
            "printer_memory_factory_standard_4h_progression_attempts "
            "ORDER BY cycle_id"
        ).fetchall()
        assert len(progression) == 2
        assert all(str(row["attempt_state"]) == "HANDOFF_COMMITTED" for row in progression)

        assert int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
                "WHERE window_kind IN ('WINDOW_12H','WINDOW_24H')"
            ).fetchone()[0]
        ) == 0
        assert int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs "
                "WHERE status IN ('PENDING','RUNNING','COOLDOWN') "
                "OR locked_at IS NOT NULL OR lock_owner IS NOT NULL"
            ).fetchone()[0]
        ) == 0
        assert int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
                "WHERE step_status IN ('PENDING','RUNNING')"
            ).fetchone()[0]
        ) == 0
        assert int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work "
                "WHERE work_state IN ('PENDING','RUNNING','COOLDOWN')"
            ).fetchone()[0]
        ) == 0

        supervision = connection.execute(
            "SELECT supervision_state,terminal_status,cleanup_completed_at,"
            "lease_released_at FROM printer_memory_factory_campaign_supervision"
        ).fetchone()
        assert str(supervision["supervision_state"]) == "TERMINAL"
        assert str(supervision["terminal_status"]) == "COMPLETED"
        assert supervision["cleanup_completed_at"] is not None
        assert supervision["lease_released_at"] is not None
        assert connection.execute(
            "SELECT run_state FROM printer_memory_factory_campaign_runs"
        ).fetchone()[0] == "TERMINAL_COMPLETED"
        assert connection.execute(
            "SELECT run_status FROM printer_memory_factory_runs"
        ).fetchone()[0] == "COMPLETED"
    finally:
        connection.close()

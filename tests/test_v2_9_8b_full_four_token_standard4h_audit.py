"""End-to-end disposable audit of the Standard-4H memory lifecycle.

This file intentionally drives real production orchestration with the existing
accelerated fixture-source clock. It does not contact providers, prepare an
authorization, or touch the authoritative database.
"""
from __future__ import annotations

import sqlite3

from tests.test_v2_9_8b_lane3_standard_4h_progression import (
    _FactoryLoopDateTime,
    _factory_loop_snapshot_adapter,
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
    """Drive real Cycle-1 admission and Cycle-2 through shared Standard-4H."""
    import json
    from datetime import timedelta

    from printer_v1.discovery.combined_executor import (
        CombinedDiscoveryFixtures,
        CombinedPumpfunCampaignExecutor,
        FixtureOriginProof,
        FixturePumpSwapProof,
        FixtureSourceFact,
    )
    from printer_v1.operator_cli.abstract_campaign_command import (
        AbstractCampaignCommand,
        CAMPAIGN_MODE,
        CampaignCeilings,
    )
    from printer_v1.operator_cli.authoritative_live_operational_campaign import (
        AuthoritativeLiveOperationalCampaignOwner,
        later_cycle_gate_quantum_seconds,
    )
    from printer_v1.operator_cli.campaign_supervision import (
        cleanup_campaign_supervision,
    )
    from printer_v1.operator_cli.four_token_proof_integration import (
        FourTokenProofController,
        LaterCycleCandidateSupply,
        LaterCycleSourceEvidence,
    )
    from printer_v1.operator_cli.origin_lifecycle_campaign import (
        _read_activated_slots,
        materialize_origin_activated_batch,
    )
    from printer_v1.operator_cli.unified_terminal_closure import (
        reconcile_admitted_campaign_terminal,
    )
    from printer_v1.sources.governed_execution import build_fixture_source_adapter
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
        START,
        _healthy_projection,
    )

    cycle_one_mints = ("A" * 32, "B" * 32)
    cycle_one_pools = ("C" * 32, "D" * 32)
    cycle_one_batch_ids: list[str] = []
    cycle_one_activation_slots: list[dict[str, object]] = []

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
        cycle_one_seed = "cycle1-real-admission-four-hour-seed"
        origins = (
            FixtureOriginProof(
                mint=cycle_one_mints[0],
                signature="cycle1-origin-a",
                slot=10,
                block_time=10,
                bonding_curve=cycle_one_pools[0],
                associated_bonding_curve="cycle1-ata-a",
                creator_address="cycle1-creator-a",
            ),
            FixtureOriginProof(
                mint=cycle_one_mints[1],
                signature="cycle1-origin-b",
                slot=11,
                block_time=11,
                bonding_curve=cycle_one_pools[1],
                associated_bonding_curve="cycle1-ata-b",
                creator_address="cycle1-creator-b",
            ),
        )
        fixtures = CombinedDiscoveryFixtures(
            cycle_id=CYCLE_ID,
            cycle_cutoff=(START + timedelta(minutes=6)).isoformat(),
            campaign_selection_seed=cycle_one_seed,
            provider_contract_versions={
                "direct": "V2-9.7D.7B.3A",
                "dexscreener": "existing",
            },
            git_provenance_identity="cycle1-four-hour-admission-proof",
            evaluated_at=START.isoformat(),
            dexscreener_ops=(
                FixtureSourceFact(
                    request_kind="dexscreener_fresh_profiles",
                    source_name="dexscreener",
                    body=[
                        {
                            "chainId": "solana",
                            "baseToken": {"address": mint},
                            "quoteToken": {
                                "address": "So11111111111111111111111111111111111111112"
                            },
                            "pairAddress": pool,
                            "dexId": "pumpfun",
                            "priceUsd": 0.01,
                            "liquidity": {"usd": 10_000},
                            "volume": {"m5": 500, "h1": 2_000, "h24": 10_000},
                            "txns": {
                                "m5": {"buys": 7, "sells": 3},
                                "h1": 50,
                                "h24": 500,
                            },
                        }
                        for mint, pool in zip(
                            cycle_one_mints, cycle_one_pools, strict=True
                        )
                    ],
                    receipt_time=START.isoformat(),
                ),
            ),
            direct_observations=origins,
            pumpswap_proofs={
                origin.mint: FixturePumpSwapProof(
                    mint=origin.mint,
                    pool_address=origin.bonding_curve,
                )
                for origin in origins
            },
        )
        command = AbstractCampaignCommand(
            mode=CAMPAIGN_MODE,
            db_path=str(db),
            db_target_identity="db-1",
            campaign_id=CAMPAIGN_ID,
            configuration_id=CONFIGURATION_ID,
            configuration_hash="a" * 64,
            policy_version="policy-1",
            token_capacity=2,
            ceilings=CampaignCeilings(
                campaign_count=1,
                cycle_count=2,
                duration_seconds=21_600,
                source_calls=200,
                scheduler_work=500,
                storage_bytes=50_000_000,
                failures=20,
            ),
            report_directory=db.parent,
            report_directory_identity="path-sha256:" + "c" * 64,
            launch_git_provenance={
                "git_head": "d" * 40,
                "git_tracked_tree_clean": True,
                "git_staged_changes_present": False,
                "git_unstaged_changes_present": False,
                "git_untracked_present": True,
                "git_provenance_captured_at": START.isoformat(),
            },
            run_id=CAMPAIGN_RUN_ID,
            report_id="cycle1-four-hour-admission-proof",
        )
        activation = CombinedPumpfunCampaignExecutor(fixtures).execute(
            command=command,
            source_governor=GOVERNOR,
            central_scheduler=SCHEDULER,
        )
        assert activation.terminal_status == "COMPLETED", activation

        connection = sqlite3.connect(db)
        connection.row_factory = sqlite3.Row
        try:
            committed_cycle_one_slots = _read_activated_slots(
                connection, CYCLE_ID
            )
            assert len(committed_cycle_one_slots) == 2, committed_cycle_one_slots
            cycle_one_activation_slots.extend(committed_cycle_one_slots)
            batch_id = materialize_origin_activated_batch(
                connection,
                cycle_id=CYCLE_ID,
                selection_seed=cycle_one_seed,
            )
            assert batch_id is not None
            cycle_one_batch_ids.append(str(batch_id))
            connection.commit()
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

        def admitted_cycle_one_discovery(_args):
            return {
                "selection_handoff_report": {
                    "batch_id": cycle_one_batch_ids[0],
                    "selection_seed": cycle_one_seed,
                    "eligible_pool_size": 2,
                },
                "discovery_results": [],
            }

        cycle_one_pool_by_mint = dict(
            zip(cycle_one_mints, cycle_one_pools, strict=True)
        )

        def admitted_snapshot_adapter(*, token_mint, timeout_seconds):
            pool = cycle_one_pool_by_mint.get(str(token_mint))
            if pool is None:
                return _factory_loop_snapshot_adapter(
                    token_mint=token_mint,
                    timeout_seconds=timeout_seconds,
                )
            return build_fixture_source_adapter(
                "dexscreener",
                fixture_payload={
                    "pairs": [
                        {
                            "chain": "solana",
                            "token_mint": str(token_mint),
                            "pair_address": pool,
                            "price_usd": 1.0,
                            "liquidity_usd": 10_000.0,
                            "volume_5m": 500.0,
                            "volume_1h": 2_000.0,
                            "volume_24h": 10_000.0,
                            "txns_5m": 10,
                            "txns_1h": 50,
                            "txns_24h": 500,
                            "buys_5m": 7,
                            "sells_5m": 3,
                            "buys_1h": 30,
                            "sells_1h": 20,
                            "buys_24h": 280,
                            "sells_24h": 220,
                            "price_change_5m": 1.0,
                            "price_change_1h": 2.0,
                            "price_change_24h": 3.0,
                        }
                    ]
                },
            )

        return {
            "discovery_runner": admitted_cycle_one_discovery,
            "snapshot_adapter_factory": admitted_snapshot_adapter,
            "four_token_proof_controller": FourTokenProofController.exact(),
            "later_cycle_discovery_callback": later_callback,
            "later_cycle_acquisition_quantum_seconds": (
                lambda: later_cycle_gate_quantum_seconds({})
            ),
            "later_cycle_admission_deadline_seconds_after_first_cycle": 600,
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
            pre_admit_cycle_one=False,
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
        durable = {}
        try:
            connection = sqlite3.connect(tmp_path / "wake-order.sqlite3")
            connection.row_factory = sqlite3.Row
            durable = {
                "factory_run": [
                    dict(row)
                    for row in connection.execute(
                        "SELECT run_status,stop_reason,started_at,finished_at "
                        "FROM printer_memory_factory_runs"
                    ).fetchall()
                ],
                "campaign_cycles": [
                    dict(row)
                    for row in connection.execute(
                        "SELECT cycle_id,cycle_ordinal,cycle_state,"
                        "first_terminal_cause,created_at,updated_at "
                        "FROM printer_memory_factory_campaign_cycles "
                        "ORDER BY cycle_ordinal"
                    ).fetchall()
                ],
                "admission_attempts": [
                    dict(row)
                    for row in connection.execute(
                        "SELECT attempt_id,proposed_cycle_ordinal,attempt_state,"
                        "first_terminal_cause,consumed_cycle_id,created_at,updated_at "
                        "FROM printer_pre_admission_discovery_attempts "
                        "ORDER BY proposed_cycle_ordinal,attempt_id"
                    ).fetchall()
                ],
                "cycle_one_slots": [
                    dict(row)
                    for row in connection.execute(
                        """SELECT s.slot_ordinal,s.token_row_id,s.token_state,
                                  q.tracking_lane,q.queue_status
                             FROM printer_memory_factory_campaign_token_slots AS s
                             LEFT JOIN printer_tracking_queue AS q
                               ON q.id=s.tracking_queue_id
                            WHERE s.cycle_id=?
                            ORDER BY s.slot_ordinal""",
                        (CYCLE_ID,),
                    ).fetchall()
                ],
                "active_steps": [
                    dict(row)
                    for row in connection.execute(
                        "SELECT step_key,step_kind,token_id,tracking_lane,"
                        "step_status,scheduled_for,error_or_skip_reason "
                        "FROM printer_memory_factory_run_steps "
                        "WHERE step_status IN ('PENDING','RUNNING') "
                        "ORDER BY scheduled_for,id LIMIT 20"
                    ).fetchall()
                ],
            }
        finally:
            try:
                connection.close()
            except Exception:
                pass
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
                    "durable": durable,
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
    assert accounting.get("exact_four_distinct_targets") is True, accounting
    selection_provenance = dict(accounting.get("selection_provenance") or {})
    assert selection_provenance.get("exact") is True, selection_provenance
    assert dict(selection_provenance.get("cycle_1") or {}).get("exact") is True
    assert dict(selection_provenance.get("cycle_2") or {}).get("exact") is True
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

        assert len(cycle_one_activation_slots) == 2
        assert len(cycle_one_batch_ids) == 1
        cycle_one_queue_lanes = connection.execute(
            """SELECT s.slot_ordinal,s.token_row_id,s.pair_row_id,
                      s.mint_identity,s.pair_identity,q.tracking_lane
                 FROM printer_memory_factory_campaign_token_slots AS s
                 JOIN printer_tracking_queue AS q ON q.id=s.tracking_queue_id
                WHERE s.campaign_id=? AND s.run_id=? AND s.cycle_id=?
                ORDER BY s.slot_ordinal""",
            (CAMPAIGN_ID, CAMPAIGN_RUN_ID, CYCLE_ID),
        ).fetchall()
        assert len(cycle_one_queue_lanes) == 2
        assert {
            (str(row["mint_identity"]), str(row["pair_identity"]))
            for row in cycle_one_queue_lanes
        } == {
            (str(slot["mint_identity"]), str(slot["pair_identity"]))
            for slot in cycle_one_activation_slots
        }

        cycle_one_selection = connection.execute(
            "SELECT token_id,pair_id,tracking_lane "
            "FROM printer_selection_batch_items "
            "WHERE batch_id=? AND item_status='SELECTED' ORDER BY token_id",
            (cycle_one_batch_ids[0],),
        ).fetchall()
        expected_cycle_one_targets = {
            (
                int(row["token_row_id"]),
                int(row["pair_row_id"]),
                str(row["tracking_lane"]),
            )
            for row in cycle_one_queue_lanes
        }
        assert {tuple(row) for row in cycle_one_selection} == expected_cycle_one_targets

        cycle_one_token_ids = tuple(
            int(row["token_row_id"]) for row in cycle_one_queue_lanes
        )
        cycle_one_step_lanes = connection.execute(
            """SELECT token_id,tracking_lane
                 FROM printer_memory_factory_run_steps
                WHERE run_id=? AND token_id IN (?,?)
                  AND tracking_lane IS NOT NULL
                GROUP BY token_id,tracking_lane
                ORDER BY token_id""",
            (FACTORY_RUN_ID, *cycle_one_token_ids),
        ).fetchall()
        assert {
            (int(row["token_id"]), str(row["tracking_lane"]))
            for row in cycle_one_step_lanes
        } == {
            (int(row["token_row_id"]), str(row["tracking_lane"]))
            for row in cycle_one_queue_lanes
        }

        cycle_one_progression_lanes = connection.execute(
            """SELECT slot_ordinal,tracking_lane
                 FROM printer_memory_factory_standard_4h_progression_tokens
                WHERE cycle_id=? ORDER BY slot_ordinal""",
            (CYCLE_ID,),
        ).fetchall()
        assert [
            (int(row["slot_ordinal"]), str(row["tracking_lane"]))
            for row in cycle_one_progression_lanes
        ] == [
            (int(row["slot_ordinal"]), str(row["tracking_lane"]))
            for row in cycle_one_queue_lanes
        ]

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
            authoritative_lane = connection.execute(
                """SELECT q.tracking_lane
                     FROM printer_memory_factory_campaign_token_slots AS s
                     JOIN printer_tracking_queue AS q ON q.id=s.tracking_queue_id
                    WHERE s.cycle_id=? AND s.slot_ordinal=?""",
                (str(row["cycle_id"]), int(row["slot_ordinal"])),
            ).fetchone()
            assert authoritative_lane is not None
            placeholders = ",".join("?" for _ in snapshot_ids)
            snapshot_lanes = connection.execute(
                f"SELECT DISTINCT tracking_lane FROM printer_token_snapshots "
                f"WHERE id IN ({placeholders}) ORDER BY tracking_lane",
                tuple(int(value) for value in snapshot_ids),
            ).fetchall()
            assert [str(item[0]) for item in snapshot_lanes] == [
                str(authoritative_lane[0])
            ]

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

        # Clean-memory promotion is allowed only after the exact owned window
        # closes. Any promoted object must preserve the originating physical
        # window identity/kind and have exactly one canonical fingerprint.
        clean_objects = connection.execute(
            """SELECT e.id AS episode_id,e.memory_window_id,e.token_id,e.pair_id,
                      e.window_kind,e.episode_kind,e.memory_status,
                      e.memory_quality_label,e.data_quality_label,e.do_not_train,
                      mw.window_kind AS source_window_kind,
                      COUNT(f.id) AS fingerprint_count
                 FROM printer_episodes AS e
                 JOIN printer_memory_windows AS mw ON mw.id=e.memory_window_id
                 LEFT JOIN printer_memory_fingerprints AS f
                   ON f.episode_id=e.id
                  AND f.fingerprint_kind='STATIC_CONDITION_SUMMARY'
                WHERE e.memory_status='CLEAN_MEMORY'
                GROUP BY e.id,e.memory_window_id,e.token_id,e.pair_id,
                         e.window_kind,e.episode_kind,e.memory_status,
                         e.memory_quality_label,e.data_quality_label,e.do_not_train,
                         mw.window_kind
                ORDER BY e.id"""
        ).fetchall()
        assert len({int(row["memory_window_id"]) for row in clean_objects}) == len(
            clean_objects
        )
        for row in clean_objects:
            assert str(row["window_kind"]) == str(row["source_window_kind"])
            assert str(row["episode_kind"]) == (
                f"{row['source_window_kind']}_CLEAN_MEMORY"
            )
            assert str(row["memory_quality_label"]) == "CLEAN_MEMORY"
            assert str(row["data_quality_label"]) == "CLEAN_DATA"
            assert int(row["do_not_train"]) == 0
            assert int(row["fingerprint_count"]) == 1

        clean_four_hour = connection.execute(
            """SELECT cw.cycle_id,cw.token_slot_id,e.id AS episode_id,
                      e.memory_window_id,e.window_kind,f.fingerprint_payload_json
                 FROM printer_memory_factory_campaign_windows AS cw
                 JOIN printer_episodes AS e
                   ON e.memory_window_id=cw.memory_window_row_id
                  AND e.memory_status='CLEAN_MEMORY'
                 JOIN printer_memory_fingerprints AS f
                   ON f.episode_id=e.id
                  AND f.fingerprint_kind='STATIC_CONDITION_SUMMARY'
                WHERE cw.window_kind='WINDOW_4H'
                ORDER BY cw.cycle_id,cw.token_slot_id"""
        ).fetchall()
        assert len({int(row["episode_id"]) for row in clean_four_hour}) == len(
            clean_four_hour
        )
        assert len({int(row["memory_window_id"]) for row in clean_four_hour}) == len(
            clean_four_hour
        )
        for row in clean_four_hour:
            payload = json.loads(str(row["fingerprint_payload_json"] or "{}"))
            assert int(payload["episode_id"]) == int(row["episode_id"])
            assert int(payload["window_id"]) == int(row["memory_window_id"])
            assert str(payload["window_kind"]) == "WINDOW_4H"

        # Memory growth does not activate retrieval or decision/trading surfaces.
        for table in (
            "printer_memory_retrieval_queries",
            "printer_memory_retrieval_matches",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
            "printer_paper_trade_audits",
        ):
            assert int(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            ) == 0

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

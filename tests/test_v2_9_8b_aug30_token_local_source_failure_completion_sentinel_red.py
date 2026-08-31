"""Aug-30 revision-3 RED/GREEN: token-local Dex→Gecko isolation.

Disposable SQLite only. No network/provider calls.

Covers:
1. Failed/no-WINDOW_15M sibling must not contaminate a healthy peer close
   through selective-1h evaluation (soft-skip at barrier; no fake window).
2. Full four-token drained-loop finalization:
   - Cycle-1 Token-1 Dex+Gecko fail → token-local FAILED
   - Cycle-1 peer WINDOW_CLOSE stays SUCCEEDED
   - Cycle-2 ordinary WINDOW_15M paths complete with CLEAN_PROMOTED
   - pre-Phase-A shared stop is not false STOP_COMPLETED / SAFE_STOP_SOURCE_FAILURE
   - no CAMPAIGN/CAMPAIGN consumption of token-local source cause
"""

from __future__ import annotations

from dataclasses import replace
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
from printer_v1.operator_cli.one_command_15m_factory import (
    TOKEN_LOCAL_FAILED,
    _run_selective_1h_campaign_barrier,
)
from printer_v1.operator_cli.unified_terminal_closure import reconcile_campaign_terminal
from printer_v1.sources.dexscreener import build_dexscreener_adapter
from printer_v1.sources.geckoterminal import build_geckoterminal_adapter
from printer_v1.sources.governed_execution import (
    FIXTURE_FAILURE,
    build_fixture_source_adapter,
)
from tests.test_v2_9_5_exact_pair_source_redundancy import (
    _dex_failure_payload,
    _gt_failure_payload,
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
FAILED_MINT = "mint-1"
PEER_MINT = "mint-2"
STOP_COMPLETED = "COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED"
STOP_SOURCE = "SAFE_STOP_SOURCE_FAILURE"
TOKEN_LOCAL_CANCELLED = "TOKEN_LOCAL_CANCELLED_AFTER_FAILURE"


def _dex_success_pairs(token_mint: str) -> dict:
    pool = f"pool-{token_mint.rsplit('-', 1)[-1]}"
    return {
        "_source_status_code": 200,
        "pairs": [
            {
                "chainId": "solana",
                "pairAddress": pool,
                "baseToken": {
                    "address": token_mint,
                    "symbol": "TOK",
                    "name": "Token",
                },
                "priceUsd": "1.0",
                "liquidity": {"usd": 10_000.0},
                "volume": {"m5": 10.0, "h1": 20.0, "h24": 30.0},
                "txns": {
                    "m5": {"buys": 1, "sells": 1},
                    "h1": {"buys": 2, "sells": 2},
                    "h24": {"buys": 3, "sells": 3},
                },
                "fdv": 1_000_000.0,
                "marketCap": 900_000.0,
                "priceChange": {"m5": 0.0, "h1": 0.0, "h24": 0.0},
                "pairCreatedAt": 1_700_000_000_000,
            }
        ],
    }


def _discovery(db):
    def run(_args):
        connection = sqlite3.connect(db)
        connection.execute(
            "INSERT INTO printer_selection_batches("
            "batch_id,batch_status,window_kind,candidate_pool_total,selected_count,"
            "operator_approved) VALUES "
            "('aug30-red-batch','ASSEMBLED','WINDOW_15M',2,2,1)"
        )
        for row_id in (1, 2):
            connection.execute(
                "INSERT INTO printer_selection_batch_items("
                "batch_id,item_status,token_id,pair_id,token_mint,pair_address,"
                "tracking_lane,operator_approved) VALUES "
                "('aug30-red-batch','SELECTED',?,?,?,?, 'TRACK_NORMAL',1)",
                (row_id, 100 + row_id, f"mint-{row_id}", f"pool-{row_id}"),
            )
        connection.commit()
        connection.close()
        return {
            "selection_handoff_report": {
                "batch_id": "aug30-red-batch",
                "selection_seed": "aug30-red-seed",
                "eligible_pool_size": 2,
            },
            "discovery_results": [],
        }

    return run


def _ensure_clean_episode(conn: sqlite3.Connection, memory_window_id: int) -> None:
    """Attach durable CLEAN episode so campaign registration can CLEAN_PROMOTE."""
    existing = conn.execute(
        """SELECT id FROM printer_episodes
           WHERE memory_window_id=? AND episode_kind='WINDOW_15M_CLEAN_MEMORY'
           LIMIT 1""",
        (int(memory_window_id),),
    ).fetchone()
    if existing is not None:
        return
    mw = conn.execute(
        "SELECT token_id,pair_id FROM printer_memory_windows WHERE id=?",
        (int(memory_window_id),),
    ).fetchone()
    if mw is None:
        return
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE printer_memory_windows
           SET memory_status='CLEAN_MEMORY',
               memory_quality_label='CLEAN_MEMORY',
               data_quality_label='CLEAN_DATA',
               do_not_train=0,
               updated_at=?
           WHERE id=?""",
        (now, int(memory_window_id)),
    )
    conn.execute(
        """INSERT INTO printer_episodes(
               memory_window_id,token_id,pair_id,episode_kind,episode_status,
               memory_status,data_quality_label,do_not_train,memory_quality_label,
               window_kind,created_at,updated_at)
           VALUES (?,?,?,'WINDOW_15M_CLEAN_MEMORY','COMPLETE',
                   'CLEAN_MEMORY','CLEAN_DATA',0,'CLEAN_MEMORY',
                   'WINDOW_15M',?,?)""",
        (
            int(memory_window_id),
            int(mw[0]),
            int(mw[1]),
            now,
            now,
        ),
    )


def test_mixed_pre_15m_exclusion_creates_two_row_progression_and_healthy_1h(
    tmp_path,
    monkeypatch,
) -> None:
    """RED: the mixed barrier must represent A and still evaluate healthy B.

    Removing the mixed-exclusion producer or routing A through the ordinary
    evaluator must fail this test.
    """
    del tmp_path
    from printer_v1.operator_cli.campaign_ownership import transition_state
    from printer_v1.operator_cli import one_command_15m_factory as factory
    from tests.test_v2_9_8b_operational_selective_1h import Selective1hFixture

    fixture = Selective1hFixture(standard_four_hour_campaign=True)
    try:
        connection = fixture.connection
        fixture.prepare_eligible(
            token_id=2,
            window_id=202,
            outcome="CONSOLIDATION",
        )
        failure_id = int(
            connection.execute(
                """INSERT INTO printer_source_failures(
                       source_name,request_kind,failed_at,failure_type,
                       failure_message,source_status,data_quality_label)
                   VALUES ('geckoterminal','pair_market_snapshot',?,
                           'DEX_AND_FALLBACK_FAILED','fixture failure',
                           'FAILED','MISSING_CRITICAL_DATA')""",
                (NOW := START.isoformat(),),
            ).lastrowid
        )
        failed_step_id = int(
            connection.execute(
                """INSERT INTO printer_memory_factory_run_steps(
                       run_id,step_key,step_kind,step_status,token_id,pair_id,
                       token_mint,pair_address,tracking_lane,source_failure_id,
                       error_or_skip_reason,finished_at)
                   VALUES ('factory-run-1','slot-1-snapshot-00','SNAPSHOT','FAILED',
                           1,1,'mint-1','pair-1','TRACK_FAST',?,?,?)""",
                (failure_id, TOKEN_LOCAL_FAILED, NOW),
            ).lastrowid
        )
        transition_state(
            connection,
            record_kind="token_slot",
            identity="slot-1",
            expected_state="SELECTED",
            new_state="FAILED",
            terminal_cause=TOKEN_LOCAL_FAILED,
            now=NOW,
        )
        connection.commit()
        monkeypatch.setattr(
            factory,
            "_selective_1h_schedule_for_close",
            lambda *args, **kwargs: (
                {"captured": False, "verdict": "FIXTURE_NO_CAPTURE"},
                {"enqueue_ok": True, "planned_jobs": 0},
            ),
        )

        result = factory._run_selective_1h_campaign_barrier(
            connection,
            db_path=str(fixture.db),
            run_id="factory-run-1",
            config={
                "campaign_id": "campaign-1h",
                "campaign_run_id": "run-1h",
                "configuration_id": "config-1h",
                "cycle_id": "cycle-1h",
            },
            continuation_seconds=16.0,
        )

        assert result["evaluation_reached"] is True
        progression = connection.execute(
            """SELECT attempt_state
               FROM printer_memory_factory_standard_4h_progression_attempts
               WHERE campaign_id='campaign-1h' AND campaign_run_id='run-1h'
                 AND cycle_id='cycle-1h'"""
        ).fetchone()
        assert progression is not None
        rows = connection.execute(
            """SELECT token_slot_id,token_disposition,first_terminal_cause,
                      disposition_reasons_json,eligibility_evidence_json,
                      predecessor_window_1h_id,successor_window_4h_id
               FROM printer_memory_factory_standard_4h_progression_tokens
               ORDER BY slot_ordinal"""
        ).fetchall()
        assert len(rows) == 2
        excluded = rows[0]
        assert tuple(excluded[:3]) == ("slot-1", "INELIGIBLE", None)
        assert json.loads(excluded["disposition_reasons_json"]) == [
            "PRE_15M_TOKEN_LOCAL_TERMINAL_FAILURE"
        ]
        evidence = json.loads(excluded["eligibility_evidence_json"])
        assert int(evidence["failed_factory_step_id"]) == failed_step_id
        assert int(evidence["source_failure_id"]) == failure_id
        assert evidence["terminal_cause"] == TOKEN_LOCAL_FAILED
        assert evidence["no_valid_successful_memory_backed_window_15m"] is True
        assert excluded["predecessor_window_1h_id"] is None
        assert excluded["successor_window_4h_id"] is None

        healthy = rows[1]
        assert healthy["token_slot_id"] == "slot-2"
        assert healthy["token_disposition"] == "WAITING_FOR_PREDECESSOR"
        healthy_window = connection.execute(
            """SELECT window_state FROM printer_memory_factory_campaign_windows
               WHERE token_slot_id='slot-2' AND window_kind='WINDOW_1H'"""
        ).fetchone()
        assert healthy_window is not None
        assert healthy_window["window_state"] == "PLANNED"
        assert connection.execute(
            """SELECT COUNT(*) FROM printer_memory_factory_campaign_objects
               WHERE token_slot_id='slot-1' AND object_kind='CONTINUATION_4A'"""
        ).fetchone()[0] == 0
        assert connection.execute(
            """SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
               WHERE token_slot_id='slot-1' AND window_kind IN (
                   'WINDOW_15M','WINDOW_1H','WINDOW_4H')"""
        ).fetchone()[0] == 0
    finally:
        fixture.close()


def _seed_exact_pre_15m_failure(fixture, *, token_id: int) -> tuple[int, int]:
    from printer_v1.operator_cli.campaign_ownership import transition_state

    connection = fixture.connection
    now = START.isoformat()
    failure_id = int(
        connection.execute(
            """INSERT INTO printer_source_failures(
                   source_name,request_kind,failed_at,failure_type,
                   failure_message,source_status,data_quality_label)
               VALUES ('geckoterminal','pair_market_snapshot',?,
                       'DEX_AND_FALLBACK_FAILED','fixture failure',
                       'FAILED','MISSING_CRITICAL_DATA')""",
            (now,),
        ).lastrowid
    )
    failed_step_id = int(
        connection.execute(
            """INSERT INTO printer_memory_factory_run_steps(
                   run_id,step_key,step_kind,step_status,token_id,pair_id,
                   token_mint,pair_address,tracking_lane,source_failure_id,
                   error_or_skip_reason,finished_at)
               VALUES ('factory-run-1',?,'SNAPSHOT','FAILED',?,?,?, ?,?,?,?,?)""",
            (
                f"slot-{token_id}-snapshot-00",
                token_id,
                token_id,
                f"mint-{token_id}",
                f"pair-{token_id}",
                "TRACK_FAST" if token_id == 1 else "TRACK_NORMAL",
                failure_id,
                TOKEN_LOCAL_FAILED,
                now,
            ),
        ).lastrowid
    )
    transition_state(
        connection,
        record_kind="token_slot",
        identity=f"slot-{token_id}",
        expected_state="SELECTED",
        new_state="FAILED",
        terminal_cause=TOKEN_LOCAL_FAILED,
        now=now,
    )
    connection.commit()
    return failed_step_id, failure_id


def test_two_pre_15m_exclusions_commit_truthful_zero_successor_handoff() -> None:
    from printer_v1.operator_cli import one_command_15m_factory as factory
    from printer_v1.db.migrate import canonical_migration_count, canonical_migration_names
    from printer_v1.operator_cli.campaign_supervision import acquire_campaign_supervision
    from printer_v1.operator_cli.operational_database_target_binding import (
        PRODUCTION_AUTHORITATIVE,
        build_operational_database_target_binding,
    )
    from printer_v1.operator_cli.operational_standard_4h import (
        run_standard_four_hour_campaign_barrier,
    )
    from tests.test_v2_9_8b_operational_selective_1h import Selective1hFixture

    fixture = Selective1hFixture(standard_four_hour_campaign=True)
    try:
        _seed_exact_pre_15m_failure(fixture, token_id=1)
        _seed_exact_pre_15m_failure(fixture, token_id=2)
        result = factory._run_selective_1h_campaign_barrier(
            fixture.connection,
            db_path=str(fixture.db),
            run_id="factory-run-1",
            config={
                "campaign_id": "campaign-1h",
                "campaign_run_id": "run-1h",
                "configuration_id": "config-1h",
                "cycle_id": "cycle-1h",
            },
            continuation_seconds=16.0,
        )
        assert result["evaluation_reached"] is True
        rows = fixture.connection.execute(
            """SELECT token_disposition,disposition_reasons_json,
                      predecessor_window_1h_id,successor_window_4h_id
               FROM printer_memory_factory_standard_4h_progression_tokens
               ORDER BY slot_ordinal"""
        ).fetchall()
        assert len(rows) == 2
        assert all(str(row["token_disposition"]) == "INELIGIBLE" for row in rows)
        assert all(
            json.loads(str(row["disposition_reasons_json"]))
            == ["PRE_15M_TOKEN_LOCAL_TERMINAL_FAILURE"]
            for row in rows
        )
        assert all(row["predecessor_window_1h_id"] is None for row in rows)
        assert all(row["successor_window_4h_id"] is None for row in rows)
        assert fixture.connection.execute(
            "SELECT attempt_state FROM "
            "printer_memory_factory_standard_4h_progression_attempts"
        ).fetchone()[0] == "ELIGIBILITY_COMPLETE"

        acquire_campaign_supervision(
            fixture.db,
            lock_path=fixture.db.with_suffix(".two-exclusions.lease.json"),
            supervision_id="two-exclusions-supervision",
            campaign_id="campaign-1h",
            configuration_id="config-1h",
            run_id="run-1h",
            owner_id="two-exclusions-owner",
            lease_seconds=3600,
        )
        binding = build_operational_database_target_binding(
            target_kind=PRODUCTION_AUTHORITATIVE,
            resolved_db_path=fixture.db,
            authorized_pre_mutation_sha256="a" * 64,
            migration_count=canonical_migration_count(),
            migration_head=canonical_migration_names()[-1],
            authorization_id="lane3-authorization",
            authorization_marker_sha256="b" * 64,
            application_marker_sha256="c" * 64,
            execution_id="lane3-execution",
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
            configuration_id="config-1h",
            authorization_consumed_once=True,
            invocation_count=1,
            allowed_invocation_count=1,
            automatic_retry_allowed=False,
            manual_rerun_allowed=False,
            resume_allowed=False,
            restart_allowed=False,
            successor_allowed=False,
        )
        barrier = run_standard_four_hour_campaign_barrier(
            fixture.connection,
            db_path=fixture.db,
            campaign_id="campaign-1h",
            configuration_id="config-1h",
            run_id="run-1h",
            cycle_id="cycle-1h",
            factory_run_id="factory-run-1",
            operational_db_binding=binding,
            canonical_authoritative_db_path=fixture.db,
            cancellation_probe=lambda: None,
        )
        assert barrier["plan"]["no_op"] is True
        assert fixture.connection.execute(
            "SELECT attempt_state FROM "
            "printer_memory_factory_standard_4h_progression_attempts"
        ).fetchone()[0] == "HANDOFF_COMMITTED"
        assert fixture.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
            "WHERE window_kind IN ('WINDOW_1H','WINDOW_4H')"
        ).fetchone()[0] == 0
    finally:
        fixture.close()


def test_mixed_pre_15m_exclusion_does_not_block_healthy_peer_4h() -> None:
    """GREEN B: the real sibling keeps the existing 1h -> 4h path."""
    from printer_v1.db.migrate import canonical_migration_count, canonical_migration_names
    from printer_v1.operator_cli import one_command_15m_factory as factory
    from printer_v1.operator_cli.campaign_supervision import acquire_campaign_supervision
    from printer_v1.operator_cli.operational_database_target_binding import (
        PRODUCTION_AUTHORITATIVE,
        build_operational_database_target_binding,
    )
    from printer_v1.operator_cli.operational_selective_1h import (
        reconcile_1h_terminal_lifecycle,
    )
    from printer_v1.operator_cli.campaign_ownership import transition_state
    from printer_v1.operator_cli.standard_4h_progression import (
        commit_standard_4h_progression_handoff,
        evaluate_standard_4h_progression,
    )
    from tests import (
        test_v2_9_8b_post_dtw100_standard_four_hour_activation_factory_barrier
        as activation_fixture,
    )
    from tests.test_v2_9_8b_operational_selective_1h import (
        Selective1hFixture,
        T15,
        T1H,
        _iso,
    )

    fixture = Selective1hFixture(standard_four_hour_campaign=True)
    try:
        fixture.prepare_eligible(token_id=2, window_id=202, outcome="CONSOLIDATION")
        _seed_exact_pre_15m_failure(fixture, token_id=1)
        with fixture.connection:
            fixture.connection.execute(
                """UPDATE printer_memory_factory_run_steps SET snapshot_id=5002
                   WHERE run_id='factory-run-1' AND token_id=2
                     AND step_kind='WINDOW_CLOSE'"""
            )
        first_hour = factory._run_selective_1h_campaign_barrier(
            fixture.connection,
            db_path=str(fixture.db),
            run_id="factory-run-1",
            config={
                "campaign_id": "campaign-1h",
                "campaign_run_id": "run-1h",
                "configuration_id": "config-1h",
                "cycle_id": "cycle-1h",
            },
            continuation_seconds=16.0,
        )
        assert first_hour["evaluation_reached"] is True

        connection = fixture.connection
        campaign_1h = str(
            connection.execute(
                "SELECT window_id FROM printer_memory_factory_campaign_windows "
                "WHERE token_slot_id='slot-2' AND window_kind='WINDOW_1H'"
            ).fetchone()[0]
        )
        with connection:
            connection.execute(
                """INSERT INTO printer_token_snapshots(
                       id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                       source_status,data_quality_label)
                   VALUES (12020,2,2,?,'TRACK_NORMAL','TOKEN','COMPLETE','CLEAN_DATA'),
                          (12021,2,2,?,'TRACK_NORMAL','TOKEN','COMPLETE','CLEAN_DATA')""",
                (_iso(T15), _iso(T1H)),
            )
            connection.execute(
                """INSERT INTO printer_memory_windows(
                       id,token_id,pair_id,window_kind,opened_at,closed_at,
                       window_start_at,window_end_at,snapshot_start_id,snapshot_end_id,
                       memory_status,data_quality_label,window_status,
                       memory_quality_label,outcome_label,do_not_train,
                       supporting_context_json)
                   VALUES (13002,2,2,'WINDOW_1H',?,?,?,?,12020,12021,
                           'PARTIAL_MEMORY','CLEAN_DATA','WINDOW_CLOSED',
                           'PARTIAL_MEMORY','CONSOLIDATION',0,'{}')""",
                (_iso(T15), _iso(T1H), _iso(T15), _iso(T1H)),
            )
            episode_id = int(
                connection.execute(
                    """INSERT INTO printer_episodes(
                           memory_window_id,token_id,pair_id,episode_kind,
                           episode_status,memory_status,data_quality_label,
                           do_not_train,window_kind,memory_quality_label,
                           episode_outcome_label)
                       VALUES (13002,2,2,'WINDOW_1H_CLEAN_MEMORY','COMPLETE',
                               'CLEAN_MEMORY','CLEAN_DATA',0,'WINDOW_1H',
                               'CLEAN_MEMORY','CONSOLIDATION')"""
                ).lastrowid
            )
            connection.execute(
                """INSERT INTO printer_memory_fingerprints(
                       episode_id,fingerprint_kind,fingerprint_payload_json,
                       memory_status,data_quality_label,do_not_train)
                   VALUES (?,'STATIC_CONDITION_SUMMARY',?,
                           'CLEAN_MEMORY','CLEAN_DATA',0)""",
                (
                    episode_id,
                    json.dumps(
                        {
                            "episode_id": episode_id,
                            "window_id": 13002,
                            "token_id": 2,
                            "pair_id": 2,
                            "window_kind": "WINDOW_1H",
                        },
                        sort_keys=True,
                    ),
                ),
            )
            close = connection.execute(
                """SELECT id,scheduler_job_id
                   FROM printer_memory_factory_run_steps
                   WHERE run_id='factory-run-1' AND token_id=2
                     AND step_kind IN ('CONTINUATION_CLOSE','CONTINUATION_CLOSE_AUDIT')"""
            ).fetchone()
            assert close is not None
            connection.execute(
                """UPDATE printer_memory_factory_run_steps
                   SET step_status='SUCCEEDED',finished_at=?,tracking_lane='TRACK_NORMAL',
                       snapshot_id=12021,memory_window_id=13002,result_json=?
                   WHERE id=?""",
                (
                    _iso(T1H),
                    json.dumps({"ok": True, "memory_window_id": 13002}),
                    int(close["id"]),
                ),
            )
            job_ids = [
                int(row[0])
                for row in connection.execute(
                    """SELECT scheduler_job_id
                       FROM printer_memory_factory_run_steps
                       WHERE run_id='factory-run-1' AND token_id=2
                         AND step_kind LIKE 'CONTINUATION_%'"""
                ).fetchall()
            ]
            assert job_ids
            placeholders = ",".join("?" for _ in job_ids)
            connection.execute(
                f"UPDATE printer_memory_factory_run_steps SET step_status='SUCCEEDED',"
                f"finished_at=? WHERE scheduler_job_id IN ({placeholders})",
                (_iso(T1H), *job_ids),
            )
            connection.execute(
                f"UPDATE printer_scheduler_jobs SET status='SUCCEEDED',finished_at=?,"
                f"locked_at=NULL,lock_owner=NULL,last_error=NULL "
                f"WHERE id IN ({placeholders})",
                (_iso(T1H), *job_ids),
            )
            connection.execute(
                f"UPDATE printer_memory_factory_campaign_scheduler_work "
                f"SET work_state='SUCCEEDED',first_terminal_cause='fixture_clean_1h',"
                f"terminal_at=?,updated_at=? WHERE scheduler_job_id IN ({placeholders})",
                (_iso(T1H), _iso(T1H), *job_ids),
            )

        transition_state(
            connection,
            record_kind="window",
            identity=campaign_1h,
            expected_state="PLANNED",
            new_state="COLLECTING",
            now=_iso(T1H),
        )
        transition_state(
            connection,
            record_kind="window",
            identity=campaign_1h,
            expected_state="COLLECTING",
            new_state="CLOSE_PENDING",
            now=_iso(T1H),
        )
        reconcile_1h_terminal_lifecycle(
            connection,
            campaign_window_1h_id=campaign_1h,
            terminal_state="CLEAN_PROMOTED",
            terminal_cause="fixture_clean_1h",
            memory_window_row_id=13002,
            now=_iso(T1H),
        )
        authority = activation_fixture.StandardFourHourActivationFactoryBarrierTests()
        authority.fx = fixture
        candidate = {
            "token_row_id": 2,
            "pair_row_id": 2,
            "mint_identity": "mint-2",
            "pair_identity": "pair-2",
            "memory_window_1h_id": 13002,
        }
        authority._attach_acceptable_safety(2, candidate)
        with connection:
            connection.execute(
                "UPDATE printer_memory_factory_campaign_cycles SET cycle_state='TRACKING' "
                "WHERE cycle_id='cycle-1h'"
            )
        acquire_campaign_supervision(
            fixture.db,
            lock_path=fixture.db.with_suffix(".mixed-4h.lease.json"),
            supervision_id="mixed-4h-supervision",
            campaign_id="campaign-1h",
            configuration_id="config-1h",
            run_id="run-1h",
            owner_id="mixed-4h-owner",
            lease_seconds=3600,
        )
        binding = build_operational_database_target_binding(
            target_kind=PRODUCTION_AUTHORITATIVE,
            resolved_db_path=fixture.db,
            authorized_pre_mutation_sha256="a" * 64,
            migration_count=canonical_migration_count(),
            migration_head=canonical_migration_names()[-1],
            authorization_id="lane3-authorization",
            authorization_marker_sha256="b" * 64,
            application_marker_sha256="c" * 64,
            execution_id="lane3-execution",
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
            configuration_id="config-1h",
            authorization_consumed_once=True,
            invocation_count=1,
            allowed_invocation_count=1,
            automatic_retry_allowed=False,
            manual_rerun_allowed=False,
            resume_allowed=False,
            restart_allowed=False,
            successor_allowed=False,
        )
        evaluated = evaluate_standard_4h_progression(
            connection,
            db_path=str(fixture.db),
            campaign_id="campaign-1h",
            configuration_id="config-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
            factory_run_id="factory-run-1",
            operational_db_binding=binding,
            canonical_authoritative_db_path=str(fixture.db),
            cancellation_probe=lambda: None,
            now=_iso(T1H),
        )
        assert evaluated["eligible_token_slot_ids"] == ["slot-2"]
        committed = commit_standard_4h_progression_handoff(
            connection,
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
            factory_run_id="factory-run-1",
            db_path=str(fixture.db),
            configuration_id="config-1h",
            operational_db_binding=binding,
            canonical_authoritative_db_path=str(fixture.db),
            cancellation_probe=lambda: None,
            now=_iso(T1H),
        )
        assert committed["eligible_token_slot_ids"] == ["slot-2"]
        assert connection.execute(
            "SELECT attempt_state FROM printer_memory_factory_standard_4h_progression_attempts"
        ).fetchone()[0] == "HANDOFF_COMMITTED"
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
            "WHERE token_slot_id='slot-1' AND window_kind IN ('WINDOW_1H','WINDOW_4H')"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
            "WHERE token_slot_id='slot-2' AND window_kind='WINDOW_4H'"
        ).fetchone()[0] == 1
    finally:
        fixture.close()


@pytest.mark.parametrize(
    ("terminal_state", "terminal_cause"),
    (("FAILED", "DIFFERENT_CAUSE"), ("MANUAL_REVIEW", "DIFFERENT_CAUSE")),
)
def test_token_local_slot_marker_fails_closed_on_conflicting_terminal_truth(
    terminal_state,
    terminal_cause,
) -> None:
    from printer_v1.operator_cli import one_command_15m_factory as factory
    from printer_v1.operator_cli.campaign_ownership import (
        CampaignOwnershipError,
        transition_state,
    )
    from tests.test_v2_9_8b_operational_selective_1h import Selective1hFixture

    fixture = Selective1hFixture(standard_four_hour_campaign=True)
    try:
        transition_state(
            fixture.connection,
            record_kind="token_slot",
            identity="slot-1",
            expected_state="SELECTED",
            new_state=terminal_state,
            terminal_cause=terminal_cause,
            now=START.isoformat(),
        )
        before = tuple(
            fixture.connection.execute(
                "SELECT token_state,first_terminal_cause FROM "
                "printer_memory_factory_campaign_token_slots "
                "WHERE token_slot_id='slot-1'"
            ).fetchone()
        )
        with pytest.raises(CampaignOwnershipError):
            factory._mark_campaign_slot_token_local_failed(
                fixture.connection,
                campaign_id="campaign-1h",
                campaign_run_id="run-1h",
                cycle_id="cycle-1h",
                token_id=1,
            )
        after = tuple(
            fixture.connection.execute(
                "SELECT token_state,first_terminal_cause FROM "
                "printer_memory_factory_campaign_token_slots "
                "WHERE token_slot_id='slot-1'"
            ).fetchone()
        )
        assert after == before
    finally:
        fixture.close()


def test_token_local_slot_marker_exact_terminal_repeat_is_idempotent() -> None:
    from printer_v1.operator_cli import one_command_15m_factory as factory
    from tests.test_v2_9_8b_operational_selective_1h import Selective1hFixture

    fixture = Selective1hFixture(standard_four_hour_campaign=True)
    try:
        _seed_exact_pre_15m_failure(fixture, token_id=1)
        factory._mark_campaign_slot_token_local_failed(
            fixture.connection,
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
            token_id=1,
        )
        assert tuple(
            fixture.connection.execute(
                "SELECT token_state,first_terminal_cause FROM "
                "printer_memory_factory_campaign_token_slots "
                "WHERE token_slot_id='slot-1'"
            ).fetchone()
        ) == ("FAILED", TOKEN_LOCAL_FAILED)
    finally:
        fixture.close()


def test_drained_pre_15m_exclusion_cycle_accounts_token_to_cycle_cancelled(
    tmp_path,
) -> None:
    """RED/GREEN H: only an actual exclusion aggregate seals missing 15m."""
    from printer_v1.operator_cli.campaign_ownership import (
        persist_window,
        transition_state,
    )
    from tests.test_v2_9_8b_lane4_multi_cycle_terminal_accounting_bounded_proof import (
        CAMPAIGN,
        CAMPAIGN_RUN,
        CONFIGURATION,
        CYCLE_1,
        FACTORY_RUN,
        Lane4ProofDB,
        NOW,
        _EMPTY_FAULTS,
        _EMPTY_OBJECT,
    )

    proof = Lane4ProofDB(tmp_path)
    try:
        slots = proof.admit_cycle(CYCLE_1, 1, token_base=100)
        excluded, healthy = slots

        excluded_window = f"{CYCLE_1}:window-15m:{excluded['token_slot_id']}"
        persist_window(
            proof.connection,
            window_id=excluded_window,
            campaign_id=CAMPAIGN,
            run_id=CAMPAIGN_RUN,
            cycle_id=CYCLE_1,
            token_slot_id=str(excluded["token_slot_id"]),
            token_row_id=int(excluded["token_row_id"]),
            pair_row_id=int(excluded["pair_row_id"]),
            window_kind="WINDOW_15M",
            root_15m_lifecycle_identity=str(excluded["lifecycle_identity"]),
            checkpoint_cutoff=NOW,
            now=NOW,
        )
        transition_state(
            proof.connection,
            record_kind="window",
            identity=excluded_window,
            expected_state="PLANNED",
            new_state="BLOCKED",
            terminal_cause=TOKEN_LOCAL_FAILED,
            now=NOW,
        )
        failure_id = int(
            proof.connection.execute(
                """INSERT INTO printer_source_failures(
                       source_name,request_kind,failed_at,failure_type,
                       failure_message,source_status,data_quality_label)
                   VALUES ('geckoterminal','pair_market_snapshot',?,
                           'DEX_AND_FALLBACK_FAILED','fixture failure',
                           'FAILED','MISSING_CRITICAL_DATA')""",
                (NOW,),
            ).lastrowid
        )
        failed_job = proof._step(
            cycle_id=CYCLE_1,
            token_id=int(excluded["token_row_id"]),
            pair_id=int(excluded["pair_row_id"]),
            mint=str(excluded["mint_identity"]),
            pair_address=str(excluded["pair_identity"]),
            step_kind="SNAPSHOT",
            memory_window_id=None,
            snapshot_id=None,
        )
        failed_step_id = int(
            proof.connection.execute(
                "SELECT id FROM printer_memory_factory_run_steps "
                "WHERE scheduler_job_id=?",
                (failed_job,),
            ).fetchone()[0]
        )
        proof.connection.execute(
            """UPDATE printer_memory_factory_run_steps
               SET step_status='FAILED',source_failure_id=?,
                   error_or_skip_reason=?,finished_at=? WHERE id=?""",
            (failure_id, TOKEN_LOCAL_FAILED, NOW, failed_step_id),
        )
        proof.connection.execute(
            "UPDATE printer_scheduler_jobs SET status='FAILED',last_error=?,"
            "finished_at=? WHERE id=?",
            (TOKEN_LOCAL_FAILED, NOW, failed_job),
        )
        proof._own_job(
            cycle_id=CYCLE_1,
            slot_id=str(excluded["token_slot_id"]),
            window_id=excluded_window,
            job_id=failed_job,
            stage_id="WINDOW_15M_SLOT_1",
        )
        proof.connection.execute(
            """UPDATE printer_memory_factory_campaign_scheduler_work
               SET work_state='FAILED',first_terminal_cause=?,terminal_at=?,updated_at=?
               WHERE scheduler_job_id=?""",
            (TOKEN_LOCAL_FAILED, NOW, NOW, failed_job),
        )
        transition_state(
            proof.connection,
            record_kind="token_slot",
            identity=str(excluded["token_slot_id"]),
            expected_state="SELECTED",
            new_state="FAILED",
            terminal_cause=TOKEN_LOCAL_FAILED,
            now=NOW,
        )

        token_id = int(healthy["token_row_id"])
        pair_id = int(healthy["pair_row_id"])
        memory_15m = proof._memory_window(
            token_id=token_id,
            pair_id=pair_id,
            window_kind="WINDOW_15M",
            clean=True,
        )
        memory_1h = proof._memory_window(
            token_id=token_id,
            pair_id=pair_id,
            window_kind="WINDOW_1H",
            clean=True,
        )
        jobs_15m = []
        for _ in range(8):
            jobs_15m.append(
                proof._step(
                    cycle_id=CYCLE_1,
                    token_id=token_id,
                    pair_id=pair_id,
                    mint=str(healthy["mint_identity"]),
                    pair_address=str(healthy["pair_identity"]),
                    step_kind="SNAPSHOT",
                    memory_window_id=None,
                    snapshot_id=proof._snapshot(token_id, pair_id),
                )
            )
        jobs_15m.append(
            proof._step(
                cycle_id=CYCLE_1,
                token_id=token_id,
                pair_id=pair_id,
                mint=str(healthy["mint_identity"]),
                pair_address=str(healthy["pair_identity"]),
                step_kind="WINDOW_CLOSE",
                memory_window_id=memory_15m,
                snapshot_id=proof._snapshot(token_id, pair_id),
            )
        )
        healthy_15m = f"{CYCLE_1}:window-15m:{healthy['token_slot_id']}"
        persist_window(
            proof.connection,
            window_id=healthy_15m,
            campaign_id=CAMPAIGN,
            run_id=CAMPAIGN_RUN,
            cycle_id=CYCLE_1,
            token_slot_id=str(healthy["token_slot_id"]),
            token_row_id=token_id,
            pair_row_id=pair_id,
            window_kind="WINDOW_15M",
            root_15m_lifecycle_identity=str(healthy["lifecycle_identity"]),
            checkpoint_cutoff=NOW,
            memory_window_row_id=memory_15m,
            now=NOW,
        )
        transition_state(
            proof.connection,
            record_kind="window",
            identity=healthy_15m,
            expected_state="PLANNED",
            new_state="CLEAN_PROMOTED",
            terminal_cause="FIXTURE_15M_CLOSED",
            now=NOW,
        )
        jobs_1h = []
        for _ in range(12):
            jobs_1h.append(
                proof._step(
                    cycle_id=CYCLE_1,
                    token_id=token_id,
                    pair_id=pair_id,
                    mint=str(healthy["mint_identity"]),
                    pair_address=str(healthy["pair_identity"]),
                    step_kind="CONTINUATION_SNAPSHOT",
                    memory_window_id=None,
                    snapshot_id=proof._snapshot(token_id, pair_id),
                )
            )
        jobs_1h.append(
            proof._step(
                cycle_id=CYCLE_1,
                token_id=token_id,
                pair_id=pair_id,
                mint=str(healthy["mint_identity"]),
                pair_address=str(healthy["pair_identity"]),
                step_kind="CONTINUATION_CLOSE",
                memory_window_id=memory_1h,
                snapshot_id=proof._snapshot(token_id, pair_id),
            )
        )
        healthy_1h = f"{CYCLE_1}:window-1h:{healthy['token_slot_id']}"
        persist_window(
            proof.connection,
            window_id=healthy_1h,
            campaign_id=CAMPAIGN,
            run_id=CAMPAIGN_RUN,
            cycle_id=CYCLE_1,
            token_slot_id=str(healthy["token_slot_id"]),
            token_row_id=token_id,
            pair_row_id=pair_id,
            window_kind="WINDOW_1H",
            root_15m_lifecycle_identity=str(healthy["lifecycle_identity"]),
            checkpoint_cutoff=NOW,
            predecessor_window_id=healthy_15m,
            memory_window_row_id=memory_1h,
            now=NOW,
        )
        transition_state(
            proof.connection,
            record_kind="window",
            identity=healthy_1h,
            expected_state="PLANNED",
            new_state="CLEAN_PROMOTED",
            terminal_cause="FIXTURE_1H_CLOSED",
            now=NOW,
        )
        for job_id in jobs_15m:
            proof._own_job(
                cycle_id=CYCLE_1,
                slot_id=str(healthy["token_slot_id"]),
                window_id=healthy_15m,
                job_id=job_id,
                stage_id="WINDOW_15M_SLOT_2",
            )
        for job_id in jobs_1h:
            proof._own_job(
                cycle_id=CYCLE_1,
                slot_id=str(healthy["token_slot_id"]),
                window_id=healthy_1h,
                job_id=job_id,
                stage_id="WINDOW_1H",
            )
        transition_state(
            proof.connection,
            record_kind="token_slot",
            identity=str(healthy["token_slot_id"]),
            expected_state="SELECTED",
            new_state="COOLDOWN",
            terminal_cause="OWNED_TERMINAL_WINDOW_COOLDOWN",
            now=NOW,
        )

        attempt_id = f"progression-{CYCLE_1}"
        proof.connection.execute(
            """INSERT INTO printer_memory_factory_standard_4h_progression_attempts(
                   progression_attempt_id,campaign_id,configuration_id,
                   campaign_run_id,factory_run_id,cycle_id,policy_version,
                   attempt_state,authority_evidence_json,first_terminal_cause,
                   fault_details_json,eligibility_completed_at,handoff_committed_at,
                   terminal_at,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,'HANDOFF_COMMITTED',?,NULL,?,?,?,?,?,?)""",
            (
                attempt_id,
                CAMPAIGN,
                CONFIGURATION,
                CAMPAIGN_RUN,
                FACTORY_RUN,
                CYCLE_1,
                "STANDARD_4H_PROGRESSION_V1",
                _EMPTY_OBJECT,
                _EMPTY_FAULTS,
                NOW,
                NOW,
                NOW,
                NOW,
                NOW,
            ),
        )
        exclusion_evidence = {
            "producer": "campaign_ownership.persist_standard_first_hour_handoff_set",
            "boundary_kind": "PRE_15M_TOKEN_LOCAL_TERMINAL_EXCLUSION",
            "campaign_id": CAMPAIGN,
            "campaign_run_id": CAMPAIGN_RUN,
            "cycle_id": CYCLE_1,
            "slot_ordinal": 1,
            "token_slot_id": str(excluded["token_slot_id"]),
            "token_row_id": int(excluded["token_row_id"]),
            "mint_identity": str(excluded["mint_identity"]),
            "pair_row_id": int(excluded["pair_row_id"]),
            "pair_identity": str(excluded["pair_identity"]),
            "lifecycle_identity": str(excluded["lifecycle_identity"]),
            "tracking_queue_id": int(excluded["tracking_queue_id"]),
            "tracking_lane": "TRACK_NORMAL",
            "failed_factory_step_id": failed_step_id,
            "failed_step_kind": "SNAPSHOT",
            "source_failure_id": failure_id,
            "terminal_cause": TOKEN_LOCAL_FAILED,
            "exclusion_reason": "PRE_15M_TOKEN_LOCAL_TERMINAL_FAILURE",
            "terminal_at": NOW,
            "no_valid_successful_memory_backed_window_15m": True,
        }
        progression_rows = (
            (
                excluded,
                None,
                None,
                ["PRE_15M_TOKEN_LOCAL_TERMINAL_FAILURE"],
                exclusion_evidence,
            ),
            (
                healthy,
                healthy_1h,
                memory_1h,
                ["NO_WINDOW_4H_ELIGIBLE_CONTINUATION"],
                {"predecessor_state": "SUCCEEDED"},
            ),
        )
        for slot, predecessor_id, predecessor_memory_id, reasons, evidence in progression_rows:
            proof.connection.execute(
                """INSERT INTO printer_memory_factory_standard_4h_progression_tokens(
                       progression_token_id,progression_attempt_id,campaign_id,
                       campaign_run_id,factory_run_id,cycle_id,slot_ordinal,
                       token_slot_id,token_identity,token_row_id,mint_identity,
                       pair_identity,pair_row_id,lifecycle_identity,
                       tracking_queue_id,tracking_lane,predecessor_window_1h_id,
                       predecessor_memory_window_id,token_disposition,
                       disposition_reasons_json,eligibility_evidence_json,
                       successor_window_4h_id,first_terminal_cause,
                       fault_details_json,evaluated_at,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'INELIGIBLE',
                           ?,?,NULL,NULL,?,?,?,?)""",
                (
                    f"progression-token-{slot['token_slot_id']}",
                    attempt_id,
                    CAMPAIGN,
                    CAMPAIGN_RUN,
                    FACTORY_RUN,
                    CYCLE_1,
                    int(slot["slot_ordinal"]),
                    slot["token_slot_id"],
                    slot["token_identity"],
                    int(slot["token_row_id"]),
                    slot["mint_identity"],
                    slot["pair_identity"],
                    int(slot["pair_row_id"]),
                    slot["lifecycle_identity"],
                    int(slot["tracking_queue_id"]),
                    "TRACK_NORMAL",
                    predecessor_id,
                    predecessor_memory_id,
                    json.dumps(reasons),
                    json.dumps(evidence, sort_keys=True),
                    _EMPTY_FAULTS,
                    NOW,
                    NOW,
                    NOW,
                ),
            )
        proof.connection.commit()

        result = proof.derive_cycle(CYCLE_1)
        assert result["execution_outcome"] == "CANCELLED_STOPPED", result[
            "incomplete_reasons"
        ]
        assert result["accounting_complete"] is True
        assert result["requires_review"] is False
        assert result["primary_fault"]["cause"] == TOKEN_LOCAL_FAILED
        assert result["primary_fault"]["origin_scope"] == "TOKEN"
        assert result["primary_fault"]["effect_scope"] == "CYCLE"
    finally:
        proof.close()


def test_ordinary_no_window_1h_planned_remains_terminal_success(tmp_path) -> None:
    """GREEN E: ordinary selective stop never enters the exclusion rule."""
    from printer_v1.operator_cli.campaign_ownership import (
        register_campaign_window_close,
        transition_state,
    )
    from tests.test_v2_9_8b_lane4_multi_cycle_terminal_accounting_bounded_proof import (
        CYCLE_1,
        Lane4ProofDB,
        NOW,
    )

    proof = Lane4ProofDB(tmp_path)
    try:
        slots = proof.admit_cycle(CYCLE_1, 1, token_base=100)
        for slot in slots:
            token_id = int(slot["token_row_id"])
            pair_id = int(slot["pair_row_id"])
            slot_id = str(slot["token_slot_id"])
            mint = str(slot["mint_identity"])
            pair_identity = str(slot["pair_identity"])
            memory_15m = proof._memory_window(
                token_id=token_id,
                pair_id=pair_id,
                window_kind="WINDOW_15M",
                clean=True,
            )
            jobs: list[int] = []
            for _ in range(8):
                jobs.append(
                    proof._step(
                        cycle_id=CYCLE_1,
                        token_id=token_id,
                        pair_id=pair_id,
                        mint=mint,
                        pair_address=pair_identity,
                        step_kind="SNAPSHOT",
                        memory_window_id=None,
                        snapshot_id=proof._snapshot(token_id, pair_id),
                    )
                )
            close_job = proof._step(
                cycle_id=CYCLE_1,
                token_id=token_id,
                pair_id=pair_id,
                mint=mint,
                pair_address=pair_identity,
                step_kind="WINDOW_CLOSE",
                memory_window_id=memory_15m,
                snapshot_id=proof._snapshot(token_id, pair_id),
            )
            jobs.append(close_job)
            close_step_id = int(
                proof.connection.execute(
                    "SELECT id FROM printer_memory_factory_run_steps "
                    "WHERE scheduler_job_id=?",
                    (close_job,),
                ).fetchone()[0]
            )
            window_15m = f"{CYCLE_1}:window-15m:{slot_id}"
            register_campaign_window_close(
                proof.connection,
                campaign_id=proof.context(CYCLE_1).campaign_id,
                run_id=proof.context(CYCLE_1).campaign_run_id,
                cycle_id=CYCLE_1,
                factory_run_id=proof.context(CYCLE_1).factory_run_id,
                token_slot_id=slot_id,
                window_id=window_15m,
                close_step_id=close_step_id,
                memory_window_row_id=memory_15m,
                root_15m_lifecycle_identity=str(slot["lifecycle_identity"]),
                checkpoint_cutoff=NOW,
                terminal_window_state="CLEAN_PROMOTED",
                terminal_cause="FIXTURE_15M_CLOSED",
                now=NOW,
            )
            stage_id = (
                "WINDOW_15M_SLOT_1"
                if int(slot["slot_ordinal"]) == 1
                else "WINDOW_15M_SLOT_2"
            )
            for job_id in jobs:
                proof._own_job(
                    cycle_id=CYCLE_1,
                    slot_id=slot_id,
                    window_id=window_15m,
                    job_id=job_id,
                    stage_id=stage_id,
                )
            transition_state(
                proof.connection,
                record_kind="token_slot",
                identity=slot_id,
                expected_state="SELECTED",
                new_state="WINDOW_15M_ACTIVE",
                now=NOW,
            )
            transition_state(
                proof.connection,
                record_kind="token_slot",
                identity=slot_id,
                expected_state="WINDOW_15M_ACTIVE",
                new_state="WINDOW_15M_CLOSED",
                now=NOW,
            )

        proof._seed_ineligible_progression(
            CYCLE_1,
            slots,
            reason="NO_WINDOW_1H_PLANNED",
        )
        transition_state(
            proof.connection,
            record_kind="cycle",
            identity=CYCLE_1,
            expected_state="PLANNED",
            new_state="TERMINAL_COMPLETED",
            terminal_cause="COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
            now=NOW,
        )
        proof.connection.commit()

        result = proof.derive_cycle(CYCLE_1)
        assert result["execution_outcome"] == "TERMINAL_SUCCESS", result[
            "incomplete_reasons"
        ]
        assert result["execution_outcome"] != "CANCELLED_STOPPED"
        assert result["accounting_complete"] is True
        assert result["requires_review"] is False
        assert result["pre_15m_terminal_exclusions"] == ()
        assert all(
            token["progression"]["reasons"] == ["NO_WINDOW_1H_PLANNED"]
            for token in result["tokens"]
        )
    finally:
        proof.close()


def test_token_local_dex_gecko_failure_isolates_peer_and_preserves_cycle2_clean(
    tmp_path, monkeypatch
) -> None:
    """Full factory seam: token-local source failure stays token/cycle local."""
    from printer_v1.operator_cli import one_command_15m_factory as factory
    from printer_v1.operator_cli import multi_cycle_campaign_coordinator as coordinator
    from printer_v1.discovery import pre_admission_materialization as materialization
    from printer_v1.operator_cli import operational_standard_4h as standard_4h
    from printer_v1.operator_cli import standard_4h_progression as progression
    from printer_v1.operator_cli import authoritative_admission_health
    from printer_v1.sources.dexscreener import fixture_success_transport as dex_transport
    from printer_v1.sources.geckoterminal import (
        fixture_success_transport as gt_transport,
    )

    db, backup, disposable_binding = _prepare(tmp_path)
    observations: dict[str, object] = {
        "failed_mint_snapshot_calls": 0,
        "fallback_calls": [],
        "shared_terminalizer_calls": [],
        "mixed_boundaries": [],
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
    original_register = factory._register_repaired_campaign_window_before_terminalization
    original_barrier = factory._run_selective_1h_campaign_barrier
    original_standard_barrier = standard_4h.run_standard_four_hour_campaign_barrier

    def plan_future_cycle1_opening(connection, run_id, targets, now, **kwargs):
        cycle_ordinal = int(kwargs.get("cycle_ordinal") or 1)
        original_plan(connection, run_id, targets, now, **kwargs)
        if cycle_ordinal != 1:
            return
        due = (now + timedelta(seconds=100)).isoformat()
        connection.execute(
            "UPDATE printer_memory_factory_run_steps SET scheduled_for=? WHERE run_id=?",
            (due, run_id),
        )
        connection.execute(
            "UPDATE printer_scheduler_jobs SET scheduled_for=? WHERE id IN ("
            "SELECT scheduler_job_id FROM printer_memory_factory_run_steps "
            "WHERE run_id=?)",
            (due, run_id),
        )

    def register_with_clean(conn, *, step, result, ownership_context):
        mint = str(step["token_mint"])
        mw_id = result.get("memory_window_id")
        if mw_id is not None and mint != FAILED_MINT:
            _ensure_clean_episode(conn, int(mw_id))
        return original_register(
            conn,
            step=step,
            result=result,
            ownership_context=ownership_context,
        )

    def barrier_probe(conn, **kwargs):
        out = original_barrier(conn, **kwargs)
        evaluation = out.get("evaluation") or {}
        if evaluation.get("terminal_exclusions"):
            observations["mixed_boundaries"].append(dict(out))
        return out

    def snapshot_factory(*, token_mint, timeout_seconds):
        del timeout_seconds
        if token_mint == FAILED_MINT:
            observations["failed_mint_snapshot_calls"] = (
                int(observations["failed_mint_snapshot_calls"]) + 1
            )
            return build_dexscreener_adapter(
                enabled=True,
                fixture_transport=dex_transport(
                    _dex_failure_payload("dexscreener_transport_failure")
                ),
            )
        payload = _dex_success_pairs(token_mint)

        class VirtualClockSnapshotAdapter:
            def __init__(self) -> None:
                self._inner = build_dexscreener_adapter(
                    enabled=True,
                    fixture_transport=dex_transport(payload),
                )

            def __getattr__(self, name):
                return getattr(self._inner, name)

            def execute(self, context):
                return replace(
                    self._inner.execute(context),
                    received_at=clock.now().isoformat(),
                )

        return VirtualClockSnapshotAdapter()

    def fallback_factory(*, pair_address, token_mint, timeout_seconds):
        del pair_address, timeout_seconds
        observations["fallback_calls"].append(token_mint)
        return build_geckoterminal_adapter(
            enabled=True,
            fixture_transport=gt_transport(_gt_failure_payload()),
        )

    def admit(**kwargs):
        connection = kwargs["connection"]
        from printer_v1.operator_cli.cadence_authority import (
            claim_tracking_authority_for_slot_insert,
        )

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
        queue_ids = tuple(
            claim_tracking_authority_for_slot_insert(
                connection,
                token_row_id=row_id,
                pair_row_id=100 + row_id,
                tracking_lane="TRACK_NORMAL",
                now=clock.now(),
            )
            for row_id in (3, 4)
        )
        slots = []
        for ordinal, row_id in enumerate((3, 4), start=1):
            slot = _slot(row_id, ordinal, tracking_queue_id=queue_ids[ordinal - 1])
            slot["token_slot_id"] = f"t{ordinal}_c0002_slot"
            slots.append(slot)
        create_cycle_with_two_slots(
            connection,
            campaign_id=CAMPAIGN_ID,
            run_id=CAMPAIGN_RUN_ID,
            cycle_id=CYCLE2_ID,
            cycle_ordinal=2,
            slots=tuple(slots),
            now=clock.now().isoformat(),
            commit_transaction=True,
        )
        return SimpleNamespace(mutation_performed=True, cycle_id=CYCLE2_ID)

    def materialize(**_kwargs):
        return None

    def shared_terminalizer(*, terminal_cause, run_status):
        observations["shared_terminalizer_calls"].append(
            {"terminal_cause": terminal_cause, "run_status": run_status}
        )
        assert str(terminal_cause) != STOP_SOURCE
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

    def standard_barrier_probe(*args, **kwargs):
        return original_standard_barrier(*args, **kwargs)

    # Cycle 1 must commit its truthful zero-successor handoff. Cycle 2's later
    # 4h runtime remains outside this disposable full-factory seam.
    monkeypatch.setattr(
        standard_4h, "run_standard_four_hour_campaign_barrier", standard_barrier_probe
    )
    # This is an explicitly disposable composition DB. Keep the real progression
    # and no-op handoff owners while replacing only production-path DB binding
    # validation, which is proven separately by its own focused contracts.
    monkeypatch.setattr(
        progression,
        "validate_operational_database_target_binding",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        authoritative_admission_health,
        "project_scheduler_health",
        lambda *args, **kwargs: (
            authoritative_admission_health.SchedulerHealthProjection(
                scheduler_budget_available=True,
                scheduler_due_work_healthy=True,
                attributable_job_count=0,
                attributable_job_ids=(),
                cycle_one_scheduler_ceiling=222,
                second_cycle_scheduler_envelope=222,
                four_token_scheduler_ceiling=444,
                recheck_on_lifecycle_change=False,
                reasons=(),
            )
        ),
    )
    monkeypatch.setattr(factory, "_now", clock.now)
    monkeypatch.setattr(factory, "_plan_opening_jobs", plan_future_cycle1_opening)
    monkeypatch.setattr(
        factory,
        "_register_repaired_campaign_window_before_terminalization",
        register_with_clean,
    )
    monkeypatch.setattr(factory, "_run_selective_1h_campaign_barrier", barrier_probe)

    # Disposable CLEAN_PROMOTED fixtures for healthy Cycle-2 / peer closes:
    # authoritative promotion returns CLEAN so campaign windows terminalize
    # CLEAN_PROMOTED and survive finalization.
    from printer_v1.operator_cli import operational_selective_1h as selective_1h

    def clean_promotion_facts(
        db_path, *, campaign_id, run_id, cycle_id, token_slot_id, campaign_window_id
        ):
            if "c0002" in str(token_slot_id):
                return {
                    "authority": "B.1_AUTHORITATIVE_PROMOTION",
                    "promotion_status": "CLEAN_PROMOTED",
                    "authoritative_episode_id": None,
                    "blocked_reason": None,
                    "campaign_id": campaign_id,
                    "run_id": run_id,
                    "cycle_id": cycle_id,
                    "token_slot_id": token_slot_id,
                    "window_id": campaign_window_id,
                    "predecessor_memory_quality": "CLEAN_MEMORY",
                    "predecessor_evidence_eligible": True,
                }
            return {
                "authority": "B.1_AUTHORITATIVE_PROMOTION",
                "promotion_status": "NO_PROMOTION",
                "authoritative_episode_id": None,
                "blocked_reason": "cycle1_or_failed_excluded",
            "campaign_id": campaign_id,
            "run_id": run_id,
            "cycle_id": cycle_id,
            "token_slot_id": token_slot_id,
            "window_id": campaign_window_id,
        }

    monkeypatch.setattr(selective_1h, "_promotion_facts", clean_promotion_facts)
    monkeypatch.setattr(coordinator, "admit_two_token_cycle_from_attempt", admit)
    monkeypatch.setattr(
        materialization, "materialize_consumed_pre_admission_pair", materialize
    )
    from printer_v1.operator_cli.campaign_supervision import acquire_campaign_supervision

    acquire_campaign_supervision(
        db,
        lock_path=db.with_suffix(".aug30-integration.lease.json"),
        supervision_id="aug30-integration-supervision",
        campaign_id=CAMPAIGN_ID,
        configuration_id=CONFIGURATION_ID,
        run_id=CAMPAIGN_RUN_ID,
        owner_id="aug30-integration-owner",
        lease_seconds=3600,
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
        _window_seconds=8,
        _continuation_seconds=16,
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
        four_token_health_projector=lambda _c, _n: _healthy_projection(),
        four_token_shared_terminalizer=shared_terminalizer,
        source_governor_owner=OwnerPort(SOURCE_GOVERNOR_OWNER, True),
        central_scheduler_owner=OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
        snapshot_adapter_factory=snapshot_factory,
        fallback_snapshot_adapter_factory=fallback_factory,
        context_adapter_factories=context_factories,
        _sleep=clock.sleep,
        _monotonic=clock.monotonic,
    )

    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        cycles = connection.execute(
            "SELECT cycle_ordinal,cycle_id,cycle_state,first_terminal_cause FROM "
            "printer_memory_factory_campaign_cycles "
            "WHERE campaign_id=? AND run_id=? ORDER BY cycle_ordinal",
            (CAMPAIGN_ID, CAMPAIGN_RUN_ID),
        ).fetchall()
        failed_steps = connection.execute(
            "SELECT step_key,step_status,token_mint,source_failure_id,"
            "snapshot_id,memory_window_id FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND token_mint=? AND step_status='FAILED' ORDER BY id",
            (FACTORY_RUN_ID, FAILED_MINT),
        ).fetchall()
        failed_slot = connection.execute(
            "SELECT token_state,first_terminal_cause FROM "
            "printer_memory_factory_campaign_token_slots "
            "WHERE cycle_id=? AND token_row_id=1",
            (CYCLE_ID,),
        ).fetchone()
        peer_close = connection.execute(
            "SELECT s.step_key,s.step_status,s.error_or_skip_reason,j.status AS job_status "
            "FROM printer_memory_factory_run_steps AS s "
            "JOIN printer_scheduler_jobs AS j ON j.id=s.scheduler_job_id "
            "WHERE s.run_id=? AND s.token_mint=? "
            "AND s.step_kind IN ('WINDOW_CLOSE','WINDOW_CLOSE_AUDIT') "
            "ORDER BY s.id",
            (FACTORY_RUN_ID, PEER_MINT),
        ).fetchall()
        peer_failed_source = connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND token_mint=? AND step_status='FAILED' "
            "AND source_failure_id IS NOT NULL",
            (FACTORY_RUN_ID, PEER_MINT),
        ).fetchone()[0]
        peer_cancelled_local = connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND token_mint=? AND step_status='CANCELLED' "
            "AND error_or_skip_reason=?",
            (FACTORY_RUN_ID, PEER_MINT, TOKEN_LOCAL_CANCELLED),
        ).fetchone()[0]
        cycle2_closes = connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND step_key LIKE '%_c0002_%' "
            "AND step_kind IN ('WINDOW_CLOSE','WINDOW_CLOSE_AUDIT') "
            "AND step_status='SUCCEEDED'",
            (FACTORY_RUN_ID,),
        ).fetchone()[0]
        cycle2_clean = connection.execute(
            "SELECT cw.token_slot_id,cw.window_state,mw.memory_quality_label "
            "FROM printer_memory_factory_campaign_windows AS cw "
            "JOIN printer_memory_windows AS mw ON mw.id=cw.memory_window_row_id "
            "WHERE cw.cycle_id=? AND cw.window_kind='WINDOW_15M' "
            "ORDER BY cw.token_slot_id",
            (CYCLE2_ID,),
        ).fetchall()
        durable_stop = connection.execute(
            "SELECT stop_reason,run_status FROM printer_memory_factory_runs "
            "WHERE run_id=?",
            (FACTORY_RUN_ID,),
        ).fetchone()
        source_failures = connection.execute(
            "SELECT source_name,failure_type FROM printer_source_failures ORDER BY id"
        ).fetchall()
        failed_snapshots = connection.execute(
            "SELECT COUNT(*) FROM printer_token_snapshots ts "
            "JOIN printer_tokens t ON t.id=ts.token_id WHERE t.token_mint=?",
            (FAILED_MINT,),
        ).fetchone()[0]
    finally:
        connection.close()

    assert len(cycles) == 2
    assert int(observations["failed_mint_snapshot_calls"]) >= 1
    assert FAILED_MINT in observations["fallback_calls"]
    assert observations["mixed_boundaries"], "expected Cycle-1 mixed boundary"

    # Failed token: Dex+Gecko, FAILED step, no invented success.
    assert failed_steps
    assert failed_steps[0]["source_failure_id"] is not None
    assert failed_steps[0]["snapshot_id"] is None
    assert failed_steps[0]["memory_window_id"] is None
    assert failed_snapshots == 0
    assert failed_slot is not None
    assert str(failed_slot["token_state"]) == "FAILED"
    assert str(failed_slot["first_terminal_cause"]) == TOKEN_LOCAL_FAILED
    names = {str(row["source_name"]) for row in source_failures}
    assert "dexscreener" in names and "geckoterminal" in names

    # Healthy Cycle-1 peer close remains SUCCEEDED; not contaminated.
    assert peer_close, "peer must reach WINDOW_CLOSE"
    assert all(str(row["step_status"]) == "SUCCEEDED" for row in peer_close)
    assert all(str(row["job_status"]) == "SUCCEEDED" for row in peer_close)
    assert peer_failed_source == 0
    assert peer_cancelled_local == 0
    assert all(
        STOP_SOURCE not in str(row["error_or_skip_reason"] or "")
        and "dexscreener_transport_failure" not in str(row["error_or_skip_reason"] or "")
        for row in peer_close
    )

    # Cycle 2 ordinary 15m + CLEAN_PROMOTED survives.
    assert cycle2_closes >= 1
    assert len(cycle2_clean) == 2, json.dumps(
        [dict(row) for row in cycle2_clean], default=str
    )
    assert all(str(row["window_state"]) == "CLEAN_PROMOTED" for row in cycle2_clean)
    assert all(
        str(row["memory_quality_label"]) == "CLEAN_MEMORY" for row in cycle2_clean
    )
    cycle2 = cycles[1]
    assert str(cycle2["first_terminal_cause"] or "") != STOP_SOURCE
    assert str(cycle2["first_terminal_cause"] or "") != "dexscreener_transport_failure"
    assert "CAMPAIGN_STOPPED_AFTER_PEER" not in str(cycle2["first_terminal_cause"] or "")

    # Shared truth: no false completion; no source-stop promotion.
    assert durable_stop["stop_reason"] != STOP_COMPLETED
    assert durable_stop["stop_reason"] != STOP_SOURCE
    assert durable_stop["run_status"] != "COMPLETED"
    assert str(cycles[0]["first_terminal_cause"] or "") != STOP_SOURCE
    assert observations["shared_terminalizer_calls"]
    assert all(
        call["terminal_cause"] != STOP_SOURCE
        for call in observations["shared_terminalizer_calls"]
    )
    assert report.get("four_token_terminal") is not None


def _seed_mark_helper_slot(tmp_path):
    """Minimal disposable campaign/slot graph for ownership-mark helper proofs."""
    from printer_v1.db import apply_migrations
    from printer_v1.operator_cli.cadence_authority import (
        claim_tracking_authority_for_slot_insert,
    )

    db = tmp_path / "mark-helper.sqlite3"
    apply_migrations(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    now = START.isoformat()
    conn.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES (?,?,?,?,?)",
        (CAMPAIGN_ID, "RUNNING", "OPERATIONAL_PERSISTENT", "db-1", "policy-1"),
    )
    conn.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json) VALUES (?,?,?,?,?)",
        (CONFIGURATION_ID, CAMPAIGN_ID, "a" * 64, "{}", '{"commit":"disposable"}'),
    )
    conn.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,created_at,updated_at) "
        "VALUES (?,?,1,'RUNNING',?,?)",
        (CAMPAIGN_RUN_ID, CAMPAIGN_ID, now, now),
    )
    for row_id in (1, 2):
        conn.execute(
            "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?,'solana')",
            (row_id, f"mint-{row_id}"),
        )
        conn.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
            "VALUES (?,?,?,?)",
            (100 + row_id, row_id, f"pool-{row_id}", f"mint-{row_id}"),
        )
    queue_ids = tuple(
        claim_tracking_authority_for_slot_insert(
            conn,
            token_row_id=row_id,
            pair_row_id=100 + row_id,
            tracking_lane="TRACK_NORMAL",
            now=START,
        )
        for row_id in (1, 2)
    )
    create_cycle_with_two_slots(
        conn,
        campaign_id=CAMPAIGN_ID,
        run_id=CAMPAIGN_RUN_ID,
        cycle_id=CYCLE_ID,
        cycle_ordinal=1,
        slots=(
            _slot(1, 1, tracking_queue_id=queue_ids[0]),
            _slot(2, 2, tracking_queue_id=queue_ids[1]),
        ),
        now=now,
    )
    conn.commit()
    return conn


def test_f1_mark_token_local_failed_accepts_exact_idempotent_durable_state(
    tmp_path, monkeypatch
) -> None:
    """F1: ownership conflict is success only when durable is exact FAILED+cause."""
    from printer_v1.operator_cli import campaign_ownership as ownership
    from printer_v1.operator_cli.one_command_15m_factory import (
        _mark_campaign_slot_token_local_failed,
    )

    conn = _seed_mark_helper_slot(tmp_path)
    token_slot_id = "t1_c0001_slot"
    transition_calls = {"count": 0}

    def raise_after_exact_persist(*_args, **_kwargs):
        transition_calls["count"] += 1
        now = START.isoformat()
        conn.execute(
            """UPDATE printer_memory_factory_campaign_token_slots
               SET token_state='FAILED',
                   first_terminal_cause=?,
                   terminal_at=?,
                   updated_at=?
               WHERE token_slot_id=?""",
            (TOKEN_LOCAL_FAILED, now, now, token_slot_id),
        )
        conn.commit()
        raise ownership.CampaignOwnershipError(
            "terminal state and first cause are immutable"
        )

    monkeypatch.setattr(ownership, "transition_state", raise_after_exact_persist)
    _mark_campaign_slot_token_local_failed(
        conn,
        campaign_id=CAMPAIGN_ID,
        campaign_run_id=CAMPAIGN_RUN_ID,
        cycle_id=CYCLE_ID,
        token_id=1,
    )
    row = conn.execute(
        """SELECT token_state, first_terminal_cause
           FROM printer_memory_factory_campaign_token_slots
           WHERE token_slot_id=?""",
        (token_slot_id,),
    ).fetchone()
    conn.close()

    assert transition_calls["count"] == 1
    assert str(row["token_state"]) == "FAILED"
    assert str(row["first_terminal_cause"]) == TOKEN_LOCAL_FAILED


def test_f2_mark_token_local_failed_propagates_conflicting_ownership_error(
    tmp_path, monkeypatch
) -> None:
    """F2: non-exact durable terminal after ownership error must propagate."""
    from printer_v1.operator_cli import campaign_ownership as ownership
    from printer_v1.operator_cli.one_command_15m_factory import (
        _mark_campaign_slot_token_local_failed,
    )

    conn = _seed_mark_helper_slot(tmp_path)
    token_slot_id = "t1_c0001_slot"
    conflicting_cause = "DIFFERENT_CAUSE"

    def raise_after_conflict_persist(*_args, **_kwargs):
        now = START.isoformat()
        conn.execute(
            """UPDATE printer_memory_factory_campaign_token_slots
               SET token_state='MANUAL_REVIEW',
                   first_terminal_cause=?,
                   terminal_at=?,
                   updated_at=?
               WHERE token_slot_id=?""",
            (conflicting_cause, now, now, token_slot_id),
        )
        conn.commit()
        raise ownership.CampaignOwnershipError(
            "terminal state and first cause are immutable"
        )

    monkeypatch.setattr(ownership, "transition_state", raise_after_conflict_persist)
    with pytest.raises(ownership.CampaignOwnershipError):
        _mark_campaign_slot_token_local_failed(
            conn,
            campaign_id=CAMPAIGN_ID,
            campaign_run_id=CAMPAIGN_RUN_ID,
            cycle_id=CYCLE_ID,
            token_id=1,
        )
    row = conn.execute(
        """SELECT token_state, first_terminal_cause
           FROM printer_memory_factory_campaign_token_slots
           WHERE token_slot_id=?""",
        (token_slot_id,),
    ).fetchone()
    conn.close()

    assert str(row["token_state"]) == "MANUAL_REVIEW"
    assert str(row["first_terminal_cause"]) == conflicting_cause

from __future__ import annotations

import inspect
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import authoritative_live_operational_campaign as live
from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.sources.governed_execution import build_fixture_source_adapter


TEST_GIT_PROVENANCE = {
    "git_head": "a" * 40,
    "git_tracked_tree_clean": True,
    "git_staged_changes_present": False,
    "git_unstaged_changes_present": False,
    "git_untracked_present": True,
    "git_provenance_captured_at": "2026-08-11T00:00:00+00:00",
}

MINT_A = "A" * 32
MINT_B = "C" * 32
PAIR_A = "B" * 32
PAIR_B = "D" * 32


class _OpeningPlanReached(RuntimeError):
    post_handoff_proof_fault = True

    def __init__(self, evidence):
        self.evidence = dict(evidence)
        super().__init__("OFFLINE_STANDARD_4H_OPENING_PLAN_REACHED")


class StandardFourHourPreflightCompositionRepairTests(unittest.TestCase):
    def test_live_owner_standard_mode_does_not_inherit_natural_disposition(self) -> None:
        source = inspect.getsource(
            live.AuthoritativeLiveOperationalCampaignOwner.run_operational
        )
        self.assertEqual(
            source.count('lk["operational_natural_disposition"] = True'),
            1,
        )
        self.assertRegex(
            source,
            r'if not standard_four_hour_campaign:\s*\n\s+'
            r'lk\["operational_natural_disposition"\] = True',
        )

    def test_standard_two_token_path_reaches_real_factory_opening_plan(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "standard-four-hour-proof.sqlite3"
            backup = root / "standard-four-hour-proof.backup.sqlite3"
            apply_migrations(db)
            shutil.copy2(db, backup)

            pair_by_mint = {
                MINT_A: PAIR_A,
                MINT_B: PAIR_B,
            }

            def discovery(_args):
                conn = sqlite3.connect(db)
                try:
                    rows = (
                        (MINT_A, PAIR_A, "TRACK_FAST"),
                        (MINT_B, PAIR_B, "TRACK_NORMAL"),
                    )
                    selected = []
                    for mint, pair, lane in rows:
                        conn.execute(
                            "INSERT INTO printer_tokens"
                            "(token_mint,chain,token_status) "
                            "VALUES (?,'solana',?)",
                            (mint, lane),
                        )
                        token_id = int(
                            conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                        )
                        conn.execute(
                            "INSERT INTO printer_pairs"
                            "(token_id,pair_address,base_token_mint) VALUES (?,?,?)",
                            (token_id, pair, mint),
                        )
                        pair_id = int(
                            conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                        )
                        selected.append((token_id, pair_id, mint, pair, lane))

                    conn.execute(
                        "INSERT INTO printer_selection_batches"
                        "(batch_id,batch_status,window_kind,candidate_pool_total,"
                        "selected_count,operator_approved) "
                        "VALUES "
                        "('batch-standard-repair','ASSEMBLED','WINDOW_15M',2,2,1)"
                    )
                    for token_id, pair_id, mint, pair, lane in selected:
                        conn.execute(
                            "INSERT INTO printer_selection_batch_items"
                            "(batch_id,item_status,token_id,pair_id,token_mint,"
                            "pair_address,tracking_lane,operator_approved) "
                            "VALUES "
                            "('batch-standard-repair','SELECTED',?,?,?,?,?,1)",
                            (token_id, pair_id, mint, pair, lane),
                        )
                    conn.commit()
                finally:
                    conn.close()
                return {
                    "selection_handoff_report": {
                        "batch_id": "batch-standard-repair",
                        "selection_seed": "standard-four-hour-repair-seed",
                        "eligible_pool_size": 2,
                    },
                    "discovery_results": [],
                }

            def snapshot_factory(*, token_mint, timeout_seconds):
                pair = pair_by_mint[token_mint]
                return build_fixture_source_adapter(
                    "dexscreener",
                    fixture_payload={
                        "pairs": [
                            {
                                "chain": "solana",
                                "token_mint": token_mint,
                                "pair_address": pair,
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

            real_plan = factory._plan_opening_jobs

            def plan_then_stop(conn, run_id, targets, opening_at, **kwargs):
                real_plan(conn, run_id, targets, opening_at, **kwargs)
                conn.commit()

                run_row = conn.execute(
                    "SELECT run_status,db_mode,config_json "
                    "FROM printer_memory_factory_runs WHERE run_id=?",
                    (run_id,),
                ).fetchone()
                opening_rows = conn.execute(
                    "SELECT token_id,pair_id,step_kind,step_status,scheduler_job_id "
                    "FROM printer_memory_factory_run_steps "
                    "WHERE run_id=? AND step_kind='SNAPSHOT' "
                    "ORDER BY token_id,id",
                    (run_id,),
                ).fetchall()
                scheduler_rows = conn.execute(
                    "SELECT COUNT(*) FROM printer_scheduler_jobs "
                    "WHERE id IN ("
                    "SELECT scheduler_job_id FROM printer_memory_factory_run_steps "
                    "WHERE run_id=? AND step_kind='SNAPSHOT'"
                    ")",
                    (run_id,),
                ).fetchone()[0]
                memory_windows = conn.execute(
                    "SELECT COUNT(*) FROM printer_memory_windows"
                ).fetchone()[0]

                raise _OpeningPlanReached(
                    {
                        "factory_run_exists": run_row is not None,
                        "factory_run_status": (
                            str(run_row[0]) if run_row is not None else None
                        ),
                        "factory_db_mode": (
                            str(run_row[1]) if run_row is not None else None
                        ),
                        "config": (
                            json.loads(str(run_row[2]))
                            if run_row is not None
                            else {}
                        ),
                        "opening_step_count": len(opening_rows),
                        "opening_token_ids": sorted(
                            {int(row[0]) for row in opening_rows}
                        ),
                        "opening_pair_ids": sorted(
                            {int(row[1]) for row in opening_rows}
                        ),
                        "opening_scheduler_row_count": int(scheduler_rows),
                        "memory_window_count": int(memory_windows),
                    }
                )

            with (
                mock.patch.object(
                    factory,
                    "capture_git_provenance",
                    return_value=dict(TEST_GIT_PROVENANCE),
                ),
                mock.patch(
                    "printer_v1.operator_cli.proof_db_schema_readiness."
                    "CANONICAL_PERSISTENT_DB",
                    db,
                ),
                mock.patch(
                    "printer_v1.operator_cli.operational_database_target_binding."
                    "load_durable_operational_database_target_expectation",
                    return_value=None,
                ),
                mock.patch(
                    "printer_v1.operator_cli.operational_database_target_binding."
                    "validate_bound_operational_invocation",
                    return_value=None,
                ),
                mock.patch(
                    "printer_v1.operator_cli.operational_selective_1h."
                    "ensure_authoritative_factory_link",
                    return_value=None,
                ),
                mock.patch.object(
                    factory,
                    "_plan_opening_jobs",
                    side_effect=plan_then_stop,
                ),
            ):
                try:
                    result = factory.run_one_command_15m_factory(
                        db,
                        backup,
                        operator_approved=True,
                        proof_mode=False,
                        operational_persistent_mode=True,
                        standard_four_hour_campaign=True,
                        selective_1h_continuation=True,
                        continuous_first_hour=True,
                        continuous_four_hour=True,
                        four_hour_proof_mode=False,
                        max_selected_tokens=2,
                        max_source_requests=2,
                        total_duration_seconds=14_700.0,
                        campaign_id="campaign-standard-repair",
                        campaign_run_id="run-standard-repair",
                        cycle_id="cycle-standard-repair",
                        configuration_id="config-standard-repair",
                        factory_run_id="factory-standard-repair",
                        discovery_runner=discovery,
                        snapshot_adapter_factory=snapshot_factory,
                    )
                except _OpeningPlanReached as reached:
                    evidence = reached.evidence
                else:
                    self.fail(
                        "standard two-token production shape stopped before the "
                        "real opening planner: "
                        + repr(result.get("blocked_reasons"))
                    )

            self.assertTrue(evidence["factory_run_exists"])
            self.assertEqual(evidence["factory_run_status"], "RUNNING")
            self.assertEqual(evidence["factory_db_mode"], "OPERATIONAL_PERSISTENT")
            self.assertTrue(evidence["config"]["standard_four_hour_campaign"])
            self.assertTrue(evidence["config"]["continuous_first_hour"])
            self.assertTrue(evidence["config"]["continuous_four_hour"])
            self.assertTrue(evidence["config"]["selective_1h_continuation"])
            self.assertFalse(evidence["config"]["four_hour_proof_mode"])
            self.assertFalse(evidence["config"]["operational_natural_disposition"])
            self.assertEqual(evidence["opening_step_count"], 2)
            self.assertEqual(len(evidence["opening_token_ids"]), 2)
            self.assertEqual(len(evidence["opening_pair_ids"]), 2)
            self.assertEqual(evidence["opening_scheduler_row_count"], 2)
            self.assertEqual(evidence["memory_window_count"], 0)

    def test_standard_mixed_historical_dispositions_remain_fail_closed(self) -> None:
        source = inspect.getsource(factory.run_one_command_15m_factory)
        self.assertIn(
            "standard four-hour campaign excludes historical proof dispositions",
            source,
        )
        self.assertIn(
            "standard four-hour campaign cannot use four_hour_proof_mode",
            source,
        )
        self.assertIn(
            "standard four-hour campaign requires exactly two token slots",
            source,
        )
        self.assertIn(
            "continuous first-hour proof cannot use V2-5 three-token mode",
            source,
        )


if __name__ == "__main__":
    unittest.main()

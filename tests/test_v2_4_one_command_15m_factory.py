import json
import shutil
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.one_command_15m_factory import (
    STOP_EMPTY,
    STOP_PREFLIGHT,
    load_report_only,
    run_one_command_15m_factory,
)
from printer_v1.sources.governed_execution import build_fixture_source_adapter


MINT_A = "A" * 32
PAIR_A = "B" * 32


class OneCommand15mFactoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.db = root / "proof.sqlite3"
        self.backup = root / "proof.backup.sqlite3"
        apply_migrations(self.db)
        shutil.copy2(self.db, self.backup)

    def tearDown(self):
        self.temp.cleanup()

    def _discovery(self, *, with_target=True):
        def run(_args):
            if not with_target:
                return {
                    "selection_handoff_report": {
                        "batch_id": None,
                        "selection_seed": "fixture-seed",
                        "eligible_pool_size": 0,
                    },
                    "discovery_results": [],
                }
            conn = sqlite3.connect(self.db)
            try:
                conn.execute(
                    "INSERT INTO printer_tokens(token_mint,chain,token_status) VALUES (?,'solana','TRACK_FAST')",
                    (MINT_A,),
                )
                token_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                conn.execute(
                    "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) VALUES (?,?,?)",
                    (token_id, PAIR_A, MINT_A),
                )
                pair_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                conn.execute(
                    "INSERT INTO printer_selection_batches(batch_id,batch_status,window_kind,candidate_pool_total,selected_count,operator_approved) VALUES ('batch-fixture','ASSEMBLED','WINDOW_15M',1,1,1)"
                )
                conn.execute(
                    """INSERT INTO printer_selection_batch_items
                       (batch_id,item_status,token_id,pair_id,token_mint,pair_address,tracking_lane,operator_approved)
                       VALUES ('batch-fixture','SELECTED',?,?,?,?, 'TRACK_FAST',1)""",
                    (token_id, pair_id, MINT_A, PAIR_A),
                )
                conn.commit()
            finally:
                conn.close()
            return {
                "selection_handoff_report": {
                    "batch_id": "batch-fixture",
                    "selection_seed": "fixture-seed",
                    "eligible_pool_size": 1,
                },
                "discovery_results": [],
            }
        return run

    def _adapter_factory(self, pair=PAIR_A, delay=0.0):
        calls = []
        def build(*, token_mint, timeout_seconds):
            calls.append((token_mint, timeout_seconds))
            if delay:
                time.sleep(delay)
            return build_fixture_source_adapter(
                "dexscreener",
                fixture_payload={
                    "pairs": [{
                        "chain": "solana", "token_mint": token_mint,
                        "pair_address": pair, "price_usd": 1.0,
                        "liquidity_usd": 10000.0, "volume_5m": 500.0,
                        "volume_1h": 2000.0, "volume_24h": 10000.0,
                        "txns_5m": 10, "txns_1h": 50, "txns_24h": 500,
                        "price_change_5m": 1.0, "price_change_1h": 2.0,
                        "price_change_24h": 3.0,
                    }]
                },
            )
        return build, calls

    def _run(self, **overrides):
        factory, calls = self._adapter_factory(
            pair=overrides.pop("pair", PAIR_A), delay=overrides.pop("delay", 0.0)
        )
        options = dict(
            operator_approved=True, proof_mode=True,
            discovery_runner=self._discovery(), snapshot_adapter_factory=factory,
            _window_seconds=0.08, total_duration_seconds=1.0,
            max_selected_tokens=1, max_source_requests=1,
        )
        options.update(overrides)
        return run_one_command_15m_factory(self.db, self.backup, **options), calls

    def test_rejects_unsupported_window_and_persistent_mode(self):
        result = run_one_command_15m_factory(
            self.db, self.backup, operator_approved=True, proof_mode=True,
            window_kind="WINDOW_1H",
        )
        self.assertEqual(result["stop_reason"], STOP_PREFLIGHT)
        self.assertIn("unsupported window_kind", " ".join(result["blocked_reasons"]))

    def test_empty_pool_stops_without_jobs(self):
        result = run_one_command_15m_factory(
            self.db, self.backup, operator_approved=True, proof_mode=True,
            discovery_runner=self._discovery(with_target=False),
            snapshot_adapter_factory=self._adapter_factory()[0],
            _window_seconds=0.05, total_duration_seconds=1.0,
        )
        self.assertEqual(result["stop_reason"], STOP_EMPTY)
        self.assertEqual(result["running_jobs_after_stop"], 0)

    def test_governed_scheduler_path_report_and_replay_are_idempotent(self):
        result, calls = self._run()
        self.assertEqual(result["run_status"], "COMPLETED")
        self.assertEqual(result["running_jobs_after_stop"], 0)
        self.assertEqual(len(calls), 10)
        self.assertEqual(result["table_deltas"]["printer_source_requests"], 10)
        self.assertEqual(result["table_deltas"]["printer_token_snapshots"], 10)
        self.assertEqual(len(result["selected_tokens"]), 1)
        self.assertTrue(all(step["step_status"] == "SUCCEEDED" for step in result["steps"]))
        before = dict(result["counts_after"])
        replay = load_report_only(self.db, result["run_id"])
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0], before["printer_source_requests"])
        finally:
            conn.close()
        self.assertEqual(replay["replay"]["new_source_calls"], 0)
        self.assertEqual(replay["replay"]["new_evidence_rows"], 0)

    def test_exact_pair_mismatch_fails_closed(self):
        result, _calls = self._run(pair="C" * 32)
        self.assertEqual(result["run_status"], "SAFE_STOPPED")
        self.assertEqual(result["table_deltas"]["printer_token_snapshots"], 0)
        self.assertEqual(result["running_jobs_after_stop"], 0)
        self.assertEqual(result["memory_results"]["clean"], 0)

    def test_duration_budget_cancels_pending_jobs(self):
        result, _calls = self._run(delay=0.12, total_duration_seconds=0.1, _window_seconds=0.08)
        self.assertEqual(result["run_status"], "SAFE_STOPPED")
        self.assertEqual(result["running_jobs_after_stop"], 0)
        self.assertTrue(any(step["step_status"] == "CANCELLED" for step in result["steps"]))

    def test_financial_and_retrieval_tables_are_zero_delta(self):
        result, _calls = self._run()
        self.assertTrue(all(value == 0 for value in result["forbidden_deltas"].values()))
        self.assertTrue(result["locks_preserved"]["retrieval"])
        self.assertTrue(result["locks_preserved"]["financial"])


if __name__ == "__main__":
    unittest.main()

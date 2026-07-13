import json
import shutil
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.one_command_15m_factory import (
    STOP_EMPTY,
    STOP_PREFLIGHT,
    _evidence_duration_is_eligible,
    _plan_anchored_jobs,
    _plan_opening_jobs,
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

    def test_close_is_anchored_to_delayed_first_persisted_snapshot(self):
        discovery = self._discovery()

        def delayed(args):
            time.sleep(0.05)
            return discovery(args)

        result, _calls = self._run(discovery_runner=delayed)
        opening = next(step for step in result["steps"] if step["step_key"].endswith("snapshot_00"))
        close = next(step for step in result["steps"] if step["step_kind"] == "WINDOW_CLOSE")
        conn = sqlite3.connect(self.db)
        try:
            captured_at = conn.execute(
                "SELECT captured_at FROM printer_token_snapshots WHERE id=?",
                (opening["snapshot_id"],),
            ).fetchone()[0]
        finally:
            conn.close()
        anchored = (
            datetime.fromisoformat(close["scheduled_for"])
            - datetime.fromisoformat(captured_at)
        ).total_seconds()
        self.assertAlmostEqual(anchored, 0.08, places=5)

    def test_899_seconds_blocks_and_900_seconds_can_continue_to_audit(self):
        start = "2026-07-13T10:00:00+00:00"
        self.assertFalse(_evidence_duration_is_eligible(
            start, "2026-07-13T10:14:59+00:00"
        ))
        self.assertTrue(_evidence_duration_is_eligible(
            start, "2026-07-13T10:15:00+00:00"
        ))

    def test_two_tokens_keep_independent_first_snapshot_anchors(self):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        now = datetime.now(timezone.utc)
        conn.execute(
            """INSERT INTO printer_memory_factory_runs
               (run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at)
               VALUES ('anchor-run','RUNNING','WINDOW_15M','PROOF_ONLY','hash','{}',?)""",
            (now.isoformat(),),
        )
        targets = []
        for index in range(2):
            mint = chr(68 + index) * 32
            pair = chr(70 + index) * 32
            token = conn.execute(
                "INSERT INTO printer_tokens(token_mint,chain,token_status) VALUES (?,'solana','TRACK_FAST')",
                (mint,),
            ).lastrowid
            pair_id = conn.execute(
                "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) VALUES (?,?,?)",
                (token, pair, mint),
            ).lastrowid
            targets.append({
                "token_id": token, "pair_id": pair_id, "token_mint": mint,
                "pair_address": pair, "tracking_lane": "TRACK_FAST",
            })
        _plan_opening_jobs(conn, "anchor-run", targets, now)
        openings = conn.execute(
            "SELECT * FROM printer_memory_factory_run_steps ORDER BY id"
        ).fetchall()
        anchors = [now, now + timedelta(seconds=11)]
        for opening, anchor in zip(openings, anchors):
            _plan_anchored_jobs(
                conn, run_id="anchor-run", opening_step=opening,
                first_snapshot_captured_at=anchor.isoformat(), window_seconds=900,
            )
        closes = conn.execute(
            """SELECT token_id,scheduled_for FROM printer_memory_factory_run_steps
               WHERE step_kind='WINDOW_CLOSE' ORDER BY token_id"""
        ).fetchall()
        conn.close()
        self.assertEqual(len(closes), 2)
        for close, anchor in zip(closes, anchors):
            self.assertEqual(
                datetime.fromisoformat(close["scheduled_for"]),
                anchor + timedelta(seconds=900),
            )

    def test_exact_window_context_blocks_unknown_critical_evidence(self):
        result, _calls = self._run()
        close = next(step for step in result["steps"] if step["step_kind"] == "WINDOW_CLOSE")
        close_result = json.loads(close["result_json"])
        quality = close_result["context_quality"]
        self.assertFalse(quality["clean_promotion_candidate"])
        self.assertTrue(quality["remaining_blockers"])
        self.assertEqual(
            quality["derived_window_context"]["window_kind"], "WINDOW_15M"
        )
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        try:
            window = conn.execute(
                "SELECT * FROM printer_memory_windows WHERE id=?",
                (close["memory_window_id"],),
            ).fetchone()
            context = json.loads(window["supporting_context_json"])
        finally:
            conn.close()
        self.assertEqual(window["snapshot_start_id"], result["steps"][0]["snapshot_id"])
        self.assertEqual(window["snapshot_end_id"], close["snapshot_id"])
        self.assertEqual(window["do_not_train"], 1)
        self.assertEqual(context["window_5m_support_role"], "SUPPORT_ONLY_NOT_MAIN_EVIDENCE")
        self.assertEqual(result["memory_results"]["clean"], 0)


if __name__ == "__main__":
    unittest.main()

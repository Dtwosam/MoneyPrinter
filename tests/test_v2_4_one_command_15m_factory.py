import json
import shutil
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.one_command_15m_factory import (
    STOP_EMPTY,
    STOP_PREFLIGHT,
    _evidence_duration_is_eligible,
    _plan_anchored_jobs,
    _plan_opening_jobs,
    _schedule_offsets,
    load_report_only,
    run_one_command_15m_factory,
)
from printer_v1.sources.governed_execution import (
    FIXTURE_FAILURE,
    build_fixture_source_adapter,
)


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

    def _discovery(self, *, with_target=True, lane="TRACK_FAST"):
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
                    "INSERT INTO printer_tokens(token_mint,chain,token_status) VALUES (?,'solana',?)",
                    (MINT_A, lane),
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
                       VALUES ('batch-fixture','SELECTED',?,?,?,?, ?,1)""",
                    (token_id, pair_id, MINT_A, PAIR_A, lane),
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
                        "buys_5m": 7, "sells_5m": 3,
                        "buys_1h": 30, "sells_1h": 20,
                        "buys_24h": 280, "sells_24h": 220,
                        "price_change_5m": 1.0, "price_change_1h": 2.0,
                        "price_change_24h": 3.0,
                    }]
                },
            )
        return build, calls

    def _failing_context_factories(self):
        factories = {
            source: (lambda _source=source, **_kwargs: build_fixture_source_adapter(
                _source, fixture_kind=FIXTURE_FAILURE
            ))
            for source in ("coingecko", "goplus", "jupiter_quote")
        }
        factories["solana_rpc_holder"] = lambda **_kwargs: build_fixture_source_adapter(
            "solana_rpc", fixture_kind=FIXTURE_FAILURE
        )
        return factories

    def _clean_context_factories(self):
        market_payload = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "assets": {
                "bitcoin": {"price_usd": 65_000, "change_24h": 2.5},
                "ethereum": {"price_usd": 3_500, "change_24h": 1.5},
                "solana": {
                    "price_usd": 150,
                    "change_24h": 4.0,
                    "volume_24h": 2_000_000_000,
                },
            },
        }
        safety_payload = {
            "token_mint": MINT_A,
            "mint_authority": None,
            "freeze_authority": None,
            "metadata_mutable": False,
            "total_supply": "1000000000",
            "top_10_holders": [{"percent": "3"} for _ in range(10)],
            "lp_info": [{"locked": True}],
            "risk_flags": [],
        }
        return {
            "coingecko": lambda **_kwargs: build_fixture_source_adapter(
                "coingecko", fixture_payload=market_payload
            ),
            "goplus": lambda **_kwargs: build_fixture_source_adapter(
                "goplus", fixture_payload=safety_payload
            ),
            "jupiter_quote": lambda **kwargs: build_fixture_source_adapter(
                "jupiter_quote",
                fixture_payload={
                    "route_available": True,
                    "route_plan_present": True,
                    "slippage_bps": 50,
                    "price_impact_bps": 5,
                    "freshness_label": "QUOTE_FRESH",
                    "target_status": "TARGET_MATCH",
                    "paper_only_context": True,
                    "liquidity_context_label": "LIQUIDITY_CONTEXT_ACCEPTABLE",
                    "input_mint": kwargs["input_mint"],
                    "output_mint": kwargs["output_mint"],
                },
            ),
        }

    def _run(self, **overrides):
        factory, calls = self._adapter_factory(
            pair=overrides.pop("pair", PAIR_A), delay=overrides.pop("delay", 0.0)
        )
        options = dict(
            operator_approved=True, proof_mode=True,
            discovery_runner=self._discovery(lane=overrides.pop("lane", "TRACK_FAST")),
            snapshot_adapter_factory=factory,
            context_adapter_factories=overrides.pop(
                "context_adapter_factories", self._failing_context_factories()
            ),
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
        self.assertEqual(result["table_deltas"]["printer_source_requests"], 15)
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

    def test_track_normal_plans_six_boundary_and_spaced_snapshots(self):
        self.assertEqual(_schedule_offsets("TRACK_NORMAL", 900), [180.0, 360.0, 540.0, 720.0])
        result, calls = self._run(lane="TRACK_NORMAL")
        self.assertEqual(result["run_status"], "COMPLETED")
        self.assertEqual(len(calls), 6)
        self.assertEqual(result["table_deltas"]["printer_token_snapshots"], 6)
        self.assertEqual(result["running_jobs_after_stop"], 0)

    def test_exact_pair_mismatch_fails_closed(self):
        # V2-5: an exact-pair mismatch on the opening snapshot is a token-local
        # terminal failure. With a single selected token it isolates that token
        # (no other tokens to continue), leaving no snapshot, no clean memory,
        # and no running jobs. The run completes with the token terminal-failed.
        result, _calls = self._run(pair="C" * 32)
        self.assertEqual(result["table_deltas"]["printer_token_snapshots"], 0)
        self.assertEqual(result["running_jobs_after_stop"], 0)
        self.assertEqual(result["memory_results"]["clean"], 0)
        self.assertEqual(len(result["per_token_outcomes"]), 1)
        self.assertEqual(result["per_token_outcomes"][0]["terminal_status"], "TOKEN_LOCAL_FAILED")
        self.assertEqual(result["terminal_window_outcomes"], 0)

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

    def test_shared_resolver_receives_exact_window_and_all_blockers_reach_audit(self):
        blockers = [
            "MARKET_CONTEXT_BLOCKED", "CHAIN_CONTEXT_BLOCKED", "SAFETY_CONTEXT_BLOCKED",
            "QUOTE_CONTEXT_BLOCKED", "FLOW_CONTEXT_BLOCKED", "CHART_CONTEXT_BLOCKED",
        ]
        shared = {
            "clean_memory_context_ready": False,
            "blockers": blockers,
            "sections": {},
            "writes_performed": False,
        }
        with patch(
            "printer_v1.context_evidence.build_window_15m_context_evidence",
            return_value=shared,
        ) as resolver:
            result, _calls = self._run()
        close = next(step for step in result["steps"] if step["step_kind"] == "WINDOW_CLOSE")
        close_result = json.loads(close["result_json"])
        quality = close_result["context_quality"]
        call = resolver.call_args.kwargs
        self.assertEqual(call["token_id"], close["token_id"])
        self.assertEqual(call["pair_id"], close["pair_id"])
        self.assertEqual(call["snapshot_end_id"], close["snapshot_id"])
        self.assertEqual(call["snapshot_start_id"], result["steps"][0]["snapshot_id"])
        self.assertTrue(set(blockers).issubset(quality["remaining_blockers"]))
        self.assertEqual(close_result["window_audit"]["e2q_status"], "E2Q_AUDIT_DIRTY")
        self.assertFalse(quality["clean_promotion_candidate"])

    def test_governed_close_context_reaches_exact_target_and_side_aware_flow(self):
        with patch("printer_v1.context_evidence.window_15m.WINDOW_SECONDS", 0):
            result, _calls = self._run(
                context_adapter_factories=self._clean_context_factories()
            )
        close = next(
            step for step in result["steps"] if step["step_kind"] == "WINDOW_CLOSE"
        )
        close_result = json.loads(close["result_json"])
        collection = close_result["governed_context_collection"]
        self.assertEqual(collection["source_request_budget"], 5)
        self.assertEqual(collection["source_requests_attempted"], 4)
        self.assertEqual(result["config"]["context_source_request_budget"], 5)
        self.assertTrue(all(
            item["source_response_id"] is not None
            for item in collection["items"].values()
        ))
        persisted = close_result["governed_context_persistence"]
        self.assertIsNotNone(persisted["market_regime_row_id"])
        self.assertIsNotNone(persisted["chain_heat_row_id"])
        self.assertTrue(persisted["safety"]["inserted"])
        self.assertIsNotNone(persisted["safety_composite"]["composite_id"])
        self.assertEqual(
            persisted["safety_composite"]["safety_contract_label"],
            "SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY",
        )
        self.assertTrue(persisted["entry_quote"]["inserted"])
        self.assertTrue(persisted["exit_quote"]["inserted"])

        shared = close_result["context_quality"]["shared_context_evidence"]
        self.assertEqual(shared["snapshot_end_id"], close["snapshot_id"])
        self.assertEqual(shared["sections"]["market_regime"]["status"], "READY")
        self.assertEqual(shared["sections"]["solana_chain_heat"]["status"], "READY")
        self.assertEqual(shared["sections"]["safety_rug"]["status"], "READY")
        self.assertEqual(
            shared["sections"]["safety_rug"]["labels"]["safety_status_label"],
            "SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY",
        )
        self.assertEqual(
            close_result["context_quality"]["context_labels"]["safety_status_label"],
            "SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY",
        )
        self.assertEqual(
            shared["sections"]["liquidity_exit_realism"]["status"], "READY"
        )
        flow = shared["sections"]["trading_flow"]
        self.assertEqual(flow["status"], "READY")
        self.assertNotEqual(flow["labels"]["flow_direction_label"], "FLOW_UNKNOWN")
        self.assertNotEqual(flow["labels"]["flow_pressure_label"], "PRESSURE_UNKNOWN")
        self.assertEqual(result["running_jobs_after_stop"], 0)
        self.assertTrue(all(value == 0 for value in result["forbidden_deltas"].values()))

    def test_missing_goplus_holders_use_governed_rpc_fallback(self):
        factories = self._clean_context_factories()
        factories["goplus"] = lambda **_kwargs: build_fixture_source_adapter(
            "goplus",
            fixture_payload={
                "token_mint": MINT_A,
                "mint_authority": None,
                "freeze_authority": None,
                "metadata_mutable": False,
                "total_supply": "1000000000",
                "risk_flags": [],
            },
        )
        factories["solana_rpc_holder"] = lambda **_kwargs: build_fixture_source_adapter(
            "solana_rpc",
            fixture_payload={
                "token_mint": MINT_A,
                "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
            },
        )
        with patch("printer_v1.context_evidence.window_15m.WINDOW_SECONDS", 0):
            result, _calls = self._run(context_adapter_factories=factories)
        close = next(
            step for step in result["steps"] if step["step_kind"] == "WINDOW_CLOSE"
        )
        close_result = json.loads(close["result_json"])
        collection = close_result["governed_context_collection"]
        self.assertEqual(collection["source_requests_attempted"], 5)
        self.assertIsNotNone(collection["items"]["holder"]["source_response_id"])
        composite = close_result["governed_context_persistence"]["safety_composite"]
        self.assertEqual(composite["contribution_count"], 2)
        self.assertEqual(
            composite["holder_concentration_label"],
            "HOLDER_CONCENTRATION_HEALTHY",
        )
        self.assertEqual(
            close_result["context_quality"]["shared_context_evidence"]["sections"]["safety_rug"]["status"],
            "READY",
        )
        self.assertEqual(result["running_jobs_after_stop"], 0)
        self.assertTrue(all(value == 0 for value in result["forbidden_deltas"].values()))

    def test_mismatched_safety_and_quotes_fail_closed_without_exact_evidence(self):
        factories = self._clean_context_factories()
        factories["goplus"] = lambda **_kwargs: build_fixture_source_adapter(
            "goplus",
            fixture_payload={
                "token_mint": "Z" * 32,
                "mint_authority": None,
                "freeze_authority": None,
                "metadata_mutable": False,
                "total_supply": "1000000000",
                "risk_flags": [],
            },
        )
        factories["jupiter_quote"] = lambda **_kwargs: build_fixture_source_adapter(
            "jupiter_quote",
            fixture_payload={
                "route_available": True,
                "route_plan_present": True,
                "freshness_label": "QUOTE_FRESH",
                "target_status": "TARGET_MATCH",
                "paper_only_context": True,
                "input_mint": "Z" * 32,
                "output_mint": "Y" * 32,
            },
        )
        with patch("printer_v1.context_evidence.window_15m.WINDOW_SECONDS", 0):
            result, _calls = self._run(context_adapter_factories=factories)
        close = next(
            step for step in result["steps"] if step["step_kind"] == "WINDOW_CLOSE"
        )
        close_result = json.loads(close["result_json"])
        persisted = close_result["governed_context_persistence"]
        self.assertEqual(
            persisted["safety"]["audit_status"], "REJECTED_TARGET_MINT_MISMATCH"
        )
        self.assertEqual(
            persisted["entry_quote"]["audit_status"],
            "REJECTED_TARGET_MINT_MISMATCH",
        )
        self.assertEqual(
            persisted["exit_quote"]["audit_status"],
            "REJECTED_TARGET_MINT_MISMATCH",
        )
        self.assertEqual(result["table_deltas"]["printer_solana_safety_evidence"], 0)
        self.assertEqual(result["table_deltas"]["printer_paper_quote_evidence"], 0)
        shared = close_result["context_quality"]["shared_context_evidence"]
        self.assertFalse(shared["clean_memory_context_ready"])
        self.assertIn(
            "NO_VALID_EXACT_TARGET_SAFETY_EVIDENCE", shared["blockers"]
        )


if __name__ == "__main__":
    unittest.main()

"""V2-5 conservative multi-token 15m proof — focused verification (Gate 2).

Proves the readiness repair: explicit three-token proof mode, token-local
failure isolation, hard run/per-token budgets, scheduler-row ceiling, run-local
reporting separation, and preserved locks. Uses fixtures and isolated temp DBs.
No live network, no persistent DB, no retrieval/financial deltas.
"""

import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.one_command_15m_factory import (
    STOP_PREFLIGHT,
    TOKEN_LOCAL_CANCELLED,
    _GlobalStop,
    _cancel_pending_for_token,
    _enforce_budgets_before_step,
    _plan_anchored_jobs,
    _plan_opening_jobs,
    load_report_only,
    run_one_command_15m_factory,
)
from printer_v1.sources.governed_execution import build_fixture_source_adapter

# Distinct 32-char mints/pairs; selection orders by lower(mint) so M1<M2<M3.
M1, M2, M3 = "1" * 32, "2" * 32, "3" * 32
P1, P2, P3 = "a" * 32, "b" * 32, "c" * 32
TOKENS = [(M1, P1), (M2, P2), (M3, P3)]


def _snapshot_payload(token_mint, pair):
    return {
        "pairs": [{
            "chain": "solana", "token_mint": token_mint, "pair_address": pair,
            "price_usd": 1.0, "liquidity_usd": 10000.0, "volume_5m": 500.0,
            "volume_1h": 2000.0, "volume_24h": 10000.0,
            "txns_5m": 10, "txns_1h": 50, "txns_24h": 500,
            "buys_5m": 7, "sells_5m": 3, "buys_1h": 30, "sells_1h": 20,
            "buys_24h": 280, "sells_24h": 220,
            "price_change_5m": 1.0, "price_change_1h": 2.0, "price_change_24h": 3.0,
        }]
    }


class V2_5MultiTokenTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.db = root / "proof.sqlite3"
        self.backup = root / "proof.backup.sqlite3"
        apply_migrations(self.db)
        shutil.copy2(self.db, self.backup)

    def tearDown(self):
        self.temp.cleanup()

    def _discovery(self, tokens, lanes):
        def run(_args):
            conn = sqlite3.connect(self.db)
            try:
                conn.execute(
                    "INSERT INTO printer_selection_batches(batch_id,batch_status,window_kind,candidate_pool_total,selected_count,operator_approved) VALUES ('b3','ASSEMBLED','WINDOW_15M',?,?,1)",
                    (len(tokens), len(tokens)),
                )
                for (mint, pair), lane in zip(tokens, lanes):
                    conn.execute(
                        "INSERT INTO printer_tokens(token_mint,chain,token_status) VALUES (?,'solana',?)",
                        (mint, lane),
                    )
                    token_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                    conn.execute(
                        "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) VALUES (?,?,?)",
                        (token_id, pair, mint),
                    )
                    conn.execute(
                        """INSERT INTO printer_selection_batch_items
                           (batch_id,item_status,token_id,pair_id,token_mint,pair_address,tracking_lane,operator_approved)
                           VALUES ('b3','SELECTED',?, (SELECT id FROM printer_pairs WHERE pair_address=?), ?,?,?,1)""",
                        (token_id, pair, mint, pair, lane),
                    )
                conn.commit()
            finally:
                conn.close()
            return {
                "selection_handoff_report": {"batch_id": "b3", "selection_seed": "seed3", "eligible_pool_size": len(tokens)},
                "discovery_results": [],
            }
        return run

    def _adapter_factory(self, *, fail_mint=None, calls=None):
        calls = calls if calls is not None else []
        def build(*, token_mint, timeout_seconds):
            calls.append(token_mint)
            expected_pair = dict(TOKENS)[token_mint]
            pair = "z" * 32 if token_mint == fail_mint else expected_pair
            return build_fixture_source_adapter(
                "dexscreener", fixture_payload=_snapshot_payload(token_mint, pair)
            )
        return build, calls

    def _context_factories(self):
        from printer_v1.sources.governed_execution import FIXTURE_FAILURE
        f = {s: (lambda _s=s, **_k: build_fixture_source_adapter(_s, fixture_kind=FIXTURE_FAILURE))
             for s in ("coingecko", "goplus", "jupiter_quote")}
        f["solana_rpc_holder"] = lambda **_k: build_fixture_source_adapter("solana_rpc", fixture_kind=FIXTURE_FAILURE)
        return f

    def _run3(self, *, lanes=("TRACK_NORMAL",) * 3, fail_mint=None, tokens=TOKENS, **overrides):
        factory, calls = self._adapter_factory(fail_mint=fail_mint)
        options = dict(
            operator_approved=True, proof_mode=True, v2_5_proof_mode=True,
            max_selected_tokens=3, max_source_requests=2,
            discovery_runner=self._discovery(tokens, lanes),
            snapshot_adapter_factory=factory,
            context_adapter_factories=self._context_factories(),
            _window_seconds=0.05, total_duration_seconds=3.0,
        )
        options.update(overrides)
        return run_one_command_15m_factory(self.db, self.backup, **options), calls

    # --- Validation / caps -------------------------------------------------

    def test_v2_5_mode_requires_exactly_three(self):
        r = run_one_command_15m_factory(
            self.db, self.backup, operator_approved=True, proof_mode=True,
            v2_5_proof_mode=True, max_selected_tokens=2,
        )
        self.assertEqual(r["stop_reason"], STOP_PREFLIGHT)
        self.assertIn("exactly three", " ".join(r["blocked_reasons"]))

    def test_normal_mode_rejects_three(self):
        r = run_one_command_15m_factory(
            self.db, self.backup, operator_approved=True, proof_mode=True,
            v2_5_proof_mode=False, max_selected_tokens=3,
        )
        self.assertEqual(r["stop_reason"], STOP_PREFLIGHT)

    def test_four_tokens_rejected_in_both_modes(self):
        for mode in (True, False):
            r = run_one_command_15m_factory(
                self.db, self.backup, operator_approved=True, proof_mode=True,
                v2_5_proof_mode=mode, max_selected_tokens=4,
            )
            self.assertEqual(r["stop_reason"], STOP_PREFLIGHT)

    # --- Failure isolation -------------------------------------------------

    def test_token_a_failure_does_not_cancel_b_or_c(self):
        result, _calls = self._run3(fail_mint=M1)
        self.assertEqual(result["run_status"], "COMPLETED")
        outcomes = {o["token_mint"]: o for o in result["per_token_outcomes"]}
        self.assertEqual(outcomes[M1]["terminal_status"], "TOKEN_LOCAL_FAILED")
        self.assertTrue(outcomes[M2]["reached_terminal_window"])
        self.assertTrue(outcomes[M3]["reached_terminal_window"])
        self.assertGreaterEqual(result["terminal_window_outcomes"], 2)
        self.assertEqual(result["running_jobs_after_stop"], 0)

    def test_token_local_cancellation_leaves_no_pending_for_a(self):
        result, _calls = self._run3(fail_mint=M1)
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        try:
            a_token = conn.execute("SELECT id FROM printer_tokens WHERE token_mint=?", (M1,)).fetchone()[0]
            pend = conn.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_run_steps WHERE token_id=? AND step_status IN ('PENDING','RUNNING')",
                (a_token,),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(pend, 0)

    def test_no_cross_token_snapshot_evidence(self):
        result, _calls = self._run3()
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        try:
            checked = 0
            for step in result["steps"]:
                if step["snapshot_id"] is None:
                    continue
                snap = conn.execute(
                    "SELECT token_id, pair_id FROM printer_token_snapshots WHERE id=?",
                    (step["snapshot_id"],),
                ).fetchone()
                # Every persisted snapshot belongs to exactly its own token/pair.
                self.assertEqual(snap["token_id"], step["token_id"])
                self.assertEqual(snap["pair_id"], step["pair_id"])
                checked += 1
            self.assertGreater(checked, 0)
            # Each memory window's start/end snapshots belong to that token only.
            for step in result["steps"]:
                if step["step_kind"] != "WINDOW_CLOSE" or step["memory_window_id"] is None:
                    continue
                win = conn.execute(
                    "SELECT snapshot_start_id, snapshot_end_id FROM printer_memory_windows WHERE id=?",
                    (step["memory_window_id"],),
                ).fetchone()
                for sid in (win["snapshot_start_id"], win["snapshot_end_id"]):
                    owner = conn.execute(
                        "SELECT token_id FROM printer_token_snapshots WHERE id=?", (sid,)
                    ).fetchone()
                    self.assertEqual(owner["token_id"], step["token_id"])
        finally:
            conn.close()

    # --- Budgets / scheduler ----------------------------------------------

    def test_budgets_and_scheduler_within_ceilings(self):
        result, _calls = self._run3(lanes=("TRACK_FAST",) * 3)
        b = result["run_budgets"]
        # V2-6.1a: budgets derive from the cadence policy (16 snapshots/token FAST):
        # per-token 21, run 65, scheduler 51.
        self.assertTrue(b["governed_requests_run_within_ceiling"])
        self.assertLessEqual(b["governed_requests_run"], 65)
        self.assertTrue(b["governed_requests_per_token_within_ceiling"])
        for v in b["governed_requests_per_token"].values():
            self.assertLessEqual(v, 21)
        self.assertTrue(b["scheduler_rows_within_ceiling"])
        self.assertLessEqual(b["scheduler_rows_total"], 51)
        self.assertEqual(b["automatic_retries"], 0)

    def test_enforce_budgets_raises_global_stop(self):
        # Direct unit check: a projected per-token breach raises _GlobalStop.
        # The per-token ceiling derives from the cadence policy (V2-6.1a: 21).
        from printer_v1.operator_cli.one_command_15m_factory import (
            _MAX_GOVERNED_REQUESTS_PER_TOKEN,
        )
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        try:
            for i in range(_MAX_GOVERNED_REQUESTS_PER_TOKEN):
                conn.execute(
                    "INSERT INTO printer_source_requests(source_name,request_kind,requested_at,request_key,source_status,data_quality_label) VALUES ('dexscreener','pair_market_snapshot',?,?,'COMPLETE','CLEAN_DATA')",
                    (datetime.now(timezone.utc).isoformat(), f"run9:t1_snapshot_{i:02d}"),
                )
            conn.commit()
            # One more snapshot would exceed the per-token ceiling.
            fake_step = {"step_kind": "SNAPSHOT", "step_key": "t1_snapshot_99"}
            with self.assertRaises(_GlobalStop):
                _enforce_budgets_before_step(conn, "run9", fake_step)
        finally:
            conn.close()

    def test_cancel_pending_for_token_is_scoped(self):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        now = datetime.now(timezone.utc)
        conn.execute(
            "INSERT INTO printer_memory_factory_runs(run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at) VALUES ('rid','RUNNING','WINDOW_15M','PROOF_ONLY','h','{}',?)",
            (now.isoformat(),),
        )
        targets = []
        for (mint, pair), lane in zip(TOKENS, ("TRACK_NORMAL",) * 3):
            tk = conn.execute("INSERT INTO printer_tokens(token_mint,chain,token_status) VALUES (?,'solana',?)", (mint, lane)).lastrowid
            pr = conn.execute("INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) VALUES (?,?,?)", (tk, pair, mint)).lastrowid
            targets.append({"token_id": tk, "pair_id": pr, "token_mint": mint, "pair_address": pair, "tracking_lane": lane})
        _plan_opening_jobs(conn, "rid", targets, now)
        conn.commit()
        cancelled = _cancel_pending_for_token(conn, "rid", targets[0]["token_id"], TOKEN_LOCAL_CANCELLED)
        conn.commit()
        self.assertEqual(cancelled, 1)
        remaining = conn.execute(
            "SELECT token_id,step_status FROM printer_memory_factory_run_steps"
        ).fetchall()
        by_token = {r["token_id"]: r["step_status"] for r in remaining}
        self.assertEqual(by_token[targets[0]["token_id"]], "CANCELLED")
        self.assertEqual(by_token[targets[1]["token_id"]], "PENDING")
        self.assertEqual(by_token[targets[2]["token_id"]], "PENDING")
        conn.close()

    # --- Coverage / anchors ------------------------------------------------

    def test_track_normal_six_and_fast_ten_per_token(self):
        result, _calls = self._run3(lanes=("TRACK_FAST", "TRACK_NORMAL", "TRACK_NORMAL"))
        outcomes = {o["token_mint"]: o for o in result["per_token_outcomes"]}
        # V2-6.1a cadence: 15m FAST = 16 snapshots, NORMAL = 9.
        self.assertEqual(outcomes[M1]["expected_snapshots"], 16)
        self.assertEqual(outcomes[M1]["actual_snapshots"], 16)
        self.assertEqual(outcomes[M2]["expected_snapshots"], 9)
        self.assertEqual(outcomes[M2]["actual_snapshots"], 9)
        self.assertEqual(outcomes[M3]["actual_snapshots"], 9)

    def test_three_independent_first_snapshot_anchors(self):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        now = datetime.now(timezone.utc)
        conn.execute(
            "INSERT INTO printer_memory_factory_runs(run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at) VALUES ('ar','RUNNING','WINDOW_15M','PROOF_ONLY','h','{}',?)",
            (now.isoformat(),),
        )
        targets = []
        for (mint, pair) in TOKENS:
            tk = conn.execute("INSERT INTO printer_tokens(token_mint,chain,token_status) VALUES (?,'solana','TRACK_FAST')", (mint,)).lastrowid
            pr = conn.execute("INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) VALUES (?,?,?)", (tk, pair, mint)).lastrowid
            targets.append({"token_id": tk, "pair_id": pr, "token_mint": mint, "pair_address": pair, "tracking_lane": "TRACK_FAST"})
        _plan_opening_jobs(conn, "ar", targets, now)
        openings = conn.execute("SELECT * FROM printer_memory_factory_run_steps ORDER BY id").fetchall()
        anchors = [now, now + timedelta(seconds=7), now + timedelta(seconds=19)]
        for opening, anchor in zip(openings, anchors):
            _plan_anchored_jobs(conn, run_id="ar", opening_step=opening, first_snapshot_captured_at=anchor.isoformat(), window_seconds=900)
        closes = conn.execute("SELECT token_id,scheduled_for FROM printer_memory_factory_run_steps WHERE step_kind='WINDOW_CLOSE' ORDER BY token_id").fetchall()
        conn.close()
        self.assertEqual(len(closes), 3)
        for close, anchor in zip(closes, anchors):
            self.assertEqual(datetime.fromisoformat(close["scheduled_for"]), anchor + timedelta(seconds=900))

    # --- Replay / locks / reporting ---------------------------------------

    def test_replay_creates_no_writes_or_calls(self):
        result, _calls = self._run3()
        conn = sqlite3.connect(self.db)
        try:
            before = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                      for t in ("printer_source_requests", "printer_token_snapshots", "printer_memory_windows", "printer_scheduler_jobs")}
        finally:
            conn.close()
        replay = load_report_only(self.db, result["run_id"])
        self.assertEqual(replay["replay"]["new_source_calls"], 0)
        self.assertEqual(replay["replay"]["new_evidence_rows"], 0)
        conn = sqlite3.connect(self.db)
        try:
            after = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in before}
        finally:
            conn.close()
        self.assertEqual(before, after)

    def test_retrieval_and_financial_zero_delta(self):
        result, _calls = self._run3()
        self.assertTrue(all(v == 0 for v in result["forbidden_deltas"].values()))
        self.assertTrue(result["locks_preserved"]["retrieval"])
        self.assertTrue(result["locks_preserved"]["financial"])

    def test_run_local_yield_and_historical_note_present(self):
        result, _calls = self._run3()
        self.assertIn("run_local_yield", result)
        self.assertEqual(
            result["run_local_yield"]["authoritative_source"],
            "eligible_printer_episodes_joined_to_run_step_attached_memory_window_ids",
        )
        self.assertIn("historical_report_note", result)
        self.assertIn("not authoritative", result["historical_report_note"].lower())
        # run-local yield token counts sum to <= selected tokens
        y = result["run_local_yield"]
        self.assertLessEqual(y["clean"] + y["dirty"] + y["blocked"] + y["token_local_failed"], 3)


if __name__ == "__main__":
    unittest.main()

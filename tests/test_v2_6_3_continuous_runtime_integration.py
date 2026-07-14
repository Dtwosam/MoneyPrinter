"""V2-6.3 — Continuous Lifecycle Runtime Integration.

Proves the V2-6.2 continuity contract is wired into the live runtime paths:
- lane_x12_1h_runner planning path calls build_1h_continuation_plan;
- the runner threads continuation_of_15m into the E2O 1h close so the transition
  verdict (CLEAN / DIRTY / BLOCKED) is consumed before quality promotion;
- delayed scheduling cannot extend the deadline (15m close + 2700s is fixed);
- DIRTY forces do_not_train; BLOCKED prevents 1h window creation;
- the one-command factory reports the continuation plan;
- downstream financial / retrieval locks stay unchanged.

Fixtures and temporary DBs only. No live sources.
"""

import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.lane_x12_1h_runner import (
    LANE_X12_MODE_FAST,
    plan_1h_continuation,
    run_1h_memory_factory_cycle,
)
from printer_v1.operator_cli.one_command_15m_factory import _per_token_outcomes
from printer_v1.sources.governed_execution import (
    FIXTURE_SUCCESS,
    build_fixture_source_adapter,
)

_MINT_A = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_PAIR_A = "V263PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


def _iso(dt):
    return dt.isoformat()


def _build_adapter(mint, pair):
    return build_fixture_source_adapter(
        "dexscreener", fixture_kind=FIXTURE_SUCCESS,
        fixture_payload={
            "source_name": "dexscreener", "request_kind": "pair_market_snapshot",
            "pairs": [{
                "chain": "solana", "pair_address": pair, "token_mint": mint,
                "symbol": "X12T", "name": "X12 Test", "price_usd": 0.00012,
                "liquidity_usd": 12000.0, "volume_5m": 150.0, "volume_1h": 1800.0,
                "volume_24h": 43200.0, "txns_5m": 6, "txns_1h": 72, "txns_24h": 1728,
                "fdv": 120000.0, "market_cap": 100000.0, "price_change_5m": 0.3,
                "price_change_1h": -0.8, "price_change_24h": -2.5,
            }],
        },
    )


# ===========================================================================
# Planning path
# ===========================================================================

class TestPlanningPath(unittest.TestCase):
    def _fifteen(self, close):
        return {"id": 42, "window_kind": "WINDOW_15M", "window_status": "WINDOW_CLOSED",
                "snapshot_end_id": 115, "closed_at": _iso(close),
                "tracking_lane": "TRACK_FAST"}

    def test_planning_calls_build_plan_and_anchors_deadline(self):
        close = datetime(2026, 6, 29, 10, 15, 1, tzinfo=timezone.utc)
        p = plan_1h_continuation({"token_mint": "m",
                                  "continuation_of_15m": self._fifteen(close)})
        self.assertTrue(p["is_continuation"])
        self.assertEqual(p["enqueue_at"], _iso(close))  # enqueue at exact 15m close
        self.assertEqual(p["deadline_at"], _iso(close + timedelta(seconds=2700)))
        self.assertEqual(p["deadline_anchored_to"], "fifteen_m_close_plus_2700s")
        self.assertEqual(p["continuation_of_window_id"], 42)

    def test_non_continuation_token(self):
        p = plan_1h_continuation({"token_mint": "m"})
        self.assertFalse(p["is_continuation"])
        self.assertIsNone(p["plan"])

    def test_delayed_scheduling_cannot_extend_deadline(self):
        # The deadline derives solely from the 15m close, so re-planning "later"
        # (or a delayed first snapshot) cannot push it out.
        close = datetime(2026, 6, 29, 10, 15, 1, tzinfo=timezone.utc)
        entry = {"token_mint": "m", "continuation_of_15m": self._fifteen(close)}
        first = plan_1h_continuation(entry)["deadline_at"]
        # simulate a much later re-plan — identical input, identical deadline
        again = plan_1h_continuation(entry)["deadline_at"]
        self.assertEqual(first, again)
        self.assertEqual(first, _iso(close + timedelta(seconds=2700)))


# ===========================================================================
# Factory continuation reporting
# ===========================================================================

class TestFactoryContinuationReport(unittest.TestCase):
    def test_per_token_outcome_includes_continuation_plan(self):
        close = datetime(2026, 6, 29, 10, 15, 1, tzinfo=timezone.utc)
        steps = [{
            "token_id": 1, "token_mint": _MINT_A, "pair_id": 1, "pair_address": _PAIR_A,
            "tracking_lane": "TRACK_NORMAL", "step_kind": "WINDOW_CLOSE",
            "step_status": "SUCCEEDED", "snapshot_id": None, "memory_window_id": 7,
        }]
        windows = {7: {"id": 7, "window_kind": "WINDOW_15M", "window_status": "WINDOW_CLOSED",
                       "memory_quality_label": "DIRTY_MEMORY", "snapshot_end_id": 30,
                       "closed_at": _iso(close), "window_end_at": _iso(close)}}
        out = _per_token_outcomes(steps, windows)
        self.assertEqual(len(out), 1)
        plan = out[0].get("continuation_plan")
        self.assertIsNotNone(plan)
        self.assertTrue(plan["enqueue_ok"])
        self.assertEqual(plan["enqueue_at"], _iso(close))
        self.assertEqual(plan["deadline_at"], _iso(close + timedelta(seconds=2700)))


# ===========================================================================
# End-to-end runner wiring
# ===========================================================================

class TestRunnerContinuationWiring(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        self.backup = pathlib.Path(self._tmp.name) / "backup.sqlite3"
        self.backup.write_bytes(b"backup")
        apply_migrations(self.db)
        # Seed the token/pair so the preceding 15m window's identity is real and
        # the 1h phase runs for the same token/pair.
        now = "2026-06-28T10:00:00+00:00"
        conn = sqlite3.connect(str(self.db))
        self.tid = int(conn.execute(
            "INSERT INTO printer_tokens(token_mint,chain,token_status,created_at,updated_at)"
            " VALUES (?,'solana','TRACKING',?,?)", (_MINT_A, now, now)).lastrowid)
        self.pid = int(conn.execute(
            "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint,created_at,updated_at)"
            " VALUES (?,?,?,?,?)", (self.tid, _PAIR_A, _PAIR_A, now, now)).lastrowid)
        conn.commit()
        conn.close()

    def tearDown(self):
        self._tmp.cleanup()

    def _count(self, table, where=""):
        conn = sqlite3.connect(str(self.db))
        try:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table} {where}").fetchone()[0])
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def _token_list(self, continuation):
        tokens = [{
            "token_mint": _MINT_A, "pair_address": _PAIR_A, "chain": "solana",
            "tracking_lane": LANE_X12_MODE_FAST, "operator_approved": True,
            "continuation_of_15m": continuation,
        }]
        tf = pathlib.Path(self._tmp.name) / "tl.json"
        tf.write_text(json.dumps({"tokens": tokens}), encoding="utf-8")
        return tf

    def _run(self, continuation):
        tf = self._token_list(continuation)
        return run_1h_memory_factory_cycle(
            token_list_path=tf, db_path=self.db, backup_proof_path=self.backup,
            mode=LANE_X12_MODE_FAST, operator_approved=True,
            _adapter_map={_MINT_A: _build_adapter(_MINT_A, _PAIR_A)},
            _cycle_budget=1, window_close_interval_seconds=0.001,
            snapshot_interval_seconds=0.0,
        )

    def _cont(self, gap_seconds):
        # 15m close relative to now: positive gap -> continuation begins after
        # close; negative -> delayed restart. First 1h snapshot is created ~now.
        close = datetime.now(timezone.utc) - timedelta(seconds=gap_seconds)
        return {"id": 900, "window_kind": "WINDOW_15M", "window_status": "WINDOW_CLOSED",
                "snapshot_end_id": 1, "closed_at": _iso(close),
                "tracking_lane": "TRACK_FAST", "run_id": "r1",
                "token_id": self.tid, "pair_id": self.pid}

    def test_clean_continuation_creates_anchored_1h_window(self):
        self._run(self._cont(gap_seconds=60))  # gap ~60s <=120 clean
        self.assertEqual(self._count("printer_memory_windows",
                                     "WHERE window_kind='WINDOW_1H'"), 1)
        conn = sqlite3.connect(str(self.db))
        row = conn.execute(
            "SELECT do_not_train, supporting_context_json FROM printer_memory_windows"
            " WHERE window_kind='WINDOW_1H'").fetchone()
        conn.close()
        self.assertEqual(int(row[0]), 0)
        ctx = json.loads(row[1])
        self.assertEqual(ctx["continuity"]["continuity_status"], "CONTINUITY_CONTINUOUS")

    def test_dirty_continuation_forces_do_not_train(self):
        self._run(self._cont(gap_seconds=210))  # 180<gap<=240 -> DIRTY
        conn = sqlite3.connect(str(self.db))
        row = conn.execute(
            "SELECT do_not_train, supporting_context_json FROM printer_memory_windows"
            " WHERE window_kind='WINDOW_1H'").fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(int(row[0]), 1)
        ctx = json.loads(row[1])
        self.assertEqual(ctx["continuity"]["continuity_status"], "CONTINUITY_DIRTY")

    def test_blocked_continuation_prevents_1h_window(self):
        self._run(self._cont(gap_seconds=-600))  # future close -> negative gap
        # No 1h window is created for a BLOCKED (delayed-restart) transition.
        self.assertEqual(self._count("printer_memory_windows",
                                     "WHERE window_kind='WINDOW_1H'"), 0)
        # The block reason is recorded on the failed scheduler job.
        conn = sqlite3.connect(str(self.db))
        n = conn.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs"
            " WHERE last_error LIKE '%CONTINUITY_BLOCKED%'").fetchone()[0]
        conn.close()
        self.assertGreater(int(n), 0)

    def test_downstream_locks_unchanged(self):
        self._run(self._cont(gap_seconds=60))
        for t in ("printer_paper_decisions", "printer_paper_positions",
                  "printer_paper_trade_events", "printer_paper_trade_audits",
                  "printer_retrieval_candidates", "printer_retrieval_results"):
            self.assertEqual(self._count(t), 0, t)


if __name__ == "__main__":
    unittest.main()

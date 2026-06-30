"""
Post-Lane 10 Lane T -- E2T Start-Snapshot Threading

Tests prove:
- E2J accepts _snapshot_start_id keyword parameter
- E2J exposes snapshot_id_for_window in its return dict
- E2J exposes window integrity fields (window_start_at, window_end_at,
  elapsed_seconds, lane_q_integrity_eligible, snapshot_start_id, snapshot_end_id)
- E2J blocked path returns all new fields as None/False
- Single-cycle E2T: cycle 1 gets _snapshot_start_id=None; snapshot_id_for_window
  is captured as cycle_start_snapshot_id after the cycle
- Single-cycle: window_start_at is None (no start provided); lane_q_integrity_eligible False
- Multi-cycle E2T (2 cycles): cycle_start_snapshot_id set from cycle 1's close snapshot
- Multi-cycle: cycle 2 receives snapshot_start_id from cycle 1; window_start_at populated
- Multi-cycle: elapsed ~ 0 in fixture run so lane_q_integrity_eligible still False (honest)
- 3-cycle: cycles 2 and 3 both carry cycle 1's snapshot_id as snapshot_start_id
- After backdating cycle-1 snapshot to 2026-01-01: cycle 2 shows elapsed >> 900s;
  lane_q_integrity_eligible=True
- DB columns (window_start_at, snapshot_start_id, snapshot_end_id) written correctly
- No paper decisions, positions, trade events, audits, or episodes after any cycle run
- Hard locks present and all True
"""

import json
import pathlib
import sqlite3
import tempfile
import unittest
from typing import Any

import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.e2j_first_15m_cycle import (
    E2J_STATUS_EXECUTED,
    E2J_STATUS_BLOCKED,
    build_e2j_first_15m_cycle_payload,
)
from printer_v1.operator_cli.e2t_bounded_cycle_runner import (
    E2T_STATUS_COMPLETED,
    E2T_STATUS_BLOCKED,
    _HARD_LOCKS,
    run_bounded_15m_cycles,
)
from printer_v1.sources.governed_execution import (
    build_fixture_source_adapter,
    FIXTURE_SUCCESS,
)

_MINT_1 = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_PAIR_ADDR = "LaneTTestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_VALID_NOTE = "Operator-approved for Lane T test. Reviewed 2026-06-30."

# Used to guarantee elapsed >> 900 s in backdate tests.
_BACKDATE_TS = "2026-01-01T00:00:00+00:00"


def _build_fixture_adapter(mint: str = _MINT_1):
    return build_fixture_source_adapter(
        "dexscreener",
        fixture_kind=FIXTURE_SUCCESS,
        fixture_payload={
            "source_name": "dexscreener",
            "request_kind": "pair_market_snapshot",
            "pairs": [
                {
                    "chain": "solana",
                    "pair_address": _PAIR_ADDR,
                    "token_mint": mint,
                    "symbol": "TEST",
                    "name": "Test Token",
                    "price_usd": 0.00042,
                    "liquidity_usd": 50000.0,
                    "volume_5m": 1000.0,
                    "volume_1h": 12000.0,
                    "volume_24h": 288000.0,
                    "txns_5m": 10,
                    "txns_1h": 120,
                    "txns_24h": 2880,
                    "fdv": 420000.0,
                    "market_cap": 380000.0,
                    "price_change_5m": 0.5,
                    "price_change_1h": 2.1,
                    "price_change_24h": -3.4,
                }
            ],
        },
    )


class _DbTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        self.backup_proof_path = pathlib.Path(self._tmp.name) / "backup.sqlite3"
        self.backup_proof_path.write_bytes(b"backup")
        apply_migrations(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def _count_rows(self, table: str) -> int:
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return row[0] if row else 0
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def _write_token_file(self, tokens: list) -> pathlib.Path:
        tf = pathlib.Path(self._tmp.name) / "tokens.json"
        tf.write_text(json.dumps({"tokens": tokens}), encoding="utf-8")
        return tf

    def _valid_token_entry(self, mint: str = _MINT_1) -> dict:
        return {
            "token_mint": mint,
            "lifecycle_lane": "TRACK_FAST",
            "approved_by_operator": True,
            "operator_note": _VALID_NOTE,
        }

    def _run_e2t(self, max_cycles: int = 1, **kwargs) -> dict:
        token_file = self._write_token_file([self._valid_token_entry()])
        defaults: dict[str, Any] = dict(
            token_list_path=token_file,
            db_path=self.db_path,
            backup_proof_path=self.backup_proof_path,
            operator_approved=True,
            max_cycles=max_cycles,
            _adapter=_build_fixture_adapter(),
        )
        defaults.update(kwargs)
        return run_bounded_15m_cycles(**defaults)

    def _run_e2j(self, *, snapshot_start_id: int | None = None) -> dict:
        token_file = self._write_token_file([self._valid_token_entry()])
        return build_e2j_first_15m_cycle_payload(
            token_file,
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter=_build_fixture_adapter(),
            _snapshot_start_id=snapshot_start_id,
        )

    def _backdate_snapshot(self, snapshot_id: int) -> None:
        """Overwrite a snapshot's captured_at to guarantee elapsed >> 900 s."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "UPDATE printer_token_snapshots SET captured_at = ? WHERE id = ?",
                (_BACKDATE_TS, snapshot_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _fetch_window_row(self, window_id: int) -> dict | None:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM printer_memory_windows WHERE id = ?", (window_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# 1. Import / signature tests
# ---------------------------------------------------------------------------

class LaneTImportTests(unittest.TestCase):
    def test_e2j_module_imports_cleanly(self):
        from printer_v1.operator_cli import e2j_first_15m_cycle
        self.assertIsNotNone(e2j_first_15m_cycle)

    def test_e2t_module_imports_cleanly(self):
        from printer_v1.operator_cli import e2t_bounded_cycle_runner
        self.assertIsNotNone(e2t_bounded_cycle_runner)

    def test_e2j_callable(self):
        self.assertTrue(callable(build_e2j_first_15m_cycle_payload))

    def test_e2t_callable(self):
        self.assertTrue(callable(run_bounded_15m_cycles))

    def test_e2j_accepts_snapshot_start_id_kwarg(self):
        import inspect
        sig = inspect.signature(build_e2j_first_15m_cycle_payload)
        self.assertIn("_snapshot_start_id", sig.parameters)

    def test_e2j_snapshot_start_id_default_none(self):
        import inspect
        sig = inspect.signature(build_e2j_first_15m_cycle_payload)
        self.assertIsNone(sig.parameters["_snapshot_start_id"].default)

    def test_hard_locks_defined(self):
        self.assertIsInstance(_HARD_LOCKS, dict)
        self.assertTrue(len(_HARD_LOCKS) > 0)


# ---------------------------------------------------------------------------
# 2. Single-cycle E2T — first cycle gets no start snapshot
# ---------------------------------------------------------------------------

class LaneTSingleCycleFieldsTests(_DbTestBase):
    def setUp(self):
        super().setUp()
        self._result = self._run_e2t(max_cycles=1)

    def test_single_cycle_completed(self):
        self.assertEqual(self._result["bounded_cycle_status"], E2T_STATUS_COMPLETED)

    def test_cycle_start_snapshot_id_in_result(self):
        self.assertIn("cycle_start_snapshot_id", self._result)

    def test_cycle_start_snapshot_id_is_int(self):
        v = self._result.get("cycle_start_snapshot_id")
        self.assertIsInstance(v, int)

    def test_cycle1_snapshot_id_for_window_is_int(self):
        c = self._result["cycles"][0]
        v = c.get("snapshot_id_for_window")
        self.assertIsInstance(v, int)

    def test_cycle1_snapshot_start_id_is_none(self):
        c = self._result["cycles"][0]
        self.assertIsNone(c.get("snapshot_start_id"))

    def test_cycle1_window_start_at_is_none(self):
        c = self._result["cycles"][0]
        self.assertIsNone(c.get("window_start_at"))

    def test_cycle1_lane_q_integrity_eligible_false(self):
        c = self._result["cycles"][0]
        self.assertFalse(c.get("lane_q_integrity_eligible"))

    def test_result_json_serializable(self):
        json.dumps(self._result)


# ---------------------------------------------------------------------------
# 3. Multi-cycle E2T threading — cycle 2 receives cycle 1's snapshot as start
# ---------------------------------------------------------------------------

class LaneTMultiCycleThreadingTests(_DbTestBase):
    def setUp(self):
        super().setUp()
        self._result2 = self._run_e2t(max_cycles=2)

    def test_2cycle_completed(self):
        self.assertEqual(self._result2["bounded_cycle_status"], E2T_STATUS_COMPLETED)
        self.assertEqual(self._result2["completed_cycle_count"], 2)

    def test_cycle_start_snapshot_id_set(self):
        v = self._result2.get("cycle_start_snapshot_id")
        self.assertIsInstance(v, int)

    def test_cycle_start_snapshot_id_matches_cycle1_close_snap(self):
        csi = self._result2["cycle_start_snapshot_id"]
        win_snap = self._result2["cycles"][0].get("snapshot_id_for_window")
        self.assertEqual(csi, win_snap)

    def test_cycle1_snapshot_start_id_still_none(self):
        c = self._result2["cycles"][0]
        self.assertIsNone(c.get("snapshot_start_id"))

    def test_cycle2_snapshot_start_id_not_none(self):
        c = self._result2["cycles"][1]
        self.assertIsNotNone(c.get("snapshot_start_id"))

    def test_cycle2_snapshot_start_id_equals_cycle_start_snapshot(self):
        csi = self._result2["cycle_start_snapshot_id"]
        c2 = self._result2["cycles"][1]
        self.assertEqual(c2.get("snapshot_start_id"), csi)

    def test_cycle2_window_start_at_not_none(self):
        c = self._result2["cycles"][1]
        self.assertIsNotNone(c.get("window_start_at"))

    def test_cycle2_window_end_at_not_none(self):
        c = self._result2["cycles"][1]
        self.assertIsNotNone(c.get("window_end_at"))

    def test_cycle2_elapsed_seconds_nonnegative(self):
        c = self._result2["cycles"][1]
        elap = c.get("elapsed_seconds")
        self.assertIsInstance(elap, float)
        self.assertGreaterEqual(elap, 0.0)

    def test_cycle2_lane_q_integrity_eligible_false_fixture_run(self):
        # In fixture runs both snapshots are taken in the same second → < 900 s.
        c = self._result2["cycles"][1]
        self.assertFalse(c.get("lane_q_integrity_eligible"))


# ---------------------------------------------------------------------------
# 4. 3-cycle run — all subsequent cycles carry cycle-1 snapshot as start
# ---------------------------------------------------------------------------

class LaneTThreeCycleThreadingTests(_DbTestBase):
    def setUp(self):
        super().setUp()
        self._result3 = self._run_e2t(max_cycles=3)

    def test_3cycle_completed(self):
        self.assertEqual(self._result3["bounded_cycle_status"], E2T_STATUS_COMPLETED)
        self.assertEqual(self._result3["completed_cycle_count"], 3)

    def test_cycle3_snapshot_start_id_equals_cycle1_close_snap(self):
        csi = self._result3["cycle_start_snapshot_id"]
        c3 = self._result3["cycles"][2]
        self.assertEqual(c3.get("snapshot_start_id"), csi)

    def test_all_cycles_have_snapshot_end_id_field(self):
        for c in self._result3["cycles"]:
            self.assertIn("snapshot_end_id", c)

    def test_cycle2_and_cycle3_have_same_snapshot_start_id(self):
        c2_start = self._result3["cycles"][1].get("snapshot_start_id")
        c3_start = self._result3["cycles"][2].get("snapshot_start_id")
        self.assertEqual(c2_start, c3_start)
        self.assertIsNotNone(c2_start)


# ---------------------------------------------------------------------------
# 5. Direct E2J calls — prove _snapshot_start_id threads correctly
# ---------------------------------------------------------------------------

class LaneTE2JDirectTests(_DbTestBase):
    def test_e2j_no_start_returns_snapshot_id_for_window(self):
        r = self._run_e2j()
        self.assertIsInstance(r.get("snapshot_id_for_window"), int)

    def test_e2j_no_start_snapshot_start_id_is_none(self):
        r = self._run_e2j()
        self.assertIsNone(r.get("snapshot_start_id"))

    def test_e2j_no_start_window_start_at_is_none(self):
        r = self._run_e2j()
        self.assertIsNone(r.get("window_start_at"))

    def test_e2j_no_start_lane_q_integrity_eligible_false(self):
        r = self._run_e2j()
        self.assertFalse(r.get("lane_q_integrity_eligible"))

    def test_e2j_with_start_snapshot_start_id_set(self):
        r1 = self._run_e2j()
        snap1_id = r1["snapshot_id_for_window"]
        r2 = self._run_e2j(snapshot_start_id=snap1_id)
        self.assertEqual(r2.get("snapshot_start_id"), snap1_id)

    def test_e2j_with_start_window_start_at_not_none(self):
        r1 = self._run_e2j()
        snap1_id = r1["snapshot_id_for_window"]
        r2 = self._run_e2j(snapshot_start_id=snap1_id)
        self.assertIsNotNone(r2.get("window_start_at"))

    def test_e2j_with_start_window_end_at_not_none(self):
        r1 = self._run_e2j()
        snap1_id = r1["snapshot_id_for_window"]
        r2 = self._run_e2j(snapshot_start_id=snap1_id)
        self.assertIsNotNone(r2.get("window_end_at"))

    def test_e2j_return_has_all_new_fields(self):
        r = self._run_e2j()
        for field in ("snapshot_id_for_window", "snapshot_start_id", "snapshot_end_id",
                      "window_start_at", "window_end_at", "elapsed_seconds",
                      "lane_q_integrity_eligible"):
            self.assertIn(field, r, f"missing field {field!r}")


# ---------------------------------------------------------------------------
# 6. Elapsed-boundary tests — backdate snap1 to guarantee >= 900 s
# ---------------------------------------------------------------------------

class LaneTElapsedBoundaryTests(_DbTestBase):
    def _setup_backdated_two_cycle(self):
        """Run E2J twice; backdate snap1 before the second call."""
        r1 = self._run_e2j()
        snap1_id = r1["snapshot_id_for_window"]
        self._backdate_snapshot(snap1_id)
        r2 = self._run_e2j(snapshot_start_id=snap1_id)
        return snap1_id, r1, r2

    def test_cycle1_snapshot_id_for_window_present(self):
        r1 = self._run_e2j()
        self.assertIsInstance(r1.get("snapshot_id_for_window"), int)

    def test_backdate_window_start_at_equals_backdate_ts(self):
        _, _, r2 = self._setup_backdated_two_cycle()
        self.assertEqual(r2.get("window_start_at"), _BACKDATE_TS)

    def test_backdate_window_end_at_is_recent(self):
        _, _, r2 = self._setup_backdated_two_cycle()
        wea = r2.get("window_end_at")
        self.assertIsNotNone(wea)
        # end_at is well after the 2026-01-01 backdate
        self.assertGreater(wea, _BACKDATE_TS)

    def test_backdate_elapsed_seconds_over_900(self):
        _, _, r2 = self._setup_backdated_two_cycle()
        elap = r2.get("elapsed_seconds")
        self.assertIsInstance(elap, float)
        self.assertGreater(elap, 900.0)

    def test_backdate_lane_q_integrity_eligible_true(self):
        _, _, r2 = self._setup_backdated_two_cycle()
        self.assertTrue(r2.get("lane_q_integrity_eligible"))

    def test_backdate_snapshot_start_id_equals_snap1(self):
        snap1_id, _, r2 = self._setup_backdated_two_cycle()
        self.assertEqual(r2.get("snapshot_start_id"), snap1_id)

    def test_no_backdate_lane_q_integrity_eligible_false(self):
        r1 = self._run_e2j()
        snap1_id = r1["snapshot_id_for_window"]
        r2 = self._run_e2j(snapshot_start_id=snap1_id)
        self.assertFalse(r2.get("lane_q_integrity_eligible"))

    def test_no_backdate_elapsed_under_900(self):
        r1 = self._run_e2j()
        snap1_id = r1["snapshot_id_for_window"]
        r2 = self._run_e2j(snapshot_start_id=snap1_id)
        elap = r2.get("elapsed_seconds")
        self.assertIsInstance(elap, float)
        self.assertLess(elap, 900.0)


# ---------------------------------------------------------------------------
# 7. DB write verification
# ---------------------------------------------------------------------------

class LaneTDBWriteTests(_DbTestBase):
    def _setup_backdated_db(self):
        r1 = self._run_e2j()
        snap1_id = r1["snapshot_id_for_window"]
        win1_id = r1["memory_window_id"]
        self._backdate_snapshot(snap1_id)
        r2 = self._run_e2j(snapshot_start_id=snap1_id)
        win2_id = r2["memory_window_id"]
        return snap1_id, win1_id, r2, win2_id

    def test_cycle1_db_window_start_at_null(self):
        r1 = self._run_e2j()
        row = self._fetch_window_row(r1["memory_window_id"])
        self.assertIsNotNone(row)
        self.assertIsNone(row.get("window_start_at"))

    def test_cycle1_db_snapshot_start_id_null(self):
        r1 = self._run_e2j()
        row = self._fetch_window_row(r1["memory_window_id"])
        self.assertIsNone(row.get("snapshot_start_id"))

    def test_cycle2_db_window_start_at_populated_after_backdate(self):
        _, _, _, win2_id = self._setup_backdated_db()
        row = self._fetch_window_row(win2_id)
        self.assertIsNotNone(row)
        self.assertIsNotNone(row.get("window_start_at"))

    def test_cycle2_db_snapshot_start_id_equals_snap1(self):
        snap1_id, _, _, win2_id = self._setup_backdated_db()
        row = self._fetch_window_row(win2_id)
        self.assertEqual(row.get("snapshot_start_id"), snap1_id)

    def test_cycle2_db_snapshot_end_id_set(self):
        _, _, r2, win2_id = self._setup_backdated_db()
        row = self._fetch_window_row(win2_id)
        self.assertIsNotNone(row.get("snapshot_end_id"))
        self.assertEqual(row.get("snapshot_end_id"), r2.get("snapshot_end_id"))

    def test_two_windows_in_db_after_two_cycles(self):
        self._run_e2j()
        self._run_e2j()
        self.assertEqual(self._count_rows("printer_memory_windows"), 2)

    def test_cycle2_db_window_end_at_populated_after_backdate(self):
        _, _, _, win2_id = self._setup_backdated_db()
        row = self._fetch_window_row(win2_id)
        self.assertIsNotNone(row.get("window_end_at"))


# ---------------------------------------------------------------------------
# 8. E2T result and cycle_summary fields
# ---------------------------------------------------------------------------

class LaneTE2TResultFieldsTests(_DbTestBase):
    def setUp(self):
        super().setUp()
        self._res = self._run_e2t(max_cycles=2)

    def test_cycle_start_snapshot_id_in_result(self):
        self.assertIn("cycle_start_snapshot_id", self._res)

    def test_result_json_serializable(self):
        json.dumps(self._res)

    def test_cycle_summary_has_snapshot_id_for_window(self):
        for c in self._res["cycles"]:
            self.assertIn("snapshot_id_for_window", c)

    def test_cycle_summary_has_window_start_at(self):
        for c in self._res["cycles"]:
            self.assertIn("window_start_at", c)

    def test_cycle_summary_has_lane_q_integrity_eligible(self):
        for c in self._res["cycles"]:
            self.assertIn("lane_q_integrity_eligible", c)

    def test_cycle_summary_has_elapsed_seconds(self):
        for c in self._res["cycles"]:
            self.assertIn("elapsed_seconds", c)


# ---------------------------------------------------------------------------
# 9. Locks / forbidden tables
# ---------------------------------------------------------------------------

class LaneTLocksTests(_DbTestBase):
    def setUp(self):
        super().setUp()
        self._res = self._run_e2t(max_cycles=2)

    def test_no_paper_decisions(self):
        self.assertEqual(self._count_rows("printer_paper_decisions"), 0)

    def test_no_paper_positions(self):
        self.assertEqual(self._count_rows("printer_paper_positions"), 0)

    def test_no_paper_trade_events(self):
        self.assertEqual(self._count_rows("printer_paper_trade_events"), 0)

    def test_no_paper_trade_audits(self):
        self.assertEqual(self._count_rows("printer_paper_trade_audits"), 0)

    def test_no_episodes(self):
        self.assertEqual(self._count_rows("printer_episodes"), 0)

    def test_paper_decisions_created_zero_in_result(self):
        self.assertEqual(self._res.get("paper_decisions_created"), 0)


# ---------------------------------------------------------------------------
# 10. Hard locks
# ---------------------------------------------------------------------------

class LaneTHardLocksTests(_DbTestBase):
    def test_hard_locks_in_result(self):
        res = self._run_e2t(max_cycles=1)
        self.assertIn("hard_locks", res)

    def test_hard_locks_no_buy_sell_hold(self):
        self.assertIn("no_buy_sell_hold", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_buy_sell_hold"])

    def test_hard_locks_no_live_trading(self):
        self.assertIn("no_live_trading", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_live_trading"])

    def test_hard_locks_no_unbounded_loop(self):
        self.assertIn("no_unbounded_loop", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_unbounded_loop"])

    def test_hard_locks_all_true(self):
        for key, val in _HARD_LOCKS.items():
            self.assertTrue(val, f"hard lock {key!r} must be True")


# ---------------------------------------------------------------------------
# 11. Blocked-path fields
# ---------------------------------------------------------------------------

class LaneTBlockedPathTests(_DbTestBase):
    def _run_e2j_blocked(self) -> dict:
        token_file = self._write_token_file([self._valid_token_entry()])
        return build_e2j_first_15m_cycle_payload(
            token_file,
            self.db_path,
            self.backup_proof_path,
            operator_approved=False,  # blocked here
            _adapter=_build_fixture_adapter(),
            _snapshot_start_id=99,
        )

    def test_blocked_status(self):
        r = self._run_e2j_blocked()
        self.assertEqual(r.get("e2j_status"), E2J_STATUS_BLOCKED)

    def test_blocked_snapshot_id_for_window_none(self):
        r = self._run_e2j_blocked()
        self.assertIsNone(r.get("snapshot_id_for_window"))

    def test_blocked_snapshot_start_id_none(self):
        r = self._run_e2j_blocked()
        self.assertIsNone(r.get("snapshot_start_id"))

    def test_blocked_window_start_at_none(self):
        r = self._run_e2j_blocked()
        self.assertIsNone(r.get("window_start_at"))

    def test_blocked_lane_q_integrity_eligible_false(self):
        r = self._run_e2j_blocked()
        self.assertFalse(r.get("lane_q_integrity_eligible"))


if __name__ == "__main__":
    unittest.main()

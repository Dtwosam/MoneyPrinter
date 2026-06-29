"""
Lane R — E2O Real 15m Window Writer Update

Tests prove:
- close_15m_memory_window_from_snapshot accepts snapshot_start_id param
- window_start_at written from start snapshot captured_at (real evidence)
- window_end_at written from close snapshot captured_at (real evidence)
- snapshot_start_id written to DB row when provided
- snapshot_end_id written to DB row (= close snapshot_id) when start provided
- elapsed_seconds present in result
- lane_q_integrity_eligible=True when elapsed >= 900s
- lane_q_integrity_eligible=False when elapsed < 900s
- lane_q_integrity_eligible=False when snapshot_start_id not provided
- not_eligible_reason present when lane_q_integrity_eligible=False
- window_start_at/window_end_at are NULL in DB when no start snapshot provided
- snapshot_start_id/snapshot_end_id are NULL in DB when no start snapshot provided
- window row always written even when elapsed < 900s (Lane Q blocks, not writer)
- window_start_at comes from snapshot captured_at — not wall clock
- snapshot_start_id not in DB → NULL fields, not_eligible_reason, still creates row
- idempotent: second call returns E2O_WINDOW_DUPLICATE
- hard_locks all True in result
- Lane Q check_window_integrity passes for windows with real 15m fields
- Lane Q check_window_integrity blocks windows with NULL window_start_at
- opened_at reflects window_start_at when start snapshot provided
- closed_at always = close snapshot captured_at
"""

import pathlib
import sqlite3
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.e2o_memory_window_close import (
    E2O_STATUS_BLOCKED,
    E2O_STATUS_CREATED,
    E2O_STATUS_DUPLICATE,
    E2O_WINDOW_KIND,
    E2O_WINDOW_STATUS,
    _HARD_LOCKS,
    close_15m_memory_window_from_snapshot,
)
from printer_v1.operator_cli.lane_q_15m_window_integrity_guard import (
    LANE_Q_VALID,
    check_window_integrity,
)

_MINT = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_PAIR_ADDR = "LaneRTestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

# Real 15m: 901 seconds elapsed
_TS_START = "2026-06-29T10:00:00+00:00"
_TS_CLOSE_VALID = "2026-06-29T10:15:01+00:00"   # 901s after start
# Instant: same second as start
_TS_CLOSE_INSTANT = "2026-06-29T10:00:00+00:00"  # 0s elapsed
# Just under 15m
_TS_CLOSE_SHORT = "2026-06-29T10:14:59+00:00"    # 899s — not enough


class _DbBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        apply_migrations(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _insert_token(self, conn: sqlite3.Connection, mint: str = _MINT) -> int:
        now = "2026-06-29T00:00:00+00:00"
        cursor = conn.execute(
            "INSERT INTO printer_tokens"
            " (token_mint, chain, symbol, name, first_seen_at, last_seen_at,"
            "  token_status, created_at, updated_at)"
            " VALUES (?, 'solana', 'TST', 'Test', ?, ?, 'TRACKING', ?, ?)",
            (mint, now, now, now, now),
        )
        return int(cursor.lastrowid)

    def _insert_pair(self, conn: sqlite3.Connection, token_id: int) -> int:
        now = "2026-06-29T00:00:00+00:00"
        cursor = conn.execute(
            "INSERT INTO printer_pairs"
            " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at,"
            "  created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_id, _PAIR_ADDR, _PAIR_ADDR, now, now, now, now),
        )
        return int(cursor.lastrowid)

    def _insert_snapshot(
        self,
        conn: sqlite3.Connection,
        token_id: int,
        pair_id: int | None,
        captured_at: str,
        tracking_lane: str = "TRACK_FAST",
    ) -> int:
        cursor = conn.execute(
            "INSERT INTO printer_token_snapshots"
            " (token_id, pair_id, captured_at, tracking_lane, snapshot_mode,"
            "  source_status, data_quality_label, created_at)"
            " VALUES (?, ?, ?, ?, 'FIRST_15M_CYCLE', 'COMPLETE', 'CLEAN_DATA', datetime('now'))",
            (token_id, pair_id, captured_at, tracking_lane),
        )
        return int(cursor.lastrowid)

    def _setup_token_pair(self) -> tuple[int, int]:
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            conn.commit()
        finally:
            conn.close()
        return token_id, pair_id

    def _close_window(
        self,
        snapshot_id: int,
        *,
        snapshot_start_id: int | None = None,
        mint: str = _MINT,
    ) -> dict:
        conn = self._connect()
        try:
            result = close_15m_memory_window_from_snapshot(
                conn, snapshot_id, mint, snapshot_start_id=snapshot_start_id
            )
            conn.commit()
        finally:
            conn.close()
        return result

    def _read_window(self, window_id: int) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM printer_memory_windows WHERE id = ?", (window_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def _make_two_snapshots(self) -> tuple[int, int, int, int]:
        """Return (token_id, pair_id, start_snapshot_id, close_snapshot_id)."""
        token_id, pair_id = self._setup_token_pair()
        conn = self._connect()
        try:
            start_id = self._insert_snapshot(conn, token_id, pair_id, _TS_START)
            close_id = self._insert_snapshot(conn, token_id, pair_id, _TS_CLOSE_VALID)
            conn.commit()
        finally:
            conn.close()
        return token_id, pair_id, start_id, close_id


# ---------------------------------------------------------------------------
# Proof class 1: Import / signature
# ---------------------------------------------------------------------------

class LaneRImportTests(unittest.TestCase):
    def test_close_accepts_snapshot_start_id_kwarg(self):
        import inspect
        sig = inspect.signature(close_15m_memory_window_from_snapshot)
        self.assertIn("snapshot_start_id", sig.parameters)

    def test_snapshot_start_id_default_is_none(self):
        import inspect
        sig = inspect.signature(close_15m_memory_window_from_snapshot)
        self.assertIsNone(sig.parameters["snapshot_start_id"].default)

    def test_min_elapsed_seconds_constant_exists(self):
        from printer_v1.operator_cli.e2o_memory_window_close import _MIN_ELAPSED_SECONDS
        self.assertEqual(_MIN_ELAPSED_SECONDS, 900.0)


# ---------------------------------------------------------------------------
# Proof class 2: Valid 15m evidence (901s elapsed)
# ---------------------------------------------------------------------------

class LaneRValidIntegrityFieldsTests(_DbBase):
    def setUp(self):
        super().setUp()
        _, _, self.start_id, self.close_id = self._make_two_snapshots()
        self.result = self._close_window(
            self.close_id, snapshot_start_id=self.start_id
        )

    def test_status_created(self):
        self.assertEqual(self.result["e2o_status"], E2O_STATUS_CREATED)

    def test_lane_q_integrity_eligible_true(self):
        self.assertTrue(self.result["lane_q_integrity_eligible"])

    def test_elapsed_seconds_in_result(self):
        self.assertIn("elapsed_seconds", self.result)

    def test_elapsed_seconds_at_least_900(self):
        self.assertGreaterEqual(self.result["elapsed_seconds"], 900.0)

    def test_window_start_at_in_result(self):
        self.assertEqual(self.result["window_start_at"], _TS_START)

    def test_window_end_at_in_result(self):
        self.assertEqual(self.result["window_end_at"], _TS_CLOSE_VALID)

    def test_snapshot_start_id_in_result(self):
        self.assertEqual(self.result["snapshot_start_id"], self.start_id)

    def test_snapshot_end_id_in_result(self):
        self.assertEqual(self.result["snapshot_end_id"], self.close_id)

    def test_window_start_at_written_to_db(self):
        row = self._read_window(self.result["window_id"])
        self.assertEqual(row["window_start_at"], _TS_START)

    def test_window_end_at_written_to_db(self):
        row = self._read_window(self.result["window_id"])
        self.assertEqual(row["window_end_at"], _TS_CLOSE_VALID)

    def test_snapshot_start_id_written_to_db(self):
        row = self._read_window(self.result["window_id"])
        self.assertEqual(int(row["snapshot_start_id"]), self.start_id)

    def test_snapshot_end_id_written_to_db(self):
        row = self._read_window(self.result["window_id"])
        self.assertEqual(int(row["snapshot_end_id"]), self.close_id)

    def test_opened_at_matches_start_snapshot(self):
        # opened_at reflects the real window open time
        self.assertEqual(self.result["opened_at"], _TS_START)

    def test_closed_at_matches_close_snapshot(self):
        self.assertEqual(self.result["closed_at"], _TS_CLOSE_VALID)

    def test_no_not_eligible_reason_when_eligible(self):
        self.assertNotIn("not_eligible_reason", self.result)


# ---------------------------------------------------------------------------
# Proof class 3: Single-snapshot path (no snapshot_start_id)
# ---------------------------------------------------------------------------

class LaneRNoStartSnapshotTests(_DbBase):
    def setUp(self):
        super().setUp()
        token_id, pair_id = self._setup_token_pair()
        conn = self._connect()
        try:
            self.snap_id = self._insert_snapshot(conn, token_id, pair_id, _TS_START)
            conn.commit()
        finally:
            conn.close()
        self.result = self._close_window(self.snap_id)  # no snapshot_start_id

    def test_status_created(self):
        self.assertEqual(self.result["e2o_status"], E2O_STATUS_CREATED)

    def test_lane_q_integrity_eligible_false(self):
        self.assertFalse(self.result["lane_q_integrity_eligible"])

    def test_not_eligible_reason_present(self):
        self.assertIn("not_eligible_reason", self.result)

    def test_window_start_at_none_in_result(self):
        self.assertIsNone(self.result["window_start_at"])

    def test_window_end_at_none_in_result(self):
        self.assertIsNone(self.result["window_end_at"])

    def test_snapshot_start_id_none_in_result(self):
        self.assertIsNone(self.result["snapshot_start_id"])

    def test_snapshot_end_id_none_in_result(self):
        self.assertIsNone(self.result["snapshot_end_id"])

    def test_window_start_at_null_in_db(self):
        row = self._read_window(self.result["window_id"])
        self.assertIsNone(row["window_start_at"])

    def test_window_end_at_null_in_db(self):
        row = self._read_window(self.result["window_id"])
        self.assertIsNone(row["window_end_at"])

    def test_snapshot_start_id_null_in_db(self):
        row = self._read_window(self.result["window_id"])
        self.assertIsNone(row["snapshot_start_id"])

    def test_snapshot_end_id_null_in_db(self):
        row = self._read_window(self.result["window_id"])
        self.assertIsNone(row["snapshot_end_id"])

    def test_row_still_created(self):
        self.assertIn("window_id", self.result)
        self.assertIsNotNone(self.result["window_id"])

    def test_elapsed_seconds_none(self):
        self.assertIsNone(self.result["elapsed_seconds"])


# ---------------------------------------------------------------------------
# Proof class 4: Elapsed < 900s — writer does NOT block, but reports ineligible
# ---------------------------------------------------------------------------

class LaneRShortElapsedTests(_DbBase):
    def setUp(self):
        super().setUp()
        token_id, pair_id = self._setup_token_pair()
        conn = self._connect()
        try:
            self.start_id = self._insert_snapshot(conn, token_id, pair_id, _TS_START)
            self.close_id = self._insert_snapshot(conn, token_id, pair_id, _TS_CLOSE_SHORT)
            conn.commit()
        finally:
            conn.close()
        self.result = self._close_window(
            self.close_id, snapshot_start_id=self.start_id
        )

    def test_status_is_created_not_blocked(self):
        # Writer does not block — Lane Q does
        self.assertEqual(self.result["e2o_status"], E2O_STATUS_CREATED)

    def test_window_row_written(self):
        self.assertIsNotNone(self.result.get("window_id"))

    def test_lane_q_integrity_eligible_false(self):
        self.assertFalse(self.result["lane_q_integrity_eligible"])

    def test_not_eligible_reason_present(self):
        self.assertIn("not_eligible_reason", self.result)

    def test_elapsed_seconds_below_900(self):
        self.assertLess(self.result["elapsed_seconds"], 900.0)

    def test_integrity_fields_still_written_to_db(self):
        # Fields written even though elapsed < 900s (Lane Q uses them to block)
        row = self._read_window(self.result["window_id"])
        self.assertIsNotNone(row["window_start_at"])
        self.assertIsNotNone(row["window_end_at"])
        self.assertIsNotNone(row["snapshot_start_id"])
        self.assertIsNotNone(row["snapshot_end_id"])


# ---------------------------------------------------------------------------
# Proof class 5: Instant window (same timestamp for start + close)
# ---------------------------------------------------------------------------

class LaneRInstantWindowTests(_DbBase):
    def setUp(self):
        super().setUp()
        token_id, pair_id = self._setup_token_pair()
        conn = self._connect()
        try:
            self.start_id = self._insert_snapshot(conn, token_id, pair_id, _TS_START)
            self.close_id = self._insert_snapshot(conn, token_id, pair_id, _TS_CLOSE_INSTANT)
            conn.commit()
        finally:
            conn.close()
        self.result = self._close_window(
            self.close_id, snapshot_start_id=self.start_id
        )

    def test_created_not_blocked(self):
        self.assertEqual(self.result["e2o_status"], E2O_STATUS_CREATED)

    def test_lane_q_integrity_eligible_false(self):
        self.assertFalse(self.result["lane_q_integrity_eligible"])

    def test_elapsed_seconds_zero(self):
        self.assertEqual(self.result["elapsed_seconds"], 0.0)

    def test_not_eligible_reason_present(self):
        self.assertIn("not_eligible_reason", self.result)


# ---------------------------------------------------------------------------
# Proof class 6: Timestamps come from real snapshot captured_at (not wall clock)
# ---------------------------------------------------------------------------

class LaneRTimestampSourceTests(_DbBase):
    def test_window_start_at_from_start_snapshot_captured_at(self):
        token_id, pair_id = self._setup_token_pair()
        conn = self._connect()
        try:
            start_id = self._insert_snapshot(conn, token_id, pair_id, _TS_START)
            close_id = self._insert_snapshot(conn, token_id, pair_id, _TS_CLOSE_VALID)
            conn.commit()
        finally:
            conn.close()
        result = self._close_window(close_id, snapshot_start_id=start_id)
        # Must equal the DB captured_at of the start snapshot, not _utc_now()
        self.assertEqual(result["window_start_at"], _TS_START)

    def test_window_end_at_from_close_snapshot_captured_at(self):
        token_id, pair_id = self._setup_token_pair()
        conn = self._connect()
        try:
            start_id = self._insert_snapshot(conn, token_id, pair_id, _TS_START)
            close_id = self._insert_snapshot(conn, token_id, pair_id, _TS_CLOSE_VALID)
            conn.commit()
        finally:
            conn.close()
        result = self._close_window(close_id, snapshot_start_id=start_id)
        self.assertEqual(result["window_end_at"], _TS_CLOSE_VALID)

    def test_different_start_times_produce_different_window_start_at(self):
        token_id, pair_id = self._setup_token_pair()
        ts_early = "2026-06-29T08:00:00+00:00"
        ts_late = "2026-06-29T09:00:00+00:00"
        conn = self._connect()
        try:
            start_early = self._insert_snapshot(conn, token_id, pair_id, ts_early)
            start_late = self._insert_snapshot(conn, token_id, pair_id, ts_late)
            close_id = self._insert_snapshot(conn, token_id, pair_id, _TS_CLOSE_VALID)
            conn.commit()
        finally:
            conn.close()
        result_a = self._close_window(close_id, snapshot_start_id=start_early)
        self.assertEqual(result_a["window_start_at"], ts_early)
        # Duplicate guard: close_id already used, so second call returns DUPLICATE
        result_b = self._close_window(close_id, snapshot_start_id=start_late)
        self.assertEqual(result_b["e2o_status"], E2O_STATUS_DUPLICATE)


# ---------------------------------------------------------------------------
# Proof class 7: snapshot_start_id not in DB
# ---------------------------------------------------------------------------

class LaneRMissingStartSnapshotTests(_DbBase):
    def setUp(self):
        super().setUp()
        token_id, pair_id = self._setup_token_pair()
        conn = self._connect()
        try:
            self.close_id = self._insert_snapshot(conn, token_id, pair_id, _TS_CLOSE_VALID)
            conn.commit()
        finally:
            conn.close()
        self.result = self._close_window(self.close_id, snapshot_start_id=99999)

    def test_status_created_despite_missing_start(self):
        self.assertEqual(self.result["e2o_status"], E2O_STATUS_CREATED)

    def test_lane_q_integrity_eligible_false(self):
        self.assertFalse(self.result["lane_q_integrity_eligible"])

    def test_not_eligible_reason_present(self):
        self.assertIn("not_eligible_reason", self.result)

    def test_window_start_at_null(self):
        self.assertIsNone(self.result["window_start_at"])

    def test_snapshot_start_id_null(self):
        self.assertIsNone(self.result["snapshot_start_id"])

    def test_db_row_has_null_integrity_fields(self):
        row = self._read_window(self.result["window_id"])
        self.assertIsNone(row["window_start_at"])
        self.assertIsNone(row["snapshot_start_id"])


# ---------------------------------------------------------------------------
# Proof class 8: Lane Q integration — valid 15m fields pass guard
# ---------------------------------------------------------------------------

class LaneRLaneQIntegrationTests(_DbBase):
    def test_valid_15m_window_passes_lane_q_check(self):
        _, _, start_id, close_id = self._make_two_snapshots()
        result = self._close_window(close_id, snapshot_start_id=start_id)
        self.assertEqual(result["e2o_status"], E2O_STATUS_CREATED)
        # Build a synthetic row dict as Lane Q expects
        row = self._read_window(result["window_id"])
        lane_q = check_window_integrity({
            "id": row["id"],
            "window_kind": row["window_kind"],
            "data_quality_label": row["data_quality_label"],
            "do_not_train": row["do_not_train"],
            "memory_status": row["memory_status"],
            "memory_quality_label": row.get("memory_quality_label"),
            "window_start_at": row["window_start_at"],
            "window_end_at": row["window_end_at"],
            "snapshot_start_id": row["snapshot_start_id"],
            "snapshot_end_id": row["snapshot_end_id"],
        })
        self.assertEqual(lane_q["lane_q_status"], LANE_Q_VALID)

    def test_null_fields_window_blocked_by_lane_q(self):
        token_id, pair_id = self._setup_token_pair()
        conn = self._connect()
        try:
            snap_id = self._insert_snapshot(conn, token_id, pair_id, _TS_START)
            conn.commit()
        finally:
            conn.close()
        result = self._close_window(snap_id)  # no start snapshot
        row = self._read_window(result["window_id"])
        lane_q = check_window_integrity({
            "id": row["id"],
            "window_kind": row["window_kind"],
            "data_quality_label": row["data_quality_label"],
            "do_not_train": row["do_not_train"],
            "memory_status": row["memory_status"],
            "memory_quality_label": row.get("memory_quality_label"),
            "window_start_at": row["window_start_at"],
            "window_end_at": row["window_end_at"],
            "snapshot_start_id": row["snapshot_start_id"],
            "snapshot_end_id": row["snapshot_end_id"],
        })
        self.assertNotEqual(lane_q["lane_q_status"], LANE_Q_VALID)
        self.assertIn("missing_window_start_at", lane_q["blocked_reasons"])

    def test_short_elapsed_window_blocked_by_lane_q(self):
        token_id, pair_id = self._setup_token_pair()
        conn = self._connect()
        try:
            start_id = self._insert_snapshot(conn, token_id, pair_id, _TS_START)
            close_id = self._insert_snapshot(conn, token_id, pair_id, _TS_CLOSE_SHORT)
            conn.commit()
        finally:
            conn.close()
        result = self._close_window(close_id, snapshot_start_id=start_id)
        row = self._read_window(result["window_id"])
        lane_q = check_window_integrity({
            "id": row["id"],
            "window_kind": row["window_kind"],
            "data_quality_label": row["data_quality_label"],
            "do_not_train": row["do_not_train"],
            "memory_status": row["memory_status"],
            "memory_quality_label": row.get("memory_quality_label"),
            "window_start_at": row["window_start_at"],
            "window_end_at": row["window_end_at"],
            "snapshot_start_id": row["snapshot_start_id"],
            "snapshot_end_id": row["snapshot_end_id"],
        })
        self.assertNotEqual(lane_q["lane_q_status"], LANE_Q_VALID)
        self.assertIn("elapsed_seconds_below_900", lane_q["blocked_reasons"])


# ---------------------------------------------------------------------------
# Proof class 9: Idempotency
# ---------------------------------------------------------------------------

class LaneRIdempotencyTests(_DbBase):
    def test_second_call_returns_duplicate(self):
        _, _, start_id, close_id = self._make_two_snapshots()
        r1 = self._close_window(close_id, snapshot_start_id=start_id)
        self.assertEqual(r1["e2o_status"], E2O_STATUS_CREATED)
        r2 = self._close_window(close_id, snapshot_start_id=start_id)
        self.assertEqual(r2["e2o_status"], E2O_STATUS_DUPLICATE)

    def test_duplicate_has_existing_window_id(self):
        _, _, start_id, close_id = self._make_two_snapshots()
        r1 = self._close_window(close_id, snapshot_start_id=start_id)
        r2 = self._close_window(close_id, snapshot_start_id=start_id)
        self.assertEqual(r2["existing_window_id"], r1["window_id"])

    def test_no_extra_row_on_duplicate(self):
        _, _, start_id, close_id = self._make_two_snapshots()
        self._close_window(close_id, snapshot_start_id=start_id)
        self._close_window(close_id, snapshot_start_id=start_id)
        conn = self._connect()
        try:
            count = int(
                conn.execute("SELECT COUNT(*) FROM printer_memory_windows").fetchone()[0]
            )
        finally:
            conn.close()
        self.assertEqual(count, 1)

    def test_idempotent_without_start_snapshot(self):
        token_id, pair_id = self._setup_token_pair()
        conn = self._connect()
        try:
            snap_id = self._insert_snapshot(conn, token_id, pair_id, _TS_START)
            conn.commit()
        finally:
            conn.close()
        r1 = self._close_window(snap_id)
        r2 = self._close_window(snap_id)
        self.assertEqual(r1["e2o_status"], E2O_STATUS_CREATED)
        self.assertEqual(r2["e2o_status"], E2O_STATUS_DUPLICATE)


# ---------------------------------------------------------------------------
# Proof class 10: Hard locks
# ---------------------------------------------------------------------------

class LaneRLocksTests(_DbBase):
    def _result_with_valid_15m(self) -> dict:
        _, _, start_id, close_id = self._make_two_snapshots()
        return self._close_window(close_id, snapshot_start_id=start_id)

    def _result_no_start(self) -> dict:
        token_id, pair_id = self._setup_token_pair()
        conn = self._connect()
        try:
            snap_id = self._insert_snapshot(conn, token_id, pair_id, _TS_START)
            conn.commit()
        finally:
            conn.close()
        return self._close_window(snap_id)

    def test_hard_locks_in_result_valid_15m(self):
        result = self._result_with_valid_15m()
        self.assertIn("hard_locks", result)
        for key, val in result["hard_locks"].items():
            self.assertTrue(val, f"hard lock {key!r} must be True")

    def test_hard_locks_in_result_no_start(self):
        result = self._result_no_start()
        self.assertIn("hard_locks", result)
        for key, val in result["hard_locks"].items():
            self.assertTrue(val, f"hard lock {key!r} must be True")

    def test_no_buy_sell_hold_lock(self):
        result = self._result_with_valid_15m()
        self.assertTrue(result["hard_locks"]["no_buy_sell_hold"])

    def test_no_paper_decisions_lock(self):
        result = self._result_with_valid_15m()
        self.assertTrue(result["hard_locks"]["no_paper_decisions"])

    def test_no_memory_creation_lock(self):
        result = self._result_with_valid_15m()
        self.assertTrue(result["hard_locks"]["no_memory_creation"])

    def test_no_live_trading_lock(self):
        result = self._result_with_valid_15m()
        self.assertTrue(result["hard_locks"]["no_live_trading"])

    def test_paper_decisions_created_zero(self):
        result = self._result_with_valid_15m()
        self.assertEqual(result["paper_decisions_created"], 0)

    def test_memories_created_zero(self):
        result = self._result_with_valid_15m()
        self.assertEqual(result["memories_created"], 0)

    def test_memory_windows_created_one(self):
        result = self._result_with_valid_15m()
        self.assertEqual(result["memory_windows_created"], 1)

    def test_window_kind_always_window_15m(self):
        result = self._result_with_valid_15m()
        self.assertEqual(result["window_kind"], E2O_WINDOW_KIND)

    def test_window_status_always_window_closed(self):
        result = self._result_with_valid_15m()
        self.assertEqual(result["window_status"], E2O_WINDOW_STATUS)


if __name__ == "__main__":
    unittest.main()

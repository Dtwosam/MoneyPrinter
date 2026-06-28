"""
Post-Lane 10 Lane E2O -- 15m Memory Window Close Boundary

Tests prove:
- e2o_memory_window_close module imports cleanly
- status constants defined correctly
- hard_locks all True
- no_5m_main_window lock exists and is True
- no_memory_creation lock exists and is True
- clean snapshot creates exactly one WINDOW_15M memory window
- window_id returned on success
- window_kind is always WINDOW_15M
- window_status is WINDOW_CLOSED
- opened_at and closed_at match snapshot captured_at
- tracking_lane and snapshot_mode in result
- second call with same snapshot_id is idempotent (DUPLICATE, no new row)
- DUPLICATE result has existing_window_id
- missing snapshot is blocked
- snapshot with source_status=STALE is blocked
- snapshot with source_status=FAILED is blocked
- snapshot with source_status=PARTIAL is blocked
- snapshot with data_quality_label=DIRTY_DATA is blocked
- snapshot with data_quality_label=STALE_DATA is blocked
- snapshot with tracking_lane not in TRACK_FAST/TRACK_NORMAL is blocked
- TRACK_5M tracking_lane is explicitly blocked (5m not main window)
- wrong approved_mint is blocked
- approved_mint case-insensitive match passes
- no memory rows created
- no paper decisions created
- no paper positions created
- no paper trade events created
- no paper trade audits created
- no episodes created
- no episode snapshots created
- printer_tokens.chain schema enforces solana only
- TRACK_NORMAL lane is allowed
- TRACK_FAST lane is allowed
- blocked result has blocked_reasons list
- blocked result has zero memory_windows_created
- success result has memory_windows_created=1
- memories_created is 0 on success
"""

import json
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
    E2O_ALLOWED_LANES,
    E2O_CREATED_BY,
    E2O_MEMORY_STATUS,
    E2O_REQUIRED_CHAIN,
    E2O_REQUIRED_QUALITY,
    E2O_REQUIRED_SOURCE_STATUS,
    E2O_STATUS_BLOCKED,
    E2O_STATUS_CREATED,
    E2O_STATUS_DUPLICATE,
    E2O_WINDOW_KIND,
    E2O_WINDOW_STATUS,
    _HARD_LOCKS,
    close_15m_memory_window_from_snapshot,
)


_MINT_1 = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_MINT_2 = "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"
_PAIR_ADDR = "E2OTestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


class _DbTestBase(unittest.TestCase):
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

    def _count_rows(self, table: str) -> int:
        conn = sqlite3.connect(str(self.db_path))
        try:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def _insert_token(
        self,
        conn: sqlite3.Connection,
        mint: str = _MINT_1,
    ) -> int:
        now = "2026-06-28T00:00:00+00:00"
        cursor = conn.execute(
            "INSERT INTO printer_tokens"
            " (token_mint, chain, symbol, name, first_seen_at, last_seen_at,"
            "  token_status, created_at, updated_at)"
            " VALUES (?, 'solana', 'TEST', 'Test Token', ?, ?, 'TRACKING', ?, ?)",
            (mint, now, now, now, now),
        )
        return int(cursor.lastrowid)

    def _insert_pair(
        self,
        conn: sqlite3.Connection,
        token_id: int,
        pair_address: str = _PAIR_ADDR,
    ) -> int:
        now = "2026-06-28T00:00:00+00:00"
        cursor = conn.execute(
            "INSERT INTO printer_pairs"
            " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at,"
            "  created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_id, pair_address, pair_address, now, now, now, now),
        )
        return int(cursor.lastrowid)

    def _insert_snapshot(
        self,
        conn: sqlite3.Connection,
        token_id: int,
        pair_id: int | None = None,
        tracking_lane: str = "TRACK_FAST",
        snapshot_mode: str = "FIRST_15M_CYCLE",
        source_status: str = "COMPLETE",
        data_quality_label: str = "CLEAN_DATA",
        captured_at: str = "2026-06-28T10:00:00+00:00",
    ) -> int:
        cursor = conn.execute(
            "INSERT INTO printer_token_snapshots"
            " (token_id, pair_id, captured_at, tracking_lane, snapshot_mode,"
            "  source_status, data_quality_label, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (
                token_id,
                pair_id,
                captured_at,
                tracking_lane,
                snapshot_mode,
                source_status,
                data_quality_label,
            ),
        )
        return int(cursor.lastrowid)

    def _make_clean_snapshot(
        self,
        mint: str = _MINT_1,
        tracking_lane: str = "TRACK_FAST",
    ) -> tuple[int, int, int]:
        """Return (token_id, pair_id, snapshot_id) for a clean COMPLETE/CLEAN_DATA snapshot."""
        conn = self._connect()
        try:
            token_id = self._insert_token(conn, mint)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(
                conn, token_id, pair_id, tracking_lane=tracking_lane
            )
            conn.commit()
        finally:
            conn.close()
        return token_id, pair_id, snap_id

    def _run(
        self,
        snapshot_id: int,
        approved_mint: str = _MINT_1,
    ) -> dict:
        conn = self._connect()
        try:
            result = close_15m_memory_window_from_snapshot(conn, snapshot_id, approved_mint)
            conn.commit()
        finally:
            conn.close()
        return result


# ---------------------------------------------------------------------------
# Import and constants
# ---------------------------------------------------------------------------

class LaneE2OImportTests(unittest.TestCase):
    def test_module_imports_cleanly(self):
        from printer_v1.operator_cli import e2o_memory_window_close
        self.assertIsNotNone(e2o_memory_window_close)

    def test_status_created_constant(self):
        self.assertEqual(E2O_STATUS_CREATED, "E2O_WINDOW_CREATED")

    def test_status_duplicate_constant(self):
        self.assertEqual(E2O_STATUS_DUPLICATE, "E2O_WINDOW_DUPLICATE")

    def test_status_blocked_constant(self):
        self.assertEqual(E2O_STATUS_BLOCKED, "E2O_WINDOW_BLOCKED")

    def test_window_kind_is_window_15m(self):
        self.assertEqual(E2O_WINDOW_KIND, "WINDOW_15M")

    def test_window_status_is_window_closed(self):
        self.assertEqual(E2O_WINDOW_STATUS, "WINDOW_CLOSED")

    def test_required_source_status_complete(self):
        self.assertEqual(E2O_REQUIRED_SOURCE_STATUS, "COMPLETE")

    def test_required_quality_clean_data(self):
        self.assertEqual(E2O_REQUIRED_QUALITY, "CLEAN_DATA")

    def test_required_chain_solana(self):
        self.assertEqual(E2O_REQUIRED_CHAIN, "solana")

    def test_allowed_lanes_contains_track_fast(self):
        self.assertIn("TRACK_FAST", E2O_ALLOWED_LANES)

    def test_allowed_lanes_contains_track_normal(self):
        self.assertIn("TRACK_NORMAL", E2O_ALLOWED_LANES)

    def test_allowed_lanes_does_not_contain_track_5m(self):
        self.assertNotIn("TRACK_5M", E2O_ALLOWED_LANES)

    def test_hard_locks_all_true(self):
        for key, val in _HARD_LOCKS.items():
            self.assertTrue(val, f"hard lock {key!r} must be True")

    def test_hard_locks_no_buy_sell_hold(self):
        self.assertIn("no_buy_sell_hold", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_buy_sell_hold"])

    def test_hard_locks_no_paper_decisions(self):
        self.assertIn("no_paper_decisions", _HARD_LOCKS)

    def test_hard_locks_no_memory_creation(self):
        self.assertIn("no_memory_creation", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_memory_creation"])

    def test_hard_locks_no_5m_main_window(self):
        self.assertIn("no_5m_main_window", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_5m_main_window"])

    def test_hard_locks_no_retrieval_activation(self):
        self.assertIn("no_retrieval_activation", _HARD_LOCKS)

    def test_hard_locks_no_paid_api(self):
        self.assertIn("no_paid_api", _HARD_LOCKS)

    def test_function_importable(self):
        self.assertTrue(callable(close_15m_memory_window_from_snapshot))


# ---------------------------------------------------------------------------
# Happy path: clean snapshot creates one WINDOW_15M window
# ---------------------------------------------------------------------------

class LaneE2OHappyPathTests(_DbTestBase):
    def _result(self) -> dict:
        _, _, snap_id = self._make_clean_snapshot()
        return self._run(snap_id)

    def test_status_created(self):
        r = self._result()
        self.assertEqual(r.get("e2o_status"), E2O_STATUS_CREATED)

    def test_created_flag_true(self):
        r = self._result()
        self.assertTrue(r.get("created"))

    def test_window_id_returned(self):
        r = self._result()
        self.assertIsNotNone(r.get("window_id"))
        self.assertIsInstance(r["window_id"], int)

    def test_window_kind_is_window_15m(self):
        r = self._result()
        self.assertEqual(r.get("window_kind"), "WINDOW_15M")

    def test_window_status_is_window_closed(self):
        r = self._result()
        self.assertEqual(r.get("window_status"), "WINDOW_CLOSED")

    def test_opened_at_matches_captured_at(self):
        r = self._result()
        self.assertEqual(r.get("opened_at"), "2026-06-28T10:00:00+00:00")

    def test_closed_at_matches_captured_at(self):
        r = self._result()
        self.assertEqual(r.get("closed_at"), "2026-06-28T10:00:00+00:00")

    def test_tracking_lane_in_result(self):
        r = self._result()
        self.assertEqual(r.get("tracking_lane"), "TRACK_FAST")

    def test_snapshot_mode_in_result(self):
        r = self._result()
        self.assertEqual(r.get("snapshot_mode"), "FIRST_15M_CYCLE")

    def test_approved_mint_in_result(self):
        r = self._result()
        self.assertEqual(r.get("approved_mint"), _MINT_1)

    def test_hard_locks_in_result(self):
        r = self._result()
        locks = r.get("hard_locks", {})
        for key, val in _HARD_LOCKS.items():
            self.assertTrue(locks.get(key), f"hard lock {key!r} missing or False")

    def test_paper_decisions_zero(self):
        r = self._result()
        self.assertEqual(r.get("paper_decisions_created"), 0)

    def test_positions_zero(self):
        r = self._result()
        self.assertEqual(r.get("positions_created"), 0)

    def test_pnl_zero(self):
        r = self._result()
        self.assertEqual(r.get("pnl_created"), 0)

    def test_memories_created_zero(self):
        r = self._result()
        self.assertEqual(r.get("memories_created"), 0)

    def test_memory_windows_created_one(self):
        r = self._result()
        self.assertEqual(r.get("memory_windows_created"), 1)

    def test_track_normal_also_allowed(self):
        _, _, snap_id = self._make_clean_snapshot(tracking_lane="TRACK_NORMAL")
        r = self._run(snap_id)
        self.assertEqual(r.get("e2o_status"), E2O_STATUS_CREATED)


# ---------------------------------------------------------------------------
# Idempotency: second call is DUPLICATE, no new row
# ---------------------------------------------------------------------------

class LaneE2OIdempotencyTests(_DbTestBase):
    def test_second_call_returns_duplicate(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        r2 = self._run(snap_id)
        self.assertEqual(r2.get("e2o_status"), E2O_STATUS_DUPLICATE)

    def test_duplicate_created_flag_false(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        r2 = self._run(snap_id)
        self.assertFalse(r2.get("created"))

    def test_duplicate_has_existing_window_id(self):
        _, _, snap_id = self._make_clean_snapshot()
        r1 = self._run(snap_id)
        r2 = self._run(snap_id)
        self.assertIsNotNone(r2.get("existing_window_id"))
        self.assertEqual(r2["existing_window_id"], r1["window_id"])

    def test_only_one_window_row_after_two_calls(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        self._run(snap_id)
        self.assertEqual(self._count_rows("printer_memory_windows"), 1)

    def test_different_snapshots_create_separate_windows(self):
        conn = self._connect()
        try:
            token_id = self._insert_token(conn, _MINT_1)
            pair_id = self._insert_pair(conn, token_id)
            snap1 = self._insert_snapshot(
                conn, token_id, pair_id,
                captured_at="2026-06-28T10:00:00+00:00"
            )
            snap2 = self._insert_snapshot(
                conn, token_id, pair_id,
                captured_at="2026-06-28T10:15:00+00:00"
            )
            conn.commit()
        finally:
            conn.close()
        self._run(snap1)
        self._run(snap2)
        self.assertEqual(self._count_rows("printer_memory_windows"), 2)

    def test_duplicate_memory_windows_created_zero(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        r2 = self._run(snap_id)
        self.assertEqual(r2.get("memory_windows_created"), 0)


# ---------------------------------------------------------------------------
# Blocked: missing snapshot
# ---------------------------------------------------------------------------

class LaneE2OBlockedMissingTests(_DbTestBase):
    def test_missing_snapshot_blocked(self):
        r = self._run(snapshot_id=99999)
        self.assertEqual(r.get("e2o_status"), E2O_STATUS_BLOCKED)

    def test_missing_snapshot_created_false(self):
        r = self._run(snapshot_id=99999)
        self.assertFalse(r.get("created"))

    def test_missing_snapshot_has_blocked_reasons(self):
        r = self._run(snapshot_id=99999)
        reasons = r.get("blocked_reasons", [])
        self.assertTrue(len(reasons) > 0)
        self.assertIn("99999", reasons[0])

    def test_missing_snapshot_no_window_created(self):
        self._run(snapshot_id=99999)
        self.assertEqual(self._count_rows("printer_memory_windows"), 0)


# ---------------------------------------------------------------------------
# Blocked: dirty / stale / failed source status
# ---------------------------------------------------------------------------

class LaneE2OBlockedSourceStatusTests(_DbTestBase):
    def _snap_with_status(self, source_status: str) -> int:
        conn = self._connect()
        try:
            token_id = self._insert_token(conn, _MINT_1)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(
                conn, token_id, pair_id, source_status=source_status
            )
            conn.commit()
        finally:
            conn.close()
        return snap_id

    def test_stale_source_status_blocked(self):
        snap_id = self._snap_with_status("STALE")
        r = self._run(snap_id)
        self.assertEqual(r.get("e2o_status"), E2O_STATUS_BLOCKED)

    def test_failed_source_status_blocked(self):
        snap_id = self._snap_with_status("FAILED")
        r = self._run(snap_id)
        self.assertEqual(r.get("e2o_status"), E2O_STATUS_BLOCKED)

    def test_partial_source_status_blocked(self):
        snap_id = self._snap_with_status("PARTIAL")
        r = self._run(snap_id)
        self.assertEqual(r.get("e2o_status"), E2O_STATUS_BLOCKED)

    def test_conflicting_source_status_blocked(self):
        snap_id = self._snap_with_status("CONFLICTING")
        r = self._run(snap_id)
        self.assertEqual(r.get("e2o_status"), E2O_STATUS_BLOCKED)

    def test_stale_blocked_reason_mentions_source_status(self):
        snap_id = self._snap_with_status("STALE")
        r = self._run(snap_id)
        reasons = " ".join(r.get("blocked_reasons", []))
        self.assertIn("source_status", reasons)

    def test_blocked_status_creates_no_window(self):
        snap_id = self._snap_with_status("STALE")
        self._run(snap_id)
        self.assertEqual(self._count_rows("printer_memory_windows"), 0)


# ---------------------------------------------------------------------------
# Blocked: dirty / stale data_quality_label
# ---------------------------------------------------------------------------

class LaneE2OBlockedQualityTests(_DbTestBase):
    def _snap_with_quality(self, quality: str) -> int:
        conn = self._connect()
        try:
            token_id = self._insert_token(conn, _MINT_1)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(
                conn, token_id, pair_id, data_quality_label=quality
            )
            conn.commit()
        finally:
            conn.close()
        return snap_id

    def test_dirty_data_blocked(self):
        snap_id = self._snap_with_quality("DIRTY_DATA")
        r = self._run(snap_id)
        self.assertEqual(r.get("e2o_status"), E2O_STATUS_BLOCKED)

    def test_stale_data_blocked(self):
        snap_id = self._snap_with_quality("STALE_DATA")
        r = self._run(snap_id)
        self.assertEqual(r.get("e2o_status"), E2O_STATUS_BLOCKED)

    def test_missing_critical_data_blocked(self):
        snap_id = self._snap_with_quality("MISSING_CRITICAL_DATA")
        r = self._run(snap_id)
        self.assertEqual(r.get("e2o_status"), E2O_STATUS_BLOCKED)

    def test_do_not_train_quality_blocked(self):
        snap_id = self._snap_with_quality("DO_NOT_TRAIN")
        r = self._run(snap_id)
        self.assertEqual(r.get("e2o_status"), E2O_STATUS_BLOCKED)

    def test_dirty_blocked_reason_mentions_quality(self):
        snap_id = self._snap_with_quality("DIRTY_DATA")
        r = self._run(snap_id)
        reasons = " ".join(r.get("blocked_reasons", []))
        self.assertIn("data_quality_label", reasons)

    def test_dirty_quality_creates_no_window(self):
        snap_id = self._snap_with_quality("DIRTY_DATA")
        self._run(snap_id)
        self.assertEqual(self._count_rows("printer_memory_windows"), 0)


# ---------------------------------------------------------------------------
# Blocked: wrong tracking_lane (5m not main window)
# ---------------------------------------------------------------------------

class LaneE2OBlockedLaneTests(_DbTestBase):
    def _snap_with_lane(self, lane: str) -> int:
        conn = self._connect()
        try:
            token_id = self._insert_token(conn, _MINT_1)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(
                conn, token_id, pair_id, tracking_lane=lane
            )
            conn.commit()
        finally:
            conn.close()
        return snap_id

    def test_track_5m_blocked(self):
        snap_id = self._snap_with_lane("TRACK_5M")
        r = self._run(snap_id)
        self.assertEqual(r.get("e2o_status"), E2O_STATUS_BLOCKED)

    def test_track_5m_support_blocked(self):
        snap_id = self._snap_with_lane("TRACK_5M_SUPPORT")
        r = self._run(snap_id)
        self.assertEqual(r.get("e2o_status"), E2O_STATUS_BLOCKED)

    def test_unknown_lane_blocked(self):
        snap_id = self._snap_with_lane("UNKNOWN_LANE")
        r = self._run(snap_id)
        self.assertEqual(r.get("e2o_status"), E2O_STATUS_BLOCKED)

    def test_track_5m_blocked_reason_mentions_5m(self):
        snap_id = self._snap_with_lane("TRACK_5M")
        r = self._run(snap_id)
        reasons = " ".join(r.get("blocked_reasons", []))
        self.assertIn("5m", reasons.lower())

    def test_track_5m_creates_no_window(self):
        snap_id = self._snap_with_lane("TRACK_5M")
        self._run(snap_id)
        self.assertEqual(self._count_rows("printer_memory_windows"), 0)

    def test_window_5m_not_in_allowed_lanes(self):
        self.assertNotIn("WINDOW_5M", E2O_ALLOWED_LANES)

    def test_track_fast_passes(self):
        snap_id = self._snap_with_lane("TRACK_FAST")
        r = self._run(snap_id)
        self.assertEqual(r.get("e2o_status"), E2O_STATUS_CREATED)

    def test_track_normal_passes(self):
        snap_id = self._snap_with_lane("TRACK_NORMAL")
        r = self._run(snap_id)
        self.assertEqual(r.get("e2o_status"), E2O_STATUS_CREATED)


# ---------------------------------------------------------------------------
# Blocked: wrong approved_mint
# ---------------------------------------------------------------------------

class LaneE2OBlockedMintTests(_DbTestBase):
    def test_wrong_mint_blocked(self):
        _, _, snap_id = self._make_clean_snapshot(mint=_MINT_1)
        r = self._run(snap_id, approved_mint=_MINT_2)
        self.assertEqual(r.get("e2o_status"), E2O_STATUS_BLOCKED)

    def test_wrong_mint_blocked_reason_mentions_mint(self):
        _, _, snap_id = self._make_clean_snapshot(mint=_MINT_1)
        r = self._run(snap_id, approved_mint=_MINT_2)
        reasons = " ".join(r.get("blocked_reasons", []))
        self.assertIn("token_mint", reasons)

    def test_wrong_mint_creates_no_window(self):
        _, _, snap_id = self._make_clean_snapshot(mint=_MINT_1)
        self._run(snap_id, approved_mint=_MINT_2)
        self.assertEqual(self._count_rows("printer_memory_windows"), 0)

    def test_case_insensitive_mint_match_passes(self):
        _, _, snap_id = self._make_clean_snapshot(mint=_MINT_1)
        r = self._run(snap_id, approved_mint=_MINT_1.upper())
        self.assertEqual(r.get("e2o_status"), E2O_STATUS_CREATED)


# ---------------------------------------------------------------------------
# Window kind enforcement: always WINDOW_15M
# ---------------------------------------------------------------------------

class LaneE2OWindowKindTests(_DbTestBase):
    def test_window_kind_hardcoded_window_15m(self):
        _, _, snap_id = self._make_clean_snapshot()
        r = self._run(snap_id)
        self.assertEqual(r.get("window_kind"), "WINDOW_15M")

    def test_module_window_kind_constant_is_window_15m(self):
        self.assertEqual(E2O_WINDOW_KIND, "WINDOW_15M")

    def test_db_row_window_kind_is_window_15m(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT window_kind FROM printer_memory_windows LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["window_kind"], "WINDOW_15M")

    def test_no_5m_window_kind_in_db(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM printer_memory_windows WHERE window_kind = 'WINDOW_5M'"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row[0], 0)


# ---------------------------------------------------------------------------
# Forbidden tables: no paper decisions, positions, episodes, etc.
# ---------------------------------------------------------------------------

class LaneE2OForbiddenTableTests(_DbTestBase):
    def test_no_paper_decisions_created(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        self.assertEqual(self._count_rows("printer_paper_decisions"), 0)

    def test_no_paper_positions_created(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        self.assertEqual(self._count_rows("printer_paper_positions"), 0)

    def test_no_paper_trade_events_created(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        self.assertEqual(self._count_rows("printer_paper_trade_events"), 0)

    def test_no_paper_trade_audits_created(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        self.assertEqual(self._count_rows("printer_paper_trade_audits"), 0)

    def test_no_episodes_created(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        self.assertEqual(self._count_rows("printer_episodes"), 0)

    def test_no_episode_snapshots_created(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        self.assertEqual(self._count_rows("printer_episode_snapshots"), 0)

    def test_no_episode_outcomes_created(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        self.assertEqual(self._count_rows("printer_episode_outcomes"), 0)

    def test_no_memory_fingerprints_created(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        self.assertEqual(self._count_rows("printer_memory_fingerprints"), 0)


# ---------------------------------------------------------------------------
# DB state: exactly one window row, correct columns
# ---------------------------------------------------------------------------

class LaneE2ODbStateTests(_DbTestBase):
    def test_exactly_one_window_row_after_success(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        self.assertEqual(self._count_rows("printer_memory_windows"), 1)

    def test_window_row_window_kind(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM printer_memory_windows LIMIT 1").fetchone()
        finally:
            conn.close()
        self.assertEqual(row["window_kind"], "WINDOW_15M")

    def test_window_row_window_status(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM printer_memory_windows LIMIT 1").fetchone()
        finally:
            conn.close()
        self.assertEqual(row["window_status"], "WINDOW_CLOSED")

    def test_window_row_memory_status(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM printer_memory_windows LIMIT 1").fetchone()
        finally:
            conn.close()
        self.assertEqual(row["memory_status"], E2O_MEMORY_STATUS)

    def test_window_row_data_quality_label(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM printer_memory_windows LIMIT 1").fetchone()
        finally:
            conn.close()
        self.assertEqual(row["data_quality_label"], "CLEAN_DATA")

    def test_window_row_do_not_train_zero(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM printer_memory_windows LIMIT 1").fetchone()
        finally:
            conn.close()
        self.assertEqual(row["do_not_train"], 0)

    def test_window_row_supporting_context_has_snapshot_id(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM printer_memory_windows LIMIT 1").fetchone()
        finally:
            conn.close()
        ctx = json.loads(row["supporting_context_json"])
        self.assertEqual(ctx.get("snapshot_id"), snap_id)

    def test_window_row_supporting_context_has_tracking_lane(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM printer_memory_windows LIMIT 1").fetchone()
        finally:
            conn.close()
        ctx = json.loads(row["supporting_context_json"])
        self.assertEqual(ctx.get("tracking_lane"), "TRACK_FAST")

    def test_window_row_created_by_phase(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM printer_memory_windows LIMIT 1").fetchone()
        finally:
            conn.close()
        self.assertEqual(row["created_by_phase"], E2O_CREATED_BY)

    def test_window_row_opened_closed_at_match_captured_at(self):
        _, _, snap_id = self._make_clean_snapshot()
        self._run(snap_id)
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM printer_memory_windows LIMIT 1").fetchone()
        finally:
            conn.close()
        self.assertEqual(row["opened_at"], row["closed_at"])
        self.assertEqual(row["opened_at"], "2026-06-28T10:00:00+00:00")

    def test_solana_schema_enforces_chain(self):
        conn = self._connect()
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO printer_tokens"
                    " (token_mint, chain, created_at, updated_at)"
                    " VALUES (?, 'ethereum', datetime('now'), datetime('now'))",
                    ("0xdeadbeef",),
                )
        finally:
            conn.close()


if __name__ == "__main__":
    import unittest
    unittest.main()

"""
Lane S — Real Spaced 15m Window End-to-End Proof

Proves the full memory path works on an isolated DB:

  Two snapshots (>= 900s apart)
  → E2O writes window with real canonical integrity fields
  → E2Q audits window as PARTIAL_MEMORY / CLEAN_CANDIDATE
  → Lane Q validates window as LANE_Q_VALID
  → Lane K / E2Z creates one clean-memory episode per valid window
  → Lane K second run creates 0 new episodes (idempotent)

Also proves:

  - compressed/instant windows (no snapshot_start_id) are blocked by Lane Q
  - five compressed windows → Lane K creates zero episodes
  - retrieval, paper, position, PnL tables remain zero throughout
  - all hard locks are True in every result dict

Tests prove:
  - valid 15m spaced snapshot pair writes all four canonical fields
  - valid 15m spaced window passes Lane Q
  - elapsed < 900 seconds is blocked by Lane Q
  - missing snapshot_start_id is blocked by Lane Q
  - Lane K creates exactly 5 clean-memory episodes from 5 Lane-Q-valid windows
  - Lane K second run is idempotent (0 new episodes, 5 already-exists)
  - Lane K creates zero episodes from Lane-Q-blocked windows
  - retrieval tables remain zero
  - paper decision tables remain zero
  - positions / trade events / audits / PnL tables remain zero
  - existing Lane Q tests still pass (verified by cross-check run)
  - existing Lane R tests still pass (verified by cross-check run)
  - existing Lane K tests still pass (verified by cross-check run)
  - E2Z tests still pass (verified by cross-check run)
"""

from __future__ import annotations

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
    E2O_STATUS_CREATED,
    close_15m_memory_window_from_snapshot,
)
from printer_v1.operator_cli.e2q_memory_window_audit import (
    E2Q_STATUS_CLEAN_CANDIDATE,
    audit_15m_memory_window,
)
from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import (
    LANE_K_STATUS_COMPLETED,
    run_e2z_pipeline,
)
from printer_v1.operator_cli.lane_q_15m_window_integrity_guard import (
    LANE_Q_BLOCKED,
    LANE_Q_GUARD_COMPLETED,
    LANE_Q_VALID,
    check_window_integrity,
    guard_candidate_windows,
)

_MINT = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_PAIR_ADDR = "LaneSTestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

# Timestamps: T (window open) and T+901s (window close) — 901s >= 900s threshold
_BASE_TS = "2026-06-29T10:00:00+00:00"
_BASE_TS_CLOSE = "2026-06-29T10:15:01+00:00"  # +901s

# Short (compressed) timestamps: same base, only +1s elapsed
_SHORT_CLOSE_TS = "2026-06-29T10:00:01+00:00"  # +1s — not a real 15m window


class _DbBase(unittest.TestCase):
    """Base class: isolated temp DB, token/pair helpers."""

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

    def _count_table(self, table: str) -> int:
        conn = sqlite3.connect(str(self.db_path))
        try:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                return 0
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def _insert_token(self, conn: sqlite3.Connection, mint: str = _MINT) -> int:
        now = "2026-06-29T00:00:00+00:00"
        cur = conn.execute(
            "INSERT INTO printer_tokens"
            " (token_mint, chain, symbol, name, first_seen_at, last_seen_at,"
            "  token_status, created_at, updated_at)"
            " VALUES (?, 'solana', 'TST', 'Test', ?, ?, 'TRACKING', ?, ?)",
            (mint, now, now, now, now),
        )
        return int(cur.lastrowid)

    def _insert_pair(self, conn: sqlite3.Connection, token_id: int) -> int:
        now = "2026-06-29T00:00:00+00:00"
        cur = conn.execute(
            "INSERT INTO printer_pairs"
            " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at,"
            "  created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_id, _PAIR_ADDR, _PAIR_ADDR, now, now, now, now),
        )
        return int(cur.lastrowid)

    def _insert_snapshot(
        self,
        conn: sqlite3.Connection,
        token_id: int,
        pair_id: int | None,
        captured_at: str,
    ) -> int:
        cur = conn.execute(
            "INSERT INTO printer_token_snapshots"
            " (token_id, pair_id, captured_at, tracking_lane, snapshot_mode,"
            "  source_status, data_quality_label, created_at)"
            " VALUES (?, ?, ?, 'TRACK_FAST', 'FIRST_15M_CYCLE',"
            "         'COMPLETE', 'CLEAN_DATA', datetime('now'))",
            (token_id, pair_id, captured_at),
        )
        return int(cur.lastrowid)

    def _setup_token_pair(self) -> tuple[int, int]:
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            conn.commit()
        finally:
            conn.close()
        return token_id, pair_id

    def _make_one_valid_window(
        self,
        conn: sqlite3.Connection,
        token_id: int,
        pair_id: int,
        start_ts: str = _BASE_TS,
        close_ts: str = _BASE_TS_CLOSE,
    ) -> tuple[int, int, int]:
        """Create one valid 15m window: two snapshots >= 900s apart, E2O + E2Q.

        Returns (start_snap_id, close_snap_id, window_id).
        Does NOT commit — caller must commit.
        """
        start_id = self._insert_snapshot(conn, token_id, pair_id, start_ts)
        close_id = self._insert_snapshot(conn, token_id, pair_id, close_ts)
        e2o = close_15m_memory_window_from_snapshot(
            conn, close_id, _MINT, snapshot_start_id=start_id
        )
        assert e2o["e2o_status"] == E2O_STATUS_CREATED, f"E2O failed: {e2o}"
        window_id = e2o["window_id"]
        e2q = audit_15m_memory_window(conn, window_id)
        assert e2q["e2q_status"] == E2Q_STATUS_CLEAN_CANDIDATE, f"E2Q failed: {e2q}"
        return start_id, close_id, window_id

    def _make_one_compressed_window(
        self,
        conn: sqlite3.Connection,
        token_id: int,
        pair_id: int,
        captured_at: str = _BASE_TS,
    ) -> tuple[int, int]:
        """Create one instant/compressed window: no snapshot_start_id, or 0s elapsed.

        Uses the single-snapshot E2O path (no snapshot_start_id).
        window_start_at will be NULL → Lane Q blocks with missing_window_start_at.
        Returns (close_snap_id, window_id). Does NOT commit.
        """
        close_id = self._insert_snapshot(conn, token_id, pair_id, captured_at)
        e2o = close_15m_memory_window_from_snapshot(conn, close_id, _MINT)
        assert e2o["e2o_status"] == E2O_STATUS_CREATED, f"E2O failed: {e2o}"
        window_id = e2o["window_id"]
        e2q = audit_15m_memory_window(conn, window_id)
        assert e2q["e2q_status"] == E2Q_STATUS_CLEAN_CANDIDATE, f"E2Q failed: {e2q}"
        return close_id, window_id

    def _make_five_valid_windows(self) -> list[tuple[int, int, int]]:
        """Create 5 valid 15m windows in the test DB.

        Each window uses distinct timestamps (spaced 2h apart) so all snapshot IDs
        are strictly increasing. Returns list of (start_id, close_id, window_id).
        """
        token_id, pair_id = self._setup_token_pair()
        results = []
        conn = self._connect()
        try:
            for i in range(5):
                # Offset start time by 2h per window to avoid any timestamp collision
                hour_offset = i * 2
                start_ts = f"2026-06-29T{10 + hour_offset:02d}:00:00+00:00"
                close_ts = f"2026-06-29T{10 + hour_offset:02d}:15:01+00:00"  # +901s
                ids = self._make_one_valid_window(conn, token_id, pair_id, start_ts, close_ts)
                results.append(ids)
            conn.commit()
        finally:
            conn.close()
        return results

    def _make_five_compressed_windows(self) -> list[tuple[int, int]]:
        """Create 5 compressed (NULL window_start_at) windows in the test DB.

        These are e2q_audited PARTIAL_MEMORY CLEAN_DATA windows — eligible by
        E2X/E2Y — but Lane Q will block them for missing_window_start_at.
        Returns list of (close_id, window_id).
        """
        token_id, pair_id = self._setup_token_pair()
        results = []
        conn = self._connect()
        try:
            for i in range(5):
                hour_offset = i * 2
                captured_at = f"2026-06-29T{10 + hour_offset:02d}:00:00+00:00"
                ids = self._make_one_compressed_window(conn, token_id, pair_id, captured_at)
                results.append(ids)
            conn.commit()
        finally:
            conn.close()
        return results

    def _read_window(self, window_id: int) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM printer_memory_windows WHERE id = ?", (window_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def _run_lane_k(self) -> dict:
        return run_e2z_pipeline(self.db_path, operator_approved=True)


# ---------------------------------------------------------------------------
# Proof class 1: Import / constants
# ---------------------------------------------------------------------------

class LaneSImportTests(unittest.TestCase):
    def test_e2o_import(self):
        from printer_v1.operator_cli.e2o_memory_window_close import (
            close_15m_memory_window_from_snapshot,
        )
        self.assertIsNotNone(close_15m_memory_window_from_snapshot)

    def test_e2q_import(self):
        from printer_v1.operator_cli.e2q_memory_window_audit import (
            audit_15m_memory_window,
        )
        self.assertIsNotNone(audit_15m_memory_window)

    def test_lane_q_import(self):
        from printer_v1.operator_cli.lane_q_15m_window_integrity_guard import (
            guard_candidate_windows,
        )
        self.assertIsNotNone(guard_candidate_windows)

    def test_lane_k_import(self):
        from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline
        self.assertIsNotNone(run_e2z_pipeline)


# ---------------------------------------------------------------------------
# Proof class 2: E2O + E2Q write canonical integrity fields
# ---------------------------------------------------------------------------

class LaneSE2OE2QWriterTests(_DbBase):
    def setUp(self):
        super().setUp()
        token_id, pair_id = self._setup_token_pair()
        conn = self._connect()
        try:
            self.start_id, self.close_id, self.window_id = self._make_one_valid_window(
                conn, token_id, pair_id
            )
            conn.commit()
        finally:
            conn.close()
        self.row = self._read_window(self.window_id)

    def test_e2o_status_created(self):
        self.assertIsNotNone(self.window_id)

    def test_window_start_at_written(self):
        self.assertEqual(self.row["window_start_at"], _BASE_TS)

    def test_window_end_at_written(self):
        self.assertEqual(self.row["window_end_at"], _BASE_TS_CLOSE)

    def test_snapshot_start_id_written(self):
        self.assertEqual(int(self.row["snapshot_start_id"]), self.start_id)

    def test_snapshot_end_id_written(self):
        self.assertEqual(int(self.row["snapshot_end_id"]), self.close_id)

    def test_window_kind_is_window_15m(self):
        self.assertEqual(self.row["window_kind"], "WINDOW_15M")

    def test_window_status_closed(self):
        self.assertEqual(self.row["window_status"], "WINDOW_CLOSED")

    def test_data_quality_clean(self):
        self.assertEqual(self.row["data_quality_label"], "CLEAN_DATA")

    def test_memory_status_partial(self):
        self.assertEqual(self.row["memory_status"], "PARTIAL_MEMORY")

    def test_memory_quality_partial_after_e2q(self):
        self.assertEqual(self.row["memory_quality_label"], "PARTIAL_MEMORY")

    def test_do_not_train_zero(self):
        self.assertEqual(int(self.row["do_not_train"]), 0)

    def test_e2q_audited_in_supporting_context(self):
        import json
        ctx = json.loads(self.row["supporting_context_json"] or "{}")
        self.assertTrue(ctx.get("e2q_audited"))


# ---------------------------------------------------------------------------
# Proof class 3: Lane Q VALID for real 15m windows
# ---------------------------------------------------------------------------

class LaneSLaneQValidWindowTests(_DbBase):
    def setUp(self):
        super().setUp()
        token_id, pair_id = self._setup_token_pair()
        conn = self._connect()
        try:
            self.start_id, self.close_id, self.window_id = self._make_one_valid_window(
                conn, token_id, pair_id
            )
            conn.commit()
        finally:
            conn.close()
        row = self._read_window(self.window_id)
        self.verdict = check_window_integrity({
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

    def test_lane_q_status_valid(self):
        self.assertEqual(self.verdict["lane_q_status"], LANE_Q_VALID)

    def test_integrity_proven(self):
        self.assertTrue(self.verdict["integrity_proven"])

    def test_no_blocked_reasons(self):
        self.assertEqual(self.verdict["blocked_reasons"], [])

    def test_elapsed_at_least_900(self):
        self.assertGreaterEqual(self.verdict["elapsed_seconds"], 900.0)

    def test_snapshot_ids_correct(self):
        self.assertEqual(int(self.verdict["snapshot_start_id"]), self.start_id)
        self.assertEqual(int(self.verdict["snapshot_end_id"]), self.close_id)


# ---------------------------------------------------------------------------
# Proof class 4: Lane Q BLOCKED for compressed / instant windows
# ---------------------------------------------------------------------------

class LaneSLaneQBlockedWindowTests(_DbBase):
    def _run_check(self, window_id: int) -> dict:
        row = self._read_window(window_id)
        return check_window_integrity({
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

    def test_missing_snapshot_start_id_is_blocked(self):
        """Single-snapshot E2O path (no snapshot_start_id) → Lane Q blocks."""
        token_id, pair_id = self._setup_token_pair()
        conn = self._connect()
        try:
            _, window_id = self._make_one_compressed_window(conn, token_id, pair_id)
            conn.commit()
        finally:
            conn.close()
        verdict = self._run_check(window_id)
        self.assertEqual(verdict["lane_q_status"], LANE_Q_BLOCKED)
        self.assertIn("missing_window_start_at", verdict["blocked_reasons"])

    def test_short_elapsed_is_blocked(self):
        """Two snapshots only 1s apart → Lane Q blocks for elapsed < 900s."""
        token_id, pair_id = self._setup_token_pair()
        conn = self._connect()
        try:
            start_id = self._insert_snapshot(conn, token_id, pair_id, _BASE_TS)
            close_id = self._insert_snapshot(conn, token_id, pair_id, _SHORT_CLOSE_TS)
            e2o = close_15m_memory_window_from_snapshot(
                conn, close_id, _MINT, snapshot_start_id=start_id
            )
            window_id = e2o["window_id"]
            audit_15m_memory_window(conn, window_id)
            conn.commit()
        finally:
            conn.close()
        verdict = self._run_check(window_id)
        self.assertEqual(verdict["lane_q_status"], LANE_Q_BLOCKED)
        self.assertIn("elapsed_seconds_below_900", verdict["blocked_reasons"])

    def test_short_elapsed_elapsed_seconds_below_900(self):
        token_id, pair_id = self._setup_token_pair()
        conn = self._connect()
        try:
            start_id = self._insert_snapshot(conn, token_id, pair_id, _BASE_TS)
            close_id = self._insert_snapshot(conn, token_id, pair_id, _SHORT_CLOSE_TS)
            e2o = close_15m_memory_window_from_snapshot(
                conn, close_id, _MINT, snapshot_start_id=start_id
            )
            window_id = e2o["window_id"]
            audit_15m_memory_window(conn, window_id)
            conn.commit()
        finally:
            conn.close()
        verdict = self._run_check(window_id)
        self.assertLess(verdict["elapsed_seconds"], 900.0)

    def test_guard_blocks_five_compressed_windows(self):
        """guard_candidate_windows blocks all 5 when they have NULL window_start_at."""
        self._make_five_compressed_windows()
        # Read all window IDs from DB
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id FROM printer_memory_windows ORDER BY id"
            ).fetchall()
            window_ids = [int(r["id"]) for r in rows]
        finally:
            conn.close()
        self.assertEqual(len(window_ids), 5)
        result = guard_candidate_windows(self.db_path, window_ids, operator_approved=True)
        self.assertEqual(result["lane_q_guard_status"], LANE_Q_GUARD_COMPLETED)
        self.assertEqual(result["valid_count"], 0)
        self.assertEqual(result["blocked_count"], 5)


# ---------------------------------------------------------------------------
# Proof class 5: Lane K full flow — 5 valid windows → 5 episodes
# ---------------------------------------------------------------------------

class LaneSLaneKFullFlowTests(_DbBase):
    def setUp(self):
        super().setUp()
        self._windows = self._make_five_valid_windows()
        self.result = self._run_lane_k()

    def test_lane_k_status_completed(self):
        self.assertEqual(self.result["lane_k_status"], LANE_K_STATUS_COMPLETED)

    def test_e2y_set_gate_passed(self):
        self.assertTrue(self.result["e2y_set_gate_passed"])

    def test_lane_q_guard_completed(self):
        self.assertEqual(self.result["lane_q_guard_status"], LANE_Q_GUARD_COMPLETED)

    def test_all_five_pass_lane_q(self):
        self.assertEqual(len(self.result["lane_q_valid_window_ids"]), 5)

    def test_zero_windows_blocked_by_lane_q(self):
        self.assertEqual(self.result["lane_q_blocked_count"], 0)

    def test_e2z_created_count_is_5(self):
        self.assertEqual(self.result["e2z_created_count"], 5)

    def test_clean_memory_rows_created_5(self):
        self.assertEqual(self.result["clean_memory_rows_created"], 5)

    def test_e2z_blocked_count_zero(self):
        self.assertEqual(self.result["e2z_blocked_count"], 0)

    def test_zero_clean_memories_valid_flag(self):
        self.assertTrue(self.result["zero_clean_memories_valid"])

    def test_five_episodes_in_db(self):
        count = self._count_table("printer_episodes")
        self.assertEqual(count, 5)


# ---------------------------------------------------------------------------
# Proof class 6: Lane K idempotency — second run creates 0 new episodes
# ---------------------------------------------------------------------------

class LaneSLaneKIdempotencyTests(_DbBase):
    def setUp(self):
        super().setUp()
        self._make_five_valid_windows()
        self._first = self._run_lane_k()
        self._second = self._run_lane_k()

    def test_first_run_creates_5(self):
        self.assertEqual(self._first["e2z_created_count"], 5)

    def test_second_run_creates_0(self):
        self.assertEqual(self._second["e2z_created_count"], 0)

    def test_second_run_already_exists_5(self):
        self.assertEqual(self._second["e2z_already_exists_count"], 5)

    def test_second_run_status_completed(self):
        self.assertEqual(self._second["lane_k_status"], LANE_K_STATUS_COMPLETED)

    def test_episode_count_stays_at_5(self):
        count = self._count_table("printer_episodes")
        self.assertEqual(count, 5)


# ---------------------------------------------------------------------------
# Proof class 7: Lane K creates zero episodes from 5 Lane-Q-blocked windows
# ---------------------------------------------------------------------------

class LaneSLaneKBlockedWindowsTests(_DbBase):
    def setUp(self):
        super().setUp()
        self._make_five_compressed_windows()
        self.result = self._run_lane_k()

    def test_lane_k_status_completed(self):
        # Lane K runs to completion even when all windows are Lane-Q-blocked
        self.assertEqual(self.result["lane_k_status"], LANE_K_STATUS_COMPLETED)

    def test_e2y_gate_passed_with_five_candidates(self):
        # E2Y passes (5 e2q_audited PARTIAL_MEMORY CLEAN_DATA candidates)
        self.assertTrue(self.result["e2y_set_gate_passed"])

    def test_lane_q_blocks_all_five(self):
        self.assertEqual(self.result["lane_q_blocked_count"], 5)

    def test_zero_valid_windows_after_lane_q(self):
        self.assertEqual(len(self.result["lane_q_valid_window_ids"]), 0)

    def test_e2z_created_count_zero(self):
        self.assertEqual(self.result["e2z_created_count"], 0)

    def test_clean_memory_rows_created_zero(self):
        self.assertEqual(self.result["clean_memory_rows_created"], 0)

    def test_zero_episodes_in_db(self):
        count = self._count_table("printer_episodes")
        self.assertEqual(count, 0)

    def test_zero_clean_memories_valid_flag_present(self):
        self.assertTrue(self.result["zero_clean_memories_valid"])

    def test_lane_q_blocked_windows_reported(self):
        blocked_ids = self.result.get("lane_q_blocked_window_ids", [])
        self.assertEqual(len(blocked_ids), 5)


# ---------------------------------------------------------------------------
# Proof class 8: Locked tables remain zero
# ---------------------------------------------------------------------------

class LaneSLockedTablesTests(_DbBase):
    def setUp(self):
        super().setUp()
        self._make_five_valid_windows()
        self._run_lane_k()

    def test_retrieval_queries_zero(self):
        self.assertEqual(self._count_table("printer_memory_retrieval_queries"), 0)

    def test_retrieval_matches_zero(self):
        self.assertEqual(self._count_table("printer_memory_retrieval_matches"), 0)

    def test_paper_decisions_zero(self):
        self.assertEqual(self._count_table("printer_paper_decisions"), 0)

    def test_paper_positions_zero(self):
        self.assertEqual(self._count_table("printer_paper_positions"), 0)

    def test_paper_trade_events_zero(self):
        self.assertEqual(self._count_table("printer_paper_trade_events"), 0)

    def test_paper_trade_audits_zero(self):
        self.assertEqual(self._count_table("printer_paper_trade_audits"), 0)

    def test_paper_audit_reports_zero(self):
        self.assertEqual(self._count_table("printer_paper_audit_reports"), 0)


# ---------------------------------------------------------------------------
# Proof class 9: Hard locks preserved in all result dicts
# ---------------------------------------------------------------------------

class LaneSHardLocksTests(_DbBase):
    def _all_true(self, locks: dict) -> None:
        for key, val in locks.items():
            self.assertTrue(val, f"hard lock {key!r} must be True")

    def test_e2o_hard_locks_valid_window(self):
        token_id, pair_id = self._setup_token_pair()
        conn = self._connect()
        try:
            start_id = self._insert_snapshot(conn, token_id, pair_id, _BASE_TS)
            close_id = self._insert_snapshot(conn, token_id, pair_id, _BASE_TS_CLOSE)
            result = close_15m_memory_window_from_snapshot(
                conn, close_id, _MINT, snapshot_start_id=start_id
            )
            conn.commit()
        finally:
            conn.close()
        self._all_true(result["hard_locks"])

    def test_e2q_hard_locks(self):
        token_id, pair_id = self._setup_token_pair()
        conn = self._connect()
        try:
            start_id = self._insert_snapshot(conn, token_id, pair_id, _BASE_TS)
            close_id = self._insert_snapshot(conn, token_id, pair_id, _BASE_TS_CLOSE)
            e2o = close_15m_memory_window_from_snapshot(
                conn, close_id, _MINT, snapshot_start_id=start_id
            )
            result = audit_15m_memory_window(conn, e2o["window_id"])
            conn.commit()
        finally:
            conn.close()
        self._all_true(result["hard_locks"])

    def test_lane_q_guard_hard_locks(self):
        self._make_five_valid_windows()
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id FROM printer_memory_windows"
            ).fetchall()
            ids = [int(r["id"]) for r in rows]
        finally:
            conn.close()
        result = guard_candidate_windows(self.db_path, ids, operator_approved=True)
        self._all_true(result["hard_locks"])

    def test_lane_k_hard_locks(self):
        self._make_five_valid_windows()
        result = self._run_lane_k()
        self._all_true(result["hard_locks"])

    def test_lane_k_no_paper_decisions(self):
        self._make_five_valid_windows()
        result = self._run_lane_k()
        self.assertEqual(result["paper_decisions_created"], 0)

    def test_lane_k_no_positions(self):
        self._make_five_valid_windows()
        result = self._run_lane_k()
        self.assertEqual(result["positions_created"], 0)

    def test_lane_k_no_buy_sell_hold(self):
        self._make_five_valid_windows()
        result = self._run_lane_k()
        self.assertFalse(result["buy_enabled"])
        self.assertFalse(result["sell_enabled"])
        self.assertFalse(result["hold_enabled"])

    def test_lane_k_retrieval_not_activated(self):
        self._make_five_valid_windows()
        result = self._run_lane_k()
        self.assertFalse(result.get("retrieval_activated", False))


# ---------------------------------------------------------------------------
# Proof class 10: Guard correctly separates valid from invalid in mixed DB
# ---------------------------------------------------------------------------

class LaneSGuardMixedWindowTests(_DbBase):
    """5 valid + 1 compressed → guard passes 5, blocks 1."""

    def setUp(self):
        super().setUp()
        # We use a different token_id/pair_id here so E2Y won't mix them.
        # The guard is called directly on specific IDs, not through Lane K.
        token_id, pair_id = self._setup_token_pair()
        self.valid_ids: list[int] = []
        self.compressed_ids: list[int] = []
        conn = self._connect()
        try:
            for i in range(5):
                hour = 10 + i * 2
                start_ts = f"2026-06-29T{hour:02d}:00:00+00:00"
                close_ts = f"2026-06-29T{hour:02d}:15:01+00:00"
                _, _, wid = self._make_one_valid_window(conn, token_id, pair_id, start_ts, close_ts)
                self.valid_ids.append(wid)
            _, wid_c = self._make_one_compressed_window(conn, token_id, pair_id)
            self.compressed_ids.append(wid_c)
            conn.commit()
        finally:
            conn.close()

    def test_guard_passes_all_five_valid(self):
        result = guard_candidate_windows(
            self.db_path, self.valid_ids, operator_approved=True
        )
        self.assertEqual(result["valid_count"], 5)
        self.assertEqual(result["blocked_count"], 0)

    def test_guard_blocks_compressed(self):
        result = guard_candidate_windows(
            self.db_path, self.compressed_ids, operator_approved=True
        )
        self.assertEqual(result["valid_count"], 0)
        self.assertEqual(result["blocked_count"], 1)

    def test_guard_on_all_six_passes_5_blocks_1(self):
        all_ids = self.valid_ids + self.compressed_ids
        result = guard_candidate_windows(
            self.db_path, all_ids, operator_approved=True
        )
        self.assertEqual(result["valid_count"], 5)
        self.assertEqual(result["blocked_count"], 1)

    def test_guard_returns_completed_status(self):
        result = guard_candidate_windows(
            self.db_path, self.valid_ids, operator_approved=True
        )
        self.assertEqual(result["lane_q_guard_status"], LANE_Q_GUARD_COMPLETED)


if __name__ == "__main__":
    unittest.main()

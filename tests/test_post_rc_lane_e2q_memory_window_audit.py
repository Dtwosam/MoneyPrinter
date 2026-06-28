"""
Post-Lane 10 Lane E2Q -- 15m Memory Window Audit / Classification Boundary

Tests prove:
- e2q_memory_window_audit module imports cleanly
- status constants defined correctly
- hard_locks all True (including no_5m_main_window, no_memory_creation, no_scoring_ranking)
- audit_15m_memory_window is callable
- clean WINDOW_15M closed window → E2Q_AUDIT_CLEAN_CANDIDATE
- classified flag True on success
- window_id in result on success
- snapshot_id in result on success
- memory_quality_label PARTIAL_MEMORY on clean candidate
- rejection_reasons empty on clean candidate
- clean run writes memory_quality_label to printer_memory_windows row
- clean run writes do_not_train=0 to window row
- clean run marks supporting_context_json with e2q_audited=True
- duplicate audit is idempotent (same status, no extra rows)
- missing window → E2Q_AUDIT_BLOCKED
- window_kind != WINDOW_15M → E2Q_AUDIT_BLOCKED
- WINDOW_5M_MICRO_EVENT → E2Q_AUDIT_BLOCKED (5m not valid main outcome window)
- open window (WINDOW_OPEN) → E2Q_AUDIT_BLOCKED
- dirty window data_quality_label → E2Q_AUDIT_DIRTY
- stale window data_quality_label → E2Q_AUDIT_DIRTY
- missing supporting_context_json → E2Q_AUDIT_BLOCKED
- supporting_context_json without snapshot_id → E2Q_AUDIT_BLOCKED
- missing snapshot → E2Q_AUDIT_BLOCKED
- snapshot source_status=FAILED → E2Q_AUDIT_DIRTY
- snapshot source_status=STALE → E2Q_AUDIT_DIRTY
- snapshot data_quality_label=DIRTY_DATA → E2Q_AUDIT_DIRTY
- snapshot data_quality_label=STALE_DATA → E2Q_AUDIT_DIRTY
- token_id mismatch → E2Q_AUDIT_BLOCKED
- pair_id mismatch → E2Q_AUDIT_BLOCKED
- pair_id None on window with non-null pair on snapshot → passes (no mismatch)
- window data_quality_label=ACCEPTABLE_PARTIAL_DATA → E2Q_AUDIT_ONLY
- dirty result writes DIRTY_MEMORY to window row
- dirty result sets do_not_train=1
- audit_only result writes AUDIT_ONLY to window row
- audit_only result sets do_not_train=1
- no printer_memories rows created
- no printer_episodes rows created
- no printer_paper_decisions rows created
- no printer_paper_positions rows created
- no printer_paper_trade_events rows created
- no printer_paper_trade_audits rows created
- blocked result has classified=False
- blocked result has no write-back to window
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
from printer_v1.operator_cli.e2q_memory_window_audit import (
    E2Q_REQUIRED_QUALITY,
    E2Q_REQUIRED_SOURCE_STATUS,
    E2Q_REQUIRED_WINDOW_KIND,
    E2Q_REQUIRED_WINDOW_STATUS,
    E2Q_STATUS_AUDIT_ONLY,
    E2Q_STATUS_BLOCKED,
    E2Q_STATUS_CLEAN_CANDIDATE,
    E2Q_STATUS_DIRTY,
    _HARD_LOCKS,
    audit_15m_memory_window,
)


_MINT_1 = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_MINT_2 = "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"
_PAIR_ADDR = "E2QTestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_CAPTURED_AT = "2026-06-28T10:00:00+00:00"


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

    def _insert_token(self, conn: sqlite3.Connection, mint: str = _MINT_1) -> int:
        now = _CAPTURED_AT
        cur = conn.execute(
            "INSERT INTO printer_tokens"
            " (token_mint, chain, symbol, name, first_seen_at, last_seen_at,"
            "  token_status, created_at, updated_at)"
            " VALUES (?, 'solana', 'TEST', 'Test Token', ?, ?, 'TRACKING', ?, ?)",
            (mint, now, now, now, now),
        )
        return int(cur.lastrowid)

    def _insert_pair(self, conn: sqlite3.Connection, token_id: int,
                     pair_address: str = _PAIR_ADDR) -> int:
        now = _CAPTURED_AT
        cur = conn.execute(
            "INSERT INTO printer_pairs"
            " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at,"
            "  created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_id, pair_address, pair_address, now, now, now, now),
        )
        return int(cur.lastrowid)

    def _insert_snapshot(
        self,
        conn: sqlite3.Connection,
        token_id: int,
        pair_id: int | None = None,
        source_status: str = "COMPLETE",
        data_quality_label: str = "CLEAN_DATA",
        tracking_lane: str = "TRACK_FAST",
        snapshot_mode: str = "FIRST_15M_CYCLE",
    ) -> int:
        cur = conn.execute(
            "INSERT INTO printer_token_snapshots"
            " (token_id, pair_id, captured_at, tracking_lane, snapshot_mode,"
            "  source_status, data_quality_label, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (token_id, pair_id, _CAPTURED_AT, tracking_lane,
             snapshot_mode, source_status, data_quality_label),
        )
        return int(cur.lastrowid)

    def _insert_window(
        self,
        conn: sqlite3.Connection,
        token_id: int,
        pair_id: int | None,
        snapshot_id: int,
        window_kind: str = "WINDOW_15M",
        window_status: str = "WINDOW_CLOSED",
        data_quality_label: str = "CLEAN_DATA",
        memory_status: str = "PARTIAL_MEMORY",
        supporting_context: dict | None = None,
    ) -> int:
        if supporting_context is None:
            supporting_context = {
                "snapshot_id": snapshot_id,
                "tracking_lane": "TRACK_FAST",
                "snapshot_mode": "FIRST_15M_CYCLE",
                "created_by": "lane_e2o",
            }
        now = _CAPTURED_AT
        cur = conn.execute(
            """
            INSERT INTO printer_memory_windows (
                token_id, pair_id, window_kind, opened_at, closed_at,
                memory_status, data_quality_label, do_not_train, window_status,
                supporting_context_json, created_by_phase, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 'lane_e2o', ?, ?)
            """,
            (
                token_id, pair_id, window_kind, now, now,
                memory_status, data_quality_label, window_status,
                json.dumps(supporting_context, sort_keys=True), now, now,
            ),
        )
        return int(cur.lastrowid)

    def _make_clean_fixture(self) -> tuple[int, int, int, int]:
        """Return (token_id, pair_id, snapshot_id, window_id) for a valid clean setup."""
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id)
            win_id = self._insert_window(conn, token_id, pair_id, snap_id)
            conn.commit()
        finally:
            conn.close()
        return token_id, pair_id, snap_id, win_id

    def _run(self, window_id: int) -> dict:
        conn = self._connect()
        try:
            result = audit_15m_memory_window(conn, window_id)
            conn.commit()
        finally:
            conn.close()
        return result

    def _read_window(self, window_id: int) -> sqlite3.Row:
        conn = self._connect()
        try:
            return conn.execute(
                "SELECT * FROM printer_memory_windows WHERE id = ?", (window_id,)
            ).fetchone()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Import and constants
# ---------------------------------------------------------------------------

class LaneE2QImportTests(unittest.TestCase):
    def test_module_imports_cleanly(self):
        from printer_v1.operator_cli import e2q_memory_window_audit
        self.assertIsNotNone(e2q_memory_window_audit)

    def test_function_importable(self):
        self.assertTrue(callable(audit_15m_memory_window))

    def test_status_clean_candidate(self):
        self.assertEqual(E2Q_STATUS_CLEAN_CANDIDATE, "E2Q_AUDIT_CLEAN_CANDIDATE")

    def test_status_dirty(self):
        self.assertEqual(E2Q_STATUS_DIRTY, "E2Q_AUDIT_DIRTY")

    def test_status_audit_only(self):
        self.assertEqual(E2Q_STATUS_AUDIT_ONLY, "E2Q_AUDIT_ONLY")

    def test_status_blocked(self):
        self.assertEqual(E2Q_STATUS_BLOCKED, "E2Q_AUDIT_BLOCKED")

    def test_required_window_kind_window_15m(self):
        self.assertEqual(E2Q_REQUIRED_WINDOW_KIND, "WINDOW_15M")

    def test_required_window_status_closed(self):
        self.assertEqual(E2Q_REQUIRED_WINDOW_STATUS, "WINDOW_CLOSED")

    def test_required_source_status_complete(self):
        self.assertEqual(E2Q_REQUIRED_SOURCE_STATUS, "COMPLETE")

    def test_required_quality_clean_data(self):
        self.assertEqual(E2Q_REQUIRED_QUALITY, "CLEAN_DATA")

    def test_hard_locks_all_true(self):
        for key, val in _HARD_LOCKS.items():
            self.assertTrue(val, f"hard lock {key!r} must be True")

    def test_hard_locks_no_buy_sell_hold(self):
        self.assertIn("no_buy_sell_hold", _HARD_LOCKS)

    def test_hard_locks_no_memory_creation(self):
        self.assertIn("no_memory_creation", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_memory_creation"])

    def test_hard_locks_no_5m_main_window(self):
        self.assertIn("no_5m_main_window", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_5m_main_window"])

    def test_hard_locks_no_scoring_ranking(self):
        self.assertIn("no_scoring_ranking", _HARD_LOCKS)

    def test_hard_locks_no_embeddings_vectors(self):
        self.assertIn("no_embeddings_vectors", _HARD_LOCKS)

    def test_hard_locks_no_retrieval_activation(self):
        self.assertIn("no_retrieval_activation", _HARD_LOCKS)


# ---------------------------------------------------------------------------
# Happy path: clean window → E2Q_AUDIT_CLEAN_CANDIDATE
# ---------------------------------------------------------------------------

class LaneE2QHappyPathTests(_DbTestBase):
    def test_clean_window_classified_clean_candidate(self):
        _, _, _, win_id = self._make_clean_fixture()
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_CLEAN_CANDIDATE)

    def test_classified_flag_true(self):
        _, _, _, win_id = self._make_clean_fixture()
        r = self._run(win_id)
        self.assertTrue(r.get("classified"))

    def test_window_id_in_result(self):
        _, _, _, win_id = self._make_clean_fixture()
        r = self._run(win_id)
        self.assertEqual(r.get("window_id"), win_id)

    def test_snapshot_id_in_result(self):
        _, _, snap_id, win_id = self._make_clean_fixture()
        r = self._run(win_id)
        self.assertEqual(r.get("snapshot_id"), snap_id)

    def test_memory_quality_label_partial_memory(self):
        _, _, _, win_id = self._make_clean_fixture()
        r = self._run(win_id)
        self.assertEqual(r.get("memory_quality_label"), "PARTIAL_MEMORY")

    def test_rejection_reasons_empty(self):
        _, _, _, win_id = self._make_clean_fixture()
        r = self._run(win_id)
        self.assertEqual(r.get("rejection_reasons"), [])

    def test_hard_locks_in_result(self):
        _, _, _, win_id = self._make_clean_fixture()
        r = self._run(win_id)
        locks = r.get("hard_locks", {})
        for key, val in _HARD_LOCKS.items():
            self.assertTrue(locks.get(key), f"{key!r} missing or False")

    def test_paper_decisions_zero(self):
        _, _, _, win_id = self._make_clean_fixture()
        r = self._run(win_id)
        self.assertEqual(r.get("paper_decisions_created"), 0)

    def test_memories_zero(self):
        _, _, _, win_id = self._make_clean_fixture()
        r = self._run(win_id)
        self.assertEqual(r.get("memories_created"), 0)


# ---------------------------------------------------------------------------
# Write-back: window row updated after classification
# ---------------------------------------------------------------------------

class LaneE2QWriteBackTests(_DbTestBase):
    def test_clean_candidate_writes_memory_quality_label(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        row = self._read_window(win_id)
        self.assertEqual(row["memory_quality_label"], "PARTIAL_MEMORY")

    def test_clean_candidate_writes_do_not_train_zero(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        row = self._read_window(win_id)
        self.assertEqual(row["do_not_train"], 0)

    def test_clean_candidate_sets_e2q_audited_in_context(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        row = self._read_window(win_id)
        ctx = json.loads(row["supporting_context_json"])
        self.assertTrue(ctx.get("e2q_audited"))

    def test_clean_candidate_rejection_reasons_empty_json(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        row = self._read_window(win_id)
        reasons = json.loads(row["rejection_reasons_json"] or "[]")
        self.assertEqual(reasons, [])

    def test_dirty_writes_dirty_memory_quality(self):
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id,
                                            source_status="FAILED",
                                            data_quality_label="DIRTY_DATA")
            win_id = self._insert_window(conn, token_id, pair_id, snap_id)
            conn.commit()
        finally:
            conn.close()
        self._run(win_id)
        row = self._read_window(win_id)
        self.assertEqual(row["memory_quality_label"], "DIRTY_MEMORY")

    def test_dirty_sets_do_not_train_one(self):
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id,
                                            source_status="STALE",
                                            data_quality_label="STALE_DATA")
            win_id = self._insert_window(conn, token_id, pair_id, snap_id)
            conn.commit()
        finally:
            conn.close()
        self._run(win_id)
        row = self._read_window(win_id)
        self.assertEqual(row["do_not_train"], 1)

    def test_audit_only_writes_audit_only_memory_quality(self):
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id)
            win_id = self._insert_window(conn, token_id, pair_id, snap_id,
                                         data_quality_label="ACCEPTABLE_PARTIAL_DATA")
            conn.commit()
        finally:
            conn.close()
        self._run(win_id)
        row = self._read_window(win_id)
        self.assertEqual(row["memory_quality_label"], "AUDIT_ONLY_MEMORY")

    def test_audit_only_sets_do_not_train_one(self):
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id)
            win_id = self._insert_window(conn, token_id, pair_id, snap_id,
                                         data_quality_label="ACCEPTABLE_PARTIAL_DATA")
            conn.commit()
        finally:
            conn.close()
        self._run(win_id)
        row = self._read_window(win_id)
        self.assertEqual(row["do_not_train"], 1)


# ---------------------------------------------------------------------------
# Idempotency: duplicate audit produces same result, no extra rows
# ---------------------------------------------------------------------------

class LaneE2QIdempotencyTests(_DbTestBase):
    def test_duplicate_audit_same_status(self):
        _, _, _, win_id = self._make_clean_fixture()
        r1 = self._run(win_id)
        r2 = self._run(win_id)
        self.assertEqual(r1.get("e2q_status"), r2.get("e2q_status"))

    def test_duplicate_audit_no_extra_window_rows(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        self._run(win_id)
        self.assertEqual(self._count_rows("printer_memory_windows"), 1)

    def test_duplicate_audit_same_memory_quality_label(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        self._run(win_id)
        row = self._read_window(win_id)
        self.assertEqual(row["memory_quality_label"], "PARTIAL_MEMORY")

    def test_duplicate_audit_e2q_audited_remains_true(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        self._run(win_id)
        row = self._read_window(win_id)
        ctx = json.loads(row["supporting_context_json"])
        self.assertTrue(ctx.get("e2q_audited"))


# ---------------------------------------------------------------------------
# E2Q-A: strict no-op idempotency — updated_at must not change on re-audit
# ---------------------------------------------------------------------------

class LaneE2QANoOpIdempotencyTests(_DbTestBase):
    """E2Q-A: second identical audit must be a state-preserving no-op."""

    def test_first_audit_row_updated_true(self):
        _, _, _, win_id = self._make_clean_fixture()
        r = self._run(win_id)
        self.assertTrue(r.get("row_updated"))

    def test_second_identical_audit_row_updated_false(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        r2 = self._run(win_id)
        self.assertFalse(r2.get("row_updated"))

    def test_second_identical_audit_does_not_change_updated_at(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        row_after_first = self._read_window(win_id)
        updated_at_first = row_after_first["updated_at"]

        self._run(win_id)
        row_after_second = self._read_window(win_id)
        self.assertEqual(row_after_second["updated_at"], updated_at_first)

    def test_second_identical_audit_does_not_change_supporting_context_json(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        ctx_after_first = self._read_window(win_id)["supporting_context_json"]

        self._run(win_id)
        ctx_after_second = self._read_window(win_id)["supporting_context_json"]
        self.assertEqual(ctx_after_second, ctx_after_first)

    def test_second_identical_audit_does_not_change_rejection_reasons_json(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        rr_after_first = self._read_window(win_id)["rejection_reasons_json"]

        self._run(win_id)
        rr_after_second = self._read_window(win_id)["rejection_reasons_json"]
        self.assertEqual(rr_after_second, rr_after_first)

    def test_second_identical_audit_creates_no_extra_rows(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        self._run(win_id)
        self.assertEqual(self._count_rows("printer_memory_windows"), 1)

    def test_second_identical_audit_same_status(self):
        _, _, _, win_id = self._make_clean_fixture()
        r1 = self._run(win_id)
        r2 = self._run(win_id)
        self.assertEqual(r1.get("e2q_status"), r2.get("e2q_status"))

    def test_dirty_second_audit_is_also_no_op(self):
        """Re-auditing a dirty window with same evidence → row_updated=False."""
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id,
                                            source_status="FAILED",
                                            data_quality_label="DIRTY_DATA")
            win_id = self._insert_window(conn, token_id, pair_id, snap_id)
            conn.commit()
        finally:
            conn.close()
        self._run(win_id)
        r2 = self._run(win_id)
        self.assertFalse(r2.get("row_updated"))

    def test_dirty_second_audit_does_not_change_updated_at(self):
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id,
                                            source_status="STALE",
                                            data_quality_label="STALE_DATA")
            win_id = self._insert_window(conn, token_id, pair_id, snap_id)
            conn.commit()
        finally:
            conn.close()
        self._run(win_id)
        updated_at_first = self._read_window(win_id)["updated_at"]
        self._run(win_id)
        self.assertEqual(self._read_window(win_id)["updated_at"], updated_at_first)

    def test_audit_only_second_audit_is_also_no_op(self):
        """Re-auditing an audit-only window with same evidence → row_updated=False."""
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id)
            win_id = self._insert_window(conn, token_id, pair_id, snap_id,
                                         data_quality_label="ACCEPTABLE_PARTIAL_DATA")
            conn.commit()
        finally:
            conn.close()
        self._run(win_id)
        r2 = self._run(win_id)
        self.assertFalse(r2.get("row_updated"))

    def test_audit_only_second_audit_does_not_change_updated_at(self):
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id)
            win_id = self._insert_window(conn, token_id, pair_id, snap_id,
                                         data_quality_label="ACCEPTABLE_PARTIAL_DATA")
            conn.commit()
        finally:
            conn.close()
        self._run(win_id)
        updated_at_first = self._read_window(win_id)["updated_at"]
        self._run(win_id)
        self.assertEqual(self._read_window(win_id)["updated_at"], updated_at_first)


# ---------------------------------------------------------------------------
# Blocked: missing window
# ---------------------------------------------------------------------------

class LaneE2QBlockedMissingWindowTests(_DbTestBase):
    def test_missing_window_blocked(self):
        r = self._run(99999)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_BLOCKED)

    def test_missing_window_classified_false(self):
        r = self._run(99999)
        self.assertFalse(r.get("classified"))

    def test_missing_window_has_blocked_reasons(self):
        r = self._run(99999)
        self.assertTrue(len(r.get("blocked_reasons", [])) > 0)

    def test_missing_window_no_write_back(self):
        self._run(99999)
        self.assertEqual(self._count_rows("printer_memory_windows"), 0)


# ---------------------------------------------------------------------------
# Blocked: wrong window_kind
# ---------------------------------------------------------------------------

class LaneE2QBlockedWindowKindTests(_DbTestBase):
    def _window_with_kind(self, kind: str) -> int:
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id)
            win_id = self._insert_window(conn, token_id, pair_id, snap_id,
                                         window_kind=kind)
            conn.commit()
        finally:
            conn.close()
        return win_id

    def test_window_1h_blocked(self):
        win_id = self._window_with_kind("WINDOW_1H")
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_BLOCKED)

    def test_window_4h_blocked(self):
        win_id = self._window_with_kind("WINDOW_4H")
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_BLOCKED)

    def test_window_5m_micro_event_blocked(self):
        """5m micro-event window is not a valid main outcome window."""
        win_id = self._window_with_kind("WINDOW_5M_MICRO_EVENT")
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_BLOCKED)

    def test_window_5m_blocked_reason_mentions_5m(self):
        win_id = self._window_with_kind("WINDOW_5M_MICRO_EVENT")
        r = self._run(win_id)
        reasons = " ".join(r.get("blocked_reasons", []))
        self.assertIn("5m", reasons.lower())

    def test_window_kind_blocked_no_write_back_to_quality_label(self):
        win_id = self._window_with_kind("WINDOW_1H")
        self._run(win_id)
        row = self._read_window(win_id)
        self.assertIsNone(row["memory_quality_label"])


# ---------------------------------------------------------------------------
# Blocked: open (non-closed) window
# ---------------------------------------------------------------------------

class LaneE2QBlockedOpenWindowTests(_DbTestBase):
    def _window_with_status(self, status: str) -> int:
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id)
            win_id = self._insert_window(conn, token_id, pair_id, snap_id,
                                         window_status=status)
            conn.commit()
        finally:
            conn.close()
        return win_id

    def test_open_window_blocked(self):
        win_id = self._window_with_status("WINDOW_OPEN")
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_BLOCKED)

    def test_closing_window_blocked(self):
        win_id = self._window_with_status("WINDOW_CLOSING")
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_BLOCKED)

    def test_broken_window_blocked(self):
        win_id = self._window_with_status("WINDOW_BROKEN")
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_BLOCKED)

    def test_open_blocked_classified_false(self):
        win_id = self._window_with_status("WINDOW_OPEN")
        r = self._run(win_id)
        self.assertFalse(r.get("classified"))

    def test_open_blocked_no_write_back(self):
        win_id = self._window_with_status("WINDOW_OPEN")
        self._run(win_id)
        row = self._read_window(win_id)
        self.assertIsNone(row["memory_quality_label"])


# ---------------------------------------------------------------------------
# Blocked: missing or invalid supporting_context_json
# ---------------------------------------------------------------------------

class LaneE2QBlockedContextTests(_DbTestBase):
    def test_missing_supporting_context_blocked(self):
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id)
            win_id = self._insert_window(conn, token_id, pair_id, snap_id,
                                         supporting_context={})
            conn.commit()
        finally:
            conn.close()
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_BLOCKED)

    def test_context_without_snapshot_id_blocked(self):
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id)
            win_id = self._insert_window(conn, token_id, pair_id, snap_id,
                                         supporting_context={"tracking_lane": "TRACK_FAST"})
            conn.commit()
        finally:
            conn.close()
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_BLOCKED)

    def test_null_supporting_context_blocked(self):
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id)
            # Insert window with NULL supporting_context_json
            cur = conn.execute(
                """
                INSERT INTO printer_memory_windows (
                    token_id, pair_id, window_kind, opened_at, closed_at,
                    memory_status, data_quality_label, do_not_train, window_status,
                    supporting_context_json, created_by_phase, created_at, updated_at
                ) VALUES (?, ?, 'WINDOW_15M', ?, ?, 'PARTIAL_MEMORY', 'CLEAN_DATA',
                          0, 'WINDOW_CLOSED', NULL, 'test', ?, ?)
                """,
                (token_id, pair_id, _CAPTURED_AT, _CAPTURED_AT, _CAPTURED_AT, _CAPTURED_AT),
            )
            conn.commit()
            win_id = int(cur.lastrowid)
        finally:
            conn.close()
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_BLOCKED)


# ---------------------------------------------------------------------------
# Blocked: missing snapshot
# ---------------------------------------------------------------------------

class LaneE2QBlockedMissingSnapshotTests(_DbTestBase):
    def test_missing_snapshot_blocked(self):
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            # Reference a non-existent snapshot_id
            win_id = self._insert_window(conn, token_id, pair_id, 99999)
            conn.commit()
        finally:
            conn.close()
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_BLOCKED)

    def test_missing_snapshot_classified_false(self):
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            win_id = self._insert_window(conn, token_id, pair_id, 99999)
            conn.commit()
        finally:
            conn.close()
        r = self._run(win_id)
        self.assertFalse(r.get("classified"))


# ---------------------------------------------------------------------------
# Dirty: bad snapshot source_status / data_quality_label
# ---------------------------------------------------------------------------

class LaneE2QDirtySnapshotTests(_DbTestBase):
    def _setup_with_snap_status(self, source_status: str, quality: str = "CLEAN_DATA") -> int:
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id,
                                            source_status=source_status,
                                            data_quality_label=quality)
            win_id = self._insert_window(conn, token_id, pair_id, snap_id)
            conn.commit()
        finally:
            conn.close()
        return win_id

    def _setup_with_snap_quality(self, quality: str) -> int:
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id,
                                            source_status="COMPLETE",
                                            data_quality_label=quality)
            win_id = self._insert_window(conn, token_id, pair_id, snap_id)
            conn.commit()
        finally:
            conn.close()
        return win_id

    def test_failed_source_status_dirty(self):
        win_id = self._setup_with_snap_status("FAILED", "DIRTY_DATA")
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_DIRTY)

    def test_stale_source_status_dirty(self):
        win_id = self._setup_with_snap_status("STALE", "STALE_DATA")
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_DIRTY)

    def test_conflicting_source_status_dirty(self):
        win_id = self._setup_with_snap_status("CONFLICTING", "CONFLICTING_DATA")
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_DIRTY)

    def test_dirty_data_quality_dirty(self):
        win_id = self._setup_with_snap_quality("DIRTY_DATA")
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_DIRTY)

    def test_stale_data_quality_dirty(self):
        win_id = self._setup_with_snap_quality("STALE_DATA")
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_DIRTY)

    def test_missing_critical_data_quality_dirty(self):
        win_id = self._setup_with_snap_quality("MISSING_CRITICAL_DATA")
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_DIRTY)

    def test_do_not_train_quality_dirty(self):
        win_id = self._setup_with_snap_quality("DO_NOT_TRAIN")
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_DIRTY)

    def test_dirty_has_rejection_reasons(self):
        win_id = self._setup_with_snap_status("FAILED", "DIRTY_DATA")
        r = self._run(win_id)
        self.assertTrue(len(r.get("rejection_reasons", [])) > 0)

    def test_dirty_classified_true(self):
        win_id = self._setup_with_snap_status("STALE", "STALE_DATA")
        r = self._run(win_id)
        self.assertTrue(r.get("classified"))


# ---------------------------------------------------------------------------
# Dirty: bad window data_quality_label
# ---------------------------------------------------------------------------

class LaneE2QDirtyWindowTests(_DbTestBase):
    def _setup_window_quality(self, quality: str) -> int:
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id)
            win_id = self._insert_window(conn, token_id, pair_id, snap_id,
                                         data_quality_label=quality)
            conn.commit()
        finally:
            conn.close()
        return win_id

    def test_dirty_data_window_dirty(self):
        win_id = self._setup_window_quality("DIRTY_DATA")
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_DIRTY)

    def test_stale_data_window_dirty(self):
        win_id = self._setup_window_quality("STALE_DATA")
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_DIRTY)

    def test_acceptable_partial_window_audit_only(self):
        win_id = self._setup_window_quality("ACCEPTABLE_PARTIAL_DATA")
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_AUDIT_ONLY)

    def test_audit_only_classified_true(self):
        win_id = self._setup_window_quality("ACCEPTABLE_PARTIAL_DATA")
        r = self._run(win_id)
        self.assertTrue(r.get("classified"))

    def test_audit_only_rejection_reasons_empty(self):
        win_id = self._setup_window_quality("ACCEPTABLE_PARTIAL_DATA")
        r = self._run(win_id)
        self.assertEqual(r.get("rejection_reasons"), [])


# ---------------------------------------------------------------------------
# Blocked: token/pair identity mismatch
# ---------------------------------------------------------------------------

class LaneE2QBlockedMismatchTests(_DbTestBase):
    def test_token_id_mismatch_blocked(self):
        conn = self._connect()
        try:
            token_id_1 = self._insert_token(conn, _MINT_1)
            token_id_2 = self._insert_token(conn, _MINT_2)
            pair_id = self._insert_pair(conn, token_id_1)
            # Snapshot belongs to token_2, window belongs to token_1
            snap_id = self._insert_snapshot(conn, token_id_2, pair_id)
            win_id = self._insert_window(conn, token_id_1, pair_id, snap_id)
            conn.commit()
        finally:
            conn.close()
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_BLOCKED)

    def test_token_mismatch_blocked_reason_mentions_token_id(self):
        conn = self._connect()
        try:
            token_id_1 = self._insert_token(conn, _MINT_1)
            token_id_2 = self._insert_token(conn, _MINT_2)
            pair_id = self._insert_pair(conn, token_id_1)
            snap_id = self._insert_snapshot(conn, token_id_2, pair_id)
            win_id = self._insert_window(conn, token_id_1, pair_id, snap_id)
            conn.commit()
        finally:
            conn.close()
        r = self._run(win_id)
        reasons = " ".join(r.get("blocked_reasons", []))
        self.assertIn("token_id", reasons)

    def test_pair_id_mismatch_blocked(self):
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id_1 = self._insert_pair(conn, token_id, _PAIR_ADDR)
            pair_id_2 = self._insert_pair(conn, token_id, _PAIR_ADDR + "2")
            snap_id = self._insert_snapshot(conn, token_id, pair_id_1)
            win_id = self._insert_window(conn, token_id, pair_id_2, snap_id)
            conn.commit()
        finally:
            conn.close()
        r = self._run(win_id)
        self.assertEqual(r.get("e2q_status"), E2Q_STATUS_BLOCKED)

    def test_window_null_pair_snapshot_nonnull_pair_passes(self):
        """Window pair_id=None with snapshot pair_id set → no mismatch (null OK)."""
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id)
            # Window has pair_id=None, snapshot has pair_id set → no conflict
            win_id = self._insert_window(conn, token_id, None, snap_id)
            conn.commit()
        finally:
            conn.close()
        r = self._run(win_id)
        self.assertNotEqual(r.get("e2q_status"), E2Q_STATUS_BLOCKED)


# ---------------------------------------------------------------------------
# Forbidden tables: no paper, no episodes, no memories
# ---------------------------------------------------------------------------

class LaneE2QForbiddenTableTests(_DbTestBase):
    def test_no_paper_decisions_created(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        self.assertEqual(self._count_rows("printer_paper_decisions"), 0)

    def test_no_paper_positions_created(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        self.assertEqual(self._count_rows("printer_paper_positions"), 0)

    def test_no_paper_trade_events_created(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        self.assertEqual(self._count_rows("printer_paper_trade_events"), 0)

    def test_no_paper_trade_audits_created(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        self.assertEqual(self._count_rows("printer_paper_trade_audits"), 0)

    def test_no_episodes_created(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        self.assertEqual(self._count_rows("printer_episodes"), 0)

    def test_no_episode_snapshots_created(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        self.assertEqual(self._count_rows("printer_episode_snapshots"), 0)

    def test_no_episode_outcomes_created(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        self.assertEqual(self._count_rows("printer_episode_outcomes"), 0)

    def test_no_memory_fingerprints_created(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        self.assertEqual(self._count_rows("printer_memory_fingerprints"), 0)

    def test_no_extra_memory_windows_created(self):
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        # Only the one window we inserted; audit updates it, not inserts more.
        self.assertEqual(self._count_rows("printer_memory_windows"), 1)

    def test_no_printer_memories_created_if_table_exists(self):
        """printer_memories table absent in this schema — count gracefully returns 0."""
        _, _, _, win_id = self._make_clean_fixture()
        self._run(win_id)
        self.assertEqual(self._count_rows("printer_memories"), 0)

    def test_blocked_result_does_not_write_back(self):
        """When blocked, window memory_quality_label must remain NULL."""
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            snap_id = self._insert_snapshot(conn, token_id, pair_id)
            win_id = self._insert_window(conn, token_id, pair_id, snap_id,
                                         window_kind="WINDOW_1H")
            conn.commit()
        finally:
            conn.close()
        self._run(win_id)
        row = self._read_window(win_id)
        self.assertIsNone(row["memory_quality_label"])


if __name__ == "__main__":
    import unittest
    unittest.main()

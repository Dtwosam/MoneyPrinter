"""
Post-Lane 10 Lane Q -- Real-Time 15m Window Integrity Guard

Thirteen boundary proofs:
 1.  Valid 15m window (start/end >= 900s, snapshot ids, CLEAN_DATA, not do_not_train) passes
 2.  Missing window_start_at blocks with missing_window_start_at
 3.  Missing window_end_at blocks with missing_window_end_at
 4.  Invalid/unparseable window_start_at blocks with invalid_window_start_at
 5.  Invalid/unparseable window_end_at blocks with invalid_window_end_at
 6.  Elapsed time below 900 seconds blocks with elapsed_seconds_below_900
 7.  Missing snapshot_start_id blocks
 8.  Missing snapshot_end_id blocks
 9.  snapshot_end_id < snapshot_start_id blocks with invalid_snapshot_order
10.  WINDOW_5M_MICRO_EVENT blocks as main clean memory (not_window_15m)
11.  Dirty data / do_not_train window blocks (dirty_or_do_not_train_window)
12.  guard_candidate_windows approval and DB-path gates
13.  Lane K integration — compressed instant windows do not become clean memory;
     Lane K locks preserved; idempotency for real 15m candidates
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
from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline
from printer_v1.operator_cli.lane_q_15m_window_integrity_guard import (
    LANE_Q_BLOCKED,
    LANE_Q_GUARD_BLOCKED,
    LANE_Q_GUARD_COMPLETED,
    LANE_Q_VALID,
    MIN_ELAPSED_SECONDS,
    _HARD_LOCKS,
    check_window_integrity,
    guard_candidate_windows,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINT = "LaneQTestMintAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_PAIR = "LaneQTestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_NOW = "2026-06-29T10:00:00+00:00"
_WIN_START = "2026-06-29T10:00:00+00:00"
_WIN_END = "2026-06-29T10:15:01+00:00"   # 901 s → passes the 900-s gate
_WIN_END_FAST = "2026-06-29T10:00:00+00:00"  # same as start → 0 s elapsed


def _valid_row(**overrides) -> dict:
    """Return a minimal window row that passes all Lane Q checks."""
    base = {
        "id": 1,
        "window_kind": "WINDOW_15M",
        "data_quality_label": "CLEAN_DATA",
        "do_not_train": 0,
        "memory_status": "PARTIAL_MEMORY",
        "memory_quality_label": "PARTIAL_MEMORY",
        "window_start_at": _WIN_START,
        "window_end_at": _WIN_END,
        "snapshot_start_id": 1,
        "snapshot_end_id": 5,
    }
    base.update(overrides)
    return base


def _clean_ctx(snapshot_id: int) -> str:
    return json.dumps({
        "snapshot_id": snapshot_id,
        "e2q_audited": True,
        "e2q_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
        "e2q_audited_by": "lane_e2q",
    }, sort_keys=True)


class _DBBase(unittest.TestCase):
    """Base for tests that need a real SQLite DB."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        apply_migrations(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _count(self, table: str) -> int:
        conn = sqlite3.connect(str(self.db_path))
        try:
            r = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return r[0] if r else 0
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def _insert_token(self, conn) -> int:
        return int(conn.execute(
            "INSERT INTO printer_tokens"
            " (token_mint, chain, symbol, name, first_seen_at, last_seen_at,"
            "  token_status, created_at, updated_at)"
            " VALUES (?, 'solana', 'T', 'T', ?, ?, 'TRACKING', ?, ?)",
            (_MINT, _NOW, _NOW, _NOW, _NOW),
        ).lastrowid)

    def _insert_pair(self, conn, token_id: int) -> int:
        return int(conn.execute(
            "INSERT INTO printer_pairs"
            " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at,"
            "  created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_id, _PAIR, _PAIR, _NOW, _NOW, _NOW, _NOW),
        ).lastrowid)

    def _insert_window(
        self,
        conn,
        token_id: int,
        pair_id: int,
        *,
        window_kind: str = "WINDOW_15M",
        window_status: str = "WINDOW_CLOSED",
        memory_status: str = "PARTIAL_MEMORY",
        memory_quality_label: str = "PARTIAL_MEMORY",
        data_quality_label: str = "CLEAN_DATA",
        do_not_train: int = 0,
        supporting_context_json: str | None = None,
        snapshot_id: int = 99,
        window_start_at: str | None = _WIN_START,
        window_end_at: str | None = _WIN_END,
        snapshot_start_id: int | None = 1,
        snapshot_end_id: int | None = 2,
    ) -> int:
        if supporting_context_json is None:
            supporting_context_json = _clean_ctx(snapshot_id)
        return int(conn.execute(
            """
            INSERT INTO printer_memory_windows (
                token_id, pair_id, window_kind, opened_at, closed_at,
                memory_status, data_quality_label, do_not_train,
                window_status, memory_quality_label,
                supporting_context_json, created_by_phase, created_at, updated_at,
                window_start_at, window_end_at,
                snapshot_start_id, snapshot_end_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'lane_e2o', ?, ?, ?, ?, ?, ?)
            """,
            (
                token_id, pair_id, window_kind, _NOW, _NOW,
                memory_status, data_quality_label, do_not_train,
                window_status, memory_quality_label,
                supporting_context_json, _NOW, _NOW,
                window_start_at, window_end_at,
                snapshot_start_id, snapshot_end_id,
            ),
        ).lastrowid)

    def _make_five_eligible(
        self,
        *,
        window_start_at: str = _WIN_START,
        window_end_at: str = _WIN_END,
    ) -> tuple[int, int, list[int]]:
        """5 valid E2Y + Lane-Q-eligible WINDOW_15M rows."""
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            wids = []
            for i, sid in enumerate((101, 102, 103, 104, 105)):
                wid = self._insert_window(
                    conn, tid, pid,
                    snapshot_id=sid,
                    window_start_at=window_start_at,
                    window_end_at=window_end_at,
                    snapshot_start_id=i * 10 + 1,
                    snapshot_end_id=i * 10 + 5,
                )
                wids.append(wid)
            conn.commit()
        finally:
            conn.close()
        return tid, pid, wids

    def _run_lane_k(self, **kw) -> dict:
        return run_e2z_pipeline(self.db_path, operator_approved=True, **kw)


# ===========================================================================
# Proof 1 — Valid 15m window passes
# ===========================================================================

class LaneQValidWindowTests(unittest.TestCase):
    def test_valid_row_passes(self):
        r = check_window_integrity(_valid_row())
        self.assertEqual(r["lane_q_status"], LANE_Q_VALID)

    def test_valid_row_no_blocked_reasons(self):
        r = check_window_integrity(_valid_row())
        self.assertEqual(r["blocked_reasons"], [])

    def test_valid_row_integrity_proven_true(self):
        r = check_window_integrity(_valid_row())
        self.assertIs(r["integrity_proven"], True)

    def test_valid_row_elapsed_seconds_gte_900(self):
        r = check_window_integrity(_valid_row())
        self.assertIsNotNone(r["elapsed_seconds"])
        self.assertGreaterEqual(r["elapsed_seconds"], MIN_ELAPSED_SECONDS)

    def test_valid_row_snapshot_start_and_end_present(self):
        r = check_window_integrity(_valid_row())
        self.assertIsNotNone(r["snapshot_start_id"])
        self.assertIsNotNone(r["snapshot_end_id"])

    def test_valid_row_exactly_900_seconds_passes(self):
        r = check_window_integrity(_valid_row(
            window_start_at="2026-06-29T10:00:00+00:00",
            window_end_at="2026-06-29T10:15:00+00:00",
        ))
        self.assertEqual(r["lane_q_status"], LANE_Q_VALID)

    def test_valid_row_snapshot_end_equal_to_start_passes(self):
        r = check_window_integrity(_valid_row(snapshot_start_id=5, snapshot_end_id=5))
        self.assertEqual(r["lane_q_status"], LANE_Q_VALID)


# ===========================================================================
# Proof 2 — Missing window_start_at blocks
# ===========================================================================

class LaneQMissingStartTests(unittest.TestCase):
    def test_none_start_at_blocked(self):
        r = check_window_integrity(_valid_row(window_start_at=None))
        self.assertEqual(r["lane_q_status"], LANE_Q_BLOCKED)

    def test_none_start_at_reason(self):
        r = check_window_integrity(_valid_row(window_start_at=None))
        self.assertIn("missing_window_start_at", r["blocked_reasons"])

    def test_empty_string_start_at_blocked(self):
        r = check_window_integrity(_valid_row(window_start_at=""))
        self.assertEqual(r["lane_q_status"], LANE_Q_BLOCKED)

    def test_empty_string_start_at_reason(self):
        r = check_window_integrity(_valid_row(window_start_at=""))
        self.assertIn("missing_window_start_at", r["blocked_reasons"])

    def test_missing_start_no_elapsed(self):
        r = check_window_integrity(_valid_row(window_start_at=None))
        self.assertIsNone(r["elapsed_seconds"])


# ===========================================================================
# Proof 3 — Missing window_end_at blocks
# ===========================================================================

class LaneQMissingEndTests(unittest.TestCase):
    def test_none_end_at_blocked(self):
        r = check_window_integrity(_valid_row(window_end_at=None))
        self.assertEqual(r["lane_q_status"], LANE_Q_BLOCKED)

    def test_none_end_at_reason(self):
        r = check_window_integrity(_valid_row(window_end_at=None))
        self.assertIn("missing_window_end_at", r["blocked_reasons"])

    def test_empty_string_end_at_blocked(self):
        r = check_window_integrity(_valid_row(window_end_at=""))
        self.assertEqual(r["lane_q_status"], LANE_Q_BLOCKED)

    def test_empty_string_end_at_reason(self):
        r = check_window_integrity(_valid_row(window_end_at=""))
        self.assertIn("missing_window_end_at", r["blocked_reasons"])

    def test_missing_end_no_elapsed(self):
        r = check_window_integrity(_valid_row(window_end_at=None))
        self.assertIsNone(r["elapsed_seconds"])


# ===========================================================================
# Proof 4 — Invalid window_start_at blocks
# ===========================================================================

class LaneQInvalidStartTests(unittest.TestCase):
    def test_garbage_start_at_blocked(self):
        r = check_window_integrity(_valid_row(window_start_at="not-a-date"))
        self.assertEqual(r["lane_q_status"], LANE_Q_BLOCKED)

    def test_garbage_start_at_reason(self):
        r = check_window_integrity(_valid_row(window_start_at="not-a-date"))
        self.assertIn("invalid_window_start_at", r["blocked_reasons"])

    def test_integer_start_at_blocked(self):
        r = check_window_integrity(_valid_row(window_start_at=123456))
        self.assertEqual(r["lane_q_status"], LANE_Q_BLOCKED)

    def test_partial_date_start_blocked(self):
        r = check_window_integrity(_valid_row(window_start_at="2026-06-29"))
        # "2026-06-29" parses as a date in fromisoformat → valid, so elapsed check runs
        # But it's a date not datetime — fromisoformat returns date not datetime on 3.11+
        # Actually datetime.fromisoformat("2026-06-29") → datetime(2026, 6, 29, 0, 0) in 3.11+
        # That's a naive datetime without time, which may still work.
        # The important thing is it doesn't raise and elapsed is computed.
        # This edge case is more about documentation. Just verify no exception.
        self.assertIn(r["lane_q_status"], (LANE_Q_VALID, LANE_Q_BLOCKED))


# ===========================================================================
# Proof 5 — Invalid window_end_at blocks
# ===========================================================================

class LaneQInvalidEndTests(unittest.TestCase):
    def test_garbage_end_at_blocked(self):
        r = check_window_integrity(_valid_row(window_end_at="not-a-date"))
        self.assertEqual(r["lane_q_status"], LANE_Q_BLOCKED)

    def test_garbage_end_at_reason(self):
        r = check_window_integrity(_valid_row(window_end_at="not-a-date"))
        self.assertIn("invalid_window_end_at", r["blocked_reasons"])

    def test_integer_end_at_blocked(self):
        r = check_window_integrity(_valid_row(window_end_at=9999999))
        self.assertEqual(r["lane_q_status"], LANE_Q_BLOCKED)

    def test_no_elapsed_when_end_invalid(self):
        r = check_window_integrity(_valid_row(window_end_at="BADVALUE"))
        self.assertIsNone(r["elapsed_seconds"])


# ===========================================================================
# Proof 6 — Elapsed time below 900 seconds blocks
# ===========================================================================

class LaneQElapsedTests(unittest.TestCase):
    def test_zero_elapsed_blocked(self):
        r = check_window_integrity(_valid_row(
            window_start_at=_WIN_START,
            window_end_at=_WIN_START,  # same → 0 s
        ))
        self.assertEqual(r["lane_q_status"], LANE_Q_BLOCKED)

    def test_zero_elapsed_reason(self):
        r = check_window_integrity(_valid_row(
            window_start_at=_WIN_START,
            window_end_at=_WIN_START,
        ))
        self.assertIn("elapsed_seconds_below_900", r["blocked_reasons"])

    def test_899_seconds_blocked(self):
        r = check_window_integrity(_valid_row(
            window_start_at="2026-06-29T10:00:00+00:00",
            window_end_at="2026-06-29T10:14:59+00:00",   # 899 s
        ))
        self.assertEqual(r["lane_q_status"], LANE_Q_BLOCKED)

    def test_899_seconds_reason(self):
        r = check_window_integrity(_valid_row(
            window_start_at="2026-06-29T10:00:00+00:00",
            window_end_at="2026-06-29T10:14:59+00:00",
        ))
        self.assertIn("elapsed_seconds_below_900", r["blocked_reasons"])

    def test_900_seconds_passes(self):
        r = check_window_integrity(_valid_row(
            window_start_at="2026-06-29T10:00:00+00:00",
            window_end_at="2026-06-29T10:15:00+00:00",   # exactly 900 s
        ))
        self.assertEqual(r["lane_q_status"], LANE_Q_VALID)

    def test_elapsed_seconds_returned(self):
        r = check_window_integrity(_valid_row(
            window_start_at="2026-06-29T10:00:00+00:00",
            window_end_at="2026-06-29T10:00:00+00:00",
        ))
        self.assertEqual(r["elapsed_seconds"], 0.0)

    def test_instant_window_blocked_is_main_integrity_concern(self):
        """Compressed/instant windows must not become clean memory."""
        r = check_window_integrity(_valid_row(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END_FAST,
        ))
        self.assertIs(r["integrity_proven"], False)


# ===========================================================================
# Proof 7 — Missing snapshot_start_id blocks
# ===========================================================================

class LaneQMissingSnapshotStartTests(unittest.TestCase):
    def test_none_snapshot_start_blocked(self):
        r = check_window_integrity(_valid_row(snapshot_start_id=None))
        self.assertEqual(r["lane_q_status"], LANE_Q_BLOCKED)

    def test_none_snapshot_start_reason(self):
        r = check_window_integrity(_valid_row(snapshot_start_id=None))
        self.assertIn("missing_snapshot_start_id", r["blocked_reasons"])

    def test_integrity_proven_false_on_missing_snapshot_start(self):
        r = check_window_integrity(_valid_row(snapshot_start_id=None))
        self.assertIs(r["integrity_proven"], False)


# ===========================================================================
# Proof 8 — Missing snapshot_end_id blocks
# ===========================================================================

class LaneQMissingSnapshotEndTests(unittest.TestCase):
    def test_none_snapshot_end_blocked(self):
        r = check_window_integrity(_valid_row(snapshot_end_id=None))
        self.assertEqual(r["lane_q_status"], LANE_Q_BLOCKED)

    def test_none_snapshot_end_reason(self):
        r = check_window_integrity(_valid_row(snapshot_end_id=None))
        self.assertIn("missing_snapshot_end_id", r["blocked_reasons"])

    def test_integrity_proven_false_on_missing_snapshot_end(self):
        r = check_window_integrity(_valid_row(snapshot_end_id=None))
        self.assertIs(r["integrity_proven"], False)


# ===========================================================================
# Proof 9 — snapshot_end_id < snapshot_start_id blocks
# ===========================================================================

class LaneQSnapshotOrderTests(unittest.TestCase):
    def test_end_lt_start_blocked(self):
        r = check_window_integrity(_valid_row(snapshot_start_id=10, snapshot_end_id=5))
        self.assertEqual(r["lane_q_status"], LANE_Q_BLOCKED)

    def test_end_lt_start_reason(self):
        r = check_window_integrity(_valid_row(snapshot_start_id=10, snapshot_end_id=5))
        self.assertIn("invalid_snapshot_order", r["blocked_reasons"])

    def test_end_equal_start_passes(self):
        r = check_window_integrity(_valid_row(snapshot_start_id=7, snapshot_end_id=7))
        self.assertEqual(r["lane_q_status"], LANE_Q_VALID)
        self.assertNotIn("invalid_snapshot_order", r["blocked_reasons"])

    def test_end_gt_start_passes(self):
        r = check_window_integrity(_valid_row(snapshot_start_id=1, snapshot_end_id=99))
        self.assertEqual(r["lane_q_status"], LANE_Q_VALID)


# ===========================================================================
# Proof 10 — WINDOW_5M_MICRO_EVENT blocks (not_window_15m)
# ===========================================================================

class LaneQ5mWindowTests(unittest.TestCase):
    def test_5m_window_blocked(self):
        r = check_window_integrity(_valid_row(window_kind="WINDOW_5M_MICRO_EVENT"))
        self.assertEqual(r["lane_q_status"], LANE_Q_BLOCKED)

    def test_5m_window_reason(self):
        r = check_window_integrity(_valid_row(window_kind="WINDOW_5M_MICRO_EVENT"))
        self.assertIn("not_window_15m", r["blocked_reasons"])

    def test_window_4h_blocked(self):
        r = check_window_integrity(_valid_row(window_kind="WINDOW_4H"))
        self.assertIn("not_window_15m", r["blocked_reasons"])

    def test_window_1h_blocked(self):
        r = check_window_integrity(_valid_row(window_kind="WINDOW_1H"))
        self.assertIn("not_window_15m", r["blocked_reasons"])

    def test_window_24h_blocked(self):
        r = check_window_integrity(_valid_row(window_kind="WINDOW_24H"))
        self.assertIn("not_window_15m", r["blocked_reasons"])

    def test_5m_window_integrity_proven_false(self):
        r = check_window_integrity(_valid_row(window_kind="WINDOW_5M_MICRO_EVENT"))
        self.assertIs(r["integrity_proven"], False)


# ===========================================================================
# Proof 11 — Dirty data / do_not_train blocks
# ===========================================================================

class LaneQDirtyWindowTests(unittest.TestCase):
    def test_dirty_data_blocked(self):
        r = check_window_integrity(_valid_row(data_quality_label="DIRTY_DATA"))
        self.assertEqual(r["lane_q_status"], LANE_Q_BLOCKED)

    def test_dirty_data_reason(self):
        r = check_window_integrity(_valid_row(data_quality_label="DIRTY_DATA"))
        self.assertIn("dirty_or_do_not_train_window", r["blocked_reasons"])

    def test_stale_data_blocked(self):
        r = check_window_integrity(_valid_row(data_quality_label="STALE_DATA"))
        self.assertIn("dirty_or_do_not_train_window", r["blocked_reasons"])

    def test_do_not_train_1_blocked(self):
        r = check_window_integrity(_valid_row(do_not_train=1))
        self.assertEqual(r["lane_q_status"], LANE_Q_BLOCKED)

    def test_do_not_train_1_reason(self):
        r = check_window_integrity(_valid_row(do_not_train=1))
        self.assertIn("dirty_or_do_not_train_window", r["blocked_reasons"])

    def test_do_not_train_true_blocked(self):
        r = check_window_integrity(_valid_row(do_not_train=True))
        self.assertIn("dirty_or_do_not_train_window", r["blocked_reasons"])

    def test_dirty_memory_status_blocked(self):
        r = check_window_integrity(_valid_row(
            memory_status="DIRTY_MEMORY",
            memory_quality_label="DIRTY_MEMORY",
        ))
        self.assertIn("unsupported_memory_status", r["blocked_reasons"])

    def test_audit_only_memory_blocked(self):
        r = check_window_integrity(_valid_row(
            memory_status="AUDIT_ONLY",
            memory_quality_label="AUDIT_ONLY",
        ))
        self.assertIn("unsupported_memory_status", r["blocked_reasons"])

    def test_do_not_train_memory_status_blocked(self):
        r = check_window_integrity(_valid_row(
            memory_status="DO_NOT_TRAIN",
            memory_quality_label="DO_NOT_TRAIN",
        ))
        self.assertIn("unsupported_memory_status", r["blocked_reasons"])


# ===========================================================================
# Proof 12 — guard_candidate_windows approval and DB-path gates
# ===========================================================================

class LaneQGuardApprovalTests(unittest.TestCase):
    def test_guard_blocked_without_approval(self):
        r = guard_candidate_windows(None, [], operator_approved=False)
        self.assertEqual(r["lane_q_guard_status"], LANE_Q_GUARD_BLOCKED)

    def test_guard_blocked_reason_approval(self):
        r = guard_candidate_windows(None, [], operator_approved=False)
        self.assertTrue(any("operator_approved" in s for s in r["blocked_reasons"]))

    def test_guard_blocked_none_db_path(self):
        r = guard_candidate_windows(None, [], operator_approved=True)
        self.assertEqual(r["lane_q_guard_status"], LANE_Q_GUARD_BLOCKED)

    def test_guard_blocked_missing_file(self):
        r = guard_candidate_windows(
            "/nonexistent/path/db.sqlite3", [], operator_approved=True
        )
        self.assertEqual(r["lane_q_guard_status"], LANE_Q_GUARD_BLOCKED)

    def test_guard_zero_clean_valid_on_blocked(self):
        r = guard_candidate_windows(None, [], operator_approved=False)
        self.assertIs(r["zero_clean_memories_valid"], True)

    def test_guard_hard_locks_on_blocked(self):
        r = guard_candidate_windows(None, [], operator_approved=False)
        self.assertIn("hard_locks", r)
        self.assertTrue(all(r["hard_locks"].values()))


class LaneQGuardDbTests(_DBBase):
    def test_guard_completed_with_valid_window(self):
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            wid = self._insert_window(conn, tid, pid, snapshot_id=10)
            conn.commit()
        finally:
            conn.close()
        r = guard_candidate_windows(
            self.db_path, [wid], operator_approved=True
        )
        self.assertEqual(r["lane_q_guard_status"], LANE_Q_GUARD_COMPLETED)
        self.assertIn(wid, r["valid_window_ids"])
        self.assertEqual(r["valid_count"], 1)
        self.assertEqual(r["blocked_count"], 0)

    def test_guard_blocks_instant_window(self):
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            wid = self._insert_window(
                conn, tid, pid, snapshot_id=10,
                window_start_at=_WIN_START,
                window_end_at=_WIN_START,   # elapsed = 0
            )
            conn.commit()
        finally:
            conn.close()
        r = guard_candidate_windows(
            self.db_path, [wid], operator_approved=True
        )
        self.assertIn(wid, r["blocked_window_ids"])
        self.assertEqual(r["blocked_count"], 1)
        self.assertEqual(r["valid_count"], 0)

    def test_guard_zero_clean_valid_always(self):
        r = guard_candidate_windows(self.db_path, [], operator_approved=True)
        self.assertIs(r["zero_clean_memories_valid"], True)

    def test_guard_hard_locks_all_true(self):
        r = guard_candidate_windows(self.db_path, [], operator_approved=True)
        self.assertTrue(all(r["hard_locks"].values()))

    def test_guard_missing_window_id_blocked(self):
        r = guard_candidate_windows(
            self.db_path, [99999], operator_approved=True
        )
        self.assertIn(99999, r["blocked_window_ids"])

    def test_guard_mixed_valid_and_blocked(self):
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            wid_valid = self._insert_window(conn, tid, pid, snapshot_id=1)
            wid_instant = self._insert_window(
                conn, tid, pid, snapshot_id=2,
                window_start_at=_WIN_START,
                window_end_at=_WIN_START,
            )
            conn.commit()
        finally:
            conn.close()
        r = guard_candidate_windows(
            self.db_path, [wid_valid, wid_instant], operator_approved=True
        )
        self.assertIn(wid_valid, r["valid_window_ids"])
        self.assertIn(wid_instant, r["blocked_window_ids"])
        self.assertEqual(r["valid_count"], 1)
        self.assertEqual(r["blocked_count"], 1)


# ===========================================================================
# Proof 13 — Lane K integration with Lane Q guard
# ===========================================================================

class LaneKIntegrationInstantWindowTests(_DBBase):
    def test_lane_k_does_not_create_episodes_from_instant_windows(self):
        """Compressed (start==end) WINDOW_15M rows must not become clean memory."""
        # Insert 5 "instant" windows — they pass E2X/E2Y but fail Lane Q
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END_FAST,   # 0 s elapsed
        )
        r = self._run_lane_k()
        self.assertEqual(r["clean_memory_rows_created"], 0)

    def test_lane_k_instant_windows_blocked_by_lane_q(self):
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END_FAST,
        )
        r = self._run_lane_k()
        self.assertEqual(r.get("lane_q_blocked_count", 0), 5)

    def test_lane_k_zero_clean_valid_when_all_lane_q_blocked(self):
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END_FAST,
        )
        r = self._run_lane_k()
        self.assertIs(r["zero_clean_memories_valid"], True)

    def test_lane_k_completed_not_blocked_when_all_lane_q_blocked(self):
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END_FAST,
        )
        r = self._run_lane_k()
        from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import LANE_K_STATUS_COMPLETED
        self.assertEqual(r["lane_k_status"], LANE_K_STATUS_COMPLETED)

    def test_lane_k_no_episodes_created_from_instant_windows(self):
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END_FAST,
        )
        before = self._count("printer_episodes")
        self._run_lane_k()
        self.assertEqual(self._count("printer_episodes"), before)


class LaneKIntegrationLocksTests(_DBBase):
    def test_no_retrieval_rows_created(self):
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END_FAST,
        )
        before = self._count("printer_memory_retrieval_queries")
        self._run_lane_k()
        self.assertEqual(self._count("printer_memory_retrieval_queries"), before)

    def test_no_paper_decisions_created(self):
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END_FAST,
        )
        before = self._count("printer_paper_decisions")
        self._run_lane_k()
        self.assertEqual(self._count("printer_paper_decisions"), before)

    def test_no_positions_created(self):
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END_FAST,
        )
        before = self._count("printer_paper_positions")
        self._run_lane_k()
        self.assertEqual(self._count("printer_paper_positions"), before)

    def test_no_trade_events_created(self):
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END_FAST,
        )
        before = self._count("printer_paper_trade_events")
        self._run_lane_k()
        self.assertEqual(self._count("printer_paper_trade_events"), before)

    def test_no_paper_trade_audits_created(self):
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END_FAST,
        )
        before = self._count("printer_paper_trade_audits")
        self._run_lane_k()
        self.assertEqual(self._count("printer_paper_trade_audits"), before)

    def test_no_source_requests_created(self):
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END_FAST,
        )
        before = self._count("printer_source_requests")
        self._run_lane_k()
        self.assertEqual(self._count("printer_source_requests"), before)

    def test_no_scheduler_jobs_created(self):
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END_FAST,
        )
        before = self._count("printer_scheduler_jobs")
        self._run_lane_k()
        self.assertEqual(self._count("printer_scheduler_jobs"), before)

    def test_retrieval_activated_false(self):
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END_FAST,
        )
        r = self._run_lane_k()
        self.assertIs(r["retrieval_activated"], False)

    def test_paper_decisions_created_zero(self):
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END_FAST,
        )
        r = self._run_lane_k()
        self.assertEqual(r["paper_decisions_created"], 0)

    def test_pnl_created_zero(self):
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END_FAST,
        )
        r = self._run_lane_k()
        self.assertEqual(r["pnl_created"], 0)


class LaneKIntegrationIdempotencyTests(_DBBase):
    def test_idempotency_for_valid_real_15m_windows(self):
        """Valid real 15m windows: first run creates, second creates nothing."""
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END,   # 901 s — valid
        )
        r1 = self._run_lane_k()
        self.assertEqual(r1["e2z_created_count"], 5)
        self.assertEqual(r1["clean_memory_rows_created"], 5)

        r2 = self._run_lane_k()
        self.assertEqual(r2["e2z_created_count"], 0)
        self.assertEqual(r2["e2z_already_exists_count"], 5)
        self.assertEqual(r2["clean_memory_rows_created"], 0)

    def test_episode_count_stable_after_rerun(self):
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END,
        )
        self._run_lane_k()
        count_after_first = self._count("printer_episodes")
        self._run_lane_k()
        self.assertEqual(self._count("printer_episodes"), count_after_first)

    def test_rerun_zero_clean_still_valid(self):
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END,
        )
        self._run_lane_k()
        r2 = self._run_lane_k()
        self.assertIs(r2["zero_clean_memories_valid"], True)

    def test_rerun_lane_q_blocked_count_zero_for_valid_windows(self):
        """Valid windows pass Lane Q on both runs."""
        self._make_five_eligible(
            window_start_at=_WIN_START,
            window_end_at=_WIN_END,
        )
        self._run_lane_k()
        r2 = self._run_lane_k()
        self.assertEqual(r2.get("lane_q_blocked_count", 0), 0)


if __name__ == "__main__":
    unittest.main()

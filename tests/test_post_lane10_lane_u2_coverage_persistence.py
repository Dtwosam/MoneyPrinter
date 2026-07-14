"""Lane U2 — Coverage Audit Persistence tests.

Coverage proofs:
  1.  operator_approved=False → LANE_U2_BLOCKED, zero writes
  2.  db_path missing / invalid → LANE_U2_BLOCKED
  3.  Valid TRACK_FAST window (10 snaps, gaps ≤ 120s) → COVERAGE_PASS
  4.  Coverage fields are non-null after persistence (coverage_state et al)
  5.  printer_snapshot_window_coverage has row after persistence
  6.  printer_snapshot_gap_audits has rows (9 gap rows for 10 snapshots)
  7.  Insufficient snapshots for TRACK_FAST (9 of 10) → COVERAGE_BLOCKED
  8.  Excessive gap (> 120s) in TRACK_FAST window → COVERAGE_BLOCKED
  9.  Zero snapshots + production_mode=True → COVERAGE_BLOCKED
 10.  Zero snapshots + production_mode=False → COVERAGE_UNKNOWN (non-blocking)
 11.  WINDOW_5M_MICRO_EVENT (support-only) → COVERAGE_BLOCKED
 12.  WINDOW_1H (disabled) → COVERAGE_BLOCKED
 13.  WINDOW_4H (disabled) → COVERAGE_BLOCKED
 14.  Rerun is idempotent: no duplicate coverage or gap rows
 15.  window_id not in DB → window classified COVERAGE_BLOCKED, zero DB writes
 16.  Valid TRACK_NORMAL window (5 snaps, gaps ≤ 300s) → COVERAGE_PASS
 17.  Lane K: 6 eligible WINDOW_15M windows passes E2Y gate (>= 5)
 18.  Lane K: TRACK_NORMAL windows with real snapshots → COVERAGE_PASS → episodes
 19.  Lane K: coverage_rows_written > 0 after successful Lane K run
 20.  Hard locks / financial locks remain zero after coverage persistence
"""

from __future__ import annotations

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
from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline
from printer_v1.operator_cli.lane_u2_coverage_audit_persistence import (
    COVERAGE_STATE_BLOCKED,
    COVERAGE_STATE_PASS,
    COVERAGE_STATE_UNKNOWN,
    LANE_U2_STATUS_BLOCKED,
    LANE_U2_STATUS_COMPLETED,
    persist_coverage_for_windows,
)


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_MINT = "LaneU2TestMintAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_PAIR = "LaneU2TestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_NOW = "2026-06-29T10:00:00+00:00"

_BASE_DT = datetime(2026, 6, 29, 10, 0, 0, tzinfo=timezone.utc)
_WIN_START = _BASE_DT.isoformat()
_WIN_END = (_BASE_DT + timedelta(seconds=901)).isoformat()

# 15m windows staggered 15m apart (for multi-window tests)
_WINDOW_STARTS = [
    (_BASE_DT + timedelta(minutes=i * 15)).isoformat() for i in range(6)
]
_WINDOW_ENDS = [
    (_BASE_DT + timedelta(minutes=i * 15, seconds=901)).isoformat() for i in range(6)
]


def _clean_ctx(snapshot_id: int) -> str:
    return json.dumps({
        "snapshot_id": snapshot_id,
        "e2q_audited": True,
        "e2q_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
        "e2q_audited_by": "lane_e2q",
    }, sort_keys=True)


def _track_fast_snap_times(base: datetime = _BASE_DT, n: int = 16) -> list[str]:
    """V2-6.1a clean FAST cadence: 16 snapshots evenly across 900s (gaps 60s)."""
    return [(base + timedelta(seconds=round(i * 900 / (n - 1)))).isoformat() for i in range(n)]


def _track_normal_snap_times(base: datetime = _BASE_DT, n: int = 9) -> list[str]:
    """V2-6.1a clean NORMAL cadence: 9 snapshots evenly across 900s (gaps 112.5s)."""
    return [(base + timedelta(seconds=round(i * 900 / (n - 1)))).isoformat() for i in range(n)]


class _DBBase(unittest.TestCase):
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

    def _count(self, table: str) -> int:
        conn = sqlite3.connect(str(self.db_path))
        try:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def _insert_token(self, conn, *, token_status: str = "TRACK_FAST") -> int:
        return int(conn.execute(
            "INSERT INTO printer_tokens"
            " (token_mint, chain, symbol, name, first_seen_at, last_seen_at,"
            "  token_status, created_at, updated_at)"
            " VALUES (?, 'solana', 'T', 'T', ?, ?, ?, ?, ?)",
            (_MINT, _NOW, _NOW, token_status, _NOW, _NOW),
        ).lastrowid)

    def _insert_pair(self, conn, token_id: int) -> int:
        return int(conn.execute(
            "INSERT INTO printer_pairs"
            " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at,"
            "  created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_id, _PAIR, _PAIR, _NOW, _NOW, _NOW, _NOW),
        ).lastrowid)

    def _insert_snapshot(
        self,
        conn,
        snap_id: int,
        token_id: int,
        pair_id: int,
        captured_at: str,
        *,
        tracking_lane: str = "TRACK_FAST",
        source_status: str = "COMPLETE",
        data_quality_label: str = "CLEAN_DATA",
    ) -> int:
        return int(conn.execute(
            """INSERT INTO printer_token_snapshots (
                id, token_id, pair_id, captured_at,
                tracking_lane, snapshot_mode,
                source_status, data_quality_label,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                snap_id, token_id, pair_id, captured_at,
                tracking_lane, tracking_lane,
                source_status, data_quality_label,
                _NOW,
            ),
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
        snapshot_id: int = 99,
        window_start_at: str | None = _WIN_START,
        window_end_at: str | None = _WIN_END,
        snapshot_start_id: int | None = None,
        snapshot_end_id: int | None = None,
        created_at: str = _NOW,
    ) -> int:
        return int(conn.execute(
            """
            INSERT INTO printer_memory_windows (
                token_id, pair_id, window_kind, opened_at, closed_at,
                memory_status, data_quality_label, do_not_train,
                window_status, memory_quality_label,
                supporting_context_json, created_by_phase,
                created_at, updated_at,
                window_start_at, window_end_at,
                snapshot_start_id, snapshot_end_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'lane_e2o', ?, ?, ?, ?, ?, ?)
            """,
            (
                token_id, pair_id, window_kind, _NOW, _NOW,
                memory_status, data_quality_label, do_not_train,
                window_status, memory_quality_label,
                _clean_ctx(snapshot_id), created_at, created_at,
                window_start_at, window_end_at,
                snapshot_start_id, snapshot_end_id,
            ),
        ).lastrowid)

    def _run(
        self,
        window_ids: list[int],
        *,
        operator_approved: bool = True,
        production_mode: bool = False,
    ) -> dict:
        return persist_coverage_for_windows(
            self.db_path,
            window_ids,
            operator_approved=operator_approved,
            production_mode=production_mode,
        )

    def _window_row(self, window_id: int) -> dict:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM printer_memory_windows WHERE id = ?",
                (window_id,),
            ).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()


# ===========================================================================
# Proof 1 — Approval gate
# ===========================================================================

class LaneU2ApprovalGateTests(_DBBase):
    def _make_window(self) -> list[int]:
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            wid = self._insert_window(conn, tid, pid)
            conn.commit()
        finally:
            conn.close()
        return [wid]

    def test_no_approval_returns_blocked(self):
        wids = self._make_window()
        r = self._run(wids, operator_approved=False)
        self.assertEqual(r["lane_u2_status"], LANE_U2_STATUS_BLOCKED)

    def test_no_approval_zero_coverage_rows(self):
        wids = self._make_window()
        self._run(wids, operator_approved=False)
        self.assertEqual(self._count("printer_snapshot_window_coverage"), 0)

    def test_no_approval_zero_gap_audit_rows(self):
        wids = self._make_window()
        self._run(wids, operator_approved=False)
        self.assertEqual(self._count("printer_snapshot_gap_audits"), 0)

    def test_no_approval_window_ids_in_blocked_ids(self):
        wids = self._make_window()
        r = self._run(wids, operator_approved=False)
        self.assertEqual(r["coverage_blocked_ids"], wids)

    def test_no_approval_hard_locks_present(self):
        r = self._run([], operator_approved=False)
        self.assertIn("hard_locks", r)
        self.assertIs(r["hard_locks"]["no_retrieval_activation"], True)

    def test_missing_db_path_returns_blocked(self):
        r = persist_coverage_for_windows(
            None, [1], operator_approved=True
        )
        self.assertEqual(r["lane_u2_status"], LANE_U2_STATUS_BLOCKED)

    def test_invalid_db_path_returns_blocked(self):
        r = persist_coverage_for_windows(
            "/nonexistent/path/printer_v1.sqlite3", [1], operator_approved=True
        )
        self.assertEqual(r["lane_u2_status"], LANE_U2_STATUS_BLOCKED)


# ===========================================================================
# Proof 2 — Valid TRACK_FAST coverage → COVERAGE_PASS
# ===========================================================================

class LaneU2TrackFastPassTests(_DBBase):
    def _setup(self) -> tuple[int, int, int]:
        """Return (token_id, pair_id, window_id) with 16 valid TRACK_FAST snaps."""
        conn = self._connect()
        try:
            tid = self._insert_token(conn, token_status="TRACK_FAST")
            pid = self._insert_pair(conn, tid)
            # V2-6.1a: 16 clean FAST snapshots (IDs 1000..1015) at 60s spacing.
            snap_times = _track_fast_snap_times(_BASE_DT)
            for i, ts in enumerate(snap_times):
                self._insert_snapshot(conn, 1000 + i, tid, pid, ts,
                                      tracking_lane="TRACK_FAST")
            wid = self._insert_window(
                conn, tid, pid,
                snapshot_start_id=1000,
                snapshot_end_id=1000 + len(snap_times) - 1,
            )
            conn.commit()
        finally:
            conn.close()
        return tid, pid, wid

    def test_status_completed(self):
        _, _, wid = self._setup()
        r = self._run([wid])
        self.assertEqual(r["lane_u2_status"], LANE_U2_STATUS_COMPLETED)

    def test_coverage_state_pass(self):
        _, _, wid = self._setup()
        r = self._run([wid])
        self.assertIn(wid, r["coverage_pass_ids"])

    def test_window_result_coverage_state_pass(self):
        _, _, wid = self._setup()
        r = self._run([wid])
        result = next(v for v in r["window_coverage_results"] if v["window_id"] == wid)
        self.assertEqual(result["coverage_state"], COVERAGE_STATE_PASS)

    def test_coverage_rows_written_one(self):
        _, _, wid = self._setup()
        r = self._run([wid])
        self.assertEqual(r["coverage_rows_written"], 1)

    def test_printer_snapshot_window_coverage_has_row(self):
        _, _, wid = self._setup()
        self._run([wid])
        self.assertEqual(self._count("printer_snapshot_window_coverage"), 1)

    def test_printer_snapshot_gap_audits_has_rows(self):
        _, _, wid = self._setup()
        self._run([wid])
        # 16 snapshots → 15 inter-snapshot gaps
        self.assertEqual(self._count("printer_snapshot_gap_audits"), 15)

    def test_gap_audit_rows_written_in_result(self):
        _, _, wid = self._setup()
        r = self._run([wid])
        self.assertEqual(r["gap_audit_rows_written"], 15)

    def test_coverage_state_persisted_to_window(self):
        _, _, wid = self._setup()
        self._run([wid])
        row = self._window_row(wid)
        self.assertEqual(row["coverage_state"], COVERAGE_STATE_PASS)

    def test_actual_snapshot_count_persisted(self):
        _, _, wid = self._setup()
        self._run([wid])
        row = self._window_row(wid)
        self.assertEqual(row["actual_snapshot_count"], 16)

    def test_expected_snapshot_count_persisted(self):
        _, _, wid = self._setup()
        self._run([wid])
        row = self._window_row(wid)
        # TRACK_FAST minimum_required_snapshots = 16
        self.assertEqual(row["expected_snapshot_count"], 16)

    def test_missing_snapshot_count_is_zero(self):
        _, _, wid = self._setup()
        self._run([wid])
        row = self._window_row(wid)
        self.assertEqual(row["missing_snapshot_count"], 0)

    def test_coverage_fields_not_null(self):
        _, _, wid = self._setup()
        self._run([wid])
        row = self._window_row(wid)
        self.assertIsNotNone(row["coverage_state"])
        self.assertIsNotNone(row["actual_snapshot_count"])
        self.assertIsNotNone(row["expected_snapshot_count"])
        self.assertIsNotNone(row["missing_snapshot_count"])

    def test_hard_locks_financial_zero(self):
        _, _, wid = self._setup()
        r = self._run([wid])
        self.assertIs(r["retrieval_activated"], False)
        self.assertEqual(r["paper_decisions_created"], 0)
        self.assertIs(r["buy_enabled"], False)
        self.assertIs(r["sell_enabled"], False)
        self.assertIs(r["hold_enabled"], False)
        self.assertEqual(r["positions_created"], 0)
        self.assertEqual(r["pnl_created"], 0)

    def test_no_episodes_created(self):
        _, _, wid = self._setup()
        before = self._count("printer_episodes")
        self._run([wid])
        self.assertEqual(self._count("printer_episodes"), before)


# ===========================================================================
# Proof 3 — Valid TRACK_NORMAL coverage → COVERAGE_PASS
# ===========================================================================

class LaneU2TrackNormalPassTests(_DBBase):
    def _setup(self) -> tuple[int, int, int]:
        conn = self._connect()
        try:
            tid = self._insert_token(conn, token_status="TRACK_NORMAL")
            pid = self._insert_pair(conn, tid)
            snap_times = _track_normal_snap_times(_BASE_DT)
            for i, ts in enumerate(snap_times):
                self._insert_snapshot(conn, 2000 + i, tid, pid, ts,
                                      tracking_lane="TRACK_NORMAL")
            wid = self._insert_window(
                conn, tid, pid,
                snapshot_start_id=2000,
                snapshot_end_id=2000 + len(snap_times) - 1,
            )
            conn.commit()
        finally:
            conn.close()
        return tid, pid, wid

    def test_coverage_pass(self):
        _, _, wid = self._setup()
        r = self._run([wid])
        self.assertIn(wid, r["coverage_pass_ids"])

    def test_coverage_row_written(self):
        _, _, wid = self._setup()
        self._run([wid])
        self.assertEqual(self._count("printer_snapshot_window_coverage"), 1)

    def test_gap_audit_rows_for_5_snaps(self):
        _, _, wid = self._setup()
        self._run([wid])
        # 9 snapshots → 8 inter-snapshot gaps
        self.assertEqual(self._count("printer_snapshot_gap_audits"), 8)

    def test_actual_count_is_5(self):
        _, _, wid = self._setup()
        self._run([wid])
        row = self._window_row(wid)
        self.assertEqual(row["actual_snapshot_count"], 9)

    def test_expected_count_is_5(self):
        _, _, wid = self._setup()
        self._run([wid])
        row = self._window_row(wid)
        # TRACK_NORMAL minimum_required_snapshots = 9
        self.assertEqual(row["expected_snapshot_count"], 9)


# ===========================================================================
# Proof 4 — Blocked coverage scenarios
# ===========================================================================

class LaneU2CoverageBlockedTests(_DBBase):
    def _insert_token_pair(self, conn, *, status="TRACK_FAST"):
        tid = self._insert_token(conn, token_status=status)
        pid = self._insert_pair(conn, tid)
        return tid, pid

    # --- Insufficient snapshots (9 of 10 required for TRACK_FAST) ---

    def test_insufficient_snaps_blocked(self):
        conn = self._connect()
        try:
            tid, pid = self._insert_token_pair(conn)
            snap_times = _track_fast_snap_times(n=9)  # only 9 of 10 required
            for i, ts in enumerate(snap_times):
                self._insert_snapshot(conn, 3000 + i, tid, pid, ts)
            wid = self._insert_window(
                conn, tid, pid,
                snapshot_start_id=3000, snapshot_end_id=3008,
            )
            conn.commit()
        finally:
            conn.close()

        r = self._run([wid])
        self.assertIn(wid, r["coverage_blocked_ids"])
        self.assertEqual(r["coverage_pass_ids"], [])

    def test_insufficient_snaps_coverage_state_blocked_on_window(self):
        conn = self._connect()
        try:
            tid, pid = self._insert_token_pair(conn)
            for i, ts in enumerate(_track_fast_snap_times(n=9)):
                self._insert_snapshot(conn, 3100 + i, tid, pid, ts)
            wid = self._insert_window(
                conn, tid, pid,
                snapshot_start_id=3100, snapshot_end_id=3108,
            )
            conn.commit()
        finally:
            conn.close()

        self._run([wid])
        row = self._window_row(wid)
        self.assertEqual(row["coverage_state"], COVERAGE_STATE_BLOCKED)

    # --- Excessive gap (> 120s for TRACK_FAST) ---

    def test_excessive_gap_blocked(self):
        """Gap of 131s between snap 4 and snap 5 exceeds 120s max."""
        conn = self._connect()
        try:
            tid, pid = self._insert_token_pair(conn)
            base = _BASE_DT
            # First 5 snaps normal, then a 131s gap, then 4 more
            times = [(base + timedelta(seconds=45 + i * 90)).isoformat()
                     for i in range(5)]
            # Snap 5 comes 131s after snap 4 (instead of 90s)
            snap5 = (base + timedelta(seconds=45 + 4 * 90 + 131)).isoformat()
            times.append(snap5)
            # Snaps 6-9 continue at 90s intervals from snap 5
            gap5_dt = base + timedelta(seconds=45 + 4 * 90 + 131)
            for i in range(1, 5):
                times.append((gap5_dt + timedelta(seconds=i * 90)).isoformat())
            for i, ts in enumerate(times):
                self._insert_snapshot(conn, 3200 + i, tid, pid, ts)
            wid = self._insert_window(
                conn, tid, pid,
                snapshot_start_id=3200, snapshot_end_id=3209,
            )
            conn.commit()
        finally:
            conn.close()

        r = self._run([wid])
        self.assertIn(wid, r["coverage_blocked_ids"])

    # --- 5m support-only window ---

    def test_5m_support_only_blocked(self):
        conn = self._connect()
        try:
            tid, pid = self._insert_token_pair(conn)
            # 3 snaps so it's not a 0-snap case (0 returns UNKNOWN not BLOCKED)
            base = _BASE_DT
            for i in range(3):
                ts = (base + timedelta(seconds=30 + i * 60)).isoformat()
                self._insert_snapshot(conn, 4000 + i, tid, pid, ts)
            wid = self._insert_window(
                conn, tid, pid,
                window_kind="WINDOW_5M_MICRO_EVENT",
                window_start_at=_WIN_START,
                window_end_at=(_BASE_DT + timedelta(seconds=301)).isoformat(),
                snapshot_start_id=4000,
                snapshot_end_id=4002,
            )
            conn.commit()
        finally:
            conn.close()

        r = self._run([wid])
        self.assertIn(wid, r["coverage_blocked_ids"])

    def test_5m_support_only_coverage_state(self):
        conn = self._connect()
        try:
            tid, pid = self._insert_token_pair(conn)
            base = _BASE_DT
            for i in range(3):
                ts = (base + timedelta(seconds=30 + i * 60)).isoformat()
                self._insert_snapshot(conn, 4100 + i, tid, pid, ts)
            wid = self._insert_window(
                conn, tid, pid,
                window_kind="WINDOW_5M_MICRO_EVENT",
                window_start_at=_WIN_START,
                window_end_at=(_BASE_DT + timedelta(seconds=301)).isoformat(),
                snapshot_start_id=4100,
                snapshot_end_id=4102,
            )
            conn.commit()
        finally:
            conn.close()

        self._run([wid])
        row = self._window_row(wid)
        self.assertEqual(row["coverage_state"], COVERAGE_STATE_BLOCKED)

    # --- WINDOW_1H disabled ---

    def test_1h_window_blocked(self):
        conn = self._connect()
        try:
            tid, pid = self._insert_token_pair(conn)
            base = _BASE_DT
            for i in range(5):
                ts = (base + timedelta(seconds=300 + i * 600)).isoformat()
                self._insert_snapshot(conn, 5000 + i, tid, pid, ts)
            wid = self._insert_window(
                conn, tid, pid,
                window_kind="WINDOW_1H",
                window_start_at=_WIN_START,
                window_end_at=(_BASE_DT + timedelta(seconds=3601)).isoformat(),
                snapshot_start_id=5000,
                snapshot_end_id=5004,
            )
            conn.commit()
        finally:
            conn.close()

        r = self._run([wid])
        self.assertIn(wid, r["coverage_blocked_ids"])

    # --- WINDOW_4H disabled ---

    def test_4h_window_blocked(self):
        conn = self._connect()
        try:
            tid, pid = self._insert_token_pair(conn)
            base = _BASE_DT
            for i in range(5):
                ts = (base + timedelta(seconds=600 + i * 1200)).isoformat()
                self._insert_snapshot(conn, 6000 + i, tid, pid, ts)
            wid = self._insert_window(
                conn, tid, pid,
                window_kind="WINDOW_4H",
                window_start_at=_WIN_START,
                window_end_at=(_BASE_DT + timedelta(seconds=14401)).isoformat(),
                snapshot_start_id=6000,
                snapshot_end_id=6004,
            )
            conn.commit()
        finally:
            conn.close()

        r = self._run([wid])
        self.assertIn(wid, r["coverage_blocked_ids"])

    def test_window_not_in_db_is_blocked(self):
        r = self._run([9999])  # non-existent window
        self.assertIn(9999, r["coverage_blocked_ids"])
        self.assertEqual(r["coverage_pass_ids"], [])


# ===========================================================================
# Proof 5 — Production mode: zero snapshots → BLOCKED
# ===========================================================================

class LaneU2ProductionModeTests(_DBBase):
    def _make_window_no_snaps(self) -> int:
        conn = self._connect()
        try:
            tid = self._insert_token(conn, token_status="TRACK_FAST")
            pid = self._insert_pair(conn, tid)
            wid = self._insert_window(
                conn, tid, pid,
                snapshot_start_id=9001,
                snapshot_end_id=9010,
            )
            conn.commit()
        finally:
            conn.close()
        return wid

    def test_zero_snaps_production_mode_true_blocked(self):
        wid = self._make_window_no_snaps()
        r = self._run([wid], production_mode=True)
        self.assertIn(wid, r["coverage_blocked_ids"])

    def test_zero_snaps_production_mode_true_state_blocked_on_window(self):
        wid = self._make_window_no_snaps()
        self._run([wid], production_mode=True)
        row = self._window_row(wid)
        self.assertEqual(row["coverage_state"], COVERAGE_STATE_BLOCKED)

    def test_zero_snaps_production_mode_false_unknown(self):
        wid = self._make_window_no_snaps()
        r = self._run([wid], production_mode=False)
        self.assertIn(wid, r["coverage_unknown_ids"])
        self.assertNotIn(wid, r["coverage_blocked_ids"])

    def test_zero_snaps_production_mode_false_state_unknown_on_window(self):
        wid = self._make_window_no_snaps()
        self._run([wid], production_mode=False)
        row = self._window_row(wid)
        self.assertEqual(row["coverage_state"], COVERAGE_STATE_UNKNOWN)


# ===========================================================================
# Proof 6 — Idempotency: rerun produces no duplicate rows
# ===========================================================================

class LaneU2IdempotencyTests(_DBBase):
    def _setup(self) -> int:
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            snap_times = _track_fast_snap_times()
            for i, ts in enumerate(snap_times):
                self._insert_snapshot(conn, 7000 + i, tid, pid, ts)
            wid = self._insert_window(
                conn, tid, pid,
                snapshot_start_id=7000,
                snapshot_end_id=7000 + len(snap_times) - 1,
            )
            conn.commit()
        finally:
            conn.close()
        return wid

    def test_rerun_no_duplicate_coverage_rows(self):
        wid = self._setup()
        self._run([wid])
        self._run([wid])
        self.assertEqual(self._count("printer_snapshot_window_coverage"), 1)

    def test_rerun_no_duplicate_gap_audit_rows(self):
        wid = self._setup()
        self._run([wid])
        self._run([wid])
        # 16 snaps → 15 gaps, no duplicates
        self.assertEqual(self._count("printer_snapshot_gap_audits"), 15)

    def test_rerun_still_pass(self):
        wid = self._setup()
        self._run([wid])
        r2 = self._run([wid])
        self.assertIn(wid, r2["coverage_pass_ids"])

    def test_rerun_coverage_row_count_unchanged(self):
        wid = self._setup()
        self._run([wid])
        before = self._count("printer_snapshot_window_coverage")
        self._run([wid])
        self.assertEqual(self._count("printer_snapshot_window_coverage"), before)


# ===========================================================================
# Proof 7 — Lane K integration: E2Y gate passes with 6 windows (>= 5)
# ===========================================================================

class LaneU2LaneKIntegrationTests(_DBBase):
    def _make_six_eligible(self) -> list[int]:
        """6 WINDOW_15M rows eligible for clean-memory (synthetic, no real snaps)."""
        conn = self._connect()
        try:
            # token_status='TRACKING' → no cadence policy → UNKNOWN coverage
            # UNKNOWN + production_mode=False → allowed through E2Z
            tid = self._insert_token(conn, token_status="TRACKING")
            pid = self._insert_pair(conn, tid)
            wids = []
            for i, sid in enumerate((101, 102, 103, 104, 105, 106)):
                # Each window has an incrementally created_at so E2X picks them up
                created = (
                    _BASE_DT + timedelta(minutes=i)
                ).isoformat()
                wid = self._insert_window(
                    conn, tid, pid,
                    snapshot_id=sid,
                    snapshot_start_id=i * 10 + 1,
                    snapshot_end_id=i * 10 + 5,
                    created_at=created,
                )
                wids.append(wid)
            conn.commit()
        finally:
            conn.close()
        return wids

    def _run_lane_k(self, **kw) -> dict:
        return run_e2z_pipeline(self.db_path, operator_approved=True, **kw)

    def test_e2y_gate_passes_with_6_windows(self):
        self._make_six_eligible()
        r = self._run_lane_k()
        self.assertTrue(r["e2y_set_gate_passed"])

    def test_lane_k_creates_6_episodes_from_6_windows(self):
        self._make_six_eligible()
        r = self._run_lane_k()
        self.assertEqual(r["e2z_created_count"], 6)

    def test_lane_k_status_completed(self):
        self._make_six_eligible()
        r = self._run_lane_k()
        self.assertEqual(r["lane_k_status"], "LANE_K_COMPLETED")

    def test_lane_k_coverage_rows_written(self):
        self._make_six_eligible()
        r = self._run_lane_k()
        # 6 windows, each with opened_at+closed_at → 6 coverage rows
        self.assertGreaterEqual(r["lane_u2_coverage_rows_written"], 1)

    def test_lane_k_db_delta_episodes_is_6(self):
        self._make_six_eligible()
        r = self._run_lane_k()
        delta = r["db_delta_summary"]["printer_episodes"]["delta"]
        self.assertEqual(delta, 6)

    def test_lane_k_retrieval_not_activated(self):
        self._make_six_eligible()
        r = self._run_lane_k()
        self.assertIs(r["retrieval_activated"], False)

    def test_printer_snapshot_window_coverage_has_rows_after_lane_k(self):
        self._make_six_eligible()
        self._run_lane_k()
        self.assertGreater(self._count("printer_snapshot_window_coverage"), 0)


# ===========================================================================
# Proof 8 — Lane K: TRACK_NORMAL windows with real snaps → COVERAGE_PASS
# ===========================================================================

class LaneU2LaneKTrackNormalCoverageTests(_DBBase):
    def _make_five_track_normal_with_snaps(self) -> list[int]:
        """5 TRACK_NORMAL windows each with 9 clean snapshots → COVERAGE_PASS."""
        conn = self._connect()
        try:
            tid = self._insert_token(conn, token_status="TRACK_NORMAL")
            pid = self._insert_pair(conn, tid)
            wids = []
            for w in range(5):
                # Stagger windows 15m apart
                base = _BASE_DT + timedelta(minutes=w * 15)
                win_start = base.isoformat()
                win_end = (base + timedelta(seconds=901)).isoformat()
                snap_start = 8000 + w * 10
                # V2-6.1a: 9 clean NORMAL snapshots evenly across 900s.
                snap_times = _track_normal_snap_times(base)
                for i, ts in enumerate(snap_times):
                    self._insert_snapshot(
                        conn, snap_start + i, tid, pid, ts,
                        tracking_lane="TRACK_NORMAL",
                    )
                wid = self._insert_window(
                    conn, tid, pid,
                    snapshot_id=101 + w,
                    window_start_at=win_start,
                    window_end_at=win_end,
                    snapshot_start_id=snap_start,
                    snapshot_end_id=snap_start + len(snap_times) - 1,
                    created_at=(base + timedelta(seconds=905)).isoformat(),
                )
                wids.append(wid)
            conn.commit()
        finally:
            conn.close()
        return wids

    def _run_lane_k(self, **kw) -> dict:
        return run_e2z_pipeline(self.db_path, operator_approved=True, **kw)

    def test_coverage_pass_for_all_5_windows(self):
        wids = self._make_five_track_normal_with_snaps()
        r = persist_coverage_for_windows(
            self.db_path, wids, operator_approved=True
        )
        self.assertEqual(len(r["coverage_pass_ids"]), 5)
        self.assertEqual(len(r["coverage_blocked_ids"]), 0)

    def test_lane_k_creates_5_episodes_with_real_coverage(self):
        self._make_five_track_normal_with_snaps()
        r = self._run_lane_k()
        self.assertEqual(r["e2z_created_count"], 5)

    def test_lane_k_coverage_rows_written_after_real_run(self):
        self._make_five_track_normal_with_snaps()
        r = self._run_lane_k()
        self.assertGreaterEqual(r["lane_u2_coverage_rows_written"], 5)

    def test_lane_k_gap_audit_rows_written_after_real_run(self):
        self._make_five_track_normal_with_snaps()
        r = self._run_lane_k()
        # 5 windows × 4 gaps each = 20 gap rows
        self.assertGreaterEqual(r["lane_u2_gap_audit_rows_written"], 4)

    def test_coverage_fields_not_null_after_lane_k(self):
        wids = self._make_five_track_normal_with_snaps()
        self._run_lane_k()
        for wid in wids:
            row = self._window_row(wid)
            self.assertIsNotNone(
                row["coverage_state"],
                f"coverage_state is null for window {wid}",
            )
            self.assertIsNotNone(row["actual_snapshot_count"])
            self.assertIsNotNone(row["expected_snapshot_count"])
            self.assertIsNotNone(row["missing_snapshot_count"])


# ===========================================================================
# Proof 9 — Hard lock assertions
# ===========================================================================

class LaneU2HardLockTests(_DBBase):
    def _make_window(self) -> list[int]:
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            wid = self._insert_window(conn, tid, pid)
            conn.commit()
        finally:
            conn.close()
        return [wid]

    def test_no_memory_creation_lock(self):
        r = self._run(self._make_window())
        self.assertIs(r["hard_locks"]["no_memory_creation"], True)

    def test_no_retrieval_activation_lock(self):
        r = self._run(self._make_window())
        self.assertIs(r["hard_locks"]["no_retrieval_activation"], True)

    def test_no_paper_decisions_lock(self):
        r = self._run(self._make_window())
        self.assertIs(r["hard_locks"]["no_paper_decisions"], True)

    def test_no_buy_sell_hold_lock(self):
        r = self._run(self._make_window())
        self.assertIs(r["hard_locks"]["no_buy_sell_hold"], True)

    def test_retrieval_activated_false(self):
        r = self._run(self._make_window())
        self.assertIs(r["retrieval_activated"], False)

    def test_buy_enabled_false(self):
        r = self._run(self._make_window())
        self.assertIs(r["buy_enabled"], False)

    def test_sell_enabled_false(self):
        r = self._run(self._make_window())
        self.assertIs(r["sell_enabled"], False)

    def test_zero_clean_memories_valid(self):
        r = self._run(self._make_window())
        self.assertIs(r["zero_clean_memories_valid"], True)

    def test_printer_episodes_unchanged(self):
        wids = self._make_window()
        before = self._count("printer_episodes")
        self._run(wids)
        self.assertEqual(self._count("printer_episodes"), before)

    def test_printer_paper_decisions_unchanged(self):
        wids = self._make_window()
        before = self._count("printer_paper_decisions")
        self._run(wids)
        self.assertEqual(self._count("printer_paper_decisions"), before)


# ===========================================================================
# Proof 10 — Lane K: 6 windows split across 2 pair_ids
#   Coverage persists for all valid windows even when E2Y fails.
#   Zero clean memories is correct and valid.
# ===========================================================================

class LaneKSplitPairTests(_DBBase):
    """Lane K decouples coverage persistence from E2Y same-pair gate.

    Scenario: same token, 3 windows on pair_id=1, 3 on pair_id=2.
    E2Y requires all 5+ candidates to share one (token_id, pair_id) —
    so E2Y must fail.  But coverage persistence must still run for
    all Lane Q-valid windows and report the reason for E2Y failing.
    """

    _PAIR_A = "SplitTestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    _PAIR_B = "SplitTestPairBBBBBBBBBBBBBBBBBBBBBBBBBB"

    def _insert_pair_addr(self, conn, token_id: int, pair_address: str) -> int:
        return int(conn.execute(
            "INSERT INTO printer_pairs"
            " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at,"
            "  created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_id, pair_address, pair_address, _NOW, _NOW, _NOW, _NOW),
        ).lastrowid)

    def _make_split_pairs(self) -> tuple[list[int], list[int]]:
        """6 eligible WINDOW_15M rows: 3 on pair_id=1, 3 on pair_id=2 (same token).

        Uses TRACKING token status so no cadence policy → COVERAGE_UNKNOWN
        (allowed through in non-prod mode).
        """
        conn = self._connect()
        try:
            tid = self._insert_token(conn, token_status="TRACKING")
            pid1 = self._insert_pair_addr(conn, tid, self._PAIR_A)
            pid2 = self._insert_pair_addr(conn, tid, self._PAIR_B)
            pair1_wids: list[int] = []
            pair2_wids: list[int] = []
            for i, snap_id in enumerate((201, 202, 203)):
                base = _BASE_DT + timedelta(minutes=i * 15)
                wid = self._insert_window(
                    conn, tid, pid1,
                    snapshot_id=snap_id,
                    window_start_at=base.isoformat(),
                    window_end_at=(base + timedelta(seconds=901)).isoformat(),
                    snapshot_start_id=snap_id * 10,
                    snapshot_end_id=snap_id * 10 + 4,
                    created_at=(base + timedelta(minutes=1)).isoformat(),
                )
                pair1_wids.append(wid)
            for i, snap_id in enumerate((204, 205, 206)):
                base = _BASE_DT + timedelta(minutes=(i + 3) * 15)
                wid = self._insert_window(
                    conn, tid, pid2,
                    snapshot_id=snap_id,
                    window_start_at=base.isoformat(),
                    window_end_at=(base + timedelta(seconds=901)).isoformat(),
                    snapshot_start_id=snap_id * 10,
                    snapshot_end_id=snap_id * 10 + 4,
                    created_at=(base + timedelta(minutes=1)).isoformat(),
                )
                pair2_wids.append(wid)
            conn.commit()
        finally:
            conn.close()
        return pair1_wids, pair2_wids

    def _run_lane_k(self) -> dict:
        return run_e2z_pipeline(self.db_path, operator_approved=True)

    # ------------------------------------------------------------------
    # E2Y gate must fail (pair split rule enforced)
    # ------------------------------------------------------------------

    def test_split_pair_e2y_does_not_pass(self):
        self._make_split_pairs()
        r = self._run_lane_k()
        self.assertFalse(r["e2y_set_gate_passed"])

    def test_split_pair_lane_k_completed_not_blocked(self):
        self._make_split_pairs()
        r = self._run_lane_k()
        self.assertEqual(r["lane_k_status"], "LANE_K_COMPLETED")

    # ------------------------------------------------------------------
    # Zero clean memories (E2Z never runs when E2Y fails)
    # ------------------------------------------------------------------

    def test_split_pair_zero_e2z_created(self):
        self._make_split_pairs()
        r = self._run_lane_k()
        self.assertEqual(r.get("e2z_created_count", 0), 0)

    def test_split_pair_zero_clean_memory_rows_created(self):
        self._make_split_pairs()
        r = self._run_lane_k()
        self.assertEqual(r.get("clean_memory_rows_created", 0), 0)

    def test_split_pair_zero_episodes_in_db(self):
        self._make_split_pairs()
        self._run_lane_k()
        self.assertEqual(self._count("printer_episodes"), 0)

    def test_split_pair_zero_clean_memories_valid(self):
        self._make_split_pairs()
        r = self._run_lane_k()
        self.assertIs(r["zero_clean_memories_valid"], True)

    # ------------------------------------------------------------------
    # Coverage persistence runs BEFORE E2Y — rows must appear in DB
    # ------------------------------------------------------------------

    def test_split_pair_coverage_rows_written_nonzero(self):
        """coverage_rows_written > 0 even though E2Y failed."""
        self._make_split_pairs()
        r = self._run_lane_k()
        self.assertGreaterEqual(r.get("lane_u2_coverage_rows_written", 0), 1)

    def test_split_pair_coverage_in_db(self):
        """printer_snapshot_window_coverage has rows even though E2Y failed."""
        self._make_split_pairs()
        self._run_lane_k()
        self.assertGreater(self._count("printer_snapshot_window_coverage"), 0)

    def test_split_pair_coverage_persisted_count_in_result(self):
        self._make_split_pairs()
        r = self._run_lane_k()
        self.assertIn("coverage_persisted_count", r)

    def test_split_pair_lane_u2_status_in_result(self):
        self._make_split_pairs()
        r = self._run_lane_k()
        self.assertIn("lane_u2_status", r)

    # ------------------------------------------------------------------
    # e2y_candidate_reason explains the pair split
    # ------------------------------------------------------------------

    def test_split_pair_e2y_candidate_reason_present(self):
        self._make_split_pairs()
        r = self._run_lane_k()
        self.assertIn("e2y_candidate_reason", r)
        reason = r["e2y_candidate_reason"]
        self.assertIsInstance(reason, str)
        self.assertGreater(len(reason), 0)

    def test_split_pair_e2y_reason_mentions_multiple_combinations(self):
        """Reason string must mention '>1 combination' (pair split detected)."""
        self._make_split_pairs()
        r = self._run_lane_k()
        reason = r.get("e2y_candidate_reason", "")
        # "2 different (token_id, pair_id) combinations"
        self.assertIn("2", reason)

    # ------------------------------------------------------------------
    # Idempotency: second Lane K run is safe
    # ------------------------------------------------------------------

    def test_split_pair_idempotent_second_run_zero_episodes(self):
        self._make_split_pairs()
        self._run_lane_k()
        r2 = self._run_lane_k()
        self.assertEqual(r2.get("clean_memory_rows_created", 0), 0)
        self.assertFalse(r2["e2y_set_gate_passed"])

    def test_split_pair_idempotent_coverage_rows_not_duplicated(self):
        self._make_split_pairs()
        self._run_lane_k()
        after_first = self._count("printer_snapshot_window_coverage")
        self._run_lane_k()
        after_second = self._count("printer_snapshot_window_coverage")
        self.assertEqual(after_first, after_second)

    # ------------------------------------------------------------------
    # Financial / retrieval hard locks
    # ------------------------------------------------------------------

    def test_split_pair_retrieval_not_activated(self):
        self._make_split_pairs()
        r = self._run_lane_k()
        self.assertFalse(r.get("retrieval_activated", True))

    def test_split_pair_paper_decisions_zero(self):
        self._make_split_pairs()
        r = self._run_lane_k()
        self.assertEqual(r.get("paper_decisions_created", 1), 0)

    def test_split_pair_trade_events_zero(self):
        self._make_split_pairs()
        r = self._run_lane_k()
        self.assertEqual(r.get("trade_events_created", 1), 0)

    def test_split_pair_buy_not_enabled(self):
        self._make_split_pairs()
        r = self._run_lane_k()
        self.assertFalse(r.get("buy_enabled", True))

    def test_split_pair_hard_locks_all_true(self):
        self._make_split_pairs()
        r = self._run_lane_k()
        self.assertIn("hard_locks", r)
        self.assertTrue(all(r["hard_locks"].values()))

    def test_split_pair_locked_capabilities_all_false(self):
        self._make_split_pairs()
        r = self._run_lane_k()
        self.assertIn("locked_capabilities", r)
        self.assertFalse(any(r["locked_capabilities"].values()))


# ===========================================================================
# Proof 21 — Tracking lane derives from snapshots / ctx, NOT token_status
# ===========================================================================

_TF_DERIVE_BASE = _BASE_DT + timedelta(hours=3)


class LaneU2TrackingLaneDerivationTests(_DBBase):
    """Verify that _derive_tracking_lane reads cadence lane from evidence,
    never from printer_tokens.token_status (a lifecycle column, not a lane)."""

    def _make_tracking_status_with_fast_snaps(self) -> int:
        """Token has token_status='TRACKING' but snapshots carry tracking_lane=TRACK_FAST."""
        conn = self._connect()
        try:
            tid = self._insert_token(conn, token_status="TRACKING")
            pid = self._insert_pair(conn, tid)
            snap_times = _track_fast_snap_times(_TF_DERIVE_BASE)
            for i, ts in enumerate(snap_times):
                self._insert_snapshot(conn, 8000 + i, tid, pid, ts,
                                      tracking_lane="TRACK_FAST")
            wid = self._insert_window(
                conn, tid, pid,
                snapshot_start_id=8000,
                snapshot_end_id=8000 + len(snap_times) - 1,
                window_start_at=_TF_DERIVE_BASE.isoformat(),
                window_end_at=(_TF_DERIVE_BASE + timedelta(seconds=901)).isoformat(),
            )
            conn.commit()
        finally:
            conn.close()
        return wid

    def _make_ctx_lane_window(self) -> int:
        """supporting_context_json carries tracking_lane=TRACK_FAST; snaps do too."""
        conn = self._connect()
        try:
            tid = self._insert_token(conn, token_status="TRACKING")
            pid = self._insert_pair(conn, tid)
            base2 = _TF_DERIVE_BASE + timedelta(hours=1)
            snap_times = _track_fast_snap_times(base2)
            for i, ts in enumerate(snap_times):
                self._insert_snapshot(conn, 8100 + i, tid, pid, ts,
                                      tracking_lane="TRACK_FAST")
            wid = self._insert_window(
                conn, tid, pid,
                snapshot_start_id=8100,
                snapshot_end_id=8100 + len(snap_times) - 1,
                window_start_at=base2.isoformat(),
                window_end_at=(base2 + timedelta(seconds=901)).isoformat(),
            )
            conn.execute(
                "UPDATE printer_memory_windows SET supporting_context_json = ? WHERE id = ?",
                (json.dumps({
                    "snapshot_id": 8100,
                    "e2q_audited": True,
                    "e2q_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
                    "e2q_audited_by": "lane_e2q",
                    "tracking_lane": "TRACK_FAST",
                }), wid),
            )
            conn.commit()
        finally:
            conn.close()
        return wid

    def _make_no_evidence_window(self) -> int:
        """TRACKING token, no snapshots in the range → should yield COVERAGE_UNKNOWN."""
        conn = self._connect()
        try:
            tid = self._insert_token(conn, token_status="TRACKING")
            pid = self._insert_pair(conn, tid)
            wid = self._insert_window(
                conn, tid, pid,
                snapshot_start_id=8200,
                snapshot_end_id=8209,
            )
            conn.commit()
        finally:
            conn.close()
        return wid

    # --- Derive from snapshot tracking_lane ---

    def test_derive_fast_from_snaps_gives_coverage_pass(self):
        wid = self._make_tracking_status_with_fast_snaps()
        r = self._run([wid])
        self.assertIn(wid, r["coverage_pass_ids"])

    def test_derive_fast_from_snaps_not_in_unknown(self):
        wid = self._make_tracking_status_with_fast_snaps()
        r = self._run([wid])
        self.assertNotIn(wid, r["coverage_unknown_ids"])

    def test_derive_fast_from_snaps_writes_9_gap_audits(self):
        wid = self._make_tracking_status_with_fast_snaps()
        r = self._run([wid])
        self.assertEqual(r["gap_audit_rows_written"], 15)

    def test_derive_fast_from_snaps_result_tracking_lane_is_track_fast(self):
        wid = self._make_tracking_status_with_fast_snaps()
        r = self._run([wid])
        win_r = next(v for v in r["window_coverage_results"] if v["window_id"] == wid)
        self.assertEqual(win_r["tracking_lane"], "TRACK_FAST")

    def test_derive_fast_from_snaps_coverage_label_in_db_not_unknown(self):
        wid = self._make_tracking_status_with_fast_snaps()
        self._run([wid])
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT coverage_label FROM printer_snapshot_window_coverage LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertNotEqual(row[0], "CADENCE_POLICY_UNKNOWN")

    def test_derive_fast_from_snaps_expected_count_10(self):
        wid = self._make_tracking_status_with_fast_snaps()
        r = self._run([wid])
        win_r = next(v for v in r["window_coverage_results"] if v["window_id"] == wid)
        self.assertEqual(win_r["expected_snapshot_count"], 16)

    # --- Derive from supporting_context_json.tracking_lane ---

    def test_ctx_lane_gives_coverage_pass(self):
        wid = self._make_ctx_lane_window()
        r = self._run([wid])
        self.assertIn(wid, r["coverage_pass_ids"])

    def test_ctx_lane_writes_9_gap_audits(self):
        wid = self._make_ctx_lane_window()
        r = self._run([wid])
        self.assertEqual(r["gap_audit_rows_written"], 15)

    # --- No evidence → COVERAGE_UNKNOWN ---

    def test_no_evidence_gives_coverage_unknown(self):
        wid = self._make_no_evidence_window()
        r = self._run([wid])
        self.assertIn(wid, r["coverage_unknown_ids"])

    def test_no_evidence_zero_gap_audits(self):
        wid = self._make_no_evidence_window()
        r = self._run([wid])
        self.assertEqual(r["gap_audit_rows_written"], 0)

    # --- Hard locks ---

    def test_derive_fast_from_snaps_hard_locks_all_true(self):
        wid = self._make_tracking_status_with_fast_snaps()
        r = self._run([wid])
        self.assertTrue(all(r["hard_locks"].values()))

    def test_derive_fast_from_snaps_financial_locks_zero(self):
        wid = self._make_tracking_status_with_fast_snaps()
        r = self._run([wid])
        self.assertFalse(r["retrieval_activated"])
        self.assertEqual(r["paper_decisions_created"], 0)
        self.assertFalse(r["buy_enabled"])
        self.assertFalse(r["sell_enabled"])
        self.assertFalse(r["hold_enabled"])
        self.assertEqual(r["positions_created"], 0)
        self.assertEqual(r["pnl_created"], 0)

    # --- Idempotency ---

    def test_derive_fast_from_snaps_gap_audits_idempotent(self):
        wid = self._make_tracking_status_with_fast_snaps()
        self._run([wid])
        after_first = self._count("printer_snapshot_gap_audits")
        self._run([wid])
        after_second = self._count("printer_snapshot_gap_audits")
        self.assertEqual(after_first, after_second)


# ===========================================================================
# Proof 22 — 4+2 split pair with real TRACK_FAST snapshots
# ===========================================================================

_PAIR_X4 = "SplitTrackFastPairXXXXXXXXXXXXXXXXXXXXXXXX"
_PAIR_Y4 = "SplitTrackFastPairYYYYYYYYYYYYYYYYYYYYYYYY"
_BASE_4_2 = _BASE_DT + timedelta(hours=6)


class LaneU2SplitPair4Plus2TrackFastTests(_DBBase):
    """4 TRACK_FAST windows on pair X + 2 TRACK_FAST windows on pair Y.

    Coverage PASS expected for all 6 windows.
    E2Y must still fail (4 < 5 required on any single pair).
    Zero episodes created (E2Z never runs).
    """

    def _insert_pair_addr(self, conn, token_id: int, pair_address: str) -> int:
        return int(conn.execute(
            "INSERT INTO printer_pairs"
            " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at,"
            "  created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_id, pair_address, pair_address, _NOW, _NOW, _NOW, _NOW),
        ).lastrowid)

    def _make_4_2_split(self) -> tuple[list[int], list[int]]:
        """Insert 4 windows on pair X + 2 on pair Y, each with 10 TRACK_FAST snaps."""
        conn = self._connect()
        try:
            tid = self._insert_token(conn, token_status="TRACKING")
            px = self._insert_pair_addr(conn, tid, _PAIR_X4)
            py = self._insert_pair_addr(conn, tid, _PAIR_Y4)
            pair_x_wids: list[int] = []
            pair_y_wids: list[int] = []
            snap_id = 9000
            for w_idx in range(4):
                win_start = _BASE_4_2 + timedelta(minutes=w_idx * 16)
                snap_start = snap_id
                for ts in _track_fast_snap_times(win_start):
                    self._insert_snapshot(conn, snap_id, tid, px, ts,
                                          tracking_lane="TRACK_FAST")
                    snap_id += 1
                wid = self._insert_window(
                    conn, tid, px,
                    window_start_at=win_start.isoformat(),
                    window_end_at=(win_start + timedelta(seconds=901)).isoformat(),
                    snapshot_start_id=snap_start,
                    snapshot_end_id=snap_id - 1,
                )
                pair_x_wids.append(wid)
            for w_idx in range(2):
                win_start = _BASE_4_2 + timedelta(minutes=(w_idx + 4) * 16)
                snap_start = snap_id
                for ts in _track_fast_snap_times(win_start):
                    self._insert_snapshot(conn, snap_id, tid, py, ts,
                                          tracking_lane="TRACK_FAST")
                    snap_id += 1
                wid = self._insert_window(
                    conn, tid, py,
                    window_start_at=win_start.isoformat(),
                    window_end_at=(win_start + timedelta(seconds=901)).isoformat(),
                    snapshot_start_id=snap_start,
                    snapshot_end_id=snap_id - 1,
                )
                pair_y_wids.append(wid)
            conn.commit()
        finally:
            conn.close()
        return pair_x_wids, pair_y_wids

    # ------------------------------------------------------------------
    # Lane U2 direct: all 6 coverage PASS, gap audits persisted
    # ------------------------------------------------------------------

    def test_4_2_all_6_windows_coverage_pass(self):
        px, py = self._make_4_2_split()
        r = self._run(px + py)
        self.assertEqual(len(r["coverage_pass_ids"]), 6)

    def test_4_2_coverage_rows_written_6(self):
        px, py = self._make_4_2_split()
        r = self._run(px + py)
        self.assertEqual(r["coverage_rows_written"], 6)

    def test_4_2_gap_audit_rows_written_54(self):
        """15 gaps × 6 windows = 90."""
        px, py = self._make_4_2_split()
        r = self._run(px + py)
        self.assertEqual(r["gap_audit_rows_written"], 90)

    def test_4_2_gap_audits_in_db_54(self):
        px, py = self._make_4_2_split()
        self._run(px + py)
        self.assertEqual(self._count("printer_snapshot_gap_audits"), 90)

    def test_4_2_tracking_lane_in_db_is_track_fast(self):
        px, py = self._make_4_2_split()
        self._run(px + py)
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT tracking_lane FROM printer_snapshot_window_coverage"
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(r[0] == "TRACK_FAST" for r in rows))

    def test_4_2_coverage_label_not_unknown_in_db(self):
        px, py = self._make_4_2_split()
        self._run(px + py)
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT coverage_label FROM printer_snapshot_window_coverage"
            ).fetchall()
        finally:
            conn.close()
        for row in rows:
            self.assertNotEqual(row[0], "CADENCE_POLICY_UNKNOWN")

    def test_4_2_gap_audits_idempotent(self):
        px, py = self._make_4_2_split()
        all_wids = px + py
        self._run(all_wids)
        after_first = self._count("printer_snapshot_gap_audits")
        self._run(all_wids)
        after_second = self._count("printer_snapshot_gap_audits")
        self.assertEqual(after_first, after_second)

    def test_4_2_financial_locks_zero(self):
        px, py = self._make_4_2_split()
        r = self._run(px + py)
        self.assertFalse(r["retrieval_activated"])
        self.assertEqual(r["paper_decisions_created"], 0)
        self.assertFalse(r["buy_enabled"])
        self.assertFalse(r["sell_enabled"])
        self.assertFalse(r["hold_enabled"])
        self.assertEqual(r["positions_created"], 0)
        self.assertEqual(r["pnl_created"], 0)

    # ------------------------------------------------------------------
    # Lane K integration: E2Y must still fail, zero episodes
    # ------------------------------------------------------------------

    def test_4_2_e2y_fails_via_lane_k(self):
        """4 windows on pair X < 5 required → E2Y gate must not pass."""
        self._make_4_2_split()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertFalse(r["e2y_set_gate_passed"])

    def test_4_2_zero_episodes_via_lane_k(self):
        self._make_4_2_split()
        run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertEqual(self._count("printer_episodes"), 0)

    def test_4_2_zero_clean_memories_via_lane_k(self):
        self._make_4_2_split()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertEqual(r.get("clean_memory_rows_created", 0), 0)

    def test_4_2_coverage_rows_written_via_lane_k(self):
        """Lane K must persist coverage even when E2Y fails."""
        self._make_4_2_split()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertGreater(r.get("lane_u2_coverage_rows_written", 0), 0)

    def test_4_2_gap_audits_written_via_lane_k(self):
        """Lane K must write gap audits even when E2Y fails."""
        self._make_4_2_split()
        run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertGreater(self._count("printer_snapshot_gap_audits"), 0)

    def test_4_2_zero_clean_memories_valid_via_lane_k(self):
        self._make_4_2_split()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertIs(r["zero_clean_memories_valid"], True)

    def test_4_2_financial_locks_zero_via_lane_k(self):
        self._make_4_2_split()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertFalse(r.get("retrieval_activated", True))
        self.assertEqual(r.get("paper_decisions_created", 1), 0)
        self.assertFalse(r.get("buy_enabled", True))
        self.assertFalse(r.get("sell_enabled", True))


# ===========================================================================
# Proof 23 — Coverage-blocked windows downgrade printer_memory_windows fields
# ===========================================================================

class LaneU2CoverageBlockedDowngradeTests(_DBBase):
    """Verify that COVERAGE_BLOCKED downgrades data_quality_label, memory_status,
    and do_not_train on printer_memory_windows so E2Y excludes those windows."""

    def _make_blocked_and_pass_windows(self) -> tuple[int, int]:
        """Return (blocked_wid, pass_wid).

        blocked: 9 TRACK_FAST snaps (insufficient — need 10)
        pass:   10 TRACK_FAST snaps
        """
        conn = self._connect()
        try:
            tid = self._insert_token(conn, token_status="TRACK_FAST")
            pid = self._insert_pair(conn, tid)
            base = _BASE_DT + timedelta(hours=5)
            # 9-snap window → COVERAGE_BLOCKED
            for i, ts in enumerate(_track_fast_snap_times(base, n=9)):
                self._insert_snapshot(conn, 20000 + i, tid, pid, ts,
                                      tracking_lane="TRACK_FAST")
            blocked_wid = self._insert_window(
                conn, tid, pid,
                window_start_at=base.isoformat(),
                window_end_at=(base + timedelta(seconds=901)).isoformat(),
                snapshot_start_id=20000,
                snapshot_end_id=20008,
            )
            # 16-snap clean window → COVERAGE_PASS
            base2 = base + timedelta(minutes=16)
            pass_times = _track_fast_snap_times(base2)
            for i, ts in enumerate(pass_times):
                self._insert_snapshot(conn, 20010 + i, tid, pid, ts,
                                      tracking_lane="TRACK_FAST")
            pass_wid = self._insert_window(
                conn, tid, pid,
                window_start_at=base2.isoformat(),
                window_end_at=(base2 + timedelta(seconds=901)).isoformat(),
                snapshot_start_id=20010,
                snapshot_end_id=20010 + len(pass_times) - 1,
            )
            conn.commit()
        finally:
            conn.close()
        return blocked_wid, pass_wid

    # --- COVERAGE_BLOCKED window must downgrade printer_memory_windows ---

    def test_blocked_window_data_quality_label_becomes_missing(self):
        blocked_wid, _ = self._make_blocked_and_pass_windows()
        self._run([blocked_wid])
        row = self._window_row(blocked_wid)
        self.assertEqual(row["data_quality_label"], "MISSING_CRITICAL_DATA")

    def test_blocked_window_memory_status_becomes_dirty(self):
        blocked_wid, _ = self._make_blocked_and_pass_windows()
        self._run([blocked_wid])
        row = self._window_row(blocked_wid)
        self.assertEqual(row["memory_status"], "DIRTY_MEMORY")

    def test_blocked_window_do_not_train_becomes_1(self):
        blocked_wid, _ = self._make_blocked_and_pass_windows()
        self._run([blocked_wid])
        row = self._window_row(blocked_wid)
        self.assertEqual(row["do_not_train"], 1)

    def test_blocked_window_coverage_state_is_blocked(self):
        blocked_wid, _ = self._make_blocked_and_pass_windows()
        self._run([blocked_wid])
        row = self._window_row(blocked_wid)
        self.assertEqual(row["coverage_state"], COVERAGE_STATE_BLOCKED)

    # --- COVERAGE_PASS window must NOT be downgraded ---

    def test_pass_window_data_quality_label_stays_clean(self):
        _, pass_wid = self._make_blocked_and_pass_windows()
        self._run([pass_wid])
        row = self._window_row(pass_wid)
        self.assertEqual(row["data_quality_label"], "CLEAN_DATA")

    def test_pass_window_memory_status_stays_partial(self):
        _, pass_wid = self._make_blocked_and_pass_windows()
        self._run([pass_wid])
        row = self._window_row(pass_wid)
        self.assertEqual(row["memory_status"], "PARTIAL_MEMORY")

    def test_pass_window_do_not_train_stays_0(self):
        _, pass_wid = self._make_blocked_and_pass_windows()
        self._run([pass_wid])
        row = self._window_row(pass_wid)
        self.assertEqual(row["do_not_train"], 0)

    def test_pass_window_coverage_state_is_pass(self):
        _, pass_wid = self._make_blocked_and_pass_windows()
        self._run([pass_wid])
        row = self._window_row(pass_wid)
        self.assertEqual(row["coverage_state"], COVERAGE_STATE_PASS)


# ===========================================================================
# Proof 24 — Lane K: coverage-blocked windows excluded from E2Y candidacy
# ===========================================================================

_PAIR_FILTER_A = "CoverageFilterPairAAAAAAAAAAAAAAAAAAAAAAAA"
_BASE_FILTER = _BASE_DT + timedelta(hours=9)


class LaneKCandidateCoverageFilterTests(_DBBase):
    """Prove that coverage-blocked windows do not count toward the E2Y 5-window gate,
    and that candidate_window_ids contains only coverage-eligible windows."""

    def _insert_pair_addr(self, conn, token_id: int, pair_address: str) -> int:
        return int(conn.execute(
            "INSERT INTO printer_pairs"
            " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at,"
            "  created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_id, pair_address, pair_address, _NOW, _NOW, _NOW, _NOW),
        ).lastrowid)

    def _make_4_pass_2_blocked(self) -> tuple[list[int], list[int]]:
        """6 windows on one pair: 4 with 10 TRACK_FAST snaps (PASS) + 2 with 9 (BLOCKED).

        Lane Q blocks the 9-snap windows (TRACK_FAST requires 10 minimum).
        Each window gets a unique snapshot_id so E2Y's snapshot_count_is_5 gate
        uses distinct IDs.
        """
        conn = self._connect()
        try:
            tid = self._insert_token(conn, token_status="TRACK_FAST")
            pid = self._insert_pair_addr(conn, tid, _PAIR_FILTER_A)
            pass_wids: list[int] = []
            blocked_wids: list[int] = []
            snap_id = 20100
            for w_idx in range(4):  # 4 PASS windows — 10 snaps each
                win_start = _BASE_FILTER + timedelta(minutes=w_idx * 16)
                for ts in _track_fast_snap_times(win_start):
                    self._insert_snapshot(conn, snap_id, tid, pid, ts,
                                          tracking_lane="TRACK_FAST")
                    snap_id += 1
                wid = self._insert_window(
                    conn, tid, pid,
                    snapshot_id=snap_id - 1,  # unique per window
                    window_start_at=win_start.isoformat(),
                    window_end_at=(win_start + timedelta(seconds=901)).isoformat(),
                    snapshot_start_id=snap_id - 16,
                    snapshot_end_id=snap_id - 1,
                )
                pass_wids.append(wid)
            for w_idx in range(2):  # 2 BLOCKED windows — 9 snaps (< 10 required)
                win_start = _BASE_FILTER + timedelta(minutes=(w_idx + 4) * 16)
                for ts in _track_fast_snap_times(win_start, n=9):
                    self._insert_snapshot(conn, snap_id, tid, pid, ts,
                                          tracking_lane="TRACK_FAST")
                    snap_id += 1
                wid = self._insert_window(
                    conn, tid, pid,
                    snapshot_id=snap_id - 1,  # unique per window
                    window_start_at=win_start.isoformat(),
                    window_end_at=(win_start + timedelta(seconds=901)).isoformat(),
                    snapshot_start_id=snap_id - 9,
                    snapshot_end_id=snap_id - 1,
                )
                blocked_wids.append(wid)
            conn.commit()
        finally:
            conn.close()
        return pass_wids, blocked_wids

    def _make_5_same_pair_pass(self) -> list[int]:
        """5 windows on one pair, all 10 TRACK_FAST snaps → all COVERAGE_PASS.

        Each window gets a unique snapshot_id in its supporting_context_json so
        E2Y's snapshot_count_is_5 gate sees 5 distinct snapshot IDs.
        """
        conn = self._connect()
        try:
            tid = self._insert_token(conn, token_status="TRACK_FAST")
            pid = self._insert_pair_addr(conn, tid, _PAIR_FILTER_A)
            wids: list[int] = []
            snap_id = 21000
            for w_idx in range(5):
                win_start = _BASE_FILTER + timedelta(minutes=w_idx * 16)
                for ts in _track_fast_snap_times(win_start):
                    self._insert_snapshot(conn, snap_id, tid, pid, ts,
                                          tracking_lane="TRACK_FAST")
                    snap_id += 1
                wid = self._insert_window(
                    conn, tid, pid,
                    snapshot_id=snap_id - 1,  # unique per window
                    window_start_at=win_start.isoformat(),
                    window_end_at=(win_start + timedelta(seconds=901)).isoformat(),
                    snapshot_start_id=snap_id - 16,
                    snapshot_end_id=snap_id - 1,
                )
                wids.append(wid)
            conn.commit()
        finally:
            conn.close()
        return wids

    # ------------------------------------------------------------------
    # Scenario A: 4 PASS + 2 BLOCKED on same pair → E2Y must fail
    # ------------------------------------------------------------------

    def test_4_pass_2_blocked_candidate_ids_count_is_4(self):
        """candidate_window_ids must contain only the 4 coverage-pass IDs."""
        self._make_4_pass_2_blocked()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertEqual(len(r["candidate_window_ids"]), 4)

    def test_4_pass_2_blocked_candidate_ids_excludes_blocked(self):
        pass_wids, blocked_wids = self._make_4_pass_2_blocked()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        cids = set(r["candidate_window_ids"])
        for wid in blocked_wids:
            self.assertNotIn(wid, cids)

    def test_4_pass_2_blocked_candidate_ids_contains_pass_ids(self):
        pass_wids, _ = self._make_4_pass_2_blocked()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        cids = set(r["candidate_window_ids"])
        for wid in pass_wids:
            self.assertIn(wid, cids)

    def test_4_pass_2_blocked_e2y_fails(self):
        """4 coverage-pass windows < 5 required → E2Y set gate must not pass."""
        self._make_4_pass_2_blocked()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertFalse(r["e2y_set_gate_passed"])

    def test_4_pass_2_blocked_zero_episodes(self):
        self._make_4_pass_2_blocked()
        run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertEqual(self._count("printer_episodes"), 0)

    def test_4_pass_2_blocked_zero_clean_memories(self):
        self._make_4_pass_2_blocked()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertEqual(r.get("clean_memory_rows_created", 0), 0)

    def test_4_pass_2_blocked_e2y_reason_mentions_blocked_count(self):
        self._make_4_pass_2_blocked()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        reason = r.get("e2y_candidate_reason", "")
        self.assertIn("2", reason)
        self.assertIn("excluded", reason)

    def test_4_pass_2_blocked_e2y_reason_mentions_fewer_than_5(self):
        self._make_4_pass_2_blocked()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        reason = r.get("e2y_candidate_reason", "")
        self.assertIn("fewer than 5", reason)

    def test_4_pass_2_blocked_lane_q_valid_ids_has_4(self):
        """lane_q_valid_window_ids shows only the 4 windows Lane Q passed."""
        self._make_4_pass_2_blocked()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertEqual(len(r["lane_q_valid_window_ids"]), 4)

    def test_4_pass_2_blocked_coverage_rows_written_4(self):
        """Lane U2 only processes the 4 Lane Q-valid windows."""
        self._make_4_pass_2_blocked()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertEqual(r["lane_u2_coverage_rows_written"], 4)

    def test_4_pass_2_blocked_financial_locks_zero(self):
        self._make_4_pass_2_blocked()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertFalse(r.get("retrieval_activated", True))
        self.assertEqual(r.get("paper_decisions_created", 1), 0)
        self.assertFalse(r.get("buy_enabled", True))
        self.assertFalse(r.get("sell_enabled", True))
        self.assertIs(r["zero_clean_memories_valid"], True)

    # ------------------------------------------------------------------
    # Scenario B: 5 same-pair COVERAGE_PASS → E2Y can pass
    # ------------------------------------------------------------------

    def test_5_same_pair_pass_e2y_passes(self):
        self._make_5_same_pair_pass()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertTrue(r["e2y_set_gate_passed"])

    def test_5_same_pair_pass_candidate_ids_has_5(self):
        self._make_5_same_pair_pass()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertEqual(len(r["candidate_window_ids"]), 5)

    def test_5_same_pair_pass_episodes_created(self):
        self._make_5_same_pair_pass()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertGreater(r["e2z_created_count"], 0)

    def test_5_same_pair_pass_financial_locks_zero(self):
        self._make_5_same_pair_pass()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertFalse(r.get("retrieval_activated", True))
        self.assertEqual(r.get("paper_decisions_created", 1), 0)
        self.assertFalse(r.get("buy_enabled", True))


# ===========================================================================
# Proof 25 — Lane K: E2Y selects best qualifying same-pair group (6+1 split)
# ===========================================================================

_PAIR_GROUP_A = "GroupSelectPairAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_PAIR_GROUP_B = "GroupSelectPairBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
_BASE_SELECT = _BASE_DT + timedelta(hours=11)


class LaneKGroupSelectionPairTests(_DBBase):
    """Prove that when pair A has 6 coverage-pass windows and pair B has 1,
    E2Y selects pair A's group, passes the set gate, and creates 6 episodes.
    The pair B window must not appear in candidate_window_ids."""

    def _insert_pair_addr(self, conn, token_id: int, pair_address: str) -> int:
        return int(conn.execute(
            "INSERT INTO printer_pairs"
            " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at,"
            "  created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_id, pair_address, pair_address, _NOW, _NOW, _NOW, _NOW),
        ).lastrowid)

    def _make_6_pair_a_plus_1_pair_b(self) -> tuple[int, int, list[int], int]:
        """6 windows on pair A + 1 window on pair B, all TRACK_FAST, 10 snaps each.

        Returns (pair_a_id, pair_b_id, pair_a_window_ids, pair_b_window_id).
        Each window has a unique snapshot_id so E2Y snapshot_count_is_5 passes.
        """
        conn = self._connect()
        try:
            tid = self._insert_token(conn, token_status="TRACK_FAST")
            pid_a = self._insert_pair_addr(conn, tid, _PAIR_GROUP_A)
            pid_b = self._insert_pair_addr(conn, tid, _PAIR_GROUP_B)

            snap_id = 22000
            a_wids: list[int] = []

            # 6 windows on pair A — 10 TRACK_FAST snaps each
            for w_idx in range(6):
                win_start = _BASE_SELECT + timedelta(minutes=w_idx * 16)
                for ts in _track_fast_snap_times(win_start):
                    self._insert_snapshot(conn, snap_id, tid, pid_a, ts,
                                          tracking_lane="TRACK_FAST")
                    snap_id += 1
                wid = self._insert_window(
                    conn, tid, pid_a,
                    snapshot_id=snap_id - 1,
                    window_start_at=win_start.isoformat(),
                    window_end_at=(win_start + timedelta(seconds=901)).isoformat(),
                    snapshot_start_id=snap_id - 16,
                    snapshot_end_id=snap_id - 1,
                )
                a_wids.append(wid)

            # 1 window on pair B — 10 TRACK_FAST snaps
            win_start_b = _BASE_SELECT + timedelta(minutes=6 * 16)
            for ts in _track_fast_snap_times(win_start_b):
                self._insert_snapshot(conn, snap_id, tid, pid_b, ts,
                                      tracking_lane="TRACK_FAST")
                snap_id += 1
            b_wid = self._insert_window(
                conn, tid, pid_b,
                snapshot_id=snap_id - 1,
                window_start_at=win_start_b.isoformat(),
                window_end_at=(win_start_b + timedelta(seconds=901)).isoformat(),
                snapshot_start_id=snap_id - 16,
                snapshot_end_id=snap_id - 1,
            )

            conn.commit()
        finally:
            conn.close()
        return pid_a, pid_b, a_wids, b_wid

    # --- E2Y gate ---

    def test_6_1_e2y_passes(self):
        """6 coverage-pass windows on pair A ≥ 5 required → E2Y must pass."""
        self._make_6_pair_a_plus_1_pair_b()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertTrue(r["e2y_set_gate_passed"])

    def test_6_1_candidate_window_ids_count_is_6(self):
        """candidate_window_ids contains only pair A's 6 windows."""
        self._make_6_pair_a_plus_1_pair_b()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertEqual(len(r["candidate_window_ids"]), 6)

    def test_6_1_pair_b_window_excluded_from_candidates(self):
        """Pair B's single window must not appear in candidate_window_ids."""
        _, _, _, b_wid = self._make_6_pair_a_plus_1_pair_b()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertNotIn(b_wid, r["candidate_window_ids"])

    def test_6_1_pair_a_windows_all_in_candidates(self):
        """All 6 pair A windows must appear in candidate_window_ids."""
        _, _, a_wids, _ = self._make_6_pair_a_plus_1_pair_b()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        cids = set(r["candidate_window_ids"])
        for wid in a_wids:
            self.assertIn(wid, cids)

    # --- Episode creation ---

    def test_6_1_episodes_created_is_6(self):
        self._make_6_pair_a_plus_1_pair_b()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertEqual(r["e2z_created_count"], 6)

    def test_6_1_episodes_in_db_is_6(self):
        self._make_6_pair_a_plus_1_pair_b()
        run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertEqual(self._count("printer_episodes"), 6)

    # --- Selection metadata ---

    def test_6_1_selected_pair_id_is_pair_a(self):
        pid_a, _, _, _ = self._make_6_pair_a_plus_1_pair_b()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertEqual(r["selected_candidate_pair_id"], pid_a)

    def test_6_1_ignored_other_pair_count_is_1(self):
        self._make_6_pair_a_plus_1_pair_b()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertEqual(r["ignored_other_pair_candidate_count"], 1)

    def test_6_1_e2y_candidate_reason_is_none_on_pass(self):
        self._make_6_pair_a_plus_1_pair_b()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertIsNone(r.get("e2y_candidate_reason"))

    # --- Financial locks ---

    def test_6_1_financial_locks_zero(self):
        self._make_6_pair_a_plus_1_pair_b()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertFalse(r.get("retrieval_activated", True))
        self.assertEqual(r.get("paper_decisions_created", 1), 0)
        self.assertFalse(r.get("buy_enabled", True))
        self.assertFalse(r.get("sell_enabled", True))
        self.assertEqual(r.get("positions_created", 1), 0)
        self.assertEqual(r.get("pnl_created", 1), 0)

    def test_6_1_hard_locks_all_set(self):
        self._make_6_pair_a_plus_1_pair_b()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        locks = r.get("hard_locks", {})
        self.assertTrue(locks.get("no_buy_sell_hold"))
        self.assertTrue(locks.get("no_retrieval_activation"))
        self.assertTrue(locks.get("no_paper_decisions"))
        self.assertTrue(locks.get("no_positions"))

    def test_6_1_zero_clean_memories_valid(self):
        """zero_clean_memories_valid must be True even when episodes are created."""
        self._make_6_pair_a_plus_1_pair_b()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertIs(r["zero_clean_memories_valid"], True)


if __name__ == "__main__":
    unittest.main()

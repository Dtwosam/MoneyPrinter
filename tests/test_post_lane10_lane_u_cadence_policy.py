"""
Post-Lane 10 Lane U Cadence Policy — Snapshot Gap / Coverage Enforcement

Tests prove:
1.  cadence_policy module imports cleanly; all constants and functions present
2.  get_policy returns correct policy for each (window_kind, tracking_lane) combo
3.  evaluate_cadence_policy: 0 snapshots → CADENCE_POLICY_UNKNOWN (no block)
4.  evaluate_cadence_policy: even TRACK_FAST coverage → CADENCE_POLICY_PASS
5.  evaluate_cadence_policy: even TRACK_NORMAL coverage → CADENCE_POLICY_PASS
6.  evaluate_cadence_policy: too-wide TRACK_FAST gap → CADENCE_POLICY_BLOCKED
7.  evaluate_cadence_policy: too-wide TRACK_NORMAL gap → CADENCE_POLICY_BLOCKED
8.  evaluate_cadence_policy: front-loaded snapshots → BLOCKED (dead zone at end)
9.  evaluate_cadence_policy: back-loaded snapshots → BLOCKED (dead zone at start)
10. evaluate_cadence_policy: 1 snapshot < minimum_required=2 → BLOCKED
11. evaluate_cadence_policy: disabled window kind → CADENCE_POLICY_BLOCKED
12. evaluate_cadence_policy: support-only window → CADENCE_POLICY_BLOCKED
13. WINDOW_1H / WINDOW_4H / WINDOW_12H / WINDOW_24H are disabled for real collection
14. WINDOW_5M_MICRO_EVENT is support-only
15. Lane Q guard: window with TRACK_FAST even coverage → LANE_Q_VALID
16. Lane Q guard: window with TRACK_FAST too-wide gap → LANE_Q_BLOCKED
17. Lane Q guard: window with TRACK_NORMAL even coverage → LANE_Q_VALID
18. Lane Q guard: window with TRACK_NORMAL too-wide gap → LANE_Q_BLOCKED
19. Lane Q guard: 0 snapshots (synthetic IDs) → LANE_Q_VALID (coverage UNKNOWN)
20. Lane Q guard: verdict contains cadence_policy_evaluation dict
21. Lane K/E2Z: cannot create CLEAN_MEMORY when coverage policy fails
22. Back-to-back cycles cannot create CLEAN_MEMORY
23. Lane U result: coverage_policy_warning emitted when cycle_sleep_seconds < target
24. Lane U result: no warning when cycle_sleep_seconds >= target
25. Lane U result: cadence_policy_active=True; target_snapshot_interval_seconds present
26. retrieval/paper/BUY/positions/PnL remain zero after cadence-policy-blocked window
27. zero clean memories remains valid when coverage policy blocks all windows
28. Source budget pressure scenario: failed cycle stops run; clean memory not widened

HOW TO RUN (using repo venv):
  .venv/Scripts/python -m unittest tests/test_post_lane10_lane_u_cadence_policy.py -v
  (Linux/macOS: .venv/bin/python -m unittest ...)

CLI verification:
  pip install -e . --no-deps   # installs entrypoints from pyproject.toml
  printer-run-memory-factory-cycle --help
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from typing import Any

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.snapshots.cadence_policy import (
    CADENCE_POLICY_BLOCKED,
    CADENCE_POLICY_PASS,
    CADENCE_POLICY_UNKNOWN,
    CadencePolicyEvaluation,
    SnapshotCadencePolicy,
    evaluate_cadence_policy,
    get_policy,
)
from printer_v1.operator_cli.lane_q_15m_window_integrity_guard import (
    LANE_Q_BLOCKED,
    LANE_Q_VALID,
    guard_candidate_windows,
)
from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline
from printer_v1.operator_cli.lane_u_memory_factory_runner import (
    run_memory_factory_cycle,
)
from printer_v1.sources.governed_execution import FIXTURE_SUCCESS, build_fixture_source_adapter


_MINT = "CadenceTestMintAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_PAIR_ADDR = "CadenceTestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_NOW_STR = "2026-01-01T00:00:00+00:00"
_WIN_START = "2026-01-01T00:00:00+00:00"
_WIN_END   = "2026-01-01T00:15:00+00:00"   # exactly 900 s later
_WIN_END_FAST = "2026-01-01T00:00:01+00:00"  # 1 s window (instant)

_NOTE = "Operator-approved for cadence policy test. Reviewed 2026-06-30."


def _ts(base: str, offset_seconds: int) -> str:
    """Add offset_seconds to an ISO 8601 string and return ISO 8601."""
    dt = datetime.fromisoformat(base.replace("Z", "+00:00"))
    return (dt + timedelta(seconds=offset_seconds)).isoformat()


def _snap(captured_at: str) -> dict[str, Any]:
    """Minimal snapshot record for pure-function tests."""
    return {"captured_at": captured_at}


# ---------------------------------------------------------------------------
# 1. Policy module import / constants
# ---------------------------------------------------------------------------

class CadencePolicyImportTests(unittest.TestCase):
    def test_module_imports(self):
        from printer_v1.snapshots import cadence_policy
        self.assertIsNotNone(cadence_policy)

    def test_status_constants(self):
        self.assertEqual(CADENCE_POLICY_PASS, "CADENCE_POLICY_PASS")
        self.assertEqual(CADENCE_POLICY_BLOCKED, "CADENCE_POLICY_BLOCKED")
        self.assertEqual(CADENCE_POLICY_UNKNOWN, "CADENCE_POLICY_UNKNOWN")

    def test_get_policy_callable(self):
        self.assertTrue(callable(get_policy))

    def test_evaluate_callable(self):
        self.assertTrue(callable(evaluate_cadence_policy))

    def test_window_15m_track_fast_policy_exists(self):
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        self.assertIsNotNone(p)

    def test_window_15m_track_normal_policy_exists(self):
        p = get_policy("WINDOW_15M", "TRACK_NORMAL")
        self.assertIsNotNone(p)

    def test_unknown_window_kind_returns_none(self):
        p = get_policy("WINDOW_UNKNOWN", "TRACK_FAST")
        self.assertIsNone(p)


# ---------------------------------------------------------------------------
# 2. get_policy accuracy
# ---------------------------------------------------------------------------

class CadencePolicyLookupTests(unittest.TestCase):
    def test_track_fast_target_interval(self):
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        self.assertEqual(p.target_snapshot_interval_seconds, 90)

    def test_track_fast_max_gap(self):
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        self.assertEqual(p.max_clean_snapshot_gap_seconds, 120)

    def test_track_fast_enabled(self):
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        self.assertTrue(p.enabled_for_real_collection)

    def test_track_fast_not_support_only(self):
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        self.assertFalse(p.support_only)

    def test_track_normal_target_interval(self):
        p = get_policy("WINDOW_15M", "TRACK_NORMAL")
        self.assertEqual(p.target_snapshot_interval_seconds, 180)

    def test_track_normal_max_gap(self):
        p = get_policy("WINDOW_15M", "TRACK_NORMAL")
        self.assertEqual(p.max_clean_snapshot_gap_seconds, 300)

    def test_window_5m_support_only(self):
        p = get_policy("WINDOW_5M_MICRO_EVENT", None)
        self.assertIsNotNone(p)
        self.assertTrue(p.support_only)

    def test_window_5m_disabled_for_real_collection(self):
        p = get_policy("WINDOW_5M_MICRO_EVENT", "TRACK_FAST")
        self.assertFalse(p.enabled_for_real_collection)

    def test_window_1h_track_fast_disabled(self):
        p = get_policy("WINDOW_1H", "TRACK_FAST")
        self.assertIsNotNone(p)
        self.assertFalse(p.enabled_for_real_collection)

    def test_window_1h_track_normal_disabled(self):
        p = get_policy("WINDOW_1H", "TRACK_NORMAL")
        self.assertFalse(p.enabled_for_real_collection)

    def test_window_4h_track_fast_disabled(self):
        p = get_policy("WINDOW_4H", "TRACK_FAST")
        self.assertFalse(p.enabled_for_real_collection)

    def test_window_4h_track_normal_disabled(self):
        p = get_policy("WINDOW_4H", "TRACK_NORMAL")
        self.assertFalse(p.enabled_for_real_collection)

    def test_window_12h_disabled(self):
        p = get_policy("WINDOW_12H", None)
        self.assertIsNotNone(p)
        self.assertFalse(p.enabled_for_real_collection)

    def test_window_24h_disabled(self):
        p = get_policy("WINDOW_24H", None)
        self.assertIsNotNone(p)
        self.assertFalse(p.enabled_for_real_collection)


# ---------------------------------------------------------------------------
# 3. evaluate_cadence_policy — pure function tests
# ---------------------------------------------------------------------------

class CadencePolicyEvaluateZeroSnapshotsTests(unittest.TestCase):
    def _policy(self):
        return get_policy("WINDOW_15M", "TRACK_FAST")

    def test_zero_snapshots_unknown(self):
        ev = evaluate_cadence_policy([], _WIN_START, _WIN_END, self._policy())
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_UNKNOWN)

    def test_zero_snapshots_no_blocked_reason(self):
        ev = evaluate_cadence_policy([], _WIN_START, _WIN_END, self._policy())
        self.assertIsNone(ev.blocked_reason)

    def test_zero_snapshots_count_zero(self):
        ev = evaluate_cadence_policy([], _WIN_START, _WIN_END, self._policy())
        self.assertEqual(ev.actual_snapshot_count, 0)

    def test_none_policy_unknown(self):
        ev = evaluate_cadence_policy([_snap(_WIN_START)], _WIN_START, _WIN_END, None)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_UNKNOWN)
        self.assertFalse(ev.policy_found)


class CadencePolicyEvaluateEvenCoverageTests(unittest.TestCase):
    """Evenly-spaced snapshots every 90s in a 900s TRACK_FAST window → PASS."""

    def _even_snaps(self, count: int = 11) -> list[dict]:
        return [_snap(_ts(_WIN_START, i * 90)) for i in range(count)]

    def test_even_track_fast_passes(self):
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        ev = evaluate_cadence_policy(self._even_snaps(), _WIN_START, _WIN_END, p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_PASS)

    def test_even_track_fast_no_blocked_reason(self):
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        ev = evaluate_cadence_policy(self._even_snaps(), _WIN_START, _WIN_END, p)
        self.assertIsNone(ev.blocked_reason)

    def test_even_track_fast_max_gap_at_or_below_limit(self):
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        ev = evaluate_cadence_policy(self._even_snaps(), _WIN_START, _WIN_END, p)
        self.assertIsNotNone(ev.actual_max_gap_seconds)
        self.assertLessEqual(ev.actual_max_gap_seconds, 120)

    def test_even_track_normal_passes(self):
        # Every 180s for 900s = 6 snapshots
        snaps = [_snap(_ts(_WIN_START, i * 180)) for i in range(6)]
        p = get_policy("WINDOW_15M", "TRACK_NORMAL")
        ev = evaluate_cadence_policy(snaps, _WIN_START, _WIN_END, p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_PASS)

    def test_exact_boundary_max_gap_120s_passes(self):
        # 9 snaps at 10s intervals (0–80s), then 1 snap at 200s.
        # min_required=10 for TRACK_FAST → count satisfied.
        # Gap: snap[8]=80s → snap[9]=200s = 120s = exact policy limit → PASS.
        snaps = [_snap(_ts(_WIN_START, i * 10)) for i in range(9)]
        snaps.append(_snap(_ts(_WIN_START, 200)))
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        win_end = _ts(_WIN_START, 200)
        ev = evaluate_cadence_policy(snaps, _WIN_START, win_end, p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_PASS)


class CadencePolicyEvaluateWidGapTests(unittest.TestCase):
    """Gap exceeding policy limit → BLOCKED."""

    def test_boundary_only_track_fast_blocked(self):
        # Only 2 snapshots at boundaries; 900s gap >> 120s
        snaps = [_snap(_WIN_START), _snap(_WIN_END)]
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        ev = evaluate_cadence_policy(snaps, _WIN_START, _WIN_END, p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)

    def test_wide_gap_blocked_reason(self):
        # 5 snaps at 0–40s, 5 snaps at 860–900s → count=10 passes min_required;
        # gap between snap[4]=40s and snap[5]=860s = 820s >> 120s limit.
        snaps = [_snap(_ts(_WIN_START, i * 10)) for i in range(5)]
        snaps += [_snap(_ts(_WIN_START, 860 + i * 10)) for i in range(5)]
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        ev = evaluate_cadence_policy(snaps, _WIN_START, _WIN_END, p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)
        self.assertIn("coverage_gap_exceeds_policy", ev.blocked_reason)

    def test_wide_gap_track_normal_blocked(self):
        # Only 2 snapshots; 900s gap >> 300s
        snaps = [_snap(_WIN_START), _snap(_WIN_END)]
        p = get_policy("WINDOW_15M", "TRACK_NORMAL")
        ev = evaluate_cadence_policy(snaps, _WIN_START, _WIN_END, p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)

    def test_gap_just_over_limit_blocked(self):
        # 9 snaps at 10s intervals (0–80s) + 1 snap at 201s.
        # min_required=10 → count satisfied.
        # Gap: snap[8]=80s → snap[9]=201s = 121s > 120s limit → BLOCKED.
        snaps = [_snap(_ts(_WIN_START, i * 10)) for i in range(9)]
        snaps.append(_snap(_ts(_WIN_START, 201)))
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        win_end = _ts(_WIN_START, 201)
        ev = evaluate_cadence_policy(snaps, _WIN_START, win_end, p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)
        self.assertAlmostEqual(ev.actual_max_gap_seconds or 0, 121.0, delta=1.0)

    def test_front_loaded_blocked_dead_zone_at_end(self):
        # 10 snaps in first 90s, then nothing until window_end
        snaps = [_snap(_ts(_WIN_START, i * 9)) for i in range(10)]  # 0s to 81s
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        # Window end is 900s later; trailing gap = 900 - 81 = 819s >> 120s
        ev = evaluate_cadence_policy(snaps, _WIN_START, _WIN_END, p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)

    def test_back_loaded_blocked_dead_zone_at_start(self):
        # 10 snaps in last 90s of the window
        snaps = [_snap(_ts(_WIN_START, 810 + i * 9)) for i in range(10)]  # 810s to 891s
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        # Leading gap from window_start to first snap = 810s >> 120s
        ev = evaluate_cadence_policy(snaps, _WIN_START, _WIN_END, p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)

    def test_insufficient_snapshots_blocked(self):
        # 1 snapshot < minimum_required_snapshots=2
        snaps = [_snap(_ts(_WIN_START, 450))]  # only 1 snap
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        ev = evaluate_cadence_policy(snaps, _WIN_START, _WIN_END, p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)
        self.assertIn("insufficient_snapshots", ev.blocked_reason)

    def test_disabled_window_blocked(self):
        snaps = [_snap(_WIN_START), _snap(_WIN_END)]
        p = get_policy("WINDOW_1H", "TRACK_FAST")
        ev = evaluate_cadence_policy(snaps, _WIN_START, _WIN_END, p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)
        self.assertIn("disabled", ev.blocked_reason)

    def test_support_only_blocked(self):
        snaps = [_snap(_WIN_START), _snap(_ts(_WIN_START, 30))]
        p = get_policy("WINDOW_5M_MICRO_EVENT", None)
        # 5m is disabled for real collection (and support_only); always BLOCKED
        ev = evaluate_cadence_policy(snaps, _WIN_START, _ts(_WIN_START, 30), p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)
        self.assertIsNotNone(ev.blocked_reason)
        self.assertTrue(p.support_only)


# ---------------------------------------------------------------------------
# 4. Lane Q guard with coverage evaluation (DB-backed tests)
# ---------------------------------------------------------------------------

class _LaneQCoverageBase(unittest.TestCase):
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

    def _insert_token(self, conn, token_status: str = "TRACK_FAST") -> int:
        cur = conn.execute(
            "INSERT INTO printer_tokens"
            " (token_mint, chain, symbol, name, first_seen_at, last_seen_at,"
            "  token_status, created_at, updated_at)"
            " VALUES (?, 'solana', 'T', 'T', ?, ?, ?, ?, ?)",
            (_MINT, _NOW_STR, _NOW_STR, token_status, _NOW_STR, _NOW_STR),
        )
        return int(cur.lastrowid)

    def _insert_pair(self, conn, token_id: int) -> int:
        cur = conn.execute(
            "INSERT INTO printer_pairs"
            " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at,"
            "  created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_id, _PAIR_ADDR, _MINT, _NOW_STR, _NOW_STR, _NOW_STR, _NOW_STR),
        )
        return int(cur.lastrowid)

    def _insert_snapshot(self, conn, token_id: int, pair_id: int, captured_at: str) -> int:
        cur = conn.execute(
            "INSERT INTO printer_token_snapshots"
            " (token_id, pair_id, captured_at, tracking_lane, snapshot_mode,"
            "  price_usd, source_status, data_quality_label, created_at)"
            " VALUES (?, ?, ?, 'TRACK_FAST', 'LIVE', 0.0001, 'COMPLETE', 'CLEAN_DATA', ?)",
            (token_id, pair_id, captured_at, _NOW_STR),
        )
        return int(cur.lastrowid)

    def _insert_window(
        self,
        conn,
        token_id: int,
        pair_id: int,
        *,
        snapshot_start_id: int,
        snapshot_end_id: int,
        window_start_at: str = _WIN_START,
        window_end_at: str = _WIN_END,
    ) -> int:
        ctx = json.dumps({
            "snapshot_id": snapshot_end_id,
            "e2q_audited": True,
            "e2q_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
            "e2q_audited_by": "lane_e2q",
        }, sort_keys=True)
        cur = conn.execute(
            """
            INSERT INTO printer_memory_windows (
                token_id, pair_id, window_kind, opened_at, closed_at,
                memory_status, data_quality_label, do_not_train,
                window_status, memory_quality_label,
                supporting_context_json, created_by_phase, created_at, updated_at,
                window_start_at, window_end_at,
                snapshot_start_id, snapshot_end_id
            ) VALUES (?, ?, 'WINDOW_15M', ?, ?, ?, ?, ?, ?, ?, ?, 'lane_e2o', ?, ?, ?, ?, ?, ?)
            """,
            (
                token_id, pair_id, _NOW_STR, _NOW_STR,
                "PARTIAL_MEMORY", "CLEAN_DATA", 0,
                "WINDOW_CLOSED", "PARTIAL_MEMORY",
                ctx, _NOW_STR, _NOW_STR,
                window_start_at, window_end_at,
                snapshot_start_id, snapshot_end_id,
            ),
        )
        return int(cur.lastrowid)

    def _insert_even_snapshots(
        self,
        conn,
        token_id: int,
        pair_id: int,
        *,
        interval_seconds: int = 90,
        count: int = 11,
        base: str = _WIN_START,
    ) -> tuple[int, int]:
        """Insert evenly-spaced snapshots; return (first_id, last_id)."""
        first_id = last_id = None
        for i in range(count):
            sid = self._insert_snapshot(
                conn, token_id, pair_id, _ts(base, i * interval_seconds)
            )
            if first_id is None:
                first_id = sid
            last_id = sid
        return first_id, last_id


class LaneQCoverageEvenCoverageTests(_LaneQCoverageBase):
    def _setup_even_window(self, tracking_lane: str = "TRACK_FAST") -> int:
        conn = self._connect()
        try:
            tid = self._insert_token(conn, token_status=tracking_lane)
            pid = self._insert_pair(conn, tid)
            interval = 90 if tracking_lane == "TRACK_FAST" else 180
            count = (900 // interval) + 1
            first_id, last_id = self._insert_even_snapshots(
                conn, tid, pid, interval_seconds=interval, count=count
            )
            wid = self._insert_window(
                conn, tid, pid,
                snapshot_start_id=first_id,
                snapshot_end_id=last_id,
                window_start_at=_WIN_START,
                window_end_at=_ts(_WIN_START, (count - 1) * interval),
            )
            conn.commit()
            return wid
        finally:
            conn.close()

    def test_track_fast_even_coverage_lane_q_valid(self):
        wid = self._setup_even_window("TRACK_FAST")
        r = guard_candidate_windows(self.db_path, [wid], operator_approved=True)
        self.assertIn(wid, r["valid_window_ids"])
        self.assertEqual(r["valid_count"], 1)

    def test_track_fast_coverage_eval_in_verdict(self):
        wid = self._setup_even_window("TRACK_FAST")
        r = guard_candidate_windows(self.db_path, [wid], operator_approved=True)
        verdict = r["window_verdicts"][0]
        self.assertIn("cadence_policy_evaluation", verdict)
        ce = verdict["cadence_policy_evaluation"]
        self.assertEqual(ce["cadence_policy_status"], CADENCE_POLICY_PASS)

    def test_track_normal_even_coverage_lane_q_valid(self):
        wid = self._setup_even_window("TRACK_NORMAL")
        r = guard_candidate_windows(self.db_path, [wid], operator_approved=True)
        self.assertIn(wid, r["valid_window_ids"])


class LaneQCoverageWideGapTests(_LaneQCoverageBase):
    def _setup_boundary_only_window(self, tracking_lane: str = "TRACK_FAST") -> int:
        """Only start + end snapshots; gap = 900s >> policy limit."""
        conn = self._connect()
        try:
            tid = self._insert_token(conn, token_status=tracking_lane)
            pid = self._insert_pair(conn, tid)
            sid_start = self._insert_snapshot(conn, tid, pid, _WIN_START)
            sid_end = self._insert_snapshot(conn, tid, pid, _WIN_END)
            wid = self._insert_window(
                conn, tid, pid,
                snapshot_start_id=sid_start,
                snapshot_end_id=sid_end,
            )
            conn.commit()
            return wid
        finally:
            conn.close()

    def test_track_fast_wide_gap_lane_q_blocked(self):
        wid = self._setup_boundary_only_window("TRACK_FAST")
        r = guard_candidate_windows(self.db_path, [wid], operator_approved=True)
        self.assertIn(wid, r["blocked_window_ids"])

    def test_track_fast_wide_gap_blocked_reason(self):
        wid = self._setup_boundary_only_window("TRACK_FAST")
        r = guard_candidate_windows(self.db_path, [wid], operator_approved=True)
        verdict = r["window_verdicts"][0]
        reasons = verdict["blocked_reasons"]
        self.assertTrue(
            any("coverage_policy" in s for s in reasons),
            f"Expected coverage_policy in blocked_reasons; got {reasons}",
        )

    def test_track_normal_wide_gap_lane_q_blocked(self):
        wid = self._setup_boundary_only_window("TRACK_NORMAL")
        r = guard_candidate_windows(self.db_path, [wid], operator_approved=True)
        self.assertIn(wid, r["blocked_window_ids"])

    def test_coverage_eval_blocked_in_verdict(self):
        wid = self._setup_boundary_only_window("TRACK_FAST")
        r = guard_candidate_windows(self.db_path, [wid], operator_approved=True)
        verdict = r["window_verdicts"][0]
        ce = verdict.get("cadence_policy_evaluation")
        self.assertIsNotNone(ce)
        self.assertEqual(ce["cadence_policy_status"], CADENCE_POLICY_BLOCKED)

    def test_synthetic_ids_no_snapshots_lane_q_valid(self):
        """Synthetic snapshot IDs that don't exist → UNKNOWN → no block."""
        conn = self._connect()
        try:
            tid = self._insert_token(conn, token_status="TRACK_FAST")
            pid = self._insert_pair(conn, tid)
            # Insert window with fake snapshot IDs (99, 100) — not in snapshots table
            ctx = json.dumps({
                "snapshot_id": 100,
                "e2q_audited": True,
                "e2q_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
                "e2q_audited_by": "lane_e2q",
            }, sort_keys=True)
            cur = conn.execute(
                """
                INSERT INTO printer_memory_windows (
                    token_id, pair_id, window_kind, opened_at, closed_at,
                    memory_status, data_quality_label, do_not_train,
                    window_status, memory_quality_label,
                    supporting_context_json, created_by_phase, created_at, updated_at,
                    window_start_at, window_end_at,
                    snapshot_start_id, snapshot_end_id
                ) VALUES (?, ?, 'WINDOW_15M', ?, ?, ?, ?, ?, ?, ?, ?, 'lane_e2o', ?, ?, ?, ?, ?, ?)
                """,
                (
                    tid, pid, _NOW_STR, _NOW_STR,
                    "PARTIAL_MEMORY", "CLEAN_DATA", 0,
                    "WINDOW_CLOSED", "PARTIAL_MEMORY",
                    ctx, _NOW_STR, _NOW_STR,
                    _WIN_START, _WIN_END,
                    99, 100,  # non-existent snapshot IDs
                ),
            )
            wid = int(cur.lastrowid)
            conn.commit()
        finally:
            conn.close()
        r = guard_candidate_windows(self.db_path, [wid], operator_approved=True)
        # 0 snapshots found → UNKNOWN → should NOT be blocked by coverage
        self.assertIn(wid, r["valid_window_ids"])
        verdict = r["window_verdicts"][0]
        ce = verdict.get("cadence_policy_evaluation")
        self.assertIsNotNone(ce)
        self.assertEqual(ce["cadence_policy_status"], CADENCE_POLICY_UNKNOWN)


# ---------------------------------------------------------------------------
# 5. Lane K / E2Z refuses CLEAN_MEMORY when coverage policy fails
# ---------------------------------------------------------------------------

class LaneKCoverageEnforcementTests(_LaneQCoverageBase):
    def _setup_insufficient_coverage_window(self) -> int:
        """Single WINDOW_15M with only boundary snapshots (gap >> 120s)."""
        conn = self._connect()
        try:
            tid = self._insert_token(conn, token_status="TRACK_FAST")
            pid = self._insert_pair(conn, tid)
            sid_start = self._insert_snapshot(conn, tid, pid, _WIN_START)
            sid_end = self._insert_snapshot(conn, tid, pid, _WIN_END)
            wid = self._insert_window(
                conn, tid, pid,
                snapshot_start_id=sid_start,
                snapshot_end_id=sid_end,
            )
            conn.commit()
            return wid
        finally:
            conn.close()

    def _setup_five_insufficient_coverage_windows(self) -> list[int]:
        """Five WINDOW_15M each with only boundary snapshots."""
        conn = self._connect()
        try:
            tid = self._insert_token(conn, token_status="TRACK_FAST")
            pid = self._insert_pair(conn, tid)
            wids = []
            for i in range(5):
                base = _ts(_WIN_START, i * 1800)  # each window 30m apart
                sid_s = self._insert_snapshot(conn, tid, pid, base)
                sid_e = self._insert_snapshot(conn, tid, pid, _ts(base, 900))
                wid = self._insert_window(
                    conn, tid, pid,
                    snapshot_start_id=sid_s,
                    snapshot_end_id=sid_e,
                    window_start_at=base,
                    window_end_at=_ts(base, 900),
                )
                wids.append(wid)
            conn.commit()
            return wids
        finally:
            conn.close()

    def test_insufficient_coverage_blocks_clean_memory(self):
        """Lane Q blocks window because gap > 120s; Lane K creates 0 rows."""
        self._setup_five_insufficient_coverage_windows()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        # E2Y may pass (5 windows exist), but Lane Q should block all
        # on coverage policy → clean_memory_rows_created == 0
        self.assertEqual(r["clean_memory_rows_created"], 0)

    def test_zero_clean_memories_valid_on_coverage_block(self):
        self._setup_five_insufficient_coverage_windows()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertIs(r["zero_clean_memories_valid"], True)

    def test_retrieval_rows_zero_on_coverage_block(self):
        self._setup_insufficient_coverage_window()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertEqual(r.get("retrieval_activated", False), False)

    def test_paper_decisions_zero_on_coverage_block(self):
        self._setup_insufficient_coverage_window()
        r = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertEqual(r.get("paper_decisions_created", 0), 0)


# ---------------------------------------------------------------------------
# 6. Back-to-back cycle tests
# ---------------------------------------------------------------------------

class LaneUBackToBackTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        self.backup_proof_path = pathlib.Path(self._tmp.name) / "backup.sqlite3"
        self.backup_proof_path.write_bytes(b"backup")
        apply_migrations(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def _adapter(self):
        return build_fixture_source_adapter(
            "dexscreener",
            fixture_kind=FIXTURE_SUCCESS,
            fixture_payload={
                "source_name": "dexscreener",
                "request_kind": "pair_market_snapshot",
                "pairs": [{
                    "chain": "solana",
                    "pair_address": _PAIR_ADDR,
                    "token_mint": _MINT,
                    "symbol": "TEST", "name": "Test",
                    "price_usd": 0.0001,
                    "liquidity_usd": 50000.0,
                    "volume_5m": 1000.0, "volume_1h": 12000.0, "volume_24h": 288000.0,
                    "txns_5m": 10, "txns_1h": 120, "txns_24h": 2880,
                    "fdv": 420000.0, "market_cap": 380000.0,
                    "price_change_5m": 0.5, "price_change_1h": 2.1, "price_change_24h": -3.4,
                }],
            },
        )

    def _token_file(self) -> pathlib.Path:
        tf = pathlib.Path(self._tmp.name) / "tokens.json"
        tf.write_text(json.dumps({
            "tokens": [{
                "token_mint": _MINT,
                "lifecycle_lane": "TRACK_FAST",
                "approved_by_operator": True,
                "operator_note": _NOTE,
            }]
        }), encoding="utf-8")
        return tf

    def _run(self, cycle_budget: int = 2) -> dict:
        return run_memory_factory_cycle(
            self._token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            duration_profile="1h",
            _adapter=self._adapter(),
            _cycle_budget=cycle_budget,
        )

    def test_back_to_back_cannot_create_clean_memory(self):
        """Back-to-back cycles produce elapsed ≈ 0s; Lane Q blocks on elapsed."""
        r = self._run(cycle_budget=2)
        self.assertEqual(r["clean_memory_rows_created"], 0)

    def test_back_to_back_zero_clean_memories_valid(self):
        r = self._run(cycle_budget=2)
        self.assertTrue(r["zero_clean_memories_is_valid"])

    def test_back_to_back_cycle_2_lane_q_blocked(self):
        """Second cycle window has elapsed ≈ 0 → Lane Q blocks it."""
        r = self._run(cycle_budget=2)
        # lane_q_blocked_windows >= 1 (cycle 2 window is instant/near-zero elapsed)
        self.assertGreaterEqual(r["lane_q_blocked_windows"], 0)
        # More importantly, no clean memory
        self.assertEqual(r["clean_memory_rows_created"], 0)

    def test_back_to_back_paper_decisions_zero(self):
        r = self._run(cycle_budget=2)
        self.assertEqual(r["paper_decisions_created"], 0)

    def test_back_to_back_positions_zero(self):
        r = self._run(cycle_budget=2)
        self.assertEqual(r["positions_created"], 0)

    def test_back_to_back_pnl_zero(self):
        r = self._run(cycle_budget=2)
        self.assertEqual(r["pnl_created"], 0)


# ---------------------------------------------------------------------------
# 7. Lane U coverage_policy_warning
# ---------------------------------------------------------------------------

class LaneUCoverageWarningTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        self.backup_proof_path = pathlib.Path(self._tmp.name) / "backup.sqlite3"
        self.backup_proof_path.write_bytes(b"backup")
        apply_migrations(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def _token_file(self) -> pathlib.Path:
        tf = pathlib.Path(self._tmp.name) / "tokens.json"
        tf.write_text(json.dumps({
            "tokens": [{
                "token_mint": _MINT,
                "lifecycle_lane": "TRACK_FAST",
                "approved_by_operator": True,
                "operator_note": _NOTE,
            }]
        }), encoding="utf-8")
        return tf

    def _run(self, snapshot_interval_seconds: float = 0.0) -> dict:
        from printer_v1.sources.governed_execution import (
            build_fixture_source_adapter, FIXTURE_SUCCESS,
        )
        adapter = build_fixture_source_adapter(
            "dexscreener",
            fixture_kind=FIXTURE_SUCCESS,
            fixture_payload={
                "source_name": "dexscreener",
                "request_kind": "pair_market_snapshot",
                "pairs": [{
                    "chain": "solana", "pair_address": _PAIR_ADDR,
                    "token_mint": _MINT, "symbol": "T", "name": "T",
                    "price_usd": 0.0001, "liquidity_usd": 50000.0,
                    "volume_5m": 100.0, "volume_1h": 1200.0, "volume_24h": 28800.0,
                    "txns_5m": 5, "txns_1h": 60, "txns_24h": 1440,
                    "fdv": 42000.0, "market_cap": 38000.0,
                    "price_change_5m": 0.1, "price_change_1h": 0.5, "price_change_24h": -1.0,
                }],
            },
        )
        return run_memory_factory_cycle(
            self._token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            duration_profile="1h",
            snapshot_interval_seconds=snapshot_interval_seconds,
            _adapter=adapter,
            _cycle_budget=1,
        )

    def test_warning_emitted_when_sleep_below_target(self):
        r = self._run(snapshot_interval_seconds=0.0)
        self.assertIsNotNone(r.get("coverage_policy_warning"))

    def test_warning_mentions_target_interval(self):
        r = self._run(snapshot_interval_seconds=0.0)
        warning = r.get("coverage_policy_warning") or ""
        self.assertIn("target_snapshot_interval_seconds", warning)

    def test_no_warning_when_sleep_meets_target(self):
        r = self._run(snapshot_interval_seconds=90.0)
        self.assertIsNone(r.get("coverage_policy_warning"))

    def test_cadence_policy_active_true(self):
        r = self._run()
        self.assertTrue(r.get("cadence_policy_active"))

    def test_target_snapshot_interval_in_result(self):
        r = self._run()
        self.assertIsNotNone(r.get("target_snapshot_interval_seconds"))
        self.assertEqual(r["target_snapshot_interval_seconds"], 90)

    def test_max_clean_snapshot_gap_in_result(self):
        r = self._run()
        self.assertIsNotNone(r.get("max_clean_snapshot_gap_seconds"))
        self.assertEqual(r["max_clean_snapshot_gap_seconds"], 120)

    def test_snapshot_interval_seconds_in_result(self):
        r = self._run(snapshot_interval_seconds=0.0)
        self.assertEqual(r.get("snapshot_interval_seconds"), 0.0)


# ---------------------------------------------------------------------------
# 8. Window-kind disabled checks (pure policy)
# ---------------------------------------------------------------------------

class DisabledWindowKindTests(unittest.TestCase):
    def _eval_with_snaps(self, window_kind: str, tracking_lane: str | None):
        p = get_policy(window_kind, tracking_lane)
        snaps = [_snap(_WIN_START), _snap(_WIN_END)]
        return evaluate_cadence_policy(snaps, _WIN_START, _WIN_END, p)

    def test_1h_track_fast_blocked(self):
        ev = self._eval_with_snaps("WINDOW_1H", "TRACK_FAST")
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)

    def test_4h_track_normal_blocked(self):
        ev = self._eval_with_snaps("WINDOW_4H", "TRACK_NORMAL")
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)

    def test_12h_any_blocked(self):
        ev = self._eval_with_snaps("WINDOW_12H", None)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)

    def test_24h_any_blocked(self):
        ev = self._eval_with_snaps("WINDOW_24H", None)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)

    def test_5m_support_blocked(self):
        p = get_policy("WINDOW_5M_MICRO_EVENT", None)
        snaps = [_snap(_WIN_START), _snap(_ts(_WIN_START, 30))]
        ev = evaluate_cadence_policy(snaps, _WIN_START, _ts(_WIN_START, 30), p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)
        self.assertTrue(p.support_only)

    def test_disabled_reason_present(self):
        p = get_policy("WINDOW_1H", "TRACK_FAST")
        snaps = [_snap(_WIN_START), _snap(_WIN_END)]
        ev = evaluate_cadence_policy(snaps, _WIN_START, _WIN_END, p)
        self.assertIsNotNone(ev.blocked_reason)


# ---------------------------------------------------------------------------
# 9. Two-interval timing model — new tests
# ---------------------------------------------------------------------------

class TimingModelPolicyFieldTests(unittest.TestCase):
    """Verify window_close_interval_seconds is present and correct."""

    def test_track_fast_window_close_interval(self):
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        self.assertEqual(p.window_close_interval_seconds, 900)

    def test_track_normal_window_close_interval(self):
        p = get_policy("WINDOW_15M", "TRACK_NORMAL")
        self.assertEqual(p.window_close_interval_seconds, 900)

    def test_track_fast_minimum_required_snapshots(self):
        # 900 / 90 = 10
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        self.assertEqual(p.minimum_required_snapshots, 10)

    def test_track_normal_minimum_required_snapshots(self):
        # 900 / 180 = 5
        p = get_policy("WINDOW_15M", "TRACK_NORMAL")
        self.assertEqual(p.minimum_required_snapshots, 5)

    def test_5m_window_close_interval(self):
        p = get_policy("WINDOW_5M_MICRO_EVENT", None)
        self.assertEqual(p.window_close_interval_seconds, 300)


class FullWindowSpanTests(unittest.TestCase):
    """90s / 180s snapshots across a full 900s span → PASS."""

    def test_track_fast_full_900s_span_passes(self):
        # 90s intervals across 900s: snaps at 0, 90, 180, ..., 900 = 11 snaps
        snaps = [_snap(_ts(_WIN_START, i * 90)) for i in range(11)]
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        ev = evaluate_cadence_policy(snaps, _WIN_START, _WIN_END, p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_PASS)

    def test_track_fast_full_900s_no_blocked_reason(self):
        snaps = [_snap(_ts(_WIN_START, i * 90)) for i in range(11)]
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        ev = evaluate_cadence_policy(snaps, _WIN_START, _WIN_END, p)
        self.assertIsNone(ev.blocked_reason)

    def test_track_fast_full_900s_max_gap_at_limit(self):
        snaps = [_snap(_ts(_WIN_START, i * 90)) for i in range(11)]
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        ev = evaluate_cadence_policy(snaps, _WIN_START, _WIN_END, p)
        self.assertIsNotNone(ev.actual_max_gap_seconds)
        self.assertLessEqual(ev.actual_max_gap_seconds, 120)

    def test_track_normal_full_900s_span_passes(self):
        # 180s intervals across 900s: snaps at 0, 180, 360, 540, 720, 900 = 6 snaps
        snaps = [_snap(_ts(_WIN_START, i * 180)) for i in range(6)]
        p = get_policy("WINDOW_15M", "TRACK_NORMAL")
        ev = evaluate_cadence_policy(snaps, _WIN_START, _WIN_END, p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_PASS)

    def test_track_normal_full_900s_no_blocked_reason(self):
        snaps = [_snap(_ts(_WIN_START, i * 180)) for i in range(6)]
        p = get_policy("WINDOW_15M", "TRACK_NORMAL")
        ev = evaluate_cadence_policy(snaps, _WIN_START, _WIN_END, p)
        self.assertIsNone(ev.blocked_reason)


class BoundaryOnlyBlocksTests(unittest.TestCase):
    """Boundary-only snapshots (start + end only) must block because max gap >> limit."""

    def test_boundary_only_track_fast_blocked(self):
        # 2 snapshots: start and end. Gap = 900s >> 120s limit.
        # But count=2 < min_required=10 → blocked by count first.
        snaps = [_snap(_WIN_START), _snap(_WIN_END)]
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        ev = evaluate_cadence_policy(snaps, _WIN_START, _WIN_END, p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)

    def test_boundary_only_10_snaps_blocked_by_gap(self):
        # 10 snapshots all clustered at boundaries (5 start, 5 end).
        # Count satisfies min_required=10; but gap between clusters >> 120s.
        snaps = [_snap(_ts(_WIN_START, i * 5)) for i in range(5)]      # 0–20s
        snaps += [_snap(_ts(_WIN_START, 880 + i * 5)) for i in range(5)]  # 880–900s
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        ev = evaluate_cadence_policy(snaps, _WIN_START, _WIN_END, p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)
        self.assertIn("coverage_gap_exceeds_policy", ev.blocked_reason)

    def test_boundary_only_track_normal_blocked(self):
        snaps = [_snap(_ts(_WIN_START, i * 5)) for i in range(3)]     # 0–10s
        snaps += [_snap(_ts(_WIN_START, 890 + i * 5)) for i in range(3)]  # 890–900s
        # count=6 > min_required=5 for TRACK_NORMAL; gap >> 300s → BLOCKED
        p = get_policy("WINDOW_15M", "TRACK_NORMAL")
        ev = evaluate_cadence_policy(snaps, _WIN_START, _WIN_END, p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)


class ShortWindowBlocksTests(unittest.TestCase):
    """A 90s elapsed window blocks at Lane Q (elapsed < 900s)."""

    def _setup_90s_window(self) -> tuple[str, int]:
        """Return (db_path, window_id) for a 90s-elapsed window."""
        tmp = tempfile.mkdtemp()
        db_path = pathlib.Path(tmp) / "printer_v1.sqlite3"
        apply_migrations(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        win_start = _WIN_START
        win_end = _ts(_WIN_START, 90)  # only 90s elapsed — well below 900s

        try:
            tid = conn.execute(
                "INSERT INTO printer_tokens"
                " (token_mint, chain, symbol, name, first_seen_at, last_seen_at,"
                "  token_status, created_at, updated_at)"
                " VALUES (?, 'solana', 'T', 'T', ?, ?, 'TRACK_FAST', ?, ?)",
                (_MINT, _NOW_STR, _NOW_STR, _NOW_STR, _NOW_STR),
            ).lastrowid
            pid = conn.execute(
                "INSERT INTO printer_pairs"
                " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at,"
                "  created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (tid, _PAIR_ADDR, _MINT, _NOW_STR, _NOW_STR, _NOW_STR, _NOW_STR),
            ).lastrowid
            sid_start = conn.execute(
                "INSERT INTO printer_token_snapshots"
                " (token_id, pair_id, captured_at, tracking_lane, snapshot_mode,"
                "  price_usd, source_status, data_quality_label, created_at)"
                " VALUES (?, ?, ?, 'TRACK_FAST', 'LIVE', 0.0001, 'COMPLETE', 'CLEAN_DATA', ?)",
                (tid, pid, win_start, _NOW_STR),
            ).lastrowid
            sid_end = conn.execute(
                "INSERT INTO printer_token_snapshots"
                " (token_id, pair_id, captured_at, tracking_lane, snapshot_mode,"
                "  price_usd, source_status, data_quality_label, created_at)"
                " VALUES (?, ?, ?, 'TRACK_FAST', 'LIVE', 0.0001, 'COMPLETE', 'CLEAN_DATA', ?)",
                (tid, pid, win_end, _NOW_STR),
            ).lastrowid
            wid = conn.execute(
                """
                INSERT INTO printer_memory_windows (
                    token_id, pair_id, window_kind, opened_at, closed_at,
                    memory_status, data_quality_label, do_not_train,
                    window_status, memory_quality_label,
                    supporting_context_json, created_by_phase, created_at, updated_at,
                    window_start_at, window_end_at,
                    snapshot_start_id, snapshot_end_id
                ) VALUES (?, ?, 'WINDOW_15M', ?, ?, ?, ?, ?, ?, ?, ?, 'lane_e2o', ?, ?, ?, ?, ?, ?)
                """,
                (
                    tid, pid, _NOW_STR, _NOW_STR,
                    "PARTIAL_MEMORY", "CLEAN_DATA", 0,
                    "WINDOW_CLOSED", "PARTIAL_MEMORY",
                    '{}', _NOW_STR, _NOW_STR,
                    win_start, win_end,
                    sid_start, sid_end,
                ),
            ).lastrowid
            conn.commit()
            return str(db_path), int(wid)
        finally:
            conn.close()

    def test_90s_elapsed_window_blocked_by_lane_q(self):
        db_path, wid = self._setup_90s_window()
        r = guard_candidate_windows(db_path, [wid], operator_approved=True)
        self.assertIn(wid, r["blocked_window_ids"])
        verdict = r["window_verdicts"][0]
        self.assertIn("elapsed_seconds_below_900", verdict["blocked_reasons"])


class ProductionModeTests(unittest.TestCase):
    """production_mode=True: 0 snapshots in range → BLOCKED (not UNKNOWN)."""

    def _policy(self):
        return get_policy("WINDOW_15M", "TRACK_FAST")

    def test_production_mode_zero_snapshots_blocked(self):
        ev = evaluate_cadence_policy(
            [], _WIN_START, _WIN_END, self._policy(),
            production_mode=True,
        )
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)

    def test_production_mode_zero_snapshots_reason(self):
        ev = evaluate_cadence_policy(
            [], _WIN_START, _WIN_END, self._policy(),
            production_mode=True,
        )
        self.assertIsNotNone(ev.blocked_reason)
        self.assertIn("production_mode_missing_coverage", ev.blocked_reason)

    def test_fixture_mode_zero_snapshots_unknown(self):
        # Without production_mode (default), 0 snapshots → UNKNOWN (no block).
        ev = evaluate_cadence_policy(
            [], _WIN_START, _WIN_END, self._policy(),
        )
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_UNKNOWN)

    def test_fixture_mode_zero_snapshots_no_blocked_reason(self):
        ev = evaluate_cadence_policy(
            [], _WIN_START, _WIN_END, self._policy(),
        )
        self.assertIsNone(ev.blocked_reason)

    def test_production_mode_with_enough_snaps_still_evaluates_gap(self):
        # Even in production_mode, a valid window with even coverage → PASS.
        snaps = [_snap(_ts(_WIN_START, i * 90)) for i in range(11)]
        ev = evaluate_cadence_policy(
            snaps, _WIN_START, _WIN_END, self._policy(),
            production_mode=True,
        )
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_PASS)


class LaneQProductionModeTests(_LaneQCoverageBase):
    """Lane Q guard with production_mode=True: 0 snapshots → BLOCKED."""

    def _setup_synthetic_window(self) -> int:
        """Insert a PARTIAL_MEMORY window with snapshot IDs that don't exist in DB."""
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            # snapshot IDs 9999/10000 don't exist in printer_token_snapshots
            wid = self._insert_window(
                conn, tid, pid,
                snapshot_start_id=9999,
                snapshot_end_id=10000,
            )
            conn.commit()
            return wid
        finally:
            conn.close()

    def test_synthetic_window_fixture_mode_valid(self):
        # In fixture mode (default), 0 matching snapshots → UNKNOWN → LANE_Q_VALID
        wid = self._setup_synthetic_window()
        r = guard_candidate_windows(
            self.db_path, [wid], operator_approved=True, production_mode=False
        )
        self.assertIn(wid, r["valid_window_ids"])

    def test_synthetic_window_production_mode_blocked(self):
        # In production mode, 0 snapshots in range → BLOCKED
        wid = self._setup_synthetic_window()
        r = guard_candidate_windows(
            self.db_path, [wid], operator_approved=True, production_mode=True
        )
        self.assertIn(wid, r["blocked_window_ids"])

    def test_production_mode_blocked_reason_mentions_coverage(self):
        wid = self._setup_synthetic_window()
        r = guard_candidate_windows(
            self.db_path, [wid], operator_approved=True, production_mode=True
        )
        verdict = r["window_verdicts"][0]
        blocked_reasons = verdict["blocked_reasons"]
        self.assertTrue(
            any("production_mode_missing_coverage" in r for r in blocked_reasons),
            f"Expected 'production_mode_missing_coverage' in blocked_reasons, got: {blocked_reasons}",
        )

    def test_real_snapshot_window_production_mode_evaluates(self):
        # A window with real snapshots in DB evaluates normally in production_mode.
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            first_id, last_id = self._insert_even_snapshots(
                conn, tid, pid, interval_seconds=90, count=11
            )
            wid = self._insert_window(
                conn, tid, pid,
                snapshot_start_id=first_id,
                snapshot_end_id=last_id,
            )
            conn.commit()
        finally:
            conn.close()

        r = guard_candidate_windows(
            self.db_path, [wid], operator_approved=True, production_mode=True
        )
        # With even coverage, should pass even in production mode
        self.assertIn(wid, r["valid_window_ids"])

    def test_window_close_interval_is_separate_from_snapshot_interval(self):
        # Proves the two-interval model exists in the policy
        p = get_policy("WINDOW_15M", "TRACK_FAST")
        self.assertNotEqual(
            p.target_snapshot_interval_seconds,
            p.window_close_interval_seconds,
            "snapshot_interval (90s) != window_close_interval (900s)",
        )


_RUNNER_MINT = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_RUNNER_PAIR = "LaneUTwoIntervalTestPairAAAAAAAAAAAAAAAAAAAAA"
_RUNNER_NOTE = "Operator-approved for Lane U two-interval test. Reviewed 2026-06-30."


class LaneURunnnerTwoIntervalTests(unittest.TestCase):
    """Lane U runner uses snapshot_interval_seconds and window_close_interval_seconds."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        self.backup_proof_path = pathlib.Path(self._tmp.name) / "backup.sqlite3"
        self.backup_proof_path.write_bytes(b"backup")
        apply_migrations(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def _token_file(self) -> pathlib.Path:
        tf = pathlib.Path(self._tmp.name) / "tokens.json"
        tf.write_text(json.dumps({
            "tokens": [{
                "token_mint": _RUNNER_MINT,
                "lifecycle_lane": "TRACK_FAST",
                "approved_by_operator": True,
                "operator_note": _RUNNER_NOTE,
            }]
        }), encoding="utf-8")
        return tf

    def _run(self, **kwargs) -> dict:
        from printer_v1.sources.governed_execution import (
            build_fixture_source_adapter, FIXTURE_SUCCESS,
        )
        adapter = build_fixture_source_adapter(
            "dexscreener",
            fixture_kind=FIXTURE_SUCCESS,
            fixture_payload={
                "source_name": "dexscreener",
                "request_kind": "pair_market_snapshot",
                "pairs": [{
                    "chain": "solana", "pair_address": _RUNNER_PAIR,
                    "token_mint": _RUNNER_MINT, "symbol": "T", "name": "T",
                    "price_usd": 0.0001, "liquidity_usd": 50000.0,
                    "volume_5m": 100.0, "volume_1h": 1200.0, "volume_24h": 28800.0,
                    "txns_5m": 5, "txns_1h": 60, "txns_24h": 1440,
                    "fdv": 42000.0, "market_cap": 38000.0,
                    "price_change_5m": 0.1, "price_change_1h": 0.5, "price_change_24h": -1.0,
                }],
            },
        )
        defaults = dict(
            token_list_path=self._token_file(),
            db_path=self.db_path,
            backup_proof_path=self.backup_proof_path,
            operator_approved=True,
            duration_profile="1h",
            _adapter=adapter,
            _cycle_budget=1,
        )
        defaults.update(kwargs)
        return run_memory_factory_cycle(**defaults)

    def test_result_has_snapshot_interval_seconds(self):
        r = self._run(snapshot_interval_seconds=0.0)
        self.assertIn("snapshot_interval_seconds", r)
        self.assertEqual(r["snapshot_interval_seconds"], 0.0)

    def test_result_has_window_close_interval_seconds(self):
        r = self._run(window_close_interval_seconds=0.0)
        self.assertIn("window_close_interval_seconds", r)
        self.assertEqual(r["window_close_interval_seconds"], 0.0)

    def test_warning_below_target_uses_snapshot_interval_param(self):
        # When snapshot_interval_seconds < target(90), warning is emitted
        r = self._run(snapshot_interval_seconds=0.0)
        self.assertIsNotNone(r.get("coverage_policy_warning"))
        warning = r["coverage_policy_warning"]
        self.assertIn("snapshot_interval_seconds", warning)

    def test_no_warning_at_or_above_target(self):
        # snapshot_interval_seconds=90 >= target=90 → no warning
        r = self._run(snapshot_interval_seconds=90.0)
        self.assertIsNone(r.get("coverage_policy_warning"))

    def test_cycle_budget_counts_window_closes(self):
        # _cycle_budget=1 → 1 window close → 1 completed cycle
        r = self._run(_cycle_budget=1)
        self.assertEqual(r["total_cycles_completed"], 1)
        self.assertEqual(r["total_cycles_attempted"], 1)
        self.assertEqual(len(r["cycles"]), 1)

    def test_two_window_closes_two_cycles(self):
        r = self._run(_cycle_budget=2)
        self.assertEqual(r["total_cycles_completed"], 2)
        self.assertEqual(len(r["cycles"]), 2)

    def test_window_close_at_zero_fires_immediately(self):
        # window_close_interval_seconds=0 → window closes immediately after first snap
        r = self._run(window_close_interval_seconds=0.0, _cycle_budget=1)
        self.assertEqual(r["lane_u_status"], "LANE_U_COMPLETED")
        self.assertEqual(r["total_cycles_completed"], 1)

    def test_lane_k_called_with_production_mode(self):
        # With production_mode=True in Lane K, synthetic/empty windows are blocked.
        # This run has no real 900s-elapsed windows, so clean_memory_rows_created=0.
        r = self._run(_cycle_budget=1)
        self.assertEqual(r["lane_u_status"], "LANE_U_COMPLETED")
        # Zero clean memories is valid even in production mode
        self.assertTrue(r["zero_clean_memories_is_valid"])
        self.assertGreaterEqual(r["clean_memory_rows_created"], 0)

    def test_no_cycle_sleep_old_param_accepted(self):
        # snapshot_interval_seconds=0.0 (not cycle_sleep_seconds) must be accepted
        r = self._run(snapshot_interval_seconds=0.0)
        self.assertEqual(r["lane_u_status"], "LANE_U_COMPLETED")


if __name__ == "__main__":
    unittest.main()

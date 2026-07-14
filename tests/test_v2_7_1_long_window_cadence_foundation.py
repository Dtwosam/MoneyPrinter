"""V2-7.1 deterministic long-window cadence foundation tests.

Fixtures and temporary DBs only. Long windows remain disabled for real
collection; this suite proves their future cadence and reporting contracts.
"""

from __future__ import annotations

import pathlib
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from printer_v1.db.migrate import apply_migrations
from printer_v1.operator_cli.e2q_memory_window_audit import (
    E2Q_STATUS_BLOCKED,
    audit_15m_memory_window,
)
from printer_v1.snapshots.cadence_policy import (
    CADENCE_POLICY_BLOCKED,
    CADENCE_POLICY_DIRTY,
    CADENCE_POLICY_PASS,
    cadence_policy_evaluation_to_dict,
    cadence_policy_to_dict,
    cadence_resource_budget,
    evaluate_cadence_policy,
    expected_snapshot_count,
    get_policy,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
MINT = "11111111111111111111111111111111"
PAIR = "22222222222222222222222222222222"

CASES = {
    ("WINDOW_4H", "TRACK_FAST"): (10800, 180, 225, 360, 61),
    ("WINDOW_4H", "TRACK_NORMAL"): (10800, 360, 450, 720, 31),
    ("WINDOW_12H", "TRACK_FAST"): (28800, 300, 375, 600, 97),
    ("WINDOW_12H", "TRACK_NORMAL"): (28800, 600, 750, 1200, 49),
    ("WINDOW_24H", "TRACK_FAST"): (43200, 300, 375, 600, 145),
    ("WINDOW_24H", "TRACK_NORMAL"): (43200, 600, 750, 1200, 73),
}


def iso(seconds: float) -> str:
    return (T0 + timedelta(seconds=seconds)).isoformat()


def snapshots_from_gaps(gaps: list[float], *, close_late: float = 0) -> list[dict]:
    times = [0.0]
    for gap in gaps:
        times.append(times[-1] + gap)
    times[-1] += close_late
    return [{"captured_at": iso(value)} for value in times]


def even_snapshots(duration: int, count: int, *, close_late: float = 0) -> list[dict]:
    interval = duration / (count - 1)
    return snapshots_from_gaps([interval] * (count - 1), close_late=close_late)


def snapshots_with_gap(duration: int, count: int, target_gap: float) -> list[dict]:
    nominal = duration / (count - 1)
    gaps = [nominal] * (count - 1)
    extra = target_gap - nominal
    gaps[0] = target_gap
    index = 1
    while extra > 0 and index < len(gaps):
        reduction = min(extra, gaps[index] - 1.0)
        gaps[index] -= reduction
        extra -= reduction
        index += 1
    if extra > 0:
        raise AssertionError("fixture cannot redistribute target gap")
    return snapshots_from_gaps(gaps)


class LongWindowPolicyTableTests(unittest.TestCase):
    def test_exact_approved_table_and_counts(self):
        for (window, lane), (duration, nominal, clean_max, blocked_at, count) in CASES.items():
            with self.subTest(window=window, lane=lane):
                policy = get_policy(window, lane)
                self.assertIsNotNone(policy)
                self.assertEqual(policy.window_close_interval_seconds, duration)
                self.assertEqual(policy.target_snapshot_interval_seconds, nominal)
                self.assertEqual(policy.clean_max_gap_seconds, clean_max)
                self.assertEqual(policy.blocked_at_gap_seconds, blocked_at)
                self.assertEqual(policy.minimum_required_snapshots, count)
                self.assertEqual(expected_snapshot_count(duration, nominal), count)
                self.assertFalse(policy.enabled_for_real_collection)
                self.assertTrue(policy.require_full_anchored_duration)
                self.assertTrue(policy.require_forced_closing_snapshot)

    def test_policy_derived_budgets(self):
        for (window, lane), (_, _, _, _, count) in CASES.items():
            budget = cadence_resource_budget(window, lane, token_count=2)
            self.assertEqual(budget["expected_snapshots_per_token"], count)
            self.assertEqual(budget["source_request_ceiling"], 2 * count)
            self.assertEqual(budget["scheduler_row_ceiling"], 2 * count)
            self.assertEqual(budget["automatic_retries"], 0)
            self.assertFalse(budget["enabled_for_real_collection"])

    def test_canonical_policy_reporting(self):
        policy = get_policy("WINDOW_4H", "TRACK_FAST")
        report = cadence_policy_to_dict(policy)
        self.assertEqual(report["clean_max_gap_seconds"], 225)
        self.assertEqual(report["blocked_at_gap_seconds"], 360)
        self.assertEqual(report["continuation_seconds"], 10800)
        self.assertEqual(report["expected_snapshot_count"], 61)


class LongWindowQualityBoundaryTests(unittest.TestCase):
    def evaluate(self, window: str, lane: str, snaps: list[dict], duration: float):
        return evaluate_cadence_policy(
            snaps,
            iso(0),
            iso(duration),
            get_policy(window, lane),
            allow_disabled_policy_evaluation=True,
        )

    def test_exact_count_clean_gaps_and_canonical_duration(self):
        for (window, lane), (duration, _, _, _, count) in CASES.items():
            ev = self.evaluate(window, lane, even_snapshots(duration, count), duration)
            self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_PASS)
            self.assertEqual(ev.anchored_duration_seconds, duration)
            self.assertEqual(ev.observed_snapshot_span_seconds, duration)
            self.assertEqual(ev.closing_freshness_status, "CLOSING_SNAPSHOT_CLEAN")
            self.assertEqual(ev.closing_snapshot_lateness_seconds, 0)

    def test_one_missing_dirty_two_missing_blocked_without_interpolation(self):
        for (window, lane), (duration, _, _, _, count) in CASES.items():
            one_missing = self.evaluate(
                window, lane, even_snapshots(duration, count - 1), duration
            )
            two_missing = self.evaluate(
                window, lane, even_snapshots(duration, count - 2), duration
            )
            self.assertEqual(one_missing.cadence_policy_status, CADENCE_POLICY_DIRTY)
            self.assertEqual(one_missing.missed_snapshots, 1)
            self.assertEqual(two_missing.cadence_policy_status, CADENCE_POLICY_BLOCKED)
            self.assertEqual(two_missing.missed_snapshots, 2)
            self.assertIn("too_many_missing_snapshots", two_missing.blocked_reason)

    def test_clean_dirty_and_blocked_gap_boundaries(self):
        for (window, lane), (duration, _, clean_max, blocked_at, count) in CASES.items():
            at_clean = self.evaluate(
                window, lane, snapshots_with_gap(duration, count, clean_max), duration
            )
            above_clean = self.evaluate(
                window, lane, snapshots_with_gap(duration, count, clean_max + 1), duration
            )
            at_block = self.evaluate(
                window, lane, snapshots_with_gap(duration, count, blocked_at), duration
            )
            above_block = self.evaluate(
                window, lane, snapshots_with_gap(duration, count, blocked_at + 1), duration
            )
            self.assertEqual(at_clean.cadence_policy_status, CADENCE_POLICY_PASS)
            self.assertEqual(above_clean.cadence_policy_status, CADENCE_POLICY_DIRTY)
            self.assertEqual(at_block.cadence_policy_status, CADENCE_POLICY_BLOCKED)
            self.assertEqual(above_block.cadence_policy_status, CADENCE_POLICY_BLOCKED)

    def test_closing_freshness_boundaries(self):
        for (window, lane), (duration, nominal, _, _, count) in CASES.items():
            clean = self.evaluate(
                window, lane, even_snapshots(duration, count, close_late=60), duration
            )
            dirty = self.evaluate(
                window, lane, even_snapshots(duration, count, close_late=61), duration
            )
            dirty_upper_boundary = self.evaluate(
                window,
                lane,
                even_snapshots(duration, count, close_late=nominal - 1),
                duration,
            )
            blocked = self.evaluate(
                window, lane, even_snapshots(duration, count, close_late=nominal), duration
            )
            missing_close = self.evaluate(
                window, lane, even_snapshots(duration, count)[:-1], duration
            )
            self.assertEqual(clean.cadence_policy_status, CADENCE_POLICY_PASS)
            self.assertEqual(clean.closing_freshness_status, "CLOSING_SNAPSHOT_CLEAN")
            self.assertEqual(dirty.cadence_policy_status, CADENCE_POLICY_DIRTY)
            self.assertEqual(dirty.closing_freshness_status, "CLOSING_SNAPSHOT_DIRTY")
            self.assertEqual(
                dirty_upper_boundary.cadence_policy_status, CADENCE_POLICY_DIRTY
            )
            self.assertEqual(blocked.cadence_policy_status, CADENCE_POLICY_BLOCKED)
            self.assertEqual(blocked.closing_freshness_status, "CLOSING_SNAPSHOT_BLOCKED")
            self.assertEqual(missing_close.cadence_policy_status, CADENCE_POLICY_BLOCKED)
            self.assertEqual(
                missing_close.closing_freshness_status,
                "CLOSING_SNAPSHOT_MISSING_AT_DEADLINE",
            )

    def test_inadequate_anchored_duration_blocks(self):
        for (window, lane), (duration, _, _, _, count) in CASES.items():
            ev = self.evaluate(
                window, lane, even_snapshots(duration - 1, count), duration - 1
            )
            self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)
            self.assertIn("anchored_duration_inadequate", ev.blocked_reason)

    def test_real_collection_remains_disabled(self):
        for (window, lane), (duration, _, _, _, count) in CASES.items():
            ev = evaluate_cadence_policy(
                even_snapshots(duration, count),
                iso(0),
                iso(duration),
                get_policy(window, lane),
                production_mode=True,
            )
            self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)
            self.assertIn("disabled", ev.blocked_reason)

    def test_evaluation_report_is_canonical(self):
        ev = self.evaluate(
            "WINDOW_12H", "TRACK_NORMAL", even_snapshots(28800, 49), 28800
        )
        report = cadence_policy_evaluation_to_dict(ev)
        self.assertEqual(report["clean_max_gap_seconds"], 750)
        self.assertEqual(report["blocked_at_gap_seconds"], 1200)
        self.assertEqual(report["anchored_duration_seconds"], 28800)
        self.assertEqual(report["observed_snapshot_span_seconds"], 28800)


class ExistingCadenceAndAuditLockTests(unittest.TestCase):
    def test_5m_15m_1h_contracts_unchanged(self):
        expected = {
            ("WINDOW_5M_MICRO_EVENT", "TRACK_FAST"): (30, 45, 60, 11, False),
            ("WINDOW_5M_MICRO_EVENT", "TRACK_NORMAL"): (60, 90, 120, 6, False),
            ("WINDOW_15M", "TRACK_FAST"): (60, 90, 120, 16, True),
            ("WINDOW_15M", "TRACK_NORMAL"): (120, 180, 240, 9, True),
            ("WINDOW_1H", "TRACK_FAST"): (120, 180, 240, 24, True),
            ("WINDOW_1H", "TRACK_NORMAL"): (240, 360, 480, 13, True),
        }
        for key, values in expected.items():
            p = get_policy(*key)
            self.assertEqual(
                (
                    p.target_snapshot_interval_seconds,
                    p.dirty_above_gap_seconds,
                    p.max_clean_snapshot_gap_seconds,
                    p.minimum_required_snapshots,
                    p.enabled_for_real_collection,
                ),
                values,
            )

    def test_e2q_blocks_long_window_but_reports_policy_and_zero_unlocks(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            db_path = pathlib.Path(directory) / "proof.sqlite3"
            apply_migrations(db_path)
            connection = sqlite3.connect(str(db_path))
            connection.row_factory = sqlite3.Row
            try:
                now = T0.isoformat()
                token_id = connection.execute(
                    "INSERT INTO printer_tokens"
                    " (token_mint, chain, first_seen_at, last_seen_at, token_status, created_at, updated_at)"
                    " VALUES (?, 'solana', ?, ?, 'TRACK_FAST', ?, ?)",
                    (MINT, now, now, now, now),
                ).lastrowid
                pair_id = connection.execute(
                    "INSERT INTO printer_pairs"
                    " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (token_id, PAIR, MINT, now, now, now, now),
                ).lastrowid
                window_id = connection.execute(
                    "INSERT INTO printer_memory_windows"
                    " (token_id, pair_id, window_kind, opened_at, closed_at,"
                    "  memory_status, data_quality_label, do_not_train,"
                    "  window_status, created_at, updated_at)"
                    " VALUES (?, ?, 'WINDOW_4H', ?, ?, 'PARTIAL_MEMORY',"
                    "  'CLEAN_DATA', 0, 'WINDOW_CLOSED', ?, ?)",
                    (token_id, pair_id, now, now, now, now),
                ).lastrowid
                connection.commit()
                locked_tables = (
                    "printer_memory_retrieval_queries",
                    "printer_memory_retrieval_matches",
                    "printer_paper_decisions",
                    "printer_paper_positions",
                    "printer_paper_trade_events",
                    "printer_paper_trade_audits",
                    "printer_paper_audit_reports",
                )
                before = {
                    table: connection.execute(
                        f'SELECT COUNT(*) FROM "{table}"'
                    ).fetchone()[0]
                    for table in locked_tables
                }
                result = audit_15m_memory_window(connection, window_id)
                after = {
                    table: connection.execute(
                        f'SELECT COUNT(*) FROM "{table}"'
                    ).fetchone()[0]
                    for table in locked_tables
                }
            finally:
                connection.close()
            self.assertEqual(result["e2q_status"], E2Q_STATUS_BLOCKED)
            self.assertEqual(result["cadence_policy"]["expected_snapshot_count"], 61)
            self.assertEqual(result["cadence_resource_budget"]["scheduler_row_ceiling"], 61)
            self.assertEqual(result["paper_decisions_created"], 0)
            self.assertEqual(result["positions_created"], 0)
            self.assertEqual(result["pnl_created"], 0)
            self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()

"""V2-6.1a snapshot cadence + 15m->1h continuity — focused verification.

Proves the single authoritative cadence contract and its three-tier (clean /
dirty / blocked) coverage classification, the expected minimum schedules, the
15m->1h transition rule, jitter handling, no interpolation, exact token/pair
continuity, and that both the 15m runner and the quality gates consume the same
contract. Fixtures / temp DBs only — no source calls, scheduler runtime, or
persistent DB mutation.
"""

import pathlib
import sys
import unittest
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.snapshots.cadence_policy import (
    CADENCE_POLICY_BLOCKED,
    CADENCE_POLICY_DIRTY,
    CADENCE_POLICY_PASS,
    TRANSITION_BLOCKED,
    TRANSITION_CLEAN,
    TRANSITION_DIRTY,
    evaluate_cadence_policy,
    evaluate_transition_gap,
    expected_snapshot_count,
    get_policy,
)

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _iso(dt):
    return dt.isoformat()


def _snaps(interval, count, start=_T0):
    return [{"captured_at": _iso(start + timedelta(seconds=i * interval))} for i in range(count)]


class ContractTableTests(unittest.TestCase):
    CASES = {
        ("WINDOW_5M_MICRO_EVENT", "TRACK_FAST"): (30, 45, 60, 11),
        ("WINDOW_5M_MICRO_EVENT", "TRACK_NORMAL"): (60, 90, 120, 6),
        ("WINDOW_15M", "TRACK_FAST"): (60, 90, 120, 16),
        ("WINDOW_15M", "TRACK_NORMAL"): (120, 180, 240, 9),
        ("WINDOW_1H", "TRACK_FAST"): (120, 180, 240, 24),
        ("WINDOW_1H", "TRACK_NORMAL"): (240, 360, 480, 13),
    }

    def test_all_rows_match_authoritative_table(self):
        for (wk, lane), (nominal, dirty, block, expected) in self.CASES.items():
            p = get_policy(wk, lane)
            self.assertIsNotNone(p, f"{wk}/{lane}")
            self.assertEqual(p.target_snapshot_interval_seconds, nominal, f"{wk}/{lane} nominal")
            self.assertEqual(p.dirty_above_gap_seconds, dirty, f"{wk}/{lane} dirty")
            self.assertEqual(p.max_clean_snapshot_gap_seconds, block, f"{wk}/{lane} block")
            self.assertEqual(p.minimum_required_snapshots, expected, f"{wk}/{lane} expected")

    def test_expected_counts_derive_from_window_and_nominal(self):
        self.assertEqual(expected_snapshot_count(300, 30), 11)
        self.assertEqual(expected_snapshot_count(300, 60), 6)
        self.assertEqual(expected_snapshot_count(900, 60), 16)
        self.assertEqual(expected_snapshot_count(900, 120), 9)
        self.assertEqual(expected_snapshot_count(2700, 120), 24)
        self.assertEqual(expected_snapshot_count(2700, 240), 13)

    def test_5m_support_only_and_longer_disabled(self):
        self.assertTrue(get_policy("WINDOW_5M_MICRO_EVENT", "TRACK_FAST").support_only)
        for wk in ("WINDOW_4H", "WINDOW_12H", "WINDOW_24H"):
            self.assertFalse(get_policy(wk, "TRACK_FAST").enabled_for_real_collection)

    def test_15m_and_1h_enabled(self):
        self.assertTrue(get_policy("WINDOW_15M", "TRACK_FAST").enabled_for_real_collection)
        self.assertTrue(get_policy("WINDOW_1H", "TRACK_FAST").enabled_for_real_collection)


class ThreeTierClassificationTests(unittest.TestCase):
    def _p(self, lane="TRACK_FAST"):
        return get_policy("WINDOW_15M", lane)

    def test_full_expected_even_is_clean(self):
        win_end = _iso(_T0 + timedelta(seconds=900))
        ev = evaluate_cadence_policy(_snaps(60, 16), _iso(_T0), win_end, self._p())
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_PASS)
        self.assertEqual(ev.missed_snapshots, 0)

    def test_gap_in_dirty_band_is_dirty(self):
        times = [0, 100] + [100 + i * 55 for i in range(1, 15)]  # 16 points, first gap 100s
        snaps = [{"captured_at": _iso(_T0 + timedelta(seconds=t))} for t in times]
        win_end = _iso(_T0 + timedelta(seconds=times[-1]))
        ev = evaluate_cadence_policy(snaps, _iso(_T0), win_end, self._p())
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_DIRTY)
        self.assertGreater(ev.actual_max_gap_seconds, 90)
        self.assertLessEqual(ev.actual_max_gap_seconds, 120)

    def test_gap_above_block_is_blocked(self):
        snaps = _snaps(60, 16)
        win_end = _iso(_T0 + timedelta(seconds=900 + 400))
        ev = evaluate_cadence_policy(snaps, _iso(_T0), win_end, self._p())
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)

    def test_missed_snapshots_with_clean_gaps_is_dirty(self):
        win_end = _iso(_T0 + timedelta(seconds=660))
        ev = evaluate_cadence_policy(_snaps(60, 12), _iso(_T0), win_end, self._p())
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_DIRTY)
        self.assertEqual(ev.missed_snapshots, 4)
        self.assertIn("missed_snapshots", ev.blocked_reason)

    def test_jitter_within_dirty_band_stays_clean_or_dirty_not_blocked(self):
        times = [0, 60, 145, 205, 265, 325, 385, 445, 505, 565, 625, 685, 745, 805, 865, 900]
        snaps = [{"captured_at": _iso(_T0 + timedelta(seconds=t))} for t in times]
        win_end = _iso(_T0 + timedelta(seconds=900))
        ev = evaluate_cadence_policy(snaps, _iso(_T0), win_end, self._p())
        self.assertIn(ev.cadence_policy_status, (CADENCE_POLICY_PASS, CADENCE_POLICY_DIRTY))
        self.assertNotEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)

    def test_missing_snapshots_never_interpolated(self):
        win_end = _iso(_T0 + timedelta(seconds=660))
        ev = evaluate_cadence_policy(_snaps(60, 12), _iso(_T0), win_end, self._p())
        self.assertEqual(ev.actual_snapshot_count, 12)
        self.assertEqual(len(ev.actual_gaps_seconds), 13)
        self.assertEqual(ev.missed_snapshots, 4)

    def test_5m_support_blocked_from_main(self):
        p = get_policy("WINDOW_5M_MICRO_EVENT", "TRACK_FAST")
        self.assertTrue(p.support_only)
        ev = evaluate_cadence_policy(_snaps(30, 11), _iso(_T0), _iso(_T0 + timedelta(seconds=300)), p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)
        self.assertTrue(
            "support_only" in ev.blocked_reason or "disabled" in ev.blocked_reason
        )

    def test_disabled_4h_blocked(self):
        p = get_policy("WINDOW_4H", "TRACK_FAST")
        ev = evaluate_cadence_policy(_snaps(300, 10), _iso(_T0), _iso(_T0 + timedelta(seconds=2700)), p)
        self.assertEqual(ev.cadence_policy_status, CADENCE_POLICY_BLOCKED)
        self.assertIn("disabled", ev.blocked_reason)


class TransitionRuleTests(unittest.TestCase):
    def _gap(self, seconds, lane="TRACK_FAST"):
        return evaluate_transition_gap(
            _iso(_T0), _iso(_T0 + timedelta(seconds=seconds)), lane
        )

    def test_fast_expected_clean(self):
        self.assertEqual(self._gap(120)["transition_status"], TRANSITION_CLEAN)

    def test_fast_dirty_band(self):
        self.assertEqual(self._gap(181)["transition_status"], TRANSITION_DIRTY)

    def test_fast_block_band(self):
        self.assertEqual(self._gap(241)["transition_status"], TRANSITION_BLOCKED)

    def test_normal_expected_clean(self):
        self.assertEqual(self._gap(240, "TRACK_NORMAL")["transition_status"], TRANSITION_CLEAN)

    def test_normal_dirty_band(self):
        self.assertEqual(self._gap(361, "TRACK_NORMAL")["transition_status"], TRANSITION_DIRTY)

    def test_normal_block_band(self):
        self.assertEqual(self._gap(481, "TRACK_NORMAL")["transition_status"], TRANSITION_BLOCKED)

    def test_delayed_restart_negative_gap_blocked(self):
        r = evaluate_transition_gap(_iso(_T0 + timedelta(seconds=100)), _iso(_T0), "TRACK_FAST")
        self.assertEqual(r["transition_status"], TRANSITION_BLOCKED)
        self.assertIn("delayed_restart", r["reason"])


class SharedContractTests(unittest.TestCase):
    def test_runner_schedule_matches_policy_expected_counts(self):
        from printer_v1.operator_cli.one_command_15m_factory import _schedule_offsets
        for lane in ("TRACK_FAST", "TRACK_NORMAL"):
            expected = get_policy("WINDOW_15M", lane).minimum_required_snapshots
            self.assertEqual(len(_schedule_offsets(lane, 900)) + 2, expected)

    def test_runner_budgets_derive_from_cadence(self):
        from printer_v1.operator_cli import one_command_15m_factory as f
        fast = get_policy("WINDOW_15M", "TRACK_FAST").minimum_required_snapshots
        self.assertEqual(f._MAX_SNAPSHOTS_PER_TOKEN, fast)
        self.assertEqual(f._MAX_GOVERNED_REQUESTS_PER_TOKEN, fast + 5)
        self.assertEqual(f._MAX_GOVERNED_REQUESTS_RUN, 2 + 3 * (fast + 5))
        self.assertEqual(f._MAX_SCHEDULER_ROWS, 3 * fast + 3)

    def test_lane_q_and_e2q_consume_same_policy_module(self):
        import printer_v1.operator_cli.lane_q_15m_window_integrity_guard as lane_q
        from printer_v1.snapshots import cadence_policy
        self.assertIs(lane_q.get_policy, cadence_policy.get_policy)
        self.assertIs(lane_q.evaluate_cadence_policy, cadence_policy.evaluate_cadence_policy)


if __name__ == "__main__":
    unittest.main()

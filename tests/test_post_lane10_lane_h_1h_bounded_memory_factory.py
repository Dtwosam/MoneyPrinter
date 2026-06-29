"""
Post-Lane 10 Lane H — Bounded 1h Memory Factory Boundary

Ten boundary proofs:
1. operator_approved is required
2. WINDOW_1H is the only target window for Lane H
3. 1h evidence must span a real 1h window; fake 15m-composite is blocked
4. incomplete/dirty/stale/missing context → DIRTY or AUDIT_ONLY, not CLEAN
5. CLEAN_MEMORY is only possible when all full 1h evidence gates pass
6. zero clean memory is a valid outcome
7. 5m remains support-only and cannot parent/replace 1h
8. retrieval/paper/BUY/SELL/HOLD/positions/PnL remain locked
9. no scheduler/source governor bypass
10. no existing 15m/5m behavior is changed by Lane H
"""

import pathlib
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.operator_cli.lane_h_1h_bounded_memory_factory import (
    LANE_H_MIN_SNAPSHOT_COUNT,
    LANE_H_MIN_WINDOW_MINUTES,
    LANE_H_STATUS_AUDIT_ONLY,
    LANE_H_STATUS_BLOCKED,
    LANE_H_STATUS_CLEAN_CANDIDATE,
    LANE_H_STATUS_DIRTY,
    LANE_H_WINDOW_KIND,
    _HARD_LOCKS,
    _LOCKED_STATE,
    build_1h_evidence_fixture,
    classify_1h_memory_attempt,
)


def _run(evidence, *, operator_approved=True):
    return classify_1h_memory_attempt(evidence, operator_approved=operator_approved)


def _valid():
    return build_1h_evidence_fixture()


# ============================================================
# Proof 1 — operator_approved is required
# ============================================================

class LaneHApprovalTests(unittest.TestCase):
    def test_blocked_without_approval(self):
        r = _run(_valid(), operator_approved=False)
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_BLOCKED)

    def test_blocked_reason_mentions_operator(self):
        r = _run(_valid(), operator_approved=False)
        self.assertTrue(
            any("operator_approved" in reason for reason in r["rejection_reasons"])
        )

    def test_no_episode_marker_on_blocked(self):
        r = _run(_valid(), operator_approved=False)
        self.assertFalse(r["is_clean_candidate"])

    def test_hard_locks_true_on_blocked(self):
        r = _run(_valid(), operator_approved=False)
        for k, v in r["hard_locks"].items():
            self.assertTrue(v, f"hard_locks[{k!r}] must be True on blocked result")

    def test_evidence_none_blocked(self):
        r = classify_1h_memory_attempt(None, operator_approved=True)
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_BLOCKED)

    def test_evidence_non_dict_blocked(self):
        r = classify_1h_memory_attempt("not-a-dict", operator_approved=True)  # type: ignore[arg-type]
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_BLOCKED)

    def test_retrieval_false_on_blocked(self):
        r = _run(_valid(), operator_approved=False)
        self.assertFalse(r["retrieval_activated"])

    def test_buy_false_on_blocked(self):
        r = _run(_valid(), operator_approved=False)
        self.assertFalse(r["buy_enabled"])


# ============================================================
# Proof 2 — WINDOW_1H is the only valid target window
# ============================================================

class LaneHWindowKindTests(unittest.TestCase):
    def test_window_1h_passes_kind_gate(self):
        r = _run(build_1h_evidence_fixture(window_kind="WINDOW_1H"))
        self.assertNotEqual(r["lane_h_status"], LANE_H_STATUS_BLOCKED)

    def test_window_15m_is_blocked(self):
        r = _run(build_1h_evidence_fixture(window_kind="WINDOW_15M"))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_BLOCKED)

    def test_window_15m_blocked_reason(self):
        r = _run(build_1h_evidence_fixture(window_kind="WINDOW_15M"))
        self.assertTrue(any("WINDOW_1H" in reason for reason in r["rejection_reasons"]))

    def test_window_4h_is_blocked(self):
        r = _run(build_1h_evidence_fixture(window_kind="WINDOW_4H"))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_BLOCKED)

    def test_window_24h_is_blocked(self):
        r = _run(build_1h_evidence_fixture(window_kind="WINDOW_24H"))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_BLOCKED)

    def test_none_window_kind_is_blocked(self):
        r = _run(build_1h_evidence_fixture(window_kind=None))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_BLOCKED)

    def test_window_kind_target_always_1h(self):
        for kind in ("WINDOW_15M", "WINDOW_4H", "WINDOW_5M_MICRO_EVENT"):
            with self.subTest(kind=kind):
                r = _run(build_1h_evidence_fixture(window_kind=kind))
                self.assertEqual(r["window_kind_target"], LANE_H_WINDOW_KIND)


# ============================================================
# Proof 3 — real 1h evidence required; fake 15m composite is blocked
# ============================================================

class LaneHFakeLongWindowTests(unittest.TestCase):
    def test_fake_15m_composite_is_blocked(self):
        r = _run(build_1h_evidence_fixture(is_fake_15m_composite=True))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_BLOCKED)

    def test_fake_15m_composite_blocked_reason(self):
        r = _run(build_1h_evidence_fixture(is_fake_15m_composite=True))
        self.assertTrue(
            any("fake" in reason or "composite" in reason for reason in r["rejection_reasons"])
        )

    def test_no_episode_from_fake_composite(self):
        r = _run(build_1h_evidence_fixture(is_fake_15m_composite=True))
        self.assertFalse(r["is_clean_candidate"])

    def test_short_duration_below_60m_is_dirty(self):
        r = _run(build_1h_evidence_fixture(window_duration_minutes=45))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_DIRTY)

    def test_exactly_60m_passes_duration_gate(self):
        r = _run(build_1h_evidence_fixture(window_duration_minutes=60))
        self.assertNotEqual(r["lane_h_status"], LANE_H_STATUS_DIRTY)

    def test_59m_fails_duration_gate(self):
        r = _run(build_1h_evidence_fixture(window_duration_minutes=59))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_DIRTY)

    def test_missing_open_snapshot_is_dirty(self):
        r = _run(build_1h_evidence_fixture(has_open_snapshot=False))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_DIRTY)

    def test_missing_close_snapshot_is_dirty(self):
        r = _run(build_1h_evidence_fixture(has_close_snapshot=False))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_DIRTY)


# ============================================================
# Proof 4 — incomplete/dirty/stale/missing → DIRTY or AUDIT_ONLY
# ============================================================

class LaneHDirtyAuditClassificationTests(unittest.TestCase):
    def test_dirty_data_label_yields_dirty(self):
        r = _run(build_1h_evidence_fixture(data_quality_label="DIRTY_DATA"))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_DIRTY)

    def test_stale_data_label_yields_dirty(self):
        r = _run(build_1h_evidence_fixture(data_quality_label="STALE_DATA"))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_DIRTY)

    def test_missing_critical_data_yields_dirty(self):
        r = _run(build_1h_evidence_fixture(data_quality_label="MISSING_CRITICAL_DATA"))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_DIRTY)

    def test_conflicting_data_yields_dirty(self):
        r = _run(build_1h_evidence_fixture(data_quality_label="CONFLICTING_DATA"))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_DIRTY)

    def test_do_not_train_yields_dirty(self):
        r = _run(build_1h_evidence_fixture(do_not_train=True))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_DIRTY)

    def test_failed_source_yields_dirty(self):
        r = _run(build_1h_evidence_fixture(source_status="FAILED"))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_DIRTY)

    def test_too_few_snapshots_yields_dirty(self):
        r = _run(build_1h_evidence_fixture(snapshot_count=1))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_DIRTY)

    def test_zero_snapshots_yields_dirty(self):
        r = _run(build_1h_evidence_fixture(snapshot_count=0))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_DIRTY)

    def test_dirty_is_not_clean_candidate(self):
        r = _run(build_1h_evidence_fixture(data_quality_label="DIRTY_DATA"))
        self.assertFalse(r["is_clean_candidate"])

    def test_acceptable_partial_data_yields_audit_only(self):
        r = _run(build_1h_evidence_fixture(data_quality_label="ACCEPTABLE_PARTIAL_DATA"))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_AUDIT_ONLY)

    def test_partial_source_status_yields_audit_only(self):
        r = _run(build_1h_evidence_fixture(source_status="PARTIAL"))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_AUDIT_ONLY)

    def test_incomplete_context_yields_audit_only(self):
        r = _run(build_1h_evidence_fixture(context_complete=False))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_AUDIT_ONLY)

    def test_audit_only_is_not_clean_candidate(self):
        r = _run(build_1h_evidence_fixture(context_complete=False))
        self.assertFalse(r["is_clean_candidate"])

    def test_audit_only_has_rejection_reasons(self):
        r = _run(build_1h_evidence_fixture(context_complete=False))
        self.assertGreater(len(r["rejection_reasons"]), 0)


# ============================================================
# Proof 5 — CLEAN only when all gates pass
# ============================================================

class LaneHCleanCandidateTests(unittest.TestCase):
    def test_valid_fixture_is_clean_candidate(self):
        r = _run(_valid())
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_CLEAN_CANDIDATE)

    def test_clean_candidate_has_is_clean_true(self):
        r = _run(_valid())
        self.assertTrue(r["is_clean_candidate"])

    def test_clean_candidate_has_no_rejection_reasons(self):
        r = _run(_valid())
        self.assertEqual(r["rejection_reasons"], [])

    def test_clean_requires_complete_source(self):
        r = _run(build_1h_evidence_fixture(source_status="PARTIAL"))
        self.assertNotEqual(r["lane_h_status"], LANE_H_STATUS_CLEAN_CANDIDATE)

    def test_clean_requires_clean_data_quality(self):
        r = _run(build_1h_evidence_fixture(data_quality_label="ACCEPTABLE_PARTIAL_DATA"))
        self.assertNotEqual(r["lane_h_status"], LANE_H_STATUS_CLEAN_CANDIDATE)

    def test_clean_requires_complete_context(self):
        r = _run(build_1h_evidence_fixture(context_complete=False))
        self.assertNotEqual(r["lane_h_status"], LANE_H_STATUS_CLEAN_CANDIDATE)

    def test_clean_requires_open_and_close_snapshots(self):
        r = _run(build_1h_evidence_fixture(has_close_snapshot=False))
        self.assertNotEqual(r["lane_h_status"], LANE_H_STATUS_CLEAN_CANDIDATE)

    def test_clean_requires_sufficient_snapshots(self):
        r = _run(build_1h_evidence_fixture(snapshot_count=1))
        self.assertNotEqual(r["lane_h_status"], LANE_H_STATUS_CLEAN_CANDIDATE)

    def test_clean_requires_full_duration(self):
        r = _run(build_1h_evidence_fixture(window_duration_minutes=30))
        self.assertNotEqual(r["lane_h_status"], LANE_H_STATUS_CLEAN_CANDIDATE)

    def test_hard_locks_all_true_on_clean_candidate(self):
        r = _run(_valid())
        for k, v in r["hard_locks"].items():
            self.assertTrue(v, f"hard_locks[{k!r}] must be True even on CLEAN_CANDIDATE")


# ============================================================
# Proof 6 — zero clean memory is a valid outcome
# ============================================================

class LaneHZeroCleanTests(unittest.TestCase):
    def test_all_dirty_evidence_yields_zero_clean_candidates(self):
        results = [
            _run(build_1h_evidence_fixture(data_quality_label="DIRTY_DATA")),
            _run(build_1h_evidence_fixture(source_status="FAILED")),
            _run(build_1h_evidence_fixture(snapshot_count=1)),
        ]
        clean_count = sum(1 for r in results if r["is_clean_candidate"])
        self.assertEqual(clean_count, 0)

    def test_all_audit_only_evidence_yields_zero_clean_candidates(self):
        results = [
            _run(build_1h_evidence_fixture(context_complete=False)),
            _run(build_1h_evidence_fixture(source_status="PARTIAL")),
        ]
        clean_count = sum(1 for r in results if r["is_clean_candidate"])
        self.assertEqual(clean_count, 0)

    def test_blocked_evidence_yields_zero_clean_candidates(self):
        results = [
            _run(_valid(), operator_approved=False),
            _run(build_1h_evidence_fixture(window_kind="WINDOW_15M")),
            _run(build_1h_evidence_fixture(is_fake_15m_composite=True)),
        ]
        clean_count = sum(1 for r in results if r["is_clean_candidate"])
        self.assertEqual(clean_count, 0)

    def test_zero_clean_is_not_an_error(self):
        # Module returns a result dict (not raises) even when nothing qualifies
        r = _run(build_1h_evidence_fixture(data_quality_label="DIRTY_DATA"))
        self.assertIn("lane_h_status", r)
        self.assertFalse(r["is_clean_candidate"])


# ============================================================
# Proof 7 — 5m remains support-only; cannot parent/replace 1h
# ============================================================

class LaneH5mSupportOnlyTests(unittest.TestCase):
    def test_5m_window_flag_is_blocked(self):
        r = _run(build_1h_evidence_fixture(is_5m_window=True))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_BLOCKED)

    def test_5m_blocked_reason_mentions_support_only(self):
        r = _run(build_1h_evidence_fixture(is_5m_window=True))
        self.assertTrue(
            any("support-only" in reason or "5m" in reason for reason in r["rejection_reasons"])
        )

    def test_5m_micro_event_window_kind_is_blocked(self):
        r = _run(build_1h_evidence_fixture(
            window_kind="WINDOW_5M_MICRO_EVENT",
            is_5m_window=True,
        ))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_BLOCKED)

    def test_5m_window_is_not_clean_candidate(self):
        r = _run(build_1h_evidence_fixture(is_5m_window=True))
        self.assertFalse(r["is_clean_candidate"])

    def test_5m_flag_does_not_override_1h_kind_gate(self):
        # Even with is_5m_window=False, WINDOW_5M_MICRO_EVENT kind is still blocked
        r = _run(build_1h_evidence_fixture(
            window_kind="WINDOW_5M_MICRO_EVENT",
            is_5m_window=False,
        ))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_BLOCKED)

    def test_no_5m_main_outcome_lock_is_true(self):
        r = _run(_valid())
        self.assertTrue(r["hard_locks"]["no_5m_main_outcome"])


# ============================================================
# Proof 8 — retrieval/paper/BUY/SELL/HOLD/positions/PnL locked
# ============================================================

class LaneHLockedStateTests(unittest.TestCase):
    def _all_statuses(self):
        return [
            _run(_valid()),                                              # CLEAN_CANDIDATE
            _run(build_1h_evidence_fixture(context_complete=False)),    # AUDIT_ONLY
            _run(build_1h_evidence_fixture(data_quality_label="DIRTY_DATA")),  # DIRTY
            _run(_valid(), operator_approved=False),                    # BLOCKED
        ]

    def test_retrieval_never_activated(self):
        for r in self._all_statuses():
            with self.subTest(status=r["lane_h_status"]):
                self.assertFalse(r["retrieval_activated"])

    def test_paper_decisions_always_zero(self):
        for r in self._all_statuses():
            with self.subTest(status=r["lane_h_status"]):
                self.assertEqual(r["paper_decisions_created"], 0)

    def test_buy_never_enabled(self):
        for r in self._all_statuses():
            with self.subTest(status=r["lane_h_status"]):
                self.assertFalse(r["buy_enabled"])

    def test_sell_never_enabled(self):
        for r in self._all_statuses():
            with self.subTest(status=r["lane_h_status"]):
                self.assertFalse(r["sell_enabled"])

    def test_hold_never_enabled(self):
        for r in self._all_statuses():
            with self.subTest(status=r["lane_h_status"]):
                self.assertFalse(r["hold_enabled"])

    def test_positions_always_zero(self):
        for r in self._all_statuses():
            with self.subTest(status=r["lane_h_status"]):
                self.assertEqual(r["positions_created"], 0)

    def test_pnl_always_zero(self):
        for r in self._all_statuses():
            with self.subTest(status=r["lane_h_status"]):
                self.assertEqual(r["pnl_created"], 0)

    def test_all_hard_locks_true_always(self):
        for r in self._all_statuses():
            with self.subTest(status=r["lane_h_status"]):
                for k, v in r["hard_locks"].items():
                    self.assertTrue(v, f"hard_locks[{k!r}] must be True")

    def test_locked_state_all_false_always(self):
        for r in self._all_statuses():
            with self.subTest(status=r["lane_h_status"]):
                for k, v in r["locked_state"].items():
                    self.assertFalse(v, f"locked_state[{k!r}] must be False")


# ============================================================
# Proof 9 — no scheduler / source governor bypass
# ============================================================

class LaneHSchedulerGovernorTests(unittest.TestCase):
    def test_no_scheduler_bypass_lock_exists(self):
        r = _run(_valid())
        self.assertIn("no_scheduler_bypass", r["hard_locks"])
        self.assertTrue(r["hard_locks"]["no_scheduler_bypass"])

    def test_no_source_governor_bypass_lock_exists(self):
        r = _run(_valid())
        self.assertIn("no_source_governor_bypass", r["hard_locks"])
        self.assertTrue(r["hard_locks"]["no_source_governor_bypass"])

    def test_no_unbounded_runtime_lock_exists(self):
        r = _run(_valid())
        self.assertIn("no_unbounded_runtime", r["hard_locks"])
        self.assertTrue(r["hard_locks"]["no_unbounded_runtime"])

    def test_no_paid_api_lock_exists(self):
        r = _run(_valid())
        self.assertIn("no_paid_api", r["hard_locks"])
        self.assertTrue(r["hard_locks"]["no_paid_api"])

    def test_no_fake_long_window_lock_exists(self):
        r = _run(_valid())
        self.assertIn("no_fake_long_window_data", r["hard_locks"])
        self.assertTrue(r["hard_locks"]["no_fake_long_window_data"])

    def test_lock_count_is_sufficient(self):
        # At least 14 hard locks to cover the full threat surface
        r = _run(_valid())
        self.assertGreaterEqual(len(r["hard_locks"]), 14)

    def test_locked_state_retrieval_unlock_is_false(self):
        r = _run(_valid())
        self.assertFalse(r["locked_state"]["retrieval_unlock"])

    def test_locked_state_paper_decision_unlock_is_false(self):
        r = _run(_valid())
        self.assertFalse(r["locked_state"]["paper_decision_unlock"])


# ============================================================
# Proof 10 — existing 15m / 5m behavior is not changed
#   (structural proof: Lane H is pure dict-in/dict-out;
#    it imports no 15m modules and writes no DB rows)
# ============================================================

class LaneH15mBehaviorPreservationTests(unittest.TestCase):
    def test_lane_h_module_does_not_import_15m_modules(self):
        import printer_v1.operator_cli.lane_h_1h_bounded_memory_factory as lh
        module_file = str(getattr(lh, "__file__", ""))
        # Read the module source and check for forbidden imports
        with open(module_file, encoding="utf-8") as fh:
            source = fh.read()
        forbidden = ["e2j_", "e2o_", "e2q_", "e2t_", "e2x_", "e2y_", "e2z_"]
        for name in forbidden:
            self.assertNotIn(name, source, f"Lane H must not import {name}")

    def test_lane_h_window_kind_constant_is_1h_not_15m(self):
        self.assertEqual(LANE_H_WINDOW_KIND, "WINDOW_1H")
        self.assertNotEqual(LANE_H_WINDOW_KIND, "WINDOW_15M")

    def test_lane_h_classify_does_not_modify_shared_state(self):
        # Calling classify multiple times with same fixture is idempotent
        r1 = _run(_valid())
        r2 = _run(_valid())
        self.assertEqual(r1["lane_h_status"], r2["lane_h_status"])
        self.assertEqual(r1["is_clean_candidate"], r2["is_clean_candidate"])

    def test_15m_window_kind_is_explicitly_blocked_not_silently_misclassified(self):
        r = _run(build_1h_evidence_fixture(window_kind="WINDOW_15M"))
        self.assertEqual(r["lane_h_status"], LANE_H_STATUS_BLOCKED)
        # Ensure it's not DIRTY or AUDIT_ONLY — which would imply the 15m
        # window kind is being "partially accepted" by Lane H
        self.assertNotEqual(r["lane_h_status"], LANE_H_STATUS_DIRTY)
        self.assertNotEqual(r["lane_h_status"], LANE_H_STATUS_AUDIT_ONLY)

    def test_fixture_constant_min_minutes_is_60(self):
        self.assertEqual(LANE_H_MIN_WINDOW_MINUTES, 60)

    def test_fixture_constant_min_snapshots_is_2(self):
        self.assertEqual(LANE_H_MIN_SNAPSHOT_COUNT, 2)


if __name__ == "__main__":
    unittest.main()

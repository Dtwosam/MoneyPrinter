"""
Post-Lane 10 Lane I-C — Bounded 24h Staged Memory Factory Boundary

Thirteen boundary proofs:
1.  operator_approved is required
2.  WINDOW_24H is the only accepted target
3.  WINDOW_15M, WINDOW_1H, WINDOW_4H, WINDOW_12H, WINDOW_5M_MICRO_EVENT cannot satisfy 24h
4.  evidence must span >= 1440 real minutes
5.  fake 15m/1h/4h/12h composite evidence is blocked
6.  incomplete/dirty/stale/missing data → DIRTY or AUDIT_ONLY, not clean
7.  CLEAN_CANDIDATE only when full 24h evidence gates pass
8.  zero clean candidates is valid
9.  5m remains support-only
10. retrieval/paper/BUY/SELL/HOLD/positions/PnL remain locked
11. Lane J financial action gates remain locked after Lane I-C
12. no scheduler/source-governor bypass
13. no existing Lane H, Lane I-A, Lane I-B, 15m, 1h, 4h, 12h, or 5m behavior is weakened
"""

import pathlib
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.operator_cli.lane_i_24h_staged_memory_factory import (
    LANE_IC_MIN_SNAPSHOT_COUNT,
    LANE_IC_MIN_WINDOW_MINUTES,
    LANE_IC_STATUS_AUDIT_ONLY,
    LANE_IC_STATUS_BLOCKED,
    LANE_IC_STATUS_CLEAN_CANDIDATE,
    LANE_IC_STATUS_DIRTY,
    LANE_IC_WINDOW_KIND,
    _HARD_LOCKS,
    _LOCKED_STATE,
    build_24h_evidence_fixture,
    classify_24h_memory_attempt,
)


def _run(evidence, *, operator_approved=True):
    return classify_24h_memory_attempt(evidence, operator_approved=operator_approved)


def _valid():
    return build_24h_evidence_fixture()


# ============================================================
# Proof 1 — operator_approved is required
# ============================================================

class LaneICApprovalTests(unittest.TestCase):
    def test_blocked_without_approval(self):
        r = _run(_valid(), operator_approved=False)
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_blocked_reason_mentions_operator(self):
        r = _run(_valid(), operator_approved=False)
        self.assertTrue(
            any("operator_approved" in reason for reason in r["rejection_reasons"])
        )

    def test_no_clean_candidate_when_not_approved(self):
        r = _run(_valid(), operator_approved=False)
        self.assertFalse(r["is_clean_candidate"])

    def test_hard_locks_true_on_blocked(self):
        r = _run(_valid(), operator_approved=False)
        for k, v in r["hard_locks"].items():
            self.assertTrue(v, f"hard_locks[{k!r}] must be True on blocked result")

    def test_evidence_none_blocked(self):
        r = classify_24h_memory_attempt(None, operator_approved=True)
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_evidence_non_dict_blocked(self):
        r = classify_24h_memory_attempt("not-a-dict", operator_approved=True)  # type: ignore[arg-type]
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_retrieval_false_on_blocked(self):
        r = _run(_valid(), operator_approved=False)
        self.assertFalse(r["retrieval_activated"])

    def test_buy_false_on_blocked(self):
        r = _run(_valid(), operator_approved=False)
        self.assertFalse(r["buy_enabled"])


# ============================================================
# Proof 2 — WINDOW_24H is the only accepted target
# ============================================================

class LaneICWindowKindTests(unittest.TestCase):
    def test_window_24h_passes_kind_gate(self):
        r = _run(build_24h_evidence_fixture(window_kind="WINDOW_24H"))
        self.assertNotEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_window_kind_target_always_24h(self):
        for kind in ("WINDOW_15M", "WINDOW_1H", "WINDOW_4H", "WINDOW_12H", None):
            with self.subTest(kind=kind):
                r = _run(build_24h_evidence_fixture(window_kind=kind))
                self.assertEqual(r["window_kind_target"], LANE_IC_WINDOW_KIND)

    def test_none_window_kind_is_blocked(self):
        r = _run(build_24h_evidence_fixture(window_kind=None))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_blocked_reason_mentions_24h(self):
        r = _run(build_24h_evidence_fixture(window_kind=None))
        self.assertTrue(
            any("WINDOW_24H" in reason for reason in r["rejection_reasons"])
        )


# ============================================================
# Proof 3 — WINDOW_15M, WINDOW_1H, WINDOW_4H, WINDOW_12H, WINDOW_5M cannot satisfy 24h
# ============================================================

class LaneICShortWindowRejectionTests(unittest.TestCase):
    def test_window_15m_is_blocked(self):
        r = _run(build_24h_evidence_fixture(window_kind="WINDOW_15M"))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_window_1h_is_blocked(self):
        r = _run(build_24h_evidence_fixture(window_kind="WINDOW_1H"))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_window_4h_is_blocked(self):
        r = _run(build_24h_evidence_fixture(window_kind="WINDOW_4H"))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_window_12h_is_blocked(self):
        r = _run(build_24h_evidence_fixture(window_kind="WINDOW_12H"))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_window_5m_micro_event_is_blocked(self):
        r = _run(build_24h_evidence_fixture(
            window_kind="WINDOW_5M_MICRO_EVENT",
            is_5m_window=True,
        ))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_15m_blocked_reason_mentions_24h(self):
        r = _run(build_24h_evidence_fixture(window_kind="WINDOW_15M"))
        self.assertTrue(any("WINDOW_24H" in reason for reason in r["rejection_reasons"]))

    def test_4h_blocked_reason_mentions_24h(self):
        r = _run(build_24h_evidence_fixture(window_kind="WINDOW_4H"))
        self.assertTrue(any("WINDOW_24H" in reason for reason in r["rejection_reasons"]))

    def test_12h_blocked_reason_mentions_24h(self):
        r = _run(build_24h_evidence_fixture(window_kind="WINDOW_12H"))
        self.assertTrue(any("WINDOW_24H" in reason for reason in r["rejection_reasons"]))

    def test_prior_stage_kinds_are_not_clean_candidates(self):
        for kind in ("WINDOW_15M", "WINDOW_1H", "WINDOW_4H", "WINDOW_12H"):
            with self.subTest(kind=kind):
                r = _run(build_24h_evidence_fixture(window_kind=kind))
                self.assertFalse(r["is_clean_candidate"])

    def test_prior_stage_kinds_blocked_not_misclassified(self):
        for kind in ("WINDOW_15M", "WINDOW_1H", "WINDOW_4H", "WINDOW_12H"):
            with self.subTest(kind=kind):
                r = _run(build_24h_evidence_fixture(window_kind=kind))
                self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)
                self.assertNotEqual(r["lane_ic_status"], LANE_IC_STATUS_DIRTY)
                self.assertNotEqual(r["lane_ic_status"], LANE_IC_STATUS_AUDIT_ONLY)


# ============================================================
# Proof 4 — evidence must span >= 1440 real minutes
# ============================================================

class LaneICDurationTests(unittest.TestCase):
    def test_exactly_1440m_passes_duration_gate(self):
        r = _run(build_24h_evidence_fixture(window_duration_minutes=1440))
        self.assertNotEqual(r["lane_ic_status"], LANE_IC_STATUS_DIRTY)

    def test_1439m_fails_duration_gate(self):
        r = _run(build_24h_evidence_fixture(window_duration_minutes=1439))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_DIRTY)

    def test_720m_fails_duration_gate(self):
        # 12h evidence is not sufficient for 24h
        r = _run(build_24h_evidence_fixture(window_duration_minutes=720))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_DIRTY)

    def test_240m_fails_duration_gate(self):
        # 4h evidence is not sufficient for 24h
        r = _run(build_24h_evidence_fixture(window_duration_minutes=240))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_DIRTY)

    def test_60m_fails_duration_gate(self):
        # 1h evidence is not sufficient for 24h
        r = _run(build_24h_evidence_fixture(window_duration_minutes=60))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_DIRTY)

    def test_duration_dirty_reason_mentions_minimum(self):
        r = _run(build_24h_evidence_fixture(window_duration_minutes=100))
        self.assertTrue(
            any("1440" in reason for reason in r["rejection_reasons"]),
            msg=f"expected 1440 minimum mentioned in {r['rejection_reasons']}",
        )

    def test_min_window_minutes_constant_is_1440(self):
        self.assertEqual(LANE_IC_MIN_WINDOW_MINUTES, 1440)

    def test_missing_open_snapshot_is_dirty(self):
        r = _run(build_24h_evidence_fixture(has_open_snapshot=False))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_DIRTY)

    def test_missing_close_snapshot_is_dirty(self):
        r = _run(build_24h_evidence_fixture(has_close_snapshot=False))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_DIRTY)


# ============================================================
# Proof 5 — fake 15m/1h/4h/12h composite evidence is blocked
# ============================================================

class LaneICFakeCompositeTests(unittest.TestCase):
    def test_fake_15m_composite_is_blocked(self):
        r = _run(build_24h_evidence_fixture(is_fake_15m_composite=True))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_fake_15m_composite_blocked_reason(self):
        r = _run(build_24h_evidence_fixture(is_fake_15m_composite=True))
        self.assertTrue(
            any("15m" in reason or "composite" in reason for reason in r["rejection_reasons"])
        )

    def test_fake_1h_composite_is_blocked(self):
        r = _run(build_24h_evidence_fixture(is_fake_1h_composite=True))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_fake_1h_composite_blocked_reason(self):
        r = _run(build_24h_evidence_fixture(is_fake_1h_composite=True))
        self.assertTrue(
            any("1h" in reason or "composite" in reason for reason in r["rejection_reasons"])
        )

    def test_fake_4h_composite_is_blocked(self):
        r = _run(build_24h_evidence_fixture(is_fake_4h_composite=True))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_fake_4h_composite_blocked_reason(self):
        r = _run(build_24h_evidence_fixture(is_fake_4h_composite=True))
        self.assertTrue(
            any("4h" in reason or "composite" in reason for reason in r["rejection_reasons"])
        )

    def test_fake_12h_composite_is_blocked(self):
        r = _run(build_24h_evidence_fixture(is_fake_12h_composite=True))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_fake_12h_composite_blocked_reason(self):
        r = _run(build_24h_evidence_fixture(is_fake_12h_composite=True))
        self.assertTrue(
            any("12h" in reason or "composite" in reason for reason in r["rejection_reasons"])
        )

    def test_no_episode_from_any_fake_composite(self):
        for flag in (
            "is_fake_15m_composite",
            "is_fake_1h_composite",
            "is_fake_4h_composite",
            "is_fake_12h_composite",
        ):
            with self.subTest(flag=flag):
                r = _run(build_24h_evidence_fixture(**{flag: True}))
                self.assertFalse(r["is_clean_candidate"])

    def test_no_fake_long_window_lock_is_true(self):
        r = _run(_valid())
        self.assertTrue(r["hard_locks"]["no_fake_long_window_data"])


# ============================================================
# Proof 6 — incomplete/dirty/stale/missing → DIRTY or AUDIT_ONLY
# ============================================================

class LaneICDirtyAuditClassificationTests(unittest.TestCase):
    def test_dirty_data_label_yields_dirty(self):
        r = _run(build_24h_evidence_fixture(data_quality_label="DIRTY_DATA"))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_DIRTY)

    def test_stale_data_label_yields_dirty(self):
        r = _run(build_24h_evidence_fixture(data_quality_label="STALE_DATA"))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_DIRTY)

    def test_missing_critical_data_yields_dirty(self):
        r = _run(build_24h_evidence_fixture(data_quality_label="MISSING_CRITICAL_DATA"))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_DIRTY)

    def test_conflicting_data_yields_dirty(self):
        r = _run(build_24h_evidence_fixture(data_quality_label="CONFLICTING_DATA"))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_DIRTY)

    def test_do_not_train_yields_dirty(self):
        r = _run(build_24h_evidence_fixture(do_not_train=True))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_DIRTY)

    def test_failed_source_yields_dirty(self):
        r = _run(build_24h_evidence_fixture(source_status="FAILED"))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_DIRTY)

    def test_too_few_snapshots_yields_dirty(self):
        r = _run(build_24h_evidence_fixture(snapshot_count=1))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_DIRTY)

    def test_dirty_is_not_clean_candidate(self):
        r = _run(build_24h_evidence_fixture(data_quality_label="DIRTY_DATA"))
        self.assertFalse(r["is_clean_candidate"])

    def test_acceptable_partial_data_yields_audit_only(self):
        r = _run(build_24h_evidence_fixture(data_quality_label="ACCEPTABLE_PARTIAL_DATA"))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_AUDIT_ONLY)

    def test_partial_source_status_yields_audit_only(self):
        r = _run(build_24h_evidence_fixture(source_status="PARTIAL"))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_AUDIT_ONLY)

    def test_incomplete_context_yields_audit_only(self):
        r = _run(build_24h_evidence_fixture(context_complete=False))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_AUDIT_ONLY)

    def test_audit_only_is_not_clean_candidate(self):
        r = _run(build_24h_evidence_fixture(context_complete=False))
        self.assertFalse(r["is_clean_candidate"])

    def test_audit_only_has_rejection_reasons(self):
        r = _run(build_24h_evidence_fixture(context_complete=False))
        self.assertGreater(len(r["rejection_reasons"]), 0)


# ============================================================
# Proof 7 — CLEAN_CANDIDATE only when all gates pass
# ============================================================

class LaneICCleanCandidateTests(unittest.TestCase):
    def test_valid_fixture_is_clean_candidate(self):
        r = _run(_valid())
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_CLEAN_CANDIDATE)

    def test_clean_candidate_has_is_clean_true(self):
        r = _run(_valid())
        self.assertTrue(r["is_clean_candidate"])

    def test_clean_candidate_has_no_rejection_reasons(self):
        r = _run(_valid())
        self.assertEqual(r["rejection_reasons"], [])

    def test_clean_requires_complete_source(self):
        r = _run(build_24h_evidence_fixture(source_status="PARTIAL"))
        self.assertNotEqual(r["lane_ic_status"], LANE_IC_STATUS_CLEAN_CANDIDATE)

    def test_clean_requires_clean_data_quality(self):
        r = _run(build_24h_evidence_fixture(data_quality_label="ACCEPTABLE_PARTIAL_DATA"))
        self.assertNotEqual(r["lane_ic_status"], LANE_IC_STATUS_CLEAN_CANDIDATE)

    def test_clean_requires_complete_context(self):
        r = _run(build_24h_evidence_fixture(context_complete=False))
        self.assertNotEqual(r["lane_ic_status"], LANE_IC_STATUS_CLEAN_CANDIDATE)

    def test_clean_requires_open_and_close_snapshots(self):
        r = _run(build_24h_evidence_fixture(has_close_snapshot=False))
        self.assertNotEqual(r["lane_ic_status"], LANE_IC_STATUS_CLEAN_CANDIDATE)

    def test_clean_requires_full_24h_duration(self):
        r = _run(build_24h_evidence_fixture(window_duration_minutes=720))
        self.assertNotEqual(r["lane_ic_status"], LANE_IC_STATUS_CLEAN_CANDIDATE)

    def test_hard_locks_all_true_on_clean_candidate(self):
        r = _run(_valid())
        for k, v in r["hard_locks"].items():
            self.assertTrue(v, f"hard_locks[{k!r}] must be True even on CLEAN_CANDIDATE")


# ============================================================
# Proof 8 — zero clean candidates is valid
# ============================================================

class LaneICZeroCleanTests(unittest.TestCase):
    def test_all_dirty_evidence_yields_zero_clean(self):
        results = [
            _run(build_24h_evidence_fixture(data_quality_label="DIRTY_DATA")),
            _run(build_24h_evidence_fixture(source_status="FAILED")),
            _run(build_24h_evidence_fixture(window_duration_minutes=720)),
        ]
        self.assertEqual(sum(1 for r in results if r["is_clean_candidate"]), 0)

    def test_all_audit_only_yields_zero_clean(self):
        results = [
            _run(build_24h_evidence_fixture(context_complete=False)),
            _run(build_24h_evidence_fixture(source_status="PARTIAL")),
        ]
        self.assertEqual(sum(1 for r in results if r["is_clean_candidate"]), 0)

    def test_blocked_evidence_yields_zero_clean(self):
        results = [
            _run(_valid(), operator_approved=False),
            _run(build_24h_evidence_fixture(window_kind="WINDOW_12H")),
            _run(build_24h_evidence_fixture(is_fake_12h_composite=True)),
        ]
        self.assertEqual(sum(1 for r in results if r["is_clean_candidate"]), 0)

    def test_zero_clean_does_not_raise(self):
        r = _run(build_24h_evidence_fixture(data_quality_label="DIRTY_DATA"))
        self.assertIn("lane_ic_status", r)
        self.assertFalse(r["is_clean_candidate"])


# ============================================================
# Proof 9 — 5m remains support-only
# ============================================================

class LaneIC5mSupportOnlyTests(unittest.TestCase):
    def test_5m_window_flag_is_blocked(self):
        r = _run(build_24h_evidence_fixture(is_5m_window=True))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_5m_blocked_reason_mentions_support_only(self):
        r = _run(build_24h_evidence_fixture(is_5m_window=True))
        self.assertTrue(
            any("support-only" in reason or "5m" in reason for reason in r["rejection_reasons"])
        )

    def test_5m_micro_event_kind_is_blocked(self):
        r = _run(build_24h_evidence_fixture(
            window_kind="WINDOW_5M_MICRO_EVENT",
            is_5m_window=True,
        ))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_5m_is_not_clean_candidate(self):
        r = _run(build_24h_evidence_fixture(is_5m_window=True))
        self.assertFalse(r["is_clean_candidate"])

    def test_5m_kind_blocked_even_without_flag(self):
        r = _run(build_24h_evidence_fixture(
            window_kind="WINDOW_5M_MICRO_EVENT",
            is_5m_window=False,
        ))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_no_5m_main_outcome_lock_is_true(self):
        r = _run(_valid())
        self.assertTrue(r["hard_locks"]["no_5m_main_outcome"])


# ============================================================
# Proof 10 — retrieval/paper/BUY/SELL/HOLD/positions/PnL locked
# ============================================================

class LaneICLockedStateTests(unittest.TestCase):
    def _all_statuses(self):
        return [
            _run(_valid()),
            _run(build_24h_evidence_fixture(context_complete=False)),
            _run(build_24h_evidence_fixture(data_quality_label="DIRTY_DATA")),
            _run(_valid(), operator_approved=False),
            _run(build_24h_evidence_fixture(window_kind="WINDOW_12H")),
        ]

    def test_retrieval_never_activated(self):
        for r in self._all_statuses():
            with self.subTest(status=r["lane_ic_status"]):
                self.assertFalse(r["retrieval_activated"])

    def test_paper_decisions_always_zero(self):
        for r in self._all_statuses():
            with self.subTest(status=r["lane_ic_status"]):
                self.assertEqual(r["paper_decisions_created"], 0)

    def test_buy_never_enabled(self):
        for r in self._all_statuses():
            with self.subTest(status=r["lane_ic_status"]):
                self.assertFalse(r["buy_enabled"])

    def test_sell_never_enabled(self):
        for r in self._all_statuses():
            with self.subTest(status=r["lane_ic_status"]):
                self.assertFalse(r["sell_enabled"])

    def test_hold_never_enabled(self):
        for r in self._all_statuses():
            with self.subTest(status=r["lane_ic_status"]):
                self.assertFalse(r["hold_enabled"])

    def test_positions_always_zero(self):
        for r in self._all_statuses():
            with self.subTest(status=r["lane_ic_status"]):
                self.assertEqual(r["positions_created"], 0)

    def test_pnl_always_zero(self):
        for r in self._all_statuses():
            with self.subTest(status=r["lane_ic_status"]):
                self.assertEqual(r["pnl_created"], 0)

    def test_all_hard_locks_true_always(self):
        for r in self._all_statuses():
            with self.subTest(status=r["lane_ic_status"]):
                for k, v in r["hard_locks"].items():
                    self.assertTrue(v, f"hard_locks[{k!r}] must be True")

    def test_locked_state_all_false_always(self):
        for r in self._all_statuses():
            with self.subTest(status=r["lane_ic_status"]):
                for k, v in r["locked_state"].items():
                    self.assertFalse(v, f"locked_state[{k!r}] must be False")


# ============================================================
# Proof 11 — Lane J financial action gates remain locked after Lane I-C
# ============================================================

class LaneJGatesRemainLockedTests(unittest.TestCase):
    """Lane I-C completion does NOT unlock Lane J (BUY, Positions, PnL)."""

    def _result_clean(self):
        return _run(_valid())

    def test_lane_j_buy_unlock_active_is_false_on_clean(self):
        r = self._result_clean()
        self.assertFalse(r["locked_state"]["lane_j_buy_unlock_active"])

    def test_lane_j_sell_hold_unlock_active_is_false_on_clean(self):
        r = self._result_clean()
        self.assertFalse(r["locked_state"]["lane_j_sell_hold_unlock_active"])

    def test_lane_j_paper_positions_unlock_active_is_false_on_clean(self):
        r = self._result_clean()
        self.assertFalse(r["locked_state"]["lane_j_paper_positions_unlock_active"])

    def test_lane_j_pnl_unlock_active_is_false_on_clean(self):
        r = self._result_clean()
        self.assertFalse(r["locked_state"]["lane_j_pnl_unlock_active"])

    def test_no_lane_j_activation_hard_lock_is_true(self):
        r = self._result_clean()
        self.assertTrue(r["hard_locks"]["no_lane_j_activation"])

    def test_lane_j_gates_locked_on_all_outcomes(self):
        all_results = [
            _run(_valid()),
            _run(build_24h_evidence_fixture(context_complete=False)),
            _run(build_24h_evidence_fixture(data_quality_label="DIRTY_DATA")),
            _run(_valid(), operator_approved=False),
        ]
        lane_j_keys = [
            "lane_j_buy_unlock_active",
            "lane_j_sell_hold_unlock_active",
            "lane_j_paper_positions_unlock_active",
            "lane_j_pnl_unlock_active",
        ]
        for r in all_results:
            with self.subTest(status=r["lane_ic_status"]):
                for k in lane_j_keys:
                    self.assertFalse(
                        r["locked_state"][k],
                        f"locked_state[{k!r}] must be False on {r['lane_ic_status']}",
                    )

    def test_buy_enabled_is_false_even_on_clean_candidate(self):
        r = self._result_clean()
        self.assertFalse(r["buy_enabled"])

    def test_positions_created_is_zero_even_on_clean_candidate(self):
        r = self._result_clean()
        self.assertEqual(r["positions_created"], 0)

    def test_pnl_created_is_zero_even_on_clean_candidate(self):
        r = self._result_clean()
        self.assertEqual(r["pnl_created"], 0)

    def test_paper_decisions_created_is_zero_even_on_clean_candidate(self):
        r = self._result_clean()
        self.assertEqual(r["paper_decisions_created"], 0)


# ============================================================
# Proof 12 — no scheduler/source-governor bypass
# ============================================================

class LaneICSchedulerGovernorTests(unittest.TestCase):
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

    def test_no_source_fetching_lock_exists(self):
        r = _run(_valid())
        self.assertIn("no_source_fetching", r["hard_locks"])
        self.assertTrue(r["hard_locks"]["no_source_fetching"])

    def test_lock_count_is_sufficient(self):
        r = _run(_valid())
        self.assertGreaterEqual(len(r["hard_locks"]), 16)

    def test_locked_state_retrieval_unlock_is_false(self):
        r = _run(_valid())
        self.assertFalse(r["locked_state"]["retrieval_unlock"])

    def test_locked_state_paper_decision_unlock_is_false(self):
        r = _run(_valid())
        self.assertFalse(r["locked_state"]["paper_decision_unlock"])


# ============================================================
# Proof 13 — no existing Lane H, Lane I-A, Lane I-B, 15m, 1h, 4h, 12h, or 5m weakened
#   (structural: Lane I-C is pure dict-in/dict-out,
#    imports no Lane H / Lane I-A / Lane I-B modules, writes no DB rows)
# ============================================================

class LaneICBehaviorPreservationTests(unittest.TestCase):
    def test_lane_ic_module_does_not_import_prior_lanes(self):
        import printer_v1.operator_cli.lane_i_24h_staged_memory_factory as lib
        with open(lib.__file__, encoding="utf-8") as fh:
            source = fh.read()
        forbidden = [
            "lane_h_", "lane_i_4h_", "lane_i_12h_",
            "e2j_", "e2o_", "e2q_", "e2t_", "e2x_", "e2y_", "e2z_",
        ]
        for name in forbidden:
            self.assertNotIn(name, source, f"Lane I-C must not import {name}")

    def test_lane_ic_window_kind_is_24h(self):
        self.assertEqual(LANE_IC_WINDOW_KIND, "WINDOW_24H")
        self.assertNotEqual(LANE_IC_WINDOW_KIND, "WINDOW_12H")
        self.assertNotEqual(LANE_IC_WINDOW_KIND, "WINDOW_4H")
        self.assertNotEqual(LANE_IC_WINDOW_KIND, "WINDOW_1H")
        self.assertNotEqual(LANE_IC_WINDOW_KIND, "WINDOW_15M")

    def test_lane_ic_classify_is_stateless(self):
        r1 = _run(_valid())
        r2 = _run(_valid())
        self.assertEqual(r1["lane_ic_status"], r2["lane_ic_status"])
        self.assertEqual(r1["is_clean_candidate"], r2["is_clean_candidate"])

    def test_min_window_minutes_is_1440(self):
        self.assertEqual(LANE_IC_MIN_WINDOW_MINUTES, 1440)

    def test_min_snapshot_count_is_2(self):
        self.assertEqual(LANE_IC_MIN_SNAPSHOT_COUNT, 2)

    def test_15m_blocked_as_wrong_kind_not_dirty(self):
        r = _run(build_24h_evidence_fixture(window_kind="WINDOW_15M"))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_12h_blocked_as_wrong_kind_not_dirty(self):
        r = _run(build_24h_evidence_fixture(window_kind="WINDOW_12H"))
        self.assertEqual(r["lane_ic_status"], LANE_IC_STATUS_BLOCKED)

    def test_no_db_import_in_module(self):
        import printer_v1.operator_cli.lane_i_24h_staged_memory_factory as lib
        with open(lib.__file__, encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("sqlalchemy", source)


if __name__ == "__main__":
    unittest.main()

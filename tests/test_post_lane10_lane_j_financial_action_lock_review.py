"""
Post-Lane 10 Lane J — Financial Action Lock Review

Twenty boundary proofs:
1.  operator_approved is required for the review
2.  Lane J status is LOCKED_REVIEW when approved, never UNLOCKED
3.  BUY remains locked
4.  SELL remains locked
5.  HOLD remains locked
6.  WAIT/AVOID/NO_ACTION are not created here
7.  paper decisions remain locked
8.  paper positions remain locked
9.  trade events remain locked
10. paper trade audits remain locked
11. PnL remains locked
12. live trading / wallet / private keys / signing remain locked
13. paid APIs remain locked
14. scoring/ranking/confidence/weighted logic remains locked
15. embeddings/vectors remain locked
16. Lane 9 policy is documentation-only, not executable approval
17. Lane 10 policy is documentation-only, not executable approval
18. Lane I 4h/12h/24h completion does not unlock financial actions
19. no DB/CLI/scheduler/source/retrieval/paper behavior changes
20. zero unlocked financial actions is the only valid outcome
"""

import pathlib
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.operator_cli.lane_j_financial_action_lock_review import (
    LANE_J_LANE10_POLICY_REF,
    LANE_J_LANE9_POLICY_REF,
    LANE_J_LANE_I_STAGES_ANCHORED,
    LANE_J_STATUS_BLOCKED,
    LANE_J_STATUS_LOCKED_REVIEW,
    _HARD_LOCKS,
    _LOCKED_STATE,
    review_financial_action_locks,
)


def _run(*, operator_approved=True):
    return review_financial_action_locks(operator_approved=operator_approved)


# ============================================================
# Proof 1 — operator_approved is required for the review
# ============================================================

class LaneJApprovalTests(unittest.TestCase):
    def test_blocked_without_approval(self):
        r = _run(operator_approved=False)
        self.assertEqual(r["lane_j_status"], LANE_J_STATUS_BLOCKED)

    def test_blocked_reason_mentions_operator(self):
        r = _run(operator_approved=False)
        self.assertTrue(
            any("operator_approved" in reason for reason in r["rejection_reasons"])
        )

    def test_approved_gives_locked_review(self):
        r = _run(operator_approved=True)
        self.assertEqual(r["lane_j_status"], LANE_J_STATUS_LOCKED_REVIEW)

    def test_hard_locks_true_on_blocked(self):
        r = _run(operator_approved=False)
        for k, v in r["hard_locks"].items():
            self.assertTrue(v, f"hard_locks[{k!r}] must be True on blocked result")

    def test_locked_state_all_false_on_blocked(self):
        r = _run(operator_approved=False)
        for k, v in r["locked_state"].items():
            self.assertFalse(v, f"locked_state[{k!r}] must be False on blocked result")

    def test_zero_unlocked_on_blocked(self):
        r = _run(operator_approved=False)
        self.assertEqual(r["financial_actions_unlocked"], 0)


# ============================================================
# Proof 2 — Lane J status is LOCKED_REVIEW, never UNLOCKED
# ============================================================

class LaneJStatusTests(unittest.TestCase):
    def test_status_is_locked_review_when_approved(self):
        r = _run()
        self.assertEqual(r["lane_j_status"], LANE_J_STATUS_LOCKED_REVIEW)

    def test_status_constant_value(self):
        self.assertEqual(LANE_J_STATUS_LOCKED_REVIEW, "LANE_J_LOCKED_REVIEW")

    def test_status_never_contains_unlocked(self):
        for approved in (True, False):
            r = _run(operator_approved=approved)
            self.assertNotIn("UNLOCKED", r["lane_j_status"])
            self.assertNotIn("ACTIVE", r["lane_j_status"])

    def test_blocked_constant_value(self):
        self.assertEqual(LANE_J_STATUS_BLOCKED, "LANE_J_BLOCKED")

    def test_only_two_possible_statuses(self):
        approved_status = _run(operator_approved=True)["lane_j_status"]
        blocked_status = _run(operator_approved=False)["lane_j_status"]
        self.assertIn(approved_status, {LANE_J_STATUS_LOCKED_REVIEW, LANE_J_STATUS_BLOCKED})
        self.assertIn(blocked_status, {LANE_J_STATUS_LOCKED_REVIEW, LANE_J_STATUS_BLOCKED})

    def test_locked_review_has_no_rejection_reasons(self):
        r = _run()
        self.assertEqual(r["rejection_reasons"], [])

    def test_lane_j_activated_always_false(self):
        for approved in (True, False):
            r = _run(operator_approved=approved)
            self.assertFalse(r["locked_state"]["lane_j_activated"])


# ============================================================
# Proof 3 — BUY remains locked
# ============================================================

class LaneJBuyLockedTests(unittest.TestCase):
    def test_buy_enabled_is_false(self):
        r = _run()
        self.assertFalse(r["buy_enabled"])

    def test_buy_unlock_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_state"]["buy_unlock_active"])

    def test_no_buy_unlock_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_buy_unlock"])

    def test_buy_locked_on_blocked_result(self):
        r = _run(operator_approved=False)
        self.assertFalse(r["buy_enabled"])
        self.assertFalse(r["locked_state"]["buy_unlock_active"])


# ============================================================
# Proof 4 — SELL remains locked
# ============================================================

class LaneJSellLockedTests(unittest.TestCase):
    def test_sell_enabled_is_false(self):
        r = _run()
        self.assertFalse(r["sell_enabled"])

    def test_sell_unlock_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_state"]["sell_unlock_active"])

    def test_no_sell_unlock_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_sell_unlock"])


# ============================================================
# Proof 5 — HOLD remains locked
# ============================================================

class LaneJHoldLockedTests(unittest.TestCase):
    def test_hold_enabled_is_false(self):
        r = _run()
        self.assertFalse(r["hold_enabled"])

    def test_hold_unlock_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_state"]["hold_unlock_active"])

    def test_no_hold_unlock_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_hold_unlock"])


# ============================================================
# Proof 6 — WAIT/AVOID/NO_ACTION are not created here
# ============================================================

class LaneJWaitAvoidNoActionTests(unittest.TestCase):
    def test_no_wait_avoid_no_action_creation_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_wait_avoid_no_action_creation"])

    def test_paper_decisions_created_is_zero(self):
        r = _run()
        self.assertEqual(r["paper_decisions_created"], 0)

    def test_paper_decisions_zero_on_blocked(self):
        r = _run(operator_approved=False)
        self.assertEqual(r["paper_decisions_created"], 0)


# ============================================================
# Proof 7 — paper decisions remain locked
# ============================================================

class LaneJPaperDecisionLockedTests(unittest.TestCase):
    def test_no_paper_decision_creation_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_paper_decision_creation"])

    def test_paper_decision_creation_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_state"]["paper_decision_creation_active"])

    def test_paper_decisions_created_always_zero(self):
        for approved in (True, False):
            r = _run(operator_approved=approved)
            self.assertEqual(r["paper_decisions_created"], 0)


# ============================================================
# Proof 8 — paper positions remain locked
# ============================================================

class LaneJPaperPositionLockedTests(unittest.TestCase):
    def test_no_paper_position_creation_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_paper_position_creation"])

    def test_paper_positions_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_state"]["paper_positions_active"])

    def test_paper_positions_created_always_zero(self):
        for approved in (True, False):
            r = _run(operator_approved=approved)
            self.assertEqual(r["paper_positions_created"], 0)


# ============================================================
# Proof 9 — trade events remain locked
# ============================================================

class LaneJTradeEventLockedTests(unittest.TestCase):
    def test_no_trade_event_creation_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_trade_event_creation"])

    def test_trade_events_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_state"]["trade_events_active"])

    def test_trade_events_created_always_zero(self):
        for approved in (True, False):
            r = _run(operator_approved=approved)
            self.assertEqual(r["trade_events_created"], 0)


# ============================================================
# Proof 10 — paper trade audits remain locked
# ============================================================

class LaneJPaperTradeAuditLockedTests(unittest.TestCase):
    def test_no_paper_trade_audit_creation_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_paper_trade_audit_creation"])

    def test_paper_trade_audits_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_state"]["paper_trade_audits_active"])


# ============================================================
# Proof 11 — PnL remains locked
# ============================================================

class LaneJPnlLockedTests(unittest.TestCase):
    def test_no_pnl_creation_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_pnl_creation"])

    def test_pnl_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_state"]["pnl_active"])

    def test_pnl_created_always_zero(self):
        for approved in (True, False):
            r = _run(operator_approved=approved)
            self.assertEqual(r["pnl_created"], 0)


# ============================================================
# Proof 12 — live trading / wallet / private keys / signing remain locked
# ============================================================

class LaneJLiveTradingLockedTests(unittest.TestCase):
    def test_no_live_trading_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_live_trading"])

    def test_no_wallet_private_key_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_wallet_private_key"])

    def test_no_signing_execution_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_signing_execution"])

    def test_live_trading_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_state"]["live_trading_active"])

    def test_wallet_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_state"]["wallet_active"])


# ============================================================
# Proof 13 — paid APIs remain locked
# ============================================================

class LaneJPaidApiLockedTests(unittest.TestCase):
    def test_no_paid_api_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_paid_api"])

    def test_no_source_fetching_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_source_fetching"])


# ============================================================
# Proof 14 — scoring/ranking/confidence/weighted logic remains locked
# ============================================================

class LaneJScoringLockedTests(unittest.TestCase):
    def test_no_scoring_ranking_confidence_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_scoring_ranking_confidence"])


# ============================================================
# Proof 15 — embeddings/vectors remain locked
# ============================================================

class LaneJEmbeddingsLockedTests(unittest.TestCase):
    def test_no_embeddings_vectors_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_embeddings_vectors"])


# ============================================================
# Proof 16 — Lane 9 policy is documentation-only, not executable approval
# ============================================================

class LaneJLane9PolicyTests(unittest.TestCase):
    def test_lane_9_policy_ref_constant_points_to_doc(self):
        self.assertIn("buy-unlock-preconditions", LANE_J_LANE9_POLICY_REF)

    def test_lane_9_executable_approval_is_false(self):
        r = _run()
        self.assertFalse(r["locked_state"]["lane_9_executable_approval"])

    def test_lane_9_policy_ref_in_result(self):
        r = _run()
        self.assertIn("lane_9_buy_preconditions", r["policy_references"])
        ref = r["policy_references"]["lane_9_buy_preconditions"]
        self.assertIn("buy-unlock-preconditions", ref)

    def test_lane_9_policy_note_says_documentation_only(self):
        r = _run()
        note = r["policy_references"]["note"]
        self.assertIn("documentation-only", note)

    def test_lane_9_does_not_enable_buy(self):
        r = _run()
        self.assertFalse(r["buy_enabled"])
        self.assertFalse(r["locked_state"]["buy_unlock_active"])


# ============================================================
# Proof 17 — Lane 10 policy is documentation-only, not executable approval
# ============================================================

class LaneJLane10PolicyTests(unittest.TestCase):
    def test_lane_10_policy_ref_constant_points_to_doc(self):
        self.assertIn("paper-position-reactivation-review", LANE_J_LANE10_POLICY_REF)

    def test_lane_10_executable_approval_is_false(self):
        r = _run()
        self.assertFalse(r["locked_state"]["lane_10_executable_approval"])

    def test_lane_10_policy_ref_in_result(self):
        r = _run()
        self.assertIn("lane_10_position_review", r["policy_references"])
        ref = r["policy_references"]["lane_10_position_review"]
        self.assertIn("paper-position-reactivation-review", ref)

    def test_lane_10_does_not_enable_positions(self):
        r = _run()
        self.assertFalse(r["locked_state"]["paper_positions_active"])
        self.assertEqual(r["paper_positions_created"], 0)

    def test_lane_10_does_not_enable_pnl(self):
        r = _run()
        self.assertFalse(r["locked_state"]["pnl_active"])
        self.assertEqual(r["pnl_created"], 0)


# ============================================================
# Proof 18 — Lane I 4h/12h/24h completion does not unlock financial actions
# ============================================================

class LaneJLaneICompletionTests(unittest.TestCase):
    def test_lane_i_stages_anchored_constant_contains_all_three(self):
        self.assertIn("WINDOW_4H", LANE_J_LANE_I_STAGES_ANCHORED)
        self.assertIn("WINDOW_12H", LANE_J_LANE_I_STAGES_ANCHORED)
        self.assertIn("WINDOW_24H", LANE_J_LANE_I_STAGES_ANCHORED)

    def test_lane_i_unlocked_financial_actions_is_false(self):
        r = _run()
        self.assertFalse(r["locked_state"]["lane_i_unlocked_financial_actions"])

    def test_lane_i_completion_note_mentions_no_unlock(self):
        r = _run()
        note = r["lane_i_completion_note"]
        self.assertIn("does NOT unlock", note)

    def test_lane_i_completion_note_mentions_4h(self):
        r = _run()
        self.assertIn("4h", r["lane_i_completion_note"].lower()
                       + r["lane_i_completion_note"])

    def test_buy_still_locked_after_lane_i(self):
        r = _run()
        self.assertFalse(r["buy_enabled"])

    def test_positions_still_locked_after_lane_i(self):
        r = _run()
        self.assertFalse(r["locked_state"]["paper_positions_active"])
        self.assertEqual(r["paper_positions_created"], 0)

    def test_pnl_still_locked_after_lane_i(self):
        r = _run()
        self.assertFalse(r["locked_state"]["pnl_active"])
        self.assertEqual(r["pnl_created"], 0)

    def test_retrieval_still_locked_after_lane_i(self):
        r = _run()
        self.assertFalse(r["retrieval_activated"])
        self.assertFalse(r["locked_state"]["retrieval_active"])


# ============================================================
# Proof 19 — no DB/CLI/scheduler/source/retrieval/paper behavior changes
# ============================================================

class LaneJNoBehaviorChangeTests(unittest.TestCase):
    def test_no_db_writes_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_db_writes"])

    def test_no_scheduler_bypass_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_scheduler_bypass"])

    def test_no_retrieval_activation_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_retrieval_activation"])

    def test_retrieval_activated_is_false(self):
        r = _run()
        self.assertFalse(r["retrieval_activated"])

    def test_module_does_not_import_db_libraries(self):
        import printer_v1.operator_cli.lane_j_financial_action_lock_review as lib
        with open(lib.__file__, encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("sqlalchemy", source)

    def test_module_does_not_import_prior_lane_modules(self):
        import printer_v1.operator_cli.lane_j_financial_action_lock_review as lib
        with open(lib.__file__, encoding="utf-8") as fh:
            source = fh.read()
        forbidden = [
            "lane_h_", "lane_i_4h_", "lane_i_12h_", "lane_i_24h_",
            "e2j_", "e2q_", "e2x_", "e2y_", "e2z_",
        ]
        for name in forbidden:
            self.assertNotIn(name, source, f"Lane J must not import {name}")

    def test_no_clean_memory_creation_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_clean_memory_creation"])

    def test_function_is_stateless(self):
        r1 = _run()
        r2 = _run()
        self.assertEqual(r1["lane_j_status"], r2["lane_j_status"])
        self.assertEqual(r1["financial_actions_unlocked"], r2["financial_actions_unlocked"])


# ============================================================
# Proof 20 — zero unlocked financial actions is the only valid outcome
# ============================================================

class LaneJZeroUnlockedTests(unittest.TestCase):
    def test_financial_actions_unlocked_is_zero_when_approved(self):
        r = _run()
        self.assertEqual(r["financial_actions_unlocked"], 0)

    def test_financial_actions_unlocked_is_zero_when_blocked(self):
        r = _run(operator_approved=False)
        self.assertEqual(r["financial_actions_unlocked"], 0)

    def test_all_locked_state_values_are_false(self):
        r = _run()
        for k, v in r["locked_state"].items():
            self.assertFalse(v, f"locked_state[{k!r}] must be False")

    def test_all_hard_locks_are_true(self):
        r = _run()
        for k, v in r["hard_locks"].items():
            self.assertTrue(v, f"hard_locks[{k!r}] must be True")

    def test_hard_lock_count_is_sufficient(self):
        r = _run()
        self.assertGreaterEqual(len(r["hard_locks"]), 18)

    def test_locked_state_count_is_sufficient(self):
        r = _run()
        self.assertGreaterEqual(len(r["locked_state"]), 12)

    def test_zero_paper_decisions_on_any_outcome(self):
        for approved in (True, False):
            r = _run(operator_approved=approved)
            self.assertEqual(r["paper_decisions_created"], 0)

    def test_zero_pnl_on_any_outcome(self):
        for approved in (True, False):
            r = _run(operator_approved=approved)
            self.assertEqual(r["pnl_created"], 0)

    def test_zero_trade_events_on_any_outcome(self):
        for approved in (True, False):
            r = _run(operator_approved=approved)
            self.assertEqual(r["trade_events_created"], 0)

    def test_zero_paper_positions_on_any_outcome(self):
        for approved in (True, False):
            r = _run(operator_approved=approved)
            self.assertEqual(r["paper_positions_created"], 0)


if __name__ == "__main__":
    unittest.main()

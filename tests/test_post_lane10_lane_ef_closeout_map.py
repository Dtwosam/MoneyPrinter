"""
Post-Lane 10 Lane E/F Closeout Map

Twenty boundary proofs:
1.  operator_approved is required
2.  status is READ_ONLY_CLOSEOUT or BLOCKED only
3.  Lane E is advanced but not blindly assumed complete
4.  Lane F is mostly done/hardened but not blindly assumed complete
5.  E2X and E2Y are safety hardening, not replacement roadmap lanes
6.  Post-E2Y revised proposal remains documentation-only and NOT ACTIVE
7.  E2Z clean memory creation boundary status is honestly classified
8.  real persistent clean-memory creation is not claimed unless proven by code/tests
9.  no real DB write path is introduced by this lane
10. no retrieval activation is introduced
11. no paper decision creation is introduced
12. 5m remains support-only
13. BUY/SELL/HOLD remain locked
14. paper positions remain locked
15. trade events/audits/PnL remain locked
16. no source/scheduler/runtime behavior changes
17. output includes remaining_gaps list
18. output includes recommended_next_action
19. output includes locked_capabilities
20. zero unlocked capabilities is the only valid outcome
"""

import pathlib
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.operator_cli.lane_ef_closeout_map import (
    E2X_CLASSIFICATION,
    E2Y_CLASSIFICATION,
    E2Z_CLASSIFICATION,
    EF_STATUS_BLOCKED,
    EF_STATUS_READ_ONLY_CLOSEOUT,
    LANE_E_STATUS,
    LANE_F_STATUS,
    POST_E2Y_REVISED_PROPOSAL_STATUS,
    RECOMMENDED_NEXT_ACTION,
    REMAINING_GAPS,
    _HARD_LOCKS,
    _LOCKED_CAPABILITIES,
    build_ef_closeout_map,
)


def _run(*, operator_approved=True):
    return build_ef_closeout_map(operator_approved=operator_approved)


# ============================================================
# Proof 1 — operator_approved is required
# ============================================================

class EFCloseoutApprovalTests(unittest.TestCase):
    def test_blocked_without_approval(self):
        r = _run(operator_approved=False)
        self.assertEqual(r["ef_status"], EF_STATUS_BLOCKED)

    def test_blocked_reason_mentions_operator(self):
        r = _run(operator_approved=False)
        self.assertTrue(
            any("operator_approved" in reason for reason in r["rejection_reasons"])
        )

    def test_approved_gives_read_only_closeout(self):
        r = _run()
        self.assertEqual(r["ef_status"], EF_STATUS_READ_ONLY_CLOSEOUT)

    def test_hard_locks_true_on_blocked(self):
        r = _run(operator_approved=False)
        for k, v in r["hard_locks"].items():
            self.assertTrue(v, f"hard_locks[{k!r}] must be True on blocked")

    def test_locked_capabilities_all_false_on_blocked(self):
        r = _run(operator_approved=False)
        for k, v in r["locked_capabilities"].items():
            self.assertFalse(v, f"locked_capabilities[{k!r}] must be False on blocked")

    def test_zero_unlocked_on_blocked(self):
        r = _run(operator_approved=False)
        self.assertEqual(r["unlocked_capabilities_count"], 0)


# ============================================================
# Proof 2 — status is READ_ONLY_CLOSEOUT or BLOCKED only
# ============================================================

class EFCloseoutStatusTests(unittest.TestCase):
    def test_status_constant_read_only_closeout(self):
        self.assertEqual(EF_STATUS_READ_ONLY_CLOSEOUT, "EF_READ_ONLY_CLOSEOUT")

    def test_status_constant_blocked(self):
        self.assertEqual(EF_STATUS_BLOCKED, "EF_BLOCKED")

    def test_status_never_contains_unlocked(self):
        for approved in (True, False):
            r = _run(operator_approved=approved)
            self.assertNotIn("UNLOCKED", r["ef_status"])
            self.assertNotIn("ACTIVE", r["ef_status"])
            self.assertNotIn("COMPLETE", r["ef_status"])

    def test_only_two_possible_statuses(self):
        valid = {EF_STATUS_READ_ONLY_CLOSEOUT, EF_STATUS_BLOCKED}
        for approved in (True, False):
            r = _run(operator_approved=approved)
            self.assertIn(r["ef_status"], valid)

    def test_approved_has_no_rejection_reasons(self):
        r = _run()
        self.assertEqual(r["rejection_reasons"], [])


# ============================================================
# Proof 3 — Lane E is advanced but not blindly assumed complete
# ============================================================

class EFCloseoutLaneETests(unittest.TestCase):
    def test_lane_e_status_is_advanced_partial(self):
        r = _run()
        self.assertEqual(r["lane_e_status"], LANE_E_STATUS)
        self.assertEqual(r["lane_e_status"], "ADVANCED_PARTIAL")

    def test_lane_e_not_marked_complete(self):
        r = _run()
        self.assertNotIn("COMPLETE", r["lane_e_status"])

    def test_lane_e_note_mentions_readiness_scaffolding(self):
        r = _run()
        note = r["lane_e_note"].lower()
        self.assertIn("readiness", note)

    def test_lane_e_note_says_no_real_cycle_run(self):
        r = _run()
        note = r["lane_e_note"].lower()
        self.assertIn("no real", note)

    def test_bounded_cycle_runtime_exists_is_false(self):
        r = _run()
        self.assertFalse(r["bounded_cycle_runtime_exists"])


# ============================================================
# Proof 4 — Lane F is mostly done/hardened but not blindly assumed complete
# ============================================================

class EFCloseoutLaneFTests(unittest.TestCase):
    def test_lane_f_status_is_boundary_complete_no_runtime(self):
        r = _run()
        self.assertEqual(r["lane_f_status"], LANE_F_STATUS)
        self.assertEqual(r["lane_f_status"], "BOUNDARY_COMPLETE_NO_RUNTIME")

    def test_lane_f_not_marked_complete(self):
        r = _run()
        # status contains BOUNDARY_COMPLETE but also NO_RUNTIME — not blindly complete
        self.assertIn("NO_RUNTIME", r["lane_f_status"])

    def test_lane_f_note_mentions_e2v_and_e2w(self):
        r = _run()
        note = r["lane_f_note"].upper()
        self.assertIn("E2V", note)
        self.assertIn("E2W", note)

    def test_lane_f_note_says_5m_support_only(self):
        r = _run()
        note = r["lane_f_note"].lower()
        self.assertIn("support-only", note)

    def test_lane_f_note_says_no_runtime_integration(self):
        r = _run()
        note = r["lane_f_note"].lower()
        self.assertIn("no runtime", note)


# ============================================================
# Proof 5 — E2X and E2Y are safety hardening, not replacement lanes
# ============================================================

class EFCloseoutE2xE2yTests(unittest.TestCase):
    def test_e2x_classification_is_safety_hardening(self):
        r = _run()
        self.assertEqual(r["e2x_classification"], E2X_CLASSIFICATION)
        self.assertIn("SAFETY_HARDENING", r["e2x_classification"])

    def test_e2x_note_says_read_only(self):
        r = _run()
        note = r["e2x_note"].lower()
        self.assertIn("read-only", note)

    def test_e2x_note_says_not_replacement(self):
        r = _run()
        note = r["e2x_note"].lower()
        self.assertIn("not", note)

    def test_e2y_classification_is_safety_hardening(self):
        r = _run()
        self.assertEqual(r["e2y_classification"], E2Y_CLASSIFICATION)
        self.assertIn("SAFETY_HARDENING", r["e2y_classification"])

    def test_e2y_note_says_read_only(self):
        r = _run()
        note = r["e2y_note"].lower()
        self.assertIn("read-only", note)

    def test_e2y_note_says_does_not_create_memory(self):
        r = _run()
        note = r["e2y_note"].lower()
        self.assertIn("not create memory", note)


# ============================================================
# Proof 6 — Post-E2Y revised proposal is documentation-only and NOT ACTIVE
# ============================================================

class EFCloseoutPostE2yProposalTests(unittest.TestCase):
    def test_post_e2y_revised_proposal_status_is_not_active(self):
        r = _run()
        self.assertEqual(
            r["post_e2y_revised_proposal_status"],
            POST_E2Y_REVISED_PROPOSAL_STATUS,
        )
        self.assertIn("NOT_ACTIVE", r["post_e2y_revised_proposal_status"])

    def test_post_e2y_status_contains_proposed_only(self):
        r = _run()
        self.assertIn("PROPOSED_ONLY", r["post_e2y_revised_proposal_status"])

    def test_post_e2y_note_says_not_active(self):
        r = _run()
        note = r["post_e2y_revised_proposal_note"].upper()
        self.assertIn("NOT ACTIVE", note)

    def test_post_e2y_note_references_the_doc(self):
        r = _run()
        self.assertIn("post-e2y-revised-next-build-order", r["post_e2y_revised_proposal_note"])

    def test_post_e2y_proposal_not_adopted_in_locked_capabilities(self):
        r = _run()
        self.assertFalse(r["locked_capabilities"]["post_e2y_revised_proposal_adopted"])

    def test_no_post_e2y_proposal_adoption_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_post_e2y_proposal_adoption"])


# ============================================================
# Proof 7 — E2Z status honestly classified
# ============================================================

class EFCloseoutE2zClassificationTests(unittest.TestCase):
    def test_e2z_classification_is_single_window_writer(self):
        r = _run()
        self.assertEqual(r["e2z_classification"], E2Z_CLASSIFICATION)
        self.assertIn("SINGLE_WINDOW_WRITER", r["e2z_classification"])

    def test_e2z_classification_says_no_bounded_cycle(self):
        r = _run()
        self.assertIn("NO_BOUNDED_CYCLE", r["e2z_classification"])

    def test_e2z_note_says_can_write(self):
        r = _run()
        note = r["e2z_note"].lower()
        self.assertIn("can write", note)

    def test_e2z_note_says_not_wired_to_bounded_cycle(self):
        r = _run()
        note = r["e2z_note"].lower()
        self.assertIn("not wired", note)

    def test_e2z_note_mentions_printer_episodes(self):
        r = _run()
        self.assertIn("printer_episodes", r["e2z_note"])


# ============================================================
# Proof 8 — real persistent clean-memory creation not claimed without proof
# ============================================================

class EFCloseoutCleanMemoryProofTests(unittest.TestCase):
    def test_clean_memory_creation_proven_by_e2z_is_true(self):
        # E2Z DOES have a real write path — this must be honestly acknowledged
        r = _run()
        self.assertTrue(r["clean_memory_creation_proven_by_e2z"])

    def test_bounded_cycle_runtime_exists_is_false(self):
        # but the full wired bounded cycle does NOT exist
        r = _run()
        self.assertFalse(r["bounded_cycle_runtime_exists"])

    def test_bounded_cycle_runtime_wired_in_locked_capabilities(self):
        r = _run()
        self.assertFalse(r["locked_capabilities"]["bounded_cycle_runtime_wired"])

    def test_no_clean_memory_creation_claimed_without_proof_lock(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_clean_memory_creation_claimed_without_proof"])

    def test_memory_rows_created_is_zero(self):
        r = _run()
        self.assertEqual(r["memory_rows_created"], 0)


# ============================================================
# Proof 9 — no real DB write path introduced by this lane
# ============================================================

class EFCloseoutNoDbWriteTests(unittest.TestCase):
    def test_no_db_writes_introduced_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_db_writes_introduced"])

    def test_module_does_not_import_db_libraries(self):
        import printer_v1.operator_cli.lane_ef_closeout_map as lib
        with open(lib.__file__, encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("sqlalchemy", source)

    def test_memory_rows_created_zero_on_blocked(self):
        r = _run(operator_approved=False)
        self.assertEqual(r["memory_rows_created"], 0)

    def test_memory_creation_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_capabilities"]["memory_creation_active"])

    def test_no_memory_creation_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_memory_creation"])


# ============================================================
# Proof 10 — no retrieval activation introduced
# ============================================================

class EFCloseoutNoRetrievalTests(unittest.TestCase):
    def test_no_retrieval_activation_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_retrieval_activation"])

    def test_retrieval_activated_is_false(self):
        r = _run()
        self.assertFalse(r["retrieval_activated"])

    def test_retrieval_active_in_locked_capabilities_is_false(self):
        r = _run()
        self.assertFalse(r["locked_capabilities"]["retrieval_active"])

    def test_retrieval_false_on_blocked(self):
        r = _run(operator_approved=False)
        self.assertFalse(r["retrieval_activated"])


# ============================================================
# Proof 11 — no paper decision creation introduced
# ============================================================

class EFCloseoutNoPaperDecisionTests(unittest.TestCase):
    def test_no_paper_decision_creation_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_paper_decision_creation"])

    def test_paper_decisions_created_is_zero(self):
        r = _run()
        self.assertEqual(r["paper_decisions_created"], 0)

    def test_paper_decision_creation_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_capabilities"]["paper_decision_creation_active"])

    def test_paper_decisions_zero_on_blocked(self):
        r = _run(operator_approved=False)
        self.assertEqual(r["paper_decisions_created"], 0)


# ============================================================
# Proof 12 — 5m remains support-only
# ============================================================

class EFCloseout5mSupportOnlyTests(unittest.TestCase):
    def test_no_5m_main_outcome_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_5m_main_outcome"])

    def test_5m_main_outcome_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_capabilities"]["5m_main_outcome_active"])

    def test_lane_f_note_confirms_5m_support_only(self):
        r = _run()
        self.assertIn("support-only", r["lane_f_note"].lower())


# ============================================================
# Proof 13 — BUY/SELL/HOLD remain locked
# ============================================================

class EFCloseoutBuySelHoldLockedTests(unittest.TestCase):
    def test_no_buy_sell_hold_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_buy_sell_hold"])

    def test_buy_enabled_is_false(self):
        r = _run()
        self.assertFalse(r["buy_enabled"])

    def test_sell_enabled_is_false(self):
        r = _run()
        self.assertFalse(r["sell_enabled"])

    def test_hold_enabled_is_false(self):
        r = _run()
        self.assertFalse(r["hold_enabled"])

    def test_buy_unlock_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_capabilities"]["buy_unlock_active"])

    def test_sell_unlock_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_capabilities"]["sell_unlock_active"])

    def test_hold_unlock_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_capabilities"]["hold_unlock_active"])


# ============================================================
# Proof 14 — paper positions remain locked
# ============================================================

class EFCloseoutPositionsLockedTests(unittest.TestCase):
    def test_no_positions_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_positions"])

    def test_paper_positions_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_capabilities"]["paper_positions_active"])

    def test_paper_positions_created_is_zero(self):
        r = _run()
        self.assertEqual(r["paper_positions_created"], 0)


# ============================================================
# Proof 15 — trade events/audits/PnL remain locked
# ============================================================

class EFCloseoutTradeEventsPnlLockedTests(unittest.TestCase):
    def test_no_trade_events_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_trade_events"])

    def test_no_paper_trade_audits_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_paper_trade_audits"])

    def test_no_pnl_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_pnl"])

    def test_trade_events_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_capabilities"]["trade_events_active"])

    def test_paper_trade_audits_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_capabilities"]["paper_trade_audits_active"])

    def test_pnl_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_capabilities"]["pnl_active"])

    def test_trade_events_created_is_zero(self):
        r = _run()
        self.assertEqual(r["trade_events_created"], 0)

    def test_pnl_created_is_zero(self):
        r = _run()
        self.assertEqual(r["pnl_created"], 0)


# ============================================================
# Proof 16 — no source/scheduler/runtime behavior changes
# ============================================================

class EFCloseoutNoRuntimeChangeTests(unittest.TestCase):
    def test_no_source_fetching_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_source_fetching"])

    def test_no_scheduler_execution_hard_lock_is_true(self):
        r = _run()
        self.assertTrue(r["hard_locks"]["no_scheduler_execution"])

    def test_source_fetching_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_capabilities"]["source_fetching_active"])

    def test_scheduler_execution_active_is_false(self):
        r = _run()
        self.assertFalse(r["locked_capabilities"]["scheduler_execution_active"])

    def test_module_does_not_import_prior_lane_modules(self):
        import printer_v1.operator_cli.lane_ef_closeout_map as lib
        with open(lib.__file__, encoding="utf-8") as fh:
            source = fh.read()
        forbidden = [
            "lane_h_", "lane_i_4h_", "lane_i_12h_", "lane_i_24h_", "lane_j_",
            "e2z_clean", "e2x_15m", "e2y_15m", "e2v_5m", "e2w_5m",
        ]
        for name in forbidden:
            self.assertNotIn(name, source, f"EF closeout map must not import {name}")

    def test_function_is_stateless(self):
        r1 = _run()
        r2 = _run()
        self.assertEqual(r1["ef_status"], r2["ef_status"])
        self.assertEqual(r1["unlocked_capabilities_count"], r2["unlocked_capabilities_count"])


# ============================================================
# Proof 17 — output includes remaining_gaps list
# ============================================================

class EFCloseoutRemainingGapsTests(unittest.TestCase):
    def test_remaining_gaps_present_in_result(self):
        r = _run()
        self.assertIn("remaining_gaps", r)

    def test_remaining_gaps_is_list(self):
        r = _run()
        self.assertIsInstance(r["remaining_gaps"], list)

    def test_remaining_gaps_not_empty(self):
        r = _run()
        self.assertGreater(len(r["remaining_gaps"]), 0)

    def test_remaining_gaps_mentions_bounded_cycle(self):
        r = _run()
        combined = " ".join(r["remaining_gaps"]).lower()
        self.assertIn("bounded", combined)

    def test_remaining_gaps_mentions_e2z(self):
        r = _run()
        combined = " ".join(r["remaining_gaps"])
        self.assertIn("E2Z", combined)

    def test_remaining_gaps_constant_matches_result(self):
        r = _run()
        self.assertEqual(r["remaining_gaps"], list(REMAINING_GAPS))


# ============================================================
# Proof 18 — output includes recommended_next_action
# ============================================================

class EFCloseoutRecommendedNextActionTests(unittest.TestCase):
    def test_recommended_next_action_present(self):
        r = _run()
        self.assertIn("recommended_next_action", r)

    def test_recommended_next_action_is_string(self):
        r = _run()
        self.assertIsInstance(r["recommended_next_action"], str)

    def test_recommended_next_action_not_empty(self):
        r = _run()
        self.assertGreater(len(r["recommended_next_action"]), 10)

    def test_recommended_next_action_says_read_only(self):
        r = _run()
        self.assertIn("Read-only", r["recommended_next_action"])

    def test_recommended_next_action_mentions_e2x_e2y_e2z(self):
        r = _run()
        action = r["recommended_next_action"]
        self.assertIn("E2X", action)
        self.assertIn("E2Y", action)
        self.assertIn("E2Z", action)

    def test_recommended_next_action_constant_matches_result(self):
        r = _run()
        self.assertEqual(r["recommended_next_action"], RECOMMENDED_NEXT_ACTION)


# ============================================================
# Proof 19 — output includes locked_capabilities
# ============================================================

class EFCloseoutLockedCapabilitiesTests(unittest.TestCase):
    def test_locked_capabilities_present_in_result(self):
        r = _run()
        self.assertIn("locked_capabilities", r)

    def test_locked_capabilities_is_dict(self):
        r = _run()
        self.assertIsInstance(r["locked_capabilities"], dict)

    def test_locked_capabilities_not_empty(self):
        r = _run()
        self.assertGreater(len(r["locked_capabilities"]), 0)

    def test_locked_capabilities_all_false(self):
        r = _run()
        for k, v in r["locked_capabilities"].items():
            self.assertFalse(v, f"locked_capabilities[{k!r}] must be False")

    def test_locked_capabilities_count_is_sufficient(self):
        r = _run()
        self.assertGreaterEqual(len(r["locked_capabilities"]), 12)


# ============================================================
# Proof 20 — zero unlocked capabilities is the only valid outcome
# ============================================================

class EFCloseoutZeroUnlockedTests(unittest.TestCase):
    def test_unlocked_capabilities_count_zero_when_approved(self):
        r = _run()
        self.assertEqual(r["unlocked_capabilities_count"], 0)

    def test_unlocked_capabilities_count_zero_when_blocked(self):
        r = _run(operator_approved=False)
        self.assertEqual(r["unlocked_capabilities_count"], 0)

    def test_all_hard_locks_true_on_approved(self):
        r = _run()
        for k, v in r["hard_locks"].items():
            self.assertTrue(v, f"hard_locks[{k!r}] must be True")

    def test_all_hard_locks_true_on_blocked(self):
        r = _run(operator_approved=False)
        for k, v in r["hard_locks"].items():
            self.assertTrue(v, f"hard_locks[{k!r}] must be True on blocked")

    def test_all_locked_capabilities_false_on_approved(self):
        r = _run()
        for k, v in r["locked_capabilities"].items():
            self.assertFalse(v, f"locked_capabilities[{k!r}] must be False")

    def test_zero_paper_positions_on_any_outcome(self):
        for approved in (True, False):
            r = _run(operator_approved=approved)
            self.assertEqual(r["paper_positions_created"], 0)

    def test_zero_pnl_on_any_outcome(self):
        for approved in (True, False):
            r = _run(operator_approved=approved)
            self.assertEqual(r["pnl_created"], 0)

    def test_zero_trade_events_on_any_outcome(self):
        for approved in (True, False):
            r = _run(operator_approved=approved)
            self.assertEqual(r["trade_events_created"], 0)

    def test_zero_memory_rows_on_any_outcome(self):
        for approved in (True, False):
            r = _run(operator_approved=approved)
            self.assertEqual(r["memory_rows_created"], 0)

    def test_hard_lock_count_is_sufficient(self):
        r = _run()
        self.assertGreaterEqual(len(r["hard_locks"]), 16)


if __name__ == "__main__":
    unittest.main()

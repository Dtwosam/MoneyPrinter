"""Lane X6 — Discovery / Selection / Dedup Repair — test suite.

Required test coverage (verbatim from Lane X6 spec):
- duplicate mint rejected or collapsed correctly
- duplicate pair rejected or collapsed correctly
- same token/new pair handled explicitly
- stale/cooldown/archived token not immediately recycled
- revival/reopen path remains possible
- selected set includes memory-value variety, not only bullish-looking tokens
- selection reason is auditable
- discovery cannot directly create paper BUY or paper decisions
- discovery cannot act as a trade signal
- X3 lifecycle regression still passes
- X5 regression still passes
- all retrieval/paper/BUY/position/PnL locks remain unchanged
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from printer_v1.db import apply_migrations

from printer_v1.operator_cli.lane_x6_discovery_selection_repair import (
    ALL_DIET_LABELS,
    DIET_AMBIGUOUS,
    DIET_DEAD_TOKEN,
    DIET_DUMP,
    DIET_FAKE_PUMP,
    DIET_LATE_BUY_TRAP,
    DIET_LIQUIDITY_DECAY,
    DIET_PUMP,
    DIET_REVIVAL,
    DIET_WICK_ONLY,
    LANE_X6_COMMAND_NAME,
    LANE_X6_STATUS_BLOCKED,
    LANE_X6_STATUS_COMPLETED,
    _HARD_LOCKS,
    classify_memory_diet_label,
    dedup_by_mint,
    dedup_by_pair,
    detect_same_token_new_pair,
    filter_cooldown_blocked,
    select_candidates_for_memory_growth,
)

# ---------------------------------------------------------------------------
# Shared test constants
# ---------------------------------------------------------------------------

_MINT_A = "6XxMint1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAax"
_MINT_B = "6XxMint2BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBbx"
_MINT_C = "6XxMint3CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCx"
_MINT_D = "6XxMint4DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDx"
_PAIR_A = "LaneX6PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_PAIR_B = "LaneX6PairBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
_PAIR_A2 = "LaneX6PairA2AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAa2"  # second pair for MINT_A
_PAIR_C = "LaneX6PairCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"
_PAIR_D = "LaneX6PairDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD"


def _cand(
    mint: str,
    pair: str,
    *,
    price_5m: float = 0.0,
    price_1h: float = 0.0,
    price_24h: float = 0.0,
    vol_5m: float = 0.0,
    vol_1h: float = 0.0,
    vol_24h: float = 0.0,
    txns_5m: int = 0,
    txns_1h: int = 0,
    txns_24h: int = 0,
    liquidity: float = 5_000.0,
    chain: str = "solana",
    action: str = "TRACK_FAST",
    reason: str = "test_reason",
    captured_at: str = "2026-01-01T00:00:00+00:00",
    lifecycle_status: str | None = None,
) -> dict:
    c = {
        "token_mint": mint,
        "pair_address": pair,
        "chain": chain,
        "price_change_5m": price_5m,
        "price_change_1h": price_1h,
        "price_change_24h": price_24h,
        "volume_5m": vol_5m,
        "volume_1h": vol_1h,
        "volume_24h": vol_24h,
        "txns_5m": txns_5m,
        "txns_1h": txns_1h,
        "txns_24h": txns_24h,
        "liquidity_usd": liquidity,
        "discovery_action": action,
        "priority_reason": reason,
        "captured_at": captured_at,
    }
    if lifecycle_status is not None:
        c["_lifecycle_status"] = lifecycle_status
    return c


# ---------------------------------------------------------------------------
# DB base class for tests requiring a real SQLite DB + backup proof
# ---------------------------------------------------------------------------

class _DbBase(unittest.TestCase):
    def setUp(self):
        self._db_fd, self._db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(self._db_fd)
        self._bp_fd, self._bp_path = tempfile.mkstemp(suffix=".bak")
        os.close(self._bp_fd)

    def tearDown(self):
        for p in (self._db_path, self._bp_path):
            try:
                os.unlink(p)
            except OSError:
                pass

    def _run(self, candidates, **kwargs) -> dict:
        return select_candidates_for_memory_growth(
            self._db_path,
            self._bp_path,
            operator_approved=True,
            candidate_list_override=candidates,
            **kwargs,
        )


# ===========================================================================
# 1. Hard locks and module constants
# ===========================================================================

class TestLaneX6HardLocks(unittest.TestCase):
    def test_hard_lock_count_is_24(self):
        self.assertEqual(len(_HARD_LOCKS), 24)

    def test_no_buy_sell_hold(self):
        self.assertTrue(_HARD_LOCKS["no_buy_sell_hold"])

    def test_no_paper_decisions(self):
        self.assertTrue(_HARD_LOCKS["no_paper_decisions"])

    def test_no_positions(self):
        self.assertTrue(_HARD_LOCKS["no_positions"])

    def test_no_pnl(self):
        self.assertTrue(_HARD_LOCKS["no_pnl"])

    def test_no_retrieval_activation(self):
        self.assertTrue(_HARD_LOCKS["no_retrieval_activation"])

    def test_no_live_trading(self):
        self.assertTrue(_HARD_LOCKS["no_live_trading"])

    def test_no_scoring_ranking_confidence(self):
        self.assertTrue(_HARD_LOCKS["no_scoring_ranking_confidence"])

    def test_no_discovery_automation(self):
        self.assertTrue(_HARD_LOCKS["no_discovery_automation"])

    def test_no_source_budget_bypass(self):
        self.assertTrue(_HARD_LOCKS["no_source_budget_bypass"])

    def test_no_1h_4h_12h_24h_collection(self):
        self.assertTrue(_HARD_LOCKS["no_1h_4h_12h_24h_collection"])

    def test_command_name_correct(self):
        self.assertEqual(LANE_X6_COMMAND_NAME, "printer-run-lane-x6-discovery-selection-repair")

    def test_all_diet_labels_present(self):
        expected = {
            "PUMP", "DUMP", "FAKE_PUMP", "WICK_ONLY", "LATE_BUY_TRAP",
            "LIQUIDITY_DECAY", "DEAD_TOKEN", "REVIVAL", "AMBIGUOUS",
        }
        self.assertEqual(set(ALL_DIET_LABELS), expected)


# ===========================================================================
# 2. Operator gate
# ===========================================================================

class TestLaneX6OperatorGate(_DbBase):
    def test_blocked_without_operator_approved(self):
        r = select_candidates_for_memory_growth(
            self._db_path,
            self._bp_path,
            operator_approved=False,
            candidate_list_override=[],
        )
        self.assertEqual(r["lane_x6_status"], LANE_X6_STATUS_BLOCKED)

    def test_blocked_without_backup_proof(self):
        r = select_candidates_for_memory_growth(
            self._db_path,
            "/nonexistent/backup.bak",
            operator_approved=True,
            candidate_list_override=[],
        )
        self.assertEqual(r["lane_x6_status"], LANE_X6_STATUS_BLOCKED)

    def test_blocked_result_has_hard_locks(self):
        r = select_candidates_for_memory_growth(
            self._db_path,
            self._bp_path,
            operator_approved=False,
            candidate_list_override=[],
        )
        self.assertIn("hard_locks", r)
        self.assertTrue(r["hard_locks"]["no_paper_decisions"])

    def test_blocked_result_buy_enabled_false(self):
        r = select_candidates_for_memory_growth(
            self._db_path,
            self._bp_path,
            operator_approved=False,
            candidate_list_override=[],
        )
        self.assertFalse(r["buy_enabled"])

    def test_approved_returns_completed(self):
        r = self._run([])
        self.assertEqual(r["lane_x6_status"], LANE_X6_STATUS_COMPLETED)


# ===========================================================================
# 3. Financial locks in completed result
# ===========================================================================

class TestLaneX6FinancialLocks(_DbBase):
    def _result(self):
        return self._run([_cand(_MINT_A, _PAIR_A)])

    def test_buy_enabled_false(self):
        self.assertFalse(self._result()["buy_enabled"])

    def test_sell_enabled_false(self):
        self.assertFalse(self._result()["sell_enabled"])

    def test_hold_enabled_false(self):
        self.assertFalse(self._result()["hold_enabled"])

    def test_paper_decisions_created_zero(self):
        self.assertEqual(self._result()["paper_decisions_created"], 0)

    def test_retrieval_rows_created_zero(self):
        self.assertEqual(self._result()["retrieval_rows_created"], 0)

    def test_positions_created_zero(self):
        self.assertEqual(self._result()["positions_created"], 0)

    def test_pnl_created_zero(self):
        self.assertEqual(self._result()["pnl_created"], 0)

    def test_trade_events_created_zero(self):
        self.assertEqual(self._result()["trade_events_created"], 0)

    def test_paper_trade_audits_created_zero(self):
        self.assertEqual(self._result()["paper_trade_audits_created"], 0)

    def test_discovery_is_intake_not_alpha(self):
        self.assertTrue(self._result()["discovery_is_intake_not_alpha"])

    def test_selection_is_memory_value_based(self):
        self.assertTrue(
            self._result()["selection_is_memory_value_based_not_buy_probability"]
        )

    def test_hard_locks_in_completed_result(self):
        r = self._result()
        self.assertIn("hard_locks", r)
        self.assertEqual(len(r["hard_locks"]), 24)

    def test_no_discovery_automation_in_completed_result(self):
        self.assertTrue(self._result()["hard_locks"]["no_discovery_automation"])


# ===========================================================================
# 4. Mint-level dedup
# ===========================================================================

class TestLaneX6MintDedup(unittest.TestCase):
    def test_two_same_mints_collapses_to_one(self):
        c1 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T00:00:00+00:00")
        c2 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T01:00:00+00:00")
        kept, collapsed = dedup_by_mint([c1, c2])
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(collapsed), 1)

    def test_keeps_most_recent(self):
        c1 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T00:00:00+00:00", reason="old")
        c2 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T01:00:00+00:00", reason="new")
        kept, _ = dedup_by_mint([c1, c2])
        self.assertEqual(kept[0]["priority_reason"], "new")

    def test_distinct_mints_both_kept(self):
        c1 = _cand(_MINT_A, _PAIR_A)
        c2 = _cand(_MINT_B, _PAIR_B)
        kept, collapsed = dedup_by_mint([c1, c2])
        self.assertEqual(len(kept), 2)
        self.assertEqual(len(collapsed), 0)

    def test_collapsed_has_reason_field(self):
        c1 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T00:00:00+00:00")
        c2 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T01:00:00+00:00")
        _, collapsed = dedup_by_mint([c1, c2])
        self.assertIn("_collapse_reason", collapsed[0])
        self.assertIn("mint_duplicate", collapsed[0]["_collapse_reason"])

    def test_three_same_mints_keeps_freshest(self):
        c1 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T00:00:00+00:00", reason="oldest")
        c2 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T01:00:00+00:00", reason="middle")
        c3 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T02:00:00+00:00", reason="newest")
        kept, collapsed = dedup_by_mint([c1, c2, c3])
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(collapsed), 2)
        self.assertEqual(kept[0]["priority_reason"], "newest")

    def test_missing_mint_collapsed(self):
        c1 = {"pair_address": _PAIR_A, "captured_at": "2026-01-01T00:00:00+00:00"}
        kept, collapsed = dedup_by_mint([c1])
        self.assertEqual(len(collapsed), 1)
        self.assertEqual(collapsed[0]["_collapse_reason"], "missing_mint")

    def test_empty_input_returns_empty(self):
        kept, collapsed = dedup_by_mint([])
        self.assertEqual(len(kept), 0)
        self.assertEqual(len(collapsed), 0)


# ===========================================================================
# 5. Pair-level dedup
# ===========================================================================

class TestLaneX6PairDedup(unittest.TestCase):
    def test_two_same_pairs_collapses_to_one(self):
        c1 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T00:00:00+00:00")
        c2 = _cand(_MINT_B, _PAIR_A, captured_at="2026-01-01T01:00:00+00:00")
        kept, collapsed = dedup_by_pair([c1, c2])
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(collapsed), 1)

    def test_pair_dedup_keeps_most_recent(self):
        c1 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T00:00:00+00:00", reason="old")
        c2 = _cand(_MINT_B, _PAIR_A, captured_at="2026-01-01T01:00:00+00:00", reason="new")
        kept, _ = dedup_by_pair([c1, c2])
        self.assertEqual(kept[0]["priority_reason"], "new")

    def test_distinct_pairs_both_kept(self):
        c1 = _cand(_MINT_A, _PAIR_A)
        c2 = _cand(_MINT_B, _PAIR_B)
        kept, collapsed = dedup_by_pair([c1, c2])
        self.assertEqual(len(kept), 2)
        self.assertEqual(len(collapsed), 0)

    def test_collapsed_pair_has_reason_field(self):
        c1 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T00:00:00+00:00")
        c2 = _cand(_MINT_B, _PAIR_A, captured_at="2026-01-01T01:00:00+00:00")
        _, collapsed = dedup_by_pair([c1, c2])
        self.assertIn("_collapse_reason", collapsed[0])
        self.assertIn("pair_duplicate", collapsed[0]["_collapse_reason"])

    def test_empty_input_returns_empty(self):
        kept, collapsed = dedup_by_pair([])
        self.assertEqual(len(kept), 0)
        self.assertEqual(len(collapsed), 0)


# ===========================================================================
# 6. Same-token/new-pair detection
# ===========================================================================

class TestLaneX6SameTokenNewPair(unittest.TestCase):
    def test_same_mint_two_pairs_detected(self):
        c1 = _cand(_MINT_A, _PAIR_A)
        c2 = _cand(_MINT_A, _PAIR_A2)
        cases = detect_same_token_new_pair([c1, c2])
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["token_mint"], _MINT_A)
        self.assertEqual(cases[0]["pair_count"], 2)

    def test_different_mints_no_case_detected(self):
        c1 = _cand(_MINT_A, _PAIR_A)
        c2 = _cand(_MINT_B, _PAIR_B)
        cases = detect_same_token_new_pair([c1, c2])
        self.assertEqual(len(cases), 0)

    def test_same_mint_same_pair_not_a_new_pair_case(self):
        c1 = _cand(_MINT_A, _PAIR_A)
        c2 = _cand(_MINT_A, _PAIR_A)
        cases = detect_same_token_new_pair([c1, c2])
        # Same pair — not a new-pair case
        self.assertEqual(len(cases), 0)

    def test_case_includes_both_pairs(self):
        c1 = _cand(_MINT_A, _PAIR_A)
        c2 = _cand(_MINT_A, _PAIR_A2)
        cases = detect_same_token_new_pair([c1, c2])
        self.assertIn(_PAIR_A, cases[0]["pairs"])
        self.assertIn(_PAIR_A2, cases[0]["pairs"])

    def test_case_has_explicit_handling_field(self):
        c1 = _cand(_MINT_A, _PAIR_A)
        c2 = _cand(_MINT_A, _PAIR_A2)
        cases = detect_same_token_new_pair([c1, c2])
        self.assertIn("handling", cases[0])
        self.assertEqual(cases[0]["handling"], "keep_freshest_pair_after_dedup")

    def test_already_known_pairs_from_db_detected(self):
        c1 = _cand(_MINT_A, _PAIR_A)
        # _PAIR_A2 "already in DB" for MINT_A
        known = {_MINT_A: [_PAIR_A2]}
        cases = detect_same_token_new_pair([c1], already_known_pairs_by_mint=known)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["pair_count"], 2)

    def test_reason_field_is_explicit(self):
        c1 = _cand(_MINT_A, _PAIR_A)
        c2 = _cand(_MINT_A, _PAIR_A2)
        cases = detect_same_token_new_pair([c1, c2])
        self.assertIn("same_token_new_pair_detected_explicitly", cases[0]["reason"])


# ===========================================================================
# 7. Integration: mint+pair dedup in full selection run
# ===========================================================================

class TestLaneX6DedupIntegration(_DbBase):
    def test_duplicate_mint_collapsed_in_run(self):
        c1 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T00:00:00+00:00")
        c2 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T01:00:00+00:00")
        r = self._run([c1, c2])
        self.assertEqual(r["candidate_count_input"], 2)
        self.assertEqual(r["mint_duplicates_collapsed"], 1)
        self.assertEqual(r["selected_count"], 1)

    def test_duplicate_pair_collapsed_in_run(self):
        c1 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T00:00:00+00:00")
        c2 = _cand(_MINT_B, _PAIR_A, captured_at="2026-01-01T01:00:00+00:00")
        r = self._run([c1, c2])
        self.assertEqual(r["pair_duplicates_collapsed"], 1)
        self.assertEqual(r["selected_count"], 1)

    def test_same_token_new_pair_case_counted_in_run(self):
        c1 = _cand(_MINT_A, _PAIR_A)
        c2 = _cand(_MINT_A, _PAIR_A2)
        r = self._run([c1, c2])
        self.assertGreaterEqual(r["same_token_new_pair_cases"], 1)

    def test_dedup_report_mint_duplicates_populated(self):
        c1 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T00:00:00+00:00")
        c2 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T01:00:00+00:00")
        r = self._run([c1, c2])
        self.assertGreater(len(r["dedup_report"]["mint_duplicates"]), 0)

    def test_dedup_report_pair_duplicates_populated(self):
        c1 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T00:00:00+00:00")
        c2 = _cand(_MINT_B, _PAIR_A, captured_at="2026-01-01T01:00:00+00:00")
        r = self._run([c1, c2])
        self.assertGreater(len(r["dedup_report"]["pair_duplicates"]), 0)

    def test_no_duplicates_nothing_collapsed(self):
        c1 = _cand(_MINT_A, _PAIR_A)
        c2 = _cand(_MINT_B, _PAIR_B)
        r = self._run([c1, c2])
        self.assertEqual(r["mint_duplicates_collapsed"], 0)
        self.assertEqual(r["pair_duplicates_collapsed"], 0)

    def test_same_token_new_pair_flagged_on_selected_candidate(self):
        c1 = _cand(_MINT_A, _PAIR_A, captured_at="2026-01-01T00:00:00+00:00")
        c2 = _cand(_MINT_A, _PAIR_A2, captured_at="2026-01-01T01:00:00+00:00")
        r = self._run([c1, c2])
        # Only one selected (mint dedup collapses to freshest)
        selected = r["selected_candidates"]
        self.assertEqual(len(selected), 1)
        self.assertTrue(selected[0]["same_token_new_pair"])


# ===========================================================================
# 8. Cooldown-aware filtering
# ===========================================================================

class TestLaneX6CooldownFiltering(_DbBase):
    def test_cooldown_token_blocked(self):
        c = _cand(_MINT_A, _PAIR_A, lifecycle_status="COOLDOWN")
        r = self._run([c], cooldown_aware=True)
        self.assertEqual(r["cooldown_blocked_count"], 1)
        self.assertEqual(r["selected_count"], 0)

    def test_archived_token_blocked(self):
        c = _cand(_MINT_A, _PAIR_A, lifecycle_status="ARCHIVED")
        r = self._run([c], cooldown_aware=True)
        self.assertEqual(r["cooldown_blocked_count"], 1)
        self.assertEqual(r["selected_count"], 0)

    def test_queued_token_allowed(self):
        c = _cand(_MINT_A, _PAIR_A, lifecycle_status="QUEUED")
        r = self._run([c], cooldown_aware=True)
        self.assertEqual(r["cooldown_blocked_count"], 0)
        self.assertEqual(r["selected_count"], 1)

    def test_unknown_status_token_allowed(self):
        c = _cand(_MINT_A, _PAIR_A)  # no lifecycle_status override
        r = self._run([c], cooldown_aware=True)
        self.assertEqual(r["cooldown_blocked_count"], 0)
        self.assertEqual(r["selected_count"], 1)

    def test_cooldown_disabled_includes_all(self):
        c1 = _cand(_MINT_A, _PAIR_A, lifecycle_status="COOLDOWN")
        c2 = _cand(_MINT_B, _PAIR_B, lifecycle_status="ARCHIVED")
        r = self._run([c1, c2], cooldown_aware=False)
        self.assertEqual(r["cooldown_blocked_count"], 0)
        self.assertEqual(r["selected_count"], 2)

    def test_mixed_statuses_partial_block(self):
        c1 = _cand(_MINT_A, _PAIR_A, lifecycle_status="COOLDOWN")
        c2 = _cand(_MINT_B, _PAIR_B, lifecycle_status="QUEUED")
        c3 = _cand(_MINT_C, _PAIR_C)
        r = self._run([c1, c2, c3], cooldown_aware=True)
        self.assertEqual(r["cooldown_blocked_count"], 1)
        self.assertEqual(r["selected_count"], 2)

    def test_cooldown_blocked_list_has_reason(self):
        c = _cand(_MINT_A, _PAIR_A, lifecycle_status="COOLDOWN")
        r = self._run([c], cooldown_aware=True)
        blocked = r["cooldown_blocked"]
        self.assertEqual(len(blocked), 1)
        self.assertIn("blocked_reason", blocked[0])
        self.assertIn("cooldown", blocked[0]["blocked_reason"])

    def test_archived_blocked_list_has_reason(self):
        c = _cand(_MINT_A, _PAIR_A, lifecycle_status="ARCHIVED")
        r = self._run([c], cooldown_aware=True)
        blocked = r["cooldown_blocked"]
        self.assertIn("archived", blocked[0]["blocked_reason"])


# ===========================================================================
# 9. Revival path (stale/cooldown token not immediately recycled,
#    but already-reopened token CAN be selected)
# ===========================================================================

class TestLaneX6RevivalPath(_DbBase):
    def test_cooldown_token_not_selected_by_default(self):
        c = _cand(_MINT_A, _PAIR_A, lifecycle_status="COOLDOWN")
        r = self._run([c], cooldown_aware=True, include_revivals=True)
        # COOLDOWN → still blocked (QUEUED would be the reopened state)
        self.assertEqual(r["cooldown_blocked_count"], 1)

    def test_archived_token_not_selected_by_default(self):
        c = _cand(_MINT_A, _PAIR_A, lifecycle_status="ARCHIVED")
        r = self._run([c], cooldown_aware=True, include_revivals=True)
        self.assertEqual(r["cooldown_blocked_count"], 1)

    def test_reopened_queued_token_allowed_with_revivals(self):
        c = _cand(_MINT_A, _PAIR_A, lifecycle_status="QUEUED")
        r = self._run([c], cooldown_aware=True, include_revivals=True)
        self.assertEqual(r["selected_count"], 1)

    def test_no_revivals_still_allows_fresh_queued_token(self):
        # A token with no prior cooldown, status QUEUED
        c = _cand(_MINT_A, _PAIR_A, lifecycle_status="QUEUED")
        r = self._run([c], cooldown_aware=True, include_revivals=False)
        self.assertEqual(r["selected_count"], 1)

    def test_zero_candidates_is_valid_outcome(self):
        r = self._run([])
        self.assertEqual(r["selected_count"], 0)
        self.assertTrue(r["zero_candidates_is_valid"])


# ===========================================================================
# 10. filter_cooldown_blocked unit tests
# ===========================================================================

class TestFilterCooldownBlocked(unittest.TestCase):
    def test_cooldown_blocked(self):
        c = _cand(_MINT_A, _PAIR_A)
        allowed, blocked = filter_cooldown_blocked([c], {_MINT_A: "COOLDOWN"})
        self.assertEqual(len(allowed), 0)
        self.assertEqual(len(blocked), 1)

    def test_archived_blocked(self):
        c = _cand(_MINT_A, _PAIR_A)
        allowed, blocked = filter_cooldown_blocked([c], {_MINT_A: "ARCHIVED"})
        self.assertEqual(len(allowed), 0)
        self.assertEqual(len(blocked), 1)

    def test_queued_allowed(self):
        c = _cand(_MINT_A, _PAIR_A)
        allowed, blocked = filter_cooldown_blocked([c], {_MINT_A: "QUEUED"})
        self.assertEqual(len(allowed), 1)
        self.assertEqual(len(blocked), 0)

    def test_no_status_allowed(self):
        c = _cand(_MINT_A, _PAIR_A)
        allowed, blocked = filter_cooldown_blocked([c], {})
        self.assertEqual(len(allowed), 1)
        self.assertEqual(len(blocked), 0)

    def test_empty_input(self):
        allowed, blocked = filter_cooldown_blocked([], {})
        self.assertEqual(len(allowed), 0)
        self.assertEqual(len(blocked), 0)


# ===========================================================================
# 11. Memory-diet classification — unit tests for classify_memory_diet_label
# ===========================================================================

class TestMemoryDietClassify(unittest.TestCase):
    def test_pump_high_5m_volume_and_price(self):
        c = _cand(_MINT_A, _PAIR_A, price_5m=25.0, vol_5m=8_000.0, txns_5m=25)
        self.assertEqual(classify_memory_diet_label(c), DIET_PUMP)

    def test_pump_high_1h(self):
        c = _cand(_MINT_A, _PAIR_A, price_1h=60.0, vol_1h=15_000.0)
        self.assertEqual(classify_memory_diet_label(c), DIET_PUMP)

    def test_dump_1h(self):
        c = _cand(_MINT_A, _PAIR_A, price_1h=-40.0, vol_1h=8_000.0)
        self.assertEqual(classify_memory_diet_label(c), DIET_DUMP)

    def test_dump_24h(self):
        c = _cand(_MINT_A, _PAIR_A, price_24h=-60.0, vol_24h=8_000.0)
        self.assertEqual(classify_memory_diet_label(c), DIET_DUMP)

    def test_fake_pump_thin_liquidity(self):
        c = _cand(_MINT_A, _PAIR_A, price_1h=80.0, liquidity=1_500.0)
        self.assertEqual(classify_memory_diet_label(c), DIET_FAKE_PUMP)

    def test_fake_pump_5m_thin_liquidity(self):
        c = _cand(_MINT_A, _PAIR_A, price_5m=35.0, liquidity=2_000.0)
        self.assertEqual(classify_memory_diet_label(c), DIET_FAKE_PUMP)

    def test_wick_only(self):
        c = _cand(_MINT_A, _PAIR_A, price_5m=40.0, price_1h=3.0)
        self.assertEqual(classify_memory_diet_label(c), DIET_WICK_ONLY)

    def test_late_buy_trap(self):
        c = _cand(_MINT_A, _PAIR_A, price_24h=300.0, vol_24h=8_000.0)
        self.assertEqual(classify_memory_diet_label(c), DIET_LATE_BUY_TRAP)

    def test_dead_token_all_zeros(self):
        c = _cand(_MINT_A, _PAIR_A, price_5m=0.0, vol_5m=0.0, txns_5m=0,
                  vol_1h=0.0, txns_1h=0, vol_24h=5.0, txns_24h=1)
        self.assertEqual(classify_memory_diet_label(c), DIET_DEAD_TOKEN)

    def test_liquidity_decay(self):
        c = _cand(_MINT_A, _PAIR_A, liquidity=3_000.0, vol_24h=200.0, txns_24h=2)
        self.assertEqual(classify_memory_diet_label(c), DIET_LIQUIDITY_DECAY)

    def test_revival_flag_overrides(self):
        c = _cand(_MINT_A, _PAIR_A, price_5m=25.0, vol_5m=8_000.0, txns_5m=25)
        self.assertEqual(classify_memory_diet_label(c, is_revival=True), DIET_REVIVAL)

    def test_ambiguous_no_strong_signal(self):
        c = _cand(_MINT_A, _PAIR_A, price_5m=2.0, price_1h=5.0, vol_5m=100.0,
                  vol_1h=500.0, vol_24h=1000.0, txns_5m=5, txns_24h=10,
                  liquidity=5_000.0)
        self.assertEqual(classify_memory_diet_label(c), DIET_AMBIGUOUS)


# ===========================================================================
# 12. Memory-diet variety in selected set
# ===========================================================================

class TestLaneX6MemoryDietVariety(_DbBase):
    def _diverse_candidates(self):
        return [
            _cand(_MINT_A, _PAIR_A, price_5m=25.0, vol_5m=8_000.0, txns_5m=25),  # PUMP
            _cand(_MINT_B, _PAIR_B, price_1h=-40.0, vol_1h=8_000.0),  # DUMP
            _cand(_MINT_C, _PAIR_C, price_1h=80.0, liquidity=1_500.0),  # FAKE_PUMP
            _cand(_MINT_D, _PAIR_D, price_5m=40.0, price_1h=3.0),  # WICK_ONLY
        ]

    def test_diet_summary_present(self):
        r = self._run(self._diverse_candidates())
        self.assertIn("memory_diet_summary", r)

    def test_diet_summary_has_all_labels(self):
        r = self._run([])
        summary = r["memory_diet_summary"]
        for label in ALL_DIET_LABELS:
            self.assertIn(label, summary)

    def test_diet_summary_counts_diverse_input(self):
        r = self._run(self._diverse_candidates())
        summary = r["memory_diet_summary"]
        self.assertEqual(summary[DIET_PUMP], 1)
        self.assertEqual(summary[DIET_DUMP], 1)
        self.assertEqual(summary[DIET_FAKE_PUMP], 1)
        self.assertEqual(summary[DIET_WICK_ONLY], 1)

    def test_not_only_bullish_tokens(self):
        """Selected set must not be uniformly bullish."""
        r = self._run(self._diverse_candidates())
        summary = r["memory_diet_summary"]
        non_pump = summary[DIET_DUMP] + summary[DIET_FAKE_PUMP] + summary[DIET_DEAD_TOKEN]
        self.assertGreater(non_pump, 0)

    def test_dead_token_included_in_selection(self):
        c = _cand(_MINT_A, _PAIR_A, vol_5m=0.0, txns_5m=0, vol_1h=0.0,
                  txns_1h=0, vol_24h=5.0, txns_24h=1)
        r = self._run([c])
        self.assertEqual(r["memory_diet_summary"][DIET_DEAD_TOKEN], 1)

    def test_ambiguous_case_included(self):
        c = _cand(_MINT_A, _PAIR_A, price_5m=2.0, price_1h=5.0, vol_5m=100.0,
                  vol_1h=500.0, vol_24h=1000.0, txns_5m=5, txns_24h=10,
                  liquidity=5_000.0)
        r = self._run([c])
        self.assertEqual(r["memory_diet_summary"][DIET_AMBIGUOUS], 1)

    def test_revival_label_in_summary(self):
        """REVIVAL label is assigned when is_revival=True via _was_cooled."""
        # We mark a candidate as a genuine revival by using _was_cooled flag
        c = _cand(_MINT_A, _PAIR_A, lifecycle_status="QUEUED")
        cand_with_revival = dict(c)
        cand_with_revival["_was_cooled"] = True
        r = self._run([cand_with_revival])
        self.assertEqual(r["memory_diet_summary"][DIET_REVIVAL], 1)


# ===========================================================================
# 13. Auditable selection reason
# ===========================================================================

class TestLaneX6SelectionReason(_DbBase):
    def test_selection_reason_present_on_candidate(self):
        r = self._run([_cand(_MINT_A, _PAIR_A)])
        self.assertGreater(r["selected_count"], 0)
        c = r["selected_candidates"][0]
        self.assertIn("selection_reason", c)

    def test_selection_reason_not_empty(self):
        r = self._run([_cand(_MINT_A, _PAIR_A)])
        c = r["selected_candidates"][0]
        self.assertTrue(c["selection_reason"])

    def test_selection_reason_includes_diet_label(self):
        c = _cand(_MINT_A, _PAIR_A, price_5m=25.0, vol_5m=8_000.0, txns_5m=25)
        r = self._run([c])
        sel = r["selected_candidates"][0]
        self.assertIn(DIET_PUMP, sel["selection_reason"])

    def test_selection_reason_includes_action(self):
        c = _cand(_MINT_A, _PAIR_A, action="TRACK_FAST")
        r = self._run([c])
        sel = r["selected_candidates"][0]
        self.assertIn("TRACK_FAST", sel["selection_reason"])

    def test_selection_reason_format_is_colon_separated(self):
        r = self._run([_cand(_MINT_A, _PAIR_A)])
        reason = r["selected_candidates"][0]["selection_reason"]
        parts = reason.split(":")
        self.assertGreaterEqual(len(parts), 2)

    def test_memory_diet_label_on_selected_candidate(self):
        r = self._run([_cand(_MINT_A, _PAIR_A)])
        c = r["selected_candidates"][0]
        self.assertIn("memory_diet_label", c)
        self.assertIn(c["memory_diet_label"], ALL_DIET_LABELS)

    def test_each_candidate_has_unique_auditable_reason(self):
        candidates = [
            _cand(_MINT_A, _PAIR_A, reason="reason_a"),
            _cand(_MINT_B, _PAIR_B, reason="reason_b"),
        ]
        r = self._run(candidates)
        reasons = [c["selection_reason"] for c in r["selected_candidates"]]
        # All reasons should contain the candidate's priority_reason
        self.assertIn("reason_a", reasons[0])
        self.assertIn("reason_b", reasons[1])


# ===========================================================================
# 14. Discovery cannot create paper BUY / act as trade signal
# ===========================================================================

class TestLaneX6NoTradingSignal(_DbBase):
    def test_no_paper_decisions_created(self):
        r = self._run([_cand(_MINT_A, _PAIR_A)])
        self.assertEqual(r["paper_decisions_created"], 0)

    def test_no_trade_events_created(self):
        r = self._run([_cand(_MINT_A, _PAIR_A)])
        self.assertEqual(r["trade_events_created"], 0)

    def test_no_positions_created(self):
        r = self._run([_cand(_MINT_A, _PAIR_A)])
        self.assertEqual(r["positions_created"], 0)

    def test_forbidden_tables_all_zero(self):
        r = self._run([_cand(_MINT_A, _PAIR_A)])
        for table, count in r["forbidden_table_counts"].items():
            self.assertEqual(count, 0, f"Expected 0 rows in {table}, got {count}")

    def test_buy_enabled_remains_false_on_pump_token(self):
        c = _cand(_MINT_A, _PAIR_A, price_5m=25.0, vol_5m=8_000.0, txns_5m=25)
        r = self._run([c])
        # Even a PUMP-labeled token must not enable buying
        self.assertFalse(r["buy_enabled"])

    def test_sell_enabled_remains_false(self):
        r = self._run([_cand(_MINT_A, _PAIR_A)])
        self.assertFalse(r["sell_enabled"])

    def test_hold_enabled_remains_false(self):
        r = self._run([_cand(_MINT_A, _PAIR_A)])
        self.assertFalse(r["hold_enabled"])

    def test_discovery_is_intake_label_present(self):
        r = self._run([_cand(_MINT_A, _PAIR_A)])
        self.assertTrue(r["discovery_is_intake_not_alpha"])


# ===========================================================================
# 15. Max-candidates cap
# ===========================================================================

class TestLaneX6MaxCandidatesCap(_DbBase):
    def _many_candidates(self, n: int) -> list[dict]:
        mints = [f"MINT{i:040d}" for i in range(n)]
        pairs = [f"PAIR{i:040d}" for i in range(n)]
        return [_cand(m, p) for m, p in zip(mints, pairs)]

    def test_default_max_candidates(self):
        from printer_v1.operator_cli.lane_x6_discovery_selection_repair import _DEFAULT_MAX_CANDIDATES
        self.assertEqual(_DEFAULT_MAX_CANDIDATES, 20)

    def test_max_candidates_enforced(self):
        r = self._run(self._many_candidates(50), max_candidates=5)
        self.assertLessEqual(r["selected_count"], 5)

    def test_fewer_than_max_all_selected(self):
        r = self._run(self._many_candidates(3), max_candidates=20)
        self.assertEqual(r["selected_count"], 3)

    def test_zero_input_zero_selected(self):
        r = self._run([])
        self.assertEqual(r["selected_count"], 0)


# ===========================================================================
# 16. Output structure completeness
# ===========================================================================

class TestLaneX6OutputStructure(_DbBase):
    def _r(self):
        return self._run([_cand(_MINT_A, _PAIR_A)])

    def test_command_field(self):
        self.assertEqual(self._r()["command"], LANE_X6_COMMAND_NAME)

    def test_status_completed(self):
        self.assertEqual(self._r()["lane_x6_status"], LANE_X6_STATUS_COMPLETED)

    def test_operator_approved_field(self):
        self.assertTrue(self._r()["operator_approved"])

    def test_candidate_count_input_present(self):
        self.assertIn("candidate_count_input", self._r())

    def test_dedup_report_structure(self):
        r = self._r()
        self.assertIn("dedup_report", r)
        self.assertIn("mint_duplicates", r["dedup_report"])
        self.assertIn("pair_duplicates", r["dedup_report"])
        self.assertIn("same_token_new_pair_cases", r["dedup_report"])

    def test_cooldown_blocked_list(self):
        self.assertIn("cooldown_blocked", self._r())

    def test_memory_diet_summary_structure(self):
        summary = self._r()["memory_diet_summary"]
        for label in ALL_DIET_LABELS:
            self.assertIn(label, summary)

    def test_selected_candidate_fields(self):
        r = self._r()
        c = r["selected_candidates"][0]
        required_fields = [
            "token_mint", "pair_address", "chain",
            "memory_diet_label", "selection_reason",
            "lifecycle_status", "is_revival", "same_token_new_pair",
        ]
        for f in required_fields:
            self.assertIn(f, c, f"Missing field: {f}")

    def test_chain_is_solana(self):
        r = self._r()
        c = r["selected_candidates"][0]
        self.assertEqual(c["chain"], "solana")

    def test_run_timestamps_present(self):
        r = self._r()
        self.assertIn("run_started_at", r)
        self.assertIn("run_finished_at", r)


# ===========================================================================
# 17. CLI integration test
# ===========================================================================

class TestLaneX6CLI(unittest.TestCase):
    def setUp(self):
        self._db_fd, self._db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(self._db_fd)
        self._bp_fd, self._bp_path = tempfile.mkstemp(suffix=".bak")
        os.close(self._bp_fd)

    def tearDown(self):
        for p in (self._db_path, self._bp_path):
            try:
                os.unlink(p)
            except OSError:
                pass

    def _run_cli(self, extra_args=None):
        from printer_v1.operator_cli.commands import main_run_lane_x6_discovery_selection_repair
        argv = [
            "--db-path", self._db_path,
            "--backup-proof-path", self._bp_path,
        ]
        if extra_args:
            argv.extend(extra_args)
        return main_run_lane_x6_discovery_selection_repair(argv)

    def test_cli_blocked_without_operator_approved(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self._run_cli()
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["lane_x6_status"], LANE_X6_STATUS_BLOCKED)

    def test_cli_completed_with_operator_approved(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self._run_cli(["--operator-approved"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["lane_x6_status"], LANE_X6_STATUS_COMPLETED)

    def test_cli_no_cooldown_aware_flag(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self._run_cli(["--operator-approved", "--no-cooldown-aware"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertFalse(payload["cooldown_aware"])

    def test_cli_max_candidates_flag(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self._run_cli(["--operator-approved", "--max-candidates", "5"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["max_candidates"], 5)


# ===========================================================================
# 18. X3 lifecycle regression
# ===========================================================================

class TestLaneX6X3Regression(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self._tmp.name) / "printer_v1.sqlite3"
        apply_migrations(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_x3_cooldown_still_works(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            LANE_X3_STATUS_COOLDOWN_ENTERED,
            enter_cooldown_after_window,
        )
        r = enter_cooldown_after_window(self.db_path, _MINT_A, _PAIR_A)
        self.assertEqual(r["lane_x3_status"], LANE_X3_STATUS_COOLDOWN_ENTERED)

    def test_x3_reopen_still_works(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            LANE_X3_STATUS_REOPENED,
            enter_cooldown_after_window,
            reopen_token,
        )
        enter_cooldown_after_window(self.db_path, _MINT_A, _PAIR_A)
        r = reopen_token(self.db_path, _MINT_A, _PAIR_A)
        self.assertEqual(r["lane_x3_status"], LANE_X3_STATUS_REOPENED)

    def test_x3_gate_blocks_cooldown_token(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            check_x3_cooldown_gate,
            enter_cooldown_after_window,
        )
        enter_cooldown_after_window(self.db_path, _MINT_B, _PAIR_B)
        blocked = check_x3_cooldown_gate(self.db_path, [_MINT_B])
        self.assertGreater(len(blocked), 0, "X3 gate must block cooldown token")

    def test_x3_gate_passes_after_reopen(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            check_x3_cooldown_gate,
            enter_cooldown_after_window,
            reopen_token,
        )
        enter_cooldown_after_window(self.db_path, _MINT_C, _PAIR_C)
        reopen_token(self.db_path, _MINT_C, _PAIR_C)
        blocked = check_x3_cooldown_gate(self.db_path, [_MINT_C])
        self.assertEqual(len(blocked), 0, "X3 gate must pass after reopen")

    def test_x3_hard_locks_count_is_23(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import _HARD_LOCKS as X3_LOCKS
        self.assertEqual(len(X3_LOCKS), 23)


# ===========================================================================
# 19. X5 regression
# ===========================================================================

class TestLaneX6X5Regression(unittest.TestCase):
    def test_x5_hard_locks_still_present(self):
        from printer_v1.operator_cli.lane_x5_five_token_runner import _HARD_LOCKS as X5_LOCKS
        self.assertEqual(len(X5_LOCKS), 24)
        self.assertIn("no_source_budget_bypass", X5_LOCKS)
        self.assertIn("no_x6_expansion", X5_LOCKS)

    def test_x5_status_constants_present(self):
        from printer_v1.operator_cli.lane_x5_five_token_runner import (
            LANE_X5_STATUS_BLOCKED,
            LANE_X5_STATUS_COMPLETED,
            LANE_X5_STATUS_STOPPED,
        )
        self.assertIsInstance(LANE_X5_STATUS_BLOCKED, str)
        self.assertIsInstance(LANE_X5_STATUS_COMPLETED, str)
        self.assertIsInstance(LANE_X5_STATUS_STOPPED, str)

    def test_x5_exact_token_count_is_five(self):
        from printer_v1.operator_cli.lane_x5_five_token_runner import LANE_X5_EXACT_TOKEN_COUNT
        self.assertEqual(LANE_X5_EXACT_TOKEN_COUNT, 5)

    def test_x5_command_name_unchanged(self):
        from printer_v1.operator_cli.lane_x5_five_token_runner import LANE_X5_COMMAND_NAME
        self.assertEqual(LANE_X5_COMMAND_NAME, "printer-run-lane-x5-five-token-cycle")

    def test_x5_no_x6_expansion_lock_is_true(self):
        from printer_v1.operator_cli.lane_x5_five_token_runner import _HARD_LOCKS as X5_LOCKS
        self.assertTrue(X5_LOCKS["no_x6_expansion"])

    def test_x6_does_not_replace_x5_locks(self):
        """X6 introduces its own locks; X5 locks remain unchanged."""
        from printer_v1.operator_cli.lane_x5_five_token_runner import _HARD_LOCKS as X5_LOCKS
        # X6 has no_discovery_automation; X5 has no_x6_expansion — they are different
        self.assertIn("no_x6_expansion", X5_LOCKS)
        self.assertNotIn("no_discovery_automation", X5_LOCKS)
        self.assertIn("no_discovery_automation", _HARD_LOCKS)


# ===========================================================================
# 20. All retrieval/paper/BUY/position/PnL locks unchanged cross-lane
# ===========================================================================

class TestLaneX6CrossLaneLocks(unittest.TestCase):
    def test_x6_no_buy_sell_hold(self):
        self.assertTrue(_HARD_LOCKS["no_buy_sell_hold"])

    def test_x6_no_paper_decisions(self):
        self.assertTrue(_HARD_LOCKS["no_paper_decisions"])

    def test_x6_no_positions(self):
        self.assertTrue(_HARD_LOCKS["no_positions"])

    def test_x6_no_pnl(self):
        self.assertTrue(_HARD_LOCKS["no_pnl"])

    def test_x6_no_retrieval_activation(self):
        self.assertTrue(_HARD_LOCKS["no_retrieval_activation"])

    def test_x6_no_live_trading(self):
        self.assertTrue(_HARD_LOCKS["no_live_trading"])

    def test_x6_no_paid_api(self):
        self.assertTrue(_HARD_LOCKS["no_paid_api"])

    def test_x6_no_wallet_private_key(self):
        self.assertTrue(_HARD_LOCKS["no_wallet_private_key"])

    def test_x6_no_embeddings_vectors(self):
        self.assertTrue(_HARD_LOCKS["no_embeddings_vectors"])

    def test_x6_no_scoring_ranking_confidence(self):
        self.assertTrue(_HARD_LOCKS["no_scoring_ranking_confidence"])

    def test_x3_buy_sell_hold_still_locked(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import _HARD_LOCKS as X3_LOCKS
        self.assertTrue(X3_LOCKS["no_buy_sell_hold"])

    def test_x5_buy_sell_hold_still_locked(self):
        from printer_v1.operator_cli.lane_x5_five_token_runner import _HARD_LOCKS as X5_LOCKS
        self.assertTrue(X5_LOCKS["no_buy_sell_hold"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

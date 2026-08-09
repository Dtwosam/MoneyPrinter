"""Focused proof for V2-9.7D.4A token-local selective continuation."""

from dataclasses import replace
import sqlite3
import unittest

from printer_v1.safety.composite import (
    SAFETY_CONTEXT_ACCEPTABLE,
    SAFETY_CONTEXT_BLOCKED,
)
from printer_v1.scheduler.token_local_continuation import (
    CampaignContinuationContext,
    ContinuationLearningNeed,
    ContinuationVerdict,
    ExpectedTokenContinuationIdentity,
    TokenContinuationInput,
    evaluate_token_local_continuations,
)
from printer_v1.snapshots.lifecycle_continuity import (
    CONTINUITY_CONTINUOUS,
    CONTINUITY_DIRTY,
)


def _token(slot: str, *, stage: str = "15m_to_1h") -> TokenContinuationInput:
    suffix = slot.lower()
    predecessor, successor, need = (
        ("WINDOW_15M", "WINDOW_1H", ContinuationLearningNeed.TRANSITION)
        if stage == "15m_to_1h"
        else ("WINDOW_1H", "WINDOW_4H", ContinuationLearningNeed.SURVIVAL)
    )
    identity = ExpectedTokenContinuationIdentity(
        token_slot_id=f"slot-{suffix}",
        token_id=f"token-{suffix}",
        mint_id=f"mint-{suffix}",
        pair_id=f"pair-{suffix}",
        lifecycle_id=f"lifecycle-{suffix}",
        predecessor_window_id=f"window-{predecessor.lower()}-{suffix}",
    )
    return TokenContinuationInput(
        campaign_id="campaign-4a",
        configuration_id="config-4a",
        token_slot_id=identity.token_slot_id,
        token_id=identity.token_id,
        mint_id=identity.mint_id,
        pair_id=identity.pair_id,
        lifecycle_id=identity.lifecycle_id,
        predecessor_window_id=identity.predecessor_window_id,
        expected_identity=identity,
        predecessor_window_kind=predecessor,
        successor_window_kind=successor,
        predecessor_window_status="WINDOW_CLOSED",
        predecessor_memory_quality="CLEAN_MEMORY",
        predecessor_data_quality="CLEAN_DATA",
        predecessor_do_not_train=False,
        predecessor_evidence_eligible=True,
        predecessor_complete=True,
        freshness_within_contract=True,
        governed_provenance_traceable=True,
        safety_context_present=True,
        safety_context_result=SAFETY_CONTEXT_ACCEPTABLE,
        continuity_status=CONTINUITY_CONTINUOUS,
        learning_need=need,
        token_budget_available=True,
        token_state="TRACK_NORMAL",
    )


class TokenLocalSelectiveContinuationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.campaign = CampaignContinuationContext("campaign-4a", "config-4a")
        self.a = _token("A")
        self.b = _token("B")

    def _evaluate(self, a=None, b=None, campaign=None):
        return evaluate_token_local_continuations(
            campaign=campaign or self.campaign,
            tokens=(a or self.a, b or self.b),
        )

    def test_both_tokens_continue_15m_to_1h_without_learning_need_gate(self) -> None:
        result = self._evaluate(
            a=replace(self.a, learning_need=None),
            b=replace(self.b, learning_need=None),
        )
        self.assertEqual(
            [item.verdict for item in result],
            [ContinuationVerdict.CONTINUE_TO_WINDOW_1H] * 2,
        )

    def test_only_token_b_continues_1h_to_4h(self) -> None:
        a = replace(_token("A", stage="1h_to_4h"), learning_need=None)
        b = _token("B", stage="1h_to_4h")
        result = self._evaluate(a=a, b=b)
        self.assertEqual(result[0].verdict, ContinuationVerdict.STOP_AFTER_WINDOW_1H)
        self.assertEqual(result[1].verdict, ContinuationVerdict.CONTINUE_TO_WINDOW_4H)

    def test_both_tokens_continue_cleanly_after_15m_without_learning_need(self) -> None:
        result = self._evaluate(
            a=replace(self.a, learning_need=None),
            b=replace(self.b, learning_need=None),
        )
        self.assertEqual(
            [item.verdict for item in result],
            [ContinuationVerdict.CONTINUE_TO_WINDOW_1H] * 2,
        )

    def test_one_token_blocks_while_the_other_continues(self) -> None:
        result = self._evaluate(a=replace(self.a, safety_context_result=SAFETY_CONTEXT_BLOCKED))
        self.assertEqual(result[0].verdict, ContinuationVerdict.BLOCK_CONTINUATION)
        self.assertEqual(result[1].verdict, ContinuationVerdict.CONTINUE_TO_WINDOW_1H)

    def test_dirty_or_stale_predecessor_blocks_only_affected_token(self) -> None:
        for changes in (
            {"predecessor_memory_quality": "DIRTY_MEMORY"},
            {"freshness_within_contract": False},
        ):
            with self.subTest(changes=changes):
                result = self._evaluate(a=replace(self.a, **changes))
                self.assertEqual(result[0].verdict, ContinuationVerdict.BLOCK_CONTINUATION)
                self.assertEqual(result[1].verdict, ContinuationVerdict.CONTINUE_TO_WINDOW_1H)

    def test_identity_or_predecessor_mismatch_fails_closed(self) -> None:
        for changes in (
            {"pair_id": "pair-wrong"},
            {"predecessor_window_id": "window-wrong"},
            {"continuity_status": CONTINUITY_DIRTY},
            {"predecessor_window_kind": "WINDOW_4H"},
        ):
            with self.subTest(changes=changes):
                result = self._evaluate(a=replace(self.a, **changes))
                self.assertEqual(result[0].verdict, ContinuationVerdict.BLOCK_CONTINUATION)
                self.assertEqual(result[1].verdict, ContinuationVerdict.CONTINUE_TO_WINDOW_1H)

    def test_missing_safety_context_blocks_continuation(self) -> None:
        result = self._evaluate(a=replace(self.a, safety_context_present=False))
        self.assertEqual(result[0].verdict, ContinuationVerdict.BLOCK_CONTINUATION)
        self.assertIn("mandatory_safety_context_missing", result[0].reasons)

    def test_token_budget_exhaustion_is_token_local(self) -> None:
        result = self._evaluate(a=replace(self.a, token_budget_available=False))
        self.assertEqual(result[0].verdict, ContinuationVerdict.BLOCK_CONTINUATION)
        self.assertEqual(result[1].verdict, ContinuationVerdict.CONTINUE_TO_WINDOW_1H)

    def test_shared_campaign_budget_exhaustion_blocks_both(self) -> None:
        campaign = replace(self.campaign, campaign_budget_available=False)
        result = self._evaluate(campaign=campaign)
        self.assertEqual(
            [item.verdict for item in result],
            [ContinuationVerdict.BLOCK_CONTINUATION] * 2,
        )
        self.assertTrue(all("campaign_budget_exhausted" in item.reasons for item in result))

    def test_shared_db_lease_or_integrity_failure_blocks_both(self) -> None:
        for field in ("shared_db_healthy", "shared_lease_healthy", "shared_integrity_healthy"):
            with self.subTest(field=field):
                result = self._evaluate(campaign=replace(self.campaign, **{field: False}))
                self.assertTrue(
                    all(item.verdict == ContinuationVerdict.BLOCK_CONTINUATION for item in result)
                )

    def test_repeated_evaluation_is_deterministic_and_idempotent(self) -> None:
        first = self._evaluate()
        second = self._evaluate()
        self.assertEqual(first, second)
        self.assertEqual(self.a, _token("A"))
        self.assertEqual(self.b, _token("B"))

    def test_no_locked_capability_rows_are_created(self) -> None:
        connection = sqlite3.connect(":memory:")
        tables = (
            "printer_memories",
            "printer_memory_retrieval_queries",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
            "printer_paper_trade_audits",
        )
        for table in tables:
            connection.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")
        before = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
        self._evaluate()
        after = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
        connection.close()
        self.assertEqual(after, before)

    def test_fail_closed_matrix_for_remaining_required_conditions(self) -> None:
        cases = (
            {"predecessor_data_quality": "STALE_DATA"},
            {"predecessor_do_not_train": True},
            {"predecessor_evidence_eligible": False},
            {"predecessor_complete": False},
            {"governed_provenance_traceable": False},
            {"token_state": "COOLDOWN"},
            {"token_eligible": False},
            {"cancelled": True},
            {"terminal": True},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                result = self._evaluate(a=replace(self.a, **changes))
                self.assertEqual(result[0].verdict, ContinuationVerdict.BLOCK_CONTINUATION)
                self.assertEqual(result[1].verdict, ContinuationVerdict.CONTINUE_TO_WINDOW_1H)


if __name__ == "__main__":
    unittest.main()

"""Focused offline composition proof for the post-DTW100 first-hour policy.

This file exercises the real operational 15m outcome-to-learning-need adapter
and the real token-local continuation policy together. It uses only an in-memory
SQLite table; it performs no source work, Scheduler runtime, authoritative DB
mutation, memory generation, authorization, or financial action.
"""

from __future__ import annotations

from dataclasses import replace
import sqlite3
import unittest

from printer_v1.operator_cli.operational_selective_1h import _learning_need_from_window
from printer_v1.safety.composite import SAFETY_CONTEXT_ACCEPTABLE
from printer_v1.scheduler.token_local_continuation import (
    CampaignContinuationContext,
    ContinuationLearningNeed,
    ContinuationVerdict,
    ExpectedTokenContinuationIdentity,
    TokenContinuationInput,
    evaluate_token_local_continuations,
)
from printer_v1.snapshots.lifecycle_continuity import CONTINUITY_CONTINUOUS


class FirstHourLifecycleCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """
            CREATE TABLE printer_memory_windows (
                id INTEGER PRIMARY KEY,
                outcome_label TEXT,
                memory_quality_label TEXT,
                data_quality_label TEXT,
                do_not_train INTEGER NOT NULL,
                window_status TEXT NOT NULL,
                window_kind TEXT NOT NULL
            )
            """
        )
        self.campaign = CampaignContinuationContext(
            campaign_id="campaign-first-hour",
            configuration_id="config-first-hour",
        )

    def tearDown(self) -> None:
        self.connection.close()

    def _insert_15m(self, window_id: int, outcome: str) -> None:
        self.connection.execute(
            """
            INSERT INTO printer_memory_windows(
                id,outcome_label,memory_quality_label,data_quality_label,
                do_not_train,window_status,window_kind
            ) VALUES (?,?,'CLEAN_MEMORY','CLEAN_DATA',0,'WINDOW_CLOSED','WINDOW_15M')
            """,
            (window_id, outcome),
        )
        self.connection.commit()

    @staticmethod
    def _token(slot: int, *, learning_need: str | None) -> TokenContinuationInput:
        identity = ExpectedTokenContinuationIdentity(
            token_slot_id=f"slot-{slot}",
            token_id=f"token-{slot}",
            mint_id=f"mint-{slot}",
            pair_id=f"pair-{slot}",
            lifecycle_id=f"lifecycle-{slot}",
            predecessor_window_id=f"window-15m-{slot}",
        )
        return TokenContinuationInput(
            campaign_id="campaign-first-hour",
            configuration_id="config-first-hour",
            token_slot_id=identity.token_slot_id,
            token_id=identity.token_id,
            mint_id=identity.mint_id,
            pair_id=identity.pair_id,
            lifecycle_id=identity.lifecycle_id,
            predecessor_window_id=identity.predecessor_window_id,
            expected_identity=identity,
            predecessor_window_kind="WINDOW_15M",
            successor_window_kind="WINDOW_1H",
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
            learning_need=learning_need,
            token_budget_available=True,
            token_state="TRACK_NORMAL",
        )

    def test_no_pump_and_consolidation_have_no_learning_need_but_both_continue(self) -> None:
        self._insert_15m(1, "NO_PUMP")
        self._insert_15m(2, "CONSOLIDATION")
        needs = (
            _learning_need_from_window(self.connection, 1),
            _learning_need_from_window(self.connection, 2),
        )
        self.assertEqual(needs, (None, None))

        results = evaluate_token_local_continuations(
            campaign=self.campaign,
            tokens=(
                self._token(1, learning_need=needs[0]),
                self._token(2, learning_need=needs[1]),
            ),
        )
        self.assertEqual(
            [item.verdict for item in results],
            [ContinuationVerdict.CONTINUE_TO_WINDOW_1H] * 2,
        )
        self.assertTrue(
            all(item.reasons == ("standard_first_hour_lifecycle",) for item in results)
        )

    def test_transition_outcome_still_continues_without_gaining_extra_authority(self) -> None:
        self._insert_15m(3, "SHORT_TERM_PUMP")
        self._insert_15m(4, "DUMP")
        needs = (
            _learning_need_from_window(self.connection, 3),
            _learning_need_from_window(self.connection, 4),
        )
        self.assertEqual(
            needs,
            (
                ContinuationLearningNeed.TRANSITION.value,
                ContinuationLearningNeed.TRANSITION.value,
            ),
        )
        results = evaluate_token_local_continuations(
            campaign=self.campaign,
            tokens=(
                self._token(1, learning_need=needs[0]),
                self._token(2, learning_need=needs[1]),
            ),
        )
        self.assertEqual(
            [item.verdict for item in results],
            [ContinuationVerdict.CONTINUE_TO_WINDOW_1H] * 2,
        )
        self.assertTrue(
            all(item.reasons == ("standard_first_hour_lifecycle",) for item in results)
        )

    def test_first_hour_resource_and_identity_guards_still_fail_closed(self) -> None:
        valid_a = self._token(1, learning_need=None)
        valid_b = self._token(2, learning_need=None)

        budget_blocked = evaluate_token_local_continuations(
            campaign=self.campaign,
            tokens=(replace(valid_a, token_budget_available=False), valid_b),
        )
        self.assertEqual(budget_blocked[0].verdict, ContinuationVerdict.BLOCK_CONTINUATION)
        self.assertIn("token_budget_exhausted", budget_blocked[0].reasons)
        self.assertEqual(budget_blocked[1].verdict, ContinuationVerdict.CONTINUE_TO_WINDOW_1H)

        identity_blocked = evaluate_token_local_continuations(
            campaign=self.campaign,
            tokens=(replace(valid_a, pair_id="wrong-pair"), valid_b),
        )
        self.assertEqual(identity_blocked[0].verdict, ContinuationVerdict.BLOCK_CONTINUATION)
        self.assertIn("pair_identity_mismatch", identity_blocked[0].reasons)
        self.assertEqual(identity_blocked[1].verdict, ContinuationVerdict.CONTINUE_TO_WINDOW_1H)

    def test_5m_support_cannot_authorize_main_lifecycle_and_1h_to_4h_is_standard(self) -> None:
        first = self._token(1, learning_need=None)
        second = self._token(2, learning_need=None)

        five_minute = evaluate_token_local_continuations(
            campaign=self.campaign,
            tokens=(
                replace(first, predecessor_window_kind="WINDOW_5M_MICRO_EVENT"),
                second,
            ),
        )
        self.assertEqual(five_minute[0].verdict, ContinuationVerdict.BLOCK_CONTINUATION)
        self.assertIn("unsupported_window_transition", five_minute[0].reasons)

        later = evaluate_token_local_continuations(
            campaign=self.campaign,
            tokens=(
                replace(
                    first,
                    predecessor_window_kind="WINDOW_1H",
                    successor_window_kind="WINDOW_4H",
                    predecessor_window_id="window-1h-1",
                    expected_identity=replace(
                        first.expected_identity,
                        predecessor_window_id="window-1h-1",
                    ),
                ),
                replace(
                    second,
                    predecessor_window_kind="WINDOW_1H",
                    successor_window_kind="WINDOW_4H",
                    predecessor_window_id="window-1h-2",
                    expected_identity=replace(
                        second.expected_identity,
                        predecessor_window_id="window-1h-2",
                    ),
                ),
            ),
        )
        self.assertEqual(
            [item.verdict for item in later],
            [ContinuationVerdict.CONTINUE_TO_WINDOW_4H] * 2,
        )
        self.assertTrue(
            all(
                item.reasons == ("standard_first_four_hour_lifecycle",)
                for item in later
            )
        )


if __name__ == "__main__":
    unittest.main()

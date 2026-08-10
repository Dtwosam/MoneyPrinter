"""Focused offline TDD for standard first-four-hour policy/capacity foundation."""

from dataclasses import replace
import unittest

from printer_v1.operator_cli import one_token_4h_runtime as four_hour
from printer_v1.scheduler.token_local_continuation import (
    CampaignContinuationContext,
    ContinuationLearningNeed,
    ContinuationVerdict,
    evaluate_token_local_continuations,
)
from tests.test_v2_9_7d_4a_token_local_selective_continuation import _token


class StandardFourHourPolicyCapacityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.campaign = CampaignContinuationContext("campaign-4a", "config-4a")

    def _evaluate(self, a, b):
        return evaluate_token_local_continuations(
            campaign=self.campaign,
            tokens=(a, b),
        )

    def test_both_valid_first_hour_tokens_continue_to_4h_without_learning_need(self) -> None:
        a = replace(_token("A", stage="1h_to_4h"), learning_need=None)
        b = replace(_token("B", stage="1h_to_4h"), learning_need=None)
        result = self._evaluate(a, b)
        self.assertEqual(
            [item.verdict for item in result],
            [ContinuationVerdict.CONTINUE_TO_WINDOW_4H] * 2,
        )
        self.assertTrue(
            all(item.reasons == ("standard_first_four_hour_lifecycle",) for item in result)
        )

    def test_learning_need_has_no_special_1h_to_4h_authority(self) -> None:
        quiet = replace(_token("A", stage="1h_to_4h"), learning_need=None)
        transition = replace(
            _token("B", stage="1h_to_4h"),
            learning_need=ContinuationLearningNeed.COLLAPSE,
        )
        result = self._evaluate(quiet, transition)
        self.assertEqual(
            [item.verdict for item in result],
            [ContinuationVerdict.CONTINUE_TO_WINDOW_4H] * 2,
        )
        self.assertEqual(result[0].reasons, result[1].reasons)
        self.assertEqual(result[0].reasons, ("standard_first_four_hour_lifecycle",))

    def test_token_budget_remains_a_hard_1h_to_4h_gate(self) -> None:
        blocked = replace(
            _token("A", stage="1h_to_4h"),
            learning_need=None,
            token_budget_available=False,
        )
        peer = replace(_token("B", stage="1h_to_4h"), learning_need=None)
        result = self._evaluate(blocked, peer)
        self.assertEqual(result[0].verdict, ContinuationVerdict.BLOCK_CONTINUATION)
        self.assertIn("token_budget_exhausted", result[0].reasons)
        self.assertEqual(result[1].verdict, ContinuationVerdict.CONTINUE_TO_WINDOW_4H)

    def test_two_token_first_four_hour_capacity_is_policy_derived(self) -> None:
        self.assertTrue(
            hasattr(four_hour, "standard_two_token_lifecycle_budget"),
            "standard two-token four-hour budget owner is missing",
        )
        budget = four_hour.standard_two_token_lifecycle_budget
        expected = {
            ("TRACK_FAST", "TRACK_FAST"): (230, 210),
            ("TRACK_FAST", "TRACK_NORMAL"): (182, 162),
            ("TRACK_NORMAL", "TRACK_NORMAL"): (134, 114),
        }
        for lanes, ceilings in expected.items():
            with self.subTest(lanes=lanes):
                actual = budget(lanes)
                self.assertEqual(actual["request_ceiling"], ceilings[0])
                self.assertEqual(actual["scheduler_ceiling"], ceilings[1])
                self.assertEqual(tuple(actual["tracking_lanes"]), lanes)
                self.assertEqual(actual["automatic_retries"], 0)
                self.assertFalse(actual["endpoint_rotation"])

    def test_standard_activation_enables_real_4h_collection_only(self) -> None:
        self.assertTrue(four_hour.runtime_budget("TRACK_FAST")["enabled_for_real_collection"])
        self.assertTrue(four_hour.runtime_budget("TRACK_NORMAL")["enabled_for_real_collection"])
        from printer_v1.snapshots.cadence_policy import get_policy
        for lane in ("TRACK_FAST", "TRACK_NORMAL"):
            self.assertFalse(get_policy("WINDOW_12H", lane).enabled_for_real_collection)
            self.assertFalse(get_policy("WINDOW_24H", lane).enabled_for_real_collection)


if __name__ == "__main__":
    unittest.main()

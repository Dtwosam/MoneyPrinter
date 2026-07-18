"""Focused V2-9.7D.4B conditional support-only 5m capture proof."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import sqlite3
import unittest

from printer_v1.safety.composite import SAFETY_CONTEXT_ACCEPTABLE
from printer_v1.scheduler.support_only_5m_capture import (
    ExpectedSupportCaptureIdentity,
    GovernedSourceProvenance,
    SupportCaptureBudgets,
    SupportCaptureRequest,
    SupportCaptureVerdict,
    SupportTriggerFamily,
    TriggeringSnapshot,
    evaluate_support_only_5m_capture,
)
from printer_v1.scheduler.token_local_continuation import (
    CampaignContinuationContext,
    ContinuationLearningNeed,
    ExpectedTokenContinuationIdentity,
    TokenContinuationInput,
    evaluate_token_local_continuations,
)
from printer_v1.snapshots.lifecycle_continuity import CONTINUITY_CONTINUOUS


TRIGGER_TIME = datetime(2026, 7, 18, 12, 5, tzinfo=timezone.utc)


def _request(
    slot: str = "a",
    *,
    trigger_family: SupportTriggerFamily | str | None = SupportTriggerFamily.LIQUIDITY_SHOCK,
    window_kind: str = "WINDOW_15M",
) -> SupportCaptureRequest:
    expected = ExpectedSupportCaptureIdentity(
        campaign_id="campaign-4b",
        run_id="run-4b",
        cycle_id="cycle-1",
        token_slot_id=f"slot-{slot}",
        token_id=f"token-{slot}",
        mint_id=f"mint-{slot}",
        pair_id=f"pair-{slot}",
        root_15m_lifecycle_id=f"root-15m-{slot}",
        containing_main_window_id=f"main-window-{slot}",
        scheduler_work_id=f"scheduler-work-{slot}",
    )
    provenance = GovernedSourceProvenance(
        source_name="dexscreener",
        source_request_id=11,
        source_response_id=12,
        scheduler_work_id=expected.scheduler_work_id,
        source_status="COMPLETE",
        data_quality_label="CLEAN_DATA",
        governor_approved=True,
        traceable=True,
    )

    def snapshot(snapshot_id: int, observed_at: datetime) -> TriggeringSnapshot:
        return TriggeringSnapshot(
            snapshot_id=snapshot_id,
            campaign_id=expected.campaign_id,
            run_id=expected.run_id,
            cycle_id=expected.cycle_id,
            token_slot_id=expected.token_slot_id,
            token_id=expected.token_id,
            mint_id=expected.mint_id,
            pair_id=expected.pair_id,
            root_15m_lifecycle_id=expected.root_15m_lifecycle_id,
            containing_main_window_id=expected.containing_main_window_id,
            observed_at=observed_at,
            freshness_within_contract=True,
            provenance=provenance,
        )

    return SupportCaptureRequest(
        campaign_id=expected.campaign_id,
        run_id=expected.run_id,
        cycle_id=expected.cycle_id,
        token_slot_id=expected.token_slot_id,
        token_id=expected.token_id,
        mint_id=expected.mint_id,
        pair_id=expected.pair_id,
        root_15m_lifecycle_id=expected.root_15m_lifecycle_id,
        containing_main_window_id=expected.containing_main_window_id,
        containing_main_window_kind=window_kind,
        containing_main_window_status="WINDOW_OPEN",
        scheduler_work_id=expected.scheduler_work_id,
        expected_identity=expected,
        trigger_family=trigger_family,
        trigger_time=TRIGGER_TIME,
        evidence_cutoff=TRIGGER_TIME,
        triggering_snapshots=(
            snapshot(101, TRIGGER_TIME - timedelta(minutes=1)),
            snapshot(102, TRIGGER_TIME),
        ),
        budgets=SupportCaptureBudgets(),
        token_state="TRACK_FAST",
        meaningful_transition_proven=True,
    )


def _continuation_token(slot: str) -> TokenContinuationInput:
    identity = ExpectedTokenContinuationIdentity(
        token_slot_id=f"slot-{slot}",
        token_id=f"token-{slot}",
        mint_id=f"mint-{slot}",
        pair_id=f"pair-{slot}",
        lifecycle_id=f"lifecycle-{slot}",
        predecessor_window_id=f"window-{slot}",
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
        learning_need=ContinuationLearningNeed.TRANSITION,
        token_budget_available=True,
        token_state="TRACK_NORMAL",
    )


class ConditionalSupportOnly5mCaptureTests(unittest.TestCase):
    def test_each_approved_trigger_family_can_capture(self) -> None:
        for family in SupportTriggerFamily:
            with self.subTest(family=family):
                result = evaluate_support_only_5m_capture(_request(trigger_family=family))
                self.assertEqual(result.verdict, SupportCaptureVerdict.CAPTURE_SUPPORT)
                self.assertEqual(result.capture.trigger_family, family)
                self.assertEqual(result.capture.window_kind, "WINDOW_5M_MICRO_EVENT")

    def test_ordinary_movement_is_valid_no_capture(self) -> None:
        request = replace(
            _request(trigger_family=None),
            ordinary_movement=True,
            meaningful_transition_proven=False,
        )
        result = evaluate_support_only_5m_capture(request)
        self.assertEqual(result.verdict, SupportCaptureVerdict.VALID_NO_CAPTURE)
        self.assertIsNone(result.capture)

    def test_unsupported_trigger_label_does_not_capture(self) -> None:
        result = evaluate_support_only_5m_capture(
            _request(trigger_family="SINGLE_UNSUPPORTED_LABEL")
        )
        self.assertEqual(result.verdict, SupportCaptureVerdict.BLOCK_SUPPORT_CAPTURE)
        self.assertIsNone(result.capture)

    def test_stale_mismatched_untraceable_or_future_leaking_evidence_blocks(self) -> None:
        base = _request()
        stale = replace(base.triggering_snapshots[0], freshness_within_contract=False)
        mismatched = replace(base.triggering_snapshots[0], pair_id="pair-wrong")
        untraceable_provenance = replace(
            base.triggering_snapshots[0].provenance,
            traceable=False,
        )
        untraceable = replace(
            base.triggering_snapshots[0],
            provenance=untraceable_provenance,
        )
        cases = (
            replace(base, triggering_snapshots=(stale, base.triggering_snapshots[1])),
            replace(base, triggering_snapshots=(mismatched, base.triggering_snapshots[1])),
            replace(base, triggering_snapshots=(untraceable, base.triggering_snapshots[1])),
            replace(base, future_main_window_outcome_used=True),
        )
        for request in cases:
            with self.subTest(reasons=request):
                result = evaluate_support_only_5m_capture(request)
                self.assertEqual(result.verdict, SupportCaptureVerdict.BLOCK_SUPPORT_CAPTURE)

    def test_exact_root_15m_and_containing_window_linkage_is_required(self) -> None:
        base = _request()
        for changes in (
            {"root_15m_lifecycle_id": "root-wrong"},
            {"containing_main_window_id": "window-wrong"},
        ):
            with self.subTest(changes=changes):
                snapshot = replace(base.triggering_snapshots[0], **changes)
                result = evaluate_support_only_5m_capture(
                    replace(base, triggering_snapshots=(snapshot, base.triggering_snapshots[1]))
                )
                self.assertEqual(result.verdict, SupportCaptureVerdict.BLOCK_SUPPORT_CAPTURE)

    def test_capture_works_inside_15m_1h_and_4h_active_windows(self) -> None:
        for window_kind in ("WINDOW_15M", "WINDOW_1H", "WINDOW_4H"):
            with self.subTest(window_kind=window_kind):
                result = evaluate_support_only_5m_capture(_request(window_kind=window_kind))
                self.assertEqual(result.verdict, SupportCaptureVerdict.CAPTURE_SUPPORT)
                self.assertEqual(result.capture.containing_main_window_kind, window_kind)

    def test_token_a_support_failure_does_not_affect_token_b_or_main_windows(self) -> None:
        token_a = replace(_request("a"), cancelled=True)
        token_b = _request("b")
        before_a, before_b = token_a, token_b
        result_a = evaluate_support_only_5m_capture(token_a)
        result_b = evaluate_support_only_5m_capture(token_b)
        self.assertEqual(result_a.verdict, SupportCaptureVerdict.BLOCK_SUPPORT_CAPTURE)
        self.assertEqual(result_b.verdict, SupportCaptureVerdict.CAPTURE_SUPPORT)
        self.assertTrue(result_a.containing_main_window_unchanged)
        self.assertTrue(result_b.containing_main_window_unchanged)
        self.assertEqual((token_a, token_b), (before_a, before_b))

    def test_each_budget_exhaustion_blocks_without_hidden_retry(self) -> None:
        for field in (
            "token_available",
            "source_available",
            "scheduler_available",
            "storage_available",
            "campaign_available",
        ):
            with self.subTest(field=field):
                budgets = replace(SupportCaptureBudgets(), **{field: False})
                result = evaluate_support_only_5m_capture(replace(_request(), budgets=budgets))
                self.assertEqual(result.verdict, SupportCaptureVerdict.BLOCK_SUPPORT_CAPTURE)
                self.assertFalse(result.hidden_retry_allowed)

    def test_repeated_evaluation_is_deterministic_and_idempotent(self) -> None:
        request = _request()
        first = evaluate_support_only_5m_capture(request)
        second = evaluate_support_only_5m_capture(request)
        self.assertEqual(first, second)
        self.assertEqual(request, _request())

    def test_capture_object_encodes_permanent_5m_non_authority(self) -> None:
        capture = evaluate_support_only_5m_capture(_request()).capture
        self.assertTrue(capture.support_only)
        self.assertFalse(capture.main_outcome_memory)
        self.assertFalse(capture.replaces_window_15m)
        self.assertFalse(capture.continuation_authority)
        self.assertFalse(capture.counts_toward_main_clean_memory)
        self.assertFalse(capture.lifecycle_disposition_authority)
        self.assertFalse(capture.retrieval_authority)
        self.assertFalse(capture.decision_authority)
        self.assertFalse(capture.financial_authority)

    def test_support_evidence_cannot_alter_4a_continuation_verdict(self) -> None:
        context = CampaignContinuationContext("campaign-4a", "config-4a")
        tokens = (_continuation_token("a"), _continuation_token("b"))
        before = evaluate_token_local_continuations(campaign=context, tokens=tokens)
        support = evaluate_support_only_5m_capture(_request())
        after = evaluate_token_local_continuations(campaign=context, tokens=tokens)
        self.assertEqual(support.verdict, SupportCaptureVerdict.CAPTURE_SUPPORT)
        self.assertEqual(after, before)

    def test_no_locked_capability_rows_are_created(self) -> None:
        connection = sqlite3.connect(":memory:")
        tables = (
            "printer_memory_windows",
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
        evaluate_support_only_5m_capture(_request())
        after = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
        connection.close()
        self.assertEqual(after, before)

    def test_cutoff_identity_state_and_provenance_fail_closed(self) -> None:
        base = _request()
        cases = (
            replace(base, evidence_cutoff=TRIGGER_TIME + timedelta(seconds=1)),
            replace(base, containing_main_window_status="WINDOW_CLOSED"),
            replace(base, containing_main_window_kind="WINDOW_5M_MICRO_EVENT"),
            replace(base, terminal=True),
            replace(base, token_eligible=False),
            replace(base, pair_id="pair-conflict"),
            replace(base, triggering_snapshots=base.triggering_snapshots[:1]),
        )
        for request in cases:
            with self.subTest(request=request):
                result = evaluate_support_only_5m_capture(request)
                self.assertEqual(result.verdict, SupportCaptureVerdict.BLOCK_SUPPORT_CAPTURE)


if __name__ == "__main__":
    unittest.main()

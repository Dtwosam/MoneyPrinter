"""Focused V2-9.7D.5C opportunity-segment object proof."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import sqlite3
import unittest

from printer_v1.contracts.enums import MemoryStatus
from printer_v1.memory.contracts import EpisodeOutcomeLabel
from printer_v1.scheduler.manipulation_context import (
    ActionEligibility,
    ManipulationContextRequest,
    ManipulationLifecycleStage,
    MarketIntegrityCondition,
    Tradeability,
    UnknownState,
    build_manipulation_context,
)
from printer_v1.scheduler.opportunity_segment import (
    EventTimeEvidenceGap,
    EventTimeEvidenceReference,
    EventTimeEvidenceRequirement,
    OpportunityEvidenceClass,
    OpportunitySegmentRequest,
    OpportunitySegmentVerdict,
    ReentryLink,
    TradeablePathContext,
    build_opportunity_segment,
    build_opportunity_window,
    evaluate_later_segment_evidence,
    required_event_time_contract_fields,
)
from printer_v1.scheduler.support_only_5m_capture import GovernedSourceProvenance
from printer_v1.scheduler.trajectory_checkpoint import (
    CheckpointKind,
    CheckpointRequest,
    EvaluationPath,
    FixedTrajectoryRequest,
    PhaseClaim,
    ReversalClaim,
    TrajectoryIdentity,
    TrajectoryObservation,
    build_checkpoint,
    build_fixed_trajectory,
)


T0 = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)


class OpportunitySegmentEvidenceGapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.identity = TrajectoryIdentity(
            "campaign-5c", "run-5c", "cycle-1", "slot-a", "token-a",
            "mint-a", "pair-a", "root-15m-a", "window-15m-a",
        )
        self.market_provenance = self.provenance("geckoterminal", 10)
        self.jupiter_provenance = self.provenance("jupiter_quote", 20)
        observations = (
            TrajectoryObservation(1, self.identity, T0, self.market_provenance),
            TrajectoryObservation(
                2, self.identity, T0 + timedelta(minutes=1),
                self.market_provenance, observed_peak=True,
            ),
            TrajectoryObservation(
                3, self.identity, T0 + timedelta(minutes=2), self.market_provenance
            ),
        )
        result = build_fixed_trajectory(
            FixedTrajectoryRequest(
                self.identity, self.identity, "scheduler-5c", observations, (),
                (PhaseClaim("INITIAL_EXPANSION", (1, 2)),
                 PhaseClaim("PULLBACK", (2, 3))),
                (ReversalClaim("NO_CONFIRMED_REVERSAL", (3,)),),
            )
        )
        self.assertIsNotNone(result.trajectory)
        self.trajectory = result.trajectory
        self.checkpoint = self.make_checkpoint("checkpoint-a", 2)
        context_result = build_manipulation_context(
            ManipulationContextRequest(
                "context-5c", self.trajectory, self.checkpoint,
                ManipulationLifecycleStage.ATTENTION_EXPANSION, None, (),
                MemoryStatus.CLEAN_MEMORY,
                MarketIntegrityCondition.MARKET_INTEGRITY_UNKNOWN,
                Tradeability.TRADEABILITY_UNKNOWN,
                ActionEligibility.ACTION_ELIGIBILITY_LOCKED,
            )
        )
        self.assertIsNotNone(context_result.context)
        self.context = context_result.context

    def provenance(self, source: str, seed: int) -> GovernedSourceProvenance:
        return GovernedSourceProvenance(
            source, seed, seed + 1, "scheduler-5c", "COMPLETE", "CLEAN_DATA",
            True, True,
        )

    def make_checkpoint(self, checkpoint_id: str, minute: int, paths=()):
        result = build_checkpoint(
            CheckpointRequest(
                checkpoint_id, self.trajectory, CheckpointKind.SCHEDULED_CADENCE,
                T0 + timedelta(minutes=minute), T0 + timedelta(minutes=minute),
                paths, "scheduler-5c",
            )
        )
        self.assertIsNotNone(result.checkpoint)
        return result.checkpoint

    def gaps(self, checkpoint_id="checkpoint-a"):
        return tuple(
            EventTimeEvidenceGap(
                f"gap-{requirement.value.lower()}", requirement,
                UnknownState.CURRENT_EVIDENCE_GAP, checkpoint_id,
                f"{requirement.value.lower()} evidence unavailable",
            )
            for requirement in EventTimeEvidenceRequirement
        )

    def complete_references(self, checkpoint_id="checkpoint-a", minute=2):
        return tuple(
            EventTimeEvidenceReference(
                f"evidence-{requirement.value.lower()}", requirement,
                self.identity, checkpoint_id, T0 + timedelta(minutes=minute),
                self.jupiter_provenance, True, True,
                required_event_time_contract_fields(requirement),
            )
            for requirement in EventTimeEvidenceRequirement
        )

    def request(self, **changes):
        value = OpportunitySegmentRequest(
            "segment-a", self.trajectory, (self.checkpoint,), self.context,
            TradeablePathContext.EXPANSION_PULLBACK_CONTINUATION,
            EpisodeOutcomeLabel.DUMP, EpisodeOutcomeLabel.SHORT_TERM_PUMP,
            OpportunityEvidenceClass.CHART_OPPORTUNITY,
            (1, 2, 3), (), self.gaps(), T0 + timedelta(minutes=2),
            observed_peak_snapshot_id=2,
        )
        return replace(value, **changes)

    def test_all_twelve_fixed_tradeable_path_contexts_are_represented(self) -> None:
        self.assertEqual(len(TradeablePathContext), 12)
        for path in TradeablePathContext:
            with self.subTest(path=path):
                changes = {"path_context": path}
                if path == TradeablePathContext.REENTRY_CHURN:
                    fresh = self.make_checkpoint("checkpoint-fresh", 3)
                    changes.update(
                        checkpoints=(self.checkpoint, fresh),
                        evidence_gaps=self.gaps("checkpoint-fresh"),
                        evidence_cutoff=T0 + timedelta(minutes=3),
                        reentry_link=ReentryLink(
                            "prior-segment", "checkpoint-prior", "checkpoint-fresh",
                            T0 + timedelta(minutes=2),
                        ),
                    )
                result = build_opportunity_segment(self.request(**changes))
                self.assertEqual(result.verdict, OpportunitySegmentVerdict.VALID)
                self.assertEqual(result.segment.path_context, path)

    def test_full_window_and_internal_outcomes_are_independent(self) -> None:
        result = build_opportunity_segment(self.request())
        self.assertEqual(result.verdict, OpportunitySegmentVerdict.VALID)
        self.assertEqual(result.segment.full_window_outcome, EpisodeOutcomeLabel.DUMP)
        self.assertEqual(
            result.segment.internal_trade_opportunity_outcome,
            EpisodeOutcomeLabel.SHORT_TERM_PUMP,
        )
        self.assertNotEqual(
            result.segment.full_window_outcome,
            result.segment.internal_trade_opportunity_outcome,
        )

    def test_multiple_ordered_segments_can_exist_in_one_negative_window(self) -> None:
        first = build_opportunity_segment(self.request()).segment
        later_checkpoint = self.make_checkpoint("checkpoint-b", 3)
        second = build_opportunity_segment(
            self.request(
                segment_id="segment-b",
                checkpoints=(self.checkpoint, later_checkpoint),
                path_context=TradeablePathContext.CORRECT_EXIT_THEN_MORE_UPSIDE,
                internal_trade_opportunity_outcome=EpisodeOutcomeLabel.MISSED_UPSIDE,
                evidence_gaps=self.gaps("checkpoint-b"),
                evidence_cutoff=T0 + timedelta(minutes=3),
            )
        ).segment
        result = build_opportunity_window((first, second))
        self.assertEqual(result.verdict, OpportunitySegmentVerdict.VALID)
        self.assertEqual(result.window.full_window_outcome, EpisodeOutcomeLabel.DUMP)
        self.assertEqual(len(result.window.segments), 2)
        self.assertNotEqual(
            first.internal_trade_opportunity_outcome,
            second.internal_trade_opportunity_outcome,
        )

    def test_gaps_mismatches_unsupported_and_post_cutoff_evidence_fail_closed(self) -> None:
        foreign = replace(self.identity, pair_id="foreign-pair")
        cases = (
            self.request(evidence_gaps=self.gaps()[:-1]),
            self.request(checkpoints=(replace(self.checkpoint, identity=foreign),)),
            self.request(path_context="INVENTED_PATH"),
            self.request(evidence_references=(EventTimeEvidenceReference(
                "foreign", EventTimeEvidenceRequirement.ROUTE, foreign,
                "checkpoint-a", T0 + timedelta(minutes=2),
                self.jupiter_provenance, True,
            ),)),
            self.request(evidence_references=(EventTimeEvidenceReference(
                "late", EventTimeEvidenceRequirement.ROUTE, self.identity,
                "checkpoint-a", T0 + timedelta(minutes=3),
                self.jupiter_provenance, True,
            ),)),
            self.request(evidence_references=(EventTimeEvidenceReference(
                "stale", EventTimeEvidenceRequirement.ROUTE, self.identity,
                "checkpoint-a", T0 + timedelta(minutes=2),
                self.jupiter_provenance, False,
            ),)),
        )
        for request in cases:
            with self.subTest(request=request):
                self.assertEqual(
                    build_opportunity_segment(request).verdict,
                    OpportunitySegmentVerdict.BLOCKED,
                )

    def test_wick_only_peak_cannot_become_capturable_exit(self) -> None:
        result = build_opportunity_segment(
            self.request(
                path_context=TradeablePathContext.WICK_ONLY_PEAK,
                realistically_capturable_exit_snapshot_id=2,
            )
        )
        self.assertEqual(result.verdict, OpportunitySegmentVerdict.BLOCKED)
        self.assertIn("wick_only_peak_cannot_be_capturable_exit", result.reasons)

    def test_chart_opportunity_cannot_silently_become_realistically_executable(self) -> None:
        chart = build_opportunity_segment(self.request())
        self.assertEqual(chart.verdict, OpportunitySegmentVerdict.VALID)
        self.assertEqual(
            chart.segment.opportunity_class, OpportunityEvidenceClass.CHART_OPPORTUNITY
        )
        blocked = build_opportunity_segment(
            self.request(
                opportunity_class=OpportunityEvidenceClass.REALISTICALLY_EXECUTABLE_OPPORTUNITY
            )
        )
        self.assertEqual(blocked.verdict, OpportunitySegmentVerdict.BLOCKED)
        executable = build_opportunity_segment(
            self.request(
                opportunity_class=OpportunityEvidenceClass.REALISTICALLY_EXECUTABLE_OPPORTUNITY,
                evidence_references=self.complete_references(),
                evidence_gaps=(),
                realistically_capturable_exit_snapshot_id=3,
            )
        )
        self.assertEqual(executable.verdict, OpportunitySegmentVerdict.VALID)

    def test_provider_context_remains_an_explicit_gap_not_execution_proof(self) -> None:
        categorical = EventTimeEvidenceReference(
            "gt-liquidity", EventTimeEvidenceRequirement.USABLE_LIQUIDITY,
            self.identity, "checkpoint-a", T0 + timedelta(minutes=2),
            self.market_provenance, True, False,
        )
        result = build_opportunity_segment(
            self.request(evidence_references=(categorical,))
        )
        self.assertEqual(result.verdict, OpportunitySegmentVerdict.VALID)
        self.assertIn(
            EventTimeEvidenceRequirement.USABLE_LIQUIDITY,
            {gap.requirement for gap in result.segment.evidence_gaps},
        )
        unsupported = build_opportunity_segment(
            self.request(
                evidence_references=(replace(categorical, quantitative_contract_complete=True),),
                opportunity_class=OpportunityEvidenceClass.REALISTICALLY_EXECUTABLE_OPPORTUNITY,
            )
        )
        self.assertEqual(unsupported.verdict, OpportunitySegmentVerdict.BLOCKED)
        self.assertIn("context_provider_cannot_prove_execution", unsupported.reasons)

    def test_manipulation_context_does_not_determine_execution_realism(self) -> None:
        context = replace(
            self.context,
            market_integrity=MarketIntegrityCondition.MANIPULATION_CONTEXT_PRESENT,
            tradeability=Tradeability.MANIPULATED_REALISTICALLY_TRADEABLE,
        )
        segment = build_opportunity_segment(self.request(manipulation_context=context))
        self.assertEqual(segment.verdict, OpportunitySegmentVerdict.VALID)
        self.assertEqual(
            segment.segment.opportunity_class, OpportunityEvidenceClass.CHART_OPPORTUNITY
        )
        self.assertEqual(
            segment.segment.participant_authenticity, UnknownState.UNKNOWN
        )

    def test_reentry_requires_a_distinct_fresh_checkpoint(self) -> None:
        missing = build_opportunity_segment(
            self.request(path_context=TradeablePathContext.REENTRY_CHURN)
        )
        self.assertEqual(missing.verdict, OpportunitySegmentVerdict.BLOCKED)
        reused = build_opportunity_segment(
            self.request(
                path_context=TradeablePathContext.REENTRY_CHURN,
                reentry_link=ReentryLink(
                    "prior", "checkpoint-a", "checkpoint-a",
                    T0 + timedelta(minutes=2),
                ),
            )
        )
        self.assertEqual(reused.verdict, OpportunitySegmentVerdict.BLOCKED)
        fresh = self.make_checkpoint(
            "checkpoint-fresh", 3, (EvaluationPath.FRESH_REENTRY_REVIEW,)
        )
        valid = build_opportunity_segment(
            self.request(
                path_context=TradeablePathContext.REENTRY_CHURN,
                checkpoints=(self.checkpoint, fresh),
                evidence_gaps=self.gaps("checkpoint-fresh"),
                evidence_cutoff=T0 + timedelta(minutes=3),
                reentry_link=ReentryLink(
                    "prior", "checkpoint-a", "checkpoint-fresh",
                    T0 + timedelta(minutes=2),
                ),
            )
        )
        self.assertEqual(valid.verdict, OpportunitySegmentVerdict.VALID)

    def test_later_evidence_cannot_mutate_a_frozen_segment(self) -> None:
        segment = build_opportunity_segment(self.request()).segment
        with self.assertRaises(FrozenInstanceError):
            segment.segment_id = "rewritten"
        later = EventTimeEvidenceReference(
            "later-route", EventTimeEvidenceRequirement.ROUTE, self.identity,
            "checkpoint-a", T0 + timedelta(minutes=3), self.jupiter_provenance,
            True, True,
        )
        evaluation = evaluate_later_segment_evidence(segment, (later,))
        self.assertEqual(evaluation.verdict, OpportunitySegmentVerdict.VALID)
        self.assertIs(evaluation.evaluation.segment, segment)
        self.assertTrue(evaluation.evaluation.segment_unchanged)
        self.assertEqual(segment.evidence_cutoff, T0 + timedelta(minutes=2))

    def test_identical_inputs_are_deterministic(self) -> None:
        request = self.request()
        self.assertEqual(
            build_opportunity_segment(request), build_opportunity_segment(request)
        )

    def test_no_locked_capability_rows_are_created(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE locked_capabilities (name TEXT)")
        before = connection.total_changes
        result = build_opportunity_segment(self.request())
        self.assertEqual(result.verdict, OpportunitySegmentVerdict.VALID)
        self.assertEqual(connection.total_changes, before)
        self.assertEqual(
            connection.execute("SELECT COUNT(*) FROM locked_capabilities").fetchone()[0], 0
        )
        self.assertFalse(result.segment.retrieval_authority)
        self.assertFalse(result.segment.decision_authority)
        self.assertFalse(result.segment.financial_authority)


if __name__ == "__main__":
    unittest.main()

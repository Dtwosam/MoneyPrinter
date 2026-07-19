"""Focused V2-9.7D.5B manipulation-aware context object proof."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import sqlite3
import unittest

from printer_v1.contracts.enums import MemoryStatus
from printer_v1.scheduler.manipulation_context import (
    ActionEligibility,
    ManipulationBehaviorClaim,
    ManipulationBehaviorFamily,
    ManipulationContextRequest,
    ManipulationContextVerdict,
    ManipulationLifecycleStage,
    ManipulationStageTransition,
    MarketIntegrityCondition,
    ParticipantUnknowns,
    Tradeability,
    UnknownState,
    build_manipulation_context,
    evaluate_later_manipulation_evidence,
)
from printer_v1.scheduler.support_only_5m_capture import (
    ExpectedSupportCaptureIdentity,
    GovernedSourceProvenance,
    SupportCaptureBudgets,
    SupportCaptureRequest,
    SupportTriggerFamily,
    TriggeringSnapshot,
    evaluate_support_only_5m_capture,
)
from printer_v1.scheduler.trajectory_checkpoint import (
    CheckpointKind,
    CheckpointRequest,
    FixedTrajectoryRequest,
    PhaseClaim,
    ReversalClaim,
    TrajectoryIdentity,
    TrajectoryObservation,
    VisibleEvidenceGap,
    build_checkpoint,
    build_fixed_trajectory,
)


T0 = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)


class ManipulationAwareContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.identity = TrajectoryIdentity(
            "campaign-5b", "run-5b", "cycle-1", "slot-a", "token-a",
            "mint-a", "pair-a", "root-15m-a", "window-15m-a",
        )
        self.provenance = GovernedSourceProvenance(
            "dexscreener", 21, 22, "scheduler-a", "COMPLETE", "CLEAN_DATA",
            True, True,
        )

    def observation(self, snapshot_id: int, minute: int, **changes):
        value = TrajectoryObservation(
            snapshot_id, self.identity, T0 + timedelta(minutes=minute),
            self.provenance,
        )
        return replace(value, **changes)

    def trajectory(self, observations=None, gaps=()):
        observations = observations or (self.observation(1, 0), self.observation(2, 1))
        phase_support = (
            (observations[0].snapshot_id,)
            if gaps
            else tuple(o.snapshot_id for o in observations)
        )
        result = build_fixed_trajectory(
            FixedTrajectoryRequest(
                self.identity, self.identity, "scheduler-a", observations, gaps,
                (PhaseClaim("INITIAL_EXPANSION", phase_support),),
                (ReversalClaim("NO_CONFIRMED_REVERSAL", (observations[-1].snapshot_id,)),),
            )
        )
        self.assertIsNotNone(result.trajectory)
        return result.trajectory

    def checkpoint(self, trajectory=None):
        trajectory = trajectory or self.trajectory()
        result = build_checkpoint(
            CheckpointRequest(
                "checkpoint-5b", trajectory, CheckpointKind.SCHEDULED_CADENCE,
                T0 + timedelta(minutes=1), T0 + timedelta(minutes=1), (),
                "scheduler-a",
            )
        )
        self.assertIsNotNone(result.checkpoint)
        return result.checkpoint

    def request(self, **changes):
        trajectory = changes.pop("trajectory") if "trajectory" in changes else self.trajectory()
        checkpoint = (
            changes.pop("checkpoint")
            if "checkpoint" in changes
            else self.checkpoint(trajectory)
        )
        value = ManipulationContextRequest(
            "context-5b", trajectory, checkpoint,
            ManipulationLifecycleStage.ARTIFICIAL_ACTIVITY,
            ManipulationStageTransition(
                ManipulationLifecycleStage.QUIET_PREPARATION_OR_ACCUMULATION,
                ManipulationLifecycleStage.ARTIFICIAL_ACTIVITY,
                (1, 2),
            ),
            (ManipulationBehaviorClaim(
                ManipulationBehaviorFamily.WASH_LIKE_OR_ARTIFICIAL_FLOW,
                (1, 2), flow_direction="FLOW_WASH_LIKE",
                wallet_participation="WALLETS_UNKNOWN",
            ),),
            MemoryStatus.CLEAN_MEMORY,
            MarketIntegrityCondition.MANIPULATION_CONTEXT_PRESENT,
            Tradeability.TRADEABILITY_UNKNOWN,
            ActionEligibility.ACTION_ELIGIBILITY_LOCKED,
        )
        return replace(value, **changes)

    def test_exact_fixed_vocabularies(self) -> None:
        self.assertEqual(len(ManipulationLifecycleStage), 10)
        self.assertEqual(len(ManipulationBehaviorFamily), 8)
        self.assertEqual(
            {item.value for item in MarketIntegrityCondition},
            {"NO_MANIPULATION_EVIDENCE", "MANIPULATION_CONTEXT_PRESENT",
             "MANIPULATION_CONTEXT_MIXED", "MARKET_INTEGRITY_UNKNOWN"},
        )
        self.assertEqual(len(Tradeability), 4)
        self.assertEqual(
            {item.value for item in ActionEligibility},
            {"ACTION_ELIGIBILITY_LOCKED", "ACTION_ELIGIBILITY_BLOCKED",
             "ACTION_ELIGIBILITY_UNKNOWN"},
        )
        self.assertEqual(
            {item.value for item in UnknownState},
            {"UNKNOWN", "UNKNOWN_REQUIRES_RESEARCH", "CURRENT_EVIDENCE_GAP"},
        )

    def test_four_dimensions_remain_independent_and_mixed_stays_mixed(self) -> None:
        result = build_manipulation_context(
            self.request(
                evidence_quality=MemoryStatus.DIRTY_MEMORY,
                market_integrity=MarketIntegrityCondition.MANIPULATION_CONTEXT_MIXED,
                tradeability=Tradeability.MANIPULATED_REALISTICALLY_TRADEABLE,
                action_eligibility=ActionEligibility.ACTION_ELIGIBILITY_UNKNOWN,
            )
        )
        self.assertEqual(result.verdict, ManipulationContextVerdict.VALID)
        self.assertEqual(result.context.evidence_quality, MemoryStatus.DIRTY_MEMORY)
        self.assertEqual(result.context.market_integrity, MarketIntegrityCondition.MANIPULATION_CONTEXT_MIXED)
        self.assertEqual(result.context.tradeability, Tradeability.MANIPULATED_REALISTICALLY_TRADEABLE)
        self.assertEqual(result.context.action_eligibility, ActionEligibility.ACTION_ELIGIBILITY_UNKNOWN)

    def test_dirty_useful_evidence_cannot_be_promoted_to_clean(self) -> None:
        dirty_provenance = replace(self.provenance, data_quality_label="DIRTY_DATA")
        observations = (
            self.observation(1, 0, provenance=dirty_provenance),
            self.observation(2, 1, provenance=dirty_provenance),
        )
        trajectory = self.trajectory(observations)
        checkpoint = self.checkpoint(trajectory)
        clean_claim = build_manipulation_context(
            self.request(
                trajectory=trajectory,
                checkpoint=checkpoint,
                evidence_quality=MemoryStatus.CLEAN_MEMORY,
            )
        )
        self.assertIn("unclean_evidence_cannot_be_promoted_to_clean", clean_claim.reasons)
        preserved = build_manipulation_context(
            self.request(
                trajectory=trajectory,
                checkpoint=checkpoint,
                evidence_quality=MemoryStatus.DIRTY_MEMORY,
            )
        )
        self.assertEqual(preserved.verdict, ManipulationContextVerdict.VALID)
        self.assertEqual(preserved.context.evidence_quality, MemoryStatus.DIRTY_MEMORY)

    def test_all_approved_stages_are_accepted(self) -> None:
        for stage in ManipulationLifecycleStage:
            with self.subTest(stage=stage):
                result = build_manipulation_context(
                    self.request(lifecycle_stage=stage, transition=None)
                )
                self.assertEqual(result.verdict, ManipulationContextVerdict.VALID)
                self.assertEqual(result.context.lifecycle_stage, stage)

    def test_all_approved_behavior_families_are_accepted(self) -> None:
        for family in ManipulationBehaviorFamily:
            with self.subTest(family=family):
                claim = ManipulationBehaviorClaim(family, (1, 2))
                result = build_manipulation_context(
                    self.request(behavior_claims=(claim,))
                )
                self.assertEqual(result.verdict, ManipulationContextVerdict.VALID)

    def test_invented_stage_behavior_and_evidence_labels_are_rejected(self) -> None:
        cases = (
            self.request(lifecycle_stage="INVENTED_STAGE", transition=None),
            self.request(behavior_claims=(ManipulationBehaviorClaim("INVENTED_BEHAVIOR", (1, 2)),)),
            self.request(behavior_claims=(ManipulationBehaviorClaim(
                ManipulationBehaviorFamily.FAST_COORDINATED_PUMP, (1, 2),
                safety_status="INVENTED_SAFETY",
            ),)),
        )
        for request in cases:
            with self.subTest(request=request):
                self.assertEqual(build_manipulation_context(request).verdict, ManipulationContextVerdict.BLOCKED)

    def test_valid_ordered_evidence_supports_adjacent_stage_transition(self) -> None:
        result = build_manipulation_context(self.request())
        self.assertEqual(result.verdict, ManipulationContextVerdict.VALID)
        self.assertEqual(result.context.transition.supporting_snapshot_ids, (1, 2))
        self.assertEqual(tuple(o.snapshot_id for o in result.context.supporting_observations), (1, 2))
        self.assertEqual(result.context.provenance, (self.provenance, self.provenance))

    def test_unsupported_or_gapped_stage_transition_fails_closed(self) -> None:
        unsupported = replace(
            self.request().transition,
            to_stage=ManipulationLifecycleStage.ATTENTION_EXPANSION,
        )
        self.assertEqual(
            build_manipulation_context(self.request(transition=unsupported)).verdict,
            ManipulationContextVerdict.BLOCKED,
        )
        observations = (self.observation(1, 0), self.observation(3, 3))
        gap = VisibleEvidenceGap(
            "gap-1", 1, 3, T0 + timedelta(seconds=30),
            T0 + timedelta(minutes=2, seconds=30), "missed cadence",
        )
        trajectory = self.trajectory(observations, (gap,))
        checkpoint = build_checkpoint(
            CheckpointRequest(
                "checkpoint-gap", trajectory, CheckpointKind.SCHEDULED_CADENCE,
                T0 + timedelta(minutes=3), T0 + timedelta(minutes=3), (), "scheduler-a",
            )
        ).checkpoint
        request = self.request(
            trajectory=trajectory,
            checkpoint=checkpoint,
            transition=ManipulationStageTransition(
                ManipulationLifecycleStage.QUIET_PREPARATION_OR_ACCUMULATION,
                ManipulationLifecycleStage.ARTIFICIAL_ACTIVITY, (1, 3),
            ),
            behavior_claims=(ManipulationBehaviorClaim(
                ManipulationBehaviorFamily.FAST_COORDINATED_PUMP, (1, 3),
            ),),
        )
        result = build_manipulation_context(request)
        self.assertIn("stage_transition_crosses_visible_evidence_gap", result.reasons)
        self.assertIn("behavior_claim_crosses_visible_evidence_gap", result.reasons)

    def test_stale_mismatched_and_post_cutoff_evidence_fail_closed(self) -> None:
        valid = self.trajectory()
        stale = replace(
            valid,
            observations=(
                self.observation(1, 0),
                self.observation(2, 1, freshness_within_contract=False),
            ),
        )
        foreign_identity = replace(self.identity, pair_id="pair-b")
        mismatched = replace(
            valid,
            observations=(
                self.observation(1, 0),
                self.observation(2, 1, identity=foreign_identity),
            ),
        )
        post_cutoff = replace(
            valid,
            observations=(self.observation(1, 0), self.observation(2, 2)),
        )
        for trajectory in (stale, mismatched, post_cutoff):
            with self.subTest(trajectory=trajectory):
                result = build_manipulation_context(
                    self.request(trajectory=trajectory, checkpoint=self.checkpoint())
                )
                self.assertEqual(result.verdict, ManipulationContextVerdict.BLOCKED)

    def test_manipulation_presence_can_keep_tradeability_unknown(self) -> None:
        result = build_manipulation_context(self.request())
        self.assertEqual(result.context.market_integrity, MarketIntegrityCondition.MANIPULATION_CONTEXT_PRESENT)
        self.assertEqual(result.context.tradeability, Tradeability.TRADEABILITY_UNKNOWN)

    def test_tradeable_context_cannot_unlock_action_eligibility(self) -> None:
        valid = build_manipulation_context(
            self.request(
                tradeability=Tradeability.MANIPULATED_REALISTICALLY_TRADEABLE,
                action_eligibility=ActionEligibility.ACTION_ELIGIBILITY_LOCKED,
            )
        )
        self.assertEqual(valid.verdict, ManipulationContextVerdict.VALID)
        self.assertFalse(valid.context.decision_authority)
        self.assertFalse(valid.context.financial_authority)
        blocked = build_manipulation_context(self.request(action_eligibility="BUY"))
        self.assertEqual(blocked.verdict, ManipulationContextVerdict.BLOCKED)

    def test_unsupported_wallet_and_participant_claims_remain_unknown(self) -> None:
        valid = build_manipulation_context(self.request())
        self.assertEqual(valid.context.participant_unknowns.participant_authenticity, UnknownState.UNKNOWN)
        self.assertEqual(valid.context.participant_unknowns.wallet_control, UnknownState.UNKNOWN_REQUIRES_RESEARCH)
        unsupported = ParticipantUnknowns(wallet_control="COMMON_CONTROL_PROVEN")
        blocked = build_manipulation_context(self.request(participant_unknowns=unsupported))
        self.assertIn("unsupported_wallet_or_participant_claim", blocked.reasons)

    def test_later_evidence_cannot_mutate_frozen_context(self) -> None:
        context = build_manipulation_context(self.request()).context
        before = context
        result = evaluate_later_manipulation_evidence(
            context, (self.observation(3, 2),),
        )
        self.assertEqual(result.verdict, ManipulationContextVerdict.VALID)
        self.assertEqual(result.evaluation.context, before)
        self.assertEqual(context, before)
        with self.assertRaises(FrozenInstanceError):
            context.tradeability = Tradeability.MANIPULATED_REALISTICALLY_TRADEABLE

    def test_4b_support_contributes_without_main_window_authority(self) -> None:
        capture = self.support_capture()
        result = build_manipulation_context(self.request(support_capture=capture))
        self.assertEqual(result.verdict, ManipulationContextVerdict.VALID)
        self.assertFalse(result.context.support_5m_has_main_authority)
        self.assertFalse(result.context.support_capture.main_outcome_memory)
        tampered = replace(capture, main_outcome_memory=True)
        blocked = build_manipulation_context(self.request(support_capture=tampered))
        self.assertIn("support_5m_authority_forbidden", blocked.reasons)

    def test_repeated_evaluation_is_deterministic_and_has_no_db_side_effect(self) -> None:
        connection = sqlite3.connect(":memory:")
        before = connection.total_changes
        request = self.request()
        self.assertEqual(build_manipulation_context(request), build_manipulation_context(request))
        self.assertEqual(connection.total_changes, before)
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND "
            "(name LIKE '%decision%' OR name LIKE '%position%' OR name LIKE '%trade%' OR name LIKE '%pnl%')"
        ).fetchall()
        self.assertEqual(tables, [])
        connection.close()

    def support_capture(self):
        expected = ExpectedSupportCaptureIdentity(
            *self.identity.__dict__.values(), "scheduler-a",
        )
        snapshots = tuple(
            TriggeringSnapshot(
                snapshot_id, *self.identity.__dict__.values(),
                T0 + timedelta(minutes=minute), True, self.provenance,
            )
            for snapshot_id, minute in ((1, 0), (2, 1))
        )
        request = SupportCaptureRequest(
            *self.identity.__dict__.values(), "WINDOW_15M", "WINDOW_OPEN",
            "scheduler-a", expected, SupportTriggerFamily.LIQUIDITY_SHOCK,
            T0 + timedelta(minutes=1), T0 + timedelta(minutes=1), snapshots,
            SupportCaptureBudgets(), "TRACK_FAST", True,
        )
        return evaluate_support_only_5m_capture(request).capture


if __name__ == "__main__":
    unittest.main()

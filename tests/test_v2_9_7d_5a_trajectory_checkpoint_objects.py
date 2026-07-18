"""Focused V2-9.7D.5A trajectory and checkpoint object proof."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import sqlite3
import unittest

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
    EvaluationPath,
    FixedTrajectoryRequest,
    PhaseClaim,
    ReversalClaim,
    TrajectoryCheckpointVerdict,
    TrajectoryIdentity,
    TrajectoryObservation,
    TrajectoryPhase,
    TrajectoryReversal,
    VisibleEvidenceGap,
    build_checkpoint,
    build_fixed_trajectory,
    evaluate_later_evidence,
    resolve_phase,
    resolve_reversal,
)


T0 = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


class TrajectoryCheckpointObjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.identity = TrajectoryIdentity(
            "campaign-5a", "run-5a", "cycle-1", "slot-a", "token-a",
            "mint-a", "pair-a", "root-15m-a", "window-15m-a",
        )
        self.provenance = GovernedSourceProvenance(
            "dexscreener", 11, 12, "scheduler-a", "COMPLETE", "CLEAN_DATA",
            True, True,
        )

    def observation(self, snapshot_id: int, minute: int, **changes) -> TrajectoryObservation:
        value = TrajectoryObservation(
            snapshot_id, self.identity, T0 + timedelta(minutes=minute),
            self.provenance, observed_peak=snapshot_id == 2,
        )
        return replace(value, **changes)

    def trajectory_request(self, **changes) -> FixedTrajectoryRequest:
        value = FixedTrajectoryRequest(
            identity=self.identity,
            expected_identity=self.identity,
            scheduler_work_id="scheduler-a",
            observations=(self.observation(1, 0), self.observation(2, 1)),
            gaps=(),
            phases=(PhaseClaim("INITIAL_EXPANSION", (1, 2)),),
            reversals=(ReversalClaim("NO_CONFIRMED_REVERSAL", (2,)),),
        )
        return replace(value, **changes)

    def trajectory(self):
        return build_fixed_trajectory(self.trajectory_request()).trajectory

    def test_fixed_vocabularies_and_unknown_preservation(self) -> None:
        expected_phases = {
            "OPENING_STATE", "QUIET_PREPARATION", "INITIAL_EXPANSION", "PULLBACK",
            "CONTINUATION", "CONSOLIDATION", "BREAKDOWN", "RECLAIM",
            "SECOND_EXPANSION", "DISTRIBUTION", "LIQUIDITY_DETERIORATION",
            "COLLAPSE", "SURVIVAL", "REVIVAL", "FINAL_OUTCOME", "EVIDENCE_GAP",
            "UNKNOWN_PHASE",
        }
        expected_reversals = {
            "NO_CONFIRMED_REVERSAL", "BREAKDOWN_TO_RECLAIM",
            "EXPANSION_TO_DISTRIBUTION", "COLLAPSE_TO_REVIVAL", "REVERSAL_UNKNOWN",
        }
        self.assertEqual({value.value for value in TrajectoryPhase}, expected_phases)
        self.assertEqual({value.value for value in TrajectoryReversal}, expected_reversals)
        for phase in TrajectoryPhase:
            self.assertEqual(resolve_phase(phase.value), phase)
        for reversal in TrajectoryReversal:
            self.assertEqual(resolve_reversal(reversal.value), reversal)
        self.assertEqual(resolve_phase("invented"), TrajectoryPhase.UNKNOWN_PHASE)
        self.assertEqual(resolve_reversal("invented"), TrajectoryReversal.REVERSAL_UNKNOWN)
        result = build_fixed_trajectory(
            self.trajectory_request(
                phases=(PhaseClaim("invented", (1,)),),
                reversals=(ReversalClaim("invented", (2,)),),
            )
        )
        self.assertEqual(result.verdict, TrajectoryCheckpointVerdict.VALID)
        self.assertEqual(result.trajectory.phases[0].phase, TrajectoryPhase.UNKNOWN_PHASE)
        self.assertEqual(result.trajectory.reversals[0].reversal, TrajectoryReversal.REVERSAL_UNKNOWN)

    def test_valid_trajectory_preserves_order_provenance_peak_and_exit_unknown(self) -> None:
        result = build_fixed_trajectory(self.trajectory_request())
        self.assertEqual(result.verdict, TrajectoryCheckpointVerdict.VALID)
        self.assertEqual(tuple(o.snapshot_id for o in result.trajectory.observations), (1, 2))
        self.assertEqual(result.trajectory.observed_peak_snapshot_ids, (2,))
        self.assertEqual(result.trajectory.realistically_capturable_exit, "UNKNOWN_REQUIRES_RESEARCH")
        self.assertFalse(result.trajectory.financial_authority)

    def test_duplicate_conflicting_ordered_foreign_and_provenance_fail_closed(self) -> None:
        cases = (
            self.trajectory_request(observations=(self.observation(1, 0), self.observation(1, 1))),
            self.trajectory_request(observations=(self.observation(1, 1), self.observation(2, 0))),
            self.trajectory_request(observations=(self.observation(1, 0), self.observation(2, 0))),
            self.trajectory_request(observations=(self.observation(1, 0), self.observation(2, 1, identity=replace(self.identity, pair_id="pair-b")))),
            self.trajectory_request(observations=(self.observation(1, 0), self.observation(2, 1, provenance=replace(self.provenance, traceable=False)))),
            self.trajectory_request(observations=(self.observation(1, 0), self.observation(2, 1, freshness_within_contract=False))),
            self.trajectory_request(phases=(PhaseClaim("PULLBACK", (1,)), PhaseClaim("CONTINUATION", (1,)))),
        )
        for request in cases:
            with self.subTest(request=request):
                self.assertEqual(build_fixed_trajectory(request).verdict, TrajectoryCheckpointVerdict.BLOCKED)

    def test_claims_require_exact_observations_and_cannot_cross_visible_gap(self) -> None:
        gap = VisibleEvidenceGap("gap-1", 1, 3, T0 + timedelta(seconds=30), T0 + timedelta(minutes=2, seconds=30), "missed cadence")
        observations = (self.observation(1, 0), self.observation(3, 3))
        crossed = self.trajectory_request(
            observations=observations,
            gaps=(gap,),
            phases=(PhaseClaim("CONTINUATION", (1, 3)),),
            reversals=(ReversalClaim("BREAKDOWN_TO_RECLAIM", (1, 3)),),
        )
        result = build_fixed_trajectory(crossed)
        self.assertEqual(result.verdict, TrajectoryCheckpointVerdict.BLOCKED)
        self.assertIn("phase_claim_crosses_visible_evidence_gap", result.reasons)
        self.assertIn("reversal_claim_crosses_visible_evidence_gap", result.reasons)
        missing = self.trajectory_request(phases=(PhaseClaim("PULLBACK", (999,)),))
        self.assertIn("phase_claim_observation_missing", build_fixed_trajectory(missing).reasons)

    def test_hidden_or_malformed_gap_blocks(self) -> None:
        gap = VisibleEvidenceGap("gap-1", 1, 2, T0, T0 + timedelta(minutes=1), "missed", visible=False)
        result = build_fixed_trajectory(self.trajectory_request(gaps=(gap,)))
        self.assertEqual(result.verdict, TrajectoryCheckpointVerdict.BLOCKED)
        self.assertIn("evidence_gap_must_remain_visible", result.reasons)

    def test_confirmed_reversal_requires_both_ordered_sides(self) -> None:
        result = build_fixed_trajectory(
            self.trajectory_request(
                reversals=(ReversalClaim("BREAKDOWN_TO_RECLAIM", (2,)),),
            )
        )
        self.assertIn("reversal_requires_observations_on_both_sides", result.reasons)

    def test_scheduled_checkpoint_has_exact_cutoff_identity_and_fixed_paths(self) -> None:
        request = CheckpointRequest(
            "checkpoint-1", self.trajectory(), CheckpointKind.SCHEDULED_CADENCE,
            T0 + timedelta(minutes=1), T0 + timedelta(minutes=1),
            tuple(EvaluationPath), "scheduler-a",
        )
        result = build_checkpoint(request)
        self.assertEqual(result.verdict, TrajectoryCheckpointVerdict.VALID)
        self.assertEqual(result.checkpoint.ordered_snapshot_ids, (1, 2))
        self.assertEqual(result.checkpoint.eligible_paths, tuple(EvaluationPath))
        self.assertFalse(result.checkpoint.mutable_by_later_evidence)
        with self.assertRaises(FrozenInstanceError):
            result.checkpoint.checkpoint_id = "rewritten"

    def test_post_cutoff_evidence_and_unsupported_path_block(self) -> None:
        trajectory = replace(
            self.trajectory(),
            observations=(self.observation(1, 0), self.observation(2, 2)),
        )
        base = CheckpointRequest(
            "checkpoint-1", trajectory, "SCHEDULED_DEADLINE",
            T0 + timedelta(minutes=1), T0 + timedelta(minutes=1),
            ("PROFIT_REVIEW",), "scheduler-a",
        )
        result = build_checkpoint(base)
        self.assertEqual(result.verdict, TrajectoryCheckpointVerdict.BLOCKED)
        self.assertIn("post_cutoff_observation_rejected", result.reasons)
        self.assertIn("unsupported_evaluation_path", result.reasons)

    def test_approved_event_checkpoint_requires_exact_4b_capture_link(self) -> None:
        capture = self.support_capture()
        trajectory = build_fixed_trajectory(
            self.trajectory_request(
                observations=(self.observation(1, 0), self.observation(2, 1)),
            )
        ).trajectory
        request = CheckpointRequest(
            "checkpoint-event", trajectory, CheckpointKind.APPROVED_EVENT,
            T0 + timedelta(minutes=1), T0 + timedelta(minutes=1),
            (EvaluationPath.WAIT_REVIEW,), "scheduler-a", capture,
        )
        result = build_checkpoint(request)
        self.assertEqual(result.verdict, TrajectoryCheckpointVerdict.VALID)
        self.assertEqual(result.checkpoint.event_trigger_family, SupportTriggerFamily.LIQUIDITY_SHOCK)
        self.assertEqual(result.checkpoint.event_support_snapshot_ids, (1, 2))
        self.assertFalse(result.checkpoint.support_5m_has_main_authority)
        mismatch = replace(capture, pair_id="pair-b")
        self.assertEqual(build_checkpoint(replace(request, event_capture=mismatch)).verdict, TrajectoryCheckpointVerdict.BLOCKED)

    def test_event_capture_is_rejected_for_scheduled_checkpoint(self) -> None:
        request = CheckpointRequest(
            "checkpoint-1", self.trajectory(), CheckpointKind.SCHEDULED_CADENCE,
            T0 + timedelta(minutes=1), T0 + timedelta(minutes=1), (),
            "scheduler-a", self.support_capture(),
        )
        self.assertIn("event_capture_for_non_event_checkpoint", build_checkpoint(request).reasons)

    def test_later_evidence_is_separate_and_cannot_rewrite_paths_or_checkpoint(self) -> None:
        checkpoint = build_checkpoint(
            CheckpointRequest(
                "checkpoint-1", self.trajectory(), CheckpointKind.SCHEDULED_CADENCE,
                T0 + timedelta(minutes=1), T0 + timedelta(minutes=1),
                (EvaluationPath.WAIT_REVIEW,), "scheduler-a",
            )
        ).checkpoint
        before = checkpoint
        result = evaluate_later_evidence(checkpoint, (self.observation(3, 2),))
        self.assertEqual(result.verdict, TrajectoryCheckpointVerdict.VALID)
        self.assertEqual(result.evaluation.checkpoint, before)
        self.assertEqual(result.evaluation.eligible_paths, (EvaluationPath.WAIT_REVIEW,))
        self.assertEqual(result.evaluation.checkpoint.gaps, checkpoint.gaps)
        self.assertEqual(checkpoint, before)
        leaked = evaluate_later_evidence(checkpoint, (self.observation(3, 1),))
        self.assertEqual(leaked.verdict, TrajectoryCheckpointVerdict.BLOCKED)

    def test_construction_is_deterministic_and_has_no_persistence_side_effect(self) -> None:
        connection = sqlite3.connect(":memory:")
        before = connection.total_changes
        request = self.trajectory_request()
        first = build_fixed_trajectory(request)
        second = build_fixed_trajectory(request)
        checkpoint_request = CheckpointRequest(
            "checkpoint-1", first.trajectory, CheckpointKind.SCHEDULED_DEADLINE,
            T0 + timedelta(minutes=1), T0 + timedelta(minutes=1),
            (EvaluationPath.NO_ACTION_REVIEW,), "scheduler-a",
        )
        self.assertEqual(first, second)
        self.assertEqual(build_checkpoint(checkpoint_request), build_checkpoint(checkpoint_request))
        self.assertEqual(connection.total_changes, before)
        connection.close()

    def support_capture(self):
        expected = ExpectedSupportCaptureIdentity(
            self.identity.campaign_id, self.identity.run_id, self.identity.cycle_id,
            self.identity.token_slot_id, self.identity.token_id, self.identity.mint_id,
            self.identity.pair_id, self.identity.root_15m_lifecycle_id,
            self.identity.containing_main_window_id, "scheduler-a",
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

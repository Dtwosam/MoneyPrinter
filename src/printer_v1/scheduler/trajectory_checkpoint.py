"""Immutable trajectory, transition, and checkpoint objects for V2-9.7D.5A.

This module validates already-observed evidence. It performs no collection,
scheduling, persistence, retrieval, decision, or financial action.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Iterable

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.scheduler.support_only_5m_capture import (
    GovernedSourceProvenance,
    SupportOnly5mCapture,
    SupportTriggerFamily,
)
from printer_v1.sources.registry import SOURCE_REGISTRY


class TrajectoryPhase(StrEnum):
    OPENING_STATE = "OPENING_STATE"
    QUIET_PREPARATION = "QUIET_PREPARATION"
    INITIAL_EXPANSION = "INITIAL_EXPANSION"
    PULLBACK = "PULLBACK"
    CONTINUATION = "CONTINUATION"
    CONSOLIDATION = "CONSOLIDATION"
    BREAKDOWN = "BREAKDOWN"
    RECLAIM = "RECLAIM"
    SECOND_EXPANSION = "SECOND_EXPANSION"
    DISTRIBUTION = "DISTRIBUTION"
    LIQUIDITY_DETERIORATION = "LIQUIDITY_DETERIORATION"
    COLLAPSE = "COLLAPSE"
    SURVIVAL = "SURVIVAL"
    REVIVAL = "REVIVAL"
    FINAL_OUTCOME = "FINAL_OUTCOME"
    EVIDENCE_GAP = "EVIDENCE_GAP"
    UNKNOWN_PHASE = "UNKNOWN_PHASE"


class TrajectoryReversal(StrEnum):
    NO_CONFIRMED_REVERSAL = "NO_CONFIRMED_REVERSAL"
    BREAKDOWN_TO_RECLAIM = "BREAKDOWN_TO_RECLAIM"
    EXPANSION_TO_DISTRIBUTION = "EXPANSION_TO_DISTRIBUTION"
    COLLAPSE_TO_REVIVAL = "COLLAPSE_TO_REVIVAL"
    REVERSAL_UNKNOWN = "REVERSAL_UNKNOWN"


class CheckpointKind(StrEnum):
    SCHEDULED_CADENCE = "SCHEDULED_CADENCE"
    SCHEDULED_DEADLINE = "SCHEDULED_DEADLINE"
    APPROVED_EVENT = "APPROVED_EVENT"


class EvaluationPath(StrEnum):
    ENTRY_REVIEW = "ENTRY_REVIEW"
    HOLD_REVIEW = "HOLD_REVIEW"
    EXIT_REVIEW = "EXIT_REVIEW"
    WAIT_REVIEW = "WAIT_REVIEW"
    AVOID_REVIEW = "AVOID_REVIEW"
    NO_ACTION_REVIEW = "NO_ACTION_REVIEW"
    FRESH_REENTRY_REVIEW = "FRESH_REENTRY_REVIEW"


class TrajectoryCheckpointVerdict(StrEnum):
    VALID = "VALID"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class TrajectoryIdentity:
    campaign_id: str
    run_id: str
    cycle_id: str
    token_slot_id: str
    token_id: str
    mint_id: str
    pair_id: str
    root_15m_lifecycle_id: str
    containing_main_window_id: str


@dataclass(frozen=True)
class TrajectoryObservation:
    snapshot_id: int
    identity: TrajectoryIdentity
    observed_at: datetime
    provenance: GovernedSourceProvenance
    freshness_within_contract: bool = True
    observed_peak: bool = False


@dataclass(frozen=True)
class VisibleEvidenceGap:
    gap_id: str
    before_snapshot_id: int
    after_snapshot_id: int
    opened_at: datetime
    closed_at: datetime
    reason: str
    visible: bool = True


@dataclass(frozen=True)
class PhaseClaim:
    phase: TrajectoryPhase | str
    supporting_snapshot_ids: tuple[int, ...]


@dataclass(frozen=True)
class ReversalClaim:
    reversal: TrajectoryReversal | str
    supporting_snapshot_ids: tuple[int, ...]


@dataclass(frozen=True)
class FixedTrajectoryRequest:
    identity: TrajectoryIdentity
    expected_identity: TrajectoryIdentity
    scheduler_work_id: str
    observations: tuple[TrajectoryObservation, ...]
    gaps: tuple[VisibleEvidenceGap, ...]
    phases: tuple[PhaseClaim, ...]
    reversals: tuple[ReversalClaim, ...]


@dataclass(frozen=True)
class FixedTrajectory:
    identity: TrajectoryIdentity
    scheduler_work_id: str
    observations: tuple[TrajectoryObservation, ...]
    gaps: tuple[VisibleEvidenceGap, ...]
    phases: tuple[PhaseClaim, ...]
    reversals: tuple[ReversalClaim, ...]
    observed_peak_snapshot_ids: tuple[int, ...]
    realistically_capturable_exit: str = "UNKNOWN_REQUIRES_RESEARCH"
    representation_only: bool = True
    support_5m_has_main_authority: bool = False
    retrieval_authority: bool = False
    decision_authority: bool = False
    financial_authority: bool = False


@dataclass(frozen=True)
class TrajectoryResult:
    verdict: TrajectoryCheckpointVerdict
    reasons: tuple[str, ...]
    trajectory: FixedTrajectory | None


@dataclass(frozen=True)
class CheckpointRequest:
    checkpoint_id: str
    trajectory: FixedTrajectory
    kind: CheckpointKind | str
    checkpoint_time: datetime
    evidence_cutoff: datetime
    eligible_paths: tuple[EvaluationPath | str, ...]
    scheduler_work_id: str
    event_capture: SupportOnly5mCapture | None = None


@dataclass(frozen=True)
class TrajectoryCheckpoint:
    checkpoint_id: str
    identity: TrajectoryIdentity
    kind: CheckpointKind
    checkpoint_time: datetime
    evidence_cutoff: datetime
    scheduler_work_id: str
    ordered_snapshot_ids: tuple[int, ...]
    provenance: tuple[GovernedSourceProvenance, ...]
    gaps: tuple[VisibleEvidenceGap, ...]
    phases: tuple[PhaseClaim, ...]
    reversals: tuple[ReversalClaim, ...]
    eligible_paths: tuple[EvaluationPath, ...]
    event_trigger_family: SupportTriggerFamily | None
    event_support_snapshot_ids: tuple[int, ...]
    realistically_capturable_exit: str = "UNKNOWN_REQUIRES_RESEARCH"
    representation_only: bool = True
    mutable_by_later_evidence: bool = False
    support_5m_has_main_authority: bool = False
    retrieval_authority: bool = False
    decision_authority: bool = False
    financial_authority: bool = False


@dataclass(frozen=True)
class CheckpointResult:
    verdict: TrajectoryCheckpointVerdict
    reasons: tuple[str, ...]
    checkpoint: TrajectoryCheckpoint | None


@dataclass(frozen=True)
class CheckpointEvaluation:
    checkpoint: TrajectoryCheckpoint
    later_observations: tuple[TrajectoryObservation, ...]
    eligible_paths: tuple[EvaluationPath, ...]
    checkpoint_unchanged: bool = True
    evaluation_only: bool = True


@dataclass(frozen=True)
class CheckpointEvaluationResult:
    verdict: TrajectoryCheckpointVerdict
    reasons: tuple[str, ...]
    evaluation: CheckpointEvaluation | None


def resolve_phase(value: TrajectoryPhase | str) -> TrajectoryPhase:
    try:
        return TrajectoryPhase(value)
    except (TypeError, ValueError):
        return TrajectoryPhase.UNKNOWN_PHASE


def resolve_reversal(value: TrajectoryReversal | str) -> TrajectoryReversal:
    try:
        return TrajectoryReversal(value)
    except (TypeError, ValueError):
        return TrajectoryReversal.REVERSAL_UNKNOWN


def build_fixed_trajectory(request: FixedTrajectoryRequest) -> TrajectoryResult:
    reasons: list[str] = []
    if request.identity != request.expected_identity:
        reasons.append("trajectory_identity_mismatch")
    if not _valid_identity(request.identity):
        reasons.append("invalid_trajectory_identity")
    if not _valid_text(request.scheduler_work_id):
        reasons.append("invalid_scheduler_work_identity")

    observations = request.observations
    snapshot_ids = tuple(observation.snapshot_id for observation in observations)
    if not observations:
        reasons.append("trajectory_observations_required")
    if any(not isinstance(snapshot_id, int) or snapshot_id <= 0 for snapshot_id in snapshot_ids):
        reasons.append("invalid_snapshot_identity")
    if len(set(snapshot_ids)) != len(snapshot_ids):
        reasons.append("duplicate_snapshot_identity")

    observed_times: list[datetime] = []
    for observation in observations:
        if observation.identity != request.identity:
            reasons.append("foreign_or_mismatched_observation")
        try:
            observed_times.append(_utc(observation.observed_at))
        except ValueError:
            reasons.append("observation_time_not_timezone_aware")
        if not observation.freshness_within_contract:
            reasons.append("stale_trajectory_observation")
        _append_provenance_reasons(
            observation.provenance,
            request.scheduler_work_id,
            reasons,
        )
    if observed_times and any(
        later <= earlier for earlier, later in zip(observed_times, observed_times[1:])
    ):
        reasons.append("observations_not_strictly_chronological")

    positions = {snapshot_id: index for index, snapshot_id in enumerate(snapshot_ids)}
    _append_gap_reasons(request.gaps, positions, observations, reasons)
    phases = tuple(
        PhaseClaim(resolve_phase(claim.phase), claim.supporting_snapshot_ids)
        for claim in request.phases
    )
    reversals = tuple(
        ReversalClaim(resolve_reversal(claim.reversal), claim.supporting_snapshot_ids)
        for claim in request.reversals
    )
    _append_claim_reasons(phases, request.gaps, positions, "phase", reasons)
    _append_claim_reasons(reversals, request.gaps, positions, "reversal", reasons)
    _append_conflicting_claim_reasons(phases, "phase", reasons)
    _append_conflicting_claim_reasons(reversals, "reversal", reasons)
    for claim in reversals:
        if claim.reversal not in {
            TrajectoryReversal.NO_CONFIRMED_REVERSAL,
            TrajectoryReversal.REVERSAL_UNKNOWN,
        } and len(claim.supporting_snapshot_ids) < 2:
            reasons.append("reversal_requires_observations_on_both_sides")

    if reasons:
        return _trajectory_result(reasons)
    trajectory = FixedTrajectory(
        identity=request.identity,
        scheduler_work_id=request.scheduler_work_id,
        observations=observations,
        gaps=request.gaps,
        phases=phases,
        reversals=reversals,
        observed_peak_snapshot_ids=tuple(
            observation.snapshot_id for observation in observations if observation.observed_peak
        ),
    )
    return TrajectoryResult(
        TrajectoryCheckpointVerdict.VALID,
        ("fixed_trajectory_valid",),
        trajectory,
    )


def build_checkpoint(request: CheckpointRequest) -> CheckpointResult:
    reasons: list[str] = []
    if not _valid_text(request.checkpoint_id):
        reasons.append("invalid_checkpoint_identity")
    if request.scheduler_work_id != request.trajectory.scheduler_work_id:
        reasons.append("checkpoint_scheduler_work_mismatch")
    try:
        kind = CheckpointKind(request.kind)
    except (TypeError, ValueError):
        reasons.append("unsupported_checkpoint_kind")
        kind = None
    try:
        checkpoint_time = _utc(request.checkpoint_time)
        cutoff = _utc(request.evidence_cutoff)
        if cutoff != checkpoint_time:
            reasons.append("evidence_cutoff_must_equal_checkpoint_time")
    except ValueError:
        reasons.append("checkpoint_time_or_cutoff_not_timezone_aware")
        checkpoint_time = request.checkpoint_time
        cutoff = request.evidence_cutoff

    paths: list[EvaluationPath] = []
    for path in request.eligible_paths:
        try:
            paths.append(EvaluationPath(path))
        except (TypeError, ValueError):
            reasons.append("unsupported_evaluation_path")
    if len(set(paths)) != len(paths):
        reasons.append("duplicate_evaluation_path")

    for observation in request.trajectory.observations:
        try:
            if _utc(observation.observed_at) > cutoff:
                reasons.append("post_cutoff_observation_rejected")
        except (TypeError, ValueError):
            reasons.append("observation_time_not_timezone_aware")

    event_family: SupportTriggerFamily | None = None
    event_snapshot_ids: tuple[int, ...] = ()
    if kind == CheckpointKind.APPROVED_EVENT:
        event_family, event_snapshot_ids = _validate_event_capture(request, reasons)
    elif request.event_capture is not None:
        reasons.append("event_capture_for_non_event_checkpoint")

    if reasons or kind is None:
        return _checkpoint_result(reasons)
    trajectory = request.trajectory
    checkpoint = TrajectoryCheckpoint(
        checkpoint_id=request.checkpoint_id,
        identity=trajectory.identity,
        kind=kind,
        checkpoint_time=checkpoint_time,
        evidence_cutoff=cutoff,
        scheduler_work_id=request.scheduler_work_id,
        ordered_snapshot_ids=tuple(o.snapshot_id for o in trajectory.observations),
        provenance=tuple(o.provenance for o in trajectory.observations),
        gaps=trajectory.gaps,
        phases=trajectory.phases,
        reversals=trajectory.reversals,
        eligible_paths=tuple(paths),
        event_trigger_family=event_family,
        event_support_snapshot_ids=event_snapshot_ids,
    )
    return CheckpointResult(
        TrajectoryCheckpointVerdict.VALID,
        ("immutable_checkpoint_valid",),
        checkpoint,
    )


def evaluate_later_evidence(
    checkpoint: TrajectoryCheckpoint,
    later_observations: tuple[TrajectoryObservation, ...],
) -> CheckpointEvaluationResult:
    reasons: list[str] = []
    previous_time = checkpoint.evidence_cutoff
    seen = set(checkpoint.ordered_snapshot_ids)
    for observation in later_observations:
        if observation.identity != checkpoint.identity:
            reasons.append("foreign_or_mismatched_later_observation")
        if observation.snapshot_id in seen or observation.snapshot_id <= 0:
            reasons.append("duplicate_or_invalid_later_snapshot_identity")
        seen.add(observation.snapshot_id)
        try:
            observed_at = _utc(observation.observed_at)
            if observed_at <= previous_time:
                reasons.append("later_evidence_not_strictly_after_checkpoint")
            previous_time = observed_at
        except ValueError:
            reasons.append("later_observation_time_not_timezone_aware")
        if not observation.freshness_within_contract:
            reasons.append("stale_later_observation")
        _append_provenance_reasons(
            observation.provenance,
            checkpoint.scheduler_work_id,
            reasons,
        )
    if reasons:
        return CheckpointEvaluationResult(
            TrajectoryCheckpointVerdict.BLOCKED,
            tuple(dict.fromkeys(reasons)),
            None,
        )
    return CheckpointEvaluationResult(
        TrajectoryCheckpointVerdict.VALID,
        ("later_evidence_evaluated_without_checkpoint_mutation",),
        CheckpointEvaluation(
            checkpoint=checkpoint,
            later_observations=later_observations,
            eligible_paths=checkpoint.eligible_paths,
        ),
    )


def _validate_event_capture(
    request: CheckpointRequest,
    reasons: list[str],
) -> tuple[SupportTriggerFamily | None, tuple[int, ...]]:
    capture = request.event_capture
    if capture is None:
        reasons.append("approved_event_capture_required")
        return None, ()
    identity = request.trajectory.identity
    comparisons = (
        capture.campaign_id == identity.campaign_id,
        capture.run_id == identity.run_id,
        capture.cycle_id == identity.cycle_id,
        capture.token_slot_id == identity.token_slot_id,
        capture.token_id == identity.token_id,
        capture.mint_id == identity.mint_id,
        capture.pair_id == identity.pair_id,
        capture.root_15m_lifecycle_id == identity.root_15m_lifecycle_id,
        capture.containing_main_window_id == identity.containing_main_window_id,
        capture.scheduler_work_id == request.scheduler_work_id,
    )
    if not all(comparisons):
        reasons.append("event_capture_identity_mismatch")
    if not capture.support_only or capture.main_outcome_memory:
        reasons.append("event_capture_not_support_only")
    try:
        if _utc(capture.trigger_time) != _utc(request.checkpoint_time):
            reasons.append("event_trigger_time_mismatch")
    except ValueError:
        reasons.append("event_trigger_time_not_timezone_aware")
    support_ids = tuple(snapshot.snapshot_id for snapshot in capture.triggering_snapshots)
    trajectory_ids = {o.snapshot_id for o in request.trajectory.observations}
    if not set(support_ids).issubset(trajectory_ids):
        reasons.append("event_support_snapshots_not_exact_linked")
    return capture.trigger_family, support_ids


def _append_gap_reasons(
    gaps: tuple[VisibleEvidenceGap, ...],
    positions: dict[int, int],
    observations: tuple[TrajectoryObservation, ...],
    reasons: list[str],
) -> None:
    seen: set[str] = set()
    prior_after_position = -1
    for gap in gaps:
        if not _valid_text(gap.gap_id) or gap.gap_id in seen:
            reasons.append("duplicate_or_invalid_gap_identity")
        seen.add(gap.gap_id)
        if not gap.visible:
            reasons.append("evidence_gap_must_remain_visible")
        if gap.before_snapshot_id not in positions or gap.after_snapshot_id not in positions:
            reasons.append("gap_snapshot_identity_missing")
            continue
        before = positions[gap.before_snapshot_id]
        after = positions[gap.after_snapshot_id]
        if before >= after:
            reasons.append("gap_snapshot_order_invalid")
        if before < prior_after_position:
            reasons.append("evidence_gaps_not_ordered")
        prior_after_position = after
        try:
            opened_at, closed_at = _utc(gap.opened_at), _utc(gap.closed_at)
            if opened_at >= closed_at:
                reasons.append("gap_time_order_invalid")
            if opened_at < _utc(observations[before].observed_at):
                reasons.append("gap_opens_before_preceding_observation")
            if closed_at > _utc(observations[after].observed_at):
                reasons.append("gap_closes_after_following_observation")
        except ValueError:
            reasons.append("gap_time_not_timezone_aware")
        if not _valid_text(gap.reason):
            reasons.append("gap_reason_required")


def _append_claim_reasons(
    claims: tuple[PhaseClaim, ...] | tuple[ReversalClaim, ...],
    gaps: tuple[VisibleEvidenceGap, ...],
    positions: dict[int, int],
    label: str,
    reasons: list[str],
) -> None:
    for claim in claims:
        support = claim.supporting_snapshot_ids
        if not support or len(set(support)) != len(support):
            reasons.append(f"{label}_claim_requires_unique_exact_observations")
            continue
        if any(snapshot_id not in positions for snapshot_id in support):
            reasons.append(f"{label}_claim_observation_missing")
            continue
        claim_positions = [positions[snapshot_id] for snapshot_id in support]
        for gap in gaps:
            if gap.before_snapshot_id not in positions or gap.after_snapshot_id not in positions:
                continue
            if min(claim_positions) <= positions[gap.before_snapshot_id] and max(
                claim_positions
            ) >= positions[gap.after_snapshot_id]:
                reasons.append(f"{label}_claim_crosses_visible_evidence_gap")


def _append_conflicting_claim_reasons(
    claims: tuple[PhaseClaim, ...] | tuple[ReversalClaim, ...],
    label: str,
    reasons: list[str],
) -> None:
    meanings_by_support: dict[tuple[int, ...], object] = {}
    for claim in claims:
        support = claim.supporting_snapshot_ids
        meaning = claim.phase if isinstance(claim, PhaseClaim) else claim.reversal
        existing = meanings_by_support.get(support)
        if existing is not None:
            if existing == meaning:
                reasons.append(f"duplicate_{label}_claim")
            else:
                reasons.append(f"conflicting_{label}_claim")
        meanings_by_support[support] = meaning


def _append_provenance_reasons(
    provenance: GovernedSourceProvenance,
    scheduler_work_id: str,
    reasons: list[str],
) -> None:
    if provenance.source_name not in SOURCE_REGISTRY:
        reasons.append("unregistered_source_provenance")
    if provenance.source_request_id <= 0 or provenance.source_response_id <= 0:
        reasons.append("source_provenance_identity_missing")
    if provenance.scheduler_work_id != scheduler_work_id:
        reasons.append("source_provenance_scheduler_work_mismatch")
    if not provenance.governor_approved or not provenance.traceable:
        reasons.append("source_provenance_untraceable_or_ungoverned")
    try:
        SourceStatus(provenance.source_status)
        DataQualityLabel(provenance.data_quality_label)
    except (TypeError, ValueError):
        reasons.append("source_provenance_status_or_quality_unknown")


def _valid_identity(identity: TrajectoryIdentity) -> bool:
    return all(_valid_text(value) for value in identity.__dict__.values())


def _valid_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _trajectory_result(reasons: Iterable[str]) -> TrajectoryResult:
    return TrajectoryResult(
        TrajectoryCheckpointVerdict.BLOCKED,
        tuple(dict.fromkeys(reasons)),
        None,
    )


def _checkpoint_result(reasons: Iterable[str]) -> CheckpointResult:
    return CheckpointResult(
        TrajectoryCheckpointVerdict.BLOCKED,
        tuple(dict.fromkeys(reasons)),
        None,
    )

"""Immutable manipulation-aware context objects for V2-9.7D.5B.

The evaluator represents already-governed checkpoint evidence. It performs no
collection, scheduling, persistence, retrieval, decision, or financial action.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Iterable

from printer_v1.contracts.enums import DataQualityLabel, MemoryStatus, SourceStatus
from printer_v1.liquidity_exit.contracts import LiquidityStateLabel
from printer_v1.safety.contracts import DistributionLabel, SafetyStatusLabel
from printer_v1.scheduler.support_only_5m_capture import (
    GovernedSourceProvenance,
    SupportOnly5mCapture,
)
from printer_v1.scheduler.trajectory_checkpoint import (
    FixedTrajectory,
    TrajectoryCheckpoint,
    TrajectoryIdentity,
    TrajectoryObservation,
    VisibleEvidenceGap,
)
from printer_v1.sources.registry import SOURCE_REGISTRY
from printer_v1.trading_flow.contracts import (
    FlowDirectionLabel,
    WalletParticipationLabel,
)


class ManipulationLifecycleStage(StrEnum):
    QUIET_PREPARATION_OR_ACCUMULATION = "QUIET_PREPARATION_OR_ACCUMULATION"
    ARTIFICIAL_ACTIVITY = "ARTIFICIAL_ACTIVITY"
    ATTENTION_EXPANSION = "ATTENTION_EXPANSION"
    WIDER_PARTICIPATION = "WIDER_PARTICIPATION"
    INITIAL_DISTRIBUTION_PRESSURE = "INITIAL_DISTRIBUTION_PRESSURE"
    SHAKEOUT_OR_CONTINUATION = "SHAKEOUT_OR_CONTINUATION"
    SECOND_EXPANSION_OR_FAILED_RECOVERY = "SECOND_EXPANSION_OR_FAILED_RECOVERY"
    HEAVY_DISTRIBUTION = "HEAVY_DISTRIBUTION"
    LIQUIDITY_DETERIORATION = "LIQUIDITY_DETERIORATION"
    COLLAPSE_SURVIVAL_OR_REVIVAL = "COLLAPSE_SURVIVAL_OR_REVIVAL"


class ManipulationBehaviorFamily(StrEnum):
    FAST_COORDINATED_PUMP = "FAST_COORDINATED_PUMP"
    WASH_LIKE_OR_ARTIFICIAL_FLOW = "WASH_LIKE_OR_ARTIFICIAL_FLOW"
    CONCENTRATED_EARLY_OWNERSHIP_OR_SUSPECTED_INSIDER_DISTRIBUTION = (
        "CONCENTRATED_EARLY_OWNERSHIP_OR_SUSPECTED_INSIDER_DISTRIBUTION"
    )
    LIQUIDITY_ADD_PULL_LOCK_OR_UNLOCK_BEHAVIOR = (
        "LIQUIDITY_ADD_PULL_LOCK_OR_UNLOCK_BEHAVIOR"
    )
    DEV_CREATOR_POOL_OR_HOLDER_PRESSURE = "DEV_CREATOR_POOL_OR_HOLDER_PRESSURE"
    TRAP_WICK_LATE_BUY_OR_EXIT_FAILURE_BEHAVIOR = (
        "TRAP_WICK_LATE_BUY_OR_EXIT_FAILURE_BEHAVIOR"
    )
    DEAD_TO_ACTIVE_MANIPULATED_TO_ACTIVE_OR_REVIVAL_BEHAVIOR = (
        "DEAD_TO_ACTIVE_MANIPULATED_TO_ACTIVE_OR_REVIVAL_BEHAVIOR"
    )
    PARTICIPANT_AUTHENTICITY_UNCERTAINTY = (
        "PARTICIPANT_AUTHENTICITY_UNCERTAINTY"
    )


class MarketIntegrityCondition(StrEnum):
    NO_MANIPULATION_EVIDENCE = "NO_MANIPULATION_EVIDENCE"
    MANIPULATION_CONTEXT_PRESENT = "MANIPULATION_CONTEXT_PRESENT"
    MANIPULATION_CONTEXT_MIXED = "MANIPULATION_CONTEXT_MIXED"
    MARKET_INTEGRITY_UNKNOWN = "MARKET_INTEGRITY_UNKNOWN"


class Tradeability(StrEnum):
    MANIPULATED_REALISTICALLY_TRADEABLE = "MANIPULATED_REALISTICALLY_TRADEABLE"
    MANIPULATED_EXIT_QUALITY_DETERIORATING = (
        "MANIPULATED_EXIT_QUALITY_DETERIORATING"
    )
    MANIPULATED_REALISTICALLY_UNTRADEABLE = (
        "MANIPULATED_REALISTICALLY_UNTRADEABLE"
    )
    TRADEABILITY_UNKNOWN = "TRADEABILITY_UNKNOWN"


class ActionEligibility(StrEnum):
    ACTION_ELIGIBILITY_LOCKED = "ACTION_ELIGIBILITY_LOCKED"
    ACTION_ELIGIBILITY_BLOCKED = "ACTION_ELIGIBILITY_BLOCKED"
    ACTION_ELIGIBILITY_UNKNOWN = "ACTION_ELIGIBILITY_UNKNOWN"


class UnknownState(StrEnum):
    UNKNOWN = "UNKNOWN"
    UNKNOWN_REQUIRES_RESEARCH = "UNKNOWN_REQUIRES_RESEARCH"
    CURRENT_EVIDENCE_GAP = "CURRENT_EVIDENCE_GAP"


class ManipulationContextVerdict(StrEnum):
    VALID = "VALID"
    BLOCKED = "BLOCKED"


_EVIDENCE_QUALITY = frozenset(
    {
        MemoryStatus.CLEAN_MEMORY,
        MemoryStatus.PARTIAL_MEMORY,
        MemoryStatus.DIRTY_MEMORY,
        MemoryStatus.DO_NOT_TRAIN,
    }
)
_STAGE_ORDER = tuple(ManipulationLifecycleStage)


@dataclass(frozen=True)
class ParticipantUnknowns:
    wallet_control: UnknownState | str = UnknownState.UNKNOWN_REQUIRES_RESEARCH
    participant_coordination: UnknownState | str = UnknownState.UNKNOWN_REQUIRES_RESEARCH
    insider_status: UnknownState | str = UnknownState.UNKNOWN_REQUIRES_RESEARCH
    participant_authenticity: UnknownState | str = UnknownState.UNKNOWN
    participant_intent: UnknownState | str = UnknownState.UNKNOWN_REQUIRES_RESEARCH
    participant_identity: UnknownState | str = UnknownState.UNKNOWN


@dataclass(frozen=True)
class ManipulationBehaviorClaim:
    family: ManipulationBehaviorFamily | str
    supporting_snapshot_ids: tuple[int, ...]
    safety_status: SafetyStatusLabel | str = SafetyStatusLabel.SAFETY_UNKNOWN
    holder_distribution: DistributionLabel | str = DistributionLabel.DISTRIBUTION_UNKNOWN
    liquidity_state: LiquidityStateLabel | str = LiquidityStateLabel.LIQUIDITY_UNKNOWN
    flow_direction: FlowDirectionLabel | str = FlowDirectionLabel.FLOW_UNKNOWN
    wallet_participation: WalletParticipationLabel | str = (
        WalletParticipationLabel.WALLETS_UNKNOWN
    )


@dataclass(frozen=True)
class ManipulationStageTransition:
    from_stage: ManipulationLifecycleStage | str
    to_stage: ManipulationLifecycleStage | str
    supporting_snapshot_ids: tuple[int, ...]


@dataclass(frozen=True)
class ManipulationContextRequest:
    context_id: str
    trajectory: FixedTrajectory
    checkpoint: TrajectoryCheckpoint
    lifecycle_stage: ManipulationLifecycleStage | str
    transition: ManipulationStageTransition | None
    behavior_claims: tuple[ManipulationBehaviorClaim, ...]
    evidence_quality: MemoryStatus | str
    market_integrity: MarketIntegrityCondition | str
    tradeability: Tradeability | str
    action_eligibility: ActionEligibility | str
    participant_unknowns: ParticipantUnknowns = ParticipantUnknowns()
    support_capture: SupportOnly5mCapture | None = None


@dataclass(frozen=True)
class ManipulationAwareContext:
    context_id: str
    identity: TrajectoryIdentity
    trajectory: FixedTrajectory
    checkpoint: TrajectoryCheckpoint
    lifecycle_stage: ManipulationLifecycleStage
    transition: ManipulationStageTransition | None
    behavior_claims: tuple[ManipulationBehaviorClaim, ...]
    evidence_quality: MemoryStatus
    market_integrity: MarketIntegrityCondition
    tradeability: Tradeability
    action_eligibility: ActionEligibility
    participant_unknowns: ParticipantUnknowns
    supporting_observations: tuple[TrajectoryObservation, ...]
    observed_times: tuple[datetime, ...]
    provenance: tuple[GovernedSourceProvenance, ...]
    evidence_cutoff: datetime
    support_capture: SupportOnly5mCapture | None
    representation_only: bool = True
    mutable_by_later_evidence: bool = False
    support_5m_has_main_authority: bool = False
    retrieval_authority: bool = False
    decision_authority: bool = False
    financial_authority: bool = False


@dataclass(frozen=True)
class ManipulationContextResult:
    verdict: ManipulationContextVerdict
    reasons: tuple[str, ...]
    context: ManipulationAwareContext | None


@dataclass(frozen=True)
class LaterManipulationEvidenceEvaluation:
    context: ManipulationAwareContext
    later_observations: tuple[TrajectoryObservation, ...]
    context_unchanged: bool = True
    evaluation_only: bool = True


@dataclass(frozen=True)
class LaterManipulationEvidenceResult:
    verdict: ManipulationContextVerdict
    reasons: tuple[str, ...]
    evaluation: LaterManipulationEvidenceEvaluation | None


def build_manipulation_context(
    request: ManipulationContextRequest,
) -> ManipulationContextResult:
    reasons: list[str] = []
    if not _valid_text(request.context_id):
        reasons.append("invalid_manipulation_context_identity")
    _append_checkpoint_linkage_reasons(request, reasons)

    stage = _enum_or_reason(
        ManipulationLifecycleStage,
        request.lifecycle_stage,
        "unsupported_manipulation_lifecycle_stage",
        reasons,
    )
    evidence_quality = _enum_or_reason(
        MemoryStatus,
        request.evidence_quality,
        "unsupported_evidence_quality",
        reasons,
    )
    if evidence_quality is not None and evidence_quality not in _EVIDENCE_QUALITY:
        reasons.append("unsupported_evidence_quality")
    market_integrity = _enum_or_reason(
        MarketIntegrityCondition,
        request.market_integrity,
        "unsupported_market_integrity_condition",
        reasons,
    )
    tradeability = _enum_or_reason(
        Tradeability,
        request.tradeability,
        "unsupported_tradeability",
        reasons,
    )
    action_eligibility = _enum_or_reason(
        ActionEligibility,
        request.action_eligibility,
        "unsupported_action_eligibility",
        reasons,
    )
    participant_unknowns = _normalize_unknowns(request.participant_unknowns, reasons)

    observations = request.trajectory.observations
    positions = {
        observation.snapshot_id: index for index, observation in enumerate(observations)
    }
    claims = _normalize_behavior_claims(
        request.behavior_claims,
        positions,
        request.trajectory.gaps,
        reasons,
    )
    transition = _normalize_transition(
        request.transition,
        stage,
        positions,
        request.trajectory.gaps,
        reasons,
    )
    if market_integrity in {
        MarketIntegrityCondition.MANIPULATION_CONTEXT_PRESENT,
        MarketIntegrityCondition.MANIPULATION_CONTEXT_MIXED,
    } and not claims:
        reasons.append("manipulation_context_requires_supported_behavior")
    if market_integrity == MarketIntegrityCondition.NO_MANIPULATION_EVIDENCE and claims:
        reasons.append("behavior_claim_conflicts_with_no_manipulation_evidence")

    _append_observation_reasons(
        observations,
        request.checkpoint,
        evidence_quality,
        reasons,
    )
    _append_support_capture_reasons(request, claims, reasons)

    if reasons or any(
        value is None
        for value in (
            stage,
            evidence_quality,
            market_integrity,
            tradeability,
            action_eligibility,
            participant_unknowns,
        )
    ):
        return _result(reasons)

    used_ids = {
        snapshot_id
        for claim in claims
        for snapshot_id in claim.supporting_snapshot_ids
    }
    if transition is not None:
        used_ids.update(transition.supporting_snapshot_ids)
    supporting = tuple(
        observation for observation in observations if observation.snapshot_id in used_ids
    )
    context = ManipulationAwareContext(
        context_id=request.context_id,
        identity=request.trajectory.identity,
        trajectory=request.trajectory,
        checkpoint=request.checkpoint,
        lifecycle_stage=stage,
        transition=transition,
        behavior_claims=claims,
        evidence_quality=evidence_quality,
        market_integrity=market_integrity,
        tradeability=tradeability,
        action_eligibility=action_eligibility,
        participant_unknowns=participant_unknowns,
        supporting_observations=supporting,
        observed_times=tuple(_utc(item.observed_at) for item in supporting),
        provenance=tuple(item.provenance for item in supporting),
        evidence_cutoff=_utc(request.checkpoint.evidence_cutoff),
        support_capture=request.support_capture,
    )
    return ManipulationContextResult(
        ManipulationContextVerdict.VALID,
        ("immutable_manipulation_context_valid",),
        context,
    )


def evaluate_later_manipulation_evidence(
    context: ManipulationAwareContext,
    later_observations: tuple[TrajectoryObservation, ...],
) -> LaterManipulationEvidenceResult:
    reasons: list[str] = []
    previous_time = context.evidence_cutoff
    seen = set(context.checkpoint.ordered_snapshot_ids)
    for observation in later_observations:
        if observation.identity != context.identity:
            reasons.append("foreign_or_mismatched_later_observation")
        if observation.snapshot_id in seen or observation.snapshot_id <= 0:
            reasons.append("duplicate_or_invalid_later_snapshot_identity")
        seen.add(observation.snapshot_id)
        try:
            observed_at = _utc(observation.observed_at)
            if observed_at <= previous_time:
                reasons.append("later_evidence_not_strictly_after_context_cutoff")
            previous_time = observed_at
        except ValueError:
            reasons.append("later_observation_time_not_timezone_aware")
        if not observation.freshness_within_contract:
            reasons.append("stale_later_observation")
        _append_provenance_reasons(
            observation.provenance,
            context.checkpoint.scheduler_work_id,
            reasons,
        )
    if reasons:
        return LaterManipulationEvidenceResult(
            ManipulationContextVerdict.BLOCKED,
            tuple(dict.fromkeys(reasons)),
            None,
        )
    return LaterManipulationEvidenceResult(
        ManipulationContextVerdict.VALID,
        ("later_evidence_evaluated_without_context_mutation",),
        LaterManipulationEvidenceEvaluation(context, later_observations),
    )


def _append_checkpoint_linkage_reasons(
    request: ManipulationContextRequest,
    reasons: list[str],
) -> None:
    trajectory = request.trajectory
    checkpoint = request.checkpoint
    if checkpoint.identity != trajectory.identity:
        reasons.append("checkpoint_trajectory_identity_mismatch")
    if checkpoint.scheduler_work_id != trajectory.scheduler_work_id:
        reasons.append("checkpoint_trajectory_scheduler_work_mismatch")
    if checkpoint.ordered_snapshot_ids != tuple(
        observation.snapshot_id for observation in trajectory.observations
    ):
        reasons.append("checkpoint_trajectory_snapshot_linkage_mismatch")
    if checkpoint.provenance != tuple(
        observation.provenance for observation in trajectory.observations
    ):
        reasons.append("checkpoint_trajectory_provenance_mismatch")
    if checkpoint.gaps != trajectory.gaps:
        reasons.append("checkpoint_trajectory_gap_mismatch")
    if checkpoint.phases != trajectory.phases or checkpoint.reversals != trajectory.reversals:
        reasons.append("checkpoint_trajectory_claim_mismatch")


def _normalize_behavior_claims(
    claims: tuple[ManipulationBehaviorClaim, ...],
    positions: dict[int, int],
    gaps: tuple[VisibleEvidenceGap, ...],
    reasons: list[str],
) -> tuple[ManipulationBehaviorClaim, ...]:
    normalized: list[ManipulationBehaviorClaim] = []
    seen_families: set[ManipulationBehaviorFamily] = set()
    for claim in claims:
        family = _enum_or_reason(
            ManipulationBehaviorFamily,
            claim.family,
            "unsupported_manipulation_behavior_family",
            reasons,
        )
        support = claim.supporting_snapshot_ids
        if not support or len(set(support)) != len(support):
            reasons.append("behavior_claim_requires_unique_exact_observations")
        elif any(snapshot_id not in positions for snapshot_id in support):
            reasons.append("behavior_claim_observation_missing")
        elif _crosses_gap(support, positions, gaps):
            reasons.append("behavior_claim_crosses_visible_evidence_gap")
        labels = (
            _enum_or_reason(SafetyStatusLabel, claim.safety_status, "unsupported_safety_evidence_label", reasons),
            _enum_or_reason(DistributionLabel, claim.holder_distribution, "unsupported_holder_evidence_label", reasons),
            _enum_or_reason(LiquidityStateLabel, claim.liquidity_state, "unsupported_liquidity_evidence_label", reasons),
            _enum_or_reason(FlowDirectionLabel, claim.flow_direction, "unsupported_flow_evidence_label", reasons),
            _enum_or_reason(WalletParticipationLabel, claim.wallet_participation, "unsupported_wallet_participation_label", reasons),
        )
        if family is None or any(label is None for label in labels):
            continue
        if family in seen_families:
            reasons.append("duplicate_manipulation_behavior_family")
        seen_families.add(family)
        normalized.append(
            ManipulationBehaviorClaim(family, support, *labels)
        )
    return tuple(normalized)


def _normalize_transition(
    transition: ManipulationStageTransition | None,
    current_stage: ManipulationLifecycleStage | None,
    positions: dict[int, int],
    gaps: tuple[VisibleEvidenceGap, ...],
    reasons: list[str],
) -> ManipulationStageTransition | None:
    if transition is None:
        return None
    from_stage = _enum_or_reason(
        ManipulationLifecycleStage,
        transition.from_stage,
        "unsupported_transition_from_stage",
        reasons,
    )
    to_stage = _enum_or_reason(
        ManipulationLifecycleStage,
        transition.to_stage,
        "unsupported_transition_to_stage",
        reasons,
    )
    support = transition.supporting_snapshot_ids
    if len(support) < 2 or len(set(support)) != len(support):
        reasons.append("stage_transition_requires_ordered_evidence_on_both_sides")
    elif any(snapshot_id not in positions for snapshot_id in support):
        reasons.append("stage_transition_observation_missing")
    elif [positions[item] for item in support] != sorted(positions[item] for item in support):
        reasons.append("stage_transition_evidence_not_ordered")
    elif _crosses_gap(support, positions, gaps):
        reasons.append("stage_transition_crosses_visible_evidence_gap")
    if from_stage is not None and to_stage is not None:
        if _STAGE_ORDER.index(to_stage) != _STAGE_ORDER.index(from_stage) + 1:
            reasons.append("unsupported_manipulation_stage_transition")
        if current_stage is not None and to_stage != current_stage:
            reasons.append("transition_destination_does_not_match_context_stage")
        return ManipulationStageTransition(from_stage, to_stage, support)
    return None


def _normalize_unknowns(
    unknowns: ParticipantUnknowns,
    reasons: list[str],
) -> ParticipantUnknowns | None:
    values: list[UnknownState] = []
    for value in unknowns.__dict__.values():
        normalized = _enum_or_reason(
            UnknownState,
            value,
            "unsupported_wallet_or_participant_claim",
            reasons,
        )
        if normalized is not None:
            values.append(normalized)
    if len(values) != len(unknowns.__dict__):
        return None
    return ParticipantUnknowns(*values)


def _append_observation_reasons(
    observations: tuple[TrajectoryObservation, ...],
    checkpoint: TrajectoryCheckpoint,
    evidence_quality: MemoryStatus | None,
    reasons: list[str],
) -> None:
    for observation in observations:
        if observation.identity != checkpoint.identity:
            reasons.append("foreign_or_mismatched_manipulation_evidence")
        try:
            if _utc(observation.observed_at) > _utc(checkpoint.evidence_cutoff):
                reasons.append("post_cutoff_manipulation_evidence")
        except ValueError:
            reasons.append("manipulation_evidence_time_not_timezone_aware")
        if not observation.freshness_within_contract:
            reasons.append("stale_manipulation_evidence")
        _append_provenance_reasons(
            observation.provenance,
            checkpoint.scheduler_work_id,
            reasons,
        )
        if evidence_quality == MemoryStatus.CLEAN_MEMORY and (
            str(observation.provenance.source_status) != SourceStatus.COMPLETE.value
            or str(observation.provenance.data_quality_label)
            != DataQualityLabel.CLEAN_DATA.value
        ):
            reasons.append("unclean_evidence_cannot_be_promoted_to_clean")


def _append_support_capture_reasons(
    request: ManipulationContextRequest,
    claims: tuple[ManipulationBehaviorClaim, ...],
    reasons: list[str],
) -> None:
    capture = request.support_capture
    if capture is None:
        return
    identity = request.trajectory.identity
    actual_identity = (
        capture.campaign_id,
        capture.run_id,
        capture.cycle_id,
        capture.token_slot_id,
        capture.token_id,
        capture.mint_id,
        capture.pair_id,
        capture.root_15m_lifecycle_id,
        capture.containing_main_window_id,
    )
    if actual_identity != tuple(identity.__dict__.values()):
        reasons.append("support_capture_identity_mismatch")
    if capture.scheduler_work_id != request.checkpoint.scheduler_work_id:
        reasons.append("support_capture_scheduler_work_mismatch")
    try:
        if _utc(capture.evidence_cutoff) > _utc(request.checkpoint.evidence_cutoff):
            reasons.append("post_cutoff_support_capture")
    except ValueError:
        reasons.append("support_capture_cutoff_not_timezone_aware")
    forbidden_authority = (
        not capture.support_only
        or capture.main_outcome_memory
        or capture.replaces_window_15m
        or capture.continuation_authority
        or capture.counts_toward_main_clean_memory
        or capture.lifecycle_disposition_authority
        or capture.retrieval_authority
        or capture.decision_authority
        or capture.financial_authority
    )
    if forbidden_authority:
        reasons.append("support_5m_authority_forbidden")
    capture_ids = {item.snapshot_id for item in capture.triggering_snapshots}
    claim_ids = {
        snapshot_id for claim in claims for snapshot_id in claim.supporting_snapshot_ids
    }
    if not capture_ids or not capture_ids.issubset(claim_ids):
        reasons.append("support_capture_not_exact_linked_to_behavior_evidence")


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


def _crosses_gap(
    support: tuple[int, ...],
    positions: dict[int, int],
    gaps: tuple[VisibleEvidenceGap, ...],
) -> bool:
    if not support or any(item not in positions for item in support):
        return False
    claim_positions = [positions[item] for item in support]
    return any(
        gap.before_snapshot_id in positions
        and gap.after_snapshot_id in positions
        and min(claim_positions) <= positions[gap.before_snapshot_id]
        and max(claim_positions) >= positions[gap.after_snapshot_id]
        for gap in gaps
    )


def _enum_or_reason(enum_type, value, reason: str, reasons: list[str]):
    try:
        return enum_type(value)
    except (TypeError, ValueError):
        reasons.append(reason)
        return None


def _valid_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _result(reasons: Iterable[str]) -> ManipulationContextResult:
    return ManipulationContextResult(
        ManipulationContextVerdict.BLOCKED,
        tuple(dict.fromkeys(reasons)),
        None,
    )

"""Immutable opportunity-segment and event-time gap objects for V2-9.7D.5C.

The builders validate already-governed evidence. They perform no source calls,
execution simulation, profitability calculation, persistence, or action.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Iterable

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.memory.contracts import EpisodeOutcomeLabel
from printer_v1.scheduler.manipulation_context import (
    ManipulationAwareContext,
    UnknownState,
)
from printer_v1.scheduler.support_only_5m_capture import GovernedSourceProvenance
from printer_v1.scheduler.trajectory_checkpoint import (
    EvaluationPath,
    FixedTrajectory,
    TrajectoryCheckpoint,
    TrajectoryIdentity,
    TrajectoryObservation,
)
from printer_v1.sources.registry import SOURCE_REGISTRY


class TradeablePathContext(StrEnum):
    EXPANSION_PULLBACK_CONTINUATION = "EXPANSION_PULLBACK_CONTINUATION"
    EXPANSION_THEN_FAILED_CONTINUATION = "EXPANSION_THEN_FAILED_CONTINUATION"
    FAST_BREAKDOWN_THEN_GENUINE_RECLAIM = "FAST_BREAKDOWN_THEN_GENUINE_RECLAIM"
    WICK_ONLY_PEAK = "WICK_ONLY_PEAK"
    PRICE_RISING_WHILE_EXIT_DETERIORATES = (
        "PRICE_RISING_WHILE_EXIT_DETERIORATES"
    )
    HIGH_VOLUME_WITH_WEAK_AUTHENTICITY = "HIGH_VOLUME_WITH_WEAK_AUTHENTICITY"
    GOOD_ENTRY_WITH_BAD_HOLD = "GOOD_ENTRY_WITH_BAD_HOLD"
    BAD_ENTRY_WITH_PROFITABLE_OUTCOME = "BAD_ENTRY_WITH_PROFITABLE_OUTCOME"
    CORRECT_EXIT_THEN_MORE_UPSIDE = "CORRECT_EXIT_THEN_MORE_UPSIDE"
    MISSED_ENTRY_WITH_NO_CHASE = "MISSED_ENTRY_WITH_NO_CHASE"
    REENTRY_CHURN = "REENTRY_CHURN"
    MARKET_CONTEXT_MISMATCH = "MARKET_CONTEXT_MISMATCH"


class OpportunityEvidenceClass(StrEnum):
    CHART_OPPORTUNITY = "CHART_OPPORTUNITY"
    REALISTICALLY_EXECUTABLE_OPPORTUNITY = "REALISTICALLY_EXECUTABLE_OPPORTUNITY"


class EventTimeEvidenceRequirement(StrEnum):
    ROUTE = "ROUTE"
    QUOTE = "QUOTE"
    QUOTE_FRESHNESS = "QUOTE_FRESHNESS"
    USABLE_LIQUIDITY = "USABLE_LIQUIDITY"
    PRICE_IMPACT = "PRICE_IMPACT"
    SLIPPAGE = "SLIPPAGE"
    FEES = "FEES"
    LATENCY = "LATENCY"
    OPPORTUNITY_DURATION = "OPPORTUNITY_DURATION"
    FAILED_ROUTE = "FAILED_ROUTE"
    EXECUTABLE_SIZE = "EXECUTABLE_SIZE"
    EXIT_CAPABILITY = "EXIT_CAPABILITY"


class OpportunitySegmentVerdict(StrEnum):
    VALID = "VALID"
    BLOCKED = "BLOCKED"


_REQUIREMENTS = frozenset(EventTimeEvidenceRequirement)
_EXECUTION_PROVIDERS = frozenset({"jupiter_quote"})
_CONTEXT_PROVIDERS = frozenset(
    {"jupiter_quote", "geckoterminal", "goplus", "solana_rpc"}
)
_CONTRACT_FIELDS = {
    EventTimeEvidenceRequirement.ROUTE: frozenset(
        {"input_mint", "output_mint", "route_plan"}
    ),
    EventTimeEvidenceRequirement.QUOTE: frozenset(
        {"in_amount", "out_amount", "other_amount_threshold", "swap_mode"}
    ),
    EventTimeEvidenceRequirement.QUOTE_FRESHNESS: frozenset(
        {"request_time", "response_time", "context_slot"}
    ),
    EventTimeEvidenceRequirement.USABLE_LIQUIDITY: frozenset(
        {"exact_pair_id", "position_size", "route_depth"}
    ),
    EventTimeEvidenceRequirement.PRICE_IMPACT: frozenset({"price_impact_pct"}),
    EventTimeEvidenceRequirement.SLIPPAGE: frozenset({"slippage_bps"}),
    EventTimeEvidenceRequirement.FEES: frozenset({"platform_fee", "route_fees"}),
    EventTimeEvidenceRequirement.LATENCY: frozenset(
        {"observation_time", "decision_time", "simulated_execution_time"}
    ),
    EventTimeEvidenceRequirement.OPPORTUNITY_DURATION: frozenset(
        {"opportunity_opened_at", "opportunity_closed_at"}
    ),
    EventTimeEvidenceRequirement.FAILED_ROUTE: frozenset({"structured_route_status"}),
    EventTimeEvidenceRequirement.EXECUTABLE_SIZE: frozenset(
        {"input_amount", "output_amount"}
    ),
    EventTimeEvidenceRequirement.EXIT_CAPABILITY: frozenset(
        {"reverse_route", "exit_quote", "exit_threshold"}
    ),
}


@dataclass(frozen=True)
class EventTimeEvidenceReference:
    evidence_id: str
    requirement: EventTimeEvidenceRequirement | str
    identity: TrajectoryIdentity
    checkpoint_id: str
    observed_at: datetime
    provenance: GovernedSourceProvenance
    freshness_within_contract: bool
    quantitative_contract_complete: bool = False
    contract_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventTimeEvidenceGap:
    gap_id: str
    requirement: EventTimeEvidenceRequirement | str
    state: UnknownState | str
    checkpoint_id: str
    reason: str
    visible: bool = True


@dataclass(frozen=True)
class ReentryLink:
    prior_segment_id: str
    prior_terminal_checkpoint_id: str
    fresh_checkpoint_id: str
    prior_segment_cutoff: datetime


@dataclass(frozen=True)
class OpportunitySegmentRequest:
    segment_id: str
    trajectory: FixedTrajectory
    checkpoints: tuple[TrajectoryCheckpoint, ...]
    manipulation_context: ManipulationAwareContext
    path_context: TradeablePathContext | str
    full_window_outcome: EpisodeOutcomeLabel | str
    internal_trade_opportunity_outcome: EpisodeOutcomeLabel | str
    opportunity_class: OpportunityEvidenceClass | str
    supporting_snapshot_ids: tuple[int, ...]
    evidence_references: tuple[EventTimeEvidenceReference, ...]
    evidence_gaps: tuple[EventTimeEvidenceGap, ...]
    evidence_cutoff: datetime
    observed_peak_snapshot_id: int | None = None
    realistically_capturable_exit_snapshot_id: int | None = None
    reentry_link: ReentryLink | None = None


@dataclass(frozen=True)
class OpportunitySegment:
    segment_id: str
    identity: TrajectoryIdentity
    trajectory: FixedTrajectory
    checkpoints: tuple[TrajectoryCheckpoint, ...]
    manipulation_context: ManipulationAwareContext
    path_context: TradeablePathContext
    full_window_outcome: EpisodeOutcomeLabel
    internal_trade_opportunity_outcome: EpisodeOutcomeLabel
    opportunity_class: OpportunityEvidenceClass
    supporting_observations: tuple[TrajectoryObservation, ...]
    provenance: tuple[GovernedSourceProvenance, ...]
    evidence_references: tuple[EventTimeEvidenceReference, ...]
    evidence_gaps: tuple[EventTimeEvidenceGap, ...]
    evidence_cutoff: datetime
    observed_peak_snapshot_id: int | None
    realistically_capturable_exit_snapshot_id: int | None
    reentry_link: ReentryLink | None
    participant_authenticity: UnknownState
    representation_only: bool = True
    mutable_by_later_evidence: bool = False
    retrieval_authority: bool = False
    decision_authority: bool = False
    financial_authority: bool = False


@dataclass(frozen=True)
class OpportunitySegmentResult:
    verdict: OpportunitySegmentVerdict
    reasons: tuple[str, ...]
    segment: OpportunitySegment | None


@dataclass(frozen=True)
class OpportunityWindow:
    identity: TrajectoryIdentity
    full_window_outcome: EpisodeOutcomeLabel
    segments: tuple[OpportunitySegment, ...]
    representation_only: bool = True
    financial_authority: bool = False


@dataclass(frozen=True)
class OpportunityWindowResult:
    verdict: OpportunitySegmentVerdict
    reasons: tuple[str, ...]
    window: OpportunityWindow | None


@dataclass(frozen=True)
class LaterSegmentEvidenceEvaluation:
    segment: OpportunitySegment
    later_evidence: tuple[EventTimeEvidenceReference, ...]
    segment_unchanged: bool = True
    evaluation_only: bool = True


@dataclass(frozen=True)
class LaterSegmentEvidenceResult:
    verdict: OpportunitySegmentVerdict
    reasons: tuple[str, ...]
    evaluation: LaterSegmentEvidenceEvaluation | None


def required_event_time_contract_fields(
    requirement: EventTimeEvidenceRequirement | str,
) -> tuple[str, ...]:
    """Return the fixed provider-contract fields required for one proof kind."""
    return tuple(sorted(_CONTRACT_FIELDS[EventTimeEvidenceRequirement(requirement)]))


def build_opportunity_segment(
    request: OpportunitySegmentRequest,
) -> OpportunitySegmentResult:
    reasons: list[str] = []
    if not _valid_text(request.segment_id):
        reasons.append("invalid_segment_identity")
    path = _enum_or_reason(
        TradeablePathContext, request.path_context, "unsupported_tradeable_path_context", reasons
    )
    full_outcome = _enum_or_reason(
        EpisodeOutcomeLabel, request.full_window_outcome, "unsupported_full_window_outcome", reasons
    )
    internal_outcome = _enum_or_reason(
        EpisodeOutcomeLabel,
        request.internal_trade_opportunity_outcome,
        "unsupported_internal_trade_opportunity_outcome",
        reasons,
    )
    opportunity_class = _enum_or_reason(
        OpportunityEvidenceClass,
        request.opportunity_class,
        "unsupported_opportunity_evidence_class",
        reasons,
    )
    try:
        cutoff = _utc(request.evidence_cutoff)
    except ValueError:
        reasons.append("segment_cutoff_not_timezone_aware")
        cutoff = request.evidence_cutoff

    _append_linkage_reasons(request, cutoff, reasons)
    observations = _ordered_supporting_observations(request, cutoff, reasons)
    references, complete = _validate_references(request, cutoff, reasons)
    gaps = _validate_gaps(request, reasons)
    if complete.intersection(gap.requirement for gap in gaps):
        reasons.append("complete_event_time_evidence_conflicts_with_gap")

    for requirement in _REQUIREMENTS - complete:
        if requirement not in {gap.requirement for gap in gaps}:
            reasons.append("missing_event_time_evidence_gap")
    if opportunity_class == OpportunityEvidenceClass.REALISTICALLY_EXECUTABLE_OPPORTUNITY:
        if complete != _REQUIREMENTS or gaps:
            reasons.append("realistic_execution_requires_complete_event_time_evidence")
    if request.realistically_capturable_exit_snapshot_id is not None:
        if opportunity_class != OpportunityEvidenceClass.REALISTICALLY_EXECUTABLE_OPPORTUNITY:
            reasons.append("capturable_exit_requires_realistically_executable_opportunity")
        if request.realistically_capturable_exit_snapshot_id not in request.supporting_snapshot_ids:
            reasons.append("capturable_exit_snapshot_not_exact_linked")
    if path == TradeablePathContext.WICK_ONLY_PEAK and (
        request.realistically_capturable_exit_snapshot_id is not None
    ):
        reasons.append("wick_only_peak_cannot_be_capturable_exit")
    if request.observed_peak_snapshot_id is not None:
        by_id = {item.snapshot_id: item for item in observations}
        if (
            request.observed_peak_snapshot_id not in by_id
            or not by_id[request.observed_peak_snapshot_id].observed_peak
        ):
            reasons.append("observed_peak_not_exact_linked")
    _append_reentry_reasons(request, path, cutoff, reasons)

    if reasons or None in {path, full_outcome, internal_outcome, opportunity_class}:
        return _blocked(reasons)
    segment = OpportunitySegment(
        segment_id=request.segment_id,
        identity=request.trajectory.identity,
        trajectory=request.trajectory,
        checkpoints=request.checkpoints,
        manipulation_context=request.manipulation_context,
        path_context=path,
        full_window_outcome=full_outcome,
        internal_trade_opportunity_outcome=internal_outcome,
        opportunity_class=opportunity_class,
        supporting_observations=observations,
        provenance=tuple(item.provenance for item in observations),
        evidence_references=references,
        evidence_gaps=gaps,
        evidence_cutoff=cutoff,
        observed_peak_snapshot_id=request.observed_peak_snapshot_id,
        realistically_capturable_exit_snapshot_id=(
            request.realistically_capturable_exit_snapshot_id
        ),
        reentry_link=request.reentry_link,
        participant_authenticity=(
            request.manipulation_context.participant_unknowns.participant_authenticity
        ),
    )
    return OpportunitySegmentResult(
        OpportunitySegmentVerdict.VALID, ("immutable_opportunity_segment_valid",), segment
    )


def build_opportunity_window(
    segments: tuple[OpportunitySegment, ...],
) -> OpportunityWindowResult:
    reasons: list[str] = []
    if not segments:
        reasons.append("opportunity_window_requires_segments")
        return _window_blocked(reasons)
    identity = segments[0].identity
    outcome = segments[0].full_window_outcome
    seen: set[str] = set()
    previous_cutoff: datetime | None = None
    for segment in segments:
        if segment.segment_id in seen:
            reasons.append("duplicate_segment_identity")
        seen.add(segment.segment_id)
        if segment.identity != identity:
            reasons.append("segment_window_identity_mismatch")
        if segment.full_window_outcome != outcome:
            reasons.append("segment_full_window_outcome_mismatch")
        if previous_cutoff is not None and segment.evidence_cutoff <= previous_cutoff:
            reasons.append("segments_not_strictly_ordered")
        previous_cutoff = segment.evidence_cutoff
    if reasons:
        return _window_blocked(reasons)
    return OpportunityWindowResult(
        OpportunitySegmentVerdict.VALID,
        ("ordered_opportunity_window_valid",),
        OpportunityWindow(identity, outcome, segments),
    )


def evaluate_later_segment_evidence(
    segment: OpportunitySegment,
    later_evidence: tuple[EventTimeEvidenceReference, ...],
) -> LaterSegmentEvidenceResult:
    reasons: list[str] = []
    prior_time = segment.evidence_cutoff
    for item in later_evidence:
        if item.identity != segment.identity:
            reasons.append("later_evidence_identity_mismatch")
        try:
            observed_at = _utc(item.observed_at)
            if observed_at <= prior_time:
                reasons.append("later_evidence_not_strictly_after_segment")
            prior_time = observed_at
        except ValueError:
            reasons.append("later_evidence_time_not_timezone_aware")
    if reasons:
        return LaterSegmentEvidenceResult(
            OpportunitySegmentVerdict.BLOCKED, tuple(dict.fromkeys(reasons)), None
        )
    return LaterSegmentEvidenceResult(
        OpportunitySegmentVerdict.VALID,
        ("later_evidence_evaluated_without_segment_mutation",),
        LaterSegmentEvidenceEvaluation(segment, later_evidence),
    )


def _append_linkage_reasons(
    request: OpportunitySegmentRequest, cutoff: datetime, reasons: list[str]
) -> None:
    trajectory = request.trajectory
    context = request.manipulation_context
    if context.identity != trajectory.identity or context.trajectory != trajectory:
        reasons.append("manipulation_context_trajectory_mismatch")
    unknown_values = vars(context.participant_unknowns).values()
    try:
        if any(UnknownState(value) not in frozenset(UnknownState) for value in unknown_values):
            reasons.append("unsupported_participant_unknown")
    except (TypeError, ValueError):
        reasons.append("unsupported_participant_unknown")
    if not request.checkpoints:
        reasons.append("segment_checkpoints_required")
    checkpoint_ids: set[str] = set()
    trajectory_ids = tuple(item.snapshot_id for item in trajectory.observations)
    for checkpoint in request.checkpoints:
        if checkpoint.checkpoint_id in checkpoint_ids:
            reasons.append("duplicate_checkpoint_identity")
        checkpoint_ids.add(checkpoint.checkpoint_id)
        if checkpoint.identity != trajectory.identity:
            reasons.append("checkpoint_identity_mismatch")
        if checkpoint.scheduler_work_id != trajectory.scheduler_work_id:
            reasons.append("checkpoint_scheduler_work_mismatch")
        if checkpoint.ordered_snapshot_ids != trajectory_ids:
            reasons.append("checkpoint_trajectory_mismatch")
        if checkpoint.evidence_cutoff > cutoff:
            reasons.append("checkpoint_after_segment_cutoff")
    if context.checkpoint.checkpoint_id not in checkpoint_ids:
        reasons.append("manipulation_checkpoint_not_exact_linked")
    if context.evidence_cutoff > cutoff:
        reasons.append("manipulation_context_after_segment_cutoff")


def _ordered_supporting_observations(
    request: OpportunitySegmentRequest, cutoff: datetime, reasons: list[str]
) -> tuple[TrajectoryObservation, ...]:
    ids = request.supporting_snapshot_ids
    if not ids or len(ids) != len(set(ids)):
        reasons.append("segment_requires_unique_supporting_observations")
    by_id = {item.snapshot_id: item for item in request.trajectory.observations}
    if any(snapshot_id not in by_id for snapshot_id in ids):
        reasons.append("segment_supporting_observation_missing")
        return ()
    observations = tuple(by_id[snapshot_id] for snapshot_id in ids)
    positions = {item.snapshot_id: index for index, item in enumerate(request.trajectory.observations)}
    if any(positions[later] <= positions[earlier] for earlier, later in zip(ids, ids[1:])):
        reasons.append("segment_observations_not_ordered")
    support_positions = tuple(positions[snapshot_id] for snapshot_id in ids)
    for gap in request.trajectory.gaps:
        if gap.before_snapshot_id in positions and gap.after_snapshot_id in positions:
            if min(support_positions, default=0) <= positions[gap.before_snapshot_id] and max(
                support_positions, default=0
            ) >= positions[gap.after_snapshot_id]:
                reasons.append("segment_claim_crosses_visible_evidence_gap")
    for observation in observations:
        if observation.identity != request.trajectory.identity:
            reasons.append("segment_observation_identity_mismatch")
        try:
            if _utc(observation.observed_at) > cutoff:
                reasons.append("post_cutoff_segment_observation")
        except ValueError:
            reasons.append("segment_observation_time_not_timezone_aware")
        if not observation.freshness_within_contract:
            reasons.append("stale_segment_observation")
    return observations


def _validate_references(
    request: OpportunitySegmentRequest, cutoff: datetime, reasons: list[str]
) -> tuple[tuple[EventTimeEvidenceReference, ...], frozenset[EventTimeEvidenceRequirement]]:
    normalized: list[EventTimeEvidenceReference] = []
    complete: set[EventTimeEvidenceRequirement] = set()
    seen_ids: set[str] = set()
    checkpoint_ids = {item.checkpoint_id for item in request.checkpoints}
    for item in request.evidence_references:
        requirement = _enum_or_reason(
            EventTimeEvidenceRequirement,
            item.requirement,
            "unsupported_event_time_evidence_requirement",
            reasons,
        )
        if not _valid_text(item.evidence_id) or item.evidence_id in seen_ids:
            reasons.append("duplicate_or_invalid_event_time_evidence_identity")
        seen_ids.add(item.evidence_id)
        if item.identity != request.trajectory.identity:
            reasons.append("event_time_evidence_identity_mismatch")
        if item.checkpoint_id not in checkpoint_ids:
            reasons.append("event_time_evidence_checkpoint_mismatch")
        try:
            if _utc(item.observed_at) > cutoff:
                reasons.append("post_cutoff_event_time_evidence")
        except ValueError:
            reasons.append("event_time_evidence_time_not_timezone_aware")
        _append_provenance_reasons(item.provenance, request.trajectory.scheduler_work_id, reasons)
        if item.provenance.source_name not in _CONTEXT_PROVIDERS:
            reasons.append("unsupported_event_time_evidence_provider")
        if not item.freshness_within_contract:
            reasons.append("stale_event_time_evidence")
        if item.quantitative_contract_complete:
            if item.provenance.source_name not in _EXECUTION_PROVIDERS:
                reasons.append("context_provider_cannot_prove_execution")
            elif requirement is not None:
                if frozenset(item.contract_fields) != _CONTRACT_FIELDS[requirement]:
                    reasons.append("incomplete_event_time_contract_fields")
                    continue
                if requirement in complete:
                    reasons.append("duplicate_complete_event_time_requirement")
                complete.add(requirement)
        if requirement is not None:
            normalized.append(
                EventTimeEvidenceReference(
                    item.evidence_id,
                    requirement,
                    item.identity,
                    item.checkpoint_id,
                    item.observed_at,
                    item.provenance,
                    item.freshness_within_contract,
                    item.quantitative_contract_complete,
                    item.contract_fields,
                )
            )
    return tuple(normalized), frozenset(complete)


def _validate_gaps(
    request: OpportunitySegmentRequest, reasons: list[str]
) -> tuple[EventTimeEvidenceGap, ...]:
    normalized: list[EventTimeEvidenceGap] = []
    seen_ids: set[str] = set()
    seen_requirements: set[EventTimeEvidenceRequirement] = set()
    checkpoint_ids = {item.checkpoint_id for item in request.checkpoints}
    for gap in request.evidence_gaps:
        requirement = _enum_or_reason(
            EventTimeEvidenceRequirement,
            gap.requirement,
            "unsupported_event_time_gap_requirement",
            reasons,
        )
        state = _enum_or_reason(
            UnknownState, gap.state, "unsupported_event_time_gap_unknown_state", reasons
        )
        if state not in {
            UnknownState.CURRENT_EVIDENCE_GAP,
            UnknownState.UNKNOWN_REQUIRES_RESEARCH,
        }:
            reasons.append("event_time_gap_must_preserve_explicit_unknown")
        if not _valid_text(gap.gap_id) or gap.gap_id in seen_ids:
            reasons.append("duplicate_or_invalid_event_time_gap_identity")
        seen_ids.add(gap.gap_id)
        if requirement in seen_requirements:
            reasons.append("duplicate_event_time_gap_requirement")
        if requirement is not None:
            seen_requirements.add(requirement)
        if gap.checkpoint_id not in checkpoint_ids:
            reasons.append("event_time_gap_checkpoint_mismatch")
        if not gap.visible:
            reasons.append("event_time_gap_must_remain_visible")
        if not _valid_text(gap.reason):
            reasons.append("event_time_gap_reason_required")
        if requirement is not None and state is not None:
            normalized.append(
                EventTimeEvidenceGap(
                    gap.gap_id, requirement, state, gap.checkpoint_id, gap.reason, gap.visible
                )
            )
    return tuple(normalized)


def _append_reentry_reasons(
    request: OpportunitySegmentRequest,
    path: TradeablePathContext | None,
    cutoff: datetime,
    reasons: list[str],
) -> None:
    needs_reentry = path == TradeablePathContext.REENTRY_CHURN or any(
        EvaluationPath.FRESH_REENTRY_REVIEW in checkpoint.eligible_paths
        for checkpoint in request.checkpoints
    )
    if not needs_reentry and request.reentry_link is not None:
        reasons.append("unexpected_reentry_link")
        return
    if not needs_reentry:
        return
    link = request.reentry_link
    if link is None:
        reasons.append("reentry_requires_fresh_checkpoint")
        return
    ids = {item.checkpoint_id for item in request.checkpoints}
    if (
        link.fresh_checkpoint_id not in ids
        or link.fresh_checkpoint_id == link.prior_terminal_checkpoint_id
    ):
        reasons.append("reentry_requires_distinct_fresh_checkpoint")
    try:
        prior_cutoff = _utc(link.prior_segment_cutoff)
        fresh = next(
            (item for item in request.checkpoints if item.checkpoint_id == link.fresh_checkpoint_id),
            None,
        )
        if fresh is None or fresh.evidence_cutoff <= prior_cutoff or cutoff <= prior_cutoff:
            reasons.append("reentry_evidence_not_fresh")
    except ValueError:
        reasons.append("reentry_cutoff_not_timezone_aware")
    if not _valid_text(link.prior_segment_id) or not _valid_text(
        link.prior_terminal_checkpoint_id
    ):
        reasons.append("invalid_reentry_link_identity")


def _append_provenance_reasons(
    provenance: GovernedSourceProvenance, scheduler_work_id: str, reasons: list[str]
) -> None:
    if provenance.source_name not in SOURCE_REGISTRY:
        reasons.append("unregistered_source_provenance")
    if provenance.source_request_id <= 0 or provenance.source_response_id <= 0:
        reasons.append("source_provenance_identity_missing")
    if provenance.scheduler_work_id != scheduler_work_id:
        reasons.append("source_provenance_scheduler_work_mismatch")
    if not provenance.governor_approved or not provenance.traceable:
        reasons.append("ungoverned_or_untraceable_source_provenance")
    try:
        if SourceStatus(provenance.source_status) != SourceStatus.COMPLETE:
            reasons.append("incomplete_source_provenance")
    except (TypeError, ValueError):
        reasons.append("unsupported_source_status")
    try:
        if DataQualityLabel(provenance.data_quality_label) != DataQualityLabel.CLEAN_DATA:
            reasons.append("unclean_event_time_evidence")
    except (TypeError, ValueError):
        reasons.append("unsupported_data_quality_label")


def _enum_or_reason(enum_type, value, reason: str, reasons: list[str]):
    try:
        return enum_type(value)
    except (TypeError, ValueError):
        reasons.append(reason)
        return None


def _blocked(reasons: Iterable[str]) -> OpportunitySegmentResult:
    return OpportunitySegmentResult(
        OpportunitySegmentVerdict.BLOCKED, tuple(dict.fromkeys(reasons)), None
    )


def _window_blocked(reasons: Iterable[str]) -> OpportunityWindowResult:
    return OpportunityWindowResult(
        OpportunitySegmentVerdict.BLOCKED, tuple(dict.fromkeys(reasons)), None
    )


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")
    return value.astimezone(timezone.utc)


def _valid_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())

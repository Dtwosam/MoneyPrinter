"""Pure conditional support-only 5m capture policy for V2-9.7D.4B.

The evaluator consumes already-governed observations. It performs no source
request, scheduler action, persistence, main-window mutation, or retry.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Iterable

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.lifecycle.contracts import TokenLifecycleState
from printer_v1.memory.contracts import MemoryWindowKind, MemoryWindowStatus
from printer_v1.operator_cli.campaign_identity_state import (
    CampaignIdentityError,
    require_identity,
    validate_identity,
)
from printer_v1.operator_cli.e2v_5m_micro_event_evidence import E2V_WINDOW_KIND
from printer_v1.sources.registry import SOURCE_REGISTRY


class SupportCaptureVerdict(StrEnum):
    CAPTURE_SUPPORT = "CAPTURE_SUPPORT"
    VALID_NO_CAPTURE = "VALID_NO_CAPTURE"
    BLOCK_SUPPORT_CAPTURE = "BLOCK_SUPPORT_CAPTURE"


class SupportTriggerFamily(StrEnum):
    FAST_COORDINATED_PUMP = "FAST_COORDINATED_PUMP"
    FAST_DUMP_OR_COLLAPSE = "FAST_DUMP_OR_COLLAPSE"
    WICK_OR_LATE_BUY_TRAP = "WICK_OR_LATE_BUY_TRAP"
    EXIT_REALISM_CHANGE = "EXIT_REALISM_CHANGE"
    LIQUIDITY_SHOCK = "LIQUIDITY_SHOCK"
    FAST_BREAKDOWN_OR_RECLAIM = "FAST_BREAKDOWN_OR_RECLAIM"


_ACTIVE_MAIN_WINDOW_KINDS = frozenset(
    {
        MemoryWindowKind.WINDOW_15M.value,
        MemoryWindowKind.WINDOW_1H.value,
        MemoryWindowKind.WINDOW_4H.value,
    }
)
_ELIGIBLE_TOKEN_STATES = frozenset(
    {
        TokenLifecycleState.TRACK_FAST.value,
        TokenLifecycleState.TRACK_NORMAL.value,
    }
)


@dataclass(frozen=True)
class ExpectedSupportCaptureIdentity:
    campaign_id: str
    run_id: str
    cycle_id: str
    token_slot_id: str
    token_id: str
    mint_id: str
    pair_id: str
    root_15m_lifecycle_id: str
    containing_main_window_id: str
    scheduler_work_id: str


@dataclass(frozen=True)
class GovernedSourceProvenance:
    source_name: str
    source_request_id: int
    source_response_id: int
    scheduler_work_id: str
    source_status: SourceStatus | str
    data_quality_label: DataQualityLabel | str
    governor_approved: bool
    traceable: bool


@dataclass(frozen=True)
class TriggeringSnapshot:
    snapshot_id: int
    campaign_id: str
    run_id: str
    cycle_id: str
    token_slot_id: str
    token_id: str
    mint_id: str
    pair_id: str
    root_15m_lifecycle_id: str
    containing_main_window_id: str
    observed_at: datetime
    freshness_within_contract: bool
    provenance: GovernedSourceProvenance


@dataclass(frozen=True)
class SupportCaptureBudgets:
    token_available: bool = True
    source_available: bool = True
    scheduler_available: bool = True
    storage_available: bool = True
    campaign_available: bool = True


@dataclass(frozen=True)
class SupportCaptureRequest:
    campaign_id: str
    run_id: str
    cycle_id: str
    token_slot_id: str
    token_id: str
    mint_id: str
    pair_id: str
    root_15m_lifecycle_id: str
    containing_main_window_id: str
    containing_main_window_kind: MemoryWindowKind | str
    containing_main_window_status: MemoryWindowStatus | str
    scheduler_work_id: str
    expected_identity: ExpectedSupportCaptureIdentity
    trigger_family: SupportTriggerFamily | str | None
    trigger_time: datetime
    evidence_cutoff: datetime
    triggering_snapshots: tuple[TriggeringSnapshot, ...]
    budgets: SupportCaptureBudgets
    token_state: TokenLifecycleState | str
    meaningful_transition_proven: bool
    ordinary_movement: bool = False
    future_main_window_outcome_used: bool = False
    token_eligible: bool = True
    containing_lifecycle_eligible: bool = True
    cancelled: bool = False
    terminal: bool = False


@dataclass(frozen=True)
class SupportOnly5mCapture:
    window_kind: str
    trigger_family: SupportTriggerFamily
    campaign_id: str
    run_id: str
    cycle_id: str
    token_slot_id: str
    token_id: str
    mint_id: str
    pair_id: str
    root_15m_lifecycle_id: str
    containing_main_window_id: str
    containing_main_window_kind: str
    triggering_snapshots: tuple[TriggeringSnapshot, ...]
    scheduler_work_id: str
    trigger_time: datetime
    evidence_cutoff: datetime
    support_only: bool = True
    main_outcome_memory: bool = False
    replaces_window_15m: bool = False
    continuation_authority: bool = False
    counts_toward_main_clean_memory: bool = False
    lifecycle_disposition_authority: bool = False
    retrieval_authority: bool = False
    decision_authority: bool = False
    financial_authority: bool = False


@dataclass(frozen=True)
class SupportCaptureResult:
    verdict: SupportCaptureVerdict
    reasons: tuple[str, ...]
    capture: SupportOnly5mCapture | None
    support_request_only: bool = True
    containing_main_window_unchanged: bool = True
    hidden_retry_allowed: bool = False


def evaluate_support_only_5m_capture(
    request: SupportCaptureRequest,
) -> SupportCaptureResult:
    """Return a deterministic support-only verdict for one token request."""
    blocked: list[str] = []
    _append_identity_reasons(request, blocked)
    _append_state_and_budget_reasons(request, blocked)
    _append_cutoff_and_snapshot_reasons(request, blocked)

    if request.future_main_window_outcome_used:
        blocked.append("future_main_window_outcome_used_retrospectively")

    if blocked:
        return _result(SupportCaptureVerdict.BLOCK_SUPPORT_CAPTURE, blocked)

    if request.trigger_family is None:
        if request.ordinary_movement or not request.meaningful_transition_proven:
            return _result(
                SupportCaptureVerdict.VALID_NO_CAPTURE,
                ("no_approved_meaningful_transition",),
            )
        return _result(
            SupportCaptureVerdict.BLOCK_SUPPORT_CAPTURE,
            ("meaningful_transition_missing_trigger_family",),
        )

    try:
        trigger_family = SupportTriggerFamily(request.trigger_family)
    except ValueError:
        return _result(
            SupportCaptureVerdict.BLOCK_SUPPORT_CAPTURE,
            ("unsupported_trigger_family",),
        )

    if request.ordinary_movement or not request.meaningful_transition_proven:
        return _result(
            SupportCaptureVerdict.VALID_NO_CAPTURE,
            ("approved_trigger_not_proven_by_governed_observations",),
        )

    capture = SupportOnly5mCapture(
        window_kind=E2V_WINDOW_KIND,
        trigger_family=trigger_family,
        campaign_id=request.campaign_id,
        run_id=request.run_id,
        cycle_id=request.cycle_id,
        token_slot_id=request.token_slot_id,
        token_id=request.token_id,
        mint_id=request.mint_id,
        pair_id=request.pair_id,
        root_15m_lifecycle_id=request.root_15m_lifecycle_id,
        containing_main_window_id=request.containing_main_window_id,
        containing_main_window_kind=str(request.containing_main_window_kind),
        triggering_snapshots=request.triggering_snapshots,
        scheduler_work_id=request.scheduler_work_id,
        trigger_time=_utc(request.trigger_time),
        evidence_cutoff=_utc(request.evidence_cutoff),
    )
    return SupportCaptureResult(
        verdict=SupportCaptureVerdict.CAPTURE_SUPPORT,
        reasons=("approved_trigger_proven_by_exact_governed_evidence",),
        capture=capture,
    )


def _append_identity_reasons(
    request: SupportCaptureRequest,
    reasons: list[str],
) -> None:
    expected = request.expected_identity
    comparisons = (
        ("campaign", request.campaign_id, expected.campaign_id),
        ("run", request.run_id, expected.run_id),
        ("cycle", request.cycle_id, expected.cycle_id),
        ("token_slot", request.token_slot_id, expected.token_slot_id),
        ("token", request.token_id, expected.token_id),
        ("mint", request.mint_id, expected.mint_id),
        ("pair", request.pair_id, expected.pair_id),
        (
            "lifecycle",
            request.root_15m_lifecycle_id,
            expected.root_15m_lifecycle_id,
        ),
        (
            "window",
            request.containing_main_window_id,
            expected.containing_main_window_id,
        ),
        ("scheduler_work", request.scheduler_work_id, expected.scheduler_work_id),
    )
    for kind, actual, required in comparisons:
        try:
            if kind == "run":
                _require_run_identity(actual, required)
            else:
                require_identity(kind, actual, required)
        except CampaignIdentityError:
            reasons.append(f"{kind}_identity_mismatch")


def _require_run_identity(actual: object, expected: object) -> None:
    """Use the 3A identity shape for the design's run identity."""
    try:
        validated_actual = validate_identity("campaign", actual)
        validated_expected = validate_identity("campaign", expected)
    except CampaignIdentityError as exc:
        raise CampaignIdentityError("run identity has invalid shape") from exc
    if validated_actual != validated_expected:
        raise CampaignIdentityError("run identity mismatch")


def _append_state_and_budget_reasons(
    request: SupportCaptureRequest,
    reasons: list[str],
) -> None:
    if str(request.containing_main_window_kind) not in _ACTIVE_MAIN_WINDOW_KINDS:
        reasons.append("unsupported_containing_main_window_kind")
    if str(request.containing_main_window_status) != MemoryWindowStatus.WINDOW_OPEN.value:
        reasons.append("containing_main_window_not_active")
    if request.cancelled:
        reasons.append("support_request_cancelled")
    if request.terminal:
        reasons.append("containing_lifecycle_terminal")
    if (
        not request.token_eligible
        or not request.containing_lifecycle_eligible
        or str(request.token_state) not in _ELIGIBLE_TOKEN_STATES
    ):
        reasons.append("token_or_containing_lifecycle_ineligible")

    budget_fields = (
        ("token", request.budgets.token_available),
        ("source", request.budgets.source_available),
        ("scheduler", request.budgets.scheduler_available),
        ("storage", request.budgets.storage_available),
        ("campaign", request.budgets.campaign_available),
    )
    for scope, available in budget_fields:
        if not available:
            reasons.append(f"{scope}_budget_exhausted")


def _append_cutoff_and_snapshot_reasons(
    request: SupportCaptureRequest,
    reasons: list[str],
) -> None:
    try:
        trigger_time = _utc(request.trigger_time)
        cutoff = _utc(request.evidence_cutoff)
    except ValueError:
        reasons.append("trigger_time_or_evidence_cutoff_not_timezone_aware")
        return
    if cutoff != trigger_time:
        reasons.append("evidence_cutoff_must_equal_trigger_time")

    snapshots = request.triggering_snapshots
    if len(snapshots) < 2:
        reasons.append("at_least_two_triggering_snapshots_required")
        return
    if len({snapshot.snapshot_id for snapshot in snapshots}) != len(snapshots):
        reasons.append("duplicate_triggering_snapshot_identity")

    observed_times: list[datetime] = []
    for snapshot in snapshots:
        if not isinstance(snapshot.snapshot_id, int) or snapshot.snapshot_id <= 0:
            reasons.append("invalid_triggering_snapshot_identity")
        _append_snapshot_identity_reasons(request, snapshot, reasons)
        try:
            observed_at = _utc(snapshot.observed_at)
        except ValueError:
            reasons.append("snapshot_time_not_timezone_aware")
            continue
        observed_times.append(observed_at)
        if observed_at > cutoff:
            reasons.append("snapshot_observed_after_evidence_cutoff")
        if not snapshot.freshness_within_contract:
            reasons.append("stale_triggering_snapshot")
        _append_provenance_reasons(request, snapshot.provenance, reasons)

    if observed_times:
        if observed_times != sorted(observed_times):
            reasons.append("triggering_snapshots_not_time_ordered")
        if max(observed_times) != trigger_time:
            reasons.append("trigger_boundary_not_exact_latest_snapshot")


def _append_snapshot_identity_reasons(
    request: SupportCaptureRequest,
    snapshot: TriggeringSnapshot,
    reasons: list[str],
) -> None:
    fields = (
        ("campaign", snapshot.campaign_id, request.campaign_id),
        ("run", snapshot.run_id, request.run_id),
        ("cycle", snapshot.cycle_id, request.cycle_id),
        ("token_slot", snapshot.token_slot_id, request.token_slot_id),
        ("token", snapshot.token_id, request.token_id),
        ("mint", snapshot.mint_id, request.mint_id),
        ("pair", snapshot.pair_id, request.pair_id),
        (
            "root_15m_lifecycle",
            snapshot.root_15m_lifecycle_id,
            request.root_15m_lifecycle_id,
        ),
        (
            "containing_main_window",
            snapshot.containing_main_window_id,
            request.containing_main_window_id,
        ),
    )
    for field, actual, expected in fields:
        if actual != expected:
            reasons.append(f"snapshot_{field}_identity_mismatch")


def _append_provenance_reasons(
    request: SupportCaptureRequest,
    provenance: GovernedSourceProvenance,
    reasons: list[str],
) -> None:
    if provenance.source_name not in SOURCE_REGISTRY:
        reasons.append("unregistered_source_provenance")
    if provenance.source_request_id <= 0 or provenance.source_response_id <= 0:
        reasons.append("source_provenance_identity_missing")
    try:
        require_identity(
            "scheduler_work",
            provenance.scheduler_work_id,
            request.scheduler_work_id,
        )
    except CampaignIdentityError:
        reasons.append("source_provenance_scheduler_work_mismatch")
    if not provenance.governor_approved or not provenance.traceable:
        reasons.append("source_provenance_untraceable_or_ungoverned")
    if str(provenance.source_status) != SourceStatus.COMPLETE.value:
        reasons.append("source_provenance_not_complete")
    if str(provenance.data_quality_label) != DataQualityLabel.CLEAN_DATA.value:
        reasons.append("source_provenance_not_clean")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _result(
    verdict: SupportCaptureVerdict,
    reasons: Iterable[str],
) -> SupportCaptureResult:
    return SupportCaptureResult(
        verdict=verdict,
        reasons=tuple(dict.fromkeys(reasons)),
        capture=None,
    )

"""Pure token-local continuation policy for V2-9.7D.4A / V2-9.8B.

The policy evaluates exactly two already-materialised campaign token records.
It does not fetch, schedule, persist, mutate, or create a successor window.

Post-DTW100 policy amendment: WINDOW_15M -> WINDOW_1H is the standard bounded
first-hour lifecycle for every otherwise-valid activated token. Outcome or
learning-need labels do not qualify that transition. WINDOW_1H -> WINDOW_4H
remains selective and learning-need-gated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from printer_v1.contracts.enums import DataQualityLabel
from printer_v1.lifecycle.contracts import TokenLifecycleState
from printer_v1.memory.contracts import (
    MemoryQualityLabel,
    MemoryWindowKind,
    MemoryWindowStatus,
)
from printer_v1.operator_cli.campaign_identity_state import (
    CampaignIdentityError,
    require_identity,
    validate_identity,
)
from printer_v1.safety.composite import SAFETY_CONTEXT_ACCEPTABLE
from printer_v1.scheduler.two_token_fairness import TWO_TOKEN_ACTIVE_SLOT_COUNT
from printer_v1.snapshots.lifecycle_continuity import CONTINUITY_CONTINUOUS


class ContinuationVerdict(StrEnum):
    CONTINUE_TO_WINDOW_1H = "CONTINUE_TO_WINDOW_1H"
    STOP_AFTER_WINDOW_15M = "STOP_AFTER_WINDOW_15M"
    CONTINUE_TO_WINDOW_4H = "CONTINUE_TO_WINDOW_4H"
    STOP_AFTER_WINDOW_1H = "STOP_AFTER_WINDOW_1H"
    BLOCK_CONTINUATION = "BLOCK_CONTINUATION"


class ContinuationLearningNeed(StrEnum):
    COVERAGE = "COVERAGE"
    TRANSITION = "TRANSITION"
    SURVIVAL = "SURVIVAL"
    COLLAPSE = "COLLAPSE"
    REVIVAL = "REVIVAL"
    DISTRIBUTION = "DISTRIBUTION"
    LIQUIDITY_DETERIORATION = "LIQUIDITY_DETERIORATION"


_FIRST_HOUR_TRANSITION = (
    MemoryWindowKind.WINDOW_15M,
    MemoryWindowKind.WINDOW_1H,
)

_ALLOWED_TRANSITIONS = {
    _FIRST_HOUR_TRANSITION: (
        ContinuationVerdict.CONTINUE_TO_WINDOW_1H,
        ContinuationVerdict.STOP_AFTER_WINDOW_15M,
        frozenset(
            {
                ContinuationLearningNeed.COVERAGE,
                ContinuationLearningNeed.TRANSITION,
            }
        ),
    ),
    (
        MemoryWindowKind.WINDOW_1H,
        MemoryWindowKind.WINDOW_4H,
    ): (
        ContinuationVerdict.CONTINUE_TO_WINDOW_4H,
        ContinuationVerdict.STOP_AFTER_WINDOW_1H,
        frozenset(
            {
                ContinuationLearningNeed.TRANSITION,
                ContinuationLearningNeed.SURVIVAL,
                ContinuationLearningNeed.COLLAPSE,
                ContinuationLearningNeed.REVIVAL,
                ContinuationLearningNeed.DISTRIBUTION,
                ContinuationLearningNeed.LIQUIDITY_DETERIORATION,
            }
        ),
    ),
}

_ELIGIBLE_TOKEN_STATES = frozenset(
    {
        TokenLifecycleState.TRACK_FAST.value,
        TokenLifecycleState.TRACK_NORMAL.value,
    }
)


@dataclass(frozen=True)
class CampaignContinuationContext:
    campaign_id: str
    configuration_id: str
    campaign_state: str = "RUNNING"
    campaign_eligible: bool = True
    shared_db_healthy: bool = True
    shared_lease_healthy: bool = True
    shared_integrity_healthy: bool = True
    campaign_budget_available: bool = True


@dataclass(frozen=True)
class ExpectedTokenContinuationIdentity:
    token_slot_id: str
    token_id: str
    mint_id: str
    pair_id: str
    lifecycle_id: str
    predecessor_window_id: str


@dataclass(frozen=True)
class TokenContinuationInput:
    campaign_id: str
    configuration_id: str
    token_slot_id: str
    token_id: str
    mint_id: str
    pair_id: str
    lifecycle_id: str
    predecessor_window_id: str
    expected_identity: ExpectedTokenContinuationIdentity
    predecessor_window_kind: MemoryWindowKind | str
    successor_window_kind: MemoryWindowKind | str
    predecessor_window_status: MemoryWindowStatus | str
    predecessor_memory_quality: MemoryQualityLabel | str
    predecessor_data_quality: DataQualityLabel | str
    predecessor_do_not_train: bool
    predecessor_evidence_eligible: bool
    predecessor_complete: bool
    freshness_within_contract: bool
    governed_provenance_traceable: bool
    safety_context_present: bool
    safety_context_result: str
    continuity_status: str
    learning_need: ContinuationLearningNeed | str | None
    token_budget_available: bool
    token_state: TokenLifecycleState | str
    token_eligible: bool = True
    cancelled: bool = False
    terminal: bool = False


@dataclass(frozen=True)
class TokenContinuationResult:
    token_slot_id: str
    token_id: str
    verdict: ContinuationVerdict
    reasons: tuple[str, ...]


def evaluate_token_local_continuations(
    *,
    campaign: CampaignContinuationContext,
    tokens: Iterable[TokenContinuationInput],
) -> tuple[TokenContinuationResult, TokenContinuationResult]:
    """Evaluate exactly two tokens independently, with shared failures shared."""
    token_inputs = tuple(tokens)
    if len(token_inputs) != TWO_TOKEN_ACTIVE_SLOT_COUNT:
        raise ValueError("continuation policy requires exactly two token slots")

    shared_reasons = _shared_block_reasons(campaign, token_inputs)
    if shared_reasons:
        return tuple(  # type: ignore[return-value]
            _result(token, ContinuationVerdict.BLOCK_CONTINUATION, shared_reasons)
            for token in token_inputs
        )

    return tuple(  # type: ignore[return-value]
        _evaluate_token(campaign, token) for token in token_inputs
    )


def _shared_block_reasons(
    campaign: CampaignContinuationContext,
    tokens: tuple[TokenContinuationInput, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    try:
        validate_identity("campaign", campaign.campaign_id)
        validate_identity("configuration", campaign.configuration_id)
    except CampaignIdentityError:
        reasons.append("invalid_campaign_or_configuration_identity")

    if campaign.campaign_state != "RUNNING" or not campaign.campaign_eligible:
        reasons.append("campaign_not_running_and_eligible")
    if not campaign.shared_db_healthy:
        reasons.append("shared_db_failure")
    if not campaign.shared_lease_healthy:
        reasons.append("shared_lease_failure")
    if not campaign.shared_integrity_healthy:
        reasons.append("shared_integrity_failure")
    if not campaign.campaign_budget_available:
        reasons.append("campaign_budget_exhausted")

    slot_ids = [token.token_slot_id for token in tokens]
    token_ids = [token.token_id for token in tokens]
    if len(set(slot_ids)) != TWO_TOKEN_ACTIVE_SLOT_COUNT:
        reasons.append("duplicate_token_slot_identity")
    if len(set(token_ids)) != TWO_TOKEN_ACTIVE_SLOT_COUNT:
        reasons.append("duplicate_token_identity")
    return tuple(reasons)


def _evaluate_token(
    campaign: CampaignContinuationContext,
    token: TokenContinuationInput,
) -> TokenContinuationResult:
    blocked: list[str] = []
    _append_identity_reasons(campaign, token, blocked)

    try:
        predecessor_kind = MemoryWindowKind(token.predecessor_window_kind)
        successor_kind = MemoryWindowKind(token.successor_window_kind)
    except ValueError:
        return _result(
            token,
            ContinuationVerdict.BLOCK_CONTINUATION,
            (*blocked, "unsupported_window_transition"),
        )

    transition_key = (predecessor_kind, successor_kind)
    transition = _ALLOWED_TRANSITIONS.get(transition_key)
    if transition is None:
        blocked.append("unsupported_window_transition")

    if token.cancelled:
        blocked.append("token_cancelled")
    if token.terminal:
        blocked.append("token_terminal")
    if not token.token_eligible or str(token.token_state) not in _ELIGIBLE_TOKEN_STATES:
        blocked.append("token_state_not_eligible")
    if str(token.predecessor_window_status) != MemoryWindowStatus.WINDOW_CLOSED.value:
        blocked.append("predecessor_window_not_closed")
    if str(token.predecessor_memory_quality) != MemoryQualityLabel.CLEAN_MEMORY.value:
        blocked.append("predecessor_memory_not_clean")
    if str(token.predecessor_data_quality) != DataQualityLabel.CLEAN_DATA.value:
        blocked.append("predecessor_data_not_clean")
    if token.predecessor_do_not_train:
        blocked.append("predecessor_marked_do_not_train")
    if not token.predecessor_evidence_eligible:
        blocked.append("predecessor_evidence_not_eligible")
    if not token.predecessor_complete:
        blocked.append("predecessor_evidence_incomplete")
    if not token.freshness_within_contract:
        blocked.append("predecessor_evidence_stale")
    if not token.governed_provenance_traceable:
        blocked.append("governed_provenance_untraceable")
    if not token.safety_context_present:
        blocked.append("mandatory_safety_context_missing")
    elif token.safety_context_result != SAFETY_CONTEXT_ACCEPTABLE:
        blocked.append("mandatory_safety_context_not_acceptable")
    if token.continuity_status != CONTINUITY_CONTINUOUS:
        blocked.append("predecessor_continuity_not_eligible")

    if blocked:
        return _result(token, ContinuationVerdict.BLOCK_CONTINUATION, blocked)

    assert transition is not None
    continue_verdict, stop_verdict, allowed_needs = transition

    # Post-DTW100 first-hour lifecycle amendment: once a token has passed every
    # hard operational/evidence/identity/safety/continuity gate above, the only
    # remaining first-hour resource gate is the bounded token budget. A 15m
    # outcome or learning-need label has no authority to stop observation.
    if transition_key == _FIRST_HOUR_TRANSITION:
        if not token.token_budget_available:
            return _result(
                token,
                ContinuationVerdict.BLOCK_CONTINUATION,
                ("token_budget_exhausted",),
            )
        return _result(
            token,
            ContinuationVerdict.CONTINUE_TO_WINDOW_1H,
            ("standard_first_hour_lifecycle",),
        )

    # Later windows remain selective. Preserve the established 1h -> 4h
    # decision order exactly: no learning need is a normal stop; an applicable
    # need then still requires available token budget.
    if token.learning_need is None:
        return _result(token, stop_verdict, ("no_unresolved_learning_need",))
    try:
        learning_need = ContinuationLearningNeed(token.learning_need)
    except ValueError:
        return _result(
            token,
            ContinuationVerdict.BLOCK_CONTINUATION,
            ("unsupported_learning_need",),
        )
    if learning_need not in allowed_needs:
        return _result(
            token,
            ContinuationVerdict.BLOCK_CONTINUATION,
            ("learning_need_not_applicable_to_transition",),
        )
    if not token.token_budget_available:
        return _result(
            token,
            ContinuationVerdict.BLOCK_CONTINUATION,
            ("token_budget_exhausted",),
        )
    return _result(token, continue_verdict, ("all_continuation_requirements_met",))


def _append_identity_reasons(
    campaign: CampaignContinuationContext,
    token: TokenContinuationInput,
    reasons: list[str],
) -> None:
    expected = token.expected_identity
    comparisons = (
        ("campaign", token.campaign_id, campaign.campaign_id),
        ("configuration", token.configuration_id, campaign.configuration_id),
        ("token_slot", token.token_slot_id, expected.token_slot_id),
        ("token", token.token_id, expected.token_id),
        ("mint", token.mint_id, expected.mint_id),
        ("pair", token.pair_id, expected.pair_id),
        ("lifecycle", token.lifecycle_id, expected.lifecycle_id),
        ("window", token.predecessor_window_id, expected.predecessor_window_id),
    )
    for kind, actual, required in comparisons:
        try:
            require_identity(kind, actual, required)
        except CampaignIdentityError:
            reasons.append(f"{kind}_identity_mismatch")


def _result(
    token: TokenContinuationInput,
    verdict: ContinuationVerdict,
    reasons: Iterable[str],
) -> TokenContinuationResult:
    return TokenContinuationResult(
        token_slot_id=token.token_slot_id,
        token_id=token.token_id,
        verdict=verdict,
        reasons=tuple(reasons),
    )

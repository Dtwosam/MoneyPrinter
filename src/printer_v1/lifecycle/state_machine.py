"""Deterministic token lifecycle transitions for Printer V1."""

from dataclasses import dataclass

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.contracts.rules import PRINTER_CHAIN
from printer_v1.lifecycle.contracts import LifecycleEvent, TokenLifecycleState


ALLOWED_TRANSITIONS = {
    TokenLifecycleState.DISCOVERED: frozenset(
        {
            TokenLifecycleState.WATCH_ONLY,
            TokenLifecycleState.TRACK_NORMAL,
            TokenLifecycleState.TRACK_FAST,
            TokenLifecycleState.INSTANT_REJECT_MEMORY_ONLY,
        }
    ),
    TokenLifecycleState.WATCH_ONLY: frozenset(
        {
            TokenLifecycleState.WATCH_ONLY,
            TokenLifecycleState.TRACK_NORMAL,
            TokenLifecycleState.TRACK_FAST,
            TokenLifecycleState.ARCHIVED,
        }
    ),
    TokenLifecycleState.TRACK_NORMAL: frozenset(
        {
            TokenLifecycleState.TRACK_FAST,
            TokenLifecycleState.WATCH_ONLY,
            TokenLifecycleState.COOLDOWN,
            TokenLifecycleState.ARCHIVED,
        }
    ),
    TokenLifecycleState.TRACK_FAST: frozenset(
        {
            TokenLifecycleState.TRACK_NORMAL,
            TokenLifecycleState.PAPER_MONITORING,
            TokenLifecycleState.COOLDOWN,
            TokenLifecycleState.ARCHIVED,
        }
    ),
    TokenLifecycleState.PAPER_MONITORING: frozenset(
        {
            TokenLifecycleState.PAPER_MONITORING,
            TokenLifecycleState.COOLDOWN,
            TokenLifecycleState.ARCHIVED,
        }
    ),
    TokenLifecycleState.COOLDOWN: frozenset(
        {
            TokenLifecycleState.WATCH_ONLY,
            TokenLifecycleState.TRACK_NORMAL,
            TokenLifecycleState.TRACK_FAST,
            TokenLifecycleState.ARCHIVED,
        }
    ),
    TokenLifecycleState.ARCHIVED: frozenset(
        {
            TokenLifecycleState.WATCH_ONLY,
            TokenLifecycleState.TRACK_NORMAL,
            TokenLifecycleState.TRACK_FAST,
        }
    ),
    TokenLifecycleState.INSTANT_REJECT_MEMORY_ONLY: frozenset(
        {
            TokenLifecycleState.WATCH_ONLY,
            TokenLifecycleState.TRACK_NORMAL,
        }
    ),
}

REOPEN_EVENTS = frozenset(
    {
        LifecycleEvent.REOPEN_REVIVED_TOKEN,
        LifecycleEvent.MANUAL_REVIEW,
    }
)

MANUAL_REVIEW_EVENTS = frozenset({LifecycleEvent.MANUAL_REVIEW})

BAD_DATA_LABELS = frozenset(
    {
        DataQualityLabel.DIRTY_DATA,
        DataQualityLabel.MISSING_CRITICAL_DATA,
        DataQualityLabel.DO_NOT_TRAIN,
    }
)


@dataclass(frozen=True)
class LifecycleTransition:
    previous_state: TokenLifecycleState
    new_state: TokenLifecycleState
    lifecycle_event: LifecycleEvent
    allowed: bool
    reason: str


def validate_lifecycle_state(state: TokenLifecycleState | str) -> TokenLifecycleState:
    return state if isinstance(state, TokenLifecycleState) else TokenLifecycleState(state)


def as_lifecycle_event(event: LifecycleEvent | str) -> LifecycleEvent:
    return event if isinstance(event, LifecycleEvent) else LifecycleEvent(event)


def can_transition(
    previous_state: TokenLifecycleState | str,
    new_state: TokenLifecycleState | str,
    reason: LifecycleEvent | str,
) -> bool:
    previous = validate_lifecycle_state(previous_state)
    new = validate_lifecycle_state(new_state)
    event = as_lifecycle_event(reason)

    if new not in ALLOWED_TRANSITIONS[previous]:
        return False
    if previous == TokenLifecycleState.ARCHIVED and event not in REOPEN_EVENTS:
        return False
    if (
        previous == TokenLifecycleState.INSTANT_REJECT_MEMORY_ONLY
        and new in {TokenLifecycleState.TRACK_NORMAL, TokenLifecycleState.TRACK_FAST}
        and event not in MANUAL_REVIEW_EVENTS
    ):
        return False
    if (
        previous == TokenLifecycleState.PAPER_MONITORING
        and new == TokenLifecycleState.WATCH_ONLY
    ):
        return False
    return True


def transition_token_state(
    previous_state: TokenLifecycleState | str,
    new_state: TokenLifecycleState | str,
    reason: LifecycleEvent | str,
) -> LifecycleTransition:
    previous = validate_lifecycle_state(previous_state)
    new = validate_lifecycle_state(new_state)
    event = as_lifecycle_event(reason)
    allowed = can_transition(previous, new, event)
    return LifecycleTransition(
        previous_state=previous,
        new_state=new,
        lifecycle_event=event,
        allowed=allowed,
        reason="allowed" if allowed else "transition_not_allowed",
    )


def should_promote_to_track_fast(
    *,
    source_status: SourceStatus,
    data_quality_label: DataQualityLabel,
    has_fast_activity: bool,
    has_usable_pair: bool,
) -> bool:
    return (
        source_status in {SourceStatus.COMPLETE, SourceStatus.PARTIAL}
        and data_quality_label not in BAD_DATA_LABELS
        and has_fast_activity
        and has_usable_pair
    )


def should_promote_to_track_normal(
    *,
    source_status: SourceStatus,
    data_quality_label: DataQualityLabel,
    has_usable_pair: bool,
) -> bool:
    return (
        source_status in {SourceStatus.COMPLETE, SourceStatus.PARTIAL}
        and data_quality_label not in BAD_DATA_LABELS
        and has_usable_pair
    )


def should_demote_to_watch_only(
    *,
    source_status: SourceStatus,
    data_quality_label: DataQualityLabel,
    activity_faded: bool,
) -> bool:
    return (
        activity_faded
        or source_status in {SourceStatus.STALE, SourceStatus.CONFLICTING}
        or data_quality_label in {DataQualityLabel.STALE_DATA, DataQualityLabel.CONFLICTING_DATA}
    )


def should_enter_cooldown(*, repeated_failures: bool, source_status: SourceStatus) -> bool:
    return repeated_failures or source_status == SourceStatus.FAILED


def should_archive_token(
    *,
    stale: bool = False,
    unusable_liquidity: bool = False,
    memory_window_complete: bool = False,
) -> bool:
    return stale or unusable_liquidity or memory_window_complete


def should_reopen_token(*, revival_detected: bool, manual_review: bool = False) -> bool:
    return revival_detected or manual_review


def classify_initial_state(
    *,
    chain: str,
    source_status: SourceStatus,
    data_quality_label: DataQualityLabel,
    has_usable_pair: bool,
    has_fast_activity: bool = False,
) -> TokenLifecycleState:
    if chain != PRINTER_CHAIN:
        return TokenLifecycleState.INSTANT_REJECT_MEMORY_ONLY
    if source_status == SourceStatus.FAILED or data_quality_label in BAD_DATA_LABELS:
        return TokenLifecycleState.INSTANT_REJECT_MEMORY_ONLY
    if not has_usable_pair:
        return TokenLifecycleState.WATCH_ONLY
    if has_fast_activity:
        return TokenLifecycleState.TRACK_FAST
    return TokenLifecycleState.TRACK_NORMAL

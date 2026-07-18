"""Pure two-token scheduler fairness policy for V2-9.7D.3B.

This module does not enqueue, claim, execute, retry, or persist scheduler work.
It orders already-materialised scheduler-work records for one bounded campaign
with exactly two active token slots, using the existing scheduler vocabulary and
3A identity validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Iterable

from printer_v1.lifecycle.contracts import TokenLifecycleState
from printer_v1.operator_cli.campaign_identity_state import validate_identity
from printer_v1.scheduler.contracts import JobKind, JobStatus


TWO_TOKEN_ACTIVE_SLOT_COUNT = 2

TOKEN_TERMINAL_OR_INELIGIBLE_STATES = frozenset(
    {
        TokenLifecycleState.COOLDOWN.value,
        TokenLifecycleState.ARCHIVED.value,
        TokenLifecycleState.INSTANT_REJECT_MEMORY_ONLY.value,
        "CANCELLED",
        "FAILED",
        "BLOCKED",
        "MANUAL_REVIEW",
        "SKIPPED",
        "TERMINAL_COMPLETED",
        "TERMINAL_STOPPED",
        "TERMINAL_BLOCKED",
        "TERMINAL_FAILED",
    }
)

SELECTABLE_WORK_STATUSES = frozenset(
    {
        JobStatus.PENDING.value,
        JobStatus.COOLDOWN.value,
    }
)

SHARED_STOP_REASONS = frozenset(
    {
        "SHARED_DB_FAILURE",
        "SHARED_LEASE_FAILURE",
        "SHARED_INTEGRITY_FAILURE",
        "CAMPAIGN_BUDGET_FAILURE",
    }
)

CEILING_STOP_REASON_ORDER = (
    "scheduler_work_ceiling_exhausted",
    "source_request_ceiling_exhausted",
    "storage_growth_ceiling_exhausted",
    "failure_ceiling_exhausted",
)


class SchedulerWorkIntent(StrEnum):
    MAIN_WINDOW_CLOSE = "MAIN_WINDOW_CLOSE"
    EVIDENCE_GAP = "EVIDENCE_GAP"
    SAFE_STOP = "SAFE_STOP"
    ORDINARY = "ORDINARY"


class SchedulerSelectionStatus(StrEnum):
    SELECTED = "SELECTED"
    BLOCKED = "BLOCKED"
    NO_ELIGIBLE_WORK = "NO_ELIGIBLE_WORK"


@dataclass(frozen=True)
class TwoTokenSlot:
    slot_id: str
    token_id: str
    mint_id: str
    pair_id: str
    lifecycle_id: str
    token_state: str
    ordinary_service_count: int = 0
    eligible: bool = True
    token_local_failure: bool = False


@dataclass(frozen=True)
class SchedulerWorkItem:
    scheduler_work_id: str
    token_slot_id: str
    token_id: str
    job_kind: JobKind | str
    work_intent: SchedulerWorkIntent | str
    status: JobStatus | str = JobStatus.PENDING
    scheduled_for: datetime | None = None
    deadline_at: datetime | None = None
    created_at: datetime | None = None
    eligible: bool = True


@dataclass(frozen=True)
class CampaignSchedulerCeilings:
    scheduler_work_ceiling: int | None = None
    scheduler_work_used: int = 0
    source_request_ceiling: int | None = None
    source_requests_used: int = 0
    storage_growth_ceiling: int | None = None
    storage_growth_used: int = 0
    failure_ceiling: int | None = None
    failures_used: int = 0


@dataclass(frozen=True)
class TwoTokenSchedulerSelection:
    status: SchedulerSelectionStatus
    selected_work: SchedulerWorkItem | None
    reason: str
    excluded_work_ids: tuple[str, ...] = ()


def select_two_token_scheduler_work(
    *,
    token_slots: Iterable[TwoTokenSlot],
    work_items: Iterable[SchedulerWorkItem],
    now: datetime,
    ceilings: CampaignSchedulerCeilings | None = None,
    shared_stop_reasons: Iterable[str] = (),
) -> TwoTokenSchedulerSelection:
    """Select the next deterministic two-token scheduler-work item.

    Selection is idempotent for the same input state. Shared DB, lease,
    integrity, or campaign-budget failures stop scheduling. Token-local failure
    excludes only that token's work. Exhausted ceilings return an honest blocked
    result instead of manufacturing retries or a restart.
    """
    current_time = _normalize_time(now)
    slots = tuple(token_slots)
    items = tuple(work_items)

    if len(slots) != TWO_TOKEN_ACTIVE_SLOT_COUNT:
        return _blocked("active_token_slot_count_not_two")

    try:
        slot_by_id = _validated_slots(slots)
        validated_items = tuple(_validated_work_items(items))
    except ValueError as exc:
        return _blocked(str(exc))

    for reason in shared_stop_reasons:
        if reason in SHARED_STOP_REASONS:
            return _blocked(reason.lower())

    ceiling_reason = _exhausted_ceiling_reason(ceilings or CampaignSchedulerCeilings())
    if ceiling_reason is not None:
        return _blocked(ceiling_reason)

    eligible, excluded = _eligible_work(validated_items, slot_by_id, current_time)
    if not eligible:
        return TwoTokenSchedulerSelection(
            status=SchedulerSelectionStatus.NO_ELIGIBLE_WORK,
            selected_work=None,
            reason="no_eligible_work",
            excluded_work_ids=excluded,
        )

    selected = min(eligible, key=lambda item: _selection_key(item, slot_by_id))
    return TwoTokenSchedulerSelection(
        status=SchedulerSelectionStatus.SELECTED,
        selected_work=selected,
        reason="selected",
        excluded_work_ids=excluded,
    )


def _blocked(reason: str) -> TwoTokenSchedulerSelection:
    return TwoTokenSchedulerSelection(
        status=SchedulerSelectionStatus.BLOCKED,
        selected_work=None,
        reason=reason,
    )


def _normalize_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _validated_slots(slots: tuple[TwoTokenSlot, ...]) -> dict[str, tuple[int, TwoTokenSlot]]:
    by_slot: dict[str, tuple[int, TwoTokenSlot]] = {}
    token_ids: set[str] = set()
    for index, slot in enumerate(slots):
        slot_id = validate_identity("token_slot", slot.slot_id)
        token_id = validate_identity("token", slot.token_id)
        validate_identity("mint", slot.mint_id)
        validate_identity("pair", slot.pair_id)
        validate_identity("lifecycle", slot.lifecycle_id)
        if slot_id in by_slot:
            raise ValueError("duplicate_token_slot_identity")
        if token_id in token_ids:
            raise ValueError("duplicate_token_identity")
        if slot.ordinary_service_count < 0:
            raise ValueError("negative_ordinary_service_count")
        by_slot[slot_id] = (index, slot)
        token_ids.add(token_id)
    return by_slot


def _validated_work_items(items: tuple[SchedulerWorkItem, ...]) -> Iterable[SchedulerWorkItem]:
    seen_work_ids: set[str] = set()
    for item in items:
        work_id = validate_identity("scheduler_work", item.scheduler_work_id)
        validate_identity("token_slot", item.token_slot_id)
        validate_identity("token", item.token_id)
        JobKind(item.job_kind)
        SchedulerWorkIntent(item.work_intent)
        JobStatus(item.status)
        if work_id in seen_work_ids:
            raise ValueError("duplicate_scheduler_work_identity")
        seen_work_ids.add(work_id)
        yield item


def _eligible_work(
    items: tuple[SchedulerWorkItem, ...],
    slot_by_id: dict[str, tuple[int, TwoTokenSlot]],
    now: datetime,
) -> tuple[tuple[SchedulerWorkItem, ...], tuple[str, ...]]:
    eligible: list[SchedulerWorkItem] = []
    excluded: list[str] = []
    for item in items:
        slot_entry = slot_by_id.get(item.token_slot_id)
        if slot_entry is None:
            excluded.append(item.scheduler_work_id)
            continue
        _, slot = slot_entry
        if item.token_id != slot.token_id:
            excluded.append(item.scheduler_work_id)
            continue
        if not item.eligible or not slot.eligible or slot.token_local_failure:
            excluded.append(item.scheduler_work_id)
            continue
        if str(slot.token_state) in TOKEN_TERMINAL_OR_INELIGIBLE_STATES:
            excluded.append(item.scheduler_work_id)
            continue
        if str(item.status) not in SELECTABLE_WORK_STATUSES:
            excluded.append(item.scheduler_work_id)
            continue
        if item.scheduled_for is not None and _normalize_time(item.scheduled_for) > now:
            excluded.append(item.scheduler_work_id)
            continue
        eligible.append(item)
    return tuple(eligible), tuple(excluded)


def _selection_key(
    item: SchedulerWorkItem,
    slot_by_id: dict[str, tuple[int, TwoTokenSlot]],
) -> tuple[object, ...]:
    slot_index, slot = slot_by_id[item.token_slot_id]
    category = _category_value(item)
    deadline = _deadline_value(item) if category == 0 else "9999-12-31T23:59:59+00:00"
    return (
        category,
        deadline,
        slot.ordinary_service_count,
        _created_value(item),
        slot_index,
        item.scheduler_work_id,
    )


def _category_value(item: SchedulerWorkItem) -> int:
    kind = JobKind(item.job_kind)
    intent = SchedulerWorkIntent(item.work_intent)
    if kind == JobKind.MEMORY_WINDOW_CLOSE and intent == SchedulerWorkIntent.MAIN_WINDOW_CLOSE:
        return 0
    if intent in {SchedulerWorkIntent.EVIDENCE_GAP, SchedulerWorkIntent.SAFE_STOP}:
        return 1
    return 2


def _deadline_value(item: SchedulerWorkItem) -> str:
    if item.deadline_at is not None:
        return _normalize_time(item.deadline_at).isoformat()
    if item.scheduled_for is not None:
        return _normalize_time(item.scheduled_for).isoformat()
    return "9999-12-31T23:59:59+00:00"


def _created_value(item: SchedulerWorkItem) -> str:
    if item.created_at is None:
        return "9999-12-31T23:59:59+00:00"
    return _normalize_time(item.created_at).isoformat()


def _exhausted_ceiling_reason(ceilings: CampaignSchedulerCeilings) -> str | None:
    checks = {
        "scheduler_work_ceiling_exhausted": (
            ceilings.scheduler_work_used,
            ceilings.scheduler_work_ceiling,
        ),
        "source_request_ceiling_exhausted": (
            ceilings.source_requests_used,
            ceilings.source_request_ceiling,
        ),
        "storage_growth_ceiling_exhausted": (
            ceilings.storage_growth_used,
            ceilings.storage_growth_ceiling,
        ),
        "failure_ceiling_exhausted": (
            ceilings.failures_used,
            ceilings.failure_ceiling,
        ),
    }
    for reason in CEILING_STOP_REASON_ORDER:
        used, ceiling = checks[reason]
        if ceiling is not None and used >= ceiling:
            return reason
    return None

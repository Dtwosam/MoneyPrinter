"""Campaign-wide fairness composition for up to three exact two-token cycles.

The existing two-token selector remains authoritative inside each cycle. This
module only compares each cycle's already-selected next work item to preserve
close/safe-stop priority and deterministic ordinary fairness across cycles.
It does not enqueue, claim, execute, fetch, retry, or persist work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from printer_v1.operator_cli.campaign_identity_state import validate_identity
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    MAX_ACTIVE_TWO_TOKEN_CYCLES,
)
from printer_v1.scheduler.contracts import JobKind
from printer_v1.scheduler.two_token_fairness import (
    TWO_TOKEN_ACTIVE_SLOT_COUNT,
    CampaignSchedulerCeilings,
    SchedulerSelectionStatus,
    SchedulerWorkIntent,
    SchedulerWorkItem,
    TwoTokenSlot,
    select_two_token_scheduler_work,
)


@dataclass(frozen=True)
class TwoTokenCycleWork:
    cycle_id: str
    cycle_ordinal: int
    token_slots: tuple[TwoTokenSlot, ...]
    work_items: tuple[SchedulerWorkItem, ...]


@dataclass(frozen=True)
class MultiCycleSchedulerSelection:
    status: SchedulerSelectionStatus
    selected_cycle_id: str | None
    selected_work: SchedulerWorkItem | None
    reason: str
    excluded_work_ids: tuple[str, ...] = ()


def _blocked(reason: str, excluded: Iterable[str] = ()) -> MultiCycleSchedulerSelection:
    return MultiCycleSchedulerSelection(
        status=SchedulerSelectionStatus.BLOCKED,
        selected_cycle_id=None,
        selected_work=None,
        reason=reason,
        excluded_work_ids=tuple(excluded),
    )


def _normalize_time(value: datetime | None) -> str:
    if value is None:
        return "9999-12-31T23:59:59+00:00"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _category(item: SchedulerWorkItem) -> int:
    kind = JobKind(item.job_kind)
    intent = SchedulerWorkIntent(item.work_intent)
    if kind == JobKind.MEMORY_WINDOW_CLOSE and intent == SchedulerWorkIntent.MAIN_WINDOW_CLOSE:
        return 0
    if intent in {SchedulerWorkIntent.EVIDENCE_GAP, SchedulerWorkIntent.SAFE_STOP}:
        return 1
    return 2


def _candidate_key(
    cycle: TwoTokenCycleWork,
    work: SchedulerWorkItem,
) -> tuple[object, ...]:
    slots = {slot.slot_id: slot for slot in cycle.token_slots}
    slot = slots.get(work.token_slot_id)
    if slot is None:
        raise ValueError("selected work does not belong to its cycle")
    category = _category(work)
    if category == 0:
        return (
            0,
            _normalize_time(work.deadline_at or work.scheduled_for),
            _normalize_time(work.created_at),
            cycle.cycle_ordinal,
            work.scheduler_work_id,
        )
    if category == 1:
        return (
            1,
            _normalize_time(work.created_at),
            cycle.cycle_ordinal,
            work.scheduler_work_id,
        )
    return (
        2,
        slot.ordinary_service_count,
        _normalize_time(work.created_at),
        cycle.cycle_ordinal,
        work.scheduler_work_id,
    )


def _validate_cycles(cycles: tuple[TwoTokenCycleWork, ...]) -> str | None:
    if not cycles:
        return "no_active_cycles"
    if len(cycles) > MAX_ACTIVE_TWO_TOKEN_CYCLES:
        return "active_cycle_count_exceeds_compiled_maximum"

    cycle_ids: set[str] = set()
    ordinals: set[int] = set()
    token_ids: set[str] = set()
    slot_ids: set[str] = set()
    for cycle in cycles:
        try:
            cycle_id = validate_identity("cycle", cycle.cycle_id)
        except ValueError as exc:
            return str(exc)
        if cycle_id in cycle_ids:
            return "duplicate_cycle_identity"
        if type(cycle.cycle_ordinal) is not int or cycle.cycle_ordinal <= 0:
            return "invalid_cycle_ordinal"
        if cycle.cycle_ordinal in ordinals:
            return "duplicate_cycle_ordinal"
        if len(cycle.token_slots) != TWO_TOKEN_ACTIVE_SLOT_COUNT:
            return "cycle_does_not_have_exactly_two_slots"
        for slot in cycle.token_slots:
            if slot.slot_id in slot_ids:
                return "duplicate_token_slot_identity_across_cycles"
            if slot.token_id in token_ids:
                return "duplicate_token_identity_across_cycles"
            slot_ids.add(slot.slot_id)
            token_ids.add(slot.token_id)
        cycle_ids.add(cycle_id)
        ordinals.add(cycle.cycle_ordinal)
    return None


def select_multi_cycle_scheduler_work(
    *,
    cycles: Iterable[TwoTokenCycleWork],
    now: datetime,
    ceilings: CampaignSchedulerCeilings | None = None,
    shared_stop_reasons: Iterable[str] = (),
) -> MultiCycleSchedulerSelection:
    """Select one deterministic next work item across 1-3 two-token cycles."""
    cycle_items = tuple(cycles)
    invalid = _validate_cycles(cycle_items)
    if invalid is not None:
        return _blocked(invalid)

    shared_ceilings = ceilings or CampaignSchedulerCeilings()
    shared_stops = tuple(shared_stop_reasons)
    excluded: list[str] = []
    candidates: list[tuple[TwoTokenCycleWork, SchedulerWorkItem]] = []

    for cycle in sorted(cycle_items, key=lambda item: (item.cycle_ordinal, item.cycle_id)):
        result = select_two_token_scheduler_work(
            token_slots=cycle.token_slots,
            work_items=cycle.work_items,
            now=now,
            ceilings=shared_ceilings,
            shared_stop_reasons=shared_stops,
        )
        excluded.extend(result.excluded_work_ids)
        if result.status == SchedulerSelectionStatus.BLOCKED:
            return _blocked(result.reason, excluded)
        if result.status == SchedulerSelectionStatus.SELECTED:
            if result.selected_work is None:
                return _blocked("selected_cycle_work_missing", excluded)
            candidates.append((cycle, result.selected_work))

    if not candidates:
        return MultiCycleSchedulerSelection(
            status=SchedulerSelectionStatus.NO_ELIGIBLE_WORK,
            selected_cycle_id=None,
            selected_work=None,
            reason="no_eligible_work",
            excluded_work_ids=tuple(excluded),
        )

    try:
        selected_cycle, selected_work = min(
            candidates,
            key=lambda candidate: _candidate_key(candidate[0], candidate[1]),
        )
    except ValueError as exc:
        return _blocked(str(exc), excluded)

    return MultiCycleSchedulerSelection(
        status=SchedulerSelectionStatus.SELECTED,
        selected_cycle_id=selected_cycle.cycle_id,
        selected_work=selected_work,
        reason="selected",
        excluded_work_ids=tuple(excluded),
    )

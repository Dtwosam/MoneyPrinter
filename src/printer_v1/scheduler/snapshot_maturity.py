"""Central-Scheduler policy for snapshot-readiness maturity admission."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum


SNAPSHOT_MATURITY_SECONDS = 900


class SnapshotMaturityContractError(ValueError):
    """The injected Scheduler clock does not satisfy the maturity contract."""


class SnapshotMaturityState(StrEnum):
    IMMATURE = "IMMATURE"
    DUE = "DUE"
    INVALID_ORIGIN_TIME = "INVALID_ORIGIN_TIME"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class SnapshotMaturityDecision:
    state: SnapshotMaturityState
    evaluated_at_utc: datetime
    origin_block_time_utc: datetime | None
    due_at_utc: datetime | None


def _evaluation_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise SnapshotMaturityContractError(
            "snapshot maturity requires a timezone-aware evaluation clock"
        )
    return value.astimezone(timezone.utc)


def evaluate_snapshot_maturity(
    *,
    pump_block_time: object,
    evaluated_at: datetime,
    cancelled: bool = False,
) -> SnapshotMaturityDecision:
    """Classify one finalized Pump origin without waiting or provider work."""
    evaluated_utc = _evaluation_utc(evaluated_at)
    if type(cancelled) is not bool:
        raise SnapshotMaturityContractError("cancelled must be a boolean")
    if cancelled:
        return SnapshotMaturityDecision(
            state=SnapshotMaturityState.CANCELLED,
            evaluated_at_utc=evaluated_utc,
            origin_block_time_utc=None,
            due_at_utc=None,
        )
    if type(pump_block_time) is not int or pump_block_time <= 0:
        return SnapshotMaturityDecision(
            state=SnapshotMaturityState.INVALID_ORIGIN_TIME,
            evaluated_at_utc=evaluated_utc,
            origin_block_time_utc=None,
            due_at_utc=None,
        )
    try:
        origin_utc = datetime.fromtimestamp(pump_block_time, tz=timezone.utc)
        due_utc = origin_utc + timedelta(seconds=SNAPSHOT_MATURITY_SECONDS)
    except (OverflowError, OSError, ValueError):
        return SnapshotMaturityDecision(
            state=SnapshotMaturityState.INVALID_ORIGIN_TIME,
            evaluated_at_utc=evaluated_utc,
            origin_block_time_utc=None,
            due_at_utc=None,
        )
    return SnapshotMaturityDecision(
        state=(
            SnapshotMaturityState.DUE
            if evaluated_utc >= due_utc
            else SnapshotMaturityState.IMMATURE
        ),
        evaluated_at_utc=evaluated_utc,
        origin_block_time_utc=origin_utc,
        due_at_utc=due_utc,
    )

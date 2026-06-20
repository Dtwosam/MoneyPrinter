"""Deterministic token-level snapshot timing helpers."""

from datetime import datetime, timedelta, timezone
from collections.abc import Iterable

from printer_v1.lifecycle.contracts import TokenLifecycleState
from printer_v1.snapshots.contracts import SnapshotMode


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def normalized_reasons(reason_labels: Iterable[str] | None) -> set[str]:
    return {label.lower() for label in reason_labels or ()}


def get_base_snapshot_interval_seconds(
    tracking_lane: TokenLifecycleState | str,
    snapshot_mode: SnapshotMode | str,
    token_age_seconds: int | None = None,
    window_age_seconds: int | None = None,
) -> int:
    del window_age_seconds
    lane = TokenLifecycleState(tracking_lane)
    mode = SnapshotMode(snapshot_mode)
    if mode in {SnapshotMode.PAPER_EXIT_PROTECTION_MODE, SnapshotMode.WINDOW_CLOSE_MODE}:
        return 60
    if mode == SnapshotMode.MICRO_EVENT_MODE:
        return 120
    if lane == TokenLifecycleState.PAPER_MONITORING:
        return 60
    if lane == TokenLifecycleState.TRACK_FAST:
        age = token_age_seconds if token_age_seconds is not None else 0
        if age <= 15 * 60:
            return 120
        if age <= 60 * 60:
            return 240
        return 480
    if lane == TokenLifecycleState.TRACK_NORMAL:
        age = token_age_seconds if token_age_seconds is not None else 0
        if age <= 15 * 60:
            return 420
        if age <= 60 * 60:
            return 720
        return 1200
    if lane == TokenLifecycleState.WATCH_ONLY:
        return 1500
    return 1800


def should_speed_up_snapshots(reason_labels: Iterable[str] | None) -> bool:
    reasons = normalized_reasons(reason_labels)
    return bool(reasons & {"micro_event", "dump", "exit_risk", "paper_exit", "revival"})


def should_slow_down_snapshots(reason_labels: Iterable[str] | None) -> bool:
    reasons = normalized_reasons(reason_labels)
    return bool(reasons & {"stable", "cooldown", "watch_only_light"})


def calculate_next_snapshot_at(
    last_snapshot_at: datetime | str,
    tracking_lane: TokenLifecycleState | str,
    snapshot_mode: SnapshotMode | str,
    reason_labels: Iterable[str] | None = None,
) -> datetime:
    last_at = parse_timestamp(last_snapshot_at)
    interval = get_base_snapshot_interval_seconds(tracking_lane, snapshot_mode)
    if should_speed_up_snapshots(reason_labels):
        interval = max(interval // 2, 60)
    elif should_slow_down_snapshots(reason_labels):
        interval = int(interval * 1.5)
    return last_at + timedelta(seconds=interval)


def choose_snapshot_mode(reason_labels: Iterable[str] | None) -> SnapshotMode:
    reasons = normalized_reasons(reason_labels)
    if reasons & {"paper_exit", "exit_risk"}:
        return SnapshotMode.PAPER_EXIT_PROTECTION_MODE
    if "window_close" in reasons:
        return SnapshotMode.WINDOW_CLOSE_MODE
    if "micro_event" in reasons:
        return SnapshotMode.MICRO_EVENT_MODE
    if "dump" in reasons:
        return SnapshotMode.DUMP_MODE
    if "revival" in reasons:
        return SnapshotMode.REVIVAL_MODE
    if "consolidation" in reasons:
        return SnapshotMode.CONSOLIDATION_MODE
    return SnapshotMode.NORMAL_MODE


def should_force_window_close_snapshot(now: datetime, window_closes_at: datetime) -> bool:
    current_time = now.astimezone(timezone.utc)
    closes_at = window_closes_at.astimezone(timezone.utc)
    seconds_until_close = (closes_at - current_time).total_seconds()
    return 0 <= seconds_until_close <= 60

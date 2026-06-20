"""Snapshot gap and memory-window coverage helpers."""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import math
import sqlite3
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, MemoryStatus
from printer_v1.lifecycle.contracts import TokenLifecycleState
from printer_v1.snapshots.contracts import CoverageLabel, SnapshotGapLabel


@dataclass(frozen=True)
class SnapshotGap:
    expected_captured_at: datetime
    actual_captured_at: datetime | None
    gap_seconds: int
    snapshot_gap_label: SnapshotGapLabel


@dataclass(frozen=True)
class WindowCoverage:
    expected_snapshot_count: int
    actual_snapshot_count: int
    missing_snapshot_count: int
    max_gap_seconds: int
    coverage_label: CoverageLabel


def parse_timestamp(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def to_timestamp(value: datetime | str) -> str:
    return parse_timestamp(value).isoformat()


def snapshot_captured_at(snapshot: Mapping[str, Any] | sqlite3.Row) -> datetime:
    return parse_timestamp(snapshot["captured_at"])


@contextmanager
def connect(db_or_connection: str | Path | sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    if isinstance(db_or_connection, sqlite3.Connection):
        db_or_connection.row_factory = sqlite3.Row
        yield db_or_connection
        return
    connection = sqlite3.connect(Path(db_or_connection))
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def classify_snapshot_gap(
    gap_seconds: int,
    expected_interval_seconds: int,
) -> SnapshotGapLabel:
    if gap_seconds <= expected_interval_seconds:
        return SnapshotGapLabel.NO_GAP
    if gap_seconds <= expected_interval_seconds * 2:
        return SnapshotGapLabel.MINOR_GAP
    if gap_seconds <= expected_interval_seconds * 4:
        return SnapshotGapLabel.MAJOR_GAP
    return SnapshotGapLabel.WINDOW_BROKEN


def calculate_expected_snapshot_count(
    opened_at: datetime,
    closed_at: datetime,
    expected_interval_seconds: int,
) -> int:
    seconds = max((closed_at - opened_at).total_seconds(), 0)
    return int(math.floor(seconds / expected_interval_seconds)) + 1


def detect_snapshot_gaps(
    snapshots: Sequence[Mapping[str, Any] | sqlite3.Row],
    expected_interval_seconds: int,
    opened_at: datetime,
    closed_at: datetime,
) -> list[SnapshotGap]:
    captured_times = sorted(snapshot_captured_at(snapshot) for snapshot in snapshots)
    if not captured_times:
        return [
            SnapshotGap(
                expected_captured_at=opened_at,
                actual_captured_at=None,
                gap_seconds=int((closed_at - opened_at).total_seconds()),
                snapshot_gap_label=SnapshotGapLabel.WINDOW_BROKEN,
            )
        ]

    gaps = []
    prior = opened_at
    for captured_at in captured_times:
        gap_seconds = int((captured_at - prior).total_seconds())
        label = classify_snapshot_gap(gap_seconds, expected_interval_seconds)
        if label != SnapshotGapLabel.NO_GAP:
            gaps.append(
                SnapshotGap(
                    expected_captured_at=prior,
                    actual_captured_at=captured_at,
                    gap_seconds=gap_seconds,
                    snapshot_gap_label=label,
                )
            )
        prior = captured_at

    close_gap_seconds = int((closed_at - captured_times[-1]).total_seconds())
    if close_gap_seconds > expected_interval_seconds:
        gaps.append(
            SnapshotGap(
                expected_captured_at=closed_at,
                actual_captured_at=captured_times[-1],
                gap_seconds=close_gap_seconds,
                snapshot_gap_label=SnapshotGapLabel.MISSED_WINDOW_CLOSE,
            )
        )
    return gaps


def classify_window_coverage(
    expected_count: int,
    actual_count: int,
    missing_count: int,
    max_gap_seconds: int,
) -> CoverageLabel:
    if expected_count <= 0:
        return CoverageLabel.AUDIT_ONLY_COVERAGE
    if missing_count == 0 and max_gap_seconds == 0:
        return CoverageLabel.FULL_COVERAGE
    if missing_count <= 1 and actual_count / expected_count >= 0.8:
        return CoverageLabel.ACCEPTABLE_COVERAGE
    if actual_count / expected_count >= 0.5:
        return CoverageLabel.PARTIAL_COVERAGE
    return CoverageLabel.BROKEN_COVERAGE


def calculate_coverage(
    opened_at: datetime,
    closed_at: datetime,
    snapshots: Sequence[Mapping[str, Any] | sqlite3.Row],
    expected_interval_seconds: int,
) -> WindowCoverage:
    expected_count = calculate_expected_snapshot_count(
        opened_at,
        closed_at,
        expected_interval_seconds,
    )
    actual_count = len(snapshots)
    missing_count = max(expected_count - actual_count, 0)
    gaps = detect_snapshot_gaps(snapshots, expected_interval_seconds, opened_at, closed_at)
    max_gap_seconds = max((gap.gap_seconds for gap in gaps), default=0)
    label = classify_window_coverage(
        expected_count,
        actual_count,
        missing_count,
        max_gap_seconds,
    )
    if any(gap.snapshot_gap_label == SnapshotGapLabel.MISSED_WINDOW_CLOSE for gap in gaps):
        label = CoverageLabel.BROKEN_COVERAGE
    return WindowCoverage(
        expected_snapshot_count=expected_count,
        actual_snapshot_count=actual_count,
        missing_snapshot_count=missing_count,
        max_gap_seconds=max_gap_seconds,
        coverage_label=label,
    )


def memory_status_for_coverage(label: CoverageLabel) -> MemoryStatus:
    if label in {CoverageLabel.FULL_COVERAGE, CoverageLabel.ACCEPTABLE_COVERAGE}:
        return MemoryStatus.CLEAN_MEMORY
    if label == CoverageLabel.PARTIAL_COVERAGE:
        return MemoryStatus.PARTIAL_MEMORY
    if label == CoverageLabel.AUDIT_ONLY_COVERAGE:
        return MemoryStatus.AUDIT_ONLY
    return MemoryStatus.DO_NOT_TRAIN


def data_quality_for_coverage(label: CoverageLabel) -> DataQualityLabel:
    if label in {CoverageLabel.FULL_COVERAGE, CoverageLabel.ACCEPTABLE_COVERAGE}:
        return DataQualityLabel.CLEAN_DATA
    if label == CoverageLabel.PARTIAL_COVERAGE:
        return DataQualityLabel.ACCEPTABLE_PARTIAL_DATA
    return DataQualityLabel.DO_NOT_TRAIN


def write_snapshot_window_coverage(
    db_path_or_conn: str | Path | sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int | None,
    window_kind: str,
    tracking_lane: TokenLifecycleState | str,
    opened_at: datetime,
    closed_at: datetime,
    coverage: WindowCoverage,
) -> int:
    label = coverage.coverage_label
    memory_status = memory_status_for_coverage(label)
    data_quality = data_quality_for_coverage(label)
    with connect(db_path_or_conn) as connection:
        cursor = connection.execute(
            """
            INSERT INTO printer_snapshot_window_coverage (
                token_id,
                pair_id,
                window_kind,
                tracking_lane,
                opened_at,
                closed_at,
                expected_snapshot_count,
                actual_snapshot_count,
                missing_snapshot_count,
                max_gap_seconds,
                coverage_label,
                memory_status,
                data_quality_label,
                do_not_train
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token_id,
                pair_id,
                window_kind,
                TokenLifecycleState(tracking_lane).value,
                to_timestamp(opened_at),
                to_timestamp(closed_at),
                coverage.expected_snapshot_count,
                coverage.actual_snapshot_count,
                coverage.missing_snapshot_count,
                coverage.max_gap_seconds,
                label.value,
                memory_status.value,
                data_quality.value,
                1 if memory_status == MemoryStatus.DO_NOT_TRAIN else 0,
            ),
        )
        return int(cursor.lastrowid)

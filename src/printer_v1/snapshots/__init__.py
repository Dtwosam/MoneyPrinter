"""Token-Level Snapshot System foundation for Printer V1."""

from printer_v1.snapshots.contracts import (
    CoverageLabel,
    QuoteRouteStatus,
    SnapshotGapLabel,
    SnapshotMode,
    SnapshotQualityLabel,
)
from printer_v1.snapshots.coverage import calculate_coverage, detect_snapshot_gaps
from printer_v1.snapshots.frequency import (
    calculate_next_snapshot_at,
    get_base_snapshot_interval_seconds,
)
from printer_v1.snapshots.quality import (
    classify_snapshot_quality,
    normalize_snapshot_payload,
    snapshot_can_support_clean_memory,
)
from printer_v1.snapshots.recorder import record_token_snapshot

__all__ = [
    "CoverageLabel",
    "QuoteRouteStatus",
    "SnapshotGapLabel",
    "SnapshotMode",
    "SnapshotQualityLabel",
    "calculate_coverage",
    "calculate_next_snapshot_at",
    "classify_snapshot_quality",
    "detect_snapshot_gaps",
    "get_base_snapshot_interval_seconds",
    "normalize_snapshot_payload",
    "record_token_snapshot",
    "snapshot_can_support_clean_memory",
]

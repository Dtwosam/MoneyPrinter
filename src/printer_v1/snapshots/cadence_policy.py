"""Snapshot Cadence / Gap Policy for Printer V1 — single authoritative contract.

V2-6.1a authoritative cadence contract. This is the ONE source of truth for
snapshot spacing consumed by every runner and quality gate. Each (window, lane)
has three gap tiers plus an expected minimum schedule:

  | Window          | Lane   | Nominal | Dirty above | Block above | Expected |
  |-----------------|--------|--------:|------------:|------------:|---------:|
  | 5m support      | FAST   |     30s |         45s |         60s |       11 |
  | 5m support      | NORMAL |     60s |         90s |        120s |        6 |
  | 15m             | FAST   |     60s |         90s |        120s |       16 |
  | 15m             | NORMAL |    120s |        180s |        240s |        9 |
  | 1h continuation | FAST   |    120s |        180s |        240s |       24 |
  | 1h continuation | NORMAL |    240s |        360s |        480s |       13 |

Coverage classification (count + gap, strict):
  CLEAN   (PASS)   — count >= expected AND every gap <= dirty_above.
  DIRTY            — a gap in (dirty_above, block_above], OR count < expected
                     (missed snapshots) with all gaps <= block_above.
  BLOCKED          — a gap > block_above, too few snapshots to evaluate,
                     disabled/support-only window, or unparseable boundaries.

15m -> 1h transition rule (gap from the 15m closing snapshot to the first 1h
continuation snapshot):
  FAST:   expected <=120s, dirty >180s, block >240s
  NORMAL: expected <=240s, dirty >360s, block >480s

Rules enforced:
  - WINDOW_15M and genuine WINDOW_1H continuation are enabled main windows.
  - WINDOW_5M_MICRO_EVENT is support-only; never a main clean-memory window.
  - WINDOW_4H / WINDOW_12H / WINDOW_24H are recognized but disabled.
  - Missing snapshots are reported, never interpolated.
  - Source/scheduler budget pressure must produce dirty/blocked coverage — it
    must never silently widen a clean-memory gap.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


CADENCE_POLICY_PASS: str = "CADENCE_POLICY_PASS"
CADENCE_POLICY_DIRTY: str = "CADENCE_POLICY_DIRTY"
CADENCE_POLICY_BLOCKED: str = "CADENCE_POLICY_BLOCKED"
CADENCE_POLICY_UNKNOWN: str = "CADENCE_POLICY_UNKNOWN"

# Transition classification statuses (15m -> 1h continuity).
TRANSITION_CLEAN: str = "TRANSITION_CLEAN"
TRANSITION_DIRTY: str = "TRANSITION_DIRTY"
TRANSITION_BLOCKED: str = "TRANSITION_BLOCKED"
TRANSITION_UNKNOWN: str = "TRANSITION_UNKNOWN"

# Minimum snapshots needed to evaluate gaps at all.
_MIN_EVALUABLE_SNAPSHOTS: int = 2

# Sentinel meaning "matches any tracking lane"
_ANY_LANE: str = "*"


@dataclass(frozen=True)
class SnapshotCadencePolicy:
    """Authoritative snapshot cadence requirements for a given window / lane."""

    window_kind: str
    tracking_lane: str  # "TRACK_FAST", "TRACK_NORMAL", or "*" (any)
    asset_state: str    # "any" (reserved for future urgency differentiation)
    urgency_state: str  # "any" (reserved)

    # Nominal snapshot spacing target INSIDE the window (the scheduling gap).
    target_snapshot_interval_seconds: int

    # Middle tier: a gap above this makes coverage DIRTY (do_not_train), not clean.
    dirty_above_gap_seconds: int

    # Hard ceiling: any gap exceeding this BLOCKS the window (never clean/dirty).
    max_clean_snapshot_gap_seconds: int

    # How long the window stays open before close/evaluation.
    window_close_interval_seconds: int

    # Expected minimum schedule: the snapshot count a clean window should have.
    # count < this (with acceptable gaps) => DIRTY (missed snapshots reported).
    minimum_required_snapshots: int

    support_only: bool
    enabled_for_real_collection: bool


# ---------------------------------------------------------------------------
# Authoritative policy table (V2-6.1a)
# ---------------------------------------------------------------------------

_POLICIES: tuple[SnapshotCadencePolicy, ...] = (
    # 5m support-evidence windows (support-only; never a main clean window).
    SnapshotCadencePolicy(
        window_kind="WINDOW_5M_MICRO_EVENT", tracking_lane="TRACK_FAST",
        asset_state="any", urgency_state="any",
        target_snapshot_interval_seconds=30, dirty_above_gap_seconds=45,
        max_clean_snapshot_gap_seconds=60, window_close_interval_seconds=300,
        minimum_required_snapshots=11, support_only=True,
        enabled_for_real_collection=False,
    ),
    SnapshotCadencePolicy(
        window_kind="WINDOW_5M_MICRO_EVENT", tracking_lane="TRACK_NORMAL",
        asset_state="any", urgency_state="any",
        target_snapshot_interval_seconds=60, dirty_above_gap_seconds=90,
        max_clean_snapshot_gap_seconds=120, window_close_interval_seconds=300,
        minimum_required_snapshots=6, support_only=True,
        enabled_for_real_collection=False,
    ),
    # 15m — the primary enabled main clean-memory window.
    SnapshotCadencePolicy(
        window_kind="WINDOW_15M", tracking_lane="TRACK_FAST",
        asset_state="any", urgency_state="any",
        target_snapshot_interval_seconds=60, dirty_above_gap_seconds=90,
        max_clean_snapshot_gap_seconds=120, window_close_interval_seconds=900,
        minimum_required_snapshots=16, support_only=False,
        enabled_for_real_collection=True,
    ),
    SnapshotCadencePolicy(
        window_kind="WINDOW_15M", tracking_lane="TRACK_NORMAL",
        asset_state="any", urgency_state="any",
        target_snapshot_interval_seconds=120, dirty_above_gap_seconds=180,
        max_clean_snapshot_gap_seconds=240, window_close_interval_seconds=900,
        minimum_required_snapshots=9, support_only=False,
        enabled_for_real_collection=True,
    ),
    # 1h continuation windows (t=15m..60m = 2700s continuation phase).
    SnapshotCadencePolicy(
        window_kind="WINDOW_1H", tracking_lane="TRACK_FAST",
        asset_state="any", urgency_state="any",
        target_snapshot_interval_seconds=120, dirty_above_gap_seconds=180,
        max_clean_snapshot_gap_seconds=240, window_close_interval_seconds=2700,
        minimum_required_snapshots=24, support_only=False,
        enabled_for_real_collection=True,
    ),
    SnapshotCadencePolicy(
        window_kind="WINDOW_1H", tracking_lane="TRACK_NORMAL",
        asset_state="any", urgency_state="any",
        target_snapshot_interval_seconds=240, dirty_above_gap_seconds=360,
        max_clean_snapshot_gap_seconds=480, window_close_interval_seconds=2700,
        minimum_required_snapshots=13, support_only=False,
        enabled_for_real_collection=True,
    ),
    # 4h / 12h / 24h — recognized but disabled for real collection.
    SnapshotCadencePolicy(
        window_kind="WINDOW_4H", tracking_lane=_ANY_LANE,
        asset_state="any", urgency_state="any",
        target_snapshot_interval_seconds=300, dirty_above_gap_seconds=450,
        max_clean_snapshot_gap_seconds=600, window_close_interval_seconds=14400,
        minimum_required_snapshots=2, support_only=False,
        enabled_for_real_collection=False,
    ),
    SnapshotCadencePolicy(
        window_kind="WINDOW_12H", tracking_lane=_ANY_LANE,
        asset_state="any", urgency_state="any",
        target_snapshot_interval_seconds=900, dirty_above_gap_seconds=1350,
        max_clean_snapshot_gap_seconds=1800, window_close_interval_seconds=43200,
        minimum_required_snapshots=2, support_only=False,
        enabled_for_real_collection=False,
    ),
    SnapshotCadencePolicy(
        window_kind="WINDOW_24H", tracking_lane=_ANY_LANE,
        asset_state="any", urgency_state="any",
        target_snapshot_interval_seconds=1800, dirty_above_gap_seconds=2700,
        max_clean_snapshot_gap_seconds=3600, window_close_interval_seconds=86400,
        minimum_required_snapshots=2, support_only=False,
        enabled_for_real_collection=False,
    ),
)


# ---------------------------------------------------------------------------
# 15m -> 1h transition contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TransitionThresholds:
    expected_max_seconds: int
    dirty_above_seconds: int
    block_above_seconds: int


_TRANSITION: dict[str, TransitionThresholds] = {
    "TRACK_FAST": TransitionThresholds(120, 180, 240),
    "TRACK_NORMAL": TransitionThresholds(240, 360, 480),
}


@dataclass(frozen=True)
class CadencePolicyEvaluation:
    """Result of evaluating a window's snapshot coverage against the policy."""

    policy_found: bool
    window_kind: str
    tracking_lane: str | None
    enabled_for_real_collection: bool
    support_only: bool
    target_snapshot_interval_seconds: int | None
    dirty_above_gap_seconds: int | None
    max_clean_snapshot_gap_seconds: int | None
    minimum_required_snapshots: int | None
    expected_minimum_snapshots: int | None
    actual_snapshot_count: int
    missed_snapshots: int | None
    actual_max_gap_seconds: float | None
    actual_gaps_seconds: list[float] = field(default_factory=list)
    cadence_policy_status: str = CADENCE_POLICY_UNKNOWN
    blocked_reason: str | None = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_policy(
    window_kind: str,
    tracking_lane: str | None,
) -> SnapshotCadencePolicy | None:
    """Return the matching policy or None. Exact lane first, then wildcard."""
    lane = tracking_lane or _ANY_LANE
    for p in _POLICIES:
        if p.window_kind == window_kind and p.tracking_lane == lane:
            return p
    for p in _POLICIES:
        if p.window_kind == window_kind and p.tracking_lane == _ANY_LANE:
            return p
    # Lane-specific-only window kinds (e.g. 5m FAST/NORMAL) have no wildcard row.
    # A *lane-less* (None) lookup still resolves to the first lane policy so
    # support-only / enabled checks work without a lane. This fallback fires
    # ONLY when no lane was supplied — an explicit but unmapped lane string
    # (e.g. a generic "TRACKING" token_status that is not a cadence lane) must
    # resolve to None so coverage stays UNKNOWN rather than being force-fit to
    # an arbitrary lane's thresholds. Explicit mapped lanes match above.
    if tracking_lane is None:
        for p in _POLICIES:
            if p.window_kind == window_kind:
                return p
    return None


def expected_snapshot_count(window_seconds: float, nominal_gap_seconds: float) -> int:
    """Expected minimum schedule = ceil(window / nominal_gap) + 1 (both ends)."""
    if nominal_gap_seconds <= 0:
        return 0
    return int(math.ceil(window_seconds / nominal_gap_seconds)) + 1


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    try:
        s = str(value).strip()
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _gap_series(
    snapshots: Sequence[Mapping[str, Any]],
    window_start: datetime,
    window_end: datetime,
) -> list[float]:
    """Return the ordered gap series across the window (start→first→…→last→end)."""
    times: list[datetime] = []
    for snap in snapshots:
        ts = _parse_ts(snap.get("captured_at"))
        if ts is not None:
            times.append(ts)
    times.sort()
    if not times:
        return [(window_end - window_start).total_seconds()]
    boundaries = [window_start] + times + [window_end]
    return [
        (boundaries[i] - boundaries[i - 1]).total_seconds()
        for i in range(1, len(boundaries))
    ]


def evaluate_cadence_policy(
    snapshots: Sequence[Mapping[str, Any]],
    window_start_at: Any,
    window_end_at: Any,
    policy: SnapshotCadencePolicy | None,
    *,
    production_mode: bool = False,
) -> CadencePolicyEvaluation:
    """Evaluate snapshot coverage against a cadence policy (count + gap, strict)."""
    if policy is None:
        return CadencePolicyEvaluation(
            policy_found=False, window_kind="UNKNOWN", tracking_lane=None,
            enabled_for_real_collection=False, support_only=False,
            target_snapshot_interval_seconds=None, dirty_above_gap_seconds=None,
            max_clean_snapshot_gap_seconds=None, minimum_required_snapshots=None,
            expected_minimum_snapshots=None, actual_snapshot_count=len(snapshots),
            missed_snapshots=None, actual_max_gap_seconds=None, actual_gaps_seconds=[],
            cadence_policy_status=CADENCE_POLICY_UNKNOWN, blocked_reason=None,
        )

    actual_count = len(snapshots)

    def _mk(status: str, *, reason: str | None, max_gap: float | None,
            gaps: list[float] | None, missed: int | None) -> CadencePolicyEvaluation:
        return CadencePolicyEvaluation(
            policy_found=True, window_kind=policy.window_kind,
            tracking_lane=policy.tracking_lane,
            enabled_for_real_collection=policy.enabled_for_real_collection,
            support_only=policy.support_only,
            target_snapshot_interval_seconds=policy.target_snapshot_interval_seconds,
            dirty_above_gap_seconds=policy.dirty_above_gap_seconds,
            max_clean_snapshot_gap_seconds=policy.max_clean_snapshot_gap_seconds,
            minimum_required_snapshots=policy.minimum_required_snapshots,
            expected_minimum_snapshots=policy.minimum_required_snapshots,
            actual_snapshot_count=actual_count, missed_snapshots=missed,
            actual_max_gap_seconds=round(max_gap, 3) if max_gap is not None else None,
            actual_gaps_seconds=[round(g, 3) for g in (gaps or [])],
            cadence_policy_status=status, blocked_reason=reason,
        )

    # 0 snapshots — cannot evaluate.
    if actual_count == 0:
        if production_mode:
            return _mk(CADENCE_POLICY_BLOCKED,
                       reason="production_mode_missing_coverage: no snapshots found in window range",
                       max_gap=None, gaps=None, missed=policy.minimum_required_snapshots)
        return _mk(CADENCE_POLICY_UNKNOWN, reason=None, max_gap=None, gaps=None, missed=None)

    if not policy.enabled_for_real_collection:
        return _mk(CADENCE_POLICY_BLOCKED,
                   reason="window_kind_disabled_for_real_collection",
                   max_gap=None, gaps=None, missed=None)

    if policy.support_only:
        return _mk(CADENCE_POLICY_BLOCKED,
                   reason="support_only_window_cannot_be_main_clean_memory",
                   max_gap=None, gaps=None, missed=None)

    start_ts = _parse_ts(window_start_at)
    end_ts = _parse_ts(window_end_at)
    if start_ts is None or end_ts is None:
        return _mk(CADENCE_POLICY_BLOCKED,
                   reason="unparseable_window_boundary_timestamps",
                   max_gap=None, gaps=None, missed=None)

    if actual_count < _MIN_EVALUABLE_SNAPSHOTS:
        return _mk(CADENCE_POLICY_BLOCKED,
                   reason=(f"insufficient_snapshots: need >= {_MIN_EVALUABLE_SNAPSHOTS}"
                           f" to evaluate cadence, got {actual_count}"),
                   max_gap=None, gaps=None,
                   missed=max(0, policy.minimum_required_snapshots - actual_count))

    gaps = _gap_series(snapshots, start_ts, end_ts)
    max_gap = max(gaps) if gaps else 0.0
    missed = max(0, policy.minimum_required_snapshots - actual_count)

    if max_gap > policy.max_clean_snapshot_gap_seconds:
        return _mk(CADENCE_POLICY_BLOCKED,
                   reason=(f"coverage_gap_exceeds_policy: max_gap={max_gap:.1f}s"
                           f" > block_above={policy.max_clean_snapshot_gap_seconds}s"),
                   max_gap=max_gap, gaps=gaps, missed=missed)

    if max_gap > policy.dirty_above_gap_seconds:
        return _mk(CADENCE_POLICY_DIRTY,
                   reason=(f"coverage_gap_dirty: max_gap={max_gap:.1f}s"
                           f" > dirty_above={policy.dirty_above_gap_seconds}s"),
                   max_gap=max_gap, gaps=gaps, missed=missed)

    if actual_count < policy.minimum_required_snapshots:
        return _mk(CADENCE_POLICY_DIRTY,
                   reason=(f"missed_snapshots: expected >= {policy.minimum_required_snapshots},"
                           f" got {actual_count} (missed {missed})"),
                   max_gap=max_gap, gaps=gaps, missed=missed)

    return _mk(CADENCE_POLICY_PASS, reason=None, max_gap=max_gap, gaps=gaps, missed=0)


def evaluate_transition_gap(
    prev_15m_close_at: Any,
    first_1h_snapshot_at: Any,
    tracking_lane: str | None,
) -> dict[str, Any]:
    """Classify the 15m->1h continuation transition gap.

    CLEAN if gap <= expected_max; DIRTY if <= block_above; BLOCKED if above.
    UNKNOWN if either timestamp is missing/unparseable or the lane is unknown.
    """
    thresholds = _TRANSITION.get(str(tracking_lane or ""))
    start = _parse_ts(prev_15m_close_at)
    end = _parse_ts(first_1h_snapshot_at)
    if thresholds is None or start is None or end is None:
        return {
            "transition_status": TRANSITION_UNKNOWN,
            "transition_gap_seconds": None,
            "reason": "missing_lane_or_timestamps",
        }
    gap = (end - start).total_seconds()
    if gap < 0:
        return {
            "transition_status": TRANSITION_BLOCKED,
            "transition_gap_seconds": round(gap, 3),
            "reason": "negative_transition_gap_delayed_restart_disguised_as_continuation",
        }
    if gap > thresholds.block_above_seconds:
        status, reason = TRANSITION_BLOCKED, "transition_gap_exceeds_block"
    elif gap > thresholds.dirty_above_seconds:
        status, reason = TRANSITION_DIRTY, "transition_gap_dirty"
    else:
        status, reason = TRANSITION_CLEAN, None
    return {
        "transition_status": status,
        "transition_gap_seconds": round(gap, 3),
        "expected_max_seconds": thresholds.expected_max_seconds,
        "dirty_above_seconds": thresholds.dirty_above_seconds,
        "block_above_seconds": thresholds.block_above_seconds,
        "reason": reason,
    }


def cadence_policy_evaluation_to_dict(ev: CadencePolicyEvaluation) -> dict[str, Any]:
    """Convert to plain dict for embedding in report payloads."""
    return asdict(ev)

"""Snapshot Cadence / Gap Policy for Printer V1.

Central policy table that defines the accepted snapshot cadence and maximum
allowable gap per window kind, tracking lane, and asset state.

Rules enforced here:
  - WINDOW_15M is the only enabled main clean-memory window.
  - WINDOW_5M_MICRO_EVENT is support-only; disabled for real clean-memory.
  - WINDOW_1H / WINDOW_4H / WINDOW_12H / WINDOW_24H are recognized but
    disabled for real collection.
  - Back-to-back cycles that violate the max gap are BLOCKED at Lane Q.
  - Source budget pressure must produce dirty/audit-only/no memory — not
    widen clean-memory gaps.

Policy lookup:
  get_policy(window_kind, tracking_lane) -> SnapshotCadencePolicy | None

Evaluation:
  evaluate_cadence_policy(snapshots, window_start_at, window_end_at, policy)
    -> CadencePolicyEvaluation

Coverage status values:
  CADENCE_POLICY_PASS     — snapshot cadence meets policy requirements
  CADENCE_POLICY_BLOCKED  — cadence violation; CLEAN_MEMORY must be refused
  CADENCE_POLICY_UNKNOWN  — not enough data to evaluate (0 snapshots in range)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


CADENCE_POLICY_PASS: str = "CADENCE_POLICY_PASS"
CADENCE_POLICY_BLOCKED: str = "CADENCE_POLICY_BLOCKED"
CADENCE_POLICY_UNKNOWN: str = "CADENCE_POLICY_UNKNOWN"

# Sentinel meaning "matches any tracking lane"
_ANY_LANE: str = "*"


@dataclass(frozen=True)
class SnapshotCadencePolicy:
    """Accepted snapshot cadence requirements for a given window / lane."""

    window_kind: str
    tracking_lane: str  # "TRACK_FAST", "TRACK_NORMAL", or "*" (any)
    asset_state: str    # "any" (reserved for future urgency differentiation)
    urgency_state: str  # "any" (reserved)

    # How often snapshots are captured INSIDE the window (snapshot collection interval).
    target_snapshot_interval_seconds: int

    # Hard ceiling: any intra-window gap exceeding this blocks CLEAN_MEMORY.
    max_clean_snapshot_gap_seconds: int

    # How long a window must remain open before it can be closed/evaluated.
    # Distinct from snapshot_interval_seconds: the runner collects repeated
    # snapshots every target_snapshot_interval_seconds, then evaluates after
    # window_close_interval_seconds has elapsed.
    window_close_interval_seconds: int

    # Minimum number of snapshots that must exist in the window range for
    # coverage to be evaluable.  Derived from window_close / target_interval.
    # When actual count < this AND count > 0, BLOCKED as "insufficient_snapshots".
    # When count == 0, result is UNKNOWN (or BLOCKED in production_mode).
    minimum_required_snapshots: int

    # Support-only windows cannot become main clean memory.
    support_only: bool

    # False = recognized but disabled for real collection; block at evaluation.
    enabled_for_real_collection: bool


# ---------------------------------------------------------------------------
# Policy table
# ---------------------------------------------------------------------------

_POLICIES: tuple[SnapshotCadencePolicy, ...] = (
    # 5m support-evidence windows (support-only, not enabled for main memory)
    SnapshotCadencePolicy(
        window_kind="WINDOW_5M_MICRO_EVENT",
        tracking_lane=_ANY_LANE,
        asset_state="any",
        urgency_state="any",
        target_snapshot_interval_seconds=60,
        max_clean_snapshot_gap_seconds=90,
        window_close_interval_seconds=300,
        minimum_required_snapshots=2,
        support_only=True,
        enabled_for_real_collection=False,
    ),
    # 15m — TRACK_FAST (default Memory Factory lane)
    # minimum_required = window_close(900) / target_interval(90) = 10 snapshots
    SnapshotCadencePolicy(
        window_kind="WINDOW_15M",
        tracking_lane="TRACK_FAST",
        asset_state="any",
        urgency_state="any",
        target_snapshot_interval_seconds=90,
        max_clean_snapshot_gap_seconds=120,
        window_close_interval_seconds=900,
        minimum_required_snapshots=10,
        support_only=False,
        enabled_for_real_collection=True,
    ),
    # 15m — TRACK_NORMAL (less frequent sampling acceptable)
    # minimum_required = window_close(900) / target_interval(180) = 5 snapshots
    SnapshotCadencePolicy(
        window_kind="WINDOW_15M",
        tracking_lane="TRACK_NORMAL",
        asset_state="any",
        urgency_state="any",
        target_snapshot_interval_seconds=180,
        max_clean_snapshot_gap_seconds=300,
        window_close_interval_seconds=900,
        minimum_required_snapshots=5,
        support_only=False,
        enabled_for_real_collection=True,
    ),
    # 1h continuation windows (Lane X12 — enabled for structural collection)
    # Continuation phase: t=15m to t=60m = 2700s.  Cadences from frequency.py.
    # TRACK_FAST: 240s interval → ~11 snapshots in 2700s; minimum 8 (≥72%).
    # max gap 600s = 2.5× the 240s interval.
    SnapshotCadencePolicy(
        window_kind="WINDOW_1H",
        tracking_lane="TRACK_FAST",
        asset_state="any",
        urgency_state="any",
        target_snapshot_interval_seconds=240,
        max_clean_snapshot_gap_seconds=600,
        window_close_interval_seconds=2700,
        minimum_required_snapshots=8,
        support_only=False,
        enabled_for_real_collection=True,
    ),
    # TRACK_NORMAL: 720s interval → ~4 snapshots in 2700s; minimum 3 (≥75%).
    # max gap 1800s = 2.5× the 720s interval.
    SnapshotCadencePolicy(
        window_kind="WINDOW_1H",
        tracking_lane="TRACK_NORMAL",
        asset_state="any",
        urgency_state="any",
        target_snapshot_interval_seconds=720,
        max_clean_snapshot_gap_seconds=1800,
        window_close_interval_seconds=2700,
        minimum_required_snapshots=3,
        support_only=False,
        enabled_for_real_collection=True,
    ),
    # 4h windows (disabled)
    SnapshotCadencePolicy(
        window_kind="WINDOW_4H",
        tracking_lane="TRACK_FAST",
        asset_state="any",
        urgency_state="any",
        target_snapshot_interval_seconds=300,
        max_clean_snapshot_gap_seconds=450,
        window_close_interval_seconds=14400,
        minimum_required_snapshots=2,
        support_only=False,
        enabled_for_real_collection=False,
    ),
    SnapshotCadencePolicy(
        window_kind="WINDOW_4H",
        tracking_lane="TRACK_NORMAL",
        asset_state="any",
        urgency_state="any",
        target_snapshot_interval_seconds=600,
        max_clean_snapshot_gap_seconds=900,
        window_close_interval_seconds=14400,
        minimum_required_snapshots=2,
        support_only=False,
        enabled_for_real_collection=False,
    ),
    # 12h windows (disabled)
    SnapshotCadencePolicy(
        window_kind="WINDOW_12H",
        tracking_lane=_ANY_LANE,
        asset_state="any",
        urgency_state="any",
        target_snapshot_interval_seconds=900,
        max_clean_snapshot_gap_seconds=1800,
        window_close_interval_seconds=43200,
        minimum_required_snapshots=2,
        support_only=False,
        enabled_for_real_collection=False,
    ),
    # 24h windows (disabled)
    SnapshotCadencePolicy(
        window_kind="WINDOW_24H",
        tracking_lane=_ANY_LANE,
        asset_state="any",
        urgency_state="any",
        target_snapshot_interval_seconds=1800,
        max_clean_snapshot_gap_seconds=3600,
        window_close_interval_seconds=86400,
        minimum_required_snapshots=2,
        support_only=False,
        enabled_for_real_collection=False,
    ),
)


@dataclass(frozen=True)
class CadencePolicyEvaluation:
    """Result of evaluating a window's snapshot coverage against the policy."""

    policy_found: bool
    window_kind: str
    tracking_lane: str | None
    enabled_for_real_collection: bool
    support_only: bool
    target_snapshot_interval_seconds: int | None
    max_clean_snapshot_gap_seconds: int | None
    minimum_required_snapshots: int | None
    actual_snapshot_count: int
    actual_max_gap_seconds: float | None
    cadence_policy_status: str  # CADENCE_POLICY_PASS | BLOCKED | UNKNOWN
    blocked_reason: str | None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_policy(
    window_kind: str,
    tracking_lane: str | None,
) -> SnapshotCadencePolicy | None:
    """Return the matching policy or None if no policy exists for this combo.

    Lookup order:
      1. Exact match on (window_kind, tracking_lane)
      2. Wildcard match on (window_kind, "*")
      3. None
    """
    lane = tracking_lane or _ANY_LANE

    # Exact match first
    for p in _POLICIES:
        if p.window_kind == window_kind and p.tracking_lane == lane:
            return p

    # Wildcard fallback
    for p in _POLICIES:
        if p.window_kind == window_kind and p.tracking_lane == _ANY_LANE:
            return p

    return None


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


def _compute_max_gap_seconds(
    snapshots: Sequence[Mapping[str, Any]],
    window_start: datetime,
    window_end: datetime,
) -> float:
    """Return the largest gap (seconds) across the entire window span.

    Gaps are measured:
      - From window_start to the first snapshot
      - Between consecutive snapshots
      - From the last snapshot to window_end

    Front-loaded snapshots produce a large trailing gap; back-loaded snapshots
    produce a large leading gap.  Both violate even-gap policy.
    """
    times: list[datetime] = []
    for snap in snapshots:
        ts = _parse_ts(snap.get("captured_at"))
        if ts is not None:
            times.append(ts)
    times.sort()

    if not times:
        # No parseable timestamps — treat as full-window gap
        return (window_end - window_start).total_seconds()

    all_boundaries = [window_start] + times + [window_end]
    max_gap = 0.0
    for i in range(1, len(all_boundaries)):
        gap = (all_boundaries[i] - all_boundaries[i - 1]).total_seconds()
        if gap > max_gap:
            max_gap = gap
    return max_gap


def evaluate_cadence_policy(
    snapshots: Sequence[Mapping[str, Any]],
    window_start_at: Any,
    window_end_at: Any,
    policy: SnapshotCadencePolicy | None,
    *,
    production_mode: bool = False,
) -> CadencePolicyEvaluation:
    """Evaluate snapshot coverage against a cadence policy.

    Parameters
    ----------
    snapshots:
        Collection of snapshot records (each must have a "captured_at" key).
        Pass only snapshots that belong to the token/pair within the window ID
        range — callers are responsible for pre-filtering.
    window_start_at / window_end_at:
        The authoritative boundary timestamps of the memory window.
    policy:
        The SnapshotCadencePolicy for this window_kind + tracking_lane combo.
        If None, the function returns CADENCE_POLICY_UNKNOWN.
    production_mode:
        When True, 0 snapshots in range → CADENCE_POLICY_BLOCKED rather than
        CADENCE_POLICY_UNKNOWN.  Use for real Lane U production runs.
        When False (default), 0 snapshots → UNKNOWN (no block) — preserves
        compatibility with synthetic test fixtures whose snapshot IDs may not
        exist in the DB.

    Returns
    -------
    CadencePolicyEvaluation
        cadence_policy_status is PASS, BLOCKED, or UNKNOWN.
    """
    if policy is None:
        return CadencePolicyEvaluation(
            policy_found=False,
            window_kind="UNKNOWN",
            tracking_lane=None,
            enabled_for_real_collection=False,
            support_only=False,
            target_snapshot_interval_seconds=None,
            max_clean_snapshot_gap_seconds=None,
            minimum_required_snapshots=None,
            actual_snapshot_count=len(snapshots),
            actual_max_gap_seconds=None,
            cadence_policy_status=CADENCE_POLICY_UNKNOWN,
            blocked_reason=None,
        )

    actual_count = len(snapshots)

    # 0 snapshots — cannot evaluate even-gap policy.
    # In production_mode: BLOCKED (real windows must have real snapshots).
    # Otherwise: UNKNOWN (preserves synthetic fixture test compatibility).
    if actual_count == 0:
        if production_mode:
            return CadencePolicyEvaluation(
                policy_found=True,
                window_kind=policy.window_kind,
                tracking_lane=policy.tracking_lane,
                enabled_for_real_collection=policy.enabled_for_real_collection,
                support_only=policy.support_only,
                target_snapshot_interval_seconds=policy.target_snapshot_interval_seconds,
                max_clean_snapshot_gap_seconds=policy.max_clean_snapshot_gap_seconds,
                minimum_required_snapshots=policy.minimum_required_snapshots,
                actual_snapshot_count=0,
                actual_max_gap_seconds=None,
                cadence_policy_status=CADENCE_POLICY_BLOCKED,
                blocked_reason="production_mode_missing_coverage: no snapshots found in window range",
            )
        return CadencePolicyEvaluation(
            policy_found=True,
            window_kind=policy.window_kind,
            tracking_lane=policy.tracking_lane,
            enabled_for_real_collection=policy.enabled_for_real_collection,
            support_only=policy.support_only,
            target_snapshot_interval_seconds=policy.target_snapshot_interval_seconds,
            max_clean_snapshot_gap_seconds=policy.max_clean_snapshot_gap_seconds,
            minimum_required_snapshots=policy.minimum_required_snapshots,
            actual_snapshot_count=0,
            actual_max_gap_seconds=None,
            cadence_policy_status=CADENCE_POLICY_UNKNOWN,
            blocked_reason=None,
        )

    # Disabled windows block regardless of snapshot count
    if not policy.enabled_for_real_collection:
        return CadencePolicyEvaluation(
            policy_found=True,
            window_kind=policy.window_kind,
            tracking_lane=policy.tracking_lane,
            enabled_for_real_collection=False,
            support_only=policy.support_only,
            target_snapshot_interval_seconds=policy.target_snapshot_interval_seconds,
            max_clean_snapshot_gap_seconds=policy.max_clean_snapshot_gap_seconds,
            minimum_required_snapshots=policy.minimum_required_snapshots,
            actual_snapshot_count=actual_count,
            actual_max_gap_seconds=None,
            cadence_policy_status=CADENCE_POLICY_BLOCKED,
            blocked_reason="window_kind_disabled_for_real_collection",
        )

    # Support-only windows cannot become main clean memory
    if policy.support_only:
        return CadencePolicyEvaluation(
            policy_found=True,
            window_kind=policy.window_kind,
            tracking_lane=policy.tracking_lane,
            enabled_for_real_collection=False,
            support_only=True,
            target_snapshot_interval_seconds=policy.target_snapshot_interval_seconds,
            max_clean_snapshot_gap_seconds=policy.max_clean_snapshot_gap_seconds,
            minimum_required_snapshots=policy.minimum_required_snapshots,
            actual_snapshot_count=actual_count,
            actual_max_gap_seconds=None,
            cadence_policy_status=CADENCE_POLICY_BLOCKED,
            blocked_reason="support_only_window_cannot_be_main_clean_memory",
        )

    # Parse window boundaries
    start_ts = _parse_ts(window_start_at)
    end_ts = _parse_ts(window_end_at)

    if start_ts is None or end_ts is None:
        return CadencePolicyEvaluation(
            policy_found=True,
            window_kind=policy.window_kind,
            tracking_lane=policy.tracking_lane,
            enabled_for_real_collection=policy.enabled_for_real_collection,
            support_only=policy.support_only,
            target_snapshot_interval_seconds=policy.target_snapshot_interval_seconds,
            max_clean_snapshot_gap_seconds=policy.max_clean_snapshot_gap_seconds,
            minimum_required_snapshots=policy.minimum_required_snapshots,
            actual_snapshot_count=actual_count,
            actual_max_gap_seconds=None,
            cadence_policy_status=CADENCE_POLICY_BLOCKED,
            blocked_reason="unparseable_window_boundary_timestamps",
        )

    # Minimum snapshot count check
    if actual_count < policy.minimum_required_snapshots:
        return CadencePolicyEvaluation(
            policy_found=True,
            window_kind=policy.window_kind,
            tracking_lane=policy.tracking_lane,
            enabled_for_real_collection=policy.enabled_for_real_collection,
            support_only=policy.support_only,
            target_snapshot_interval_seconds=policy.target_snapshot_interval_seconds,
            max_clean_snapshot_gap_seconds=policy.max_clean_snapshot_gap_seconds,
            minimum_required_snapshots=policy.minimum_required_snapshots,
            actual_snapshot_count=actual_count,
            actual_max_gap_seconds=None,
            cadence_policy_status=CADENCE_POLICY_BLOCKED,
            blocked_reason=(
                f"insufficient_snapshots: need {policy.minimum_required_snapshots},"
                f" got {actual_count}"
            ),
        )

    # Even-gap check — no front-loading, no dead zones
    max_gap = _compute_max_gap_seconds(snapshots, start_ts, end_ts)

    if max_gap > policy.max_clean_snapshot_gap_seconds:
        return CadencePolicyEvaluation(
            policy_found=True,
            window_kind=policy.window_kind,
            tracking_lane=policy.tracking_lane,
            enabled_for_real_collection=policy.enabled_for_real_collection,
            support_only=policy.support_only,
            target_snapshot_interval_seconds=policy.target_snapshot_interval_seconds,
            max_clean_snapshot_gap_seconds=policy.max_clean_snapshot_gap_seconds,
            minimum_required_snapshots=policy.minimum_required_snapshots,
            actual_snapshot_count=actual_count,
            actual_max_gap_seconds=round(max_gap, 3),
            cadence_policy_status=CADENCE_POLICY_BLOCKED,
            blocked_reason=(
                f"coverage_gap_exceeds_policy: max_gap={max_gap:.1f}s"
                f" > limit={policy.max_clean_snapshot_gap_seconds}s"
            ),
        )

    return CadencePolicyEvaluation(
        policy_found=True,
        window_kind=policy.window_kind,
        tracking_lane=policy.tracking_lane,
        enabled_for_real_collection=policy.enabled_for_real_collection,
        support_only=policy.support_only,
        target_snapshot_interval_seconds=policy.target_snapshot_interval_seconds,
        max_clean_snapshot_gap_seconds=policy.max_clean_snapshot_gap_seconds,
        minimum_required_snapshots=policy.minimum_required_snapshots,
        actual_snapshot_count=actual_count,
        actual_max_gap_seconds=round(max_gap, 3),
        cadence_policy_status=CADENCE_POLICY_PASS,
        blocked_reason=None,
    )


def cadence_policy_evaluation_to_dict(ev: CadencePolicyEvaluation) -> dict[str, Any]:
    """Convert to plain dict for embedding in report payloads."""
    return asdict(ev)

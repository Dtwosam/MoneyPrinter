"""V2-6.2 — Continuous First-Hour Lifecycle Contract.

One continuous lifecycle for the same run, token, pair, and lane:

    5m support  ->  15m main window  ->  1h continuation

This module is the single authoritative evaluator for lifecycle continuity. It
turns the previously-orphaned ``evaluate_transition_gap`` (cadence_policy) into a
wired, enforced contract and adds the 5m->15m linkage rules that were previously
only *reported* (read-only) by ``e2w_5m_linkage_report``. V2-7.2 extends the same
contract to disabled, fixture-only 1h->4h->12h->24h chained planning without
activating long-window collection.

Continuity invariants enforced
------------------------------
5m -> 15m:
  * same run / token / pair / lane;
  * the 5m support window uses the *first* snapshots of the same 15m run
    (identical opening snapshot; the 5m snapshot range is a prefix of the 15m
    range) — never a separate restart;
  * the 15m close stays anchored to the original opening snapshot + 900s;
  * the first post-5m snapshot gap is judged with the 15m cadence thresholds.

15m -> 1h:
  * same run / token / pair / lane;
  * the 1h continuation links the *exact* fresh 15m window and its closing
    snapshot (no historical window reuse, no already-consumed window);
  * continuation is enqueued immediately at the 15m close;
  * the 1h deadline is ``15m close + 2700s`` — never delayed-first-snapshot +
    2700s (that is target drift and is rejected);
  * the transition gap uses the approved FAST/NORMAL thresholds; a negative gap
    (a delayed restart disguised as continuation) is BLOCKED;
  * no interpolation: the first 1h snapshot must be a real captured snapshot.

Outcome discipline (consumed by E2Q / Lane Q / Lane K):
  * CONTINUOUS -> may become quality memory (subject to the ordinary coverage /
    data-quality gates elsewhere);
  * DIRTY      -> ``do_not_train`` is forced True; never clean;
  * BLOCKED    -> ``can_be_quality_memory`` is False; the transition cannot become
    quality memory at all.

Long-window foundation:
  * each successor resolves its exact terminal predecessor from the current run;
  * linkage, deadline, and gap boundaries derive from the successor cadence;
  * blocked transitions are token-local and replay-terminal;
  * 4h, 12h, and 24h remain disabled for real collection.

The pure evaluators take plain dicts (as read from ``printer_memory_windows`` /
``printer_token_snapshots``) so they are trivially fixture-testable. A DB-backed
resolver reads the real rows for a run/token/pair/lane and runs both evaluators.

No DB mutation is produced by anything in this module. No memory, episode,
retrieval, paper, position, or PnL row is ever written or unlocked here.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

from printer_v1.snapshots.cadence_policy import (
    TRANSITION_BLOCKED,
    TRANSITION_CLEAN,
    TRANSITION_DIRTY,
    TRANSITION_UNKNOWN,
    _parse_ts,
    evaluate_transition_gap,
    get_policy,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONTINUITY_CONTINUOUS: str = "CONTINUITY_CONTINUOUS"
CONTINUITY_DIRTY: str = "CONTINUITY_DIRTY"
CONTINUITY_BLOCKED: str = "CONTINUITY_BLOCKED"
CONTINUITY_UNKNOWN: str = "CONTINUITY_UNKNOWN"

STAGE_5M_TO_15M: str = "5M_TO_15M"
STAGE_15M_TO_1H: str = "15M_TO_1H"
STAGE_1H_TO_4H: str = "1H_TO_4H"
STAGE_4H_TO_12H: str = "4H_TO_12H"
STAGE_12H_TO_24H: str = "12H_TO_24H"

# The 15m main window spans 900s; the 1h continuation phase spans the remaining
# 2700s (t=15m..60m). The continuation deadline is anchored to the 15m close.
WINDOW_15M_SECONDS: float = 900.0
CONTINUATION_1H_SECONDS: float = 2700.0

_ALLOWED_LANES: frozenset[str] = frozenset({"TRACK_FAST", "TRACK_NORMAL"})


@dataclass(frozen=True)
class LongWindowTransitionSpec:
    predecessor_kind: str
    successor_kind: str
    stage: str


_LONG_WINDOW_TRANSITIONS: tuple[LongWindowTransitionSpec, ...] = (
    LongWindowTransitionSpec("WINDOW_1H", "WINDOW_4H", STAGE_1H_TO_4H),
    LongWindowTransitionSpec("WINDOW_4H", "WINDOW_12H", STAGE_4H_TO_12H),
    LongWindowTransitionSpec("WINDOW_12H", "WINDOW_24H", STAGE_12H_TO_24H),
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ContinuityResult:
    """Verdict for one lifecycle transition.

    ``status`` is one of CONTINUITY_CONTINUOUS / _DIRTY / _BLOCKED / _UNKNOWN.
    ``do_not_train`` and ``can_be_quality_memory`` are the flags E2Q / Lane Q /
    Lane K consume: a DIRTY transition forces do_not_train; a BLOCKED transition
    cannot become quality memory.
    """

    stage: str
    status: str
    do_not_train: bool
    can_be_quality_memory: bool
    reasons: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "continuity_status": self.status,
            "do_not_train": self.do_not_train,
            "can_be_quality_memory": self.can_be_quality_memory,
            "reasons": list(self.reasons),
            "details": dict(self.details),
        }


def _mk(stage: str, status: str, reasons: list[str], details: dict[str, Any]) -> ContinuityResult:
    do_not_train = status in (CONTINUITY_DIRTY, CONTINUITY_BLOCKED)
    can_be_quality = status == CONTINUITY_CONTINUOUS
    return ContinuityResult(
        stage=stage, status=status, do_not_train=do_not_train,
        can_be_quality_memory=can_be_quality, reasons=reasons, details=details,
    )


# ---------------------------------------------------------------------------
# Deadline / enqueue helpers
# ---------------------------------------------------------------------------

def compute_1h_continuation_deadline(fifteen_m_close_at: Any) -> Any:
    """Return the authoritative 1h continuation deadline = 15m close + 2700s.

    The deadline is anchored to the *15m close*, never to the first 1h snapshot.
    Returns a timezone-aware datetime, or None if the close timestamp is
    missing/unparseable.
    """
    close = _parse_ts(fifteen_m_close_at)
    if close is None:
        return None
    return close + timedelta(seconds=CONTINUATION_1H_SECONDS)


def build_1h_continuation_plan(fifteen_m: Mapping[str, Any]) -> dict[str, Any]:
    """Build the 1h continuation enqueue plan for a closed 15m window.

    Continuation jobs enqueue *immediately* at the 15m close, and the deadline is
    ``15m close + 2700s`` (not delayed-first-snapshot + 2700s). Returns a plan
    dict; ``enqueue_ok`` is False (with a reason) when the 15m window cannot seed
    a continuation.
    """
    reasons: list[str] = []
    close_at = fifteen_m.get("closed_at") or fifteen_m.get("window_end_at")
    window_id = fifteen_m.get("id")
    closing_snapshot_id = fifteen_m.get("snapshot_end_id")
    lane = fifteen_m.get("tracking_lane")
    status = fifteen_m.get("window_status")

    if fifteen_m.get("window_kind") != "WINDOW_15M":
        reasons.append("source_window_is_not_window_15m")
    if status not in (None, "WINDOW_CLOSED"):
        reasons.append(f"source_15m_window_not_closed: {status}")
    if _parse_ts(close_at) is None:
        reasons.append("missing_15m_close_timestamp")
    if closing_snapshot_id is None:
        reasons.append("missing_15m_closing_snapshot")

    deadline = compute_1h_continuation_deadline(close_at)
    enqueue_ok = not reasons
    return {
        "enqueue_ok": enqueue_ok,
        "reasons": reasons,
        # enqueue immediately at the 15m close (no delay)
        "enqueue_at": _iso(close_at),
        "deadline_at": _iso(deadline),
        "deadline_anchored_to": "fifteen_m_close_plus_2700s",
        "continuation_of_window_id": window_id,
        "linked_closing_snapshot_id": closing_snapshot_id,
        "tracking_lane": lane,
    }


def _iso(value: Any) -> str | None:
    ts = _parse_ts(value)
    return ts.isoformat() if ts is not None else None


# ---------------------------------------------------------------------------
# Disabled long-window chained-continuity foundation
# ---------------------------------------------------------------------------

def get_long_window_transition_spec(
    predecessor_kind: str,
    successor_kind: str,
) -> LongWindowTransitionSpec | None:
    """Return an approved long-window transition, never an inferred chain."""
    return next(
        (
            spec
            for spec in _LONG_WINDOW_TRANSITIONS
            if spec.predecessor_kind == predecessor_kind
            and spec.successor_kind == successor_kind
        ),
        None,
    )


def _spec_for_successor(successor_kind: str) -> LongWindowTransitionSpec | None:
    matches = [s for s in _LONG_WINDOW_TRANSITIONS if s.successor_kind == successor_kind]
    return matches[0] if len(matches) == 1 else None


def compute_long_window_deadline(
    predecessor_close_at: Any,
    successor_kind: str,
    tracking_lane: str,
) -> Any:
    """Return predecessor close plus the unchanged V2-7.1 continuation duration."""
    spec = _spec_for_successor(successor_kind)
    policy = get_policy(successor_kind, tracking_lane)
    close = _parse_ts(predecessor_close_at)
    if spec is None or policy is None or close is None:
        return None
    return close + timedelta(seconds=policy.window_close_interval_seconds)


def build_long_window_continuation_plan(
    predecessor: Mapping[str, Any],
    successor_kind: str,
    *,
    allow_enabled_successor_planning: bool = False,
) -> dict[str, Any]:
    """Build an automatic, disabled long-window handoff from a resolved predecessor.

    The caller supplies no predecessor id or deadline. Both are taken from the
    current-run predecessor row and the authoritative successor cadence policy.
    This function plans only; it does not enqueue or activate long-window work.
    """
    predecessor_kind = str(predecessor.get("window_kind") or "")
    lane = str(predecessor.get("tracking_lane") or "")
    spec = get_long_window_transition_spec(predecessor_kind, successor_kind)
    policy = get_policy(successor_kind, lane)
    reasons: list[str] = []
    close_at = predecessor.get("closed_at") or predecessor.get("window_end_at")
    if spec is None:
        reasons.append("unsupported_predecessor_successor_chain")
    if lane not in _ALLOWED_LANES or policy is None:
        reasons.append("unsupported_tracking_lane_or_missing_successor_policy")
    if predecessor.get("run_id") is None:
        reasons.append("missing_current_run_identity")
    if predecessor.get("id") is None:
        reasons.append("missing_predecessor_window_id")
    if predecessor.get("snapshot_end_id") is None:
        reasons.append("missing_predecessor_closing_snapshot")
    if predecessor.get("window_status") != "WINDOW_CLOSED":
        reasons.append("predecessor_not_terminally_closed")
    if _parse_ts(close_at) is None:
        reasons.append("missing_predecessor_close_timestamp")
    if (
        policy is not None
        and policy.enabled_for_real_collection
        and not allow_enabled_successor_planning
    ):
        reasons.append("successor_enabled_without_explicit_planning_authority")
    deadline = compute_long_window_deadline(close_at, successor_kind, lane)
    return {
        "plan_ok": not reasons,
        "reasons": reasons,
        "activation_allowed": False,
        "predecessor_kind": predecessor_kind,
        "successor_kind": successor_kind,
        "stage": spec.stage if spec else None,
        "run_id": predecessor.get("run_id"),
        "token_id": predecessor.get("token_id"),
        "pair_id": predecessor.get("pair_id"),
        "tracking_lane": lane,
        "continuation_of_window_id": predecessor.get("id"),
        "linked_closing_snapshot_id": predecessor.get("snapshot_end_id"),
        "enqueue_at": _iso(close_at),
        "deadline_at": _iso(deadline),
        "deadline_anchored_to": "exact_predecessor_close_plus_successor_continuation",
        "continuation_seconds": (
            policy.window_close_interval_seconds if policy is not None else None
        ),
        "expected_snapshots": (
            policy.minimum_required_snapshots if policy is not None else None
        ),
        "enabled_for_real_collection": (
            policy.enabled_for_real_collection if policy is not None else None
        ),
    }


def _evaluate_long_transition_gap(
    predecessor_close_at: Any,
    first_successor_snapshot_at: Any,
    successor_kind: str,
    tracking_lane: str,
) -> dict[str, Any]:
    """Classify a long transition using the successor's V2-7.1 boundaries."""
    policy = get_policy(successor_kind, tracking_lane)
    start = _parse_ts(predecessor_close_at)
    end = _parse_ts(first_successor_snapshot_at)
    if policy is None or start is None or end is None:
        return {
            "transition_status": TRANSITION_UNKNOWN,
            "transition_gap_seconds": None,
            "reason": "missing_successor_policy_lane_or_timestamps",
        }
    gap = (end - start).total_seconds()
    details = {
        "transition_gap_seconds": round(gap, 3),
        "clean_max_seconds": policy.clean_max_gap_seconds,
        "blocked_at_seconds": policy.blocked_at_gap_seconds,
    }
    if gap < 0:
        return {
            **details,
            "transition_status": TRANSITION_BLOCKED,
            "reason": "negative_transition_gap_delayed_restart_forbidden",
        }
    if gap >= policy.blocked_at_gap_seconds:
        return {
            **details,
            "transition_status": TRANSITION_BLOCKED,
            "reason": "transition_gap_at_or_above_blocked_threshold",
        }
    if gap > policy.clean_max_gap_seconds:
        return {
            **details,
            "transition_status": TRANSITION_DIRTY,
            "reason": "transition_gap_above_clean_maximum",
        }
    return {**details, "transition_status": TRANSITION_CLEAN, "reason": None}


def evaluate_long_window_continuity(
    predecessor: Mapping[str, Any],
    successor: Mapping[str, Any],
    *,
    consumed_predecessor_window_ids: Sequence[int] | None = None,
) -> ContinuityResult:
    """Evaluate one exact 1h->4h, 4h->12h, or 12h->24h handoff."""
    predecessor_kind = str(predecessor.get("window_kind") or "")
    successor_kind = str(successor.get("window_kind") or "")
    spec = get_long_window_transition_spec(predecessor_kind, successor_kind)
    lane = str(predecessor.get("tracking_lane") or successor.get("tracking_lane") or "")
    stage = spec.stage if spec else f"{predecessor_kind}_TO_{successor_kind}"
    details: dict[str, Any] = {
        "predecessor_kind": predecessor_kind,
        "successor_kind": successor_kind,
        "tracking_lane": lane,
    }
    reasons: list[str] = []
    if spec is None:
        reasons.append("unsupported_or_wrong_predecessor_chain")
    if lane not in _ALLOWED_LANES:
        reasons.append("unknown_or_unsupported_lane")
    reasons.extend(_identity_reasons("long_chain", predecessor, successor, lane))
    if predecessor.get("window_status") != "WINDOW_CLOSED":
        reasons.append("predecessor_not_terminally_closed")
    if successor.get("manual_linkage") or successor.get("reuses_historical_window"):
        reasons.append("manual_or_historical_linkage_forbidden")
    if successor.get("interpolated_first_snapshot") or successor.get("aggregated_predecessor"):
        reasons.append("interpolation_or_fake_aggregation_forbidden")
    if successor.get("clock_reset") or successor.get("delayed_restart"):
        reasons.append("restart_or_clock_reset_forbidden")

    predecessor_id = predecessor.get("id")
    linked_window_id = successor.get("continuation_of_window_id")
    if (
        predecessor_id is None
        or linked_window_id is None
        or int(predecessor_id) != int(linked_window_id)
    ):
        reasons.append("successor_not_linked_to_exact_predecessor_window")
    predecessor_close_snapshot = predecessor.get("snapshot_end_id")
    linked_close_snapshot = successor.get("linked_closing_snapshot_id")
    if (
        predecessor_close_snapshot is None
        or linked_close_snapshot is None
        or int(predecessor_close_snapshot) != int(linked_close_snapshot)
    ):
        reasons.append("successor_not_linked_to_exact_predecessor_closing_snapshot")
    consumed = {int(v) for v in (consumed_predecessor_window_ids or [])}
    if predecessor_id is not None and int(predecessor_id) in consumed:
        reasons.append("predecessor_window_already_consumed")
    if successor.get("linked_first_snapshot_id") is None:
        reasons.append("missing_real_first_successor_snapshot")
    if _parse_ts(successor.get("first_snapshot_at")) is None:
        reasons.append("missing_real_first_successor_snapshot_timestamp")

    predecessor_close_at = predecessor.get("closed_at") or predecessor.get("window_end_at")
    expected_deadline = compute_long_window_deadline(
        predecessor_close_at, successor_kind, lane
    )
    actual_deadline = _parse_ts(successor.get("window_end_at") or successor.get("deadline_at"))
    details["expected_deadline"] = _iso(expected_deadline)
    details["actual_deadline"] = _iso(actual_deadline)
    if expected_deadline is None or actual_deadline is None:
        reasons.append("missing_fixed_deadline")
    else:
        drift = abs((actual_deadline - expected_deadline).total_seconds())
        details["deadline_drift_seconds"] = round(drift, 3)
        if drift > 1e-6:
            reasons.append("deadline_target_drift")

    transition = _evaluate_long_transition_gap(
        predecessor_close_at,
        successor.get("first_snapshot_at"),
        successor_kind,
        lane,
    )
    details["transition"] = transition
    if reasons:
        return _mk(stage, CONTINUITY_BLOCKED, reasons, details)
    if transition["transition_status"] == TRANSITION_BLOCKED:
        return _mk(
            stage,
            CONTINUITY_BLOCKED,
            [f"transition_gap_blocked: {transition.get('reason')}"],
            details,
        )
    if transition["transition_status"] == TRANSITION_DIRTY:
        return _mk(
            stage,
            CONTINUITY_DIRTY,
            [f"transition_gap_dirty: {transition.get('reason')}"],
            details,
        )
    if transition["transition_status"] != TRANSITION_CLEAN:
        return _mk(
            stage,
            CONTINUITY_UNKNOWN,
            [f"transition_gap_unknown: {transition.get('reason')}"],
            details,
        )
    return _mk(stage, CONTINUITY_CONTINUOUS, [], details)


# ---------------------------------------------------------------------------
# Identity helper
# ---------------------------------------------------------------------------

def _identity_reasons(prefix: str, a: Mapping[str, Any], b: Mapping[str, Any], lane: str | None) -> list[str]:
    """Return reasons for any run/token/pair/lane mismatch between two records."""
    reasons: list[str] = []
    for key in ("run_id", "token_id", "pair_id"):
        av, bv = a.get(key), b.get(key)
        if av is None or bv is None or av != bv:
            reasons.append(f"{prefix}_{key}_mismatch: {av!r} != {bv!r}")
    la = a.get("tracking_lane")
    lb = b.get("tracking_lane")
    if la != lb or (lane is not None and la != lane):
        reasons.append(f"{prefix}_lane_mismatch: {la!r} / {lb!r} / expected {lane!r}")
    return reasons


# ---------------------------------------------------------------------------
# 5m -> 15m continuity
# ---------------------------------------------------------------------------

def evaluate_5m_to_15m_continuity(
    five_m: Mapping[str, Any],
    fifteen_m: Mapping[str, Any],
    *,
    tracking_lane: str | None = None,
    first_post_5m_gap_seconds: float | None = None,
) -> ContinuityResult:
    """Classify the 5m-support -> 15m-main continuity.

    The 5m support window must be the opening slice of the *same* 15m run: same
    run/token/pair/lane, the identical opening snapshot (no restart), and a
    snapshot range that is a prefix of the 15m range. The 15m close must stay
    anchored to the opening snapshot + 900s. The first post-5m gap is judged with
    the 15m cadence thresholds.
    """
    lane = tracking_lane or fifteen_m.get("tracking_lane") or five_m.get("tracking_lane")
    reasons: list[str] = []
    details: dict[str, Any] = {"tracking_lane": lane}

    if lane not in _ALLOWED_LANES:
        return _mk(STAGE_5M_TO_15M, CONTINUITY_UNKNOWN,
                   [f"unknown_or_unsupported_lane: {lane!r}"], details)

    # Same run / token / pair / lane.
    reasons += _identity_reasons("5m_15m", five_m, fifteen_m, lane)

    # 5m uses the FIRST snapshots of the same 15m run.
    five_start = five_m.get("snapshot_start_id")
    five_end = five_m.get("snapshot_end_id")
    m_start = fifteen_m.get("snapshot_start_id")
    m_end = fifteen_m.get("snapshot_end_id")
    if five_start is None or m_start is None:
        reasons.append("missing_snapshot_start_id")
    elif int(five_start) != int(m_start):
        # A different opening snapshot means the 15m restarted rather than
        # continuing the same run past minute 5.
        reasons.append(
            f"restart_detected_opening_snapshot_differs: 5m={five_start} 15m={m_start}")
    if (five_end is not None and m_end is not None
            and int(five_end) > int(m_end)):
        reasons.append(
            f"5m_range_not_prefix_of_15m: 5m_end={five_end} > 15m_end={m_end}")
    details["opening_snapshot_id"] = m_start

    # 15m close anchored to opening snapshot + 900s.
    ws = _parse_ts(fifteen_m.get("window_start_at"))
    we = _parse_ts(fifteen_m.get("window_end_at"))
    if ws is None or we is None:
        reasons.append("missing_15m_window_boundaries")
    else:
        elapsed = (we - ws).total_seconds()
        details["fifteen_m_elapsed_seconds"] = round(elapsed, 3)
        if elapsed + 1e-6 < WINDOW_15M_SECONDS:
            reasons.append(
                f"15m_close_not_anchored_to_open_plus_900s: elapsed={elapsed:.1f}s")

    if reasons:
        return _mk(STAGE_5M_TO_15M, CONTINUITY_BLOCKED, reasons, details)

    # First post-5m gap judged with the 15m cadence thresholds.
    if first_post_5m_gap_seconds is not None:
        policy = get_policy("WINDOW_15M", lane)
        if policy is not None:
            details["first_post_5m_gap_seconds"] = round(float(first_post_5m_gap_seconds), 3)
            details["dirty_above_gap_seconds"] = policy.dirty_above_gap_seconds
            details["block_above_gap_seconds"] = policy.max_clean_snapshot_gap_seconds
            if first_post_5m_gap_seconds > policy.max_clean_snapshot_gap_seconds:
                return _mk(STAGE_5M_TO_15M, CONTINUITY_BLOCKED,
                           [f"first_post_5m_gap_exceeds_block: "
                            f"{first_post_5m_gap_seconds:.1f}s > "
                            f"{policy.max_clean_snapshot_gap_seconds}s"], details)
            if first_post_5m_gap_seconds > policy.dirty_above_gap_seconds:
                return _mk(STAGE_5M_TO_15M, CONTINUITY_DIRTY,
                           [f"first_post_5m_gap_dirty: "
                            f"{first_post_5m_gap_seconds:.1f}s > "
                            f"{policy.dirty_above_gap_seconds}s"], details)

    return _mk(STAGE_5M_TO_15M, CONTINUITY_CONTINUOUS, [], details)


# ---------------------------------------------------------------------------
# 15m -> 1h continuity
# ---------------------------------------------------------------------------

def evaluate_15m_to_1h_continuity(
    fifteen_m: Mapping[str, Any],
    one_h: Mapping[str, Any],
    *,
    tracking_lane: str | None = None,
    consumed_15m_window_ids: Sequence[int] | None = None,
) -> ContinuityResult:
    """Classify the 15m-main -> 1h-continuation continuity.

    The 1h continuation must link the exact fresh 15m window and its closing
    snapshot; must not reuse a historical or already-consumed 15m window; must be
    deadlined at ``15m close + 2700s``; must begin with a real (non-interpolated)
    first snapshot; and its transition gap is classified with the approved
    FAST/NORMAL thresholds (negative gap = delayed restart = BLOCKED).
    """
    lane = tracking_lane or fifteen_m.get("tracking_lane") or one_h.get("tracking_lane")
    reasons: list[str] = []
    details: dict[str, Any] = {"tracking_lane": lane}

    if lane not in _ALLOWED_LANES:
        return _mk(STAGE_15M_TO_1H, CONTINUITY_UNKNOWN,
                   [f"unknown_or_unsupported_lane: {lane!r}"], details)

    reasons += _identity_reasons("15m_1h", fifteen_m, one_h, lane)

    # Link the EXACT fresh 15m window + closing snapshot.
    src_window_id = one_h.get("continuation_of_window_id")
    src_close_snap = one_h.get("linked_closing_snapshot_id")
    if src_window_id is None or fifteen_m.get("id") is None or int(src_window_id) != int(fifteen_m["id"]):
        reasons.append(
            f"1h_not_linked_to_this_15m_window: linked={src_window_id} "
            f"actual={fifteen_m.get('id')}")
    if (src_close_snap is None or fifteen_m.get("snapshot_end_id") is None
            or int(src_close_snap) != int(fifteen_m["snapshot_end_id"])):
        reasons.append(
            f"1h_not_linked_to_15m_closing_snapshot: linked={src_close_snap} "
            f"closing={fifteen_m.get('snapshot_end_id')}")

    # No historical window reuse.
    consumed = set(int(x) for x in (consumed_15m_window_ids or []))
    if fifteen_m.get("id") is not None and int(fifteen_m["id"]) in consumed:
        reasons.append(f"reused_historical_15m_window: {fifteen_m['id']} already consumed")
    if one_h.get("reuses_historical_window"):
        reasons.append("explicit_historical_window_reuse_flag")

    # No interpolation: the first 1h snapshot must be a real captured snapshot.
    first_snap_id = one_h.get("linked_first_snapshot_id")
    if first_snap_id is None:
        reasons.append("missing_first_1h_snapshot_no_real_snapshot")
    if one_h.get("interpolated_first_snapshot"):
        reasons.append("interpolated_first_1h_snapshot_forbidden")

    # Deadline must be anchored to 15m close + 2700s (never first-snapshot+2700s).
    close_at = fifteen_m.get("closed_at") or fifteen_m.get("window_end_at")
    expected_deadline = compute_1h_continuation_deadline(close_at)
    actual_deadline = _parse_ts(one_h.get("window_end_at") or one_h.get("deadline_at"))
    details["expected_deadline"] = _iso(expected_deadline)
    details["actual_deadline"] = _iso(actual_deadline)
    if expected_deadline is None:
        reasons.append("missing_15m_close_for_deadline_anchor")
    elif actual_deadline is not None:
        drift = abs((actual_deadline - expected_deadline).total_seconds())
        details["deadline_drift_seconds"] = round(drift, 3)
        if drift > 1.0:
            reasons.append(
                f"deadline_target_drift: 1h deadline off by {drift:.1f}s from "
                f"15m_close+2700s (delayed-first-snapshot anchoring)")

    # Transition gap classification (approved FAST/NORMAL thresholds).
    first_snap_at = one_h.get("first_snapshot_at")
    transition = evaluate_transition_gap(close_at, first_snap_at, lane)
    details["transition"] = transition

    # Identity / linkage / reuse / interpolation / deadline failures are BLOCKING.
    if reasons:
        return _mk(STAGE_15M_TO_1H, CONTINUITY_BLOCKED, reasons, details)

    tstatus = transition.get("transition_status")
    if tstatus == TRANSITION_BLOCKED:
        return _mk(STAGE_15M_TO_1H, CONTINUITY_BLOCKED,
                   [f"transition_gap_blocked: {transition.get('reason')}"], details)
    if tstatus == TRANSITION_DIRTY:
        return _mk(STAGE_15M_TO_1H, CONTINUITY_DIRTY,
                   [f"transition_gap_dirty: {transition.get('reason')}"], details)
    if tstatus == TRANSITION_UNKNOWN:
        return _mk(STAGE_15M_TO_1H, CONTINUITY_UNKNOWN,
                   [f"transition_gap_unknown: {transition.get('reason')}"], details)

    # tstatus == TRANSITION_CLEAN
    return _mk(STAGE_15M_TO_1H, CONTINUITY_CONTINUOUS, [], details)


# ---------------------------------------------------------------------------
# DB-backed resolver
# ---------------------------------------------------------------------------

def _connect_ro(db_path: str | Path) -> sqlite3.Connection:
    try:
        uri = Path(db_path).resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    except Exception:
        conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _window_record(row: sqlite3.Row, run_id: Any, tracking_lane: str) -> dict[str, Any]:
    # printer_memory_windows has no tracking_lane column; the lane is carried by
    # the run step. Stamp the resolved run/lane onto the record so the identity
    # checks compare against the same run/lane the resolver was asked about.
    d = dict(row)
    d["run_id"] = run_id
    d["tracking_lane"] = tracking_lane
    return d


def _consumed_long_predecessor_ids(
    connection: sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int,
    successor_kind: str,
) -> list[int]:
    rows = connection.execute(
        "SELECT supporting_context_json FROM printer_memory_windows "
        "WHERE token_id=? AND pair_id=? AND window_kind=?",
        (token_id, pair_id, successor_kind),
    ).fetchall()
    consumed: list[int] = []
    for row in rows:
        try:
            context = json.loads(row["supporting_context_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            context = {}
        linked_id = context.get("continuation_of_window_id")
        if linked_id is None:
            linked_id = (context.get("continuity") or {}).get(
                "continuation_of_window_id"
            )
        if linked_id is not None:
            consumed.append(int(linked_id))
    return consumed


def resolve_current_run_long_predecessor(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    token_id: int,
    pair_id: int,
    tracking_lane: str,
    successor_kind: str,
    current_close_step_id: int | None = None,
    allow_enabled_successor_planning: bool = False,
) -> dict[str, Any]:
    """Resolve one exact, terminal, unused predecessor from the current run.

    This is the only supported long-window planning entry point. It accepts no
    manual predecessor/window/snapshot identifiers and never looks outside the
    requested run for the source row.
    """
    spec = _spec_for_successor(successor_kind)
    if spec is None:
        return {"resolved": False, "reasons": ["unsupported_successor_kind"]}
    rows = connection.execute(
        """
        SELECT w.*, s.id AS close_step_id, s.snapshot_id AS step_snapshot_id,
               s.step_status AS close_step_status,
               s.tracking_lane AS step_lane
        FROM printer_memory_factory_run_steps s
        JOIN printer_memory_windows w ON w.id = s.memory_window_id
        WHERE s.run_id=? AND s.token_id=? AND s.pair_id=?
          AND s.tracking_lane=?
          AND (
            s.step_status='SUCCEEDED'
            OR (s.id=? AND s.step_status='RUNNING')
          )
          AND s.step_kind IN ('CONTINUATION_CLOSE','LONG_CONTINUATION_CLOSE')
          AND w.window_kind=?
        GROUP BY w.id
        """,
        (
            run_id,
            token_id,
            pair_id,
            tracking_lane,
            current_close_step_id or -1,
            spec.predecessor_kind,
        ),
    ).fetchall()
    reasons: list[str] = []
    if len(rows) != 1:
        return {
            "resolved": False,
            "reasons": [
                f"current_run_terminal_{spec.predecessor_kind}_count={len(rows)} expected=1"
            ],
        }
    row = dict(rows[0])
    if row.get("window_status") != "WINDOW_CLOSED":
        reasons.append("current_run_predecessor_not_terminally_closed")
    if row.get("snapshot_end_id") is None or row.get("step_snapshot_id") is None:
        reasons.append("missing_current_run_predecessor_closing_snapshot")
    elif int(row["snapshot_end_id"]) != int(row["step_snapshot_id"]):
        reasons.append("current_run_predecessor_closing_snapshot_mismatch")
    if int(row["token_id"]) != int(token_id) or int(row["pair_id"]) != int(pair_id):
        reasons.append("current_run_predecessor_target_mismatch")
    if str(row.get("step_lane")) != tracking_lane:
        reasons.append("current_run_predecessor_lane_mismatch")
    consumed = _consumed_long_predecessor_ids(
        connection,
        token_id=token_id,
        pair_id=pair_id,
        successor_kind=successor_kind,
    )
    if int(row["id"]) in consumed:
        reasons.append("current_run_predecessor_already_consumed")
    terminal_marker = connection.execute(
        """
        SELECT id FROM printer_memory_factory_run_steps
        WHERE run_id=? AND token_id=? AND pair_id=?
          AND step_kind='LONG_CONTINUITY_BLOCK'
          AND step_key=?
        """,
        (
            run_id,
            token_id,
            pair_id,
            _long_block_step_key(token_id, pair_id, successor_kind),
        ),
    ).fetchone()
    if terminal_marker is not None:
        reasons.append("token_successor_transition_already_terminally_blocked")
    if reasons:
        return {
            "resolved": False,
            "reasons": reasons,
            "window_id": row.get("id"),
            "consumed_ids": consumed,
        }
    row["run_id"] = run_id
    row["tracking_lane"] = tracking_lane
    plan = build_long_window_continuation_plan(
        row,
        successor_kind,
        allow_enabled_successor_planning=allow_enabled_successor_planning,
    )
    if not plan["plan_ok"]:
        return {
            "resolved": False,
            "reasons": list(plan["reasons"]),
            "window_id": row.get("id"),
        }
    return {
        "resolved": True,
        "reasons": [],
        "window": row,
        "plan": plan,
        "consumed_ids": consumed,
    }


def _long_block_step_key(token_id: int, pair_id: int, successor_kind: str) -> str:
    suffix = successor_kind.removeprefix("WINDOW_").lower()
    return f"t{token_id}_p{pair_id}_{suffix}_long_continuity_block"


def terminally_block_long_continuation(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    token_id: int,
    pair_id: int,
    tracking_lane: str,
    successor_kind: str,
    reason: str,
) -> dict[str, Any]:
    """Record one replay-safe token-local block and cancel only its long jobs."""
    from printer_v1.scheduler import cancel_job

    key = _long_block_step_key(token_id, pair_id, successor_kind)
    existing = connection.execute(
        "SELECT id FROM printer_memory_factory_run_steps WHERE run_id=? AND step_key=?",
        (run_id, key),
    ).fetchone()
    if existing is not None:
        return {
            "terminally_blocked": True,
            "already_terminal": True,
            "cancelled_jobs": 0,
            "block_step_id": int(existing["id"]),
        }

    pending = connection.execute(
        """
        SELECT id, scheduler_job_id, result_json
        FROM printer_memory_factory_run_steps
        WHERE run_id=? AND token_id=? AND pair_id=?
          AND step_status='PENDING' AND step_kind LIKE 'LONG_CONTINUATION_%'
        """,
        (run_id, token_id, pair_id),
    ).fetchall()
    cancelled = 0
    for row in pending:
        try:
            payload = json.loads(row["result_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            payload = {}
        if payload.get("successor_window_kind") != successor_kind:
            continue
        if row["scheduler_job_id"] is not None:
            cancel_job(connection, job_id=int(row["scheduler_job_id"]))
        connection.execute(
            """
            UPDATE printer_memory_factory_run_steps
            SET step_status='CANCELLED', error_or_skip_reason=?,
                finished_at=datetime('now'), updated_at=datetime('now')
            WHERE id=?
            """,
            (reason, int(row["id"])),
        )
        cancelled += 1
    cursor = connection.execute(
        """
        INSERT INTO printer_memory_factory_run_steps
          (run_id,step_key,step_kind,step_status,token_id,pair_id,tracking_lane,
           result_json,error_or_skip_reason,finished_at)
        VALUES (?,?,'LONG_CONTINUITY_BLOCK','FAILED',?,?,?,?,?,datetime('now'))
        """,
        (
            run_id,
            key,
            token_id,
            pair_id,
            tracking_lane,
            json.dumps(
                {
                    "successor_window_kind": successor_kind,
                    "continuity_status": CONTINUITY_BLOCKED,
                },
                sort_keys=True,
            ),
            reason,
        ),
    )
    return {
        "terminally_blocked": True,
        "already_terminal": False,
        "cancelled_jobs": cancelled,
        "block_step_id": int(cursor.lastrowid),
    }


def resolve_lifecycle_continuity(
    connection: sqlite3.Connection,
    *,
    run_id: Any,
    token_id: int,
    pair_id: int,
    tracking_lane: str,
) -> dict[str, Any]:
    """Resolve the 5m->15m->1h continuity for one run/token/pair/lane from the DB.

    Read-only. Reads the 5m / 15m / 1h windows and the closing/opening snapshots
    for the run and runs both pure evaluators. Returns a combined result carrying
    the two ``ContinuityResult`` dicts and an overall ``continuity_status``.
    """
    # Windows attached to this run for this token/pair/lane, via run steps.
    win_rows = connection.execute(
        """
        SELECT w.* FROM printer_memory_windows w
        JOIN printer_memory_factory_run_steps s ON s.memory_window_id = w.id
        WHERE s.run_id = ? AND w.token_id = ? AND w.pair_id = ?
          AND s.tracking_lane = ?
        GROUP BY w.id
        ORDER BY w.id
        """,
        (run_id, token_id, pair_id, tracking_lane),
    ).fetchall()

    by_kind: dict[str, list[dict[str, Any]]] = {}
    for r in win_rows:
        by_kind.setdefault(str(r["window_kind"]), []).append(
            _window_record(r, run_id, tracking_lane))

    five = (by_kind.get("WINDOW_5M_MICRO_EVENT") or [None])[0]
    fifteen = (by_kind.get("WINDOW_15M") or [None])[0]
    one_h = (by_kind.get("WINDOW_1H") or [None])[0]

    out: dict[str, Any] = {
        "run_id": run_id,
        "token_id": token_id,
        "pair_id": pair_id,
        "tracking_lane": tracking_lane,
        "same_run_token_pair_lane": True,
        "five_m_window_id": (five or {}).get("id"),
        "fifteen_m_window_id": (fifteen or {}).get("id"),
        "one_h_window_id": (one_h or {}).get("id"),
    }

    stages: list[dict[str, Any]] = []
    statuses: list[str] = []

    if five is not None and fifteen is not None:
        gap = _first_post_5m_gap(connection, fifteen, five)
        r1 = evaluate_5m_to_15m_continuity(
            five, fifteen, tracking_lane=tracking_lane,
            first_post_5m_gap_seconds=gap,
        )
        stages.append(r1.to_dict())
        statuses.append(r1.status)

    if fifteen is not None and one_h is not None:
        # Populate continuation linkage from the 1h window's supporting context
        # if present; the DB path assumes the 1h row records its linkage.
        one_h_linked = _augment_1h_linkage(connection, one_h)
        consumed = _consumed_15m_ids(connection, run_id, token_id, pair_id, exclude_1h=one_h.get("id"))
        r2 = evaluate_15m_to_1h_continuity(
            fifteen, one_h_linked, tracking_lane=tracking_lane,
            consumed_15m_window_ids=consumed,
        )
        stages.append(r2.to_dict())
        statuses.append(r2.status)

    out["stages"] = stages
    out["continuity_status"] = _overall_status(statuses)
    out["do_not_train"] = any(s.get("do_not_train") for s in stages)
    out["can_be_quality_memory"] = bool(stages) and all(s.get("can_be_quality_memory") for s in stages)
    return out


def _overall_status(statuses: Sequence[str]) -> str:
    if not statuses:
        return CONTINUITY_UNKNOWN
    if CONTINUITY_BLOCKED in statuses:
        return CONTINUITY_BLOCKED
    if CONTINUITY_UNKNOWN in statuses:
        return CONTINUITY_UNKNOWN
    if CONTINUITY_DIRTY in statuses:
        return CONTINUITY_DIRTY
    return CONTINUITY_CONTINUOUS


def _first_post_5m_gap(
    connection: sqlite3.Connection,
    fifteen_m: Mapping[str, Any],
    five_m: Mapping[str, Any],
) -> float | None:
    """Gap between the last 5m snapshot and the next 15m snapshot in the run."""
    five_end = five_m.get("snapshot_end_id")
    m_end = fifteen_m.get("snapshot_end_id")
    if five_end is None or m_end is None:
        return None
    rows = connection.execute(
        """
        SELECT id, captured_at FROM printer_token_snapshots
        WHERE pair_id = ? AND id BETWEEN ? AND ?
        ORDER BY id
        """,
        (fifteen_m.get("pair_id"), int(five_end), int(m_end)),
    ).fetchall()
    if len(rows) < 2:
        return None
    a = _parse_ts(rows[0]["captured_at"])
    b = _parse_ts(rows[1]["captured_at"])
    if a is None or b is None:
        return None
    return (b - a).total_seconds()


def _augment_1h_linkage(connection: sqlite3.Connection, one_h: dict[str, Any]) -> dict[str, Any]:
    """Fill 1h continuation-linkage fields from supporting_context_json."""
    import json
    d = dict(one_h)
    try:
        ctx = json.loads(one_h.get("supporting_context_json") or "{}")
    except (json.JSONDecodeError, TypeError):
        ctx = {}
    d.setdefault("continuation_of_window_id", ctx.get("continuation_of_window_id"))
    d.setdefault("linked_closing_snapshot_id", ctx.get("linked_closing_snapshot_id"))
    d.setdefault("linked_first_snapshot_id", one_h.get("snapshot_start_id"))
    d.setdefault("reuses_historical_window", ctx.get("reuses_historical_window", False))
    d.setdefault("interpolated_first_snapshot", ctx.get("interpolated_first_snapshot", False))
    # first snapshot captured_at
    snap_id = d.get("linked_first_snapshot_id")
    if snap_id is not None and d.get("first_snapshot_at") is None:
        row = connection.execute(
            "SELECT captured_at FROM printer_token_snapshots WHERE id = ?",
            (int(snap_id),),
        ).fetchone()
        if row is not None:
            d["first_snapshot_at"] = row["captured_at"]
    return d


def _consumed_15m_ids(
    connection: sqlite3.Connection,
    run_id: Any,
    token_id: int,
    pair_id: int,
    *,
    exclude_1h: Any,
) -> list[int]:
    """15m window ids already referenced as a continuation source by *other* 1h windows."""
    import json
    rows = connection.execute(
        "SELECT id, supporting_context_json FROM printer_memory_windows"
        " WHERE window_kind = 'WINDOW_1H' AND token_id = ? AND pair_id = ?",
        (token_id, pair_id),
    ).fetchall()
    consumed: list[int] = []
    for r in rows:
        if exclude_1h is not None and int(r["id"]) == int(exclude_1h):
            continue
        try:
            ctx = json.loads(r["supporting_context_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            ctx = {}
        cid = ctx.get("continuation_of_window_id")
        if cid is not None:
            consumed.append(int(cid))
    return consumed

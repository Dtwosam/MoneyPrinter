"""V2-6.2 — Continuous First-Hour Lifecycle Contract.

One continuous lifecycle for the same run, token, pair, and lane:

    5m support  ->  15m main window  ->  1h continuation

This module is the single authoritative evaluator for lifecycle continuity. It
turns the previously-orphaned ``evaluate_transition_gap`` (cadence_policy) into a
wired, enforced contract and adds the 5m->15m linkage rules that were previously
only *reported* (read-only) by ``e2w_5m_linkage_report``.

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

The pure evaluators take plain dicts (as read from ``printer_memory_windows`` /
``printer_token_snapshots``) so they are trivially fixture-testable. A DB-backed
resolver reads the real rows for a run/token/pair/lane and runs both evaluators.

No DB mutation is produced by anything in this module. No memory, episode,
retrieval, paper, position, or PnL row is ever written or unlocked here.
"""

from __future__ import annotations

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

# The 15m main window spans 900s; the 1h continuation phase spans the remaining
# 2700s (t=15m..60m). The continuation deadline is anchored to the 15m close.
WINDOW_15M_SECONDS: float = 900.0
CONTINUATION_1H_SECONDS: float = 2700.0

_ALLOWED_LANES: frozenset[str] = frozenset({"TRACK_FAST", "TRACK_NORMAL"})


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

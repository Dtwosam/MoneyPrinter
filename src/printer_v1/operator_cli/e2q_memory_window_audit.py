"""E2Q Memory Window Audit / Classification Boundary.

Audits and classifies a closed main-outcome printer_memory_windows row against
its referenced snapshot evidence. Two window kinds are auditable: WINDOW_15M
(unchanged) and a genuine WINDOW_1H (real 1h identity, duration, governed
snapshot anchors, coverage, and exact token/pair targeting). WINDOW_5M_MICRO_EVENT
is support-only and WINDOW_4H/12H/24H are not enabled; all are blocked with a
window-kind-specific reason. Writes classification back to the window row
idempotently. Does NOT create memory rows, episodes, fingerprints, or any
paper-trading records.

Classification outcomes:
  E2Q_AUDIT_CLEAN_CANDIDATE — window + snapshot pass all quality gates; eligible
      to become clean memory in a later lane.
  E2Q_AUDIT_DIRTY — one or more hard quality failures detected (dirty/stale/failed
      evidence); do_not_train flag set on the window.
  E2Q_AUDIT_ONLY — acceptable but not fully clean (ACCEPTABLE_PARTIAL_DATA);
      audit-only, do_not_train set.
  E2Q_AUDIT_BLOCKED — structural gate failure (missing window, wrong kind, open
      window, missing snapshot, or token/pair mismatch); no write-back.

Hard locks (permanent):
- No memory retrieval activation.
- No paper decisions, positions, PnL, trade events, or paper trade audits.
- No BUY/SELL/HOLD.
- No live wallet/private keys/signing/real funds.
- No paid APIs, scoring/ranking/confidence/weighted logic, embeddings/vectors.
- No 5m main outcome window.
- No memory row creation (printer_episodes / printer_memories).
- Fail closed on missing, dirty, stale, failed, or mismatched evidence.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from printer_v1.snapshots.cadence_policy import (
    cadence_policy_to_dict,
    cadence_resource_budget,
    get_policy,
)


E2Q_REQUIRED_WINDOW_KIND: str = "WINDOW_15M"
E2Q_REQUIRED_WINDOW_STATUS: str = "WINDOW_CLOSED"
E2Q_REQUIRED_SOURCE_STATUS: str = "COMPLETE"
E2Q_REQUIRED_QUALITY: str = "CLEAN_DATA"
E2Q_ACCEPTABLE_QUALITY: str = "ACCEPTABLE_PARTIAL_DATA"
E2Q_CREATED_BY: str = "lane_e2q"

# V2-6 window-kind-specific audit gate.
#   WINDOW_15M            — the original valid main outcome window (unchanged).
#   WINDOW_1H            — a genuine 1h continuation window is admissible ONLY when
#                          it has real 1h identity (kind), real duration, governed
#                          snapshot anchors, coverage, and exact token/pair
#                          targeting; a relabelled or insufficient window is blocked.
#   WINDOW_5M_MICRO_EVENT — support-only; never a valid main outcome window.
#   WINDOW_4H/12H/24H     — not enabled as main outcome windows.
E2Q_1H_WINDOW_KIND: str = "WINDOW_1H"
E2Q_4H_WINDOW_KIND: str = "WINDOW_4H"
E2Q_SUPPORT_ONLY_WINDOW_KIND: str = "WINDOW_5M_MICRO_EVENT"
E2Q_VALID_MAIN_WINDOW_KINDS: frozenset[str] = frozenset({
    E2Q_REQUIRED_WINDOW_KIND,
    E2Q_1H_WINDOW_KIND,
    E2Q_4H_WINDOW_KIND,
})
E2Q_UNSUPPORTED_MAIN_WINDOW_KINDS: frozenset[str] = frozenset({
    "WINDOW_12H",
    "WINDOW_24H",
})
# Genuine WINDOW_1H continuation-phase minimum span. Matches the established 1h
# contract in lane_e2o_1h_window_close (_MIN_ELAPSED_SECONDS = 2700.0, the
# 45-minute continuation minimum also enforced by Lane Q). A ~900s window (a
# relabelled 15m window) fails this floor and stays blocked from 1h audit.
E2Q_1H_MIN_ELAPSED_SECONDS: float = 2700.0
E2Q_4H_MIN_ELAPSED_SECONDS: float = 10_800.0

E2Q_STATUS_CLEAN_CANDIDATE: str = "E2Q_AUDIT_CLEAN_CANDIDATE"
E2Q_STATUS_DIRTY: str = "E2Q_AUDIT_DIRTY"
E2Q_STATUS_AUDIT_ONLY: str = "E2Q_AUDIT_ONLY"
E2Q_STATUS_BLOCKED: str = "E2Q_AUDIT_BLOCKED"

_DIRTY_QUALITY_LABELS: frozenset[str] = frozenset({
    "DIRTY_DATA",
    "STALE_DATA",
    "MISSING_CRITICAL_DATA",
    "CONFLICTING_DATA",
    "DO_NOT_TRAIN",
})
_DIRTY_SOURCE_STATUSES: frozenset[str] = frozenset({
    "FAILED",
    "STALE",
    "CONFLICTING",
})

_HARD_LOCKS: dict[str, bool] = {
    "no_buy_sell_hold": True,
    "no_paper_decisions": True,
    "no_positions": True,
    "no_pnl": True,
    "no_memory_creation": True,
    "no_retrieval_activation": True,
    "no_live_trading": True,
    "no_paid_api": True,
    "no_generic_search": True,
    "no_scoring_ranking": True,
    "no_embeddings_vectors": True,
    "no_5m_main_window": True,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_window(
    connection: sqlite3.Connection, window_id: int
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM printer_memory_windows WHERE id = ?",
        (window_id,),
    ).fetchone()


def _load_snapshot(
    connection: sqlite3.Connection, snapshot_id: int
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM printer_token_snapshots WHERE id = ?",
        (snapshot_id,),
    ).fetchone()


def _load_tracking_lane(
    connection: sqlite3.Connection, token_id: int
) -> str | None:
    row = connection.execute(
        "SELECT token_status FROM printer_tokens WHERE id = ?",
        (token_id,),
    ).fetchone()
    if row is None:
        return None
    lane = str(row["token_status"] or "")
    return lane if lane in {"TRACK_FAST", "TRACK_NORMAL"} else None


def _elapsed_seconds(start_ts: str, end_ts: str) -> float | None:
    """Return end-start in seconds from two ISO timestamps, or None if unparseable."""
    try:
        start = datetime.fromisoformat(start_ts)
        end = datetime.fromisoformat(end_ts)
        try:
            return (end - start).total_seconds()
        except TypeError:
            s = start.replace(tzinfo=None) if start.tzinfo else start
            e = end.replace(tzinfo=None) if end.tzinfo else end
            return (e - s).total_seconds()
    except (ValueError, TypeError):
        return None


def _validate_genuine_1h_window(
    connection: sqlite3.Connection, win: sqlite3.Row,
) -> list[str]:
    """Return structural block reasons for a WINDOW_1H window (empty = genuine).

    A genuine 1h window must have real 1h identity, real duration, governed
    snapshot anchors, coverage, and exact token/pair targeting on both anchors.
    This rejects a WINDOW_1H produced by relabelling or combining insufficient
    15m evidence. Evidence *quality* (dirty/stale) is handled by the shared
    quality gates, exactly like WINDOW_15M — a genuine but dirty 1h window
    classifies DIRTY (do_not_train), not clean.
    """
    reasons: list[str] = []

    start_at = win["window_start_at"]
    end_at = win["window_end_at"]
    start_snap_id = win["snapshot_start_id"]
    end_snap_id = win["snapshot_end_id"]

    # Real 1h duration identity: both boundary timestamps must be present.
    if not start_at or not end_at:
        reasons.append(
            "WINDOW_1H missing real window_start_at/window_end_at;"
            " a relabelled or insufficient 1h window is not auditable"
        )

    # Governed snapshot anchors (coverage): both start and end anchors required.
    if start_snap_id is None or end_snap_id is None:
        reasons.append(
            "WINDOW_1H missing governed snapshot anchors"
            " (snapshot_start_id and snapshot_end_id required)"
        )

    # Real duration floor: a genuine 1h continuation window spans >= the
    # established 1h minimum; a ~900s window is relabelled 15m evidence.
    if start_at and end_at:
        elapsed = _elapsed_seconds(str(start_at), str(end_at))
        if elapsed is None:
            reasons.append("WINDOW_1H window_start_at/window_end_at are not parseable")
        elif elapsed < E2Q_1H_MIN_ELAPSED_SECONDS:
            reasons.append(
                f"WINDOW_1H elapsed {elapsed:.0f}s is below the genuine 1h minimum"
                f" {E2Q_1H_MIN_ELAPSED_SECONDS:.0f}s; insufficient 15m evidence cannot"
                " be relabelled as 1h"
            )

    # Exact token/pair targeting on the START anchor (the END anchor is the
    # audited snapshot, already token/pair-validated by the shared gates).
    if start_snap_id is not None:
        start_snap = _load_snapshot(connection, int(start_snap_id))
        if start_snap is None:
            reasons.append(
                f"WINDOW_1H snapshot_start_id {start_snap_id} not found"
            )
        else:
            if int(start_snap["token_id"]) != int(win["token_id"]):
                reasons.append(
                    "WINDOW_1H snapshot_start token_id mismatch:"
                    f" window.token_id={win['token_id']!r}"
                    f" vs start_snapshot.token_id={start_snap['token_id']!r}"
                )
            win_pair = int(win["pair_id"]) if win["pair_id"] is not None else None
            start_pair = int(start_snap["pair_id"]) if start_snap["pair_id"] is not None else None
            if win_pair is not None and start_pair is not None and win_pair != start_pair:
                reasons.append(
                    "WINDOW_1H snapshot_start pair_id mismatch:"
                    f" window.pair_id={win_pair!r} vs start_snapshot.pair_id={start_pair!r}"
                )

    return reasons


def _validate_genuine_4h_window(
    connection: sqlite3.Connection, win: sqlite3.Row,
) -> list[str]:
    """Require an exact, anchored 1h-to-4h continuation."""
    reasons: list[str] = []
    start_at = win["window_start_at"]
    end_at = win["window_end_at"]
    start_id = win["snapshot_start_id"]
    end_id = win["snapshot_end_id"]
    if not start_at or not end_at or start_id is None or end_id is None:
        return ["WINDOW_4H missing anchored boundaries or governed snapshot anchors"]
    elapsed = _elapsed_seconds(str(start_at), str(end_at))
    if elapsed is None or elapsed < E2Q_4H_MIN_ELAPSED_SECONDS:
        reasons.append("WINDOW_4H does not span the fixed 10800-second continuation")
    try:
        context = json.loads(win["supporting_context_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        context = {}
    required = (
        "run_id", "continuation_of_window_id", "linked_closing_snapshot_id",
        "linked_first_snapshot_id", "fixed_deadline_at", "continuity_status",
    )
    missing = [name for name in required if context.get(name) is None]
    if missing:
        reasons.append(f"WINDOW_4H missing continuity metadata: {missing}")
    if context.get("continuity_status") == "CONTINUITY_BLOCKED":
        reasons.append("WINDOW_4H continuity is blocked")
    for label, snapshot_id in (("start", start_id), ("end", end_id)):
        snapshot = _load_snapshot(connection, int(snapshot_id))
        if snapshot is None:
            reasons.append(f"WINDOW_4H {label} snapshot not found")
            continue
        if int(snapshot["token_id"]) != int(win["token_id"]):
            reasons.append(f"WINDOW_4H {label} snapshot token mismatch")
        if win["pair_id"] is not None and snapshot["pair_id"] is not None and int(snapshot["pair_id"]) != int(win["pair_id"]):
            reasons.append(f"WINDOW_4H {label} snapshot pair mismatch")
    return reasons


def _write_audit_result(
    connection: sqlite3.Connection,
    window_id: int,
    memory_quality_label: str,
    memory_status: str,
    do_not_train: int,
    rejection_reasons: list[str],
    audit_notes: list[str],
    now: str,
) -> bool:
    """Write classification fields back to the window row.

    Returns True if the row was updated, False if the computed values were
    already present (no-op — updated_at is not changed in the no-op case).
    """
    existing_row = connection.execute(
        "SELECT memory_quality_label, memory_status, do_not_train,"
        "       rejection_reasons_json, supporting_context_json"
        " FROM printer_memory_windows WHERE id = ?",
        (window_id,),
    ).fetchone()

    try:
        ctx = json.loads(existing_row["supporting_context_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        ctx = {}
    ctx["e2q_audited"] = True
    ctx["e2q_audit_status"] = memory_quality_label
    ctx["e2q_audited_by"] = E2Q_CREATED_BY

    new_rejection_json = json.dumps(rejection_reasons, sort_keys=True)
    new_ctx_json = json.dumps(ctx, sort_keys=True)

    # No-op check: skip the UPDATE if every field we'd write is already stored.
    already_stored = (
        existing_row["memory_quality_label"] == memory_quality_label
        and existing_row["memory_status"] == memory_status
        and int(existing_row["do_not_train"] or 0) == do_not_train
        and (existing_row["rejection_reasons_json"] or "[]") == new_rejection_json
        and (existing_row["supporting_context_json"] or "{}") == new_ctx_json
    )
    if already_stored:
        return False

    connection.execute(
        """
        UPDATE printer_memory_windows
        SET memory_quality_label = ?,
            memory_status = ?,
            do_not_train = ?,
            rejection_reasons_json = ?,
            supporting_context_json = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            memory_quality_label,
            memory_status,
            do_not_train,
            new_rejection_json,
            new_ctx_json,
            now,
            window_id,
        ),
    )
    return True


def audit_15m_memory_window(
    connection: sqlite3.Connection,
    window_id: int,
) -> dict[str, Any]:
    """Audit and classify a closed WINDOW_15M evidence window.

    Reads the window and its referenced snapshot, applies quality gates, and
    writes the classification back to the window row. Idempotent: re-running
    with the same window produces the same result without creating extra rows.

    Returns an audit dict. Does NOT commit — caller is responsible.
    """
    # --- Gate 1: window must exist ---
    win = _load_window(connection, window_id)
    if win is None:
        return {
            "e2q_status": E2Q_STATUS_BLOCKED,
            "classified": False,
            "blocked_reasons": [f"window_id {window_id} not found"],
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memories_created": 0,
        }

    # --- Gate 2: window_kind must be a valid main outcome window ---
    # WINDOW_15M and genuine WINDOW_1H are auditable. WINDOW_5M_MICRO_EVENT is
    # support-only. WINDOW_4H/12H/24H are not enabled. All others are blocked
    # with a window-kind-specific reason. The genuine-1h identity/duration/
    # anchor/targeting checks run below, after the shared structural gates.
    window_kind = win["window_kind"]
    if window_kind not in E2Q_VALID_MAIN_WINDOW_KINDS:
        if window_kind == E2Q_SUPPORT_ONLY_WINDOW_KIND:
            blocked_reason = (
                f"window_kind {window_kind!r} is support-only;"
                " 5m micro-event is not a valid main outcome window"
            )
        elif window_kind in E2Q_UNSUPPORTED_MAIN_WINDOW_KINDS:
            cadence_policy = get_policy(
                window_kind,
                _load_tracking_lane(connection, int(win["token_id"])),
            )
            blocked_reason = (
                f"window_kind {window_kind!r} is not enabled as a main outcome"
                " window; only WINDOW_15M and genuine WINDOW_1H are audited"
            )
        else:
            blocked_reason = (
                f"window_kind must be one of {sorted(E2Q_VALID_MAIN_WINDOW_KINDS)!r};"
                f" got {window_kind!r}"
            )
        result = {
            "e2q_status": E2Q_STATUS_BLOCKED,
            "classified": False,
            "blocked_reasons": [blocked_reason],
            "window_id": window_id,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memories_created": 0,
        }
        if window_kind in E2Q_UNSUPPORTED_MAIN_WINDOW_KINDS and cadence_policy is not None:
            result["cadence_policy"] = cadence_policy_to_dict(cadence_policy)
            result["cadence_resource_budget"] = cadence_resource_budget(
                window_kind, cadence_policy.tracking_lane
            )
        return result

    # --- Gate 3: window must be closed ---
    if win["window_status"] != E2Q_REQUIRED_WINDOW_STATUS:
        return {
            "e2q_status": E2Q_STATUS_BLOCKED,
            "classified": False,
            "blocked_reasons": [
                f"window_status must be {E2Q_REQUIRED_WINDOW_STATUS!r};"
                f" got {win['window_status']!r}"
            ],
            "window_id": window_id,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memories_created": 0,
        }

    # --- Gate 4: supporting_context_json must contain snapshot_id ---
    try:
        ctx = json.loads(win["supporting_context_json"] or "{}")
        snapshot_id = ctx.get("snapshot_id")
    except (json.JSONDecodeError, TypeError):
        snapshot_id = None
        ctx = {}
    if snapshot_id is None:
        result = {
            "e2q_status": E2Q_STATUS_BLOCKED,
            "classified": False,
            "blocked_reasons": [
                "supporting_context_json missing or has no 'snapshot_id'"
            ],
            "window_id": window_id,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memories_created": 0,
        }
        if window_kind == E2Q_4H_WINDOW_KIND:
            policy = get_policy(
                window_kind, _load_tracking_lane(connection, int(win["token_id"]))
            )
            if policy is not None:
                result["cadence_policy"] = cadence_policy_to_dict(policy)
                result["cadence_resource_budget"] = cadence_resource_budget(
                    window_kind, policy.tracking_lane
                )
        return result

    # --- Gate 5: snapshot must exist ---
    snap = _load_snapshot(connection, int(snapshot_id))
    if snap is None:
        return {
            "e2q_status": E2Q_STATUS_BLOCKED,
            "classified": False,
            "blocked_reasons": [
                f"snapshot_id {snapshot_id} referenced in supporting_context_json not found"
            ],
            "window_id": window_id,
            "snapshot_id": snapshot_id,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memories_created": 0,
        }

    # --- Gate 6: token_id match ---
    if int(snap["token_id"]) != int(win["token_id"]):
        return {
            "e2q_status": E2Q_STATUS_BLOCKED,
            "classified": False,
            "blocked_reasons": [
                f"token_id mismatch: window.token_id={win['token_id']!r}"
                f" vs snapshot.token_id={snap['token_id']!r}"
            ],
            "window_id": window_id,
            "snapshot_id": snapshot_id,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memories_created": 0,
        }

    # --- Gate 7: pair_id match (when both non-null) ---
    win_pair = int(win["pair_id"]) if win["pair_id"] is not None else None
    snap_pair = int(snap["pair_id"]) if snap["pair_id"] is not None else None
    if win_pair is not None and snap_pair is not None and win_pair != snap_pair:
        return {
            "e2q_status": E2Q_STATUS_BLOCKED,
            "classified": False,
            "blocked_reasons": [
                f"pair_id mismatch: window.pair_id={win_pair!r}"
                f" vs snapshot.pair_id={snap_pair!r}"
            ],
            "window_id": window_id,
            "snapshot_id": snapshot_id,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memories_created": 0,
        }

    # --- Gate 8 (WINDOW_1H only): genuine 1h identity / duration / anchors /
    # coverage / exact targeting. A relabelled or insufficient 1h window is
    # blocked here. WINDOW_15M skips this gate (behavior unchanged). ---
    if window_kind == E2Q_1H_WINDOW_KIND:
        onehour_reasons = _validate_genuine_1h_window(connection, win)
        if onehour_reasons:
            return {
                "e2q_status": E2Q_STATUS_BLOCKED,
                "classified": False,
                "blocked_reasons": onehour_reasons,
                "window_id": window_id,
                "snapshot_id": snapshot_id,
                "window_kind": window_kind,
                "hard_locks": dict(_HARD_LOCKS),
                "paper_decisions_created": 0,
                "positions_created": 0,
                "pnl_created": 0,
                "memories_created": 0,
            }
    elif window_kind == E2Q_4H_WINDOW_KIND:
        fourhour_reasons = _validate_genuine_4h_window(connection, win)
        if fourhour_reasons:
            return {
                "e2q_status": E2Q_STATUS_BLOCKED,
                "classified": False,
                "blocked_reasons": fourhour_reasons,
                "window_id": window_id,
                "snapshot_id": snapshot_id,
                "window_kind": window_kind,
                "hard_locks": dict(_HARD_LOCKS),
                "paper_decisions_created": 0,
                "positions_created": 0,
                "pnl_created": 0,
                "memories_created": 0,
            }

    # All structural gates passed. Now classify quality.
    rejection_reasons: list[str] = []
    audit_notes: list[str] = []

    win_quality = str(win["data_quality_label"] or "")
    snap_status = str(snap["source_status"] or "")
    snap_quality = str(snap["data_quality_label"] or "")

    # Check window quality
    if win_quality in _DIRTY_QUALITY_LABELS:
        rejection_reasons.append(
            f"window data_quality_label is dirty: {win_quality!r}"
        )
    elif win_quality == E2Q_ACCEPTABLE_QUALITY:
        audit_notes.append(
            f"window data_quality_label is acceptable partial: {win_quality!r}"
        )

    # Check snapshot source_status
    if snap_status in _DIRTY_SOURCE_STATUSES:
        rejection_reasons.append(
            f"snapshot source_status is dirty: {snap_status!r}"
        )
    elif snap_status != E2Q_REQUIRED_SOURCE_STATUS:
        audit_notes.append(
            f"snapshot source_status is not COMPLETE: {snap_status!r}"
        )

    # Check snapshot data_quality_label
    if snap_quality in _DIRTY_QUALITY_LABELS:
        rejection_reasons.append(
            f"snapshot data_quality_label is dirty: {snap_quality!r}"
        )
    elif snap_quality == E2Q_ACCEPTABLE_QUALITY:
        audit_notes.append(
            f"snapshot data_quality_label is acceptable partial: {snap_quality!r}"
        )

    # Determine final classification
    now = _utc_now()
    if rejection_reasons:
        row_updated = _write_audit_result(
            connection, window_id,
            memory_quality_label="DIRTY_MEMORY",
            memory_status="DIRTY_MEMORY",
            do_not_train=1,
            rejection_reasons=rejection_reasons,
            audit_notes=audit_notes,
            now=now,
        )
        return {
            "e2q_status": E2Q_STATUS_DIRTY,
            "classified": True,
            "row_updated": row_updated,
            "window_id": window_id,
            "snapshot_id": snapshot_id,
            "memory_quality_label": "DIRTY_MEMORY",
            "rejection_reasons": rejection_reasons,
            "audit_notes": audit_notes,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memories_created": 0,
        }

    if audit_notes:
        row_updated = _write_audit_result(
            connection, window_id,
            memory_quality_label="AUDIT_ONLY_MEMORY",
            memory_status="AUDIT_ONLY",
            do_not_train=1,
            rejection_reasons=[],
            audit_notes=audit_notes,
            now=now,
        )
        return {
            "e2q_status": E2Q_STATUS_AUDIT_ONLY,
            "classified": True,
            "row_updated": row_updated,
            "window_id": window_id,
            "snapshot_id": snapshot_id,
            "memory_quality_label": "AUDIT_ONLY_MEMORY",
            "rejection_reasons": [],
            "audit_notes": audit_notes,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memories_created": 0,
        }

    # All quality gates passed — clean candidate.
    row_updated = _write_audit_result(
        connection, window_id,
        memory_quality_label="PARTIAL_MEMORY",
        memory_status="PARTIAL_MEMORY",
        do_not_train=0,
        rejection_reasons=[],
        audit_notes=[],
        now=now,
    )
    return {
        "e2q_status": E2Q_STATUS_CLEAN_CANDIDATE,
        "classified": True,
        "row_updated": row_updated,
        "window_id": window_id,
        "snapshot_id": snapshot_id,
        "memory_quality_label": "PARTIAL_MEMORY",
        "rejection_reasons": [],
        "audit_notes": [],
        "hard_locks": dict(_HARD_LOCKS),
        "paper_decisions_created": 0,
        "positions_created": 0,
        "pnl_created": 0,
        "memories_created": 0,
    }

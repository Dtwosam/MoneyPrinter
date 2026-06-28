"""E2Q 15m Memory Window Audit / Classification Boundary.

Audits and classifies a closed WINDOW_15M printer_memory_windows row against
its referenced snapshot evidence. Writes classification back to the window row
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


E2Q_REQUIRED_WINDOW_KIND: str = "WINDOW_15M"
E2Q_REQUIRED_WINDOW_STATUS: str = "WINDOW_CLOSED"
E2Q_REQUIRED_SOURCE_STATUS: str = "COMPLETE"
E2Q_REQUIRED_QUALITY: str = "CLEAN_DATA"
E2Q_ACCEPTABLE_QUALITY: str = "ACCEPTABLE_PARTIAL_DATA"
E2Q_CREATED_BY: str = "lane_e2q"

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


def _write_audit_result(
    connection: sqlite3.Connection,
    window_id: int,
    memory_quality_label: str,
    memory_status: str,
    do_not_train: int,
    rejection_reasons: list[str],
    audit_notes: list[str],
    now: str,
) -> None:
    existing_ctx_row = connection.execute(
        "SELECT supporting_context_json FROM printer_memory_windows WHERE id = ?",
        (window_id,),
    ).fetchone()
    try:
        ctx = json.loads(existing_ctx_row["supporting_context_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        ctx = {}
    ctx["e2q_audited"] = True
    ctx["e2q_audit_status"] = memory_quality_label
    ctx["e2q_audited_by"] = E2Q_CREATED_BY

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
            json.dumps(rejection_reasons, sort_keys=True),
            json.dumps(ctx, sort_keys=True),
            now,
            window_id,
        ),
    )


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

    # --- Gate 2: must be WINDOW_15M ---
    if win["window_kind"] != E2Q_REQUIRED_WINDOW_KIND:
        return {
            "e2q_status": E2Q_STATUS_BLOCKED,
            "classified": False,
            "blocked_reasons": [
                f"window_kind must be {E2Q_REQUIRED_WINDOW_KIND!r};"
                f" got {win['window_kind']!r}; 5m is not a valid main outcome window"
            ],
            "window_id": window_id,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memories_created": 0,
        }

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
        return {
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
        _write_audit_result(
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
        _write_audit_result(
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
    _write_audit_result(
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

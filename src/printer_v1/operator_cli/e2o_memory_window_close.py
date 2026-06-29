"""E2O 15m Memory Window Close Boundary.

Closes a WINDOW_15M memory evidence window from a single existing, validated
printer_token_snapshots row.

This module only writes one printer_memory_windows row.
It does NOT create memories, episodes, fingerprints, paper decisions, positions,
or any other downstream records.

Integrity fields (Lane R):
  When snapshot_start_id is supplied to close_15m_memory_window_from_snapshot,
  the writer derives window_start_at / window_end_at from the real captured_at
  timestamps of the start and close snapshots, and writes snapshot_start_id /
  snapshot_end_id to the row.  No fake timestamps are ever written.

  If snapshot_start_id is NOT supplied (single-snapshot path), all four
  integrity fields are written as NULL.  Lane Q will block such rows with
  missing_window_start_at — that is the correct, honest outcome.

  The writer does NOT block when elapsed < 900 s; it reports
  lane_q_integrity_eligible=False and not_eligible_reason so the caller can
  understand why Lane Q will block the window.

Hard locks (permanent):
- No BUY/SELL/HOLD, paper decisions, positions, or PnL.
- No memory creation (printer_episodes, printer_memories, printer_fingerprints).
- No retrieval activation.
- No wallet/private keys/live trading/real funds.
- No paid APIs, scoring, ranking, confidence, embeddings, or vectors.
- No generic search or broad discovery.
- No direct source calls.
- One token only. Solana only (enforced by schema + explicit gate).
- WINDOW_15M only. 5m is not a valid main window.
- TRACK_FAST or TRACK_NORMAL lane only.
- Fail closed on missing, dirty, stale, failed, mismatched, or non-15m evidence.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

_MIN_ELAPSED_SECONDS: float = 900.0  # 15 minutes


E2O_WINDOW_KIND: str = "WINDOW_15M"
E2O_REQUIRED_SOURCE_STATUS: str = "COMPLETE"
E2O_REQUIRED_QUALITY: str = "CLEAN_DATA"
E2O_ALLOWED_LANES: frozenset[str] = frozenset({"TRACK_FAST", "TRACK_NORMAL"})
E2O_REQUIRED_CHAIN: str = "solana"
E2O_WINDOW_STATUS: str = "WINDOW_CLOSED"
E2O_MEMORY_STATUS: str = "PARTIAL_MEMORY"
E2O_CREATED_BY: str = "lane_e2o"

E2O_STATUS_CREATED: str = "E2O_WINDOW_CREATED"
E2O_STATUS_DUPLICATE: str = "E2O_WINDOW_DUPLICATE"
E2O_STATUS_BLOCKED: str = "E2O_WINDOW_BLOCKED"

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
    "no_5m_main_window": True,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_snapshot_captured_at(
    connection: sqlite3.Connection, snapshot_id: int
) -> str | None:
    """Return captured_at for the given snapshot id, or None if not found."""
    row = connection.execute(
        "SELECT captured_at FROM printer_token_snapshots WHERE id = ?",
        (snapshot_id,),
    ).fetchone()
    return str(row["captured_at"]) if row else None


def _compute_elapsed_seconds(start_ts: str, end_ts: str) -> float | None:
    """Return elapsed seconds between two ISO 8601 strings, or None on error."""
    try:
        s = datetime.fromisoformat(start_ts)
        e = datetime.fromisoformat(end_ts)
        try:
            return (e - s).total_seconds()
        except TypeError:
            # Mixed aware/naive — strip tz from the aware side
            s2 = s.replace(tzinfo=None) if s.tzinfo else s
            e2 = e.replace(tzinfo=None) if e.tzinfo else e
            return (e2 - s2).total_seconds()
    except (ValueError, TypeError):
        return None


def _load_snapshot_with_token(
    connection: sqlite3.Connection, snapshot_id: int
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT s.*, t.token_mint, t.chain"
        " FROM printer_token_snapshots s"
        " JOIN printer_tokens t ON t.id = s.token_id"
        " WHERE s.id = ?",
        (snapshot_id,),
    ).fetchone()


def _find_existing_window(
    connection: sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    snapshot_id: int,
) -> int | None:
    """Return existing window id if already created from this snapshot."""
    row = connection.execute(
        "SELECT id FROM printer_memory_windows"
        " WHERE token_id = ?"
        "   AND COALESCE(pair_id, -1) = COALESCE(?, -1)"
        "   AND window_kind = ?"
        "   AND json_extract(supporting_context_json, '$.snapshot_id') = ?"
        " LIMIT 1",
        (token_id, pair_id, E2O_WINDOW_KIND, snapshot_id),
    ).fetchone()
    return int(row["id"]) if row else None


def _insert_memory_window(
    connection: sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    snapshot: sqlite3.Row,
    approved_mint: str,
    snapshot_id: int,
    now: str,
    *,
    window_start_at: str | None = None,
    window_end_at: str | None = None,
    snapshot_start_id: int | None = None,
    snapshot_end_id: int | None = None,
) -> int:
    captured_at = str(snapshot["captured_at"])
    # opened_at tracks the real window open time when start evidence is available
    opened_at = window_start_at if window_start_at is not None else captured_at
    tracking_lane = str(snapshot["tracking_lane"])
    snapshot_mode = str(snapshot["snapshot_mode"])
    supporting_context = json.dumps(
        {
            "snapshot_id": snapshot_id,
            "tracking_lane": tracking_lane,
            "snapshot_mode": snapshot_mode,
            "approved_mint": approved_mint,
            "created_by": E2O_CREATED_BY,
        },
        sort_keys=True,
    )
    cursor = connection.execute(
        """
        INSERT INTO printer_memory_windows (
            token_id, pair_id, window_kind, opened_at, closed_at,
            memory_status, data_quality_label, do_not_train, window_status,
            supporting_context_json, created_by_phase, created_at, updated_at,
            window_start_at, window_end_at, snapshot_start_id, snapshot_end_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            token_id,
            pair_id,
            E2O_WINDOW_KIND,
            opened_at,
            captured_at,  # closed_at always = close snapshot's captured_at
            E2O_MEMORY_STATUS,
            E2O_REQUIRED_QUALITY,
            E2O_WINDOW_STATUS,
            supporting_context,
            E2O_CREATED_BY,
            now,
            now,
            window_start_at,
            window_end_at,
            snapshot_start_id,
            snapshot_end_id,
        ),
    )
    return int(cursor.lastrowid)


def close_15m_memory_window_from_snapshot(
    connection: sqlite3.Connection,
    snapshot_id: int,
    approved_mint: str,
    *,
    snapshot_start_id: int | None = None,
) -> dict[str, Any]:
    """Close exactly one WINDOW_15M evidence window from a clean snapshot.

    Validates the snapshot before writing. Idempotent: a second call with the
    same snapshot_id returns E2O_WINDOW_DUPLICATE without creating a new row.

    snapshot_start_id (optional): the snapshot that marks the OPEN boundary of
    this 15m window.  When provided, window_start_at / window_end_at /
    snapshot_start_id / snapshot_end_id are derived from real captured_at
    values and written to the row so Lane Q can validate real elapsed time.
    When omitted, those four columns are written as NULL (Lane Q will block
    the window with missing_window_start_at — the correct honest outcome for
    instant single-snapshot cycles that have no real 15m evidence).

    No fake timestamps are ever written.  The writer does not block when
    elapsed < 900 s; lane_q_integrity_eligible=False is reported instead.

    Returns an audit dict. Does NOT commit — caller is responsible.
    """
    row = _load_snapshot_with_token(connection, snapshot_id)
    if row is None:
        return {
            "e2o_status": E2O_STATUS_BLOCKED,
            "created": False,
            "blocked_reasons": [f"snapshot_id {snapshot_id} not found"],
            "approved_mint": approved_mint,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memories_created": 0,
            "memory_windows_created": 0,
        }

    blocked_reasons: list[str] = []

    if row["source_status"] != E2O_REQUIRED_SOURCE_STATUS:
        blocked_reasons.append(
            f"source_status must be {E2O_REQUIRED_SOURCE_STATUS!r};"
            f" got {row['source_status']!r}"
        )

    if row["data_quality_label"] != E2O_REQUIRED_QUALITY:
        blocked_reasons.append(
            f"data_quality_label must be {E2O_REQUIRED_QUALITY!r};"
            f" got {row['data_quality_label']!r}"
        )

    if row["tracking_lane"] not in E2O_ALLOWED_LANES:
        blocked_reasons.append(
            f"tracking_lane must be one of {sorted(E2O_ALLOWED_LANES)!r};"
            f" got {row['tracking_lane']!r}; WINDOW_5M is not a valid main window"
        )

    if row["chain"] != E2O_REQUIRED_CHAIN:
        blocked_reasons.append(
            f"chain must be {E2O_REQUIRED_CHAIN!r}; got {row['chain']!r}"
        )

    if str(row["token_mint"]).lower() != approved_mint.lower():
        blocked_reasons.append(
            f"token_mint {row['token_mint']!r} does not match"
            f" approved_mint {approved_mint!r}"
        )

    if blocked_reasons:
        return {
            "e2o_status": E2O_STATUS_BLOCKED,
            "created": False,
            "blocked_reasons": blocked_reasons,
            "approved_mint": approved_mint,
            "snapshot_id": snapshot_id,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memories_created": 0,
            "memory_windows_created": 0,
        }

    token_id = int(row["token_id"])
    pair_id = int(row["pair_id"]) if row["pair_id"] is not None else None

    existing_id = _find_existing_window(connection, token_id, pair_id, snapshot_id)
    if existing_id is not None:
        return {
            "e2o_status": E2O_STATUS_DUPLICATE,
            "created": False,
            "duplicate": True,
            "existing_window_id": existing_id,
            "token_id": token_id,
            "pair_id": pair_id,
            "approved_mint": approved_mint,
            "snapshot_id": snapshot_id,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memories_created": 0,
            "memory_windows_created": 0,
        }

    # Resolve canonical 15m integrity fields from real snapshot timestamps.
    window_start_at: str | None = None
    window_end_at: str | None = None
    resolved_snapshot_start_id: int | None = None
    resolved_snapshot_end_id: int | None = None
    elapsed_seconds: float | None = None
    lane_q_integrity_eligible: bool = False
    not_eligible_reason: str | None = None

    if snapshot_start_id is not None:
        start_captured_at = _load_snapshot_captured_at(connection, snapshot_start_id)
        if start_captured_at is None:
            not_eligible_reason = (
                f"snapshot_start_id {snapshot_start_id} not found in DB;"
                " window_start_at/window_end_at will be NULL"
            )
        else:
            close_captured_at = str(row["captured_at"])
            window_start_at = start_captured_at
            window_end_at = close_captured_at
            resolved_snapshot_start_id = snapshot_start_id
            resolved_snapshot_end_id = snapshot_id
            elapsed_seconds = _compute_elapsed_seconds(window_start_at, window_end_at)
            if elapsed_seconds is not None and elapsed_seconds >= _MIN_ELAPSED_SECONDS:
                lane_q_integrity_eligible = True
            else:
                not_eligible_reason = (
                    f"elapsed_seconds={elapsed_seconds} < {_MIN_ELAPSED_SECONDS};"
                    " window is not a real 15m window and will be blocked by Lane Q"
                )
    else:
        not_eligible_reason = (
            "snapshot_start_id not provided; window_start_at/window_end_at will be"
            " NULL — Lane Q will block this window with missing_window_start_at"
        )

    now = _utc_now()
    window_id = _insert_memory_window(
        connection,
        token_id,
        pair_id,
        row,
        approved_mint,
        snapshot_id,
        now,
        window_start_at=window_start_at,
        window_end_at=window_end_at,
        snapshot_start_id=resolved_snapshot_start_id,
        snapshot_end_id=resolved_snapshot_end_id,
    )

    close_captured_at = str(row["captured_at"])
    opened_at_result = window_start_at if window_start_at is not None else close_captured_at

    result: dict[str, Any] = {
        "e2o_status": E2O_STATUS_CREATED,
        "created": True,
        "window_id": window_id,
        "window_kind": E2O_WINDOW_KIND,
        "window_status": E2O_WINDOW_STATUS,
        "token_id": token_id,
        "pair_id": pair_id,
        "approved_mint": approved_mint,
        "snapshot_id": snapshot_id,
        "snapshot_start_id": resolved_snapshot_start_id,
        "snapshot_end_id": resolved_snapshot_end_id,
        "tracking_lane": str(row["tracking_lane"]),
        "snapshot_mode": str(row["snapshot_mode"]),
        "opened_at": opened_at_result,
        "closed_at": close_captured_at,
        "window_start_at": window_start_at,
        "window_end_at": window_end_at,
        "elapsed_seconds": elapsed_seconds,
        "lane_q_integrity_eligible": lane_q_integrity_eligible,
        "hard_locks": dict(_HARD_LOCKS),
        "paper_decisions_created": 0,
        "positions_created": 0,
        "pnl_created": 0,
        "memories_created": 0,
        "memory_windows_created": 1,
    }
    if not_eligible_reason is not None:
        result["not_eligible_reason"] = not_eligible_reason
    return result

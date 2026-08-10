"""Lane X12 — WINDOW_1H Memory Window Close Boundary.

Closes a WINDOW_1H memory evidence window from a single existing, validated
printer_token_snapshots row.  Parallel to e2o_memory_window_close.py (WINDOW_15M).

This module only writes one printer_memory_windows row.
It does NOT create memories, episodes, fingerprints, paper decisions, positions,
or any other downstream records.

Evidence identity:
  pair_id + window_kind("WINDOW_1H") + snapshot_start_id is the unique key.
  Multiple WINDOW_1H records for the same token/pair at different time periods
  are valid and expected.  The duplicate check uses snapshot_start_id to
  distinguish different 1h windows for the same token.

Integrity fields (Lane X12):
  When snapshot_start_id is supplied, window_start_at / window_end_at /
  snapshot_start_id / snapshot_end_id are derived from real captured_at
  timestamps and written to the row so Lane Q can validate real elapsed time.
  When omitted, those four columns are written as NULL (Lane Q blocks with
  missing_window_start_at — the correct honest outcome).

  _MIN_ELAPSED_SECONDS = 2700.0 (45-minute continuation phase minimum).
  For predecessor-linked first-hour continuation, the actual closing snapshot
  must reach the fixed 15m-close + 2700s deadline; an early closing observation
  fails closed and creates no WINDOW_1H row. Legacy unlinked fixture behavior
  remains separately reported through lane_q_integrity_eligible.

Pair drift:
  The close module enforces that the closing snapshot's pair_id matches the
  pair_id expected for this window.  If pair_id has drifted (new pool/AMM),
  the close is blocked with pair_drift_detected=True.

Hard locks (permanent):
- No BUY/SELL/HOLD, paper decisions, positions, or PnL.
- No memory creation (printer_episodes, printer_memories, printer_fingerprints).
- No retrieval activation.
- No wallet/private keys/live trading/real funds.
- No paid APIs, scoring, ranking, confidence, embeddings, or vectors.
- No generic search or broad discovery.
- No direct source calls.
- One token only. Solana only.
- WINDOW_1H only. WINDOW_15M and WINDOW_5M_MICRO_EVENT are not accepted here.
- TRACK_FAST or TRACK_NORMAL lane only.
- Fail closed on missing, dirty, stale, failed, mismatched, or non-1h evidence.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from printer_v1.snapshots.lifecycle_continuity import (
    CONTINUITY_BLOCKED,
    CONTINUITY_DIRTY,
    compute_1h_continuation_deadline,
    evaluate_15m_to_1h_continuity,
)

_MIN_ELAPSED_SECONDS: float = 2700.0  # 45-minute continuation phase minimum

E2O_1H_STATUS_CONTINUITY_BLOCKED: str = "E2O_1H_CONTINUITY_BLOCKED"
_DIRTY_DATA_QUALITY: str = "DIRTY_DATA"

E2O_1H_WINDOW_KIND: str = "WINDOW_1H"
E2O_1H_REQUIRED_SOURCE_STATUS: str = "COMPLETE"
E2O_1H_REQUIRED_QUALITY: str = "CLEAN_DATA"
E2O_1H_ALLOWED_LANES: frozenset[str] = frozenset({"TRACK_FAST", "TRACK_NORMAL"})
E2O_1H_REQUIRED_CHAIN: str = "solana"
E2O_1H_WINDOW_STATUS: str = "WINDOW_CLOSED"
E2O_1H_MEMORY_STATUS: str = "PARTIAL_MEMORY"
E2O_1H_CREATED_BY: str = "lane_e2o_1h"

E2O_1H_STATUS_CREATED: str = "E2O_1H_WINDOW_CREATED"
E2O_1H_STATUS_DUPLICATE: str = "E2O_1H_WINDOW_DUPLICATE"
E2O_1H_STATUS_BLOCKED: str = "E2O_1H_WINDOW_BLOCKED"

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
    "no_window_15m_in_1h_close": True,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_snapshot_captured_at(
    connection: sqlite3.Connection, snapshot_id: int
) -> str | None:
    row = connection.execute(
        "SELECT captured_at FROM printer_token_snapshots WHERE id = ?",
        (snapshot_id,),
    ).fetchone()
    return str(row["captured_at"]) if row else None


def _compute_elapsed_seconds(start_ts: str, end_ts: str) -> float | None:
    try:
        s = datetime.fromisoformat(start_ts)
        e = datetime.fromisoformat(end_ts)
        try:
            return (e - s).total_seconds()
        except TypeError:
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


def _find_existing_1h_window(
    connection: sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    snapshot_start_id: int | None,
) -> int | None:
    """Return existing window id if already created from this snapshot_start_id.

    Unlike E2O (which keys on the close snapshot_id), the 1h window is keyed on
    snapshot_start_id — the first snapshot of the 1h continuation phase.
    This ensures separate 1h windows for different time periods are correctly
    identified as independent records.
    """
    if snapshot_start_id is None:
        return None
    row = connection.execute(
        "SELECT id FROM printer_memory_windows"
        " WHERE token_id = ?"
        "   AND COALESCE(pair_id, -1) = COALESCE(?, -1)"
        "   AND window_kind = ?"
        "   AND snapshot_start_id = ?"
        " LIMIT 1",
        (token_id, pair_id, E2O_1H_WINDOW_KIND, snapshot_start_id),
    ).fetchone()
    return int(row["id"]) if row else None


def _insert_1h_memory_window(
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
    do_not_train: int = 0,
    data_quality_label: str = E2O_1H_REQUIRED_QUALITY,
    extra_context: dict[str, Any] | None = None,
) -> int:
    captured_at = str(snapshot["captured_at"])
    opened_at = window_start_at if window_start_at is not None else captured_at
    tracking_lane = str(snapshot["tracking_lane"])
    snapshot_mode = str(snapshot["snapshot_mode"])
    context: dict[str, Any] = {
        "snapshot_id": snapshot_id,
        "tracking_lane": tracking_lane,
        "snapshot_mode": snapshot_mode,
        "approved_mint": approved_mint,
        "created_by": E2O_1H_CREATED_BY,
    }
    if extra_context:
        context.update(extra_context)
    supporting_context = json.dumps(context, sort_keys=True)
    cursor = connection.execute(
        """
        INSERT INTO printer_memory_windows (
            token_id, pair_id, window_kind, opened_at, closed_at,
            memory_status, data_quality_label, do_not_train, window_status,
            supporting_context_json, created_by_phase, created_at, updated_at,
            window_start_at, window_end_at, snapshot_start_id, snapshot_end_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            token_id,
            pair_id,
            E2O_1H_WINDOW_KIND,
            opened_at,
            captured_at,
            E2O_1H_MEMORY_STATUS,
            data_quality_label,
            int(do_not_train),
            E2O_1H_WINDOW_STATUS,
            supporting_context,
            E2O_1H_CREATED_BY,
            now,
            now,
            window_start_at,
            window_end_at,
            snapshot_start_id,
            snapshot_end_id,
        ),
    )
    return int(cursor.lastrowid)


def close_1h_memory_window_from_snapshot(
    connection: sqlite3.Connection,
    snapshot_id: int,
    approved_mint: str,
    *,
    snapshot_start_id: int | None = None,
    expected_pair_id: int | None = None,
    continuation_of_15m: Mapping[str, Any] | None = None,
    consumed_15m_window_ids: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Close exactly one WINDOW_1H evidence window from a clean snapshot.

    Validates the closing snapshot before writing.  Idempotent: a second call
    with the same (token_id, pair_id, snapshot_start_id) returns
    E2O_1H_WINDOW_DUPLICATE without creating a new row.

    snapshot_start_id (optional): the first snapshot of the 1h continuation
    phase.  When provided, window_start_at / window_end_at /
    snapshot_start_id / snapshot_end_id are derived from real captured_at
    values and written so Lane Q can validate real elapsed time.

    expected_pair_id (optional): if provided, the closing snapshot's pair_id
    must match.  Mismatch → pair_drift_detected=True, close is blocked.

    No fake timestamps are ever written.  The writer does NOT block when
    elapsed < 2700s; lane_q_integrity_eligible=False is reported instead.

    Returns an audit dict.  Does NOT commit — caller is responsible.
    """
    row = _load_snapshot_with_token(connection, snapshot_id)
    if row is None:
        return {
            "e2o_1h_status": E2O_1H_STATUS_BLOCKED,
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
    pair_drift_detected: bool = False

    if row["source_status"] != E2O_1H_REQUIRED_SOURCE_STATUS:
        blocked_reasons.append(
            f"source_status must be {E2O_1H_REQUIRED_SOURCE_STATUS!r};"
            f" got {row['source_status']!r}"
        )

    if row["data_quality_label"] != E2O_1H_REQUIRED_QUALITY:
        blocked_reasons.append(
            f"data_quality_label must be {E2O_1H_REQUIRED_QUALITY!r};"
            f" got {row['data_quality_label']!r}"
        )

    if row["tracking_lane"] not in E2O_1H_ALLOWED_LANES:
        blocked_reasons.append(
            f"tracking_lane must be one of {sorted(E2O_1H_ALLOWED_LANES)!r};"
            f" got {row['tracking_lane']!r};"
            " WINDOW_5M_MICRO_EVENT is support-only; WINDOW_15M must use E2O"
        )

    if row["chain"] != E2O_1H_REQUIRED_CHAIN:
        blocked_reasons.append(
            f"chain must be {E2O_1H_REQUIRED_CHAIN!r}; got {row['chain']!r}"
        )

    if str(row["token_mint"]).lower() != approved_mint.lower():
        blocked_reasons.append(
            f"token_mint {row['token_mint']!r} does not match"
            f" approved_mint {approved_mint!r}"
        )

    # Pair drift check: if expected_pair_id provided, snapshot must match.
    actual_pair_id = int(row["pair_id"]) if row["pair_id"] is not None else None
    if expected_pair_id is not None and actual_pair_id != expected_pair_id:
        pair_drift_detected = True
        blocked_reasons.append(
            f"pair_drift_detected: expected pair_id={expected_pair_id},"
            f" snapshot has pair_id={actual_pair_id};"
            " WINDOW_1H cannot close across a pair address change"
        )

    if blocked_reasons:
        return {
            "e2o_1h_status": E2O_1H_STATUS_BLOCKED,
            "created": False,
            "blocked_reasons": blocked_reasons,
            "pair_drift_detected": pair_drift_detected,
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

    existing_id = _find_existing_1h_window(connection, token_id, pair_id, snapshot_start_id)
    if existing_id is not None:
        return {
            "e2o_1h_status": E2O_1H_STATUS_DUPLICATE,
            "created": False,
            "duplicate": True,
            "existing_window_id": existing_id,
            "token_id": token_id,
            "pair_id": pair_id,
            "approved_mint": approved_mint,
            "snapshot_id": snapshot_id,
            "pair_drift_detected": False,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memories_created": 0,
            "memory_windows_created": 0,
        }

    # Resolve canonical 1h integrity fields from real snapshot timestamps.
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
                    " window is not a real 45-minute continuation window and"
                    " will be blocked by Lane Q"
                )
    else:
        not_eligible_reason = (
            "snapshot_start_id not provided; window_start_at/window_end_at will be"
            " NULL — Lane Q will block this window with missing_window_start_at"
        )

    # ----- V2-6.2 continuity: anchor deadline + classify 15m->1h transition -----
    do_not_train = 0
    data_quality_label = E2O_1H_REQUIRED_QUALITY
    continuity_dict: dict[str, Any] | None = None
    closing_snapshot_lateness_seconds: float | None = None
    if continuation_of_15m is not None:
        fifteen_close_at = (
            continuation_of_15m.get("closed_at")
            or continuation_of_15m.get("window_end_at")
        )
        deadline = compute_1h_continuation_deadline(fifteen_close_at)
        if deadline is not None:
            close_captured_at = str(row["captured_at"])
            closing_snapshot_lateness_seconds = _compute_elapsed_seconds(
                deadline.isoformat(), close_captured_at
            )
            if closing_snapshot_lateness_seconds is None:
                return {
                    "e2o_1h_status": E2O_1H_STATUS_BLOCKED,
                    "created": False,
                    "blocked_reasons": ["closing_snapshot_timestamp_unparseable"],
                    "approved_mint": approved_mint,
                    "snapshot_id": snapshot_id,
                    "hard_locks": dict(_HARD_LOCKS),
                    "paper_decisions_created": 0,
                    "positions_created": 0,
                    "pnl_created": 0,
                    "memories_created": 0,
                    "memory_windows_created": 0,
                }
            if closing_snapshot_lateness_seconds < -0.001:
                return {
                    "e2o_1h_status": E2O_1H_STATUS_BLOCKED,
                    "created": False,
                    "blocked_reasons": [
                        "closing_snapshot_precedes_fixed_deadline: "
                        f"offset={closing_snapshot_lateness_seconds:.3f}s"
                    ],
                    "closing_snapshot_lateness_seconds": round(
                        closing_snapshot_lateness_seconds, 3
                    ),
                    "approved_mint": approved_mint,
                    "snapshot_id": snapshot_id,
                    "hard_locks": dict(_HARD_LOCKS),
                    "paper_decisions_created": 0,
                    "positions_created": 0,
                    "pnl_created": 0,
                    "memories_created": 0,
                    "memory_windows_created": 0,
                }
            if closing_snapshot_lateness_seconds < 0:
                closing_snapshot_lateness_seconds = 0.0
        one_h_link = {
            "run_id": continuation_of_15m.get("run_id"),
            "token_id": token_id,
            "pair_id": pair_id,
            "tracking_lane": str(row["tracking_lane"]),
            "continuation_of_window_id": continuation_of_15m.get("id"),
            "linked_closing_snapshot_id": continuation_of_15m.get("snapshot_end_id"),
            "linked_first_snapshot_id": resolved_snapshot_start_id,
            "first_snapshot_at": window_start_at,
            # deadline anchored to 15m close + 2700s (never first-snapshot + 2700s)
            "deadline_at": deadline.isoformat() if deadline is not None else None,
        }
        continuity = evaluate_15m_to_1h_continuity(
            continuation_of_15m, one_h_link,
            tracking_lane=str(row["tracking_lane"]),
            consumed_15m_window_ids=consumed_15m_window_ids,
        )
        continuity_dict = continuity.to_dict()
        if continuity.status == CONTINUITY_BLOCKED:
            return {
                "e2o_1h_status": E2O_1H_STATUS_CONTINUITY_BLOCKED,
                "created": False,
                "blocked_reasons": continuity.reasons,
                "continuity": continuity_dict,
                "approved_mint": approved_mint,
                "snapshot_id": snapshot_id,
                "hard_locks": dict(_HARD_LOCKS),
                "paper_decisions_created": 0,
                "positions_created": 0,
                "pnl_created": 0,
                "memories_created": 0,
                "memory_windows_created": 0,
            }
        # Anchor the window boundaries to the continuation phase:
        # start = 15m close, end = 15m close + 2700s (the deadline).
        if fifteen_close_at is not None and deadline is not None:
            window_start_at = str(fifteen_close_at)
            window_end_at = deadline.isoformat()
            elapsed_seconds = _compute_elapsed_seconds(window_start_at, window_end_at)
            lane_q_integrity_eligible = (
                elapsed_seconds is not None and elapsed_seconds >= _MIN_ELAPSED_SECONDS
            )
        if continuity.status == CONTINUITY_DIRTY or continuity.do_not_train:
            do_not_train = 1
            data_quality_label = _DIRTY_DATA_QUALITY

    now = _utc_now()
    window_id = _insert_1h_memory_window(
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
        do_not_train=do_not_train,
        data_quality_label=data_quality_label,
        extra_context=(
            {
                "continuity": continuity_dict,
                "continuation_run_id": continuation_of_15m.get("run_id"),
                "continuation_of_window_id": continuation_of_15m.get("id"),
                "linked_closing_snapshot_id": continuation_of_15m.get("snapshot_end_id"),
                "linked_first_snapshot_id": resolved_snapshot_start_id,
                "reuses_historical_window": False,
                "interpolated_first_snapshot": False,
                "observed_closing_snapshot_at": str(row["captured_at"]),
                "closing_snapshot_lateness_seconds": closing_snapshot_lateness_seconds,
            }
            if continuity_dict is not None and continuation_of_15m is not None
            else None
        ),
    )

    close_captured_at = str(row["captured_at"])
    opened_at_result = window_start_at if window_start_at is not None else close_captured_at

    result: dict[str, Any] = {
        "e2o_1h_status": E2O_1H_STATUS_CREATED,
        "created": True,
        "window_id": window_id,
        "window_kind": E2O_1H_WINDOW_KIND,
        "window_status": E2O_1H_WINDOW_STATUS,
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
        "closing_snapshot_lateness_seconds": closing_snapshot_lateness_seconds,
        "lane_q_integrity_eligible": lane_q_integrity_eligible,
        "pair_drift_detected": pair_drift_detected,
        "do_not_train": do_not_train,
        "hard_locks": dict(_HARD_LOCKS),
        "paper_decisions_created": 0,
        "positions_created": 0,
        "pnl_created": 0,
        "memories_created": 0,
        "memory_windows_created": 1,
    }
    if continuity_dict is not None:
        result["continuity"] = continuity_dict
    if not_eligible_reason is not None:
        result["not_eligible_reason"] = not_eligible_reason
    return result

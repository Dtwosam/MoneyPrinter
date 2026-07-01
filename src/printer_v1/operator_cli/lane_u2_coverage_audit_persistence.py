"""Lane U2 — Coverage Audit Persistence.

Evaluates snapshot cadence/gap coverage for WINDOW_15M candidates and
persists the results to the database.

Writes:
  - printer_snapshot_window_coverage: one row per window (idempotent upsert
    on token_id / pair_id / window_kind / opened_at / closed_at)
  - printer_memory_windows: updates coverage_state, actual_snapshot_count,
    expected_snapshot_count, missing_snapshot_count
  - printer_snapshot_gap_audits: one row per inter-snapshot gap (idempotent
    on token_id / pair_id / actual_captured_at)

Classification outcomes per window:
  COVERAGE_PASS     — cadence policy satisfied; window is eligible for E2Z
  COVERAGE_BLOCKED  — cadence violation; CLEAN_MEMORY must be refused
  COVERAGE_UNKNOWN  — 0 snapshots in range; status depends on production_mode

Lane-level outcomes:
  LANE_U2_COMPLETED — evaluation ran for all requested windows
  LANE_U2_BLOCKED   — operator_approved not set or db_path missing/invalid

Permanently locked (no unlock path in this module):
  memory creation, retrieval activation, paper decisions, BUY/SELL/HOLD,
  positions, PnL, live trading, wallet/private keys, source fetching,
  scheduler runtime expansion, paid APIs, scoring/ranking/confidence,
  embeddings/vectors, 5m as main outcome memory.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from printer_v1.snapshots.cadence_policy import (
    CADENCE_POLICY_BLOCKED,
    CADENCE_POLICY_PASS,
    CADENCE_POLICY_UNKNOWN,
    CadencePolicyEvaluation,
    cadence_policy_evaluation_to_dict,
    evaluate_cadence_policy,
    get_policy,
)


COVERAGE_STATE_PASS: str = "COVERAGE_PASS"
COVERAGE_STATE_BLOCKED: str = "COVERAGE_BLOCKED"
COVERAGE_STATE_UNKNOWN: str = "COVERAGE_UNKNOWN"

LANE_U2_STATUS_COMPLETED: str = "LANE_U2_COMPLETED"
LANE_U2_STATUS_BLOCKED: str = "LANE_U2_BLOCKED"

LANE_U2_NAME: str = "Lane U2 — Coverage Audit Persistence"

_HARD_LOCKS: dict[str, bool] = {
    "no_memory_creation": True,
    "no_retrieval_activation": True,
    "no_paper_decisions": True,
    "no_buy_sell_hold": True,
    "no_positions": True,
    "no_pnl": True,
    "no_live_trading": True,
    "no_wallet_private_key": True,
    "no_paid_api": True,
    "no_source_fetching": True,
    "no_scheduler_runtime_expansion": True,
    "no_scoring_ranking_confidence": True,
    "no_embeddings_vectors": True,
    "no_5m_main_outcome": True,
}

# data_quality_label values allowed by the DB CHECK constraint
_DQ_CLEAN: str = "CLEAN_DATA"
_DQ_MISSING: str = "MISSING_CRITICAL_DATA"

# memory_status values allowed by the DB CHECK constraint
_MS_PARTIAL: str = "PARTIAL_MEMORY"
_MS_DIRTY: str = "DIRTY_MEMORY"
_MS_AUDIT: str = "AUDIT_ONLY"

# source_status values allowed by printer_snapshot_gap_audits CHECK
_VALID_SOURCE_STATUSES: frozenset[str] = frozenset(
    {"COMPLETE", "PARTIAL", "FAILED", "STALE", "CONFLICTING"}
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coverage_state_from_eval(ev: CadencePolicyEvaluation) -> str:
    if ev.cadence_policy_status == CADENCE_POLICY_PASS:
        return COVERAGE_STATE_PASS
    if ev.cadence_policy_status == CADENCE_POLICY_BLOCKED:
        return COVERAGE_STATE_BLOCKED
    return COVERAGE_STATE_UNKNOWN


def _memory_status_for_coverage(state: str) -> str:
    if state == COVERAGE_STATE_PASS:
        return _MS_PARTIAL
    if state == COVERAGE_STATE_BLOCKED:
        return _MS_DIRTY
    return _MS_AUDIT


def _data_quality_for_coverage(state: str) -> str:
    return _DQ_CLEAN if state == COVERAGE_STATE_PASS else _DQ_MISSING


def _do_not_train_for_coverage(state: str) -> int:
    return 0 if state == COVERAGE_STATE_PASS else 1


def _gap_label(gap_seconds: float, target: int, max_gap: int) -> str:
    if gap_seconds <= target:
        return "NORMAL_GAP"
    if gap_seconds <= max_gap:
        return "LARGE_GAP"
    return "EXCESSIVE_GAP"


def _gap_coverage_label(gap_seconds: float, target: int, max_gap: int) -> str:
    if gap_seconds <= target:
        return "COVERED"
    if gap_seconds <= max_gap:
        return "PARTIAL_COVERAGE"
    return "MISSED"


def _safe_source_status(raw: Any) -> str:
    s = str(raw or "COMPLETE")
    return s if s in _VALID_SOURCE_STATUSES else "COMPLETE"


def _fetch_window_row(conn: sqlite3.Connection, window_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, token_id, pair_id, window_kind,
               window_start_at, window_end_at,
               opened_at, closed_at,
               snapshot_start_id, snapshot_end_id,
               data_quality_label, memory_status,
               supporting_context_json
        FROM printer_memory_windows
        WHERE id = ?
        """,
        (window_id,),
    ).fetchone()
    return dict(row) if row else None


def _derive_tracking_lane(
    win_row: dict[str, Any],
    snapshots: list[dict[str, Any]],
    conn: sqlite3.Connection | None = None,
    token_id: int | None = None,
) -> str | None:
    """Derive the cadence-lane for a window from reliable evidence.

    Priority:
      1. supporting_context_json.tracking_lane (most authoritative)
      2. First TRACK_FAST / TRACK_NORMAL value found in the window's snapshots
      3. printer_tokens.token_status — ONLY if it is itself a cadence lane
         ("TRACK_FAST" or "TRACK_NORMAL"); the lifecycle value "TRACKING" is
         rejected here so it is never forwarded to get_policy().

    "TRACKING" is a lifecycle/collection-state value, not a cadence lane.
    Passing it to get_policy("WINDOW_15M", "TRACKING") returns None, which
    makes the evaluation fall back to CADENCE_POLICY_UNKNOWN — incorrect.
    """
    _VALID = frozenset({"TRACK_FAST", "TRACK_NORMAL"})

    # 1. supporting_context_json
    ctx_raw = win_row.get("supporting_context_json")
    if ctx_raw:
        try:
            ctx = json.loads(ctx_raw)
            lane = ctx.get("tracking_lane")
            if lane in _VALID:
                return str(lane)
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    # 2. Snapshot tracking_lane column
    for snap in snapshots:
        lane = snap.get("tracking_lane")
        if lane in _VALID:
            return str(lane)

    # 3. Token status — only when it is explicitly a cadence lane
    if conn is not None and token_id is not None:
        try:
            row = conn.execute(
                "SELECT token_status FROM printer_tokens WHERE id = ? LIMIT 1",
                (int(token_id),),
            ).fetchone()
            if row and row[0] in _VALID:
                return str(row[0])
        except Exception:
            pass

    return None


def _fetch_snapshots_in_range(
    conn: sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    snap_start: int,
    snap_end: int,
) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT id, captured_at, source_status, data_quality_label,
                   tracking_lane,
                   COALESCE(snapshot_mode, 'UNKNOWN') AS snapshot_mode
            FROM printer_token_snapshots
            WHERE token_id = ?
              AND COALESCE(pair_id, -1) = COALESCE(?, -1)
              AND id BETWEEN ? AND ?
            ORDER BY captured_at ASC, id ASC
            """,
            (token_id, pair_id, snap_start, snap_end),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _upsert_coverage_row(
    conn: sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    window_kind: str,
    tracking_lane: str,
    opened_at: str,
    closed_at: str,
    ev: CadencePolicyEvaluation,
    coverage_state: str,
    policy_min_snapshots: int,
    now: str,
) -> None:
    actual = ev.actual_snapshot_count
    expected = policy_min_snapshots
    missing = max(0, expected - actual)
    max_gap_int = (
        int(ev.actual_max_gap_seconds)
        if ev.actual_max_gap_seconds is not None
        else -1
    )
    coverage_label = ev.cadence_policy_status  # PASS / BLOCKED / UNKNOWN
    memory_status = _memory_status_for_coverage(coverage_state)
    data_quality = _data_quality_for_coverage(coverage_state)
    do_not_train = _do_not_train_for_coverage(coverage_state)

    existing = conn.execute(
        """
        SELECT id FROM printer_snapshot_window_coverage
        WHERE token_id = ?
          AND COALESCE(pair_id, -1) = COALESCE(?, -1)
          AND window_kind = ?
          AND opened_at = ?
          AND closed_at = ?
        LIMIT 1
        """,
        (token_id, pair_id, window_kind, opened_at, closed_at),
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE printer_snapshot_window_coverage
            SET tracking_lane = ?,
                expected_snapshot_count = ?,
                actual_snapshot_count = ?,
                missing_snapshot_count = ?,
                max_gap_seconds = ?,
                coverage_label = ?,
                memory_status = ?,
                data_quality_label = ?,
                do_not_train = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                tracking_lane, expected, actual, missing, max_gap_int,
                coverage_label, memory_status, data_quality, do_not_train,
                now, existing[0],
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO printer_snapshot_window_coverage (
                token_id, pair_id, window_kind, tracking_lane,
                opened_at, closed_at,
                expected_snapshot_count, actual_snapshot_count,
                missing_snapshot_count, max_gap_seconds,
                coverage_label, memory_status, data_quality_label,
                do_not_train, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token_id, pair_id, window_kind, tracking_lane,
                opened_at, closed_at,
                expected, actual, missing, max_gap_int,
                coverage_label, memory_status, data_quality, do_not_train,
                now, now,
            ),
        )


def _update_window_coverage_fields(
    conn: sqlite3.Connection,
    window_id: int,
    ev: CadencePolicyEvaluation,
    coverage_state: str,
    policy_min_snapshots: int,
    now: str,
) -> None:
    actual = ev.actual_snapshot_count
    expected = policy_min_snapshots
    missing = max(0, expected - actual)

    if coverage_state == COVERAGE_STATE_BLOCKED:
        # Downgrade quality fields so E2X/E2Y DB queries naturally exclude
        # this window from the clean-memory candidate set.  A coverage-blocked
        # window has snapshot gaps or count violations that disqualify it; it
        # must not count toward the 5-window E2Y gate.
        conn.execute(
            """
            UPDATE printer_memory_windows
            SET coverage_state = ?,
                actual_snapshot_count = ?,
                expected_snapshot_count = ?,
                missing_snapshot_count = ?,
                data_quality_label = ?,
                memory_status = ?,
                do_not_train = 1,
                updated_at = ?
            WHERE id = ?
            """,
            (
                coverage_state, actual, expected, missing,
                _DQ_MISSING, _MS_DIRTY, now, window_id,
            ),
        )
    else:
        # COVERAGE_PASS: no change to data_quality/memory_status (already CLEAN/PARTIAL).
        # COVERAGE_UNKNOWN: keep as-is; non-prod mode allows unknown through E2Y.
        conn.execute(
            """
            UPDATE printer_memory_windows
            SET coverage_state = ?,
                actual_snapshot_count = ?,
                expected_snapshot_count = ?,
                missing_snapshot_count = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (coverage_state, actual, expected, missing, now, window_id),
        )


def _write_gap_audits(
    conn: sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    snapshots: list[dict[str, Any]],
    policy: Any,
    now: str,
) -> int:
    """Write one gap-audit row per inter-snapshot interval. Returns rows inserted."""
    if policy is None or len(snapshots) < 2:
        return 0

    tracking_lane = str(policy.tracking_lane)
    target = policy.target_snapshot_interval_seconds
    max_gap = policy.max_clean_snapshot_gap_seconds
    inserted = 0

    for i in range(len(snapshots) - 1):
        snap_before = snapshots[i]
        snap_after = snapshots[i + 1]

        try:
            t_before_raw = str(snap_before["captured_at"]).replace("Z", "+00:00")
            t_after_raw = str(snap_after["captured_at"]).replace("Z", "+00:00")
            t_before = datetime.fromisoformat(t_before_raw)
            t_after = datetime.fromisoformat(t_after_raw)
        except (ValueError, TypeError):
            continue

        gap_secs = (t_after - t_before).total_seconds()
        expected_ts = (
            t_before + timedelta(seconds=target)
        ).isoformat()
        actual_ts = str(snap_after["captured_at"])

        # Idempotency: one gap row per (token, pair, actual_captured_at)
        exists = conn.execute(
            """
            SELECT 1 FROM printer_snapshot_gap_audits
            WHERE token_id = ?
              AND COALESCE(pair_id, -1) = COALESCE(?, -1)
              AND actual_captured_at = ?
            LIMIT 1
            """,
            (token_id, pair_id, actual_ts),
        ).fetchone()
        if exists:
            continue

        snapshot_mode = str(snap_before.get("snapshot_mode") or "UNKNOWN")
        gap_lbl = _gap_label(gap_secs, target, max_gap)
        cov_lbl = _gap_coverage_label(gap_secs, target, max_gap)
        source_status = _safe_source_status(snap_after.get("source_status"))
        data_quality = str(snap_after.get("data_quality_label") or _DQ_CLEAN)

        conn.execute(
            """
            INSERT INTO printer_snapshot_gap_audits (
                token_id, pair_id, tracking_lane, snapshot_mode,
                expected_captured_at, actual_captured_at,
                gap_seconds, snapshot_gap_label, coverage_label,
                source_status, data_quality_label, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token_id, pair_id, tracking_lane, snapshot_mode,
                expected_ts, actual_ts,
                int(gap_secs), gap_lbl, cov_lbl,
                source_status, data_quality, now,
            ),
        )
        inserted += 1

    return inserted


def _blocked_result(reasons: list[str], window_ids: list[int]) -> dict[str, Any]:
    return {
        "lane_u2_status": LANE_U2_STATUS_BLOCKED,
        "lane": LANE_U2_NAME,
        "operator_approved": False,
        "blocked_reasons": reasons,
        "coverage_pass_ids": [],
        "coverage_blocked_ids": list(window_ids),
        "coverage_unknown_ids": [],
        "coverage_pass_count": 0,
        "coverage_blocked_count": len(window_ids),
        "coverage_unknown_count": 0,
        "coverage_rows_written": 0,
        "gap_audit_rows_written": 0,
        "window_coverage_results": [],
        "zero_clean_memories_valid": True,
        "hard_locks": dict(_HARD_LOCKS),
        "retrieval_activated": False,
        "paper_decisions_created": 0,
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "positions_created": 0,
        "pnl_created": 0,
    }


def persist_coverage_for_windows(
    db_path: str | Path | None,
    window_ids: list[int],
    *,
    operator_approved: bool = False,
    production_mode: bool = False,
) -> dict[str, Any]:
    """Evaluate snapshot coverage for each window and persist results to DB.

    For each window_id, this function:
      1. Fetches the window row and its referenced snapshots.
      2. Evaluates cadence/gap policy (via evaluate_cadence_policy).
      3. Upserts a printer_snapshot_window_coverage row.
      4. Updates printer_memory_windows coverage fields.
      5. Writes printer_snapshot_gap_audits rows (one per inter-snapshot gap).

    Coverage states:
      COVERAGE_PASS    — cadence policy satisfied; eligible for E2Z
      COVERAGE_BLOCKED — gap or count violation; block clean memory
      COVERAGE_UNKNOWN — 0 snapshots in range (fixture compat in non-prod)

    production_mode=True: UNKNOWN treated same as BLOCKED by callers.
    production_mode=False (default): UNKNOWN windows are allowed through.

    Returns a summary dict with coverage_pass_ids, coverage_blocked_ids,
    coverage_unknown_ids, and per-window results.
    """
    if not operator_approved:
        return _blocked_result(["operator_approved must be True"], window_ids)

    if db_path is None:
        return _blocked_result(["db_path is required"], window_ids)

    p = Path(db_path)
    if not p.is_file():
        return _blocked_result([f"db_path not found: {db_path}"], window_ids)

    db_path_str = str(p)

    pass_ids: list[int] = []
    blocked_ids: list[int] = []
    unknown_ids: list[int] = []
    window_results: list[dict[str, Any]] = []
    total_coverage_rows = 0
    total_gap_rows = 0

    conn = sqlite3.connect(db_path_str)
    conn.row_factory = sqlite3.Row
    try:
        for wid in window_ids:
            now = _utc_now()
            win = _fetch_window_row(conn, wid)
            if win is None:
                blocked_ids.append(wid)
                window_results.append({
                    "window_id": wid,
                    "coverage_state": COVERAGE_STATE_BLOCKED,
                    "blocked_reason": "window_not_found_in_db",
                    "actual_snapshot_count": 0,
                    "expected_snapshot_count": 0,
                    "actual_max_gap_seconds": None,
                    "cadence_policy_status": CADENCE_POLICY_BLOCKED,
                    "tracking_lane": None,
                    "gap_audit_rows_written": 0,
                })
                continue

            token_id: int = int(win["token_id"])
            pair_id: int | None = (
                int(win["pair_id"]) if win["pair_id"] is not None else None
            )
            window_kind: str = str(win["window_kind"])

            # Canonical 15m boundary; fall back to opened_at/closed_at
            win_start = win["window_start_at"] or win["opened_at"]
            win_end = win["window_end_at"] or win["closed_at"]

            # Use canonical boundary for the coverage row timestamp columns
            opened_at = win["window_start_at"] or win["opened_at"]
            closed_at = win["window_end_at"] or win["closed_at"]

            snap_start = win["snapshot_start_id"]
            snap_end = win["snapshot_end_id"]

            # Fetch snapshots first so _derive_tracking_lane can inspect them
            snapshots: list[dict[str, Any]] = []
            if snap_start is not None and snap_end is not None:
                snapshots = _fetch_snapshots_in_range(
                    conn, token_id, pair_id, int(snap_start), int(snap_end)
                )

            tracking_lane = _derive_tracking_lane(win, snapshots, conn, token_id)
            policy = get_policy(window_kind, tracking_lane)

            ev = evaluate_cadence_policy(
                snapshots, win_start, win_end, policy,
                production_mode=production_mode,
            )

            coverage_state = _coverage_state_from_eval(ev)
            policy_min = (
                policy.minimum_required_snapshots if policy is not None else 0
            )
            tracking_lane_str = tracking_lane or (
                policy.tracking_lane if policy is not None else "UNKNOWN"
            )

            # --- Persist printer_snapshot_window_coverage ---
            if opened_at and closed_at:
                _upsert_coverage_row(
                    conn, token_id, pair_id, window_kind,
                    tracking_lane_str, opened_at, closed_at,
                    ev, coverage_state, policy_min, now,
                )
                total_coverage_rows += 1

            # --- Update printer_memory_windows coverage columns ---
            _update_window_coverage_fields(
                conn, wid, ev, coverage_state, policy_min, now
            )

            # --- Write gap audits between consecutive snapshots ---
            gap_rows = _write_gap_audits(
                conn, token_id, pair_id, snapshots, policy, now
            )
            total_gap_rows += gap_rows

            if coverage_state == COVERAGE_STATE_PASS:
                pass_ids.append(wid)
            elif coverage_state == COVERAGE_STATE_BLOCKED:
                blocked_ids.append(wid)
            else:
                unknown_ids.append(wid)

            window_results.append({
                "window_id": wid,
                "coverage_state": coverage_state,
                "actual_snapshot_count": ev.actual_snapshot_count,
                "expected_snapshot_count": policy_min,
                "actual_max_gap_seconds": ev.actual_max_gap_seconds,
                "cadence_policy_status": ev.cadence_policy_status,
                "blocked_reason": ev.blocked_reason,
                "tracking_lane": tracking_lane,
                "gap_audit_rows_written": gap_rows,
                "cadence_policy_evaluation": cadence_policy_evaluation_to_dict(ev),
            })

        conn.commit()

    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return _blocked_result([f"db_error: {exc}"], window_ids)
    finally:
        conn.close()

    return {
        "lane_u2_status": LANE_U2_STATUS_COMPLETED,
        "lane": LANE_U2_NAME,
        "operator_approved": True,
        "production_mode": production_mode,
        "db_path": db_path_str,
        "blocked_reasons": [],
        "coverage_pass_ids": pass_ids,
        "coverage_blocked_ids": blocked_ids,
        "coverage_unknown_ids": unknown_ids,
        "coverage_pass_count": len(pass_ids),
        "coverage_blocked_count": len(blocked_ids),
        "coverage_unknown_count": len(unknown_ids),
        "coverage_rows_written": total_coverage_rows,
        "gap_audit_rows_written": total_gap_rows,
        "window_coverage_results": window_results,
        "zero_clean_memories_valid": True,
        "hard_locks": dict(_HARD_LOCKS),
        "retrieval_activated": False,
        "paper_decisions_created": 0,
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "positions_created": 0,
        "pnl_created": 0,
        "trade_events_created": 0,
    }

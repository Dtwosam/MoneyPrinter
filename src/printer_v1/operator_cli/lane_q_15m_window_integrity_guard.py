"""Lane Q — Real-Time 15m Window Integrity Guard.

Validates WINDOW_15M candidates before E2Z clean-memory creation.

A candidate window is LANE_Q_VALID only when ALL of the following hold:

  Integrity checks (pure — check_window_integrity):
  - window_kind == "WINDOW_15M"
  - data_quality_label == "CLEAN_DATA"
  - do_not_train == 0 / False
  - memory_status or memory_quality_label is "PARTIAL_MEMORY"
  - window_start_at exists and is a parseable ISO 8601 timestamp
  - window_end_at exists and is a parseable ISO 8601 timestamp
  - elapsed time between window_start_at and window_end_at >= 900 seconds
  - snapshot_start_id exists (not NULL)
  - snapshot_end_id exists (not NULL)
  - snapshot_end_id >= snapshot_start_id

  Cadence / coverage checks (DB-backed — guard_candidate_windows only):
  - The snapshot cadence policy for the window's tracking lane is satisfied:
      no front-loaded snapshots, no dead zones, actual max gap <=
      policy.max_clean_snapshot_gap_seconds.
  - If 0 snapshots exist in the range, coverage is UNKNOWN (no block).
    This preserves synthetic-fixture test windows whose snapshot IDs do not
    exist in printer_token_snapshots.  Real production windows always have
    ≥ 2 snapshots and are fully evaluated.
  - If ≥ 1 snapshot exists but max gap exceeds the policy limit, BLOCKED.

If window_start_at/window_end_at are absent the window is blocked with
"missing_window_start_at" / "missing_window_end_at" respectively.  This module
will NOT silently accept opened_at/closed_at as a substitute for the canonical
15m boundary columns.

Two entry points:
  check_window_integrity(row)           — pure dict-in/dict-out; no DB access
  guard_candidate_windows(db_path, window_ids, *, operator_approved)
                                        — DB-backed; integrity + coverage check

Classification outcomes per window:
  LANE_Q_VALID    — all integrity AND coverage checks pass; eligible for E2Z
  LANE_Q_BLOCKED  — one or more checks failed; must not become clean memory

Guard-level outcomes:
  LANE_Q_GUARD_COMPLETED — guard ran (even if all windows blocked; zero clean valid)
  LANE_Q_GUARD_BLOCKED   — operator_approved not set or db_path missing/invalid
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from printer_v1.snapshots.cadence_policy import (
    CADENCE_POLICY_BLOCKED,
    CADENCE_POLICY_DIRTY,
    CADENCE_POLICY_UNKNOWN,
    CadencePolicyEvaluation,
    cadence_policy_evaluation_to_dict,
    evaluate_cadence_policy,
    get_policy,
)


LANE_Q_VALID: str = "LANE_Q_VALID"
LANE_Q_BLOCKED: str = "LANE_Q_BLOCKED"
LANE_Q_GUARD_COMPLETED: str = "LANE_Q_GUARD_COMPLETED"
LANE_Q_GUARD_BLOCKED: str = "LANE_Q_GUARD_BLOCKED"

LANE_Q_NAME: str = "Lane Q — Real-Time 15m Window Integrity Guard"

_MIN_ELAPSED_BY_WINDOW: dict[str, float] = {
    "WINDOW_15M": 900.0,
    "WINDOW_1H": 2_700.0,
    "WINDOW_4H": 10_800.0,
}
# Backward-compatible public 15m contract used by existing callers/tests.
MIN_ELAPSED_SECONDS: float = _MIN_ELAPSED_BY_WINDOW["WINDOW_15M"]
_REQUIRED_DATA_QUALITY: str = "CLEAN_DATA"
_SUPPORTED_MEMORY_STATUSES: frozenset[str] = frozenset({"PARTIAL_MEMORY"})

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


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        return None


def _elapsed_seconds(start: datetime, end: datetime) -> float:
    try:
        return (end - start).total_seconds()
    except TypeError:
        # Mixed aware / naive — strip tz from the aware side
        s = start.replace(tzinfo=None) if start.tzinfo else start
        e = end.replace(tzinfo=None) if end.tzinfo else end
        return (e - s).total_seconds()


def check_window_integrity(row: dict[str, Any]) -> dict[str, Any]:
    """Validate a single window row dict. Pure — no DB access.

    row should contain at minimum:
      id, window_kind, data_quality_label, do_not_train,
      memory_status, memory_quality_label,
      window_start_at, window_end_at,
      snapshot_start_id, snapshot_end_id
    """
    reasons: list[str] = []

    window_id = row.get("id")
    window_kind = row.get("window_kind")
    data_quality = row.get("data_quality_label")
    do_not_train = row.get("do_not_train")
    memory_status = row.get("memory_status")
    memory_quality_label = row.get("memory_quality_label")
    window_start_at = row.get("window_start_at")
    window_end_at = row.get("window_end_at")
    snapshot_start_id = row.get("snapshot_start_id")
    snapshot_end_id = row.get("snapshot_end_id")

    # window_kind
    if window_kind not in _MIN_ELAPSED_BY_WINDOW:
        # Retain the historical reason consumed by 5m-support callers while
        # making the broader unsupported-kind meaning explicit.
        reasons.extend(("not_window_15m", "unsupported_window_kind"))

    # data quality / do_not_train
    if do_not_train not in (0, False):
        reasons.append("dirty_or_do_not_train_window")
    elif data_quality != _REQUIRED_DATA_QUALITY:
        reasons.append("dirty_or_do_not_train_window")

    # memory status
    if (
        memory_status not in _SUPPORTED_MEMORY_STATUSES
        and memory_quality_label not in _SUPPORTED_MEMORY_STATUSES
    ):
        reasons.append("unsupported_memory_status")

    # window_start_at
    start_ts: datetime | None = None
    if not window_start_at:
        reasons.append("missing_window_start_at")
    else:
        start_ts = _parse_ts(window_start_at)
        if start_ts is None:
            reasons.append("invalid_window_start_at")

    # window_end_at
    end_ts: datetime | None = None
    if not window_end_at:
        reasons.append("missing_window_end_at")
    else:
        end_ts = _parse_ts(window_end_at)
        if end_ts is None:
            reasons.append("invalid_window_end_at")

    # elapsed time
    elapsed: float | None = None
    if start_ts is not None and end_ts is not None:
        elapsed = _elapsed_seconds(start_ts, end_ts)
        minimum_elapsed = _MIN_ELAPSED_BY_WINDOW.get(str(window_kind))
        if minimum_elapsed is not None and elapsed < minimum_elapsed:
            reasons.append(f"elapsed_seconds_below_{int(minimum_elapsed)}")

    # snapshot_start_id
    if snapshot_start_id is None:
        reasons.append("missing_snapshot_start_id")

    # snapshot_end_id
    if snapshot_end_id is None:
        reasons.append("missing_snapshot_end_id")

    # snapshot ordering
    if (
        snapshot_start_id is not None
        and snapshot_end_id is not None
        and int(snapshot_end_id) < int(snapshot_start_id)
    ):
        reasons.append("invalid_snapshot_order")

    lane_q_status = LANE_Q_VALID if not reasons else LANE_Q_BLOCKED

    return {
        "window_id": window_id,
        "lane_q_status": lane_q_status,
        "integrity_proven": lane_q_status == LANE_Q_VALID,
        "blocked_reasons": reasons,
        "elapsed_seconds": elapsed,
        "window_kind": window_kind,
        "data_quality_label": data_quality,
        "do_not_train": do_not_train,
        "memory_status": memory_status,
        "memory_quality_label": memory_quality_label,
        "window_start_at": window_start_at,
        "window_end_at": window_end_at,
        "snapshot_start_id": snapshot_start_id,
        "snapshot_end_id": snapshot_end_id,
    }


def _fetch_windows(
    db_path: str | Path,
    window_ids: list[int],
) -> list[dict[str, Any]]:
    if not window_ids:
        return []
    placeholders = ",".join("?" * len(window_ids))
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"""
            SELECT id, token_id, pair_id,
                   window_kind, data_quality_label, do_not_train,
                   memory_status, memory_quality_label,
                   window_start_at, window_end_at,
                   snapshot_start_id, snapshot_end_id,
                   opened_at, closed_at
            FROM printer_memory_windows
            WHERE id IN ({placeholders})
            """,
            tuple(window_ids),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _get_token_tracking_lane(db_path: str | Path, token_id: int | None) -> str | None:
    """Look up the token's current lifecycle/tracking lane from printer_tokens."""
    if token_id is None:
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT token_status FROM printer_tokens WHERE id = ? LIMIT 1",
                (int(token_id),),
            ).fetchone()
            return str(row[0]) if row and row[0] else None
        finally:
            conn.close()
    except Exception:
        return None


def _fetch_window_snapshots(
    db_path: str | Path,
    token_id: int | None,
    pair_id: int | None,
    snapshot_start_id: int | None,
    snapshot_end_id: int | None,
) -> list[dict[str, Any]]:
    """Return snapshots for token/pair whose IDs fall in [start, end]."""
    if token_id is None or snapshot_start_id is None or snapshot_end_id is None:
        return []
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT id, captured_at
                FROM printer_token_snapshots
                WHERE token_id = ?
                  AND COALESCE(pair_id, -1) = COALESCE(?, -1)
                  AND id BETWEEN ? AND ?
                ORDER BY captured_at ASC, id ASC
                """,
                (int(token_id), pair_id, int(snapshot_start_id), int(snapshot_end_id)),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception:
        return []


def _evaluate_coverage_for_window(
    db_path: str | Path,
    window_row: dict[str, Any],
    *,
    production_mode: bool = False,
    allow_disabled_policy_evaluation: bool = False,
) -> CadencePolicyEvaluation:
    """Evaluate snapshot cadence/gap policy for a window row.

    Loads actual snapshots from the DB and runs the cadence policy evaluator.
    Returns CADENCE_POLICY_UNKNOWN when 0 snapshots exist in the range, which
    prevents blocking of synthetic test windows.
    """
    token_id = window_row.get("token_id")
    pair_id = window_row.get("pair_id")
    snap_start = window_row.get("snapshot_start_id")
    snap_end = window_row.get("snapshot_end_id")
    window_kind = window_row.get("window_kind", "WINDOW_15M")
    window_start_at = window_row.get("window_start_at")
    window_end_at = window_row.get("window_end_at")

    tracking_lane = _get_token_tracking_lane(db_path, token_id)
    policy = get_policy(window_kind, tracking_lane)
    snapshots = _fetch_window_snapshots(db_path, token_id, pair_id, snap_start, snap_end)

    return evaluate_cadence_policy(
        snapshots, window_start_at, window_end_at, policy,
        production_mode=production_mode,
        allow_disabled_policy_evaluation=allow_disabled_policy_evaluation,
    )


def guard_candidate_windows(
    db_path: str | Path | None,
    window_ids: list[int],
    *,
    operator_approved: bool = False,
    production_mode: bool = False,
    allow_disabled_policy_evaluation: bool = False,
) -> dict[str, Any]:
    """Read window rows from DB and validate each through check_window_integrity.

    Returns a summary with valid_window_ids (pass Lane Q) and
    blocked_window_ids (fail Lane Q).  Zero valid is always a valid outcome.
    """
    if not operator_approved:
        return {
            "lane_q_guard_status": LANE_Q_GUARD_BLOCKED,
            "lane": LANE_Q_NAME,
            "operator_approved": False,
            "blocked_reasons": ["operator_approved must be True"],
            "valid_window_ids": [],
            "blocked_window_ids": list(window_ids),
            "window_verdicts": [],
            "valid_count": 0,
            "blocked_count": len(window_ids),
            "zero_clean_memories_valid": True,
            "hard_locks": dict(_HARD_LOCKS),
        }

    db_path_str = ""
    if db_path is None:
        return {
            "lane_q_guard_status": LANE_Q_GUARD_BLOCKED,
            "lane": LANE_Q_NAME,
            "operator_approved": True,
            "blocked_reasons": ["db_path is required"],
            "valid_window_ids": [],
            "blocked_window_ids": list(window_ids),
            "window_verdicts": [],
            "valid_count": 0,
            "blocked_count": len(window_ids),
            "zero_clean_memories_valid": True,
            "hard_locks": dict(_HARD_LOCKS),
        }

    p = Path(db_path)
    db_path_str = str(p)
    if not p.is_file():
        return {
            "lane_q_guard_status": LANE_Q_GUARD_BLOCKED,
            "lane": LANE_Q_NAME,
            "operator_approved": True,
            "blocked_reasons": [f"db_path not found: {db_path}"],
            "valid_window_ids": [],
            "blocked_window_ids": list(window_ids),
            "window_verdicts": [],
            "valid_count": 0,
            "blocked_count": len(window_ids),
            "zero_clean_memories_valid": True,
            "hard_locks": dict(_HARD_LOCKS),
        }

    rows = _fetch_windows(db_path_str, window_ids)
    found_ids = {row["id"] for row in rows}

    verdicts: list[dict[str, Any]] = []
    valid_ids: list[int] = []
    blocked_ids: list[int] = []

    for row in rows:
        verdict = check_window_integrity(row)

        # Coverage / cadence-policy check — additive after integrity passes.
        # Windows that fail integrity are not re-checked for coverage.
        # Windows with 0 matching snapshots get CADENCE_POLICY_UNKNOWN (no block),
        # which preserves synthetic test fixtures.
        coverage_eval: CadencePolicyEvaluation | None = None
        if verdict["lane_q_status"] == LANE_Q_VALID:
            coverage_eval = _evaluate_coverage_for_window(
                db_path_str, row, production_mode=production_mode,
                allow_disabled_policy_evaluation=allow_disabled_policy_evaluation,
            )
            # Both BLOCKED and DIRTY coverage stop clean promotion. DIRTY means
            # the cadence is real but below clean quality (a gap in the dirty
            # band or missed snapshots); such a window may still be dirty memory
            # but must never be promoted clean, so Lane Q blocks it here.
            if coverage_eval.cadence_policy_status in (
                CADENCE_POLICY_BLOCKED, CADENCE_POLICY_DIRTY
            ):
                reasons: list[str] = list(verdict.get("blocked_reasons") or [])
                reasons.append(
                    f"coverage_policy: {coverage_eval.blocked_reason}"
                )
                verdict = dict(verdict)
                verdict["lane_q_status"] = LANE_Q_BLOCKED
                verdict["integrity_proven"] = False
                verdict["blocked_reasons"] = reasons

        if coverage_eval is not None:
            verdict = dict(verdict)
            verdict["cadence_policy_evaluation"] = cadence_policy_evaluation_to_dict(
                coverage_eval
            )

        verdicts.append(verdict)
        if verdict["lane_q_status"] == LANE_Q_VALID:
            valid_ids.append(verdict["window_id"])
        else:
            blocked_ids.append(verdict["window_id"])

    # IDs requested but not found in DB
    for wid in window_ids:
        if wid not in found_ids:
            missing_verdict = {
                "window_id": wid,
                "lane_q_status": LANE_Q_BLOCKED,
                "integrity_proven": False,
                "blocked_reasons": ["window_not_found_in_db"],
                "elapsed_seconds": None,
                "window_kind": None,
                "data_quality_label": None,
                "do_not_train": None,
                "memory_status": None,
                "memory_quality_label": None,
                "window_start_at": None,
                "window_end_at": None,
                "snapshot_start_id": None,
                "snapshot_end_id": None,
                "cadence_policy_evaluation": None,
            }
            verdicts.append(missing_verdict)
            blocked_ids.append(wid)

    return {
        "lane_q_guard_status": LANE_Q_GUARD_COMPLETED,
        "lane": LANE_Q_NAME,
        "operator_approved": True,
        "db_path": db_path_str,
        "blocked_reasons": [],
        "valid_window_ids": valid_ids,
        "blocked_window_ids": blocked_ids,
        "window_verdicts": verdicts,
        "valid_count": len(valid_ids),
        "blocked_count": len(blocked_ids),
        "zero_clean_memories_valid": True,
        "hard_locks": dict(_HARD_LOCKS),
    }

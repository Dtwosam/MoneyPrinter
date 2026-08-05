"""Lane E2Z — Clean Memory Creation Boundary.

The only module in the Lane E sequence that writes to printer_episodes.
All prior Lane E modules (E2X, E2Y) are read-only. This module closes the
gap between E2Y-reviewed candidates and actual clean-memory rows.

Eligibility mirrors the E2X classification gate for main outcome windows:
  (WINDOW_15M | WINDOW_1H | WINDOW_4H) + WINDOW_CLOSED + CLEAN_DATA + PARTIAL_MEMORY
  + e2q_audited (in supporting_context_json) + snapshot link present
  + do_not_train=0 + no legacy CLEAN_MEMORY label on the window row.
  WINDOW_1H requires genuine 1h identity already enforced by E2Q before promotion.

Idempotency: if printer_episodes already contains a CLEAN_MEMORY row for
the given memory_window_id, the call is a no-op and returns
E2Z_ALREADY_EXISTS without a second INSERT.

Permanently locked (no unlock path in this module):
  retrieval, paper decisions, BUY/SELL/HOLD, positions, PnL,
  source fetching, scheduler runtime, wallet/live trading, paid APIs,
  scoring, embeddings, vectors.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


E2Z_CREATED_BY: str = "lane_e2z"
E2Z_EPISODE_KIND: str = "WINDOW_15M_CLEAN_MEMORY"
E2Z_EPISODE_STATUS: str = "COMPLETE"

E2Z_STATUS_CREATED: str = "E2Z_MEMORY_CREATED"
E2Z_STATUS_ALREADY_EXISTS: str = "E2Z_ALREADY_EXISTS"
E2Z_STATUS_BLOCKED: str = "E2Z_BLOCKED"

_ALLOWED_WINDOW_KINDS: frozenset[str] = frozenset(
    {"WINDOW_15M", "WINDOW_1H", "WINDOW_4H"}
)
_REQUIRED_WINDOW_STATUS: str = "WINDOW_CLOSED"
_REQUIRED_DATA_QUALITY: str = "CLEAN_DATA"
_REQUIRED_MEMORY_STATUS: str = "PARTIAL_MEMORY"
_REQUIRED_MEMORY_QUALITY: str = "PARTIAL_MEMORY"

_HARD_LOCKS: dict[str, bool] = {
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
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads_json(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _has_snapshot_link(ctx: dict[str, Any]) -> bool:
    if ctx.get("snapshot_id") is not None:
        return True
    if ctx.get("token_snapshot_id") is not None:
        return True
    if ctx.get("supporting_snapshot_id") is not None:
        return True
    ids = ctx.get("snapshot_ids")
    return isinstance(ids, list) and len(ids) > 0


def _is_e2q_audited(ctx: dict[str, Any]) -> bool:
    return ctx.get("e2q_audited") is True or ctx.get("e2q_audited_by") == "lane_e2q"


def _gate_window(row: sqlite3.Row) -> list[str]:
    """Return list of blocking reasons; empty means the window passes."""
    reasons: list[str] = []

    if row["window_kind"] not in _ALLOWED_WINDOW_KINDS:
        reasons.append(
            f"window_kind must be one of {sorted(_ALLOWED_WINDOW_KINDS)!r};"
            f" got {row['window_kind']!r}"
        )

    if row["window_status"] != _REQUIRED_WINDOW_STATUS:
        reasons.append(
            f"window_status must be '{_REQUIRED_WINDOW_STATUS}';"
            f" got {row['window_status']!r}"
        )

    if row["data_quality_label"] != _REQUIRED_DATA_QUALITY:
        reasons.append(
            f"data_quality_label must be '{_REQUIRED_DATA_QUALITY}';"
            f" got {row['data_quality_label']!r}"
        )

    if row["memory_status"] != _REQUIRED_MEMORY_STATUS:
        reasons.append(
            f"memory_status must be '{_REQUIRED_MEMORY_STATUS}';"
            f" got {row['memory_status']!r}"
        )

    if (row["memory_quality_label"] or "") != _REQUIRED_MEMORY_QUALITY:
        reasons.append(
            f"memory_quality_label must be '{_REQUIRED_MEMORY_QUALITY}';"
            f" got {row['memory_quality_label']!r}"
        )

    if row["do_not_train"] not in (0, False):
        reasons.append("do_not_train must be 0 (clean candidate)")

    ctx = _loads_json(row["supporting_context_json"])

    if row["window_kind"] == "WINDOW_4H" and (
        ctx.get("shared_window_4h_context_evidence", {}).get(
            "clean_memory_context_ready"
        ) is not True
    ):
        reasons.append(
            "WINDOW_4H shared context evidence must be clean-ready before promotion"
        )

    if not _is_e2q_audited(ctx):
        reasons.append("window must be e2q_audited (e2q_audited=True in supporting_context_json)")

    if not _has_snapshot_link(ctx):
        reasons.append("window must have a snapshot link in supporting_context_json")

    return reasons


def _validate_e2y_report(
    e2y_report: dict[str, Any] | None,
    window_id: int | None,
) -> list[str]:
    """Return blocking reasons from E2Y set-gate validation; empty = pass."""
    reasons: list[str] = []
    if e2y_report is None:
        reasons.append(
            "e2y_report is required: supply a completed E2Y candidate set gate report"
        )
        return reasons
    if e2y_report.get("set_gate_passed") is not True:
        reasons.append(
            "E2Y set_gate_passed must be True;"
            f" got {e2y_report.get('set_gate_passed')!r}"
        )
    if window_id is not None:
        candidate_ids = (
            e2y_report.get("candidate_set_summary", {}).get("candidate_ids", [])
        )
        if window_id not in candidate_ids:
            reasons.append(
                f"window_id {window_id} is not in the E2Y candidate set"
                f" (candidate_ids={candidate_ids!r})"
            )
    return reasons


def create_clean_memory_from_window(
    db_path: str | Path | None,
    window_id: int | None,
    *,
    operator_approved: bool = False,
    e2y_report: dict[str, Any] | None = None,
    individual_promotion: bool = False,
    lane_q_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Promote one eligible main window to a clean printer_episodes row.

    Two promotion modes:

    Batch mode (individual_promotion=False, default):
      Requires a passed E2Y candidate set gate report. window_id must appear
      in the report's candidate_set_summary.candidate_ids and set_gate_passed
      must be True. The per-window DB gate is also applied.

    Individual promotion mode (individual_promotion=True):
      Skips the E2Y batch report requirement. The per-window DB gate
      (_gate_window) is the sole authority. Use this when Lane K is promoting
      individually eligible windows from a mixed batch (e.g. 3 PARTIAL_MEMORY +
      10 DIRTY_MEMORY) where the full E2Y batch gate would fail due to mixed
      statuses even though individual windows are eligible.

    Idempotent: a second call for the same window_id returns
    E2Z_ALREADY_EXISTS without a second INSERT.
    """
    blocked_reasons: list[str] = []

    if not operator_approved:
        blocked_reasons.append("operator_approved must be True")

    if window_id is None:
        blocked_reasons.append("window_id is required")

    if not individual_promotion:
        blocked_reasons.extend(_validate_e2y_report(e2y_report, window_id))

    db_path_str: str = ""
    if db_path is None:
        blocked_reasons.append("db_path is required")
    else:
        p = Path(db_path)
        db_path_str = str(p)
        if not p.is_file():
            blocked_reasons.append(f"db_path not found: {db_path}")

    if blocked_reasons:
        return _blocked(blocked_reasons, db_path_str, window_id)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        # Fetch the window row.
        win_row = conn.execute(
            """
            SELECT id, token_id, pair_id, window_kind, window_status,
                   memory_status, memory_quality_label, data_quality_label,
                   do_not_train, supporting_context_json, opened_at, closed_at
            FROM printer_memory_windows WHERE id = ?
            """,
            (window_id,),
        ).fetchone()

        if win_row is None:
            return _blocked(
                [f"no printer_memory_windows row found for id={window_id}"],
                db_path_str, window_id,
            )

        gate_failures = _gate_window(win_row)
        if win_row["window_kind"] == "WINDOW_4H":
            valid_ids = (lane_q_report or {}).get("valid_window_ids", [])
            if window_id not in valid_ids:
                gate_failures.append(
                    "WINDOW_4H requires an explicit passed Lane Q report"
                )
        if gate_failures:
            return _blocked(gate_failures, db_path_str, window_id)

        from printer_v1.memory.clean_object_promotion import (
            CleanObjectIntegrityError,
            promote_clean_object,
        )

        try:
            promotion = promote_clean_object(conn, window_id=int(window_id))
        except CleanObjectIntegrityError as exc:
            return _blocked(
                [f"clean_object_integrity:{exc.code}"],
                db_path_str,
                window_id,
            )
        episode_id = int(promotion.episode_id)
        fingerprint_id = int(promotion.fingerprint_id)
        created = promotion.created
        e2z_status = E2Z_STATUS_CREATED if created else E2Z_STATUS_ALREADY_EXISTS

    finally:
        conn.close()

    return {
        "e2z_status": e2z_status,
        "episode_id": episode_id,
        "fingerprint_id": fingerprint_id,
        "atomic_status": promotion.status,
        "idempotent": promotion.idempotent,
        "window_id": window_id,
        "db_path": db_path_str,
        "operator_approved": True,
        "created": created,
        "retrieval_activated": False,
        "paper_decisions_created": 0,
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "positions_created": 0,
        "pnl_created": 0,
        "hard_locks": dict(_HARD_LOCKS),
    }


def _blocked(
    reasons: list[str],
    db_path_str: str,
    window_id: int | None,
) -> dict[str, Any]:
    return {
        "e2z_status": E2Z_STATUS_BLOCKED,
        "episode_id": None,
        "fingerprint_id": None,
        "atomic_status": "BLOCKED",
        "idempotent": False,
        "window_id": window_id,
        "db_path": db_path_str,
        "operator_approved": False,
        "created": False,
        "blocked_reasons": reasons,
        "retrieval_activated": False,
        "paper_decisions_created": 0,
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "positions_created": 0,
        "pnl_created": 0,
        "hard_locks": dict(_HARD_LOCKS),
    }

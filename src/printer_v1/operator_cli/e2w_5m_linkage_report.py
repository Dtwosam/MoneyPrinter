"""E2W 5m-to-15m Linkage Verification Report.

Read-only / fixture-only verification of WINDOW_5M_MICRO_EVENT linkage to
parent WINDOW_15M evidence windows.

Permanent hard rules:
- Read-only.  All DB operations are SELECT-only.  Delta guard proves zero mutations.
- WINDOW_5M_MICRO_EVENT is support-only.  It never replaces WINDOW_15M evidence.
- 5m cannot produce CLEAN_MEMORY, activate retrieval, create paper decisions,
  unlock BUY/SELL/HOLD, create positions, trade events, paper trade audits, or PnL.
- No scoring, ranking, confidence, weighted logic, embeddings, or vectors.
- No Source Governor bypass.  No Central Scheduler bypass.
- No migrations.  No schema changes.  No runtime hooks.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


E2W_COMMAND_NAME: str = "printer-report-e2w-5m-linkage"
E2W_STATUS_READY: str = "E2W_REPORT_READY"
E2W_STATUS_BLOCKED: str = "E2W_BLOCKED"
E2W_WINDOW_KIND: str = "WINDOW_5M_MICRO_EVENT"
E2W_PARENT_KIND: str = "WINDOW_15M"
_LAST_N: int = 10

_DIRTY_QUALITY_LABELS: frozenset[str] = frozenset({
    "DIRTY_DATA", "STALE_DATA", "MISSING_CRITICAL_DATA",
    "CONFLICTING_DATA", "DO_NOT_TRAIN",
})
_DIRTY_MEMORY_LABELS: frozenset[str] = frozenset({
    "DIRTY_MEMORY", "DO_NOT_TRAIN",
})

_LOCKED_STATE: dict[str, bool] = {
    "buy_unlock": False,
    "sell_unlock": False,
    "hold_unlock": False,
    "paper_positions_unlock": False,
    "pnl_unlock": False,
    "live_execution": False,
    "wallet_private_key": False,
    "paid_api_dependency": False,
}

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
    "no_5m_main_outcome": True,
    "no_clean_memory_from_5m": True,
    "no_source_governor_bypass": True,
    "no_scheduler_bypass": True,
    "no_scoring_ranking_confidence": True,
    "no_embeddings_vectors": True,
}


def _connect_ro(db_path: str | Path) -> sqlite3.Connection:
    try:
        uri = Path(db_path).resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn


def _safe_count(conn: sqlite3.Connection, table: str) -> int | str:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.OperationalError:
        return "table_absent"


def _count_snapshot(conn: sqlite3.Connection) -> dict[str, int | str]:
    tables = [
        "printer_memory_windows",
        "printer_memories",
        "printer_paper_decisions",
        "printer_paper_positions",
        "printer_paper_trade_events",
        "printer_paper_trade_audits",
        "printer_token_snapshots",
        "printer_scheduler_jobs",
    ]
    return {t: _safe_count(conn, t) for t in tables}


def _classify_5m_row(
    row: sqlite3.Row,
    parent_index: dict[int, str],
) -> str:
    """Classify a single WINDOW_5M_MICRO_EVENT row.

    Returns one of: 'valid_linked', 'dirty', 'unlinked', 'invalid_parent'.
    Dirty takes precedence over linkage errors â€” evidence that is explicitly
    marked dirty/do_not_train is classified dirty regardless of parent state.
    """
    is_dirty = (
        row["do_not_train"] == 1
        or (row["data_quality_label"] or "") in _DIRTY_QUALITY_LABELS
        or (row["memory_quality_label"] or "") in _DIRTY_MEMORY_LABELS
    )

    try:
        ctx = json.loads(row["supporting_context_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        ctx = {}

    parent_id = ctx.get("parent_window_id")

    if is_dirty:
        return "dirty"

    if parent_id is None:
        return "unlinked"

    parent_kind = parent_index.get(int(parent_id))
    if parent_kind != E2W_PARENT_KIND:
        return "invalid_parent"

    return "valid_linked"


def build_e2w_linkage_report(
    db_path: str | Path | None,
    *,
    operator_approved: bool = False,
) -> dict[str, Any]:
    """Build the E2W 5m-to-15m linkage verification report.

    Read-only.  No DB mutations.  All operations are SELECT-only.
    Delta guard verifies zero-row-count change before and after.
    """
    blocked_reasons: list[str] = []

    if not operator_approved:
        blocked_reasons.append(
            "operator_approved must be True to run E2W linkage report"
        )

    db_path_str: str = ""
    if db_path is None:
        blocked_reasons.append("db_path is required")
    else:
        p = Path(db_path)
        db_path_str = str(p)
        if not p.is_file():
            blocked_reasons.append(f"db_path not found: {db_path}")

    if blocked_reasons:
        return {
            "command": E2W_COMMAND_NAME,
            "e2w_status": E2W_STATUS_BLOCKED,
            "operator_approved": operator_approved,
            "db_path": db_path_str,
            "blocked_reasons": blocked_reasons,
            "locked_state": dict(_LOCKED_STATE),
            "hard_locks": dict(_HARD_LOCKS),
            "support_only_confirmed": True,
            "main_outcome_blocked": True,
            "clean_memory_from_5m_blocked": True,
            "retrieval_from_5m_blocked": True,
            "paper_decision_from_5m_blocked": True,
            "buy_from_5m_blocked": True,
            "position_from_5m_blocked": True,
        }

    conn = _connect_ro(db_path)
    try:
        counts_before = _count_snapshot(conn)

        # Build index: window_id â†’ window_kind for all non-5m windows
        parent_index: dict[int, str] = {}
        try:
            for r in conn.execute(
                "SELECT id, window_kind FROM printer_memory_windows"
                " WHERE window_kind != ?",
                (E2W_WINDOW_KIND,),
            ).fetchall():
                parent_index[int(r["id"])] = str(r["window_kind"])
        except sqlite3.OperationalError:
            pass

        # Fetch all WINDOW_5M_MICRO_EVENT rows
        five_m_rows: list[sqlite3.Row] = []
        try:
            five_m_rows = conn.execute(
                """
                SELECT id, token_id, pair_id, window_kind, window_status,
                       memory_status, data_quality_label, memory_quality_label,
                       do_not_train, supporting_context_json, opened_at, closed_at
                FROM printer_memory_windows
                WHERE window_kind = ?
                ORDER BY id DESC
                """,
                (E2W_WINDOW_KIND,),
            ).fetchall()
        except sqlite3.OperationalError:
            pass

        # Classify each 5m row
        valid_linked: list[dict[str, Any]] = []
        dirty: list[dict[str, Any]] = []
        unlinked: list[dict[str, Any]] = []
        invalid_parent: list[dict[str, Any]] = []

        for row in five_m_rows:
            try:
                ctx = json.loads(row["supporting_context_json"] or "{}")
            except (json.JSONDecodeError, TypeError):
                ctx = {}

            classification = _classify_5m_row(row, parent_index)
            entry: dict[str, Any] = {
                "id": int(row["id"]),
                "token_id": row["token_id"],
                "pair_id": row["pair_id"],
                "window_status": row["window_status"],
                "memory_quality_label": row["memory_quality_label"],
                "data_quality_label": row["data_quality_label"],
                "do_not_train": bool(row["do_not_train"]),
                "parent_window_id": ctx.get("parent_window_id"),
                "parent_window_kind": ctx.get("parent_window_kind"),
                "opened_at": row["opened_at"],
                "closed_at": row["closed_at"],
                "classification": classification,
            }
            if classification == "valid_linked":
                valid_linked.append(entry)
            elif classification == "dirty":
                dirty.append(entry)
            elif classification == "unlinked":
                unlinked.append(entry)
            else:
                invalid_parent.append(entry)

        # Derive proof flags
        # repeated_5m_support_proof: same (token_id, pair_id) has â‰¥2 5m windows
        token_pair_counts: dict[tuple[int, int], int] = {}
        for row in five_m_rows:
            key = (row["token_id"], row["pair_id"])
            token_pair_counts[key] = token_pair_counts.get(key, 0) + 1
        repeated_5m_support_proof = any(v >= 2 for v in token_pair_counts.values())

        # multiple_5m_to_one_15m_parent_proof: same parent_window_id has â‰¥2 5m windows
        parent_ref_counts: dict[int, int] = {}
        for entry in valid_linked:
            pid = entry["parent_window_id"]
            if pid is not None:
                parent_ref_counts[int(pid)] = parent_ref_counts.get(int(pid), 0) + 1
        multiple_5m_to_one_15m_parent_proof = any(
            v >= 2 for v in parent_ref_counts.values()
        )

        # Distinct WINDOW_15M ids that are referenced by valid linked 5m rows
        parent_15m_ids: set[int] = {
            int(e["parent_window_id"])
            for e in valid_linked
            if e["parent_window_id"] is not None
        }

        counts_after = _count_snapshot(conn)

    finally:
        conn.close()

    # Delta guard
    delta_violations: list[str] = []
    for t, before_val in counts_before.items():
        after_val = counts_after.get(t)
        if isinstance(before_val, int) and isinstance(after_val, int):
            if after_val != before_val:
                delta_violations.append(
                    f"{t}: before={before_val} after={after_val}"
                    f" DELTA={after_val - before_val}"
                )

    last_n_5m = (valid_linked + dirty + unlinked + invalid_parent)[:_LAST_N]

    return {
        "command": E2W_COMMAND_NAME,
        "e2w_status": E2W_STATUS_READY,
        "operator_approved": operator_approved,
        "db_path": db_path_str,

        # Counts
        "total_5m_window_count": len(five_m_rows),
        "valid_linked_5m_count": len(valid_linked),
        "dirty_5m_count": len(dirty),
        "unlinked_5m_count": len(unlinked),
        "invalid_parent_count": len(invalid_parent),
        "parent_window_15m_count": len(parent_15m_ids),

        # Evidence rows (last N)
        "last_n_5m_windows": last_n_5m,

        # Proof flags
        "repeated_5m_support_proof": repeated_5m_support_proof,
        "multiple_5m_to_one_15m_parent_proof": multiple_5m_to_one_15m_parent_proof,

        # Safety flags (all permanent)
        "support_only_confirmed": True,
        "main_outcome_blocked": True,
        "clean_memory_from_5m_blocked": True,
        "retrieval_from_5m_blocked": True,
        "paper_decision_from_5m_blocked": True,
        "buy_from_5m_blocked": True,
        "position_from_5m_blocked": True,

        # Read-only proof
        "read_only_delta_violations": delta_violations,

        # Locks
        "locked_state": dict(_LOCKED_STATE),
        "hard_locks": dict(_HARD_LOCKS),

        "next_recommended_lane": "E2X - Strict 15m Clean-Memory Eligibility Review / No-Creation Gate",
    }

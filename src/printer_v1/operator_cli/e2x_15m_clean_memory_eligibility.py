"""Lane E2X strict 15m clean-memory eligibility review.

This module is intentionally read-only. It reviews WINDOW_15M rows that may
be eligible for future clean-memory creation, but it does not create memory,
activate retrieval, create paper decisions, or unlock BUY/SELL/HOLD.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


E2X_STATUS_READY = "E2X_REVIEW_READY"
E2X_STATUS_BLOCKED = "E2X_REVIEW_BLOCKED"
E2X_LANE_NAME = "E2X - Strict 15m Clean-Memory Eligibility Review / No-Creation Gate"
E2X_WINDOW_KIND = "WINDOW_15M"
_LAST_N = 12

_DIRTY_DATA_LABELS = frozenset({
    "DIRTY_DATA",
    "STALE_DATA",
    "MISSING_CRITICAL_DATA",
    "CONFLICTING_DATA",
    "DO_NOT_TRAIN",
})

_DIRTY_MEMORY_LABELS = frozenset({
    "DIRTY_MEMORY",
    "DO_NOT_TRAIN",
    "AUDIT_ONLY_MEMORY",
})

_KNOWN_CLASSIFICATIONS = (
    "eligible_for_future_clean_memory_review",
    "not_eligible_partial_only",
    "blocked_dirty_or_do_not_train",
    "blocked_legacy_clean_memory_label",
    "blocked_missing_snapshot_link",
    "blocked_not_e2q_audited",
    "blocked_not_closed",
)

_MUTATION_CAPABLE_TABLES = (
    "printer_memory_windows",
    "printer_memories",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_results",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_scheduler_jobs",
    "printer_source_requests",
    "printer_source_responses",
    "printer_source_failures",
    "printer_token_snapshots",
)

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
}

_LOCKED_STATE: dict[str, bool] = {
    "clean_memory_creation_unlock": False,
    "retrieval_unlock": False,
    "paper_decision_unlock": False,
    "buy_unlock": False,
    "sell_unlock": False,
    "hold_unlock": False,
    "paper_positions_unlock": False,
    "pnl_unlock": False,
    "live_execution": False,
    "wallet_private_key": False,
}


def _connect_read_only(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _table_count(conn: sqlite3.Connection, table_name: str) -> int | str:
    if not _table_exists(conn, table_name):
        return "table_absent"
    return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def _count_where(
    conn: sqlite3.Connection,
    table_name: str,
    where_sql: str,
    params: tuple[Any, ...] = (),
) -> int | str:
    if not _table_exists(conn, table_name):
        return "table_absent"
    return int(
        conn.execute(
            f"SELECT COUNT(*) FROM {table_name} WHERE {where_sql}",
            params,
        ).fetchone()[0]
    )


def _columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    if not _table_exists(conn, table_name):
        return []
    return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table_name})")]


def _count_snapshot(conn: sqlite3.Connection) -> dict[str, int | str]:
    return {table: _table_count(conn, table) for table in _MUTATION_CAPABLE_TABLES}


def _loads_json(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"_parse_error": True}
    return parsed if isinstance(parsed, dict) else {"_non_object_json": parsed}


def _has_snapshot_link(ctx: dict[str, Any]) -> bool:
    if ctx.get("snapshot_id") is not None:
        return True
    if ctx.get("token_snapshot_id") is not None:
        return True
    if ctx.get("supporting_snapshot_id") is not None:
        return True
    snapshot_ids = ctx.get("snapshot_ids")
    return isinstance(snapshot_ids, list) and len(snapshot_ids) > 0


def _is_e2q_audited(ctx: dict[str, Any]) -> bool:
    return ctx.get("e2q_audited") is True or ctx.get("e2q_audited_by") == "lane_e2q"


def _snapshot_hint(ctx: dict[str, Any]) -> Any:
    if ctx.get("snapshot_id") is not None:
        return ctx.get("snapshot_id")
    if ctx.get("token_snapshot_id") is not None:
        return ctx.get("token_snapshot_id")
    if ctx.get("supporting_snapshot_id") is not None:
        return ctx.get("supporting_snapshot_id")
    if isinstance(ctx.get("snapshot_ids"), list):
        return ctx.get("snapshot_ids")
    return None


def _classify_15m_review(row: dict[str, Any], ctx: dict[str, Any]) -> str:
    data_quality = row.get("data_quality_label")
    memory_quality = row.get("memory_quality_label")
    memory_status = row.get("memory_status")
    do_not_train = row.get("do_not_train") in (1, True, "1")

    if row.get("window_kind") != E2X_WINDOW_KIND:
        return "not_eligible_partial_only"

    if (
        do_not_train
        or data_quality in _DIRTY_DATA_LABELS
        or memory_quality in _DIRTY_MEMORY_LABELS
    ):
        return "blocked_dirty_or_do_not_train"

    if row.get("window_status") != "WINDOW_CLOSED":
        return "blocked_not_closed"

    if memory_quality == "CLEAN_MEMORY" or memory_status == "CLEAN_MEMORY":
        return "blocked_legacy_clean_memory_label"

    if not _has_snapshot_link(ctx):
        return "blocked_missing_snapshot_link"

    if not _is_e2q_audited(ctx):
        return "blocked_not_e2q_audited"

    if (
        data_quality == "CLEAN_DATA"
        and memory_quality == "PARTIAL_MEMORY"
        and memory_status == "PARTIAL_MEMORY"
    ):
        return "eligible_for_future_clean_memory_review"

    return "not_eligible_partial_only"


def _fetch_15m_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if not _table_exists(conn, "printer_memory_windows"):
        return []

    cols = _columns(conn, "printer_memory_windows")
    wanted = [
        "id",
        "token_id",
        "pair_id",
        "window_kind",
        "window_status",
        "memory_status",
        "memory_quality_label",
        "data_quality_label",
        "do_not_train",
        "opened_at",
        "closed_at",
        "rejection_reasons_json",
        "supporting_context_json",
        "created_by_phase",
        "created_at",
        "updated_at",
    ]
    selected = [col for col in wanted if col in cols]

    if not selected:
        return []

    rows = conn.execute(
        f"""
        SELECT {", ".join(selected)}
        FROM printer_memory_windows
        WHERE window_kind=?
        ORDER BY id DESC
        """,
        (E2X_WINDOW_KIND,),
    ).fetchall()

    return [dict(row) for row in rows]


def _summarize_row(row: dict[str, Any]) -> dict[str, Any]:
    ctx = _loads_json(row.get("supporting_context_json"))
    rejection_reasons = _loads_json(row.get("rejection_reasons_json"))
    classification = _classify_15m_review(row, ctx)

    return {
        "id": row.get("id"),
        "token_id": row.get("token_id"),
        "pair_id": row.get("pair_id"),
        "window_kind": row.get("window_kind"),
        "window_status": row.get("window_status"),
        "data_quality_label": row.get("data_quality_label"),
        "memory_status": row.get("memory_status"),
        "memory_quality_label": row.get("memory_quality_label"),
        "do_not_train": bool(row.get("do_not_train")),
        "opened_at": row.get("opened_at"),
        "closed_at": row.get("closed_at"),
        "created_by_phase": row.get("created_by_phase"),
        "parsed_snapshot_link": _snapshot_hint(ctx),
        "e2q_audited": _is_e2q_audited(ctx),
        "supporting_context_keys": sorted(ctx.keys()),
        "rejection_reasons": rejection_reasons,
        "e2x_classification": classification,
        "review_only": True,
        "creates_clean_memory": False,
        "activates_retrieval": False,
        "activates_paper_decision": False,
        "unlocks_buy": False,
    }


def build_e2x_15m_clean_memory_eligibility_report(
    db_path: str | Path,
    *,
    operator_approved: bool = False,
) -> dict[str, Any]:
    """Build a read-only 15m clean-memory eligibility review report."""

    db_path_str = str(db_path)

    if not operator_approved:
        return {
            "lane": E2X_LANE_NAME,
            "e2x_status": E2X_STATUS_BLOCKED,
            "operator_approved": False,
            "blocked_reasons": ["OPERATOR_APPROVAL_REQUIRED"],
            "hard_locks": dict(_HARD_LOCKS),
            "locked_state": dict(_LOCKED_STATE),
            "clean_memory_rows_created": 0,
            "retrieval_activated": False,
            "paper_decisions_created": 0,
            "buy_enabled": False,
        }

    conn = _connect_read_only(db_path)
    try:
        before_counts = _count_snapshot(conn)
        rows = _fetch_15m_rows(conn)
        summaries = [_summarize_row(row) for row in rows]
        after_counts = _count_snapshot(conn)
    finally:
        conn.close()

    classification_counts = {name: 0 for name in _KNOWN_CLASSIFICATIONS}
    for item in summaries:
        classification = item["e2x_classification"]
        classification_counts[classification] = classification_counts.get(classification, 0) + 1

    eligible = [
        item for item in summaries
        if item["e2x_classification"] == "eligible_for_future_clean_memory_review"
    ]
    blocked_legacy = [
        item for item in summaries
        if item["e2x_classification"] == "blocked_legacy_clean_memory_label"
    ]

    read_only_delta_violations = []
    for table in _MUTATION_CAPABLE_TABLES:
        before = before_counts[table]
        after = after_counts[table]
        if isinstance(before, int) and isinstance(after, int) and before != after:
            read_only_delta_violations.append({
                "table": table,
                "before": before,
                "after": after,
            })

    return {
        "lane": E2X_LANE_NAME,
        "e2x_status": E2X_STATUS_READY,
        "operator_approved": True,
        "db_path": db_path_str,
        "mode": "READ_ONLY_REVIEW",
        "hard_locks": dict(_HARD_LOCKS),
        "locked_state": dict(_LOCKED_STATE),
        "table_counts_before": before_counts,
        "table_counts_after": after_counts,
        "read_only_delta_violations": read_only_delta_violations,

        "total_15m_window_count": len(summaries),
        "review_candidate_count": len(eligible),
        "legacy_clean_memory_label_count": len(blocked_legacy),
        "classification_counts": classification_counts,
        "review_candidate_ids": [item["id"] for item in eligible],
        "legacy_clean_memory_label_ids": [item["id"] for item in blocked_legacy],
        "latest_15m_reviews": summaries[:_LAST_N],

        "clean_memory_creation_ready": False,
        "clean_memory_rows_created": 0,
        "retrieval_activated": False,
        "paper_decisions_created": 0,
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "positions_created": 0,
        "pnl_created": 0,

        "interpretation": {
            "partial_memory_is_not_clean_memory": True,
            "eligible_means_future_review_only": True,
            "legacy_clean_memory_label_is_not_printer_memories_row": True,
            "printer_memories_table_required_before_real_clean_memory": True,
            "no_creation_gate_confirmed": True,
        },
        "next_recommended_lane": (
            "operator review required before any clean-memory creation boundary"
        ),
    }

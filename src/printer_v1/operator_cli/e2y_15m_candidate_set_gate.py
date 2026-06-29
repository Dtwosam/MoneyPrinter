"""Lane E2Y strict 15m candidate set gate.

This module is intentionally read-only. It validates a set of E2X review
candidates as a group before any future clean-memory creation boundary.
It does not create memory rows, activate retrieval, create paper decisions,
or unlock BUY/SELL/HOLD.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from printer_v1.operator_cli.e2x_15m_clean_memory_eligibility import (
    build_e2x_15m_clean_memory_eligibility_report,
)


E2Y_STATUS_READY = "E2Y_SET_GATE_READY"
E2Y_STATUS_BLOCKED = "E2Y_SET_GATE_BLOCKED"
E2Y_LANE_NAME = "E2Y - Strict 15m Candidate Set Gate / No-Creation Boundary"
_REQUIRED_CANDIDATE_COUNT = 5

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
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def _table_count(conn: sqlite3.Connection, table_name: str) -> int | str:
    if not _table_exists(conn, table_name):
        return "table_absent"
    return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def _count_snapshot(conn: sqlite3.Connection) -> dict[str, int | str]:
    return {table: _table_count(conn, table) for table in _MUTATION_CAPABLE_TABLES}


def _candidate_snapshot_links(candidates: list[dict[str, Any]]) -> list[int]:
    out: list[int] = []
    for item in candidates:
        link = item.get("parsed_snapshot_link")
        if isinstance(link, int):
            out.append(link)
    return sorted(out)


def _candidate_token_pairs(candidates: list[dict[str, Any]]) -> list[list[int]]:
    return sorted({
        (int(item["token_id"]), int(item["pair_id"]))
        for item in candidates
    })


def _unique_values(candidates: list[dict[str, Any]], key: str) -> list[Any]:
    return sorted({item.get(key) for item in candidates})


def _build_set_gate(candidates: list[dict[str, Any]]) -> dict[str, bool]:
    snapshot_ids = _candidate_snapshot_links(candidates)
    token_pairs = _candidate_token_pairs(candidates) if candidates else []
    memory_statuses = _unique_values(candidates, "memory_status")
    memory_quality_labels = _unique_values(candidates, "memory_quality_label")

    return {
        "candidate_count_is_5": len(candidates) == _REQUIRED_CANDIDATE_COUNT,
        "all_same_token_pair": len(token_pairs) == 1,
        "all_window_15m": _unique_values(candidates, "window_kind") == ["WINDOW_15M"],
        "all_window_closed": _unique_values(candidates, "window_status") == ["WINDOW_CLOSED"],
        "all_clean_data": _unique_values(candidates, "data_quality_label") == ["CLEAN_DATA"],
        "all_partial_memory": (
            memory_statuses == ["PARTIAL_MEMORY"]
            and memory_quality_labels == ["PARTIAL_MEMORY"]
        ),
        "no_clean_memory_labels_in_candidate_set": (
            "CLEAN_MEMORY" not in memory_statuses
            and "CLEAN_MEMORY" not in memory_quality_labels
        ),
        "all_e2q_audited": (
            bool(candidates)
            and all(item.get("e2q_audited") is True for item in candidates)
        ),
        "all_have_snapshot_links": len(snapshot_ids) == len(candidates),
        "snapshot_ids_are_strictly_increasing": snapshot_ids == sorted(set(snapshot_ids)),
        "snapshot_count_is_5": len(snapshot_ids) == _REQUIRED_CANDIDATE_COUNT,
        "no_dirty_or_do_not_train_in_candidate_set": all(
            item.get("do_not_train") is False for item in candidates
        ),
        "all_review_only": all(item.get("review_only") is True for item in candidates),
        "no_candidate_creates_memory": all(
            item.get("creates_clean_memory") is False for item in candidates
        ),
        "no_candidate_activates_retrieval": all(
            item.get("activates_retrieval") is False for item in candidates
        ),
        "no_candidate_activates_paper_decision": all(
            item.get("activates_paper_decision") is False for item in candidates
        ),
        "no_candidate_unlocks_buy": all(
            item.get("unlocks_buy") is False for item in candidates
        ),
        "no_memory_creation": True,
        "no_retrieval_activation": True,
        "no_paper_decisions": True,
        "no_buy_sell_hold": True,
        "no_positions": True,
        "no_pnl": True,
    }


def build_e2y_15m_candidate_set_gate_report(
    db_path: str | Path,
    *,
    operator_approved: bool = False,
) -> dict[str, Any]:
    """Build a read-only set-gate report over E2X review candidates."""

    if not operator_approved:
        return {
            "lane": E2Y_LANE_NAME,
            "e2y_status": E2Y_STATUS_BLOCKED,
            "operator_approved": False,
            "blocked_reasons": ["OPERATOR_APPROVAL_REQUIRED"],
            "set_gate_passed": False,
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
        e2x = build_e2x_15m_clean_memory_eligibility_report(
            db_path,
            operator_approved=True,
        )
        candidate_ids = set(e2x.get("review_candidate_ids", []))
        latest_reviews = e2x.get("latest_15m_reviews", [])
        candidates = [
            item for item in latest_reviews
            if item.get("id") in candidate_ids
        ]
        after_counts = _count_snapshot(conn)
    finally:
        conn.close()

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

    set_gate = _build_set_gate(candidates)
    set_gate["read_only_delta_clean"] = read_only_delta_violations == []

    token_pairs = _candidate_token_pairs(candidates) if candidates else []
    snapshot_ids = _candidate_snapshot_links(candidates)

    return {
        "lane": E2Y_LANE_NAME,
        "e2y_status": E2Y_STATUS_READY,
        "operator_approved": True,
        "mode": "READ_ONLY_SET_GATE",
        "source_anchor": {
            "e2x_status": e2x.get("e2x_status"),
            "review_candidate_count": e2x.get("review_candidate_count"),
            "review_candidate_ids": e2x.get("review_candidate_ids"),
        },
        "candidate_set_summary": {
            "candidate_ids": [item.get("id") for item in candidates],
            "token_pairs": token_pairs,
            "snapshot_ids": snapshot_ids,
            "window_kinds": _unique_values(candidates, "window_kind"),
            "window_statuses": _unique_values(candidates, "window_status"),
            "data_labels": _unique_values(candidates, "data_quality_label"),
            "memory_statuses": _unique_values(candidates, "memory_status"),
            "memory_quality_labels": _unique_values(candidates, "memory_quality_label"),
        },
        "candidate_rows": candidates,
        "set_gate": set_gate,
        "set_gate_passed": all(set_gate.values()),
        "hard_locks": dict(_HARD_LOCKS),
        "locked_state": dict(_LOCKED_STATE),
        "table_counts_before": before_counts,
        "table_counts_after": after_counts,
        "read_only_delta_violations": read_only_delta_violations,
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
            "set_gate_is_review_only": True,
            "candidate_set_pass_does_not_create_memory": True,
            "partial_memory_is_not_clean_memory": True,
            "printer_memories_table_required_before_real_clean_memory": True,
            "operator_must_approve_next_boundary": True,
        },
        "next_recommended_lane": (
            "operator review required before any clean-memory creation boundary"
        ),
    }

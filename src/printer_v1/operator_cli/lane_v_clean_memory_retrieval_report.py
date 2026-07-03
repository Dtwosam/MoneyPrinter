"""Lane V — Controlled Clean-Memory Retrieval Reporting (Audit-Only).

Read-only report over printer_episodes. Covers only fully complete clean
memories (memory_status=CLEAN_MEMORY, data_quality_label=CLEAN_DATA,
do_not_train=0, episode_status=COMPLETE, window_kind!=WINDOW_5M_MICRO_EVENT).

Applies no-score categorical labels only.  Never writes any rows.  Never
activates retrieval, creates paper decisions, unlocks BUY/SELL/HOLD, creates
positions/PnL, fetches live data, or applies numeric scoring / rankings /
confidence percentages.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


LANE_V_NAME = "Lane V — Controlled Clean-Memory Retrieval Report / Audit-Only"
LANE_V_STATUS_READY = "LANE_V_REPORT_READY"
LANE_V_STATUS_BLOCKED = "LANE_V_REPORT_BLOCKED"

# No-score categorical labels — the only labels this module emits.
LABEL_SAME_PAIR = "SAME_PAIR"
LABEL_SAME_TOKEN = "SAME_TOKEN"
LABEL_SAME_WINDOW_KIND = "SAME_WINDOW_KIND"
LABEL_RECENT_CLEAN_MEMORY = "RECENT_CLEAN_MEMORY"
LABEL_CONFLICTING_OUTCOME_LABELS = "CONFLICTING_OUTCOME_LABELS"
LABEL_INSUFFICIENT_CLEAN_MEMORY = "INSUFFICIENT_CLEAN_MEMORY"

_REQUIRED_MEMORY_STATUS = "CLEAN_MEMORY"
_REQUIRED_DATA_QUALITY = "CLEAN_DATA"
_REQUIRED_EPISODE_STATUS = "COMPLETE"
_SUPPORT_ONLY_KIND = "WINDOW_5M_MICRO_EVENT"

# Fewer than this → INSUFFICIENT_CLEAN_MEMORY label added.
_INSUFFICIENT_THRESHOLD = 5

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


def build_clean_memory_retrieval_report(
    db_path: str | Path | None,
    *,
    token_id: int | None = None,
    pair_id: int | None = None,
    window_kind: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Build a read-only audit report of existing clean memories from printer_episodes.

    Reads printer_episodes.  Writes nothing.  No retrieval activation.
    No paper decisions.  No scoring, ranking, or confidence percentages.
    """
    if db_path is None:
        return _blocked(["db_path is required"])
    p = Path(db_path)
    if not p.is_file():
        return _blocked([f"db_path not found: {db_path}"])

    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    try:
        return _run_report(
            conn,
            token_id=token_id,
            pair_id=pair_id,
            window_kind=window_kind,
            limit=limit,
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _optional_filters(
    token_id: int | None,
    pair_id: int | None,
    window_kind: str | None,
) -> tuple[list[str], list[Any]]:
    parts: list[str] = []
    args: list[Any] = []
    if token_id is not None:
        parts.append("e.token_id = ?")
        args.append(int(token_id))
    if pair_id is not None:
        parts.append("e.pair_id = ?")
        args.append(int(pair_id))
    if window_kind is not None:
        parts.append("e.window_kind = ?")
        args.append(str(window_kind))
    return parts, args


def _run_report(
    conn: sqlite3.Connection,
    *,
    token_id: int | None,
    pair_id: int | None,
    window_kind: str | None,
    limit: int | None,
) -> dict[str, Any]:
    opt_parts, opt_args = _optional_filters(token_id, pair_id, window_kind)

    # --- Main clean-memory query ---
    base_parts = [
        "e.memory_status = ?",
        "e.data_quality_label = ?",
        "e.do_not_train = 0",
        "e.episode_status = ?",
        "(e.window_kind IS NULL OR e.window_kind != ?)",
    ]
    base_args: list[Any] = [
        _REQUIRED_MEMORY_STATUS,
        _REQUIRED_DATA_QUALITY,
        _REQUIRED_EPISODE_STATUS,
        _SUPPORT_ONLY_KIND,
    ]
    all_parts = base_parts + opt_parts
    all_args = base_args + opt_args

    where_clause = " AND ".join(all_parts)
    sql = (
        "SELECT e.id, e.memory_window_id, e.token_id, e.pair_id,"
        " e.window_kind, e.episode_kind, e.episode_status,"
        " e.memory_status, e.data_quality_label, e.do_not_train,"
        " e.memory_quality_label, e.episode_outcome_label,"
        " e.created_at, e.updated_at"
        " FROM printer_episodes e"
        f" WHERE {where_clause}"
        " ORDER BY e.id DESC"
    )
    if limit is not None:
        sql += f" LIMIT {int(limit)}"

    rows = conn.execute(sql, all_args).fetchall()
    episodes = [dict(row) for row in rows]
    episode_ids = [ep["id"] for ep in episodes]
    window_ids = [ep["memory_window_id"] for ep in episodes]

    # --- Grouping ---
    groups: dict[tuple[Any, Any, Any], list[int]] = {}
    for ep in episodes:
        key = (ep["token_id"], ep["pair_id"], ep["window_kind"])
        groups.setdefault(key, []).append(ep["id"])
    group_summary = [
        {
            "token_id": k[0],
            "pair_id": k[1],
            "window_kind": k[2],
            "episode_ids": v,
            "count": len(v),
        }
        for k, v in sorted(groups.items(), key=lambda kv: kv[0])
    ]

    # --- No-score categorical labels ---
    labels: list[str] = []
    all_pair_ids = {ep["pair_id"] for ep in episodes}
    all_token_ids = {ep["token_id"] for ep in episodes}
    all_window_kinds = {ep["window_kind"] for ep in episodes}

    if pair_id is not None or (episodes and len(all_pair_ids) == 1):
        labels.append(LABEL_SAME_PAIR)
    if token_id is not None or (episodes and len(all_token_ids) == 1):
        labels.append(LABEL_SAME_TOKEN)
    if window_kind is not None or (episodes and len(all_window_kinds) == 1):
        labels.append(LABEL_SAME_WINDOW_KIND)
    if episodes:
        labels.append(LABEL_RECENT_CLEAN_MEMORY)
    outcome_set = {
        ep.get("episode_outcome_label")
        for ep in episodes
        if ep.get("episode_outcome_label") is not None
    }
    if len(outcome_set) > 1:
        labels.append(LABEL_CONFLICTING_OUTCOME_LABELS)
    if len(episodes) < _INSUFFICIENT_THRESHOLD:
        labels.append(LABEL_INSUFFICIENT_CLEAN_MEMORY)

    # --- Excluded counts (scoped to same token/pair if provided) ---
    exc_parts, exc_args = _optional_filters(token_id, pair_id, window_kind=None)

    dirty_count = _count_where(
        conn,
        "memory_status IN ('DIRTY_MEMORY', 'PARTIAL_MEMORY', 'AUDIT_ONLY')",
        exc_parts, exc_args,
    )
    do_not_train_count = _count_where(
        conn,
        "do_not_train = 1 OR memory_status = 'DO_NOT_TRAIN' OR data_quality_label = 'DO_NOT_TRAIN'",
        exc_parts, exc_args,
    )
    support_only_count = _count_where(
        conn,
        "window_kind = 'WINDOW_5M_MICRO_EVENT'",
        exc_parts, exc_args,
    )

    return {
        "lane": LANE_V_NAME,
        "lane_v_status": LANE_V_STATUS_READY,
        "clean_only": True,
        "retrieval_activation": False,
        "paper_decisions_created": 0,
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "positions_created": 0,
        "pnl_created": 0,
        "hard_locks": dict(_HARD_LOCKS),
        "filters_applied": {
            "token_id": token_id,
            "pair_id": pair_id,
            "window_kind": window_kind,
            "limit": limit,
        },
        "clean_memory_count": len(episodes),
        "selected_clean_memory_ids": episode_ids,
        "selected_window_ids": window_ids,
        "group_summary": group_summary,
        "report_labels": labels,
        "dirty_memory_excluded_count": dirty_count,
        "do_not_train_excluded_count": do_not_train_count,
        "support_only_excluded_count": support_only_count,
        "episodes": episodes,
    }


def _count_where(
    conn: sqlite3.Connection,
    condition: str,
    extra_parts: list[str],
    extra_args: list[Any],
) -> int:
    all_parts = [f"({condition})"] + extra_parts
    where = " AND ".join(all_parts)
    row = conn.execute(
        f"SELECT COUNT(*) FROM printer_episodes e WHERE {where}",
        extra_args,
    ).fetchone()
    return int(row[0])


def _blocked(reasons: list[str]) -> dict[str, Any]:
    return {
        "lane": LANE_V_NAME,
        "lane_v_status": LANE_V_STATUS_BLOCKED,
        "blocked_reasons": reasons,
        "clean_only": True,
        "retrieval_activation": False,
        "paper_decisions_created": 0,
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "positions_created": 0,
        "pnl_created": 0,
        "hard_locks": dict(_HARD_LOCKS),
    }

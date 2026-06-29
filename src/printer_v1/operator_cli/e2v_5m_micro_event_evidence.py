"""E2V 5m Micro-Event Support Evidence Hardening.

Validates WINDOW_5M_MICRO_EVENT evidence records as *support-only* context
linked to a parent WINDOW_15M.  This module is fixture/test-only — it does
not fetch sources, call the scheduler, write real DB rows, or change runtime
behavior.

Hard rules (permanent):
- WINDOW_5M_MICRO_EVENT is support-only.  It is never a main outcome window.
- 5m evidence cannot produce CLEAN_MEMORY by itself.
- 5m evidence requires an explicit parent_window_id referencing a WINDOW_15M.
- Non-15m parent linkage is rejected.
- Dirty, stale, incomplete, failed, mismatched, or unlinked 5m evidence is
  always AUDIT_ONLY / DIRTY_MEMORY / DO_NOT_TRAIN.
- No retrieval activation.
- No memory rows created.
- No paper decisions, positions, PnL, trade events, or paper audits.
- No BUY / SELL / HOLD.
- No live execution, wallet, or private key logic.
- No paid API, scoring, ranking, confidence, weighted logic, embeddings, vectors.
- No Source Governor bypass.
- No Central Scheduler bypass.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any


# ---------------------------------------------------------------------------
# Module identity
# ---------------------------------------------------------------------------

E2V_WINDOW_KIND: str = "WINDOW_5M_MICRO_EVENT"
E2V_REQUIRED_PARENT_KIND: str = "WINDOW_15M"
E2V_CREATED_BY: str = "lane_e2v"

# Validation outcomes
E2V_STATUS_VALID: str = "E2V_VALID"
E2V_STATUS_AUDIT_ONLY: str = "E2V_AUDIT_ONLY"
E2V_STATUS_DIRTY: str = "E2V_DIRTY"
E2V_STATUS_BLOCKED: str = "E2V_BLOCKED"

# Allowed memory_status values for 5m windows (CLEAN_MEMORY is forbidden)
E2V_ALLOWED_MEMORY_STATUS: frozenset[str] = frozenset({
    "PARTIAL_MEMORY",
    "DIRTY_MEMORY",
    "DO_NOT_TRAIN",
    "AUDIT_ONLY",
})

# Allowed memory_quality_label values for 5m windows
E2V_ALLOWED_QUALITY_LABELS: frozenset[str] = frozenset({
    "SUPPORT_EVIDENCE",
    "PARTIAL_MEMORY",
    "AUDIT_ONLY",
    "DIRTY_MEMORY",
    "DO_NOT_TRAIN",
})

# Data quality labels that force do_not_train
E2V_DIRTY_DATA_LABELS: frozenset[str] = frozenset({
    "DIRTY_DATA",
    "STALE_DATA",
    "MISSING_CRITICAL_DATA",
    "CONFLICTING_DATA",
    "DO_NOT_TRAIN",
})

# Source statuses that force dirty classification
E2V_DIRTY_SOURCE_STATUSES: frozenset[str] = frozenset({
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
    "no_5m_main_outcome": True,
    "no_source_governor_bypass": True,
    "no_scheduler_bypass": True,
    "no_clean_memory_from_5m": True,
}


# ---------------------------------------------------------------------------
# Core validator
# ---------------------------------------------------------------------------

def validate_5m_micro_event_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Validate a WINDOW_5M_MICRO_EVENT evidence dict.

    Returns a result dict with:
      e2v_status: E2V_VALID | E2V_AUDIT_ONLY | E2V_DIRTY | E2V_BLOCKED
      valid: bool
      blocked_reasons: list[str]
      rejection_reasons: list[str]
      do_not_train: bool
      memory_quality_label: str | None  (suggested classification)
      hard_locks: dict[str, bool]
    """
    blocked_reasons: list[str] = []
    rejection_reasons: list[str] = []

    # Gate 1: window kind must be WINDOW_5M_MICRO_EVENT
    window_kind = evidence.get("window_kind")
    if window_kind != E2V_WINDOW_KIND:
        blocked_reasons.append(
            f"window_kind must be '{E2V_WINDOW_KIND}'; got {window_kind!r}"
        )

    # Gate 2: parent linkage required
    parent_window_id = evidence.get("parent_window_id")
    if parent_window_id is None:
        blocked_reasons.append(
            "parent_window_id is required for WINDOW_5M_MICRO_EVENT evidence"
        )

    # Gate 3: parent window kind must be WINDOW_15M
    parent_window_kind = evidence.get("parent_window_kind")
    if parent_window_id is not None:
        if parent_window_kind != E2V_REQUIRED_PARENT_KIND:
            blocked_reasons.append(
                f"parent_window_kind must be '{E2V_REQUIRED_PARENT_KIND}';"
                f" got {parent_window_kind!r}"
            )

    # Gate 4: memory_status must not be CLEAN_MEMORY
    memory_status = evidence.get("memory_status")
    if memory_status == "CLEAN_MEMORY":
        blocked_reasons.append(
            "WINDOW_5M_MICRO_EVENT cannot have memory_status='CLEAN_MEMORY';"
            " 5m evidence cannot produce clean memory by itself"
        )

    # Gate 5: memory_quality_label must not be CLEAN_MEMORY
    quality_label = evidence.get("memory_quality_label")
    if quality_label == "CLEAN_MEMORY":
        blocked_reasons.append(
            "WINDOW_5M_MICRO_EVENT cannot have memory_quality_label='CLEAN_MEMORY';"
            " 5m evidence cannot produce clean memory by itself"
        )

    # Gate 6: memory_quality_label must be in allowed set (if present)
    if quality_label is not None and quality_label not in E2V_ALLOWED_QUALITY_LABELS:
        if quality_label != "CLEAN_MEMORY":  # already reported above
            blocked_reasons.append(
                f"memory_quality_label {quality_label!r} is not allowed for 5m evidence;"
                f" allowed: {sorted(E2V_ALLOWED_QUALITY_LABELS)}"
            )

    # Gate 7: 5m cannot be a main outcome window
    is_main_outcome = evidence.get("is_main_outcome_window", False)
    if is_main_outcome:
        blocked_reasons.append(
            "WINDOW_5M_MICRO_EVENT cannot be a main outcome window"
        )

    # Early-exit on structural gate failures
    if blocked_reasons:
        return {
            "e2v_status": E2V_STATUS_BLOCKED,
            "valid": False,
            "blocked_reasons": blocked_reasons,
            "rejection_reasons": rejection_reasons,
            "do_not_train": True,
            "memory_quality_label": "DO_NOT_TRAIN",
            "hard_locks": dict(_HARD_LOCKS),
        }

    # --- Quality classification ---

    data_quality = evidence.get("data_quality_label", "")
    source_status = evidence.get("source_status", "")
    is_dirty = (
        data_quality in E2V_DIRTY_DATA_LABELS
        or source_status in E2V_DIRTY_SOURCE_STATUSES
    )
    is_stale = evidence.get("is_stale", False)
    is_incomplete = evidence.get("is_incomplete", False)
    is_failed = evidence.get("is_failed", False)
    is_mismatched = evidence.get("is_mismatched", False)

    if is_dirty or is_stale or is_failed or is_mismatched:
        if data_quality in E2V_DIRTY_DATA_LABELS:
            rejection_reasons.append(
                f"data_quality_label={data_quality!r} is dirty/stale/do_not_train"
            )
        if source_status in E2V_DIRTY_SOURCE_STATUSES:
            rejection_reasons.append(
                f"source_status={source_status!r} is failed/stale/conflicting"
            )
        if is_stale:
            rejection_reasons.append("evidence is stale")
        if is_failed:
            rejection_reasons.append("evidence fetch failed")
        if is_mismatched:
            rejection_reasons.append("evidence token/pair mismatch")
        return {
            "e2v_status": E2V_STATUS_DIRTY,
            "valid": False,
            "blocked_reasons": [],
            "rejection_reasons": rejection_reasons,
            "do_not_train": True,
            "memory_quality_label": "DIRTY_MEMORY",
            "hard_locks": dict(_HARD_LOCKS),
        }

    if is_incomplete or data_quality == "ACCEPTABLE_PARTIAL_DATA":
        if is_incomplete:
            rejection_reasons.append("evidence is incomplete")
        if data_quality == "ACCEPTABLE_PARTIAL_DATA":
            rejection_reasons.append(
                "data_quality_label=ACCEPTABLE_PARTIAL_DATA; audit-only"
            )
        return {
            "e2v_status": E2V_STATUS_AUDIT_ONLY,
            "valid": False,
            "blocked_reasons": [],
            "rejection_reasons": rejection_reasons,
            "do_not_train": True,
            "memory_quality_label": "AUDIT_ONLY",
            "hard_locks": dict(_HARD_LOCKS),
        }

    # Passed all gates: valid support evidence
    suggested_label = quality_label or "SUPPORT_EVIDENCE"
    return {
        "e2v_status": E2V_STATUS_VALID,
        "valid": True,
        "blocked_reasons": [],
        "rejection_reasons": [],
        "do_not_train": False,
        "memory_quality_label": suggested_label,
        "hard_locks": dict(_HARD_LOCKS),
    }


# ---------------------------------------------------------------------------
# Fixture helpers (test/validation use only — no runtime path)
# ---------------------------------------------------------------------------

def build_5m_evidence_fixture(
    *,
    token_id: int = 1,
    pair_id: int = 1,
    parent_window_id: int | None = 1,
    parent_window_kind: str = "WINDOW_15M",
    data_quality_label: str = "CLEAN_DATA",
    source_status: str = "COMPLETE",
    memory_status: str = "PARTIAL_MEMORY",
    memory_quality_label: str = "SUPPORT_EVIDENCE",
    is_main_outcome_window: bool = False,
    is_stale: bool = False,
    is_incomplete: bool = False,
    is_failed: bool = False,
    is_mismatched: bool = False,
    opened_at: str = "2026-06-28T10:00:00+00:00",
    closed_at: str = "2026-06-28T10:05:00+00:00",
) -> dict[str, Any]:
    """Build a WINDOW_5M_MICRO_EVENT evidence dict for validation or fixture use."""
    return {
        "window_kind": E2V_WINDOW_KIND,
        "token_id": token_id,
        "pair_id": pair_id,
        "parent_window_id": parent_window_id,
        "parent_window_kind": parent_window_kind,
        "data_quality_label": data_quality_label,
        "source_status": source_status,
        "memory_status": memory_status,
        "memory_quality_label": memory_quality_label,
        "is_main_outcome_window": is_main_outcome_window,
        "is_stale": is_stale,
        "is_incomplete": is_incomplete,
        "is_failed": is_failed,
        "is_mismatched": is_mismatched,
        "opened_at": opened_at,
        "closed_at": closed_at,
        "created_by_phase": E2V_CREATED_BY,
    }


def insert_5m_evidence_window(
    conn: sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int,
    snapshot_id: int | None = None,
    parent_window_id: int | None = None,
    memory_status: str = "PARTIAL_MEMORY",
    memory_quality_label: str = "SUPPORT_EVIDENCE",
    data_quality_label: str = "CLEAN_DATA",
    window_status: str = "WINDOW_CLOSED",
    do_not_train: int = 0,
    opened_at: str = "2026-06-28T10:00:00+00:00",
    closed_at: str = "2026-06-28T10:05:00+00:00",
) -> int:
    """Insert a WINDOW_5M_MICRO_EVENT row into printer_memory_windows.

    Uses supporting_context_json to carry parent_window_id / parent_window_kind.
    This is a fixture helper only — no runtime path.
    """
    ctx: dict[str, Any] = {
        "created_by": E2V_CREATED_BY,
        "parent_window_kind": E2V_REQUIRED_PARENT_KIND,
    }
    if parent_window_id is not None:
        ctx["parent_window_id"] = parent_window_id
    if snapshot_id is not None:
        ctx["snapshot_id"] = snapshot_id

    now = "2026-06-28T10:00:00+00:00"
    cur = conn.execute(
        """
        INSERT INTO printer_memory_windows (
            token_id, pair_id, window_kind, opened_at, closed_at,
            memory_status, data_quality_label, do_not_train,
            window_status, memory_quality_label,
            supporting_context_json, created_by_phase, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            token_id, pair_id, E2V_WINDOW_KIND, opened_at, closed_at,
            memory_status, data_quality_label, do_not_train,
            window_status, memory_quality_label,
            json.dumps(ctx, sort_keys=True), E2V_CREATED_BY, now, now,
        ),
    )
    return int(cur.lastrowid)

"""Lane H — Bounded 1h Memory Factory Boundary.

Classifies a single 1h memory factory evidence attempt under strict gates.
Pure dict-in / dict-out. No DB writes. No scheduler. No source calls.
No unbounded runtime. No paper decisions. No trading.

Evidence must be genuine WINDOW_1H evidence:
  - window_kind must be exactly "WINDOW_1H"
  - must span >= 60 real minutes (not assembled from 15m snapshots)
  - must carry real open + close snapshots
  - source_status must be COMPLETE
  - data_quality_label must be CLEAN_DATA
  - context must be complete
  - do_not_train must be False
  - is_fake_15m_composite must be False

Classification outcomes:
  LANE_H_CLEAN_CANDIDATE  — all gates pass; still honest (zero clean is valid)
  LANE_H_AUDIT_ONLY       — partial evidence; cannot train, cannot retrieve
  LANE_H_DIRTY            — incomplete / stale / bad quality; blocked from all use
  LANE_H_BLOCKED          — operator approval missing or absolute gate violation

5m is support-only and cannot parent or replace a 1h window.
15m is the prior confirmed memory window kind; its rules are not weakened here.

Permanently locked (no unlock path in this module):
  retrieval, paper decisions, BUY/SELL/HOLD, positions, PnL,
  source fetching, scheduler runtime, wallet/live trading, paid APIs,
  scoring/ranking/confidence, embeddings/vectors.
"""

from __future__ import annotations

from typing import Any


LANE_H_WINDOW_KIND: str = "WINDOW_1H"
LANE_H_MIN_WINDOW_MINUTES: int = 60
LANE_H_MIN_SNAPSHOT_COUNT: int = 2

LANE_H_STATUS_CLEAN_CANDIDATE: str = "LANE_H_CLEAN_CANDIDATE"
LANE_H_STATUS_AUDIT_ONLY: str = "LANE_H_AUDIT_ONLY"
LANE_H_STATUS_DIRTY: str = "LANE_H_DIRTY"
LANE_H_STATUS_BLOCKED: str = "LANE_H_BLOCKED"

_DIRTY_DATA_LABELS: frozenset[str] = frozenset({
    "DIRTY_DATA",
    "STALE_DATA",
    "MISSING_CRITICAL_DATA",
    "CONFLICTING_DATA",
    "DO_NOT_TRAIN",
})

_PARTIAL_DATA_LABELS: frozenset[str] = frozenset({
    "ACCEPTABLE_PARTIAL_DATA",
})

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
    "no_scheduler_bypass": True,
    "no_source_governor_bypass": True,
    "no_unbounded_runtime": True,
    "no_scoring_ranking_confidence": True,
    "no_embeddings_vectors": True,
    "no_5m_main_outcome": True,
    "no_fake_long_window_data": True,
}

_LOCKED_STATE: dict[str, bool] = {
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


def classify_1h_memory_attempt(
    evidence: dict[str, Any] | None,
    *,
    operator_approved: bool = False,
) -> dict[str, Any]:
    """Classify one 1h memory factory evidence attempt.

    Returns a classification result with lane_h_status, rejection_reasons,
    hard_locks, and locked_state.  Never writes to any DB or external system.
    Zero CLEAN_CANDIDATE outcomes is a valid result.
    """
    absolute_blocks: list[str] = []
    dirty_reasons: list[str] = []
    audit_reasons: list[str] = []

    # ── Absolute block: operator approval ────────────────────────────────────
    if not operator_approved:
        absolute_blocks.append("operator_approved must be True")

    # ── Absolute block: evidence dict required ────────────────────────────────
    if evidence is None:
        absolute_blocks.append("evidence dict is required")
        return _result(
            LANE_H_STATUS_BLOCKED,
            rejection_reasons=absolute_blocks,
        )

    if not isinstance(evidence, dict):
        absolute_blocks.append("evidence must be a dict")
        return _result(
            LANE_H_STATUS_BLOCKED,
            rejection_reasons=absolute_blocks,
        )

    # ── Absolute block: window kind must be WINDOW_1H ────────────────────────
    window_kind = evidence.get("window_kind")
    if window_kind != LANE_H_WINDOW_KIND:
        absolute_blocks.append(
            f"window_kind must be '{LANE_H_WINDOW_KIND}'; got {window_kind!r}"
        )

    # ── Absolute block: 5m cannot parent or replace 1h ───────────────────────
    if evidence.get("is_5m_window") is True:
        absolute_blocks.append(
            "5m windows are support-only and cannot be used as 1h evidence"
        )

    # ── Absolute block: no fake 15m composite evidence ───────────────────────
    if evidence.get("is_fake_15m_composite") is True:
        absolute_blocks.append(
            "is_fake_15m_composite: 1h evidence must be genuine; "
            "do not assemble from 15m snapshots"
        )

    if absolute_blocks:
        return _result(
            LANE_H_STATUS_BLOCKED,
            rejection_reasons=absolute_blocks,
        )

    # ── Dirty checks (hard failure — cannot train, cannot retrieve) ───────────
    do_not_train = evidence.get("do_not_train") is True
    if do_not_train:
        dirty_reasons.append("do_not_train is True")

    data_quality = evidence.get("data_quality_label", "")
    if data_quality in _DIRTY_DATA_LABELS:
        dirty_reasons.append(
            f"data_quality_label '{data_quality}' is blocked (dirty/stale/missing)"
        )

    source_status = evidence.get("source_status", "")
    if source_status not in ("COMPLETE", "PARTIAL"):
        dirty_reasons.append(
            f"source_status '{source_status}' is not acceptable (must be COMPLETE or PARTIAL)"
        )

    snap_count = evidence.get("snapshot_count", 0)
    if not isinstance(snap_count, int) or snap_count < LANE_H_MIN_SNAPSHOT_COUNT:
        dirty_reasons.append(
            f"snapshot_count {snap_count!r} is below minimum {LANE_H_MIN_SNAPSHOT_COUNT}"
        )

    duration = evidence.get("window_duration_minutes", 0)
    if (not isinstance(duration, (int, float))) or duration < LANE_H_MIN_WINDOW_MINUTES:
        dirty_reasons.append(
            f"window_duration_minutes {duration!r} is below minimum {LANE_H_MIN_WINDOW_MINUTES}"
        )

    if not evidence.get("has_open_snapshot"):
        dirty_reasons.append("has_open_snapshot must be True (open snapshot required)")

    if not evidence.get("has_close_snapshot"):
        dirty_reasons.append("has_close_snapshot must be True (close snapshot required)")

    if dirty_reasons:
        return _result(
            LANE_H_STATUS_DIRTY,
            rejection_reasons=dirty_reasons,
        )

    # ── Audit-only checks (partial — classified, not trainable) ──────────────
    if data_quality in _PARTIAL_DATA_LABELS:
        audit_reasons.append(
            f"data_quality_label '{data_quality}' is partial; outcome is AUDIT_ONLY"
        )

    if source_status == "PARTIAL":
        audit_reasons.append("source_status is PARTIAL; outcome is AUDIT_ONLY")

    if not evidence.get("context_complete"):
        audit_reasons.append(
            "context_complete is not True; missing full 1h context"
        )

    if audit_reasons:
        return _result(
            LANE_H_STATUS_AUDIT_ONLY,
            rejection_reasons=audit_reasons,
        )

    # ── All gates pass → CLEAN_CANDIDATE ─────────────────────────────────────
    return _result(
        LANE_H_STATUS_CLEAN_CANDIDATE,
        rejection_reasons=[],
    )


def build_1h_evidence_fixture(**overrides: Any) -> dict[str, Any]:
    """Return a valid WINDOW_1H evidence dict that passes all Lane H gates.

    Override any field to test specific failure paths.
    """
    base: dict[str, Any] = {
        "window_kind": LANE_H_WINDOW_KIND,
        "window_duration_minutes": 61,
        "snapshot_count": 4,
        "has_open_snapshot": True,
        "has_close_snapshot": True,
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "context_complete": True,
        "is_5m_window": False,
        "is_fake_15m_composite": False,
        "do_not_train": False,
    }
    base.update(overrides)
    return base


def _result(
    status: str,
    *,
    rejection_reasons: list[str],
) -> dict[str, Any]:
    return {
        "lane_h_status": status,
        "window_kind_target": LANE_H_WINDOW_KIND,
        "is_clean_candidate": status == LANE_H_STATUS_CLEAN_CANDIDATE,
        "rejection_reasons": rejection_reasons,
        "hard_locks": dict(_HARD_LOCKS),
        "locked_state": dict(_LOCKED_STATE),
        "retrieval_activated": False,
        "paper_decisions_created": 0,
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "positions_created": 0,
        "pnl_created": 0,
    }

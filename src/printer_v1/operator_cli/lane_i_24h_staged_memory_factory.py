"""Lane I-C — Bounded 24h Staged Memory Factory Boundary.

Classifies a single 24h memory factory evidence attempt under strict gates.
Pure dict-in / dict-out. No DB writes. No scheduler. No source calls.
No unbounded runtime. No paper decisions. No trading.

This is the third and final staged sub-lane of Lane I.
Lane I must be activated in order: 4h first, then 12h, then 24h.
The 4h and 12h stages are now anchored. This module activates the 24h stage.

There are no further Lane I stages after 24h.
Lane J (BUY, Positions, and PnL review) is NOT unlocked by Lane I-C.
Lane J financial action gates remain locked and are explicitly listed in
locked_state so every result carries visible proof.

Evidence must be genuine WINDOW_24H evidence:
  - window_kind must be exactly "WINDOW_24H"
  - must span >= 1440 real minutes (cannot be assembled from 15m, 1h, 4h, or 12h windows)
  - must carry real open + close snapshots
  - source_status must be COMPLETE
  - data_quality_label must be CLEAN_DATA
  - context must be complete
  - do_not_train must be False
  - is_fake_15m_composite must be False
  - is_fake_1h_composite must be False
  - is_fake_4h_composite must be False
  - is_fake_12h_composite must be False

Classification outcomes:
  LANE_IC_CLEAN_CANDIDATE  — all gates pass; still honest (zero clean is valid)
  LANE_IC_AUDIT_ONLY       — partial evidence; cannot train, cannot retrieve
  LANE_IC_DIRTY            — incomplete / stale / bad quality; blocked from all use
  LANE_IC_BLOCKED          — operator approval missing, wrong window kind,
                             or fake composite evidence

5m is support-only and cannot parent or replace a 24h window.
15m, 1h, 4h, and 12h are prior confirmed window kinds; their rules are not weakened here.

Permanently locked (no unlock path in this module):
  retrieval, paper decisions, BUY/SELL/HOLD, positions, PnL,
  source fetching, scheduler runtime, wallet/live trading, paid APIs,
  scoring/ranking/confidence, embeddings/vectors.

Lane J gates (locked, no unlock in Lane I-C):
  lane_j_buy_unlock_active:              False
  lane_j_sell_hold_unlock_active:        False
  lane_j_paper_positions_unlock_active:  False
  lane_j_pnl_unlock_active:             False
"""

from __future__ import annotations

from typing import Any


LANE_IC_WINDOW_KIND: str = "WINDOW_24H"
LANE_IC_MIN_WINDOW_MINUTES: int = 1440
LANE_IC_MIN_SNAPSHOT_COUNT: int = 2

LANE_IC_STATUS_CLEAN_CANDIDATE: str = "LANE_IC_CLEAN_CANDIDATE"
LANE_IC_STATUS_AUDIT_ONLY: str = "LANE_IC_AUDIT_ONLY"
LANE_IC_STATUS_DIRTY: str = "LANE_IC_DIRTY"
LANE_IC_STATUS_BLOCKED: str = "LANE_IC_BLOCKED"

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
    "no_lane_j_activation": True,
}

# Lane J financial action gates — all False (locked).
# These are carried on every result so operators can verify Lane I-C
# does not unlock BUY, positions, PnL, or any other Lane J capability.
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
    "lane_j_buy_unlock_active": False,
    "lane_j_sell_hold_unlock_active": False,
    "lane_j_paper_positions_unlock_active": False,
    "lane_j_pnl_unlock_active": False,
}


def classify_24h_memory_attempt(
    evidence: dict[str, Any] | None,
    *,
    operator_approved: bool = False,
) -> dict[str, Any]:
    """Classify one 24h memory factory evidence attempt.

    Returns a classification result with lane_ic_status, rejection_reasons,
    hard_locks, and locked_state.  Never writes to any DB or external system.
    Zero CLEAN_CANDIDATE outcomes is a valid result.

    Lane J financial action gates remain locked — completing Lane I-C does NOT
    unlock BUY, SELL, HOLD, paper positions, or PnL.
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
        return _result(LANE_IC_STATUS_BLOCKED, rejection_reasons=absolute_blocks)

    if not isinstance(evidence, dict):
        absolute_blocks.append("evidence must be a dict")
        return _result(LANE_IC_STATUS_BLOCKED, rejection_reasons=absolute_blocks)

    window_kind = evidence.get("window_kind")

    # ── Absolute block: window kind must be WINDOW_24H ────────────────────────
    # 24h is the final Lane I stage; prior stage kinds (15m, 1h, 4h, 12h) are
    # blocked as wrong window kind, not as future stages.
    if window_kind != LANE_IC_WINDOW_KIND:
        absolute_blocks.append(
            f"window_kind must be '{LANE_IC_WINDOW_KIND}'; got {window_kind!r}"
        )

    # ── Absolute block: 5m cannot parent or replace 24h ──────────────────────
    if evidence.get("is_5m_window") is True:
        absolute_blocks.append(
            "5m windows are support-only and cannot be used as 24h evidence"
        )

    # ── Absolute block: no fake short-window composite evidence ──────────────
    if evidence.get("is_fake_15m_composite") is True:
        absolute_blocks.append(
            "is_fake_15m_composite: 24h evidence must be genuine; "
            "do not assemble from 15m snapshots"
        )

    if evidence.get("is_fake_1h_composite") is True:
        absolute_blocks.append(
            "is_fake_1h_composite: 24h evidence must be genuine; "
            "do not assemble from 1h windows"
        )

    if evidence.get("is_fake_4h_composite") is True:
        absolute_blocks.append(
            "is_fake_4h_composite: 24h evidence must be genuine; "
            "do not assemble from 4h windows"
        )

    if evidence.get("is_fake_12h_composite") is True:
        absolute_blocks.append(
            "is_fake_12h_composite: 24h evidence must be genuine; "
            "do not assemble from 12h windows"
        )

    if absolute_blocks:
        return _result(LANE_IC_STATUS_BLOCKED, rejection_reasons=absolute_blocks)

    # ── Dirty checks (hard failure — cannot train, cannot retrieve) ───────────
    if evidence.get("do_not_train") is True:
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
    if not isinstance(snap_count, int) or snap_count < LANE_IC_MIN_SNAPSHOT_COUNT:
        dirty_reasons.append(
            f"snapshot_count {snap_count!r} is below minimum {LANE_IC_MIN_SNAPSHOT_COUNT}"
        )

    duration = evidence.get("window_duration_minutes", 0)
    if (not isinstance(duration, (int, float))) or duration < LANE_IC_MIN_WINDOW_MINUTES:
        dirty_reasons.append(
            f"window_duration_minutes {duration!r} is below minimum {LANE_IC_MIN_WINDOW_MINUTES}"
        )

    if not evidence.get("has_open_snapshot"):
        dirty_reasons.append("has_open_snapshot must be True (open snapshot required)")

    if not evidence.get("has_close_snapshot"):
        dirty_reasons.append("has_close_snapshot must be True (close snapshot required)")

    if dirty_reasons:
        return _result(LANE_IC_STATUS_DIRTY, rejection_reasons=dirty_reasons)

    # ── Audit-only checks (partial — classified, not trainable) ──────────────
    if data_quality in _PARTIAL_DATA_LABELS:
        audit_reasons.append(
            f"data_quality_label '{data_quality}' is partial; outcome is AUDIT_ONLY"
        )

    if source_status == "PARTIAL":
        audit_reasons.append("source_status is PARTIAL; outcome is AUDIT_ONLY")

    if not evidence.get("context_complete"):
        audit_reasons.append(
            "context_complete is not True; missing full 24h context"
        )

    if audit_reasons:
        return _result(LANE_IC_STATUS_AUDIT_ONLY, rejection_reasons=audit_reasons)

    # ── All gates pass → CLEAN_CANDIDATE ─────────────────────────────────────
    return _result(LANE_IC_STATUS_CLEAN_CANDIDATE, rejection_reasons=[])


def build_24h_evidence_fixture(**overrides: Any) -> dict[str, Any]:
    """Return a valid WINDOW_24H evidence dict that passes all Lane I-C gates.

    Override any field to test specific failure paths.
    """
    base: dict[str, Any] = {
        "window_kind": LANE_IC_WINDOW_KIND,
        "window_duration_minutes": 1441,
        "snapshot_count": 4,
        "has_open_snapshot": True,
        "has_close_snapshot": True,
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "context_complete": True,
        "is_5m_window": False,
        "is_fake_15m_composite": False,
        "is_fake_1h_composite": False,
        "is_fake_4h_composite": False,
        "is_fake_12h_composite": False,
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
        "lane_ic_status": status,
        "window_kind_target": LANE_IC_WINDOW_KIND,
        "is_clean_candidate": status == LANE_IC_STATUS_CLEAN_CANDIDATE,
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

"""Lane J — Financial Action Lock Review.

Reports the locked state of every financial action gate after Lane I (4h/12h/24h).

This is NOT an unlock lane.  Lane J keeps BUY, SELL, HOLD, paper decisions,
paper positions, trade events, paper trade audits, PnL, live trading, wallet/
private-key/signing, paid APIs, scoring/ranking/confidence, and embeddings/
vectors locked until separate future operator-approved lanes explicitly review them.

Pure dict-in / dict-out (no evidence dict required — only operator_approved).
No DB writes.  No CLI.  No scheduler runtime.  No source fetching.
No retrieval activation.  No paper decisions.  No trading.

Policy references (documentation-only, not executable approval):
  Lane 9  — docs/printer-v1-buy-unlock-preconditions.md
  Lane 10 — docs/printer-v1-paper-position-reactivation-review.md

Lane I completion (4h + 12h + 24h anchored) does NOT unlock Lane J gates.
Lane J can only be advanced by a separate, future, explicitly-approved lane.

Classification outcomes:
  LANE_J_LOCKED_REVIEW  — operator-approved review confirming all locks hold
  LANE_J_BLOCKED        — operator_approved not set; review cannot proceed

The only valid outcome for financial_actions_unlocked is 0.
"""

from __future__ import annotations

from typing import Any


LANE_J_STATUS_LOCKED_REVIEW: str = "LANE_J_LOCKED_REVIEW"
LANE_J_STATUS_BLOCKED: str = "LANE_J_BLOCKED"

# Documentation-only policy references (not executable approval).
LANE_J_LANE9_POLICY_REF: str = "docs/printer-v1-buy-unlock-preconditions.md"
LANE_J_LANE10_POLICY_REF: str = "docs/printer-v1-paper-position-reactivation-review.md"

# Lane I stages known to be anchored (informational only).
LANE_J_LANE_I_STAGES_ANCHORED: tuple[str, ...] = (
    "WINDOW_4H",
    "WINDOW_12H",
    "WINDOW_24H",
)

_HARD_LOCKS: dict[str, bool] = {
    "no_buy_unlock": True,
    "no_sell_unlock": True,
    "no_hold_unlock": True,
    "no_wait_avoid_no_action_creation": True,
    "no_paper_decision_creation": True,
    "no_paper_position_creation": True,
    "no_trade_event_creation": True,
    "no_paper_trade_audit_creation": True,
    "no_pnl_creation": True,
    "no_live_trading": True,
    "no_wallet_private_key": True,
    "no_signing_execution": True,
    "no_paid_api": True,
    "no_scoring_ranking_confidence": True,
    "no_embeddings_vectors": True,
    "no_source_fetching": True,
    "no_scheduler_bypass": True,
    "no_retrieval_activation": True,
    "no_db_writes": True,
    "no_clean_memory_creation": True,
}

_LOCKED_STATE: dict[str, bool] = {
    # Core financial action gates
    "buy_unlock_active": False,
    "sell_unlock_active": False,
    "hold_unlock_active": False,
    "paper_decision_creation_active": False,
    "paper_positions_active": False,
    "trade_events_active": False,
    "paper_trade_audits_active": False,
    "pnl_active": False,
    # Execution and infrastructure gates
    "live_trading_active": False,
    "wallet_active": False,
    "retrieval_active": False,
    # Policy executable approval (both remain documentation-only)
    "lane_9_executable_approval": False,
    "lane_10_executable_approval": False,
    # Lane J activation status
    "lane_j_activated": False,
    # Lane I completion does not unlock financial actions
    "lane_i_unlocked_financial_actions": False,
}


def review_financial_action_locks(
    *,
    operator_approved: bool = False,
) -> dict[str, Any]:
    """Run a Lane J financial-action lock review.

    Returns a result dict confirming every financial action gate remains
    locked.  The result is always LANE_J_LOCKED_REVIEW when approved,
    LANE_J_BLOCKED otherwise.  financial_actions_unlocked is always 0.

    Lane 9 and Lane 10 policy references are included as informational
    strings only — they do not constitute executable approval here.

    Lane I completion (4h, 12h, 24h anchored) is acknowledged but does NOT
    unlock any financial action gate.
    """
    if not operator_approved:
        return {
            "lane_j_status": LANE_J_STATUS_BLOCKED,
            "financial_actions_unlocked": 0,
            "rejection_reasons": ["operator_approved must be True to run Lane J review"],
            "hard_locks": dict(_HARD_LOCKS),
            "locked_state": dict(_LOCKED_STATE),
            "buy_enabled": False,
            "sell_enabled": False,
            "hold_enabled": False,
            "paper_decisions_created": 0,
            "paper_positions_created": 0,
            "trade_events_created": 0,
            "pnl_created": 0,
            "retrieval_activated": False,
        }

    return {
        "lane_j_status": LANE_J_STATUS_LOCKED_REVIEW,
        "financial_actions_unlocked": 0,
        "rejection_reasons": [],
        "hard_locks": dict(_HARD_LOCKS),
        "locked_state": dict(_LOCKED_STATE),
        "policy_references": {
            "lane_9_buy_preconditions": LANE_J_LANE9_POLICY_REF,
            "lane_10_position_review": LANE_J_LANE10_POLICY_REF,
            "note": (
                "These documents are documentation-only policy. "
                "They do not constitute executable approval for BUY, SELL, HOLD, "
                "paper positions, trade events, or PnL. "
                "Each requires a separate future operator-approved lane."
            ),
        },
        "lane_i_completion_note": (
            f"Lane I stages anchored: {list(LANE_J_LANE_I_STAGES_ANCHORED)}. "
            "Completing Lane I 4h/12h/24h does NOT unlock Lane J financial actions. "
            "BUY, positions, and PnL require a separate, future, explicitly-approved lane."
        ),
        "buy_enabled": False,
        "sell_enabled": False,
        "hold_enabled": False,
        "paper_decisions_created": 0,
        "paper_positions_created": 0,
        "trade_events_created": 0,
        "pnl_created": 0,
        "retrieval_activated": False,
    }

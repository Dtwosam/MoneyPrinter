"""Simulated paper position helpers."""

from datetime import datetime, timezone
from typing import Any, Mapping

from printer_v1.paper_decision.contracts import DecisionGateLabel, PaperDecisionActionLabel, PaperDecisionStatusLabel
from printer_v1.paper_monitor.contracts import PaperEntryStatusLabel, PaperPnlStateLabel, PaperPositionStatusLabel


DEFAULT_PAPER_SIZE_USD = 100.0


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_paper_entry_allowed(decision_row_or_payload: Mapping[str, Any]) -> bool:
    return classify_entry_status(decision_row_or_payload, {}) == PaperEntryStatusLabel.PAPER_ENTRY_ALLOWED


def classify_entry_status(decision_row_or_payload: Mapping[str, Any] | None, entry_evidence: Mapping[str, Any]) -> PaperEntryStatusLabel:
    if not decision_row_or_payload:
        return PaperEntryStatusLabel.PAPER_ENTRY_BLOCKED_NO_DECISION
    if decision_row_or_payload.get("paper_decision_status_label") == PaperDecisionStatusLabel.PAPER_DECISION_AUDIT_ONLY.value:
        return PaperEntryStatusLabel.PAPER_ENTRY_AUDIT_ONLY
    if (
        decision_row_or_payload.get("decision_gate_label") != DecisionGateLabel.DECISION_ALLOWED.value
        or decision_row_or_payload.get("paper_decision_status_label") != PaperDecisionStatusLabel.PAPER_DECISION_PROPOSED.value
    ):
        return PaperEntryStatusLabel.PAPER_ENTRY_BLOCKED_DECISION_NOT_ALLOWED
    if decision_row_or_payload.get("final_action_label") != PaperDecisionActionLabel.BUY.value:
        return PaperEntryStatusLabel.PAPER_ENTRY_BLOCKED_NOT_BUY_ACTION
    values = [value for context_name in ("token_snapshot", "liquidity_exit", "safety") for value in (entry_evidence.get(context_name) or {}).values()]
    if "STALE" in values or "STALE_DATA" in values or entry_evidence.get("paper_monitor_quality_label") == "PAPER_MONITOR_CONTEXT_STALE":
        return PaperEntryStatusLabel.PAPER_ENTRY_BLOCKED_STALE_CONTEXT
    if "SAFETY_UNSAFE" in values or "SAFETY_DO_NOT_USE_FOR_MEMORY" in values:
        return PaperEntryStatusLabel.PAPER_ENTRY_BLOCKED_UNSAFE_TOKEN
    if "ENTRY_UNREALISTIC" in values or "ENTRY_BLOCKED_BY_ROUTE" in values or "EXIT_UNREALISTIC" in values:
        return PaperEntryStatusLabel.PAPER_ENTRY_BLOCKED_UNREALISTIC_ENTRY
    return PaperEntryStatusLabel.PAPER_ENTRY_ALLOWED


def classify_initial_position_status(entry_status_label: PaperEntryStatusLabel | str) -> PaperPositionStatusLabel:
    if PaperEntryStatusLabel(entry_status_label) == PaperEntryStatusLabel.PAPER_ENTRY_ALLOWED:
        return PaperPositionStatusLabel.PAPER_POSITION_OPEN
    if PaperEntryStatusLabel(entry_status_label) == PaperEntryStatusLabel.PAPER_ENTRY_AUDIT_ONLY:
        return PaperPositionStatusLabel.PAPER_POSITION_BLOCKED
    return PaperPositionStatusLabel.PAPER_POSITION_BLOCKED


def calculate_paper_token_amount(paper_size_usd: float, entry_price_usd: float) -> float:
    if entry_price_usd <= 0:
        return 0.0
    return paper_size_usd / entry_price_usd


def calculate_unrealized_pnl(entry_price_usd: float, current_price_usd: float, paper_token_amount: float) -> tuple[float, float]:
    pnl_usd = (current_price_usd - entry_price_usd) * paper_token_amount
    basis = entry_price_usd * paper_token_amount
    pnl_percent = 0.0 if basis == 0 else (pnl_usd / basis) * 100
    return pnl_usd, pnl_percent


def calculate_realized_pnl(entry_price_usd: float, exit_price_usd: float, paper_token_amount: float) -> tuple[float, float]:
    return calculate_unrealized_pnl(entry_price_usd, exit_price_usd, paper_token_amount)


def classify_paper_pnl_state(unrealized_pnl_usd: float | None = None, realized_pnl_usd: float | None = None) -> PaperPnlStateLabel:
    value = realized_pnl_usd if realized_pnl_usd is not None else unrealized_pnl_usd
    if value is None:
        return PaperPnlStateLabel.PNL_UNKNOWN
    if value > 0 and realized_pnl_usd is not None:
        return PaperPnlStateLabel.PNL_REALIZED_PROFIT
    if value < 0 and realized_pnl_usd is not None:
        return PaperPnlStateLabel.PNL_REALIZED_LOSS
    if value > 0:
        return PaperPnlStateLabel.PNL_UNREALIZED_PROFIT
    if value < 0:
        return PaperPnlStateLabel.PNL_UNREALIZED_LOSS
    return PaperPnlStateLabel.PNL_BREAKEVEN


def build_paper_position_payload(
    decision_row_or_payload: Mapping[str, Any],
    entry_evidence: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or utc_now()
    decision = dict(decision_row_or_payload)
    token_snapshot = entry_evidence.get("token_snapshot") or {}
    liquidity = entry_evidence.get("liquidity_exit") or {}
    entry_price = float(token_snapshot.get("price_usd") or liquidity.get("price_usd") or 0.0)
    paper_size = DEFAULT_PAPER_SIZE_USD
    token_amount = calculate_paper_token_amount(paper_size, entry_price)
    entry_status = classify_entry_status(decision, entry_evidence)
    position_status = classify_initial_position_status(entry_status)
    return {
        "paper_decision_id": decision.get("id"),
        "retrieval_query_id": decision.get("retrieval_query_id"),
        "token_id": decision.get("token_id"),
        "pair_id": decision.get("pair_id"),
        "token_mint": decision.get("token_mint"),
        "pair_address": decision.get("pair_address"),
        "opened_at": current_time.isoformat() if position_status == PaperPositionStatusLabel.PAPER_POSITION_OPEN else None,
        "entry_price_usd": entry_price,
        "paper_size_usd": paper_size,
        "paper_token_amount": token_amount,
        "current_price_usd": entry_price,
        "unrealized_pnl_usd": 0.0,
        "unrealized_pnl_percent": 0.0,
        "max_runup_percent": 0.0,
        "max_drawdown_percent": 0.0,
        "entry_status_label": entry_status.value,
        "paper_position_status_label": position_status.value,
        "paper_monitor_state_label": "MONITOR_HEALTHY" if position_status == PaperPositionStatusLabel.PAPER_POSITION_OPEN else "MONITOR_UNKNOWN",
        "paper_exit_reason_label": "EXIT_REASON_NO_EXIT",
        "paper_pnl_state_label": PaperPnlStateLabel.PNL_BREAKEVEN.value,
        "entry_context": dict(entry_evidence),
    }

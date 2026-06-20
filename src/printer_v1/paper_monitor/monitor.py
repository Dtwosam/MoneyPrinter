"""Simulated paper position monitoring from local snapshots only."""

from datetime import datetime, timezone
from typing import Any, Mapping

from printer_v1.paper_monitor.contracts import PaperExitReasonLabel, PaperMonitorStateLabel
from printer_v1.paper_monitor.evidence import collect_paper_monitor_evidence
from printer_v1.paper_monitor.positions import calculate_realized_pnl, calculate_unrealized_pnl, classify_paper_pnl_state


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def update_position_extremes(position_payload: Mapping[str, Any], current_price_usd: float) -> dict[str, float]:
    entry_price = float(position_payload.get("entry_price_usd") or position_payload.get("paper_entry_price") or 0.0)
    if entry_price <= 0:
        return {
            "max_runup_percent": float(position_payload.get("max_runup_percent") or 0.0),
            "max_drawdown_percent": float(position_payload.get("max_drawdown_percent") or 0.0),
        }
    change_percent = ((current_price_usd - entry_price) / entry_price) * 100
    return {
        "max_runup_percent": max(float(position_payload.get("max_runup_percent") or 0.0), change_percent),
        "max_drawdown_percent": min(float(position_payload.get("max_drawdown_percent") or 0.0), change_percent),
    }


def classify_paper_monitor_state(position_payload: Mapping[str, Any], monitor_evidence: Mapping[str, Any]) -> PaperMonitorStateLabel:
    if position_payload.get("paper_position_status_label") == "PAPER_POSITION_CLOSED":
        return PaperMonitorStateLabel.MONITOR_CLOSED
    if monitor_evidence.get("paper_monitor_quality_label") == "PAPER_MONITOR_CONTEXT_STALE":
        return PaperMonitorStateLabel.MONITOR_STALE_DATA
    liquidity = monitor_evidence.get("liquidity_exit") or {}
    safety = monitor_evidence.get("safety") or {}
    if safety.get("safety_status_label") in {"SAFETY_UNSAFE", "SAFETY_DO_NOT_USE_FOR_MEMORY"}:
        return PaperMonitorStateLabel.MONITOR_SAFETY_RISK
    if liquidity.get("route_label") in {"ROUTE_FAILED", "ROUTE_NOT_AVAILABLE"}:
        return PaperMonitorStateLabel.MONITOR_ROUTE_RISK
    if liquidity.get("liquidity_state_label") in {"LIQUIDITY_DRAINING", "LIQUIDITY_DANGEROUS", "LIQUIDITY_UNSTABLE"}:
        return PaperMonitorStateLabel.MONITOR_LIQUIDITY_RISK
    current_price = float((monitor_evidence.get("token_snapshot") or {}).get("price_usd") or position_payload.get("current_price_usd") or 0.0)
    entry_price = float(position_payload.get("entry_price_usd") or position_payload.get("paper_entry_price") or 0.0)
    if entry_price > 0:
        change_percent = ((current_price - entry_price) / entry_price) * 100
        if change_percent >= 20:
            return PaperMonitorStateLabel.MONITOR_PROFIT_WATCH
        if change_percent <= -10:
            return PaperMonitorStateLabel.MONITOR_DRAWDOWN_WATCH
    return PaperMonitorStateLabel.MONITOR_HEALTHY


def classify_exit_reason(position_payload: Mapping[str, Any], monitor_evidence: Mapping[str, Any]) -> PaperExitReasonLabel:
    state = classify_paper_monitor_state(position_payload, monitor_evidence)
    if state == PaperMonitorStateLabel.MONITOR_ROUTE_RISK:
        return PaperExitReasonLabel.EXIT_REASON_ROUTE_FAILED
    if state == PaperMonitorStateLabel.MONITOR_LIQUIDITY_RISK:
        return PaperExitReasonLabel.EXIT_REASON_LIQUIDITY_EXIT_RISK
    if state == PaperMonitorStateLabel.MONITOR_SAFETY_RISK:
        return PaperExitReasonLabel.EXIT_REASON_SAFETY_RISK
    if state == PaperMonitorStateLabel.MONITOR_DRAWDOWN_WATCH:
        return PaperExitReasonLabel.EXIT_REASON_STOP_REACHED
    if state == PaperMonitorStateLabel.MONITOR_PROFIT_WATCH:
        return PaperExitReasonLabel.EXIT_REASON_TARGET_REACHED
    return PaperExitReasonLabel.EXIT_REASON_NO_EXIT


def paper_position_should_close(position_payload: Mapping[str, Any], monitor_evidence: Mapping[str, Any]) -> bool:
    return classify_exit_reason(position_payload, monitor_evidence) != PaperExitReasonLabel.EXIT_REASON_NO_EXIT


def build_paper_exit_payload(position_payload: Mapping[str, Any], monitor_evidence: Mapping[str, Any], now: datetime | None = None) -> dict[str, Any]:
    current_time = now or utc_now()
    token_snapshot = monitor_evidence.get("token_snapshot") or {}
    exit_price = float(token_snapshot.get("price_usd") or position_payload.get("current_price_usd") or 0.0)
    amount = float(position_payload.get("paper_token_amount") or 0.0)
    entry_price = float(position_payload.get("entry_price_usd") or position_payload.get("paper_entry_price") or 0.0)
    pnl_usd, pnl_percent = calculate_realized_pnl(entry_price, exit_price, amount)
    return {
        "paper_position_id": position_payload.get("id"),
        "paper_decision_id": position_payload.get("paper_decision_id"),
        "token_id": position_payload.get("token_id"),
        "pair_id": position_payload.get("pair_id"),
        "closed_at": current_time.isoformat(),
        "exit_price_usd": exit_price,
        "realized_pnl_usd": pnl_usd,
        "realized_pnl_percent": pnl_percent,
        "paper_pnl_state_label": classify_paper_pnl_state(realized_pnl_usd=pnl_usd).value,
        "paper_exit_reason_label": classify_exit_reason(position_payload, monitor_evidence).value,
        "exit_context": dict(monitor_evidence),
    }


def build_monitor_update(db_path_or_conn, paper_position_id: int, target_time: str | None = None) -> dict[str, Any]:
    evidence = collect_paper_monitor_evidence(db_path_or_conn, paper_position_id, target_time)
    position = evidence.get("paper_position") or {}
    token_snapshot = evidence.get("token_snapshot") or {}
    current_price = float(token_snapshot.get("price_usd") or position.get("current_price_usd") or 0.0)
    amount = float(position.get("paper_token_amount") or 0.0)
    entry_price = float(position.get("entry_price_usd") or position.get("paper_entry_price") or 0.0)
    pnl_usd, pnl_percent = calculate_unrealized_pnl(entry_price, current_price, amount)
    extremes = update_position_extremes(position, current_price)
    state = classify_paper_monitor_state(position, evidence)
    exit_reason = classify_exit_reason(position, evidence)
    return {
        "paper_position_id": paper_position_id,
        "current_price_usd": current_price,
        "unrealized_pnl_usd": pnl_usd,
        "unrealized_pnl_percent": pnl_percent,
        "paper_pnl_state_label": classify_paper_pnl_state(unrealized_pnl_usd=pnl_usd).value,
        "paper_monitor_state_label": state.value,
        "paper_exit_reason_label": exit_reason.value,
        "should_close": paper_position_should_close(position, evidence),
        "monitor_evidence": evidence,
        **extremes,
    }

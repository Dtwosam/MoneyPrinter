"""Paper monitor event payload helpers."""

from datetime import datetime, timezone
from typing import Any

from printer_v1.paper_monitor.contracts import PaperMonitorStateLabel, PaperTradeEventLabel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def classify_paper_trade_event_label(event_kind: str) -> PaperTradeEventLabel:
    mapping = {
        "entry_created": PaperTradeEventLabel.PAPER_EVENT_ENTRY_CREATED,
        "entry_blocked": PaperTradeEventLabel.PAPER_EVENT_ENTRY_BLOCKED,
        "position_opened": PaperTradeEventLabel.PAPER_EVENT_POSITION_OPENED,
        "snapshot_monitored": PaperTradeEventLabel.PAPER_EVENT_SNAPSHOT_MONITORED,
        "exit_risk": PaperTradeEventLabel.PAPER_EVENT_EXIT_RISK_DETECTED,
        "position_closed": PaperTradeEventLabel.PAPER_EVENT_POSITION_CLOSED,
        "position_expired": PaperTradeEventLabel.PAPER_EVENT_POSITION_EXPIRED,
        "audit_recorded": PaperTradeEventLabel.PAPER_EVENT_AUDIT_RECORDED,
    }
    return mapping.get(event_kind, PaperTradeEventLabel.PAPER_EVENT_SNAPSHOT_MONITORED)


def build_paper_trade_event_payload(
    paper_position_id: int,
    paper_decision_id: int | None,
    token_id: int | None,
    pair_id: int | None,
    event_kind: str,
    event_payload: dict[str, Any] | None = None,
    event_at: datetime | None = None,
) -> dict[str, Any]:
    payload = event_payload or {}
    event_label = classify_paper_trade_event_label(event_kind)
    return {
        "paper_position_id": paper_position_id,
        "paper_decision_id": paper_decision_id,
        "token_id": token_id,
        "pair_id": pair_id,
        "event_at": (event_at or utc_now()).isoformat(),
        "paper_trade_event_label": event_label.value,
        "paper_monitor_state_label": payload.get("paper_monitor_state_label", PaperMonitorStateLabel.MONITOR_UNKNOWN.value),
        "paper_exit_reason_label": payload.get("paper_exit_reason_label", "EXIT_REASON_NO_EXIT"),
        "paper_pnl_state_label": payload.get("paper_pnl_state_label", "PNL_UNKNOWN"),
        "event_payload": {**payload, "paper_only": True, "live_execution": False},
    }


def event_is_paper_only(event_payload: dict[str, Any]) -> bool:
    return (event_payload.get("event_payload") or {}).get("paper_only") is True


def event_has_no_live_execution(event_payload: dict[str, Any]) -> bool:
    return (event_payload.get("event_payload") or {}).get("live_execution") is False

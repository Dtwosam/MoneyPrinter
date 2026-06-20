"""Paper monitor report helpers."""

from typing import Any, Mapping


def summarize_paper_pnl(position_payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "unrealized_pnl_usd": position_payload.get("unrealized_pnl_usd"),
        "unrealized_pnl_percent": position_payload.get("unrealized_pnl_percent"),
        "realized_pnl_usd": position_payload.get("realized_pnl_usd"),
        "realized_pnl_percent": position_payload.get("realized_pnl_percent"),
        "paper_pnl_state_label": position_payload.get("paper_pnl_state_label"),
    }


def build_paper_position_report(position_payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "mode": "paper_only",
        "paper_position_id": position_payload.get("id"),
        "paper_decision_id": position_payload.get("paper_decision_id"),
        "paper_position_status_label": position_payload.get("paper_position_status_label"),
        "paper_monitor_state_label": position_payload.get("paper_monitor_state_label"),
        "pnl": summarize_paper_pnl(position_payload),
        "live_execution": False,
    }


def build_paper_monitor_update_report(position_payload: Mapping[str, Any], monitor_payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "mode": "paper_only",
        "paper_position_id": position_payload.get("id"),
        "paper_monitor_state_label": monitor_payload.get("paper_monitor_state_label"),
        "paper_exit_reason_label": monitor_payload.get("paper_exit_reason_label"),
        "should_close": bool(monitor_payload.get("should_close")),
        "pnl": summarize_paper_pnl(monitor_payload),
        "live_execution": False,
    }


def build_paper_close_report(position_payload: Mapping[str, Any], exit_payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "mode": "paper_only",
        "paper_position_id": position_payload.get("id"),
        "paper_exit_reason_label": exit_payload.get("paper_exit_reason_label"),
        "pnl": summarize_paper_pnl(exit_payload),
        "live_execution": False,
    }


def report_is_paper_only(report_payload: Mapping[str, Any]) -> bool:
    return report_payload.get("mode") == "paper_only" and report_payload.get("live_execution") is False

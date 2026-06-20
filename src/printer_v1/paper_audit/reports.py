"""Paper audit report helpers."""

from typing import Any, Mapping


def summarize_rule_compliance(evidence: Mapping[str, Any], issues: list[str]) -> dict[str, Any]:
    return {
        "paper_decision_id": (evidence.get("paper_decision") or {}).get("id"),
        "paper_position_id": (evidence.get("paper_position") or {}).get("id"),
        "issues": issues,
    }


def summarize_paper_realism(evidence: Mapping[str, Any]) -> dict[str, Any]:
    position = evidence.get("paper_position") or {}
    return {
        "entry_status_label": position.get("entry_status_label"),
        "paper_exit_reason_label": position.get("paper_exit_reason_label"),
        "paper_monitor_state_label": position.get("paper_monitor_state_label"),
    }


def summarize_outcome_review(evidence: Mapping[str, Any]) -> dict[str, Any]:
    position = evidence.get("paper_position") or {}
    return {
        "realized_pnl_usd": position.get("realized_pnl_usd"),
        "realized_pnl_percent": position.get("realized_pnl_percent"),
        "unrealized_pnl_usd": position.get("unrealized_pnl_usd"),
        "unrealized_pnl_percent": position.get("unrealized_pnl_percent"),
    }


def summarize_data_quality_audit(evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "data_quality_audit_hint": evidence.get("data_quality_audit_hint"),
        "entry_context_available": bool(evidence.get("entry_context")),
        "exit_context_available": bool(evidence.get("exit_context")),
        "monitor_event_count": len(evidence.get("monitoring_events") or []),
    }


def build_paper_audit_report(evidence: Mapping[str, Any], classification_payload: Mapping[str, Any]) -> dict[str, Any]:
    issues = list(classification_payload.get("audit_issues") or [])
    return {
        "mode": "paper_only",
        "purpose": "audit_only",
        "paper_audit_result_label": classification_payload.get("paper_audit_result_label"),
        "paper_rule_compliance_label": classification_payload.get("paper_rule_compliance_label"),
        "paper_realism_label": classification_payload.get("paper_realism_label"),
        "paper_outcome_review_label": classification_payload.get("paper_outcome_review_label"),
        "paper_data_quality_audit_label": classification_payload.get("paper_data_quality_audit_label"),
        "rule_compliance": summarize_rule_compliance(evidence, issues),
        "paper_realism": summarize_paper_realism(evidence),
        "outcome_review": summarize_outcome_review(evidence),
        "data_quality": summarize_data_quality_audit(evidence),
        "live_execution": False,
    }


def report_is_paper_audit_only(report_payload: Mapping[str, Any]) -> bool:
    return (
        report_payload.get("mode") == "paper_only"
        and report_payload.get("purpose") == "audit_only"
        and report_payload.get("live_execution") is False
    )

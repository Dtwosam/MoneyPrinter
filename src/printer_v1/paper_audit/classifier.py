"""Deterministic paper audit classification."""

from math import isclose
from typing import Any, Mapping

from printer_v1.paper_audit.contracts import (
    PaperAuditIssueLabel,
    PaperAuditResultLabel,
    PaperDataQualityAuditLabel,
    PaperOutcomeReviewLabel,
    PaperRealismLabel,
    PaperRuleComplianceLabel,
)


def collect_paper_audit_issues(evidence: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    position = evidence.get("paper_position") or {}
    decision = evidence.get("paper_decision") or {}
    entry_context = evidence.get("entry_context") or {}
    exit_context = evidence.get("exit_context") or {}
    events = evidence.get("monitoring_events") or []
    if position and not decision:
        issues.append(PaperAuditIssueLabel.ISSUE_POSITION_WITHOUT_DECISION.value)
    if not decision:
        issues.append(PaperAuditIssueLabel.ISSUE_NO_VALID_DECISION.value)
    if position and decision.get("decision_gate_label") != "DECISION_ALLOWED":
        issues.append(PaperAuditIssueLabel.ISSUE_BLOCKED_DECISION_OPENED.value)
    if position and decision.get("paper_decision_status_label") != "PAPER_DECISION_PROPOSED":
        issues.append(PaperAuditIssueLabel.ISSUE_BLOCKED_DECISION_OPENED.value)
    if position and decision.get("final_action_label") != "BUY":
        issues.append(PaperAuditIssueLabel.ISSUE_NON_BUY_DECISION_OPENED.value)
    if decision and decision.get("memory_evidence_gate_label") != "MEMORY_GATE_CLEAN_MATCH":
        issues.append(PaperAuditIssueLabel.ISSUE_NO_VALID_DECISION.value)
    if evidence.get("data_quality_audit_hint") == "STALE":
        issues.append(PaperAuditIssueLabel.ISSUE_STALE_ENTRY_CONTEXT.value)
    if any((context or {}).get("safety_status_label") == "SAFETY_UNSAFE" for context in (entry_context.get("safety"), exit_context.get("safety"))):
        issues.append(PaperAuditIssueLabel.ISSUE_UNSAFE_CONTEXT_IGNORED.value)
    if any((context or {}).get("entry_realism_label") in {"ENTRY_UNREALISTIC", "ENTRY_BLOCKED_BY_ROUTE"} for context in (entry_context.get("liquidity_exit"),)):
        issues.append(PaperAuditIssueLabel.ISSUE_UNREALISTIC_ENTRY.value)
    if any((context or {}).get("exit_realism_label") in {"EXIT_UNREALISTIC", "EXIT_BLOCKED_BY_ROUTE"} for context in (exit_context.get("liquidity_exit"),)):
        issues.append(PaperAuditIssueLabel.ISSUE_UNREALISTIC_EXIT.value)
    if any((context or {}).get("route_label") in {"ROUTE_FAILED", "ROUTE_NOT_AVAILABLE"} for context in (entry_context.get("liquidity_exit"), exit_context.get("liquidity_exit"))):
        issues.append(PaperAuditIssueLabel.ISSUE_ROUTE_RISK_IGNORED.value)
    if any((context or {}).get("liquidity_state_label") in {"LIQUIDITY_DRAINING", "LIQUIDITY_DANGEROUS", "LIQUIDITY_UNSTABLE"} for context in (entry_context.get("liquidity_exit"), exit_context.get("liquidity_exit"))):
        issues.append(PaperAuditIssueLabel.ISSUE_LIQUIDITY_RISK_IGNORED.value)
    if position and len(events) < 2:
        issues.append(PaperAuditIssueLabel.ISSUE_MONITORING_GAP.value)
    if position and position.get("paper_position_status_label") == "PAPER_POSITION_CLOSED" and not position.get("closed_at"):
        issues.append(PaperAuditIssueLabel.ISSUE_MISSING_CLOSE_EVIDENCE.value)
    if pnl_is_inconsistent(position):
        issues.append(PaperAuditIssueLabel.ISSUE_PNL_INCONSISTENT.value)
    if not issues:
        return [PaperAuditIssueLabel.ISSUE_NONE.value]
    return list(dict.fromkeys(issues))


def pnl_is_inconsistent(position: Mapping[str, Any]) -> bool:
    if not position or position.get("realized_pnl_usd") is None:
        return False
    entry = float(position.get("entry_price_usd") or position.get("paper_entry_price") or 0.0)
    exit_price = float(position.get("exit_price_usd") or position.get("paper_exit_price") or 0.0)
    amount = float(position.get("paper_token_amount") or 0.0)
    expected = (exit_price - entry) * amount
    return not isclose(expected, float(position.get("realized_pnl_usd") or 0.0), abs_tol=0.0001)


def classify_paper_rule_compliance(evidence: Mapping[str, Any]) -> PaperRuleComplianceLabel:
    issues = set(collect_paper_audit_issues(evidence))
    violations = {
        PaperAuditIssueLabel.ISSUE_NO_VALID_DECISION.value,
        PaperAuditIssueLabel.ISSUE_POSITION_WITHOUT_DECISION.value,
        PaperAuditIssueLabel.ISSUE_BLOCKED_DECISION_OPENED.value,
        PaperAuditIssueLabel.ISSUE_NON_BUY_DECISION_OPENED.value,
        PaperAuditIssueLabel.ISSUE_UNSAFE_CONTEXT_IGNORED.value,
        PaperAuditIssueLabel.ISSUE_PNL_INCONSISTENT.value,
    }
    if issues & violations:
        return PaperRuleComplianceLabel.RULES_VIOLATION
    if PaperAuditIssueLabel.ISSUE_MONITORING_GAP.value in issues or PaperAuditIssueLabel.ISSUE_MISSING_CLOSE_EVIDENCE.value in issues:
        return PaperRuleComplianceLabel.RULES_INCOMPLETE_EVIDENCE
    if issues != {PaperAuditIssueLabel.ISSUE_NONE.value}:
        return PaperRuleComplianceLabel.RULES_COMPLIANT_WITH_WARNINGS
    return PaperRuleComplianceLabel.RULES_COMPLIANT


def classify_paper_realism(evidence: Mapping[str, Any]) -> PaperRealismLabel:
    issues = set(collect_paper_audit_issues(evidence))
    if PaperAuditIssueLabel.ISSUE_UNREALISTIC_ENTRY.value in issues or PaperAuditIssueLabel.ISSUE_UNREALISTIC_EXIT.value in issues:
        return PaperRealismLabel.PAPER_REALISM_UNREALISTIC
    if PaperAuditIssueLabel.ISSUE_ROUTE_RISK_IGNORED.value in issues or PaperAuditIssueLabel.ISSUE_LIQUIDITY_RISK_IGNORED.value in issues:
        return PaperRealismLabel.PAPER_REALISM_WEAK
    if PaperAuditIssueLabel.ISSUE_MONITORING_GAP.value in issues:
        return PaperRealismLabel.PAPER_REALISM_ACCEPTABLE
    if issues == {PaperAuditIssueLabel.ISSUE_NONE.value}:
        return PaperRealismLabel.PAPER_REALISM_CLEAN
    return PaperRealismLabel.PAPER_REALISM_UNKNOWN


def classify_paper_outcome_review(evidence: Mapping[str, Any]) -> PaperOutcomeReviewLabel:
    position = evidence.get("paper_position") or {}
    decision = evidence.get("paper_decision") or {}
    if not position:
        if decision.get("final_action_label") in {"NO_ACTION", "WAIT", "AVOID"}:
            return PaperOutcomeReviewLabel.PAPER_OUTCOME_NO_ACTION_VALID
        return PaperOutcomeReviewLabel.PAPER_OUTCOME_UNKNOWN
    realized = position.get("realized_pnl_usd")
    unrealized = position.get("unrealized_pnl_usd")
    value = realized if realized is not None else unrealized
    if value is None:
        return PaperOutcomeReviewLabel.PAPER_OUTCOME_INCONCLUSIVE
    if float(value) > 0:
        return PaperOutcomeReviewLabel.PAPER_OUTCOME_WORKED
    if float(value) < 0:
        return PaperOutcomeReviewLabel.PAPER_OUTCOME_FAILED
    return PaperOutcomeReviewLabel.PAPER_OUTCOME_INCONCLUSIVE


def classify_paper_data_quality_audit(evidence: Mapping[str, Any]) -> PaperDataQualityAuditLabel:
    hint = evidence.get("data_quality_audit_hint")
    if hint == "CLEAN":
        return PaperDataQualityAuditLabel.PAPER_AUDIT_DATA_CLEAN
    if hint == "PARTIAL":
        return PaperDataQualityAuditLabel.PAPER_AUDIT_DATA_PARTIAL
    if hint == "STALE":
        return PaperDataQualityAuditLabel.PAPER_AUDIT_DATA_STALE
    if hint == "CONFLICTING":
        return PaperDataQualityAuditLabel.PAPER_AUDIT_DATA_CONFLICTING
    if hint == "MISSING":
        return PaperDataQualityAuditLabel.PAPER_AUDIT_DATA_MISSING
    return PaperDataQualityAuditLabel.PAPER_AUDIT_DATA_UNKNOWN


def classify_paper_audit_result(evidence: Mapping[str, Any]) -> PaperAuditResultLabel:
    compliance = classify_paper_rule_compliance(evidence)
    realism = classify_paper_realism(evidence)
    data = classify_paper_data_quality_audit(evidence)
    if compliance == PaperRuleComplianceLabel.RULES_VIOLATION or realism == PaperRealismLabel.PAPER_REALISM_UNREALISTIC:
        return PaperAuditResultLabel.PAPER_AUDIT_FAIL
    if data in {PaperDataQualityAuditLabel.PAPER_AUDIT_DATA_MISSING, PaperDataQualityAuditLabel.PAPER_AUDIT_DATA_UNKNOWN}:
        return PaperAuditResultLabel.PAPER_AUDIT_INCOMPLETE
    if compliance == PaperRuleComplianceLabel.RULES_INCOMPLETE_EVIDENCE:
        return PaperAuditResultLabel.PAPER_AUDIT_INCOMPLETE
    if data in {PaperDataQualityAuditLabel.PAPER_AUDIT_DATA_STALE, PaperDataQualityAuditLabel.PAPER_AUDIT_DATA_CONFLICTING}:
        return PaperAuditResultLabel.PAPER_AUDIT_AUDIT_ONLY
    if compliance == PaperRuleComplianceLabel.RULES_COMPLIANT_WITH_WARNINGS or realism in {PaperRealismLabel.PAPER_REALISM_ACCEPTABLE, PaperRealismLabel.PAPER_REALISM_WEAK}:
        return PaperAuditResultLabel.PAPER_AUDIT_PASS_WITH_WARNINGS
    if compliance == PaperRuleComplianceLabel.RULES_COMPLIANT:
        return PaperAuditResultLabel.PAPER_AUDIT_PASS
    return PaperAuditResultLabel.PAPER_AUDIT_UNKNOWN


def paper_audit_passes(evidence: Mapping[str, Any]) -> bool:
    return classify_paper_audit_result(evidence) in {
        PaperAuditResultLabel.PAPER_AUDIT_PASS,
        PaperAuditResultLabel.PAPER_AUDIT_PASS_WITH_WARNINGS,
    }


def paper_audit_requires_manual_review(evidence: Mapping[str, Any]) -> bool:
    return classify_paper_audit_result(evidence) in {
        PaperAuditResultLabel.PAPER_AUDIT_INCOMPLETE,
        PaperAuditResultLabel.PAPER_AUDIT_AUDIT_ONLY,
        PaperAuditResultLabel.PAPER_AUDIT_UNKNOWN,
    }

"""Paper-only decision report helpers."""

from typing import Any, Mapping


def summarize_memory_support(evidence: Mapping[str, Any]) -> dict[str, Any]:
    retrieval = evidence.get("memory_retrieval") or {}
    clean_matches = retrieval.get("clean_matches") or []
    outcomes: dict[str, int] = {}
    lessons: dict[str, int] = {}
    for match in clean_matches:
        outcome = match.get("outcome_label") or "OUTCOME_UNKNOWN"
        lesson = match.get("action_lesson_label") or "ACTION_LESSON_UNKNOWN"
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        lessons[lesson] = lessons.get(lesson, 0) + 1
    return {
        "clean_match_count": len(clean_matches),
        "historical_outcomes": outcomes,
        "action_lessons": lessons,
    }


def summarize_current_context_blocks(evidence: Mapping[str, Any]) -> dict[str, Any]:
    context = evidence.get("current_context") or {}
    return {
        "safety_status_label": context.get("safety_status_label"),
        "liquidity_state_label": context.get("liquidity_state_label"),
        "exit_realism_label": context.get("exit_realism_label"),
        "route_label": context.get("route_label"),
        "flow_direction_label": context.get("flow_direction_label"),
        "trend_structure_label": context.get("trend_structure_label"),
        "source_status": context.get("source_status"),
        "data_quality_label": context.get("data_quality_label"),
    }


def summarize_decision_reasons(decision_payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "decision_reasons": list(decision_payload.get("decision_reasons") or []),
        "blocking_reasons": list(decision_payload.get("blocking_reasons") or []),
    }


def build_paper_decision_report(decision_payload: Mapping[str, Any]) -> dict[str, Any]:
    evidence = decision_payload.get("evidence") or {}
    return {
        "mode": "paper_only",
        "decision": decision_payload.get("final_action_label"),
        "requested_action": decision_payload.get("requested_action_label"),
        "decision_gate_label": decision_payload.get("decision_gate_label"),
        "memory_evidence_gate_label": decision_payload.get("memory_evidence_gate_label"),
        "paper_decision_status_label": decision_payload.get("paper_decision_status_label"),
        "memory_support": summarize_memory_support(evidence),
        "current_context": summarize_current_context_blocks(evidence),
        "reasons": summarize_decision_reasons(decision_payload),
        "live_execution": False,
    }


def report_is_safe_for_paper_only(decision_report: Mapping[str, Any]) -> bool:
    return decision_report.get("mode") == "paper_only" and decision_report.get("live_execution") is False

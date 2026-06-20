"""Memory retrieval evidence reports without recommendations."""

from typing import Any, Mapping

from printer_v1.memory_retrieval.contracts import RetrievalResultLabel
from printer_v1.memory_retrieval.retriever import group_matches_by_outcome


def summarize_historical_outcomes(matches: list[Mapping[str, Any]]) -> dict[str, int]:
    return group_matches_by_outcome(matches)


def summarize_action_lessons(matches: list[Mapping[str, Any]]) -> dict[str, int]:
    grouped: dict[str, int] = {}
    for match in matches:
        label = match.get("action_lesson_label") or "ACTION_LESSON_UNKNOWN"
        grouped[label] = grouped.get(label, 0) + 1
    return grouped


def summarize_blocking_reasons(matches: list[Mapping[str, Any]]) -> dict[str, int]:
    grouped: dict[str, int] = {}
    for match in matches:
        for reason in match.get("mismatch_reasons", []):
            grouped[reason] = grouped.get(reason, 0) + 1
    return grouped


def build_memory_comparison_report(query_payload: Mapping[str, Any], matches: list[Mapping[str, Any]]) -> dict[str, Any]:
    clean_matches = [match for match in matches if match.get("included_as_clean_evidence")]
    return {
        "query_type": query_payload.get("query_type"),
        "clean_match_count": len(clean_matches),
        "audit_context_count": len([match for match in matches if match.get("included_as_audit_context")]),
        "historical_outcomes": summarize_historical_outcomes(clean_matches),
        "action_lessons": summarize_action_lessons(clean_matches),
        "blocking_reasons": summarize_blocking_reasons(matches),
        "recommendation": None,
    }


def report_has_enough_clean_memory(report: Mapping[str, Any]) -> bool:
    return int(report.get("clean_match_count") or 0) > 0

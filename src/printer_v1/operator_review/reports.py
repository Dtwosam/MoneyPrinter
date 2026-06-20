"""Operator review report builders."""

from datetime import datetime, timezone
from typing import Any, Mapping

from printer_v1.operator_review.contracts import ReportFormatLabel, ReportScopeLabel
from printer_v1.operator_review.summaries import (
    classify_operator_review,
    classify_report_status,
    collect_attention_labels,
    summarize_db_state,
    summarize_full_operator_review,
    summarize_memory,
    summarize_paper_audits,
    summarize_paper_decisions,
    summarize_paper_positions,
    summarize_system_health,
    summarize_token_snapshots,
)


def utc_now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def title_for_scope(scope: ReportScopeLabel) -> str:
    return scope.value.replace("REPORT_", "").replace("_", " ").title()


def build_payload(scope: ReportScopeLabel, summary: Mapping[str, Any], now: datetime | None = None, report_format_label: ReportFormatLabel = ReportFormatLabel.REPORT_FORMAT_JSON) -> dict[str, Any]:
    attention = list(summary.get("attention_labels") or collect_attention_labels(summary))
    status = classify_report_status(summary)
    review = classify_operator_review(summary)
    return {
        "mode": "paper_only",
        "purpose": "operator_review_only",
        "review_only": True,
        "report_scope_label": scope.value,
        "report_status_label": status.value,
        "operator_review_label": review.value,
        "report_format_label": report_format_label.value,
        "generated_at": utc_now_iso(now),
        "db_state_classification": summary.get("db_state_classification"),
        "report_title": title_for_scope(scope),
        "attention_labels": attention,
        "summary": dict(summary),
        "items": build_report_items(scope, attention, summary),
    }


def build_report_items(scope: ReportScopeLabel, attention: list[str], summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "item_scope_label": scope.value,
            "operator_review_label": classify_operator_review(summary).value,
            "attention_label": label,
            "item_payload": {"subject": summary.get("subject"), "db_state_classification": summary.get("db_state_classification")},
        }
        for label in attention
    ]


def build_db_state_report(evidence: Mapping[str, Any], now: datetime | None = None) -> dict[str, Any]:
    return build_payload(ReportScopeLabel.REPORT_DB_STATE, summarize_db_state(evidence), now)


def build_system_health_report(evidence: Mapping[str, Any], now: datetime | None = None) -> dict[str, Any]:
    return build_payload(ReportScopeLabel.REPORT_SYSTEM_HEALTH, summarize_system_health(evidence), now)


def build_token_review_report(evidence: Mapping[str, Any], token_id=None, pair_id=None, now: datetime | None = None) -> dict[str, Any]:
    payload = build_payload(ReportScopeLabel.REPORT_TOKEN_SNAPSHOTS, summarize_token_snapshots(evidence), now)
    payload["token_id"] = token_id
    payload["pair_id"] = pair_id
    return payload


def build_memory_review_report(evidence: Mapping[str, Any], token_id=None, pair_id=None, now: datetime | None = None) -> dict[str, Any]:
    payload = build_payload(ReportScopeLabel.REPORT_MEMORY, summarize_memory(evidence), now)
    payload["token_id"] = token_id
    payload["pair_id"] = pair_id
    return payload


def build_paper_trading_review_report(evidence: Mapping[str, Any], token_id=None, pair_id=None, now: datetime | None = None) -> dict[str, Any]:
    summary = {
        "subject": "paper_trading",
        "db_state_classification": evidence.get("paper_positions", {}).get("state_classification"),
        "paper_decisions": summarize_paper_decisions(evidence.get("paper_decisions", {})),
        "paper_positions": summarize_paper_positions(evidence.get("paper_positions", {})),
        "paper_audits": summarize_paper_audits(evidence.get("paper_audits", {})),
    }
    summary["attention_labels"] = []
    for section in ("paper_decisions", "paper_positions", "paper_audits"):
        summary["attention_labels"].extend(collect_attention_labels(summary[section]))
    payload = build_payload(ReportScopeLabel.REPORT_PAPER_POSITIONS, summary, now)
    payload["token_id"] = token_id
    payload["pair_id"] = pair_id
    return payload


def build_full_operator_review_report(evidence: Mapping[str, Any], token_id=None, pair_id=None, now: datetime | None = None) -> dict[str, Any]:
    payload = build_payload(ReportScopeLabel.REPORT_FULL_OPERATOR_REVIEW, summarize_full_operator_review(evidence), now)
    payload["token_id"] = token_id
    payload["pair_id"] = pair_id
    return payload


def build_operator_report_payload(report_scope_label: str | ReportScopeLabel, evidence: Mapping[str, Any], now: datetime | None = None) -> dict[str, Any]:
    scope = ReportScopeLabel(report_scope_label)
    if scope == ReportScopeLabel.REPORT_DB_STATE:
        return build_db_state_report(evidence, now)
    if scope == ReportScopeLabel.REPORT_SYSTEM_HEALTH:
        return build_system_health_report(evidence, now)
    if scope == ReportScopeLabel.REPORT_TOKEN_SNAPSHOTS:
        return build_token_review_report(evidence, now=now)
    if scope == ReportScopeLabel.REPORT_MEMORY:
        return build_memory_review_report(evidence, now=now)
    if scope == ReportScopeLabel.REPORT_PAPER_POSITIONS:
        return build_paper_trading_review_report(evidence, now=now)
    if scope == ReportScopeLabel.REPORT_FULL_OPERATOR_REVIEW:
        return build_full_operator_review_report(evidence, now=now)
    return build_payload(scope, summarize_system_health(evidence), now)


def report_payload_is_review_only(report_payload: Mapping[str, Any]) -> bool:
    return (
        report_payload.get("mode") == "paper_only"
        and report_payload.get("purpose") == "operator_review_only"
        and report_payload.get("review_only") is True
    )

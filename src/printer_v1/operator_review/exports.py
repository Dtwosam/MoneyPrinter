"""Local operator report formatting helpers."""

import json
from typing import Any, Mapping

from printer_v1.operator_review.contracts import ReportFormatLabel


def validate_report_format(report_format_label: str | ReportFormatLabel) -> ReportFormatLabel:
    return ReportFormatLabel(report_format_label)


def export_report_as_json_payload(report_payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(dict(report_payload), sort_keys=True, default=str))


def export_report_as_markdown_text(report_payload: Mapping[str, Any]) -> str:
    lines = [
        f"# {report_payload.get('report_title', 'Operator Review')}",
        "",
        f"- Scope: {report_payload.get('report_scope_label')}",
        f"- Status: {report_payload.get('report_status_label')}",
        f"- Review: {report_payload.get('operator_review_label')}",
        f"- DB State: {report_payload.get('db_state_classification')}",
        f"- Attention: {', '.join(report_payload.get('attention_labels') or [])}",
        "",
        "This report is paper-only and review-only.",
    ]
    return "\n".join(lines)


def export_report_as_plain_text(report_payload: Mapping[str, Any]) -> str:
    return (
        f"{report_payload.get('report_title', 'Operator Review')}\n"
        f"Scope: {report_payload.get('report_scope_label')}\n"
        f"Status: {report_payload.get('report_status_label')}\n"
        f"Review: {report_payload.get('operator_review_label')}\n"
        f"DB State: {report_payload.get('db_state_classification')}\n"
        f"Attention: {', '.join(report_payload.get('attention_labels') or [])}\n"
        "Paper-only review-only report."
    )

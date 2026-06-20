"""Validation report builders for synthetic hardening runs."""

from __future__ import annotations

from collections import Counter
from typing import Any

from printer_v1.hardening.contracts import ValidationResultLabel


def summarize_validation_items(validation_items: list[dict[str, Any]]) -> dict[str, Any]:
    by_result = Counter(item.get("validation_result_label") for item in validation_items)
    by_stage = Counter(item.get("flow_stage_label") for item in validation_items)
    issues = [
        item.get("validation_issue_label")
        for item in validation_items
        if item.get("validation_issue_label") != "VALIDATION_ISSUE_NONE"
    ]
    return {
        "item_count": len(validation_items),
        "result_counts": dict(sorted(by_result.items())),
        "stage_counts": dict(sorted(by_stage.items())),
        "issues": issues,
    }


def build_validation_run_report(validation_payload: dict[str, Any]) -> dict[str, Any]:
    items = validation_payload.get("items", [])
    summary = summarize_validation_items(items)
    has_failures = any(
        item.get("validation_result_label") == ValidationResultLabel.VALIDATION_FAIL.value
        for item in items
    )
    result = (
        ValidationResultLabel.VALIDATION_FAIL.value
        if has_failures
        else validation_payload.get("validation_result_label", ValidationResultLabel.VALIDATION_PASS.value)
    )
    return {
        "validation_scope_label": validation_payload.get("validation_scope_label"),
        "validation_result_label": result,
        "synthetic_only": True,
        "paper_only": True,
        "temp_db_only": bool(validation_payload.get("temp_db_only", True)),
        "project_db_created": bool(validation_payload.get("project_db_created", False)),
        "summary": summary,
        "items": items,
    }


def validation_report_passes(validation_report: dict[str, Any]) -> bool:
    return validation_report.get("validation_result_label") == ValidationResultLabel.VALIDATION_PASS.value


def validation_report_has_blockers(validation_report: dict[str, Any]) -> bool:
    return not validation_report_passes(validation_report)


def report_is_synthetic_only(report_payload: dict[str, Any]) -> bool:
    return bool(report_payload.get("synthetic_only")) and bool(report_payload.get("temp_db_only", True))

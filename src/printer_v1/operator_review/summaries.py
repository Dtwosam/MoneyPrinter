"""Deterministic operator review summary builders."""

from typing import Any, Mapping

from printer_v1.operator_db.status import STATE_NO_DB, STATE_SCHEMA_ONLY
from printer_v1.operator_review.contracts import (
    OperatorAttentionLabel,
    OperatorReviewLabel,
    ReportStatusLabel,
)


def values_count(rows: list[Mapping[str, Any]] | None) -> int:
    return len(rows or [])


def base_summary(evidence: Mapping[str, Any], subject: str) -> dict[str, Any]:
    state = evidence.get("state_classification") or (evidence.get("db_state") or {}).get("state_classification")
    return {
        "subject": subject,
        "db_path": evidence.get("db_path"),
        "db_state_classification": state,
        "row_groups": {},
        "attention_labels": [],
    }


def summarize_db_state(evidence: Mapping[str, Any]) -> dict[str, Any]:
    summary = base_summary(evidence, "db_state")
    counts = evidence.get("counts") or {}
    summary["row_groups"] = {"core_tables": counts}
    summary["total_non_schema_rows"] = sum(count or 0 for table, count in counts.items() if table != "printer_schema_migrations")
    return summary


def summarize_system_health(evidence: Mapping[str, Any]) -> dict[str, Any]:
    summary = base_summary(evidence, "system_health")
    counts = evidence.get("counts") or {}
    summary["row_groups"] = {"core_tables": counts}
    summary["source_failure_count"] = counts.get("printer_source_failures") or 0
    summary["scheduler_job_count"] = counts.get("printer_scheduler_jobs") or 0
    summary["token_snapshot_count"] = counts.get("printer_token_snapshots") or 0
    summary["memory_window_count"] = counts.get("printer_memory_windows") or 0
    summary["paper_position_count"] = counts.get("printer_paper_positions") or 0
    return summary


def summarize_source_health(evidence: Mapping[str, Any]) -> dict[str, Any]:
    summary = base_summary(evidence, "source_health")
    summary["request_count"] = values_count(evidence.get("latest_requests"))
    summary["response_count"] = values_count(evidence.get("latest_responses"))
    summary["failure_count"] = evidence.get("failure_count", 0)
    summary["latest_failures"] = evidence.get("latest_failures", [])
    return summary


def summarize_scheduler_health(evidence: Mapping[str, Any]) -> dict[str, Any]:
    summary = base_summary(evidence, "scheduler_health")
    summary["pending_jobs"] = evidence.get("pending_jobs", 0)
    summary["running_jobs"] = evidence.get("running_jobs", 0)
    summary["failed_jobs"] = evidence.get("failed_jobs", 0)
    summary["latest_jobs"] = evidence.get("latest_jobs", [])
    return summary


def summarize_lifecycle_queue(evidence: Mapping[str, Any]) -> dict[str, Any]:
    summary = base_summary(evidence, "lifecycle_queue")
    summary["queue_item_count"] = values_count(evidence.get("queue_items"))
    summary["lifecycle_event_count"] = values_count(evidence.get("lifecycle_events"))
    return summary


def summarize_discovery(evidence: Mapping[str, Any]) -> dict[str, Any]:
    summary = base_summary(evidence, "discovery")
    summary["discovery_count"] = values_count(evidence.get("discoveries"))
    return summary


def summarize_token_snapshots(evidence: Mapping[str, Any]) -> dict[str, Any]:
    summary = base_summary(evidence, "token_snapshots")
    summary["snapshot_count"] = values_count(evidence.get("snapshots"))
    summary["stale_snapshot_count"] = evidence.get("stale_count", 0)
    return summary


def summarize_context_engines(evidence: Mapping[str, Any]) -> dict[str, Any]:
    summary = base_summary(evidence, "context_engines")
    for key in ("market", "chain_heat", "safety", "liquidity_exit", "trading_flow", "chart_volatility", "micro_events"):
        summary[f"{key}_count"] = values_count(evidence.get(key))
    return summary


def summarize_memory(evidence: Mapping[str, Any]) -> dict[str, Any]:
    summary = base_summary(evidence, "memory")
    summary["window_count"] = values_count(evidence.get("windows"))
    summary["episode_count"] = values_count(evidence.get("episodes"))
    summary["clean_memory_count"] = evidence.get("clean_memory_count", 0)
    summary["dirty_memory_count"] = evidence.get("dirty_memory_count", 0)
    return summary


def summarize_memory_retrieval(evidence: Mapping[str, Any]) -> dict[str, Any]:
    summary = base_summary(evidence, "memory_retrieval")
    summary["query_count"] = values_count(evidence.get("queries"))
    summary["match_count"] = values_count(evidence.get("matches"))
    return summary


def summarize_paper_decisions(evidence: Mapping[str, Any]) -> dict[str, Any]:
    summary = base_summary(evidence, "paper_decisions")
    summary["decision_count"] = values_count(evidence.get("decisions"))
    summary["blocked_decision_count"] = evidence.get("blocked_count", 0)
    return summary


def summarize_paper_positions(evidence: Mapping[str, Any]) -> dict[str, Any]:
    summary = base_summary(evidence, "paper_positions")
    summary["position_count"] = values_count(evidence.get("positions"))
    summary["event_count"] = values_count(evidence.get("events"))
    summary["open_position_count"] = evidence.get("open_count", 0)
    summary["exit_risk_count"] = evidence.get("exit_risk_count", 0)
    return summary


def summarize_paper_audits(evidence: Mapping[str, Any]) -> dict[str, Any]:
    summary = base_summary(evidence, "paper_audits")
    summary["audit_count"] = values_count(evidence.get("audits"))
    summary["audit_failure_count"] = evidence.get("failure_count", 0)
    return summary


def collect_attention_labels(summary_payload: Mapping[str, Any]) -> list[str]:
    labels: list[str] = []
    state = summary_payload.get("db_state_classification")
    if state == STATE_NO_DB:
        labels.append(OperatorAttentionLabel.ATTENTION_NO_PERSISTENT_DB.value)
    if state == STATE_SCHEMA_ONLY:
        labels.append(OperatorAttentionLabel.ATTENTION_SCHEMA_ONLY_DB.value)
    if summary_payload.get("failure_count", 0) > 0 or summary_payload.get("source_failure_count", 0) > 0:
        labels.append(OperatorAttentionLabel.ATTENTION_SOURCE_FAILURES.value)
    if summary_payload.get("pending_jobs", 0) > 0 or summary_payload.get("failed_jobs", 0) > 0:
        labels.append(OperatorAttentionLabel.ATTENTION_SCHEDULER_BACKLOG.value)
    if summary_payload.get("stale_snapshot_count", 0) > 0:
        labels.append(OperatorAttentionLabel.ATTENTION_STALE_SNAPSHOTS.value)
    if summary_payload.get("dirty_memory_count", 0) > 0:
        labels.append(OperatorAttentionLabel.ATTENTION_DIRTY_MEMORY.value)
    if summary_payload.get("window_count", 0) > 0 and summary_payload.get("clean_memory_count", 0) == 0:
        labels.append(OperatorAttentionLabel.ATTENTION_NO_CLEAN_MEMORY.value)
    if summary_payload.get("blocked_decision_count", 0) > 0:
        labels.append(OperatorAttentionLabel.ATTENTION_BLOCKED_PAPER_DECISIONS.value)
    if summary_payload.get("open_position_count", 0) > 0:
        labels.append(OperatorAttentionLabel.ATTENTION_OPEN_PAPER_POSITION.value)
    if summary_payload.get("exit_risk_count", 0) > 0:
        labels.append(OperatorAttentionLabel.ATTENTION_PAPER_EXIT_RISK.value)
    if summary_payload.get("audit_failure_count", 0) > 0:
        labels.append(OperatorAttentionLabel.ATTENTION_PAPER_AUDIT_FAILURE.value)
    if not labels:
        return [OperatorAttentionLabel.ATTENTION_NONE.value]
    return list(dict.fromkeys(labels))


def classify_report_status(summary_payload: Mapping[str, Any]) -> ReportStatusLabel:
    state = summary_payload.get("db_state_classification")
    if state == STATE_NO_DB:
        return ReportStatusLabel.REPORT_NO_DB
    if state == STATE_SCHEMA_ONLY:
        return ReportStatusLabel.REPORT_SCHEMA_ONLY
    if summary_payload.get("failure_count", 0) > 0:
        return ReportStatusLabel.REPORT_PARTIAL
    if summary_payload.get("stale_snapshot_count", 0) > 0:
        return ReportStatusLabel.REPORT_STALE
    payload_values = [value for key, value in summary_payload.items() if key.endswith("_count")]
    if payload_values and all(not value for value in payload_values):
        return ReportStatusLabel.REPORT_EMPTY
    if state:
        return ReportStatusLabel.REPORT_READY
    return ReportStatusLabel.REPORT_UNKNOWN


def classify_operator_review(summary_payload: Mapping[str, Any]) -> OperatorReviewLabel:
    status = classify_report_status(summary_payload)
    if status == ReportStatusLabel.REPORT_NO_DB:
        return OperatorReviewLabel.OPERATOR_REVIEW_NO_DB
    if status == ReportStatusLabel.REPORT_SCHEMA_ONLY:
        return OperatorReviewLabel.OPERATOR_REVIEW_SCHEMA_ONLY
    attention = set(collect_attention_labels(summary_payload))
    if attention == {OperatorAttentionLabel.ATTENTION_NONE.value}:
        return OperatorReviewLabel.OPERATOR_REVIEW_OK
    if status == ReportStatusLabel.REPORT_EMPTY:
        return OperatorReviewLabel.OPERATOR_REVIEW_NO_DATA
    return OperatorReviewLabel.OPERATOR_REVIEW_NEEDS_ATTENTION


def summarize_full_operator_review(evidence: Mapping[str, Any]) -> dict[str, Any]:
    sections = {
        "db_state": summarize_db_state(evidence["db_state"]),
        "system_health": summarize_system_health(evidence["system_health"]),
        "source_health": summarize_source_health(evidence["source_health"]),
        "scheduler_health": summarize_scheduler_health(evidence["scheduler_health"]),
        "lifecycle_queue": summarize_lifecycle_queue(evidence["lifecycle_queue"]),
        "discovery": summarize_discovery(evidence["discovery"]),
        "token_snapshots": summarize_token_snapshots(evidence["token_snapshots"]),
        "context_engines": summarize_context_engines(evidence["context_engines"]),
        "memory": summarize_memory(evidence["memory"]),
        "memory_retrieval": summarize_memory_retrieval(evidence["memory_retrieval"]),
        "paper_decisions": summarize_paper_decisions(evidence["paper_decisions"]),
        "paper_positions": summarize_paper_positions(evidence["paper_positions"]),
        "paper_audits": summarize_paper_audits(evidence["paper_audits"]),
    }
    state = sections["db_state"].get("db_state_classification")
    combined: dict[str, Any] = {
        "subject": "full_operator_review",
        "db_state_classification": state,
        "sections": sections,
        "attention_labels": [],
    }
    labels: list[str] = []
    for section in sections.values():
        labels.extend(collect_attention_labels(section))
    combined["attention_labels"] = list(dict.fromkeys(labels)) or [OperatorAttentionLabel.ATTENTION_NONE.value]
    return combined

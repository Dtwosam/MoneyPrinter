"""SQLite-backed Paper Audit recorder."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.paper_audit.classifier import (
    classify_paper_audit_result,
    classify_paper_data_quality_audit,
    classify_paper_outcome_review,
    classify_paper_realism,
    classify_paper_rule_compliance,
    collect_paper_audit_issues,
)
from printer_v1.paper_audit.contracts import (
    PaperAuditResultLabel,
    PaperAuditScopeLabel,
    PaperDataQualityAuditLabel,
    PaperOutcomeReviewLabel,
    PaperRealismLabel,
    PaperRuleComplianceLabel,
)
from printer_v1.paper_audit.evidence import collect_paper_audit_evidence
from printer_v1.paper_audit.reports import build_paper_audit_report
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import enqueue_job


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@contextmanager
def connect(db_or_connection: str | Path | sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    if isinstance(db_or_connection, sqlite3.Connection):
        db_or_connection.row_factory = sqlite3.Row
        yield db_or_connection
        return
    connection = sqlite3.connect(Path(db_or_connection))
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def build_classification_payload(evidence: Mapping[str, Any], scope: PaperAuditScopeLabel = PaperAuditScopeLabel.AUDIT_FULL_PAPER_TRADE) -> dict[str, Any]:
    return {
        "audit_scope_label": scope.value,
        "paper_audit_result_label": classify_paper_audit_result(evidence).value,
        "paper_rule_compliance_label": classify_paper_rule_compliance(evidence).value,
        "paper_realism_label": classify_paper_realism(evidence).value,
        "paper_outcome_review_label": classify_paper_outcome_review(evidence).value,
        "paper_data_quality_audit_label": classify_paper_data_quality_audit(evidence).value,
        "audit_issues": collect_paper_audit_issues(evidence),
    }


def build_audit_payload(
    evidence: Mapping[str, Any],
    audit_at: datetime | None = None,
    scope: PaperAuditScopeLabel = PaperAuditScopeLabel.AUDIT_FULL_PAPER_TRADE,
) -> dict[str, Any]:
    current_time = audit_at or utc_now()
    classification = build_classification_payload(evidence, scope)
    report = build_paper_audit_report(evidence, classification)
    position = evidence.get("paper_position") or {}
    decision = evidence.get("paper_decision") or {}
    return {
        "paper_position_id": position.get("id"),
        "paper_decision_id": decision.get("id"),
        "retrieval_query_id": decision.get("retrieval_query_id") or position.get("retrieval_query_id"),
        "token_id": position.get("token_id") or decision.get("token_id"),
        "pair_id": position.get("pair_id") or decision.get("pair_id"),
        "token_mint": position.get("token_mint") or decision.get("token_mint"),
        "pair_address": position.get("pair_address") or decision.get("pair_address"),
        "audit_at": current_time.isoformat(),
        "decision_audit": decision,
        "entry_audit": evidence.get("entry_context") or {},
        "monitoring_audit": {"events": evidence.get("monitoring_events") or []},
        "exit_audit": evidence.get("exit_context") or {},
        "pnl_audit": {
            "realized_pnl_usd": position.get("realized_pnl_usd"),
            "realized_pnl_percent": position.get("realized_pnl_percent"),
            "unrealized_pnl_usd": position.get("unrealized_pnl_usd"),
            "unrealized_pnl_percent": position.get("unrealized_pnl_percent"),
        },
        "rule_compliance": {"issues": classification["audit_issues"]},
        "audit_report": report,
        **classification,
    }


def record_paper_audit_report(db_path_or_conn: str | Path | sqlite3.Connection, audit_payload: Mapping[str, Any]) -> int:
    with connect(db_path_or_conn) as connection:
        duplicate = connection.execute(
            """
            SELECT id
            FROM printer_paper_audit_reports
            WHERE COALESCE(paper_position_id, -1) = COALESCE(?, -1)
              AND COALESCE(paper_decision_id, -1) = COALESCE(?, -1)
              AND audit_at = ?
            LIMIT 1
            """,
            (audit_payload.get("paper_position_id"), audit_payload.get("paper_decision_id"), audit_payload.get("audit_at")),
        ).fetchone()
        if duplicate:
            return int(duplicate["id"])
        cursor = connection.execute(
            """
            INSERT INTO printer_paper_audit_reports (
                paper_position_id, paper_decision_id, retrieval_query_id,
                token_id, pair_id, token_mint, pair_address, audit_at,
                audit_scope_label, paper_audit_result_label,
                paper_rule_compliance_label, paper_realism_label,
                paper_outcome_review_label, paper_data_quality_audit_label,
                audit_issues_json, decision_audit_json, entry_audit_json,
                monitoring_audit_json, exit_audit_json, pnl_audit_json,
                rule_compliance_json, audit_report_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_payload.get("paper_position_id"),
                audit_payload.get("paper_decision_id"),
                audit_payload.get("retrieval_query_id"),
                audit_payload.get("token_id"),
                audit_payload.get("pair_id"),
                audit_payload.get("token_mint"),
                audit_payload.get("pair_address"),
                audit_payload.get("audit_at"),
                PaperAuditScopeLabel(audit_payload["audit_scope_label"]).value,
                PaperAuditResultLabel(audit_payload["paper_audit_result_label"]).value,
                PaperRuleComplianceLabel(audit_payload["paper_rule_compliance_label"]).value,
                PaperRealismLabel(audit_payload["paper_realism_label"]).value,
                PaperOutcomeReviewLabel(audit_payload["paper_outcome_review_label"]).value,
                PaperDataQualityAuditLabel(audit_payload["paper_data_quality_audit_label"]).value,
                json.dumps(audit_payload.get("audit_issues", []), sort_keys=True),
                json.dumps(audit_payload.get("decision_audit", {}), sort_keys=True),
                json.dumps(audit_payload.get("entry_audit", {}), sort_keys=True),
                json.dumps(audit_payload.get("monitoring_audit", {}), sort_keys=True),
                json.dumps(audit_payload.get("exit_audit", {}), sort_keys=True),
                json.dumps(audit_payload.get("pnl_audit", {}), sort_keys=True),
                json.dumps(audit_payload.get("rule_compliance", {}), sort_keys=True),
                json.dumps(audit_payload.get("audit_report", {}), sort_keys=True),
            ),
        )
        return int(cursor.lastrowid)


def build_and_record_paper_audit(
    db_path_or_conn: str | Path | sqlite3.Connection,
    paper_position_id: int | None = None,
    paper_decision_id: int | None = None,
    target_time: str | None = None,
) -> tuple[int, dict[str, Any]]:
    evidence = collect_paper_audit_evidence(db_path_or_conn, paper_position_id, paper_decision_id, target_time)
    payload = build_audit_payload(evidence)
    audit_id = record_paper_audit_report(db_path_or_conn, payload)
    return audit_id, payload


def get_latest_paper_audit(
    db_path_or_conn: str | Path | sqlite3.Connection,
    paper_position_id: int | None = None,
    paper_decision_id: int | None = None,
) -> sqlite3.Row | None:
    clauses: list[str] = []
    params: list[Any] = []
    if paper_position_id is not None:
        clauses.append("paper_position_id = ?")
        params.append(paper_position_id)
    if paper_decision_id is not None:
        clauses.append("paper_decision_id = ?")
        params.append(paper_decision_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect(db_path_or_conn) as connection:
        return connection.execute(
            f"SELECT * FROM printer_paper_audit_reports {where} ORDER BY audit_at DESC, id DESC LIMIT 1",
            params,
        ).fetchone()


def get_paper_audits_for_position(db_path_or_conn: str | Path | sqlite3.Connection, paper_position_id: int) -> list[sqlite3.Row]:
    with connect(db_path_or_conn) as connection:
        return connection.execute(
            "SELECT * FROM printer_paper_audit_reports WHERE paper_position_id = ? ORDER BY audit_at ASC, id ASC",
            (paper_position_id,),
        ).fetchall()


def enqueue_paper_audit_job(
    db_path_or_conn: str | Path | sqlite3.Connection,
    paper_position_id: int | None = None,
    paper_decision_id: int | None = None,
    scheduled_for: datetime | None = None,
    reason: str | None = None,
) -> tuple[LockResult, int | None]:
    target_id = paper_position_id or paper_decision_id
    suffix = reason or "scheduled"
    return enqueue_job(
        db_path_or_conn,
        job_name=f"paper_audit_{target_id or 0}_{suffix}",
        job_kind=JobKind.OPEN_PAPER_TRADE_MONITOR,
        target_table="printer_paper_audit_reports",
        target_id=target_id,
        scheduled_for=scheduled_for or utc_now(),
    )

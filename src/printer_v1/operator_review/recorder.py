"""SQLite-backed operator review report recorder."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.operator_review.contracts import (
    OperatorAttentionLabel,
    OperatorReviewLabel,
    ReportFormatLabel,
    ReportScopeLabel,
    ReportStatusLabel,
)
from printer_v1.operator_review.evidence import (
    collect_db_state_evidence,
    collect_full_operator_review_evidence,
    collect_memory_evidence,
    collect_paper_audit_evidence,
    collect_paper_decision_evidence,
    collect_paper_position_evidence,
    collect_system_health_evidence,
    collect_token_snapshot_evidence,
)
from printer_v1.operator_review.exports import export_report_as_markdown_text, export_report_as_plain_text
from printer_v1.operator_review.reports import build_operator_report_payload
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


def evidence_for_scope(db_path_or_conn: str | Path | sqlite3.Connection, scope: ReportScopeLabel, token_id=None, pair_id=None, now=None) -> dict[str, Any]:
    if scope == ReportScopeLabel.REPORT_DB_STATE:
        return collect_db_state_evidence(db_path_or_conn, now=now)
    if scope == ReportScopeLabel.REPORT_TOKEN_SNAPSHOTS:
        return collect_token_snapshot_evidence(db_path_or_conn, token_id=token_id, pair_id=pair_id, now=now)
    if scope == ReportScopeLabel.REPORT_MEMORY:
        return collect_memory_evidence(db_path_or_conn, token_id=token_id, pair_id=pair_id, now=now)
    if scope == ReportScopeLabel.REPORT_PAPER_DECISIONS:
        return collect_paper_decision_evidence(db_path_or_conn, token_id=token_id, pair_id=pair_id, now=now)
    if scope == ReportScopeLabel.REPORT_PAPER_POSITIONS:
        return {
            "paper_decisions": collect_paper_decision_evidence(db_path_or_conn, token_id=token_id, pair_id=pair_id, now=now),
            "paper_positions": collect_paper_position_evidence(db_path_or_conn, token_id=token_id, pair_id=pair_id, now=now),
            "paper_audits": collect_paper_audit_evidence(db_path_or_conn, token_id=token_id, pair_id=pair_id, now=now),
        }
    if scope == ReportScopeLabel.REPORT_FULL_OPERATOR_REVIEW:
        return collect_full_operator_review_evidence(db_path_or_conn, token_id=token_id, pair_id=pair_id, now=now)
    return collect_system_health_evidence(db_path_or_conn, now=now)


def report_text_for_format(report_payload: Mapping[str, Any], report_format: ReportFormatLabel) -> str:
    if report_format == ReportFormatLabel.REPORT_FORMAT_MARKDOWN:
        return export_report_as_markdown_text(report_payload)
    if report_format == ReportFormatLabel.REPORT_FORMAT_TEXT:
        return export_report_as_plain_text(report_payload)
    return json.dumps(dict(report_payload), sort_keys=True, default=str)


def record_operator_review_report(db_path_or_conn: str | Path | sqlite3.Connection, report_payload: Mapping[str, Any]) -> int:
    with connect(db_path_or_conn) as connection:
        duplicate = connection.execute(
            """
            SELECT id
            FROM printer_operator_review_reports
            WHERE report_scope_label = ?
              AND COALESCE(token_id, -1) = COALESCE(?, -1)
              AND COALESCE(pair_id, -1) = COALESCE(?, -1)
              AND generated_at = ?
            LIMIT 1
            """,
            (
                report_payload["report_scope_label"],
                report_payload.get("token_id"),
                report_payload.get("pair_id"),
                report_payload["generated_at"],
            ),
        ).fetchone()
        if duplicate:
            return int(duplicate["id"])
        report_format = ReportFormatLabel(report_payload["report_format_label"])
        cursor = connection.execute(
            """
            INSERT INTO printer_operator_review_reports (
                report_scope_label, report_status_label, operator_review_label,
                report_format_label, generated_at, db_state_classification,
                token_id, pair_id, token_mint, pair_address, report_title,
                attention_labels_json, summary_payload_json, report_payload_json,
                report_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ReportScopeLabel(report_payload["report_scope_label"]).value,
                ReportStatusLabel(report_payload["report_status_label"]).value,
                OperatorReviewLabel(report_payload["operator_review_label"]).value,
                report_format.value,
                report_payload["generated_at"],
                report_payload.get("db_state_classification"),
                report_payload.get("token_id"),
                report_payload.get("pair_id"),
                report_payload.get("token_mint"),
                report_payload.get("pair_address"),
                report_payload["report_title"],
                json.dumps(report_payload.get("attention_labels", []), sort_keys=True),
                json.dumps(report_payload.get("summary", {}), sort_keys=True, default=str),
                json.dumps(dict(report_payload), sort_keys=True, default=str),
                report_text_for_format(report_payload, report_format),
            ),
        )
        return int(cursor.lastrowid)


def record_operator_review_items(db_path_or_conn: str | Path | sqlite3.Connection, operator_review_report_id: int, items: list[Mapping[str, Any]]) -> None:
    with connect(db_path_or_conn) as connection:
        for item in items:
            connection.execute(
                """
                INSERT INTO printer_operator_review_items (
                    operator_review_report_id, item_scope_label, operator_review_label,
                    attention_label, token_id, pair_id, related_table, related_row_id,
                    item_payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    operator_review_report_id,
                    ReportScopeLabel(item["item_scope_label"]).value,
                    OperatorReviewLabel(item["operator_review_label"]).value,
                    OperatorAttentionLabel(item["attention_label"]).value,
                    item.get("token_id"),
                    item.get("pair_id"),
                    item.get("related_table"),
                    item.get("related_row_id"),
                    json.dumps(item.get("item_payload", {}), sort_keys=True, default=str),
                ),
            )


def build_and_record_operator_review_report(
    db_path_or_conn: str | Path | sqlite3.Connection,
    report_scope_label: str | ReportScopeLabel,
    token_id: int | None = None,
    pair_id: int | None = None,
    report_format_label: str | ReportFormatLabel | None = None,
    now: datetime | None = None,
) -> tuple[int, dict[str, Any]]:
    scope = ReportScopeLabel(report_scope_label)
    evidence = evidence_for_scope(db_path_or_conn, scope, token_id, pair_id, now)
    payload = build_operator_report_payload(scope, evidence, now)
    payload["token_id"] = token_id
    payload["pair_id"] = pair_id
    if report_format_label is not None:
        payload["report_format_label"] = ReportFormatLabel(report_format_label).value
    report_id = record_operator_review_report(db_path_or_conn, payload)
    record_operator_review_items(db_path_or_conn, report_id, payload.get("items", []))
    return report_id, payload


def get_latest_operator_review_report(
    db_path_or_conn: str | Path | sqlite3.Connection,
    report_scope_label: str | ReportScopeLabel | None = None,
    token_id: int | None = None,
    pair_id: int | None = None,
) -> sqlite3.Row | None:
    clauses: list[str] = []
    params: list[Any] = []
    if report_scope_label is not None:
        clauses.append("report_scope_label = ?")
        params.append(ReportScopeLabel(report_scope_label).value)
    if token_id is not None:
        clauses.append("token_id = ?")
        params.append(token_id)
    if pair_id is not None:
        clauses.append("COALESCE(pair_id, -1) = COALESCE(?, -1)")
        params.append(pair_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect(db_path_or_conn) as connection:
        return connection.execute(
            f"SELECT * FROM printer_operator_review_reports {where} ORDER BY generated_at DESC, id DESC LIMIT 1",
            params,
        ).fetchone()


def get_operator_review_reports(
    db_path_or_conn: str | Path | sqlite3.Connection,
    report_scope_label: str | ReportScopeLabel | None = None,
    token_id: int | None = None,
    pair_id: int | None = None,
) -> list[sqlite3.Row]:
    clauses: list[str] = []
    params: list[Any] = []
    if report_scope_label is not None:
        clauses.append("report_scope_label = ?")
        params.append(ReportScopeLabel(report_scope_label).value)
    if token_id is not None:
        clauses.append("token_id = ?")
        params.append(token_id)
    if pair_id is not None:
        clauses.append("COALESCE(pair_id, -1) = COALESCE(?, -1)")
        params.append(pair_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect(db_path_or_conn) as connection:
        return connection.execute(
            f"SELECT * FROM printer_operator_review_reports {where} ORDER BY generated_at DESC, id DESC",
            params,
        ).fetchall()


def enqueue_operator_review_job(
    db_path_or_conn: str | Path | sqlite3.Connection,
    report_scope_label: str | ReportScopeLabel,
    scheduled_for: datetime,
    token_id: int | None = None,
    pair_id: int | None = None,
    reason: str | None = None,
) -> tuple[LockResult, int | None]:
    scope = ReportScopeLabel(report_scope_label)
    target_id = pair_id or token_id
    suffix = reason or "scheduled"
    return enqueue_job(
        db_path_or_conn,
        job_name=f"operator_review_{scope.value}_{target_id or 0}_{suffix}",
        job_kind=JobKind.BACKUP_SOURCE_CHECK,
        target_table="printer_operator_review_reports",
        target_id=target_id,
        scheduled_for=scheduled_for,
    )

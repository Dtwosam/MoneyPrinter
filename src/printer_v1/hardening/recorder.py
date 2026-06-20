"""SQLite recording helpers for Phase 20 validation runs."""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from typing import Any

from printer_v1.hardening.contracts import (
    SYNTHETIC_FLOW_STAGE_LABELS,
    VALIDATION_ISSUE_LABELS,
    VALIDATION_RESULT_LABELS,
    VALIDATION_SCOPE_LABELS,
    ValidationResultLabel,
)
from printer_v1.hardening.reports import build_validation_run_report


@contextmanager
def _connect(db_path_or_conn: str | Path | sqlite3.Connection):
    if isinstance(db_path_or_conn, sqlite3.Connection):
        yield db_path_or_conn
        return
    connection = sqlite3.connect(db_path_or_conn)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def _validate(value: str, allowed: set[str], field_name: str) -> None:
    if value not in allowed:
        raise ValueError(f"Invalid {field_name}: {value}")


def record_validation_run(db_path_or_conn: str | Path | sqlite3.Connection, validation_payload: dict[str, Any]) -> int:
    scope = validation_payload.get("validation_scope_label")
    result = validation_payload.get("validation_result_label", ValidationResultLabel.VALIDATION_UNKNOWN.value)
    _validate(scope, VALIDATION_SCOPE_LABELS, "validation_scope_label")
    _validate(result, VALIDATION_RESULT_LABELS, "validation_result_label")
    started_at = validation_payload.get("started_at")
    if not started_at:
        raise ValueError("started_at is required")
    report = validation_payload.get("report") or build_validation_run_report(validation_payload)
    summary = validation_payload.get("summary") or report.get("summary", {})
    with _connect(db_path_or_conn) as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO printer_validation_runs (
                validation_scope_label,
                validation_result_label,
                started_at,
                completed_at,
                synthetic_only,
                temp_db_only,
                project_db_created,
                validation_summary_json,
                validation_report_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scope,
                result,
                started_at,
                validation_payload.get("completed_at"),
                1 if validation_payload.get("synthetic_only", True) else 0,
                1 if validation_payload.get("temp_db_only", True) else 0,
                1 if validation_payload.get("project_db_created", False) else 0,
                json.dumps(summary, sort_keys=True),
                json.dumps(report, sort_keys=True),
            ),
        )
        if cursor.lastrowid:
            return int(cursor.lastrowid)
        row = connection.execute(
            """
            SELECT id FROM printer_validation_runs
            WHERE validation_scope_label = ? AND started_at = ?
            ORDER BY id DESC LIMIT 1
            """,
            (scope, started_at),
        ).fetchone()
        return int(row["id"])


def record_validation_items(
    db_path_or_conn: str | Path | sqlite3.Connection,
    validation_run_id: int,
    validation_items: list[dict[str, Any]],
) -> list[int]:
    item_ids: list[int] = []
    with _connect(db_path_or_conn) as connection:
        for item in validation_items:
            scope = item.get("validation_scope_label")
            result = item.get("validation_result_label")
            issue = item.get("validation_issue_label")
            stage = item.get("flow_stage_label")
            _validate(scope, VALIDATION_SCOPE_LABELS, "validation_scope_label")
            _validate(result, VALIDATION_RESULT_LABELS, "validation_result_label")
            _validate(issue, VALIDATION_ISSUE_LABELS, "validation_issue_label")
            _validate(stage, SYNTHETIC_FLOW_STAGE_LABELS, "flow_stage_label")
            cursor = connection.execute(
                """
                INSERT INTO printer_validation_items (
                    validation_run_id,
                    validation_scope_label,
                    validation_result_label,
                    validation_issue_label,
                    flow_stage_label,
                    related_table,
                    related_row_id,
                    item_payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    validation_run_id,
                    scope,
                    result,
                    issue,
                    stage,
                    item.get("related_table"),
                    item.get("related_row_id"),
                    json.dumps(item.get("item_payload", {}), sort_keys=True),
                ),
            )
            item_ids.append(int(cursor.lastrowid))
    return item_ids


def build_and_record_validation_report(
    db_path_or_conn: str | Path | sqlite3.Connection,
    validation_scope_label: str,
    validation_payload: dict[str, Any],
    now: str | None = None,
) -> int:
    payload = dict(validation_payload)
    payload["validation_scope_label"] = validation_scope_label
    payload.setdefault("started_at", now)
    payload.setdefault("validation_result_label", ValidationResultLabel.VALIDATION_PASS.value)
    if not payload.get("started_at"):
        raise ValueError("started_at is required")
    run_id = record_validation_run(db_path_or_conn, payload)
    record_validation_items(db_path_or_conn, run_id, payload.get("items", []))
    return run_id


def get_latest_validation_run(
    db_path_or_conn: str | Path | sqlite3.Connection,
    validation_scope_label: str | None = None,
) -> dict[str, Any] | None:
    with _connect(db_path_or_conn) as connection:
        if validation_scope_label:
            row = connection.execute(
                """
                SELECT * FROM printer_validation_runs
                WHERE validation_scope_label = ?
                ORDER BY started_at DESC, id DESC LIMIT 1
                """,
                (validation_scope_label,),
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT * FROM printer_validation_runs ORDER BY started_at DESC, id DESC LIMIT 1"
            ).fetchone()
    return dict(row) if row else None


def get_validation_items(
    db_path_or_conn: str | Path | sqlite3.Connection,
    validation_run_id: int,
) -> list[dict[str, Any]]:
    with _connect(db_path_or_conn) as connection:
        rows = connection.execute(
            "SELECT * FROM printer_validation_items WHERE validation_run_id = ? ORDER BY id ASC",
            (validation_run_id,),
        ).fetchall()
    return [dict(row) for row in rows]

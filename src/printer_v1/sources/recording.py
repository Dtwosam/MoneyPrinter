"""SQLite recording helpers for governed source evidence."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.sources.contracts import (
    NormalizedSourceResult,
    SourceFailureRecord,
    SourceRequest,
    SourceRequestRecord,
    SourceResponseRecord,
    utc_now_iso,
)
from printer_v1.sources.governor import SourceRequestDecision


@contextmanager
def writable_connection(db_path_or_conn: str | Path | sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    if isinstance(db_path_or_conn, sqlite3.Connection):
        db_path_or_conn.row_factory = sqlite3.Row
        yield db_path_or_conn
        return

    connection = sqlite3.connect(Path(db_path_or_conn))
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def json_payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def record_source_request(
    db_path_or_conn: str | Path | sqlite3.Connection,
    source_request: SourceRequest,
    decision: SourceRequestDecision | None = None,
) -> SourceRequestRecord:
    source_status = decision.source_status if decision else SourceStatus.COMPLETE
    data_quality = decision.data_quality_label if decision else DataQualityLabel.CLEAN_DATA
    with writable_connection(db_path_or_conn) as connection:
        cursor = connection.execute(
            """
            INSERT INTO printer_source_requests (
                source_name,
                request_kind,
                requested_at,
                request_key,
                tracking_priority,
                source_status,
                data_quality_label
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_request.source_name,
                source_request.request_kind,
                source_request.requested_at,
                source_request.request_key,
                source_request.tracking_priority,
                source_status.value,
                data_quality.value,
            ),
        )
        row_id = int(cursor.lastrowid)
    return SourceRequestRecord(
        id=row_id,
        source_name=source_request.source_name,
        request_kind=source_request.request_kind,
        requested_at=source_request.requested_at,
        request_key=source_request.request_key,
        tracking_priority=source_request.tracking_priority,
        source_status=source_status,
        data_quality_label=data_quality,
    )


def record_source_response(
    db_path_or_conn: str | Path | sqlite3.Connection,
    request_record: SourceRequestRecord,
    normalized_result: NormalizedSourceResult,
) -> SourceResponseRecord:
    payload = dict(normalized_result.normalized_payload or {})
    payload_hash = json_payload_hash(payload)
    with writable_connection(db_path_or_conn) as connection:
        cursor = connection.execute(
            """
            INSERT INTO printer_source_responses (
                source_request_id,
                source_name,
                received_at,
                status_code,
                source_status,
                data_quality_label,
                response_hash,
                normalized_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_record.id,
                normalized_result.source_name,
                normalized_result.received_at,
                normalized_result.status_code,
                normalized_result.source_status.value,
                normalized_result.data_quality_label.value,
                payload_hash,
                json.dumps(payload, sort_keys=True),
            ),
        )
        row_id = int(cursor.lastrowid)
    return SourceResponseRecord(
        id=row_id,
        source_request_id=request_record.id,
        source_name=normalized_result.source_name,
        received_at=normalized_result.received_at,
        status_code=normalized_result.status_code,
        source_status=normalized_result.source_status,
        data_quality_label=normalized_result.data_quality_label,
        response_hash=payload_hash,
        normalized_payload=payload,
    )


def record_source_failure(
    db_path_or_conn: str | Path | sqlite3.Connection,
    source_request: SourceRequest | SourceRequestRecord,
    *,
    failure_type: str,
    failure_message: str | None = None,
    source_status: SourceStatus = SourceStatus.FAILED,
    data_quality_label: DataQualityLabel = DataQualityLabel.MISSING_CRITICAL_DATA,
    failed_at: str | None = None,
    retry_after_at: str | None = None,
    normalized_payload: Mapping[str, Any] | None = None,
) -> SourceFailureRecord:
    failure_time = failed_at or utc_now_iso()
    payload = dict(normalized_payload or {})
    source_request_id = (
        int(source_request.id) if isinstance(source_request, SourceRequestRecord) else None
    )
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":")) if payload else None
    with writable_connection(db_path_or_conn) as connection:
        cursor = connection.execute(
            """
            INSERT INTO printer_source_failures (
                source_request_id,
                source_name,
                request_kind,
                failed_at,
                failure_type,
                failure_message,
                source_status,
                data_quality_label,
                retry_after_at,
                normalized_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_request_id,
                source_request.source_name,
                source_request.request_kind,
                failure_time,
                failure_type,
                failure_message,
                source_status.value,
                data_quality_label.value,
                retry_after_at,
                payload_json,
            ),
        )
        row_id = int(cursor.lastrowid)
    return SourceFailureRecord(
        id=row_id,
        source_name=source_request.source_name,
        request_kind=source_request.request_kind,
        failed_at=failure_time,
        failure_type=failure_type,
        failure_message=failure_message,
        source_status=source_status,
        data_quality_label=data_quality_label,
        retry_after_at=retry_after_at,
        normalized_payload=payload,
        source_request_id=source_request_id,
    )

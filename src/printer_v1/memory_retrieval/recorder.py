"""SQLite-backed Memory Retrieval recorder."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.memory_retrieval.contracts import MemoryEvidenceLabel, RetrievalQueryTypeLabel, RetrievalResultLabel
from printer_v1.memory_retrieval.fingerprint_builder import build_current_setup_fingerprint
from printer_v1.memory_retrieval.query import normalize_retrieval_query_payload
from printer_v1.memory_retrieval.reports import build_memory_comparison_report
from printer_v1.memory_retrieval.retriever import (
    build_memory_evidence_label,
    build_retrieval_result_label,
    retrieve_memory_matches_for_current_setup,
)
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


def record_memory_retrieval_query(
    db_path_or_conn: str | Path | sqlite3.Connection,
    query_payload: Mapping[str, Any],
    result_payload: Mapping[str, Any],
) -> int:
    query = normalize_retrieval_query_payload(query_payload)
    fingerprint = result_payload.get("current_fingerprint") or build_current_setup_fingerprint(query)
    with connect(db_path_or_conn) as connection:
        cursor = connection.execute(
            """
            INSERT INTO printer_memory_retrieval_queries (
                query_type, token_id, pair_id, token_mint, pair_address, query_at,
                current_fingerprint_json, query_context_json, retrieval_result_label,
                memory_evidence_label, data_quality_label, source_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                RetrievalQueryTypeLabel(query["query_type"]).value,
                query.get("token_id"),
                query.get("pair_id"),
                query.get("token_mint"),
                query.get("pair_address"),
                query.get("query_at") or utc_now().isoformat(),
                json.dumps(fingerprint, sort_keys=True),
                json.dumps(query.get("context", {}), sort_keys=True),
                RetrievalResultLabel(result_payload["retrieval_result_label"]).value,
                MemoryEvidenceLabel(result_payload["memory_evidence_label"]).value,
                DataQualityLabel(query["data_quality_label"]).value,
                SourceStatus(query["source_status"]).value,
            ),
        )
        return int(cursor.lastrowid)


def record_memory_retrieval_matches(db_path_or_conn: str | Path | sqlite3.Connection, retrieval_query_id: int, matches: list[Mapping[str, Any]]) -> None:
    with connect(db_path_or_conn) as connection:
        for match in matches:
            connection.execute(
                """
                INSERT INTO printer_memory_retrieval_matches (
                    retrieval_query_id, episode_id, memory_window_id, token_id, pair_id,
                    window_kind, outcome_label, action_lesson_label, memory_quality_label,
                    match_strength_label, match_reasons_json, mismatch_reasons_json,
                    memory_fingerprint_json, comparison_payload_json,
                    included_as_clean_evidence, included_as_audit_context
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    retrieval_query_id,
                    match.get("episode_id"),
                    match.get("memory_window_id"),
                    match.get("token_id"),
                    match.get("pair_id"),
                    match.get("window_kind"),
                    match.get("outcome_label"),
                    match.get("action_lesson_label"),
                    match.get("memory_quality_label"),
                    match.get("match_strength_label"),
                    json.dumps(match.get("match_reasons", []), sort_keys=True),
                    json.dumps(match.get("mismatch_reasons", []), sort_keys=True),
                    json.dumps(match.get("memory_fingerprint", {}), sort_keys=True),
                    json.dumps(match.get("comparison_payload", {}), sort_keys=True),
                    1 if match.get("included_as_clean_evidence") else 0,
                    1 if match.get("included_as_audit_context") else 0,
                ),
            )


def build_and_record_memory_retrieval_report(
    db_path_or_conn: str | Path | sqlite3.Connection,
    query_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> tuple[int, dict[str, Any]]:
    del now
    matches = retrieve_memory_matches_for_current_setup(db_path_or_conn, query_payload)
    result = {
        "current_fingerprint": build_current_setup_fingerprint(query_payload),
        "retrieval_result_label": build_retrieval_result_label(matches).value,
        "memory_evidence_label": build_memory_evidence_label(matches).value,
        "report": build_memory_comparison_report(query_payload, matches),
    }
    query_id = record_memory_retrieval_query(db_path_or_conn, query_payload, result)
    record_memory_retrieval_matches(db_path_or_conn, query_id, matches)
    return query_id, result


def enqueue_memory_retrieval_job(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    scheduled_for: datetime,
    reason: str | None = None,
) -> tuple[LockResult, int | None]:
    suffix = reason or "scheduled"
    return enqueue_job(
        db_path_or_conn,
        job_name=f"memory_retrieval_{token_id}_{pair_id or 0}_{suffix}",
        job_kind=JobKind.MEMORY_WINDOW_CLOSE,
        target_table="printer_memory_retrieval_queries",
        target_id=token_id,
        scheduled_for=scheduled_for,
    )

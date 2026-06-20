"""Local evidence collection for paper-only decision records."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.memory_retrieval.contracts import MemoryEvidenceLabel, RetrievalResultLabel
from printer_v1.memory_retrieval.fingerprint_builder import build_current_setup_fingerprint_from_db


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


def latest_row(
    connection: sqlite3.Connection,
    table: str,
    token_id: int,
    pair_id: int | None,
    time_field: str = "captured_at",
) -> dict[str, Any]:
    row = connection.execute(
        f"""
        SELECT *
        FROM {table}
        WHERE token_id = ?
          AND COALESCE(pair_id, -1) = COALESCE(?, -1)
        ORDER BY {time_field} DESC, id DESC
        LIMIT 1
        """,
        (token_id, pair_id),
    ).fetchone()
    return dict(row) if row else {}


def collect_latest_current_context(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    target_time: str | None = None,
) -> dict[str, Any]:
    del target_time
    context = build_current_setup_fingerprint_from_db(db_path_or_conn, token_id, pair_id)
    with connect(db_path_or_conn) as connection:
        for table, time_field in (
            ("printer_safety_rug_snapshots", "captured_at"),
            ("printer_liquidity_exit_snapshots", "captured_at"),
            ("printer_trading_flow_snapshots", "captured_at"),
            ("printer_chart_volatility_snapshots", "captured_at"),
            ("printer_micro_events", "detected_at"),
        ):
            context.update(latest_row(connection, table, token_id, pair_id, time_field))
    context["source_status"] = context.get("source_status") or SourceStatus.COMPLETE.value
    context["data_quality_label"] = context.get("data_quality_label") or DataQualityLabel.CLEAN_DATA.value
    return context


def collect_memory_retrieval_evidence(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    target_time: str | None = None,
) -> dict[str, Any]:
    del target_time
    with connect(db_path_or_conn) as connection:
        query = connection.execute(
            """
            SELECT *
            FROM printer_memory_retrieval_queries
            WHERE token_id = ?
              AND COALESCE(pair_id, -1) = COALESCE(?, -1)
            ORDER BY query_at DESC, id DESC
            LIMIT 1
            """,
            (token_id, pair_id),
        ).fetchone()
        if query is None:
            return {
                "retrieval_query": None,
                "matches": [],
                "clean_matches": [],
                "audit_matches": [],
            }
        matches = [
            dict(row)
            for row in connection.execute(
                """
                SELECT *
                FROM printer_memory_retrieval_matches
                WHERE retrieval_query_id = ?
                ORDER BY included_as_clean_evidence DESC, created_at DESC, id DESC
                """,
                (query["id"],),
            ).fetchall()
        ]
    return {
        "retrieval_query": dict(query),
        "matches": matches,
        "clean_matches": [match for match in matches if int(match.get("included_as_clean_evidence") or 0) == 1],
        "audit_matches": [match for match in matches if int(match.get("included_as_audit_context") or 0) == 1],
    }


def evidence_has_clean_memory_comparison(evidence: Mapping[str, Any]) -> bool:
    retrieval = evidence.get("memory_retrieval") or {}
    query = retrieval.get("retrieval_query") or {}
    return (
        query.get("retrieval_result_label") == RetrievalResultLabel.RETRIEVAL_HAS_CLEAN_MATCHES.value
        and query.get("memory_evidence_label") != MemoryEvidenceLabel.MEMORY_EVIDENCE_NOT_ENOUGH.value
        and bool(retrieval.get("clean_matches"))
    )


def evidence_has_blocking_context(evidence: Mapping[str, Any]) -> bool:
    context = evidence.get("current_context") or {}
    blocked_values = {
        "SAFETY_UNSAFE",
        "SAFETY_DO_NOT_USE_FOR_MEMORY",
        "EXIT_UNREALISTIC",
        "EXIT_BLOCKED_BY_ROUTE",
        "REALISM_CONTEXT_BLOCKED",
        "REALISM_CONTEXT_DO_NOT_TRAIN",
        "ROUTE_NOT_AVAILABLE",
        "ROUTE_FAILED",
        SourceStatus.FAILED.value,
        SourceStatus.STALE.value,
        SourceStatus.CONFLICTING.value,
        DataQualityLabel.DIRTY_DATA.value,
        DataQualityLabel.STALE_DATA.value,
        DataQualityLabel.MISSING_CRITICAL_DATA.value,
        DataQualityLabel.CONFLICTING_DATA.value,
        DataQualityLabel.DO_NOT_TRAIN.value,
    }
    return any(value in blocked_values for value in context.values())


def normalize_decision_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(evidence)
    retrieval = dict(normalized.get("memory_retrieval") or {})
    retrieval["clean_match_count"] = len(retrieval.get("clean_matches") or [])
    retrieval["audit_match_count"] = len(retrieval.get("audit_matches") or [])
    normalized["memory_retrieval"] = retrieval
    normalized["has_clean_memory_comparison"] = evidence_has_clean_memory_comparison(normalized)
    normalized["has_blocking_context"] = evidence_has_blocking_context(normalized)
    return normalized


def collect_paper_decision_evidence(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    target_time: str | None = None,
) -> dict[str, Any]:
    return normalize_decision_evidence(
        {
            "token_id": token_id,
            "pair_id": pair_id,
            "target_time": target_time,
            "current_context": collect_latest_current_context(db_path_or_conn, token_id, pair_id, target_time),
            "memory_retrieval": collect_memory_retrieval_evidence(db_path_or_conn, token_id, pair_id, target_time),
        }
    )


def safe_json_loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    loaded = json.loads(value)
    return loaded if isinstance(loaded, dict) else {"value": loaded}

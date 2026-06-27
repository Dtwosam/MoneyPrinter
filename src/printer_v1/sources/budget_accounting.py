"""Read-only source request budget accounting for Printer V1.

Provides count_recent_source_requests so callers can supply an accurate
recent_request_count to can_request_source (Source Governor) without
bypassing Source Governor or making network calls.

The count represents consumed source/provider attempts, not every
printer_source_requests row. Pure governor rejections that never reached
the adapter/provider must not increase the rate-limit count.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3


DEFAULT_WINDOW_SECONDS: int = 60

_PRE_ADAPTER_FAILURE_TYPES = {
    "governor_rejection",
    "governor_rejected",
    "rate_limit_exceeded",
    "paid_dependency_rejected",
    "unknown_source",
    "request_kind_not_allowed",
    "not_solana_token_level_source",
    "jupiter_quote_paper_only",
    "test_fixture",
}

_TIME_COLUMNS = (
    "requested_at",
    "recorded_at",
    "failed_at",
    "created_at",
    "updated_at",
)


@contextmanager
def _read_connection(db: str | Path | sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    if isinstance(db, sqlite3.Connection):
        yield db
        return
    conn = sqlite3.connect(Path(db))
    try:
        yield conn
    finally:
        conn.close()


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _first_existing(columns: set[str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _request_link_column(conn: sqlite3.Connection, table: str) -> str | None:
    columns = _table_columns(conn, table)
    return _first_existing(
        columns,
        (
            "source_request_id",
            "request_id",
            "request_record_id",
            "source_request_record_id",
        ),
    )


def _count_response_attempts(
    conn: sqlite3.Connection,
    source_name: str,
    cutoff: str,
) -> int:
    response_request_col = _request_link_column(conn, "printer_source_responses")
    if response_request_col is None:
        return 0

    row = conn.execute(
        "SELECT COUNT(DISTINCT r.id)"
        " FROM printer_source_requests r"
        " WHERE r.source_name = ?"
        " AND r.requested_at >= ?"
        f" AND EXISTS (SELECT 1 FROM printer_source_responses resp WHERE resp.{response_request_col} = r.id)",
        (source_name, cutoff),
    ).fetchone()
    return int(row[0])


def _failure_filter_sql(conn: sqlite3.Connection) -> tuple[str, tuple[str, ...]]:
    failure_columns = _table_columns(conn, "printer_source_failures")
    if "failure_type" not in failure_columns:
        return "", ()
    placeholders = ", ".join("?" for _ in _PRE_ADAPTER_FAILURE_TYPES)
    return (
        f" AND lower(coalesce(f.failure_type, '')) NOT IN ({placeholders})",
        tuple(_PRE_ADAPTER_FAILURE_TYPES),
    )


def _count_failure_attempts(
    conn: sqlite3.Connection,
    source_name: str,
    cutoff: str,
) -> int:
    failure_columns = _table_columns(conn, "printer_source_failures")
    failure_request_col = _request_link_column(conn, "printer_source_failures")
    failure_filter, failure_params = _failure_filter_sql(conn)

    if failure_request_col is not None:
        row = conn.execute(
            "SELECT COUNT(DISTINCT r.id)"
            " FROM printer_source_requests r"
            " WHERE r.source_name = ?"
            " AND r.requested_at >= ?"
            f" AND EXISTS (SELECT 1 FROM printer_source_failures f WHERE f.{failure_request_col} = r.id{failure_filter})",
            (source_name, cutoff, *failure_params),
        ).fetchone()
        return int(row[0])

    source_col = _first_existing(failure_columns, ("source_name", "source"))
    time_col = _first_existing(failure_columns, _TIME_COLUMNS)

    if source_col is None or time_col is None:
        return 0

    row = conn.execute(
        "SELECT COUNT(*)"
        " FROM printer_source_failures f"
        f" WHERE f.{source_col} = ?"
        f" AND f.{time_col} >= ?"
        f"{failure_filter}",
        (source_name, cutoff, *failure_params),
    ).fetchone()
    return int(row[0])


def count_recent_source_requests(
    db: str | Path | sqlite3.Connection,
    source_name: str,
    *,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
    now: datetime | None = None,
) -> int:
    """Count consumed source/provider attempts for *source_name* within the window.

    Counted:
    - requests with a recorded source response
    - source/adapter/network failures when the schema can attribute them to the source

    Not counted:
    - pure request rows without response/failure evidence
    - pure governor rejections that never reached the adapter/provider

    Read-only. Never mutates the database.
    """
    current_time = now or datetime.now(timezone.utc)
    cutoff = (current_time - timedelta(seconds=window_seconds)).isoformat()

    with _read_connection(db) as conn:
        return _count_response_attempts(conn, source_name, cutoff) + _count_failure_attempts(
            conn,
            source_name,
            cutoff,
        )
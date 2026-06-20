"""Memory window helpers for completed Printer V1 tracking windows."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from typing import Any

from printer_v1.contracts.enums import DataQualityLabel
from printer_v1.memory.contracts import MemoryQualityLabel, MemoryWindowKind, MemoryWindowStatus


WINDOW_DURATIONS = {
    MemoryWindowKind.WINDOW_15M: 15 * 60,
    MemoryWindowKind.WINDOW_1H: 60 * 60,
    MemoryWindowKind.WINDOW_4H: 4 * 60 * 60,
    MemoryWindowKind.WINDOW_12H: 12 * 60 * 60,
    MemoryWindowKind.WINDOW_24H: 24 * 60 * 60,
}


def parse_timestamp(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def to_timestamp(value: datetime | str) -> str:
    return parse_timestamp(value).isoformat()


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


def validate_memory_window_kind(window_kind: str | MemoryWindowKind) -> MemoryWindowKind:
    return MemoryWindowKind(window_kind)


def get_window_duration_seconds(window_kind: str | MemoryWindowKind) -> int:
    return WINDOW_DURATIONS[validate_memory_window_kind(window_kind)]


def memory_window_is_complete(opened_at: datetime | str, closed_at: datetime | str, window_kind: str | MemoryWindowKind) -> bool:
    return (parse_timestamp(closed_at) - parse_timestamp(opened_at)).total_seconds() >= get_window_duration_seconds(window_kind)


def memory_window_can_close(opened_at: datetime | str, now: datetime, window_kind: str | MemoryWindowKind) -> bool:
    return memory_window_is_complete(opened_at, now, window_kind)


def open_memory_window(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    window_kind: str | MemoryWindowKind,
    opened_at: datetime,
    tracking_lane: str,
    reason: str | None = None,
) -> int:
    kind = validate_memory_window_kind(window_kind)
    with connect(db_path_or_conn) as connection:
        cursor = connection.execute(
            """
            INSERT INTO printer_memory_windows (
                token_id, pair_id, window_kind, opened_at, memory_status,
                data_quality_label, window_status, memory_quality_label,
                supporting_context_json, created_by_phase
            )
            VALUES (?, ?, ?, ?, 'PARTIAL_MEMORY', ?, ?, ?, ?, 'phase14')
            """,
            (
                token_id,
                pair_id,
                kind.value,
                to_timestamp(opened_at),
                DataQualityLabel.CLEAN_DATA.value,
                MemoryWindowStatus.WINDOW_OPEN.value,
                MemoryQualityLabel.PARTIAL_MEMORY.value,
                f'{{"tracking_lane":"{tracking_lane}","reason":"{reason or ""}"}}',
            ),
        )
        return int(cursor.lastrowid)


def close_memory_window(db_path_or_conn: str | Path | sqlite3.Connection, memory_window_id: int, closed_at: datetime) -> None:
    with connect(db_path_or_conn) as connection:
        connection.execute(
            """
            UPDATE printer_memory_windows
            SET closed_at = ?, window_status = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (to_timestamp(closed_at), MemoryWindowStatus.WINDOW_CLOSING.value, memory_window_id),
        )


def get_due_memory_windows(db_path_or_conn: str | Path | sqlite3.Connection, now: datetime | None = None) -> list[sqlite3.Row]:
    current_time = now or datetime.now(timezone.utc)
    with connect(db_path_or_conn) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM printer_memory_windows
            WHERE closed_at IS NULL
              AND COALESCE(window_status, 'WINDOW_OPEN') IN ('WINDOW_OPEN', 'WINDOW_CLOSING')
            ORDER BY opened_at ASC, id ASC
            """
        ).fetchall()
    return [
        row for row in rows
        if memory_window_can_close(row["opened_at"], current_time, row["window_kind"])
    ]

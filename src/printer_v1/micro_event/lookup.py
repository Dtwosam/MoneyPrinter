"""Micro-Event lookup helpers for future episode support evidence."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.micro_event.contracts import (
    MicroEventMemoryGateLabel,
    MicroEventPayloadQualityLabel,
    MicroEventStateLabel,
    MicroExitRealismLabel,
)


DEFAULT_MAX_AGE_SECONDS = 30 * 60


def parse_timestamp(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


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


def micro_event_blocks_clean_micro_profit(event: sqlite3.Row | dict | None) -> bool:
    if event is None:
        return False
    return (
        MicroEventStateLabel(event["micro_event_state_label"])
        in {MicroEventStateLabel.UNTRADABLE_MICRO_PUMP, MicroEventStateLabel.FAKE_PUMP_NO_EXIT, MicroEventStateLabel.WICK_ONLY_PUMP}
        or MicroExitRealismLabel(event["micro_exit_realism_label"])
        in {MicroExitRealismLabel.MICRO_EXIT_NO_EXIT, MicroExitRealismLabel.MICRO_EXIT_UNREALISTIC}
    )


def micro_event_is_valid_support_evidence(
    event: sqlite3.Row | dict | None,
    target_time: datetime | None = None,
    max_age_seconds: int | None = None,
) -> bool:
    if event is None or micro_event_blocks_clean_micro_profit(event):
        return False
    if SourceStatus(event["source_status"]) != SourceStatus.COMPLETE:
        return False
    if DataQualityLabel(event["data_quality_label"]) != DataQualityLabel.CLEAN_DATA:
        return False
    if MicroEventPayloadQualityLabel(event["micro_event_payload_quality_label"]) != MicroEventPayloadQualityLabel.MICRO_EVENT_CONTEXT_CLEAN:
        return False
    if MicroEventMemoryGateLabel(event["micro_event_memory_gate_label"]) != MicroEventMemoryGateLabel.MICRO_EVENT_SUPPORT_EVIDENCE:
        return False
    if target_time is None:
        return True
    detected_at = parse_timestamp(event["detected_at"])
    return abs((target_time - detected_at).total_seconds()) <= (max_age_seconds or DEFAULT_MAX_AGE_SECONDS)


def find_latest_micro_event(
    db_path_or_conn: str | Path | sqlite3.Connection,
    *,
    token_id: int | None = None,
    pair_id: int | None = None,
) -> sqlite3.Row | None:
    clauses = []
    params: list[int] = []
    if token_id is not None:
        clauses.append("token_id = ?")
        params.append(token_id)
    if pair_id is not None:
        clauses.append("pair_id = ?")
        params.append(pair_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect(db_path_or_conn) as connection:
        return connection.execute(
            f"SELECT * FROM printer_micro_events {where} ORDER BY detected_at DESC, id DESC LIMIT 1",
            params,
        ).fetchone()


def find_micro_events_for_window(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    opened_at: datetime,
    closed_at: datetime,
) -> list[sqlite3.Row]:
    with connect(db_path_or_conn) as connection:
        return connection.execute(
            """
            SELECT * FROM printer_micro_events
            WHERE token_id = ?
              AND COALESCE(pair_id, -1) = COALESCE(?, -1)
              AND detected_at >= ?
              AND detected_at <= ?
            ORDER BY detected_at ASC, id ASC
            """,
            (token_id, pair_id, to_timestamp(opened_at), to_timestamp(closed_at)),
        ).fetchall()


def find_nearest_micro_event(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    target_time: datetime,
    max_age_seconds: int | None = None,
) -> sqlite3.Row | None:
    with connect(db_path_or_conn) as connection:
        rows = connection.execute(
            """
            SELECT * FROM printer_micro_events
            WHERE token_id = ?
              AND COALESCE(pair_id, -1) = COALESCE(?, -1)
            ORDER BY detected_at ASC, id ASC
            """,
            (token_id, pair_id),
        ).fetchall()
    valid = [
        row
        for row in rows
        if micro_event_is_valid_support_evidence(row, target_time, max_age_seconds)
    ]
    if not valid:
        return None
    return min(valid, key=lambda row: abs((target_time - parse_timestamp(row["detected_at"])).total_seconds()))

"""Solana chain heat context lookup helpers."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from printer_v1.chain_heat.contracts import ChainHeatPayloadQualityLabel
from printer_v1.contracts.enums import DataQualityLabel, SourceStatus


DEFAULT_MAX_AGE_SECONDS = 3 * 60 * 60


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


def chain_heat_snapshot_is_valid_for_memory(
    snapshot: sqlite3.Row | dict | None,
    target_time: datetime,
    max_age_seconds: int | None = None,
) -> bool:
    if snapshot is None:
        return False
    if SourceStatus(snapshot["source_status"]) != SourceStatus.COMPLETE:
        return False
    if DataQualityLabel(snapshot["data_quality_label"]) != DataQualityLabel.CLEAN_DATA:
        return False
    if (
        ChainHeatPayloadQualityLabel(snapshot["chain_heat_payload_quality_label"])
        != ChainHeatPayloadQualityLabel.CHAIN_HEAT_CONTEXT_CLEAN
    ):
        return False
    captured_at = parse_timestamp(snapshot["captured_at"])
    max_age = max_age_seconds or DEFAULT_MAX_AGE_SECONDS
    return abs((target_time - captured_at).total_seconds()) <= max_age


def find_chain_heat_snapshot_before(
    db_path_or_conn: str | Path | sqlite3.Connection,
    target_time: datetime,
    max_age_seconds: int | None = None,
) -> sqlite3.Row | None:
    with connect(db_path_or_conn) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM printer_solana_chain_heat_snapshots
            WHERE captured_at <= ?
            ORDER BY captured_at DESC, id DESC
            """,
            (to_timestamp(target_time),),
        ).fetchall()
    for row in rows:
        if chain_heat_snapshot_is_valid_for_memory(row, target_time, max_age_seconds):
            return row
    return None


def find_chain_heat_snapshot_after(
    db_path_or_conn: str | Path | sqlite3.Connection,
    target_time: datetime,
    max_age_seconds: int | None = None,
) -> sqlite3.Row | None:
    with connect(db_path_or_conn) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM printer_solana_chain_heat_snapshots
            WHERE captured_at >= ?
            ORDER BY captured_at ASC, id ASC
            """,
            (to_timestamp(target_time),),
        ).fetchall()
    for row in rows:
        if chain_heat_snapshot_is_valid_for_memory(row, target_time, max_age_seconds):
            return row
    return None


def find_nearest_chain_heat_snapshot(
    db_path_or_conn: str | Path | sqlite3.Connection,
    target_time: datetime,
    max_age_seconds: int | None = None,
) -> sqlite3.Row | None:
    before = find_chain_heat_snapshot_before(db_path_or_conn, target_time, max_age_seconds)
    after = find_chain_heat_snapshot_after(db_path_or_conn, target_time, max_age_seconds)
    if before is None:
        return after
    if after is None:
        return before
    before_delta = abs((target_time - parse_timestamp(before["captured_at"])).total_seconds())
    after_delta = abs((parse_timestamp(after["captured_at"]) - target_time).total_seconds())
    return before if before_delta <= after_delta else after

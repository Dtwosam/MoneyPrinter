"""Trading Flow lookup helpers for future memory and audit use."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.trading_flow.contracts import (
    FlowDirectionLabel,
    FlowMemoryGateLabel,
    TradingFlowPayloadQualityLabel,
)


DEFAULT_MAX_AGE_SECONDS = 60 * 60


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


def trading_flow_snapshot_blocks_clean_memory(snapshot: sqlite3.Row | dict | None) -> bool:
    if snapshot is None:
        return False
    return (
        FlowMemoryGateLabel(snapshot["flow_memory_gate_label"])
        == FlowMemoryGateLabel.FLOW_CONTEXT_DO_NOT_TRAIN
        or FlowDirectionLabel(snapshot["flow_direction_label"]) == FlowDirectionLabel.FLOW_WASH_LIKE
    )


def trading_flow_snapshot_is_valid_for_memory(
    snapshot: sqlite3.Row | dict | None,
    target_time: datetime,
    max_age_seconds: int | None = None,
) -> bool:
    if snapshot is None or trading_flow_snapshot_blocks_clean_memory(snapshot):
        return False
    if SourceStatus(snapshot["source_status"]) != SourceStatus.COMPLETE:
        return False
    if DataQualityLabel(snapshot["data_quality_label"]) != DataQualityLabel.CLEAN_DATA:
        return False
    # V2-9.4.7: PARTIAL means optional context (split volume, wallet
    # participation) is unavailable, which no current adapter supplies. Treating
    # it as invalid made this lookup unable to return any real snapshot. Every
    # genuine fault -- stale, conflicting, do-not-train, wash-like -- is still
    # rejected above and below.
    if TradingFlowPayloadQualityLabel(snapshot["trading_flow_payload_quality_label"]) not in {
        TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CLEAN,
        TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_PARTIAL,
    }:
        return False
    captured_at = parse_timestamp(snapshot["captured_at"])
    max_age = max_age_seconds or DEFAULT_MAX_AGE_SECONDS
    return abs((target_time - captured_at).total_seconds()) <= max_age


def find_latest_trading_flow_snapshot(
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
            f"""
            SELECT *
            FROM printer_trading_flow_snapshots
            {where}
            ORDER BY captured_at DESC, id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()


def find_trading_flow_snapshot_before(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    target_time: datetime,
    max_age_seconds: int | None = None,
) -> sqlite3.Row | None:
    with connect(db_path_or_conn) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM printer_trading_flow_snapshots
            WHERE token_id = ?
              AND COALESCE(pair_id, -1) = COALESCE(?, -1)
              AND captured_at <= ?
            ORDER BY captured_at DESC, id DESC
            """,
            (token_id, pair_id, to_timestamp(target_time)),
        ).fetchall()
    for row in rows:
        if trading_flow_snapshot_is_valid_for_memory(row, target_time, max_age_seconds):
            return row
    return None


def find_nearest_trading_flow_snapshot(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    target_time: datetime,
    max_age_seconds: int | None = None,
) -> sqlite3.Row | None:
    before = find_trading_flow_snapshot_before(
        db_path_or_conn,
        token_id,
        pair_id,
        target_time,
        max_age_seconds,
    )
    with connect(db_path_or_conn) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM printer_trading_flow_snapshots
            WHERE token_id = ?
              AND COALESCE(pair_id, -1) = COALESCE(?, -1)
              AND captured_at >= ?
            ORDER BY captured_at ASC, id ASC
            """,
            (token_id, pair_id, to_timestamp(target_time)),
        ).fetchall()
    after = None
    for row in rows:
        if trading_flow_snapshot_is_valid_for_memory(row, target_time, max_age_seconds):
            after = row
            break
    if before is None:
        return after
    if after is None:
        return before
    before_delta = abs((target_time - parse_timestamp(before["captured_at"])).total_seconds())
    after_delta = abs((parse_timestamp(after["captured_at"]) - target_time).total_seconds())
    return before if before_delta <= after_delta else after

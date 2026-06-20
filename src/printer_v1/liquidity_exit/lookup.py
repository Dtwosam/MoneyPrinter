"""Liquidity + Exit lookup helpers for future memory and audit use."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.liquidity_exit.contracts import (
    ExitRealismLabel,
    LiquidityDrainLabel,
    LiquidityExitPayloadQualityLabel,
    RealismGateLabel,
)


DEFAULT_MAX_AGE_SECONDS = 2 * 60 * 60


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


def liquidity_exit_snapshot_blocks_clean_paper_profit(snapshot: sqlite3.Row | dict | None) -> bool:
    if snapshot is None:
        return False
    return (
        RealismGateLabel(snapshot["realism_gate_label"])
        in {
            RealismGateLabel.REALISM_CONTEXT_BLOCKED,
            RealismGateLabel.REALISM_CONTEXT_DO_NOT_TRAIN,
        }
        or ExitRealismLabel(snapshot["exit_realism_label"])
        in {ExitRealismLabel.EXIT_UNREALISTIC, ExitRealismLabel.EXIT_BLOCKED_BY_ROUTE}
        or LiquidityDrainLabel(snapshot["liquidity_drain_label"])
        == LiquidityDrainLabel.SEVERE_LIQUIDITY_DRAIN
    )


def liquidity_exit_snapshot_is_valid_for_memory(
    snapshot: sqlite3.Row | dict | None,
    target_time: datetime,
    max_age_seconds: int | None = None,
) -> bool:
    if snapshot is None or liquidity_exit_snapshot_blocks_clean_paper_profit(snapshot):
        return False
    if SourceStatus(snapshot["source_status"]) != SourceStatus.COMPLETE:
        return False
    if DataQualityLabel(snapshot["data_quality_label"]) != DataQualityLabel.CLEAN_DATA:
        return False
    if (
        LiquidityExitPayloadQualityLabel(snapshot["liquidity_exit_payload_quality_label"])
        != LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_CLEAN
    ):
        return False
    captured_at = parse_timestamp(snapshot["captured_at"])
    max_age = max_age_seconds or DEFAULT_MAX_AGE_SECONDS
    return abs((target_time - captured_at).total_seconds()) <= max_age


def find_latest_liquidity_exit_snapshot(
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
            FROM printer_liquidity_exit_snapshots
            {where}
            ORDER BY captured_at DESC, id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()


def find_liquidity_exit_snapshot_before(
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
            FROM printer_liquidity_exit_snapshots
            WHERE token_id = ?
              AND COALESCE(pair_id, -1) = COALESCE(?, -1)
              AND captured_at <= ?
            ORDER BY captured_at DESC, id DESC
            """,
            (token_id, pair_id, to_timestamp(target_time)),
        ).fetchall()
    for row in rows:
        if liquidity_exit_snapshot_is_valid_for_memory(row, target_time, max_age_seconds):
            return row
    return None


def find_nearest_liquidity_exit_snapshot(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    target_time: datetime,
    max_age_seconds: int | None = None,
) -> sqlite3.Row | None:
    before = find_liquidity_exit_snapshot_before(
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
            FROM printer_liquidity_exit_snapshots
            WHERE token_id = ?
              AND COALESCE(pair_id, -1) = COALESCE(?, -1)
              AND captured_at >= ?
            ORDER BY captured_at ASC, id ASC
            """,
            (token_id, pair_id, to_timestamp(target_time)),
        ).fetchall()
    after = None
    for row in rows:
        if liquidity_exit_snapshot_is_valid_for_memory(row, target_time, max_age_seconds):
            after = row
            break
    if before is None:
        return after
    if after is None:
        return before
    before_delta = abs((target_time - parse_timestamp(before["captured_at"])).total_seconds())
    after_delta = abs((parse_timestamp(after["captured_at"]) - target_time).total_seconds())
    return before if before_delta <= after_delta else after

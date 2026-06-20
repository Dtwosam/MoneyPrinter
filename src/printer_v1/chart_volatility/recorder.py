"""SQLite-backed Chart / Volatility snapshot recorder."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.chart_volatility.classifier import (
    classify_candle_path,
    classify_chart_memory_gate,
    classify_chart_payload_quality,
    classify_drawdown_recovery,
    classify_momentum,
    classify_range_behavior,
    classify_trend_structure,
    classify_volatility,
)
from printer_v1.chart_volatility.parser import (
    build_chart_payload_from_token_snapshots,
    normalize_chart_payload,
    to_timestamp,
)
from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import enqueue_job


INSERT_FIELDS = (
    "token_id",
    "pair_id",
    "token_mint",
    "pair_address",
    "captured_at",
    "window_start_at",
    "window_end_at",
    "price_open",
    "price_high",
    "price_low",
    "price_close",
    "price_change_percent",
    "max_runup_percent",
    "max_drawdown_percent",
    "recovery_from_low_percent",
    "high_to_close_fade_percent",
    "open_to_low_drop_percent",
    "volatility_percent",
    "candle_count",
    "green_candle_count",
    "red_candle_count",
    "flat_candle_count",
    "largest_green_candle_percent",
    "largest_red_candle_percent",
    "consecutive_green_candles",
    "consecutive_red_candles",
    "higher_high_count",
    "lower_low_count",
    "range_high",
    "range_low",
    "range_width_percent",
    "breakout_percent",
    "breakdown_percent",
    "round_trip_percent",
    "trend_structure_label",
    "volatility_label",
    "range_behavior_label",
    "momentum_label",
    "drawdown_recovery_label",
    "candle_path_label",
    "chart_payload_quality_label",
    "chart_memory_gate_label",
    "data_quality_label",
    "source_status",
    "raw_chart_payload_json",
    "normalized_chart_payload_json",
)


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


def resolve_token_pair_fields(connection: sqlite3.Connection, normalized: dict[str, Any]) -> None:
    if normalized.get("token_id") is None and normalized.get("token_mint"):
        row = connection.execute(
            "SELECT id FROM printer_tokens WHERE token_mint = ?",
            (normalized["token_mint"],),
        ).fetchone()
        if row:
            normalized["token_id"] = int(row["id"])
    if normalized.get("pair_id") is None and normalized.get("pair_address"):
        row = connection.execute(
            "SELECT id FROM printer_pairs WHERE pair_address = ?",
            (normalized["pair_address"],),
        ).fetchone()
        if row:
            normalized["pair_id"] = int(row["id"])
    if normalized.get("token_mint") is None and normalized.get("token_id") is not None:
        row = connection.execute(
            "SELECT token_mint FROM printer_tokens WHERE id = ?",
            (normalized["token_id"],),
        ).fetchone()
        if row:
            normalized["token_mint"] = row["token_mint"]
    if normalized.get("pair_address") is None and normalized.get("pair_id") is not None:
        row = connection.execute(
            "SELECT pair_address FROM printer_pairs WHERE id = ?",
            (normalized["pair_id"],),
        ).fetchone()
        if row:
            normalized["pair_address"] = row["pair_address"]


def existing_snapshot_id(
    connection: sqlite3.Connection,
    *,
    token_id: int | None,
    pair_id: int | None,
    token_mint: str | None,
    pair_address: str | None,
    window_start_at: str | None,
    window_end_at: str | None,
) -> int | None:
    row = connection.execute(
        """
        SELECT id
        FROM printer_chart_volatility_snapshots
        WHERE COALESCE(token_id, -1) = COALESCE(?, -1)
          AND COALESCE(pair_id, -1) = COALESCE(?, -1)
          AND COALESCE(token_mint, '') = COALESCE(?, '')
          AND COALESCE(pair_address, '') = COALESCE(?, '')
          AND COALESCE(window_start_at, '') = COALESCE(?, '')
          AND COALESCE(window_end_at, '') = COALESCE(?, '')
        LIMIT 1
        """,
        (token_id, pair_id, token_mint, pair_address, window_start_at, window_end_at),
    ).fetchone()
    return int(row["id"]) if row else None


def record_chart_volatility_snapshot(
    db_path_or_conn: str | Path | sqlite3.Connection,
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> tuple[bool, int]:
    current_time = now or utc_now()
    normalized = normalize_chart_payload(payload, current_time)
    normalized["captured_at"] = normalized.get("captured_at") or to_timestamp(current_time)
    normalized["source_status"] = SourceStatus(normalized["source_status"]).value
    normalized["data_quality_label"] = DataQualityLabel(normalized["data_quality_label"]).value
    normalized["trend_structure_label"] = classify_trend_structure(normalized).value
    normalized["volatility_label"] = classify_volatility(normalized).value
    normalized["range_behavior_label"] = classify_range_behavior(normalized).value
    normalized["momentum_label"] = classify_momentum(normalized).value
    normalized["drawdown_recovery_label"] = classify_drawdown_recovery(normalized).value
    normalized["candle_path_label"] = classify_candle_path(normalized).value
    normalized["chart_payload_quality_label"] = classify_chart_payload_quality(normalized, current_time).value
    normalized["chart_memory_gate_label"] = classify_chart_memory_gate(normalized, current_time).value

    with connect(db_path_or_conn) as connection:
        resolve_token_pair_fields(connection, normalized)
        duplicate_id = existing_snapshot_id(
            connection,
            token_id=normalized.get("token_id"),
            pair_id=normalized.get("pair_id"),
            token_mint=normalized.get("token_mint"),
            pair_address=normalized.get("pair_address"),
            window_start_at=normalized.get("window_start_at"),
            window_end_at=normalized.get("window_end_at"),
        )
        if duplicate_id is not None:
            return False, duplicate_id
        normalized["raw_chart_payload_json"] = json.dumps(dict(payload), sort_keys=True)
        normalized["normalized_chart_payload_json"] = json.dumps(normalized, sort_keys=True)
        placeholders = ", ".join("?" for _ in INSERT_FIELDS)
        columns = ", ".join(INSERT_FIELDS)
        cursor = connection.execute(
            f"INSERT INTO printer_chart_volatility_snapshots ({columns}) VALUES ({placeholders})",
            tuple(normalized.get(field) for field in INSERT_FIELDS),
        )
        return True, int(cursor.lastrowid)


def record_chart_volatility_from_source_response(
    db_path_or_conn: str | Path | sqlite3.Connection,
    source_response_id: int,
    now: datetime | None = None,
) -> tuple[bool, int]:
    with connect(db_path_or_conn) as connection:
        row = connection.execute(
            "SELECT * FROM printer_source_responses WHERE id = ?",
            (source_response_id,),
        ).fetchone()
    if row is None:
        raise ValueError(f"Source response not found: {source_response_id}")
    payload = json.loads(row["normalized_payload_json"] or "{}")
    if not isinstance(payload, dict):
        raise ValueError("Normalized source response payload must be an object")
    payload.setdefault("source_status", row["source_status"])
    payload.setdefault("data_quality_label", row["data_quality_label"])
    payload.setdefault("captured_at", row["received_at"])
    return record_chart_volatility_snapshot(db_path_or_conn, payload, now)


def record_chart_volatility_from_token_snapshots(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    opened_at: datetime,
    closed_at: datetime,
    now: datetime | None = None,
) -> tuple[bool, int]:
    with connect(db_path_or_conn) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM printer_token_snapshots
            WHERE token_id = ?
              AND COALESCE(pair_id, -1) = COALESCE(?, -1)
              AND captured_at >= ?
              AND captured_at <= ?
            ORDER BY captured_at ASC, id ASC
            """,
            (token_id, pair_id, to_timestamp(opened_at), to_timestamp(closed_at)),
        ).fetchall()
    payload = build_chart_payload_from_token_snapshots(rows, now)
    if not payload:
        raise ValueError("No usable token snapshots found for chart window")
    return record_chart_volatility_snapshot(db_path_or_conn, payload, now)


def get_latest_chart_volatility_snapshot(
    db_path_or_conn: str | Path | sqlite3.Connection,
    *,
    token_id: int | None = None,
    pair_id: int | None = None,
) -> sqlite3.Row | None:
    clauses = []
    params: list[Any] = []
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
            FROM printer_chart_volatility_snapshots
            {where}
            ORDER BY captured_at DESC, id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()


def enqueue_chart_volatility_refresh_job(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    scheduled_for: datetime,
    reason: str | None = None,
) -> tuple[LockResult, int | None]:
    suffix = reason or "scheduled"
    return enqueue_job(
        db_path_or_conn,
        job_name=f"chart_volatility_refresh_{token_id}_{pair_id or 0}_{suffix}",
        job_kind=JobKind.TRACK_FAST_FIRST_15M,
        target_table="printer_chart_volatility_snapshots",
        target_id=token_id,
        scheduled_for=scheduled_for,
    )

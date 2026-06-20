"""SQLite-backed Micro-Event recorder."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.micro_event.classifier import (
    classify_holding_to_15m_result,
    classify_late_buy_trap,
    classify_micro_event_memory_gate,
    classify_micro_event_move,
    classify_micro_event_payload_quality,
    classify_micro_event_state,
    classify_micro_exit_realism,
)
from printer_v1.micro_event.parser import build_micro_event_payload_from_token_snapshots, normalize_micro_event_payload, to_timestamp
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import enqueue_job


INSERT_FIELDS = (
    "token_id", "pair_id", "token_mint", "pair_address", "detected_at",
    "event_window_start_at", "event_window_end_at", "hold_check_15m_at",
    "price_start", "price_high", "price_low", "price_end",
    "price_change_5m_percent", "high_to_end_fade_percent",
    "max_drawdown_5m_percent", "wick_percent", "volume_5m",
    "volume_change_5m_percent", "txns_5m", "txns_change_5m_percent",
    "buys_5m", "sells_5m", "buy_volume_5m", "sell_volume_5m",
    "liquidity_start_usd", "liquidity_end_usd", "liquidity_change_5m_percent",
    "liquidity_exit_realism_label", "slippage_label", "price_impact_label",
    "route_label", "safety_status_label", "liquidity_state_label",
    "flow_direction_label", "candle_path_label", "micro_event_state_label",
    "micro_event_move_label", "micro_exit_realism_label", "late_buy_trap_label",
    "held_to_15m_result_label", "micro_event_payload_quality_label",
    "micro_event_memory_gate_label", "data_quality_label", "source_status",
    "raw_micro_event_payload_json", "normalized_micro_event_payload_json",
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
        row = connection.execute("SELECT id FROM printer_tokens WHERE token_mint = ?", (normalized["token_mint"],)).fetchone()
        if row:
            normalized["token_id"] = int(row["id"])
    if normalized.get("pair_id") is None and normalized.get("pair_address"):
        row = connection.execute("SELECT id FROM printer_pairs WHERE pair_address = ?", (normalized["pair_address"],)).fetchone()
        if row:
            normalized["pair_id"] = int(row["id"])
    if normalized.get("token_mint") is None and normalized.get("token_id") is not None:
        row = connection.execute("SELECT token_mint FROM printer_tokens WHERE id = ?", (normalized["token_id"],)).fetchone()
        if row:
            normalized["token_mint"] = row["token_mint"]
    if normalized.get("pair_address") is None and normalized.get("pair_id") is not None:
        row = connection.execute("SELECT pair_address FROM printer_pairs WHERE id = ?", (normalized["pair_id"],)).fetchone()
        if row:
            normalized["pair_address"] = row["pair_address"]


def existing_event_id(connection: sqlite3.Connection, normalized: Mapping[str, Any]) -> int | None:
    row = connection.execute(
        """
        SELECT id FROM printer_micro_events
        WHERE COALESCE(token_id, -1) = COALESCE(?, -1)
          AND COALESCE(pair_id, -1) = COALESCE(?, -1)
          AND COALESCE(event_window_start_at, '') = COALESCE(?, '')
          AND COALESCE(event_window_end_at, '') = COALESCE(?, '')
        LIMIT 1
        """,
        (
            normalized.get("token_id"),
            normalized.get("pair_id"),
            normalized.get("event_window_start_at"),
            normalized.get("event_window_end_at"),
        ),
    ).fetchone()
    return int(row["id"]) if row else None


def record_micro_event(
    db_path_or_conn: str | Path | sqlite3.Connection,
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> tuple[bool, int]:
    current_time = now or utc_now()
    normalized = normalize_micro_event_payload(payload, current_time)
    normalized["detected_at"] = normalized.get("detected_at") or to_timestamp(current_time)
    normalized["source_status"] = SourceStatus(normalized["source_status"]).value
    normalized["data_quality_label"] = DataQualityLabel(normalized["data_quality_label"]).value
    normalized["micro_event_move_label"] = classify_micro_event_move(normalized).value
    normalized["micro_exit_realism_label"] = classify_micro_exit_realism(normalized).value
    normalized["late_buy_trap_label"] = classify_late_buy_trap(normalized).value
    normalized["held_to_15m_result_label"] = classify_holding_to_15m_result(normalized).value
    normalized["micro_event_state_label"] = classify_micro_event_state(normalized).value
    normalized["micro_event_payload_quality_label"] = classify_micro_event_payload_quality(normalized, current_time).value
    normalized["micro_event_memory_gate_label"] = classify_micro_event_memory_gate(normalized, current_time).value
    with connect(db_path_or_conn) as connection:
        resolve_token_pair_fields(connection, normalized)
        duplicate_id = existing_event_id(connection, normalized)
        if duplicate_id is not None:
            return False, duplicate_id
        normalized["raw_micro_event_payload_json"] = json.dumps(dict(payload), sort_keys=True)
        normalized["normalized_micro_event_payload_json"] = json.dumps(normalized, sort_keys=True)
        columns = ", ".join(INSERT_FIELDS)
        placeholders = ", ".join("?" for _ in INSERT_FIELDS)
        cursor = connection.execute(
            f"INSERT INTO printer_micro_events ({columns}) VALUES ({placeholders})",
            tuple(normalized.get(field) for field in INSERT_FIELDS),
        )
        return True, int(cursor.lastrowid)


def record_micro_event_from_token_snapshots(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    event_window_start_at: datetime,
    event_window_end_at: datetime,
    now: datetime | None = None,
) -> tuple[bool, int]:
    with connect(db_path_or_conn) as connection:
        rows = connection.execute(
            """
            SELECT * FROM printer_token_snapshots
            WHERE token_id = ?
              AND COALESCE(pair_id, -1) = COALESCE(?, -1)
              AND captured_at >= ?
              AND captured_at <= ?
            ORDER BY captured_at ASC, id ASC
            """,
            (token_id, pair_id, to_timestamp(event_window_start_at), to_timestamp(event_window_end_at)),
        ).fetchall()
    payload = build_micro_event_payload_from_token_snapshots(rows, now)
    if not payload:
        raise ValueError("No usable token snapshots found for micro-event window")
    return record_micro_event(db_path_or_conn, payload, now)


def get_latest_micro_event(
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
            f"SELECT * FROM printer_micro_events {where} ORDER BY detected_at DESC, id DESC LIMIT 1",
            params,
        ).fetchone()


def enqueue_micro_event_refresh_job(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    scheduled_for: datetime,
    reason: str | None = None,
) -> tuple[LockResult, int | None]:
    suffix = reason or "scheduled"
    return enqueue_job(
        db_path_or_conn,
        job_name=f"micro_event_refresh_{token_id}_{pair_id or 0}_{suffix}",
        job_kind=JobKind.TRACK_FAST_MICRO_EVENT,
        target_table="printer_micro_events",
        target_id=token_id,
        scheduled_for=scheduled_for,
    )

"""SQLite-backed Liquidity + Exit snapshot recorder."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.liquidity_exit.classifier import (
    classify_entry_realism,
    classify_exit_realism,
    classify_liquidity_drain,
    classify_liquidity_exit_payload_quality,
    classify_liquidity_state,
    classify_price_impact,
    classify_quote_age,
    classify_realism_gate,
    classify_route_availability,
    classify_slippage,
)
from printer_v1.liquidity_exit.parser import normalize_liquidity_exit_payload, to_timestamp
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import enqueue_job


INSERT_FIELDS = (
    "token_id",
    "pair_id",
    "token_mint",
    "pair_address",
    "captured_at",
    "price_usd",
    "liquidity_usd",
    "volume_5m",
    "volume_15m",
    "volume_1h",
    "volume_24h",
    "txns_5m",
    "txns_15m",
    "txns_1h",
    "txns_24h",
    "expected_entry_size_usd",
    "expected_exit_size_usd",
    "estimated_entry_slippage_percent",
    "estimated_exit_slippage_percent",
    "estimated_entry_price_impact_percent",
    "estimated_exit_price_impact_percent",
    "route_available",
    "route_source",
    "quote_captured_at",
    "quote_age_seconds",
    "quote_status",
    "route_status",
    "liquidity_before_usd",
    "liquidity_after_usd",
    "liquidity_change_percent",
    "liquidity_state_label",
    "entry_realism_label",
    "exit_realism_label",
    "slippage_label",
    "price_impact_label",
    "route_label",
    "quote_age_label",
    "liquidity_drain_label",
    "liquidity_exit_payload_quality_label",
    "realism_gate_label",
    "data_quality_label",
    "source_status",
    "raw_liquidity_exit_payload_json",
    "normalized_liquidity_exit_payload_json",
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
    captured_at: str,
) -> int | None:
    row = connection.execute(
        """
        SELECT id
        FROM printer_liquidity_exit_snapshots
        WHERE COALESCE(token_id, -1) = COALESCE(?, -1)
          AND COALESCE(pair_id, -1) = COALESCE(?, -1)
          AND COALESCE(token_mint, '') = COALESCE(?, '')
          AND COALESCE(pair_address, '') = COALESCE(?, '')
          AND captured_at = ?
        LIMIT 1
        """,
        (token_id, pair_id, token_mint, pair_address, captured_at),
    ).fetchone()
    return int(row["id"]) if row else None


def record_liquidity_exit_snapshot(
    db_path_or_conn: str | Path | sqlite3.Connection,
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> tuple[bool, int]:
    current_time = now or utc_now()
    normalized = normalize_liquidity_exit_payload(payload, current_time)
    normalized["captured_at"] = normalized.get("captured_at") or to_timestamp(current_time)
    normalized["source_status"] = SourceStatus(normalized["source_status"]).value
    normalized["data_quality_label"] = DataQualityLabel(normalized["data_quality_label"]).value
    normalized["liquidity_state_label"] = classify_liquidity_state(normalized).value
    normalized["entry_realism_label"] = classify_entry_realism(normalized).value
    normalized["exit_realism_label"] = classify_exit_realism(normalized).value
    normalized["slippage_label"] = classify_slippage(normalized).value
    normalized["price_impact_label"] = classify_price_impact(normalized).value
    normalized["route_label"] = classify_route_availability(normalized).value
    normalized["quote_age_label"] = classify_quote_age(normalized, current_time).value
    normalized["liquidity_drain_label"] = classify_liquidity_drain(normalized).value
    normalized["liquidity_exit_payload_quality_label"] = classify_liquidity_exit_payload_quality(
        normalized,
        current_time,
    ).value
    normalized["realism_gate_label"] = classify_realism_gate(normalized).value

    with connect(db_path_or_conn) as connection:
        resolve_token_pair_fields(connection, normalized)
        duplicate_id = existing_snapshot_id(
            connection,
            token_id=normalized.get("token_id"),
            pair_id=normalized.get("pair_id"),
            token_mint=normalized.get("token_mint"),
            pair_address=normalized.get("pair_address"),
            captured_at=normalized["captured_at"],
        )
        if duplicate_id is not None:
            return False, duplicate_id
        normalized["raw_liquidity_exit_payload_json"] = json.dumps(dict(payload), sort_keys=True)
        normalized["normalized_liquidity_exit_payload_json"] = json.dumps(
            normalized,
            sort_keys=True,
        )
        placeholders = ", ".join("?" for _ in INSERT_FIELDS)
        columns = ", ".join(INSERT_FIELDS)
        cursor = connection.execute(
            f"INSERT INTO printer_liquidity_exit_snapshots ({columns}) VALUES ({placeholders})",
            tuple(normalized.get(field) for field in INSERT_FIELDS),
        )
        return True, int(cursor.lastrowid)


def record_liquidity_exit_from_source_response(
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
    return record_liquidity_exit_snapshot(db_path_or_conn, payload, now)


def record_liquidity_exit_from_token_snapshot(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_snapshot_id: int,
    supplemental_payload: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> tuple[bool, int]:
    with connect(db_path_or_conn) as connection:
        row = connection.execute(
            "SELECT * FROM printer_token_snapshots WHERE id = ?",
            (token_snapshot_id,),
        ).fetchone()
    if row is None:
        raise ValueError(f"Token snapshot not found: {token_snapshot_id}")
    payload = dict(row)
    payload.update(dict(supplemental_payload or {}))
    return record_liquidity_exit_snapshot(db_path_or_conn, payload, now)


def get_latest_liquidity_exit_snapshot(
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
            FROM printer_liquidity_exit_snapshots
            {where}
            ORDER BY captured_at DESC, id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()


def enqueue_liquidity_exit_refresh_job(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    scheduled_for: datetime,
    reason: str | None = None,
) -> tuple[LockResult, int | None]:
    suffix = reason or "scheduled"
    return enqueue_job(
        db_path_or_conn,
        job_name=f"liquidity_exit_refresh_{token_id}_{pair_id or 0}_{suffix}",
        job_kind=JobKind.TRACKED_TOKEN_SAFETY_LIQUIDITY_REFRESH,
        target_table="printer_liquidity_exit_snapshots",
        target_id=token_id,
        scheduled_for=scheduled_for,
    )

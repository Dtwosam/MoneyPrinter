"""SQLite-backed Solana chain heat context recorder."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.chain_heat.classifier import (
    classify_chain_heat,
    classify_chain_heat_payload_quality,
    classify_solana_activity,
    classify_solana_congestion,
    classify_solana_liquidity,
)
from printer_v1.chain_heat.parser import normalize_chain_heat_payload, to_timestamp
from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import enqueue_job


INSERT_FIELDS = (
    "captured_at",
    "sol_price_usd",
    "sol_change_1h",
    "sol_change_24h",
    "sol_change_7d",
    "sol_volume_24h",
    "solana_tvl_usd",
    "solana_dex_volume_24h",
    "solana_stablecoin_supply",
    "solana_active_addresses",
    "solana_tx_count_24h",
    "solana_priority_fee_context",
    "solana_congestion_context",
    "solana_new_token_count",
    "solana_hot_pair_count",
    "solana_meme_volume_24h",
    "solana_meme_liquidity_usd",
    "solana_meme_new_pair_count",
    "solana_meme_graduation_count",
    "solana_meme_failed_pair_count",
    "chain_heat_label",
    "activity_label",
    "liquidity_label",
    "congestion_label",
    "chain_heat_payload_quality_label",
    "data_quality_label",
    "source_status",
    "raw_chain_heat_payload_json",
    "normalized_chain_heat_payload_json",
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


def get_latest_chain_heat_snapshot(
    db_path_or_conn: str | Path | sqlite3.Connection,
) -> sqlite3.Row | None:
    with connect(db_path_or_conn) as connection:
        return connection.execute(
            """
            SELECT *
            FROM printer_solana_chain_heat_snapshots
            ORDER BY captured_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()


def existing_snapshot_id(connection: sqlite3.Connection, captured_at: str) -> int | None:
    row = connection.execute(
        "SELECT id FROM printer_solana_chain_heat_snapshots WHERE captured_at = ? LIMIT 1",
        (captured_at,),
    ).fetchone()
    return int(row["id"]) if row else None


def record_chain_heat_snapshot(
    db_path_or_conn: str | Path | sqlite3.Connection,
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> tuple[bool, int]:
    current_time = now or utc_now()
    normalized = normalize_chain_heat_payload(payload, current_time)
    normalized["captured_at"] = normalized.get("captured_at") or to_timestamp(current_time)
    normalized["source_status"] = SourceStatus(normalized["source_status"]).value
    normalized["data_quality_label"] = DataQualityLabel(normalized["data_quality_label"]).value
    normalized["chain_heat_label"] = classify_chain_heat(normalized).value
    normalized["activity_label"] = classify_solana_activity(normalized).value
    normalized["liquidity_label"] = classify_solana_liquidity(normalized).value
    normalized["congestion_label"] = classify_solana_congestion(normalized).value
    normalized["chain_heat_payload_quality_label"] = classify_chain_heat_payload_quality(
        normalized,
        current_time,
    ).value

    with connect(db_path_or_conn) as connection:
        duplicate_id = existing_snapshot_id(connection, normalized["captured_at"])
        if duplicate_id is not None:
            return False, duplicate_id
        normalized["raw_chain_heat_payload_json"] = json.dumps(dict(payload), sort_keys=True)
        normalized["normalized_chain_heat_payload_json"] = json.dumps(normalized, sort_keys=True)
        placeholders = ", ".join("?" for _ in INSERT_FIELDS)
        columns = ", ".join(INSERT_FIELDS)
        cursor = connection.execute(
            f"INSERT INTO printer_solana_chain_heat_snapshots ({columns}) VALUES ({placeholders})",
            tuple(normalized.get(field) for field in INSERT_FIELDS),
        )
        return True, int(cursor.lastrowid)


def record_chain_heat_from_source_response(
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
    return record_chain_heat_snapshot(db_path_or_conn, payload, now)


def enqueue_chain_heat_refresh_job(
    db_path_or_conn: str | Path | sqlite3.Connection,
    scheduled_for: datetime,
    reason: str | None = None,
) -> tuple[LockResult, int | None]:
    suffix = reason or "scheduled"
    return enqueue_job(
        db_path_or_conn,
        job_name=f"solana_chain_heat_refresh_{suffix}",
        job_kind=JobKind.SOLANA_CHAIN_HEAT_CONTEXT,
        target_table="printer_solana_chain_heat_snapshots",
        target_id=None,
        scheduled_for=scheduled_for,
    )

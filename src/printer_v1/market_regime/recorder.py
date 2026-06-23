"""SQLite-backed market regime context recorder."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.market_regime.classifier import (
    classify_market_payload_quality,
    classify_market_regime,
    classify_market_transition,
)
from printer_v1.market_regime.contracts import MarketPayloadQualityLabel, MarketTransitionLabel
from printer_v1.market_regime.parser import normalize_market_payload, to_timestamp
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import enqueue_job


INSERT_FIELDS = (
    "captured_at",
    "btc_price_usd",
    "btc_change_1h",
    "btc_change_24h",
    "btc_change_7d",
    "eth_price_usd",
    "eth_change_24h",
    "eth_change_7d",
    "sol_price_usd",
    "sol_change_1h",
    "sol_change_24h",
    "sol_change_7d",
    "sol_volume_24h",
    "fear_greed_value",
    "fear_greed_label",
    "fear_greed_previous_value",
    "fear_greed_previous_label",
    "solana_tvl_usd",
    "solana_dex_volume_context",
    "stablecoin_context",
    "tracked_solana_meme_volume",
    "tracked_solana_meme_liquidity",
    "tracked_solana_hot_pair_count",
    "tracked_solana_new_pair_count",
    "market_regime_label",
    "market_transition_label",
    "market_payload_quality_label",
    "data_quality_label",
    "source_status",
    "raw_market_payload_json",
    "normalized_market_payload_json",
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


def get_latest_market_regime_snapshot(
    db_path_or_conn: str | Path | sqlite3.Connection,
) -> sqlite3.Row | None:
    with connect(db_path_or_conn) as connection:
        return connection.execute(
            """
            SELECT *
            FROM printer_market_regime_snapshots
            ORDER BY captured_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()


def existing_snapshot_id(connection: sqlite3.Connection, captured_at: str) -> int | None:
    row = connection.execute(
        "SELECT id FROM printer_market_regime_snapshots WHERE captured_at = ? LIMIT 1",
        (captured_at,),
    ).fetchone()
    return int(row["id"]) if row else None


def record_market_regime_snapshot(
    db_path_or_conn: str | Path | sqlite3.Connection,
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> tuple[bool, int]:
    current_time = now or utc_now()
    normalized = normalize_market_payload(payload, current_time)
    normalized["captured_at"] = normalized.get("captured_at") or to_timestamp(current_time)
    normalized["source_status"] = SourceStatus(normalized["source_status"]).value
    normalized["data_quality_label"] = DataQualityLabel(normalized["data_quality_label"]).value
    quality = classify_market_payload_quality(
        normalized,
        current_time,
    )
    normalized["market_payload_quality_label"] = quality.value
    if quality in {
        MarketPayloadQualityLabel.MARKET_CONTEXT_STALE,
        MarketPayloadQualityLabel.MARKET_CONTEXT_CONFLICTING,
        MarketPayloadQualityLabel.MARKET_CONTEXT_UNKNOWN,
        MarketPayloadQualityLabel.MARKET_CONTEXT_DO_NOT_USE_FOR_MEMORY,
    }:
        normalized["market_regime_label"] = "UNKNOWN"
    else:
        normalized["market_regime_label"] = classify_market_regime(normalized).value

    with connect(db_path_or_conn) as connection:
        duplicate_id = existing_snapshot_id(connection, normalized["captured_at"])
        if duplicate_id is not None:
            return False, duplicate_id
        previous = connection.execute(
            """
            SELECT *
            FROM printer_market_regime_snapshots
            WHERE captured_at < ?
            ORDER BY captured_at DESC, id DESC
            LIMIT 1
            """,
            (normalized["captured_at"],),
        ).fetchone()
        normalized["market_transition_label"] = classify_market_transition(
            previous,
            normalized,
        ).value
        if previous is None:
            normalized["market_transition_label"] = MarketTransitionLabel.UNKNOWN_TRANSITION.value
        normalized["raw_market_payload_json"] = json.dumps(dict(payload), sort_keys=True)
        normalized["normalized_market_payload_json"] = json.dumps(normalized, sort_keys=True)
        placeholders = ", ".join("?" for _ in INSERT_FIELDS)
        columns = ", ".join(INSERT_FIELDS)
        cursor = connection.execute(
            f"INSERT INTO printer_market_regime_snapshots ({columns}) VALUES ({placeholders})",
            tuple(normalized.get(field) for field in INSERT_FIELDS),
        )
        return True, int(cursor.lastrowid)


def record_market_regime_from_source_response(
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
    return record_market_regime_snapshot(db_path_or_conn, payload, now)


def enqueue_market_regime_refresh_job(
    db_path_or_conn: str | Path | sqlite3.Connection,
    scheduled_for: datetime,
    reason: str | None = None,
) -> tuple[LockResult, int | None]:
    suffix = reason or "scheduled"
    return enqueue_job(
        db_path_or_conn,
        job_name=f"market_regime_refresh_{suffix}",
        job_kind=JobKind.MARKET_REGIME_CONTEXT,
        target_table="printer_market_regime_snapshots",
        target_id=None,
        scheduled_for=scheduled_for,
    )

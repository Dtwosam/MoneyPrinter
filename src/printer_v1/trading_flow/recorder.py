"""SQLite-backed Trading Flow snapshot recorder."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import enqueue_job
from printer_v1.trading_flow.contracts import TradingFlowPayloadQualityLabel
from printer_v1.trading_flow.classifier import (
    classify_flow_direction,
    classify_flow_memory_gate,
    classify_flow_pressure,
    classify_imbalance,
    classify_trading_flow_payload_quality,
    classify_tx_activity,
    classify_volume_activity,
    classify_wallet_participation,
)
from printer_v1.trading_flow.parser import normalize_trading_flow_payload, to_timestamp
from printer_v1.trading_flow.evidence_completeness import (
    plan_optional_wallet_flow_enrichment,
)


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
    "volume_4h",
    "volume_24h",
    "txns_5m",
    "txns_15m",
    "txns_1h",
    "txns_4h",
    "txns_24h",
    "buys_5m",
    "sells_5m",
    "buys_15m",
    "sells_15m",
    "buys_1h",
    "sells_1h",
    "buys_4h",
    "sells_4h",
    "buys_24h",
    "sells_24h",
    "buy_volume_5m",
    "sell_volume_5m",
    "buy_volume_15m",
    "sell_volume_15m",
    "buy_volume_1h",
    "sell_volume_1h",
    "buy_volume_4h",
    "sell_volume_4h",
    "buy_volume_24h",
    "sell_volume_24h",
    "unique_wallets_5m",
    "unique_wallets_15m",
    "unique_wallets_1h",
    "unique_wallets_24h",
    "new_wallets_5m",
    "new_wallets_15m",
    "repeat_wallets_5m",
    "repeat_wallets_15m",
    "flow_direction_label",
    "flow_pressure_label",
    "imbalance_label",
    "volume_activity_label",
    "tx_activity_label",
    "wallet_participation_label",
    "trading_flow_payload_quality_label",
    "flow_memory_gate_label",
    "data_quality_label",
    "source_status",
    "raw_trading_flow_payload_json",
    "normalized_trading_flow_payload_json",
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
        FROM printer_trading_flow_snapshots
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


def record_trading_flow_snapshot(
    db_path_or_conn: str | Path | sqlite3.Connection,
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> tuple[bool, int]:
    current_time = now or utc_now()
    normalized = normalize_trading_flow_payload(payload, current_time)
    normalized["captured_at"] = normalized.get("captured_at") or to_timestamp(current_time)
    normalized["source_status"] = SourceStatus(normalized["source_status"]).value
    normalized["data_quality_label"] = DataQualityLabel(normalized["data_quality_label"]).value
    payload_quality = classify_trading_flow_payload_quality(
        normalized,
        current_time,
    )
    if payload_quality in {
        TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_STALE,
        TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CONFLICTING,
        TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_UNKNOWN,
        TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_DO_NOT_USE_FOR_MEMORY,
    }:
        normalized["flow_direction_label"] = "FLOW_UNKNOWN"
        normalized["flow_pressure_label"] = "PRESSURE_UNKNOWN"
    else:
        normalized["flow_direction_label"] = classify_flow_direction(normalized).value
        normalized["flow_pressure_label"] = classify_flow_pressure(normalized).value
    normalized["imbalance_label"] = classify_imbalance(normalized).value
    normalized["volume_activity_label"] = classify_volume_activity(normalized).value
    normalized["tx_activity_label"] = classify_tx_activity(normalized).value
    normalized["wallet_participation_label"] = classify_wallet_participation(normalized).value
    normalized["trading_flow_payload_quality_label"] = payload_quality.value
    normalized["flow_memory_gate_label"] = classify_flow_memory_gate(normalized, current_time).value
    # Current approved pair-snapshot sources do not deterministically expose
    # unique wallets or split buy/sell volume. Record that the optional gap was
    # evaluated rather than silently ignoring it. A future approved free
    # enricher can flip the availability input without changing clean-memory
    # eligibility or inventing values.
    normalized["optional_wallet_flow_enrichment"] = (
        plan_optional_wallet_flow_enrichment(
            normalized,
            approved_free_enricher_available=False,
            source_budget_available=True,
        ).to_dict()
    )

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
        normalized["raw_trading_flow_payload_json"] = json.dumps(dict(payload), sort_keys=True)
        normalized["normalized_trading_flow_payload_json"] = json.dumps(
            normalized,
            sort_keys=True,
        )
        placeholders = ", ".join("?" for _ in INSERT_FIELDS)
        columns = ", ".join(INSERT_FIELDS)
        cursor = connection.execute(
            f"INSERT INTO printer_trading_flow_snapshots ({columns}) VALUES ({placeholders})",
            tuple(normalized.get(field) for field in INSERT_FIELDS),
        )
        return True, int(cursor.lastrowid)


def record_trading_flow_from_source_response(
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
    return record_trading_flow_snapshot(db_path_or_conn, payload, now)


def record_trading_flow_from_token_snapshot(
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
    return record_trading_flow_snapshot(db_path_or_conn, payload, now)


def get_latest_trading_flow_snapshot(
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
            FROM printer_trading_flow_snapshots
            {where}
            ORDER BY captured_at DESC, id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()


def enqueue_trading_flow_refresh_job(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    scheduled_for: datetime,
    reason: str | None = None,
) -> tuple[LockResult, int | None]:
    suffix = reason or "scheduled"
    return enqueue_job(
        db_path_or_conn,
        job_name=f"trading_flow_refresh_{token_id}_{pair_id or 0}_{suffix}",
        job_kind=JobKind.TRACK_FAST_FIRST_15M,
        target_table="printer_trading_flow_snapshots",
        target_id=token_id,
        scheduled_for=scheduled_for,
    )

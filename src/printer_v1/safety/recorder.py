"""SQLite-backed Safety / Rug snapshot recorder."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.safety.classifier import (
    classify_authority_safety,
    classify_distribution_safety,
    classify_liquidity_safety,
    classify_rug_risk,
    classify_safety_gate,
    classify_safety_payload_quality,
    classify_safety_status,
)
from printer_v1.safety.parser import normalize_safety_payload, to_timestamp
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import enqueue_job


INSERT_FIELDS = (
    "token_id",
    "pair_id",
    "token_mint",
    "pair_address",
    "captured_at",
    "liquidity_usd",
    "liquidity_locked",
    "liquidity_lock_source",
    "liquidity_lock_until",
    "holder_count",
    "top_holder_percent",
    "top_5_holder_percent",
    "top_10_holder_percent",
    "creator_percent",
    "mint_authority_present",
    "freeze_authority_present",
    "update_authority_present",
    "transfer_fee_present",
    "blacklist_function_present",
    "honeypot_like_behavior",
    "sell_restriction_detected",
    "buy_restriction_detected",
    "mutable_metadata",
    "suspicious_metadata",
    "suspicious_creator_activity",
    "source_name",
    "safety_status_label",
    "rug_risk_label",
    "liquidity_safety_label",
    "authority_label",
    "distribution_label",
    "safety_payload_quality_label",
    "safety_gate_label",
    "data_quality_label",
    "source_status",
    "raw_safety_payload_json",
    "normalized_safety_payload_json",
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


def resolve_token_pair_fields(
    connection: sqlite3.Connection,
    normalized: dict[str, Any],
) -> None:
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
        FROM printer_safety_rug_snapshots
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


def record_safety_rug_snapshot(
    db_path_or_conn: str | Path | sqlite3.Connection,
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> tuple[bool, int]:
    current_time = now or utc_now()
    normalized = normalize_safety_payload(payload, current_time)
    normalized["captured_at"] = normalized.get("captured_at") or to_timestamp(current_time)
    normalized["source_status"] = SourceStatus(normalized["source_status"]).value
    normalized["data_quality_label"] = DataQualityLabel(normalized["data_quality_label"]).value
    normalized["safety_status_label"] = classify_safety_status(normalized).value
    normalized["rug_risk_label"] = classify_rug_risk(normalized).value
    normalized["liquidity_safety_label"] = classify_liquidity_safety(normalized).value
    normalized["authority_label"] = classify_authority_safety(normalized).value
    normalized["distribution_label"] = classify_distribution_safety(normalized).value
    normalized["safety_payload_quality_label"] = classify_safety_payload_quality(
        normalized,
        current_time,
    ).value
    normalized["safety_gate_label"] = classify_safety_gate(normalized).value

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
        normalized["raw_safety_payload_json"] = json.dumps(dict(payload), sort_keys=True)
        normalized["normalized_safety_payload_json"] = json.dumps(normalized, sort_keys=True)
        placeholders = ", ".join("?" for _ in INSERT_FIELDS)
        columns = ", ".join(INSERT_FIELDS)
        cursor = connection.execute(
            f"INSERT INTO printer_safety_rug_snapshots ({columns}) VALUES ({placeholders})",
            tuple(normalized.get(field) for field in INSERT_FIELDS),
        )
        return True, int(cursor.lastrowid)


def record_safety_rug_from_source_response(
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
    payload.setdefault("source_name", row["source_name"])
    payload.setdefault("source_status", row["source_status"])
    payload.setdefault("data_quality_label", row["data_quality_label"])
    payload.setdefault("captured_at", row["received_at"])
    return record_safety_rug_snapshot(db_path_or_conn, payload, now)


def get_latest_safety_rug_snapshot(
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
            FROM printer_safety_rug_snapshots
            {where}
            ORDER BY captured_at DESC, id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()


def enqueue_safety_rug_refresh_job(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    scheduled_for: datetime,
    reason: str | None = None,
) -> tuple[LockResult, int | None]:
    suffix = reason or "scheduled"
    return enqueue_job(
        db_path_or_conn,
        job_name=f"safety_rug_refresh_{token_id}_{pair_id or 0}_{suffix}",
        job_kind=JobKind.TRACKED_TOKEN_SAFETY_LIQUIDITY_REFRESH,
        target_table="printer_safety_rug_snapshots",
        target_id=token_id,
        scheduled_for=scheduled_for,
    )

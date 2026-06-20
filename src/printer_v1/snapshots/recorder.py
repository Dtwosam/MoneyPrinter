"""SQLite-backed token snapshot recording helpers."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.lifecycle.contracts import TokenLifecycleState
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import enqueue_job
from printer_v1.snapshots.contracts import CoverageLabel, SnapshotGapLabel, SnapshotMode
from printer_v1.snapshots.quality import (
    classify_snapshot_quality,
    normalize_snapshot_payload,
    to_timestamp,
)


SCHEDULER_KIND_BY_LANE = {
    TokenLifecycleState.PAPER_MONITORING: JobKind.OPEN_PAPER_TRADE_MONITOR,
    TokenLifecycleState.TRACK_FAST: JobKind.TRACK_FAST_FIRST_15M,
    TokenLifecycleState.TRACK_NORMAL: JobKind.TRACK_NORMAL_FIRST_15M,
    TokenLifecycleState.WATCH_ONLY: JobKind.DISCOVERY_REFRESH,
    TokenLifecycleState.COOLDOWN: JobKind.BACKUP_SOURCE_CHECK,
}


SNAPSHOT_INSERT_FIELDS = (
    "token_id",
    "pair_id",
    "captured_at",
    "tracking_lane",
    "snapshot_mode",
    "price_usd",
    "price_native",
    "liquidity_usd",
    "volume_5m",
    "volume_15m",
    "volume_1h",
    "volume_4h",
    "volume_12h",
    "volume_24h",
    "txns_5m",
    "txns_15m",
    "txns_1h",
    "txns_4h",
    "txns_12h",
    "txns_24h",
    "fdv",
    "market_cap",
    "price_change_5m",
    "price_change_15m",
    "price_change_1h",
    "price_change_4h",
    "price_change_12h",
    "price_change_24h",
    "source_status",
    "data_quality_label",
    "pair_age_seconds",
    "token_age_seconds",
    "quote_status",
    "route_status",
    "snapshot_quality_label",
    "snapshot_gap_label",
    "coverage_label",
    "raw_snapshot_payload_json",
    "normalized_snapshot_payload_json",
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


def resolve_token_pair_ids(
    connection: sqlite3.Connection,
    payload: Mapping[str, Any],
) -> tuple[int | None, int | None]:
    token_id = payload.get("token_id")
    pair_id = payload.get("pair_id")
    if token_id is None and payload.get("token_mint"):
        row = connection.execute(
            "SELECT id FROM printer_tokens WHERE token_mint = ?",
            (payload["token_mint"],),
        ).fetchone()
        token_id = row["id"] if row else None
    if pair_id is None and payload.get("pair_address"):
        row = connection.execute(
            "SELECT id FROM printer_pairs WHERE pair_address = ?",
            (payload["pair_address"],),
        ).fetchone()
        pair_id = row["id"] if row else None
    return token_id, pair_id


def existing_snapshot_id(
    connection: sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int | None,
    captured_at: str,
    snapshot_mode: str,
) -> int | None:
    row = connection.execute(
        """
        SELECT id
        FROM printer_token_snapshots
        WHERE token_id = ?
          AND COALESCE(pair_id, -1) = COALESCE(?, -1)
          AND captured_at = ?
          AND snapshot_mode = ?
        LIMIT 1
        """,
        (token_id, pair_id, captured_at, snapshot_mode),
    ).fetchone()
    return int(row["id"]) if row else None


def record_token_snapshot(
    db_path_or_conn: str | Path | sqlite3.Connection,
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> tuple[bool, int]:
    normalized = normalize_snapshot_payload(payload)
    with connect(db_path_or_conn) as connection:
        token_id, pair_id = resolve_token_pair_ids(connection, normalized)
        normalized["token_id"] = token_id
        normalized["pair_id"] = pair_id
        quality = classify_snapshot_quality(normalized, now or utc_now())
        normalized["snapshot_quality_label"] = quality.value
        normalized.setdefault("snapshot_gap_label", SnapshotGapLabel.NO_GAP.value)
        normalized.setdefault("coverage_label", CoverageLabel.AUDIT_ONLY_COVERAGE.value)
        normalized["raw_snapshot_payload_json"] = json.dumps(dict(payload), sort_keys=True)
        normalized["normalized_snapshot_payload_json"] = json.dumps(
            normalized,
            sort_keys=True,
        )
        if normalized.get("token_id") is None:
            raise ValueError("Snapshot payload must resolve token_id or token_mint")
        if normalized.get("captured_at") is None:
            raise ValueError("Snapshot payload must include captured_at")
        duplicate_id = existing_snapshot_id(
            connection,
            token_id=int(normalized["token_id"]),
            pair_id=normalized.get("pair_id"),
            captured_at=normalized["captured_at"],
            snapshot_mode=SnapshotMode(normalized["snapshot_mode"]).value,
        )
        if duplicate_id is not None:
            return False, duplicate_id
        placeholders = ", ".join("?" for _ in SNAPSHOT_INSERT_FIELDS)
        columns = ", ".join(SNAPSHOT_INSERT_FIELDS)
        cursor = connection.execute(
            f"INSERT INTO printer_token_snapshots ({columns}) VALUES ({placeholders})",
            tuple(normalized.get(field) for field in SNAPSHOT_INSERT_FIELDS),
        )
        return True, int(cursor.lastrowid)


def record_snapshot_from_source_response(
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
    return record_token_snapshot(db_path_or_conn, payload, now)


def get_latest_snapshot(
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
            FROM printer_token_snapshots
            {where}
            ORDER BY captured_at DESC, id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()


def get_snapshots_for_window(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    opened_at: datetime,
    closed_at: datetime,
) -> list[sqlite3.Row]:
    with connect(db_path_or_conn) as connection:
        return connection.execute(
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


def enqueue_next_snapshot_job(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    tracking_lane: TokenLifecycleState | str,
    snapshot_mode: SnapshotMode | str,
    scheduled_for: datetime,
) -> tuple[LockResult, int | None]:
    lane = TokenLifecycleState(tracking_lane)
    mode = SnapshotMode(snapshot_mode)
    return enqueue_job(
        db_path_or_conn,
        job_name=f"token_snapshot_{token_id}_{pair_id or 0}_{mode.value}",
        job_kind=SCHEDULER_KIND_BY_LANE.get(lane, JobKind.BACKUP_SOURCE_CHECK),
        target_table="printer_token_snapshots",
        target_id=token_id,
        scheduled_for=scheduled_for,
    )


def record_snapshot_gap_audit(
    db_path_or_conn: str | Path | sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int | None,
    tracking_lane: TokenLifecycleState | str,
    snapshot_mode: SnapshotMode | str,
    expected_captured_at: datetime,
    actual_captured_at: datetime | None,
    gap_seconds: int,
    snapshot_gap_label: SnapshotGapLabel | str,
    coverage_label: CoverageLabel | str,
    source_status: SourceStatus | str,
    data_quality_label: DataQualityLabel | str,
) -> int:
    with connect(db_path_or_conn) as connection:
        cursor = connection.execute(
            """
            INSERT INTO printer_snapshot_gap_audits (
                token_id,
                pair_id,
                tracking_lane,
                snapshot_mode,
                expected_captured_at,
                actual_captured_at,
                gap_seconds,
                snapshot_gap_label,
                coverage_label,
                source_status,
                data_quality_label
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token_id,
                pair_id,
                TokenLifecycleState(tracking_lane).value,
                SnapshotMode(snapshot_mode).value,
                to_timestamp(expected_captured_at),
                to_timestamp(actual_captured_at) if actual_captured_at else None,
                gap_seconds,
                SnapshotGapLabel(snapshot_gap_label).value,
                CoverageLabel(coverage_label).value,
                SourceStatus(source_status).value,
                DataQualityLabel(data_quality_label).value,
            ),
        )
        return int(cursor.lastrowid)

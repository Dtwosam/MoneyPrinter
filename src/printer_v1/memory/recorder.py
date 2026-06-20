"""SQLite-backed Episode / Memory recorder."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping, Sequence

from printer_v1.contracts.enums import DataQualityLabel
from printer_v1.memory.assembler import assemble_episode
from printer_v1.memory.contracts import EpisodeStatus, MemoryQualityLabel
from printer_v1.memory.fingerprints import build_memory_fingerprint_payload, record_memory_fingerprint as write_fingerprint, storage_memory_status
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import enqueue_job


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_timestamp(value: datetime | str) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


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


def record_memory_window(db_path_or_conn: str | Path | sqlite3.Connection, payload: Mapping[str, Any]) -> int:
    with connect(db_path_or_conn) as connection:
        cursor = connection.execute(
            """
            INSERT INTO printer_memory_windows (
                token_id, pair_id, window_kind, opened_at, closed_at,
                memory_status, data_quality_label, do_not_train, window_status,
                outcome_label, memory_quality_label, rejection_reasons_json,
                supporting_context_json, created_by_phase
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'phase14')
            """,
            (
                payload["token_id"],
                payload.get("pair_id"),
                payload["window_kind"],
                payload["opened_at"],
                payload.get("closed_at"),
                storage_memory_status(payload.get("memory_quality_label", MemoryQualityLabel.PARTIAL_MEMORY)),
                payload.get("data_quality_label", DataQualityLabel.CLEAN_DATA.value),
                1 if payload.get("memory_quality_label") in {MemoryQualityLabel.DIRTY_MEMORY.value, MemoryQualityLabel.DO_NOT_TRAIN_MEMORY.value} else 0,
                payload.get("window_status", "WINDOW_CLOSED"),
                payload.get("outcome_label"),
                payload.get("memory_quality_label"),
                json.dumps(payload.get("rejection_reasons", []), sort_keys=True),
                json.dumps(payload.get("supporting_context", {}), sort_keys=True),
            ),
        )
        return int(cursor.lastrowid)


def find_existing_episode(connection: sqlite3.Connection, memory_window_id: int) -> int | None:
    row = connection.execute(
        "SELECT id FROM printer_episodes WHERE memory_window_id = ? LIMIT 1",
        (memory_window_id,),
    ).fetchone()
    return int(row["id"]) if row else None


def record_episode(db_path_or_conn: str | Path | sqlite3.Connection, episode_payload: Mapping[str, Any]) -> tuple[bool, int]:
    window = episode_payload["window"]
    quality = MemoryQualityLabel(episode_payload["memory_quality_label"])
    status = EpisodeStatus.EPISODE_BUILT
    if quality == MemoryQualityLabel.DIRTY_MEMORY:
        status = EpisodeStatus.EPISODE_DIRTY
    elif quality == MemoryQualityLabel.AUDIT_ONLY_MEMORY:
        status = EpisodeStatus.EPISODE_AUDIT_ONLY
    elif quality == MemoryQualityLabel.DO_NOT_TRAIN_MEMORY:
        status = EpisodeStatus.EPISODE_SKIPPED
    with connect(db_path_or_conn) as connection:
        existing = find_existing_episode(connection, int(window["id"]))
        if existing is not None:
            return False, existing
        cursor = connection.execute(
            """
            INSERT INTO printer_episodes (
                memory_window_id, token_id, pair_id, episode_kind, episode_status,
                memory_status, data_quality_label, do_not_train, window_kind,
                episode_outcome_label, memory_quality_label, action_lesson_label,
                rejection_reasons_json, episode_summary_json, supporting_context_json
            )
            VALUES (?, ?, ?, 'TOKEN_WINDOW_EPISODE', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                window["id"],
                window["token_id"],
                window["pair_id"],
                status.value,
                storage_memory_status(quality),
                DataQualityLabel.CLEAN_DATA.value,
                0 if quality == MemoryQualityLabel.CLEAN_MEMORY else 1,
                window["window_kind"],
                episode_payload["outcome_label"],
                quality.value,
                episode_payload["action_lesson_label"],
                json.dumps(episode_payload["rejection_reasons"], sort_keys=True),
                json.dumps({"price_path": episode_payload["price_path"]}, sort_keys=True),
                json.dumps(episode_payload["supporting_context"], sort_keys=True),
            ),
        )
        return True, int(cursor.lastrowid)


def record_episode_snapshots(db_path_or_conn: str | Path | sqlite3.Connection, episode_id: int, snapshots: Sequence[Mapping[str, Any]]) -> None:
    with connect(db_path_or_conn) as connection:
        for position, snapshot in enumerate(snapshots):
            connection.execute(
                """
                INSERT INTO printer_episode_snapshots (episode_id, token_snapshot_id, position_in_episode)
                VALUES (?, ?, ?)
                """,
                (episode_id, snapshot["id"], position),
            )


def record_episode_outcome(db_path_or_conn: str | Path | sqlite3.Connection, episode_id: int, episode_payload: Mapping[str, Any]) -> int:
    window = episode_payload["window"]
    path = episode_payload["price_path"]
    quality = episode_payload["memory_quality_label"]
    with connect(db_path_or_conn) as connection:
        cursor = connection.execute(
            """
            INSERT INTO printer_episode_outcomes (
                episode_id, memory_window_id, token_id, pair_id, window_kind,
                outcome_label, action_lesson_label, price_start, price_high,
                price_low, price_end, price_change_percent, max_runup_percent,
                max_drawdown_percent, realistic_entry_available,
                realistic_exit_available, realistic_profit_possible,
                capital_protection_possible, memory_quality_label,
                rejection_reasons_json, outcome_payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                episode_id,
                window["id"],
                window["token_id"],
                window["pair_id"],
                window["window_kind"],
                episode_payload["outcome_label"],
                episode_payload["action_lesson_label"],
                path["price_start"],
                path["price_high"],
                path["price_low"],
                path["price_end"],
                path["price_change_percent"],
                path["max_runup_percent"],
                path["max_drawdown_percent"],
                1 if episode_payload["outcome_label"] == "REALISTIC_PAPER_PROFIT" else 0,
                1 if episode_payload["outcome_label"] == "REALISTIC_PAPER_PROFIT" else 0,
                1 if episode_payload["outcome_label"] == "REALISTIC_PAPER_PROFIT" else 0,
                1 if episode_payload["outcome_label"] in {"DUMP", "DEAD_TOKEN", "FAKE_PUMP", "PUMP_AND_DUMP"} else 0,
                quality,
                json.dumps(episode_payload["rejection_reasons"], sort_keys=True),
                json.dumps(path, sort_keys=True),
            ),
        )
        return int(cursor.lastrowid)


def record_memory_audit_report(db_path_or_conn: str | Path | sqlite3.Connection, episode_id: int, episode_payload: Mapping[str, Any]) -> int:
    window = episode_payload["window"]
    with connect(db_path_or_conn) as connection:
        cursor = connection.execute(
            """
            INSERT INTO printer_memory_audit_reports (
                episode_id, memory_window_id, token_id, pair_id, audit_status,
                memory_quality_label, rejection_reasons_json, audit_payload_json
            )
            VALUES (?, ?, ?, ?, 'PHASE14_STATIC_AUDIT', ?, ?, ?)
            """,
            (
                episode_id,
                window["id"],
                window["token_id"],
                window["pair_id"],
                episode_payload["memory_quality_label"],
                json.dumps(episode_payload["rejection_reasons"], sort_keys=True),
                json.dumps({"outcome_label": episode_payload["outcome_label"]}, sort_keys=True),
            ),
        )
        return int(cursor.lastrowid)


def record_memory_fingerprint(db_path_or_conn: str | Path | sqlite3.Connection, episode_id: int, episode_payload: Mapping[str, Any]) -> int:
    return write_fingerprint(
        db_path_or_conn,
        episode_id,
        build_memory_fingerprint_payload(episode_payload),
        episode_payload["memory_quality_label"],
    )


def build_and_record_episode(db_path_or_conn: str | Path | sqlite3.Connection, memory_window_id: int, now: datetime | None = None) -> tuple[bool, int]:
    payload = assemble_episode(db_path_or_conn, memory_window_id, now)
    created, episode_id = record_episode(db_path_or_conn, payload)
    if not created:
        return False, episode_id
    record_episode_snapshots(db_path_or_conn, episode_id, payload["snapshots"])
    record_episode_outcome(db_path_or_conn, episode_id, payload)
    record_memory_audit_report(db_path_or_conn, episode_id, payload)
    record_memory_fingerprint(db_path_or_conn, episode_id, payload)
    with connect(db_path_or_conn) as connection:
        connection.execute(
            """
            UPDATE printer_memory_windows
            SET window_status = 'WINDOW_CLOSED', outcome_label = ?,
                memory_quality_label = ?, rejection_reasons_json = ?,
                supporting_context_json = ?, memory_status = ?,
                do_not_train = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                payload["outcome_label"],
                payload["memory_quality_label"],
                json.dumps(payload["rejection_reasons"], sort_keys=True),
                json.dumps(payload["supporting_context"], sort_keys=True),
                storage_memory_status(payload["memory_quality_label"]),
                0 if payload["memory_quality_label"] == MemoryQualityLabel.CLEAN_MEMORY.value else 1,
                memory_window_id,
            ),
        )
    return True, episode_id


def enqueue_memory_build_job(
    db_path_or_conn: str | Path | sqlite3.Connection,
    memory_window_id: int,
    scheduled_for: datetime,
    reason: str | None = None,
) -> tuple[LockResult, int | None]:
    suffix = reason or "scheduled"
    return enqueue_job(
        db_path_or_conn,
        job_name=f"memory_build_{memory_window_id}_{suffix}",
        job_kind=JobKind.MEMORY_WINDOW_CLOSE,
        target_table="printer_memory_windows",
        target_id=memory_window_id,
        scheduled_for=scheduled_for,
    )

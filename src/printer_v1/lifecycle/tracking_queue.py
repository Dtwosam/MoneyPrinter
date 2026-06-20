"""SQLite helpers for Printer V1 token lifecycle tracking queue."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.lifecycle.contracts import (
    TRACKING_LANE_DUE_ORDER,
    LifecycleEvent,
    QueueStatus,
    TokenLifecycleState,
)
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import enqueue_job


ACTIVE_QUEUE_STATUSES = (
    QueueStatus.QUEUED,
    QueueStatus.ACTIVE,
    QueueStatus.PAUSED,
    QueueStatus.COOLDOWN,
)

QUEUE_LANE_PRIORITY = {
    lane: index + 1 for index, lane in enumerate(TRACKING_LANE_DUE_ORDER)
}

SCHEDULER_KIND_BY_LANE = {
    TokenLifecycleState.PAPER_MONITORING: JobKind.OPEN_PAPER_TRADE_MONITOR,
    TokenLifecycleState.TRACK_FAST: JobKind.TRACK_FAST_FIRST_15M,
    TokenLifecycleState.TRACK_NORMAL: JobKind.TRACK_NORMAL_FIRST_15M,
    TokenLifecycleState.WATCH_ONLY: JobKind.DISCOVERY_REFRESH,
    TokenLifecycleState.COOLDOWN: JobKind.BACKUP_SOURCE_CHECK,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


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


def normalize_pair_id(pair_id: int | None) -> int:
    return -1 if pair_id is None else pair_id


def has_active_tracking_duplicate(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int | None,
    tracking_lane: TokenLifecycleState | str,
) -> bool:
    lane = TokenLifecycleState(tracking_lane)
    with connect(db_or_connection) as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM printer_tracking_queue
            WHERE token_id = ?
              AND COALESCE(pair_id, -1) = ?
              AND tracking_lane = ?
              AND queue_status IN (?, ?, ?, ?)
            LIMIT 1
            """,
            (
                token_id,
                normalize_pair_id(pair_id),
                lane.value,
                *(status.value for status in ACTIVE_QUEUE_STATUSES),
            ),
        ).fetchone()
    return row is not None


def enqueue_tracking_item(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int | None,
    tracking_lane: TokenLifecycleState | str,
    tracking_action: LifecycleEvent | str,
    priority_reason: str,
    next_check_at: datetime,
    source_status: SourceStatus,
    data_quality_label: DataQualityLabel,
) -> tuple[bool, int | None]:
    lane = TokenLifecycleState(tracking_lane)
    action = LifecycleEvent(tracking_action)
    if has_active_tracking_duplicate(
        db_or_connection,
        token_id=token_id,
        pair_id=pair_id,
        tracking_lane=lane,
    ):
        return False, None

    with connect(db_or_connection) as connection:
        cursor = connection.execute(
            """
            INSERT INTO printer_tracking_queue (
                token_id,
                pair_id,
                tracking_lane,
                tracking_action,
                priority_reason,
                next_check_at,
                queue_status,
                source_status,
                data_quality_label
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token_id,
                pair_id,
                lane.value,
                action.value,
                priority_reason,
                to_timestamp(next_check_at),
                QueueStatus.QUEUED.value,
                source_status.value,
                data_quality_label.value,
            ),
        )
        return True, int(cursor.lastrowid)


def update_tracking_lane(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    queue_id: int,
    tracking_lane: TokenLifecycleState | str,
    tracking_action: LifecycleEvent | str,
    priority_reason: str,
    next_check_at: datetime,
) -> None:
    lane = TokenLifecycleState(tracking_lane)
    action = LifecycleEvent(tracking_action)
    with connect(db_or_connection) as connection:
        connection.execute(
            """
            UPDATE printer_tracking_queue
            SET tracking_lane = ?,
                tracking_action = ?,
                priority_reason = ?,
                next_check_at = ?,
                queue_status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                lane.value,
                action.value,
                priority_reason,
                to_timestamp(next_check_at),
                QueueStatus.QUEUED.value,
                to_timestamp(utc_now()),
                queue_id,
            ),
        )


def pause_tracking_item(db_or_connection: str | Path | sqlite3.Connection, *, queue_id: int) -> None:
    set_queue_status(db_or_connection, queue_id=queue_id, queue_status=QueueStatus.PAUSED)


def archive_tracking_item(db_or_connection: str | Path | sqlite3.Connection, *, queue_id: int) -> None:
    set_queue_status(db_or_connection, queue_id=queue_id, queue_status=QueueStatus.ARCHIVED)


def set_queue_status(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    queue_id: int,
    queue_status: QueueStatus | str,
) -> None:
    status = QueueStatus(queue_status)
    with connect(db_or_connection) as connection:
        connection.execute(
            """
            UPDATE printer_tracking_queue
            SET queue_status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (status.value, to_timestamp(utc_now()), queue_id),
        )


def get_active_tracking_items(db_or_connection: str | Path | sqlite3.Connection) -> list[sqlite3.Row]:
    with connect(db_or_connection) as connection:
        return connection.execute(
            """
            SELECT *
            FROM printer_tracking_queue
            WHERE queue_status IN (?, ?, ?, ?)
              AND tracking_lane NOT IN (?, ?)
            ORDER BY id ASC
            """,
            (
                *(status.value for status in ACTIVE_QUEUE_STATUSES),
                TokenLifecycleState.ARCHIVED.value,
                TokenLifecycleState.INSTANT_REJECT_MEMORY_ONLY.value,
            ),
        ).fetchall()


def get_due_tracking_items(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    now: datetime,
) -> list[sqlite3.Row]:
    due_lanes = tuple(lane.value for lane in TRACKING_LANE_DUE_ORDER)
    with connect(db_or_connection) as connection:
        rows = connection.execute(
            f"""
            SELECT *
            FROM printer_tracking_queue
            WHERE queue_status IN (?, ?, ?)
              AND tracking_lane IN ({",".join("?" for _ in due_lanes)})
              AND next_check_at <= ?
            """,
            (
                QueueStatus.QUEUED.value,
                QueueStatus.ACTIVE.value,
                QueueStatus.COOLDOWN.value,
                *due_lanes,
                to_timestamp(now),
            ),
        ).fetchall()
    return sorted(
        rows,
        key=lambda row: (
            QUEUE_LANE_PRIORITY[TokenLifecycleState(row["tracking_lane"])],
            row["next_check_at"],
            row["created_at"],
            row["id"],
        ),
    )


def record_lifecycle_event(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int | None,
    previous_state: TokenLifecycleState | str | None,
    new_state: TokenLifecycleState | str,
    lifecycle_event: LifecycleEvent | str,
    priority_reason: str,
    source_status: SourceStatus,
    data_quality_label: DataQualityLabel,
    event_payload: dict | None = None,
) -> int:
    previous_value = (
        TokenLifecycleState(previous_state).value if previous_state is not None else None
    )
    new_value = TokenLifecycleState(new_state).value
    event = LifecycleEvent(lifecycle_event)
    payload_json = json.dumps(event_payload or {}, sort_keys=True)
    with connect(db_or_connection) as connection:
        cursor = connection.execute(
            """
            INSERT INTO printer_token_lifecycle_events (
                token_id,
                pair_id,
                previous_state,
                new_state,
                lifecycle_event,
                priority_reason,
                source_status,
                data_quality_label,
                event_payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token_id,
                pair_id,
                previous_value,
                new_value,
                event.value,
                priority_reason,
                source_status.value,
                data_quality_label.value,
                payload_json,
            ),
        )
        return int(cursor.lastrowid)


def sync_tracking_state_with_scheduler(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    queue_id: int,
    scheduled_for: datetime,
) -> tuple[LockResult, int | None]:
    with connect(db_or_connection) as connection:
        row = connection.execute(
            "SELECT * FROM printer_tracking_queue WHERE id = ?",
            (queue_id,),
        ).fetchone()
    if row is None:
        return LockResult.NOT_FOUND, None

    lane = TokenLifecycleState(row["tracking_lane"])
    if lane not in SCHEDULER_KIND_BY_LANE:
        return LockResult.NOT_FOUND, None

    return enqueue_job(
        db_or_connection,
        job_name=f"tracking_queue_{queue_id}_{lane.value.lower()}",
        job_kind=SCHEDULER_KIND_BY_LANE[lane],
        target_table="printer_tracking_queue",
        target_id=queue_id,
        scheduled_for=scheduled_for,
    )

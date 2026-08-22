"""SQLite-backed scheduler helpers for Printer V1 Phase 3."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from printer_v1.scheduler.contracts import ACTIVE_JOB_STATUSES, JobKind, JobStatus, LockResult
from printer_v1.scheduler.resource_governor import (
    effective_priority_value,
    get_retry_cooldown_seconds,
    next_check_interval_seconds,
    priority_value,
    should_cooldown_failed_job,
)
from printer_v1.sources.governor import can_request_source


ACTIVE_STATUS_VALUES = tuple(status.value for status in ACTIVE_JOB_STATUSES)
_SCHEDULER_OBSERVER: ContextVar[object | None] = ContextVar(
    "printer_v1_scheduler_operation_observer", default=None
)


def set_scheduler_operation_observer(observer: object | None) -> Token:
    return _SCHEDULER_OBSERVER.set(observer)


def reset_scheduler_operation_observer(token: Token) -> None:
    _SCHEDULER_OBSERVER.reset(token)


def _observe(boundary: str, **evidence: object) -> None:
    observer = _SCHEDULER_OBSERVER.get()
    if observer is not None:
        observer({"boundary": boundary, **evidence})  # type: ignore[operator]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


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


def normalize_target_id(target_id: int | None) -> int:
    return -1 if target_id is None else target_id


def validate_source_backing(
    source_name: str | None,
    source_request_kind: str | None,
    recent_request_count: int = 0,
) -> LockResult | None:
    if source_name is None and source_request_kind is None:
        return None
    if source_name is None or source_request_kind is None:
        return LockResult.SOURCE_NOT_ALLOWED
    decision = can_request_source(source_name, source_request_kind, recent_request_count)
    return None if decision.allowed else LockResult.SOURCE_NOT_ALLOWED


def has_active_duplicate_job(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    job_name: str,
    job_kind: JobKind | str,
    target_table: str | None = None,
    target_id: int | None = None,
) -> bool:
    kind = JobKind(job_kind)
    with connect(db_or_connection) as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM printer_scheduler_jobs
            WHERE job_name = ?
              AND job_kind = ?
              AND COALESCE(target_table, '') = COALESCE(?, '')
              AND COALESCE(target_id, -1) = ?
              AND status IN (?, ?, ?)
            LIMIT 1
            """,
            (
                job_name,
                kind.value,
                target_table,
                normalize_target_id(target_id),
                *ACTIVE_STATUS_VALUES,
            ),
        ).fetchone()
    return row is not None


def enqueue_job(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    job_name: str,
    job_kind: JobKind | str,
    target_table: str | None = None,
    target_id: int | None = None,
    scheduled_for: datetime | None = None,
    source_name: str | None = None,
    source_request_kind: str | None = None,
    recent_request_count: int = 0,
) -> tuple[LockResult, int | None]:
    source_result = validate_source_backing(
        source_name, source_request_kind, recent_request_count
    )
    if source_result is not None:
        return source_result, None

    kind = JobKind(job_kind)
    due_at = scheduled_for or utc_now()
    if has_active_duplicate_job(
        db_or_connection,
        job_name=job_name,
        job_kind=kind,
        target_table=target_table,
        target_id=target_id,
    ):
        return LockResult.DUPLICATE_ACTIVE_JOB, None

    with connect(db_or_connection) as connection:
        cursor = connection.execute(
            """
            INSERT INTO printer_scheduler_jobs (
                job_name,
                job_kind,
                target_table,
                target_id,
                priority,
                status,
                scheduled_for
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_name,
                kind.value,
                target_table,
                target_id,
                priority_value(kind),
                JobStatus.PENDING.value,
                to_timestamp(due_at),
            ),
        )
        job_id = int(cursor.lastrowid)
        _observe(
            "SCHEDULER_ENQUEUE",
            scheduler_job_id=job_id,
            job_name=job_name,
            job_kind=kind.value,
            target_table=target_table,
            target_id=target_id,
        )
        return LockResult.ACQUIRED, job_id


def list_due_jobs(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    now: datetime | None = None,
    limit: int | None = None,
) -> list[sqlite3.Row]:
    current_time = now or utc_now()
    query = """
        SELECT *
        FROM printer_scheduler_jobs
        WHERE status IN (?, ?)
          AND scheduled_for <= ?
        ORDER BY priority ASC, scheduled_for ASC, created_at ASC, id ASC
    """
    params: list[object] = [
        JobStatus.PENDING.value,
        JobStatus.COOLDOWN.value,
        to_timestamp(current_time),
    ]
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    with connect(db_or_connection) as connection:
        return connection.execute(query, params).fetchall()


def select_next_jobs(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    now: datetime | None = None,
    limit: int = 1,
) -> list[sqlite3.Row]:
    current_time = now or utc_now()
    due_jobs = list_due_jobs(db_or_connection, now=current_time)
    sorted_jobs = sorted(
        due_jobs,
        key=lambda row: (
            effective_priority_value(
                row["job_kind"], parse_timestamp(row["scheduled_for"]), current_time
            ),
            row["scheduled_for"],
            row["created_at"],
            row["id"],
        ),
    )
    return sorted_jobs[:limit]


def claim_due_job(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    job_id: int,
    lock_owner: str,
    now: datetime | None = None,
) -> LockResult:
    current_time = now or utc_now()
    with connect(db_or_connection) as connection:
        row = connection.execute(
            "SELECT * FROM printer_scheduler_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return LockResult.NOT_FOUND
        if row["status"] == JobStatus.RUNNING.value or row["locked_at"] is not None:
            return LockResult.ALREADY_LOCKED
        if row["status"] not in {JobStatus.PENDING.value, JobStatus.COOLDOWN.value}:
            return LockResult.NOT_FOUND
        if row["scheduled_for"] > to_timestamp(current_time):
            return LockResult.NOT_DUE

        connection.execute(
            """
            UPDATE printer_scheduler_jobs
            SET status = ?,
                lock_owner = ?,
                locked_at = ?,
                started_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                JobStatus.RUNNING.value,
                lock_owner,
                to_timestamp(current_time),
                to_timestamp(current_time),
                to_timestamp(current_time),
                job_id,
            ),
        )
        _observe(
            "SCHEDULER_CLAIM",
            scheduler_job_id=int(job_id),
            lock_owner=lock_owner,
            claimed_at=to_timestamp(current_time),
        )
    return LockResult.ACQUIRED


def complete_job(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    job_id: int,
    now: datetime | None = None,
) -> None:
    current_time = now or utc_now()
    with connect(db_or_connection) as connection:
        connection.execute(
            """
            UPDATE printer_scheduler_jobs
            SET status = ?,
                finished_at = ?,
                locked_at = NULL,
                lock_owner = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (
                JobStatus.SUCCEEDED.value,
                to_timestamp(current_time),
                to_timestamp(current_time),
                job_id,
            ),
        )
        _observe(
            "SCHEDULER_TERMINAL",
            scheduler_job_id=int(job_id),
            terminal_state=JobStatus.SUCCEEDED.value,
            terminal_at=to_timestamp(current_time),
            first_terminal_cause=None,
        )


def skip_job(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    job_id: int,
    reason: str,
    now: datetime | None = None,
) -> None:
    """Terminalize one claimed Scheduler job as an honest non-execution."""
    current_time = now or utc_now()
    with connect(db_or_connection) as connection:
        row = connection.execute(
            "SELECT status,locked_at,lock_owner FROM printer_scheduler_jobs WHERE id=?",
            (int(job_id),),
        ).fetchone()
        if (
            row is None
            or str(row["status"]) != JobStatus.RUNNING.value
            or row["locked_at"] is None
            or not str(row["lock_owner"] or "")
        ):
            raise ValueError(f"Scheduler job is not running: {job_id}")
        connection.execute(
            """UPDATE printer_scheduler_jobs
               SET status=?,finished_at=?,locked_at=NULL,lock_owner=NULL,
                   last_error=?,updated_at=? WHERE id=?""",
            (
                JobStatus.SKIPPED.value,
                to_timestamp(current_time),
                str(reason),
                to_timestamp(current_time),
                int(job_id),
            ),
        )
        _observe(
            "SCHEDULER_TERMINAL",
            scheduler_job_id=int(job_id),
            terminal_state=JobStatus.SKIPPED.value,
            terminal_at=to_timestamp(current_time),
            first_terminal_cause=str(reason),
        )


def yield_job(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    job_id: int,
    scheduled_for: datetime,
    now: datetime | None = None,
) -> None:
    """Cooperatively release one running job for a later Scheduler claim."""
    current_time = now or utc_now()
    next_due = scheduled_for.astimezone(timezone.utc)
    with connect(db_or_connection) as connection:
        row = connection.execute(
            "SELECT status,locked_at,lock_owner FROM printer_scheduler_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        if (
            row is None
            or str(row["status"]) != JobStatus.RUNNING.value
            or row["locked_at"] is None
            or not str(row["lock_owner"] or "")
        ):
            raise ValueError(f"Scheduler job is not running: {job_id}")
        connection.execute(
            """
            UPDATE printer_scheduler_jobs
            SET status = ?,
                scheduled_for = ?,
                locked_at = NULL,
                lock_owner = NULL,
                started_at = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (
                JobStatus.PENDING.value,
                to_timestamp(next_due),
                to_timestamp(current_time),
                job_id,
            ),
        )
        _observe(
            "SCHEDULER_YIELD",
            scheduler_job_id=int(job_id),
            yielded_at=to_timestamp(current_time),
            scheduled_for=to_timestamp(next_due),
        )


def fail_job(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    job_id: int,
    error: str,
    now: datetime | None = None,
    max_retries: int = 3,
) -> JobStatus:
    current_time = now or utc_now()
    with connect(db_or_connection) as connection:
        row = connection.execute(
            "SELECT * FROM printer_scheduler_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Scheduler job not found: {job_id}")

        retry_count = int(row["retry_count"]) + 1
        kind = JobKind(row["job_kind"])
        if should_cooldown_failed_job(kind, retry_count, max_retries=max_retries):
            status = JobStatus.COOLDOWN
            scheduled_for = current_time + timedelta(
                seconds=get_retry_cooldown_seconds(kind, retry_count)
            )
            finished_at = None
        else:
            status = JobStatus.FAILED
            scheduled_for = parse_timestamp(row["scheduled_for"]) or current_time
            finished_at = current_time

        connection.execute(
            """
            UPDATE printer_scheduler_jobs
            SET status = ?,
                scheduled_for = ?,
                finished_at = ?,
                locked_at = NULL,
                lock_owner = NULL,
                retry_count = ?,
                last_error = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                status.value,
                to_timestamp(scheduled_for),
                to_timestamp(finished_at) if finished_at else None,
                retry_count,
                error,
                to_timestamp(current_time),
                job_id,
            ),
        )
    _observe(
        "SCHEDULER_TERMINAL",
        scheduler_job_id=int(job_id),
        terminal_state=status.value,
        terminal_at=(to_timestamp(finished_at) if finished_at else None),
        first_terminal_cause=error,
    )
    return status


def cancel_job(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    job_id: int,
    now: datetime | None = None,
) -> None:
    current_time = now or utc_now()
    with connect(db_or_connection) as connection:
        connection.execute(
            """
            UPDATE printer_scheduler_jobs
            SET status = ?,
                finished_at = ?,
                locked_at = NULL,
                lock_owner = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (
                JobStatus.CANCELLED.value,
                to_timestamp(current_time),
                to_timestamp(current_time),
                job_id,
            ),
        )
        _observe(
            "SCHEDULER_TERMINAL",
            scheduler_job_id=int(job_id),
            terminal_state=JobStatus.CANCELLED.value,
            terminal_at=to_timestamp(current_time),
            first_terminal_cause="CANCELLED_BY_OWNER",
        )


def release_stale_locks(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    now: datetime | None = None,
    lock_timeout_seconds: int = 300,
) -> int:
    current_time = now or utc_now()
    stale_before = current_time - timedelta(seconds=lock_timeout_seconds)
    with connect(db_or_connection) as connection:
        stale_job_ids = [
            int(row[0])
            for row in connection.execute(
                """SELECT id FROM printer_scheduler_jobs
                   WHERE status=? AND locked_at IS NOT NULL AND locked_at < ?""",
                (
                    JobStatus.RUNNING.value,
                    to_timestamp(stale_before),
                ),
            ).fetchall()
        ]
        cursor = connection.execute(
            """
            UPDATE printer_scheduler_jobs
            SET status = ?,
                locked_at = NULL,
                lock_owner = NULL,
                started_at = NULL,
                updated_at = ?
            WHERE status = ?
              AND locked_at IS NOT NULL
              AND locked_at < ?
            """,
            (
                JobStatus.PENDING.value,
                to_timestamp(current_time),
                JobStatus.RUNNING.value,
                to_timestamp(stale_before),
            ),
        )
        has_run_steps = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='printer_memory_factory_run_steps'"
        ).fetchone()
        if stale_job_ids and has_run_steps is not None:
            placeholders = ",".join("?" for _ in stale_job_ids)
            connection.execute(
                f"""UPDATE printer_memory_factory_run_steps
                    SET step_status='PENDING',started_at=NULL,updated_at=?
                    WHERE scheduler_job_id IN ({placeholders})
                      AND step_status='RUNNING'
                      AND step_kind IN (
                        'WINDOW_CLOSE_PRE_CLOSE_CRITICAL',
                        'CONTINUATION_CLOSE_PRE_CLOSE_CRITICAL',
                        'LONG_CONTINUATION_CLOSE_PRE_CLOSE_CRITICAL'
                      )""",
                (to_timestamp(current_time), *stale_job_ids),
            )
        return int(cursor.rowcount)


def calculate_next_check_at(
    job_kind: JobKind | str,
    *,
    now: datetime | None = None,
) -> datetime:
    current_time = now or utc_now()
    return current_time + timedelta(seconds=next_check_interval_seconds(job_kind))

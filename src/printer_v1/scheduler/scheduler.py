"""V2-9.8B compatibility adapter for bounded Scheduler failure diagnostics.

The exact pre-corrective Scheduler implementation is preserved byte-for-byte in
``_scheduler_base``. This adapter re-exports that surface and overrides only
``fail_job`` so one exact typed Cycle-2 pre-admission error may durably retain a
sanitized diagnostic envelope without changing the authoritative categorical
terminal cause.

No source, retry, priority, claim, cooldown, scheduling, or lifecycle policy is
changed here.
"""
from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime
import json
from pathlib import Path
import re
import sqlite3
from typing import Mapping

from printer_v1.scheduler import _scheduler_base as _base

# Preserve the complete established Scheduler surface for existing callers.
for _name in dir(_base):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_base, _name)


_JOB_FAILURE_DIAGNOSTICS: ContextVar[dict[int, tuple[str, str]]] = ContextVar(
    "printer_v1_scheduler_job_failure_diagnostics", default={}
)
_ALLOWED_DIAGNOSTIC_FIELDS = (
    "stage",
    "mint",
    "pool",
    "admission_authority",
    "nomination_source",
)
_PERSISTENCE_DIAGNOSTIC_FIELDS = frozenset(
    {
        "diagnostic_schema",
        "failure_code",
        "producer_code",
        "failure_category",
        "operation_phase",
        "exception_type",
        "reason_code",
    }
)
_PERSISTENCE_DIAGNOSTIC_SCHEMA = "PRE_ADMISSION_PERSISTENCE_DIAGNOSTIC_V1"
_PERSISTENCE_FAILURE_CODE = "LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED"
_PERSISTENCE_PRODUCERS = frozenset(
    {
        "RUNNING_ATTEMPT_FAILURE_TERMINALIZATION",
        "SOURCE_EVIDENCE_LINK_ARGUMENT",
        "SOURCE_EVIDENCE_LINK_INSERT",
        "FROZEN_EVIDENCE_PROJECTION",
        "FROZEN_LANE_CLASSIFICATION",
        "PAIR_SHAPE_VALIDATION",
        "FROZEN_LANE_FIELD_VALIDATION",
        "PAIR_ATTEMPT_RUNNING_PREREQUISITE",
        "PAIR_ITEM_INSERT",
        "PAIR_READY_TRANSITION",
        "PRE_ADMISSION_PERSISTENCE_UNKNOWN",
    }
)
_PERSISTENCE_CATEGORIES = frozenset(
    {
        "APPLICATION_VALIDATION",
        "PREREQUISITE_MISSING",
        "CONSTRAINT_OR_INTEGRITY",
        "SQLITE_BUSY_OR_LOCK",
        "SQLITE_IO_OR_OPERATIONAL",
        "UNKNOWN_PERSISTENCE_FAILURE",
    }
)
_PERSISTENCE_PHASES = frozenset(
    {
        "TERMINALIZATION",
        "SOURCE_LINK",
        "FROZEN_CARRIER",
        "PAIR_PRECHECK",
        "PAIR_ITEM_1",
        "PAIR_ITEM_2",
        "PAIR_READY",
        "UNKNOWN_PHASE",
    }
)
_EXCEPTION_TYPE_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,96}$")
_REASON_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


def _bounded_diagnostic_value(
    value: object | None, *, limit: int = 192
) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _normalize_diagnostic_code(value: object) -> str:
    raw = str(value or "").strip().upper()
    normalized = "".join(
        character if (character.isalnum() or character == "_") else "_"
        for character in raw
    )
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_") or "SCHEDULER_FAILURE"


def stage_job_failure_diagnostic(
    *,
    job_id: int,
    failure_code: str,
    context: Mapping[str, object | None],
) -> None:
    """Stage one sanitized diagnostic for an exact Scheduler job in this context.

    This carrier is non-authoritative. ``fail_job`` remains the sole durable
    Scheduler writer and the ordinary categorical ``error`` remains the observer
    terminal cause.
    """
    identity = int(job_id)
    if identity <= 0:
        raise ValueError("job_id must be positive")
    code = _normalize_diagnostic_code(failure_code)
    if "diagnostic_schema" in context:
        if (
            set(context) != _PERSISTENCE_DIAGNOSTIC_FIELDS
            or any(
                not isinstance(context[key], str)
                for key in _PERSISTENCE_DIAGNOSTIC_FIELDS
            )
        ):
            raise ValueError("pre-admission persistence diagnostic key set invalid")
        payload = {key: context[key] for key in _PERSISTENCE_DIAGNOSTIC_FIELDS}
        if (
            payload["diagnostic_schema"] != _PERSISTENCE_DIAGNOSTIC_SCHEMA
            or code != _PERSISTENCE_FAILURE_CODE
            or payload["failure_code"] != code
            or payload["producer_code"] not in _PERSISTENCE_PRODUCERS
            or payload["failure_category"] not in _PERSISTENCE_CATEGORIES
            or payload["operation_phase"] not in _PERSISTENCE_PHASES
            or _EXCEPTION_TYPE_PATTERN.fullmatch(payload["exception_type"]) is None
            or _REASON_CODE_PATTERN.fullmatch(payload["reason_code"]) is None
        ):
            raise ValueError("pre-admission persistence diagnostic invalid")
    else:
        payload = {"failure_code": code}
        for key in _ALLOWED_DIAGNOSTIC_FIELDS:
            bounded = _bounded_diagnostic_value(context.get(key))
            if bounded is not None:
                payload[key] = bounded
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if len(canonical) > 1536:
        raise ValueError("scheduler failure diagnostic exceeds bound")
    staged = dict(_JOB_FAILURE_DIAGNOSTICS.get())
    if identity not in staged:
        staged[identity] = (code, canonical)
    _JOB_FAILURE_DIAGNOSTICS.set(staged)


def discard_job_failure_diagnostic(*, job_id: int) -> None:
    staged = dict(_JOB_FAILURE_DIAGNOSTICS.get())
    staged.pop(int(job_id), None)
    _JOB_FAILURE_DIAGNOSTICS.set(staged)


def _consume_job_failure_diagnostic(*, job_id: int, error: str) -> str:
    staged = dict(_JOB_FAILURE_DIAGNOSTICS.get())
    entry = staged.pop(int(job_id), None)
    _JOB_FAILURE_DIAGNOSTICS.set(staged)
    if entry is None:
        return str(error)
    code, canonical = entry
    terminal = str(error)
    if terminal == code or terminal.endswith(f"_{code}"):
        return canonical
    return terminal


def fail_job(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    job_id: int,
    error: str,
    now: datetime | None = None,
    max_retries: int = 3,
):
    """Run the established failure transition with optional safe diagnostics.

    The database ``last_error`` may carry the matching staged diagnostic envelope;
    the Scheduler observer always receives the original categorical ``error``.
    Without a matching staged diagnostic this is behaviorally identical to the
    preserved base implementation.
    """
    current_time = now or _base.utc_now()
    persisted_error = _consume_job_failure_diagnostic(
        job_id=job_id, error=str(error)
    )
    with _base.connect(db_or_connection) as connection:
        row = connection.execute(
            "SELECT * FROM printer_scheduler_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Scheduler job not found: {job_id}")

        retry_count = int(row["retry_count"]) + 1
        kind = _base.JobKind(row["job_kind"])
        if _base.should_cooldown_failed_job(
            kind, retry_count, max_retries=max_retries
        ):
            status = _base.JobStatus.COOLDOWN
            scheduled_for = current_time + _base.timedelta(
                seconds=_base.get_retry_cooldown_seconds(kind, retry_count)
            )
            finished_at = None
        else:
            status = _base.JobStatus.FAILED
            scheduled_for = (
                _base.parse_timestamp(row["scheduled_for"]) or current_time
            )
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
                _base.to_timestamp(scheduled_for),
                _base.to_timestamp(finished_at) if finished_at else None,
                retry_count,
                persisted_error,
                _base.to_timestamp(current_time),
                job_id,
            ),
        )
    _base._observe(
        "SCHEDULER_TERMINAL",
        scheduler_job_id=int(job_id),
        terminal_state=status.value,
        terminal_at=(
            _base.to_timestamp(finished_at) if finished_at else None
        ),
        first_terminal_cause=str(error),
    )
    return status


def complete_job(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    job_id: int,
    now: datetime | None = None,
) -> None:
    discard_job_failure_diagnostic(job_id=job_id)
    _base.complete_job(db_or_connection, job_id=job_id, now=now)


def cancel_job(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    job_id: int,
    now: datetime | None = None,
) -> None:
    discard_job_failure_diagnostic(job_id=job_id)
    _base.cancel_job(db_or_connection, job_id=job_id, now=now)


# Public overrides after the compatibility re-export above.
globals()["fail_job"] = fail_job
globals()["stage_job_failure_diagnostic"] = stage_job_failure_diagnostic

"""V2-9.7E.47 A2 — discovery work / Scheduler job terminal parity.

Whenever a ``printer_discovery_work`` row becomes terminal, the Scheduler job
that owns it must become terminal too, and only through the committed Central
Scheduler owner (``complete_job`` / ``fail_job`` / ``cancel_job``). No status is
written by an unowned ``UPDATE printer_scheduler_jobs``.

Root cause repaired (V2-9.7E.46 §10.2): the combined discovery executor
terminalised its work rows but never transitioned the ``DISCOVERY_REFRESH`` jobs
it had enqueued, so eight jobs stayed ``PENDING`` after a governed terminal while
their work rows were ``SUCCEEDED``. The factory's discovery cleanup could not
compensate because it was called with the *handoff* batch id
(``origin-activated:<cycle>``) rather than the executor's discovery batch id
(``discovery-batch:<campaign>:<run>:<cycle>``), so it matched zero rows.

Mapping (frozen):

* successful work  -> ``SUCCEEDED``
* failed work      -> ``FAILED``
* abandoned, superseded or terminally unnecessary work -> ``CANCELLED``
"""

from __future__ import annotations

import sqlite3
from typing import Any

from printer_v1.scheduler.contracts import ACTIVE_JOB_STATUSES
from printer_v1.scheduler.scheduler import cancel_job, complete_job, fail_job


ACTIVE_JOB_STATUS_VALUES = tuple(status.value for status in ACTIVE_JOB_STATUSES)

#: Terminal ``printer_discovery_work.work_state`` -> Scheduler terminal action.
WORK_STATE_TO_JOB_ACTION = {
    "SUCCEEDED": "COMPLETE",
    "COMPLETED": "COMPLETE",
    "FAILED": "FAIL",
    "CANCELLED": "CANCEL",
    "SKIPPED": "CANCEL",
    "ABANDONED": "CANCEL",
    "SUPERSEDED": "CANCEL",
}


class DiscoverySchedulerParityError(RuntimeError):
    """Fail-closed discovery/Scheduler parity fault."""


def _job_row(connection: sqlite3.Connection, job_id: int) -> dict[str, Any] | None:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT id, status, locked_at, lock_owner FROM printer_scheduler_jobs WHERE id = ?",
        (job_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def terminalize_scheduler_job_for_work(
    connection: sqlite3.Connection,
    *,
    job_id: int,
    work_state: str,
    cause: str,
) -> str | None:
    """Drive one Scheduler job terminal to match its discovery work row.

    Returns the applied Scheduler action (``COMPLETE`` / ``FAIL`` / ``CANCEL``),
    or ``None`` when the job is absent or already terminal. Already-terminal
    jobs are never rewritten, so the first terminal cause stays immutable.
    """
    action = WORK_STATE_TO_JOB_ACTION.get(str(work_state).upper())
    if action is None:
        raise DiscoverySchedulerParityError(
            f"unsupported terminal discovery work state: {work_state!r}"
        )
    row = _job_row(connection, job_id)
    if row is None:
        return None
    if str(row["status"]) not in ACTIVE_JOB_STATUS_VALUES:
        # Already terminal (SUCCEEDED / FAILED / CANCELLED / SKIPPED).
        return None
    if action == "COMPLETE":
        complete_job(connection, job_id=job_id)
    elif action == "FAIL":
        fail_job(connection, job_id=job_id, error=str(cause), max_retries=0)
    else:
        cancel_job(connection, job_id=job_id)
    return action


def reconcile_discovery_work_jobs(
    connection: sqlite3.Connection,
    *,
    discovery_batch_id: str | None = None,
    campaign_id: str | None = None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    abandoned_cause: str = "DISCOVERY_WORK_ABANDONED_AT_TERMINAL",
) -> dict[str, Any]:
    """Bring every discovery work row and its Scheduler job to terminal parity.

    Scope is any combination of batch / campaign / run / cycle; at least one
    must be supplied. Work rows that are still active at a governed terminal are
    themselves cancelled first (abandoned work), then every linked job is driven
    terminal through the Scheduler owner.
    """
    connection.row_factory = sqlite3.Row
    if not _table_exists(connection, "printer_discovery_work"):
        return {
            "scope": {},
            "work_rows": 0,
            "cancelled_active_work": 0,
            "job_actions": {},
            "terminal_work_with_active_job": 0,
        }
    clauses: list[str] = []
    joined_clauses: list[str] = []
    params: list[Any] = []
    scope: dict[str, str] = {}
    for column, value in (
        ("discovery_batch_id", discovery_batch_id),
        ("campaign_id", campaign_id),
        ("run_id", run_id),
        ("cycle_id", cycle_id),
    ):
        if value:
            clauses.append(f"{column} = ?")
            joined_clauses.append(f"w.{column} = ?")
            params.append(value)
            scope[column] = str(value)
    if not clauses:
        raise DiscoverySchedulerParityError(
            "discovery work reconciliation requires an explicit scope"
        )
    where = " AND ".join(clauses)
    joined_where = " AND ".join(joined_clauses)
    now = _utc_now()
    active = connection.execute(
        f"""
        SELECT discovery_work_id FROM printer_discovery_work
        WHERE {where} AND work_state IN ('PENDING', 'RUNNING', 'COOLDOWN')
        """,
        params,
    ).fetchall()
    for row in active:
        connection.execute(
            """
            UPDATE printer_discovery_work
            SET work_state = 'CANCELLED',
                first_terminal_cause = COALESCE(first_terminal_cause, ?),
                terminal_at = COALESCE(terminal_at, ?),
                updated_at = ?
            WHERE discovery_work_id = ?
            """,
            (abandoned_cause, now, now, str(row["discovery_work_id"])),
        )
    rows = connection.execute(
        f"""
        SELECT discovery_work_id, scheduler_job_id, work_state, first_terminal_cause
        FROM printer_discovery_work
        WHERE {where}
        ORDER BY discovery_work_id
        """,
        params,
    ).fetchall()
    actions: dict[str, int] = {}
    for row in rows:
        if row["scheduler_job_id"] is None:
            continue
        applied = terminalize_scheduler_job_for_work(
            connection,
            job_id=int(row["scheduler_job_id"]),
            work_state=str(row["work_state"]),
            cause=str(row["first_terminal_cause"] or abandoned_cause),
        )
        if applied:
            actions[applied] = actions.get(applied, 0) + 1
    remaining = int(
        connection.execute(
            f"""
            SELECT COUNT(*)
            FROM printer_discovery_work AS w
            JOIN printer_scheduler_jobs AS j ON j.id = w.scheduler_job_id
            WHERE {joined_where}
              AND w.work_state NOT IN ('PENDING', 'RUNNING', 'COOLDOWN')
              AND j.status IN ('PENDING', 'RUNNING', 'COOLDOWN')
            """,
            params,
        ).fetchone()[0]
    )
    return {
        "scope": scope,
        "work_rows": len(rows),
        "cancelled_active_work": len(active),
        "job_actions": actions,
        "terminal_work_with_active_job": remaining,
    }


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "ACTIVE_JOB_STATUS_VALUES",
    "DiscoverySchedulerParityError",
    "WORK_STATE_TO_JOB_ACTION",
    "reconcile_discovery_work_jobs",
    "terminalize_scheduler_job_for_work",
]

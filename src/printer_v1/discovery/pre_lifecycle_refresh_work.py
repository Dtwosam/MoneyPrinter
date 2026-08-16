"""Dedicated persistence for Scheduler-owned pre-lifecycle discovery refresh work.

This is a persistence helper, not a discovery engine. It records one claimed
refresh ordinal at a time while preserving all historical terminal rows.
"""
from __future__ import annotations

import sqlite3
from typing import Any

REFRESH_WORK_TABLE = "printer_pre_lifecycle_discovery_refresh_work"
ACTIVE_REFRESH_WORK_STATES = ("RUNNING",)
TERMINAL_REFRESH_WORK_STATES = ("SUCCEEDED", "FAILED", "CANCELLED")


class PreLifecycleRefreshWorkError(RuntimeError):
    """Fail-closed refresh-work persistence fault."""


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def insert_refresh_work(
    connection: sqlite3.Connection,
    *,
    refresh_work_id: str,
    wait_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    supervision_id: str,
    scheduler_job_id: int,
    refresh_ordinal: int,
    work_deadline_at: str,
    now: str,
) -> None:
    if not _table_exists(connection, REFRESH_WORK_TABLE):
        raise PreLifecycleRefreshWorkError("PRE_LIFECYCLE_REFRESH_WORK_TABLE_MISSING")
    if int(refresh_ordinal) <= 0:
        raise PreLifecycleRefreshWorkError("INVALID_PRE_LIFECYCLE_REFRESH_ORDINAL")
    parent = connection.execute(
        """SELECT campaign_id,run_id,cycle_id,supervision_id,scheduler_job_id,
                  refresh_ordinal,wait_state
             FROM printer_pre_lifecycle_discovery_refresh_waits WHERE wait_id=?""",
        (wait_id,),
    ).fetchone()
    if parent is None:
        raise PreLifecycleRefreshWorkError("PRE_LIFECYCLE_REFRESH_WAIT_MISSING")
    values = tuple(parent)
    expected = (
        campaign_id,
        run_id,
        cycle_id,
        supervision_id,
        int(scheduler_job_id),
        int(refresh_ordinal),
        "CLAIMED",
    )
    if values != expected:
        raise PreLifecycleRefreshWorkError(
            "PRE_LIFECYCLE_REFRESH_WORK_PARENT_NOT_EXACT_CLAIM"
        )
    try:
        connection.execute(
            f"""INSERT INTO {REFRESH_WORK_TABLE}(
                refresh_work_id,wait_id,campaign_id,run_id,cycle_id,supervision_id,
                scheduler_job_id,refresh_ordinal,work_state,work_deadline_at,
                created_at,updated_at,terminal_at,first_terminal_cause
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                refresh_work_id,
                wait_id,
                campaign_id,
                run_id,
                cycle_id,
                supervision_id,
                int(scheduler_job_id),
                int(refresh_ordinal),
                "RUNNING",
                work_deadline_at,
                now,
                now,
                None,
                None,
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise PreLifecycleRefreshWorkError(
            "PRE_LIFECYCLE_REFRESH_WORK_OWNERSHIP_CONFLICT"
        ) from exc


def active_refresh_work(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
) -> list[dict[str, Any]]:
    if not _table_exists(connection, REFRESH_WORK_TABLE):
        return []
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        f"""SELECT * FROM {REFRESH_WORK_TABLE}
             WHERE campaign_id=? AND run_id=? AND cycle_id=? AND work_state='RUNNING'
             ORDER BY refresh_ordinal""",
        (campaign_id, run_id, cycle_id),
    ).fetchall()
    return [dict(row) for row in rows]


def terminalize_refresh_work(
    connection: sqlite3.Connection,
    *,
    refresh_work_id: str,
    work_state: str,
    first_terminal_cause: str,
    now: str,
) -> None:
    if work_state not in TERMINAL_REFRESH_WORK_STATES:
        raise PreLifecycleRefreshWorkError(
            "INVALID_PRE_LIFECYCLE_REFRESH_TERMINAL_STATE"
        )
    if not str(first_terminal_cause).strip():
        raise PreLifecycleRefreshWorkError(
            "MISSING_PRE_LIFECYCLE_REFRESH_TERMINAL_CAUSE"
        )
    row = connection.execute(
        f"SELECT work_state,first_terminal_cause FROM {REFRESH_WORK_TABLE} "
        "WHERE refresh_work_id=?",
        (refresh_work_id,),
    ).fetchone()
    if row is None:
        raise PreLifecycleRefreshWorkError("PRE_LIFECYCLE_REFRESH_WORK_MISSING")
    current = str(row[0])
    if current != "RUNNING":
        if current == work_state and str(row[1] or "") == str(first_terminal_cause):
            return
        raise PreLifecycleRefreshWorkError(
            "PRE_LIFECYCLE_REFRESH_WORK_ALREADY_TERMINAL"
        )
    connection.execute(
        f"""UPDATE {REFRESH_WORK_TABLE}
              SET work_state=?, first_terminal_cause=?, terminal_at=?, updated_at=?
            WHERE refresh_work_id=? AND work_state='RUNNING'""",
        (work_state, first_terminal_cause, now, now, refresh_work_id),
    )


__all__ = [
    "ACTIVE_REFRESH_WORK_STATES",
    "PreLifecycleRefreshWorkError",
    "REFRESH_WORK_TABLE",
    "TERMINAL_REFRESH_WORK_STATES",
    "active_refresh_work",
    "insert_refresh_work",
    "terminalize_refresh_work",
]

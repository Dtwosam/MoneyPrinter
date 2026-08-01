"""V2-9.7E.47 A3 — exact campaign-scoped active-work accounting.

The pre-repair terminal report exposed only ``running_jobs_after_stop``, computed
as "jobs joined through this run's factory run-steps whose status is ``RUNNING``
or which hold a lock". That interpretation is narrow in two independent ways:

* it never sees a ``PENDING`` or ``COOLDOWN`` job, and
* it never sees a job that is not reachable through a factory run-step —
  which is exactly the ``DISCOVERY_REFRESH`` job class that V2-9.7E.46 left
  ``PENDING`` after a governed terminal (§10.2).

This module replaces that interpretation with campaign-scoped accounting over
every job attributable to the campaign / run / cycle, plus the work rows that
own them. A terminal campaign requires zero active jobs and zero active work
rows. It performs no source call, no Scheduler mutation and no write.
"""

from __future__ import annotations

import sqlite3
from typing import Any


ACTIVE_JOB_STATUSES = ("PENDING", "RUNNING", "COOLDOWN")
ACTIVE_WORK_STATES = ("PENDING", "RUNNING", "COOLDOWN")


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )


def _job_ids(connection: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> set[int]:
    return {int(row[0]) for row in connection.execute(sql, params).fetchall()}


def _job_has_exact_scope_owner(
    connection: sqlite3.Connection,
    *,
    scheduler_job_id: int,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
) -> bool:
    """Whether one durable owner binds a job to all three scope identities.

    A factory run-step alone cannot establish ``cycle_id`` and is therefore not
    an exact campaign owner.  Exact ownership comes from the rows that durably
    carry campaign, run, cycle, and Scheduler-job identity together.
    """
    sources = (
        ("printer_discovery_work", "scheduler_job_id"),
        (
            "printer_memory_factory_campaign_scheduler_work",
            "scheduler_job_id",
        ),
        (
            "printer_discovery_selected_item_links",
            "first_window_15m_scheduler_job_id",
        ),
    )
    for table, job_column in sources:
        if not _table_exists(connection, table):
            continue
        row = connection.execute(
            f"SELECT 1 FROM {table} WHERE {job_column}=? "
            "AND campaign_id=? AND run_id=? AND cycle_id=? LIMIT 1",
            (scheduler_job_id, campaign_id, run_id, cycle_id),
        ).fetchone()
        if row is not None:
            return True
    return False


def campaign_scoped_job_ids(
    connection: sqlite3.Connection,
    *,
    factory_run_id: str | None = None,
    campaign_id: str | None = None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    exact_scope: bool = False,
) -> dict[str, set[int]]:
    """Every Scheduler job attributable to this campaign, grouped by owner.

    The historical compatibility mode (``exact_scope=False``) retains its broad
    campaign/run/cycle ``OR`` attribution.  Cleanup capture uses the explicit
    read-only exact mode: every broad candidate is filtered through one complete
    durable-owner resolver requiring the same campaign, run, *and* cycle.
    """
    connection.row_factory = sqlite3.Row
    if exact_scope and not (campaign_id and run_id and cycle_id):
        raise ValueError(
            "exact campaign Scheduler scope requires campaign_id, run_id, and cycle_id"
        )
    groups: dict[str, set[int]] = {
        "factory_run_step_jobs": set(),
        "discovery_jobs": set(),
        "campaign_scheduler_work_jobs": set(),
    }
    if factory_run_id and _table_exists(connection, "printer_memory_factory_run_steps"):
        groups["factory_run_step_jobs"] = _job_ids(
            connection,
            "SELECT scheduler_job_id FROM printer_memory_factory_run_steps "
            "WHERE run_id = ? AND scheduler_job_id IS NOT NULL",
            (factory_run_id,),
        )
    if _table_exists(connection, "printer_discovery_work"):
        clauses: list[str] = []
        params: list[Any] = []
        for column, value in (
            ("campaign_id", campaign_id),
            ("run_id", run_id),
            ("cycle_id", cycle_id),
        ):
            if value:
                clauses.append(f"{column} = ?")
                params.append(value)
        if clauses:
            groups["discovery_jobs"] = _job_ids(
                connection,
                "SELECT scheduler_job_id FROM printer_discovery_work "
                f"WHERE ({' OR '.join(clauses)}) AND scheduler_job_id IS NOT NULL",
                tuple(params),
            )
    if _table_exists(
        connection, "printer_memory_factory_campaign_scheduler_work"
    ) and (campaign_id or run_id or cycle_id):
        clauses = []
        params = []
        for column, value in (
            ("campaign_id", campaign_id),
            ("run_id", run_id),
            ("cycle_id", cycle_id),
        ):
            if value:
                clauses.append(f"{column} = ?")
                params.append(value)
        columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(printer_memory_factory_campaign_scheduler_work)"
            ).fetchall()
        }
        if "scheduler_job_id" in columns:
            groups["campaign_scheduler_work_jobs"] = _job_ids(
                connection,
                "SELECT scheduler_job_id FROM "
                "printer_memory_factory_campaign_scheduler_work "
                f"WHERE ({' OR '.join(clauses)}) AND scheduler_job_id IS NOT NULL",
                tuple(params),
            )
    if exact_scope and _table_exists(
        connection, "printer_discovery_selected_item_links"
    ):
        groups["first_15m_handoff_jobs"] = _job_ids(
            connection,
            "SELECT first_window_15m_scheduler_job_id "
            "FROM printer_discovery_selected_item_links "
            "WHERE campaign_id=? AND run_id=? AND cycle_id=? "
            "AND first_window_15m_scheduler_job_id IS NOT NULL",
            (campaign_id, run_id, cycle_id),
        )
    if exact_scope:
        for name, job_ids in groups.items():
            groups[name] = {
                job_id
                for job_id in job_ids
                if _job_has_exact_scope_owner(
                    connection,
                    scheduler_job_id=job_id,
                    campaign_id=str(campaign_id),
                    run_id=str(run_id),
                    cycle_id=str(cycle_id),
                )
            }
    return groups


def campaign_active_work_report(
    connection: sqlite3.Connection,
    *,
    factory_run_id: str | None = None,
    campaign_id: str | None = None,
    run_id: str | None = None,
    cycle_id: str | None = None,
) -> dict[str, Any]:
    """Exact active-job / active-work report for one campaign.

    ``active_jobs`` counts every attributable Scheduler job that is ``PENDING``,
    ``RUNNING`` or ``COOLDOWN``, or that still holds a lock (``locked_at`` or
    ``lock_owner`` non-null), regardless of which owner enqueued it.
    """
    connection.row_factory = sqlite3.Row
    groups = campaign_scoped_job_ids(
        connection,
        factory_run_id=factory_run_id,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
    )
    every_id = set().union(*groups.values()) if groups else set()
    by_status: dict[str, int] = {}
    locked: list[int] = []
    active: list[dict[str, Any]] = []
    if every_id and _table_exists(connection, "printer_scheduler_jobs"):
        placeholders = ",".join("?" * len(every_id))
        rows = connection.execute(
            f"SELECT id, job_name, job_kind, status, locked_at, lock_owner "
            f"FROM printer_scheduler_jobs WHERE id IN ({placeholders}) ORDER BY id",
            tuple(sorted(every_id)),
        ).fetchall()
        for row in rows:
            status = str(row["status"])
            by_status[status] = by_status.get(status, 0) + 1
            is_locked = row["locked_at"] is not None or row["lock_owner"] is not None
            if is_locked:
                locked.append(int(row["id"]))
            if status in ACTIVE_JOB_STATUSES or is_locked:
                active.append(
                    {
                        "job_id": int(row["id"]),
                        "job_name": row["job_name"],
                        "job_kind": row["job_kind"],
                        "status": status,
                        "locked": is_locked,
                    }
                )

    active_work_rows: list[dict[str, Any]] = []
    terminal_work_with_active_job = 0
    if _table_exists(connection, "printer_discovery_work") and (
        campaign_id or run_id or cycle_id
    ):
        clauses: list[str] = []
        params: list[Any] = []
        for column, value in (
            ("campaign_id", campaign_id),
            ("run_id", run_id),
            ("cycle_id", cycle_id),
        ):
            if value:
                clauses.append(f"w.{column} = ?")
                params.append(value)
        scope = " OR ".join(clauses)
        active_work_rows = [
            {
                "discovery_work_id": str(row["discovery_work_id"]),
                "work_type": str(row["work_type"]),
                "work_state": str(row["work_state"]),
            }
            for row in connection.execute(
                f"""
                SELECT discovery_work_id, work_type, work_state
                FROM printer_discovery_work AS w
                WHERE ({scope}) AND w.work_state IN
                      ({','.join('?' * len(ACTIVE_WORK_STATES))})
                ORDER BY discovery_work_id
                """,
                (*params, *ACTIVE_WORK_STATES),
            ).fetchall()
        ]
        terminal_work_with_active_job = int(
            connection.execute(
                f"""
                SELECT COUNT(*)
                FROM printer_discovery_work AS w
                JOIN printer_scheduler_jobs AS j ON j.id = w.scheduler_job_id
                WHERE ({scope})
                  AND w.work_state NOT IN
                      ({','.join('?' * len(ACTIVE_WORK_STATES))})
                  AND j.status IN
                      ({','.join('?' * len(ACTIVE_JOB_STATUSES))})
                """,
                (*params, *ACTIVE_WORK_STATES, *ACTIVE_JOB_STATUSES),
            ).fetchone()[0]
        )

    pending_run_steps = 0
    if factory_run_id and _table_exists(
        connection, "printer_memory_factory_run_steps"
    ):
        pending_run_steps = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
                "WHERE run_id = ? AND step_status IN ('PENDING','RUNNING')",
                (factory_run_id,),
            ).fetchone()[0]
        )

    return {
        "scope": {
            "factory_run_id": factory_run_id,
            "campaign_id": campaign_id,
            "run_id": run_id,
            "cycle_id": cycle_id,
        },
        "attributable_job_counts": {
            name: len(ids) for name, ids in groups.items()
        },
        "jobs_by_status": by_status,
        "locked_job_ids": sorted(locked),
        "active_jobs": len(active),
        "active_job_details": active,
        "active_work_rows": len(active_work_rows),
        "active_work_details": active_work_rows,
        "terminal_work_with_active_job": terminal_work_with_active_job,
        "pending_or_running_run_steps": pending_run_steps,
        "clean_terminal": (
            not active
            and not active_work_rows
            and terminal_work_with_active_job == 0
            and pending_run_steps == 0
        ),
    }


__all__ = [
    "ACTIVE_JOB_STATUSES",
    "ACTIVE_WORK_STATES",
    "campaign_active_work_report",
    "campaign_scoped_job_ids",
]

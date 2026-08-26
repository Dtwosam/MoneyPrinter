from __future__ import annotations

import sqlite3

import pytest

from printer_v1.operator_cli.campaign_ownership import (
    CampaignOwnershipError,
    transition_state,
)

NOW = "2026-08-25T15:00:00+00:00"


def _connection(*, scheduler_status: str, locked: bool = False, started: bool = False) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE printer_memory_factory_campaign_scheduler_work(
            scheduler_work_id TEXT PRIMARY KEY,
            work_state TEXT NOT NULL,
            scheduler_job_id INTEGER,
            first_terminal_cause TEXT,
            terminal_at TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE printer_scheduler_jobs(
            id INTEGER PRIMARY KEY,
            status TEXT NOT NULL,
            locked_at TEXT,
            lock_owner TEXT,
            started_at TEXT
        )
        """
    )
    connection.execute(
        """
        INSERT INTO printer_memory_factory_campaign_scheduler_work(
            scheduler_work_id, work_state, scheduler_job_id,
            first_terminal_cause, terminal_at, updated_at
        ) VALUES ('work-1', 'RUNNING', 7, NULL, NULL, ?)
        """,
        (NOW,),
    )
    connection.execute(
        """
        INSERT INTO printer_scheduler_jobs(id,status,locked_at,lock_owner,started_at)
        VALUES (7,?,?,?,?)
        """,
        (
            scheduler_status,
            NOW if locked else None,
            "owner-a" if locked else None,
            NOW if started else None,
        ),
    )
    connection.commit()
    return connection


def test_released_canonical_pending_scheduler_allows_running_projection_to_return_pending() -> None:
    connection = _connection(scheduler_status="PENDING")
    try:
        result = transition_state(
            connection,
            record_kind="scheduler_work",
            identity="work-1",
            expected_state="RUNNING",
            new_state="PENDING",
            now=NOW,
        )
    finally:
        connection.close()

    assert result.previous_state == "RUNNING"
    assert result.current_state == "PENDING"
    assert result.changed is True


def test_scheduler_projection_cannot_return_pending_while_canonical_job_is_running() -> None:
    connection = _connection(scheduler_status="RUNNING", locked=True, started=True)
    try:
        with pytest.raises(CampaignOwnershipError, match="invalid scheduler_work transition"):
            transition_state(
                connection,
                record_kind="scheduler_work",
                identity="work-1",
                expected_state="RUNNING",
                new_state="PENDING",
                now=NOW,
            )
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("locked", "started"),
    ((True, False), (False, True), (True, True)),
)
def test_scheduler_projection_rejects_pending_canonical_job_that_is_not_fully_released(
    locked: bool, started: bool
) -> None:
    connection = _connection(scheduler_status="PENDING", locked=locked, started=started)
    try:
        with pytest.raises(CampaignOwnershipError, match="invalid scheduler_work transition"):
            transition_state(
                connection,
                record_kind="scheduler_work",
                identity="work-1",
                expected_state="RUNNING",
                new_state="PENDING",
                now=NOW,
            )
    finally:
        connection.close()


def test_window_lifecycle_projection_syncs_real_scheduler_yield_without_state_drift() -> None:
    from printer_v1.operator_cli.campaign_ownership import project_campaign_scheduler_job

    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            """
            CREATE TABLE printer_scheduler_jobs(
                id INTEGER PRIMARY KEY,
                status TEXT NOT NULL,
                finished_at TEXT,
                last_error TEXT,
                locked_at TEXT,
                lock_owner TEXT,
                started_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE printer_memory_factory_campaign_scheduler_work(
                scheduler_work_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                cycle_id TEXT NOT NULL,
                token_slot_id TEXT,
                window_id TEXT,
                work_intent TEXT NOT NULL,
                deadline_at TEXT NOT NULL,
                work_state TEXT NOT NULL,
                scheduler_job_id INTEGER NOT NULL,
                source_request_id INTEGER,
                source_response_id INTEGER,
                source_failure_id INTEGER,
                ownership_contract_version TEXT NOT NULL,
                stage_id TEXT NOT NULL,
                work_scope TEXT NOT NULL,
                target_category TEXT NOT NULL,
                target_identity TEXT NOT NULL,
                factory_run_id TEXT,
                first_terminal_cause TEXT,
                terminal_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE printer_memory_factory_campaign_windows(
                window_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                cycle_id TEXT NOT NULL,
                token_slot_id TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE printer_memory_factory_campaign_runs(
                run_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                authoritative_run_id TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE printer_memory_factory_run_steps(
                id INTEGER PRIMARY KEY,
                run_id TEXT NOT NULL,
                scheduler_job_id INTEGER
            )
            """
        )
        connection.execute(
            """
            INSERT INTO printer_scheduler_jobs(
                id,status,finished_at,last_error,locked_at,lock_owner,started_at
            ) VALUES (7,'PENDING',NULL,NULL,NULL,NULL,NULL)
            """
        )
        connection.execute(
            """
            INSERT INTO printer_memory_factory_campaign_windows(
                window_id,campaign_id,run_id,cycle_id,token_slot_id
            ) VALUES ('window-1','campaign-1','run-1','cycle-1','slot-1')
            """
        )
        connection.execute(
            """
            INSERT INTO printer_memory_factory_campaign_runs(
                run_id,campaign_id,authoritative_run_id
            ) VALUES ('run-1','campaign-1','factory-1')
            """
        )
        connection.execute(
            """
            INSERT INTO printer_memory_factory_run_steps(id,run_id,scheduler_job_id)
            VALUES (1,'factory-1',7)
            """
        )
        connection.execute(
            """
            INSERT INTO printer_memory_factory_campaign_scheduler_work(
                scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,
                window_id,work_intent,deadline_at,work_state,scheduler_job_id,
                source_request_id,source_response_id,source_failure_id,
                ownership_contract_version,stage_id,work_scope,target_category,
                target_identity,factory_run_id,first_terminal_cause,terminal_at,
                created_at,updated_at
            ) VALUES (
                'work-1','campaign-1','run-1','cycle-1','slot-1',
                'window-1','PRE_CLOSE','2026-08-25T16:00:00+00:00','RUNNING',7,
                NULL,NULL,NULL,'V2_STAGE_SCOPED','WINDOW_15M','WINDOW_LIFECYCLE',
                'CAMPAIGN_WINDOW','window-1','factory-1',NULL,NULL,?,?
            )
            """,
            (NOW, NOW),
        )
        connection.commit()

        result = project_campaign_scheduler_job(
            connection,
            scheduler_work_id="work-1",
            campaign_id="campaign-1",
            run_id="run-1",
            cycle_id="cycle-1",
            token_slot_id="slot-1",
            window_id="window-1",
            factory_run_id="factory-1",
            work_intent="PRE_CLOSE",
            deadline_at="2026-08-25T16:00:00+00:00",
            scheduler_job_id=7,
            stage_id="WINDOW_15M",
            target_category="CAMPAIGN_WINDOW",
            target_identity="window-1",
            now=NOW,
        )

        assert result.created is False
        assert result.work_state == "PENDING"
        stored = connection.execute(
            "SELECT work_state,first_terminal_cause,terminal_at "
            "FROM printer_memory_factory_campaign_scheduler_work "
            "WHERE scheduler_work_id='work-1'"
        ).fetchone()
        assert stored == ("PENDING", None, None)
    finally:
        connection.close()

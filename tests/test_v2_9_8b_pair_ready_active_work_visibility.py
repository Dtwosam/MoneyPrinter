from __future__ import annotations

import sqlite3

from printer_v1.operator_cli.campaign_active_work import campaign_active_work_report


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE printer_scheduler_jobs(
            id INTEGER PRIMARY KEY,
            job_name TEXT NOT NULL,
            job_kind TEXT NOT NULL,
            status TEXT NOT NULL,
            locked_at TEXT,
            lock_owner TEXT
        );
        CREATE TABLE printer_pre_admission_discovery_attempts(
            attempt_id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            campaign_run_id TEXT NOT NULL,
            authoritative_factory_run_id TEXT NOT NULL,
            proposed_cycle_id TEXT NOT NULL,
            scheduler_job_id INTEGER NOT NULL,
            attempt_state TEXT NOT NULL
        );
        """
    )
    connection.execute(
        "INSERT INTO printer_scheduler_jobs(id,job_name,job_kind,status) "
        "VALUES (1,'pre-admission:attempt-1','PRE_ADMISSION_DISCOVERY_SELECTION','SUCCEEDED')"
    )
    connection.execute(
        """INSERT INTO printer_pre_admission_discovery_attempts(
               attempt_id,campaign_id,campaign_run_id,authoritative_factory_run_id,
               proposed_cycle_id,scheduler_job_id,attempt_state
           ) VALUES ('attempt-1','campaign-1','run-1','factory-1','cycle-2',1,'PAIR_READY')"""
    )
    connection.commit()
    return connection


def test_pair_ready_is_active_terminal_residue_until_cancelled() -> None:
    connection = _connection()
    try:
        before = campaign_active_work_report(
            connection,
            factory_run_id="factory-1",
            campaign_id="campaign-1",
            run_id="run-1",
            cycle_id="cycle-1",
        )
        assert before["attributable_job_counts"]["pre_admission_attempt_jobs"] == 1
        assert before["jobs_by_status"] == {"SUCCEEDED": 1}
        assert before["active_jobs"] == 0
        assert before["active_pre_admission_attempts"] == 1
        assert before["clean_terminal"] is False

        connection.execute(
            "UPDATE printer_pre_admission_discovery_attempts "
            "SET attempt_state='CANCELLED' WHERE attempt_id='attempt-1'"
        )
        connection.commit()

        after = campaign_active_work_report(
            connection,
            factory_run_id="factory-1",
            campaign_id="campaign-1",
            run_id="run-1",
            cycle_id="cycle-1",
        )
        assert after["attributable_job_counts"]["pre_admission_attempt_jobs"] == 0
        assert after["active_pre_admission_attempts"] == 0
        assert after["clean_terminal"] is True
    finally:
        connection.close()

from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

import pytest

from printer_v1.operator_cli.four_token_factory_adapter import (
    FourTokenFactoryAdapterError,
    finalize_four_token_shared_terminal,
    reconcile_four_token_cycle_terminal,
)


def _terminal_db() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE printer_memory_factory_campaigns(
            campaign_id TEXT PRIMARY KEY,campaign_state TEXT,first_terminal_cause TEXT,terminal_at TEXT
        );
        CREATE TABLE printer_memory_factory_campaign_runs(
            run_id TEXT PRIMARY KEY,campaign_id TEXT,run_state TEXT,
            authoritative_run_id TEXT,first_terminal_cause TEXT,terminal_at TEXT
        );
        CREATE TABLE printer_memory_factory_runs(
            run_id TEXT PRIMARY KEY,run_status TEXT,stop_reason TEXT,finished_at TEXT,updated_at TEXT
        );
        CREATE TABLE printer_memory_factory_campaign_cycles(
            cycle_id TEXT PRIMARY KEY,campaign_id TEXT,run_id TEXT,cycle_ordinal INTEGER,
            cycle_state TEXT,first_terminal_cause TEXT,terminal_at TEXT,updated_at TEXT
        );
        CREATE TABLE printer_memory_factory_campaign_token_slots(
            token_slot_id TEXT PRIMARY KEY,campaign_id TEXT,run_id TEXT,cycle_id TEXT,
            slot_ordinal INTEGER,token_state TEXT,first_terminal_cause TEXT,terminal_at TEXT,updated_at TEXT
        );
        CREATE TABLE printer_memory_factory_campaign_windows(
            window_id TEXT PRIMARY KEY,campaign_id TEXT,run_id TEXT,cycle_id TEXT,
            token_slot_id TEXT,window_state TEXT,first_terminal_cause TEXT,terminal_at TEXT,updated_at TEXT
        );
        CREATE TABLE printer_scheduler_jobs(
            id INTEGER PRIMARY KEY,job_name TEXT,job_kind TEXT,status TEXT,
            scheduled_for TEXT,locked_at TEXT,lock_owner TEXT,finished_at TEXT,updated_at TEXT
        );
        CREATE TABLE printer_memory_factory_campaign_scheduler_work(
            scheduler_work_id TEXT PRIMARY KEY,campaign_id TEXT,run_id TEXT,cycle_id TEXT,
            token_slot_id TEXT,window_id TEXT,work_state TEXT,scheduler_job_id INTEGER,
            factory_run_id TEXT,ownership_contract_version TEXT,work_scope TEXT,
            first_terminal_cause TEXT,terminal_at TEXT,updated_at TEXT
        );
        CREATE TABLE printer_memory_factory_run_steps(
            id INTEGER PRIMARY KEY,run_id TEXT,scheduler_job_id INTEGER,step_status TEXT
        );
        """
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns VALUES ('campaign-1','RUNNING',NULL,NULL)"
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs VALUES "
        "('campaign-run-1','campaign-1','RUNNING','factory-1',NULL,NULL)"
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs VALUES ('factory-1','RUNNING',NULL,NULL,'t0')"
    )
    for ordinal in (1, 2):
        cycle = f"cycle-{ordinal}"
        connection.execute(
            "INSERT INTO printer_memory_factory_campaign_cycles VALUES (?,?,?,?,?,?,?,?)",
            (cycle, "campaign-1", "campaign-run-1", ordinal, "TRACKING", None, None, "t0"),
        )
        for slot in (1, 2):
            slot_id = f"{cycle}-slot-{slot}"
            window_id = f"{cycle}-window-{slot}"
            job_id = ordinal * 10 + slot
            connection.execute(
                "INSERT INTO printer_memory_factory_campaign_token_slots VALUES (?,?,?,?,?,?,?,?,?)",
                (slot_id, "campaign-1", "campaign-run-1", cycle, slot,
                 "WINDOW_4H_CLOSED", None, None, "t0"),
            )
            connection.execute(
                "INSERT INTO printer_memory_factory_campaign_windows VALUES (?,?,?,?,?,?,?,?,?)",
                (window_id, "campaign-1", "campaign-run-1", cycle, slot_id,
                 "NO_PROMOTION", "WINDOW_CLOSED", "t0", "t0"),
            )
            connection.execute(
                "INSERT INTO printer_scheduler_jobs VALUES (?,?,?,'SUCCEEDED','t0',NULL,NULL,'t0','t0')",
                (job_id, f"job-{job_id}", "WINDOW_CLOSE"),
            )
            connection.execute(
                "INSERT INTO printer_memory_factory_campaign_scheduler_work VALUES "
                "(?,?,?,?,?,?,'SUCCEEDED',?,'factory-1','V2_STAGE_SCOPED',"
                "'WINDOW_LIFECYCLE','WINDOW_CLOSED','t0','t0')",
                (f"work-{job_id}", "campaign-1", "campaign-run-1", cycle,
                 slot_id, window_id, job_id),
            )
            connection.execute(
                "INSERT INTO printer_memory_factory_run_steps VALUES (?, 'factory-1', ?, 'SUCCEEDED')",
                (job_id, job_id),
            )
    connection.commit()
    return connection


def test_two_phase_terminal_waits_for_both_cycles_and_composes_shared_once() -> None:
    connection = _terminal_db()
    now = datetime(2026, 8, 13, 16, 0, tzinfo=timezone.utc)
    first = reconcile_four_token_cycle_terminal(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        cycle_id="cycle-1",
        cause="COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
        run_status="COMPLETED",
        now=now,
    )
    assert first["cycle_state"] == "TERMINAL_COMPLETED"
    assert connection.execute(
        "SELECT cycle_state FROM printer_memory_factory_campaign_cycles WHERE cycle_id='cycle-2'"
    ).fetchone()[0] == "TRACKING"
    assert connection.execute(
        "SELECT run_state FROM printer_memory_factory_campaign_runs"
    ).fetchone()[0] == "RUNNING"
    assert connection.execute(
        "SELECT run_status FROM printer_memory_factory_runs"
    ).fetchone()[0] == "RUNNING"

    calls: list[str] = []

    def shared() -> dict:
        calls.append("shared")
        connection.execute(
            "UPDATE printer_memory_factory_campaign_runs SET run_state='TERMINAL_COMPLETED',"
            "first_terminal_cause='COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED',terminal_at='t1'"
        )
        connection.execute(
            "UPDATE printer_memory_factory_campaigns SET campaign_state='TERMINAL_COMPLETED',"
            "first_terminal_cause='COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED',terminal_at='t1'"
        )
        connection.execute(
            "UPDATE printer_memory_factory_runs SET run_status='COMPLETED',finished_at='t1'"
        )
        connection.commit()
        return {"clean_terminal": True, "lease_released": True}

    with pytest.raises(FourTokenFactoryAdapterError, match="both cycles"):
        finalize_four_token_shared_terminal(
            connection,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            shared_terminalizer=shared,
        )
    assert calls == []

    reconcile_four_token_cycle_terminal(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        cycle_id="cycle-2",
        cause="COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
        run_status="COMPLETED",
        now=now,
    )
    result = finalize_four_token_shared_terminal(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        shared_terminalizer=shared,
    )
    assert result["shared_terminalized"] is True
    assert result["shared_cleanup_count"] == 1
    assert calls == ["shared"]

    repeated = finalize_four_token_shared_terminal(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        shared_terminalizer=shared,
    )
    assert repeated["shared_terminalized"] is False
    assert calls == ["shared"]


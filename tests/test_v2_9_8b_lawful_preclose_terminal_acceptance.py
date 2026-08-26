"""Regression coverage for lawful zero-work pre-close terminal accounting."""

from __future__ import annotations

import sqlite3

from printer_v1.operator_cli.campaign_full_run_accounting import (
    OperationalLifecycleOwnershipContext,
    _load_terminal_scheduler_correspondence,
)


def _context() -> OperationalLifecycleOwnershipContext:
    return OperationalLifecycleOwnershipContext(
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        cycle_id="cycle-1",
        configuration_id="config-1",
        factory_run_id="factory-run-1",
    )


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE printer_scheduler_jobs (
            id INTEGER PRIMARY KEY,
            status TEXT NOT NULL,
            retry_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE printer_memory_factory_run_steps (
            id INTEGER PRIMARY KEY,
            run_id TEXT NOT NULL,
            scheduler_job_id INTEGER,
            step_kind TEXT NOT NULL,
            token_id INTEGER NOT NULL,
            pair_id INTEGER NOT NULL,
            step_key TEXT NOT NULL,
            step_status TEXT NOT NULL,
            error_or_skip_reason TEXT
        );
        CREATE TABLE printer_memory_factory_campaign_windows (
            window_id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            cycle_id TEXT NOT NULL,
            token_slot_id TEXT NOT NULL,
            token_row_id INTEGER NOT NULL,
            pair_row_id INTEGER NOT NULL,
            window_kind TEXT NOT NULL
        );
        CREATE TABLE printer_memory_factory_campaign_scheduler_work (
            scheduler_work_id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            cycle_id TEXT NOT NULL,
            factory_run_id TEXT NOT NULL,
            scheduler_job_id INTEGER NOT NULL,
            token_slot_id TEXT,
            window_id TEXT,
            work_state TEXT NOT NULL,
            ownership_contract_version TEXT NOT NULL,
            stage_id TEXT,
            work_scope TEXT NOT NULL,
            target_category TEXT,
            target_identity TEXT
        );
        """
    )
    conn.execute(
        """INSERT INTO printer_memory_factory_campaign_windows
           (window_id,campaign_id,run_id,cycle_id,token_slot_id,token_row_id,pair_row_id,window_kind)
           VALUES ('w15','campaign-1','campaign-run-1','cycle-1','slot-1',1,11,'WINDOW_15M')"""
    )
    return conn


def _seed_preclose(conn: sqlite3.Connection, *, reason: str) -> None:
    conn.execute(
        "INSERT INTO printer_scheduler_jobs(id,status,retry_count) VALUES (1,'SKIPPED',0)"
    )
    conn.execute(
        """INSERT INTO printer_memory_factory_run_steps
           (id,run_id,scheduler_job_id,step_kind,token_id,pair_id,step_key,step_status,error_or_skip_reason)
           VALUES (1,'factory-run-1',1,'WINDOW_CLOSE_PRE_CLOSE_CRITICAL',1,11,
                   't1_window_close_pre_close_critical','SKIPPED',?)""",
        (reason,),
    )
    conn.execute(
        """INSERT INTO printer_memory_factory_campaign_scheduler_work
           (scheduler_work_id,campaign_id,run_id,cycle_id,factory_run_id,
            scheduler_job_id,token_slot_id,window_id,work_state,
            ownership_contract_version,stage_id,work_scope,target_category,target_identity)
           VALUES ('work-1','campaign-1','campaign-run-1','cycle-1','factory-run-1',
                   1,'slot-1','w15','SKIPPED','V2_STAGE_SCOPED','WINDOW_15M_SLOT_1',
                   'WINDOW_LIFECYCLE','CAMPAIGN_WINDOW','w15')"""
    )


def test_typed_unproducible_preclose_skip_is_terminal_acceptable() -> None:
    conn = _db()
    _seed_preclose(conn, reason="TIMELY_ACQUISITION_NOT_PRODUCIBLE")
    result = _load_terminal_scheduler_correspondence(
        conn, context=_context(), standard_four_hour_campaign=False
    )
    assert result["correspondence_exact"] is True
    assert result["all_lifecycle_jobs_succeeded"] is False
    assert result["all_lifecycle_jobs_terminal_acceptable"] is True
    assert result["lawful_skipped_preclose_job_ids"] == [1]


def test_untyped_preclose_skip_remains_terminal_unacceptable() -> None:
    conn = _db()
    _seed_preclose(conn, reason="SOME_OTHER_REASON")
    result = _load_terminal_scheduler_correspondence(
        conn, context=_context(), standard_four_hour_campaign=False
    )
    assert result["correspondence_exact"] is True
    assert result["all_lifecycle_jobs_succeeded"] is False
    assert result["all_lifecycle_jobs_terminal_acceptable"] is False
    assert result["lawful_skipped_preclose_job_ids"] == []

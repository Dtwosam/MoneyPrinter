"""Focused V2-9.8B standard-4h close/accounting repair contracts.

Static/in-memory only. No providers, source fetching, runtime campaign, memory
factory execution, authorization creation, retrieval, paper decisions or trades.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

from printer_v1.operator_cli.campaign_full_run_accounting import (
    OperationalLifecycleOwnershipContext,
    _load_terminal_scheduler_correspondence,
    _no_retry_restart_resume_successor,
    _scheduler_family_attribution_complete,
)
from printer_v1.operator_cli.one_token_4h_runtime import (
    FourHourExecutionAuthority,
    close_current_run_4h,
)


def _context() -> OperationalLifecycleOwnershipContext:
    return OperationalLifecycleOwnershipContext(
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        cycle_id="cycle-1",
        configuration_id="config-1",
        factory_run_id="factory-run-1",
    )


def _scheduler_db() -> sqlite3.Connection:
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
            step_key TEXT NOT NULL
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
    return conn


def _job(conn: sqlite3.Connection, job_id: int, step_kind: str, token_id: int = 1, pair_id: int = 11) -> None:
    conn.execute(
        "INSERT INTO printer_scheduler_jobs(id,status,retry_count) VALUES (?,'SUCCEEDED',0)",
        (job_id,),
    )
    conn.execute(
        """INSERT INTO printer_memory_factory_run_steps
           (id,run_id,scheduler_job_id,step_kind,token_id,pair_id,step_key)
           VALUES (?,?,?,?,?,?,?)""",
        (job_id, "factory-run-1", job_id, step_kind, token_id, pair_id, f"t1_{step_kind.lower()}_{job_id}"),
    )


def _owned(
    conn: sqlite3.Connection,
    job_id: int,
    *,
    stage_id: str,
    window_id: str,
    token_slot_id: str = "slot-1",
) -> None:
    conn.execute(
        """INSERT INTO printer_memory_factory_campaign_scheduler_work
           (scheduler_work_id,campaign_id,run_id,cycle_id,factory_run_id,
            scheduler_job_id,token_slot_id,window_id,work_state,
            ownership_contract_version,stage_id,work_scope,target_category,target_identity)
           VALUES (?,?,?,?,?,?,?,?,?,'V2_STAGE_SCOPED',?,'WINDOW_LIFECYCLE',
                   'CAMPAIGN_WINDOW',?)""",
        (
            f"work-{job_id}", "campaign-1", "campaign-run-1", "cycle-1",
            "factory-run-1", job_id, token_slot_id, window_id, "SUCCEEDED",
            stage_id, window_id,
        ),
    )


def _window(conn: sqlite3.Connection, window_id: str, kind: str) -> None:
    conn.execute(
        """INSERT INTO printer_memory_factory_campaign_windows
           (window_id,campaign_id,run_id,cycle_id,token_slot_id,token_row_id,pair_row_id,window_kind)
           VALUES (?,'campaign-1','campaign-run-1','cycle-1','slot-1',1,11,?)""",
        (window_id, kind),
    )


def test_standard_close_authority_reaches_enabled_successor_resolution() -> None:
    conn = sqlite3.connect(":memory:")
    with patch(
        "printer_v1.operator_cli.one_token_4h_runtime.resolve_current_run_long_predecessor",
        return_value={"resolved": False, "reasons": ["sentinel"]},
    ) as resolver:
        result = close_current_run_4h(
            conn,
            run_id="factory-run-1",
            close_step={"token_id": 1, "pair_id": 11, "tracking_lane": "TRACK_FAST"},
            closing_snapshot_id=99,
            execution_authority=FourHourExecutionAuthority.STANDARD_CAMPAIGN,
        )
    assert result["closed"] is False
    assert resolver.call_args.kwargs["allow_enabled_successor_planning"] is True


def test_missing_close_authority_still_fails_closed_before_resolution() -> None:
    conn = sqlite3.connect(":memory:")
    with patch(
        "printer_v1.operator_cli.one_token_4h_runtime.resolve_current_run_long_predecessor"
    ) as resolver:
        result = close_current_run_4h(
            conn,
            run_id="factory-run-1",
            close_step={"token_id": 1, "pair_id": 11, "tracking_lane": "TRACK_FAST"},
            closing_snapshot_id=99,
        )
    assert result == {
        "closed": False,
        "blocked_reasons": ["WINDOW_4H close execution authority is disabled"],
    }
    resolver.assert_not_called()


def test_standard_scheduler_correspondence_accepts_exact_15m_1h_4h_lineage() -> None:
    conn = _scheduler_db()
    _window(conn, "w15", "WINDOW_15M")
    _window(conn, "w1h", "WINDOW_1H")
    _window(conn, "w4h", "WINDOW_4H")
    for job_id, kind, stage, window in (
        (1, "SNAPSHOT", "WINDOW_15M_SLOT_1", "w15"),
        (2, "WINDOW_CLOSE", "WINDOW_15M_SLOT_1", "w15"),
        (3, "CONTINUATION_SNAPSHOT", "WINDOW_1H", "w1h"),
        (4, "CONTINUATION_CLOSE", "WINDOW_1H", "w1h"),
        (5, "LONG_CONTINUATION_SNAPSHOT", "WINDOW_4H", "w4h"),
        (6, "LONG_CONTINUATION_CLOSE", "WINDOW_4H", "w4h"),
    ):
        _job(conn, job_id, kind)
        _owned(conn, job_id, stage_id=stage, window_id=window)
    result = _load_terminal_scheduler_correspondence(
        conn, context=_context(), standard_four_hour_campaign=True
    )
    assert result["correspondence_exact"] is True
    assert result["lifecycle_job_ids"] == [1, 2, 3, 4, 5, 6]
    assert result["extra_ownership"] == []
    assert result["all_lifecycle_jobs_succeeded"] is True


def test_standard_scheduler_correspondence_rejects_unexplained_extra_work() -> None:
    conn = _scheduler_db()
    _window(conn, "w15", "WINDOW_15M")
    _job(conn, 1, "SNAPSHOT")
    _owned(conn, 1, stage_id="WINDOW_15M_SLOT_1", window_id="w15")
    conn.execute(
        "INSERT INTO printer_scheduler_jobs(id,status,retry_count) VALUES (99,'SUCCEEDED',0)"
    )
    _owned(conn, 99, stage_id="WINDOW_4H", window_id="w15")
    result = _load_terminal_scheduler_correspondence(
        conn, context=_context(), standard_four_hour_campaign=True
    )
    assert result["correspondence_exact"] is False
    assert result["extra_ownership"] == [99]


def test_window_15m_scheduler_correspondence_does_not_expand_to_long_work() -> None:
    conn = _scheduler_db()
    _window(conn, "w15", "WINDOW_15M")
    _job(conn, 1, "SNAPSHOT")
    _owned(conn, 1, stage_id="WINDOW_15M_SLOT_1", window_id="w15")
    result = _load_terminal_scheduler_correspondence(
        conn, context=_context(), standard_four_hour_campaign=False
    )
    assert result["correspondence_exact"] is True
    assert result["lifecycle_job_ids"] == [1]


def test_standard_family_attribution_uses_exact_expected_lifecycle_count() -> None:
    accounting = {
        "scheduler_attribution": {
            "discovery": 1, "selection": 1, "handoff": 2, "lifecycle": 42
        },
        "scheduler_ownership": {"expected_lifecycle_scheduler_count": 42},
    }
    assert _scheduler_family_attribution_complete(accounting) is True
    accounting["scheduler_attribution"]["lifecycle"] = 41
    assert _scheduler_family_attribution_complete(accounting) is False


def test_ordinary_family_attribution_keeps_legacy_18_job_contract() -> None:
    accounting = {
        "scheduler_attribution": {
            "discovery": 1, "selection": 1, "handoff": 2, "lifecycle": 18
        },
        "scheduler_ownership": {},
    }
    assert _scheduler_family_attribution_complete(accounting) is True


def test_scheduler_retry_history_is_not_campaign_automatic_retry() -> None:
    assert _no_retry_restart_resume_successor(
        cleanup_truth_complete=True,
        scheduler_retry_count=2,
        automatic_retry_count=0,
        restart_count=0,
        resume_count=0,
        successor_count=0,
        bound_run_count=1,
    ) is True
    assert _no_retry_restart_resume_successor(
        cleanup_truth_complete=True,
        scheduler_retry_count=0,
        automatic_retry_count=1,
        restart_count=0,
        resume_count=0,
        successor_count=0,
        bound_run_count=1,
    ) is False

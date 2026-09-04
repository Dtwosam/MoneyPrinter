from __future__ import annotations

import sqlite3

from printer_v1.operator_cli import one_command_15m_factory as factory


RUN_ID = "cycle2-scheduler-budget-run"


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE printer_scheduler_jobs("
        "id INTEGER PRIMARY KEY,job_name TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE printer_memory_factory_run_steps("
        "id INTEGER PRIMARY KEY,run_id TEXT NOT NULL,step_key TEXT NOT NULL,"
        "step_kind TEXT NOT NULL,tracking_lane TEXT,scheduler_job_id INTEGER)"
    )
    conn.execute(
        "CREATE TABLE printer_source_requests("
        "id INTEGER PRIMARY KEY,source_name TEXT,request_key TEXT)"
    )
    conn.execute(
        "CREATE TABLE printer_pre_admission_discovery_attempts("
        "attempt_id TEXT PRIMARY KEY,authoritative_factory_run_id TEXT NOT NULL,"
        "scheduler_job_id INTEGER NOT NULL)"
    )
    conn.executemany(
        "INSERT INTO printer_scheduler_jobs(id,job_name) VALUES (?,?)",
        [
            (101, f"v2_4_{RUN_ID}_t1_snapshot_00"),
            (102, "cycle1-handoff"),
            (103, "cycle2-pre-admission"),
        ],
    )
    conn.execute(
        "INSERT INTO printer_memory_factory_run_steps("
        "id,run_id,step_key,step_kind,tracking_lane,scheduler_job_id) "
        "VALUES (1,?,'t1_snapshot_00','SNAPSHOT','TRACK_NORMAL',101)",
        (RUN_ID,),
    )
    conn.execute(
        "INSERT INTO printer_pre_admission_discovery_attempts("
        "attempt_id,authoritative_factory_run_id,scheduler_job_id) "
        "VALUES ('attempt-2',?,103)",
        (RUN_ID,),
    )
    return conn


def test_cycle2_pre_admission_scheduler_job_counts_in_terminal_budget(monkeypatch) -> None:
    conn = _db()
    monkeypatch.setattr(
        factory,
        "_load_run_config",
        lambda *_: {
            "continuous_first_hour": True,
            "continuous_four_hour": True,
            "standard_four_hour_campaign": True,
            "four_token_proof": True,
        },
    )
    monkeypatch.setattr(
        factory,
        "_standard_four_hour_reporting_budget_for_run",
        lambda *_: {
            "available": True,
            "reason": None,
            "budget": {
                "phase_request_ceiling": 0,
                "phase_scheduler_ceiling": 10,
                "phase_holder_fallback_ceiling": 0,
                "request_ceiling": 100,
                "scheduler_ceiling": 10,
                "request_components": {"discovery": 4},
                "scheduler_components": {},
            },
        },
    )
    monkeypatch.setattr(
        factory,
        "_later_cycle_discovery_request_ids",
        lambda *_: set(),
    )

    report = factory._run_budgets(
        conn,
        RUN_ID,
        {
            "source_budget_report": {"source_requests_attempted": 0},
            "discovery_results": [{"scheduler_job_id": 102}],
        },
        [
            {
                "step_key": "t1_snapshot_00",
                "step_kind": "SNAPSHOT",
                "tracking_lane": "TRACK_NORMAL",
            }
        ],
    )

    usage = report["cumulative_lifecycle_usage"]
    assert report["scheduler_run_step_jobs"] == 1
    assert report["scheduler_cancelled_discovery_handoffs"] == 1
    assert report["scheduler_pre_admission_attempt_jobs"] == 1
    assert report["scheduler_rows_total"] == 3
    assert usage["scheduler_rows"] == 3
    assert usage["scheduler_rows_within_ceiling"] is True
    conn.close()

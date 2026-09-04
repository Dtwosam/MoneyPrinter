from __future__ import annotations

import sqlite3

from printer_v1.operator_cli import one_command_15m_factory as factory


RUN_ID = "cycle2-discovery-budget-run"


def test_later_cycle_discovery_request_ids_reduce_exact_attempt_scope() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE printer_pre_admission_discovery_attempts("
        "attempt_id TEXT PRIMARY KEY,authoritative_factory_run_id TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE printer_pre_admission_discovery_attempt_source_links("
        "attempt_id TEXT NOT NULL,source_request_id INTEGER NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE printer_pre_admission_attempt_evidence("
        "attempt_id TEXT NOT NULL,source_request_id INTEGER)"
    )
    conn.executemany(
        "INSERT INTO printer_pre_admission_discovery_attempts("
        "attempt_id,authoritative_factory_run_id) VALUES (?,?)",
        [
            ("attempt-cycle2", RUN_ID),
            ("attempt-other", "other-run"),
        ],
    )
    conn.executemany(
        "INSERT INTO printer_pre_admission_discovery_attempt_source_links("
        "attempt_id,source_request_id) VALUES (?,?)",
        [
            ("attempt-cycle2", 11),
            ("attempt-cycle2", 12),
            ("attempt-other", 99),
        ],
    )
    conn.executemany(
        "INSERT INTO printer_pre_admission_attempt_evidence("
        "attempt_id,source_request_id) VALUES (?,?)",
        [
            ("attempt-cycle2", 12),
            ("attempt-cycle2", 13),
            ("attempt-cycle2", None),
            ("attempt-other", 98),
        ],
    )

    assert factory._later_cycle_discovery_request_ids(conn, RUN_ID) == {11, 12, 13}
    conn.close()


def test_run_budget_includes_cycle2_discovery_without_runtime_double_count(
    monkeypatch,
) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE printer_source_requests("
        "id INTEGER PRIMARY KEY,source_name TEXT,request_key TEXT)"
    )
    conn.execute(
        "CREATE TABLE printer_memory_factory_run_steps("
        "id INTEGER PRIMARY KEY,run_id TEXT,step_key TEXT,step_kind TEXT,"
        "tracking_lane TEXT,scheduler_job_id INTEGER)"
    )
    conn.executemany(
        "INSERT INTO printer_source_requests(id,source_name,request_key) "
        "VALUES (?,?,?)",
        [
            # This later-cycle request is already a run-keyed lifecycle request;
            # it must not be counted twice when the attempt ledger also links it.
            (21, "dexscreener", f"{RUN_ID}:t1_c0002_snapshot_00:attempt-1"),
            # This is a pre-admission discovery request outside the run-keyed
            # lifecycle namespace and must be added to discovery usage.
            (22, "geckoterminal", "campaign:cycle2:discovery:attempt-1"),
        ],
    )
    conn.execute(
        "INSERT INTO printer_memory_factory_run_steps("
        "id,run_id,step_key,step_kind,tracking_lane,scheduler_job_id) "
        "VALUES (1,?,'t1_c0002_snapshot_00','SNAPSHOT','TRACK_NORMAL',NULL)",
        (RUN_ID,),
    )

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
                "phase_scheduler_ceiling": 0,
                "phase_holder_fallback_ceiling": 0,
                "request_ceiling": 100,
                "scheduler_ceiling": 100,
                "request_components": {"discovery": 4},
                "scheduler_components": {},
            },
        },
    )
    monkeypatch.setattr(
        factory,
        "_later_cycle_discovery_request_ids",
        lambda *_: {21, 22},
        raising=False,
    )

    report = factory._run_budgets(
        conn,
        RUN_ID,
        {"source_budget_report": {"source_requests_attempted": 2}},
        [
            {
                "step_key": "t1_c0002_snapshot_00",
                "step_kind": "SNAPSHOT",
                "tracking_lane": "TRACK_NORMAL",
            }
        ],
    )

    assert report["cumulative_lifecycle_usage"]["runtime_source_requests"] == 1
    assert report["cumulative_lifecycle_usage"]["discovery_source_requests"] == 3
    assert report["cumulative_lifecycle_usage"][
        "later_cycle_discovery_source_requests"
    ] == 1
    assert report["cumulative_lifecycle_usage"]["source_requests"] == 4
    assert report["governed_requests_run"] == 4
    conn.close()

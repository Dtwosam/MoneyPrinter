"""End-to-end disposable audit of the Standard-4H memory lifecycle.

This file intentionally drives real production orchestration with the existing
accelerated fixture-source clock. It does not contact providers, prepare an
authorization, or touch the authoritative database.
"""
from __future__ import annotations

import sqlite3

from tests.test_v2_9_8b_lane3_standard_4h_progression import (
    _FactoryLoopDateTime,
    _run_standard_factory_loop,
)


def test_single_cycle_real_factory_reaches_two_terminal_four_hour_closes(
    tmp_path,
    monkeypatch,
) -> None:
    # The legacy Lane-3 harness binds the factory and source contracts to its
    # accelerated clock. Bind the long-window planner too so this audit proves
    # production control flow rather than mixing fake August time with the
    # runner's real wall clock.
    monkeypatch.setattr(
        "printer_v1.operator_cli.one_token_4h_runtime.datetime",
        _FactoryLoopDateTime,
    )
    db, report = _run_standard_factory_loop(
        tmp_path,
        monkeypatch,
        operational_binding="VALID",
        disposable_binding=None,
    )

    validation = dict(report.get("standard_four_hour_terminal_validation") or {})
    assert validation.get("enabled") is True
    assert validation.get("complete") is True, validation
    assert validation.get("reasons") == [], validation

    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        windows = connection.execute(
            """SELECT w.window_id,w.window_state,w.memory_window_row_id,
                      s.token_state,s.token_row_id,s.pair_row_id
                 FROM printer_memory_factory_campaign_windows AS w
                 JOIN printer_memory_factory_campaign_token_slots AS s
                   ON s.campaign_id=w.campaign_id
                  AND s.run_id=w.run_id
                  AND s.cycle_id=w.cycle_id
                  AND s.token_slot_id=w.token_slot_id
                WHERE w.window_kind='WINDOW_4H'
                ORDER BY s.slot_ordinal"""
        ).fetchall()
        assert len(windows) == 2
        assert all(row["memory_window_row_id"] is not None for row in windows)
        assert all(str(row["token_state"]) == "WINDOW_4H_CLOSED" for row in windows)
        assert all(
            str(row["window_state"])
            in {"CLEAN_PROMOTED", "DIRTY", "NO_PROMOTION", "ALREADY_EXISTS_IDEMPOTENT"}
            for row in windows
        )

        closes = connection.execute(
            """SELECT s.step_status,j.status,w.work_state
                 FROM printer_memory_factory_run_steps AS s
                 JOIN printer_scheduler_jobs AS j ON j.id=s.scheduler_job_id
                 JOIN printer_memory_factory_campaign_scheduler_work AS w
                   ON w.scheduler_job_id=s.scheduler_job_id
                WHERE s.step_kind='LONG_CONTINUATION_CLOSE_AUDIT'
                ORDER BY s.id"""
        ).fetchall()
        assert len(closes) == 2
        assert all(tuple(row) == ("SUCCEEDED", "SUCCEEDED", "SUCCEEDED") for row in closes)

        active_jobs = connection.execute(
            """SELECT COUNT(*)
                 FROM printer_scheduler_jobs
                WHERE status IN ('PENDING','RUNNING')"""
        ).fetchone()[0]
        active_steps = connection.execute(
            """SELECT COUNT(*)
                 FROM printer_memory_factory_run_steps
                WHERE step_status IN ('PENDING','RUNNING')"""
        ).fetchone()[0]
        assert int(active_jobs) == 0
        assert int(active_steps) == 0
    finally:
        connection.close()

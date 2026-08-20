"""Readiness active-count helper must see RUNNING factory runs.

The strict four-token zero-state gate already counts
``printer_memory_factory_runs.run_status IN ('PENDING','RUNNING')``.
``_active_counts`` previously counted only factory steps, so an orphan
RUNNING factory row with zero active steps looked quiescent to readiness.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import operational_memory_factory_command as command


NOW = datetime(2026, 8, 20, 18, 0, tzinfo=timezone.utc).isoformat()


def _seed(db: Path, *, factory_status: str = "RUNNING") -> None:
    import sqlite3

    apply_migrations(db)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    with connection:
        connection.execute(
            """INSERT INTO printer_memory_factory_runs(
                   run_id,run_status,window_kind,db_mode,config_hash,config_json,
                   started_at,created_at,updated_at)
               VALUES ('factory-orphan',?,'WINDOW_15M','OPERATIONAL_PERSISTENT',
                       'h','{}',?,?,?)""",
            (factory_status, NOW, NOW, NOW),
        )
        if factory_status == "RUNNING":
            connection.execute(
                """INSERT INTO printer_memory_factory_run_steps(
                       run_id,step_key,step_kind,step_status,created_at,updated_at)
                   VALUES ('factory-orphan','step-1','SNAPSHOT','SUCCEEDED',?,?)""",
                (NOW, NOW),
            )
    connection.close()


def test_active_counts_reports_running_factory_run_even_when_steps_are_terminal(
    tmp_path,
) -> None:
    db = tmp_path / "active-counts-factory.sqlite3"
    _seed(db, factory_status="RUNNING")
    connection = __import__("sqlite3").connect(db)
    connection.row_factory = __import__("sqlite3").Row
    try:
        counts = command._active_counts(connection)
        assert counts["factory_runs"] == 1
        assert counts["factory_run_steps"] == 0
        assert any(int(v) > 0 for v in counts.values())
    finally:
        connection.close()


def test_active_counts_zero_when_factory_run_is_safe_stopped(tmp_path) -> None:
    db = tmp_path / "active-counts-factory-stopped.sqlite3"
    _seed(db, factory_status="SAFE_STOPPED")
    connection = __import__("sqlite3").connect(db)
    connection.row_factory = __import__("sqlite3").Row
    try:
        counts = command._active_counts(connection)
        assert counts["factory_runs"] == 0
        assert counts["factory_run_steps"] == 0
    finally:
        connection.close()

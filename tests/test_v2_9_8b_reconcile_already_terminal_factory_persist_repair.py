"""Disposable proofs: already-terminal parents must not roll back factory stop."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from unittest import mock

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_active_work import campaign_active_work_report
from printer_v1.operator_cli.campaign_ownership import transition_state
from printer_v1.operator_cli.unified_terminal_closure import reconcile_campaign_terminal


NOW = datetime(2026, 8, 20, 20, 0, tzinfo=timezone.utc)
CAUSE = "OPERATIONAL_CAMPAIGN_FAILED:FourTokenFactoryAdapterError"
CAMPAIGN = "campaign-1"
RUN = "campaign-run-1"
CYCLE = "cycle-1"
FACTORY = "factory-1"
CONFIG = "configuration-1"


def _seed(
    db: Path,
    *,
    campaign_state: str = "TERMINAL_FAILED",
    run_state: str = "TERMINAL_FAILED",
    cycle_state: str = "TERMINAL_FAILED",
    factory_status: str = "RUNNING",
    stop_reason: str | None = None,
) -> None:
    apply_migrations(db)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    instant = NOW.isoformat()
    terminal = campaign_state.startswith("TERMINAL_")
    with connection:
        connection.execute(
            """INSERT INTO printer_memory_factory_campaigns(
                   campaign_id,campaign_state,db_mode,db_target_identity,policy_version,
                   first_terminal_cause,terminal_at,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                CAMPAIGN, campaign_state, "OPERATIONAL_PERSISTENT", "db-1", "policy-1",
                CAUSE if terminal else None,
                instant if terminal else None,
                instant, instant,
            ),
        )
        connection.execute(
            """INSERT INTO printer_memory_factory_campaign_configurations(
                   configuration_id,campaign_id,configuration_hash,configuration_json,
                   launch_provenance_json,created_at)
               VALUES (?,?,?,?,?,?)""",
            (CONFIG, CAMPAIGN, "a" * 64, "{}", "{}", instant),
        )
        connection.execute(
            """INSERT INTO printer_memory_factory_runs(
                   run_id,run_status,window_kind,db_mode,config_hash,config_json,
                   stop_reason,started_at,finished_at,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                FACTORY, factory_status, "WINDOW_15M", "OPERATIONAL_PERSISTENT",
                "a" * 64, "{}", stop_reason, instant,
                instant if factory_status != "RUNNING" else None,
                instant, instant,
            ),
        )
        connection.execute(
            """INSERT INTO printer_memory_factory_campaign_runs(
                   run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,
                   first_terminal_cause,terminal_at,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                RUN, CAMPAIGN, 1, run_state, FACTORY,
                CAUSE if run_state.startswith("TERMINAL_") else None,
                instant if run_state.startswith("TERMINAL_") else None,
                instant, instant,
            ),
        )
        connection.execute(
            """INSERT INTO printer_memory_factory_campaign_cycles(
                   cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,
                   first_terminal_cause,terminal_at,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                CYCLE, CAMPAIGN, RUN, 1, cycle_state,
                CAUSE if cycle_state.startswith("TERMINAL_") else None,
                instant if cycle_state.startswith("TERMINAL_") else None,
                instant, instant,
            ),
        )
        connection.execute(
            """INSERT INTO printer_memory_factory_run_steps(
                   run_id,step_key,step_kind,step_status,created_at,updated_at)
               VALUES (?,?,?,?,?,?)""",
            (FACTORY, "step-1", "SNAPSHOT", "SUCCEEDED", instant, instant),
        )
    connection.close()


def _open(db: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def test_orphan_shaped_already_terminal_parents_persist_safe_stopped(tmp_path: Path) -> None:
    db = tmp_path / "orphan-shaped.sqlite3"
    _seed(db, factory_status="RUNNING", stop_reason=None)

    result = reconcile_campaign_terminal(
        db,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
        terminal_cause=CAUSE,
        run_status="FAILED",
        factory_run_id=FACTORY,
        lifecycle_started=True,
        now=NOW.isoformat(),
    )

    connection = _open(db)
    try:
        factory = dict(
            connection.execute(
                "SELECT run_status,stop_reason,finished_at FROM printer_memory_factory_runs "
                "WHERE run_id=?",
                (FACTORY,),
            ).fetchone()
        )
        camp = dict(
            connection.execute(
                "SELECT campaign_state,first_terminal_cause FROM "
                "printer_memory_factory_campaigns WHERE campaign_id=?",
                (CAMPAIGN,),
            ).fetchone()
        )
        run = dict(
            connection.execute(
                "SELECT run_state,first_terminal_cause FROM "
                "printer_memory_factory_campaign_runs WHERE run_id=?",
                (RUN,),
            ).fetchone()
        )
        cycle = dict(
            connection.execute(
                "SELECT cycle_state,first_terminal_cause FROM "
                "printer_memory_factory_campaign_cycles WHERE cycle_id=?",
                (CYCLE,),
            ).fetchone()
        )
        report = campaign_active_work_report(
            connection,
            factory_run_id=FACTORY,
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
        )
    finally:
        connection.close()

    assert factory["run_status"] == "SAFE_STOPPED"
    assert factory["stop_reason"] == CAUSE
    assert factory["finished_at"] is not None
    assert result["factory_run"] == "SAFE_STOPPED"
    assert result["factory_run"] == factory["run_status"]
    assert result["clean_terminal"] is True
    assert report["clean_terminal"] is True
    assert result["records"] == {
        "cycle": "already_terminal",
        "run": "already_terminal",
        "campaign": "already_terminal",
    }
    assert camp["campaign_state"] == "TERMINAL_FAILED"
    assert camp["first_terminal_cause"] == CAUSE
    assert run["run_state"] == "TERMINAL_FAILED"
    assert run["first_terminal_cause"] == CAUSE
    assert cycle["cycle_state"] == "TERMINAL_FAILED"
    assert cycle["first_terminal_cause"] == CAUSE


def test_second_reconcile_is_idempotent_for_safe_stopped_factory(tmp_path: Path) -> None:
    db = tmp_path / "idempotent.sqlite3"
    _seed(db, factory_status="RUNNING")
    first = reconcile_campaign_terminal(
        db,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
        terminal_cause=CAUSE,
        run_status="FAILED",
        factory_run_id=FACTORY,
        now=NOW.isoformat(),
    )
    assert first["factory_run"] == "SAFE_STOPPED"

    connection = _open(db)
    try:
        before = dict(
            connection.execute(
                "SELECT run_status,stop_reason,finished_at,updated_at FROM "
                "printer_memory_factory_runs WHERE run_id=?",
                (FACTORY,),
            ).fetchone()
        )
        causes_before = (
            connection.execute(
                "SELECT first_terminal_cause FROM printer_memory_factory_campaigns "
                "WHERE campaign_id=?",
                (CAMPAIGN,),
            ).fetchone()[0],
            connection.execute(
                "SELECT first_terminal_cause FROM printer_memory_factory_campaign_runs "
                "WHERE run_id=?",
                (RUN,),
            ).fetchone()[0],
        )
    finally:
        connection.close()

    second = reconcile_campaign_terminal(
        db,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
        terminal_cause="SECOND_CAUSE_MUST_NOT_REWRITE",
        run_status="FAILED",
        factory_run_id=FACTORY,
        now=(NOW.replace(minute=30)).isoformat(),
    )
    assert second["factory_run"] == "SAFE_STOPPED"
    assert second["records"] == {
        "cycle": "already_terminal",
        "run": "already_terminal",
        "campaign": "already_terminal",
    }

    connection = _open(db)
    try:
        after = dict(
            connection.execute(
                "SELECT run_status,stop_reason,finished_at,updated_at FROM "
                "printer_memory_factory_runs WHERE run_id=?",
                (FACTORY,),
            ).fetchone()
        )
        causes_after = (
            connection.execute(
                "SELECT first_terminal_cause FROM printer_memory_factory_campaigns "
                "WHERE campaign_id=?",
                (CAMPAIGN,),
            ).fetchone()[0],
            connection.execute(
                "SELECT first_terminal_cause FROM printer_memory_factory_campaign_runs "
                "WHERE run_id=?",
                (RUN,),
            ).fetchone()[0],
        )
    finally:
        connection.close()
    assert after == before
    assert causes_after == causes_before == (CAUSE, CAUSE)


def test_nonterminal_campaign_run_still_terminalizes_normally(tmp_path: Path) -> None:
    db = tmp_path / "nonterminal.sqlite3"
    _seed(
        db,
        campaign_state="RUNNING",
        run_state="RUNNING",
        cycle_state="TRACKING",
        factory_status="RUNNING",
    )
    result = reconcile_campaign_terminal(
        db,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
        terminal_cause=CAUSE,
        run_status="FAILED",
        factory_run_id=FACTORY,
        now=NOW.isoformat(),
    )
    connection = _open(db)
    try:
        factory = connection.execute(
            "SELECT run_status FROM printer_memory_factory_runs WHERE run_id=?",
            (FACTORY,),
        ).fetchone()[0]
        campaign = connection.execute(
            "SELECT campaign_state,first_terminal_cause FROM "
            "printer_memory_factory_campaigns WHERE campaign_id=?",
            (CAMPAIGN,),
        ).fetchone()
        run = connection.execute(
            "SELECT run_state,first_terminal_cause FROM "
            "printer_memory_factory_campaign_runs WHERE run_id=?",
            (RUN,),
        ).fetchone()
    finally:
        connection.close()
    assert factory == "SAFE_STOPPED"
    assert result["factory_run"] == "SAFE_STOPPED"
    assert campaign[0] == "TERMINAL_FAILED"
    assert campaign[1] == CAUSE
    assert run[0] == "TERMINAL_FAILED"
    assert run[1] == CAUSE
    assert result["records"]["campaign"] == "TERMINAL_FAILED"
    assert result["records"]["run"] == "TERMINAL_FAILED"


def test_injected_commit_failure_cannot_report_false_safe_stopped(tmp_path: Path) -> None:
    db = tmp_path / "commit-fail.sqlite3"
    _seed(db, factory_status="RUNNING")

    real_connect = sqlite3.connect

    class _FailingCommitConnection:
        def __init__(self, real: sqlite3.Connection):
            object.__setattr__(self, "_real", real)

        def commit(self) -> None:
            raise sqlite3.OperationalError("injected commit failure")

        def close(self) -> None:
            self._real.close()

        def __getattr__(self, name: str):
            return getattr(self._real, name)

        def __setattr__(self, name: str, value: object) -> None:
            if name == "_real":
                object.__setattr__(self, name, value)
            else:
                setattr(self._real, name, value)

    def connect_wrapper(*args, **kwargs):
        return _FailingCommitConnection(real_connect(*args, **kwargs))

    with mock.patch(
        "printer_v1.operator_cli.unified_terminal_closure.sqlite3.connect",
        connect_wrapper,
    ):
        with pytest.raises(sqlite3.OperationalError, match="injected commit failure"):
            reconcile_campaign_terminal(
                db,
                campaign_id=CAMPAIGN,
                run_id=RUN,
                cycle_id=CYCLE,
                terminal_cause=CAUSE,
                run_status="FAILED",
                factory_run_id=FACTORY,
                now=NOW.isoformat(),
            )

    connection = _open(db)
    try:
        status = connection.execute(
            "SELECT run_status FROM printer_memory_factory_runs WHERE run_id=?",
            (FACTORY,),
        ).fetchone()[0]
    finally:
        connection.close()
    assert status == "RUNNING"


def test_transition_state_not_called_for_already_terminal_parents(tmp_path: Path) -> None:
    db = tmp_path / "no-transition.sqlite3"
    _seed(db, factory_status="RUNNING")
    calls: list[str] = []
    real = transition_state

    def wrapped(connection, **kwargs):
        calls.append(str(kwargs.get("record_kind")))
        return real(connection, **kwargs)

    with mock.patch(
        "printer_v1.operator_cli.unified_terminal_closure.transition_state",
        side_effect=wrapped,
    ):
        result = reconcile_campaign_terminal(
            db,
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
            terminal_cause=CAUSE,
            run_status="FAILED",
            factory_run_id=FACTORY,
            now=NOW.isoformat(),
        )
    assert result["factory_run"] == "SAFE_STOPPED"
    assert "cycle" not in calls
    assert "run" not in calls
    assert "campaign" not in calls

"""Bounded disposable proofs for factory-run terminal cleanup product repair.

Covers:
- clean_terminal false while linked factory is PENDING/RUNNING
- reconcile RUNNING -> SAFE_STOPPED for failed campaigns
- adapter already-terminal path cannot leave factory active
- post-factory reconcile callers supply exact factory_run_id
- pre-factory factory_run_id=None remains lawful
- mismatched factory identity fails closed
- idempotent SAFE_STOPPED reconcile
- first terminal cause / stop_reason preserved
- _active_counts still exposes factory residue
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli.campaign_active_work import campaign_active_work_report
from printer_v1.operator_cli.four_token_factory_adapter import (
    FourTokenFactoryAdapterError,
    finalize_four_token_shared_terminal,
)
from printer_v1.operator_cli.unified_terminal_closure import reconcile_campaign_terminal


NOW = datetime(2026, 8, 20, 19, 0, tzinfo=timezone.utc)
CAUSE = "OPERATIONAL_CAMPAIGN_FAILED:FourTokenFactoryAdapterError"
CAMPAIGN = "campaign-1"
RUN = "campaign-run-1"
CYCLE = "cycle-1"
FACTORY = "factory-1"
CONFIG = "configuration-1"


def _seed_graph(
    db: Path,
    *,
    campaign_state: str = "TERMINAL_FAILED",
    run_state: str = "TERMINAL_FAILED",
    factory_status: str = "RUNNING",
    stop_reason: str | None = None,
    authoritative_run_id: str | None = FACTORY,
) -> None:
    apply_migrations(db)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    instant = NOW.isoformat()
    with connection:
        connection.execute(
            """INSERT INTO printer_memory_factory_campaigns(
                   campaign_id,campaign_state,db_mode,db_target_identity,policy_version,
                   first_terminal_cause,terminal_at,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                CAMPAIGN,
                campaign_state,
                "OPERATIONAL_PERSISTENT",
                "db-1",
                "policy-1",
                CAUSE if campaign_state.startswith("TERMINAL_") else None,
                instant if campaign_state.startswith("TERMINAL_") else None,
                instant,
                instant,
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
                FACTORY,
                factory_status,
                "WINDOW_15M",
                "OPERATIONAL_PERSISTENT",
                "a" * 64,
                "{}",
                stop_reason,
                instant,
                instant if factory_status != "RUNNING" else None,
                instant,
                instant,
            ),
        )
        connection.execute(
            """INSERT INTO printer_memory_factory_campaign_runs(
                   run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,
                   first_terminal_cause,terminal_at,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                RUN,
                CAMPAIGN,
                1,
                run_state,
                authoritative_run_id,
                CAUSE if run_state.startswith("TERMINAL_") else None,
                instant if run_state.startswith("TERMINAL_") else None,
                instant,
                instant,
            ),
        )
        for ordinal, cycle_id in ((1, CYCLE), (2, f"{CYCLE}-2")):
            connection.execute(
                """INSERT INTO printer_memory_factory_campaign_cycles(
                       cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,
                       first_terminal_cause,terminal_at,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    cycle_id,
                    CAMPAIGN,
                    RUN,
                    ordinal,
                    "TERMINAL_FAILED" if campaign_state.startswith("TERMINAL_") else "PLANNED",
                    CAUSE if campaign_state.startswith("TERMINAL_") else None,
                    instant if campaign_state.startswith("TERMINAL_") else None,
                    instant,
                    instant,
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


def test_clean_terminal_false_while_linked_factory_running(tmp_path: Path) -> None:
    db = tmp_path / "clean-false.sqlite3"
    _seed_graph(db, factory_status="RUNNING")
    connection = _open(db)
    try:
        report = campaign_active_work_report(
            connection,
            factory_run_id=FACTORY,
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
        )
        assert report["active_factory_runs"] == 1
        assert report["pending_or_running_run_steps"] == 0
        assert report["clean_terminal"] is False
        assert command._active_counts(connection)["factory_runs"] == 1
    finally:
        connection.close()


def test_reconcile_running_factory_to_safe_stopped_preserves_cause(tmp_path: Path) -> None:
    db = tmp_path / "reconcile.sqlite3"
    _seed_graph(db, factory_status="RUNNING", stop_reason="PREEXISTING_STOP")
    before = _open(db)
    try:
        assert campaign_active_work_report(
            before, factory_run_id=FACTORY, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE
        )["clean_terminal"] is False
    finally:
        before.close()

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
    assert result["factory_run"] == "SAFE_STOPPED"

    connection = _open(db)
    try:
        row = connection.execute(
            "SELECT run_status,stop_reason,finished_at FROM printer_memory_factory_runs "
            "WHERE run_id=?",
            (FACTORY,),
        ).fetchone()
        assert row["run_status"] == "SAFE_STOPPED"
        assert row["stop_reason"] == "PREEXISTING_STOP"
        assert row["finished_at"] is not None
        camp = connection.execute(
            "SELECT first_terminal_cause FROM printer_memory_factory_campaigns "
            "WHERE campaign_id=?",
            (CAMPAIGN,),
        ).fetchone()
        assert camp["first_terminal_cause"] == CAUSE
        report = campaign_active_work_report(
            connection,
            factory_run_id=FACTORY,
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
        )
        assert report["active_factory_runs"] == 0
        assert report["clean_terminal"] is True
        assert command._active_counts(connection)["factory_runs"] == 0
    finally:
        connection.close()


def test_already_safe_stopped_reconcile_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "idempotent.sqlite3"
    _seed_graph(
        db,
        factory_status="SAFE_STOPPED",
        stop_reason="ALREADY_STOPPED",
    )
    connection = _open(db)
    try:
        before = dict(
            connection.execute(
                "SELECT run_status,stop_reason,finished_at,updated_at "
                "FROM printer_memory_factory_runs WHERE run_id=?",
                (FACTORY,),
            ).fetchone()
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
    assert set(second["records"].values()) == {"already_terminal"}

    connection = _open(db)
    try:
        after = dict(
            connection.execute(
                "SELECT run_status,stop_reason,finished_at,updated_at "
                "FROM printer_memory_factory_runs WHERE run_id=?",
                (FACTORY,),
            ).fetchone()
        )
        assert after == before
        assert connection.execute(
            "SELECT first_terminal_cause FROM printer_memory_factory_campaigns "
            "WHERE campaign_id=?",
            (CAMPAIGN,),
        ).fetchone()[0] == CAUSE
    finally:
        connection.close()


def test_adapter_already_terminal_routes_active_factory_through_owner(
    tmp_path: Path,
) -> None:
    db = tmp_path / "adapter.sqlite3"
    _seed_graph(db, factory_status="RUNNING")
    calls: list[str] = []

    def shared_terminalizer():
        calls.append("called")
        reconciled = reconcile_campaign_terminal(
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
        return {**reconciled, "clean_terminal": True, "lease_released": True}

    connection = _open(db)
    try:
        result = finalize_four_token_shared_terminal(
            connection,
            campaign_id=CAMPAIGN,
            campaign_run_id=RUN,
            factory_run_id=FACTORY,
            shared_terminalizer=shared_terminalizer,
        )
        assert calls == ["called"]
        assert result["shared_terminalized"] is True
        assert result["already_terminal"] is False
        status = connection.execute(
            "SELECT run_status FROM printer_memory_factory_runs WHERE run_id=?",
            (FACTORY,),
        ).fetchone()[0]
        assert status == "SAFE_STOPPED"
    finally:
        connection.close()


def test_adapter_already_terminal_with_stopped_factory_returns_without_rerun(
    tmp_path: Path,
) -> None:
    db = tmp_path / "adapter-stopped.sqlite3"
    _seed_graph(db, factory_status="SAFE_STOPPED", stop_reason="DONE")
    calls: list[str] = []

    connection = _open(db)
    try:
        result = finalize_four_token_shared_terminal(
            connection,
            campaign_id=CAMPAIGN,
            campaign_run_id=RUN,
            factory_run_id=FACTORY,
            shared_terminalizer=lambda: calls.append("x") or {},
        )
        assert calls == []
        assert result["already_terminal"] is True
        assert result["shared_terminalized"] is False
    finally:
        connection.close()


def test_resolve_linked_factory_run_id_exact_and_fail_closed(tmp_path: Path) -> None:
    db = tmp_path / "resolve.sqlite3"
    _seed_graph(db, factory_status="RUNNING")
    connection = _open(db)
    try:
        assert (
            command._resolve_linked_factory_run_id(
                connection, campaign_id=CAMPAIGN, run_id=RUN
            )
            == FACTORY
        )
        # Fail closed when the bound factory row is deleted out from under the link.
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            "DELETE FROM printer_memory_factory_runs WHERE run_id=?",
            (FACTORY,),
        )
        connection.execute("PRAGMA foreign_keys=ON")
        connection.commit()
        with pytest.raises(command.OperationalMemoryFactoryError, match="FACTORY"):
            command._resolve_linked_factory_run_id(
                connection, campaign_id=CAMPAIGN, run_id=RUN
            )
    finally:
        connection.close()

    # No factory ever created remains lawful None
    empty = tmp_path / "no-factory.sqlite3"
    apply_migrations(empty)
    connection = _open(empty)
    try:
        connection.execute(
            """INSERT INTO printer_memory_factory_campaigns(
                   campaign_id,campaign_state,db_mode,db_target_identity,policy_version,
                   created_at,updated_at)
               VALUES ('c','RUNNING','OPERATIONAL_PERSISTENT','db','p',?,?)""",
            (NOW.isoformat(), NOW.isoformat()),
        )
        connection.execute(
            """INSERT INTO printer_memory_factory_campaign_runs(
                   run_id,campaign_id,run_ordinal,run_state,created_at,updated_at)
               VALUES ('r','c',1,'RUNNING',?,?)""",
            (NOW.isoformat(), NOW.isoformat()),
        )
        connection.commit()
        assert (
            command._resolve_linked_factory_run_id(
                connection, campaign_id="c", run_id="r"
            )
            is None
        )
    finally:
        connection.close()


def test_pre_lifecycle_finalize_passes_linked_factory_id(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "prelife.sqlite3"
    _seed_graph(db, factory_status="RUNNING")
    seen: dict[str, object] = {}

    def fake_reconcile(db_path, **kwargs):
        seen.update(kwargs)
        seen["db_path"] = db_path
        return {
            "reconciled": True,
            "clean_terminal": True,
            "restart_created": False,
            "successor_created": False,
            "factory_run": "SAFE_STOPPED",
            "records": {"campaign": "already_terminal", "run": "already_terminal", "cycle": "already_terminal"},
        }

    monkeypatch.setattr(command, "reconcile_campaign_terminal", fake_reconcile)
    monkeypatch.setattr(
        command,
        "cleanup_campaign_supervision",
        lambda *args, **kwargs: {"cleanup_completed": True, "lease_released": True},
    )
    monkeypatch.setattr(
        command,
        "assemble_campaign_terminal_reporting",
        lambda *args, **kwargs: {},
    )

    class _Activation:
        first_terminal_cause = CAUSE
        cancellation_reason = None
        fault_details = {}
        terminal_status = "FAILED"

    class _Result:
        activation = _Activation()
        lifecycle_started = False

    class _Command:
        db_path = db
        supervision_id = "sup-1"
        campaign_id = CAMPAIGN
        configuration_id = CONFIG
        run_id = RUN
        owner_id = "owner-1"
        report_id = "report-1"

    class _Units:
        def six_unit_totals(self):
            return {}

        def durable_evidence(self):
            return {}

    command._finalize_returned_pre_lifecycle_result(
        result=_Result(),
        lifecycle={"run_status": "FAILED", "first_terminal_cause": CAUSE},
        command=_Command(),
        cycle_id=CYCLE,
        execution_id="exec-1",
        paths={"reports": tmp_path / "reports"},
        launch_git_provenance={},
        campaign_units=_Units(),
        action_local_transport_identities=[],
        stage_observer_state={},
    )
    assert seen.get("factory_run_id") == FACTORY
    assert seen.get("campaign_id") == CAMPAIGN
    assert seen.get("run_id") == RUN


def test_adapter_mismatched_factory_identity_fails_closed(tmp_path: Path) -> None:
    db = tmp_path / "mismatch.sqlite3"
    _seed_graph(db, factory_status="SAFE_STOPPED", authoritative_run_id=FACTORY)
    connection = _open(db)
    try:
        with pytest.raises(FourTokenFactoryAdapterError, match="identity"):
            finalize_four_token_shared_terminal(
                connection,
                campaign_id=CAMPAIGN,
                campaign_run_id=RUN,
                factory_run_id="factory-mismatch",
                shared_terminalizer=lambda: {},
            )
    finally:
        connection.close()

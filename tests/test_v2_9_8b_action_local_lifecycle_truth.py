"""Disposable regression coverage for exception-path lifecycle truth."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from printer_v1.operator_cli.action_local_terminal_truth import (
    build_action_local_terminal_truth,
    merge_action_local_into_exception_envelope,
)
from printer_v1.operator_cli.window_15m_child_terminal import (
    ChildTerminalBinding,
    build_child_terminal_envelope,
)


CAUSE = (
    "FourTokenFactoryAdapterError:planned-lifecycle zero-attempt provenance "
    "requires a fresh transaction"
)


def _database(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE printer_memory_factory_campaign_runs (
                run_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                authoritative_run_id TEXT,
                run_state TEXT NOT NULL,
                first_terminal_cause TEXT,
                terminal_at TEXT
            );
            CREATE TABLE printer_memory_factory_runs (
                run_id TEXT PRIMARY KEY,
                run_status TEXT NOT NULL,
                started_at TEXT NOT NULL
            );
            CREATE TABLE printer_memory_factory_run_steps (
                id INTEGER PRIMARY KEY,
                run_id TEXT NOT NULL,
                step_key TEXT NOT NULL,
                step_status TEXT NOT NULL,
                started_at TEXT
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def _truth(path: Path, *, campaign: str, run: str) -> dict[str, object]:
    return build_action_local_terminal_truth(
        path,
        execution_id="execution-a",
        campaign_id=campaign,
        run_id=run,
        cycle_id="cycle-a",
        first_terminal_cause=CAUSE,
    )


def _binding() -> ChildTerminalBinding:
    return ChildTerminalBinding(
        terminal_path=Path("/tmp/child-terminal.json"),
        marker_path=Path("/tmp/application-marker.json"),
        authorization_id="AUTH_TEST",
        marker_sha256="a" * 64,
    )


def test_exception_reconstruction_projects_exact_started_lifecycle_to_child(tmp_path):
    database = tmp_path / "started.sqlite3"
    _database(database)
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "INSERT INTO printer_memory_factory_campaign_runs VALUES (?,?,?,?,?,?)",
            ("campaign-run-a", "campaign-a", "factory-a", "RUNNING", None, None),
        )
        connection.execute(
            "INSERT INTO printer_memory_factory_runs VALUES (?,?,?)",
            ("factory-a", "RUNNING", "2026-09-14T12:38:16+00:00"),
        )
        connection.execute(
            "INSERT INTO printer_memory_factory_run_steps VALUES (?,?,?,?,?)",
            (1, "factory-a", "snapshot-00", "SUCCEEDED", "2026-09-14T12:38:32+00:00"),
        )
        connection.commit()
    finally:
        connection.close()

    truth = _truth(database, campaign="campaign-a", run="campaign-run-a")
    envelope = merge_action_local_into_exception_envelope(
        {"status": "OPERATIONAL_COMMAND_BLOCKED"}, truth
    )
    child = build_child_terminal_envelope(
        binding=_binding(),
        source=envelope,
        mode="four-token-standard-four-hour-run",
        exit_code=1,
        success=False,
    )

    assert truth["factory_run_id"] == "factory-a"
    assert truth["lifecycle_started"] is True
    assert child["lifecycle_started"] is True
    assert child["failure_phase"] == "CAMPAIGN_LIFECYCLE_OR_CLOSEOUT"
    assert child["first_terminal_cause"] == CAUSE


def test_exception_reconstruction_proves_pre_lifecycle_without_factory_identity(tmp_path):
    database = tmp_path / "pre-lifecycle.sqlite3"
    _database(database)
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "INSERT INTO printer_memory_factory_campaign_runs VALUES (?,?,?,?,?,?)",
            ("campaign-run-a", "campaign-a", None, "RUNNING", None, None),
        )
        connection.commit()
    finally:
        connection.close()

    truth = _truth(database, campaign="campaign-a", run="campaign-run-a")
    child = build_child_terminal_envelope(
        binding=_binding(),
        source=merge_action_local_into_exception_envelope({}, truth),
        mode="four-token-standard-four-hour-run",
        exit_code=1,
        success=False,
    )

    assert truth["factory_run_id"] is None
    assert truth["lifecycle_started"] is False
    assert child["lifecycle_started"] is False
    assert child["failure_phase"] == "CAMPAIGN_PRE_LIFECYCLE"


def test_exception_reconstruction_keeps_unstarted_link_ambiguous(tmp_path):
    database = tmp_path / "ambiguous.sqlite3"
    _database(database)
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "INSERT INTO printer_memory_factory_campaign_runs VALUES (?,?,?,?,?,?)",
            ("campaign-run-a", "campaign-a", "factory-a", "RUNNING", None, None),
        )
        connection.execute(
            "INSERT INTO printer_memory_factory_runs VALUES (?,?,?)",
            ("factory-a", "RUNNING", "2026-09-14T12:38:16+00:00"),
        )
        connection.execute(
            "INSERT INTO printer_memory_factory_run_steps VALUES (?,?,?,?,?)",
            (1, "factory-a", "snapshot-00", "PENDING", None),
        )
        connection.commit()
    finally:
        connection.close()

    truth = _truth(database, campaign="campaign-a", run="campaign-run-a")

    assert truth["factory_run_id"] is None
    assert truth["lifecycle_started"] is None
    assert truth["first_terminal_cause"] == CAUSE

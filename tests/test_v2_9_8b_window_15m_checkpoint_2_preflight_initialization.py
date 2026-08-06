from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
from unittest import mock

import pytest

from printer_v1.db import apply_migrations
from printer_v1.db.migrate import canonical_migration_names
from printer_v1.operator_cli import campaign_persistence
from printer_v1.operator_cli import campaign_supervision
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli.action_local_mutation_recorder import (
    clear_action_local_mutation_recorder,
    install_action_local_mutation_recorder,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _migrated_db(tmp_path: Path) -> Path:
    db = tmp_path / "printer_v1.sqlite3"
    apply_migrations(db)
    return db


def _provenance() -> dict[str, object]:
    return {
        "git_head": "a" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": "2026-08-06T17:00:00+00:00",
    }


def _preflight(db: Path) -> dict[str, object]:
    migrations = canonical_migration_names()
    return {
        "database_path": str(db.resolve()),
        "database_sha256": _sha256(db),
        "migration_count": len(migrations),
        "latest_migration": migrations[-1],
        "git_provenance": _provenance(),
    }


def _backup(preflight: dict[str, object]) -> dict[str, object]:
    return {
        "source_identity": f"sha256:{preflight['database_sha256']}",
        "backup_hash": "b" * 64,
        "latest_rehearsed_migration": preflight["latest_migration"],
    }


def _paths(tmp_path: Path) -> dict[str, Path]:
    reports = tmp_path / "reports"
    reports.mkdir()
    return {
        "reports": reports,
        "lock": tmp_path / "campaign.lease.lock",
    }


def _authorization_facts(
    db: Path, preflight: dict[str, object]
) -> dict[str, object]:
    return {
        "authorization_id": "AUTH_CHECKPOINT_2",
        "manifest_sha256": "c" * 64,
        "application_marker_sha256": "d" * 64,
        "authorization_consumed_once": True,
        "invocation_count": 1,
        "allowed_invocation_count": 1,
        "automatic_retry_allowed": False,
        "manual_rerun_allowed": False,
        "resume_allowed": False,
        "restart_allowed": False,
        "successor_allowed": False,
        "authorized_db_path": str(db.resolve()),
        "authorized_pre_mutation_sha256": preflight["database_sha256"],
        "migration_count": preflight["migration_count"],
        "migration_head": preflight["latest_migration"],
    }


def _graph_counts(db: Path) -> dict[str, int]:
    connection = sqlite3.connect(db)
    try:
        return {
            "campaigns": int(connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaigns"
            ).fetchone()[0]),
            "configurations": int(connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_configurations"
            ).fetchone()[0]),
            "runs": int(connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_runs"
            ).fetchone()[0]),
            "cycles": int(connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles"
            ).fetchone()[0]),
        }
    finally:
        connection.close()


def _create(
    db: Path,
    tmp_path: Path,
    *,
    preflight: dict[str, object] | None = None,
):
    facts = preflight or _preflight(db)
    with mock.patch.object(command, "AUTHORITATIVE_DB", db):
        return command._create_campaign_command(
            execution_id="checkpoint2-execution",
            paths=_paths(tmp_path),
            preflight=facts,
            backup=_backup(facts),
            now="2026-08-06T17:00:00+00:00",
            operator_approved=True,
            authorization_runtime_facts=_authorization_facts(db, facts),
        )


def _clear_action_context() -> None:
    for key in command._ACTION_RUN_CONTEXT:
        command._ACTION_RUN_CONTEXT[key] = None


def test_authorized_database_drift_blocks_before_any_campaign_write(tmp_path: Path):
    db = _migrated_db(tmp_path)
    preflight = _preflight(db)
    connection = sqlite3.connect(db)
    try:
        connection.execute("CREATE TABLE checkpoint2_drift_marker(value INTEGER)")
        connection.commit()
    finally:
        connection.close()

    _clear_action_context()
    with pytest.raises(Exception, match="AUTHORIZED_DATABASE_CHANGED_BEFORE_FIRST_WRITE"):
        _create(db, tmp_path, preflight=preflight)

    assert _graph_counts(db) == {
        "campaigns": 0,
        "configurations": 0,
        "runs": 0,
        "cycles": 0,
    }
    assert command._ACTION_RUN_CONTEXT["campaign_id"] is None
    assert command._ACTION_RUN_CONTEXT["run_id"] is None
    assert command._ACTION_RUN_CONTEXT["cycle_id"] is None


def test_cycle_insert_failure_rolls_back_entire_initialization_graph(tmp_path: Path):
    db = _migrated_db(tmp_path)
    connection = sqlite3.connect(db)
    try:
        connection.execute(
            """CREATE TRIGGER checkpoint2_fail_cycle
               BEFORE INSERT ON printer_memory_factory_campaign_cycles
               BEGIN
                   SELECT RAISE(ABORT, 'CHECKPOINT2_CYCLE_INSERT_FAIL');
               END"""
        )
        connection.commit()
    finally:
        connection.close()

    _clear_action_context()
    with pytest.raises(Exception, match="CHECKPOINT2_CYCLE_INSERT_FAIL"):
        _create(db, tmp_path)

    assert _graph_counts(db) == {
        "campaigns": 0,
        "configurations": 0,
        "runs": 0,
        "cycles": 0,
    }
    assert command._ACTION_RUN_CONTEXT["campaign_id"] is None
    assert command._ACTION_RUN_CONTEXT["run_id"] is None
    assert command._ACTION_RUN_CONTEXT["cycle_id"] is None


def test_authorized_database_is_revalidated_while_first_write_lock_is_held(
    tmp_path: Path,
):
    db = _migrated_db(tmp_path)
    observed = {"locked": False, "calls": 0}

    def probe(path: Path) -> str:
        observed["calls"] += 1
        contender = sqlite3.connect(db, timeout=0.0)
        try:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                contender.execute("BEGIN IMMEDIATE")
            observed["locked"] = True
        finally:
            contender.close()
        return _sha256(Path(path))

    with mock.patch.object(
        campaign_persistence,
        "_sha256_file",
        side_effect=probe,
        create=True,
    ):
        _create(db, tmp_path)

    assert observed == {"locked": True, "calls": 1}


def test_initialization_records_all_exact_insert_and_update_identities(tmp_path: Path):
    db = _migrated_db(tmp_path)
    recorder = install_action_local_mutation_recorder()
    try:
        _create(db, tmp_path)
        frozen = recorder.freeze()
        assert frozen["inserted_rows"] == {
            "printer_memory_factory_campaigns": ["checkpoint2-execution-campaign"],
            "printer_memory_factory_campaign_configurations": [
                "checkpoint2-execution-configuration"
            ],
            "printer_memory_factory_campaign_runs": [
                "checkpoint2-execution-campaign-run"
            ],
            "printer_memory_factory_campaign_cycles": [
                "checkpoint2-execution-cycle"
            ],
        }
        assert frozen["updated_rows"] == {
            "printer_memory_factory_campaigns": ["checkpoint2-execution-campaign"],
            "printer_memory_factory_campaign_runs": [
                "checkpoint2-execution-campaign-run"
            ],
        }
        assert frozen["unknown_tables"] == []
        assert recorder.authoritative_write_count() == 6
    finally:
        clear_action_local_mutation_recorder()


def test_supervision_connection_failure_removes_only_newly_created_lock(
    tmp_path: Path,
):
    missing = tmp_path / "missing.sqlite3"
    lock = tmp_path / "campaign.lease.lock"
    with pytest.raises(campaign_supervision.CampaignSupervisionError, match="database missing"):
        campaign_supervision.acquire_campaign_supervision(
            missing,
            lock_path=lock,
            supervision_id="checkpoint2-supervision",
            campaign_id="checkpoint2-campaign",
            configuration_id="checkpoint2-configuration",
            run_id="checkpoint2-run",
            owner_id="checkpoint2-owner",
            lease_seconds=90,
            now=datetime(2026, 8, 6, 17, 0, tzinfo=timezone.utc),
        )
    assert not lock.exists()


def test_successful_initialization_graph_is_complete_before_supervision(tmp_path: Path):
    db = _migrated_db(tmp_path)
    command_value, cycle_id = _create(db, tmp_path)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        campaign = connection.execute(
            "SELECT campaign_state FROM printer_memory_factory_campaigns WHERE campaign_id=?",
            (command_value.campaign_id,),
        ).fetchone()
        run = connection.execute(
            "SELECT run_state FROM printer_memory_factory_campaign_runs WHERE run_id=?",
            (command_value.run_id,),
        ).fetchone()
        cycle = connection.execute(
            "SELECT cycle_state FROM printer_memory_factory_campaign_cycles WHERE cycle_id=?",
            (cycle_id,),
        ).fetchone()
        supervision_count = int(connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_supervision"
        ).fetchone()[0])
    finally:
        connection.close()

    assert campaign["campaign_state"] == "RUNNING"
    assert run["run_state"] == "RUNNING"
    assert cycle["cycle_state"] == "PLANNED"
    assert supervision_count == 0


def test_zero_source_preflight_failure_precedes_artifacts_and_campaign_graph(
    tmp_path: Path,
):
    db = _migrated_db(tmp_path)
    artifact_root = tmp_path / "artifacts"
    with (
        mock.patch.object(command, "AUTHORITATIVE_DB", db),
        mock.patch.object(command, "ARTIFACT_ROOT", artifact_root),
        mock.patch.object(
            command,
            "build_activation_preflight",
            side_effect=command.OperationalMemoryFactoryError("ZERO_SOURCE_PREFLIGHT_BLOCK"),
        ),
    ):
        with pytest.raises(command.OperationalMemoryFactoryError, match="ZERO_SOURCE_PREFLIGHT_BLOCK"):
            command.run_operational_campaign(operator_approved=True)

    assert not artifact_root.exists()
    assert _graph_counts(db) == {
        "campaigns": 0,
        "configurations": 0,
        "runs": 0,
        "cycles": 0,
    }

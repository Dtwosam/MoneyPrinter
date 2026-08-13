from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_active_work import campaign_active_work_report
from printer_v1.operator_cli.pre_admission_discovery_attempt import (
    PreAdmissionAttemptError,
    PreAdmissionAttemptState,
    create_scheduled_pre_admission_attempt,
    mark_pre_admission_attempt_running,
    pre_admission_attempt_lock_owner,
    terminalize_pre_admission_attempt,
)
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import claim_due_job


NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def connection(tmp_path):
    path = tmp_path / "attempt-scheduler.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES ('campaign-1','RUNNING','OPERATIONAL_PERSISTENT','db-1','policy-1')"
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json) VALUES (?,?,?,?,?)",
        ("configuration-1", "campaign-1", "a" * 64, "{}", "{}"),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("factory-1", "RUNNING", "WINDOW_15M", "OPERATIONAL_PERSISTENT", "a" * 64, "{}", NOW.isoformat()),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("campaign-run-1", "campaign-1", 1, "RUNNING", "factory-1", NOW.isoformat(), NOW.isoformat()),
    )
    connection.commit()
    try:
        yield connection
    finally:
        connection.close()


def _create(connection, *, attempt_id="attempt-1", factory="factory-1"):
    return create_scheduled_pre_admission_attempt(
        connection,
        attempt_id=attempt_id,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        configuration_id="configuration-1",
        authoritative_factory_run_id=factory,
        proposed_cycle_ordinal=2,
        proposed_cycle_id="cycle-2",
        cycle_cutoff=NOW,
        evaluated_at=NOW,
        selection_seed_identity="seed-2",
        scheduled_for=NOW,
        now=NOW,
    )


def test_attempt_and_exact_scheduler_owner_are_created_atomically(connection) -> None:
    attempt = _create(connection)
    job = connection.execute(
        "SELECT * FROM printer_scheduler_jobs WHERE id=?", (attempt.scheduler_job_id,)
    ).fetchone()
    assert job["job_kind"] == JobKind.PRE_ADMISSION_DISCOVERY_SELECTION.value
    assert job["job_name"] == "pre-admission-discovery-selection:attempt-1"
    assert job["target_table"] == "printer_pre_admission_discovery_attempts"
    assert job["target_id"] is None
    with pytest.raises(PreAdmissionAttemptError, match="ATTEMPT_ALREADY_EXISTS"):
        _create(connection)
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE job_kind=?",
        (JobKind.PRE_ADMISSION_DISCOVERY_SELECTION.value,),
    ).fetchone()[0] == 1


def test_wrong_factory_rolls_back_scheduler_creation(connection) -> None:
    with pytest.raises(PreAdmissionAttemptError, match="OWNERSHIP_MISMATCH"):
        _create(connection, factory="wrong-factory")
    assert connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0] == 0
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts"
    ).fetchone()[0] == 0


def test_running_requires_exact_canonical_scheduler_claim(connection) -> None:
    attempt = _create(connection)
    with pytest.raises(PreAdmissionAttemptError, match="SCHEDULER_CLAIM_MISMATCH"):
        mark_pre_admission_attempt_running(connection, attempt_id=attempt.attempt_id, now=NOW)
    wrong = claim_due_job(
        connection, job_id=attempt.scheduler_job_id, lock_owner="wrong-owner", now=NOW
    )
    assert wrong is LockResult.ACQUIRED
    with pytest.raises(PreAdmissionAttemptError, match="SCHEDULER_CLAIM_MISMATCH"):
        mark_pre_admission_attempt_running(connection, attempt_id=attempt.attempt_id, now=NOW)
    connection.execute(
        "UPDATE printer_scheduler_jobs SET status='PENDING',lock_owner=NULL,locked_at=NULL "
        "WHERE id=?",
        (attempt.scheduler_job_id,),
    )
    claimed = claim_due_job(
        connection,
        job_id=attempt.scheduler_job_id,
        lock_owner=pre_admission_attempt_lock_owner(attempt.attempt_id),
        now=NOW,
    )
    assert claimed is LockResult.ACQUIRED
    running = mark_pre_admission_attempt_running(
        connection, attempt_id=attempt.attempt_id, now=NOW
    )
    assert running.state is PreAdmissionAttemptState.RUNNING


def test_active_work_sees_only_planned_or_running_attempts(connection) -> None:
    attempt = _create(connection)
    report = campaign_active_work_report(
        connection,
        factory_run_id="factory-1",
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-2",
    )
    assert report["active_pre_admission_attempts"] == 1
    assert report["active_jobs"] == 1
    terminalize_pre_admission_attempt(
        connection,
        attempt_id=attempt.attempt_id,
        state=PreAdmissionAttemptState.BLOCKED,
        cause="HEALTH_BLOCKED",
        now=NOW,
    )
    terminal = campaign_active_work_report(
        connection,
        factory_run_id="factory-1",
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-2",
    )
    assert terminal["active_pre_admission_attempts"] == 0
    assert terminal["active_jobs"] == 0

"""RED/GREEN proofs for pre-admission attempt terminal cleanup in reconcile_campaign_terminal.

Product defect: campaign_active_work_report treats PLANNED/RUNNING pre-admission
attempts as active work, but reconcile_campaign_terminal cancelled attributable
Scheduler jobs without terminalizing the attempts themselves.
"""

from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_active_work import campaign_active_work_report
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES
from printer_v1.operator_cli.pre_admission_discovery_attempt import (
    PreAdmissionAttemptState,
    create_pre_admission_attempt,
    create_scheduled_pre_admission_attempt,
    mark_pre_admission_attempt_running,
    pre_admission_attempt_lock_owner,
    terminalize_pre_admission_attempt,
)
from printer_v1.operator_cli.unified_terminal_closure import reconcile_campaign_terminal
from printer_v1.scheduler.contracts import LockResult
from printer_v1.scheduler.scheduler import claim_due_job


NOW = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
CAUSE = "OPERATIONAL_CAMPAIGN_FAILED:FourTokenFactoryAdapterError"


def _seed_campaign_graph(
    connection: sqlite3.Connection,
    *,
    campaign_id: str = "campaign-1",
    run_id: str = "campaign-run-1",
    cycle_id: str = "cycle-1",
    factory_run_id: str = "factory-1",
    configuration_id: str = "configuration-1",
) -> None:
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        (
            campaign_id,
            "RUNNING",
            "OPERATIONAL_PERSISTENT",
            "db-1",
            "policy-1",
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json,created_at) VALUES (?,?,?,?,?,?)",
        (configuration_id, campaign_id, "a" * 64, "{}", "{}", NOW.isoformat()),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            factory_run_id,
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            "{}",
            NOW.isoformat(),
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        (
            run_id,
            campaign_id,
            1,
            "RUNNING",
            factory_run_id,
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_cycles("
        "cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            cycle_id,
            campaign_id,
            run_id,
            1,
            "PLANNED",
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    connection.commit()


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "pre-admission-terminal-cleanup.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        _seed_campaign_graph(connection)
    finally:
        connection.close()
    return path


def _open(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _locked_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in LOCKED_CAPABILITY_TABLES
    }


def test_planned_attempt_and_pending_job_are_cancelled_cleanly(db_path) -> None:
    connection = _open(db_path)
    try:
        attempt = create_scheduled_pre_admission_attempt(
            connection,
            attempt_id="attempt-planned",
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            configuration_id="configuration-1",
            authoritative_factory_run_id="factory-1",
            proposed_cycle_ordinal=2,
            proposed_cycle_id="cycle-2",
            cycle_cutoff=NOW,
            evaluated_at=NOW,
            selection_seed_identity="seed-2",
            scheduled_for=NOW,
            now=NOW,
        )
        before_locks = _locked_counts(connection)
        dirty = campaign_active_work_report(
            connection,
            factory_run_id="factory-1",
            campaign_id="campaign-1",
            run_id="campaign-run-1",
            cycle_id="cycle-1",
        )
        assert dirty["active_pre_admission_attempts"] == 1
        assert dirty["clean_terminal"] is False
    finally:
        connection.close()

    result = reconcile_campaign_terminal(
        db_path,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        terminal_cause=CAUSE,
        run_status="FAILED",
        factory_run_id="factory-1",
        lifecycle_started=False,
        now=NOW.isoformat(),
    )
    assert result["clean_terminal"] is True

    connection = _open(db_path)
    try:
        job = connection.execute(
            "SELECT status, locked_at, lock_owner, finished_at FROM printer_scheduler_jobs "
            "WHERE id=?",
            (attempt.scheduler_job_id,),
        ).fetchone()
        row = connection.execute(
            "SELECT attempt_state, first_terminal_cause, terminal_at FROM "
            "printer_pre_admission_discovery_attempts WHERE attempt_id=?",
            ("attempt-planned",),
        ).fetchone()
        assert job["status"] == "CANCELLED"
        assert job["locked_at"] is None
        assert job["lock_owner"] is None
        assert job["finished_at"] is not None
        assert row["attempt_state"] == "CANCELLED"
        assert row["first_terminal_cause"] == CAUSE
        assert row["terminal_at"] is not None
        assert _locked_counts(connection) == before_locks
        assert all(value == 0 for value in _locked_counts(connection).values())
    finally:
        connection.close()


def test_running_attempt_and_locked_running_job_are_cancelled_cleanly(db_path) -> None:
    connection = _open(db_path)
    try:
        attempt = create_scheduled_pre_admission_attempt(
            connection,
            attempt_id="attempt-running",
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            configuration_id="configuration-1",
            authoritative_factory_run_id="factory-1",
            proposed_cycle_ordinal=2,
            proposed_cycle_id="cycle-2",
            cycle_cutoff=NOW,
            evaluated_at=NOW,
            selection_seed_identity="seed-running",
            scheduled_for=NOW,
            now=NOW,
        )
        claimed = claim_due_job(
            connection,
            job_id=attempt.scheduler_job_id,
            lock_owner=pre_admission_attempt_lock_owner(attempt.attempt_id),
            now=NOW,
        )
        assert claimed is LockResult.ACQUIRED
        mark_pre_admission_attempt_running(
            connection, attempt_id=attempt.attempt_id, now=NOW
        )
        job_before = connection.execute(
            "SELECT status, locked_at, lock_owner FROM printer_scheduler_jobs WHERE id=?",
            (attempt.scheduler_job_id,),
        ).fetchone()
        assert job_before["status"] == "RUNNING"
        assert job_before["lock_owner"] is not None
    finally:
        connection.close()

    result = reconcile_campaign_terminal(
        db_path,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        terminal_cause=CAUSE,
        run_status="FAILED",
        factory_run_id="factory-1",
        lifecycle_started=False,
        now=NOW.isoformat(),
    )
    assert result["clean_terminal"] is True

    connection = _open(db_path)
    try:
        job = connection.execute(
            "SELECT status, locked_at, lock_owner FROM printer_scheduler_jobs WHERE id=?",
            (attempt.scheduler_job_id,),
        ).fetchone()
        row = connection.execute(
            "SELECT attempt_state, first_terminal_cause, terminal_at FROM "
            "printer_pre_admission_discovery_attempts WHERE attempt_id=?",
            ("attempt-running",),
        ).fetchone()
        assert job["status"] == "CANCELLED"
        assert job["locked_at"] is None
        assert job["lock_owner"] is None
        assert row["attempt_state"] == "CANCELLED"
        assert row["first_terminal_cause"] == CAUSE
        assert row["terminal_at"] is not None
    finally:
        connection.close()


def test_second_reconciliation_is_idempotent_for_cancelled_attempt(db_path) -> None:
    connection = _open(db_path)
    try:
        attempt = create_scheduled_pre_admission_attempt(
            connection,
            attempt_id="attempt-idempotent",
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            configuration_id="configuration-1",
            authoritative_factory_run_id="factory-1",
            proposed_cycle_ordinal=2,
            proposed_cycle_id="cycle-2",
            cycle_cutoff=NOW,
            evaluated_at=NOW,
            selection_seed_identity="seed-idempotent",
            scheduled_for=NOW,
            now=NOW,
        )
    finally:
        connection.close()

    first = reconcile_campaign_terminal(
        db_path,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        terminal_cause=CAUSE,
        run_status="FAILED",
        factory_run_id="factory-1",
        now=NOW.isoformat(),
    )
    assert first["clean_terminal"] is True

    connection = _open(db_path)
    try:
        before = connection.execute(
            "SELECT attempt_state, first_terminal_cause, terminal_at, updated_at, "
            "scheduler_job_id FROM printer_pre_admission_discovery_attempts "
            "WHERE attempt_id=?",
            ("attempt-idempotent",),
        ).fetchone()
        job_before = connection.execute(
            "SELECT status, finished_at, updated_at, locked_at, lock_owner "
            "FROM printer_scheduler_jobs WHERE id=?",
            (attempt.scheduler_job_id,),
        ).fetchone()
        before_map = {k: before[k] for k in before.keys()}
        job_before_map = {k: job_before[k] for k in job_before.keys()}
    finally:
        connection.close()

    second = reconcile_campaign_terminal(
        db_path,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        terminal_cause="SECOND_CAUSE_MUST_NOT_REWRITE",
        run_status="FAILED",
        factory_run_id="factory-1",
        now=(NOW.replace(minute=30)).isoformat(),
    )
    assert second["clean_terminal"] is True
    assert set(second["records"].values()) == {"already_terminal"}

    connection = _open(db_path)
    try:
        after = connection.execute(
            "SELECT attempt_state, first_terminal_cause, terminal_at, updated_at, "
            "scheduler_job_id FROM printer_pre_admission_discovery_attempts "
            "WHERE attempt_id=?",
            ("attempt-idempotent",),
        ).fetchone()
        job_after = connection.execute(
            "SELECT status, finished_at, updated_at, locked_at, lock_owner "
            "FROM printer_scheduler_jobs WHERE id=?",
            (attempt.scheduler_job_id,),
        ).fetchone()
        assert {k: after[k] for k in after.keys()} == before_map
        assert {k: job_after[k] for k in job_after.keys()} == job_before_map
        assert after["first_terminal_cause"] == CAUSE
    finally:
        connection.close()


def test_already_terminal_successful_attempt_is_not_rewritten(db_path) -> None:
    """A completed terminal pre-admission outcome (NO_PAIR) must stay immutable."""
    connection = _open(db_path)
    try:
        attempt = create_scheduled_pre_admission_attempt(
            connection,
            attempt_id="attempt-terminal-success",
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            configuration_id="configuration-1",
            authoritative_factory_run_id="factory-1",
            proposed_cycle_ordinal=2,
            proposed_cycle_id="cycle-2",
            cycle_cutoff=NOW,
            evaluated_at=NOW,
            selection_seed_identity="seed-terminal-success",
            scheduled_for=NOW,
            now=NOW,
        )
        claimed = claim_due_job(
            connection,
            job_id=attempt.scheduler_job_id,
            lock_owner=pre_admission_attempt_lock_owner(attempt.attempt_id),
            now=NOW,
        )
        assert claimed is LockResult.ACQUIRED
        mark_pre_admission_attempt_running(
            connection, attempt_id=attempt.attempt_id, now=NOW
        )
        terminalize_pre_admission_attempt(
            connection,
            attempt_id=attempt.attempt_id,
            state=PreAdmissionAttemptState.NO_PAIR,
            cause="NO_EXACT_PAIR",
            now=NOW,
        )
        from printer_v1.scheduler.scheduler import cancel_job

        cancel_job(connection, job_id=attempt.scheduler_job_id, now=NOW)
        connection.commit()
        before = connection.execute(
            "SELECT * FROM printer_pre_admission_discovery_attempts WHERE attempt_id=?",
            ("attempt-terminal-success",),
        ).fetchone()
        before_map = {k: before[k] for k in before.keys()}
    finally:
        connection.close()

    result = reconcile_campaign_terminal(
        db_path,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        terminal_cause=CAUSE,
        run_status="FAILED",
        factory_run_id="factory-1",
        now=NOW.isoformat(),
    )
    assert result["clean_terminal"] is True

    connection = _open(db_path)
    try:
        after = connection.execute(
            "SELECT * FROM printer_pre_admission_discovery_attempts WHERE attempt_id=?",
            ("attempt-terminal-success",),
        ).fetchone()
        assert {k: after[k] for k in after.keys()} == before_map
        assert after["attempt_state"] == "NO_PAIR"
        assert after["first_terminal_cause"] == "NO_EXACT_PAIR"
    finally:
        connection.close()


def test_only_exact_campaign_owned_attempts_are_touched(db_path) -> None:
    connection = _open(db_path)
    try:
        _seed_campaign_graph(
            connection,
            campaign_id="campaign-other",
            run_id="campaign-run-other",
            cycle_id="cycle-other",
            factory_run_id="factory-other",
            configuration_id="configuration-other",
        )
        owned = create_scheduled_pre_admission_attempt(
            connection,
            attempt_id="attempt-owned",
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            configuration_id="configuration-1",
            authoritative_factory_run_id="factory-1",
            proposed_cycle_ordinal=2,
            proposed_cycle_id="cycle-2",
            cycle_cutoff=NOW,
            evaluated_at=NOW,
            selection_seed_identity="seed-owned",
            scheduled_for=NOW,
            now=NOW,
        )
        other = create_scheduled_pre_admission_attempt(
            connection,
            attempt_id="attempt-other",
            campaign_id="campaign-other",
            campaign_run_id="campaign-run-other",
            configuration_id="configuration-other",
            authoritative_factory_run_id="factory-other",
            proposed_cycle_ordinal=2,
            proposed_cycle_id="cycle-other-2",
            cycle_cutoff=NOW,
            evaluated_at=NOW,
            selection_seed_identity="seed-other",
            scheduled_for=NOW,
            now=NOW,
        )
    finally:
        connection.close()

    result = reconcile_campaign_terminal(
        db_path,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        terminal_cause=CAUSE,
        run_status="FAILED",
        factory_run_id="factory-1",
        now=NOW.isoformat(),
    )
    assert result["clean_terminal"] is True

    connection = _open(db_path)
    try:
        owned_row = connection.execute(
            "SELECT attempt_state FROM printer_pre_admission_discovery_attempts "
            "WHERE attempt_id='attempt-owned'"
        ).fetchone()
        other_row = connection.execute(
            "SELECT attempt_state FROM printer_pre_admission_discovery_attempts "
            "WHERE attempt_id='attempt-other'"
        ).fetchone()
        owned_job = connection.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id=?",
            (owned.scheduler_job_id,),
        ).fetchone()
        other_job = connection.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id=?",
            (other.scheduler_job_id,),
        ).fetchone()
        assert owned_row["attempt_state"] == "CANCELLED"
        assert owned_job["status"] == "CANCELLED"
        assert other_row["attempt_state"] == "PLANNED"
        assert other_job["status"] == "PENDING"
    finally:
        connection.close()


def test_normal_successful_campaign_without_pre_admission_remains_clean(db_path) -> None:
    result = reconcile_campaign_terminal(
        db_path,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        terminal_cause="COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
        run_status="COMPLETED",
        factory_run_id="factory-1",
        lifecycle_started=True,
        now=NOW.isoformat(),
    )
    assert result["clean_terminal"] is True
    assert result["new_state"] == "TERMINAL_COMPLETED"
    assert result["restart_created"] is False
    assert result["successor_created"] is False

    connection = _open(db_path)
    try:
        assert connection.execute(
            "SELECT campaign_state FROM printer_memory_factory_campaigns "
            "WHERE campaign_id='campaign-1'"
        ).fetchone()[0] == "TERMINAL_COMPLETED"
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts"
        ).fetchone()[0] == 0
        assert all(value == 0 for value in _locked_counts(connection).values())
    finally:
        connection.close()


def test_already_cancelled_attempt_stays_cancelled_without_cause_rewrite(db_path) -> None:
    connection = _open(db_path)
    try:
        attempt = create_scheduled_pre_admission_attempt(
            connection,
            attempt_id="attempt-already-cancelled",
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            configuration_id="configuration-1",
            authoritative_factory_run_id="factory-1",
            proposed_cycle_ordinal=2,
            proposed_cycle_id="cycle-2",
            cycle_cutoff=NOW,
            evaluated_at=NOW,
            selection_seed_identity="seed-cancelled",
            scheduled_for=NOW,
            now=NOW,
        )
        from printer_v1.scheduler.scheduler import cancel_job

        cancel_job(connection, job_id=attempt.scheduler_job_id, now=NOW)
        terminalize_pre_admission_attempt(
            connection,
            attempt_id=attempt.attempt_id,
            state=PreAdmissionAttemptState.CANCELLED,
            cause="PREEXISTING_CANCEL",
            now=NOW,
        )
        connection.commit()
        before = connection.execute(
            "SELECT attempt_state, first_terminal_cause, terminal_at FROM "
            "printer_pre_admission_discovery_attempts WHERE attempt_id=?",
            (attempt.attempt_id,),
        ).fetchone()
    finally:
        connection.close()

    result = reconcile_campaign_terminal(
        db_path,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        terminal_cause=CAUSE,
        run_status="FAILED",
        factory_run_id="factory-1",
        now=NOW.isoformat(),
    )
    assert result["clean_terminal"] is True

    connection = _open(db_path)
    try:
        after = connection.execute(
            "SELECT attempt_state, first_terminal_cause, terminal_at FROM "
            "printer_pre_admission_discovery_attempts WHERE attempt_id=?",
            (attempt.attempt_id,),
        ).fetchone()
        assert after["attempt_state"] == "CANCELLED"
        assert after["first_terminal_cause"] == "PREEXISTING_CANCEL"
        assert after["terminal_at"] == before["terminal_at"]
    finally:
        connection.close()

"""Follow-up proofs for independent review defects in interrupted four-token repair."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import time
from unittest.mock import patch

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import campaign_supervision as supervision
from printer_v1.operator_cli.campaign_ownership import create_campaign_run
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.campaign_supervision import (
    acquire_campaign_supervision,
    renew_campaign_lease,
)
from printer_v1.operator_cli.four_token_factory_adapter import (
    FourTokenFactoryAdapterError,
    parent_interrupted_attempt_cause,
    reconcile_parent_interrupted_open_pre_admission_attempts,
)
from printer_v1.operator_cli.pre_admission_discovery_attempt import (
    PreAdmissionAttemptState,
    create_scheduled_pre_admission_attempt,
    mark_pre_admission_attempt_running,
    terminalize_pre_admission_attempt,
)


LEASE_NOW = datetime(2026, 8, 28, 22, 0, 0, tzinfo=timezone.utc)
INTERRUPT_NOW = datetime(2026, 8, 28, 22, 18, 12, tzinfo=timezone.utc)
PARENT_CAUSE = "LEASE_RENEWAL_SQLITE_LOCKED"
EXPECTED_INTERRUPT_CAUSE = parent_interrupted_attempt_cause(PARENT_CAUSE)


def _lease_provenance() -> dict[str, object]:
    return {
        "git_head": "d" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": LEASE_NOW.isoformat(),
    }


def _lease_db() -> tuple[Path, dict[str, str]]:
    root = Path(tempfile.mkdtemp(prefix="v2-9-8b-followup-lease-"))
    db = root / "proof.sqlite3"
    apply_migrations(db)
    identities = {
        "supervision_id": "sup-followup-lease",
        "campaign_id": "campaign-followup-lease",
        "configuration_id": "configuration-followup-lease",
        "run_id": "campaign-run-followup-lease",
        "owner_id": "owner-followup-lease",
    }
    create_campaign(
        db,
        campaign_id=identities["campaign_id"],
        configuration_id=identities["configuration_id"],
        configuration={"slots": 2},
        launch_provenance=_lease_provenance(),
        db_mode=DB_MODE_PROOF_ISOLATED,
        db_target_identity="fixture",
        proof_source_db_identity="fixture-source",
        policy_version="v2-9.8b-followup-lease",
    )
    connection = sqlite3.connect(db)
    connection.execute("PRAGMA foreign_keys=ON")
    create_campaign_run(
        connection,
        campaign_id=identities["campaign_id"],
        run_id=identities["run_id"],
        run_ordinal=1,
        now=LEASE_NOW.isoformat(),
    )
    connection.execute(
        "UPDATE printer_memory_factory_campaigns SET campaign_state='RUNNING' "
        "WHERE campaign_id=?",
        (identities["campaign_id"],),
    )
    connection.execute(
        "UPDATE printer_memory_factory_campaign_runs SET run_state='RUNNING' "
        "WHERE run_id=?",
        (identities["run_id"],),
    )
    connection.commit()
    connection.close()
    acquire_campaign_supervision(
        db,
        lock_path=root / "campaign.lease.lock",
        lease_seconds=16.5,
        now=LEASE_NOW,
        **identities,
    )
    return db, identities


def test_followup_lease_rechecks_safety_before_each_inner_sqlite_wait() -> None:
    db, identities = _lease_db()
    blocker = sqlite3.connect(db, timeout=0.1)
    blocker.execute("BEGIN IMMEDIATE")
    blocker.execute("CREATE TABLE IF NOT EXISTS _hold(x INTEGER)")
    configured_waits: list[float] = []
    real_configure = supervision._configure_busy_timeout

    def record_wait(connection: sqlite3.Connection, *, busy_timeout_seconds: float) -> None:
        configured_waits.append(float(busy_timeout_seconds))
        real_configure(connection, busy_timeout_seconds=busy_timeout_seconds)

    started = time.monotonic()
    try:
        with patch.object(supervision, "SQLITE_BUSY_TIMEOUT_SECONDS", 0.4), patch.object(
            supervision, "SQLITE_BUSY_RETRY_SECONDS", 0.01
        ), patch.object(supervision, "SQLITE_BUSY_MAX_ATTEMPTS", 5), patch.object(
            supervision, "LEASE_CONTENTION_OUTER_MAX_ATTEMPTS", 1
        ), patch.object(supervision, "_configure_busy_timeout", record_wait):
            result = renew_campaign_lease(
                db,
                lease_seconds=90,
                now=LEASE_NOW + timedelta(seconds=0.1),
                **identities,
            )
    finally:
        blocker.rollback()
        blocker.close()
    elapsed = time.monotonic() - started

    assert result["renewal_confirmed"] is False
    assert result["suggested_terminal_cause"] == "LEASE_RENEWAL_SQLITE_LOCKED"
    assert result["db_ledger_advanced"] is False
    # The baseline implementation reaches all five inner waits. The corrected
    # path must stop earlier when another planned block would consume the 15s
    # remaining-lease safety margin.
    assert 1 <= len(configured_waits) < 5
    assert elapsed < 2.0


def _seed_interrupt(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        (
            "campaign-1",
            "RUNNING",
            "OPERATIONAL_PERSISTENT",
            "db-1",
            "policy-1",
            INTERRUPT_NOW.isoformat(),
            INTERRUPT_NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json,created_at) VALUES (?,?,?,?,?,?)",
        (
            "configuration-1",
            "campaign-1",
            "a" * 64,
            "{}",
            "{}",
            INTERRUPT_NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at,"
        "created_at,updated_at,stop_reason) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            "factory-1",
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            "{}",
            INTERRUPT_NOW.isoformat(),
            INTERRUPT_NOW.isoformat(),
            INTERRUPT_NOW.isoformat(),
            PARENT_CAUSE,
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        (
            "campaign-run-1",
            "campaign-1",
            1,
            "RUNNING",
            "factory-1",
            INTERRUPT_NOW.isoformat(),
            INTERRUPT_NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_cycles("
        "cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,first_terminal_cause,"
        "terminal_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "cycle-1",
            "campaign-1",
            "campaign-run-1",
            1,
            "TERMINAL_BLOCKED",
            PARENT_CAUSE,
            INTERRUPT_NOW.isoformat(),
            INTERRUPT_NOW.isoformat(),
            INTERRUPT_NOW.isoformat(),
        ),
    )
    connection.commit()


def _interrupt_db() -> sqlite3.Connection:
    root = Path(tempfile.mkdtemp(prefix="v2-9-8b-followup-interrupt-"))
    db = root / "proof.sqlite3"
    apply_migrations(db)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    _seed_interrupt(connection)
    return connection


def _make_attempt(connection: sqlite3.Connection, *, running: bool) -> tuple[str, int]:
    from printer_v1.operator_cli.pre_admission_discovery_attempt import (
        pre_admission_attempt_lock_owner,
    )
    from printer_v1.scheduler.contracts import LockResult
    from printer_v1.scheduler.scheduler import claim_due_job

    attempt = create_scheduled_pre_admission_attempt(
        connection,
        attempt_id="attempt-c2",
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        configuration_id="configuration-1",
        authoritative_factory_run_id="factory-1",
        proposed_cycle_ordinal=2,
        proposed_cycle_id="cycle-2",
        cycle_cutoff=INTERRUPT_NOW,
        evaluated_at=INTERRUPT_NOW,
        selection_seed_identity="seed-2",
        scheduled_for=INTERRUPT_NOW,
        now=INTERRUPT_NOW,
    )
    if running:
        claimed = claim_due_job(
            connection,
            job_id=attempt.scheduler_job_id,
            lock_owner=pre_admission_attempt_lock_owner(attempt.attempt_id),
            now=INTERRUPT_NOW,
        )
        assert claimed is LockResult.ACQUIRED
        mark_pre_admission_attempt_running(
            connection,
            attempt_id=attempt.attempt_id,
            now=INTERRUPT_NOW,
        )
    connection.commit()
    return attempt.attempt_id, int(attempt.scheduler_job_id)


def _assert_attempt_unchanged(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    expected_state: str,
    expected_cause: str | None,
) -> None:
    row = connection.execute(
        "SELECT attempt_state,first_terminal_cause FROM "
        "printer_pre_admission_discovery_attempts WHERE attempt_id=?",
        (attempt_id,),
    ).fetchone()
    assert tuple(row) == (expected_state, expected_cause)


@pytest.mark.parametrize("terminal_status", ["FAILED", "SUCCEEDED", "SKIPPED"])
def test_followup_running_attempt_rejects_non_cancelled_terminal_job(
    terminal_status: str,
) -> None:
    connection = _interrupt_db()
    try:
        attempt_id, job_id = _make_attempt(connection, running=True)
        connection.execute(
            "UPDATE printer_scheduler_jobs SET status=?,finished_at=?,"
            "locked_at=NULL,lock_owner=NULL,updated_at=? WHERE id=?",
            (
                terminal_status,
                INTERRUPT_NOW.isoformat(),
                INTERRUPT_NOW.isoformat(),
                job_id,
            ),
        )
        connection.commit()
        with pytest.raises(FourTokenFactoryAdapterError, match="Scheduler"):
            reconcile_parent_interrupted_open_pre_admission_attempts(
                connection,
                campaign_id="campaign-1",
                campaign_run_id="campaign-run-1",
                factory_run_id="factory-1",
                now=INTERRUPT_NOW,
            )
        _assert_attempt_unchanged(
            connection,
            attempt_id=attempt_id,
            expected_state="RUNNING",
            expected_cause=None,
        )
    finally:
        connection.close()


@pytest.mark.parametrize("terminal_status", ["FAILED", "SUCCEEDED"])
def test_followup_exact_cancelled_attempt_rejects_non_cancelled_terminal_job(
    terminal_status: str,
) -> None:
    connection = _interrupt_db()
    try:
        attempt_id, job_id = _make_attempt(connection, running=False)
        terminalize_pre_admission_attempt(
            connection,
            attempt_id=attempt_id,
            state=PreAdmissionAttemptState.CANCELLED,
            cause=EXPECTED_INTERRUPT_CAUSE,
            now=INTERRUPT_NOW,
        )
        connection.execute(
            "UPDATE printer_scheduler_jobs SET status=?,finished_at=?,"
            "locked_at=NULL,lock_owner=NULL,updated_at=? WHERE id=?",
            (
                terminal_status,
                INTERRUPT_NOW.isoformat(),
                INTERRUPT_NOW.isoformat(),
                job_id,
            ),
        )
        connection.commit()
        with pytest.raises(FourTokenFactoryAdapterError, match="Scheduler"):
            reconcile_parent_interrupted_open_pre_admission_attempts(
                connection,
                campaign_id="campaign-1",
                campaign_run_id="campaign-run-1",
                factory_run_id="factory-1",
                now=INTERRUPT_NOW,
            )
        _assert_attempt_unchanged(
            connection,
            attempt_id=attempt_id,
            expected_state="CANCELLED",
            expected_cause=EXPECTED_INTERRUPT_CAUSE,
        )
    finally:
        connection.close()


def test_followup_terminal_job_with_lock_fields_fails_closed() -> None:
    connection = _interrupt_db()
    try:
        attempt_id, job_id = _make_attempt(connection, running=True)
        connection.execute(
            "UPDATE printer_scheduler_jobs SET status='FAILED',finished_at=?,"
            "locked_at=?,lock_owner='contradictory-owner',updated_at=? WHERE id=?",
            (
                INTERRUPT_NOW.isoformat(),
                INTERRUPT_NOW.isoformat(),
                INTERRUPT_NOW.isoformat(),
                job_id,
            ),
        )
        connection.commit()
        with pytest.raises(FourTokenFactoryAdapterError, match="Scheduler"):
            reconcile_parent_interrupted_open_pre_admission_attempts(
                connection,
                campaign_id="campaign-1",
                campaign_run_id="campaign-run-1",
                factory_run_id="factory-1",
                now=INTERRUPT_NOW,
            )
        _assert_attempt_unchanged(
            connection,
            attempt_id=attempt_id,
            expected_state="RUNNING",
            expected_cause=None,
        )
    finally:
        connection.close()

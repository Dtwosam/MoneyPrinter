"""Focused proofs for parent-interrupted Cycle-2 cleanup (design C1–C12)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any
from unittest.mock import patch

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_supervision import (
    acquire_campaign_supervision,
    cleanup_campaign_supervision,
)
from printer_v1.operator_cli.four_token_factory_adapter import (
    FourTokenFactoryAdapterError,
    PARENT_CAMPAIGN_INTERRUPTED_PREFIX,
    finalize_four_token_shared_terminal,
    parent_interrupted_attempt_cause,
    reconcile_parent_interrupted_open_pre_admission_attempts,
)
from printer_v1.operator_cli.pre_admission_discovery_attempt import (
    PreAdmissionAttemptState,
    create_scheduled_pre_admission_attempt,
    mark_pre_admission_attempt_running,
    terminalize_pre_admission_attempt,
)
from printer_v1.operator_cli.unified_terminal_closure import reconcile_campaign_terminal


NOW = datetime(2026, 8, 28, 22, 18, 12, tzinfo=timezone.utc)
PARENT_CAUSE = "LEASE_RENEWAL_SQLITE_LOCKED"
EXPECTED_CAUSE = parent_interrupted_attempt_cause(PARENT_CAUSE)


def _seed(connection: sqlite3.Connection) -> None:
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
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json,created_at) VALUES (?,?,?,?,?,?)",
        ("configuration-1", "campaign-1", "a" * 64, "{}", "{}", NOW.isoformat()),
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
            NOW.isoformat(),
            NOW.isoformat(),
            NOW.isoformat(),
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
            NOW.isoformat(),
            NOW.isoformat(),
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
            NOW.isoformat(),
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    connection.commit()


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "interrupt-cleanup.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        _seed(connection)
    finally:
        connection.close()
    return path


def _open(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _make_open_attempt(
    connection: sqlite3.Connection, *, running: bool = False
) -> tuple[str, int]:
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
        cycle_cutoff=NOW,
        evaluated_at=NOW,
        selection_seed_identity="seed-2",
        scheduled_for=NOW,
        now=NOW,
    )
    if running:
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
    connection.commit()
    return attempt.attempt_id, int(attempt.scheduler_job_id)


def _acquire_supervision(db_path: Path) -> dict[str, str]:
    identities = {
        "supervision_id": "sup-1",
        "campaign_id": "campaign-1",
        "configuration_id": "configuration-1",
        "run_id": "campaign-run-1",
        "owner_id": "owner-1",
    }
    acquire_campaign_supervision(
        db_path,
        lock_path=db_path.parent / "campaign.lease.lock",
        now=NOW,
        **identities,
    )
    return identities


def test_c_atomic_state_a_and_finalize_shape(db_path: Path) -> None:
    connection = _open(db_path)
    attempt_id, job_id = _make_open_attempt(connection, running=True)
    report = reconcile_parent_interrupted_open_pre_admission_attempts(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        now=NOW,
    )
    connection.commit()
    row = connection.execute(
        "SELECT attempt_state,first_terminal_cause FROM "
        "printer_pre_admission_discovery_attempts WHERE attempt_id=?",
        (attempt_id,),
    ).fetchone()
    job = connection.execute(
        "SELECT status FROM printer_scheduler_jobs WHERE id=?", (job_id,)
    ).fetchone()
    assert report["reconciled"] is True
    assert report["replay_state"] == "A"
    assert row[0] == "CANCELLED"
    assert row[1] == EXPECTED_CAUSE
    assert EXPECTED_CAUSE.startswith(PARENT_CAMPAIGN_INTERRUPTED_PREFIX)
    assert "NO_PAIR" not in EXPECTED_CAUSE
    assert job[0] == "CANCELLED"

    identities = _acquire_supervision(db_path)

    def shared_terminalizer() -> dict[str, Any]:
        reconcile_campaign_terminal(
            db_path,
            campaign_id="campaign-1",
            run_id="campaign-run-1",
            cycle_id="cycle-1",
            terminal_cause=PARENT_CAUSE,
            run_status="SAFE_STOPPED",
            factory_run_id="factory-1",
            lifecycle_started=True,
            now=NOW.isoformat(),
        )
        cleanup = cleanup_campaign_supervision(
            db_path,
            terminal_status="FAILED",
            first_terminal_cause=PARENT_CAUSE,
            now=NOW,
            **identities,
        )
        return {
            "clean_terminal": True,
            "lease_released": bool(cleanup.get("lease_released")),
            "cleanup": cleanup,
        }

    result = finalize_four_token_shared_terminal(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        shared_terminalizer=shared_terminalizer,
        now=NOW,
    )
    connection.close()
    assert result["admitted_shape"] == "ONE_CYCLE_CAMPAIGN_INTERRUPTED_OPEN_ATTEMPT"
    assert result["shared_terminalized"] is True
    assert (db_path.parent / "campaign.lease.lock").exists() is False
    verify = _open(db_path)
    try:
        assert tuple(
            verify.execute(
                "SELECT attempt_state,first_terminal_cause FROM "
                "printer_pre_admission_discovery_attempts WHERE attempt_id=?",
                (attempt_id,),
            ).fetchone()
        ) == ("CANCELLED", EXPECTED_CAUSE)
        assert (
            verify.execute(
                "SELECT status FROM printer_scheduler_jobs WHERE id=?", (job_id,)
            ).fetchone()[0]
            == "CANCELLED"
        )
        assert (
            verify.execute(
                "SELECT supervision_state FROM "
                "printer_memory_factory_campaign_supervision"
            ).fetchone()[0]
            == "TERMINAL"
        )
        assert verify.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert verify.execute("PRAGMA foreign_key_check").fetchall() == []
        assert (
            verify.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs "
                "WHERE status IN ('PENDING','RUNNING','COOLDOWN') "
                "OR locked_at IS NOT NULL OR lock_owner IS NOT NULL"
            ).fetchone()[0]
            == 0
        )
        # Cycle-1 evidence preserved.
        assert tuple(
            verify.execute(
                "SELECT cycle_state,first_terminal_cause FROM "
                "printer_memory_factory_campaign_cycles WHERE cycle_id='cycle-1'"
            ).fetchone()
        ) == ("TERMINAL_BLOCKED", PARENT_CAUSE)
    finally:
        verify.close()


def test_replay_b_c_d_and_conflicting_cause(db_path: Path) -> None:
    connection = _open(db_path)
    attempt_id, job_id = _make_open_attempt(connection, running=True)

    # State C: cancel job first, leave attempt RUNNING.
    connection.execute(
        "UPDATE printer_scheduler_jobs SET status='CANCELLED',finished_at=?,"
        "locked_at=NULL,lock_owner=NULL,updated_at=? WHERE id=?",
        (NOW.isoformat(), NOW.isoformat(), job_id),
    )
    connection.commit()
    report_c = reconcile_parent_interrupted_open_pre_admission_attempts(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        now=NOW,
    )
    assert report_c["replay_state"] == "C"
    assert tuple(
        connection.execute(
            "SELECT attempt_state,first_terminal_cause FROM "
            "printer_pre_admission_discovery_attempts WHERE attempt_id=?",
            (attempt_id,),
        ).fetchone()
    ) == ("CANCELLED", EXPECTED_CAUSE)

    # State D: both already terminal with matching cause.
    report_d = reconcile_parent_interrupted_open_pre_admission_attempts(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        now=NOW,
    )
    assert report_d["idempotent_replay"] is True
    assert report_d["replay_state"] == "D"

    connection.close()

    # Conflicting interruption cause fails closed (fresh attempt terminalized
    # with a different PARENT_CAMPAIGN_INTERRUPTED suffix).
    path_conflict = db_path.parent / "state-conflict.sqlite3"
    apply_migrations(path_conflict)
    connection = _open(path_conflict)
    _seed(connection)
    conflict_id, _job = _make_open_attempt(connection)
    terminalize_pre_admission_attempt(
        connection,
        attempt_id=conflict_id,
        state=PreAdmissionAttemptState.CANCELLED,
        cause=f"{PARENT_CAMPAIGN_INTERRUPTED_PREFIX}OTHER",
        now=NOW,
    )
    connection.commit()
    with pytest.raises(FourTokenFactoryAdapterError, match="conflicting"):
        reconcile_parent_interrupted_open_pre_admission_attempts(
            connection,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            now=NOW,
        )
    connection.close()

    # State B on a fresh DB: attempt cancelled with expected cause, job pending.
    path_b = db_path.parent / "state-b.sqlite3"
    apply_migrations(path_b)
    connection = _open(path_b)
    _seed(connection)
    attempt_id, job_id = _make_open_attempt(connection)
    terminalize_pre_admission_attempt(
        connection,
        attempt_id=attempt_id,
        state=PreAdmissionAttemptState.CANCELLED,
        cause=EXPECTED_CAUSE,
        now=NOW,
    )
    connection.commit()
    assert connection.execute(
        "SELECT status FROM printer_scheduler_jobs WHERE id=?", (job_id,)
    ).fetchone()[0] == "PENDING"
    report_b = reconcile_parent_interrupted_open_pre_admission_attempts(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        now=NOW,
    )
    assert report_b["replay_state"] == "B"
    assert report_b["job_cancelled"] is True
    assert connection.execute(
        "SELECT status FROM printer_scheduler_jobs WHERE id=?", (job_id,)
    ).fetchone()[0] == "CANCELLED"
    connection.close()


def test_c12_only_finalize_is_production_call_site(db_path: Path) -> None:
    connection = _open(db_path)
    _make_open_attempt(connection)
    identities = _acquire_supervision(db_path)
    calls: list[str] = []

    def shared_terminalizer() -> dict[str, Any]:
        reconcile_campaign_terminal(
            db_path,
            campaign_id="campaign-1",
            run_id="campaign-run-1",
            cycle_id="cycle-1",
            terminal_cause=PARENT_CAUSE,
            run_status="SAFE_STOPPED",
            factory_run_id="factory-1",
            lifecycle_started=True,
            now=NOW.isoformat(),
        )
        cleanup_campaign_supervision(
            db_path,
            terminal_status="FAILED",
            first_terminal_cause=PARENT_CAUSE,
            now=NOW,
            **identities,
        )
        return {"clean_terminal": True, "lease_released": True}

    real = reconcile_parent_interrupted_open_pre_admission_attempts

    def wrapped(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append("interrupt")
        return real(*args, **kwargs)

    with patch(
        "printer_v1.operator_cli.four_token_factory_adapter."
        "reconcile_parent_interrupted_open_pre_admission_attempts",
        wrapped,
    ):
        result = finalize_four_token_shared_terminal(
            connection,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            shared_terminalizer=shared_terminalizer,
            now=NOW,
        )
    connection.close()
    assert calls == ["interrupt"]
    assert result["admitted_shape"] == "ONE_CYCLE_CAMPAIGN_INTERRUPTED_OPEN_ATTEMPT"


def test_honest_no_pair_not_classified_as_interrupted(db_path: Path) -> None:
    connection = _open(db_path)
    attempt_id, job_id = _make_open_attempt(connection, running=True)
    terminalize_pre_admission_attempt(
        connection,
        attempt_id=attempt_id,
        state=PreAdmissionAttemptState.NO_PAIR,
        cause="DURATION_EXHAUSTION",
        now=NOW,
    )
    connection.execute(
        "UPDATE printer_scheduler_jobs SET status='CANCELLED',finished_at=?,"
        "locked_at=NULL,lock_owner=NULL WHERE id=?",
        (NOW.isoformat(), job_id),
    )
    connection.commit()
    identities = _acquire_supervision(db_path)

    def shared_terminalizer() -> dict[str, Any]:
        reconcile_campaign_terminal(
            db_path,
            campaign_id="campaign-1",
            run_id="campaign-run-1",
            cycle_id="cycle-1",
            terminal_cause=PARENT_CAUSE,
            run_status="SAFE_STOPPED",
            factory_run_id="factory-1",
            lifecycle_started=True,
            now=NOW.isoformat(),
        )
        cleanup_campaign_supervision(
            db_path,
            terminal_status="FAILED",
            first_terminal_cause=PARENT_CAUSE,
            now=NOW,
            **identities,
        )
        return {"clean_terminal": True, "lease_released": True}

    result = finalize_four_token_shared_terminal(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        shared_terminalizer=shared_terminalizer,
        now=NOW,
    )
    connection.close()
    assert result["admitted_shape"] == "ONE_CYCLE_HONEST_NO_ADMISSION"
    assert EXPECTED_CAUSE.startswith(PARENT_CAMPAIGN_INTERRUPTED_PREFIX)

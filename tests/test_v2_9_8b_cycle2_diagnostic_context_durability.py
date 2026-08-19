"""Focused proof for V2-9.8B Cycle-2 diagnostic-context durability.

Disposable migrated DB only. No provider call, campaign authorization, lifecycle,
wallet, financial capability, retry, or endpoint rotation is exercised.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from printer_v1.db.migrate import apply_migrations
import printer_v1.operator_cli.graduated_supply_front_door as supply_front_door
from printer_v1.scheduler.contracts import JobKind, JobStatus, LockResult
from printer_v1.scheduler.scheduler import (
    claim_due_job,
    enqueue_job,
    fail_job,
    reset_scheduler_operation_observer,
    set_scheduler_operation_observer,
)

MINT = "4FN5PSaprS73Z2SRGx2HG9eaES1yVURMU5yAPpDQpump"
POOL = "9yuowVdGRZ35yM339cjyTWfhAdJJVPJqPKGHhyCXG3fo"
NOW = datetime(2026, 8, 19, 19, 0, tzinfo=timezone.utc)
LOCK_OWNER = "pre-admission:test-cycle2-diagnostic"
CODE = "DIRECT_PUMP_EVIDENCE_MISSING"
CAUSE = f"LATER_CYCLE_SUPPLY_EXCEPTION_{CODE}"


def _running_pre_admission_job(db: Path) -> int:
    apply_migrations(db)
    result, job_id = enqueue_job(
        db,
        job_name="test-cycle2-pre-admission",
        job_kind=JobKind.PRE_ADMISSION_DISCOVERY_SELECTION,
        scheduled_for=NOW,
    )
    assert result is LockResult.ACQUIRED
    assert job_id is not None
    claimed = claim_due_job(db, job_id=job_id, lock_owner=LOCK_OWNER, now=NOW)
    assert claimed is LockResult.ACQUIRED
    return int(job_id)


def _job(db: Path, job_id: int) -> sqlite3.Row:
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM printer_scheduler_jobs WHERE id=?", (job_id,)
        ).fetchone()
        assert row is not None
        return row
    finally:
        connection.close()


def test_typed_cycle2_failure_persists_bounded_context_without_changing_terminal_cause(
    tmp_path: Path,
) -> None:
    db = tmp_path / "cycle2-diagnostic.sqlite3"
    job_id = _running_pre_admission_job(db)
    observed: list[dict] = []
    observer_token = set_scheduler_operation_observer(observed.append)
    db_token = supply_front_door._ACTIVE_DB_PATH.set(str(db))
    try:
        exc = supply_front_door._typed_error(
            CODE,
            message="raw-message-must-not-be-persisted",
            stage="SOURCE_SPECIFIC_ADMISSION",
            mint=MINT,
            pool=POOL,
            admission_authority="DIRECT_PUMP_PUMPSWAP",
            nomination_source="direct_pump_migration",
        )
        assert exc.code == CODE
        status = fail_job(db, job_id=job_id, error=CAUSE, now=NOW, max_retries=0)
    finally:
        supply_front_door._ACTIVE_DB_PATH.reset(db_token)
        reset_scheduler_operation_observer(observer_token)

    assert status is JobStatus.FAILED
    row = _job(db, job_id)
    assert row["status"] == "FAILED"
    assert int(row["retry_count"]) == 1
    diagnostic = json.loads(str(row["last_error"]))
    assert diagnostic == {
        "admission_authority": "DIRECT_PUMP_PUMPSWAP",
        "failure_code": CODE,
        "mint": MINT,
        "nomination_source": "direct_pump_migration",
        "pool": POOL,
        "stage": "SOURCE_SPECIFIC_ADMISSION",
    }
    assert "raw-message-must-not-be-persisted" not in str(row["last_error"])

    terminal = [item for item in observed if item.get("boundary") == "SCHEDULER_TERMINAL"]
    assert len(terminal) == 1
    assert terminal[0]["terminal_state"] == "FAILED"
    assert terminal[0]["first_terminal_cause"] == CAUSE


def test_generic_failure_keeps_existing_plain_last_error_behavior(tmp_path: Path) -> None:
    db = tmp_path / "generic.sqlite3"
    job_id = _running_pre_admission_job(db)
    cause = "LATER_CYCLE_SUPPLY_EXCEPTION_RUNTIMEERROR"

    status = fail_job(db, job_id=job_id, error=cause, now=NOW, max_retries=0)

    assert status is JobStatus.FAILED
    row = _job(db, job_id)
    assert row["last_error"] == cause


def test_mismatched_staged_code_is_not_attached_to_another_failure(tmp_path: Path) -> None:
    db = tmp_path / "mismatch.sqlite3"
    job_id = _running_pre_admission_job(db)
    db_token = supply_front_door._ACTIVE_DB_PATH.set(str(db))
    try:
        supply_front_door._typed_error(
            CODE,
            stage="SOURCE_SPECIFIC_ADMISSION",
            mint=MINT,
            pool=POOL,
            admission_authority="DIRECT_PUMP_PUMPSWAP",
            nomination_source="direct_pump_migration",
        )
        other_cause = "LATER_CYCLE_SUPPLY_EXCEPTION_MARKET_CANDIDATE_OBSERVATION_TIME_MISSING"
        status = fail_job(
            db, job_id=job_id, error=other_cause, now=NOW, max_retries=0
        )
    finally:
        supply_front_door._ACTIVE_DB_PATH.reset(db_token)

    assert status is JobStatus.FAILED
    row = _job(db, job_id)
    assert row["last_error"] == other_cause

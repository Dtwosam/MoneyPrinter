from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import (
    interrupted_four_token_704f53472011_residue_reconciliation as recovery,
)


NOW = datetime(2026, 8, 29, 11, 0, tzinfo=timezone.utc)


def _open(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _marker(path: Path) -> str:
    payload = {
        "authorization_id": recovery.AUTHORIZATION_ID,
        "authorization_consumed_at": "2026-08-28T22:08:30+00:00",
        "allowed_invocation_count": 1,
        "automatic_retry_allowed": False,
        "manual_rerun_allowed": False,
        "restart_allowed": False,
        "resume_allowed": False,
        "successor_allowed": False,
    }
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return recovery._sha256(path)


def _lease(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "scope": "OPERATIONAL_CAMPAIGN",
                "supervision_id": recovery.SUPERVISION_ID,
                "campaign_id": recovery.CAMPAIGN_ID,
                "configuration_id": recovery.CONFIGURATION_ID,
                "run_id": recovery.CAMPAIGN_RUN_ID,
                "owner_id": recovery.OWNER_ID,
                "heartbeat_at": NOW.isoformat(),
                "lease_expires_at": (NOW + timedelta(seconds=90)).isoformat(),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _seed(path: Path, lease_path: Path) -> None:
    apply_migrations(path)
    connection = _open(path)
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute(
            "INSERT INTO printer_memory_factory_campaigns("
            "campaign_id,campaign_state,db_mode,db_target_identity,policy_version,"
            "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            (
                recovery.CAMPAIGN_ID,
                "RUNNING",
                "OPERATIONAL_PERSISTENT",
                "fixture-db",
                "V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1",
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
        connection.execute(
            "INSERT INTO printer_memory_factory_campaign_configurations("
            "configuration_id,campaign_id,configuration_hash,configuration_json,"
            "launch_provenance_json,created_at) VALUES (?,?,?,?,?,?)",
            (
                recovery.CONFIGURATION_ID,
                recovery.CAMPAIGN_ID,
                "a" * 64,
                "{}",
                "{}",
                NOW.isoformat(),
            ),
        )
        connection.execute(
            "INSERT INTO printer_memory_factory_runs("
            "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at,"
            "created_at,updated_at,stop_reason) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                recovery.FACTORY_RUN_ID,
                "RUNNING",
                "WINDOW_15M",
                "OPERATIONAL_PERSISTENT",
                "a" * 64,
                "{}",
                NOW.isoformat(),
                NOW.isoformat(),
                NOW.isoformat(),
                recovery.TERMINAL_CAUSE,
            ),
        )
        connection.execute(
            "INSERT INTO printer_memory_factory_campaign_runs("
            "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,"
            "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            (
                recovery.CAMPAIGN_RUN_ID,
                recovery.CAMPAIGN_ID,
                1,
                "RUNNING",
                recovery.FACTORY_RUN_ID,
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
        connection.execute(
            "INSERT INTO printer_memory_factory_campaign_cycles("
            "cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,first_terminal_cause,"
            "terminal_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                recovery.CYCLE_ID,
                recovery.CAMPAIGN_ID,
                recovery.CAMPAIGN_RUN_ID,
                1,
                "TERMINAL_BLOCKED",
                recovery.TERMINAL_CAUSE,
                NOW.isoformat(),
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
        connection.execute(
            """INSERT INTO printer_memory_factory_campaign_supervision(
                supervision_id,campaign_id,configuration_id,run_id,owner_id,
                supervision_state,heartbeat_at,lease_expires_at,lease_lock_path,
                created_at,updated_at
            ) VALUES (?,?,?,?,?,'ACTIVE',?,?,?,?,?)""",
            (
                recovery.SUPERVISION_ID,
                recovery.CAMPAIGN_ID,
                recovery.CONFIGURATION_ID,
                recovery.CAMPAIGN_RUN_ID,
                recovery.OWNER_ID,
                NOW.isoformat(),
                (NOW + timedelta(seconds=90)).isoformat(),
                str(recovery.LEASE_LOCK_PATH),
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
        connection.execute(
            """INSERT INTO printer_scheduler_jobs(
                id,job_name,job_kind,target_table,status,scheduled_for,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?)""",
            (
                recovery.SCHEDULER_JOB_ID,
                f"pre-admission-discovery-selection:{recovery.ATTEMPT_ID}",
                "PRE_ADMISSION_DISCOVERY_SELECTION",
                "printer_pre_admission_discovery_attempts",
                "PENDING",
                NOW.isoformat(),
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
        connection.execute(
            """INSERT INTO printer_pre_admission_discovery_attempts(
                attempt_id,campaign_id,campaign_run_id,configuration_id,
                authoritative_factory_run_id,proposed_cycle_ordinal,proposed_cycle_id,
                scheduler_job_id,cycle_cutoff,evaluated_at,selection_seed_identity,
                attempt_state,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'RUNNING',?,?)""",
            (
                recovery.ATTEMPT_ID,
                recovery.CAMPAIGN_ID,
                recovery.CAMPAIGN_RUN_ID,
                recovery.CONFIGURATION_ID,
                recovery.FACTORY_RUN_ID,
                2,
                f"{recovery.EXECUTION_ID}-cycle-2",
                recovery.SCHEDULER_JOB_ID,
                NOW.isoformat(),
                NOW.isoformat(),
                f"{recovery.FACTORY_RUN_ID}:{recovery.CAMPAIGN_RUN_ID}:c0002",
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
        for index in range(1, 20):
            kind = "OPPORTUNITY_EXECUTED" if index <= 9 else "SOURCE_REQUEST_TERMINAL"
            payload = json.dumps({"fixture": index, "kind": kind}, sort_keys=True)
            connection.execute(
                """INSERT INTO printer_pre_admission_attempt_evidence(
                    attempt_id,event_key,opportunity_ordinal,claim_ordinal,evidence_kind,
                    categorical_reason,payload_json,payload_hash,observed_at,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    recovery.ATTEMPT_ID,
                    f"fixture-{index:02d}",
                    0,
                    index,
                    kind,
                    "ACQUISITION_QUANTUM_YIELDED" if index <= 9 else "SOURCE_RESPONSE",
                    payload,
                    hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                    NOW.isoformat(),
                    NOW.isoformat(),
                ),
            )
        connection.commit()
    finally:
        connection.close()
    _lease(lease_path)


@pytest.fixture()
def residue(tmp_path: Path) -> dict[str, Path | str]:
    db = tmp_path / "residue.sqlite3"
    lease = tmp_path / "campaign.lease.lock"
    marker = tmp_path / "application-marker.json"
    _seed(db, lease)
    marker_sha = _marker(marker)
    return {"db": db, "lease": lease, "marker": marker, "marker_sha": marker_sha}


def _apply_fixture(residue: dict[str, Path | str]) -> dict[str, object]:
    db = Path(residue["db"])
    return recovery._reconcile(
        operator_approved=True,
        db_path=db,
        repository_root=db.parent,
        expected_git_head="proof-head",
        expected_db_sha256=recovery._sha256(db),
        marker_path=Path(residue["marker"]),
        expected_marker_sha256=str(residue["marker_sha"]),
        lease_path=Path(residue["lease"]),
        process_probe=lambda: False,
        git_head_probe=lambda _root: "proof-head",
        lease_lock_path_override=Path(residue["lease"]),
        now=NOW,
    )


def test_exact_disposable_residue_reconciles_through_canonical_owners(residue) -> None:
    db = Path(residue["db"])
    before = _open(db)
    try:
        cycle_before = dict(before.execute(
            "SELECT * FROM printer_memory_factory_campaign_cycles WHERE cycle_id=?",
            (recovery.CYCLE_ID,),
        ).fetchone())
        evidence_before = recovery._attempt_evidence_snapshot(before)
        locked_before = recovery._locked_hashes(before)
    finally:
        before.close()

    result = _apply_fixture(residue)

    assert result["status"] == "RECOVERED"
    assert result["admitted_shape"] == "ONE_CYCLE_CAMPAIGN_INTERRUPTED_OPEN_ATTEMPT"
    assert result["attempt_state"] == "CANCELLED"
    assert result["attempt_terminal_cause"] == recovery.INTERRUPTION_CAUSE
    assert result["scheduler_job_status"] == "CANCELLED"
    assert result["factory_run_status"] == "SAFE_STOPPED"
    assert result["supervision_state"] == "TERMINAL"
    assert result["lease_released"] is True
    assert result["source_calls"] == 0
    assert result["scheduler_runtime_calls"] == 0
    assert Path(residue["lease"]).exists() is False

    after = _open(db)
    try:
        assert dict(after.execute(
            "SELECT * FROM printer_memory_factory_campaign_cycles WHERE cycle_id=?",
            (recovery.CYCLE_ID,),
        ).fetchone()) == cycle_before
        assert recovery._attempt_evidence_snapshot(after) == evidence_before
        assert recovery._locked_hashes(after) == locked_before
        assert after.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert after.execute("PRAGMA foreign_key_check").fetchall() == []
        attempt = after.execute(
            "SELECT attempt_state,first_terminal_cause,consumed_cycle_id FROM "
            "printer_pre_admission_discovery_attempts WHERE attempt_id=?",
            (recovery.ATTEMPT_ID,),
        ).fetchone()
        assert tuple(attempt) == ("CANCELLED", recovery.INTERRUPTION_CAUSE, None)
        job = after.execute(
            "SELECT status,locked_at,lock_owner FROM printer_scheduler_jobs WHERE id=?",
            (recovery.SCHEDULER_JOB_ID,),
        ).fetchone()
        assert tuple(job) == ("CANCELLED", None, None)
    finally:
        after.close()


def test_exact_disposable_replay_is_idempotent(residue) -> None:
    first = _apply_fixture(residue)
    sha_after_first = recovery._sha256(Path(residue["db"]))
    second = _apply_fixture(residue)
    sha_after_second = recovery._sha256(Path(residue["db"]))
    assert first["status"] == "RECOVERED"
    assert second["status"] == "ALREADY_RECOVERED_IDEMPOTENT"
    assert second["database_writes"] == 0
    assert sha_after_second == sha_after_first


def test_operator_approval_is_required(residue) -> None:
    db = Path(residue["db"])
    with pytest.raises(recovery.InterruptedFourTokenResidueRecoveryError, match="approval"):
        recovery._reconcile(
            operator_approved=False,
            db_path=db,
            repository_root=db.parent,
            expected_git_head="proof-head",
            expected_db_sha256=recovery._sha256(db),
            marker_path=Path(residue["marker"]),
            expected_marker_sha256=str(residue["marker_sha"]),
            lease_path=Path(residue["lease"]),
            process_probe=lambda: False,
            git_head_probe=lambda _root: "proof-head",
            lease_lock_path_override=Path(residue["lease"]),
            now=NOW,
        )


def test_process_presence_fails_before_mutation(residue) -> None:
    db = Path(residue["db"])
    before = recovery._sha256(db)
    with pytest.raises(recovery.InterruptedFourTokenResidueRecoveryError, match="process"):
        recovery._reconcile(
            operator_approved=True,
            db_path=db,
            repository_root=db.parent,
            expected_git_head="proof-head",
            expected_db_sha256=before,
            marker_path=Path(residue["marker"]),
            expected_marker_sha256=str(residue["marker_sha"]),
            lease_path=Path(residue["lease"]),
            process_probe=lambda: True,
            git_head_probe=lambda _root: "proof-head",
            lease_lock_path_override=Path(residue["lease"]),
            now=NOW,
        )
    assert recovery._sha256(db) == before


def test_wrong_scheduler_truth_fails_closed_without_attempt_mutation(residue) -> None:
    db = Path(residue["db"])
    connection = _open(db)
    try:
        connection.execute(
            "UPDATE printer_scheduler_jobs SET status='FAILED' WHERE id=?",
            (recovery.SCHEDULER_JOB_ID,),
        )
        connection.commit()
    finally:
        connection.close()
    sha = recovery._sha256(db)
    with pytest.raises(recovery.InterruptedFourTokenResidueRecoveryError):
        recovery._reconcile(
            operator_approved=True,
            db_path=db,
            repository_root=db.parent,
            expected_git_head="proof-head",
            expected_db_sha256=sha,
            marker_path=Path(residue["marker"]),
            expected_marker_sha256=str(residue["marker_sha"]),
            lease_path=Path(residue["lease"]),
            process_probe=lambda: False,
            git_head_probe=lambda _root: "proof-head",
            lease_lock_path_override=Path(residue["lease"]),
            now=NOW,
        )
    connection = _open(db)
    try:
        row = connection.execute(
            "SELECT attempt_state,first_terminal_cause FROM "
            "printer_pre_admission_discovery_attempts WHERE attempt_id=?",
            (recovery.ATTEMPT_ID,),
        ).fetchone()
        assert tuple(row) == ("RUNNING", None)
    finally:
        connection.close()


def test_wrong_cycle_cause_fails_closed(residue) -> None:
    db = Path(residue["db"])
    connection = _open(db)
    try:
        connection.execute(
            "UPDATE printer_memory_factory_campaign_cycles SET first_terminal_cause='OTHER' "
            "WHERE cycle_id=?",
            (recovery.CYCLE_ID,),
        )
        connection.commit()
    finally:
        connection.close()
    sha = recovery._sha256(db)
    with pytest.raises(recovery.InterruptedFourTokenResidueRecoveryError, match="Cycle-1"):
        recovery._reconcile(
            operator_approved=True,
            db_path=db,
            repository_root=db.parent,
            expected_git_head="proof-head",
            expected_db_sha256=sha,
            marker_path=Path(residue["marker"]),
            expected_marker_sha256=str(residue["marker_sha"]),
            lease_path=Path(residue["lease"]),
            process_probe=lambda: False,
            git_head_probe=lambda _root: "proof-head",
            lease_lock_path_override=Path(residue["lease"]),
            now=NOW,
        )


def test_sidecar_fails_closed(residue) -> None:
    db = Path(residue["db"])
    sidecar = Path(f"{db}-wal")
    sidecar.write_bytes(b"not-a-real-wal")
    with pytest.raises(recovery.InterruptedFourTokenResidueRecoveryError, match="sidecar"):
        recovery._reconcile(
            operator_approved=True,
            db_path=db,
            repository_root=db.parent,
            expected_git_head="proof-head",
            expected_db_sha256=recovery._sha256(db),
            marker_path=Path(residue["marker"]),
            expected_marker_sha256=str(residue["marker_sha"]),
            lease_path=Path(residue["lease"]),
            process_probe=lambda: False,
            git_head_probe=lambda _root: "proof-head",
            lease_lock_path_override=Path(residue["lease"]),
            now=NOW,
        )


def test_consumed_marker_identity_is_hard_gated(residue) -> None:
    db = Path(residue["db"])
    with pytest.raises(recovery.InterruptedFourTokenResidueRecoveryError, match="marker SHA"):
        recovery._reconcile(
            operator_approved=True,
            db_path=db,
            repository_root=db.parent,
            expected_git_head="proof-head",
            expected_db_sha256=recovery._sha256(db),
            marker_path=Path(residue["marker"]),
            expected_marker_sha256="0" * 64,
            lease_path=Path(residue["lease"]),
            process_probe=lambda: False,
            git_head_probe=lambda _root: "proof-head",
            lease_lock_path_override=Path(residue["lease"]),
            now=NOW,
        )


def test_production_entry_point_remains_bound_to_live_database_sha(residue, monkeypatch) -> None:
    marker = Path(residue["marker"])
    monkeypatch.setattr(recovery, "APPLICATION_MARKER_PATH", marker)
    monkeypatch.setattr(recovery, "EXPECTED_APPLICATION_MARKER_SHA256", str(residue["marker_sha"]))
    monkeypatch.setattr(recovery, "LEASE_LOCK_PATH", Path(residue["lease"]))
    monkeypatch.setattr(recovery, "_default_git_head_probe", lambda _root: "proof-head")
    with pytest.raises(recovery.InterruptedFourTokenResidueRecoveryError, match="database SHA"):
        recovery.reconcile_exact_interrupted_four_token_residue(
            operator_approved=True,
            db_path=Path(residue["db"]),
            repository_root=Path(residue["db"]).parent,
            expected_git_head="proof-head",
            process_probe=lambda: False,
            now=NOW,
        )

"""Focused offline tests for discovery SHARED_FAILURE evidence capture.

Uses only deterministic exception seams, frozen/no source transports, and
disposable Migration-050 databases. It never runs the public composition.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.combined_executor import (
    CombinedPumpfunCampaignExecutor,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    SOURCE_GOVERNOR_OWNER,
    OwnerPort,
)
from printer_v1.operator_cli.offline_shared_failure_evidence import (
    DATABASE_COPY_NAME,
    FAILURE_ARTIFACT_NAME,
    OfflineSharedFailureEvidenceError,
    preserve_failed_offline_composition_evidence,
)
from printer_v1.scheduler.contracts import JobKind, JobStatus, LockResult
from printer_v1.scheduler.scheduler import enqueue_job

import test_v2_9_8b_discovery_scheduler_claim_at_work_start as _claim_tests


BATCH = _claim_tests.BATCH
NOW = _claim_tests.NOW


GOVERNOR = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCHEDULER = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)
STAGES = (
    "DISCOVERY_WORK_BEFORE_ENQUEUE",
    "DISCOVERY_WORK_AFTER_ENQUEUE_BEFORE_CLAIM",
    "DISCOVERY_WORK_AFTER_CLAIM_BEFORE_INSERT",
    "DISCOVERY_WORK_GOVERNED_EXECUTION",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_at_stage(
    stage: str,
    *,
    message: str = "deterministic discovery diagnostic failure",
    rollback=None,
    add_unrelated_job: bool = False,
):
    case = _claim_tests.DiscoverySchedulerClaimAtWorkStartTests(
        methodName="test_success_records_enqueue_claim_terminal_order_and_lock_fields"
    )
    case.setUp()
    try:
        case.connection.execute(
            "DELETE FROM printer_discovery_batches WHERE discovery_batch_id=?",
            (BATCH,),
        )
        unrelated_job_id = None
        if add_unrelated_job:
            result, unrelated_job_id = enqueue_job(
                case.connection,
                job_name="unrelated-evidence-capture-job",
                job_kind=JobKind.DISCOVERY_REFRESH,
            )
            assert result == LockResult.ACQUIRED
        case.connection.commit()

        def inject(observed_stage: str) -> None:
            if observed_stage == stage:
                raise RuntimeError(message)

        executor = CombinedPumpfunCampaignExecutor(
            case.fixtures,
            diagnostic_fault_injector=inject,
            rollback=rollback,
        )
        result = executor.execute(
            command=case.command,
            source_governor=GOVERNOR,
            central_scheduler=SCHEDULER,
        )
        remaining = {
            "batches": int(
                case.connection.execute(
                    "SELECT COUNT(*) FROM printer_discovery_batches "
                    "WHERE discovery_batch_id=?",
                    (BATCH,),
                ).fetchone()[0]
            ),
            "work": int(
                case.connection.execute(
                    "SELECT COUNT(*) FROM printer_discovery_work "
                    "WHERE discovery_batch_id=?",
                    (BATCH,),
                ).fetchone()[0]
            ),
            "target_jobs": int(
                case.connection.execute(
                    "SELECT COUNT(*) FROM printer_scheduler_jobs "
                    "WHERE job_name LIKE ?",
                    (f"%{BATCH}",),
                ).fetchone()[0]
            ),
        }
        unrelated = None
        if unrelated_job_id is not None:
            unrelated = dict(
                case.connection.execute(
                    "SELECT id, status, lock_owner FROM printer_scheduler_jobs WHERE id=?",
                    (int(unrelated_job_id),),
                ).fetchone()
            )
        return result, list(case.events), remaining, unrelated
    finally:
        case.tearDown()


@pytest.mark.parametrize(
    ("stage", "enqueue", "claim", "work_insert", "job_status"),
    (
        (STAGES[0], False, False, False, None),
        (STAGES[1], True, False, False, JobStatus.PENDING.value),
        (STAGES[2], True, True, False, JobStatus.RUNNING.value),
        (STAGES[3], True, True, True, JobStatus.RUNNING.value),
    ),
)
def test_generic_exception_preserves_exact_stage_identity_and_claim_state(
    stage, enqueue, claim, work_insert, job_status
) -> None:
    result, events, remaining, _unrelated = _run_at_stage(stage)
    assert result.terminal_status == "FAILED"
    assert result.first_terminal_cause == "SHARED_FAILURE"
    assert result.cancellation_reason == "SHARED_FAILURE"
    details = dict(result.fault_details or {})
    assert details["first_failure"] == {
        "classification": "SHARED_FAILURE",
        "exception_class": "RuntimeError",
        "sanitized_message": "deterministic discovery diagnostic failure",
    }
    discovery = details["discovery"]
    assert discovery["discovery_stage"] == stage
    assert discovery["work_type"] == "DISCOVERY_PUMPFUN_LATEST"
    assert discovery["discovery_batch_id"] == BATCH
    assert discovery["discovery_work_id"].startswith(
        "work:DISCOVERY_PUMPFUN_LATEST:"
    )
    assert discovery["enqueue_completed"] is enqueue
    assert discovery["claim_returned"] is claim
    assert discovery["claim_result"] == ("ACQUIRED" if claim else None)
    assert discovery["discovery_work_insertion_completed"] is work_insert
    snapshot = details["pre_rollback_state"]
    assert snapshot["captured_before_rollback"] is True
    assert snapshot["visibility"] == "ACTIVE_TRANSACTION_MAY_INCLUDE_UNCOMMITTED_STATE"
    scheduler_row = snapshot["scheduler_job"]
    if job_status is None:
        assert scheduler_row is None
    else:
        assert scheduler_row["status"] == job_status
        assert scheduler_row["id"] == discovery["scheduler_job_id"]
    if claim:
        assert scheduler_row["lock_owner"] == discovery["expected_lock_owner"]
        assert scheduler_row["started_at"] is not None
        assert scheduler_row["locked_at"] is not None
    assert (snapshot["discovery_work"] is not None) is work_insert
    assert details["rollback"] == {"started": True, "completed": True}
    assert details["secondary_failures"] == []
    assert remaining == {"batches": 0, "work": 0, "target_jobs": 0}

    target_boundaries = [
        event["boundary"]
        for event in events
        if int(event.get("scheduler_job_id") or 0)
        == int(discovery.get("scheduler_job_id") or 0)
    ]
    expected_boundaries = []
    if enqueue:
        expected_boundaries.append("SCHEDULER_ENQUEUE")
    if claim:
        expected_boundaries.append("SCHEDULER_CLAIM")
    assert target_boundaries == expected_boundaries
    assert "SCHEDULER_TERMINAL" not in target_boundaries


def test_rollback_failure_is_secondary_and_unrelated_job_is_not_claimed() -> None:
    def rollback_failure(_connection: sqlite3.Connection) -> None:
        raise RuntimeError("rollback diagnostic failure")

    result, _events, remaining, unrelated = _run_at_stage(
        STAGES[2], rollback=rollback_failure, add_unrelated_job=True
    )
    details = dict(result.fault_details or {})
    assert details["first_failure"]["sanitized_message"] == (
        "deterministic discovery diagnostic failure"
    )
    assert details["rollback"] == {"started": True, "completed": False}
    assert details["secondary_failures"] == [
        {
            "stage": "ROLLBACK",
            "exception_class": "RuntimeError",
            "sanitized_message": "rollback diagnostic failure",
        }
    ]
    assert remaining == {"batches": 0, "work": 0, "target_jobs": 0}
    assert unrelated == {
        "id": unrelated["id"],
        "status": JobStatus.PENDING.value,
        "lock_owner": None,
    }


def test_generic_exception_message_redacts_rpc_url_and_configured_secret(
    monkeypatch,
) -> None:
    secret = "configured-rpc-secret-value"
    monkeypatch.setenv("PRINTER_SOLANA_RPC_URL", secret)
    result, _events, _remaining, _unrelated = _run_at_stage(
        STAGES[0],
        message=(
            f"provider diagnostic https://rpc.invalid/?api-key={secret} "
            f"token={secret}"
        ),
    )
    safe_message = result.fault_details["first_failure"]["sanitized_message"]
    assert secret not in safe_message
    assert "https://rpc.invalid" not in safe_message
    assert "[REDACTED" in safe_message


def test_success_result_has_no_failure_diagnostics_and_helper_is_failure_only(
    tmp_path: Path,
) -> None:
    case = _claim_tests.DiscoverySchedulerClaimAtWorkStartTests(
        methodName="test_success_records_enqueue_claim_terminal_order_and_lock_fields"
    )
    case.setUp()
    try:
        executor = CombinedPumpfunCampaignExecutor(case.fixtures)
        with patch.object(
            executor,
            "_run_cycle",
            return_value={
                "terminal_status": "COMPLETED",
                "first_terminal_cause": "DISCOVERY_CYCLE_COMPLETED",
                "cancellation_reason": None,
            },
        ):
            result = executor.execute(
                command=case.command,
                source_governor=GOVERNOR,
                central_scheduler=SCHEDULER,
            )
        assert result.terminal_status == "COMPLETED"
        assert result.fault_details is None
        with pytest.raises(ValueError, match="failure-only"):
            preserve_failed_offline_composition_evidence(
                source_database=case.db,
                artifact_root=tmp_path / "must-not-exist",
                execution_id="success-run",
                baseline_git_head="a" * 40,
                tracked_tree_state={"git_tracked_tree_clean": True},
                test_node_id="success-node",
                terminal={"fault_details": {}},
                zero_network_assertion={"patched_urllib_call_count": 0},
                retry_state={"automatic_retries": 0, "successors": 0},
                connections_closed=True,
            )
        assert not (tmp_path / "must-not-exist").exists()
    finally:
        case.tearDown()


def test_disposable_database_and_failure_artifact_survive_source_cleanup(
    tmp_path: Path, monkeypatch
) -> None:
    source_temp = tempfile.TemporaryDirectory(dir=tmp_path)
    source = Path(source_temp.name) / "migration-050.sqlite3"
    apply_migrations(source)
    secret = "do-not-persist-rpc-secret"
    monkeypatch.setenv("PRINTER_RPC_URL", secret)
    terminal = {
        "fault_details": {
            "first_failure": {
                "classification": "SHARED_FAILURE",
                "exception_class": "RuntimeError",
                "sanitized_message": (
                    f"failure at https://rpc.invalid/?api-key={secret} token={secret}"
                ),
            },
            "secondary_failures": [],
            "discovery": {
                "discovery_stage": STAGES[3],
                "work_type": "DISCOVERY_PUMPFUN_LATEST",
                "discovery_batch_id": BATCH,
                "claim_result": "ACQUIRED",
            },
            "pre_rollback_state": {"visibility": "ACTIVE_TRANSACTION"},
            "rollback": {"started": True, "completed": True},
        }
    }
    result = preserve_failed_offline_composition_evidence(
        source_database=source,
        artifact_root=tmp_path / "evidence",
        execution_id="evidence-run-001",
        baseline_git_head="b" * 40,
        tracked_tree_state={
            "git_tracked_tree_clean": True,
            "git_staged_changes_present": False,
            "git_unstaged_changes_present": False,
            "git_untracked_present": True,
        },
        test_node_id="tests/example.py::test_failure",
        terminal=terminal,
        zero_network_assertion={
            "boundary": "frozen transports; not packet-level proof",
            "patched_urllib_call_count": 0,
        },
        retry_state={
            "automatic_retries": 0,
            "reruns": 0,
            "resumes": 0,
            "restarts": 0,
            "successors": 0,
        },
        connections_closed=True,
    )
    source_temp.cleanup()

    preserved = Path(result["preserved_database"])
    artifact = Path(result["failure_artifact"])
    assert preserved.name == DATABASE_COPY_NAME
    assert artifact.name == FAILURE_ARTIFACT_NAME
    assert not source.exists()
    assert preserved.is_file()
    assert artifact.is_file()
    assert result["preserved_database_sha256"] == _sha256(preserved)
    assert result["integrity_check"] == "ok"
    assert result["foreign_key_check"] == []
    payload_text = artifact.read_text(encoding="utf-8")
    assert secret not in payload_text
    assert "https://rpc.invalid" not in payload_text
    payload = json.loads(payload_text)
    assert payload["preserved_database"]["migration_head_applied"] is True
    assert payload["preserved_database"]["destination_sidecars_after_close"] == []
    assert payload["preserved_database"]["evidence_only_not_production_database"] is True
    assert payload["retry_or_successor_state"]["successors"] == 0


def test_artifact_write_failure_retains_operational_first_failure(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite3"
    apply_migrations(source)
    first = {
        "classification": "SHARED_FAILURE",
        "exception_class": "RuntimeError",
        "sanitized_message": "original operational failure",
    }
    terminal = {
        "fault_details": {
            "first_failure": first,
            "secondary_failures": [],
            "discovery": {},
            "rollback": {"started": True, "completed": True},
        }
    }
    with patch(
        "printer_v1.operator_cli.offline_shared_failure_evidence._write_json",
        side_effect=OSError("artifact writer failed"),
    ):
        with pytest.raises(OfflineSharedFailureEvidenceError) as raised:
            preserve_failed_offline_composition_evidence(
                source_database=source,
                artifact_root=tmp_path / "evidence-write-failure",
                execution_id="write-failure-run",
                baseline_git_head="c" * 40,
                tracked_tree_state={"git_tracked_tree_clean": True},
                test_node_id="tests/example.py::test_write_failure",
                terminal=terminal,
                zero_network_assertion={"patched_urllib_call_count": 0},
                retry_state={"automatic_retries": 0, "successors": 0},
                connections_closed=True,
            )
    assert raised.value.first_failure == first
    assert raised.value.secondary_failure["stage"] == (
        "OFFLINE_FAILURE_ARTIFACT_WRITE"
    )
    assert raised.value.secondary_failure["exception_class"] == "OSError"

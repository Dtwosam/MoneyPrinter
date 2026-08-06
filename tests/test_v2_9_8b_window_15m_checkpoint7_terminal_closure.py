"""Checkpoint 7 fail-first regressions for terminal closure/report publication."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli import unified_terminal_closure as closure
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    LiveOperationalError,
)


class _AccountingOwner:
    stage_evidence_count = 1
    accounting_block_reason = None

    def close(self) -> None:
        return None

    def six_unit_totals(self):
        return {}

    def durable_evidence(self):
        return {"evidence_kind": "CHECKPOINT7_FIXTURE"}


class _Cursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Connection:
    def __init__(self, report_row):
        self.report_row = report_row
        self.row_factory = None

    def execute(self, sql, *args):
        if "FROM printer_memory_factory_campaign_reports AS r" in str(sql):
            return _Cursor([self.report_row])
        return _Cursor([])

    def close(self):
        return None


def _command(tmp_path: Path):
    return SimpleNamespace(
        db_path=tmp_path / "fixture.sqlite3",
        supervision_id="supervision-1",
        campaign_id="campaign-1",
        configuration_id="configuration-1",
        run_id="run-1",
        owner_id="owner-1",
        report_id="report-1",
    )


def _cleanup_ok(cmd):
    return {
        "supervision_id": cmd.supervision_id,
        "campaign_id": cmd.campaign_id,
        "configuration_id": cmd.configuration_id,
        "run_id": cmd.run_id,
        "owner_id": cmd.owner_id,
        "terminal_status": "FAILED",
        "first_terminal_cause": "fixture",
        "cleanup_completed": True,
        "lease_released": True,
        "active_owned_work_after": 0,
        "restart_created": False,
        "successor_created": False,
    }


def _terminalize_patches(tmp_path: Path, cmd, busy_retry):
    return (
        mock.patch.object(command, "_existing_first_terminal_cause", return_value=None),
        mock.patch.object(command, "_with_sqlite_busy_retry", side_effect=busy_retry),
        mock.patch.object(
            command,
            "assemble_campaign_terminal_reporting",
            return_value={
                "campaign_source_calls": 0,
                "campaign_scheduler_calls": 0,
            },
        ),
        mock.patch.object(command, "build_campaign_terminal_report", return_value={}),
        mock.patch.object(command, "_selective_1h_terminal_projection", return_value=None),
    )


def test_initialized_coded_failure_preserves_safe_precise_code(tmp_path: Path):
    cmd = _command(tmp_path)
    error = LiveOperationalError(
        "CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH",
        "bounded fixture detail that must not become the terminal cause",
    )

    def busy_retry(label, operation, **kwargs):
        if label == "cleanup":
            return _cleanup_ok(cmd)
        if label == "reconciliation":
            return {"reconciled": True, "restart_created": False, "successor_created": False}
        if label == "report":
            return {"report_id": cmd.report_id}
        return operation()

    patches = _terminalize_patches(tmp_path, cmd, busy_retry)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        result = command._terminalize_initialized_failure(
            original_exception=error,
            command=cmd,
            cycle_id="cycle-1",
            execution_id="execution-1",
            paths={"summary": tmp_path / "summary.json", "reports": tmp_path / "reports"},
            launch_git_provenance={},
            accounting_owner=_AccountingOwner(),
        )

    assert result["first_terminal_cause"] == (
        "CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH"
    )
    assert "bounded fixture detail" not in result["first_terminal_cause"]


def test_cleanup_failure_blocks_canonical_failure_report_publication(tmp_path: Path):
    cmd = _command(tmp_path)
    writer = mock.Mock(return_value={"report_id": cmd.report_id})

    def busy_retry(label, operation, **kwargs):
        if label == "cleanup":
            raise command.OperationalMemoryFactoryError("fixture cleanup failure")
        if label == "reconciliation":
            return {"reconciled": True, "restart_created": False, "successor_created": False}
        if label == "report":
            return operation()
        return operation()

    patches = _terminalize_patches(tmp_path, cmd, busy_retry)
    with (
        patches[0], patches[1], patches[2], patches[3], patches[4],
        mock.patch.object(command, "write_campaign_terminal_report", writer),
    ):
        result = command._terminalize_initialized_failure(
            original_exception=RuntimeError("primary fixture failure"),
            command=cmd,
            cycle_id="cycle-1",
            execution_id="execution-1",
            paths={"summary": tmp_path / "summary.json", "reports": tmp_path / "reports"},
            launch_git_provenance={},
            accounting_owner=_AccountingOwner(),
        )

    writer.assert_not_called()
    assert result["report_written"] is False
    assert result["report_block_reason"] == "TERMINAL_CLEANUP_UNPROVEN"
    assert result["first_terminal_cause"] == "OPERATIONAL_CAMPAIGN_FAILED:RuntimeError"


def test_artifact_write_failure_cannot_commit_terminal_report_row(tmp_path: Path):
    report = {"report_kind": "PILOT_CAMPAIGN_TERMINAL", "identity": {"report_id": "r1"}}
    canonical = closure._canonical_json(report)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    persisted = mock.Mock(return_value={"report_hash": digest})

    with (
        mock.patch.object(closure, "persist_terminal_report", persisted),
        mock.patch.object(Path, "write_text", side_effect=OSError("fixture disk failure")),
        pytest.raises(Exception),
    ):
        closure.write_campaign_terminal_report(
            tmp_path / "fixture.sqlite3",
            tmp_path / "reports",
            report_id="r1",
            campaign_id="c1",
            configuration_id="cfg1",
            report=report,
            require_six_unit_evidence=False,
        )

    persisted.assert_not_called()


def test_public_report_only_blocks_exact_artifact_mismatch(tmp_path: Path):
    artifact_root = tmp_path / "artifacts"
    report_dir = artifact_root / "execution-1" / "reports"
    report_dir.mkdir(parents=True)
    configuration = {
        "run_id": "run-1",
        "report_directory_identity": "report-dir-identity",
    }
    report_row = {
        "report_id": "report-1",
        "campaign_id": "campaign-1",
        "configuration_id": "configuration-1",
        "report_state": "REPORT_TERMINAL",
        "configuration_json": json.dumps(configuration),
        "config_campaign_id": "campaign-1",
    }
    fake_connection = _Connection(report_row)
    resolved_identity = {
        "status": "RESOLVED",
        "campaign_id": "campaign-1",
        "run_id": "run-1",
        "configuration_id": "configuration-1",
        "configuration_json": json.dumps(configuration),
        "requested_identity": {"campaign_id": "campaign-1", "run_id": "run-1"},
    }
    replay = {
        "artifact_matches": False,
        "report_id": "report-1",
        "report": {
            "identity": {
                "campaign_id": "campaign-1",
                "run_id": "run-1",
                "configuration_id": "configuration-1",
                "report_id": "report-1",
            }
        },
    }

    with (
        mock.patch.object(command.sqlite3, "connect", return_value=fake_connection),
        mock.patch.object(command, "_resolve_report_only_identity", return_value=resolved_identity),
        mock.patch.object(command, "report_path_identity", return_value="report-dir-identity"),
        mock.patch.object(command, "replay_campaign_terminal_report", return_value=replay),
    ):
        result = command.report_only(
            campaign_id="campaign-1",
            run_id="run-1",
            db_path=tmp_path / "fixture.sqlite3",
            artifact_root=artifact_root,
        )

    assert result["status"] == "REPLAY_BLOCKED"
    assert result["block_reason"] == "TERMINAL_REPORT_ARTIFACT_MISMATCH"
    assert result["source_calls"] == 0
    assert result["scheduler_runtime_calls"] == 0
    assert result["database_writes"] == 0

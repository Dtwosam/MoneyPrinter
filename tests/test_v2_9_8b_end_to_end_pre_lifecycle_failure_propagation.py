"""Focused deterministic pre-lifecycle terminal propagation contract.

Disposable Migration-050 databases and injected owners only.  No public exact
composition, provider, RPC, WebSocket, authorization, or financial path runs.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

from printer_v1.db.migrate import apply_migrations
from printer_v1.operator_cli import operational_memory_factory_command as public
from printer_v1.operator_cli.campaign_supervision import acquire_campaign_supervision
from printer_v1.operator_cli.offline_shared_failure_evidence import (
    preserve_failed_offline_composition_evidence,
)
from printer_v1.operator_cli.origin_lifecycle_campaign import ActivationResult
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignSixUnitOwner,
    build_campaign_stage_id,
    seal_campaign_stage_evidence,
)
from tests.support.window_15m_authorization_fixtures import (
    validated_window_15m_authorization,
)

from test_v2_9_8b_10_post_selection_lifecycle_integrity import (
    _command,
    _provenance,
    _seed_running_campaign,
)
from test_v2_9_8b_terminal_safety_accounting_finalization import (
    _accounting_stage,
)


def _case(tmp_path: Path, *, report_id: str = "pre-lifecycle-report"):
    db = tmp_path / "pre-lifecycle.sqlite3"
    reports = tmp_path / "reports"
    reports.mkdir()
    apply_migrations(db)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        cycle_id = _seed_running_campaign(db, connection)
    finally:
        connection.close()
    lock_path = tmp_path / "campaign.lock"
    acquire_campaign_supervision(
        db,
        lock_path=lock_path,
        supervision_id="supervision-10",
        campaign_id="campaign-10",
        configuration_id="configuration-10",
        run_id="run-10",
        owner_id="owner-10",
        lease_seconds=90,
    )
    command = _command(
        db,
        campaign_id="campaign-10",
        run_id="run-10",
        configuration_id="configuration-10",
        supervision_id="supervision-10",
        owner_id="owner-10",
        lock_path=lock_path,
        report_id=report_id,
    )
    return db, str(cycle_id), command, {
        "reports": reports,
        "summary": tmp_path / "summary.json",
    }


def _result(
    *,
    terminal_status: str = "FAILED",
    cause: str = "ORIGINAL_OPERATIONAL_FAILURE",
    cancellation: str | None = None,
    accountable: bool = False,
    fault_details=None,
    stage_evidences_marker=...,
):
    lifecycle = {
        "run_status": "NOT_STARTED",
        "first_terminal_cause": cause,
        "stop_reason": cause,
        "forbidden_deltas": {},
    }
    if cancellation is not None:
        lifecycle["cancellation_reason"] = cancellation
    if fault_details:
        lifecycle["fault_details"] = fault_details
    if stage_evidences_marker is not ...:
        lifecycle["six_unit_stage_evidences"] = stage_evidences_marker
    activation = ActivationResult(
        terminal_status=terminal_status,
        first_terminal_cause=cause,
        activated_slots=(),
        selection_batch_id=None,
        cancellation_reason=cancellation,
        fault_details=fault_details,
        accountable_stage_started=accountable,
        successor_created=False,
        restart_created=False,
    )
    return SimpleNamespace(
        activation=activation,
        lifecycle=lifecycle,
        lifecycle_started=False,
    )


def _finalize(
    tmp_path: Path,
    result,
    *,
    owner=None,
    transports=(),
    observer_state=None,
):
    db, cycle_id, command, paths = _case(tmp_path)
    owner = owner or CampaignSixUnitOwner(
        campaign_id=command.campaign_id,
        run_id=command.run_id,
        cycle_id=cycle_id,
    )
    terminal = public._finalize_returned_pre_lifecycle_result(
        result=result,
        lifecycle=result.lifecycle,
        command=command,
        cycle_id=cycle_id,
        execution_id="focused-pre-lifecycle",
        paths=paths,
        launch_git_provenance=_provenance(),
        campaign_units=owner,
        action_local_transport_identities=transports,
        stage_observer_state=observer_state
        or {
            "invoked": False,
            "completed": False,
            "returned_none": False,
            "failure": None,
        },
    )
    return db, terminal, owner


@pytest.mark.parametrize(
    ("status", "cause", "cancellation"),
    (
        ("FAILED", "ZERO_SLOT_FAILURE", None),
        ("FAILED", "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL", None),
        ("BLOCKED", "BLOCKED_INSUFFICIENT_GRADUATED_POOL", None),
        ("CANCELLED", "OPERATOR_CANCELLED_BEFORE_STAGE", "OPERATOR_REQUESTED"),
        ("LEASE_RENEWAL_UNCONFIRMED", "LEASE_RENEWAL_UNCONFIRMED", None),
    ),
)
def test_no_accountable_stage_propagates_exact_terminal_without_accounting(
    tmp_path, status, cause, cancellation
):
    _db, terminal, owner = _finalize(
        tmp_path,
        _result(
            terminal_status=status,
            cause=cause,
            cancellation=cancellation,
        ),
    )
    assert terminal["activation_terminal_status"] == status
    assert terminal["first_terminal_cause"] == cause
    assert terminal["cancellation_reason"] == cancellation
    assert terminal["lifecycle_started"] is False
    assert terminal["accountable_stage_started"] is False
    assert terminal["stage_evidences"] == ()
    assert terminal["accounting_required"] is False
    assert terminal["accounting_status"] == "NOT_REQUIRED_NO_ACCOUNTABLE_STAGE"
    assert terminal["failure_evidence_required"] is True
    assert terminal["campaign_pass"] is False
    assert terminal["restart_created"] is False
    assert terminal["successor_created"] is False
    assert owner.stage_evidence_count == 0


def test_real_failed_stage_evidence_is_strictly_accounted_then_failure_propagates(
    tmp_path,
):
    db, cycle_id, command, paths = _case(tmp_path)
    owner = CampaignSixUnitOwner(
        campaign_id=command.campaign_id,
        run_id=command.run_id,
        cycle_id=cycle_id,
    )
    evidence = seal_campaign_stage_evidence(
        stage_id=build_campaign_stage_id(
            campaign_id=command.campaign_id,
            run_id=command.run_id,
            cycle_id=cycle_id,
            stage_kind="DISCOVERY_SELECTION_SCHEDULER",
            stage_sequence=1,
        ),
        stage_kind="DISCOVERY_SELECTION_SCHEDULER",
        stage_sequence=1,
        stage_terminal_status="FAILED",
        stage_first_terminal_cause="ORIGINAL_OPERATIONAL_FAILURE",
        campaign_id=command.campaign_id,
        run_id=command.run_id,
        cycle_id=cycle_id,
        evidence=_accounting_stage(campaign_id=command.campaign_id) | {
            "run_id": command.run_id,
            "cycle_id": cycle_id,
        },
    )
    owner.ingest_stage_evidence(evidence)
    transport = dict(evidence["transport_operations"][0])
    result = _result(accountable=True, fault_details={"detail": "kept"})
    terminal = public._finalize_returned_pre_lifecycle_result(
        result=result,
        lifecycle=result.lifecycle,
        command=command,
        cycle_id=cycle_id,
        execution_id="failed-stage-with-evidence",
        paths=paths,
        launch_git_provenance=_provenance(),
        campaign_units=owner,
        action_local_transport_identities=[transport],
        stage_observer_state={
            "invoked": True,
            "completed": True,
            "returned_none": True,
            "failure": None,
        },
    )
    assert terminal["first_terminal_cause"] == "ORIGINAL_OPERATIONAL_FAILURE"
    assert terminal["accountable_stage_started"] is True
    assert terminal["accounting_required"] is True
    assert terminal["accounting_status"] == "SIX_UNIT_ACCOUNTING_COMPLETE"
    assert terminal["report"] is not None
    assert terminal["fault_details"]["detail"] == "kept"
    assert terminal["campaign_pass"] is False
    assert db.is_file()


@pytest.mark.parametrize("bad_collection", (None, [None], [], [{}]))
def test_claimed_stage_missing_none_empty_or_malformed_evidence_fails_closed_secondarily(
    tmp_path, bad_collection
):
    marker = bad_collection if bad_collection is not None else ...
    result = _result(accountable=True, stage_evidences_marker=marker)
    _db, terminal, _owner = _finalize(tmp_path, result)
    assert terminal["first_terminal_cause"] == "ORIGINAL_OPERATIONAL_FAILURE"
    assert terminal["accounting_required"] is True
    assert terminal["accounting_status"] == "SIX_UNIT_ACCOUNTING_BLOCKED"
    assert terminal["stage_evidences"] == ()
    failures = terminal["fault_details"]["propagation_failures"]
    assert any(
        item["stage"] == "PRE_LIFECYCLE_SIX_UNIT_FINALIZATION"
        for item in failures
    )


def test_observer_not_invoked_is_no_stage_but_observer_none_after_claim_is_not(
    tmp_path,
):
    _db, absent, _owner = _finalize(tmp_path, _result())
    assert absent["accounting_required"] is False

    other = tmp_path / "invoked"
    other.mkdir()
    _db, invoked, _owner = _finalize(
        other,
        _result(),
        observer_state={
            "invoked": True,
            "completed": True,
            "returned_none": True,
            "failure": None,
        },
    )
    assert invoked["accounting_required"] is True
    assert invoked["accounting_status"] == "SIX_UNIT_ACCOUNTING_BLOCKED"
    assert invoked["stage_evidences"] == ()


def test_cleanup_failure_is_secondary_to_returned_operational_failure(
    tmp_path, monkeypatch
):
    def fail_cleanup(*_args, **_kwargs):
        raise RuntimeError("cleanup failed second")

    monkeypatch.setattr(public, "cleanup_campaign_supervision", fail_cleanup)
    _db, terminal, _owner = _finalize(
        tmp_path,
        _result(cause="FIRST_OPERATIONAL_CAUSE"),
    )
    assert terminal["first_terminal_cause"] == "FIRST_OPERATIONAL_CAUSE"
    assert any(
        item["stage"] == "PRE_LIFECYCLE_CLEANUP"
        for item in terminal["fault_details"]["propagation_failures"]
    )


def test_generic_returned_failure_helper_copy_survives_source_cleanup(tmp_path):
    source_temp = tempfile.TemporaryDirectory(dir=tmp_path)
    source = Path(source_temp.name) / "migration-050.sqlite3"
    apply_migrations(source)
    terminal = {
        "status": "OPERATIONAL_CAMPAIGN_PRE_LIFECYCLE_TERMINAL",
        "activation_terminal_status": "BLOCKED",
        "run_status": "NOT_STARTED",
        "first_terminal_cause": "BLOCKED_INSUFFICIENT_GRADUATED_POOL",
        "cancellation_reason": None,
        "lifecycle_started": False,
        "accountable_stage_started": False,
        "accounting_required": False,
        "accounting_status": "NOT_REQUIRED_NO_ACCOUNTABLE_STAGE",
        "failure_evidence_required": True,
        "fault_details": {},
    }
    preserved = preserve_failed_offline_composition_evidence(
        source_database=source,
        artifact_root=tmp_path / "evidence",
        execution_id="generic-returned-failure",
        baseline_git_head="d" * 40,
        tracked_tree_state={"git_tracked_tree_clean": True},
        test_node_id="focused::generic-returned-failure",
        terminal=terminal,
        zero_network_assertion={"patched_urllib_call_count": 0},
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
    assert not source.exists()
    assert Path(preserved["preserved_database"]).is_file()
    assert Path(preserved["failure_artifact"]).is_file()
    assert preserved["integrity_check"] == "ok"
    assert preserved["foreign_key_check"] == []


class _NoopHeartbeat:
    def __init__(self, _command):
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def poll_failure(self):
        return None


class _ReturnedFailureOwner:
    def __init__(self, result, *, observer_record=None):
        self.result = result
        self.observer_record = observer_record
        self.observer_returned = "NOT_CALLED"

    def run_operational(self, **kwargs):
        if self.observer_record is not None:
            self.observer_returned = kwargs["lifecycle_kwargs"][
                "full_run_stage_observer"
            ](self.observer_record)
        return self.result


def test_public_coordinator_returns_no_stage_failure_and_never_builds_none_placeholder(
    tmp_path,
):
    _db, cycle_id, command, _paths = _case(tmp_path)
    artifact_root = tmp_path / "public-artifacts"
    owner = _ReturnedFailureOwner(
        _result(
            terminal_status="CANCELLED",
            cause="PUBLIC_PRE_STAGE_CANCEL",
            cancellation="OPERATOR_REQUESTED",
        )
    )
    with (
        patch.object(
            public,
            "build_activation_preflight",
            return_value={
                "database_sha256": "a" * 64,
                "git_provenance": _provenance(),
            },
        ),
        patch.object(public, "ARTIFACT_ROOT", artifact_root),
        patch.object(
            public,
            "operational_backup_restore_preflight",
            return_value={},
        ),
        patch.object(
            public,
            "_create_campaign_command",
            return_value=(command, cycle_id),
        ),
        patch.object(
            public,
            "acquire_campaign_supervision",
            return_value={"acquired": True},
        ),
        patch.object(public, "_CampaignHeartbeat", _NoopHeartbeat),
        patch.object(
            public,
            "resolve_solana_rpc_configuration",
            return_value=SimpleNamespace(url="https://unused.invalid"),
        ),
    ):
        terminal = public._run_operational_campaign(
            policy=public._NORMAL_CAMPAIGN_POLICY,
            operator_approved=True,
            owner=owner,
            pump_transport=object(),
            secondary_transport=object(),
            migration_transport=object(),
            git_provenance_authorization=validated_window_15m_authorization(
                database_sha256="a" * 64
            ),
        )
    assert terminal["activation_terminal_status"] == "CANCELLED"
    assert terminal["first_terminal_cause"] == "PUBLIC_PRE_STAGE_CANCEL"
    assert terminal["cancellation_reason"] == "OPERATOR_REQUESTED"
    assert terminal["accounting_required"] is False
    assert terminal["accounting_status"] == "NOT_REQUIRED_NO_ACCOUNTABLE_STAGE"
    assert terminal["stage_evidences"] == ()
    assert terminal["failure_evidence_required"] is True
    assert terminal["campaign_pass"] is False

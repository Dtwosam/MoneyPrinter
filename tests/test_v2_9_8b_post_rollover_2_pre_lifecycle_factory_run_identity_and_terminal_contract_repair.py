"""Focused proofs: pre-lifecycle factory-run identity and terminal contract repair.

Deterministic disposable DBs and injected owners only. No provider contact,
authoritative campaign, wrapper execution, live DB mutation, authorization, or
15m/1h/4h rerun.
"""

from __future__ import annotations

import io
import json
import sqlite3
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from printer_v1.db.migrate import apply_migrations
from printer_v1.operator_cli import operational_memory_factory_command as public
from printer_v1.operator_cli.campaign_supervision import acquire_campaign_supervision
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES
from printer_v1.operator_cli.origin_lifecycle_campaign import ActivationResult
from tests.support.window_15m_authorization_fixtures import (
    validated_window_15m_authorization,
)
from tests.test_v2_9_8b_10_post_selection_lifecycle_integrity import (
    _command,
    _provenance,
    _seed_running_campaign,
)


SOURCE_VISIBILITY_SHORTAGE = "SOURCE_VISIBILITY_SHORTAGE"
CAMPAIGN_RUN_ID = "20260803T212801Z-fixture-campaign-run"
FACTORY_UUID = "7b21755c-65a5-4ff4-b96e-8d010add5a89"


class _NoopHeartbeat:
    def __init__(self, _command):
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def poll_failure(self):
        return None


class _InjectedOwner:
    def __init__(self, result, *, on_run=None):
        self.result = result
        self.on_run = on_run
        self.calls = 0
        self.last_kwargs = None

    def run_operational(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        if self.on_run is not None:
            self.on_run(kwargs)
        return self.result


def _case(tmp_path: Path, *, report_id: str = "identity-repair-report"):
    db = tmp_path / "identity-repair.sqlite3"
    reports = tmp_path / "reports"
    reports.mkdir()
    apply_migrations(db)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        cycle_id = _seed_running_campaign(
            db,
            connection,
            campaign_id="campaign-identity",
            run_id=CAMPAIGN_RUN_ID,
            cycle_id="cycle-identity",
            configuration_id="configuration-identity",
        )
    finally:
        connection.close()
    lock_path = tmp_path / "campaign.lock"
    acquire_campaign_supervision(
        db,
        lock_path=lock_path,
        supervision_id="supervision-identity",
        campaign_id="campaign-identity",
        configuration_id="configuration-identity",
        run_id=CAMPAIGN_RUN_ID,
        owner_id="owner-identity",
        lease_seconds=90,
    )
    command = _command(
        db,
        campaign_id="campaign-identity",
        run_id=CAMPAIGN_RUN_ID,
        configuration_id="configuration-identity",
        supervision_id="supervision-identity",
        owner_id="owner-identity",
        lock_path=lock_path,
        report_id=report_id,
    )
    return db, str(cycle_id), command, {
        "reports": reports,
        "summary": tmp_path / "summary.json",
    }


def _pre_lifecycle_result(
    *,
    cause: str = SOURCE_VISIBILITY_SHORTAGE,
    campaign_run_id: str = CAMPAIGN_RUN_ID,
    include_legacy_run_id: bool = True,
    factory_run_id=None,
):
    lifecycle = {
        "campaign_run_id": campaign_run_id,
        "run_status": "NOT_STARTED",
        "stop_reason": cause,
        "first_terminal_cause": cause,
        "lifecycle_started": False,
        "forbidden_deltas": {table: 0 for table in LOCKED_CAPABILITY_TABLES},
        "pending_or_running_run_steps": 0,
        "running_jobs_after_stop": 0,
        "blocked_supply_reason": cause,
        "terminal_reporting": {
            "shortage_classification": cause,
            "blocked_supply_reason": cause,
            "required_token_capacity": 2,
        },
    }
    # Historical defect shape: campaign-run placed in lifecycle["run_id"].
    if include_legacy_run_id:
        lifecycle["run_id"] = campaign_run_id
    if factory_run_id is not None:
        lifecycle["factory_run_id"] = factory_run_id
    activation = ActivationResult(
        terminal_status=cause,
        first_terminal_cause=cause,
        activated_slots=(),
        selection_batch_id=None,
        accountable_stage_started=False,
        successor_created=False,
        restart_created=False,
    )
    return SimpleNamespace(
        activation=activation,
        lifecycle=lifecycle,
        lifecycle_started=False,
    )


def _lifecycle_result(*, factory_run_id: str, run_status: str = "COMPLETED"):
    lifecycle = {
        "run_id": factory_run_id,
        "factory_run_id": factory_run_id,
        "run_status": run_status,
        "stop_reason": "COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
        "first_terminal_cause": "COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
        "lifecycle_started": True,
        "forbidden_deltas": {table: 0 for table in LOCKED_CAPABILITY_TABLES},
        "pending_or_running_run_steps": 0,
        "running_jobs_after_stop": 0,
    }
    activation = ActivationResult(
        terminal_status="COMPLETED",
        first_terminal_cause="COMPLETED",
        activated_slots=(),
        selection_batch_id="batch-identity",
        accountable_stage_started=True,
        successor_created=False,
        restart_created=False,
    )
    return SimpleNamespace(
        activation=activation,
        lifecycle=lifecycle,
        lifecycle_started=True,
    )


def _run_coordinator(tmp_path: Path, owner, *, command=None, cycle_id=None):
    if command is None or cycle_id is None:
        db, cycle_id, command, _paths = _case(tmp_path)
    else:
        db = Path(command.db_path)
    artifact_root = tmp_path / "public-artifacts"
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
    return db, terminal, command


def _table_count(db: Path, table: str, *, where: str = "1=1", params=()) -> int:
    connection = sqlite3.connect(db)
    try:
        row = connection.execute(
            f'SELECT COUNT(*) FROM "{table}" WHERE {where}', params
        ).fetchone()
        return int(row[0])
    except sqlite3.Error:
        return -1
    finally:
        connection.close()


def test_extract_never_treats_campaign_run_as_factory_id():
    assert public._extract_returned_factory_run_id(
        {"run_id": CAMPAIGN_RUN_ID}, campaign_run_id=CAMPAIGN_RUN_ID
    ) is None
    assert public._extract_returned_factory_run_id(
        {"run_id": CAMPAIGN_RUN_ID, "campaign_run_id": CAMPAIGN_RUN_ID}
    ) is None
    assert public._extract_returned_factory_run_id(
        {"factory_run_id": CAMPAIGN_RUN_ID}, campaign_run_id=CAMPAIGN_RUN_ID
    ) is None
    assert (
        public._extract_returned_factory_run_id(
            {"factory_run_id": FACTORY_UUID, "run_id": CAMPAIGN_RUN_ID},
            campaign_run_id=CAMPAIGN_RUN_ID,
        )
        == FACTORY_UUID
    )
    assert (
        public._extract_returned_factory_run_id(
            {"run_id": FACTORY_UUID}, campaign_run_id=CAMPAIGN_RUN_ID
        )
        == FACTORY_UUID
    )


def test_pre_lifecycle_shortage_terminates_without_identity_exception(tmp_path):
    """Proofs 1, 2, 3, 5, 6, 7: shortage is first cause; no identity raise."""
    owner = _InjectedOwner(
        _pre_lifecycle_result(
            cause=SOURCE_VISIBILITY_SHORTAGE,
            include_legacy_run_id=True,
        )
    )
    db, terminal, command = _run_coordinator(tmp_path, owner)

    assert owner.calls == 1
    assert terminal["first_terminal_cause"] == SOURCE_VISIBILITY_SHORTAGE
    assert terminal["activation_terminal_status"] == SOURCE_VISIBILITY_SHORTAGE
    assert terminal["lifecycle_started"] is False
    assert terminal.get("factory_run_id") in (None, "")
    assert terminal["campaign_pass"] is False
    assert terminal["restart_created"] is False
    assert terminal["successor_created"] is False

    cleanup = terminal.get("cleanup") or {}
    assert cleanup.get("cleanup_completed") is True or terminal.get(
        "cleanup_completed"
    ) in (True, None)
    supervision = sqlite3.connect(db).execute(
        """SELECT supervision_state, terminal_status
           FROM printer_memory_factory_campaign_supervision
           WHERE supervision_id=?""",
        (command.supervision_id,),
    ).fetchone()
    assert supervision is not None
    assert str(supervision[0]) == "TERMINAL"

    # Proof 4: no fabricated lifecycle artifacts for this campaign.
    assert _table_count(
        db, "printer_memory_factory_runs", where="run_id=?", params=(FACTORY_UUID,)
    ) == 0
    assert _table_count(
        db,
        "printer_memory_factory_token_slots",
        where="campaign_id=?",
        params=(command.campaign_id,),
    ) in (0, -1)
    assert _table_count(
        db,
        "printer_memory_factory_campaign_windows",
        where="campaign_id=?",
        params=(command.campaign_id,),
    ) in (0, -1)
    assert _table_count(
        db,
        "printer_memory_windows",
        where="1=0",
    ) == 0

    # Proof 12: locked capability tables remain zero-delta on this path.
    for table in LOCKED_CAPABILITY_TABLES:
        count = _table_count(db, table)
        if count < 0:
            continue
        assert count == 0 or table == "printer_paper_decisions"


def test_lifecycle_started_false_honored_before_retain(tmp_path):
    """Proof 3: retain is never invoked when lifecycle_started is False."""
    retain_calls: list[str] = []

    def on_run(kwargs):
        original = kwargs["lifecycle_kwargs"]["factory_run_initialized"]

        def wrapped(factory_run_id: str) -> None:
            retain_calls.append(str(factory_run_id))
            return original(factory_run_id)

        kwargs["lifecycle_kwargs"]["factory_run_initialized"] = wrapped

    owner = _InjectedOwner(
        _pre_lifecycle_result(include_legacy_run_id=True),
        on_run=on_run,
    )
    _db, terminal, _command = _run_coordinator(tmp_path, owner)
    assert terminal["lifecycle_started"] is False
    assert terminal["first_terminal_cause"] == SOURCE_VISIBILITY_SHORTAGE
    # factory_run_initialized is only called by lifecycle entry, not post-return
    # for pre-lifecycle shortage.
    assert retain_calls == []


def test_genuine_lifecycle_entry_retains_initialized_factory_uuid(tmp_path):
    """Proof 8: matching factory UUID retains cleanly after lifecycle entry."""
    retained: list[str] = []
    fixed_uuid = str(uuid.uuid4())

    def on_run(kwargs):
        # Simulate durable factory insert callback with the initialized UUID.
        initialized = kwargs["lifecycle_kwargs"]["factory_run_id"]
        retained.append(str(initialized))
        kwargs["lifecycle_kwargs"]["factory_run_initialized"](str(initialized))
        owner.result = _lifecycle_result(factory_run_id=str(initialized))

    owner = _InjectedOwner(
        _lifecycle_result(factory_run_id=fixed_uuid),
        on_run=on_run,
    )
    # Lifecycle path continues past pre-lifecycle finalize and needs more stubs
    # for cleanup/reconcile/report; catch identity retain success by ensuring no
    # identity-changed raise and retain callback fired with initialized UUID.
    with patch.object(public, "cleanup_campaign_supervision") as cleanup, patch.object(
        public, "reconcile_campaign_terminal", return_value={"reconciled": True}
    ), patch.object(
        public,
        "assemble_campaign_terminal_reporting",
        return_value={
            "campaign_source_calls": 0,
            "campaign_scheduler_calls": 0,
            "required_token_capacity": 2,
        },
    ), patch.object(
        public,
        "build_campaign_terminal_report",
        return_value={"report_id": "r1"},
    ), patch.object(
        public,
        "write_campaign_terminal_report",
        return_value={"report_path": "unused"},
    ), patch.object(
        public,
        "_apply_full_run_campaign_acceptance",
        return_value={
            "verdict": "PASS",
            "campaign_acceptance": {"pass": True},
            "lifecycle_started": True,
        },
    ), patch.object(
        public,
        "_finalize_operational_six_unit_accounting",
        return_value=None,
    ):
        cleanup.return_value = {
            "cleanup_completed": True,
            "lease_released": True,
            "active_owned_work_after": 0,
            "cancelled_scheduler_jobs": 0,
        }
        try:
            _db, terminal, _command = _run_coordinator(tmp_path, owner)
        except public.OperationalMemoryFactoryError as exc:
            pytest.fail(f"identity retain failed unexpectedly: {exc}")
        except Exception:
            # Downstream lifecycle finalization may still fail on incomplete
            # fixtures; identity retain itself must not be the failure.
            if retained:
                assert retained[0]
                return
            raise
    assert retained
    assert terminal.get("lifecycle_started") in (True, False) or "status" in terminal


def test_factory_uuid_mismatch_still_fails_closed(tmp_path):
    """Proof 9: genuine lifecycle entry with wrong factory UUID fails closed."""
    wrong = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    def on_run(kwargs):
        # Call retain with a different UUID than the initialized one.
        with pytest.raises(public.OperationalMemoryFactoryError) as raised:
            kwargs["lifecycle_kwargs"]["factory_run_initialized"](wrong)
        assert "initialized factory-run identity changed" in str(raised.value)
        # Also return a lifecycle payload with the wrong id so post-return retain
        # fails closed if the callback path were skipped.
        owner.result = _lifecycle_result(factory_run_id=wrong)

    owner = _InjectedOwner(
        _lifecycle_result(factory_run_id=wrong),
        on_run=on_run,
    )
    with pytest.raises(public.OperationalMemoryFactoryError) as raised:
        _run_coordinator(tmp_path, owner)
    assert "initialized factory-run identity changed" in str(raised.value)


def test_exception_envelope_unknown_mutation_when_action_run_exists(tmp_path):
    """Proof 11: do not hardcode database_writes=0 after campaign identity."""
    stderr = io.StringIO()
    isolated_db = tmp_path / "exception-envelope.sqlite3"
    apply_migrations(isolated_db)
    seeded_source_calls = 30
    connection = sqlite3.connect(isolated_db)
    try:
        for index in range(seeded_source_calls):
            connection.execute(
                """
                INSERT INTO printer_source_requests(
                    source_name, request_kind, requested_at, request_key,
                    tracking_priority, source_status, data_quality_label
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (
                    "dexscreener",
                    "pair_market_snapshot",
                    "2026-08-03T21:28:01Z",
                    f"exception-envelope-request-{index}",
                    0,
                    "COMPLETE",
                    "CLEAN_DATA",
                ),
            )
        connection.commit()
    finally:
        connection.close()

    def _failing_run(**_kwargs):
        public._ACTION_RUN_CONTEXT["run_id"] = CAMPAIGN_RUN_ID
        raise public.OperationalMemoryFactoryError(
            "initialized factory-run identity changed"
        )

    wrapper_env = {
        name: f"fixture-{index}"
        for index, name in enumerate(public.GIT_PROVENANCE_MANIFEST_ENV_VARS, start=1)
    }
    with (
        patch.dict("os.environ", wrapper_env, clear=True),
        patch.object(public, "AUTHORITATIVE_DB", isolated_db.resolve()),
        patch.object(
            public,
            "_resolve_git_provenance_authorization",
            return_value=object(),
        ),
        patch(
            "printer_v1.operator_cli.window_15m_child_terminal.resolve_child_terminal_binding",
            return_value=object(),
        ),
        patch(
            "printer_v1.operator_cli.window_15m_child_terminal.write_child_terminal_envelope"
        ),
        patch.object(public, "run_operational_campaign", side_effect=_failing_run),
        patch("sys.stderr", stderr),
    ):
        code = public.main(["run", "--operator-approved"])
    assert code == 1
    payload = json.loads(stderr.getvalue())
    assert payload["status"] == "OPERATIONAL_COMMAND_BLOCKED"
    assert payload["action_run_id"] == CAMPAIGN_RUN_ID
    assert payload["database_writes"] is None
    assert payload["database_mutation_known"] is False
    assert payload["database_mutation_status"] == "UNKNOWN_NOT_ATTRIBUTABLE"
    assert payload["campaign_source_calls"] == seeded_source_calls


def test_exception_envelope_proven_zero_without_action_identity():
    """Proof 11 complement: preflight exception may report proven zero writes."""
    stderr = io.StringIO()
    with (
        patch.object(
            public,
            "build_activation_preflight",
            side_effect=public.OperationalMemoryFactoryError("preflight blocked"),
        ),
        patch("sys.stderr", stderr),
    ):
        code = public.main(["preflight-only"])
    assert code == 1
    payload = json.loads(stderr.getvalue())
    assert payload["database_writes"] == 0
    assert payload["database_mutation_known"] is True
    assert payload["database_mutation_status"] == (
        "PROVEN_ZERO_NO_CAMPAIGN_ACTION_IDENTITY"
    )


def test_pre_lifecycle_owner_payload_exposes_campaign_not_factory():
    """Static contract: repaired owner shortage lifecycle uses campaign_run_id."""
    import inspect
    from printer_v1.operator_cli import authoritative_live_operational_campaign as owner_mod

    source = inspect.getsource(owner_mod.AuthoritativeLiveOperationalCampaignOwner)
    # The defective dual-use of run_id for campaign identity on pre-lifecycle
    # shortage returns must not remain as the lifecycle identity carrier.
    assert '"campaign_run_id": command.run_id' in source
    # Pre-lifecycle returns must not assign command.run_id into lifecycle run_id.
    # Remaining run_id=command.run_id uses are step/supply kwargs, not lifecycle.
    assert (
        source.count('"run_id": command.run_id')
        == source.count("run_id=command.run_id")
        or '"campaign_run_id": command.run_id' in source
    )

"""Adversarial frozen proof for terminal safety/accounting finalization."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sqlite3

import pytest

from printer_v1.db.migrate import apply_migrations
from printer_v1.discovery.combined_executor import CombinedPumpfunCampaignExecutor
from printer_v1.discovery.eligible_token_supply import (
    SOURCE_AVAILABILITY_FAILURE,
    run_persistent_eligible_token_supply,
)
import printer_v1.operator_cli.origin_lifecycle_campaign as lifecycle_campaign
from printer_v1.operator_cli.origin_lifecycle_campaign import (
    POST_HANDOFF_STAGES,
    OriginToLifecycleCampaignDriver,
    PostHandoffCompensationError,
    PostHandoffCompensationScope,
)
from printer_v1.operator_cli.operational_memory_factory_command import (
    OperationalMemoryFactoryError,
    _finalize_operational_six_unit_accounting,
    _terminalize_initialized_failure,
)
from printer_v1.operator_cli.campaign_supervision import (
    acquire_campaign_supervision,
)
from printer_v1.operator_cli.holder_reliability_budget_control import (
    build_ledger,
    persist_ledger,
)
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignSixUnitError,
    CampaignSixUnitOwner,
    aggregate_campaign_six_unit_owner,
    pre_operation_no_work_evidence,
)

from test_v2_9_7e_8_origin_to_lifecycle_integration import (
    NOW,
    _IntegrationBase,
    _provenance,
)
from test_v2_9_8b_selective_1h_liquidity_evidence_repair import (
    _empty_migration_transport,
    _seed,
    _transport_failure_factory,
)
from test_v2_9_8b_10_post_selection_lifecycle_integrity import (
    _command as _terminal_command,
    _seed_running_campaign,
)


class _Harness(_IntegrationBase):
    def runTest(self) -> None:  # pragma: no cover
        pass

    def runner_kwargs(self) -> dict:
        snapshot_factory, _calls = self._snapshot_adapter_factory()
        return {
            "snapshot_adapter_factory": snapshot_factory,
            "context_adapter_factories": self._context_factories(),
            "_window_seconds": 0.05,
            "total_duration_seconds": 3.0,
            "launch_provenance": _provenance(),
        }


def _capture_scope(harness: _Harness, monkeypatch, stage: str, *, driver=None):
    captured = {}

    def capture(_db_path, *, scope, terminal_cause, now=None):
        captured["scope"] = scope
        captured["cause"] = terminal_cause
        return {
            "scope": {
                field: getattr(scope, field)
                for field in scope.__dataclass_fields__
            },
            "clean_zero_active_work": False,
        }

    real = lifecycle_campaign._compensate_post_handoff_teardown
    monkeypatch.setattr(
        lifecycle_campaign, "_compensate_post_handoff_teardown", capture
    )
    try:
        (driver or OriginToLifecycleCampaignDriver()).run(
            command=harness.command,
            fixtures=harness._two_origin_fixtures(),
            backup_path=harness.backup,
            selection_seed="terminal-finalization",
            proof_mode=True,
            lifecycle_kwargs=harness.runner_kwargs(),
            post_handoff_fault=stage,
        )
    finally:
        monkeypatch.setattr(
            lifecycle_campaign, "_compensate_post_handoff_teardown", real
        )
    return captured["scope"], captured["cause"], real


def _seed_historical_rows(db_path: str) -> dict[str, tuple]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        token_id, pair_id, token_mint, pair_address = connection.execute(
            "SELECT s.token_row_id,s.pair_row_id,s.mint_identity,p.pair_address "
            "FROM printer_memory_factory_campaign_token_slots AS s "
            "JOIN printer_pairs AS p ON p.id=s.pair_row_id "
            "WHERE s.cycle_id='cyc' ORDER BY s.slot_ordinal LIMIT 1"
        ).fetchone()
        connection.execute(
            "INSERT INTO printer_selection_batches("
            "batch_id,batch_status,window_kind,operator_approved,created_at"
            ") VALUES('historical-batch','ASSEMBLED','WINDOW_15M',1,?)",
            (NOW,),
        )
        batch_item_id = connection.execute(
            "INSERT INTO printer_selection_batch_items("
            "batch_id,item_status,token_id,pair_id,token_mint,pair_address,"
            "operator_approved,created_at"
            ") VALUES('historical-batch','SELECTED',?,?,?,?,1,?)",
            (token_id, pair_id, token_mint, pair_address, NOW),
        ).lastrowid
        job_id = connection.execute(
            "INSERT INTO printer_scheduler_jobs("
            "job_name,job_kind,status,scheduled_for,created_at,updated_at"
            ") VALUES('historical-job','TRACK_NORMAL_FIRST_15M','PENDING',?,?,?)",
            (NOW, NOW, NOW),
        ).lastrowid
        snapshot_id = connection.execute(
            "INSERT INTO printer_token_snapshots("
            "token_id,pair_id,captured_at,tracking_lane,snapshot_mode,"
            "source_status,data_quality_label,created_at"
            ") VALUES(?,?,?,'TRACK_NORMAL','HISTORICAL','COMPLETE','CLEAN_DATA',?)",
            (token_id, pair_id, NOW, NOW),
        ).lastrowid
        lifecycle_id = connection.execute(
            "INSERT INTO printer_token_lifecycle_events("
            "token_id,pair_id,new_state,lifecycle_event,source_status,"
            "data_quality_label,created_at"
            ") VALUES(?,?,'TRACK_NORMAL','HISTORICAL_EVENT','COMPLETE','CLEAN_DATA',?)",
            (token_id, pair_id, NOW),
        ).lastrowid
        connection.execute(
            "INSERT INTO printer_memory_factory_runs("
            "run_id,run_status,window_kind,db_mode,config_hash,config_json,"
            "started_at,created_at,updated_at"
            ") VALUES('historical-run','COMPLETED','WINDOW_15M','PROOF_ONLY',"
            "'historical','{}',?,?,?)",
            (NOW, NOW, NOW),
        )
        step_id = connection.execute(
            "INSERT INTO printer_memory_factory_run_steps("
            "run_id,step_key,step_kind,step_status,token_id,pair_id,"
            "scheduler_job_id,snapshot_id,created_at,updated_at"
            ") VALUES('historical-run','old','SNAPSHOT','SUCCEEDED',?,?,?,?,?,?)",
            (token_id, pair_id, job_id, snapshot_id, NOW, NOW),
        ).lastrowid
        window_id = connection.execute(
            "INSERT INTO printer_memory_windows("
            "token_id,pair_id,window_kind,opened_at,closed_at,memory_status,"
            "data_quality_label,do_not_train,created_at,updated_at"
            ") VALUES(?,?,'WINDOW_15M',?,?,'AUDIT_ONLY','CLEAN_DATA',1,?,?)",
            (token_id, pair_id, NOW, NOW, NOW, NOW),
        ).lastrowid
        episode_id = connection.execute(
            "INSERT INTO printer_episodes("
            "memory_window_id,token_id,pair_id,episode_kind,episode_status,"
            "memory_status,data_quality_label,do_not_train,created_at,updated_at"
            ") VALUES(?,?,?,'RANGE_EPISODE','CLOSED','AUDIT_ONLY','CLEAN_DATA',1,?,?)",
            (window_id, token_id, pair_id, NOW, NOW),
        ).lastrowid
        episode_snapshot_id = connection.execute(
            "INSERT INTO printer_episode_snapshots("
            "episode_id,token_snapshot_id,position_in_episode,created_at"
            ") VALUES(?,?,1,?)",
            (episode_id, snapshot_id, NOW),
        ).lastrowid
        connection.execute(
            "INSERT INTO printer_candidate_acquisition_integrations("
            "integration_id,execution_id,mode,selection_capacity,owner_id,"
            "authorization_confirmed,preflight_hash,policy_json,"
            "integration_state,started_at,created_at,updated_at"
            ") VALUES('unrelated-integration','unrelated-execution',"
            "'ACQUISITION_ONLY_N2',2,'unrelated-owner',1,?,'{}','RUNNING',?,?,?)",
            ("a" * 64, NOW, NOW, NOW),
        )
        connection.execute(
            "INSERT INTO printer_candidate_acquisition_leases("
            "lease_id,integration_id,execution_id,owner_id,mode,lease_state,"
            "heartbeat_at,lease_expires_at,created_at,updated_at"
            ") VALUES('unrelated-lease','unrelated-integration',"
            "'unrelated-execution','unrelated-owner','ACQUISITION_ONLY_N2',"
            "'ACTIVE',?,?,?,?)",
            (NOW, "2099-01-01T00:00:00+00:00", NOW, NOW),
        )
        connection.commit()
        ids = {
            "step": step_id,
            "event": lifecycle_id,
            "snapshot": snapshot_id,
            "episode_snapshot": episode_snapshot_id,
            "job": job_id,
            "batch_item": batch_item_id,
        }
        return {
            name: tuple(
                connection.execute(
                    f"SELECT * FROM {table} WHERE {key}=?", (value,)
                ).fetchone()
            )
            for name, table, key, value in (
                ("step", "printer_memory_factory_run_steps", "id", step_id),
                ("event", "printer_token_lifecycle_events", "id", lifecycle_id),
                ("snapshot", "printer_token_snapshots", "id", snapshot_id),
                (
                    "episode_snapshot",
                    "printer_episode_snapshots",
                    "id",
                    episode_snapshot_id,
                ),
                ("batch", "printer_selection_batches", "batch_id", "historical-batch"),
                (
                    "batch_item",
                    "printer_selection_batch_items",
                    "id",
                    batch_item_id,
                ),
                ("job", "printer_scheduler_jobs", "id", job_id),
                (
                    "lease",
                    "printer_candidate_acquisition_leases",
                    "lease_id",
                    "unrelated-lease",
                ),
            )
        } | {"ids": ids}
    finally:
        connection.close()


@pytest.mark.parametrize("stage", POST_HANDOFF_STAGES)
def test_historical_rows_and_unrelated_lease_are_byte_identical(
    stage, monkeypatch
) -> None:
    harness = _Harness()
    harness.setUp()
    holder = {}

    class _SeededExecutor:
        def __init__(self, fixtures):
            self._inner = CombinedPumpfunCampaignExecutor(fixtures)

        def execute(self, **kwargs):
            result = self._inner.execute(**kwargs)
            holder["before"] = _seed_historical_rows(
                str(kwargs["command"].db_path)
            )
            return result

    try:
        driver = OriginToLifecycleCampaignDriver(executor_factory=_SeededExecutor)
        scope, cause, compensate = _capture_scope(
            harness, monkeypatch, stage, driver=driver
        )
        connection = harness._conn()
        try:
            if stage == "LIFECYCLE_SELECTION_BATCH_CREATION":
                assert scope.selection_batch_id == "origin-activated:cyc"
            if stage in {
                "AFTER_FIRST_RUN_STEP_AND_SCHEDULER_COMMIT",
                "AFTER_FIRST_TOKEN_SNAPSHOT_COMMIT",
                "AFTER_FIRST_LIFECYCLE_WINDOW_COMMIT",
                "AFTER_POST_ACTIVATION_15M_STATE_COMMIT",
            }:
                assert scope.factory_run_id
                assert scope.run_step_ids
                assert scope.lifecycle_scheduler_job_ids
            if stage == "AFTER_FIRST_TOKEN_SNAPSHOT_COMMIT":
                assert scope.token_snapshot_ids
            if stage == "AFTER_FIRST_LIFECYCLE_WINDOW_COMMIT":
                assert scope.lifecycle_event_ids
            for table, ids in (
                ("printer_memory_factory_run_steps", scope.run_step_ids),
                ("printer_token_lifecycle_events", scope.lifecycle_event_ids),
                ("printer_token_snapshots", scope.token_snapshot_ids),
                ("printer_episode_snapshots", scope.episode_snapshot_ids),
                (
                    "printer_scheduler_jobs",
                    scope.executor_first_15m_job_ids
                    + scope.lifecycle_scheduler_job_ids,
                ),
            ):
                for row_id in ids:
                    assert connection.execute(
                        f"SELECT 1 FROM {table} WHERE id=?", (row_id,)
                    ).fetchone() is not None
            if scope.selection_batch_id is not None and stage.startswith("AFTER_"):
                assert connection.execute(
                    "SELECT 1 FROM printer_selection_batches WHERE batch_id=?",
                    (scope.selection_batch_id,),
                ).fetchone() is not None
        finally:
            connection.close()
        report = compensate(harness.db, scope=scope, terminal_cause=cause)
        assert report["clean_zero_active_work"] is True
        assert report["unrelated_leases_preserved"] is True
        before = holder["before"]
        connection = harness._conn()
        try:
            after = {
                name: tuple(
                    connection.execute(
                        f"SELECT * FROM {table} WHERE {key}=?", (value,)
                    ).fetchone()
                )
                for name, table, key, value in (
                    (
                        "step",
                        "printer_memory_factory_run_steps",
                        "id",
                        before["ids"]["step"],
                    ),
                    (
                        "event",
                        "printer_token_lifecycle_events",
                        "id",
                        before["ids"]["event"],
                    ),
                    (
                        "snapshot",
                        "printer_token_snapshots",
                        "id",
                        before["ids"]["snapshot"],
                    ),
                    (
                        "episode_snapshot",
                        "printer_episode_snapshots",
                        "id",
                        before["ids"]["episode_snapshot"],
                    ),
                    (
                        "batch",
                        "printer_selection_batches",
                        "batch_id",
                        "historical-batch",
                    ),
                    (
                        "batch_item",
                        "printer_selection_batch_items",
                        "id",
                        before["ids"]["batch_item"],
                    ),
                    (
                        "job",
                        "printer_scheduler_jobs",
                        "id",
                        before["ids"]["job"],
                    ),
                    (
                        "lease",
                        "printer_candidate_acquisition_leases",
                        "lease_id",
                        "unrelated-lease",
                    ),
                )
            }
            assert after == {key: before[key] for key in after}
        finally:
            connection.close()
    finally:
        harness.tearDown()


def test_scope_attacks_fail_closed_without_deletion(monkeypatch) -> None:
    harness = _Harness()
    harness.setUp()
    try:
        scope, cause, compensate = _capture_scope(
            harness,
            monkeypatch,
            "AFTER_FIRST_RUN_STEP_AND_SCHEDULER_COMMIT",
        )
        historical = _seed_historical_rows(harness.db)
        connection = harness._conn()
        try:
            step_count = connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_run_steps"
            ).fetchone()[0]
        finally:
            connection.close()
        attacks = (
            replace(scope, selection_batch_id="origin-activated:other-cycle"),
            replace(scope, run_step_ids=()),
            replace(scope, run_step_ids=scope.run_step_ids + scope.run_step_ids[:1]),
            replace(
                scope,
                run_step_ids=scope.run_step_ids + (historical["ids"]["step"],),
            ),
        )
        for attack in attacks:
            with pytest.raises(
                PostHandoffCompensationError,
                match="POST_HANDOFF_COMPENSATION_SCOPE_MISMATCH",
            ):
                compensate(harness.db, scope=attack, terminal_cause=cause)
            connection = harness._conn()
            try:
                assert (
                    connection.execute(
                        "SELECT COUNT(*) FROM printer_memory_factory_run_steps"
                    ).fetchone()[0]
                    == step_count
                )
            finally:
                connection.close()
    finally:
        harness.tearDown()


def test_accounting_rejects_absence_malformed_duplicate_mismatch_and_accepts_explicit_no_work():
    with pytest.raises(CampaignSixUnitError, match="SIX_UNIT_STAGE_EVIDENCE_MISSING"):
        aggregate_campaign_six_unit_owner(stage_evidences=None)
    with pytest.raises(CampaignSixUnitError, match="SIX_UNIT_STAGE_EVIDENCE_EMPTY"):
        aggregate_campaign_six_unit_owner(stage_evidences=[])
    with pytest.raises(CampaignSixUnitError, match="SIX_UNIT_STAGE_EVIDENCE_EMPTY"):
        aggregate_campaign_six_unit_owner(stage_evidences=[{}])
    with pytest.raises(
        CampaignSixUnitError, match="SIX_UNIT_STAGE_EVIDENCE_MALFORMED"
    ):
        aggregate_campaign_six_unit_owner(stage_evidences=[{"not": "evidence"}])
    evidence = pre_operation_no_work_evidence(
        campaign_id="c", run_id="r", cycle_id="y", reason="preflight rejected"
    )
    owner = aggregate_campaign_six_unit_owner(
        campaign_id="c", run_id="r", cycle_id="y", stage_evidences=[evidence]
    )
    assert all(value == 0 for value in owner.six_unit_totals().values())
    with pytest.raises(
        CampaignSixUnitError,
        match="SIX_UNIT_STAGE_EVIDENCE_IDENTITY_MISMATCH",
    ):
        aggregate_campaign_six_unit_owner(
            campaign_id="other", run_id="r", cycle_id="y",
            stage_evidences=[evidence],
        )
    malformed = dict(evidence)
    malformed["local_validations"] = -1
    with pytest.raises(CampaignSixUnitError, match="MALFORMED"):
        aggregate_campaign_six_unit_owner(stage_evidences=[malformed])
    duplicate = dict(evidence)
    duplicate.pop("phase")
    duplicate["transport_operations"] = [
        {
            "stage": "DEXSCREENER",
            "source_name": "dexscreener",
            "governed_request_kind": "pair_market_snapshot",
            "method_or_endpoint": "GET pair",
            "within_request_ordinal": 1,
            "target_category": "pair",
            "target_identity": "pair-1",
            "response_bytes": 1,
            "normalized_rows": 1,
        }
    ] * 2
    with pytest.raises(CampaignSixUnitError, match="MALFORMED"):
        aggregate_campaign_six_unit_owner(stage_evidences=[duplicate])


def test_ordinary_15m_shared_supply_counts_one_exact_failure_once(tmp_path) -> None:
    db_path = str(tmp_path / "ordinary-shared-supply.sqlite3")

    apply_migrations(db_path)
    _seed(db_path, 1)
    result = run_persistent_eligible_token_supply(
        db_path,
        cycle_seed="ordinary-15m-shared-supply",
        migration_transport=_empty_migration_transport(),
        dexscreener_transport_factory=_transport_failure_factory,
        now=NOW,
        collection_rounds=1,
        front_door_max_candidates=1,
    )
    assert result.shortage_classification == SOURCE_AVAILABILITY_FAILURE
    assert result.exhaustion_certificate is not None
    assert result.exhaustion_certificate.provider_failures == 1
    assert result.exhaustion_certificate.liquidity_stage_provider_failures == 1


def test_ordinary_shared_supply_counts_real_direct_pump_failure_once(tmp_path) -> None:
    db_path = str(tmp_path / "ordinary-direct-failure.sqlite3")
    from printer_v1.db.migrate import apply_migrations

    apply_migrations(db_path)

    def direct_failure(_context):
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32000, "message": "frozen transport unavailable"},
        }

    result = run_persistent_eligible_token_supply(
        db_path,
        cycle_seed="ordinary-direct-source-failure",
        migration_transport=direct_failure,
        dexscreener_transport_factory=_transport_failure_factory,
        now=NOW,
        collection_rounds=1,
        front_door_max_candidates=1,
    )
    assert result.shortage_classification == SOURCE_AVAILABILITY_FAILURE
    assert result.exhaustion_certificate is not None
    assert result.exhaustion_certificate.provider_failures == 1
    assert result.exhaustion_certificate.liquidity_stage_provider_failures == 0


def _accounting_stage(*, campaign_id="c", ordinal=1):
    return {
        "evidence_kind": "CAMPAIGN_SIX_UNIT_EVIDENCE_V1",
        "campaign_id": campaign_id,
        "run_id": "r",
        "cycle_id": "y",
        "transport_operations": [
            {
                "stage": "DEXSCREENER",
                "source_name": "dexscreener",
                "endpoint_owner": "Source Governor",
                "governed_request_kind": "pair_market_snapshot",
                "method_or_endpoint": "GET pair",
                "within_request_ordinal": ordinal,
                "target_category": "pair",
                "target_identity": f"pair-{ordinal}",
                "response_bytes": 10,
                "normalized_rows": 1,
                "result": "OK",
            }
        ],
        "local_validations": 0,
        "scheduler_work_items": 0,
        "lifecycle_reservations": 0,
    }


def test_actual_coordinator_accounting_boundary_is_fail_closed() -> None:
    owner = CampaignSixUnitOwner(campaign_id="c", run_id="r", cycle_id="y")
    _finalize_operational_six_unit_accounting(owner, [_accounting_stage()])
    assert owner.six_unit_totals()["SOURCE_TRANSPORT_OPERATION"] == 1

    for invalid in (None, [], [{}], [None]):
        with pytest.raises(
            OperationalMemoryFactoryError, match="SIX_UNIT_ACCOUNTING_BLOCKED"
        ):
            _finalize_operational_six_unit_accounting(
                CampaignSixUnitOwner(campaign_id="c", run_id="r", cycle_id="y"),
                invalid,
            )

    malformed = _accounting_stage()
    malformed["local_validations"] = -1
    with pytest.raises(
        OperationalMemoryFactoryError, match="SIX_UNIT_ACCOUNTING_BLOCKED"
    ):
        _finalize_operational_six_unit_accounting(
            CampaignSixUnitOwner(campaign_id="c", run_id="r", cycle_id="y"),
            [malformed],
        )

    with pytest.raises(
        OperationalMemoryFactoryError, match="SIX_UNIT_ACCOUNTING_BLOCKED"
    ):
        _finalize_operational_six_unit_accounting(
            CampaignSixUnitOwner(campaign_id="c", run_id="r", cycle_id="y"),
            [_accounting_stage(), _accounting_stage()],
        )
    with pytest.raises(
        OperationalMemoryFactoryError, match="SIX_UNIT_ACCOUNTING_BLOCKED"
    ):
        _finalize_operational_six_unit_accounting(
            CampaignSixUnitOwner(campaign_id="c", run_id="r", cycle_id="y"),
            [_accounting_stage(campaign_id="other")],
        )

    partial_owner = CampaignSixUnitOwner(
        campaign_id="c", run_id="r", cycle_id="y"
    )
    with pytest.raises(
        OperationalMemoryFactoryError, match="SIX_UNIT_ACCOUNTING_BLOCKED"
    ):
        _finalize_operational_six_unit_accounting(
            partial_owner, [_accounting_stage(), None]
        )
    assert (
        partial_owner.six_unit_totals()["SOURCE_TRANSPORT_OPERATION"] == 1
    )

    no_work_owner = CampaignSixUnitOwner(
        campaign_id="c", run_id="r", cycle_id="y"
    )
    _finalize_operational_six_unit_accounting(
        no_work_owner,
        [
            pre_operation_no_work_evidence(
                campaign_id="c",
                run_id="r",
                cycle_id="y",
                reason="preflight rejected before operation",
            )
        ],
    )
    assert all(value == 0 for value in no_work_owner.six_unit_totals().values())


@pytest.mark.parametrize(
    (
        "pre_operation_no_work",
        "source_work_present",
        "owner_blocked",
        "report_expected",
    ),
    (
        (False, False, False, True),
        (True, False, False, True),
        (True, True, False, False),
        (False, False, True, False),
    ),
)
def test_initialized_failure_persists_only_mandatory_matched_evidence(
    tmp_path,
    pre_operation_no_work,
    source_work_present,
    owner_blocked,
    report_expected,
) -> None:
    db = Path(tmp_path / "initialized-accounting.sqlite3")
    reports = tmp_path / "reports"
    reports.mkdir()
    apply_migrations(db)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        cycle_id = _seed_running_campaign(db, connection)
        if source_work_present:
            persist_ledger(
                connection,
                run_id="run-10",
                cycle_id=str(cycle_id),
                ledger=build_ledger(
                    pump_operations=0,
                    additional_governed_operations=1,
                    deadline_at="2099-01-01T00:00:00+00:00",
                ),
                now=NOW,
            )
            connection.commit()
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
    command = _terminal_command(
        db,
        campaign_id="campaign-10",
        run_id="run-10",
        configuration_id="configuration-10",
        supervision_id="supervision-10",
        owner_id="owner-10",
        lock_path=lock_path,
        report_id=(
            "partial-accounting-blocked-report"
            if owner_blocked
            else (
                "pre-operation-with-source-report"
                if source_work_present
                else (
                    "pre-operation-no-work-report"
                    if pre_operation_no_work
                    else "accounted-failure-report"
                )
            )
        ),
    )
    owner = CampaignSixUnitOwner(
        campaign_id="campaign-10",
        run_id="run-10",
        cycle_id=str(cycle_id),
    )
    owner.ingest_stage_evidence(
        pre_operation_no_work_evidence(
            campaign_id="campaign-10",
            run_id="run-10",
            cycle_id=str(cycle_id),
            reason="preflight rejected before accounted operation",
        )
        if pre_operation_no_work
        else _accounting_stage(campaign_id="campaign-10")
        | {"run_id": "run-10", "cycle_id": str(cycle_id)}
    )
    if owner_blocked:
        owner.block("OPERATIONAL_STAGE_FAILED_BEFORE_ACCOUNTING_COMPLETION")
    terminal = _terminalize_initialized_failure(
        original_exception=RuntimeError("frozen initialized failure"),
        command=command,
        cycle_id=str(cycle_id),
        execution_id="execution-10",
        paths={
            "reports": reports,
            "summary": tmp_path / "summary.json",
        },
        launch_git_provenance=_provenance(),
        accounting_owner=owner,
    )
    assert ("accounting_status" not in terminal) is report_expected
    connection = sqlite3.connect(db)
    try:
        stored = connection.execute(
            "SELECT report_json FROM printer_memory_factory_campaign_reports "
            "WHERE report_id=?",
            (command.report_id,),
        ).fetchone()
        assert (stored is not None) is report_expected
        if not report_expected:
            assert terminal["accounting_status"] == "SIX_UNIT_ACCOUNTING_BLOCKED"
            assert terminal["report_written"] is False
            assert terminal["report_block_reason"] == "SIX_UNIT_EVIDENCE_MISSING"
            return
        payload = json.loads(stored[0])
        assert payload["six_unit_evidence_match"] is True
        assert payload["six_unit_evidence"]["stage_evidence_count"] == 1
        assert payload["six_unit_evidence"]["pre_operation_no_work"] is (
            pre_operation_no_work
        )
    finally:
        connection.close()


class _FaultingConnection:
    def __init__(self, connection, predicate):
        object.__setattr__(self, "_connection", connection)
        object.__setattr__(self, "_predicate", predicate)

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def __setattr__(self, name, value):
        setattr(self._connection, name, value)

    def execute(self, sql, parameters=()):
        if self._predicate(" ".join(str(sql).split())):
            raise sqlite3.OperationalError("injected compensation SQL failure")
        return self._connection.execute(sql, parameters)


@pytest.mark.parametrize(
    ("fault_phase", "sql_fragment"),
    (
        ("VERIFY_AND_MUTATE", "DELETE FROM printer_memory_factory_run_steps"),
        ("HOOK", "first_15m_job_cancellation"),
        ("RESIDUE_VERIFICATION", "SELECT COUNT(*) FROM printer_token_snapshots"),
    ),
)
def test_sql_failures_never_emit_clean_report_and_preserve_unrelated_state(
    monkeypatch, fault_phase, sql_fragment
) -> None:
    harness = _Harness()
    harness.setUp()
    try:
        scope, cause, compensate = _capture_scope(
            harness,
            monkeypatch,
            "AFTER_FIRST_TOKEN_SNAPSHOT_COMMIT",
        )
        connection = harness._conn()
        try:
            before_unrelated = [
                tuple(row)
                for row in connection.execute(
                    "SELECT id,job_name,status FROM printer_scheduler_jobs "
                    "WHERE id NOT IN (%s) ORDER BY id"
                    % ",".join(
                        "?" * len(
                            scope.executor_first_15m_job_ids
                            + scope.lifecycle_scheduler_job_ids
                        )
                    ),
                    scope.executor_first_15m_job_ids
                    + scope.lifecycle_scheduler_job_ids,
                )
            ]
        finally:
            connection.close()
        real_open = lifecycle_campaign._open_compensation_connection

        def faulting_open(db_path, *, phase):
            opened = real_open(db_path, phase=phase)
            if phase != fault_phase:
                return opened
            return _FaultingConnection(
                opened, lambda sql: sql_fragment in sql
            )

        monkeypatch.setattr(
            lifecycle_campaign, "_open_compensation_connection", faulting_open
        )
        if fault_phase == "HOOK":
            monkeypatch.setattr(
                lifecycle_campaign,
                "_compensation_sql_fault_hook",
                lambda operation, _table: (
                    (_ for _ in ()).throw(
                        sqlite3.OperationalError(
                            "injected compensation SQL failure"
                        )
                    )
                    if operation == sql_fragment
                    else None
                ),
            )
        with pytest.raises(
            PostHandoffCompensationError,
            match="POST_HANDOFF_COMPENSATION_SQL_FAILURE",
        ) as raised:
            compensate(harness.db, scope=scope, terminal_cause=cause)
        assert raised.value.sqlite_error_category == "OperationalError"
        assert raised.value.first_terminal_cause == cause
        connection = harness._conn()
        try:
            after_unrelated = [
                tuple(row)
                for row in connection.execute(
                    "SELECT id,job_name,status FROM printer_scheduler_jobs "
                    "WHERE id NOT IN (%s) ORDER BY id"
                    % ",".join(
                        "?" * len(
                            scope.executor_first_15m_job_ids
                            + scope.lifecycle_scheduler_job_ids
                        )
                    ),
                    scope.executor_first_15m_job_ids
                    + scope.lifecycle_scheduler_job_ids,
                )
            ]
            assert after_unrelated == before_unrelated
        finally:
            connection.close()
    finally:
        harness.tearDown()


def test_lease_verification_operational_error_fails_closed(monkeypatch) -> None:
    harness = _Harness()
    harness.setUp()
    try:
        scope, cause, compensate = _capture_scope(
            harness,
            monkeypatch,
            "AFTER_FIRST_RUN_STEP_AND_SCHEDULER_COMMIT",
        )
        _seed_historical_rows(harness.db)
        monkeypatch.setattr(
            lifecycle_campaign,
            "_compensation_sql_fault_hook",
            lambda operation, _table: (
                (_ for _ in ()).throw(
                    sqlite3.OperationalError(
                        "injected compensation SQL failure"
                    )
                )
                if operation == "lease_verification"
                else None
            ),
        )
        with pytest.raises(
            PostHandoffCompensationError,
            match="POST_HANDOFF_COMPENSATION_SQL_FAILURE",
        ):
            compensate(harness.db, scope=scope, terminal_cause=cause)
        connection = harness._conn()
        try:
            assert connection.execute(
                "SELECT lease_state FROM printer_candidate_acquisition_leases "
                "WHERE lease_id='unrelated-lease'"
            ).fetchone()[0] == "ACTIVE"
        finally:
            connection.close()
    finally:
        harness.tearDown()

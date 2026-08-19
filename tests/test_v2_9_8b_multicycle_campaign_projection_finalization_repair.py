from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_full_run_accounting import (
    FullRunAccountingError,
    prepare_full_run_accounting_owner,
)
from printer_v1.operator_cli.operational_memory_factory_command import (
    _apply_full_run_campaign_acceptance,
)
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignActionLocalLedger,
    CampaignCycleAccountingRegistry,
    CampaignSixUnitError,
    CampaignSixUnitProjection,
    seal_campaign_stage_evidence,
)
from printer_v1.sources.measured_transport import MeasuredTransportLedger


def _sealed_validation_stage(*, campaign_id: str, run_id: str, cycle_id: str, stage_id: str):
    ledger = MeasuredTransportLedger(
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
    )
    ledger.record_local_validation(1)
    return seal_campaign_stage_evidence(
        stage_id=stage_id,
        stage_kind="WINDOW_15M_SLOT_1",
        stage_sequence=2,
        stage_terminal_status="COMPLETED",
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        ledger=ledger,
    )


def _registry():
    registry = CampaignCycleAccountingRegistry(
        campaign_id="campaign-1",
        run_id="run-1",
        initial_cycle_id="cycle-1",
        started_at="2026-08-19T10:00:00+00:00",
    )
    registry.register_authoritative_cycle(
        campaign_id="campaign-1",
        run_id="run-1",
        cycle_id="cycle-2",
        started_at="2026-08-19T10:01:00+00:00",
    )
    return registry


def test_multicycle_missing_stage_is_ingested_by_mutable_cycle_owner_before_projection_rebuild():
    registry = _registry()
    cycle_1 = registry.owner_for_cycle("cycle-1")
    cycle_2 = registry.owner_for_cycle("cycle-2")
    original_projection = registry.campaign_projection()
    stage = _sealed_validation_stage(
        campaign_id="campaign-1",
        run_id="run-1",
        cycle_id="cycle-1",
        stage_id="cycle-1-window15-slot1",
    )

    assert isinstance(original_projection, CampaignSixUnitProjection)
    assert not hasattr(original_projection, "ingest_stage_evidence")
    assert cycle_1.stage_evidence_count == 0
    assert cycle_2.stage_evidence_count == 0

    refreshed = prepare_full_run_accounting_owner(
        original_projection,
        sealed_stage_evidences=(stage,),
        stage_evidence_owner=cycle_1,
        accounting_projection_factory=registry.campaign_projection,
    )

    assert isinstance(refreshed, CampaignSixUnitProjection)
    assert not hasattr(refreshed, "ingest_stage_evidence")
    assert cycle_1.ingested_stage_ids == ["cycle-1-window15-slot1"]
    assert cycle_2.ingested_stage_ids == []
    assert "cycle-1-window15-slot1" not in original_projection.ingested_stage_ids
    assert "cycle-1-window15-slot1" in refreshed.ingested_stage_ids
    assert refreshed.stage_evidence_count == 1


def test_multicycle_preparation_is_idempotent_and_does_not_duplicate_stage():
    registry = _registry()
    cycle_1 = registry.owner_for_cycle("cycle-1")
    stage = _sealed_validation_stage(
        campaign_id="campaign-1",
        run_id="run-1",
        cycle_id="cycle-1",
        stage_id="cycle-1-window15-slot1",
    )

    first = prepare_full_run_accounting_owner(
        registry.campaign_projection(),
        sealed_stage_evidences=(stage,),
        stage_evidence_owner=cycle_1,
        accounting_projection_factory=registry.campaign_projection,
    )
    second = prepare_full_run_accounting_owner(
        first,
        sealed_stage_evidences=(stage,),
        stage_evidence_owner=cycle_1,
        accounting_projection_factory=registry.campaign_projection,
    )

    assert cycle_1.stage_evidence_count == 1
    assert cycle_1.ingested_stage_ids == ["cycle-1-window15-slot1"]
    assert second.stage_evidence_count == 1


def test_projection_needing_missing_stage_without_mutable_owner_fails_closed_categorically():
    registry = _registry()
    projection = registry.campaign_projection()
    stage = _sealed_validation_stage(
        campaign_id="campaign-1",
        run_id="run-1",
        cycle_id="cycle-1",
        stage_id="cycle-1-window15-slot1",
    )

    with pytest.raises(
        FullRunAccountingError,
        match="MULTI_CYCLE_STAGE_EVIDENCE_OWNER_REQUIRED",
    ):
        prepare_full_run_accounting_owner(
            projection,
            sealed_stage_evidences=(stage,),
        )


def test_projection_rebuild_requirement_fails_before_mutating_cycle_owner():
    registry = _registry()
    cycle_1 = registry.owner_for_cycle("cycle-1")
    projection = registry.campaign_projection()
    stage = _sealed_validation_stage(
        campaign_id="campaign-1",
        run_id="run-1",
        cycle_id="cycle-1",
        stage_id="cycle-1-window15-slot1",
    )
    ended_at_before = cycle_1.ended_at

    assert cycle_1.stage_evidence_count == 0
    assert cycle_1.ingested_stage_ids == []

    with pytest.raises(
        FullRunAccountingError,
        match="MULTI_CYCLE_PROJECTION_REBUILD_REQUIRED",
    ):
        prepare_full_run_accounting_owner(
            projection,
            sealed_stage_evidences=(stage,),
            stage_evidence_owner=cycle_1,
        )

    assert cycle_1.stage_evidence_count == 0
    assert cycle_1.ingested_stage_ids == []
    assert cycle_1.ended_at == ended_at_before


def test_single_cycle_preserves_mutable_owner_behavior():
    registry = CampaignCycleAccountingRegistry(
        campaign_id="campaign-1",
        run_id="run-1",
        initial_cycle_id="cycle-1",
        started_at="2026-08-19T10:00:00+00:00",
    )
    owner = registry.owner_for_cycle("cycle-1")
    stage = _sealed_validation_stage(
        campaign_id="campaign-1",
        run_id="run-1",
        cycle_id="cycle-1",
        stage_id="cycle-1-window15-slot1",
    )

    result = prepare_full_run_accounting_owner(
        owner,
        sealed_stage_evidences=(stage,),
    )

    assert result is owner
    assert owner.stage_evidence_count == 1
    assert owner.ingested_stage_ids == ["cycle-1-window15-slot1"]
    assert owner.ended_at is not None


def test_cross_cycle_stage_cannot_be_routed_into_wrong_mutable_owner():
    registry = _registry()
    cycle_1 = registry.owner_for_cycle("cycle-1")
    stage_for_cycle_2 = _sealed_validation_stage(
        campaign_id="campaign-1",
        run_id="run-1",
        cycle_id="cycle-2",
        stage_id="cycle-2-window15-slot1",
    )

    with pytest.raises(CampaignSixUnitError, match="IDENTITY_MISMATCH"):
        prepare_full_run_accounting_owner(
            registry.campaign_projection(),
            sealed_stage_evidences=(stage_for_cycle_2,),
            stage_evidence_owner=cycle_1,
            accounting_projection_factory=registry.campaign_projection,
        )

    assert cycle_1.stage_evidence_count == 0
    assert registry.owner_for_cycle("cycle-2").stage_evidence_count == 0


def _disposable_factory_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "multicycle-projection-finalization.sqlite3"
    apply_migrations(db_path)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """INSERT INTO printer_memory_factory_runs(
                run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at
            ) VALUES (?,'COMPLETED','WINDOW_15M','PROOF_ONLY','h','{}',?)""",
            ("factory-run-1", "2026-08-19T10:00:00+00:00"),
        )
        connection.execute(
            """INSERT INTO printer_scheduler_jobs(
                id,job_name,job_kind,status,scheduled_for,finished_at
            ) VALUES (1,'snap-1','SNAPSHOT','SUCCEEDED',?,?)""",
            ("2026-08-19T10:00:00+00:00", "2026-08-19T10:00:00+00:00"),
        )
        connection.execute(
            """INSERT INTO printer_memory_factory_run_steps(
                run_id,step_key,step_kind,step_status,token_id,pair_id,scheduler_job_id
            ) VALUES (?,'t1_snapshot_00','SNAPSHOT','SUCCEEDED',1,1,1)""",
            ("factory-run-1",),
        )
        connection.commit()
    finally:
        connection.close()
    return db_path


def _acceptance_ledger() -> CampaignActionLocalLedger:
    return CampaignActionLocalLedger(
        campaign_id="campaign-1",
        run_id="run-1",
        cycle_id="cycle-1",
    )


def test_full_run_acceptance_does_not_attributeerror_on_readonly_projection(tmp_path):
    """Original live fault: projection passed through finalize without a mutable owner."""
    db_path = _disposable_factory_db(tmp_path)
    registry = _registry()
    projection = registry.campaign_projection()
    assert not hasattr(projection, "ingest_stage_evidence")

    outcome = _apply_full_run_campaign_acceptance(
        db_path=db_path,
        campaign_id="campaign-1",
        campaign_run_id="run-1",
        cycle_id="cycle-1",
        configuration_id="configuration-1",
        factory_run_id="factory-run-1",
        execution_id="exec-1",
        supervision_id="supervision-1",
        launch_git_provenance={"git_head": "a" * 40},
        db_target_identity="isolated-multicycle",
        lifecycle_started=True,
        lifecycle_operation_records=(),
        forbidden_deltas={},
        accounting_owner=projection,
        action_local_ledger=_acceptance_ledger(),
    )

    reason = str(outcome.get("reason") or "")
    assert outcome["verdict"] == "BLOCKED_UNSAFE"
    assert outcome["campaign_acceptance"]["pass"] is False
    assert "AttributeError" not in reason
    assert "ingest_stage_evidence" not in reason
    assert "MULTI_CYCLE_STAGE_EVIDENCE_OWNER_REQUIRED" in reason


def test_full_run_acceptance_ingests_through_mutable_owner_not_projection(tmp_path):
    db_path = _disposable_factory_db(tmp_path)
    registry = _registry()
    cycle_1 = registry.owner_for_cycle("cycle-1")
    cycle_2 = registry.owner_for_cycle("cycle-2")
    projection = registry.campaign_projection()

    outcome = _apply_full_run_campaign_acceptance(
        db_path=db_path,
        campaign_id="campaign-1",
        campaign_run_id="run-1",
        cycle_id="cycle-1",
        configuration_id="configuration-1",
        factory_run_id="factory-run-1",
        execution_id="exec-1",
        supervision_id="supervision-1",
        launch_git_provenance={"git_head": "a" * 40},
        db_target_identity="isolated-multicycle",
        lifecycle_started=True,
        lifecycle_operation_records=(),
        forbidden_deltas={},
        accounting_owner=projection,
        accounting_stage_evidence_owner=cycle_1,
        accounting_projection_factory=registry.campaign_projection,
        action_local_ledger=_acceptance_ledger(),
    )

    reason = str(outcome.get("reason") or "")
    assert "AttributeError" not in reason
    assert "ingest_stage_evidence" not in reason
    assert cycle_2.stage_evidence_count == 0
    assert not hasattr(registry.campaign_projection(), "ingest_stage_evidence")
    assert outcome["verdict"] in {"BLOCKED_UNSAFE", "HONEST_BLOCKED", "CAMPAIGN_PASS"}

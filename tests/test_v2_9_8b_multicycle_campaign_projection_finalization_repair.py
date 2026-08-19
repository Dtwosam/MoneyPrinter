from __future__ import annotations

import pytest

from printer_v1.operator_cli.campaign_full_run_accounting import (
    FullRunAccountingError,
    prepare_full_run_accounting_owner,
)
from printer_v1.sources.campaign_six_unit_accounting import (
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

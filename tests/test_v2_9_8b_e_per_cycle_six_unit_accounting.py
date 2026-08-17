"""Slice E corrective proof: each campaign cycle owns its six-unit evidence."""

from __future__ import annotations

from types import SimpleNamespace
import sqlite3

import pytest

import printer_v1.operator_cli.authoritative_live_operational_campaign as live_campaign
import printer_v1.operator_cli.operational_memory_factory_command as operational
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignActionLocalLedger,
    CampaignCycleAccountingRegistry,
    CampaignSixUnitError,
    build_campaign_stage_id,
    reconcile_full_run_owner_to_action_local,
    seal_campaign_stage_evidence,
)
from printer_v1.sources.measured_transport import (
    LocalValidationIdentity,
    TransportOperationIdentity,
)


CAMPAIGN_ID = "campaign-e"
RUN_ID = "run-e"
CYCLE_1 = "cycle-e-1"
CYCLE_2 = "cycle-e-2"
NOW = "2026-08-17T18:00:00+00:00"


def _stage_id(cycle_id: str, sequence: int) -> str:
    return build_campaign_stage_id(
        campaign_id=CAMPAIGN_ID,
        run_id=RUN_ID,
        cycle_id=cycle_id,
        stage_kind="TEST_STAGE",
        stage_sequence=sequence,
    )


def _validation_evidence(
    cycle_id: str,
    sequence: int,
    *,
    validation_stage_id: str | None = None,
    subject_identity: str | None = None,
) -> dict:
    stage_id = _stage_id(cycle_id, sequence)
    validation = LocalValidationIdentity(
        stage_id=validation_stage_id or stage_id,
        subject_identity=subject_identity or f"{cycle_id}:subject",
        validation_kind="TEST_VALIDATION",
        validation_ordinal=1,
    )
    return seal_campaign_stage_evidence(
        stage_id=stage_id,
        stage_kind="TEST_STAGE",
        stage_sequence=sequence,
        stage_terminal_status="COMPLETED",
        campaign_id=CAMPAIGN_ID,
        run_id=RUN_ID,
        cycle_id=cycle_id,
        sealed_at=NOW,
        evidence={
            "evidence_kind": "CAMPAIGN_SIX_UNIT_EVIDENCE_V1",
            "transport_operations": [],
            "local_validations": 0,
            "scheduler_work_items": 0,
            "lifecycle_reservations": 0,
        },
        local_validation_identities=[validation],
    )


def _transport_evidence(
    cycle_id: str,
    sequence: int,
    *,
    transport_stage: str,
) -> dict:
    transport = TransportOperationIdentity(
        stage=transport_stage,
        source_name="dexscreener",
        endpoint_owner="dexscreener",
        governed_request_kind="dexscreener_fresh_profiles",
        method_or_endpoint="/token-profiles/latest/v1",
        within_request_ordinal=1,
        target_category="solana_memecoin",
        target_identity="mint-e",
        response_bytes=32,
        normalized_rows=1,
        result="OK",
    )
    return seal_campaign_stage_evidence(
        stage_id=_stage_id(cycle_id, sequence),
        stage_kind="TEST_STAGE",
        stage_sequence=sequence,
        stage_terminal_status="COMPLETED",
        campaign_id=CAMPAIGN_ID,
        run_id=RUN_ID,
        cycle_id=cycle_id,
        sealed_at=NOW,
        evidence={
            "evidence_kind": "CAMPAIGN_SIX_UNIT_EVIDENCE_V1",
            "transport_operations": [transport.as_dict()],
            "local_validations": 0,
            "scheduler_work_items": 0,
            "lifecycle_reservations": 0,
        },
    )


def _registry() -> CampaignCycleAccountingRegistry:
    return CampaignCycleAccountingRegistry(
        campaign_id=CAMPAIGN_ID,
        run_id=RUN_ID,
        initial_cycle_id=CYCLE_1,
        started_at=NOW,
    )


def test_cycle_owners_are_explicit_strict_and_disjoint() -> None:
    registry = _registry()
    cycle_1_owner = registry.owner_for_cycle(CYCLE_1)
    assert registry.registered_cycle_ids == (CYCLE_1,)

    cycle_1_evidence = _validation_evidence(CYCLE_1, 1)
    registry.stage_evidence_sink_for_cycle(CYCLE_1)(cycle_1_evidence)

    cycle_2_owner = registry.register_authoritative_cycle(
        campaign_id=CAMPAIGN_ID,
        run_id=RUN_ID,
        cycle_id=CYCLE_2,
        started_at=NOW,
    )
    registry.stage_evidence_sink_for_cycle(CYCLE_2)(
        _validation_evidence(CYCLE_2, 1)
    )

    assert cycle_1_owner is not cycle_2_owner
    assert cycle_1_owner.cycle_id == CYCLE_1
    assert cycle_2_owner.cycle_id == CYCLE_2
    assert set(cycle_1_owner.ingested_stage_ids) == {_stage_id(CYCLE_1, 1)}
    assert set(cycle_2_owner.ingested_stage_ids) == {_stage_id(CYCLE_2, 1)}
    assert set(cycle_1_owner.ingested_stage_ids).isdisjoint(
        cycle_2_owner.ingested_stage_ids
    )


def test_foreign_or_unregistered_cycle_evidence_fails_closed() -> None:
    registry = _registry()
    cycle_1_owner = registry.owner_for_cycle(CYCLE_1)
    cycle_2_evidence = _validation_evidence(CYCLE_2, 1)

    with pytest.raises(
        CampaignSixUnitError,
        match="SIX_UNIT_STAGE_EVIDENCE_IDENTITY_MISMATCH:cycle_id",
    ):
        cycle_1_owner.ingest_stage_evidence(cycle_2_evidence)
    with pytest.raises(
        CampaignSixUnitError,
        match="SIX_UNIT_STAGE_EVIDENCE_CYCLE_UNREGISTERED",
    ):
        registry.ingest_stage_evidence(cycle_2_evidence)
    with pytest.raises(
        CampaignSixUnitError,
        match="SIX_UNIT_STAGE_EVIDENCE_IDENTITY_MISMATCH:campaign_id",
    ):
        registry.register_authoritative_cycle(
            campaign_id="foreign-campaign",
            run_id=RUN_ID,
            cycle_id=CYCLE_2,
            started_at=NOW,
        )


def test_campaign_projection_is_sum_with_cycle_provenance() -> None:
    registry = _registry()
    registry.stage_evidence_sink_for_cycle(CYCLE_1)(
        _transport_evidence(CYCLE_1, 1, transport_stage="cycle-1-transport")
    )
    registry.register_authoritative_cycle(
        campaign_id=CAMPAIGN_ID,
        run_id=RUN_ID,
        cycle_id=CYCLE_2,
        started_at=NOW,
    )
    registry.stage_evidence_sink_for_cycle(CYCLE_2)(
        _validation_evidence(CYCLE_2, 1)
    )

    projection = registry.campaign_projection()
    totals = projection.six_unit_totals()
    evidence = projection.durable_evidence()

    assert totals["SOURCE_TRANSPORT_OPERATION"] == 1
    assert totals["SOURCE_RESPONSE_BYTES"] == 32
    assert totals["NORMALIZED_SOURCE_ROWS"] == 1
    assert totals["LOCAL_VALIDATION_STEP"] == 1
    assert evidence["accounting_scope"] == "CAMPAIGN_MULTI_CYCLE_PROJECTION"
    assert evidence["cycle_ids"] == [CYCLE_1, CYCLE_2]
    assert [item["cycle_id"] for item in evidence["cycle_evidences"]] == [
        CYCLE_1,
        CYCLE_2,
    ]


def test_campaign_projection_preserves_cross_cycle_transport_multiplicity() -> None:
    registry = _registry()
    registry.register_authoritative_cycle(
        campaign_id=CAMPAIGN_ID,
        run_id=RUN_ID,
        cycle_id=CYCLE_2,
        started_at=NOW,
    )
    registry.stage_evidence_sink_for_cycle(CYCLE_1)(
        _transport_evidence(
            CYCLE_1, 1, transport_stage="DEXSCREENER_DISCOVERY"
        )
    )
    registry.stage_evidence_sink_for_cycle(CYCLE_2)(
        _transport_evidence(
            CYCLE_2, 1, transport_stage="DEXSCREENER_DISCOVERY"
        )
    )

    projection = registry.campaign_projection()
    evidence = projection.durable_evidence()

    assert projection.six_unit_totals()["SOURCE_TRANSPORT_OPERATION"] == 2
    assert len(evidence["transport_operations"]) == 2
    assert [item["cycle_id"] for item in evidence["cycle_evidences"]] == [
        CYCLE_1,
        CYCLE_2,
    ]
    assert [
        len(item["transport_operations"])
        for item in evidence["cycle_evidences"]
    ] == [1, 1]


@pytest.mark.parametrize(
    ("observed_multiplicity", "expected_equal"),
    [(2, True), (1, False), (3, False)],
)
def test_campaign_projection_reconciles_exact_transport_multiplicity(
    observed_multiplicity: int,
    expected_equal: bool,
) -> None:
    registry = _registry()
    registry.register_authoritative_cycle(
        campaign_id=CAMPAIGN_ID,
        run_id=RUN_ID,
        cycle_id=CYCLE_2,
        started_at=NOW,
    )
    for cycle_id in (CYCLE_1, CYCLE_2):
        registry.stage_evidence_sink_for_cycle(cycle_id)(
            _transport_evidence(
                cycle_id, 1, transport_stage="DEXSCREENER_DISCOVERY"
            )
        )
    projection = registry.campaign_projection()
    transport = projection.durable_evidence()["transport_operations"][0]
    action_local = CampaignActionLocalLedger(
        campaign_id=CAMPAIGN_ID,
        run_id=RUN_ID,
        cycle_id=CYCLE_1,
        lifecycle_started=True,
    )
    for _ in range(observed_multiplicity):
        action_local.observe_transport(transport)

    reconciliation = reconcile_full_run_owner_to_action_local(
        projection,
        action_local,
    )

    assert reconciliation["equal"] is expected_equal, reconciliation
    assert reconciliation["unit_results"]["SOURCE_TRANSPORT_OPERATION"][
        "owner_count"
    ] == 2
    assert reconciliation["unit_results"]["SOURCE_TRANSPORT_OPERATION"][
        "action_local_count"
    ] == observed_multiplicity


def test_duplicate_transport_inside_one_cycle_still_fails_closed() -> None:
    owner = _registry().owner_for_cycle(CYCLE_1)
    owner.ingest_stage_evidence(
        _transport_evidence(
            CYCLE_1, 1, transport_stage="DEXSCREENER_DISCOVERY"
        )
    )

    with pytest.raises(
        CampaignSixUnitError,
        match="SIX_UNIT_STAGE_EVIDENCE_DUPLICATE_TRANSPORT",
    ):
        owner.ingest_stage_evidence(
            _transport_evidence(
                CYCLE_1, 2, transport_stage="DEXSCREENER_DISCOVERY"
            )
        )


def test_campaign_projection_rejects_cross_cycle_duplicate_non_transport_identity(
) -> None:
    registry = _registry()
    registry.register_authoritative_cycle(
        campaign_id=CAMPAIGN_ID,
        run_id=RUN_ID,
        cycle_id=CYCLE_2,
        started_at=NOW,
    )
    duplicate_identity_stage = "duplicate-validation-stage"
    duplicate_subject = "duplicate-subject"
    registry.stage_evidence_sink_for_cycle(CYCLE_1)(
        _validation_evidence(
            CYCLE_1,
            1,
            validation_stage_id=duplicate_identity_stage,
            subject_identity=duplicate_subject,
        )
    )
    registry.stage_evidence_sink_for_cycle(CYCLE_2)(
        _validation_evidence(
            CYCLE_2,
            1,
            validation_stage_id=duplicate_identity_stage,
            subject_identity=duplicate_subject,
        )
    )

    with pytest.raises(CampaignSixUnitError, match="SIX_UNIT_CAMPAIGN_DUPLICATE"):
        registry.campaign_projection()


def test_authoritative_cycle_binding_rebinds_real_refresh_composition_to_cycle_2(
    monkeypatch, tmp_path
) -> None:
    registry = _registry()
    cycle_1_owner = registry.owner_for_cycle(CYCLE_1)
    stage_sinks = []

    def fake_locator(_db_path, **kwargs):
        stage_sinks.append(kwargs["stage_evidence_sink"])
        kwargs["stage_evidence_sink"](_validation_evidence(CYCLE_2, 1))
        return {
            "source_requests": 1,
            "source_request_ids": (1,),
            "status": "empty",
            "pool_observations": (),
        }

    monkeypatch.setattr(
        "printer_v1.operator_cli.graduated_supply_front_door.run_fresh_profile_locator",
        fake_locator,
    )
    monkeypatch.setattr(
        live_campaign,
        "operational_discovery_batch_identity_inputs",
        lambda: ({"direct": "v1"}, "git-id"),
    )
    command = SimpleNamespace(
        db_path=tmp_path / "cycle-accounting.sqlite3",
        campaign_id=CAMPAIGN_ID,
        run_id=RUN_ID,
        supervision_id="supervision-e",
        configuration_id="configuration-e",
        policy_version="policy-e",
    )
    initial_owner = operational._build_pre_lifecycle_temporal_refresh_owner(
        command=command,
        cycle_id=CYCLE_1,
        cycle_cutoff=NOW,
        evaluated_at=NOW,
        execution_id="execution-e",
        acquisition_seconds=2400,
        lifecycle_duration_seconds=14700,
        heartbeat=None,
        cancellation_probe=lambda: None,
        stage_evidence_sink=registry.stage_evidence_sink_for_cycle(CYCLE_1),
    )
    assert initial_owner.cycle_id == CYCLE_1

    cycle_2_sink, rebound = live_campaign._bind_later_cycle_accounting_owner(
        campaign_id=CAMPAIGN_ID,
        run_id=RUN_ID,
        proposed_cycle_id=CYCLE_2,
        cycle_cutoff=NOW,
        evaluated_at=NOW,
        request_key_prefix="cycle-2-request-root",
        initial_temporal_refresh_owner=initial_owner,
        accounting_stage_evidence_sink_for_cycle=(
            lambda **identity: registry.registered_stage_evidence_sink(
                campaign_id=identity["campaign_id"],
                run_id=identity["run_id"],
                cycle_id=identity["cycle_id"],
                started_at=NOW,
            )
        ),
    )
    assert rebound.cycle_id == CYCLE_2
    assert registry.registered_cycle_ids == (CYCLE_1, CYCLE_2)

    connection = sqlite3.connect(command.db_path)
    try:
        stage = rebound._refresh_stage(
            connection,
            campaign_id=CAMPAIGN_ID,
            run_id=RUN_ID,
            cycle_id=CYCLE_2,
            discovery_work_id="work-e",
            scheduler_job_id=1,
            refresh_ordinal=2,
            source_operations_remaining=1,
            now=NOW,
        )
    finally:
        connection.close()

    cycle_2_owner = registry.owner_for_cycle(CYCLE_2)
    assert stage["source_operations"] == 1
    assert stage_sinks == [cycle_2_sink]
    assert cycle_1_owner.ingested_stage_ids == []
    assert cycle_2_owner.ingested_stage_ids == [_stage_id(CYCLE_2, 1)]

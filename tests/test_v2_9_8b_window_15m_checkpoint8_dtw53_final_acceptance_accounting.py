"""DTW-53 deterministic RED: final acceptance accounting defects."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from printer_v1.discovery.direct_migration_discovery import (
    run_direct_migration_discovery,
)
from printer_v1.discovery.eligible_token_supply import (
    run_persistent_eligible_token_supply,
)
from printer_v1.operator_cli.graduated_supply_front_door import (
    build_graduated_supply,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
)
from printer_v1.operator_cli import campaign_full_run_accounting as full_run


ROOT = Path(__file__).resolve().parents[1]
FROZEN_SUMMARY = ROOT / (
    "operator-runs/checkpoint8/"
    "C8_REPROOF_AFTER_DTW52_20260807_20260807T222049Z_0aa7fdcf/"
    "checkpoint8-controlling-proof-summary.json"
)


def _frozen_summary() -> dict:
    return json.loads(FROZEN_SUMMARY.read_text(encoding="utf-8"))


def _direct_migration_owner_validations() -> list[dict]:
    summary = _frozen_summary()
    owner = (
        summary["terminal"]["full_run_campaign_acceptance"]
        ["reconciliation"]["owner_evidence"]
    )
    return [
        dict(item)
        for item in owner["local_validation_identities"]
        if str(item.get("validation_kind")) == "PUMPSWAP_GRADUATION_VERIFIED"
    ]


def _transport(
    *,
    stage: str,
    ordinal: int,
    result: str,
    reserved_from: str | None,
) -> dict:
    return {
        "stage": stage,
        "source_name": "fixture",
        "endpoint_owner": "fixture",
        "governed_request_kind": "fixture_request",
        "method_or_endpoint": f"fixture:{ordinal}",
        "within_request_ordinal": ordinal,
        "target_category": "pair",
        "target_identity": str(ordinal),
        "response_bytes": 1,
        "normalized_rows": 1,
        "result": result,
        "reserved_from": reserved_from,
        "unit": "SOURCE_TRANSPORT_OPERATION",
    }


def _reservation_fixture(*, malformed_lifecycle_link: bool = False):
    factory_run_id = "5c37f9f2-c2e9-4590-ac2e-2bf5df5f3989"
    slot1 = "c|r|cycle|WINDOW_15M_SLOT_1|2"
    slot2 = "c|r|cycle|WINDOW_15M_SLOT_2|3"
    pre_stages = (
        ["LOCATOR"]
        + ["DIRECT_MIGRATION"] * 13
        + ["FRESH_POOL_NOMINATION"]
        + ["MINT_MARKET_BATCH"]
        + ["HOLDER_SAFETY"] * 4
    )
    transports = [
        _transport(
            stage=stage,
            ordinal=index,
            result="COMPLETED" if stage == "HOLDER_SAFETY" else "OK",
            reserved_from=None,
        )
        for index, stage in enumerate(pre_stages, start=1)
    ]
    for index in range(26):
        stage = slot1 if index % 2 == 0 else slot2
        step = f"t{1 if stage == slot1 else 2}_step_{index:02d}"
        reserved_from = (
            None
            if malformed_lifecycle_link and index == 0
            else f"{factory_run_id}:{step}:reservation:1"
        )
        transports.append(
            _transport(
                stage=stage,
                ordinal=100 + index,
                result="SUCCEEDED",
                reserved_from=reserved_from,
            )
        )
    assert len(transports) == 46
    return transports, (slot1, slot2), factory_run_id


def test_dtw53_red_a_direct_migration_validation_observer_surface() -> None:
    owner_validations = _direct_migration_owner_validations()
    assert len(owner_validations) == 4
    assert {item["validation_ordinal"] for item in owner_validations} == {1, 2, 3, 4}
    assert all(
        item["stage_id"].endswith("|DIRECT_MIGRATION|1")
        for item in owner_validations
    )

    required = "local_validation_identity_observer"
    assert required in inspect.signature(run_direct_migration_discovery).parameters
    assert required in inspect.signature(run_persistent_eligible_token_supply).parameters
    assert required in inspect.signature(build_graduated_supply).parameters
    assert required in inspect.signature(
        AuthoritativeLiveOperationalCampaignOwner.run_operational
    ).parameters


def test_dtw53_red_b_lifecycle_reservation_outcome_projection() -> None:
    transports, stage_ids, factory_run_id = _reservation_fixture()
    projector = getattr(full_run, "project_lifecycle_reservation_outcomes", None)
    assert callable(projector), "DTW53 lifecycle reservation outcome projector missing"
    outcome = projector(
        transport_records=transports,
        reserved_count=28,
        owned_lifecycle_stage_ids=stage_ids,
        factory_run_id=factory_run_id,
    )
    assert outcome["reserved"] == 28
    assert outcome["attempted"] == 26
    assert outcome["succeeded"] == 26
    assert outcome["failed"] == 0
    assert outcome["malformed_linkage_count"] == 0
    assert outcome["complete"] is True


def test_dtw53_negative_unlinked_lifecycle_transport_fails_closed() -> None:
    transports, stage_ids, factory_run_id = _reservation_fixture(
        malformed_lifecycle_link=True
    )
    projector = getattr(full_run, "project_lifecycle_reservation_outcomes", None)
    assert callable(projector), "DTW53 lifecycle reservation outcome projector missing"
    outcome = projector(
        transport_records=transports,
        reserved_count=28,
        owned_lifecycle_stage_ids=stage_ids,
        factory_run_id=factory_run_id,
    )
    assert outcome["malformed_linkage_count"] == 1
    assert outcome["complete"] is False

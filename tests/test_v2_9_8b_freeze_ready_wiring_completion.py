from __future__ import annotations

import inspect

import pytest


def _liquidity(mint: str, pool: str):
    from printer_v1.discovery.graduated_liquidity_front_door import (
        LIQUIDITY_PROVEN,
        LiquidityEvidence,
    )

    return LiquidityEvidence(
        status=LIQUIDITY_PROVEN,
        liquidity_usd=4500.0,
        mint=mint,
        pool=pool,
        reason="AT_OR_ABOVE_3000_FLOOR",
        source_status="COMPLETE",
        source_request_id=11,
        source_response_id=12,
    )


def _front_door_candidate(*, provenance: str):
    from printer_v1.discovery.graduated_liquidity_front_door import FrontDoorCandidate

    mint = "MintFreezeReady111111111111111111111111111"
    pool = "PoolFreezeReady111111111111111111111111111"
    return FrontDoorCandidate(
        mint=mint,
        pumpswap_pool=pool,
        market_identity=f"solana-mainnet:pumpswap:{pool}",
        provenance=provenance,
        lifecycle_state="PUMPSWAP_GRADUATED_CONFIRMED",
        graduation_block_time=1_750_000_000,
        liquidity=_liquidity(mint, pool),
        eligible=True,
        rejection=None,
        direct_pump_evidence={
            "mint": mint,
            "pool": pool,
            "migration_signature": "historical-signature",
            "pumpswap_program_id": "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",
            "graduation_block_time": 1_750_000_000,
            "confirmed": True,
        },
    )


def test_persisted_market_revalidation_does_not_claim_current_direct_pump_authority():
    from printer_v1.discovery.graduated_liquidity_front_door import (
        PERSISTED_GRADUATED_CHANNEL,
    )

    item = _front_door_candidate(provenance=PERSISTED_GRADUATED_CHANNEL).to_dict()
    assert item["admission_authority"] == "MARKET_PRESENT_POOL"
    assert item["nomination_source"] == "dexscreener"
    assert item["lineage_state"] == "UNKNOWN_ORIGIN"
    assert item["exact_present_pool_confirmed"] is True
    assert "direct_pump_evidence" not in item


def test_current_direct_migration_keeps_direct_authority_and_proof():
    from printer_v1.discovery.graduated_liquidity_front_door import (
        LATEST_GRADUATED_CHANNEL,
    )

    item = _front_door_candidate(provenance=LATEST_GRADUATED_CHANNEL).to_dict()
    assert item["admission_authority"] == "DIRECT_PUMP_PUMPSWAP"
    assert item["nomination_source"] == "direct_pump_migration"
    assert item["lineage_state"] == "PUMP_GRADUATION_CONFIRMED"
    assert item["direct_pump_evidence"]["migration_signature"] == "historical-signature"


def _coverage(request_id: int, key_suffix: str = "a") -> dict[str, object]:
    return {
        "source_request_id": request_id,
        "source_name": "dexscreener",
        "request_kind": "candidate_market_batch",
        "logical_stage_id": f"campaign|run|cycle|MINT_MARKET_BATCH|{request_id}",
        "terminal_status": "COMPLETED",
        "transport_identity_count": 1,
        "transport_identity_keys": [["transport", request_id, key_suffix]],
    }


def test_cumulative_coverage_merge_is_exact_deduplicated_and_conflict_closed():
    from printer_v1.discovery.eligible_token_supply import (
        EligibleTokenSupplyError,
        merge_cumulative_source_request_coverage,
    )

    one = _coverage(1)
    two = _coverage(2)
    merged = merge_cumulative_source_request_coverage([one], [one, two])
    assert [item["source_request_id"] for item in merged] == [1, 2]

    conflicting = _coverage(1, "different")
    with pytest.raises(
        EligibleTokenSupplyError,
        match="CUMULATIVE_SOURCE_REQUEST_COVERAGE_CONFLICT",
    ):
        merge_cumulative_source_request_coverage([one], [conflicting])


def test_persistent_supply_wires_cumulative_coverage_into_canonical_depth_before_refresh():
    import printer_v1.discovery.eligible_token_supply as supply

    signature = inspect.signature(supply.run_persistent_eligible_token_supply)
    assert "prior_source_request_coverage" in signature.parameters
    source = inspect.getsource(supply.run_persistent_eligible_token_supply)
    refresh_def = source.index("def _request_temporal_refresh")
    owner_call = source.index("temporal_refresh_owner.request_temporal_refresh", refresh_def)
    measurement_call = source.rindex("_refresh_freeze_ready_depth()", refresh_def, owner_call)
    assert refresh_def < measurement_call < owner_call
    assert "measure_freeze_ready_candidates" in source
    assert "assemble_and_reconcile_campaign_source_requests" in source
    assert '"campaign_source_request_coverage": _current_source_request_coverage()' in source


def test_composition_and_coordinator_forward_cumulative_coverage():
    from printer_v1.operator_cli import _graduated_supply_front_door_base as base
    from printer_v1.operator_cli import authoritative_live_operational_campaign as campaign

    assert "prior_source_request_coverage" in inspect.signature(
        base.build_graduated_supply
    ).parameters
    base_source = inspect.getsource(base.build_graduated_supply)
    assert "prior_source_request_coverage=prior_source_request_coverage" in base_source

    campaign_source = inspect.getsource(campaign)
    assert '"prior_source_request_coverage": list(' in campaign_source
    assert '"source_request_coverage": list(' in campaign_source

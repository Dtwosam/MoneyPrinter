"""Focused disposable proof for exact pre-holder transport identity parity."""

from __future__ import annotations

import pytest

from printer_v1.discovery.permanent_discovery_availability import (
    CAMPAIGN_DUPLICATE_TRANSPORT_IDENTITY_OWNERSHIP,
    SOURCE_REQUEST_DUPLICATE_TRANSPORT_IDENTITY,
    SOURCE_REQUEST_TRANSPORT_IDENTITIES_MISSING,
    SOURCE_REQUEST_TRANSPORT_IDENTITY_COUNT_MISMATCH,
    SOURCE_REQUEST_TRANSPORT_IDENTITY_MALFORMED,
    validate_campaign_transport_identity_manifest,
)
from printer_v1.operator_cli.holder_reliability_budget_control import (
    HolderBudgetError,
    MULTIPLE_PRE_HOLDER_TRANSPORT_IDENTITY_DEFECTS,
    PRE_HOLDER_MANIFEST_CAMPAIGN_IDENTITY_MISMATCH,
    PRE_HOLDER_MANIFEST_TRANSPORT_IDENTITY_COUNT_MISMATCH,
    build_pre_holder_budget_snapshot,
)
from printer_v1.sources.measured_transport import (
    TransportOperationIdentity,
    canonical_transport_identity_key,
)

CAMPAIGN = "campaign-a"
STAGE = f"{CAMPAIGN}|run-a|cycle-a|MINT_MARKET_BATCH|1"


def _identity(index: int, *, stage: str = "MINT_MARKET_BATCH", source: str = "dexscreener"):
    return {
        "stage": stage,
        "source_name": source,
        "endpoint_owner": "fixture-owner",
        "governed_request_kind": "candidate_market_batch",
        "method_or_endpoint": "GET /latest/dex/tokens",
        "within_request_ordinal": index,
        "target_category": "token_mint",
        "target_identity": f"mint-{index}",
        "response_bytes": 100 + index,
        "normalized_rows": 1,
        "result": "COMPLETE",
        "reserved_from": None,
    }


def _key(index: int):
    return list(canonical_transport_identity_key(_identity(index)))


def _coverage(rid: int, keys, *, count: int | None = None, stage: str = STAGE):
    keys = list(keys)
    return {
        "source_request_id": rid,
        "source_name": "dexscreener",
        "request_kind": "candidate_market_batch",
        "logical_stage_id": stage,
        "terminal_status": "COMPLETED",
        "transport_identity_count": len(keys) if count is None else count,
        "transport_identity_keys": keys,
        "normalized_member_count": len(keys),
    }


def test_canonical_key_uses_only_the_approved_identity_fields():
    raw = _identity(3)
    dataclass_identity = TransportOperationIdentity(**{k: raw[k] for k in (
        "stage", "source_name", "endpoint_owner", "governed_request_kind",
        "method_or_endpoint", "within_request_ordinal", "target_category",
        "target_identity", "response_bytes", "normalized_rows", "result",
        "reserved_from",
    )})
    expected = (
        "MINT_MARKET_BATCH",
        "dexscreener",
        "candidate_market_batch",
        "GET /latest/dex/tokens",
        3,
        "token_mint",
        "mint-3",
    )
    assert canonical_transport_identity_key(raw) == expected
    assert canonical_transport_identity_key(dataclass_identity) == expected
    legacy_twelve_field_key = (
        raw["stage"], raw["source_name"], raw["endpoint_owner"],
        raw["governed_request_kind"], raw["method_or_endpoint"],
        raw["within_request_ordinal"], raw["target_category"],
        raw["target_identity"], raw["response_bytes"], raw["normalized_rows"],
        raw["result"], raw["reserved_from"],
    )
    assert canonical_transport_identity_key(legacy_twelve_field_key) == expected


def test_positive_count_without_keys_blocks_manifest():
    raw = _coverage(1, [], count=1)
    raw.pop("transport_identity_keys")
    result = validate_campaign_transport_identity_manifest([raw], require_exact=True)
    assert result["status"] == "BLOCKED"
    codes = {item["code"] for item in result["transport_identity_blockers"]}
    assert SOURCE_REQUEST_TRANSPORT_IDENTITIES_MISSING in codes
    assert SOURCE_REQUEST_TRANSPORT_IDENTITY_COUNT_MISMATCH in codes


def test_count_key_length_mismatch_blocks_manifest():
    result = validate_campaign_transport_identity_manifest(
        [_coverage(1, [_key(1)], count=2)], require_exact=True
    )
    assert result["status"] == "BLOCKED"
    assert SOURCE_REQUEST_TRANSPORT_IDENTITY_COUNT_MISMATCH in {
        item["code"] for item in result["transport_identity_blockers"]
    }


def test_malformed_key_blocks_manifest():
    result = validate_campaign_transport_identity_manifest(
        [_coverage(1, [["too", "short"]])], require_exact=True
    )
    assert SOURCE_REQUEST_TRANSPORT_IDENTITY_MALFORMED in {
        item["code"] for item in result["transport_identity_blockers"]
    }


def test_duplicate_key_within_request_blocks_manifest():
    key = _key(1)
    result = validate_campaign_transport_identity_manifest(
        [_coverage(1, [key, key])], require_exact=True
    )
    assert SOURCE_REQUEST_DUPLICATE_TRANSPORT_IDENTITY in {
        item["code"] for item in result["transport_identity_blockers"]
    }


def test_duplicate_key_across_requests_reports_both_owners():
    key = _key(1)
    result = validate_campaign_transport_identity_manifest(
        [
            _coverage(1, [key], stage=f"{CAMPAIGN}|run-a|cycle-a|A|1"),
            _coverage(2, [key], stage=f"{CAMPAIGN}|run-a|cycle-a|B|1"),
        ],
        require_exact=True,
    )
    blockers = [
        item for item in result["transport_identity_blockers"]
        if item["code"] == CAMPAIGN_DUPLICATE_TRANSPORT_IDENTITY_OWNERSHIP
    ]
    assert len(blockers) == 1
    assert blockers[0]["first_owner"]["source_request_id"] == 1
    assert blockers[0]["duplicate_owner"]["source_request_id"] == 2


def test_lawful_blocked_zero_transport_request_remains_valid():
    entry = _coverage(1, [], count=0)
    entry["terminal_status"] = "BLOCKED"
    result = validate_campaign_transport_identity_manifest([entry], require_exact=True)
    assert result["status"] == "OK"
    assert result["transport_identity_count_total"] == 0
    assert result["transport_identity_keys"] == []


def test_exact_manifest_campaign_action_parity_passes():
    identities = [_identity(1), _identity(2)]
    manifest = [_coverage(1, [_key(1)]), _coverage(2, [_key(2)])]
    snapshot = build_pre_holder_budget_snapshot(
        campaign_id=CAMPAIGN,
        governed_request_ids=[1, 2],
        request_manifest=manifest,
        campaign_transport_identities=identities,
        action_local_transport_identities=identities,
    )
    assert snapshot.measured_transport_count == 2
    assert set(snapshot.measured_transport_identity_keys) == {
        tuple(_key(1)), tuple(_key(2))
    }


def test_equal_counts_with_unequal_keys_block_with_all_differences():
    manifest = [_coverage(1, [_key(1)]), _coverage(2, [_key(2)])]
    campaign = [_identity(1), _identity(3)]
    action = [_identity(1), _identity(4)]
    with pytest.raises(HolderBudgetError) as captured:
        build_pre_holder_budget_snapshot(
            campaign_id=CAMPAIGN,
            governed_request_ids=[1, 2],
            request_manifest=manifest,
            campaign_transport_identities=campaign,
            action_local_transport_identities=action,
        )
    error = captured.value
    assert error.code == MULTIPLE_PRE_HOLDER_TRANSPORT_IDENTITY_DEFECTS
    assert error.detail["M_minus_C"]["count"] == 1
    assert error.detail["C_minus_M"]["count"] == 1
    assert error.detail["M_minus_A"]["count"] == 1
    assert error.detail["A_minus_M"]["count"] == 1
    assert error.detail["C_minus_A"]["count"] == 1
    assert error.detail["A_minus_C"]["count"] == 1


def test_synthetic_nine_vs_five_reports_exact_four_identity_gap():
    manifest = [_coverage(i, [_key(i)]) for i in range(1, 10)]
    campaign = [_identity(i) for i in range(1, 6)]
    action = [_identity(i) for i in range(1, 6)]
    with pytest.raises(HolderBudgetError) as captured:
        build_pre_holder_budget_snapshot(
            campaign_id=CAMPAIGN,
            governed_request_ids=list(range(1, 10)),
            request_manifest=manifest,
            campaign_transport_identities=campaign,
            action_local_transport_identities=action,
        )
    error = captured.value
    assert error.code == MULTIPLE_PRE_HOLDER_TRANSPORT_IDENTITY_DEFECTS
    assert PRE_HOLDER_MANIFEST_CAMPAIGN_IDENTITY_MISMATCH in error.detail["categories"]
    assert error.detail["manifest_identity_count"] == 9
    assert error.detail["campaign_identity_count"] == 5
    assert error.detail["M_minus_C"]["count"] == 4
    assert error.detail["M_minus_A"]["count"] == 4
    assert error.detail["C_minus_M"]["count"] == 0


def test_declared_manifest_total_must_equal_exact_manifest_keys():
    manifest = [_coverage(1, [_key(1)], count=2)]
    with pytest.raises(HolderBudgetError) as captured:
        build_pre_holder_budget_snapshot(
            campaign_id=CAMPAIGN,
            governed_request_ids=[1],
            request_manifest=manifest,
            campaign_transport_identities=[_identity(1)],
            action_local_transport_identities=[_identity(1)],
        )
    assert captured.value.code == PRE_HOLDER_MANIFEST_TRANSPORT_IDENTITY_COUNT_MISMATCH


def test_difference_evidence_is_bounded_to_twenty_keys():
    manifest = [_coverage(i, [_key(i)]) for i in range(1, 26)]
    with pytest.raises(HolderBudgetError) as captured:
        build_pre_holder_budget_snapshot(
            campaign_id=CAMPAIGN,
            governed_request_ids=list(range(1, 26)),
            request_manifest=manifest,
            campaign_transport_identities=[],
            action_local_transport_identities=[],
        )
    bounded = captured.value.detail["M_minus_C"]
    assert bounded["count"] == 25
    assert len(bounded["keys"]) == 20
    assert bounded["truncated"] is True
    assert len(captured.value.detail["manifest_identity_owners"]) <= 20



def test_historical_key_compatibility_is_exactly_twelve_fields():
    key = tuple(_identity(1).values())
    # Use the explicit historical ordering rather than mapping insertion order.
    twelve = (
        "MINT_MARKET_BATCH",
        "dexscreener",
        "fixture-owner",
        "candidate_market_batch",
        "GET /latest/dex/tokens",
        1,
        "token_mint",
        "mint-1",
        101,
        1,
        "COMPLETE",
        None,
    )
    assert canonical_transport_identity_key(twelve) == tuple(_key(1))
    with pytest.raises(Exception):
        canonical_transport_identity_key((*twelve, "unexpected-extra-field"))


def test_manifest_owner_diagnostics_only_name_mismatched_manifest_keys():
    manifest = [_coverage(i, [_key(i)]) for i in range(1, 26)]
    campaign = [_identity(i) for i in range(1, 21)]
    action = [_identity(i) for i in range(1, 21)]
    with pytest.raises(HolderBudgetError) as captured:
        build_pre_holder_budget_snapshot(
            campaign_id=CAMPAIGN,
            governed_request_ids=list(range(1, 26)),
            request_manifest=manifest,
            campaign_transport_identities=campaign,
            action_local_transport_identities=action,
        )
    detail = captured.value.detail
    mismatch_keys = {tuple(item) for item in detail["M_minus_C"]["keys"]}
    owner_keys = {
        tuple(item["transport_identity_key"])
        for item in detail["manifest_identity_owners"]
    }
    assert detail["M_minus_C"]["count"] == 5
    assert owner_keys == mismatch_keys
    assert {item["source_request_id"] for item in detail["manifest_identity_owners"]} == {
        21, 22, 23, 24, 25
    }
    assert detail["manifest_identity_owners_truncated"] is False

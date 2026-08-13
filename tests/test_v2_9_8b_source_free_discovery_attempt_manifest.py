from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import importlib
import sqlite3
import urllib.request

import pytest


def test_exact_two_token_source_free_discovery_attempt_manifest_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_owner = importlib.import_module(
        "printer_v1.operator_cli.source_free_discovery_capacity"
    )

    from printer_v1.operator_cli import authoritative_live_operational_campaign as live
    from printer_v1.operator_cli import holder_reliability_budget_control as holder_budget
    from printer_v1.operator_cli import one_command_15m_factory as factory
    from printer_v1.scheduler import scheduler
    from printer_v1.sources import governed_execution
    from printer_v1.sources import goplus, helius_holder, pumpfun_origin
    from printer_v1.sources import secondary_discovery, solana_rpc_holder

    def forbidden_activity(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("source-free manifest performed external activity")

    monkeypatch.setattr(sqlite3, "connect", forbidden_activity)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden_activity)
    monkeypatch.setattr(
        governed_execution, "execute_source_request_with_governor", forbidden_activity
    )
    monkeypatch.setattr(scheduler, "enqueue_job", forbidden_activity)
    monkeypatch.setattr(scheduler, "claim_due_job", forbidden_activity)
    monkeypatch.setattr(scheduler, "cancel_job", forbidden_activity)

    holder_plan = factory.holder_safety_request_plan()
    assert tuple(
        (row.source_name, row.request_kind, row.condition)
        for row in holder_plan
    ) == (
        (
            goplus.GOPLUS_SOURCE_NAME,
            goplus.GOPLUS_SAFETY_REQUEST_KIND,
            "ALWAYS",
        ),
        (
            solana_rpc_holder.SOLANA_RPC_SOURCE_NAME,
            factory.HOLDER_CONCENTRATION_REQUEST_KIND,
            "GOPLUS_HOLDER_CONCENTRATION_UNKNOWN",
        ),
        (
            helius_holder.HELIUS_SOURCE_NAME,
            factory.HOLDER_CONCENTRATION_REQUEST_KIND,
            "ELIGIBLE_TRANSIENT_PRIMARY_FAILURE",
        ),
    )
    assert sum(row.governed_request_ceiling for row in holder_plan) == (
        holder_budget.HOLDER_WORST_CASE_GOVERNED_REQUESTS
    )
    assert sum(row.underlying_transport_ceiling for row in holder_plan) == (
        holder_budget.HOLDER_WORST_CASE_TRANSPORT_OPERATIONS
    )
    assert tuple(row.underlying_transport_ceiling for row in holder_plan) == (
        goplus.GOPLUS_TRANSPORT_OPERATION_COST,
        solana_rpc_holder.SOLANA_RPC_HOLDER_TRANSPORT_OPERATION_COST,
        helius_holder.HELIUS_HOLDER_TRANSPORT_OPERATION_COST,
    )

    manifest = manifest_owner.build_source_free_discovery_attempt_manifest(
        target_count=2,
        tracker_auth=None,
    )
    assert manifest.target_count == 2
    assert manifest.source_free is True
    assert manifest.candidate_evaluation_ceiling == live.HOLDER_ELIGIBILITY_CANDIDATE_MAX
    assert manifest == manifest_owner.build_source_free_discovery_attempt_manifest(
        target_count=2,
        tracker_auth=None,
    )
    with pytest.raises(FrozenInstanceError):
        manifest.target_count = 3
    with pytest.raises(TypeError):
        manifest.provider_governed_request_totals["solana_rpc"] = 0

    by_identity = {
        (row.stage, row.source_name, row.request_kind): row
        for row in manifest.requirements
    }
    assert {
        request_kind: by_identity[("PUMP_ORIGIN", pumpfun_origin.SOURCE_NAME, request_kind)].governed_request_ceiling
        for request_kind in pumpfun_origin.REQUEST_CEILINGS
    } == dict(pumpfun_origin.REQUEST_CEILINGS)

    secondary_identities = {
        (row.source_name, row.request_kind)
        for row in manifest.requirements
        if row.stage == "SECONDARY_DISCOVERY"
    }
    assert secondary_identities == {
        (
            secondary_discovery.GECKO_SOURCE_NAME,
            secondary_discovery.GECKO_TRENDING_REQUEST,
        ),
        (
            secondary_discovery.GECKO_SOURCE_NAME,
            secondary_discovery.GECKO_ACTIVE_REQUEST,
        ),
        (
            secondary_discovery.DEXSCREENER_SOURCE_NAME,
            secondary_discovery.DEXSCREENER_FRESH_REQUEST,
        ),
    }
    for source_name, request_kind in secondary_identities:
        requirement = by_identity[("SECONDARY_DISCOVERY", source_name, request_kind)]
        assert requirement.governed_request_ceiling == (
            secondary_discovery.REQUEST_CEILINGS[request_kind]
        )
    assert by_identity[
        (
            "SECONDARY_DISCOVERY",
            secondary_discovery.GECKO_SOURCE_NAME,
            secondary_discovery.GECKO_ACTIVE_REQUEST,
        )
    ].condition == "ACQUIRED_ACTIVE_POOL_AVAILABLE"
    assert not any(
        row.source_name == secondary_discovery.TRACKER_SOURCE_NAME
        for row in manifest.requirements
    )

    tracker_auth = secondary_discovery.SolanaTrackerAuthConfig(
        api_key_secret_ref="env:PRINTER_SOLANA_TRACKER_API_KEY",
        free_requests_remaining_month=(
            secondary_discovery.TRACKER_FREE_REQUESTS_PER_MONTH
        ),
    )
    tracker_manifest = manifest_owner.build_source_free_discovery_attempt_manifest(
        target_count=2,
        tracker_auth=tracker_auth,
    )
    tracker_requirements = tuple(
        row
        for row in tracker_manifest.requirements
        if row.source_name == secondary_discovery.TRACKER_SOURCE_NAME
    )
    assert tuple(row.request_kind for row in tracker_requirements) == (
        secondary_discovery.TRACKER_TRENDING_REQUEST,
    )
    assert tracker_requirements[0].governed_request_ceiling == (
        secondary_discovery.REQUEST_CEILINGS[
            secondary_discovery.TRACKER_TRENDING_REQUEST
        ]
    )
    assert tracker_requirements[0].condition == "TRACKER_FREE_CONFIGURATION_ENABLED"

    forbidden_source_markers = ("birdeye", "pumpportal", "paid", "wallet")
    assert not any(
        marker in row.source_name.lower()
        for row in tracker_manifest.requirements
        for marker in forbidden_source_markers
    )

    with pytest.raises(
        manifest_owner.SourceFreeDiscoveryCapacityError,
        match="EXACT_TWO_TOKEN_TARGET_REQUIRED",
    ):
        manifest_owner.build_source_free_discovery_attempt_manifest(
            target_count=4,
            tracker_auth=None,
        )
    with pytest.raises(secondary_discovery.SecondaryDiscoveryError):
        manifest_owner.build_source_free_discovery_attempt_manifest(
            target_count=2,
            tracker_auth=replace(tracker_auth, free_requests_remaining_month=0),
        )

    first = manifest.requirements[0]
    unknown_kind = replace(first, request_kind="unknown_request_kind")
    with pytest.raises(
        manifest_owner.SourceFreeDiscoveryCapacityError,
        match="REQUEST_KIND_NOT_REGISTERED",
    ):
        manifest_owner.validate_source_free_discovery_attempt_manifest(
            replace(manifest, requirements=(unknown_kind, *manifest.requirements[1:]))
        )
    prohibited = replace(
        first,
        source_name="pumpportal",
        request_kind="pumpfun_launch_stream",
    )
    with pytest.raises(
        manifest_owner.SourceFreeDiscoveryCapacityError,
        match="PROHIBITED_SOURCE_REQUIREMENT",
    ):
        manifest_owner.validate_source_free_discovery_attempt_manifest(
            replace(manifest, requirements=(prohibited, *manifest.requirements[1:]))
        )

    holder_requirements = tuple(
        row for row in manifest.requirements if row.stage == "HOLDER_SAFETY"
    )
    assert tuple(
        (
            row.source_name,
            row.request_kind,
            row.condition,
            row.governed_request_ceiling,
            row.underlying_transport_ceiling,
        )
        for row in holder_requirements
    ) == tuple(
        (
            row.source_name,
            row.request_kind,
            row.condition,
            row.governed_request_ceiling,
            row.underlying_transport_ceiling,
        )
        for row in holder_plan
    )

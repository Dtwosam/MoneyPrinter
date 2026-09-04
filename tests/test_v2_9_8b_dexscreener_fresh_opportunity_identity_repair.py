from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import printer_v1.sources.dexscreener as dexscreener
from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    assemble_and_reconcile_campaign_source_requests,
    build_campaign_source_request_scope,
)
from printer_v1.operator_cli.graduated_supply_front_door import (
    run_fresh_profile_locator,
)
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignCycleAccountingRegistry,
)
from printer_v1.sources.measured_transport import (
    MeasuredTransportError,
    MeasuredTransportLedger,
    TransportOperationIdentity,
)


CAMPAIGN = "campaign-fresh-opportunity"
RUN = "run-fresh-opportunity"
CYCLE = "cycle-fresh-opportunity"
EXECUTION = "execution-fresh-opportunity"
ROOT = f"v2-9-8b-window15m-{EXECUTION}"
MINT = "FreshOpportunityMint111111111111111111111111111"


def _transport_identity(operation: dict) -> TransportOperationIdentity:
    return TransportOperationIdentity(
        stage=operation["stage"],
        source_name=operation["source_name"],
        endpoint_owner=operation["endpoint_owner"],
        governed_request_kind=operation["governed_request_kind"],
        method_or_endpoint=operation["method_or_endpoint"],
        within_request_ordinal=operation["within_request_ordinal"],
        target_category=operation["target_category"],
        target_identity=operation["target_identity"],
        response_bytes=operation["response_bytes"],
        normalized_rows=operation["normalized_rows"],
        result=operation["result"],
        reserved_from=operation["reserved_from"],
    )


def _successful_fresh_profiles_transport(monkeypatch):
    def fake_get(endpoint, _timeout_seconds, *, byte_ceiling):
        del byte_ceiling
        if endpoint == dexscreener.DEXSCREENER_TOKEN_PROFILES_URL:
            return ([{"chainId": "solana", "tokenAddress": MINT}], 101)
        return (
            [
                {
                    "chainId": "solana",
                    "baseToken": {"address": MINT},
                    "pairAddress": "FreshOpportunityPool111111111111111111111111",
                }
            ],
            202,
        )

    monkeypatch.setattr(dexscreener, "_dexscreener_http_get_json", fake_get)
    return dexscreener.build_dexscreener_fresh_profiles_transport()


def test_fresh_profile_locator_uses_canonical_stage_opportunity_identity(
    tmp_path: Path, monkeypatch
) -> None:
    """Regression for refresh evidence colliding with the initial locator."""
    db = tmp_path / "fresh-opportunity.sqlite3"
    apply_migrations(db)
    registry = CampaignCycleAccountingRegistry(
        campaign_id=CAMPAIGN,
        run_id=RUN,
        initial_cycle_id=CYCLE,
    )
    sink = registry.stage_evidence_sink_for_cycle(CYCLE)

    initial = run_fresh_profile_locator(
        db,
        transport=_successful_fresh_profiles_transport(monkeypatch),
        request_key=f"{ROOT}-locator",
        now="2026-09-04T11:00:00+00:00",
        stage_evidence_sink=sink,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
        stage_sequence=1,
    )
    refresh = run_fresh_profile_locator(
        db,
        transport=_successful_fresh_profiles_transport(monkeypatch),
        request_key=f"{ROOT}-refresh-1-dex-fresh",
        now="2026-09-04T11:10:00+00:00",
        stage_evidence_sink=sink,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
        stage_sequence=2,
    )

    initial_target = f"{CAMPAIGN}|{RUN}|{CYCLE}|LOCATOR|1"
    refresh_target = f"{CAMPAIGN}|{RUN}|{CYCLE}|LOCATOR|2"
    initial_keys = initial["source_request_coverage"][0]["transport_identity_keys"]
    refresh_keys = refresh["source_request_coverage"][0]["transport_identity_keys"]
    assert {key[-1] for key in initial_keys} == {initial_target}
    assert {key[-1] for key in refresh_keys} == {refresh_target}
    assert initial_target != refresh_target
    assert all(ROOT not in str(key[-1]) for key in (*initial_keys, *refresh_keys))

    scope = build_campaign_source_request_scope(
        execution_id=EXECUTION,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
    )
    connection = sqlite3.connect(db)
    try:
        reconciliation = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "campaign_source_request_scope": scope.as_dict(),
                "request_key_root": ROOT,
                "source_request_ids": [initial["request_id"], refresh["request_id"]],
                "campaign_source_request_coverage": [
                    *initial["source_request_coverage"],
                    *refresh["source_request_coverage"],
                ],
            },
            request_key_root=ROOT,
            campaign_source_request_scope=scope,
        )
    finally:
        connection.close()
    assert reconciliation["status"] == "OK"
    assert reconciliation["stage_reported_request_ids"] == [
        initial["request_id"],
        refresh["request_id"],
    ]
    assert reconciliation["manifest_request_ids"] == [
        initial["request_id"],
        refresh["request_id"],
    ]

    repeat_evidence = []
    repeat = run_fresh_profile_locator(
        db,
        transport=_successful_fresh_profiles_transport(monkeypatch),
        request_key=f"{ROOT}-refresh-1-dex-fresh-repeat",
        now="2026-09-04T11:10:30+00:00",
        stage_evidence_sink=repeat_evidence.append,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
        stage_sequence=2,
    )
    assert repeat["request_id"] != refresh["request_id"]
    duplicate_guard = MeasuredTransportLedger(
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
    )
    for operation in refresh["sealed_stage_evidence"]["transport_operations"]:
        duplicate_guard.record_transport(_transport_identity(operation))
    with pytest.raises(MeasuredTransportError, match="DUPLICATE_TRANSPORT_IDENTITY"):
        duplicate_guard.record_transport(
            _transport_identity(repeat_evidence[0]["transport_operations"][0])
        )


def test_fresh_profile_failure_keeps_canonical_stage_opportunity_identity(
    tmp_path: Path, monkeypatch
) -> None:
    """Failure evidence must carry the same semantic opportunity identity."""
    db = tmp_path / "fresh-opportunity-failure.sqlite3"
    apply_migrations(db)
    sealed = []

    def failing_get(_endpoint, _timeout_seconds, *, byte_ceiling):
        del byte_ceiling
        raise TimeoutError("controlled profile timeout")

    monkeypatch.setattr(dexscreener, "_dexscreener_http_get_json", failing_get)
    report = run_fresh_profile_locator(
        db,
        transport=dexscreener.build_dexscreener_fresh_profiles_transport(),
        request_key=f"{ROOT}-refresh-1-dex-fresh-failure",
        now="2026-09-04T11:10:00+00:00",
        stage_evidence_sink=sealed.append,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
        stage_sequence=2,
    )

    assert report["status"] == "dexscreener_profiles_transport_failure"
    assert sealed[0]["transport_operations"][0]["target_identity"] == (
        f"{CAMPAIGN}|{RUN}|{CYCLE}|LOCATOR|2"
    )

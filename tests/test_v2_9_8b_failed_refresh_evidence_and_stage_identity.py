"""Regressions for failed refresh evidence and cycle-owned stage identity.

Offline and disposable-state only.  The tests exercise production source-request,
unknown-liquidity backup, accounting-owner, refresh-composition, and persistent
refresh-owner boundaries without contacting providers or running Printer.
"""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

import printer_v1.sources.dexscreener as dexscreener
import printer_v1.sources.geckoterminal as geckoterminal
from printer_v1.db import apply_migrations
from printer_v1.discovery import pre_lifecycle_refresh_composition as composition
from printer_v1.discovery.eligible_token_supply import (
    temporal_refresh_source_request_evidence,
)
from printer_v1.discovery.permanent_discovery_availability import (
    StageBudget,
    assemble_and_reconcile_campaign_source_requests,
    build_campaign_source_request_scope,
    record_fresh_pool_nominations,
    run_bounded_unknown_liquidity_backup,
)
from printer_v1.discovery.pre_lifecycle_refresh_composition import (
    PreLifecycleRefreshCompositionError,
    build_pre_lifecycle_refresh_stage,
)
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    AcquisitionLedger,
    INTERNAL_INVARIANT,
)
from printer_v1.operator_cli.pre_lifecycle_persistent_refresh_owner import (
    PreLifecycleTemporalRefreshOwner,
)
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignCycleAccountingRegistry,
    CampaignSixUnitError,
)


CAMPAIGN = "campaign-failed-refresh-repair"
RUN = "run-failed-refresh-repair"
CYCLE = "cycle-failed-refresh-repair"
EXECUTION = "failed-refresh-repair"
ROOT = f"v2-9-8b-window15m-{EXECUTION}"
NOW = "2026-09-05T20:00:00+00:00"
WSOL = "So11111111111111111111111111111111111111112"
MINTS = (
    "4tNCRgigHBPiMsPfrCaU1kE6gGofxgXLmEq8mRK1pump",
    "4FN5PSaprS73Z2SRGx2HG9eaES1yVURMU5yAPpDQpump",
    "5tNCRgigHBPiMsPfrCaU1kE6gGofxgXLmEq8mRK2pump",
)
POOLS = (
    "BDhvEqa1KjHBsNSFxN9Np4t3CLZjaCvDtCRjrqsbQ21p",
    "9yuowVdGRZ35yM339cjyTWfhAdJJVPJqPKGHhyCXG3fo",
    "CDhvEqa1KjHBsNSFxN9Np4t3CLZjaCvDtCRjrqsbQ22q",
)


def _transport_identity(mint: str) -> dict[str, object]:
    return {
        "stage": "UNKNOWN_LIQUIDITY_BACKUP",
        "source_name": "geckoterminal",
        "endpoint_owner": "candidate_market_batch",
        "governed_request_kind": "candidate_market_batch",
        "method_or_endpoint": "GET /api/v2/networks/solana/tokens/{mint}/pools",
        "within_request_ordinal": 1,
        "target_category": "mint_pool_reconciliation",
        "target_identity": mint,
        "response_bytes": 100,
        "normalized_rows": 0,
        "result": "OK",
    }


def _backup_transport_factory(mint: str):
    def transport(_context):
        return {
            "data": [],
            "pairs": [],
            "response_bytes": 100,
            "transport_operations_used": 1,
            "transport_operation_identities": [_transport_identity(mint)],
        }

    return transport


def _seed_unknown_candidates(connection: sqlite3.Connection) -> None:
    record_fresh_pool_nominations(
        connection,
        observations=[
            {
                "mint": mint,
                "pool": pool,
                "base_mint": mint,
                "quote_mint": WSOL,
                "venue": "pumpswap",
                "liquidity_usd": None,
            }
            for mint, pool in zip(MINTS, POOLS, strict=True)
        ],
        source="dexscreener",
        request_id=900,
        now=NOW,
        campaign_id=CAMPAIGN,
    )


def test_refresh_unknown_liquidity_sequence_continues_after_real_initial_attempts(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "stage-sequence.sqlite3"
    apply_migrations(db_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    registry = CampaignCycleAccountingRegistry(
        campaign_id=CAMPAIGN,
        run_id=RUN,
        initial_cycle_id=CYCLE,
    )
    sink = registry.stage_evidence_sink_for_cycle(CYCLE)
    try:
        _seed_unknown_candidates(connection)
        initial = run_bounded_unknown_liquidity_backup(
            connection,
            stage_budget=StageBudget.permanent_discovery_default(),
            now=NOW,
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
            request_key_prefix=f"{ROOT}-initial-backup",
            geckoterminal_transport_factory=_backup_transport_factory,
            stage_evidence_sink=sink,
            max_backups=2,
        )
        assert [
            int(block["stage_sequence"])
            for block in initial["sealed_stage_evidence_blocks"]
        ] == [1, 2]

        def fake_dex(*_args, **_kwargs):
            return {
                "status": "empty",
                "source_requests": 1,
                "request_id": 901,
                "response_id": 902,
                "pool_observations": [],
            }

        def fake_gecko(*_args, **_kwargs):
            return {
                "status": "COMPLETE",
                "failure_type": None,
                "source_requests": 1,
                "nominations": [],
            }

        monkeypatch.setattr(
            "printer_v1.operator_cli.graduated_supply_front_door.run_fresh_profile_locator",
            fake_dex,
        )
        monkeypatch.setattr(
            composition, "run_geckoterminal_fresh_nomination", fake_gecko
        )
        refresh_stage = build_pre_lifecycle_refresh_stage(
            db_path=db_path,
            request_key_prefix=ROOT,
            locator_transport=lambda _context: {},
            geckoterminal_nomination_transport=lambda _context: {},
            geckoterminal_backup_transport_factory=_backup_transport_factory,
            stage_evidence_sink=sink,
        )
        refresh = refresh_stage(
            connection,
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
            discovery_work_id="refresh-work-1",
            scheduler_job_id=1,
            refresh_ordinal=1,
            source_operations_remaining=3,
            now="2026-09-05T20:10:00+00:00",
        )
    finally:
        connection.close()

    backup = refresh["stage_reports"][
        composition.UNKNOWN_LIQUIDITY_BACKUP_CHANNEL
    ]
    assert int(backup["sealed_stage_evidence_blocks"][0]["stage_sequence"]) == 3
    assert registry.owner_for_cycle(CYCLE).ingested_stage_ids[-1].endswith(
        "|UNKNOWN_LIQUIDITY_BACKUP|3"
    )
    other_cycle = "cycle-failed-refresh-repair-2"
    registry.register_authoritative_cycle(
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=other_cycle,
    )
    assert (
        registry.stage_evidence_sink_for_cycle(other_cycle).next_stage_sequence(
            "UNKNOWN_LIQUIDITY_BACKUP"
        )
        == 1
    )

    with pytest.raises(
        CampaignSixUnitError, match="SIX_UNIT_STAGE_EVIDENCE_DUPLICATE_STAGE_ID"
    ):
        sink(initial["sealed_stage_evidence_blocks"][1])


def _dex_transport(monkeypatch):
    mint = MINTS[0]
    pool = POOLS[0]

    def fake_get(endpoint, _timeout_seconds, *, byte_ceiling):
        del byte_ceiling
        if endpoint == dexscreener.DEXSCREENER_TOKEN_PROFILES_URL:
            return ([{"chainId": "solana", "tokenAddress": mint}], 101)
        return (
            [{
                "chainId": "solana",
                "baseToken": {"address": mint},
                "pairAddress": pool,
            }],
            202,
        )

    monkeypatch.setattr(dexscreener, "_dexscreener_http_get_json", fake_get)
    return dexscreener.build_dexscreener_fresh_profiles_transport()


def _gecko_transport(monkeypatch):
    mint = MINTS[1]
    pool = POOLS[1]
    monkeypatch.setattr(
        geckoterminal,
        "_load_public_json",
        lambda _endpoint, *, timeout_seconds: {
            "data": [{
                "id": f"solana_{pool}",
                "type": "pool",
                "attributes": {
                    "address": pool,
                    "base_token_address": mint,
                    "quote_token_address": WSOL,
                    "dex_id": "pumpswap",
                    "reserve_in_usd": "12000",
                },
                "relationships": {"network": {"data": {"id": "solana"}}},
            }],
            "_source_response_bytes": 303,
        },
    )
    return geckoterminal.build_geckoterminal_pools_transport()


def test_failed_refresh_preserves_completed_request_evidence_for_reconciliation(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "failed-refresh.sqlite3"
    apply_migrations(db_path)
    registry = CampaignCycleAccountingRegistry(
        campaign_id=CAMPAIGN,
        run_id=RUN,
        initial_cycle_id=CYCLE,
    )

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        _seed_unknown_candidates(connection)
    finally:
        connection.close()

    def fail_after_three_completed_requests(*_args, **_kwargs):
        raise CampaignSixUnitError("FORCED_LATER_REFRESH_SUBSTAGE_FAILURE")

    monkeypatch.setattr(
        composition,
        "process_protocol_confirmation_queue",
        fail_after_three_completed_requests,
    )
    composed = build_pre_lifecycle_refresh_stage(
        db_path=db_path,
        request_key_prefix=ROOT,
        locator_transport=_dex_transport(monkeypatch),
        geckoterminal_nomination_transport=_gecko_transport(monkeypatch),
        geckoterminal_backup_transport_factory=_backup_transport_factory,
        stage_evidence_sink=registry.stage_evidence_sink_for_cycle(CYCLE),
    )
    captured: list[PreLifecycleRefreshCompositionError] = []

    def capture_composition_failure(*args, **kwargs):
        try:
            return composed(*args, **kwargs)
        except PreLifecycleRefreshCompositionError as exc:
            captured.append(exc)
            raise

    owner = PreLifecycleTemporalRefreshOwner(
        db_path,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
        supervision_id="supervision-failed-refresh-repair",
        source_governor=SimpleNamespace(available=True),
        central_scheduler=SimpleNamespace(available=True),
        acquisition_started_at="2026-09-05T19:59:59+00:00",
        acquisition_deadline_at="2026-09-05T20:20:00+00:00",
        work_deadline_at="2026-09-05T21:00:00+00:00",
        refresh_stage=capture_composition_failure,
        waiter=lambda _seconds: False,
        refresh_interval_seconds=1,
    )
    outcome = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=4,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=4,
        now=NOW,
    )

    assert outcome.status == INTERNAL_INVARIANT
    assert outcome.source_operations == 3, (
        str(captured[0]) if captured else outcome.detail
    )
    assert len(outcome.source_request_ids) == 3
    assert len(set(outcome.source_request_ids)) == 3
    assert outcome.provider_failures == 0
    assert outcome.channels_attempted == (
        composition.DEXSCREENER_FRESH_CHANNEL,
        composition.GECKOTERMINAL_NOMINATION_CHANNEL,
        composition.UNKNOWN_LIQUIDITY_BACKUP_CHANNEL,
        composition.PROTOCOL_CONFIRMATION_CHANNEL,
    )
    assert [
        int(entry["source_request_id"])
        for entry in outcome.source_request_coverage
    ] == list(outcome.source_request_ids)
    assert captured and isinstance(captured[0].__cause__, CampaignSixUnitError)
    assert str(captured[0].__cause__) == "FORCED_LATER_REFRESH_SUBSTAGE_FAILURE"
    with pytest.raises(TypeError):
        captured[0].partial_stage["source_operations"] = 99

    ledger = AcquisitionLedger(
        started_at="2026-09-05T19:59:59+00:00",
        acquisition_deadline_at="2026-09-05T20:20:00+00:00",
        acquisition_duration_seconds=1201,
        refresh_interval_seconds=1,
    )
    ledger.record(outcome)
    request_ids, coverage = temporal_refresh_source_request_evidence(ledger)
    scope = build_campaign_source_request_scope(
        execution_id=EXECUTION,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
    )
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        assert connection.execute(
            "SELECT wait_state FROM printer_pre_lifecycle_discovery_refresh_waits"
        ).fetchone()[0] == "FAILED"
        assert connection.execute(
            "SELECT work_state FROM printer_pre_lifecycle_discovery_refresh_work"
        ).fetchone()[0] == "FAILED"
        reconciliation = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "campaign_source_request_scope": scope.as_dict(),
                "request_key_root": ROOT,
                "final_refresh_source_request_ids": request_ids,
                "final_refresh_source_request_coverage": coverage,
            },
            request_key_root=ROOT,
            campaign_source_request_scope=scope,
        )
    finally:
        connection.close()

    assert reconciliation["status"] == "OK", reconciliation.get("terminal_detail")
    assert reconciliation["durable_request_ids"] == request_ids
    assert reconciliation["stage_reported_request_ids"] == request_ids
    assert reconciliation["manifest_request_ids"] == request_ids

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        genuine_mismatch = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "campaign_source_request_scope": scope.as_dict(),
                "request_key_root": ROOT,
                "final_refresh_source_request_ids": request_ids,
                "final_refresh_source_request_coverage": coverage[:-1],
            },
            request_key_root=ROOT,
            campaign_source_request_scope=scope,
        )
    finally:
        connection.close()
    assert genuine_mismatch["status"] == "BLOCKED"


def test_untyped_exception_cannot_inject_partial_refresh_evidence(tmp_path) -> None:
    db_path = tmp_path / "untyped-partial-evidence.sqlite3"
    apply_migrations(db_path)

    class UntypedFailure(RuntimeError):
        partial_stage = {
            "source_operations": 1,
            "provider_failures": 0,
            "stage_reports": {
                "forged": {
                    "source_request_ids": [4242],
                    "source_request_coverage": [{
                        "source_request_id": 4242,
                        "terminal_status": "COMPLETED",
                    }],
                }
            },
        }

    def fail_with_untyped_evidence(*_args, **_kwargs):
        raise UntypedFailure("untyped downstream failure")

    owner = PreLifecycleTemporalRefreshOwner(
        db_path,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
        supervision_id="supervision-untyped-evidence",
        source_governor=SimpleNamespace(available=True),
        central_scheduler=SimpleNamespace(available=True),
        acquisition_started_at="2026-09-05T19:59:59+00:00",
        acquisition_deadline_at="2026-09-05T20:20:00+00:00",
        work_deadline_at="2026-09-05T21:00:00+00:00",
        refresh_stage=fail_with_untyped_evidence,
        waiter=lambda _seconds: False,
        refresh_interval_seconds=1,
    )
    outcome = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=4,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=4,
        now=NOW,
    )

    assert outcome.source_operations == 0
    assert outcome.source_request_ids == ()
    assert outcome.source_request_coverage == ()


def test_partial_evidence_does_not_hide_conflicting_owner_for_same_request() -> None:
    first = {
        "source_request_id": 7,
        "source_name": "dexscreener",
        "request_kind": "fresh_profiles",
        "logical_stage_id": "campaign|run|cycle|LOCATOR|1",
        "terminal_status": "COMPLETED",
        "transport_identity_count": 1,
        "normalized_member_count": 1,
        "transport_identity_keys": [["transport-a"]],
    }
    conflicting = {
        **first,
        "logical_stage_id": "campaign|run|cycle|OTHER_STAGE|1",
    }
    partial = composition._partial_refresh_stage(
        {
            "source_operations": 1,
            "stage_reports": {
                "first": {
                    "source_request_ids": [7],
                    "source_request_coverage": [first],
                }
            },
        },
        SimpleNamespace(blocks=[{
            "stage_id": "campaign|run|cycle|OTHER_STAGE|1",
            "source_request_ids": [7],
            "source_request_coverage": [conflicting],
        }]),
    )

    assert len(partial["stage_reports"]) == 2
    assert {
        entry["logical_stage_id"]
        for entry in partial["source_request_coverage"]
    } == {first["logical_stage_id"], conflicting["logical_stage_id"]}

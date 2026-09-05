from __future__ import annotations

import sqlite3

import printer_v1.sources.dexscreener as dexscreener
import printer_v1.sources.geckoterminal as geckoterminal
from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    assemble_and_reconcile_campaign_source_requests,
    build_campaign_source_request_scope,
    run_geckoterminal_fresh_nomination,
)
from printer_v1.discovery.pre_lifecycle_refresh_composition import (
    build_pre_lifecycle_refresh_stage,
)
from printer_v1.operator_cli.graduated_supply_front_door import (
    run_fresh_profile_locator,
)
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignCycleAccountingRegistry,
)


CAMPAIGN = "campaign-initial-refresh-ownership"
RUN = "run-initial-refresh-ownership"
CYCLE = "cycle-initial-refresh-ownership"
EXECUTION = "execution-initial-refresh-ownership"
ROOT = f"v2-9-8b-window15m-{EXECUTION}"
MINT = "InitialRefreshMint1111111111111111111111111111"
POOL = "InitialRefreshPool1111111111111111111111111111"


def _dex_transport(monkeypatch):
    def fake_get(endpoint, _timeout_seconds, *, byte_ceiling):
        del byte_ceiling
        if endpoint == dexscreener.DEXSCREENER_TOKEN_PROFILES_URL:
            return ([{"chainId": "solana", "tokenAddress": MINT}], 101)
        return (
            [{
                "chainId": "solana",
                "baseToken": {"address": MINT},
                "pairAddress": POOL,
            }],
            202,
        )

    monkeypatch.setattr(dexscreener, "_dexscreener_http_get_json", fake_get)
    return dexscreener.build_dexscreener_fresh_profiles_transport()


def _gecko_transport(monkeypatch):
    payload = {
        "data": [{
            "id": f"solana_{POOL}",
            "type": "pool",
            "attributes": {
                "address": POOL,
                "base_token_address": MINT,
                "quote_token_address": "So11111111111111111111111111111111111111112",
                "dex_id": "pumpswap",
                "reserve_in_usd": "12000",
            },
            "relationships": {"network": {"data": {"id": "solana"}}},
        }],
        "_source_response_bytes": 303,
    }
    monkeypatch.setattr(
        geckoterminal,
        "_load_public_json",
        lambda _endpoint, *, timeout_seconds: payload,
    )
    return geckoterminal.build_geckoterminal_pools_transport()


def test_initial_refresh_requests_survive_accounting_and_final_reconciliation(
    tmp_path, monkeypatch
) -> None:
    """Regression for consumed campaign requests 4928/4929 disappearing together."""
    db = tmp_path / "initial-refresh-request-ownership.sqlite3"
    apply_migrations(db)
    registry = CampaignCycleAccountingRegistry(
        campaign_id=CAMPAIGN,
        run_id=RUN,
        initial_cycle_id=CYCLE,
    )
    sink = registry.stage_evidence_sink_for_cycle(CYCLE)
    dex_transport = _dex_transport(monkeypatch)
    gecko_transport = _gecko_transport(monkeypatch)

    initial_dex = run_fresh_profile_locator(
        db,
        transport=dex_transport,
        request_key=f"{ROOT}-locator",
        now="2026-09-05T13:11:00+00:00",
        stage_evidence_sink=sink,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
        stage_sequence=1,
    )
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        initial_gecko = run_geckoterminal_fresh_nomination(
            connection,
            request_key=f"{ROOT}-gt-new-pools",
            now="2026-09-05T13:11:01+00:00",
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
            transport=gecko_transport,
            stage_evidence_sink=sink,
            stage_sequence=1,
        )
        refresh_stage = build_pre_lifecycle_refresh_stage(
            db_path=db,
            request_key_prefix=ROOT,
            locator_transport=dex_transport,
            geckoterminal_nomination_transport=gecko_transport,
            stage_evidence_sink=sink,
        )
        try:
            refresh = dict(refresh_stage(
                connection,
                campaign_id=CAMPAIGN,
                run_id=RUN,
                cycle_id=CYCLE,
                discovery_work_id="refresh-work",
                scheduler_job_id=1,
                refresh_ordinal=1,
                source_operations_remaining=2,
                now="2026-09-05T13:21:00+00:00",
            ))
        except Exception:
            refresh = {"stage_reports": {}}

        reports = refresh["stage_reports"]
        refresh_ids = [
            int(report["request_id"])
            for report in reports.values()
            if isinstance(report, dict) and report.get("request_id") is not None
        ]
        refresh_coverage = [
            dict(entry)
            for report in reports.values()
            if isinstance(report, dict)
            for entry in report.get("source_request_coverage", ())
        ]
        scope = build_campaign_source_request_scope(
            execution_id=EXECUTION,
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
        )
        reconciliation = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "campaign_source_request_scope": scope.as_dict(),
                "request_key_root": ROOT,
                "dexscreener_locator": initial_dex,
                "geckoterminal_nomination": initial_gecko,
                "final_refresh_source_request_ids": refresh_ids,
                "final_refresh_source_request_coverage": refresh_coverage,
            },
            request_key_root=ROOT,
            campaign_source_request_scope=scope,
        )
        durable_refresh = connection.execute(
            "SELECT id,request_kind FROM printer_source_requests "
            "WHERE request_key LIKE ? ORDER BY id",
            (f"{ROOT}-refresh-1-%",),
        ).fetchall()
    finally:
        connection.close()

    assert [row["request_kind"] for row in durable_refresh] == [
        "dexscreener_fresh_profiles",
        "geckoterminal_new_pool_discovery",
    ]
    assert reconciliation["status"] == "OK", reconciliation.get("terminal_detail")
    assert reconciliation["durable_request_ids"] == reconciliation["stage_reported_request_ids"]
    assert reconciliation["durable_request_ids"] == reconciliation["manifest_request_ids"]
    assert len(refresh_ids) == len(set(refresh_ids)) == 2
    initial_gecko_target = initial_gecko["source_request_coverage"][0][
        "transport_identity_keys"
    ][0][-1]
    refresh_gecko = reports["geckoterminal_fresh_pool_nomination"]
    refresh_gecko_target = refresh_gecko["source_request_coverage"][0][
        "transport_identity_keys"
    ][0][-1]
    assert initial_gecko_target == f"{CAMPAIGN}|{RUN}|{CYCLE}|FRESH_POOL_NOMINATION|1"
    assert refresh_gecko_target == f"{CAMPAIGN}|{RUN}|{CYCLE}|FRESH_POOL_NOMINATION|2"

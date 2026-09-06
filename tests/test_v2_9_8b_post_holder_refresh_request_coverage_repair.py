"""Post-holder refresh evidence must remain in campaign reconciliation."""

from __future__ import annotations

import sqlite3

from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    assemble_and_reconcile_campaign_source_requests,
    build_campaign_source_request_scope,
)
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    REFRESH_COMPLETED,
    TemporalRefreshOutcome,
)
from printer_v1.operator_cli import authoritative_live_operational_campaign as campaign


EXECUTION = "exact-post-holder-refresh-execution"
ROOT = f"v2-9-8b-window15m-{EXECUTION}"
CAMPAIGN = "exact-post-holder-refresh-campaign"
RUN = "exact-post-holder-refresh-run"
CYCLE = "exact-post-holder-refresh-cycle"


def _coverage(request_id: int) -> dict[str, object]:
    return {
        "source_request_id": request_id,
        "source_name": "dexscreener",
        "request_kind": "dexscreener_fresh_profiles",
        "logical_stage_id": f"{CAMPAIGN}|{RUN}|{CYCLE}|POST_HOLDER_REFRESH|1",
        "terminal_status": "COMPLETED",
        "transport_identity_count": 1,
        "normalized_member_count": 1,
        "transport_identity_keys": [
            [
                "DEXSCREENER_DISCOVERY",
                "dexscreener_profiles",
                "dexscreener_fresh_profiles",
                "GET /token-profiles/latest/v1",
                1,
                "fresh_profiles",
                f"{CAMPAIGN}|{RUN}|{CYCLE}|POST_HOLDER_REFRESH|{request_id}",
            ]
        ],
    }


def test_post_holder_completed_refresh_evidence_reconciles_exactly(tmp_path) -> None:
    db_path = tmp_path / "proof.sqlite3"
    apply_migrations(db_path)
    connection = sqlite3.connect(db_path)
    request_ids = (901, 902, 903, 904)
    for request_id in request_ids:
        connection.execute(
            """INSERT INTO printer_source_requests
               (id,source_name,request_kind,requested_at,request_key,
                tracking_priority,source_status,data_quality_label,created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                request_id,
                "dexscreener",
                "dexscreener_fresh_profiles",
                "2026-09-06T10:24:56+00:00",
                f"{ROOT}-refresh-{request_id}",
                0,
                "COMPLETE",
                "CLEAN_DATA",
                "2026-09-06T10:24:56+00:00",
            ),
        )
    connection.commit()
    scope = build_campaign_source_request_scope(
        execution_id=EXECUTION,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
    )
    outcome = TemporalRefreshOutcome(
        status=REFRESH_COMPLETED,
        source_request_ids=request_ids,
        source_request_coverage=tuple(
            _coverage(request_id) for request_id in request_ids
        ),
    )
    diagnostics = campaign._carry_post_holder_refresh_evidence(
        {
            "campaign_source_request_scope": scope.as_dict(),
            "request_key_root": ROOT,
        },
        outcome,
    )
    reconciled = assemble_and_reconcile_campaign_source_requests(
        connection,
        diagnostics=diagnostics,
        request_key_root=ROOT,
        campaign_source_request_scope=scope,
    )
    assert reconciled["status"] == "OK", reconciled["terminal_detail"]
    assert reconciled["durable_campaign_request_ids"] == list(request_ids)
    assert reconciled["stage_reported_request_ids"] == list(request_ids)
    assert [
        item["source_request_id"]
        for item in reconciled["campaign_source_request_manifest"]
    ] == list(request_ids)

    corrupted = dict(diagnostics)
    corrupted["final_refresh_source_request_coverage"] = list(
        outcome.source_request_coverage[:-1]
    )
    blocked = assemble_and_reconcile_campaign_source_requests(
        connection,
        diagnostics=corrupted,
        request_key_root=ROOT,
        campaign_source_request_scope=scope,
    )
    assert blocked["status"] == "BLOCKED"
    assert blocked["missing_from_manifest"] == [904]

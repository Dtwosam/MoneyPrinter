"""Focused fec30eaa root-propagation proof using disposable SQLite only."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    StageBudget,
    derive_campaign_source_request_key_root,
    request_key_belongs_to_root,
)
from printer_v1.discovery.pre_lifecycle_refresh_composition import (
    PUMP_FRESH_CHANNEL,
    build_pre_lifecycle_refresh_stage,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    CAMPAIGN_MODE,
    AbstractCampaignCommand,
    CampaignCeilings,
)
from printer_v1.operator_cli.holder_reliability_budget_control import (
    build_pre_holder_budget_snapshot,
)
from printer_v1.operator_cli import operational_memory_factory_command as command_module
from printer_v1.sources.direct_pump_migration import (
    DIRECT_MIGRATION_INDEXED_ADDRESS,
    SIGNATURE_PAGE_REQUEST_KIND,
    SIGNATURE_PAGE_TARGET_CATEGORY,
    direct_migration_signature_page_target_identity,
)


NOW = "2026-09-04T00:00:00+00:00"
EXECUTION_ID = "fec30eaa-root-propagation"


def _head_identity() -> dict[str, object]:
    return {
        "stage": "DIRECT_PUMP_NOMINATION",
        "source_name": "solana_rpc",
        "endpoint_owner": "solana",
        "governed_request_kind": SIGNATURE_PAGE_REQUEST_KIND,
        "method_or_endpoint": "getSignaturesForAddress",
        "within_request_ordinal": 1,
        "target_category": SIGNATURE_PAGE_TARGET_CATEGORY,
        "target_identity": direct_migration_signature_page_target_identity(
            indexed_address=DIRECT_MIGRATION_INDEXED_ADDRESS,
            cursor_before=None,
        ),
        "response_bytes": 0,
        "normalized_rows": 0,
        "result": "OK",
        "reserved_from": None,
    }


def _command(db_path: Path) -> AbstractCampaignCommand:
    return AbstractCampaignCommand(
        mode=CAMPAIGN_MODE,
        db_path=db_path,
        db_target_identity="test-db",
        campaign_id="campaign",
        configuration_id="configuration",
        configuration_hash="configuration-hash",
        policy_version="test-policy",
        token_capacity=2,
        ceilings=CampaignCeilings(1, 2, 900, 45, 45, 1_024, 20),
        report_directory=db_path.parent,
        report_directory_identity="test-report-directory",
        launch_git_provenance={},
        run_id="run",
        report_id="report",
        supervision_id="supervision",
        owner_id="owner",
        lease_lock_path=db_path.parent / "lease.lock",
    )


def _record_completed_head(
    connection: sqlite3.Connection, *, request_key: str
) -> int:
    request_id = int(
        connection.execute(
            """
            INSERT INTO printer_source_requests(
                source_name,request_kind,requested_at,request_key,
                tracking_priority,source_status,data_quality_label
            ) VALUES ('solana_rpc', ?, ?, ?, 0, 'COMPLETE', 'CLEAN_DATA')
            """,
            (SIGNATURE_PAGE_REQUEST_KIND, NOW, request_key),
        ).lastrowid
    )
    connection.execute(
        """
        INSERT INTO printer_source_responses(
            source_request_id,source_name,received_at,status_code,source_status,
            data_quality_label,response_hash,normalized_payload_json
        ) VALUES (?, 'solana_rpc', ?, 200, 'COMPLETE', 'CLEAN_DATA',
                  'first-head-response', ?)
        """,
        (
            request_id,
            NOW,
            json.dumps(
                {
                    "signatures": [],
                    "transport_operation_identities": [_head_identity()],
                },
                sort_keys=True,
            ),
        ),
    )
    connection.commit()
    return request_id


def test_initial_cycle_refresh_reuses_typed_root_and_skips_completed_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bare initial root must fail this test; a second Pump call is forbidden."""
    db_path = tmp_path / "fec30eaa-root.sqlite3"
    apply_migrations(db_path)
    root = derive_campaign_source_request_key_root(EXECUTION_ID)
    request_key = f"{root}-migration-page-live-tail"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    request_id = _record_completed_head(connection, request_key=request_key)

    import printer_v1.discovery.pre_lifecycle_refresh_composition as composition

    captured: dict[str, str] = {}
    real_builder = composition.build_pre_lifecycle_refresh_stage

    def capture_builder(**kwargs):
        captured["root"] = str(kwargs["request_key_prefix"])
        return real_builder(**kwargs)

    monkeypatch.setattr(
        composition, "build_pre_lifecycle_refresh_stage", capture_builder
    )
    owner = command_module._build_pre_lifecycle_temporal_refresh_owner(
        command=_command(db_path),
        cycle_id="cycle-1",
        cycle_cutoff=NOW,
        evaluated_at=NOW,
        execution_id=EXECUTION_ID,
        acquisition_seconds=2_400,
        lifecycle_duration_seconds=900,
        heartbeat=None,
        cancellation_probe=lambda: None,
        migration_transport=lambda _context: {},
    )

    assert owner.cycle_id == "cycle-1"
    assert captured["root"] == root
    assert captured["root"] != EXECUTION_ID
    assert request_key_belongs_to_root(request_key, captured["root"])

    def second_pump_call_is_forbidden(*_args, **_kwargs):
        raise AssertionError("duplicate Pump HEAD source request emitted")

    monkeypatch.setattr(
        "printer_v1.discovery.direct_migration_discovery.run_direct_migration_discovery",
        second_pump_call_is_forbidden,
    )
    stage = build_pre_lifecycle_refresh_stage(
        db_path=db_path,
        request_key_prefix=captured["root"],
        migration_transport=lambda _context: {},
        locator_transport=lambda _context: {},
    )
    try:
        outcome = stage(
            connection,
            campaign_id="campaign",
            run_id="run",
            cycle_id="cycle-1",
            discovery_work_id="work-1",
            scheduler_job_id=1,
            refresh_ordinal=1,
            source_operations_remaining=30,
            now=NOW,
            cooperative_yield=True,
            cooperative_stage_budget=StageBudget.permanent_discovery_default(),
        )
        request_count = int(
            connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]
        )
    finally:
        connection.close()

    assert request_count == 1
    assert outcome["source_operations"] == 0
    assert outcome["channels_attempted"] == ()
    assert any(
        item["channel"] == PUMP_FRESH_CHANNEL
        and item["reason"] == "CANONICAL_PUMP_LIVE_TAIL_HEAD_ALREADY_COMPLETED"
        for item in outcome["channels_skipped"]
    )

    snapshot = build_pre_holder_budget_snapshot(
        campaign_id="campaign",
        governed_request_ids=(request_id,),
        request_manifest=(
            {
                "source_request_id": request_id,
                "logical_stage_id": "campaign|DIRECT_PUMP_NOMINATION",
                "transport_identity_count": 1,
                "transport_identity_keys": (_head_identity(),),
                "source_name": "solana_rpc",
                "request_kind": SIGNATURE_PAGE_REQUEST_KIND,
            },
        ),
        campaign_transport_identities=(_head_identity(),),
        action_local_transport_identities=(_head_identity(),),
    )
    assert snapshot.measured_transport_count == 1

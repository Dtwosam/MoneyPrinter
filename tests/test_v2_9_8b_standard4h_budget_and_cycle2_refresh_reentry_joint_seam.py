"""Joint seam: four-token 118 ceiling coexists with Cycle-2 Pump HEAD skip.

Disposable SQLite only. No live providers, full 4h campaign, Printer execution,
authorization, retrieval, decisions, positions, trades, audits, or PnL.
"""
from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    StageBudget,
    derive_campaign_source_request_key_root,
)
from printer_v1.discovery.pre_lifecycle_refresh_composition import (
    DEXSCREENER_FRESH_CHANNEL,
    PUMP_FRESH_CHANNEL,
    _rotated_fresh_channels,
    build_pre_lifecycle_refresh_stage,
)
from printer_v1.operator_cli import authoritative_admission_health
from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    scaled_standard_four_hour_capacity_contract,
)
from printer_v1.sources.direct_pump_migration import (
    DIRECT_MIGRATION_INDEXED_ADDRESS,
    SIGNATURE_PAGE_REQUEST_KIND,
    SIGNATURE_PAGE_TARGET_CATEGORY,
    direct_migration_signature_page_target_identity,
)



NOW = "2026-09-03T13:01:19+00:00"
CYCLE2_ROOT = derive_campaign_source_request_key_root(
    "joint-seam-execution:c0002"
)
_FOUR_TOKEN = {
    "continuous_first_hour": True,
    "selective_1h_continuation": True,
    "continuous_four_hour": True,
    "standard_four_hour_campaign": True,
    "four_token_proof": True,
}
_CLOSE_CONTEXT_STEP = {
    "step_kind": "CONTINUATION_CLOSE_CONTEXT",
    "step_key": "t1_continuation_close_context",
    "tracking_lane": "TRACK_FAST",
}


def _head_target() -> str:
    return direct_migration_signature_page_target_identity(
        indexed_address=DIRECT_MIGRATION_INDEXED_ADDRESS,
        cursor_before=None,
    )


def _identity() -> dict[str, object]:
    return {
        "stage": "DIRECT_PUMP_NOMINATION",
        "source_name": "solana_rpc",
        "endpoint_owner": "solana",
        "governed_request_kind": SIGNATURE_PAGE_REQUEST_KIND,
        "method_or_endpoint": "getSignaturesForAddress",
        "within_request_ordinal": 1,
        "target_category": SIGNATURE_PAGE_TARGET_CATEGORY,
        "target_identity": _head_target(),
        "response_bytes": 0,
        "normalized_rows": 0,
        "result": "OK",
        "reserved_from": None,
    }


def test_four_token_51_and_cycle2_head_skip_coexist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    capacity = scaled_standard_four_hour_capacity_contract(4)
    token_ceiling = int(capacity["lifecycle_requests_per_token"])
    assert token_ceiling == 118
    assert factory._token_ceiling_for_run_config(_FOUR_TOKEN) == token_ceiling
    assert factory._CONTINUOUS_MAX_REQUESTS_PER_TOKEN == 50

    admission_source = inspect.getsource(
        authoritative_admission_health.project_lifecycle_budget_reserve
    )
    assert "_enforce_budgets_before_step" in admission_source
    factory_source = inspect.getsource(factory._enforce_budgets_before_step)
    assert "_token_ceiling_for_run_config" in factory_source
    assert "Source Governor" not in factory_source
    refresh_source = inspect.getsource(build_pre_lifecycle_refresh_stage)
    assert "run_direct_migration_discovery" in refresh_source
    assert "enqueue_job" not in refresh_source

    with (
        patch.object(factory, "_load_run_config", return_value=_FOUR_TOKEN),
        patch.object(factory, "_run_request_count", return_value=51),
        patch.object(factory, "_token_request_count", return_value=51),
    ):
        factory._enforce_budgets_before_step(
            object(), "run", _CLOSE_CONTEXT_STEP
        )

    db_path = tmp_path / "joint-seam.sqlite3"
    apply_migrations(db_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    inserted = connection.execute(
        """
        INSERT INTO printer_source_requests(
            source_name,request_kind,requested_at,request_key,
            tracking_priority,source_status,data_quality_label
        ) VALUES ('solana_rpc',?,?,?,0,'COMPLETE','CLEAN_DATA')
        """,
        (SIGNATURE_PAGE_REQUEST_KIND, NOW, f"{CYCLE2_ROOT}-migration-page-live-tail"),
    )
    request_id = int(inserted.lastrowid)
    connection.execute(
        """
        INSERT INTO printer_source_responses(
            source_request_id,source_name,received_at,status_code,source_status,
            data_quality_label,response_hash,normalized_payload_json
        ) VALUES (?, 'solana_rpc', ?, 200, 'COMPLETE', 'CLEAN_DATA', 'fixture-hash', ?)
        """,
        (
            request_id,
            NOW,
            json.dumps(
                {
                    "signatures": [],
                    "transport_operation_identities": [_identity()],
                },
                sort_keys=True,
            ),
        ),
    )
    connection.commit()

    def boom(*_args, **_kwargs):
        raise AssertionError("joint seam reissued completed Pump HEAD")

    def fake_dex(*_args, **_kwargs):
        return {
            "status": "empty",
            "source_requests": 1,
            "request_id": 21,
            "response_id": 22,
            "pool_observations": [],
        }

    monkeypatch.setattr(
        "printer_v1.discovery.direct_migration_discovery.run_direct_migration_discovery",
        boom,
    )
    monkeypatch.setattr(
        "printer_v1.operator_cli.graduated_supply_front_door.run_fresh_profile_locator",
        fake_dex,
    )
    stage = build_pre_lifecycle_refresh_stage(
        db_path=db_path,
        request_key_prefix=CYCLE2_ROOT,
        migration_transport=lambda _ctx: {},
        locator_transport=lambda _ctx: {},
    )
    try:
        ordinal_1 = stage(
            connection,
            campaign_id="campaign",
            run_id="run",
            cycle_id="cycle-2",
            discovery_work_id="work-1",
            scheduler_job_id=1,
            refresh_ordinal=1,
            source_operations_remaining=30,
            now=NOW,
            cooperative_yield=True,
            cooperative_stage_budget=StageBudget.permanent_discovery_default(),
        )
        ordinal_2 = stage(
            connection,
            campaign_id="campaign",
            run_id="run",
            cycle_id="cycle-2",
            discovery_work_id="work-2",
            scheduler_job_id=2,
            refresh_ordinal=2,
            source_operations_remaining=30,
            now=NOW,
            cooperative_yield=True,
            cooperative_stage_budget=StageBudget.permanent_discovery_default(),
        )
        request_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_source_requests"
            ).fetchone()[0]
        )
    finally:
        connection.close()

    assert ordinal_1["source_operations"] == 0
    assert not ordinal_1.get("cooperative_incomplete")
    assert any(
        item["reason"] == "CANONICAL_PUMP_LIVE_TAIL_HEAD_ALREADY_COMPLETED"
        for item in ordinal_1["channels_skipped"]
    )
    assert request_count == 1
    assert _rotated_fresh_channels(2)[0] == DEXSCREENER_FRESH_CHANNEL
    assert ordinal_2["channels_attempted"] == (DEXSCREENER_FRESH_CHANNEL,)
    assert PUMP_FRESH_CHANNEL not in ordinal_2["channels_attempted"]
    assert ordinal_2["source_operations"] == 1

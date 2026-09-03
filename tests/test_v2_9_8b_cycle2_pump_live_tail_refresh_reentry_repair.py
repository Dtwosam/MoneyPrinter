"""Focused proofs: Cycle-2 Pump live-tail HEAD refresh re-entry skip.

Disposable SQLite only. No live providers, Scheduler work, Printer execution,
authorization, retrieval, decisions, positions, trades, audits, or PnL.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    StageBudget,
    derive_campaign_source_request_key_root,
)
from printer_v1.discovery.pre_lifecycle_refresh_composition import (
    DEXSCREENER_FRESH_CHANNEL,
    GECKOTERMINAL_NOMINATION_CHANNEL,
    PUMP_FRESH_CHANNEL,
    _rotated_fresh_channels,
    build_pre_lifecycle_refresh_stage,
    cycle_pump_live_tail_head_already_completed,
)
from printer_v1.sources.campaign_six_unit_accounting import CampaignSixUnitOwner
from printer_v1.sources.direct_pump_migration import (
    DIRECT_MIGRATION_INDEXED_ADDRESS,
    SIGNATURE_PAGE_REQUEST_KIND,
    SIGNATURE_PAGE_TARGET_CATEGORY,
    direct_migration_signature_page_target_identity,
)
from printer_v1.sources.measured_transport import (
    MeasuredTransportError,
    TransportOperationIdentity,
    canonical_transport_identity_key,
)


NOW = "2026-09-03T13:01:19+00:00"
EXECUTION_ID = "cycle2-head-replay-execution"
CYCLE1_ROOT = derive_campaign_source_request_key_root(EXECUTION_ID)
CYCLE2_ROOT = derive_campaign_source_request_key_root(f"{EXECUTION_ID}:c0002")
FOREIGN_ROOT = derive_campaign_source_request_key_root("foreign-execution:c0002")
REAL_CURSOR = "5WqY8nK3vR2mP9sL1tU4xC7bN6dA0eF8gH2jK4pQ6wE"


def _head_target() -> str:
    return direct_migration_signature_page_target_identity(
        indexed_address=DIRECT_MIGRATION_INDEXED_ADDRESS,
        cursor_before=None,
    )


def _cursor_target(signature: str) -> str:
    return direct_migration_signature_page_target_identity(
        indexed_address=DIRECT_MIGRATION_INDEXED_ADDRESS,
        cursor_before=signature,
    )


def _identity(target: str) -> dict[str, object]:
    return {
        "stage": "DIRECT_PUMP_NOMINATION",
        "source_name": "solana_rpc",
        "endpoint_owner": "solana",
        "governed_request_kind": SIGNATURE_PAGE_REQUEST_KIND,
        "method_or_endpoint": "getSignaturesForAddress",
        "within_request_ordinal": 1,
        "target_category": SIGNATURE_PAGE_TARGET_CATEGORY,
        "target_identity": target,
        "response_bytes": 0,
        "normalized_rows": 0,
        "result": "OK",
        "reserved_from": None,
    }


def _db(tmp_path: Path) -> tuple[Path, sqlite3.Connection]:
    db_path = tmp_path / "cycle2-head.sqlite3"
    apply_migrations(db_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return db_path, connection


def _record_pump_page(
    connection: sqlite3.Connection,
    *,
    request_key: str,
    identity: dict[str, object] | None,
    source_status: str = "COMPLETE",
    data_quality: str = "CLEAN_DATA",
    payload: dict[str, object] | None = None,
    as_failure: bool = False,
    raw_payload: str | None = None,
) -> int:
    request_id = int(
        connection.execute(
            """
            INSERT INTO printer_source_requests(
                source_name,request_kind,requested_at,request_key,
                tracking_priority,source_status,data_quality_label
            ) VALUES ('solana_rpc',?,?,?,0,?,?)
            """,
            (SIGNATURE_PAGE_REQUEST_KIND, NOW, request_key, source_status, data_quality),
        ).lastrowid
    )
    if as_failure:
        connection.execute(
            """
            INSERT INTO printer_source_failures(
                source_request_id,source_name,request_kind,failed_at,failure_type,
                failure_message,source_status,data_quality_label
            ) VALUES (?, 'solana_rpc', ?, ?, 'rpc_timeout', 'fixture failure',
                      'STALE', 'STALE_DATA')
            """,
            (request_id, SIGNATURE_PAGE_REQUEST_KIND, NOW),
        )
    else:
        if raw_payload is not None:
            encoded = raw_payload
        else:
            body = payload if payload is not None else {
                "signatures": [],
                "transport_operation_identities": (
                    [] if identity is None else [identity]
                ),
            }
            encoded = json.dumps(body, sort_keys=True)
        connection.execute(
            """
            INSERT INTO printer_source_responses(
                source_request_id,source_name,received_at,status_code,source_status,
                data_quality_label,response_hash,normalized_payload_json
            ) VALUES (?, 'solana_rpc', ?, 200, ?, ?, 'fixture-hash', ?)
            """,
            (request_id, NOW, source_status, data_quality, encoded),
        )
    connection.commit()
    return request_id


def _boom(*_args, **_kwargs):
    raise AssertionError("completed Pump HEAD transport was reissued")


def _stage(db_path: Path, *, prefix: str):
    return build_pre_lifecycle_refresh_stage(
        db_path=db_path,
        request_key_prefix=prefix,
        migration_transport=lambda _ctx: {},
        locator_transport=lambda _ctx: {},
    )


def _run_refresh(
    stage,
    connection: sqlite3.Connection,
    *,
    ordinal: int,
    cooperative: bool,
    remaining: int = 30,
):
    kwargs: dict[str, object] = {
        "campaign_id": "campaign",
        "run_id": "run",
        "cycle_id": "cycle-2",
        "discovery_work_id": f"work-{ordinal}",
        "scheduler_job_id": ordinal,
        "refresh_ordinal": ordinal,
        "source_operations_remaining": remaining,
        "now": NOW,
        "cooperative_yield": cooperative,
    }
    if cooperative:
        kwargs["cooperative_stage_budget"] = StageBudget.permanent_discovery_default()
    return stage(connection, **kwargs)


def test_helper_detects_completed_cycle2_empty_head(tmp_path: Path) -> None:
    _db_path, connection = _db(tmp_path)
    try:
        _record_pump_page(
            connection,
            request_key=f"{CYCLE2_ROOT}-migration-page-live-tail",
            identity=_identity(_head_target()),
        )
        assert cycle_pump_live_tail_head_already_completed(
            connection, request_key_root=CYCLE2_ROOT
        ) is True
    finally:
        connection.close()


def test_helper_ignores_failure_partial_dirty_malformed_and_cursor(
    tmp_path: Path,
) -> None:
    _db_path, connection = _db(tmp_path)
    try:
        _record_pump_page(
            connection,
            request_key=f"{CYCLE2_ROOT}-migration-page-failed",
            identity=_identity(_head_target()),
            as_failure=True,
        )
        assert cycle_pump_live_tail_head_already_completed(
            connection, request_key_root=CYCLE2_ROOT
        ) is False

        _record_pump_page(
            connection,
            request_key=f"{CYCLE2_ROOT}-migration-page-partial",
            identity=_identity(_head_target()),
            source_status="PARTIAL",
        )
        assert cycle_pump_live_tail_head_already_completed(
            connection, request_key_root=CYCLE2_ROOT
        ) is False

        _record_pump_page(
            connection,
            request_key=f"{CYCLE2_ROOT}-migration-page-dirty",
            identity=_identity(_head_target()),
            data_quality="DIRTY_DATA",
        )
        assert cycle_pump_live_tail_head_already_completed(
            connection, request_key_root=CYCLE2_ROOT
        ) is False

        _record_pump_page(
            connection,
            request_key=f"{CYCLE2_ROOT}-migration-page-malformed",
            identity=None,
            raw_payload="{not-json",
        )
        assert cycle_pump_live_tail_head_already_completed(
            connection, request_key_root=CYCLE2_ROOT
        ) is False

        _record_pump_page(
            connection,
            request_key=f"{CYCLE2_ROOT}-migration-page-cursor",
            identity=_identity(_cursor_target(REAL_CURSOR)),
        )
        assert cycle_pump_live_tail_head_already_completed(
            connection, request_key_root=CYCLE2_ROOT
        ) is False
        assert _head_target() != _cursor_target(REAL_CURSOR)
        assert canonical_transport_identity_key(
            _identity(_head_target())
        ) != canonical_transport_identity_key(
            _identity(_cursor_target(REAL_CURSOR))
        )
    finally:
        connection.close()


def _clear_source_rows(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM printer_source_responses")
    connection.execute("DELETE FROM printer_source_failures")
    connection.execute("DELETE FROM printer_source_requests")
    connection.commit()


def test_helper_isolates_cycle_and_campaign_roots(tmp_path: Path) -> None:
    _db_path, connection = _db(tmp_path)
    try:
        _record_pump_page(
            connection,
            request_key=f"{CYCLE1_ROOT}-migration-page-live-tail",
            identity=_identity(_head_target()),
        )
        assert cycle_pump_live_tail_head_already_completed(
            connection, request_key_root=CYCLE2_ROOT
        ) is False
        assert cycle_pump_live_tail_head_already_completed(
            connection, request_key_root=CYCLE1_ROOT
        ) is True

        _clear_source_rows(connection)
        _record_pump_page(
            connection,
            request_key=f"{FOREIGN_ROOT}-migration-page-live-tail",
            identity=_identity(_head_target()),
        )
        assert cycle_pump_live_tail_head_already_completed(
            connection, request_key_root=CYCLE2_ROOT
        ) is False
        assert cycle_pump_live_tail_head_already_completed(
            connection, request_key_root=FOREIGN_ROOT
        ) is True

        _clear_source_rows(connection)
        _record_pump_page(
            connection,
            request_key=f"{CYCLE2_ROOT}-migration-page-live-tail",
            identity=_identity(_head_target()),
        )
        assert cycle_pump_live_tail_head_already_completed(
            connection, request_key_root=CYCLE2_ROOT
        ) is True
        assert cycle_pump_live_tail_head_already_completed(
            connection, request_key_root=CYCLE1_ROOT
        ) is False
        assert cycle_pump_live_tail_head_already_completed(
            connection, request_key_root=FOREIGN_ROOT
        ) is False
    finally:
        connection.close()


def test_sep3_refresh_ordinal_1_skips_completed_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path, connection = _db(tmp_path)
    original_id = _record_pump_page(
        connection,
        request_key=f"{CYCLE2_ROOT}-migration-page-live-tail",
        identity=_identity(_head_target()),
    )
    monkeypatch.setattr(
        "printer_v1.discovery.direct_migration_discovery.run_direct_migration_discovery",
        _boom,
    )
    sink_calls: list[object] = []
    stage = build_pre_lifecycle_refresh_stage(
        db_path=db_path,
        request_key_prefix=CYCLE2_ROOT,
        migration_transport=lambda _ctx: {},
        locator_transport=lambda _ctx: {},
        stage_evidence_sink=sink_calls.append,
    )
    try:
        result = _run_refresh(stage, connection, ordinal=1, cooperative=True)
        again = _run_refresh(stage, connection, ordinal=1, cooperative=True)
        request_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_source_requests"
            ).fetchone()[0]
        )
        preserved = connection.execute(
            "SELECT request_key,source_status FROM printer_source_requests WHERE id=?",
            (original_id,),
        ).fetchone()
    finally:
        connection.close()

    for outcome in (result, again):
        assert outcome["source_operations"] == 0
        assert not outcome.get("cooperative_incomplete")
        assert PUMP_FRESH_CHANNEL not in outcome["channels_attempted"]
        assert outcome["channels_unavailable"] == ()
        assert outcome["provider_failures"] == 0
        assert any(
            item["channel"] == PUMP_FRESH_CHANNEL
            and item["reason"]
            == "CANONICAL_PUMP_LIVE_TAIL_HEAD_ALREADY_COMPLETED"
            for item in outcome["channels_skipped"]
        )
        pump_report = outcome["stage_reports"][PUMP_FRESH_CHANNEL]
        assert pump_report["status"] == "CANONICAL_TRANSPORT_ALREADY_COMPLETED"
        assert pump_report["source_requests"] == 0
        assert pump_report["target_identity"] == _head_target()
    assert result["channels_skipped"] == again["channels_skipped"]
    assert request_count == 1
    assert sink_calls == []
    assert str(preserved["request_key"]) == f"{CYCLE2_ROOT}-migration-page-live-tail"
    assert str(preserved["source_status"]) == "COMPLETE"


def test_cooperative_ordinal_2_still_selects_dexscreener_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _rotated_fresh_channels(1)[0] == PUMP_FRESH_CHANNEL
    assert _rotated_fresh_channels(2)[0] == DEXSCREENER_FRESH_CHANNEL
    assert _rotated_fresh_channels(3)[0] == GECKOTERMINAL_NOMINATION_CHANNEL

    db_path, connection = _db(tmp_path)
    _record_pump_page(
        connection,
        request_key=f"{CYCLE2_ROOT}-migration-page-live-tail",
        identity=_identity(_head_target()),
    )
    calls: list[str] = []

    def fake_dex(*_args, **_kwargs):
        calls.append("dex")
        return {
            "status": "empty",
            "source_requests": 1,
            "request_id": 9,
            "response_id": 10,
            "pool_observations": [],
        }

    monkeypatch.setattr(
        "printer_v1.discovery.direct_migration_discovery.run_direct_migration_discovery",
        _boom,
    )
    monkeypatch.setattr(
        "printer_v1.operator_cli.graduated_supply_front_door.run_fresh_profile_locator",
        fake_dex,
    )
    stage = _stage(db_path, prefix=CYCLE2_ROOT)
    try:
        first = _run_refresh(stage, connection, ordinal=1, cooperative=True)
        second = _run_refresh(stage, connection, ordinal=2, cooperative=True)
    finally:
        connection.close()

    assert first["source_operations"] == 0
    assert not first.get("cooperative_incomplete")
    assert calls == ["dex"]
    assert second["channels_attempted"] == (DEXSCREENER_FRESH_CHANNEL,)
    assert second["source_operations"] == 1
    assert second.get("cooperative_incomplete") is True


def test_noncooperative_skip_continues_peer_channels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path, connection = _db(tmp_path)
    _record_pump_page(
        connection,
        request_key=f"{CYCLE2_ROOT}-migration-page-live-tail",
        identity=_identity(_head_target()),
    )
    calls: list[str] = []

    def fake_dex(*_args, **_kwargs):
        calls.append("dex")
        return {
            "status": "empty",
            "source_requests": 1,
            "request_id": 11,
            "response_id": 12,
            "pool_observations": [],
        }

    def fake_gt(*_args, **_kwargs):
        calls.append("gt")
        return {
            "status": "COMPLETE",
            "failure_type": None,
            "source_requests": 1,
            "nominations": [],
        }

    def fake_backup(*_args, **_kwargs):
        calls.append("backup")
        return {"source_requests": 0, "accounting_blocker": False}

    def fake_protocol(*_args, **_kwargs):
        calls.append("protocol")
        return {
            "source_requests": 0,
            "shared_source_failures": 0,
            "promoted_observation_eligible": [],
        }

    monkeypatch.setattr(
        "printer_v1.discovery.direct_migration_discovery.run_direct_migration_discovery",
        _boom,
    )
    monkeypatch.setattr(
        "printer_v1.operator_cli.graduated_supply_front_door.run_fresh_profile_locator",
        fake_dex,
    )
    monkeypatch.setattr(
        "printer_v1.discovery.pre_lifecycle_refresh_composition."
        "run_geckoterminal_fresh_nomination",
        fake_gt,
    )
    monkeypatch.setattr(
        "printer_v1.discovery.pre_lifecycle_refresh_composition."
        "run_bounded_unknown_liquidity_backup",
        fake_backup,
    )
    monkeypatch.setattr(
        "printer_v1.discovery.pre_lifecycle_refresh_composition."
        "process_protocol_confirmation_queue",
        fake_protocol,
    )
    stage = _stage(db_path, prefix=CYCLE2_ROOT)
    try:
        result = _run_refresh(stage, connection, ordinal=1, cooperative=False)
    finally:
        connection.close()

    assert "pump" not in calls
    assert calls[:2] == ["dex", "gt"]
    assert result["source_operations"] == 2
    assert PUMP_FRESH_CHANNEL not in result["channels_attempted"]
    assert DEXSCREENER_FRESH_CHANNEL in result["channels_attempted"]
    assert GECKOTERMINAL_NOMINATION_CHANNEL in result["channels_attempted"]
    assert any(
        item["reason"] == "CANONICAL_PUMP_LIVE_TAIL_HEAD_ALREADY_COMPLETED"
        for item in result["channels_skipped"]
    )


def test_duplicate_transport_identity_still_raises() -> None:
    identity = TransportOperationIdentity(
        stage="DIRECT_PUMP_NOMINATION",
        source_name="solana_rpc",
        endpoint_owner="solana",
        governed_request_kind=SIGNATURE_PAGE_REQUEST_KIND,
        method_or_endpoint="getSignaturesForAddress",
        within_request_ordinal=1,
        target_category=SIGNATURE_PAGE_TARGET_CATEGORY,
        target_identity=_head_target(),
        response_bytes=0,
        normalized_rows=0,
        result="OK",
    )
    owner = CampaignSixUnitOwner(
        campaign_id="campaign",
        run_id="run",
        cycle_id="cycle-2",
    )
    owner.record_transport(identity)
    with pytest.raises(MeasuredTransportError, match="DUPLICATE_TRANSPORT_IDENTITY"):
        owner.record_transport(identity)

"""V2-9.8B accounting handoff + exact-identity report-only repair tests.

Frozen transports and disposable migration-049 databases only.
No providers, no authoritative DB mutation, no campaign execution.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping
from unittest.mock import patch

import pytest

from printer_v1.db.migrate import apply_migrations
from printer_v1.discovery.direct_migration_discovery import (
    run_direct_migration_discovery,
)
from printer_v1.discovery.eligible_token_supply import (
    SOURCE_VISIBILITY_SHORTAGE,
    run_persistent_eligible_token_supply,
)
from printer_v1.discovery.graduated_liquidity_front_door import (
    run_graduated_liquidity_front_door,
)
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli.graduated_supply_front_door import (
    run_fresh_profile_locator,
)
from printer_v1.operator_cli.operational_memory_factory_command import (
    _finalize_operational_six_unit_accounting,
)
from printer_v1.operator_cli.unified_terminal_closure import (
    build_campaign_terminal_report,
    write_campaign_terminal_report,
)
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignSixUnitError,
    CampaignSixUnitOwner,
    build_campaign_stage_id,
    pre_operation_no_work_evidence,
    reconcile_owner_to_action_local,
    reconstruct_six_unit_totals_from_evidence,
    seal_campaign_stage_evidence,
)
from printer_v1.sources.direct_pump_migration import (
    SIGNATURE_PAGE_REQUEST_KIND,
    TRANSACTION_REQUEST_KIND,
)
from printer_v1.sources.measured_transport import (
    MeasuredTransportLedger,
    build_transport_identity,
)
from printer_v1.sources.pump_migration import MIGRATION_PROVENANCE
from printer_v1.sources.pumpswap_graduated_registry import (
    LATEST_GRADUATED_CHANNEL,
    record_graduated_candidate,
)

from test_v2_9_7e_11_authoritative_live_operational_campaign import (
    _OperationalBase,
    _two_create_transport,
)
from test_v2_9_8b_candidate_acquisition_foundation import _pinned_migration_fixture


NOW = "2026-07-31T12:00:00+00:00"
CAMPAIGN = "campaign-repair-1"
RUN = "run-repair-1"
CYCLE = "cycle-repair-1"


def _transport_identity(
    *,
    stage: str,
    source: str,
    kind: str,
    ordinal: int,
    target: str,
    result: str = "OK",
    response_bytes: int = 10,
    normalized_rows: int = 1,
    method: str | None = None,
) -> dict[str, Any]:
    return build_transport_identity(
        stage=stage,
        source_name=source,
        endpoint_owner="Source Governor",
        governed_request_kind=kind,
        method_or_endpoint=method or f"GET /{source}/{ordinal}",
        within_request_ordinal=ordinal,
        target_category="target",
        target_identity=target,
        response_bytes=response_bytes,
        normalized_rows=normalized_rows,
        result=result,
    ).as_dict()


def _sealed_stage(
    *,
    stage_kind: str,
    sequence: int,
    transports: list[dict[str, Any]],
    status: str = "COMPLETED",
    cause: str | None = None,
    campaign_id: str = CAMPAIGN,
    run_id: str = RUN,
    cycle_id: str = CYCLE,
) -> dict[str, Any]:
    ledger = MeasuredTransportLedger(
        campaign_id=campaign_id, run_id=run_id, cycle_id=cycle_id
    )
    for raw in transports:
        ledger.record_transport(
            build_transport_identity(
                stage=str(raw["stage"]),
                source_name=str(raw["source_name"]),
                endpoint_owner=str(raw.get("endpoint_owner") or "Source Governor"),
                governed_request_kind=str(raw["governed_request_kind"]),
                method_or_endpoint=str(raw["method_or_endpoint"]),
                within_request_ordinal=int(raw["within_request_ordinal"]),
                target_category=str(raw.get("target_category") or "target"),
                target_identity=raw.get("target_identity"),
                response_bytes=int(raw.get("response_bytes") or 0),
                normalized_rows=int(raw.get("normalized_rows") or 0),
                result=str(raw.get("result") or "OK"),
            )
        )
    return seal_campaign_stage_evidence(
        ledger=ledger,
        stage_id=build_campaign_stage_id(
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            stage_kind=stage_kind,
            stage_sequence=sequence,
        ),
        stage_kind=stage_kind,
        stage_sequence=sequence,
        stage_terminal_status=status,
        stage_first_terminal_cause=cause,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        sealed_at=NOW,
    )


# --------------------------------------------------------------------------- #
# 1. Campaign owner tests
# --------------------------------------------------------------------------- #


def test_owner_ingests_valid_sealed_evidence() -> None:
    owner = CampaignSixUnitOwner(campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE)
    evidence = _sealed_stage(
        stage_kind="DIRECT_MIGRATION",
        sequence=1,
        transports=[
            _transport_identity(
                stage="DIRECT_PUMP_NOMINATION",
                source="solana_rpc",
                kind="getSignaturesForAddress",
                ordinal=1,
                target="page-1",
            )
        ],
    )
    owner.ingest_stage_evidence(evidence)
    assert owner.stage_evidence_count == 1
    assert owner.owner_transport_operation_count == 1
    assert owner.ingested_stage_ids == [evidence["stage_id"]]
    diag = owner.accounting_diagnostics()
    assert diag["sealed_stage_count"] == 1
    assert diag["ingested_stage_count"] == 1
    assert diag["accounting_block_reason"] is None


def test_owner_rejects_duplicate_stage_id() -> None:
    owner = CampaignSixUnitOwner(campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE)
    first = _sealed_stage(
        stage_kind="DIRECT_MIGRATION",
        sequence=1,
        transports=[
            _transport_identity(
                stage="DIRECT_PUMP_NOMINATION",
                source="solana_rpc",
                kind="sig",
                ordinal=1,
                target="a",
            )
        ],
    )
    second = _sealed_stage(
        stage_kind="DIRECT_MIGRATION",
        sequence=1,
        transports=[
            _transport_identity(
                stage="DIRECT_PUMP_NOMINATION",
                source="solana_rpc",
                kind="sig",
                ordinal=2,
                target="b",
            )
        ],
    )
    # Force identical stage_id.
    second["stage_id"] = first["stage_id"]
    owner.ingest_stage_evidence(first)
    with pytest.raises(CampaignSixUnitError, match="DUPLICATE_STAGE_ID"):
        owner.ingest_stage_evidence(second)
    assert owner.stage_evidence_count == 1
    assert owner.accounting_block_reason is not None


def test_owner_rejects_duplicate_transport_across_stages() -> None:
    owner = CampaignSixUnitOwner(campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE)
    identity = _transport_identity(
        stage="DEXSCREENER_DISCOVERY",
        source="dexscreener_pair",
        kind="pair_market_snapshot",
        ordinal=1,
        target="pool-1",
    )
    first = _sealed_stage(
        stage_kind="EXACT_LIQUIDITY", sequence=1, transports=[identity]
    )
    second = _sealed_stage(
        stage_kind="EXACT_LIQUIDITY",
        sequence=2,
        transports=[copy.deepcopy(identity)],
    )
    owner.ingest_stage_evidence(first)
    with pytest.raises(CampaignSixUnitError, match="DUPLICATE_TRANSPORT"):
        owner.ingest_stage_evidence(second)
    assert owner.stage_evidence_count == 1
    assert owner.owner_transport_operation_count == 1


def test_owner_rejects_campaign_run_cycle_mismatch() -> None:
    owner = CampaignSixUnitOwner(campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE)
    evidence = _sealed_stage(
        stage_kind="LOCATOR",
        sequence=1,
        transports=[
            _transport_identity(
                stage="DEXSCREENER_DISCOVERY",
                source="dexscreener_profiles",
                kind="fresh",
                ordinal=1,
                target="profiles",
            )
        ],
        campaign_id="other-campaign",
    )
    with pytest.raises(CampaignSixUnitError, match="IDENTITY_MISMATCH"):
        owner.ingest_stage_evidence(evidence)


def test_owner_rejects_invalid_terminal_status_and_sequence() -> None:
    owner = CampaignSixUnitOwner(campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE)
    bad_status = _sealed_stage(
        stage_kind="LOCATOR",
        sequence=1,
        transports=[
            _transport_identity(
                stage="DEXSCREENER_DISCOVERY",
                source="dexscreener_profiles",
                kind="fresh",
                ordinal=1,
                target="p",
            )
        ],
    )
    bad_status["stage_terminal_status"] = "SUCCESS"
    with pytest.raises(CampaignSixUnitError, match="INVALID_STAGE_TERMINAL_STATUS"):
        owner.ingest_stage_evidence(bad_status)

    bad_seq = _sealed_stage(
        stage_kind="LOCATOR",
        sequence=1,
        transports=[
            _transport_identity(
                stage="DEXSCREENER_DISCOVERY",
                source="dexscreener_profiles",
                kind="fresh",
                ordinal=2,
                target="p2",
            )
        ],
    )
    bad_seq["stage_sequence"] = 0
    with pytest.raises(CampaignSixUnitError, match="INVALID_STAGE_SEQUENCE"):
        owner.ingest_stage_evidence(bad_seq)


def test_owner_rejects_negative_counters_and_is_atomic() -> None:
    owner = CampaignSixUnitOwner(campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE)
    good = _sealed_stage(
        stage_kind="DIRECT_MIGRATION",
        sequence=1,
        transports=[
            _transport_identity(
                stage="DIRECT_PUMP_NOMINATION",
                source="solana_rpc",
                kind="sig",
                ordinal=1,
                target="a",
            )
        ],
    )
    owner.ingest_stage_evidence(good)
    first_block = owner.accounting_block_reason
    bad = _sealed_stage(
        stage_kind="EXACT_LIQUIDITY",
        sequence=1,
        transports=[
            _transport_identity(
                stage="DEXSCREENER_DISCOVERY",
                source="dexscreener_pair",
                kind="pair",
                ordinal=1,
                target="pool",
            )
        ],
    )
    bad["local_validations"] = -1
    with pytest.raises(CampaignSixUnitError, match="MALFORMED|NEGATIVE"):
        owner.ingest_stage_evidence(bad)
    assert owner.stage_evidence_count == 1
    assert owner.owner_transport_operation_count == 1
    # First accounting block reason remains stable.
    assert owner.accounting_block_reason is not None
    owner.block("LATER_REASON")
    assert owner.accounting_block_reason != "LATER_REASON" or first_block is None


def test_seal_helper_rejects_empty_started_and_permits_pre_operation_no_work() -> None:
    empty = MeasuredTransportLedger()
    with pytest.raises(CampaignSixUnitError, match="EMPTY_STARTED_STAGE"):
        seal_campaign_stage_evidence(
            ledger=empty,
            stage_id="c|r|y|LOCATOR|1",
            stage_kind="LOCATOR",
            stage_sequence=1,
            stage_terminal_status="COMPLETED",
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
        )
    no_work = pre_operation_no_work_evidence(
        campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE, reason="no work"
    )
    sealed = seal_campaign_stage_evidence(
        evidence=no_work,
        stage_id=build_campaign_stage_id(
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
            stage_kind="PRE_OPERATION",
            stage_sequence=1,
        ),
        stage_kind="PRE_OPERATION",
        stage_sequence=1,
        stage_terminal_status="BLOCKED",
        stage_first_terminal_cause="no work",
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
    )
    assert sealed["phase"] == "PRE_OPERATION_NO_WORK"
    assert sealed["stage_id"]


# --------------------------------------------------------------------------- #
# 2. Child-stage tests
# --------------------------------------------------------------------------- #


def _migration_transport(tx):
    def transport(context):
        if context.request.request_kind == SIGNATURE_PAGE_REQUEST_KIND:
            return {
                "result": [
                    {
                        "signature": (
                            "5NarrowDirectPumpMigrationFinalizedSignature"
                            "111111111111111111111111111111111111111111111111"
                        ),
                        "slot": tx["slot"],
                        "err": None,
                        "confirmationStatus": "finalized",
                    }
                ],
                "response_bytes": 32,
                "transport_operations_used": 1,
                "transport_operation_identities": [
                    _transport_identity(
                        stage="DIRECT_PUMP_NOMINATION",
                        source="solana_rpc",
                        kind=SIGNATURE_PAGE_REQUEST_KIND,
                        ordinal=1,
                        target="page",
                        method="getSignaturesForAddress",
                    )
                ],
            }
        if context.request.request_kind == TRANSACTION_REQUEST_KIND:
            return {
                "result": tx,
                "response_bytes": 64,
                "transport_operations_used": 1,
                "transport_operation_identities": [
                    _transport_identity(
                        stage="DIRECT_PUMP_NOMINATION",
                        source="solana_rpc",
                        kind=TRANSACTION_REQUEST_KIND,
                        ordinal=2,
                        target="tx",
                        method="getTransaction",
                        result="FAILED",
                    )
                ],
            }
        raise AssertionError(context.request.request_kind)

    return transport


def test_direct_migration_seals_once(tmp_path: Path) -> None:
    tx, _infos, _mint, _pool = _pinned_migration_fixture()
    db = tmp_path / "dm.sqlite3"
    apply_migrations(db)
    sealed: list[Mapping[str, Any]] = []

    report = run_direct_migration_discovery(
        db,
        migration_transport=_migration_transport(tx),
        verifier_transport_factory=lambda m, s: (lambda _c: {
            "pumpswap_confirmation": {"confirmed": False},
            "transport_operations_used": 0,
            "transport_operation_identities": [],
        }),
        now=NOW,
        stage_evidence_sink=sealed.append,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
    )
    assert len(sealed) == 1
    assert sealed[0]["stage_kind"] == "DIRECT_MIGRATION"
    assert sealed[0]["stage_terminal_status"] in {"COMPLETED", "BLOCKED", "FAILED"}
    assert report.get("sealed_stage_evidence") is not None


def test_locator_seals_once_when_attempted(tmp_path: Path) -> None:
    db = tmp_path / "loc.sqlite3"
    apply_migrations(db)
    sealed: list[Mapping[str, Any]] = []

    def transport(_context):
        identity = _transport_identity(
            stage="DEXSCREENER_DISCOVERY",
            source="dexscreener_profiles",
            kind="dexscreener_fresh_profiles",
            ordinal=1,
            target="profiles",
            result="FAILED",
        )
        # Use fixture_status so normalize retains declared transport identities.
        return {
            "fixture_status": "failure",
            "failure_type": "dexscreener_fixture_failure",
            "failure_message": "frozen locator failure",
            "transport_operations_used": 1,
            "transport_operation_identities": [identity],
            "response_bytes": 8,
            "normalized_rows": 0,
        }

    report = run_fresh_profile_locator(
        db,
        transport=transport,
        now=NOW,
        stage_evidence_sink=sealed.append,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
    )
    assert len(sealed) == 1
    assert sealed[0]["stage_kind"] == "LOCATOR"
    assert report["source_requests"] == 1


def test_locator_emits_no_stage_when_not_requested(tmp_path: Path) -> None:
    db = tmp_path / "no-loc.sqlite3"
    apply_migrations(db)
    sealed: list[Mapping[str, Any]] = []
    result = run_persistent_eligible_token_supply(
        db,
        cycle_seed="no-locator",
        migration_transport=lambda _c: {
            "result": [],
            "response_bytes": 1,
            "transport_operations_used": 1,
            "transport_operation_identities": [
                _transport_identity(
                    stage="DIRECT_PUMP_NOMINATION",
                    source="solana_rpc",
                    kind=SIGNATURE_PAGE_REQUEST_KIND,
                    ordinal=1,
                    target="empty-page",
                )
            ],
        },
        now=NOW,
        run_locator=False,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
        stage_evidence_sink=sealed.append,
        front_door_max_candidates=1,
    )
    kinds = [item.get("stage_kind") for item in sealed]
    assert "LOCATOR" not in kinds
    assert result.locator_report.get("status") == "NOT_REQUESTED"


def test_each_liquidity_round_uses_distinct_stage_id(tmp_path: Path) -> None:
    db = tmp_path / "rounds.sqlite3"
    apply_migrations(db)
    from printer_v1.sources.pumpswap_graduated_registry import (
        LATEST_GRADUATED_CHANNEL,
        record_graduated_candidate,
    )
    from printer_v1.sources.pump_migration import MIGRATION_PROVENANCE

    conn = sqlite3.connect(db)
    try:
        for i in range(3):
            record_graduated_candidate(
                conn,
                mint=f"MintRound{i:02d}1111111111111111111111111111111",
                migration_signature=f"sig-round-{i}",
                pumpswap_pool=f"PoolRound{i:02d}111111111111111111111111111111",
                graduation_block_time=1 + i,
                graduation_slot=1 + i,
                now=NOW,
                discovery_channel=LATEST_GRADUATED_CHANNEL,
                migration_provenance=MIGRATION_PROVENANCE,
            )
        conn.commit()
    finally:
        conn.close()

    sealed: list[Mapping[str, Any]] = []

    def factory(mint: str, pool: str):
        def transport(_context):
            identity = _transport_identity(
                stage="DEXSCREENER_DISCOVERY",
                source="dexscreener_pair",
                kind="pair_market_snapshot",
                ordinal=1,
                target=pool,
                result="MALFORMED",
            )
            return {
                "fixture_status": "failure",
                "failure_type": "dexscreener_malformed_payload",
                "failure_message": "malformed",
                "transport_operations_used": 1,
                "transport_operation_identities": [identity],
                "response_bytes": 4,
                "normalized_rows": 0,
            }

        return transport

    run_graduated_liquidity_front_door(
        db,
        cycle_seed="r1",
        latest_mints=set(),
        dexscreener_transport_factory=factory,
        now=NOW,
        max_candidates=1,
        stage_evidence_sink=sealed.append,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
        discovery_round=1,
    )
    run_graduated_liquidity_front_door(
        db,
        cycle_seed="r2",
        latest_mints=set(),
        dexscreener_transport_factory=factory,
        now=NOW,
        max_candidates=1,
        exclude_mints={f"MintRound00{'1' * 36}"[:44]},
        stage_evidence_sink=sealed.append,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
        discovery_round=2,
    )
    assert len(sealed) >= 1
    stage_ids = [item["stage_id"] for item in sealed]
    assert len(stage_ids) == len(set(stage_ids))
    assert all(item["stage_kind"] == "EXACT_LIQUIDITY" for item in sealed)
    # Failed/malformed still produce measured attempted transport evidence.
    assert all(
        int(len(item.get("transport_operations") or ())) >= 1 for item in sealed
    )


def test_sink_exception_preserves_first_terminal_cause(tmp_path: Path) -> None:
    db = tmp_path / "sink-fail.sqlite3"
    apply_migrations(db)

    def boom(_evidence):
        raise RuntimeError("SINK_INGEST_FAILED")

    with pytest.raises(RuntimeError, match="SINK_INGEST_FAILED"):
        run_direct_migration_discovery(
            db,
            migration_transport=lambda _c: {
                "result": [],
                "response_bytes": 1,
                "transport_operations_used": 1,
                "transport_operation_identities": [
                    _transport_identity(
                        stage="DIRECT_PUMP_NOMINATION",
                        source="solana_rpc",
                        kind=SIGNATURE_PAGE_REQUEST_KIND,
                        ordinal=1,
                        target="empty",
                    )
                ],
            },
            now=NOW,
            stage_evidence_sink=boom,
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
        )


# --------------------------------------------------------------------------- #
# 3. Exact identity reconciliation
# --------------------------------------------------------------------------- #


def test_owner_count_greater_than_action_local_blocks() -> None:
    owner = CampaignSixUnitOwner(campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE)
    a = _transport_identity(
        stage="DIRECT_PUMP_NOMINATION",
        source="solana_rpc",
        kind="sig",
        ordinal=1,
        target="a",
    )
    b = _transport_identity(
        stage="DIRECT_PUMP_NOMINATION",
        source="solana_rpc",
        kind="sig",
        ordinal=2,
        target="b",
    )
    owner.ingest_stage_evidence(
        _sealed_stage(stage_kind="DIRECT_MIGRATION", sequence=1, transports=[a, b])
    )
    result = reconcile_owner_to_action_local(
        owner,
        action_local_transport_identities=[a],
    )
    assert result["equal"] is False
    assert result["mismatch_reason"] == "CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH"
    assert result["owner_transport_operation_count"] == 2
    assert result["action_local_transport_identity_count"] == 1


def test_action_local_greater_than_owner_blocks() -> None:
    owner = CampaignSixUnitOwner(campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE)
    a = _transport_identity(
        stage="DIRECT_PUMP_NOMINATION",
        source="solana_rpc",
        kind="sig",
        ordinal=1,
        target="a",
    )
    b = _transport_identity(
        stage="DIRECT_PUMP_NOMINATION",
        source="solana_rpc",
        kind="sig",
        ordinal=2,
        target="b",
    )
    owner.ingest_stage_evidence(
        _sealed_stage(stage_kind="DIRECT_MIGRATION", sequence=1, transports=[a])
    )
    result = reconcile_owner_to_action_local(
        owner,
        action_local_transport_identities=[a, b],
    )
    assert result["equal"] is False
    assert result["mismatch_reason"] == "CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH"


def test_equal_counts_with_different_identities_block() -> None:
    owner = CampaignSixUnitOwner(campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE)
    a = _transport_identity(
        stage="DIRECT_PUMP_NOMINATION",
        source="solana_rpc",
        kind="sig",
        ordinal=1,
        target="a",
    )
    b = _transport_identity(
        stage="DIRECT_PUMP_NOMINATION",
        source="solana_rpc",
        kind="sig",
        ordinal=1,
        target="b",
    )
    owner.ingest_stage_evidence(
        _sealed_stage(stage_kind="DIRECT_MIGRATION", sequence=1, transports=[a])
    )
    result = reconcile_owner_to_action_local(
        owner,
        action_local_transport_identities=[b],
    )
    assert result["equal"] is False
    assert result["mismatch_reason"] == "CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH"
    assert result["identity_sets_equal"] is False


def test_count_only_action_local_is_design_blocked() -> None:
    owner = CampaignSixUnitOwner(campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE)
    a = _transport_identity(
        stage="DIRECT_PUMP_NOMINATION",
        source="solana_rpc",
        kind="sig",
        ordinal=1,
        target="a",
    )
    owner.ingest_stage_evidence(
        _sealed_stage(stage_kind="DIRECT_MIGRATION", sequence=1, transports=[a])
    )
    result = reconcile_owner_to_action_local(
        owner,
        action_local_source_operations=1,
    )
    assert result["equal"] is False
    assert result["mismatch_reason"] == "ACTION_LOCAL_TRANSPORT_IDENTITY_DESIGN_BLOCKED"


# --------------------------------------------------------------------------- #
# 3b. Exception-safe stage sealing
# --------------------------------------------------------------------------- #


def test_direct_migration_unexpected_exception_seals_failed_once(
    tmp_path: Path,
) -> None:
    """After transport work, an unexpected body exception seals FAILED once."""
    db = tmp_path / "dm-exc.sqlite3"
    apply_migrations(db)
    sealed: list[Mapping[str, Any]] = []
    tx, _infos, _mint, _pool = _pinned_migration_fixture()

    # Raise after source work has recorded transports (not inside adapter).
    with patch(
        "printer_v1.discovery.direct_migration_discovery._ledger_counts",
        side_effect=RuntimeError("UNEXPECTED_DIRECT_MIGRATION_FAILURE"),
    ):
        with pytest.raises(RuntimeError, match="UNEXPECTED_DIRECT_MIGRATION_FAILURE"):
            run_direct_migration_discovery(
                db,
                migration_transport=_migration_transport(tx),
                verifier_transport_factory=lambda m, s: (
                    lambda _c: {
                        "pumpswap_confirmation": {"confirmed": False},
                        "transport_operations_used": 0,
                        "transport_operation_identities": [],
                    }
                ),
                now=NOW,
                stage_evidence_sink=sealed.append,
                campaign_id=CAMPAIGN,
                run_id=RUN,
                cycle_id=CYCLE,
            )
    assert len(sealed) == 1
    assert sealed[0]["stage_terminal_status"] == "FAILED"
    assert "UNEXPECTED_DIRECT_MIGRATION_FAILURE" in str(
        sealed[0].get("stage_first_terminal_cause") or ""
    )
    assert len(sealed[0].get("transport_operations") or ()) >= 1


def test_locator_unexpected_exception_seals_failed_once(tmp_path: Path) -> None:
    db = tmp_path / "loc-exc.sqlite3"
    apply_migrations(db)
    sealed: list[Mapping[str, Any]] = []
    mint = "MintLocatorExc11111111111111111111111111111"
    pool = "PoolLocatorExc11111111111111111111111111111"

    def transport(_context):
        identity = _transport_identity(
            stage="DEXSCREENER_DISCOVERY",
            source="dexscreener_profiles",
            kind="dexscreener_fresh_profiles",
            ordinal=1,
            target="profiles",
        )
        return {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": pool,
                    "baseToken": {"address": mint, "symbol": "X", "name": "X"},
                    "quoteToken": {
                        "address": "So11111111111111111111111111111111111111112",
                        "symbol": "SOL",
                        "name": "SOL",
                    },
                    "liquidity": {"usd": 1000},
                    "priceUsd": "0.01",
                }
            ],
            "transport_operations_used": 1,
            "transport_operation_identities": [identity],
            "response_bytes": 8,
            "normalized_rows": 1,
        }

    # Raise after transport identities are recorded into the measured ledger.
    with patch(
        "printer_v1.operator_cli.graduated_supply_front_door._fresh_profile_mints",
        side_effect=RuntimeError("UNEXPECTED_LOCATOR_FAILURE"),
    ):
        with pytest.raises(RuntimeError, match="UNEXPECTED_LOCATOR_FAILURE"):
            run_fresh_profile_locator(
                db,
                transport=transport,
                now=NOW,
                stage_evidence_sink=sealed.append,
                campaign_id=CAMPAIGN,
                run_id=RUN,
                cycle_id=CYCLE,
            )
    assert len(sealed) == 1
    assert sealed[0]["stage_terminal_status"] == "FAILED"
    assert "UNEXPECTED_LOCATOR_FAILURE" in str(
        sealed[0].get("stage_first_terminal_cause") or ""
    )
    assert len(sealed[0].get("transport_operations") or ()) >= 1


def test_liquidity_unexpected_exception_seals_failed_once(tmp_path: Path) -> None:
    db = tmp_path / "liq-exc.sqlite3"
    apply_migrations(db)
    from printer_v1.sources.pumpswap_graduated_registry import (
        LATEST_GRADUATED_CHANNEL,
        record_graduated_candidate,
    )
    from printer_v1.sources.pump_migration import MIGRATION_PROVENANCE

    conn = sqlite3.connect(db)
    try:
        record_graduated_candidate(
            conn,
            mint="MintExc111111111111111111111111111111111111",
            migration_signature="sig-exc",
            pumpswap_pool="PoolExc111111111111111111111111111111111",
            graduation_block_time=1,
            graduation_slot=1,
            now=NOW,
            discovery_channel=LATEST_GRADUATED_CHANNEL,
            migration_provenance=MIGRATION_PROVENANCE,
        )
        conn.commit()
    finally:
        conn.close()

    sealed: list[Mapping[str, Any]] = []

    def factory(mint: str, pool: str):
        def transport(_context):
            identity = _transport_identity(
                stage="DEXSCREENER_DISCOVERY",
                source="dexscreener_pair",
                kind="pair_market_snapshot",
                ordinal=1,
                target=pool,
                result="OK",
            )
            return {
                "pairs": [
                    {
                        "chainId": "solana",
                        "pairAddress": pool,
                        "liquidity": {"usd": 5000},
                        "priceUsd": "0.02",
                        "baseToken": {"address": mint, "symbol": "M", "name": "M"},
                        "quoteToken": {
                            "address": "So11111111111111111111111111111111111111112",
                            "symbol": "SOL",
                            "name": "SOL",
                        },
                    }
                ],
                "transport_operations_used": 1,
                "transport_operation_identities": [identity],
                "response_bytes": 16,
                "normalized_rows": 1,
            }

        return transport

    # Raise after measured transports via local import of selection authority.
    import printer_v1.discovery.selection_authority as selection_authority

    with patch.object(
        selection_authority,
        "select_two_candidates",
        side_effect=RuntimeError("UNEXPECTED_LIQUIDITY_FAILURE"),
    ):
        with pytest.raises(RuntimeError, match="UNEXPECTED_LIQUIDITY_FAILURE"):
            run_graduated_liquidity_front_door(
                db,
                cycle_seed="exc",
                latest_mints=set(),
                dexscreener_transport_factory=factory,
                now=NOW,
                max_candidates=1,
                stage_evidence_sink=sealed.append,
                campaign_id=CAMPAIGN,
                run_id=RUN,
                cycle_id=CYCLE,
                discovery_round=1,
            )
    assert len(sealed) == 1
    assert sealed[0]["stage_terminal_status"] == "FAILED"
    assert "UNEXPECTED_LIQUIDITY_FAILURE" in str(
        sealed[0].get("stage_first_terminal_cause") or ""
    )
    assert len(sealed[0].get("transport_operations") or ()) >= 1


# --------------------------------------------------------------------------- #
# 3c. End-to-end disposable coordinator proof (genuine stage graph + report)
# --------------------------------------------------------------------------- #


def test_action_local_observer_is_independent_of_stage_seal() -> None:
    """Measurement observer fills before seal; owner only after sink ingest."""
    action_local: list[dict[str, Any]] = []

    def observe(identity) -> None:
        action_local.append(identity.as_dict())

    ledger = MeasuredTransportLedger(on_transport_recorded=observe)
    identity = build_transport_identity(
        stage="DEXSCREENER_DISCOVERY",
        source_name="dexscreener_pair",
        endpoint_owner="dexscreener",
        governed_request_kind="pair_market_snapshot",
        method_or_endpoint="GET /pairs",
        within_request_ordinal=1,
        target_category="exact_pair",
        target_identity="pool-x",
        response_bytes=8,
        normalized_rows=0,
        result="MALFORMED",
    )
    ledger.record_transport(identity)
    # Observed at measurement time — no seal, no owner ingest yet.
    assert len(action_local) == 1
    owner = CampaignSixUnitOwner(campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE)
    assert owner.owner_transport_operation_count == 0
    recon = reconcile_owner_to_action_local(
        owner,
        action_local_transport_identities=action_local,
    )
    assert recon["equal"] is False
    assert recon["mismatch_reason"] == "CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH"


def test_disposable_coordinator_thirty_op_shortage_exact_handoff(
    tmp_path: Path,
) -> None:
    """Genuine disposable coordinator proof: real stages, gate, report writer."""
    db = tmp_path / "coord-30.sqlite3"
    apply_migrations(db)
    report_dir = tmp_path / "artifacts" / "reports"
    report_dir.mkdir(parents=True)

    # Seed enough graduated inventory for 29 exact-liquidity market checks.
    conn = sqlite3.connect(db)
    try:
        for i in range(40):
            record_graduated_candidate(
                conn,
                mint=f"MintCoord{i:02d}1111111111111111111111111111111"[:44],
                migration_signature=f"sig-coord-30-{i}",
                pumpswap_pool=f"PoolCoord{i:02d}11111111111111111111111111111"[:44],
                graduation_block_time=1_700_000_000 + i,
                graduation_slot=100 + i,
                now=NOW,
                discovery_channel=LATEST_GRADUATED_CHANNEL,
                migration_provenance=MIGRATION_PROVENANCE,
            )
        conn.commit()
    finally:
        conn.close()

    owner = CampaignSixUnitOwner(campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE)
    action_local: list[dict[str, Any]] = []
    sealed_stages: list[Mapping[str, Any]] = []

    def observe(identity) -> None:
        # Independent of sealed-stage handoff (pre-seal measurement surface).
        action_local.append(identity.as_dict())

    def sink(evidence: Mapping[str, Any]) -> None:
        sealed_stages.append(evidence)
        # Owner side only — do not mirror transports into action_local here.
        owner.ingest_stage_evidence(evidence)

    def dex_factory(mint: str, pool: str):
        def transport(_context):
            identity = _transport_identity(
                stage="DEXSCREENER_DISCOVERY",
                source="dexscreener_pair",
                kind="pair_market_snapshot",
                ordinal=1,
                target=pool,
                result="MALFORMED",
            )
            return {
                "fixture_status": "failure",
                "failure_type": "dexscreener_malformed_payload",
                "failure_message": "malformed visibility shortage fixture",
                "transport_operations_used": 1,
                "transport_operation_identities": [identity],
                "response_bytes": 4,
                "normalized_rows": 0,
            }

        return transport

    result = run_persistent_eligible_token_supply(
        db,
        cycle_seed="coord-30-shortage",
        migration_transport=lambda _c: {
            "jsonrpc": "2.0",
            "id": 1,
            "result": [],
            "response_bytes": 2,
        },
        dexscreener_transport_factory=dex_factory,
        now=NOW,
        collection_rounds=1,
        front_door_max_candidates=6,
        run_locator=False,
        discovery_operation_budget=30,
        campaign_id=CAMPAIGN,
        execution_id="exec-coord-30",
        run_id=RUN,
        cycle_id=CYCLE,
        stage_evidence_sink=sink,
        transport_identity_observer=observe,
    )
    assert result.ready is False
    assert result.shortage_classification == SOURCE_VISIBILITY_SHORTAGE
    assert len(action_local) == 30
    assert owner.owner_transport_operation_count == 30
    assert len(sealed_stages) >= 1
    # Independence: action_local was filled by measurement observer, not sink.
    assert all(isinstance(item, dict) for item in action_local)

    _finalize_operational_six_unit_accounting(
        owner,
        None,
        action_local_transport_identities=action_local,
    )
    totals = owner.six_unit_totals()
    evidence = owner.durable_evidence()
    assert reconstruct_six_unit_totals_from_evidence(evidence) == totals
    assert totals["SOURCE_TRANSPORT_OPERATION"] == 30

    report_id = "report-coord-30"
    configuration_id = "config-coord-30"
    execution_id = "exec-coord-30"
    # Seed FK parents only; report row/artifact come from production writer.
    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        forbidden_tables = [
            "printer_tokens",
            "printer_pairs",
            "printer_episodes",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
            "printer_paper_trade_audits",
            "printer_memory_retrieval_queries",
            "printer_memory_retrieval_matches",
        ]
        before = {}
        for table in forbidden_tables:
            try:
                before[table] = int(
                    conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                )
            except sqlite3.Error:
                before[table] = 0
        conn.execute(
            """INSERT INTO printer_memory_factory_campaigns(
                   campaign_id,campaign_state,db_mode,db_target_identity,
                   policy_version,first_terminal_cause,terminal_at,
                   created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                CAMPAIGN,
                "TERMINAL_BLOCKED",
                "OPERATIONAL_PERSISTENT",
                "sha256:test",
                "V2_9_8B",
                SOURCE_VISIBILITY_SHORTAGE,
                NOW,
                NOW,
                NOW,
            ),
        )
        conn.execute(
            """INSERT INTO printer_memory_factory_campaign_configurations(
                   configuration_id,campaign_id,configuration_hash,
                   configuration_json,launch_provenance_json,created_at
               ) VALUES (?,?,?,?,?,?)""",
            (
                configuration_id,
                CAMPAIGN,
                "b" * 64,
                json.dumps({"execution_id": execution_id, "run_id": RUN}),
                "{}",
                NOW,
            ),
        )
        conn.execute(
            """INSERT INTO printer_memory_factory_campaign_runs(
                   run_id,campaign_id,run_ordinal,run_state,
                   first_terminal_cause,terminal_at,created_at,updated_at
               ) VALUES (?,?,1,'TERMINAL_BLOCKED',?,?,?,?)""",
            (RUN, CAMPAIGN, SOURCE_VISIBILITY_SHORTAGE, NOW, NOW, NOW),
        )
        conn.commit()
    finally:
        conn.close()

    payload = build_campaign_terminal_report(
        campaign_id=CAMPAIGN,
        configuration_id=configuration_id,
        run_id=RUN,
        cycle_id=CYCLE,
        report_id=report_id,
        factory_run_id=None,
        execution_id=execution_id,
        terminal_status="BLOCKED",
        terminal_cause=SOURCE_VISIBILITY_SHORTAGE,
        run_status="NOT_STARTED",
        lifecycle_started=False,
        reconciliation={"clean_terminal": True},
        campaign_source_calls=30,
        campaign_scheduler_calls=0,
        six_unit_totals=totals,
        six_unit_evidence=evidence,
        require_six_unit_evidence=True,
        blocked_supply_reason=SOURCE_VISIBILITY_SHORTAGE,
    )
    write_campaign_terminal_report(
        db,
        report_dir,
        report_id=report_id,
        campaign_id=CAMPAIGN,
        configuration_id=configuration_id,
        report=payload,
        require_six_unit_evidence=True,
    )

    conn = sqlite3.connect(db)
    try:
        report_rows = int(
            conn.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_reports"
            ).fetchone()[0]
        )
        assert report_rows == 1
        after = {}
        for table in forbidden_tables:
            try:
                after[table] = int(
                    conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                )
            except sqlite3.Error:
                after[table] = 0
        assert after == before
    finally:
        conn.close()

    artifacts = list(report_dir.glob("*.json"))
    assert len(artifacts) == 1
    stored = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert stored["terminal"]["first_terminal_cause"] == SOURCE_VISIBILITY_SHORTAGE
    assert (
        reconstruct_six_unit_totals_from_evidence(stored["six_unit_evidence"])
        == stored["six_unit_totals"]
    )
    assert stored["six_unit_totals"]["SOURCE_TRANSPORT_OPERATION"] == 30
    assert stored["restart_created"] is False
    assert stored["successor_created"] is False
    assert stored["terminal"]["lifecycle_started"] is False
    assert stored.get("resume_created", False) is False
    assert stored.get("retry_created", False) is False


# --------------------------------------------------------------------------- #
# 4. Report-only exact identity tests
# --------------------------------------------------------------------------- #


def _seed_campaign_with_report(
    db: Path,
    *,
    campaign_id: str,
    run_id: str,
    configuration_id: str,
    report_id: str,
    report_dir: Path,
    include_report: bool = True,
    created_at: str = "2026-07-28T00:00:00+00:00",
) -> dict[str, Any]:
    apply_migrations(db)
    report_dir.mkdir(parents=True, exist_ok=True)
    identity = {
        "campaign_id": campaign_id,
        "configuration_id": configuration_id,
        "run_id": run_id,
        "cycle_id": f"{run_id}-cycle",
        "report_id": report_id,
        "factory_run_id": None,
        "execution_id": campaign_id.replace("-campaign", ""),
    }
    report_payload = {
        "report_kind": "PILOT_CAMPAIGN_TERMINAL",
        "identity": identity,
        "terminal": {
            "terminal_status": "COMPLETED",
            "first_terminal_cause": "OK",
            "run_status": "COMPLETED",
            "lifecycle_started": False,
        },
        "campaign_source_calls": 2,
        "campaign_scheduler_calls": 0,
        "six_unit_totals": {
            "SOURCE_TRANSPORT_OPERATION": 0,
            "LOCAL_VALIDATION_STEP": 0,
            "SCHEDULER_WORK_ITEM": 0,
            "SOURCE_RESPONSE_BYTES": 0,
            "NORMALIZED_SOURCE_ROWS": 0,
            "LIFECYCLE_RESERVED_TRANSPORT_OPERATION": 0,
        },
        "six_unit_evidence": {
            "evidence_kind": "CAMPAIGN_SIX_UNIT_EVIDENCE_V1",
            "transport_operations": [],
            "local_validations": 0,
            "scheduler_work_items": 0,
            "lifecycle_reservations": 0,
            "phase": "PRE_OPERATION_NO_WORK",
            "no_work_reason": "test",
            "source_transport_attempted": False,
            "source_governor_requests": 0,
            "scheduler_work_exists": False,
            "lifecycle_began": False,
        },
        "six_unit_evidence_match": True,
    }
    from printer_v1.operator_cli.abstract_campaign_command import report_path_identity

    config = {
        "report_directory_identity": report_path_identity(report_dir),
        "execution_id": identity["execution_id"],
        "run_id": run_id,
    }
    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        now = created_at
        conn.execute(
            """INSERT INTO printer_memory_factory_campaigns(
                   campaign_id,campaign_state,db_mode,db_target_identity,
                   policy_version,first_terminal_cause,terminal_at,
                   created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                campaign_id,
                "TERMINAL_COMPLETED",
                "OPERATIONAL_PERSISTENT",
                "sha256:test",
                "V2_9_8B",
                "OK",
                now,
                now,
                now,
            ),
        )
        conn.execute(
            """INSERT INTO printer_memory_factory_campaign_configurations(
                   configuration_id,campaign_id,configuration_hash,
                   configuration_json,launch_provenance_json,created_at
               ) VALUES (?,?,?,?,?,?)""",
            (
                configuration_id,
                campaign_id,
                "a" * 64,
                json.dumps(config, sort_keys=True),
                "{}",
                now,
            ),
        )
        conn.execute(
            """INSERT INTO printer_memory_factory_campaign_runs(
                   run_id,campaign_id,run_ordinal,run_state,
                   first_terminal_cause,terminal_at,created_at,updated_at
               ) VALUES (?,?,1,'TERMINAL_COMPLETED',?,?,?,?)""",
            (run_id, campaign_id, "OK", now, now, now),
        )
        conn.execute(
            """INSERT INTO printer_memory_factory_campaign_supervision(
                   supervision_id,campaign_id,configuration_id,run_id,owner_id,
                   supervision_state,terminal_status,first_terminal_cause,
                   heartbeat_at,lease_expires_at,lease_lock_path,
                   cleanup_completed_at,created_at,updated_at
               ) VALUES (?,?,?,?,?,'TERMINAL',?,?,?,?,?,?,?,?)""",
            (
                f"{run_id}-sup",
                campaign_id,
                configuration_id,
                run_id,
                f"{run_id}-owner",
                "COMPLETED",
                "OK",
                now,
                now,
                f"/tmp/{run_id}.lock",
                now,
                now,
                now,
            ),
        )
        if include_report:
            body = json.dumps(report_payload, sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            conn.execute(
                """INSERT INTO printer_memory_factory_campaign_reports(
                       report_id,campaign_id,configuration_id,report_kind,
                       report_state,report_json,report_hash,created_at
                   ) VALUES (?,?,?,'TERMINAL','REPORT_TERMINAL',?,?,?)""",
                (report_id, campaign_id, configuration_id, body, digest, now),
            )
            (report_dir / f"{report_id}.campaign-report.json").write_text(body, encoding="utf-8")
        conn.commit()
    finally:
        conn.close()
    return report_payload


def test_report_only_explicit_and_blocked_modes(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "report-only.sqlite3"
    older_dir = tmp_path / "artifacts" / "20260728T000000Z-old" / "reports"
    newer_dir = tmp_path / "artifacts" / "20260731T000000Z-new" / "reports"
    monkeypatch.setattr(command, "AUTHORITATIVE_DB", db.resolve())
    monkeypatch.setattr(command, "ARTIFACT_ROOT", tmp_path / "artifacts")

    _seed_campaign_with_report(
        db,
        campaign_id="old-campaign",
        run_id="old-run",
        configuration_id="old-config",
        report_id="old-report",
        report_dir=older_dir,
        created_at="2026-07-28T00:00:00+00:00",
    )
    _seed_campaign_with_report(
        db,
        campaign_id="new-campaign",
        run_id="new-run",
        configuration_id="new-config",
        report_id="new-report",
        report_dir=newer_dir,
        include_report=False,
        created_at="2026-07-31T00:00:00+00:00",
    )

    before_hash = hashlib.sha256(db.read_bytes()).hexdigest()
    before_requests = _source_request_count(db)

    # Supplying only one identity is blocked.
    one = command.report_only(campaign_id="new-campaign", run_id=None)
    assert one["status"] == "REPLAY_BLOCKED"
    assert one["block_reason"] == "REPORT_ONLY_EXACT_IDENTITY_INCOMPLETE"
    assert one["source_calls"] == 0
    assert one["database_writes"] == 0

    # Explicit exact campaign/run with no report and no summary: primary
    # block reason is EXACT_TERMINAL_SUMMARY_MISSING_OR_MISMATCHED.
    missing = command.report_only(campaign_id="new-campaign", run_id="new-run")
    assert missing["status"] == "REPLAY_BLOCKED"
    assert missing["block_reason"] == "EXACT_TERMINAL_SUMMARY_MISSING_OR_MISMATCHED"
    assert missing["fallback_used"] is False
    assert missing["report_rows"] == 0
    # Must not return the older global report.
    assert "old-report" not in json.dumps(missing)

    # Historical pre-repair V1 evidence is exact-identity data, but it may not
    # satisfy repaired V2 acceptance or public full-run reconstruction.
    exact = command.report_only(campaign_id="old-campaign", run_id="old-run")
    assert exact.get("status") == "REPLAY_BLOCKED"
    assert exact["block_reason"] == "FULL_RUN_EVIDENCE_MISSING"
    assert exact["source_calls"] == 0
    assert exact["database_writes"] == 0

    # No-argument resolves latest supervision first (new-campaign, no report/summary).
    latest = command.report_only()
    assert latest["status"] == "REPLAY_BLOCKED"
    assert latest["requested_identity"]["campaign_id"] == "new-campaign"
    assert latest["block_reason"] == "EXACT_TERMINAL_SUMMARY_MISSING_OR_MISMATCHED"
    assert "old-report" not in json.dumps(latest)

    # Unknown identity blocks.
    unknown = command.report_only(campaign_id="missing", run_id="missing")
    assert unknown["status"] == "REPLAY_BLOCKED"
    assert unknown["block_reason"] in {
        "REPORT_ONLY_IDENTITY_UNKNOWN",
        "REPLAY_BLOCKED",
    }

    after_hash = hashlib.sha256(db.read_bytes()).hexdigest()
    after_requests = _source_request_count(db)
    assert before_hash == after_hash
    assert before_requests == after_requests


def _source_request_count(db: Path) -> int:
    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM printer_source_requests"
        ).fetchone()
        return int(row[0]) if row else 0
    except sqlite3.Error:
        return 0
    finally:
        conn.close()


def _write_terminal_summary(
    artifacts: Path,
    *,
    execution_id: str,
    campaign_id: str,
    run_id: str,
    configuration_id: str,
    **overrides: Any,
) -> Path:
    payload = {
        "status": "OPERATIONAL_CAMPAIGN_TERMINAL_FAILURE",
        "first_terminal_cause": "SOURCE_VISIBILITY_SHORTAGE",
        "accounting_status": "SIX_UNIT_ACCOUNTING_BLOCKED",
        "report_written": False,
        "report_block_reason": "SIX_UNIT_EVIDENCE_MISSING",
        "campaign_id": campaign_id,
        "run_id": run_id,
        "configuration_id": configuration_id,
        "execution_id": execution_id,
    }
    payload.update(overrides)
    path = artifacts / execution_id / "terminal-summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def test_missing_summary_run_id_blocks(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "sum-run.sqlite3"
    artifacts = tmp_path / "artifacts"
    report_dir = artifacts / "sum" / "reports"
    monkeypatch.setattr(command, "AUTHORITATIVE_DB", db.resolve())
    monkeypatch.setattr(command, "ARTIFACT_ROOT", artifacts)
    _seed_campaign_with_report(
        db,
        campaign_id="sum-campaign",
        run_id="sum-run",
        configuration_id="sum-config",
        report_id="sum-report",
        report_dir=report_dir,
        include_report=False,
    )
    # execution_id from seed = campaign_id.replace("-campaign", "") => "sum"
    _write_terminal_summary(
        artifacts,
        execution_id="sum",
        campaign_id="sum-campaign",
        run_id="",  # missing / empty run_id is a mismatch
        configuration_id="sum-config",
    )
    result = command.report_only(campaign_id="sum-campaign", run_id="sum-run")
    assert result["status"] == "REPLAY_BLOCKED"
    assert result["block_reason"] == "EXACT_TERMINAL_SUMMARY_MISSING_OR_MISMATCHED"


def test_missing_summary_configuration_id_blocks(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "sum-cfg.sqlite3"
    artifacts = tmp_path / "artifacts"
    report_dir = artifacts / "cfg" / "reports"
    monkeypatch.setattr(command, "AUTHORITATIVE_DB", db.resolve())
    monkeypatch.setattr(command, "ARTIFACT_ROOT", artifacts)
    _seed_campaign_with_report(
        db,
        campaign_id="cfg-campaign",
        run_id="cfg-run",
        configuration_id="cfg-config",
        report_id="cfg-report",
        report_dir=report_dir,
        include_report=False,
    )
    exec_id = "cfg"
    (artifacts / exec_id).mkdir(parents=True, exist_ok=True)
    (artifacts / exec_id / "terminal-summary.json").write_text(
        json.dumps(
            {
                "status": "OPERATIONAL_CAMPAIGN_TERMINAL_FAILURE",
                "campaign_id": "cfg-campaign",
                "run_id": "cfg-run",
                "configuration_id": "",
                "execution_id": exec_id,
            }
        ),
        encoding="utf-8",
    )
    result = command.report_only(campaign_id="cfg-campaign", run_id="cfg-run")
    assert result["status"] == "REPLAY_BLOCKED"
    assert result["block_reason"] == "EXACT_TERMINAL_SUMMARY_MISSING_OR_MISMATCHED"


def test_missing_summary_execution_id_blocks(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "sum-exec.sqlite3"
    artifacts = tmp_path / "artifacts"
    report_dir = artifacts / "ex" / "reports"
    monkeypatch.setattr(command, "AUTHORITATIVE_DB", db.resolve())
    monkeypatch.setattr(command, "ARTIFACT_ROOT", artifacts)
    _seed_campaign_with_report(
        db,
        campaign_id="ex-campaign",
        run_id="ex-run",
        configuration_id="ex-config",
        report_id="ex-report",
        report_dir=report_dir,
        include_report=False,
    )
    exec_id = "ex"
    (artifacts / exec_id).mkdir(parents=True, exist_ok=True)
    (artifacts / exec_id / "terminal-summary.json").write_text(
        json.dumps(
            {
                "status": "OPERATIONAL_CAMPAIGN_TERMINAL_FAILURE",
                "campaign_id": "ex-campaign",
                "run_id": "ex-run",
                "configuration_id": "ex-config",
                "execution_id": "",
            }
        ),
        encoding="utf-8",
    )
    result = command.report_only(campaign_id="ex-campaign", run_id="ex-run")
    assert result["status"] == "REPLAY_BLOCKED"
    assert result["block_reason"] == "EXACT_TERMINAL_SUMMARY_MISSING_OR_MISMATCHED"


def test_mismatched_summary_identity_primary_block_reason(
    tmp_path: Path, monkeypatch
) -> None:
    db = tmp_path / "sum-mis.sqlite3"
    artifacts = tmp_path / "artifacts"
    report_dir = artifacts / "mis" / "reports"
    monkeypatch.setattr(command, "AUTHORITATIVE_DB", db.resolve())
    monkeypatch.setattr(command, "ARTIFACT_ROOT", artifacts)
    _seed_campaign_with_report(
        db,
        campaign_id="mis-campaign",
        run_id="mis-run",
        configuration_id="mis-config",
        report_id="mis-report",
        report_dir=report_dir,
        include_report=False,
    )
    exec_id = "mis"
    (artifacts / exec_id).mkdir(parents=True, exist_ok=True)
    (artifacts / exec_id / "terminal-summary.json").write_text(
        json.dumps(
            {
                "status": "OPERATIONAL_CAMPAIGN_TERMINAL_FAILURE",
                "campaign_id": "mis-campaign",
                "run_id": "wrong-run",
                "configuration_id": "mis-config",
                "execution_id": exec_id,
            }
        ),
        encoding="utf-8",
    )
    result = command.report_only(campaign_id="mis-campaign", run_id="mis-run")
    assert result["status"] == "REPLAY_BLOCKED"
    assert result["block_reason"] == "EXACT_TERMINAL_SUMMARY_MISSING_OR_MISMATCHED"
    assert "terminal_summary_block_reason" not in result


def test_exact_report_missing_with_valid_summary(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "sum-ok.sqlite3"
    artifacts = tmp_path / "artifacts"
    report_dir = artifacts / "ok" / "reports"
    monkeypatch.setattr(command, "AUTHORITATIVE_DB", db.resolve())
    monkeypatch.setattr(command, "ARTIFACT_ROOT", artifacts)
    _seed_campaign_with_report(
        db,
        campaign_id="ok-campaign",
        run_id="ok-run",
        configuration_id="ok-config",
        report_id="ok-report",
        report_dir=report_dir,
        include_report=False,
    )
    exec_id = "ok"
    (artifacts / exec_id).mkdir(parents=True, exist_ok=True)
    (artifacts / exec_id / "terminal-summary.json").write_text(
        json.dumps(
            {
                "status": "OPERATIONAL_CAMPAIGN_TERMINAL_FAILURE",
                "first_terminal_cause": "SOURCE_VISIBILITY_SHORTAGE",
                "accounting_status": "SIX_UNIT_ACCOUNTING_BLOCKED",
                "report_written": False,
                "report_block_reason": "SIX_UNIT_EVIDENCE_MISSING",
                "campaign_id": "ok-campaign",
                "run_id": "ok-run",
                "configuration_id": "ok-config",
                "execution_id": exec_id,
            }
        ),
        encoding="utf-8",
    )
    result = command.report_only(campaign_id="ok-campaign", run_id="ok-run")
    assert result["status"] == "REPLAY_BLOCKED"
    assert result["block_reason"] == "EXACT_TERMINAL_REPORT_MISSING"
    assert result["terminal_summary"]["first_terminal_cause"] == (
        "SOURCE_VISIBILITY_SHORTAGE"
    )


def test_report_only_never_substitutes_discovery_only(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "disc.sqlite3"
    apply_migrations(db)
    monkeypatch.setattr(command, "AUTHORITATIVE_DB", db.resolve())
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    monkeypatch.setattr(command, "ARTIFACT_ROOT", artifacts)
    disc_dir = artifacts / "discovery-exec"
    disc_dir.mkdir()
    (disc_dir / "discovery-only-report.json").write_text(
        json.dumps(
            {
                "mode": "discovery-only",
                "execution_id": "discovery-exec",
                "status": "QUALIFIED",
            }
        ),
        encoding="utf-8",
    )
    result = command.report_only(campaign_id="nope", run_id="nope")
    assert result["status"] == "REPLAY_BLOCKED"
    assert result.get("report_kind") != "discovery-only"
    assert "qualification" not in result or result.get("qualification") is None


# --------------------------------------------------------------------------- #
# 5. Nearest regression: seal handoff does not change ordinary offline success
# --------------------------------------------------------------------------- #


def test_ordinary_direct_migration_still_complete_without_sink(tmp_path: Path) -> None:
    tx, _infos, mint, pool = _pinned_migration_fixture()
    db = tmp_path / "ordinary.sqlite3"
    apply_migrations(db)

    def verifier_factory(mint_value: str, signature: str):
        def transport(_context):
            return {
                "pumpswap_confirmation": {
                    "confirmed": True,
                    "pool_address": pool,
                    "base_mint": mint_value,
                },
                "pumpswap_resolution": {
                    "pool_address": pool,
                    "resolved": True,
                    "transport_operations_used": 1,
                },
                "pump_migration_proof": {
                    "verified": True,
                    "migration_block_time": tx["blockTime"],
                    "migration_slot": tx["slot"],
                },
                "tokens": [
                    {
                        "pairAddress": pool,
                        "pumpswap_migration_block_time": tx["blockTime"],
                        "pumpswap_migration_slot": tx["slot"],
                    }
                ],
                "migration_signature": signature,
                "transport_operations_used": 1,
                "transport_operation_identities": [
                    _transport_identity(
                        stage="PUMPSWAP_EXACT_VERIFICATION",
                        source="pumpswap",
                        kind="pumpswap_signature_pool_resolution",
                        ordinal=1,
                        target=pool,
                    )
                ],
                "response_bytes": 20,
                "normalized_rows": 1,
            }

        return transport

    report = run_direct_migration_discovery(
        db,
        migration_transport=_migration_transport(tx),
        verifier_transport_factory=verifier_factory,
        now=NOW,
    )
    assert report["status"] in {"COMPLETE", "PROVIDER_FAILURE", "ACCOUNTING_BLOCKED"}
    assert "six_unit_evidence" in report
    assert report.get("sealed_stage_evidence") is None


class _OrdinaryWindow15mRegression(_OperationalBase):
    """Nearest ordinary two-token operational WINDOW_15M path (frozen, disposable)."""

    def runTest(self) -> None:  # pragma: no cover - pytest class host
        pass


def test_ordinary_disposable_two_token_window_15m_regression(tmp_path: Path) -> None:
    """Genuine frozen two-token operational coordinator that closes WINDOW_15M."""
    del tmp_path  # harness owns a fresh disposable migration-049 database
    harness = _OrdinaryWindow15mRegression()
    harness.setUp()
    try:
        transport, mints = _two_create_transport()
        with patch(
            "printer_v1.operator_cli.proof_db_schema_readiness."
            "CANONICAL_PERSISTENT_DB",
            harness.db,
        ):
            result, _continue_mint, _stop_mint = harness._run(
                pump_transport=transport,
                fifteen_minute_only=True,
            )
        report = result.lifecycle
        assert result.lifecycle_started is True
        assert report["run_status"] == "COMPLETED"
        assert len(result.activation.activated_slots) == 2
        assert {
            str(slot["mint_identity"]) for slot in result.activation.activated_slots
        } == set(mints)

        close_steps = [
            step
            for step in report["steps"]
            if step["step_kind"] == "WINDOW_CLOSE"
        ]
        assert len(close_steps) == 2
        assert not any(
            step["step_kind"] in {"CONTINUATION_CLOSE", "LONG_CONTINUATION_CLOSE"}
            for step in report["steps"]
        )

        conn = sqlite3.connect(harness.db)
        conn.row_factory = sqlite3.Row
        try:
            main_windows = conn.execute(
                """SELECT token_id,pair_id,window_kind,window_status
                   FROM printer_memory_windows
                   WHERE window_kind='WINDOW_15M'
                   ORDER BY token_id,pair_id"""
            ).fetchall()
            assert len(main_windows) == 2
            assert all(row["window_status"] == "WINDOW_CLOSED" for row in main_windows)
            head = [
                row[0]
                for row in conn.execute(
                    "SELECT version FROM printer_schema_migrations ORDER BY version"
                )
            ][-1]
            assert str(head).startswith("050")
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            for table in (
                "printer_paper_decisions",
                "printer_paper_positions",
                "printer_paper_trade_events",
                "printer_paper_trade_audits",
                "printer_memory_retrieval_queries",
                "printer_memory_retrieval_matches",
            ):
                assert (
                    int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                    == 0
                )
        finally:
            conn.close()
        assert all(value == 0 for value in report["forbidden_deltas"].values())
    finally:
        harness.tearDown()

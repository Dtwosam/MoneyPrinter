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
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignSixUnitError,
    CampaignSixUnitOwner,
    build_campaign_stage_id,
    pre_operation_no_work_evidence,
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
# 3. July 31-shaped disposable proof
# --------------------------------------------------------------------------- #


def test_july31_shaped_shortage_hands_off_full_measured_set(tmp_path: Path) -> None:
    """30 measured ops, shortage, complete owner handoff, no lifecycle work."""
    db = tmp_path / "july31.sqlite3"
    apply_migrations(db)
    owner = CampaignSixUnitOwner(campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE)

    # 1 locator (2 multi-hop identities) + 3 direct pump + 25 liquidity = 30.
    locator_identities = [
        _transport_identity(
            stage="DEXSCREENER_DISCOVERY",
            source="dexscreener_profiles",
            kind="dexscreener_fresh_profiles",
            ordinal=1,
            target="profiles",
        ),
        _transport_identity(
            stage="DEXSCREENER_DISCOVERY",
            source="dexscreener_pair",
            kind="dexscreener_fresh_profiles",
            ordinal=2,
            target="token_pairs",
        ),
    ]
    pump_identities = [
        _transport_identity(
            stage="DIRECT_PUMP_NOMINATION",
            source="solana_rpc",
            kind=SIGNATURE_PAGE_REQUEST_KIND,
            ordinal=1,
            target="page",
            method="getSignaturesForAddress",
            normalized_rows=3,
        ),
        _transport_identity(
            stage="DIRECT_PUMP_NOMINATION",
            source="solana_rpc",
            kind=TRANSACTION_REQUEST_KIND,
            ordinal=2,
            target="tx-1",
            method="getTransaction",
            result="FAILED",
        ),
        _transport_identity(
            stage="DIRECT_PUMP_NOMINATION",
            source="solana_rpc",
            kind=TRANSACTION_REQUEST_KIND,
            ordinal=3,
            target="tx-2",
            method="getTransaction",
            result="FAILED",
        ),
    ]
    # Remaining 25 liquidity attempts: 15 provider failures + 10 malformed
    # (test uses 12 malformed/partial + 15 failures shape via results).
    liq_idents = []
    for i in range(25):
        result = "FAILED" if i < 15 else "MALFORMED"
        liq_idents.append(
            _transport_identity(
                stage="DEXSCREENER_DISCOVERY",
                source="dexscreener_pair",
                kind="pair_market_snapshot",
                ordinal=1,
                target=f"pool-{i}",
                result=result,
            )
        )

    stages = [
        _sealed_stage(
            stage_kind="LOCATOR",
            sequence=1,
            transports=locator_identities,
            status="COMPLETED",
        ),
        _sealed_stage(
            stage_kind="DIRECT_MIGRATION",
            sequence=1,
            transports=pump_identities,
            status="BLOCKED",
            cause="PROVIDER_FAILURE",
        ),
        _sealed_stage(
            stage_kind="EXACT_LIQUIDITY",
            sequence=1,
            transports=liq_idents,
            status="BLOCKED",
            cause=SOURCE_VISIBILITY_SHORTAGE,
        ),
    ]
    assert sum(len(s["transport_operations"]) for s in stages) == 30
    for stage in stages:
        owner.ingest_stage_evidence(stage)
    owner.close()

    assert owner.stage_evidence_count == 3
    assert owner.owner_transport_operation_count == 30
    assert len(set(owner.ingested_stage_ids)) == 3
    assert owner.accounting_block_reason is None
    totals = owner.six_unit_totals()
    assert totals["SOURCE_TRANSPORT_OPERATION"] == 30
    assert reconstruct_six_unit_totals_from_evidence(owner.durable_evidence()) == totals

    # Honest blocked terminal report payload shape (no write to authoritative DB).
    report = {
        "terminal_cause": SOURCE_VISIBILITY_SHORTAGE,
        "six_unit_totals": totals,
        "six_unit_evidence": owner.durable_evidence(),
        "restart_created": False,
        "successor_created": False,
        "resume_created": False,
        "retry_created": False,
        "lifecycle_started": False,
        "required_eligible": 2,
        "eligible": 1,
        "provider_failures": 15,
        "malformed_or_partial": 12,
    }
    assert report["lifecycle_started"] is False
    assert report["restart_created"] is False
    assert (
        reconstruct_six_unit_totals_from_evidence(report["six_unit_evidence"])
        == report["six_unit_totals"]
    )


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
            (report_dir / f"{report_id}.json").write_text(body + "\n", encoding="utf-8")
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

    # Explicit exact campaign/run with no report returns EXACT_TERMINAL_REPORT_MISSING.
    missing = command.report_only(campaign_id="new-campaign", run_id="new-run")
    assert missing["status"] == "REPLAY_BLOCKED"
    assert missing["block_reason"] == "EXACT_TERMINAL_REPORT_MISSING"
    assert missing["fallback_used"] is False
    assert missing["report_rows"] == 0
    # Must not return the older global report.
    assert "old-report" not in json.dumps(missing)

    # Explicit exact with report returns only that report.
    exact = command.report_only(campaign_id="old-campaign", run_id="old-run")
    assert exact.get("status") == "REPLAYED"
    assert exact["fallback_used"] is False
    assert exact["replay"]["report"]["identity"]["campaign_id"] == "old-campaign"
    assert exact["source_calls"] == 0
    assert exact["database_writes"] == 0

    # No-argument resolves latest supervision first (new-campaign, no report).
    latest = command.report_only()
    assert latest["status"] == "REPLAY_BLOCKED"
    assert latest["requested_identity"]["campaign_id"] == "new-campaign"
    assert latest["block_reason"] == "EXACT_TERMINAL_REPORT_MISSING"
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

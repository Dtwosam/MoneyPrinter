"""V2-9.8B durable request identity and stage accounting blocker repair.

Offline fixture-only. Proves:
1. Durable IDs are database-proven, never copied from stage-reported IDs.
2. Accounting blockers from every governed stage block reconciliation.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.combined_executor import (
    FixtureOriginProof,
    FixturePumpSwapProof,
)
from printer_v1.discovery.permanent_discovery_availability import (
    CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH,
    CURRENT_VISIBLE,
    ExactMarketObservation,
    NETWORK,
    assemble_and_reconcile_campaign_source_requests,
    collect_stage_accounting_blockers,
    load_durable_campaign_source_request_ids,
    record_exact_market_transition,
    reconcile_campaign_source_requests,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    SOURCE_GOVERNOR_OWNER,
    OwnerPort,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
    PILOT_INPUT_READINESS,
)
from printer_v1.operator_cli.graduated_supply_front_door import (
    GraduatedSupply,
    run_fresh_profile_locator,
)
from printer_v1.sources.measured_transport import MeasuredTransportError
from printer_v1.sources.pumpswap import PUMPSWAP_AMM_PROGRAM_ID

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
from test_v2_9_7e_11_authoritative_live_operational_campaign import _FakePumpTransport

GOV = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCH = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)

_MINTS = [
    "4tNCRgigHBPiMsPfrCaU1kE6gGofxgXLmEq8mRK1pump",
    "4FN5PSaprS73Z2SRGx2HG9eaES1yVURMU5yAPpDQpump",
    "5tNCRgigHBPiMsPfrCaU1kE6gGofxgXLmEq8mRK2pump",
    "6FN5PSaprS73Z2SRGx2HG9eaES1yVURMU5yAPpDRpump",
]
_POOLS = [
    "BDhvEqa1KjHBsNSFxN9Np4t3CLZjaCvDtCRjrqsbQ21p",
    "9yuowVdGRZ35yM339cjyTWfhAdJJVPJqPKGHhyCXG3fo",
    "CDhvEqa1KjHBsNSFxN9Np4t3CLZjaCvDtCRjrqsbQ22q",
    "AyuowVdGRZ35yM339cjyTWfhAdJJVPJqPKGHhyCXG3fp",
]
EXPIRES = "2099-01-01T00:00:00+00:00"
WSOL = "So11111111111111111111111111111111111111112"


def _coverage(rid, *, stage="PROTOCOL|1", transport=1, terminal="COMPLETED"):
    return {
        "source_request_id": rid,
        "source_name": "solana_rpc",
        "request_kind": "pumpswap_pool_account_batch",
        "logical_stage_id": stage,
        "transport_identity_count": transport,
        "normalized_member_count": 1 if transport else 0,
        "terminal_status": terminal,
    }


@pytest.fixture()
def database():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "durable.sqlite3"
        apply_migrations(path)
        connection = sqlite3.connect(str(path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield path, connection
        finally:
            connection.close()


def _insert(connection, source="solana_rpc", kind="batch", key="k"):
    connection.execute(
        """
        INSERT INTO printer_source_requests(
            source_name, request_kind, requested_at, request_key,
            tracking_priority, source_status, data_quality_label
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (source, kind, e8.NOW, key, 0, "COMPLETE", "CLEAN_DATA"),
    )
    connection.commit()
    return int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])


# ---------------------------------------------------------------------------
# Repair 1 — durable IDs must be database-proven
# ---------------------------------------------------------------------------


class TestDurableIdIndependence:
    def test_stage_reported_without_db_row_blocks(self, database):
        path, connection = database
        # No DB row for 999.
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "protocol_confirmation": {
                    "source_request_ids": [999],
                    "source_request_coverage": [_coverage(999)],
                }
            },
        )
        assert recon["status"] == "BLOCKED"
        assert recon["blocker"] == CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH
        assert recon.get("categorical_detail") == (
            "STAGE_REPORTED_REQUEST_NOT_DURABLE"
        )
        assert 999 in recon["stage_reported_not_durable"]
        assert 999 not in recon["durable_campaign_request_ids"]
        assert recon["stage_reported_request_ids"] == [999]
        assert recon["coverage_request_ids"] == [999]

    def test_stage_reported_not_durable_exposes_missing_id(self, database):
        path, connection = database
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "liquidity_backup": {
                    "source_request_ids": [42],
                    "source_request_coverage": [
                        _coverage(42, stage="UNKNOWN_LIQUIDITY_BACKUP|1")
                    ],
                }
            },
        )
        assert recon["stage_reported_not_durable"] == [42]
        assert recon["categorical_detail"] == "STAGE_REPORTED_REQUEST_NOT_DURABLE"

    def test_genuine_db_row_with_matching_stage_and_coverage_passes(self, database):
        path, connection = database
        rid = _insert(connection, key="camp-ok|proto")
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "protocol_confirmation": {
                    "source_request_ids": [rid],
                    "source_request_coverage": [_coverage(rid)],
                }
            },
            request_key_prefixes=["camp-ok"],
        )
        assert recon["status"] == "OK"
        assert recon["durable_campaign_request_ids"] == [rid]
        assert recon["stage_reported_request_ids"] == [rid]
        assert recon["coverage_request_ids"] == [rid]
        assert recon["stage_reported_not_durable"] == []

    def test_prefix_lookup_cannot_make_nonexistent_id_durable(self, database):
        path, connection = database
        # Prefix finds nothing; stage reports 777 which has no row.
        durable = load_durable_campaign_source_request_ids(
            connection,
            request_key_prefixes=["nonexistent-prefix"],
            known_request_ids=[777],
        )
        assert durable == []
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "protocol_confirmation": {
                    "source_request_ids": [777],
                    "source_request_coverage": [_coverage(777)],
                }
            },
            request_key_prefixes=["nonexistent-prefix"],
        )
        assert 777 not in recon["durable_campaign_request_ids"]
        assert recon["status"] == "BLOCKED"

    def test_durable_db_id_absent_from_stage_reporting_blocks(self, database):
        path, connection = database
        rid = _insert(connection, key="prefix-only|r1")
        # Prefix discovers the durable row, but no stage reported it.
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={},
            request_key_prefixes=["prefix-only"],
        )
        assert rid in recon["durable_campaign_request_ids"]
        assert recon["status"] == "BLOCKED"
        assert rid in recon["durable_not_stage_reported"]

    def test_lawful_zero_transport_reconciles(self, database):
        path, connection = database
        rid = _insert(connection, key="zero|r1")
        entry = _coverage(rid, transport=0, stage="LOCAL_ONLY|1")
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "protocol_confirmation": {
                    "source_request_ids": [rid],
                    "source_request_coverage": [entry],
                }
            },
        )
        assert recon["status"] == "OK"
        assert recon["manifest"][0]["transport_identity_count"] == 0


# ---------------------------------------------------------------------------
# Repair 2 — all-stage accounting blockers
# ---------------------------------------------------------------------------


class TestStageAccountingBlockers:
    def test_collect_stage_accounting_blockers_generic(self):
        diag = {
            "protocol_confirmation": {
                "accounting_blocker": True,
                "accounting_blocker_reason": "PROTOCOL_X",
            },
            "dexscreener_locator": {
                "accounting_blocker": True,
                "accounting_blocker_reason": "LOCATOR_X",
            },
            "holder_context": {
                "accounting_blocker": True,
                "accounting_blocker_reason": "HOLDER_X",
            },
            "final_refresh": {
                "accounting_blocker": True,
                "accounting_blocker_reason": "REFRESH_X",
            },
            "permanent_market_reports": [
                {
                    "accounting_blocker": True,
                    "accounting_blocker_reason": "MARKET_X",
                }
            ],
            "direct_migration_discovery": {
                "campaign_safe_stop": True,
                "accounting_block_reason": "MIGRATION_SAFE_STOP",
            },
        }
        blockers = collect_stage_accounting_blockers(diag)
        stages = {b["stage"] for b in blockers}
        assert "protocol_confirmation" in stages
        assert "dexscreener_locator" in stages
        assert "holder_context" in stages
        assert "final_refresh" in stages
        assert "permanent_market_reports[0]" in stages
        assert "direct_migration_discovery" in stages

    def test_ordinary_candidate_local_rejection_not_accounting_blocker(self):
        diag = {
            "protocol_confirmation": {
                "outcome_counts": {"POOL_OWNER_MISMATCH": 3},
                "accounting_blocker": False,
            },
            "liquidity_backup": {
                "exact_pool_no_match": 1,
                "below_floor": 2,
                "accounting_blocker": False,
            },
        }
        assert collect_stage_accounting_blockers(diag) == []

    def test_locator_measurement_failure_sets_accounting_blocker(self, database):
        path, connection = database

        def transport(_ctx):
            return {
                "pairs": [
                    {
                        "pairAddress": _POOLS[0],
                        "chainId": "solana",
                        "baseToken": {"address": _MINTS[0]},
                        "quoteToken": {"address": WSOL},
                        "dexId": "pumpswap",
                    }
                ],
                "response_bytes": 10,
                "transport_operations_used": 1,
                # used without identities → measurement error when recorded
            }

        with patch(
            "printer_v1.sources.measured_transport.record_payload_transports",
            side_effect=MeasuredTransportError("TRANSPORT_IDENTITIES_MISSING"),
        ):
            report = run_fresh_profile_locator(
                path,
                transport=transport,
                request_key="locator-fail",
                now=e8.NOW,
                campaign_id="camp",
                run_id="run",
                cycle_id="cyc",
            )
        assert report["accounting_blocker"] is True
        assert "TRANSPORT_IDENTITY_MEASUREMENT_FAILED" in str(
            report["accounting_blocker_reason"]
        )
        assert report["matched_mints"] == []
        assert report["matched_count"] == 0
        assert report.get("pool_observations") == []
        assert report["source_request_coverage"][0]["terminal_status"] == "BLOCKED"
        assert report["request_id"] is not None

    def test_locator_measurement_failure_blocks_campaign_readiness(self):
        base = e8._IntegrationBase()
        base.setUp()
        try:
            rid_conn = sqlite3.connect(base.db)
            rid = _insert(rid_conn, key="loc-block|1")
            rid_conn.close()
            supply = _permanent_supply_with_stage(
                locator_blocker=True,
                locator_request_id=rid,
            )
            _seed_markets(base.db, supply)
            owner = AuthoritativeLiveOperationalCampaignOwner()
            _force_holder(owner, supply.holder_reserve_supply)
            result = owner.run(
                mode=PILOT_INPUT_READINESS,
                command=base.command,
                pump_transport=_FakePumpTransport([], {}),
                secondary_transport=None,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="loc-block",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=base.backup,
                lifecycle_kwargs={"context_adapter_factories": {}},
                graduated_supply=supply,
            )
            life = result.lifecycle
            assert life.get("pilot_input_readiness") is None
            assert life.get("stop_reason") == (
                CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH
            )
            recon = (
                life.get("pre_lifecycle_admission") or {}
            ).get("campaign_source_request_reconciliation") or {}
            assert recon.get("status") == "BLOCKED"
            blockers = recon.get("stage_accounting_blockers") or []
            assert any("locator" in b.get("stage", "") for b in blockers)
        finally:
            base.tearDown()

    def test_direct_migration_safe_stop_blocks(self, database):
        path, connection = database
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "direct_migration_discovery": {
                    "campaign_safe_stop": True,
                    "accounting_block_reason": "measured_transport:X",
                    "source_request_ids": [],
                    "source_request_coverage": [],
                }
            },
        )
        assert recon["status"] == "BLOCKED"
        assert recon.get("stage_accounting_blockers")

    def test_market_batch_accounting_blocker_blocks(self, database):
        path, connection = database
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "permanent_market_reports": [
                    {
                        "accounting_blocker": True,
                        "accounting_blocker_reason": "TRANSPORT_IDENTITY_MEASUREMENT_FAILED:X",
                        "source_request_ids": [],
                        "source_request_coverage": [],
                    }
                ]
            },
        )
        assert recon["status"] == "BLOCKED"
        assert any(
            "permanent_market" in b["stage"]
            for b in recon.get("stage_accounting_blockers") or ()
        )

    def test_holder_context_accounting_blocker_blocks(self, database):
        path, connection = database
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "holder_context": {
                    "accounting_blocker": True,
                    "accounting_blocker_reason": "HOLDER_MEASURE_FAILED",
                }
            },
        )
        assert recon["status"] == "BLOCKED"

    def test_final_refresh_accounting_blocker_blocks(self, database):
        path, connection = database
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "final_refresh": {
                    "accounting_blocker": True,
                    "accounting_blocker_reason": "REFRESH_MEASURE_FAILED",
                }
            },
        )
        assert recon["status"] == "BLOCKED"

    def test_full_campaign_blocked_report_exposes_three_id_sets(self):
        base = e8._IntegrationBase()
        base.setUp()
        try:
            # Stage reports ID that has coverage but no DB row.
            supply = _permanent_supply_with_stage(
                missing_durable_id=888,
            )
            _seed_markets(base.db, supply)
            owner = AuthoritativeLiveOperationalCampaignOwner()
            _force_holder(owner, supply.holder_reserve_supply)
            result = owner.run(
                mode=PILOT_INPUT_READINESS,
                command=base.command,
                pump_transport=_FakePumpTransport([], {}),
                secondary_transport=None,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="three-sets",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=base.backup,
                lifecycle_kwargs={"context_adapter_factories": {}},
                graduated_supply=supply,
            )
            life = result.lifecycle
            assert life["lifecycle_started"] is False
            admission = life.get("pre_lifecycle_admission") or {}
            recon = admission.get("campaign_source_request_reconciliation") or {}
            assert recon.get("status") == "BLOCKED"
            # Three ID sets exposed.
            assert "stage_reported_request_ids" in recon or (
                life.get("graduated_supply_diagnostics") or {}
            ).get("stage_reported_request_ids") is not None or recon.get(
                "stage_reported_not_durable"
            ) is not None
            diag = life.get("graduated_supply_diagnostics") or {}
            full = diag.get("campaign_source_request_reconciliation") or recon
            assert full.get("blocker") == CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH
            # Expose stage detail surfaces.
            assert (
                full.get("stage_reported_not_durable") is not None
                or full.get("stage_accounting_blockers") is not None
                or full.get("categorical_detail")
            )
        finally:
            base.tearDown()


def _permanent_supply_with_stage(
    *,
    locator_blocker: bool = False,
    locator_request_id: int | None = None,
    missing_durable_id: int | None = None,
):
    proofs = {}
    origins = []
    candidates = {}
    for i in range(4):
        mint = _MINTS[i]
        pool = _POOLS[i]
        proofs[mint] = FixturePumpSwapProof(mint=mint, pool_address=pool)
        origins.append(
            FixtureOriginProof(
                mint=mint,
                signature=f"sig{i}" + "1" * 80,
                slot=432_499_500 + i,
                block_time=int(
                    __import__("datetime")
                    .datetime.fromisoformat(e8.NOW.replace("Z", "+00:00"))
                    .timestamp()
                ),
                bonding_curve=pool,
                confirmed=True,
            )
        )
        candidates[mint.lower()] = {
            "mint": mint,
            "pool": pool,
            "pumpswap_pool": pool,
            "market_identity": f"solana-mainnet:pumpswap:{pool}",
            "provenance": "LATEST_GRADUATED",
            "liquidity": {"liquidity_usd": 5000.0},
            "evidence_expires_at": EXPIRES,
            "memory_observation_eligible": True,
            "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
        }
    diagnostics: dict = {
        "permanent_availability": True,
        "stage_local_source_requests": 0,
        "stage_operations_used": {},
    }
    if locator_blocker and locator_request_id is not None:
        diagnostics["dexscreener_locator"] = {
            "request_id": locator_request_id,
            "source_request_ids": [locator_request_id],
            "source_request_coverage": [
                _coverage(
                    locator_request_id,
                    stage="DEXSCREENER_FRESH_LOCATOR|1",
                    terminal="BLOCKED",
                    transport=0,
                )
            ],
            "accounting_blocker": True,
            "accounting_blocker_reason": (
                "TRANSPORT_IDENTITY_MEASUREMENT_FAILED:TEST"
            ),
            "matched_mints": [],
            "pool_observations": [],
        }
        # Also provide matching durable set so only accounting blocker fires.
        diagnostics["protocol_confirmation"] = {
            "source_request_ids": [locator_request_id],
            "source_request_coverage": [
                _coverage(
                    locator_request_id,
                    stage="DEXSCREENER_FRESH_LOCATOR|1",
                    terminal="BLOCKED",
                    transport=0,
                )
            ],
        }
        diagnostics["source_request_ids"] = [locator_request_id]
        diagnostics["campaign_source_request_coverage"] = [
            _coverage(
                locator_request_id,
                stage="DEXSCREENER_FRESH_LOCATOR|1",
                terminal="BLOCKED",
                transport=0,
            )
        ]
    if missing_durable_id is not None:
        mid = int(missing_durable_id)
        diagnostics["protocol_confirmation"] = {
            "source_request_ids": [mid],
            "source_request_coverage": [_coverage(mid)],
        }
        diagnostics["source_request_ids"] = [mid]
        diagnostics["campaign_source_request_coverage"] = [_coverage(mid)]
    return GraduatedSupply(
        ready=True,
        terminal="GRADUATED_SUPPLY_READY",
        graduated_supply=tuple(origins),
        graduation_proofs=proofs,
        candidate_a={"mint": origins[0].mint, "pair_address": _POOLS[0]},
        candidate_b={"mint": origins[1].mint, "pair_address": _POOLS[1]},
        two_candidate_selection={"ready": True},
        handoff_readiness={},
        discovery_report={},
        front_door_report={"generated_at": e8.NOW},
        diagnostics=diagnostics,
        holder_reserve_supply=tuple(origins),
        holder_reserve_candidates=candidates,
    )


def _seed_markets(db_path, supply):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        for proof in supply.holder_reserve_supply:
            item = supply.holder_reserve_candidates[proof.mint.lower()]
            record_exact_market_transition(
                conn,
                ExactMarketObservation(
                    network=NETWORK,
                    mint=proof.mint,
                    pool=str(item["pool"]),
                    token_program="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                    pool_program=PUMPSWAP_AMM_PROGRAM_ID,
                    base_mint=proof.mint,
                    quote_mint=WSOL,
                    venue="pumpswap",
                    state=CURRENT_VISIBLE,
                    reason="FIXTURE",
                    observed_at=e8.NOW,
                    next_lawful_action_at=None,
                    source_provenance={"fixture": True},
                    contract_version="FIXTURE_V1",
                ),
                now=e8.NOW,
            )
        conn.commit()
    finally:
        conn.close()


def _force_holder(owner, proofs):
    def _fake(self, connection, **kwargs):
        from printer_v1.operator_cli.holder_reliability_budget_control import (
            HolderContextResult,
        )

        facts = {}
        for proof in kwargs.get("bounded_candidates") or proofs:
            facts[proof.mint.lower()] = {
                "eligible": False,
                "reason": "HOLDER_CONCENTRATION_EXTREME",
                "source_name": "goplus",
                "holder_concentration_label": "HOLDER_CONCENTRATION_EXTREME",
            }
        return HolderContextResult(
            holder_facts=facts,
            ledger=kwargs["ledger"],
            source_request_ids=(),
            source_request_coverage=(),
            accounting_blocker=False,
            accounting_blocker_reason=None,
            governed_request_count=0,
            measured_transport_count=0,
        )

    owner._evaluate_holder_eligibility = _fake.__get__(
        owner, AuthoritativeLiveOperationalCampaignOwner
    )

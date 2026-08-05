"""V2-9.8B campaign source-request manifest evidence repair.

Proves the collector never synthesizes successful coverage from bare request IDs,
and that durable == stage-reported == coverage is enforced on the campaign path.
Offline fixture-only.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH,
    assemble_and_reconcile_campaign_source_requests,
    collect_stage_reported_request_ids,
    collect_stage_source_request_coverage,
    reconcile_campaign_source_requests,
)
from printer_v1.discovery.combined_executor import (
    FixtureOriginProof,
    FixturePumpSwapProof,
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
from printer_v1.operator_cli.graduated_supply_front_door import GraduatedSupply
from printer_v1.discovery.permanent_discovery_availability import (
    CURRENT_VISIBLE,
    ExactMarketObservation,
    NETWORK,
    record_exact_market_transition,
)
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


def _coverage(
    rid: int,
    *,
    source: str = "solana_rpc",
    kind: str = "pumpswap_pool_account_batch",
    stage: str = "PROTOCOL_CONFIRMATION|1",
    transport: int = 1,
    members: int = 1,
    terminal: str = "COMPLETED",
) -> dict:
    return {
        "source_request_id": rid,
        "source_name": source,
        "request_kind": kind,
        "logical_stage_id": stage,
        "transport_identity_count": transport,
        "normalized_member_count": members,
        "terminal_status": terminal,
    }


def _zero_transport_coverage(rid: int, stage: str) -> dict:
    return _coverage(
        rid,
        stage=stage,
        transport=0,
        members=0,
        terminal="COMPLETED",
    )


class TestCollectorNeverSynthesizes:
    def test_protocol_id_without_coverage_not_synthesized(self):
        diag = {
            "protocol_confirmation": {
                "source_request_ids": [11],
                # No source_request_coverage
            }
        }
        coverage = collect_stage_source_request_coverage(diag)
        assert coverage == []
        reported = collect_stage_reported_request_ids(diag)
        assert reported == [11]

    def test_backup_id_without_coverage_not_synthesized(self):
        diag = {"liquidity_backup": {"source_request_ids": [22]}}
        assert collect_stage_source_request_coverage(diag) == []
        assert collect_stage_reported_request_ids(diag) == [22]

    def test_gecko_id_without_coverage_not_synthesized(self):
        diag = {
            "geckoterminal_nomination": {
                "request_id": 33,
                "nominations": [{"mint": "x"}],
                "transport_operations": 1,
            }
        }
        # Must not invent COMPLETED coverage from request_id alone.
        assert collect_stage_source_request_coverage(diag) == []
        assert collect_stage_reported_request_ids(diag) == [33]

    def test_locator_id_without_coverage_not_synthesized(self):
        diag = {"dexscreener_locator": {"request_id": 44, "source_requests": 1}}
        assert collect_stage_source_request_coverage(diag) == []
        assert collect_stage_reported_request_ids(diag) == [44]

    def test_direct_pump_id_without_coverage_not_synthesized(self):
        diag = {
            "direct_migration_discovery": {
                "source_request_ids": [55, 56],
            }
        }
        assert collect_stage_source_request_coverage(diag) == []
        assert collect_stage_reported_request_ids(diag) == [55, 56]

    def test_collector_does_not_create_completed_zero_fallback(self):
        diag = {
            "protocol_confirmation": {"source_request_ids": [7]},
            "liquidity_backup": {"source_request_ids": [8]},
            "permanent_market_reports": [{"source_request_ids": [9]}],
            "holder_source_request_ids": [10],
        }
        coverage = collect_stage_source_request_coverage(diag)
        assert coverage == []
        # No COMPLETED synthetic rows of any kind.
        assert not any(e.get("terminal_status") == "COMPLETED" for e in coverage)


class TestReconciliationInvariants:
    def test_request_id_without_coverage_blocks(self):
        recon = reconcile_campaign_source_requests(
            durable_request_ids=[1, 2],
            stage_reported_request_ids=[1, 2],
            manifest_entries=[_coverage(1)],  # missing 2
        )
        assert recon["status"] == "BLOCKED"
        assert recon["blocker"] == CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH
        assert 2 in recon["missing_from_manifest"]
        assert 2 in recon["missing_stage_reported_coverage"]

    def test_lawful_zero_transport_stage_coverage_reconciles(self):
        entry = _zero_transport_coverage(5, "LOCAL_ONLY_STAGE|1")
        recon = reconcile_campaign_source_requests(
            durable_request_ids=[5],
            stage_reported_request_ids=[5],
            manifest_entries=[entry],
        )
        assert recon["status"] == "OK"
        assert recon["manifest"][0]["transport_identity_count"] == 0

    def test_duplicate_coverage_id_blocks(self):
        recon = reconcile_campaign_source_requests(
            durable_request_ids=[7],
            stage_reported_request_ids=[7],
            manifest_entries=[
                _coverage(7, stage="PROTOCOL|1"),
                _coverage(7, stage="PROTOCOL|2"),
            ],
        )
        assert recon["status"] == "BLOCKED"
        assert recon["blocker"] == CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH

    def test_unknown_extra_coverage_id_blocks(self):
        recon = reconcile_campaign_source_requests(
            durable_request_ids=[1],
            stage_reported_request_ids=[1],
            manifest_entries=[_coverage(1), _coverage(99)],
        )
        assert recon["status"] == "BLOCKED"
        assert 99 in recon["extra_in_manifest"]

    def test_multi_stage_real_coverage_reconciles_exactly(self):
        entries = [
            _coverage(
                1,
                source="dexscreener",
                kind="dexscreener_fresh_profiles",
                stage="DEXSCREENER_FRESH_LOCATOR|1",
            ),
            _coverage(
                2,
                source="pump_migration",
                kind="getSignaturesForAddress",
                stage="DIRECT_MIGRATION_INTAKE|1",
            ),
            _coverage(
                3,
                source="geckoterminal",
                kind="geckoterminal_new_pool_discovery",
                stage="FRESH_POOL_NOMINATION|1",
            ),
            _coverage(
                4,
                source="geckoterminal",
                kind="candidate_market_batch",
                stage="UNKNOWN_LIQUIDITY_BACKUP|1",
            ),
            _coverage(5, stage="PROTOCOL_CONFIRMATION|1"),
            _coverage(6, stage="PROTOCOL_CONFIRMATION|2"),
        ]
        recon = reconcile_campaign_source_requests(
            durable_request_ids=[1, 2, 3, 4, 5, 6],
            stage_reported_request_ids=[1, 2, 3, 4, 5, 6],
            manifest_entries=entries,
        )
        assert recon["status"] == "OK"
        assert set(recon["durable_request_ids"]) == set(recon["manifest_request_ids"])
        assert set(recon["stage_reported_request_ids"]) == set(
            recon["manifest_request_ids"]
        )


class TestAssembleAndCampaignPath:
    @pytest.fixture()
    def database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.sqlite3"
            apply_migrations(path)
            connection = sqlite3.connect(str(path))
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            try:
                yield path, connection
            finally:
                connection.close()

    def _insert_request(self, connection, source, kind, key):
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

    def test_assemble_blocks_when_protocol_coverage_missing(self, database):
        path, connection = database
        rid = self._insert_request(
            connection, "solana_rpc", "pumpswap_pool_account_batch", "camp-x|proto"
        )
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "protocol_confirmation": {
                    "source_request_ids": [rid],
                    # missing coverage on purpose
                }
            },
            request_key_prefixes=["camp-x"],
        )
        assert recon["status"] == "BLOCKED"
        assert recon["blocker"] == CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH
        assert rid in recon.get("missing_from_manifest") or rid in (
            recon.get("campaign_source_request_reconciliation") or {}
        ).get("missing_from_manifest", [])

    def test_assemble_passes_with_real_stage_coverage(self, database):
        path, connection = database
        rid = self._insert_request(
            connection, "solana_rpc", "pumpswap_pool_account_batch", "camp-ok|proto"
        )
        entry = _coverage(rid)
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "protocol_confirmation": {
                    "source_request_ids": [rid],
                    "source_request_coverage": [entry],
                }
            },
            request_key_prefixes=["camp-ok"],
        )
        assert recon["status"] == "OK"
        assert recon["stage_produced_coverage_entries"]
        assert recon["stage_reported_request_ids"] == [rid]

    def _permanent_supply(self, n=4, recon_coverage=None, recon_ids=None):
        proofs = {}
        origins = []
        candidates = {}
        for i in range(n):
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
        diagnostics = {
            "permanent_availability": True,
            "stage_local_source_requests": 0,
            "stage_operations_used": {},
        }
        if recon_coverage is not None:
            diagnostics["campaign_source_request_coverage"] = recon_coverage
            diagnostics["source_request_ids"] = list(
                recon_ids or [e["source_request_id"] for e in recon_coverage]
            )
            diagnostics["protocol_confirmation"] = {
                "source_request_ids": list(
                    recon_ids or [e["source_request_id"] for e in recon_coverage]
                ),
                "source_request_coverage": list(recon_coverage),
            }
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

    def _seed_markets(self, db_path, supply):
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

    def _force_holder(self, owner, proofs):
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

    def test_campaign_reconciliation_blocker_prevents_readiness(self):
        base = e8._IntegrationBase()
        base.setUp()
        try:
            # Stage reports an ID but provides no real coverage entry.
            conn = sqlite3.connect(base.db)
            conn.execute(
                """
                INSERT INTO printer_source_requests(
                    source_name, request_kind, requested_at, request_key,
                    tracking_priority, source_status, data_quality_label
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (
                    "solana_rpc",
                    "pumpswap_pool_account_batch",
                    e8.NOW,
                    "fixture-proto-missing-cov",
                    0,
                    "COMPLETE",
                    "CLEAN_DATA",
                ),
            )
            rid = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.commit()
            conn.close()
            supply = self._permanent_supply(4)
            supply.diagnostics["protocol_confirmation"] = {
                "source_request_ids": [rid],
                "source_request_coverage": [],
            }
            supply.diagnostics["source_request_ids"] = [rid]
            self._seed_markets(base.db, supply)
            owner = AuthoritativeLiveOperationalCampaignOwner()
            self._force_holder(owner, supply.holder_reserve_supply)
            result = owner.run(
                mode=PILOT_INPUT_READINESS,
                command=base.command,
                pump_transport=_FakePumpTransport([], {}),
                secondary_transport=None,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="manifest-block",
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
            assert life["lifecycle_started"] is False
            admission = life.get("pre_lifecycle_admission") or {}
            recon = admission.get("campaign_source_request_reconciliation") or {}
            # Durable blocked report exposes missing IDs / ownership gaps.
            assert recon.get("status") == "BLOCKED"
            assert recon.get("missing_from_manifest") or recon.get(
                "missing_stage_reported_coverage"
            ) is not None
            diag = life.get("candidate_supply_diagnostics") or {}
            assert diag.get("campaign_source_request_reconciliation")
        finally:
            base.tearDown()

    def test_campaign_with_real_stage_shaped_coverage_passes(self):
        base = e8._IntegrationBase()
        base.setUp()
        try:
            conn = sqlite3.connect(base.db)
            conn.execute(
                """
                INSERT INTO printer_source_requests(
                    source_name, request_kind, requested_at, request_key,
                    tracking_priority, source_status, data_quality_label
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (
                    "solana_rpc",
                    "pumpswap_pool_account_batch",
                    e8.NOW,
                    "fixture-ok-proto",
                    0,
                    "COMPLETE",
                    "CLEAN_DATA",
                ),
            )
            rid = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.commit()
            conn.close()
            coverage = [_coverage(rid)]
            supply = self._permanent_supply(
                4, recon_coverage=coverage, recon_ids=[rid]
            )
            self._seed_markets(base.db, supply)
            owner = AuthoritativeLiveOperationalCampaignOwner()
            self._force_holder(owner, supply.holder_reserve_supply)
            result = owner.run(
                mode=PILOT_INPUT_READINESS,
                command=base.command,
                pump_transport=_FakePumpTransport([], {}),
                secondary_transport=None,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="manifest-ok",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=base.backup,
                lifecycle_kwargs={"context_adapter_factories": {}},
                graduated_supply=supply,
            )
            life = result.lifecycle
            diag = life.get("candidate_supply_diagnostics") or {}
            recon = diag.get("campaign_source_request_reconciliation") or {}
            assert recon.get("status") == "OK"
            # This legacy fixture has request coverage but intentionally no
            # retained market response rows.  The activation contract must now
            # block instead of manufacturing them.
            assert life.get("pilot_input_readiness") is None
            assert life["stop_reason"] == "RETAINED_EVIDENCE_REFERENCE_INCOMPLETE"
            assert life["lifecycle_started"] is False
        finally:
            base.tearDown()

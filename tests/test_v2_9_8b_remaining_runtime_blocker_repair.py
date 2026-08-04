"""V2-9.8B remaining graduated-discovery runtime blocker repair proofs.

Offline fixture-only. Every defect is proven through its production caller.
No providers, runtime, authorization, WINDOW_15M, memory, retrieval, decisions,
positions, trades, audits, or PnL.
"""

from __future__ import annotations

import base64
import json
import sqlite3
import tempfile
from dataclasses import replace
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
    MINIMUM_FREEZE_DEPTH,
    NETWORK,
    STAGE_RESERVATIONS,
    StageBudget,
    assemble_and_reconcile_campaign_source_requests,
    freeze_eligible_reserve,
    record_exact_market_transition,
    record_fresh_pool_nominations,
    reconcile_campaign_source_requests,
    run_bounded_unknown_liquidity_backup,
    run_geckoterminal_fresh_nomination,
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
from printer_v1.operator_cli.pilot_input_readiness import (
    BLOCKED_HOLDER,
    READINESS_PURPOSE_FUTURE_ACTION,
    READINESS_PURPOSE_MEMORY_OBSERVATION,
    READINESS_READY,
    ReadinessCandidate,
    build_pilot_input_ready_bundle,
    evaluate_readiness_gates,
)
from printer_v1.sources.measured_transport import MeasuredTransportError
from printer_v1.sources.pumpswap import (
    PUMPSWAP_AMM_PROGRAM_ID,
    _PUMPSWAP_POOL_BASE_MINT_OFFSET,
    _b58decode,
)

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
from test_v2_9_7e_11_authoritative_live_operational_campaign import _FakePumpTransport

GOV = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCH = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)

NOW = "2026-08-04T17:00:00+00:00"
# Far-future expiry: campaign freeze uses datetime.now(timezone.utc), not the
# fixture evaluated_at clock.
EXPIRES = "2099-01-01T00:00:00+00:00"
STALE = "2000-01-01T00:00:00+00:00"
WSOL = "So11111111111111111111111111111111111111112"

# Real-looking Pump mints / pools for campaign path.
_MINTS = [
    "4tNCRgigHBPiMsPfrCaU1kE6gGofxgXLmEq8mRK1pump",
    "4FN5PSaprS73Z2SRGx2HG9eaES1yVURMU5yAPpDQpump",
    "5tNCRgigHBPiMsPfrCaU1kE6gGofxgXLmEq8mRK2pump",
    "6FN5PSaprS73Z2SRGx2HG9eaES1yVURMU5yAPpDRpump",
    "7tNCRgigHBPiMsPfrCaU1kE6gGofxgXLmEq8mRK3pump",
    "8FN5PSaprS73Z2SRGx2HG9eaES1yVURMU5yAPpDSpump",
]
_POOLS = [
    "BDhvEqa1KjHBsNSFxN9Np4t3CLZjaCvDtCRjrqsbQ21p",
    "9yuowVdGRZ35yM339cjyTWfhAdJJVPJqPKGHhyCXG3fo",
    "CDhvEqa1KjHBsNSFxN9Np4t3CLZjaCvDtCRjrqsbQ22q",
    "AyuowVdGRZ35yM339cjyTWfhAdJJVPJqPKGHhyCXG3fp",
    "DDhvEqa1KjHBsNSFxN9Np4t3CLZjaCvDtCRjrqsbQ23r",
    "ByuowVdGRZ35yM339cjyTWfhAdJJVPJqPKGHhyCXG3fq",
]


def _measured_identity(source_name: str, kind: str, ordinal: int = 1) -> dict:
    return {
        "stage": "MINT_MARKET_BATCH",
        "source_name": source_name,
        "endpoint_owner": source_name,
        "governed_request_kind": kind,
        "method_or_endpoint": f"GET /{kind}",
        "within_request_ordinal": ordinal,
        "target_category": "mint_pool_reconciliation",
        "target_identity": None,
        "response_bytes": 100,
        "normalized_rows": 1,
        "result": "OK",
        "reserved_from": None,
    }


def _seed_exact_markets_for_supply(db_path: str, supply: GraduatedSupply) -> None:
    """Parent exact-market rows required by MEMORY_OBSERVATION reserve FK.

    Campaign observation rows use proof.mint as the mint identity; seed parents
    for every holder-reserve proof so FK upserts succeed.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        for proof in supply.holder_reserve_supply or supply.graduated_supply:
            item = dict(
                supply.holder_reserve_candidates.get(proof.mint.lower()) or {}
            )
            mint = str(proof.mint)
            pool = str(item.get("pool") or item.get("pumpswap_pool") or "")
            if not mint or not pool:
                continue
            record_exact_market_transition(
                conn,
                ExactMarketObservation(
                    network=NETWORK,
                    mint=mint,
                    pool=pool,
                    token_program="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                    pool_program=PUMPSWAP_AMM_PROGRAM_ID,
                    base_mint=mint,
                    quote_mint=WSOL,
                    venue="pumpswap",
                    state=CURRENT_VISIBLE,
                    reason="AT_OR_ABOVE_3000_FLOOR_FIXTURE",
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


def _clean_goplus_extreme():
    """Holder context used by campaign path (label may still be present)."""
    from printer_v1.sources.governed_execution import build_fixture_source_adapter

    def safety(**kwargs):
        mint = kwargs.get("token_mint")
        return build_fixture_source_adapter(
            "goplus",
            fixture_payload={
                "token_mint": mint,
                "mint_authority": None,
                "freeze_authority": None,
                "metadata_mutable": False,
                "total_supply": "1000000000",
                "top_10_holders": [{"percent": "90"}] + [{"percent": "1"}] * 9,
                "lp_info": [{"locked": True}],
                "risk_flags": ["extreme_holder_concentration"],
            },
        )

    return {"goplus": safety}


def _force_holder_extreme_ineligible(owner, proofs):
    """Production-path: real holder gate can mark concentration labels eligible.

    This lane requires proving MEMORY_OBSERVATION readiness when holder_eligible
    is actually false with HOLDER_CONCENTRATION_EXTREME context. Patch the
    campaign holder owner to return that exact durable fact shape.
    """

    def _fake(self, connection, **kwargs):
        facts = {}
        for proof in kwargs.get("bounded_candidates") or proofs:
            facts[proof.mint.lower()] = {
                "eligible": False,
                "reason": "HOLDER_CONCENTRATION_EXTREME",
                "source_name": "goplus",
                "holder_concentration_label": "HOLDER_CONCENTRATION_EXTREME",
            }
        return facts, kwargs["ledger"]

    owner._evaluate_holder_eligibility = _fake.__get__(
        owner, AuthoritativeLiveOperationalCampaignOwner
    )


def _clean_goplus_healthy():
    from printer_v1.sources.governed_execution import build_fixture_source_adapter

    def safety(**kwargs):
        mint = kwargs.get("token_mint")
        return build_fixture_source_adapter(
            "goplus",
            fixture_payload={
                "token_mint": mint,
                "mint_authority": None,
                "freeze_authority": None,
                "metadata_mutable": False,
                "total_supply": "1000000000",
                "top_10_holders": [{"percent": "3"} for _ in range(10)],
                "lp_info": [{"locked": True}],
                "risk_flags": [],
            },
        )

    return {"goplus": safety}


def _proofs(n: int = 4):
    proofs = {}
    origins = []
    for i in range(n):
        mint = _MINTS[i]
        pool = _POOLS[i]
        proofs[mint] = FixturePumpSwapProof(mint=mint, pool_address=pool)
        origins.append(
            FixtureOriginProof(
                mint=mint,
                signature=f"sig{i}" + "1" * 80,
                slot=432_499_500 + i,
                block_time=e8_now_epoch(),
                bonding_curve=pool,
                confirmed=True,
            )
        )
    return proofs, tuple(origins)


def e8_now_epoch() -> int:
    from datetime import datetime, timezone

    return int(datetime.fromisoformat(e8.NOW.replace("Z", "+00:00")).timestamp())


def _permanent_supply(
    n: int = 4,
    *,
    stale_one: bool = False,
    duplicate_identity: bool = False,
    recon_coverage: list | None = None,
    recon_ids: list | None = None,
    accounting_blocker: bool = False,
):
    proofs, origins = _proofs(n if not duplicate_identity else max(n, 6))
    candidates = {}
    for i, proof in enumerate(origins):
        mint = proof.mint
        pool = _POOLS[i]
        expiry = STALE if (stale_one and i == 0) else EXPIRES
        if duplicate_identity and i >= 4:
            # Reuse earlier mint/pool identities so freeze drops duplicates.
            mint = origins[i - 4].mint
            pool = _POOLS[i - 4]
        candidates[mint.lower()] = {
            "mint": mint,
            "pool": pool,
            "pumpswap_pool": pool,
            "market_identity": f"solana-mainnet:pumpswap:{pool}",
            "provenance": "LATEST_GRADUATED" if i % 2 == 0 else "PERSISTED_GRADUATED",
            "liquidity": {"liquidity_usd": 5000.0 + i * 100},
            "liquidity_usd": 5000.0 + i * 100,
            "evidence_expires_at": expiry,
            "memory_observation_eligible": True,
            "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
            "holder_condition": "HOLDER_CONCENTRATION_EXTREME",
        }
    # When duplicate_identity, use 6 origins but only 4 unique keys in candidates
    # — graduated_supply still has 6 proofs for holder walk.
    if duplicate_identity:
        proofs, origins = _proofs(6)
        # candidates already has 4 unique from first loop iterations + overwrites
        candidates = {}
        for i, proof in enumerate(origins):
            # Map all six proofs but only four unique pool/mint pairs for freeze
            # input: first four unique; last two reuse mint/pool of first two.
            base_i = i if i < 4 else i - 4
            mint = origins[base_i].mint
            pool = _POOLS[base_i]
            candidates[proof.mint.lower()] = {
                "mint": mint,  # identity used for freeze after remap? 
                # Actually freeze uses item mint from candidate dict.
                # For production path, observation rows use proof.mint as mint
                # and pool from item. So use proof.mint with shared pool to
                # create duplicate pools, or same mint.
                "pool": pool,
                "pumpswap_pool": pool,
                "market_identity": f"solana-mainnet:pumpswap:{pool}",
                "provenance": "LATEST_GRADUATED",
                "liquidity": {"liquidity_usd": 5000.0},
                "liquidity_usd": 5000.0,
                "evidence_expires_at": EXPIRES,
                "memory_observation_eligible": True,
                "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
                "holder_condition": "HOLDER_CONCENTRATION_EXTREME",
            }
            # Force duplicate mint identities for last two proofs:
            if i >= 4:
                candidates[proof.mint.lower()]["mint"] = origins[base_i].mint

    diagnostics = {
        "permanent_availability": True,
        "selection_floor_usd": 3000.0,
        "stage_local_source_requests": 0,
        "stage_operations_used": {},
    }
    if recon_coverage is not None:
        diagnostics["campaign_source_request_coverage"] = recon_coverage
        diagnostics["source_request_ids"] = list(
            recon_ids or [e["source_request_id"] for e in recon_coverage]
        )
    if accounting_blocker:
        diagnostics["protocol_confirmation"] = {
            "accounting_blocker": True,
            "accounting_blocker_reason": "PROTOCOL_STAGE_SEAL_FAILURE:TEST",
            "source_request_ids": list(recon_ids or []),
            "source_request_coverage": list(recon_coverage or []),
        }

    return GraduatedSupply(
        ready=True,
        terminal="GRADUATED_SUPPLY_READY",
        graduated_supply=origins,
        graduation_proofs=proofs,
        candidate_a={"mint": origins[0].mint, "pair_address": _POOLS[0]},
        candidate_b={"mint": origins[1].mint, "pair_address": _POOLS[1]},
        two_candidate_selection={"ready": True},
        handoff_readiness={"atomic_two_slot_ready": True},
        discovery_report={},
        front_door_report={"generated_at": e8.NOW},
        diagnostics=diagnostics,
        holder_reserve_supply=origins,
        holder_reserve_candidates=candidates,
    )


class _CampaignBase(e8._IntegrationBase):
    """Reuse E.8 temporary DB + abstract command fixture."""


# ---------------------------------------------------------------------------
# Repair 1 — MEMORY_OBSERVATION readiness purpose
# ---------------------------------------------------------------------------


class TestMemoryObservationReadiness:
    def test_memory_purpose_allows_holder_ineligible(self, tmp_path):
        db = tmp_path / "ready.sqlite3"
        apply_migrations(db)
        conn = sqlite3.connect(db)
        conn.execute("PRAGMA foreign_keys = ON")
        latest = ReadinessCandidate(
            mint=_MINTS[0],
            pool=_POOLS[0],
            market_identity=f"solana-mainnet:pumpswap:{_POOLS[0]}",
            liquidity_usd=5000.0,
            liquidity_observed_at=NOW,
            activation_route="GRADUATION_NATIVE",
            holder_eligible=False,
            provenance="LATEST_GRADUATED",
            memory_observation_eligible=True,
            holder_condition="HOLDER_CONCENTRATION_EXTREME",
            future_action_eligibility="BLOCKED_OR_UNKNOWN",
        )
        persisted = ReadinessCandidate(
            mint=_MINTS[1],
            pool=_POOLS[1],
            market_identity=f"solana-mainnet:pumpswap:{_POOLS[1]}",
            liquidity_usd=6000.0,
            liquidity_observed_at=NOW,
            activation_route="GRADUATION_NATIVE",
            holder_eligible=False,
            provenance="PERSISTED_GRADUATED",
            memory_observation_eligible=True,
            holder_condition="HOLDER_CONCENTRATION_EXTREME",
            future_action_eligibility="BLOCKED_OR_UNKNOWN",
        )
        assert (
            evaluate_readiness_gates(
                latest,
                persisted,
                discovery_universe_evaluated=True,
                readiness_purpose=READINESS_PURPOSE_MEMORY_OBSERVATION,
            )
            == READINESS_READY
        )
        assert (
            evaluate_readiness_gates(
                latest,
                persisted,
                discovery_universe_evaluated=True,
                readiness_purpose=READINESS_PURPOSE_FUTURE_ACTION,
            )
            == BLOCKED_HOLDER
        )
        bundle = build_pilot_input_ready_bundle(
            conn,
            readiness_id="mem-1",
            latest=latest,
            persisted=persisted,
            holder_evidence={"x": "extreme"},
            source_ledger={},
            selection_seed="s",
            git_provenance_identity="g",
            configuration_hash="c" * 64,
            expires_at=EXPIRES,
            now=NOW,
            readiness_purpose=READINESS_PURPOSE_MEMORY_OBSERVATION,
        )
        assert bundle["readiness_purpose"] == READINESS_PURPOSE_MEMORY_OBSERVATION
        assert bundle["latest"]["holder_eligible"] is False
        assert bundle["latest"]["memory_observation_eligible"] is True
        assert bundle["latest"]["holder_condition"] == "HOLDER_CONCENTRATION_EXTREME"
        assert bundle["latest"]["future_action_eligibility"] == "BLOCKED_OR_UNKNOWN"
        assert bundle["source_ledger"]["readiness_purpose"] == (
            READINESS_PURPOSE_MEMORY_OBSERVATION
        )
        conn.close()

    def test_campaign_holder_extreme_memory_readiness_bundle(self):
        base = _CampaignBase()
        base.setUp()
        try:
            supply = _permanent_supply(4)
            _seed_exact_markets_for_supply(base.db, supply)
            owner = AuthoritativeLiveOperationalCampaignOwner()
            _force_holder_extreme_ineligible(owner, supply.holder_reserve_supply)
            result = owner.run(
                mode=PILOT_INPUT_READINESS,
                command=base.command,
                pump_transport=_FakePumpTransport([], {}),
                secondary_transport=None,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="rt-mem-1",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=base.backup,
                lifecycle_kwargs={
                    "context_adapter_factories": _clean_goplus_extreme()
                },
                graduated_supply=supply,
            )
            life = result.lifecycle
            assert life["lifecycle_started"] is False
            assert life["stopped_before_lifecycle"] is True
            freeze = (life.get("graduated_supply_diagnostics") or {}).get(
                "freeze_depth_enforcement"
            ) or {}
            assert freeze.get("selected_count") == 2
            assert freeze.get("alternate_count") == 2
            bundle = life.get("pilot_input_readiness")
            assert bundle is not None
            assert bundle["readiness_state"] == "PILOT_INPUT_READY"
            assert bundle["readiness_purpose"] == READINESS_PURPOSE_MEMORY_OBSERVATION
            assert bundle["latest"]["holder_eligible"] is False
            assert bundle["persisted"]["holder_eligible"] is False
            assert bundle["latest"]["memory_observation_eligible"] is True
            assert (
                bundle["latest"]["future_action_eligibility"]
                == "BLOCKED_OR_UNKNOWN"
            )
            # No paper / memory unlock.
            conn = sqlite3.connect(base.db)
            try:
                for table in (
                    "printer_memory_windows",
                    "printer_paper_decisions",
                    "printer_paper_positions",
                ):
                    assert (
                        int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                        == 0
                    )
            finally:
                conn.close()
        finally:
            base.tearDown()


# ---------------------------------------------------------------------------
# Repair 2 — Campaign-wide request reconciliation (production path)
# ---------------------------------------------------------------------------


class TestCampaignSourceRequestReconciliationWiring:
    def _seed_requests(self, db_path: str, ids_sources: list[tuple[int, str, str, str]]):
        """Insert durable source request rows with fixed IDs when possible."""
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        created = []
        for _want_id, source, kind, key in ids_sources:
            conn.execute(
                """
                INSERT INTO printer_source_requests(
                    source_name, request_kind, requested_at, request_key,
                    tracking_priority, source_status, data_quality_label
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (
                    source,
                    kind,
                    NOW,
                    key,
                    0,
                    "COMPLETE",
                    "CLEAN_DATA",
                ),
            )
            rid = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            created.append(rid)
        conn.commit()
        conn.close()
        return created

    def test_multi_stage_manifest_reconciles_exactly(self):
        base = _CampaignBase()
        base.setUp()
        try:
            rids = self._seed_requests(
                base.db,
                [
                    (1, "dexscreener", "fresh_profiles", "camp-rt|dex"),
                    (2, "geckoterminal", "geckoterminal_new_pool_discovery", "camp-rt|gecko"),
                    (3, "geckoterminal", "candidate_market_batch", "camp-rt|backup"),
                    (4, "solana_rpc", "pumpswap_pool_account_batch", "camp-rt|protocol"),
                ],
            )
            coverage = [
                {
                    "source_request_id": rids[0],
                    "source_name": "dexscreener",
                    "request_kind": "fresh_profiles",
                    "logical_stage_id": "camp|run|cyc|DEX|1",
                    "transport_identity_count": 1,
                    "normalized_member_count": 2,
                    "terminal_status": "COMPLETED",
                },
                {
                    "source_request_id": rids[1],
                    "source_name": "geckoterminal",
                    "request_kind": "geckoterminal_new_pool_discovery",
                    "logical_stage_id": "camp|run|cyc|GECKO|1",
                    "transport_identity_count": 1,
                    "normalized_member_count": 1,
                    "terminal_status": "COMPLETED",
                },
                {
                    "source_request_id": rids[2],
                    "source_name": "geckoterminal",
                    "request_kind": "candidate_market_batch",
                    "logical_stage_id": "camp|run|cyc|UNKNOWN_LIQUIDITY_BACKUP|1",
                    "transport_identity_count": 1,
                    "normalized_member_count": 1,
                    "terminal_status": "COMPLETED",
                },
                {
                    "source_request_id": rids[3],
                    "source_name": "solana_rpc",
                    "request_kind": "pumpswap_pool_account_batch",
                    "logical_stage_id": "camp|run|cyc|PROTOCOL_CONFIRMATION|1",
                    "transport_identity_count": 2,
                    "normalized_member_count": 2,
                    "terminal_status": "COMPLETED",
                },
            ]
            supply = _permanent_supply(4, recon_coverage=coverage, recon_ids=rids)
            _seed_exact_markets_for_supply(base.db, supply)
            result = AuthoritativeLiveOperationalCampaignOwner().run(
                mode=PILOT_INPUT_READINESS,
                command=base.command,
                pump_transport=_FakePumpTransport([], {}),
                secondary_transport=None,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="rt-recon-ok",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=base.backup,
                lifecycle_kwargs={
                    "context_adapter_factories": _clean_goplus_extreme()
                },
                graduated_supply=supply,
            )
            diag = result.lifecycle.get("graduated_supply_diagnostics") or {}
            recon = diag.get("campaign_source_request_reconciliation") or {}
            assert recon.get("status") == "OK"
            assert set(diag.get("durable_campaign_request_ids") or ()) == set(rids)
            assert len(diag.get("campaign_source_request_manifest") or ()) == 4
            assert result.lifecycle.get("pilot_input_readiness") is not None
            admission = result.lifecycle.get("pre_lifecycle_admission") or {}
            assert admission.get("campaign_source_request_count") == 4
            assert admission.get("holder_ledger_governed_requests") is not None
        finally:
            base.tearDown()

    def test_missing_manifest_entry_blocks_readiness(self):
        base = _CampaignBase()
        base.setUp()
        try:
            rids = self._seed_requests(
                base.db,
                [
                    (1, "dexscreener", "fresh", "camp-miss|dex"),
                    (2, "geckoterminal", "geckoterminal_new_pool_discovery", "camp-miss|gecko"),
                ],
            )
            # Manifest omits gecko entry intentionally.
            coverage = [
                {
                    "source_request_id": rids[0],
                    "source_name": "dexscreener",
                    "request_kind": "fresh",
                    "logical_stage_id": "L1",
                    "transport_identity_count": 0,
                    "normalized_member_count": 0,
                    "terminal_status": "COMPLETED",
                }
            ]
            supply = _permanent_supply(4, recon_coverage=coverage, recon_ids=rids)
            # Force durable IDs to include both by prefix + known_ids in diagnostics.
            supply.diagnostics["source_request_ids"] = rids
            supply.diagnostics["campaign_source_request_coverage"] = coverage
            _seed_exact_markets_for_supply(base.db, supply)
            result = AuthoritativeLiveOperationalCampaignOwner().run(
                mode=PILOT_INPUT_READINESS,
                command=base.command,
                pump_transport=_FakePumpTransport([], {}),
                secondary_transport=None,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="rt-recon-miss",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=base.backup,
                lifecycle_kwargs={
                    "context_adapter_factories": _clean_goplus_extreme()
                },
                graduated_supply=supply,
            )
            assert result.lifecycle["lifecycle_started"] is False
            assert result.lifecycle.get("pilot_input_readiness") is None
            terminal = result.lifecycle.get("stop_reason") or result.lifecycle.get(
                "first_terminal_cause"
            )
            assert terminal == CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH
            diag = result.lifecycle.get("graduated_supply_diagnostics") or {}
            recon = diag.get("campaign_source_request_reconciliation") or {}
            assert recon.get("status") == "BLOCKED"
            # Durable blocked report surface is present on admission/lifecycle.
            admission = result.lifecycle.get("pre_lifecycle_admission") or {}
            assert admission.get("campaign_source_request_reconciliation")
            assert result.lifecycle.get("stopped_before_lifecycle") is True
        finally:
            base.tearDown()

    def test_duplicate_protocol_id_blocks(self):
        coverage = [
            {
                "source_request_id": 7,
                "source_name": "solana_rpc",
                "request_kind": "pumpswap_pool_account_batch",
                "logical_stage_id": "PROTOCOL|1",
                "transport_identity_count": 1,
                "normalized_member_count": 1,
                "terminal_status": "COMPLETED",
            },
            {
                "source_request_id": 7,
                "source_name": "solana_rpc",
                "request_kind": "pumpswap_pool_account_batch",
                "logical_stage_id": "PROTOCOL|2",
                "transport_identity_count": 1,
                "normalized_member_count": 1,
                "terminal_status": "COMPLETED",
            },
        ]
        recon = reconcile_campaign_source_requests(
            durable_request_ids=[7],
            manifest_entries=coverage,
        )
        assert recon["status"] == "BLOCKED"
        assert recon["blocker"] == CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH


# ---------------------------------------------------------------------------
# Repair 3 — Post-filter freeze depth authority (campaign path)
# ---------------------------------------------------------------------------


class TestPostFilterFreezeDepthCampaign:
    def test_four_raw_one_stale_blocks_campaign_readiness(self):
        base = _CampaignBase()
        base.setUp()
        try:
            supply = _permanent_supply(4, stale_one=True)
            _seed_exact_markets_for_supply(base.db, supply)
            result = AuthoritativeLiveOperationalCampaignOwner().run(
                mode=PILOT_INPUT_READINESS,
                command=base.command,
                pump_transport=_FakePumpTransport([], {}),
                secondary_transport=None,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="rt-depth-stale",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=base.backup,
                lifecycle_kwargs={
                    "context_adapter_factories": _clean_goplus_extreme()
                },
                graduated_supply=supply,
            )
            diag = result.lifecycle.get("graduated_supply_diagnostics") or {}
            freeze = diag.get("observation_reserve") or {}
            assert freeze.get("input_count") == 4
            assert freeze.get("valid_fresh_unique_observation_depth") == 3
            assert freeze.get("stale_count") == 1
            assert freeze.get("coverage_blocker") is True
            assert result.lifecycle.get("pilot_input_readiness") is None
            assert result.lifecycle.get("stop_reason") == (
                "PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT"
            )
            assert result.lifecycle["lifecycle_started"] is False
        finally:
            base.tearDown()

    def test_six_raw_duplicate_identities_yield_two_plus_two(self):
        base = _CampaignBase()
        base.setUp()
        try:
            supply = _permanent_supply(6, duplicate_identity=True)
            _seed_exact_markets_for_supply(base.db, supply)
            result = AuthoritativeLiveOperationalCampaignOwner().run(
                mode=PILOT_INPUT_READINESS,
                command=base.command,
                pump_transport=_FakePumpTransport([], {}),
                secondary_transport=None,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="rt-depth-dup",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=base.backup,
                lifecycle_kwargs={
                    "context_adapter_factories": _clean_goplus_extreme()
                },
                graduated_supply=supply,
            )
            diag = result.lifecycle.get("graduated_supply_diagnostics") or {}
            freeze = diag.get("observation_reserve") or {}
            assert freeze.get("input_count") == 6
            assert freeze.get("valid_fresh_unique_observation_depth") == 4
            assert freeze.get("coverage_blocker") is False
            assert freeze.get("surplus_status") == "SURPLUS_TARGET_NOT_MET"
            assert (diag.get("freeze_depth_enforcement") or {}).get(
                "selected_count"
            ) == 2
            assert (diag.get("freeze_depth_enforcement") or {}).get(
                "alternate_count"
            ) == 2
            assert result.lifecycle.get("pilot_input_readiness") is not None
        finally:
            base.tearDown()


# ---------------------------------------------------------------------------
# Repair 4 — Measured transports (gecko + backup)
# ---------------------------------------------------------------------------


class TestMeasuredTransports:
    @pytest.fixture()
    def database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mt.sqlite3"
            apply_migrations(path)
            connection = sqlite3.connect(str(path))
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            try:
                yield path, connection
            finally:
                connection.close()

    def test_gecko_fresh_measurement_failure_not_swallowed(self, database):
        _, connection = database

        def transport(_ctx):
            return {
                "data": [],
                "pairs": [],
                "response_bytes": 10,
                "transport_operations_used": 1,
                # Declared used without identities → measurement error.
            }

        with patch(
            "printer_v1.sources.measured_transport.record_payload_transports",
            side_effect=MeasuredTransportError("TRANSPORT_IDENTITIES_MISSING"),
        ):
            report = run_geckoterminal_fresh_nomination(
                connection,
                request_key="gt-fail",
                now=NOW,
                campaign_id="camp",
                run_id="run",
                cycle_id="cyc",
                transport=transport,
            )
        assert report["request_id"] is not None
        assert report["source_requests"] == 1
        assert report["accounting_blocker"] is True
        assert "TRANSPORT_IDENTITY_MEASUREMENT_FAILED" in str(
            report["accounting_blocker_reason"]
        )
        assert report["transport_operations"] == 0
        assert report["source_request_coverage"][0]["transport_identity_count"] == 0
        assert report["nominations"] == []

    def test_backup_dex_to_gecko_records_measured_transport(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[
                {
                    "mint": _MINTS[0],
                    "pool": _POOLS[0],
                    "base_mint": _MINTS[0],
                    "quote_mint": WSOL,
                    "venue": "pumpswap",
                    "liquidity_usd": None,
                }
            ],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-bak",
        )
        identity = _measured_identity("geckoterminal", "candidate_market_batch")

        def gt_factory(mint):
            def transport(_ctx):
                # Gecko adapter expects API `data` list; metadata preserved via
                # merge_transport_payload_metadata into normalized pairs payload.
                return {
                    "data": [
                        {
                            "id": "solana_" + _POOLS[0],
                            "attributes": {
                                "address": _POOLS[0],
                                "base_token_address": mint,
                                "quote_token_address": WSOL,
                                "dex": "pumpswap",
                                "reserve_in_usd": "5500",
                            },
                            "relationships": {
                                "base_token": {
                                    "data": {"id": "solana_" + mint}
                                },
                                "quote_token": {
                                    "data": {"id": "solana_" + WSOL}
                                },
                                "dex": {"data": {"id": "pumpswap"}},
                            },
                        }
                    ],
                    "response_bytes": 200,
                    "transport_operations_used": 1,
                    "transport_operation_identities": [identity],
                }

            return transport

        report = run_bounded_unknown_liquidity_backup(
            connection,
            stage_budget=StageBudget.permanent_discovery_default(),
            now=NOW,
            campaign_id="camp-bak",
            run_id="run",
            cycle_id="cyc",
            geckoterminal_transport_factory=gt_factory,
        )
        assert report["source_requests"] == 1
        assert report["source_request_ids"]
        assert report["transport_operations"] == 1
        assert report["source_request_coverage"][0]["transport_identity_count"] == 1
        assert report["source_request_coverage"][0]["normalized_member_count"] >= 1
        assert report["accounting_blocker"] is False

    def test_backup_gecko_to_dex_records_measured_transport(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[
                {
                    "mint": _MINTS[1],
                    "pool": _POOLS[1],
                    "base_mint": _MINTS[1],
                    "quote_mint": WSOL,
                    "venue": "pumpswap",
                    "liquidity_usd": None,
                }
            ],
            source="geckoterminal",
            request_id=1,
            now=NOW,
            campaign_id="camp-bak2",
        )
        identity = _measured_identity("dexscreener", "candidate_market_batch")

        def dex_factory(mint):
            def transport(_ctx):
                return {
                    "pairs": [
                        {
                            "pairAddress": _POOLS[1],
                            "chainId": "solana",
                            "baseToken": {"address": mint},
                            "quoteToken": {"address": WSOL},
                            "dexId": "pumpswap",
                            "liquidity": {"usd": 4000},
                            "base_mint": mint,
                            "quote_mint": WSOL,
                            "pool": _POOLS[1],
                            "liquidity_usd": 4000,
                            "venue": "pumpswap",
                        }
                    ],
                    "response_bytes": 200,
                    "transport_operations_used": 1,
                    "transport_operation_identities": [identity],
                    "_requested_token_mints": [mint],
                }

            return transport

        report = run_bounded_unknown_liquidity_backup(
            connection,
            stage_budget=StageBudget.permanent_discovery_default(),
            now=NOW,
            campaign_id="camp-bak2",
            dexscreener_transport_factory=dex_factory,
        )
        assert report["source_requests"] == 1
        assert report["transport_operations"] == 1
        assert report["source_request_coverage"][0]["transport_identity_count"] == 1

    def test_backup_measurement_failure_blocks_and_preserves_request(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[
                {
                    "mint": _MINTS[0],
                    "pool": _POOLS[0],
                    "base_mint": _MINTS[0],
                    "quote_mint": WSOL,
                    "venue": "pumpswap",
                    "liquidity_usd": None,
                }
            ],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-bak-fail",
        )

        def gt_factory(mint):
            def transport(_ctx):
                return {
                    "pairs": [],
                    "response_bytes": 10,
                    "transport_operations_used": 1,
                }

            return transport

        with patch(
            "printer_v1.sources.measured_transport.record_payload_transports",
            side_effect=MeasuredTransportError("MALFORMED_TRANSPORT_IDENTITY"),
        ):
            report = run_bounded_unknown_liquidity_backup(
                connection,
                stage_budget=StageBudget.permanent_discovery_default(),
                now=NOW,
                campaign_id="camp-bak-fail",
                geckoterminal_transport_factory=gt_factory,
            )
        assert report["source_requests"] == 1
        assert report["source_request_ids"]
        assert report["accounting_blocker"] is True
        assert report["transport_operations"] == 0
        assert report["source_request_coverage"][0]["transport_identity_count"] == 0
        # Still unknown — no protocol promotion path from backup.
        assert report["above_floor_promoted_to_protocol_due"] == 0

    def test_request_and_transport_counts_remain_separate(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[
                {
                    "mint": _MINTS[0],
                    "pool": _POOLS[0],
                    "base_mint": _MINTS[0],
                    "quote_mint": WSOL,
                    "venue": "pumpswap",
                    "liquidity_usd": None,
                }
            ],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-sep",
        )
        identity = _measured_identity("geckoterminal", "candidate_market_batch")

        def gt_factory(mint):
            def transport(_ctx):
                return {
                    "data": [
                        {
                            "id": "solana_" + _POOLS[0],
                            "attributes": {
                                "address": _POOLS[0],
                                "base_token_address": mint,
                                "quote_token_address": WSOL,
                                "dex": "pumpswap",
                                "reserve_in_usd": "9000",
                            },
                            "relationships": {
                                "base_token": {
                                    "data": {"id": "solana_" + mint}
                                },
                                "quote_token": {
                                    "data": {"id": "solana_" + WSOL}
                                },
                                "dex": {"data": {"id": "pumpswap"}},
                            },
                        }
                    ],
                    "transport_operations_used": 1,
                    "transport_operation_identities": [identity],
                    "response_bytes": 50,
                }

            return transport

        report = run_bounded_unknown_liquidity_backup(
            connection,
            stage_budget=StageBudget.permanent_discovery_default(),
            now=NOW,
            campaign_id="camp-sep",
            geckoterminal_transport_factory=gt_factory,
        )
        assert report["source_requests"] == 1
        assert report["transport_operations"] == 1
        # Separate surfaces — equality is not an invariant requirement, but both
        # are independently measured.
        assert "source_requests" in report and "transport_operations" in report


# ---------------------------------------------------------------------------
# Integrated composition
# ---------------------------------------------------------------------------


class TestIntegratedComposition:
    def test_full_memory_observation_composition_stops_before_lifecycle(self):
        base = _CampaignBase()
        base.setUp()
        try:
            supply = _permanent_supply(4)
            _seed_exact_markets_for_supply(base.db, supply)
            owner = AuthoritativeLiveOperationalCampaignOwner()
            _force_holder_extreme_ineligible(owner, supply.holder_reserve_supply)
            result = owner.run(
                mode=PILOT_INPUT_READINESS,
                command=base.command,
                pump_transport=_FakePumpTransport([], {}),
                secondary_transport=None,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="rt-integ-ok",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=base.backup,
                lifecycle_kwargs={
                    "context_adapter_factories": _clean_goplus_extreme()
                },
                graduated_supply=supply,
            )
            life = result.lifecycle
            diag = life.get("graduated_supply_diagnostics") or {}
            freeze = diag.get("observation_reserve") or {}
            assert freeze.get("valid_fresh_unique_observation_depth") >= 4
            assert freeze.get("coverage_blocker") is False
            assert (diag.get("freeze_depth_enforcement") or {}).get(
                "selected_count"
            ) == 2
            assert (diag.get("freeze_depth_enforcement") or {}).get(
                "alternate_count"
            ) == 2
            bundle = life.get("pilot_input_readiness")
            assert bundle is not None
            assert bundle["readiness_purpose"] == READINESS_PURPOSE_MEMORY_OBSERVATION
            assert bundle["latest"]["holder_eligible"] is False
            assert (
                bundle["latest"]["future_action_eligibility"]
                == "BLOCKED_OR_UNKNOWN"
            )
            recon = diag.get("campaign_source_request_reconciliation") or {}
            assert recon.get("status") == "OK"
            assert life["lifecycle_started"] is False
            assert life["stopped_before_lifecycle"] is True
            conn = sqlite3.connect(base.db)
            try:
                for table in (
                    "printer_memory_windows",
                    "printer_episodes",
                    "printer_paper_decisions",
                    "printer_paper_positions",
                    "printer_paper_trade_events",
                    "printer_paper_trade_audits",
                ):
                    assert (
                        int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                        == 0
                    )
            finally:
                conn.close()
            assert sum(cap for _, cap in STAGE_RESERVATIONS) == 30
            assert MINIMUM_FREEZE_DEPTH == 4
        finally:
            base.tearDown()

    def test_three_valid_candidates_durable_coverage_blocker(self):
        base = _CampaignBase()
        base.setUp()
        try:
            supply = _permanent_supply(3)
            _seed_exact_markets_for_supply(base.db, supply)
            result = AuthoritativeLiveOperationalCampaignOwner().run(
                mode=PILOT_INPUT_READINESS,
                command=base.command,
                pump_transport=_FakePumpTransport([], {}),
                secondary_transport=None,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="rt-integ-block",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=base.backup,
                lifecycle_kwargs={
                    "context_adapter_factories": _clean_goplus_extreme()
                },
                graduated_supply=supply,
            )
            life = result.lifecycle
            assert life.get("pilot_input_readiness") is None
            assert life.get("stop_reason") == (
                "PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT"
            )
            freeze = (life.get("graduated_supply_diagnostics") or {}).get(
                "observation_reserve"
            ) or {}
            assert freeze.get("valid_fresh_unique_observation_depth") == 3
            assert freeze.get("coverage_blocker") is True
            assert life["lifecycle_started"] is False
        finally:
            base.tearDown()

"""V2-9.8B retained-evidence role completeness before freeze repair.

Cases:
A. MARKET_PRESENT complete passes pre-freeze gate
B. DIRECT_PUMP complete passes pre-freeze gate
C. DIRECT_PUMP incomplete excluded before freeze
D. insufficient role-complete freeze depth -> coverage blocker
E. report-only alternate does not hard-terminalize selected pair
F. final validator still fails RETAINED_EVIDENCE_ROLE_MISSING
Plus production-caller coverage through freeze_eligible_reserve_for_campaign.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.combined_executor import (
    FixtureOriginProof,
    FixturePumpSwapProof,
)
from printer_v1.discovery.memory_observation_activation import (
    AdmissionAuthority,
    ActivationPurpose,
    EvidenceRole,
    FrozenMemoryActivationCandidate,
    FrozenMemoryActivationSet,
    ManifestRequestEntry,
    MemoryObservationActivationError,
    RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE,
    RetainedEvidenceReference,
    TrackingFeasibility,
    assess_retained_evidence_role_completeness,
    required_evidence_roles_for_admission_authority,
    required_evidence_roles_for_candidate,
    validate_memory_activation_set,
)
from printer_v1.discovery.permanent_discovery_availability import (
    freeze_eligible_reserve,
    freeze_eligible_reserve_for_campaign,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
    PILOT_INPUT_READINESS,
    _build_frozen_memory_activation_set,
    _filter_observation_rows_by_retained_role_completeness,
)
from printer_v1.operator_cli.graduated_supply_front_door import GraduatedSupply

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
from test_v2_9_7e_11_authoritative_live_operational_campaign import _FakePumpTransport
from test_v2_9_8b_remaining_runtime_blocker_repair import (
    EXPIRES,
    GOV,
    SCH,
    _CampaignBase,
    _clean_goplus_extreme,
    _force_holder_extreme_ineligible,
    _seed_exact_markets_for_supply,
)


NOW = "2026-08-26T20:43:18+00:00"
CAMPAIGN = "role-complete-campaign"
RUN = "role-complete-run"
CYCLE = "role-complete-cycle"

MARKET_MINT_A = "MarketMintAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
MARKET_POOL_A = "MarketPoolAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
MARKET_MINT_B = "MarketMintBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
MARKET_POOL_B = "MarketPoolBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
MARKET_MINT_C = "MarketMintCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
MARKET_POOL_C = "MarketPoolCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
MARKET_MINT_D = "MarketMintDxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
MARKET_POOL_D = "MarketPoolDxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
PUMP_MINT = "CrR3AB6W9v2RV9btV9Egqsdij3jXNUSJba9dqKAqpump"
PUMP_POOL = "A2MoynsjruNQqDjdRQKMq8xDbFtAecE198KjuVrMBeWu"
PUMP_MINT_B = "PumpMintBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
PUMP_POOL_B = "PumpPoolBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"


def _tracking() -> TrackingFeasibility:
    return TrackingFeasibility(
        eligible=True,
        reason_code="ELIGIBLE",
        tracking_queue_id=None,
        tracking_queue_status=None,
        requalification_required=False,
        cooldown_until=None,
        assessed_at=NOW,
    )


def _market_item(
    *,
    mint: str,
    pool: str,
    request_id: int,
    response_id: int,
) -> dict[str, object]:
    return {
        "mint": mint,
        "pool": pool,
        "pumpswap_pool": pool,
        "market_identity": f"solana-mainnet:pumpswap:{pool}",
        "provenance": "FRESH_AGGREGATOR_PROTOCOL_CONFIRMED",
        "admission_authority": "MARKET_PRESENT_POOL",
        "memory_observation_eligible": True,
        "tracking_handoff_eligible": True,
        "tracking_requalification_required": False,
        "tracking_handoff_reason": "ELIGIBLE",
        "tracking_assessed_at": NOW,
        "evidence_expires_at": EXPIRES,
        "liquidity_observed_at": NOW,
        "liquidity": {
            "liquidity_usd": 5000.0,
            "source_request_id": request_id,
            "source_response_id": response_id,
            "source_status": "COMPLETE",
            "status": "LIQUIDITY_PROVEN",
        },
        "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
        "holder_condition": "HOLDER_CONCENTRATION_EXTREME",
        "holder_evidence_status": "COMPLETE",
    }


def _direct_item(
    *,
    mint: str,
    pool: str,
    market_req: int | None,
    market_resp: int | None,
    origin_req: int | None = None,
    origin_resp: int | None = None,
    pumpswap_req: int | None = None,
    pumpswap_resp: int | None = None,
) -> dict[str, object]:
    retained: dict[str, dict[str, int]] = {}
    if origin_req is not None and origin_resp is not None:
        retained["ORIGIN_LINEAGE"] = {
            "source_request_id": origin_req,
            "source_response_id": origin_resp,
        }
    if pumpswap_req is not None and pumpswap_resp is not None:
        retained["PUMPSWAP_CONFIRMATION"] = {
            "source_request_id": pumpswap_req,
            "source_response_id": pumpswap_resp,
        }
    if market_req is not None and market_resp is not None:
        retained["MARKET_OBSERVATION"] = {
            "source_request_id": market_req,
            "source_response_id": market_resp,
        }
    return {
        "mint": mint,
        "pool": pool,
        "pumpswap_pool": pool,
        "market_identity": f"solana-mainnet:pumpswap:{pool}",
        "provenance": "LATEST_GRADUATED",
        "admission_authority": "DIRECT_PUMP_PUMPSWAP",
        "memory_observation_eligible": True,
        "tracking_handoff_eligible": True,
        "tracking_requalification_required": False,
        "tracking_handoff_reason": "ELIGIBLE",
        "tracking_assessed_at": NOW,
        "evidence_expires_at": EXPIRES,
        "liquidity_observed_at": NOW,
        "retained_evidence": retained,
        "liquidity": {
            "liquidity_usd": 3454.0,
            "source_request_id": market_req,
            "source_response_id": market_resp,
            "source_status": "COMPLETE",
            "status": "LIQUIDITY_PROVEN",
        },
        "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
        "holder_condition": "HOLDER_CONCENTRATION_EXTREME",
        "holder_evidence_status": "COMPLETE",
    }


def test_case_a_market_present_complete_passes_gate() -> None:
    item = _market_item(
        mint=MARKET_MINT_A,
        pool=MARKET_POOL_A,
        request_id=1001,
        response_id=2001,
    )
    complete, exclusions = _filter_observation_rows_by_retained_role_completeness(
        [item]
    )
    assert len(complete) == 1
    assert exclusions == []
    assert complete[0]["admission_authority"] == "MARKET_PRESENT_POOL"
    roles = required_evidence_roles_for_admission_authority(
        AdmissionAuthority.MARKET_PRESENT_POOL
    )
    assert roles == (EvidenceRole.MARKET_OBSERVATION,)


def test_case_b_direct_pump_complete_passes_gate() -> None:
    item = _direct_item(
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        market_req=1101,
        market_resp=2101,
        origin_req=1102,
        origin_resp=2102,
        pumpswap_req=1103,
        pumpswap_resp=2103,
    )
    complete, exclusions = _filter_observation_rows_by_retained_role_completeness(
        [item]
    )
    assert len(complete) == 1
    assert exclusions == []
    roles = required_evidence_roles_for_admission_authority(
        AdmissionAuthority.DIRECT_PUMP_PUMPSWAP
    )
    assert set(roles) == {
        EvidenceRole.ORIGIN_LINEAGE,
        EvidenceRole.PUMPSWAP_CONFIRMATION,
        EvidenceRole.MARKET_OBSERVATION,
    }


def test_case_c_direct_pump_incomplete_excluded_before_freeze() -> None:
    incomplete = _direct_item(
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        market_req=1201,
        market_resp=2201,
        # Missing ORIGIN and PUMPSWAP intentionally.
    )
    markets = [
        _market_item(
            mint=mint,
            pool=pool,
            request_id=1300 + idx,
            response_id=2300 + idx,
        )
        for idx, (mint, pool) in enumerate(
            (
                (MARKET_MINT_A, MARKET_POOL_A),
                (MARKET_MINT_B, MARKET_POOL_B),
                (MARKET_MINT_C, MARKET_POOL_C),
                (MARKET_MINT_D, MARKET_POOL_D),
            )
        )
    ]
    complete, exclusions = _filter_observation_rows_by_retained_role_completeness(
        [incomplete, *markets]
    )
    assert PUMP_MINT not in {str(item.get("mint")) for item in complete}
    assert any(
        row.get("mint") == PUMP_MINT
        and row.get("disposition")
        == RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE
        and "ORIGIN_LINEAGE" in (row.get("missing_roles") or [])
        for row in exclusions
    )
    frozen = freeze_eligible_reserve(
        complete,
        cycle_seed="role-complete-case-c",
        at=NOW,
    )
    assert all(str(item.get("mint")) != PUMP_MINT for item in frozen.selected)
    assert all(
        str(item.get("mint")) != PUMP_MINT for item in frozen.alternates[:2]
    )


def test_case_d_insufficient_role_complete_depth_blocks_before_freeze() -> None:
    rows = [
        _market_item(
            mint=MARKET_MINT_A,
            pool=MARKET_POOL_A,
            request_id=1401,
            response_id=2401,
        ),
        _market_item(
            mint=MARKET_MINT_B,
            pool=MARKET_POOL_B,
            request_id=1402,
            response_id=2402,
        ),
        _direct_item(
            mint=PUMP_MINT,
            pool=PUMP_POOL,
            market_req=1403,
            market_resp=2403,
        ),
        _direct_item(
            mint=PUMP_MINT_B,
            pool=PUMP_POOL_B,
            market_req=1404,
            market_resp=2404,
        ),
    ]
    complete, exclusions = _filter_observation_rows_by_retained_role_completeness(
        rows
    )
    assert len(complete) == 2
    assert len(exclusions) == 2
    frozen = freeze_eligible_reserve(
        complete,
        cycle_seed="role-complete-case-d",
        at=NOW,
    )
    assert frozen.selected == ()
    assert bool(frozen.selection_authority.get("coverage_blocker")) is True
    assert (
        int(frozen.selection_authority.get("valid_fresh_unique_observation_depth") or 0)
        == 2
    )


def test_case_e_report_only_alternate_does_not_terminalize_selected(
    tmp_path,
) -> None:
    db_path = tmp_path / "alternate-authority.sqlite3"
    apply_migrations(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    def _persist(role: str, source: str, kind: str, mint: str, pool: str) -> tuple[int, int, str]:
        payload = {
            "chain": "solana",
            "mint": mint,
            "base_mint": mint,
            "pool": pool,
            "pair_address": pool,
            "observed_at": NOW,
        }
        payload_json = json.dumps(payload, sort_keys=True)
        digest = hashlib.sha256(payload_json.encode()).hexdigest()
        request = conn.execute(
            """INSERT INTO printer_source_requests(
                   source_name,request_kind,requested_at,request_key,
                   source_status,data_quality_label
               ) VALUES (?,?,?,?,'COMPLETE','CLEAN_DATA')""",
            (source, kind, NOW, f"{mint}:{role}"),
        )
        response = conn.execute(
            """INSERT INTO printer_source_responses(
                   source_request_id,source_name,received_at,status_code,
                   source_status,data_quality_label,response_hash,
                   normalized_payload_json
               ) VALUES (?,?,?,200,'COMPLETE','CLEAN_DATA',?,?)""",
            (int(request.lastrowid), source, NOW, digest, payload_json),
        )
        return int(request.lastrowid), int(response.lastrowid), digest

    selected_items = []
    manifest = []
    for mint, pool, source in (
        (MARKET_MINT_A, MARKET_POOL_A, "dexscreener"),
        (MARKET_MINT_B, MARKET_POOL_B, "geckoterminal"),
    ):
        req, resp, digest = _persist(
            "MARKET_OBSERVATION", source, "candidate_market_batch", mint, pool
        )
        selected_items.append(
            _market_item(mint=mint, pool=pool, request_id=req, response_id=resp)
        )
        transport_key = (
            "ROLE_COMPLETE",
            source,
            source,
            "candidate_market_batch",
            "fixture",
            1,
            "MINT",
            mint,
            32,
            1,
            "COMPLETE",
            None,
        )
        manifest.append(
            {
                "source_request_id": req,
                "source_name": source,
                "request_kind": "candidate_market_batch",
                "logical_stage_id": f"{CAMPAIGN}|{RUN}|{CYCLE}|MARKET|{mint}",
                "transport_identity_count": 1,
                "transport_identity_keys": [list(transport_key)],
                "terminal_status": "COMPLETED",
            }
        )
        # Keep digest available for activation reference construction path.
        selected_items[-1]["_digest"] = digest

    # Incomplete DIRECT_PUMP alternate: missing origin/pumpswap retained IDs.
    alternate_incomplete = _direct_item(
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        market_req=None,
        market_resp=None,
    )
    alternate_market = _market_item(
        mint=MARKET_MINT_C,
        pool=MARKET_POOL_C,
        request_id=999001,
        response_id=999002,
    )
    frozen = SimpleNamespace(
        selected=tuple(selected_items),
        alternates=(alternate_incomplete, alternate_market),
        frozen_at=NOW,
    )
    activation = _build_frozen_memory_activation_set(
        conn,
        frozen_reserve=frozen,
        readiness_id=f"{RUN}:{CYCLE}:pilot-input",
        selection_seed="role-complete-case-e",
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
        manifest=manifest,
        measured_transport_identity_keys=(),
        frozen_at=NOW,
        expires_at=EXPIRES,
    )
    assert len(activation.selected) == 2
    assert len(activation.alternates) == 2
    assert activation.alternates[0].mint == PUMP_MINT
    # Report-only alternate may lack retained refs; selected remain activation authority.
    assert activation.selected[0].retained_evidence_references
    assert activation.selected[1].retained_evidence_references
    conn.close()


def test_case_f_final_validator_still_fails_role_missing(tmp_path) -> None:
    db_path = tmp_path / "final-defense.sqlite3"
    apply_migrations(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    def _ref(
        *,
        role: EvidenceRole,
        mint: str,
        pool: str,
        source: str,
        kind: str,
    ) -> tuple[RetainedEvidenceReference, ManifestRequestEntry]:
        payload = {
            "chain": "solana",
            "mint": mint,
            "base_mint": mint,
            "pool": pool,
            "pair_address": pool,
            "observed_at": NOW,
        }
        payload_json = json.dumps(payload, sort_keys=True)
        digest = hashlib.sha256(payload_json.encode()).hexdigest()
        request = conn.execute(
            """INSERT INTO printer_source_requests(
                   source_name,request_kind,requested_at,request_key,
                   source_status,data_quality_label
               ) VALUES (?,?,?,?,'COMPLETE','CLEAN_DATA')""",
            (source, kind, NOW, f"{mint}:{role.value}"),
        )
        response = conn.execute(
            """INSERT INTO printer_source_responses(
                   source_request_id,source_name,received_at,status_code,
                   source_status,data_quality_label,response_hash,
                   normalized_payload_json
               ) VALUES (?,?,?,200,'COMPLETE','CLEAN_DATA',?,?)""",
            (int(request.lastrowid), source, NOW, digest, payload_json),
        )
        key = (
            "FINAL_DEFENSE",
            source,
            source,
            kind,
            "fixture",
            1,
            "MINT",
            mint,
            16,
            1,
            "COMPLETE",
            None,
        )
        reference = RetainedEvidenceReference(
            evidence_role=role,
            source_name=source,
            request_kind=kind,
            source_request_id=int(request.lastrowid),
            source_response_id=int(response.lastrowid),
            source_failure_id=None,
            transport_identity_keys=(key,),
            observed_at=NOW,
            raw_payload_hash=digest,
            target_mint=mint,
            target_pool=pool,
            campaign_id=CAMPAIGN,
            campaign_run_id=RUN,
            cycle_id=CYCLE,
        )
        entry = ManifestRequestEntry(
            source_request_id=int(request.lastrowid),
            source_name=source,
            request_kind=kind,
            logical_stage_id=f"{CAMPAIGN}|{RUN}|{CYCLE}|{role.value}|1",
            transport_identity_count=1,
            transport_identity_keys=(key,),
            terminal_status="COMPLETED",
        )
        return reference, entry

    market_a, entry_a = _ref(
        role=EvidenceRole.MARKET_OBSERVATION,
        mint=MARKET_MINT_A,
        pool=MARKET_POOL_A,
        source="dexscreener",
        kind="candidate_market_batch",
    )
    market_b, entry_b = _ref(
        role=EvidenceRole.MARKET_OBSERVATION,
        mint=MARKET_MINT_B,
        pool=MARKET_POOL_B,
        source="geckoterminal",
        kind="candidate_market_batch",
    )
    incomplete = FrozenMemoryActivationCandidate(
        slot_ordinal=1,
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        market_identity=f"solana-mainnet:pumpswap:{PUMP_POOL}",
        lifecycle_identity="PUMPSWAP_GRADUATED_CONFIRMED",
        activation_route="DIRECT_PUMP_PUMPSWAP",
        provenance="LATEST_GRADUATED",
        memory_observation_eligible=True,
        fully_eligible=False,
        holder_condition="HOLDER_CONCENTRATION_EXTREME",
        holder_evidence_status="COMPLETE",
        future_action_eligibility="BLOCKED_OR_UNKNOWN",
        evidence_expires_at=EXPIRES,
        liquidity_observed_at=NOW,
        tracking_feasibility=_tracking(),
        retained_evidence_references=(market_a,),  # missing ORIGIN + PUMPSWAP
        admission_authority=AdmissionAuthority.DIRECT_PUMP_PUMPSWAP,
        claims_pump_origin=True,
        claims_pumpswap_graduation=True,
    )
    complete_market = FrozenMemoryActivationCandidate(
        slot_ordinal=2,
        mint=MARKET_MINT_B,
        pool=MARKET_POOL_B,
        market_identity=f"solana-mainnet:pumpswap:{MARKET_POOL_B}",
        lifecycle_identity="PRESENT_POOL_CONFIRMED",
        activation_route="MARKET_PRESENT_POOL",
        provenance="UNKNOWN_ORIGIN",
        memory_observation_eligible=True,
        fully_eligible=False,
        holder_condition="HOLDER_CONCENTRATION_EXTREME",
        holder_evidence_status="COMPLETE",
        future_action_eligibility="BLOCKED_OR_UNKNOWN",
        evidence_expires_at=EXPIRES,
        liquidity_observed_at=NOW,
        tracking_feasibility=_tracking(),
        retained_evidence_references=(market_b,),
        admission_authority=AdmissionAuthority.MARKET_PRESENT_POOL,
        claims_pump_origin=False,
        claims_pumpswap_graduation=False,
    )
    assert set(required_evidence_roles_for_candidate(incomplete)) == {
        EvidenceRole.ORIGIN_LINEAGE,
        EvidenceRole.PUMPSWAP_CONFIRMATION,
        EvidenceRole.MARKET_OBSERVATION,
    }
    activation = FrozenMemoryActivationSet(
        activation_purpose=ActivationPurpose.MEMORY_OBSERVATION,
        readiness_id="final-defense",
        selection_seed="role-complete-case-f",
        selected=(incomplete, complete_market),
        alternates=(
            replace(complete_market, slot_ordinal=3, mint=MARKET_MINT_C, pool=MARKET_POOL_C),
            replace(complete_market, slot_ordinal=4, mint=MARKET_MINT_D, pool=MARKET_POOL_D),
        ),
        manifest_request_ids=(entry_a.source_request_id, entry_b.source_request_id),
        manifest_transport_identity_keys=(
            entry_a.transport_identity_keys[0],
            entry_b.transport_identity_keys[0],
        ),
        frozen_at=NOW,
        expires_at=EXPIRES,
        manifest_entries=(entry_a, entry_b),
    )
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            conn,
            activation,
            now=NOW,
            expected_ownership=(CAMPAIGN, RUN, CYCLE),
        )
    assert exc.value.code == "RETAINED_EVIDENCE_ROLE_MISSING"
    conn.close()


def test_assess_helper_matches_canonical_matrix() -> None:
    assessment = assess_retained_evidence_role_completeness(
        admission_authority=AdmissionAuthority.DIRECT_PUMP_PUMPSWAP,
        present_roles={EvidenceRole.MARKET_OBSERVATION},
        mint=PUMP_MINT,
    )
    assert assessment["complete"] is False
    assert assessment["disposition"] == RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE
    assert assessment["missing_roles"] == (
        "ORIGIN_LINEAGE",
        "PUMPSWAP_CONFIRMATION",
    )


def _production_supply_with_incomplete_direct() -> GraduatedSupply:
    inventory = (
        (MARKET_MINT_A, MARKET_POOL_A, "MARKET_PRESENT_POOL", True),
        (MARKET_MINT_B, MARKET_POOL_B, "MARKET_PRESENT_POOL", True),
        (MARKET_MINT_C, MARKET_POOL_C, "MARKET_PRESENT_POOL", True),
        (MARKET_MINT_D, MARKET_POOL_D, "MARKET_PRESENT_POOL", True),
        (PUMP_MINT, PUMP_POOL, "DIRECT_PUMP_PUMPSWAP", False),
    )
    proofs: dict[str, FixturePumpSwapProof] = {}
    origins: list[FixtureOriginProof] = []
    candidates: dict[str, dict[str, object]] = {}
    epoch = int(datetime.fromisoformat(e8.NOW.replace("Z", "+00:00")).timestamp())
    for i, (mint, pool, authority, complete_market) in enumerate(inventory):
        proofs[mint] = FixturePumpSwapProof(mint=mint, pool_address=pool)
        origins.append(
            FixtureOriginProof(
                mint=mint,
                signature=f"sig{i}" + "1" * 80,
                slot=432_500_000 + i,
                block_time=epoch,
                bonding_curve=pool,
                confirmed=True,
            )
        )
        if authority == "MARKET_PRESENT_POOL":
            candidates[mint.lower()] = _market_item(
                mint=mint,
                pool=pool,
                request_id=1500 + i,
                response_id=2500 + i,
            )
        else:
            candidates[mint.lower()] = _direct_item(
                mint=mint,
                pool=pool,
                market_req=1600 if complete_market else 1600,
                market_resp=2600 if complete_market else 2600,
                # Intentionally omit ORIGIN / PUMPSWAP for the DIRECT_PUMP nominee.
            )
    return GraduatedSupply(
        ready=True,
        terminal="GRADUATED_SUPPLY_READY",
        graduated_supply=tuple(origins),
        graduation_proofs=proofs,
        candidate_a={"mint": origins[0].mint, "pair_address": MARKET_POOL_A},
        candidate_b={"mint": origins[1].mint, "pair_address": MARKET_POOL_B},
        two_candidate_selection={"ready": True},
        handoff_readiness={"atomic_two_slot_ready": True},
        discovery_report={},
        front_door_report={"generated_at": e8.NOW},
        diagnostics={
            "permanent_availability": True,
            "selection_floor_usd": 3000.0,
            "stage_local_source_requests": 0,
            "stage_operations_used": {},
        },
        holder_reserve_supply=tuple(origins),
        holder_reserve_candidates=candidates,
    )


def test_production_caller_excludes_incomplete_direct_before_freeze() -> None:
    base = _CampaignBase()
    base.setUp()
    try:
        supply = _production_supply_with_incomplete_direct()
        _seed_exact_markets_for_supply(base.db, supply)
        owner = AuthoritativeLiveOperationalCampaignOwner()
        _force_holder_extreme_ineligible(owner, supply.holder_reserve_supply)
        observed: list[dict[str, object]] = []
        real_freeze = freeze_eligible_reserve_for_campaign

        def _spy(connection, candidates, **kwargs):
            mints = tuple(str(item.get("mint") or "") for item in candidates)
            observed.append(
                {
                    "candidate_mints": mints,
                    "authorities": tuple(
                        str(item.get("admission_authority") or "")
                        for item in candidates
                    ),
                }
            )
            assert PUMP_MINT not in mints
            return real_freeze(connection, candidates, **kwargs)

        with patch(
            "printer_v1.discovery.permanent_discovery_availability."
            "freeze_eligible_reserve_for_campaign",
            side_effect=_spy,
        ):
            result = owner.run(
                mode=PILOT_INPUT_READINESS,
                command=base.command,
                pump_transport=_FakePumpTransport([], {}),
                secondary_transport=None,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="role-complete-production",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=base.backup,
                lifecycle_kwargs={
                    "context_adapter_factories": _clean_goplus_extreme()
                },
                graduated_supply=supply,
            )
        assert len(observed) == 1
        assert PUMP_MINT not in observed[0]["candidate_mints"]
        life = result.lifecycle
        diag = dict(
            life.get("candidate_supply_diagnostics")
            or life.get("graduated_supply_diagnostics")
            or {}
        )
        pre_freeze = diag.get("retained_evidence_role_pre_freeze") or {}
        exclusions = list(pre_freeze.get("exclusions") or [])
        assert any(
            row.get("mint") == PUMP_MINT
            and row.get("disposition")
            == RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE
            for row in exclusions
        )
        pre_admission = life.get("pre_lifecycle_admission") or {}
        assert "retained_evidence_role_pre_freeze" in pre_admission
        assert life.get("lifecycle_started") is False
    finally:
        base.tearDown()

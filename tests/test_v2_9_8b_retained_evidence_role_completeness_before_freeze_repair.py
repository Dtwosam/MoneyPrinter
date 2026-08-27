"""V2-9.8B retained-evidence role completeness before freeze repair.

Cases A-K plus production-caller coverage. Role-complete fixtures create real
disposable-DB request/response rows; fake numeric IDs alone never qualify.
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


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "role-complete.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


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


def _persist_role(
    connection: sqlite3.Connection,
    *,
    role: str,
    source: str,
    kind: str,
    mint: str,
    pool: str,
) -> tuple[int, int, str]:
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
    request = connection.execute(
        """INSERT INTO printer_source_requests(
               source_name,request_kind,requested_at,request_key,
               source_status,data_quality_label
           ) VALUES (?,?,?,?,'COMPLETE','CLEAN_DATA')""",
        (source, kind, NOW, f"{mint}:{role}:{source}"),
    )
    request_id = int(request.lastrowid)
    response = connection.execute(
        """INSERT INTO printer_source_responses(
               source_request_id,source_name,received_at,status_code,
               source_status,data_quality_label,response_hash,
               normalized_payload_json
           ) VALUES (?,?,?,200,'COMPLETE','CLEAN_DATA',?,?)""",
        (request_id, source, NOW, digest, payload_json),
    )
    return request_id, int(response.lastrowid), digest


def _market_item(
    connection: sqlite3.Connection,
    *,
    mint: str,
    pool: str,
    source: str = "dexscreener",
) -> dict[str, object]:
    req, resp, _digest = _persist_role(
        connection,
        role="MARKET_OBSERVATION",
        source=source,
        kind="candidate_market_batch",
        mint=mint,
        pool=pool,
    )
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
            "source_request_id": req,
            "source_response_id": resp,
            "source_status": "COMPLETE",
            "status": "LIQUIDITY_PROVEN",
        },
        "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
        "holder_condition": "HOLDER_CONCENTRATION_EXTREME",
        "holder_evidence_status": "COMPLETE",
    }


def _direct_item(
    connection: sqlite3.Connection | None,
    *,
    mint: str,
    pool: str,
    include_origin: bool = True,
    include_pumpswap: bool = True,
    include_market: bool = True,
    market_req: int | None = None,
    market_resp: int | None = None,
    origin_req: int | None = None,
    origin_resp: int | None = None,
    pumpswap_req: int | None = None,
    pumpswap_resp: int | None = None,
) -> dict[str, object]:
    retained: dict[str, dict[str, int]] = {}
    if connection is not None:
        if include_origin:
            origin_req, origin_resp, _ = _persist_role(
                connection,
                role="ORIGIN_LINEAGE",
                source="solana_rpc",
                kind="restored_pump_migration_transaction",
                mint=mint,
                pool=pool,
            )
        if include_pumpswap:
            pumpswap_req, pumpswap_resp, _ = _persist_role(
                connection,
                role="PUMPSWAP_CONFIRMATION",
                source="solana_rpc",
                kind="pumpswap_pool_account_batch",
                mint=mint,
                pool=pool,
            )
        if include_market:
            market_req, market_resp, _ = _persist_role(
                connection,
                role="MARKET_OBSERVATION",
                source="dexscreener",
                kind="candidate_market_batch",
                mint=mint,
                pool=pool,
            )
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


def test_case_a_market_present_complete_passes_gate(db) -> None:
    item = _market_item(db, mint=MARKET_MINT_A, pool=MARKET_POOL_A)
    complete, exclusions = _filter_observation_rows_by_retained_role_completeness(
        db, [item], now=NOW
    )
    assert len(complete) == 1
    assert exclusions == []
    assert complete[0]["admission_authority"] == "MARKET_PRESENT_POOL"
    assert required_evidence_roles_for_admission_authority(
        AdmissionAuthority.MARKET_PRESENT_POOL
    ) == (EvidenceRole.MARKET_OBSERVATION,)


def test_case_b_direct_pump_complete_passes_gate(db) -> None:
    item = _direct_item(db, mint=PUMP_MINT, pool=PUMP_POOL)
    complete, exclusions = _filter_observation_rows_by_retained_role_completeness(
        db, [item], now=NOW
    )
    assert len(complete) == 1
    assert exclusions == []
    assert set(
        required_evidence_roles_for_admission_authority(
            AdmissionAuthority.DIRECT_PUMP_PUMPSWAP
        )
    ) == {
        EvidenceRole.ORIGIN_LINEAGE,
        EvidenceRole.PUMPSWAP_CONFIRMATION,
        EvidenceRole.MARKET_OBSERVATION,
    }


def test_case_c_direct_pump_incomplete_excluded_before_freeze(db) -> None:
    incomplete = _direct_item(
        db,
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        include_origin=False,
        include_pumpswap=False,
        include_market=True,
    )
    markets = [
        _market_item(db, mint=mint, pool=pool)
        for mint, pool in (
            (MARKET_MINT_A, MARKET_POOL_A),
            (MARKET_MINT_B, MARKET_POOL_B),
            (MARKET_MINT_C, MARKET_POOL_C),
            (MARKET_MINT_D, MARKET_POOL_D),
        )
    ]
    complete, exclusions = _filter_observation_rows_by_retained_role_completeness(
        db, [incomplete, *markets], now=NOW
    )
    assert PUMP_MINT not in {str(item.get("mint")) for item in complete}
    assert any(
        row.get("mint") == PUMP_MINT
        and row.get("disposition") == RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE
        and "ORIGIN_LINEAGE" in (row.get("missing_roles") or [])
        for row in exclusions
    )
    frozen = freeze_eligible_reserve(
        complete, cycle_seed="role-complete-case-c", at=NOW
    )
    assert all(str(item.get("mint")) != PUMP_MINT for item in frozen.selected)
    assert all(str(item.get("mint")) != PUMP_MINT for item in frozen.alternates[:2])


def test_case_d_insufficient_role_complete_depth_blocks_before_freeze(db) -> None:
    rows = [
        _market_item(db, mint=MARKET_MINT_A, pool=MARKET_POOL_A),
        _market_item(db, mint=MARKET_MINT_B, pool=MARKET_POOL_B),
        _direct_item(
            db,
            mint=PUMP_MINT,
            pool=PUMP_POOL,
            include_origin=False,
            include_pumpswap=False,
        ),
        _direct_item(
            db,
            mint=PUMP_MINT_B,
            pool=PUMP_POOL_B,
            include_origin=False,
            include_pumpswap=False,
        ),
    ]
    complete, exclusions = _filter_observation_rows_by_retained_role_completeness(
        db, rows, now=NOW
    )
    assert len(complete) == 2
    assert len(exclusions) == 2
    frozen = freeze_eligible_reserve(
        complete, cycle_seed="role-complete-case-d", at=NOW
    )
    assert frozen.selected == ()
    assert bool(frozen.selection_authority.get("coverage_blocker")) is True


def test_case_e_report_only_alternate_does_not_terminalize_selected(db) -> None:
    selected_items = []
    manifest = []
    for mint, pool, source in (
        (MARKET_MINT_A, MARKET_POOL_A, "dexscreener"),
        (MARKET_MINT_B, MARKET_POOL_B, "geckoterminal"),
    ):
        item = _market_item(db, mint=mint, pool=pool, source=source)
        selected_items.append(item)
        req = int(item["liquidity"]["source_request_id"])
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
    alternate_incomplete = {
        "mint": PUMP_MINT,
        "pool": PUMP_POOL,
        "admission_authority": "DIRECT_PUMP_PUMPSWAP",
        "market_identity": f"solana-mainnet:pumpswap:{PUMP_POOL}",
        "provenance": "LATEST_GRADUATED",
        "memory_observation_eligible": True,
        "tracking_handoff_eligible": True,
        "evidence_expires_at": EXPIRES,
        "liquidity": {},
        "retained_evidence": {},
    }
    alternate_market = _market_item(db, mint=MARKET_MINT_C, pool=MARKET_POOL_C)
    frozen = SimpleNamespace(
        selected=tuple(selected_items),
        alternates=(alternate_incomplete, alternate_market),
        frozen_at=NOW,
    )
    activation = _build_frozen_memory_activation_set(
        db,
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
    assert activation.alternates[0].admission_authority is (
        AdmissionAuthority.DIRECT_PUMP_PUMPSWAP
    )
    assert activation.selected[0].retained_evidence_references
    assert activation.selected[1].retained_evidence_references


def test_case_f_final_validator_still_fails_role_missing(db) -> None:
    def _ref(*, role: EvidenceRole, mint: str, pool: str, source: str, kind: str):
        req, resp, digest = _persist_role(
            db, role=role.value, source=source, kind=kind, mint=mint, pool=pool
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
            source_request_id=req,
            source_response_id=resp,
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
            source_request_id=req,
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
    # Force incomplete DIRECT_PUMP selected candidate: only market role retained.
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
        retained_evidence_references=(
            replace(market_a, target_mint=PUMP_MINT, target_pool=PUMP_POOL),
        ),
        admission_authority=AdmissionAuthority.DIRECT_PUMP_PUMPSWAP,
        claims_pump_origin=True,
        claims_pumpswap_graduation=True,
    )
    market_b, entry_b = _ref(
        role=EvidenceRole.MARKET_OBSERVATION,
        mint=MARKET_MINT_B,
        pool=MARKET_POOL_B,
        source="geckoterminal",
        kind="candidate_market_batch",
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
            replace(
                complete_market,
                slot_ordinal=3,
                mint=MARKET_MINT_C,
                pool=MARKET_POOL_C,
            ),
            replace(
                complete_market,
                slot_ordinal=4,
                mint=MARKET_MINT_D,
                pool=MARKET_POOL_D,
            ),
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
            db,
            activation,
            now=NOW,
            expected_ownership=(CAMPAIGN, RUN, CYCLE),
        )
    assert exc.value.code == "RETAINED_EVIDENCE_ROLE_MISSING"


def test_case_g_nonexistent_ids_fail_pre_freeze(db) -> None:
    item = _direct_item(
        None,
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        market_req=999001,
        market_resp=999002,
        origin_req=999003,
        origin_resp=999004,
        pumpswap_req=999005,
        pumpswap_resp=999006,
    )
    complete, exclusions = _filter_observation_rows_by_retained_role_completeness(
        db, [item], now=NOW
    )
    assert complete == []
    assert exclusions[0]["mint"] == PUMP_MINT
    failures = exclusions[0]["qualification_failures"]
    assert failures["ORIGIN_LINEAGE"] == "RETAINED_REQUEST_NOT_FOUND"


def test_case_h_mismatched_request_response_fails_pre_freeze(db) -> None:
    origin_req, _origin_resp, _ = _persist_role(
        db,
        role="ORIGIN_LINEAGE",
        source="solana_rpc",
        kind="restored_pump_migration_transaction",
        mint=PUMP_MINT,
        pool=PUMP_POOL,
    )
    _other_req, other_resp, _ = _persist_role(
        db,
        role="ORIGIN_LINEAGE",
        source="solana_rpc",
        kind="restored_pump_migration_transaction",
        mint=PUMP_MINT_B,
        pool=PUMP_POOL_B,
    )
    pumpswap_req, pumpswap_resp, _ = _persist_role(
        db,
        role="PUMPSWAP_CONFIRMATION",
        source="solana_rpc",
        kind="pumpswap_pool_account_batch",
        mint=PUMP_MINT,
        pool=PUMP_POOL,
    )
    market_req, market_resp, _ = _persist_role(
        db,
        role="MARKET_OBSERVATION",
        source="dexscreener",
        kind="candidate_market_batch",
        mint=PUMP_MINT,
        pool=PUMP_POOL,
    )
    item = _direct_item(
        None,
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        origin_req=origin_req,
        origin_resp=other_resp,  # response belongs to a different request
        pumpswap_req=pumpswap_req,
        pumpswap_resp=pumpswap_resp,
        market_req=market_req,
        market_resp=market_resp,
    )
    complete, exclusions = _filter_observation_rows_by_retained_role_completeness(
        db, [item], now=NOW
    )
    assert complete == []
    assert PUMP_MINT not in {
        str(row.get("mint"))
        for row in freeze_eligible_reserve(
            complete, cycle_seed="case-h", at=NOW
        ).selected
    }
    assert (
        exclusions[0]["qualification_failures"]["ORIGIN_LINEAGE"]
        == "RETAINED_RESPONSE_CONTRACT_MISMATCH"
    )


def test_case_i_wrong_candidate_evidence_fails_pre_freeze(db) -> None:
    # Evidence payload is bound to another mint/pool.
    wrong_req, wrong_resp, _ = _persist_role(
        db,
        role="MARKET_OBSERVATION",
        source="dexscreener",
        kind="candidate_market_batch",
        mint=MARKET_MINT_B,
        pool=MARKET_POOL_B,
    )
    item = {
        "mint": MARKET_MINT_A,
        "pool": MARKET_POOL_A,
        "admission_authority": "MARKET_PRESENT_POOL",
        "memory_observation_eligible": True,
        "tracking_handoff_eligible": True,
        "evidence_expires_at": EXPIRES,
        "liquidity": {
            "source_request_id": wrong_req,
            "source_response_id": wrong_resp,
        },
    }
    complete, exclusions = _filter_observation_rows_by_retained_role_completeness(
        db, [item], now=NOW
    )
    assert complete == []
    assert exclusions[0]["qualification_failures"]["MARKET_OBSERVATION"] in {
        "MARKET_RESPONSE_NO_EXACT_MEMBER_MATCH",
        "RETAINED_RESPONSE_TARGET_MISMATCH",
    }


def test_case_j_role_authority_consistency_fail_closed(db) -> None:
    item = _market_item(db, mint=MARKET_MINT_A, pool=MARKET_POOL_A)
    item["claims_pump_origin"] = True
    item["claims_pumpswap_graduation"] = True
    complete, exclusions = _filter_observation_rows_by_retained_role_completeness(
        db, [item], now=NOW
    )
    assert complete == []
    assert exclusions[0]["detail"] == "ADMISSION_AUTHORITY_CLAIMS_INCONSISTENT"

    candidate = FrozenMemoryActivationCandidate(
        slot_ordinal=1,
        mint=MARKET_MINT_A,
        pool=MARKET_POOL_A,
        market_identity=f"solana-mainnet:pumpswap:{MARKET_POOL_A}",
        lifecycle_identity="PRESENT_POOL_CONFIRMED",
        activation_route="MARKET_PRESENT_POOL",
        provenance="UNKNOWN_ORIGIN",
        memory_observation_eligible=True,
        fully_eligible=False,
        holder_condition="UNKNOWN",
        holder_evidence_status="UNKNOWN",
        future_action_eligibility="BLOCKED_OR_UNKNOWN",
        evidence_expires_at=EXPIRES,
        liquidity_observed_at=NOW,
        tracking_feasibility=_tracking(),
        retained_evidence_references=(),
        admission_authority=AdmissionAuthority.MARKET_PRESENT_POOL,
        claims_pump_origin=True,
        claims_pumpswap_graduation=False,
    )
    with pytest.raises(MemoryObservationActivationError) as exc:
        required_evidence_roles_for_candidate(candidate)
    assert exc.value.code == "ADMISSION_AUTHORITY_CLAIMS_INCONSISTENT"


def test_case_l_missing_authority_excluded_before_freeze(db) -> None:
    item = _direct_item(db, mint=PUMP_MINT, pool=PUMP_POOL)
    item.pop("admission_authority", None)
    complete, exclusions = _filter_observation_rows_by_retained_role_completeness(
        db, [item], now=NOW
    )
    assert complete == []
    assert exclusions[0]["detail"] == "ADMISSION_AUTHORITY_MISSING"
    assert exclusions[0]["admission_authority"] is None
    # Must not be rewritten/inferred as DIRECT_PUMP.
    assert "DIRECT_PUMP_PUMPSWAP" not in str(exclusions[0].get("admission_authority"))


def test_case_m_wrong_request_kind_does_not_qualify_origin(db) -> None:
    # Valid PumpSwap confirmation evidence, but claimed as ORIGIN_LINEAGE.
    pumpswap_req, pumpswap_resp, _ = _persist_role(
        db,
        role="PUMPSWAP_CONFIRMATION",
        source="solana_rpc",
        kind="pumpswap_pool_account_batch",
        mint=PUMP_MINT,
        pool=PUMP_POOL,
    )
    market_req, market_resp, _ = _persist_role(
        db,
        role="MARKET_OBSERVATION",
        source="dexscreener",
        kind="candidate_market_batch",
        mint=PUMP_MINT,
        pool=PUMP_POOL,
    )
    item = _direct_item(
        None,
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        origin_req=pumpswap_req,
        origin_resp=pumpswap_resp,
        pumpswap_req=pumpswap_req,
        pumpswap_resp=pumpswap_resp,
        market_req=market_req,
        market_resp=market_resp,
    )
    complete, exclusions = _filter_observation_rows_by_retained_role_completeness(
        db, [item], now=NOW
    )
    assert complete == []
    assert (
        exclusions[0]["qualification_failures"]["ORIGIN_LINEAGE"]
        == "RETAINED_ROLE_SOURCE_KIND_MISMATCH"
    )


def test_case_n_cross_role_reuse_only_true_role_qualifies(db) -> None:
    pumpswap_req, pumpswap_resp, _ = _persist_role(
        db,
        role="PUMPSWAP_CONFIRMATION",
        source="solana_rpc",
        kind="pumpswap_pool_account_batch",
        mint=PUMP_MINT,
        pool=PUMP_POOL,
    )
    market_req, market_resp, _ = _persist_role(
        db,
        role="MARKET_OBSERVATION",
        source="dexscreener",
        kind="candidate_market_batch",
        mint=PUMP_MINT,
        pool=PUMP_POOL,
    )
    # Reuse the PumpSwap pair under ORIGIN_LINEAGE as well.
    item = _direct_item(
        None,
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        origin_req=pumpswap_req,
        origin_resp=pumpswap_resp,
        pumpswap_req=pumpswap_req,
        pumpswap_resp=pumpswap_resp,
        market_req=market_req,
        market_resp=market_resp,
    )
    complete, exclusions = _filter_observation_rows_by_retained_role_completeness(
        db, [item], now=NOW
    )
    assert complete == []
    failures = exclusions[0]["qualification_failures"]
    assert failures["ORIGIN_LINEAGE"] == "RETAINED_ROLE_SOURCE_KIND_MISMATCH"
    assert "PUMPSWAP_CONFIRMATION" not in failures
    assert "MARKET_OBSERVATION" not in failures
    assert "ORIGIN_LINEAGE" in exclusions[0]["missing_roles"]
    assert "PUMPSWAP_CONFIRMATION" in exclusions[0]["present_roles"]
    assert "MARKET_OBSERVATION" in exclusions[0]["present_roles"]


def test_case_o_valid_production_shaped_role_kinds_qualify(db) -> None:
    from printer_v1.discovery.memory_observation_activation import (
        retained_evidence_role_source_kind_bindings,
        EvidenceRole,
    )

    bindings = retained_evidence_role_source_kind_bindings()
    assert (
        "solana_rpc",
        "restored_pump_migration_transaction",
    ) in bindings[EvidenceRole.ORIGIN_LINEAGE]
    assert (
        "solana_rpc",
        "pumpswap_pool_account_batch",
    ) in bindings[EvidenceRole.PUMPSWAP_CONFIRMATION]
    assert (
        "dexscreener",
        "candidate_market_batch",
    ) in bindings[EvidenceRole.MARKET_OBSERVATION]
    item = _direct_item(db, mint=PUMP_MINT, pool=PUMP_POOL)
    complete, exclusions = _filter_observation_rows_by_retained_role_completeness(
        db, [item], now=NOW
    )
    assert exclusions == []
    assert len(complete) == 1


def test_case_k_alternate_diagnostic_safety_no_authority_rewrite(db) -> None:
    selected_items = [
        _market_item(db, mint=MARKET_MINT_A, pool=MARKET_POOL_A),
        _market_item(db, mint=MARKET_MINT_B, pool=MARKET_POOL_B, source="geckoterminal"),
    ]
    manifest = []
    for item in selected_items:
        source = "dexscreener" if item["mint"] == MARKET_MINT_A else "geckoterminal"
        req = int(item["liquidity"]["source_request_id"])
        key = (
            "ROLE_COMPLETE",
            source,
            source,
            "candidate_market_batch",
            "fixture",
            1,
            "MINT",
            item["mint"],
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
                "logical_stage_id": f"{CAMPAIGN}|{RUN}|{CYCLE}|MARKET|{item['mint']}",
                "transport_identity_count": 1,
                "transport_identity_keys": [list(key)],
                "terminal_status": "COMPLETED",
            }
        )
    missing_refs_alternate = {
        "mint": PUMP_MINT,
        "pool": PUMP_POOL,
        "admission_authority": "DIRECT_PUMP_PUMPSWAP",
        "market_identity": f"solana-mainnet:pumpswap:{PUMP_POOL}",
        "evidence_expires_at": EXPIRES,
        "liquidity": {},
        "retained_evidence": {},
        "memory_observation_eligible": True,
        "tracking_handoff_eligible": True,
    }
    unsupported_alternate = {
        "mint": MARKET_MINT_C,
        "pool": MARKET_POOL_C,
        "admission_authority": "NOT_A_REAL_AUTHORITY",
        "market_identity": f"solana-mainnet:pumpswap:{MARKET_POOL_C}",
        "evidence_expires_at": EXPIRES,
        "liquidity": {},
        "retained_evidence": {},
        "memory_observation_eligible": True,
        "tracking_handoff_eligible": True,
    }
    frozen_ok = SimpleNamespace(
        selected=tuple(selected_items),
        alternates=(missing_refs_alternate, selected_items[0]),
        frozen_at=NOW,
    )
    activation = _build_frozen_memory_activation_set(
        db,
        frozen_reserve=frozen_ok,
        readiness_id="case-k",
        selection_seed="case-k",
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
        manifest=manifest,
        measured_transport_identity_keys=(),
        frozen_at=NOW,
        expires_at=EXPIRES,
    )
    assert activation.alternates[0].admission_authority is (
        AdmissionAuthority.DIRECT_PUMP_PUMPSWAP
    )
    # Soft report-only path preserves authority and does not invent retained
    # evidence for the missing selected-only roles.
    assert activation.alternates[0].retained_evidence_references == ()
    assert activation.alternates[0].tracking_feasibility.reason_code.startswith(
        "REPORT_ONLY_ALTERNATE:"
    )
    assert activation.selected[0].retained_evidence_references
    assert activation.selected[1].retained_evidence_references

    frozen_bad = SimpleNamespace(
        selected=tuple(selected_items),
        alternates=(unsupported_alternate, selected_items[0]),
        frozen_at=NOW,
    )
    with pytest.raises(MemoryObservationActivationError) as exc:
        _build_frozen_memory_activation_set(
            db,
            frozen_reserve=frozen_bad,
            readiness_id="case-k-bad",
            selection_seed="case-k-bad",
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
            manifest=manifest,
            measured_transport_identity_keys=(),
            frozen_at=NOW,
            expires_at=EXPIRES,
        )
    assert exc.value.code == "ADMISSION_AUTHORITY_UNSUPPORTED"


def _production_supply_with_incomplete_direct() -> GraduatedSupply:
    inventory = (
        (MARKET_MINT_A, MARKET_POOL_A, "MARKET_PRESENT_POOL"),
        (MARKET_MINT_B, MARKET_POOL_B, "MARKET_PRESENT_POOL"),
        (MARKET_MINT_C, MARKET_POOL_C, "MARKET_PRESENT_POOL"),
        (MARKET_MINT_D, MARKET_POOL_D, "MARKET_PRESENT_POOL"),
        (PUMP_MINT, PUMP_POOL, "DIRECT_PUMP_PUMPSWAP"),
    )
    proofs: dict[str, FixturePumpSwapProof] = {}
    origins: list[FixtureOriginProof] = []
    candidates: dict[str, dict[str, object]] = {}
    epoch = int(datetime.fromisoformat(e8.NOW.replace("Z", "+00:00")).timestamp())
    for i, (mint, pool, authority) in enumerate(inventory):
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
            candidates[mint.lower()] = {
                "mint": mint,
                "pool": pool,
                "pumpswap_pool": pool,
                "market_identity": f"solana-mainnet:pumpswap:{pool}",
                "provenance": "FRESH_AGGREGATOR_PROTOCOL_CONFIRMED",
                "admission_authority": "MARKET_PRESENT_POOL",
                "liquidity": {"liquidity_usd": 5000.0 + i},
                "liquidity_usd": 5000.0 + i,
                "evidence_expires_at": EXPIRES,
                "memory_observation_eligible": True,
                "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
                "holder_condition": "HOLDER_CONCENTRATION_EXTREME",
            }
        else:
            candidates[mint.lower()] = {
                "mint": mint,
                "pool": pool,
                "pumpswap_pool": pool,
                "market_identity": f"solana-mainnet:pumpswap:{pool}",
                "provenance": "LATEST_GRADUATED",
                "admission_authority": "DIRECT_PUMP_PUMPSWAP",
                "liquidity": {"liquidity_usd": 3454.0},
                "liquidity_usd": 3454.0,
                "retained_evidence": {},
                "evidence_expires_at": EXPIRES,
                "memory_observation_eligible": True,
                "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
                "holder_condition": "HOLDER_CONCENTRATION_EXTREME",
            }
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
            observed.append({"candidate_mints": mints})
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
        exclusions = list(
            (diag.get("retained_evidence_role_pre_freeze") or {}).get("exclusions")
            or []
        )
        assert any(
            row.get("mint") == PUMP_MINT
            and row.get("disposition")
            == RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE
            for row in exclusions
        )
        assert life.get("lifecycle_started") is False
    finally:
        base.tearDown()

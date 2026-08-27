"""V2-9.8B retained-evidence role completeness + current-run provenance.

Cases A-X plus production-caller coverage. Qualifying fixtures construct real
disposable request/response rows with current request_key_root, logical stage,
measured manifest membership, transport ownership, and response_hash.
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
    qualify_candidate_local_retained_role,
    qualify_current_run_retained_request_provenance,
    required_evidence_roles_for_admission_authority,
    required_evidence_roles_for_candidate,
    retained_evidence_role_source_kind_bindings,
    validate_memory_activation_set,
    build_prefreeze_manifest_transport_index,
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
EXECUTION = "role-complete-execution"
REQUEST_KEY_ROOT = f"v2-9-8b-window15m-{EXECUTION}"

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


def _transport_key(source: str, kind: str, mint: str, ordinal: int = 1):
    return (
        "ROLE_COMPLETE",
        source,
        source,
        kind,
        "fixture",
        ordinal,
        "MINT",
        mint,
        32,
        1,
        "COMPLETE",
        None,
    )


def _persist_role(
    connection: sqlite3.Connection,
    *,
    role: str,
    source: str,
    kind: str,
    mint: str,
    pool: str,
    request_key_root: str = REQUEST_KEY_ROOT,
    campaign_id: str = CAMPAIGN,
    run_id: str = RUN,
    cycle_id: str = CYCLE,
    stage_kind: str = "MINT_MARKET_BATCH",
    stage_sequence: int = 1,
    include_in_manifest: bool = True,
    transport_keys: list | None = None,
    response_hash: str | None = None,
    empty_transport_keys: bool = False,
    transport_count: int | None = None,
) -> tuple[int, int, str, dict[str, object] | None]:
    payload = {
        "chain": "solana",
        "mint": mint,
        "base_mint": mint,
        "pool": pool,
        "pair_address": pool,
        "observed_at": NOW,
    }
    payload_json = json.dumps(payload, sort_keys=True)
    digest = response_hash
    if digest is None:
        digest = hashlib.sha256(payload_json.encode()).hexdigest()
    request_key = f"{request_key_root}-{role.lower()}-{mint[:8]}-{stage_sequence}"
    request = connection.execute(
        """INSERT INTO printer_source_requests(
               source_name,request_kind,requested_at,request_key,
               source_status,data_quality_label
           ) VALUES (?,?,?,?,'COMPLETE','CLEAN_DATA')""",
        (source, kind, NOW, request_key),
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
    response_id = int(response.lastrowid)
    keys = transport_keys
    if keys is None and not empty_transport_keys:
        keys = [list(_transport_key(source, kind, mint, stage_sequence))]
    if empty_transport_keys:
        keys = []
    declared = transport_count if transport_count is not None else len(keys or [])
    manifest_entry = None
    if include_in_manifest:
        manifest_entry = {
            "source_request_id": request_id,
            "source_name": source,
            "request_kind": kind,
            "logical_stage_id": (
                f"{campaign_id}|{run_id}|{cycle_id}|{stage_kind}|{stage_sequence}"
            ),
            "terminal_status": "COMPLETED",
            "transport_identity_count": declared,
            "normalized_member_count": 1,
            "transport_identity_keys": keys,
        }
    return request_id, response_id, digest, manifest_entry


class ProvenanceBag:
    def __init__(self) -> None:
        self.manifest: list[dict[str, object]] = []
        self.transport_keys: list[list[object]] = []

    def add(self, entry: dict[str, object] | None) -> None:
        if entry is None:
            return
        self.manifest.append(entry)
        for key in entry.get("transport_identity_keys") or []:
            self.transport_keys.append(list(key))

    def filter_kwargs(self) -> dict[str, object]:
        return {
            "request_key_root": REQUEST_KEY_ROOT,
            "campaign_id": CAMPAIGN,
            "run_id": RUN,
            "cycle_id": CYCLE,
            "campaign_source_request_manifest": list(self.manifest),
            "measured_transport_identity_keys": list(self.transport_keys),
            "require_current_run_provenance": True,
        }


def _market_item(
    connection: sqlite3.Connection,
    bag: ProvenanceBag,
    *,
    mint: str,
    pool: str,
    source: str = "dexscreener",
    stage_sequence: int = 1,
) -> dict[str, object]:
    req, resp, _digest, entry = _persist_role(
        connection,
        role="MARKET_OBSERVATION",
        source=source,
        kind="candidate_market_batch",
        mint=mint,
        pool=pool,
        stage_kind="MINT_MARKET_BATCH",
        stage_sequence=stage_sequence,
    )
    bag.add(entry)
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
    bag: ProvenanceBag | None,
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
    if connection is not None and bag is not None:
        if include_origin:
            origin_req, origin_resp, _, entry = _persist_role(
                connection,
                role="ORIGIN_LINEAGE",
                source="solana_rpc",
                kind="restored_pump_migration_transaction",
                mint=mint,
                pool=pool,
                stage_kind="DIRECT_MIGRATION_INTAKE",
                stage_sequence=1,
            )
            bag.add(entry)
        if include_pumpswap:
            pumpswap_req, pumpswap_resp, _, entry = _persist_role(
                connection,
                role="PUMPSWAP_CONFIRMATION",
                source="solana_rpc",
                kind="pumpswap_pool_account_batch",
                mint=mint,
                pool=pool,
                stage_kind="PROTOCOL_CONFIRMATION",
                stage_sequence=1,
            )
            bag.add(entry)
        if include_market:
            market_req, market_resp, _, entry = _persist_role(
                connection,
                role="MARKET_OBSERVATION",
                source="dexscreener",
                kind="candidate_market_batch",
                mint=mint,
                pool=pool,
                stage_kind="MINT_MARKET_BATCH",
                stage_sequence=2,
            )
            bag.add(entry)
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


def _filter(db, rows, bag: ProvenanceBag):
    return _filter_observation_rows_by_retained_role_completeness(
        db, rows, now=NOW, **bag.filter_kwargs()
    )


def test_case_a_market_present_complete_passes_gate(db) -> None:
    bag = ProvenanceBag()
    item = _market_item(db, bag, mint=MARKET_MINT_A, pool=MARKET_POOL_A)
    complete, exclusions = _filter(db, [item], bag)
    assert len(complete) == 1
    assert exclusions == []


def test_case_b_direct_pump_complete_passes_gate(db) -> None:
    bag = ProvenanceBag()
    item = _direct_item(db, bag, mint=PUMP_MINT, pool=PUMP_POOL)
    complete, exclusions = _filter(db, [item], bag)
    assert len(complete) == 1
    assert exclusions == []


def test_case_c_direct_pump_incomplete_excluded_before_freeze(db) -> None:
    bag = ProvenanceBag()
    incomplete = _direct_item(
        db,
        bag,
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        include_origin=False,
        include_pumpswap=False,
        include_market=True,
    )
    markets = [
        _market_item(db, bag, mint=mint, pool=pool, stage_sequence=10 + idx)
        for idx, (mint, pool) in enumerate(
            (
                (MARKET_MINT_A, MARKET_POOL_A),
                (MARKET_MINT_B, MARKET_POOL_B),
                (MARKET_MINT_C, MARKET_POOL_C),
                (MARKET_MINT_D, MARKET_POOL_D),
            )
        )
    ]
    complete, exclusions = _filter(db, [incomplete, *markets], bag)
    assert PUMP_MINT not in {str(item.get("mint")) for item in complete}
    frozen = freeze_eligible_reserve(
        complete, cycle_seed="role-complete-case-c", at=NOW
    )
    assert all(str(item.get("mint")) != PUMP_MINT for item in frozen.selected)


def test_case_d_insufficient_role_complete_depth_blocks_before_freeze(db) -> None:
    bag = ProvenanceBag()
    rows = [
        _market_item(db, bag, mint=MARKET_MINT_A, pool=MARKET_POOL_A, stage_sequence=1),
        _market_item(db, bag, mint=MARKET_MINT_B, pool=MARKET_POOL_B, stage_sequence=2),
        _direct_item(
            db,
            bag,
            mint=PUMP_MINT,
            pool=PUMP_POOL,
            include_origin=False,
            include_pumpswap=False,
        ),
        _direct_item(
            db,
            bag,
            mint=PUMP_MINT_B,
            pool=PUMP_POOL_B,
            include_origin=False,
            include_pumpswap=False,
        ),
    ]
    complete, exclusions = _filter(db, rows, bag)
    assert len(complete) == 2
    assert len(exclusions) == 2
    frozen = freeze_eligible_reserve(
        complete, cycle_seed="role-complete-case-d", at=NOW
    )
    assert frozen.selected == ()
    assert bool(frozen.selection_authority.get("coverage_blocker")) is True


def test_case_e_report_only_alternate_does_not_terminalize_selected(db) -> None:
    bag = ProvenanceBag()
    selected_items = [
        _market_item(db, bag, mint=MARKET_MINT_A, pool=MARKET_POOL_A, stage_sequence=1),
        _market_item(
            db,
            bag,
            mint=MARKET_MINT_B,
            pool=MARKET_POOL_B,
            source="geckoterminal",
            stage_sequence=2,
        ),
    ]
    manifest = []
    for item in selected_items:
        source = "dexscreener" if item["mint"] == MARKET_MINT_A else "geckoterminal"
        req = int(item["liquidity"]["source_request_id"])
        entry = next(e for e in bag.manifest if int(e["source_request_id"]) == req)
        manifest.append(entry)
    alternate_incomplete = {
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
    frozen = SimpleNamespace(
        selected=tuple(selected_items),
        alternates=(alternate_incomplete, selected_items[0]),
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
        measured_transport_identity_keys=bag.transport_keys,
        frozen_at=NOW,
        expires_at=EXPIRES,
    )
    assert len(activation.selected) == 2
    assert activation.alternates[0].admission_authority is (
        AdmissionAuthority.DIRECT_PUMP_PUMPSWAP
    )


def test_case_f_final_validator_still_fails_role_missing(db) -> None:
    bag = ProvenanceBag()
    req, resp, digest, entry = _persist_role(
        db,
        role="MARKET_OBSERVATION",
        source="dexscreener",
        kind="candidate_market_batch",
        mint=PUMP_MINT,
        pool=PUMP_POOL,
    )
    bag.add(entry)
    key = tuple(entry["transport_identity_keys"][0])
    market_ref = RetainedEvidenceReference(
        evidence_role=EvidenceRole.MARKET_OBSERVATION,
        source_name="dexscreener",
        request_kind="candidate_market_batch",
        source_request_id=req,
        source_response_id=resp,
        source_failure_id=None,
        transport_identity_keys=(key,),
        observed_at=NOW,
        raw_payload_hash=digest,
        target_mint=PUMP_MINT,
        target_pool=PUMP_POOL,
        campaign_id=CAMPAIGN,
        campaign_run_id=RUN,
        cycle_id=CYCLE,
    )
    entry_obj = ManifestRequestEntry(
        source_request_id=req,
        source_name="dexscreener",
        request_kind="candidate_market_batch",
        logical_stage_id=str(entry["logical_stage_id"]),
        transport_identity_count=1,
        transport_identity_keys=(key,),
        terminal_status="COMPLETED",
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
        retained_evidence_references=(market_ref,),
        admission_authority=AdmissionAuthority.DIRECT_PUMP_PUMPSWAP,
        claims_pump_origin=True,
        claims_pumpswap_graduation=True,
    )
    market_b = _market_item(
        db, bag, mint=MARKET_MINT_B, pool=MARKET_POOL_B, source="geckoterminal"
    )
    req_b = int(market_b["liquidity"]["source_request_id"])
    entry_b = next(e for e in bag.manifest if int(e["source_request_id"]) == req_b)
    key_b = tuple(entry_b["transport_identity_keys"][0])
    resp_b = int(market_b["liquidity"]["source_response_id"])
    digest_b = db.execute(
        "SELECT response_hash FROM printer_source_responses WHERE id=?",
        (resp_b,),
    ).fetchone()[0]
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
        retained_evidence_references=(
            RetainedEvidenceReference(
                evidence_role=EvidenceRole.MARKET_OBSERVATION,
                source_name="geckoterminal",
                request_kind="candidate_market_batch",
                source_request_id=req_b,
                source_response_id=resp_b,
                source_failure_id=None,
                transport_identity_keys=(key_b,),
                observed_at=NOW,
                raw_payload_hash=str(digest_b),
                target_mint=MARKET_MINT_B,
                target_pool=MARKET_POOL_B,
                campaign_id=CAMPAIGN,
                campaign_run_id=RUN,
                cycle_id=CYCLE,
            ),
        ),
        admission_authority=AdmissionAuthority.MARKET_PRESENT_POOL,
        claims_pump_origin=False,
        claims_pumpswap_graduation=False,
    )
    entry_b_obj = ManifestRequestEntry(
        source_request_id=req_b,
        source_name="geckoterminal",
        request_kind="candidate_market_batch",
        logical_stage_id=str(entry_b["logical_stage_id"]),
        transport_identity_count=1,
        transport_identity_keys=(key_b,),
        terminal_status="COMPLETED",
    )
    activation = FrozenMemoryActivationSet(
        activation_purpose=ActivationPurpose.MEMORY_OBSERVATION,
        readiness_id="final-defense",
        selection_seed="role-complete-case-f",
        selected=(incomplete, complete_market),
        alternates=(
            replace(complete_market, slot_ordinal=3, mint=MARKET_MINT_C, pool=MARKET_POOL_C),
            replace(complete_market, slot_ordinal=4, mint=MARKET_MINT_D, pool=MARKET_POOL_D),
        ),
        manifest_request_ids=(req, req_b),
        manifest_transport_identity_keys=(key, key_b),
        frozen_at=NOW,
        expires_at=EXPIRES,
        manifest_entries=(entry_obj, entry_b_obj),
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
    bag = ProvenanceBag()
    item = _direct_item(
        None,
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
    complete, exclusions = _filter(db, [item], bag)
    assert complete == []
    assert exclusions[0]["qualification_failures"]["ORIGIN_LINEAGE"] == (
        "RETAINED_REQUEST_NOT_FOUND"
    )


def test_case_h_mismatched_request_response_fails_pre_freeze(db) -> None:
    bag = ProvenanceBag()
    origin_req, _origin_resp, _, entry = _persist_role(
        db,
        role="ORIGIN_LINEAGE",
        source="solana_rpc",
        kind="restored_pump_migration_transaction",
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        stage_kind="DIRECT_MIGRATION_INTAKE",
    )
    bag.add(entry)
    _other_req, other_resp, _, other_entry = _persist_role(
        db,
        role="ORIGIN_LINEAGE",
        source="solana_rpc",
        kind="restored_pump_migration_transaction",
        mint=PUMP_MINT_B,
        pool=PUMP_POOL_B,
        stage_kind="DIRECT_MIGRATION_INTAKE",
        stage_sequence=2,
    )
    bag.add(other_entry)
    pumpswap_req, pumpswap_resp, _, entry = _persist_role(
        db,
        role="PUMPSWAP_CONFIRMATION",
        source="solana_rpc",
        kind="pumpswap_pool_account_batch",
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        stage_kind="PROTOCOL_CONFIRMATION",
    )
    bag.add(entry)
    market_req, market_resp, _, entry = _persist_role(
        db,
        role="MARKET_OBSERVATION",
        source="dexscreener",
        kind="candidate_market_batch",
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        stage_kind="MINT_MARKET_BATCH",
        stage_sequence=3,
    )
    bag.add(entry)
    item = _direct_item(
        None,
        None,
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        origin_req=origin_req,
        origin_resp=other_resp,
        pumpswap_req=pumpswap_req,
        pumpswap_resp=pumpswap_resp,
        market_req=market_req,
        market_resp=market_resp,
    )
    complete, exclusions = _filter(db, [item], bag)
    assert complete == []
    assert exclusions[0]["qualification_failures"]["ORIGIN_LINEAGE"] == (
        "RETAINED_RESPONSE_CONTRACT_MISMATCH"
    )


def test_case_i_wrong_candidate_evidence_fails_pre_freeze(db) -> None:
    bag = ProvenanceBag()
    wrong_req, wrong_resp, _, entry = _persist_role(
        db,
        role="MARKET_OBSERVATION",
        source="dexscreener",
        kind="candidate_market_batch",
        mint=MARKET_MINT_B,
        pool=MARKET_POOL_B,
    )
    bag.add(entry)
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
    complete, exclusions = _filter(db, [item], bag)
    assert complete == []
    assert exclusions[0]["qualification_failures"]["MARKET_OBSERVATION"] in {
        "MARKET_RESPONSE_NO_EXACT_MEMBER_MATCH",
        "RETAINED_RESPONSE_TARGET_MISMATCH",
    }


def test_case_j_role_authority_consistency_fail_closed(db) -> None:
    bag = ProvenanceBag()
    item = _market_item(db, bag, mint=MARKET_MINT_A, pool=MARKET_POOL_A)
    item["claims_pump_origin"] = True
    item["claims_pumpswap_graduation"] = True
    complete, exclusions = _filter(db, [item], bag)
    assert complete == []
    assert exclusions[0]["detail"] == "ADMISSION_AUTHORITY_CLAIMS_INCONSISTENT"


def test_case_k_alternate_diagnostic_safety_no_authority_rewrite(db) -> None:
    bag = ProvenanceBag()
    selected_items = [
        _market_item(db, bag, mint=MARKET_MINT_A, pool=MARKET_POOL_A, stage_sequence=1),
        _market_item(
            db,
            bag,
            mint=MARKET_MINT_B,
            pool=MARKET_POOL_B,
            source="geckoterminal",
            stage_sequence=2,
        ),
    ]
    manifest = [
        next(
            e
            for e in bag.manifest
            if int(e["source_request_id"])
            == int(item["liquidity"]["source_request_id"])
        )
        for item in selected_items
    ]
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
    activation = _build_frozen_memory_activation_set(
        db,
        frozen_reserve=SimpleNamespace(
            selected=tuple(selected_items),
            alternates=(missing_refs_alternate, selected_items[0]),
            frozen_at=NOW,
        ),
        readiness_id="case-k",
        selection_seed="case-k",
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
        manifest=manifest,
        measured_transport_identity_keys=bag.transport_keys,
        frozen_at=NOW,
        expires_at=EXPIRES,
    )
    assert activation.alternates[0].admission_authority is (
        AdmissionAuthority.DIRECT_PUMP_PUMPSWAP
    )
    assert activation.alternates[0].retained_evidence_references == ()
    with pytest.raises(MemoryObservationActivationError) as exc:
        _build_frozen_memory_activation_set(
            db,
            frozen_reserve=SimpleNamespace(
                selected=tuple(selected_items),
                alternates=(unsupported_alternate, selected_items[0]),
                frozen_at=NOW,
            ),
            readiness_id="case-k-bad",
            selection_seed="case-k-bad",
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
            manifest=manifest,
            measured_transport_identity_keys=bag.transport_keys,
            frozen_at=NOW,
            expires_at=EXPIRES,
        )
    assert exc.value.code == "ADMISSION_AUTHORITY_UNSUPPORTED"


def test_case_l_missing_authority_excluded_before_freeze(db) -> None:
    bag = ProvenanceBag()
    item = _direct_item(db, bag, mint=PUMP_MINT, pool=PUMP_POOL)
    item.pop("admission_authority", None)
    complete, exclusions = _filter(db, [item], bag)
    assert complete == []
    assert exclusions[0]["detail"] == "ADMISSION_AUTHORITY_MISSING"


def test_case_m_wrong_request_kind_does_not_qualify_origin(db) -> None:
    bag = ProvenanceBag()
    pumpswap_req, pumpswap_resp, _, entry = _persist_role(
        db,
        role="PUMPSWAP_CONFIRMATION",
        source="solana_rpc",
        kind="pumpswap_pool_account_batch",
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        stage_kind="PROTOCOL_CONFIRMATION",
    )
    bag.add(entry)
    market_req, market_resp, _, entry = _persist_role(
        db,
        role="MARKET_OBSERVATION",
        source="dexscreener",
        kind="candidate_market_batch",
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        stage_kind="MINT_MARKET_BATCH",
        stage_sequence=2,
    )
    bag.add(entry)
    item = _direct_item(
        None,
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
    complete, exclusions = _filter(db, [item], bag)
    assert complete == []
    assert exclusions[0]["qualification_failures"]["ORIGIN_LINEAGE"] == (
        "RETAINED_ROLE_SOURCE_KIND_MISMATCH"
    )


def test_case_n_cross_role_reuse_only_true_role_qualifies(db) -> None:
    bag = ProvenanceBag()
    pumpswap_req, pumpswap_resp, _, entry = _persist_role(
        db,
        role="PUMPSWAP_CONFIRMATION",
        source="solana_rpc",
        kind="pumpswap_pool_account_batch",
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        stage_kind="PROTOCOL_CONFIRMATION",
    )
    bag.add(entry)
    market_req, market_resp, _, entry = _persist_role(
        db,
        role="MARKET_OBSERVATION",
        source="dexscreener",
        kind="candidate_market_batch",
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        stage_kind="MINT_MARKET_BATCH",
        stage_sequence=2,
    )
    bag.add(entry)
    item = _direct_item(
        None,
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
    complete, exclusions = _filter(db, [item], bag)
    assert complete == []
    failures = exclusions[0]["qualification_failures"]
    assert failures["ORIGIN_LINEAGE"] == "RETAINED_ROLE_SOURCE_KIND_MISMATCH"
    assert "PUMPSWAP_CONFIRMATION" in exclusions[0]["present_roles"]


def test_case_o_valid_production_shaped_role_kinds_qualify(db) -> None:
    bindings = retained_evidence_role_source_kind_bindings()
    assert (
        "solana_rpc",
        "restored_pump_migration_transaction",
    ) in bindings[EvidenceRole.ORIGIN_LINEAGE]
    assert (
        "pumpswap",
        "pumpswap_signature_pool_resolution",
    ) in bindings[EvidenceRole.PUMPSWAP_CONFIRMATION]
    bag = ProvenanceBag()
    item = _direct_item(db, bag, mint=PUMP_MINT, pool=PUMP_POOL)
    complete, exclusions = _filter(db, [item], bag)
    assert exclusions == []
    assert len(complete) == 1


def test_case_p_prior_campaign_same_token_rejected(db) -> None:
    bag = ProvenanceBag()
    # Prior-campaign evidence for same mint/pool.
    prior_req, prior_resp, _, _prior_entry = _persist_role(
        db,
        role="MARKET_OBSERVATION",
        source="dexscreener",
        kind="candidate_market_batch",
        mint=MARKET_MINT_A,
        pool=MARKET_POOL_A,
        request_key_root="v2-9-8b-window15m-PRIOR-EXECUTION",
        campaign_id="prior-campaign",
        run_id="prior-run",
        cycle_id="prior-cycle",
        include_in_manifest=False,
    )
    item = {
        "mint": MARKET_MINT_A,
        "pool": MARKET_POOL_A,
        "admission_authority": "MARKET_PRESENT_POOL",
        "memory_observation_eligible": True,
        "tracking_handoff_eligible": True,
        "evidence_expires_at": EXPIRES,
        "liquidity": {
            "source_request_id": prior_req,
            "source_response_id": prior_resp,
        },
    }
    complete, exclusions = _filter(db, [item], bag)
    assert complete == []
    assert exclusions[0]["qualification_failures"]["MARKET_OBSERVATION"] == (
        "RETAINED_REQUEST_ROOT_MISMATCH"
    )


def test_case_q_not_in_current_measured_manifest(db) -> None:
    bag = ProvenanceBag()
    req, resp, _, _entry = _persist_role(
        db,
        role="MARKET_OBSERVATION",
        source="dexscreener",
        kind="candidate_market_batch",
        mint=MARKET_MINT_A,
        pool=MARKET_POOL_A,
        include_in_manifest=False,
    )
    item = {
        "mint": MARKET_MINT_A,
        "pool": MARKET_POOL_A,
        "admission_authority": "MARKET_PRESENT_POOL",
        "memory_observation_eligible": True,
        "tracking_handoff_eligible": True,
        "evidence_expires_at": EXPIRES,
        "liquidity": {
            "source_request_id": req,
            "source_response_id": resp,
        },
    }
    complete, exclusions = _filter(db, [item], bag)
    assert complete == []
    assert exclusions[0]["qualification_failures"]["MARKET_OBSERVATION"] == (
        "RETAINED_REQUEST_NOT_IN_MANIFEST"
    )


def test_case_r_transport_identity_mismatch(db) -> None:
    bag = ProvenanceBag()
    foreign = _market_item(
        db, bag, mint=MARKET_MINT_B, pool=MARKET_POOL_B, stage_sequence=9
    )
    foreign_key = list(
        next(
            e
            for e in bag.manifest
            if int(e["source_request_id"])
            == int(foreign["liquidity"]["source_request_id"])
        )["transport_identity_keys"][0]
    )
    req, resp, _, entry = _persist_role(
        db,
        role="MARKET_OBSERVATION",
        source="dexscreener",
        kind="candidate_market_batch",
        mint=MARKET_MINT_A,
        pool=MARKET_POOL_A,
        transport_keys=[foreign_key],  # key owned by another request too
        stage_sequence=1,
    )
    bag.add(entry)
    item = {
        "mint": MARKET_MINT_A,
        "pool": MARKET_POOL_A,
        "admission_authority": "MARKET_PRESENT_POOL",
        "memory_observation_eligible": True,
        "tracking_handoff_eligible": True,
        "evidence_expires_at": EXPIRES,
        "liquidity": {
            "source_request_id": req,
            "source_response_id": resp,
        },
    }
    complete, exclusions = _filter(db, [item], bag)
    assert complete == []
    assert exclusions[0]["qualification_failures"]["MARKET_OBSERVATION"] == (
        "RETAINED_TRANSPORT_IDENTITY_FOREIGN_REQUEST"
    )


def test_case_s_current_provenance_valid(db) -> None:
    bag = ProvenanceBag()
    item = _market_item(db, bag, mint=MARKET_MINT_A, pool=MARKET_POOL_A)
    complete, exclusions = _filter(db, [item], bag)
    assert exclusions == []
    assert len(complete) == 1


def test_case_t_final_defense_still_fail_closed(db) -> None:
    bag = ProvenanceBag()
    item = _market_item(db, bag, mint=MARKET_MINT_A, pool=MARKET_POOL_A)
    req = int(item["liquidity"]["source_request_id"])
    resp = int(item["liquidity"]["source_response_id"])
    digest = db.execute(
        "SELECT response_hash FROM printer_source_responses WHERE id=?",
        (resp,),
    ).fetchone()[0]
    key = tuple(
        next(e for e in bag.manifest if int(e["source_request_id"]) == req)[
            "transport_identity_keys"
        ][0]
    )
    # Force past early gate by constructing activation with wrong ownership scope.
    reference = RetainedEvidenceReference(
        evidence_role=EvidenceRole.MARKET_OBSERVATION,
        source_name="dexscreener",
        request_kind="candidate_market_batch",
        source_request_id=req,
        source_response_id=resp,
        source_failure_id=None,
        transport_identity_keys=(key,),
        observed_at=NOW,
        raw_payload_hash=str(digest),
        target_mint=MARKET_MINT_A,
        target_pool=MARKET_POOL_A,
        campaign_id="other-campaign",
        campaign_run_id="other-run",
        cycle_id="other-cycle",
    )
    entry = ManifestRequestEntry(
        source_request_id=req,
        source_name="dexscreener",
        request_kind="candidate_market_batch",
        logical_stage_id=f"{CAMPAIGN}|{RUN}|{CYCLE}|MINT_MARKET_BATCH|1",
        transport_identity_count=1,
        transport_identity_keys=(key,),
        terminal_status="COMPLETED",
    )
    second = _market_item(
        db, bag, mint=MARKET_MINT_B, pool=MARKET_POOL_B, source="geckoterminal"
    )
    req2 = int(second["liquidity"]["source_request_id"])
    resp2 = int(second["liquidity"]["source_response_id"])
    digest2 = db.execute(
        "SELECT response_hash FROM printer_source_responses WHERE id=?",
        (resp2,),
    ).fetchone()[0]
    key2 = tuple(
        next(e for e in bag.manifest if int(e["source_request_id"]) == req2)[
            "transport_identity_keys"
        ][0]
    )
    candidate_a = FrozenMemoryActivationCandidate(
        slot_ordinal=1,
        mint=MARKET_MINT_A,
        pool=MARKET_POOL_A,
        market_identity=f"solana-mainnet:pumpswap:{MARKET_POOL_A}",
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
        retained_evidence_references=(reference,),
        admission_authority=AdmissionAuthority.MARKET_PRESENT_POOL,
        claims_pump_origin=False,
        claims_pumpswap_graduation=False,
    )
    candidate_b = FrozenMemoryActivationCandidate(
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
        retained_evidence_references=(
            RetainedEvidenceReference(
                evidence_role=EvidenceRole.MARKET_OBSERVATION,
                source_name="geckoterminal",
                request_kind="candidate_market_batch",
                source_request_id=req2,
                source_response_id=resp2,
                source_failure_id=None,
                transport_identity_keys=(key2,),
                observed_at=NOW,
                raw_payload_hash=str(digest2),
                target_mint=MARKET_MINT_B,
                target_pool=MARKET_POOL_B,
                campaign_id=CAMPAIGN,
                campaign_run_id=RUN,
                cycle_id=CYCLE,
            ),
        ),
        admission_authority=AdmissionAuthority.MARKET_PRESENT_POOL,
        claims_pump_origin=False,
        claims_pumpswap_graduation=False,
    )
    entry2 = ManifestRequestEntry(
        source_request_id=req2,
        source_name="geckoterminal",
        request_kind="candidate_market_batch",
        logical_stage_id=f"{CAMPAIGN}|{RUN}|{CYCLE}|MINT_MARKET_BATCH|2",
        transport_identity_count=1,
        transport_identity_keys=(key2,),
        terminal_status="COMPLETED",
    )
    activation = FrozenMemoryActivationSet(
        activation_purpose=ActivationPurpose.MEMORY_OBSERVATION,
        readiness_id="case-t",
        selection_seed="case-t",
        selected=(candidate_a, candidate_b),
        alternates=(
            replace(candidate_b, slot_ordinal=3),
            replace(candidate_b, slot_ordinal=4),
        ),
        manifest_request_ids=(req, req2),
        manifest_transport_identity_keys=(key, key2),
        frozen_at=NOW,
        expires_at=EXPIRES,
        manifest_entries=(entry, entry2),
    )
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            activation,
            now=NOW,
            expected_ownership=(CAMPAIGN, RUN, CYCLE),
        )
    assert exc.value.code in {
        "RETAINED_OWNERSHIP_MISMATCH",
        "RETAINED_LOGICAL_STAGE_OWNERSHIP_MISMATCH",
    }


def test_case_u_wrong_run_cycle_stage_rejected(db) -> None:
    bag = ProvenanceBag()
    req, resp, _, entry = _persist_role(
        db,
        role="MARKET_OBSERVATION",
        source="dexscreener",
        kind="candidate_market_batch",
        mint=MARKET_MINT_A,
        pool=MARKET_POOL_A,
        run_id="other-run",
        cycle_id="other-cycle",
    )
    bag.add(entry)
    item = {
        "mint": MARKET_MINT_A,
        "pool": MARKET_POOL_A,
        "admission_authority": "MARKET_PRESENT_POOL",
        "memory_observation_eligible": True,
        "tracking_handoff_eligible": True,
        "evidence_expires_at": EXPIRES,
        "liquidity": {
            "source_request_id": req,
            "source_response_id": resp,
        },
    }
    complete, exclusions = _filter(db, [item], bag)
    assert complete == []
    assert exclusions[0]["qualification_failures"]["MARKET_OBSERVATION"] == (
        "RETAINED_LOGICAL_STAGE_OWNERSHIP_MISMATCH"
    )


def test_case_v_empty_response_hash_rejected(db) -> None:
    bag = ProvenanceBag()
    req, resp, _, entry = _persist_role(
        db,
        role="MARKET_OBSERVATION",
        source="dexscreener",
        kind="candidate_market_batch",
        mint=MARKET_MINT_A,
        pool=MARKET_POOL_A,
        response_hash="",
    )
    bag.add(entry)
    item = {
        "mint": MARKET_MINT_A,
        "pool": MARKET_POOL_A,
        "admission_authority": "MARKET_PRESENT_POOL",
        "memory_observation_eligible": True,
        "tracking_handoff_eligible": True,
        "evidence_expires_at": EXPIRES,
        "liquidity": {
            "source_request_id": req,
            "source_response_id": resp,
        },
    }
    complete, exclusions = _filter(db, [item], bag)
    assert complete == []
    assert exclusions[0]["qualification_failures"]["MARKET_OBSERVATION"] == (
        "RETAINED_RESPONSE_HASH_MISSING"
    )


def test_case_w_transport_count_without_keys_rejected(db) -> None:
    bag = ProvenanceBag()
    req, resp, _, entry = _persist_role(
        db,
        role="MARKET_OBSERVATION",
        source="dexscreener",
        kind="candidate_market_batch",
        mint=MARKET_MINT_A,
        pool=MARKET_POOL_A,
        empty_transport_keys=True,
        transport_count=1,
    )
    bag.add(entry)
    item = {
        "mint": MARKET_MINT_A,
        "pool": MARKET_POOL_A,
        "admission_authority": "MARKET_PRESENT_POOL",
        "memory_observation_eligible": True,
        "tracking_handoff_eligible": True,
        "evidence_expires_at": EXPIRES,
        "liquidity": {
            "source_request_id": req,
            "source_response_id": resp,
        },
    }
    complete, exclusions = _filter(db, [item], bag)
    assert complete == []
    assert exclusions[0]["qualification_failures"]["MARKET_OBSERVATION"] == (
        "RETAINED_REQUEST_TRANSPORT_IDENTITY_MISSING"
    )


def test_case_x_same_mint_pair_source_kind_prior_root_rejected(db) -> None:
    bag = ProvenanceBag()
    prior_req, prior_resp, _, _ = _persist_role(
        db,
        role="MARKET_OBSERVATION",
        source="dexscreener",
        kind="candidate_market_batch",
        mint=MARKET_MINT_A,
        pool=MARKET_POOL_A,
        request_key_root="v2-9-8b-window15m-OLDER",
        include_in_manifest=False,
    )
    # Also put a current valid market into bag so provenance context exists.
    _market_item(db, bag, mint=MARKET_MINT_B, pool=MARKET_POOL_B, stage_sequence=3)
    item = {
        "mint": MARKET_MINT_A,
        "pool": MARKET_POOL_A,
        "admission_authority": "MARKET_PRESENT_POOL",
        "memory_observation_eligible": True,
        "tracking_handoff_eligible": True,
        "evidence_expires_at": EXPIRES,
        "liquidity": {
            "source_request_id": prior_req,
            "source_response_id": prior_resp,
        },
    }
    complete, exclusions = _filter(db, [item], bag)
    assert complete == []
    assert exclusions[0]["qualification_failures"]["MARKET_OBSERVATION"] == (
        "RETAINED_REQUEST_ROOT_MISMATCH"
    )


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
        candidates[mint.lower()] = {
            "mint": mint,
            "pool": pool,
            "pumpswap_pool": pool,
            "market_identity": f"solana-mainnet:pumpswap:{pool}",
            "provenance": (
                "FRESH_AGGREGATOR_PROTOCOL_CONFIRMED"
                if authority == "MARKET_PRESENT_POOL"
                else "LATEST_GRADUATED"
            ),
            "admission_authority": authority,
            "liquidity": {"liquidity_usd": 5000.0 + i},
            "liquidity_usd": 5000.0 + i,
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
        _seed_exact_markets_for_supply(
            base.db,
            supply,
            request_key_root="v2-9-8b-window15m-role-complete-production",
            campaign_id=str(base.command.campaign_id),
            run_id=str(base.command.run_id),
            cycle_id="cyc",
        )
        owner = AuthoritativeLiveOperationalCampaignOwner()
        _force_holder_extreme_ineligible(owner, supply.holder_reserve_supply)
        observed: list[dict[str, object]] = []
        real_freeze = freeze_eligible_reserve_for_campaign

        def _spy(connection, candidates, **kwargs):
            mints = tuple(str(item.get("mint") or "") for item in candidates)
            observed.append({"candidate_mints": mints})
            assert PUMP_MINT not in mints
            # Current MARKET_PRESENT nominees with fixture provenance must remain
            # eligible for freeze input when current-run ownership is seeded.
            assert any(mints)
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
        ) or any(
            row.get("detail") == "RETAINED_CURRENT_RUN_PROVENANCE_UNAVAILABLE"
            for row in exclusions
        )
        assert life.get("lifecycle_started") is False
    finally:
        base.tearDown()

"""V2-9.8B freeze-ready candidate supply reliability — focused RED/GREEN proofs.

Offline only. No live network, no authoritative DB, no authorization, no sleep.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from unittest.mock import MagicMock

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.memory_observation_activation import (
    RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE,
    AdmissionAuthority,
)
from printer_v1.discovery.permanent_discovery_availability import (
    MINIMUM_FREEZE_DEPTH,
    freeze_eligible_reserve,
    observation_reserve_depth_status,
)
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    CAPACITY_ALREADY_MET,
    WAITING_FOR_ELIGIBLE_SUPPLY,
    evaluate_wait_eligibility,
)


NOW = "2026-09-01T11:36:19+00:00"
EXPIRES = "2099-01-01T00:00:00+00:00"
STALE = "2000-01-01T00:00:00+00:00"
CAMPAIGN = "freeze-ready-campaign"
RUN = "freeze-ready-run"
CYCLE = "freeze-ready-cycle"
EXECUTION = "freeze-ready-execution"
REQUEST_KEY_ROOT = f"v2-9-8b-window15m-{EXECUTION}"

MARKET_MINTS = [
    ("MarketMintAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "MarketPoolAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"),
    ("MarketMintBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "MarketPoolBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"),
    ("MarketMintCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "MarketPoolCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"),
    ("MarketMintDxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "MarketPoolDxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"),
]
PUMP_MINT = "CrR3AB6W9v2RV9btV9Egqsdij3jXNUSJba9dqKAqpump"
PUMP_POOL = "A2MoynsjruNQqDjdRQKMq8xDbFtAecE198KjuVrMBeWu"
PUMP_MINT_B = "Av2cD8GQT5dnCiC2cav2X37hs9z2mbBSxAMGkRbwkdt2"
PUMP_POOL_B = "REUdyzJNhNYJbgxAWfjiicvcTsfSJhyd61oN1JhhJXo"


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "freeze-ready.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


@dataclass
class ProvenanceBag:
    manifest: list[dict[str, object]]
    transport_keys: list[list[object]]

    def __init__(self) -> None:
        self.manifest = []
        self.transport_keys = []

    def add(self, entry: dict[str, object] | None) -> None:
        if entry is None:
            return
        self.manifest.append(entry)
        for key in entry.get("transport_identity_keys") or []:
            self.transport_keys.append(list(key))

    def kwargs(self) -> dict[str, object]:
        return {
            "request_key_root": REQUEST_KEY_ROOT,
            "campaign_id": CAMPAIGN,
            "run_id": RUN,
            "cycle_id": CYCLE,
            "campaign_source_request_manifest": list(self.manifest),
            "measured_transport_identity_keys": list(self.transport_keys),
            "require_current_run_provenance": True,
        }


def _transport_key(source: str, kind: str, mint: str, ordinal: int = 1):
    return (
        "FREEZE_READY",
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
    bag: ProvenanceBag,
    *,
    role: str,
    source: str,
    kind: str,
    mint: str,
    pool: str,
    stage_kind: str,
    stage_sequence: int,
) -> tuple[int, int]:
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
    request_key = f"{REQUEST_KEY_ROOT}-{role.lower()}-{mint[:8]}-{stage_sequence}"
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
    keys = [list(_transport_key(source, kind, mint, stage_sequence))]
    bag.add(
        {
            "source_request_id": request_id,
            "source_name": source,
            "request_kind": kind,
            "logical_stage_id": f"{CAMPAIGN}|{RUN}|{CYCLE}|{stage_kind}|{stage_sequence}",
            "terminal_status": "COMPLETED",
            "transport_identity_count": 1,
            "normalized_member_count": 1,
            "transport_identity_keys": keys,
        }
    )
    return request_id, response_id


def _market_item(
    connection: sqlite3.Connection,
    bag: ProvenanceBag,
    *,
    mint: str,
    pool: str,
    stage_sequence: int,
) -> dict[str, object]:
    req, resp = _persist_role(
        connection,
        bag,
        role="MARKET_OBSERVATION",
        source="dexscreener",
        kind="candidate_market_batch",
        mint=mint,
        pool=pool,
        stage_kind="MINT_MARKET_BATCH",
        stage_sequence=stage_sequence,
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
        "evidence_expires_at": EXPIRES,
        "liquidity_observed_at": NOW,
        "liquidity": {
            "liquidity_usd": 5000.0,
            "status": "LIQUIDITY_PROVEN",
            "source_request_id": req,
            "source_response_id": resp,
            "source_status": "COMPLETE",
            "reason": "AT_OR_ABOVE_3000_FLOOR",
            "outcome_category": "LIQUIDITY_EXACT_ABOVE_FLOOR",
        },
        "holder_condition": "UNKNOWN",
        "fully_eligible": False,
        "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
    }


def _direct_item(
    connection: sqlite3.Connection,
    bag: ProvenanceBag,
    *,
    mint: str,
    pool: str,
    include_origin: bool,
    include_pumpswap: bool,
    include_market: bool = True,
    stage_base: int = 1,
    tracking_eligible: bool = True,
    requalification_required: bool = False,
    evidence_expires_at: str = EXPIRES,
) -> dict[str, object]:
    retained: dict[str, dict[str, int]] = {}
    market_req = market_resp = None
    if include_origin:
        o_req, o_resp = _persist_role(
            connection,
            bag,
            role="ORIGIN_LINEAGE",
            source="solana_rpc",
            kind="restored_pump_migration_transaction",
            mint=mint,
            pool=pool,
            stage_kind="DIRECT_MIGRATION_INTAKE",
            stage_sequence=stage_base,
        )
        retained["ORIGIN_LINEAGE"] = {
            "source_request_id": o_req,
            "source_response_id": o_resp,
        }
    if include_pumpswap:
        p_req, p_resp = _persist_role(
            connection,
            bag,
            role="PUMPSWAP_CONFIRMATION",
            source="solana_rpc",
            kind="pumpswap_pool_account_batch",
            mint=mint,
            pool=pool,
            stage_kind="PROTOCOL_CONFIRMATION",
            stage_sequence=stage_base + 1,
        )
        retained["PUMPSWAP_CONFIRMATION"] = {
            "source_request_id": p_req,
            "source_response_id": p_resp,
        }
    if include_market:
        market_req, market_resp = _persist_role(
            connection,
            bag,
            role="MARKET_OBSERVATION",
            source="dexscreener",
            kind="candidate_market_batch",
            mint=mint,
            pool=pool,
            stage_kind="MINT_MARKET_BATCH",
            stage_sequence=stage_base + 2,
        )
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
        "tracking_handoff_eligible": tracking_eligible,
        "tracking_requalification_required": requalification_required,
        "evidence_expires_at": evidence_expires_at,
        "liquidity_observed_at": NOW,
        "retained_evidence": retained,
        "liquidity": {
            "liquidity_usd": 4500.0,
            "status": "LIQUIDITY_PROVEN",
            "source_request_id": market_req,
            "source_response_id": market_resp,
            "source_status": "COMPLETE",
            "reason": "AT_OR_ABOVE_3000_FLOOR",
            "outcome_category": "LIQUIDITY_EXACT_ABOVE_FLOOR",
        },
        "holder_condition": "HOLDER_CONCENTRATION_EXTREME",
        "fully_eligible": False,
        "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
    }


def test_01_four_moe_only_two_freeze_ready_capacity_not_met(db) -> None:
    from printer_v1.discovery.memory_observation_activation import (
        measure_freeze_ready_candidates,
    )
    from printer_v1.discovery.eligible_token_supply import (
        acquisition_capacity_met,
    )

    bag = ProvenanceBag()
    rows = [
        _market_item(db, bag, mint=MARKET_MINTS[0][0], pool=MARKET_MINTS[0][1], stage_sequence=1),
        _market_item(db, bag, mint=MARKET_MINTS[1][0], pool=MARKET_MINTS[1][1], stage_sequence=2),
        _direct_item(
            db,
            bag,
            mint=PUMP_MINT,
            pool=PUMP_POOL,
            include_origin=False,
            include_pumpswap=False,
            stage_base=10,
        ),
        _direct_item(
            db,
            bag,
            mint=PUMP_MINT_B,
            pool=PUMP_POOL_B,
            include_origin=False,
            include_pumpswap=False,
            stage_base=20,
        ),
    ]
    assert len(rows) == 4
    assert all(row["memory_observation_eligible"] is True for row in rows)

    measured = measure_freeze_ready_candidates(db, rows, now=NOW, **bag.kwargs())
    assert measured.freeze_ready_depth == 2
    assert acquisition_capacity_met(freeze_ready_depth=measured.freeze_ready_depth) is False
    assert measured.capacity_stop_reason != "ELIGIBLE_CAPACITY_MET"
    depth = observation_reserve_depth_status(measured.freeze_ready_depth)
    assert depth["coverage_blocker"] is True


def test_02_depth_below_four_with_horizon_continues_not_terminal() -> None:
    from printer_v1.discovery.eligible_token_supply import (
        decide_pre_lifecycle_supply_continuation,
    )

    decision = decide_pre_lifecycle_supply_continuation(
        freeze_ready_depth=2,
        enrichment_work_remaining=False,
        source_operations_remaining=10,
        acquisition_deadline_at="2026-09-01T12:16:19+00:00",
        now=NOW,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        refresh_interval_seconds=600,
    )
    assert decision.status == WAITING_FOR_ELIGIBLE_SUPPLY
    assert decision.final_terminal_cause is None
    assert decision.final_terminal_cause != (
        "PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT"
    )


def test_03_direct_pump_missing_roles_not_freeze_ready(db) -> None:
    from printer_v1.discovery.memory_observation_activation import (
        measure_freeze_ready_candidates,
    )

    bag = ProvenanceBag()
    incomplete = _direct_item(
        db,
        bag,
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        include_origin=False,
        include_pumpswap=False,
    )
    measured = measure_freeze_ready_candidates(db, [incomplete], now=NOW, **bag.kwargs())
    assert measured.freeze_ready_depth == 0
    assert PUMP_MINT not in {item["mint"] for item in measured.freeze_ready}
    assert measured.exclusions
    assert measured.exclusions[0]["disposition"] == RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE


def test_04_enrichment_completion_can_make_direct_pump_freeze_ready(db) -> None:
    from printer_v1.discovery.eligible_token_supply import (
        enrich_pre_freeze_retained_evidence,
    )
    from printer_v1.discovery.memory_observation_activation import (
        measure_freeze_ready_candidates,
    )

    bag = ProvenanceBag()
    incomplete = _direct_item(
        db,
        bag,
        mint=PUMP_MINT,
        pool=PUMP_POOL,
        include_origin=False,
        include_pumpswap=False,
        include_market=True,
        stage_base=1,
    )
    before = measure_freeze_ready_candidates(db, [incomplete], now=NOW, **bag.kwargs())
    assert before.freeze_ready_depth == 0

    def fake_runner(
        connection: sqlite3.Connection,
        candidate: Mapping[str, Any],
        *,
        missing_roles: Sequence[str],
        provenance_bag: ProvenanceBag,
        now: str,
    ) -> dict[str, object]:
        updated = dict(candidate)
        retained = dict(updated.get("retained_evidence") or {})
        mint = str(updated["mint"])
        pool = str(updated["pool"])
        if "ORIGIN_LINEAGE" in missing_roles:
            req, resp = _persist_role(
                connection,
                provenance_bag,
                role="ORIGIN_LINEAGE",
                source="solana_rpc",
                kind="restored_pump_migration_transaction",
                mint=mint,
                pool=pool,
                stage_kind="DIRECT_MIGRATION_INTAKE",
                stage_sequence=50,
            )
            retained["ORIGIN_LINEAGE"] = {
                "source_request_id": req,
                "source_response_id": resp,
            }
        if "PUMPSWAP_CONFIRMATION" in missing_roles:
            req, resp = _persist_role(
                connection,
                provenance_bag,
                role="PUMPSWAP_CONFIRMATION",
                source="solana_rpc",
                kind="pumpswap_pool_account_batch",
                mint=mint,
                pool=pool,
                stage_kind="PROTOCOL_CONFIRMATION",
                stage_sequence=51,
            )
            retained["PUMPSWAP_CONFIRMATION"] = {
                "source_request_id": req,
                "source_response_id": resp,
            }
        updated["retained_evidence"] = retained
        return updated

    enriched, report = enrich_pre_freeze_retained_evidence(
        db,
        [incomplete],
        now=NOW,
        provenance_bag=bag,
        enrichment_runner=fake_runner,
        source_operations_remaining=10,
    )
    assert report["attempted_candidates"] == 1
    assert report["direct_provider_calls"] == 0
    after = measure_freeze_ready_candidates(db, enriched, now=NOW, **bag.kwargs())
    assert after.freeze_ready_depth == 1
    assert after.freeze_ready[0]["mint"] == PUMP_MINT


def test_05_depth_four_after_ready_set_freezes_two_plus_two(db) -> None:
    from printer_v1.discovery.eligible_token_supply import acquisition_capacity_met
    from printer_v1.discovery.memory_observation_activation import (
        measure_freeze_ready_candidates,
    )

    bag = ProvenanceBag()
    rows = [
        _market_item(db, bag, mint=mint, pool=pool, stage_sequence=idx + 1)
        for idx, (mint, pool) in enumerate(MARKET_MINTS)
    ]
    measured = measure_freeze_ready_candidates(db, rows, now=NOW, **bag.kwargs())
    assert measured.freeze_ready_depth == 4
    assert acquisition_capacity_met(freeze_ready_depth=measured.freeze_ready_depth) is True
    frozen = freeze_eligible_reserve(
        measured.freeze_ready, cycle_seed="freeze-ready-seed", at=NOW
    )
    assert len(frozen.selected) == 2
    assert len(frozen.alternates[:2]) == 2
    assert frozen.selection_authority["coverage_blocker"] is False


def test_06_honest_exhaustion_terminals_coverage_insufficient() -> None:
    from printer_v1.discovery.eligible_token_supply import (
        decide_pre_lifecycle_supply_continuation,
    )

    decision = decide_pre_lifecycle_supply_continuation(
        freeze_ready_depth=2,
        enrichment_work_remaining=False,
        source_operations_remaining=10,
        acquisition_deadline_at="2026-09-01T11:40:00+00:00",
        now="2026-09-01T11:39:30+00:00",
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        refresh_interval_seconds=600,
    )
    assert decision.status == "PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT"
    assert decision.final_terminal_cause == (
        "PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT"
    )
    assert decision.restart_created is False
    assert decision.successor_created is False


def test_07_duplicate_and_cooldown_cannot_refill_depth(db) -> None:
    from printer_v1.discovery.memory_observation_activation import (
        measure_freeze_ready_candidates,
    )

    bag = ProvenanceBag()
    a = _market_item(db, bag, mint=MARKET_MINTS[0][0], pool=MARKET_MINTS[0][1], stage_sequence=1)
    duplicate = dict(a)
    cooldown = _market_item(
        db, bag, mint=MARKET_MINTS[1][0], pool=MARKET_MINTS[1][1], stage_sequence=2
    )
    cooldown["tracking_handoff_eligible"] = False
    cooldown["tracking_requalification_required"] = True
    measured = measure_freeze_ready_candidates(
        db, [a, duplicate, cooldown], now=NOW, **bag.kwargs()
    )
    assert measured.freeze_ready_depth == 1
    assert {item["mint"] for item in measured.freeze_ready} == {MARKET_MINTS[0][0]}


def test_08_refresh_eligibility_uses_freeze_ready_depth_not_moe_count() -> None:
    # MOE count 4 must not trip CAPACITY_ALREADY_MET when freeze-ready depth is 2.
    eligibility = evaluate_wait_eligibility(
        reserve_depth=2,
        required_capacity=MINIMUM_FREEZE_DEPTH,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        now=NOW,
        acquisition_deadline_at="2026-09-01T12:16:19+00:00",
        source_operations_remaining=10,
        provider_terminal_failure=False,
        supervision_active=True,
        cancellation_requested=False,
        pending_refresh_exists=False,
    )
    assert eligibility.eligible is True
    assert eligibility.reason == WAITING_FOR_ELIGIBLE_SUPPLY

    met = evaluate_wait_eligibility(
        reserve_depth=4,
        required_capacity=MINIMUM_FREEZE_DEPTH,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        now=NOW,
        acquisition_deadline_at="2026-09-01T12:16:19+00:00",
        source_operations_remaining=10,
        provider_terminal_failure=False,
        supervision_active=True,
        cancellation_requested=False,
        pending_refresh_exists=False,
    )
    assert met.eligible is False
    assert met.reason == CAPACITY_ALREADY_MET


def test_08b_enrichment_and_decision_forbid_direct_provider_and_polling() -> None:
    import inspect

    from printer_v1.discovery.eligible_token_supply import (
        decide_pre_lifecycle_supply_continuation,
        enrich_pre_freeze_retained_evidence,
    )
    from printer_v1.discovery.memory_observation_activation import (
        measure_freeze_ready_candidates,
    )

    for fn in (
        measure_freeze_ready_candidates,
        decide_pre_lifecycle_supply_continuation,
        enrich_pre_freeze_retained_evidence,
    ):
        src = inspect.getsource(fn)
        for banned in ("time.sleep(", "requests.get(", "urllib.request", "httpx.", "aiohttp."):
            assert banned not in src
    enrich_src = inspect.getsource(enrich_pre_freeze_retained_evidence)
    assert "enrichment_runner" in enrich_src

from __future__ import annotations

from datetime import datetime, timezone
import base64
import json
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.memory_observation_activation import (
    AdmissionAuthority,
    EvidenceRole,
    FrozenMemoryActivationCandidate,
    TrackingFeasibility,
    required_evidence_roles_for_candidate,
)
from printer_v1.discovery.combined_executor import DiscoveryGateSelectionOutcome
from printer_v1.discovery.permanent_discovery_availability import (
    MEMORY_OBSERVATION_ELIGIBLE,
    SELECTION_FLOOR_USD,
    StageBudget,
    process_protocol_confirmation_queue,
    record_fresh_pool_nominations,
    run_geckoterminal_fresh_nomination,
)
from printer_v1.discovery.selection_authority import (
    SelectionCandidate,
    select_two_candidates,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    LaterCycleCandidateSupply,
    LaterCycleSourceEvidence,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    SOURCE_GOVERNOR_OWNER,
    OwnerPort,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
)
from printer_v1.discovery.pre_admission_materialization import (
    PreAdmissionMaterializationError,
    _admission_states_from_canonical_evidence,
)
from printer_v1.operator_cli.graduated_supply_front_door import (
    CANDIDATE_SUPPLY_READY,
    CandidateTemporalAuthority,
    CandidateTemporalContext,
    GraduatedSupplyError,
    GraduatedSupply,
    SourceSpecificCandidateAdmission,
    _source_specific_admission_for,
)
from printer_v1.operator_cli.later_cycle_graduated_supply import (
    build_later_cycle_graduated_supply,
)
from printer_v1.sources.pumpswap import (
    PUMPSWAP_AMM_PROGRAM_ID,
    _PUMPSWAP_POOL_BASE_MINT_OFFSET,
    _b58decode,
)
from printer_v1.sources.pumpswap_pool_account_batch import (
    fixture_account_batch_transport,
)


NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
WSOL = "So11111111111111111111111111111111111111112"
MINT_A = "6wtZueu89AGwQkGUki3HcerjCDFxLA9PyVUBWQbMpump"
MINT_B = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
POOL_A = "DfxsEZga7jwVhwo6JUfWnDD8tg9aSLcv32UYzLQ3SwqD"
POOL_B = "ECobcS1MSzzAnnzz89xjwRSEYsHAChB7DMbd3G25gwgc"


@pytest.fixture()
def database(tmp_path):
    path = tmp_path / "slice-c.sqlite3"
    apply_migrations(path)
    return path


def _market_admission(slot: int, *, source: str = "dexscreener"):
    return SourceSpecificCandidateAdmission(
        mint=f"mint-{slot}",
        pool_address=f"pool-{slot}",
        market_identity=f"solana-mainnet:pumpswap:pool-{slot}",
        admission_authority=AdmissionAuthority.MARKET_PRESENT_POOL,
        nomination_source=source,
        lineage_state="UNKNOWN_ORIGIN",
        present_pool_confirmed=True,
        temporal_context=CandidateTemporalContext(
            temporal_authority=(
                CandidateTemporalAuthority.RETAINED_MARKET_OBSERVATION_TIME
            ),
            admission_observed_at_utc=NOW.isoformat(),
            pump_origin_block_time_epoch=None,
        ),
    )


def _pool_account(*, mint: str, owner: str = PUMPSWAP_AMM_PROGRAM_ID):
    mint_bytes = _b58decode(mint)
    offset = _PUMPSWAP_POOL_BASE_MINT_OFFSET
    data = b"\x01" * offset + mint_bytes + b"\x02" * (
        301 - offset - len(mint_bytes)
    )
    return {
        "owner": owner,
        "data": [base64.b64encode(data).decode(), "base64"],
    }


def _observation(mint: str, pool: str, *, liquidity_usd, venue="pumpswap"):
    return {
        "mint": mint,
        "pool": pool,
        "base_mint": mint,
        "quote_mint": WSOL,
        "venue": venue,
        "liquidity_usd": liquidity_usd,
        "observed_at": NOW.isoformat(),
    }


def _open(database):
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _ready_market_supply(*admissions: SourceSpecificCandidateAdmission):
    candidates = {
        item.mint.lower(): {
            "mint": item.mint,
            "pool": item.pool_address,
            "pumpswap_pool": item.pool_address,
            "market_identity": item.market_identity,
            "provenance": item.nomination_source,
            "admission_authority": item.admission_authority.value,
            "nomination_source": item.nomination_source,
            "lineage_state": item.lineage_state,
            "exact_present_pool_confirmed": True,
            "liquidity_usd": 3_500.0,
            "liquidity_status": "LIQUIDITY_PROVEN",
            "liquidity": {
                "status": "LIQUIDITY_PROVEN",
                "liquidity_usd": 3_500.0,
                "liquidity_observed_at": NOW.isoformat(),
            },
            "evidence_expires_at": "2026-08-18T12:15:00+00:00",
            "memory_observation_eligible": True,
            "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
        }
        for item in admissions
    }
    return GraduatedSupply(
        ready=True,
        terminal=CANDIDATE_SUPPLY_READY,
        graduated_supply=tuple(admissions),
        graduation_proofs={},
        candidate_a=candidates[admissions[0].mint.lower()],
        candidate_b=candidates[admissions[1].mint.lower()],
        two_candidate_selection={"ready": True},
        handoff_readiness={"ready": True},
        discovery_report={"confirmed_this_cycle": []},
        front_door_report={},
        diagnostics={"shortage_classification": None},
        holder_reserve_supply=tuple(admissions),
        holder_reserve_candidates=candidates,
    )


def test_market_present_pool_authority_survives_later_cycle_carrier(
    database, monkeypatch
) -> None:
    admissions = (_market_admission(1), _market_admission(2, source="geckoterminal"))
    monkeypatch.setattr(
        "printer_v1.operator_cli.later_cycle_graduated_supply.build_graduated_supply",
        lambda *args, **kwargs: _ready_market_supply(*admissions),
    )
    monkeypatch.setattr(
        "printer_v1.operator_cli.later_cycle_graduated_supply._source_lineage",
        lambda *args, **kwargs: (
            LaterCycleSourceEvidence(
                logical_stage="fresh_market_nomination",
                source_request_id=1,
                source_response_id=1,
            ),
        ),
    )

    result = build_later_cycle_graduated_supply(
        database,
        campaign_id="campaign-c",
        campaign_run_id="run-c",
        authoritative_factory_run_id="factory-c",
        proposed_cycle_id="cycle-2",
        proposed_cycle_ordinal=2,
        evaluated_at=NOW,
        execution_id="execution-c",
        selection_seed="seed-c",
        migration_transport=object(),
        graduated_supply_kwargs={},
        holder_evidence_owner=lambda supply: {
            item.mint: {"eligible": True} for item in supply.graduated_supply
        },
    )

    assert len(result.candidates) == 2
    for item in result.candidates:
        assert item.lifecycle_identity == "PRESENT_POOL_CONFIRMED"
        assert item.admission_authority is AdmissionAuthority.MARKET_PRESENT_POOL
        assert item.claims_pump_origin is False
        assert item.claims_pumpswap_graduation is False


def _prepare_callback_database(path):
    connection = sqlite3.connect(path)
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES ('campaign-c','RUNNING','OPERATIONAL_PERSISTENT','db-c','policy-c')"
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json) VALUES (?,?,?,?,?)",
        ("configuration-c", "campaign-c", "a" * 64, "{}", "{}"),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "factory-c",
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            "{}",
            NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "run-c",
            "campaign-c",
            1,
            "RUNNING",
            "factory-c",
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    for slot in (1, 2):
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?, 'solana')",
            (slot, f"mint-{slot}"),
        )
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
            "VALUES (?,?,?,?)",
            (slot, slot, f"pool-{slot}", f"mint-{slot}"),
        )
    request_id = int(
        connection.execute(
            "INSERT INTO printer_source_requests("
            "source_name,request_kind,request_key,requested_at,source_status,data_quality_label) "
            "VALUES ('dexscreener','fresh_profiles','cycle-2:fresh',?,'COMPLETE','CLEAN_DATA')",
            (NOW.isoformat(),),
        ).lastrowid
    )
    response_id = int(
        connection.execute(
            "INSERT INTO printer_source_responses("
            "source_request_id,source_name,received_at,source_status,data_quality_label) "
            "VALUES (?,'dexscreener',?,'COMPLETE','CLEAN_DATA')",
            (request_id, NOW.isoformat()),
        ).lastrowid
    )
    connection.commit()
    connection.close()
    return request_id, response_id


def test_cycle_2_gate_receives_market_authority_without_pump_claims(
    database, monkeypatch
) -> None:
    request_id, response_id = _prepare_callback_database(database)
    admissions = (_market_admission(1), _market_admission(2, source="geckoterminal"))
    candidates = build_later_cycle_graduated_supply
    monkeypatch.setattr(
        "printer_v1.operator_cli.later_cycle_graduated_supply.build_graduated_supply",
        lambda *args, **kwargs: _ready_market_supply(*admissions),
    )
    monkeypatch.setattr(
        "printer_v1.operator_cli.later_cycle_graduated_supply._source_lineage",
        lambda *args, **kwargs: (
            LaterCycleSourceEvidence(
                logical_stage="fresh_market_nomination",
                source_request_id=request_id,
                source_response_id=response_id,
            ),
        ),
    )
    supply = candidates(
        database,
        campaign_id="campaign-c",
        campaign_run_id="run-c",
        authoritative_factory_run_id="factory-c",
        proposed_cycle_id="cycle-2",
        proposed_cycle_ordinal=2,
        evaluated_at=NOW,
        execution_id="execution-c",
        selection_seed="seed-c",
        migration_transport=object(),
        graduated_supply_kwargs={},
        holder_evidence_owner=lambda ready: {
            item.mint: {"eligible": True} for item in ready.graduated_supply
        },
    )
    observed = {}

    def gate(connection, **kwargs):
        observed.update(kwargs)
        return DiscoveryGateSelectionOutcome(
            eligible=tuple(kwargs["candidates"]),
            selected=tuple(kwargs["candidates"]),
            rejection_causes=(),
        )

    monkeypatch.setattr(
        "printer_v1.operator_cli.authoritative_live_operational_campaign."
        "apply_existing_discovery_gate_and_selection",
        gate,
    )
    callback = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=lambda **kwargs: LaterCycleCandidateSupply(
            candidates=supply.candidates,
            source_evidence=supply.source_evidence,
            terminal_cause=None,
        )
    )._build_later_cycle_discovery_callback(
        db_path=database,
        configuration_id="configuration-c",
    )
    health = MultiCycleAdmissionHealth(
        source_budget_available=True,
        provider_budgets_available=True,
        scheduler_budget_available=True,
        scheduler_due_work_healthy=True,
        close_reserve_available=True,
        campaign_supervision_healthy=True,
        lease_healthy=True,
        db_healthy=True,
        shared_terminal_condition=False,
        cancellation_requested=False,
        discovery_capacity_available=True,
        protected_work_capacity_available=True,
    )
    result = callback(
        campaign_id="campaign-c",
        campaign_run_id="run-c",
        authoritative_factory_run_id="factory-c",
        cycle_id="cycle-2",
        cycle_ordinal=2,
        cycle_cutoff=NOW.isoformat(),
        evaluated_at=NOW.isoformat(),
        selection_seed="seed-c",
        source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, True),
        central_scheduler=OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
        admission_health=health,
    )

    assert result.state == "PAIR_READY"
    assert observed["market_authority_mints"] == frozenset({"mint-1", "mint-2"})
    assert {item.origin_state for item in observed["candidates"]} == {"NOT_CLAIMED"}
    assert {item.pumpswap_state for item in observed["candidates"]} == {"NOT_CLAIMED"}
    connection = sqlite3.connect(database)
    try:
        rows = connection.execute(
            "SELECT lifecycle_identity,canonical_evidence_json "
            "FROM printer_pre_admission_discovery_attempt_items ORDER BY slot_ordinal"
        ).fetchall()
        assert {row[0] for row in rows} == {"PRESENT_POOL_CONFIRMED"}
        assert {
            json.loads(row[1])["candidate"]["admission_authority"] for row in rows
        } == {"MARKET_PRESENT_POOL"}
    finally:
        connection.close()


def test_materialization_projects_truthful_source_specific_claim_states() -> None:
    market = _admission_states_from_canonical_evidence(
        json.dumps(
            {
                "candidate": {
                    "admission_authority": "MARKET_PRESENT_POOL",
                    "lineage_state": "UNKNOWN_ORIGIN",
                }
            }
        ),
        lifecycle_identity="PRESENT_POOL_CONFIRMED",
    )
    assert market == ("NOT_CLAIMED", "NOT_CLAIMED")

    direct = _admission_states_from_canonical_evidence(
        json.dumps(
            {
                "candidate": {
                    "admission_authority": "DIRECT_PUMP_PUMPSWAP",
                    "lineage_state": "PUMP_GRADUATION_CONFIRMED",
                }
            }
        ),
        lifecycle_identity="PUMPSWAP_GRADUATED_CONFIRMED",
    )
    assert direct == ("CONFIRMED", "CONFIRMED")

    with pytest.raises(
        PreAdmissionMaterializationError,
        match="FROZEN_ADMISSION_AUTHORITY_DRIFT",
    ):
        _admission_states_from_canonical_evidence(
            '{"candidate":{"admission_authority":"MARKET_PRESENT_POOL"}}',
            lifecycle_identity="PUMPSWAP_GRADUATED_CONFIRMED",
        )


@pytest.mark.parametrize("source", ["dexscreener", "geckoterminal"])
def test_fresh_no_registry_candidate_promotes_through_market_present_pool(
    database, source
) -> None:
    connection = _open(database)
    try:
        if source == "dexscreener":
            request_id = int(
                connection.execute(
                    "INSERT INTO printer_source_requests("
                    "source_name,request_kind,request_key,requested_at,source_status,data_quality_label) "
                    "VALUES ('dexscreener','fresh_profiles','slice-c-dex',?,'COMPLETE','CLEAN_DATA')",
                    (NOW.isoformat(),),
                ).lastrowid
            )
            response_id = int(
                connection.execute(
                    "INSERT INTO printer_source_responses("
                    "source_request_id,source_name,received_at,source_status,data_quality_label) "
                    "VALUES (?,'dexscreener',?,'COMPLETE','CLEAN_DATA')",
                    (request_id, NOW.isoformat()),
                ).lastrowid
            )
            record_fresh_pool_nominations(
                connection,
                observations=[
                    _observation(MINT_A, POOL_A, liquidity_usd=4_500.0)
                ],
                source=source,
                request_id=request_id,
                response_id=response_id,
                now=NOW.isoformat(),
                campaign_id="campaign-c",
            )
        else:
            report = run_geckoterminal_fresh_nomination(
                connection,
                request_key="slice-c-gecko",
                now=NOW.isoformat(),
                campaign_id="campaign-c",
                run_id="run-c",
                cycle_id="cycle-2",
                transport=lambda context: {
                    "data": [
                        {
                            "id": "solana_" + POOL_A,
                            "attributes": {
                                "address": POOL_A,
                                "base_token_address": MINT_A,
                                "quote_token_address": WSOL,
                                "dex": "pumpswap",
                                "reserve_in_usd": "4500.0",
                            },
                            "relationships": {
                                "base_token": {
                                    "data": {"id": "solana_" + MINT_A}
                                },
                                "quote_token": {
                                    "data": {"id": "solana_" + WSOL}
                                },
                                "dex": {"data": {"id": "pumpswap"}},
                            },
                        }
                    ],
                    "response_bytes": 400,
                },
            )
            assert report["nominations"]

        protocol = process_protocol_confirmation_queue(
            connection,
            stage_budget=StageBudget.permanent_discovery_default(),
            now=NOW.isoformat(),
            campaign_id="campaign-c",
            run_id="run-c",
            cycle_id="cycle-2",
            account_batch_transport=fixture_account_batch_transport(
                {POOL_A: _pool_account(mint=MINT_A)}
            ),
        )

        assert len(protocol["promoted_observation_eligible"]) == 1
        promoted = protocol["promoted_observation_eligible"][0]
        assert promoted["admission_authority"] == "MARKET_PRESENT_POOL"
        assert promoted["nomination_source"] == source
        assert promoted["lineage_state"] == "UNKNOWN_ORIGIN"
        assert promoted["exact_present_pool_confirmed"] is True
        assert promoted["liquidity_usd"] >= SELECTION_FLOOR_USD
        assert not {
            "migration_signature",
            "graduation_slot",
            "graduation_block_time",
            "direct_pump_evidence",
        } & set(promoted)
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_pumpswap_graduated_candidate_registry"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_discovery_reserve_layers "
            "WHERE mint_identity=? AND pool_address=? AND reserve_layer=?",
            (MINT_A, POOL_A, MEMORY_OBSERVATION_ELIGIBLE),
        ).fetchone()[0] == 1
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("observation", "expected_reason"),
    [
        (_observation(MINT_A, POOL_A, liquidity_usd=2_999.99), "BELOW_3000_FLOOR"),
        (_observation(MINT_A, POOL_A, liquidity_usd=None), "LIQUIDITY_UNKNOWN"),
        (_observation(MINT_A, POOL_A, liquidity_usd=4_000.0, venue="unsupported"), "PROTOCOL_UNSUPPORTED_VENUE"),
        (
            {
                **_observation(MINT_A, POOL_A, liquidity_usd=4_000.0),
                "base_mint": MINT_B,
            },
            "INCOMPLETE_ORIENTATION",
        ),
    ],
)
def test_fresh_market_prefilter_failures_never_enter_protocol_or_registry(
    database, observation, expected_reason
) -> None:
    connection = _open(database)
    try:
        report = record_fresh_pool_nominations(
            connection,
            observations=[observation],
            source="dexscreener",
            request_id=1,
            now=NOW.isoformat(),
            campaign_id="campaign-c",
        )
        transport_calls = 0

        def forbidden_transport(context):
            nonlocal transport_calls
            transport_calls += 1
            raise AssertionError("ineligible nomination reached protocol transport")

        protocol = process_protocol_confirmation_queue(
            connection,
            stage_budget=StageBudget.permanent_discovery_default(),
            now=NOW.isoformat(),
            account_batch_transport=forbidden_transport,
        )
        reasons = {
            item.get("reason") for item in report.get("exclusions", [])
        } | {
            row[0]
            for row in connection.execute(
                "SELECT current_reason FROM printer_exact_market_states"
            ).fetchall()
        }
        assert expected_reason in reasons
        assert protocol["promoted_observation_eligible"] == []
        assert transport_calls == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_pumpswap_graduated_candidate_registry"
        ).fetchone()[0] == 0
    finally:
        connection.close()


@pytest.mark.parametrize("mismatch", ["owner", "base_mint"])
def test_present_pool_protocol_identity_mismatch_fails_closed(database, mismatch) -> None:
    connection = _open(database)
    try:
        record_fresh_pool_nominations(
            connection,
            observations=[_observation(MINT_A, POOL_A, liquidity_usd=4_500.0)],
            source="dexscreener",
            request_id=1,
            now=NOW.isoformat(),
            campaign_id="campaign-c",
        )
        account = (
            _pool_account(
                mint=MINT_A,
                owner="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
            )
            if mismatch == "owner"
            else _pool_account(mint=MINT_B)
        )
        report = process_protocol_confirmation_queue(
            connection,
            stage_budget=StageBudget.permanent_discovery_default(),
            now=NOW.isoformat(),
            account_batch_transport=fixture_account_batch_transport({POOL_A: account}),
        )
        assert report["promoted_observation_eligible"] == []
        assert report["outcomes"][0]["outcome"] == (
            "POOL_OWNER_MISMATCH" if mismatch == "owner" else "BASE_MINT_MISMATCH"
        )
    finally:
        connection.close()


def test_source_specific_market_admission_requires_no_direct_pump_evidence() -> None:
    item = {
        "mint": MINT_A,
        "pool": POOL_A,
        "market_identity": f"solana-mainnet:pumpswap:{POOL_A}",
        "admission_authority": "MARKET_PRESENT_POOL",
        "nomination_source": "dexscreener",
        "lineage_state": "UNKNOWN_ORIGIN",
        "exact_present_pool_confirmed": True,
        "liquidity_observed_at": NOW.isoformat(),
    }
    admission = _source_specific_admission_for(item)
    assert admission.admission_authority is AdmissionAuthority.MARKET_PRESENT_POOL
    assert admission.origin_proof is None
    assert admission.pumpswap_proof is None

    with pytest.raises(GraduatedSupplyError, match="DIRECT_PUMP_EVIDENCE_MISSING"):
        _source_specific_admission_for(
            {
                **item,
                "admission_authority": "DIRECT_PUMP_PUMPSWAP",
                "lineage_state": "PUMP_GRADUATION_CONFIRMED",
            }
        )


@pytest.mark.parametrize(
    "override",
    [
        {"nomination_source": "unknown"},
        {"exact_present_pool_confirmed": False},
        {"lineage_state": "PUMP_GRADUATION_CONFIRMED"},
        {"market_identity": "solana-mainnet:pumpswap:other-pool"},
    ],
)
def test_source_specific_market_admission_rejects_unproven_or_conflicting_claims(
    override,
) -> None:
    item = {
        "mint": MINT_A,
        "pool": POOL_A,
        "market_identity": f"solana-mainnet:pumpswap:{POOL_A}",
        "admission_authority": "MARKET_PRESENT_POOL",
        "nomination_source": "dexscreener",
        "lineage_state": "UNKNOWN_ORIGIN",
        "exact_present_pool_confirmed": True,
        "liquidity_observed_at": NOW.isoformat(),
        **override,
    }
    with pytest.raises(GraduatedSupplyError):
        _source_specific_admission_for(item)


def _activation_candidate(authority: AdmissionAuthority):
    direct = authority is AdmissionAuthority.DIRECT_PUMP_PUMPSWAP
    return FrozenMemoryActivationCandidate(
        slot_ordinal=1,
        mint=MINT_A,
        pool=POOL_A,
        market_identity=f"solana-mainnet:pumpswap:{POOL_A}",
        lifecycle_identity=(
            "PUMPSWAP_GRADUATED_CONFIRMED"
            if direct
            else "PRESENT_POOL_CONFIRMED"
        ),
        activation_route=authority.value,
        provenance="direct_pump_migration" if direct else "dexscreener",
        memory_observation_eligible=True,
        fully_eligible=False,
        holder_condition="UNKNOWN",
        holder_evidence_status="UNKNOWN",
        future_action_eligibility="BLOCKED_OR_UNKNOWN",
        evidence_expires_at="2026-08-18T12:15:00+00:00",
        liquidity_observed_at=NOW.isoformat(),
        tracking_feasibility=TrackingFeasibility(
            eligible=True,
            reason_code="ELIGIBLE",
            tracking_queue_id=None,
            tracking_queue_status=None,
            requalification_required=False,
            cooldown_until=None,
            assessed_at=NOW.isoformat(),
        ),
        retained_evidence_references=(),
        admission_authority=authority,
        claims_pump_origin=direct,
        claims_pumpswap_graduation=direct,
    )


def test_activation_role_matrix_preserves_market_and_direct_truth() -> None:
    assert required_evidence_roles_for_candidate(
        _activation_candidate(AdmissionAuthority.MARKET_PRESENT_POOL)
    ) == (EvidenceRole.MARKET_OBSERVATION,)
    assert required_evidence_roles_for_candidate(
        _activation_candidate(AdmissionAuthority.DIRECT_PUMP_PUMPSWAP)
    ) == (
        EvidenceRole.ORIGIN_LINEAGE,
        EvidenceRole.PUMPSWAP_CONFIRMATION,
        EvidenceRole.MARKET_OBSERVATION,
    )


def test_neutral_selection_deduplicates_same_exact_candidate_and_blocks_pool_conflict() -> None:
    direct = SelectionCandidate(
        mint=MINT_A,
        pair_address=POOL_A,
        market_identity=f"solana-mainnet:pumpswap:{POOL_A}",
        provenance="direct_pump_migration",
        lifecycle_state="PUMPSWAP_GRADUATED_CONFIRMED",
    )
    same_market = SelectionCandidate(
        mint=MINT_A,
        pair_address=POOL_A,
        market_identity=f"solana-mainnet:pumpswap:{POOL_A}",
        provenance="dexscreener",
        lifecycle_state="PRESENT_POOL_CONFIRMED",
    )
    other_market = SelectionCandidate(
        mint=MINT_B,
        pair_address=POOL_B,
        market_identity=f"solana-mainnet:pumpswap:{POOL_B}",
        provenance="geckoterminal",
        lifecycle_state="PRESENT_POOL_CONFIRMED",
    )
    mixed = select_two_candidates(
        [direct, same_market, other_market], cycle_seed="slice-c-mixed"
    )
    assert mixed.ready is True
    assert {(item.mint, item.pair_address) for item in mixed.selected} == {
        (MINT_A, POOL_A),
        (MINT_B, POOL_B),
    }
    assert mixed.pool_size == 2

    conflict = select_two_candidates(
        [
            direct,
            SelectionCandidate(
                mint=MINT_A,
                pair_address=POOL_B,
                market_identity=f"solana-mainnet:pumpswap:{POOL_B}",
                provenance="geckoterminal",
                lifecycle_state="PRESENT_POOL_CONFIRMED",
            ),
        ],
        cycle_seed="slice-c-conflict",
    )
    assert conflict.ready is False
    assert len(conflict.selected) == 0


def test_two_market_candidates_reach_neutral_two_slot_selection_without_scores() -> None:
    selection = select_two_candidates(
        [
            SelectionCandidate(
                mint=MINT_A,
                pair_address=POOL_A,
                market_identity=f"solana-mainnet:pumpswap:{POOL_A}",
                provenance="dexscreener",
                lifecycle_state="PRESENT_POOL_CONFIRMED",
            ),
            SelectionCandidate(
                mint=MINT_B,
                pair_address=POOL_B,
                market_identity=f"solana-mainnet:pumpswap:{POOL_B}",
                provenance="geckoterminal",
                lifecycle_state="PRESENT_POOL_CONFIRMED",
            ),
        ],
        cycle_seed="slice-c-two-market",
    )
    assert selection.ready is True
    assert len(selection.selected) == 2
    assert all("score" not in row for row in selection.funnel)

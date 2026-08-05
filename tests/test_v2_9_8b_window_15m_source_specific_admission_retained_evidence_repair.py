"""Disposable proof for source-specific WINDOW_15M candidate admission."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace
from types import SimpleNamespace

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.memory_observation_activation import (
    AdmissionAuthority,
    ActivationPurpose,
    EvidenceRole,
    FrozenMemoryActivationCandidate,
    FrozenMemoryActivationSet,
    ManifestRequestEntry,
    MemoryObservationActivationError,
    RetainedEvidenceReference,
    TrackingFeasibility,
    required_evidence_roles_for_candidate,
    validate_memory_activation_set,
)
from printer_v1.operator_cli.graduated_supply_front_door import (
    build_graduated_supply,
)
from printer_v1.discovery.combined_executor import (
    CombinedDiscoveryFixtures,
    CombinedPumpfunCampaignExecutor,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    OwnerPort,
    SOURCE_GOVERNOR_OWNER,
)
from test_v2_9_8b_window_15m_memory_activation_clean_object_integrity_repair import (
    _BatchScopedDiscoveryPersistenceProof,
    _activation_set as _legacy_activation_set,
)


NOW = "2026-08-05T22:52:58.929904+00:00"
EXPIRES = "2026-08-05T23:22:58.929904+00:00"
CAMPAIGN = "campaign-source-specific"
RUN = "run-source-specific"
CYCLE = "cycle-source-specific"
DEX_MINT = "6a4TCQoCFXXNK8jUtjCMPqvoaLGx1oNLrciBiRafpump"
DEX_POOL = "GzDaX3zHxDd5KUGKo5fHHg93arcPArrseAoEfP685JGQ"
GECKO_MINT = "Gecko11111111111111111111111111111111111111"
GECKO_POOL = "GeckoPool11111111111111111111111111111111111"
PUMP_MINT = "Pump111111111111111111111111111111111111111"
PUMP_POOL = "PumpPool111111111111111111111111111111111111"


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "source-specific.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def _transport_key(source: str, kind: str, mint: str, ordinal: int = 1):
    return (
        "SOURCE_SPECIFIC_ADMISSION",
        source,
        source,
        kind,
        "fixture-transport",
        ordinal,
        "MINT",
        mint,
        128,
        1,
        "COMPLETE",
        None,
    )


def _persist_reference(
    connection: sqlite3.Connection,
    *,
    role: EvidenceRole,
    source: str,
    kind: str,
    mint: str,
    pool: str,
    chain: str = "solana",
):
    payload = {
        "chain": chain,
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
        (source, kind, NOW, f"{mint}:{role.value}"),
    )
    response = connection.execute(
        """INSERT INTO printer_source_responses(
               source_request_id,source_name,received_at,status_code,
               source_status,data_quality_label,response_hash,
               normalized_payload_json
           ) VALUES (?,?,?,200,'COMPLETE','CLEAN_DATA',?,?)""",
        (int(request.lastrowid), source, NOW, digest, payload_json),
    )
    key = _transport_key(source, kind, mint)
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
    )
    return reference, entry


def _tracking():
    return TrackingFeasibility(
        eligible=True,
        reason_code="TRACKING_HANDOFF_ELIGIBLE",
        tracking_queue_id=None,
        tracking_queue_status=None,
        requalification_required=False,
        cooldown_until=None,
        assessed_at=NOW,
    )


def _candidate(
    *,
    ordinal: int,
    mint: str,
    pool: str,
    authority: AdmissionAuthority,
    references,
):
    direct = authority is AdmissionAuthority.DIRECT_PUMP_PUMPSWAP
    return FrozenMemoryActivationCandidate(
        slot_ordinal=ordinal,
        mint=mint,
        pool=pool,
        market_identity=f"solana-mainnet:present-pool:{pool}",
        lifecycle_identity=(
            "PUMPSWAP_GRADUATED_CONFIRMED" if direct else "PRESENT_POOL_CONFIRMED"
        ),
        activation_route=authority.value,
        provenance=("PUMP_GRADUATION_CONFIRMED" if direct else "UNKNOWN_ORIGIN"),
        admission_authority=authority,
        claims_pump_origin=direct,
        claims_pumpswap_graduation=direct,
        memory_observation_eligible=True,
        fully_eligible=False,
        holder_condition="HOLDER_CONCENTRATION_UNKNOWN",
        holder_evidence_status="SOURCE_UNAVAILABLE_OR_INCOMPLETE",
        future_action_eligibility="BLOCKED_OR_UNKNOWN",
        evidence_expires_at=EXPIRES,
        liquidity_observed_at=NOW,
        tracking_feasibility=_tracking(),
        retained_evidence_references=tuple(references),
    )


def _market(connection, *, ordinal, mint, pool, source):
    kind = (
        "dexscreener_fresh_profiles"
        if source == "dexscreener"
        else "geckoterminal_new_pool_discovery"
    )
    ref, entry = _persist_reference(
        connection,
        role=EvidenceRole.MARKET_OBSERVATION,
        source=source,
        kind=kind,
        mint=mint,
        pool=pool,
    )
    return (
        _candidate(
            ordinal=ordinal,
            mint=mint,
            pool=pool,
            authority=AdmissionAuthority.MARKET_PRESENT_POOL,
            references=(ref,),
        ),
        (entry,),
    )


def _pump(connection, *, ordinal, mint=PUMP_MINT, pool=PUMP_POOL):
    specs = (
        (EvidenceRole.ORIGIN_LINEAGE, "solana_rpc", "restored_pump_migration_transaction"),
        (EvidenceRole.PUMPSWAP_CONFIRMATION, "pumpswap", "pumpswap_signature_pool_resolution"),
        (EvidenceRole.MARKET_OBSERVATION, "dexscreener", "candidate_market_batch"),
    )
    refs = []
    entries = []
    for role, source, kind in specs:
        ref, entry = _persist_reference(
            connection, role=role, source=source, kind=kind, mint=mint, pool=pool
        )
        refs.append(ref)
        entries.append(entry)
    return (
        _candidate(
            ordinal=ordinal,
            mint=mint,
            pool=pool,
            authority=AdmissionAuthority.DIRECT_PUMP_PUMPSWAP,
            references=refs,
        ),
        tuple(entries),
    )


def _activation(selected, entries):
    entries = tuple(entry for group in entries for entry in group)
    return FrozenMemoryActivationSet(
        activation_purpose=ActivationPurpose.MEMORY_OBSERVATION,
        readiness_id="ready-source-specific",
        selection_seed="seed-source-specific",
        selected=tuple(selected),
        alternates=(
            replace(selected[0], slot_ordinal=3),
            replace(selected[1], slot_ordinal=4),
        ),
        manifest_request_ids=tuple(entry.source_request_id for entry in entries),
        manifest_transport_identity_keys=tuple(
            key for entry in entries for key in entry.transport_identity_keys
        ),
        frozen_at=NOW,
        expires_at=EXPIRES,
        manifest_entries=entries,
    )


@pytest.mark.parametrize(
    ("source", "mint", "pool"),
    (
        ("dexscreener", DEX_MINT, DEX_POOL),
        ("geckoterminal", GECKO_MINT, GECKO_POOL),
    ),
)
def test_market_present_pool_candidate_needs_only_market_role(db, source, mint, pool):
    first, first_entries = _market(
        db, ordinal=1, source=source, mint=mint, pool=pool
    )
    second, second_entries = _market(
        db,
        ordinal=2,
        source="dexscreener" if source == "geckoterminal" else "geckoterminal",
        mint=DEX_MINT if mint != DEX_MINT else GECKO_MINT,
        pool=DEX_POOL if pool != DEX_POOL else GECKO_POOL,
    )
    activation = _activation((first, second), (first_entries, second_entries))
    report = validate_memory_activation_set(
        db, activation, now=NOW, expected_ownership=(CAMPAIGN, RUN, CYCLE)
    )
    assert required_evidence_roles_for_candidate(first) == (
        EvidenceRole.MARKET_OBSERVATION,
    )
    assert report["reconciliation_status"] == "PASS"
    assert report["per_role_request_ids"]["ORIGIN_LINEAGE"] == []
    assert report["per_role_request_ids"]["PUMPSWAP_CONFIRMATION"] == []
    assert first.provenance == "UNKNOWN_ORIGIN"


def test_market_missing_or_mismatched_exact_pool_fails_closed(db):
    first, entries = _market(
        db, ordinal=1, source="dexscreener", mint=DEX_MINT, pool=DEX_POOL
    )
    second, second_entries = _market(
        db, ordinal=2, source="geckoterminal", mint=GECKO_MINT, pool=GECKO_POOL
    )
    for bad_pool, code in (("", "ACTIVATION_POOL_MISSING"), ("WrongPool", "ACTIVATION_MARKET_IDENTITY_MISMATCH")):
        bad = replace(first, pool=bad_pool)
        activation = _activation((bad, second), (entries, second_entries))
        with pytest.raises(MemoryObservationActivationError) as exc:
            validate_memory_activation_set(db, activation, now=NOW)
        assert exc.value.code == code


def test_market_missing_governed_response_transport_evidence_fails_closed(db):
    first, entries = _market(
        db, ordinal=1, source="dexscreener", mint=DEX_MINT, pool=DEX_POOL
    )
    second, second_entries = _market(
        db, ordinal=2, source="geckoterminal", mint=GECKO_MINT, pool=GECKO_POOL
    )
    market_ref = first.retained_evidence_references[0]
    no_transport = replace(market_ref, transport_identity_keys=())
    activation = _activation(
        (replace(first, retained_evidence_references=(no_transport,)), second),
        (entries, second_entries),
    )
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(db, activation, now=NOW)
    assert exc.value.code == "RETAINED_REQUEST_TRANSPORT_IDENTITY_MISSING"


def test_direct_pump_candidate_requires_pump_specific_roles_and_exact_pool(db):
    first, first_entries = _pump(db, ordinal=1)
    second, second_entries = _pump(
        db,
        ordinal=2,
        mint="Pump222222222222222222222222222222222222222",
        pool="PumpPool222222222222222222222222222222222222",
    )
    assert set(required_evidence_roles_for_candidate(first)) == {
        EvidenceRole.ORIGIN_LINEAGE,
        EvidenceRole.PUMPSWAP_CONFIRMATION,
        EvidenceRole.MARKET_OBSERVATION,
    }
    missing = replace(
        first,
        retained_evidence_references=tuple(
            ref
            for ref in first.retained_evidence_references
            if ref.evidence_role is not EvidenceRole.PUMPSWAP_CONFIRMATION
        ),
    )
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            _activation((missing, second), (first_entries, second_entries)),
            now=NOW,
        )
    assert exc.value.code == "RETAINED_EVIDENCE_ROLE_MISSING"

    mismatched = replace(
        first,
        retained_evidence_references=tuple(
            replace(ref, target_pool="WrongPool")
            if ref.evidence_role is EvidenceRole.PUMPSWAP_CONFIRMATION
            else ref
            for ref in first.retained_evidence_references
        ),
    )
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            _activation((mismatched, second), (first_entries, second_entries)),
            now=NOW,
        )
    assert exc.value.code == "RETAINED_EVIDENCE_TARGET_MISMATCH"


@pytest.mark.parametrize("composition", ("market", "pump", "mixed"))
def test_two_slot_role_matrices_are_independent_of_slot_ordinal(db, composition):
    market1, market_entries1 = _market(
        db, ordinal=1, source="dexscreener", mint=DEX_MINT, pool=DEX_POOL
    )
    market2, market_entries2 = _market(
        db, ordinal=2, source="geckoterminal", mint=GECKO_MINT, pool=GECKO_POOL
    )
    pump1, pump_entries1 = _pump(db, ordinal=1)
    pump2, pump_entries2 = _pump(
        db,
        ordinal=2,
        mint="Pump222222222222222222222222222222222222222",
        pool="PumpPool222222222222222222222222222222222222",
    )
    if composition == "market":
        selected, entries = (market1, market2), (market_entries1, market_entries2)
    elif composition == "pump":
        selected, entries = (pump1, pump2), (pump_entries1, pump_entries2)
    else:
        selected, entries = (market1, pump2), (market_entries1, pump_entries2)
    report = validate_memory_activation_set(
        db,
        _activation(selected, entries),
        now=NOW,
        expected_ownership=(CAMPAIGN, RUN, CYCLE),
    )
    assert report["reconciliation_status"] == "PASS"
    assert [candidate.slot_ordinal for candidate in selected] == [1, 2]
    for candidate in selected:
        roles = {ref.evidence_role for ref in candidate.retained_evidence_references}
        assert roles == set(required_evidence_roles_for_candidate(candidate))


def test_market_response_must_confirm_solana_chain(db):
    first, entries = _market(
        db, ordinal=1, source="dexscreener", mint=DEX_MINT, pool=DEX_POOL
    )
    ref = first.retained_evidence_references[0]
    response = db.execute(
        "SELECT normalized_payload_json FROM printer_source_responses WHERE id=?",
        (ref.source_response_id,),
    ).fetchone()
    payload = json.loads(response[0])
    payload["chain"] = "ethereum"
    payload_json = json.dumps(payload, sort_keys=True)
    digest = hashlib.sha256(payload_json.encode()).hexdigest()
    db.execute(
        "UPDATE printer_source_responses SET normalized_payload_json=?,response_hash=? WHERE id=?",
        (payload_json, digest, ref.source_response_id),
    )
    first = replace(
        first,
        retained_evidence_references=(replace(ref, raw_payload_hash=digest),),
    )
    second, second_entries = _market(
        db, ordinal=2, source="geckoterminal", mint=GECKO_MINT, pool=GECKO_POOL
    )
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            _activation((first, second), (entries, second_entries)),
            now=NOW,
        )
    assert exc.value.code == "MARKET_ADMISSION_SOLANA_CONFIRMATION_MISSING"


def test_market_activation_synthesizes_no_registry_source_or_financial_rows(db):
    first, first_entries = _market(
        db, ordinal=1, source="dexscreener", mint=DEX_MINT, pool=DEX_POOL
    )
    second, second_entries = _market(
        db, ordinal=2, source="geckoterminal", mint=GECKO_MINT, pool=GECKO_POOL
    )
    activation = _activation(
        (first, second), (first_entries, second_entries)
    )
    before_source = tuple(
        db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "printer_source_requests",
            "printer_source_responses",
            "printer_source_failures",
        )
    )
    validate_memory_activation_set(db, activation, now=NOW)
    after_source = tuple(
        db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "printer_source_requests",
            "printer_source_responses",
            "printer_source_failures",
        )
    )
    assert after_source == before_source
    assert db.execute(
        "SELECT COUNT(*) FROM printer_pumpswap_graduated_candidate_registry"
    ).fetchone()[0] == 0
    for table in (
        "printer_episode_memory",
        "printer_memory_retrieval",
        "printer_paper_decisions",
        "printer_paper_positions",
        "printer_paper_trades",
        "printer_paper_trade_audit",
    ):
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        assert exists is None or db.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0] == 0


def test_market_projection_omits_pump_specific_projection_rows(monkeypatch):
    proof = _BatchScopedDiscoveryPersistenceProof()
    proof.setUp()
    try:
        command, cycle_id = proof._create_command(91)
        connection = sqlite3.connect(proof.db)
        connection.row_factory = sqlite3.Row
        try:
            activation = _legacy_activation_set(connection)
            converted = []
            for candidate in activation.selected:
                market_ref = next(
                    ref
                    for ref in candidate.retained_evidence_references
                    if ref.evidence_role is EvidenceRole.MARKET_OBSERVATION
                )
                row = connection.execute(
                    "SELECT normalized_payload_json FROM printer_source_responses WHERE id=?",
                    (market_ref.source_response_id,),
                ).fetchone()
                payload = json.loads(row[0])
                payload["chain"] = "solana"
                payload_json = json.dumps(payload, sort_keys=True)
                digest = hashlib.sha256(payload_json.encode()).hexdigest()
                connection.execute(
                    "UPDATE printer_source_responses SET normalized_payload_json=?,response_hash=? WHERE id=?",
                    (payload_json, digest, market_ref.source_response_id),
                )
                converted.append(
                    replace(
                        candidate,
                        lifecycle_identity="PRESENT_POOL_CONFIRMED",
                        activation_route="MARKET_PRESENT_POOL",
                        provenance="UNKNOWN_ORIGIN",
                        admission_authority=AdmissionAuthority.MARKET_PRESENT_POOL,
                        claims_pump_origin=False,
                        claims_pumpswap_graduation=False,
                        retained_evidence_references=(
                            replace(
                                market_ref,
                                raw_payload_hash=digest,
                                campaign_id=command.campaign_id,
                                campaign_run_id=command.run_id,
                                cycle_id=cycle_id,
                            ),
                        ),
                    )
                )
            activation = replace(activation, selected=tuple(converted))
            connection.commit()
            source_before = tuple(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "printer_source_requests",
                    "printer_source_responses",
                    "printer_source_failures",
                )
            )
        finally:
            connection.close()

        fixtures = CombinedDiscoveryFixtures(
            cycle_id=cycle_id,
            cycle_cutoff="2026-08-05T10:06:00+00:00",
            campaign_selection_seed="source-specific-projection",
            provider_contract_versions={"retained": "V1"},
            git_provenance_identity="source-specific-test",
            evaluated_at="2026-08-05T10:00:00+00:00",
            holder_evidence_eligibility={
                candidate.mint.lower(): {
                    "eligible": False,
                    "reason": "HOLDER_UNKNOWN",
                }
                for candidate in activation.selected
            },
            memory_activation_set=activation,
        )
        executor = CombinedPumpfunCampaignExecutor(fixtures)
        monkeypatch.setattr(
            executor,
            "_governed_request",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("new source request")
            ),
        )
        monkeypatch.setattr(
            executor,
            "_store_response",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("new source response")
            ),
        )
        result = executor.execute(
            command=command,
            source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, True),
            central_scheduler=OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
        )
        assert result.terminal_status == "COMPLETED", result
        connection = sqlite3.connect(proof.db)
        try:
            source_after = tuple(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "printer_source_requests",
                    "printer_source_responses",
                    "printer_source_failures",
                )
            )
            assert source_after == source_before
            assert connection.execute(
                "SELECT COUNT(*) FROM printer_discovery_origin_verifications"
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT COUNT(*) FROM printer_discovery_pumpswap_confirmations"
            ).fetchone()[0] == 0
        finally:
            connection.close()
    finally:
        proof.tearDown()


def _supply_candidate(mint, pool, *, source, authority, direct_evidence=None):
    return {
        "mint": mint,
        "pool": pool,
        "market_identity": f"solana-mainnet:present-pool:{pool}",
        "provenance": source,
        "admission_authority": authority,
        "lineage_state": (
            "PUMP_GRADUATION_CONFIRMED"
            if authority == "DIRECT_PUMP_PUMPSWAP"
            else "UNKNOWN_ORIGIN"
        ),
        "nomination_source": source,
        "exact_present_pool_confirmed": True,
        "memory_observation_eligible": True,
        "eligible": True,
        "evidence_expires_at": EXPIRES,
        "liquidity": {
            "status": "LIQUIDITY_PROVEN",
            "liquidity_usd": 12_000.0,
            "mint": mint,
            "pool": pool,
            "source_request_id": 11,
            "source_response_id": 21,
        },
        "direct_pump_evidence": direct_evidence,
    }


@pytest.mark.parametrize("route", ("market", "pump"))
def test_supply_build_performs_no_post_selection_registry_lookup(
    db, monkeypatch, route
):
    import printer_v1.discovery.eligible_token_supply as eligible_supply
    import printer_v1.operator_cli.graduated_supply_front_door as front_door

    if route == "market":
        candidates = (
            _supply_candidate(
                DEX_MINT,
                DEX_POOL,
                source="dexscreener",
                authority="MARKET_PRESENT_POOL",
            ),
            _supply_candidate(
                GECKO_MINT,
                GECKO_POOL,
                source="geckoterminal",
                authority="MARKET_PRESENT_POOL",
            ),
        )
    else:
        def direct(mint, pool):
            return _supply_candidate(
                mint,
                pool,
                source="direct_pump_migration",
                authority="DIRECT_PUMP_PUMPSWAP",
                direct_evidence={
                    "mint": mint,
                    "pool": pool,
                    "migration_signature": f"migration:{mint}",
                    "graduation_slot": 10,
                    "graduation_block_time": 20,
                    "pumpswap_program_id": "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA",
                    "confirmed": True,
                },
            )

        candidates = (
            direct(PUMP_MINT, PUMP_POOL),
            direct(
                "Pump222222222222222222222222222222222222222",
                "PumpPool222222222222222222222222222222222222",
            ),
        )

    persistent = SimpleNamespace(
        discovery_report={},
        front_door_report={},
        locator_report={},
        eligible_reserve=candidates,
        diagnostics={"permanent_availability": True},
        exhaustion_certificate=None,
        shortage_classification=None,
        discovery_rounds=1,
    )
    monkeypatch.setattr(
        eligible_supply,
        "run_persistent_eligible_token_supply",
        lambda *args, **kwargs: persistent,
    )
    monkeypatch.setattr(
        front_door,
        "lookup_graduated_candidate",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("post-selection registry lookup")
        ),
    )

    result = build_graduated_supply(
        ":memory:",
        cycle_seed="source-specific-seed",
        migration_transport=lambda _: {},
        permanent_availability=True,
        required_token_capacity=2,
    )
    assert result.ready is True
    assert [proof.mint for proof in result.graduated_supply] == [
        item["mint"] for item in result.two_candidate_selection["selected"]
    ]
    assert {
        proof.admission_authority.value for proof in result.graduated_supply
    } == {
        "MARKET_PRESENT_POOL" if route == "market" else "DIRECT_PUMP_PUMPSWAP"
    }

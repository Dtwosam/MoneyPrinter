"""Disposable proof for exact same-member market response binding."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace

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
    validate_memory_activation_set,
)
from printer_v1.discovery.permanent_discovery_availability import (
    SOLANA_INFRASTRUCTURE_MINTS,
)


NOW = "2026-08-05T22:52:58.929904+00:00"
EXPIRES = "2026-08-05T23:22:58.929904+00:00"
CAMPAIGN = "campaign-member-binding"
RUN = "run-member-binding"
CYCLE = "cycle-member-binding"

DEX_MINT = "6a4TCQoCFXXNK8jUtjCMPqvoaLGx1oNLrciBiRafpump"
DEX_POOL = "GzDaHcmSzGjiWSphXvCzxv1N9jCcTHy3bm4LUkeH3JGQ"
GECKO_MINT = "Gecko11111111111111111111111111111111111111"
GECKO_POOL = "GeckoPool11111111111111111111111111111111111"
PUMP_MINT = "Pump111111111111111111111111111111111111111"
PUMP_POOL = "PumpPool111111111111111111111111111111111111"
OTHER_MINT = "OtherMint1111111111111111111111111111111111"
OTHER_POOL = "OtherPool1111111111111111111111111111111111"
WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "exact-member-binding.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def _transport_key(source: str, kind: str, mint: str, ordinal: int = 1):
    return (
        "EXACT_MEMBER_BINDING",
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


def _dex_pair(
    *,
    mint: str,
    pool: str,
    chain: str = "solana",
    quote: str = WSOL,
) -> dict:
    """Normalized DexScreener pair member shape from dexscreener adapter."""
    return {
        "chain": chain,
        "pair_address": pool,
        "token_mint": mint,
        "candidate_mint": mint,
        "base_mint": mint,
        "quote_mint": quote,
        "dex_id": "pumpswap",
        "symbol": "TEST",
        "liquidity_usd": 21054.68,
        "observed_at": NOW,
    }


def _gecko_pair(
    *,
    mint: str,
    pool: str,
    chain: str = "solana",
    quote: str = WSOL,
) -> dict:
    """Normalized GeckoTerminal pair member shape after pool flatten/snapshot."""
    return {
        "chainId": chain,
        "pairAddress": pool,
        "baseToken": {"address": mint},
        "quoteToken": {"address": quote},
        "base_mint": mint,
        "quote_mint": quote,
        "pool_source": "geckoterminal",
        "captured_at": NOW,
    }


def _failed_run_dex_payload() -> dict:
    """Multi-member DexScreener shape with the failed-run mint at pairs[6]."""
    pairs = []
    for index in range(7):
        if index == 6:
            pairs.append(_dex_pair(mint=DEX_MINT, pool=DEX_POOL))
        else:
            pairs.append(
                _dex_pair(
                    mint=f"FillerMint{index:02d}11111111111111111111111111111",
                    pool=f"FillerPool{index:02d}11111111111111111111111111111",
                )
            )
    return {"pairs": pairs, "observed_at": NOW}


def _persist_payload(
    connection: sqlite3.Connection,
    *,
    role: EvidenceRole,
    source: str,
    kind: str,
    mint: str,
    pool: str,
    payload: dict,
    ordinal: int = 1,
):
    payload_json = json.dumps(payload, sort_keys=True)
    digest = hashlib.sha256(payload_json.encode()).hexdigest()
    request = connection.execute(
        """INSERT INTO printer_source_requests(
               source_name,request_kind,requested_at,request_key,
               source_status,data_quality_label
           ) VALUES (?,?,?,?,'COMPLETE','CLEAN_DATA')""",
        (source, kind, NOW, f"{mint}:{role.value}:{ordinal}"),
    )
    response = connection.execute(
        """INSERT INTO printer_source_responses(
               source_request_id,source_name,received_at,status_code,
               source_status,data_quality_label,response_hash,
               normalized_payload_json
           ) VALUES (?,?,?,200,'COMPLETE','CLEAN_DATA',?,?)""",
        (int(request.lastrowid), source, NOW, digest, payload_json),
    )
    key = _transport_key(source, kind, mint, ordinal=ordinal)
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
        logical_stage_id=f"{CAMPAIGN}|{RUN}|{CYCLE}|{role.value}|{ordinal}",
        transport_identity_count=1,
        transport_identity_keys=(key,),
    )
    return reference, entry


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


def _market(
    connection,
    *,
    ordinal: int,
    mint: str,
    pool: str,
    source: str,
    payload: dict | None = None,
):
    kind = (
        "dexscreener_fresh_profiles"
        if source == "dexscreener"
        else "geckoterminal_new_pool_discovery"
    )
    if payload is None:
        if source == "dexscreener":
            payload = {"pairs": [_dex_pair(mint=mint, pool=pool)], "observed_at": NOW}
        else:
            payload = {"pairs": [_gecko_pair(mint=mint, pool=pool)], "observed_at": NOW}
    ref, entry = _persist_payload(
        connection,
        role=EvidenceRole.MARKET_OBSERVATION,
        source=source,
        kind=kind,
        mint=mint,
        pool=pool,
        payload=payload,
        ordinal=ordinal,
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


def _pump(connection, *, ordinal: int, mint: str = PUMP_MINT, pool: str = PUMP_POOL):
    specs = (
        (EvidenceRole.ORIGIN_LINEAGE, "solana_rpc", "restored_pump_migration_transaction"),
        (EvidenceRole.PUMPSWAP_CONFIRMATION, "pumpswap", "pumpswap_signature_pool_resolution"),
        (EvidenceRole.MARKET_OBSERVATION, "dexscreener", "candidate_market_batch"),
    )
    refs = []
    entries = []
    for role, source, kind in specs:
        if role is EvidenceRole.MARKET_OBSERVATION:
            payload = {
                "pairs": [_dex_pair(mint=mint, pool=pool)],
                "observed_at": NOW,
            }
        else:
            payload = {
                "mint": mint,
                "base_mint": mint,
                "pool": pool,
                "pair_address": pool,
                "observed_at": NOW,
            }
        ref, entry = _persist_payload(
            connection,
            role=role,
            source=source,
            kind=kind,
            mint=mint,
            pool=pool,
            payload=payload,
            ordinal=ordinal,
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
    first = selected[0]
    second = selected[1] if len(selected) > 1 else selected[0]
    return FrozenMemoryActivationSet(
        activation_purpose=ActivationPurpose.MEMORY_OBSERVATION,
        readiness_id="ready-member-binding",
        selection_seed="seed-member-binding",
        selected=tuple(selected),
        alternates=(
            replace(first, slot_ordinal=3),
            replace(second, slot_ordinal=4),
        ),
        manifest_request_ids=tuple(entry.source_request_id for entry in entries),
        manifest_transport_identity_keys=tuple(
            key for entry in entries for key in entry.transport_identity_keys
        ),
        frozen_at=NOW,
        expires_at=EXPIRES,
        manifest_entries=entries,
    )


def _second_market(connection):
    return _market(
        connection,
        ordinal=2,
        source="geckoterminal",
        mint=GECKO_MINT,
        pool=GECKO_POOL,
    )


def test_dexscreener_exact_mint_pool_solana_same_pair_passes(db):
    first, first_entries = _market(
        db, ordinal=1, source="dexscreener", mint=DEX_MINT, pool=DEX_POOL
    )
    second, second_entries = _second_market(db)
    report = validate_memory_activation_set(
        db,
        _activation((first, second), (first_entries, second_entries)),
        now=NOW,
        expected_ownership=(CAMPAIGN, RUN, CYCLE),
    )
    assert report["reconciliation_status"] == "PASS"


def test_geckoterminal_exact_mint_pool_solana_same_member_passes(db):
    first, first_entries = _market(
        db, ordinal=1, source="geckoterminal", mint=GECKO_MINT, pool=GECKO_POOL
    )
    second, second_entries = _market(
        db, ordinal=2, source="dexscreener", mint=DEX_MINT, pool=DEX_POOL
    )
    report = validate_memory_activation_set(
        db,
        _activation((first, second), (first_entries, second_entries)),
        now=NOW,
        expected_ownership=(CAMPAIGN, RUN, CYCLE),
    )
    assert report["reconciliation_status"] == "PASS"


def test_mint_and_pool_split_across_members_fails(db):
    payload = {
        "pairs": [
            _dex_pair(mint=DEX_MINT, pool=OTHER_POOL),
            _dex_pair(mint=OTHER_MINT, pool=DEX_POOL),
        ],
        "observed_at": NOW,
    }
    first, first_entries = _market(
        db,
        ordinal=1,
        source="dexscreener",
        mint=DEX_MINT,
        pool=DEX_POOL,
        payload=payload,
    )
    second, second_entries = _second_market(db)
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            _activation((first, second), (first_entries, second_entries)),
            now=NOW,
        )
    assert exc.value.code == "MARKET_RESPONSE_NO_EXACT_MEMBER_MATCH"


def test_mint_pool_together_solana_only_on_other_member_fails(db):
    payload = {
        "pairs": [
            {
                **_dex_pair(mint=DEX_MINT, pool=DEX_POOL, chain="ethereum"),
                "chain": "ethereum",
            },
            _dex_pair(mint=OTHER_MINT, pool=OTHER_POOL, chain="solana"),
        ],
        "observed_at": NOW,
    }
    first, first_entries = _market(
        db,
        ordinal=1,
        source="dexscreener",
        mint=DEX_MINT,
        pool=DEX_POOL,
        payload=payload,
    )
    second, second_entries = _second_market(db)
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            _activation((first, second), (first_entries, second_entries)),
            now=NOW,
        )
    assert exc.value.code == "MARKET_ADMISSION_SOLANA_CONFIRMATION_MISSING"


def test_target_mint_only_as_quote_asset_fails(db):
    payload = {
        "pairs": [
            {
                "chain": "solana",
                "pair_address": DEX_POOL,
                "token_mint": OTHER_MINT,
                "candidate_mint": OTHER_MINT,
                "base_mint": OTHER_MINT,
                "quote_mint": DEX_MINT,
                "observed_at": NOW,
            }
        ],
        "observed_at": NOW,
    }
    first, first_entries = _market(
        db,
        ordinal=1,
        source="dexscreener",
        mint=DEX_MINT,
        pool=DEX_POOL,
        payload=payload,
    )
    second, second_entries = _second_market(db)
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            _activation((first, second), (first_entries, second_entries)),
            now=NOW,
        )
    assert exc.value.code == "MARKET_RESPONSE_TARGET_IS_QUOTE_ONLY"


def test_conflicting_duplicate_exact_matches_fail_closed(db):
    payload = {
        "pairs": [
            _dex_pair(mint=DEX_MINT, pool=DEX_POOL),
            _dex_pair(mint=DEX_MINT, pool=DEX_POOL),
        ],
        "observed_at": NOW,
    }
    first, first_entries = _market(
        db,
        ordinal=1,
        source="dexscreener",
        mint=DEX_MINT,
        pool=DEX_POOL,
        payload=payload,
    )
    second, second_entries = _second_market(db)
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            _activation((first, second), (first_entries, second_entries)),
            now=NOW,
        )
    assert exc.value.code == "MARKET_RESPONSE_CONFLICTING_MEMBER_MATCHES"


def test_missing_or_unsupported_member_shape_fails_closed(db):
    first, first_entries = _market(
        db,
        ordinal=1,
        source="dexscreener",
        mint=DEX_MINT,
        pool=DEX_POOL,
        payload={"schemaVersion": "1.0.0", "status": "ok", "observed_at": NOW},
    )
    second, second_entries = _second_market(db)
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            _activation((first, second), (first_entries, second_entries)),
            now=NOW,
        )
    assert exc.value.code == "MARKET_RESPONSE_UNSUPPORTED_SHAPE"


def test_failed_run_shaped_dexscreener_candidate_passes(db):
    first, first_entries = _market(
        db,
        ordinal=1,
        source="dexscreener",
        mint=DEX_MINT,
        pool=DEX_POOL,
        payload=_failed_run_dex_payload(),
    )
    second, second_entries = _second_market(db)
    report = validate_memory_activation_set(
        db,
        _activation((first, second), (first_entries, second_entries)),
        now=NOW,
        expected_ownership=(CAMPAIGN, RUN, CYCLE),
    )
    assert report["reconciliation_status"] == "PASS"


def test_valid_direct_pump_candidate_remains_unchanged(db):
    first, first_entries = _pump(db, ordinal=1)
    second, second_entries = _pump(
        db,
        ordinal=2,
        mint="Pump222222222222222222222222222222222222222",
        pool="PumpPool222222222222222222222222222222222222",
    )
    report = validate_memory_activation_set(
        db,
        _activation((first, second), (first_entries, second_entries)),
        now=NOW,
        expected_ownership=(CAMPAIGN, RUN, CYCLE),
    )
    assert report["reconciliation_status"] == "PASS"
    assert first.admission_authority is AdmissionAuthority.DIRECT_PUMP_PUMPSWAP
    assert first.claims_pump_origin is True
    assert first.claims_pumpswap_graduation is True


@pytest.mark.parametrize("composition", ("market", "pump", "mixed"))
def test_market_market_pump_pump_and_mixed_activation_still_pass(db, composition):
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


@pytest.mark.parametrize("infra_mint", (WSOL, USDC, USDT))
def test_infrastructure_mints_excluded(db, infra_mint):
    assert infra_mint in SOLANA_INFRASTRUCTURE_MINTS
    first, first_entries = _market(
        db, ordinal=1, source="dexscreener", mint=infra_mint, pool=DEX_POOL
    )
    second, second_entries = _second_market(db)
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            _activation((first, second), (first_entries, second_entries)),
            now=NOW,
        )
    assert exc.value.code == "INFRASTRUCTURE_MINT_EXCLUDED"


def test_no_registry_lookup_or_registry_row_creation(db):
    first, first_entries = _market(
        db, ordinal=1, source="dexscreener", mint=DEX_MINT, pool=DEX_POOL
    )
    second, second_entries = _second_market(db)
    before = db.execute(
        "SELECT COUNT(*) FROM printer_pumpswap_graduated_candidate_registry"
    ).fetchone()[0]
    validate_memory_activation_set(
        db,
        _activation((first, second), (first_entries, second_entries)),
        now=NOW,
    )
    after = db.execute(
        "SELECT COUNT(*) FROM printer_pumpswap_graduated_candidate_registry"
    ).fetchone()[0]
    assert before == 0
    assert after == 0


def test_no_source_rows_created_during_retained_activation(db):
    first, first_entries = _market(
        db, ordinal=1, source="dexscreener", mint=DEX_MINT, pool=DEX_POOL
    )
    second, second_entries = _second_market(db)
    tables = (
        "printer_source_requests",
        "printer_source_responses",
        "printer_source_failures",
    )
    before = tuple(
        db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables
    )
    validate_memory_activation_set(
        db,
        _activation((first, second), (first_entries, second_entries)),
        now=NOW,
    )
    after = tuple(
        db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables
    )
    assert after == before


def test_transport_response_hash_ownership_and_freshness_remain_fail_closed(db):
    first, first_entries = _market(
        db, ordinal=1, source="dexscreener", mint=DEX_MINT, pool=DEX_POOL
    )
    second, second_entries = _second_market(db)

    market_ref = first.retained_evidence_references[0]
    no_transport = replace(market_ref, transport_identity_keys=())
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            _activation(
                (
                    replace(first, retained_evidence_references=(no_transport,)),
                    second,
                ),
                (first_entries, second_entries),
            ),
            now=NOW,
        )
    assert exc.value.code == "RETAINED_REQUEST_TRANSPORT_IDENTITY_MISSING"

    bad_hash = replace(
        first,
        retained_evidence_references=(
            replace(market_ref, raw_payload_hash="0" * 64),
        ),
    )
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            _activation((bad_hash, second), (first_entries, second_entries)),
            now=NOW,
        )
    assert exc.value.code == "RETAINED_RESPONSE_CONTRACT_MISMATCH"

    wrong_owner = replace(
        first,
        retained_evidence_references=(
            replace(market_ref, campaign_id="other-campaign"),
        ),
    )
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            _activation((wrong_owner, second), (first_entries, second_entries)),
            now=NOW,
            expected_ownership=(CAMPAIGN, RUN, CYCLE),
        )
    assert exc.value.code == "RETAINED_OWNERSHIP_MISMATCH"

    stale = replace(first, evidence_expires_at="2026-08-05T22:00:00+00:00")
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            _activation((stale, second), (first_entries, second_entries)),
            now=NOW,
        )
    assert exc.value.code == "CANDIDATE_EVIDENCE_EXPIRED"

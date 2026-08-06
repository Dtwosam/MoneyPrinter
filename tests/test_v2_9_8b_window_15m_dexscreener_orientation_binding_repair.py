"""Disposable proof for DexScreener quote-side orientation binding repair."""

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
CAMPAIGN = "campaign-orientation-binding"
RUN = "run-orientation-binding"
CYCLE = "cycle-orientation-binding"

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
    path = tmp_path / "orientation-binding.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def _transport_key(source: str, kind: str, mint: str, ordinal: int = 1):
    return (
        "ORIENTATION_BINDING",
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
    candidate_mint: str | None = None,
    orientation_status: str | None = "PASS",
    orientation_reason: str | None = None,
    include_candidate: bool = True,
    base_mint: str | None = None,
    token_mint: str | None = None,
) -> dict:
    """Normalized DexScreener pair with optional orientation metadata."""
    explicit_base = base_mint if base_mint is not None else mint
    explicit_token = token_mint if token_mint is not None else explicit_base
    cand = candidate_mint if candidate_mint is not None else explicit_base
    pair: dict = {
        "chain": chain,
        "pair_address": pool,
        "token_mint": explicit_token,
        "base_mint": explicit_base,
        "quote_mint": quote,
        "dex_id": "pumpswap",
        "symbol": "TEST",
        "liquidity_usd": 21054.68,
        "observed_at": NOW,
    }
    if include_candidate:
        pair["candidate_mint"] = cand
    if orientation_status is not None:
        pair["candidate_pair_orientation_status"] = orientation_status
    if orientation_reason is not None:
        pair["candidate_pair_orientation_reason"] = orientation_reason
    elif orientation_status == "PASS" and include_candidate:
        pair["candidate_pair_orientation_reason"] = None
    elif orientation_status == "FAIL":
        pair["candidate_pair_orientation_reason"] = "BASE_QUOTE_ORIENTATION_MISMATCH"
    return pair


def _gecko_pair(
    *,
    mint: str,
    pool: str,
    chain: str = "solana",
    quote: str = WSOL,
) -> dict:
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
        readiness_id="ready-orientation-binding",
        selection_seed="seed-orientation-binding",
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


def _quote_side_orientation_payload(
    *,
    orientation_status: str = "FAIL",
    orientation_reason: str | None = "BASE_QUOTE_ORIENTATION_MISMATCH",
) -> dict:
    """DexScreener loophole shape: target only on quote, candidate_mint=target."""
    return {
        "pairs": [
            {
                "chain": "solana",
                "pair_address": DEX_POOL,
                "token_mint": OTHER_MINT,
                "base_mint": OTHER_MINT,
                "quote_mint": DEX_MINT,
                "candidate_mint": DEX_MINT,
                "candidate_pair_orientation_status": orientation_status,
                "candidate_pair_orientation_reason": orientation_reason,
                "observed_at": NOW,
            }
        ],
        "observed_at": NOW,
    }


def test_quote_side_candidate_with_orientation_fail_is_quote_only(db):
    first, first_entries = _market(
        db,
        ordinal=1,
        source="dexscreener",
        mint=DEX_MINT,
        pool=DEX_POOL,
        payload=_quote_side_orientation_payload(orientation_status="FAIL"),
    )
    second, second_entries = _second_market(db)
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            _activation((first, second), (first_entries, second_entries)),
            now=NOW,
        )
    assert exc.value.code == "MARKET_RESPONSE_TARGET_IS_QUOTE_ONLY"


def test_quote_side_with_base_quote_orientation_mismatch_reason_is_quote_only(db):
    first, first_entries = _market(
        db,
        ordinal=1,
        source="dexscreener",
        mint=DEX_MINT,
        pool=DEX_POOL,
        payload=_quote_side_orientation_payload(
            orientation_status="FAIL",
            orientation_reason="BASE_QUOTE_ORIENTATION_MISMATCH",
        ),
    )
    second, second_entries = _second_market(db)
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            _activation((first, second), (first_entries, second_entries)),
            now=NOW,
        )
    assert exc.value.code == "MARKET_RESPONSE_TARGET_IS_QUOTE_ONLY"


def test_valid_base_oriented_member_with_pass_orientation_passes(db):
    first, first_entries = _market(
        db,
        ordinal=1,
        source="dexscreener",
        mint=DEX_MINT,
        pool=DEX_POOL,
        payload={
            "pairs": [
                _dex_pair(
                    mint=DEX_MINT,
                    pool=DEX_POOL,
                    candidate_mint=DEX_MINT,
                    orientation_status="PASS",
                )
            ],
            "observed_at": NOW,
        },
    )
    second, second_entries = _second_market(db)
    report = validate_memory_activation_set(
        db,
        _activation((first, second), (first_entries, second_entries)),
        now=NOW,
        expected_ownership=(CAMPAIGN, RUN, CYCLE),
    )
    assert report["reconciliation_status"] == "PASS"


def test_pass_candidate_disagreeing_with_explicit_base_is_orientation_conflict(db):
    first, first_entries = _market(
        db,
        ordinal=1,
        source="dexscreener",
        mint=DEX_MINT,
        pool=DEX_POOL,
        payload={
            "pairs": [
                {
                    "chain": "solana",
                    "pair_address": DEX_POOL,
                    "token_mint": OTHER_MINT,
                    "base_mint": OTHER_MINT,
                    "quote_mint": WSOL,
                    "candidate_mint": DEX_MINT,
                    "candidate_pair_orientation_status": "PASS",
                    "candidate_pair_orientation_reason": None,
                    "observed_at": NOW,
                }
            ],
            "observed_at": NOW,
        },
    )
    second, second_entries = _second_market(db)
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            _activation((first, second), (first_entries, second_entries)),
            now=NOW,
        )
    assert exc.value.code == "MARKET_RESPONSE_ORIENTATION_CONFLICT"


def test_disagreeing_explicit_base_fields_fail_closed(db):
    first, first_entries = _market(
        db,
        ordinal=1,
        source="dexscreener",
        mint=DEX_MINT,
        pool=DEX_POOL,
        payload={
            "pairs": [
                {
                    "chain": "solana",
                    "pair_address": DEX_POOL,
                    "token_mint": OTHER_MINT,
                    "base_mint": DEX_MINT,
                    "quote_mint": WSOL,
                    "candidate_mint": DEX_MINT,
                    "candidate_pair_orientation_status": "PASS",
                    "observed_at": NOW,
                }
            ],
            "observed_at": NOW,
        },
    )
    second, second_entries = _second_market(db)
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            _activation((first, second), (first_entries, second_entries)),
            now=NOW,
        )
    assert exc.value.code == "MARKET_RESPONSE_ORIENTATION_CONFLICT"


def test_target_in_both_base_and_quote_fails_closed(db):
    first, first_entries = _market(
        db,
        ordinal=1,
        source="dexscreener",
        mint=DEX_MINT,
        pool=DEX_POOL,
        payload={
            "pairs": [
                {
                    "chain": "solana",
                    "pair_address": DEX_POOL,
                    "token_mint": DEX_MINT,
                    "base_mint": DEX_MINT,
                    "quote_mint": DEX_MINT,
                    "candidate_mint": DEX_MINT,
                    "candidate_pair_orientation_status": "PASS",
                    "observed_at": NOW,
                }
            ],
            "observed_at": NOW,
        },
    )
    second, second_entries = _second_market(db)
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            db,
            _activation((first, second), (first_entries, second_entries)),
            now=NOW,
        )
    assert exc.value.code == "MARKET_RESPONSE_ORIENTATION_CONFLICT"


def test_explicit_base_without_candidate_mint_still_passes(db):
    first, first_entries = _market(
        db,
        ordinal=1,
        source="dexscreener",
        mint=DEX_MINT,
        pool=DEX_POOL,
        payload={
            "pairs": [
                _dex_pair(
                    mint=DEX_MINT,
                    pool=DEX_POOL,
                    include_candidate=False,
                    orientation_status=None,
                )
            ],
            "observed_at": NOW,
        },
    )
    second, second_entries = _second_market(db)
    report = validate_memory_activation_set(
        db,
        _activation((first, second), (first_entries, second_entries)),
        now=NOW,
        expected_ownership=(CAMPAIGN, RUN, CYCLE),
    )
    assert report["reconciliation_status"] == "PASS"


def test_failed_run_shaped_dexscreener_candidate_still_passes(db):
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


def test_valid_geckoterminal_member_remains_unchanged(db):
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


def test_cross_member_solana_missing_duplicate_and_unsupported_still_fail(db):
    cases = (
        (
            {
                "pairs": [
                    _dex_pair(mint=DEX_MINT, pool=OTHER_POOL),
                    _dex_pair(mint=OTHER_MINT, pool=DEX_POOL),
                ],
                "observed_at": NOW,
            },
            "MARKET_RESPONSE_NO_EXACT_MEMBER_MATCH",
        ),
        (
            {
                "pairs": [
                    _dex_pair(mint=DEX_MINT, pool=DEX_POOL, chain="ethereum"),
                    _dex_pair(mint=OTHER_MINT, pool=OTHER_POOL, chain="solana"),
                ],
                "observed_at": NOW,
            },
            "MARKET_ADMISSION_SOLANA_CONFIRMATION_MISSING",
        ),
        (
            {
                "pairs": [
                    _dex_pair(mint=DEX_MINT, pool=DEX_POOL),
                    _dex_pair(mint=DEX_MINT, pool=DEX_POOL),
                ],
                "observed_at": NOW,
            },
            "MARKET_RESPONSE_CONFLICTING_MEMBER_MATCHES",
        ),
        (
            {"schemaVersion": "1.0.0", "status": "ok", "observed_at": NOW},
            "MARKET_RESPONSE_UNSUPPORTED_SHAPE",
        ),
    )
    for payload, expected_code in cases:
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
        assert exc.value.code == expected_code


@pytest.mark.parametrize("infra_mint", (WSOL, USDC, USDT))
def test_infrastructure_mints_remain_excluded(db, infra_mint):
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


def test_no_registry_or_source_rows_created_during_activation(db):
    first, first_entries = _market(
        db, ordinal=1, source="dexscreener", mint=DEX_MINT, pool=DEX_POOL
    )
    second, second_entries = _second_market(db)
    tables = (
        "printer_source_requests",
        "printer_source_responses",
        "printer_source_failures",
    )
    before_source = tuple(
        db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables
    )
    before_registry = db.execute(
        "SELECT COUNT(*) FROM printer_pumpswap_graduated_candidate_registry"
    ).fetchone()[0]
    validate_memory_activation_set(
        db,
        _activation((first, second), (first_entries, second_entries)),
        now=NOW,
    )
    after_source = tuple(
        db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables
    )
    after_registry = db.execute(
        "SELECT COUNT(*) FROM printer_pumpswap_graduated_candidate_registry"
    ).fetchone()[0]
    assert after_source == before_source
    assert before_registry == 0
    assert after_registry == 0

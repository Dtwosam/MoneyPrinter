"""V2-9.8B candidate-acquisition foundation and frozen mechanics proof."""

from __future__ import annotations

import base64
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile

import pytest

from printer_v1.db.migrate import apply_migrations, canonical_migration_names
from printer_v1.discovery.candidate_acquisition import (
    CandidateAcquisitionError,
    PUMP_IDL_SHA256,
    PUMPSWAP_IDL_SHA256,
    build_acquisition_plan,
    legacy_two_token_runtime_projection,
    replay_candidate_acquisition_report,
    run_candidate_acquisition,
)
from printer_v1.sources.birdeye import normalize_birdeye_new_listing
from printer_v1.sources.governor import can_request_source
from printer_v1.sources.pump_contracts import (
    ASSOCIATED_TOKEN_PROGRAM_ID,
    CANONICAL_POOL_INDEX,
    METADATA_PROGRAM_ID,
    PUMP_CREATE_DISCRIMINATOR,
    PUMP_MIGRATE_DISCRIMINATOR,
    PUMPSWAP_POOL_DISCRIMINATOR,
    RENT_SYSVAR_ID,
    SYSTEM_PROGRAM_ID,
    TOKEN_2022_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    WSOL_MINT,
    _b58encode,
    decode_pumpswap_pool_account,
    decode_supported_pump_creation_instruction,
    derive_canonical_pumpswap_pool,
    derive_program_address,
    verify_pinned_pump_migration,
)
from printer_v1.sources.pumpfun_direct import PUMP_PROGRAM_ID
from printer_v1.sources.pumpswap import PUMPSWAP_AMM_PROGRAM_ID, _b58decode


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads(
    (ROOT / "tests/fixtures/candidate_acquisition_capacity_v1.json").read_text()
)
TOKEN_PROGRAM = TOKEN_PROGRAM_ID
PROGRAM = "675kPX9MHTjS2zt1qfr1NYHuzeuycG6t58pk8Rai7Lb"
NOW = FIXTURE["frozen_at"]
EXPIRES = FIXTURE["expires_at"]
REQUIRED_N = (2, 3, 4, 5, 6, 7, 10, 16)


def _db() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temp = tempfile.TemporaryDirectory()
    path = Path(temp.name) / "candidate.sqlite3"
    apply_migrations(path)
    return temp, path


def _plan(n: int, execution: str) -> dict:
    return build_acquisition_plan(
        selection_capacity=n,
        execution_id=execution,
        selection_seed="frozen-uniform-seed-v1",
        window_start="2026-07-29T11:00:00+00:00",
        window_end=NOW,
        cutoff_at=NOW,
        finalized_cutoff_slot=420_000_000,
        git_provenance="219ad8125a75f52686bfbf5953be0fa4cdca4712",
        allowed_sources=("dexscreener", "geckoterminal", "solana_rpc"),
        source_budgets={
            "dexscreener": {"candidate_nomination": 2},
            "geckoterminal": {"candidate_nomination": 2},
            "solana_rpc": {"pumpfun_migration_transaction": 2},
        },
    )


def _facts(**changes) -> dict:
    facts = {
        "mint_status": "PASS",
        "token_program_status": "PASS",
        "tracking_status": "PASS",
        "pool_status": "PASS",
        "market_status": "PASS",
        "age_status": "PASS",
        "holder_status": "PASS",
        "safety_status": "PASS",
        "liquidity_status": "PASS",
        "tradeability_status": "PASS",
    }
    facts.update(changes)
    return facts


def _observations(count: int, *, reverse: bool = False) -> list[dict]:
    rows: list[dict] = []
    for ordinal, (mint, pool, _unused_program) in enumerate(FIXTURE["candidates"][:count], 1):
        source = "dexscreener" if ordinal % 2 else "geckoterminal"
        rows.append(
            {
                "round_ordinal": 1 if source == "dexscreener" else 2,
                "round_mode": "FROZEN_OFFLINE",
                "source_name": source,
                "request_kind": "candidate_nomination",
                "source_status": "COMPLETE",
                "observed_at": NOW,
                "expires_at": EXPIRES,
                "mint": mint,
                "pool": pool,
                "pool_program_id": PROGRAM,
                "base_mint": mint,
                "quote_mint": WSOL_MINT,
                "token_program_id": TOKEN_PROGRAM,
                "venue_label": "FROZEN_SUPPORTED_VENUE",
                "lineage_claim": "UNKNOWN_ORIGIN" if ordinal % 3 else "NON_PUMP_POOL_CONFIRMED",
                "facts": _facts(),
            }
        )
    return list(reversed(rows)) if reverse else rows


def _count(path: Path, table: str) -> int:
    with sqlite3.connect(path) as connection:
        return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


@pytest.mark.parametrize("n", REQUIRED_N)
def test_frozen_capacity_matrix_exact_n_and_runtime_lock(n: int) -> None:
    temp, path = _db()
    try:
        report = run_candidate_acquisition(
            path, plan=_plan(n, f"matrix-{n}"), observations=_observations(2 * n)
        )
        assert report["verdict"] == "EXACT_N_MANIFEST_READY"
        assert report["selected_count"] == n
        assert report["capacity"]["candidate_acquisition_capacity"] == 2 * n
        assert report["active_capacity_lock"] == 2
        assert report["runtime_handoff_count"] == 0
        assert set(report["forbidden_capability_deltas"].values()) == {0}
        assert {
            "printer_memory_retrieval_queries", "printer_memory_retrieval_matches",
            "printer_paper_decisions", "printer_paper_positions",
            "printer_paper_trade_events", "printer_paper_trade_audits",
            "printer_paper_audit_reports",
        } <= set(report["forbidden_capability_deltas"])
        if n == 2:
            projected = legacy_two_token_runtime_projection(path, report["manifest_id"])
            assert len(projected) == 2
        else:
            with pytest.raises(CandidateAcquisitionError, match="LEGACY_RUNTIME_REQUIRES_EXACTLY_TWO"):
                legacy_two_token_runtime_projection(path, report["manifest_id"])
    finally:
        temp.cleanup()


@pytest.mark.parametrize("n", REQUIRED_N)
def test_frozen_capacity_matrix_all_or_none_shortage(n: int) -> None:
    temp, path = _db()
    try:
        report = run_candidate_acquisition(
            path, plan=_plan(n, f"short-{n}"), observations=_observations(n - 1)
        )
        assert report["exact_n_selection_result"] == "ALL_OR_NONE_FAILURE"
        assert report["selected_count"] == 0
        assert report["manifest_id"] is None
        assert _count(path, "printer_candidate_manifests") == 0
    finally:
        temp.cleanup()


def test_input_order_overlap_and_replay_are_deterministic_and_idempotent() -> None:
    temp_a, path_a = _db()
    temp_b, path_b = _db()
    try:
        plan = _plan(7, "order-proof")
        forward = _observations(14)
        overlap = deepcopy(forward[0])
        overlap.update(
            round_ordinal=3,
            source_name="geckoterminal",
            request_kind="candidate_nomination",
        )
        forward.append(overlap)
        reverse = list(reversed(forward))
        first = run_candidate_acquisition(path_a, plan=plan, observations=forward)
        second = run_candidate_acquisition(path_b, plan=plan, observations=reverse)
        assert first["manifest_hash"] == second["manifest_hash"]
        assert first["ordered_item_hashes"] == second["ordered_item_hashes"]
        assert first["source_contribution"]["cross_source_overlap_count"] == 1
        assert _count(path_a, "printer_candidate_identities") == 14
        before = path_a.read_bytes()
        assert run_candidate_acquisition(path_a, plan=plan, observations=forward) == first
        assert replay_candidate_acquisition_report(path_a, "order-proof") == first
        assert path_a.read_bytes() == before
    finally:
        temp_a.cleanup(); temp_b.cleanup()


def test_source_outage_is_provider_failure_not_market_shortage() -> None:
    temp, path = _db()
    try:
        observations = _observations(3)
        observations.append(
            {
                "round_ordinal": 3,
                "source_name": "geckoterminal",
                "request_kind": "candidate_nomination",
                "source_status": "PROVIDER_FAILURE",
                "failure_reason": "frozen_outage",
                "observed_at": NOW,
                "expires_at": EXPIRES,
                "facts": {},
            }
        )
        report = run_candidate_acquisition(
            path, plan=_plan(4, "outage-proof"), observations=observations
        )
        assert report["failure_family"] == "SOURCE_PROVIDER_FAILURE"
        assert report["failure_family"] != "INSUFFICIENT_ELIGIBLE_POOL"
    finally:
        temp.cleanup()


def test_budget_exhaustion_and_cross_mint_pool_conflict_are_structured() -> None:
    temp, path = _db()
    try:
        observations = _observations(1)
        observations.append(
            {
                "round_ordinal": 3,
                "source_name": "solana_rpc",
                "request_kind": "pumpfun_migration_transaction",
                "source_status": "BUDGET_EXHAUSTED",
                "failure_reason": "frozen_budget_ceiling",
                "observed_at": NOW,
                "expires_at": EXPIRES,
                "facts": {},
            }
        )
        report = run_candidate_acquisition(
            path, plan=_plan(2, "budget-proof"), observations=observations
        )
        assert report["failure_family"] == "BUDGET_EXHAUSTION"
    finally:
        temp.cleanup()

    temp, path = _db()
    try:
        observations = _observations(2)
        observations[1]["pool"] = observations[0]["pool"]
        report = run_candidate_acquisition(
            path, plan=_plan(2, "identity-proof"), observations=observations
        )
        assert report["failure_family"] == "IDENTITY_MERGE_FAILURE"
        assert report["exclusions_by_funnel_stage"] == {"IDENTITY_AVAILABLE": 2}
        assert _count(path, "printer_candidate_identities") == 2
    finally:
        temp.cleanup()


def test_stale_unsupported_conflicting_and_pump_lineage_fail_closed() -> None:
    cases = (
        ("stale", {"expires_at": NOW}, "MARKET_FRESH"),
        ("unsupported", {"facts": _facts(tradeability_status="UNSUPPORTED")}, "ROUTE_TRADEABILITY_VALID"),
        ("conflicting", {"lineage_claim": "CONFLICTING_LINEAGE"}, "LINEAGE_VALID"),
        ("pump-incomplete", {"lineage_claim": "PUMP_GRADUATION_CONFIRMED"}, "LINEAGE_VALID"),
    )
    for label, update, expected_stage in cases:
        temp, path = _db()
        try:
            observations = _observations(2)
            observations[0].update(update)
            report = run_candidate_acquisition(
                path, plan=_plan(2, f"reject-{label}"), observations=observations
            )
            assert report["selected_count"] == 0
            assert expected_stage in report["exclusions_by_funnel_stage"]
        finally:
            temp.cleanup()


def test_verified_pump_and_nonpump_unknown_can_coexist() -> None:
    temp, path = _db()
    try:
        observations = _observations(3)
        observations[0]["lineage_claim"] = "PUMP_GRADUATION_CONFIRMED"
        observations[0]["facts"].update(
            pump_origin_signature="origin-signature",
            pump_origin_contract_hash=PUMP_IDL_SHA256,
            pump_migration_signature="migration-signature",
            pump_migration_contract_hash=PUMP_IDL_SHA256,
            pumpswap_account_hash="a" * 64,
            pumpswap_contract_hash=PUMPSWAP_IDL_SHA256,
            pumpswap_index=0,
        )
        report = run_candidate_acquisition(
            path, plan=_plan(3, "mixed-lineage"), observations=observations
        )
        assert report["selected_count"] == 3
        with sqlite3.connect(path) as connection:
            states = {row[0] for row in connection.execute(
                "SELECT lineage_state FROM printer_candidate_identities"
            )}
        assert states == {
            "PUMP_GRADUATION_CONFIRMED", "NON_PUMP_POOL_CONFIRMED", "UNKNOWN_ORIGIN"
        }
    finally:
        temp.cleanup()


def test_cursor_cannot_advance_past_gap_and_contiguous_range_persists() -> None:
    base = _observations(2)
    cursor = {
        "indexed_address": PUMP_PROGRAM_ID,
        "contract_pin": PUMP_IDL_SHA256,
        "decoder_version": "PINNED_V1",
        "direction": "BACKWARD",
        "start_slot": 101,
        "end_slot": 100,
        "continuity_state": "GAPPED",
        "cursor_advanced": True,
        "unresolved_reason": "missing_page",
    }
    base[0].update(round_mode="BACKFILL", cursor_range=cursor)
    with pytest.raises(CandidateAcquisitionError, match="CURSOR_ADVANCED_PAST_UNRESOLVED_EVIDENCE"):
        run_candidate_acquisition("ignored.sqlite3", plan=_plan(2, "cursor-gap"), observations=base)
    temp, path = _db()
    try:
        base[0]["cursor_range"].update(continuity_state="CONTIGUOUS", cursor_advanced=True)
        report = run_candidate_acquisition(
            path, plan=_plan(2, "cursor-pass"), observations=base
        )
        assert report["cursor_continuity"] == {"CONTIGUOUS": 1}
        assert _count(path, "printer_candidate_cursor_ranges") == 1
    finally:
        temp.cleanup()


def test_certificate_immutability_and_fresh_requalification_version_reserve() -> None:
    temp, path = _db()
    try:
        first = run_candidate_acquisition(
            path, plan=_plan(2, "requal-first"), observations=_observations(2)
        )
        with sqlite3.connect(path) as connection:
            old_hashes = {
                row[0] for row in connection.execute(
                    "SELECT certificate_hash FROM printer_candidate_certificates"
                )
            }
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                connection.execute(
                    "UPDATE printer_candidate_certificates SET admission_reason='changed'"
                )
        later_observations = _observations(2)
        for item in later_observations:
            item["observed_at"] = "2026-07-29T15:00:00+00:00"
            item["expires_at"] = "2026-07-29T17:00:00+00:00"
        later_plan = build_acquisition_plan(
            selection_capacity=2,
            execution_id="requal-second",
            selection_seed="frozen-uniform-seed-v1",
            window_start="2026-07-29T14:00:00+00:00",
            window_end="2026-07-29T15:00:00+00:00",
            cutoff_at="2026-07-29T15:00:00+00:00",
            finalized_cutoff_slot=420_000_100,
            git_provenance="219ad8125a75f52686bfbf5953be0fa4cdca4712",
            allowed_sources=("dexscreener", "geckoterminal", "solana_rpc"),
            source_budgets={
                "dexscreener": {"candidate_nomination": 2},
                "geckoterminal": {"candidate_nomination": 2},
                "solana_rpc": {"pumpfun_migration_transaction": 2},
            },
        )
        second = run_candidate_acquisition(
            path, plan=later_plan, observations=later_observations
        )
        assert first["manifest_hash"] != second["manifest_hash"]
        with sqlite3.connect(path) as connection:
            versions = {
                int(row[0]) for row in connection.execute(
                    "SELECT reserve_version FROM printer_candidate_reserve"
                )
            }
            all_hashes = {
                row[0] for row in connection.execute(
                    "SELECT certificate_hash FROM printer_candidate_certificates"
                )
            }
        assert versions == {2}
        assert len(all_hashes) == 4
        assert old_hashes < all_hashes
    finally:
        temp.cleanup()


def test_migration_repair_registry_governor_and_birdeye_contract() -> None:
    assert canonical_migration_names()[-1] == "048_candidate_acquisition_foundation.sql"
    temp, path = _db()
    try:
        with sqlite3.connect(path) as connection:
            connection.execute(
                """INSERT INTO printer_discovery_exhaustion_certificates(
                certificate_id,required_eligible_capacity,eligible_reserve_count,
                shortage_classification,certificate_json,certificate_version,created_at
                ) VALUES ('cap-block',2,0,'TRACKING_STATE_CAPACITY_BLOCKED','{}','v1',?)""",
                (NOW,),
            )
            connection.commit()
        assert _count(path, "printer_discovery_exhaustion_certificates") == 1
    finally:
        temp.cleanup()
    for source, kind in (
        ("dexscreener", "candidate_nomination"),
        ("geckoterminal", "candidate_market_batch"),
        ("birdeye", "birdeye_new_listing_nomination"),
        ("solana_rpc", "pumpfun_migration_transaction"),
    ):
        assert can_request_source(source, kind, 0).allowed
    result = normalize_birdeye_new_listing(
        {"data": {"items": [{"address": FIXTURE["candidates"][0][0], "symbol": "MEME"}]}},
        observed_at=NOW,
    )
    assert result.normalized_payload["candidate_nomination_only"] is True
    assert result.normalized_payload["paid_fallback_allowed"] is False
    with pytest.raises(CandidateAcquisitionError, match="FOUNDATION_SOURCE_CONTRACT_PROHIBITED"):
        build_acquisition_plan(
            selection_capacity=2,
            execution_id="pumpportal-prohibited",
            selection_seed="seed",
            window_start="2026-07-29T11:00:00+00:00",
            window_end=NOW,
            cutoff_at=NOW,
            finalized_cutoff_slot=420_000_000,
            git_provenance="219ad8125a75f52686bfbf5953be0fa4cdca4712",
            allowed_sources=("dexscreener", "pumpportal"),
            source_budgets={},
        )


def _pool_account(creator: str, mint: str) -> tuple[str, dict]:
    pool, bump = derive_canonical_pumpswap_pool(creator=creator, base_mint=mint)
    lp_mint = derive_program_address(
        (b"pool_lp_mint", _b58decode(pool)), PUMPSWAP_AMM_PROGRAM_ID
    )[0]
    base_vault = derive_program_address(
        (_b58decode(pool), _b58decode(TOKEN_PROGRAM_ID), _b58decode(mint)),
        ASSOCIATED_TOKEN_PROGRAM_ID,
    )[0]
    quote_vault = derive_program_address(
        (_b58decode(pool), _b58decode(TOKEN_PROGRAM_ID), _b58decode(WSOL_MINT)),
        ASSOCIATED_TOKEN_PROGRAM_ID,
    )[0]
    pubkeys = [
        creator, mint, WSOL_MINT, lp_mint, base_vault, quote_vault,
    ]
    raw = (
        PUMPSWAP_POOL_DISCRIMINATOR
        + bytes([bump])
        + CANONICAL_POOL_INDEX.to_bytes(2, "little")
        + b"".join(_b58decode(value) for value in pubkeys)
        + (1_000_000).to_bytes(8, "little")
        + _b58decode(creator)
        + b"\0\0"
        + (0).to_bytes(16, "little", signed=True)
    )
    return pool, {
        "owner": PUMPSWAP_AMM_PROGRAM_ID,
        "data": [base64.b64encode(raw).decode(), "base64"],
    }


def _pinned_migration_fixture() -> tuple[dict, dict, str, str]:
    mint = FIXTURE["candidates"][0][0]
    creator = derive_program_address(
        (b"pool-authority", _b58decode(mint)), PUMP_PROGRAM_ID
    )[0]
    pool, account = _pool_account(creator, mint)
    decoded = decode_pumpswap_pool_account(account, pool_address=pool)
    keys = [FIXTURE["candidates"][i][0] for i in range(25)]
    keys[2] = mint
    keys[3] = derive_program_address(
        (b"bonding-curve", _b58decode(mint)), PUMP_PROGRAM_ID
    )[0]
    keys[6] = SYSTEM_PROGRAM_ID
    keys[7] = TOKEN_PROGRAM_ID
    keys[8] = PUMPSWAP_AMM_PROGRAM_ID
    keys[9] = pool
    keys[10] = creator
    keys[14] = WSOL_MINT
    keys[15] = decoded["lp_mint"]
    keys[17] = decoded["pool_base_token_account"]
    keys[18] = decoded["pool_quote_token_account"]
    keys[19] = TOKEN_2022_PROGRAM_ID
    keys[20] = ASSOCIATED_TOKEN_PROGRAM_ID
    keys[23] = PUMP_PROGRAM_ID
    keys[24] = RENT_SYSVAR_ID
    tx = {
        "version": 0,
        "slot": 420_000_000,
        "blockTime": 1_785_326_400,
        "transaction": {"message": {
            "accountKeys": keys,
            "instructions": [{
                "programIdIndex": 23,
                "accounts": list(range(25)),
                "data": _b58encode(PUMP_MIGRATE_DISCRIMINATOR),
            }],
        }},
        "meta": {"err": None, "loadedAddresses": {"writable": [], "readonly": []}},
    }
    return tx, {pool: account}, mint, pool


def test_pinned_pump_creation_migration_pool_and_contract_failures() -> None:
    tx, infos, mint, pool = _pinned_migration_fixture()
    verified = verify_pinned_pump_migration(tx, infos, expected_mint=mint, finalized=True)
    assert verified["verified"] is True
    assert verified["pool_address"] == pool
    assert decode_pumpswap_pool_account(infos[pool], pool_address=pool)["append_only_extension"] is True
    assert verify_pinned_pump_migration(tx, infos, expected_mint=mint, finalized=False)["verified"] is False
    wrong = deepcopy(tx)
    wrong["transaction"]["message"]["instructions"][0]["data"] = _b58encode(b"12345678")
    assert verify_pinned_pump_migration(wrong, infos, expected_mint=mint, finalized=True)["verified"] is False
    malformed = deepcopy(infos)
    encoded = base64.b64decode(malformed[pool]["data"][0])
    malformed[pool]["data"][0] = base64.b64encode(b"12345678" + encoded[8:]).decode()
    assert verify_pinned_pump_migration(tx, malformed, expected_mint=mint, finalized=True)["verified"] is False
    create_keys = [FIXTURE["candidates"][i][0] for i in range(14)]
    create_keys[0] = mint
    create_keys[1] = derive_program_address((b"mint-authority",), PUMP_PROGRAM_ID)[0]
    create_keys[2] = derive_program_address(
        (b"bonding-curve", _b58decode(mint)), PUMP_PROGRAM_ID
    )[0]
    create_keys[5] = METADATA_PROGRAM_ID
    create_keys[8] = SYSTEM_PROGRAM_ID
    create_keys[9] = TOKEN_PROGRAM_ID
    create_keys[10] = ASSOCIATED_TOKEN_PROGRAM_ID
    create_keys[11] = RENT_SYSVAR_ID
    create_keys[13] = PUMP_PROGRAM_ID
    creation = decode_supported_pump_creation_instruction(
        {"programIdIndex": 13, "accounts": list(range(14)), "data": _b58encode(PUMP_CREATE_DISCRIMINATOR)},
        create_keys,
    )
    assert creation["supported"] is True
    assert creation["variant"] == "create"

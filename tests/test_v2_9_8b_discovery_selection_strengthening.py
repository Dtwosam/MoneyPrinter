"""V2-9.8B discovery→selection strengthening — focused offline coverage.

No network, no live providers, no WINDOW_15M lifecycle, no financial surfaces.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.discovery.graduated_liquidity_front_door import (
    LIQUIDITY_EXACT_ABOVE_FLOOR,
    LIQUIDITY_EXACT_BELOW_FLOOR,
    LIQUIDITY_EXACT_PAIR_UNAVAILABLE_OR_MISMATCH,
    LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL,
    SELECTION_FLOOR_USD,
    enrich_pool_liquidity,
    run_graduated_liquidity_front_door,
)
from printer_v1.discovery.selection_authority import (
    SelectionCandidate,
    select_two_candidates,
)
from printer_v1.sources.dexscreener import (
    fixture_success_transport,
    normalize_dexscreener_fixture_result,
)
from printer_v1.sources.pumpswap_graduated_registry import (
    PERSISTED_GRADUATED_CHANNEL,
    record_graduated_candidate,
)


NOW = "2026-08-04T01:00:00+00:00"
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58(data: bytes) -> str:
    value = int.from_bytes(data, "big")
    out: list[str] = []
    while value:
        value, remainder = divmod(value, 58)
        out.append(ALPHABET[remainder])
    return "".join(reversed(out)) or "1"


def _spec(index: int) -> tuple[str, str, str]:
    mint = _b58(hashlib.sha256(f"str-mint-{index}".encode()).digest())
    pool = _b58(hashlib.sha256(f"str-pool-{index}".encode()).digest())
    signature = _b58(
        hashlib.sha256(f"str-sig-a-{index}".encode()).digest()
        + hashlib.sha256(f"str-sig-b-{index}".encode()).digest()
    )
    return mint, signature, pool


def _db(tmp_path: Path) -> str:
    path = tmp_path / "discovery-selection-strengthening.sqlite3"
    apply_migrations(path)
    return str(path)


def _seed(db: str, count: int) -> list[tuple[str, str, str]]:
    specs = [_spec(index) for index in range(count)]
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        for index, (mint, signature, pool) in enumerate(specs):
            record_graduated_candidate(
                connection,
                mint=mint,
                migration_signature=signature,
                pumpswap_pool=pool,
                graduation_block_time=1_784_841_493 + index,
                graduation_slot=1 + index,
                now=NOW,
                discovery_channel=PERSISTED_GRADUATED_CHANNEL,
            )
        connection.commit()
    finally:
        connection.close()
    return specs


def _pair(pool: str, mint: str, liquidity: float) -> dict:
    return {
        "schemaVersion": "1.0.0",
        "pairs": [
            {
                "chainId": "solana",
                "pairAddress": pool,
                "baseToken": {"address": mint, "symbol": "MEME", "name": "Meme"},
                "quoteToken": {
                    "address": "So11111111111111111111111111111111111111112",
                },
                "priceUsd": "0.10",
                "liquidity": {"usd": liquidity},
                "volume": {"m5": 1.0, "h1": 2.0, "h24": 3.0},
                "txns": {"m5": {"buys": 1, "sells": 1}},
            }
        ],
    }


@pytest.mark.parametrize(
    ("pairs_payload", "reason"),
    [
        ([], "source_returned_empty_pairs"),
        (None, "source_returned_null_pairs"),
    ],
)
def test_exact_pair_empty_or_null_is_lawful_no_match(pairs_payload, reason) -> None:
    result = normalize_dexscreener_fixture_result(
        {
            "pairs": pairs_payload,
            "schemaVersion": "1.0.0",
            "_source_status_code": 200,
            "transport_operations_used": 1,
            "response_bytes": 50,
            "normalized_rows": 0,
            "transport_operation_identities": (),
        },
        request_kind="pair_market_snapshot",
    )
    assert result.source_status == SourceStatus.PARTIAL
    assert result.data_quality_label == DataQualityLabel.ACCEPTABLE_PARTIAL_DATA
    assert result.failure_type is None
    payload = dict(result.normalized_payload)
    assert payload["no_matching_pairs"] is True
    assert payload["no_matching_pairs_reason"] == reason
    assert payload["pairs"] == []
    assert "liquidity_usd" not in payload or payload.get("liquidity_usd") is None


@pytest.mark.parametrize(
    "pairs_value",
    ["bad", {"x": 1}, 12, True],
)
def test_exact_pair_malformed_pairs_shapes_remain_failed(pairs_value) -> None:
    result = normalize_dexscreener_fixture_result(
        {
            "pairs": pairs_value,
            "schemaVersion": "1.0.0",
            "_source_status_code": 200,
            "transport_operations_used": 1,
            "response_bytes": 32,
            "normalized_rows": 0,
            "transport_operation_identities": (),
        },
        request_kind="pair_market_snapshot",
    )
    assert result.source_status == SourceStatus.FAILED
    assert result.failure_type == "dexscreener_malformed_fixture"


def test_null_pairs_on_non_exact_pair_kind_still_malformed() -> None:
    result = normalize_dexscreener_fixture_result(
        {
            "pairs": None,
            "schemaVersion": "1.0.0",
            "_source_status_code": 200,
            "transport_operations_used": 1,
            "response_bytes": 32,
            "normalized_rows": 0,
            "transport_operation_identities": (),
        },
        request_kind="token_discovery",
    )
    assert result.source_status == SourceStatus.FAILED
    assert result.failure_type == "dexscreener_malformed_fixture"


def test_enrich_no_match_is_exact_pair_unavailable_not_malformed(tmp_path) -> None:
    db = _db(tmp_path)
    mint, _sig, pool = _seed(db, 1)[0]
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        evidence = enrich_pool_liquidity(
            connection,
            mint=mint,
            pumpswap_pool=pool,
            dexscreener_transport=fixture_success_transport(
                {
                    "pairs": None,
                    "schemaVersion": "1.0.0",
                    "_source_status_code": 200,
                }
            ),
            request_key="strengthening-null-no-match",
        ).to_dict()
    finally:
        connection.close()
    assert evidence["outcome_category"] == LIQUIDITY_EXACT_PAIR_UNAVAILABLE_OR_MISMATCH
    assert evidence["reason"] == "LIQUIDITY_NO_EXACT_PAIR"
    assert evidence["liquidity_usd"] is None
    assert evidence["source_failure_id"] is None
    assert evidence["source_response_id"] is not None
    assert evidence["outcome_category"] != LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL


def test_floor_unchanged_and_below_floor_still_excluded(tmp_path) -> None:
    assert SELECTION_FLOOR_USD == 3000.0
    db = _db(tmp_path)
    specs = _seed(db, 2)
    values = {
        specs[0][2]: (specs[0][0], 3_000.0),
        specs[1][2]: (specs[1][0], 2_999.99),
    }

    def factory(_mint, pool):
        mint, liq = values[pool]
        return fixture_success_transport(_pair(pool, mint, liq))

    report = run_graduated_liquidity_front_door(
        db,
        cycle_seed="strengthening-floor",
        latest_mints=set(),
        dexscreener_transport_factory=factory,
        now=NOW,
        max_candidates=2,
    )
    by_mint = {c["mint"]: c for c in report["candidates"]}
    above = by_mint[specs[0][0]]
    below = by_mint[specs[1][0]]
    assert above["eligible"] is True
    assert above["liquidity"]["outcome_category"] == LIQUIDITY_EXACT_ABOVE_FLOOR
    assert below["eligible"] is False
    assert below["liquidity"]["outcome_category"] == LIQUIDITY_EXACT_BELOW_FLOOR


def test_neutral_selection_ignores_provider_order_and_magnitude() -> None:
    # High liquidity first in provider order, low liquidity second — selection
    # must not prefer magnitude; deterministic identity order + seed only.
    high = SelectionCandidate(
        mint="MintHighLiqzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz",
        pair_address="PoolHigh",
        market_identity="solana-mainnet:pumpswap:PoolHigh",
        provenance="LATEST_GRADUATED",
        lifecycle_state="PUMPSWAP_GRADUATED_CONFIRMED",
        graduation_block_time=100,
        liquidity_usd=50_000.0,
    )
    low = SelectionCandidate(
        mint="MintLowLiqaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        pair_address="PoolLow",
        market_identity="solana-mainnet:pumpswap:PoolLow",
        provenance="PERSISTED_GRADUATED",
        lifecycle_state="PUMPSWAP_GRADUATED_CONFIRMED",
        graduation_block_time=200,
        liquidity_usd=3_001.0,
    )
    # Provider-order: high first.
    a = select_two_candidates([high, low], cycle_seed="seed-a")
    b = select_two_candidates([low, high], cycle_seed="seed-a")
    assert a.ready and b.ready
    assert {c.mint for c in a.selected} == {c.mint for c in b.selected}
    assert a.selected[0].mint == b.selected[0].mint
    assert a.selected[1].mint == b.selected[1].mint
    # Same seed, same set regardless of input order; magnitude unused.


def test_two_eligible_selection_stops_at_two_distinct_mints(tmp_path) -> None:
    db = _db(tmp_path)
    specs = _seed(db, 4)
    values = {
        pool: (mint, 5_000.0 + index * 1000.0)
        for index, (mint, _sig, pool) in enumerate(specs)
    }

    def factory(_mint, pool):
        mint, liq = values[pool]
        return fixture_success_transport(_pair(pool, mint, liq))

    report = run_graduated_liquidity_front_door(
        db,
        cycle_seed="strengthening-two",
        latest_mints=set(),
        dexscreener_transport_factory=factory,
        now=NOW,
        max_candidates=4,
    )
    eligible = [c for c in report["candidates"] if c.get("eligible")]
    assert len(eligible) >= 2
    two = report["two_candidate_selection"]
    assert two["ready"] is True
    assert report["selected_count"] == 2
    mints = [item["mint"] for item in report["selected"]]
    assert len(mints) == 2
    assert len(set(mints)) == 2


def test_one_mint_cannot_occupy_two_selection_slots() -> None:
    same_mint = "SameMintIdentityaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    a = SelectionCandidate(
        mint=same_mint,
        pair_address="PoolA",
        market_identity="solana-mainnet:pumpswap:PoolA",
        provenance="LATEST_GRADUATED",
        lifecycle_state="PUMPSWAP_GRADUATED_CONFIRMED",
        graduation_block_time=1,
        liquidity_usd=10_000.0,
    )
    b = SelectionCandidate(
        mint=same_mint,
        pair_address="PoolB",
        market_identity="solana-mainnet:pumpswap:PoolB",
        provenance="PERSISTED_GRADUATED",
        lifecycle_state="PUMPSWAP_GRADUATED_CONFIRMED",
        graduation_block_time=2,
        liquidity_usd=20_000.0,
    )
    other = SelectionCandidate(
        mint="OtherMintbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        pair_address="PoolC",
        market_identity="solana-mainnet:pumpswap:PoolC",
        provenance="PERSISTED_GRADUATED",
        lifecycle_state="PUMPSWAP_GRADUATED_CONFIRMED",
        graduation_block_time=3,
        liquidity_usd=4_000.0,
    )
    result = select_two_candidates([a, b, other], cycle_seed="same-mint")
    assert result.ready
    selected_mints = [c.mint for c in result.selected]
    assert len(selected_mints) == 2
    assert len(set(selected_mints)) == 2
    assert selected_mints.count(same_mint) == 1

"""Focused regression proof for the consumed Cycle-2 graduated-supply failure.

Offline/disposable DB only.  No live provider, campaign authorization, lifecycle,
wallet, financial, retry, endpoint-rotation, or scheduler behaviour is exercised.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from printer_v1.db.migrate import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    run_dexscreener_batch_market_resolution,
)
from printer_v1.operator_cli.graduated_supply_front_door import (
    GraduatedSupplyError,
    _source_specific_admission_for,
)
from printer_v1.sources.dexscreener import fixture_success_transport
from printer_v1.sources.pumpswap_graduated_registry import (
    LATEST_GRADUATED_CHANNEL,
    export_graduated_candidates,
    record_graduated_candidate,
)

MINT = "4FN5PSaprS73Z2SRGx2HG9eaES1yVURMU5yAPpDQpump"
POOL = "9yuowVdGRZ35yM339cjyTWfhAdJJVPJqPKGHhyCXG3fo"
SIG = (
    "kbqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usESbbbbbbb"
)
NOW = "2026-08-19T15:30:00+00:00"
WSOL = "So11111111111111111111111111111111111111112"


def _pair_payload() -> dict:
    return {
        "pairs": [
            {
                "chainId": "solana",
                "pairAddress": POOL,
                "baseToken": {"address": MINT, "symbol": "MEME", "name": "Meme"},
                "quoteToken": {"address": WSOL, "symbol": "SOL", "name": "Wrapped SOL"},
                "dexId": "pumpswap",
                "priceUsd": "0.10",
                "liquidity": {"usd": 15_350.10},
                "volume": {"m5": 100.0, "h1": 1000.0, "h24": 10_000.0},
                "txns": {"m5": {"buys": 3, "sells": 2}},
                "priceChange": {"m5": 1.0},
            }
        ]
    }


def _seed_registry(db: Path) -> list[dict]:
    apply_migrations(db)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        record_graduated_candidate(
            connection,
            mint=MINT,
            migration_signature=SIG,
            pumpswap_pool=POOL,
            graduation_block_time=1_787_153_400,
            graduation_slot=432_400_000,
            now="2026-08-19T14:00:00+00:00",
            discovery_channel=LATEST_GRADUATED_CHANNEL,
        )
        connection.commit()
        return [dict(row) for row in export_graduated_candidates(connection)]
    finally:
        connection.close()


def test_historical_registry_market_refresh_preserves_direct_pump_proof(
    tmp_path: Path,
) -> None:
    """Registry proof must survive a current market refresh without rediscovery."""
    db = tmp_path / "historical-proof.sqlite3"
    inventory = _seed_registry(db)

    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        report = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            request_key="cycle2-historical-proof-mint-batch-r1",
            now=NOW,
            campaign_id="cycle2-proof-campaign",
            run_id="cycle2-proof-run",
            cycle_id="cycle2-proof-cycle",
            transport=fixture_success_transport(_pair_payload()),
            enable_geckoterminal_fallback=False,
            stage_sequence=1,
        )
    finally:
        connection.close()

    candidate = next(item for item in report["candidates"] if item["mint"] == MINT)
    assert candidate["eligible"] is True
    assert candidate["admission_authority"] == "DIRECT_PUMP_PUMPSWAP"
    assert candidate["nomination_source"] == "direct_pump_migration"
    assert candidate["lineage_state"] == "PUMP_GRADUATION_CONFIRMED"
    assert candidate["exact_present_pool_confirmed"] is True
    assert candidate["direct_pump_evidence"] == {
        "mint": MINT,
        "pool": POOL,
        "migration_signature": SIG,
        "pumpswap_program_id": candidate["direct_pump_evidence"]["pumpswap_program_id"],
        "graduation_slot": 432_400_000,
        "graduation_block_time": 1_787_153_400,
        "confirmed": True,
    }

    # This is the exact consumed-run boundary: the final source-specific
    # admission must succeed even though no same-invocation direct migration
    # candidate_mix was needed to reconstruct the historical proof.
    admission = _source_specific_admission_for(candidate)
    assert admission.mint == MINT
    assert admission.pool_address == POOL
    assert admission.signature == SIG


def test_typed_missing_direct_proof_exposes_bounded_failure_context() -> None:
    carrier = {
        "mint": MINT,
        "pool": POOL,
        "market_identity": f"solana-mainnet:pumpswap:{POOL}",
        "admission_authority": "DIRECT_PUMP_PUMPSWAP",
        "nomination_source": "direct_pump_migration",
        "lineage_state": "PUMP_GRADUATION_CONFIRMED",
        "exact_present_pool_confirmed": True,
    }
    with pytest.raises(GraduatedSupplyError) as raised:
        _source_specific_admission_for(carrier)

    exc = raised.value
    assert exc.code == "DIRECT_PUMP_EVIDENCE_MISSING"
    assert exc.stage == "SOURCE_SPECIFIC_ADMISSION"
    assert exc.mint == MINT
    assert exc.pool == POOL
    assert exc.admission_authority == "DIRECT_PUMP_PUMPSWAP"
    assert exc.nomination_source == "direct_pump_migration"


def test_market_present_pool_path_remains_non_pump_and_valid() -> None:
    carrier = {
        "mint": MINT,
        "pool": POOL,
        "market_identity": f"solana-mainnet:pumpswap:{POOL}",
        "admission_authority": "MARKET_PRESENT_POOL",
        "nomination_source": "dexscreener",
        "lineage_state": "UNKNOWN_ORIGIN",
        "exact_present_pool_confirmed": True,
        "liquidity_observed_at": NOW,
    }
    admission = _source_specific_admission_for(carrier)
    assert admission.admission_authority.value == "MARKET_PRESENT_POOL"
    assert admission.signature == ""
    assert admission.pool_address == POOL

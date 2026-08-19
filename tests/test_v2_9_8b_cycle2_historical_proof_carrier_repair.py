"""Focused regression proof for the consumed Cycle-2 graduated-supply failure.

Offline/disposable DB only. No live provider, campaign authorization, lifecycle,
wallet, financial, retry, endpoint-rotation, or scheduler behaviour is exercised.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from printer_v1.db.migrate import apply_migrations
from printer_v1.operator_cli.graduated_supply_front_door import (
    GraduatedSupplyError,
    _rehydrate_historical_direct_candidate,
    _source_specific_admission_for,
)
from printer_v1.sources.pumpswap_graduated_registry import (
    LATEST_GRADUATED_CHANNEL,
    record_graduated_candidate,
)

MINT = "4FN5PSaprS73Z2SRGx2HG9eaES1yVURMU5yAPpDQpump"
POOL = "9yuowVdGRZ35yM339cjyTWfhAdJJVPJqPKGHhyCXG3fo"
SIG = (
    "kbqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usESbbbbbbb"
)
NOW = "2026-08-19T15:30:00+00:00"
GRADUATION_BLOCK_TIME = 1_787_153_400
GRADUATION_SLOT = 432_400_000


def _seed_registry(db: Path) -> None:
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
            graduation_block_time=GRADUATION_BLOCK_TIME,
            graduation_slot=GRADUATION_SLOT,
            now="2026-08-19T14:00:00+00:00",
            discovery_channel=LATEST_GRADUATED_CHANNEL,
        )
        connection.commit()
    finally:
        connection.close()


def _historical_market_carrier() -> dict:
    """Shape emitted after current market revalidation in the consumed path."""
    return {
        "mint": MINT,
        "pool": POOL,
        "pumpswap_pool": POOL,
        "market_identity": f"solana-mainnet:pumpswap:{POOL}",
        "provenance": "PERSISTED_GRADUATED",
        "lifecycle_state": "PUMPSWAP_GRADUATED_CONFIRMED",
        "graduation_block_time": GRADUATION_BLOCK_TIME,
        "liquidity": {
            "status": "LIQUIDITY_PROVEN",
            "liquidity_usd": 15_350.10,
            "liquidity_observed_at": NOW,
        },
        "evidence_expires_at": "2026-08-19T16:00:00+00:00",
        "eligible": True,
        "rejection": None,
    }


def test_historical_registry_market_refresh_rejoins_direct_pump_proof(
    tmp_path: Path,
) -> None:
    """A historical candidate need not be rediscovered by the current live tail."""
    db = tmp_path / "historical-proof.sqlite3"
    _seed_registry(db)

    candidate = _rehydrate_historical_direct_candidate(
        _historical_market_carrier(), db_path=db
    )

    assert candidate["admission_authority"] == "DIRECT_PUMP_PUMPSWAP"
    assert candidate["nomination_source"] == "direct_pump_migration"
    assert candidate["lineage_state"] == "PUMP_GRADUATION_CONFIRMED"
    assert candidate["exact_present_pool_confirmed"] is True
    assert candidate["direct_pump_evidence"] == {
        "mint": MINT,
        "pool": POOL,
        "migration_signature": SIG,
        "pumpswap_program_id": candidate["direct_pump_evidence"]["pumpswap_program_id"],
        "graduation_slot": GRADUATION_SLOT,
        "graduation_block_time": GRADUATION_BLOCK_TIME,
        "confirmed": True,
    }

    # Exact consumed-run boundary: the original source-specific validator now
    # receives a complete carrier and succeeds without same-invocation discovery.
    admission = _source_specific_admission_for(candidate)
    assert admission.mint == MINT
    assert admission.pool_address == POOL
    assert admission.signature == SIG


def test_corrupt_historical_registry_proof_fails_closed(tmp_path: Path) -> None:
    db = tmp_path / "corrupt-proof.sqlite3"
    _seed_registry(db)
    connection = sqlite3.connect(db)
    try:
        connection.execute(
            "UPDATE printer_pumpswap_graduated_candidate_registry "
            "SET migration_signature='' WHERE mint_identity=?",
            (MINT,),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(GraduatedSupplyError) as raised:
        _rehydrate_historical_direct_candidate(
            _historical_market_carrier(), db_path=db
        )

    exc = raised.value
    assert exc.code == "DIRECT_PUMP_EVIDENCE_MISSING"
    assert exc.__class__.__name__ == "DIRECT_PUMP_EVIDENCE_MISSING"
    assert exc.stage == "SOURCE_SPECIFIC_ADMISSION"
    assert exc.mint == MINT
    assert exc.pool == POOL


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
    # The existing live terminal classifier uses the exception class-name
    # fallback for unknown exception types, so this remains categorical there.
    assert exc.__class__.__name__ == "DIRECT_PUMP_EVIDENCE_MISSING"
    assert exc.stage == "SOURCE_SPECIFIC_ADMISSION"
    assert exc.mint == MINT
    assert exc.pool == POOL
    assert exc.admission_authority == "DIRECT_PUMP_PUMPSWAP"
    assert exc.nomination_source == "direct_pump_migration"
    assert len(exc.detail) <= 512


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

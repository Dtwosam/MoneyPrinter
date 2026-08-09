"""DTW96 RED: reconciliation capacity must be enforced before provider I/O.

Disposable SQLite and fixture transports only. No live source calls or operational
runtime.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    run_dexscreener_batch_market_resolution,
)
from printer_v1.sources.dexscreener import fixture_success_transport
from printer_v1.sources.geckoterminal import (
    fixture_success_transport as geckoterminal_fixture_success_transport,
)
from printer_v1.sources.pumpswap_graduated_registry import (
    PUMPSWAP_AMM_PROGRAM_ID,
    PUMPSWAP_VENUE,
    record_graduated_candidate,
)


NOW = "2026-08-04T12:00:00+00:00"
WSOL = "So11111111111111111111111111111111111111112"


@pytest.fixture
def database():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "dtw96-pre-io.sqlite3"
        apply_migrations(path)
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()


def _seed(connection: sqlite3.Connection, count: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(count):
        mint = f"Mint{index:02d}"
        pool = f"Pool{index:02d}"
        record_graduated_candidate(
            connection,
            mint=mint,
            migration_signature=f"Signature{index:02d}",
            pumpswap_pool=pool,
            graduation_block_time=1_700_000_000 + index,
            graduation_slot=index,
            now=NOW,
        )
        rows.append(
            {
                "mint_identity": mint,
                "pumpswap_pool": pool,
                "market_identity": f"solana-mainnet:{PUMPSWAP_VENUE}:{pool}",
                "lifecycle_state": "PUMPSWAP_GRADUATED_CONFIRMED",
                "graduation_block_time": 1_700_000_000 + index,
                "pumpswap_program_id": PUMPSWAP_AMM_PROGRAM_ID,
                "latest_channel": "PERSISTED_GRADUATED",
            }
        )
    connection.commit()
    return rows


def _gt_factory(calls: list[str]):
    def factory(mint: str):
        calls.append(mint)
        suffix = mint[-2:]
        return geckoterminal_fixture_success_transport(
            {
                "data": [
                    {
                        "id": f"solana_Pool{suffix}",
                        "type": "pool",
                        "attributes": {
                            "address": f"Pool{suffix}",
                            "base_token_address": mint,
                            "quote_token_address": WSOL,
                            "dex_id": "pumpswap",
                            "reserve_in_usd": "6000",
                        },
                    }
                ]
            }
        )

    return factory


def test_zero_reconciliation_capacity_makes_zero_fallback_requests(database) -> None:
    inventory = _seed(database, 3)
    gt_calls: list[str] = []

    result = run_dexscreener_batch_market_resolution(
        database,
        inventory_rows=inventory,
        transport=fixture_success_transport({"pairs": []}),
        geckoterminal_transport_factory=_gt_factory(gt_calls),
        enable_geckoterminal_fallback=True,
        max_geckoterminal_fallbacks=0,
        request_key="dtw96-cap-zero",
        now=NOW,
        campaign_id="campaign-dtw96",
    )

    assert gt_calls == []
    assert result["calls_by_stage"]["market_batching"] == 1
    assert result["calls_by_stage"]["reconciliation"] == 0
    assert result["source_request_count"] == 1
    assert result["reconciliation_fallback_suppressed_count"] == 3


def test_partial_reconciliation_capacity_caps_requests_before_io(database) -> None:
    inventory = _seed(database, 4)
    gt_calls: list[str] = []

    result = run_dexscreener_batch_market_resolution(
        database,
        inventory_rows=inventory,
        transport=fixture_success_transport({"pairs": []}),
        geckoterminal_transport_factory=_gt_factory(gt_calls),
        enable_geckoterminal_fallback=True,
        max_geckoterminal_fallbacks=2,
        request_key="dtw96-cap-two",
        now=NOW,
        campaign_id="campaign-dtw96",
    )

    assert gt_calls == ["Mint00", "Mint01"]
    assert result["calls_by_stage"]["market_batching"] == 1
    assert result["calls_by_stage"]["reconciliation"] == 2
    assert result["source_request_count"] == 3
    assert result["reconciliation_fallback_suppressed_count"] == 2

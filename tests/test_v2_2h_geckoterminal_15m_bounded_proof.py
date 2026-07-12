"""V2-2H bounded proof — GeckoTerminal 15m evidence pipeline integration.

Proves the full pipeline using isolated DB + fixture transports:
  1. Source Governor accepts both new request kinds
  2. OHLCV enrichment produces price_change_15m and volume_15m with provenance
  3. Trades enrichment produces txns_15m with completeness annotation
  4. Merged enrichment + base snapshot round-trips through normalize_snapshot_payload
  5. record_token_snapshot persists all enriched fields to DB
  6. normalized_snapshot_payload_json in DB contains source_kind annotations
  7. PROVIDER_CANDLE_DERIVED guard blocks staged derivation from overwriting
  8. Zero rows written to financial/paper/memory tables throughout

Constraints:
  - No live HTTP calls; fixture transports only
  - Isolated DB per test (tmp_path)
  - Source Governor checked via can_request_source()
  - No scheduler bypass, no A3/A4, no retrieval, no positions, no PnL
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from printer_v1.db import apply_migrations
from printer_v1.sources.geckoterminal_15m import (
    GECKOTERMINAL_OHLCV_REQUEST_KIND,
    GECKOTERMINAL_POOL_TRADES_REQUEST_KIND,
    GT15M_NETWORK,
    PROVIDER_CANDLE_DERIVED,
    PROVIDER_TRADES_WINDOW,
    TRADE_HISTORY_COMPLETE,
    TRADE_HISTORY_TRUNCATED,
    build_gt15m_ohlcv_url,
    build_gt15m_trades_url,
    enrich_candidate_15m_ohlcv,
    enrich_candidate_15m_trades,
)
from printer_v1.sources.governor import can_request_source
from printer_v1.snapshots.quality import normalize_snapshot_payload
from printer_v1.snapshots.recorder import record_token_snapshot
from printer_v1.snapshots.staged_derivation import apply_staged_derivation

# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------

_POOL_ADDRESS = "BProof11111111111111111111111111111111111111"
_NETWORK = GT15M_NETWORK
_OHLCV_URL = build_gt15m_ohlcv_url(_POOL_ADDRESS)
_TRADES_URL = build_gt15m_trades_url(_POOL_ADDRESS)
_TOKEN_MINT = "BProofMint111111111111111111111111111111111"
_PAIR_ADDRESS = _POOL_ADDRESS

# A deterministic "now" safely in the past so candles are completed
_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)
_NOW_UNIX = _NOW.timestamp()

# Candle start 1 full period back so it completed exactly 900s before now
_CANDLE_START_UNIX = int(_NOW_UNIX - 900 * 2)  # completed 900s ago
_CANDLE_END_UNIX = _CANDLE_START_UNIX + 900


def _ohlcv_payload(candles: list) -> dict:
    return {
        "data": {
            "attributes": {
                "ohlcv_list": candles,
            }
        }
    }


def _fresh_candle(open_: float = 0.001, close: float = 0.0015, volume: float = 25000.0) -> list:
    # [unix_start, open, high, low, close, volume]
    return [_CANDLE_START_UNIX, open_, open_ * 1.1, open_ * 0.9, close, volume]


def _trade(ts_unix: float, kind: str = "buy") -> dict:
    return {"attributes": {"block_timestamp": ts_unix, "kind": kind}}


def _trades_payload(trades: list) -> dict:
    return {"data": trades}


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "bounded_proof.db"
    apply_migrations(db_path)
    return db_path


def _query_snapshot(db_path: Path, snapshot_id: int) -> sqlite3.Row:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM printer_token_snapshots WHERE id = ?", (snapshot_id,)
    ).fetchone()
    conn.close()
    return row


def _count_financial_rows(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(str(db_path))
    tables = [
        "printer_episodes",
        "printer_paper_decisions",
        "printer_paper_positions",
        "printer_paper_trade_events",
        "printer_paper_trade_audits",
    ]
    counts = {}
    for table in tables:
        counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    return counts


def _seed_token_pair(db_path: Path, token_mint: str, pair_address: str) -> tuple[int, int]:
    """Pre-seed token + pair rows; returns (token_id, pair_id)."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("INSERT OR IGNORE INTO printer_tokens (token_mint, chain) VALUES (?, ?)", (token_mint, "solana"))
    conn.commit()
    token_id = conn.execute("SELECT id FROM printer_tokens WHERE token_mint = ?", (token_mint,)).fetchone()["id"]
    conn.execute("INSERT OR IGNORE INTO printer_pairs (token_id, pair_address) VALUES (?, ?)", (token_id, pair_address))
    conn.commit()
    pair_id = conn.execute("SELECT id FROM printer_pairs WHERE pair_address = ?", (pair_address,)).fetchone()["id"]
    conn.close()
    return token_id, pair_id


def _base_snapshot_payload(token_mint: str = _TOKEN_MINT, pair_address: str = _PAIR_ADDRESS) -> dict:
    return {
        "token_mint": token_mint,
        "pair_address": pair_address,
        "captured_at": "2026-07-12T12:00:00+00:00",
        "tracking_lane": "TRACK_FAST",
        "snapshot_mode": "NORMAL_MODE",
        "price_usd": 0.0015,
        "liquidity_usd": 8000.0,
        "source_name": "geckoterminal",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
    }


# ---------------------------------------------------------------------------
# BP-01: Source Governor approves both new request kinds
# ---------------------------------------------------------------------------

class TestGovernorApproval:
    def test_bp01a_governor_approves_ohlcv_15m(self):
        decision = can_request_source("geckoterminal", GECKOTERMINAL_OHLCV_REQUEST_KIND, recent_request_count=0)
        assert decision.allowed is True, f"Expected allowed; reason={decision.reason}"

    def test_bp01b_governor_approves_pool_trades_15m(self):
        decision = can_request_source("geckoterminal", GECKOTERMINAL_POOL_TRADES_REQUEST_KIND, recent_request_count=0)
        assert decision.allowed is True, f"Expected allowed; reason={decision.reason}"

    def test_bp01c_governor_rejects_unknown_kind(self):
        decision = can_request_source("geckoterminal", "geckoterminal_unknown_kind_xyz", recent_request_count=0)
        assert decision.allowed is False
        assert decision.reason == "request_kind_not_allowed"


# ---------------------------------------------------------------------------
# BP-02: OHLCV enrichment produces correct fields and provenance
# ---------------------------------------------------------------------------

class TestOhlcvEnrichment:
    def test_bp02a_price_change_and_volume_populated(self):
        payload = _ohlcv_payload([_fresh_candle(open_=0.001, close=0.0015)])
        result = enrich_candidate_15m_ohlcv(
            payload, pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_OHLCV_URL, now=_NOW,
        )
        assert "price_change_15m" in result
        assert "volume_15m" in result
        expected_pct = round((0.0015 - 0.001) / 0.001 * 100, 6)
        assert result["price_change_15m"] == pytest.approx(expected_pct)
        assert result["price_change_15m_source_kind"] == PROVIDER_CANDLE_DERIVED
        assert result["volume_15m_source_kind"] == PROVIDER_CANDLE_DERIVED

    def test_bp02b_provenance_contains_required_keys(self):
        payload = _ohlcv_payload([_fresh_candle()])
        result = enrich_candidate_15m_ohlcv(
            payload, pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_OHLCV_URL, now=_NOW,
        )
        prov = result.get("price_change_15m_provenance", {})
        assert prov["source"] == "geckoterminal"
        assert prov["network"] == _NETWORK
        assert prov["pool_address"] == _POOL_ADDRESS
        assert prov["calculation_method"] == "candle_arithmetic"
        assert "candle_start_iso" in prov
        assert "candle_end_iso" in prov


# ---------------------------------------------------------------------------
# BP-03: Trades enrichment produces correct txns_15m with completeness
# ---------------------------------------------------------------------------

class TestTradesEnrichment:
    def _window_trades(self, count: int) -> list:
        """count trades all inside the 15m window."""
        return [_trade(_NOW_UNIX - 100 - i) for i in range(count)]

    def test_bp03a_complete_fewer_than_max(self):
        payload = _trades_payload(self._window_trades(5))
        result = enrich_candidate_15m_trades(
            payload, pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_TRADES_URL, now=_NOW,
        )
        assert result["txns_15m"] == 5
        assert result["txns_15m_completeness"] == TRADE_HISTORY_COMPLETE
        assert result["txns_15m_source_kind"] == PROVIDER_TRADES_WINDOW

    def test_bp03b_truncated_when_capped(self):
        # 300 trades all inside window, oldest does NOT reach window_start
        window_start = _NOW_UNIX - 900
        trades = [_trade(window_start + 1 + i * 2) for i in range(300)]
        payload = _trades_payload(trades)
        result = enrich_candidate_15m_trades(
            payload, pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_TRADES_URL, now=_NOW,
        )
        assert result["txns_15m"] is None
        assert result["txns_15m_completeness"] == TRADE_HISTORY_TRUNCATED

    def test_bp03c_provenance_keys_present(self):
        payload = _trades_payload(self._window_trades(3))
        result = enrich_candidate_15m_trades(
            payload, pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_TRADES_URL, now=_NOW,
        )
        prov = result.get("txns_15m_provenance", {})
        assert prov["source"] == "geckoterminal"
        assert "window_start_iso" in prov
        assert "window_end_iso" in prov


# ---------------------------------------------------------------------------
# BP-04: normalize_snapshot_payload passthrough
# ---------------------------------------------------------------------------

class TestNormalizePassthrough:
    def test_bp04_all_enrichment_annotations_survive_normalize(self):
        payload = {
            **_base_snapshot_payload(),
            "price_change_15m": 50.0,
            "price_change_15m_source_kind": PROVIDER_CANDLE_DERIVED,
            "price_change_15m_provenance": {"source": "geckoterminal"},
            "volume_15m": 10000.0,
            "volume_15m_source_kind": PROVIDER_CANDLE_DERIVED,
            "txns_15m": 7,
            "txns_15m_source_kind": PROVIDER_TRADES_WINDOW,
            "txns_15m_completeness": TRADE_HISTORY_COMPLETE,
        }
        normalized = normalize_snapshot_payload(payload)
        assert normalized["price_change_15m"] == pytest.approx(50.0)
        assert normalized["price_change_15m_source_kind"] == PROVIDER_CANDLE_DERIVED
        assert isinstance(normalized["price_change_15m_provenance"], dict)
        assert normalized["volume_15m"] == pytest.approx(10000.0)
        assert normalized["volume_15m_source_kind"] == PROVIDER_CANDLE_DERIVED
        assert normalized["txns_15m"] == 7
        assert normalized["txns_15m_source_kind"] == PROVIDER_TRADES_WINDOW
        assert normalized["txns_15m_completeness"] == TRADE_HISTORY_COMPLETE


# ---------------------------------------------------------------------------
# BP-05: Full pipeline — enrichment → snapshot persist → DB verification
# ---------------------------------------------------------------------------

class TestPipelinePersistence:
    def test_bp05_enriched_fields_reach_db(self, tmp_path: Path):
        db_path = _make_db(tmp_path)
        _seed_token_pair(db_path, _TOKEN_MINT, _PAIR_ADDRESS)

        ohlcv_payload = _ohlcv_payload([_fresh_candle(open_=0.001, close=0.0015, volume=20000.0)])
        ohlcv_enrichment = enrich_candidate_15m_ohlcv(
            ohlcv_payload, pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_OHLCV_URL, now=_NOW,
        )

        trades_payload = _trades_payload([_trade(_NOW_UNIX - 50), _trade(_NOW_UNIX - 100)])
        trades_enrichment = enrich_candidate_15m_trades(
            trades_payload, pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_TRADES_URL, now=_NOW,
        )

        base = _base_snapshot_payload()
        payload = {**base, **ohlcv_enrichment, **trades_enrichment}

        success, snapshot_id = record_token_snapshot(db_path, payload)
        assert success is True
        assert snapshot_id > 0

        row = _query_snapshot(db_path, snapshot_id)
        assert row is not None

        # Numeric columns populated in DB row
        assert row["price_change_15m"] == pytest.approx(50.0, rel=1e-4)
        assert row["volume_15m"] == pytest.approx(20000.0)
        assert row["txns_15m"] == 2

        # normalized_snapshot_payload_json contains provenance annotations
        nspj = json.loads(row["normalized_snapshot_payload_json"])
        assert nspj["price_change_15m_source_kind"] == PROVIDER_CANDLE_DERIVED
        assert nspj["volume_15m_source_kind"] == PROVIDER_CANDLE_DERIVED
        assert nspj["txns_15m_source_kind"] == PROVIDER_TRADES_WINDOW
        assert nspj["txns_15m_completeness"] == TRADE_HISTORY_COMPLETE
        assert isinstance(nspj.get("price_change_15m_provenance"), dict)
        assert isinstance(nspj.get("volume_15m_provenance"), dict)
        assert isinstance(nspj.get("txns_15m_provenance"), dict)

    def test_bp06_truncated_txns_persists_source_kind(self, tmp_path: Path):
        db_path = _make_db(tmp_path)
        mint2 = "BProofMint222222222222222222222222222222222"
        pair2 = "BProof22222222222222222222222222222222222222"
        _seed_token_pair(db_path, mint2, pair2)

        ohlcv_payload = _ohlcv_payload([_fresh_candle()])
        ohlcv_enrichment = enrich_candidate_15m_ohlcv(
            ohlcv_payload, pool_address=pair2, network=_NETWORK,
            endpoint_url=build_gt15m_ohlcv_url(pair2), now=_NOW,
        )

        # 300 capped trades — truncated
        window_start = _NOW_UNIX - 900
        trades = [_trade(window_start + 1 + i * 2) for i in range(300)]
        trades_payload = _trades_payload(trades)
        trades_enrichment = enrich_candidate_15m_trades(
            trades_payload, pool_address=pair2, network=_NETWORK,
            endpoint_url=build_gt15m_trades_url(pair2), now=_NOW,
        )
        assert trades_enrichment["txns_15m"] is None
        assert trades_enrichment["txns_15m_completeness"] == TRADE_HISTORY_TRUNCATED

        base = _base_snapshot_payload(token_mint=mint2, pair_address=pair2)
        payload = {**base, **ohlcv_enrichment, **trades_enrichment}

        success, snapshot_id = record_token_snapshot(db_path, payload)
        assert success is True

        row = _query_snapshot(db_path, snapshot_id)
        assert row["txns_15m"] is None
        nspj = json.loads(row["normalized_snapshot_payload_json"])
        assert nspj["txns_15m_source_kind"] == PROVIDER_TRADES_WINDOW
        assert nspj["txns_15m_completeness"] == TRADE_HISTORY_TRUNCATED


# ---------------------------------------------------------------------------
# BP-07: PROVIDER_CANDLE_DERIVED guard blocks staged derivation
# ---------------------------------------------------------------------------

class TestStagedGuardPipeline:
    def test_bp07_guard_blocks_staged_overwrite(self, tmp_path: Path):
        db_path = _make_db(tmp_path)
        mint3 = "BProofMint333333333333333333333333333333333"
        pair3 = "BProof33333333333333333333333333333333333333"
        _seed_token_pair(db_path, mint3, pair3)

        ohlcv_payload = _ohlcv_payload([_fresh_candle(open_=0.001, close=0.002)])
        enrichment = enrich_candidate_15m_ohlcv(
            ohlcv_payload, pool_address=pair3, network=_NETWORK,
            endpoint_url=build_gt15m_ohlcv_url(pair3), now=_NOW,
        )
        assert enrichment["price_change_15m_source_kind"] == PROVIDER_CANDLE_DERIVED

        base = _base_snapshot_payload(token_mint=mint3, pair_address=pair3)
        # Insert a "prior" snapshot 900s earlier to satisfy staged derivation eligibility
        prior_payload = {
            **base,
            "captured_at": "2026-07-12T10:45:00+00:00",
            "price_usd": 0.0008,
        }
        record_token_snapshot(db_path, prior_payload)

        # Insert end snapshot with PROVIDER_CANDLE_DERIVED enrichment
        end_payload = {
            **base,
            "captured_at": "2026-07-12T11:00:00+00:00",
            "price_usd": 0.0015,
            **enrichment,
        }
        success, snapshot_id = record_token_snapshot(db_path, end_payload)
        assert success is True

        row = _query_snapshot(db_path, snapshot_id)
        nspj = json.loads(row["normalized_snapshot_payload_json"])
        # Guard must have fired: source_kind remains PROVIDER_CANDLE_DERIVED
        assert nspj["price_change_15m_source_kind"] == PROVIDER_CANDLE_DERIVED
        # The derivation kind from staged path must NOT appear
        assert nspj.get("price_change_15m_source_kind") != "DERIVED_STAGED_SNAPSHOT"


# ---------------------------------------------------------------------------
# BP-08: Zero rows in financial/paper/memory tables
# ---------------------------------------------------------------------------

class TestNoFinancialRowsFromEnrichment:
    def test_bp08_enrichment_and_snapshot_create_zero_financial_rows(self, tmp_path: Path):
        db_path = _make_db(tmp_path)

        ohlcv_payload = _ohlcv_payload([_fresh_candle()])
        enrich_candidate_15m_ohlcv(
            ohlcv_payload, pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_OHLCV_URL, now=_NOW,
        )
        trades_payload = _trades_payload([_trade(_NOW_UNIX - 50)])
        enrich_candidate_15m_trades(
            trades_payload, pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_TRADES_URL, now=_NOW,
        )

        # Also call record_token_snapshot
        mint4 = "BProofMint444444444444444444444444444444444"
        pair4 = "BProof44444444444444444444444444444444444444"
        _seed_token_pair(db_path, mint4, pair4)
        base = _base_snapshot_payload(token_mint=mint4, pair_address=pair4)
        record_token_snapshot(db_path, {**base})

        counts = _count_financial_rows(db_path)
        for table, count in counts.items():
            assert count == 0, f"Unexpected {count} rows in {table}"

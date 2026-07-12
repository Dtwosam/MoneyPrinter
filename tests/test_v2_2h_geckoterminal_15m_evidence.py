"""V2-2H targeted tests — GeckoTerminal 15m OHLCV and pool-trades enrichment.

Covers:
  TC-01  Correct OHLCV candle selection: in-progress candle skipped
  TC-02  Correct OHLCV candle selection: completed candle selected
  TC-03  Stale completed candle returns None (age > 1800s)
  TC-04  Missing/malformed ohlcv_list fails closed
  TC-05  Price change calculation: basic positive case
  TC-06  Price change calculation: negative change
  TC-07  Price change calculation: zero change
  TC-08  Price change calculation: open == 0 → None
  TC-09  Volume from completed candle
  TC-10  enrich_candidate_15m_ohlcv: fixture failure payload → empty dict
  TC-11  enrich_candidate_15m_ohlcv: missing data.attributes.ohlcv_list → empty
  TC-12  enrich_candidate_15m_ohlcv: happy path returns both price and volume
  TC-13  enrich_candidate_15m_ohlcv: wrong-network / wrong-pool not validated here
         (pool address is caller-supplied; gate is in discovery filter)
  TC-14  Trade count: fewer-than-max completeness rule (a)
  TC-15  Trade count: oldest-reaches-window completeness rule (b)
  TC-16  Trade count: capped → txns_15m = None, TRADE_HISTORY_TRUNCATED
  TC-17  Trade count: trades outside window not counted
  TC-18  Trade count: duplicate tx_hash counted separately (contract: record count)
  TC-19  enrich_candidate_15m_trades: failure payload → empty dict
  TC-20  enrich_candidate_15m_trades: missing data list → empty dict
  TC-21  enrich_candidate_15m_trades: happy path COMPLETE
  TC-22  enrich_candidate_15m_trades: capped → txns_15m None in result
  TC-23  Provider evidence not overwritten by staged derivation
         (PROVIDER_CANDLE_DERIVED in normalized_snapshot_payload_json → guard fires)
  TC-24  Staged fallback still runs when source_kind is absent
  TC-25  Infrastructure-token pool not enriched when source exclusion filters it
  TC-26  No memory, paper decision, position, trade, PnL rows from enrichment
  TC-27  Provenance annotations survive normalize_snapshot_payload passthrough
  TC-28  txns_15m = None (TRUNCATED) still persists source_kind annotation
  TC-29  OHLCV with multiple candles selects most-recent completed
  TC-30  All-in-progress ohlcv_list returns None
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from types import MappingProxyType

import pytest

from printer_v1.sources.geckoterminal_15m import (
    GT15M_CANDLE_SECONDS,
    GT15M_CANDLE_MAX_AGE_SECONDS,
    GT15M_TRADES_MAX_RESPONSE,
    PROVIDER_CANDLE_DERIVED,
    PROVIDER_TRADES_WINDOW,
    TRADE_HISTORY_COMPLETE,
    TRADE_HISTORY_TRUNCATED,
    GECKOTERMINAL_OHLCV_REQUEST_KIND,
    GECKOTERMINAL_POOL_TRADES_REQUEST_KIND,
    build_gt15m_ohlcv_url,
    build_gt15m_trades_url,
    count_txns_15m_from_trades,
    derive_price_change_15m_from_candle,
    derive_volume_15m_from_candle,
    enrich_candidate_15m_ohlcv,
    enrich_candidate_15m_trades,
    select_completed_15m_candle,
)
from printer_v1.snapshots.staged_derivation import apply_staged_derivation
from printer_v1.snapshots.quality import normalize_snapshot_payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)
_NOW_UNIX = _NOW.timestamp()

_POOL_ADDRESS = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
_NETWORK = "solana"
_OHLCV_URL = build_gt15m_ohlcv_url(_POOL_ADDRESS)
_TRADES_URL = build_gt15m_trades_url(_POOL_ADDRESS)

# Completed candle: ended 300 seconds ago (well within freshness window)
_FRESH_CANDLE_START = int(_NOW_UNIX - GT15M_CANDLE_SECONDS - 300)
_FRESH_CANDLE_END = _FRESH_CANDLE_START + GT15M_CANDLE_SECONDS
_FRESH_CANDLE_AGE = int(_NOW_UNIX - _FRESH_CANDLE_END)

# In-progress candle: ends 600 seconds in the future
_INPROGRESS_CANDLE_START = int(_NOW_UNIX - 300)

# Stale completed candle: ended 2000 seconds ago (> 1800s freshness limit)
_STALE_CANDLE_START = int(_NOW_UNIX - GT15M_CANDLE_SECONDS - 2000)
_STALE_CANDLE_END = _STALE_CANDLE_START + GT15M_CANDLE_SECONDS


def _candle(start_unix: int, open_p: float = 0.001, close_p: float = 0.0015,
            volume: float = 50000.0) -> list[Any]:
    return [start_unix, open_p, max(open_p, close_p), min(open_p, close_p), close_p, volume]


def _ohlcv_payload(ohlcv_list: list[list[Any]]) -> dict[str, Any]:
    return {
        "data": {
            "id": f"solana_{_POOL_ADDRESS}_usd_15m",
            "type": "ohlcv_request",
            "attributes": {
                "ohlcv_list": ohlcv_list,
            },
        }
    }


def _trade(ts_unix: float, kind: str = "buy", tx_hash: str | None = None) -> dict[str, Any]:
    ts_iso = datetime.fromtimestamp(ts_unix, tz=timezone.utc).isoformat()
    return {
        "id": tx_hash or str(uuid.uuid4()),
        "type": "trade",
        "attributes": {
            "block_timestamp": ts_iso,
            "kind": kind,
            "volume_in_usd": "100.0",
            "tx_hash": tx_hash or str(uuid.uuid4()),
        },
    }


def _trades_payload(trades: list[dict]) -> dict[str, Any]:
    return {"data": trades}


# ---------------------------------------------------------------------------
# TC-01 / TC-02: candle selection — in-progress skipped, completed selected
# ---------------------------------------------------------------------------

class TestSelectCompleted15mCandle:
    def test_tc01_inprogress_candle_skipped(self):
        ohlcv_list = [_candle(_INPROGRESS_CANDLE_START)]
        result = select_completed_15m_candle(ohlcv_list, _NOW)
        assert result is None

    def test_tc02_completed_candle_selected(self):
        ohlcv_list = [_candle(_FRESH_CANDLE_START)]
        result = select_completed_15m_candle(ohlcv_list, _NOW)
        assert result is not None
        assert result["candle_start_unix"] == _FRESH_CANDLE_START
        assert result["candle_end_unix"] == _FRESH_CANDLE_END
        assert result["open"] == 0.001
        assert result["close"] == 0.0015
        assert result["volume_usd"] == 50000.0
        assert result["age_since_completion_seconds"] == _FRESH_CANDLE_AGE

    def test_tc03_stale_completed_candle_returns_none(self):
        ohlcv_list = [_candle(_STALE_CANDLE_START)]
        result = select_completed_15m_candle(ohlcv_list, _NOW)
        assert result is None

    def test_tc04_empty_ohlcv_list_returns_none(self):
        assert select_completed_15m_candle([], _NOW) is None
        assert select_completed_15m_candle(None, _NOW) is None  # type: ignore

    def test_tc04b_malformed_entries_skipped(self):
        ohlcv_list = [[_FRESH_CANDLE_START, None, 0.0, 0.0, None, 100.0]]
        result = select_completed_15m_candle(ohlcv_list, _NOW)
        assert result is None

    def test_tc04c_open_zero_skipped(self):
        ohlcv_list = [[_FRESH_CANDLE_START, 0.0, 0.0, 0.0, 0.001, 100.0]]
        result = select_completed_15m_candle(ohlcv_list, _NOW)
        assert result is None

    def test_tc29_selects_most_recent_completed_when_multiple(self):
        # index 0: in-progress; index 1: fresh completed; index 2: older completed
        older_start = _FRESH_CANDLE_START - GT15M_CANDLE_SECONDS
        ohlcv_list = [
            _candle(_INPROGRESS_CANDLE_START, close_p=0.002),   # in-progress
            _candle(_FRESH_CANDLE_START, close_p=0.0015),        # fresh completed
            _candle(older_start, close_p=0.001),                  # older completed
        ]
        result = select_completed_15m_candle(ohlcv_list, _NOW)
        assert result is not None
        assert result["candle_start_unix"] == _FRESH_CANDLE_START
        assert result["close"] == 0.0015

    def test_tc30_all_inprogress_returns_none(self):
        ohlcv_list = [_candle(_INPROGRESS_CANDLE_START), _candle(_INPROGRESS_CANDLE_START - 1)]
        result = select_completed_15m_candle(ohlcv_list, _NOW)
        assert result is None


# ---------------------------------------------------------------------------
# TC-05 – TC-09: price change and volume derivation
# ---------------------------------------------------------------------------

class TestDerivePriceChange15mFromCandle:
    def _candle_dict(self, open_p: float, close_p: float) -> dict:
        return {
            "open": open_p,
            "close": close_p,
            "volume_usd": 10000.0,
            "candle_start_iso": "2026-07-12T11:44:00+00:00",
            "candle_end_iso": "2026-07-12T11:59:00+00:00",
            "age_since_completion_seconds": 60,
        }

    def test_tc05_positive_price_change(self):
        result = derive_price_change_15m_from_candle(
            self._candle_dict(0.001, 0.0015),
            pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_OHLCV_URL, fetch_time_iso=_NOW.isoformat(),
        )
        assert result is not None
        assert result["price_change_15m"] == pytest.approx(50.0, rel=1e-5)
        assert result["price_change_15m_source_kind"] == PROVIDER_CANDLE_DERIVED
        prov = result["price_change_15m_provenance"]
        assert prov["calculation_method"] == "candle_arithmetic"
        assert prov["candle_open"] == 0.001
        assert prov["candle_close"] == 0.0015

    def test_tc06_negative_price_change(self):
        result = derive_price_change_15m_from_candle(
            self._candle_dict(0.002, 0.001),
            pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_OHLCV_URL, fetch_time_iso=_NOW.isoformat(),
        )
        assert result is not None
        assert result["price_change_15m"] == pytest.approx(-50.0, rel=1e-5)

    def test_tc07_zero_price_change(self):
        result = derive_price_change_15m_from_candle(
            self._candle_dict(0.001, 0.001),
            pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_OHLCV_URL, fetch_time_iso=_NOW.isoformat(),
        )
        assert result is not None
        assert result["price_change_15m"] == 0.0

    def test_tc08_open_zero_returns_none(self):
        result = derive_price_change_15m_from_candle(
            self._candle_dict(0.0, 0.001),
            pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_OHLCV_URL, fetch_time_iso=_NOW.isoformat(),
        )
        assert result is None

    def test_tc09_volume_from_candle(self):
        candle = {**self._candle_dict(0.001, 0.0015), "volume_usd": 99999.5}
        result = derive_volume_15m_from_candle(
            candle,
            pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_OHLCV_URL, fetch_time_iso=_NOW.isoformat(),
        )
        assert result is not None
        assert result["volume_15m"] == pytest.approx(99999.5)
        assert result["volume_15m_source_kind"] == PROVIDER_CANDLE_DERIVED
        prov = result["volume_15m_provenance"]
        assert prov["evidence_kind"] == "ohlcv_candle_native_volume"
        assert prov["source"] == "geckoterminal"


# ---------------------------------------------------------------------------
# TC-10 – TC-13: enrich_candidate_15m_ohlcv
# ---------------------------------------------------------------------------

class TestEnrichCandidate15mOhlcv:
    def test_tc10_fixture_failure_returns_empty(self):
        payload = {"fixture_status": "failure", "failure_type": "test"}
        result = enrich_candidate_15m_ohlcv(
            payload, pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_OHLCV_URL, now=_NOW,
        )
        assert result == {}

    def test_tc10b_rate_limited_returns_empty(self):
        payload = {"fixture_status": "rate_limited"}
        result = enrich_candidate_15m_ohlcv(
            payload, pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_OHLCV_URL, now=_NOW,
        )
        assert result == {}

    def test_tc11_missing_ohlcv_list_returns_empty(self):
        payload = {"data": {"attributes": {}}}
        result = enrich_candidate_15m_ohlcv(
            payload, pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_OHLCV_URL, now=_NOW,
        )
        assert result == {}

    def test_tc11b_missing_data_returns_empty(self):
        result = enrich_candidate_15m_ohlcv(
            {}, pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_OHLCV_URL, now=_NOW,
        )
        assert result == {}

    def test_tc12_happy_path_returns_price_and_volume(self):
        payload = _ohlcv_payload([_candle(_FRESH_CANDLE_START, 0.001, 0.0012)])
        result = enrich_candidate_15m_ohlcv(
            payload, pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_OHLCV_URL, now=_NOW,
        )
        assert "price_change_15m" in result
        assert "price_change_15m_source_kind" in result
        assert result["price_change_15m_source_kind"] == PROVIDER_CANDLE_DERIVED
        assert "volume_15m" in result
        assert result["volume_15m"] == pytest.approx(50000.0)
        assert "price_change_15m_provenance" in result
        assert "volume_15m_provenance" in result
        assert result["price_change_15m"] == pytest.approx(20.0, rel=1e-5)

    def test_tc12b_stale_candle_returns_empty(self):
        payload = _ohlcv_payload([_candle(_STALE_CANDLE_START)])
        result = enrich_candidate_15m_ohlcv(
            payload, pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_OHLCV_URL, now=_NOW,
        )
        assert result == {}


# ---------------------------------------------------------------------------
# TC-14 – TC-22: trade count and enrich_candidate_15m_trades
# ---------------------------------------------------------------------------

class TestCountTxns15mFromTrades:
    def _window(self) -> tuple[float, float]:
        end = _NOW_UNIX
        start = end - GT15M_CANDLE_SECONDS
        return start, end

    def test_tc14_fewer_than_max_is_complete(self):
        window_start, window_end = self._window()
        trades = [_trade(window_start + 100), _trade(window_start + 200)]
        count, label, details = count_txns_15m_from_trades(
            trades, window_start_unix=window_start, window_end_unix=window_end,
            max_response=300,
        )
        assert label == TRADE_HISTORY_COMPLETE
        assert count == 2
        assert details["completeness_rule_applied"] == "fewer_than_max"

    def test_tc15_oldest_reaches_window_is_complete(self):
        window_start, window_end = self._window()
        # 300 in-window trades (spaced 2s, all within 600s of window_start)
        # plus 1 pre-window trade → total 301, max_response=300, rule (a) does NOT fire
        # oldest pre-window trade triggers rule (b)
        trades = [_trade(window_start + 1 + i * 2) for i in range(300)]
        trades.append(_trade(window_start - 60))  # reaches before window
        count, label, details = count_txns_15m_from_trades(
            trades, window_start_unix=window_start, window_end_unix=window_end,
            max_response=300,
        )
        assert label == TRADE_HISTORY_COMPLETE
        assert details["completeness_rule_applied"] == "oldest_reaches_window"
        assert count == 300  # the pre-window trade is not counted

    def test_tc16_capped_trade_history_is_truncated(self):
        window_start, window_end = self._window()
        # 300 trades all within the window, oldest is window_start + 1 (does NOT reach window)
        # total == max_response → rule (a) does not fire; oldest > window_start → rule (b) does not fire
        trades = [_trade(window_start + 1 + i * 2) for i in range(300)]
        count, label, details = count_txns_15m_from_trades(
            trades, window_start_unix=window_start, window_end_unix=window_end,
            max_response=300,
        )
        assert label == TRADE_HISTORY_TRUNCATED
        assert count is None
        assert details["completeness_rule_applied"] == "truncated"

    def test_tc17_trades_outside_window_not_counted(self):
        window_start, window_end = self._window()
        trades = [
            _trade(window_start - 100),   # before window
            _trade(window_start + 100),   # in window
            _trade(window_end + 100),     # after window
        ]
        count, label, details = count_txns_15m_from_trades(
            trades, window_start_unix=window_start, window_end_unix=window_end,
            max_response=300,
        )
        assert label == TRADE_HISTORY_COMPLETE
        assert count == 1
        assert details["trades_in_window"] == 1

    def test_tc18_duplicate_tx_hash_counted_separately(self):
        """Multiple API trade records with the same tx_hash are each counted."""
        window_start, window_end = self._window()
        same_hash = "aaa111"
        trades = [
            _trade(window_start + 100, tx_hash=same_hash),
            _trade(window_start + 200, tx_hash=same_hash),
            _trade(window_start + 300, tx_hash=same_hash),
        ]
        count, label, _ = count_txns_15m_from_trades(
            trades, window_start_unix=window_start, window_end_unix=window_end,
            max_response=300,
        )
        assert label == TRADE_HISTORY_COMPLETE
        assert count == 3  # 3 records, not 1 unique hash

    def test_trades_data_not_a_list_returns_truncated(self):
        window_start, window_end = self._window()
        count, label, details = count_txns_15m_from_trades(
            "not_a_list",  # type: ignore
            window_start_unix=window_start, window_end_unix=window_end,
        )
        assert label == TRADE_HISTORY_TRUNCATED
        assert count is None


class TestEnrichCandidate15mTrades:
    def test_tc19_failure_payload_returns_empty(self):
        result = enrich_candidate_15m_trades(
            {"fixture_status": "failure"},
            pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_TRADES_URL, now=_NOW,
        )
        assert result == {}

    def test_tc20_missing_data_list_returns_empty(self):
        result = enrich_candidate_15m_trades(
            {"data": "not_a_list"},
            pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_TRADES_URL, now=_NOW,
        )
        assert result == {}

    def test_tc21_happy_path_complete_trade_coverage(self):
        window_end = _NOW_UNIX
        window_start = window_end - GT15M_CANDLE_SECONDS
        trades = [_trade(window_start + 100), _trade(window_start + 200)]
        result = enrich_candidate_15m_trades(
            _trades_payload(trades),
            pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_TRADES_URL, now=_NOW,
        )
        assert result["txns_15m"] == 2
        assert result["txns_15m_source_kind"] == PROVIDER_TRADES_WINDOW
        assert result["txns_15m_completeness"] == TRADE_HISTORY_COMPLETE
        prov = result["txns_15m_provenance"]
        assert prov["source"] == "geckoterminal"
        assert prov["completeness"] == TRADE_HISTORY_COMPLETE
        assert prov["count_method"] == "trade_record_count_buys_plus_sells"

    def test_tc22_capped_history_txns_15m_is_none(self):
        window_end = _NOW_UNIX
        window_start = window_end - GT15M_CANDLE_SECONDS
        # oldest at window_start + 1 (does not reach window); total == max → TRUNCATED
        trades = [_trade(window_start + 1 + i * 2) for i in range(300)]
        result = enrich_candidate_15m_trades(
            _trades_payload(trades),
            pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_TRADES_URL, now=_NOW,
        )
        assert result["txns_15m"] is None
        assert result["txns_15m_completeness"] == TRADE_HISTORY_TRUNCATED

    def test_tc28_truncated_still_emits_source_kind(self):
        window_end = _NOW_UNIX
        window_start = window_end - GT15M_CANDLE_SECONDS
        trades = [_trade(window_start + 1 + i * 2) for i in range(300)]
        result = enrich_candidate_15m_trades(
            _trades_payload(trades),
            pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_TRADES_URL, now=_NOW,
        )
        assert "txns_15m_source_kind" in result
        assert result["txns_15m_source_kind"] == PROVIDER_TRADES_WINDOW
        assert "txns_15m_provenance" in result


# ---------------------------------------------------------------------------
# TC-23 / TC-24: staged derivation guard
# ---------------------------------------------------------------------------

class TestStagedDerivationGuard:
    """Verify that PROVIDER_CANDLE_DERIVED prevents staged overwrite."""

    def _make_db(self, tmp_path: Path) -> sqlite3.Connection:
        from printer_v1.db import apply_migrations
        db_path = tmp_path / "test_staged_guard.db"
        apply_migrations(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _insert_token_pair(self, conn: sqlite3.Connection, mint: str, pair_addr: str) -> tuple[int, int]:
        conn.execute("INSERT INTO printer_tokens (token_mint, chain) VALUES (?, ?)", (mint, "solana"))
        token_id = conn.execute("SELECT id FROM printer_tokens WHERE token_mint = ?", (mint,)).fetchone()["id"]
        conn.execute("INSERT INTO printer_pairs (token_id, pair_address) VALUES (?, ?)", (token_id, pair_addr))
        pair_id = conn.execute("SELECT id FROM printer_pairs WHERE pair_address = ?", (pair_addr,)).fetchone()["id"]
        return token_id, pair_id

    def _insert_snapshot(
        self,
        conn: sqlite3.Connection,
        token_id: int,
        pair_id: int,
        captured_at: str,
        price_usd: float,
        source_name: str,
        price_change_15m: float | None = None,
        extra_json: dict | None = None,
    ) -> int:
        json_payload: dict = {"price_usd": price_usd, "source_name": source_name,
                              "token_id": token_id, "pair_id": pair_id}
        if extra_json:
            json_payload.update(extra_json)
        conn.execute(
            """INSERT INTO printer_token_snapshots
               (token_id, pair_id, captured_at, tracking_lane, snapshot_mode,
                price_usd, liquidity_usd, source_status, data_quality_label,
                snapshot_quality_label, price_change_15m, normalized_snapshot_payload_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (token_id, pair_id, captured_at, "TRACK_FAST", "NORMAL_MODE",
             price_usd, 5000.0, "COMPLETE", "CLEAN_DATA", "CLEAN_SNAPSHOT",
             price_change_15m, json.dumps(json_payload)),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def test_tc23_provider_candle_derived_not_overwritten(self, tmp_path: Path):
        conn = self._make_db(tmp_path)
        token_id, pair_id = self._insert_token_pair(conn, "MINT_GUARD_TEST", "PAIR_GUARD_TEST")

        # Prior snapshot eligible for staged derivation (~900s before end)
        self._insert_snapshot(conn, token_id, pair_id, "2026-07-12T11:43:00+00:00", 0.0008, "dexscreener")

        # End snapshot has PROVIDER_CANDLE_DERIVED annotation: staged guard must block
        end_json = {
            "price_usd": 0.0015,
            "source_name": "dexscreener",
            "token_id": token_id,
            "pair_id": pair_id,
            "price_change_15m_source_kind": PROVIDER_CANDLE_DERIVED,
        }
        end_id = self._insert_snapshot(
            conn, token_id, pair_id, "2026-07-12T11:58:00+00:00", 0.0015, "dexscreener",
            price_change_15m=42.0,
            extra_json={"price_change_15m_source_kind": PROVIDER_CANDLE_DERIVED},
        )

        normalized = {
            "token_id": token_id,
            "pair_id": pair_id,
            "source_name": "dexscreener",
            "captured_at": "2026-07-12T11:58:00+00:00",
            "price_usd": 0.0015,
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
            "normalized_snapshot_payload_json": json.dumps(end_json),
        }
        result = apply_staged_derivation(conn, end_id, normalized)

        assert result is False

        row = conn.execute(
            "SELECT price_change_15m, normalized_snapshot_payload_json FROM printer_token_snapshots WHERE id = ?",
            (end_id,),
        ).fetchone()
        assert float(row[0]) == pytest.approx(42.0)  # DB column unchanged
        payload_json = json.loads(row[1])
        assert payload_json.get("price_change_15m_source_kind") == PROVIDER_CANDLE_DERIVED

    def test_tc24_staged_fallback_runs_when_no_source_kind(self, tmp_path: Path):
        """Staged derivation proceeds when no prior source annotation exists."""
        conn = self._make_db(tmp_path)
        token_id, pair_id = self._insert_token_pair(conn, "MINT_STAGED_FALLBACK", "PAIR_STAGED_FALLBACK")

        # Prior snapshot: 900s before end
        self._insert_snapshot(conn, token_id, pair_id, "2026-07-12T11:43:00+00:00", 0.001, "dexscreener")

        # End snapshot: no source_kind annotation → staged derivation should run
        end_json = {
            "price_usd": 0.0015,
            "source_name": "dexscreener",
            "token_id": token_id,
            "pair_id": pair_id,
        }
        end_id = self._insert_snapshot(
            conn, token_id, pair_id, "2026-07-12T11:58:00+00:00", 0.0015, "dexscreener",
        )
        normalized = {
            "token_id": token_id,
            "pair_id": pair_id,
            "source_name": "dexscreener",
            "captured_at": "2026-07-12T11:58:00+00:00",
            "price_usd": 0.0015,
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
            "normalized_snapshot_payload_json": json.dumps(end_json),
        }
        result = apply_staged_derivation(conn, end_id, normalized)
        assert result is True

        row = conn.execute(
            "SELECT price_change_15m, normalized_snapshot_payload_json FROM printer_token_snapshots WHERE id = ?",
            (end_id,),
        ).fetchone()
        assert row[0] is not None
        payload_json = json.loads(row[1])
        assert payload_json.get("price_change_15m_source_kind") == "DERIVED_STAGED_SNAPSHOT"


# ---------------------------------------------------------------------------
# TC-25: infrastructure token exclusions intact
# ---------------------------------------------------------------------------

class TestInfrastructureTokenExclusions:
    def test_tc25_wsol_address_excluded(self):
        from printer_v1.sources.geckoterminal import _normalize_geckoterminal_pool
        # WSOL as base token must return None
        pool = {
            "id": "solana_WSOL_POOL",
            "attributes": {
                "address": "WSOL_POOL",
                "base_token_address": "So11111111111111111111111111111111111111112",
                "base_token_price_usd": "0.05",
            },
        }
        assert _normalize_geckoterminal_pool(pool) is None

    def test_tc25b_usdc_official_address_excluded(self):
        from printer_v1.sources.geckoterminal import _normalize_geckoterminal_pool
        pool = {
            "id": "solana_USDC_POOL",
            "attributes": {
                "address": "USDC_POOL",
                "base_token_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "base_token_price_usd": "1.00",
            },
        }
        assert _normalize_geckoterminal_pool(pool) is None


# ---------------------------------------------------------------------------
# TC-26: no memory, position, trade, PnL rows
# ---------------------------------------------------------------------------

class TestNoFinancialRecords:
    def test_tc26_enrichment_creates_no_rows(self, tmp_path: Path):
        from printer_v1.db import apply_migrations
        db_path = tmp_path / "no_financial.db"
        apply_migrations(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Call both enrichment functions
        payload_ohlcv = _ohlcv_payload([_candle(_FRESH_CANDLE_START)])
        enrich_candidate_15m_ohlcv(
            payload_ohlcv, pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_OHLCV_URL, now=_NOW,
        )
        enrich_candidate_15m_trades(
            _trades_payload([_trade(_NOW_UNIX - 100)]),
            pool_address=_POOL_ADDRESS, network=_NETWORK,
            endpoint_url=_TRADES_URL, now=_NOW,
        )

        for table in (
            "printer_episodes",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
            "printer_paper_trade_audits",
        ):
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            assert row[0] == 0, f"Unexpected rows in {table}"


# ---------------------------------------------------------------------------
# TC-27: provenance annotations survive normalize_snapshot_payload passthrough
# ---------------------------------------------------------------------------

class TestProvenancePassthrough:
    def test_tc27_source_kind_survives_normalize(self):
        payload = {
            "token_id": 1,
            "pair_id": 1,
            "token_mint": "MINT_TEST",
            "pair_address": "PAIR_TEST",
            "captured_at": "2026-07-12T12:00:00+00:00",
            "tracking_lane": "TRACK_FAST",
            "snapshot_mode": "NORMAL_MODE",
            "price_usd": 0.001,
            "liquidity_usd": 5000.0,
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
            # Enrichment fields
            "price_change_15m": 20.0,
            "price_change_15m_source_kind": PROVIDER_CANDLE_DERIVED,
            "price_change_15m_provenance": {"source": "geckoterminal", "test": True},
            "volume_15m": 50000.0,
            "volume_15m_source_kind": PROVIDER_CANDLE_DERIVED,
            "txns_15m": 12,
            "txns_15m_source_kind": PROVIDER_TRADES_WINDOW,
            "txns_15m_completeness": TRADE_HISTORY_COMPLETE,
        }
        normalized = normalize_snapshot_payload(payload)
        assert normalized["price_change_15m_source_kind"] == PROVIDER_CANDLE_DERIVED
        assert normalized["volume_15m_source_kind"] == PROVIDER_CANDLE_DERIVED
        assert normalized["txns_15m_source_kind"] == PROVIDER_TRADES_WINDOW
        assert normalized["txns_15m_completeness"] == TRADE_HISTORY_COMPLETE
        assert isinstance(normalized["price_change_15m_provenance"], dict)
        assert normalized["price_change_15m"] == pytest.approx(20.0)
        assert normalized["volume_15m"] == pytest.approx(50000.0)
        assert normalized["txns_15m"] == 12


# ---------------------------------------------------------------------------
# Module constant contracts
# ---------------------------------------------------------------------------

class TestModuleConstants:
    def test_geckoterminal_source_name_is_geckoterminal(self):
        from printer_v1.sources.geckoterminal_15m import GT15M_SOURCE_NAME
        assert GT15M_SOURCE_NAME == "geckoterminal"

    def test_new_request_kinds_in_registry(self):
        from printer_v1.sources.registry import SOURCE_REGISTRY
        kinds = SOURCE_REGISTRY["geckoterminal"].allowed_request_kinds
        assert "geckoterminal_ohlcv_15m" in kinds
        assert "geckoterminal_pool_trades_15m" in kinds

    def test_new_request_kinds_in_adapter_allowed_set(self):
        from printer_v1.sources.geckoterminal import ALLOWED_REQUEST_KINDS
        assert "geckoterminal_ohlcv_15m" in ALLOWED_REQUEST_KINDS
        assert "geckoterminal_pool_trades_15m" in ALLOWED_REQUEST_KINDS

    def test_governor_approves_ohlcv_request_kind(self):
        from printer_v1.sources.governor import can_request_source
        decision = can_request_source("geckoterminal", "geckoterminal_ohlcv_15m", recent_request_count=0)
        assert decision.allowed is True

    def test_governor_approves_trades_request_kind(self):
        from printer_v1.sources.governor import can_request_source
        decision = can_request_source("geckoterminal", "geckoterminal_pool_trades_15m", recent_request_count=0)
        assert decision.allowed is True

    def test_url_templates_contain_network_and_pool(self):
        ohlcv_url = build_gt15m_ohlcv_url("TEST_POOL")
        trades_url = build_gt15m_trades_url("TEST_POOL")
        assert "solana" in ohlcv_url
        assert "TEST_POOL" in ohlcv_url
        assert "solana" in trades_url
        assert "TEST_POOL" in trades_url
        assert "aggregate=15" in ohlcv_url
        assert "trade_volume_in_usd_greater_than=0" in trades_url

    def test_candle_seconds_is_900(self):
        assert GT15M_CANDLE_SECONDS == 900

    def test_provider_candle_derived_label(self):
        assert PROVIDER_CANDLE_DERIVED == "PROVIDER_CANDLE_DERIVED"

    def test_trade_history_truncated_label(self):
        assert TRADE_HISTORY_TRUNCATED == "TRADE_HISTORY_TRUNCATED"

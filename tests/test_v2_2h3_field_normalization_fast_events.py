"""V2-2H.3 — Field Normalization and A1/A2/A3/A4 Repair.

Targeted unit tests for:
  A. Field normalization repairs (pair_created_at, price_change_*, age derivation)
  B. Known-vs-unknown field handling
  C. A1/A2/A3/A4 categorical fast-event differentiation repair
  D. Field completeness reporting hook

Locks preserved: no discovery runs, no source fetching, no live DB mutation,
no memory generation, no retrieval, no paper decisions, no BUY/SELL/HOLD,
no positions/trades/audits/PnL, no scoring/ranking/confidence/weighted logic.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.discovery.parser import (
    _parse_created_at,
    _safe_age_seconds,
    normalize_candidate,
    normalize_candidates,
)
from printer_v1.discovery.selection_batch import (
    BUCKET_A1,
    BUCKET_A2,
    BUCKET_A3,
    BUCKET_A4,
    BUCKET_NAMES,
    GROUP_A_BUCKETS,
    assign_bucket,
    build_field_completeness_report,
    derive_failed_pump_bucket,
)
from printer_v1.operator_cli.commands import build_discover_candidates_once_payload
from printer_v1.sources.geckoterminal import normalize_geckoterminal_payload


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

_SOLANA_WSOL = "So11111111111111111111111111111111111111112"
_FIXED_NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_1H_AGO = (_FIXED_NOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
_2H_AGO = (_FIXED_NOW - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
_6H_AGO = (_FIXED_NOW - timedelta(hours=6)).isoformat().replace("+00:00", "Z")
_25H_AGO = (_FIXED_NOW - timedelta(hours=25)).isoformat().replace("+00:00", "Z")
_FUTURE = (_FIXED_NOW + timedelta(hours=1)).isoformat().replace("+00:00", "Z")


def _dex_pair(
    *,
    pair_address: str = "test-pair-aaa",
    mint: str = "test-mint-aaa",
    liquidity: float = 8000.0,
    volume_5m: float = 2000.0,
    txns_5m: int = 20,
    price_change_5m: float | None = None,
    price_change_1h: float | None = None,
    price_change_24h: float | None = None,
    pair_created_at: str | int | None = None,
    token_created_at: str | None = None,
) -> dict:
    """Build a DexScreener-style already-flattened candidate dict."""
    d: dict = {
        "chainId": "solana",
        "pairAddress": pair_address,
        "baseToken": {"address": mint, "symbol": "TST", "name": "Test"},
        "quoteToken": {"address": _SOLANA_WSOL},
        "dexId": "raydium",
        "priceUsd": "0.001",
        "liquidity": {"usd": liquidity},
        "volume": {"m5": volume_5m, "h1": 5000.0, "h24": 20000.0},
        "txns": {
            "m5": {"buys": txns_5m // 2, "sells": txns_5m - txns_5m // 2},
            "h1": {"buys": 50, "sells": 30},
            "h24": {"buys": 200, "sells": 120},
        },
    }
    if price_change_5m is not None:
        d.setdefault("priceChange", {})["m5"] = price_change_5m
    if price_change_1h is not None:
        d.setdefault("priceChange", {})["h1"] = price_change_1h
    if price_change_24h is not None:
        d.setdefault("priceChange", {})["h24"] = price_change_24h
    if pair_created_at is not None:
        d["pair_created_at"] = pair_created_at
    if token_created_at is not None:
        d["token_created_at"] = token_created_at
    return d


def _candidate(**fields) -> dict:
    base = {
        "liquidity_usd": 8000.0,
        "volume_5m": 2000.0,
        "txns_5m": 20,
        "volume_1h": 5000.0,
        "volume_24h": 20000.0,
        "txns_1h": 80,
        "txns_24h": 320,
    }
    base.update(fields)
    return base


def _gt_pool(
    *,
    pool_address: str = "gt-pool-aaa",
    mint: str = "gt-mint-aaa",
    liquidity: float = 3000.0,
    pool_created_at: str | None = None,
    price_change_m5: str | None = None,
    price_change_h1: str | None = None,
    price_change_h24: str | None = None,
) -> dict:
    """Build a GeckoTerminal raw pool dict (not yet normalized by the adapter)."""
    attrs: dict = {
        "address": pool_address,
        "reserve_in_usd": str(liquidity),
        "volume_usd": {"m5": "50", "h1": "300", "h24": "1000"},
        "transactions": {"m5": 5, "h1": 20, "h24": 80},
    }
    if pool_created_at is not None:
        attrs["pool_created_at"] = pool_created_at
    if any(x is not None for x in (price_change_m5, price_change_h1, price_change_h24)):
        pc: dict = {}
        if price_change_m5 is not None:
            pc["m5"] = price_change_m5
        if price_change_h1 is not None:
            pc["h1"] = price_change_h1
        if price_change_h24 is not None:
            pc["h24"] = price_change_h24
        attrs["price_change_percentage"] = pc
    base_rel = {"data": {"id": f"solana_{mint}"}}
    return {
        "id": f"solana_{pool_address}",
        "attributes": attrs,
        "relationships": {"base_token": base_rel, "network": {"data": {"id": "solana"}}},
    }


def _gt_payload(pools: list[dict]) -> dict:
    return {"data": pools}


def _args_for_hook(**overrides) -> argparse.Namespace:
    base = {
        "project_root": str(PROJECT_ROOT),
        "format": "json",
        "no_color": True,
        "operator_approved": True,
        "chain": "solana",
        "max_candidates": 10,
        "query": "pump",
        "timeout_seconds": 5.0,
        "source_name": "dexscreener",
        "request_key": "v2-2h3-test",
        "db_path": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _pair_transport_factory(pairs: list[dict]):
    def _transport(context):
        del context
        return {"pairs": pairs}
    return _transport


# ---------------------------------------------------------------------------
# A. Field normalization — timestamp and age derivation helpers
# ---------------------------------------------------------------------------

class TestParseCreatedAt(unittest.TestCase):

    def test_iso_string_parsed_to_utc(self):
        dt = _parse_created_at("2024-06-01T10:00:00Z")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_iso_string_with_offset(self):
        dt = _parse_created_at("2024-06-01T10:00:00+00:00")
        self.assertIsNotNone(dt)

    def test_epoch_ms_integer(self):
        # DexScreener pairCreatedAt is epoch-ms
        epoch_ms = 1_717_228_800_000  # 2024-06-01 12:00:00 UTC
        dt = _parse_created_at(epoch_ms)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2024)

    def test_epoch_s_integer(self):
        epoch_s = 1_717_228_800  # 2024-06-01 12:00:00 UTC (10 digits, <1e10)
        dt = _parse_created_at(epoch_s)
        self.assertIsNotNone(dt)

    def test_none_returns_none(self):
        self.assertIsNone(_parse_created_at(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(_parse_created_at(""))

    def test_invalid_string_returns_none(self):
        self.assertIsNone(_parse_created_at("not-a-date"))

    def test_garbage_type_returns_none(self):
        self.assertIsNone(_parse_created_at({"bad": "data"}))


class TestSafeAgeSeconds(unittest.TestCase):

    def test_age_computed_correctly_from_iso(self):
        created_at = (_FIXED_NOW - timedelta(hours=2)).isoformat()
        age = _safe_age_seconds(created_at, _FIXED_NOW)
        self.assertIsNotNone(age)
        self.assertAlmostEqual(age, 7200.0, delta=1.0)

    def test_future_timestamp_returns_none(self):
        future = (_FIXED_NOW + timedelta(seconds=10)).isoformat()
        self.assertIsNone(_safe_age_seconds(future, _FIXED_NOW))

    def test_none_created_at_returns_none(self):
        self.assertIsNone(_safe_age_seconds(None, _FIXED_NOW))

    def test_zero_age_at_exact_match(self):
        age = _safe_age_seconds(_FIXED_NOW.isoformat(), _FIXED_NOW)
        self.assertIsNotNone(age)
        self.assertAlmostEqual(age, 0.0, delta=0.001)

    def test_future_does_not_produce_fresh_age(self):
        future = (_FIXED_NOW + timedelta(hours=1)).isoformat()
        result = _safe_age_seconds(future, _FIXED_NOW)
        self.assertIsNone(result)
        self.assertNotEqual(result, 0.0)


# ---------------------------------------------------------------------------
# A. Field normalization — normalize_candidate with new fields
# ---------------------------------------------------------------------------

class TestNormalizeCandidateNewFields(unittest.TestCase):

    def test_pair_created_at_preserved_from_flat_key(self):
        pair = _dex_pair(pair_created_at=_2H_AGO)
        result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
        self.assertEqual(result["pair_created_at"], _2H_AGO)

    def test_pair_created_at_absent_when_not_in_source(self):
        pair = _dex_pair()  # no pair_created_at
        result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
        self.assertIsNone(result["pair_created_at"])

    def test_pair_age_seconds_derived_from_pair_created_at(self):
        pair = _dex_pair(pair_created_at=_2H_AGO)
        result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
        self.assertIsNotNone(result["pair_age_seconds"])
        self.assertAlmostEqual(result["pair_age_seconds"], 7200.0, delta=2.0)

    def test_pair_age_seconds_none_when_pair_created_at_missing(self):
        pair = _dex_pair()
        result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
        self.assertIsNone(result["pair_age_seconds"])

    def test_future_pair_created_at_returns_none_not_fresh(self):
        pair = _dex_pair(pair_created_at=_FUTURE)
        result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
        self.assertIsNone(result["pair_age_seconds"])
        self.assertNotEqual(result.get("pair_age_seconds"), 0.0)

    def test_token_age_seconds_derived_from_token_created_at(self):
        pair = _dex_pair(token_created_at=_6H_AGO)
        result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
        self.assertIsNotNone(result["token_age_seconds"])
        self.assertAlmostEqual(result["token_age_seconds"], 21600.0, delta=2.0)

    def test_token_age_seconds_none_when_token_created_at_missing(self):
        pair = _dex_pair()
        result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
        self.assertIsNone(result["token_age_seconds"])

    def test_price_change_5m_preserved_from_pricechange_nested(self):
        pair = _dex_pair(price_change_5m=-25.0)
        result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
        self.assertIsNotNone(result["price_change_5m"])
        self.assertAlmostEqual(result["price_change_5m"], -25.0)

    def test_price_change_5m_absent_when_not_in_source(self):
        pair = _dex_pair()  # no priceChange
        result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
        self.assertIsNone(result["price_change_5m"])

    def test_price_change_confirmed_zero_preserved_not_dropped(self):
        pair = _dex_pair(price_change_5m=0.0)
        # Inject the zero explicitly into the raw payload's flat form
        pair["price_change_5m"] = 0.0
        result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
        # The nested key_path ("price_change_5m",) picks up the flat 0.0 value.
        # nested_value() skips None/empty but NOT 0.0, so 0.0 must be preserved.
        # This test verifies the H.3 spec: confirmed zero != missing.
        # Note: priceChange.m5 = 0.0 is checked via the priceChange dict path.
        self.assertIsNotNone(result.get("price_change_5m"))

    def test_price_change_1h_captured(self):
        pair = _dex_pair(price_change_1h=-5.0)
        result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
        self.assertAlmostEqual(result["price_change_1h"], -5.0)

    def test_price_change_24h_captured(self):
        pair = _dex_pair(price_change_24h=120.0)
        result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
        self.assertAlmostEqual(result["price_change_24h"], 120.0)

    def test_volume_15m_remains_none_from_standard_source(self):
        # Neither DexScreener nor GeckoTerminal expose 15m volume; must remain None
        pair = _dex_pair()
        result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
        self.assertIsNone(result["volume_15m"])

    def test_existing_fields_still_present(self):
        pair = _dex_pair(pair_created_at=_2H_AGO)
        result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
        for field in ("token_mint", "pair_address", "chain", "liquidity_usd", "volume_5m"):
            with self.subTest(field=field):
                self.assertIn(field, result)


# ---------------------------------------------------------------------------
# A. Field normalization — GeckoTerminal adapter extraction
# ---------------------------------------------------------------------------

class TestGeckoTerminalFieldExtraction(unittest.TestCase):

    def test_pair_created_at_captured_from_pool_created_at(self):
        pool = _gt_pool(pool_created_at=_2H_AGO)
        result = normalize_geckoterminal_payload(
            _gt_payload([pool]), request_kind="geckoterminal_new_pool_discovery"
        )
        self.assertEqual(result.source_status.value, "COMPLETE")
        pairs = result.normalized_payload["pairs"]
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].get("pair_created_at"), _2H_AGO)

    def test_pair_created_at_none_when_pool_created_at_missing(self):
        pool = _gt_pool()  # no pool_created_at
        result = normalize_geckoterminal_payload(
            _gt_payload([pool]), request_kind="geckoterminal_new_pool_discovery"
        )
        pairs = result.normalized_payload["pairs"]
        self.assertIsNone(pairs[0].get("pair_created_at"))

    def test_price_change_5m_captured_from_price_change_percentage(self):
        pool = _gt_pool(price_change_m5="-12.5")
        result = normalize_geckoterminal_payload(
            _gt_payload([pool]), request_kind="geckoterminal_new_pool_discovery"
        )
        pairs = result.normalized_payload["pairs"]
        self.assertAlmostEqual(pairs[0].get("price_change_5m"), -12.5)

    def test_price_change_h1_captured(self):
        pool = _gt_pool(price_change_h1="8.3")
        result = normalize_geckoterminal_payload(
            _gt_payload([pool]), request_kind="geckoterminal_new_pool_discovery"
        )
        pairs = result.normalized_payload["pairs"]
        self.assertAlmostEqual(pairs[0].get("price_change_1h"), 8.3)

    def test_price_change_absent_when_not_in_payload(self):
        pool = _gt_pool()  # no price_change_percentage
        result = normalize_geckoterminal_payload(
            _gt_payload([pool]), request_kind="geckoterminal_new_pool_discovery"
        )
        pairs = result.normalized_payload["pairs"]
        self.assertIsNone(pairs[0].get("price_change_5m"))

    def test_geckoterminal_fields_flow_through_normalize_candidates(self):
        pool = _gt_pool(
            pool_created_at=_2H_AGO,
            price_change_m5="-20.5",
            price_change_h1="-3.2",
        )
        gt_result = normalize_geckoterminal_payload(
            _gt_payload([pool]), request_kind="geckoterminal_new_pool_discovery"
        )
        payload = dict(gt_result.normalized_payload)
        candidates = normalize_candidates("geckoterminal", payload, now=_FIXED_NOW)
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertIsNotNone(c["pair_created_at"])
        self.assertAlmostEqual(c["price_change_5m"], -20.5)
        self.assertAlmostEqual(c["price_change_1h"], -3.2)
        self.assertIsNotNone(c["pair_age_seconds"])
        self.assertAlmostEqual(c["pair_age_seconds"], 7200.0, delta=5.0)


# ---------------------------------------------------------------------------
# B. Known-vs-unknown field handling
# ---------------------------------------------------------------------------

class TestKnownVsUnknownFields(unittest.TestCase):

    def test_missing_price_change_5m_not_treated_as_zero(self):
        # A candidate with no price_change_5m should have None, not 0.0
        pair = _dex_pair()
        result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
        self.assertIsNone(result["price_change_5m"])
        self.assertIsNot(result["price_change_5m"], 0.0)

    def test_explicit_zero_price_change_5m_is_valid_known_value(self):
        pair = _dex_pair()
        pair["price_change_5m"] = 0.0  # confirmed zero flat key
        result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
        # 0.0 is a valid confirmed value, not the same as missing
        self.assertIsNotNone(result.get("price_change_5m"))

    def test_missing_token_age_not_treated_as_fresh(self):
        # Missing token_age_seconds must be None, not 0 (which would look fresh)
        pair = _dex_pair()
        result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
        self.assertIsNone(result["token_age_seconds"])

    def test_missing_volume_15m_is_none_not_zero(self):
        pair = _dex_pair()
        result = normalize_candidate("dexscreener", pair, now=_FIXED_NOW)
        self.assertIsNone(result["volume_15m"])


# ---------------------------------------------------------------------------
# C. A1/A2/A3/A4 categorical repair
# ---------------------------------------------------------------------------

class TestAssignBucketA1A2A3(unittest.TestCase):

    def test_a1_fires_for_fast_pump_follow_through(self):
        c = _candidate(liquidity_usd=8000, volume_5m=2000)
        bucket, name = assign_bucket(c)
        self.assertEqual(bucket, BUCKET_A1)
        self.assertEqual(name, BUCKET_NAMES[BUCKET_A1])

    def test_a2_fires_with_known_price_change_5m(self):
        c = _candidate(
            liquidity_usd=8000, volume_5m=2000,
            price_change_5m=-25.0,
        )
        bucket, _ = assign_bucket(c)
        self.assertEqual(bucket, BUCKET_A2)

    def test_a2_does_not_fire_when_price_change_5m_missing(self):
        # price_change_5m=None → must not assume -25%; falls to A1
        c = _candidate(liquidity_usd=8000, volume_5m=2000)
        c.pop("price_change_5m", None)
        bucket, _ = assign_bucket(c)
        self.assertEqual(bucket, BUCKET_A1)

    def test_a2_does_not_fire_when_price_change_5m_explicitly_none(self):
        c = _candidate(liquidity_usd=8000, volume_5m=2000, price_change_5m=None)
        bucket, _ = assign_bucket(c)
        self.assertEqual(bucket, BUCKET_A1)

    def test_a2_does_not_fire_for_known_zero_price_change(self):
        # Confirmed zero price_change is not a wick reversal → A1
        c = _candidate(liquidity_usd=8000, volume_5m=2000, price_change_5m=0.0)
        bucket, _ = assign_bucket(c)
        self.assertEqual(bucket, BUCKET_A1)

    def test_a3_fires_with_known_age_and_known_price_change_1h(self):
        c = _candidate(
            liquidity_usd=8000, txns_5m=15,
            token_age_seconds=7200.0,  # 2 hours old
            price_change_1h=-5.0,
        )
        bucket, _ = assign_bucket(c)
        self.assertEqual(bucket, BUCKET_A3)

    def test_a3_does_not_fire_when_token_age_missing(self):
        c = _candidate(
            liquidity_usd=8000, txns_5m=15,
            price_change_1h=-5.0,
        )
        c.pop("token_age_seconds", None)
        bucket, _ = assign_bucket(c)
        self.assertEqual(bucket, BUCKET_A1)

    def test_a3_does_not_fire_when_price_change_1h_missing(self):
        c = _candidate(
            liquidity_usd=8000, txns_5m=15,
            token_age_seconds=7200.0,
        )
        c.pop("price_change_1h", None)
        bucket, _ = assign_bucket(c)
        self.assertEqual(bucket, BUCKET_A1)

    def test_a3_does_not_fire_when_token_age_too_young(self):
        # Age < 3600s (1 hour) → not a late-buy trap
        c = _candidate(
            liquidity_usd=8000, txns_5m=15,
            token_age_seconds=1800.0,
            price_change_1h=-5.0,
        )
        bucket, _ = assign_bucket(c)
        self.assertEqual(bucket, BUCKET_A1)

    def test_a3_does_not_fire_when_price_change_1h_positive(self):
        c = _candidate(
            liquidity_usd=8000, txns_5m=15,
            token_age_seconds=7200.0,
            price_change_1h=5.0,  # positive — not a late-buy-trap signal
        )
        bucket, _ = assign_bucket(c)
        self.assertEqual(bucket, BUCKET_A1)

    def test_bucket_labels_are_categorical_strings(self):
        for bucket_id, bucket_name in (
            (BUCKET_A1, BUCKET_NAMES[BUCKET_A1]),
            (BUCKET_A2, BUCKET_NAMES[BUCKET_A2]),
            (BUCKET_A3, BUCKET_NAMES[BUCKET_A3]),
            (BUCKET_A4, BUCKET_NAMES[BUCKET_A4]),
        ):
            with self.subTest(bucket=bucket_id):
                self.assertIsInstance(bucket_id, str)
                self.assertIsInstance(bucket_name, str)
                self.assertNotIsInstance(bucket_id, (int, float))


class TestDeriveFailedPumpBucket(unittest.TestCase):

    def _prior_a1(self) -> dict:
        return {"primary_bucket": BUCKET_A1}

    def _current_not_fast(self) -> dict:
        return {
            "liquidity_usd": 2000.0,  # below fast threshold (5000)
            "volume_5m": 50.0,
            "txns_5m": 2,
        }

    def test_a4_fires_with_prior_a1_and_current_not_fast(self):
        result = derive_failed_pump_bucket(self._current_not_fast(), self._prior_a1())
        self.assertIsNotNone(result)
        bucket, name = result
        self.assertEqual(bucket, BUCKET_A4)
        self.assertEqual(name, BUCKET_NAMES[BUCKET_A4])

    def test_a4_fires_with_prior_a2(self):
        result = derive_failed_pump_bucket(
            self._current_not_fast(), {"primary_bucket": BUCKET_A2}
        )
        self.assertIsNotNone(result)
        self.assertEqual(result[0], BUCKET_A4)

    def test_a4_fires_with_prior_a3(self):
        result = derive_failed_pump_bucket(
            self._current_not_fast(), {"primary_bucket": BUCKET_A3}
        )
        self.assertIsNotNone(result)
        self.assertEqual(result[0], BUCKET_A4)

    def test_a4_does_not_fire_without_prior_a_tier(self):
        # Prior was B5 (consolidation) — not an A-tier → no failed pump
        result = derive_failed_pump_bucket(
            self._current_not_fast(), {"primary_bucket": "B5"}
        )
        self.assertIsNone(result)

    def test_a4_does_not_fire_when_missing_prior_bucket(self):
        result = derive_failed_pump_bucket(self._current_not_fast(), {})
        self.assertIsNone(result)

    def test_a4_does_not_fire_when_current_still_fast_tier(self):
        still_fast = {
            "liquidity_usd": 6000.0,
            "volume_5m": 2000.0,
            "txns_5m": 15,
        }
        result = derive_failed_pump_bucket(still_fast, self._prior_a1())
        self.assertIsNone(result)

    def test_a4_does_not_fire_when_liquidity_removed(self):
        # Liquidity <= 500 → C3, not A4
        liq_removed = {
            "liquidity_usd": 300.0,
            "volume_5m": 0.0,
            "txns_5m": 0,
        }
        result = derive_failed_pump_bucket(liq_removed, self._prior_a1())
        self.assertIsNone(result)

    def test_a4_return_type_is_tuple_of_strings(self):
        result = derive_failed_pump_bucket(self._current_not_fast(), self._prior_a1())
        self.assertIsNotNone(result)
        bucket, name = result
        self.assertIsInstance(bucket, str)
        self.assertIsInstance(name, str)

    def test_a4_bucket_is_in_group_a(self):
        result = derive_failed_pump_bucket(self._current_not_fast(), self._prior_a1())
        self.assertIsNotNone(result)
        self.assertIn(result[0], GROUP_A_BUCKETS)


# ---------------------------------------------------------------------------
# D. Field completeness reporting
# ---------------------------------------------------------------------------

class TestBuildFieldCompletenessReport(unittest.TestCase):

    def _all_missing(self) -> dict:
        return {"token_mint": "mint-x", "pair_address": "pair-x"}

    def _all_present(self) -> dict:
        return {
            "token_mint": "mint-x",
            "pair_address": "pair-x",
            "token_created_at": "2024-01-01T00:00:00Z",
            "pair_created_at": "2024-01-01T00:00:00Z",
            "token_age_seconds": 3600.0,
            "pair_age_seconds": 3600.0,
            "price_change_5m": 2.5,
            "price_change_15m": 1.2,
            "price_change_1h": -3.0,
            "price_change_24h": 50.0,
            "volume_15m": 250.0,
        }

    def test_empty_list_returns_zero_counts(self):
        report = build_field_completeness_report([])
        self.assertEqual(report["total_candidates"], 0)
        for key, val in report.items():
            if key != "total_candidates":
                self.assertEqual(val, 0)

    def test_all_missing_counts_all_as_missing(self):
        report = build_field_completeness_report([self._all_missing()])
        for field in (
            "token_created_at", "pair_created_at", "token_age_seconds",
            "pair_age_seconds", "price_change_5m", "price_change_15m",
            "price_change_1h", "price_change_24h", "volume_15m",
        ):
            with self.subTest(field=field):
                self.assertEqual(report[f"missing_{field}_count"], 1)

    def test_all_present_counts_zero_missing(self):
        report = build_field_completeness_report([self._all_present()])
        for field in (
            "token_created_at", "pair_created_at", "token_age_seconds",
            "pair_age_seconds", "price_change_5m", "price_change_15m",
            "price_change_1h", "price_change_24h", "volume_15m",
        ):
            with self.subTest(field=field):
                self.assertEqual(report[f"missing_{field}_count"], 0)

    def test_all_expected_keys_present(self):
        report = build_field_completeness_report([])
        expected = {
            "total_candidates", "missing_token_created_at_count",
            "missing_pair_created_at_count", "missing_token_age_seconds_count",
            "missing_pair_age_seconds_count", "missing_price_change_5m_count",
            "missing_price_change_15m_count", "missing_price_change_1h_count",
            "missing_price_change_24h_count", "missing_volume_15m_count",
        }
        self.assertEqual(set(report.keys()), expected)

    def test_counts_are_ints(self):
        report = build_field_completeness_report([self._all_missing()])
        for val in report.values():
            with self.subTest(value=val):
                self.assertIsInstance(val, int)
                self.assertNotIsInstance(val, bool)

    def test_mixed_missing_counted_correctly(self):
        candidates = [
            self._all_missing(),  # all 9 fields missing
            self._all_present(),  # none missing
        ]
        report = build_field_completeness_report(candidates)
        self.assertEqual(report["total_candidates"], 2)
        self.assertEqual(report["missing_price_change_5m_count"], 1)
        self.assertEqual(report["missing_pair_created_at_count"], 1)


class TestFieldCompletenessHookInPayload(unittest.TestCase):

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._temp_dir.cleanup)
        self.db_path = pathlib.Path(self._temp_dir.name) / "v2-2h3-hook.sqlite3"
        apply_migrations(self.db_path)

    def _run_args(self, **overrides):
        base = _args_for_hook(db_path=str(self.db_path))
        for k, v in overrides.items():
            setattr(base, k, v)
        return base

    def _two_pair_transport(self, context):
        del context
        return {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": "h3-pair-1",
                    "baseToken": {"address": "h3-mint-1", "symbol": "H3A", "name": "H3 One"},
                    "quoteToken": {"address": _SOLANA_WSOL},
                    "dexId": "raydium",
                    "priceUsd": "0.001",
                    "liquidity": {"usd": 8000},
                    "volume": {"m5": 2500, "h1": 12000, "h24": 50000},
                    "txns": {"m5": {"buys": 8, "sells": 6}, "h1": {"buys": 40, "sells": 25}},
                },
            ]
        }

    def test_field_completeness_report_present_in_payload(self):
        payload = build_discover_candidates_once_payload(
            self._run_args(), transport=self._two_pair_transport
        )
        self.assertIn("field_completeness_report", payload)

    def test_field_completeness_report_has_expected_keys(self):
        payload = build_discover_candidates_once_payload(
            self._run_args(), transport=self._two_pair_transport
        )
        report = payload["field_completeness_report"]
        for key in (
            "total_candidates", "missing_price_change_5m_count",
            "missing_pair_created_at_count", "missing_token_age_seconds_count",
        ):
            self.assertIn(key, report)

    def test_field_completeness_counts_are_ints(self):
        payload = build_discover_candidates_once_payload(
            self._run_args(), transport=self._two_pair_transport
        )
        report = payload["field_completeness_report"]
        for val in report.values():
            self.assertIsInstance(val, int)

    def test_h1_candidate_stage_report_invariant_still_preserved(self):
        # H.3 additions must not pollute candidate_stage_report
        payload = build_discover_candidates_once_payload(
            self._run_args(), transport=self._two_pair_transport
        )
        for key, val in payload["candidate_stage_report"].items():
            with self.subTest(key=key):
                self.assertTrue(
                    isinstance(val, int) or val == "NOT_MEASURED",
                    f"candidate_stage_report[{key!r}] must be int or NOT_MEASURED",
                )


if __name__ == "__main__":
    unittest.main()

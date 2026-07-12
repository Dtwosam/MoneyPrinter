"""DexScreener fresh-listing discovery vector (token-profiles -> tokens batch).

Stage 1 of the fresh-discovery / PumpSwap lane. The fresh vector surfaces
recently listed Solana memecoins instead of the popular-token repeats returned
by the text-match search endpoint, while preserving all existing categorical
filters (Solana-only, infrastructure-mint exclusion, dedup).

  FP-01  transport returns a {"pairs": [...]} payload from profiles + tokens
  FP-02  non-Solana profiles are filtered before the batch token lookup
  FP-03  no Solana profiles -> fails closed (dexscreener_no_solana_profiles)
  FP-04  profiles HTTP 429 -> rate_limited payload
  FP-05  tokens batch malformed -> fails closed
  FP-06  end-to-end: fresh payload -> normalizer keeps Solana memecoin, excludes infra
  FP-07  duplicate profile addresses de-duplicated before batch lookup
  FP-08  max_tokens cap is bounded to <= 30
  FP-09  catalog + channel + registry wiring for dexscreener_fresh_profiles
  FP-10  no score/rank/confidence field is introduced by the fresh vector

No live fetching (HTTP mocked), no DB mutation, memory, retrieval, paper
decisions, positions, trades, audits, or PnL.
"""

from __future__ import annotations

import pathlib
import sys
from urllib import error as url_error

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.sources import dexscreener as dx
from printer_v1.sources.dexscreener import (
    DEXSCREENER_SOURCE_NAME,
    _DEXSCREENER_FRESH_PROFILES_MAX_TOKENS,
    build_dexscreener_fresh_profiles_transport,
    normalize_dexscreener_fixture_result,
)

WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def _profile(chain, addr):
    return {"chainId": chain, "tokenAddress": addr, "updatedAt": 1, "url": "x", "description": "d"}


def _pair(chain, pair_addr, base_mint, symbol="MEME", liq=12000.0):
    return {
        "chainId": chain,
        "pairAddress": pair_addr,
        "baseToken": {"address": base_mint, "symbol": symbol, "name": f"{symbol} T"},
        "priceUsd": "0.001",
        "liquidity": {"usd": liq},
        "volume": {"m5": 400.0, "h1": 1000.0, "h24": 5000.0},
        "txns": {"m5": {"buys": 6, "sells": 3}, "h1": {"buys": 15, "sells": 8}},
        "priceChange": {"m5": 2.0, "h1": 8.0},
        "pairCreatedAt": 1_783_800_000_000,
    }


class _FakeHTTP:
    """Routes mocked GETs by URL substring."""

    def __init__(self, profiles=None, tokens=None, raise_on=None):
        self.profiles = profiles
        self.tokens = tokens
        self.raise_on = raise_on or {}
        self.calls = []

    def __call__(self, endpoint, timeout_seconds):
        self.calls.append(endpoint)
        for key, exc in self.raise_on.items():
            if key in endpoint:
                raise exc
        if "token-profiles" in endpoint:
            return self.profiles
        if "/tokens/v1/" in endpoint:
            return self.tokens
        raise AssertionError(f"unexpected endpoint {endpoint}")


def _run(monkeypatch, fake, **kw):
    monkeypatch.setattr(dx, "_dexscreener_http_get_json", fake)
    transport = build_dexscreener_fresh_profiles_transport(**kw)
    return transport(None)


class TestFreshProfilesTransport:
    def test_fp01_returns_pairs_payload(self, monkeypatch):
        fake = _FakeHTTP(
            profiles=[_profile("solana", "MintA1"), _profile("solana", "MintB2")],
            tokens=[_pair("solana", "PairA", "MintA1"), _pair("solana", "PairB", "MintB2")],
        )
        payload = _run(monkeypatch, fake)
        assert "pairs" in payload
        assert len(payload["pairs"]) == 2
        assert payload["_fresh_profiles_solana_count"] == 2

    def test_fp02_non_solana_profiles_filtered(self, monkeypatch):
        fake = _FakeHTTP(
            profiles=[_profile("ethereum", "EthX"), _profile("solana", "MintA1"), _profile("robinhood", "RhX")],
            tokens=[_pair("solana", "PairA", "MintA1")],
        )
        _run(monkeypatch, fake)
        # The batch call must only include the Solana mint.
        tokens_call = [c for c in fake.calls if "/tokens/v1/" in c][0]
        assert "MintA1" in tokens_call
        assert "EthX" not in tokens_call and "RhX" not in tokens_call

    def test_fp03_no_solana_profiles_fails_closed(self, monkeypatch):
        fake = _FakeHTTP(profiles=[_profile("ethereum", "EthX")], tokens=[])
        payload = _run(monkeypatch, fake)
        assert payload["fixture_status"] == "failure"
        assert payload["failure_type"] == "dexscreener_no_solana_profiles"
        # No batch token call should have been made.
        assert not any("/tokens/v1/" in c for c in fake.calls)

    def test_fp04_profiles_429_rate_limited(self, monkeypatch):
        err = url_error.HTTPError("u", 429, "Too Many Requests", {}, None)
        fake = _FakeHTTP(raise_on={"token-profiles": err})
        payload = _run(monkeypatch, fake)
        assert payload["fixture_status"] == "rate_limited"

    def test_fp05_tokens_malformed_fails_closed(self, monkeypatch):
        fake = _FakeHTTP(profiles=[_profile("solana", "MintA1")], tokens={"not": "a list"})
        payload = _run(monkeypatch, fake)
        assert payload["fixture_status"] == "failure"
        assert payload["failure_type"] == "dexscreener_tokens_malformed"

    def test_fp07_duplicate_profile_addresses_deduped(self, monkeypatch):
        fake = _FakeHTTP(
            profiles=[_profile("solana", "MintA1"), _profile("solana", "MintA1"), _profile("solana", "MintB2")],
            tokens=[_pair("solana", "PairA", "MintA1")],
        )
        _run(monkeypatch, fake)
        tokens_call = [c for c in fake.calls if "/tokens/v1/" in c][0]
        # MintA1 appears once, not twice.
        assert tokens_call.count("MintA1") == 1

    def test_fp08_max_tokens_cap_bounded(self, monkeypatch):
        profiles = [_profile("solana", f"Mint{i:02d}") for i in range(50)]
        fake = _FakeHTTP(profiles=profiles, tokens=[_pair("solana", "PairA", "Mint00")])
        _run(monkeypatch, fake, max_tokens=999)
        tokens_call = [c for c in fake.calls if "/tokens/v1/" in c][0]
        addrs = tokens_call.rsplit("/", 1)[-1].split(",")
        assert len(addrs) <= _DEXSCREENER_FRESH_PROFILES_MAX_TOKENS


class TestFreshVectorNormalization:
    def test_fp06_end_to_end_keeps_memecoin_excludes_infra(self, monkeypatch):
        fake = _FakeHTTP(
            profiles=[_profile("solana", "MemeMint"), _profile("solana", WSOL)],
            tokens=[
                _pair("solana", "PairMeme", "MemeMint", symbol="MEME"),
                _pair("solana", "PairWsol", WSOL, symbol="WSOL"),
                _pair("ethereum", "PairEth", "EthMint", symbol="ETHX"),
            ],
        )
        payload = _run(monkeypatch, fake)
        result = normalize_dexscreener_fixture_result(dict(payload), request_kind="dexscreener_fresh_profiles")
        assert result.source_status == SourceStatus.COMPLETE
        assert result.data_quality_label == DataQualityLabel.CLEAN_DATA
        kept = result.normalized_payload["pairs"]
        assert [k["token_mint"] for k in kept] == ["MemeMint"]
        reasons = {e["exclusion_reason"] for e in result.normalized_payload["excluded_pairs"]}
        assert "infrastructure_quote_mint" in reasons
        assert "non_solana_pair" in reasons

    def test_fp10_no_score_or_rank_field(self, monkeypatch):
        fake = _FakeHTTP(profiles=[_profile("solana", "MemeMint")], tokens=[_pair("solana", "P", "MemeMint")])
        payload = _run(monkeypatch, fake)
        result = normalize_dexscreener_fixture_result(dict(payload), request_kind="dexscreener_fresh_profiles")
        blob = repr(result.normalized_payload).lower()
        for banned in ("score", "rank", "confidence", "weight", "boost", "probability"):
            assert banned not in blob


class TestWiring:
    def test_fp09_catalog_channel_registry_wired(self):
        from printer_v1.operator_cli.commands import (
            _SOURCE_REQUEST_PLAN_CATALOG,
            _PLAN_STATUS_READY,
            _source_channel_for_dexscreener,
        )
        from printer_v1.discovery.contracts import DiscoveryChannelLabel
        from printer_v1.sources import SOURCE_REGISTRY

        entries = dict(_SOURCE_REQUEST_PLAN_CATALOG["dexscreener"])
        assert entries["dexscreener_fresh_profiles"] == _PLAN_STATUS_READY
        channel, reason = _source_channel_for_dexscreener("dexscreener_fresh_profiles")
        assert channel == DiscoveryChannelLabel.DEXSCREENER_LATEST_PROFILES.value
        assert reason == "dexscreener_latest_profiles_fresh_vector"
        assert "dexscreener_fresh_profiles" in SOURCE_REGISTRY["dexscreener"].allowed_request_kinds

"""DexScreener productivity repair — categorical exclusion filters.

Stage 2 of the source-productivity mini-sprint. Verifies that
normalize_dexscreener_fixture_result excludes, before emitting any candidate:

  DR-01  non-Solana pairs (reason non_solana_pair)
  DR-02  infrastructure quote-mints WSOL/USDC/USDT (reason infrastructure_quote_mint)
  DR-03  pairs missing pair_address or token_mint identity
  DR-04  a real Solana memecoin pair is retained
  DR-05  excluded_pairs audit trail is present and reasoned (never silent)
  DR-06  a response of only infrastructure/non-Solana pairs -> FAILED
  DR-07  mixed response keeps only the Solana memecoin, excludes the rest
  DR-08  retained candidate flows through normalize_candidates to selection metadata
  DR-09  exclusion is categorical only (no scores/ranks/confidence fields added)

No live source fetching, DB mutation, memory generation, retrieval, paper
decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.sources.dexscreener import (
    DEXSCREENER_SOURCE_NAME,
    _SOLANA_INFRASTRUCTURE_MINTS,
    normalize_dexscreener_fixture_result,
)

WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"

_MEME_MINT = "MEmeMint1111111111111111111111111111111111p"
_MEME_PAIR = "MEmePair1111111111111111111111111111111111p"


def _pair(chain_id, pair_address, base_mint, *, symbol="MEME", liq=12000.0):
    return {
        "chainId": chain_id,
        "pairAddress": pair_address,
        "baseToken": {"address": base_mint, "symbol": symbol, "name": f"{symbol} Token"},
        "priceUsd": "0.0011",
        "liquidity": {"usd": liq},
        "volume": {"m5": 500.0, "h1": 1200.0, "h24": 8000.0},
        "txns": {"m5": {"buys": 8, "sells": 4}, "h1": {"buys": 20, "sells": 10}},
        "priceChange": {"m5": 3.0, "h1": 12.0},
        "pairCreatedAt": 1_760_000_000_000,
    }


def _real_meme_pair():
    return _pair("solana", _MEME_PAIR, _MEME_MINT, symbol="MEME")


def _norm(pairs):
    return normalize_dexscreener_fixture_result({"pairs": pairs}, request_kind="token_discovery")


class TestExclusionFilters:
    def test_dr01_non_solana_pair_excluded(self):
        result = _norm([
            _real_meme_pair(),
            _pair("ethereum", "EthPair11111111", "EthMint11111111"),
        ])
        assert result.source_status == SourceStatus.COMPLETE
        kept = result.normalized_payload["pairs"]
        assert len(kept) == 1
        assert kept[0]["token_mint"] == _MEME_MINT
        excluded = result.normalized_payload["excluded_pairs"]
        assert any(e["exclusion_reason"] == "non_solana_pair" for e in excluded)

    @pytest.mark.parametrize("infra_mint", [WSOL, USDC, USDT])
    def test_dr02_infrastructure_base_mint_excluded(self, infra_mint):
        result = _norm([
            _real_meme_pair(),
            _pair("solana", "InfraPair1111111", infra_mint, symbol="WSOL"),
        ])
        kept = result.normalized_payload["pairs"]
        assert [k["token_mint"] for k in kept] == [_MEME_MINT]
        excluded = result.normalized_payload["excluded_pairs"]
        assert any(
            e["exclusion_reason"] == "infrastructure_quote_mint" and e["token_mint"] == infra_mint
            for e in excluded
        )

    def test_dr02b_all_three_infra_mints_are_in_exclusion_set(self):
        assert _SOLANA_INFRASTRUCTURE_MINTS == frozenset({WSOL, USDC, USDT})

    def test_dr03_missing_identity_excluded(self):
        no_mint = _pair("solana", "PairNoMint11111", "")
        no_mint["baseToken"]["address"] = None
        result = _norm([_real_meme_pair(), no_mint])
        kept = result.normalized_payload["pairs"]
        assert [k["token_mint"] for k in kept] == [_MEME_MINT]
        excluded = result.normalized_payload["excluded_pairs"]
        assert any(e["exclusion_reason"] == "missing_pair_or_mint_identity" for e in excluded)

    def test_dr04_real_memecoin_retained(self):
        result = _norm([_real_meme_pair()])
        assert result.source_status == SourceStatus.COMPLETE
        assert result.data_quality_label == DataQualityLabel.CLEAN_DATA
        kept = result.normalized_payload["pairs"]
        assert len(kept) == 1
        assert kept[0]["chain"] == "solana"
        assert kept[0]["token_mint"] == _MEME_MINT
        assert kept[0]["pair_address"] == _MEME_PAIR

    def test_dr05_excluded_pairs_audit_trail_present_and_reasoned(self):
        result = _norm([
            _real_meme_pair(),
            _pair("base", "BasePair1111111", "BaseMint1111111"),
            _pair("solana", "InfraPair1111111", USDC, symbol="USDC"),
        ])
        excluded = result.normalized_payload["excluded_pairs"]
        assert result.normalized_payload["excluded_pair_count"] == 2
        assert len(excluded) == 2
        for e in excluded:
            assert e["exclusion_reason"]  # never silent
            assert "token_mint" in e and "pair_address" in e

    def test_dr06_only_infra_and_non_solana_fails_closed(self):
        result = _norm([
            _pair("ethereum", "EthPair11111111", "EthMint11111111"),
            _pair("solana", "InfraPair1111111", WSOL, symbol="WSOL"),
        ])
        assert result.source_status == SourceStatus.FAILED
        assert result.data_quality_label == DataQualityLabel.MISSING_CRITICAL_DATA
        assert result.failure_type == "dexscreener_missing_critical_fixture_fields"

    def test_dr07_mixed_response_keeps_only_solana_memecoin(self):
        result = _norm([
            _pair("ethereum", "EthPair11111111", "EthMint11111111"),
            _pair("solana", "InfraPair1111111", USDT, symbol="USDT"),
            _real_meme_pair(),
            _pair("bsc", "BscPair11111111", "BscMint11111111"),
        ])
        kept = result.normalized_payload["pairs"]
        assert [k["token_mint"] for k in kept] == [_MEME_MINT]
        assert result.normalized_payload["excluded_pair_count"] == 3


class TestSelectionHandoff:
    def test_dr08_retained_candidate_reaches_selection_metadata(self):
        from printer_v1.discovery.parser import normalize_candidates
        from printer_v1.discovery.classifier import classify_discovery_candidate
        from printer_v1.discovery.contracts import DiscoveryOutputAction

        result = _norm([_real_meme_pair()])
        candidates = normalize_candidates(DEXSCREENER_SOURCE_NAME, dict(result.normalized_payload))
        assert len(candidates) == 1
        c = candidates[0]
        assert c["chain"] == "solana"
        assert c["token_mint"] == _MEME_MINT
        # A liquid, active fresh pair should classify into an accepted tracking lane.
        classification = classify_discovery_candidate(c)
        assert classification.discovery_action in {
            DiscoveryOutputAction.TRACK_FAST,
            DiscoveryOutputAction.TRACK_NORMAL,
        }

    def test_dr08b_infra_mint_never_reaches_selection(self):
        from printer_v1.discovery.parser import normalize_candidates

        result = _norm([_real_meme_pair(), _pair("solana", "InfraPair1111111", WSOL, symbol="WSOL")])
        candidates = normalize_candidates(DEXSCREENER_SOURCE_NAME, dict(result.normalized_payload))
        mints = {c["token_mint"] for c in candidates}
        assert WSOL not in mints
        assert _MEME_MINT in mints


class TestCategoricalOnly:
    def test_dr09_no_score_rank_confidence_fields_added(self):
        result = _norm([
            _real_meme_pair(),
            _pair("ethereum", "EthPair11111111", "EthMint11111111"),
        ])
        blob = repr(result.normalized_payload).lower()
        for banned in ("score", "rank", "confidence", "weight", "probability"):
            assert banned not in blob

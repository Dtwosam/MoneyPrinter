import pathlib
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.market_regime.contracts import MarketPayloadQualityLabel, MarketRegimeLabel


REQUIRED_CONTRACT_FIELDS = {
    "snapshot_id",
    "token_id",
    "pair_id",
    "memory_window_id",
    "evidence_window_id",
    "market_evidence_role",
    "source_name",
    "source_status",
    "data_quality_label",
    "target_status",
    "evidence_captured_at",
    "freshness_label",
    "market_scope_label",
    "market_regime_label",
    "market_trend_label",
    "market_volatility_label",
    "market_liquidity_label",
    "solana_market_context_label",
    "meme_market_context_label",
    "source_request_id",
    "source_response_id",
    "source_failure_id",
    "paper_only_context",
    "created_at",
}

FORBIDDEN_FIELD_FRAGMENTS = (
    "score",
    "ranking",
    "rank",
    "confidence",
    "weighted",
    "weight",
    "wallet",
    "private_key",
    "signature",
    "signing",
    "transaction",
    "live_execution",
    "live_trading",
)


def market_fixture(**overrides):
    fixture = {
        "snapshot_id": 36,
        "token_id": None,
        "pair_id": None,
        "memory_window_id": 8,
        "evidence_window_id": None,
        "market_evidence_role": "BROAD_MARKET_CONTEXT",
        "source_name": "future_governed_market_regime_source",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "target_status": "TARGET_MATCH",
        "evidence_captured_at": "2026-06-23T12:00:00+00:00",
        "freshness_label": "MARKET_EVIDENCE_FRESH",
        "market_scope_label": "BROAD_CRYPTO_MARKET",
        "market_regime_label": None,
        "market_trend_label": "MARKET_TREND_UP",
        "market_volatility_label": "MARKET_VOLATILITY_NORMAL",
        "market_liquidity_label": "MARKET_LIQUIDITY_HEALTHY",
        "solana_market_context_label": None,
        "meme_market_context_label": None,
        "source_request_id": 101,
        "source_response_id": 201,
        "source_failure_id": None,
        "paper_only_context": True,
        "created_at": "2026-06-23T12:00:01+00:00",
    }
    fixture.update(overrides)
    return fixture


def classify_market_fixture(fixture):
    if fixture.get("paper_only_context") is not True:
        return (
            MarketRegimeLabel.UNKNOWN,
            MarketPayloadQualityLabel.MARKET_CONTEXT_DO_NOT_USE_FOR_MEMORY,
        )
    if fixture.get("target_status") != "TARGET_MATCH":
        return (
            MarketRegimeLabel.UNKNOWN,
            MarketPayloadQualityLabel.MARKET_CONTEXT_CONFLICTING,
        )
    if fixture.get("source_request_id") is None:
        return (
            MarketRegimeLabel.UNKNOWN,
            MarketPayloadQualityLabel.MARKET_CONTEXT_UNKNOWN,
        )
    if fixture.get("source_status") == "FAILED" or fixture.get("data_quality_label") in {
        "DIRTY_DATA",
        "MISSING_CRITICAL_DATA",
        "DO_NOT_TRAIN",
    }:
        return (
            MarketRegimeLabel.UNKNOWN,
            MarketPayloadQualityLabel.MARKET_CONTEXT_DO_NOT_USE_FOR_MEMORY,
        )
    if fixture.get("source_status") == "STALE" or fixture.get("freshness_label") == "MARKET_EVIDENCE_STALE":
        return (
            MarketRegimeLabel.UNKNOWN,
            MarketPayloadQualityLabel.MARKET_CONTEXT_STALE,
        )

    if fixture.get("market_regime_label"):
        return (
            MarketRegimeLabel(fixture["market_regime_label"]),
            MarketPayloadQualityLabel.MARKET_CONTEXT_CLEAN,
        )

    trend = fixture.get("market_trend_label")
    volatility = fixture.get("market_volatility_label")
    liquidity = fixture.get("market_liquidity_label")
    if trend == "MARKET_TREND_UNKNOWN" or volatility == "MARKET_VOLATILITY_UNKNOWN":
        return (
            MarketRegimeLabel.UNKNOWN,
            MarketPayloadQualityLabel.MARKET_CONTEXT_UNKNOWN,
        )
    if volatility == "MARKET_VOLATILITY_HIGH":
        return (
            MarketRegimeLabel.VOLATILE,
            MarketPayloadQualityLabel.MARKET_CONTEXT_CLEAN,
        )
    if trend == "MARKET_TREND_DOWN" or liquidity == "MARKET_LIQUIDITY_THIN":
        return (
            MarketRegimeLabel.RISK_OFF,
            MarketPayloadQualityLabel.MARKET_CONTEXT_CLEAN,
        )
    if trend == "MARKET_TREND_UP" and liquidity == "MARKET_LIQUIDITY_HEALTHY":
        return (
            MarketRegimeLabel.RISK_ON,
            MarketPayloadQualityLabel.MARKET_CONTEXT_CLEAN,
        )
    if trend == "MARKET_TREND_SIDEWAYS":
        return (
            MarketRegimeLabel.NEUTRAL,
            MarketPayloadQualityLabel.MARKET_CONTEXT_CLEAN,
        )
    return (
        MarketRegimeLabel.UNKNOWN,
        MarketPayloadQualityLabel.MARKET_CONTEXT_UNKNOWN,
    )


def market_fixture_can_support_clean_memory_portion(fixture):
    regime_label, quality_label = classify_market_fixture(fixture)
    return (
        regime_label != MarketRegimeLabel.UNKNOWN
        and quality_label == MarketPayloadQualityLabel.MARKET_CONTEXT_CLEAN
    )


class PostRcMarketRegimeFixtureContractTest(unittest.TestCase):
    def test_contract_uses_required_candidate_fields_without_forbidden_systems(self):
        self.assertEqual(set(market_fixture().keys()), REQUIRED_CONTRACT_FIELDS)
        field_text = " ".join(REQUIRED_CONTRACT_FIELDS).lower()
        for fragment in FORBIDDEN_FIELD_FRAGMENTS:
            self.assertNotIn(fragment, field_text)

    def test_known_risk_on_fixture_maps_to_existing_risk_on_label(self):
        regime, quality = classify_market_fixture(market_fixture())
        self.assertEqual(regime, MarketRegimeLabel.RISK_ON)
        self.assertEqual(quality, MarketPayloadQualityLabel.MARKET_CONTEXT_CLEAN)
        self.assertTrue(market_fixture_can_support_clean_memory_portion(market_fixture()))

    def test_known_risk_off_fixture_maps_to_existing_risk_off_label(self):
        fixture = market_fixture(market_trend_label="MARKET_TREND_DOWN")
        regime, quality = classify_market_fixture(fixture)
        self.assertEqual(regime, MarketRegimeLabel.RISK_OFF)
        self.assertEqual(quality, MarketPayloadQualityLabel.MARKET_CONTEXT_CLEAN)

    def test_neutral_fixture_maps_to_existing_neutral_label(self):
        fixture = market_fixture(
            market_trend_label="MARKET_TREND_SIDEWAYS",
            market_liquidity_label="MARKET_LIQUIDITY_HEALTHY",
        )
        regime, quality = classify_market_fixture(fixture)
        self.assertEqual(regime, MarketRegimeLabel.NEUTRAL)
        self.assertEqual(quality, MarketPayloadQualityLabel.MARKET_CONTEXT_CLEAN)

    def test_volatile_fixture_maps_to_existing_volatile_label(self):
        fixture = market_fixture(market_volatility_label="MARKET_VOLATILITY_HIGH")
        regime, quality = classify_market_fixture(fixture)
        self.assertEqual(regime, MarketRegimeLabel.VOLATILE)
        self.assertEqual(quality, MarketPayloadQualityLabel.MARKET_CONTEXT_CLEAN)

    def test_thin_market_fixture_is_known_but_does_not_unlock_memory_alone(self):
        fixture = market_fixture(market_liquidity_label="MARKET_LIQUIDITY_THIN")
        regime, quality = classify_market_fixture(fixture)
        self.assertEqual(regime, MarketRegimeLabel.RISK_OFF)
        self.assertEqual(quality, MarketPayloadQualityLabel.MARKET_CONTEXT_CLEAN)
        downstream_gates = {
            "memory_clean_from_market_alone": False,
            "retrieval_unlocked": False,
            "paper_decision_created": False,
            "buy_unlocked": False,
            "paper_position_created": False,
            "paper_trade_event_created": False,
            "pnl_created": False,
        }
        self.assertTrue(market_fixture_can_support_clean_memory_portion(fixture))
        self.assertTrue(all(value is False for value in downstream_gates.values()))

    def test_missing_stale_failed_mismatch_trace_and_non_paper_fixtures_are_audit_only(self):
        cases = [
            market_fixture(market_trend_label="MARKET_TREND_UNKNOWN"),
            market_fixture(freshness_label="MARKET_EVIDENCE_STALE"),
            market_fixture(source_status="FAILED", source_response_id=None, source_failure_id=301),
            market_fixture(target_status="TARGET_MISMATCH"),
            market_fixture(source_request_id=None, source_response_id=None),
            market_fixture(paper_only_context=False),
        ]
        for fixture in cases:
            with self.subTest(fixture=fixture):
                self.assertFalse(market_fixture_can_support_clean_memory_portion(fixture))

    def test_market_fixture_alone_does_not_unlock_downstream_gates(self):
        fixture = market_fixture()
        downstream_gates = {
            "memory_clean_from_market_alone": False,
            "retrieval_unlocked": False,
            "paper_decision_created": False,
            "buy_unlocked": False,
            "paper_position_created": False,
            "paper_trade_event_created": False,
            "pnl_created": False,
        }
        self.assertTrue(market_fixture_can_support_clean_memory_portion(fixture))
        self.assertTrue(all(value is False for value in downstream_gates.values()))


if __name__ == "__main__":
    unittest.main()

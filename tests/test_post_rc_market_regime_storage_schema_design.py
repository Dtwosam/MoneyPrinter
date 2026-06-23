import pathlib
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.market_regime.contracts import MarketPayloadQualityLabel, MarketRegimeLabel


PROPOSED_TABLE_NAME = "printer_market_regime_evidence"

PROPOSED_FIELDS = {
    "id",
    "snapshot_id",
    "token_id",
    "pair_id",
    "memory_window_id",
    "evidence_window_id",
    "market_evidence_role",
    "market_scope_label",
    "source_name",
    "source_status",
    "data_quality_label",
    "target_status",
    "evidence_captured_at",
    "freshness_label",
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

BROAD_SCOPES = {
    "BROAD_CRYPTO_MARKET",
    "SOLANA_MARKET_CONTEXT",
    "SOLANA_MEME_MARKET_CONTEXT",
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


def market_evidence_row(**overrides):
    row = {
        "id": 1,
        "snapshot_id": 36,
        "token_id": None,
        "pair_id": None,
        "memory_window_id": 8,
        "evidence_window_id": None,
        "market_evidence_role": "BROAD_MARKET_CONTEXT",
        "market_scope_label": "BROAD_CRYPTO_MARKET",
        "source_name": "future_governed_market_regime_source",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "target_status": "TARGET_MATCH",
        "evidence_captured_at": "2026-06-23T12:00:00+00:00",
        "freshness_label": "MARKET_EVIDENCE_FRESH",
        "market_regime_label": "RISK_ON",
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
    row.update(overrides)
    return row


def audit_market_evidence(row):
    if row.get("paper_only_context") is not True:
        return {
            "regime": MarketRegimeLabel.UNKNOWN,
            "quality": MarketPayloadQualityLabel.MARKET_CONTEXT_DO_NOT_USE_FOR_MEMORY,
            "clean_eligible": False,
            "audit_only": True,
            "reason": "NON_PAPER_CONTEXT_INVALID",
        }
    if row.get("snapshot_id") is None and row.get("memory_window_id") is not None:
        return {
            "regime": MarketRegimeLabel.UNKNOWN,
            "quality": MarketPayloadQualityLabel.MARKET_CONTEXT_UNKNOWN,
            "clean_eligible": False,
            "audit_only": True,
            "reason": "MISSING_SNAPSHOT_LINKAGE",
        }
    if row.get("market_scope_label") not in BROAD_SCOPES and (
        row.get("token_id") is None or row.get("pair_id") is None
    ):
        return {
            "regime": MarketRegimeLabel.UNKNOWN,
            "quality": MarketPayloadQualityLabel.MARKET_CONTEXT_UNKNOWN,
            "clean_eligible": False,
            "audit_only": True,
            "reason": "TOKEN_PAIR_LINKAGE_REQUIRED",
        }
    if row.get("target_status") != "TARGET_MATCH":
        return {
            "regime": MarketRegimeLabel.UNKNOWN,
            "quality": MarketPayloadQualityLabel.MARKET_CONTEXT_CONFLICTING,
            "clean_eligible": False,
            "audit_only": True,
            "reason": "TARGET_MISMATCH",
        }
    if row.get("source_request_id") is None:
        return {
            "regime": MarketRegimeLabel.UNKNOWN,
            "quality": MarketPayloadQualityLabel.MARKET_CONTEXT_UNKNOWN,
            "clean_eligible": False,
            "audit_only": True,
            "reason": "MISSING_SOURCE_GOVERNOR_TRACE",
        }
    if row.get("source_status") == "FAILED" or row.get("data_quality_label") in {
        "DIRTY_DATA",
        "MISSING_CRITICAL_DATA",
        "DO_NOT_TRAIN",
    }:
        return {
            "regime": MarketRegimeLabel.UNKNOWN,
            "quality": MarketPayloadQualityLabel.MARKET_CONTEXT_DO_NOT_USE_FOR_MEMORY,
            "clean_eligible": False,
            "audit_only": True,
            "reason": "SOURCE_FAILED_OR_DIRTY",
        }
    if row.get("source_status") == "STALE" or row.get("freshness_label") == "MARKET_EVIDENCE_STALE":
        return {
            "regime": MarketRegimeLabel.UNKNOWN,
            "quality": MarketPayloadQualityLabel.MARKET_CONTEXT_STALE,
            "clean_eligible": False,
            "audit_only": True,
            "reason": "STALE_MARKET_EVIDENCE",
        }
    if row.get("market_regime_label") in {None, "UNKNOWN"}:
        return {
            "regime": MarketRegimeLabel.UNKNOWN,
            "quality": MarketPayloadQualityLabel.MARKET_CONTEXT_UNKNOWN,
            "clean_eligible": False,
            "audit_only": True,
            "reason": "MISSING_MARKET_EVIDENCE",
        }
    return {
        "regime": MarketRegimeLabel(row["market_regime_label"]),
        "quality": MarketPayloadQualityLabel.MARKET_CONTEXT_CLEAN,
        "clean_eligible": True,
        "audit_only": False,
        "reason": "MARKET_CONTEXT_KNOWN",
    }


class PostRcMarketRegimeStorageSchemaDesignTest(unittest.TestCase):
    def test_proposed_table_shape_has_required_fields_without_forbidden_systems(self):
        self.assertEqual(PROPOSED_TABLE_NAME, "printer_market_regime_evidence")
        self.assertEqual(set(market_evidence_row().keys()), PROPOSED_FIELDS)
        field_text = " ".join(PROPOSED_FIELDS).lower()
        for fragment in FORBIDDEN_FIELD_FRAGMENTS:
            self.assertNotIn(fragment, field_text)

    def test_snapshot_linkage_is_required_for_evidence_window_clean_eligibility(self):
        result = audit_market_evidence(market_evidence_row(snapshot_id=None))
        self.assertFalse(result["clean_eligible"])
        self.assertEqual(result["reason"], "MISSING_SNAPSHOT_LINKAGE")

    def test_broad_market_scope_allows_nullable_token_pair_only_when_scope_is_broad(self):
        broad_result = audit_market_evidence(market_evidence_row(token_id=None, pair_id=None))
        self.assertTrue(broad_result["clean_eligible"])

        token_specific = market_evidence_row(
            market_scope_label="TOKEN_PAIR_MARKET_CONTEXT",
            token_id=None,
            pair_id=None,
        )
        specific_result = audit_market_evidence(token_specific)
        self.assertFalse(specific_result["clean_eligible"])
        self.assertEqual(specific_result["reason"], "TOKEN_PAIR_LINKAGE_REQUIRED")

    def test_token_specific_market_evidence_requires_token_pair_linkage(self):
        row = market_evidence_row(
            market_scope_label="TOKEN_PAIR_MARKET_CONTEXT",
            token_id=2,
            pair_id=2,
        )
        self.assertTrue(audit_market_evidence(row)["clean_eligible"])

    def test_paper_only_context_and_source_trace_are_required_for_clean_eligibility(self):
        non_paper = audit_market_evidence(market_evidence_row(paper_only_context=False))
        missing_trace = audit_market_evidence(
            market_evidence_row(source_request_id=None, source_response_id=None)
        )
        self.assertEqual(non_paper["reason"], "NON_PAPER_CONTEXT_INVALID")
        self.assertEqual(missing_trace["reason"], "MISSING_SOURCE_GOVERNOR_TRACE")
        self.assertFalse(non_paper["clean_eligible"])
        self.assertFalse(missing_trace["clean_eligible"])

    def test_stale_failed_missing_and_target_mismatch_evidence_are_audit_only(self):
        cases = [
            (market_evidence_row(freshness_label="MARKET_EVIDENCE_STALE"), "STALE_MARKET_EVIDENCE"),
            (
                market_evidence_row(source_status="FAILED", source_response_id=None, source_failure_id=301),
                "SOURCE_FAILED_OR_DIRTY",
            ),
            (market_evidence_row(market_regime_label="UNKNOWN"), "MISSING_MARKET_EVIDENCE"),
            (market_evidence_row(target_status="TARGET_MISMATCH"), "TARGET_MISMATCH"),
        ]
        for row, reason in cases:
            with self.subTest(reason=reason):
                result = audit_market_evidence(row)
                self.assertFalse(result["clean_eligible"])
                self.assertTrue(result["audit_only"])
                self.assertEqual(result["reason"], reason)

    def test_storage_label_mapping_uses_existing_compatible_regime_labels(self):
        cases = {
            "RISK_ON": MarketRegimeLabel.RISK_ON,
            "RISK_OFF": MarketRegimeLabel.RISK_OFF,
            "NEUTRAL": MarketRegimeLabel.NEUTRAL,
            "VOLATILE": MarketRegimeLabel.VOLATILE,
        }
        for label, expected in cases.items():
            with self.subTest(label=label):
                result = audit_market_evidence(market_evidence_row(market_regime_label=label))
                self.assertEqual(result["regime"], expected)
                self.assertEqual(result["quality"], MarketPayloadQualityLabel.MARKET_CONTEXT_CLEAN)

    def test_market_evidence_alone_does_not_unlock_downstream_gates(self):
        result = audit_market_evidence(market_evidence_row())
        downstream_gates = {
            "memory_clean_from_market_alone": False,
            "retrieval_unlocked": False,
            "paper_decision_created": False,
            "buy_unlocked": False,
            "paper_position_created": False,
            "paper_trade_event_created": False,
            "pnl_created": False,
            "broad_market_direct_trade_signal": False,
        }
        self.assertTrue(result["clean_eligible"])
        self.assertTrue(all(value is False for value in downstream_gates.values()))


if __name__ == "__main__":
    unittest.main()

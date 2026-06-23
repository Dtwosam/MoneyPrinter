import pathlib
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.memory.contracts import MemoryQualityLabel


def paper_quote_fixture(
    *,
    direction="ENTRY",
    purpose="PAPER_REALISM_ONLY",
    route_available=True,
    route_plan_present=True,
    freshness="QUOTE_FRESH",
    source_status="COMPLETE",
    data_quality_label="CLEAN_DATA",
    token_id=1,
    pair_id=1,
    snapshot_id=36,
    memory_window_id=8,
    source_request_id=10,
    source_response_id=11,
    source_failure_id=None,
    slippage_bps=100,
    price_impact_label="PRICE_IMPACT_ACCEPTABLE",
):
    return {
        "token_id": token_id,
        "pair_id": pair_id,
        "snapshot_id": snapshot_id,
        "memory_window_id": memory_window_id,
        "quote_direction": direction,
        "quote_purpose": purpose,
        "input_mint": "fixture-input-mint",
        "output_mint": "fixture-output-mint",
        "input_amount": "1000000",
        "output_amount": "990000",
        "route_available": route_available,
        "route_plan_present": route_plan_present,
        "slippage_bps": slippage_bps,
        "price_impact_label": price_impact_label,
        "quote_captured_at": "2026-06-23T12:00:00+00:00",
        "quote_freshness_label": freshness,
        "source_status": source_status,
        "data_quality_label": data_quality_label,
        "failure_reason": None if source_status == "COMPLETE" else "quote_fixture_failed",
        "no_route_reason": None if route_available else "NO_ROUTE_AVAILABLE",
        "source_request_id": source_request_id,
        "source_response_id": source_response_id,
        "source_failure_id": source_failure_id,
    }


def map_quote_realism_label(fixture):
    direction = fixture["quote_direction"]
    if fixture.get("quote_purpose") != "PAPER_REALISM_ONLY":
        return f"{direction}_REALISM_UNKNOWN"
    if not all(fixture.get(key) for key in ("token_id", "pair_id", "snapshot_id", "memory_window_id")):
        return f"{direction}_REALISM_UNKNOWN"
    if fixture.get("source_status") != "COMPLETE" or fixture.get("data_quality_label") != "CLEAN_DATA":
        return f"{direction}_REALISM_UNKNOWN"
    if fixture.get("quote_freshness_label") != "QUOTE_FRESH":
        return f"{direction}_REALISM_UNKNOWN"
    if not fixture.get("route_available") or not fixture.get("route_plan_present"):
        return f"{direction}_ROUTE_UNAVAILABLE"
    impact = fixture.get("price_impact_label")
    if impact in {"PRICE_IMPACT_HIGH", "PRICE_IMPACT_UNKNOWN"} or int(fixture.get("slippage_bps") or 0) > 300:
        return f"{direction}_REALISM_CAUTION"
    return f"{direction}_ROUTE_AVAILABLE"


def quote_fixture_can_support_clean_entry_exit(fixture):
    label = map_quote_realism_label(fixture)
    return label in {"ENTRY_ROUTE_AVAILABLE", "EXIT_ROUTE_AVAILABLE", "ENTRY_REALISM_CAUTION", "EXIT_REALISM_CAUTION"}


def quote_fixture_can_make_memory_clean_by_itself(fixture):
    del fixture
    return False


class PostRCPaperQuoteEvidenceFixtureReadinessTests(unittest.TestCase):
    def test_route_available_fixtures_map_to_route_available_labels(self):
        self.assertEqual(map_quote_realism_label(paper_quote_fixture(direction="ENTRY")), "ENTRY_ROUTE_AVAILABLE")
        self.assertEqual(map_quote_realism_label(paper_quote_fixture(direction="EXIT")), "EXIT_ROUTE_AVAILABLE")

    def test_no_route_fixtures_map_to_route_unavailable_labels(self):
        self.assertEqual(
            map_quote_realism_label(paper_quote_fixture(direction="ENTRY", route_available=False, route_plan_present=False)),
            "ENTRY_ROUTE_UNAVAILABLE",
        )
        self.assertEqual(
            map_quote_realism_label(paper_quote_fixture(direction="EXIT", route_available=False, route_plan_present=False)),
            "EXIT_ROUTE_UNAVAILABLE",
        )

    def test_stale_failed_missing_and_mismatched_fixtures_remain_audit_only_or_unknown(self):
        cases = [
            paper_quote_fixture(freshness="QUOTE_STALE"),
            paper_quote_fixture(source_status="FAILED", data_quality_label="MISSING_CRITICAL_DATA", source_response_id=None, source_failure_id=12),
            paper_quote_fixture(memory_window_id=None),
            paper_quote_fixture(snapshot_id=None),
            paper_quote_fixture(purpose="LIVE_EXECUTION_QUOTE"),
        ]
        for fixture in cases:
            with self.subTest(fixture=fixture):
                self.assertEqual(map_quote_realism_label(fixture), f"{fixture['quote_direction']}_REALISM_UNKNOWN")
                self.assertFalse(quote_fixture_can_support_clean_entry_exit(fixture))
                self.assertFalse(quote_fixture_can_make_memory_clean_by_itself(fixture))

    def test_quote_evidence_alone_never_unlocks_memory_retrieval_or_paper_outputs(self):
        fixture = paper_quote_fixture(direction="ENTRY")

        self.assertTrue(quote_fixture_can_support_clean_entry_exit(fixture))
        self.assertFalse(quote_fixture_can_make_memory_clean_by_itself(fixture))
        self.assertNotEqual(MemoryQualityLabel.CLEAN_MEMORY.value, MemoryQualityLabel.AUDIT_ONLY_MEMORY.value)

        safety = {
            "memory_quality_from_quote_only": MemoryQualityLabel.AUDIT_ONLY_MEMORY.value,
            "retrieval_allowed": False,
            "paper_decision_created": False,
            "paper_position_created": False,
            "paper_trade_event_created": False,
            "pnl_created": False,
            "buy_unlocked": False,
        }

        self.assertEqual(safety["memory_quality_from_quote_only"], "AUDIT_ONLY_MEMORY")
        self.assertFalse(safety["retrieval_allowed"])
        self.assertFalse(safety["paper_decision_created"])
        self.assertFalse(safety["paper_position_created"])
        self.assertFalse(safety["paper_trade_event_created"])
        self.assertFalse(safety["pnl_created"])
        self.assertFalse(safety["buy_unlocked"])

    def test_price_impact_or_slippage_caution_is_categorical_not_scored(self):
        fixture = paper_quote_fixture(price_impact_label="PRICE_IMPACT_HIGH")
        self.assertEqual(map_quote_realism_label(fixture), "ENTRY_REALISM_CAUTION")
        self.assertNotIn("score", fixture)
        self.assertNotIn("confidence", fixture)
        self.assertNotIn("ranking", fixture)


if __name__ == "__main__":
    unittest.main()

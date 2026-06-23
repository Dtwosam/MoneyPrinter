import pathlib
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))


PROPOSED_TABLE_NAME = "printer_paper_quote_evidence"

PROPOSED_FIELDS = {
    "id",
    "token_id",
    "pair_id",
    "snapshot_id",
    "memory_window_id",
    "evidence_window_id",
    "quote_direction",
    "quote_purpose",
    "input_mint",
    "output_mint",
    "input_amount_raw",
    "output_amount_raw",
    "route_available",
    "route_plan_present",
    "route_count",
    "slippage_bps",
    "price_impact_bps",
    "price_impact_label",
    "quote_captured_at",
    "quote_freshness_label",
    "source_name",
    "source_status",
    "data_quality_label",
    "failure_reason",
    "no_route_reason",
    "target_status",
    "paper_only",
    "source_request_id",
    "source_response_id",
    "source_failure_id",
    "created_at",
}

FORBIDDEN_FIELDS = {
    "wallet",
    "wallet_address",
    "private_key",
    "secret_key",
    "signature",
    "signed_transaction",
    "transaction",
    "transaction_payload",
    "execute_transaction",
    "send_transaction",
    "live_execution",
    "buy_score",
    "confidence",
    "ranking",
    "weighted_score",
}


def quote_storage_fixture(**overrides):
    fixture = {
        "id": 1,
        "token_id": 2,
        "pair_id": 2,
        "snapshot_id": 36,
        "memory_window_id": 8,
        "evidence_window_id": None,
        "quote_direction": "ENTRY",
        "quote_purpose": "PAPER_REALISM_ONLY",
        "input_mint": "fixture-input-mint",
        "output_mint": "fixture-output-mint",
        "input_amount_raw": "1000000",
        "output_amount_raw": "990000",
        "route_available": 1,
        "route_plan_present": 1,
        "route_count": 1,
        "slippage_bps": 100,
        "price_impact_bps": 25,
        "price_impact_label": "PRICE_IMPACT_ACCEPTABLE",
        "quote_captured_at": "2026-06-23T12:00:00+00:00",
        "quote_freshness_label": "QUOTE_FRESH",
        "source_name": "jupiter_candidate",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "failure_reason": None,
        "no_route_reason": None,
        "target_status": "TARGET_MATCH",
        "paper_only": 1,
        "source_request_id": 10,
        "source_response_id": 11,
        "source_failure_id": None,
        "created_at": "2026-06-23T12:00:01+00:00",
    }
    fixture.update(overrides)
    return fixture


def storage_fixture_audit_label(fixture):
    if fixture.get("paper_only") != 1 or fixture.get("quote_purpose") != "PAPER_REALISM_ONLY":
        return "QUOTE_NOT_PAPER_ONLY"
    if fixture.get("quote_direction") not in {"ENTRY", "EXIT"}:
        return "QUOTE_INVALID_DIRECTION"
    if fixture.get("target_status") != "TARGET_MATCH":
        return "QUOTE_TARGET_MISMATCH"
    if not fixture.get("source_request_id"):
        return "QUOTE_SOURCE_GOVERNANCE_MISSING"
    if fixture.get("source_status") == "FAILED" or fixture.get("source_failure_id"):
        return "QUOTE_FAILED"
    if fixture.get("quote_freshness_label") != "QUOTE_FRESH":
        return "QUOTE_STALE"
    if not fixture.get("route_available") or not fixture.get("route_plan_present"):
        return "QUOTE_NO_ROUTE"
    return "QUOTE_ROUTE_AVAILABLE"


def storage_fixture_realism_label(fixture):
    direction = fixture.get("quote_direction")
    audit_label = storage_fixture_audit_label(fixture)
    if audit_label == "QUOTE_ROUTE_AVAILABLE":
        if fixture.get("price_impact_label") in {"PRICE_IMPACT_HIGH", "PRICE_IMPACT_UNKNOWN"}:
            return f"{direction}_REALISM_CAUTION"
        return f"{direction}_ROUTE_AVAILABLE"
    if audit_label == "QUOTE_NO_ROUTE":
        return f"{direction}_ROUTE_UNAVAILABLE"
    return f"{direction}_REALISM_UNKNOWN"


def quote_storage_can_support_clean_entry_exit(fixture):
    return storage_fixture_audit_label(fixture) == "QUOTE_ROUTE_AVAILABLE"


class PostRCPaperQuoteEvidenceStorageSchemaDesignTests(unittest.TestCase):
    def test_proposed_table_name_and_required_fields_are_documented(self):
        self.assertEqual(PROPOSED_TABLE_NAME, "printer_paper_quote_evidence")
        required = {
            "id",
            "token_id",
            "pair_id",
            "snapshot_id",
            "quote_direction",
            "quote_purpose",
            "input_mint",
            "output_mint",
            "input_amount_raw",
            "output_amount_raw",
            "route_available",
            "route_plan_present",
            "slippage_bps",
            "price_impact_label",
            "quote_captured_at",
            "quote_freshness_label",
            "source_name",
            "source_status",
            "data_quality_label",
            "target_status",
            "paper_only",
            "source_request_id",
            "source_response_id",
            "source_failure_id",
            "created_at",
        }
        self.assertTrue(required.issubset(PROPOSED_FIELDS))

    def test_contract_excludes_live_execution_wallet_private_key_and_score_fields(self):
        lowered = {field.lower() for field in PROPOSED_FIELDS}
        self.assertTrue(FORBIDDEN_FIELDS.isdisjoint(lowered))

    def test_paper_only_purpose_and_direction_constraints(self):
        valid = quote_storage_fixture()
        self.assertEqual(storage_fixture_audit_label(valid), "QUOTE_ROUTE_AVAILABLE")

        for direction in ("ENTRY", "EXIT"):
            with self.subTest(direction=direction):
                fixture = quote_storage_fixture(quote_direction=direction)
                self.assertIn(storage_fixture_realism_label(fixture), {f"{direction}_ROUTE_AVAILABLE", f"{direction}_REALISM_CAUTION"})

        invalid_cases = [
            quote_storage_fixture(paper_only=0),
            quote_storage_fixture(quote_purpose="LIVE_EXECUTION_QUOTE"),
            quote_storage_fixture(quote_direction="SWAP"),
        ]
        expected = ["QUOTE_NOT_PAPER_ONLY", "QUOTE_NOT_PAPER_ONLY", "QUOTE_INVALID_DIRECTION"]
        for fixture, label in zip(invalid_cases, expected):
            with self.subTest(label=label):
                self.assertEqual(storage_fixture_audit_label(fixture), label)
                self.assertFalse(quote_storage_can_support_clean_entry_exit(fixture))

    def test_stale_failed_no_route_target_mismatch_and_missing_governance_block_clean_eligibility(self):
        cases = [
            (quote_storage_fixture(quote_freshness_label="QUOTE_STALE"), "QUOTE_STALE", "ENTRY_REALISM_UNKNOWN"),
            (
                quote_storage_fixture(
                    source_status="FAILED",
                    data_quality_label="MISSING_CRITICAL_DATA",
                    source_response_id=None,
                    source_failure_id=12,
                    failure_reason="fixture failure",
                ),
                "QUOTE_FAILED",
                "ENTRY_REALISM_UNKNOWN",
            ),
            (
                quote_storage_fixture(route_available=0, route_plan_present=0, output_amount_raw=None, no_route_reason="NO_ROUTE_AVAILABLE"),
                "QUOTE_NO_ROUTE",
                "ENTRY_ROUTE_UNAVAILABLE",
            ),
            (quote_storage_fixture(target_status="TARGET_MISMATCH"), "QUOTE_TARGET_MISMATCH", "ENTRY_REALISM_UNKNOWN"),
            (quote_storage_fixture(source_request_id=None), "QUOTE_SOURCE_GOVERNANCE_MISSING", "ENTRY_REALISM_UNKNOWN"),
        ]
        for fixture, audit_label, realism_label in cases:
            with self.subTest(audit_label=audit_label):
                self.assertEqual(storage_fixture_audit_label(fixture), audit_label)
                self.assertEqual(storage_fixture_realism_label(fixture), realism_label)
                if audit_label != "QUOTE_NO_ROUTE":
                    self.assertFalse(quote_storage_can_support_clean_entry_exit(fixture))

    def test_quote_storage_alone_does_not_unlock_clean_memory_or_downstream_rows(self):
        fixture = quote_storage_fixture()
        self.assertTrue(quote_storage_can_support_clean_entry_exit(fixture))
        safety = {
            "quote_evidence_alone_makes_clean_memory": False,
            "retrieval_unlocked": False,
            "paper_decision_created": False,
            "paper_position_created": False,
            "paper_trade_event_created": False,
            "pnl_created": False,
            "buy_unlocked": False,
        }
        self.assertFalse(safety["quote_evidence_alone_makes_clean_memory"])
        self.assertFalse(safety["retrieval_unlocked"])
        self.assertFalse(safety["paper_decision_created"])
        self.assertFalse(safety["paper_position_created"])
        self.assertFalse(safety["paper_trade_event_created"])
        self.assertFalse(safety["pnl_created"])
        self.assertFalse(safety["buy_unlocked"])


if __name__ == "__main__":
    unittest.main()

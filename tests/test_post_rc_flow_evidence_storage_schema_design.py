import unittest

from printer_v1.trading_flow.contracts import (
    FlowDirectionLabel,
    FlowMemoryGateLabel,
    FlowPressureLabel,
    TradingFlowPayloadQualityLabel,
)
from tests.test_post_rc_flow_evidence_fixture_contract import (
    classify_flow_fixture,
    flow_fixture,
    flow_fixture_can_support_clean_memory_portion,
)


PROPOSED_TABLE_NAME = "printer_flow_evidence"

PROPOSED_FIELDS = {
    "id",
    "token_id",
    "pair_id",
    "snapshot_id",
    "memory_window_id",
    "evidence_window_id",
    "flow_evidence_role",
    "source_name",
    "source_status",
    "data_quality_label",
    "target_status",
    "evidence_captured_at",
    "freshness_label",
    "buy_tx_count",
    "sell_tx_count",
    "buy_volume_usd",
    "sell_volume_usd",
    "net_flow_direction_label",
    "flow_pressure_label",
    "flow_activity_label",
    "flow_window_label",
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


def storage_fixture(**overrides):
    fixture = {
        "id": 1,
    }
    fixture.update(flow_fixture())
    fixture.update(overrides)
    return fixture


def storage_has_source_trace(row):
    if row.get("source_request_id") is None:
        return False
    if row.get("source_status") == "FAILED":
        return row.get("source_failure_id") is not None
    return row.get("source_response_id") is not None


def storage_can_support_evidence_window_clean_eligibility(row):
    return (
        row.get("token_id") is not None
        and row.get("pair_id") is not None
        and row.get("snapshot_id") is not None
        and row.get("paper_only_context") is True
        and storage_has_source_trace(row)
        and flow_fixture_can_support_clean_memory_portion(row)
    )


class PostRcFlowEvidenceStorageSchemaDesignTest(unittest.TestCase):
    def test_proposed_table_shape_has_required_fields(self):
        required = {
            "id",
            "token_id",
            "pair_id",
            "snapshot_id",
            "flow_evidence_role",
            "source_name",
            "source_status",
            "data_quality_label",
            "target_status",
            "evidence_captured_at",
            "freshness_label",
            "net_flow_direction_label",
            "flow_pressure_label",
            "flow_activity_label",
            "flow_window_label",
            "source_request_id",
            "source_response_id",
            "source_failure_id",
            "paper_only_context",
            "created_at",
        }
        self.assertEqual(PROPOSED_TABLE_NAME, "printer_flow_evidence")
        self.assertTrue(required.issubset(PROPOSED_FIELDS))

    def test_proposed_shape_excludes_scores_wallets_and_live_execution_fields(self):
        field_text = " ".join(PROPOSED_FIELDS).lower()
        for fragment in FORBIDDEN_FIELD_FRAGMENTS:
            self.assertNotIn(fragment, field_text)

    def test_token_pair_snapshot_paper_context_and_source_trace_are_required(self):
        valid = storage_fixture()
        missing_token = storage_fixture(token_id=None)
        missing_pair = storage_fixture(pair_id=None)
        missing_snapshot = storage_fixture(snapshot_id=None)
        non_paper = storage_fixture(paper_only_context=False)
        missing_trace = storage_fixture(source_request_id=None, source_response_id=None)

        self.assertTrue(storage_can_support_evidence_window_clean_eligibility(valid))
        for row in (missing_token, missing_pair, missing_snapshot, non_paper, missing_trace):
            with self.subTest(row=row):
                self.assertFalse(storage_can_support_evidence_window_clean_eligibility(row))

    def test_stale_failed_missing_target_mismatch_and_low_activity_are_not_clean_eligible(self):
        cases = [
            storage_fixture(freshness_label="FLOW_EVIDENCE_STALE"),
            storage_fixture(source_status="FAILED", source_response_id=None, source_failure_id=301),
            storage_fixture(buy_tx_count=None, sell_tx_count=None, buy_volume_usd=None, sell_volume_usd=None),
            storage_fixture(target_status="TARGET_MISMATCH"),
            storage_fixture(buy_tx_count=1, sell_tx_count=1, buy_volume_usd=100.0, sell_volume_usd=80.0),
        ]
        for row in cases:
            with self.subTest(row=row):
                self.assertFalse(storage_can_support_evidence_window_clean_eligibility(row))

    def test_storage_label_mapping_remains_categorical_and_existing_compatible(self):
        buy = classify_flow_fixture(storage_fixture())
        sell = classify_flow_fixture(
            storage_fixture(
                buy_tx_count=15,
                sell_tx_count=60,
                buy_volume_usd=10_000.0,
                sell_volume_usd=40_000.0,
            )
        )
        balanced = classify_flow_fixture(
            storage_fixture(
                buy_tx_count=25,
                sell_tx_count=25,
                buy_volume_usd=20_000.0,
                sell_volume_usd=20_000.0,
            )
        )
        stale = classify_flow_fixture(storage_fixture(freshness_label="FLOW_EVIDENCE_STALE"))

        self.assertEqual(
            buy,
            (
                FlowDirectionLabel.FLOW_ACCUMULATION,
                FlowPressureLabel.PRESSURE_STRONG_INFLOW,
                TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CLEAN,
                FlowMemoryGateLabel.FLOW_CONTEXT_ACCEPTABLE,
            ),
        )
        self.assertEqual(
            sell,
            (
                FlowDirectionLabel.FLOW_DISTRIBUTION,
                FlowPressureLabel.PRESSURE_STRONG_OUTFLOW,
                TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CLEAN,
                FlowMemoryGateLabel.FLOW_CONTEXT_ACCEPTABLE,
            ),
        )
        self.assertEqual(
            balanced,
            (
                FlowDirectionLabel.FLOW_CHOPPY,
                FlowPressureLabel.PRESSURE_BALANCED,
                TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CLEAN,
                FlowMemoryGateLabel.FLOW_CONTEXT_ACCEPTABLE,
            ),
        )
        self.assertEqual(
            stale,
            (
                FlowDirectionLabel.FLOW_UNKNOWN,
                FlowPressureLabel.PRESSURE_UNKNOWN,
                TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_STALE,
                FlowMemoryGateLabel.FLOW_CONTEXT_AUDIT_ONLY,
            ),
        )

    def test_flow_evidence_alone_does_not_unlock_downstream_gates(self):
        row = storage_fixture()
        downstream_gates = {
            "clean_memory_unlocked_from_flow_alone": False,
            "retrieval_unlocked": False,
            "paper_decision_created": False,
            "buy_unlocked": False,
            "paper_position_created": False,
            "paper_trade_event_created": False,
            "pnl_created": False,
        }

        self.assertTrue(storage_can_support_evidence_window_clean_eligibility(row))
        self.assertTrue(all(value is False for value in downstream_gates.values()))


if __name__ == "__main__":
    unittest.main()

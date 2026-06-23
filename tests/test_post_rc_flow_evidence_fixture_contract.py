import pathlib
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.trading_flow.contracts import (
    FlowDirectionLabel,
    FlowMemoryGateLabel,
    FlowPressureLabel,
    TradingFlowPayloadQualityLabel,
)


REQUIRED_CONTRACT_FIELDS = {
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


def flow_fixture(**overrides):
    fixture = {
        "token_id": 2,
        "pair_id": 2,
        "snapshot_id": 36,
        "memory_window_id": 8,
        "evidence_window_id": None,
        "flow_evidence_role": "TOKEN_PAIR_FLOW_CONTEXT",
        "source_name": "future_governed_flow_source",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "target_status": "TARGET_MATCH",
        "evidence_captured_at": "2026-06-23T12:00:00+00:00",
        "freshness_label": "FLOW_EVIDENCE_FRESH",
        "buy_tx_count": 60,
        "sell_tx_count": 20,
        "buy_volume_usd": 45_000.0,
        "sell_volume_usd": 15_000.0,
        "net_flow_direction_label": None,
        "flow_pressure_label": None,
        "flow_activity_label": "FLOW_ACTIVITY_ACTIVE",
        "flow_window_label": "FLOW_WINDOW_15M",
        "source_request_id": 101,
        "source_response_id": 201,
        "source_failure_id": None,
        "paper_only_context": True,
        "created_at": "2026-06-23T12:00:01+00:00",
    }
    fixture.update(overrides)
    return fixture


def _ratio(left, right):
    if left is None or right in (None, 0):
        return None
    return float(left) / float(right)


def classify_flow_fixture(fixture):
    if fixture.get("paper_only_context") is not True:
        return (
            FlowDirectionLabel.FLOW_UNKNOWN,
            FlowPressureLabel.PRESSURE_UNKNOWN,
            TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_DO_NOT_USE_FOR_MEMORY,
            FlowMemoryGateLabel.FLOW_CONTEXT_DO_NOT_TRAIN,
        )
    if fixture.get("target_status") != "TARGET_MATCH":
        return (
            FlowDirectionLabel.FLOW_UNKNOWN,
            FlowPressureLabel.PRESSURE_UNKNOWN,
            TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CONFLICTING,
            FlowMemoryGateLabel.FLOW_CONTEXT_AUDIT_ONLY,
        )
    if fixture.get("source_request_id") is None:
        return (
            FlowDirectionLabel.FLOW_UNKNOWN,
            FlowPressureLabel.PRESSURE_UNKNOWN,
            TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_UNKNOWN,
            FlowMemoryGateLabel.FLOW_CONTEXT_AUDIT_ONLY,
        )
    if fixture.get("source_status") == "FAILED" or fixture.get("data_quality_label") in {
        "DIRTY_DATA",
        "MISSING_CRITICAL_DATA",
        "DO_NOT_TRAIN",
    }:
        return (
            FlowDirectionLabel.FLOW_UNKNOWN,
            FlowPressureLabel.PRESSURE_UNKNOWN,
            TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_DO_NOT_USE_FOR_MEMORY,
            FlowMemoryGateLabel.FLOW_CONTEXT_DO_NOT_TRAIN,
        )
    if fixture.get("freshness_label") == "FLOW_EVIDENCE_STALE" or fixture.get("source_status") == "STALE":
        return (
            FlowDirectionLabel.FLOW_UNKNOWN,
            FlowPressureLabel.PRESSURE_UNKNOWN,
            TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_STALE,
            FlowMemoryGateLabel.FLOW_CONTEXT_AUDIT_ONLY,
        )

    buy_tx = fixture.get("buy_tx_count")
    sell_tx = fixture.get("sell_tx_count")
    buy_volume = fixture.get("buy_volume_usd")
    sell_volume = fixture.get("sell_volume_usd")
    if all(value is None for value in (buy_tx, sell_tx, buy_volume, sell_volume)):
        return (
            FlowDirectionLabel.FLOW_UNKNOWN,
            FlowPressureLabel.PRESSURE_UNKNOWN,
            TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_UNKNOWN,
            FlowMemoryGateLabel.FLOW_CONTEXT_AUDIT_ONLY,
        )

    total_tx = (buy_tx or 0) + (sell_tx or 0)
    total_volume = (buy_volume or 0.0) + (sell_volume or 0.0)
    if total_tx <= 4 or total_volume < 500:
        return (
            FlowDirectionLabel.FLOW_EXHAUSTION,
            FlowPressureLabel.PRESSURE_BALANCED,
            TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_PARTIAL,
            FlowMemoryGateLabel.FLOW_CONTEXT_CAUTION,
        )

    volume_ratio = _ratio(buy_volume, sell_volume)
    count_ratio = _ratio(buy_tx, sell_tx)
    ratio = volume_ratio if volume_ratio is not None else count_ratio
    if ratio is None:
        return (
            FlowDirectionLabel.FLOW_UNKNOWN,
            FlowPressureLabel.PRESSURE_UNKNOWN,
            TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_UNKNOWN,
            FlowMemoryGateLabel.FLOW_CONTEXT_AUDIT_ONLY,
        )
    if ratio >= 2.0:
        return (
            FlowDirectionLabel.FLOW_ACCUMULATION,
            FlowPressureLabel.PRESSURE_STRONG_INFLOW,
            TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CLEAN,
            FlowMemoryGateLabel.FLOW_CONTEXT_ACCEPTABLE,
        )
    if ratio >= 1.25:
        return (
            FlowDirectionLabel.FLOW_ACCUMULATION,
            FlowPressureLabel.PRESSURE_MODERATE_INFLOW,
            TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CLEAN,
            FlowMemoryGateLabel.FLOW_CONTEXT_ACCEPTABLE,
        )
    if ratio <= 0.5:
        return (
            FlowDirectionLabel.FLOW_DISTRIBUTION,
            FlowPressureLabel.PRESSURE_STRONG_OUTFLOW,
            TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CLEAN,
            FlowMemoryGateLabel.FLOW_CONTEXT_ACCEPTABLE,
        )
    if ratio <= 0.8:
        return (
            FlowDirectionLabel.FLOW_DISTRIBUTION,
            FlowPressureLabel.PRESSURE_MODERATE_OUTFLOW,
            TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CLEAN,
            FlowMemoryGateLabel.FLOW_CONTEXT_ACCEPTABLE,
        )
    return (
        FlowDirectionLabel.FLOW_CHOPPY,
        FlowPressureLabel.PRESSURE_BALANCED,
        TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CLEAN,
        FlowMemoryGateLabel.FLOW_CONTEXT_ACCEPTABLE,
    )


def flow_fixture_can_support_clean_memory_portion(fixture):
    _, _, quality, gate = classify_flow_fixture(fixture)
    return (
        quality == TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CLEAN
        and gate == FlowMemoryGateLabel.FLOW_CONTEXT_ACCEPTABLE
    )


class PostRcFlowEvidenceFixtureContractTest(unittest.TestCase):
    def test_contract_uses_required_candidate_fields_without_forbidden_systems(self):
        self.assertEqual(set(flow_fixture().keys()), REQUIRED_CONTRACT_FIELDS)
        field_text = " ".join(REQUIRED_CONTRACT_FIELDS).lower()
        for fragment in FORBIDDEN_FIELD_FRAGMENTS:
            self.assertNotIn(fragment, field_text)

    def test_buy_dominant_fixture_maps_to_accumulation_and_inflow(self):
        direction, pressure, quality, gate = classify_flow_fixture(flow_fixture())
        self.assertEqual(direction, FlowDirectionLabel.FLOW_ACCUMULATION)
        self.assertEqual(pressure, FlowPressureLabel.PRESSURE_STRONG_INFLOW)
        self.assertEqual(quality, TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CLEAN)
        self.assertEqual(gate, FlowMemoryGateLabel.FLOW_CONTEXT_ACCEPTABLE)

    def test_sell_dominant_fixture_maps_to_distribution_and_outflow(self):
        fixture = flow_fixture(
            buy_tx_count=15,
            sell_tx_count=60,
            buy_volume_usd=10_000.0,
            sell_volume_usd=40_000.0,
        )
        direction, pressure, quality, gate = classify_flow_fixture(fixture)
        self.assertEqual(direction, FlowDirectionLabel.FLOW_DISTRIBUTION)
        self.assertEqual(pressure, FlowPressureLabel.PRESSURE_STRONG_OUTFLOW)
        self.assertEqual(quality, TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CLEAN)
        self.assertEqual(gate, FlowMemoryGateLabel.FLOW_CONTEXT_ACCEPTABLE)

    def test_balanced_fixture_maps_to_choppy_and_balanced_pressure(self):
        fixture = flow_fixture(
            buy_tx_count=30,
            sell_tx_count=29,
            buy_volume_usd=20_000.0,
            sell_volume_usd=19_500.0,
        )
        direction, pressure, quality, gate = classify_flow_fixture(fixture)
        self.assertEqual(direction, FlowDirectionLabel.FLOW_CHOPPY)
        self.assertEqual(pressure, FlowPressureLabel.PRESSURE_BALANCED)
        self.assertEqual(quality, TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CLEAN)
        self.assertEqual(gate, FlowMemoryGateLabel.FLOW_CONTEXT_ACCEPTABLE)

    def test_low_activity_fixture_is_cautionary_and_not_clean_by_itself(self):
        fixture = flow_fixture(
            buy_tx_count=2,
            sell_tx_count=1,
            buy_volume_usd=150.0,
            sell_volume_usd=100.0,
        )
        direction, pressure, quality, gate = classify_flow_fixture(fixture)
        self.assertEqual(direction, FlowDirectionLabel.FLOW_EXHAUSTION)
        self.assertEqual(pressure, FlowPressureLabel.PRESSURE_BALANCED)
        self.assertEqual(quality, TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_PARTIAL)
        self.assertEqual(gate, FlowMemoryGateLabel.FLOW_CONTEXT_CAUTION)
        self.assertFalse(flow_fixture_can_support_clean_memory_portion(fixture))

    def test_missing_stale_failed_mismatch_trace_and_non_paper_fixtures_are_audit_only(self):
        cases = [
            flow_fixture(buy_tx_count=None, sell_tx_count=None, buy_volume_usd=None, sell_volume_usd=None),
            flow_fixture(freshness_label="FLOW_EVIDENCE_STALE"),
            flow_fixture(source_status="FAILED", source_response_id=None, source_failure_id=301),
            flow_fixture(target_status="TARGET_MISMATCH"),
            flow_fixture(source_request_id=None, source_response_id=None),
            flow_fixture(paper_only_context=False),
        ]
        for fixture in cases:
            with self.subTest(fixture=fixture):
                self.assertFalse(flow_fixture_can_support_clean_memory_portion(fixture))

    def test_flow_fixture_alone_does_not_unlock_downstream_gates(self):
        fixture = flow_fixture()
        downstream_gates = {
            "memory_clean_from_flow_alone": False,
            "retrieval_unlocked": False,
            "paper_decision_created": False,
            "buy_unlocked": False,
            "paper_position_created": False,
            "paper_trade_event_created": False,
            "pnl_created": False,
        }
        self.assertTrue(flow_fixture_can_support_clean_memory_portion(fixture))
        self.assertTrue(all(value is False for value in downstream_gates.values()))


if __name__ == "__main__":
    unittest.main()

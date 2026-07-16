"""V2-9.4.5 outcome / evidence-quality separation fixtures.

The Memory Factory guide is explicit: "Clean memory is evidence quality plus
outcome clarity, not price performance", and the anti-bias rule forbids
winner-only memory. Attempt 6 produced the inverse: 61/61 snapshots, clean
cadence, exact continuity and a successful forced close were marked
DIRTY_MEMORY solely because the price round-tripped.

These fixtures prove the corrected contract:
  * market outcome (path / volatility / direction / magnitude) never degrades
    evidence quality;
  * every genuine dirty and audit-only gate still fires unchanged.

Fixture-only. No live sources, no proof runtime, no persistent DB writes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from printer_v1.chart_volatility.classifier import (
    chart_context_can_support_clean_memory,
    classify_candle_path,
    classify_chart_memory_gate,
    classify_chart_payload_quality,
    classify_volatility,
)
from printer_v1.chart_volatility.contracts import (
    CandlePathLabel,
    ChartMemoryGateLabel,
    ChartPayloadQualityLabel,
    VolatilityLabel,
)
from printer_v1.chart_volatility.lookup import (
    chart_volatility_snapshot_blocks_clean_memory,
)
from printer_v1.chart_volatility.parser import normalize_chart_payload
from printer_v1.memory.contracts import (
    EpisodeOutcomeLabel,
    MemoryQualityLabel,
    MemoryRejectionReasonLabel,
)
from printer_v1.memory.quality import (
    build_rejection_reasons,
    classify_memory_quality,
    evaluate_context_quality_gate,
    evaluate_realism_gate,
    evaluate_snapshot_coverage_gate,
    evaluate_source_quality_gate,
)

NOW = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)

# Price paths. Only OHLC differs; evidence is complete and clean in every case.
ROUND_TRIP_OHLC = {"open": 1.0, "high": 1.1, "low": 0.15, "close": 0.15}
DUMP_OHLC = {"open": 1.0, "high": 1.02, "low": 0.30, "close": 0.32}
PUMP_AND_DUMP_OHLC = {"open": 1.0, "high": 1.05, "low": 0.2, "close": 0.2}
EXTREME_OHLC = {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.0}
CALM_OHLC = {"open": 1.0, "high": 1.05, "low": 0.98, "close": 1.03}


def _chart_payload(ohlc: dict, *, source_status=None, data_quality=None):
    base = {
        "token": {"token_id": 1, "mint": "sep-mint"},
        "pair": {"pair_id": 1, "pair_address": "sep-pair"},
        "captured_at": NOW.isoformat(),
        "ohlc": {
            "start_at": (NOW - timedelta(minutes=15)).isoformat(),
            "end_at": NOW.isoformat(),
            "open": 1.0, "high": 1.35, "low": 0.95, "close": 1.25,
        },
        "candles": {
            "candle_count": 6, "green_candle_count": 4, "red_candle_count": 2,
            "flat_candle_count": 0, "consecutive_green_candles": 3,
            "consecutive_red_candles": 1,
        },
        "source": {"source_status": "COMPLETE", "data_quality_label": "CLEAN_DATA"},
    }
    base["ohlc"].update(ohlc)
    payload = normalize_chart_payload(base, NOW)
    # Source status/quality are asserted on the normalized payload (same shape
    # the engine's own fixtures use).
    if source_status is not None:
        payload["source_status"] = source_status
    if data_quality is not None:
        payload["data_quality_label"] = data_quality
    return payload


def _clean_context(**overrides):
    """A context whose every evidence axis is trustworthy."""
    context = {
        "safety_status_label": "SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY",
        "safety_payload_quality_label": "SAFETY_CONTEXT_CLEAN",
        "realism_gate_label": "REALISM_CONTEXT_ACCEPTABLE",
        "flow_memory_gate_label": "FLOW_CONTEXT_ACCEPTABLE",
        "chart_memory_gate_label": "CHART_CONTEXT_ACCEPTABLE",
        "market_payload_quality_label": "MARKET_CONTEXT_CLEAN",
        "chain_heat_payload_quality_label": "CHAIN_HEAT_CONTEXT_CLEAN",
    }
    context.update(overrides)
    return context


def _snapshots(count=6):
    return [{"price_usd": 1.0, "liquidity_usd": 10_000.0} for _ in range(count)]


def _quality_for(chart_payload, *, outcome, context_overrides=None,
                 snapshots=None, sources=None, realism=None):
    """Run the real gate chain end-to-end and return the memory quality."""
    context = _clean_context(
        chart_memory_gate_label=classify_chart_memory_gate(chart_payload, NOW).value,
        **(context_overrides or {}),
    )
    reasons = build_rejection_reasons(
        evaluate_snapshot_coverage_gate(snapshots if snapshots is not None else _snapshots()),
        evaluate_source_quality_gate(sources if sources is not None else [
            {"source_status": "COMPLETE", "data_quality_label": "CLEAN_DATA"}
        ]),
        evaluate_context_quality_gate(context),
        evaluate_realism_gate(outcome, realism or {}),
    )
    return classify_memory_quality(outcome_label=outcome, rejection_reasons=reasons), reasons


class OutcomeEvidenceSeparationTests(unittest.TestCase):

    # --- outcome must never degrade evidence quality ---------------------

    def test_fully_evidenced_round_trip_is_clean_and_outcome_preserved(self):
        payload = _chart_payload(ROUND_TRIP_OHLC)
        # Outcome is preserved truthfully.
        self.assertEqual(classify_candle_path(payload), CandlePathLabel.PATH_ROUND_TRIP)
        # Evidence is trustworthy and not gated on the outcome.
        self.assertEqual(
            classify_chart_payload_quality(payload, NOW),
            ChartPayloadQualityLabel.CHART_CONTEXT_CLEAN,
        )
        self.assertEqual(
            classify_chart_memory_gate(payload, NOW),
            ChartMemoryGateLabel.CHART_CONTEXT_ACCEPTABLE,
        )
        quality, reasons = _quality_for(payload, outcome=EpisodeOutcomeLabel.ROUND_TRIP)
        self.assertEqual(quality, MemoryQualityLabel.CLEAN_MEMORY)
        self.assertEqual(reasons, [])
        # do_not_train=0 is expressed by CLEAN_MEMORY being trainable.
        self.assertNotIn(
            MemoryRejectionReasonLabel.REJECT_DIRTY_CHART_CONTEXT.value, reasons
        )

    def test_fully_evidenced_dump_and_pump_and_dump_are_clean(self):
        for ohlc, outcome in (
            (DUMP_OHLC, EpisodeOutcomeLabel.DUMP),
            (PUMP_AND_DUMP_OHLC, EpisodeOutcomeLabel.PUMP_AND_DUMP),
        ):
            with self.subTest(outcome=outcome):
                payload = _chart_payload(ohlc)
                quality, reasons = _quality_for(payload, outcome=outcome)
                self.assertEqual(quality, MemoryQualityLabel.CLEAN_MEMORY)
                self.assertEqual(reasons, [])

    def test_extreme_volatility_with_trustworthy_evidence_is_not_dirty(self):
        payload = _chart_payload(EXTREME_OHLC)
        self.assertEqual(classify_volatility(payload), VolatilityLabel.VOLATILITY_EXTREME)
        self.assertNotEqual(
            classify_chart_memory_gate(payload, NOW),
            ChartMemoryGateLabel.CHART_CONTEXT_DO_NOT_TRAIN,
        )
        self.assertTrue(chart_context_can_support_clean_memory(payload, NOW))
        quality, reasons = _quality_for(payload, outcome=EpisodeOutcomeLabel.ROUND_TRIP)
        self.assertNotEqual(quality, MemoryQualityLabel.DIRTY_MEMORY)
        self.assertEqual(reasons, [])

    def test_no_price_path_or_volatility_label_reaches_a_rejection_reason(self):
        """No outcome label may directly produce DIRTY_MEMORY."""
        for ohlc in (ROUND_TRIP_OHLC, DUMP_OHLC, PUMP_AND_DUMP_OHLC, EXTREME_OHLC, CALM_OHLC):
            with self.subTest(ohlc=ohlc):
                payload = _chart_payload(ohlc)
                context = _clean_context(
                    chart_memory_gate_label=classify_chart_memory_gate(payload, NOW).value
                )
                self.assertEqual(evaluate_context_quality_gate(context), [])

    def test_stored_snapshot_lookup_no_longer_blocks_on_outcome(self):
        for path, volatility in (
            ("PATH_ROUND_TRIP", "VOLATILITY_EXTREME"),
            ("PATH_GRIND_DOWN", "VOLATILITY_HIGH"),
        ):
            with self.subTest(path=path):
                self.assertFalse(
                    chart_volatility_snapshot_blocks_clean_memory({
                        "chart_memory_gate_label": "CHART_CONTEXT_ACCEPTABLE",
                        "volatility_label": volatility,
                        "candle_path_label": path,
                    })
                )
        # A genuine evidence fault still blocks.
        self.assertTrue(
            chart_volatility_snapshot_blocks_clean_memory({
                "chart_memory_gate_label": "CHART_CONTEXT_DO_NOT_TRAIN",
                "volatility_label": "VOLATILITY_LOW",
                "candle_path_label": "PATH_STEADY_CLIMB",
            })
        )

    # --- genuine dirty / audit-only gates must be preserved ---------------

    def test_missing_price_or_liquidity_remains_dirty(self):
        for field in ("price_usd", "liquidity_usd"):
            with self.subTest(missing=field):
                snapshots = _snapshots()
                snapshots[2] = dict(snapshots[2])
                snapshots[2][field] = None
                quality, reasons = _quality_for(
                    _chart_payload(ROUND_TRIP_OHLC),
                    outcome=EpisodeOutcomeLabel.ROUND_TRIP,
                    snapshots=snapshots,
                )
                self.assertEqual(quality, MemoryQualityLabel.DIRTY_MEMORY)
                self.assertIn(
                    MemoryRejectionReasonLabel.REJECT_MISSING_CRITICAL_FIELDS.value, reasons
                )

    def test_insufficient_coverage_remains_dirty(self):
        quality, reasons = _quality_for(
            _chart_payload(ROUND_TRIP_OHLC),
            outcome=EpisodeOutcomeLabel.ROUND_TRIP,
            snapshots=[{"price_usd": 1.0, "liquidity_usd": 1.0}],
        )
        self.assertEqual(quality, MemoryQualityLabel.DIRTY_MEMORY)
        self.assertIn(MemoryRejectionReasonLabel.REJECT_MISSING_SNAPSHOTS.value, reasons)

    def test_stale_or_conflicting_source_remains_audit_only(self):
        for status, quality_label in (
            ("STALE", "STALE_DATA"),
            ("CONFLICTING", "CONFLICTING_DATA"),
        ):
            with self.subTest(status=status):
                quality, reasons = _quality_for(
                    _chart_payload(ROUND_TRIP_OHLC),
                    outcome=EpisodeOutcomeLabel.ROUND_TRIP,
                    sources=[{"source_status": status, "data_quality_label": quality_label}],
                )
                self.assertEqual(quality, MemoryQualityLabel.AUDIT_ONLY_MEMORY)
                self.assertTrue(reasons)

    def test_stale_chart_evidence_still_gates_as_audit_only(self):
        stale = _chart_payload(ROUND_TRIP_OHLC, source_status="STALE", data_quality="STALE_DATA")
        self.assertEqual(
            classify_chart_memory_gate(stale, NOW),
            ChartMemoryGateLabel.CHART_CONTEXT_AUDIT_ONLY,
        )
        self.assertFalse(chart_context_can_support_clean_memory(stale, NOW))

    def test_failed_chart_source_still_gates_do_not_train(self):
        failed = _chart_payload(
            ROUND_TRIP_OHLC, source_status="FAILED", data_quality="MISSING_CRITICAL_DATA"
        )
        self.assertEqual(
            classify_chart_memory_gate(failed, NOW),
            ChartMemoryGateLabel.CHART_CONTEXT_DO_NOT_TRAIN,
        )
        quality, reasons = _quality_for(failed, outcome=EpisodeOutcomeLabel.ROUND_TRIP)
        self.assertEqual(quality, MemoryQualityLabel.DIRTY_MEMORY)
        self.assertIn(
            MemoryRejectionReasonLabel.REJECT_DIRTY_CHART_CONTEXT.value, reasons
        )

    def test_mandatory_safety_failure_remains_blocked(self):
        for label in ("SAFETY_UNSAFE", "SAFETY_DO_NOT_USE_FOR_MEMORY"):
            with self.subTest(label=label):
                quality, reasons = _quality_for(
                    _chart_payload(ROUND_TRIP_OHLC),
                    outcome=EpisodeOutcomeLabel.ROUND_TRIP,
                    context_overrides={"safety_status_label": label},
                )
                self.assertEqual(quality, MemoryQualityLabel.DIRTY_MEMORY)
                self.assertIn(
                    MemoryRejectionReasonLabel.REJECT_UNSAFE_TOKEN.value, reasons
                )

    def test_dirty_safety_context_remains_blocked(self):
        quality, reasons = _quality_for(
            _chart_payload(ROUND_TRIP_OHLC),
            outcome=EpisodeOutcomeLabel.ROUND_TRIP,
            context_overrides={"safety_payload_quality_label": "SAFETY_CONTEXT_STALE"},
        )
        self.assertEqual(quality, MemoryQualityLabel.DIRTY_MEMORY)
        self.assertIn(
            MemoryRejectionReasonLabel.REJECT_DIRTY_SAFETY_CONTEXT.value, reasons
        )

    def test_outcome_unknown_remains_audit_only(self):
        quality, _ = _quality_for(
            _chart_payload(CALM_OHLC), outcome=EpisodeOutcomeLabel.OUTCOME_UNKNOWN
        )
        self.assertEqual(quality, MemoryQualityLabel.AUDIT_ONLY_MEMORY)

    def test_unrealistic_profit_remains_audit_only(self):
        quality, reasons = _quality_for(
            _chart_payload(CALM_OHLC), outcome=EpisodeOutcomeLabel.UNREALISTIC_PROFIT
        )
        self.assertEqual(quality, MemoryQualityLabel.AUDIT_ONLY_MEMORY)
        self.assertIn(MemoryRejectionReasonLabel.REJECT_UNREALISTIC_EXIT.value, reasons)

    def test_profit_claim_without_realistic_entry_and_exit_remains_audit_only(self):
        quality, reasons = _quality_for(
            _chart_payload(CALM_OHLC),
            outcome=EpisodeOutcomeLabel.REALISTIC_PAPER_PROFIT,
            realism={"entry_realism_label": "ENTRY_REALISTIC", "exit_realism_label": "EXIT_UNKNOWN"},
        )
        self.assertEqual(quality, MemoryQualityLabel.AUDIT_ONLY_MEMORY)
        self.assertIn(MemoryRejectionReasonLabel.REJECT_UNREALISTIC_EXIT.value, reasons)

    def test_flow_wash_like_remains_do_not_train(self):
        """Authenticity, not performance: wash-like flow still blocks."""
        quality, reasons = _quality_for(
            _chart_payload(CALM_OHLC),
            outcome=EpisodeOutcomeLabel.CONSOLIDATION,
            context_overrides={"flow_memory_gate_label": "FLOW_CONTEXT_DO_NOT_TRAIN"},
        )
        self.assertEqual(quality, MemoryQualityLabel.DIRTY_MEMORY)
        self.assertIn(
            MemoryRejectionReasonLabel.REJECT_DIRTY_FLOW_CONTEXT.value, reasons
        )

    def test_partial_trading_flow_is_not_silently_cleaned(self):
        """Partial flow stays honestly partial; this lane does not decide its
        optionality for overall clean promotion."""
        from printer_v1.trading_flow.classifier import classify_flow_memory_gate
        from printer_v1.trading_flow.contracts import FlowMemoryGateLabel
        partial = {
            "captured_at": NOW.isoformat(),
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
            "buys_5m": 170, "sells_5m": 63, "txns_5m": 233, "volume_5m": 1125.0,
            "liquidity_usd": 272141.0, "price_usd": 0.00265,
            # Provider limitation: split volume and unique wallets absent.
            "buy_volume_5m": None, "sell_volume_5m": None, "unique_wallets_5m": None,
        }
        gate = classify_flow_memory_gate(partial, NOW)
        self.assertNotEqual(gate, FlowMemoryGateLabel.FLOW_CONTEXT_ACCEPTABLE)
        self.assertNotEqual(gate, FlowMemoryGateLabel.FLOW_CONTEXT_DO_NOT_TRAIN)

    def test_incomplete_coverage_flag_still_forces_dirty(self):
        quality = classify_memory_quality(
            outcome_label=EpisodeOutcomeLabel.ROUND_TRIP,
            rejection_reasons=[],
            coverage_is_complete=False,
        )
        self.assertEqual(quality, MemoryQualityLabel.DIRTY_MEMORY)


if __name__ == "__main__":
    unittest.main()

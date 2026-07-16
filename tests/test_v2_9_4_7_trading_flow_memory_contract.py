"""V2-9.4.7 -- the trading-flow clean-memory contract.

Flow is a memory label, not a standalone signal (AGENTS.md:549). Clean memory
requires flow evidence "where relevant" (memory-factory-guide:593), and optional
context that no provider supplies is recorded as explicitly unknown, never
invented (solana-builder README:103, source-governor-evidence-rules:108).

No adapter in src/printer_v1/sources/ supplies split buy/sell volume or wallet
participation, so those are optional context. Their absence alone must not make
otherwise trustworthy evidence dirty. Every authenticity, provenance, freshness
and coverage fault must still fail closed.

Paper-only. No live sources, no retrieval, no financial deltas.
"""

import pathlib
import sys
import unittest
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from printer_v1.memory.contracts import (
    EpisodeOutcomeLabel,
    MemoryQualityLabel,
    MemoryRejectionReasonLabel,
)
from printer_v1.memory.quality import (
    build_rejection_reasons,
    classify_memory_quality,
    evaluate_context_quality_gate,
    evaluate_snapshot_coverage_gate,
    evaluate_source_quality_gate,
)
from printer_v1.trading_flow.classifier import (
    classify_flow_direction,
    classify_flow_memory_gate,
    classify_flow_pressure,
    classify_imbalance,
    classify_trading_flow_payload_quality,
    classify_wallet_participation,
    trading_flow_context_can_support_clean_memory,
)
from printer_v1.trading_flow.contracts import (
    FlowDirectionLabel,
    FlowMemoryGateLabel,
    TradingFlowPayloadQualityLabel,
    WalletParticipationLabel,
)
from printer_v1.trading_flow.parser import normalize_trading_flow_payload

NOW = datetime(2026, 7, 13, 16, 0, tzinfo=timezone.utc)

# The fields no current adapter supplies. Proved by inspection of
# src/printer_v1/sources/dexscreener.py and a grep across src/printer_v1/sources.
OPTIONAL_UNAVAILABLE_FIELDS = (
    "buy_volume_5m",
    "sell_volume_5m",
    "buy_volume_15m",
    "sell_volume_15m",
    "unique_wallets_5m",
    "unique_wallets_15m",
    "new_wallets_5m",
    "repeat_wallets_5m",
)


class TradingFlowMemoryContractTest(unittest.TestCase):
    maxDiff = None

    def dexscreener_shaped(self, **overrides):
        """Exactly what DexScreener supplies: counts, no split volume, no wallets."""
        payload = {
            "token_id": 1,
            "pair_id": 1,
            "token_mint": "flow-mint",
            "pair_address": "flow-pair",
            "captured_at": NOW.isoformat(),
            "price_usd": 1.0,
            "liquidity_usd": 120_000,
            "volume_5m": 30_000,
            "volume_15m": 80_000,
            "txns_5m": 60,
            "txns_15m": 150,
            "buys_5m": 40,
            "sells_5m": 20,
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
        }
        payload.update(overrides)
        return normalize_trading_flow_payload(payload, NOW)

    def fully_evidenced(self, **overrides):
        base = {
            "buy_volume_5m": 20_000.0,
            "sell_volume_5m": 10_000.0,
            "unique_wallets_5m": 25,
        }
        base.update(overrides)
        return self.dexscreener_shaped(**base)

    def memory_quality(self, flow_payload, *, outcome, snapshots=None, coverage=True, realism=None):
        """Run flow evidence through the real memory-quality gates."""
        snapshots = snapshots if snapshots is not None else [
            {"price_usd": 1.0, "liquidity_usd": 100_000, "source_status": "COMPLETE", "data_quality_label": "CLEAN_DATA"},
            {"price_usd": 1.1, "liquidity_usd": 101_000, "source_status": "COMPLETE", "data_quality_label": "CLEAN_DATA"},
        ]
        context = {
            "safety_status_label": "SAFETY_CLEAN",
            "safety_payload_quality_label": "SAFETY_CONTEXT_CLEAN",
            "realism_gate_label": "REALISM_CONTEXT_ACCEPTABLE",
            "flow_memory_gate_label": classify_flow_memory_gate(flow_payload, NOW).value,
            "chart_memory_gate_label": "CHART_CONTEXT_ACCEPTABLE",
            "market_payload_quality_label": "MARKET_CONTEXT_CLEAN",
            "chain_heat_payload_quality_label": "CHAIN_HEAT_CONTEXT_CLEAN",
        }
        reasons = build_rejection_reasons(
            evaluate_snapshot_coverage_gate(snapshots),
            evaluate_source_quality_gate(snapshots + [flow_payload]),
            evaluate_context_quality_gate(context),
        )
        return classify_memory_quality(
            outcome_label=outcome, rejection_reasons=reasons, coverage_is_complete=coverage
        ), reasons

    # --- 1. optional fields absent: partial but clean-capable --------------

    def test_optional_fields_absent_are_explicit_unknown_and_still_clean(self):
        payload = self.dexscreener_shaped()
        # Optional context is explicitly unknown, never invented.
        for field in OPTIONAL_UNAVAILABLE_FIELDS:
            self.assertIsNone(payload[field], field)
        self.assertEqual(
            classify_wallet_participation(payload), WalletParticipationLabel.WALLETS_UNKNOWN
        )
        # The flow section stays visibly partial...
        self.assertEqual(
            classify_trading_flow_payload_quality(payload, NOW),
            TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_PARTIAL,
        )
        self.assertEqual(
            classify_flow_memory_gate(payload, NOW), FlowMemoryGateLabel.FLOW_CONTEXT_CAUTION
        )
        # ...while still supporting clean memory.
        self.assertTrue(trading_flow_context_can_support_clean_memory(payload, NOW))
        quality, reasons = self.memory_quality(payload, outcome=EpisodeOutcomeLabel.DUMP)
        self.assertEqual(quality, MemoryQualityLabel.CLEAN_MEMORY)
        self.assertNotIn(MemoryRejectionReasonLabel.REJECT_DIRTY_FLOW_CONTEXT.value, reasons)

    def test_mandatory_flow_facts_are_still_derived_from_counts(self):
        payload = self.dexscreener_shaped()
        # Direction and pressure are derivable from persisted count facts alone.
        self.assertNotEqual(classify_flow_direction(payload), FlowDirectionLabel.FLOW_UNKNOWN)
        self.assertNotEqual(classify_flow_pressure(payload).value, "PRESSURE_UNKNOWN")
        self.assertNotEqual(classify_imbalance(payload).value, "IMBALANCE_UNKNOWN")

    # --- 2/3. outcome stays independent of evidence quality ---------------

    def test_fully_evidenced_round_trip_is_clean_with_outcome_preserved(self):
        payload = self.fully_evidenced()
        quality, reasons = self.memory_quality(payload, outcome=EpisodeOutcomeLabel.ROUND_TRIP)
        self.assertEqual(quality, MemoryQualityLabel.CLEAN_MEMORY)
        self.assertEqual(reasons, [])

    def test_fully_evidenced_negative_outcomes_are_clean_and_truthful(self):
        for outcome in (
            EpisodeOutcomeLabel.ROUND_TRIP,
            EpisodeOutcomeLabel.DUMP,
            EpisodeOutcomeLabel.PUMP_AND_DUMP,
            EpisodeOutcomeLabel.MISSED_UPSIDE,
            EpisodeOutcomeLabel.DEAD_TOKEN,
        ):
            with self.subTest(outcome=outcome):
                quality, _ = self.memory_quality(self.dexscreener_shaped(), outcome=outcome)
                # A negative outcome is a clean, retained lesson -- never
                # reinterpreted and never downgraded for being unfavourable.
                self.assertEqual(quality, MemoryQualityLabel.CLEAN_MEMORY)

    # --- 4. missing mandatory evidence ------------------------------------

    def test_missing_mandatory_identity_or_flow_fact_is_not_clean(self):
        no_identity = self.dexscreener_shaped(token_id=None, token_mint=None)
        no_flow_fact = self.dexscreener_shaped(
            volume_5m=None, volume_15m=None, txns_5m=None, txns_15m=None,
            buys_5m=None, sells_5m=None,
        )
        for name, payload in (("no_identity", no_identity), ("no_flow_fact", no_flow_fact)):
            with self.subTest(case=name):
                self.assertEqual(
                    classify_trading_flow_payload_quality(payload, NOW),
                    TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_UNKNOWN,
                )
                self.assertEqual(
                    classify_flow_memory_gate(payload, NOW),
                    FlowMemoryGateLabel.FLOW_CONTEXT_AUDIT_ONLY,
                )
                self.assertFalse(trading_flow_context_can_support_clean_memory(payload, NOW))

    # --- 5. failed / stale / conflicting ----------------------------------

    def test_failed_stale_conflicting_sources_still_fail_closed(self):
        cases = {
            "dirty": (self.dexscreener_shaped(data_quality_label="DIRTY_DATA"), MemoryQualityLabel.DIRTY_MEMORY),
            "failed": (self.dexscreener_shaped(source_status="FAILED"), MemoryQualityLabel.DIRTY_MEMORY),
            "stale_source": (self.dexscreener_shaped(source_status="STALE"), MemoryQualityLabel.AUDIT_ONLY_MEMORY),
            "conflicting": (self.dexscreener_shaped(source_status="CONFLICTING"), MemoryQualityLabel.AUDIT_ONLY_MEMORY),
            "stale_by_age": (
                self.dexscreener_shaped(captured_at=(NOW - timedelta(hours=3)).isoformat()),
                None,
            ),
        }
        for name, (payload, expected) in cases.items():
            with self.subTest(case=name):
                self.assertFalse(trading_flow_context_can_support_clean_memory(payload, NOW))
                if expected is not None:
                    quality, _ = self.memory_quality(payload, outcome=EpisodeOutcomeLabel.DUMP)
                    self.assertEqual(quality, expected)

    # --- 6. insufficient exact-ledger coverage ----------------------------

    def test_insufficient_ledger_coverage_is_dirty(self):
        payload = self.dexscreener_shaped()
        one_snapshot = [{"price_usd": 1.0, "liquidity_usd": 100_000, "source_status": "COMPLETE", "data_quality_label": "CLEAN_DATA"}]
        quality, reasons = self.memory_quality(
            payload, outcome=EpisodeOutcomeLabel.DUMP, snapshots=one_snapshot
        )
        self.assertEqual(quality, MemoryQualityLabel.DIRTY_MEMORY)
        self.assertIn(MemoryRejectionReasonLabel.REJECT_MISSING_SNAPSHOTS.value, reasons)
        # And an explicitly incomplete coverage flag is dirty regardless.
        incomplete, _ = self.memory_quality(
            payload, outcome=EpisodeOutcomeLabel.DUMP, coverage=False
        )
        self.assertEqual(incomplete, MemoryQualityLabel.DIRTY_MEMORY)

    def test_missing_critical_snapshot_fields_are_dirty(self):
        payload = self.dexscreener_shaped()
        snapshots = [
            {"price_usd": 1.0, "liquidity_usd": None, "source_status": "COMPLETE", "data_quality_label": "CLEAN_DATA"},
            {"price_usd": 1.1, "liquidity_usd": 101_000, "source_status": "COMPLETE", "data_quality_label": "CLEAN_DATA"},
        ]
        quality, reasons = self.memory_quality(
            payload, outcome=EpisodeOutcomeLabel.DUMP, snapshots=snapshots
        )
        self.assertEqual(quality, MemoryQualityLabel.DIRTY_MEMORY)
        self.assertIn(MemoryRejectionReasonLabel.REJECT_MISSING_CRITICAL_FIELDS.value, reasons)

    # --- 7. authenticity ---------------------------------------------------

    def test_wash_like_flow_remains_do_not_train(self):
        wash = self.dexscreener_shaped(unique_wallets_5m=2, repeat_wallets_5m=8)
        self.assertEqual(classify_flow_direction(wash), FlowDirectionLabel.FLOW_WASH_LIKE)
        self.assertEqual(
            classify_flow_memory_gate(wash, NOW), FlowMemoryGateLabel.FLOW_CONTEXT_DO_NOT_TRAIN
        )
        self.assertFalse(trading_flow_context_can_support_clean_memory(wash, NOW))
        quality, reasons = self.memory_quality(wash, outcome=EpisodeOutcomeLabel.DUMP)
        self.assertEqual(quality, MemoryQualityLabel.DIRTY_MEMORY)
        self.assertIn(MemoryRejectionReasonLabel.REJECT_DIRTY_FLOW_CONTEXT.value, reasons)

    # --- 8. contradictory flow evidence ------------------------------------

    def test_contradictory_flow_evidence_is_reported_as_noisy(self):
        # Counts say buy-heavy, volume says sell-heavy: the two disagree.
        contradictory = self.dexscreener_shaped(
            buys_5m=60, sells_5m=20, buy_volume_5m=5_000.0, sell_volume_5m=50_000.0
        )
        self.assertEqual(classify_imbalance(contradictory).value, "IMBALANCE_NOISY")
        self.assertNotEqual(
            classify_flow_direction(contradictory), FlowDirectionLabel.FLOW_ACCUMULATION
        )

    # --- 9. never invent or default to zero --------------------------------

    def test_unavailable_fields_are_never_invented_or_defaulted_to_zero(self):
        payload = self.dexscreener_shaped()
        for field in OPTIONAL_UNAVAILABLE_FIELDS:
            self.assertIsNone(payload[field], f"{field} must stay None, never 0 or estimated")
            self.assertNotEqual(payload[field], 0)

    def test_observed_zero_is_distinct_from_unknown(self):
        """A real (0,0) is a fact; absent fields are not."""
        observed_zero = self.dexscreener_shaped(buys_5m=0, sells_5m=0)
        self.assertEqual(observed_zero["buys_5m"], 0)
        self.assertEqual(classify_imbalance(observed_zero).value, "IMBALANCE_BALANCED")
        unknown = self.dexscreener_shaped(buys_5m=None, sells_5m=None)
        self.assertIsNone(unknown["buys_5m"])
        # Unknown must not be silently read as a balanced observation.
        self.assertEqual(classify_imbalance(unknown).value, "IMBALANCE_UNKNOWN")

    # --- 10. no retrieval or financial unlock ------------------------------

    def test_flow_contract_unlocks_nothing(self):
        payload = self.dexscreener_shaped()
        quality, _ = self.memory_quality(payload, outcome=EpisodeOutcomeLabel.DUMP)
        self.assertEqual(quality, MemoryQualityLabel.CLEAN_MEMORY)
        # Clean memory is a training-eligibility statement only. It is not a
        # decision, a position, or a trade.
        from printer_v1.memory.quality import memory_can_train_decisions

        self.assertTrue(memory_can_train_decisions(quality))
        self.assertFalse(memory_can_train_decisions(MemoryQualityLabel.DIRTY_MEMORY))
        self.assertFalse(memory_can_train_decisions(MemoryQualityLabel.AUDIT_ONLY_MEMORY))


if __name__ == "__main__":
    unittest.main()

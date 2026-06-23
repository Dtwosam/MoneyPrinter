import argparse
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import (
    build_collect_context_once_payload,
    build_collect_token_snapshots_once_payload,
    build_manual_intake_token_pair_payload,
    build_memory_quality_audit_once_payload,
    build_memory_window_once_payload,
    build_retrieve_clean_memory_once_payload,
)
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.governed_execution import (
    build_fixture_source_adapter,
    execute_source_request_with_governor,
)


def count_rows(connection, table):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


class PostRCCleanContextBlockerReviewTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "clean-context-review.sqlite3"
        apply_migrations(self.db_path)
        self.base_time = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tempdir.cleanup()

    def args(self, **overrides):
        values = {
            "db_path": str(self.db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "token_mint": "clean-context-mint",
            "token_id": None,
            "pair_address": "clean-context-pair",
            "pair_id": None,
            "snapshot_id": None,
            "memory_window_id": None,
            "episode_id": None,
            "chain": "solana",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def transport_with_context_fields(self, context):
        del context
        return {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": "clean-context-pair",
                    "baseToken": {"address": "clean-context-mint", "symbol": "CTX", "name": "Clean Context"},
                    "priceUsd": "0.00050",
                    "liquidity": {"usd": 31000.0},
                    "volume": {"m5": 15000.0, "h1": 85000.0, "h24": 320000.0},
                    "txns": {"m5": {"buys": 42, "sells": 18}, "h1": {"buys": 190, "sells": 72}},
                    "fdv": 500000.0,
                    "marketCap": 455000.0,
                    "priceChange": {"m5": 14.0, "h1": 24.0, "h24": 35.0},
                }
            ]
        }

    def transport_missing_context_fields(self, context):
        del context
        return {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": "clean-context-pair",
                    "baseToken": {"address": "clean-context-mint", "symbol": "CTX", "name": "Clean Context"},
                    "priceUsd": "0.00050",
                    "liquidity": {"usd": 31000.0},
                    "fdv": 500000.0,
                    "marketCap": 455000.0,
                }
            ]
        }

    def seed_snapshots(self, count=6, *, transport=None):
        build_manual_intake_token_pair_payload(self.args(
            pair_id=None,
            pool_address=None,
            intake_reason="pre lane7 clean context blocker review",
            source_reference="clean-context-intake",
            source_request_id=None,
            token_symbol="CTX",
            token_name="Clean Context",
            dex_id="dexscreener",
            intake_json=None,
        ))
        for index in range(count):
            build_collect_token_snapshots_once_payload(self.args(
                snapshot_count=1,
                max_seconds=5.0,
                source_name="dexscreener",
                source_reference=f"clean-context-snapshot-{index}",
            ), transport=transport or self.transport_with_context_fields)
        with self.connect() as connection:
            rows = connection.execute("SELECT id FROM printer_token_snapshots ORDER BY id ASC").fetchall()
            snapshot_ids = [int(row["id"]) for row in rows]
            for offset, snapshot_id in enumerate(snapshot_ids):
                captured_at = (self.base_time + timedelta(minutes=offset * 3)).isoformat()
                row = connection.execute(
                    "SELECT normalized_snapshot_payload_json FROM printer_token_snapshots WHERE id = ?",
                    (snapshot_id,),
                ).fetchone()
                normalized = json.loads(row["normalized_snapshot_payload_json"] or "{}")
                normalized["captured_at"] = captured_at
                connection.execute(
                    """
                    UPDATE printer_token_snapshots
                    SET captured_at = ?, normalized_snapshot_payload_json = ?
                    WHERE id = ?
                    """,
                    (captured_at, json.dumps(normalized, sort_keys=True), snapshot_id),
                )
        return snapshot_ids

    def collect_context(self, snapshot_id, **overrides):
        return build_collect_context_once_payload(
            self.args(snapshot_id=snapshot_id, source_name="dexscreener", **overrides)
        )

    def governed_source_response_id(self, source_name, request_kind, payload):
        with self.connect() as connection:
            request = build_governed_source_request(
                source_name,
                request_kind,
                request_key=f"{source_name}-{request_kind}-test",
                payload={"test_scope": "post_rc_clean_context"},
                now=self.base_time,
            )
            adapter = build_fixture_source_adapter(source_name, fixture_payload=payload)
            result = execute_source_request_with_governor(
                connection,
                request,
                adapter,
                now=self.base_time,
            )
            self.assertIsNotNone(result.response_record)
            return int(result.response_record.id)

    def memory_payload(self, snapshot_id, source_reference="clean-context-memory"):
        return build_memory_window_once_payload(self.args(
            snapshot_id=snapshot_id,
            memory_window="15m",
            source_reference=source_reference,
        ))

    def audit_payload(self, memory_window_id):
        return build_memory_quality_audit_once_payload(self.args(memory_window_id=memory_window_id))

    def retrieval_payload(self, snapshot_id):
        return build_retrieve_clean_memory_once_payload(self.args(snapshot_id=snapshot_id))

    def force_context_known_for_fixture(self):
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE printer_market_regime_snapshots
                SET market_regime_label = 'RISK_ON',
                    market_transition_label = 'RISK_OFF_TO_RISK_ON',
                    market_payload_quality_label = 'MARKET_CONTEXT_CLEAN',
                    data_quality_label = 'CLEAN_DATA',
                    source_status = 'COMPLETE'
                """
            )
            connection.execute(
                """
                UPDATE printer_solana_chain_heat_snapshots
                SET chain_heat_label = 'SOLANA_WARM',
                    activity_label = 'ACTIVITY_ELEVATED',
                    liquidity_label = 'LIQUIDITY_STABLE',
                    congestion_label = 'CONGESTION_LOW',
                    chain_heat_payload_quality_label = 'CHAIN_HEAT_CONTEXT_CLEAN',
                    data_quality_label = 'CLEAN_DATA',
                    source_status = 'COMPLETE'
                """
            )
            connection.execute(
                """
                UPDATE printer_safety_rug_snapshots
                SET safety_status_label = 'SAFETY_CLEAN',
                    rug_risk_label = 'RUG_RISK_LOW',
                    liquidity_safety_label = 'LIQUIDITY_SAFE',
                    authority_label = 'AUTHORITY_RENOUNCED_OR_SAFE',
                    distribution_label = 'DISTRIBUTION_HEALTHY',
                    safety_payload_quality_label = 'SAFETY_CONTEXT_CLEAN',
                    safety_gate_label = 'ALLOW_SAFETY_CONTEXT',
                    data_quality_label = 'CLEAN_DATA',
                    source_status = 'COMPLETE'
                """
            )
            connection.execute(
                """
                UPDATE printer_liquidity_exit_snapshots
                SET entry_realism_label = 'ENTRY_REALISTIC',
                    exit_realism_label = 'EXIT_REALISTIC',
                    slippage_label = 'SLIPPAGE_LOW',
                    price_impact_label = 'PRICE_IMPACT_LOW',
                    route_label = 'ROUTE_AVAILABLE',
                    quote_age_label = 'QUOTE_FRESH',
                    liquidity_drain_label = 'NO_LIQUIDITY_DRAIN',
                    liquidity_exit_payload_quality_label = 'LIQUIDITY_EXIT_CONTEXT_CLEAN',
                    realism_gate_label = 'REALISM_CONTEXT_ACCEPTABLE',
                    data_quality_label = 'CLEAN_DATA',
                    source_status = 'COMPLETE'
                """
            )
            connection.execute(
                """
                UPDATE printer_trading_flow_snapshots
                SET flow_direction_label = 'FLOW_ACCUMULATION',
                    flow_pressure_label = 'PRESSURE_MODERATE_INFLOW',
                    imbalance_label = 'IMBALANCE_BUY_HEAVY',
                    volume_activity_label = 'VOLUME_NORMAL',
                    tx_activity_label = 'TX_ACTIVITY_NORMAL',
                    wallet_participation_label = 'WALLETS_BROAD_PARTICIPATION',
                    trading_flow_payload_quality_label = 'TRADING_FLOW_CONTEXT_CLEAN',
                    flow_memory_gate_label = 'FLOW_CONTEXT_ACCEPTABLE',
                    data_quality_label = 'CLEAN_DATA',
                    source_status = 'COMPLETE'
                """
            )
            connection.execute(
                """
                UPDATE printer_chart_volatility_snapshots
                SET trend_structure_label = 'TREND_UP',
                    volatility_label = 'VOLATILITY_NORMAL',
                    range_behavior_label = 'RANGE_EXPANDING',
                    momentum_label = 'MOMENTUM_STABLE',
                    drawdown_recovery_label = 'DRAWDOWN_NONE',
                    candle_path_label = 'PATH_STEADY_CLIMB',
                    chart_payload_quality_label = 'CHART_CONTEXT_CLEAN',
                    chart_memory_gate_label = 'CHART_CONTEXT_ACCEPTABLE',
                    data_quality_label = 'CLEAN_DATA',
                    source_status = 'COMPLETE'
                """
            )
            connection.execute(
                """
                UPDATE printer_micro_events
                SET micro_event_state_label = 'NO_MICRO_EVENT',
                    micro_event_move_label = 'MOVE_NO_CLEAR_EVENT',
                    micro_exit_realism_label = 'MICRO_EXIT_REALISTIC',
                    late_buy_trap_label = 'NO_LATE_BUY_TRAP',
                    held_to_15m_result_label = 'HELD_TO_15M_CONSOLIDATED',
                    micro_event_payload_quality_label = 'MICRO_EVENT_CONTEXT_CLEAN',
                    micro_event_memory_gate_label = 'MICRO_EVENT_SUPPORT_EVIDENCE',
                    data_quality_label = 'CLEAN_DATA',
                    source_status = 'COMPLETE'
                """
            )

    def test_fresh_target_matched_context_derives_safe_labels_from_stored_snapshot_fields(self):
        snapshot_ids = self.seed_snapshots()
        self.collect_context(snapshot_ids[-1])

        with self.connect() as connection:
            safety = connection.execute("SELECT * FROM printer_safety_rug_snapshots").fetchone()
            flow = connection.execute("SELECT * FROM printer_trading_flow_snapshots").fetchone()
            chart = connection.execute("SELECT * FROM printer_chart_volatility_snapshots").fetchone()
            micro = connection.execute("SELECT * FROM printer_micro_events").fetchone()

        self.assertEqual(safety["safety_status_label"], "SAFETY_UNKNOWN")
        self.assertNotEqual(safety["liquidity_safety_label"], "LIQUIDITY_SAFETY_UNKNOWN")
        self.assertNotEqual(flow["volume_activity_label"], "VOLUME_UNKNOWN")
        self.assertNotEqual(flow["tx_activity_label"], "TX_ACTIVITY_UNKNOWN")
        self.assertEqual(flow["buys_5m"], 42)
        self.assertEqual(flow["sells_5m"], 18)
        self.assertNotEqual(flow["flow_direction_label"], "FLOW_UNKNOWN")
        self.assertIn(
            flow["flow_pressure_label"],
            {"PRESSURE_MODERATE_INFLOW", "PRESSURE_STRONG_INFLOW"},
        )
        self.assertNotEqual(chart["trend_structure_label"], "TREND_UNKNOWN")
        self.assertIn(micro["micro_event_state_label"], {"FAST_MICRO_PUMP", "NO_MICRO_EVENT", "MICRO_EVENT_UNKNOWN"})
        self.assertEqual(micro["micro_exit_realism_label"], "MICRO_EXIT_UNKNOWN")

    def test_context_collection_consumes_governed_market_and_chain_source_responses(self):
        snapshot_ids = self.seed_snapshots()
        market_response_id = self.governed_source_response_id(
            "coingecko",
            "broad_market_context",
            {
                "captured_at": self.base_time.isoformat(),
                "assets": {
                    "bitcoin": {"price_usd": 65000, "change_24h": 2.4},
                    "solana": {
                        "price_usd": 155,
                        "change_1h": 1.2,
                        "change_24h": 4.2,
                        "volume_24h": 2_000_000_000,
                    },
                },
                "fear_greed": {"value": 62, "label": "Greed"},
            },
        )
        chain_response_id = self.governed_source_response_id(
            "defillama",
            "chain_liquidity_context",
            {
                "captured_at": self.base_time.isoformat(),
                "solana": {
                    "price_usd": 155,
                    "change_24h": 4.2,
                    "volume_24h": 2_000_000_000,
                },
                "network_context": {
                    "active_addresses": 1_200_000,
                    "tx_count_24h": 45_000_000,
                    "congestion_context": "low",
                },
                "liquidity_context": {
                    "tvl_usd": 5_000_000_000,
                    "dex_volume_24h": 1_100_000_000,
                },
                "meme_context": {
                    "hot_pair_count": 35,
                    "meme_volume_24h": 120_000_000,
                    "meme_liquidity_usd": 50_000_000,
                    "meme_new_pair_count": 80,
                },
            },
        )

        self.collect_context(
            snapshot_ids[-1],
            market_source_response_id=market_response_id,
            chain_heat_source_response_id=chain_response_id,
        )

        with self.connect() as connection:
            market = connection.execute("SELECT * FROM printer_market_regime_snapshots").fetchone()
            chain = connection.execute("SELECT * FROM printer_solana_chain_heat_snapshots").fetchone()
            market_payload = json.loads(market["normalized_market_payload_json"])
            chain_payload = json.loads(chain["normalized_chain_heat_payload_json"])

            self.assertNotEqual(market["market_regime_label"], "UNKNOWN")
            self.assertEqual(market["market_payload_quality_label"], "MARKET_CONTEXT_CLEAN")
            self.assertEqual(market_payload["source_response_id"], market_response_id)
            self.assertEqual(market_payload["snapshot_id"], snapshot_ids[-1])

            self.assertNotEqual(chain["chain_heat_label"], "SOLANA_UNKNOWN")
            self.assertEqual(chain["chain_heat_payload_quality_label"], "CHAIN_HEAT_CONTEXT_CLEAN")
            self.assertEqual(chain_payload["source_response_id"], chain_response_id)
            self.assertEqual(chain_payload["snapshot_id"], snapshot_ids[-1])

            self.assertEqual(count_rows(connection, "printer_memory_windows"), 0)
            self.assertEqual(count_rows(connection, "printer_memory_fingerprints"), 0)
            self.assertEqual(count_rows(connection, "printer_memory_retrieval_matches"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_decisions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_positions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_trade_events"), 0)

    def test_missing_fixture_inputs_remain_unknown_and_audit_only(self):
        snapshot_ids = self.seed_snapshots(transport=self.transport_missing_context_fields)
        self.collect_context(snapshot_ids[-1])

        with self.connect() as connection:
            flow = connection.execute("SELECT * FROM printer_trading_flow_snapshots").fetchone()
            chart = connection.execute("SELECT * FROM printer_chart_volatility_snapshots").fetchone()
            micro = connection.execute("SELECT * FROM printer_micro_events").fetchone()

        self.assertEqual(flow["volume_activity_label"], "VOLUME_UNKNOWN")
        self.assertEqual(flow["tx_activity_label"], "TX_ACTIVITY_UNKNOWN")
        self.assertEqual(chart["trend_structure_label"], "TREND_UNKNOWN")
        self.assertEqual(micro["micro_event_state_label"], "MICRO_EVENT_UNKNOWN")

    def test_unknown_context_remains_blocking_and_dirty_memory_does_not_enter_retrieval(self):
        snapshot_ids = self.seed_snapshots()
        self.collect_context(snapshot_ids[-1])
        memory = self.memory_payload(snapshot_ids[-1], "clean-context-unknown-blocked")
        result = memory["memory_result"]

        self.assertEqual(result["coverage_state"], "COMPLETE_WINDOW_COVERAGE")
        self.assertEqual(result["missing_snapshot_count"], 0)
        self.assertIn("MISSING_OR_UNKNOWN_CONTEXT", result["rejection_reasons"])
        self.assertEqual(result["memory_quality_label"], "AUDIT_ONLY_MEMORY")
        self.assertFalse(result["retrieval_ready"])

        retrieval = self.retrieval_payload(snapshot_ids[-1])
        report = retrieval["retrieval_report"]
        self.assertEqual(report["clean_matches_returned"], 0)
        self.assertFalse(report["retrieval_allowed"])
        self.assertFalse(report["paper_decision_allowed"])
        with self.connect() as connection:
            self.assertEqual(count_rows(connection, "printer_paper_decisions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_positions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_trade_events"), 0)

    def test_known_fixture_context_can_make_memory_eligible_only_with_complete_snapshot_evidence(self):
        snapshot_ids = self.seed_snapshots()
        self.collect_context(snapshot_ids[-1])
        self.force_context_known_for_fixture()

        memory = self.memory_payload(snapshot_ids[-1], "clean-context-known-fixture")
        result = memory["memory_result"]

        self.assertEqual(result["coverage_state"], "COMPLETE_WINDOW_COVERAGE")
        self.assertEqual(result["memory_quality_label"], "CLEAN_MEMORY")
        self.assertTrue(result["retrieval_ready"])
        self.assertEqual(result["rejection_reasons"], ["REVIEW_PASSED"])
        with self.connect() as connection:
            self.assertEqual(count_rows(connection, "printer_paper_decisions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_positions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_trade_events"), 0)

    def test_historical_source_failure_is_visible_but_not_current_window_blocking_when_snapshots_are_clean(self):
        snapshot_ids = self.seed_snapshots()
        self.collect_context(snapshot_ids[-1])
        memory = self.memory_payload(snapshot_ids[-1], "clean-context-source-scope")
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO printer_source_failures (
                    source_name, request_kind, failed_at, failure_type,
                    failure_message, source_status, data_quality_label
                ) VALUES (
                    'dexscreener', 'PAIR_SNAPSHOT', datetime('now'),
                    'historical_fixture_failure', 'historical failure remains visible',
                    'FAILED', 'MISSING_CRITICAL_DATA'
                )
                """
            )
        audit = self.audit_payload(memory["memory_result"]["memory_window_id"])
        source_summary = audit["audit_report"]["source_quality_summary"]

        self.assertGreater(source_summary["source_failure_count"], 0)
        self.assertTrue(source_summary["historical_source_failures_visible"])
        self.assertFalse(source_summary["required_evidence_failed_or_missing"])
        self.assertEqual(source_summary["status"], "SOURCE_QUALITY_ACCEPTABLE_WITH_HISTORICAL_FAILURES_VISIBLE")


if __name__ == "__main__":
    unittest.main()

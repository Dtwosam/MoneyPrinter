import pathlib
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.snapshots.recorder import record_token_snapshot
from printer_v1.sources.dexscreener import normalize_dexscreener_fixture_result
from printer_v1.trading_flow.contracts import (
    FlowDirectionLabel,
    FlowMemoryGateLabel,
    FlowPressureLabel,
    TradingFlowPayloadQualityLabel,
)
from printer_v1.trading_flow.recorder import record_trading_flow_from_token_snapshot


FORBIDDEN_FRAGMENTS = (
    "score",
    "ranking",
    "rank",
    "confidence",
    "weighted",
    "weight",
    "private_key",
    "signature",
    "signing",
    "live_execution",
    "live_trading",
)


def dexscreener_payload(*, txns=None, stale=False):
    return {
        "fixture_stale": stale,
        "pairs": [
            {
                "chainId": "solana",
                "pairAddress": "flow-pair",
                "baseToken": {
                    "address": "flow-mint",
                    "symbol": "FLOW",
                    "name": "Flow Fixture",
                },
                "priceUsd": "0.0012",
                "liquidity": {"usd": 123456.0},
                "volume": {"m5": 125000.0, "h1": 900000.0, "h24": 1800000.0},
                "txns": txns
                if txns is not None
                else {
                    "m5": {"buys": 110, "sells": 35},
                    "h1": {"buys": 400, "sells": 120},
                    "h24": {"buys": 1200, "sells": 900},
                },
                "pairCreatedAt": "2026-06-23T00:00:00Z",
            }
        ],
    }


class PostRcFlowDirectionPressureFromExistingPayloadsTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "printer.sqlite3"
        apply_migrations(self.db_path)
        self.now = datetime(2026, 6, 23, 12, 0, tzinfo=timezone.utc)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.seed_token_pair()

    def tearDown(self):
        self.connection.rollback()
        self.connection.close()
        self.tempdir.cleanup()

    def seed_token_pair(self):
        self.connection.execute(
            """
            INSERT INTO printer_tokens (
                id, token_mint, chain, symbol, name, token_status
            ) VALUES (1, 'flow-mint', 'solana', 'FLOW', 'Flow Fixture', 'TRACKING')
            """
        )
        self.connection.execute(
            """
            INSERT INTO printer_pairs (
                id, token_id, pair_address, dex, pool_source
            ) VALUES (1, 1, 'flow-pair', 'raydium', 'fixture')
            """
        )
        self.connection.commit()

    def pair_payload(self, **overrides):
        result = normalize_dexscreener_fixture_result(
            dexscreener_payload(**overrides),
            request_kind="token_pair_snapshot",
        )
        pair = dict(result.normalized_payload["pairs"][0])
        pair.update(
            {
                "token_id": 1,
                "pair_id": 1,
                "captured_at": self.now.isoformat(),
                "tracking_lane": "TRACK_NORMAL",
                "snapshot_mode": "WINDOW_CLOSE_MODE",
                "source_status": result.source_status.value,
                "data_quality_label": result.data_quality_label.value,
            }
        )
        return pair

    def create_snapshot_and_flow(self, pair_payload):
        snapshot_created, snapshot_id = record_token_snapshot(
            self.db_path,
            pair_payload,
            self.now,
        )
        self.assertTrue(snapshot_created)
        flow_created, flow_id = record_trading_flow_from_token_snapshot(
            self.db_path,
            snapshot_id,
            now=self.now,
        )
        self.assertTrue(flow_created)
        return self.connection.execute(
            "SELECT * FROM printer_trading_flow_snapshots WHERE id = ?",
            (flow_id,),
        ).fetchone()

    def table_count(self, table_name):
        return int(self.connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])

    def table_names(self):
        rows = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        return {row[0] for row in rows}

    def test_dexscreener_normalization_preserves_side_aware_txn_counts(self):
        pair = self.pair_payload()

        self.assertEqual(pair["txns_5m"], 145)
        self.assertEqual(pair["buys_5m"], 110)
        self.assertEqual(pair["sells_5m"], 35)
        self.assertEqual(pair["buys_1h"], 400)
        self.assertEqual(pair["sells_1h"], 120)

    def test_buy_dominant_existing_payload_maps_to_accumulation_and_inflow(self):
        flow = self.create_snapshot_and_flow(self.pair_payload())

        self.assertEqual(flow["buys_5m"], 110)
        self.assertEqual(flow["sells_5m"], 35)
        self.assertEqual(flow["flow_direction_label"], FlowDirectionLabel.FLOW_ACCUMULATION.value)
        self.assertEqual(flow["flow_pressure_label"], FlowPressureLabel.PRESSURE_STRONG_INFLOW.value)
        self.assertEqual(
            flow["trading_flow_payload_quality_label"],
            TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_PARTIAL.value,
        )
        self.assertEqual(flow["flow_memory_gate_label"], FlowMemoryGateLabel.FLOW_CONTEXT_CAUTION.value)

    def test_sell_dominant_existing_payload_maps_to_distribution_and_outflow(self):
        payload = self.pair_payload(
            txns={
                "m5": {"buys": 20, "sells": 90},
                "h1": {"buys": 100, "sells": 300},
                "h24": {"buys": 500, "sells": 1200},
            }
        )
        flow = self.create_snapshot_and_flow(payload)

        self.assertEqual(flow["flow_direction_label"], FlowDirectionLabel.FLOW_DISTRIBUTION.value)
        self.assertEqual(flow["flow_pressure_label"], FlowPressureLabel.PRESSURE_STRONG_OUTFLOW.value)

    def test_balanced_existing_payload_maps_to_choppy_and_balanced_pressure(self):
        payload = self.pair_payload(
            txns={
                "m5": {"buys": 50, "sells": 50},
                "h1": {"buys": 200, "sells": 205},
                "h24": {"buys": 1000, "sells": 980},
            }
        )
        flow = self.create_snapshot_and_flow(payload)

        self.assertEqual(flow["flow_direction_label"], FlowDirectionLabel.FLOW_CHOPPY.value)
        self.assertEqual(flow["flow_pressure_label"], FlowPressureLabel.PRESSURE_BALANCED.value)

    def test_observed_zero_side_flow_is_not_missing_bullish_or_bearish(self):
        payload = self.pair_payload(
            txns={
                "m5": {"buys": 0, "sells": 0},
                "h1": {"buys": 7, "sells": 2},
                "h24": {"buys": 438, "sells": 386},
            }
        )
        payload["volume_5m"] = 0
        flow = self.create_snapshot_and_flow(payload)

        self.assertEqual(flow["buys_5m"], 0)
        self.assertEqual(flow["sells_5m"], 0)
        self.assertEqual(flow["flow_direction_label"], FlowDirectionLabel.FLOW_EXHAUSTION.value)
        self.assertEqual(flow["flow_pressure_label"], FlowPressureLabel.PRESSURE_BALANCED.value)
        self.assertNotIn(
            flow["flow_direction_label"],
            {
                FlowDirectionLabel.FLOW_ACCUMULATION.value,
                FlowDirectionLabel.FLOW_DISTRIBUTION.value,
            },
        )
        self.assertEqual(
            flow["trading_flow_payload_quality_label"],
            TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_PARTIAL.value,
        )
        self.assertEqual(flow["flow_memory_gate_label"], FlowMemoryGateLabel.FLOW_CONTEXT_CAUTION.value)

    def test_missing_side_evidence_stays_unknown_or_audit_only(self):
        payload = self.pair_payload(txns={})
        flow = self.create_snapshot_and_flow(payload)

        self.assertEqual(flow["flow_direction_label"], FlowDirectionLabel.FLOW_UNKNOWN.value)
        self.assertEqual(flow["flow_pressure_label"], FlowPressureLabel.PRESSURE_UNKNOWN.value)
        self.assertIn(
            flow["flow_memory_gate_label"],
            {
                FlowMemoryGateLabel.FLOW_CONTEXT_CAUTION.value,
                FlowMemoryGateLabel.FLOW_CONTEXT_AUDIT_ONLY.value,
            },
        )

    def test_stale_failed_and_dirty_evidence_remains_non_clean_unknown_context(self):
        cases = [
            self.pair_payload(stale=True),
            self.pair_payload(
                txns={
                    "m5": {"buys": 110, "sells": 35},
                    "h1": {"buys": 400, "sells": 120},
                    "h24": {"buys": 1200, "sells": 900},
                }
            )
            | {
                "source_status": SourceStatus.FAILED.value,
                "data_quality_label": DataQualityLabel.MISSING_CRITICAL_DATA.value,
                "captured_at": (self.now + timedelta(minutes=1)).isoformat(),
            },
            self.pair_payload()
            | {
                "data_quality_label": DataQualityLabel.DIRTY_DATA.value,
                "captured_at": (self.now + timedelta(minutes=2)).isoformat(),
            },
        ]

        for payload in cases:
            with self.subTest(payload=payload):
                flow = self.create_snapshot_and_flow(payload)
                self.assertEqual(flow["flow_direction_label"], FlowDirectionLabel.FLOW_UNKNOWN.value)
                self.assertEqual(flow["flow_pressure_label"], FlowPressureLabel.PRESSURE_UNKNOWN.value)
                self.assertNotEqual(
                    flow["trading_flow_payload_quality_label"],
                    TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CLEAN.value,
                )
                self.assertIn(
                    flow["flow_memory_gate_label"],
                    {
                        FlowMemoryGateLabel.FLOW_CONTEXT_AUDIT_ONLY.value,
                        FlowMemoryGateLabel.FLOW_CONTEXT_DO_NOT_TRAIN.value,
                    },
                )

    def test_flow_labels_do_not_create_downstream_rows_or_unlocks(self):
        self.create_snapshot_and_flow(self.pair_payload())

        for table_name in (
            "printer_memory_retrieval_matches",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
            "printer_paper_pl_calculations",
        ):
            with self.subTest(table_name=table_name):
                if table_name in self.table_names():
                    self.assertEqual(self.table_count(table_name), 0)

    def test_no_forbidden_schema_or_runtime_terms_are_introduced(self):
        columns = {
            row[1]
            for row in self.connection.execute(
                "PRAGMA table_info(printer_trading_flow_snapshots)"
            ).fetchall()
        }
        source_text = (
            (SRC_PATH / "printer_v1" / "trading_flow" / "parser.py").read_text(encoding="utf-8")
            + (SRC_PATH / "printer_v1" / "trading_flow" / "recorder.py").read_text(encoding="utf-8")
            + (SRC_PATH / "printer_v1" / "sources" / "dexscreener.py").read_text(encoding="utf-8")
        )
        lowered = " ".join(columns).lower()
        for fragment in FORBIDDEN_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, lowered)
        for fragment in ("requests.get", "requests.post", "httpx", "aiohttp", "while True", "APScheduler"):
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, source_text)


if __name__ == "__main__":
    unittest.main()

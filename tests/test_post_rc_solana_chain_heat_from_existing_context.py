import inspect
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

from printer_v1.chain_heat import classifier, parser, recorder
from printer_v1.chain_heat.contracts import ChainHeatPayloadQualityLabel
from printer_v1.chain_heat.recorder import record_chain_heat_snapshot
from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations


FORBIDDEN_SOURCE_FRAGMENTS = (
    "requests.get",
    "requests.post",
    "httpx",
    "aiohttp",
    "urllib.request",
    "while True",
    "APScheduler",
    "confidence",
    "weighted",
    "buy_signal",
    "wallet",
    "signature",
    "live_execution",
)


class PostRCSolanaChainHeatExistingContextTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "chain-heat.sqlite3"
        apply_migrations(self.db_path)
        self.now = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tempdir.cleanup()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def count_rows(self, table):
        with self.connect() as connection:
            return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def table_exists(self, table):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
            return row is not None

    def latest_chain_heat(self):
        with self.connect() as connection:
            return connection.execute(
                """
                SELECT *
                FROM printer_solana_chain_heat_snapshots
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

    def base_payload(self, **overrides):
        payload = {
            "captured_at": self.now.isoformat(),
            "assets": {
                "solana": {
                    "market_data": {
                        "current_price": {"usd": 150},
                        "price_change_percentage_24h": 0.4,
                        "price_change_percentage_7d": 3.0,
                        "total_volume": {"usd": 900_000_000},
                    },
                    "price_change_percentage_1h": 0.1,
                }
            },
            "network_context": {
                "active_addresses": 1_100_000,
                "tx_count_24h": 15_000_000,
                "priority_fee_context": "normal",
                "congestion_context": "normal",
                "new_token_count": 2500,
            },
            "liquidity_context": {
                "tvl_usd": 4_200_000_000,
                "dex_volume_24h": 600_000_000,
                "stablecoin_supply": 3_200_000_000,
            },
            "meme_context": {
                "hot_pair_count": 12,
                "meme_volume_24h": 7_000_000,
                "meme_liquidity_usd": 4_000_000,
                "meme_new_pair_count": 20,
                "meme_graduation_count": 6,
                "meme_failed_pair_count": 2,
            },
            "source_status": SourceStatus.COMPLETE.value,
            "data_quality_label": DataQualityLabel.CLEAN_DATA.value,
        }
        payload.update(overrides)
        return payload

    def test_valid_normal_chain_context_maps_to_known_acceptable_chain_heat(self):
        created, _row_id = record_chain_heat_snapshot(self.db_path, self.base_payload(), self.now)
        row = self.latest_chain_heat()

        self.assertTrue(created)
        self.assertIn(row["chain_heat_label"], {"SOLANA_NEUTRAL", "SOLANA_WARM"})
        self.assertEqual(row["chain_heat_payload_quality_label"], "CHAIN_HEAT_CONTEXT_CLEAN")
        self.assertEqual(row["source_status"], "COMPLETE")
        self.assertEqual(row["data_quality_label"], "CLEAN_DATA")

    def test_valid_congested_context_maps_to_cautionary_chain_heat(self):
        record_chain_heat_snapshot(
            self.db_path,
            self.base_payload(
                captured_at=(self.now + timedelta(minutes=1)).isoformat(),
                network_context={
                    "active_addresses": 1_800_000,
                    "tx_count_24h": 32_000_000,
                    "priority_fee_context": "high",
                    "congestion_context": "congested",
                    "new_token_count": 4500,
                },
            ),
            self.now,
        )
        row = self.latest_chain_heat()

        self.assertEqual(row["chain_heat_label"], "SOLANA_CONGESTED")
        self.assertEqual(row["congestion_label"], "CONGESTION_HIGH")
        self.assertEqual(row["chain_heat_payload_quality_label"], "CHAIN_HEAT_CONTEXT_CLEAN")

    def test_valid_unstable_context_maps_to_cautionary_chain_heat(self):
        record_chain_heat_snapshot(
            self.db_path,
            self.base_payload(
                captured_at=(self.now + timedelta(minutes=2)).isoformat(),
                network_context={
                    "active_addresses": 2_100_000,
                    "tx_count_24h": 38_000_000,
                    "priority_fee_context": "severe",
                    "congestion_context": "severe",
                    "new_token_count": 6200,
                },
            ),
            self.now,
        )
        row = self.latest_chain_heat()

        self.assertEqual(row["chain_heat_label"], "SOLANA_CONGESTED")
        self.assertEqual(row["congestion_label"], "CONGESTION_SEVERE")
        self.assertEqual(row["chain_heat_payload_quality_label"], "CHAIN_HEAT_CONTEXT_CLEAN")

    def test_congestion_is_not_required_when_contract_critical_fields_are_present(self):
        record_chain_heat_snapshot(
            self.db_path,
            self.base_payload(
                captured_at=(self.now + timedelta(minutes=3)).isoformat(),
                network_context={
                    "active_addresses": 1_100_000,
                    "tx_count_24h": 15_000_000,
                    "new_token_count": 2500,
                },
            ),
            self.now,
        )
        row = self.latest_chain_heat()

        self.assertEqual(row["chain_heat_payload_quality_label"], "CHAIN_HEAT_CONTEXT_CLEAN")
        self.assertEqual(row["congestion_label"], "CONGESTION_UNKNOWN")
        self.assertNotEqual(row["activity_label"], "ACTIVITY_UNKNOWN")

    def test_missing_required_activity_fields_stays_partial_even_with_price_and_liquidity(self):
        record_chain_heat_snapshot(
            self.db_path,
            self.base_payload(
                captured_at=(self.now + timedelta(minutes=4)).isoformat(),
                assets={
                    "solana": {
                        "market_data": {
                            "current_price": {"usd": 150},
                            "price_change_percentage_24h": 0.4,
                        },
                    },
                },
                network_context={},
                liquidity_context={
                    "tvl_usd": 4_200_000_000,
                    "stablecoin_supply": 3_200_000_000,
                },
                meme_context={},
            ),
            self.now,
        )
        row = self.latest_chain_heat()

        self.assertEqual(row["chain_heat_payload_quality_label"], "CHAIN_HEAT_CONTEXT_PARTIAL")
        self.assertEqual(row["activity_label"], "ACTIVITY_UNKNOWN")
        self.assertNotEqual(row["liquidity_label"], "LIQUIDITY_UNKNOWN")

    def test_coingecko_sol_volume_can_satisfy_activity_without_tx_count_or_meme_volume(self):
        record_chain_heat_snapshot(
            self.db_path,
            self.base_payload(
                captured_at=(self.now + timedelta(minutes=5)).isoformat(),
                network_context={},
                liquidity_context={},
                meme_context={},
            ),
            self.now,
        )
        row = self.latest_chain_heat()

        self.assertEqual(row["chain_heat_payload_quality_label"], "CHAIN_HEAT_CONTEXT_CLEAN")
        self.assertNotEqual(row["activity_label"], "ACTIVITY_UNKNOWN")
        self.assertEqual(row["sol_volume_24h"], 900_000_000)
        self.assertIsNone(row["solana_tx_count_24h"])
        self.assertIsNone(row["solana_meme_volume_24h"])

    def test_defillama_dex_volume_can_satisfy_activity_without_tx_count_or_meme_volume(self):
        record_chain_heat_snapshot(
            self.db_path,
            self.base_payload(
                captured_at=(self.now + timedelta(minutes=6)).isoformat(),
                assets={
                    "solana": {
                        "market_data": {
                            "current_price": {"usd": 150},
                            "price_change_percentage_24h": 0.4,
                        },
                    },
                },
                network_context={},
                liquidity_context={
                    "dex_volume_24h": 600_000_000,
                    "tvl_usd": 4_200_000_000,
                },
                meme_context={},
            ),
            self.now,
        )
        row = self.latest_chain_heat()

        self.assertEqual(row["chain_heat_payload_quality_label"], "CHAIN_HEAT_CONTEXT_CLEAN")
        self.assertNotEqual(row["activity_label"], "ACTIVITY_UNKNOWN")
        self.assertEqual(row["solana_dex_volume_24h"], 600_000_000)
        self.assertIsNone(row["solana_tx_count_24h"])
        self.assertIsNone(row["solana_meme_volume_24h"])

    def test_tvl_liquidity_alone_cannot_satisfy_activity(self):
        record_chain_heat_snapshot(
            self.db_path,
            self.base_payload(
                captured_at=(self.now + timedelta(minutes=7)).isoformat(),
                assets={
                    "solana": {
                        "market_data": {
                            "current_price": {"usd": 150},
                            "price_change_percentage_24h": 0.4,
                        },
                    },
                },
                network_context={},
                liquidity_context={
                    "tvl_usd": 4_200_000_000,
                    "stablecoin_supply": 3_200_000_000,
                },
                meme_context={},
            ),
            self.now,
        )
        row = self.latest_chain_heat()

        self.assertEqual(row["chain_heat_payload_quality_label"], "CHAIN_HEAT_CONTEXT_PARTIAL")
        self.assertEqual(row["activity_label"], "ACTIVITY_UNKNOWN")
        self.assertNotEqual(row["liquidity_label"], "LIQUIDITY_UNKNOWN")

    def test_missing_stale_failed_conflicting_and_dirty_context_remain_unknown_or_audit_only(self):
        cases = [
            self.base_payload(captured_at=(self.now + timedelta(minutes=8)).isoformat(), network_context={}, liquidity_context={}, meme_context={}, assets={}),
            self.base_payload(captured_at=(self.now - timedelta(hours=4)).isoformat()),
            self.base_payload(captured_at=(self.now + timedelta(minutes=9)).isoformat(), source_status=SourceStatus.FAILED.value),
            self.base_payload(captured_at=(self.now + timedelta(minutes=10)).isoformat(), source_status=SourceStatus.CONFLICTING.value),
            self.base_payload(captured_at=(self.now + timedelta(minutes=11)).isoformat(), data_quality_label=DataQualityLabel.DIRTY_DATA.value),
        ]

        for payload in cases:
            record_chain_heat_snapshot(self.db_path, payload, self.now)
            row = self.latest_chain_heat()
            self.assertEqual(row["chain_heat_label"], "SOLANA_UNKNOWN")
            self.assertEqual(row["activity_label"], "ACTIVITY_UNKNOWN")
            self.assertEqual(row["liquidity_label"], "LIQUIDITY_UNKNOWN")
            self.assertEqual(row["congestion_label"], "CONGESTION_UNKNOWN")
            self.assertIn(
                row["chain_heat_payload_quality_label"],
                {
                    ChainHeatPayloadQualityLabel.CHAIN_HEAT_CONTEXT_UNKNOWN.value,
                    ChainHeatPayloadQualityLabel.CHAIN_HEAT_CONTEXT_STALE.value,
                    ChainHeatPayloadQualityLabel.CHAIN_HEAT_CONTEXT_CONFLICTING.value,
                    ChainHeatPayloadQualityLabel.CHAIN_HEAT_CONTEXT_DO_NOT_USE_FOR_MEMORY.value,
                },
            )

    def test_chain_heat_evidence_alone_does_not_create_downstream_unlocks(self):
        record_chain_heat_snapshot(self.db_path, self.base_payload(), self.now)

        self.assertEqual(self.count_rows("printer_memory_windows"), 0)
        self.assertEqual(self.count_rows("printer_memory_retrieval_queries"), 0)
        self.assertEqual(self.count_rows("printer_memory_retrieval_matches"), 0)
        self.assertEqual(self.count_rows("printer_paper_decisions"), 0)
        self.assertEqual(self.count_rows("printer_paper_positions"), 0)
        self.assertEqual(self.count_rows("printer_paper_trade_events"), 0)
        if self.table_exists("printer_paper_pl_calculations"):
            self.assertEqual(self.count_rows("printer_paper_pl_calculations"), 0)

    def test_chain_heat_modules_do_not_add_live_or_scoring_capability(self):
        source_text = "\n".join(
            inspect.getsource(module)
            for module in (parser, classifier, recorder)
        )
        for fragment in FORBIDDEN_SOURCE_FRAGMENTS:
            self.assertNotIn(fragment, source_text)


if __name__ == "__main__":
    unittest.main()

import inspect
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.chain_heat.recorder import record_chain_heat_from_source_response
from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.market_regime.recorder import record_market_regime_from_source_response
from printer_v1.sources import (
    SOURCE_REGISTRY,
    build_governed_source_request,
    execute_source_request_with_governor,
    validate_source_adapter_contract,
)
from printer_v1.sources import alternative_me, coingecko, defillama
from printer_v1.sources.alternative_me import build_alternative_me_adapter, build_alternative_me_adapter_contract
from printer_v1.sources.coingecko import build_coingecko_adapter, build_coingecko_adapter_contract
from printer_v1.sources.defillama import build_defillama_adapter, build_defillama_adapter_contract


FORBIDDEN_FRAGMENTS = (
    "requests.get",
    "requests.post",
    "httpx",
    "aiohttp",
    "urllib.request",
    "private_key",
    "wallet",
    "buy_signal",
    "sell_signal",
    "trade_signal",
    "confidence",
    "weighted",
    "while True",
)

DOWNSTREAM_TABLES = (
    "printer_memory_windows",
    "printer_memory_fingerprints",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
)


class PostRCGovernedPublicBroadContextSourceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "public-context.sqlite3"
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

    def count_rows(self, table_name):
        with self.connect() as connection:
            return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])

    def latest_row(self, table_name):
        with self.connect() as connection:
            return connection.execute(
                f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT 1"
            ).fetchone()

    def execute(self, source_name, request_kind, adapter):
        request = build_governed_source_request(
            source_name,
            request_kind,
            request_key=f"{source_name}-{request_kind}",
            now=self.now,
        )
        return execute_source_request_with_governor(self.db_path, request, adapter, now=self.now)

    def coingecko_payload(self):
        return {
            "captured_at": self.now.isoformat(),
            "assets": {
                "bitcoin": {
                    "market_data": {
                        "current_price": {"usd": 65000},
                        "price_change_percentage_24h": 2.8,
                        "price_change_percentage_7d": 6.2,
                    },
                    "price_change_percentage_1h": 0.3,
                },
                "solana": {
                    "market_data": {
                        "current_price": {"usd": 150},
                        "price_change_percentage_24h": 4.0,
                        "price_change_percentage_7d": 9.0,
                        "total_volume": {"usd": 1_700_000_000},
                    },
                    "price_change_percentage_1h": 0.7,
                },
            },
            "source_status": SourceStatus.COMPLETE.value,
            "data_quality_label": DataQualityLabel.CLEAN_DATA.value,
        }

    def defillama_payload(self):
        return {
            "captured_at": self.now.isoformat(),
            "solana_tvl_usd": 4_700_000_000,
            "solana_dex_volume_24h": 650_000_000,
            "solana_stablecoin_supply": 3_400_000_000,
            "source_status": SourceStatus.COMPLETE.value,
            "data_quality_label": DataQualityLabel.CLEAN_DATA.value,
        }

    def alternative_me_payload(self):
        return {
            "data": [
                {
                    "value": "66",
                    "value_classification": "Greed",
                    "timestamp": int(self.now.timestamp()),
                }
            ],
            "source_status": SourceStatus.COMPLETE.value,
            "data_quality_label": DataQualityLabel.CLEAN_DATA.value,
        }

    def assert_no_downstream_unlocks(self):
        for table in DOWNSTREAM_TABLES:
            self.assertEqual(self.count_rows(table), 0, table)
        if self.table_exists("printer_paper_pl_calculations"):
            self.assertEqual(self.count_rows("printer_paper_pl_calculations"), 0)

    def table_exists(self, table_name):
        with self.connect() as connection:
            return connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone() is not None

    def test_public_context_contracts_are_free_public_no_key_disabled_and_governed(self):
        contracts = (
            build_alternative_me_adapter_contract(),
            build_coingecko_adapter_contract(),
            build_defillama_adapter_contract(),
        )
        for contract in contracts:
            definition = SOURCE_REGISTRY[contract.source_name]
            self.assertTrue(validate_source_adapter_contract(contract))
            self.assertEqual(definition.dependency_type, "free_public")
            self.assertFalse(definition.requires_paid_plan)
            self.assertFalse(contract.enabled_by_default)
            self.assertTrue(contract.fixture_only)
            self.assertFalse(contract.supports_network_execution)
            self.assertTrue(contract.requires_governor_context)

    def test_disabled_adapters_refuse_execution_before_governed_transport(self):
        adapters = (
            build_alternative_me_adapter(),
            build_coingecko_adapter(),
            build_defillama_adapter(),
        )
        for adapter in adapters:
            with self.assertRaises(PermissionError):
                adapter.execute(None)

    def test_coingecko_governed_response_can_feed_market_and_chain_heat_context(self):
        result = self.execute(
            "coingecko",
            "broad_market_context",
            build_coingecko_adapter(
                enabled=True,
                fixture_transport=coingecko.fixture_success_transport(self.coingecko_payload()),
            ),
        )

        self.assertEqual(result.normalized_result.source_status, SourceStatus.COMPLETE)
        self.assertIsNotNone(result.response_record)
        record_market_regime_from_source_response(self.db_path, result.response_record.id, self.now)
        record_chain_heat_from_source_response(self.db_path, result.response_record.id, self.now)

        market = self.latest_row("printer_market_regime_snapshots")
        chain = self.latest_row("printer_solana_chain_heat_snapshots")
        self.assertNotEqual(market["market_regime_label"], "UNKNOWN")
        self.assertNotEqual(chain["chain_heat_label"], "SOLANA_UNKNOWN")
        self.assertEqual(self.count_rows("printer_source_requests"), 1)
        self.assertEqual(self.count_rows("printer_source_responses"), 1)
        self.assertEqual(self.count_rows("printer_source_failures"), 0)
        self.assert_no_downstream_unlocks()

    def test_alternative_me_governed_response_can_feed_market_regime_context(self):
        result = self.execute(
            "alternative_me",
            "fear_greed_context",
            build_alternative_me_adapter(
                enabled=True,
                fixture_transport=alternative_me.fixture_success_transport(self.alternative_me_payload()),
            ),
        )

        self.assertEqual(result.normalized_result.source_status, SourceStatus.COMPLETE)
        record_market_regime_from_source_response(self.db_path, result.response_record.id, self.now)

        market = self.latest_row("printer_market_regime_snapshots")
        self.assertNotEqual(market["market_regime_label"], "UNKNOWN")
        self.assertEqual(self.count_rows("printer_source_responses"), 1)
        self.assert_no_downstream_unlocks()

    def test_defillama_governed_response_can_feed_chain_heat_context(self):
        result = self.execute(
            "defillama",
            "chain_liquidity_context",
            build_defillama_adapter(
                enabled=True,
                fixture_transport=defillama.fixture_success_transport(self.defillama_payload()),
            ),
        )

        self.assertEqual(result.normalized_result.source_status, SourceStatus.COMPLETE)
        record_chain_heat_from_source_response(self.db_path, result.response_record.id, self.now)

        chain = self.latest_row("printer_solana_chain_heat_snapshots")
        self.assertNotEqual(chain["chain_heat_label"], "SOLANA_UNKNOWN")
        self.assertNotEqual(chain["liquidity_label"], "LIQUIDITY_UNKNOWN")
        self.assertEqual(self.count_rows("printer_source_responses"), 1)
        self.assert_no_downstream_unlocks()

    def test_malformed_public_context_records_failure_and_creates_no_context_rows(self):
        result = self.execute(
            "coingecko",
            "broad_market_context",
            build_coingecko_adapter(
                enabled=True,
                fixture_transport=coingecko.fixture_success_transport({"captured_at": self.now.isoformat()}),
            ),
        )

        self.assertEqual(result.normalized_result.source_status, SourceStatus.FAILED)
        self.assertIsNone(result.response_record)
        self.assertIsNotNone(result.failure_record)
        self.assertEqual(self.count_rows("printer_source_requests"), 1)
        self.assertEqual(self.count_rows("printer_source_responses"), 0)
        self.assertEqual(self.count_rows("printer_source_failures"), 1)
        self.assertEqual(self.count_rows("printer_market_regime_snapshots"), 0)
        self.assertEqual(self.count_rows("printer_solana_chain_heat_snapshots"), 0)
        self.assert_no_downstream_unlocks()

    def test_adapters_do_not_introduce_live_paid_trade_or_scoring_capability(self):
        source_text = "\n".join(
            inspect.getsource(module)
            for module in (alternative_me, coingecko, defillama)
        )
        for fragment in FORBIDDEN_FRAGMENTS:
            self.assertNotIn(fragment, source_text)


if __name__ == "__main__":
    unittest.main()

import inspect
import pathlib
import sqlite3
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.sources.contracts import SourceAdapterContext, build_governed_source_request, build_governor_decision
from printer_v1.sources.dexscreener import (
    DEXSCREENER_SOURCE_NAME,
    DexScreenerAdapter,
    build_dexscreener_adapter,
    build_dexscreener_adapter_contract,
    fixture_rate_limited_transport,
    fixture_success_transport,
    get_dexscreener_adapter_metadata,
    normalize_dexscreener_fixture_result,
)
from printer_v1.sources.governed_execution import execute_source_request_with_governor
from printer_v1.sources.recording import record_source_request


DOWNSTREAM_TABLES = [
    "printer_tokens",
    "printer_pairs",
    "printer_token_snapshots",
    "printer_market_regime_snapshots",
    "printer_solana_chain_heat_snapshots",
    "printer_safety_rug_snapshots",
    "printer_liquidity_exit_snapshots",
    "printer_trading_flow_snapshots",
    "printer_chart_volatility_snapshots",
    "printer_micro_events",
    "printer_memory_windows",
    "printer_episodes",
    "printer_episode_snapshots",
    "printer_episode_outcomes",
    "printer_memory_fingerprints",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
]


def table_count(connection, table_name):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def fixture_payload(*, stale=False):
    return {
        "fixture_stale": stale,
        "pairs": [
            {
                "chainId": "solana",
                "pairAddress": "dex-fixture-pair",
                "baseToken": {
                    "address": "dex-fixture-mint",
                    "symbol": "DFX",
                    "name": "Dex Fixture",
                },
                "priceUsd": "0.0012",
                "liquidity": {"usd": 12345.0},
                "volume": {"m5": 100.0, "h1": 900.0},
                "pairCreatedAt": "2026-06-20T00:00:00Z",
            }
        ],
    }


class Phase24DexScreenerAdapterDisabledTests(unittest.TestCase):
    def make_db(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = pathlib.Path(temp_dir.name) / "phase24.sqlite3"
        apply_migrations(db_path)
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(connection.close)
        return connection

    def test_package_structure_uses_dunder_init_not_accidental_init(self):
        self.assertTrue((SRC_PATH / "printer_v1" / "sources" / "__init__.py").is_file())
        self.assertFalse((SRC_PATH / "printer_v1" / "sources" / "init.py").exists())

    def test_dexscreener_adapter_exists_and_is_disabled_by_default(self):
        metadata = get_dexscreener_adapter_metadata()
        adapter = build_dexscreener_adapter()
        contract = build_dexscreener_adapter_contract()
        self.assertEqual(metadata.source_name, DEXSCREENER_SOURCE_NAME)
        self.assertEqual(adapter.contract.source_name, DEXSCREENER_SOURCE_NAME)
        self.assertEqual(contract.source_name, DEXSCREENER_SOURCE_NAME)
        self.assertFalse(metadata.enabled_by_default)
        self.assertFalse(adapter.enabled)
        self.assertFalse(adapter.contract.enabled_by_default)
        self.assertFalse(adapter.contract.supports_network_execution)

    def test_dexscreener_adapter_cannot_run_outside_governed_execution(self):
        adapter = build_dexscreener_adapter(enabled=True, fixture_transport=fixture_success_transport(fixture_payload()))
        with self.assertRaises(PermissionError):
            adapter.execute(None)

        connection = self.make_db()
        request = build_governed_source_request("dexscreener", "token_discovery")
        decision = build_governor_decision(request)
        request_record = record_source_request(connection, request, decision)
        context = SourceAdapterContext(
            request=request,
            request_record=request_record,
            decision=decision,
            governor_approved=False,
        )
        with self.assertRaises(PermissionError):
            adapter.execute(context)

    def test_disabled_dexscreener_adapter_refuses_even_governed_context(self):
        connection = self.make_db()
        request = build_governed_source_request("dexscreener", "token_discovery")
        decision = build_governor_decision(request)
        request_record = record_source_request(connection, request, decision)
        context = SourceAdapterContext(
            request=request,
            request_record=request_record,
            decision=decision,
            governor_approved=True,
        )
        adapter = build_dexscreener_adapter(fixture_transport=fixture_success_transport(fixture_payload()))
        with self.assertRaises(PermissionError):
            adapter.execute(context)

    def test_fixture_success_normalizes_through_governed_execution(self):
        connection = self.make_db()
        request = build_governed_source_request("dexscreener", "token_discovery")
        adapter = build_dexscreener_adapter(
            enabled=True,
            fixture_transport=fixture_success_transport(fixture_payload()),
        )
        result = execute_source_request_with_governor(connection, request, adapter)
        payload = result.normalized_result.normalized_payload
        self.assertEqual(result.normalized_result.source_status, SourceStatus.COMPLETE)
        self.assertEqual(result.normalized_result.data_quality_label, DataQualityLabel.CLEAN_DATA)
        self.assertEqual(payload["source_name"], "dexscreener")
        self.assertEqual(payload["pairs"][0]["chain"], "solana")
        self.assertEqual(payload["pairs"][0]["pair_address"], "dex-fixture-pair")
        self.assertEqual(payload["pairs"][0]["token_mint"], "dex-fixture-mint")
        self.assertIsNotNone(result.response_record)
        self.assertEqual(table_count(connection, "printer_source_requests"), 1)
        self.assertEqual(table_count(connection, "printer_source_responses"), 1)
        self.assertEqual(table_count(connection, "printer_source_failures"), 0)
        for table_name in DOWNSTREAM_TABLES:
            self.assertEqual(table_count(connection, table_name), 0, table_name)

    def test_fixture_stale_response_is_marked_stale(self):
        result = normalize_dexscreener_fixture_result(fixture_payload(stale=True), request_kind="token_discovery")
        self.assertEqual(result.source_status, SourceStatus.STALE)
        self.assertEqual(result.data_quality_label, DataQualityLabel.STALE_DATA)

    def test_fixture_malformed_response_is_invalid_result(self):
        result = normalize_dexscreener_fixture_result({"pairs": []}, request_kind="token_discovery")
        self.assertEqual(result.source_status, SourceStatus.FAILED)
        self.assertEqual(result.data_quality_label, DataQualityLabel.MISSING_CRITICAL_DATA)
        self.assertEqual(result.failure_type, "dexscreener_malformed_fixture")

    def test_fixture_rate_limit_behavior_is_recorded_honestly_by_governor(self):
        connection = self.make_db()
        request = build_governed_source_request("dexscreener", "token_discovery")
        adapter = build_dexscreener_adapter(
            enabled=True,
            fixture_transport=fixture_rate_limited_transport(),
        )
        result = execute_source_request_with_governor(
            connection,
            request,
            adapter,
            recent_request_count=10_000,
        )
        self.assertEqual(result.normalized_result.source_status, SourceStatus.STALE)
        self.assertEqual(result.failure_record.failure_type, "rate_limit_exceeded")
        self.assertEqual(adapter.call_count, 0)
        self.assertEqual(table_count(connection, "printer_source_requests"), 1)
        self.assertEqual(table_count(connection, "printer_source_responses"), 0)
        self.assertEqual(table_count(connection, "printer_source_failures"), 1)

    def test_no_automatic_network_method_exists(self):
        adapter = DexScreenerAdapter()
        public_methods = {
            name
            for name, member in inspect.getmembers(adapter, predicate=callable)
            if not name.startswith("_")
        }
        self.assertEqual(public_methods, {"execute"})
        source_text = (SRC_PATH / "printer_v1" / "sources" / "dexscreener.py").read_text(encoding="utf-8")
        for fragment in ("requests.", "httpx", "aiohttp", "socket"):
            self.assertNotIn(fragment, source_text)

    def test_no_unauthorised_adapter_module_exists(self):
        source_files = {path.name for path in (SRC_PATH / "printer_v1" / "sources").glob("*.py")}
        self.assertIn("dexscreener.py", source_files)
        self.assertIn("geckoterminal.py", source_files)
        self.assertIn("pumpportal.py", source_files)
        self.assertIn("pumpswap.py", source_files)
        self.assertIn("goplus.py", source_files)
        self.assertIn("jupiter_quote.py", source_files)
        self.assertFalse(
            source_files
            & {
                "solana_rpc.py",
                "helius.py",
                "jupiter.py",
            }
        )
        for adapter_name in ("alternative_me.py", "coingecko.py", "defillama.py", "geckoterminal.py", "pumpportal.py", "pumpswap.py", "goplus.py", "jupiter_quote.py"):
            text = (SRC_PATH / "printer_v1" / "sources" / adapter_name).read_text(encoding="utf-8")
            for fragment in ("requests.", "httpx", "aiohttp"):
                self.assertNotIn(fragment, text)


if __name__ == "__main__":
    unittest.main()

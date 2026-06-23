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
from printer_v1.sources import (
    FIXTURE_FAILURE,
    FIXTURE_MALFORMED,
    FIXTURE_STALE,
    FIXTURE_SUCCESS,
    GOVERNOR_ONLY_EXECUTION_PATH,
    SourceAdapterContext,
    build_fixture_source_adapter,
    build_governed_source_request,
    build_governor_decision,
    build_source_adapter_contract,
    execute_source_request_with_governor,
    validate_source_adapter_contract,
)
from printer_v1.sources.recording import (
    record_source_failure,
    record_source_request,
    record_source_response,
)


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


class Phase23SourceAdapterExecutionContractTests(unittest.TestCase):
    def make_db(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = pathlib.Path(temp_dir.name) / "phase23.sqlite3"
        apply_migrations(db_path)
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(connection.close)
        return connection

    def test_source_adapter_contract_is_disabled_fixture_only_and_governed(self):
        contract = build_source_adapter_contract("dexscreener")
        self.assertTrue(validate_source_adapter_contract(contract))
        self.assertEqual(contract.source_name, "dexscreener")
        self.assertFalse(contract.enabled_by_default)
        self.assertTrue(contract.fixture_only)
        self.assertFalse(contract.supports_network_execution)
        self.assertTrue(contract.requires_governor_context)
        self.assertEqual(GOVERNOR_ONLY_EXECUTION_PATH, "source_governor_record_then_adapter_boundary")

    def test_source_request_response_failure_contracts_record_to_existing_tables(self):
        connection = self.make_db()
        request = build_governed_source_request(
            "dexscreener",
            "token_discovery",
            request_key="fixture-token",
            payload={"token_mint": "fixture-mint"},
        )
        decision = build_governor_decision(request)
        request_record = record_source_request(connection, request, decision)
        result = execute_source_request_with_governor(
            connection,
            request,
            build_fixture_source_adapter(
                "dexscreener",
                fixture_payload={"token_mint": "fixture-mint", "pairs": []},
            ),
        ).normalized_result
        response_record = record_source_response(connection, request_record, result)
        failure_record = record_source_failure(
            connection,
            request_record,
            failure_type="fixture_failure",
            failure_message="local fixture failure",
        )
        self.assertGreater(request_record.id, 0)
        self.assertGreater(response_record.id, 0)
        self.assertGreater(failure_record.id, 0)
        self.assertEqual(table_count(connection, "printer_source_requests"), 2)
        self.assertEqual(table_count(connection, "printer_source_responses"), 2)
        self.assertEqual(table_count(connection, "printer_source_failures"), 1)

    def test_governed_fixture_success_records_request_and_response_only(self):
        connection = self.make_db()
        request = build_governed_source_request("dexscreener", "token_discovery")
        adapter = build_fixture_source_adapter(
            "dexscreener",
            fixture_kind=FIXTURE_SUCCESS,
            fixture_payload={"chain": "solana", "token_mint": "fixture-mint"},
        )
        result = execute_source_request_with_governor(connection, request, adapter)
        self.assertEqual(result.normalized_result.source_status, SourceStatus.COMPLETE)
        self.assertEqual(result.normalized_result.data_quality_label, DataQualityLabel.CLEAN_DATA)
        self.assertIsNotNone(result.response_record)
        self.assertIsNone(result.failure_record)
        self.assertEqual(adapter.call_count, 1)
        self.assertEqual(table_count(connection, "printer_source_requests"), 1)
        self.assertEqual(table_count(connection, "printer_source_responses"), 1)
        self.assertEqual(table_count(connection, "printer_source_failures"), 0)
        for table_name in DOWNSTREAM_TABLES:
            self.assertEqual(table_count(connection, table_name), 0, table_name)

    def test_governed_fixture_malformed_records_failure_honestly(self):
        connection = self.make_db()
        request = build_governed_source_request("dexscreener", "token_discovery")
        adapter = build_fixture_source_adapter("dexscreener", fixture_kind=FIXTURE_MALFORMED)
        result = execute_source_request_with_governor(connection, request, adapter)
        self.assertEqual(result.normalized_result.source_status, SourceStatus.FAILED)
        self.assertEqual(result.normalized_result.data_quality_label, DataQualityLabel.MISSING_CRITICAL_DATA)
        self.assertEqual(result.failure_record.failure_type, "malformed_fixture")
        self.assertEqual(table_count(connection, "printer_source_requests"), 1)
        self.assertEqual(table_count(connection, "printer_source_responses"), 0)
        self.assertEqual(table_count(connection, "printer_source_failures"), 1)

    def test_governed_fixture_stale_records_stale_response_honestly(self):
        connection = self.make_db()
        request = build_governed_source_request("dexscreener", "token_discovery")
        adapter = build_fixture_source_adapter(
            "dexscreener",
            fixture_kind=FIXTURE_STALE,
            fixture_payload={"chain": "solana", "token_mint": "stale-fixture"},
        )
        result = execute_source_request_with_governor(connection, request, adapter)
        self.assertEqual(result.normalized_result.source_status, SourceStatus.STALE)
        self.assertEqual(result.normalized_result.data_quality_label, DataQualityLabel.STALE_DATA)
        self.assertIsNotNone(result.response_record)
        self.assertEqual(table_count(connection, "printer_source_responses"), 1)
        response = connection.execute("SELECT * FROM printer_source_responses").fetchone()
        self.assertEqual(response["source_status"], SourceStatus.STALE.value)
        self.assertEqual(response["data_quality_label"], DataQualityLabel.STALE_DATA.value)

    def test_governed_fixture_failure_records_failure_honestly(self):
        connection = self.make_db()
        request = build_governed_source_request("dexscreener", "token_discovery")
        adapter = build_fixture_source_adapter("dexscreener", fixture_kind=FIXTURE_FAILURE)
        result = execute_source_request_with_governor(connection, request, adapter)
        self.assertEqual(result.normalized_result.source_status, SourceStatus.FAILED)
        self.assertIsNotNone(result.failure_record)
        self.assertEqual(result.failure_record.failure_type, "fixture_failure")
        self.assertEqual(table_count(connection, "printer_source_failures"), 1)

    def test_rate_limit_rejection_records_failure_without_adapter_call(self):
        connection = self.make_db()
        request = build_governed_source_request("dexscreener", "token_discovery")
        adapter = build_fixture_source_adapter("dexscreener", fixture_kind=FIXTURE_SUCCESS)
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

    def test_adapter_execution_requires_source_governor_context(self):
        adapter = build_fixture_source_adapter("dexscreener")
        with self.assertRaises(PermissionError):
            adapter.execute(None)

        connection = self.make_db()
        request = build_governed_source_request("dexscreener", "token_discovery")
        decision = build_governor_decision(request)
        record = record_source_request(connection, request, decision)
        context = SourceAdapterContext(
            request=request,
            request_record=record,
            decision=decision,
            governor_approved=False,
        )
        with self.assertRaises(PermissionError):
            adapter.execute(context)

    def test_adapter_public_surface_has_no_direct_fetch_entrypoint(self):
        adapter = build_fixture_source_adapter("dexscreener")
        public_methods = {
            name
            for name, member in inspect.getmembers(adapter, predicate=callable)
            if not name.startswith("_")
        }
        self.assertEqual(public_methods, {"execute"})

    def test_engine_modules_do_not_import_phase23_adapter_boundary(self):
        engine_roots = [
            "discovery",
            "snapshots",
            "market_regime",
            "chain_heat",
            "safety",
            "liquidity_exit",
            "trading_flow",
            "chart_volatility",
            "micro_event",
            "memory",
            "memory_retrieval",
            "paper_decision",
            "paper_monitor",
            "paper_audit",
        ]
        forbidden_fragments = (
            "printer_v1.sources.governed_execution",
            "FixtureSourceAdapter",
            "execute_source_request_with_governor",
        )
        for root_name in engine_roots:
            for path in (SRC_PATH / "printer_v1" / root_name).glob("*.py"):
                text = path.read_text(encoding="utf-8")
                for fragment in forbidden_fragments:
                    self.assertNotIn(fragment, text, str(path))

    def test_no_new_network_dependency_or_real_adapter_module_exists(self):
        pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        for fragment in ("requests", "httpx", "aiohttp", "websocket-client"):
            self.assertNotIn(fragment, pyproject)
        source_files = {path.name for path in (SRC_PATH / "printer_v1" / "sources").glob("*.py")}
        self.assertFalse(
            source_files
            & {
                "geckoterminal.py",
                "pumpportal.py",
                "goplus.py",
                "solana_rpc.py",
                "helius.py",
                "jupiter.py",
            }
        )
        for adapter_name in ("alternative_me.py", "coingecko.py", "defillama.py"):
            text = (SRC_PATH / "printer_v1" / "sources" / adapter_name).read_text(encoding="utf-8")
            for fragment in ("requests.get", "requests.post", "httpx", "aiohttp", "urllib.request"):
                self.assertNotIn(fragment, text)


if __name__ == "__main__":
    unittest.main()

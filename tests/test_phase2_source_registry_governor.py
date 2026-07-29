import inspect
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.sources import governor
from printer_v1.sources.governor import (
    can_request_source,
    get_retry_after,
    get_source_definition,
    is_response_stale,
    is_source_allowed,
    should_cooldown_source,
    source_priority_value,
    validate_request_kind,
)
from printer_v1.sources.registry import ALLOWED_SOURCE_NAMES, SOURCE_REGISTRY, SourceDefinition


EXPECTED_SOURCES = {
    "birdeye",
    "dexscreener",
    "geckoterminal",
    "solana_tracker",
    "pumpportal",
    "pumpswap",
    "alternative_me",
    "coingecko",
    "defillama",
    "goplus",
    "solana_rpc",
    "helius_free",
    "jupiter_quote",
}

FORBIDDEN_NAME_FRAGMENTS = {
    "score",
    "confidence",
    "rank",
    "rating",
    "weight",
    "wallet",
    "private_key",
    "signed_tx",
    "live_trade",
}


class Phase2SourceRegistryGovernorTest(unittest.TestCase):
    def test_every_allowed_v1_source_is_registered(self):
        self.assertEqual(ALLOWED_SOURCE_NAMES, EXPECTED_SOURCES)
        self.assertEqual(set(SOURCE_REGISTRY), EXPECTED_SOURCES)

    def test_no_registered_source_requires_paid_plan(self):
        self.assertTrue(all(not source.requires_paid_plan for source in SOURCE_REGISTRY.values()))

    def test_unknown_source_is_rejected(self):
        self.assertFalse(is_source_allowed("paid_birdeye"))
        decision = can_request_source("paid_birdeye", "token_market_snapshot", 0)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "unknown_source")

    def test_paid_dependency_is_rejected(self):
        paid_source = SourceDefinition(
            source_name="paid_test",
            purpose="test",
            dependency_type="paid",
            requires_paid_plan=True,
            supports_solana=True,
            allowed_request_kinds=("token_market_snapshot",),
            default_rate_limit_per_minute=1,
            stale_after_seconds=1,
            retry_after_seconds=1,
            max_retries=1,
            priority_class="token_level",
        )
        original = governor.SOURCE_REGISTRY
        try:
            governor.SOURCE_REGISTRY = {**original, "paid_test": paid_source}
            decision = can_request_source("paid_test", "token_market_snapshot", 0)
        finally:
            governor.SOURCE_REGISTRY = original

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "paid_dependency_rejected")

    def test_allowed_request_kinds_are_enforced(self):
        self.assertTrue(validate_request_kind("dexscreener", "token_market_snapshot"))
        self.assertFalse(validate_request_kind("dexscreener", "fear_greed_context"))
        decision = can_request_source("dexscreener", "fear_greed_context", 0)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "request_kind_not_allowed")

    def test_solana_token_level_requests_reject_non_chain_specific_sources(self):
        decision = can_request_source("coingecko", "token_market_snapshot", 0)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "request_kind_not_allowed")

    def test_jupiter_quote_is_restricted_to_paper_quote_realism(self):
        self.assertTrue(validate_request_kind("jupiter_quote", "paper_quote_realism"))
        self.assertFalse(validate_request_kind("jupiter_quote", "onchain_reference"))
        allowed = can_request_source("jupiter_quote", "paper_quote_realism", 0)
        rejected = can_request_source("jupiter_quote", "onchain_reference", 0)
        self.assertTrue(allowed.allowed)
        self.assertFalse(rejected.allowed)

    def test_stale_detection_uses_fake_timestamps(self):
        now = datetime(2026, 6, 19, tzinfo=timezone.utc)
        fresh = now - timedelta(seconds=10)
        stale = now - timedelta(seconds=31)
        self.assertFalse(is_response_stale("jupiter_quote", fresh, now))
        self.assertTrue(is_response_stale("jupiter_quote", stale, now))

    def test_retry_and_cooldown_logic_uses_fake_failure_counts(self):
        definition = get_source_definition("dexscreener")
        self.assertEqual(get_retry_after("dexscreener", 2), definition.retry_after_seconds * 2)
        self.assertFalse(should_cooldown_source("dexscreener", definition.max_retries - 1))
        self.assertTrue(should_cooldown_source("dexscreener", definition.max_retries))

    def test_rate_limit_permission_check_uses_fake_counts(self):
        definition = get_source_definition("dexscreener")
        allowed = can_request_source("dexscreener", "token_market_snapshot", 0)
        limited = can_request_source(
            "dexscreener",
            "token_market_snapshot",
            definition.default_rate_limit_per_minute,
        )
        self.assertTrue(allowed.allowed)
        self.assertFalse(limited.allowed)
        self.assertEqual(limited.reason, "rate_limit_exceeded")

    def test_broad_context_sources_are_lower_priority_than_token_level_sources(self):
        self.assertGreater(source_priority_value("coingecko"), source_priority_value("dexscreener"))
        self.assertGreater(source_priority_value("defillama"), source_priority_value("solana_rpc"))

    def test_no_source_function_performs_live_network_call(self):
        source_text = "\n".join(
            inspect.getsource(obj)
            for _, obj in inspect.getmembers(governor, inspect.isfunction)
            if obj.__module__ == governor.__name__
        )
        forbidden_calls = ["requests.get", "requests.post", "httpx", "aiohttp", "urllib.request"]
        self.assertFalse(any(call in source_text for call in forbidden_calls))

    def test_no_network_dependency_exists(self):
        pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertNotIn("requests", pyproject)
        self.assertNotIn("httpx", pyproject)
        self.assertNotIn("aiohttp", pyproject)

    def test_no_forbidden_field_or_function_is_introduced(self):
        names = []
        for module in (governor,):
            names.extend(name.lower() for name, _ in inspect.getmembers(module))
        for source in SOURCE_REGISTRY.values():
            names.extend(source.__dict__)
        joined_names = " ".join(names)
        self.assertFalse(any(fragment in joined_names for fragment in FORBIDDEN_NAME_FRAGMENTS))

    def test_source_registry_governor_tables_exist_and_reject_paid_plan(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db_path = pathlib.Path(tempdir) / "printer.sqlite3"
            apply_migrations(db_path)
            connection = sqlite3.connect(db_path)
            try:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                self.assertIn("printer_source_registry", tables)
                self.assertIn("printer_source_health", tables)
                self.assertIn("printer_source_rate_limits", tables)
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO printer_source_registry (
                            source_name,
                            purpose,
                            dependency_type,
                            requires_paid_plan,
                            supports_solana,
                            allowed_request_kinds_json,
                            default_rate_limit_per_minute,
                            stale_after_seconds,
                            retry_after_seconds,
                            max_retries,
                            priority_class
                        )
                        VALUES (
                            'paid_test',
                            'test',
                            'paid',
                            1,
                            'true',
                            '[]',
                            1,
                            1,
                            1,
                            1,
                            'token_level'
                        )
                        """
                    )
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()

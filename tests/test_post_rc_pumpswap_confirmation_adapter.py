"""Sprint D: PumpSwap read-only pool confirmation adapter tests."""

import argparse
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.discovery.contracts import DiscoveryChannelLabel, DiscoveryOutputAction
from printer_v1.operator_cli.commands import build_discover_candidates_once_payload
from printer_v1.sources import (
    SOURCE_REGISTRY,
    build_governed_source_request,
    execute_source_request_with_governor,
    validate_source_adapter_contract,
)
from printer_v1.sources.pumpswap import (
    ALLOWED_REQUEST_KINDS as PUMPSWAP_ALLOWED_KINDS,
    PUMPSWAP_SOURCE_NAME,
    PumpSwapAdapterMetadata,
    build_pumpswap_adapter,
    build_pumpswap_adapter_contract,
    fixture_failure_transport,
    fixture_success_transport,
    normalize_pumpswap_payload,
)


DOWNSTREAM_TABLES = (
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
)

FORBIDDEN_FRAGMENTS = (
    "score",
    "rank",
    "confidence",
    "weighted",
    "buy_signal",
    "sell_signal",
    "trade_signal",
    "wallet",
    "private_key",
    "live_execution",
    "buy_unlock",
    "pnl",
)

# These request kinds must never be in PUMPSWAP_ALLOWED_KINDS
FORBIDDEN_REQUEST_KINDS = (
    "swap",
    "buy",
    "sell",
    "route",
    "transaction",
    "instruction",
    "execute",
    "signing",
    "quote_for_execution",
    "live_trade",
    "trade_stream",
)


def count_rows(db_path, table):
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        conn.close()


def make_db():
    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db_path = pathlib.Path(tmp.name) / "sprint-d.sqlite3"
    apply_migrations(db_path)
    return tmp, db_path


def _cli_args(db_path, **kw):
    values = {
        "db_path": str(db_path),
        "project_root": str(PROJECT_ROOT),
        "format": "json",
        "no_color": True,
        "operator_approved": True,
        "chain": "solana",
        "max_candidates": 1,
        "query": "pump",
        "timeout_seconds": 5.0,
        "source_name": "pumpswap",
        "request_kind": "pumpswap_pool_confirmation",
        "request_key": "sprint-d-test",
    }
    values.update(kw)
    return argparse.Namespace(**values)


def _pool_confirmation_payload(*, mint="ps-pool-mint-1", pool="ps-pool-addr-1",
                                symbol="SPSD", name="Sprint D Pool", liquidity=8000.0):
    return {
        "tokens": [
            {
                "chain": "solana",
                "mint": mint,
                "pairAddress": pool,
                "symbol": symbol,
                "name": name,
                "dex": "pumpswap",
                "poolSource": "pumpswap",
                "price_usd": "0.00050",
                "liquidity_usd": liquidity,
                "volume_1h": 2000.0,
                "txns_1h": 25,
                "captured_at": "2026-06-25T12:00:00+00:00",
            }
        ]
    }


def _migration_pool_payload(*, mint="ps-mig-mint-1", pool="ps-mig-pool-1",
                             liquidity=15000.0):
    return {
        "tokens": [
            {
                "chain": "solana",
                "mint": mint,
                "pairAddress": pool,
                "symbol": "SPSDM",
                "name": "Sprint D Migration",
                "dex": "pumpswap",
                "poolSource": "pumpswap",
                "price_usd": "0.00200",
                "liquidity_usd": liquidity,
                "volume_1h": 5000.0,
                "txns_1h": 45,
                "captured_at": "2026-06-25T12:00:00+00:00",
            }
        ]
    }


def _liquidity_ref_payload(*, mint="ps-liq-mint-1", pool="ps-liq-pool-1",
                            liquidity=3000.0):
    return {
        "tokens": [
            {
                "chain": "solana",
                "mint": mint,
                "pairAddress": pool,
                "symbol": "SPSDL",
                "name": "Sprint D Liquidity Ref",
                "dex": "pumpswap",
                "poolSource": "pumpswap",
                "price_usd": "0.00010",
                "liquidity_usd": liquidity,
                "volume_1h": 800.0,
                "txns_1h": 10,
                "captured_at": "2026-06-25T12:00:00+00:00",
            }
        ]
    }


def _raw_pools_payload(*, mint="ps-raw-mint-1", pool="ps-raw-pool-1"):
    return {
        "pools": [
            {
                "base_mint": mint,
                "pool_address": pool,
                "liquidity_usd": "6000",
                "price_usd": "0.001",
                "volume_1h": "1500",
                "txns_1h": "18",
                "symbol": "RAW",
                "name": "Raw Pool",
                "chain": "solana",
            }
        ]
    }


# ---------------------------------------------------------------------------
# Class 1: Source registry and contract
# ---------------------------------------------------------------------------

class PumpSwapRegistryContractTests(unittest.TestCase):

    def test_pumpswap_is_registered(self):
        self.assertIn("pumpswap", SOURCE_REGISTRY)

    def test_pumpswap_is_free_public_no_paid_plan(self):
        defn = SOURCE_REGISTRY["pumpswap"]
        self.assertFalse(defn.requires_paid_plan)
        self.assertEqual(defn.dependency_type, "free_public")

    def test_pumpswap_supports_solana(self):
        self.assertEqual(SOURCE_REGISTRY["pumpswap"].supports_solana, True)

    def test_pumpswap_has_read_only_request_kinds_only(self):
        defn = SOURCE_REGISTRY["pumpswap"]
        self.assertIn("pumpswap_pool_confirmation", defn.allowed_request_kinds)
        self.assertIn("pumpswap_migration_pool_reference", defn.allowed_request_kinds)
        self.assertIn("pumpswap_liquidity_reference", defn.allowed_request_kinds)

    def test_pumpswap_adapter_allowed_kinds_match_registry(self):
        defn = SOURCE_REGISTRY["pumpswap"]
        self.assertEqual(PUMPSWAP_ALLOWED_KINDS, set(defn.allowed_request_kinds))

    def test_pumpswap_forbidden_request_kinds_not_allowed(self):
        for kind in FORBIDDEN_REQUEST_KINDS:
            self.assertNotIn(kind, PUMPSWAP_ALLOWED_KINDS,
                             f"Forbidden kind '{kind}' must not be in ALLOWED_REQUEST_KINDS")

    def test_pumpswap_contract_validates(self):
        contract = build_pumpswap_adapter_contract()
        self.assertTrue(validate_source_adapter_contract(contract))

    def test_pumpswap_contract_is_fixture_only_and_governed(self):
        contract = build_pumpswap_adapter_contract()
        self.assertTrue(contract.fixture_only)
        self.assertFalse(contract.supports_network_execution)
        self.assertTrue(contract.requires_governor_context)
        self.assertFalse(contract.enabled_by_default)

    def test_pumpswap_has_read_only_restriction(self):
        defn = SOURCE_REGISTRY["pumpswap"]
        self.assertEqual(defn.restriction, "read_only_confirmation")


# ---------------------------------------------------------------------------
# Class 2: Adapter metadata and safety
# ---------------------------------------------------------------------------

class PumpSwapAdapterSafetyTests(unittest.TestCase):

    def test_adapter_is_disabled_by_default(self):
        adapter = build_pumpswap_adapter()
        self.assertFalse(adapter.enabled)

    def test_adapter_requires_explicit_transport(self):
        adapter = build_pumpswap_adapter()
        with self.assertRaises(PermissionError):
            adapter.execute(None)

    def test_adapter_metadata_is_read_only_fixture_only_governed(self):
        meta = PumpSwapAdapterMetadata()
        self.assertEqual(meta.source_name, PUMPSWAP_SOURCE_NAME)
        self.assertFalse(meta.enabled_by_default)
        self.assertTrue(meta.requires_governor_context)
        self.assertFalse(meta.supports_network_execution)
        self.assertTrue(meta.fixture_transport_only)
        self.assertTrue(meta.read_only)

    def test_adapter_module_does_not_contain_forbidden_terms(self):
        source_text = (
            SRC_PATH / "printer_v1" / "sources" / "pumpswap.py"
        ).read_text(encoding="utf-8")
        for term in FORBIDDEN_FRAGMENTS:
            self.assertNotIn(term, source_text, f"Forbidden term '{term}' in pumpswap.py")

    def test_adapter_does_not_import_requests_or_httpx(self):
        source_text = (
            SRC_PATH / "printer_v1" / "sources" / "pumpswap.py"
        ).read_text(encoding="utf-8")
        for fragment in ("requests.get", "requests.post", "httpx", "aiohttp"):
            self.assertNotIn(fragment, source_text)

    def test_forbidden_request_kinds_are_rejected(self):
        for forbidden in FORBIDDEN_REQUEST_KINDS:
            result = normalize_pumpswap_payload(
                _pool_confirmation_payload(), request_kind=forbidden
            )
            self.assertEqual(result.source_status.value, "FAILED",
                             f"Expected FAILED for forbidden kind: {forbidden}")
            self.assertIn("not_allowed", result.failure_type)


# ---------------------------------------------------------------------------
# Class 3: Payload normalization
# ---------------------------------------------------------------------------

class PumpSwapPayloadNormalizationTests(unittest.TestCase):

    def _normalize(self, payload, *, request_kind="pumpswap_pool_confirmation"):
        return normalize_pumpswap_payload(payload, request_kind=request_kind)

    def test_valid_pool_confirmation_normalizes_correctly(self):
        result = self._normalize(_pool_confirmation_payload())
        self.assertEqual(result.source_status.value, "COMPLETE")
        self.assertEqual(result.data_quality_label.value, "CLEAN_DATA")
        tokens = result.normalized_payload["tokens"]
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]["mint"], "ps-pool-mint-1")
        self.assertEqual(tokens[0]["pairAddress"], "ps-pool-addr-1")
        self.assertEqual(tokens[0]["chain"], "solana")

    def test_migration_pool_reference_normalizes_correctly(self):
        result = self._normalize(
            _migration_pool_payload(), request_kind="pumpswap_migration_pool_reference"
        )
        self.assertEqual(result.source_status.value, "COMPLETE")
        tokens = result.normalized_payload["tokens"]
        self.assertEqual(tokens[0]["mint"], "ps-mig-mint-1")
        self.assertEqual(tokens[0]["pairAddress"], "ps-mig-pool-1")

    def test_liquidity_reference_normalizes_correctly(self):
        result = self._normalize(
            _liquidity_ref_payload(), request_kind="pumpswap_liquidity_reference"
        )
        self.assertEqual(result.source_status.value, "COMPLETE")

    def test_raw_pools_list_normalizes_correctly(self):
        result = self._normalize(_raw_pools_payload())
        self.assertEqual(result.source_status.value, "COMPLETE")
        tokens = result.normalized_payload["tokens"]
        self.assertEqual(tokens[0]["mint"], "ps-raw-mint-1")
        self.assertEqual(tokens[0]["pairAddress"], "ps-raw-pool-1")
        self.assertEqual(float(tokens[0]["liquidity_usd"]), 6000.0)

    def test_non_solana_pool_filtered_out(self):
        payload = {
            "tokens": [{
                "chain": "ethereum",
                "mint": "eth-mint",
                "pairAddress": "eth-pool",
                "liquidity_usd": 10000.0,
            }]
        }
        result = self._normalize(payload)
        self.assertEqual(result.source_status.value, "FAILED")
        self.assertIn("no_valid_solana_pools", result.failure_type)

    def test_missing_mint_in_raw_pool_is_skipped(self):
        payload = {"pools": [{"pool_address": "some-pool", "liquidity_usd": 5000}]}
        result = self._normalize(payload)
        self.assertEqual(result.source_status.value, "FAILED")

    def test_missing_pool_address_in_raw_pool_is_skipped(self):
        payload = {"pools": [{"base_mint": "some-mint", "liquidity_usd": 5000}]}
        result = self._normalize(payload)
        self.assertEqual(result.source_status.value, "FAILED")

    def test_missing_pool_list_returns_failed(self):
        result = self._normalize({"unexpected_key": []})
        self.assertEqual(result.source_status.value, "FAILED")

    def test_fixture_failure_transport_returns_failed_result(self):
        adapter = build_pumpswap_adapter(
            enabled=True, fixture_transport=fixture_failure_transport()
        )
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db_path = pathlib.Path(tmp.name) / "ps-fail.sqlite3"
        apply_migrations(db_path)
        try:
            req = build_governed_source_request(
                "pumpswap", "pumpswap_pool_confirmation", request_key="ps-fail-test"
            )
            res = execute_source_request_with_governor(db_path, req, adapter)
            self.assertEqual(res.normalized_result.source_status.value, "FAILED")
            self.assertIsNone(res.response_record)
        finally:
            tmp.cleanup()

    def test_normalized_output_does_not_contain_execution_fields(self):
        result = self._normalize(_pool_confirmation_payload())
        pool = result.normalized_payload["tokens"][0]
        for field in ("instruction", "signed_tx", "wallet", "private_key"):
            self.assertNotIn(field, pool)


# ---------------------------------------------------------------------------
# Class 4: Governed execution
# ---------------------------------------------------------------------------

class PumpSwapGovernedExecutionTests(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = make_db()

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, payload, *, request_kind="pumpswap_pool_confirmation"):
        adapter = build_pumpswap_adapter(
            enabled=True, fixture_transport=fixture_success_transport(payload)
        )
        req = build_governed_source_request(
            "pumpswap", request_kind, request_key=f"ps-governed-{request_kind}"
        )
        return execute_source_request_with_governor(self.db_path, req, adapter)

    def test_pool_confirmation_governed_execution_records_source_request_and_response(self):
        result = self._run(_pool_confirmation_payload())
        self.assertIsNotNone(result.request_record)
        self.assertIsNotNone(result.response_record)
        self.assertIsNone(result.failure_record)

    def test_migration_pool_reference_governed_execution_succeeds(self):
        result = self._run(
            _migration_pool_payload(), request_kind="pumpswap_migration_pool_reference"
        )
        self.assertEqual(result.normalized_result.source_status.value, "COMPLETE")

    def test_liquidity_reference_governed_execution_succeeds(self):
        result = self._run(
            _liquidity_ref_payload(), request_kind="pumpswap_liquidity_reference"
        )
        self.assertEqual(result.normalized_result.source_status.value, "COMPLETE")

    def test_governed_execution_does_not_write_downstream_tables(self):
        self._run(_pool_confirmation_payload())
        for table in DOWNSTREAM_TABLES:
            self.assertEqual(count_rows(self.db_path, table), 0, table)

    def test_adapter_requires_governor_approval(self):
        from printer_v1.sources.contracts import SourceAdapterContext, SourceRequest
        adapter = build_pumpswap_adapter(
            enabled=True,
            fixture_transport=fixture_success_transport(_pool_confirmation_payload()),
        )
        fake_req = SourceRequest(
            source_name="pumpswap",
            request_kind="pumpswap_pool_confirmation",
            request_key="bad-context",
        )
        bad_context = SourceAdapterContext(
            request=fake_req,
            request_record=None,
            decision=None,
            governor_approved=False,
        )
        with self.assertRaises(PermissionError):
            adapter.execute(bad_context)


# ---------------------------------------------------------------------------
# Class 5: Discovery CLI integration
# ---------------------------------------------------------------------------

class PumpSwapCLIIntegrationTests(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = make_db()

    def tearDown(self):
        self._tmp.cleanup()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def test_pool_confirmation_records_pumpswap_pool_confirmation_channel(self):
        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path, request_kind="pumpswap_pool_confirmation"),
            transport=lambda ctx: _pool_confirmation_payload(),
        )
        self.assertEqual(result["source_name"], "pumpswap")
        self.assertEqual(
            result["source_channel"], DiscoveryChannelLabel.PUMPSWAP_POOL_CONFIRMATION.value
        )
        self.assertEqual(result["source_channel_reason"], "pumpswap_pool_confirmation")

    def test_migration_pool_reference_records_correct_channel(self):
        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path, request_kind="pumpswap_migration_pool_reference"),
            transport=lambda ctx: _migration_pool_payload(),
        )
        self.assertEqual(
            result["source_channel"],
            DiscoveryChannelLabel.PUMPSWAP_MIGRATION_POOL_REFERENCE.value,
        )

    def test_liquidity_reference_records_correct_channel(self):
        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path, request_kind="pumpswap_liquidity_reference"),
            transport=lambda ctx: _liquidity_ref_payload(),
        )
        self.assertEqual(
            result["source_channel"],
            DiscoveryChannelLabel.PUMPSWAP_LIQUIDITY_REFERENCE.value,
        )

    def test_valid_pool_accepted_by_sprint_a_hard_gates(self):
        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path), transport=lambda ctx: _pool_confirmation_payload()
        )
        if result["candidates_accepted"] > 0:
            self.assertIn(
                result["accepted_candidates"][0]["tracking_label"],
                {"TRACK_NORMAL", "TRACK_FAST"},
            )

    def test_no_transport_raises(self):
        with self.assertRaises(ValueError):
            build_discover_candidates_once_payload(
                _cli_args(self.db_path), transport=None
            )

    def test_source_channel_stored_in_discovery_candidates_table(self):
        build_discover_candidates_once_payload(
            _cli_args(self.db_path), transport=lambda ctx: _pool_confirmation_payload()
        )
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT source_channel FROM printer_discovery_candidates"
            ).fetchall()
        for row in rows:
            if row["source_channel"] is not None:
                self.assertEqual(
                    row["source_channel"],
                    DiscoveryChannelLabel.PUMPSWAP_POOL_CONFIRMATION.value,
                )

    def test_no_downstream_unlocks_after_pumpswap_confirmation(self):
        build_discover_candidates_once_payload(
            _cli_args(self.db_path), transport=lambda ctx: _pool_confirmation_payload()
        )
        for table in DOWNSTREAM_TABLES:
            self.assertEqual(count_rows(self.db_path, table), 0, table)

    def test_dexscreener_unchanged_after_pumpswap_added(self):
        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path, source_name="dexscreener", request_kind=None),
            transport=lambda ctx: {
                "pairs": [{
                    "chainId": "solana",
                    "pairAddress": "dex-ctrl-d-pair",
                    "baseToken": {"address": "dex-ctrl-d-mint"},
                    "priceUsd": "0.001",
                    "liquidity": {"usd": 9000},
                    "volume": {"m5": 1500, "h1": 10000, "h24": 50000},
                    "txns": {"m5": {"buys": 10, "sells": 7}},
                }]
            },
        )
        self.assertEqual(result["source_name"], "dexscreener")
        self.assertEqual(result["source_channel"], DiscoveryChannelLabel.DEXSCREENER_SEARCH.value)

    def test_geckoterminal_unchanged_after_pumpswap_added(self):
        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path, source_name="geckoterminal",
                      request_kind="geckoterminal_new_pool_discovery"),
            transport=lambda ctx: {
                "data": [{
                    "id": "solana_gt-d-pool",
                    "type": "pool",
                    "attributes": {
                        "address": "gt-d-pool",
                        "name": "GT / SOL",
                        "base_token_price_usd": "0.002",
                        "reserve_in_usd": "8000",
                        "fdv_usd": "200000",
                        "volume_usd": {"m5": "200", "h1": "1500", "h24": "8000"},
                        "transactions": {
                            "m5": {"buys": 4, "sells": 3},
                            "h1": {"buys": 20, "sells": 15},
                        },
                    },
                    "relationships": {
                        "base_token": {"data": {"id": "solana_gt-d-mint", "type": "token"}},
                        "network": {"data": {"id": "solana", "type": "network"}},
                    },
                }]
            },
        )
        self.assertEqual(result["source_name"], "geckoterminal")

    def test_pumpportal_unchanged_after_pumpswap_added(self):
        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path, source_name="pumpportal",
                      request_kind="pumpfun_launch_stream"),
            transport=lambda ctx: {
                "tokens": [{
                    "chain": "solana",
                    "mint": "pp-d-ctrl-mint",
                    "pairAddress": "pp-d-ctrl-pair",
                    "symbol": "PPDC",
                    "name": "PumpPortal D Control",
                    "dex": "pumpfun",
                    "poolSource": "pumpportal",
                    "price_usd": "0.00001",
                    "liquidity_usd": 2500.0,
                    "captured_at": "2026-06-25T12:00:00+00:00",
                }]
            },
        )
        self.assertEqual(result["source_name"], "pumpportal")
        self.assertEqual(result["source_channel"], DiscoveryChannelLabel.PUMPFUN_NEW_TOKEN.value)


# ---------------------------------------------------------------------------
# Class 6: PumpSwap channel labels — metadata only
# ---------------------------------------------------------------------------

class PumpSwapChannelLabelTests(unittest.TestCase):

    PUMPSWAP_LABELS = (
        DiscoveryChannelLabel.PUMPSWAP_POOL_CONFIRMATION,
        DiscoveryChannelLabel.PUMPSWAP_MIGRATION_POOL_REFERENCE,
        DiscoveryChannelLabel.PUMPSWAP_LIQUIDITY_REFERENCE,
        DiscoveryChannelLabel.PUMPSWAP_GRADUATED,
    )

    def test_pumpswap_labels_are_defined(self):
        for label in self.PUMPSWAP_LABELS:
            self.assertIsInstance(label.value, str)
            self.assertTrue(label.value.startswith("PUMPSWAP_"))

    def test_pumpswap_labels_do_not_contain_forbidden_terms(self):
        all_values = " ".join(label.value.lower() for label in self.PUMPSWAP_LABELS)
        for term in FORBIDDEN_FRAGMENTS:
            self.assertNotIn(term, all_values)

    def test_pumpswap_labels_are_pure_string_constants(self):
        for label in self.PUMPSWAP_LABELS:
            self.assertIsInstance(label.value, str)
            self.assertFalse(any(c.isdigit() for c in label.value))

    def test_pumpswap_labels_do_not_reference_execution_concepts(self):
        for label in self.PUMPSWAP_LABELS:
            v = label.value.lower()
            self.assertNotIn("buy", v)
            self.assertNotIn("sell", v)
            self.assertNotIn("position", v)
            self.assertNotIn("pnl", v)
            self.assertNotIn("retrieval", v)
            self.assertNotIn("paper", v)


if __name__ == "__main__":
    unittest.main()

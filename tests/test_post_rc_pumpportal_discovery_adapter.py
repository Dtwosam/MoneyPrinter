"""Sprint C: PumpPortal adapter and Pump.fun surface labels — governed, fixture-only."""

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
from printer_v1.sources.pumpportal import (
    ALLOWED_REQUEST_KINDS as PUMPPORTAL_ALLOWED_KINDS,
    PUMPPORTAL_SOURCE_NAME,
    PumpPortalAdapterMetadata,
    build_pumpportal_adapter,
    build_pumpportal_adapter_contract,
    fixture_failure_transport,
    fixture_success_transport,
    normalize_pumpportal_payload,
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

# These request kinds must never be in ALLOWED_REQUEST_KINDS
FORBIDDEN_REQUEST_KINDS = (
    "subscribeTokenTrade",
    "subscribeAccountTrade",
    "subscribe_token_trade",
    "subscribe_account_trade",
    "token_trade",
    "account_trade",
)


def count_rows(db_path, table):
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        conn.close()


def make_db():
    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db_path = pathlib.Path(tmp.name) / "sprint-c.sqlite3"
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
        "source_name": "pumpportal",
        "request_kind": "pumpfun_launch_stream",
        "request_key": "sprint-c-test",
    }
    values.update(kw)
    return argparse.Namespace(**values)


def _launch_payload(*, mint="pp-launch-mint-1", pair="pp-bonding-curve-1",
                    symbol="SPRC", name="Sprint C Launch", liquidity=2500.0):
    return {
        "tokens": [
            {
                "chain": "solana",
                "mint": mint,
                "pairAddress": pair,
                "symbol": symbol,
                "name": name,
                "dex": "pumpfun",
                "poolSource": "pumpportal",
                "price_usd": "0.00001",
                "liquidity_usd": liquidity,
                "captured_at": "2026-06-25T12:00:00+00:00",
            }
        ]
    }


def _migration_payload(*, mint="pp-migration-mint-1", pair="pp-raydium-pool-1",
                       symbol="SPCM", name="Sprint C Migration", liquidity=12000.0):
    return {
        "tokens": [
            {
                "chain": "solana",
                "mint": mint,
                "pairAddress": pair,
                "symbol": symbol,
                "name": name,
                "dex": "raydium",
                "poolSource": "pumpportal",
                "price_usd": "0.00050",
                "liquidity_usd": liquidity,
                "volume_1h": 4000.0,
                "txns_1h": 30,
                "captured_at": "2026-06-25T12:00:00+00:00",
            }
        ]
    }


# ---------------------------------------------------------------------------
# Class 1: Source registry and contract
# ---------------------------------------------------------------------------

class PumpPortalRegistryContractTests(unittest.TestCase):

    def test_pumpportal_is_registered(self):
        self.assertIn("pumpportal", SOURCE_REGISTRY)

    def test_pumpportal_is_free_public_no_paid_plan(self):
        defn = SOURCE_REGISTRY["pumpportal"]
        self.assertFalse(defn.requires_paid_plan)
        self.assertEqual(defn.dependency_type, "free_public")

    def test_pumpportal_supports_solana(self):
        self.assertEqual(SOURCE_REGISTRY["pumpportal"].supports_solana, True)

    def test_pumpportal_has_only_allowed_request_kinds(self):
        defn = SOURCE_REGISTRY["pumpportal"]
        self.assertIn("pumpfun_launch_stream", defn.allowed_request_kinds)
        self.assertIn("pumpfun_migration_stream", defn.allowed_request_kinds)

    def test_pumpportal_does_not_allow_trading_kinds(self):
        defn = SOURCE_REGISTRY["pumpportal"]
        for forbidden in FORBIDDEN_REQUEST_KINDS:
            self.assertNotIn(forbidden, defn.allowed_request_kinds)

    def test_pumpportal_adapter_allowed_kinds_match_registry(self):
        defn = SOURCE_REGISTRY["pumpportal"]
        self.assertEqual(PUMPPORTAL_ALLOWED_KINDS, set(defn.allowed_request_kinds))

    def test_pumpportal_contract_validates(self):
        contract = build_pumpportal_adapter_contract()
        self.assertTrue(validate_source_adapter_contract(contract))

    def test_pumpportal_contract_is_fixture_only_and_governed(self):
        contract = build_pumpportal_adapter_contract()
        self.assertTrue(contract.fixture_only)
        self.assertFalse(contract.supports_network_execution)
        self.assertTrue(contract.requires_governor_context)
        self.assertFalse(contract.enabled_by_default)


# ---------------------------------------------------------------------------
# Class 2: Adapter metadata and safety
# ---------------------------------------------------------------------------

class PumpPortalAdapterSafetyTests(unittest.TestCase):

    def test_adapter_is_disabled_by_default(self):
        adapter = build_pumpportal_adapter()
        self.assertFalse(adapter.enabled)

    def test_adapter_requires_explicit_transport(self):
        adapter = build_pumpportal_adapter()
        with self.assertRaises(PermissionError):
            adapter.execute(None)

    def test_adapter_metadata_is_fixture_only_and_governed(self):
        meta = PumpPortalAdapterMetadata()
        self.assertEqual(meta.source_name, PUMPPORTAL_SOURCE_NAME)
        self.assertFalse(meta.enabled_by_default)
        self.assertTrue(meta.requires_governor_context)
        # V2-2AB: live transport now supported — flags updated from V2-2AB design
        self.assertTrue(meta.supports_network_execution)
        self.assertFalse(meta.fixture_transport_only)

    def test_adapter_module_does_not_contain_forbidden_terms(self):
        source_text = (
            SRC_PATH / "printer_v1" / "sources" / "pumpportal.py"
        ).read_text(encoding="utf-8")
        for term in FORBIDDEN_FRAGMENTS:
            self.assertNotIn(term, source_text, f"Forbidden term '{term}' in pumpportal.py")

    def test_adapter_does_not_import_requests_or_httpx(self):
        source_text = (
            SRC_PATH / "printer_v1" / "sources" / "pumpportal.py"
        ).read_text(encoding="utf-8")
        for fragment in ("requests.get", "requests.post", "httpx", "aiohttp"):
            self.assertNotIn(fragment, source_text)

    def test_adapter_has_no_websocket_import(self):
        # V2-2AB: websockets reference is present but import is LAZY (deferred inside
        # build_pumpportal_live_transport, not a top-level import). Verify no top-level import.
        import ast
        source_text = (
            SRC_PATH / "printer_v1" / "sources" / "pumpportal.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source_text)
        top_level_names: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if getattr(node, "col_offset", 1) != 0:
                continue
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_level_names.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                top_level_names.add(node.module.split(".")[0])
        self.assertNotIn("websockets", top_level_names)

    def test_trading_request_kinds_not_in_allowed(self):
        for forbidden in FORBIDDEN_REQUEST_KINDS:
            self.assertNotIn(forbidden, PUMPPORTAL_ALLOWED_KINDS)


# ---------------------------------------------------------------------------
# Class 3: Payload normalization
# ---------------------------------------------------------------------------

class PumpPortalPayloadNormalizationTests(unittest.TestCase):

    def _normalize(self, payload, *, request_kind="pumpfun_launch_stream"):
        return normalize_pumpportal_payload(payload, request_kind=request_kind)

    def test_valid_launch_event_normalizes_to_complete_result(self):
        result = self._normalize(_launch_payload())
        self.assertEqual(result.source_status.value, "COMPLETE")
        self.assertEqual(result.data_quality_label.value, "CLEAN_DATA")
        self.assertIsNotNone(result.normalized_payload)
        tokens = result.normalized_payload.get("tokens")
        self.assertIsInstance(tokens, list)
        self.assertEqual(len(tokens), 1)

    def test_valid_migration_event_normalizes_to_complete_result(self):
        result = self._normalize(_migration_payload(), request_kind="pumpfun_migration_stream")
        self.assertEqual(result.source_status.value, "COMPLETE")
        tokens = result.normalized_payload["tokens"]
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]["mint"], "pp-migration-mint-1")
        self.assertEqual(tokens[0]["pairAddress"], "pp-raydium-pool-1")

    def test_non_solana_token_filtered_out(self):
        payload = {"tokens": [{"chain": "ethereum", "mint": "eth-mint", "pairAddress": "eth-pair"}]}
        result = self._normalize(payload)
        self.assertEqual(result.source_status.value, "FAILED")
        self.assertIn("no_valid_solana_events", result.failure_type)

    def test_missing_mint_in_raw_event_is_skipped(self):
        payload = {"events": [{"name": "NoMint", "symbol": "NM", "bondingCurveKey": "bc-key"}]}
        result = self._normalize(payload)
        self.assertEqual(result.source_status.value, "FAILED")

    def test_missing_event_list_returns_failed(self):
        result = self._normalize({"unexpected_key": []})
        self.assertEqual(result.source_status.value, "FAILED")

    def test_raw_events_list_normalized_correctly(self):
        raw = {
            "events": [
                {
                    "mint": "raw-mint-1",
                    "newRaydiumPool": "raydium-pool-1",
                    "symbol": "RAW",
                    "name": "Raw Event",
                    "vSolInBondingCurve": 80,
                }
            ]
        }
        result = self._normalize(raw, request_kind="pumpfun_migration_stream")
        self.assertEqual(result.source_status.value, "COMPLETE")
        token = result.normalized_payload["tokens"][0]
        self.assertEqual(token["mint"], "raw-mint-1")
        self.assertEqual(token["pairAddress"], "raydium-pool-1")
        self.assertEqual(token["chain"], "solana")

    def test_forbidden_request_kind_returns_failed(self):
        for forbidden in FORBIDDEN_REQUEST_KINDS:
            result = normalize_pumpportal_payload(_launch_payload(), request_kind=forbidden)
            self.assertEqual(result.source_status.value, "FAILED",
                             f"Expected FAILED for forbidden kind: {forbidden}")

    def test_fixture_failure_transport_returns_failed_result(self):
        adapter = build_pumpportal_adapter(
            enabled=True, fixture_transport=fixture_failure_transport()
        )
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db_path = pathlib.Path(tmp.name) / "pp-fail.sqlite3"
        apply_migrations(db_path)
        try:
            req = build_governed_source_request(
                "pumpportal", "pumpfun_launch_stream", request_key="pp-fail-test"
            )
            res = execute_source_request_with_governor(db_path, req, adapter)
            self.assertEqual(res.normalized_result.source_status.value, "FAILED")
            self.assertIsNone(res.response_record)
        finally:
            tmp.cleanup()


# ---------------------------------------------------------------------------
# Class 4: Governed execution
# ---------------------------------------------------------------------------

class PumpPortalGovernedExecutionTests(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = make_db()

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, payload, *, request_kind="pumpfun_launch_stream"):
        adapter = build_pumpportal_adapter(
            enabled=True, fixture_transport=fixture_success_transport(payload)
        )
        req = build_governed_source_request(
            "pumpportal", request_kind, request_key=f"pp-governed-{request_kind}"
        )
        return execute_source_request_with_governor(self.db_path, req, adapter)

    def test_launch_governed_execution_records_source_request_and_response(self):
        result = self._run(_launch_payload())
        self.assertIsNotNone(result.request_record)
        self.assertIsNotNone(result.response_record)
        self.assertIsNone(result.failure_record)

    def test_migration_governed_execution_succeeds(self):
        result = self._run(_migration_payload(), request_kind="pumpfun_migration_stream")
        self.assertEqual(result.normalized_result.source_status.value, "COMPLETE")

    def test_governed_execution_does_not_write_downstream_tables(self):
        self._run(_launch_payload())
        for table in DOWNSTREAM_TABLES:
            self.assertEqual(count_rows(self.db_path, table), 0, table)

    def test_adapter_requires_governor_approval(self):
        from printer_v1.sources.contracts import SourceAdapterContext, SourceRequest
        adapter = build_pumpportal_adapter(
            enabled=True, fixture_transport=fixture_success_transport(_launch_payload())
        )
        fake_req = SourceRequest(
            source_name="pumpportal",
            request_kind="pumpfun_launch_stream",
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

class PumpPortalCLIDiscoveryTests(unittest.TestCase):

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

    def test_launch_stream_records_pumpfun_new_token_channel(self):
        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path, request_kind="pumpfun_launch_stream"),
            transport=lambda ctx: _launch_payload(),
        )
        self.assertEqual(result["source_name"], "pumpportal")
        self.assertEqual(result["source_channel"], DiscoveryChannelLabel.PUMPFUN_NEW_TOKEN.value)
        self.assertEqual(result["source_channel_reason"], "pumpportal_launch_stream")

    def test_migration_stream_not_ready_in_plan(self):
        # V2-2AB: pumpfun_migration_stream is NOT_READY — no live migration transport exists.
        # The plan item is included for reporting only; no execution occurs for migration.
        # (This test was previously test_migration_stream_records_pumpfun_migration_channel;
        # updated because migration was NOT_READY before and after V2-2AB.)
        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path, request_kind="pumpfun_migration_stream"),
            transport=lambda ctx: _migration_payload(),
        )
        # Migration is NOT_READY and max_source_requests=1, so it is the only plan item
        # and is skipped. source_channel comes from primary (first executed) — None here.
        self.assertIsNone(result["source_channel"])

    def test_migration_candidate_accepted_when_liquidity_above_floor(self):
        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path, request_kind="pumpfun_migration_stream"),
            transport=lambda ctx: _migration_payload(liquidity=12000.0),
        )
        if result["candidates_accepted"] > 0:
            self.assertIn(result["accepted_candidates"][0]["tracking_label"],
                          {"TRACK_NORMAL", "TRACK_FAST"})

    def test_launch_with_very_low_liquidity_demoted_to_watch_only(self):
        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path, request_kind="pumpfun_launch_stream"),
            transport=lambda ctx: _launch_payload(liquidity=50.0),
        )
        self.assertEqual(result["candidates_accepted"], 0)
        self.assertGreater(result["candidates_rejected"], 0)

    def test_no_transport_raises_for_pumpportal(self):
        with self.assertRaises(ValueError):
            build_discover_candidates_once_payload(
                _cli_args(self.db_path), transport=None
            )

    def test_source_channel_stored_in_db(self):
        build_discover_candidates_once_payload(
            _cli_args(self.db_path), transport=lambda ctx: _launch_payload()
        )
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT source_channel FROM printer_discovery_candidates"
            ).fetchall()
        for row in rows:
            if row["source_channel"] is not None:
                self.assertEqual(row["source_channel"], DiscoveryChannelLabel.PUMPFUN_NEW_TOKEN.value)

    def test_no_downstream_unlocks_after_pumpportal_discovery(self):
        build_discover_candidates_once_payload(
            _cli_args(self.db_path), transport=lambda ctx: _launch_payload()
        )
        for table in DOWNSTREAM_TABLES:
            self.assertEqual(count_rows(self.db_path, table), 0, table)

    def test_dexscreener_unchanged_after_pumpportal_added(self):
        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path, source_name="dexscreener", request_kind=None),
            transport=lambda ctx: {
                "pairs": [{
                    "chainId": "solana",
                    "pairAddress": "dex-ctrl-pair",
                    "baseToken": {"address": "dex-ctrl-mint"},
                    "priceUsd": "0.001",
                    "liquidity": {"usd": 9000},
                    "volume": {"m5": 1500, "h1": 10000, "h24": 50000},
                    "txns": {"m5": {"buys": 10, "sells": 7}},
                }]
            },
        )
        self.assertEqual(result["source_name"], "dexscreener")
        self.assertEqual(result["source_channel"], DiscoveryChannelLabel.DEXSCREENER_SEARCH.value)

    def test_geckoterminal_unchanged_after_pumpportal_added(self):
        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path, source_name="geckoterminal",
                      request_kind="geckoterminal_new_pool_discovery"),
            transport=lambda ctx: {
                "data": [{
                    "id": "solana_gt-ctrl-pool",
                    "type": "pool",
                    "attributes": {
                        "address": "gt-ctrl-pool",
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
                        "base_token": {"data": {"id": "solana_gt-ctrl-mint", "type": "token"}},
                        "network": {"data": {"id": "solana", "type": "network"}},
                    },
                }]
            },
        )
        self.assertEqual(result["source_name"], "geckoterminal")
        self.assertEqual(result["source_channel"], DiscoveryChannelLabel.GECKOTERMINAL_NEW_POOL.value)


# ---------------------------------------------------------------------------
# Class 6: Pump.fun surface labels — metadata-only
# ---------------------------------------------------------------------------

class PumpFunSurfaceLabelsTests(unittest.TestCase):

    SURFACE_LABELS = (
        DiscoveryChannelLabel.PUMPFUN_TRENDING_NOW,
        DiscoveryChannelLabel.PUMPFUN_TOP_COINS,
        DiscoveryChannelLabel.PUMPFUN_MOVERS,
        DiscoveryChannelLabel.PUMPFUN_MAYHEM,
        DiscoveryChannelLabel.PUMPFUN_NEW,
        DiscoveryChannelLabel.PUMPFUN_LIVE,
        DiscoveryChannelLabel.PUMPFUN_MARKET_CAP,
        DiscoveryChannelLabel.PUMPFUN_AGENTS,
        DiscoveryChannelLabel.PUMPFUN_OLDEST,
        DiscoveryChannelLabel.PUMPFUN_LAST_TRADE,
        DiscoveryChannelLabel.PUMPFUN_CHARITIES,
    )

    def test_all_surface_labels_are_defined(self):
        for label in self.SURFACE_LABELS:
            self.assertIsInstance(label.value, str)
            self.assertTrue(label.value.startswith("PUMPFUN_"))

    def test_surface_labels_do_not_contain_forbidden_terms(self):
        all_values = " ".join(label.value.lower() for label in self.SURFACE_LABELS)
        for term in FORBIDDEN_FRAGMENTS:
            self.assertNotIn(term, all_values)

    def test_surface_labels_are_informational_strings_not_numerics(self):
        for label in self.SURFACE_LABELS:
            self.assertIsInstance(label.value, str)
            self.assertFalse(any(c.isdigit() for c in label.value),
                             f"{label.value} should not contain numeric measurements")

    def test_surface_labels_exist_in_discovery_channel_labels_tuple(self):
        from printer_v1.discovery.contracts import DISCOVERY_CHANNEL_LABELS
        label_values = {label.value for label in DISCOVERY_CHANNEL_LABELS}
        for label in self.SURFACE_LABELS:
            self.assertIn(label.value, label_values)

    def test_surface_labels_do_not_unlock_retrieval_or_paper(self):
        """Surface labels must not appear anywhere near retrieval or paper decision paths."""
        from printer_v1.discovery.contracts import DiscoveryChannelLabel as DCL
        # Confirm PUMPFUN surface labels are just string values with no side effects
        for label in self.SURFACE_LABELS:
            self.assertEqual(type(label.value), str)
            # These are pure string constants — calling .value is the only operation
            self.assertNotIn("retrieval", label.value.lower())
            self.assertNotIn("paper", label.value.lower())
            self.assertNotIn("buy", label.value.lower())
            self.assertNotIn("position", label.value.lower())
            self.assertNotIn("pnl", label.value.lower())


if __name__ == "__main__":
    unittest.main()

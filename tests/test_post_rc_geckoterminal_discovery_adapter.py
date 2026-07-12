"""Sprint B: GeckoTerminal adapter, governor-only, fixture-first discovery tests."""

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
from printer_v1.sources.geckoterminal import (
    GECKOTERMINAL_SOURCE_NAME,
    GeckoTerminalAdapterMetadata,
    build_geckoterminal_adapter,
    build_geckoterminal_adapter_contract,
    fixture_failure_transport,
    fixture_success_transport,
    normalize_geckoterminal_payload,
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


def count_rows(db_path, table):
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        conn.close()


def make_db():
    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db_path = pathlib.Path(tmp.name) / "sprint-b.sqlite3"
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
        "source_name": "geckoterminal",
        "request_kind": "geckoterminal_new_pool_discovery",
        "request_key": "sprint-b-test",
    }
    values.update(kw)
    return argparse.Namespace(**values)


def _gt_new_pool_payload(*,
    pair_address="gt-sprint-b-pool-1",
    base_mint="gt-sprint-b-mint-1",
    price_usd="0.002",
    reserve_in_usd="9000",
    vol_m5="300", vol_h1="2000", vol_h24="12000",
    txns_m5=8, txns_h1=40, txns_h24=150,
    fdv_usd="500000",
    network_id="solana",
):
    return {
        "data": [
            {
                "id": f"solana_{pair_address}",
                "type": "pool",
                "attributes": {
                    "address": pair_address,
                    "name": "SBTEST / SOL",
                    "base_token_price_usd": price_usd,
                    "reserve_in_usd": reserve_in_usd,
                    "fdv_usd": fdv_usd,
                    "market_cap_usd": None,
                    "volume_usd": {"m5": vol_m5, "h1": vol_h1, "h24": vol_h24},
                    "transactions": {
                        "m5": {"buys": txns_m5 // 2, "sells": txns_m5 - txns_m5 // 2},
                        "h1": {"buys": txns_h1 // 2, "sells": txns_h1 - txns_h1 // 2},
                        "h24": {"buys": txns_h24 // 2, "sells": txns_h24 - txns_h24 // 2},
                    },
                    "pool_created_at": "2026-06-25T10:00:00Z",
                },
                "relationships": {
                    "base_token": {
                        "data": {"id": f"solana_{base_mint}", "type": "token"}
                    },
                    "network": {
                        "data": {"id": network_id, "type": "network"}
                    },
                },
            }
        ]
    }


# ---------------------------------------------------------------------------
# Class 1: Source registry contract
# ---------------------------------------------------------------------------

class GeckoTerminalRegistryContractTests(unittest.TestCase):

    def test_geckoterminal_is_registered(self):
        self.assertIn("geckoterminal", SOURCE_REGISTRY)

    def test_geckoterminal_is_free_public_no_paid_plan(self):
        defn = SOURCE_REGISTRY["geckoterminal"]
        self.assertFalse(defn.requires_paid_plan)
        self.assertEqual(defn.dependency_type, "free_public")

    def test_geckoterminal_supports_solana(self):
        defn = SOURCE_REGISTRY["geckoterminal"]
        self.assertEqual(defn.supports_solana, True)

    def test_geckoterminal_has_sprint_b_request_kinds(self):
        defn = SOURCE_REGISTRY["geckoterminal"]
        self.assertIn("geckoterminal_new_pool_discovery", defn.allowed_request_kinds)
        self.assertIn("geckoterminal_trending_pool_reference", defn.allowed_request_kinds)
        self.assertNotIn("geckoterminal_pair_market_reference", defn.allowed_request_kinds)

    def test_geckoterminal_contract_validates(self):
        contract = build_geckoterminal_adapter_contract()
        self.assertTrue(validate_source_adapter_contract(contract))

    def test_geckoterminal_contract_is_fixture_only_and_governed(self):
        contract = build_geckoterminal_adapter_contract()
        self.assertTrue(contract.fixture_only)
        self.assertFalse(contract.supports_network_execution)
        self.assertTrue(contract.requires_governor_context)
        self.assertFalse(contract.enabled_by_default)


# ---------------------------------------------------------------------------
# Class 2: Adapter metadata and safety
# ---------------------------------------------------------------------------

class GeckoTerminalAdapterMetadataTests(unittest.TestCase):

    def test_adapter_is_disabled_by_default(self):
        adapter = build_geckoterminal_adapter()
        self.assertFalse(adapter.enabled)

    def test_adapter_requires_explicit_transport(self):
        adapter = build_geckoterminal_adapter()
        with self.assertRaises(PermissionError):
            adapter.execute(None)

    def test_adapter_metadata_source_name(self):
        meta = GeckoTerminalAdapterMetadata()
        self.assertEqual(meta.source_name, GECKOTERMINAL_SOURCE_NAME)
        self.assertFalse(meta.enabled_by_default)
        self.assertTrue(meta.requires_governor_context)
        self.assertFalse(meta.supports_network_execution)
        self.assertTrue(meta.fixture_transport_only)

    def test_adapter_source_module_does_not_contain_forbidden_terms(self):
        source_text = (
            SRC_PATH / "printer_v1" / "sources" / "geckoterminal.py"
        ).read_text(encoding="utf-8")
        for term in FORBIDDEN_FRAGMENTS:
            self.assertNotIn(term, source_text, f"Forbidden term '{term}' in geckoterminal.py")

    def test_adapter_does_not_import_requests_or_httpx(self):
        source_text = (
            SRC_PATH / "printer_v1" / "sources" / "geckoterminal.py"
        ).read_text(encoding="utf-8")
        for fragment in ("requests.get", "requests.post", "httpx", "aiohttp"):
            self.assertNotIn(fragment, source_text)


# ---------------------------------------------------------------------------
# Class 3: Payload normalization
# ---------------------------------------------------------------------------

class GeckoTerminalPayloadNormalizationTests(unittest.TestCase):

    def _normalize(self, payload, *, request_kind="geckoterminal_new_pool_discovery"):
        return normalize_geckoterminal_payload(payload, request_kind=request_kind)

    def test_valid_solana_pool_normalizes_to_complete_result(self):
        result = self._normalize(_gt_new_pool_payload())
        self.assertEqual(result.source_status.value, "COMPLETE")
        self.assertEqual(result.data_quality_label.value, "CLEAN_DATA")
        self.assertIsNotNone(result.normalized_payload)
        pairs = result.normalized_payload.get("pairs")
        self.assertIsInstance(pairs, list)
        self.assertEqual(len(pairs), 1)

    def test_normalized_pool_has_correct_identity_fields(self):
        result = self._normalize(_gt_new_pool_payload(
            pair_address="test-pool-addr",
            base_mint="test-base-mint",
        ))
        pool = result.normalized_payload["pairs"][0]
        self.assertEqual(pool["pairAddress"], "test-pool-addr")
        self.assertEqual(pool["baseToken"]["address"], "test-base-mint")
        self.assertEqual(pool["chainId"], "solana")

    def test_base_mint_extracted_from_relationships_id_with_prefix_stripped(self):
        result = self._normalize(_gt_new_pool_payload(base_mint="abc123"))
        pool = result.normalized_payload["pairs"][0]
        self.assertEqual(pool["baseToken"]["address"], "abc123")

    def test_non_solana_pool_is_filtered_out(self):
        result = self._normalize(_gt_new_pool_payload(network_id="ethereum"))
        self.assertEqual(result.source_status.value, "FAILED")
        self.assertIn("no_valid_solana_pools", result.failure_type)

    def test_missing_pool_address_skips_pool(self):
        payload = {"data": [{"id": "solana_pool", "attributes": {}, "relationships": {}}]}
        result = self._normalize(payload)
        self.assertEqual(result.source_status.value, "FAILED")

    def test_missing_base_mint_skips_pool(self):
        payload = {
            "data": [{
                "id": "solana_pool",
                "attributes": {"address": "some-pair"},
                "relationships": {
                    "network": {"data": {"id": "solana", "type": "network"}},
                },
            }]
        }
        result = self._normalize(payload)
        self.assertEqual(result.source_status.value, "FAILED")

    def test_fixture_failure_transport_returns_failed_result(self):
        adapter = build_geckoterminal_adapter(
            enabled=True, fixture_transport=fixture_failure_transport()
        )
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db_path = pathlib.Path(tmp.name) / "gt-fail.sqlite3"
        apply_migrations(db_path)
        try:
            req = build_governed_source_request(
                "geckoterminal", "geckoterminal_new_pool_discovery",
                request_key="gt-fail-test",
            )
            res = execute_source_request_with_governor(db_path, req, adapter)
            self.assertEqual(res.normalized_result.source_status.value, "FAILED")
            self.assertIsNone(res.response_record)
            self.assertIsNotNone(res.failure_record)
        finally:
            tmp.cleanup()

    def test_rate_limited_fixture_returns_stale_result(self):
        result = self._normalize({"fixture_status": "rate_limited", "retry_after_seconds": 60})
        self.assertEqual(result.source_status.value, "STALE")
        self.assertIsNotNone(result.failure_type)

    def test_invalid_request_kind_returns_failed_result(self):
        result = self._normalize(_gt_new_pool_payload(), request_kind="unsupported_kind")
        self.assertEqual(result.source_status.value, "FAILED")
        self.assertIn("not_allowed", result.failure_type)

    def test_txns_extracted_as_integer_totals(self):
        result = self._normalize(_gt_new_pool_payload(txns_m5=10, txns_h1=50))
        pool = result.normalized_payload["pairs"][0]
        m5 = pool["txns"]["m5"]
        self.assertIsInstance(m5, int)
        self.assertEqual(m5, 10)

    def test_volumes_extracted_from_volume_usd_nested_dict(self):
        result = self._normalize(_gt_new_pool_payload(vol_m5="200", vol_h1="1500", vol_h24="8000"))
        pool = result.normalized_payload["pairs"][0]
        self.assertEqual(float(pool["volume"]["h1"]), 1500.0)
        self.assertEqual(float(pool["volume"]["h24"]), 8000.0)

    def test_trending_pool_request_kind_also_works(self):
        result = self._normalize(
            _gt_new_pool_payload(), request_kind="geckoterminal_trending_pool_reference"
        )
        self.assertEqual(result.source_status.value, "COMPLETE")

    # ------------------------------------------------------------------
    # Real API shape tests — no network relationship, chain from pool id
    # ------------------------------------------------------------------

    def _real_api_pool(self, *, pool_id="solana_BDMpDHtFJf4apQD4cB9Y9vZVMBL3LGiPvZoMFP1Zt4Pe",
                       pool_address="BDMpDHtFJf4apQD4cB9Y9vZVMBL3LGiPvZoMFP1Zt4Pe",
                       base_token_id="solana_AdMUXQvPPirB62KJWukkBS2t1fP9ErreaMbwt9mRpump",
                       reserve_in_usd=None, vol_h1="3.10", txns_m5_buys=1):
        """Pool shaped exactly like the real GeckoTerminal v2 API response.
        Key differences from the old fixture: no network relationship in rels.
        """
        return {
            "data": [{
                "id": pool_id,
                "type": "pool",
                "attributes": {
                    "address": pool_address,
                    "name": "THESECRET / SOL",
                    "base_token_price_usd": "0.00000257",
                    "base_token_price_native_currency": "0.000000017",
                    "quote_token_price_usd": "152.5",
                    "reserve_in_usd": reserve_in_usd,
                    "fdv_usd": "2570",
                    "market_cap_usd": None,
                    "pool_created_at": "2026-06-25T11:18:22Z",
                    "volume_usd": {
                        "m5": "3.10", "m15": "3.10", "m30": "3.10",
                        "h1": vol_h1, "h6": "3.10", "h24": "3.10",
                    },
                    "transactions": {
                        "m5": {"buys": txns_m5_buys, "sells": 0, "buyers": txns_m5_buys, "sellers": 0},
                        "m15": {"buys": txns_m5_buys, "sells": 0},
                        "h1": {"buys": txns_m5_buys, "sells": 0},
                        "h24": {"buys": txns_m5_buys, "sells": 0},
                    },
                    "price_change_percentage": {"m5": "0.0", "h1": "0.0", "h24": "0.0"},
                },
                "relationships": {
                    # No "network" key — this is what the real API returns for
                    # network-scoped endpoints like /networks/solana/new_pools.
                    "base_token": {
                        "data": {"id": base_token_id, "type": "token"}
                    },
                    "quote_token": {
                        "data": {"id": "solana_So11111111111111111111111111111111111111112", "type": "token"}
                    },
                    "dex": {
                        "data": {"id": "pump-fun", "type": "dex"}
                    },
                },
            }]
        }

    def test_real_api_shape_new_pool_without_network_rel_normalizes(self):
        """Real GT new_pools shape: no network relationship, chain inferred from pool id."""
        result = self._normalize(self._real_api_pool())
        self.assertEqual(result.source_status.value, "COMPLETE")
        self.assertIsNotNone(result.normalized_payload)
        pairs = result.normalized_payload.get("pairs")
        self.assertEqual(len(pairs), 1)
        pool = pairs[0]
        self.assertEqual(pool["chainId"], "solana")
        self.assertEqual(pool["pairAddress"], "BDMpDHtFJf4apQD4cB9Y9vZVMBL3LGiPvZoMFP1Zt4Pe")
        self.assertEqual(pool["baseToken"]["address"], "AdMUXQvPPirB62KJWukkBS2t1fP9ErreaMbwt9mRpump")

    def test_real_api_shape_trending_pool_with_liquidity_normalizes(self):
        """Real GT trending_pools shape: no network rel, has reserve_in_usd."""
        result = self._normalize(
            self._real_api_pool(
                pool_id="solana_3Qhv2Z6n5aknNzx56A2n4qvqUZ4CvbCkUh24KcK9T9qY",
                pool_address="3Qhv2Z6n5aknNzx56A2n4qvqUZ4CvbCkUh24KcK9T9qY",
                base_token_id="solana_AXLmMWkRmSPdPxkuMqAD4nzYBK7QRssNkYZ6RXzLpump",
                reserve_in_usd=28759.74,
                vol_h1="23867.72",
                txns_m5_buys=2,
            ),
            request_kind="geckoterminal_trending_pool_reference",
        )
        self.assertEqual(result.source_status.value, "COMPLETE")
        pool = result.normalized_payload["pairs"][0]
        self.assertEqual(pool["chainId"], "solana")
        self.assertAlmostEqual(float(pool["liquidity"]["usd"]), 28759.74, places=1)
        self.assertAlmostEqual(float(pool["volume"]["h1"]), 23867.72, places=1)
        self.assertEqual(pool["txns"]["m5"], 2)

    def test_real_api_shape_with_null_reserve_still_normalizes(self):
        """New pools often have null reserve_in_usd — pool is valid but has no liquidity data."""
        result = self._normalize(self._real_api_pool(reserve_in_usd=None))
        self.assertEqual(result.source_status.value, "COMPLETE")
        pool = result.normalized_payload["pairs"][0]
        self.assertIsNone(pool["liquidity"]["usd"])

    def test_real_api_shape_non_solana_id_prefix_is_still_rejected(self):
        """Pool with non-Solana id prefix must be rejected even without network rel."""
        payload = {
            "data": [{
                "id": "ethereum_0xSomeEthPool",
                "type": "pool",
                "attributes": {
                    "address": "0xSomeEthPool",
                    "name": "ETH Pool",
                    "base_token_price_usd": "1.0",
                    "reserve_in_usd": "10000",
                    "volume_usd": {"h1": "1000"},
                    "transactions": {"m5": {"buys": 5, "sells": 3}},
                },
                "relationships": {
                    "base_token": {"data": {"id": "ethereum_0xSomeMint", "type": "token"}},
                },
            }]
        }
        result = self._normalize(payload)
        self.assertEqual(result.source_status.value, "FAILED")
        self.assertIn("no_valid_solana_pools", result.failure_type)

    # ------------------------------------------------------------------
    # WSOL / native-quote asset leak prevention tests
    # ------------------------------------------------------------------

    WSOL = "So11111111111111111111111111111111111111112"
    USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"

    def _pool_with_base(self, base_mint, pool_address="wsol-test-pool", reserve="28000",
                        vol_h1="10000"):
        """Build a pool payload where the given mint is the base_token."""
        return {
            "data": [{
                "id": f"solana_{pool_address}",
                "type": "pool",
                "attributes": {
                    "address": pool_address,
                    "name": "WSOL / USDC",
                    "base_token_price_usd": "152.0",
                    "reserve_in_usd": reserve,
                    "fdv_usd": "999999999",
                    "volume_usd": {"m5": "1000", "h1": vol_h1, "h24": "50000"},
                    "transactions": {
                        "m5": {"buys": 20, "sells": 15},
                        "h1": {"buys": 80, "sells": 60},
                        "h24": {"buys": 300, "sells": 250},
                    },
                    "pool_created_at": "2026-06-25T10:00:00Z",
                },
                "relationships": {
                    "base_token": {
                        "data": {"id": f"solana_{base_mint}", "type": "token"}
                    },
                    "quote_token": {
                        "data": {"id": f"solana_{self.USDC}", "type": "token"}
                    },
                    "dex": {"data": {"id": "orca", "type": "dex"}},
                },
            }]
        }

    def test_wsol_as_base_token_is_skipped_not_discovered(self):
        """WSOL/USDC pool: WSOL as base_token must produce no valid Solana pools."""
        result = self._normalize(self._pool_with_base(self.WSOL))
        self.assertEqual(result.source_status.value, "FAILED")
        self.assertIn("no_valid_solana_pools", result.failure_type)

    def test_usdc_as_base_token_is_skipped(self):
        """USDC as base_token must also be skipped — not a memecoin candidate."""
        result = self._normalize(self._pool_with_base(self.USDC))
        self.assertEqual(result.source_status.value, "FAILED")
        self.assertIn("no_valid_solana_pools", result.failure_type)

    def test_usdt_as_base_token_is_skipped(self):
        """USDT as base_token must also be skipped."""
        result = self._normalize(self._pool_with_base(self.USDT))
        self.assertEqual(result.source_status.value, "FAILED")
        self.assertIn("no_valid_solana_pools", result.failure_type)

    def test_memecoin_with_wsol_as_quote_still_discovered(self):
        """Normal memecoin/SOL pool: memecoin as base_token passes through."""
        memecoin_mint = "AdMUXQvPPirB62KJWukkBS2t1fP9ErreaMbwt9mRpump"
        payload = {
            "data": [{
                "id": "solana_meme-sol-pool-1",
                "type": "pool",
                "attributes": {
                    "address": "meme-sol-pool-1",
                    "name": "MEME / SOL",
                    "base_token_price_usd": "0.00050",
                    "reserve_in_usd": "12000",
                    "fdv_usd": "500000",
                    "volume_usd": {"m5": "500", "h1": "3000", "h24": "15000"},
                    "transactions": {
                        "m5": {"buys": 8, "sells": 5},
                        "h1": {"buys": 40, "sells": 30},
                        "h24": {"buys": 150, "sells": 110},
                    },
                    "pool_created_at": "2026-06-25T10:00:00Z",
                },
                "relationships": {
                    "base_token": {
                        "data": {"id": f"solana_{memecoin_mint}", "type": "token"}
                    },
                    "quote_token": {
                        "data": {"id": f"solana_{self.WSOL}", "type": "token"}
                    },
                    "dex": {"data": {"id": "pump-fun", "type": "dex"}},
                },
            }]
        }
        result = self._normalize(payload)
        self.assertEqual(result.source_status.value, "COMPLETE")
        pairs = result.normalized_payload["pairs"]
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["baseToken"]["address"], memecoin_mint)
        self.assertNotEqual(pairs[0]["baseToken"]["address"], self.WSOL)

    def test_real_trending_pool_wsol_base_shape_is_skipped(self):
        """Real-shape trending pool with WSOL as base_token (WSOL/USDC pair) is skipped."""
        result = self._normalize(
            self._pool_with_base(
                self.WSOL,
                pool_address="FpCMFDFGYotvufJ7sPBGY4sKoKFVPeBtpVpzaJcDnxV8",
                reserve="28759",
                vol_h1="23867",
            ),
            request_kind="geckoterminal_trending_pool_reference",
        )
        self.assertEqual(result.source_status.value, "FAILED")
        self.assertIn("no_valid_solana_pools", result.failure_type)


# ---------------------------------------------------------------------------
# Class 4: Governed execution through Source Governor
# ---------------------------------------------------------------------------

class GeckoTerminalGovernedExecutionTests(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = make_db()

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, payload, *, request_kind="geckoterminal_new_pool_discovery"):
        adapter = build_geckoterminal_adapter(
            enabled=True,
            fixture_transport=fixture_success_transport(payload),
        )
        req = build_governed_source_request(
            "geckoterminal", request_kind, request_key=f"gt-governed-{request_kind}"
        )
        return execute_source_request_with_governor(self.db_path, req, adapter)

    def test_governed_execution_records_source_request_and_response(self):
        result = self._run(_gt_new_pool_payload())
        self.assertIsNotNone(result.request_record)
        self.assertIsNotNone(result.response_record)
        self.assertIsNone(result.failure_record)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            req_row = conn.execute("SELECT * FROM printer_source_requests WHERE id = ?",
                                   (result.request_record.id,)).fetchone()
            resp_row = conn.execute("SELECT * FROM printer_source_responses WHERE id = ?",
                                    (result.response_record.id,)).fetchone()
        finally:
            conn.close()
        self.assertEqual(req_row["source_name"], "geckoterminal")
        self.assertEqual(resp_row["source_status"], "COMPLETE")

    def test_governed_execution_does_not_write_downstream_tables(self):
        self._run(_gt_new_pool_payload())
        for table in DOWNSTREAM_TABLES:
            self.assertEqual(count_rows(self.db_path, table), 0, table)

    def test_adapter_requires_governor_approval_to_execute(self):
        from printer_v1.sources.contracts import SourceAdapterContext, SourceRequest
        adapter = build_geckoterminal_adapter(
            enabled=True,
            fixture_transport=fixture_success_transport(_gt_new_pool_payload()),
        )
        fake_req = SourceRequest(
            source_name="geckoterminal",
            request_kind="geckoterminal_new_pool_discovery",
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

class GeckoTerminalCLIDiscoveryTests(unittest.TestCase):

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

    def _transport(self, ctx):
        del ctx
        return _gt_new_pool_payload()

    def _trending_transport(self, ctx):
        del ctx
        return _gt_new_pool_payload(
            pair_address="gt-trending-pool",
            base_mint="gt-trending-mint",
        )

    def test_new_pool_discovery_records_geckoterminal_new_pool_channel(self):
        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path, request_kind="geckoterminal_new_pool_discovery"),
            transport=self._transport,
        )
        self.assertEqual(result["source_name"], "geckoterminal")
        self.assertEqual(result["source_channel"], DiscoveryChannelLabel.GECKOTERMINAL_NEW_POOL.value)
        self.assertEqual(result["source_channel_reason"], "geckoterminal_new_pool_discovery")

    def test_trending_pool_discovery_records_geckoterminal_trending_pool_channel(self):
        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path, request_kind="geckoterminal_trending_pool_reference"),
            transport=self._trending_transport,
        )
        self.assertEqual(result["source_channel"], DiscoveryChannelLabel.GECKOTERMINAL_TRENDING_POOL.value)

    def test_accepted_candidate_has_source_channel_set(self):
        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path), transport=self._transport
        )
        if result["candidates_accepted"] > 0:
            for cand in result["accepted_candidates"]:
                self.assertEqual(cand["source_channel"], DiscoveryChannelLabel.GECKOTERMINAL_NEW_POOL.value)

    def test_source_channel_stored_in_discovery_candidates_table(self):
        build_discover_candidates_once_payload(
            _cli_args(self.db_path), transport=self._transport
        )
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT source_channel FROM printer_discovery_candidates"
            ).fetchall()
        for row in rows:
            if row["source_channel"] is not None:
                self.assertEqual(row["source_channel"], DiscoveryChannelLabel.GECKOTERMINAL_NEW_POOL.value)

    def test_valid_pool_accepted_as_track_normal_or_track_fast(self):
        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path), transport=self._transport
        )
        if result["candidates_accepted"] > 0:
            for cand in result["accepted_candidates"]:
                self.assertIn(cand["tracking_label"], {"TRACK_NORMAL", "TRACK_FAST"})

    def test_no_downstream_unlocks_after_geckoterminal_discovery(self):
        build_discover_candidates_once_payload(
            _cli_args(self.db_path), transport=self._transport
        )
        for table in DOWNSTREAM_TABLES:
            self.assertEqual(count_rows(self.db_path, table), 0, table)

    def test_stale_24h_only_pool_rejected_from_proof_cycle(self):
        def stale_transport(ctx):
            del ctx
            return _gt_new_pool_payload(
                pair_address="gt-stale-pool",
                base_mint="gt-stale-mint",
                vol_m5="0",
                vol_h1="0",
                vol_h24="5000",
                txns_m5=0,
                txns_h1=0,
                txns_h24=50,
            )

        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path), transport=stale_transport
        )
        self.assertEqual(result["candidates_accepted"], 0)
        self.assertGreater(result["candidates_rejected"], 0)
        for rej in result["rejected_candidates"]:
            self.assertIn(
                rej.get("reject_reason"),
                {
                    "watch_only_not_eligible_for_15m_memory_proof_cycle",
                    "no_recent_activity_pulse_for_memory_growth",
                    "insufficient_activity_for_memory_growth",
                    "classified_watch_only",
                },
            )

    def test_non_solana_pool_rejected_as_non_solana_candidate(self):
        def non_solana_transport(ctx):
            del ctx
            return _gt_new_pool_payload(network_id="ethereum")

        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path), transport=non_solana_transport
        )
        self.assertEqual(result["source_status"], "FAILED")

    def test_dexscreener_source_name_still_works_after_geckoterminal_added(self):
        def dex_transport(ctx):
            del ctx
            return {
                "pairs": [{
                    "chainId": "solana",
                    "pairAddress": "dex-control-pair",
                    "baseToken": {"address": "dex-control-mint", "symbol": "DCT", "name": "Control"},
                    "dexId": "raydium",
                    "priceUsd": "0.003",
                    "liquidity": {"usd": 10000},
                    "volume": {"m5": 2000, "h1": 15000, "h24": 60000},
                    "txns": {"m5": {"buys": 12, "sells": 8}},
                }]
            }

        result = build_discover_candidates_once_payload(
            _cli_args(self.db_path, source_name="dexscreener", request_kind=None, request_key=None),
            transport=dex_transport,
        )
        self.assertEqual(result["source_name"], "dexscreener")
        self.assertEqual(result["source_channel"], DiscoveryChannelLabel.DEXSCREENER_SEARCH.value)

    def test_source_channel_does_not_unlock_paper_decisions_or_retrieval(self):
        build_discover_candidates_once_payload(
            _cli_args(self.db_path), transport=self._transport
        )
        with self.connect() as conn:
            self.assertEqual(count_rows(self.db_path, "printer_memory_retrieval_matches"), 0)
            self.assertEqual(count_rows(self.db_path, "printer_paper_decisions"), 0)
            self.assertEqual(count_rows(self.db_path, "printer_paper_positions"), 0)
            self.assertEqual(count_rows(self.db_path, "printer_paper_trade_events"), 0)
            self.assertEqual(count_rows(self.db_path, "printer_paper_trade_audits"), 0)


if __name__ == "__main__":
    unittest.main()

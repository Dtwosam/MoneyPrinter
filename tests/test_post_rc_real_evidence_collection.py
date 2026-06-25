"""Post-RC real governed evidence collection tests.

Covers:
- GoPlus safety adapter: contract, governed execution, normalization
- Jupiter Quote adapter: contract, governed execution, normalization, no-tx path
- Real evidence orchestrator: safety + entry + exit quote collection
- Memory overlay: AUDIT_ONLY → CLEAN_MEMORY after valid real evidence
- Guardrails: no scoring/wallet/BUY/position/PnL, downstream tables untouched
"""

import argparse
import io
import json
import pathlib
import os
import sqlite3
import sys
import tempfile
import unittest
from urllib import error as url_error
from contextlib import contextmanager
from datetime import timedelta, timezone, datetime

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.evidence_fill.real import (
    RealEvidenceTarget,
    collect_real_evidence,
)
from printer_v1.operator_cli.commands import (
    build_collect_real_evidence_once_payload,
    build_collect_context_once_payload,
    build_collect_token_snapshots_once_payload,
    build_manual_intake_token_pair_payload,
    build_memory_window_once_payload,
)
from printer_v1.safety.goplus_normalizer import (
    normalize_goplus_safety_response,
    insert_goplus_safety_evidence_from_source_response,
)
from printer_v1.sources import (
    SOURCE_REGISTRY,
    build_governed_source_request,
    execute_source_request_with_governor,
    validate_source_adapter_contract,
)
from printer_v1.sources.goplus import (
    build_goplus_adapter,
    build_goplus_adapter_contract,
    fixture_failure_transport as goplus_failure_transport,
    fixture_success_transport as goplus_success_transport,
    normalize_goplus_payload,
)
from printer_v1.sources.solana_rpc_holder import (
    build_solana_rpc_holder_transport,
    build_solana_rpc_holder_adapter,
    build_solana_rpc_holder_adapter_contract,
    fixture_failure_transport as rpc_holder_failure_transport,
    fixture_success_transport as rpc_holder_success_transport,
    normalize_solana_rpc_holder_response,
    redacted_solana_rpc_source,
)
from printer_v1.sources.jupiter_quote import (
    DEFAULT_PAPER_AMOUNT_LAMPORTS,
    DEFAULT_SLIPPAGE_BPS,
    JUPITER_QUOTE_API_URL,
    JUPITER_QUOTE_LEGACY_V6_URL,
    WSOL_MINT,
    build_jupiter_paper_quote_transport,
    build_jupiter_quote_adapter,
    build_jupiter_quote_adapter_contract,
    fixture_failure_transport as jq_failure_transport,
    fixture_success_transport as jq_success_transport,
    normalize_jupiter_quote_response,
)


DOWNSTREAM_TABLES = (
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
)

FORBIDDEN_TERMS = (
    "wallet", "private_key", "signing", "sendTransaction",
    "live_execution", "buy_unlock", "pnl",
    "score", "rank", "confidence", "weighted",
)


def make_db():
    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db_path = pathlib.Path(tmp.name) / "real-evidence.sqlite3"
    apply_migrations(db_path)
    return tmp, db_path


def count_rows(db_path, table):
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        conn.close()


def _goplus_clean_payload(token_mint="fixture-mint"):
    return {
        "code": 1,
        "message": "OK",
        "result": {
            token_mint: {
                "mint_authority": None,
                "freeze_authority": None,
                "metadata_mutable": False,
                "is_open_minting": False,
                "top_10_holders": [
                    {"percent": "3.5", "address": "holder1"},
                    {"percent": "2.1", "address": "holder2"},
                ],
                "lp_info": [{"locked": True, "locked_percent": "100"}],
                "risky_flags": [],
            }
        },
        "captured_at": "2026-06-25T12:00:00+00:00",
    }


def _goplus_partial_payload(token_mint="fixture-mint"):
    """Missing holder data → HOLDER_CONCENTRATION_UNKNOWN → SAFETY_UNKNOWN."""
    return {
        "code": 1,
        "message": "OK",
        "result": {
            token_mint: {
                "mint_authority": None,
                "freeze_authority": None,
                "metadata_mutable": False,
                "is_open_minting": False,
                # No top_10_holders — will be UNKNOWN
                "lp_info": [],
                "risky_flags": [],
            }
        },
        "captured_at": "2026-06-25T12:00:00+00:00",
    }


def _goplus_real_solana_payload(token_mint="real-solana-mint"):
    """Payload matching the real GoPlus Solana API response shape (status objects)."""
    return {
        "code": 1,
        "message": "OK",
        "result": {
            token_mint: {
                "mintable": {"status": "0", "authority": []},
                "freezable": {"status": "0", "authority": []},
                "metadata_mutable": {"status": "0", "metadata_upgrade_authority": []},
                "total_supply": "1000000000",
                "trusted_token": 0,
                # No top_10_holders in real payload — triggers HOLDER_CONCENTRATION_UNKNOWN
            }
        },
        "captured_at": "2026-06-25T12:00:00+00:00",
    }


def _goplus_real_solana_unsafe_payload(token_mint="unsafe-solana-mint"):
    """Real GoPlus shape with active mint/freeze authority."""
    return {
        "code": 1,
        "message": "OK",
        "result": {
            token_mint: {
                "mintable": {"status": "1", "authority": ["SomeAuthority111111111111111111111111111111"]},
                "freezable": {"status": "1", "authority": ["SomeAuthority111111111111111111111111111111"]},
                "metadata_mutable": {"status": "1", "metadata_upgrade_authority": ["SomeUpgradeAuth"]},
                "total_supply": "999999999999",
            }
        },
        "captured_at": "2026-06-25T12:00:00+00:00",
    }


def _jupiter_clean_payload(route=True):
    return {
        "route_available": route,
        "route_plan_present": route,
        "slippage_bps": 50,
        "price_impact_bps": 30.0,
        "quote_captured_at": "2026-06-25T12:00:00+00:00",
        "freshness_label": "QUOTE_FRESH",
        "target_status": "TARGET_MATCH",
        "paper_only_context": True,
        "liquidity_context_label": "LIQUIDITY_CONTEXT_ACCEPTABLE",
    }


def _rpc_holder_healthy_payload(token_mint="fixture-mint"):
    """Pre-normalized RPC payload producing HOLDER_CONCENTRATION_HEALTHY."""
    return {
        "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
        "token_mint": token_mint,
        "captured_at": "2026-06-25T12:00:00+00:00",
    }


def _rpc_holder_raw_payload(token_mint="fixture-mint"):
    """Raw RPC-shape payload with getTokenLargestAccounts + getTokenSupply results."""
    total_supply = 1_000_000_000
    # 5% top holder
    top_amount = int(total_supply * 0.05)
    return {
        "token_mint": token_mint,
        "largest_accounts_result": {
            "result": {
                "value": [{"address": f"holder{i}", "amount": str(top_amount)} for i in range(10)]
            }
        },
        "token_supply_result": {
            "result": {
                "value": {"amount": str(total_supply), "decimals": 9}
            }
        },
        "captured_at": "2026-06-25T12:00:00+00:00",
    }


def _rpc_holder_extreme_payload(token_mint="fixture-mint"):
    """RPC payload that produces HOLDER_CONCENTRATION_EXTREME (top-10 = 90%)."""
    total_supply = 1_000_000_000
    top_amount = int(total_supply * 0.09)  # 9% each = 90% total
    return {
        "token_mint": token_mint,
        "largest_accounts_result": {
            "result": {
                "value": [{"address": f"holder{i}", "amount": str(top_amount)} for i in range(10)]
            }
        },
        "token_supply_result": {
            "result": {
                "value": {"amount": str(total_supply), "decimals": 9}
            }
        },
        "captured_at": "2026-06-25T12:00:00+00:00",
    }


class _FakeRpcResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, _limit):
        return json.dumps(self.payload).encode("utf-8")


def _fake_solana_rpc_urlopen_factory(seen_urls, token_mint="fixture-mint"):
    total_supply = 1_000_000_000
    top_amount = int(total_supply * 0.05)

    def fake_urlopen(request, timeout):
        del timeout
        seen_urls.append(request.full_url)
        body = json.loads(request.data.decode("utf-8"))
        method = body["method"]
        if method == "getTokenLargestAccounts":
            return _FakeRpcResponse({
                "result": {
                    "value": [{"address": f"holder{i}", "amount": str(top_amount)} for i in range(10)]
                }
            })
        if method == "getTokenSupply":
            return _FakeRpcResponse({
                "result": {
                    "value": {"amount": str(total_supply), "decimals": 9}
                }
            })
        raise AssertionError(f"unexpected RPC method {method}")

    return fake_urlopen


# ---------------------------------------------------------------------------
# Class 1: GoPlus source registry and contract
# ---------------------------------------------------------------------------

class GoPlusRegistryAndContractTests(unittest.TestCase):

    def test_goplus_is_in_source_registry(self):
        self.assertIn("goplus", SOURCE_REGISTRY)

    def test_goplus_is_free_public_no_paid_plan(self):
        defn = SOURCE_REGISTRY["goplus"]
        self.assertFalse(defn.requires_paid_plan)

    def test_goplus_contract_validates_source_governor_boundary(self):
        contract = build_goplus_adapter_contract()
        self.assertTrue(validate_source_adapter_contract(contract))
        self.assertTrue(contract.fixture_only)
        self.assertTrue(contract.requires_governor_context)
        self.assertFalse(contract.enabled_by_default)

    def test_goplus_adapter_is_disabled_by_default(self):
        adapter = build_goplus_adapter()
        self.assertFalse(adapter.enabled)
        with self.assertRaises(PermissionError):
            adapter.execute(None)

    def test_goplus_module_has_no_forbidden_terms(self):
        text = (SRC_PATH / "printer_v1" / "sources" / "goplus.py").read_text(encoding="utf-8")
        for term in FORBIDDEN_TERMS:
            self.assertNotIn(term, text, f"Forbidden term '{term}' in goplus.py")

    def test_goplus_module_has_no_requests_or_httpx(self):
        text = (SRC_PATH / "printer_v1" / "sources" / "goplus.py").read_text(encoding="utf-8")
        for fragment in ("requests.get", "requests.post", "httpx", "aiohttp"):
            self.assertNotIn(fragment, text)


# ---------------------------------------------------------------------------
# Class 2: Jupiter Quote source registry and contract
# ---------------------------------------------------------------------------

class JupiterQuoteRegistryAndContractTests(unittest.TestCase):

    def test_jupiter_quote_is_in_source_registry(self):
        self.assertIn("jupiter_quote", SOURCE_REGISTRY)

    def test_jupiter_quote_requires_paper_quote_realism_kind(self):
        defn = SOURCE_REGISTRY["jupiter_quote"]
        self.assertIn("paper_quote_realism", defn.allowed_request_kinds)

    def test_jupiter_quote_contract_validates(self):
        contract = build_jupiter_quote_adapter_contract()
        self.assertTrue(validate_source_adapter_contract(contract))
        self.assertTrue(contract.fixture_only)
        self.assertTrue(contract.requires_governor_context)

    def test_jupiter_quote_adapter_disabled_by_default(self):
        adapter = build_jupiter_quote_adapter()
        self.assertFalse(adapter.enabled)
        with self.assertRaises(PermissionError):
            adapter.execute(None)

    def test_jupiter_quote_module_has_no_forbidden_terms(self):
        text = (SRC_PATH / "printer_v1" / "sources" / "jupiter_quote.py").read_text(encoding="utf-8")
        for term in FORBIDDEN_TERMS:
            self.assertNotIn(term, text, f"Forbidden term '{term}' in jupiter_quote.py")

    def test_jupiter_quote_module_has_no_swap_transaction_instruction(self):
        text = (SRC_PATH / "printer_v1" / "sources" / "jupiter_quote.py").read_text(encoding="utf-8")
        # These terms indicate transaction building — not allowed
        for fragment in ("swapTransaction", "swapInstructions", "getInstructions",
                         "quoteResponse.swapTransaction", "buildTransaction"):
            self.assertNotIn(fragment, text)

    def test_jupiter_quote_module_metadata_is_read_only(self):
        from printer_v1.sources.jupiter_quote import JupiterQuoteAdapterMetadata
        meta = JupiterQuoteAdapterMetadata()
        self.assertTrue(meta.read_only)
        self.assertFalse(meta.supports_network_execution)

    def test_jupiter_quote_default_endpoint_is_lite_api(self):
        self.assertIn("lite-api.jup.ag", JUPITER_QUOTE_API_URL)
        self.assertIn("/swap/v1/quote", JUPITER_QUOTE_API_URL)

    def test_jupiter_quote_default_endpoint_is_not_legacy_v6(self):
        self.assertNotEqual(JUPITER_QUOTE_API_URL, JUPITER_QUOTE_LEGACY_V6_URL)
        self.assertNotIn("quote-api.jup.ag", JUPITER_QUOTE_API_URL)
        self.assertNotIn("/v6/quote", JUPITER_QUOTE_API_URL)

    def test_jupiter_quote_transport_url_uses_lite_api(self):
        import inspect
        # The factory builds endpoint = JUPITER_QUOTE_API_URL + params.
        # We verify the factory uses the constant (proven to be lite-api.jup.ag
        # in test_jupiter_quote_default_endpoint_is_lite_api).
        src = inspect.getsource(build_jupiter_paper_quote_transport)
        self.assertIn("JUPITER_QUOTE_API_URL", src)

    def test_jupiter_quote_transport_is_get_only(self):
        text = (SRC_PATH / "printer_v1" / "sources" / "jupiter_quote.py").read_text(encoding="utf-8")
        self.assertIn('method="GET"', text)
        for bad in ("method=\"POST\"", "method=\"PUT\"", "method=\"PATCH\""):
            self.assertNotIn(bad, text)


# ---------------------------------------------------------------------------
# Class 3: GoPlus payload normalization
# ---------------------------------------------------------------------------

class GoPlusNormalizationTests(unittest.TestCase):

    def test_clean_goplus_payload_normalizes_to_complete(self):
        result = normalize_goplus_payload(
            _goplus_clean_payload(), request_kind="safety_reference"
        )
        self.assertEqual(result.source_status.value, "COMPLETE")
        self.assertEqual(result.data_quality_label.value, "CLEAN_DATA")

    def test_invalid_request_kind_returns_failed(self):
        result = normalize_goplus_payload(
            _goplus_clean_payload(), request_kind="unsupported_kind"
        )
        self.assertEqual(result.source_status.value, "FAILED")

    def test_fixture_failure_returns_failed(self):
        result = normalize_goplus_payload(
            {"fixture_status": "failure", "failure_type": "test_fail"},
            request_kind="safety_reference",
        )
        self.assertEqual(result.source_status.value, "FAILED")
        self.assertEqual(result.failure_type, "test_fail")

    def test_clean_safety_response_produces_safety_clean(self):
        token_data = _goplus_clean_payload("mint-x")["result"]["mint-x"]
        evidence = normalize_goplus_safety_response(
            token_data,
            token_id=1,
            snapshot_id=1,
            source_request_id=1,
            source_response_id=1,
            captured_at="2026-06-25T12:00:00+00:00",
        )
        self.assertEqual(evidence["safety_context_label"], "SAFETY_CLEAN")
        self.assertEqual(evidence["mint_authority_status"], "MINT_AUTHORITY_RENOUNCED")
        self.assertEqual(evidence["freeze_authority_status"], "FREEZE_AUTHORITY_DISABLED")
        self.assertEqual(evidence["metadata_mutability_status"], "METADATA_IMMUTABLE")

    def test_partial_payload_without_holders_produces_safety_unknown(self):
        token_data = _goplus_partial_payload("mint-y")["result"]["mint-y"]
        evidence = normalize_goplus_safety_response(
            token_data,
            token_id=1,
            snapshot_id=1,
            source_request_id=1,
            source_response_id=1,
        )
        self.assertEqual(evidence["safety_context_label"], "SAFETY_UNKNOWN")
        self.assertEqual(evidence["holder_concentration_label"], "HOLDER_CONCENTRATION_UNKNOWN")

    def test_failed_source_status_forces_safety_unknown(self):
        token_data = _goplus_clean_payload("mint-z")["result"]["mint-z"]
        evidence = normalize_goplus_safety_response(
            token_data,
            token_id=1,
            snapshot_id=1,
            source_request_id=1,
            source_status="FAILED",
        )
        self.assertEqual(evidence["safety_context_label"], "SAFETY_UNKNOWN")


# ---------------------------------------------------------------------------
# Class 4: Jupiter Quote payload normalization
    def test_real_solana_mintable_status0_maps_to_renounced(self):
        token_data = _goplus_real_solana_payload("real-solana-mint")["result"]["real-solana-mint"]
        evidence = normalize_goplus_safety_response(
            token_data,
            token_id=1,
            snapshot_id=1,
            source_request_id=1,
            captured_at="2026-06-25T12:00:00+00:00",
        )
        self.assertEqual(evidence["mint_authority_status"], "MINT_AUTHORITY_RENOUNCED")

    def test_real_solana_freezable_status0_maps_to_disabled(self):
        token_data = _goplus_real_solana_payload("real-solana-mint")["result"]["real-solana-mint"]
        evidence = normalize_goplus_safety_response(
            token_data,
            token_id=1,
            snapshot_id=1,
            source_request_id=1,
            captured_at="2026-06-25T12:00:00+00:00",
        )
        self.assertEqual(evidence["freeze_authority_status"], "FREEZE_AUTHORITY_DISABLED")

    def test_real_solana_metadata_mutable_status0_maps_to_immutable(self):
        token_data = _goplus_real_solana_payload("real-solana-mint")["result"]["real-solana-mint"]
        evidence = normalize_goplus_safety_response(
            token_data,
            token_id=1,
            snapshot_id=1,
            source_request_id=1,
            captured_at="2026-06-25T12:00:00+00:00",
        )
        self.assertEqual(evidence["metadata_mutability_status"], "METADATA_IMMUTABLE")

    def test_real_solana_total_supply_maps_to_supply_sanity_ok(self):
        token_data = _goplus_real_solana_payload("real-solana-mint")["result"]["real-solana-mint"]
        evidence = normalize_goplus_safety_response(
            token_data,
            token_id=1,
            snapshot_id=1,
            source_request_id=1,
            captured_at="2026-06-25T12:00:00+00:00",
        )
        self.assertEqual(evidence["supply_sanity_label"], "SUPPLY_SANITY_OK")

    def test_real_solana_no_holders_stays_unknown(self):
        token_data = _goplus_real_solana_payload("real-solana-mint")["result"]["real-solana-mint"]
        evidence = normalize_goplus_safety_response(
            token_data,
            token_id=1,
            snapshot_id=1,
            source_request_id=1,
            captured_at="2026-06-25T12:00:00+00:00",
        )
        self.assertEqual(evidence["holder_concentration_label"], "HOLDER_CONCENTRATION_UNKNOWN")

    def test_real_solana_no_liquidity_stays_unknown(self):
        token_data = _goplus_real_solana_payload("real-solana-mint")["result"]["real-solana-mint"]
        evidence = normalize_goplus_safety_response(
            token_data,
            token_id=1,
            snapshot_id=1,
            source_request_id=1,
            captured_at="2026-06-25T12:00:00+00:00",
        )
        self.assertEqual(evidence["liquidity_lock_or_burn_label"], "LIQUIDITY_LOCK_OR_BURN_UNKNOWN")

    def test_real_solana_partial_fields_produce_safety_unknown(self):
        """Real payload without holders/liquidity must remain SAFETY_UNKNOWN."""
        token_data = _goplus_real_solana_payload("real-solana-mint")["result"]["real-solana-mint"]
        evidence = normalize_goplus_safety_response(
            token_data,
            token_id=1,
            snapshot_id=1,
            source_request_id=1,
            captured_at="2026-06-25T12:00:00+00:00",
        )
        self.assertEqual(evidence["safety_context_label"], "SAFETY_UNKNOWN")

    def test_real_solana_unsafe_mintable_maps_to_present(self):
        token_data = _goplus_real_solana_unsafe_payload("unsafe-solana-mint")["result"]["unsafe-solana-mint"]
        evidence = normalize_goplus_safety_response(
            token_data,
            token_id=1,
            snapshot_id=1,
            source_request_id=1,
            captured_at="2026-06-25T12:00:00+00:00",
        )
        self.assertEqual(evidence["mint_authority_status"], "MINT_AUTHORITY_PRESENT")
        self.assertEqual(evidence["freeze_authority_status"], "FREEZE_AUTHORITY_PRESENT")
        self.assertEqual(evidence["metadata_mutability_status"], "METADATA_MUTABLE")


# ---------------------------------------------------------------------------

class JupiterQuoteNormalizationTests(unittest.TestCase):

    def test_route_available_payload_normalizes_to_complete(self):
        result = normalize_jupiter_quote_response(
            _jupiter_clean_payload(route=True), request_kind="paper_quote_realism"
        )
        self.assertEqual(result.source_status.value, "COMPLETE")
        pairs = result.normalized_payload
        self.assertTrue(pairs.get("route_available"))
        self.assertTrue(pairs.get("paper_only_context"))

    def test_no_route_fixture_status_normalizes_route_unavailable(self):
        result = normalize_jupiter_quote_response(
            {"fixture_status": "no_route"}, request_kind="paper_quote_realism"
        )
        self.assertEqual(result.source_status.value, "COMPLETE")
        self.assertFalse(result.normalized_payload.get("route_available"))
        self.assertFalse(result.normalized_payload.get("route_plan_present"))

    def test_failure_returns_failed(self):
        result = normalize_jupiter_quote_response(
            {"fixture_status": "failure", "failure_type": "jq_fail"},
            request_kind="paper_quote_realism",
        )
        self.assertEqual(result.source_status.value, "FAILED")

    def test_invalid_request_kind_rejected(self):
        result = normalize_jupiter_quote_response(
            _jupiter_clean_payload(), request_kind="unsupported"
        )
        self.assertEqual(result.source_status.value, "FAILED")

    def test_stale_fixture_is_stale_not_clean(self):
        payload = {**_jupiter_clean_payload(), "fixture_stale": True}
        result = normalize_jupiter_quote_response(payload, request_kind="paper_quote_realism")
        self.assertEqual(result.source_status.value, "STALE")
        self.assertEqual(result.data_quality_label.value, "STALE_DATA")


# ---------------------------------------------------------------------------
# Class 5: Governed execution through Source Governor
# ---------------------------------------------------------------------------

class RealEvidenceGovernedExecutionTests(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = make_db()

    def tearDown(self):
        self._tmp.cleanup()

    def test_goplus_governed_execution_records_source_rows(self):
        adapter = build_goplus_adapter(
            enabled=True,
            fixture_transport=goplus_success_transport(_goplus_clean_payload()),
        )
        req = build_governed_source_request(
            "goplus", "safety_reference", request_key="test-goplus-safety"
        )
        result = execute_source_request_with_governor(self.db_path, req, adapter)
        self.assertIsNotNone(result.request_record)
        self.assertIsNotNone(result.response_record)
        self.assertIsNone(result.failure_record)
        self.assertEqual(result.normalized_result.source_status.value, "COMPLETE")

    def test_goplus_governed_failure_records_failure_row(self):
        adapter = build_goplus_adapter(
            enabled=True, fixture_transport=goplus_failure_transport()
        )
        req = build_governed_source_request(
            "goplus", "safety_reference", request_key="test-goplus-fail"
        )
        result = execute_source_request_with_governor(self.db_path, req, adapter)
        self.assertIsNone(result.response_record)
        self.assertIsNotNone(result.failure_record)

    def test_jupiter_quote_governed_execution_records_source_rows(self):
        adapter = build_jupiter_quote_adapter(
            enabled=True,
            fixture_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
        )
        req = build_governed_source_request(
            "jupiter_quote", "paper_quote_realism", request_key="test-jq-entry"
        )
        result = execute_source_request_with_governor(self.db_path, req, adapter)
        self.assertIsNotNone(result.request_record)
        self.assertIsNotNone(result.response_record)
        self.assertEqual(result.normalized_result.source_status.value, "COMPLETE")

    def test_governed_execution_does_not_touch_downstream_tables(self):
        adapter = build_goplus_adapter(
            enabled=True,
            fixture_transport=goplus_success_transport(_goplus_clean_payload()),
        )
        req = build_governed_source_request(
            "goplus", "safety_reference", request_key="test-goplus-downstream"
        )
        execute_source_request_with_governor(self.db_path, req, adapter)
        for table in DOWNSTREAM_TABLES:
            self.assertEqual(count_rows(self.db_path, table), 0, table)


# ---------------------------------------------------------------------------
# Class 6: Real evidence fill orchestrator
# ---------------------------------------------------------------------------

class RealEvidenceFillOrchestratorTests(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = make_db()
        self._seed_token_pair_snapshot()
        self.target = RealEvidenceTarget(
            token_id=1, snapshot_id=1, token_mint="fixture-mint", pair_id=1
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _seed_token_pair_snapshot(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute(
                "INSERT INTO printer_tokens (id, token_mint, chain, symbol, name, token_status) "
                "VALUES (1, 'fixture-mint', 'solana', 'FIX', 'Fixture', 'TRACK_NORMAL')"
            )
            conn.execute(
                "INSERT INTO printer_pairs (id, token_id, pair_address, dex, pool_source) "
                "VALUES (1, 1, 'fixture-pair', 'raydium', 'fixture')"
            )
            conn.execute(
                "INSERT INTO printer_token_snapshots "
                "(id, token_id, pair_id, captured_at, tracking_lane, snapshot_mode, "
                "price_usd, liquidity_usd, source_status, data_quality_label) "
                "VALUES (1, 1, 1, '2026-06-25T12:00:00+00:00', 'TRACK_NORMAL', 'NORMAL_MODE', "
                "0.001, 50000, 'COMPLETE', 'CLEAN_DATA')"
            )
            conn.commit()
        finally:
            conn.close()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def test_clean_safety_and_quotes_produce_three_inserted_rows(self):
        with self.connect() as conn:
            result = collect_real_evidence(
                conn,
                self.target,
                safety_transport=goplus_success_transport(_goplus_clean_payload()),
                entry_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
                exit_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
            )
        self.assertEqual(result.safety_evidence_inserted, 1)
        self.assertEqual(result.quote_evidence_inserted, 2)
        self.assertEqual(result.rejected_or_failed, 0)

    def test_clean_safety_produces_clean_eligible_evidence(self):
        with self.connect() as conn:
            result = collect_real_evidence(
                conn,
                self.target,
                safety_transport=goplus_success_transport(_goplus_clean_payload()),
                entry_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
                exit_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
            )
        self.assertGreater(result.clean_evidence_inserted, 0)

    def test_partial_safety_produces_audit_only_evidence(self):
        with self.connect() as conn:
            result = collect_real_evidence(
                conn,
                self.target,
                safety_transport=goplus_success_transport(
                    _goplus_partial_payload()  # missing holder data → SAFETY_UNKNOWN
                ),
                entry_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
                exit_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
            )
        # Safety is inserted but not clean_eligible (SAFETY_UNKNOWN → audit only)
        safety_items = [r for r in result.item_results if r.evidence_type == "goplus_safety"]
        self.assertEqual(len(safety_items), 1)
        self.assertTrue(safety_items[0].inserted)
        self.assertFalse(safety_items[0].clean_eligible)

    def test_no_route_quote_produces_inserted_but_not_clean(self):
        with self.connect() as conn:
            result = collect_real_evidence(
                conn,
                self.target,
                safety_transport=goplus_success_transport(_goplus_clean_payload()),
                entry_quote_transport=jq_success_transport(
                    {"fixture_status": "no_route"}
                ),
                exit_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
            )
        entry_items = [r for r in result.item_results if "entry" in r.evidence_type]
        self.assertTrue(entry_items[0].inserted)
        self.assertFalse(entry_items[0].clean_eligible)

    def test_failed_safety_is_not_inserted(self):
        with self.connect() as conn:
            result = collect_real_evidence(
                conn,
                self.target,
                safety_transport=goplus_failure_transport(),
                entry_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
                exit_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
            )
        self.assertEqual(result.safety_evidence_inserted, 0)
        self.assertGreater(result.rejected_or_failed, 0)

    def test_no_downstream_unlocks_from_evidence_fill(self):
        with self.connect() as conn:
            collect_real_evidence(
                conn,
                self.target,
                safety_transport=goplus_success_transport(_goplus_clean_payload()),
                entry_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
                exit_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
            )
        for table in DOWNSTREAM_TABLES:
            self.assertEqual(count_rows(self.db_path, table), 0, table)

    def test_all_downstream_unlock_flags_are_false(self):
        with self.connect() as conn:
            result = collect_real_evidence(
                conn,
                self.target,
                safety_transport=goplus_success_transport(_goplus_clean_payload()),
                entry_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
                exit_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
            )
        for item in result.item_results:
            for key, val in item.downstream_unlocks.items():
                self.assertFalse(val, f"downstream unlock {key} must remain False")


# ---------------------------------------------------------------------------
# Class 6b: Solana RPC holder concentration fallback
# ---------------------------------------------------------------------------

class SolanaRpcHolderFallbackTests(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = make_db()
        self._seed_token_pair_snapshot()
        self.target = RealEvidenceTarget(
            token_id=1, snapshot_id=1, token_mint="fixture-mint", pair_id=1
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _seed_token_pair_snapshot(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute(
                "INSERT INTO printer_tokens (id, token_mint, chain, symbol, name, token_status) "
                "VALUES (1, 'fixture-mint', 'solana', 'FIX', 'Fixture', 'TRACK_NORMAL')"
            )
            conn.execute(
                "INSERT INTO printer_pairs (id, token_id, pair_address, dex, pool_source) "
                "VALUES (1, 1, 'fixture-pair', 'raydium', 'fixture')"
            )
            conn.execute(
                "INSERT INTO printer_token_snapshots "
                "(id, token_id, pair_id, captured_at, tracking_lane, snapshot_mode, "
                "price_usd, liquidity_usd, source_status, data_quality_label) "
                "VALUES (1, 1, 1, '2026-06-25T12:00:00+00:00', 'TRACK_NORMAL', 'NORMAL_MODE', "
                "0.001, 50000, 'COMPLETE', 'CLEAN_DATA')"
            )
            conn.commit()
        finally:
            conn.close()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def test_rpc_holder_adapter_is_disabled_by_default(self):
        adapter = build_solana_rpc_holder_adapter()
        self.assertFalse(adapter.enabled)
        with self.assertRaises(PermissionError):
            adapter.execute(None)

    def test_rpc_holder_contract_validates(self):
        contract = build_solana_rpc_holder_adapter_contract()
        from printer_v1.sources import validate_source_adapter_contract
        self.assertTrue(validate_source_adapter_contract(contract))
        self.assertTrue(contract.fixture_only)
        self.assertTrue(contract.requires_governor_context)
        self.assertFalse(contract.enabled_by_default)

    def test_healthy_raw_rpc_payload_produces_holder_healthy(self):
        result = normalize_solana_rpc_holder_response(
            _rpc_holder_raw_payload(), request_kind="holder_concentration_reference"
        )
        self.assertEqual(result.source_status.value, "COMPLETE")
        self.assertEqual(
            result.normalized_payload["holder_concentration_label"],
            "HOLDER_CONCENTRATION_HEALTHY",
        )

    def test_extreme_raw_rpc_payload_produces_holder_extreme(self):
        result = normalize_solana_rpc_holder_response(
            _rpc_holder_extreme_payload(), request_kind="holder_concentration_reference"
        )
        self.assertEqual(result.source_status.value, "COMPLETE")
        self.assertEqual(
            result.normalized_payload["holder_concentration_label"],
            "HOLDER_CONCENTRATION_EXTREME",
        )

    def test_failure_rpc_returns_failed(self):
        result = normalize_solana_rpc_holder_response(
            {"fixture_status": "failure", "failure_type": "rpc_fail"},
            request_kind="holder_concentration_reference",
        )
        self.assertEqual(result.source_status.value, "FAILED")

    def test_missing_rpc_data_stays_unknown(self):
        result = normalize_solana_rpc_holder_response(
            {"token_mint": "fixture-mint"},  # no RPC result data
            request_kind="holder_concentration_reference",
        )
        self.assertEqual(result.source_status.value, "FAILED")

    def test_http_429_maps_to_solana_rpc_rate_limited(self):
        import printer_v1.sources.solana_rpc_holder as holder_module

        original = holder_module.url_request.urlopen

        def fake_urlopen(request, timeout):
            del request, timeout
            raise url_error.HTTPError(
                "https://api.mainnet-beta.solana.com",
                429,
                "Too Many Requests",
                hdrs=None,
                fp=io.BytesIO(b""),
            )

        holder_module.url_request.urlopen = fake_urlopen
        try:
            transport = build_solana_rpc_holder_transport(
                "fixture-mint",
                rpc_url="https://api.mainnet-beta.solana.com",
                timeout_seconds=0.1,
            )
            payload = transport(None)
        finally:
            holder_module.url_request.urlopen = original

        result = normalize_solana_rpc_holder_response(
            payload, request_kind="holder_concentration_reference"
        )
        self.assertEqual(result.source_status.value, "FAILED")
        self.assertEqual(result.data_quality_label.value, "MISSING_CRITICAL_DATA")
        self.assertEqual(result.failure_type, "solana_rpc_rate_limited")

    def test_rate_limited_holder_fallback_keeps_holder_unknown_and_no_clean_insert(self):
        def rate_limited_transport(context):
            del context
            return {
                "fixture_status": "failure",
                "failure_type": "solana_rpc_rate_limited",
                "failure_message": "Solana RPC HTTP 429 rate limit",
            }

        with self.connect() as conn:
            result = collect_real_evidence(
                conn,
                self.target,
                safety_transport=goplus_success_transport(_goplus_real_solana_payload()),
                holder_rpc_transport=rate_limited_transport,
                entry_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
                exit_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
            )

        rpc_items = [r for r in result.item_results if r.evidence_type == "solana_rpc_holder"]
        self.assertEqual(len(rpc_items), 1)
        self.assertFalse(rpc_items[0].inserted)
        self.assertFalse(rpc_items[0].clean_eligible)
        self.assertEqual(rpc_items[0].holder_rpc_failure_type, "solana_rpc_rate_limited")
        self.assertTrue(rpc_items[0].holder_rpc_rate_limited)
        with self.connect() as conn:
            safety_rows = conn.execute(
                "SELECT holder_concentration_label, safety_context_label FROM printer_solana_safety_evidence"
            ).fetchall()
        self.assertEqual(len(safety_rows), 1)
        self.assertEqual(safety_rows[0]["holder_concentration_label"], "HOLDER_CONCENTRATION_UNKNOWN")
        self.assertEqual(safety_rows[0]["safety_context_label"], "SAFETY_UNKNOWN")

    def test_configurable_rpc_url_is_used_by_holder_fallback(self):
        import printer_v1.sources.solana_rpc_holder as holder_module

        seen_urls = []
        original = holder_module.url_request.urlopen
        configured_url = "https://free-rpc.example.test/solana"
        holder_module.url_request.urlopen = _fake_solana_rpc_urlopen_factory(seen_urls)
        try:
            with self.connect() as conn:
                result = collect_real_evidence(
                    conn,
                    self.target,
                    safety_transport=goplus_success_transport(_goplus_real_solana_payload()),
                    holder_rpc_url=configured_url,
                    entry_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
                    exit_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
                )
        finally:
            holder_module.url_request.urlopen = original

        self.assertEqual(seen_urls, [configured_url, configured_url])
        rpc_items = [r for r in result.item_results if r.evidence_type == "solana_rpc_holder"]
        self.assertEqual(len(rpc_items), 1)
        self.assertEqual(rpc_items[0].holder_rpc_source_used, "free-rpc.example.test")

    def test_redacted_rpc_source_removes_query_string(self):
        redacted = redacted_solana_rpc_source("https://rpc.example.test/?api-key=secret-token")
        self.assertEqual(redacted, "rpc.example.test")
        self.assertNotIn("secret-token", redacted)
        self.assertNotIn("api-key", redacted)

    def test_successful_rpc_fallback_fills_holder_concentration(self):
        """When GoPlus omits holders, RPC fallback inserts merged safety evidence row."""
        with self.connect() as conn:
            result = collect_real_evidence(
                conn,
                self.target,
                safety_transport=goplus_success_transport(_goplus_real_solana_payload()),
                holder_rpc_transport=rpc_holder_success_transport(
                    _rpc_holder_healthy_payload("fixture-mint")
                ),
                entry_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
                exit_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
            )
        rpc_items = [r for r in result.item_results if r.evidence_type == "solana_rpc_holder"]
        self.assertEqual(len(rpc_items), 1)
        self.assertTrue(rpc_items[0].inserted)
        # Safety still UNKNOWN (liquidity/risk still unknown) but holder is now resolved
        self.assertFalse(rpc_items[0].clean_eligible)  # not clean yet — other fields still UNKNOWN

    def test_missing_rpc_data_holder_stays_unknown(self):
        with self.connect() as conn:
            result = collect_real_evidence(
                conn,
                self.target,
                safety_transport=goplus_success_transport(_goplus_real_solana_payload()),
                holder_rpc_transport=rpc_holder_failure_transport(),
                entry_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
                exit_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
            )
        rpc_items = [r for r in result.item_results if r.evidence_type == "solana_rpc_holder"]
        self.assertEqual(len(rpc_items), 1)
        self.assertFalse(rpc_items[0].inserted)

    def test_target_mint_mismatch_is_rejected(self):
        with self.connect() as conn:
            result = collect_real_evidence(
                conn,
                self.target,
                safety_transport=goplus_success_transport(_goplus_real_solana_payload()),
                holder_rpc_transport=rpc_holder_success_transport(
                    _rpc_holder_healthy_payload("WRONG-MINT")  # mismatch
                ),
                entry_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
                exit_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
            )
        rpc_items = [r for r in result.item_results if r.evidence_type == "solana_rpc_holder"]
        self.assertEqual(len(rpc_items), 1)
        self.assertFalse(rpc_items[0].inserted)
        self.assertIn("RPC_HOLDER_TARGET_MINT_MISMATCH", rpc_items[0].rejection_reasons)

    def test_stale_rpc_does_not_clean_safety(self):
        stale_payload = {**_rpc_holder_healthy_payload("fixture-mint"), "fixture_stale": True}
        with self.connect() as conn:
            result = collect_real_evidence(
                conn,
                self.target,
                safety_transport=goplus_success_transport(_goplus_real_solana_payload()),
                holder_rpc_transport=rpc_holder_success_transport(stale_payload),
                entry_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
                exit_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
            )
        # Stale RPC should not result in a clean-eligible insert
        rpc_items = [r for r in result.item_results if r.evidence_type == "solana_rpc_holder"]
        for item in rpc_items:
            self.assertFalse(item.clean_eligible)

    def test_rpc_fallback_not_triggered_when_goplus_has_holders(self):
        """When GoPlus provides holder data, the RPC fallback should not run."""
        with self.connect() as conn:
            result = collect_real_evidence(
                conn,
                self.target,
                safety_transport=goplus_success_transport(_goplus_clean_payload()),
                holder_rpc_transport=rpc_holder_success_transport(
                    _rpc_holder_healthy_payload("fixture-mint")
                ),
                entry_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
                exit_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
            )
        rpc_items = [r for r in result.item_results if r.evidence_type == "solana_rpc_holder"]
        # Should be empty — GoPlus already had holders
        self.assertEqual(len(rpc_items), 0)

    def test_no_downstream_unlocks_from_rpc_fallback(self):
        with self.connect() as conn:
            result = collect_real_evidence(
                conn,
                self.target,
                safety_transport=goplus_success_transport(_goplus_real_solana_payload()),
                holder_rpc_transport=rpc_holder_success_transport(
                    _rpc_holder_healthy_payload("fixture-mint")
                ),
                entry_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
                exit_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
            )
        for item in result.item_results:
            for key, val in item.downstream_unlocks.items():
                self.assertFalse(val, f"downstream unlock {key} must remain False")

        for table in DOWNSTREAM_TABLES:
            self.assertEqual(count_rows(self.db_path, table), 0, table)

    def test_rpc_holder_module_has_no_forbidden_terms(self):
        text = (SRC_PATH / "printer_v1" / "sources" / "solana_rpc_holder.py").read_text(encoding="utf-8")
        for term in FORBIDDEN_TERMS:
            self.assertNotIn(term, text, f"Forbidden term '{term}' in solana_rpc_holder.py")

    def test_rpc_holder_module_is_read_only(self):
        meta = build_solana_rpc_holder_adapter().metadata
        self.assertTrue(meta.read_only)
        self.assertFalse(meta.supports_network_execution)


# ---------------------------------------------------------------------------
# Class 7: CLI command integration
# ---------------------------------------------------------------------------

class CollectRealEvidenceOnceCommandTests(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = make_db()
        self._seed_token_pair_snapshot()

    def tearDown(self):
        self._tmp.cleanup()

    def _seed_token_pair_snapshot(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                "INSERT INTO printer_tokens (id, token_mint, chain, symbol, name, token_status) "
                "VALUES (1, 'cli-fixture-mint', 'solana', 'CFM', 'CLI Fixture', 'TRACK_NORMAL')"
            )
            conn.execute(
                "INSERT INTO printer_pairs (id, token_id, pair_address, dex, pool_source) "
                "VALUES (1, 1, 'cli-fixture-pair', 'raydium', 'fixture')"
            )
            conn.execute(
                "INSERT INTO printer_token_snapshots "
                "(id, token_id, pair_id, captured_at, tracking_lane, snapshot_mode, "
                "price_usd, liquidity_usd, source_status, data_quality_label) "
                "VALUES (1, 1, 1, '2026-06-25T12:00:00+00:00', 'TRACK_NORMAL', 'NORMAL_MODE', "
                "0.001, 50000, 'COMPLETE', 'CLEAN_DATA')"
            )
            conn.commit()
        finally:
            conn.close()

    def _args(self, **kw):
        values = {
            "db_path": str(self.db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "token_id": 1,
            "token_mint": None,
            "pair_id": 1,
            "pair_address": None,
            "snapshot_id": 1,
            "memory_window_id": None,
            "evidence_window_id": None,
            "paper_amount_lamports": DEFAULT_PAPER_AMOUNT_LAMPORTS,
            "slippage_bps": DEFAULT_SLIPPAGE_BPS,
            "quote_currency_mint": WSOL_MINT,
        }
        values.update(kw)
        return argparse.Namespace(**values)

    def test_pyproject_exposes_collect_real_evidence_once(self):
        import tomllib
        scripts = tomllib.loads(
            (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]["scripts"]
        self.assertEqual(
            scripts["printer-collect-real-evidence-once"],
            "printer_v1.operator_cli.commands:main_collect_real_evidence_once",
        )

    def test_requires_operator_approval(self):
        from printer_v1.operator_cli.commands import build_collect_real_evidence_once_payload
        with self.assertRaises((ValueError, Exception)):
            build_collect_real_evidence_once_payload(self._args(operator_approved=False))

    def test_command_returns_evidence_metadata(self):
        from printer_v1.evidence_fill.real import collect_real_evidence as _orig

        # Monkey-patch collect_real_evidence to use fixture transports
        import printer_v1.operator_cli.commands as cmd_module
        import printer_v1.evidence_fill.real as real_module

        original_collect = real_module.collect_real_evidence

        def patched_collect(connection, target, **kwargs):
            kwargs["safety_transport"] = goplus_success_transport(_goplus_clean_payload())
            kwargs["entry_quote_transport"] = jq_success_transport(_jupiter_clean_payload(route=True))
            kwargs["exit_quote_transport"] = jq_success_transport(_jupiter_clean_payload(route=True))
            return original_collect(connection, target, **kwargs)

        real_module.collect_real_evidence = patched_collect
        try:
            payload = cmd_module.build_collect_real_evidence_once_payload(self._args())
        finally:
            real_module.collect_real_evidence = original_collect

        self.assertEqual(payload["command"], "printer-collect-real-evidence-once")
        self.assertIn("safety_evidence_inserted", payload)
        self.assertIn("quote_evidence_inserted", payload)
        self.assertIn("clean_evidence_inserted", payload)
        self.assertIn("item_results", payload)
        self.assertFalse(payload["guard_tables_unchanged"] is False and any(payload["guard_table_deltas"].values()))
        self.assertIn("next_step_hint", payload)

    def test_all_downstream_unlock_flags_false_in_result(self):
        from printer_v1.evidence_fill.real import collect_real_evidence as _orig
        import printer_v1.operator_cli.commands as cmd_module
        import printer_v1.evidence_fill.real as real_module

        original_collect = real_module.collect_real_evidence

        def patched_collect(connection, target, **kwargs):
            kwargs["safety_transport"] = goplus_success_transport(_goplus_clean_payload())
            kwargs["entry_quote_transport"] = jq_success_transport(_jupiter_clean_payload(route=True))
            kwargs["exit_quote_transport"] = jq_success_transport(_jupiter_clean_payload(route=True))
            return original_collect(connection, target, **kwargs)

        real_module.collect_real_evidence = patched_collect
        try:
            payload = cmd_module.build_collect_real_evidence_once_payload(self._args())
        finally:
            real_module.collect_real_evidence = original_collect

        for item in payload["item_results"]:
            for key, val in item["downstream_unlocks"].items():
                self.assertFalse(val, f"downstream unlock {key} must be False in CLI result")

    def test_retrieval_and_paper_rows_unchanged_after_command(self):
        from printer_v1.evidence_fill.real import collect_real_evidence as _orig
        import printer_v1.operator_cli.commands as cmd_module
        import printer_v1.evidence_fill.real as real_module

        original_collect = real_module.collect_real_evidence

        def patched_collect(connection, target, **kwargs):
            kwargs["safety_transport"] = goplus_success_transport(_goplus_clean_payload())
            kwargs["entry_quote_transport"] = jq_success_transport(_jupiter_clean_payload(route=True))
            kwargs["exit_quote_transport"] = jq_success_transport(_jupiter_clean_payload(route=True))
            return original_collect(connection, target, **kwargs)

        real_module.collect_real_evidence = patched_collect
        try:
            cmd_module.build_collect_real_evidence_once_payload(self._args())
        finally:
            real_module.collect_real_evidence = original_collect

        for table in DOWNSTREAM_TABLES:
            self.assertEqual(count_rows(self.db_path, table), 0, table)


# ---------------------------------------------------------------------------
# Class 8: Memory overlay — AUDIT_ONLY → CLEAN_MEMORY after valid evidence
# ---------------------------------------------------------------------------

class MemoryOverlayAfterRealEvidenceTests(unittest.TestCase):
    """Tests that a real evidence revision promotes AUDIT_ONLY to CLEAN_MEMORY."""

    def setUp(self):
        self._tmp, self.db_path = make_db()
        self.base_time = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self._tmp.cleanup()

    def _args(self, **kw):
        values = {
            "db_path": str(self.db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "token_mint": "overlay-mint",
            "token_id": None,
            "pair_address": "overlay-pair",
            "pair_id": None,
            "snapshot_id": None,
            "chain": "solana",
            "memory_window_id": None,
            "episode_id": None,
            "source_name": "dexscreener",
            "source_reference": "overlay-test",
        }
        values.update(kw)
        return argparse.Namespace(**values)

    def _snapshot_transport(self, ctx):
        del ctx
        return {
            "pairs": [{
                "chainId": "solana",
                "pairAddress": "overlay-pair",
                "baseToken": {"address": "overlay-mint", "symbol": "OVL", "name": "Overlay"},
                "priceUsd": "0.00050",
                "liquidity": {"usd": 32000.0},
                "volume": {"m5": 14000.0, "h1": 80000.0, "h24": 310000.0},
                "txns": {"m5": {"buys": 40, "sells": 16}, "h1": {"buys": 180, "sells": 70}},
                "fdv": 500000.0, "marketCap": 455000.0,
                "priceChange": {"m5": 12.0, "h1": 22.0, "h24": 33.0},
            }]
        }

    def _force_all_context_known(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            for sql in [
                "UPDATE printer_market_regime_snapshots SET market_regime_label='RISK_ON', market_transition_label='RISK_OFF_TO_RISK_ON', market_payload_quality_label='MARKET_CONTEXT_CLEAN', data_quality_label='CLEAN_DATA', source_status='COMPLETE'",
                "UPDATE printer_solana_chain_heat_snapshots SET chain_heat_label='SOLANA_WARM', activity_label='ACTIVITY_ELEVATED', liquidity_label='LIQUIDITY_STABLE', congestion_label='CONGESTION_LOW', chain_heat_payload_quality_label='CHAIN_HEAT_CONTEXT_CLEAN', data_quality_label='CLEAN_DATA', source_status='COMPLETE'",
                "UPDATE printer_safety_rug_snapshots SET safety_status_label='SAFETY_CLEAN', rug_risk_label='RUG_RISK_LOW', liquidity_safety_label='LIQUIDITY_SAFE', authority_label='AUTHORITY_RENOUNCED_OR_SAFE', distribution_label='DISTRIBUTION_HEALTHY', safety_payload_quality_label='SAFETY_CONTEXT_CLEAN', safety_gate_label='ALLOW_SAFETY_CONTEXT', data_quality_label='CLEAN_DATA', source_status='COMPLETE'",
                "UPDATE printer_liquidity_exit_snapshots SET entry_realism_label='ENTRY_REALISTIC', exit_realism_label='EXIT_REALISTIC', slippage_label='SLIPPAGE_LOW', price_impact_label='PRICE_IMPACT_LOW', route_label='ROUTE_AVAILABLE', quote_age_label='QUOTE_FRESH', liquidity_drain_label='NO_LIQUIDITY_DRAIN', liquidity_exit_payload_quality_label='LIQUIDITY_EXIT_CONTEXT_CLEAN', realism_gate_label='REALISM_CONTEXT_ACCEPTABLE', data_quality_label='CLEAN_DATA', source_status='COMPLETE'",
                "UPDATE printer_trading_flow_snapshots SET flow_direction_label='FLOW_ACCUMULATION', flow_pressure_label='PRESSURE_MODERATE_INFLOW', imbalance_label='IMBALANCE_BUY_HEAVY', volume_activity_label='VOLUME_NORMAL', tx_activity_label='TX_ACTIVITY_NORMAL', wallet_participation_label='WALLETS_BROAD_PARTICIPATION', trading_flow_payload_quality_label='TRADING_FLOW_CONTEXT_CLEAN', flow_memory_gate_label='FLOW_CONTEXT_ACCEPTABLE', data_quality_label='CLEAN_DATA', source_status='COMPLETE'",
                "UPDATE printer_chart_volatility_snapshots SET trend_structure_label='TREND_UP', volatility_label='VOLATILITY_NORMAL', range_behavior_label='RANGE_EXPANDING', momentum_label='MOMENTUM_STABLE', drawdown_recovery_label='DRAWDOWN_NONE', candle_path_label='PATH_STEADY_CLIMB', chart_payload_quality_label='CHART_CONTEXT_CLEAN', chart_memory_gate_label='CHART_CONTEXT_ACCEPTABLE', data_quality_label='CLEAN_DATA', source_status='COMPLETE'",
                "UPDATE printer_micro_events SET micro_event_state_label='NO_MICRO_EVENT', micro_event_move_label='MOVE_NO_CLEAR_EVENT', micro_exit_realism_label='MICRO_EXIT_REALISTIC', late_buy_trap_label='NO_LATE_BUY_TRAP', held_to_15m_result_label='HELD_TO_15M_CONSOLIDATED', micro_event_payload_quality_label='MICRO_EVENT_CONTEXT_CLEAN', micro_event_memory_gate_label='MICRO_EVENT_SUPPORT_EVIDENCE', data_quality_label='CLEAN_DATA', source_status='COMPLETE'",
            ]:
                conn.execute(sql)
            conn.commit()
        finally:
            conn.close()

    def test_memory_stays_audit_only_without_evidence(self):
        build_manual_intake_token_pair_payload(self._args(
            pool_address=None, intake_reason="overlay-test", source_request_id=None,
            token_symbol="OVL", token_name="Overlay", dex_id="raydium", intake_json=None,
        ))
        snapshot_ids = []
        for i in range(6):
            build_collect_token_snapshots_once_payload(
                self._args(snapshot_count=1, max_seconds=5.0, source_reference=f"ovl-snap-{i}"),
                transport=self._snapshot_transport,
            )
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute("SELECT id FROM printer_token_snapshots ORDER BY id DESC LIMIT 1").fetchone()
                snap_id = int(row["id"])
                captured = (self.base_time + timedelta(minutes=i * 3)).isoformat()
                conn.execute("UPDATE printer_token_snapshots SET captured_at=? WHERE id=?", (captured, snap_id))
                conn.commit()
            finally:
                conn.close()
            snapshot_ids.append(snap_id)

        build_collect_context_once_payload(self._args(snapshot_id=snapshot_ids[-1], source_name="dexscreener"))
        self._force_all_context_known()

        memory = build_memory_window_once_payload(self._args(
            snapshot_id=snapshot_ids[-1], memory_window="15m", source_reference="overlay-no-evidence",
        ))
        result = memory["memory_result"]

        self.assertEqual(result["memory_quality_label"], "AUDIT_ONLY_MEMORY")
        self.assertFalse(result["retrieval_ready"])
        self.assertIn("NO_VALID_SAFETY_EVIDENCE_FOR_TARGET", result["evidence_blockers"])

        for table in DOWNSTREAM_TABLES:
            self.assertEqual(count_rows(self.db_path, table), 0, table)

    def test_memory_becomes_clean_after_valid_real_evidence(self):
        """After inserting valid safety + quote evidence, rebuild can produce CLEAN_MEMORY."""
        build_manual_intake_token_pair_payload(self._args(
            pool_address=None, intake_reason="overlay-clean-test", source_request_id=None,
            token_symbol="OVL", token_name="Overlay", dex_id="raydium", intake_json=None,
        ))
        snapshot_ids = []
        for i in range(6):
            build_collect_token_snapshots_once_payload(
                self._args(snapshot_count=1, max_seconds=5.0, source_reference=f"ovl-clean-snap-{i}"),
                transport=self._snapshot_transport,
            )
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute("SELECT id FROM printer_token_snapshots ORDER BY id DESC LIMIT 1").fetchone()
                snap_id = int(row["id"])
                captured = (self.base_time + timedelta(minutes=i * 3)).isoformat()
                conn.execute("UPDATE printer_token_snapshots SET captured_at=? WHERE id=?", (captured, snap_id))
                conn.commit()
            finally:
                conn.close()
            snapshot_ids.append(snap_id)

        build_collect_context_once_payload(self._args(snapshot_id=snapshot_ids[-1], source_name="dexscreener"))
        self._force_all_context_known()

        # First build: AUDIT_ONLY (no evidence)
        first = build_memory_window_once_payload(self._args(
            snapshot_id=snapshot_ids[-1], memory_window="15m",
            source_reference="overlay-clean-first-window",
        ))
        mw_id = int(first["memory_result"]["memory_window_id"])
        self.assertEqual(first["memory_result"]["memory_quality_label"], "AUDIT_ONLY_MEMORY")

        # Get token_id and pair_id from DB
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            tok = conn.execute("SELECT id FROM printer_tokens WHERE token_mint='overlay-mint'").fetchone()
            pair = conn.execute("SELECT id FROM printer_pairs WHERE pair_address='overlay-pair'").fetchone()
            token_id = int(tok["id"])
            pair_id = int(pair["id"])
        finally:
            conn.close()

        # Insert real evidence via orchestrator with fixture transports
        target = RealEvidenceTarget(
            token_id=token_id,
            snapshot_id=snapshot_ids[-1],
            token_mint="overlay-mint",
            pair_id=pair_id,
            memory_window_id=mw_id,
        )
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            collect_real_evidence(
                conn,
                target,
                safety_transport=goplus_success_transport(_goplus_clean_payload("overlay-mint")),
                entry_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
                exit_quote_transport=jq_success_transport(_jupiter_clean_payload(route=True)),
            )
            conn.commit()
        finally:
            conn.close()

        # Second build: should now be CLEAN_MEMORY (evidence revision)
        second = build_memory_window_once_payload(self._args(
            snapshot_id=snapshot_ids[-1], memory_window="15m",
            source_reference="overlay-clean-second-window",
        ))
        result = second["memory_result"]

        self.assertEqual(result["memory_quality_label"], "CLEAN_MEMORY")
        self.assertTrue(result["retrieval_ready"])
        self.assertEqual(result["do_not_train"], 0)
        self.assertEqual(result["evidence_blockers"], [])

        # Downstream still untouched
        for table in DOWNSTREAM_TABLES:
            self.assertEqual(count_rows(self.db_path, table), 0, table)


# ---------------------------------------------------------------------------
# Class 9a: Liquidity lock/burn conservative framework
# ---------------------------------------------------------------------------

class LiquidityLockBurnConservativeTests(unittest.TestCase):
    """Prove that pool existence, liquidity amount, and partial data never
    produce LIQUIDITY_LOCK_OR_BURN_CONFIRMED; only explicit locked=True does."""

    def _norm(self, token_data, mint="test-mint"):
        return normalize_goplus_safety_response(
            token_data,
            token_id=1, snapshot_id=1, source_request_id=1,
            captured_at="2026-06-25T12:00:00+00:00",
        )

    def test_no_lp_fields_stays_unknown(self):
        """No lp_info or lp_lock at all → UNKNOWN."""
        ev = self._norm({"mintable": {"status": "0", "authority": []}})
        self.assertEqual(ev["liquidity_lock_or_burn_label"], "LIQUIDITY_LOCK_OR_BURN_UNKNOWN")

    def test_empty_lp_info_stays_unknown(self):
        """Empty lp_info list → UNKNOWN (pool list exists but no entries)."""
        ev = self._norm({"lp_info": []})
        self.assertEqual(ev["liquidity_lock_or_burn_label"], "LIQUIDITY_LOCK_OR_BURN_UNKNOWN")

    def test_pool_existence_alone_is_not_proof(self):
        """Pool address present without lock data → UNKNOWN."""
        ev = self._norm({
            "pool_address": "SomePool111111111111111111111111111111111111",
            "dex": "raydium",
        })
        self.assertEqual(ev["liquidity_lock_or_burn_label"], "LIQUIDITY_LOCK_OR_BURN_UNKNOWN")

    def test_liquidity_amount_alone_is_not_proof(self):
        """Liquidity amount present without lock data → UNKNOWN."""
        ev = self._norm({"liquidity": 150000.0, "lp_info": []})
        self.assertEqual(ev["liquidity_lock_or_burn_label"], "LIQUIDITY_LOCK_OR_BURN_UNKNOWN")

    def test_locked_percent_alone_without_locked_key_stays_unknown(self):
        """locked_percent non-zero but no explicit locked=True → UNKNOWN (conservative)."""
        ev = self._norm({"lp_info": [{"locked_percent": "100"}]})
        self.assertEqual(ev["liquidity_lock_or_burn_label"], "LIQUIDITY_LOCK_OR_BURN_UNKNOWN")

    def test_lp_info_non_mapping_entries_stays_unknown(self):
        """lp_info entries that are strings/ints (not Mapping) → UNKNOWN."""
        ev = self._norm({"lp_info": ["some_string", 42]})
        self.assertEqual(ev["liquidity_lock_or_burn_label"], "LIQUIDITY_LOCK_OR_BURN_UNKNOWN")

    def test_explicit_locked_true_produces_confirmed(self):
        """lp_info with locked=True → LIQUIDITY_LOCK_OR_BURN_CONFIRMED."""
        ev = self._norm({"lp_info": [{"locked": True, "locked_percent": "100"}]})
        self.assertEqual(ev["liquidity_lock_or_burn_label"], "LIQUIDITY_LOCK_OR_BURN_CONFIRMED")

    def test_explicit_locked_false_produces_unlocked(self):
        """All lp_info entries with locked=False → LIQUIDITY_UNLOCKED_OR_DANGEROUS."""
        ev = self._norm({"lp_info": [{"locked": False, "locked_percent": "0"}]})
        self.assertEqual(ev["liquidity_lock_or_burn_label"], "LIQUIDITY_UNLOCKED_OR_DANGEROUS")

    def test_mixed_locked_true_and_false_produces_confirmed(self):
        """At least one locked=True among entries → CONFIRMED (source proved something locked)."""
        ev = self._norm({"lp_info": [
            {"locked": True, "locked_percent": "80"},
            {"locked": False, "locked_percent": "0"},
        ]})
        self.assertEqual(ev["liquidity_lock_or_burn_label"], "LIQUIDITY_LOCK_OR_BURN_CONFIRMED")

    def test_lp_info_with_no_locked_key_stays_unknown(self):
        """Non-empty lp_info entry with no 'locked' key → UNKNOWN (not UNLOCKED)."""
        ev = self._norm({"lp_info": [{"pool": "SomePool", "amount": "9999"}]})
        self.assertEqual(ev["liquidity_lock_or_burn_label"], "LIQUIDITY_LOCK_OR_BURN_UNKNOWN")

    def test_lp_lock_true_alone_produces_confirmed(self):
        """Top-level lp_lock=True (no lp_info) → CONFIRMED."""
        ev = self._norm({"lp_lock": True})
        self.assertEqual(ev["liquidity_lock_or_burn_label"], "LIQUIDITY_LOCK_OR_BURN_CONFIRMED")

    def test_lp_lock_false_alone_produces_unlocked(self):
        """Top-level lp_lock=False (no lp_info) → UNLOCKED."""
        ev = self._norm({"lp_lock": False})
        self.assertEqual(ev["liquidity_lock_or_burn_label"], "LIQUIDITY_UNLOCKED_OR_DANGEROUS")

    def test_migration_alone_is_not_proof(self):
        """Migration field present without lock data → UNKNOWN."""
        ev = self._norm({"migration": "pumpswap", "migrated": True})
        self.assertEqual(ev["liquidity_lock_or_burn_label"], "LIQUIDITY_LOCK_OR_BURN_UNKNOWN")

    def test_unknown_liquidity_prevents_safety_clean(self):
        """LIQUIDITY_LOCK_OR_BURN_UNKNOWN must prevent SAFETY_CLEAN."""
        ev = self._norm({
            "mintable": {"status": "0", "authority": []},
            "freezable": {"status": "0", "authority": []},
            "metadata_mutable": {"status": "0", "metadata_upgrade_authority": []},
            "total_supply": "1000000000",
            "top_10_holders": [{"percent": "3"} for _ in range(10)],
            "lp_info": [],       # UNKNOWN
            "risky_flags": [],
        })
        self.assertEqual(ev["liquidity_lock_or_burn_label"], "LIQUIDITY_LOCK_OR_BURN_UNKNOWN")
        self.assertNotEqual(ev["safety_context_label"], "SAFETY_CLEAN")

    def test_unlocked_liquidity_prevents_safety_clean(self):
        """LIQUIDITY_UNLOCKED_OR_DANGEROUS must prevent SAFETY_CLEAN."""
        ev = self._norm({
            "mintable": {"status": "0", "authority": []},
            "freezable": {"status": "0", "authority": []},
            "metadata_mutable": {"status": "0", "metadata_upgrade_authority": []},
            "total_supply": "1000000000",
            "top_10_holders": [{"percent": "3"} for _ in range(10)],
            "lp_info": [{"locked": False}],  # UNLOCKED
            "risky_flags": [],
        })
        self.assertEqual(ev["liquidity_lock_or_burn_label"], "LIQUIDITY_UNLOCKED_OR_DANGEROUS")
        self.assertNotEqual(ev["safety_context_label"], "SAFETY_CLEAN")


# ---------------------------------------------------------------------------
# Class 9b: Known-risk flag conservative label
# ---------------------------------------------------------------------------

class KnownRiskFlagTests(unittest.TestCase):

    def _norm(self, token_data):
        return normalize_goplus_safety_response(
            token_data,
            token_id=1, snapshot_id=1, source_request_id=1,
            captured_at="2026-06-25T12:00:00+00:00",
        )

    def test_missing_risk_field_stays_unknown(self):
        """No risk field present → KNOWN_RISK_FLAGS_UNKNOWN."""
        ev = self._norm({"total_supply": "1000000000"})
        self.assertEqual(ev["known_risk_flag_label"], "KNOWN_RISK_FLAGS_UNKNOWN")

    def test_risky_flags_null_stays_unknown(self):
        """risky_flags=None → KNOWN_RISK_FLAGS_UNKNOWN (not safe)."""
        ev = self._norm({"risky_flags": None})
        self.assertEqual(ev["known_risk_flag_label"], "KNOWN_RISK_FLAGS_UNKNOWN")

    def test_absence_of_risk_field_is_not_safe(self):
        """Absence of risk key must not produce NO_KNOWN_RISK_FLAGS."""
        ev = self._norm({"total_supply": "1000000000"})
        self.assertNotEqual(ev["known_risk_flag_label"], "NO_KNOWN_RISK_FLAGS")

    def test_explicit_empty_risky_flags_maps_to_no_risk(self):
        """risky_flags=[] explicitly → NO_KNOWN_RISK_FLAGS."""
        ev = self._norm({"risky_flags": []})
        self.assertEqual(ev["known_risk_flag_label"], "NO_KNOWN_RISK_FLAGS")

    def test_nonempty_risky_flags_maps_to_present(self):
        """risky_flags=[...] non-empty → KNOWN_RISK_FLAGS_PRESENT."""
        ev = self._norm({"risky_flags": ["honeypot_risk"]})
        self.assertEqual(ev["known_risk_flag_label"], "KNOWN_RISK_FLAGS_PRESENT")

    def test_explicit_empty_risk_flags_key_maps_to_no_risk(self):
        """risk_flags=[] → NO_KNOWN_RISK_FLAGS."""
        ev = self._norm({"risk_flags": []})
        self.assertEqual(ev["known_risk_flag_label"], "NO_KNOWN_RISK_FLAGS")

    def test_nonempty_risks_key_maps_to_present(self):
        """risks=['rug_pull'] → KNOWN_RISK_FLAGS_PRESENT."""
        ev = self._norm({"risks": ["rug_pull"]})
        self.assertEqual(ev["known_risk_flag_label"], "KNOWN_RISK_FLAGS_PRESENT")

    def test_unknown_risk_prevents_safety_clean(self):
        """KNOWN_RISK_FLAGS_UNKNOWN must prevent SAFETY_CLEAN."""
        ev = self._norm({
            "mintable": {"status": "0", "authority": []},
            "freezable": {"status": "0", "authority": []},
            "metadata_mutable": {"status": "0", "metadata_upgrade_authority": []},
            "total_supply": "1000000000",
            "top_10_holders": [{"percent": "3"} for _ in range(10)],
            "lp_info": [{"locked": True}],
            # no risk field → UNKNOWN
        })
        self.assertEqual(ev["known_risk_flag_label"], "KNOWN_RISK_FLAGS_UNKNOWN")
        self.assertNotEqual(ev["safety_context_label"], "SAFETY_CLEAN")

    def test_present_risk_prevents_safety_clean(self):
        """KNOWN_RISK_FLAGS_PRESENT must prevent SAFETY_CLEAN."""
        ev = self._norm({
            "mintable": {"status": "0", "authority": []},
            "freezable": {"status": "0", "authority": []},
            "metadata_mutable": {"status": "0", "metadata_upgrade_authority": []},
            "total_supply": "1000000000",
            "top_10_holders": [{"percent": "3"} for _ in range(10)],
            "lp_info": [{"locked": True}],
            "risky_flags": ["bad_flag"],
        })
        self.assertEqual(ev["known_risk_flag_label"], "KNOWN_RISK_FLAGS_PRESENT")
        self.assertNotEqual(ev["safety_context_label"], "SAFETY_CLEAN")


# ---------------------------------------------------------------------------
# Class 9c: Effective safety merge — all required fields must be clean
# ---------------------------------------------------------------------------

from printer_v1.safety.goplus_normalizer import (
    REQUIRED_CLEAN_SAFETY_FIELDS,
    compute_safety_context_label,
)


class EffectiveSafetyMergeTests(unittest.TestCase):
    """compute_safety_context_label must only return SAFETY_CLEAN when every
    required field is at its explicit clean value. Any UNKNOWN → SAFETY_UNKNOWN."""

    def _all_clean(self) -> dict:
        return {
            "mint_authority_status": "MINT_AUTHORITY_RENOUNCED",
            "freeze_authority_status": "FREEZE_AUTHORITY_DISABLED",
            "metadata_mutability_status": "METADATA_IMMUTABLE",
            "supply_sanity_label": "SUPPLY_SANITY_OK",
            "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
            "liquidity_lock_or_burn_label": "LIQUIDITY_LOCK_OR_BURN_CONFIRMED",
            "known_risk_flag_label": "NO_KNOWN_RISK_FLAGS",
            "token_program_label": "SPL_TOKEN_OR_TOKEN_2022_VERIFIED",
        }

    def test_all_clean_fields_produces_safety_clean(self):
        self.assertEqual(compute_safety_context_label(self._all_clean()), "SAFETY_CLEAN")

    def test_missing_liquidity_lock_produces_safety_unknown(self):
        ev = {**self._all_clean(), "liquidity_lock_or_burn_label": "LIQUIDITY_LOCK_OR_BURN_UNKNOWN"}
        self.assertEqual(compute_safety_context_label(ev), "SAFETY_UNKNOWN")

    def test_missing_known_risk_produces_safety_unknown(self):
        ev = {**self._all_clean(), "known_risk_flag_label": "KNOWN_RISK_FLAGS_UNKNOWN"}
        self.assertEqual(compute_safety_context_label(ev), "SAFETY_UNKNOWN")

    def test_missing_holder_concentration_produces_safety_unknown(self):
        ev = {**self._all_clean(), "holder_concentration_label": "HOLDER_CONCENTRATION_UNKNOWN"}
        self.assertEqual(compute_safety_context_label(ev), "SAFETY_UNKNOWN")

    def test_missing_mint_authority_produces_safety_unknown(self):
        ev = {**self._all_clean(), "mint_authority_status": "MINT_AUTHORITY_UNKNOWN"}
        self.assertEqual(compute_safety_context_label(ev), "SAFETY_UNKNOWN")

    def test_missing_freeze_authority_produces_safety_unknown(self):
        ev = {**self._all_clean(), "freeze_authority_status": "FREEZE_AUTHORITY_UNKNOWN"}
        self.assertEqual(compute_safety_context_label(ev), "SAFETY_UNKNOWN")

    def test_missing_metadata_produces_safety_unknown(self):
        ev = {**self._all_clean(), "metadata_mutability_status": "METADATA_UNKNOWN"}
        self.assertEqual(compute_safety_context_label(ev), "SAFETY_UNKNOWN")

    def test_missing_supply_sanity_produces_safety_unknown(self):
        ev = {**self._all_clean(), "supply_sanity_label": "SUPPLY_SANITY_UNKNOWN"}
        self.assertEqual(compute_safety_context_label(ev), "SAFETY_UNKNOWN")

    def test_token_program_unsupported_produces_safety_unsafe(self):
        ev = {**self._all_clean(), "token_program_label": "TOKEN_PROGRAM_UNSUPPORTED"}
        self.assertEqual(compute_safety_context_label(ev), "SAFETY_UNSAFE")

    def test_present_mint_authority_does_not_produce_safety_clean(self):
        ev = {**self._all_clean(), "mint_authority_status": "MINT_AUTHORITY_PRESENT"}
        self.assertNotEqual(compute_safety_context_label(ev), "SAFETY_CLEAN")

    def test_mutable_metadata_does_not_produce_safety_clean(self):
        ev = {**self._all_clean(), "metadata_mutability_status": "METADATA_MUTABLE"}
        self.assertNotEqual(compute_safety_context_label(ev), "SAFETY_CLEAN")

    def test_unlocked_liquidity_does_not_produce_safety_clean(self):
        ev = {**self._all_clean(), "liquidity_lock_or_burn_label": "LIQUIDITY_UNLOCKED_OR_DANGEROUS"}
        self.assertNotEqual(compute_safety_context_label(ev), "SAFETY_CLEAN")

    def test_risk_flags_present_does_not_produce_safety_clean(self):
        ev = {**self._all_clean(), "known_risk_flag_label": "KNOWN_RISK_FLAGS_PRESENT"}
        self.assertNotEqual(compute_safety_context_label(ev), "SAFETY_CLEAN")

    def test_concentrated_holders_does_not_produce_safety_clean(self):
        ev = {**self._all_clean(), "holder_concentration_label": "HOLDER_CONCENTRATION_CONCENTRATED"}
        self.assertNotEqual(compute_safety_context_label(ev), "SAFETY_CLEAN")

    def test_empty_evidence_is_safety_unknown(self):
        self.assertEqual(compute_safety_context_label({}), "SAFETY_UNKNOWN")

    def test_required_clean_safety_fields_covers_all_required_categories(self):
        required = set(REQUIRED_CLEAN_SAFETY_FIELDS.keys())
        expected = {
            "mint_authority_status",
            "freeze_authority_status",
            "metadata_mutability_status",
            "supply_sanity_label",
            "holder_concentration_label",
            "liquidity_lock_or_burn_label",
            "known_risk_flag_label",
            "token_program_label",
        }
        self.assertEqual(required, expected)


# ---------------------------------------------------------------------------
# Class 9d: Reporting consistency — source fail is clearly surfaced
# ---------------------------------------------------------------------------

class ReportingConsistencyTests(unittest.TestCase):
    """When a source request is recorded but fails, the item_result must make
    that clear: request_recorded=True, source_failed=True, inserted=False,
    clean_eligible=False."""

    def setUp(self):
        self._tmp, self.db_path = make_db()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                "INSERT INTO printer_tokens (id, token_mint, chain, symbol, name, token_status) "
                "VALUES (1, 'report-mint', 'solana', 'RPT', 'Report', 'TRACK_NORMAL')"
            )
            conn.execute(
                "INSERT INTO printer_pairs (id, token_id, pair_address, dex, pool_source) "
                "VALUES (1, 1, 'report-pair', 'raydium', 'fixture')"
            )
            conn.execute(
                "INSERT INTO printer_token_snapshots "
                "(id, token_id, pair_id, captured_at, tracking_lane, snapshot_mode, "
                "price_usd, liquidity_usd, source_status, data_quality_label) "
                "VALUES (1, 1, 1, '2026-06-25T12:00:00+00:00', 'TRACK_NORMAL', 'NORMAL_MODE', "
                "0.001, 50000, 'COMPLETE', 'CLEAN_DATA')"
            )
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self._tmp.cleanup()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def test_failed_safety_source_has_request_recorded_true(self):
        target = RealEvidenceTarget(
            token_id=1, snapshot_id=1, token_mint="report-mint", pair_id=1
        )
        with self.connect() as conn:
            result = collect_real_evidence(
                conn, target,
                safety_transport=goplus_failure_transport(),
                entry_quote_transport=jq_success_transport(_jupiter_clean_payload()),
                exit_quote_transport=jq_success_transport(_jupiter_clean_payload()),
            )
        safety_items = [r for r in result.item_results if r.evidence_type == "goplus_safety"]
        self.assertEqual(len(safety_items), 1)
        item = safety_items[0]
        self.assertIsNotNone(item.source_request_id, "source request must be recorded on failure")
        self.assertFalse(item.inserted)
        self.assertFalse(item.clean_eligible)

    def test_failed_safety_source_has_failure_id_set(self):
        target = RealEvidenceTarget(
            token_id=1, snapshot_id=1, token_mint="report-mint", pair_id=1
        )
        with self.connect() as conn:
            result = collect_real_evidence(
                conn, target,
                safety_transport=goplus_failure_transport(),
                entry_quote_transport=jq_success_transport(_jupiter_clean_payload()),
                exit_quote_transport=jq_success_transport(_jupiter_clean_payload()),
            )
        safety_items = [r for r in result.item_results if r.evidence_type == "goplus_safety"]
        item = safety_items[0]
        self.assertIsNotNone(item.source_failure_id, "failure record must be set on failure")
        self.assertIsNone(item.source_response_id, "response must be absent on failure")

    def test_failed_quote_source_has_request_recorded_true(self):
        target = RealEvidenceTarget(
            token_id=1, snapshot_id=1, token_mint="report-mint", pair_id=1
        )
        with self.connect() as conn:
            result = collect_real_evidence(
                conn, target,
                safety_transport=goplus_success_transport(_goplus_clean_payload("report-mint")),
                entry_quote_transport=jq_failure_transport(),
                exit_quote_transport=jq_success_transport(_jupiter_clean_payload()),
            )
        entry_items = [r for r in result.item_results if "entry" in r.evidence_type]
        self.assertEqual(len(entry_items), 1)
        item = entry_items[0]
        self.assertIsNotNone(item.source_request_id)
        self.assertFalse(item.clean_eligible)


# ---------------------------------------------------------------------------
# Class 9e: Operator output — new payload fields (Tasks 7+8)
# ---------------------------------------------------------------------------

class OperatorOutputEnhancedTests(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = make_db()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                "INSERT INTO printer_tokens (id, token_mint, chain, symbol, name, token_status) "
                "VALUES (1, 'out-mint', 'solana', 'OUT', 'Output', 'TRACK_NORMAL')"
            )
            conn.execute(
                "INSERT INTO printer_pairs (id, token_id, pair_address, dex, pool_source) "
                "VALUES (1, 1, 'out-pair', 'raydium', 'fixture')"
            )
            conn.execute(
                "INSERT INTO printer_token_snapshots "
                "(id, token_id, pair_id, captured_at, tracking_lane, snapshot_mode, "
                "price_usd, liquidity_usd, source_status, data_quality_label) "
                "VALUES (1, 1, 1, '2026-06-25T12:00:00+00:00', 'TRACK_NORMAL', 'NORMAL_MODE', "
                "0.001, 50000, 'COMPLETE', 'CLEAN_DATA')"
            )
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self._tmp.cleanup()

    def _args(self, **kw):
        values = {
            "db_path": str(self.db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "token_id": 1,
            "token_mint": None,
            "pair_id": 1,
            "pair_address": None,
            "snapshot_id": 1,
            "memory_window_id": None,
            "evidence_window_id": None,
            "paper_amount_lamports": DEFAULT_PAPER_AMOUNT_LAMPORTS,
            "slippage_bps": DEFAULT_SLIPPAGE_BPS,
            "quote_currency_mint": WSOL_MINT,
            "solana_rpc_url": None,
            "solana_rpc_fallback_url": None,
        }
        values.update(kw)
        return argparse.Namespace(**values)

    def _run_with_transports(
        self,
        safety_payload,
        entry_payload=None,
        exit_payload=None,
        holder_rpc_transport=None,
        **arg_overrides,
    ):
        import printer_v1.operator_cli.commands as cmd_module
        import printer_v1.evidence_fill.real as real_module
        original = real_module.collect_real_evidence

        def patched(connection, target, **kwargs):
            kwargs["safety_transport"] = goplus_success_transport(safety_payload)
            if holder_rpc_transport is not None:
                kwargs["holder_rpc_transport"] = holder_rpc_transport
            kwargs["entry_quote_transport"] = jq_success_transport(
                entry_payload or _jupiter_clean_payload(route=True)
            )
            kwargs["exit_quote_transport"] = jq_success_transport(
                exit_payload or _jupiter_clean_payload(route=True)
            )
            return original(connection, target, **kwargs)

        # Patch the name in the commands module (local binding from `from ... import`).
        cmd_module.collect_real_evidence = patched
        try:
            return cmd_module.build_collect_real_evidence_once_payload(self._args(**arg_overrides))
        finally:
            cmd_module.collect_real_evidence = original

    def test_payload_has_resolved_safety_fields(self):
        payload = self._run_with_transports(_goplus_clean_payload("out-mint"))
        self.assertIn("resolved_safety_fields", payload)
        self.assertIsInstance(payload["resolved_safety_fields"], list)

    def test_payload_has_unresolved_safety_fields(self):
        payload = self._run_with_transports(_goplus_clean_payload("out-mint"))
        self.assertIn("unresolved_safety_fields", payload)
        self.assertIsInstance(payload["unresolved_safety_fields"], list)

    def test_payload_has_safety_sources_used(self):
        payload = self._run_with_transports(_goplus_clean_payload("out-mint"))
        self.assertIn("safety_sources_used", payload)
        self.assertIsInstance(payload["safety_sources_used"], list)

    def test_payload_has_quote_sources_used(self):
        payload = self._run_with_transports(_goplus_clean_payload("out-mint"))
        self.assertIn("quote_sources_used", payload)
        self.assertIsInstance(payload["quote_sources_used"], list)

    def test_payload_has_clean_eligible(self):
        payload = self._run_with_transports(_goplus_clean_payload("out-mint"))
        self.assertIn("clean_eligible", payload)

    def test_payload_has_audit_only(self):
        payload = self._run_with_transports(_goplus_clean_payload("out-mint"))
        self.assertIn("audit_only", payload)

    def test_default_rpc_source_requires_no_api_key(self):
        payload = self._run_with_transports(_goplus_clean_payload("out-mint"))
        self.assertEqual(payload["holder_rpc_status"], "NOT_ATTEMPTED")
        self.assertEqual(payload["holder_rpc_source_used"], "api.mainnet-beta.solana.com")
        self.assertNotIn("api-key", payload["holder_rpc_source_used"])

    def test_rpc_source_can_come_from_environment_and_is_redacted(self):
        old_value = os.environ.get("PRINTER_SOLANA_RPC_URL")
        os.environ["PRINTER_SOLANA_RPC_URL"] = "https://env-rpc.example.test/?token=hidden"
        try:
            payload = self._run_with_transports(_goplus_clean_payload("out-mint"))
        finally:
            if old_value is None:
                os.environ.pop("PRINTER_SOLANA_RPC_URL", None)
            else:
                os.environ["PRINTER_SOLANA_RPC_URL"] = old_value
        self.assertEqual(payload["holder_rpc_source_used"], "env-rpc.example.test")
        self.assertNotIn("hidden", json.dumps(payload))

    def test_clean_safety_gives_empty_unresolved_fields(self):
        payload = self._run_with_transports(_goplus_clean_payload("out-mint"))
        self.assertEqual(payload["unresolved_safety_fields"], [])

    def test_clean_safety_gives_clean_eligible_true(self):
        payload = self._run_with_transports(_goplus_clean_payload("out-mint"))
        self.assertTrue(payload["clean_eligible"])
        self.assertFalse(payload["audit_only"])

    def test_partial_safety_gives_nonempty_unresolved_fields(self):
        """GoPlus partial payload (missing holder + liquidity) → unresolved fields present."""
        payload = self._run_with_transports(_goplus_real_solana_payload("out-mint"))
        self.assertGreater(len(payload["unresolved_safety_fields"]), 0)

    def test_partial_safety_gives_clean_eligible_false(self):
        payload = self._run_with_transports(_goplus_real_solana_payload("out-mint"))
        self.assertFalse(payload["clean_eligible"])
        self.assertTrue(payload["audit_only"])

    def test_next_step_hint_mentions_audit_only_when_unresolved(self):
        payload = self._run_with_transports(_goplus_real_solana_payload("out-mint"))
        hint = payload["next_step_hint"].upper()
        self.assertIn("AUDIT_ONLY", hint)

    def test_next_step_hint_mentions_lane_7_when_unresolved(self):
        payload = self._run_with_transports(_goplus_real_solana_payload("out-mint"))
        hint = payload["next_step_hint"].upper()
        self.assertIn("LANE 7", hint)

    def test_next_step_hint_mentions_clean_when_unresolved(self):
        payload = self._run_with_transports(_goplus_real_solana_payload("out-mint"))
        hint = payload["next_step_hint"].upper()
        self.assertIn("CLEAN", hint)

    def test_goplus_safety_in_safety_sources_used_when_inserted(self):
        payload = self._run_with_transports(_goplus_clean_payload("out-mint"))
        self.assertIn("goplus_safety", payload["safety_sources_used"])

    def test_quote_sources_used_contains_entry_and_exit_on_success(self):
        payload = self._run_with_transports(_goplus_clean_payload("out-mint"))
        self.assertIn("jupiter_quote_entry", payload["quote_sources_used"])
        self.assertIn("jupiter_quote_exit", payload["quote_sources_used"])

    def test_evidence_table_deltas_count_inserted_rows(self):
        payload = self._run_with_transports(_goplus_clean_payload("out-mint"))
        self.assertEqual(payload["evidence_table_deltas"]["printer_solana_safety_evidence"], 1)
        self.assertEqual(payload["evidence_table_deltas"]["printer_paper_quote_evidence"], 2)

    def test_holder_rate_limit_reporting_is_clear_and_redacted(self):
        import printer_v1.sources.solana_rpc_holder as holder_module

        original = holder_module.url_request.urlopen

        def fake_urlopen(request, timeout):
            del request, timeout
            raise url_error.HTTPError(
                "https://rpc.example.test/?api-key=secret-token",
                429,
                "Too Many Requests",
                hdrs=None,
                fp=io.BytesIO(b""),
            )

        holder_module.url_request.urlopen = fake_urlopen
        try:
            payload = self._run_with_transports(
                _goplus_real_solana_payload("out-mint"),
                solana_rpc_url="https://rpc.example.test/?api-key=secret-token",
            )
        finally:
            holder_module.url_request.urlopen = original
        self.assertEqual(payload["holder_rpc_status"], "FAILED")
        self.assertEqual(payload["holder_rpc_failure_type"], "solana_rpc_rate_limited")
        self.assertTrue(payload["holder_rpc_rate_limited"])
        self.assertEqual(payload["holder_rpc_source_used"], "rpc.example.test")
        self.assertIn("holder_concentration_label", payload["unresolved_safety_fields"])
        self.assertIn("rate limited", payload["next_step_hint"].lower())
        self.assertIn("operator-approved free/read-only RPC endpoint", payload["next_step_hint"])
        self.assertNotIn("secret-token", json.dumps(payload))
        self.assertNotIn("api-key", json.dumps(payload))

    def test_item_results_contain_source_request_recorded_flag(self):
        payload = self._run_with_transports(_goplus_clean_payload("out-mint"))
        for item in payload["item_results"]:
            self.assertIn("source_request_recorded", item)

    def test_item_results_contain_source_failed_flag(self):
        payload = self._run_with_transports(_goplus_clean_payload("out-mint"))
        for item in payload["item_results"]:
            self.assertIn("source_failed", item)

    def test_all_downstream_unlock_flags_false_in_enhanced_payload(self):
        payload = self._run_with_transports(_goplus_clean_payload("out-mint"))
        for item in payload["item_results"]:
            for key, val in item["downstream_unlocks"].items():
                self.assertFalse(val, f"downstream unlock {key} must be False")


# ---------------------------------------------------------------------------
# Class 9f: Forbidden-term scan on new/changed source files
# ---------------------------------------------------------------------------

SCANNED_SOURCE_FILES = [
    SRC_PATH / "printer_v1" / "sources" / "goplus.py",
    SRC_PATH / "printer_v1" / "sources" / "jupiter_quote.py",
    SRC_PATH / "printer_v1" / "sources" / "solana_rpc_holder.py",
    SRC_PATH / "printer_v1" / "safety" / "goplus_normalizer.py",
    SRC_PATH / "printer_v1" / "evidence_fill" / "real.py",
]

FORBIDDEN_SOURCE_TERMS = (
    "wallet",
    "private_key",
    "signing",
    "sendTransaction",
    "swap_instructions",
    "swapInstructions",
    "live_execution",
    "buy_unlock",
    "pnl",
    "score",
    "rank",
    "confidence",
    "weighted",
)


class ForbiddenTermScanTests(unittest.TestCase):

    def _check_file(self, path, terms):
        text = path.read_text(encoding="utf-8")
        hits = [t for t in terms if t in text]
        return hits

    def test_goplus_source_has_no_forbidden_terms(self):
        path = SRC_PATH / "printer_v1" / "sources" / "goplus.py"
        hits = self._check_file(path, FORBIDDEN_SOURCE_TERMS)
        self.assertEqual(hits, [], f"Forbidden terms in goplus.py: {hits}")

    def test_jupiter_quote_source_has_no_forbidden_terms(self):
        path = SRC_PATH / "printer_v1" / "sources" / "jupiter_quote.py"
        hits = self._check_file(path, FORBIDDEN_SOURCE_TERMS)
        self.assertEqual(hits, [], f"Forbidden terms in jupiter_quote.py: {hits}")

    def test_solana_rpc_holder_source_has_no_forbidden_terms(self):
        path = SRC_PATH / "printer_v1" / "sources" / "solana_rpc_holder.py"
        hits = self._check_file(path, FORBIDDEN_SOURCE_TERMS)
        self.assertEqual(hits, [], f"Forbidden terms in solana_rpc_holder.py: {hits}")

    def test_goplus_normalizer_has_no_forbidden_terms(self):
        path = SRC_PATH / "printer_v1" / "safety" / "goplus_normalizer.py"
        hits = self._check_file(path, FORBIDDEN_SOURCE_TERMS)
        self.assertEqual(hits, [], f"Forbidden terms in goplus_normalizer.py: {hits}")

    def test_real_evidence_fill_has_no_wallet_or_key_terms(self):
        # real.py uses "pnl", "paper_decision" etc. as disabled-flag dict keys only.
        # Scan only for terms that have no legitimate disabled-flag use.
        path = SRC_PATH / "printer_v1" / "evidence_fill" / "real.py"
        text = path.read_text(encoding="utf-8")
        for term in ("wallet", "private_key", "signing", "sendTransaction",
                     "live_execution", "buy_unlock", "swapInstructions"):
            self.assertNotIn(term, text, f"Forbidden term '{term}' in real.py")

    def test_no_retrieval_unlock_in_real_evidence_fill(self):
        text = (SRC_PATH / "printer_v1" / "evidence_fill" / "real.py").read_text(encoding="utf-8")
        self.assertNotIn("retrieval_ready", text)
        self.assertNotIn("retrieval_unlock", text)

    def test_no_buy_execution_in_real_evidence_fill(self):
        text = (SRC_PATH / "printer_v1" / "evidence_fill" / "real.py").read_text(encoding="utf-8")
        # buy/position/trade/pnl appear only as "False" disabled-flag keys, not as actions
        self.assertNotIn("execute_buy", text)
        self.assertNotIn("trigger_buy", text)
        self.assertNotIn("record_paper_position", text)
        self.assertNotIn("record_paper_trade", text)
        self.assertNotIn("record_pnl", text)


if __name__ == "__main__":
    unittest.main()

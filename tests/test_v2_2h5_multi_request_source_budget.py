"""V2-2H.5 — Bounded Multi-Request Source Plumbing.

Targeted unit tests for:
  A. _build_source_request_plan: plan structure, ordering, NOT_READY items
  B. _get_transport_for_index: None / single callable / list routing
  C. _build_source_budget_report: all metric fields
  D. _validate_discover_candidates_args: max_source_requests range enforcement
  E. Multi-request integration: geckoterminal with max_source_requests=2
  F. Backward-compat: single-request path (max_source_requests=1) preserves
     all pre-H.5 payload fields
  G. NOT_READY plan items are reported but not executed
  H. _aggregate_wr_reports: merging multiple per-response WR reports

Locks preserved: no live discovery, no source fetching, no live DB mutation,
no memory generation, no retrieval, no paper decisions, no BUY/SELL/HOLD,
no positions/trades/audits/PnL, no scoring/ranking/confidence/weighted logic.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import (
    _MAX_SOURCE_REQUESTS_DEFAULT,
    _MAX_SOURCE_REQUESTS_MAX,
    _MAX_SOURCE_REQUESTS_MIN,
    _PLAN_STATUS_NOT_READY,
    _PLAN_STATUS_READY,
    _SOURCE_REQUEST_PLAN_CATALOG,
    _aggregate_wr_reports,
    _build_source_budget_report,
    _build_source_request_plan,
    _get_transport_for_index,
    _validate_discover_candidates_args,
    build_discover_candidates_once_payload,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_SOLANA_WSOL = "So11111111111111111111111111111111111111112"


def _db_path(tmp_dir: str) -> str:
    p = pathlib.Path(tmp_dir) / "test_h5.db"
    apply_migrations(p)
    return str(p)


def _run_args(db_path: str, **overrides) -> argparse.Namespace:
    base = {
        "project_root": str(PROJECT_ROOT),
        "format": "json",
        "no_color": True,
        "operator_approved": True,
        "chain": "solana",
        "max_candidates": 10,
        "query": "pump",
        "timeout_seconds": 5.0,
        "source_name": "dexscreener",
        "request_kind": None,
        "request_key": "v2-2h5-test",
        "db_path": db_path,
        "max_source_requests": _MAX_SOURCE_REQUESTS_DEFAULT,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _dex_transport(pairs: list[dict]):
    def _transport(context):
        del context
        return {"pairs": pairs}
    return _transport


def _gt_transport(pools: list[dict]):
    """GeckoTerminal fixture transport: wraps pools in GT-style envelope."""
    def _transport(context):
        del context
        return {"data": pools}
    return _transport


def _minimal_dex_pair(
    pair_address: str = "PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    token_mint: str = "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    *,
    symbol: str = "TST",
    liquidity_usd: float = 9000.0,
    volume_5m: float = 3000.0,
    txns_5m: int = 25,
) -> dict:
    return {
        "pairAddress": pair_address,
        "baseToken": {"address": token_mint, "symbol": symbol, "name": "Test Token"},
        "quoteToken": {"address": _SOLANA_WSOL},
        "chainId": "solana",
        "dexId": "raydium",
        "priceUsd": "0.0001",
        "liquidity": {"usd": liquidity_usd},
        "volume": {"m5": volume_5m, "h1": 10000.0, "h24": 50000.0},
        "txns": {"m5": {"buys": txns_5m, "sells": txns_5m}},
        "pairCreatedAt": 1700000000000,
    }


def _fake_exec_record(
    source_name: str = "dexscreener",
    request_kind: str = "token_discovery",
    executed: bool = True,
    response_id=1,
    failure_id=None,
    candidates_seen: int = 0,
    candidates_persisted: int = 0,
    status: str = _PLAN_STATUS_READY,
) -> dict:
    return {
        "plan_index": 0,
        "source_name": source_name,
        "request_kind": request_kind,
        "status": status,
        "executed": executed,
        "result": None,
        "request_id": 1 if executed else None,
        "response_id": response_id,
        "failure_id": failure_id,
        "source_channel": "DEXSCREENER_SEARCH",
        "source_channel_reason": "test",
        "endpoint": "https://example.com",
        "query": "pump",
        "display_request_kind": request_kind,
        "candidates_seen": candidates_seen,
        "candidates_persisted": candidates_persisted,
    }


# ---------------------------------------------------------------------------
# A. _build_source_request_plan
# ---------------------------------------------------------------------------

class TestBuildSourceRequestPlan(unittest.TestCase):

    def test_dexscreener_default_plan_has_one_item(self):
        plan = _build_source_request_plan("dexscreener", None, 1)
        self.assertEqual(len(plan), 1)

    def test_dexscreener_plan_item_is_ready(self):
        plan = _build_source_request_plan("dexscreener", None, 1)
        self.assertEqual(plan[0]["status"], _PLAN_STATUS_READY)

    def test_dexscreener_plan_item_request_kind(self):
        plan = _build_source_request_plan("dexscreener", None, 1)
        self.assertEqual(plan[0]["request_kind"], "token_discovery")

    def test_geckoterminal_max1_gives_one_item(self):
        plan = _build_source_request_plan("geckoterminal", None, 1)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["request_kind"], "geckoterminal_new_pool_discovery")
        self.assertEqual(plan[0]["status"], _PLAN_STATUS_READY)

    def test_geckoterminal_max2_gives_two_items(self):
        plan = _build_source_request_plan("geckoterminal", None, 2)
        self.assertEqual(len(plan), 2)
        self.assertEqual(plan[0]["request_kind"], "geckoterminal_new_pool_discovery")
        self.assertEqual(plan[1]["request_kind"], "geckoterminal_trending_pool_reference")

    def test_geckoterminal_both_items_are_ready(self):
        plan = _build_source_request_plan("geckoterminal", None, 2)
        self.assertTrue(all(p["status"] == _PLAN_STATUS_READY for p in plan))

    def test_geckoterminal_max10_caps_at_catalog_size(self):
        plan = _build_source_request_plan("geckoterminal", None, 10)
        catalog_size = len(_SOURCE_REQUEST_PLAN_CATALOG["geckoterminal"])
        self.assertEqual(len(plan), catalog_size)

    def test_pumpportal_max1_gives_one_not_ready_item(self):
        plan = _build_source_request_plan("pumpportal", None, 1)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["status"], _PLAN_STATUS_NOT_READY)

    def test_pumpswap_max1_gives_one_not_ready_item(self):
        plan = _build_source_request_plan("pumpswap", None, 1)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["status"], _PLAN_STATUS_NOT_READY)

    def test_plan_index_is_sequential(self):
        plan = _build_source_request_plan("geckoterminal", None, 2)
        self.assertEqual(plan[0]["plan_index"], 0)
        self.assertEqual(plan[1]["plan_index"], 1)

    def test_plan_source_name_matches(self):
        plan = _build_source_request_plan("dexscreener", None, 1)
        self.assertEqual(plan[0]["source_name"], "dexscreener")

    def test_initial_request_kind_at_position_0_no_reorder(self):
        """Specifying the default first item produces the same plan."""
        plan_default = _build_source_request_plan("geckoterminal", None, 2)
        plan_explicit = _build_source_request_plan(
            "geckoterminal", "geckoterminal_new_pool_discovery", 2
        )
        self.assertEqual(
            [p["request_kind"] for p in plan_default],
            [p["request_kind"] for p in plan_explicit],
        )

    def test_initial_request_kind_reorders_to_position_0(self):
        """Requesting the second catalog item first moves it to front."""
        plan = _build_source_request_plan(
            "geckoterminal", "geckoterminal_trending_pool_reference", 2
        )
        self.assertEqual(plan[0]["request_kind"], "geckoterminal_trending_pool_reference")
        self.assertEqual(plan[1]["request_kind"], "geckoterminal_new_pool_discovery")

    def test_initial_request_kind_not_in_catalog_inserted_as_ready(self):
        """Unknown kind is inserted as READY at position 0."""
        plan = _build_source_request_plan("dexscreener", "boosted_discovery", 1)
        self.assertEqual(plan[0]["request_kind"], "boosted_discovery")
        self.assertEqual(plan[0]["status"], _PLAN_STATUS_READY)

    def test_max_source_requests_1_with_geckoterminal_trending_gives_one_item(self):
        plan = _build_source_request_plan(
            "geckoterminal", "geckoterminal_trending_pool_reference", 1
        )
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["request_kind"], "geckoterminal_trending_pool_reference")

    def test_unknown_source_gives_empty_plan(self):
        plan = _build_source_request_plan("unknown_source", None, 5)
        self.assertEqual(plan, [])


# ---------------------------------------------------------------------------
# B. _get_transport_for_index
# ---------------------------------------------------------------------------

class TestGetTransportForIndex(unittest.TestCase):

    def test_none_transport_returns_none_for_any_index(self):
        self.assertIsNone(_get_transport_for_index(None, 0))
        self.assertIsNone(_get_transport_for_index(None, 5))

    def test_single_callable_returned_for_index_0(self):
        fn = lambda ctx: {}
        self.assertIs(_get_transport_for_index(fn, 0), fn)

    def test_single_callable_returned_for_any_index(self):
        fn = lambda ctx: {}
        self.assertIs(_get_transport_for_index(fn, 3), fn)

    def test_list_transport_index_0_returns_first(self):
        fn0 = lambda ctx: {"idx": 0}
        fn1 = lambda ctx: {"idx": 1}
        self.assertIs(_get_transport_for_index([fn0, fn1], 0), fn0)

    def test_list_transport_index_1_returns_second(self):
        fn0 = lambda ctx: {"idx": 0}
        fn1 = lambda ctx: {"idx": 1}
        self.assertIs(_get_transport_for_index([fn0, fn1], 1), fn1)

    def test_list_transport_out_of_range_returns_none(self):
        fn0 = lambda ctx: {}
        self.assertIsNone(_get_transport_for_index([fn0], 1))

    def test_empty_list_always_returns_none(self):
        self.assertIsNone(_get_transport_for_index([], 0))


# ---------------------------------------------------------------------------
# C. _build_source_budget_report
# ---------------------------------------------------------------------------

class TestBuildSourceBudgetReport(unittest.TestCase):

    def _simple_plan(self, n=1):
        return [
            {"plan_index": i, "source_name": "dexscreener", "request_kind": "token_discovery", "status": _PLAN_STATUS_READY}
            for i in range(n)
        ]

    def test_max_source_requests_in_report(self):
        plan = self._simple_plan(1)
        report = _build_source_budget_report(plan, [], 1)
        self.assertEqual(report["max_source_requests"], 1)

    def test_source_requests_planned_equals_plan_length(self):
        plan = self._simple_plan(2)
        report = _build_source_budget_report(plan, [], 2)
        self.assertEqual(report["source_requests_planned"], 2)

    def test_source_requests_attempted_counts_only_executed(self):
        plan = self._simple_plan(2)
        records = [
            _fake_exec_record(executed=True),
            _fake_exec_record(executed=False, status=_PLAN_STATUS_NOT_READY, response_id=None),
        ]
        report = _build_source_budget_report(plan, records, 2)
        self.assertEqual(report["source_requests_attempted"], 1)

    def test_source_responses_received_counts_non_none_response_id(self):
        plan = self._simple_plan(2)
        records = [
            _fake_exec_record(executed=True, response_id=42),
            _fake_exec_record(executed=True, response_id=None, failure_id=1),
        ]
        report = _build_source_budget_report(plan, records, 2)
        self.assertEqual(report["source_responses_received"], 1)

    def test_source_failures_counts_non_none_failure_id(self):
        plan = self._simple_plan(2)
        records = [
            _fake_exec_record(executed=True, response_id=None, failure_id=5),
            _fake_exec_record(executed=True, response_id=10, failure_id=None),
        ]
        report = _build_source_budget_report(plan, records, 2)
        self.assertEqual(report["source_failures"], 1)

    def test_source_failure_rate_zero_when_no_failures(self):
        plan = self._simple_plan(1)
        records = [_fake_exec_record(executed=True, response_id=1, failure_id=None)]
        report = _build_source_budget_report(plan, records, 1)
        self.assertEqual(report["source_failure_rate"], 0.0)

    def test_source_failure_rate_one_when_all_fail(self):
        plan = self._simple_plan(1)
        records = [_fake_exec_record(executed=True, response_id=None, failure_id=1)]
        report = _build_source_budget_report(plan, records, 1)
        self.assertEqual(report["source_failure_rate"], 1.0)

    def test_source_failure_rate_zero_when_no_attempts(self):
        plan = self._simple_plan(1)
        report = _build_source_budget_report(plan, [], 1)
        self.assertEqual(report["source_failure_rate"], 0.0)

    def test_channels_planned_matches_plan_request_kinds(self):
        plan = [
            {"plan_index": 0, "source_name": "geckoterminal", "request_kind": "geckoterminal_new_pool_discovery", "status": _PLAN_STATUS_READY},
            {"plan_index": 1, "source_name": "geckoterminal", "request_kind": "geckoterminal_trending_pool_reference", "status": _PLAN_STATUS_READY},
        ]
        report = _build_source_budget_report(plan, [], 2)
        self.assertEqual(report["source_channels_planned"], [
            "geckoterminal_new_pool_discovery",
            "geckoterminal_trending_pool_reference",
        ])

    def test_channels_sampled_includes_only_executed_items(self):
        plan = [
            {"plan_index": 0, "source_name": "pumpportal", "request_kind": "pumpfun_launch_stream", "status": _PLAN_STATUS_NOT_READY},
        ]
        records = [
            {**_fake_exec_record(executed=False, response_id=None, status=_PLAN_STATUS_NOT_READY), "request_kind": "pumpfun_launch_stream"},
        ]
        report = _build_source_budget_report(plan, records, 1)
        self.assertEqual(report["source_channels_sampled"], [])

    def test_channels_not_ready_lists_not_ready_items(self):
        plan = [
            {"plan_index": 0, "source_name": "pumpportal", "request_kind": "pumpfun_launch_stream", "status": _PLAN_STATUS_NOT_READY},
            {"plan_index": 1, "source_name": "pumpportal", "request_kind": "pumpfun_migration_stream", "status": _PLAN_STATUS_NOT_READY},
        ]
        report = _build_source_budget_report(plan, [], 2)
        self.assertIn("pumpfun_launch_stream", report["source_channels_not_ready"])
        self.assertIn("pumpfun_migration_stream", report["source_channels_not_ready"])

    def test_channels_failed_lists_failed_executed_items(self):
        plan = self._simple_plan(1)
        records = [_fake_exec_record(executed=True, response_id=None, failure_id=3)]
        report = _build_source_budget_report(plan, records, 1)
        self.assertIn("token_discovery", report["source_channels_failed"])

    def test_candidates_seen_by_source_aggregated_correctly(self):
        plan = self._simple_plan(1)
        records = [_fake_exec_record(executed=True, candidates_seen=15)]
        report = _build_source_budget_report(plan, records, 1)
        self.assertEqual(report["candidates_seen_by_source"].get("dexscreener", 0), 15)

    def test_candidates_persisted_by_source_channel(self):
        plan = self._simple_plan(1)
        records = [_fake_exec_record(executed=True, candidates_persisted=3)]
        report = _build_source_budget_report(plan, records, 1)
        self.assertEqual(report["candidates_persisted_by_source_channel"].get("token_discovery", 0), 3)

    def test_candidates_seen_by_source_channel_sums_across_same_channel(self):
        plan = [
            {"plan_index": 0, "source_name": "dexscreener", "request_kind": "token_discovery", "status": _PLAN_STATUS_READY},
            {"plan_index": 1, "source_name": "dexscreener", "request_kind": "token_discovery", "status": _PLAN_STATUS_READY},
        ]
        records = [
            _fake_exec_record(candidates_seen=5),
            _fake_exec_record(candidates_seen=8),
        ]
        report = _build_source_budget_report(plan, records, 2)
        self.assertEqual(report["candidates_seen_by_source_channel"].get("token_discovery", 0), 13)

    def test_report_has_all_required_keys(self):
        report = _build_source_budget_report(self._simple_plan(1), [], 1)
        required = {
            "max_source_requests",
            "source_requests_planned",
            "source_requests_attempted",
            "source_responses_received",
            "source_failures",
            "source_failure_rate",
            "source_channels_planned",
            "source_channels_sampled",
            "source_channels_not_ready",
            "source_channels_failed",
            "candidates_seen_by_source",
            "candidates_seen_by_source_channel",
            "candidates_persisted_by_source",
            "candidates_persisted_by_source_channel",
        }
        self.assertEqual(required, required & report.keys())


# ---------------------------------------------------------------------------
# D. _validate_discover_candidates_args — max_source_requests range
# ---------------------------------------------------------------------------

class TestValidateMaxSourceRequests(unittest.TestCase):

    def _base_args(self, **kwargs):
        d = {
            "operator_approved": True,
            "chain": "solana",
            "max_candidates": 10,
            "source_name": "dexscreener",
            "timeout_seconds": 5.0,
            "max_source_requests": 1,
        }
        d.update(kwargs)
        return argparse.Namespace(**d)

    def test_min_value_passes(self):
        _validate_discover_candidates_args(self._base_args(max_source_requests=_MAX_SOURCE_REQUESTS_MIN))

    def test_max_value_passes(self):
        _validate_discover_candidates_args(self._base_args(max_source_requests=_MAX_SOURCE_REQUESTS_MAX))

    def test_value_in_range_passes(self):
        _validate_discover_candidates_args(self._base_args(max_source_requests=5))

    def test_zero_raises_value_error(self):
        with self.assertRaises(ValueError):
            _validate_discover_candidates_args(self._base_args(max_source_requests=0))

    def test_above_max_raises_value_error(self):
        with self.assertRaises(ValueError):
            _validate_discover_candidates_args(self._base_args(max_source_requests=_MAX_SOURCE_REQUESTS_MAX + 1))

    def test_negative_raises_value_error(self):
        with self.assertRaises(ValueError):
            _validate_discover_candidates_args(self._base_args(max_source_requests=-1))

    def test_missing_attribute_uses_default_and_passes(self):
        """No max_source_requests attribute → getattr default → no error."""
        args = argparse.Namespace(
            operator_approved=True,
            chain="solana",
            max_candidates=10,
            source_name="dexscreener",
            timeout_seconds=5.0,
        )
        _validate_discover_candidates_args(args)

    def test_bool_true_raises_value_error(self):
        """bool is a subclass of int; True == 1 but should be rejected."""
        with self.assertRaises(ValueError):
            _validate_discover_candidates_args(self._base_args(max_source_requests=True))

    def test_string_raises_value_error(self):
        with self.assertRaises(ValueError):
            _validate_discover_candidates_args(self._base_args(max_source_requests="2"))


# ---------------------------------------------------------------------------
# E. Multi-request integration: geckoterminal with max_source_requests=2
# ---------------------------------------------------------------------------

class TestMultiRequestGeckoTerminal(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._db = _db_path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _gt_pool(self, pool_address: str, token_mint: str, *, symbol: str = "TST") -> dict:
        """Build a minimal GeckoTerminal pool fixture."""
        return {
            "id": f"solana_{pool_address}",
            "type": "pool",
            "attributes": {
                "address": pool_address,
                "base_token_price_usd": "0.0001",
                "reserve_in_usd": "9500.0",
                "volume_usd": {"m5": "3000.0", "h1": "12000.0", "h24": "60000.0"},
                "transactions": {"m5": {"buys": 25, "sells": 10}, "h24": {"buys": 400, "sells": 200}},
                "pool_created_at": "2024-01-01T00:00:00Z",
                "network": "solana",
                "dex_id": "raydium",
                "name": f"{symbol} / SOL",
                "price_change_percentage": {"m5": "-1.0", "h1": "-5.0", "h24": "-10.0"},
            },
            "relationships": {
                "base_token": {"data": {"id": f"solana_{token_mint}"}},
            },
        }

    def test_two_requests_aggregate_candidates_from_both(self):
        """With max_source_requests=2, candidates from both GT responses are aggregated."""
        pool_a = self._gt_pool(
            "PoolAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            symbol="AAA",
        )
        pool_b = self._gt_pool(
            "PoolBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "MintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            symbol="BBB",
        )
        transport_a = _gt_transport([pool_a])
        transport_b = _gt_transport([pool_b])

        args = _run_args(
            self._db,
            source_name="geckoterminal",
            request_kind="geckoterminal_new_pool_discovery",
            max_source_requests=2,
        )
        payload = build_discover_candidates_once_payload(args, transport=[transport_a, transport_b])
        self.assertEqual(payload["candidates_found"], 2)

    def test_source_budget_report_planned_two(self):
        pool_a = self._gt_pool(
            "PoolAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        )
        pool_b = self._gt_pool(
            "PoolBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "MintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        )
        args = _run_args(
            self._db,
            source_name="geckoterminal",
            request_kind="geckoterminal_new_pool_discovery",
            max_source_requests=2,
        )
        payload = build_discover_candidates_once_payload(
            args, transport=[_gt_transport([pool_a]), _gt_transport([pool_b])]
        )
        self.assertEqual(payload["source_budget_report"]["source_requests_planned"], 2)

    def test_source_budget_report_attempted_two(self):
        pool_a = self._gt_pool(
            "PoolAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        )
        pool_b = self._gt_pool(
            "PoolBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "MintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        )
        args = _run_args(
            self._db,
            source_name="geckoterminal",
            request_kind="geckoterminal_new_pool_discovery",
            max_source_requests=2,
        )
        payload = build_discover_candidates_once_payload(
            args, transport=[_gt_transport([pool_a]), _gt_transport([pool_b])]
        )
        self.assertEqual(payload["source_budget_report"]["source_requests_attempted"], 2)

    def test_source_budget_report_channels_sampled_has_two(self):
        pool_a = self._gt_pool(
            "PoolAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        )
        pool_b = self._gt_pool(
            "PoolBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "MintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        )
        args = _run_args(
            self._db,
            source_name="geckoterminal",
            request_kind="geckoterminal_new_pool_discovery",
            max_source_requests=2,
        )
        payload = build_discover_candidates_once_payload(
            args, transport=[_gt_transport([pool_a]), _gt_transport([pool_b])]
        )
        self.assertEqual(len(payload["source_budget_report"]["source_channels_sampled"]), 2)

    def test_within_response_integrity_report_present_and_merged(self):
        pool_a = self._gt_pool(
            "PoolAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        )
        pool_b = self._gt_pool(
            "PoolBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "MintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        )
        args = _run_args(
            self._db,
            source_name="geckoterminal",
            request_kind="geckoterminal_new_pool_discovery",
            max_source_requests=2,
        )
        payload = build_discover_candidates_once_payload(
            args, transport=[_gt_transport([pool_a]), _gt_transport([pool_b])]
        )
        wr = payload["within_response_integrity_report"]
        self.assertIn("within_response_duplicate_pair_count", wr)
        self.assertIn("within_response_duplicate_mint_count", wr)

    def test_candidate_stage_report_seen_total_across_both_responses(self):
        pool_a = self._gt_pool(
            "PoolAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        )
        pool_b = self._gt_pool(
            "PoolBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "MintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        )
        args = _run_args(
            self._db,
            source_name="geckoterminal",
            request_kind="geckoterminal_new_pool_discovery",
            max_source_requests=2,
        )
        payload = build_discover_candidates_once_payload(
            args, transport=[_gt_transport([pool_a]), _gt_transport([pool_b])]
        )
        self.assertEqual(payload["candidate_stage_report"]["candidates_seen_total"], 2)


# ---------------------------------------------------------------------------
# F. Backward compat: single-request path
# ---------------------------------------------------------------------------

class TestSingleRequestBackwardCompat(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._db = _db_path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _transport(self):
        return _dex_transport([_minimal_dex_pair()])

    def test_source_budget_report_key_present(self):
        args = _run_args(self._db, max_source_requests=1)
        payload = build_discover_candidates_once_payload(args, transport=self._transport())
        self.assertIn("source_budget_report", payload)

    def test_source_budget_report_planned_one(self):
        args = _run_args(self._db, max_source_requests=1)
        payload = build_discover_candidates_once_payload(args, transport=self._transport())
        self.assertEqual(payload["source_budget_report"]["source_requests_planned"], 1)

    def test_source_budget_report_attempted_one(self):
        args = _run_args(self._db, max_source_requests=1)
        payload = build_discover_candidates_once_payload(args, transport=self._transport())
        self.assertEqual(payload["source_budget_report"]["source_requests_attempted"], 1)

    def test_source_budget_report_channels_not_ready_is_empty(self):
        args = _run_args(self._db, max_source_requests=1)
        payload = build_discover_candidates_once_payload(args, transport=self._transport())
        self.assertEqual(payload["source_budget_report"]["source_channels_not_ready"], [])

    def test_pre_h5_fields_still_present(self):
        args = _run_args(self._db, max_source_requests=1)
        payload = build_discover_candidates_once_payload(args, transport=self._transport())
        expected_keys = {
            "command", "db_path", "operator_approved", "source_name",
            "request_kind", "query", "endpoint", "max_candidates",
            "source_status", "data_quality_label", "source_request_id",
            "source_response_id", "source_failure_id", "failure_type",
            "failure_message", "candidates_found", "candidates_inspected",
            "candidates_accepted", "candidates_rejected", "rejected_candidates",
            "candidate_stage_report", "age_activity_report",
            "field_completeness_report", "within_response_integrity_report",
            "source_channel", "source_channel_reason", "accepted_candidates",
            "discovery_results", "latest_discovery_rows",
        }
        missing = expected_keys - payload.keys()
        self.assertEqual(missing, set(), f"Missing payload keys: {missing}")

    def test_candidate_stage_report_h1_invariant_preserved(self):
        """All candidate_stage_report values must be int or 'NOT_MEASURED'."""
        args = _run_args(self._db, max_source_requests=1)
        payload = build_discover_candidates_once_payload(args, transport=self._transport())
        for key, val in payload["candidate_stage_report"].items():
            self.assertTrue(
                isinstance(val, int) or val == "NOT_MEASURED",
                f"candidate_stage_report[{key!r}] = {val!r} violates H.1 invariant",
            )

    def test_within_response_integrity_report_separate_from_candidate_stage_report(self):
        """H.4 invariant: WR report is a separate key, not nested in candidate_stage_report."""
        args = _run_args(self._db, max_source_requests=1)
        payload = build_discover_candidates_once_payload(args, transport=self._transport())
        self.assertNotIn("within_response_integrity_report", payload["candidate_stage_report"])
        self.assertIn("within_response_integrity_report", payload)

    def test_missing_max_source_requests_attr_does_not_break(self):
        """Args without max_source_requests attribute use default and succeed."""
        args = _run_args(self._db)
        del args.max_source_requests
        payload = build_discover_candidates_once_payload(args, transport=self._transport())
        self.assertEqual(payload["source_budget_report"]["max_source_requests"], _MAX_SOURCE_REQUESTS_DEFAULT)


# ---------------------------------------------------------------------------
# G. NOT_READY plan items are reported but not executed
# ---------------------------------------------------------------------------

class TestNotReadyItemsNotExecuted(unittest.TestCase):

    def test_pumpportal_plan_item_is_not_ready(self):
        plan = _build_source_request_plan("pumpportal", "pumpfun_launch_stream", 1)
        self.assertEqual(plan[0]["status"], _PLAN_STATUS_NOT_READY)

    def test_pumpswap_plan_item_is_not_ready(self):
        plan = _build_source_request_plan("pumpswap", "pumpswap_pool_confirmation", 1)
        self.assertEqual(plan[0]["status"], _PLAN_STATUS_NOT_READY)

    def test_not_ready_item_in_budget_report_channels_not_ready(self):
        plan = [
            {"plan_index": 0, "source_name": "pumpportal", "request_kind": "pumpfun_launch_stream", "status": _PLAN_STATUS_NOT_READY},
        ]
        records = [
            {**_fake_exec_record(executed=False, response_id=None, failure_id=None, status=_PLAN_STATUS_NOT_READY), "request_kind": "pumpfun_launch_stream"},
        ]
        report = _build_source_budget_report(plan, records, 1)
        self.assertIn("pumpfun_launch_stream", report["source_channels_not_ready"])
        self.assertEqual(report["source_requests_attempted"], 0)

    def test_geckoterminal_max1_channels_not_ready_is_empty(self):
        plan = _build_source_request_plan("geckoterminal", None, 1)
        self.assertFalse(any(p["status"] == _PLAN_STATUS_NOT_READY for p in plan))


# ---------------------------------------------------------------------------
# H. _aggregate_wr_reports
# ---------------------------------------------------------------------------

class TestAggregateWrReports(unittest.TestCase):

    def _empty_report(self) -> dict:
        return {
            "within_response_duplicate_pair_count": 0,
            "within_response_duplicate_mint_count": 0,
            "within_response_stnp_event_count": 0,
            "within_response_stnp_rejections": [],
            "within_response_duplicate_rejections": [],
        }

    def test_empty_list_gives_zero_counts(self):
        merged = _aggregate_wr_reports([])
        self.assertEqual(merged["within_response_duplicate_pair_count"], 0)
        self.assertEqual(merged["within_response_duplicate_mint_count"], 0)
        self.assertEqual(merged["within_response_stnp_event_count"], 0)

    def test_single_report_passes_through(self):
        r = self._empty_report()
        r["within_response_duplicate_pair_count"] = 3
        merged = _aggregate_wr_reports([r])
        self.assertEqual(merged["within_response_duplicate_pair_count"], 3)

    def test_two_reports_counts_are_summed(self):
        r1 = self._empty_report()
        r1["within_response_duplicate_pair_count"] = 2
        r2 = self._empty_report()
        r2["within_response_duplicate_pair_count"] = 5
        merged = _aggregate_wr_reports([r1, r2])
        self.assertEqual(merged["within_response_duplicate_pair_count"], 7)

    def test_stnp_rejection_lists_are_concatenated(self):
        r1 = self._empty_report()
        r1["within_response_stnp_rejections"] = [{"pair_address": "A"}]
        r2 = self._empty_report()
        r2["within_response_stnp_rejections"] = [{"pair_address": "B"}]
        merged = _aggregate_wr_reports([r1, r2])
        self.assertEqual(len(merged["within_response_stnp_rejections"]), 2)

    def test_duplicate_rejection_lists_are_concatenated(self):
        r1 = self._empty_report()
        r1["within_response_duplicate_rejections"] = [{"pair_address": "X"}]
        r2 = self._empty_report()
        r2["within_response_duplicate_rejections"] = [{"pair_address": "Y"}, {"pair_address": "Z"}]
        merged = _aggregate_wr_reports([r1, r2])
        self.assertEqual(len(merged["within_response_duplicate_rejections"]), 3)

    def test_all_count_keys_summed(self):
        r1 = self._empty_report()
        r1["within_response_duplicate_pair_count"] = 1
        r1["within_response_duplicate_mint_count"] = 2
        r1["within_response_stnp_event_count"] = 3
        r2 = self._empty_report()
        r2["within_response_duplicate_pair_count"] = 4
        r2["within_response_duplicate_mint_count"] = 5
        r2["within_response_stnp_event_count"] = 6
        merged = _aggregate_wr_reports([r1, r2])
        self.assertEqual(merged["within_response_duplicate_pair_count"], 5)
        self.assertEqual(merged["within_response_duplicate_mint_count"], 7)
        self.assertEqual(merged["within_response_stnp_event_count"], 9)

    def test_original_reports_not_mutated(self):
        r1 = self._empty_report()
        r1["within_response_stnp_rejections"] = [{"pair_address": "A"}]
        _aggregate_wr_reports([r1])
        self.assertEqual(len(r1["within_response_stnp_rejections"]), 1)


if __name__ == "__main__":
    unittest.main()

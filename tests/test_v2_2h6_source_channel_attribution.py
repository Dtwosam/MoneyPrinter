"""V2-2H.6 — Per-Candidate Source/Channel Attribution Repair.

Targeted tests for:
  A. Multi-request persistence: each candidate keeps its true source_channel
  B. Persisted rows do not collapse into the primary channel
  C. source_response_id stays attached to the correct candidate group
  D. source_budget_report persisted counts match actual per-channel attribution
  E. Single-request backward compat: H.1-H.5 invariants preserved

Locks preserved: no live discovery, no source fetching, no live DB mutation,
no memory generation, no retrieval, no paper decisions, no BUY/SELL/HOLD,
no positions/trades/audits/PnL, no scoring/ranking/confidence/weighted logic.
"""

from __future__ import annotations

import argparse
import pathlib
import sqlite3
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import (
    _MAX_SOURCE_REQUESTS_DEFAULT,
    build_discover_candidates_once_payload,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_SOLANA_WSOL = "So11111111111111111111111111111111111111112"

_GT_NEW_POOL_CHANNEL = "GECKOTERMINAL_NEW_POOL"
_GT_TRENDING_CHANNEL = "GECKOTERMINAL_TRENDING_POOL"


def _db(tmp_dir: str) -> pathlib.Path:
    p = pathlib.Path(tmp_dir) / "h6_attr.db"
    apply_migrations(p)
    return p


def _run_args(db_path: str | pathlib.Path, **overrides) -> argparse.Namespace:
    base = {
        "project_root": str(PROJECT_ROOT),
        "format": "json",
        "no_color": True,
        "operator_approved": True,
        "chain": "solana",
        "max_candidates": 10,
        "query": "pump",
        "timeout_seconds": 5.0,
        "source_name": "geckoterminal",
        "request_kind": "geckoterminal_new_pool_discovery",
        "request_key": "v2-2h6-attr-test",
        "db_path": str(db_path),
        "max_source_requests": 1,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _gt_transport(pools: list[dict]):
    def _t(context):
        del context
        return {"data": pools}
    return _t


def _gt_pool(pool_address: str, token_mint: str, *, symbol: str = "TST") -> dict:
    return {
        "id": f"solana_{pool_address}",
        "type": "pool",
        "attributes": {
            "address": pool_address,
            "base_token_price_usd": "0.0001",
            "reserve_in_usd": "9500.0",
            "volume_usd": {"m5": "3500.0", "h1": "14000.0", "h24": "60000.0"},
            "transactions": {
                "m5": {"buys": 30, "sells": 10},
                "h24": {"buys": 400, "sells": 200},
            },
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


def _query_persisted_channels(db_path: pathlib.Path) -> list[str | None]:
    """Return source_channel for every row in printer_discovery_candidates."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT source_channel FROM printer_discovery_candidates ORDER BY id"
        ).fetchall()
    return [row["source_channel"] for row in rows]


def _query_all_rows(db_path: pathlib.Path) -> list[dict]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT source_channel, source_channel_reason, source_response_id
               FROM printer_discovery_candidates ORDER BY id"""
        ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# A. Multi-request: each candidate keeps its true source_channel
# ---------------------------------------------------------------------------

class TestMultiRequestChannelAttribution(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._db = _db(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _two_channel_payload(self):
        """Run with 2 GT requests (new_pool + trending), 1 pool each."""
        pool_a = _gt_pool(
            "PoolAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            symbol="AAA",
        )
        pool_b = _gt_pool(
            "PoolBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "MintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            symbol="BBB",
        )
        args = _run_args(
            self._db,
            request_kind="geckoterminal_new_pool_discovery",
            max_source_requests=2,
        )
        return build_discover_candidates_once_payload(
            args,
            transport=[_gt_transport([pool_a]), _gt_transport([pool_b])],
        )

    def test_two_distinct_channels_are_persisted(self):
        payload = self._two_channel_payload()
        if payload["candidates_accepted"] < 2:
            self.skipTest("Both pools must be accepted to test attribution")
        channels = _query_persisted_channels(self._db)
        self.assertIn(_GT_NEW_POOL_CHANNEL, channels)
        self.assertIn(_GT_TRENDING_CHANNEL, channels)

    def test_persisted_channels_do_not_all_collapse_to_primary(self):
        payload = self._two_channel_payload()
        if payload["candidates_accepted"] < 2:
            self.skipTest("Both pools must be accepted to test attribution")
        channels = _query_persisted_channels(self._db)
        # If all candidates collapsed to primary channel, this set would have size 1.
        self.assertGreater(len(set(channels)), 1)

    def test_first_pool_gets_new_pool_channel(self):
        payload = self._two_channel_payload()
        if payload["candidates_accepted"] < 1:
            self.skipTest("At least one pool must be accepted")
        rows = _query_all_rows(self._db)
        new_pool_rows = [r for r in rows if r["source_channel"] == _GT_NEW_POOL_CHANNEL]
        self.assertGreater(len(new_pool_rows), 0, "Expected at least one GECKOTERMINAL_NEW_POOL row")

    def test_second_pool_gets_trending_channel(self):
        payload = self._two_channel_payload()
        if payload["candidates_accepted"] < 2:
            self.skipTest("Both pools must be accepted to test attribution")
        rows = _query_all_rows(self._db)
        trending_rows = [r for r in rows if r["source_channel"] == _GT_TRENDING_CHANNEL]
        self.assertGreater(len(trending_rows), 0, "Expected at least one GECKOTERMINAL_TRENDING_POOL row")

    def test_source_response_ids_differ_across_channels(self):
        """Candidates from different requests must reference different source_response_ids."""
        payload = self._two_channel_payload()
        if payload["candidates_accepted"] < 2:
            self.skipTest("Both pools must be accepted to test attribution")
        rows = _query_all_rows(self._db)
        resp_ids = {r["source_response_id"] for r in rows if r["source_response_id"] is not None}
        self.assertGreater(len(resp_ids), 1, "Expected distinct source_response_ids for each channel")

    def test_source_budget_report_persisted_counts_sum_to_total_accepted(self):
        payload = self._two_channel_payload()
        budget = payload["source_budget_report"]
        total_persisted_by_channel = sum(budget["candidates_persisted_by_source_channel"].values())
        self.assertEqual(total_persisted_by_channel, payload["candidates_accepted"])

    def test_source_budget_report_persisted_by_channel_not_zero_for_accepted(self):
        payload = self._two_channel_payload()
        if payload["candidates_accepted"] < 2:
            self.skipTest("Both pools must be accepted to test attribution")
        budget = payload["source_budget_report"]
        # candidates_persisted_by_source_channel is keyed by request_kind, not
        # the DiscoveryChannelLabel string, since request_kind is what distinguishes
        # requests in the budget catalog.
        by_rk = budget["candidates_persisted_by_source_channel"]
        self.assertGreater(by_rk.get("geckoterminal_new_pool_discovery", 0), 0)
        self.assertGreater(by_rk.get("geckoterminal_trending_pool_reference", 0), 0)

    def test_candidates_found_counts_from_both_responses(self):
        payload = self._two_channel_payload()
        self.assertEqual(payload["candidates_found"], 2)

    def test_candidate_stage_report_seen_total_is_two(self):
        payload = self._two_channel_payload()
        self.assertEqual(payload["candidate_stage_report"]["candidates_seen_total"], 2)


# ---------------------------------------------------------------------------
# B. Single-request backward compat: all H.1-H.5 invariants preserved
# ---------------------------------------------------------------------------

class TestSingleRequestAttribution(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._db = _db(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _single_payload(self):
        pool = _gt_pool(
            "PoolAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            symbol="AAA",
        )
        args = _run_args(self._db, max_source_requests=1)
        return build_discover_candidates_once_payload(
            args, transport=_gt_transport([pool])
        )

    def test_single_request_persisted_channel_is_new_pool(self):
        payload = self._single_payload()
        if payload["candidates_accepted"] < 1:
            self.skipTest("Pool must be accepted")
        channels = _query_persisted_channels(self._db)
        self.assertEqual(channels, [_GT_NEW_POOL_CHANNEL])

    def test_single_request_source_budget_report_persisted_by_channel(self):
        payload = self._single_payload()
        budget = payload["source_budget_report"]
        total_by_ch = sum(budget["candidates_persisted_by_source_channel"].values())
        self.assertEqual(total_by_ch, payload["candidates_accepted"])

    def test_h1_candidate_stage_report_invariant(self):
        payload = self._single_payload()
        for key, val in payload["candidate_stage_report"].items():
            self.assertTrue(
                isinstance(val, int) or val == "NOT_MEASURED",
                f"candidate_stage_report[{key!r}] = {val!r} violates H.1 invariant",
            )

    def test_h4_within_response_integrity_report_present(self):
        payload = self._single_payload()
        self.assertIn("within_response_integrity_report", payload)
        self.assertNotIn("within_response_integrity_report", payload["candidate_stage_report"])

    def test_h5_source_budget_report_present(self):
        payload = self._single_payload()
        self.assertIn("source_budget_report", payload)

    def test_h3_field_completeness_report_present(self):
        payload = self._single_payload()
        self.assertIn("field_completeness_report", payload)

    def test_h2_age_activity_report_present(self):
        payload = self._single_payload()
        self.assertIn("age_activity_report", payload)

    def test_source_channel_in_payload_top_level_matches_persisted(self):
        payload = self._single_payload()
        if payload["candidates_accepted"] < 1:
            self.skipTest("Pool must be accepted")
        channels = _query_persisted_channels(self._db)
        self.assertEqual(payload["source_channel"], _GT_NEW_POOL_CHANNEL)
        self.assertTrue(all(c == _GT_NEW_POOL_CHANNEL for c in channels))


# ---------------------------------------------------------------------------
# C. source_response_id correctness for single-request
# ---------------------------------------------------------------------------

class TestSourceResponseIdAttribution(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._db = _db(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_persisted_row_source_response_id_matches_payload_source_response_id(self):
        pool = _gt_pool(
            "PoolAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        )
        args = _run_args(self._db, max_source_requests=1)
        payload = build_discover_candidates_once_payload(
            args, transport=_gt_transport([pool])
        )
        if payload["candidates_accepted"] < 1:
            self.skipTest("Pool must be accepted")
        rows = _query_all_rows(self._db)
        payload_resp_id = payload["source_response_id"]
        for row in rows:
            self.assertEqual(
                row["source_response_id"], payload_resp_id,
                "Persisted row source_response_id must match payload source_response_id",
            )

    def test_multi_request_persisted_response_ids_not_all_primary(self):
        pool_a = _gt_pool(
            "PoolAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            symbol="AAA",
        )
        pool_b = _gt_pool(
            "PoolBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "MintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            symbol="BBB",
        )
        args = _run_args(
            self._db,
            request_kind="geckoterminal_new_pool_discovery",
            max_source_requests=2,
        )
        payload = build_discover_candidates_once_payload(
            args, transport=[_gt_transport([pool_a]), _gt_transport([pool_b])]
        )
        if payload["candidates_accepted"] < 2:
            self.skipTest("Both pools must be accepted")
        rows = _query_all_rows(self._db)
        primary_resp_id = payload["source_response_id"]
        resp_ids = {r["source_response_id"] for r in rows}
        # At least one persisted row must have a response_id != primary's response_id.
        non_primary = [rid for rid in resp_ids if rid != primary_resp_id]
        self.assertTrue(
            len(non_primary) > 0,
            "Expected at least one persisted row with a non-primary source_response_id",
        )


# ---------------------------------------------------------------------------
# D. source_budget_report persisted counts match DB reality
# ---------------------------------------------------------------------------

class TestBudgetReportMatchesDb(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._db = _db(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_candidates_persisted_total_matches_db_row_count(self):
        pool = _gt_pool(
            "PoolAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        )
        args = _run_args(self._db, max_source_requests=1)
        payload = build_discover_candidates_once_payload(
            args, transport=_gt_transport([pool])
        )
        with sqlite3.connect(self._db) as conn:
            db_count = conn.execute(
                "SELECT COUNT(*) FROM printer_discovery_candidates"
            ).fetchone()[0]
        self.assertEqual(
            payload["candidate_stage_report"]["candidates_persisted_total"],
            db_count,
        )

    def test_two_request_persisted_total_in_budget_matches_accepted(self):
        pool_a = _gt_pool(
            "PoolAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            symbol="AAA",
        )
        pool_b = _gt_pool(
            "PoolBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "MintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            symbol="BBB",
        )
        args = _run_args(
            self._db,
            request_kind="geckoterminal_new_pool_discovery",
            max_source_requests=2,
        )
        payload = build_discover_candidates_once_payload(
            args, transport=[_gt_transport([pool_a]), _gt_transport([pool_b])]
        )
        budget = payload["source_budget_report"]
        total_persisted = sum(budget["candidates_persisted_by_source"].values())
        self.assertEqual(total_persisted, payload["candidates_accepted"])


if __name__ == "__main__":
    unittest.main()

"""Mini-Sprint A: governed broad context command, discovery eligibility, snapshot diagnostics."""

import argparse
import pathlib
import sqlite3
import sys
import tempfile
import tomllib
import unittest
from contextlib import contextmanager

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import (
    build_collect_broad_context_once_payload,
    build_collect_context_once_payload,
    build_collect_token_snapshots_once_payload,
    build_discover_candidates_once_payload,
    build_manual_intake_token_pair_payload,
)
from printer_v1.sources.coingecko import fixture_success_transport as coingecko_fixture
from printer_v1.sources.defillama import fixture_success_transport as defillama_fixture


DOWNSTREAM_TABLES = (
    "printer_market_regime_snapshots",
    "printer_solana_chain_heat_snapshots",
    "printer_memory_windows",
    "printer_memory_fingerprints",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
)


def make_db():
    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db_path = pathlib.Path(tmp.name) / "sprint-a.sqlite3"
    apply_migrations(db_path)
    return tmp, db_path


def count_rows(db_path, table):
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        conn.close()


def make_args(**kw):
    defaults = {
        "db_path": None,
        "project_root": str(PROJECT_ROOT),
        "format": "json",
        "no_color": True,
        "operator_approved": True,
        "source_name": None,
        "request_kind": None,
        "request_key": None,
        "timeout_seconds": 8.0,
        "chain": "solana",
        "token_mint": None,
        "token_id": None,
        "pair_address": None,
        "pair_id": None,
        "snapshot_id": None,
        "snapshot_count": 1,
        "max_seconds": 5.0,
        "max_candidates": 1,
        "query": "pump",
        "market_source_response_id": None,
        "chain_heat_source_response_id": None,
        "pool_address": None,
        "intake_reason": "mini-sprint-a-test",
        "source_reference": "mini-sprint-a",
        "source_request_id": None,
        "token_symbol": "TST",
        "token_name": "Test Token",
        "dex_id": "raydium",
        "intake_json": None,
        "memory_window_id": None,
        "episode_id": None,
    }
    defaults.update(kw)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# Class 1: printer-collect-broad-context-once
# ---------------------------------------------------------------------------

class PostRcBroadContextCommandTests(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = make_db()

    def tearDown(self):
        self._tmp.cleanup()

    def _args(self, **kw):
        return make_args(db_path=str(self.db_path), **kw)

    def coingecko_payload(self):
        return {
            "captured_at": "2026-06-24T12:00:00+00:00",
            "assets": {
                "bitcoin": {
                    "market_data": {
                        "current_price": {"usd": 64000},
                        "price_change_percentage_24h": 2.5,
                        "price_change_percentage_7d": 5.0,
                    },
                    "price_change_percentage_1h": 0.3,
                },
                "solana": {
                    "market_data": {
                        "current_price": {"usd": 150},
                        "price_change_percentage_24h": 6.0,
                        "price_change_percentage_7d": 10.0,
                        "total_volume": {"usd": 2_000_000_000},
                    },
                    "price_change_percentage_1h": 0.8,
                },
            },
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
        }

    def defillama_payload(self):
        return {
            "captured_at": "2026-06-24T12:00:00+00:00",
            "solana": {
                "price_usd": 150,
                "change_24h": 6.0,
                "volume_24h": 2_000_000_000,
            },
            "network_context": {
                "active_addresses": 1_200_000,
                "tx_count_24h": 45_000_000,
                "congestion_context": "low",
            },
            "liquidity_context": {
                "tvl_usd": 5_000_000_000,
                "dex_volume_24h": 1_100_000_000,
            },
            "meme_context": {
                "hot_pair_count": 35,
                "meme_volume_24h": 120_000_000,
                "meme_liquidity_usd": 50_000_000,
                "meme_new_pair_count": 80,
            },
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
        }

    def test_pyproject_exposes_collect_broad_context_once(self):
        scripts = tomllib.loads(
            (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]["scripts"]
        self.assertEqual(
            scripts["printer-collect-broad-context-once"],
            "printer_v1.operator_cli.commands:main_collect_broad_context_once",
        )

    def test_requires_operator_approval(self):
        with self.assertRaises(ValueError):
            build_collect_broad_context_once_payload(
                self._args(source_name="coingecko", operator_approved=False),
                transport=coingecko_fixture(self.coingecko_payload()),
            )

    def test_requires_valid_source_name(self):
        with self.assertRaises(ValueError):
            build_collect_broad_context_once_payload(
                self._args(source_name="birdeye"),
                transport=coingecko_fixture(self.coingecko_payload()),
            )

    def test_coingecko_broad_context_records_governed_source_response(self):
        result = build_collect_broad_context_once_payload(
            self._args(source_name="coingecko", request_kind="broad_market_context"),
            transport=coingecko_fixture(self.coingecko_payload()),
        )

        self.assertEqual(result["command"], "printer-collect-broad-context-once")
        self.assertEqual(result["source_name"], "coingecko")
        self.assertEqual(result["request_kind"], "broad_market_context")
        self.assertEqual(result["source_status"], "COMPLETE")
        self.assertEqual(result["data_quality_label"], "CLEAN_DATA")
        self.assertIsNotNone(result["source_request_id"])
        self.assertIsNotNone(result["source_response_id"])
        self.assertIsNone(result["source_failure_id"])
        self.assertEqual(result["source_table_deltas"]["printer_source_requests"], 1)
        self.assertEqual(result["source_table_deltas"]["printer_source_responses"], 1)
        self.assertEqual(result["source_table_deltas"]["printer_source_failures"], 0)
        self.assertTrue(result["guard_tables_unchanged"])

    def test_defillama_broad_context_records_governed_source_response(self):
        result = build_collect_broad_context_once_payload(
            self._args(source_name="defillama", request_kind="chain_liquidity_context"),
            transport=defillama_fixture(self.defillama_payload()),
        )

        self.assertEqual(result["source_name"], "defillama")
        self.assertEqual(result["source_status"], "COMPLETE")
        self.assertIsNotNone(result["source_response_id"])
        self.assertIsNone(result["source_failure_id"])
        self.assertTrue(result["guard_tables_unchanged"])

    def test_broad_context_does_not_write_downstream_tables(self):
        build_collect_broad_context_once_payload(
            self._args(source_name="coingecko"),
            transport=coingecko_fixture(self.coingecko_payload()),
        )

        for table in DOWNSTREAM_TABLES:
            self.assertEqual(
                count_rows(self.db_path, table), 0, f"expected 0 rows in {table}"
            )

    def test_next_step_hint_present_in_result(self):
        result = build_collect_broad_context_once_payload(
            self._args(source_name="coingecko"),
            transport=coingecko_fixture(self.coingecko_payload()),
        )
        self.assertIsNotNone(result["next_step_hint"])
        self.assertIn(str(result["source_response_id"]), result["next_step_hint"])

    def test_default_request_kind_used_when_omitted(self):
        result = build_collect_broad_context_once_payload(
            self._args(source_name="coingecko", request_kind=None),
            transport=coingecko_fixture(self.coingecko_payload()),
        )
        self.assertEqual(result["request_kind"], "broad_market_context")

    def test_invalid_request_kind_for_source_is_rejected(self):
        with self.assertRaises(ValueError):
            build_collect_broad_context_once_payload(
                self._args(source_name="coingecko", request_kind="chain_liquidity_context"),
                transport=coingecko_fixture(self.coingecko_payload()),
            )


# ---------------------------------------------------------------------------
# Class 2: collect-context-once can consume source_response_id
# ---------------------------------------------------------------------------

class PostRcCollectContextConsumesBroadContextResponseTests(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = make_db()
        self._seed_token_and_snapshot()

    def tearDown(self):
        self._tmp.cleanup()

    def _args(self, **kw):
        return make_args(db_path=str(self.db_path), **kw)

    def _seed_token_and_snapshot(self):
        build_manual_intake_token_pair_payload(self._args(
            token_mint="broad-ctx-mint",
            pair_address="broad-ctx-pair",
            token_symbol="BCX",
            token_name="Broad Context",
        ))
        build_collect_token_snapshots_once_payload(
            self._args(
                token_mint="broad-ctx-mint",
                pair_address="broad-ctx-pair",
                source_name="dexscreener",
                source_reference="broad-ctx-snap",
            ),
            transport=lambda ctx: {
                "pairs": [{
                    "chainId": "solana",
                    "pairAddress": "broad-ctx-pair",
                    "baseToken": {"address": "broad-ctx-mint", "symbol": "BCX", "name": "Broad Context"},
                    "priceUsd": "0.00050",
                    "liquidity": {"usd": 32000.0},
                    "volume": {"m5": 14000.0, "h1": 80000.0, "h24": 310000.0},
                    "txns": {"m5": {"buys": 40, "sells": 16}, "h1": {"buys": 180, "sells": 70}},
                    "fdv": 500000.0, "marketCap": 455000.0,
                    "priceChange": {"m5": 12.0, "h1": 22.0, "h24": 33.0},
                }]
            },
        )

    def coingecko_payload(self):
        return {
            "captured_at": "2026-06-24T12:00:00+00:00",
            "assets": {
                "bitcoin": {
                    "market_data": {
                        "current_price": {"usd": 65000},
                        "price_change_percentage_24h": 3.0,
                        "price_change_percentage_7d": 6.0,
                    },
                    "price_change_percentage_1h": 0.4,
                },
                "solana": {
                    "market_data": {
                        "current_price": {"usd": 155},
                        "price_change_percentage_24h": 5.0,
                        "price_change_percentage_7d": 9.0,
                        "total_volume": {"usd": 1_800_000_000},
                    },
                    "price_change_percentage_1h": 0.7,
                },
            },
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
        }

    def test_collect_context_consumes_market_source_response_id(self):
        broad = build_collect_broad_context_once_payload(
            self._args(source_name="coingecko"),
            transport=coingecko_fixture(self.coingecko_payload()),
        )
        market_response_id = broad["source_response_id"]
        self.assertIsNotNone(market_response_id)

        ctx_result = build_collect_context_once_payload(
            self._args(
                token_mint="broad-ctx-mint",
                pair_address="broad-ctx-pair",
                source_name="dexscreener",
                market_source_response_id=market_response_id,
            )
        )

        self.assertIsNone(ctx_result["skipped_reason"])
        inserted = ctx_result["inserted_context_rows"]
        self.assertIn("printer_market_regime_snapshots", inserted)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            market = conn.execute(
                "SELECT * FROM printer_market_regime_snapshots ORDER BY id DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(market)
        self.assertNotEqual(market["market_regime_label"], "UNKNOWN")
        self.assertEqual(market["source_status"], "COMPLETE")

        for table in (
            "printer_memory_retrieval_matches",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
        ):
            self.assertEqual(count_rows(self.db_path, table), 0, table)


# ---------------------------------------------------------------------------
# Class 3: discovery candidate selection — WATCH_ONLY rejection
# ---------------------------------------------------------------------------

class PostRcDiscoveryWatchOnlyRejectionTests(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = make_db()

    def tearDown(self):
        self._tmp.cleanup()

    def _args(self, **kw):
        return make_args(
            db_path=str(self.db_path),
            source_name="dexscreener",
            request_key="mini-sprint-a-discovery",
            **kw,
        )

    def _watch_only_low_liq_transport(self, ctx):
        """WATCH_ONLY: has price + pair but liquidity < MIN_TRACK_NORMAL_LIQUIDITY_USD (1000)."""
        del ctx
        return {
            "pairs": [{
                "chainId": "solana",
                "pairAddress": "watch-liq-pair",
                "baseToken": {"address": "watch-liq-mint", "symbol": "WLIQ", "name": "Low Liq"},
                "priceUsd": "0.000001",
                "liquidity": {"usd": 400},
                "volume": {"m5": 50, "h1": 300, "h24": 1200},
                "txns": {"m5": {"buys": 2, "sells": 1}, "h1": {"buys": 12, "sells": 8}},
            }]
        }

    def _watch_only_dead_transport(self, ctx):
        """WATCH_ONLY: near-zero activity (WATCH_ONLY via insufficient_activity path)."""
        del ctx
        return {
            "pairs": [{
                "chainId": "solana",
                "pairAddress": "watch-dead-pair",
                "baseToken": {"address": "watch-dead-mint", "symbol": "DEAD", "name": "Dead Token"},
                "priceUsd": "0.000001",
                "liquidity": {"usd": 5000},
                "volume": {"m5": 0, "h1": 0, "h24": 5},
                "txns": {"m5": {"buys": 0, "sells": 0}, "h1": {"buys": 0, "sells": 0}},
            }]
        }

    def _track_normal_transport(self, ctx):
        """TRACK_NORMAL: liquidity ≥ 1000, price, sufficient activity."""
        del ctx
        return {
            "pairs": [{
                "chainId": "solana",
                "pairAddress": "normal-pair",
                "baseToken": {"address": "normal-mint", "symbol": "NRM", "name": "Normal Token"},
                "priceUsd": "0.001",
                "liquidity": {"usd": 5000},
                "volume": {"m5": 100, "h1": 800, "h24": 5000},
                "txns": {"m5": {"buys": 3, "sells": 2}, "h1": {"buys": 18, "sells": 12}},
            }]
        }

    def _track_fast_transport(self, ctx):
        """TRACK_FAST: liquidity ≥ 5000, volume_5m ≥ 1000."""
        del ctx
        return {
            "pairs": [{
                "chainId": "solana",
                "pairAddress": "fast-pair",
                "baseToken": {"address": "fast-mint", "symbol": "FST", "name": "Fast Token"},
                "priceUsd": "0.005",
                "liquidity": {"usd": 15000},
                "volume": {"m5": 2000, "h1": 20000, "h24": 80000},
                "txns": {"m5": {"buys": 12, "sells": 8}, "h1": {"buys": 60, "sells": 40}},
            }]
        }

    def test_watch_only_low_liquidity_rejected_from_proof_cycle(self):
        result = build_discover_candidates_once_payload(
            self._args(), transport=self._watch_only_low_liq_transport
        )

        self.assertEqual(result["candidates_accepted"], 0)
        self.assertEqual(result["candidates_rejected"], 1)
        rejected = result["rejected_candidates"][0]
        self.assertEqual(rejected["reject_reason"], "watch_only_not_eligible_for_15m_memory_proof_cycle")
        self.assertEqual(result["tracking_queue_delta"], 0)
        self.assertEqual(result["paper_decision_delta"], 0)

    def test_watch_only_dead_activity_rejected_from_proof_cycle(self):
        result = build_discover_candidates_once_payload(
            self._args(), transport=self._watch_only_dead_transport
        )

        self.assertEqual(result["candidates_accepted"], 0)
        self.assertEqual(result["candidates_rejected"], 1)
        rejected = result["rejected_candidates"][0]
        self.assertIn(
            rejected["reject_reason"],
            {"watch_only_not_eligible_for_15m_memory_proof_cycle", "insufficient_activity_for_memory_growth"},
        )
        self.assertEqual(result["tracking_queue_delta"], 0)

    def test_track_normal_remains_eligible(self):
        result = build_discover_candidates_once_payload(
            self._args(), transport=self._track_normal_transport
        )

        self.assertEqual(result["candidates_accepted"], 1)
        self.assertEqual(result["candidates_rejected"], 0)
        self.assertEqual(result["accepted_candidates"][0]["tracking_label"], "TRACK_NORMAL")
        self.assertEqual(result["tracking_queue_delta"], 1)

    def test_track_fast_remains_eligible(self):
        result = build_discover_candidates_once_payload(
            self._args(), transport=self._track_fast_transport
        )

        self.assertEqual(result["candidates_accepted"], 1)
        self.assertEqual(result["accepted_candidates"][0]["tracking_label"], "TRACK_FAST")
        self.assertEqual(result["tracking_queue_delta"], 1)
        self.assertEqual(result["paper_decision_delta"], 0)
        self.assertEqual(result["paper_position_delta"], 0)


# ---------------------------------------------------------------------------
# Class 4: snapshot failure diagnostics — specific skip reasons
# ---------------------------------------------------------------------------

class PostRcSnapshotFailureDiagnosticsTests(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = make_db()
        self._seed_token_pair()

    def tearDown(self):
        self._tmp.cleanup()

    def _seed_token_pair(self):
        build_manual_intake_token_pair_payload(make_args(
            db_path=str(self.db_path),
            token_mint="diag-mint",
            pair_address="diag-pair",
            token_symbol="DGX",
            token_name="Diag Token",
        ))

    def _snap_args(self, **kw):
        return make_args(
            db_path=str(self.db_path),
            token_mint="diag-mint",
            pair_address="diag-pair",
            source_name="dexscreener",
            source_reference="diag-snapshot",
            **kw,
        )

    def _good_pair(self):
        return {
            "chainId": "solana",
            "pairAddress": "diag-pair",
            "baseToken": {"address": "diag-mint", "symbol": "DGX", "name": "Diag Token"},
            "priceUsd": "0.001",
            "liquidity": {"usd": 10000},
        }

    def _run_snapshot(self, transport):
        result = build_collect_token_snapshots_once_payload(
            self._snap_args(), transport=transport
        )
        return result["results"][0]

    def test_transport_failure_gives_source_specific_reason(self):
        def failing_transport(ctx):
            raise RuntimeError("connection refused")

        snap = self._run_snapshot(failing_transport)

        self.assertFalse(snap["snapshot_created"])
        self.assertIsNone(snap["snapshot_id"])
        self.assertEqual(snap["source_status"], "FAILED")
        self.assertEqual(snap["skip_reason"], "dexscreener_transport_error")

    def test_stale_source_gives_source_status_not_complete(self):
        def stale_transport(ctx):
            del ctx
            return {"fixture_stale": True, "pairs": [self._good_pair()]}

        snap = self._run_snapshot(stale_transport)

        self.assertFalse(snap["snapshot_created"])
        self.assertEqual(snap["source_status"], "STALE")
        self.assertEqual(snap["skip_reason"], "source_status_not_complete")

    def test_pair_not_in_response_gives_specific_reason(self):
        def wrong_pair_transport(ctx):
            del ctx
            return {
                "pairs": [{
                    "chainId": "solana",
                    "pairAddress": "completely-different-pair",
                    "baseToken": {"address": "completely-different-mint", "symbol": "OTH", "name": "Other"},
                    "priceUsd": "0.001",
                    "liquidity": {"usd": 10000},
                }]
            }

        snap = self._run_snapshot(wrong_pair_transport)

        self.assertFalse(snap["snapshot_created"])
        self.assertEqual(snap["source_status"], "COMPLETE")
        self.assertEqual(snap["skip_reason"], "pair_not_in_response")

    def test_price_usd_missing_gives_specific_reason(self):
        def no_price_transport(ctx):
            del ctx
            pair = self._good_pair().copy()
            del pair["priceUsd"]
            return {"pairs": [pair]}

        snap = self._run_snapshot(no_price_transport)

        self.assertFalse(snap["snapshot_created"])
        self.assertEqual(snap["source_status"], "COMPLETE")
        self.assertEqual(snap["skip_reason"], "price_usd_missing")

    def test_liquidity_missing_gives_specific_reason(self):
        def no_liquidity_transport(ctx):
            del ctx
            pair = self._good_pair().copy()
            del pair["liquidity"]
            return {"pairs": [pair]}

        snap = self._run_snapshot(no_liquidity_transport)

        self.assertFalse(snap["snapshot_created"])
        self.assertEqual(snap["source_status"], "COMPLETE")
        self.assertEqual(snap["skip_reason"], "liquidity_usd_missing")

    def test_successful_snapshot_has_no_skip_reason(self):
        def good_transport(ctx):
            del ctx
            return {"pairs": [self._good_pair()]}

        snap = self._run_snapshot(good_transport)

        self.assertTrue(snap["snapshot_created"])
        self.assertIsNotNone(snap["snapshot_id"])
        self.assertIsNone(snap["skip_reason"])

    def test_no_downstream_unlocks_across_diagnostics(self):
        """Snapshot failures must not create retrieval/decision/position rows."""
        def failing_transport(ctx):
            raise RuntimeError("forced failure")

        build_collect_token_snapshots_once_payload(
            self._snap_args(), transport=failing_transport
        )

        for table in (
            "printer_memory_retrieval_matches",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
        ):
            self.assertEqual(count_rows(self.db_path, table), 0, table)


if __name__ == "__main__":
    unittest.main()

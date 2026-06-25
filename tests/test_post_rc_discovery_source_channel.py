"""Discovery Source Channel Sprint A: source_channel plumbing + hard gate improvements."""

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
from printer_v1.discovery.classifier import (
    classify_discovery_candidate,
    channel_specific_minimum_liquidity_floor,
    has_recent_activity_pulse,
    should_track_fast_candidate,
    should_track_normal_candidate,
    CHANNEL_MIGRATION_MINIMUM_LIQUIDITY_USD,
    MIN_TRACK_FAST_LIQUIDITY_USD,
    MIN_MEMORY_GROWTH_VOLUME_1H_USD,
)
from printer_v1.discovery.contracts import (
    DiscoveryChannelLabel,
    DiscoveryOutputAction,
    DISCOVERY_CHANNEL_LABELS,
)
from printer_v1.operator_cli.commands import build_discover_candidates_once_payload


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
)


def count_rows(connection, table):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def make_db():
    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db_path = pathlib.Path(tmp.name) / "sprint-a-discovery.sqlite3"
    apply_migrations(db_path)
    return tmp, db_path


def _args(db_path, **kw):
    values = {
        "db_path": str(db_path),
        "project_root": str(PROJECT_ROOT),
        "format": "json",
        "no_color": True,
        "operator_approved": True,
        "chain": "solana",
        "max_candidates": 2,
        "query": "pump",
        "timeout_seconds": 5.0,
        "source_name": "dexscreener",
        "request_key": "sprint-a-channel-test",
    }
    values.update(kw)
    return argparse.Namespace(**values)


# ---------------------------------------------------------------------------
# Class 1: Migration + schema
# ---------------------------------------------------------------------------

class DiscoverySourceChannelMigrationTests(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = make_db()

    def tearDown(self):
        self._tmp.cleanup()

    def test_source_channel_column_exists_after_migration(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("PRAGMA table_info(printer_discovery_candidates)").fetchall()
            column_names = {r["name"] for r in row}
        finally:
            conn.close()
        self.assertIn("source_channel", column_names)
        self.assertIn("source_channel_reason", column_names)

    def test_source_channel_index_exists(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            indexes = {
                row["name"]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()
            }
        finally:
            conn.close()
        self.assertIn("idx_discovery_candidates_source_channel", indexes)

    def test_existing_rows_have_null_source_channel_by_default(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                """INSERT INTO printer_discovery_candidates
                   (source_name, discovery_label, discovery_action, source_status, data_quality_label)
                   VALUES ('dexscreener', 'NEW_CANDIDATE', 'TRACK_NORMAL', 'COMPLETE', 'CLEAN_DATA')"""
            )
            conn.commit()
            row = conn.execute("SELECT * FROM printer_discovery_candidates ORDER BY id DESC LIMIT 1").fetchone()
        finally:
            conn.close()
        self.assertIsNone(row["source_channel"])
        self.assertIsNone(row["source_channel_reason"])


# ---------------------------------------------------------------------------
# Class 2: DiscoveryChannelLabel contract
# ---------------------------------------------------------------------------

class DiscoveryChannelLabelContractTests(unittest.TestCase):

    def test_all_required_channel_labels_are_defined(self):
        required = {
            "DEXSCREENER_SEARCH",
            "DEXSCREENER_LATEST_BOOSTED",
            "DEXSCREENER_TOP_BOOSTED",
            "GECKOTERMINAL_NEW_POOL",
            "GECKOTERMINAL_TRENDING_POOL",
            "PUMPFUN_NEW_TOKEN",
            "PUMPFUN_MIGRATION",
            "PUMPSWAP_GRADUATED",
            "RAYDIUM_POOL_CONFIRMATION",
            "MANUAL_BASELINE",
            "BASELINE_MEMORY",
            # Pump.fun public surface labels added in Sprint C
            "PUMPFUN_TRENDING_NOW",
            "PUMPFUN_TOP_COINS",
            "PUMPFUN_MOVERS",
            "PUMPFUN_MAYHEM",
            "PUMPFUN_NEW",
            "PUMPFUN_LIVE",
            "PUMPFUN_MARKET_CAP",
            "PUMPFUN_AGENTS",
            "PUMPFUN_OLDEST",
            "PUMPFUN_LAST_TRADE",
            "PUMPFUN_CHARITIES",
            # PumpSwap read-only confirmation labels added in Sprint D
            "PUMPSWAP_POOL_CONFIRMATION",
            "PUMPSWAP_MIGRATION_POOL_REFERENCE",
            "PUMPSWAP_LIQUIDITY_REFERENCE",
        }
        defined = {label.value for label in DiscoveryChannelLabel}
        self.assertEqual(required, defined)

    def test_discovery_channel_labels_tuple_is_complete(self):
        self.assertEqual(len(DISCOVERY_CHANNEL_LABELS), len(DiscoveryChannelLabel))

    def test_channel_labels_do_not_contain_forbidden_terms(self):
        all_values = " ".join(label.value.lower() for label in DiscoveryChannelLabel)
        for term in FORBIDDEN_FRAGMENTS:
            self.assertNotIn(term, all_values)

    def test_channel_label_is_a_fact_not_a_score(self):
        for label in DiscoveryChannelLabel:
            self.assertIsInstance(label.value, str)
            self.assertFalse(any(c.isdigit() for c in label.value),
                             f"{label.value} should not contain numeric score")


# ---------------------------------------------------------------------------
# Class 3: channel_specific_minimum_liquidity_floor (hard gate, not score)
# ---------------------------------------------------------------------------

class ChannelSpecificLiquidityFloorTests(unittest.TestCase):

    def test_none_channel_uses_standard_floor(self):
        self.assertEqual(
            channel_specific_minimum_liquidity_floor(None),
            MIN_TRACK_FAST_LIQUIDITY_USD,
        )

    def test_dexscreener_search_uses_standard_floor(self):
        self.assertEqual(
            channel_specific_minimum_liquidity_floor(DiscoveryChannelLabel.DEXSCREENER_SEARCH.value),
            MIN_TRACK_FAST_LIQUIDITY_USD,
        )

    def test_pumpfun_migration_uses_lower_floor(self):
        floor = channel_specific_minimum_liquidity_floor(DiscoveryChannelLabel.PUMPFUN_MIGRATION.value)
        self.assertEqual(floor, CHANNEL_MIGRATION_MINIMUM_LIQUIDITY_USD)
        self.assertLess(floor, MIN_TRACK_FAST_LIQUIDITY_USD)

    def test_pumpswap_graduated_uses_lower_floor(self):
        floor = channel_specific_minimum_liquidity_floor(DiscoveryChannelLabel.PUMPSWAP_GRADUATED.value)
        self.assertEqual(floor, CHANNEL_MIGRATION_MINIMUM_LIQUIDITY_USD)
        self.assertLess(floor, MIN_TRACK_FAST_LIQUIDITY_USD)

    def test_geckoterminal_and_other_channels_use_standard_floor(self):
        for label in (
            DiscoveryChannelLabel.GECKOTERMINAL_NEW_POOL,
            DiscoveryChannelLabel.GECKOTERMINAL_TRENDING_POOL,
            DiscoveryChannelLabel.DEXSCREENER_LATEST_BOOSTED,
            DiscoveryChannelLabel.DEXSCREENER_TOP_BOOSTED,
            DiscoveryChannelLabel.MANUAL_BASELINE,
        ):
            self.assertEqual(
                channel_specific_minimum_liquidity_floor(label.value),
                MIN_TRACK_FAST_LIQUIDITY_USD,
                f"{label.value} should use standard floor",
            )

    def test_floor_is_a_hard_numeric_gate_not_a_score(self):
        floor = channel_specific_minimum_liquidity_floor(DiscoveryChannelLabel.PUMPFUN_MIGRATION.value)
        self.assertIsInstance(floor, float)
        self.assertGreater(floor, 0)


# ---------------------------------------------------------------------------
# Class 4: has_recent_activity_pulse (new gate for TRACK_NORMAL)
# ---------------------------------------------------------------------------

class RecentActivityPulseGateTests(unittest.TestCase):

    def _c(self, **kw):
        base = {
            "token_mint": "test-mint",
            "pair_address": "test-pair",
            "chain": "solana",
            "source_name": "dexscreener",
            "captured_at": "2026-06-25T12:00:00+00:00",
            "price_usd": 0.001,
            "liquidity_usd": 5000.0,
            "volume_5m": None,
            "txns_5m": None,
            "volume_1h": None,
            "txns_1h": None,
            "volume_24h": None,
            "txns_24h": None,
        }
        base.update(kw)
        return base

    def test_any_5m_volume_is_a_pulse(self):
        self.assertTrue(has_recent_activity_pulse(self._c(volume_5m=5.0)))

    def test_any_5m_txns_is_a_pulse(self):
        self.assertTrue(has_recent_activity_pulse(self._c(txns_5m=1)))

    def test_sufficient_1h_volume_is_a_pulse(self):
        self.assertTrue(has_recent_activity_pulse(self._c(volume_1h=MIN_MEMORY_GROWTH_VOLUME_1H_USD)))

    def test_sufficient_1h_txns_is_a_pulse(self):
        self.assertTrue(has_recent_activity_pulse(self._c(txns_1h=3)))

    def test_only_24h_data_with_no_recent_pulse_fails(self):
        self.assertFalse(has_recent_activity_pulse(self._c(
            volume_5m=0, txns_5m=0,
            volume_1h=50.0,  # below MIN_MEMORY_GROWTH_VOLUME_1H_USD
            txns_1h=1,        # below MIN_MEMORY_GROWTH_TXNS_1H
            volume_24h=5000.0,
            txns_24h=50,
        )))

    def test_all_none_activity_fails(self):
        self.assertFalse(has_recent_activity_pulse(self._c()))

    def test_zero_5m_with_good_1h_passes(self):
        self.assertTrue(has_recent_activity_pulse(self._c(volume_5m=0, txns_5m=0, volume_1h=300.0)))


# ---------------------------------------------------------------------------
# Class 5: Classifier gate improvements
# ---------------------------------------------------------------------------

class ClassifierGateImprovementTests(unittest.TestCase):

    def _candidate(self, **kw):
        base = {
            "token_mint": "gate-mint",
            "pair_address": "gate-pair",
            "chain": "solana",
            "source_name": "dexscreener",
            "captured_at": "2026-06-25T12:00:00+00:00",
            "price_usd": 0.001,
            "liquidity_usd": 3000.0,
            "volume_5m": 100.0,
            "txns_5m": 5,
            "volume_1h": 500.0,
            "txns_1h": 20,
            "volume_24h": 5000.0,
            "txns_24h": 80,
        }
        base.update(kw)
        return base

    def test_stale_24h_only_token_does_not_become_track_normal(self):
        candidate = self._candidate(
            volume_5m=0, txns_5m=0,
            volume_1h=50.0, txns_1h=1,  # below pulse threshold
            volume_24h=5000.0, txns_24h=50,  # 24h looks ok but no recent pulse
        )
        self.assertFalse(should_track_normal_candidate(candidate))
        result = classify_discovery_candidate(candidate)
        self.assertNotEqual(result.discovery_action, DiscoveryOutputAction.TRACK_NORMAL)
        self.assertNotEqual(result.discovery_action, DiscoveryOutputAction.TRACK_FAST)

    def test_fresh_candidate_with_5m_volume_becomes_track_normal(self):
        candidate = self._candidate(volume_5m=50.0, txns_5m=2, volume_1h=300.0, txns_1h=15)
        self.assertTrue(should_track_normal_candidate(candidate))

    def test_track_fast_candidate_with_migration_channel_uses_lower_floor(self):
        candidate = self._candidate(
            liquidity_usd=3000.0,  # above migration floor (2000) but below standard (5000)
            volume_5m=2000.0, txns_5m=15,
            source_channel=DiscoveryChannelLabel.PUMPFUN_MIGRATION.value,
        )
        self.assertTrue(should_track_fast_candidate(candidate))

    def test_track_fast_candidate_with_search_channel_requires_standard_floor(self):
        candidate = self._candidate(
            liquidity_usd=3000.0,  # below standard floor (5000)
            volume_5m=2000.0, txns_5m=15,
            source_channel=DiscoveryChannelLabel.DEXSCREENER_SEARCH.value,
        )
        self.assertFalse(should_track_fast_candidate(candidate))

    def test_dead_candidate_remains_watch_only_or_instant_reject(self):
        candidate = self._candidate(
            volume_5m=0, txns_5m=0,
            volume_1h=0, txns_1h=0,
            volume_24h=5.0, txns_24h=1,
        )
        result = classify_discovery_candidate(candidate)
        self.assertIn(result.discovery_action, {
            DiscoveryOutputAction.WATCH_ONLY,
            DiscoveryOutputAction.INSTANT_REJECT_MEMORY_ONLY,
            DiscoveryOutputAction.IGNORE,
        })

    def test_non_solana_candidate_remains_instant_reject(self):
        candidate = self._candidate(chain="ethereum")
        result = classify_discovery_candidate(candidate)
        self.assertEqual(result.discovery_action, DiscoveryOutputAction.INSTANT_REJECT_MEMORY_ONLY)

    def test_source_channel_never_overrides_liquidity_gate_below_migration_floor(self):
        candidate = self._candidate(
            liquidity_usd=1500.0,  # below CHANNEL_MIGRATION_MINIMUM_LIQUIDITY_USD (2000)
            volume_5m=2000.0, txns_5m=15,
            source_channel=DiscoveryChannelLabel.PUMPFUN_MIGRATION.value,
        )
        self.assertFalse(should_track_fast_candidate(candidate))

    def test_watch_only_candidate_is_not_track_normal(self):
        candidate = self._candidate(liquidity_usd=400.0)  # below MIN_TRACK_NORMAL_LIQUIDITY_USD
        result = classify_discovery_candidate(candidate)
        self.assertEqual(result.discovery_action, DiscoveryOutputAction.WATCH_ONLY)

    def test_classifier_does_not_use_score_in_reason(self):
        candidate = self._candidate()
        result = classify_discovery_candidate(candidate)
        for term in FORBIDDEN_FRAGMENTS:
            self.assertNotIn(term, result.reason.lower())


# ---------------------------------------------------------------------------
# Class 6: CLI integration — source_channel stored on discovery records
# ---------------------------------------------------------------------------

class DiscoverySourceChannelCLIIntegrationTests(unittest.TestCase):

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
            conn.commit()
        finally:
            conn.close()

    def _transport_track_fast(self, ctx):
        del ctx
        return {
            "pairs": [{
                "chainId": "solana",
                "pairAddress": "sprint-a-pair-1",
                "baseToken": {"address": "sprint-a-mint-1", "symbol": "SA1", "name": "Sprint A One"},
                "quoteToken": {"address": "So11111111111111111111111111111111111111112"},
                "dexId": "raydium",
                "priceUsd": "0.005",
                "liquidity": {"usd": 12000},
                "volume": {"m5": 2000, "h1": 18000, "h24": 80000},
                "txns": {"m5": {"buys": 12, "sells": 8}, "h1": {"buys": 80, "sells": 55}},
            }]
        }

    def _transport_stale_24h_only(self, ctx):
        del ctx
        return {
            "pairs": [{
                "chainId": "solana",
                "pairAddress": "sprint-a-stale-pair",
                "baseToken": {"address": "sprint-a-stale-mint", "symbol": "STALE", "name": "Stale Token"},
                "quoteToken": {"address": "So11111111111111111111111111111111111111112"},
                "dexId": "raydium",
                "priceUsd": "0.0001",
                "liquidity": {"usd": 2000},
                "volume": {"m5": 0, "h1": 0, "h24": 5000},
                "txns": {"m5": {"buys": 0, "sells": 0}, "h1": {"buys": 0, "sells": 0}},
            }]
        }

    def test_dexscreener_search_records_source_channel_dexscreener_search(self):
        result = build_discover_candidates_once_payload(
            _args(self.db_path, max_candidates=1),
            transport=self._transport_track_fast,
        )
        self.assertEqual(result["source_channel"], "DEXSCREENER_SEARCH")
        self.assertEqual(result["source_channel_reason"], "dexscreener_default_search_query")
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT source_channel, source_channel_reason FROM printer_discovery_candidates ORDER BY id DESC LIMIT 5"
            ).fetchall()
        for row in rows:
            self.assertEqual(row["source_channel"], "DEXSCREENER_SEARCH")
            self.assertEqual(row["source_channel_reason"], "dexscreener_default_search_query")

    def test_accepted_candidates_include_source_channel(self):
        result = build_discover_candidates_once_payload(
            _args(self.db_path, max_candidates=1),
            transport=self._transport_track_fast,
        )
        if result["candidates_accepted"] > 0:
            for cand in result["accepted_candidates"]:
                self.assertIn("source_channel", cand)
                self.assertEqual(cand["source_channel"], "DEXSCREENER_SEARCH")

    def test_source_channel_in_result_payload(self):
        result = build_discover_candidates_once_payload(
            _args(self.db_path), transport=self._transport_track_fast
        )
        self.assertIn("source_channel", result)
        self.assertIn("source_channel_reason", result)

    def test_stale_24h_only_token_rejected_from_discovery_cycle(self):
        result = build_discover_candidates_once_payload(
            _args(self.db_path, max_candidates=1),
            transport=self._transport_stale_24h_only,
        )
        self.assertEqual(result["candidates_accepted"], 0)
        self.assertGreater(result["candidates_rejected"], 0)
        rejected = result["rejected_candidates"]
        self.assertTrue(any(
            r.get("reject_reason") in {
                "watch_only_not_eligible_for_15m_memory_proof_cycle",
                "insufficient_activity_for_memory_growth",
                "classified_watch_only",
            }
            for r in rejected
        ), f"unexpected reject reasons: {[r.get('reject_reason') for r in rejected]}")

    def test_no_downstream_unlocks_after_discovery(self):
        build_discover_candidates_once_payload(
            _args(self.db_path, max_candidates=1),
            transport=self._transport_track_fast,
        )
        with self.connect() as conn:
            for table in DOWNSTREAM_TABLES:
                self.assertEqual(count_rows(conn, table), 0, f"expected 0 rows in {table}")

    def test_pyproject_exposes_discover_candidates_once(self):
        import tomllib
        scripts = tomllib.loads(
            (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]["scripts"]
        self.assertEqual(
            scripts["printer-discover-candidates-once"],
            "printer_v1.operator_cli.commands:main_discover_candidates_once",
        )

    def test_source_channel_field_does_not_contain_score_or_rank_terms(self):
        source_text = (PROJECT_ROOT / "src" / "printer_v1" / "discovery" / "classifier.py").read_text(encoding="utf-8")
        source_text += (PROJECT_ROOT / "src" / "printer_v1" / "discovery" / "contracts.py").read_text(encoding="utf-8")
        source_text += (PROJECT_ROOT / "src" / "printer_v1" / "discovery" / "discovery.py").read_text(encoding="utf-8")
        for term in FORBIDDEN_FRAGMENTS:
            self.assertNotIn(term, source_text, f"Forbidden term '{term}' found in discovery modules")


if __name__ == "__main__":
    unittest.main()

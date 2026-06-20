import inspect
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.liquidity_exit import classifier, lookup, parser, recorder
from printer_v1.liquidity_exit.classifier import (
    classify_entry_realism,
    classify_exit_realism,
    classify_liquidity_drain,
    classify_liquidity_state,
    classify_price_impact,
    classify_route_availability,
    classify_slippage,
    liquidity_exit_context_blocks_clean_paper_profit,
    liquidity_exit_context_can_support_clean_memory,
)
from printer_v1.liquidity_exit.contracts import (
    EntryRealismLabel,
    ExitRealismLabel,
    LiquidityDrainLabel,
    LiquidityExitPayloadQualityLabel,
    LiquidityStateLabel,
    PriceImpactLabel,
    QuoteAgeLabel,
    RealismGateLabel,
    RouteLabel,
    SlippageLabel,
)
from printer_v1.liquidity_exit.parser import normalize_liquidity_exit_payload, validate_liquidity_exit_payload
from printer_v1.liquidity_exit.recorder import (
    enqueue_liquidity_exit_refresh_job,
    get_latest_liquidity_exit_snapshot,
    record_liquidity_exit_from_token_snapshot,
    record_liquidity_exit_snapshot,
)
from printer_v1.scheduler.contracts import JobStatus


FORBIDDEN_COLUMNS = {
    "score",
    "confidence",
    "rank",
    "rating",
    "weight",
    "wallet_address",
    "private_key",
    "signed_tx",
    "live_trade",
}
FORBIDDEN_FRAGMENTS = {
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


class Phase10LiquidityExitEngineTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "printer.sqlite3"
        apply_migrations(self.db_path)
        self.now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
        self.token_id, self.pair_id = self.insert_token_pair()

    def tearDown(self):
        self.tempdir.cleanup()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def insert_token_pair(self):
        with self.connect() as connection:
            token_id = connection.execute(
                "INSERT INTO printer_tokens (token_mint, chain) VALUES ('liq-mint', 'solana')"
            ).lastrowid
            pair_id = connection.execute(
                """
                INSERT INTO printer_pairs (token_id, pair_address, dex, pool_source)
                VALUES (?, 'liq-pair', 'raydium', 'local')
                """,
                (token_id,),
            ).lastrowid
        return int(token_id), int(pair_id)

    def payload(self, *, captured_at=None, **overrides):
        base = {
            "token": {"token_id": self.token_id, "mint": "liq-mint"},
            "pair": {"pair_id": self.pair_id, "pair_address": "liq-pair"},
            "captured_at": (captured_at or self.now).isoformat(),
            "liquidity": {
                "price_usd": 0.01,
                "usd": 200_000,
                "volume_5m": 1000,
                "volume_15m": 3000,
                "volume_1h": 10000,
                "volume_24h": 100000,
                "txns_5m": 10,
                "txns_15m": 30,
                "txns_1h": 100,
                "txns_24h": 1000,
                "liquidity_before_usd": 210_000,
                "liquidity_after_usd": 200_000,
            },
            "route": {
                "route_available": True,
                "source": "local_quote",
                "status": "available",
            },
            "quote": {
                "captured_at": (self.now - timedelta(seconds=20)).isoformat(),
                "quote_age_seconds": 20,
                "status": "fresh",
            },
            "slippage": {
                "expected_entry_size_usd": 100,
                "expected_exit_size_usd": 100,
                "estimated_entry_slippage_percent": 0.5,
                "estimated_exit_slippage_percent": 0.7,
            },
            "price_impact": {
                "estimated_entry_price_impact_percent": 0.4,
                "estimated_exit_price_impact_percent": 0.6,
            },
            "source_status": SourceStatus.COMPLETE.value,
            "data_quality_label": DataQualityLabel.CLEAN_DATA.value,
        }
        for key, value in overrides.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key].update(value)
            else:
                base[key] = value
        return base

    def count_rows(self, table):
        with self.connect() as connection:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def column_names(self, table_name):
        with self.connect() as connection:
            return {
                row[1]
                for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
            }

    def table_names(self):
        with self.connect() as connection:
            return {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

    def test_safety_package_has_dunder_init_not_accidental_init(self):
        self.assertTrue((SRC_PATH / "printer_v1" / "safety" / "__init__.py").exists())
        self.assertFalse((SRC_PATH / "printer_v1" / "safety" / "init.py").exists())

    def test_liquidity_exit_files_import_successfully(self):
        self.assertTrue(inspect.ismodule(parser))
        self.assertTrue(inspect.ismodule(classifier))
        self.assertTrue(inspect.ismodule(recorder))
        self.assertTrue(inspect.ismodule(lookup))

    def test_required_contract_labels_exist(self):
        self.assertEqual({label.value for label in LiquidityStateLabel}, {
            "LIQUIDITY_DEEP", "LIQUIDITY_USABLE", "LIQUIDITY_THIN", "LIQUIDITY_UNSTABLE", "LIQUIDITY_DRAINING", "LIQUIDITY_DANGEROUS", "LIQUIDITY_UNKNOWN"
        })
        self.assertEqual({label.value for label in EntryRealismLabel}, {
            "ENTRY_REALISTIC", "ENTRY_POSSIBLE_WITH_SLIPPAGE", "ENTRY_UNREALISTIC", "ENTRY_BLOCKED_BY_ROUTE", "ENTRY_UNKNOWN"
        })
        self.assertEqual({label.value for label in ExitRealismLabel}, {
            "EXIT_REALISTIC", "EXIT_POSSIBLE_WITH_SLIPPAGE", "EXIT_AT_RISK", "EXIT_UNREALISTIC", "EXIT_BLOCKED_BY_ROUTE", "EXIT_UNKNOWN"
        })
        self.assertEqual({label.value for label in SlippageLabel}, {
            "SLIPPAGE_LOW", "SLIPPAGE_MODERATE", "SLIPPAGE_HIGH", "SLIPPAGE_EXTREME", "SLIPPAGE_UNKNOWN"
        })
        self.assertEqual({label.value for label in PriceImpactLabel}, {
            "PRICE_IMPACT_LOW", "PRICE_IMPACT_MODERATE", "PRICE_IMPACT_HIGH", "PRICE_IMPACT_EXTREME", "PRICE_IMPACT_UNKNOWN"
        })
        self.assertEqual({label.value for label in RouteLabel}, {
            "ROUTE_AVAILABLE", "ROUTE_LIMITED", "ROUTE_STALE", "ROUTE_FAILED", "ROUTE_NOT_AVAILABLE", "ROUTE_UNKNOWN"
        })
        self.assertEqual({label.value for label in QuoteAgeLabel}, {
            "QUOTE_FRESH", "QUOTE_ACCEPTABLE", "QUOTE_STALE", "QUOTE_EXPIRED", "QUOTE_MISSING"
        })
        self.assertEqual({label.value for label in LiquidityDrainLabel}, {
            "NO_LIQUIDITY_DRAIN", "MINOR_LIQUIDITY_DRAIN", "MAJOR_LIQUIDITY_DRAIN", "SEVERE_LIQUIDITY_DRAIN", "LIQUIDITY_DRAIN_UNKNOWN"
        })
        self.assertEqual({label.value for label in LiquidityExitPayloadQualityLabel}, {
            "LIQUIDITY_EXIT_CONTEXT_CLEAN", "LIQUIDITY_EXIT_CONTEXT_PARTIAL", "LIQUIDITY_EXIT_CONTEXT_STALE", "LIQUIDITY_EXIT_CONTEXT_CONFLICTING", "LIQUIDITY_EXIT_CONTEXT_UNKNOWN", "LIQUIDITY_EXIT_CONTEXT_DO_NOT_USE_FOR_MEMORY"
        })
        self.assertEqual({label.value for label in RealismGateLabel}, {
            "REALISM_CONTEXT_ACCEPTABLE", "REALISM_CONTEXT_CAUTION", "REALISM_CONTEXT_BLOCKED", "REALISM_CONTEXT_AUDIT_ONLY", "REALISM_CONTEXT_DO_NOT_TRAIN"
        })

    def test_migration_creates_table_without_forbidden_columns(self):
        self.assertIn("printer_liquidity_exit_snapshots", self.table_names())
        self.assertEqual(
            self.column_names("printer_liquidity_exit_snapshots") & FORBIDDEN_COLUMNS,
            set(),
        )

    def test_parser_normalizes_fake_jupiter_route_payload(self):
        normalized = normalize_liquidity_exit_payload(self.payload(), self.now)
        self.assertEqual(normalized["route_available"], 1)
        self.assertEqual(normalized["quote_age_seconds"], 20)
        self.assertEqual(normalized["estimated_exit_slippage_percent"], 0.7)

    def test_parser_normalizes_fake_liquidity_payload_and_token_snapshot_shape(self):
        normalized = normalize_liquidity_exit_payload(self.payload(), self.now)
        self.assertEqual(normalized["liquidity_usd"], 200000.0)
        self.assertEqual(normalized["txns_15m"], 30)
        with self.connect() as connection:
            snapshot_id = connection.execute(
                """
                INSERT INTO printer_token_snapshots (
                    token_id, pair_id, captured_at, tracking_lane, snapshot_mode,
                    price_usd, liquidity_usd, source_status, data_quality_label
                )
                VALUES (?, ?, ?, 'TRACK_FAST', 'NORMAL_MODE', 0.01, 200000, 'COMPLETE', 'CLEAN_DATA')
                """,
                (self.token_id, self.pair_id, self.now.isoformat()),
            ).lastrowid
        created, row_id = record_liquidity_exit_from_token_snapshot(
            self.db_path,
            int(snapshot_id),
            supplemental_payload=self.payload(),
            now=self.now,
        )
        self.assertTrue(created)
        self.assertGreater(row_id, 0)

    def test_parser_labels_missing_critical_and_stale_quote_context(self):
        self.assertIn(
            validate_liquidity_exit_payload({"captured_at": self.now.isoformat()}, self.now),
            {
                LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_PARTIAL,
                LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_UNKNOWN,
                LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_DO_NOT_USE_FOR_MEMORY,
            },
        )
        stale = self.payload(quote={"quote_age_seconds": 600, "status": "expired"})
        self.assertEqual(
            validate_liquidity_exit_payload(stale, self.now),
            LiquidityExitPayloadQualityLabel.LIQUIDITY_EXIT_CONTEXT_STALE,
        )

    def test_classifier_identifies_liquidity_states_and_realism(self):
        deep = normalize_liquidity_exit_payload(self.payload(), self.now)
        thin = normalize_liquidity_exit_payload(self.payload(liquidity={"usd": 8000}), self.now)
        draining = normalize_liquidity_exit_payload(
            self.payload(liquidity={"liquidity_before_usd": 100000, "liquidity_after_usd": 70000}),
            self.now,
        )
        self.assertEqual(classify_liquidity_state(deep), LiquidityStateLabel.LIQUIDITY_DEEP)
        self.assertEqual(classify_liquidity_state(thin), LiquidityStateLabel.LIQUIDITY_THIN)
        self.assertEqual(classify_liquidity_state(draining), LiquidityStateLabel.LIQUIDITY_DRAINING)
        self.assertEqual(classify_entry_realism(deep), EntryRealismLabel.ENTRY_REALISTIC)
        self.assertEqual(classify_exit_realism(deep), ExitRealismLabel.EXIT_REALISTIC)
        self.assertEqual(classify_exit_realism(draining), ExitRealismLabel.EXIT_AT_RISK)

    def test_classifier_identifies_unrealistic_and_blocked_route(self):
        extreme = normalize_liquidity_exit_payload(
            self.payload(
                slippage={"estimated_exit_slippage_percent": 12},
                price_impact={"estimated_exit_price_impact_percent": 12},
            ),
            self.now,
        )
        blocked = normalize_liquidity_exit_payload(
            self.payload(route={"route_available": False, "status": "not_available"}),
            self.now,
        )
        self.assertEqual(classify_exit_realism(extreme), ExitRealismLabel.EXIT_UNREALISTIC)
        self.assertEqual(classify_route_availability(blocked), RouteLabel.ROUTE_NOT_AVAILABLE)
        self.assertEqual(classify_entry_realism(blocked), EntryRealismLabel.ENTRY_BLOCKED_BY_ROUTE)

    def test_classifier_identifies_slippage_price_impact_and_drains(self):
        cases = [(0.5, SlippageLabel.SLIPPAGE_LOW), (2, SlippageLabel.SLIPPAGE_MODERATE), (6, SlippageLabel.SLIPPAGE_HIGH), (10, SlippageLabel.SLIPPAGE_EXTREME)]
        for value, expected in cases:
            payload = normalize_liquidity_exit_payload(self.payload(slippage={"estimated_exit_slippage_percent": value}), self.now)
            self.assertEqual(classify_slippage(payload), expected)
        impact_cases = [(0.5, PriceImpactLabel.PRICE_IMPACT_LOW), (2, PriceImpactLabel.PRICE_IMPACT_MODERATE), (6, PriceImpactLabel.PRICE_IMPACT_HIGH), (10, PriceImpactLabel.PRICE_IMPACT_EXTREME)]
        for value, expected in impact_cases:
            payload = normalize_liquidity_exit_payload(self.payload(price_impact={"estimated_exit_price_impact_percent": value}), self.now)
            self.assertEqual(classify_price_impact(payload), expected)
        major = normalize_liquidity_exit_payload(self.payload(liquidity={"liquidity_change_percent": -30}), self.now)
        severe = normalize_liquidity_exit_payload(self.payload(liquidity={"liquidity_change_percent": -50}), self.now)
        self.assertEqual(classify_liquidity_drain(major), LiquidityDrainLabel.MAJOR_LIQUIDITY_DRAIN)
        self.assertEqual(classify_liquidity_drain(severe), LiquidityDrainLabel.SEVERE_LIQUIDITY_DRAIN)

    def test_dirty_stale_conflicting_context_cannot_support_clean_memory(self):
        dirty = normalize_liquidity_exit_payload(self.payload(), self.now)
        dirty["data_quality_label"] = DataQualityLabel.DIRTY_DATA.value
        stale = normalize_liquidity_exit_payload(self.payload(captured_at=self.now - timedelta(hours=3)), self.now)
        conflicting = normalize_liquidity_exit_payload(self.payload(), self.now)
        conflicting["source_status"] = SourceStatus.CONFLICTING.value
        for payload in (dirty, stale, conflicting):
            self.assertFalse(liquidity_exit_context_can_support_clean_memory(payload, self.now))

    def test_unrealistic_exit_blocks_profit_without_paper_decisions(self):
        payload = normalize_liquidity_exit_payload(
            self.payload(liquidity={"liquidity_change_percent": -60}),
            self.now,
        )
        self.assertTrue(liquidity_exit_context_blocks_clean_paper_profit(payload, self.now))
        record_liquidity_exit_snapshot(self.db_path, self.payload(liquidity={"liquidity_change_percent": -60}), self.now)
        self.assertEqual(self.count_rows("printer_paper_decisions"), 0)

    def test_record_dedupe_latest_and_nearest_lookup(self):
        created, row_id = record_liquidity_exit_snapshot(self.db_path, self.payload(), self.now)
        duplicate_created, duplicate_id = record_liquidity_exit_snapshot(self.db_path, self.payload(), self.now)
        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(row_id, duplicate_id)
        after = self.now + timedelta(minutes=10)
        record_liquidity_exit_snapshot(self.db_path, self.payload(captured_at=after), self.now)
        latest = get_latest_liquidity_exit_snapshot(self.db_path, token_id=self.token_id, pair_id=self.pair_id)
        nearest = lookup.find_nearest_liquidity_exit_snapshot(
            self.db_path,
            self.token_id,
            self.pair_id,
            self.now + timedelta(minutes=8),
            max_age_seconds=3600,
        )
        self.assertEqual(latest["captured_at"], after.isoformat())
        self.assertEqual(nearest["captured_at"], after.isoformat())

    def test_nearest_lookup_rejects_stale_dirty_conflicting_snapshots(self):
        dirty = self.payload()
        dirty["data_quality_label"] = DataQualityLabel.DIRTY_DATA.value
        record_liquidity_exit_snapshot(self.db_path, dirty, self.now)
        self.assertIsNone(
            lookup.find_nearest_liquidity_exit_snapshot(
                self.db_path,
                self.token_id,
                self.pair_id,
                self.now,
                max_age_seconds=3600,
            )
        )

    def test_scheduler_integration_creates_rows_only(self):
        result, job_id = enqueue_liquidity_exit_refresh_job(
            self.db_path,
            self.token_id,
            self.pair_id,
            self.now + timedelta(minutes=5),
            reason="phase10_test",
        )
        self.assertEqual(result.value, "ACQUIRED")
        self.assertIsNotNone(job_id)
        with self.connect() as connection:
            row = connection.execute("SELECT status FROM printer_scheduler_jobs").fetchone()
            running = connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = ?",
                (JobStatus.RUNNING.value,),
            ).fetchone()[0]
        self.assertEqual(row["status"], JobStatus.PENDING.value)
        self.assertEqual(running, 0)

    def test_no_paper_rows_or_lifecycle_state_changes_are_created(self):
        record_liquidity_exit_snapshot(self.db_path, self.payload(), self.now)
        self.assertEqual(self.count_rows("printer_paper_decisions"), 0)
        self.assertEqual(self.count_rows("printer_paper_positions"), 0)
        self.assertEqual(self.count_rows("printer_token_lifecycle_events"), 0)

    def test_no_network_source_adapter_loop_or_forbidden_concepts_exist(self):
        source_text = "\n".join(inspect.getsource(module) for module in (parser, classifier, recorder, lookup))
        for fragment in ("requests.get", "requests.post", "httpx", "aiohttp", "urllib.request", "while True", "APScheduler"):
            self.assertNotIn(fragment, source_text)
        names = []
        for module in (parser, classifier, recorder, lookup):
            names.extend(name.lower() for name, _ in inspect.getmembers(module))
        joined_names = " ".join(names)
        self.assertFalse(any(fragment in joined_names for fragment in FORBIDDEN_FRAGMENTS))


if __name__ == "__main__":
    unittest.main()

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
from printer_v1.market_regime import classifier, lookup, parser, recorder
from printer_v1.market_regime.classifier import (
    classify_market_regime,
    classify_market_transition,
    market_context_can_support_clean_memory,
)
from printer_v1.market_regime.contracts import (
    MarketPayloadQualityLabel,
    MarketRegimeLabel,
    MarketTransitionLabel,
)
from printer_v1.market_regime.parser import normalize_market_payload, validate_market_payload
from printer_v1.market_regime.recorder import (
    enqueue_market_regime_refresh_job,
    get_latest_market_regime_snapshot,
    record_market_regime_snapshot,
)
from printer_v1.scheduler.contracts import JobStatus


REQUIRED_REGIME_LABELS = {
    "EXTREME_FEAR",
    "FEAR",
    "NEUTRAL",
    "GREED",
    "EXTREME_GREED",
    "RISK_ON",
    "RISK_OFF",
    "CHOPPY",
    "VOLATILE",
    "UNKNOWN",
}

REQUIRED_TRANSITION_LABELS = {
    "FEAR_TO_NEUTRAL",
    "NEUTRAL_TO_GREED",
    "GREED_TO_EXTREME_GREED",
    "EXTREME_GREED_TO_GREED",
    "GREED_TO_NEUTRAL",
    "NEUTRAL_TO_FEAR",
    "FEAR_TO_EXTREME_FEAR",
    "RISK_OFF_TO_RISK_ON",
    "RISK_ON_TO_RISK_OFF",
    "CHOPPY_TO_TRENDING",
    "TRENDING_TO_CHOPPY",
    "UNKNOWN_TRANSITION",
}

REQUIRED_QUALITY_LABELS = {
    "MARKET_CONTEXT_CLEAN",
    "MARKET_CONTEXT_PARTIAL",
    "MARKET_CONTEXT_STALE",
    "MARKET_CONTEXT_CONFLICTING",
    "MARKET_CONTEXT_UNKNOWN",
    "MARKET_CONTEXT_DO_NOT_USE_FOR_MEMORY",
}

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


class Phase7MarketRegimeEngineTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "printer.sqlite3"
        apply_migrations(self.db_path)
        self.now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)

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

    def count_rows(self, table):
        with self.connect() as connection:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def fear_greed_payload(self, value=20, captured_at=None):
        timestamp = int((captured_at or self.now).timestamp())
        return {
            "data": [
                {
                    "value": str(value),
                    "value_classification": "Extreme Fear" if value < 25 else "Greed",
                    "timestamp": str(timestamp),
                },
                {
                    "value": "40",
                    "value_classification": "Fear",
                    "timestamp": str(timestamp - 86400),
                },
            ],
            "source_status": SourceStatus.COMPLETE.value,
            "data_quality_label": DataQualityLabel.CLEAN_DATA.value,
        }

    def asset_payload(self, *, captured_at=None, btc_24h=3.0, sol_24h=4.0):
        return {
            "captured_at": (captured_at or self.now).isoformat(),
            "assets": {
                "bitcoin": {
                    "market_data": {
                        "current_price": {"usd": 65000},
                        "price_change_percentage_24h": btc_24h,
                        "price_change_percentage_7d": 8.0,
                    },
                    "price_change_percentage_1h": 0.5,
                },
                "ethereum": {
                    "market_data": {
                        "current_price": {"usd": 3500},
                        "price_change_percentage_24h": 2.0,
                        "price_change_percentage_7d": 5.0,
                    }
                },
                "solana": {
                    "market_data": {
                        "current_price": {"usd": 150},
                        "price_change_percentage_24h": sol_24h,
                        "price_change_percentage_7d": 12.0,
                        "total_volume": {"usd": 2000000000},
                    },
                    "price_change_percentage_1h": 1.0,
                },
            },
            "fear_greed": {"value": 66, "label": "Greed"},
            "source_status": SourceStatus.COMPLETE.value,
            "data_quality_label": DataQualityLabel.CLEAN_DATA.value,
        }

    def defi_payload(self, captured_at=None):
        return {
            "captured_at": (captured_at or self.now).isoformat(),
            "solana_context": {
                "solana_tvl_usd": 4700000000,
                "dex_volume_context": "rising",
                "stablecoin_context": "steady",
                "tracked_solana_meme_volume": 12000000,
                "tracked_solana_meme_liquidity": 3500000,
                "tracked_solana_hot_pair_count": 22,
                "tracked_solana_new_pair_count": 40,
            },
            "source_status": SourceStatus.COMPLETE.value,
            "data_quality_label": DataQualityLabel.CLEAN_DATA.value,
        }

    def full_payload(self, *, captured_at=None, btc_24h=3.0, sol_24h=4.0):
        when = captured_at or self.now
        payload = self.asset_payload(captured_at=when, btc_24h=btc_24h, sol_24h=sol_24h)
        payload["solana_context"] = self.defi_payload(captured_at=when)["solana_context"]
        return payload

    def table_names(self):
        with self.connect() as connection:
            return {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

    def column_names(self, table_name):
        with self.connect() as connection:
            return {
                row[1]
                for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
            }

    def test_snapshots_package_has_dunder_init_not_accidental_init(self):
        self.assertTrue((SRC_PATH / "printer_v1" / "snapshots" / "__init__.py").exists())
        self.assertFalse((SRC_PATH / "printer_v1" / "snapshots" / "init.py").exists())

    def test_market_regime_files_import_successfully(self):
        self.assertTrue(inspect.ismodule(parser))
        self.assertTrue(inspect.ismodule(classifier))
        self.assertTrue(inspect.ismodule(recorder))
        self.assertTrue(inspect.ismodule(lookup))

    def test_required_contract_labels_exist(self):
        self.assertEqual({label.value for label in MarketRegimeLabel}, REQUIRED_REGIME_LABELS)
        self.assertEqual({label.value for label in MarketTransitionLabel}, REQUIRED_TRANSITION_LABELS)
        self.assertEqual({label.value for label in MarketPayloadQualityLabel}, REQUIRED_QUALITY_LABELS)

    def test_migration_creates_market_regime_table_without_forbidden_columns(self):
        self.assertIn("printer_market_regime_snapshots", self.table_names())
        forbidden_found = self.column_names("printer_market_regime_snapshots") & FORBIDDEN_COLUMNS
        self.assertEqual(forbidden_found, set())

    def test_parser_normalizes_fake_alternative_me_payload(self):
        normalized = normalize_market_payload(self.fear_greed_payload(20), self.now)
        self.assertEqual(normalized["fear_greed_value"], 20)
        self.assertEqual(normalized["fear_greed_label"], "Extreme Fear")

    def test_parser_normalizes_fake_coingecko_asset_payload(self):
        normalized = normalize_market_payload(self.asset_payload(), self.now)
        self.assertEqual(normalized["btc_price_usd"], 65000.0)
        self.assertEqual(normalized["sol_price_usd"], 150.0)
        self.assertEqual(normalized["sol_volume_24h"], 2000000000.0)

    def test_parser_normalizes_fake_defillama_context_payload(self):
        normalized = normalize_market_payload(self.defi_payload(), self.now)
        self.assertEqual(normalized["solana_tvl_usd"], 4700000000.0)
        self.assertEqual(normalized["tracked_solana_hot_pair_count"], 22)

    def test_parser_labels_missing_critical_context_as_not_clean(self):
        payload = {"captured_at": self.now.isoformat()}
        self.assertIn(
            validate_market_payload(payload, self.now),
            {
                MarketPayloadQualityLabel.MARKET_CONTEXT_PARTIAL,
                MarketPayloadQualityLabel.MARKET_CONTEXT_UNKNOWN,
                MarketPayloadQualityLabel.MARKET_CONTEXT_DO_NOT_USE_FOR_MEMORY,
            },
        )

    def test_stale_market_payload_is_labeled_stale(self):
        payload = self.full_payload(captured_at=self.now - timedelta(hours=4))
        self.assertEqual(
            validate_market_payload(payload, self.now),
            MarketPayloadQualityLabel.MARKET_CONTEXT_STALE,
        )

    def test_classifier_maps_fear_greed_values(self):
        cases = [
            (10, MarketRegimeLabel.EXTREME_FEAR),
            (30, MarketRegimeLabel.FEAR),
            (50, MarketRegimeLabel.NEUTRAL),
            (60, MarketRegimeLabel.GREED),
            (80, MarketRegimeLabel.EXTREME_GREED),
        ]
        for value, expected in cases:
            self.assertEqual(classify_market_regime({"fear_greed_value": value}), expected)

    def test_classifier_identifies_risk_on_from_positive_context(self):
        normalized = normalize_market_payload(self.full_payload(btc_24h=3, sol_24h=5), self.now)
        self.assertEqual(classify_market_regime(normalized), MarketRegimeLabel.RISK_ON)

    def test_classifier_identifies_risk_off_from_negative_context(self):
        normalized = normalize_market_payload(self.full_payload(btc_24h=-4, sol_24h=-6), self.now)
        self.assertEqual(classify_market_regime(normalized), MarketRegimeLabel.RISK_OFF)

    def test_classifier_identifies_choppy_or_volatile_mixed_context(self):
        choppy = normalize_market_payload(self.full_payload(btc_24h=0.2, sol_24h=-0.5), self.now)
        volatile = normalize_market_payload(self.full_payload(btc_24h=5, sol_24h=-5), self.now)
        self.assertEqual(classify_market_regime(choppy), MarketRegimeLabel.CHOPPY)
        self.assertEqual(classify_market_regime(volatile), MarketRegimeLabel.VOLATILE)

    def test_classifier_returns_unknown_for_insufficient_context(self):
        self.assertEqual(classify_market_regime({}), MarketRegimeLabel.UNKNOWN)

    def test_transition_classifier_returns_known_and_unknown_transitions(self):
        self.assertEqual(
            classify_market_transition(
                {"market_regime_label": MarketRegimeLabel.FEAR.value},
                {"market_regime_label": MarketRegimeLabel.NEUTRAL.value},
            ),
            MarketTransitionLabel.FEAR_TO_NEUTRAL,
        )
        self.assertEqual(
            classify_market_transition(
                {"market_regime_label": MarketRegimeLabel.EXTREME_FEAR.value},
                {"market_regime_label": MarketRegimeLabel.EXTREME_GREED.value},
            ),
            MarketTransitionLabel.UNKNOWN_TRANSITION,
        )

    def test_dirty_stale_conflicting_context_cannot_support_clean_memory(self):
        dirty = normalize_market_payload(self.full_payload(), self.now)
        dirty["data_quality_label"] = DataQualityLabel.DIRTY_DATA.value
        stale = normalize_market_payload(
            self.full_payload(captured_at=self.now - timedelta(hours=4)),
            self.now,
        )
        conflicting = normalize_market_payload(self.full_payload(), self.now)
        conflicting["source_status"] = SourceStatus.CONFLICTING.value
        for payload in (dirty, stale, conflicting):
            self.assertFalse(market_context_can_support_clean_memory(payload, self.now))

    def test_record_market_regime_snapshot_inserts_and_dedupes_row(self):
        created, row_id = record_market_regime_snapshot(self.db_path, self.full_payload(), self.now)
        duplicate_created, duplicate_id = record_market_regime_snapshot(
            self.db_path,
            self.full_payload(),
            self.now,
        )
        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(row_id, duplicate_id)
        self.assertEqual(self.count_rows("printer_market_regime_snapshots"), 1)

    def test_latest_market_regime_snapshot_returns_newest_snapshot(self):
        record_market_regime_snapshot(
            self.db_path,
            self.full_payload(captured_at=self.now - timedelta(minutes=30)),
            self.now,
        )
        record_market_regime_snapshot(self.db_path, self.full_payload(captured_at=self.now), self.now)
        latest = get_latest_market_regime_snapshot(self.db_path)
        self.assertEqual(latest["captured_at"], self.now.isoformat())

    def test_nearest_valid_lookup_returns_closest_clean_snapshot(self):
        before_time = self.now - timedelta(minutes=20)
        after_time = self.now + timedelta(minutes=10)
        record_market_regime_snapshot(self.db_path, self.full_payload(captured_at=before_time), self.now)
        record_market_regime_snapshot(self.db_path, self.full_payload(captured_at=after_time), self.now)
        nearest = lookup.find_nearest_market_regime_snapshot(
            self.db_path,
            self.now,
            max_age_seconds=3600,
        )
        self.assertEqual(nearest["captured_at"], after_time.isoformat())

    def test_nearest_valid_lookup_rejects_stale_dirty_conflicting_context(self):
        dirty = self.full_payload(captured_at=self.now)
        dirty["data_quality_label"] = DataQualityLabel.DIRTY_DATA.value
        record_market_regime_snapshot(self.db_path, dirty, self.now)
        self.assertIsNone(
            lookup.find_nearest_market_regime_snapshot(
                self.db_path,
                self.now,
                max_age_seconds=3600,
            )
        )

    def test_scheduler_integration_creates_rows_only(self):
        result, job_id = enqueue_market_regime_refresh_job(
            self.db_path,
            self.now + timedelta(minutes=15),
            reason="phase7_test",
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

    def test_no_paper_decision_or_position_rows_are_created(self):
        record_market_regime_snapshot(self.db_path, self.full_payload(), self.now)
        self.assertEqual(self.count_rows("printer_paper_decisions"), 0)
        self.assertEqual(self.count_rows("printer_paper_positions"), 0)

    def test_no_network_source_adapter_loop_or_forbidden_concepts_exist(self):
        source_text = "\n".join(inspect.getsource(module) for module in (parser, classifier, recorder, lookup))
        for fragment in (
            "requests.get",
            "requests.post",
            "httpx",
            "aiohttp",
            "urllib.request",
            "while True",
            "APScheduler",
        ):
            self.assertNotIn(fragment, source_text)
        names = []
        for module in (parser, classifier, recorder, lookup):
            names.extend(name.lower() for name, _ in inspect.getmembers(module))
        joined_names = " ".join(names)
        self.assertFalse(any(fragment in joined_names for fragment in FORBIDDEN_FRAGMENTS))


if __name__ == "__main__":
    unittest.main()

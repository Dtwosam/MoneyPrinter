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

from printer_v1.chart_volatility import classifier, lookup, parser, recorder
from printer_v1.chart_volatility.classifier import (
    chart_context_can_support_clean_memory,
    classify_candle_path,
    classify_chart_memory_gate,
    classify_chart_payload_quality,
    classify_drawdown_recovery,
    classify_momentum,
    classify_range_behavior,
    classify_trend_structure,
    classify_volatility,
)
from printer_v1.chart_volatility.contracts import (
    CandlePathLabel,
    ChartMemoryGateLabel,
    ChartPayloadQualityLabel,
    DrawdownRecoveryLabel,
    MomentumLabel,
    RangeBehaviorLabel,
    TrendStructureLabel,
    VolatilityLabel,
)
from printer_v1.chart_volatility.parser import normalize_chart_payload, validate_chart_payload
from printer_v1.chart_volatility.recorder import (
    enqueue_chart_volatility_refresh_job,
    get_latest_chart_volatility_snapshot,
    record_chart_volatility_from_token_snapshots,
    record_chart_volatility_snapshot,
)
from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
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
    "private_key",
    "signed_tx",
    "live_trade",
}


class Phase12ChartVolatilityEngineTest(unittest.TestCase):
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
                "INSERT INTO printer_tokens (token_mint, chain) VALUES ('chart-mint', 'solana')"
            ).lastrowid
            pair_id = connection.execute(
                """
                INSERT INTO printer_pairs (token_id, pair_address, dex, pool_source)
                VALUES (?, 'chart-pair', 'raydium', 'local')
                """,
                (token_id,),
            ).lastrowid
        return int(token_id), int(pair_id)

    def payload(self, *, captured_at=None, **overrides):
        base = {
            "token": {"token_id": self.token_id, "mint": "chart-mint"},
            "pair": {"pair_id": self.pair_id, "pair_address": "chart-pair"},
            "captured_at": (captured_at or self.now).isoformat(),
            "ohlc": {
                "start_at": (self.now - timedelta(minutes=15)).isoformat(),
                "end_at": (captured_at or self.now).isoformat(),
                "open": 1.0,
                "high": 1.35,
                "low": 0.95,
                "close": 1.25,
            },
            "candles": {
                "candle_count": 6,
                "green_candle_count": 4,
                "red_candle_count": 1,
                "flat_candle_count": 1,
                "largest_green_candle_percent": 12,
                "largest_red_candle_percent": -4,
                "consecutive_green_candles": 4,
                "consecutive_red_candles": 1,
                "higher_high_count": 4,
                "lower_low_count": 0,
            },
            "breakout_percent": 12,
            "source_status": SourceStatus.COMPLETE.value,
            "data_quality_label": DataQualityLabel.CLEAN_DATA.value,
        }
        for key, value in overrides.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key].update(value)
            else:
                base[key] = value
        return base

    def normalize(self, **overrides):
        return normalize_chart_payload(self.payload(**overrides), self.now)

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

    def test_trading_flow_package_has_dunder_init_not_accidental_init(self):
        self.assertTrue((SRC_PATH / "printer_v1" / "trading_flow" / "__init__.py").exists())
        self.assertFalse((SRC_PATH / "printer_v1" / "trading_flow" / "init.py").exists())

    def test_chart_volatility_files_import_successfully(self):
        self.assertTrue(inspect.ismodule(parser))
        self.assertTrue(inspect.ismodule(classifier))
        self.assertTrue(inspect.ismodule(recorder))
        self.assertTrue(inspect.ismodule(lookup))

    def test_required_contract_labels_exist(self):
        self.assertEqual({label.value for label in TrendStructureLabel}, {
            "TREND_UP", "TREND_DOWN", "TREND_SIDEWAYS", "TREND_PARABOLIC_UP", "TREND_PARABOLIC_DOWN", "TREND_CHOPPY", "TREND_UNKNOWN"
        })
        self.assertEqual({label.value for label in VolatilityLabel}, {
            "VOLATILITY_LOW", "VOLATILITY_NORMAL", "VOLATILITY_ELEVATED", "VOLATILITY_HIGH", "VOLATILITY_EXTREME", "VOLATILITY_UNKNOWN"
        })
        self.assertEqual({label.value for label in RangeBehaviorLabel}, {
            "RANGE_EXPANDING", "RANGE_COMPRESSING", "RANGE_BREAKOUT", "RANGE_BREAKDOWN", "RANGE_FAKEOUT", "RANGE_UNKNOWN"
        })
        self.assertEqual({label.value for label in MomentumLabel}, {
            "MOMENTUM_ACCELERATING_UP", "MOMENTUM_ACCELERATING_DOWN", "MOMENTUM_FADING", "MOMENTUM_STABLE", "MOMENTUM_EXHAUSTED", "MOMENTUM_UNKNOWN"
        })
        self.assertEqual({label.value for label in DrawdownRecoveryLabel}, {
            "DRAWDOWN_NONE", "DRAWDOWN_MINOR", "DRAWDOWN_MODERATE", "DRAWDOWN_SEVERE", "RECOVERY_STRONG", "RECOVERY_WEAK", "RECOVERY_FAILED", "DRAWDOWN_RECOVERY_UNKNOWN"
        })
        self.assertEqual({label.value for label in CandlePathLabel}, {
            "PATH_STEADY_CLIMB", "PATH_SPIKE_AND_HOLD", "PATH_SPIKE_AND_FADE", "PATH_GRIND_DOWN", "PATH_V_SHAPED_RECOVERY", "PATH_ROUND_TRIP", "PATH_CHOPPY_NOISE", "PATH_UNKNOWN"
        })
        self.assertEqual({label.value for label in ChartPayloadQualityLabel}, {
            "CHART_CONTEXT_CLEAN", "CHART_CONTEXT_PARTIAL", "CHART_CONTEXT_STALE", "CHART_CONTEXT_CONFLICTING", "CHART_CONTEXT_UNKNOWN", "CHART_CONTEXT_DO_NOT_USE_FOR_MEMORY"
        })
        self.assertEqual({label.value for label in ChartMemoryGateLabel}, {
            "CHART_CONTEXT_ACCEPTABLE", "CHART_CONTEXT_CAUTION", "CHART_CONTEXT_AUDIT_ONLY", "CHART_CONTEXT_DO_NOT_TRAIN"
        })

    def test_migration_creates_table_without_forbidden_columns(self):
        self.assertIn("printer_chart_volatility_snapshots", self.table_names())
        self.assertEqual(
            self.column_names("printer_chart_volatility_snapshots") & FORBIDDEN_COLUMNS,
            set(),
        )

    def test_parser_normalizes_ohlc_and_token_snapshot_payloads(self):
        normalized = normalize_chart_payload(self.payload(), self.now)
        self.assertEqual(normalized["token_mint"], "chart-mint")
        self.assertEqual(normalized["price_open"], 1.0)
        self.assertEqual(round(normalized["price_change_percent"], 2), 25.0)
        self.assertEqual(normalized["candle_count"], 6)
        prices = [1.0, 1.05, 1.1, 1.2, 1.18, 1.25]
        with self.connect() as connection:
            for index, price in enumerate(prices):
                connection.execute(
                    """
                    INSERT INTO printer_token_snapshots (
                        token_id, pair_id, captured_at, tracking_lane, snapshot_mode,
                        price_usd, liquidity_usd, source_status, data_quality_label
                    )
                    VALUES (?, ?, ?, 'TRACK_FAST', 'NORMAL_MODE', ?, 120000, 'COMPLETE', 'CLEAN_DATA')
                    """,
                    (self.token_id, self.pair_id, (self.now - timedelta(minutes=5 - index)).isoformat(), price),
                )
        created, row_id = record_chart_volatility_from_token_snapshots(
            self.db_path,
            self.token_id,
            self.pair_id,
            self.now - timedelta(minutes=5),
            self.now,
            now=self.now,
        )
        self.assertTrue(created)
        self.assertGreater(row_id, 0)

    def test_parser_labels_missing_critical_and_stale_context(self):
        self.assertIn(
            validate_chart_payload({"captured_at": self.now.isoformat()}, self.now),
            {
                ChartPayloadQualityLabel.CHART_CONTEXT_PARTIAL,
                ChartPayloadQualityLabel.CHART_CONTEXT_UNKNOWN,
                ChartPayloadQualityLabel.CHART_CONTEXT_DO_NOT_USE_FOR_MEMORY,
            },
        )
        self.assertEqual(
            validate_chart_payload(self.payload(captured_at=self.now - timedelta(hours=3)), self.now),
            ChartPayloadQualityLabel.CHART_CONTEXT_STALE,
        )

    def test_classifier_identifies_trends_and_volatility(self):
        self.assertEqual(classify_trend_structure(self.normalize()), TrendStructureLabel.TREND_UP)
        self.assertEqual(classify_trend_structure(self.normalize(ohlc={"close": 0.75}, candles={"lower_low_count": 4, "higher_high_count": 0})), TrendStructureLabel.TREND_DOWN)
        self.assertEqual(classify_trend_structure(self.normalize(ohlc={"high": 1.03, "low": 0.98, "close": 1.01}, candles={"green_candle_count": 2, "red_candle_count": 2})), TrendStructureLabel.TREND_SIDEWAYS)
        self.assertEqual(classify_trend_structure(self.normalize(ohlc={"high": 2.4, "close": 2.0})), TrendStructureLabel.TREND_PARABOLIC_UP)
        self.assertEqual(classify_trend_structure(self.normalize(ohlc={"low": 0.3, "close": 0.4})), TrendStructureLabel.TREND_PARABOLIC_DOWN)
        self.assertEqual(classify_trend_structure(self.normalize(ohlc={"high": 1.4, "low": 0.85, "close": 1.03}, candles={"green_candle_count": 3, "red_candle_count": 3})), TrendStructureLabel.TREND_CHOPPY)
        for pct, expected in [
            (5, VolatilityLabel.VOLATILITY_LOW),
            (10, VolatilityLabel.VOLATILITY_NORMAL),
            (30, VolatilityLabel.VOLATILITY_ELEVATED),
            (50, VolatilityLabel.VOLATILITY_HIGH),
            (90, VolatilityLabel.VOLATILITY_EXTREME),
        ]:
            self.assertEqual(classify_volatility({"volatility_percent": pct}), expected)
        self.assertEqual(classify_volatility({}), VolatilityLabel.VOLATILITY_UNKNOWN)

    def test_classifier_identifies_range_momentum_drawdown_and_paths(self):
        self.assertEqual(classify_range_behavior({"range_width_percent": 40}), RangeBehaviorLabel.RANGE_EXPANDING)
        self.assertEqual(classify_range_behavior({"range_width_percent": 4, "price_change_percent": 1}), RangeBehaviorLabel.RANGE_COMPRESSING)
        self.assertEqual(classify_range_behavior({"breakout_percent": 12}), RangeBehaviorLabel.RANGE_BREAKOUT)
        self.assertEqual(classify_range_behavior({"breakdown_percent": -12}), RangeBehaviorLabel.RANGE_BREAKDOWN)
        self.assertEqual(classify_range_behavior({"breakout_percent": 20, "high_to_close_fade_percent": -40}), RangeBehaviorLabel.RANGE_FAKEOUT)
        self.assertEqual(classify_momentum({"price_change_percent": 25, "consecutive_green_candles": 3}), MomentumLabel.MOMENTUM_ACCELERATING_UP)
        self.assertEqual(classify_momentum({"price_change_percent": -25, "consecutive_red_candles": 3}), MomentumLabel.MOMENTUM_ACCELERATING_DOWN)
        self.assertEqual(classify_momentum({"price_change_percent": 25, "high_to_close_fade_percent": -40}), MomentumLabel.MOMENTUM_FADING)
        self.assertEqual(classify_momentum({"price_change_percent": 2}), MomentumLabel.MOMENTUM_STABLE)
        self.assertEqual(classify_momentum({"price_change_percent": 6, "volatility_percent": 40}), MomentumLabel.MOMENTUM_EXHAUSTED)
        self.assertEqual(classify_drawdown_recovery({"max_drawdown_percent": -2}), DrawdownRecoveryLabel.DRAWDOWN_NONE)
        self.assertEqual(classify_drawdown_recovery({"max_drawdown_percent": -8}), DrawdownRecoveryLabel.DRAWDOWN_MINOR)
        self.assertEqual(classify_drawdown_recovery({"max_drawdown_percent": -20}), DrawdownRecoveryLabel.DRAWDOWN_MODERATE)
        self.assertEqual(classify_drawdown_recovery({"max_drawdown_percent": -32}), DrawdownRecoveryLabel.DRAWDOWN_SEVERE)
        self.assertEqual(classify_drawdown_recovery({"max_drawdown_percent": -25, "recovery_from_low_percent": 55}), DrawdownRecoveryLabel.RECOVERY_STRONG)
        self.assertEqual(classify_drawdown_recovery({"max_drawdown_percent": -25, "recovery_from_low_percent": 20}), DrawdownRecoveryLabel.RECOVERY_WEAK)
        self.assertEqual(classify_drawdown_recovery({"max_drawdown_percent": -40, "recovery_from_low_percent": 4}), DrawdownRecoveryLabel.RECOVERY_FAILED)
        self.assertEqual(classify_candle_path({"price_change_percent": 14, "consecutive_green_candles": 3}), CandlePathLabel.PATH_STEADY_CLIMB)
        self.assertEqual(classify_candle_path({"price_change_percent": 25, "max_runup_percent": 35}), CandlePathLabel.PATH_SPIKE_AND_HOLD)
        self.assertEqual(classify_candle_path({"price_change_percent": 5, "high_to_close_fade_percent": -40}), CandlePathLabel.PATH_SPIKE_AND_FADE)
        self.assertEqual(classify_candle_path({"price_change_percent": -15, "consecutive_red_candles": 3}), CandlePathLabel.PATH_GRIND_DOWN)
        self.assertEqual(classify_candle_path({"price_change_percent": 12, "recovery_from_low_percent": 55}), CandlePathLabel.PATH_V_SHAPED_RECOVERY)
        self.assertEqual(classify_candle_path({"price_change_percent": 2, "round_trip_percent": 85}), CandlePathLabel.PATH_ROUND_TRIP)
        self.assertEqual(classify_candle_path({"price_change_percent": 2, "green_candle_count": 3, "red_candle_count": 3}), CandlePathLabel.PATH_CHOPPY_NOISE)

    def test_bad_context_cannot_support_clean_memory(self):
        dirty = self.normalize()
        dirty["data_quality_label"] = DataQualityLabel.DIRTY_DATA.value
        stale = self.normalize(captured_at=self.now - timedelta(hours=3))
        conflicting = self.normalize()
        conflicting["source_status"] = SourceStatus.CONFLICTING.value
        for payload in (dirty, stale, conflicting):
            self.assertFalse(chart_context_can_support_clean_memory(payload, self.now))
            self.assertNotEqual(
                classify_chart_payload_quality(payload, self.now),
                ChartPayloadQualityLabel.CHART_CONTEXT_CLEAN,
            )

    def test_extreme_or_round_trip_is_outcome_not_evidence_fault(self):
        """V2-9.4.5: market outcome never degrades evidence quality.

        This previously asserted the inverse (that extreme volatility and a
        round trip block clean memory). That conflated a price-path fact with a
        data fault and is what marked Attempt 6's fully evidenced round trip
        DIRTY. The labels stay truthful; only the blocking is removed.
        """
        extreme = self.normalize(ohlc={"high": 2.0, "low": 0.5, "close": 1.0})
        # Pumped 10% then retraced fully: the Attempt 6 shape.
        round_trip = self.normalize(
            ohlc={"open": 1.0, "high": 1.1, "low": 0.15, "close": 0.15}
        )
        # Outcome facts are still classified truthfully.
        self.assertEqual(classify_volatility(extreme), VolatilityLabel.VOLATILITY_EXTREME)
        self.assertEqual(classify_candle_path(round_trip), CandlePathLabel.PATH_ROUND_TRIP)
        # But trustworthy evidence is no longer gated on them.
        for payload in (extreme, round_trip):
            self.assertEqual(
                classify_chart_payload_quality(payload, self.now),
                ChartPayloadQualityLabel.CHART_CONTEXT_CLEAN,
            )
            self.assertNotEqual(
                classify_chart_memory_gate(payload, self.now),
                ChartMemoryGateLabel.CHART_CONTEXT_DO_NOT_TRAIN,
            )
            self.assertTrue(chart_context_can_support_clean_memory(payload, self.now))
        record_chart_volatility_snapshot(self.db_path, self.payload(ohlc={"high": 1.8, "close": 1.02}), self.now)
        self.assertEqual(self.count_rows("printer_paper_decisions"), 0)

    def test_record_dedupe_latest_and_nearest_lookup(self):
        created, row_id = record_chart_volatility_snapshot(self.db_path, self.payload(), self.now)
        duplicate_created, duplicate_id = record_chart_volatility_snapshot(self.db_path, self.payload(), self.now)
        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(row_id, duplicate_id)
        later = self.now + timedelta(minutes=10)
        record_chart_volatility_snapshot(
            self.db_path,
            self.payload(captured_at=later, ohlc={"start_at": (later - timedelta(minutes=15)).isoformat(), "end_at": later.isoformat()}),
            self.now,
        )
        latest = get_latest_chart_volatility_snapshot(self.db_path, token_id=self.token_id, pair_id=self.pair_id)
        nearest = lookup.find_nearest_chart_volatility_snapshot(
            self.db_path,
            self.token_id,
            self.pair_id,
            self.now + timedelta(minutes=8),
            max_age_seconds=3600,
        )
        self.assertEqual(latest["captured_at"], later.isoformat())
        self.assertEqual(nearest["captured_at"], later.isoformat())

    def test_nearest_lookup_rejects_bad_snapshots(self):
        dirty = self.payload()
        dirty["data_quality_label"] = DataQualityLabel.DIRTY_DATA.value
        stale = self.payload(captured_at=self.now - timedelta(hours=3))
        conflicting = self.payload()
        conflicting["source_status"] = SourceStatus.CONFLICTING.value
        extreme = self.payload(ohlc={"high": 2.0, "low": 0.5, "close": 1.0})
        round_trip = self.payload(ohlc={"high": 1.8, "close": 1.02})
        for payload in (dirty, stale, conflicting, extreme, round_trip):
            record_chart_volatility_snapshot(self.db_path, payload, self.now)
        self.assertIsNone(
            lookup.find_nearest_chart_volatility_snapshot(
                self.db_path,
                self.token_id,
                self.pair_id,
                self.now,
                max_age_seconds=3600,
            )
        )

    def test_scheduler_integration_creates_rows_only(self):
        result, job_id = enqueue_chart_volatility_refresh_job(
            self.db_path,
            self.token_id,
            self.pair_id,
            self.now + timedelta(minutes=5),
            reason="phase12_test",
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
        record_chart_volatility_snapshot(self.db_path, self.payload(), self.now)
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

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

from printer_v1.chain_heat import classifier, lookup, parser, recorder
from printer_v1.chain_heat.classifier import (
    chain_heat_context_can_support_clean_memory,
    classify_chain_heat,
)
from printer_v1.chain_heat.contracts import (
    ChainHeatLabel,
    ChainHeatPayloadQualityLabel,
    SolanaActivityLabel,
    SolanaCongestionLabel,
    SolanaLiquidityLabel,
)
from printer_v1.chain_heat.parser import normalize_chain_heat_payload, validate_chain_heat_payload
from printer_v1.chain_heat.recorder import (
    enqueue_chain_heat_refresh_job,
    get_latest_chain_heat_snapshot,
    record_chain_heat_snapshot,
)
from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.scheduler.contracts import JobStatus


REQUIRED_HEAT_LABELS = {
    "SOLANA_HOT",
    "SOLANA_WARM",
    "SOLANA_NEUTRAL",
    "SOLANA_COOL",
    "SOLANA_COLD",
    "SOLANA_CONGESTED",
    "SOLANA_QUIET",
    "SOLANA_UNKNOWN",
}

REQUIRED_ACTIVITY_LABELS = {
    "ACTIVITY_SURGING",
    "ACTIVITY_ELEVATED",
    "ACTIVITY_NORMAL",
    "ACTIVITY_WEAK",
    "ACTIVITY_DEAD",
    "ACTIVITY_UNKNOWN",
}

REQUIRED_LIQUIDITY_LABELS = {
    "LIQUIDITY_EXPANDING",
    "LIQUIDITY_STABLE",
    "LIQUIDITY_THINNING",
    "LIQUIDITY_STRESSED",
    "LIQUIDITY_UNKNOWN",
}

REQUIRED_CONGESTION_LABELS = {
    "CONGESTION_LOW",
    "CONGESTION_NORMAL",
    "CONGESTION_HIGH",
    "CONGESTION_SEVERE",
    "CONGESTION_UNKNOWN",
}

REQUIRED_QUALITY_LABELS = {
    "CHAIN_HEAT_CONTEXT_CLEAN",
    "CHAIN_HEAT_CONTEXT_PARTIAL",
    "CHAIN_HEAT_CONTEXT_STALE",
    "CHAIN_HEAT_CONTEXT_CONFLICTING",
    "CHAIN_HEAT_CONTEXT_UNKNOWN",
    "CHAIN_HEAT_CONTEXT_DO_NOT_USE_FOR_MEMORY",
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


class Phase8SolanaChainHeatEngineTest(unittest.TestCase):
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

    def full_payload(
        self,
        *,
        captured_at=None,
        sol_change_24h=5.0,
        hot_pairs=48,
        new_pairs=90,
        meme_volume=60_000_000,
        meme_liquidity=12_000_000,
        dex_volume=1_500_000_000,
        sol_volume=2_000_000_000,
        tx_count=30_000_000,
        priority_fee="normal",
        congestion="normal",
    ):
        when = captured_at or self.now
        return {
            "captured_at": when.isoformat(),
            "assets": {
                "solana": {
                    "market_data": {
                    "current_price": {"usd": 150},
                    "price_change_percentage_24h": sol_change_24h,
                    "price_change_percentage_7d": 12.0,
                    "total_volume": {"usd": sol_volume},
                    },
                    "price_change_percentage_1h": 1.0,
                }
            },
            "network_context": {
                "active_addresses": 1_400_000,
                "tx_count_24h": tx_count,
                "priority_fee_context": priority_fee,
                "congestion_context": congestion,
                "new_token_count": 5000,
            },
            "liquidity_context": {
                "tvl_usd": 4_800_000_000,
                "dex_volume_24h": dex_volume,
                "stablecoin_supply": 3_500_000_000,
            },
            "meme_context": {
                "hot_pair_count": hot_pairs,
                "meme_volume_24h": meme_volume,
                "meme_liquidity_usd": meme_liquidity,
                "meme_new_pair_count": new_pairs,
                "meme_graduation_count": 15,
                "meme_failed_pair_count": 4,
            },
            "source_status": SourceStatus.COMPLETE.value,
            "data_quality_label": DataQualityLabel.CLEAN_DATA.value,
        }

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

    def test_market_regime_package_has_dunder_init_not_accidental_init(self):
        self.assertTrue((SRC_PATH / "printer_v1" / "market_regime" / "__init__.py").exists())
        self.assertFalse((SRC_PATH / "printer_v1" / "market_regime" / "init.py").exists())

    def test_chain_heat_files_import_successfully(self):
        self.assertTrue(inspect.ismodule(parser))
        self.assertTrue(inspect.ismodule(classifier))
        self.assertTrue(inspect.ismodule(recorder))
        self.assertTrue(inspect.ismodule(lookup))

    def test_required_contract_labels_exist(self):
        self.assertEqual({label.value for label in ChainHeatLabel}, REQUIRED_HEAT_LABELS)
        self.assertEqual({label.value for label in SolanaActivityLabel}, REQUIRED_ACTIVITY_LABELS)
        self.assertEqual({label.value for label in SolanaLiquidityLabel}, REQUIRED_LIQUIDITY_LABELS)
        self.assertEqual({label.value for label in SolanaCongestionLabel}, REQUIRED_CONGESTION_LABELS)
        self.assertEqual(
            {label.value for label in ChainHeatPayloadQualityLabel},
            REQUIRED_QUALITY_LABELS,
        )

    def test_migration_creates_chain_heat_table_without_forbidden_columns(self):
        self.assertIn("printer_solana_chain_heat_snapshots", self.table_names())
        forbidden_found = self.column_names("printer_solana_chain_heat_snapshots") & FORBIDDEN_COLUMNS
        self.assertEqual(forbidden_found, set())

    def test_parser_normalizes_fake_solana_context_payload(self):
        normalized = normalize_chain_heat_payload(self.full_payload(), self.now)
        self.assertEqual(normalized["sol_price_usd"], 150.0)
        self.assertEqual(normalized["solana_tx_count_24h"], 30_000_000)
        self.assertEqual(normalized["solana_dex_volume_24h"], 1_500_000_000.0)
        self.assertEqual(normalized["solana_meme_new_pair_count"], 90)

    def test_parser_labels_missing_critical_context_as_not_clean(self):
        payload = {"captured_at": self.now.isoformat()}
        self.assertIn(
            validate_chain_heat_payload(payload, self.now),
            {
                ChainHeatPayloadQualityLabel.CHAIN_HEAT_CONTEXT_PARTIAL,
                ChainHeatPayloadQualityLabel.CHAIN_HEAT_CONTEXT_UNKNOWN,
                ChainHeatPayloadQualityLabel.CHAIN_HEAT_CONTEXT_DO_NOT_USE_FOR_MEMORY,
            },
        )

    def test_stale_chain_heat_payload_is_labeled_stale(self):
        payload = self.full_payload(captured_at=self.now - timedelta(hours=4))
        self.assertEqual(
            validate_chain_heat_payload(payload, self.now),
            ChainHeatPayloadQualityLabel.CHAIN_HEAT_CONTEXT_STALE,
        )

    def test_classifier_identifies_hot_warm_neutral_cool_cold_congested_quiet_unknown(self):
        hot = normalize_chain_heat_payload(self.full_payload(), self.now)
        warm = normalize_chain_heat_payload(
            self.full_payload(sol_change_24h=2.5, hot_pairs=24, new_pairs=38, meme_volume=10_000_000, meme_liquidity=4_000_000),
            self.now,
        )
        neutral = normalize_chain_heat_payload(
            self.full_payload(sol_change_24h=0.5, hot_pairs=12, new_pairs=22, meme_volume=7_000_000, meme_liquidity=5_000_000, dex_volume=400_000_000, sol_volume=500_000_000, tx_count=12_000_000),
            self.now,
        )
        cool = normalize_chain_heat_payload(
            self.full_payload(sol_change_24h=-1, hot_pairs=6, new_pairs=12, meme_volume=3_000_000, meme_liquidity=1_500_000, dex_volume=350_000_000),
            self.now,
        )
        cold = normalize_chain_heat_payload(
            self.full_payload(sol_change_24h=-4, hot_pairs=5, new_pairs=10, meme_volume=700_000, meme_liquidity=300_000, dex_volume=80_000_000, sol_volume=100_000_000, tx_count=5_000_000),
            self.now,
        )
        congested = normalize_chain_heat_payload(
            self.full_payload(priority_fee="high", congestion="congested"),
            self.now,
        )
        quiet = normalize_chain_heat_payload(
            self.full_payload(sol_change_24h=0.1, hot_pairs=1, new_pairs=3, meme_volume=500_000, meme_liquidity=3_000_000, dex_volume=50_000_000, sol_volume=100_000_000, tx_count=4_000_000),
            self.now,
        )
        self.assertEqual(classify_chain_heat(hot), ChainHeatLabel.SOLANA_HOT)
        self.assertEqual(classify_chain_heat(warm), ChainHeatLabel.SOLANA_WARM)
        self.assertEqual(classify_chain_heat(neutral), ChainHeatLabel.SOLANA_NEUTRAL)
        self.assertEqual(classify_chain_heat(cool), ChainHeatLabel.SOLANA_COOL)
        self.assertEqual(classify_chain_heat(cold), ChainHeatLabel.SOLANA_COLD)
        self.assertEqual(classify_chain_heat(congested), ChainHeatLabel.SOLANA_CONGESTED)
        self.assertEqual(classify_chain_heat(quiet), ChainHeatLabel.SOLANA_QUIET)
        self.assertEqual(classify_chain_heat({}), ChainHeatLabel.SOLANA_UNKNOWN)

    def test_dirty_stale_conflicting_context_cannot_support_clean_memory(self):
        dirty = normalize_chain_heat_payload(self.full_payload(), self.now)
        dirty["data_quality_label"] = DataQualityLabel.DIRTY_DATA.value
        stale = normalize_chain_heat_payload(
            self.full_payload(captured_at=self.now - timedelta(hours=4)),
            self.now,
        )
        conflicting = normalize_chain_heat_payload(self.full_payload(), self.now)
        conflicting["source_status"] = SourceStatus.CONFLICTING.value
        for payload in (dirty, stale, conflicting):
            self.assertFalse(chain_heat_context_can_support_clean_memory(payload, self.now))

    def test_record_chain_heat_snapshot_inserts_and_dedupes_row(self):
        created, row_id = record_chain_heat_snapshot(self.db_path, self.full_payload(), self.now)
        duplicate_created, duplicate_id = record_chain_heat_snapshot(
            self.db_path,
            self.full_payload(),
            self.now,
        )
        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(row_id, duplicate_id)
        self.assertEqual(self.count_rows("printer_solana_chain_heat_snapshots"), 1)

    def test_latest_chain_heat_snapshot_returns_newest_snapshot(self):
        record_chain_heat_snapshot(
            self.db_path,
            self.full_payload(captured_at=self.now - timedelta(minutes=30)),
            self.now,
        )
        record_chain_heat_snapshot(self.db_path, self.full_payload(captured_at=self.now), self.now)
        latest = get_latest_chain_heat_snapshot(self.db_path)
        self.assertEqual(latest["captured_at"], self.now.isoformat())

    def test_nearest_valid_lookup_returns_closest_clean_snapshot(self):
        before_time = self.now - timedelta(minutes=20)
        after_time = self.now + timedelta(minutes=10)
        record_chain_heat_snapshot(self.db_path, self.full_payload(captured_at=before_time), self.now)
        record_chain_heat_snapshot(self.db_path, self.full_payload(captured_at=after_time), self.now)
        nearest = lookup.find_nearest_chain_heat_snapshot(
            self.db_path,
            self.now,
            max_age_seconds=3600,
        )
        self.assertEqual(nearest["captured_at"], after_time.isoformat())

    def test_nearest_valid_lookup_rejects_stale_dirty_conflicting_context(self):
        dirty = self.full_payload(captured_at=self.now)
        dirty["data_quality_label"] = DataQualityLabel.DIRTY_DATA.value
        record_chain_heat_snapshot(self.db_path, dirty, self.now)
        self.assertIsNone(
            lookup.find_nearest_chain_heat_snapshot(
                self.db_path,
                self.now,
                max_age_seconds=3600,
            )
        )

    def test_scheduler_integration_creates_rows_only(self):
        result, job_id = enqueue_chain_heat_refresh_job(
            self.db_path,
            self.now + timedelta(minutes=20),
            reason="phase8_test",
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
        record_chain_heat_snapshot(self.db_path, self.full_payload(), self.now)
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

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
from printer_v1.market_regime import classifier, parser, recorder
from printer_v1.market_regime.contracts import MarketPayloadQualityLabel
from printer_v1.market_regime.recorder import record_market_regime_snapshot


FORBIDDEN_SOURCE_FRAGMENTS = (
    "requests.get",
    "requests.post",
    "httpx",
    "aiohttp",
    "urllib.request",
    "while True",
    "APScheduler",
    "confidence",
    "weighted",
    "buy_signal",
    "wallet",
    "signature",
    "live_execution",
)


class PostRCMarketRegimeExistingContextTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "market-regime.sqlite3"
        apply_migrations(self.db_path)
        self.now = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)

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
            return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def table_exists(self, table):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
            return row is not None

    def latest_market(self):
        with self.connect() as connection:
            return connection.execute(
                """
                SELECT *
                FROM printer_market_regime_snapshots
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

    def market_payload(self, *, captured_at=None, btc_24h=3.0, sol_24h=5.0, fear_value=66, **overrides):
        when = captured_at or self.now
        payload = {
            "captured_at": when.isoformat(),
            "assets": {
                "bitcoin": {
                    "market_data": {
                        "current_price": {"usd": 65000},
                        "price_change_percentage_24h": btc_24h,
                        "price_change_percentage_7d": 6.0,
                    },
                    "price_change_percentage_1h": 0.4,
                },
                "ethereum": {
                    "market_data": {
                        "current_price": {"usd": 3500},
                        "price_change_percentage_24h": btc_24h * 0.6,
                        "price_change_percentage_7d": 4.0,
                    },
                },
                "solana": {
                    "market_data": {
                        "current_price": {"usd": 150},
                        "price_change_percentage_24h": sol_24h,
                        "price_change_percentage_7d": 10.0,
                        "total_volume": {"usd": 1_800_000_000},
                    },
                    "price_change_percentage_1h": 0.8,
                },
            },
            "fear_greed": {"value": fear_value, "label": "Greed"},
            "solana_context": {
                "solana_tvl_usd": 4_700_000_000,
                "dex_volume_context": "steady",
                "stablecoin_context": "steady",
                "tracked_solana_meme_volume": 12_000_000,
                "tracked_solana_meme_liquidity": 3_500_000,
                "tracked_solana_hot_pair_count": 22,
                "tracked_solana_new_pair_count": 40,
            },
            "source_status": SourceStatus.COMPLETE.value,
            "data_quality_label": DataQualityLabel.CLEAN_DATA.value,
        }
        payload.update(overrides)
        return payload

    def test_risk_on_fixture_maps_to_risk_on_market_regime(self):
        created, _row_id = record_market_regime_snapshot(
            self.db_path,
            self.market_payload(),
            self.now,
        )
        row = self.latest_market()

        self.assertTrue(created)
        self.assertEqual(row["market_regime_label"], "RISK_ON")
        self.assertEqual(row["market_payload_quality_label"], "MARKET_CONTEXT_CLEAN")
        self.assertEqual(row["source_status"], "COMPLETE")
        self.assertEqual(row["data_quality_label"], "CLEAN_DATA")

    def test_risk_off_neutral_and_volatile_fixtures_map_categorically(self):
        cases = [
            (self.market_payload(captured_at=self.now + timedelta(minutes=1), btc_24h=-4, sol_24h=-6, fear_value=28), "RISK_OFF"),
            (self.market_payload(captured_at=self.now + timedelta(minutes=2), btc_24h=0.2, sol_24h=-0.4, fear_value=50), "CHOPPY"),
            (self.market_payload(captured_at=self.now + timedelta(minutes=3), btc_24h=5, sol_24h=-5, fear_value=50), "VOLATILE"),
        ]

        for payload, expected in cases:
            record_market_regime_snapshot(self.db_path, payload, self.now)
            row = self.latest_market()
            self.assertEqual(row["market_regime_label"], expected)
            self.assertEqual(row["market_payload_quality_label"], "MARKET_CONTEXT_CLEAN")

    def test_missing_stale_failed_conflicting_and_dirty_context_remain_unknown_or_audit_only(self):
        cases = [
            self.market_payload(captured_at=self.now + timedelta(minutes=4), assets={}, fear_greed={}, solana_context={}),
            self.market_payload(captured_at=self.now - timedelta(hours=4)),
            self.market_payload(captured_at=self.now + timedelta(minutes=5), source_status=SourceStatus.FAILED.value),
            self.market_payload(captured_at=self.now + timedelta(minutes=6), source_status=SourceStatus.CONFLICTING.value),
            self.market_payload(captured_at=self.now + timedelta(minutes=7), data_quality_label=DataQualityLabel.DIRTY_DATA.value),
        ]

        for payload in cases:
            record_market_regime_snapshot(self.db_path, payload, self.now)
            row = self.latest_market()
            self.assertEqual(row["market_regime_label"], "UNKNOWN")
            self.assertIn(
                row["market_payload_quality_label"],
                {
                    MarketPayloadQualityLabel.MARKET_CONTEXT_UNKNOWN.value,
                    MarketPayloadQualityLabel.MARKET_CONTEXT_STALE.value,
                    MarketPayloadQualityLabel.MARKET_CONTEXT_CONFLICTING.value,
                    MarketPayloadQualityLabel.MARKET_CONTEXT_DO_NOT_USE_FOR_MEMORY.value,
                },
            )

    def test_market_context_alone_does_not_create_downstream_unlocks(self):
        record_market_regime_snapshot(self.db_path, self.market_payload(), self.now)

        self.assertEqual(self.count_rows("printer_memory_windows"), 0)
        self.assertEqual(self.count_rows("printer_memory_retrieval_queries"), 0)
        self.assertEqual(self.count_rows("printer_memory_retrieval_matches"), 0)
        self.assertEqual(self.count_rows("printer_paper_decisions"), 0)
        self.assertEqual(self.count_rows("printer_paper_positions"), 0)
        self.assertEqual(self.count_rows("printer_paper_trade_events"), 0)
        if self.table_exists("printer_paper_pl_calculations"):
            self.assertEqual(self.count_rows("printer_paper_pl_calculations"), 0)

    def test_market_modules_do_not_add_live_scoring_or_direct_trade_capability(self):
        source_text = "\n".join(
            inspect.getsource(module)
            for module in (parser, classifier, recorder)
        )
        for fragment in FORBIDDEN_SOURCE_FRAGMENTS:
            self.assertNotIn(fragment, source_text)


if __name__ == "__main__":
    unittest.main()

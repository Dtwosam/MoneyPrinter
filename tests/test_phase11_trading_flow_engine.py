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
from printer_v1.scheduler.contracts import JobStatus
from printer_v1.trading_flow import classifier, lookup, parser, recorder
from printer_v1.trading_flow.classifier import (
    classify_flow_direction,
    classify_flow_pressure,
    classify_imbalance,
    classify_trading_flow_payload_quality,
    classify_tx_activity,
    classify_volume_activity,
    classify_wallet_participation,
    trading_flow_context_can_support_clean_memory,
)
from printer_v1.trading_flow.contracts import (
    FlowDirectionLabel,
    FlowMemoryGateLabel,
    FlowPressureLabel,
    ImbalanceLabel,
    TradingFlowPayloadQualityLabel,
    TxActivityLabel,
    VolumeActivityLabel,
    WalletParticipationLabel,
)
from printer_v1.trading_flow.parser import normalize_trading_flow_payload, validate_trading_flow_payload
from printer_v1.trading_flow.recorder import (
    enqueue_trading_flow_refresh_job,
    get_latest_trading_flow_snapshot,
    record_trading_flow_from_token_snapshot,
    record_trading_flow_snapshot,
)


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


class Phase11TradingFlowEngineTest(unittest.TestCase):
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
                "INSERT INTO printer_tokens (token_mint, chain) VALUES ('flow-mint', 'solana')"
            ).lastrowid
            pair_id = connection.execute(
                """
                INSERT INTO printer_pairs (token_id, pair_address, dex, pool_source)
                VALUES (?, 'flow-pair', 'raydium', 'local')
                """,
                (token_id,),
            ).lastrowid
        return int(token_id), int(pair_id)

    def payload(self, *, captured_at=None, **overrides):
        base = {
            "token": {"token_id": self.token_id, "mint": "flow-mint"},
            "pair": {"pair_id": self.pair_id, "pair_address": "flow-pair"},
            "captured_at": (captured_at or self.now).isoformat(),
            "price_usd": 0.01,
            "liquidity_usd": 120_000,
            "volume": {
                "m5": 125_000,
                "m15": 260_000,
                "h1": 600_000,
                "h4": 900_000,
                "h24": 1_800_000,
                "buy_volume_5m": 90_000,
                "sell_volume_5m": 30_000,
                "buy_volume_15m": 180_000,
                "sell_volume_15m": 60_000,
            },
            "txns": {
                "m5": 150,
                "m15": 320,
                "h1": 900,
                "h4": 1200,
                "h24": 3000,
                "m5_buys": 110,
                "m5_sells": 35,
                "m15_buys": 230,
                "m15_sells": 90,
            },
            "wallets": {
                "unique_wallets_5m": 45,
                "unique_wallets_15m": 80,
                "unique_wallets_1h": 150,
                "unique_wallets_24h": 400,
                "new_wallets_5m": 25,
                "new_wallets_15m": 50,
                "repeat_wallets_5m": 8,
                "repeat_wallets_15m": 12,
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

    def clean_payload(self, **overrides):
        return normalize_trading_flow_payload(self.payload(**overrides), self.now)

    def test_liquidity_exit_package_has_dunder_init_not_accidental_init(self):
        self.assertTrue((SRC_PATH / "printer_v1" / "liquidity_exit" / "__init__.py").exists())
        self.assertFalse((SRC_PATH / "printer_v1" / "liquidity_exit" / "init.py").exists())

    def test_trading_flow_files_import_successfully(self):
        self.assertTrue(inspect.ismodule(parser))
        self.assertTrue(inspect.ismodule(classifier))
        self.assertTrue(inspect.ismodule(recorder))
        self.assertTrue(inspect.ismodule(lookup))

    def test_required_contract_labels_exist(self):
        self.assertEqual({label.value for label in FlowDirectionLabel}, {
            "FLOW_ACCUMULATION", "FLOW_DISTRIBUTION", "FLOW_ROTATION", "FLOW_EXHAUSTION", "FLOW_CHOPPY", "FLOW_WASH_LIKE", "FLOW_UNKNOWN"
        })
        self.assertEqual({label.value for label in FlowPressureLabel}, {
            "PRESSURE_STRONG_INFLOW", "PRESSURE_MODERATE_INFLOW", "PRESSURE_BALANCED", "PRESSURE_MODERATE_OUTFLOW", "PRESSURE_STRONG_OUTFLOW", "PRESSURE_UNKNOWN"
        })
        self.assertEqual({label.value for label in ImbalanceLabel}, {
            "IMBALANCE_BUY_HEAVY", "IMBALANCE_SELL_HEAVY", "IMBALANCE_BALANCED", "IMBALANCE_NOISY", "IMBALANCE_UNKNOWN"
        })
        self.assertEqual({label.value for label in VolumeActivityLabel}, {
            "VOLUME_SURGING", "VOLUME_ELEVATED", "VOLUME_NORMAL", "VOLUME_WEAK", "VOLUME_DEAD", "VOLUME_UNKNOWN"
        })
        self.assertEqual({label.value for label in TxActivityLabel}, {
            "TX_ACTIVITY_SURGING", "TX_ACTIVITY_ELEVATED", "TX_ACTIVITY_NORMAL", "TX_ACTIVITY_WEAK", "TX_ACTIVITY_DEAD", "TX_ACTIVITY_UNKNOWN"
        })
        self.assertEqual({label.value for label in WalletParticipationLabel}, {
            "WALLETS_BROAD_PARTICIPATION", "WALLETS_NARROW_PARTICIPATION", "WALLETS_CONCENTRATED", "WALLETS_WASH_LIKE", "WALLETS_UNKNOWN"
        })
        self.assertEqual({label.value for label in TradingFlowPayloadQualityLabel}, {
            "TRADING_FLOW_CONTEXT_CLEAN", "TRADING_FLOW_CONTEXT_PARTIAL", "TRADING_FLOW_CONTEXT_STALE", "TRADING_FLOW_CONTEXT_CONFLICTING", "TRADING_FLOW_CONTEXT_UNKNOWN", "TRADING_FLOW_CONTEXT_DO_NOT_USE_FOR_MEMORY"
        })
        self.assertEqual({label.value for label in FlowMemoryGateLabel}, {
            "FLOW_CONTEXT_ACCEPTABLE", "FLOW_CONTEXT_CAUTION", "FLOW_CONTEXT_AUDIT_ONLY", "FLOW_CONTEXT_DO_NOT_TRAIN"
        })

    def test_migration_creates_table_without_forbidden_columns(self):
        self.assertIn("printer_trading_flow_snapshots", self.table_names())
        self.assertEqual(
            self.column_names("printer_trading_flow_snapshots") & FORBIDDEN_COLUMNS,
            set(),
        )

    def test_parser_normalizes_fake_dex_and_geckoterminal_payload(self):
        normalized = normalize_trading_flow_payload(self.payload(), self.now)
        self.assertEqual(normalized["token_mint"], "flow-mint")
        self.assertEqual(normalized["volume_5m"], 125000.0)
        self.assertEqual(normalized["txns_5m"], 150)
        self.assertEqual(normalized["buys_5m"], 110)
        self.assertEqual(normalized["unique_wallets_5m"], 45)

    def test_parser_normalizes_fake_pumpportal_and_token_snapshot_payloads(self):
        flat = self.payload(
            volume_5m=80_000,
            txns_5m=75,
            buys_5m=50,
            sells_5m=20,
            buy_volume_5m=55_000,
            sell_volume_5m=20_000,
            unique_wallets_5m=20,
        )
        normalized = normalize_trading_flow_payload(flat, self.now)
        self.assertEqual(normalized["volume_5m"], 80000.0)
        self.assertEqual(normalized["txns_5m"], 75)
        with self.connect() as connection:
            snapshot_id = connection.execute(
                """
                INSERT INTO printer_token_snapshots (
                    token_id, pair_id, captured_at, tracking_lane, snapshot_mode,
                    price_usd, liquidity_usd, volume_5m, volume_15m, volume_1h,
                    volume_4h, volume_24h, txns_5m, txns_15m, txns_1h, txns_4h,
                    txns_24h, source_status, data_quality_label
                )
                VALUES (?, ?, ?, 'TRACK_FAST', 'NORMAL_MODE', 0.01, 120000, 125000,
                    260000, 600000, 900000, 1800000, 150, 320, 900, 1200, 3000,
                    'COMPLETE', 'CLEAN_DATA')
                """,
                (self.token_id, self.pair_id, self.now.isoformat()),
            ).lastrowid
        created, row_id = record_trading_flow_from_token_snapshot(
            self.db_path,
            int(snapshot_id),
            supplemental_payload=self.payload(),
            now=self.now,
        )
        self.assertTrue(created)
        self.assertGreater(row_id, 0)

    def test_parser_labels_missing_critical_and_stale_context(self):
        self.assertIn(
            validate_trading_flow_payload({"captured_at": self.now.isoformat()}, self.now),
            {
                TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_PARTIAL,
                TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_UNKNOWN,
                TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_DO_NOT_USE_FOR_MEMORY,
            },
        )
        self.assertEqual(
            validate_trading_flow_payload(
                self.payload(captured_at=self.now - timedelta(hours=3)),
                self.now,
            ),
            TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_STALE,
        )

    def test_classifier_identifies_direction_variants(self):
        accumulation = self.clean_payload()
        distribution = self.clean_payload(
            txns={"m5_buys": 20, "m5_sells": 90},
            volume={"buy_volume_5m": 20_000, "sell_volume_5m": 90_000},
        )
        rotation = self.clean_payload(
            txns={"m5_buys": 120, "m5_sells": 40},
            volume={"buy_volume_5m": 20_000, "sell_volume_5m": 90_000},
        )
        exhaustion = self.clean_payload(
            volume={"m5": 700, "buy_volume_5m": 300, "sell_volume_5m": 300},
            txns={"m5": 4, "m5_buys": 2, "m5_sells": 2},
        )
        wash = self.clean_payload(wallets={"unique_wallets_5m": 2, "repeat_wallets_5m": 8})
        self.assertEqual(classify_flow_direction(accumulation), FlowDirectionLabel.FLOW_ACCUMULATION)
        self.assertEqual(classify_flow_direction(distribution), FlowDirectionLabel.FLOW_DISTRIBUTION)
        self.assertEqual(classify_flow_direction(rotation), FlowDirectionLabel.FLOW_ROTATION)
        self.assertEqual(classify_flow_direction(exhaustion), FlowDirectionLabel.FLOW_EXHAUSTION)
        self.assertEqual(classify_flow_direction(wash), FlowDirectionLabel.FLOW_WASH_LIKE)
        self.assertEqual(classify_flow_direction({}), FlowDirectionLabel.FLOW_UNKNOWN)

    def test_classifier_identifies_pressure_and_imbalance(self):
        strong_in = self.clean_payload()
        strong_out = self.clean_payload(
            txns={"m5_buys": 20, "m5_sells": 90},
            volume={"buy_volume_5m": 20_000, "sell_volume_5m": 90_000},
        )
        balanced = self.clean_payload(
            txns={"m5_buys": 50, "m5_sells": 50},
            volume={"buy_volume_5m": 50_000, "sell_volume_5m": 50_000},
        )
        noisy = self.clean_payload(
            txns={"m5_buys": 100, "m5_sells": 40},
            volume={"buy_volume_5m": 20_000, "sell_volume_5m": 90_000},
        )
        self.assertEqual(classify_flow_pressure(strong_in), FlowPressureLabel.PRESSURE_STRONG_INFLOW)
        self.assertEqual(classify_flow_pressure(strong_out), FlowPressureLabel.PRESSURE_STRONG_OUTFLOW)
        self.assertEqual(classify_imbalance(strong_in), ImbalanceLabel.IMBALANCE_BUY_HEAVY)
        self.assertEqual(classify_imbalance(strong_out), ImbalanceLabel.IMBALANCE_SELL_HEAVY)
        self.assertEqual(classify_imbalance(balanced), ImbalanceLabel.IMBALANCE_BALANCED)
        self.assertEqual(classify_imbalance(noisy), ImbalanceLabel.IMBALANCE_NOISY)
        self.assertEqual(classify_imbalance({}), ImbalanceLabel.IMBALANCE_UNKNOWN)

    def test_classifier_identifies_activity_and_wallet_participation(self):
        volume_cases = [
            (125_000, VolumeActivityLabel.VOLUME_SURGING),
            (30_000, VolumeActivityLabel.VOLUME_ELEVATED),
            (7_500, VolumeActivityLabel.VOLUME_NORMAL),
            (700, VolumeActivityLabel.VOLUME_WEAK),
            (100, VolumeActivityLabel.VOLUME_DEAD),
        ]
        for value, expected in volume_cases:
            self.assertEqual(classify_volume_activity({"volume_5m": value}), expected)
        tx_cases = [
            (150, TxActivityLabel.TX_ACTIVITY_SURGING),
            (50, TxActivityLabel.TX_ACTIVITY_ELEVATED),
            (20, TxActivityLabel.TX_ACTIVITY_NORMAL),
            (5, TxActivityLabel.TX_ACTIVITY_WEAK),
            (1, TxActivityLabel.TX_ACTIVITY_DEAD),
        ]
        for value, expected in tx_cases:
            self.assertEqual(classify_tx_activity({"txns_5m": value}), expected)
        self.assertEqual(classify_volume_activity({}), VolumeActivityLabel.VOLUME_UNKNOWN)
        self.assertEqual(classify_tx_activity({}), TxActivityLabel.TX_ACTIVITY_UNKNOWN)
        self.assertEqual(classify_wallet_participation({"unique_wallets_5m": 30}), WalletParticipationLabel.WALLETS_BROAD_PARTICIPATION)
        self.assertEqual(classify_wallet_participation({"unique_wallets_5m": 8}), WalletParticipationLabel.WALLETS_NARROW_PARTICIPATION)
        self.assertEqual(classify_wallet_participation({"unique_wallets_5m": 2}), WalletParticipationLabel.WALLETS_CONCENTRATED)
        self.assertEqual(classify_wallet_participation({"unique_wallets_5m": 2, "repeat_wallets_5m": 8}), WalletParticipationLabel.WALLETS_WASH_LIKE)
        self.assertEqual(classify_wallet_participation({}), WalletParticipationLabel.WALLETS_UNKNOWN)

    def test_dirty_stale_conflicting_context_cannot_support_clean_memory(self):
        dirty = self.clean_payload()
        dirty["data_quality_label"] = DataQualityLabel.DIRTY_DATA.value
        stale = self.clean_payload(captured_at=self.now - timedelta(hours=3))
        conflicting = self.clean_payload()
        conflicting["source_status"] = SourceStatus.CONFLICTING.value
        for payload in (dirty, stale, conflicting):
            self.assertFalse(trading_flow_context_can_support_clean_memory(payload, self.now))
            self.assertNotEqual(
                classify_trading_flow_payload_quality(payload, self.now),
                TradingFlowPayloadQualityLabel.TRADING_FLOW_CONTEXT_CLEAN,
            )

    def test_wash_like_flow_blocks_memory_without_paper_decisions(self):
        wash = self.payload(wallets={"unique_wallets_5m": 2, "repeat_wallets_5m": 8})
        record_trading_flow_snapshot(self.db_path, wash, self.now)
        latest = get_latest_trading_flow_snapshot(
            self.db_path,
            token_id=self.token_id,
            pair_id=self.pair_id,
        )
        self.assertTrue(lookup.trading_flow_snapshot_blocks_clean_memory(latest))
        self.assertEqual(self.count_rows("printer_paper_decisions"), 0)

    def test_record_dedupe_latest_and_nearest_lookup(self):
        created, row_id = record_trading_flow_snapshot(self.db_path, self.payload(), self.now)
        duplicate_created, duplicate_id = record_trading_flow_snapshot(self.db_path, self.payload(), self.now)
        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(row_id, duplicate_id)
        after = self.now + timedelta(minutes=10)
        record_trading_flow_snapshot(self.db_path, self.payload(captured_at=after), self.now)
        latest = get_latest_trading_flow_snapshot(self.db_path, token_id=self.token_id, pair_id=self.pair_id)
        nearest = lookup.find_nearest_trading_flow_snapshot(
            self.db_path,
            self.token_id,
            self.pair_id,
            self.now + timedelta(minutes=8),
            max_age_seconds=3600,
        )
        self.assertEqual(latest["captured_at"], after.isoformat())
        self.assertEqual(nearest["captured_at"], after.isoformat())

    def test_nearest_lookup_rejects_bad_context(self):
        dirty = self.payload()
        dirty["data_quality_label"] = DataQualityLabel.DIRTY_DATA.value
        stale = self.payload(captured_at=self.now - timedelta(hours=3))
        conflicting = self.payload()
        conflicting["source_status"] = SourceStatus.CONFLICTING.value
        wash = self.payload(wallets={"unique_wallets_5m": 2, "repeat_wallets_5m": 8})
        for payload in (dirty, stale, conflicting, wash):
            record_trading_flow_snapshot(self.db_path, payload, self.now)
        self.assertIsNone(
            lookup.find_nearest_trading_flow_snapshot(
                self.db_path,
                self.token_id,
                self.pair_id,
                self.now,
                max_age_seconds=3600,
            )
        )

    def test_scheduler_integration_creates_rows_only(self):
        result, job_id = enqueue_trading_flow_refresh_job(
            self.db_path,
            self.token_id,
            self.pair_id,
            self.now + timedelta(minutes=5),
            reason="phase11_test",
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
        record_trading_flow_snapshot(self.db_path, self.payload(), self.now)
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

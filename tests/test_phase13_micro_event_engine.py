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
from printer_v1.micro_event import classifier, lookup, parser, recorder
from printer_v1.micro_event.classifier import (
    classify_holding_to_15m_result,
    classify_late_buy_trap,
    classify_micro_event_move,
    classify_micro_event_payload_quality,
    classify_micro_event_state,
    classify_micro_exit_realism,
    micro_event_context_blocks_clean_micro_profit,
    micro_event_context_can_support_clean_memory,
    micro_event_context_is_tradable_support_evidence,
)
from printer_v1.micro_event.contracts import (
    HeldTo15mResultLabel,
    LateBuyTrapLabel,
    MicroEventMemoryGateLabel,
    MicroEventMoveLabel,
    MicroEventPayloadQualityLabel,
    MicroEventStateLabel,
    MicroExitRealismLabel,
)
from printer_v1.micro_event.parser import normalize_micro_event_payload, validate_micro_event_payload
from printer_v1.micro_event.recorder import (
    enqueue_micro_event_refresh_job,
    get_latest_micro_event,
    record_micro_event,
    record_micro_event_from_token_snapshots,
)
from printer_v1.scheduler.contracts import JobStatus


FORBIDDEN_COLUMNS = {"score", "confidence", "rank", "rating", "weight", "wallet_address", "private_key", "signed_tx", "live_trade"}
FORBIDDEN_FRAGMENTS = {"score", "confidence", "rank", "rating", "weight", "private_key", "signed_tx", "live_trade"}


class Phase13MicroEventEngineTest(unittest.TestCase):
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
                "INSERT INTO printer_tokens (token_mint, chain) VALUES ('micro-mint', 'solana')"
            ).lastrowid
            pair_id = connection.execute(
                "INSERT INTO printer_pairs (token_id, pair_address, dex, pool_source) VALUES (?, 'micro-pair', 'raydium', 'local')",
                (token_id,),
            ).lastrowid
        return int(token_id), int(pair_id)

    def payload(self, *, detected_at=None, **overrides):
        start = self.now - timedelta(minutes=5)
        detected = detected_at or self.now
        base = {
            "token": {"token_id": self.token_id, "mint": "micro-mint"},
            "pair": {"pair_id": self.pair_id, "pair_address": "micro-pair"},
            "detected_at": detected.isoformat(),
            "event_window_start_at": start.isoformat(),
            "event_window_end_at": detected.isoformat(),
            "hold_check_15m_at": (start + timedelta(minutes=15)).isoformat(),
            "chart": {"price_start": 1.0, "price_high": 1.35, "price_low": 0.98, "price_end": 1.3},
            "flow": {"volume_5m": 150000, "txns_5m": 150, "buys_5m": 110, "sells_5m": 40, "buy_volume_5m": 90000, "sell_volume_5m": 30000},
            "liquidity": {
                "start_usd": 120000,
                "end_usd": 130000,
                "exit_realism_label": "EXIT_REALISTIC",
                "slippage_label": "SLIPPAGE_LOW",
                "price_impact_label": "PRICE_IMPACT_LOW",
                "route_label": "ROUTE_AVAILABLE",
                "liquidity_state_label": "LIQUIDITY_USABLE",
            },
            "hold_15m": {"held_to_15m_price_change_percent": 30, "held_to_15m_liquidity_usd": 125000},
            "safety_status_label": "SAFETY_CLEAN",
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
        return normalize_micro_event_payload(self.payload(**overrides), self.now)

    def count_rows(self, table):
        with self.connect() as connection:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def column_names(self, table_name):
        with self.connect() as connection:
            return {row[1] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()}

    def table_names(self):
        with self.connect() as connection:
            return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}

    def test_chart_volatility_package_has_dunder_init_not_accidental_init(self):
        self.assertTrue((SRC_PATH / "printer_v1" / "chart_volatility" / "__init__.py").exists())
        self.assertFalse((SRC_PATH / "printer_v1" / "chart_volatility" / "init.py").exists())

    def test_micro_event_files_import_successfully(self):
        self.assertTrue(inspect.ismodule(parser))
        self.assertTrue(inspect.ismodule(classifier))
        self.assertTrue(inspect.ismodule(recorder))
        self.assertTrue(inspect.ismodule(lookup))

    def test_required_contract_labels_exist(self):
        self.assertEqual({label.value for label in MicroEventStateLabel}, {
            "NO_MICRO_EVENT", "FAST_MICRO_PUMP", "TRADABLE_MICRO_PUMP", "UNTRADABLE_MICRO_PUMP", "FAKE_PUMP_WITH_EXIT", "FAKE_PUMP_NO_EXIT", "FAST_PUMP_DUMP", "WICK_PUMP", "WICK_ONLY_PUMP", "LATE_BUY_TRAP", "MICRO_PUMP_TO_SUSTAINED_PUMP", "MICRO_PUMP_TO_CONSOLIDATION", "MICRO_PUMP_TO_DEAD_TOKEN", "MICRO_EVENT_UNKNOWN"
        })
        self.assertEqual({label.value for label in MicroEventMoveLabel}, {
            "MOVE_FAST_UP", "MOVE_FAST_DOWN", "MOVE_SPIKE_AND_HOLD", "MOVE_SPIKE_AND_FADE", "MOVE_WICK_ONLY", "MOVE_ROUND_TRIP", "MOVE_NO_CLEAR_EVENT", "MOVE_UNKNOWN"
        })
        self.assertEqual({label.value for label in MicroExitRealismLabel}, {
            "MICRO_EXIT_REALISTIC", "MICRO_EXIT_POSSIBLE_WITH_SLIPPAGE", "MICRO_EXIT_FRAGILE", "MICRO_EXIT_UNREALISTIC", "MICRO_EXIT_NO_EXIT", "MICRO_EXIT_UNKNOWN"
        })
        self.assertEqual({label.value for label in LateBuyTrapLabel}, {
            "NO_LATE_BUY_TRAP", "POSSIBLE_LATE_BUY_TRAP", "CONFIRMED_LATE_BUY_TRAP", "LATE_BUY_TRAP_UNKNOWN"
        })
        # V2-9.7E.47 B2 adds exactly one categorical label for the measured
        # (+5%, +25%) band, which previously fell into HELD_TO_15M_UNKNOWN.
        self.assertEqual({label.value for label in HeldTo15mResultLabel}, {
            "HELD_TO_15M_CONTINUED", "HELD_TO_15M_MODERATE_CONTINUATION",
            "HELD_TO_15M_CONSOLIDATED", "HELD_TO_15M_FADED", "HELD_TO_15M_DUMPED",
            "HELD_TO_15M_DEAD", "HELD_TO_15M_UNKNOWN"
        })
        self.assertEqual({label.value for label in MicroEventPayloadQualityLabel}, {
            "MICRO_EVENT_CONTEXT_CLEAN", "MICRO_EVENT_CONTEXT_PARTIAL", "MICRO_EVENT_CONTEXT_STALE", "MICRO_EVENT_CONTEXT_CONFLICTING", "MICRO_EVENT_CONTEXT_UNKNOWN", "MICRO_EVENT_CONTEXT_DO_NOT_USE_FOR_MEMORY"
        })
        self.assertEqual({label.value for label in MicroEventMemoryGateLabel}, {
            "MICRO_EVENT_SUPPORT_EVIDENCE", "MICRO_EVENT_AUDIT_ONLY", "MICRO_EVENT_DO_NOT_TRAIN", "MICRO_EVENT_IGNORE"
        })

    def test_migration_creates_table_without_forbidden_columns(self):
        self.assertIn("printer_micro_events", self.table_names())
        self.assertEqual(self.column_names("printer_micro_events") & FORBIDDEN_COLUMNS, set())

    def test_parser_normalizes_payload_variants_and_snapshot_derived_payload(self):
        normalized = self.normalize()
        self.assertEqual(normalized["token_mint"], "micro-mint")
        self.assertEqual(round(normalized["price_change_5m_percent"], 2), 30.0)
        wick = self.normalize(chart={"price_start": 1.0, "price_high": 1.8, "price_end": 1.02})
        self.assertGreater(wick["wick_percent"], 50)
        dump = self.normalize(chart={"price_start": 1.0, "price_high": 1.4, "price_low": 0.65, "price_end": 0.75})
        self.assertLess(dump["price_change_5m_percent"], 0)
        with self.connect() as connection:
            for index, price in enumerate([1.0, 1.12, 1.25, 1.3]):
                connection.execute(
                    """
                    INSERT INTO printer_token_snapshots (
                        token_id, pair_id, captured_at, tracking_lane, snapshot_mode,
                        price_usd, liquidity_usd, volume_5m, txns_5m, source_status, data_quality_label
                    )
                    VALUES (?, ?, ?, 'TRACK_FAST', 'MICRO_EVENT_MODE', ?, 120000, 100000, 100, 'COMPLETE', 'CLEAN_DATA')
                    """,
                    (self.token_id, self.pair_id, (self.now - timedelta(minutes=3 - index)).isoformat(), price),
                )
        created, row_id = record_micro_event_from_token_snapshots(
            self.db_path,
            self.token_id,
            self.pair_id,
            self.now - timedelta(minutes=3),
            self.now,
            now=self.now,
        )
        self.assertTrue(created)
        self.assertGreater(row_id, 0)

    def test_parser_labels_missing_critical_and_stale_context(self):
        self.assertIn(
            validate_micro_event_payload({"detected_at": self.now.isoformat()}, self.now),
            {
                MicroEventPayloadQualityLabel.MICRO_EVENT_CONTEXT_PARTIAL,
                MicroEventPayloadQualityLabel.MICRO_EVENT_CONTEXT_UNKNOWN,
                MicroEventPayloadQualityLabel.MICRO_EVENT_CONTEXT_DO_NOT_USE_FOR_MEMORY,
            },
        )
        self.assertEqual(
            validate_micro_event_payload(self.payload(detected_at=self.now - timedelta(hours=3)), self.now),
            MicroEventPayloadQualityLabel.MICRO_EVENT_CONTEXT_STALE,
        )

    def test_classifier_identifies_event_states_and_moves(self):
        tradable = self.normalize(hold_15m={"held_to_15m_price_change_percent": 12})
        untradable = self.normalize(liquidity={"slippage_label": "SLIPPAGE_EXTREME"})
        no_exit = self.normalize(liquidity={"route_label": "ROUTE_NOT_AVAILABLE"})
        fade = self.normalize(chart={"price_start": 1.0, "price_high": 1.8, "price_end": 1.2}, hold_15m={"held_to_15m_price_change_percent": -12})
        dump = self.normalize(chart={"price_start": 1.0, "price_high": 1.4, "price_low": 0.65, "price_end": 0.75}, hold_15m={"held_to_15m_price_change_percent": -30})
        wick = self.normalize(chart={"price_start": 1.0, "price_high": 1.8, "price_end": 1.02}, hold_15m={"held_to_15m_price_change_percent": 0})
        trap = self.normalize(hold_15m={"held_to_15m_price_change_percent": -30})
        self.assertEqual(classify_micro_event_state(tradable), MicroEventStateLabel.TRADABLE_MICRO_PUMP)
        self.assertEqual(classify_micro_event_state(untradable), MicroEventStateLabel.UNTRADABLE_MICRO_PUMP)
        self.assertEqual(classify_micro_event_state(fade), MicroEventStateLabel.FAKE_PUMP_WITH_EXIT)
        self.assertEqual(classify_micro_event_state(no_exit), MicroEventStateLabel.FAKE_PUMP_NO_EXIT)
        self.assertEqual(classify_micro_event_state(dump), MicroEventStateLabel.FAST_PUMP_DUMP)
        self.assertEqual(classify_micro_event_state(wick), MicroEventStateLabel.WICK_ONLY_PUMP)
        self.assertEqual(classify_micro_event_state(trap), MicroEventStateLabel.LATE_BUY_TRAP)
        self.assertEqual(classify_micro_event_move(tradable), MicroEventMoveLabel.MOVE_SPIKE_AND_HOLD)
        self.assertEqual(classify_micro_event_move(fade), MicroEventMoveLabel.MOVE_SPIKE_AND_FADE)
        self.assertEqual(classify_micro_event_move(wick), MicroEventMoveLabel.MOVE_WICK_ONLY)

    def test_classifier_identifies_15m_outcomes_exit_realism_and_late_traps(self):
        self.assertEqual(classify_holding_to_15m_result({"held_to_15m_price_change_percent": 30}), HeldTo15mResultLabel.HELD_TO_15M_CONTINUED)
        self.assertEqual(classify_holding_to_15m_result({"held_to_15m_price_change_percent": 3}), HeldTo15mResultLabel.HELD_TO_15M_CONSOLIDATED)
        self.assertEqual(classify_holding_to_15m_result({"held_to_15m_price_change_percent": -15}), HeldTo15mResultLabel.HELD_TO_15M_FADED)
        self.assertEqual(classify_holding_to_15m_result({"held_to_15m_price_change_percent": -30}), HeldTo15mResultLabel.HELD_TO_15M_DUMPED)
        self.assertEqual(classify_holding_to_15m_result({"held_to_15m_price_change_percent": -50}), HeldTo15mResultLabel.HELD_TO_15M_DEAD)
        self.assertEqual(classify_micro_exit_realism({"route_label": "ROUTE_AVAILABLE", "slippage_label": "SLIPPAGE_LOW"}), MicroExitRealismLabel.MICRO_EXIT_REALISTIC)
        self.assertEqual(classify_micro_exit_realism({"slippage_label": "SLIPPAGE_MODERATE"}), MicroExitRealismLabel.MICRO_EXIT_POSSIBLE_WITH_SLIPPAGE)
        self.assertEqual(classify_micro_exit_realism({"slippage_label": "SLIPPAGE_HIGH"}), MicroExitRealismLabel.MICRO_EXIT_FRAGILE)
        self.assertEqual(classify_micro_exit_realism({"slippage_label": "SLIPPAGE_EXTREME"}), MicroExitRealismLabel.MICRO_EXIT_UNREALISTIC)
        self.assertEqual(classify_micro_exit_realism({"route_label": "ROUTE_NOT_AVAILABLE"}), MicroExitRealismLabel.MICRO_EXIT_NO_EXIT)
        self.assertEqual(classify_late_buy_trap(self.normalize(hold_15m={"held_to_15m_price_change_percent": -12}, chart={"price_high": 1.6, "price_end": 1.1})), LateBuyTrapLabel.POSSIBLE_LATE_BUY_TRAP)
        self.assertEqual(classify_late_buy_trap(self.normalize(hold_15m={"held_to_15m_price_change_percent": -30})), LateBuyTrapLabel.CONFIRMED_LATE_BUY_TRAP)

    def test_clean_memory_gates_and_chart_only_gain_requires_exit(self):
        clean = self.normalize(hold_15m={"held_to_15m_price_change_percent": 12})
        chart_only = self.normalize(liquidity={"route_label": None, "slippage_label": None, "price_impact_label": None, "exit_realism_label": None})
        dirty = self.normalize()
        dirty["data_quality_label"] = DataQualityLabel.DIRTY_DATA.value
        stale = self.normalize(detected_at=self.now - timedelta(hours=3))
        conflicting = self.normalize()
        conflicting["source_status"] = SourceStatus.CONFLICTING.value
        self.assertTrue(micro_event_context_is_tradable_support_evidence(clean, self.now))
        self.assertFalse(micro_event_context_can_support_clean_memory(chart_only, self.now))
        for payload in (dirty, stale, conflicting):
            self.assertFalse(micro_event_context_can_support_clean_memory(payload, self.now))

    def test_untradable_or_no_exit_blocks_profit_without_paper_decisions(self):
        no_exit = self.normalize(liquidity={"route_label": "ROUTE_NOT_AVAILABLE"})
        self.assertTrue(micro_event_context_blocks_clean_micro_profit(no_exit, self.now))
        record_micro_event(self.db_path, self.payload(liquidity={"route_label": "ROUTE_NOT_AVAILABLE"}), self.now)
        self.assertEqual(self.count_rows("printer_paper_decisions"), 0)

    def test_record_dedupe_latest_nearest_and_window_lookup(self):
        created, row_id = record_micro_event(self.db_path, self.payload(hold_15m={"held_to_15m_price_change_percent": 12}), self.now)
        duplicate_created, duplicate_id = record_micro_event(self.db_path, self.payload(hold_15m={"held_to_15m_price_change_percent": 12}), self.now)
        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(row_id, duplicate_id)
        later = self.now + timedelta(minutes=10)
        record_micro_event(
            self.db_path,
            self.payload(detected_at=later, event_window_start_at=(later - timedelta(minutes=5)).isoformat(), event_window_end_at=later.isoformat(), hold_15m={"held_to_15m_price_change_percent": 12}),
            self.now,
        )
        latest = get_latest_micro_event(self.db_path, token_id=self.token_id, pair_id=self.pair_id)
        nearest = lookup.find_nearest_micro_event(self.db_path, self.token_id, self.pair_id, self.now + timedelta(minutes=8), max_age_seconds=3600)
        window = lookup.find_micro_events_for_window(self.db_path, self.token_id, self.pair_id, self.now - timedelta(minutes=1), later + timedelta(minutes=1))
        self.assertEqual(latest["detected_at"], later.isoformat())
        self.assertEqual(nearest["detected_at"], later.isoformat())
        self.assertEqual(len(window), 2)

    def test_scheduler_and_no_side_effects(self):
        result, job_id = enqueue_micro_event_refresh_job(self.db_path, self.token_id, self.pair_id, self.now + timedelta(minutes=1), reason="phase13_test")
        self.assertEqual(result.value, "ACQUIRED")
        self.assertIsNotNone(job_id)
        record_micro_event(self.db_path, self.payload(), self.now)
        with self.connect() as connection:
            running = connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = ?", (JobStatus.RUNNING.value,)).fetchone()[0]
        self.assertEqual(running, 0)
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
        self.assertFalse(any(fragment in " ".join(names) for fragment in FORBIDDEN_FRAGMENTS))


if __name__ == "__main__":
    unittest.main()

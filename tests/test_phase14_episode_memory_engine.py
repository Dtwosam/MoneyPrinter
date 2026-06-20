import inspect
import json
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
from printer_v1.memory import assembler, fingerprints, lookup, outcomes, quality, recorder, windowing
from printer_v1.memory.contracts import (
    ActionLessonLabel,
    EpisodeOutcomeLabel,
    EpisodeStatus,
    MemoryQualityLabel,
    MemoryRejectionReasonLabel,
    MemoryWindowKind,
    MemoryWindowStatus,
)
from printer_v1.memory.fingerprints import build_memory_fingerprint_payload, fingerprint_can_be_indexed_later
from printer_v1.memory.outcomes import classify_episode_outcome
from printer_v1.memory.quality import classify_memory_quality, memory_can_train_decisions
from printer_v1.memory.recorder import build_and_record_episode, enqueue_memory_build_job
from printer_v1.memory.windowing import (
    close_memory_window,
    get_due_memory_windows,
    get_window_duration_seconds,
    memory_window_can_close,
    open_memory_window,
)
from printer_v1.scheduler.contracts import JobStatus


FORBIDDEN_COLUMNS = {
    "score", "confidence", "rank", "rating", "weight", "wallet_address",
    "private_key", "signed_tx", "live_trade", "similarity", "embedding", "vector",
}
FORBIDDEN_FRAGMENTS = {
    "score", "confidence", "rank", "rating", "weight",
    "private_key", "signed_tx", "live_trade", "similarity_score", "rank_score",
    "embedding", "vector",
}


class Phase14EpisodeMemoryEngineTest(unittest.TestCase):
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
                "INSERT INTO printer_tokens (token_mint, chain) VALUES ('memory-mint', 'solana')"
            ).lastrowid
            pair_id = connection.execute(
                "INSERT INTO printer_pairs (token_id, pair_address, dex, pool_source) VALUES (?, 'memory-pair', 'raydium', 'local')",
                (token_id,),
            ).lastrowid
        return int(token_id), int(pair_id)

    def insert_snapshots(self, opened_at, prices, *, liquidity=120000, source_status="COMPLETE", data_quality="CLEAN_DATA"):
        with self.connect() as connection:
            for index, price in enumerate(prices):
                connection.execute(
                    """
                    INSERT INTO printer_token_snapshots (
                        token_id, pair_id, captured_at, tracking_lane, snapshot_mode,
                        price_usd, liquidity_usd, source_status, data_quality_label
                    )
                    VALUES (?, ?, ?, 'TRACK_FAST', 'NORMAL_MODE', ?, ?, ?, ?)
                    """,
                    (
                        self.token_id,
                        self.pair_id,
                        (opened_at + timedelta(minutes=index * 5)).isoformat(),
                        price,
                        liquidity,
                        source_status,
                        data_quality,
                    ),
                )

    def count_rows(self, table):
        with self.connect() as connection:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def column_names(self, table_name):
        with self.connect() as connection:
            return {row[1] for row in connection.execute(f"PRAGMA table_info({table_name})")}

    def table_names(self):
        with self.connect() as connection:
            return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    def test_micro_event_package_has_dunder_init_not_accidental_init(self):
        self.assertTrue((SRC_PATH / "printer_v1" / "micro_event" / "__init__.py").exists())
        self.assertFalse((SRC_PATH / "printer_v1" / "micro_event" / "init.py").exists())

    def test_memory_files_import_successfully(self):
        for module in (assembler, fingerprints, lookup, outcomes, quality, recorder, windowing):
            self.assertTrue(inspect.ismodule(module))

    def test_required_contract_labels_exist(self):
        self.assertEqual({label.value for label in MemoryWindowKind}, {"WINDOW_15M", "WINDOW_1H", "WINDOW_4H", "WINDOW_12H", "WINDOW_24H"})
        self.assertEqual({label.value for label in MemoryWindowStatus}, {"WINDOW_OPEN", "WINDOW_CLOSING", "WINDOW_CLOSED", "WINDOW_BROKEN", "WINDOW_SKIPPED", "WINDOW_AUDIT_ONLY"})
        self.assertEqual({label.value for label in EpisodeStatus}, {"EPISODE_BUILDABLE", "EPISODE_BUILT", "EPISODE_DIRTY", "EPISODE_AUDIT_ONLY", "EPISODE_SKIPPED", "EPISODE_INCOMPLETE"})
        self.assertEqual({label.value for label in EpisodeOutcomeLabel}, {
            "NO_PUMP", "FAKE_PUMP", "SHORT_TERM_PUMP", "SUSTAINED_PUMP", "EXTENDED_PUMP", "CONSOLIDATION", "DUMP", "PUMP_AND_DUMP", "ROUND_TRIP", "REVIVAL", "DEAD_TOKEN", "UNREALISTIC_PROFIT", "REALISTIC_PAPER_PROFIT", "REALISTIC_CAPITAL_PROTECTION", "MISSED_UPSIDE", "OUTCOME_UNKNOWN"
        })
        self.assertEqual({label.value for label in MemoryQualityLabel}, {"CLEAN_MEMORY", "PARTIAL_MEMORY", "DIRTY_MEMORY", "AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN_MEMORY"})
        self.assertIn("REJECT_MISSING_SNAPSHOTS", {label.value for label in MemoryRejectionReasonLabel})
        self.assertIn("ACTION_BUY_WORKED", {label.value for label in ActionLessonLabel})

    def test_migration_creates_required_additions_without_forbidden_columns(self):
        self.assertIn("printer_episode_outcomes", self.table_names())
        self.assertIn("printer_memory_audit_reports", self.table_names())
        self.assertIn("memory_quality_label", self.column_names("printer_memory_windows"))
        self.assertIn("episode_summary_json", self.column_names("printer_episodes"))
        for table in ("printer_memory_windows", "printer_episodes", "printer_episode_outcomes", "printer_memory_audit_reports", "printer_memory_fingerprints"):
            self.assertEqual(self.column_names(table) & FORBIDDEN_COLUMNS, set(), table)

    def test_window_durations_and_5m_rejection(self):
        self.assertEqual(get_window_duration_seconds(MemoryWindowKind.WINDOW_15M), 900)
        self.assertEqual(get_window_duration_seconds(MemoryWindowKind.WINDOW_1H), 3600)
        self.assertEqual(get_window_duration_seconds(MemoryWindowKind.WINDOW_4H), 14400)
        self.assertEqual(get_window_duration_seconds(MemoryWindowKind.WINDOW_12H), 43200)
        self.assertEqual(get_window_duration_seconds(MemoryWindowKind.WINDOW_24H), 86400)
        with self.assertRaises(ValueError):
            get_window_duration_seconds("WINDOW_5M")

    def test_due_windows_only_after_full_duration_and_incomplete_is_not_clean(self):
        opened = self.now - timedelta(minutes=10)
        window_id = open_memory_window(self.db_path, self.token_id, self.pair_id, MemoryWindowKind.WINDOW_15M, opened, "TRACK_FAST")
        self.assertFalse(memory_window_can_close(opened, self.now, MemoryWindowKind.WINDOW_15M))
        self.assertEqual(get_due_memory_windows(self.db_path, self.now), [])
        due_time = self.now + timedelta(minutes=6)
        self.assertTrue(memory_window_can_close(opened, due_time, MemoryWindowKind.WINDOW_15M))
        self.assertEqual(get_due_memory_windows(self.db_path, due_time)[0]["id"], window_id)
        self.assertEqual(
            classify_memory_quality(outcome_label=EpisodeOutcomeLabel.NO_PUMP, rejection_reasons=["REJECT_MISSING_SNAPSHOTS"], coverage_is_complete=False),
            MemoryQualityLabel.DIRTY_MEMORY,
        )

    def test_quality_gates_for_broken_stale_conflicting_unrealistic_and_realistic(self):
        self.assertEqual(
            classify_memory_quality(outcome_label=EpisodeOutcomeLabel.NO_PUMP, rejection_reasons=["REJECT_MISSING_CRITICAL_FIELDS"]),
            MemoryQualityLabel.DIRTY_MEMORY,
        )
        self.assertEqual(
            classify_memory_quality(outcome_label=EpisodeOutcomeLabel.NO_PUMP, rejection_reasons=["REJECT_STALE_SOURCE_DATA"]),
            MemoryQualityLabel.AUDIT_ONLY_MEMORY,
        )
        self.assertEqual(
            classify_memory_quality(outcome_label=EpisodeOutcomeLabel.NO_PUMP, rejection_reasons=["REJECT_CONFLICTING_DATA"]),
            MemoryQualityLabel.AUDIT_ONLY_MEMORY,
        )
        self.assertEqual(
            classify_memory_quality(outcome_label=EpisodeOutcomeLabel.UNREALISTIC_PROFIT, rejection_reasons=["REJECT_UNREALISTIC_EXIT"]),
            MemoryQualityLabel.AUDIT_ONLY_MEMORY,
        )
        self.assertEqual(
            classify_memory_quality(outcome_label=EpisodeOutcomeLabel.REALISTIC_PAPER_PROFIT, rejection_reasons=[]),
            MemoryQualityLabel.CLEAN_MEMORY,
        )

    def test_outcome_labels_preserve_fake_pump_round_trip_and_profit_realism(self):
        snapshots = [
            {"captured_at": "2026-06-19T12:00:00+00:00", "price_usd": 1.0, "liquidity_usd": 100000},
            {"captured_at": "2026-06-19T12:05:00+00:00", "price_usd": 1.4, "liquidity_usd": 100000},
            {"captured_at": "2026-06-19T12:15:00+00:00", "price_usd": 1.02, "liquidity_usd": 100000},
        ]
        self.assertEqual(classify_episode_outcome("WINDOW_15M", snapshots), EpisodeOutcomeLabel.ROUND_TRIP)
        self.assertEqual(
            classify_episode_outcome("WINDOW_15M", snapshots, {"realism_gate_label": "REALISM_CONTEXT_BLOCKED"}),
            EpisodeOutcomeLabel.UNREALISTIC_PROFIT,
        )
        profit_snapshots = [dict(snapshots[0]), {"captured_at": "x", "price_usd": 1.5, "liquidity_usd": 100000}]
        self.assertEqual(
            classify_episode_outcome("WINDOW_15M", profit_snapshots, {"entry_realism_label": "ENTRY_REALISTIC", "exit_realism_label": "EXIT_REALISTIC"}),
            EpisodeOutcomeLabel.REALISTIC_PAPER_PROFIT,
        )

    def test_build_and_record_episode_creates_related_rows_and_prevents_duplicates(self):
        opened = self.now - timedelta(minutes=15)
        window_id = open_memory_window(self.db_path, self.token_id, self.pair_id, MemoryWindowKind.WINDOW_15M, opened, "TRACK_FAST")
        close_memory_window(self.db_path, window_id, self.now)
        self.insert_snapshots(opened, [1.0, 1.2, 1.45, 1.5])
        created, episode_id = build_and_record_episode(self.db_path, window_id, self.now)
        duplicate_created, duplicate_id = build_and_record_episode(self.db_path, window_id, self.now)
        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(episode_id, duplicate_id)
        self.assertEqual(self.count_rows("printer_episode_snapshots"), 4)
        self.assertEqual(self.count_rows("printer_episode_outcomes"), 1)
        self.assertEqual(self.count_rows("printer_memory_audit_reports"), 1)
        self.assertEqual(self.count_rows("printer_memory_fingerprints"), 1)
        episode = lookup.find_episode_by_window(self.db_path, window_id)
        self.assertEqual(episode["memory_quality_label"], MemoryQualityLabel.CLEAN_MEMORY.value)
        self.assertTrue(lookup.episode_can_be_used_for_future_retrieval(episode))
        self.assertTrue(memory_can_train_decisions(episode["memory_quality_label"]))

    def test_micro_event_is_support_only_and_cannot_replace_main_window_snapshots(self):
        opened = self.now - timedelta(minutes=15)
        window_id = open_memory_window(self.db_path, self.token_id, self.pair_id, MemoryWindowKind.WINDOW_15M, opened, "TRACK_FAST")
        close_memory_window(self.db_path, window_id, self.now)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO printer_micro_events (
                    token_id, pair_id, detected_at, event_window_start_at, event_window_end_at,
                    micro_event_state_label, micro_event_move_label, micro_exit_realism_label,
                    late_buy_trap_label, held_to_15m_result_label, micro_event_payload_quality_label,
                    micro_event_memory_gate_label, data_quality_label, source_status
                )
                VALUES (?, ?, ?, ?, ?, 'TRADABLE_MICRO_PUMP', 'MOVE_FAST_UP',
                    'MICRO_EXIT_REALISTIC', 'NO_LATE_BUY_TRAP', 'HELD_TO_15M_CONTINUED',
                    'MICRO_EVENT_CONTEXT_CLEAN', 'MICRO_EVENT_SUPPORT_EVIDENCE',
                    'CLEAN_DATA', 'COMPLETE')
                """,
                (self.token_id, self.pair_id, self.now.isoformat(), opened.isoformat(), self.now.isoformat()),
            )
        created, episode_id = build_and_record_episode(self.db_path, window_id, self.now)
        episode = lookup.find_episode_by_window(self.db_path, window_id)
        self.assertTrue(created)
        self.assertEqual(episode_id, episode["id"])
        self.assertEqual(episode["memory_quality_label"], MemoryQualityLabel.DIRTY_MEMORY.value)
        self.assertFalse(lookup.episode_can_be_used_for_future_retrieval(episode))

    def test_fingerprint_payload_contains_conditions_without_forbidden_concepts(self):
        payload = {
            "window": {"window_kind": "WINDOW_15M"},
            "outcome_label": "SUSTAINED_PUMP",
            "memory_quality_label": "CLEAN_MEMORY",
            "supporting_context": {
                "liquidity_exit": {"liquidity_state_label": "LIQUIDITY_USABLE", "exit_realism_label": "EXIT_REALISTIC"},
                "trading_flow": {"flow_direction_label": "FLOW_ACCUMULATION"},
                "chart_volatility": {"trend_structure_label": "TREND_UP"},
                "micro_events": [{"micro_event_state_label": "TRADABLE_MICRO_PUMP"}],
            },
        }
        fingerprint = build_memory_fingerprint_payload(payload)
        encoded = json.dumps(fingerprint)
        for fragment in ("score", "confidence", "rank", "embedding", "vector"):
            self.assertNotIn(fragment, encoded)
        self.assertTrue(fingerprint_can_be_indexed_later(MemoryQualityLabel.CLEAN_MEMORY))

    def test_local_episode_lookup_and_scheduler_enqueue_only(self):
        opened = self.now - timedelta(minutes=15)
        window_id = open_memory_window(self.db_path, self.token_id, self.pair_id, MemoryWindowKind.WINDOW_15M, opened, "TRACK_FAST")
        close_memory_window(self.db_path, window_id, self.now)
        self.insert_snapshots(opened, [1.0, 1.1, 1.2])
        build_and_record_episode(self.db_path, window_id, self.now)
        self.assertEqual(len(lookup.find_episodes_for_token_pair(self.db_path, self.token_id, self.pair_id)), 1)
        self.assertEqual(len(lookup.find_clean_episodes_for_token_pair(self.db_path, self.token_id, self.pair_id)), 1)
        result, job_id = enqueue_memory_build_job(self.db_path, window_id, self.now + timedelta(minutes=1), reason="phase14_test")
        self.assertEqual(result.value, "ACQUIRED")
        self.assertIsNotNone(job_id)
        with self.connect() as connection:
            running = connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = ?", (JobStatus.RUNNING.value,)).fetchone()[0]
        self.assertEqual(running, 0)

    def test_no_paper_lifecycle_network_or_forbidden_capabilities(self):
        self.assertEqual(self.count_rows("printer_paper_decisions"), 0)
        self.assertEqual(self.count_rows("printer_paper_positions"), 0)
        self.assertEqual(self.count_rows("printer_token_lifecycle_events"), 0)
        source_text = "\n".join(inspect.getsource(module) for module in (assembler, fingerprints, lookup, outcomes, quality, recorder, windowing))
        for fragment in ("requests.get", "requests.post", "httpx", "aiohttp", "urllib.request", "while True", "APScheduler"):
            self.assertNotIn(fragment, source_text)
        names = []
        for module in (assembler, fingerprints, lookup, outcomes, quality, recorder, windowing):
            names.extend(name.lower() for name, _ in inspect.getmembers(module))
        self.assertFalse(any(fragment in " ".join(names) for fragment in FORBIDDEN_FRAGMENTS))


if __name__ == "__main__":
    unittest.main()

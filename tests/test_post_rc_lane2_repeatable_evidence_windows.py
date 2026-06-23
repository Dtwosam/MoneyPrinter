import argparse
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

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import (
    CONTEXT_TABLES,
    build_collect_context_once_payload,
    build_collect_token_snapshots_once_payload,
    build_manual_intake_token_pair_payload,
    build_memory_window_once_payload,
    build_retrieve_clean_memory_once_payload,
)


def count_rows(connection, table):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


class PostRCLane2RepeatableEvidenceWindowTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "lane2.sqlite3"
        apply_migrations(self.db_path)
        self.base_time = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tempdir.cleanup()

    def args(self, **overrides):
        values = {
            "db_path": str(self.db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "token_mint": "lane2-mint",
            "token_id": None,
            "pair_address": "lane2-pair",
            "pair_id": None,
            "chain": "solana",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def transport(self, context):
        del context
        return {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": "lane2-pair",
                    "baseToken": {"address": "lane2-mint", "symbol": "L2", "name": "Lane 2"},
                    "priceUsd": "0.00042",
                    "liquidity": {"usd": 18000.0},
                    "volume": {"m5": 120.0, "h1": 700.0, "h24": 3200.0},
                    "txns": {"m5": {"buys": 3, "sells": 1}, "h1": {"buys": 22, "sells": 8}},
                    "fdv": 420000.0,
                    "marketCap": 390000.0,
                    "priceChange": {"m5": 1.2, "h1": 4.5, "h24": 9.0},
                }
            ]
        }

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def seed_snapshots(self, count=6):
        build_manual_intake_token_pair_payload(self.args(
            pair_id=None,
            snapshot_id=None,
            pair_address="lane2-pair",
            pool_address=None,
            intake_reason="lane2 repeatable evidence test",
            source_reference="lane2-intake",
            source_request_id=None,
            token_symbol="L2",
            token_name="Lane 2",
            dex_id="dexscreener",
            intake_json=None,
        ))
        snapshot_ids = []
        for index in range(count):
            build_collect_token_snapshots_once_payload(self.args(
                snapshot_count=1,
                max_seconds=5.0,
                source_name="dexscreener",
                source_reference=f"lane2-snapshot-{index}",
            ), transport=self.transport)
        with self.connect() as connection:
            rows = connection.execute("SELECT id FROM printer_token_snapshots ORDER BY id ASC").fetchall()
            snapshot_ids = [int(row["id"]) for row in rows]
            for offset, snapshot_id in enumerate(snapshot_ids):
                captured_at = (self.base_time + timedelta(minutes=offset * 3)).isoformat()
                connection.execute("UPDATE printer_token_snapshots SET captured_at = ? WHERE id = ?", (captured_at, snapshot_id))
            connection.commit()
        return snapshot_ids

    def collect_context(self, snapshot_id):
        return build_collect_context_once_payload(self.args(
            snapshot_id=snapshot_id,
            source_name="dexscreener",
        ))

    def memory_payload(self, snapshot_id, window="15m", source_reference="lane2-memory"):
        return build_memory_window_once_payload(self.args(
            snapshot_id=snapshot_id,
            memory_window=window,
            source_reference=source_reference,
        ))

    def test_context_and_memory_are_repeatable_by_evidence_identity(self):
        snapshot_ids = self.seed_snapshots(6)
        first_context = self.collect_context(snapshot_ids[0])
        second_context = self.collect_context(snapshot_ids[-1])
        self.assertEqual(first_context["context_rows_created"], 7)
        self.assertEqual(second_context["context_rows_created"], 7)

        first = self.memory_payload(snapshot_ids[-1], source_reference="lane2-window-a")
        duplicate = self.memory_payload(snapshot_ids[-1], source_reference="lane2-window-a")
        second = self.memory_payload(snapshot_ids[-2], source_reference="lane2-window-b")

        self.assertIsNone(first["memory_result"]["skipped_reason"])
        self.assertEqual(duplicate["memory_result"]["skipped_reason"], "duplicate_same_evidence_noop")
        self.assertEqual(duplicate["memory_table_deltas"]["printer_memory_windows"], 0)
        self.assertIsNone(second["memory_result"]["skipped_reason"])
        self.assertNotEqual(first["memory_result"]["evidence_identity_hash"], second["memory_result"]["evidence_identity_hash"])
        self.assertEqual(first["memory_result"]["coverage_state"], "COMPLETE_WINDOW_COVERAGE")

        with self.connect() as connection:
            self.assertEqual(count_rows(connection, "printer_memory_windows"), 2)
            self.assertGreaterEqual(count_rows(connection, "printer_episode_snapshots"), 10)

    def test_source_reference_only_difference_is_duplicate_noop(self):
        snapshot_ids = self.seed_snapshots(6)
        self.collect_context(snapshot_ids[-1])

        first = self.memory_payload(snapshot_ids[-1], source_reference="lane2-original-build")
        duplicate = self.memory_payload(snapshot_ids[-1], source_reference="lane2-renamed-manual-run")

        self.assertIsNone(first["memory_result"]["skipped_reason"])
        self.assertEqual(duplicate["memory_result"]["skipped_reason"], "duplicate_same_evidence_noop")
        self.assertEqual(duplicate["memory_result"]["duplicate_guard_status"], "DUPLICATE_SAME_EVIDENCE_NOOP")
        self.assertEqual(duplicate["memory_result"]["duplicate_block_reason"], "source_reference_only_difference_blocked")
        self.assertEqual(duplicate["memory_result"]["evidence_difference_reason"], "source_reference_only_difference_blocked")
        self.assertEqual(duplicate["memory_table_deltas"]["printer_memory_windows"], 0)
        self.assertEqual(duplicate["memory_table_deltas"]["printer_episodes"], 0)
        self.assertEqual(duplicate["memory_table_deltas"]["printer_episode_snapshots"], 0)
        with self.connect() as connection:
            self.assertEqual(count_rows(connection, "printer_memory_windows"), 1)
            self.assertEqual(count_rows(connection, "printer_paper_decisions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_positions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_trade_events"), 0)

    def test_5m_micro_event_is_repeatable_support_only_and_not_retrieval_ready(self):
        snapshot_ids = self.seed_snapshots(3)
        self.collect_context(snapshot_ids[-1])
        main = self.memory_payload(snapshot_ids[-1], window="15m", source_reference="lane2-main")
        micro = self.memory_payload(snapshot_ids[-1], window="5m", source_reference="lane2-micro")

        self.assertEqual(main["memory_result"]["evidence_role"], "MAIN_OUTCOME")
        self.assertEqual(micro["window_kind"], "WINDOW_5M_MICRO_EVENT")
        self.assertEqual(micro["memory_result"]["evidence_role"], "SUPPORT_MICRO_EVENT")
        self.assertFalse(micro["memory_result"]["retrieval_ready"])
        self.assertIn("REJECT_5M_ONLY_WINDOW", micro["memory_result"]["rejection_reasons"])

        with self.connect() as connection:
            self.assertEqual(count_rows(connection, "printer_paper_decisions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_positions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_trade_events"), 0)

    def test_old_dirty_memory_does_not_block_newer_completed_evidence(self):
        snapshot_ids = self.seed_snapshots(6)
        self.collect_context(snapshot_ids[0])
        dirty = self.memory_payload(snapshot_ids[0], source_reference="lane2-dirty-one-snapshot")
        self.collect_context(snapshot_ids[-1])
        newer = self.memory_payload(snapshot_ids[-1], source_reference="lane2-newer-complete")

        self.assertEqual(dirty["memory_result"]["memory_quality_label"], "DIRTY_MEMORY")
        self.assertEqual(dirty["memory_result"]["coverage_state"], "INCOMPLETE_15M_WINDOW")
        self.assertIsNone(newer["memory_result"]["skipped_reason"])
        self.assertEqual(newer["memory_result"]["coverage_state"], "COMPLETE_WINDOW_COVERAGE")

        with self.connect() as connection:
            qualities = [row["memory_quality_label"] for row in connection.execute("SELECT memory_quality_label FROM printer_memory_windows ORDER BY id")]
            self.assertEqual(qualities[0], "DIRTY_MEMORY")
            self.assertEqual(len(qualities), 2)

    def test_retrieval_dedupes_evidence_and_reports_same_token_concentration(self):
        snapshot_ids = self.seed_snapshots(2)
        self.collect_context(snapshot_ids[-1])
        with self.connect() as connection:
            token = connection.execute("SELECT * FROM printer_tokens WHERE token_mint = 'lane2-mint'").fetchone()
            pair = connection.execute("SELECT * FROM printer_pairs WHERE pair_address = 'lane2-pair'").fetchone()
            for index in range(3):
                memory_id = connection.execute(
                    """
                    INSERT INTO printer_memory_windows (
                        token_id, pair_id, window_kind, opened_at, closed_at, memory_status,
                        data_quality_label, do_not_train, window_status, outcome_label, memory_quality_label,
                        snapshot_start_id, snapshot_end_id, window_start_at, window_end_at,
                        evidence_role, evidence_identity_hash, evidence_difference_reason,
                        duplicate_guard_status, memory_diversity_label
                    ) VALUES (?, ?, 'WINDOW_15M', ?, ?, 'CLEAN_MEMORY', 'CLEAN_DATA', 0,
                        'WINDOW_CLOSED', 'NO_PUMP', 'CLEAN_MEMORY', ?, ?, ?, ?,
                        'MAIN_OUTCOME', ?, 'distinct_snapshot_range', 'NEW_DISTINCT_EVIDENCE_WINDOW',
                        'NORMAL_TOKEN_MEMORY_DISTRIBUTION')
                    """,
                    (
                        token["id"], pair["id"], self.base_time.isoformat(), (self.base_time + timedelta(minutes=15)).isoformat(),
                        snapshot_ids[0], snapshot_ids[-1], self.base_time.isoformat(),
                        (self.base_time + timedelta(minutes=15)).isoformat(), f"lane2-clean-{index}",
                    ),
                ).lastrowid
                episode_id = connection.execute(
                    """
                    INSERT INTO printer_episodes (
                        memory_window_id, token_id, pair_id, episode_kind, episode_status,
                        memory_status, data_quality_label, do_not_train, window_kind,
                        episode_outcome_label, memory_quality_label, action_lesson_label
                    ) VALUES (?, ?, ?, 'TOKEN_WINDOW_EPISODE', 'EPISODE_BUILT',
                        'CLEAN_MEMORY', 'CLEAN_DATA', 0, 'WINDOW_15M', 'NO_PUMP',
                        'CLEAN_MEMORY', 'ACTION_WAIT_WORKED')
                    """,
                    (memory_id, token["id"], pair["id"]),
                ).lastrowid
                connection.execute(
                    """
                    INSERT INTO printer_memory_fingerprints (
                        episode_id, fingerprint_kind, fingerprint_payload_json,
                        memory_status, data_quality_label, do_not_train
                    ) VALUES (?, 'STATIC_CONDITION_SUMMARY', ?, 'CLEAN_MEMORY', 'CLEAN_DATA', 0)
                    """,
                    (episode_id, json.dumps({
                    "window_kind": "WINDOW_15M",
                    "outcome_label": "NO_PUMP",
                    "memory_quality_label": "CLEAN_MEMORY",
                    "retrieval_ready": True,
                    "safety_status_label": "SAFETY_UNKNOWN",
                    "liquidity_state_label": "LIQUIDITY_USABLE",
                    "exit_realism_label": "EXIT_UNKNOWN",
                    "flow_direction_label": "FLOW_UNKNOWN",
                    "trend_structure_label": "TREND_UNKNOWN",
                    "candle_path_label": "PATH_UNKNOWN",
                    }, sort_keys=True)),
                )
            connection.commit()

        payload = build_retrieve_clean_memory_once_payload(self.args(snapshot_id=snapshot_ids[-1]))
        report = payload["retrieval_report"]
        self.assertEqual(report["clean_matches_returned"], 3)
        self.assertEqual(report["memory_diversity_label"], "TOKEN_MEMORY_CONCENTRATED")
        self.assertEqual(report["distinct_token_count_in_retrieval"], 1)
        self.assertFalse(report["paper_decision_allowed"])
        with self.connect() as connection:
            self.assertEqual(count_rows(connection, "printer_paper_decisions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_positions"), 0)


if __name__ == "__main__":
    unittest.main()

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
    _memory_evidence_role,
    _memory_window_duration_minutes,
    _normalize_memory_window,
    build_collect_context_once_payload,
    build_collect_token_snapshots_once_payload,
    build_manual_intake_token_pair_payload,
    build_memory_window_once_payload,
    build_retrieve_clean_memory_once_payload,
)


def count_rows(connection, table):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


class PostRCLane6LongerWindowActivationReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "lane6.sqlite3"
        apply_migrations(self.db_path)
        self.base_time = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tempdir.cleanup()

    def args(self, **overrides):
        values = {
            "db_path": str(self.db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "token_mint": "lane6-mint",
            "token_id": None,
            "pair_address": "lane6-pair",
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
                    "pairAddress": "lane6-pair",
                    "baseToken": {"address": "lane6-mint", "symbol": "L6", "name": "Lane 6"},
                    "priceUsd": "0.00051",
                    "liquidity": {"usd": 24000.0},
                    "volume": {"m5": 150.0, "h1": 820.0, "h24": 3600.0},
                    "txns": {"m5": {"buys": 5, "sells": 2}, "h1": {"buys": 30, "sells": 12}},
                    "fdv": 510000.0,
                    "marketCap": 470000.0,
                    "priceChange": {"m5": 1.1, "h1": 4.2, "h24": 8.5},
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

    def seed_snapshots_at_offsets(self, minute_offsets):
        build_manual_intake_token_pair_payload(self.args(
            pair_id=None,
            snapshot_id=None,
            pair_address="lane6-pair",
            pool_address=None,
            intake_reason="lane6 long-window fixture only",
            source_reference="lane6-intake",
            source_request_id=None,
            token_symbol="L6",
            token_name="Lane 6",
            dex_id="dexscreener",
            intake_json=None,
        ))
        for index, _offset in enumerate(minute_offsets):
            build_collect_token_snapshots_once_payload(self.args(
                snapshot_count=1,
                max_seconds=5.0,
                source_name="dexscreener",
                source_reference=f"lane6-fixture-snapshot-{index}",
            ), transport=self.transport)
        with self.connect() as connection:
            rows = connection.execute("SELECT id FROM printer_token_snapshots ORDER BY id ASC").fetchall()
            snapshot_ids = [int(row["id"]) for row in rows]
            for snapshot_id, offset in zip(snapshot_ids, minute_offsets):
                captured_at = (self.base_time + timedelta(minutes=offset)).isoformat()
                row = connection.execute(
                    "SELECT normalized_snapshot_payload_json FROM printer_token_snapshots WHERE id = ?",
                    (snapshot_id,),
                ).fetchone()
                normalized = json.loads(row["normalized_snapshot_payload_json"] or "{}")
                normalized["captured_at"] = captured_at
                connection.execute(
                    """
                    UPDATE printer_token_snapshots
                    SET captured_at = ?, normalized_snapshot_payload_json = ?
                    WHERE id = ?
                    """,
                    (captured_at, json.dumps(normalized, sort_keys=True), snapshot_id),
                )
        return snapshot_ids

    def collect_context(self, snapshot_id):
        return build_collect_context_once_payload(self.args(
            snapshot_id=snapshot_id,
            source_name="dexscreener",
        ))

    def memory_payload(self, snapshot_id, window, source_reference):
        return build_memory_window_once_payload(self.args(
            snapshot_id=snapshot_id,
            memory_window=window,
            source_reference=source_reference,
        ))

    def retrieval_payload(self, snapshot_id):
        return build_retrieve_clean_memory_once_payload(self.args(snapshot_id=snapshot_id))

    def test_long_window_kinds_are_recognized_as_main_outcome_windows(self):
        expected = {
            "1h": ("WINDOW_1H", 60),
            "4h": ("WINDOW_4H", 240),
            "12h": ("WINDOW_12H", 720),
            "24h": ("WINDOW_24H", 1440),
        }
        for user_value, (window_kind, minutes) in expected.items():
            with self.subTest(user_value=user_value):
                self.assertEqual(_normalize_memory_window(user_value), window_kind)
                self.assertEqual(_memory_window_duration_minutes(window_kind), minutes)
                self.assertEqual(_memory_evidence_role(window_kind), "MAIN_OUTCOME")
        self.assertEqual(_memory_evidence_role("WINDOW_5M_MICRO_EVENT"), "SUPPORT_MICRO_EVENT")

    def test_long_window_fixture_evidence_is_structural_audit_only_not_retrieval_ready(self):
        cases = [
            ("1h", 60, "WINDOW_1H"),
            ("4h", 240, "WINDOW_4H"),
            ("12h", 720, "WINDOW_12H"),
            ("24h", 1440, "WINDOW_24H"),
        ]
        for window_arg, minutes, window_kind in cases:
            with self.subTest(window_arg=window_arg):
                self.tearDown()
                self.setUp()
                snapshot_ids = self.seed_snapshots_at_offsets([0, minutes])
                self.collect_context(snapshot_ids[-1])
                payload = self.memory_payload(snapshot_ids[-1], window_arg, f"lane6-{window_arg}-fixture")
                result = payload["memory_result"]
                self.assertEqual(payload["window_kind"], window_kind)
                self.assertEqual(result["evidence_role"], "MAIN_OUTCOME")
                self.assertEqual(result["snapshot_ids"], snapshot_ids)
                self.assertEqual(result["snapshot_start_id"], snapshot_ids[0])
                self.assertEqual(result["snapshot_end_id"], snapshot_ids[-1])
                self.assertEqual(result["duplicate_guard_status"], "NEW_DISTINCT_EVIDENCE_WINDOW")
                self.assertEqual(result["memory_quality_label"], "AUDIT_ONLY_MEMORY")
                self.assertFalse(result["retrieval_ready"])
                self.assertEqual(result["do_not_train"], 1)
                self.assertIn("MISSING_OR_UNKNOWN_CONTEXT", result["rejection_reasons"])
                with self.connect() as connection:
                    self.assertEqual(count_rows(connection, "printer_paper_decisions"), 0)
                    self.assertEqual(count_rows(connection, "printer_paper_positions"), 0)
                    self.assertEqual(count_rows(connection, "printer_paper_trade_events"), 0)

    def test_incomplete_long_window_fixture_coverage_stays_not_retrieval_ready(self):
        snapshot_ids = self.seed_snapshots_at_offsets([60])
        self.collect_context(snapshot_ids[-1])

        payload = self.memory_payload(snapshot_ids[-1], "1h", "lane6-incomplete-1h")
        result = payload["memory_result"]

        self.assertEqual(result["coverage_state"], "INCOMPLETE_1H_WINDOW")
        self.assertIn("REJECT_MISSING_SNAPSHOTS", result["rejection_reasons"])
        self.assertIn("INSUFFICIENT_SNAPSHOT_COVERAGE", result["rejection_reasons"])
        self.assertEqual(result["memory_quality_label"], "DIRTY_MEMORY")
        self.assertFalse(result["retrieval_ready"])
        self.assertEqual(result["do_not_train"], 1)

    def test_source_reference_only_duplicate_long_window_fixture_is_noop(self):
        snapshot_ids = self.seed_snapshots_at_offsets([0, 60])
        self.collect_context(snapshot_ids[-1])
        first = self.memory_payload(snapshot_ids[-1], "1h", "lane6-1h-first")
        duplicate = self.memory_payload(snapshot_ids[-1], "1h", "lane6-1h-renamed")

        self.assertIsNone(first["memory_result"]["skipped_reason"])
        self.assertEqual(duplicate["memory_result"]["skipped_reason"], "duplicate_same_evidence_noop")
        self.assertEqual(duplicate["memory_result"]["duplicate_guard_status"], "DUPLICATE_SAME_EVIDENCE_NOOP")
        self.assertEqual(duplicate["memory_result"]["duplicate_block_reason"], "source_reference_only_difference_blocked")
        self.assertEqual(duplicate["memory_table_deltas"]["printer_memory_windows"], 0)
        self.assertEqual(duplicate["memory_table_deltas"]["printer_episodes"], 0)
        self.assertEqual(duplicate["memory_table_deltas"]["printer_memory_fingerprints"], 0)
        retrieval = self.retrieval_payload(snapshot_ids[-1])
        report = retrieval["retrieval_report"]
        self.assertEqual(report["clean_matches_returned"], 0)
        self.assertFalse(report["paper_decision_allowed"])
        with self.connect() as connection:
            self.assertEqual(count_rows(connection, "printer_memory_windows"), 1)
            self.assertEqual(count_rows(connection, "printer_paper_decisions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_positions"), 0)

    def test_distinct_long_window_fixture_evidence_is_allowed_but_stays_blocked(self):
        snapshot_ids = self.seed_snapshots_at_offsets([0, 60, 120])
        self.collect_context(snapshot_ids[1])
        self.collect_context(snapshot_ids[2])

        first = self.memory_payload(snapshot_ids[1], "1h", "lane6-1h-first-range")
        second = self.memory_payload(snapshot_ids[2], "1h", "lane6-1h-second-range")

        self.assertIsNone(first["memory_result"]["skipped_reason"])
        self.assertIsNone(second["memory_result"]["skipped_reason"])
        self.assertEqual(second["memory_result"]["duplicate_guard_status"], "NEW_DISTINCT_EVIDENCE_WINDOW")
        self.assertEqual(second["memory_result"]["evidence_difference_reason"], "distinct_snapshot_range")
        self.assertNotEqual(first["memory_result"]["evidence_identity_hash"], second["memory_result"]["evidence_identity_hash"])
        self.assertEqual(second["memory_result"]["memory_quality_label"], "AUDIT_ONLY_MEMORY")
        self.assertFalse(second["memory_result"]["retrieval_ready"])
        retrieval = self.retrieval_payload(snapshot_ids[2])
        self.assertEqual(retrieval["retrieval_report"]["clean_matches_returned"], 0)
        with self.connect() as connection:
            self.assertEqual(count_rows(connection, "printer_memory_windows"), 2)
            self.assertEqual(count_rows(connection, "printer_memory_retrieval_matches"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_decisions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_positions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_trade_events"), 0)

    def test_5m_and_15m_existing_behavior_remains_locked(self):
        snapshot_ids = self.seed_snapshots_at_offsets([0, 5, 15])
        self.collect_context(snapshot_ids[-1])
        micro = self.memory_payload(snapshot_ids[1], "5m", "lane6-5m-support")
        main = self.memory_payload(snapshot_ids[-1], "15m", "lane6-15m-main")

        self.assertEqual(micro["memory_result"]["evidence_role"], "SUPPORT_MICRO_EVENT")
        self.assertIn("REJECT_5M_ONLY_WINDOW", micro["memory_result"]["rejection_reasons"])
        self.assertFalse(micro["memory_result"]["retrieval_ready"])
        self.assertEqual(main["memory_result"]["evidence_role"], "MAIN_OUTCOME")
        self.assertEqual(main["window_kind"], "WINDOW_15M")
        self.assertFalse(main["memory_result"]["retrieval_ready"])
        with self.connect() as connection:
            self.assertEqual(count_rows(connection, "printer_paper_decisions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_positions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_trade_events"), 0)


if __name__ == "__main__":
    unittest.main()

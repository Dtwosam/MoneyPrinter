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
    _context_payload_column,
    build_collect_context_once_payload,
    build_collect_token_snapshots_once_payload,
    build_manual_intake_token_pair_payload,
    build_memory_window_once_payload,
)


def count_rows(connection, table):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


class PostRCLane3ContextFreshnessWindowTargetingTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "lane3.sqlite3"
        apply_migrations(self.db_path)
        self.base_time = datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tempdir.cleanup()

    def args(self, **overrides):
        values = {
            "db_path": str(self.db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "token_mint": "lane3-mint",
            "token_id": None,
            "pair_address": "lane3-pair",
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
                    "pairAddress": "lane3-pair",
                    "baseToken": {"address": "lane3-mint", "symbol": "L3", "name": "Lane 3"},
                    "priceUsd": "0.00045",
                    "liquidity": {"usd": 21000.0},
                    "volume": {"m5": 160.0, "h1": 900.0, "h24": 3400.0},
                    "txns": {"m5": {"buys": 4, "sells": 2}, "h1": {"buys": 28, "sells": 11}},
                    "fdv": 450000.0,
                    "marketCap": 410000.0,
                    "priceChange": {"m5": 1.4, "h1": 4.8, "h24": 10.0},
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
            pair_address="lane3-pair",
            pool_address=None,
            intake_reason="lane3 context targeting test",
            source_reference="lane3-intake",
            source_request_id=None,
            token_symbol="L3",
            token_name="Lane 3",
            dex_id="dexscreener",
            intake_json=None,
        ))
        for index in range(count):
            build_collect_token_snapshots_once_payload(self.args(
                snapshot_count=1,
                max_seconds=5.0,
                source_name="dexscreener",
                source_reference=f"lane3-snapshot-{index}",
            ), transport=self.transport)
        with self.connect() as connection:
            rows = connection.execute("SELECT id FROM printer_token_snapshots ORDER BY id ASC").fetchall()
            snapshot_ids = [int(row["id"]) for row in rows]
            for offset, snapshot_id in enumerate(snapshot_ids):
                captured_at = (self.base_time + timedelta(minutes=offset * 3)).isoformat()
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

    def memory_payload(self, snapshot_id, window="15m", source_reference="lane3-memory"):
        return build_memory_window_once_payload(self.args(
            snapshot_id=snapshot_id,
            memory_window=window,
            source_reference=source_reference,
        ))

    def rewrite_context_payloads(self, mutator):
        with self.connect() as connection:
            for table in CONTEXT_TABLES:
                payload_column = _context_payload_column(table)
                for row in connection.execute(f"SELECT id, {payload_column} FROM {table}").fetchall():
                    payload = json.loads(row[payload_column] or "{}")
                    mutator(payload)
                    connection.execute(
                        f"UPDATE {table} SET {payload_column} = ? WHERE id = ?",
                        (json.dumps(payload, sort_keys=True), row["id"]),
                    )

    def latest_supporting_context(self):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT supporting_context_json FROM printer_memory_windows ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return json.loads(row["supporting_context_json"])

    def test_context_attaches_to_specific_fresh_evidence_window_without_forcing_clean_memory(self):
        snapshot_ids = self.seed_snapshots(6)
        self.collect_context(snapshot_ids[-1])

        payload = self.memory_payload(snapshot_ids[-1], source_reference="lane3-fresh-context")
        result = payload["memory_result"]

        self.assertEqual(result["coverage_state"], "COMPLETE_WINDOW_COVERAGE")
        self.assertEqual(result["actual_snapshot_count"], 6)
        self.assertEqual(result["missing_snapshot_count"], 0)
        self.assertNotIn("REJECT_MISSING_SNAPSHOTS", result["rejection_reasons"])
        self.assertIn("MISSING_OR_UNKNOWN_CONTEXT", result["rejection_reasons"])
        self.assertEqual(result["memory_quality_label"], "AUDIT_ONLY_MEMORY")
        report = result["context_freshness_report"]
        self.assertEqual(report["context_blocking_reasons"], [])
        self.assertTrue(report["all_context_fresh_enough"])
        for item in report["context_details"].values():
            self.assertEqual(item["context_target_status"], "CONTEXT_TARGET_MATCH")
            self.assertIn(item["context_freshness_label"], {"CONTEXT_FRESH", "CONTEXT_ACCEPTABLE"})

    def test_same_context_evidence_target_is_idempotent_but_new_window_context_is_allowed(self):
        snapshot_ids = self.seed_snapshots(6)
        first = self.collect_context(snapshot_ids[0])
        duplicate = self.collect_context(snapshot_ids[0])
        second = self.collect_context(snapshot_ids[-1])

        self.assertEqual(first["context_rows_created"], 7)
        self.assertEqual(duplicate["skipped_reason"], "context_already_exists_for_evidence")
        self.assertEqual(second["context_rows_created"], 7)
        with self.connect() as connection:
            for table in CONTEXT_TABLES:
                self.assertEqual(count_rows(connection, table), 2)

    def test_old_context_targets_are_visible_mismatches_not_false_snapshot_gaps(self):
        snapshot_ids = self.seed_snapshots(6)
        self.collect_context(snapshot_ids[0])

        payload = self.memory_payload(snapshot_ids[-1], source_reference="lane3-target-mismatch")
        result = payload["memory_result"]

        self.assertEqual(result["coverage_state"], "COMPLETE_WINDOW_COVERAGE")
        self.assertNotIn("REJECT_MISSING_SNAPSHOTS", result["rejection_reasons"])
        self.assertIn("CONTEXT_TARGET_MISMATCH", result["rejection_reasons"])
        report = result["context_freshness_report"]
        self.assertEqual(report["context_target_mismatch_count"], 7)
        self.assertEqual(set(report["context_blocking_reasons"]), {"CONTEXT_TARGET_MISMATCH"})

    def test_context_outside_window_remains_blocking_and_audit_visible(self):
        snapshot_ids = self.seed_snapshots(6)
        self.collect_context(snapshot_ids[-1])
        outside_time = (self.base_time - timedelta(hours=2)).isoformat()
        self.rewrite_context_payloads(lambda payload: payload.update({"snapshot_captured_at": outside_time}))

        payload = self.memory_payload(snapshot_ids[-1], source_reference="lane3-stale-context")
        result = payload["memory_result"]

        self.assertEqual(result["coverage_state"], "COMPLETE_WINDOW_COVERAGE")
        self.assertIn("CONTEXT_OUTSIDE_WINDOW", result["rejection_reasons"])
        self.assertIn("CONTEXT_OUTSIDE_WINDOW", result["context_blocking_reasons"])
        self.assertEqual(result["context_freshness_report"]["stale_context_count"], 7)

    def test_failed_context_source_status_remains_blocking(self):
        snapshot_ids = self.seed_snapshots(6)
        self.collect_context(snapshot_ids[-1])
        with self.connect() as connection:
            connection.execute("UPDATE printer_liquidity_exit_snapshots SET source_status = 'FAILED'")

        payload = self.memory_payload(snapshot_ids[-1], source_reference="lane3-failed-context")
        result = payload["memory_result"]

        self.assertIn("CONTEXT_SOURCE_FAILED", result["rejection_reasons"])
        details = result["context_freshness_report"]["context_details"]
        self.assertEqual(details["liquidity_exit"]["context_freshness_label"], "CONTEXT_SOURCE_FAILED")

    def test_lane2_duplicate_guard_and_5m_support_only_rules_remain_intact(self):
        snapshot_ids = self.seed_snapshots(6)
        self.collect_context(snapshot_ids[-1])

        first = self.memory_payload(snapshot_ids[-1], source_reference="lane3-duplicate-check")
        duplicate = self.memory_payload(snapshot_ids[-1], source_reference="lane3-duplicate-check")
        micro = self.memory_payload(snapshot_ids[-1], window="5m", source_reference="lane3-micro-support")

        self.assertIsNone(first["memory_result"]["skipped_reason"])
        self.assertEqual(duplicate["memory_result"]["skipped_reason"], "duplicate_same_evidence_noop")
        self.assertEqual(duplicate["memory_table_deltas"]["printer_memory_windows"], 0)
        self.assertEqual(micro["memory_result"]["evidence_role"], "SUPPORT_MICRO_EVENT")
        self.assertIn("REJECT_5M_ONLY_WINDOW", micro["memory_result"]["rejection_reasons"])
        self.assertFalse(micro["memory_result"]["retrieval_ready"])
        with self.connect() as connection:
            self.assertEqual(count_rows(connection, "printer_paper_decisions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_positions"), 0)
            self.assertEqual(count_rows(connection, "printer_paper_trade_events"), 0)


if __name__ == "__main__":
    unittest.main()

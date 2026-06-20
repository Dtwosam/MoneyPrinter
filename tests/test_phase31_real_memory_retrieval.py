import argparse
import pathlib
import sqlite3
import sys
import tempfile
import tomllib
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import (
    CONTEXT_TABLES,
    MEMORY_OUTPUT_TABLES,
    build_collect_context_once_payload,
    build_collect_token_snapshots_once_payload,
    build_manual_intake_token_pair_payload,
    build_memory_quality_audit_once_payload,
    build_memory_window_once_payload,
    build_readiness_check_payload,
    build_retrieve_clean_memory_once_payload,
)
from printer_v1.operator_db.status import classify_operator_db_state


def table_count(connection, table_name):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


class Phase31RealMemoryRetrievalTests(unittest.TestCase):
    def make_db(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = pathlib.Path(temp_dir.name) / "phase31.sqlite3"
        apply_migrations(db_path)
        self.addCleanup(temp_dir.cleanup)
        return db_path

    def intake_args(self, db_path, **overrides):
        values = {
            "db_path": str(db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "token_mint": "phase31-mint",
            "pair_address": "phase31-pair",
            "pool_address": None,
            "chain": "solana",
            "intake_reason": "operator approved phase 31 test",
            "source_reference": "manual-phase31-test",
            "source_request_id": None,
            "token_symbol": "P31",
            "token_name": "Phase 31",
            "dex_id": "dexscreener",
            "intake_json": None,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def snapshot_args(self, db_path, **overrides):
        values = {
            "db_path": str(db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "token_mint": "phase31-mint",
            "token_id": None,
            "pair_address": "phase31-pair",
            "pair_id": None,
            "chain": "solana",
            "snapshot_count": 1,
            "max_seconds": 5.0,
            "source_name": "dexscreener",
            "source_reference": "phase31-fixture",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def context_args(self, db_path, **overrides):
        values = {
            "db_path": str(db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "token_mint": "phase31-mint",
            "token_id": None,
            "pair_address": "phase31-pair",
            "pair_id": None,
            "snapshot_id": None,
            "chain": "solana",
            "source_name": "dexscreener",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def memory_args(self, db_path, **overrides):
        values = {
            "db_path": str(db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "token_mint": "phase31-mint",
            "token_id": None,
            "pair_address": "phase31-pair",
            "pair_id": None,
            "snapshot_id": None,
            "chain": "solana",
            "memory_window": "15m",
            "source_reference": "phase31-test",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def audit_args(self, db_path, **overrides):
        values = {
            "db_path": str(db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "memory_window_id": 1,
            "episode_id": None,
            "token_mint": None,
            "token_id": None,
            "pair_address": None,
            "pair_id": None,
            "chain": "solana",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def retrieval_args(self, db_path, **overrides):
        values = {
            "db_path": str(db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "snapshot_id": 1,
            "token_mint": None,
            "token_id": None,
            "pair_address": None,
            "pair_id": None,
            "chain": "solana",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def readiness_args(self, db_path):
        return argparse.Namespace(
            db_path=str(db_path),
            project_root=str(PROJECT_ROOT),
            format="json",
            no_color=True,
        )

    def success_transport(self, context):
        del context
        return {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": "phase31-pair",
                    "baseToken": {
                        "address": "phase31-mint",
                        "symbol": "P31",
                        "name": "Phase 31",
                    },
                    "priceUsd": "0.00042",
                    "liquidity": {"usd": 12345.67},
                    "volume": {"m5": 100.0, "h1": 500.0, "h24": 2400.0},
                    "txns": {"m5": {"buys": 2, "sells": 1}},
                    "fdv": 420000.0,
                    "marketCap": 390000.0,
                    "priceChange": {"m5": 1.2, "h1": 4.5, "h24": 9.0},
                }
            ]
        }

    def seed_through_memory_audit(self, db_path):
        build_manual_intake_token_pair_payload(self.intake_args(db_path))
        build_collect_token_snapshots_once_payload(self.snapshot_args(db_path), transport=self.success_transport)
        build_collect_context_once_payload(self.context_args(db_path))
        build_memory_window_once_payload(self.memory_args(db_path))
        return build_memory_quality_audit_once_payload(self.audit_args(db_path))

    def test_retrieval_command_exists_in_pyproject(self):
        scripts = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertEqual(
            scripts["printer-retrieve-clean-memory-once"],
            "printer_v1.operator_cli.commands:main_retrieve_clean_memory_once",
        )

    def test_retrieval_requires_operator_approval(self):
        db_path = self.make_db()
        self.seed_through_memory_audit(db_path)
        with self.assertRaises(ValueError):
            build_retrieve_clean_memory_once_payload(self.retrieval_args(db_path, operator_approved=False))

    def test_retrieval_rejects_unknown_token_pair_or_snapshot(self):
        db_path = self.make_db()
        self.seed_through_memory_audit(db_path)
        with self.assertRaises(ValueError):
            build_retrieve_clean_memory_once_payload(self.retrieval_args(db_path, snapshot_id=999))
        with self.assertRaises(ValueError):
            build_retrieve_clean_memory_once_payload(
                self.retrieval_args(db_path, snapshot_id=None, token_mint="unknown", pair_address="phase31-pair")
            )
        with self.assertRaises(ValueError):
            build_retrieve_clean_memory_once_payload(
                self.retrieval_args(db_path, snapshot_id=None, token_mint="phase31-mint", pair_address="unknown")
            )

    def test_retrieval_rejects_non_solana_chain(self):
        db_path = self.make_db()
        self.seed_through_memory_audit(db_path)
        with self.assertRaises(ValueError):
            build_retrieve_clean_memory_once_payload(self.retrieval_args(db_path, chain="ethereum"))

    def test_retrieval_blocks_dirty_memory_and_writes_query_only(self):
        db_path = self.make_db()
        self.seed_through_memory_audit(db_path)
        payload = build_retrieve_clean_memory_once_payload(self.retrieval_args(db_path))
        report = payload["retrieval_report"]

        self.assertEqual(payload["retrieval_query_delta"], 1)
        self.assertEqual(payload["retrieval_match_delta"], 0)
        self.assertEqual(payload["guard_table_deltas"], {})
        self.assertTrue(payload["guard_tables_unchanged"])
        self.assertEqual(payload["db_state_classification"], "PERSISTENT_DB_REAL_MEMORY_RETRIEVAL")
        self.assertEqual(report["clean_memory_count"], 0)
        self.assertEqual(report["clean_eligible_memory_count"], 0)
        self.assertEqual(report["dirty_memory_count"], 1)
        self.assertEqual(report["blocked_dirty_memory_count"], 1)
        self.assertEqual(report["retrieval_ready_false_count"], 1)
        self.assertEqual(report["clean_matches_returned"], 0)
        self.assertEqual(report["dirty_or_audit_only_matches_returned_as_clean"], 0)
        self.assertFalse(report["retrieval_allowed"])
        self.assertFalse(report["paper_decision_allowed"])
        self.assertFalse(report["decision_allowed"])
        self.assertTrue(report["dirty_memory_blocked"])
        self.assertIn("DIRTY_MEMORY_NOT_RETRIEVAL_READY", report["blocked_match_reasons"]["1"])
        self.assertIn("INSUFFICIENT_SNAPSHOT_COVERAGE", report["blocked_match_reasons"]["1"])

        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        try:
            self.assertEqual(table_count(connection, "printer_memory_retrieval_queries"), 1)
            self.assertEqual(table_count(connection, "printer_memory_retrieval_matches"), 0)
            self.assertEqual(table_count(connection, "printer_tokens"), 1)
            self.assertEqual(table_count(connection, "printer_pairs"), 1)
            self.assertEqual(table_count(connection, "printer_token_snapshots"), 1)
            for table in CONTEXT_TABLES:
                self.assertEqual(table_count(connection, table), 1, table)
            for table in MEMORY_OUTPUT_TABLES:
                self.assertEqual(table_count(connection, table), 1, table)
            self.assertEqual(table_count(connection, "printer_memory_audit_reports"), 1)
            self.assertEqual(table_count(connection, "printer_paper_decisions"), 0)
            self.assertEqual(table_count(connection, "printer_paper_positions"), 0)
            self.assertEqual(table_count(connection, "printer_scheduler_jobs"), 0)
            window = connection.execute("SELECT * FROM printer_memory_windows WHERE id = 1").fetchone()
            self.assertEqual(window["memory_quality_label"], "DIRTY_MEMORY")
            self.assertEqual(window["do_not_train"], 1)
        finally:
            connection.close()

    def test_classifier_and_readiness_report_real_memory_retrieval_state(self):
        db_path = self.make_db()
        self.seed_through_memory_audit(db_path)
        self.assertEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_MEMORY_QUALITY_AUDITED")
        build_retrieve_clean_memory_once_payload(self.retrieval_args(db_path))
        self.assertEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_REAL_MEMORY_RETRIEVAL")
        readiness = build_readiness_check_payload(self.readiness_args(db_path))
        self.assertEqual(readiness["db_state_classification"], "PERSISTENT_DB_REAL_MEMORY_RETRIEVAL")
        self.assertEqual(readiness["readiness_label"], "READY_REAL_MEMORY_RETRIEVAL")

    def test_real_memory_retrieval_state_with_runtime_row_is_not_safe(self):
        db_path = self.make_db()
        self.seed_through_memory_audit(db_path)
        build_retrieve_clean_memory_once_payload(self.retrieval_args(db_path))
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                INSERT INTO printer_scheduler_jobs (
                    job_name, job_kind, target_table, target_id, priority, status, scheduled_for
                ) VALUES (
                    'phase31_runtime_blocker', 'MEMORY_WINDOW_CLOSE', 'printer_memory_retrieval_queries',
                    1, 0, 'RUNNING', datetime('now')
                )
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.assertNotEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_REAL_MEMORY_RETRIEVAL")

    def test_no_phase32_paper_decision_behavior_exists(self):
        cli_text = (SRC_PATH / "printer_v1" / "operator_cli" / "commands.py").read_text(encoding="utf-8")
        self.assertNotIn("printer-paper-decision", cli_text)


if __name__ == "__main__":
    unittest.main()

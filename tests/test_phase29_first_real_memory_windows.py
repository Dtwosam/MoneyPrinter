import argparse
import json
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
    FIRST_MEMORY_GUARD_TABLES,
    MEMORY_OUTPUT_TABLES,
    build_collect_context_once_payload,
    build_collect_token_snapshots_once_payload,
    build_manual_intake_token_pair_payload,
    build_memory_window_once_payload,
    build_readiness_check_payload,
)
from printer_v1.operator_db.status import classify_operator_db_state


def table_count(connection, table_name):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


class Phase29FirstRealMemoryWindowTests(unittest.TestCase):
    def make_db(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = pathlib.Path(temp_dir.name) / "phase29.sqlite3"
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
            "token_mint": "phase29-mint",
            "pair_address": "phase29-pair",
            "pool_address": None,
            "chain": "solana",
            "intake_reason": "operator approved phase 29 test",
            "source_reference": "manual-phase29-test",
            "source_request_id": None,
            "token_symbol": "P29",
            "token_name": "Phase 29",
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
            "token_mint": "phase29-mint",
            "token_id": None,
            "pair_address": "phase29-pair",
            "pair_id": None,
            "chain": "solana",
            "snapshot_count": 1,
            "max_seconds": 5.0,
            "source_name": "dexscreener",
            "source_reference": "phase29-fixture",
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
            "token_mint": "phase29-mint",
            "token_id": None,
            "pair_address": "phase29-pair",
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
            "token_mint": "phase29-mint",
            "token_id": None,
            "pair_address": "phase29-pair",
            "pair_id": None,
            "snapshot_id": None,
            "chain": "solana",
            "memory_window": "15m",
            "source_reference": "phase29-test",
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
                    "pairAddress": "phase29-pair",
                    "baseToken": {
                        "address": "phase29-mint",
                        "symbol": "P29",
                        "name": "Phase 29",
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

    def seed_through_context(self, db_path):
        build_manual_intake_token_pair_payload(self.intake_args(db_path))
        build_collect_token_snapshots_once_payload(self.snapshot_args(db_path), transport=self.success_transport)
        return build_collect_context_once_payload(self.context_args(db_path))

    def test_memory_command_exists_in_pyproject(self):
        scripts = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertEqual(
            scripts["printer-build-memory-window-once"],
            "printer_v1.operator_cli.commands:main_build_memory_window_once",
        )

    def test_memory_command_requires_operator_approval(self):
        db_path = self.make_db()
        self.seed_through_context(db_path)
        with self.assertRaises(ValueError):
            build_memory_window_once_payload(self.memory_args(db_path, operator_approved=False))

    def test_memory_command_rejects_non_solana_chain(self):
        db_path = self.make_db()
        self.seed_through_context(db_path)
        with self.assertRaises(ValueError):
            build_memory_window_once_payload(self.memory_args(db_path, chain="ethereum"))

    def test_memory_command_rejects_unknown_token_or_pair(self):
        db_path = self.make_db()
        self.seed_through_context(db_path)
        with self.assertRaises(ValueError):
            build_memory_window_once_payload(self.memory_args(db_path, token_mint="unknown-mint"))
        with self.assertRaises(ValueError):
            build_memory_window_once_payload(self.memory_args(db_path, pair_address="unknown-pair"))

    def test_memory_command_rejects_unsupported_windows(self):
        db_path = self.make_db()
        self.seed_through_context(db_path)
        for window in ("1h", "4h", "12h", "24h"):
            with self.assertRaises(ValueError):
                build_memory_window_once_payload(self.memory_args(db_path, memory_window=window))

    def test_memory_command_rejects_missing_snapshot_evidence(self):
        db_path = self.make_db()
        build_manual_intake_token_pair_payload(self.intake_args(db_path))
        with self.assertRaises(ValueError):
            build_memory_window_once_payload(self.memory_args(db_path))

    def test_memory_command_rejects_missing_context_evidence(self):
        db_path = self.make_db()
        build_manual_intake_token_pair_payload(self.intake_args(db_path))
        build_collect_token_snapshots_once_payload(self.snapshot_args(db_path), transport=self.success_transport)
        with self.assertRaises(ValueError):
            build_memory_window_once_payload(self.memory_args(db_path))

    def test_memory_command_creates_allowed_memory_rows_only(self):
        db_path = self.make_db()
        self.seed_through_context(db_path)
        payload = build_memory_window_once_payload(self.memory_args(db_path))
        result = payload["memory_result"]
        self.assertEqual(payload["token_delta"], 0)
        self.assertEqual(payload["pair_delta"], 0)
        self.assertEqual(payload["snapshot_delta"], 0)
        self.assertEqual(payload["context_delta_total"], 0)
        self.assertEqual(payload["source_request_delta"], 0)
        self.assertEqual(payload["source_response_delta"], 0)
        self.assertEqual(payload["source_failure_delta"], 0)
        self.assertEqual(payload["retrieval_delta"], 0)
        self.assertEqual(payload["paper_decision_delta"], 0)
        self.assertEqual(payload["paper_position_delta"], 0)
        self.assertTrue(payload["guard_tables_unchanged"])
        self.assertEqual(payload["db_state_classification"], "PERSISTENT_DB_FIRST_MEMORY_WINDOW")
        self.assertEqual(result["memory_quality_label"], "DIRTY_MEMORY")
        self.assertFalse(result["retrieval_ready"])
        self.assertIn("REJECT_MISSING_SNAPSHOTS", result["rejection_reasons"])
        self.assertIn("INCOMPLETE_15M_WINDOW", result["rejection_reasons"])

        connection = sqlite3.connect(db_path)
        try:
            self.assertEqual(table_count(connection, "printer_tokens"), 1)
            self.assertEqual(table_count(connection, "printer_pairs"), 1)
            self.assertEqual(table_count(connection, "printer_token_snapshots"), 1)
            for table in CONTEXT_TABLES:
                self.assertEqual(table_count(connection, table), 1, table)
            for table in MEMORY_OUTPUT_TABLES:
                self.assertEqual(table_count(connection, table), 1, table)
            for table in FIRST_MEMORY_GUARD_TABLES:
                self.assertEqual(table_count(connection, table), 0, table)
            row = connection.execute("SELECT * FROM printer_memory_fingerprints").fetchone()
            self.assertEqual(row[6], 1)
            fingerprint = json.loads(row[3])
            self.assertFalse(fingerprint["retrieval_ready"])
        finally:
            connection.close()

    def test_classifier_reports_context_and_first_memory_states(self):
        db_path = self.make_db()
        self.seed_through_context(db_path)
        self.assertEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_CONTROLLED_CONTEXT")
        build_memory_window_once_payload(self.memory_args(db_path))
        self.assertEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_FIRST_MEMORY_WINDOW")

    def test_readiness_reports_first_memory_window(self):
        db_path = self.make_db()
        self.seed_through_context(db_path)
        build_memory_window_once_payload(self.memory_args(db_path))
        readiness = build_readiness_check_payload(self.readiness_args(db_path))
        self.assertEqual(readiness["db_state_classification"], "PERSISTENT_DB_FIRST_MEMORY_WINDOW")
        self.assertEqual(readiness["readiness_label"], "READY_FIRST_MEMORY_WINDOW")
        self.assertTrue(readiness["memory_has_started"])

    def test_first_memory_state_with_retrieval_or_paper_rows_is_not_safe(self):
        db_path = self.make_db()
        self.seed_through_context(db_path)
        build_memory_window_once_payload(self.memory_args(db_path))
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                INSERT INTO printer_memory_retrieval_queries (
                    query_type, token_id, pair_id, token_mint, pair_address, query_at,
                    current_fingerprint_json, query_context_json, retrieval_result_label,
                    memory_evidence_label, data_quality_label, source_status
                ) VALUES (
                    'AUDIT_MEMORY_REVIEW_QUERY', 1, 1, 'phase29-mint', 'phase29-pair',
                    datetime('now'), '{}', '{}', 'RETRIEVAL_BLOCKED_NO_CLEAN_MEMORY',
                    'MEMORY_EVIDENCE_NOT_ENOUGH', 'MISSING_CRITICAL_DATA', 'PARTIAL'
                )
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.assertNotEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_FIRST_MEMORY_WINDOW")

    def test_no_phase30_or_phase31_or_phase32_behavior_exists(self):
        cli_text = (SRC_PATH / "printer_v1" / "operator_cli" / "commands.py").read_text(encoding="utf-8")
        self.assertNotIn("printer-memory-audit", cli_text)
        self.assertNotIn("printer-memory-retrieval", cli_text)
        self.assertNotIn("printer-paper-decision", cli_text)


if __name__ == "__main__":
    unittest.main()

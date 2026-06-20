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
    MEMORY_OUTPUT_TABLES,
    build_collect_context_once_payload,
    build_collect_token_snapshots_once_payload,
    build_create_paper_decision_once_payload,
    build_manual_intake_token_pair_payload,
    build_memory_quality_audit_once_payload,
    build_memory_window_once_payload,
    build_readiness_check_payload,
    build_retrieve_clean_memory_once_payload,
)
from printer_v1.operator_db.status import classify_operator_db_state


def table_count(connection, table_name):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


class Phase32RealDataPaperDecisionActivationTests(unittest.TestCase):
    def make_db(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = pathlib.Path(temp_dir.name) / "phase32.sqlite3"
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
            "token_mint": "phase32-mint",
            "pair_address": "phase32-pair",
            "pool_address": None,
            "chain": "solana",
            "intake_reason": "operator approved phase 32 test",
            "source_reference": "manual-phase32-test",
            "source_request_id": None,
            "token_symbol": "P32",
            "token_name": "Phase 32",
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
            "token_mint": "phase32-mint",
            "token_id": None,
            "pair_address": "phase32-pair",
            "pair_id": None,
            "chain": "solana",
            "snapshot_count": 1,
            "max_seconds": 5.0,
            "source_name": "dexscreener",
            "source_reference": "phase32-fixture",
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
            "token_mint": "phase32-mint",
            "token_id": None,
            "pair_address": "phase32-pair",
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
            "token_mint": "phase32-mint",
            "token_id": None,
            "pair_address": "phase32-pair",
            "pair_id": None,
            "snapshot_id": None,
            "chain": "solana",
            "memory_window": "15m",
            "source_reference": "phase32-test",
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

    def decision_args(self, db_path, **overrides):
        values = {
            "db_path": str(db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "retrieval_query_id": 1,
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
                    "pairAddress": "phase32-pair",
                    "baseToken": {
                        "address": "phase32-mint",
                        "symbol": "P32",
                        "name": "Phase 32",
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

    def seed_through_real_memory_retrieval(self, db_path):
        build_manual_intake_token_pair_payload(self.intake_args(db_path))
        build_collect_token_snapshots_once_payload(self.snapshot_args(db_path), transport=self.success_transport)
        build_collect_context_once_payload(self.context_args(db_path))
        build_memory_window_once_payload(self.memory_args(db_path))
        build_memory_quality_audit_once_payload(self.audit_args(db_path))
        return build_retrieve_clean_memory_once_payload(self.retrieval_args(db_path))

    def test_paper_decision_command_exists_in_pyproject(self):
        scripts = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertEqual(
            scripts["printer-create-paper-decision-once"],
            "printer_v1.operator_cli.commands:main_create_paper_decision_once",
        )

    def test_paper_decision_requires_operator_approval(self):
        db_path = self.make_db()
        self.seed_through_real_memory_retrieval(db_path)
        with self.assertRaises(ValueError):
            build_create_paper_decision_once_payload(self.decision_args(db_path, operator_approved=False))

    def test_paper_decision_rejects_unknown_inputs_and_non_solana(self):
        db_path = self.make_db()
        self.seed_through_real_memory_retrieval(db_path)
        with self.assertRaises(ValueError):
            build_create_paper_decision_once_payload(self.decision_args(db_path, retrieval_query_id=999))
        with self.assertRaises(ValueError):
            build_create_paper_decision_once_payload(
                self.decision_args(db_path, retrieval_query_id=None, snapshot_id=None, token_mint="unknown", pair_address="phase32-pair")
            )
        with self.assertRaises(ValueError):
            build_create_paper_decision_once_payload(self.decision_args(db_path, chain="ethereum"))

    def test_paper_decision_blocks_buy_and_writes_only_decision_row(self):
        db_path = self.make_db()
        self.seed_through_real_memory_retrieval(db_path)
        payload = build_create_paper_decision_once_payload(self.decision_args(db_path))
        report = payload["decision_report"]
        summary = payload["retrieval_summary"]

        self.assertEqual(payload["paper_decision_delta"], 1)
        self.assertEqual(payload["guard_table_deltas"], {})
        self.assertTrue(payload["guard_tables_unchanged"])
        self.assertEqual(payload["db_state_classification"], "PERSISTENT_DB_REAL_DATA_PAPER_DECISION")
        self.assertEqual(payload["decision_action"], "NO_ACTION")
        self.assertEqual(payload["paper_decision_status_label"], "PAPER_DECISION_BLOCKED")
        self.assertEqual(payload["decision_gate_label"], "DECISION_BLOCKED_NO_CLEAN_MEMORY")
        self.assertEqual(payload["memory_evidence_gate_label"], "MEMORY_GATE_DIRTY_ONLY")
        self.assertEqual(summary["clean_eligible_memory_count"], 0)
        self.assertEqual(summary["dirty_memory_count"], 1)
        self.assertEqual(summary["blocked_dirty_memory_count"], 1)
        self.assertEqual(summary["clean_matches_returned"], 0)
        self.assertEqual(summary["dirty_matches_used_for_decision"], 0)
        self.assertFalse(summary["dirty_memory_used"])
        self.assertFalse(summary["retrieval_allowed"])
        self.assertFalse(summary["decision_allowed"])
        self.assertFalse(summary["buy_allowed"])
        self.assertFalse(summary["paper_position_allowed"])
        self.assertEqual(report["Similar clean memories found"], 0)
        self.assertEqual(report["Current action"], "NO_ACTION")
        self.assertEqual(report["Paper trade status"], "NO_POSITION_OPENED")

        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        try:
            self.assertEqual(table_count(connection, "printer_paper_decisions"), 1)
            self.assertEqual(table_count(connection, "printer_paper_positions"), 0)
            self.assertEqual(table_count(connection, "printer_paper_trade_events"), 0)
            self.assertEqual(table_count(connection, "printer_tokens"), 1)
            self.assertEqual(table_count(connection, "printer_pairs"), 1)
            self.assertEqual(table_count(connection, "printer_token_snapshots"), 1)
            for table in CONTEXT_TABLES:
                self.assertEqual(table_count(connection, table), 1, table)
            for table in MEMORY_OUTPUT_TABLES:
                self.assertEqual(table_count(connection, table), 1, table)
            self.assertEqual(table_count(connection, "printer_memory_retrieval_queries"), 1)
            self.assertEqual(table_count(connection, "printer_memory_retrieval_matches"), 0)
            self.assertEqual(table_count(connection, "printer_scheduler_jobs"), 0)
            decision = connection.execute("SELECT * FROM printer_paper_decisions").fetchone()
            self.assertEqual(decision["decision_action"], "NO_ACTION")
            self.assertEqual(decision["final_action_label"], "NO_ACTION")
            self.assertEqual(decision["paper_decision_status_label"], "PAPER_DECISION_BLOCKED")
            self.assertEqual(decision["decision_gate_label"], "DECISION_BLOCKED_NO_CLEAN_MEMORY")
            self.assertEqual(decision["retrieval_query_id"], 1)
            decision_report = json.loads(decision["decision_report_json"])
            self.assertEqual(decision_report["Decision"], "NO_ACTION")
        finally:
            connection.close()

    def test_classifier_and_readiness_report_paper_decision_state(self):
        db_path = self.make_db()
        self.seed_through_real_memory_retrieval(db_path)
        self.assertEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_REAL_MEMORY_RETRIEVAL")
        build_create_paper_decision_once_payload(self.decision_args(db_path))
        self.assertEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_REAL_DATA_PAPER_DECISION")
        readiness = build_readiness_check_payload(self.readiness_args(db_path))
        self.assertEqual(readiness["db_state_classification"], "PERSISTENT_DB_REAL_DATA_PAPER_DECISION")
        self.assertEqual(readiness["readiness_label"], "READY_REAL_DATA_PAPER_DECISION")

    def test_paper_decision_state_with_buy_or_position_is_not_safe(self):
        db_path = self.make_db()
        self.seed_through_real_memory_retrieval(db_path)
        build_create_paper_decision_once_payload(self.decision_args(db_path))
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                INSERT INTO printer_paper_decisions (
                    token_id, pair_id, decision_action, decision_status, source_status, data_quality_label,
                    decided_at, token_mint, pair_address, requested_action_label, final_action_label,
                    decision_gate_label, memory_evidence_gate_label, paper_decision_status_label
                ) VALUES (
                    1, 1, 'BUY', 'PAPER_DECISION_PROPOSED', 'COMPLETE', 'CLEAN_DATA',
                    datetime('now'), 'phase32-mint', 'phase32-pair', 'BUY', 'BUY',
                    'DECISION_ALLOWED', 'MEMORY_GATE_CLEAN_MATCH', 'PAPER_DECISION_PROPOSED'
                )
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.assertNotEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_REAL_DATA_PAPER_DECISION")

        db_path = self.make_db()
        self.seed_through_real_memory_retrieval(db_path)
        payload = build_create_paper_decision_once_payload(self.decision_args(db_path))
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                INSERT INTO printer_paper_positions (
                    paper_decision_id, token_id, pair_id, position_status
                ) VALUES (?, 1, 1, 'OPEN')
                """,
                (payload["paper_decision_id"],),
            )
            connection.commit()
        finally:
            connection.close()
        self.assertNotEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_REAL_DATA_PAPER_DECISION")

    def test_no_phase33_position_command_exists(self):
        cli_text = (SRC_PATH / "printer_v1" / "operator_cli" / "commands.py").read_text(encoding="utf-8")
        self.assertNotIn("printer-open-paper-position", cli_text)
        self.assertNotIn("printer-monitor-paper-position", cli_text)


if __name__ == "__main__":
    unittest.main()

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
    build_audit_paper_decision_once_payload,
    build_collect_context_once_payload,
    build_collect_token_snapshots_once_payload,
    build_create_paper_decision_once_payload,
    build_manual_intake_token_pair_payload,
    build_memory_quality_audit_once_payload,
    build_memory_window_once_payload,
    build_retrieve_clean_memory_once_payload,
)
from printer_v1.operator_db.status import classify_operator_db_state


def table_count(connection, table_name):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


class Phase34RealPaperAuditOperatorReviewTests(unittest.TestCase):
    def make_db(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = pathlib.Path(temp_dir.name) / "phase34.sqlite3"
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
            "token_mint": "phase34-mint",
            "pair_address": "phase34-pair",
            "pool_address": None,
            "chain": "solana",
            "intake_reason": "operator approved phase 34 test",
            "source_reference": "manual-phase34-test",
            "source_request_id": None,
            "token_symbol": "P34",
            "token_name": "Phase 34",
            "dex_id": "dexscreener",
            "intake_json": None,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def snapshot_args(self, db_path):
        return argparse.Namespace(
            db_path=str(db_path),
            project_root=str(PROJECT_ROOT),
            format="json",
            no_color=True,
            operator_approved=True,
            token_mint="phase34-mint",
            token_id=None,
            pair_address="phase34-pair",
            pair_id=None,
            chain="solana",
            snapshot_count=1,
            max_seconds=5.0,
            source_name="dexscreener",
            source_reference="phase34-fixture",
        )

    def context_args(self, db_path):
        return argparse.Namespace(
            db_path=str(db_path),
            project_root=str(PROJECT_ROOT),
            format="json",
            no_color=True,
            operator_approved=True,
            token_mint="phase34-mint",
            token_id=None,
            pair_address="phase34-pair",
            pair_id=None,
            snapshot_id=None,
            chain="solana",
            source_name="dexscreener",
        )

    def memory_args(self, db_path):
        return argparse.Namespace(
            db_path=str(db_path),
            project_root=str(PROJECT_ROOT),
            format="json",
            no_color=True,
            operator_approved=True,
            token_mint="phase34-mint",
            token_id=None,
            pair_address="phase34-pair",
            pair_id=None,
            snapshot_id=None,
            chain="solana",
            memory_window="15m",
            source_reference="phase34-test",
        )

    def audit_memory_args(self, db_path):
        return argparse.Namespace(
            db_path=str(db_path),
            project_root=str(PROJECT_ROOT),
            format="json",
            no_color=True,
            operator_approved=True,
            memory_window_id=1,
            episode_id=None,
            token_mint=None,
            token_id=None,
            pair_address=None,
            pair_id=None,
            chain="solana",
        )

    def retrieval_args(self, db_path):
        return argparse.Namespace(
            db_path=str(db_path),
            project_root=str(PROJECT_ROOT),
            format="json",
            no_color=True,
            operator_approved=True,
            snapshot_id=1,
            token_mint=None,
            token_id=None,
            pair_address=None,
            pair_id=None,
            chain="solana",
        )

    def decision_args(self, db_path):
        return argparse.Namespace(
            db_path=str(db_path),
            project_root=str(PROJECT_ROOT),
            format="json",
            no_color=True,
            operator_approved=True,
            retrieval_query_id=1,
            snapshot_id=1,
            token_mint=None,
            token_id=None,
            pair_address=None,
            pair_id=None,
            chain="solana",
        )

    def paper_audit_args(self, db_path, **overrides):
        values = {
            "db_path": str(db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "decision_id": 1,
            "snapshot_id": 1,
            "token_mint": None,
            "token_id": None,
            "pair_address": None,
            "pair_id": None,
            "chain": "solana",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def success_transport(self, context):
        del context
        return {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": "phase34-pair",
                    "baseToken": {"address": "phase34-mint", "symbol": "P34", "name": "Phase 34"},
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

    def seed_through_blocked_paper_decision(self, db_path):
        build_manual_intake_token_pair_payload(self.intake_args(db_path))
        build_collect_token_snapshots_once_payload(self.snapshot_args(db_path), transport=self.success_transport)
        build_collect_context_once_payload(self.context_args(db_path))
        build_memory_window_once_payload(self.memory_args(db_path))
        build_memory_quality_audit_once_payload(self.audit_memory_args(db_path))
        build_retrieve_clean_memory_once_payload(self.retrieval_args(db_path))
        return build_create_paper_decision_once_payload(self.decision_args(db_path))

    def test_paper_audit_command_exists_in_pyproject(self):
        scripts = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertEqual(
            scripts["printer-audit-paper-decision-once"],
            "printer_v1.operator_cli.commands:main_audit_paper_decision_once",
        )

    def test_paper_audit_requires_operator_approval(self):
        db_path = self.make_db()
        self.seed_through_blocked_paper_decision(db_path)
        with self.assertRaises(ValueError):
            build_audit_paper_decision_once_payload(self.paper_audit_args(db_path, operator_approved=False))

    def test_paper_audit_rejects_unknown_inputs_and_non_solana(self):
        db_path = self.make_db()
        self.seed_through_blocked_paper_decision(db_path)
        with self.assertRaises(ValueError):
            build_audit_paper_decision_once_payload(self.paper_audit_args(db_path, decision_id=999))
        with self.assertRaises(ValueError):
            build_audit_paper_decision_once_payload(self.paper_audit_args(db_path, decision_id=None, token_mint="unknown", pair_address="phase34-pair"))
        with self.assertRaises(ValueError):
            build_audit_paper_decision_once_payload(self.paper_audit_args(db_path, chain="ethereum"))

    def test_paper_audit_records_only_audit_and_review_rows(self):
        db_path = self.make_db()
        self.seed_through_blocked_paper_decision(db_path)
        payload = build_audit_paper_decision_once_payload(self.paper_audit_args(db_path))
        report = payload["audit_report"]

        self.assertEqual(payload["paper_audit_delta"], 1)
        self.assertEqual(payload["operator_review_report_delta"], 1)
        self.assertEqual(payload["operator_review_item_delta"], 4)
        self.assertEqual(payload["guard_table_deltas"], {})
        self.assertTrue(payload["guard_tables_unchanged"])
        self.assertEqual(payload["db_state_classification"], "PERSISTENT_DB_REAL_PAPER_AUDIT_OPERATOR_REVIEW")
        self.assertEqual(report["decision_action"], "NO_ACTION")
        self.assertEqual(report["decision_status"], "PAPER_DECISION_BLOCKED")
        self.assertEqual(report["clean_eligible_memory_count"], 0)
        self.assertEqual(report["dirty_memory_count"], 1)
        self.assertFalse(report["dirty_memory_used_for_decision"])
        self.assertEqual(report["retrieval_match_count"], 0)
        self.assertEqual(report["buy_count"], 0)
        self.assertEqual(report["paper_position_count"], 0)
        self.assertEqual(report["open_paper_position_count"], 0)
        self.assertEqual(report["paper_trade_event_count"], 0)
        self.assertFalse(report["simulated_pnl_available"])
        self.assertEqual(report["decision_quality_label"], "BLOCKED_DECISION_VALID")
        self.assertEqual(report["trade_quality_label"], "NO_TRADE_OPENED")
        self.assertEqual(report["profit_realism_label"], "NO_PNL_NOT_APPLICABLE")
        self.assertEqual(report["memory_safety_label"], "DIRTY_MEMORY_BLOCKED")
        self.assertEqual(report["retrieval_safety_label"], "NO_CLEAN_MEMORY_MATCHES")
        self.assertEqual(report["monitor_safety_label"], "POSITION_OPEN_BLOCKED")
        self.assertEqual(report["operator_review_verdict"], "SAFE_BLOCKED_BEHAVIOR")
        self.assertIn("NO_FAKE_PROFIT", report["issue_labels"])
        self.assertFalse(report["paper_win"])
        self.assertFalse(report["paper_loss"])
        self.assertFalse(report["live_execution"])

        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        try:
            self.assertEqual(table_count(connection, "printer_tokens"), 1)
            self.assertEqual(table_count(connection, "printer_pairs"), 1)
            self.assertEqual(table_count(connection, "printer_source_requests"), 1)
            self.assertEqual(table_count(connection, "printer_token_snapshots"), 1)
            self.assertEqual(table_count(connection, "printer_memory_windows"), 1)
            self.assertEqual(table_count(connection, "printer_memory_retrieval_queries"), 1)
            self.assertEqual(table_count(connection, "printer_memory_retrieval_matches"), 0)
            self.assertEqual(table_count(connection, "printer_paper_decisions"), 1)
            self.assertEqual(table_count(connection, "printer_paper_positions"), 0)
            self.assertEqual(table_count(connection, "printer_paper_trade_events"), 0)
            self.assertEqual(table_count(connection, "printer_paper_audit_reports"), 1)
            self.assertEqual(table_count(connection, "printer_operator_review_reports"), 1)
            self.assertEqual(table_count(connection, "printer_operator_review_items"), 4)
            self.assertEqual(table_count(connection, "printer_scheduler_jobs"), 0)
            audit = connection.execute("SELECT * FROM printer_paper_audit_reports WHERE id = 1").fetchone()
            self.assertEqual(audit["paper_outcome_review_label"], "PAPER_OUTCOME_NO_ACTION_VALID")
            self.assertEqual(audit["paper_realism_label"], "PAPER_REALISM_ACCEPTABLE")
            audit_payload = json.loads(audit["audit_report_json"])
            self.assertEqual(audit_payload["profit_realism_label"], "NO_PNL_NOT_APPLICABLE")
        finally:
            connection.close()

    def test_classifier_reports_real_paper_audit_operator_review_state(self):
        db_path = self.make_db()
        self.seed_through_blocked_paper_decision(db_path)
        self.assertEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_REAL_DATA_PAPER_DECISION")
        build_audit_paper_decision_once_payload(self.paper_audit_args(db_path))
        self.assertEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_REAL_PAPER_AUDIT_OPERATOR_REVIEW")

    def test_audit_state_with_position_or_profit_outcome_is_unsafe(self):
        db_path = self.make_db()
        self.seed_through_blocked_paper_decision(db_path)
        build_audit_paper_decision_once_payload(self.paper_audit_args(db_path))
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                INSERT INTO printer_paper_positions (
                    paper_decision_id, token_id, pair_id, position_status,
                    paper_position_status_label, entry_status_label
                )
                VALUES (1, 1, 1, 'PAPER_POSITION_OPEN', 'PAPER_POSITION_OPEN', 'PAPER_ENTRY_ALLOWED')
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.assertNotEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_REAL_PAPER_AUDIT_OPERATOR_REVIEW")

    def test_no_phase35_scheduler_single_tick_command_exists(self):
        scripts = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertNotIn("printer-run-scheduler-once", scripts)


if __name__ == "__main__":
    unittest.main()

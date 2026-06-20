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
    build_collect_context_once_payload,
    build_collect_token_snapshots_once_payload,
    build_create_paper_decision_once_payload,
    build_manual_intake_token_pair_payload,
    build_memory_quality_audit_once_payload,
    build_memory_window_once_payload,
    build_monitor_simulated_paper_position_once_payload,
    build_retrieve_clean_memory_once_payload,
)
from printer_v1.operator_db.status import classify_operator_db_state


def table_count(connection, table_name):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


class Phase33RealDataSimulatedPaperPositionMonitorTests(unittest.TestCase):
    def make_db(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = pathlib.Path(temp_dir.name) / "phase33.sqlite3"
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
            "token_mint": "phase33-mint",
            "pair_address": "phase33-pair",
            "pool_address": None,
            "chain": "solana",
            "intake_reason": "operator approved phase 33 test",
            "source_reference": "manual-phase33-test",
            "source_request_id": None,
            "token_symbol": "P33",
            "token_name": "Phase 33",
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
            "token_mint": "phase33-mint",
            "token_id": None,
            "pair_address": "phase33-pair",
            "pair_id": None,
            "chain": "solana",
            "snapshot_count": 1,
            "max_seconds": 5.0,
            "source_name": "dexscreener",
            "source_reference": "phase33-fixture",
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
            "token_mint": "phase33-mint",
            "token_id": None,
            "pair_address": "phase33-pair",
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
            "token_mint": "phase33-mint",
            "token_id": None,
            "pair_address": "phase33-pair",
            "pair_id": None,
            "snapshot_id": None,
            "chain": "solana",
            "memory_window": "15m",
            "source_reference": "phase33-test",
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

    def monitor_args(self, db_path, **overrides):
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
                    "pairAddress": "phase33-pair",
                    "baseToken": {"address": "phase33-mint", "symbol": "P33", "name": "Phase 33"},
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
        build_memory_quality_audit_once_payload(self.audit_args(db_path))
        build_retrieve_clean_memory_once_payload(self.retrieval_args(db_path))
        return build_create_paper_decision_once_payload(self.decision_args(db_path))

    def test_monitor_command_exists_in_pyproject(self):
        scripts = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertEqual(
            scripts["printer-monitor-simulated-paper-position-once"],
            "printer_v1.operator_cli.commands:main_monitor_simulated_paper_position_once",
        )

    def test_monitor_requires_operator_approval(self):
        db_path = self.make_db()
        self.seed_through_blocked_paper_decision(db_path)
        with self.assertRaises(ValueError):
            build_monitor_simulated_paper_position_once_payload(self.monitor_args(db_path, operator_approved=False))

    def test_monitor_rejects_unknown_inputs_and_non_solana(self):
        db_path = self.make_db()
        self.seed_through_blocked_paper_decision(db_path)
        with self.assertRaises(ValueError):
            build_monitor_simulated_paper_position_once_payload(self.monitor_args(db_path, decision_id=999))
        with self.assertRaises(ValueError):
            build_monitor_simulated_paper_position_once_payload(self.monitor_args(db_path, decision_id=None, token_mint="unknown", pair_address="phase33-pair"))
        with self.assertRaises(ValueError):
            build_monitor_simulated_paper_position_once_payload(self.monitor_args(db_path, chain="ethereum"))

    def test_monitor_blocks_position_from_blocked_no_action_decision(self):
        db_path = self.make_db()
        self.seed_through_blocked_paper_decision(db_path)
        payload = build_monitor_simulated_paper_position_once_payload(self.monitor_args(db_path))
        report = payload["monitor_report"]

        self.assertTrue(payload["guard_tables_unchanged"])
        self.assertEqual(payload["guard_table_deltas"], {})
        self.assertFalse(payload["monitor_attempt_recorded"])
        self.assertEqual(payload["monitor_attempt_rows"], 0)
        self.assertEqual(report["monitor_action"], "POSITION_BLOCKED")
        self.assertEqual(report["decision_action"], "NO_ACTION")
        self.assertEqual(report["decision_status"], "PAPER_DECISION_BLOCKED")
        self.assertFalse(report["buy_allowed"])
        self.assertFalse(report["buy_unlocked"])
        self.assertEqual(report["clean_eligible_memory_count"], 0)
        self.assertFalse(report["dirty_memory_used"])
        self.assertFalse(report["paper_position_allowed"])
        self.assertEqual(report["existing_open_position_count"], 0)
        self.assertFalse(report["position_opened"])
        self.assertIsNone(report["position_id"])
        self.assertIn("BLOCKED_DECISION_NOT_BUY", report["blocked_reason"])
        self.assertIn("BLOCKED_DECISION_NOT_ALLOWED", report["blocked_reason"])
        self.assertIn("BLOCKED_NO_CLEAN_MEMORY", report["blocked_reason"])
        self.assertIn("BLOCKED_PAPER_POSITION_NOT_ALLOWED", report["blocked_reason"])
        self.assertFalse(report["paper_trade_event_created"])
        self.assertFalse(report["simulated_pnl_created"])
        self.assertFalse(report["runtime_started"])
        self.assertFalse(report["scheduler_executed"])

        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        try:
            self.assertEqual(table_count(connection, "printer_tokens"), 1)
            self.assertEqual(table_count(connection, "printer_pairs"), 1)
            self.assertEqual(table_count(connection, "printer_source_requests"), 1)
            self.assertEqual(table_count(connection, "printer_token_snapshots"), 1)
            self.assertEqual(sum(table_count(connection, table) for table in [
                "printer_market_regime_snapshots",
                "printer_solana_chain_heat_snapshots",
                "printer_safety_rug_snapshots",
                "printer_liquidity_exit_snapshots",
                "printer_trading_flow_snapshots",
                "printer_chart_volatility_snapshots",
                "printer_micro_events",
            ]), 7)
            self.assertEqual(table_count(connection, "printer_memory_windows"), 1)
            self.assertEqual(table_count(connection, "printer_memory_retrieval_queries"), 1)
            self.assertEqual(table_count(connection, "printer_memory_retrieval_matches"), 0)
            self.assertEqual(table_count(connection, "printer_paper_decisions"), 1)
            self.assertEqual(table_count(connection, "printer_paper_positions"), 0)
            self.assertEqual(table_count(connection, "printer_paper_trade_events"), 0)
            self.assertEqual(table_count(connection, "printer_scheduler_jobs"), 0)
            decision = connection.execute("SELECT * FROM printer_paper_decisions WHERE id = 1").fetchone()
            self.assertEqual(decision["final_action_label"], "NO_ACTION")
            self.assertEqual(decision["paper_decision_status_label"], "PAPER_DECISION_BLOCKED")
        finally:
            connection.close()

    def test_classifier_remains_real_data_paper_decision_for_output_only_monitor(self):
        db_path = self.make_db()
        self.seed_through_blocked_paper_decision(db_path)
        payload = build_monitor_simulated_paper_position_once_payload(self.monitor_args(db_path))
        self.assertEqual(payload["db_state_classification"], "PERSISTENT_DB_REAL_DATA_PAPER_DECISION")
        self.assertEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_REAL_DATA_PAPER_DECISION")

    def test_position_from_blocked_decision_is_not_phase33_safe(self):
        db_path = self.make_db()
        self.seed_through_blocked_paper_decision(db_path)
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
        self.assertNotEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_SIMULATED_PAPER_POSITION_MONITOR")
        self.assertEqual(classify_operator_db_state(db_path, PROJECT_ROOT), "PERSISTENT_DB_HAS_REAL_PAPER_ROWS")

    def test_no_phase34_paper_audit_command_exists(self):
        scripts = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertNotIn("printer-audit-real-paper-once", scripts)


if __name__ == "__main__":
    unittest.main()

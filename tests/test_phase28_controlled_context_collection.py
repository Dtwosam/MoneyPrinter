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
    CONTROLLED_CONTEXT_GUARD_TABLES,
    build_collect_context_once_payload,
    build_collect_token_snapshots_once_payload,
    build_manual_intake_token_pair_payload,
    build_readiness_check_payload,
)
from printer_v1.operator_db.status import classify_operator_db_state


def table_count(connection, table_name):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


class Phase28ControlledContextCollectionTests(unittest.TestCase):
    def make_db(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = pathlib.Path(temp_dir.name) / "phase28.sqlite3"
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
            "token_mint": "phase28-mint",
            "pair_address": "phase28-pair",
            "pool_address": None,
            "chain": "solana",
            "intake_reason": "operator approved phase 28 test",
            "source_reference": "manual-phase28-test",
            "source_request_id": None,
            "token_symbol": "P28",
            "token_name": "Phase 28",
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
            "token_mint": "phase28-mint",
            "token_id": None,
            "pair_address": "phase28-pair",
            "pair_id": None,
            "chain": "solana",
            "snapshot_count": 1,
            "max_seconds": 5.0,
            "source_name": "dexscreener",
            "source_reference": "phase28-fixture",
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
            "token_mint": "phase28-mint",
            "token_id": None,
            "pair_address": "phase28-pair",
            "pair_id": None,
            "snapshot_id": None,
            "chain": "solana",
            "source_name": "dexscreener",
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
                    "pairAddress": "phase28-pair",
                    "baseToken": {
                        "address": "phase28-mint",
                        "symbol": "P28",
                        "name": "Phase 28",
                    },
                    "priceUsd": "0.00042",
                    "liquidity": {"usd": 12345.67},
                    "volume": {"m5": 100.0, "h1": 500.0, "h24": 2400.0},
                    "txns": {
                        "m5": {"buys": 2, "sells": 1},
                        "h1": {"buys": 12, "sells": 9},
                        "h24": {"buys": 40, "sells": 44},
                    },
                    "fdv": 420000.0,
                    "marketCap": 390000.0,
                    "priceChange": {"m5": 1.2, "h1": 4.5, "h24": 9.0},
                }
            ]
        }

    def seed_intake_and_snapshot(self, db_path):
        build_manual_intake_token_pair_payload(self.intake_args(db_path))
        return build_collect_token_snapshots_once_payload(
            self.snapshot_args(db_path),
            transport=self.success_transport,
        )

    def test_context_command_exists_in_pyproject(self):
        scripts = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertEqual(
            scripts["printer-collect-context-once"],
            "printer_v1.operator_cli.commands:main_collect_context_once",
        )

    def test_context_command_requires_explicit_operator_approval(self):
        db_path = self.make_db()
        self.seed_intake_and_snapshot(db_path)
        with self.assertRaises(ValueError):
            build_collect_context_once_payload(self.context_args(db_path, operator_approved=False))

    def test_context_command_rejects_non_solana_chain(self):
        db_path = self.make_db()
        self.seed_intake_and_snapshot(db_path)
        with self.assertRaises(ValueError):
            build_collect_context_once_payload(self.context_args(db_path, chain="ethereum"))

    def test_context_command_rejects_unknown_token_or_pair(self):
        db_path = self.make_db()
        self.seed_intake_and_snapshot(db_path)
        with self.assertRaises(ValueError):
            build_collect_context_once_payload(self.context_args(db_path, token_mint="unknown-mint"))
        with self.assertRaises(ValueError):
            build_collect_context_once_payload(self.context_args(db_path, pair_address="unknown-pair"))

    def test_context_command_rejects_missing_snapshot_evidence(self):
        db_path = self.make_db()
        build_manual_intake_token_pair_payload(self.intake_args(db_path))
        with self.assertRaises(ValueError):
            build_collect_context_once_payload(self.context_args(db_path))

    def test_context_command_creates_allowed_context_rows_only(self):
        db_path = self.make_db()
        self.seed_intake_and_snapshot(db_path)
        payload = build_collect_context_once_payload(self.context_args(db_path))
        self.assertEqual(payload["token_delta"], 0)
        self.assertEqual(payload["pair_delta"], 0)
        self.assertEqual(payload["snapshot_delta"], 0)
        self.assertEqual(payload["source_request_delta"], 0)
        self.assertEqual(payload["source_response_delta"], 0)
        self.assertEqual(payload["source_failure_delta"], 0)
        self.assertEqual(payload["context_rows_created"], len(CONTEXT_TABLES))
        self.assertTrue(payload["guard_tables_unchanged"])
        self.assertEqual(payload["db_state_classification"], "PERSISTENT_DB_CONTROLLED_CONTEXT")

        connection = sqlite3.connect(db_path)
        try:
            self.assertEqual(table_count(connection, "printer_tokens"), 1)
            self.assertEqual(table_count(connection, "printer_pairs"), 1)
            self.assertEqual(table_count(connection, "printer_token_snapshots"), 1)
            for table in CONTEXT_TABLES:
                self.assertEqual(table_count(connection, table), 1, table)
            for table in CONTROLLED_CONTEXT_GUARD_TABLES:
                self.assertEqual(table_count(connection, table), 0, table)
        finally:
            connection.close()

    def test_context_rows_mark_unknown_evidence_honestly(self):
        db_path = self.make_db()
        self.seed_intake_and_snapshot(db_path)
        build_collect_context_once_payload(self.context_args(db_path))
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        try:
            safety = connection.execute("SELECT * FROM printer_safety_rug_snapshots").fetchone()
            market = connection.execute("SELECT * FROM printer_market_regime_snapshots").fetchone()
            micro = connection.execute("SELECT * FROM printer_micro_events").fetchone()
            self.assertEqual(safety["authority_label"], "AUTHORITY_UNKNOWN")
            self.assertEqual(safety["safety_gate_label"], "MANUAL_REVIEW_REQUIRED")
            self.assertEqual(market["market_regime_label"], "UNKNOWN")
            self.assertEqual(market["data_quality_label"], "MISSING_CRITICAL_DATA")
            self.assertEqual(micro["micro_event_state_label"], "MICRO_EVENT_UNKNOWN")
            self.assertEqual(micro["micro_event_memory_gate_label"], "MICRO_EVENT_AUDIT_ONLY")
        finally:
            connection.close()

    def test_classifier_reports_snapshot_and_context_states(self):
        db_path = self.make_db()
        self.seed_intake_and_snapshot(db_path)
        self.assertEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_CONTROLLED_SNAPSHOTS")
        build_collect_context_once_payload(self.context_args(db_path))
        self.assertEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_CONTROLLED_CONTEXT")

    def test_readiness_reports_controlled_context(self):
        db_path = self.make_db()
        self.seed_intake_and_snapshot(db_path)
        build_collect_context_once_payload(self.context_args(db_path))
        readiness = build_readiness_check_payload(self.readiness_args(db_path))
        self.assertEqual(readiness["db_state_classification"], "PERSISTENT_DB_CONTROLLED_CONTEXT")
        self.assertEqual(readiness["readiness_label"], "READY_CONTROLLED_CONTEXT")

    def test_controlled_context_with_memory_rows_is_not_safe(self):
        db_path = self.make_db()
        snapshot_payload = self.seed_intake_and_snapshot(db_path)
        build_collect_context_once_payload(self.context_args(db_path))
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                INSERT INTO printer_memory_windows (
                    token_id,
                    pair_id,
                    window_kind,
                    opened_at,
                    memory_status,
                    data_quality_label,
                    do_not_train,
                    window_status
                ) VALUES (?, ?, 'WINDOW_15M', 'now', 'DIRTY_MEMORY', 'DIRTY_DATA', 1, 'WINDOW_OPEN')
                """,
                (snapshot_payload["token_id"], snapshot_payload["pair_id"]),
            )
            connection.commit()
        finally:
            connection.close()
        self.assertNotEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_CONTROLLED_CONTEXT")

    def test_no_phase30_or_paper_decision_behavior_exists(self):
        cli_text = (SRC_PATH / "printer_v1" / "operator_cli" / "commands.py").read_text(encoding="utf-8")
        self.assertNotIn("printer-memory-audit", cli_text)
        self.assertNotIn("main_memory_audit", cli_text)
        self.assertNotIn("printer-paper-decision", cli_text)


if __name__ == "__main__":
    unittest.main()

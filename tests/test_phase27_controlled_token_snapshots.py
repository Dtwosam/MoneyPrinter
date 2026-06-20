import argparse
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import (
    CONTROLLED_SNAPSHOT_GUARD_TABLES,
    build_collect_token_snapshots_once_payload,
    build_manual_intake_token_pair_payload,
    build_readiness_check_payload,
)
from printer_v1.operator_db.status import classify_operator_db_state
from printer_v1.sources.dexscreener import build_dexscreener_pair_snapshot_transport


def table_count(connection, table_name):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


class Phase27ControlledTokenSnapshotTests(unittest.TestCase):
    def make_db(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = pathlib.Path(temp_dir.name) / "phase27.sqlite3"
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
            "token_mint": "phase27-mint",
            "pair_address": "phase27-pair",
            "pool_address": None,
            "chain": "solana",
            "intake_reason": "operator approved phase 27 test",
            "source_reference": "manual-phase27-test",
            "source_request_id": None,
            "token_symbol": "P27",
            "token_name": "Phase 27",
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
            "token_mint": "phase27-mint",
            "token_id": None,
            "pair_address": "phase27-pair",
            "pair_id": None,
            "chain": "solana",
            "snapshot_count": 1,
            "max_seconds": 5.0,
            "source_name": "dexscreener",
            "source_reference": "phase27-fixture",
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

    def seed_intake(self, db_path):
        return build_manual_intake_token_pair_payload(self.intake_args(db_path))

    def success_transport(self, context):
        del context
        return {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": "phase27-pair",
                    "baseToken": {
                        "address": "phase27-mint",
                        "symbol": "P27",
                        "name": "Phase 27",
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

    def failure_transport(self, context):
        del context
        return {
            "fixture_status": "failure",
            "failure_type": "phase27_fixture_failure",
            "failure_message": "fixture source failure",
        }

    def test_snapshot_command_exists_in_pyproject(self):
        pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("printer-collect-token-snapshots-once", pyproject)
        self.assertIn("main_collect_token_snapshots_once", pyproject)

    def test_dexscreener_transport_uses_public_api_headers(self):
        captured_requests = []

        def fake_urlopen(request, timeout):
            del timeout
            captured_requests.append(request)
            raise OSError("stop before network")

        transport = build_dexscreener_pair_snapshot_transport("phase27-pair", timeout_seconds=1.0)
        with mock.patch("printer_v1.sources.dexscreener.url_request.urlopen", side_effect=fake_urlopen):
            payload = transport(None)

        self.assertEqual(payload["fixture_status"], "failure")
        request = captured_requests[0]
        self.assertEqual(request.get_header("User-agent"), "PrinterV1/0.1 (+paper-only source check)")
        self.assertEqual(request.get_header("Accept"), "application/json")

    def test_snapshot_command_requires_explicit_operator_approval(self):
        db_path = self.make_db()
        self.seed_intake(db_path)
        with self.assertRaises(ValueError):
            build_collect_token_snapshots_once_payload(
                self.snapshot_args(db_path, operator_approved=False),
                transport=self.success_transport,
            )

    def test_snapshot_command_rejects_non_solana_chain(self):
        db_path = self.make_db()
        self.seed_intake(db_path)
        with self.assertRaises(ValueError):
            build_collect_token_snapshots_once_payload(
                self.snapshot_args(db_path, chain="ethereum"),
                transport=self.success_transport,
            )

    def test_snapshot_command_rejects_unknown_token_or_pair(self):
        db_path = self.make_db()
        self.seed_intake(db_path)
        with self.assertRaises(ValueError):
            build_collect_token_snapshots_once_payload(
                self.snapshot_args(db_path, token_mint="unknown-mint"),
                transport=self.success_transport,
            )
        with self.assertRaises(ValueError):
            build_collect_token_snapshots_once_payload(
                self.snapshot_args(db_path, pair_address="unknown-pair"),
                transport=self.success_transport,
            )

    def test_snapshot_command_rejects_count_above_three(self):
        db_path = self.make_db()
        self.seed_intake(db_path)
        with self.assertRaises(ValueError):
            build_collect_token_snapshots_once_payload(
                self.snapshot_args(db_path, snapshot_count=4),
                transport=self.success_transport,
            )

    def test_snapshot_success_creates_snapshot_and_source_rows_only(self):
        db_path = self.make_db()
        self.seed_intake(db_path)
        payload = build_collect_token_snapshots_once_payload(
            self.snapshot_args(db_path),
            transport=self.success_transport,
        )
        self.assertEqual(payload["token_delta"], 0)
        self.assertEqual(payload["pair_delta"], 0)
        self.assertEqual(payload["source_request_delta"], 1)
        self.assertEqual(payload["source_response_delta"], 1)
        self.assertEqual(payload["source_failure_delta"], 0)
        self.assertEqual(payload["snapshot_delta"], 1)
        self.assertEqual(payload["snapshot_rows_created"], 1)
        self.assertTrue(payload["guard_tables_unchanged"])
        self.assertEqual(payload["db_state_classification"], "PERSISTENT_DB_CONTROLLED_SNAPSHOTS")

        connection = sqlite3.connect(db_path)
        try:
            self.assertEqual(table_count(connection, "printer_tokens"), 1)
            self.assertEqual(table_count(connection, "printer_pairs"), 1)
            self.assertEqual(table_count(connection, "printer_token_snapshots"), 1)
            for table in CONTROLLED_SNAPSHOT_GUARD_TABLES:
                self.assertEqual(table_count(connection, table), 0, table)
        finally:
            connection.close()

    def test_snapshot_failure_records_source_failure_without_fake_snapshot(self):
        db_path = self.make_db()
        self.seed_intake(db_path)
        payload = build_collect_token_snapshots_once_payload(
            self.snapshot_args(db_path),
            transport=self.failure_transport,
        )
        self.assertEqual(payload["source_request_delta"], 1)
        self.assertEqual(payload["source_response_delta"], 0)
        self.assertEqual(payload["source_failure_delta"], 1)
        self.assertEqual(payload["snapshot_delta"], 0)
        self.assertEqual(payload["snapshot_rows_created"], 0)
        self.assertEqual(payload["db_state_classification"], "PERSISTENT_DB_CONTROLLED_INTAKE")

    def test_classifier_reports_intake_and_snapshot_states(self):
        db_path = self.make_db()
        self.seed_intake(db_path)
        self.assertEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_CONTROLLED_INTAKE")
        build_collect_token_snapshots_once_payload(
            self.snapshot_args(db_path),
            transport=self.success_transport,
        )
        self.assertEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_CONTROLLED_SNAPSHOTS")

    def test_readiness_reports_controlled_snapshots(self):
        db_path = self.make_db()
        self.seed_intake(db_path)
        build_collect_token_snapshots_once_payload(
            self.snapshot_args(db_path),
            transport=self.success_transport,
        )
        readiness = build_readiness_check_payload(self.readiness_args(db_path))
        self.assertEqual(readiness["db_state_classification"], "PERSISTENT_DB_CONTROLLED_SNAPSHOTS")
        self.assertEqual(readiness["readiness_label"], "READY_CONTROLLED_SNAPSHOTS")

    def test_controlled_snapshot_with_memory_rows_is_not_safe(self):
        db_path = self.make_db()
        self.seed_intake(db_path)
        payload = build_collect_token_snapshots_once_payload(
            self.snapshot_args(db_path),
            transport=self.success_transport,
        )
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
                (payload["token_id"], payload["pair_id"]),
            )
            connection.commit()
        finally:
            connection.close()
        self.assertNotEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_CONTROLLED_SNAPSHOTS")

    def test_no_phase30_or_later_behavior_exists(self):
        cli_text = (SRC_PATH / "printer_v1" / "operator_cli" / "commands.py").read_text(encoding="utf-8")
        self.assertNotIn("printer-memory-audit", cli_text)
        self.assertNotIn("printer-memory-retrieval", cli_text)
        self.assertNotIn("printer-paper-decision", cli_text)


if __name__ == "__main__":
    unittest.main()

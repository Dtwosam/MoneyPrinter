import argparse
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import (
    MANUAL_INTAKE_GUARD_TABLES,
    build_manual_intake_token_pair_payload,
    build_readiness_check_payload,
)
from printer_v1.operator_db.status import classify_operator_db_state


def table_count(connection, table_name):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


class Phase26ControlledManualIntakeTests(unittest.TestCase):
    def make_db(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = pathlib.Path(temp_dir.name) / "phase26.sqlite3"
        apply_migrations(db_path)
        self.addCleanup(temp_dir.cleanup)
        return db_path

    def args(self, db_path, **overrides):
        values = {
            "db_path": str(db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "token_mint": "phase26-mint",
            "pair_address": "phase26-pair",
            "pool_address": None,
            "chain": "solana",
            "intake_reason": "operator approved phase 26 test",
            "source_reference": "manual-test",
            "source_request_id": None,
            "token_symbol": "P26",
            "token_name": "Phase 26",
            "dex_id": "manual-dex",
            "intake_json": None,
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

    def test_manual_intake_command_exists_in_pyproject(self):
        pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("printer-manual-intake-token-pair", pyproject)
        self.assertIn("main_manual_intake_token_pair", pyproject)

    def test_manual_intake_requires_explicit_operator_approval(self):
        db_path = self.make_db()
        with self.assertRaises(ValueError):
            build_manual_intake_token_pair_payload(self.args(db_path, operator_approved=False))

    def test_manual_intake_rejects_non_solana_chain(self):
        db_path = self.make_db()
        with self.assertRaises(ValueError):
            build_manual_intake_token_pair_payload(self.args(db_path, chain="ethereum"))

    def test_manual_intake_requires_token_mint_pair_and_reason(self):
        db_path = self.make_db()
        for field in ("token_mint", "pair_address", "intake_reason"):
            kwargs = {field: ""}
            if field == "pair_address":
                kwargs["pool_address"] = None
            with self.assertRaises(ValueError, msg=field):
                build_manual_intake_token_pair_payload(self.args(db_path, **kwargs))

    def test_manual_intake_requires_source_reference_or_request_id(self):
        db_path = self.make_db()
        with self.assertRaises(ValueError):
            build_manual_intake_token_pair_payload(
                self.args(db_path, source_reference=None, source_request_id=None)
            )

    def test_manual_intake_limits_items_to_three(self):
        db_path = self.make_db()
        items = [
            {
                "token_mint": f"mint-{index}",
                "pair_address": f"pair-{index}",
                "chain": "solana",
                "intake_reason": "operator approved",
                "source_reference": "manual-test",
            }
            for index in range(4)
        ]
        with self.assertRaises(ValueError):
            build_manual_intake_token_pair_payload(self.args(db_path, intake_json=json.dumps(items)))

    def test_manual_intake_creates_token_pair_rows_only_in_temp_db(self):
        db_path = self.make_db()
        payload = build_manual_intake_token_pair_payload(self.args(db_path))
        self.assertEqual(payload["intake_count"], 1)
        self.assertEqual(payload["token_delta"], 1)
        self.assertEqual(payload["pair_delta"], 1)
        self.assertTrue(payload["guard_tables_unchanged"])
        self.assertEqual(payload["db_state_classification"], "PERSISTENT_DB_CONTROLLED_INTAKE")

        connection = sqlite3.connect(db_path)
        try:
            self.assertEqual(table_count(connection, "printer_tokens"), 1)
            self.assertEqual(table_count(connection, "printer_pairs"), 1)
            for table in MANUAL_INTAKE_GUARD_TABLES:
                self.assertEqual(table_count(connection, table), 0, table)
        finally:
            connection.close()

    def test_manual_intake_is_idempotent_for_duplicate_input(self):
        db_path = self.make_db()
        first = build_manual_intake_token_pair_payload(self.args(db_path))
        second = build_manual_intake_token_pair_payload(self.args(db_path))
        self.assertEqual(first["token_delta"], 1)
        self.assertEqual(first["pair_delta"], 1)
        self.assertEqual(second["token_delta"], 0)
        self.assertEqual(second["pair_delta"], 0)
        self.assertFalse(second["results"][0]["token_created"])
        self.assertFalse(second["results"][0]["pair_created"])

    def test_manual_intake_accepts_three_items(self):
        db_path = self.make_db()
        items = [
            {
                "token_mint": f"mint-{index}",
                "pair_address": f"pair-{index}",
                "chain": "solana",
                "intake_reason": "operator approved",
                "source_reference": "manual-test",
            }
            for index in range(3)
        ]
        payload = build_manual_intake_token_pair_payload(self.args(db_path, intake_json=json.dumps(items)))
        self.assertEqual(payload["intake_count"], 3)
        self.assertEqual(payload["token_delta"], 3)
        self.assertEqual(payload["pair_delta"], 3)
        self.assertEqual(payload["db_state_classification"], "PERSISTENT_DB_CONTROLLED_INTAKE")

    def test_db_classifier_reports_source_only_and_controlled_intake(self):
        db_path = self.make_db()
        self.assertEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_EMPTY_SCHEMA_ONLY")
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                INSERT INTO printer_source_requests (
                    source_name,
                    request_kind,
                    requested_at,
                    source_status,
                    data_quality_label
                ) VALUES ('dexscreener', 'token_discovery', 'now', 'FAILED', 'MISSING_CRITICAL_DATA')
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.assertEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_SOURCE_ONLY_SMOKE_CHECK")
        build_manual_intake_token_pair_payload(self.args(db_path))
        self.assertEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_CONTROLLED_INTAKE")

    def test_readiness_reports_controlled_intake(self):
        db_path = self.make_db()
        build_manual_intake_token_pair_payload(self.args(db_path))
        readiness = build_readiness_check_payload(self.readiness_args(db_path))
        self.assertEqual(readiness["db_state_classification"], "PERSISTENT_DB_CONTROLLED_INTAKE")
        self.assertEqual(readiness["readiness_label"], "READY_CONTROLLED_INTAKE")

    def test_controlled_intake_with_snapshot_memory_or_paper_rows_is_not_safe(self):
        db_path = self.make_db()
        payload = build_manual_intake_token_pair_payload(self.args(db_path))
        token_id = payload["results"][0]["token_id"]
        pair_id = payload["results"][0]["pair_id"]
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                INSERT INTO printer_token_snapshots (
                    token_id,
                    pair_id,
                    captured_at,
                    tracking_lane,
                    snapshot_mode,
                    source_status,
                    data_quality_label
                ) VALUES (?, ?, 'now', 'TRACK_NORMAL', 'MANUAL_TEST', 'COMPLETE', 'CLEAN_DATA')
                """,
                (token_id, pair_id),
            )
            connection.commit()
        finally:
            connection.close()
        self.assertNotEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_CONTROLLED_INTAKE")

    def test_no_automated_discovery_or_phase27_snapshot_command_exists(self):
        cli_text = (SRC_PATH / "printer_v1" / "operator_cli" / "commands.py").read_text(encoding="utf-8")
        self.assertNotIn("printer-auto-discovery-intake", cli_text)
        self.assertNotIn("printer-token-snapshot-collect", cli_text)
        self.assertNotIn("main_snapshot", cli_text)

    def test_manual_intake_does_not_call_live_sources(self):
        source_text = (SRC_PATH / "printer_v1" / "operator_cli" / "commands.py").read_text(encoding="utf-8")
        manual_start = source_text.index("def build_manual_intake_token_pair_payload")
        manual_block = source_text[manual_start:]
        self.assertNotIn("build_dexscreener_smoke_transport(", manual_block)
        self.assertNotIn("execute_source_request_with_governor(", manual_block)


if __name__ == "__main__":
    unittest.main()

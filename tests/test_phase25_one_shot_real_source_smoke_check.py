import argparse
import pathlib
import sqlite3
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import (
    DOWNSTREAM_GUARD_TABLES,
    build_readiness_check_payload,
    build_source_smoke_dexscreener_payload,
)
from printer_v1.operator_db.status import classify_operator_db_state, get_operator_db_status
from printer_v1.sources.contracts import SourceAdapterContext, build_governed_source_request, build_governor_decision
from printer_v1.sources.dexscreener import (
    build_dexscreener_adapter,
    fixture_rate_limited_transport,
    fixture_success_transport,
)
from printer_v1.sources.recording import record_source_request


def table_count(connection, table_name):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def fake_success_payload():
    return {
        "pairs": [
            {
                "chainId": "solana",
                "pairAddress": "phase25-pair",
                "baseToken": {
                    "address": "phase25-mint",
                    "symbol": "P25",
                    "name": "Phase 25",
                },
                "priceUsd": "0.0025",
                "liquidity": {"usd": 25000},
                "volume": {"m5": 25, "h1": 250},
            }
        ]
    }


class Phase25OneShotRealSourceSmokeCheckTests(unittest.TestCase):
    def make_db(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = pathlib.Path(temp_dir.name) / "phase25.sqlite3"
        apply_migrations(db_path)
        self.addCleanup(temp_dir.cleanup)
        return db_path

    def args(self, db_path):
        return argparse.Namespace(
            db_path=str(db_path),
            project_root=None,
            format="json",
            no_color=True,
            timeout_seconds=1.0,
            request_key="phase25-test-smoke",
        )

    def readiness_args(self, db_path):
        return argparse.Namespace(
            db_path=str(db_path),
            project_root=str(PROJECT_ROOT),
            format="json",
            no_color=True,
        )

    def test_smoke_command_exists_in_pyproject(self):
        pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("printer-source-smoke-dexscreener", pyproject)
        self.assertIn("main_source_smoke_dexscreener", pyproject)

    def test_smoke_command_success_records_source_request_and_response_only(self):
        db_path = self.make_db()
        payload = build_source_smoke_dexscreener_payload(
            self.args(db_path),
            transport=fixture_success_transport(fake_success_payload()),
        )
        self.assertTrue(payload["one_shot"])
        self.assertEqual(payload["bounded_request_count"], 1)
        self.assertEqual(payload["source_name"], "dexscreener")
        self.assertEqual(payload["source_status"], SourceStatus.COMPLETE.value)
        self.assertEqual(payload["data_quality_label"], DataQualityLabel.CLEAN_DATA.value)
        self.assertEqual(payload["source_table_deltas"]["printer_source_requests"], 1)
        self.assertEqual(payload["source_table_deltas"]["printer_source_responses"], 1)
        self.assertEqual(payload["source_table_deltas"]["printer_source_failures"], 0)
        self.assertTrue(payload["downstream_unchanged"])
        self.assertEqual(payload["downstream_table_deltas"], {})
        self.assertEqual(payload["db_state_classification"], "PERSISTENT_DB_SOURCE_ONLY_SMOKE_CHECK")

        connection = sqlite3.connect(db_path)
        try:
            for table in DOWNSTREAM_GUARD_TABLES:
                self.assertEqual(table_count(connection, table), 0, table)
        finally:
            connection.close()

    def test_smoke_command_failure_records_source_request_and_failure_only(self):
        db_path = self.make_db()

        def failing_transport(context):
            del context
            return {
                "fixture_status": "failure",
                "failure_type": "phase25_fake_failure",
                "failure_message": "fake source failure",
            }

        payload = build_source_smoke_dexscreener_payload(self.args(db_path), transport=failing_transport)
        self.assertEqual(payload["source_status"], SourceStatus.FAILED.value)
        self.assertEqual(payload["source_table_deltas"]["printer_source_requests"], 1)
        self.assertEqual(payload["source_table_deltas"]["printer_source_responses"], 0)
        self.assertEqual(payload["source_table_deltas"]["printer_source_failures"], 1)
        self.assertEqual(payload["failure_type"], "phase25_fake_failure")
        self.assertTrue(payload["downstream_unchanged"])
        self.assertEqual(payload["db_state_classification"], "PERSISTENT_DB_SOURCE_ONLY_SMOKE_CHECK")

    def test_malformed_live_style_payload_creates_no_downstream_rows(self):
        db_path = self.make_db()

        def malformed_transport(context):
            del context
            return {"pairs": []}

        payload = build_source_smoke_dexscreener_payload(self.args(db_path), transport=malformed_transport)
        self.assertEqual(payload["source_status"], SourceStatus.FAILED.value)
        self.assertEqual(payload["data_quality_label"], DataQualityLabel.MISSING_CRITICAL_DATA.value)
        self.assertEqual(payload["source_table_deltas"]["printer_source_failures"], 1)
        self.assertTrue(payload["downstream_unchanged"])

    def test_rate_limit_style_failure_records_honestly(self):
        db_path = self.make_db()
        payload = build_source_smoke_dexscreener_payload(
            self.args(db_path),
            transport=fixture_rate_limited_transport(),
        )
        self.assertEqual(payload["source_status"], SourceStatus.STALE.value)
        self.assertEqual(payload["data_quality_label"], DataQualityLabel.STALE_DATA.value)
        self.assertEqual(payload["source_table_deltas"]["printer_source_requests"], 1)
        self.assertEqual(payload["source_table_deltas"]["printer_source_responses"], 0)
        self.assertEqual(payload["source_table_deltas"]["printer_source_failures"], 1)
        self.assertEqual(payload["failure_type"], "dexscreener_rate_limited_fixture")

    def test_adapter_still_cannot_bypass_source_governor(self):
        adapter = build_dexscreener_adapter(enabled=True, fixture_transport=fixture_success_transport(fake_success_payload()))
        with self.assertRaises(PermissionError):
            adapter.execute(None)

        db_path = self.make_db()
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        try:
            request = build_governed_source_request("dexscreener", "token_discovery")
            decision = build_governor_decision(request)
            request_record = record_source_request(connection, request, decision)
            context = SourceAdapterContext(
                request=request,
                request_record=request_record,
                decision=decision,
                governor_approved=False,
            )
            with self.assertRaises(PermissionError):
                adapter.execute(context)
        finally:
            connection.close()

    def test_no_phase26_intake_behavior_exists(self):
        source_files = {path.name for path in (SRC_PATH / "printer_v1" / "sources").glob("*.py")}
        self.assertIn("dexscreener.py", source_files)
        self.assertIn("coingecko.py", source_files)
        self.assertIn("defillama.py", source_files)
        cli_text = (SRC_PATH / "printer_v1" / "operator_cli" / "commands.py").read_text(encoding="utf-8")
        self.assertNotIn("printer-controlled-intake", cli_text)
        self.assertNotIn("record_discovery_candidate", cli_text)

    def test_smoke_command_does_not_create_scheduler_or_runtime_rows(self):
        db_path = self.make_db()
        payload = build_source_smoke_dexscreener_payload(
            self.args(db_path),
            transport=fixture_success_transport(fake_success_payload()),
        )
        self.assertEqual(payload["counts_after"]["printer_scheduler_jobs"], 0)
        self.assertFalse(payload["runtime_has_started"])
        self.assertFalse(payload["memory_has_started"])
        self.assertFalse(payload["paper_trading_has_started"])

    def test_schema_only_db_still_reports_schema_only_ready(self):
        db_path = self.make_db()
        self.assertEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_EMPTY_SCHEMA_ONLY")
        readiness = build_readiness_check_payload(self.readiness_args(db_path))
        self.assertEqual(readiness["db_state_classification"], "PERSISTENT_DB_EMPTY_SCHEMA_ONLY")
        self.assertEqual(readiness["readiness_label"], "READY_SCHEMA_ONLY")

    def test_source_only_smoke_db_reports_source_only_ready(self):
        db_path = self.make_db()
        build_source_smoke_dexscreener_payload(
            self.args(db_path),
            transport=fixture_success_transport(fake_success_payload()),
        )
        status = get_operator_db_status(db_path)
        readiness = build_readiness_check_payload(self.readiness_args(db_path))
        self.assertEqual(status["state_classification"], "PERSISTENT_DB_SOURCE_ONLY_SMOKE_CHECK")
        self.assertEqual(readiness["db_state_classification"], "PERSISTENT_DB_SOURCE_ONLY_SMOKE_CHECK")
        self.assertEqual(readiness["readiness_label"], "READY_SOURCE_ONLY_SMOKE_CHECK")

    def test_source_rows_with_token_rows_are_not_source_only_safe(self):
        db_path = self.make_db()
        build_source_smoke_dexscreener_payload(
            self.args(db_path),
            transport=fixture_success_transport(fake_success_payload()),
        )
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                INSERT INTO printer_tokens (
                    token_mint,
                    chain,
                    symbol,
                    name
                ) VALUES (?, 'solana', 'P25', 'Phase 25')
                """,
                ("phase25-real-token",),
            )
            connection.commit()
        finally:
            connection.close()
        self.assertNotEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_SOURCE_ONLY_SMOKE_CHECK")


if __name__ == "__main__":
    unittest.main()

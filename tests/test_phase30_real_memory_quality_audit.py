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
    build_manual_intake_token_pair_payload,
    build_memory_quality_audit_once_payload,
    build_memory_window_once_payload,
    build_readiness_check_payload,
)
from printer_v1.operator_db.status import classify_operator_db_state


def table_count(connection, table_name):
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


class Phase30RealMemoryQualityAuditTests(unittest.TestCase):
    def make_db(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = pathlib.Path(temp_dir.name) / "phase30.sqlite3"
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
            "token_mint": "phase30-mint",
            "pair_address": "phase30-pair",
            "pool_address": None,
            "chain": "solana",
            "intake_reason": "operator approved phase 30 test",
            "source_reference": "manual-phase30-test",
            "source_request_id": None,
            "token_symbol": "P30",
            "token_name": "Phase 30",
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
            "token_mint": "phase30-mint",
            "token_id": None,
            "pair_address": "phase30-pair",
            "pair_id": None,
            "chain": "solana",
            "snapshot_count": 1,
            "max_seconds": 5.0,
            "source_name": "dexscreener",
            "source_reference": "phase30-fixture",
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
            "token_mint": "phase30-mint",
            "token_id": None,
            "pair_address": "phase30-pair",
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
            "token_mint": "phase30-mint",
            "token_id": None,
            "pair_address": "phase30-pair",
            "pair_id": None,
            "snapshot_id": None,
            "chain": "solana",
            "memory_window": "15m",
            "source_reference": "phase30-test",
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
                    "pairAddress": "phase30-pair",
                    "baseToken": {
                        "address": "phase30-mint",
                        "symbol": "P30",
                        "name": "Phase 30",
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

    def seed_through_dirty_memory(self, db_path, add_source_failure=False):
        build_manual_intake_token_pair_payload(self.intake_args(db_path))
        build_collect_token_snapshots_once_payload(self.snapshot_args(db_path), transport=self.success_transport)
        build_collect_context_once_payload(self.context_args(db_path))
        if add_source_failure:
            connection = sqlite3.connect(db_path)
            try:
                connection.execute(
                    """
                    INSERT INTO printer_source_failures (
                        source_name, request_kind, failed_at, failure_type,
                        failure_message, source_status, data_quality_label
                    ) VALUES (
                        'dexscreener', 'PAIR_SNAPSHOT', datetime('now'),
                        'fixture_failure', 'phase 30 source issue fixture',
                        'FAILED', 'MISSING_CRITICAL_DATA'
                    )
                    """
                )
                connection.commit()
            finally:
                connection.close()
        return build_memory_window_once_payload(self.memory_args(db_path))

    def test_memory_audit_command_exists_in_pyproject(self):
        scripts = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertEqual(
            scripts["printer-audit-memory-quality-once"],
            "printer_v1.operator_cli.commands:main_audit_memory_quality_once",
        )

    def test_memory_audit_requires_operator_approval(self):
        db_path = self.make_db()
        self.seed_through_dirty_memory(db_path)
        with self.assertRaises(ValueError):
            build_memory_quality_audit_once_payload(self.audit_args(db_path, operator_approved=False))

    def test_memory_audit_rejects_unknown_memory_or_episode(self):
        db_path = self.make_db()
        self.seed_through_dirty_memory(db_path)
        with self.assertRaises(ValueError):
            build_memory_quality_audit_once_payload(self.audit_args(db_path, memory_window_id=999))
        with self.assertRaises(ValueError):
            build_memory_quality_audit_once_payload(self.audit_args(db_path, memory_window_id=None, episode_id=999))

    def test_memory_audit_rejects_non_solana_chain_for_token_input(self):
        db_path = self.make_db()
        self.seed_through_dirty_memory(db_path)
        with self.assertRaises(ValueError):
            build_memory_quality_audit_once_payload(
                self.audit_args(
                    db_path,
                    memory_window_id=None,
                    token_mint="phase30-mint",
                    pair_address="phase30-pair",
                    chain="ethereum",
                )
            )

    def test_memory_audit_writes_only_audit_report_row(self):
        db_path = self.make_db()
        self.seed_through_dirty_memory(db_path, add_source_failure=True)
        payload = build_memory_quality_audit_once_payload(self.audit_args(db_path))
        report = payload["audit_report"]

        self.assertEqual(payload["memory_audit_report_delta"], 1)
        self.assertEqual(payload["guard_table_deltas"], {})
        self.assertTrue(payload["guard_tables_unchanged"])
        self.assertEqual(payload["db_state_classification"], "PERSISTENT_DB_MEMORY_QUALITY_AUDITED")
        self.assertEqual(report["memory_quality_label"], "DIRTY_MEMORY")
        self.assertFalse(report["clean_memory_eligible"])
        self.assertFalse(report["retrieval_allowed"])
        self.assertFalse(report["paper_decision_allowed"])
        self.assertIn("DIRTY_MEMORY_CONFIRMED", report["audit_verdict"])
        self.assertIn("CLEAN_MEMORY_BLOCKED", report["audit_verdict"])
        self.assertIn("MEMORY_NOT_TRUSTWORTHY_FOR_RETRIEVAL", report["audit_verdict"])
        self.assertIn("RETRIEVAL_NOT_ALLOWED", report["audit_verdict"])
        self.assertIn("PAPER_DECISION_NOT_ALLOWED", report["audit_verdict"])
        self.assertIn("REJECT_MISSING_SNAPSHOTS", report["dirty_reasons"])
        self.assertEqual(report["snapshot_coverage_status"], "INSUFFICIENT_SNAPSHOT_COVERAGE")
        self.assertEqual(report["snapshot_gap_summary"]["snapshot_count"], 1)
        self.assertEqual(report["snapshot_gap_summary"]["expected_min_snapshot_count"], 2)
        self.assertTrue(report["snapshot_gap_summary"]["incomplete_15m_window"])
        self.assertEqual(report["source_quality_summary"]["status"], "SOURCE_ISSUES_VISIBLE")
        self.assertEqual(report["context_quality_summary"]["status"], "MISSING_OR_UNKNOWN_CONTEXT")
        self.assertEqual(report["outcome_quality_summary"]["status"], "OUTCOME_NOT_DETERMINABLE")
        self.assertEqual(report["fingerprint_quality_summary"]["status"], "FINGERPRINT_NOT_RETRIEVAL_READY")
        self.assertFalse(report["fingerprint_quality_summary"]["learned_representation_present"])
        self.assertFalse(report["fingerprint_quality_summary"]["numeric_similarity_artifact_present"])

        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        try:
            self.assertEqual(table_count(connection, "printer_memory_audit_reports"), 1)
            self.assertEqual(table_count(connection, "printer_tokens"), 1)
            self.assertEqual(table_count(connection, "printer_pairs"), 1)
            self.assertEqual(table_count(connection, "printer_token_snapshots"), 1)
            for table in CONTEXT_TABLES:
                self.assertEqual(table_count(connection, table), 1, table)
            for table in MEMORY_OUTPUT_TABLES:
                self.assertEqual(table_count(connection, table), 1, table)
            self.assertEqual(table_count(connection, "printer_memory_retrieval_queries"), 0)
            self.assertEqual(table_count(connection, "printer_memory_retrieval_matches"), 0)
            self.assertEqual(table_count(connection, "printer_paper_decisions"), 0)
            self.assertEqual(table_count(connection, "printer_paper_positions"), 0)
            self.assertEqual(table_count(connection, "printer_scheduler_jobs"), 0)
            window = connection.execute("SELECT * FROM printer_memory_windows WHERE id = 1").fetchone()
            self.assertEqual(window["memory_quality_label"], "DIRTY_MEMORY")
            self.assertEqual(window["do_not_train"], 1)
            fingerprint = connection.execute("SELECT * FROM printer_memory_fingerprints WHERE id = 1").fetchone()
            fingerprint_payload = json.loads(fingerprint["fingerprint_payload_json"])
            self.assertFalse(fingerprint_payload["retrieval_ready"])
        finally:
            connection.close()

    def test_memory_audit_is_idempotent_for_same_window(self):
        db_path = self.make_db()
        self.seed_through_dirty_memory(db_path)
        first = build_memory_quality_audit_once_payload(self.audit_args(db_path))
        second = build_memory_quality_audit_once_payload(self.audit_args(db_path))
        self.assertTrue(first["audit_report_created"])
        self.assertFalse(second["audit_report_created"])
        self.assertEqual(second["memory_audit_report_delta"], 0)

    def test_classifier_and_readiness_report_memory_quality_audited_state(self):
        db_path = self.make_db()
        self.seed_through_dirty_memory(db_path)
        self.assertEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_FIRST_MEMORY_WINDOW")
        build_memory_quality_audit_once_payload(self.audit_args(db_path))
        self.assertEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_MEMORY_QUALITY_AUDITED")
        readiness = build_readiness_check_payload(self.readiness_args(db_path))
        self.assertEqual(readiness["db_state_classification"], "PERSISTENT_DB_MEMORY_QUALITY_AUDITED")
        self.assertEqual(readiness["readiness_label"], "READY_MEMORY_QUALITY_AUDITED")

    def test_memory_quality_audited_state_with_retrieval_or_paper_rows_is_not_safe(self):
        db_path = self.make_db()
        self.seed_through_dirty_memory(db_path)
        build_memory_quality_audit_once_payload(self.audit_args(db_path))
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                INSERT INTO printer_memory_retrieval_queries (
                    query_type, token_id, pair_id, token_mint, pair_address, query_at,
                    current_fingerprint_json, query_context_json, retrieval_result_label,
                    memory_evidence_label, data_quality_label, source_status
                ) VALUES (
                    'AUDIT_MEMORY_REVIEW_QUERY', 1, 1, 'phase30-mint', 'phase30-pair',
                    datetime('now'), '{}', '{}', 'RETRIEVAL_BLOCKED_NO_CLEAN_MEMORY',
                    'MEMORY_EVIDENCE_NOT_ENOUGH', 'MISSING_CRITICAL_DATA', 'PARTIAL'
                )
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.assertNotEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_MEMORY_QUALITY_AUDITED")

    def test_no_phase31_or_phase32_behavior_exists(self):
        cli_text = (SRC_PATH / "printer_v1" / "operator_cli" / "commands.py").read_text(encoding="utf-8")
        self.assertNotIn("printer-memory-retrieval", cli_text)
        self.assertNotIn("printer-paper-decision", cli_text)


if __name__ == "__main__":
    unittest.main()

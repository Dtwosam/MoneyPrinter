import pathlib
import sqlite3
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations


REQUIRED_TABLES = {
    "printer_schema_migrations",
    "printer_tokens",
    "printer_pairs",
    "printer_source_requests",
    "printer_source_responses",
    "printer_source_failures",
    "printer_tracking_queue",
    "printer_scheduler_jobs",
    "printer_token_snapshots",
    "printer_engine_outputs",
    "printer_memory_windows",
    "printer_episodes",
    "printer_episode_snapshots",
    "printer_memory_fingerprints",
    "printer_episode_outcomes",
    "printer_memory_audit_reports",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_decision_audits",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
    "printer_operator_review_reports",
    "printer_operator_review_items",
    "printer_validation_runs",
    "printer_validation_items",
    "printer_run_logs",
    "printer_market_regime_snapshots",
    "printer_solana_chain_heat_snapshots",
    "printer_safety_rug_snapshots",
    "printer_liquidity_exit_snapshots",
    "printer_trading_flow_snapshots",
    "printer_chart_volatility_snapshots",
    "printer_micro_events",
}

KEY_COLUMNS = {
    "printer_tokens": {"id", "token_mint", "chain", "created_at", "updated_at"},
    "printer_pairs": {"id", "token_id", "pair_address", "dex", "pool_source"},
    "printer_source_requests": {
        "id",
        "source_name",
        "request_kind",
        "source_status",
        "data_quality_label",
    },
    "printer_scheduler_jobs": {
        "id",
        "job_name",
        "job_kind",
        "scheduled_for",
        "status",
    },
    "printer_token_snapshots": {
        "id",
        "token_id",
        "pair_id",
        "captured_at",
        "source_status",
        "data_quality_label",
    },
    "printer_memory_windows": {
        "id",
        "token_id",
        "pair_id",
        "memory_status",
        "data_quality_label",
        "do_not_train",
    },
    "printer_paper_decisions": {
        "id",
        "token_id",
        "pair_id",
        "decision_action",
        "source_status",
        "data_quality_label",
    },
    "printer_validation_runs": {
        "id",
        "validation_scope_label",
        "validation_result_label",
        "synthetic_only",
        "temp_db_only",
    },
}

FORBIDDEN_COLUMN_NAMES = {
    "score",
    "confidence",
    "rank",
    "rating",
    "weight",
    "private_key",
    "wallet_address",
    "signed_tx",
    "live_trade",
}


class Phase1DatabaseSchemaTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "printer.sqlite3"
        apply_migrations(self.db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.execute("PRAGMA foreign_keys = ON")

    def tearDown(self):
        self.connection.rollback()
        self.connection.close()
        self.tempdir.cleanup()

    def table_names(self):
        rows = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        return {row[0] for row in rows}

    def column_names(self, table_name):
        rows = self.connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {row[1] for row in rows}

    def test_required_tables_exist(self):
        self.assertTrue(REQUIRED_TABLES.issubset(self.table_names()))

    def test_key_required_columns_exist(self):
        for table_name, expected_columns in KEY_COLUMNS.items():
            self.assertTrue(expected_columns.issubset(self.column_names(table_name)))

    def test_tokens_chain_rejects_non_solana(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO printer_tokens (token_mint, chain)
                VALUES ('mint-eth', 'ethereum')
                """
            )

    def test_paper_decision_action_rejects_invalid_action(self):
        token_id = self.insert_token()
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO printer_paper_decisions (
                    token_id,
                    decision_action,
                    decision_status,
                    source_status,
                    data_quality_label
                )
                VALUES (?, 'MAYBE', 'schema_only', 'COMPLETE', 'CLEAN_DATA')
                """,
                (token_id,),
            )

    def test_source_status_rejects_invalid_value(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO printer_source_requests (
                    source_name,
                    request_kind,
                    requested_at,
                    source_status,
                    data_quality_label
                )
                VALUES ('test_source', 'test', '2026-06-19T00:00:00Z', 'BROKEN', 'CLEAN_DATA')
                """
            )

    def test_data_quality_label_rejects_invalid_value(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO printer_source_requests (
                    source_name,
                    request_kind,
                    requested_at,
                    source_status,
                    data_quality_label
                )
                VALUES ('test_source', 'test', '2026-06-19T00:00:00Z', 'COMPLETE', 'GUESS')
                """
            )

    def test_memory_status_rejects_invalid_value(self):
        token_id = self.insert_token()
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO printer_memory_windows (
                    token_id,
                    window_kind,
                    opened_at,
                    memory_status,
                    data_quality_label
                )
                VALUES (?, '15m', '2026-06-19T00:00:00Z', 'TRAIN_ANYWAY', 'CLEAN_DATA')
                """,
                (token_id,),
            )

    def test_no_forbidden_columns_exist(self):
        for table_name in REQUIRED_TABLES:
            forbidden_found = self.column_names(table_name) & FORBIDDEN_COLUMN_NAMES
            self.assertEqual(forbidden_found, set(), table_name)

    def test_migration_runner_is_idempotent(self):
        apply_migrations(self.db_path)
        rows = self.connection.execute(
            "SELECT version FROM printer_schema_migrations"
        ).fetchall()
        self.assertEqual(
            rows,
            [
                ("001_database_foundation.sql",),
                ("002_source_registry_governor.sql",),
                ("003_scheduler_resource_governor.sql",),
                ("004_token_lifecycle_tracking_queue.sql",),
                ("005_discovery_engine.sql",),
                ("006_token_level_snapshot_system.sql",),
                ("007_market_regime_engine.sql",),
                ("008_solana_chain_heat_engine.sql",),
                ("009_safety_rug_filter_engine.sql",),
                ("010_liquidity_exit_engine.sql",),
                ("011_trading_flow_engine.sql",),
                ("012_chart_volatility_engine.sql",),
                ("013_micro_event_engine.sql",),
                ("014_episode_memory_engine.sql",),
                ("015_memory_retrieval_similarity_engine.sql",),
                ("016_paper_decision_engine.sql",),
                ("017_paper_trade_monitor.sql",),
                ("018_paper_audit_engine.sql",),
                ("019_reporting_operator_review.sql",),
                ("020_hardening_synthetic_validation.sql",),
                ("021_repeatable_evidence_windows.sql",),
            ],
        )

    def insert_token(self):
        cursor = self.connection.execute(
            "INSERT INTO printer_tokens (token_mint) VALUES ('mint-solana-test')"
        )
        return cursor.lastrowid


if __name__ == "__main__":
    unittest.main()

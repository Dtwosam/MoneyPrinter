import pathlib
import sqlite3
import sys
import tempfile
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations


MIGRATION_PATH = PROJECT_ROOT / "migrations" / "022_solana_safety_evidence.sql"
TABLE_NAME = "printer_solana_safety_evidence"

REQUIRED_COLUMNS = {
    "id",
    "token_id",
    "pair_id",
    "snapshot_id",
    "memory_window_id",
    "evidence_window_id",
    "safety_evidence_role",
    "source_name",
    "source_status",
    "data_quality_label",
    "target_status",
    "evidence_captured_at",
    "freshness_label",
    "mint_authority_status",
    "freeze_authority_status",
    "metadata_mutability_status",
    "supply_sanity_label",
    "holder_concentration_label",
    "liquidity_lock_or_burn_label",
    "known_risk_flag_label",
    "token_program_label",
    "safety_context_label",
    "source_request_id",
    "source_response_id",
    "source_failure_id",
    "paper_only_context",
    "created_at",
}

NULLABLE_COLUMNS = {
    "pair_id",
    "memory_window_id",
    "evidence_window_id",
    "source_request_id",
    "source_response_id",
    "source_failure_id",
}

REQUIRED_NOT_NULL_COLUMNS = REQUIRED_COLUMNS - NULLABLE_COLUMNS - {"id"}

INDEXED_COLUMNS = {
    "token_id",
    "pair_id",
    "snapshot_id",
    "memory_window_id",
    "source_request_id",
    "source_response_id",
    "source_failure_id",
    "source_status",
    "data_quality_label",
    "freshness_label",
    "target_status",
    "safety_context_label",
    "created_at",
}

FORBIDDEN_FIELD_FRAGMENTS = (
    "score",
    "rank",
    "confidence",
    "weight",
    "weighted",
    "wallet",
    "private_key",
    "signature",
    "signer",
    "live_execution",
    "buy_unlock",
    "pnl",
    "retrieval_ready",
)


class PostRcSolanaSafetyEvidenceMigrationTest(unittest.TestCase):
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

    def table_info(self, table_name=TABLE_NAME):
        return self.connection.execute(f"PRAGMA table_info({table_name})").fetchall()

    def column_names(self, table_name=TABLE_NAME):
        return {row[1] for row in self.table_info(table_name)}

    def index_columns(self, table_name=TABLE_NAME):
        indexed_columns = set()
        indexes = self.connection.execute(f"PRAGMA index_list({table_name})").fetchall()
        for index in indexes:
            index_name = index[1]
            rows = self.connection.execute(f"PRAGMA index_info({index_name})").fetchall()
            indexed_columns.update(row[2] for row in rows)
        return indexed_columns

    def table_row_count(self, table_name):
        return self.connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

    def test_migration_file_exists(self):
        self.assertTrue(MIGRATION_PATH.exists())

    def test_table_name_and_required_columns_exist(self):
        self.assertIn(TABLE_NAME, self.table_names())
        self.assertTrue(REQUIRED_COLUMNS.issubset(self.column_names()))

    def test_nullable_and_required_columns_match_contract(self):
        info_by_name = {row[1]: row for row in self.table_info()}

        for column in NULLABLE_COLUMNS:
            with self.subTest(column=column):
                self.assertEqual(info_by_name[column][3], 0)

        for column in REQUIRED_NOT_NULL_COLUMNS:
            with self.subTest(column=column):
                self.assertEqual(info_by_name[column][3], 1)

    def test_paper_only_context_exists_is_required_and_guarded(self):
        info_by_name = {row[1]: row for row in self.table_info()}
        self.assertIn("paper_only_context", info_by_name)
        self.assertEqual(info_by_name["paper_only_context"][3], 1)

        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO printer_solana_safety_evidence (
                    token_id,
                    snapshot_id,
                    safety_evidence_role,
                    source_name,
                    source_status,
                    data_quality_label,
                    target_status,
                    evidence_captured_at,
                    freshness_label,
                    mint_authority_status,
                    freeze_authority_status,
                    metadata_mutability_status,
                    supply_sanity_label,
                    holder_concentration_label,
                    liquidity_lock_or_burn_label,
                    known_risk_flag_label,
                    token_program_label,
                    safety_context_label,
                    paper_only_context
                )
                VALUES (
                    1,
                    1,
                    'TOKEN_SAFETY_CONTEXT',
                    'fixture_source',
                    'COMPLETE',
                    'CLEAN_DATA',
                    'TARGET_MATCH',
                    '2026-06-23T00:00:00Z',
                    'SAFETY_EVIDENCE_FRESH',
                    'MINT_AUTHORITY_RENOUNCED',
                    'FREEZE_AUTHORITY_DISABLED',
                    'METADATA_IMMUTABLE',
                    'SUPPLY_SANITY_OK',
                    'HOLDER_CONCENTRATION_HEALTHY',
                    'LIQUIDITY_LOCK_OR_BURN_CONFIRMED',
                    'NO_KNOWN_RISK_FLAGS',
                    'SPL_TOKEN_OR_TOKEN_2022_VERIFIED',
                    'SAFETY_CLEAN',
                    0
                )
                """
            )

    def test_source_governor_trace_linkage_columns_exist(self):
        self.assertTrue(
            {"source_request_id", "source_response_id", "source_failure_id"}.issubset(
                self.column_names()
            )
        )

    def test_key_lookup_indexes_exist(self):
        self.assertTrue(INDEXED_COLUMNS.issubset(self.index_columns()))

    def test_forbidden_fields_are_absent(self):
        lowered_columns = " ".join(self.column_names()).lower()
        for fragment in FORBIDDEN_FIELD_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, lowered_columns)

    def test_migration_creates_no_downstream_rows(self):
        downstream_tables = {
            "printer_memory_windows",
            "printer_memory_retrieval_matches",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
            "printer_paper_pl_calculations",
        }
        for table_name in downstream_tables:
            with self.subTest(table_name=table_name):
                if table_name in self.table_names():
                    self.assertEqual(self.table_row_count(table_name), 0)
                else:
                    self.assertEqual(table_name, "printer_paper_pl_calculations")


if __name__ == "__main__":
    unittest.main()

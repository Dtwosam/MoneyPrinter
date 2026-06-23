import inspect
import pathlib
import sqlite3
import sys
import tempfile
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.paper_quote.evidence import (
    ALLOWED_CALLER,
    PaperQuoteEvidenceInsertResult,
    insert_paper_quote_evidence,
)


MIGRATION_PATH = PROJECT_ROOT / "migrations" / "023_paper_quote_evidence.sql"
TABLE_NAME = "printer_paper_quote_evidence"

REQUIRED_COLUMNS = {
    "id",
    "token_id",
    "pair_id",
    "snapshot_id",
    "memory_window_id",
    "evidence_window_id",
    "quote_evidence_role",
    "quote_direction",
    "quote_purpose",
    "source_name",
    "source_status",
    "data_quality_label",
    "target_status",
    "evidence_captured_at",
    "freshness_label",
    "quote_context_label",
    "entry_realism_label",
    "exit_realism_label",
    "route_available_label",
    "slippage_context_label",
    "price_impact_context_label",
    "liquidity_context_label",
    "quote_failure_label",
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
    "liquidity_context_label",
    "quote_failure_label",
    "source_request_id",
    "source_response_id",
    "source_failure_id",
}

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
    "target_status",
    "freshness_label",
    "entry_realism_label",
    "exit_realism_label",
    "quote_context_label",
    "created_at",
}

FORBIDDEN_FIELD_FRAGMENTS = (
    "score",
    "rank",
    "confidence",
    "weight",
    "weighted",
    "buy_signal",
    "sell_signal",
    "trade_signal",
    "wallet",
    "private_key",
    "signature",
    "signer",
    "live_execution",
    "buy_unlock",
    "pnl",
    "retrieval_ready",
)


def valid_quote_evidence_fixture(**overrides):
    fixture = {
        "token_id": 1,
        "pair_id": 1,
        "snapshot_id": 1,
        "memory_window_id": None,
        "evidence_window_id": None,
        "quote_evidence_role": "ENTRY_QUOTE_CONTEXT",
        "quote_direction": "ENTRY",
        "quote_purpose": "PAPER_REALISM_ONLY",
        "source_name": "fixture_paper_quote_source",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "target_status": "TARGET_MATCH",
        "evidence_captured_at": "2026-06-23T12:00:00+00:00",
        "freshness_label": "QUOTE_FRESH",
        "quote_context_label": "QUOTE_ROUTE_AVAILABLE",
        "entry_realism_label": "ENTRY_REALISTIC",
        "exit_realism_label": "EXIT_UNKNOWN",
        "route_available_label": "ROUTE_AVAILABLE",
        "slippage_context_label": "SLIPPAGE_ACCEPTABLE",
        "price_impact_context_label": "PRICE_IMPACT_ACCEPTABLE",
        "liquidity_context_label": "LIQUIDITY_CONTEXT_ACCEPTABLE",
        "quote_failure_label": None,
        "source_request_id": 1,
        "source_response_id": 1,
        "source_failure_id": None,
        "paper_only_context": True,
    }
    fixture.update(overrides)
    return fixture


class PostRcPaperQuoteEvidenceMigrationAndInsertHelperTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "printer.sqlite3"
        apply_migrations(self.db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.seed_foreign_keys()

    def tearDown(self):
        self.connection.rollback()
        self.connection.close()
        self.tempdir.cleanup()

    def seed_foreign_keys(self):
        self.connection.execute(
            """
            INSERT INTO printer_tokens (
                id, token_mint, chain, symbol, name, token_status
            ) VALUES (1, 'fixture-mint', 'solana', 'FIX', 'Fixture Token', 'TRACKING')
            """
        )
        self.connection.execute(
            """
            INSERT INTO printer_pairs (
                id, token_id, pair_address, dex, pool_source
            ) VALUES (1, 1, 'fixture-pair', 'raydium', 'fixture')
            """
        )
        self.connection.execute(
            """
            INSERT INTO printer_source_requests (
                id,
                source_name,
                request_kind,
                requested_at,
                request_key,
                tracking_priority,
                source_status,
                data_quality_label
            ) VALUES (
                1,
                'fixture_paper_quote_source',
                'PAPER_QUOTE_CONTEXT',
                '2026-06-23T12:00:00+00:00',
                'fixture-mint',
                1,
                'COMPLETE',
                'CLEAN_DATA'
            )
            """
        )
        self.connection.execute(
            """
            INSERT INTO printer_source_responses (
                id,
                source_request_id,
                source_name,
                received_at,
                status_code,
                source_status,
                data_quality_label,
                response_hash,
                normalized_payload_json
            ) VALUES (
                1,
                1,
                'fixture_paper_quote_source',
                '2026-06-23T12:00:00+00:00',
                200,
                'COMPLETE',
                'CLEAN_DATA',
                'fixture-hash',
                '{}'
            )
            """
        )
        self.connection.execute(
            """
            INSERT INTO printer_source_failures (
                id,
                source_name,
                request_kind,
                failed_at,
                failure_type,
                failure_message,
                source_status,
                data_quality_label
            ) VALUES (
                1,
                'fixture_paper_quote_source',
                'PAPER_QUOTE_CONTEXT',
                '2026-06-23T12:00:00+00:00',
                'fixture_failure',
                'fixture failure',
                'FAILED',
                'MISSING_CRITICAL_DATA'
            )
            """
        )
        self.connection.execute(
            """
            INSERT INTO printer_token_snapshots (
                id,
                token_id,
                pair_id,
                captured_at,
                tracking_lane,
                snapshot_mode,
                price_usd,
                liquidity_usd,
                source_status,
                data_quality_label
            ) VALUES (
                1,
                1,
                1,
                '2026-06-23T12:00:00+00:00',
                'TRACK_NORMAL',
                'WINDOW_CLOSE',
                0.001,
                50000,
                'COMPLETE',
                'CLEAN_DATA'
            )
            """
        )
        self.connection.commit()

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

    def insert_fixture(self, **overrides):
        return insert_paper_quote_evidence(
            self.connection,
            valid_quote_evidence_fixture(**overrides),
            scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
            operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
            caller=ALLOWED_CALLER,
        )

    def test_migration_023_applies_to_temporary_db(self):
        self.assertTrue(MIGRATION_PATH.exists())
        self.assertIn(TABLE_NAME, self.table_names())
        self.assertTrue(REQUIRED_COLUMNS.issubset(self.column_names()))

    def test_nullable_and_required_columns_match_contract(self):
        info_by_name = {row[1]: row for row in self.table_info()}

        for column in NULLABLE_COLUMNS:
            with self.subTest(column=column):
                self.assertEqual(info_by_name[column][3], 0)

        for column in REQUIRED_COLUMNS - NULLABLE_COLUMNS - {"id"}:
            with self.subTest(column=column):
                self.assertEqual(info_by_name[column][3], 1)

    def test_forbidden_columns_are_absent_and_indexes_exist(self):
        lowered_columns = " ".join(self.column_names()).lower()
        for fragment in FORBIDDEN_FIELD_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, lowered_columns)

        self.assertTrue(INDEXED_COLUMNS.issubset(self.index_columns()))

    def test_helper_requires_explicit_db_handle_and_has_no_default_path(self):
        parameters = inspect.signature(insert_paper_quote_evidence).parameters

        self.assertIn("db_or_connection", parameters)
        self.assertEqual(parameters["db_or_connection"].default, inspect._empty)

    def test_helper_inserts_valid_fixture_quote_evidence_row(self):
        result = self.insert_fixture()

        self.assertIsInstance(result, PaperQuoteEvidenceInsertResult)
        self.assertTrue(result.inserted)
        self.assertIsNotNone(result.evidence_id)
        self.assertTrue(result.clean_eligible)
        self.assertEqual(set(result.downstream_unlocks.values()), {False})

        row = self.connection.execute(
            "SELECT * FROM printer_paper_quote_evidence WHERE id = ?",
            (result.evidence_id,),
        ).fetchone()
        self.assertEqual(row["entry_realism_label"], "ENTRY_REALISTIC")
        self.assertEqual(row["exit_realism_label"], "EXIT_UNKNOWN")
        self.assertEqual(row["route_available_label"], "ROUTE_AVAILABLE")
        self.assertEqual(row["paper_only_context"], 1)

    def test_helper_rejects_missing_required_ids_and_source_trace(self):
        cases = {
            "token_id": {"token_id": None},
            "snapshot_id": {"snapshot_id": None},
            "source_request_id": {"source_request_id": None},
            "terminal_trace": {"source_response_id": None, "source_failure_id": None},
        }

        for name, overrides in cases.items():
            with self.subTest(name=name):
                result = self.insert_fixture(**overrides)
                self.assertFalse(result.inserted)
                self.assertFalse(result.clean_eligible)
                self.assertTrue(result.rejection_reasons)
        self.assertEqual(self.table_row_count(TABLE_NAME), 0)

    def test_helper_rejects_paper_only_target_and_forbidden_field_failures(self):
        cases = [
            (
                valid_quote_evidence_fixture(paper_only_context=False),
                "PAPER_ONLY_CONTEXT_REQUIRED",
            ),
            (
                valid_quote_evidence_fixture(quote_purpose="LIVE_EXECUTION_QUOTE"),
                "PAPER_REALISM_ONLY_REQUIRED",
            ),
            (
                valid_quote_evidence_fixture(score="forbidden"),
                "FORBIDDEN_FIELDS_PRESENT",
            ),
            (
                valid_quote_evidence_fixture(target_status="TARGET_MISMATCH"),
                "TARGET_MISMATCH",
            ),
        ]

        for evidence, expected_reason in cases:
            with self.subTest(expected_reason=expected_reason):
                result = insert_paper_quote_evidence(
                    self.connection,
                    evidence,
                    scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
                    operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
                    caller=ALLOWED_CALLER,
                )
                self.assertFalse(result.inserted)
                self.assertIn(expected_reason, result.rejection_reasons)

    def test_helper_rejects_scheduler_operator_and_direct_engine_callers(self):
        missing_scheduler = insert_paper_quote_evidence(
            self.connection,
            valid_quote_evidence_fixture(),
            scheduler_boundary_label=None,
            operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
            caller=ALLOWED_CALLER,
        )
        self.assertFalse(missing_scheduler.inserted)
        self.assertIn("SCHEDULER_BOUNDARY_MISSING", missing_scheduler.rejection_reasons)

        missing_operator = insert_paper_quote_evidence(
            self.connection,
            valid_quote_evidence_fixture(),
            scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
            operator_approval_label=None,
            caller=ALLOWED_CALLER,
        )
        self.assertFalse(missing_operator.inserted)
        self.assertIn("OPERATOR_APPROVAL_MISSING", missing_operator.rejection_reasons)

        for caller in (
            "memory_engine",
            "retrieval_engine",
            "paper_decision_engine",
            "paper_position_engine",
            "pnl_engine",
        ):
            with self.subTest(caller=caller):
                result = insert_paper_quote_evidence(
                    self.connection,
                    valid_quote_evidence_fixture(),
                    scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
                    operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
                    caller=caller,
                )
                self.assertFalse(result.inserted)
                self.assertIn("DIRECT_CALLER_FORBIDDEN", result.rejection_reasons)

    def test_stale_failed_and_no_route_quote_evidence_is_audit_only(self):
        cases = [
            {
                "freshness_label": "QUOTE_STALE",
                "quote_context_label": "QUOTE_STALE",
                "quote_failure_label": "QUOTE_STALE_FAILURE",
            },
            {
                "source_status": "FAILED",
                "data_quality_label": "MISSING_CRITICAL_DATA",
                "freshness_label": "QUOTE_FAILED",
                "quote_context_label": "QUOTE_FAILED",
                "quote_failure_label": "QUOTE_SOURCE_FAILED",
                "source_response_id": None,
                "source_failure_id": 1,
            },
            {
                "quote_context_label": "QUOTE_ROUTE_UNAVAILABLE",
                "route_available_label": "ROUTE_UNAVAILABLE",
                "entry_realism_label": "ENTRY_ROUTE_UNAVAILABLE",
                "quote_failure_label": "NO_ROUTE_AVAILABLE",
            },
        ]

        for overrides in cases:
            with self.subTest(overrides=overrides):
                result = self.insert_fixture(**overrides)
                self.assertTrue(result.inserted)
                self.assertFalse(result.clean_eligible)
                self.assertEqual(result.audit_status, "INSERTED_AUDIT_ONLY_EVIDENCE")
                self.assertEqual(set(result.downstream_unlocks.values()), {False})

    def test_helper_rejects_complete_source_with_bad_quality_label(self):
        result = self.insert_fixture(data_quality_label="DIRTY_DATA")

        self.assertFalse(result.inserted)
        self.assertFalse(result.clean_eligible)
        self.assertIn("DATA_QUALITY_NOT_INSERTABLE", result.rejection_reasons)

    def test_inserted_quote_evidence_creates_no_downstream_rows(self):
        result = self.insert_fixture()

        self.assertTrue(result.inserted)
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

    def test_persistent_operator_db_remains_untouched_by_helper_tests(self):
        persistent_db = PROJECT_ROOT / "data" / "printer_v1.sqlite3"
        before_mtime = persistent_db.stat().st_mtime_ns if persistent_db.exists() else None

        result = self.insert_fixture()

        after_mtime = persistent_db.stat().st_mtime_ns if persistent_db.exists() else None
        self.assertTrue(result.inserted)
        self.assertEqual(before_mtime, after_mtime)


if __name__ == "__main__":
    unittest.main()

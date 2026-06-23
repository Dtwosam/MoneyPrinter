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
from printer_v1.safety.evidence import (
    ALLOWED_CALLER,
    SolanaSafetyEvidenceInsertResult,
    insert_solana_safety_evidence,
)


def valid_evidence_fixture(**overrides):
    fixture = {
        "token_id": 1,
        "pair_id": 1,
        "snapshot_id": 1,
        "memory_window_id": None,
        "evidence_window_id": None,
        "safety_evidence_role": "TOKEN_SAFETY_CONTEXT",
        "source_name": "fixture_safety_source",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "target_status": "TARGET_MATCH",
        "evidence_captured_at": "2026-06-23T12:00:00+00:00",
        "freshness_label": "SAFETY_EVIDENCE_FRESH",
        "mint_authority_status": "MINT_AUTHORITY_RENOUNCED",
        "freeze_authority_status": "FREEZE_AUTHORITY_DISABLED",
        "metadata_mutability_status": "METADATA_IMMUTABLE",
        "supply_sanity_label": "SUPPLY_SANITY_OK",
        "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
        "liquidity_lock_or_burn_label": "LIQUIDITY_LOCK_OR_BURN_CONFIRMED",
        "known_risk_flag_label": "NO_KNOWN_RISK_FLAGS",
        "token_program_label": "SPL_TOKEN_OR_TOKEN_2022_VERIFIED",
        "safety_context_label": "SAFETY_CLEAR",
        "source_request_id": 1,
        "source_response_id": 1,
        "source_failure_id": None,
        "paper_only_context": True,
    }
    fixture.update(overrides)
    return fixture


class PostRcSolanaSafetyEvidenceIsolatedDbInsertHelperTest(unittest.TestCase):
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
                'fixture_safety_source',
                'TOKEN_SAFETY_CONTEXT',
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
                'fixture_safety_source',
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
                'fixture_safety_source',
                'TOKEN_SAFETY_CONTEXT',
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

    def table_row_count(self, table_name):
        return self.connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

    def insert_fixture(self, **overrides):
        return insert_solana_safety_evidence(
            self.connection,
            valid_evidence_fixture(**overrides),
            scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
            operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
            caller=ALLOWED_CALLER,
        )

    def test_migration_022_applies_to_temporary_db(self):
        row = self.connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'printer_solana_safety_evidence'
            """
        ).fetchone()

        self.assertIsNotNone(row)

    def test_helper_requires_explicit_db_handle_and_has_no_default_path(self):
        parameters = inspect.signature(insert_solana_safety_evidence).parameters

        self.assertIn("db_or_connection", parameters)
        self.assertEqual(parameters["db_or_connection"].default, inspect._empty)

    def test_helper_inserts_valid_safety_clear_fixture_row(self):
        result = self.insert_fixture()

        self.assertIsInstance(result, SolanaSafetyEvidenceInsertResult)
        self.assertTrue(result.inserted)
        self.assertIsNotNone(result.evidence_id)
        self.assertTrue(result.clean_eligible)
        self.assertEqual(set(result.downstream_unlocks.values()), {False})

        row = self.connection.execute(
            "SELECT * FROM printer_solana_safety_evidence WHERE id = ?",
            (result.evidence_id,),
        ).fetchone()
        self.assertEqual(row["safety_context_label"], "SAFETY_CLEAN")
        self.assertEqual(row["source_status"], "COMPLETE")
        self.assertEqual(row["data_quality_label"], "CLEAN_DATA")
        self.assertEqual(row["target_status"], "TARGET_MATCH")
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
        self.assertEqual(self.table_row_count("printer_solana_safety_evidence"), 0)

    def test_helper_rejects_paper_only_scheduler_operator_and_forbidden_field_failures(self):
        cases = [
            (
                valid_evidence_fixture(paper_only_context=False),
                "SCHEDULER_BOUNDARY_PRESENT",
                "OPERATOR_APPROVED_MANUAL_PROOF",
                ALLOWED_CALLER,
                "PAPER_ONLY_CONTEXT_REQUIRED",
            ),
            (
                valid_evidence_fixture(),
                None,
                "OPERATOR_APPROVED_MANUAL_PROOF",
                ALLOWED_CALLER,
                "SCHEDULER_BOUNDARY_MISSING",
            ),
            (
                valid_evidence_fixture(),
                "SCHEDULER_BOUNDARY_PRESENT",
                None,
                ALLOWED_CALLER,
                "OPERATOR_APPROVAL_MISSING",
            ),
            (
                valid_evidence_fixture(score="forbidden"),
                "SCHEDULER_BOUNDARY_PRESENT",
                "OPERATOR_APPROVED_MANUAL_PROOF",
                ALLOWED_CALLER,
                "FORBIDDEN_FIELDS_PRESENT",
            ),
        ]

        for evidence, scheduler_label, operator_label, caller, expected_reason in cases:
            with self.subTest(expected_reason=expected_reason):
                result = insert_solana_safety_evidence(
                    self.connection,
                    evidence,
                    scheduler_boundary_label=scheduler_label,
                    operator_approval_label=operator_label,
                    caller=caller,
                )
                self.assertFalse(result.inserted)
                self.assertIn(expected_reason, result.rejection_reasons)

    def test_helper_rejects_target_mismatch_and_direct_engine_callers(self):
        mismatch = self.insert_fixture(target_status="TARGET_MISMATCH")
        self.assertFalse(mismatch.inserted)
        self.assertIn("TARGET_MISMATCH", mismatch.rejection_reasons)

        for caller in (
            "memory_engine",
            "retrieval_engine",
            "paper_decision_engine",
            "paper_position_engine",
            "pnl_engine",
        ):
            with self.subTest(caller=caller):
                result = insert_solana_safety_evidence(
                    self.connection,
                    valid_evidence_fixture(),
                    scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
                    operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
                    caller=caller,
                )
                self.assertFalse(result.inserted)
                self.assertIn("DIRECT_CALLER_FORBIDDEN", result.rejection_reasons)

    def test_helper_inserts_stale_failed_caution_blocked_unknown_as_not_clean(self):
        cases = [
            (
                {
                    "freshness_label": "SAFETY_EVIDENCE_STALE",
                },
                "INSERTED_AUDIT_ONLY_EVIDENCE",
            ),
            (
                {
                    "source_status": "FAILED",
                    "data_quality_label": "MISSING_CRITICAL_DATA",
                    "source_response_id": None,
                    "source_failure_id": 1,
                },
                "INSERTED_AUDIT_ONLY_EVIDENCE",
            ),
            (
                {
                    "safety_context_label": "SAFETY_CAUTION",
                },
                "INSERTED_AUDIT_ONLY_EVIDENCE",
            ),
            (
                {
                    "safety_context_label": "SAFETY_BLOCKED",
                },
                "INSERTED_AUDIT_ONLY_EVIDENCE",
            ),
            (
                {
                    "safety_context_label": "SAFETY_UNKNOWN",
                },
                "INSERTED_AUDIT_ONLY_EVIDENCE",
            ),
        ]

        for overrides, expected_status in cases:
            with self.subTest(overrides=overrides):
                result = self.insert_fixture(**overrides)
                self.assertTrue(result.inserted)
                self.assertFalse(result.clean_eligible)
                self.assertEqual(result.audit_status, expected_status)
                self.assertEqual(set(result.downstream_unlocks.values()), {False})

    def test_helper_rejects_complete_source_with_bad_quality_label(self):
        result = self.insert_fixture(data_quality_label="DIRTY_DATA")

        self.assertFalse(result.inserted)
        self.assertFalse(result.clean_eligible)
        self.assertIn("DATA_QUALITY_NOT_INSERTABLE", result.rejection_reasons)

    def test_inserted_evidence_creates_no_downstream_rows(self):
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

    def table_names(self):
        rows = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        return {row[0] for row in rows}

    def test_persistent_operator_db_remains_untouched_by_helper_tests(self):
        persistent_db = PROJECT_ROOT / "data" / "printer_v1.sqlite3"
        before_mtime = persistent_db.stat().st_mtime_ns if persistent_db.exists() else None

        result = self.insert_fixture()

        after_mtime = persistent_db.stat().st_mtime_ns if persistent_db.exists() else None
        self.assertTrue(result.inserted)
        self.assertEqual(before_mtime, after_mtime)


if __name__ == "__main__":
    unittest.main()

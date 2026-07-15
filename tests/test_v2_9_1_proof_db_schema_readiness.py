"""V2-9.1 proof-DB schema readiness repair tests (temporary DBs only)."""

from __future__ import annotations

from contextlib import closing, redirect_stdout
import hashlib
import io
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.db import migrate as migration_runner
from printer_v1.operator_cli.one_command_15m_factory import _require_schema
from printer_v1.operator_cli.proof_db_schema_readiness import (
    CANONICAL_PERSISTENT_DB,
    CRITICAL_DATA_TABLES,
    ProofDbReadinessError,
    critical_counts,
    main_prepare_proof_db,
    prepare_proof_db,
    validate_runtime_schema,
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _apply_through(db_path: Path, maximum_prefix: int) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS printer_schema_migrations (
                   version TEXT PRIMARY KEY,
                   applied_at TEXT NOT NULL DEFAULT (datetime('now'))
               )"""
        )
        applied = {
            str(row[0]) for row in connection.execute(
                "SELECT version FROM printer_schema_migrations"
            ).fetchall()
        }
        for migration_file in sorted(migration_runner.MIGRATIONS_DIR.glob("*.sql")):
            prefix = int(migration_file.name.split("_", 1)[0])
            if prefix > maximum_prefix or migration_file.name in applied:
                continue
            connection.executescript(migration_file.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO printer_schema_migrations(version) VALUES (?)",
                (migration_file.name,),
            )
        connection.commit()
    finally:
        connection.close()


class ProofDbSchemaReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.persistent = self.root / "persistent-old.sqlite3"
        self.proof = self.root / "proof.sqlite3"
        self.backup = self.root / "proof.backup.sqlite3"
        _apply_through(self.persistent, 24)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_old_schema_copy_is_migrated_validated_and_backed_up(self) -> None:
        persistent_hash = _hash(self.persistent)
        persistent_counts = critical_counts(self.persistent)

        report = prepare_proof_db(self.persistent, self.proof, self.backup)

        self.assertEqual(report["status"], "PROOF_DB_SCHEMA_READY")
        self.assertTrue(report["proof_validation"]["runtime_ready"])
        self.assertTrue(report["backup_validation"]["runtime_ready"])
        self.assertTrue(report["proof_backup_byte_identical"])
        self.assertEqual(self.proof.read_bytes(), self.backup.read_bytes())
        self.assertEqual(_hash(self.persistent), persistent_hash)
        self.assertEqual(critical_counts(self.persistent), persistent_counts)
        self.assertEqual(critical_counts(self.proof), persistent_counts)
        self.assertFalse(report["sources_run"])
        self.assertFalse(report["scheduler_runtime_run"])

        with closing(sqlite3.connect(self.proof)) as connection:
            tables = {
                str(row[0]) for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            self.assertIn("printer_memory_factory_runs", tables)
            self.assertIn("printer_memory_factory_run_steps", tables)
            versions = {
                str(row[0]) for row in connection.execute(
                    "SELECT version FROM printer_schema_migrations"
                ).fetchall()
            }
            self.assertIn("028_memory_factory_run_ledger.sql", versions)
            self.assertIn("029_composite_safety_evidence.sql", versions)
            _require_schema(connection)

        counts = critical_counts(self.proof)
        for table in CRITICAL_DATA_TABLES:
            self.assertEqual(counts[table], 0, table)

    def test_canonical_migration_application_is_idempotent(self) -> None:
        prepare_proof_db(self.persistent, self.proof, self.backup)
        counts_before = critical_counts(self.proof)
        with closing(sqlite3.connect(self.proof)) as connection:
            versions_before = int(connection.execute(
                "SELECT COUNT(*) FROM printer_schema_migrations"
            ).fetchone()[0])

        migration_runner.apply_migrations(self.proof)
        migration_runner.apply_migrations(self.proof)

        self.assertTrue(validate_runtime_schema(self.proof)["runtime_ready"])
        self.assertEqual(critical_counts(self.proof), counts_before)
        with closing(sqlite3.connect(self.proof)) as connection:
            versions_after = int(connection.execute(
                "SELECT COUNT(*) FROM printer_schema_migrations"
            ).fetchone()[0])
        self.assertEqual(versions_after, versions_before)

    def test_cli_requires_operator_approval_before_copy(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main_prepare_proof_db([
                "--persistent-db-path", str(self.persistent),
                "--proof-db-path", str(self.proof),
                "--backup-proof-path", str(self.backup),
            ])
        self.assertEqual(code, 1)
        self.assertIn("operator approval required", output.getvalue())
        self.assertFalse(self.proof.exists())
        self.assertFalse(self.backup.exists())

    def test_rejects_canonical_persistent_db_as_proof_target(self) -> None:
        with self.assertRaisesRegex(
            ProofDbReadinessError, "canonical persistent DB is forbidden"
        ):
            prepare_proof_db(
                self.persistent, CANONICAL_PERSISTENT_DB, self.backup
            )
        self.assertFalse(self.backup.exists())

    def test_rejects_non_fresh_or_overlapping_paths(self) -> None:
        self.proof.write_bytes(b"occupied")
        with self.assertRaisesRegex(ProofDbReadinessError, "must be fresh"):
            prepare_proof_db(self.persistent, self.proof, self.backup)
        self.assertFalse(self.backup.exists())

        second = self.root / "second.sqlite3"
        with self.assertRaisesRegex(ProofDbReadinessError, "must be distinct"):
            prepare_proof_db(self.persistent, second, self.persistent)

    def test_missing_canonical_run_ledger_migration_blocks_before_copy(self) -> None:
        incomplete_dir = self.root / "incomplete-migrations"
        incomplete_dir.mkdir()
        shutil.copy2(
            migration_runner.MIGRATIONS_DIR / "001_database_foundation.sql",
            incomplete_dir / "001_database_foundation.sql",
        )
        with patch.object(migration_runner, "MIGRATIONS_DIR", incomplete_dir):
            with self.assertRaisesRegex(
                ProofDbReadinessError, "required canonical migration missing"
            ):
                prepare_proof_db(self.persistent, self.proof, self.backup)
        self.assertFalse(self.proof.exists())
        self.assertFalse(self.backup.exists())

    def test_failed_migration_leaves_no_backup_and_no_runtime_rows(self) -> None:
        persistent_hash = _hash(self.persistent)
        with patch.object(
            migration_runner, "apply_migrations",
            side_effect=sqlite3.OperationalError("fixture migration failure"),
        ):
            with self.assertRaises(sqlite3.OperationalError):
                prepare_proof_db(self.persistent, self.proof, self.backup)

        self.assertTrue(self.proof.exists())
        self.assertFalse(self.backup.exists())
        self.assertEqual(_hash(self.persistent), persistent_hash)
        counts = critical_counts(self.proof)
        self.assertEqual(counts["printer_source_requests"], 0)
        self.assertEqual(counts["printer_scheduler_jobs"], 0)
        self.assertEqual(counts["printer_memory_factory_runs"], 0)

    def test_incomplete_migration_blocks_runtime_and_backup(self) -> None:
        def incomplete_apply(path: str | Path) -> None:
            _apply_through(Path(path), 28)

        with patch.object(migration_runner, "apply_migrations", incomplete_apply):
            with self.assertRaisesRegex(
                ProofDbReadinessError, "missing canonical migrations"
            ):
                prepare_proof_db(self.persistent, self.proof, self.backup)

        self.assertTrue(self.proof.exists())
        self.assertFalse(self.backup.exists())
        with closing(sqlite3.connect(self.proof)) as connection:
            with self.assertRaisesRegex(
                ProofDbReadinessError, "missing canonical migrations"
            ):
                _require_schema(connection)
        counts = critical_counts(self.proof)
        self.assertEqual(counts["printer_source_requests"], 0)
        self.assertEqual(counts["printer_scheduler_jobs"], 0)
        self.assertEqual(counts["printer_memory_factory_runs"], 0)

    def test_missing_runtime_index_fails_closed(self) -> None:
        migration_runner.apply_migrations(self.proof)
        with closing(sqlite3.connect(self.proof)) as connection:
            connection.execute("DROP INDEX idx_memory_factory_steps_job")
            connection.commit()
            with self.assertRaisesRegex(
                ProofDbReadinessError, "missing index"
            ):
                _require_schema(connection)

    def test_no_retrieval_or_financial_rows_are_created(self) -> None:
        prepare_proof_db(self.persistent, self.proof, self.backup)
        counts = critical_counts(self.proof)
        locked = (
            "printer_memory_retrieval_queries",
            "printer_memory_retrieval_matches",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
            "printer_paper_trade_audits",
            "printer_paper_audit_reports",
        )
        self.assertTrue(all(counts[table] == 0 for table in locked))


if __name__ == "__main__":
    unittest.main()

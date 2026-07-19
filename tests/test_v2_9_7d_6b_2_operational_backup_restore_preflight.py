"""Focused V2-9.7D.6B.2 backup/restore tests; disposable DBs only."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.db import migrate as migration_runner
from printer_v1.operator_cli.operational_backup_restore_preflight import (
    MIGRATION_032,
    OperationalBackupPreflightError,
    operational_backup_restore_preflight,
    source_identity,
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
        for path in sorted(migration_runner.MIGRATIONS_DIR.glob("*.sql")):
            if int(path.name.split("_", 1)[0]) > maximum_prefix:
                continue
            if path.name not in applied:
                connection.executescript(path.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO printer_schema_migrations(version) VALUES (?)",
                    (path.name,),
                )
        connection.commit()
    finally:
        connection.close()


class OperationalBackupRestorePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        temp_parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=temp_parent)
        self.root = Path(self.temp.name)
        self.source = self.root / "persistent-fixture.sqlite3"
        self.backup_root = self.root / "backups"
        self.restore_root = self.root / "disposable-restores"
        self.backup_root.mkdir()
        self.restore_root.mkdir()
        _apply_through(self.source, 31)
        connection = sqlite3.connect(self.source)
        try:
            connection.execute(
                "INSERT INTO printer_tokens(id,token_mint,symbol) VALUES (1,'mint-a','AAA')"
            )
            connection.execute(
                "INSERT INTO printer_pairs(id,token_id,pair_address) VALUES (1,1,'pair-a')"
            )
            connection.commit()
        finally:
            connection.close()
        self.identity = source_identity(self.source)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _run(self, suffix: str = "a") -> dict[str, object]:
        return operational_backup_restore_preflight(
            self.source,
            expected_source_path=self.source,
            expected_source_identity=self.identity,
            backup_path=self.backup_root / f"verified-{suffix}.sqlite3",
            disposable_restore_root=self.restore_root,
            restore_path=self.restore_root / f"restore-{suffix}.sqlite3",
        )

    def test_captures_identity_metadata_and_rehearses_migration_032(self) -> None:
        source_bytes = self.source.read_bytes()
        source_hash = _hash(self.source)
        report = self._run()

        backup = self.backup_root / "verified-a.sqlite3"
        restore = self.restore_root / "restore-a.sqlite3"
        self.assertEqual(report["status"], "OPERATIONAL_BACKUP_RESTORE_PREFLIGHT_READY")
        self.assertEqual(report["source_identity"], self.identity)
        self.assertTrue(report["exclusive_writer_verified"])
        self.assertTrue(report["backup_byte_identical"])
        self.assertEqual(report["backup_hash"], source_hash)
        self.assertEqual(report["backup_size"], len(source_bytes))
        self.assertEqual(backup.read_bytes(), source_bytes)
        self.assertEqual(self.source.read_bytes(), source_bytes)
        self.assertEqual(_hash(self.source), source_hash)
        self.assertEqual(report["source_hash_before"], report["source_hash_after"])
        self.assertEqual(report["latest_rehearsed_migration"], MIGRATION_032)
        self.assertEqual(report["restore_metadata"]["latest_migration"], MIGRATION_032)
        self.assertEqual(report["restore_metadata"]["integrity_check"], ["ok"])
        self.assertEqual(report["restore_metadata"]["foreign_key_error_count"], 0)
        self.assertTrue(report["restore_validation"]["runtime_ready"])
        self.assertEqual(
            report["source_metadata"]["critical_row_counts"],
            report["restore_metadata"]["critical_row_counts"],
        )
        connection = sqlite3.connect(restore)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT symbol FROM printer_tokens WHERE id=1"
                ).fetchone()[0],
                "AAA",
            )
        finally:
            connection.close()
        self.assertFalse(report["sources_run"])
        self.assertFalse(report["scheduler_runtime_run"])
        self.assertEqual(report["source_writes"], 0)

    def test_wrong_path_or_content_identity_blocks_before_artifacts(self) -> None:
        with self.assertRaisesRegex(
            OperationalBackupPreflightError, "target path mismatch"
        ):
            operational_backup_restore_preflight(
                self.source,
                expected_source_path=self.root / "other.sqlite3",
                expected_source_identity=self.identity,
                backup_path=self.backup_root / "wrong-path.sqlite3",
                disposable_restore_root=self.restore_root,
                restore_path=self.restore_root / "wrong-path.sqlite3",
            )
        with self.assertRaisesRegex(
            OperationalBackupPreflightError, "target identity mismatch"
        ):
            operational_backup_restore_preflight(
                self.source,
                expected_source_path=self.source,
                expected_source_identity=f"sha256:{'0' * 64}",
                backup_path=self.backup_root / "wrong-id.sqlite3",
                disposable_restore_root=self.restore_root,
                restore_path=self.restore_root / "wrong-id.sqlite3",
            )
        self.assertEqual(list(self.backup_root.iterdir()), [])
        self.assertEqual(list(self.restore_root.iterdir()), [])

    def test_active_writer_and_wal_sidecar_fail_closed(self) -> None:
        writer = sqlite3.connect(self.source, timeout=0.0)
        try:
            writer.execute("BEGIN IMMEDIATE")
            with self.assertRaisesRegex(
                OperationalBackupPreflightError, "exclusive writer check failed"
            ):
                self._run("writer")
        finally:
            writer.rollback()
            writer.close()
        self.assertFalse((self.backup_root / "verified-writer.sqlite3").exists())

        wal = Path(f"{self.source}-wal")
        wal.write_bytes(b"uncheckpointed")
        try:
            with self.assertRaisesRegex(
                OperationalBackupPreflightError, "not quiescent"
            ):
                self._run("wal")
        finally:
            wal.unlink()
        self.assertFalse((self.backup_root / "verified-wal.sqlite3").exists())

    def test_interrupted_copy_publishes_nothing_and_preserves_last_backup(self) -> None:
        first = self._run("first")
        last_backup = self.backup_root / "verified-first.sqlite3"
        last_bytes = last_backup.read_bytes()

        def interrupted(source: Path, target: Path) -> None:
            target.write_bytes(source.read_bytes()[:32])
            raise OSError("fixture interrupted copy")

        with patch(
            "printer_v1.operator_cli.operational_backup_restore_preflight._copy_bytes",
            side_effect=interrupted,
        ):
            with self.assertRaisesRegex(OSError, "interrupted copy"):
                self._run("failed")
        self.assertEqual(first["backup_hash"], _hash(last_backup))
        self.assertEqual(last_backup.read_bytes(), last_bytes)
        self.assertFalse((self.backup_root / "verified-failed.sqlite3").exists())
        self.assertFalse((self.restore_root / "restore-failed.sqlite3").exists())
        self.assertEqual(list(self.backup_root.glob(".*.tmp")), [])

    def test_hash_mismatch_and_existing_targets_block_without_overwrite(self) -> None:
        def corrupt_copy(source: Path, target: Path) -> None:
            shutil.copyfile(source, target)
            target.write_bytes(target.read_bytes() + b"corrupt")

        with patch(
            "printer_v1.operator_cli.operational_backup_restore_preflight._copy_bytes",
            side_effect=corrupt_copy,
        ):
            with self.assertRaisesRegex(
                OperationalBackupPreflightError, "size/hash mismatch"
            ):
                self._run("corrupt")
        self.assertFalse((self.backup_root / "verified-corrupt.sqlite3").exists())

        occupied_backup = self.backup_root / "verified-occupied.sqlite3"
        occupied_backup.write_bytes(b"last verified")
        with self.assertRaisesRegex(
            OperationalBackupPreflightError, "already exists"
        ):
            self._run("occupied")
        self.assertEqual(occupied_backup.read_bytes(), b"last verified")

        occupied_restore = self.restore_root / "restore-restore-occupied.sqlite3"
        occupied_restore.write_bytes(b"occupied restore")
        with self.assertRaisesRegex(
            OperationalBackupPreflightError, "restore target already exists"
        ):
            operational_backup_restore_preflight(
                self.source,
                expected_source_path=self.source,
                expected_source_identity=self.identity,
                backup_path=self.backup_root / "restore-occupied.sqlite3",
                disposable_restore_root=self.restore_root,
                restore_path=occupied_restore,
            )
        self.assertEqual(occupied_restore.read_bytes(), b"occupied restore")

    def test_repeated_preflight_is_deterministic_and_never_reuses_artifacts(self) -> None:
        first = self._run("one")
        second = self._run("two")
        for key in (
            "source_identity", "source_size_before", "source_hash_before",
            "source_metadata", "backup_hash", "backup_size",
            "restore_metadata", "latest_rehearsed_migration",
        ):
            self.assertEqual(first[key], second[key], key)
        with self.assertRaisesRegex(
            OperationalBackupPreflightError, "already exists"
        ):
            self._run("one")
        self.assertEqual(
            (self.backup_root / "verified-one.sqlite3").read_bytes(),
            self.source.read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()

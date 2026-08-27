from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.operator_cli import operational_backup_restore_preflight as backup_preflight


_METADATA = {
    "migration_ledger": [backup_preflight.MIGRATION_032],
    "latest_migration": backup_preflight.MIGRATION_032,
    "critical_row_counts": {},
    "integrity_check": ["ok"],
    "foreign_key_errors": [],
    "foreign_key_error_count": 0,
}


class BackupDirectoryDurabilityTests(unittest.TestCase):
    def _paths(self, root: Path) -> tuple[Path, Path, Path]:
        source = root / "source.sqlite3"
        connection = sqlite3.connect(source)
        connection.execute("CREATE TABLE fixture(value INTEGER)")
        connection.commit()
        connection.close()
        return source, root / "backup.sqlite3", root / "restore.sqlite3"

    def _patches(self):
        return (
            patch.object(
                backup_preflight,
                "_inspect_connection",
                return_value=dict(_METADATA),
            ),
            patch.object(
                backup_preflight,
                "_inspect_read_only",
                return_value=dict(_METADATA),
            ),
            patch.object(backup_preflight.migration_runner, "apply_migrations"),
            patch.object(
                backup_preflight,
                "validate_runtime_schema",
                return_value={"status": "fixture"},
            ),
        )

    def test_verified_backup_publication_syncs_parent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, backup, restore = self._paths(root)
            sync_calls = []

            first, second, third, fourth = self._patches()
            with first, second, third, fourth:
                result = backup_preflight.operational_backup_restore_preflight(
                    source,
                    expected_source_path=source,
                    expected_source_identity=backup_preflight.source_identity(source),
                    backup_path=backup,
                    disposable_restore_root=root,
                    restore_path=restore,
                    directory_sync=lambda path: sync_calls.append(Path(path)),
                )

            self.assertTrue(result["backup_byte_identical"])
            self.assertEqual(sync_calls, [root.resolve()])

    def test_durability_failure_blocks_after_create_once_publication(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, backup, restore = self._paths(root)

            def fail_sync(_path):
                raise OSError("injected directory fsync failure")

            first, second, third, fourth = self._patches()
            with first, second, third, fourth:
                with self.assertRaises(
                    backup_preflight.OperationalBackupPreflightError
                ):
                    backup_preflight.operational_backup_restore_preflight(
                        source,
                        expected_source_path=source,
                        expected_source_identity=(
                            backup_preflight.source_identity(source)
                        ),
                        backup_path=backup,
                        disposable_restore_root=root,
                        restore_path=restore,
                        directory_sync=fail_sync,
                    )

            self.assertTrue(backup.exists())


if __name__ == "__main__":
    unittest.main()

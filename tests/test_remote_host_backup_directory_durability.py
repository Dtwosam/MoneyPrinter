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
    def test_verified_backup_publication_syncs_parent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.sqlite3"
            connection = sqlite3.connect(source)
            connection.execute("CREATE TABLE fixture(value INTEGER)")
            connection.commit()
            connection.close()
            backup = root / "backup.sqlite3"
            restore = root / "restore.sqlite3"
            sync_calls = []

            with (
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
            ):
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


if __name__ == "__main__":
    unittest.main()

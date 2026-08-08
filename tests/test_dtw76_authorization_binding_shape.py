from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from printer_v1.operator_cli.pre_authorization_migration_ledger_guard import (
    MigrationLedgerDriftGuardError,
    PACKAGE_BINDING_FIELDS,
    evaluate_migration_ledger_drift,
    inspect_authoritative_database,
    package_binding_from_document,
)


class AuthorizationBindingShapeTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path, dict[str, object]]:
        migrations = root / "migrations"
        migrations.mkdir()
        (migrations / "001_initial.sql").write_text("-- fixture\n", encoding="utf-8")

        db = root / "printer.sqlite3"
        connection = sqlite3.connect(db)
        try:
            connection.execute(
                "CREATE TABLE printer_schema_migrations (version TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO printer_schema_migrations(version) VALUES (?)",
                ("001_initial.sql",),
            )
            connection.commit()
        finally:
            connection.close()

        observed = inspect_authoritative_database(db)
        binding = {key: observed[key] for key in PACKAGE_BINDING_FIELDS}
        return migrations, db, binding

    def test_exact_binding_passes_review(self) -> None:
        with TemporaryDirectory() as temporary:
            migrations, db, binding = self._fixture(Path(temporary))
            result = evaluate_migration_ledger_drift(
                mode="review",
                db_path=db,
                migrations_dir=migrations,
                package_binding=binding,
            )
        self.assertTrue(result.passed, result.to_dict())

    def test_package_binding_from_document_blocks_missing_field(self) -> None:
        with TemporaryDirectory() as temporary:
            _, _, binding = self._fixture(Path(temporary))
            binding.pop("mtime_ns")
            with self.assertRaisesRegex(
                MigrationLedgerDriftGuardError,
                "exact required fields",
            ):
                package_binding_from_document(
                    {"authoritative_database": binding}
                )

    def test_package_binding_from_document_blocks_extra_field(self) -> None:
        with TemporaryDirectory() as temporary:
            _, _, binding = self._fixture(Path(temporary))
            binding["integrity"] = "ok"
            with self.assertRaisesRegex(
                MigrationLedgerDriftGuardError,
                "exact required fields",
            ):
                package_binding_from_document(
                    {"authoritative_database": binding}
                )

    def test_direct_review_blocks_truthful_binding_with_extra_field(self) -> None:
        with TemporaryDirectory() as temporary:
            migrations, db, binding = self._fixture(Path(temporary))
            binding["integrity"] = "ok"
            result = evaluate_migration_ledger_drift(
                mode="review",
                db_path=db,
                migrations_dir=migrations,
                package_binding=binding,
            )
        self.assertFalse(result.passed, result.to_dict())
        self.assertIn("package_binding_invalid", result.blocker_codes)


if __name__ == "__main__":
    unittest.main()

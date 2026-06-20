"""Minimal SQLite migration runner for Printer V1."""

from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"


def apply_migrations(db_path: str | Path) -> None:
    """Apply all SQL migrations to a local SQLite database."""
    database_path = Path(db_path)
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS printer_schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        applied_versions = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations"
            ).fetchall()
        }

        for migration_file in migration_files:
            version = migration_file.name
            if version in applied_versions:
                continue

            sql = migration_file.read_text(encoding="utf-8")
            connection.executescript(sql)
            connection.execute(
                "INSERT INTO printer_schema_migrations (version) VALUES (?)",
                (version,),
            )
        connection.commit()
    finally:
        connection.close()

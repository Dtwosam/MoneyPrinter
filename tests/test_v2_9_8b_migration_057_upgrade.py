from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from printer_v1.db import apply_migrations
from printer_v1.db.migrate import MIGRATIONS_DIR, canonical_migration_names


MIGRATION_057 = "057_pre_lifecycle_discovery_refresh_work.sql"


def _table_columns(connection: sqlite3.Connection, table_name: str) -> tuple[tuple, ...]:
    return tuple(connection.execute(f"PRAGMA table_info({table_name})").fetchall())


def test_migration_057_upgrades_previous_head_additively(tmp_path):
    """Prove the 056 -> 057 upgrade preserves the legacy discovery-work schema."""
    db_path = tmp_path / "upgrade.sqlite3"
    names = canonical_migration_names()
    assert names[-1] == MIGRATION_057

    connection = sqlite3.connect(db_path)
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
        for name in names[:-1]:
            connection.executescript((MIGRATIONS_DIR / name).read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO printer_schema_migrations (version) VALUES (?)",
                (name,),
            )
        connection.commit()

        legacy_columns_before = _table_columns(connection, "printer_discovery_work")
        assert legacy_columns_before
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='printer_pre_lifecycle_discovery_refresh_work'"
            ).fetchone()
            is None
        )
    finally:
        connection.close()

    apply_migrations(db_path)

    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        applied = tuple(
            row[0]
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY rowid"
            ).fetchall()
        )
        assert applied == names
        assert _table_columns(connection, "printer_discovery_work") == legacy_columns_before
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='printer_pre_lifecycle_discovery_refresh_work'"
            ).fetchone()
            is not None
        )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()

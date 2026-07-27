"""Minimal SQLite migration runner for Printer V1.

The ordered ``migrations/*.sql`` directory is the single canonical source for
migration names, counts, and ledger validation. Callers must not hard-code a
migration count.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"


def canonical_migration_names(
    migrations_dir: Path | None = None,
) -> tuple[str, ...]:
    """Return the ordered canonical migration file names.

    The directory listing is sorted lexicographically, which matches the
    zero-padded ``NNN_name.sql`` naming contract used by every Printer V1
    migration.
    """
    directory = Path(migrations_dir) if migrations_dir is not None else MIGRATIONS_DIR
    names = tuple(path.name for path in sorted(directory.glob("*.sql")))
    if not names:
        raise RuntimeError(f"no canonical migrations found under {directory}")
    seen: set[str] = set()
    duplicates: list[str] = []
    for name in names:
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)
    if duplicates:
        raise RuntimeError(
            "canonical migration directory contains duplicate names: "
            + ", ".join(duplicates)
        )
    return names


def canonical_migration_count(migrations_dir: Path | None = None) -> int:
    """Return the live canonical migration count (never hard-coded)."""
    return len(canonical_migration_names(migrations_dir))


def describe_migration_ledger_mismatch(
    applied: Sequence[str],
    *,
    migrations_dir: Path | None = None,
) -> list[str]:
    """Describe exact migration-ledger failures, or return an empty list.

    Reports missing, unexpected, duplicate, reordered, and count mismatches
    against the single canonical ordered migration source.
    """
    expected = list(canonical_migration_names(migrations_dir))
    applied_list = [str(item) for item in applied]
    issues: list[str] = []

    if not applied_list:
        issues.append("applied migration ledger is empty")
        issues.append(
            f"missing canonical migrations: {expected}"
        )
        return issues

    applied_set = set(applied_list)
    expected_set = set(expected)
    if len(applied_list) != len(applied_set):
        seen: set[str] = set()
        duplicates: list[str] = []
        for name in applied_list:
            if name in seen and name not in duplicates:
                duplicates.append(name)
            seen.add(name)
        issues.append(f"duplicate applied migrations: {duplicates}")

    missing = [name for name in expected if name not in applied_set]
    unexpected = [name for name in applied_list if name not in expected_set]
    if missing:
        issues.append(f"missing canonical migrations: {missing}")
    if unexpected:
        issues.append(f"unexpected applied migrations: {unexpected}")

    if (
        not missing
        and not unexpected
        and len(applied_list) == len(expected)
        and applied_list != expected
    ):
        issues.append(
            "applied migrations are reordered relative to the canonical ledger: "
            f"applied={applied_list!r} expected={expected!r}"
        )

    if len(applied_list) != len(expected) and not missing and not unexpected:
        issues.append(
            f"migration count mismatch: applied={len(applied_list)} "
            f"canonical={len(expected)}"
        )

    if not issues and applied_list != expected:
        issues.append(
            "canonical migration ledger mismatch: "
            f"applied={applied_list!r} expected={expected!r}"
        )
    return issues


def validate_migration_ledger(
    applied: Sequence[str],
    *,
    migrations_dir: Path | None = None,
) -> dict[str, object]:
    """Validate an applied ledger against the canonical ordered source.

    Returns a structured report. Callers that must fail closed should raise
    when ``matches`` is false and surface ``issues``.
    """
    expected = list(canonical_migration_names(migrations_dir))
    applied_list = [str(item) for item in applied]
    issues = describe_migration_ledger_mismatch(
        applied_list, migrations_dir=migrations_dir
    )
    return {
        "matches": not issues and applied_list == expected,
        "applied": applied_list,
        "expected": expected,
        "applied_count": len(applied_list),
        "canonical_count": len(expected),
        "latest_canonical": expected[-1] if expected else None,
        "latest_applied": applied_list[-1] if applied_list else None,
        "issues": issues,
    }


def apply_migrations(db_path: str | Path) -> None:
    """Apply all SQL migrations to a local SQLite database."""
    database_path = Path(db_path)
    migration_files = [
        MIGRATIONS_DIR / name for name in canonical_migration_names()
    ]

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


__all__ = [
    "MIGRATIONS_DIR",
    "PROJECT_ROOT",
    "apply_migrations",
    "canonical_migration_count",
    "canonical_migration_names",
    "describe_migration_ledger_mismatch",
    "validate_migration_ledger",
]

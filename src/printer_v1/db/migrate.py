"""Minimal SQLite migration runner for Printer V1.

The ordered ``migrations/*.sql`` directory is the single canonical source for
migration names, counts, and ledger validation. Callers must not hard-code a
migration count.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import sqlite3
from typing import Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"

# Exact canonical migration filename contract: a zero-padded three-digit
# ordinal, then lowercase ``[a-z0-9]`` words separated by single underscores,
# then ``.sql``. Uppercase, spaces, doubled underscores, leading/trailing
# underscores, and any other suffix are rejected.
MIGRATION_FILENAME_PATTERN = re.compile(
    r"^(?P<ordinal>[0-9]{3})_(?P<slug>[a-z0-9]+(?:_[a-z0-9]+)*)\.sql$"
)
MIGRATION_DIGEST_DOMAIN = "PRINTER_V1_CANONICAL_MIGRATION_ORDER_V1"


def parse_migration_ordinal(name: str) -> int:
    """Return the ordinal encoded in a canonical migration filename.

    Raises ``ValueError`` when the name violates the filename contract.
    """
    match = MIGRATION_FILENAME_PATTERN.fullmatch(str(name))
    if match is None:
        raise ValueError(f"malformed canonical migration filename: {name!r}")
    return int(match.group("ordinal"))


def describe_canonical_catalogue_issues(names: Sequence[str]) -> list[str]:
    """Describe strict filename and sequence faults, or return an empty list.

    The catalogue must be a lexicographically ordered, gap-free, duplicate-free
    ``001..NNN`` run of well-formed filenames. Anything else is a fault: a
    catalogue that cannot be trusted must never be used to judge a live ledger.
    """
    listed = [str(item) for item in names]
    issues: list[str] = []
    if not listed:
        issues.append("canonical migration catalogue is empty")
        return issues

    malformed = [name for name in listed if MIGRATION_FILENAME_PATTERN.fullmatch(name) is None]
    if malformed:
        issues.append(f"malformed canonical migration filenames: {malformed}")
        # Ordinal-derived checks are meaningless once a name is malformed.
        return issues

    ordinals = [parse_migration_ordinal(name) for name in listed]

    duplicate_names = sorted({name for name in listed if listed.count(name) > 1})
    if duplicate_names:
        issues.append(f"duplicate canonical migration names: {duplicate_names}")

    duplicate_ordinals = sorted({value for value in ordinals if ordinals.count(value) > 1})
    if duplicate_ordinals:
        issues.append(
            f"duplicate canonical migration ordinals: {duplicate_ordinals}"
        )

    if listed != sorted(listed):
        issues.append(
            "canonical migration catalogue is not lexicographically ordered: "
            f"{listed!r}"
        )

    expected = list(range(1, len(ordinals) + 1))
    if not duplicate_ordinals and ordinals != expected:
        missing = sorted(set(expected) - set(ordinals))
        extra = sorted(set(ordinals) - set(expected))
        detail = []
        if missing:
            detail.append(f"missing ordinals {missing}")
        if extra:
            detail.append(f"out-of-range ordinals {extra}")
        if not detail:
            detail.append(f"non-ascending ordinals {ordinals}")
        issues.append(
            "canonical migration sequence is not a contiguous 001..NNN run: "
            + "; ".join(detail)
        )
    return issues


def ordered_name_digest(names: Sequence[str]) -> str:
    """Return the order-sensitive digest of a migration name sequence.

    Order-sensitive by construction: names are newline-joined under a domain
    tag, so a reordering produces a different digest even though the name *set*
    is unchanged.
    """
    payload = "\n".join(
        [MIGRATION_DIGEST_DOMAIN, *(str(item) for item in names)]
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def canonical_migration_names(
    migrations_dir: Path | None = None,
) -> tuple[str, ...]:
    """Return the ordered canonical migration file names.

    The directory listing is sorted lexicographically, which matches the
    zero-padded ``NNN_name.sql`` naming contract used by every Printer V1
    migration. The contract is enforced rather than assumed: a malformed
    filename or a non-contiguous ordinal run fails closed here, before any
    caller can compare a live ledger against an untrustworthy catalogue.
    """
    directory = Path(migrations_dir) if migrations_dir is not None else MIGRATIONS_DIR
    names = tuple(path.name for path in sorted(directory.glob("*.sql")))
    if not names:
        raise RuntimeError(f"no canonical migrations found under {directory}")
    issues = describe_canonical_catalogue_issues(names)
    if issues:
        raise RuntimeError(
            f"invalid canonical migration catalogue under {directory}: "
            + "; ".join(issues)
        )
    return names


def canonical_migration_digest(migrations_dir: Path | None = None) -> str:
    """Return the ordered-name digest of the canonical migration catalogue."""
    return ordered_name_digest(canonical_migration_names(migrations_dir))


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
    "MIGRATION_DIGEST_DOMAIN",
    "MIGRATION_FILENAME_PATTERN",
    "PROJECT_ROOT",
    "apply_migrations",
    "canonical_migration_count",
    "canonical_migration_digest",
    "canonical_migration_names",
    "describe_canonical_catalogue_issues",
    "describe_migration_ledger_mismatch",
    "ordered_name_digest",
    "parse_migration_ordinal",
    "validate_migration_ledger",
]

"""Pre-authorization migration-ledger drift guard.

One consumed ``WINDOW_15M`` authorization was permanently spent for zero
campaign output because the authoritative database ledger sat one canonical
migration behind the repository. The operational preflight caught the drift
correctly, but it only runs *inside* the child — by which point the
authorization has already been consumed and cannot be recovered.

This guard moves the identical structural question earlier, to the two places
where it is still free:

* ``prepare`` — before an authorization package directory or byte is written.
* ``review`` — independent re-derivation from the live repository and live
  database, plus honesty checking of the migration facts a package claims.

The guard owns no provider, Scheduler, campaign, memory, retrieval, or
paper-trading behaviour. It never writes, never migrates, and never opens the
authoritative database for anything but immutable read-only inspection. The
operational preflight in ``operational_memory_factory_command`` is deliberately
left unchanged as the final defence: this guard is an additional earlier gate,
never a replacement.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import sys
from pathlib import Path
import sqlite3
from typing import Any, Mapping, Sequence

from printer_v1.db.migrate import (
    canonical_migration_names,
    ordered_name_digest,
)
from printer_v1.operator_db.paths import get_default_db_path


GUARD_SCHEMA_VERSION = "PRINTER_V1_PRE_AUTHORIZATION_MIGRATION_LEDGER_GUARD_V1"
PASS_VERDICT = "V2_9_8B_PRE_AUTHORIZATION_MIGRATION_LEDGER_GUARD_PASS"
BLOCKED_VERDICT = "V2_9_8B_PRE_AUTHORIZATION_MIGRATION_LEDGER_GUARD_BLOCKED"
GUARD_MODES = ("prepare", "review")
SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")
LEDGER_TABLE = "printer_schema_migrations"

#: Package field carrying the authorization's authoritative-database binding.
PACKAGE_DB_BINDING_KEY = "authoritative_database"


class MigrationLedgerDriftGuardError(RuntimeError):
    """Fail-closed pre-authorization migration-ledger drift fault."""


@dataclass(frozen=True)
class GuardResult:
    """Structured PASS/BLOCKED outcome of one guard inspection."""

    mode: str
    status: str
    verdict: str
    blockers: tuple[dict[str, str], ...] = ()
    repository: Mapping[str, Any] = field(default_factory=dict)
    database: Mapping[str, Any] = field(default_factory=dict)
    package_binding: Mapping[str, Any] | None = None
    inspected_at: str = ""

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    @property
    def blocker_codes(self) -> tuple[str, ...]:
        return tuple(item["code"] for item in self.blockers)

    def summary(self) -> str:
        if self.passed:
            return "pre-authorization migration-ledger guard: PASS"
        detail = "; ".join(
            f"{item['code']}: {item['detail']}" for item in self.blockers
        )
        return f"pre-authorization migration-ledger guard blocked: {detail}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": GUARD_SCHEMA_VERSION,
            "mode": self.mode,
            "status": self.status,
            "verdict": self.verdict,
            "blockers": [dict(item) for item in self.blockers],
            "blocker_codes": list(self.blocker_codes),
            "repository": dict(self.repository),
            "database": dict(self.database),
            "package_binding": (
                dict(self.package_binding) if self.package_binding is not None else None
            ),
            "inspected_at": self.inspected_at,
            "authorization_created": False,
            "package_bytes_written": 0,
            "database_writes": 0,
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _blocker(code: str, detail: str) -> dict[str, str]:
    return {"code": code, "detail": detail}


def present_sidecars(db_path: str | Path) -> list[str]:
    """Return existing SQLite sidecar paths for one database file."""
    base = Path(db_path)
    return [
        f"{base}{suffix}"
        for suffix in SIDECAR_SUFFIXES
        if Path(f"{base}{suffix}").exists()
    ]


def inspect_authoritative_database(db_path: str | Path) -> dict[str, Any]:
    """Inspect one database with a sidecar-safe immutable read-only handle.

    Sidecars are rejected *before* the connection opens. ``immutable=1`` is only
    sound on a file with no hot journal, so the ordering matters: refusing
    sidecars first is what makes the immutable open safe, and the immutable open
    is what guarantees SQLite creates no ``-wal``/``-shm`` of its own and takes
    no lock against a file this guard must not disturb.
    """
    path = Path(db_path)
    sidecars = present_sidecars(path)
    identity: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "sidecars": sidecars,
        "opened_mode": "read_only_immutable",
    }
    if not path.is_file():
        identity.update(
            {
                "readable": False,
                "error": "authoritative database file is unavailable",
            }
        )
        return identity

    info = path.stat()
    identity.update(
        {
            "sha256": _sha256_file(path),
            "size": info.st_size,
            "inode": info.st_ino,
            "mtime_ns": info.st_mtime_ns,
        }
    )
    if sidecars:
        # Never open immutable against a possibly hot journal.
        identity.update(
            {
                "readable": False,
                "error": f"SQLite sidecars present: {sidecars}",
            }
        )
        return identity

    try:
        connection = sqlite3.connect(
            f"file:{path.as_posix()}?mode=ro&immutable=1", uri=True, timeout=0.0
        )
    except sqlite3.Error as exc:
        identity.update({"readable": False, "error": f"database is unreadable: {exc}"})
        return identity
    try:
        connection.execute("PRAGMA query_only=ON")
        has_ledger = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (LEDGER_TABLE,),
        ).fetchone() is not None
        if has_ledger:
            ledger = [
                str(row[0])
                for row in connection.execute(
                    f"SELECT version FROM {LEDGER_TABLE} ORDER BY rowid"
                ).fetchall()
            ]
        else:
            ledger = []
        integrity = [
            str(row[0])
            for row in connection.execute("PRAGMA integrity_check").fetchall()
        ]
        foreign_keys = [
            tuple(row)
            for row in connection.execute("PRAGMA foreign_key_check").fetchall()
        ]
    except sqlite3.Error as exc:
        identity.update({"readable": False, "error": f"database inspection failed: {exc}"})
        return identity
    finally:
        connection.close()

    identity.update(
        {
            "readable": True,
            "ledger_table_present": has_ledger,
            "migration_ledger": ledger,
            "migration_count": len(ledger),
            "migration_head": ledger[-1] if ledger else None,
            "ledger_digest": ordered_name_digest(ledger) if ledger else None,
            "integrity": integrity,
            "foreign_key_violations": len(foreign_keys),
            "foreign_key_sample": [list(row) for row in foreign_keys[:5]],
        }
    )
    return identity


def _catalogue_facts(migrations_dir: str | Path | None) -> tuple[dict[str, Any], list[dict[str, str]]]:
    directory = Path(migrations_dir) if migrations_dir is not None else None
    try:
        names = list(canonical_migration_names(directory))
    except RuntimeError as exc:
        # Reconstruct the raw listing so the report still names what was seen.
        raw: list[str] = []
        if directory is not None and directory.is_dir():
            raw = [item.name for item in sorted(directory.glob("*.sql"))]
        return (
            {
                "migrations_dir": str(directory) if directory is not None else None,
                "canonical_count": len(raw),
                "canonical_head": raw[-1] if raw else None,
                "canonical_names": raw,
                "canonical_digest": None,
                "catalogue_valid": False,
            },
            [_blocker("canonical_catalogue_invalid", str(exc))],
        )
    return (
        {
            "migrations_dir": str(directory) if directory is not None else None,
            "canonical_count": len(names),
            "canonical_head": names[-1],
            "canonical_names": names,
            "canonical_digest": ordered_name_digest(names),
            "catalogue_valid": True,
        },
        [],
    )


def _ledger_blockers(
    *, canonical: Sequence[str], applied: Sequence[str]
) -> list[dict[str, str]]:
    """Compare a live ledger against a validated canonical catalogue.

    Ordering matters as much as membership. A ledger holding exactly the right
    names in the wrong order is drift, not a match, so a strict ordered-prefix
    check runs even when no name is missing or unexpected.
    """
    expected = [str(item) for item in canonical]
    listed = [str(item) for item in applied]
    blockers: list[dict[str, str]] = []

    if not listed:
        return [
            _blocker(
                "migration_ledger_empty",
                f"applied ledger is empty; canonical head is {expected[-1]!r}",
            )
        ]

    duplicates = sorted({name for name in listed if listed.count(name) > 1})
    if duplicates:
        blockers.append(
            _blocker("migration_ledger_duplicate", f"duplicate applied migrations: {duplicates}")
        )

    expected_set = set(expected)
    applied_set = set(listed)
    missing = [name for name in expected if name not in applied_set]
    unexpected = [name for name in listed if name not in expected_set]
    if missing:
        blockers.append(
            _blocker("migration_ledger_missing", f"missing canonical migrations: {missing}")
        )
    if unexpected:
        blockers.append(
            _blocker(
                "migration_ledger_unexpected",
                f"unexpected applied migrations: {unexpected}",
            )
        )

    # Strict ordered-prefix check: catches reordering and any interleaving that
    # membership comparison alone cannot see.
    if not duplicates and not unexpected:
        prefix = expected[: len(listed)]
        if listed != prefix:
            blockers.append(
                _blocker(
                    "migration_ledger_out_of_order",
                    "applied ledger is not an ordered prefix of the canonical "
                    f"catalogue: applied={listed!r} expected_prefix={prefix!r}",
                )
            )

    if len(listed) != len(expected):
        blockers.append(
            _blocker(
                "migration_count_mismatch",
                f"applied count {len(listed)} != canonical count {len(expected)}",
            )
        )
    if listed[-1] != expected[-1]:
        blockers.append(
            _blocker(
                "migration_head_mismatch",
                f"applied head {listed[-1]!r} != canonical head {expected[-1]!r}",
            )
        )
    if not blockers and ordered_name_digest(listed) != ordered_name_digest(expected):
        blockers.append(
            _blocker(
                "migration_ledger_digest_mismatch",
                "ordered-name digest disagreement between ledger and catalogue",
            )
        )
    return blockers


def _health_blockers(database: Mapping[str, Any]) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    integrity = list(database.get("integrity") or [])
    if integrity != ["ok"]:
        blockers.append(
            _blocker("database_integrity", f"PRAGMA integrity_check returned {integrity!r}")
        )
    violations = int(database.get("foreign_key_violations") or 0)
    if violations:
        blockers.append(
            _blocker(
                "foreign_key_violations",
                f"{violations} foreign-key violation(s); "
                f"sample={database.get('foreign_key_sample')!r}",
            )
        )
    return blockers


def evaluate_migration_ledger_drift(
    *,
    mode: str = "prepare",
    db_path: str | Path | None = None,
    migrations_dir: str | Path | None = None,
    package_binding: Mapping[str, Any] | None = None,
) -> GuardResult:
    """Evaluate live repository canonical migrations against a live database."""
    if mode not in GUARD_MODES:
        raise MigrationLedgerDriftGuardError(f"unknown guard mode: {mode!r}")

    inspected_at = _utc_now()
    repository, blockers = _catalogue_facts(migrations_dir)

    target = Path(db_path) if db_path is not None else get_default_db_path()
    database = inspect_authoritative_database(target)

    if not database.get("readable"):
        blockers.append(
            _blocker(
                "database_unavailable",
                str(database.get("error") or "authoritative database is unreadable"),
            )
        )
    else:
        blockers.extend(_health_blockers(database))
        if not database.get("ledger_table_present"):
            blockers.append(
                _blocker(
                    "migration_ledger_absent",
                    f"table {LEDGER_TABLE!r} is missing from the authoritative database",
                )
            )
        elif repository["catalogue_valid"]:
            blockers.extend(
                _ledger_blockers(
                    canonical=repository["canonical_names"],
                    applied=database["migration_ledger"],
                )
            )

    binding_report: dict[str, Any] | None = None
    if package_binding is not None:
        binding_report, binding_blockers = _review_package_binding(
            package_binding=package_binding,
            repository=repository,
            database=database,
        )
        blockers.extend(binding_blockers)

    status = "PASS" if not blockers else "BLOCKED"
    return GuardResult(
        mode=mode,
        status=status,
        verdict=PASS_VERDICT if status == "PASS" else BLOCKED_VERDICT,
        blockers=tuple(blockers),
        repository=repository,
        database=database,
        package_binding=binding_report,
        inspected_at=inspected_at,
    )


def _review_package_binding(
    *,
    package_binding: Mapping[str, Any],
    repository: Mapping[str, Any],
    database: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Check a package's claimed migration facts against independent truth.

    ``review`` never trusts the package. Every claim is re-derived here from the
    live repository catalogue and the live database, so a package asserting a
    head, count, or identity it does not actually have is rejected rather than
    ratified.
    """
    claimed = {
        "migration_count": package_binding.get("migration_count"),
        "migration_head": package_binding.get("migration_head"),
        "sha256": package_binding.get("sha256"),
        "size": package_binding.get("size"),
        "path": package_binding.get("path"),
    }
    blockers: list[dict[str, str]] = []

    if not database.get("readable"):
        # Health blockers already recorded; nothing independent to compare to.
        return {"claimed": claimed, "observed": None, "honest": False}, blockers

    observed = {
        "migration_count": database.get("migration_count"),
        "migration_head": database.get("migration_head"),
        "sha256": database.get("sha256"),
        "size": database.get("size"),
        "path": database.get("path"),
    }

    for key in ("migration_count", "migration_head", "sha256", "size"):
        claim = claimed[key]
        if claim is None:
            blockers.append(
                _blocker(
                    "package_binding_incomplete",
                    f"package migration binding omits {key!r}",
                )
            )
            continue
        if claim != observed[key]:
            blockers.append(
                _blocker(
                    "package_binding_dishonest",
                    f"package claims {key}={claim!r} but the live database has "
                    f"{observed[key]!r}",
                )
            )

    claimed_path = claimed["path"]
    if claimed_path is not None:
        if Path(str(claimed_path)).resolve() != Path(str(observed["path"])).resolve():
            blockers.append(
                _blocker(
                    "package_binding_dishonest",
                    f"package binds database path {claimed_path!r} but the guard "
                    f"inspected {observed['path']!r}",
                )
            )

    # A package may only bind a head the repository actually still ships.
    if repository.get("catalogue_valid") and claimed["migration_head"] is not None:
        if claimed["migration_head"] not in repository["canonical_names"]:
            blockers.append(
                _blocker(
                    "package_binding_dishonest",
                    f"package binds head {claimed['migration_head']!r} which is not a "
                    "canonical repository migration",
                )
            )

    return (
        {"claimed": claimed, "observed": observed, "honest": not blockers},
        blockers,
    )


def assert_migration_ledger_ready(
    *,
    mode: str = "prepare",
    db_path: str | Path | None = None,
    migrations_dir: str | Path | None = None,
    package_binding: Mapping[str, Any] | None = None,
) -> GuardResult:
    """Return a PASS result or raise before any caller side effect occurs."""
    result = evaluate_migration_ledger_drift(
        mode=mode,
        db_path=db_path,
        migrations_dir=migrations_dir,
        package_binding=package_binding,
    )
    if not result.passed:
        raise MigrationLedgerDriftGuardError(result.summary())
    return result


def load_package_binding(authorization_file: str | Path) -> dict[str, Any]:
    """Read the authoritative-database binding out of an authorization package.

    The existing ``PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2`` schema already
    records this binding, so ``review`` reads what the package always carried
    and no authorization schema change is required.
    """
    path = Path(authorization_file)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise MigrationLedgerDriftGuardError(
            f"authorization file is unreadable or malformed: {exc}"
        ) from exc
    if not isinstance(document, dict):
        raise MigrationLedgerDriftGuardError("authorization file must be a JSON object")
    binding = document.get(PACKAGE_DB_BINDING_KEY)
    if not isinstance(binding, Mapping):
        raise MigrationLedgerDriftGuardError(
            f"authorization package has no {PACKAGE_DB_BINDING_KEY!r} binding"
        )
    return dict(binding)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Block migration-ledger drift before an authorization package is "
            "written or consumed."
        )
    )
    parser.add_argument("mode", choices=list(GUARD_MODES))
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--migrations-dir", default=None)
    parser.add_argument(
        "--authorization-file",
        default=None,
        help="review mode: package whose migration facts are checked for honesty",
    )
    args = parser.parse_args(argv)

    try:
        binding: dict[str, Any] | None = None
        if args.mode == "review":
            if not args.authorization_file:
                raise MigrationLedgerDriftGuardError(
                    "review mode requires --authorization-file"
                )
            binding = load_package_binding(args.authorization_file)
        result = evaluate_migration_ledger_drift(
            mode=args.mode,
            db_path=args.db_path,
            migrations_dir=args.migrations_dir,
            package_binding=binding,
        )
    except MigrationLedgerDriftGuardError as exc:
        print(
            json.dumps(
                {
                    "schema_version": GUARD_SCHEMA_VERSION,
                    "mode": args.mode,
                    "status": "BLOCKED",
                    "verdict": BLOCKED_VERDICT,
                    "blockers": [_blocker("guard_input_invalid", str(exc))],
                    "authorization_created": False,
                    "package_bytes_written": 0,
                },
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 3

    payload = json.dumps(result.to_dict(), indent=2, sort_keys=True, default=str)
    if result.passed:
        print(payload)
        return 0
    print(payload, file=sys.stderr)
    return 3


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "BLOCKED_VERDICT",
    "GUARD_MODES",
    "GUARD_SCHEMA_VERSION",
    "GuardResult",
    "MigrationLedgerDriftGuardError",
    "PACKAGE_DB_BINDING_KEY",
    "PASS_VERDICT",
    "assert_migration_ledger_ready",
    "evaluate_migration_ledger_drift",
    "inspect_authoritative_database",
    "load_package_binding",
    "main",
    "present_sidecars",
]

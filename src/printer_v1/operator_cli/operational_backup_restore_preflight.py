"""Fail-closed operational backup and disposable restore preflight.

This module does not migrate the source database. It reserves SQLite's writer
lock while copying, validates a same-volume temporary backup, rehearses current
migrations on a disposable restore, and publishes without overwriting an
existing artifact.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
from typing import Any
from uuid import uuid4

from printer_v1.db import migrate as migration_runner
from printer_v1.operator_cli.proof_db_schema_readiness import (
    CRITICAL_DATA_TABLES,
    validate_runtime_schema,
)


MIGRATION_032 = "032_campaign_ownership_schema.sql"
SQLITE_SUFFIXES = frozenset({".sqlite", ".sqlite3", ".db"})
OPERATIONAL_CRITICAL_TABLES = tuple(dict.fromkeys(CRITICAL_DATA_TABLES + (
    "printer_memory_factory_campaigns",
    "printer_memory_factory_campaign_configurations",
    "printer_memory_factory_campaign_reports",
    "printer_memory_factory_campaign_runs",
    "printer_memory_factory_campaign_cycles",
    "printer_memory_factory_campaign_token_slots",
    "printer_memory_factory_campaign_windows",
    "printer_memory_factory_campaign_scheduler_work",
    "printer_memory_factory_campaign_objects",
    "printer_memory_factory_campaign_report_objects",
)))


class OperationalBackupPreflightError(ValueError):
    """Raised when backup or restore evidence fails closed."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def source_identity(path: str | Path) -> str:
    """Return the exact content identity accepted by the preflight."""
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise OperationalBackupPreflightError(f"source database missing: {resolved}")
    return f"sha256:{_sha256(resolved)}"


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _inspect_connection(connection: sqlite3.Connection) -> dict[str, Any]:
    integrity_rows = [
        str(row[0]) for row in connection.execute("PRAGMA integrity_check").fetchall()
    ]
    foreign_key_rows = [
        tuple(row) for row in connection.execute("PRAGMA foreign_key_check").fetchall()
    ]
    if _table_exists(connection, "printer_schema_migrations"):
        migrations = [
            str(row[0]) for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY version"
            ).fetchall()
        ]
    else:
        migrations = []
    counts = {
        table: (
            int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            if _table_exists(connection, table) else 0
        )
        for table in OPERATIONAL_CRITICAL_TABLES
    }
    return {
        "migration_ledger": migrations,
        "latest_migration": migrations[-1] if migrations else None,
        "critical_row_counts": counts,
        "integrity_check": integrity_rows,
        "foreign_key_errors": foreign_key_rows,
        "foreign_key_error_count": len(foreign_key_rows),
    }


def _inspect_read_only(path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(
        f"file:{path.as_posix()}?mode=ro", uri=True, timeout=0.0
    )
    try:
        connection.execute("PRAGMA query_only=ON")
        return _inspect_connection(connection)
    finally:
        connection.close()


def _require_healthy(metadata: dict[str, Any], label: str) -> None:
    if metadata["integrity_check"] != ["ok"]:
        raise OperationalBackupPreflightError(
            f"{label} integrity check failed: {metadata['integrity_check']}"
        )
    if metadata["foreign_key_error_count"] != 0:
        raise OperationalBackupPreflightError(
            f"{label} foreign key check failed: "
            f"{metadata['foreign_key_error_count']} row(s)"
        )


def _validate_paths(
    source: Path,
    expected_source: Path,
    backup: Path,
    restore: Path,
    disposable_root: Path,
) -> None:
    if source != expected_source:
        raise OperationalBackupPreflightError(
            f"persistent target path mismatch: {source} != {expected_source}"
        )
    if not source.is_file():
        raise OperationalBackupPreflightError(f"source database missing: {source}")
    if source.suffix.lower() not in SQLITE_SUFFIXES:
        raise OperationalBackupPreflightError("source must be a SQLite file")
    if len({source, backup, restore}) != 3:
        raise OperationalBackupPreflightError(
            "source, backup, and restore paths must be distinct"
        )
    if backup.exists():
        raise OperationalBackupPreflightError(
            f"verified backup target already exists: {backup}"
        )
    if restore.exists():
        raise OperationalBackupPreflightError(
            f"disposable restore target already exists: {restore}"
        )
    if not backup.parent.is_dir():
        raise OperationalBackupPreflightError(
            f"backup parent must already exist: {backup.parent}"
        )
    if not disposable_root.is_dir():
        raise OperationalBackupPreflightError(
            f"disposable restore root missing: {disposable_root}"
        )
    if restore.parent != disposable_root:
        raise OperationalBackupPreflightError(
            "restore target must be a direct child of the disposable restore root"
        )
    if backup.suffix.lower() not in SQLITE_SUFFIXES:
        raise OperationalBackupPreflightError("backup target must be a SQLite file")
    if restore.suffix.lower() not in SQLITE_SUFFIXES:
        raise OperationalBackupPreflightError("restore target must be a SQLite file")


def _reject_sqlite_sidecars(source: Path) -> None:
    present = [
        str(Path(f"{source}{suffix}"))
        for suffix in ("-wal", "-shm", "-journal")
        if Path(f"{source}{suffix}").exists()
    ]
    if present:
        raise OperationalBackupPreflightError(
            f"source WAL or journal state is not quiescent: {present}"
        )


def _copy_bytes(source: Path, target: Path) -> None:
    shutil.copyfile(source, target)


def _verify_byte_copy(
    *, source_size: int, source_hash: str, copy_path: Path, label: str,
) -> None:
    copy_size = copy_path.stat().st_size
    copy_hash = _sha256(copy_path)
    if copy_size != source_size or copy_hash != source_hash:
        raise OperationalBackupPreflightError(
            f"{label} byte verification failed: size/hash mismatch"
        )


def operational_backup_restore_preflight(
    source_db_path: str | Path,
    *,
    expected_source_path: str | Path,
    expected_source_identity: str,
    backup_path: str | Path,
    disposable_restore_root: str | Path,
    restore_path: str | Path,
) -> dict[str, Any]:
    """Verify, back up, and migrate-rehearse one explicit source database.

    The source is never migrated. Publication uses ``os.link`` so an existing
    destination cannot be replaced, including a destination created by a race.
    """
    source = Path(source_db_path).resolve()
    expected_source = Path(expected_source_path).resolve()
    backup = Path(backup_path).resolve()
    disposable_root = Path(disposable_restore_root).resolve()
    restore = Path(restore_path).resolve()
    _validate_paths(source, expected_source, backup, restore, disposable_root)
    _reject_sqlite_sidecars(source)

    expected_identity = str(expected_source_identity).strip().lower()
    if not expected_identity.startswith("sha256:") or len(expected_identity) != 71:
        raise OperationalBackupPreflightError(
            "expected source identity must be sha256:<64 lowercase hex>"
        )
    try:
        int(expected_identity.removeprefix("sha256:"), 16)
    except ValueError as exc:
        raise OperationalBackupPreflightError(
            "expected source identity contains non-hex characters"
        ) from exc

    source_size_before = source.stat().st_size
    source_hash_before = _sha256(source)
    actual_identity = f"sha256:{source_hash_before}"
    if actual_identity != expected_identity:
        raise OperationalBackupPreflightError(
            f"persistent target identity mismatch: {actual_identity}"
        )

    temporary_backup = backup.parent / f".{backup.name}.{uuid4().hex}.tmp"
    restore_created = False
    source_connection: sqlite3.Connection | None = None
    try:
        source_connection = sqlite3.connect(source, timeout=0.0)
        source_connection.execute("PRAGMA foreign_keys=ON")
        try:
            source_connection.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            raise OperationalBackupPreflightError(
                f"exclusive writer check failed: {exc}"
            ) from exc

        source_metadata_before = _inspect_connection(source_connection)
        _require_healthy(source_metadata_before, "source")

        _copy_bytes(source, temporary_backup)
        _verify_byte_copy(
            source_size=source_size_before,
            source_hash=source_hash_before,
            copy_path=temporary_backup,
            label="temporary backup",
        )
        temporary_metadata = _inspect_read_only(temporary_backup)
        _require_healthy(temporary_metadata, "temporary backup")
        if temporary_metadata != source_metadata_before:
            raise OperationalBackupPreflightError(
                "temporary backup metadata differs from source"
            )

        _copy_bytes(temporary_backup, restore)
        restore_created = True
        _verify_byte_copy(
            source_size=source_size_before,
            source_hash=source_hash_before,
            copy_path=restore,
            label="disposable restore before migration",
        )
        migration_runner.apply_migrations(restore)
        restore_validation = validate_runtime_schema(restore)
        restore_metadata = _inspect_read_only(restore)
        _require_healthy(restore_metadata, "migrated disposable restore")
        if MIGRATION_032 not in restore_metadata["migration_ledger"]:
            raise OperationalBackupPreflightError(
                "disposable restore did not reach migration 032"
            )
        if (
            restore_metadata["critical_row_counts"]
            != source_metadata_before["critical_row_counts"]
        ):
            raise OperationalBackupPreflightError(
                "restore rehearsal changed critical data-row counts"
            )

        source_metadata_after = _inspect_connection(source_connection)
        source_size_after = source.stat().st_size
        source_hash_after = _sha256(source)
        if (
            source_size_after != source_size_before
            or source_hash_after != source_hash_before
            or source_metadata_after != source_metadata_before
        ):
            raise OperationalBackupPreflightError(
                "source database changed during preflight"
            )

        try:
            os.link(temporary_backup, backup)
        except FileExistsError as exc:
            raise OperationalBackupPreflightError(
                f"verified backup target already exists: {backup}"
            ) from exc
        except OSError as exc:
            raise OperationalBackupPreflightError(
                f"atomic same-volume backup publication failed: {exc}"
            ) from exc
        backup_size = backup.stat().st_size
        backup_hash = _sha256(backup)
        if backup_size != source_size_before or backup_hash != source_hash_before:
            raise OperationalBackupPreflightError(
                "published backup differs from verified temporary backup"
            )

        return {
            "status": "OPERATIONAL_BACKUP_RESTORE_PREFLIGHT_READY",
            "source_path": str(source),
            "source_identity": actual_identity,
            "source_size_before": source_size_before,
            "source_size_after": source_size_after,
            "source_hash_before": source_hash_before,
            "source_hash_after": source_hash_after,
            "source_unchanged": True,
            "exclusive_writer_verified": True,
            "source_metadata": source_metadata_before,
            "backup_path": str(backup),
            "backup_size": backup_size,
            "backup_hash": backup_hash,
            "backup_byte_identical": True,
            "restore_path": str(restore),
            "restore_pre_migration_hash": source_hash_before,
            "restore_metadata": restore_metadata,
            "restore_validation": restore_validation,
            "required_rehearsed_migration": MIGRATION_032,
            "latest_rehearsed_migration": restore_metadata["latest_migration"],
            "sources_run": False,
            "scheduler_runtime_run": False,
            "source_writes": 0,
        }
    except Exception:
        if restore_created and restore.exists():
            restore.unlink()
        raise
    finally:
        if source_connection is not None:
            try:
                if source_connection.in_transaction:
                    source_connection.rollback()
            finally:
                source_connection.close()
        if temporary_backup.exists():
            temporary_backup.unlink()

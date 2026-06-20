"""One-shot operator database bootstrap helpers."""

from pathlib import Path
from typing import Any

from printer_v1.db import apply_migrations
from printer_v1.operator_db.paths import (
    db_path_is_sqlite_file,
    ensure_data_dir_exists,
    get_default_db_path,
    resolve_operator_db_path,
)
from printer_v1.operator_db.status import get_operator_db_status, get_schema_migration_status


def operator_db_exists(db_path: str | Path | None = None, project_root: str | Path | None = None) -> bool:
    return resolve_operator_db_path(db_path, project_root).is_file()


def apply_all_migrations_to_operator_db(db_path: str | Path | None = None, project_root: str | Path | None = None) -> Path:
    resolved = resolve_operator_db_path(db_path, project_root)
    if not db_path_is_sqlite_file(resolved):
        raise ValueError("Operator DB path must use a SQLite file suffix.")
    ensure_data_dir_exists(resolved.parent)
    apply_migrations(resolved)
    return resolved


def initialize_operator_db(db_path: str | Path | None = None, project_root: str | Path | None = None) -> dict[str, Any]:
    resolved = apply_all_migrations_to_operator_db(db_path, project_root)
    return get_operator_db_bootstrap_report(resolved, project_root)


def get_operator_db_bootstrap_report(db_path: str | Path | None = None, project_root: str | Path | None = None) -> dict[str, Any]:
    resolved = resolve_operator_db_path(db_path or get_default_db_path(project_root), project_root)
    return {
        "db_path": str(resolved),
        "exists": resolved.is_file(),
        "schema": get_schema_migration_status(resolved, project_root),
        "status": get_operator_db_status(resolved, project_root),
    }

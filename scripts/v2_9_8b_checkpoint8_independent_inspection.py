#!/usr/bin/env python3
"""Checkpoint 8 independent-inspection safety shell.

This file owns only the proof DB isolation/read-only boundary at this stage.
The complete frozen-evidence inspection is added only after the controlling
harness entry contracts are proven.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
from urllib.parse import quote


class Checkpoint8IndependentInspectionError(RuntimeError):
    """Fail-closed independent-inspection fault."""


def validate_independent_proof_db_target(
    db_path: str | Path,
    *,
    canonical_db_path: str | Path,
) -> Path:
    target = Path(db_path).expanduser().resolve()
    canonical = Path(canonical_db_path).expanduser().resolve()

    if target == canonical:
        raise Checkpoint8IndependentInspectionError(
            "CANONICAL_PRODUCTION_DB_FORBIDDEN"
        )
    if not target.is_file():
        raise Checkpoint8IndependentInspectionError(
            "INDEPENDENT_PROOF_DB_MISSING"
        )
    return target


def open_independent_read_only_db(
    db_path: str | Path,
    *,
    canonical_db_path: str | Path,
) -> sqlite3.Connection:
    target = validate_independent_proof_db_target(
        db_path,
        canonical_db_path=canonical_db_path,
    )
    uri = f"file:{quote(str(target))}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def main(argv: list[str] | None = None) -> int:
    del argv
    raise Checkpoint8IndependentInspectionError(
        "CHECKPOINT8_INDEPENDENT_INSPECTION_NOT_YET_WIRED"
    )


if __name__ == "__main__":
    raise SystemExit(main())

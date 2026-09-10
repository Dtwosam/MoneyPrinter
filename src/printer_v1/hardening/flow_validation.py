"""Disposable-only public facade for synthetic validation.

The historical synthetic stages remain available for focused disposable tests,
but the full mutating validation flow may run only against a database created
through ``initialize_temp_validation_db`` inside the process-local temporary
root. Arbitrary paths and SQLite connections fail before stage 1.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
from typing import Any

from printer_v1.hardening import _flow_validation_impl as _impl


# Focused historical synthetic stages remain available for disposable tests.
seed_synthetic_discovery_and_snapshots = _impl.seed_synthetic_discovery_and_snapshots
seed_synthetic_context_engine_rows = _impl.seed_synthetic_context_engine_rows
run_synthetic_memory_build = _impl.run_synthetic_memory_build
run_synthetic_memory_retrieval = _impl.run_synthetic_memory_retrieval
run_synthetic_paper_decision = _impl.run_synthetic_paper_decision
run_synthetic_paper_monitor = _impl.run_synthetic_paper_monitor
run_synthetic_paper_audit = _impl.run_synthetic_paper_audit
run_synthetic_operator_review = _impl.run_synthetic_operator_review

_REGISTERED_TEMP_VALIDATION_DATABASES: set[Path] = set()
_TEMP_VALIDATION_ERROR = "FULL_SYNTHETIC_VALIDATION_REQUIRES_REGISTERED_TEMP_DB"


def _resolved_isolated_temp_dir(temp_dir: str | Path) -> Path:
    candidate = Path(temp_dir).resolve(strict=False)
    system_temp = Path(tempfile.gettempdir()).resolve(strict=False)
    if (
        candidate == system_temp
        or not candidate.is_relative_to(system_temp)
        or not candidate.is_dir()
    ):
        raise ValueError(_TEMP_VALIDATION_ERROR)
    return candidate


def initialize_temp_validation_db(temp_dir: str | Path) -> Path:
    """Create and register one disposable synthetic-validation database."""

    isolated_temp_dir = _resolved_isolated_temp_dir(temp_dir)
    db_path = _impl.initialize_temp_validation_db(isolated_temp_dir).resolve(
        strict=False
    )
    _REGISTERED_TEMP_VALIDATION_DATABASES.add(db_path)
    return db_path


def _consume_registered_temp_validation_db(
    db_path_or_conn: str | Path | sqlite3.Connection,
) -> Path:
    if isinstance(db_path_or_conn, sqlite3.Connection):
        raise ValueError(_TEMP_VALIDATION_ERROR)
    candidate = Path(db_path_or_conn).resolve(strict=False)
    if candidate not in _REGISTERED_TEMP_VALIDATION_DATABASES:
        raise ValueError(_TEMP_VALIDATION_ERROR)
    _REGISTERED_TEMP_VALIDATION_DATABASES.discard(candidate)
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def run_full_synthetic_validation_flow(
    db_path_or_conn: str | Path | sqlite3.Connection,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    """Run the mutating full flow once on a registered disposable DB only."""

    db_path = _consume_registered_temp_validation_db(db_path_or_conn)
    payload = _impl.run_full_synthetic_validation_flow(
        db_path,
        project_root=project_root,
    )
    if payload.get("synthetic_only") is not True or payload.get("temp_db_only") is not True:
        raise RuntimeError("synthetic validation lost its disposable-only contract")
    return payload


__all__ = [
    "initialize_temp_validation_db",
    "run_full_synthetic_validation_flow",
    "seed_synthetic_discovery_and_snapshots",
    "seed_synthetic_context_engine_rows",
    "run_synthetic_memory_build",
    "run_synthetic_memory_retrieval",
    "run_synthetic_paper_decision",
    "run_synthetic_paper_monitor",
    "run_synthetic_paper_audit",
    "run_synthetic_operator_review",
]

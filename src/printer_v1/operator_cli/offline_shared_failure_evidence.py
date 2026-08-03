"""Proof-only preservation for a failed offline public composition.

This helper is never called by ordinary discovery or operational production
paths. It copies a closed disposable database and writes one execution-scoped,
allowlisted pre-lifecycle failure artifact for later read-only classification.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

from printer_v1.db.migrate import canonical_migration_names
from printer_v1.operator_cli.proof_db_schema_readiness import (
    CANONICAL_PERSISTENT_DB,
)


ARTIFACT_SCHEMA_VERSION = "PRE_LIFECYCLE_FAILURE_OFFLINE_EVIDENCE_V2"
DATABASE_COPY_NAME = "shared-failure-disposable-migration-050.sqlite3"
FAILURE_ARTIFACT_NAME = "shared-failure-evidence.json"
_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")
_URL_VALUE = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)
_SECRET_ASSIGNMENT = re.compile(
    r"\b(api[_-]?key|authorization|credential|password|secret|token)\s*[:=]\s*[^\s,;]+",
    re.IGNORECASE,
)
_SENSITIVE_ENV_NAME = re.compile(
    r"(?:API|AUTH|BEARER|CREDENTIAL|KEY|PASSWORD|RPC|SECRET|TOKEN|URL)", re.IGNORECASE
)


class OfflineSharedFailureEvidenceError(RuntimeError):
    """Secondary proof-harness failure that retains the operational first cause."""

    def __init__(
        self,
        message: str,
        *,
        first_failure: Mapping[str, Any],
        secondary_failure: Mapping[str, Any],
    ) -> None:
        self.first_failure = dict(first_failure)
        self.secondary_failure = dict(secondary_failure)
        super().__init__(message)


def _redact_text(value: str) -> str:
    text = value
    for name, configured in os.environ.items():
        if _SENSITIVE_ENV_NAME.search(name) and len(configured) >= 4:
            text = text.replace(configured, "[REDACTED_CONFIG]")
    text = _URL_VALUE.sub("[REDACTED_URL]", text)
    text = _SECRET_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}=[REDACTED]", text
    )
    return " ".join(text.split())[:1000]


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, Mapping):
        return {str(key): _redact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_text(str(value))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sidecars(path: Path) -> list[str]:
    return [
        str(Path(f"{path}{suffix}").resolve())
        for suffix in _SIDECAR_SUFFIXES
        if Path(f"{path}{suffix}").exists()
    ]


def _copy_closed_database(source: Path, destination: Path) -> dict[str, Any]:
    source_sidecars_before = _sidecars(source)
    source_connection = sqlite3.connect(source)
    destination_connection: sqlite3.Connection | None = None
    checkpoint: dict[str, Any] = {"required": False, "completed": True}
    try:
        journal_mode = str(source_connection.execute("PRAGMA journal_mode").fetchone()[0])
        if journal_mode.casefold() == "wal":
            checkpoint["required"] = True
            row = source_connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            checkpoint["result"] = list(row) if row is not None else None
            checkpoint["completed"] = bool(row is not None and int(row[0]) == 0)
            if not checkpoint["completed"]:
                raise RuntimeError("disposable database WAL checkpoint did not complete")
        destination_connection = sqlite3.connect(destination)
        source_connection.backup(destination_connection)
        destination_connection.commit()
    finally:
        if destination_connection is not None:
            destination_connection.close()
        source_connection.close()
    destination_sidecars = _sidecars(destination)
    if destination_sidecars:
        raise RuntimeError("preserved database retained SQLite sidecars after close")
    return {
        "journal_mode": journal_mode,
        "source_sidecars_before_copy": source_sidecars_before,
        "source_sidecars_after_copy": _sidecars(source),
        "destination_sidecars_after_close": destination_sidecars,
        "checkpoint": checkpoint,
        "copy_method": "sqlite_backup_api_after_owner_connections_closed",
    }


def _inspect_copy(path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys = [
            list(row) for row in connection.execute("PRAGMA foreign_key_check").fetchall()
        ]
        applied = {
            str(row[0])
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations"
            ).fetchall()
        }
    finally:
        connection.close()
    canonical = canonical_migration_names()
    migration_head = canonical[-1]
    return {
        "integrity_check": integrity,
        "foreign_key_check": foreign_keys,
        "migration_head": migration_head,
        "migration_head_applied": migration_head in applied,
        "migration_count": len(applied),
        "inspection_mode": "sqlite_uri_mode_ro_query_only",
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    encoded = json.dumps(
        dict(payload),
        allow_nan=False,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ) + "\n"
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def preserve_failed_offline_composition_evidence(
    *,
    source_database: str | Path,
    artifact_root: str | Path,
    execution_id: str,
    baseline_git_head: str,
    tracked_tree_state: Mapping[str, Any],
    test_node_id: str,
    terminal: Mapping[str, Any],
    zero_network_assertion: Mapping[str, Any],
    retry_state: Mapping[str, Any],
    connections_closed: bool,
) -> dict[str, Any]:
    """Preserve one failed disposable composition after every DB owner closes."""
    fault_details = dict(terminal.get("fault_details") or {})
    first_failure = dict(fault_details.get("first_failure") or {})
    activation_status = str(
        terminal.get("activation_terminal_status")
        or terminal.get("run_status")
        or ""
    )
    first_cause = str(terminal.get("first_terminal_cause") or "")
    failure_required = bool(terminal.get("failure_evidence_required"))
    classification = str(
        first_failure.get("classification") or first_cause or activation_status
    )
    is_returned_failure = bool(
        first_failure
        or failure_required
        or (
            activation_status
            and activation_status not in {"COMPLETED", "SUCCEEDED", "PASS"}
        )
    )
    if not is_returned_failure:
        raise ValueError("offline evidence preservation is failure-only")
    if not first_failure:
        first_failure = {
            "classification": classification or "PRE_LIFECYCLE_FAILURE",
            "exception_class": "RETURNED_OPERATIONAL_TERMINAL",
            "sanitized_message": first_cause or activation_status,
        }
    if not connections_closed:
        raise ValueError("all composition database connections must close first")

    source = Path(source_database).resolve()
    authoritative = Path(CANONICAL_PERSISTENT_DB).resolve()
    if source == authoritative:
        raise ValueError("authoritative database preservation is forbidden")
    if not source.is_file():
        raise FileNotFoundError(source)
    execution = str(execution_id).strip()
    if not execution or Path(execution).name != execution:
        raise ValueError("execution_id must be one safe path component")

    directory = (Path(artifact_root).resolve() / execution).resolve()
    database_copy = directory / DATABASE_COPY_NAME
    artifact_path = directory / FAILURE_ARTIFACT_NAME
    try:
        directory.mkdir(parents=True, exist_ok=False)
        sidecars = _copy_closed_database(source, database_copy)
        inspection = _inspect_copy(database_copy)
        database_hash = _sha256(database_copy)
        payload = {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "execution_identity": execution,
            "baseline_git_head": str(baseline_git_head),
            "tracked_tree_state": _redact(dict(tracked_tree_state)),
            "test_node_id": str(test_node_id),
            "first_failure_classification": classification,
            "first_failure": _redact(first_failure),
            "authoritative_terminal": _redact(
                {
                    "status": terminal.get("status"),
                    "activation_terminal_status": terminal.get(
                        "activation_terminal_status"
                    ),
                    "run_status": terminal.get("run_status"),
                    "first_terminal_cause": terminal.get(
                        "first_terminal_cause"
                    ),
                    "cancellation_reason": terminal.get("cancellation_reason"),
                    "lifecycle_started": terminal.get("lifecycle_started"),
                    "accountable_stage_started": terminal.get(
                        "accountable_stage_started"
                    ),
                    "accounting_required": terminal.get("accounting_required"),
                    "accounting_status": terminal.get("accounting_status"),
                }
            ),
            "secondary_failures": _redact(
                list(fault_details.get("secondary_failures") or [])
            ),
            "discovery": _redact(dict(fault_details.get("discovery") or {})),
            "pre_rollback_state": _redact(
                fault_details.get("pre_rollback_state")
            ),
            "rollback": _redact(dict(fault_details.get("rollback") or {})),
            "preserved_database": {
                "path": str(database_copy),
                "sha256": database_hash,
                **sidecars,
                **inspection,
                "evidence_only_not_production_database": True,
            },
            "zero_network_assertion_boundary": _redact(
                dict(zero_network_assertion)
            ),
            "retry_or_successor_state": _redact(dict(retry_state)),
        }
        _write_json(artifact_path, payload)
    except Exception as exc:
        secondary = {
            "stage": "OFFLINE_FAILURE_ARTIFACT_WRITE",
            "exception_class": type(exc).__name__,
            "sanitized_message": _redact_text(str(exc)),
        }
        raise OfflineSharedFailureEvidenceError(
            "offline pre-lifecycle failure evidence capture failed after the operational failure",
            first_failure=first_failure,
            secondary_failure=secondary,
        ) from exc
    return {
        "artifact_directory": str(directory),
        "failure_artifact": str(artifact_path),
        "preserved_database": str(database_copy),
        "preserved_database_sha256": database_hash,
        "integrity_check": inspection["integrity_check"],
        "foreign_key_check": inspection["foreign_key_check"],
    }


__all__ = [
    "ARTIFACT_SCHEMA_VERSION",
    "DATABASE_COPY_NAME",
    "FAILURE_ARTIFACT_NAME",
    "OfflineSharedFailureEvidenceError",
    "preserve_failed_offline_composition_evidence",
]

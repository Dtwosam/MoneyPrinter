#!/usr/bin/env python3
"""Checkpoint 8 controlling-proof safety shell.

This file intentionally owns only the proof-only safety envelope at this stage:
the process-local network tripwire and the atomic one-shot attempt claim.

It does not construct fixtures, start Printer runtime work, or execute the
controlling proof. Those entry responsibilities remain fail-closed until the
subsequent Checkpoint 8 harness-wiring slice is proven.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
from types import SimpleNamespace
from typing import Any

from printer_v1.db.migrate import (
    apply_migrations,
    canonical_migration_count,
    canonical_migration_names,
)
from printer_v1.operator_cli.proof_db_schema_readiness import (
    CANONICAL_PERSISTENT_DB,
)
from printer_v1.operator_cli import (
    window_15m_disposable_public_composition_proof as proof,
)
from printer_v1.operator_cli.window_15m_concrete_composition import (
    ordinary_window_15m_builder_identities,
)


_ATTEMPT_SENTINEL_NAME = "checkpoint8-controlling-attempt.json"


class Checkpoint8ControllingProofError(RuntimeError):
    """Fail-closed controlling-proof harness fault."""


class Checkpoint8NetworkTripwireError(Checkpoint8ControllingProofError):
    """Raised when the proof process attempts an external network operation."""


class Checkpoint8NetworkAttempt:
    """Minimal import-safe record for one blocked network attempt."""

    __slots__ = ("operation", "target")

    def __init__(self, *, operation: str, target: str) -> None:
        self.operation = operation
        self.target = target


def _redacted_target(value: Any) -> str:
    if isinstance(value, tuple) and value:
        host = str(value[0])
        port = value[1] if len(value) > 1 else None
        family = "IPV6" if ":" in host else "IP"
        return f"{family}:{port if port is not None else 'UNKNOWN'}"
    return type(value).__name__


class Checkpoint8NetworkTripwire:
    """Process-local socket tripwire used only by the C8 controlling harness."""

    def __init__(self) -> None:
        self.attempts: list[Checkpoint8NetworkAttempt] = []
        self._installed = False
        self._original_create_connection = None
        self._original_connect = None
        self._original_connect_ex = None

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    def _record_and_fail(self, operation: str, target: Any) -> None:
        self.attempts.append(
            Checkpoint8NetworkAttempt(
                operation=operation,
                target=_redacted_target(target),
            )
        )
        raise Checkpoint8NetworkTripwireError(
            "CHECKPOINT8_EXTERNAL_NETWORK_ATTEMPT_FORBIDDEN"
        )

    def __enter__(self) -> "Checkpoint8NetworkTripwire":
        if self._installed:
            raise Checkpoint8NetworkTripwireError(
                "CHECKPOINT8_NETWORK_TRIPWIRE_ALREADY_INSTALLED"
            )

        self._original_create_connection = socket.create_connection
        self._original_connect = socket.socket.connect
        self._original_connect_ex = socket.socket.connect_ex
        tripwire = self

        def blocked_create_connection(address, *args, **kwargs):
            del args, kwargs
            tripwire._record_and_fail("socket.create_connection", address)

        def blocked_connect(sock, address):
            del sock
            tripwire._record_and_fail("socket.socket.connect", address)

        def blocked_connect_ex(sock, address):
            del sock
            tripwire._record_and_fail("socket.socket.connect_ex", address)

        socket.create_connection = blocked_create_connection
        socket.socket.connect = blocked_connect
        socket.socket.connect_ex = blocked_connect_ex
        self._installed = True
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self._installed:
            socket.create_connection = self._original_create_connection
            socket.socket.connect = self._original_connect
            socket.socket.connect_ex = self._original_connect_ex
            self._installed = False
        return False


def claim_controlling_attempt_sentinel(
    proof_root: str | Path,
    *,
    proof_id: str,
    git_head: str,
) -> Path:
    """Atomically consume the single C8 controlling-attempt entitlement."""
    root = Path(proof_root).expanduser().resolve()
    if not root.is_dir():
        raise Checkpoint8ControllingProofError(
            "CONTROLLING_PROOF_ROOT_MISSING"
        )

    proof = str(proof_id or "").strip()
    head = str(git_head or "").strip()
    if not proof:
        raise Checkpoint8ControllingProofError("CONTROLLING_PROOF_ID_MISSING")
    if len(head) != 40 or any(ch not in "0123456789abcdef" for ch in head.lower()):
        raise Checkpoint8ControllingProofError("CONTROLLING_GIT_HEAD_INVALID")

    sentinel = root / _ATTEMPT_SENTINEL_NAME
    payload = {
        "attempt_ordinal": 1,
        "git_head": head,
        "proof_id": proof,
        "sentinel_schema": "CHECKPOINT8_CONTROLLING_ATTEMPT_V1",
    }
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(sentinel, flags, 0o600)
    except FileExistsError as exc:
        raise Checkpoint8ControllingProofError(
            "CONTROLLING_ATTEMPT_ALREADY_CONSUMED"
        ) from exc

    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            sentinel.unlink()
        except FileNotFoundError:
            pass
        raise

    return sentinel



_PROTECTED_CAPABILITY_TABLES = (
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
)


class _Checkpoint8DeterministicFixture:
    """Zero-I/O fixture value for one canonical C8 DI route."""

    def __init__(self, route: str) -> None:
        self.route = str(route)

    def __call__(self, *args, **kwargs):
        del args, kwargs
        return self

    def execute(self, *args, **kwargs):
        del args, kwargs
        return self

    def json_get(self, *args, **kwargs):
        del args, kwargs
        return self

    def json_rpc(self, *args, **kwargs):
        del args, kwargs
        return self


def _checkpoint8_route_by_label() -> dict[str, str]:
    route_rows = getattr(proof, "_EXECUTION_ROUTE_BY_LABEL", None)
    if route_rows is None:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_FIXTURE_ROUTE_OWNER_MISSING"
        )
    route_by_label = {
        str(label): str(route)
        for label, route in tuple(route_rows)
    }
    expected = tuple(ordinary_window_15m_builder_identities())
    if tuple(route_by_label) != expected:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_FIXTURE_ROUTE_REGISTRY_MISMATCH"
        )
    return route_by_label


def build_checkpoint8_deterministic_success_fixture_composition():
    """Build the exact marked 20-label C8 registry with zero fallback.

    This slice proves registry/materialization readiness only. Exact response
    semantics are owned by the subsequent execution-entry RED contracts.
    """
    expected = tuple(ordinary_window_15m_builder_identities())
    if len(expected) != 20:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_CANONICAL_COMPOSITION_COUNT_MISMATCH"
        )

    route_by_label = _checkpoint8_route_by_label()
    fixture_by_route: dict[str, _Checkpoint8DeterministicFixture] = {}
    builders: dict[str, Any] = {}

    for label in expected:
        route = route_by_label[label]
        fixture = fixture_by_route.setdefault(
            route,
            _Checkpoint8DeterministicFixture(route),
        )

        def builder(label=label, fixture=fixture):
            return proof.mark_checkpoint8_fixture_output(
                fixture,
                label=label,
            )

        builders[label] = proof.mark_checkpoint8_fixture_builder(
            builder,
            label=label,
        )

    composition = proof.build_window_15m_fixture_composition(builders)
    if composition.provider_fallback_allowed is not False:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_FIXTURE_PROVIDER_FALLBACK_FORBIDDEN"
        )
    return composition


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_preparation_git_head(git_head: str) -> str:
    head = str(git_head or "").strip().lower()
    if len(head) != 40 or any(ch not in "0123456789abcdef" for ch in head):
        raise Checkpoint8ControllingProofError(
            "CONTROLLING_GIT_HEAD_INVALID"
        )
    return head


def _protected_capability_counts(
    connection: sqlite3.Connection,
) -> dict[str, int]:
    existing = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    counts = {
        table: int(
            connection.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]
        )
        for table in _PROTECTED_CAPABILITY_TABLES
        if table in existing
    }
    if not counts:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_PROTECTED_CAPABILITY_TABLES_MISSING"
        )
    return counts


def prepare_checkpoint8_controlling_entry(
    proof_root: str | Path,
    *,
    proof_id: str,
    git_head: str,
):
    """Prepare one fresh, still-unclaimed C8 controlling-proof target."""
    root = Path(proof_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    head = _validate_preparation_git_head(git_head)

    db_path = root / "checkpoint8-controlling-proof.sqlite3"
    artifact_root = root / "checkpoint8-artifacts"
    sentinel = root / _ATTEMPT_SENTINEL_NAME

    if sentinel.exists():
        raise Checkpoint8ControllingProofError(
            "CONTROLLING_ATTEMPT_ALREADY_CONSUMED"
        )
    if db_path.exists() or artifact_root.exists():
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_ENTRY_TARGET_NOT_FRESH"
        )

    artifact_root.mkdir(parents=False, exist_ok=False)
    apply_migrations(db_path)

    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        integrity_check = str(
            connection.execute("PRAGMA integrity_check").fetchone()[0]
        )
        foreign_key_violations = len(
            connection.execute("PRAGMA foreign_key_check").fetchall()
        )
        applied = [
            str(row[0])
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations "
                "ORDER BY rowid"
            ).fetchall()
        ]
        protected_counts = _protected_capability_counts(connection)
    finally:
        connection.close()

    canonical_names = tuple(canonical_migration_names())
    if tuple(applied) != canonical_names:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_MIGRATION_LEDGER_MISMATCH"
        )
    if integrity_check != "ok" or foreign_key_violations != 0:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_DISPOSABLE_DB_INTEGRITY_FAILED"
        )
    if any(protected_counts.values()):
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_PROTECTED_CAPABILITY_BASELINE_NONZERO"
        )

    db_sha256 = _sha256_file(db_path)
    composition = build_checkpoint8_deterministic_success_fixture_composition()
    plan = proof.build_disposable_public_composition_proof_plan(
        proof_id=str(proof_id),
        db_path=db_path,
        db_sha256=db_sha256,
        migration_count=canonical_migration_count(),
        migration_head=canonical_names[-1],
        artifact_root=artifact_root,
        composition_labels=composition.labels,
        provider_execution_allowed=False,
        automatic_retry_allowed=False,
        manual_rerun_allowed=False,
        resume_allowed=False,
        restart_allowed=False,
        successor_allowed=False,
    )
    runtime = proof.build_disposable_public_composition_proof_runtime(
        plan,
        composition,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
    )

    materialized = proof.materialize_disposable_public_composition_execution(
        runtime
    )
    if (
        tuple(materialized.outputs_by_label)
        != tuple(ordinary_window_15m_builder_identities())
        or materialized.provider_fallback_allowed is not False
    ):
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_FIXTURE_MATERIALIZATION_MISMATCH"
        )

    pre_run_evidence = {
        "db_path": str(db_path.resolve()),
        "db_sha256": db_sha256,
        "artifact_root": str(artifact_root.resolve()),
        "migration_count": canonical_migration_count(),
        "migration_head": canonical_names[-1],
        "integrity_check": integrity_check,
        "foreign_key_violations": foreign_key_violations,
        "protected_capability_counts": protected_counts,
        "fixture_composition_manifest_sha256": (
            runtime.fixture_composition_manifest_sha256
        ),
        "composition_registry_sha256": (
            runtime.plan.composition_registry_sha256
        ),
        "git_head": head,
        "network_attempt_count": 0,
    }

    return SimpleNamespace(
        proof_root=root,
        runtime=runtime,
        pre_run_evidence=pre_run_evidence,
    )


def main(argv: list[str] | None = None) -> int:
    del argv
    raise Checkpoint8ControllingProofError(
        "CHECKPOINT8_CONTROLLING_PROOF_ENTRY_NOT_YET_WIRED"
    )


if __name__ == "__main__":
    raise SystemExit(main())

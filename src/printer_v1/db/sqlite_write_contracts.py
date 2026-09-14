"""Operational SQLite write-transaction contracts for Printer V1.

Architectural law (V2-9.8B.20):

* A SQLite write transaction must never remain open across source I/O,
  intentional waits/sleeps, pacing, or lengthy computation.
* Operational write transactions must be short, explicit, and owned by one
  canonical boundary.
* Heartbeat lease renewal must receive a deterministic bounded opportunity to
  obtain ``BEGIN IMMEDIATE``.

These helpers centralize the release and short-write contracts. They do not
loosen Source Governor, Central Scheduler, busy-timeout, or fail-closed lease
renewal rules.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Iterator, Mapping
import uuid


# Align with campaign_supervision bounded busy budget for operational writers
# that must coexist with the heartbeat renewer.
DEFAULT_OPERATIONAL_BUSY_TIMEOUT_MS = 2000
WRITER_ATTRIBUTION_SCHEMA_VERSION = "PRINTER_V1_SQLITE_WRITER_ATTRIBUTION_V1"
DEFAULT_WRITER_ATTRIBUTION_MAX_RECORDS = 256


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_sqlite_error(exc: BaseException) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)[:240]}


class SQLiteWriterAttributionTimeline:
    """Bounded sidecar telemetry for application-owned operational writers.

    This deliberately does not write to SQLite.  A blocked writer cannot be a
    dependency of evidence identifying that block.
    """

    def __init__(
        self,
        artifact_path: str | Path,
        *,
        scope: Mapping[str, object] | None = None,
        max_records: int = DEFAULT_WRITER_ATTRIBUTION_MAX_RECORDS,
    ) -> None:
        if max_records < 16:
            raise ValueError("writer attribution max_records must be at least 16")
        self.artifact_path = Path(artifact_path).resolve()
        self.scope = {
            str(key): value for key, value in dict(scope or {}).items()
            if value is not None
        }
        self.max_records = int(max_records)
        self._records: list[dict[str, Any]] = []
        self._connections: dict[str, dict[str, Any]] = {}
        self._transactions: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def _record(self, event: str, **payload: object) -> dict[str, Any]:
        record = {
            "event": event,
            "at": _utc_now(),
            "monotonic": time.monotonic(),
            "pid": os.getpid(),
            "thread_name": threading.current_thread().name,
            "thread_id": threading.get_ident(),
            **{key: value for key, value in payload.items() if value is not None},
        }
        self._records.append(record)
        if len(self._records) > self.max_records:
            del self._records[: len(self._records) - self.max_records]
        self._persist_best_effort()
        return record

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": WRITER_ATTRIBUTION_SCHEMA_VERSION,
            "scope": dict(self.scope),
            "max_records": self.max_records,
            "records": list(self._records),
            "active_connections": list(self._connections.values()),
            "active_transactions": list(self._transactions.values()),
        }

    def _persist_best_effort(self) -> None:
        """Atomically replace the sidecar; telemetry failure is non-operative."""
        temporary = self.artifact_path.with_name(
            f".{self.artifact_path.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            self.artifact_path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(self._payload(), sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, self.artifact_path)
        except (OSError, TypeError, ValueError):
            # Observability cannot change the existing fail-closed operational
            # behaviour.  The in-memory timeline remains available to the caller.
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def open_connection(
        self,
        connection: sqlite3.Connection,
        *,
        db_path: str | Path,
        connection_role: str,
        context: Mapping[str, object] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            identity = {
                "connection_id": f"sqlite-conn-{uuid.uuid4().hex}",
                "connection_role": str(connection_role),
                "db_path": str(Path(db_path).resolve()),
                "pid": os.getpid(),
                "thread_name": threading.current_thread().name,
                "thread_id": threading.get_ident(),
                "context": dict(context or {}),
                "opened_at": _utc_now(),
                "opened_monotonic": time.monotonic(),
            }
            self._connections[identity["connection_id"]] = identity
            self._record("CONNECTION_OPEN", **identity)
            return dict(identity)

    def set_context(
        self,
        connection_id: str,
        *,
        owner: str | None = None,
        operation: str | None = None,
        context: Mapping[str, object] | None = None,
    ) -> None:
        with self._lock:
            connection = self._connections.get(connection_id)
            if connection is None:
                return
            if owner is not None:
                connection["transaction_owner"] = str(owner)
            if operation is not None:
                connection["transaction_operation"] = str(operation)
            if context:
                connection["context"] = {**connection["context"], **dict(context)}

    def begin_requested(self, connection_id: str) -> dict[str, Any] | None:
        with self._lock:
            connection = self._connections.get(connection_id)
            if connection is None:
                return None
            transaction = {
                "transaction_id": f"sqlite-tx-{uuid.uuid4().hex}",
                "connection_id": connection_id,
                "connection_role": connection["connection_role"],
                "transaction_owner": connection.get("transaction_owner"),
                "transaction_operation": connection.get("transaction_operation"),
                "context": dict(connection["context"]),
                "begin_requested_at": _utc_now(),
                "begin_requested_monotonic": time.monotonic(),
            }
            self._transactions[connection_id] = transaction
            self._record("TRANSACTION_BEGIN_REQUESTED", **transaction)
            return dict(transaction)

    def begin_acquired(self, connection_id: str) -> None:
        with self._lock:
            transaction = self._transactions.get(connection_id)
            if transaction is None:
                return
            transaction["begin_acquired_at"] = _utc_now()
            transaction["begin_acquired_monotonic"] = time.monotonic()
            self._record("TRANSACTION_BEGIN_ACQUIRED", **transaction)

    def begin_failed(self, connection_id: str, exc: BaseException) -> None:
        with self._lock:
            transaction = self._transactions.pop(connection_id, None)
            connection = self._connections.get(connection_id, {})
            self._record(
                "TRANSACTION_BEGIN_FAILED",
                connection_id=connection_id,
                connection_role=connection.get("connection_role"),
                transaction_id=(transaction or {}).get("transaction_id"),
                error=_safe_sqlite_error(exc),
            )

    def terminal(self, connection_id: str, event: str) -> None:
        with self._lock:
            transaction = self._transactions.pop(connection_id, None)
            if transaction is None:
                return
            transaction[f"{event.lower()}_at"] = _utc_now()
            transaction[f"{event.lower()}_monotonic"] = time.monotonic()
            self._record(event, **transaction)

    def close_connection(self, connection_id: str) -> None:
        with self._lock:
            self.terminal(connection_id, "TRANSACTION_ROLLBACK")
            connection = self._connections.pop(connection_id, None)
            if connection is not None:
                self._record("CONNECTION_CLOSE", **connection)

    def contention_attribution(
        self, *, heartbeat_connection_id: str | None, attempt_started_monotonic: float
    ) -> dict[str, Any]:
        """Report only a sole writer that stayed open through the attempt."""
        with self._lock:
            now = time.monotonic()
            candidates = [
                transaction for connection_id, transaction in self._transactions.items()
                if connection_id != heartbeat_connection_id
                and transaction.get("begin_acquired_monotonic") is not None
                and float(transaction["begin_acquired_monotonic"])
                <= attempt_started_monotonic
            ]
            base = {
                "artifact_path": str(self.artifact_path),
                "heartbeat_connection_id": heartbeat_connection_id,
                "attempt_started_monotonic": attempt_started_monotonic,
                "observed_at_monotonic": now,
            }
            if len(candidates) == 1:
                candidate = candidates[0]
                return {
                    **base,
                    "disposition": "PROVEN_APPLICATION_OWNED_OVERLAPPING_WRITER",
                    "connection_id": candidate["connection_id"],
                    "transaction_id": candidate["transaction_id"],
                    "connection_role": candidate["connection_role"],
                    "transaction_owner": candidate.get("transaction_owner"),
                    "transaction_operation": candidate.get("transaction_operation"),
                    "transaction_begin_acquired_at": candidate.get("begin_acquired_at"),
                    "context": dict(candidate["context"]),
                }
            if len(candidates) > 1:
                return {
                    **base,
                    "disposition": "AMBIGUOUS_APPLICATION_OWNED_WRITERS",
                    "candidate_connection_ids": sorted(
                        str(item["connection_id"]) for item in candidates
                    ),
                }
            return {
                **base,
                "disposition": "NO_KNOWN_APPLICATION_OWNED_WRITER",
                "external_or_uninstrumented_writer_possible": True,
            }


_ACTIVE_TIMELINES: dict[str, SQLiteWriterAttributionTimeline] = {}
_CONNECTION_IDENTITIES: dict[int, tuple[SQLiteWriterAttributionTimeline, str]] = {}
_REGISTRY_LOCK = threading.RLock()


def activate_writer_attribution(
    db_path: str | Path,
    *,
    artifact_path: str | Path,
    scope: Mapping[str, object] | None = None,
    max_records: int = DEFAULT_WRITER_ATTRIBUTION_MAX_RECORDS,
) -> SQLiteWriterAttributionTimeline:
    timeline = SQLiteWriterAttributionTimeline(
        artifact_path, scope=scope, max_records=max_records
    )
    with _REGISTRY_LOCK:
        _ACTIVE_TIMELINES[str(Path(db_path).resolve())] = timeline
    return timeline


def active_writer_attribution(
    db_path: str | Path,
) -> SQLiteWriterAttributionTimeline | None:
    with _REGISTRY_LOCK:
        return _ACTIVE_TIMELINES.get(str(Path(db_path).resolve()))


def deactivate_writer_attribution(db_path: str | Path) -> None:
    with _REGISTRY_LOCK:
        _ACTIVE_TIMELINES.pop(str(Path(db_path).resolve()), None)


def _identity_for(connection: sqlite3.Connection) -> tuple[SQLiteWriterAttributionTimeline, str] | None:
    with _REGISTRY_LOCK:
        return _CONNECTION_IDENTITIES.get(id(connection))


class _AttributedSQLiteConnection(sqlite3.Connection):
    """Connection subclass that observes canonical SQLite transaction calls."""

    def execute(self, sql: str, parameters: object = (), /):  # type: ignore[override]
        identity = _identity_for(self)
        statement = str(sql).lstrip().upper()
        is_begin = statement.startswith("BEGIN")
        is_write = statement.startswith((
            "INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER",
        ))
        before = self.in_transaction
        if identity is not None and is_begin:
            identity[0].begin_requested(identity[1])
        try:
            result = super().execute(sql, parameters)
        except sqlite3.Error as exc:
            if identity is not None and is_begin:
                identity[0].begin_failed(identity[1], exc)
            raise
        if identity is not None and self.in_transaction and (is_begin or (is_write and not before)):
            timeline, connection_id = identity
            if connection_id not in timeline._transactions:
                timeline.begin_requested(connection_id)
            timeline.begin_acquired(connection_id)
        return result

    def commit(self) -> None:  # type: ignore[override]
        identity = _identity_for(self)
        try:
            super().commit()
        finally:
            if identity is not None:
                identity[0].terminal(identity[1], "TRANSACTION_COMMIT")

    def rollback(self) -> None:  # type: ignore[override]
        identity = _identity_for(self)
        try:
            super().rollback()
        finally:
            if identity is not None:
                identity[0].terminal(identity[1], "TRANSACTION_ROLLBACK")

    def close(self) -> None:  # type: ignore[override]
        identity = _identity_for(self)
        try:
            super().close()
        finally:
            if identity is not None:
                identity[0].close_connection(identity[1])
                with _REGISTRY_LOCK:
                    _CONNECTION_IDENTITIES.pop(id(self), None)


def connect_attributed(
    db_path: str | Path,
    *,
    timeline: SQLiteWriterAttributionTimeline | None = None,
    connection_role: str,
    context: Mapping[str, object] | None = None,
    timeout: float = 5.0,
    uri: bool = False,
    **connect_kwargs: object,
) -> sqlite3.Connection:
    """Open an operational connection and register a UUID identity when active."""
    path = Path(db_path).resolve()
    active = timeline or active_writer_attribution(path)
    if active is None:
        return sqlite3.connect(path, timeout=timeout, uri=uri, **connect_kwargs)
    connection = sqlite3.connect(
        path, timeout=timeout, uri=uri, factory=_AttributedSQLiteConnection, **connect_kwargs
    )
    identity = active.open_connection(
        connection, db_path=path, connection_role=connection_role, context=context
    )
    with _REGISTRY_LOCK:
        _CONNECTION_IDENTITIES[id(connection)] = (active, str(identity["connection_id"]))
    return connection


def set_writer_attribution_context(
    connection: sqlite3.Connection,
    *,
    owner: str | None = None,
    operation: str | None = None,
    context: Mapping[str, object] | None = None,
) -> None:
    identity = _identity_for(connection)
    if identity is not None:
        identity[0].set_context(identity[1], owner=owner, operation=operation, context=context)


def writer_attribution_connection_id(connection: sqlite3.Connection) -> str | None:
    identity = _identity_for(connection)
    return None if identity is None else identity[1]


def begin_attributed_write(
    connection: sqlite3.Connection,
    *,
    owner: str,
    operation: str,
    context: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    set_writer_attribution_context(
        connection, owner=owner, operation=operation, context=context
    )
    connection.execute("BEGIN IMMEDIATE")
    identity = _identity_for(connection)
    if identity is None:
        return {"connection_id": None, "transaction_id": None}
    transaction = identity[0]._transactions.get(identity[1])
    return dict(transaction or {"connection_id": identity[1], "transaction_id": None})


def commit_attributed_write(connection: sqlite3.Connection) -> None:
    connection.commit()


def rollback_attributed_write(connection: sqlite3.Connection) -> None:
    connection.rollback()


def is_sqlite_connection(value: object) -> bool:
    return isinstance(value, sqlite3.Connection)


def release_write_transaction(db_path_or_conn: object) -> bool:
    """Commit any open write transaction on a shared connection.

    Path-based callers already own short autocommiting scopes and are no-ops.
    Returns True only when an open connection transaction was committed.
    """
    if not isinstance(db_path_or_conn, sqlite3.Connection):
        return False
    if not db_path_or_conn.in_transaction:
        return False
    commit_attributed_write(db_path_or_conn)
    return True


def configure_operational_connection(
    connection: sqlite3.Connection,
    *,
    busy_timeout_ms: int = DEFAULT_OPERATIONAL_BUSY_TIMEOUT_MS,
    foreign_keys: bool = True,
) -> sqlite3.Connection:
    """Apply the shared operational connection contract."""
    if foreign_keys:
        connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
    return connection


def connect_operational(
    db_path: str | Path,
    *,
    busy_timeout_ms: int = DEFAULT_OPERATIONAL_BUSY_TIMEOUT_MS,
    row_factory: bool = True,
) -> sqlite3.Connection:
    """Open a writer connection with the shared operational PRAGMA contract."""
    connection = connect_attributed(
        db_path,
        connection_role="OPERATIONAL_SHARED",
    )
    if row_factory:
        connection.row_factory = sqlite3.Row
    return configure_operational_connection(
        connection, busy_timeout_ms=busy_timeout_ms
    )


@contextmanager
def short_write_transaction(
    connection: sqlite3.Connection,
) -> Iterator[sqlite3.Connection]:
    """Begin IMMEDIATE, yield, commit on success, rollback on error.

    Callers must not perform source I/O, sleeps, or long computation inside this
    boundary.
    """
    begin_attributed_write(
        connection,
        owner="short_write_transaction",
        operation="SHORT_WRITE_TRANSACTION",
    )
    try:
        yield connection
        commit_attributed_write(connection)
    except Exception:
        if connection.in_transaction:
            rollback_attributed_write(connection)
        raise

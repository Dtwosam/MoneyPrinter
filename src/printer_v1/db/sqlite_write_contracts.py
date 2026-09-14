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
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Iterator, Mapping
import uuid
import weakref
from urllib.parse import unquote, urlsplit


# Align with campaign_supervision bounded busy budget for operational writers
# that must coexist with the heartbeat renewer.
DEFAULT_OPERATIONAL_BUSY_TIMEOUT_MS = 2000
WRITER_ATTRIBUTION_SCHEMA_VERSION = "PRINTER_V1_SQLITE_WRITER_ATTRIBUTION_V2"
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
        self._result_cursors: dict[str, dict[str, Any]] = {}
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
            "active_transactions": deepcopy(list(self._transactions.values())),
            "open_result_cursors": deepcopy(list(self._result_cursors.values())),
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
                "context": deepcopy(dict(context or {})),
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

    def begin_requested(self, connection_id: str, kind: str = "UNKNOWN") -> dict[str, Any] | None:
        with self._lock:
            connection = self._connections.get(connection_id)
            if connection is None:
                return None
            transaction = {
                "transaction_id": f"sqlite-tx-{uuid.uuid4().hex}",
                "transaction_kind": kind,
                "connection_id": connection_id,
                "connection_role": connection["connection_role"],
                "transaction_owner": connection.get("transaction_owner"),
                "transaction_operation": connection.get("transaction_operation"),
                "context": deepcopy(connection["context"]),
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
            self.terminal(connection_id, "TRANSACTION_CLOSE_ROLLBACK_SUCCEEDED")
            for cursor_id, cursor in list(self._result_cursors.items()):
                if cursor["connection_id"] == connection_id:
                    self.end_cursor(cursor_id)
            connection = self._connections.pop(connection_id, None)
            if connection is not None:
                self._record("CONNECTION_CLOSE", **connection)

    def open_cursor(self, connection_id: str, kind: str) -> str:
        with self._lock:
            cursor_id = f"sqlite-cursor-{uuid.uuid4().hex}"
            connection = self._connections[connection_id]
            self._result_cursors[cursor_id] = {
                **deepcopy(connection), "cursor_id": cursor_id,
                "transaction_kind": kind, "activity_scope": "OPEN_RESULT_CURSOR",
                "lock_held_proven": False,
            }
            self._record("RESULT_CURSOR_OPEN", **self._result_cursors[cursor_id])
            return cursor_id

    def end_cursor(self, cursor_id: str) -> None:
        with self._lock:
            cursor = self._result_cursors.pop(cursor_id, None)
            if cursor:
                self._record("RESULT_CURSOR_RELEASED", **cursor)

    def activity(self, connection_id: str, event: str, **details: object) -> None:
        with self._lock:
            self._record(event, **deepcopy(self._transactions.get(connection_id, {
                "connection_id": connection_id,
            })), **details)

    def classify(self, connection_id: str, kind: str) -> None:
        with self._lock:
            transaction = self._transactions.get(connection_id)
            if transaction is not None and kind != "UNKNOWN":
                if kind == "READ" and transaction.get("unclassified_activity"):
                    return
                if transaction["transaction_kind"] != "WRITE":
                    transaction["transaction_kind"] = kind
                    self.activity(connection_id, "TRANSACTION_KIND_OBSERVED")

    def mark_unknown(self, connection_id: str) -> None:
        with self._lock:
            transaction = self._transactions.get(connection_id)
            if transaction is not None and transaction["transaction_kind"] != "WRITE":
                transaction["transaction_kind"] = "UNKNOWN"
                transaction["unclassified_activity"] = True
                self.activity(connection_id, "TRANSACTION_KIND_UNCERTAIN")

    def contention_attribution(
        self, *, heartbeat_connection_id: str | None, attempt_started_monotonic: float
    ) -> dict[str, Any]:
        """Prove current overlap, never causation or absence of external locks.

        Include transactions acquired during the attempt too. A candidate must
        still be active at observation; a request alone is not an acquisition.
        """
        with self._lock:
            candidates = deepcopy([
                transaction for connection_id, transaction in self._transactions.items()
                if connection_id != heartbeat_connection_id
                and transaction.get("begin_acquired_monotonic") is not None
            ])
            transaction_connections = {item["connection_id"] for item in candidates}
            candidates.extend(deepcopy([
                cursor for cursor in self._result_cursors.values()
                if cursor["connection_id"] != heartbeat_connection_id
                and cursor["connection_id"] not in transaction_connections
            ]))
            kinds = {item["transaction_kind"] for item in candidates}
            if not candidates:
                disposition = "NO_KNOWN_APPLICATION_OWNED_WRITER"
            elif kinds == {"WRITE"}:
                disposition = ("PROVEN_APPLICATION_OWNED_OVERLAPPING_WRITER" if len(candidates) == 1
                               else "AMBIGUOUS_APPLICATION_OWNED_WRITERS")
            elif kinds == {"READ"}:
                disposition = ("PROVEN_APPLICATION_OWNED_OVERLAPPING_READER" if len(candidates) == 1
                               else "AMBIGUOUS_APPLICATION_OWNED_READERS")
            elif kinds == {"READ", "WRITE"}:
                disposition = "MIXED_APPLICATION_OWNED_READERS_AND_WRITERS"
            else:
                disposition = "UNKNOWN_APPLICATION_OWNED_TRANSACTIONS"
            result = {
                "artifact_path": str(self.artifact_path),
                "heartbeat_connection_id": heartbeat_connection_id,
                "attempt_started_monotonic": attempt_started_monotonic,
                "observed_at_monotonic": time.monotonic(),
                "disposition": disposition,
                "causal_blocker_proven": False,
                "external_or_uninstrumented_blocker_possible": True,
                "external_or_uninstrumented_writer_possible": True,
                "candidates": candidates,
                "candidate_connection_ids": sorted(item["connection_id"] for item in candidates),
            }
            if len(candidates) == 1:
                result.update(candidates[0])
                result["transaction_begin_acquired_at"] = candidates[0].get("begin_acquired_at")
            return result


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


# Tokenize comments, quoted values/identifiers and parentheses before looking
# for a top-level CTE operation. Never inspect bound parameter values.
_SQL_TOKENS = re.compile(
    r"--[^\n]*(?:\n|$)|/\*.*?\*/|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|"
    r"`(?:``|[^`])*`|\[[^\]]*\]|[A-Za-z_][A-Za-z_0-9]*|[()]|[^\s]",
    re.DOTALL,
)


def _statement_kind(sql: str) -> tuple[str, str]:
    tokens = [m.group().upper() for m in _SQL_TOKENS.finditer(sql)
              if not m.group().startswith(("--", "/*"))]
    if not tokens:
        return "OTHER", "UNKNOWN"
    first = tokens[0]
    if first == "WITH":
        depth = 0
        for token in tokens[1:]:
            if token == "(":
                depth += 1
            elif token == ")":
                depth -= 1
            elif depth == 0 and token in {"SELECT", "INSERT", "UPDATE", "DELETE", "REPLACE"}:
                first = token
                break
    if first == "BEGIN":
        return "BEGIN", "WRITE" if any(t in {"IMMEDIATE", "EXCLUSIVE"} for t in tokens[1:]) else "UNKNOWN"
    if first in {"COMMIT", "END"}:
        return "COMMIT", "UNKNOWN"
    if first == "ROLLBACK":
        return ("ROLLBACK_TO" if "TO" in tokens[1:3] else "ROLLBACK"), "UNKNOWN"
    if first in {"SAVEPOINT", "RELEASE"}:
        return first, "UNKNOWN"
    if first in {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER", "REINDEX", "ANALYZE"}:
        return "STATEMENT", "WRITE"
    if first == "SELECT":
        return "STATEMENT", "READ"
    return "OTHER", "UNKNOWN"


class _AttributedSQLiteCursor(sqlite3.Cursor):
    _result_finalizer = None

    def _release_result(self):
        if self._result_finalizer is not None:
            self._result_finalizer()
            self._result_finalizer = None

    def execute(self, sql, parameters=(), /):
        self._release_result()
        result = self.connection._observe_call(super().execute, sql, parameters)
        identity = _identity_for(self.connection)
        if self.description is not None and identity is not None:
            timeline, cid = identity
            cursor_id = timeline.open_cursor(cid, _statement_kind(sql)[1])
            self._result_finalizer = weakref.finalize(self, timeline.end_cursor, cursor_id)
        return result

    def executemany(self, sql, parameters, /):
        self._release_result()
        return self.connection._observe_call(super().executemany, sql, parameters)

    def executescript(self, sql, /):
        return self.connection._observe_call(super().executescript, sql)

    def fetchone(self):
        row = super().fetchone()
        if row is None:
            self._release_result()
        return row

    def fetchmany(self, size=None):
        rows = super().fetchmany() if size is None else super().fetchmany(size)
        if not rows:
            self._release_result()
        return rows

    def fetchall(self):
        rows = super().fetchall()
        self._release_result()
        return rows

    def __next__(self):
        try:
            return super().__next__()
        except StopIteration:
            self._release_result()
            raise

    def close(self):
        super().close()
        self._release_result()


class _AttributedSQLiteConnection(sqlite3.Connection):
    """Observe native SQLite execution without rewriting SQL or transactions.

    The local trace hook sees implicit BEGIN, each executescript statement and
    context-manager terminals. API return/error and in_transaction
    reconcile the last traced statement. SQL text/values are never persisted.
    """

    _pending = None
    _pending_sql = None
    _user_trace = None
    _last_contention = None

    def _trace(self, sql):
        # SQLite repeats the outer SQL for trigger entry/body trace events.
        # Such a trace is not evidence that the preceding statement finished.
        if self._pending is not None and sql == self._pending_sql:
            if self._user_trace is not None:
                self._user_trace(sql)
            return
        self._finish_statement()
        self._pending_sql = sql
        identity = _identity_for(self)
        if identity is None:
            return
        timeline, cid = identity
        operation, kind = _statement_kind(sql)
        before = self.in_transaction
        self._pending = (operation, kind, before)
        if operation in {"BEGIN", "SAVEPOINT"} and not before:
            timeline.begin_requested(cid)
        if operation in {"COMMIT", "ROLLBACK"}:
            timeline.activity(cid, f"TRANSACTION_{operation}_REQUESTED")
        elif operation in {"SAVEPOINT", "RELEASE", "ROLLBACK_TO"}:
            timeline.activity(cid, f"SAVEPOINT_{operation}_REQUESTED")
        if self._user_trace is not None:
            self._user_trace(sql)

    def _finish_statement(self, error=None):
        pending, self._pending = self._pending, None
        identity = _identity_for(self)
        if pending is None or identity is None:
            return
        operation, kind, before = pending
        timeline, cid = identity
        after = self.in_transaction
        suffix = "FAILED" if error is not None else "SUCCEEDED"
        details = {"error": _safe_sqlite_error(error)} if error is not None else {}
        if operation in {"BEGIN", "SAVEPOINT"} and not before:
            if after:
                timeline.begin_acquired(cid)
            else:
                timeline.begin_failed(cid, error or RuntimeError("SQLite did not enter transaction"))
        if after and cid not in timeline._transactions:
            timeline.begin_requested(cid)
            timeline.begin_acquired(cid)
        if operation == "OTHER" or (kind == "WRITE" and error is not None):
            timeline.mark_unknown(cid)
        elif error is None:
            timeline.classify(cid, kind)
        if operation in {"COMMIT", "ROLLBACK"}:
            # A terminal request with a still-open SQLite transaction has
            # failed; it must never remove the active transaction.
            if after:
                timeline.activity(cid, f"TRANSACTION_{operation}_FAILED", **details)
            elif error is None:
                timeline.terminal(cid, f"TRANSACTION_{operation}_SUCCEEDED")
            else:
                # A script can finish COMMIT and then fail preparing its next
                # statement (which has no trace). Do not invent its outcome.
                timeline.activity(cid, f"TRANSACTION_{operation}_OUTCOME_UNKNOWN", **details)
        if operation in {"SAVEPOINT", "RELEASE", "ROLLBACK_TO"}:
            timeline.activity(cid, f"SAVEPOINT_{operation}_{suffix}", **details)
        if not after and cid in timeline._transactions:
            timeline.terminal(cid, "TRANSACTION_RELEASE_SUCCEEDED" if operation == "RELEASE" and error is None
                              else "TRANSACTION_SQLITE_ENDED")
        if not before and not after and operation == "STATEMENT":
            timeline.activity(cid, f"STATEMENT_EXECUTION_{suffix}", statement_kind=kind, **details)

    def _observe_call(self, call, *args):
        started = time.monotonic()
        try:
            result = call(*args)
        except BaseException as exc:
            identity = _identity_for(self)
            code = getattr(exc, "sqlite_errorcode", 0) or 0
            if identity is not None and code & 0xFF in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                timeline, cid = identity
                observation = timeline.contention_attribution(
                    heartbeat_connection_id=cid, attempt_started_monotonic=started,
                )
                observation["failure_phase"] = self._pending[0] if self._pending else "UNKNOWN"
                observation["heartbeat_in_transaction"] = self.in_transaction
                self._last_contention = observation
                timeline.activity(cid, "SQLITE_CONTENTION_OBSERVED", attribution=observation)
            self._finish_statement(exc)
            raise
        self._finish_statement()
        return result

    def set_trace_callback(self, callback):
        self._user_trace = callback
        super().set_trace_callback(self._trace)

    def cursor(self, factory=None):
        # Custom cursor factories are intentionally not replaced. Trace still
        # sees their SQL; last-statement reconciliation requires our cursor.
        return super().cursor(factory or _AttributedSQLiteCursor)

    def execute(self, sql, parameters=(), /):
        return self.cursor().execute(sql, parameters)

    def executemany(self, sql, parameters, /):
        return self.cursor().executemany(sql, parameters)

    def executescript(self, sql, /):
        return self.cursor().executescript(sql)

    def commit(self):
        return self._observe_call(super().commit)

    def rollback(self):
        return self._observe_call(super().rollback)

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            try:
                self.commit()
            except BaseException:
                self.rollback()
                raise
        else:
            self.rollback()
        return False

    def close(self):
        identity = _identity_for(self)
        self._observe_call(super().close)
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
    # Preserve URI mode/query flags while resolving the registry's DB identity.
    target = str(db_path) if uri else Path(db_path).resolve()
    path = Path(unquote(urlsplit(str(db_path)).path)).resolve() if uri else target
    active = timeline or active_writer_attribution(path)
    if active is None:
        return sqlite3.connect(target, timeout=timeout, uri=uri, **connect_kwargs)
    connection = sqlite3.connect(
        target, timeout=timeout, uri=uri, factory=_AttributedSQLiteConnection, **connect_kwargs
    )
    identity = active.open_connection(
        connection, db_path=path, connection_role=connection_role, context=context
    )
    with _REGISTRY_LOCK:
        _CONNECTION_IDENTITIES[id(connection)] = (active, str(identity["connection_id"]))
    connection.set_trace_callback(None)
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


def writer_attribution_last_contention(connection: sqlite3.Connection) -> dict[str, Any] | None:
    """Snapshot captured at the SQLite exception, before retry or rollback."""
    return deepcopy(getattr(connection, "_last_contention", None))


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

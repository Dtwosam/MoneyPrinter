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
from pathlib import Path
import sqlite3
from typing import Iterator


# Align with campaign_supervision bounded busy budget for operational writers
# that must coexist with the heartbeat renewer.
DEFAULT_OPERATIONAL_BUSY_TIMEOUT_MS = 2000


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
    db_path_or_conn.commit()
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
    connection = sqlite3.connect(Path(db_path))
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
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
        connection.commit()
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise

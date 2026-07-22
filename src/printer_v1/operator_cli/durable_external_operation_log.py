"""Durable, secret-free timing evidence for external Pump RPC operations."""

from __future__ import annotations

from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path
import sqlite3
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DurablePumpRpcTransport:
    """Record each delegated call exactly once; never retry or reconnect."""

    def __init__(
        self,
        delegate: Any,
        *,
        db_path: str | Path,
        run_id: str,
        cycle_id: str,
        redacted_host: str = "api.mainnet-beta.solana.com",
    ) -> None:
        self._delegate = delegate
        self._db_path = Path(db_path)
        self._run_id = run_id
        self._cycle_id = cycle_id
        self._redacted_host = redacted_host

    def json_rpc(
        self,
        method: str,
        params: list[Any],
        *,
        timeout_seconds: float,
        byte_ceiling: int,
    ) -> Any:
        commitment = None
        for value in params:
            if isinstance(value, dict) and value.get("commitment"):
                commitment = str(value["commitment"])
        started_at = _utc_now()
        with closing(sqlite3.connect(self._db_path)) as connection, connection:
            connection.execute("PRAGMA foreign_keys=ON")
            ordinal = int(connection.execute(
                "SELECT COALESCE(MAX(operation_ordinal),0)+1 "
                "FROM printer_external_source_operations WHERE run_id=? AND cycle_id=?",
                (self._run_id, self._cycle_id),
            ).fetchone()[0])
            cursor = connection.execute(
                """INSERT INTO printer_external_source_operations(
                    run_id,cycle_id,operation_ordinal,source_name,request_purpose,
                    endpoint_role,redacted_host,rpc_method,commitment,started_at,
                    operation_state,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,'STARTED',?,?)""",
                (
                    self._run_id, self._cycle_id, ordinal, "solana_rpc",
                    "pumpfun_finalized_origin_acquisition", "PRIMARY",
                    self._redacted_host, method, commitment, started_at,
                    started_at, started_at,
                ),
            )
            operation_id = int(cursor.lastrowid)
        try:
            result = self._delegate.json_rpc(
                method, params,
                timeout_seconds=timeout_seconds,
                byte_ceiling=byte_ceiling,
            )
        except Exception as exc:
            finished_at = _utc_now()
            subtype = str(getattr(exc, "code", None) or type(exc).__name__)
            with closing(sqlite3.connect(self._db_path)) as connection, connection:
                connection.execute(
                    """UPDATE printer_external_source_operations
                       SET finished_at=?,operation_state='FAILED',failure_subtype=?,updated_at=?
                       WHERE operation_id=?""",
                    (finished_at, subtype, finished_at, operation_id),
                )
            raise
        finished_at = _utc_now()
        with closing(sqlite3.connect(self._db_path)) as connection, connection:
            connection.execute(
                """UPDATE printer_external_source_operations
                   SET finished_at=?,operation_state='COMPLETE',updated_at=?
                   WHERE operation_id=?""",
                (finished_at, finished_at, operation_id),
            )
        return result

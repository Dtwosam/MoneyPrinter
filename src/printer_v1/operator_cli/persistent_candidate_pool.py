"""V2-9.7E.40 discovery-only persistent candidate pool.

Reuses the durable ``printer_pumpfun_finalized_origin_registry`` (the adopted
prospective-origin persistence owner) as a bounded, mixed-age staged candidate
pool so the full pilot can reach two categorically mature candidates without a
new provider, a paid API, a source-budget increase, a hidden retry, or a source
substitution.

Pool state is discovery/source state ONLY: confirmed Pump origin identity,
origin time and provenance. It never holds, and this module never reads or
writes, pilot authorizations, campaign/run/cycle identities, Scheduler jobs,
lifecycle state, memory rows, retrieval/decision state, terminal causes, or
report results.

Flow (maturity waiting happens OUTSIDE FULL_PILOT, through real wall clock and
Scheduler-owned categorical states):

    bounded governed Pump acquisition cycles
    -> durable confirmed-origin pool (this module, one DB, existing registry)
    -> categorical 900s maturity (evaluate_snapshot_maturity)
    -> mixed-age available pool
    -> bounded immutable DUE candidate export
    -> copy only DUE candidate facts into a fresh isolated FULL_PILOT attempt DB
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping

from printer_v1.scheduler.snapshot_maturity import SNAPSHOT_MATURITY_SECONDS
from printer_v1.sources.pumpfun_origin import (
    OriginRegistryError,
    export_due_confirmed_origins,
    import_confirmed_origin_row,
    record_confirmed_origin,
)


class CandidatePoolError(RuntimeError):
    """Fail-closed discovery-pool fault."""


def _epoch(evaluated_at: str | datetime) -> int:
    if isinstance(evaluated_at, datetime):
        dt = evaluated_at
    else:
        dt = datetime.fromisoformat(str(evaluated_at).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _connect(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def record_acquisition_into_pool(
    pool_db: str | Path, acquisition: Any, *, now: str
) -> int:
    """Record every confirmed origin from one bounded acquisition into the pool.

    Discovery-only: writes solely the durable finalized-origin registry. Returns
    the count of newly staged origins. Confirmed-origin conflicts never raise;
    the conflicting candidate is simply not restaged.
    """
    connection = _connect(pool_db)
    staged = 0
    try:
        for observation in acquisition.result.observations:
            try:
                if record_confirmed_origin(connection, observation, now=now):
                    staged += 1
            except OriginRegistryError:
                pass
        connection.commit()
    finally:
        connection.close()
    return staged


def pool_maturity_state(
    pool_db: str | Path,
    *,
    evaluated_at: str | datetime,
    maturity_seconds: int = SNAPSHOT_MATURITY_SECONDS,
) -> dict[str, Any]:
    """Categorical maturity summary of the pool at ``evaluated_at`` (zero source).

    ``due`` is the count of confirmed origins whose Scheduler-owned categorical
    boundary (``block_time + maturity_seconds``) has been reached.
    """
    epoch = _epoch(evaluated_at)
    connection = _connect(pool_db)
    try:
        rows = connection.execute(
            "SELECT mint_identity, block_time FROM "
            "printer_pumpfun_finalized_origin_registry "
            "WHERE origin_state='PUMPFUN_ORIGIN_CONFIRMED'"
        ).fetchall()
    finally:
        connection.close()
    due_mints = sorted(
        str(r["mint_identity"])
        for r in rows
        if epoch >= int(r["block_time"]) + int(maturity_seconds)
    )
    return {
        "total": len(rows),
        "due": len(due_mints),
        "immature": len(rows) - len(due_mints),
        "evaluated_epoch": epoch,
        "due_mints": due_mints,
    }


def seed_attempt_from_pool(
    pool_db: str | Path,
    attempt_db: str | Path,
    *,
    evaluated_at: str | datetime,
    maturity_seconds: int = SNAPSHOT_MATURITY_SECONDS,
    exclude_mints: Iterable[str] = (),
) -> dict[str, Any]:
    """Copy only DUE candidate facts from the pool into a fresh attempt DB.

    Builds a bounded immutable DUE candidate export from the pool and imports it
    verbatim into the fresh isolated attempt's discovery registry. No campaign,
    run, cycle, scheduler, lifecycle, memory or report state is read or written;
    the persistent pool DB is never cloned as operational state.
    """
    epoch = _epoch(evaluated_at)
    source = _connect(pool_db)
    try:
        export = export_due_confirmed_origins(
            source,
            evaluated_epoch=epoch,
            maturity_seconds=maturity_seconds,
            exclude_mints=exclude_mints,
        )
    finally:
        source.close()
    destination = _connect(attempt_db)
    copied = 0
    try:
        for row in export:
            if import_confirmed_origin_row(destination, row):
                copied += 1
        destination.commit()
    finally:
        destination.close()
    return {
        "exported": len(export),
        "copied": copied,
        "mints": [str(row["mint_identity"]) for row in export],
    }

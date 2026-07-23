"""V2-9.7E.40/.41 persistent candidate pool (pending discovery + graduated).

Reuses the durable ``printer_pumpfun_finalized_origin_registry`` (the adopted
prospective-origin persistence owner) as a bounded pending-discovery pool.

V2-9.7E.41 graduation-only law separates the pool's two roles:

* **Pending discovery population** — confirmed Pump origin identity, origin time
  and provenance for bonding-curve / unpaired launches. It is retained as
  discovery evidence and is **never** exported as a selectable pilot candidate.
  Age is discovery context, not eligibility. The former "maturity" helpers are
  renamed to reflect this (``pool_pending_discovery_state``,
  ``seed_pending_discovery_from_pool``); the old ``pool_maturity_state`` /
  ``seed_attempt_from_pool`` names are kept as deprecated aliases for historical
  callers and carry no eligibility meaning.
* **Graduated candidate population** — a candidate is exported to a fresh pilot
  only when exact PumpSwap graduation and market identity are confirmed
  (``export_graduated_pilot_candidates``). The bare origin registry stores only
  pre-graduation origins, so this export is empty until a graduation-evidence
  owner supplies confirmed graduations — the honest current state.

Pool state is discovery/source state ONLY. It never holds, and this module never
reads or writes, pilot authorizations, campaign/run/cycle identities, Scheduler
jobs, lifecycle state, memory rows, retrieval/decision state, terminal causes, or
report results.
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
from printer_v1.sources.pumpswap_graduated_registry import (
    export_graduated_candidates,
    graduated_registry_exists,
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


def pool_pending_discovery_state(
    pool_db: str | Path,
    *,
    evaluated_at: str | datetime,
    maturity_seconds: int = SNAPSHOT_MATURITY_SECONDS,
) -> dict[str, Any]:
    """Pending-discovery age summary of the pool at ``evaluated_at`` (zero source).

    ``due`` is the count of confirmed origins whose age boundary
    (``block_time + maturity_seconds``) has been reached. V2-9.7E.41: age is
    discovery context only and is NEVER selection eligibility — these are
    bonding-curve / unpaired origins, not graduated candidates.
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


def seed_pending_discovery_from_pool(
    pool_db: str | Path,
    attempt_db: str | Path,
    *,
    evaluated_at: str | datetime,
    maturity_seconds: int = SNAPSHOT_MATURITY_SECONDS,
    exclude_mints: Iterable[str] = (),
) -> dict[str, Any]:
    """Copy PENDING-DISCOVERY origin facts from the pool into a fresh attempt DB.

    V2-9.7E.41: this seeds pending discovery evidence only (confirmed Pump origin
    identity, signature/block time and provenance). It is explicitly NOT a
    selectable-candidate export — these origins are bonding-curve / unpaired and
    the graduation-only law forbids selecting them. Use
    ``export_graduated_pilot_candidates`` for selectable pilot candidates. No
    campaign, run, cycle, scheduler, lifecycle, memory or report state is read or
    written; the persistent pool DB is never cloned as operational state.
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
        "population": "PENDING_DISCOVERY_NOT_SELECTABLE",
    }


def export_graduated_pilot_candidates(
    pool_db: str | Path,
    *,
    exclude_market_identities: Iterable[str] = (),
) -> dict[str, Any]:
    """Export only graduation-confirmed candidates for a fresh pilot (fail-closed).

    V2-9.7E.41 graduation-only law: a candidate is exported to a pilot only when
    exact PumpSwap graduation and one valid post-graduation market identity are
    confirmed, deduplicated by exact token and market identity. Bonding-curve /
    unpaired origins are excluded. The bare
    ``printer_pumpfun_finalized_origin_registry`` stores only pre-graduation
    origins and carries no graduation/market-identity evidence, so this export is
    empty until a graduation-evidence owner persists confirmed graduations. This
    is the honest current state, not a defect.
    """
    excluded = {str(m) for m in exclude_market_identities}
    connection = _connect(pool_db)
    try:
        total_origins = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_pumpfun_finalized_origin_registry "
                "WHERE origin_state='PUMPFUN_ORIGIN_CONFIRMED'"
            ).fetchone()[0]
        )
        # V2-9.7E.42: the durable graduated-candidate registry (migration 040) is
        # the graduation-evidence owner. When present, export its confirmed
        # graduated candidates (deduplicated by exact mint / market identity). When
        # absent or empty, keep the honest empty result — the origin registry stores
        # only pre-graduation origins and carries no graduation evidence.
        graduated: list[Mapping[str, Any]] = []
        if graduated_registry_exists(connection):
            graduated = [
                dict(row)
                for row in export_graduated_candidates(
                    connection, exclude_market_identities=excluded
                )
            ]
    finally:
        connection.close()
    if not graduated:
        return {
            "graduated_candidates": [],
            "exported": 0,
            "pending_discovery_origins": total_origins,
            "reason": "NO_PERSISTED_GRADUATION_EVIDENCE",
            "population": "GRADUATED_ONLY",
        }
    return {
        "graduated_candidates": graduated,
        "exported": len(graduated),
        "pending_discovery_origins": total_origins,
        "reason": "GRADUATED_EVIDENCE_EXPORTED",
        "population": "GRADUATED_ONLY",
    }


# Deprecated V2-9.7E.40 aliases. The names imply age eligibility, which the
# V2-9.7E.41 graduation-only law removed. They forward to the pending-discovery
# helpers and carry no selection-eligibility meaning.
def pool_maturity_state(pool_db: str | Path, **kwargs: Any) -> dict[str, Any]:
    return pool_pending_discovery_state(pool_db, **kwargs)


def seed_attempt_from_pool(
    pool_db: str | Path, attempt_db: str | Path, **kwargs: Any
) -> dict[str, Any]:
    return seed_pending_discovery_from_pool(pool_db, attempt_db, **kwargs)

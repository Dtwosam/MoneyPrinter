"""One-time V2-9.8A historical Scheduler residue reconciliation.

The repair is deliberately narrower than a general cleanup command. It accepts
one immutable set of audited job IDs, re-proves that every row is unlocked and
unlinked, creates a verified backup/restore rehearsal, and then uses the
Central Scheduler's existing ``cancel_job`` transition in one transaction.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from printer_v1.operator_cli.operational_backup_restore_preflight import (
    operational_backup_restore_preflight,
)
from printer_v1.scheduler.scheduler import cancel_job


AUDITED_JOB_IDS = (8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 738, 980, 981, 982)
EXPECTED_PRE_REPAIR_SHA256 = (
    "985e44b136bf599b6a864874cdb2c0f10b61dbcd476271c2ba2d39680ce6b9f3"
)
ALLOWED_CHANGED_FIELDS = frozenset({"status", "finished_at", "updated_at"})
PROTECTED_FIELDS = (
    "id", "job_name", "job_kind", "target_table", "target_id", "priority",
    "scheduled_for", "started_at", "locked_at", "lock_owner", "retry_count",
    "last_error", "created_at",
)


class SchedulerResidueReconciliationError(RuntimeError):
    """Fail-closed scheduler reconciliation fault."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _exact_ids(job_ids: Iterable[int]) -> tuple[int, ...]:
    values = tuple(int(value) for value in job_ids)
    if values != AUDITED_JOB_IDS:
        raise SchedulerResidueReconciliationError(
            "job IDs must exactly match the audited ordered set"
        )
    return values


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _ownership_links(connection: sqlite3.Connection, job_id: int) -> dict[str, int]:
    links: dict[str, int] = {}
    for table in (
        "printer_discovery_work",
        "printer_memory_factory_campaign_scheduler_work",
        "printer_memory_factory_run_steps",
    ):
        if not _table_exists(connection, table):
            links[table] = 0
            continue
        columns = {
            str(row[1])
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if "scheduler_job_id" not in columns:
            links[table] = 0
            continue
        links[table] = int(
            connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE scheduler_job_id=?", (job_id,)
            ).fetchone()[0]
        )
    return links


def _target_exists(connection: sqlite3.Connection, row: sqlite3.Row) -> bool:
    table = str(row["target_table"] or "")
    target_id = row["target_id"]
    if table != "printer_tracking_queue" or target_id is None:
        return False
    return connection.execute(
        "SELECT 1 FROM printer_tracking_queue WHERE id=?", (int(target_id),)
    ).fetchone() is not None


def classify_scheduler_residue(
    connection: sqlite3.Connection, job_ids: Iterable[int] = AUDITED_JOB_IDS
) -> tuple[dict[str, Any], ...]:
    """Classify the exact audited rows without writing."""
    ids = _exact_ids(job_ids)
    connection.row_factory = sqlite3.Row
    placeholders = ",".join("?" * len(ids))
    rows = connection.execute(
        f"SELECT * FROM printer_scheduler_jobs WHERE id IN ({placeholders}) ORDER BY id",
        ids,
    ).fetchall()
    if tuple(int(row["id"]) for row in rows) != ids:
        raise SchedulerResidueReconciliationError(
            "audited scheduler row set is missing or changed"
        )
    result: list[dict[str, Any]] = []
    for row in rows:
        links = _ownership_links(connection, int(row["id"]))
        unlocked = row["locked_at"] is None and row["lock_owner"] is None
        target_exists = _target_exists(connection, row)
        status = str(row["status"])
        if status == "PENDING" and unlocked and target_exists and not any(links.values()):
            classification = "UNLINKED_HISTORICAL_ACTIVE_STATUS"
        elif status == "CANCELLED" and unlocked and target_exists and not any(links.values()):
            classification = "RECONCILED_HISTORICAL_TERMINAL"
        else:
            classification = "CLASSIFICATION_DRIFT"
        result.append(
            {
                "id": int(row["id"]),
                "status": status,
                "unlocked": unlocked,
                "target_exists": target_exists,
                "ownership_links": links,
                "classification": classification,
                "row": dict(row),
            }
        )
    return tuple(result)


def _require_no_active_owners(connection: sqlite3.Connection) -> None:
    checks = (
        ("printer_memory_factory_campaigns", "campaign_state", ("RUNNING", "PREFLIGHT", "STOP_REQUESTED")),
        ("printer_memory_factory_campaign_runs", "run_state", ("RUNNING", "STOP_REQUESTED")),
        ("printer_memory_factory_campaign_supervision", "supervision_state", ("ACTIVE", "STOPPING")),
        ("printer_discovery_work", "work_state", ("PENDING", "RUNNING", "COOLDOWN")),
        ("printer_memory_factory_run_steps", "step_status", ("PENDING", "RUNNING")),
    )
    for table, column, states in checks:
        if not _table_exists(connection, table):
            continue
        placeholders = ",".join("?" * len(states))
        count = int(
            connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {column} IN ({placeholders})",
                states,
            ).fetchone()[0]
        )
        if count:
            raise SchedulerResidueReconciliationError(
                f"active operational ownership exists in {table}"
            )


def reconcile_scheduler_residue(
    db_path: str | Path,
    *,
    expected_authoritative_path: str | Path,
    expected_sha256: str,
    job_ids: Iterable[int],
    operator_approved: bool,
    backup_path: str | Path,
    disposable_restore_root: str | Path,
    restore_path: str | Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Back up and atomically terminalize the exact audited Scheduler rows."""
    if not operator_approved:
        raise SchedulerResidueReconciliationError("operator approval is required")
    ids = _exact_ids(job_ids)
    path = Path(db_path).resolve()
    expected_path = Path(expected_authoritative_path).resolve()
    if path != expected_path:
        raise SchedulerResidueReconciliationError("authoritative database path mismatch")
    if not path.is_file():
        raise SchedulerResidueReconciliationError("authoritative database is missing")
    expected_hash = str(expected_sha256).lower()
    if len(expected_hash) != 64 or _sha256(path) != expected_hash:
        raise SchedulerResidueReconciliationError("authoritative database SHA mismatch")

    read = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=0.0)
    read.row_factory = sqlite3.Row
    try:
        read.execute("PRAGMA query_only=ON")
        before_classification = classify_scheduler_residue(read, ids)
        _require_no_active_owners(read)
    finally:
        read.close()
    classes = {item["classification"] for item in before_classification}
    if classes == {"RECONCILED_HISTORICAL_TERMINAL"}:
        return {
            "status": "ALREADY_RECONCILED",
            "job_ids": ids,
            "changed_fields": (),
            "database_sha256": _sha256(path),
            "source_calls": 0,
            "campaigns_created": 0,
        }
    if classes != {"UNLINKED_HISTORICAL_ACTIVE_STATUS"}:
        raise SchedulerResidueReconciliationError(
            "scheduler residue classification drifted"
        )

    backup = operational_backup_restore_preflight(
        path,
        expected_source_path=expected_path,
        expected_source_identity=f"sha256:{expected_hash}",
        backup_path=backup_path,
        disposable_restore_root=disposable_restore_root,
        restore_path=restore_path,
    )
    if backup["status"] != "OPERATIONAL_BACKUP_RESTORE_PREFLIGHT_READY":
        raise SchedulerResidueReconciliationError("verified backup was not ready")

    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    connection = sqlite3.connect(path, timeout=0.0)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        fresh = classify_scheduler_residue(connection, ids)
        _require_no_active_owners(connection)
        if {item["classification"] for item in fresh} != {
            "UNLINKED_HISTORICAL_ACTIVE_STATUS"
        }:
            raise SchedulerResidueReconciliationError(
                "scheduler residue changed after backup"
            )
        before_rows = {item["id"]: dict(item["row"]) for item in fresh}
        for job_id in ids:
            cancel_job(connection, job_id=job_id, now=stamp)
        after = classify_scheduler_residue(connection, ids)
        if {item["classification"] for item in after} != {
            "RECONCILED_HISTORICAL_TERMINAL"
        }:
            raise SchedulerResidueReconciliationError(
                "scheduler terminal transition did not reconcile every row"
            )
        changed_fields: set[str] = set()
        for item in after:
            old = before_rows[item["id"]]
            new = item["row"]
            changed_fields.update(
                key for key in old if old[key] != new[key]
            )
            if any(old[field] != new[field] for field in PROTECTED_FIELDS):
                raise SchedulerResidueReconciliationError(
                    f"protected scheduler fields changed for job {item['id']}"
                )
        if not changed_fields.issubset(ALLOWED_CHANGED_FIELDS):
            raise SchedulerResidueReconciliationError(
                f"unexpected scheduler fields changed: {sorted(changed_fields)}"
            )
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or foreign_keys:
            raise SchedulerResidueReconciliationError(
                "post-repair database validation failed"
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    return {
        "status": "SCHEDULER_RESIDUE_RECONCILED",
        "job_ids": ids,
        "changed_fields": tuple(sorted(changed_fields)),
        "backup_path": str(Path(backup_path).resolve()),
        "database_sha256_before": expected_hash,
        "database_sha256_after": _sha256(path),
        "integrity": "ok",
        "foreign_key_violations": 0,
        "source_calls": 0,
        "campaigns_created": 0,
    }


__all__ = [
    "ALLOWED_CHANGED_FIELDS",
    "AUDITED_JOB_IDS",
    "EXPECTED_PRE_REPAIR_SHA256",
    "SchedulerResidueReconciliationError",
    "classify_scheduler_residue",
    "reconcile_scheduler_residue",
]

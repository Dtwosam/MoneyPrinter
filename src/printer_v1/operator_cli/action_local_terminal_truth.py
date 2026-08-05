"""Action-local terminal truth for WINDOW_15M public command surfaces.

Captures a pre-action baseline and, on success or exception, reports exact
action-attributable source requests, transport categories, DB identity and
table-by-table deltas without inventing attribution that cannot be proven.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ActionLocalBaseline:
    """Read-only snapshot taken before mutable campaign work."""

    database_identity: Mapping[str, object]
    table_counts: Mapping[str, int]
    source_request_max_id: int
    source_response_max_id: int
    source_failure_max_id: int
    measured_transport_max_id: int


_MUTATION_TABLES: tuple[str, ...] = (
    # Campaign identity and terminal ownership (pre-lifecycle and later).
    "printer_memory_factory_campaign_configurations",
    "printer_memory_factory_campaigns",
    "printer_memory_factory_campaign_runs",
    "printer_memory_factory_campaign_cycles",
    "printer_memory_factory_campaign_supervision",
    "printer_memory_factory_campaign_token_slots",
    "printer_memory_factory_campaign_windows",
    "printer_memory_factory_campaign_scheduler_work",
    "printer_memory_factory_campaign_reports",
    "printer_memory_factory_campaign_report_objects",
    "printer_memory_factory_campaign_objects",
    "printer_memory_factory_campaign_heartbeat_failures",
    "printer_memory_factory_runs",
    "printer_memory_factory_run_steps",
    # Source Governor durable evidence.
    "printer_source_requests",
    "printer_source_responses",
    "printer_source_failures",
    "printer_source_health",
    "printer_source_rate_limits",
    "printer_external_source_operations",
    "printer_measured_transport_operations",
    # Discovery / reserve layers reachable before lifecycle handoff.
    "printer_discovery_reserve_layers",
    "printer_exact_market_states",
    "printer_discovery_work",
    "printer_discovery_work_source_links",
    "printer_discovery_candidates",
    "printer_discovery_merged_candidates",
    "printer_discovery_candidate_contributions",
    "printer_discovery_selected_items",
    "printer_discovery_selected_item_links",
    "printer_discovery_selection_links",
    "printer_discovery_batches",
    "printer_discovery_availability_observations",
    "printer_discovery_provider_observations",
    "printer_discovery_exhaustion_certificates",
    # Holder evidence and maturation (pre-lifecycle admission).
    "printer_holder_campaign_operation_ledgers",
    "printer_holder_evidence_attempts",
    "printer_holder_maturation_work",
    # Scheduler and memory surfaces that may mutate once lifecycle starts.
    "printer_scheduler_jobs",
    "printer_token_snapshots",
    "printer_memory_windows",
    "printer_episodes",
    "printer_memory_fingerprints",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture_database_identity(db_path: str | Path) -> dict[str, object]:
    """Byte-level identity facts for a SQLite database file."""
    path = Path(db_path).resolve()
    if not path.is_file():
        return {
            "path": str(path),
            "exists": False,
            "sha256": None,
            "size": None,
            "inode": None,
            "mtime_ns": None,
        }
    st = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "sha256": _sha256_file(path),
        "size": int(st.st_size),
        "inode": int(st.st_ino),
        "mtime_ns": int(st.st_mtime_ns),
    }


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def _count_table(connection: sqlite3.Connection, table: str) -> int:
    if not _table_exists(connection, table):
        return 0
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _max_id(connection: sqlite3.Connection, table: str, column: str = "id") -> int:
    if not _table_exists(connection, table):
        return 0
    try:
        row = connection.execute(f"SELECT MAX({column}) FROM {table}").fetchone()
    except sqlite3.Error:
        return 0
    if row is None or row[0] is None:
        return 0
    return int(row[0])


def capture_action_local_baseline(
    db_path: str | Path,
    *,
    tables: Sequence[str] | None = None,
) -> ActionLocalBaseline:
    """Capture pre-mutation baseline counts and source ID ceilings."""
    path = Path(db_path).resolve()
    identity = capture_database_identity(path)
    counts: dict[str, int] = {}
    max_req = max_resp = max_fail = max_transport = 0
    if path.is_file():
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            for table in tables or _MUTATION_TABLES:
                counts[table] = _count_table(connection, table)
            max_req = _max_id(connection, "printer_source_requests")
            max_resp = _max_id(connection, "printer_source_responses")
            max_fail = _max_id(connection, "printer_source_failures")
            # Measured transport table name varies across migrations.
            for candidate in (
                "printer_measured_transport_operations",
                "printer_source_transport_operations",
            ):
                if _table_exists(connection, candidate):
                    max_transport = _max_id(connection, candidate)
                    break
        finally:
            connection.close()
    return ActionLocalBaseline(
        database_identity=identity,
        table_counts=counts,
        source_request_max_id=max_req,
        source_response_max_id=max_resp,
        source_failure_max_id=max_fail,
        measured_transport_max_id=max_transport,
    )


def _campaign_scope_clause(
    *,
    campaign_id: str | None,
    run_id: str | None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if campaign_id:
        clauses.append("campaign_id = ?")
        params.append(campaign_id)
    if run_id:
        clauses.append("run_id = ?")
        params.append(run_id)
    if not clauses:
        return "1=0", []
    return " AND ".join(clauses), params


def build_action_local_terminal_truth(
    db_path: str | Path,
    *,
    baseline: ActionLocalBaseline | None = None,
    execution_id: str | None = None,
    campaign_id: str | None = None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    supervision_id: str | None = None,
    first_terminal_cause: str | None = None,
) -> dict[str, object]:
    """Build action-local source and mutation truth from durable evidence."""
    path = Path(db_path).resolve()
    after_identity = capture_database_identity(path)
    before_identity = (
        dict(baseline.database_identity) if baseline is not None else None
    )
    truth: dict[str, object] = {
        "execution_id": execution_id,
        "campaign_id": campaign_id,
        "run_id": run_id,
        "cycle_id": cycle_id,
        "supervision_id": supervision_id,
        "first_terminal_cause": first_terminal_cause,
        "database_identity_before": before_identity,
        "database_identity_after": after_identity,
        "source_request_ids": [],
        "source_response_ids": [],
        "source_failure_ids": [],
        "source_request_count": 0,
        "source_response_count": 0,
        "source_failure_count": 0,
        "fresh_external_transport_attempts": 0,
        "retained_evidence_reuse_zero_transport": 0,
        "projection_only_writes": 0,
        "table_deltas": {},
        "mutation_classifications": {},
        "campaign_run_cycle_states": {
            "run_state": "UNKNOWN_NOT_ATTRIBUTABLE",
            "cycle_state": "UNKNOWN_NOT_ATTRIBUTABLE",
            "supervision_state": "UNKNOWN_NOT_ATTRIBUTABLE",
            "terminal_status": "UNKNOWN_NOT_ATTRIBUTABLE",
            "first_terminal_cause": first_terminal_cause,
            "terminal_at": "UNKNOWN_NOT_ATTRIBUTABLE",
            "cleanup_completed_at": "UNKNOWN_NOT_ATTRIBUTABLE",
            "lease_released_at": "UNKNOWN_NOT_ATTRIBUTABLE",
            "state_read_status": "NOT_ATTEMPTED",
        },
        "cleanup_complete": None,
        "lease_released": None,
        "active_locked_work": {},
        "source_calls": 0,
        "database_mutation_known": False,
        "database_mutation_status": "UNKNOWN_NOT_ATTRIBUTABLE",
        "database_writes": None,
    }
    if not path.is_file():
        return truth

    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        # Source / mutation inventory first so a later optional state-read fault
        # cannot erase already-derived IDs, deltas, or the original terminal cause.
        try:
            _populate_source_and_mutation_inventory(
                connection,
                truth=truth,
                baseline=baseline,
                before_identity=before_identity,
                after_identity=after_identity,
                campaign_id=campaign_id,
                run_id=run_id,
            )
        except Exception as exc:
            truth["source_inventory_status"] = (
                f"UNKNOWN_NOT_ATTRIBUTABLE:{type(exc).__name__}"
            )

        try:
            states = _read_campaign_run_cycle_supervision_states(
                connection,
                campaign_id=campaign_id,
                run_id=run_id,
                cycle_id=cycle_id,
                supervision_id=supervision_id,
                first_terminal_cause=first_terminal_cause,
            )
            truth["campaign_run_cycle_states"] = states
            cleanup_at = states.get("cleanup_completed_at")
            lease_at = states.get("lease_released_at")
            if cleanup_at not in (None, "UNKNOWN_NOT_ATTRIBUTABLE"):
                truth["cleanup_complete"] = True
            elif cleanup_at is None:
                truth["cleanup_complete"] = False
            else:
                truth["cleanup_complete"] = None
            if lease_at not in (None, "UNKNOWN_NOT_ATTRIBUTABLE"):
                truth["lease_released"] = True
            elif lease_at is None:
                truth["lease_released"] = False
            else:
                truth["lease_released"] = None
        except Exception as exc:
            # Never raise a secondary exception from the public exception path.
            states = dict(truth["campaign_run_cycle_states"])  # type: ignore[arg-type]
            states["state_read_status"] = (
                f"UNKNOWN_NOT_ATTRIBUTABLE:{type(exc).__name__}"
            )
            states["run_state"] = "UNKNOWN_NOT_ATTRIBUTABLE"
            states["cycle_state"] = "UNKNOWN_NOT_ATTRIBUTABLE"
            states["supervision_state"] = "UNKNOWN_NOT_ATTRIBUTABLE"
            states["terminal_status"] = "UNKNOWN_NOT_ATTRIBUTABLE"
            states["terminal_at"] = "UNKNOWN_NOT_ATTRIBUTABLE"
            states["cleanup_completed_at"] = "UNKNOWN_NOT_ATTRIBUTABLE"
            states["lease_released_at"] = "UNKNOWN_NOT_ATTRIBUTABLE"
            # Preserve the original exception as first terminal cause.
            states["first_terminal_cause"] = first_terminal_cause
            truth["campaign_run_cycle_states"] = states
            truth["cleanup_complete"] = None
            truth["lease_released"] = None

        try:
            active: dict[str, int] = {}
            if _table_exists(connection, "printer_scheduler_jobs"):
                active["scheduler_pending_or_running"] = int(
                    connection.execute(
                        """SELECT COUNT(*) FROM printer_scheduler_jobs
                           WHERE status IN ('PENDING','RUNNING')"""
                    ).fetchone()[0]
                )
                active["scheduler_locked"] = int(
                    connection.execute(
                        """SELECT COUNT(*) FROM printer_scheduler_jobs
                           WHERE locked_at IS NOT NULL OR lock_owner IS NOT NULL"""
                    ).fetchone()[0]
                )
            truth["active_locked_work"] = active
        except Exception as exc:
            truth["active_locked_work"] = {
                "status": f"UNKNOWN_NOT_ATTRIBUTABLE:{type(exc).__name__}"
            }
    finally:
        connection.close()

    return truth


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(connection, table):
        return set()
    return {
        str(row[1])
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }


def _populate_source_and_mutation_inventory(
    connection: sqlite3.Connection,
    *,
    truth: dict[str, object],
    baseline: ActionLocalBaseline | None,
    before_identity: Mapping[str, object] | None,
    after_identity: Mapping[str, object],
    campaign_id: str | None,
    run_id: str | None,
) -> None:
    """Fill source IDs and table deltas; may raise only for programming bugs."""
    scope_sql, scope_params = _campaign_scope_clause(
        campaign_id=campaign_id, run_id=run_id
    )
    request_ids: list[int] = []
    response_ids: list[int] = []
    failure_ids: list[int] = []
    baseline_max = (
        int(baseline.source_request_max_id) if baseline is not None else 0
    )

    if _table_exists(connection, "printer_source_requests"):
        cols = _table_columns(connection, "printer_source_requests")
        if "campaign_id" in cols or "run_id" in cols:
            where = scope_sql
            params = list(scope_params)
            if not params and baseline is not None:
                where = "id > ?"
                params = [baseline_max]
            rows = connection.execute(
                f"SELECT id FROM printer_source_requests WHERE {where} ORDER BY id",
                params,
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT id FROM printer_source_requests WHERE id > ? ORDER BY id",
                (baseline_max,),
            ).fetchall()
        request_ids = [int(row["id"]) for row in rows]

    if _table_exists(connection, "printer_source_responses"):
        if request_ids:
            placeholders = ",".join("?" for _ in request_ids)
            rows = connection.execute(
                f"""SELECT id FROM printer_source_responses
                    WHERE source_request_id IN ({placeholders})
                    ORDER BY id""",
                request_ids,
            ).fetchall()
            response_ids = [int(row["id"]) for row in rows]
        elif baseline is not None:
            rows = connection.execute(
                "SELECT id FROM printer_source_responses WHERE id > ? ORDER BY id",
                (int(baseline.source_response_max_id),),
            ).fetchall()
            response_ids = [int(row["id"]) for row in rows]

    if _table_exists(connection, "printer_source_failures"):
        if request_ids:
            placeholders = ",".join("?" for _ in request_ids)
            fail_cols = _table_columns(connection, "printer_source_failures")
            req_col = (
                "source_request_id"
                if "source_request_id" in fail_cols
                else "request_id"
                if "request_id" in fail_cols
                else None
            )
            if req_col is not None:
                rows = connection.execute(
                    f"""SELECT id FROM printer_source_failures
                        WHERE {req_col} IN ({placeholders})
                        ORDER BY id""",
                    request_ids,
                ).fetchall()
                failure_ids = [int(row["id"]) for row in rows]
        elif baseline is not None:
            rows = connection.execute(
                "SELECT id FROM printer_source_failures WHERE id > ? ORDER BY id",
                (int(baseline.source_failure_max_id),),
            ).fetchall()
            failure_ids = [int(row["id"]) for row in rows]

    truth["source_request_ids"] = request_ids
    truth["source_response_ids"] = response_ids
    truth["source_failure_ids"] = failure_ids
    truth["source_request_count"] = len(request_ids)
    truth["source_response_count"] = len(response_ids)
    truth["source_failure_count"] = len(failure_ids)
    truth["source_calls"] = len(request_ids)

    transport_table = None
    for candidate in (
        "printer_measured_transport_operations",
        "printer_source_transport_operations",
    ):
        if _table_exists(connection, candidate):
            transport_table = candidate
            break
    if transport_table is not None and baseline is not None:
        count = int(
            connection.execute(
                f"SELECT COUNT(*) FROM {transport_table} WHERE id > ?",
                (int(baseline.measured_transport_max_id),),
            ).fetchone()[0]
        )
        truth["fresh_external_transport_attempts"] = count
    elif len(request_ids) > 0:
        truth["fresh_external_transport_attempts"] = "UNKNOWN_NOT_ATTRIBUTABLE"

    deltas: dict[str, dict[str, object]] = {}
    classifications: dict[str, str] = {}
    total_positive_delta = 0
    for table in _MUTATION_TABLES:
        after = _count_table(connection, table)
        before = (
            int(baseline.table_counts.get(table, 0))
            if baseline is not None
            else None
        )
        if before is None:
            delta: object = "UNKNOWN_NOT_ATTRIBUTABLE"
            classifications[table] = "UNKNOWN_NOT_ATTRIBUTABLE"
        else:
            delta_int = after - before
            delta = delta_int
            if delta_int > 0:
                total_positive_delta += delta_int
                classifications[table] = "INSERT_OR_UPDATE_NET_POSITIVE"
            elif delta_int == 0:
                classifications[table] = "UNCHANGED"
            else:
                classifications[table] = "NET_NEGATIVE_OR_DELETE"
        deltas[table] = {"before": before, "after": after, "delta": delta}
    truth["table_deltas"] = deltas
    truth["mutation_classifications"] = classifications

    if baseline is not None:
        truth["database_mutation_known"] = True
        if total_positive_delta == 0 and before_identity == after_identity:
            truth["database_mutation_status"] = "PROVEN_ZERO_NO_MUTATION"
            truth["database_writes"] = 0
        elif total_positive_delta > 0:
            truth["database_mutation_status"] = "PROVEN_POSITIVE_DELTA"
            truth["database_writes"] = total_positive_delta
        else:
            truth["database_mutation_status"] = "PROVEN_DELTA_PRESENT"
            truth["database_writes"] = total_positive_delta
    else:
        truth["database_mutation_status"] = "UNKNOWN_NOT_ATTRIBUTABLE"
        truth["database_writes"] = None


def _read_campaign_run_cycle_supervision_states(
    connection: sqlite3.Connection,
    *,
    campaign_id: str | None,
    run_id: str | None,
    cycle_id: str | None,
    supervision_id: str | None,
    first_terminal_cause: str | None,
) -> dict[str, object]:
    """Read canonical durable state columns only (Migration-052 owners).

    Canonical names (do not invent compatibility aliases):
    - run: run_state, first_terminal_cause, terminal_at
    - cycle: cycle_state, first_terminal_cause, terminal_at
    - supervision: supervision_state, terminal_status, first_terminal_cause,
      terminal_at (if present), cleanup_completed_at, lease_released_at
    """
    states: dict[str, object] = {
        "run_state": "UNKNOWN_NOT_ATTRIBUTABLE",
        "cycle_state": "UNKNOWN_NOT_ATTRIBUTABLE",
        "supervision_state": "UNKNOWN_NOT_ATTRIBUTABLE",
        "terminal_status": "UNKNOWN_NOT_ATTRIBUTABLE",
        "first_terminal_cause": first_terminal_cause,
        "terminal_at": "UNKNOWN_NOT_ATTRIBUTABLE",
        "cleanup_completed_at": "UNKNOWN_NOT_ATTRIBUTABLE",
        "lease_released_at": "UNKNOWN_NOT_ATTRIBUTABLE",
        "state_read_status": "READY",
        "campaign_id": campaign_id,
        "run_id": run_id,
        "cycle_id": cycle_id,
        "supervision_id": supervision_id,
    }

    # Campaign run — canonical columns only.
    if run_id and _table_exists(connection, "printer_memory_factory_campaign_runs"):
        cols = _table_columns(connection, "printer_memory_factory_campaign_runs")
        needed = {"run_state", "first_terminal_cause", "terminal_at", "campaign_id"}
        if needed.issubset(cols):
            row = connection.execute(
                """SELECT run_state, first_terminal_cause, terminal_at, campaign_id
                   FROM printer_memory_factory_campaign_runs
                   WHERE run_id=? LIMIT 1""",
                (run_id,),
            ).fetchone()
            if row is not None:
                states["run_state"] = row["run_state"]
                states["campaign_id"] = row["campaign_id"]
                if first_terminal_cause is None and row["first_terminal_cause"] is not None:
                    states["first_terminal_cause"] = row["first_terminal_cause"]
                if row["terminal_at"] is not None:
                    states["terminal_at"] = row["terminal_at"]
            else:
                states["run_state"] = "UNKNOWN_NOT_ATTRIBUTABLE"
        else:
            states["run_state"] = "UNKNOWN_NOT_ATTRIBUTABLE"
            states["state_read_status"] = "UNKNOWN_NOT_ATTRIBUTABLE:RUN_COLUMNS"

    # Campaign cycle — canonical columns only.
    if cycle_id and _table_exists(
        connection, "printer_memory_factory_campaign_cycles"
    ):
        cols = _table_columns(connection, "printer_memory_factory_campaign_cycles")
        needed = {"cycle_state", "first_terminal_cause", "terminal_at"}
        if needed.issubset(cols):
            row = connection.execute(
                """SELECT cycle_state, first_terminal_cause, terminal_at
                   FROM printer_memory_factory_campaign_cycles
                   WHERE cycle_id=? LIMIT 1""",
                (cycle_id,),
            ).fetchone()
            if row is not None:
                states["cycle_state"] = row["cycle_state"]
                if first_terminal_cause is None and row["first_terminal_cause"] is not None:
                    if states.get("first_terminal_cause") is None:
                        states["first_terminal_cause"] = row["first_terminal_cause"]
                if (
                    states.get("terminal_at") in (None, "UNKNOWN_NOT_ATTRIBUTABLE")
                    and row["terminal_at"] is not None
                ):
                    states["terminal_at"] = row["terminal_at"]
            else:
                states["cycle_state"] = "UNKNOWN_NOT_ATTRIBUTABLE"
        else:
            states["cycle_state"] = "UNKNOWN_NOT_ATTRIBUTABLE"
            states["state_read_status"] = "UNKNOWN_NOT_ATTRIBUTABLE:CYCLE_COLUMNS"

    # Supervision — canonical columns only.
    if (supervision_id or run_id) and _table_exists(
        connection, "printer_memory_factory_campaign_supervision"
    ):
        cols = _table_columns(
            connection, "printer_memory_factory_campaign_supervision"
        )
        needed = {
            "supervision_id",
            "supervision_state",
            "terminal_status",
            "cleanup_completed_at",
            "lease_released_at",
        }
        if needed.issubset(cols):
            select_cols = (
                "supervision_id, supervision_state, terminal_status, "
                "first_terminal_cause, cleanup_completed_at, lease_released_at"
            )
            if "terminal_at" in cols:
                select_cols += ", terminal_at"
            if supervision_id:
                row = connection.execute(
                    f"""SELECT {select_cols}
                        FROM printer_memory_factory_campaign_supervision
                        WHERE supervision_id=? LIMIT 1""",
                    (supervision_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    f"""SELECT {select_cols}
                        FROM printer_memory_factory_campaign_supervision
                        WHERE run_id=?
                        ORDER BY created_at DESC LIMIT 1""",
                    (run_id,),
                ).fetchone()
            if row is not None:
                states["supervision_id"] = row["supervision_id"]
                states["supervision_state"] = row["supervision_state"]
                states["terminal_status"] = row["terminal_status"]
                states["cleanup_completed_at"] = row["cleanup_completed_at"]
                states["lease_released_at"] = row["lease_released_at"]
                if first_terminal_cause is None and row["first_terminal_cause"] is not None:
                    if states.get("first_terminal_cause") is None:
                        states["first_terminal_cause"] = row["first_terminal_cause"]
                if "terminal_at" in row.keys() and row["terminal_at"] is not None:
                    if states.get("terminal_at") in (None, "UNKNOWN_NOT_ATTRIBUTABLE"):
                        states["terminal_at"] = row["terminal_at"]
            else:
                states["supervision_state"] = "UNKNOWN_NOT_ATTRIBUTABLE"
                states["terminal_status"] = "UNKNOWN_NOT_ATTRIBUTABLE"
                states["cleanup_completed_at"] = "UNKNOWN_NOT_ATTRIBUTABLE"
                states["lease_released_at"] = "UNKNOWN_NOT_ATTRIBUTABLE"
        else:
            states["supervision_state"] = "UNKNOWN_NOT_ATTRIBUTABLE"
            states["terminal_status"] = "UNKNOWN_NOT_ATTRIBUTABLE"
            states["cleanup_completed_at"] = "UNKNOWN_NOT_ATTRIBUTABLE"
            states["lease_released_at"] = "UNKNOWN_NOT_ATTRIBUTABLE"
            states["state_read_status"] = "UNKNOWN_NOT_ATTRIBUTABLE:SUPERVISION_COLUMNS"

    # Always preserve the original exception as the first terminal cause when
    # the public exception path supplied one.
    if first_terminal_cause is not None:
        states["first_terminal_cause"] = first_terminal_cause
    return states


def merge_action_local_into_exception_envelope(
    envelope: Mapping[str, Any],
    truth: Mapping[str, Any],
) -> dict[str, Any]:
    """Overlay action-local truth onto the public exception envelope."""
    out = dict(envelope)
    out["source_calls"] = int(truth.get("source_calls") or 0)
    out["campaign_source_calls"] = (
        int(truth["source_calls"])
        if truth.get("source_calls") is not None
        else out.get("campaign_source_calls")
    )
    out["source_request_ids"] = list(truth.get("source_request_ids") or [])
    out["source_response_ids"] = list(truth.get("source_response_ids") or [])
    out["source_failure_ids"] = list(truth.get("source_failure_ids") or [])
    out["fresh_external_transport_attempts"] = truth.get(
        "fresh_external_transport_attempts"
    )
    out["database_identity_before"] = truth.get("database_identity_before")
    out["database_identity_after"] = truth.get("database_identity_after")
    out["table_deltas"] = truth.get("table_deltas")
    out["mutation_classifications"] = truth.get("mutation_classifications")
    out["database_writes"] = truth.get("database_writes")
    out["database_mutation_known"] = bool(truth.get("database_mutation_known"))
    out["database_mutation_status"] = truth.get("database_mutation_status")
    out["campaign_run_cycle_states"] = truth.get("campaign_run_cycle_states")
    states = truth.get("campaign_run_cycle_states") or {}
    if isinstance(states, Mapping):
        # Surface canonical durable names on the public envelope.
        for key in (
            "run_state",
            "cycle_state",
            "supervision_state",
            "terminal_status",
            "first_terminal_cause",
            "terminal_at",
            "cleanup_completed_at",
            "lease_released_at",
        ):
            if key in states:
                out[key] = states[key]
    out["cleanup_complete"] = truth.get("cleanup_complete")
    out["lease_released"] = truth.get("lease_released")
    out["active_locked_work"] = truth.get("active_locked_work")
    out["action_local_terminal_truth"] = dict(truth)
    return out


__all__ = [
    "ActionLocalBaseline",
    "build_action_local_terminal_truth",
    "capture_action_local_baseline",
    "capture_database_identity",
    "merge_action_local_into_exception_envelope",
]

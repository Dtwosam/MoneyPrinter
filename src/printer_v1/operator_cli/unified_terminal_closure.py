"""V2-9.7E.47 — one authoritative terminal path for a governed pilot campaign.

Before this lane the pilot runner had two disjoint terminal behaviours:

* a **pre-lifecycle** terminal reconciled campaign / run / cycle metadata
  (``_reconcile_pre_lifecycle_terminal_metadata``), and
* a **lifecycle-started** terminal reconciled nothing at all, on the stated
  assumption that "a started lifecycle owns its own terminal reconciliation".

V2-9.7E.46 §10.1 proved that assumption false: supervision closed ``TERMINAL`` /
``GOVERNED_SAFE_STOP`` with zero active work while ``RUNNING`` / ``RUNNING`` /
``PLANNED`` ownership metadata survived. This module replaces both behaviours
with a single path that covers every terminal, whether or not a factory
lifecycle run started (A1), and adds the terminal report the pilot path never
wrote (A5) and the pre-mutation dependency preflight that would have refused the
E.46 interpreter launch before any state existed (A6).

Nothing here fetches a source, schedules work, retries, restarts, or creates a
successor. Scheduler transitions go exclusively through the committed Central
Scheduler owner; campaign/run/cycle transitions go exclusively through
``campaign_ownership.transition_state``, which enforces the immutable first
terminal cause.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import tempfile
import sqlite3
import sys
from typing import Any, Iterable, Mapping

from printer_v1.discovery.scheduler_parity import reconcile_discovery_work_jobs
from printer_v1.operator_cli.campaign_active_work import (
    campaign_active_work_report,
    campaign_scoped_job_ids,
)
from printer_v1.operator_cli.campaign_ownership import (
    CampaignOwnershipError,
    transition_state,
)
from printer_v1.operator_cli.campaign_persistence import (
    CampaignPersistenceError,
    persist_terminal_report,
)
from printer_v1.operator_cli.pre_admission_discovery_attempt import (
    PreAdmissionAttemptState,
    cancel_pair_ready_pre_admission_attempt_for_terminal_parent,
    terminalize_pre_admission_attempt,
)
from printer_v1.scheduler.scheduler import cancel_job


class TerminalClosureError(RuntimeError):
    """Fail-closed unified terminal closure fault."""


# ---------------------------------------------------------------------------
# A6 — dependency and invocation preflight (before any mutable state)
# ---------------------------------------------------------------------------

#: Declared runtime dependencies the executing interpreter must satisfy before a
#: pilot may consume an authorization. ``websockets`` is declared in
#: ``pyproject.toml`` but was absent from the interpreter selected for the first
#: E.46 launch, which failed *after* supervision, the campaign graph and the
#: proof lock already existed (E.46 §2).
REQUIRED_RUNTIME_DEPENDENCIES: tuple[tuple[str, str], ...] = (
    ("websockets", "12.0"),
)

#: Canonical package that must resolve from this repository, not site-packages.
CANONICAL_PACKAGE = "printer_v1"


@dataclass(frozen=True)
class DependencyPreflight:
    status: str
    interpreter: str
    package_path: str
    dependencies: tuple[dict[str, Any], ...]
    issues: tuple[str, ...]
    external_requests: int = 0
    database_writes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "interpreter": self.interpreter,
            "package_path": self.package_path,
            "dependencies": [dict(item) for item in self.dependencies],
            "issues": list(self.issues),
            "external_requests": self.external_requests,
            "database_writes": self.database_writes,
        }


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in str(value).split("."):
        digits = ""
        for character in chunk:
            if not character.isdigit():
                break
            digits += character
        parts.append(int(digits or 0))
    return tuple(parts) or (0,)


def _installed_version(module_name: str) -> str | None:
    try:
        from importlib import metadata
    except Exception:  # pragma: no cover - defensive
        return None
    try:
        return str(metadata.version(module_name))
    except Exception:
        module = sys.modules.get(module_name)
        version = getattr(module, "__version__", None)
        return str(version) if version else None


def assert_runtime_dependency_preflight(
    *,
    required: Iterable[tuple[str, str]] = REQUIRED_RUNTIME_DEPENDENCIES,
    repository_root: str | Path | None = None,
    adapter_builders: Iterable[tuple[str, Any]] = (),
    paths: Mapping[str, Any] | None = None,
) -> DependencyPreflight:
    """Resolve interpreter, dependencies, package and adapters before mutation.

    Performs zero external requests and zero database writes. A failure here
    must leave zero campaign, run, cycle, supervision, lock or source rows,
    because it runs before any of them are created.
    """
    issues: list[str] = []
    interpreter = str(Path(sys.executable).resolve()) if sys.executable else ""
    if not interpreter:
        issues.append("EXACT_PYTHON_INTERPRETER_UNRESOLVED")

    package_path = ""
    try:
        package = importlib.import_module(CANONICAL_PACKAGE)
        package_file = getattr(package, "__file__", None)
        if not package_file:
            issues.append("CANONICAL_PACKAGE_HAS_NO_LOCATION")
        else:
            package_path = str(Path(package_file).resolve().parent)
    except Exception:
        issues.append("CANONICAL_PACKAGE_IMPORT_FAILED")
    if repository_root is not None and package_path:
        root = Path(repository_root).resolve()
        package_parent = Path(package_path)
        if root not in package_parent.parents and package_parent != root:
            # Enforce package-under-repo only for full source checkouts that
            # themselves contain src/printer_v1. Disposable evidence-only
            # worktrees bind authorization Git without vendoring the package.
            checkout_pkg = root / "src" / "printer_v1"
            if checkout_pkg.is_dir() or (root / "printer_v1").is_dir():
                issues.append("CANONICAL_PACKAGE_NOT_RESOLVED_FROM_REPOSITORY")

    dependencies: list[dict[str, Any]] = []
    for module_name, minimum in required:
        record: dict[str, Any] = {
            "module": module_name,
            "required_minimum": minimum,
            "importable": False,
            "version": None,
            "satisfied": False,
        }
        try:
            importlib.import_module(module_name)
            record["importable"] = True
        except Exception:
            issues.append(f"DECLARED_DEPENDENCY_NOT_IMPORTABLE:{module_name}")
            dependencies.append(record)
            continue
        version = _installed_version(module_name)
        record["version"] = version
        if version is None:
            issues.append(f"DECLARED_DEPENDENCY_VERSION_UNKNOWN:{module_name}")
        elif _version_tuple(version) < _version_tuple(minimum):
            issues.append(
                f"DECLARED_DEPENDENCY_BELOW_MINIMUM:{module_name}<{minimum}"
            )
        else:
            record["satisfied"] = True
        dependencies.append(record)

    for label, builder in adapter_builders:
        try:
            built = builder()
        except Exception:
            issues.append(f"REQUIRED_ADAPTER_NOT_CONSTRUCTIBLE:{label}")
            continue
        if built is None:
            issues.append(f"REQUIRED_ADAPTER_NOT_CONSTRUCTIBLE:{label}")

    for label, value in dict(paths or {}).items():
        if value is None or not str(value).strip():
            issues.append(f"INVOCATION_PATH_MISSING:{label}")

    return DependencyPreflight(
        status="READY" if not issues else "BLOCKED",
        interpreter=interpreter,
        package_path=package_path,
        dependencies=tuple(dependencies),
        issues=tuple(issues),
    )


# ---------------------------------------------------------------------------
# A1 — one authoritative terminal reconciliation
# ---------------------------------------------------------------------------

#: run_status / stop_reason -> campaign ownership terminal state.
_COMPLETED_STATUSES = frozenset({"COMPLETED"})
_FAILED_STATUSES = frozenset({"FAILED"})
_CLEAN_STOP_CAUSES = frozenset(
    {
        "PILOT_INPUT_READY",
        "COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
        "PRE_LIFECYCLE_ATOMIC_TWO_SLOT_READY",
    }
)


def resolve_terminal_state(*, run_status: str | None, terminal_cause: str) -> str:
    """Map an honest terminal result onto one campaign ownership state."""
    status = str(run_status or "").strip().upper()
    cause = str(terminal_cause or "").strip()
    if status in _COMPLETED_STATUSES:
        return "TERMINAL_COMPLETED"
    if status in _FAILED_STATUSES:
        return "TERMINAL_FAILED"
    if cause in _CLEAN_STOP_CAUSES:
        return "TERMINAL_STOPPED"
    if cause.startswith("SAFE_STOP_"):
        return "TERMINAL_STOPPED"
    return "TERMINAL_BLOCKED"


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _transition(
    connection: sqlite3.Connection,
    *,
    record_kind: str,
    identity: str,
    candidate_states: tuple[str, ...],
    new_state: str,
    cause: str,
    now: str,
) -> str:
    """Compare-and-update through the ownership owner; never rewrite a terminal."""
    last_error = "not_found"
    for expected_state in candidate_states:
        try:
            result = transition_state(
                connection,
                record_kind=record_kind,
                identity=identity,
                expected_state=expected_state,
                new_state=new_state,
                terminal_cause=cause,
                now=now,
            )
            return result.current_state
        except CampaignOwnershipError as exc:
            message = str(exc)
            if "terminal state" in message or "immutable" in message:
                # First terminal cause is immutable and already recorded.
                return "already_terminal"
            if "unknown" in message:
                return "not_found"
            last_error = f"skipped:{type(exc).__name__}"
    return last_error


def _current_state(
    connection: sqlite3.Connection, table: str, identity_column: str,
    state_column: str, identity: str,
) -> str | None:
    if not _table_exists(connection, table):
        return None
    row = connection.execute(
        f"SELECT {state_column} FROM {table} WHERE {identity_column}=?",
        (identity,),
    ).fetchone()
    return None if row is None else str(row[0])


def _is_already_terminal_ownership_state(state: str | None) -> bool:
    """True when campaign/run/cycle ownership is already in a TERMINAL_* state."""
    return bool(state) and str(state).startswith("TERMINAL_")


def reconcile_campaign_terminal(
    db_path: str | Path,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    terminal_cause: str,
    run_status: str | None = None,
    factory_run_id: str | None = None,
    lifecycle_started: bool = False,
    now: str | None = None,
) -> dict[str, Any]:
    """Terminally reconcile the whole campaign ownership graph, once.

    Covers campaign, campaign run, cycle, factory run, every started campaign
    memory window, campaign-scoped work and Scheduler jobs. Idempotent: a second
    call over an already-terminal graph changes nothing and preserves the first
    terminal cause.
    """
    cause = str(terminal_cause or "").strip() or "GOVERNED_TERMINAL"
    new_state = resolve_terminal_state(run_status=run_status, terminal_cause=cause)
    instant = now or _utc_now()
    report: dict[str, Any] = {
        "reconciled": True,
        "lifecycle_started": bool(lifecycle_started),
        "terminal_cause": cause,
        "new_state": new_state,
        "records": {},
        "cancelled_jobs": 0,
        "pre_admission_attempts": [],
        "discovery_parity": {},
        "windows": {},
        "factory_run": "not_found",
        "pre_lifecycle_dispositions": [],
    }
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        # 1. Discovery work / Scheduler job parity (A2), campaign-scoped.
        report["discovery_parity"] = reconcile_discovery_work_jobs(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            abandoned_cause=cause,
        )

        # 2. Every remaining attributable Scheduler job is cancelled through the
        #    Scheduler owner. Work that already succeeded or failed keeps its own
        #    terminal; only still-active jobs are cancelled.
        groups = campaign_scoped_job_ids(
            connection,
            factory_run_id=factory_run_id,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
        )
        every_id = sorted(set().union(*groups.values())) if groups else []
        cancelled = 0
        for job_id in every_id:
            row = connection.execute(
                "SELECT status, locked_at, lock_owner FROM printer_scheduler_jobs "
                "WHERE id=?",
                (job_id,),
            ).fetchone()
            if row is None:
                continue
            active = str(row["status"]) in {"PENDING", "RUNNING", "COOLDOWN"}
            locked = row["locked_at"] is not None or row["lock_owner"] is not None
            if active or locked:
                cancel_job(connection, job_id=job_id)
                cancelled += 1
        report["cancelled_jobs"] = cancelled

        # 2b. Terminalize attributable pre-admission discovery attempts. Existing
        #     PLANNED/RUNNING cleanup keeps its broad attribution law. A frozen
        #     PAIR_READY admission authority is cancelled only on exact campaign,
        #     run and factory ownership and preserves its frozen-pair truth.
        pre_admission_outcomes: list[dict[str, Any]] = []
        if _table_exists(
            connection, "printer_pre_admission_discovery_attempts"
        ) and (factory_run_id or campaign_id or run_id or cycle_id):
            clauses: list[str] = []
            params: list[Any] = []
            for column, value in (
                ("authoritative_factory_run_id", factory_run_id),
                ("campaign_id", campaign_id),
                ("campaign_run_id", run_id),
                ("proposed_cycle_id", cycle_id),
            ):
                if value:
                    clauses.append(f"{column} = ?")
                    params.append(value)
            attempt_rows = list(connection.execute(
                """
                SELECT attempt_id, scheduler_job_id, attempt_state
                FROM printer_pre_admission_discovery_attempts
                WHERE ({})
                  AND attempt_state IN ('PLANNED','RUNNING')
                ORDER BY attempt_id
                """.format(" OR ".join(clauses)),
                tuple(params),
            ).fetchall())
            if factory_run_id:
                pair_ready_rows = connection.execute(
                    """
                    SELECT attempt_id, scheduler_job_id, attempt_state
                    FROM printer_pre_admission_discovery_attempts
                    WHERE campaign_id=?
                      AND campaign_run_id=?
                      AND authoritative_factory_run_id=?
                      AND attempt_state='PAIR_READY'
                    ORDER BY attempt_id
                    """,
                    (campaign_id, run_id, factory_run_id),
                ).fetchall()
                existing_attempt_ids = {
                    str(row["attempt_id"]) for row in attempt_rows
                }
                attempt_rows.extend(
                    row for row in pair_ready_rows
                    if str(row["attempt_id"]) not in existing_attempt_ids
                )
            attempt_now = datetime.fromisoformat(instant)
            if attempt_now.tzinfo is None:
                attempt_now = attempt_now.replace(tzinfo=timezone.utc)
            for attempt_row in attempt_rows:
                attempt_id = str(attempt_row["attempt_id"])
                prior_state = str(attempt_row["attempt_state"])
                job_id = int(attempt_row["scheduler_job_id"])
                job_row = connection.execute(
                    "SELECT status, locked_at, lock_owner "
                    "FROM printer_scheduler_jobs WHERE id=?",
                    (job_id,),
                ).fetchone()
                job_cancelled = False
                if job_row is not None:
                    job_active = str(job_row["status"]) in {
                        "PENDING",
                        "RUNNING",
                        "COOLDOWN",
                    }
                    job_locked = (
                        job_row["locked_at"] is not None
                        or job_row["lock_owner"] is not None
                    )
                    if job_active or job_locked:
                        cancel_job(connection, job_id=job_id)
                        job_cancelled = True
                        cancelled += 1
                if prior_state == PreAdmissionAttemptState.PAIR_READY.value:
                    if not factory_run_id:
                        raise TerminalClosureError(
                            "PAIR_READY_PARENT_TERMINAL_FACTORY_ID_REQUIRED"
                        )
                    cancel_pair_ready_pre_admission_attempt_for_terminal_parent(
                        connection,
                        attempt_id=attempt_id,
                        campaign_id=campaign_id,
                        campaign_run_id=run_id,
                        authoritative_factory_run_id=factory_run_id,
                        now=attempt_now,
                    )
                    outcome_cause = "EXACT_PAIR_FROZEN"
                else:
                    terminalize_pre_admission_attempt(
                        connection,
                        attempt_id=attempt_id,
                        state=PreAdmissionAttemptState.CANCELLED,
                        cause=cause,
                        now=attempt_now,
                    )
                    outcome_cause = cause
                pre_admission_outcomes.append(
                    {
                        "attempt_id": attempt_id,
                        "scheduler_job_id": job_id,
                        "prior_state": prior_state,
                        "new_state": PreAdmissionAttemptState.CANCELLED.value,
                        "job_cancelled": job_cancelled,
                        "terminal_cause": outcome_cause,
                    }
                )
            report["cancelled_jobs"] = cancelled
            report["pre_admission_attempts"] = pre_admission_outcomes

        # 3. Every started campaign memory window reaches a terminal state.
        if _table_exists(connection, "printer_memory_factory_campaign_windows"):
            rows = connection.execute(
                """
                SELECT window_id, window_state
                FROM printer_memory_factory_campaign_windows
                WHERE campaign_id=? AND run_id=?
                ORDER BY window_id
                """,
                (campaign_id, run_id),
            ).fetchall()
            outcomes: dict[str, str] = {}
            for row in rows:
                state = str(row["window_state"])
                if state in {"PLANNED", "COLLECTING", "CLOSE_PENDING", "AUDITING"}:
                    outcomes[str(row["window_id"])] = _transition(
                        connection,
                        record_kind="window",
                        identity=str(row["window_id"]),
                        candidate_states=(state,),
                        new_state="CANCELLED",
                        cause=cause,
                        now=instant,
                    )
                else:
                    outcomes[str(row["window_id"])] = "already_terminal"
            report["windows"] = outcomes

        # 4. Factory run: a governed terminal never leaves run_status RUNNING.
        if factory_run_id and _table_exists(connection, "printer_memory_factory_runs"):
            row = connection.execute(
                "SELECT run_status FROM printer_memory_factory_runs WHERE run_id=?",
                (factory_run_id,),
            ).fetchone()
            if row is None:
                report["factory_run"] = "not_found"
            elif str(row["run_status"]) == "RUNNING":
                factory_terminal_status = (
                    "COMPLETED"
                    if new_state == "TERMINAL_COMPLETED"
                    else "SAFE_STOPPED"
                )
                connection.execute(
                    """
                    UPDATE printer_memory_factory_runs
                    SET run_status=?,
                        stop_reason=COALESCE(stop_reason, ?),
                        finished_at=COALESCE(finished_at, ?),
                        updated_at=?
                    WHERE run_id=? AND run_status='RUNNING'
                    """,
                    (
                        factory_terminal_status,
                        cause,
                        instant,
                        instant,
                        factory_run_id,
                    ),
                )
                # Provisional only. Durable report status is re-read after commit.
                report["factory_run"] = "pending_persist"
            else:
                report["factory_run"] = str(row["run_status"])

        # 4a. Preserve selected evidence while removing active ownership for a
        # terminal reached before any main-window lifecycle step.
        if _table_exists(
            connection, "printer_memory_factory_campaign_token_slots"
        ):
            slot_rows = connection.execute(
                """SELECT cycle_id,token_slot_id,tracking_queue_id,token_state
                   FROM printer_memory_factory_campaign_token_slots
                   WHERE campaign_id=? AND run_id=?
                   ORDER BY cycle_id,slot_ordinal,token_slot_id""",
                (campaign_id, run_id),
            ).fetchall()
            dispositions: list[dict[str, Any]] = []
            for slot in slot_rows:
                slot_cycle_id = str(slot["cycle_id"])
                slot_id = str(slot["token_slot_id"])
                queue_id = slot["tracking_queue_id"]
                slot_result = "already_terminal"
                queue_result = "not_linked"
                owned_terminal = connection.execute(
                    """SELECT window_id, window_state
                       FROM printer_memory_factory_campaign_windows
                       WHERE campaign_id=? AND run_id=? AND cycle_id=?
                         AND token_slot_id=? AND window_kind='WINDOW_15M'
                         AND window_state IN (
                           'CLEAN_PROMOTED','DIRTY','NO_PROMOTION',
                           'ALREADY_EXISTS_IDEMPOTENT'
                         )
                       ORDER BY window_id""",
                    (campaign_id, run_id, slot_cycle_id, slot_id),
                ).fetchall()
                has_exact_owned_terminal = len(owned_terminal) == 1
                if queue_id is not None:
                    if has_exact_owned_terminal:
                        cursor = connection.execute(
                            """UPDATE printer_tracking_queue
                               SET queue_status='COOLDOWN',tracking_action='COOLDOWN',
                                   priority_reason=?,last_checked_at=?,updated_at=?
                               WHERE id=?""",
                            (
                                f"owned_window_terminal:{owned_terminal[0]['window_id']}",
                                instant,
                                instant,
                                int(queue_id),
                            ),
                        )
                    else:
                        cursor = connection.execute(
                            """UPDATE printer_tracking_queue
                               SET queue_status='SKIPPED',tracking_action='MANUAL_REVIEW',
                                   priority_reason=?,last_checked_at=?,updated_at=?
                               WHERE id=? AND queue_status='QUEUED'""",
                            (f"campaign_terminal:{cause}", instant, instant, int(queue_id)),
                        )
                    if cursor.rowcount == 1:
                        queue_result = (
                            "COOLDOWN" if has_exact_owned_terminal else "SKIPPED"
                        )
                    else:
                        current = connection.execute(
                            "SELECT queue_status FROM printer_tracking_queue WHERE id=?",
                            (int(queue_id),),
                        ).fetchone()
                        queue_result = (
                            "not_found" if current is None else str(current[0])
                        )
                if str(slot["token_state"]) not in {
                    "COOLDOWN", "ARCHIVED", "MANUAL_REVIEW", "FAILED"
                }:
                    # transition_state commits the active transaction. Queue
                    # first so the exact queue/slot terminal pair commits
                    # together; a later already-terminal campaign transition
                    # must not roll the queue disposition back.
                    slot_result = _transition(
                        connection,
                        record_kind="token_slot",
                        identity=slot_id,
                        candidate_states=(
                            "SELECTED", "WINDOW_15M_ACTIVE", "WINDOW_15M_CLOSED",
                            "WINDOW_1H_CONTINUING", "WINDOW_1H_CLOSED",
                            "WINDOW_4H_CONTINUING", "WINDOW_4H_CLOSED",
                        ),
                        new_state=(
                            "COOLDOWN"
                            if has_exact_owned_terminal and queue_result == "COOLDOWN"
                            else "MANUAL_REVIEW"
                        ),
                        cause=(
                            "OWNED_TERMINAL_WINDOW_COOLDOWN"
                            if has_exact_owned_terminal and queue_result == "COOLDOWN"
                            else cause
                        ),
                        now=instant,
                    )
                dispositions.append(
                    {
                        "cycle_id": slot_cycle_id,
                        "token_slot_id": slot_id,
                        "slot_disposition": slot_result,
                        "tracking_queue_id": queue_id,
                        "queue_disposition": queue_result,
                    }
                )
            report["pre_lifecycle_dispositions"] = dispositions

        # 5. Cycle, run and campaign. Already-terminal ownership must not call
        #    transition_state again: its connection context manager rolls back
        #    prior uncommitted factory terminalization on the same connection.
        cycle_state = _current_state(
            connection,
            "printer_memory_factory_campaign_cycles",
            "cycle_id",
            "cycle_state",
            cycle_id,
        )
        if _is_already_terminal_ownership_state(cycle_state):
            report["records"]["cycle"] = "already_terminal"
        else:
            report["records"]["cycle"] = _transition(
                connection,
                record_kind="cycle",
                identity=cycle_id,
                candidate_states=(
                    (cycle_state,) if cycle_state else
                    ("PLANNED", "DISCOVERING", "SELECTING", "TRACKING", "CLOSING",
                     "AUDITING", "ROTATING")
                ),
                new_state=new_state,
                cause=cause,
                now=instant,
            )
        for record_kind, identity, table, column in (
            (
                "run",
                run_id,
                "printer_memory_factory_campaign_runs",
                "run_state",
            ),
            (
                "campaign",
                campaign_id,
                "printer_memory_factory_campaigns",
                "campaign_state",
            ),
        ):
            current = _current_state(
                connection,
                table,
                "run_id" if record_kind == "run" else "campaign_id",
                column,
                identity,
            )
            if _is_already_terminal_ownership_state(current):
                report["records"][record_kind] = "already_terminal"
            else:
                report["records"][record_kind] = _transition(
                    connection,
                    record_kind=record_kind,
                    identity=identity,
                    candidate_states=(
                        "RUNNING", "STOP_REQUESTED", "PREFLIGHT", "DRAFT"
                    ),
                    new_state=new_state,
                    cause=cause,
                    now=instant,
                )
        connection.commit()

        # 6. Durable factory report honesty: only claim SAFE_STOPPED/COMPLETED
        #    when the committed row actually has that status.
        if factory_run_id and _table_exists(connection, "printer_memory_factory_runs"):
            durable = connection.execute(
                "SELECT run_status FROM printer_memory_factory_runs WHERE run_id=?",
                (factory_run_id,),
            ).fetchone()
            report["factory_run"] = (
                "not_found" if durable is None else str(durable["run_status"])
            )

        # 7. Prove the terminal: zero active jobs, zero active work rows.
        report["active_work"] = campaign_active_work_report(
            connection,
            factory_run_id=factory_run_id,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
        )
    finally:
        connection.close()
    report["clean_terminal"] = bool(
        report.get("active_work", {}).get("clean_terminal", True)
    )
    report["restart_created"] = False
    report["successor_created"] = False
    return report


# ---------------------------------------------------------------------------
# A5 — exactly one persistent campaign report row and one durable artifact
# ---------------------------------------------------------------------------

REPORT_ARTIFACT_SUFFIX = ".campaign-report.json"
BLOCKED_INSUFFICIENT_GRADUATED_POOL = "BLOCKED_INSUFFICIENT_GRADUATED_POOL"
LIQUIDITY_BELOW_SELECTION_FLOOR = "LIQUIDITY_BELOW_SELECTION_FLOOR"


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    )


def load_campaign_operation_totals(
    db_path: str | Path,
    *,
    run_id: str,
    cycle_id: str,
) -> dict[str, int]:
    """Read campaign-attributable operation totals from the holder ledger only.

    This is a reporting read of the existing holder budget owner. It does not
    create a second source-accounting path and never whole-table-counts
    ``printer_source_requests``.
    """
    path = Path(db_path).resolve()
    connection = sqlite3.connect(
        f"file:{path.as_posix()}?mode=ro", uri=True, timeout=0.0
    )
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        row = connection.execute(
            """SELECT governed_requests, underlying_transport_operations
               FROM printer_holder_campaign_operation_ledgers
               WHERE run_id=? AND cycle_id=?""",
            (run_id, cycle_id),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return {
            "campaign_source_calls": 0,
            "campaign_transport_operations": 0,
            "campaign_scheduler_calls": 0,
            "ledger_present": 0,
        }
    return {
        "campaign_source_calls": int(row["governed_requests"] or 0),
        "campaign_transport_operations": int(
            row["underlying_transport_operations"] or 0
        ),
        "campaign_scheduler_calls": 0,
        "ledger_present": 1,
    }


def build_candidate_supply_report(
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize one front-door / supply candidate into the terminal report shape."""
    liquidity = candidate.get("liquidity")
    if isinstance(liquidity, Mapping):
        liquidity_usd = liquidity.get("liquidity_usd")
        liquidity_status = liquidity.get("status")
        liquidity_reason = liquidity.get("reason")
        liquidity_detailed_reason = liquidity.get("detailed_reason")
        liquidity_source_status = liquidity.get("source_status")
        liquidity_outcome_category = liquidity.get("outcome_category")
        pool_from_liquidity = liquidity.get("pool")
        source_lineage = {
            "source_channel": liquidity.get("source_channel"),
            "source_request_id": liquidity.get("source_request_id"),
            "source_response_id": liquidity.get("source_response_id"),
            "source_failure_id": liquidity.get("source_failure_id"),
            "failure_type": liquidity.get("failure_type"),
        }
    else:
        liquidity_usd = candidate.get("liquidity_usd")
        liquidity_status = candidate.get("liquidity_status")
        liquidity_reason = candidate.get("liquidity_reason")
        liquidity_detailed_reason = candidate.get("liquidity_detailed_reason")
        liquidity_source_status = candidate.get("liquidity_source_status")
        liquidity_outcome_category = candidate.get("liquidity_outcome_category")
        pool_from_liquidity = None
        source_lineage = {
            "source_channel": candidate.get("liquidity_source_channel"),
            "source_request_id": candidate.get("source_request_id"),
            "source_response_id": candidate.get("source_response_id"),
            "source_failure_id": candidate.get("source_failure_id"),
            "failure_type": candidate.get("failure_type"),
        }

    eligible = bool(candidate.get("eligible"))
    rejection = candidate.get("rejection")
    if rejection is None:
        rejection = candidate.get("rejection_or_exclusion_reason")
    if not eligible and rejection is None and liquidity_status == LIQUIDITY_BELOW_SELECTION_FLOOR:
        rejection = LIQUIDITY_BELOW_SELECTION_FLOOR
    if not eligible and rejection is None and liquidity_reason:
        rejection = str(liquidity_reason)

    pool = candidate.get("pool") or candidate.get("pumpswap_pool") or pool_from_liquidity
    migration = candidate.get("migration_evidence")
    if migration is None:
        migration = {
            "migration_signature": candidate.get("migration_signature"),
            "migration_provenance": candidate.get("migration_provenance"),
        }
    pool_confirmation = candidate.get("pool_confirmation")
    if pool_confirmation is None:
        pool_confirmation = {
            "pool": pool,
            "market_identity": candidate.get("market_identity"),
            "lifecycle_state": candidate.get("lifecycle_state"),
            "confirmed": bool(
                candidate.get("pumpswap_confirmed", candidate.get("lifecycle_state")
                              == "PUMPSWAP_GRADUATED_CONFIRMED")
            ),
        }
    source_path = candidate.get("source_path")
    if not source_path:
        provenance = str(candidate.get("provenance") or "")
        if provenance:
            source_path = f"graduated_registry_or_migration:{provenance}"
        else:
            source_path = "graduated_liquidity_front_door"
    stage_reached = candidate.get("stage_reached")
    if not stage_reached:
        if eligible:
            stage_reached = "MARKET_ELIGIBLE"
        elif rejection in {LIQUIDITY_BELOW_SELECTION_FLOOR, "BELOW_3000_FLOOR"}:
            stage_reached = "LIQUIDITY_FLOOR_FAILED"
        else:
            stage_reached = "EVALUATED"

    return {
        "mint": candidate.get("mint") or candidate.get("mint_identity"),
        "source_path": source_path,
        "stage_reached": stage_reached,
        "migration_evidence": dict(migration) if isinstance(migration, Mapping) else migration,
        "pool_confirmation": (
            dict(pool_confirmation)
            if isinstance(pool_confirmation, Mapping)
            else pool_confirmation
        ),
        "liquidity": liquidity_usd,
        "liquidity_status": liquidity_status,
        "liquidity_reason": liquidity_reason,
        "liquidity_detailed_reason": (
            liquidity_detailed_reason or liquidity_reason
        ),
        "liquidity_source_status": liquidity_source_status,
        "liquidity_outcome_category": liquidity_outcome_category,
        "liquidity_source_lineage": source_lineage,
        "current_liquidity_evidence": (
            dict(liquidity) if isinstance(liquidity, Mapping) else None
        ),
        "historical_reserve_evidence": candidate.get(
            "historical_reserve_evidence"
        ),
        "current_eligibility_status": candidate.get(
            "current_eligibility_status"
        ),
        "market_cap": candidate.get("market_cap"),
        "eligibility_result": "eligible" if eligible else "rejected",
        "rejection_or_exclusion_reason": None if eligible else (
            None if rejection is None else str(rejection)
        ),
    }


def build_blocked_supply_reporting(
    *,
    required_token_capacity: int,
    candidates: Iterable[Mapping[str, Any]],
    blocked_supply_reason: str | None,
    campaign_source_calls: int,
    campaign_scheduler_calls: int = 0,
    shortage_classification: str | None = None,
    exhaustion_certificate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the authoritative blocked-supply + campaign activity report surface."""
    candidate_reports = [
        build_candidate_supply_report(candidate) for candidate in candidates
    ]
    eligible = sum(
        1 for item in candidate_reports if item.get("eligibility_result") == "eligible"
    )
    validated = sum(
        1
        for item in candidate_reports
        if item.get("liquidity") is not None
        or item.get("pool_confirmation")
        or item.get("eligibility_result") == "eligible"
    )
    observed = len(candidate_reports)
    reason = blocked_supply_reason
    if reason is None and required_token_capacity > eligible:
        reason = BLOCKED_INSUFFICIENT_GRADUATED_POOL
    blocked_supply = {
        "required_token_capacity": int(required_token_capacity),
        "candidates_observed": observed,
        "candidates_validated": validated,
        "eligible_candidates": eligible,
        "blocked_supply_reason": reason,
        "shortage_classification": shortage_classification,
        "exhaustion_certificate": (
            None if exhaustion_certificate is None else dict(exhaustion_certificate)
        ),
        "candidates": candidate_reports,
    }
    return {
        "campaign_activity": {
            "campaign_source_calls": int(campaign_source_calls),
            "campaign_scheduler_calls": int(campaign_scheduler_calls),
        },
        "blocked_supply": blocked_supply,
        "campaign_source_calls": int(campaign_source_calls),
        "campaign_scheduler_calls": int(campaign_scheduler_calls),
        "candidates_observed": observed,
        "candidates_validated": validated,
        "eligible_candidates": eligible,
        "required_token_capacity": int(required_token_capacity),
        "blocked_supply_reason": reason,
        "shortage_classification": shortage_classification,
        "exhaustion_certificate": blocked_supply["exhaustion_certificate"],
    }


def assemble_campaign_terminal_reporting(
    db_path: str | Path,
    *,
    run_id: str,
    cycle_id: str,
    terminal_cause: str | None,
    lifecycle: Mapping[str, Any] | None = None,
    required_token_capacity: int = 2,
    campaign_scheduler_calls: int | None = None,
) -> dict[str, Any]:
    """Assemble campaign totals and blocked-supply detail for terminal reporting.

    Prefers durable holder-ledger source totals. Candidate detail comes from
    lifecycle packaging produced at the insufficient-pool boundary; no network
    I/O and no second source-accounting owner.
    """
    totals = load_campaign_operation_totals(
        db_path, run_id=run_id, cycle_id=cycle_id
    )
    lifecycle = dict(lifecycle or {})
    reporting = dict(lifecycle.get("terminal_reporting") or {})
    pre_lifecycle_admission = (
        reporting.get("pre_lifecycle_admission")
        or lifecycle.get("pre_lifecycle_admission")
    )
    candidates_raw = (
        reporting.get("candidates")
        or lifecycle.get("front_door_candidates")
        or lifecycle.get("blocked_supply_candidates")
        or []
    )
    if campaign_scheduler_calls is None:
        campaign_scheduler_calls = int(
            reporting.get("campaign_scheduler_calls")
            if reporting.get("campaign_scheduler_calls") is not None
            else totals.get("campaign_scheduler_calls") or 0
        )
    source_calls = int(
        reporting.get("campaign_source_calls")
        if reporting.get("campaign_source_calls") is not None
        else totals["campaign_source_calls"]
    )
    capacity = int(
        reporting.get("required_token_capacity")
        if reporting.get("required_token_capacity") is not None
        else required_token_capacity
    )
    reason = (
        reporting.get("blocked_supply_reason")
        or lifecycle.get("blocked_supply_reason")
        or (
            terminal_cause
            if terminal_cause in {
                BLOCKED_INSUFFICIENT_GRADUATED_POOL,
                "BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL",
            }
            else None
        )
    )
    surface = build_blocked_supply_reporting(
        required_token_capacity=capacity,
        candidates=list(candidates_raw),
        blocked_supply_reason=None if reason is None else str(reason),
        campaign_source_calls=source_calls,
        campaign_scheduler_calls=int(campaign_scheduler_calls),
        shortage_classification=(
            None
            if reporting.get("shortage_classification") is None
            else str(reporting.get("shortage_classification"))
        ),
        exhaustion_certificate=(
            reporting.get("exhaustion_certificate")
            if isinstance(reporting.get("exhaustion_certificate"), Mapping)
            else None
        ),
    )
    # If no candidates were packaged and the terminal is not a blocked-supply
    # close, keep activity totals without inventing a blocked-supply story.
    from printer_v1.sources.measured_transport import (
        empty_six_unit_totals,
        six_unit_totals_from_mapping,
    )

    six_units = six_unit_totals_from_mapping(
        reporting.get("six_unit_totals")
        or lifecycle.get("six_unit_totals")
        or empty_six_unit_totals()
    )
    six_evidence = (
        reporting.get("six_unit_evidence")
        or lifecycle.get("six_unit_evidence")
        or {}
    )
    elapsed = reporting.get("elapsed_seconds")
    if elapsed is None:
        elapsed = lifecycle.get("elapsed_seconds")
    if not candidates_raw and reason is None:
        activity = dict(surface["campaign_activity"])
        activity["six_unit_totals"] = six_units
        if six_evidence:
            activity["six_unit_evidence"] = dict(six_evidence)
        result = {
            "campaign_activity": activity,
            "campaign_source_calls": surface["campaign_source_calls"],
            "campaign_scheduler_calls": surface["campaign_scheduler_calls"],
            "six_unit_totals": six_units,
            "six_unit_evidence": dict(six_evidence) if six_evidence else {},
            "elapsed_seconds": elapsed,
        }
        if isinstance(pre_lifecycle_admission, Mapping):
            result["pre_lifecycle_admission"] = dict(pre_lifecycle_admission)
        return result
    if isinstance(pre_lifecycle_admission, Mapping):
        surface["pre_lifecycle_admission"] = dict(pre_lifecycle_admission)
    activity = dict(surface.get("campaign_activity") or {})
    activity["six_unit_totals"] = six_units
    if six_evidence:
        activity["six_unit_evidence"] = dict(six_evidence)
    surface["campaign_activity"] = activity
    surface["six_unit_totals"] = six_units
    surface["six_unit_evidence"] = dict(six_evidence) if six_evidence else {}
    surface["elapsed_seconds"] = elapsed
    return surface


def build_campaign_terminal_report(
    *,
    campaign_id: str,
    configuration_id: str,
    report_id: str,
    execution_id: str,
    lifecycle_started: bool,
    reconciliation: Mapping[str, Any],
    campaign_run_id: str | None = None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    factory_run_id: str | None = None,
    terminal_accounting: Mapping[str, Any] | None = None,
    terminal_status: str | None = None,
    terminal_cause: str | None = None,
    run_status: str | None = None,
    forbidden_deltas: Mapping[str, int] | None = None,
    launch_git_provenance: Mapping[str, Any] | None = None,
    campaign_activity: Mapping[str, Any] | None = None,
    blocked_supply: Mapping[str, Any] | None = None,
    campaign_source_calls: int | None = None,
    campaign_scheduler_calls: int | None = None,
    candidates_observed: int | None = None,
    candidates_validated: int | None = None,
    eligible_candidates: int | None = None,
    required_token_capacity: int | None = None,
    blocked_supply_reason: str | None = None,
    fault_details: Mapping[str, Any] | None = None,
    selective_1h: Mapping[str, Any] | None = None,
    pre_lifecycle_admission: Mapping[str, Any] | None = None,
    six_unit_totals: Mapping[str, int] | None = None,
    six_unit_evidence: Mapping[str, Any] | None = None,
    elapsed_seconds: float | None = None,
    require_six_unit_evidence: bool = False,
) -> dict[str, Any]:
    """Assemble the canonical terminal report payload from stored facts only.

    When ``require_six_unit_evidence`` is True (the top-level coordinator path),
    six-unit accounting is fail-closed before a report can be built: missing,
    malformed, duplicate, partial, or mismatched evidence raises
    ``TerminalClosureError`` and no synthetic empty evidence is substituted for
    an attempted campaign.
    """
    from printer_v1.sources.campaign_six_unit_accounting import (
        CampaignSixUnitError,
        compare_report_totals_to_evidence,
        empty_six_unit_evidence,
        reconstruct_six_unit_totals_from_evidence,
    )
    from printer_v1.sources.measured_transport import (
        empty_six_unit_totals,
        six_unit_totals_from_mapping,
    )

    provided_evidence = isinstance(six_unit_evidence, Mapping)
    if require_six_unit_evidence and not provided_evidence:
        # Attempted-campaign evidence must never be synthesized (B7/B8).
        raise TerminalClosureError("SIX_UNIT_EVIDENCE_MISSING")
    evidence = (
        dict(six_unit_evidence)
        if provided_evidence
        else empty_six_unit_evidence()
    )
    if require_six_unit_evidence:
        # Structural fail-closed: malformed / duplicate / negative evidence.
        try:
            evidence_totals = reconstruct_six_unit_totals_from_evidence(evidence)
        except CampaignSixUnitError as exc:
            raise TerminalClosureError(f"SIX_UNIT_EVIDENCE_INVALID:{exc}") from exc
        resolved_six = (
            six_unit_totals_from_mapping(six_unit_totals)
            if six_unit_totals is not None
            else evidence_totals
        )
    elif six_unit_totals is not None:
        resolved_six = six_unit_totals_from_mapping(six_unit_totals)
    elif evidence.get("transport_operations") is not None:
        try:
            resolved_six = reconstruct_six_unit_totals_from_evidence(evidence)
        except Exception:
            resolved_six = empty_six_unit_totals()
    else:
        resolved_six = empty_six_unit_totals()
    evidence_compare = compare_report_totals_to_evidence(resolved_six, evidence)
    if require_six_unit_evidence and not bool(evidence_compare.get("equal")):
        # Report totals must equal the independent evidence reconstruction (B9).
        raise TerminalClosureError("SIX_UNIT_EVIDENCE_MISMATCH")
    lane4_accounting = (
        json.loads(_canonical_json(terminal_accounting))
        if isinstance(terminal_accounting, Mapping)
        else None
    )
    if lane4_accounting is not None:
        if any(
            value is not None
            for value in (cycle_id, terminal_status, terminal_cause, run_status)
        ):
            raise TerminalClosureError(
                "LANE4_REPORT_REJECTS_LEGACY_SHARED_TERMINAL_INPUTS"
            )
        resolved_run_id = str(campaign_run_id or run_id or "").strip()
        if not resolved_run_id:
            raise TerminalClosureError("CAMPAIGN_RUN_ID_MISSING")
        cycles = lane4_accounting.get("cycles")
        if not isinstance(cycles, list) or [
            int(item.get("cycle_ordinal") or 0)
            for item in cycles
            if isinstance(item, Mapping)
        ] != [1, 2]:
            raise TerminalClosureError("LANE4_EXACT_TWO_CYCLE_ACCOUNTING_MISSING")
        expected_identity = {
            "campaign_id": campaign_id,
            "campaign_run_id": resolved_run_id,
            "configuration_id": configuration_id,
            "factory_run_id": factory_run_id,
        }
        for field, expected in expected_identity.items():
            supplied = lane4_accounting.get(field)
            if str(supplied or "") != str(expected or ""):
                raise TerminalClosureError(
                    f"LANE4_TERMINAL_ACCOUNTING_IDENTITY_MISMATCH:{field}"
                )
        if lane4_accounting.get("required_cycle_ordinals") != [1, 2]:
            raise TerminalClosureError(
                "LANE4_REQUIRED_CYCLE_ORDINALS_MISMATCH"
            )
        canonical_first_cause = lane4_accounting.get("first_cause")
        canonical_execution = str(
            lane4_accounting.get("execution_outcome") or ""
        )
        identity = {
            "campaign_id": campaign_id,
            "configuration_id": configuration_id,
            "campaign_run_id": resolved_run_id,
            "report_id": report_id,
            "factory_run_id": factory_run_id,
            "execution_id": execution_id,
        }
        policy_version = "V2_9_8B_LANE4_MULTI_CYCLE_TERMINAL"
        terminal_payload = {
            "terminal_status": canonical_execution,
            "first_terminal_cause": canonical_first_cause,
            "run_status": canonical_execution,
            "lifecycle_started": bool(lifecycle_started),
        }
    else:
        resolved_run_id = str(run_id or campaign_run_id or "").strip()
        if not resolved_run_id:
            raise TerminalClosureError("RUN_ID_MISSING")
        if not str(cycle_id or "").strip():
            raise TerminalClosureError("CYCLE_ID_MISSING")
        identity = {
            "campaign_id": campaign_id,
            "configuration_id": configuration_id,
            "run_id": resolved_run_id,
            "cycle_id": cycle_id,
            "report_id": report_id,
            "factory_run_id": factory_run_id,
            "execution_id": execution_id,
        }
        policy_version = "V2_9_8B_VERIFIABLE_REAL_PATH_TERMINAL"
        terminal_payload = {
            "terminal_status": terminal_status,
            "first_terminal_cause": terminal_cause,
            "run_status": run_status,
            "lifecycle_started": bool(lifecycle_started),
        }

    payload: dict[str, Any] = {
        "report_kind": "PILOT_CAMPAIGN_TERMINAL",
        "policy_version": policy_version,
        "identity": identity,
        "terminal": terminal_payload,
        "reconciliation": json.loads(_canonical_json(reconciliation)),
        "forbidden_deltas": dict(forbidden_deltas or {}),
        "launch_git_provenance": dict(launch_git_provenance or {}),
        "six_unit_totals": resolved_six,
        "six_unit_evidence": evidence,
        "six_unit_evidence_match": bool(evidence_compare.get("equal")),
        "elapsed_seconds": (
            None if elapsed_seconds is None else float(elapsed_seconds)
        ),
        "downstream_unlocks": {
            "retrieval": False,
            "paper_decisions": False,
            "buy_sell_hold": False,
            "positions": False,
            "trades": False,
            "audits": False,
            "pnl": False,
        },
        "restart_created": False,
        "successor_created": False,
    }
    if lane4_accounting is not None:
        payload["terminal_accounting"] = lane4_accounting
        payload["cycles"] = list(lane4_accounting["cycles"])
    if fault_details:
        payload["terminal"]["fault_details"] = json.loads(
            _canonical_json(dict(fault_details))
        )
    if selective_1h is not None:
        payload["selective_1h"] = json.loads(
            _canonical_json(dict(selective_1h))
        )
    if pre_lifecycle_admission is not None:
        payload["pre_lifecycle_admission"] = json.loads(
            _canonical_json(dict(pre_lifecycle_admission))
        )
    if campaign_activity is not None:
        activity = dict(campaign_activity)
        if "six_unit_totals" not in activity:
            activity["six_unit_totals"] = resolved_six
        elif six_unit_totals is None:
            payload["six_unit_totals"] = six_unit_totals_from_mapping(
                activity.get("six_unit_totals")
            )
        payload["campaign_activity"] = activity
        payload["campaign_source_calls"] = int(
            campaign_activity.get("campaign_source_calls")
            if campaign_source_calls is None
            else campaign_source_calls
        )
        payload["campaign_scheduler_calls"] = int(
            campaign_activity.get("campaign_scheduler_calls")
            if campaign_scheduler_calls is None
            else campaign_scheduler_calls
        )
    elif campaign_source_calls is not None or campaign_scheduler_calls is not None:
        payload["campaign_source_calls"] = int(campaign_source_calls or 0)
        payload["campaign_scheduler_calls"] = int(campaign_scheduler_calls or 0)
        payload["campaign_activity"] = {
            "campaign_source_calls": payload["campaign_source_calls"],
            "campaign_scheduler_calls": payload["campaign_scheduler_calls"],
            "six_unit_totals": resolved_six,
        }
    if blocked_supply is not None:
        payload["blocked_supply"] = dict(blocked_supply)
        payload["shortage_classification"] = blocked_supply.get(
            "shortage_classification"
        )
        payload["exhaustion_certificate"] = blocked_supply.get(
            "exhaustion_certificate"
        )
        payload["candidates_observed"] = int(
            blocked_supply.get("candidates_observed")
            if candidates_observed is None
            else candidates_observed
        )
        payload["candidates_validated"] = int(
            blocked_supply.get("candidates_validated")
            if candidates_validated is None
            else candidates_validated
        )
        payload["eligible_candidates"] = int(
            blocked_supply.get("eligible_candidates")
            if eligible_candidates is None
            else eligible_candidates
        )
        payload["required_token_capacity"] = int(
            blocked_supply.get("required_token_capacity")
            if required_token_capacity is None
            else required_token_capacity
        )
        payload["blocked_supply_reason"] = (
            blocked_supply.get("blocked_supply_reason")
            if blocked_supply_reason is None
            else blocked_supply_reason
        )
    else:
        if candidates_observed is not None:
            payload["candidates_observed"] = int(candidates_observed)
        if candidates_validated is not None:
            payload["candidates_validated"] = int(candidates_validated)
        if eligible_candidates is not None:
            payload["eligible_candidates"] = int(eligible_candidates)
        if required_token_capacity is not None:
            payload["required_token_capacity"] = int(required_token_capacity)
        if blocked_supply_reason is not None:
            payload["blocked_supply_reason"] = blocked_supply_reason
    return payload


def _assert_report_six_unit_evidence(report: Mapping[str, Any]) -> None:
    """Fail closed unless the report carries valid, matched six-unit evidence."""
    from printer_v1.sources.campaign_six_unit_accounting import (
        CampaignSixUnitError,
        compare_report_totals_to_evidence,
    )

    if not isinstance(report, Mapping):
        raise TerminalClosureError("SIX_UNIT_EVIDENCE_MISSING")
    evidence = report.get("six_unit_evidence")
    if not isinstance(evidence, Mapping) or not evidence:
        raise TerminalClosureError("SIX_UNIT_EVIDENCE_MISSING")
    totals = report.get("six_unit_totals")
    try:
        comparison = compare_report_totals_to_evidence(totals, evidence)
    except CampaignSixUnitError as exc:
        raise TerminalClosureError(f"SIX_UNIT_EVIDENCE_INVALID:{exc}") from exc
    if not bool(comparison.get("equal")):
        raise TerminalClosureError("SIX_UNIT_EVIDENCE_MISMATCH")
    if report.get("six_unit_evidence_match") is False:
        raise TerminalClosureError("SIX_UNIT_EVIDENCE_MISMATCH")


def build_campaign_terminal_summary(
    *,
    campaign_id: str,
    configuration_id: str,
    campaign_run_id: str,
    factory_run_id: str | None,
    execution_id: str,
    report_id: str,
    terminal_accounting: Mapping[str, Any],
    report_result: Mapping[str, Any] | None,
    cleanup: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build the subordinate operator summary from canonical report inputs.

    This helper performs no lifecycle query.  Both cycle summaries and campaign
    status are projections of the already-derived terminal-accounting mapping.
    """
    accounting = json.loads(_canonical_json(terminal_accounting))
    for field, expected in (
        ("campaign_id", campaign_id),
        ("configuration_id", configuration_id),
        ("campaign_run_id", campaign_run_id),
        ("factory_run_id", factory_run_id),
    ):
        if str(accounting.get(field) or "") != str(expected or ""):
            raise TerminalClosureError(
                f"TERMINAL_SUMMARY_ACCOUNTING_IDENTITY_MISMATCH:{field}"
            )
    if accounting.get("required_cycle_ordinals") != [1, 2]:
        raise TerminalClosureError(
            "TERMINAL_SUMMARY_REQUIRED_CYCLE_ORDINALS_MISMATCH"
        )
    cycles = accounting.get("cycles")
    if not isinstance(cycles, list):
        raise TerminalClosureError("TERMINAL_SUMMARY_CYCLES_MISSING")
    ordinals = [
        int(item.get("cycle_ordinal") or 0)
        for item in cycles
        if isinstance(item, Mapping)
    ]
    if ordinals not in ([], [1, 2]):
        raise TerminalClosureError("TERMINAL_SUMMARY_CYCLE_IDENTITY_MISMATCH")
    report = dict(report_result or {})
    cleanup_truth = dict(cleanup or {})
    durable_report = bool(
        report.get("report_rows") == 1
        and str(report.get("report_hash") or "").strip()
        and str(report.get("artifact_path") or "").strip()
    )
    return {
        "summary_version": "V2_9_8B_LANE4_TERMINAL_SUMMARY_V1",
        "status": "OPERATIONAL_CAMPAIGN_TERMINAL_SUMMARY",
        "campaign_id": str(campaign_id),
        "configuration_id": str(configuration_id),
        "campaign_run_id": str(campaign_run_id),
        # Compatibility read alias. New exact identity is campaign_run_id.
        "run_id": str(campaign_run_id),
        "factory_run_id": factory_run_id,
        "execution_id": str(execution_id),
        "report_id": str(report_id),
        "report_status": "REPORT_DURABLE" if durable_report else "REPORT_MISSING",
        "report_hash": report.get("report_hash"),
        "terminal_report_path": report.get("artifact_path"),
        "campaign_execution_outcome": accounting.get("execution_outcome"),
        "campaign_quality_outcome": accounting.get("quality_outcome"),
        "campaign_accounting_complete": bool(
            accounting.get("accounting_complete") is True
        ),
        "first_terminal_cause": accounting.get("first_cause"),
        "secondary_faults": list(accounting.get("secondary_faults") or []),
        "cycles": [
            {
                "cycle_id": item.get("cycle_id"),
                "cycle_ordinal": int(item.get("cycle_ordinal")),
                "activity_state": item.get("activity_state"),
                "execution_outcome": item.get("execution_outcome"),
                "quality_outcome": item.get("quality_outcome"),
                "accounting_complete": bool(item.get("accounting_complete")),
                "requires_review": bool(item.get("requires_review")),
                "primary_fault": item.get("primary_fault"),
                "secondary_faults": list(item.get("secondary_faults") or []),
            }
            for item in cycles
        ],
        "cleanup_complete": bool(cleanup_truth.get("cleanup_complete")),
        "lease_released": bool(cleanup_truth.get("lease_released")),
        "active_work": int(cleanup_truth.get("active_work") or 0),
        "restart_created": False,
        "successor_created": False,
        "permanent_locks": {
            "cycle_3_locked": True,
            "window_12h_locked": True,
            "window_24h_locked": True,
            "retrieval_locked": True,
            "financial_capabilities_locked": True,
        },
    }


def write_campaign_terminal_summary(
    destination: str | Path,
    *,
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Create one deterministic summary artifact; divergent replay blocks."""
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    canonical = _canonical_json(summary)
    encoded = canonical.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    if path.exists():
        try:
            existing = path.read_bytes()
        except OSError as exc:
            raise TerminalClosureError(
                f"terminal summary read blocked: {exc}"
            ) from exc
        if existing != encoded:
            raise TerminalClosureError("terminal summary artifact already differs")
        return {
            "artifact_path": str(path.resolve()),
            "summary_hash": digest,
            "artifact_created": False,
        }
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        temporary.write_bytes(encoded)
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if path.read_bytes() != encoded:
            raise TerminalClosureError(
                "terminal summary artifact differs after persistence"
            )
    except (OSError, TerminalClosureError) as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        if isinstance(exc, TerminalClosureError):
            raise
        raise TerminalClosureError(
            f"terminal summary artifact write blocked: {exc}"
        ) from exc
    return {
        "artifact_path": str(path.resolve()),
        "summary_hash": digest,
        "artifact_created": True,
    }


def write_campaign_terminal_report(
    db_path: str | Path,
    report_directory: str | Path,
    *,
    report_id: str,
    campaign_id: str,
    configuration_id: str,
    report: Mapping[str, Any],
    now: datetime | None = None,
    require_six_unit_evidence: bool = False,
) -> dict[str, Any]:
    """Persist exactly one report row and one durable artifact, idempotently.

    Uses the committed ``campaign_persistence`` report owner for the row (which
    rejects a differing payload under the same identity) and writes the same
    canonical bytes to one file in the configured report directory. A replay
    creates no duplicate row and no second artifact.

    ``campaign_source_calls`` / ``source_calls`` on the return surface are the
    original campaign totals embedded in the report payload. Report-write itself
    performs no Source Governor work; replay surfaces use ``replay_new_*``.

    When ``require_six_unit_evidence`` is True, persistence is blocked
    (``TerminalClosureError``) on missing, malformed, or mismatched six-unit
    evidence — a final guard so an accounting-faulted report cannot be written
    or reported as successful completion.
    """
    if require_six_unit_evidence:
        _assert_report_six_unit_evidence(report)
    canonical = _canonical_json(report)
    report_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # Checkpoint 7: the exact artifact must exist before the authoritative
    # REPORT_TERMINAL row is committed. New artifacts are written to an exact
    # sibling temporary file, fsynced, and atomically replaced into place.
    directory = Path(report_directory)
    directory.mkdir(parents=True, exist_ok=True)
    artifact = directory / f"{report_id}{REPORT_ARTIFACT_SUFFIX}"
    artifact_created = False
    if artifact.exists():
        existing = artifact.read_text(encoding="utf-8")
        if existing != canonical:
            raise TerminalClosureError(
                "durable campaign report artifact already differs"
            )
    else:
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{artifact.name}.",
            suffix=".tmp",
            dir=str(directory),
        )
        os.close(fd)
        temporary_artifact = Path(temporary_name)
        try:
            temporary_artifact.write_text(canonical, encoding="utf-8")
            with temporary_artifact.open("rb") as stream:
                os.fsync(stream.fileno())
            os.replace(temporary_artifact, artifact)
        except OSError as exc:
            try:
                temporary_artifact.unlink(missing_ok=True)
            except OSError:
                pass
            raise TerminalClosureError(
                f"campaign report artifact write blocked: {exc}"
            ) from exc
        artifact_created = True

    try:
        persisted = persist_terminal_report(
            db_path,
            report_id=report_id,
            campaign_id=campaign_id,
            configuration_id=configuration_id,
            report=report,
            now=now,
        )
    except Exception as exc:
        # Compensate only an artifact created by this invocation. A
        # pre-existing exact artifact is never removed.
        if artifact_created:
            try:
                artifact.unlink()
            except OSError:
                pass
        if isinstance(exc, CampaignPersistenceError):
            raise TerminalClosureError(
                f"campaign report persistence blocked: {exc}"
            ) from exc
        raise
    if str(persisted.get("report_hash")) != report_hash:
        raise TerminalClosureError("persisted campaign report hash mismatch")

    try:
        final_artifact = artifact.read_text(encoding="utf-8")
    except OSError as exc:
        raise TerminalClosureError(
            f"durable campaign report artifact readback blocked: {exc}"
        ) from exc
    if final_artifact != canonical:
        raise TerminalClosureError(
            "durable campaign report artifact differs after persistence"
        )
    written = sorted(
        path.name for path in directory.glob(f"*{REPORT_ARTIFACT_SUFFIX}")
    )
    activity = report.get("campaign_activity") if isinstance(report, Mapping) else None
    campaign_source_calls = int(
        report.get("campaign_source_calls")
        if report.get("campaign_source_calls") is not None
        else (
            activity.get("campaign_source_calls")
            if isinstance(activity, Mapping) and activity.get("campaign_source_calls") is not None
            else 0
        )
    )
    campaign_scheduler_calls = int(
        report.get("campaign_scheduler_calls")
        if report.get("campaign_scheduler_calls") is not None
        else (
            activity.get("campaign_scheduler_calls")
            if isinstance(activity, Mapping)
            and activity.get("campaign_scheduler_calls") is not None
            else 0
        )
    )
    return {
        "report_id": report_id,
        "campaign_id": campaign_id,
        "configuration_id": configuration_id,
        "report_hash": report_hash,
        "report_rows": 1,
        "artifact_path": str(artifact.resolve()),
        "artifact_created": artifact_created,
        "artifact_count": len(written),
        "artifacts": written,
        "campaign_source_calls": campaign_source_calls,
        "campaign_scheduler_calls": campaign_scheduler_calls,
        # Compatibility alias: original campaign total, not report-write work.
        "source_calls": campaign_source_calls,
        "scheduler_calls": campaign_scheduler_calls,
        "candidates_observed": report.get("candidates_observed"),
        "candidates_validated": report.get("candidates_validated"),
        "eligible_candidates": report.get("eligible_candidates"),
        "required_token_capacity": report.get("required_token_capacity"),
        "blocked_supply_reason": report.get("blocked_supply_reason"),
        "blocked_supply": report.get("blocked_supply"),
        "shortage_classification": report.get("shortage_classification"),
        "exhaustion_certificate": report.get("exhaustion_certificate"),
        "six_unit_totals": (
            dict(report["six_unit_totals"])
            if isinstance(report.get("six_unit_totals"), Mapping)
            else {}
        ),
    }


def replay_campaign_terminal_report(
    db_path: str | Path,
    report_directory: str | Path,
    *,
    report_id: str,
    campaign_id: str,
    configuration_id: str,
) -> dict[str, Any]:
    """Deterministic zero-source report-only replay; creates no duplicate row."""
    path = Path(db_path).resolve()
    connection = sqlite3.connect(
        f"file:{path.as_posix()}?mode=ro", uri=True, timeout=0.0
    )
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute(
            """SELECT report_id, campaign_id, configuration_id, report_kind,
                      report_state, report_hash, report_json
               FROM printer_memory_factory_campaign_reports
               WHERE report_id=? AND campaign_id=? AND configuration_id=?""",
            (report_id, campaign_id, configuration_id),
        ).fetchall()
        if len(rows) != 1:
            raise TerminalClosureError("terminal campaign report identity mismatch")
        row = dict(rows[0])
        total_changes = int(connection.total_changes)
    finally:
        connection.close()
    if row["report_kind"] != "TERMINAL" or row["report_state"] != "REPORT_TERMINAL":
        raise TerminalClosureError("terminal campaign report state mismatch")
    stored = json.loads(str(row["report_json"]))
    canonical = _canonical_json(stored)
    if canonical != row["report_json"]:
        raise TerminalClosureError("stored campaign report is not canonical JSON")
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if digest != str(row["report_hash"]):
        raise TerminalClosureError("stored campaign report hash mismatch")
    artifact = Path(report_directory) / f"{report_id}{REPORT_ARTIFACT_SUFFIX}"
    artifact_matches = (
        artifact.is_file() and artifact.read_text(encoding="utf-8") == canonical
    )
    activity = stored.get("campaign_activity") if isinstance(stored, dict) else None
    campaign_source_calls = int(
        stored.get("campaign_source_calls")
        if stored.get("campaign_source_calls") is not None
        else (
            activity.get("campaign_source_calls")
            if isinstance(activity, Mapping)
            and activity.get("campaign_source_calls") is not None
            else 0
        )
    )
    campaign_scheduler_calls = int(
        stored.get("campaign_scheduler_calls")
        if stored.get("campaign_scheduler_calls") is not None
        else (
            activity.get("campaign_scheduler_calls")
            if isinstance(activity, Mapping)
            and activity.get("campaign_scheduler_calls") is not None
            else 0
        )
    )
    from printer_v1.sources.campaign_six_unit_accounting import (
        compare_report_totals_to_evidence,
        empty_six_unit_evidence,
        reconstruct_six_unit_totals_from_evidence,
    )
    from printer_v1.sources.measured_transport import six_unit_totals_from_mapping

    stored_six = six_unit_totals_from_mapping(
        stored.get("six_unit_totals") if isinstance(stored, dict) else None
    )
    evidence = (
        dict(stored.get("six_unit_evidence") or {})
        if isinstance(stored, dict)
        else empty_six_unit_evidence()
    )
    if not evidence:
        evidence = empty_six_unit_evidence()
    # Independent reconstruction from durable evidence — never self-compare totals.
    reconstructed = reconstruct_six_unit_totals_from_evidence(evidence)
    equality = compare_report_totals_to_evidence(stored_six, evidence)
    return {
        "mode": "REPORT_ONLY",
        "report_id": report_id,
        "report_hash": digest,
        "report": stored,
        "report_rows": 1,
        "duplicate_reports_created": 0,
        "artifact_matches": artifact_matches,
        "campaign_source_calls": campaign_source_calls,
        "campaign_scheduler_calls": campaign_scheduler_calls,
        "six_unit_totals": stored_six,
        "six_unit_evidence": evidence,
        "six_unit_totals_reconstructed": reconstructed,
        "six_unit_report_replay_equal": bool(equality.get("equal")),
        "six_unit_self_comparison": False,
        "elapsed_seconds": (
            stored.get("elapsed_seconds") if isinstance(stored, dict) else None
        ),
        "replay_new_source_calls": 0,
        "replay_new_scheduler_calls": 0,
        "replay_new_transport_operations": 0,
        # Compatibility aliases for earlier replay consumers.
        "new_source_calls": 0,
        "new_scheduler_work": 0,
        "database_writes": total_changes,
        "candidates_observed": stored.get("candidates_observed"),
        "candidates_validated": stored.get("candidates_validated"),
        "eligible_candidates": stored.get("eligible_candidates"),
        "required_token_capacity": stored.get("required_token_capacity"),
        "blocked_supply_reason": stored.get("blocked_supply_reason"),
        "blocked_supply": stored.get("blocked_supply"),
        "shortage_classification": stored.get("shortage_classification"),
        "exhaustion_certificate": stored.get("exhaustion_certificate"),
    }


__all__ = [
    "BLOCKED_INSUFFICIENT_GRADUATED_POOL",
    "CANONICAL_PACKAGE",
    "DependencyPreflight",
    "LIQUIDITY_BELOW_SELECTION_FLOOR",
    "REPORT_ARTIFACT_SUFFIX",
    "REQUIRED_RUNTIME_DEPENDENCIES",
    "TerminalClosureError",
    "assemble_campaign_terminal_reporting",
    "assert_runtime_dependency_preflight",
    "build_blocked_supply_reporting",
    "build_campaign_terminal_report",
    "build_campaign_terminal_summary",
    "build_candidate_supply_report",
    "load_campaign_operation_totals",
    "reconcile_campaign_terminal",
    "replay_campaign_terminal_report",
    "resolve_terminal_state",
    "write_campaign_terminal_report",
    "write_campaign_terminal_summary",
]

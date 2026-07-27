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
from pathlib import Path
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
        if root not in Path(package_path).parents and Path(package_path) != root:
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
        "discovery_parity": {},
        "windows": {},
        "factory_run": "not_found",
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
                connection.execute(
                    """
                    UPDATE printer_memory_factory_runs
                    SET run_status='SAFE_STOPPED',
                        stop_reason=COALESCE(stop_reason, ?),
                        finished_at=COALESCE(finished_at, ?),
                        updated_at=?
                    WHERE run_id=? AND run_status='RUNNING'
                    """,
                    (cause, instant, instant, factory_run_id),
                )
                report["factory_run"] = "SAFE_STOPPED"
            else:
                report["factory_run"] = str(row["run_status"])

        # 5. Cycle, run and campaign. The cycle may sit anywhere in its own
        #    sequence; the campaign/run may be RUNNING or STOP_REQUESTED.
        cycle_state = _current_state(
            connection,
            "printer_memory_factory_campaign_cycles",
            "cycle_id",
            "cycle_state",
            cycle_id,
        )
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
        for record_kind, identity in (("run", run_id), ("campaign", campaign_id)):
            report["records"][record_kind] = _transition(
                connection,
                record_kind=record_kind,
                identity=identity,
                candidate_states=("RUNNING", "STOP_REQUESTED", "PREFLIGHT", "DRAFT"),
                new_state=new_state,
                cause=cause,
                now=instant,
            )
        connection.commit()

        # 6. Prove the terminal: zero active jobs, zero active work rows.
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
        pool_from_liquidity = liquidity.get("pool")
    else:
        liquidity_usd = candidate.get("liquidity_usd")
        liquidity_status = candidate.get("liquidity_status")
        liquidity_reason = candidate.get("liquidity_reason")
        pool_from_liquidity = None

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
    return {
        "campaign_activity": {
            "campaign_source_calls": int(campaign_source_calls),
            "campaign_scheduler_calls": int(campaign_scheduler_calls),
        },
        "blocked_supply": {
            "required_token_capacity": int(required_token_capacity),
            "candidates_observed": observed,
            "candidates_validated": validated,
            "eligible_candidates": eligible,
            "blocked_supply_reason": reason,
            "candidates": candidate_reports,
        },
        "campaign_source_calls": int(campaign_source_calls),
        "campaign_scheduler_calls": int(campaign_scheduler_calls),
        "candidates_observed": observed,
        "candidates_validated": validated,
        "eligible_candidates": eligible,
        "required_token_capacity": int(required_token_capacity),
        "blocked_supply_reason": reason,
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
    )
    # If no candidates were packaged and the terminal is not a blocked-supply
    # close, keep activity totals without inventing a blocked-supply story.
    if not candidates_raw and reason is None:
        return {
            "campaign_activity": surface["campaign_activity"],
            "campaign_source_calls": surface["campaign_source_calls"],
            "campaign_scheduler_calls": surface["campaign_scheduler_calls"],
        }
    return surface


def build_campaign_terminal_report(
    *,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    cycle_id: str,
    report_id: str,
    factory_run_id: str | None,
    execution_id: str,
    terminal_status: str,
    terminal_cause: str,
    run_status: str | None,
    lifecycle_started: bool,
    reconciliation: Mapping[str, Any],
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
) -> dict[str, Any]:
    """Assemble the canonical terminal report payload from stored facts only."""
    payload: dict[str, Any] = {
        "report_kind": "PILOT_CAMPAIGN_TERMINAL",
        "policy_version": "V2_9_7E_47_UNIFIED_TERMINAL_CLOSURE",
        "identity": {
            "campaign_id": campaign_id,
            "configuration_id": configuration_id,
            "run_id": run_id,
            "cycle_id": cycle_id,
            "report_id": report_id,
            "factory_run_id": factory_run_id,
            "execution_id": execution_id,
        },
        "terminal": {
            "terminal_status": terminal_status,
            "first_terminal_cause": terminal_cause,
            "run_status": run_status,
            "lifecycle_started": bool(lifecycle_started),
        },
        "reconciliation": json.loads(_canonical_json(reconciliation)),
        "forbidden_deltas": dict(forbidden_deltas or {}),
        "launch_git_provenance": dict(launch_git_provenance or {}),
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
    if fault_details:
        payload["terminal"]["fault_details"] = json.loads(
            _canonical_json(dict(fault_details))
        )
    if campaign_activity is not None:
        payload["campaign_activity"] = dict(campaign_activity)
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
        }
    if blocked_supply is not None:
        payload["blocked_supply"] = dict(blocked_supply)
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


def write_campaign_terminal_report(
    db_path: str | Path,
    report_directory: str | Path,
    *,
    report_id: str,
    campaign_id: str,
    configuration_id: str,
    report: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Persist exactly one report row and one durable artifact, idempotently.

    Uses the committed ``campaign_persistence`` report owner for the row (which
    rejects a differing payload under the same identity) and writes the same
    canonical bytes to one file in the configured report directory. A replay
    creates no duplicate row and no second artifact.

    ``campaign_source_calls`` / ``source_calls`` on the return surface are the
    original campaign totals embedded in the report payload. Report-write itself
    performs no Source Governor work; replay surfaces use ``replay_new_*``.
    """
    canonical = _canonical_json(report)
    report_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    try:
        persisted = persist_terminal_report(
            db_path,
            report_id=report_id,
            campaign_id=campaign_id,
            configuration_id=configuration_id,
            report=report,
            now=now,
        )
    except CampaignPersistenceError as exc:
        raise TerminalClosureError(f"campaign report persistence blocked: {exc}") from exc
    if str(persisted.get("report_hash")) != report_hash:
        raise TerminalClosureError("persisted campaign report hash mismatch")

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
        artifact.write_text(canonical, encoding="utf-8")
        artifact_created = True
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
        "replay_new_source_calls": 0,
        "replay_new_scheduler_calls": 0,
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
    "build_candidate_supply_report",
    "load_campaign_operation_totals",
    "reconcile_campaign_terminal",
    "replay_campaign_terminal_report",
    "resolve_terminal_state",
    "write_campaign_terminal_report",
]

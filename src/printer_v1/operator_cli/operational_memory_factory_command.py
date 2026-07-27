"""Public V2-9.8 bounded persistent 15-minute Memory Factory command.

This is the only public operational entry point. It fixes the authoritative
database target, generates artifact identities internally, preserves the
Source Governor/Central Scheduler owners, and exposes zero-source auxiliary
modes. The legacy V2-9.7E pilot launcher is neither imported nor promoted.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time
from typing import Any, Iterable, Mapping
import uuid

from printer_v1.db import migrate as migration_runner
from printer_v1.operator_cli.abstract_campaign_command import (
    CAMPAIGN_MODE,
    CENTRAL_SCHEDULER_OWNER,
    SOURCE_GOVERNOR_OWNER,
    AbstractCampaignCommand,
    CampaignCeilings,
    OwnerPort,
    report_path_identity,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
    OneShotUrllibPumpTransport,
    OneShotUrllibSecondaryTransport,
)
from printer_v1.operator_cli.graduated_supply_front_door import (
    OPERATIONAL_GRADUATED_SUPPLY_KWARGS,
)
from printer_v1.operator_cli.campaign_ownership import create_campaign_run
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_OPERATIONAL_PERSISTENT,
    create_campaign,
)
from printer_v1.operator_cli.campaign_supervision import (
    acquire_campaign_supervision,
    cleanup_campaign_supervision,
    inspect_campaign_supervision,
    renew_campaign_lease,
    request_campaign_cancellation,
)
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES
from printer_v1.operator_cli.git_provenance import (
    GitProvenanceError,
    capture_git_provenance,
)
from printer_v1.operator_cli.operational_backup_restore_preflight import (
    operational_backup_restore_preflight,
)
from printer_v1.operator_cli.operational_campaign_recovery import (
    production_recovery_paths,
    recover_exact_orphan,
)
from printer_v1.operator_cli.proof_db_schema_readiness import (
    CANONICAL_PERSISTENT_DB,
)
from printer_v1.operator_cli.holder_reliability_budget_control import (
    build_operational_budget_preflight,
)
from printer_v1.operator_cli.readiness_source_contract_preflight import (
    build_readiness_source_contract_preflight,
)
from printer_v1.operator_cli.unified_terminal_closure import (
    assemble_campaign_terminal_reporting,
    assert_runtime_dependency_preflight,
    build_campaign_terminal_report,
    reconcile_campaign_terminal,
    replay_campaign_terminal_report,
    write_campaign_terminal_report,
)
from printer_v1.scheduler.scheduler import ACTIVE_STATUS_VALUES


POLICY_VERSION = "V2-9.8-15M-OPERATIONAL-V1"
TOKEN_CAPACITY = 2
MAIN_WINDOW = "WINDOW_15M"
MAIN_WINDOW_SECONDS = 900
TOTAL_DURATION_SECONDS = 1_200
DISCOVERY_REQUEST_CEILING = 2
GOVERNED_15M_REQUEST_CEILING = 65
GOVERNED_REQUESTS_PER_TOKEN = 21
SCHEDULER_ROW_CEILING = 51
ADMISSION_OPERATION_CEILING = 45
STORAGE_BYTE_CEILING = 64 * 1024 * 1024
FAILURE_CEILING = 20
AUTOMATIC_RETRIES = 0
LEASE_SECONDS = 90
HEARTBEAT_SECONDS = 30
FREE_PUBLIC_SOLANA_RPC = "https://api.mainnet-beta.solana.com"
ARTIFACT_ROOT = Path.home() / "PrinterOperations" / "v2-9-8"
AUTHORITATIVE_DB = Path(CANONICAL_PERSISTENT_DB).resolve()
# Re-export shared E.46B / V2-9.8B.6 supply bounds for public production wiring.
EXPECTED_MIGRATION_COUNT = 44
LOCKED_WINDOWS = ("WINDOW_1H", "WINDOW_4H", "WINDOW_12H", "WINDOW_24H")
AUTHORITATIVE_SQLITE_RUNTIME_SIDECARS = (
    "data/printer_v1.sqlite3-journal",
    "data/printer_v1.sqlite3-wal",
    "data/printer_v1.sqlite3-shm",
)


class OperationalMemoryFactoryError(RuntimeError):
    """Fail-closed public command fault."""


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _read_only(path: Path = AUTHORITATIVE_DB) -> sqlite3.Connection:
    if path.resolve() != AUTHORITATIVE_DB or not path.is_file():
        raise OperationalMemoryFactoryError("authoritative database target mismatch")
    connection = sqlite3.connect(
        f"file:{path.as_posix()}?mode=ro", uri=True, timeout=0.0
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def _active_counts(connection: sqlite3.Connection) -> dict[str, int]:
    checks = {
        "scheduler_jobs": (
            "printer_scheduler_jobs", "status", ACTIVE_STATUS_VALUES,
        ),
        "locked_scheduler_jobs": (
            "printer_scheduler_jobs", None, (),
        ),
        "campaigns": (
            "printer_memory_factory_campaigns", "campaign_state",
            ("PREFLIGHT", "RUNNING", "STOP_REQUESTED"),
        ),
        "campaign_runs": (
            "printer_memory_factory_campaign_runs", "run_state",
            ("RUNNING", "STOP_REQUESTED"),
        ),
        "campaign_supervision": (
            "printer_memory_factory_campaign_supervision", "supervision_state",
            ("ACTIVE", "STOPPING"),
        ),
        "discovery_work": (
            "printer_discovery_work", "work_state",
            ("PENDING", "RUNNING", "COOLDOWN"),
        ),
        "factory_run_steps": (
            "printer_memory_factory_run_steps", "step_status",
            ("PENDING", "RUNNING"),
        ),
        "proof_supervision": (
            "printer_proof_run_supervision", "execution_status",
            ("STARTING", "RUNNING"),
        ),
    }
    counts: dict[str, int] = {}
    for label, (table, column, states) in checks.items():
        if not _table_exists(connection, table):
            counts[label] = 0
            continue
        if label == "locked_scheduler_jobs":
            counts[label] = int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_scheduler_jobs "
                    "WHERE locked_at IS NOT NULL OR lock_owner IS NOT NULL"
                ).fetchone()[0]
            )
        else:
            placeholders = ",".join("?" * len(states))
            counts[label] = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {table} "
                    f"WHERE {column} IN ({placeholders})",
                    states,
                ).fetchone()[0]
            )
    return counts


def _locked_capability_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in LOCKED_CAPABILITY_TABLES
    }


def _validate_locked_baseline(counts: Mapping[str, int]) -> None:
    # Preserved pre-V2-9.8 historical paper-only evidence. These rows are not
    # activation and must remain exact; all position/trade/PnL surfaces stay 0.
    allowed = {
        "printer_memory_retrieval_queries": 10,
        "printer_paper_decisions": 2,
        "printer_paper_audit_reports": 1,
    }
    for table, count in counts.items():
        if int(count) != allowed.get(table, 0):
            raise OperationalMemoryFactoryError(
                f"locked capability baseline drift: {table}={count}"
            )


def _capture_operational_git_provenance(root: Path) -> dict[str, Any]:
    provenance = capture_git_provenance(
        root, allowed_untracked_paths=AUTHORITATIVE_SQLITE_RUNTIME_SIDECARS
    )
    if provenance["git_untracked_present"]:
        raise GitProvenanceError(
            "launch Git tree contains an arbitrary untracked file"
        )
    return provenance


def build_activation_preflight(
    *,
    db_path: str | Path = AUTHORITATIVE_DB,
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    """Run the complete read-only, zero-source activation preflight."""
    path = Path(db_path).resolve()
    if path != AUTHORITATIVE_DB or not path.is_file():
        raise OperationalMemoryFactoryError("only data/printer_v1.sqlite3 is allowed")
    sidecars = [
        str(Path(f"{path}{suffix}"))
        for suffix in ("-wal", "-shm", "-journal")
        if Path(f"{path}{suffix}").exists()
    ]
    if sidecars:
        raise OperationalMemoryFactoryError("SQLite sidecar state is not quiescent")
    root = (
        Path(repository_root).resolve()
        if repository_root is not None
        else AUTHORITATIVE_DB.parent.parent
    )
    provenance = _capture_operational_git_provenance(root)
    source = build_readiness_source_contract_preflight()
    dependency = assert_runtime_dependency_preflight(repository_root=root)
    budget = build_operational_budget_preflight(
        admission_operation_ceiling=ADMISSION_OPERATION_CEILING,
        discovery_request_ceiling=DISCOVERY_REQUEST_CEILING,
        governed_15m_request_ceiling=GOVERNED_15M_REQUEST_CEILING,
        governed_requests_per_token=GOVERNED_REQUESTS_PER_TOKEN,
    )
    if source["status"] != "READY" or dependency.status != "READY":
        raise OperationalMemoryFactoryError("source or dependency preflight is not READY")
    if budget["status"] != "READY":
        raise OperationalMemoryFactoryError(
            "holder budget preflight is not READY: " + ";".join(budget["issues"])
        )

    connection = _read_only(path)
    try:
        migrations = tuple(
            str(row[0]) for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY version"
            ).fetchall()
        )
        expected = tuple(
            item.name for item in sorted(migration_runner.MIGRATIONS_DIR.glob("*.sql"))
        )
        integrity = tuple(
            str(row[0]) for row in connection.execute("PRAGMA integrity_check").fetchall()
        )
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        active = _active_counts(connection)
        locked = _locked_capability_counts(connection)
        historical_audit = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_paper_audit_reports "
                "WHERE paper_position_id IS NULL"
            ).fetchone()[0]
        )
    finally:
        connection.close()
    if migrations != expected or len(migrations) != EXPECTED_MIGRATION_COUNT:
        raise OperationalMemoryFactoryError("canonical migration ledger mismatch")
    if integrity != ("ok",) or foreign_keys:
        raise OperationalMemoryFactoryError("database integrity or foreign keys failed")
    if any(active.values()):
        raise OperationalMemoryFactoryError(f"active operational state exists: {active}")
    _validate_locked_baseline(locked)
    if historical_audit != 1:
        raise OperationalMemoryFactoryError("historical paper-audit evidence drifted")

    return {
        "status": "V2_9_8_OPERATIONAL_PREFLIGHT_READY",
        "database_path": str(path),
        "database_sha256": _sha256(path),
        "migration_count": len(migrations),
        "latest_migration": migrations[-1],
        "integrity": "ok",
        "foreign_key_violations": 0,
        "active_counts": active,
        "locked_capability_counts": locked,
        "historical_paper_audit_rows_preserved": historical_audit,
        "source_contract": {
            "status": source["status"],
            "external_requests": source["external_requests"],
            "secret_material_recorded": source["secret_material_recorded"],
        },
        "holder_budget_preflight": {
            "status": budget["status"],
            "expected": budget["expected"],
            "issues": budget["issues"],
            "source_calls": budget["source_calls"],
        },
        "dependency_preflight": dependency.to_dict(),
        "git_provenance": provenance,
        "policy": {
            "token_capacity": TOKEN_CAPACITY,
            "main_window": MAIN_WINDOW,
            "main_window_seconds": MAIN_WINDOW_SECONDS,
            "locked_windows": LOCKED_WINDOWS,
            "support_5m_only": True,
            "automatic_retries": AUTOMATIC_RETRIES,
            "restart_created": False,
            "successor_created": False,
        },
        "ceilings": {
            "campaigns": 1,
            "cycles": 1,
            "duration_seconds": TOTAL_DURATION_SECONDS,
            "discovery_requests": DISCOVERY_REQUEST_CEILING,
            "governed_15m_requests": GOVERNED_15M_REQUEST_CEILING,
            "governed_requests_per_token": GOVERNED_REQUESTS_PER_TOKEN,
            "scheduler_rows": SCHEDULER_ROW_CEILING,
            "admission_operations": ADMISSION_OPERATION_CEILING,
            "storage_bytes": STORAGE_BYTE_CEILING,
            "failures": FAILURE_CEILING,
        },
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "database_writes": 0,
    }


def _artifact_paths(execution_id: str) -> dict[str, Path]:
    root = (ARTIFACT_ROOT / execution_id).resolve()
    return {
        "root": root,
        "backup": root / "printer_v1.pre-campaign.backup.sqlite3",
        "restore": root / "printer_v1.restore-rehearsal.sqlite3",
        "reports": root / "reports",
        "lock": root / "campaign.lease.lock",
        "stdout": root / "stdout.log",
        "stderr": root / "stderr.log",
        "summary": root / "terminal-summary.json",
    }


def _create_campaign_command(
    *,
    execution_id: str,
    paths: Mapping[str, Path],
    preflight: Mapping[str, Any],
    backup: Mapping[str, Any],
    now: str,
) -> tuple[AbstractCampaignCommand, str]:
    campaign_id = f"{execution_id}-campaign"
    configuration_id = f"{execution_id}-configuration"
    run_id = f"{execution_id}-campaign-run"
    cycle_id = f"{execution_id}-cycle"
    report_id = f"{execution_id}-report"
    report_identity = report_path_identity(paths["reports"])
    ceilings = CampaignCeilings(
        campaign_count=1,
        cycle_count=1,
        duration_seconds=TOTAL_DURATION_SECONDS,
        source_calls=ADMISSION_OPERATION_CEILING,
        scheduler_work=SCHEDULER_ROW_CEILING,
        storage_bytes=STORAGE_BYTE_CEILING,
        failures=FAILURE_CEILING,
    )
    configuration = {
        "token_capacity": TOKEN_CAPACITY,
        "ceilings": asdict(ceilings),
        "main_window": MAIN_WINDOW,
        "main_window_seconds": MAIN_WINDOW_SECONDS,
        "continuous_first_hour": False,
        "continuous_four_hour": False,
        "support_5m_only": True,
        "automatic_retries": AUTOMATIC_RETRIES,
        "report_directory_identity": report_identity,
        "backup_preflight_references": {
            "preflight_status": "READY",
            "source_identity": backup["source_identity"],
            "backup_sha256": backup["backup_hash"],
            "required_migration": "032_campaign_ownership_schema.sql",
            "latest_migration": backup["latest_rehearsed_migration"],
        },
        "inner_15m_ceilings": {
            "discovery_requests": DISCOVERY_REQUEST_CEILING,
            "governed_requests": GOVERNED_15M_REQUEST_CEILING,
            "governed_requests_per_token": GOVERNED_REQUESTS_PER_TOKEN,
            "scheduler_rows": SCHEDULER_ROW_CEILING,
        },
    }
    target_identity = f"sha256:{preflight['database_sha256']}"
    created = create_campaign(
        AUTHORITATIVE_DB,
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        configuration=configuration,
        launch_provenance=preflight["git_provenance"],
        db_mode=DB_MODE_OPERATIONAL_PERSISTENT,
        db_target_identity=target_identity,
        policy_version=POLICY_VERSION,
        campaign_state="DRAFT",
    )
    connection = sqlite3.connect(AUTHORITATIVE_DB)
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        create_campaign_run(
            connection, campaign_id=campaign_id, run_id=run_id,
            run_ordinal=1, now=now,
        )
        with connection:
            connection.execute(
                """INSERT INTO printer_memory_factory_campaign_cycles(
                       cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,
                       created_at,updated_at
                   ) VALUES (?,?,?,1,'PLANNED',?,?)""",
                (cycle_id, campaign_id, run_id, now, now),
            )
            connection.execute(
                "UPDATE printer_memory_factory_campaigns "
                "SET campaign_state='RUNNING',updated_at=? WHERE campaign_id=?",
                (now, campaign_id),
            )
            connection.execute(
                "UPDATE printer_memory_factory_campaign_runs "
                "SET run_state='RUNNING',updated_at=? WHERE run_id=?",
                (now, run_id),
            )
    finally:
        connection.close()
    return (
        AbstractCampaignCommand(
            mode=CAMPAIGN_MODE,
            db_path=AUTHORITATIVE_DB,
            db_target_identity=target_identity,
            campaign_id=campaign_id,
            configuration_id=configuration_id,
            configuration_hash=str(created["configuration_hash"]),
            policy_version=POLICY_VERSION,
            token_capacity=TOKEN_CAPACITY,
            ceilings=ceilings,
            report_directory=paths["reports"],
            report_directory_identity=report_identity,
            launch_git_provenance=preflight["git_provenance"],
            run_id=run_id,
            report_id=report_id,
            supervision_id=f"{execution_id}-supervision",
            owner_id=f"{execution_id}-owner",
            lease_lock_path=paths["lock"],
        ),
        cycle_id,
    )


class _CampaignHeartbeat:
    """Background lease renewer. Never performs terminal cleanup (V2-9.8B.2)."""

    def __init__(self, command: AbstractCampaignCommand) -> None:
        self.command = command
        self.stop_event = threading.Event()
        self.failure_event = threading.Event()
        self._failure_lock = threading.Lock()
        self._failure: dict[str, Any] | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        def loop() -> None:
            while not self.stop_event.wait(HEARTBEAT_SECONDS):
                try:
                    result = renew_campaign_lease(
                        self.command.db_path,
                        supervision_id=self.command.supervision_id,
                        campaign_id=self.command.campaign_id,
                        configuration_id=self.command.configuration_id,
                        run_id=self.command.run_id,
                        owner_id=self.command.owner_id,
                        lease_seconds=LEASE_SECONDS,
                    )
                except BaseException as exc:  # signal main; never cleanup here
                    with self._failure_lock:
                        self._failure = {
                            "renewal_confirmed": False,
                            "renewal_error": f"{type(exc).__name__}:{exc}",
                            "renewal_error_type": type(exc).__name__,
                            "terminal_cleanup_performed": False,
                            "signal_main_coordinator": True,
                            "suggested_terminal_cause": "LEASE_RENEWAL_UNCONFIRMED",
                        }
                    self.failure_event.set()
                    break
                if not result.get("renewal_confirmed"):
                    with self._failure_lock:
                        self._failure = dict(result)
                        self._failure["terminal_cleanup_performed"] = bool(
                            result.get("terminal_cleanup_performed")
                        )
                    self.failure_event.set()
                    break
        self.thread = threading.Thread(
            target=loop, daemon=True, name="campaign-heartbeat"
        )
        self.thread.start()

    def poll_failure(self) -> dict[str, Any] | None:
        with self._failure_lock:
            if self._failure is None:
                return None
            return dict(self._failure)

    def stop(self) -> None:
        """Stop renewals and wait long enough for an in-flight renew to finish."""
        self.stop_event.set()
        if self.thread is not None:
            # Join covers one heartbeat interval plus the supervision busy budget
            # so cleanup does not race a mid-renew write lock.
            self.thread.join(timeout=HEARTBEAT_SECONDS + 15)


def _connect_query_only(path: Path) -> sqlite3.Connection:
    """Read-only connection for the authoritative DB or disposable fixtures."""
    resolved = Path(path).resolve()
    if resolved == AUTHORITATIVE_DB.resolve() and resolved.is_file():
        return _read_only(resolved)
    connection = sqlite3.connect(
        f"file:{resolved.as_posix()}?mode=ro", uri=True, timeout=0.0
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def _existing_first_terminal_cause(command: AbstractCampaignCommand) -> str | None:
    connection = _connect_query_only(Path(command.db_path))
    try:
        row = connection.execute(
            """SELECT c.first_terminal_cause AS campaign_cause,
                      s.first_terminal_cause AS supervision_cause
               FROM printer_memory_factory_campaigns AS c
               LEFT JOIN printer_memory_factory_campaign_supervision AS s
                 ON s.campaign_id=c.campaign_id AND s.run_id=?
               WHERE c.campaign_id=?""",
            (command.run_id, command.campaign_id),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    return str(row["campaign_cause"] or row["supervision_cause"] or "").strip() or None


def _is_sqlite_locked_error(exc: BaseException) -> bool:
    if isinstance(exc, sqlite3.OperationalError):
        text = str(exc).lower()
        return "locked" in text or "busy" in text
    text = str(exc).lower()
    return "database is locked" in text or "database is busy" in text


def _with_sqlite_busy_retry(label: str, operation, *, attempts: int = 8, base_sleep: float = 0.05):
    """Bounded retry for transient SQLite lock contention during terminalization."""
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except BaseException as exc:
            last_error = exc
            if not _is_sqlite_locked_error(exc) or attempt >= attempts:
                raise
            time.sleep(base_sleep * attempt)
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"{label}: busy retry exhausted without result")


def _latest_campaign_source_total(db_path: Path | str | None = None) -> int | None:
    """Best-effort durable campaign source total from the holder ledger.

    Prefers the latest supervision run's ledger row. Returns None when unavailable
    so pre-ledger faults can still report honest zeros.
    """
    path = Path(db_path) if db_path is not None else AUTHORITATIVE_DB
    try:
        resolved = path.resolve()
        if resolved == AUTHORITATIVE_DB.resolve() and resolved.is_file():
            connection = _read_only(resolved)
        else:
            if not resolved.is_file():
                return None
            connection = sqlite3.connect(
                f"file:{resolved.as_posix()}?mode=ro", uri=True, timeout=0.0
            )
            connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                """SELECT l.governed_requests
                   FROM printer_holder_campaign_operation_ledgers AS l
                   JOIN printer_memory_factory_campaign_supervision AS s
                     ON s.run_id = l.run_id
                   ORDER BY s.created_at DESC, s.supervision_id DESC
                   LIMIT 1"""
            ).fetchone()
            if row is None:
                return None
            return int(row["governed_requests"])
        finally:
            connection.close()
    except Exception:
        return None


def _terminalize_initialized_failure(
    *,
    original_exception: BaseException,
    command: AbstractCampaignCommand,
    cycle_id: str,
    execution_id: str,
    paths: Mapping[str, Path],
    launch_git_provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Attempt every canonical terminal owner without replacing the first fault."""
    original_cause = f"OPERATIONAL_CAMPAIGN_FAILED:{type(original_exception).__name__}"
    cause = _existing_first_terminal_cause(command) or original_cause
    closure_errors: list[str] = []
    reconciliation: Mapping[str, Any] = {
        "reconciled": False,
        "restart_created": False,
        "successor_created": False,
    }
    cleanup: Mapping[str, Any] = {"cleanup_completed": False}
    # V2-9.8B.10: retry cleanup/report under transient SQLite lock contention so
    # heartbeat or a just-closed factory connection cannot leave RUNNING residue.
    try:
        cleanup = _with_sqlite_busy_retry(
            "cleanup",
            lambda: cleanup_campaign_supervision(
                command.db_path,
                supervision_id=command.supervision_id,
                campaign_id=command.campaign_id,
                configuration_id=command.configuration_id,
                run_id=command.run_id,
                owner_id=command.owner_id,
                terminal_status="FAILED",
                first_terminal_cause=cause,
            ),
        )
    except BaseException as exc:  # report still has to be attempted
        closure_errors.append(f"cleanup:{type(exc).__name__}:{exc}")
    try:
        reconciliation = _with_sqlite_busy_retry(
            "reconciliation",
            lambda: reconcile_campaign_terminal(
                command.db_path,
                campaign_id=command.campaign_id,
                run_id=command.run_id,
                cycle_id=cycle_id,
                terminal_cause=cause,
                run_status="FAILED",
                factory_run_id=None,
                lifecycle_started=False,
                now=_iso(),
            ),
        )
    except BaseException as exc:  # preserve and continue to report owner
        closure_errors.append(f"reconciliation:{type(exc).__name__}:{exc}")
    reporting = assemble_campaign_terminal_reporting(
        command.db_path,
        run_id=command.run_id,
        cycle_id=cycle_id,
        terminal_cause=cause,
        lifecycle={},
        required_token_capacity=TOKEN_CAPACITY,
    )
    payload = build_campaign_terminal_report(
        campaign_id=command.campaign_id,
        configuration_id=command.configuration_id,
        run_id=command.run_id,
        cycle_id=cycle_id,
        report_id=command.report_id,
        factory_run_id=None,
        execution_id=execution_id,
        terminal_status="FAILED",
        terminal_cause=cause,
        run_status="FAILED",
        lifecycle_started=False,
        reconciliation=reconciliation,
        forbidden_deltas={},
        launch_git_provenance=launch_git_provenance,
        campaign_activity=reporting.get("campaign_activity"),
        blocked_supply=reporting.get("blocked_supply"),
        campaign_source_calls=reporting.get("campaign_source_calls"),
        campaign_scheduler_calls=reporting.get("campaign_scheduler_calls"),
        candidates_observed=reporting.get("candidates_observed"),
        candidates_validated=reporting.get("candidates_validated"),
        eligible_candidates=reporting.get("eligible_candidates"),
        required_token_capacity=reporting.get("required_token_capacity"),
        blocked_supply_reason=reporting.get("blocked_supply_reason"),
    )
    report: Mapping[str, Any] = {"report_written": False}
    try:
        report = _with_sqlite_busy_retry(
            "report",
            lambda: write_campaign_terminal_report(
                command.db_path,
                paths["reports"],
                report_id=command.report_id,
                campaign_id=command.campaign_id,
                configuration_id=command.configuration_id,
                report=payload,
            ),
        )
    except BaseException as exc:
        closure_errors.append(f"report:{type(exc).__name__}:{exc}")
    terminal = {
        "status": "OPERATIONAL_CAMPAIGN_TERMINAL_FAILURE",
        "execution_id": execution_id,
        "campaign_id": command.campaign_id,
        "first_terminal_cause": cause,
        "original_exception_type": type(original_exception).__name__,
        "reconciliation": dict(reconciliation),
        "cleanup": dict(cleanup),
        "report": dict(report),
        "closure_errors": tuple(closure_errors),
        "restart_created": False,
        "successor_created": False,
        "campaign_source_calls": reporting.get("campaign_source_calls"),
    }
    try:
        paths["summary"].write_text(
            json.dumps(terminal, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
    except BaseException as exc:
        closure_errors.append(f"summary:{type(exc).__name__}:{exc}")
    if closure_errors:
        original_exception.add_note(
            "post-initialization terminalization diagnostics: "
            + " | ".join(closure_errors)
        )
    return terminal


def run_operational_campaign(
    *,
    operator_approved: bool,
    owner: Any | None = None,
    pump_transport: Any | None = None,
    secondary_transport: Any | None = None,
    migration_transport: Any | None = None,
) -> dict[str, Any]:
    """Run one bounded persistent 15m campaign. V2-9.8A must not call this."""
    if not operator_approved:
        raise OperationalMemoryFactoryError("explicit operator approval is required")
    preflight = build_activation_preflight()
    execution_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid.uuid4().hex[:12]
    )
    paths = _artifact_paths(execution_id)
    paths["root"].mkdir(parents=True, exist_ok=False)
    paths["reports"].mkdir()
    paths["stdout"].touch(exist_ok=False)
    paths["stderr"].touch(exist_ok=False)
    backup = operational_backup_restore_preflight(
        AUTHORITATIVE_DB,
        expected_source_path=AUTHORITATIVE_DB,
        expected_source_identity=f"sha256:{preflight['database_sha256']}",
        backup_path=paths["backup"],
        disposable_restore_root=paths["root"],
        restore_path=paths["restore"],
    )
    now = _iso()
    command, cycle_id = _create_campaign_command(
        execution_id=execution_id, paths=paths, preflight=preflight,
        backup=backup, now=now,
    )
    heartbeat: _CampaignHeartbeat | None = None
    try:
        acquire_campaign_supervision(
            command.db_path,
            lock_path=command.lease_lock_path,
            supervision_id=command.supervision_id,
            campaign_id=command.campaign_id,
            configuration_id=command.configuration_id,
            run_id=command.run_id,
            owner_id=command.owner_id,
            lease_seconds=LEASE_SECONDS,
        )
        heartbeat = _CampaignHeartbeat(command)
        heartbeat.start()
        active_owner = owner or AuthoritativeLiveOperationalCampaignOwner()
        active_pump = pump_transport or OneShotUrllibPumpTransport(FREE_PUBLIC_SOLANA_RPC)
        active_secondary = secondary_transport or OneShotUrllibSecondaryTransport()
        if migration_transport is None:
            from printer_v1.sources.pumpportal import build_pumpportal_migration_transport
            migration_transport = build_pumpportal_migration_transport(
                max_events=4, duration_seconds=120.0, connect_timeout_seconds=10.0,
            )

        def cancellation_probe() -> str | None:
            hb_failure = heartbeat.poll_failure() if heartbeat is not None else None
            if hb_failure is not None:
                return str(
                    hb_failure.get("suggested_terminal_cause")
                    or "LEASE_RENEWAL_UNCONFIRMED"
                )
            connection = _read_only()
            try:
                row = connection.execute(
                    """SELECT supervision_state,cancellation_reason
                       FROM printer_memory_factory_campaign_supervision
                       WHERE supervision_id=? AND campaign_id=? AND run_id=?""",
                    (command.supervision_id, command.campaign_id, command.run_id),
                ).fetchone()
            finally:
                connection.close()
            if row is None:
                return "CAMPAIGN_SUPERVISION_MISSING"
            if row["supervision_state"] == "STOPPING":
                return str(
                    row["cancellation_reason"]
                    or "OPERATOR_REQUESTED_COOPERATIVE_STOP"
                )
            if row["supervision_state"] == "TERMINAL":
                return "CAMPAIGN_SUPERVISION_TERMINAL"
            return None

        result = active_owner.run_operational(
            command=command,
            pump_transport=active_pump,
            secondary_transport=active_secondary,
            source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, True),
            central_scheduler=OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
            selection_seed=execution_id,
            cycle_id=cycle_id,
            cycle_cutoff=now,
            evaluated_at=now,
            backup_path=paths["backup"],
            lifecycle_kwargs={
                "total_duration_seconds": TOTAL_DURATION_SECONDS,
                "launch_provenance": preflight["git_provenance"],
                "cancellation_probe": cancellation_probe,
            },
            migration_transport=migration_transport,
            graduated_supply_kwargs=dict(OPERATIONAL_GRADUATED_SUPPLY_KWARGS),
            fifteen_minute_only=True,
        )
        # Heartbeat never terminalizes. Main coordinator observes failure signal.
        heartbeat_failure = heartbeat.poll_failure() if heartbeat is not None else None
        if heartbeat is not None:
            heartbeat.stop()
            heartbeat = None
        lifecycle = dict(result.lifecycle)
        cause = str(
            lifecycle.get("first_terminal_cause")
            or lifecycle.get("stop_reason")
            or "PRE_LIFECYCLE_GOVERNED_SAFE_STOP"
        )
        if heartbeat_failure is not None and lifecycle.get("run_status") not in {
            "FAILED", "CANCELLED", "TERMINAL_FAILED",
        }:
            # Prefer an existing lifecycle terminal cause; otherwise surface the
            # heartbeat signal so the main path can cleanup once.
            if cause in {"PRE_LIFECYCLE_GOVERNED_SAFE_STOP", ""}:
                cause = str(
                    heartbeat_failure.get("suggested_terminal_cause")
                    or "LEASE_RENEWAL_UNCONFIRMED"
                )
                lifecycle["run_status"] = "FAILED"
                lifecycle["first_terminal_cause"] = cause
                lifecycle["heartbeat_failure"] = dict(heartbeat_failure)
        cleanup = cleanup_campaign_supervision(
            command.db_path,
            supervision_id=command.supervision_id,
            campaign_id=command.campaign_id,
            configuration_id=command.configuration_id,
            run_id=command.run_id,
            owner_id=command.owner_id,
            terminal_status=(
                "FAILED" if lifecycle.get("run_status") == "FAILED" else "COMPLETED"
            ),
            first_terminal_cause=cause,
        )
        reconciliation = reconcile_campaign_terminal(
            command.db_path,
            campaign_id=command.campaign_id,
            run_id=command.run_id,
            cycle_id=cycle_id,
            terminal_cause=cause,
            run_status=lifecycle.get("run_status"),
            factory_run_id=str(lifecycle.get("run_id") or "") or None,
            lifecycle_started=bool(result.lifecycle_started),
            now=_iso(),
        )
        reporting = assemble_campaign_terminal_reporting(
            command.db_path,
            run_id=command.run_id,
            cycle_id=cycle_id,
            terminal_cause=cause,
            lifecycle=lifecycle,
            required_token_capacity=TOKEN_CAPACITY,
        )
        payload = build_campaign_terminal_report(
            campaign_id=command.campaign_id,
            configuration_id=command.configuration_id,
            run_id=command.run_id,
            cycle_id=cycle_id,
            report_id=command.report_id,
            factory_run_id=str(lifecycle.get("run_id") or "") or None,
            execution_id=execution_id,
            terminal_status=str(cleanup.get("terminal_status") or "COMPLETED"),
            terminal_cause=cause,
            run_status=lifecycle.get("run_status"),
            lifecycle_started=bool(result.lifecycle_started),
            reconciliation=reconciliation,
            forbidden_deltas=dict(lifecycle.get("forbidden_deltas") or {}),
            launch_git_provenance=preflight["git_provenance"],
            campaign_activity=reporting.get("campaign_activity"),
            blocked_supply=reporting.get("blocked_supply"),
            campaign_source_calls=reporting.get("campaign_source_calls"),
            campaign_scheduler_calls=reporting.get("campaign_scheduler_calls"),
            candidates_observed=reporting.get("candidates_observed"),
            candidates_validated=reporting.get("candidates_validated"),
            eligible_candidates=reporting.get("eligible_candidates"),
            required_token_capacity=reporting.get("required_token_capacity"),
            blocked_supply_reason=reporting.get("blocked_supply_reason"),
        )
        report = write_campaign_terminal_report(
            command.db_path,
            paths["reports"],
            report_id=command.report_id,
            campaign_id=command.campaign_id,
            configuration_id=command.configuration_id,
            report=payload,
        )
        terminal = {
            "status": "OPERATIONAL_CAMPAIGN_TERMINAL",
            "execution_id": execution_id,
            "campaign_id": command.campaign_id,
            "run_status": lifecycle.get("run_status"),
            "first_terminal_cause": cause,
            "report": report,
            "campaign_source_calls": report.get("campaign_source_calls"),
            "campaign_scheduler_calls": report.get("campaign_scheduler_calls"),
            "candidates_observed": report.get("candidates_observed"),
            "candidates_validated": report.get("candidates_validated"),
            "eligible_candidates": report.get("eligible_candidates"),
            "required_token_capacity": report.get("required_token_capacity")
            or TOKEN_CAPACITY,
            "blocked_supply_reason": report.get("blocked_supply_reason"),
            "token_capacity": TOKEN_CAPACITY,
            "main_window": MAIN_WINDOW,
            "support_5m_only": True,
            "restart_created": False,
            "successor_created": False,
        }
        paths["summary"].write_text(
            json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return terminal
    except BaseException as exc:
        if heartbeat is not None:
            heartbeat.stop()
        try:
            _terminalize_initialized_failure(
                original_exception=exc,
                command=command,
                cycle_id=cycle_id,
                execution_id=execution_id,
                paths=paths,
                launch_git_provenance=preflight["git_provenance"],
            )
        except BaseException as closure_exc:
            exc.add_note(
                "post-initialization terminalization coordinator fault: "
                f"{type(closure_exc).__name__}:{closure_exc}"
            )
        raise
    finally:
        if heartbeat is not None:
            heartbeat.stop()


def _latest_supervision(connection: sqlite3.Connection) -> sqlite3.Row:
    row = connection.execute(
        """SELECT * FROM printer_memory_factory_campaign_supervision
           ORDER BY created_at DESC, supervision_id DESC LIMIT 1"""
    ).fetchone()
    if row is None:
        raise OperationalMemoryFactoryError("no operational campaign supervision exists")
    return row


def operational_status() -> dict[str, Any]:
    connection = _read_only()
    try:
        row = _latest_supervision(connection)
    finally:
        connection.close()
    result = inspect_campaign_supervision(
        AUTHORITATIVE_DB,
        supervision_id=row["supervision_id"],
        campaign_id=row["campaign_id"],
        configuration_id=row["configuration_id"],
        run_id=row["run_id"],
        owner_id=row["owner_id"],
    )
    return {
        "mode": "STATUS",
        "status": result,
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "database_writes": 0,
    }


def cooperative_stop(*, operator_approved: bool) -> dict[str, Any]:
    if not operator_approved:
        raise OperationalMemoryFactoryError("explicit operator approval is required")
    connection = _read_only()
    try:
        row = _latest_supervision(connection)
    finally:
        connection.close()
    result = request_campaign_cancellation(
        AUTHORITATIVE_DB,
        supervision_id=row["supervision_id"],
        campaign_id=row["campaign_id"],
        configuration_id=row["configuration_id"],
        run_id=row["run_id"],
        owner_id=row["owner_id"],
        reason="OPERATOR_REQUESTED_COOPERATIVE_STOP",
    )
    return {
        "mode": "COOPERATIVE_STOP",
        "result": result,
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "restart_created": False,
        "successor_created": False,
    }


def recover_orphan(*, operator_approved: bool) -> dict[str, Any]:
    """Run the one exact V2-9.8B.1 operator-approved orphan recovery."""
    paths = production_recovery_paths()
    return recover_exact_orphan(
        operator_approved=operator_approved,
        current_db=paths["current_db"],
        pre_campaign_backup=paths["pre_campaign_backup"],
        artifact_root=paths["artifact_root"],
        recovery_root=paths["recovery_root"],
    )


def report_only() -> dict[str, Any]:
    connection = _read_only()
    try:
        row = connection.execute(
            """SELECT r.report_id,r.campaign_id,r.configuration_id,
                      c.configuration_json
               FROM printer_memory_factory_campaign_reports AS r
               JOIN printer_memory_factory_campaign_configurations AS c
                 ON c.configuration_id=r.configuration_id
               WHERE r.report_state='REPORT_TERMINAL'
               ORDER BY r.created_at DESC,r.report_id DESC LIMIT 1"""
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise OperationalMemoryFactoryError("no terminal operational report exists")
    configuration = json.loads(str(row["configuration_json"]))
    report_dir = None
    for candidate in ARTIFACT_ROOT.glob("*/reports"):
        if report_path_identity(candidate) == configuration["report_directory_identity"]:
            report_dir = candidate
            break
    if report_dir is None:
        raise OperationalMemoryFactoryError("terminal report directory is unavailable")
    replay = replay_campaign_terminal_report(
        AUTHORITATIVE_DB,
        report_dir,
        report_id=row["report_id"],
        campaign_id=row["campaign_id"],
        configuration_id=row["configuration_id"],
    )
    return {
        "mode": "REPORT_ONLY",
        "replay": replay,
        # Original campaign totals from the stored terminal report.
        "campaign_source_calls": replay.get("campaign_source_calls"),
        "campaign_scheduler_calls": replay.get("campaign_scheduler_calls"),
        "candidates_observed": replay.get("candidates_observed"),
        "candidates_validated": replay.get("candidates_validated"),
        "eligible_candidates": replay.get("eligible_candidates"),
        "required_token_capacity": replay.get("required_token_capacity"),
        "blocked_supply_reason": replay.get("blocked_supply_reason"),
        "blocked_supply": replay.get("blocked_supply"),
        # Report-only itself performs no new Source Governor / Scheduler work.
        "replay_new_source_calls": 0,
        "replay_new_scheduler_calls": 0,
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "database_writes": 0,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Printer V1 bounded persistent 15m Memory Factory command."
    )
    parser.add_argument(
        "mode",
        choices=(
            "preflight-only", "run", "status", "cooperative-stop",
            "recover-orphan", "report-only",
        ),
    )
    parser.add_argument("--operator-approved", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.mode == "preflight-only":
            result = build_activation_preflight()
        elif args.mode == "run":
            result = run_operational_campaign(operator_approved=args.operator_approved)
        elif args.mode == "status":
            result = operational_status()
        elif args.mode == "cooperative-stop":
            result = cooperative_stop(operator_approved=args.operator_approved)
        elif args.mode == "recover-orphan":
            result = recover_orphan(operator_approved=args.operator_approved)
        else:
            result = report_only()
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        # V2-9.8B.10: when a campaign already wrote a holder ledger, surface that
        # durable total instead of hard-coding zero (which hid 18 ops on the
        # audited IntegrityError path).
        campaign_source_calls = _latest_campaign_source_total()
        print(
            json.dumps(
                {
                    "status": "OPERATIONAL_COMMAND_BLOCKED",
                    "error_type": type(exc).__name__,
                    "campaign_source_calls": campaign_source_calls,
                    "source_calls": (
                        int(campaign_source_calls)
                        if campaign_source_calls is not None
                        else 0
                    ),
                    "restart_created": False,
                    "successor_created": False,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "AUTHORITATIVE_DB",
    "EXPECTED_MIGRATION_COUNT",
    "LOCKED_WINDOWS",
    "MAIN_WINDOW",
    "OPERATIONAL_GRADUATED_SUPPLY_KWARGS",
    "TOKEN_CAPACITY",
    "_latest_campaign_source_total",
    "_terminalize_initialized_failure",
    "_with_sqlite_busy_retry",
    "build_activation_preflight",
    "cooperative_stop",
    "main",
    "operational_status",
    "recover_orphan",
    "report_only",
    "run_operational_campaign",
]

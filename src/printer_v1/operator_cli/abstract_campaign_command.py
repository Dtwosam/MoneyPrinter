"""Internal V2-9.7D campaign and report-only command handlers.

This module deliberately exposes no shell parser or runnable entry point.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Callable, Mapping

from printer_v1.db import migrate as migration_runner
from printer_v1.operator_cli.campaign_supervision import (
    acquire_campaign_supervision,
    cleanup_campaign_supervision,
    request_campaign_cancellation,
)
from printer_v1.operator_cli.final_campaign_report import (
    LOCKED_CAPABILITY_TABLES,
    persist_final_campaign_report,
)
from printer_v1.operator_cli.git_provenance import (
    GitProvenanceError,
    validate_launch_provenance,
)
from printer_v1.operator_cli.zero_source_campaign_replay import (
    replay_terminal_campaign_report,
)


CAMPAIGN_MODE = "BOUNDED_CAMPAIGN"
REPORT_ONLY_MODE = "REPORT_ONLY"
SOURCE_GOVERNOR_OWNER = "SOURCE_GOVERNOR"
CENTRAL_SCHEDULER_OWNER = "CENTRAL_SCHEDULER"
_MODES = frozenset({CAMPAIGN_MODE, REPORT_ONLY_MODE})
_TERMINAL_STATUSES = frozenset(
    {"COMPLETED", "FAILED", "CANCELLED", "LEASE_RENEWAL_UNCONFIRMED"}
)


class AbstractCommandError(RuntimeError):
    """Fail-closed abstract command contract violation."""


@dataclass(frozen=True)
class CampaignCeilings:
    campaign_count: int
    cycle_count: int
    duration_seconds: int
    source_calls: int
    scheduler_work: int
    storage_bytes: int
    failures: int

    def validate(self) -> None:
        values = asdict(self)
        if any(type(value) is not int or value <= 0 for value in values.values()):
            raise AbstractCommandError("all campaign ceilings must be finite positive integers")
        if self.campaign_count != 1:
            raise AbstractCommandError("one command may own exactly one bounded campaign")


@dataclass(frozen=True)
class LockedCapabilityRequest:
    retrieval: bool = False
    decisions: bool = False
    buy_sell_hold: bool = False
    positions: bool = False
    trades: bool = False
    audits: bool = False
    pnl: bool = False

    def validate(self) -> None:
        if any(type(value) is not bool for value in asdict(self).values()):
            raise AbstractCommandError("locked capability requests must be booleans")
        if any(asdict(self).values()):
            raise AbstractCommandError("locked capability activation is forbidden")


@dataclass(frozen=True)
class OwnerPort:
    owner_kind: str
    available: bool


@dataclass(frozen=True)
class CampaignExecutionResult:
    terminal_status: str
    first_terminal_cause: str
    cancellation_reason: str | None = None
    cycles: int = 0
    duration_seconds: int = 0
    source_calls: int = 0
    scheduler_work: int = 0
    storage_bytes: int = 0
    failures: int = 0
    source_governor_used: bool = True
    central_scheduler_used: bool = True
    selective_continuation_preserved: bool = True
    support_5m_only: bool = True
    successor_created: bool = False
    restart_created: bool = False


@dataclass(frozen=True)
class AbstractCampaignCommand:
    mode: str
    db_path: Path
    db_target_identity: str
    campaign_id: str
    configuration_id: str
    configuration_hash: str
    policy_version: str
    token_capacity: int
    ceilings: CampaignCeilings
    report_directory: Path
    report_directory_identity: str
    launch_git_provenance: Mapping[str, Any]
    run_id: str
    report_id: str
    supervision_id: str = ""
    owner_id: str = ""
    lease_lock_path: Path | None = None
    report_hash: str | None = None
    locked_capabilities: LockedCapabilityRequest = LockedCapabilityRequest()


@dataclass(frozen=True)
class CommandServices:
    source_governor: OwnerPort
    central_scheduler: OwnerPort
    execute_campaign: Callable[..., CampaignExecutionResult]
    acquire: Callable[..., Mapping[str, Any]] = acquire_campaign_supervision
    cancel: Callable[..., Mapping[str, Any]] = request_campaign_cancellation
    cleanup: Callable[..., Mapping[str, Any]] = cleanup_campaign_supervision
    persist_report: Callable[..., Mapping[str, Any]] = persist_final_campaign_report
    replay: Callable[..., Mapping[str, Any]] = replay_terminal_campaign_report


def report_path_identity(path: str | Path) -> str:
    """Return the immutable identity used for an explicit report directory."""
    resolved = str(Path(path).resolve()).casefold().encode("utf-8")
    return "path-sha256:" + hashlib.sha256(resolved).hexdigest()


def _required(value: object, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise AbstractCommandError(f"{label} is required")
    return text


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    )


def _read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise AbstractCommandError(f"database missing: {path}")
    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=0.0
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def _locked_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        for table in LOCKED_CAPABILITY_TABLES
    }


def _validate_report_directory(command: AbstractCampaignCommand) -> None:
    directory = command.report_directory.resolve()
    if not directory.is_dir() or not os.access(directory, os.W_OK):
        raise AbstractCommandError("report directory is unavailable or not writable")
    if report_path_identity(directory) != command.report_directory_identity:
        raise AbstractCommandError("report directory identity mismatch")
    if directory == command.db_path.resolve() or command.db_path.resolve() in directory.parents:
        raise AbstractCommandError("report directory cannot resolve inside the database target")


def _validate_configuration(
    command: AbstractCampaignCommand, configuration_json: str
) -> None:
    try:
        configuration = json.loads(configuration_json)
    except json.JSONDecodeError as exc:
        raise AbstractCommandError("stored campaign configuration is malformed") from exc
    expected = {
        "token_capacity": command.token_capacity,
        "ceilings": asdict(command.ceilings),
        "report_directory_identity": command.report_directory_identity,
    }
    if not isinstance(configuration, dict) or any(
        configuration.get(key) != value for key, value in expected.items()
    ):
        raise AbstractCommandError("immutable command configuration mismatch")
    backup = configuration.get("backup_preflight_references")
    latest_migration = sorted(
        migration_runner.MIGRATIONS_DIR.glob("*.sql")
    )[-1].name
    required = {
        "preflight_status": "READY",
        "required_migration": "032_campaign_ownership_schema.sql",
        "latest_migration": latest_migration,
    }
    if not isinstance(backup, dict) or any(backup.get(k) != v for k, v in required.items()):
        raise AbstractCommandError("verified backup/restore prerequisite is missing")
    for field in ("source_identity", "backup_sha256"):
        if not isinstance(backup.get(field), str) or not backup[field].strip():
            raise AbstractCommandError("verified backup/restore prerequisite is incomplete")


def preflight_abstract_command(command: AbstractCampaignCommand) -> dict[str, Any]:
    """Validate the command and stored ownership graph without writing."""
    if command.mode not in _MODES:
        raise AbstractCommandError("command mode is unsupported")
    for label in (
        "db_target_identity", "campaign_id", "configuration_id",
        "configuration_hash", "policy_version", "run_id", "report_id",
    ):
        _required(getattr(command, label), label)
    if command.token_capacity != 2:
        raise AbstractCommandError("token capacity must be exactly two")
    command.ceilings.validate()
    command.locked_capabilities.validate()
    _validate_report_directory(command)
    try:
        current_provenance = validate_launch_provenance(command.launch_git_provenance)
    except GitProvenanceError as exc:
        raise AbstractCommandError(str(exc)) from exc

    connection = _read_only(command.db_path.resolve())
    try:
        rows = connection.execute(
            """SELECT c.campaign_state,c.db_target_identity,c.policy_version,
                      cfg.configuration_hash,cfg.configuration_json,
                      cfg.launch_provenance_json,r.run_state
               FROM printer_memory_factory_campaigns AS c
               JOIN printer_memory_factory_campaign_configurations AS cfg
                 ON cfg.campaign_id=c.campaign_id AND cfg.configuration_id=?
               JOIN printer_memory_factory_campaign_runs AS r
                 ON r.campaign_id=c.campaign_id AND r.run_id=?
               WHERE c.campaign_id=?""",
            (command.configuration_id, command.run_id, command.campaign_id),
        ).fetchall()
        if len(rows) != 1:
            raise AbstractCommandError("campaign/configuration/run identity mismatch")
        row = rows[0]
        exact = {
            "db_target_identity": command.db_target_identity,
            "policy_version": command.policy_version,
            "configuration_hash": command.configuration_hash,
        }
        if any(row[key] != value for key, value in exact.items()):
            raise AbstractCommandError("campaign ownership or configuration identity mismatch")
        try:
            stored_provenance = validate_launch_provenance(
                json.loads(row["launch_provenance_json"])
            )
        except (GitProvenanceError, json.JSONDecodeError) as exc:
            raise AbstractCommandError("stored launch Git provenance is invalid") from exc
        if stored_provenance != current_provenance:
            raise AbstractCommandError("launch Git provenance identity mismatch")
        _validate_configuration(command, str(row["configuration_json"]))

        ledger = tuple(
            str(item[0]) for item in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY version"
            ).fetchall()
        )
        expected_ledger = tuple(
            migration.name for migration in sorted(
                migration_runner.MIGRATIONS_DIR.glob("*.sql")
            )
        )
        # Ledger must match the repository migration head exactly. After 7B.4C
        # the head includes 034_discovery_persistence_reconciliation.sql.
        if ledger != expected_ledger or not ledger:
            raise AbstractCommandError("database migration ledger is not canonical")

        leases = connection.execute(
            """SELECT supervision_state FROM printer_memory_factory_campaign_supervision
               WHERE campaign_id=? AND run_id=?""",
            (command.campaign_id, command.run_id),
        ).fetchall()
        active_lease_count = int(connection.execute(
            """SELECT COUNT(*) FROM printer_memory_factory_campaign_supervision
               WHERE supervision_state IN ('ACTIVE','STOPPING')"""
        ).fetchone()[0])
        if active_lease_count:
            raise AbstractCommandError("target database has an active or foreign lease")
        if command.mode == CAMPAIGN_MODE:
            if row["campaign_state"] != "RUNNING" or row["run_state"] != "RUNNING":
                raise AbstractCommandError("bounded campaign graph is not runnable")
            if leases:
                raise AbstractCommandError("campaign run already has lease history; resume is forbidden")
            slot_counts = tuple(
                int(item[0]) for item in connection.execute(
                    """SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots
                       WHERE campaign_id=? AND run_id=? GROUP BY cycle_id ORDER BY cycle_id""",
                    (command.campaign_id, command.run_id),
                ).fetchall()
            )
            if (
                not slot_counts
                or len(slot_counts) > command.ceilings.cycle_count
                or any(count != 2 for count in slot_counts)
            ):
                raise AbstractCommandError("every campaign cycle must have exactly two token slots")

        return {
            "preflight_state": "READY",
            "mode": command.mode,
            "migration_ledger": ledger,
            "locked_capability_counts": _locked_counts(connection),
            "database_writes": 0,
        }
    except sqlite3.Error as exc:
        raise AbstractCommandError(f"database preflight failed: {exc}") from exc
    finally:
        connection.close()


def _validate_services(services: CommandServices) -> None:
    if (
        services.source_governor.owner_kind != SOURCE_GOVERNOR_OWNER
        or not services.source_governor.available
    ):
        raise AbstractCommandError("Source Governor owner is unavailable")
    if (
        services.central_scheduler.owner_kind != CENTRAL_SCHEDULER_OWNER
        or not services.central_scheduler.available
    ):
        raise AbstractCommandError("Central Scheduler owner is unavailable")


def _validate_execution(
    result: CampaignExecutionResult, ceilings: CampaignCeilings
) -> None:
    if result.terminal_status not in _TERMINAL_STATUSES:
        raise AbstractCommandError("campaign executor returned an invalid terminal status")
    _required(result.first_terminal_cause, "first_terminal_cause")
    usage = {
        "cycle_count": result.cycles,
        "duration_seconds": result.duration_seconds,
        "source_calls": result.source_calls,
        "scheduler_work": result.scheduler_work,
        "storage_bytes": result.storage_bytes,
        "failures": result.failures,
    }
    limits = asdict(ceilings)
    if any(type(value) is not int or value < 0 or value > limits[key] for key, value in usage.items()):
        raise AbstractCommandError("campaign executor exceeded a finite ceiling")
    if not all((
        result.source_governor_used,
        result.central_scheduler_used,
        result.selective_continuation_preserved,
        result.support_5m_only,
    )):
        raise AbstractCommandError("campaign executor bypassed a committed owner or policy")
    if result.successor_created or result.restart_created:
        raise AbstractCommandError("successor and automatic restart are forbidden")


def request_abstract_campaign_cancellation(
    services: CommandServices,
    command: AbstractCampaignCommand,
    reason: str,
) -> Mapping[str, Any]:
    try:
        return services.cancel(
            command.db_path, supervision_id=command.supervision_id,
            campaign_id=command.campaign_id,
            configuration_id=command.configuration_id, run_id=command.run_id,
            owner_id=command.owner_id, reason=reason,
        )
    except Exception as exc:
        connection = _read_only(command.db_path.resolve())
        try:
            row = connection.execute(
                """SELECT cancellation_reason FROM printer_memory_factory_campaign_supervision
                   WHERE supervision_id=? AND campaign_id=? AND configuration_id=?
                     AND run_id=? AND owner_id=?""",
                (
                    command.supervision_id, command.campaign_id,
                    command.configuration_id, command.run_id, command.owner_id,
                ),
            ).fetchone()
        finally:
            connection.close()
        if row is not None and row["cancellation_reason"] == reason:
            return {
                "cancellation_requested": True,
                "cancellation_reason": reason,
                "idempotent_replay": True,
                "new_child_work_allowed": False,
            }
        raise AbstractCommandError("campaign cancellation was not confirmed") from exc


def handle_abstract_command(
    command: AbstractCampaignCommand, services: CommandServices | None = None
) -> dict[str, Any]:
    """Handle one validated internal command without exposing shell syntax."""
    preflight = preflight_abstract_command(command)
    if command.mode == REPORT_ONLY_MODE:
        if services is None:
            replay = replay_terminal_campaign_report
        else:
            replay = services.replay
        if not command.report_hash:
            raise AbstractCommandError("report-only mode requires an exact report hash")
        result = replay(
            command.db_path, campaign_id=command.campaign_id,
            configuration_id=command.configuration_id,
            report_id=command.report_id, report_hash=command.report_hash,
        )
        return {"mode": REPORT_ONLY_MODE, "preflight": preflight, "replay": result}

    if services is None:
        raise AbstractCommandError("bounded campaign mode requires injected operational owners")
    _validate_services(services)
    for label in ("supervision_id", "owner_id"):
        _required(getattr(command, label), label)
    if command.lease_lock_path is None:
        raise AbstractCommandError("lease_lock_path is required")

    baseline = dict(preflight["locked_capability_counts"])
    acquired = services.acquire(
        command.db_path, lock_path=command.lease_lock_path,
        supervision_id=command.supervision_id, campaign_id=command.campaign_id,
        configuration_id=command.configuration_id, run_id=command.run_id,
        owner_id=command.owner_id,
    )
    try:
        result = services.execute_campaign(
            command=command, source_governor=services.source_governor,
            central_scheduler=services.central_scheduler,
        )
        _validate_execution(result, command.ceilings)
    except Exception as exc:
        services.cleanup(
            command.db_path, supervision_id=command.supervision_id,
            campaign_id=command.campaign_id,
            configuration_id=command.configuration_id, run_id=command.run_id,
            owner_id=command.owner_id, terminal_status="FAILED",
            first_terminal_cause="ABSTRACT_COMMAND_EXECUTION_FAILED",
        )
        if isinstance(exc, AbstractCommandError):
            raise
        raise AbstractCommandError("bounded campaign execution failed safely") from exc
    cancellation: Mapping[str, Any] | None = None
    if result.cancellation_reason is not None:
        cancellation = request_abstract_campaign_cancellation(
            services, command, result.cancellation_reason
        )
    cleanup = services.cleanup(
        command.db_path, supervision_id=command.supervision_id,
        campaign_id=command.campaign_id,
        configuration_id=command.configuration_id, run_id=command.run_id,
        owner_id=command.owner_id, terminal_status=result.terminal_status,
        first_terminal_cause=result.first_terminal_cause,
    )
    if not cleanup.get("cleanup_completed") or not cleanup.get("lease_released"):
        raise AbstractCommandError("campaign cleanup or lease release was not confirmed")
    if cleanup.get("first_terminal_cause") != result.first_terminal_cause:
        raise AbstractCommandError("campaign first terminal cause changed")
    if cleanup.get("successor_created") or cleanup.get("restart_created"):
        raise AbstractCommandError("campaign cleanup created forbidden continuation")

    connection = _read_only(command.db_path.resolve())
    try:
        final_locked = _locked_counts(connection)
    finally:
        connection.close()
    deltas = {table: final_locked[table] - baseline[table] for table in baseline}
    if any(deltas.values()):
        raise AbstractCommandError("locked capability rows changed during campaign handling")
    report = services.persist_report(
        command.db_path, report_id=command.report_id,
        campaign_id=command.campaign_id,
        configuration_id=command.configuration_id, run_id=command.run_id,
    )
    return {
        "mode": CAMPAIGN_MODE,
        "preflight": preflight,
        "acquired": dict(acquired),
        "execution": asdict(result),
        "cancellation": dict(cancellation) if cancellation is not None else None,
        "cleanup": dict(cleanup),
        "report": dict(report),
        "locked_capability_deltas": deltas,
        "successor_created": False,
        "restart_created": False,
    }

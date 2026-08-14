"""Exact V2-9.8B.1 recovery for the first orphaned operational campaign.

This is deliberately not a generic resume or repair surface.  It recognizes one
operator-approved execution, proves its complete pre-recovery database delta,
creates a verified backup, and delegates mutation to the canonical terminal
owners.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from typing import Any, Callable, Mapping
import uuid

from printer_v1.operator_cli.campaign_active_work import campaign_active_work_report
from printer_v1.operator_cli.campaign_supervision import (
    cleanup_campaign_supervision,
)
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES
from printer_v1.operator_cli.operational_backup_restore_preflight import (
    operational_backup_restore_preflight,
)
from printer_v1.operator_cli.unified_terminal_closure import (
    build_campaign_terminal_report,
    reconcile_campaign_terminal,
    write_campaign_terminal_report,
)
from printer_v1.scheduler.scheduler import ACTIVE_STATUS_VALUES


EXECUTION_ID = "20260726T114155Z-95d9979a9302"
EXPECTED_CURRENT_SHA256 = (
    "2db1a11456771a0c5d48e8cee801d29860f21e11de0c70d86db1dd66068ed39a"
)
PRE_CAMPAIGN_BACKUP_SHA256 = (
    "e0f506d480b448c65c5f4573df5dea09adabd21bd017cd4664602b920edcae7f"
)
ORIGINAL_TERMINAL_CAUSE = "OPERATIONAL_CAMPAIGN_FAILED:GitProvenanceError"
_GRAPH_TABLES = {
    "printer_memory_factory_campaigns": "c64268af6a722a5d69618b98e9981a3edb42fa7832e3f8f9ee45081dd06713e4",
    "printer_memory_factory_campaign_configurations": "287f9c99fb316af1b08e2b9e19e68d597687b4649f3eb655e99994e2dd196147",
    "printer_memory_factory_campaign_runs": "c324a011eb432329e1b6124e25d48e7e6d7a4e247ca1316fbfab6e853608a4c9",
    "printer_memory_factory_campaign_cycles": "ea91d02f90ed99bdd73c00893e0ba2c4bf67bec92f2060a69a92a274e8cec942",
    "printer_memory_factory_campaign_supervision": "78b9d922c6cf2990e3c90001a2b734bd7ba07743bf85b6774731c4d83becaa5b",
}


class OperationalCampaignRecoveryError(RuntimeError):
    """Fail-closed exact orphan recovery fault."""


@dataclass(frozen=True)
class OrphanRecoveryContract:
    execution_id: str = EXECUTION_ID
    expected_current_sha256: str = EXPECTED_CURRENT_SHA256
    pre_campaign_backup_sha256: str = PRE_CAMPAIGN_BACKUP_SHA256
    expected_graph_table_hashes: Mapping[str, str] = field(
        default_factory=lambda: dict(_GRAPH_TABLES)
    )
    original_terminal_cause: str = ORIGINAL_TERMINAL_CAUSE

    @property
    def campaign_id(self) -> str:
        return f"{self.execution_id}-campaign"

    @property
    def configuration_id(self) -> str:
        return f"{self.execution_id}-configuration"

    @property
    def run_id(self) -> str:
        return f"{self.execution_id}-campaign-run"

    @property
    def cycle_id(self) -> str:
        return f"{self.execution_id}-cycle"

    @property
    def supervision_id(self) -> str:
        return f"{self.execution_id}-supervision"

    @property
    def owner_id(self) -> str:
        return f"{self.execution_id}-owner"

    @property
    def report_id(self) -> str:
        return f"{self.execution_id}-report"


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=0.0
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def _rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    if not table.replace("_", "").isalnum():
        raise OperationalCampaignRecoveryError("database table identity is malformed")
    rows = [
        dict(row)
        for row in connection.execute(f'SELECT * FROM "{table}"').fetchall()
    ]
    rows.sort(key=lambda row: repr(tuple(row.values())))
    return rows


def _canonical_rows_hash(rows: list[dict[str, Any]]) -> str:
    canonical = json.dumps(
        rows, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ) + "\n"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _table_names(connection: sqlite3.Connection) -> tuple[str, ...]:
    return tuple(
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    )


def _locked_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        for table in LOCKED_CAPABILITY_TABLES
    }


def _locked_hashes(connection: sqlite3.Connection) -> dict[str, str]:
    return {
        table: _canonical_rows_hash(_rows(connection, table))
        for table in LOCKED_CAPABILITY_TABLES
    }


def _assert_exact_pre_recovery_delta(
    *,
    current_db: Path,
    pre_campaign_backup: Path,
    contract: OrphanRecoveryContract,
) -> dict[str, Any]:
    if _sha256(pre_campaign_backup) != contract.pre_campaign_backup_sha256:
        raise OperationalCampaignRecoveryError("pre-campaign backup SHA mismatch")
    current = _read_only(current_db)
    baseline = _read_only(pre_campaign_backup)
    try:
        current_tables = _table_names(current)
        baseline_tables = _table_names(baseline)
        if current_tables != baseline_tables:
            raise OperationalCampaignRecoveryError("database schema table set drifted")
        graph_tables = set(contract.expected_graph_table_hashes)
        changed: list[str] = []
        for table in current_tables:
            current_rows = _rows(current, table)
            baseline_rows = _rows(baseline, table)
            if table in graph_tables:
                expected_hash = contract.expected_graph_table_hashes[table]
                if _canonical_rows_hash(current_rows) != expected_hash:
                    raise OperationalCampaignRecoveryError(
                        f"unexpected campaign graph row delta: {table}"
                    )
                if baseline_rows:
                    raise OperationalCampaignRecoveryError(
                        f"pre-campaign graph table was not empty: {table}"
                    )
                changed.append(table)
            elif current_rows != baseline_rows:
                raise OperationalCampaignRecoveryError(
                    f"unexpected database row delta: {table}"
                )
        if set(changed) != graph_tables:
            raise OperationalCampaignRecoveryError("campaign graph delta is incomplete")
        return {
            "changed_tables": sorted(changed),
            "unchanged_tables": len(current_tables) - len(changed),
            "retrieval_financial_counts": _locked_counts(current),
        }
    finally:
        baseline.close()
        current.close()


HOST_PROCESS_INSPECTION_TIMEOUT_SECONDS = 5.0


def host_process_inventory(
    *,
    timeout_seconds: float = HOST_PROCESS_INSPECTION_TIMEOUT_SECONDS,
    runner: Callable[..., Any] = subprocess.run,
) -> tuple[tuple[int, str], ...]:
    """Return one bounded read-only ``(pid, command_line)`` host inventory.

    This is the single platform process-enumeration owner. It performs exactly
    one inspection pass with a fixed timeout ceiling, never polls, and never
    signals, kills, or otherwise mutates a process. Any inability to inspect
    host state fails closed.
    """
    if os.name == "nt":  # pragma: no cover - production operator is currently macOS
        command = [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_Process | "
            "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress",
        ]
    else:
        command = ["ps", "-axo", "pid=,command="]
    try:
        result = runner(
            command, capture_output=True, text=True, timeout=timeout_seconds,
            check=False, shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OperationalCampaignRecoveryError(
            "live Printer process state could not be verified"
        ) from exc
    if result.returncode != 0:
        raise OperationalCampaignRecoveryError(
            "live Printer process state could not be verified"
        )
    if os.name == "nt":  # pragma: no cover - production operator is currently macOS
        return _windows_process_inventory(result.stdout)
    inventory: list[tuple[int, str]] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        fields = stripped.split(maxsplit=1)
        try:
            pid = int(fields[0])
        except (ValueError, IndexError):
            continue
        inventory.append((pid, fields[1] if len(fields) == 2 else ""))
    return tuple(inventory)


def _windows_process_inventory(
    stdout: str,
) -> tuple[tuple[int, str], ...]:  # pragma: no cover - macOS production operator
    """Parse the Windows CIM JSON listing, failing closed on malformed output."""
    try:
        payload = json.loads(stdout or "[]")
    except json.JSONDecodeError as exc:
        raise OperationalCampaignRecoveryError(
            "live Printer process state could not be verified"
        ) from exc
    records = payload if isinstance(payload, list) else [payload]
    inventory: list[tuple[int, str]] = []
    for record in records:
        if not isinstance(record, dict):
            raise OperationalCampaignRecoveryError(
                "live Printer process state could not be verified"
            )
        try:
            pid = int(record["ProcessId"])
        except (KeyError, TypeError, ValueError):
            continue
        inventory.append((pid, str(record.get("CommandLine") or "")))
    return tuple(inventory)


def _default_live_process_probe(
    execution_id: str,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> bool:
    """Conservatively detect a different active Printer production process."""
    own_pid = os.getpid()
    for pid, command_line in host_process_inventory(runner=runner):
        if pid == own_pid:
            continue
        production_run = (
            ("Start-PrinterV1-MemoryFactory" in command_line and "-Mode run" in command_line)
            or (
                "operational_memory_factory_command" in command_line
                and command_line.rstrip().endswith(" run")
            )
            or (
                "printer-run-v2-9-8-memory-factory" in command_line
                and command_line.rstrip().endswith(" run")
            )
            or execution_id in command_line
        )
        if production_run:
            return True
    return False


def _load_graph(
    connection: sqlite3.Connection, contract: OrphanRecoveryContract
) -> tuple[sqlite3.Row, sqlite3.Row, sqlite3.Row, sqlite3.Row]:
    campaign = connection.execute(
        "SELECT * FROM printer_memory_factory_campaigns WHERE campaign_id=?",
        (contract.campaign_id,),
    ).fetchone()
    run = connection.execute(
        "SELECT * FROM printer_memory_factory_campaign_runs WHERE run_id=?",
        (contract.run_id,),
    ).fetchone()
    cycle = connection.execute(
        "SELECT * FROM printer_memory_factory_campaign_cycles WHERE cycle_id=?",
        (contract.cycle_id,),
    ).fetchone()
    supervision = connection.execute(
        """SELECT * FROM printer_memory_factory_campaign_supervision
           WHERE supervision_id=? AND campaign_id=? AND configuration_id=?
             AND run_id=? AND owner_id=?""",
        (
            contract.supervision_id, contract.campaign_id,
            contract.configuration_id, contract.run_id, contract.owner_id,
        ),
    ).fetchone()
    if any(row is None for row in (campaign, run, cycle, supervision)):
        raise OperationalCampaignRecoveryError("exact orphan identity graph mismatch")
    return campaign, run, cycle, supervision


def _already_recovered(
    connection: sqlite3.Connection,
    contract: OrphanRecoveryContract,
    *,
    report_directory: Path,
) -> bool:
    campaign, run, cycle, supervision = _load_graph(connection, contract)
    exact_terminal = (
        campaign["campaign_state"] == "TERMINAL_FAILED"
        and run["run_state"] == "TERMINAL_FAILED"
        and cycle["cycle_state"] == "TERMINAL_FAILED"
        and supervision["supervision_state"] == "TERMINAL"
        and supervision["terminal_status"] == "FAILED"
        and campaign["first_terminal_cause"] == contract.original_terminal_cause
        and run["first_terminal_cause"] == contract.original_terminal_cause
        and cycle["first_terminal_cause"] == contract.original_terminal_cause
        and supervision["first_terminal_cause"] == contract.original_terminal_cause
        and supervision["cleanup_completed_at"] is not None
        and supervision["lease_released_at"] is not None
    )
    if not exact_terminal:
        return False
    report_count = int(
        connection.execute(
            """SELECT COUNT(*) FROM printer_memory_factory_campaign_reports
               WHERE report_id=? AND campaign_id=? AND configuration_id=?
                 AND report_state='REPORT_TERMINAL'""",
            (contract.report_id, contract.campaign_id, contract.configuration_id),
        ).fetchone()[0]
    )
    artifact = report_directory / f"{contract.report_id}.campaign-report.json"
    return report_count == 1 and artifact.is_file() and not Path(
        str(supervision["lease_lock_path"])
    ).exists()


def recover_exact_orphan(
    *,
    operator_approved: bool,
    current_db: str | Path,
    pre_campaign_backup: str | Path,
    artifact_root: str | Path,
    recovery_root: str | Path,
    contract: OrphanRecoveryContract | None = None,
    live_process_probe: Callable[[str], bool] = _default_live_process_probe,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Recover the one approved orphan after proving every ownership boundary."""
    if not operator_approved:
        raise OperationalCampaignRecoveryError("explicit operator approval is required")
    active_contract = contract or OrphanRecoveryContract()
    db_path = Path(current_db).resolve()
    baseline = Path(pre_campaign_backup).resolve()
    artifacts = Path(artifact_root).resolve()
    report_directory = artifacts / "reports"
    instant = now or datetime.now(timezone.utc)

    connection = _read_only(db_path)
    try:
        if _already_recovered(
            connection, active_contract, report_directory=report_directory
        ):
            return {
                "status": "V2_9_8B_1_ORPHAN_ALREADY_RECOVERED",
                "campaign_id": active_contract.campaign_id,
                "source_calls": 0,
                "scheduler_runtime_calls": 0,
                "database_writes": 0,
                "restart_created": False,
                "successor_created": False,
            }
    finally:
        connection.close()

    if _sha256(db_path) != active_contract.expected_current_sha256:
        raise OperationalCampaignRecoveryError("current authoritative DB SHA mismatch")
    delta = _assert_exact_pre_recovery_delta(
        current_db=db_path, pre_campaign_backup=baseline,
        contract=active_contract,
    )
    if live_process_probe(active_contract.execution_id):
        raise OperationalCampaignRecoveryError("live Printer owner process exists")

    connection = _read_only(db_path)
    try:
        campaign, run, cycle, supervision = _load_graph(connection, active_contract)
        if (
            campaign["campaign_state"] != "STOP_REQUESTED"
            or run["run_state"] != "STOP_REQUESTED"
            or cycle["cycle_state"] != "PLANNED"
            or supervision["supervision_state"] != "STOPPING"
            or supervision["terminal_status"] is not None
            or supervision["first_terminal_cause"] is not None
            or supervision["cleanup_completed_at"] is not None
            or supervision["lease_released_at"] is not None
            or supervision["cancellation_reason"]
            != "OPERATOR_REQUESTED_COOPERATIVE_STOP"
        ):
            raise OperationalCampaignRecoveryError("orphan terminal state drifted")
        lock_path = Path(str(supervision["lease_lock_path"])).resolve()
        try:
            lock_payload = json.loads(lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OperationalCampaignRecoveryError(
                "orphan filesystem lease is missing or ambiguous"
            ) from exc
        expected_lock = {
            "scope": "OPERATIONAL_CAMPAIGN",
            "supervision_id": active_contract.supervision_id,
            "campaign_id": active_contract.campaign_id,
            "configuration_id": active_contract.configuration_id,
            "run_id": active_contract.run_id,
            "owner_id": active_contract.owner_id,
        }
        if any(lock_payload.get(key) != value for key, value in expected_lock.items()):
            raise OperationalCampaignRecoveryError("orphan lease ownership mismatch")
        if (
            _parse(str(supervision["lease_expires_at"])) > instant
            or _parse(str(lock_payload.get("lease_expires_at"))) > instant
        ):
            raise OperationalCampaignRecoveryError("orphan lease is still live")
        placeholders = ",".join("?" * len(ACTIVE_STATUS_VALUES))
        active_scheduler = int(
            connection.execute(
                f"""SELECT COUNT(*) FROM printer_scheduler_jobs
                    WHERE status IN ({placeholders})
                       OR locked_at IS NOT NULL OR lock_owner IS NOT NULL""",
                ACTIVE_STATUS_VALUES,
            ).fetchone()[0]
        )
        if active_scheduler:
            raise OperationalCampaignRecoveryError(
                "active or locked Scheduler work exists"
            )
        active_work = campaign_active_work_report(
            connection, factory_run_id=None, campaign_id=active_contract.campaign_id,
            run_id=active_contract.run_id, cycle_id=active_contract.cycle_id,
        )
        if not active_work["clean_terminal"]:
            raise OperationalCampaignRecoveryError("campaign-owned active work exists")
        locked_before = _locked_counts(connection)
        locked_hashes_before = _locked_hashes(connection)
        configuration_row = connection.execute(
            """SELECT launch_provenance_json
               FROM printer_memory_factory_campaign_configurations
               WHERE configuration_id=? AND campaign_id=?""",
            (active_contract.configuration_id, active_contract.campaign_id),
        ).fetchone()
        if configuration_row is None:
            raise OperationalCampaignRecoveryError(
                "orphan configuration identity mismatch"
            )
        launch_git_provenance = json.loads(
            str(configuration_row["launch_provenance_json"])
        )
    finally:
        connection.close()

    recovery_directory = Path(recovery_root).resolve()
    recovery_directory.mkdir(parents=True, exist_ok=False)
    recovery_backup = recovery_directory / "printer_v1.pre-recovery.backup.sqlite3"
    restore = recovery_directory / "printer_v1.recovery-restore-rehearsal.sqlite3"
    backup = operational_backup_restore_preflight(
        db_path,
        expected_source_path=db_path,
        expected_source_identity=f"sha256:{active_contract.expected_current_sha256}",
        backup_path=recovery_backup,
        disposable_restore_root=recovery_directory,
        restore_path=restore,
    )
    if _sha256(recovery_backup) != active_contract.expected_current_sha256:
        raise OperationalCampaignRecoveryError("fresh recovery backup SHA mismatch")

    timestamp = _iso(instant)
    cleanup = cleanup_campaign_supervision(
        db_path,
        supervision_id=active_contract.supervision_id,
        campaign_id=active_contract.campaign_id,
        configuration_id=active_contract.configuration_id,
        run_id=active_contract.run_id,
        owner_id=active_contract.owner_id,
        terminal_status="FAILED",
        first_terminal_cause=active_contract.original_terminal_cause,
        now=instant,
    )
    reconciliation = reconcile_campaign_terminal(
        db_path,
        campaign_id=active_contract.campaign_id,
        run_id=active_contract.run_id,
        cycle_id=active_contract.cycle_id,
        terminal_cause=active_contract.original_terminal_cause,
        run_status="FAILED",
        factory_run_id=None,
        lifecycle_started=False,
        now=timestamp,
    )
    terminal_report = build_campaign_terminal_report(
        campaign_id=active_contract.campaign_id,
        configuration_id=active_contract.configuration_id,
        run_id=active_contract.run_id,
        cycle_id=active_contract.cycle_id,
        report_id=active_contract.report_id,
        factory_run_id=None,
        execution_id=active_contract.execution_id,
        terminal_status="FAILED",
        terminal_cause=active_contract.original_terminal_cause,
        run_status="FAILED",
        lifecycle_started=False,
        reconciliation=reconciliation,
        forbidden_deltas={table: 0 for table in locked_before},
        launch_git_provenance=launch_git_provenance,
    )
    report = write_campaign_terminal_report(
        db_path,
        report_directory,
        report_id=active_contract.report_id,
        campaign_id=active_contract.campaign_id,
        configuration_id=active_contract.configuration_id,
        report=terminal_report,
        now=instant,
    )

    connection = _read_only(db_path)
    try:
        if not _already_recovered(
            connection, active_contract, report_directory=report_directory
        ):
            raise OperationalCampaignRecoveryError(
                "canonical orphan recovery did not reach exact terminal state"
            )
        if _locked_counts(connection) != locked_before:
            raise OperationalCampaignRecoveryError(
                "retrieval or financial lock rows changed"
            )
        if _locked_hashes(connection) != locked_hashes_before:
            raise OperationalCampaignRecoveryError(
                "retrieval or financial lock row content changed"
            )
        integrity = tuple(
            str(row[0]) for row in connection.execute("PRAGMA integrity_check").fetchall()
        )
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        active_scheduler_after = int(
            connection.execute(
                f"""SELECT COUNT(*) FROM printer_scheduler_jobs
                    WHERE status IN ({placeholders})
                       OR locked_at IS NOT NULL OR lock_owner IS NOT NULL""",
                ACTIVE_STATUS_VALUES,
            ).fetchone()[0]
        )
    finally:
        connection.close()
    if integrity != ("ok",) or foreign_keys or active_scheduler_after:
        raise OperationalCampaignRecoveryError("post-recovery database checks failed")

    return {
        "status": "V2_9_8B_1_ORPHAN_RECOVERED",
        "campaign_id": active_contract.campaign_id,
        "first_terminal_cause": active_contract.original_terminal_cause,
        "recovery_backup": str(recovery_backup),
        "recovery_backup_sha256": _sha256(recovery_backup),
        "backup_preflight": backup,
        "delta": delta,
        "reconciliation": reconciliation,
        "cleanup": cleanup,
        "report": report,
        "final_database_sha256": _sha256(db_path),
        "integrity": "ok",
        "foreign_key_violations": 0,
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "restart_created": False,
        "successor_created": False,
    }


def production_recovery_paths() -> dict[str, Path]:
    repository = Path(__file__).resolve().parents[3]
    artifacts = (
        Path.home() / "PrinterOperations" / "v2-9-8" / EXECUTION_ID
    ).resolve()
    recovery = (
        Path.home() / "PrinterOperations" / "v2-9-8-recovery"
        / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:12]}"
    ).resolve()
    return {
        "current_db": repository / "data" / "printer_v1.sqlite3",
        "pre_campaign_backup": artifacts / "printer_v1.pre-campaign.backup.sqlite3",
        "artifact_root": artifacts,
        "recovery_root": recovery,
    }


__all__ = [
    "EXECUTION_ID",
    "EXPECTED_CURRENT_SHA256",
    "ORIGINAL_TERMINAL_CAUSE",
    "OperationalCampaignRecoveryError",
    "OrphanRecoveryContract",
    "production_recovery_paths",
    "recover_exact_orphan",
]

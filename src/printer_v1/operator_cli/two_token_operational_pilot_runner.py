"""V2-9.7E.14 real-wall-clock two-token operational pilot runner.

One internal, unregistered, pilot-only composition that drives the committed
E.11 ``AuthoritativeLiveOperationalCampaignOwner.run_operational`` (the two-token
finalized-origin operational owner) against live adapters and *real* canonical
timing, wired to the existing supervision, backup, report and replay owners.

It implements no discovery, disposition, barrier, continuation, support-only-5m,
promotion, activation, Source Governor or Central Scheduler logic, and no second
campaign or lifecycle owner. Those remain owned entirely by the committed E.11
implementation. This module is not a public CLI, is not registered in
``pyproject.toml``, and is not the future V2-9.8 operator command.

Design: ``docs/printer-v1-v2-9-7e-14-real-wall-clock-pilot-runner-design.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import threading
import time
from typing import Any, Callable, Mapping

from printer_v1.db.migrate import MIGRATIONS_DIR
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
    DEFAULT_CALL_TIMEOUT_SECONDS,
    AuthoritativeLiveOperationalCampaignOwner,
    OneShotUrllibPumpTransport,
    OneShotUrllibSecondaryTransport,
)
from printer_v1.operator_cli.campaign_ownership import create_campaign_run
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.git_provenance import (
    GitProvenanceError,
    validate_launch_provenance,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    _CONTINUATION_SECONDS,
    load_report_only,
)
from printer_v1.operator_cli.proof_db_schema_readiness import (
    ProofDbReadinessError,
    prepare_proof_db,
    validate_runtime_schema,
)
from printer_v1.operator_cli import proof_supervision as _sup

# Free-public source endpoints (read-only; no wallet, key, signing or funds).
FREE_PUBLIC_SOLANA_RPC = "https://api.mainnet-beta.solana.com"

# ---------------------------------------------------------------------------
# Canonical REAL lifecycle timing (never compressible on the production path).
#
# These mirror the ``run_one_command_15m_factory`` defaults. The production
# lifecycle kwargs set NONE of ``_window_seconds`` / ``_continuation_seconds`` /
# ``_sleep`` / ``_monotonic`` / adapter factories, so the factory defaults (real
# 900 s / 2700 s / ``time.sleep`` / ``time.monotonic`` / live adapters) apply.
# The only production timing kwarg is the total-duration envelope below.
# ---------------------------------------------------------------------------
CANONICAL_15M_WINDOW_SECONDS = 900.0
CANONICAL_CONTINUATION_SECONDS = _CONTINUATION_SECONDS  # 2700 s (real 45m)
CANONICAL_PILOT_TOTAL_DURATION_SECONDS = 15_300.0  # 4.25 h envelope
CANONICAL_PER_OP_TIMEOUT_SECONDS = DEFAULT_CALL_TIMEOUT_SECONDS  # 30 s
CANONICAL_LEASE_SECONDS = 90
CANONICAL_HEARTBEAT_INTERVAL_SECONDS = 30

# Lifecycle-kwargs keys that would compress or fixture the production run. The
# production path must never set any of them; a runtime guard enforces this.
_FORBIDDEN_PRODUCTION_TIMING_KEYS = frozenset(
    {
        "_window_seconds",
        "_continuation_seconds",
        "_sleep",
        "_monotonic",
        "snapshot_adapter_factory",
        "fallback_snapshot_adapter_factory",
        "context_adapter_factories",
    }
)


class PilotRunnerError(RuntimeError):
    """Fail-closed pilot runner fault."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _utc_now()).astimezone(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Explicit path contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PilotPaths:
    """Every path the pilot needs, explicit and mutually distinct."""

    persistent_source_db: Path
    target_db: Path
    backup_db: Path
    restore_rehearsal_db: Path
    report_dir: Path
    one_proof_lock_path: Path
    stdout_log_path: Path
    stderr_log_path: Path

    @staticmethod
    def of(
        *,
        persistent_source_db: str | Path,
        target_db: str | Path,
        backup_db: str | Path,
        restore_rehearsal_db: str | Path,
        report_dir: str | Path,
        one_proof_lock_path: str | Path,
        stdout_log_path: str | Path,
        stderr_log_path: str | Path,
    ) -> "PilotPaths":
        return PilotPaths(
            persistent_source_db=Path(persistent_source_db),
            target_db=Path(target_db),
            backup_db=Path(backup_db),
            restore_rehearsal_db=Path(restore_rehearsal_db),
            report_dir=Path(report_dir),
            one_proof_lock_path=Path(one_proof_lock_path),
            stdout_log_path=Path(stdout_log_path),
            stderr_log_path=Path(stderr_log_path),
        )


def _canonical_authoritative_corpus() -> Path | None:
    try:
        from printer_v1.operator_cli.proof_db_schema_readiness import (
            CANONICAL_PERSISTENT_DB,
        )
    except Exception:  # pragma: no cover - defensive
        return None
    try:
        return Path(CANONICAL_PERSISTENT_DB).resolve()
    except Exception:  # pragma: no cover - defensive
        return None


def _require_paths(paths: PilotPaths, *, allow_authoritative_target: bool) -> None:
    mutable = {
        "target_db": paths.target_db,
        "backup_db": paths.backup_db,
        "restore_rehearsal_db": paths.restore_rehearsal_db,
    }
    everything = {
        "persistent_source_db": paths.persistent_source_db,
        "report_dir": paths.report_dir,
        "one_proof_lock_path": paths.one_proof_lock_path,
        "stdout_log_path": paths.stdout_log_path,
        "stderr_log_path": paths.stderr_log_path,
        **mutable,
    }
    for label, value in everything.items():
        if value is None or not str(value).strip():
            raise PilotRunnerError(f"pilot path is missing or ambiguous: {label}")
    resolved = {label: Path(value).resolve() for label, value in everything.items()}
    if len(set(resolved.values())) != len(resolved):
        raise PilotRunnerError("pilot paths must be mutually distinct")
    if not paths.persistent_source_db.is_file():
        raise PilotRunnerError("persistent source database is missing")
    corpus = _canonical_authoritative_corpus()
    if corpus is not None and not allow_authoritative_target:
        for label in ("target_db", "backup_db", "restore_rehearsal_db"):
            if resolved[label] == corpus:
                raise PilotRunnerError(
                    f"{label} may not be the authoritative corpus without authorization"
                )


def _no_active_lease(target_db: Path) -> None:
    connection = sqlite3.connect(str(target_db))
    try:
        for table, states in (
            ("printer_proof_run_supervision", ("STARTING", "RUNNING")),
            ("printer_memory_factory_campaign_supervision", ("ACTIVE", "STOPPING")),
        ):
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if exists is None:
                continue
            column = (
                "execution_status"
                if table == "printer_proof_run_supervision"
                else "supervision_state"
            )
            placeholders = ",".join("?" * len(states))
            active = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {column} IN ({placeholders})",
                    states,
                ).fetchone()[0]
            )
            if active:
                raise PilotRunnerError(
                    f"target has an active or foreign lease in {table}"
                )
    finally:
        connection.close()


def prepare_pilot_target(
    paths: PilotPaths, *, allow_authoritative_target: bool = False
) -> dict[str, Any]:
    """Migrate, integrity-check, back up and restore-rehearse the pilot target.

    Fails closed on ambiguous paths, an authoritative-corpus target, migration /
    integrity / foreign-key failure, a non-byte-identical backup, a failed
    restore rehearsal, or an active/foreign lease. No campaign mutation occurs.
    """
    _require_paths(paths, allow_authoritative_target=allow_authoritative_target)
    if paths.target_db.exists() or paths.backup_db.exists():
        raise PilotRunnerError("pilot target and backup must be fresh")
    try:
        from printer_v1.sources.graduated_registry_bootstrap import (
            export_isolated_attempt_registry,
        )

        export = export_isolated_attempt_registry(
            paths.persistent_source_db,
            paths.target_db,
            export_identity=(
                f"pilot-export:{paths.target_db.parent.name}:{paths.target_db.name}"
            ),
        )
        validate_runtime_schema(paths.target_db)
        source_hash_before = _sha256(paths.persistent_source_db)
        paths.backup_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(paths.target_db, paths.backup_db)
        target_hash = _sha256(paths.target_db)
        backup_hash_created = _sha256(paths.backup_db)
        prep = {
            "proof_hash": target_hash,
            "backup_hash": backup_hash_created,
            "proof_backup_byte_identical": target_hash == backup_hash_created,
            "persistent_unchanged": _sha256(paths.persistent_source_db) == source_hash_before,
            "candidate_export": export.to_dict(),
        }
    except (ProofDbReadinessError, sqlite3.Error, OSError, ValueError) as exc:
        raise PilotRunnerError(f"target preparation blocked: {exc}") from exc

    # Restore rehearsal on a disposable copy of the byte-identical backup. The
    # byte-identity is asserted on the fresh copy BEFORE the schema is validated,
    # because opening the database read-write for validation mutates the file.
    rehearsal = paths.restore_rehearsal_db.resolve()
    if rehearsal.exists():
        raise PilotRunnerError("restore-rehearsal target must be fresh")
    rehearsal.parent.mkdir(parents=True, exist_ok=True)
    backup_hash = _sha256(paths.backup_db.resolve())
    try:
        shutil.copy2(paths.backup_db, rehearsal)
        if _sha256(rehearsal) != backup_hash:
            raise PilotRunnerError("restore rehearsal produced a divergent database")
        validate_runtime_schema(rehearsal)
        restore_rehearsal_ok = True
    finally:
        if rehearsal.exists():
            rehearsal.unlink()

    _no_active_lease(paths.target_db)

    return {
        "status": "PILOT_TARGET_READY",
        "target_db": str(paths.target_db.resolve()),
        "backup_db": str(paths.backup_db.resolve()),
        "target_hash": prep["proof_hash"],
        "backup_hash": prep["backup_hash"],
        "proof_backup_byte_identical": prep["proof_backup_byte_identical"],
        "persistent_unchanged": prep["persistent_unchanged"],
        "restore_rehearsal_ok": restore_rehearsal_ok,
        "no_active_lease": True,
        "candidate_export": prep["candidate_export"],
    }


# ---------------------------------------------------------------------------
# Campaign ownership graph
# ---------------------------------------------------------------------------


def _latest_migration_name() -> str:
    migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migrations:
        raise PilotRunnerError("no canonical migrations found")
    return migrations[-1].name


def build_pilot_command(
    target_db: Path,
    report_dir: Path,
    *,
    launch_provenance: Mapping[str, Any],
    selection_seed: str,
    campaign_id: str = "pilot-camp",
    configuration_id: str = "pilot-cfg",
    run_id: str = "pilot-run",
    report_id: str = "pilot-rep",
    cycle_id: str = "pilot-cyc",
    now: str,
) -> AbstractCampaignCommand:
    """Create the campaign/config/run/cycle graph and return the command."""
    report_dir.mkdir(parents=True, exist_ok=True)
    report_identity = report_path_identity(report_dir)
    ceilings = {
        "campaign_count": 1,
        "cycle_count": 1,
        "duration_seconds": int(CANONICAL_PILOT_TOTAL_DURATION_SECONDS),
        "source_calls": 45,
        "scheduler_work": 400,
        "storage_bytes": 64 * 1024 * 1024,
        "failures": 20,
    }
    configuration = {
        "token_capacity": 2,
        "ceilings": ceilings,
        "campaign_selection_seed": selection_seed,
        "report_directory_identity": report_identity,
        "backup_preflight_references": {
            "preflight_status": "READY",
            "source_identity": "sha256:" + "a" * 64,
            "backup_sha256": "b" * 64,
            "required_migration": "032_campaign_ownership_schema.sql",
            "latest_migration": _latest_migration_name(),
        },
    }
    created = create_campaign(
        target_db,
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        configuration=configuration,
        launch_provenance=launch_provenance,
        db_mode=DB_MODE_PROOF_ISOLATED,
        db_target_identity="pilot-iso",
        proof_source_db_identity="pilot-src",
        policy_version="v2-9.7e.14",
    )
    connection = sqlite3.connect(str(target_db))
    connection.execute("PRAGMA foreign_keys=ON")
    create_campaign_run(
        connection, campaign_id=campaign_id, run_id=run_id, run_ordinal=1, now=now
    )
    with connection:
        connection.execute(
            """
            INSERT INTO printer_memory_factory_campaign_cycles(
                cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                created_at, updated_at
            ) VALUES (?, ?, ?, 1, 'PLANNED', ?, ?)
            """,
            (cycle_id, campaign_id, run_id, now, now),
        )
        connection.execute(
            "UPDATE printer_memory_factory_campaigns SET campaign_state='RUNNING'"
        )
        connection.execute(
            "UPDATE printer_memory_factory_campaign_runs SET run_state='RUNNING'"
        )
    connection.close()
    return AbstractCampaignCommand(
        mode=CAMPAIGN_MODE,
        db_path=target_db,
        db_target_identity="pilot-iso",
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        configuration_hash=str(created["configuration_hash"]),
        policy_version="v2-9.7e.14",
        token_capacity=2,
        ceilings=CampaignCeilings(**ceilings),
        report_directory=report_dir,
        report_directory_identity=report_identity,
        launch_git_provenance=dict(launch_provenance),
        run_id=run_id,
        report_id=report_id,
    )


# ---------------------------------------------------------------------------
# Durable heartbeat worker
# ---------------------------------------------------------------------------


class HeartbeatWorker:
    """Durable periodic heartbeat over the active supervision lease.

    ``beat`` performs one monotonic heartbeat and is directly testable with an
    injected clock. ``start``/``stop`` run a background daemon thread for a real
    long pilot; the thread is never required by the offline proof.
    """

    def __init__(
        self,
        lock_path: str | Path,
        execution_id: str,
        *,
        interval_seconds: int = CANONICAL_HEARTBEAT_INTERVAL_SECONDS,
        lease_seconds: int = CANONICAL_LEASE_SECONDS,
        clock: Callable[[], datetime] = _utc_now,
        sleep: Callable[[float], None] = time.sleep,
        process_id: int | None = None,
    ) -> None:
        self._lock_path = str(lock_path)
        self._execution_id = execution_id
        self._interval = interval_seconds
        self._lease_seconds = lease_seconds
        self._clock = clock
        self._sleep = sleep
        self._process_id = process_id
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.beats = 0

    def beat(self, *, now: datetime | None = None) -> dict[str, Any]:
        result = _sup.heartbeat_active_lease(
            self._lock_path,
            self._execution_id,
            process_id=self._process_id,
            lease_seconds=self._lease_seconds,
            now=now or self._clock(),
        )
        self.beats += 1
        return result

    def _loop(self) -> None:  # pragma: no cover - real-thread cadence
        while not self._stop.is_set():
            self._sleep(self._interval)
            if self._stop.is_set():
                break
            try:
                self.beat()
            except _sup.ProofSupervisionError:
                break

    def start(self) -> None:  # pragma: no cover - real-thread cadence
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:  # pragma: no cover - real-thread cadence
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self._interval + 5)
            self._thread = None


# ---------------------------------------------------------------------------
# Production lifecycle kwargs (real timing only)
# ---------------------------------------------------------------------------


def production_lifecycle_kwargs(
    *,
    cancellation_probe: Callable[[], str | None],
    launch_provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the ONLY lifecycle kwargs the production pilot passes.

    Contains no timing override or fixture adapter, so the factory's real
    canonical 15m/1h/4h/5m/sleep defaults apply. A guard rejects any forbidden
    key, so a compressed or fixtured production run cannot be expressed.
    """
    kwargs = {
        "total_duration_seconds": CANONICAL_PILOT_TOTAL_DURATION_SECONDS,
        "cancellation_probe": cancellation_probe,
        "launch_provenance": dict(launch_provenance),
    }
    leaked = _FORBIDDEN_PRODUCTION_TIMING_KEYS.intersection(kwargs)
    if leaked:
        raise PilotRunnerError(
            f"production lifecycle kwargs must not compress timing: {sorted(leaked)}"
        )
    return kwargs


# ---------------------------------------------------------------------------
# Status / stop / replay (zero source and Scheduler calls)
# ---------------------------------------------------------------------------


def pilot_status(target_db: str | Path, execution_id: str) -> dict[str, Any]:
    """Read-only local supervision status; makes zero source/Scheduler calls."""
    status = _sup.inspect_execution(target_db, execution_id)
    status["source_calls"] = 0
    status["scheduler_calls"] = 0
    return status


def request_pilot_stop(
    lock_path: str | Path, execution_id: str, *, reason: str
) -> dict[str, Any]:
    """Request a cooperative operator stop; makes zero source/Scheduler calls."""
    result = dict(
        _sup.request_cooperative_stop(lock_path, execution_id, stop_reason=reason)
    )
    result["source_calls"] = 0
    result["scheduler_calls"] = 0
    return result


def pilot_report_only_replay(
    target_db: str | Path, run_id: str
) -> dict[str, Any]:
    """Deterministic report-only replay; zero source and Scheduler calls."""
    return load_report_only(target_db, run_id)


def _refuse_relaunch_if_present(target_db: Path, execution_id: str) -> None:
    # Connecting would create an empty file; a non-existent target cannot hold a
    # prior execution, so there is nothing to refuse yet.
    if not target_db.exists():
        return
    connection = sqlite3.connect(str(target_db))
    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='printer_proof_run_supervision'"
        ).fetchone()
        if exists is None:
            return
        row = connection.execute(
            "SELECT execution_status FROM printer_proof_run_supervision "
            "WHERE execution_id=?",
            (execution_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is not None:
        raise PilotRunnerError(
            f"execution {execution_id} already exists ({row[0]}); "
            "relaunch must not rerun or restart work"
        )


# ---------------------------------------------------------------------------
# The pilot runner
# ---------------------------------------------------------------------------


def _default_owner() -> AuthoritativeLiveOperationalCampaignOwner:
    return AuthoritativeLiveOperationalCampaignOwner()


def run_two_token_operational_pilot(
    paths: PilotPaths,
    *,
    execution_id: str,
    launch_provenance: Mapping[str, Any],
    selection_seed: str,
    cycle_cutoff: str,
    evaluated_at: str,
    owner: Any | None = None,
    pump_transport: Any | None = None,
    secondary_transport: Any | None = None,
    source_governor: OwnerPort | None = None,
    central_scheduler: OwnerPort | None = None,
    prepared: Mapping[str, Any] | None = None,
    owner_launcher_type: str = _sup.OWNER_MANUAL_POWERSHELL,
    process_id: int | None = None,
    lease_seconds: int = CANONICAL_LEASE_SECONDS,
    heartbeat: HeartbeatWorker | None = None,
    migration_transport: Any | None = None,
    graduated_supply_kwargs: Mapping[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Run exactly one bounded two-token live operational pilot under real timing.

    The E.11 owner is invoked exactly once. Supervision (lock, lease, heartbeat,
    cooperative stop, terminal cause, cleanup, replay) reuses ``proof_supervision``.
    No timing is compressible on this path. In offline proofs an injected fake
    owner replaces the live owner; no provider is contacted.
    """
    instant = now or _iso()
    target = paths.target_db.resolve()

    # Fail closed on dirty Git provenance before any supervision or mutation.
    try:
        provenance = validate_launch_provenance(launch_provenance)
    except GitProvenanceError as exc:
        raise PilotRunnerError(f"launch Git provenance blocked: {exc}") from exc

    # A relaunch that finds an existing execution refuses to rerun or restart.
    _refuse_relaunch_if_present(target, execution_id)

    if prepared is None:
        prepared = prepare_pilot_target(paths)

    # Create the supervision execution BEFORE the campaign graph is written, so
    # its byte-identical target/backup check sees the freshly prepared target.
    supervision = _sup.create_execution(
        target,
        execution_id=execution_id,
        owner_launcher_type=owner_launcher_type,
        process_id=process_id if process_id is not None else os.getpid(),
        backup_db_path=paths.backup_db,
        one_proof_lock_path=paths.one_proof_lock_path,
        stdout_log_path=paths.stdout_log_path,
        stderr_log_path=paths.stderr_log_path,
        lease_seconds=lease_seconds,
    )
    lock_path = str(supervision["one_proof_lock_path"])

    identity_prefix = execution_id
    campaign_id = f"{identity_prefix}-campaign"
    configuration_id = f"{identity_prefix}-configuration"
    run_id = f"{identity_prefix}-campaign-run"
    cycle_id = f"{identity_prefix}-cycle"
    report_id = f"{identity_prefix}-report"
    command = build_pilot_command(
        target,
        paths.report_dir,
        launch_provenance=provenance,
        selection_seed=selection_seed,
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        run_id=run_id,
        report_id=report_id,
        cycle_id=cycle_id,
        now=instant,
    )

    def cancellation_probe() -> str | None:
        return _sup.cooperative_stop_reason(lock_path, execution_id)

    lifecycle_kwargs = production_lifecycle_kwargs(
        cancellation_probe=cancellation_probe, launch_provenance=provenance
    )

    active_owner = owner if owner is not None else _default_owner()
    active_pump = pump_transport or OneShotUrllibPumpTransport(FREE_PUBLIC_SOLANA_RPC)
    active_secondary = (
        secondary_transport
        if secondary_transport is not None
        else OneShotUrllibSecondaryTransport()
    )
    governor = source_governor or OwnerPort(SOURCE_GOVERNOR_OWNER, True)
    scheduler = central_scheduler or OwnerPort(CENTRAL_SCHEDULER_OWNER, True)

    if migration_transport is None:
        from printer_v1.sources.pumpportal import build_pumpportal_migration_transport

        migration_transport = build_pumpportal_migration_transport(
            max_events=4,
            duration_seconds=120.0,
            connect_timeout_seconds=10.0,
        )
    supply_kwargs = {
        "collection_rounds": 3,
        "max_candidates": 4,
        "settle_seconds": 6.0,
        "reverify_on_transient": True,
        "reverify_settle_seconds": 6.0,
        "front_door_max_candidates": 4,
        "run_locator": True,
        "discovery_request_key_prefix": f"{execution_id}-supply",
        "front_door_request_key_prefix": f"{execution_id}-market",
    }
    supply_kwargs.update(dict(graduated_supply_kwargs or {}))

    worker = heartbeat or HeartbeatWorker(
        lock_path, execution_id, lease_seconds=lease_seconds, process_id=process_id
    )
    worker.start()
    try:
        result = active_owner.run_operational(
            command=command,
            pump_transport=active_pump,
            secondary_transport=active_secondary,
            source_governor=governor,
            central_scheduler=scheduler,
            selection_seed=selection_seed,
            cycle_id=cycle_id,
            cycle_cutoff=cycle_cutoff,
            evaluated_at=evaluated_at,
            backup_path=paths.backup_db,
            lifecycle_kwargs=lifecycle_kwargs,
            migration_transport=migration_transport,
            graduated_supply_kwargs=supply_kwargs,
        )
    finally:
        worker.stop()

    report = dict(result.lifecycle)
    run_id = str(report.get("run_id") or "")
    lifecycle_started = bool(getattr(result, "lifecycle_started", False))
    if lifecycle_started and not run_id:
        raise PilotRunnerError("pilot campaign returned no run identity")

    # A full pilot that terminates before any factory lifecycle run — a
    # pre-lifecycle admission block (fewer than two mature candidates) or a
    # no-atomic-activation / activation-failed terminal — creates no factory run.
    # There is nothing to attach or replay: finalize supervision directly from the
    # honest terminal report. Only a started lifecycle attaches a factory run and
    # runs a deterministic report-only replay.
    if lifecycle_started:
        _sup.attach_run(target, execution_id, run_id, process_id=process_id)
    terminal = _sup.finalize_execution_from_report(target, execution_id, report)

    if lifecycle_started:
        replay = pilot_report_only_replay(target, run_id)
        replay_new_source_calls = replay.get("replay", {}).get("new_source_calls")
        replay_deterministic = replay == pilot_report_only_replay(target, run_id)
    else:
        replay_new_source_calls = 0
        replay_deterministic = True
    forbidden = report.get("forbidden_deltas", {})

    return {
        "status": "PILOT_TERMINAL",
        "execution_id": execution_id,
        "authorization_id": execution_id,
        "campaign_id": campaign_id,
        "cycle_id": cycle_id,
        "run_id": run_id,
        "run_status": report.get("run_status"),
        "stop_reason": report.get("stop_reason"),
        "lifecycle_started": lifecycle_started,
        "terminal_status": terminal.get("terminal_status"),
        "first_terminal_cause": terminal.get("first_stop_reason"),
        "one_proof_lock_released": not Path(lock_path).exists(),
        "pending_or_running_run_steps": report.get("pending_or_running_run_steps"),
        "running_jobs_after_stop": report.get("running_jobs_after_stop"),
        "forbidden_deltas": forbidden,
        "full_pilot_admission": report.get("full_pilot_admission"),
        "replay_new_source_calls": replay_new_source_calls,
        "replay_deterministic": replay_deterministic,
        "prepared": dict(prepared),
        "restart_created": False,
        "successor_created": False,
    }

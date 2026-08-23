"""Read-only pre-consumption zero-state gate for the four-token proof.

This gate runs immediately before an application marker could be created, so a
known blocker is discovered while the authorization is still unconsumed. It is
strictly read-only: it opens the authoritative database through the existing
sidecar-safe immutable inspector, creates no campaign, reservation, lease,
discovery attempt, Scheduler job, or source request, and starts no process.

It replaces nothing. The final operational child preflight remains an additional
defence downstream.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from printer_v1.operator_cli.proof_supervision import process_is_alive
from printer_v1.operator_cli.four_token_proof_one_shot_wrapper import (
    FourTokenProofOneShotWrapperError,
    LOCKED_WINDOWS,
    exact_proof_policy,
    validate_four_token_proof_authorization_document,
)
from printer_v1.operator_cli.pre_authorization_migration_ledger_guard import (
    GuardResult,
    MigrationLedgerDriftGuardError,
    assert_migration_ledger_ready,
    inspect_authoritative_database,
    package_binding_from_document,
)
from printer_v1.operator_cli.schema_admission_coherence import (
    REQUIRED_MIGRATION_COUNT,
    REQUIRED_MIGRATION_HEAD,
    evaluate_schema_admission_coherence,
)
from printer_v1.sources.operational_source_contracts import (
    SolanaRpcConfigurationError,
    validate_window_15m_source_configuration,
)


ZERO_STATE_SCHEMA_VERSION = "PRINTER_V1_FOUR_TOKEN_PROOF_ZERO_STATE_GATE_V1"
OPERATIONAL_ZERO_STATE_SCHEMA_VERSION = (
    "PRINTER_V1_FOUR_TOKEN_STANDARD_4H_ZERO_STATE_GATE_V1"
)
# Exact authorized schema pin lives in schema_admission_coherence as explicit
# literals. This gate re-exports those names and does not keep a second pin.
# Adding a migrations-directory file must not silently re-authorize bounded
# admission: a future head requires its own helper-literal review. The
# canonical migration-ledger drift guard still runs independently and is not
# replaced by the pin. Four-token git current evidence remains the 059 package
# until a later apply/closeout lane creates a real 061 package.
LOCKED_LONG_WINDOWS = LOCKED_WINDOWS

#: Every domain that must be exactly zero before this proof may start. Each
#: entry is a read-only count over durable ownership; none of them mutate.
_ZERO_STATE_QUERIES: tuple[tuple[str, str], ...] = (
    (
        "active_campaigns",
        "SELECT COUNT(*) FROM printer_memory_factory_campaigns "
        "WHERE campaign_state NOT LIKE 'TERMINAL_%'",
    ),
    (
        "active_campaign_runs",
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_runs "
        "WHERE run_state NOT LIKE 'TERMINAL_%'",
    ),
    (
        "active_campaign_cycles",
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles "
        "WHERE cycle_state NOT LIKE 'TERMINAL_%'",
    ),
    (
        "active_campaign_scheduler_work",
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work "
        "WHERE work_state IN ('PENDING','RUNNING','COOLDOWN')",
    ),
    # Zero supervision means zero *active* ownership, never destroyed history.
    # Migration 033 keeps campaign supervision rows in TERMINAL and defines
    # active ownership as ACTIVE/STOPPING; migration 030 keeps proof supervision
    # rows in TERMINAL and defines active proof ownership as STARTING/RUNNING.
    # Historical terminal evidence is immutable and must never need deletion to
    # authorize a new bounded proof.
    (
        "campaign_supervision",
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_supervision "
        "WHERE supervision_state IN ('ACTIVE','STOPPING')",
    ),
    (
        "proof_supervision",
        "SELECT COUNT(*) FROM printer_proof_run_supervision "
        "WHERE execution_status IN ('STARTING','RUNNING')",
    ),
    (
        "active_discovery_work",
        "SELECT COUNT(*) FROM printer_discovery_work "
        "WHERE work_state IN ('PENDING','RUNNING','COOLDOWN')",
    ),
    (
        "active_factory_runs",
        "SELECT COUNT(*) FROM printer_memory_factory_runs "
        "WHERE run_status IN ('PENDING','RUNNING')",
    ),
    (
        "active_factory_steps",
        "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
        "WHERE step_status IN ('PENDING','RUNNING')",
    ),
    (
        "pre_admission_discovery_attempts",
        "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts "
        "WHERE attempt_state NOT IN "
        "('NO_PAIR','BLOCKED','FAILED','CANCELLED','CONSUMED')",
    ),
    # Migration 057 preserves terminal refresh-work history by design. Only a
    # live RUNNING row owns refresh work and therefore blocks a fresh proof.
    (
        "active_pre_lifecycle_discovery_refresh_work",
        "SELECT COUNT(*) FROM printer_pre_lifecycle_discovery_refresh_work "
        "WHERE work_state = 'RUNNING'",
    ),
    (
        "active_scheduler_jobs",
        "SELECT COUNT(*) FROM printer_scheduler_jobs "
        "WHERE status IN ('PENDING','RUNNING','COOLDOWN')",
    ),
)

REQUIRED_ZERO_STATE_DOMAINS: tuple[str, ...] = tuple(
    domain for domain, _query in _ZERO_STATE_QUERIES
)


class FourTokenProofZeroStateError(RuntimeError):
    """Fail-closed four-token proof pre-consumption zero-state fault."""


def project_four_token_proof_zero_state(
    connection: sqlite3.Connection,
) -> dict[str, int]:
    """Project every required zero-state domain count. Read-only."""
    projection: dict[str, int] = {}
    for domain, query in _ZERO_STATE_QUERIES:
        projection[domain] = int(connection.execute(query).fetchone()[0])
    return projection


#: The one public operational command whose runtime modes represent a live
#: Printer run. Auxiliary read-only modes (status, report-only, preflight) are
#: deliberately excluded: they are not a Printer runtime.
PRINTER_OPERATIONAL_COMMAND_MODULE = (
    "printer_v1.operator_cli.operational_memory_factory_command"
)
PRINTER_OPERATIONAL_LAUNCHERS = (
    PRINTER_OPERATIONAL_COMMAND_MODULE,
    "Start-PrinterV1-MemoryFactory",
    "printer-run-v2-9-8-memory-factory",
)
PRINTER_OPERATIONAL_RUNTIME_MODES = (
    "run",
    "standard-four-hour-run",
    "four-token-bounded-capacity-proof-run",
    "four-token-standard-four-hour-run",
)


def is_printer_operational_runtime_command(command_line: str) -> bool:
    """Return whether one host command line is a live Printer operational run.

    A match requires both a known operational launcher and one exact runtime
    mode carried as its own whitespace-delimited argument, so an unrelated
    Python process, a text search mentioning the module, or a read-only
    auxiliary mode of the same command never counts as a Printer runtime.
    """
    text = str(command_line or "")
    if not any(launcher in text for launcher in PRINTER_OPERATIONAL_LAUNCHERS):
        return False
    tokens = text.split()
    return any(mode in tokens for mode in PRINTER_OPERATIONAL_RUNTIME_MODES)


def active_printer_runtime_processes(
    db_path: str | Path,
    *,
    liveness_probe: Callable[[int | None], bool] | None = None,
    self_pids: Iterable[int] | None = None,
    host_process_inventory: Callable[[], Iterable[tuple[int, str]]] | None = None,
) -> tuple[int, ...]:
    """Return live Printer runtime PIDs from host state and durable supervision.

    Two independent authorities are combined in one bounded read-only pass, and
    neither is treated as complete on its own:

    * host state — one inventory pass over the platform process listing,
      matching the current wrapper-bound operational command shapes. This is the
      authority that covers a live operational child owning no supervision row.
    * durable supervision — proof-supervision rows still claiming active
      ownership, whose PIDs are checked with the existing
      :func:`process_is_alive` owner.

    Nothing polls, signals, kills, or mutates a process, and the durable
    zero-state database domains remain a separate defence. The wrapper's own
    process tree is never classified as an active Printer run, and any inability
    to inspect host or durable state fails closed.
    """
    probe = liveness_probe if liveness_probe is not None else process_is_alive
    excluded = set(self_pids) if self_pids is not None else {os.getpid(), os.getppid()}

    inventory_owner = host_process_inventory
    if inventory_owner is None:
        from printer_v1.operator_cli.operational_campaign_recovery import (
            host_process_inventory as _platform_host_process_inventory,
        )

        inventory_owner = _platform_host_process_inventory
    try:
        inventory = tuple(inventory_owner() or ())
    except FourTokenProofZeroStateError:
        raise
    except Exception as exc:  # fail closed on any unreliable host inspection
        raise FourTokenProofZeroStateError(
            _blocker("printer_process_state_unavailable", str(exc))
        ) from exc
    host_live: list[int] = []
    for entry in inventory:
        try:
            pid = int(entry[0])
            command_line = str(entry[1])
        except (IndexError, TypeError, ValueError) as exc:
            raise FourTokenProofZeroStateError(
                _blocker("printer_process_state_unavailable", f"host entry: {exc}")
            ) from exc
        if pid in excluded:
            continue
        if is_printer_operational_runtime_command(command_line):
            host_live.append(pid)

    identity = inspect_authoritative_database(db_path)
    if not identity.get("readable"):
        raise FourTokenProofZeroStateError(
            _blocker(
                "printer_process_state_unavailable",
                str(identity.get("error") or "authoritative database is unreadable"),
            )
        )
    try:
        connection = _read_only_connection(db_path)
    except sqlite3.Error as exc:
        raise FourTokenProofZeroStateError(
            _blocker("printer_process_state_unavailable", str(exc))
        ) from exc
    try:
        rows = connection.execute(
            "SELECT process_id FROM printer_proof_run_supervision "
            "WHERE execution_status IN ('STARTING','RUNNING') "
            "AND process_id IS NOT NULL ORDER BY process_id"
        ).fetchall()
    except sqlite3.Error as exc:
        raise FourTokenProofZeroStateError(
            _blocker("printer_process_state_unavailable", str(exc))
        ) from exc
    finally:
        connection.close()

    live: list[int] = list(host_live)
    for row in rows:
        pid = int(row[0])
        if pid in excluded:
            continue
        try:
            alive = probe(pid)
        except Exception as exc:  # fail closed on any unreliable inspection
            raise FourTokenProofZeroStateError(
                _blocker("printer_process_state_unavailable", f"pid {pid}: {exc}")
            ) from exc
        if alive:
            live.append(pid)
    return tuple(sorted(set(live)))


def _blocker(code: str, detail: str) -> str:
    return f"{code}: {detail}"


def _read_only_connection(db_path: str | Path) -> sqlite3.Connection:
    """Open the database immutable so the gate cannot write or create sidecars."""
    uri = Path(db_path).resolve().as_uri().replace("file://", "file:", 1)
    return sqlite3.connect(f"{uri}?immutable=1", uri=True)


def _assert_four_token_zero_state(
    *,
    db_path: str | Path,
    authorization_document: Mapping[str, Any],
    environment: Mapping[str, str],
    printer_process_probe: Callable[[], Iterable[int]],
    migrations_dir: str | Path | None,
    migration_ledger_guard: Callable[..., GuardResult | None],
    document_validator: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    validator_error: type[Exception],
    policy_key: str,
    expected_policy: Callable[[], Mapping[str, Any]],
    schema_version: str,
) -> dict[str, Any]:
    """Prove the authoritative state is quiescent for one exact 4/2/2 start.

    This is the single owner of every four-token zero-state check. The proof and
    operational entry points differ only in which authorization authority
    validates the document and which exact 4/2/2 policy must match; the database
    identity checks, ownership SQL, host-process probe, migration-ledger guard
    and source-configuration check are shared, never duplicated.

    Every reachable check runs before the caller may create an application
    marker, so the authorization is never consumed to discover a known blocker.
    """
    blockers: list[str] = []

    try:
        document = document_validator(authorization_document)
    except validator_error as exc:
        raise FourTokenProofZeroStateError(
            _blocker("authorization_document_invalid", str(exc))
        ) from exc

    policy = dict(document[policy_key])
    if policy != dict(expected_policy()):
        blockers.append(
            _blocker(
                f"{policy_key}_not_exact",
                f"{policy_key} is not the exact 4/2/2 policy",
            )
        )
    locked_windows = list(policy.get("locked_windows") or ())
    if tuple(locked_windows) != tuple(LOCKED_LONG_WINDOWS):
        blockers.append(
            _blocker("long_windows_unlocked", f"locked windows are {locked_windows}")
        )

    try:
        binding = package_binding_from_document(document)
        migration_ledger_guard(
            mode="review",
            db_path=db_path,
            migrations_dir=migrations_dir,
            package_binding=binding,
        )
    except MigrationLedgerDriftGuardError as exc:
        blockers.append(_blocker("migration_ledger_drift", str(exc)))

    coherence = evaluate_schema_admission_coherence(
        db_path=db_path,
        migrations_dir=migrations_dir,
        expected_target=None,
    )
    if not coherence.admission_schema_ready:
        for code in coherence.blocker_codes:
            blockers.append(_blocker(code, coherence.summary()))

    identity = inspect_authoritative_database(db_path)
    sidecars = list(identity.get("sidecars") or ())
    if sidecars:
        blockers.append(
            _blocker("authoritative_sidecars_present", ", ".join(sidecars))
        )
    migration_count = identity.get("migration_count")
    migration_head = identity.get("migration_head")
    if migration_count != REQUIRED_MIGRATION_COUNT:
        blockers.append(
            _blocker("migration_count_mismatch", f"observed {migration_count!r}")
        )
    if migration_head != REQUIRED_MIGRATION_HEAD:
        blockers.append(
            _blocker("migration_head_mismatch", f"observed {migration_head!r}")
        )
    integrity_rows = list(identity.get("integrity") or ())
    integrity = "ok" if integrity_rows == ["ok"] else ",".join(integrity_rows)
    if integrity != "ok":
        blockers.append(_blocker("integrity_check_failed", f"observed {integrity!r}"))
    foreign_key_violations = int(identity.get("foreign_key_violations") or 0)
    if foreign_key_violations:
        blockers.append(
            _blocker(
                "foreign_key_violations", f"observed {foreign_key_violations}"
            )
        )

    processes = list(printer_process_probe() or ())
    if processes:
        blockers.append(
            _blocker(
                "printer_process_present",
                ", ".join(str(item) for item in processes),
            )
        )

    try:
        validate_window_15m_source_configuration(environment)
    except SolanaRpcConfigurationError as exc:
        blockers.append(_blocker("source_configuration_invalid", str(exc)))

    projection: dict[str, int] = {}
    if identity.get("readable"):
        connection = _read_only_connection(db_path)
        try:
            projection = project_four_token_proof_zero_state(connection)
        except sqlite3.Error as exc:
            blockers.append(_blocker("zero_state_projection_failed", str(exc)))
        finally:
            connection.close()
        for domain in REQUIRED_ZERO_STATE_DOMAINS:
            observed = int(projection.get(domain, -1))
            if observed != 0:
                blockers.append(_blocker(domain, f"observed {observed}"))
    else:
        blockers.append(
            _blocker(
                "authoritative_database_unreadable",
                str(identity.get("error") or "database is unreadable"),
            )
        )

    if blockers:
        raise FourTokenProofZeroStateError(
            "four-token proof zero-state gate blocked before consumption: "
            + "; ".join(blockers)
        )

    return {
        "schema_version": schema_version,
        "zero_state_ready": True,
        "blockers": [],
        "authorization_id": str(document["authorization_id"]),
        "migration_count": int(migration_count),
        "migration_head": str(migration_head),
        "integrity_check": str(integrity),
        "foreign_key_violations": foreign_key_violations,
        "sidecars": sidecars,
        "printer_processes": len(processes),
        "locked_windows": list(locked_windows),
        "zero_state_domains": dict(projection),
    }


def assert_four_token_proof_zero_state(
    *,
    db_path: str | Path,
    authorization_document: Mapping[str, Any],
    environment: Mapping[str, str],
    printer_process_probe: Callable[[], Iterable[int]],
    migrations_dir: str | Path | None = None,
    migration_ledger_guard: Callable[..., GuardResult | None] = (
        assert_migration_ledger_ready
    ),
) -> dict[str, Any]:
    """Prove quiescence for one exact bounded four-token PROOF start.

    Proof-only authority. It accepts nothing but a proof authorization document
    and the exact proof 4/2/2 policy.
    """
    return _assert_four_token_zero_state(
        db_path=db_path,
        authorization_document=authorization_document,
        environment=environment,
        printer_process_probe=printer_process_probe,
        migrations_dir=migrations_dir,
        migration_ledger_guard=migration_ledger_guard,
        document_validator=validate_four_token_proof_authorization_document,
        validator_error=FourTokenProofOneShotWrapperError,
        policy_key="proof_policy",
        expected_policy=exact_proof_policy,
        schema_version=ZERO_STATE_SCHEMA_VERSION,
    )


def assert_four_token_standard_four_hour_zero_state(
    *,
    db_path: str | Path,
    authorization_document: Mapping[str, Any],
    environment: Mapping[str, str],
    printer_process_probe: Callable[[], Iterable[int]],
    migrations_dir: str | Path | None = None,
    migration_ledger_guard: Callable[..., GuardResult | None] = (
        assert_migration_ledger_ready
    ),
) -> dict[str, Any]:
    """Prove quiescence for one exact bounded four-token OPERATIONAL start.

    Operational 4/2/2 authority. It accepts nothing but an operational
    authorization document and the exact operational 4/2/2 policy. The imports
    are local because the operational wrapper imports this module for its own
    default gate.
    """
    from printer_v1.operator_cli.four_token_operational_composition import (
        exact_operational_policy,
    )
    from printer_v1.operator_cli.four_token_standard_four_hour_one_shot_wrapper import (
        FourTokenStandardFourHourOneShotWrapperError,
        validate_four_token_standard_four_hour_authorization_document,
    )

    return _assert_four_token_zero_state(
        db_path=db_path,
        authorization_document=authorization_document,
        environment=environment,
        printer_process_probe=printer_process_probe,
        migrations_dir=migrations_dir,
        migration_ledger_guard=migration_ledger_guard,
        document_validator=(
            validate_four_token_standard_four_hour_authorization_document
        ),
        validator_error=FourTokenStandardFourHourOneShotWrapperError,
        policy_key="operational_policy",
        expected_policy=exact_operational_policy,
        schema_version=OPERATIONAL_ZERO_STATE_SCHEMA_VERSION,
    )


__all__ = [
    "FourTokenProofZeroStateError",
    "LOCKED_LONG_WINDOWS",
    "OPERATIONAL_ZERO_STATE_SCHEMA_VERSION",
    "REQUIRED_MIGRATION_COUNT",
    "REQUIRED_MIGRATION_HEAD",
    "REQUIRED_ZERO_STATE_DOMAINS",
    "ZERO_STATE_SCHEMA_VERSION",
    "active_printer_runtime_processes",
    "assert_four_token_proof_zero_state",
    "assert_four_token_standard_four_hour_zero_state",
    "project_four_token_proof_zero_state",
]

"""Terminal-only expired-orphan recovery for operational four-token Standard-4H.

Inspection is read-only. Terminalization requires an operator-approved stable
inspection SHA, a verified backup/restore rehearsal, and a second matching
inspection immediately before mutation. The recovery never resumes lifecycle
work, reuses authorization, performs source work, promotes memory, or creates a
retry/restart/rerun/successor.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Callable, Iterable, Mapping

from printer_v1.db.migrate import canonical_migration_names
from printer_v1.operator_cli.campaign_active_work import campaign_active_work_report
from printer_v1.operator_cli.campaign_persistence import campaign_evidence_sha256
from printer_v1.operator_cli.campaign_supervision import cleanup_campaign_supervision
from printer_v1.operator_cli.four_token_operational_composition import (
    FOUR_TOKEN_STANDARD_FOUR_HOUR_MODE,
    build_operational_multi_cycle_controller,
    exact_operational_policy,
)
from printer_v1.operator_cli.four_token_proof_zero_state_gate import (
    is_printer_operational_runtime_command,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    multi_cycle_configuration_contract,
)
from printer_v1.operator_cli.operational_backup_restore_preflight import (
    operational_backup_restore_preflight,
)
from printer_v1.operator_cli.operational_campaign_recovery import host_process_inventory
from printer_v1.operator_cli.unified_terminal_closure import (
    reconcile_admitted_campaign_terminal,
    reconcile_campaign_terminal,
)


INSPECTION_SCHEMA_VERSION = (
    "PRINTER_V1_FOUR_TOKEN_STANDARD_4H_EXPIRED_ORPHAN_INSPECTION_V1"
)
RECOVERY_SCHEMA_VERSION = (
    "PRINTER_V1_FOUR_TOKEN_STANDARD_4H_TERMINAL_ONLY_RECOVERY_V1"
)
RECOVERY_CAUSE = "OPERATIONAL_CAMPAIGN_ORPHANED_AFTER_LEASE_EXPIRY"
AUTHORIZED_MODE = FOUR_TOKEN_STANDARD_FOUR_HOUR_MODE
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ExpiredOrphanReconciliationError(RuntimeError):
    """Fail-closed expired-orphan inspection/reconciliation fault."""


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _sha256_file(path: Path) -> str:
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


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )


def _one(
    connection: sqlite3.Connection,
    sql: str,
    params: tuple[Any, ...],
) -> dict[str, Any] | None:
    rows = connection.execute(sql, params).fetchall()
    if len(rows) != 1:
        return None
    return dict(rows[0])


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [_jsonable(item) for item in value]
        if isinstance(value, (set, frozenset)):
            return sorted(items, key=repr)
        return items
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            _jsonable(payload),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_sha(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _block(blockers: list[str], code: str) -> None:
    if code not in blockers:
        blockers.append(code)


def _configuration_policy_valid(configuration: Mapping[str, Any]) -> bool:
    expected = exact_operational_policy()
    if configuration.get("command_mode") != AUTHORIZED_MODE:
        return False
    if configuration.get("policy_version") != expected["policy_version"]:
        return False
    if configuration.get("token_capacity") != expected["tokens_per_cycle"]:
        return False
    if configuration.get("main_window", expected["root_main_window"]) != expected[
        "root_main_window"
    ]:
        return False
    if configuration.get("pre_lifecycle_acquisition_duration_seconds") != expected[
        "pre_lifecycle_acquisition_duration_seconds"
    ]:
        return False
    if configuration.get(
        "later_cycle_pre_admission_deadline_seconds_after_cycle_one"
    ) != expected["later_cycle_pre_admission_deadline_seconds_after_cycle_one"]:
        return False
    if configuration.get("standard_four_hour_campaign") is not True:
        return False
    if configuration.get("selective_1h_continuation") is not True:
        return False
    if configuration.get("continuous_four_hour") is not True:
        return False
    if list(configuration.get("locked_windows") or ()) != list(
        expected["locked_windows"]
    ):
        return False
    if configuration.get("automatic_retries") != 0:
        return False
    ceilings = configuration.get("ceilings")
    if not isinstance(ceilings, Mapping):
        return False
    if ceilings.get("cycle_count") != expected["total_cycle_admission_ceiling"]:
        return False
    if ceilings.get("duration_seconds") != expected[
        "post_supply_lifecycle_duration_seconds"
    ]:
        return False
    persisted = configuration.get("multi_cycle_capacity")
    if not isinstance(persisted, Mapping):
        return False
    intake_started_at = _parse_time(persisted.get("intake_started_at"))
    if intake_started_at is None:
        return False
    controller = build_operational_multi_cycle_controller()
    expected_multi = multi_cycle_configuration_contract(
        controller.policy,
        intake_started_at=intake_started_at,
    )
    return dict(persisted) == expected_multi


def _authorization_valid(
    configuration: Mapping[str, Any],
    *,
    path: Path,
    campaign_id: str,
    run_id: str,
    configuration_id: str,
    cycle_id: str,
) -> tuple[bool, dict[str, Any]]:
    marker = configuration.get("authorization_marker")
    marker_sha = configuration.get("authorization_marker_sha256")
    if not isinstance(marker, Mapping) or not isinstance(marker_sha, str):
        return False, {}
    if campaign_evidence_sha256(marker) != marker_sha:
        return False, {}
    marker_expected = {
        "execution_id": configuration.get("execution_id"),
        "campaign_id": campaign_id,
        "configuration_id": configuration_id,
        "run_id": run_id,
        "policy_version": exact_operational_policy()["policy_version"],
        "operator_approved": True,
    }
    if any(marker.get(key) != value for key, value in marker_expected.items()):
        return False, {}

    expectation = configuration.get("operational_database_target_expectation")
    if not isinstance(expectation, Mapping):
        return False, {}
    identity_expected = {
        "resolved_db_path": str(path),
        "authorized_db_path": str(path),
        "execution_id": configuration.get("execution_id"),
        "campaign_id": campaign_id,
        "campaign_run_id": run_id,
        "configuration_id": configuration_id,
        "cycle_id": cycle_id,
        "authorization_consumed_once": True,
        "invocation_count": 1,
        "allowed_invocation_count": 1,
        "automatic_retry_allowed": False,
        "manual_rerun_allowed": False,
        "resume_allowed": False,
        "restart_allowed": False,
        "successor_allowed": False,
    }
    for key, value in identity_expected.items():
        observed = expectation.get(key)
        if key in {"resolved_db_path", "authorized_db_path"}:
            try:
                if Path(str(observed)).resolve() != path:
                    return False, {}
            except (OSError, RuntimeError):
                return False, {}
        elif observed != value:
            return False, {}
    return True, {
        "internal_authorization_marker_sha256": marker_sha,
        "external_authorization_id": expectation.get("authorization_id"),
        "external_authorization_marker_sha256": expectation.get(
            "authorization_marker_sha256"
        ),
        "application_marker_sha256": expectation.get("application_marker_sha256"),
        "authorization_consumed_once": True,
        "invocation_count": 1,
        "allowed_invocation_count": 1,
        "automatic_retry_allowed": False,
        "manual_rerun_allowed": False,
        "resume_allowed": False,
        "restart_allowed": False,
        "successor_allowed": False,
    }


def _admitted_shape(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    origin_cycle_id: str,
) -> tuple[str | None, list[dict[str, Any]], list[dict[str, Any]]]:
    cycles = [
        dict(row)
        for row in connection.execute(
            """SELECT cycle_id,cycle_ordinal,cycle_state,first_terminal_cause
               FROM printer_memory_factory_campaign_cycles
               WHERE campaign_id=? AND run_id=?
               ORDER BY cycle_ordinal,cycle_id""",
            (campaign_id, run_id),
        ).fetchall()
    ]
    if not cycles or str(cycles[0]["cycle_id"]) != origin_cycle_id:
        return None, cycles, []
    ordinals = [int(row["cycle_ordinal"]) for row in cycles]
    if ordinals not in ([1], [1, 2]):
        return None, cycles, []
    slots = [
        dict(row)
        for row in connection.execute(
            """SELECT token_slot_id,cycle_id,slot_ordinal,token_state,
                      token_row_id,pair_row_id,mint_identity,pair_identity
               FROM printer_memory_factory_campaign_token_slots
               WHERE campaign_id=? AND run_id=?
               ORDER BY cycle_id,slot_ordinal,token_slot_id""",
            (campaign_id, run_id),
        ).fetchall()
    ]
    by_cycle: dict[str, list[int]] = {
        str(row["cycle_id"]): [] for row in cycles
    }
    for slot in slots:
        owner = str(slot["cycle_id"])
        if owner not in by_cycle:
            return None, cycles, slots
        by_cycle[owner].append(int(slot["slot_ordinal"]))
    if len(cycles) == 1 and not slots:
        return "PRE_ADMISSION", cycles, slots
    if len(cycles) == 1 and by_cycle[origin_cycle_id] == [1, 2]:
        return "CYCLE_1_ADMITTED", cycles, slots
    if len(cycles) == 2 and all(values == [1, 2] for values in by_cycle.values()):
        return "TWO_CYCLES_ADMITTED", cycles, slots
    return None, cycles, slots


def _memory_snapshot(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
) -> dict[str, Any]:
    campaign_windows: list[dict[str, Any]] = []
    physical_ids: list[int] = []
    if _table_exists(connection, "printer_memory_factory_campaign_windows"):
        campaign_windows = [
            dict(row)
            for row in connection.execute(
                """SELECT window_id,cycle_id,token_slot_id,window_kind,window_state,
                          memory_window_row_id
                   FROM printer_memory_factory_campaign_windows
                   WHERE campaign_id=? AND run_id=?
                   ORDER BY cycle_id,token_slot_id,window_kind,window_id""",
                (campaign_id, run_id),
            ).fetchall()
        ]
        physical_ids = sorted(
            {
                int(row["memory_window_row_id"])
                for row in campaign_windows
                if row.get("memory_window_row_id") is not None
            }
        )
    episodes: list[dict[str, Any]] = []
    fingerprints: list[dict[str, Any]] = []
    if physical_ids and _table_exists(connection, "printer_episodes"):
        placeholders = ",".join("?" for _ in physical_ids)
        episodes = [
            dict(row)
            for row in connection.execute(
                f"""SELECT id,memory_window_id,memory_status,memory_quality_label,
                           data_quality_label,do_not_train,episode_kind,
                           episode_outcome_label,token_id,pair_id
                    FROM printer_episodes
                    WHERE memory_window_id IN ({placeholders}) ORDER BY id""",
                tuple(physical_ids),
            ).fetchall()
        ]
        episode_ids = [int(row["id"]) for row in episodes]
        if episode_ids and _table_exists(connection, "printer_memory_fingerprints"):
            ep_placeholders = ",".join("?" for _ in episode_ids)
            fingerprints = [
                dict(row)
                for row in connection.execute(
                    f"""SELECT id,episode_id,fingerprint_kind,
                               fingerprint_payload_json
                        FROM printer_memory_fingerprints
                        WHERE episode_id IN ({ep_placeholders}) ORDER BY id""",
                    tuple(episode_ids),
                ).fetchall()
            ]
    return {
        "campaign_windows": campaign_windows,
        "physical_memory_window_ids": physical_ids,
        "episodes": episodes,
        "fingerprints": fingerprints,
    }


def _row_counts(
    connection: sqlite3.Connection,
    tables: Iterable[str],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in tables:
        if _table_exists(connection, table):
            counts[table] = int(
                connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            )
    return counts


def inspect_expired_orphan(
    db_path: str | Path,
    *,
    campaign_id: str,
    run_id: str,
    artifact_root: str | Path,
    expected_db_path: str | Path | None = None,
    process_inventory: Callable[[], Iterable[tuple[int, str]]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read-only exact four-token orphan inspection with stable SHA binding."""
    path = Path(db_path).resolve()
    expected_path = Path(expected_db_path or db_path).resolve()
    artifacts = Path(artifact_root).resolve()
    observed_at = _utc(now)
    blockers: list[str] = []

    if path != expected_path or not path.is_file():
        _block(blockers, "ORPHAN_DATABASE_HEALTH_BLOCKED")
        stable = {
            "schema_version": INSPECTION_SCHEMA_VERSION,
            "requested": {"campaign_id": campaign_id, "run_id": run_id},
            "database_path": str(path),
            "blockers": blockers,
        }
        return {
            **stable,
            "eligible": False,
            "inspection_sha256": _canonical_sha(stable),
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        }

    sidecars = sorted(
        str(candidate)
        for candidate in (
            Path(f"{path}-wal"),
            Path(f"{path}-shm"),
            Path(f"{path}-journal"),
        )
        if candidate.exists()
    )
    if sidecars:
        _block(blockers, "ORPHAN_DATABASE_SIDECAR_AMBIGUOUS")

    try:
        connection = _read_only(path)
    except sqlite3.Error as exc:
        raise ExpiredOrphanReconciliationError(
            "ORPHAN_DATABASE_HEALTH_BLOCKED"
        ) from exc
    try:
        campaign = _one(
            connection,
            "SELECT * FROM printer_memory_factory_campaigns WHERE campaign_id=?",
            (campaign_id,),
        )
        run = _one(
            connection,
            """SELECT * FROM printer_memory_factory_campaign_runs
               WHERE campaign_id=? AND run_id=?""",
            (campaign_id, run_id),
        )
        configurations = connection.execute(
            """SELECT * FROM printer_memory_factory_campaign_configurations
               WHERE campaign_id=? ORDER BY configuration_id""",
            (campaign_id,),
        ).fetchall()
        supervisions = connection.execute(
            """SELECT * FROM printer_memory_factory_campaign_supervision
               WHERE campaign_id=? AND run_id=? ORDER BY supervision_id""",
            (campaign_id, run_id),
        ).fetchall()
        if campaign is None or run is None or len(configurations) != 1 or len(supervisions) != 1:
            _block(blockers, "ORPHAN_IDENTITY_NOT_FOUND")
            configuration_row = None
            supervision = None
            configuration: dict[str, Any] = {}
        else:
            configuration_row = dict(configurations[0])
            supervision = dict(supervisions[0])
            try:
                decoded = json.loads(str(configuration_row["configuration_json"]))
            except (TypeError, ValueError):
                decoded = None
            if not isinstance(decoded, dict):
                _block(blockers, "ORPHAN_AUTHORIZATION_EVIDENCE_INVALID")
                configuration = {}
            else:
                configuration = decoded

        execution_id = str(configuration.get("execution_id") or "")
        configuration_id = str(
            configuration.get("configuration_id")
            or (configuration_row or {}).get("configuration_id")
            or ""
        )
        origin_cycle_id = str(configuration.get("cycle_id") or "")
        identity_ok = bool(
            campaign
            and run
            and configuration_row
            and supervision
            and execution_id
            and configuration_id
            and origin_cycle_id
            and str(configuration.get("campaign_id") or "") == campaign_id
            and str(configuration.get("run_id") or "") == run_id
            and str(configuration_row.get("configuration_id") or "")
            == configuration_id
            and str(supervision.get("configuration_id") or "")
            == configuration_id
        )
        if not identity_ok:
            _block(blockers, "ORPHAN_IDENTITY_AMBIGUOUS")

        if configuration and not _configuration_policy_valid(configuration):
            _block(blockers, "ORPHAN_MODE_NOT_FOUR_TOKEN_STANDARD_4H")

        authorization_evidence: dict[str, Any] = {}
        if identity_ok:
            authorization_ok, authorization_evidence = _authorization_valid(
                configuration,
                path=path,
                campaign_id=campaign_id,
                run_id=run_id,
                configuration_id=configuration_id,
                cycle_id=origin_cycle_id,
            )
            if not authorization_ok:
                _block(blockers, "ORPHAN_AUTHORIZATION_EVIDENCE_INVALID")

        applied = tuple(
            str(row[0])
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY version"
            ).fetchall()
        )
        canonical = tuple(canonical_migration_names())
        integrity = tuple(
            str(row[0]) for row in connection.execute("PRAGMA integrity_check").fetchall()
        )
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        if applied != canonical or integrity != ("ok",) or foreign_keys:
            _block(blockers, "ORPHAN_DATABASE_HEALTH_BLOCKED")

        inventory_owner = process_inventory or host_process_inventory
        try:
            inventory = tuple(inventory_owner() or ())
        except Exception as exc:
            raise ExpiredOrphanReconciliationError(
                "ORPHAN_PROCESS_INSPECTION_BLOCKED"
            ) from exc
        own_pid = os.getpid()
        matched_processes = sorted(
            (int(pid), str(command))
            for pid, command in inventory
            if int(pid) != own_pid and is_printer_operational_runtime_command(str(command))
        )
        if matched_processes:
            _block(blockers, "ORPHAN_PRINTER_PROCESS_PRESENT")

        lease_evidence: dict[str, Any] = {}
        if supervision is not None:
            state = str(supervision.get("supervision_state") or "")
            if state not in {"ACTIVE", "STOPPING"}:
                _block(blockers, "ORPHAN_FIRST_CAUSE_CONFLICT")
            expires_at = _parse_time(supervision.get("lease_expires_at"))
            expired = bool(expires_at is not None and expires_at < observed_at)
            if not expired:
                _block(blockers, "ORPHAN_LEASE_NOT_EXPIRED")
            lease_path = Path(str(supervision.get("lease_lock_path") or "")).resolve()
            expected_lease_path = (
                artifacts / execution_id / "campaign.lease.lock"
            ).resolve()
            if lease_path != expected_lease_path:
                _block(blockers, "ORPHAN_LEASE_OWNERSHIP_MISMATCH")
            if not lease_path.is_file() or lease_path.is_symlink():
                _block(blockers, "ORPHAN_LEASE_FILE_MISSING")
            else:
                try:
                    raw = json.loads(lease_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    raw = None
                if not isinstance(raw, dict):
                    _block(blockers, "ORPHAN_LEASE_FILE_MALFORMED")
                else:
                    expected_scope = {
                        "scope": "OPERATIONAL_CAMPAIGN",
                        "supervision_id": supervision.get("supervision_id"),
                        "campaign_id": campaign_id,
                        "configuration_id": configuration_id,
                        "run_id": run_id,
                        "owner_id": supervision.get("owner_id"),
                    }
                    if any(raw.get(key) != value for key, value in expected_scope.items()):
                        _block(blockers, "ORPHAN_LEASE_OWNERSHIP_MISMATCH")
                    for key in ("heartbeat_at", "lease_expires_at"):
                        if key in raw and str(raw.get(key)) != str(supervision.get(key)):
                            _block(blockers, "ORPHAN_LEASE_OWNERSHIP_MISMATCH")
            lease_evidence = {
                "supervision_state": state,
                "supervision_id": supervision.get("supervision_id"),
                "owner_id": supervision.get("owner_id"),
                "heartbeat_at": supervision.get("heartbeat_at"),
                "lease_expires_at": supervision.get("lease_expires_at"),
                "lease_expired": expired,
                "lease_lock_path": str(lease_path),
                "lease_file_present": lease_path.is_file() and not lease_path.is_symlink(),
                "lease_file_sha256": (
                    _sha256_file(lease_path)
                    if lease_path.is_file() and not lease_path.is_symlink()
                    else None
                ),
            }

        other_active_supervision = int(
            connection.execute(
                """SELECT COUNT(*) FROM printer_memory_factory_campaign_supervision
                   WHERE supervision_state IN ('ACTIVE','STOPPING')
                     AND NOT (campaign_id=? AND run_id=?)""",
                (campaign_id, run_id),
            ).fetchone()[0]
        )
        if other_active_supervision:
            _block(blockers, "ORPHAN_ACTIVE_OWNERSHIP_AMBIGUOUS")

        shape, cycles, slots = (
            _admitted_shape(
                connection,
                campaign_id=campaign_id,
                run_id=run_id,
                origin_cycle_id=origin_cycle_id,
            )
            if identity_ok
            else (None, [], [])
        )
        if shape is None:
            _block(blockers, "ORPHAN_ADMITTED_SHAPE_INVALID")

        first_causes: list[str] = []
        for row in (campaign, run, supervision):
            if row and row.get("first_terminal_cause"):
                first_causes.append(str(row["first_terminal_cause"]))
        for row in cycles:
            if row.get("first_terminal_cause"):
                first_causes.append(str(row["first_terminal_cause"]))
        if first_causes and any(cause != RECOVERY_CAUSE for cause in first_causes):
            _block(blockers, "ORPHAN_FIRST_CAUSE_CONFLICT")

        factory_run_id = (
            None
            if run is None or not run.get("authoritative_run_id")
            else str(run["authoritative_run_id"])
        )
        active_work = (
            campaign_active_work_report(
                connection,
                factory_run_id=factory_run_id,
                campaign_id=campaign_id,
                run_id=run_id,
                cycle_id=None,
            )
            if identity_ok
            else {}
        )
        memory = (
            _memory_snapshot(connection, campaign_id=campaign_id, run_id=run_id)
            if identity_ok
            else {}
        )

        stable = {
            "schema_version": INSPECTION_SCHEMA_VERSION,
            "requested": {"campaign_id": campaign_id, "run_id": run_id},
            "identity": {
                "execution_id": execution_id,
                "campaign_id": campaign_id,
                "run_id": run_id,
                "configuration_id": configuration_id,
                "origin_cycle_id": origin_cycle_id,
                "supervision_id": None if supervision is None else supervision.get("supervision_id"),
                "owner_id": None if supervision is None else supervision.get("owner_id"),
                "factory_run_id": factory_run_id,
            },
            "command_mode": configuration.get("command_mode"),
            "policy_version": configuration.get("policy_version"),
            "authorization": authorization_evidence,
            "database": {
                "path": str(path),
                "sha256": _sha256_file(path),
                "migration_count": len(applied),
                "migration_head": applied[-1] if applied else None,
                "integrity": list(integrity),
                "foreign_key_violations": len(foreign_keys),
                "sidecars": sidecars,
            },
            "processes": {
                "matching_runtime_processes": [
                    {"pid": pid, "command": command}
                    for pid, command in matched_processes
                ]
            },
            "lease": lease_evidence,
            "admitted_shape": shape,
            "cycles": cycles,
            "slots": slots,
            "active_work": _jsonable(active_work),
            "memory": _jsonable(memory),
            "expected_recovery_cause": RECOVERY_CAUSE,
            "blockers": blockers,
        }
        inspection_sha256 = _canonical_sha(stable)
        return {
            **stable,
            "eligible": not blockers,
            "inspection_sha256": inspection_sha256,
            "observed_at": observed_at.isoformat(),
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        }
    finally:
        connection.close()


def _post_terminal_evidence(
    path: Path,
    *,
    campaign_id: str,
    run_id: str,
    inspection: Mapping[str, Any],
) -> dict[str, Any]:
    identity = dict(inspection.get("identity") or {})
    supervision_id = str(identity.get("supervision_id") or "")
    factory_run_id = identity.get("factory_run_id")
    connection = _read_only(path)
    try:
        campaign = _one(
            connection,
            "SELECT campaign_state,first_terminal_cause FROM "
            "printer_memory_factory_campaigns WHERE campaign_id=?",
            (campaign_id,),
        )
        run = _one(
            connection,
            "SELECT run_state,first_terminal_cause,authoritative_run_id FROM "
            "printer_memory_factory_campaign_runs WHERE campaign_id=? AND run_id=?",
            (campaign_id, run_id),
        )
        cycles = [
            dict(row)
            for row in connection.execute(
                """SELECT cycle_id,cycle_ordinal,cycle_state,first_terminal_cause
                   FROM printer_memory_factory_campaign_cycles
                   WHERE campaign_id=? AND run_id=? ORDER BY cycle_ordinal,cycle_id""",
                (campaign_id, run_id),
            ).fetchall()
        ]
        supervision = _one(
            connection,
            """SELECT supervision_state,terminal_status,first_terminal_cause,
                      cleanup_completed_at,lease_released_at,lease_lock_path
               FROM printer_memory_factory_campaign_supervision
               WHERE supervision_id=? AND campaign_id=? AND run_id=?""",
            (supervision_id, campaign_id, run_id),
        )
        active = campaign_active_work_report(
            connection,
            factory_run_id=(None if not factory_run_id else str(factory_run_id)),
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=None,
        )
        memory = _memory_snapshot(connection, campaign_id=campaign_id, run_id=run_id)
        counts = _row_counts(
            connection,
            (
                "printer_source_requests",
                "printer_scheduler_jobs",
                "printer_episodes",
                "printer_memory_fingerprints",
                "printer_memory_factory_campaigns",
                "printer_memory_factory_campaign_cycles",
            ),
        )
    finally:
        connection.close()
    lease_path = Path(str((supervision or {}).get("lease_lock_path") or ""))
    terminal = bool(
        campaign
        and campaign.get("campaign_state") == "TERMINAL_FAILED"
        and campaign.get("first_terminal_cause") == RECOVERY_CAUSE
        and run
        and run.get("run_state") == "TERMINAL_FAILED"
        and run.get("first_terminal_cause") == RECOVERY_CAUSE
        and cycles
        and all(
            str(row.get("cycle_state")) == "TERMINAL_FAILED"
            and row.get("first_terminal_cause") == RECOVERY_CAUSE
            for row in cycles
        )
        and supervision
        and supervision.get("supervision_state") == "TERMINAL"
        and supervision.get("terminal_status") == "FAILED"
        and supervision.get("first_terminal_cause") == RECOVERY_CAUSE
        and supervision.get("cleanup_completed_at") is not None
        and supervision.get("lease_released_at") is not None
        and not lease_path.exists()
        and active.get("clean_terminal") is True
    )
    return {
        "terminal_proven": terminal,
        "campaign": campaign,
        "run": run,
        "cycles": cycles,
        "supervision": supervision,
        "active_work": active,
        "memory": memory,
        "row_counts": counts,
        "lease_lock_absent": not lease_path.exists(),
    }


def terminalize_expired_orphan(
    db_path: str | Path,
    *,
    campaign_id: str,
    run_id: str,
    artifact_root: str | Path,
    inspection_sha256: str,
    operator_approved: bool,
    expected_db_path: str | Path | None = None,
    process_inventory: Callable[[], Iterable[tuple[int, str]]] | None = None,
    now: datetime | None = None,
    backup_preflight: Callable[..., Mapping[str, Any]] = (
        operational_backup_restore_preflight
    ),
) -> dict[str, Any]:
    """Explicitly terminalize one approved expired orphan; never resume it."""
    if operator_approved is not True:
        raise ExpiredOrphanReconciliationError("ORPHAN_OPERATOR_APPROVAL_REQUIRED")
    approved_sha = str(inspection_sha256 or "")
    if _SHA256_RE.fullmatch(approved_sha) is None:
        raise ExpiredOrphanReconciliationError("ORPHAN_INSPECTION_SHA_INVALID")

    path = Path(db_path).resolve()
    expected_path = Path(expected_db_path or db_path).resolve()
    artifacts = Path(artifact_root).resolve()
    initial = inspect_expired_orphan(
        path,
        campaign_id=campaign_id,
        run_id=run_id,
        artifact_root=artifacts,
        expected_db_path=expected_path,
        process_inventory=process_inventory,
        now=now,
    )
    if initial.get("eligible") is not True:
        raise ExpiredOrphanReconciliationError(
            "ORPHAN_INSPECTION_BLOCKED:" + ",".join(initial.get("blockers") or ())
        )
    if initial.get("inspection_sha256") != approved_sha:
        raise ExpiredOrphanReconciliationError("ORPHAN_INSPECTION_SHA_MISMATCH")

    identity = dict(initial["identity"])
    execution_id = str(identity["execution_id"])
    recovery_root = (
        artifacts / execution_id / "orphan-recovery" / approved_sha
    ).resolve()
    if recovery_root.exists():
        raise ExpiredOrphanReconciliationError("ORPHAN_RECOVERY_ARTIFACT_ALREADY_EXISTS")
    recovery_root.mkdir(parents=True, exist_ok=False)
    backup_path = recovery_root / "printer_v1.pre-recovery.backup.sqlite3"
    restore_path = recovery_root / "printer_v1.restore-rehearsal.sqlite3"

    before_connection = _read_only(path)
    try:
        before_counts = _row_counts(
            before_connection,
            (
                "printer_source_requests",
                "printer_scheduler_jobs",
                "printer_episodes",
                "printer_memory_fingerprints",
                "printer_memory_factory_campaigns",
                "printer_memory_factory_campaign_cycles",
            ),
        )
    finally:
        before_connection.close()
    before_memory = _jsonable(initial.get("memory") or {})

    try:
        backup = dict(
            backup_preflight(
                path,
                expected_source_path=expected_path,
                expected_source_identity=f"sha256:{initial['database']['sha256']}",
                backup_path=backup_path,
                disposable_restore_root=recovery_root,
                restore_path=restore_path,
            )
        )
    except Exception as exc:
        raise ExpiredOrphanReconciliationError(
            f"ORPHAN_BACKUP_PREFLIGHT_BLOCKED:{type(exc).__name__}"
        ) from exc

    repeated = inspect_expired_orphan(
        path,
        campaign_id=campaign_id,
        run_id=run_id,
        artifact_root=artifacts,
        expected_db_path=expected_path,
        process_inventory=process_inventory,
        now=now,
    )
    if repeated.get("eligible") is not True:
        raise ExpiredOrphanReconciliationError("ORPHAN_REINSPECTION_BLOCKED")
    if repeated.get("inspection_sha256") != approved_sha:
        raise ExpiredOrphanReconciliationError("ORPHAN_INSPECTION_SHA_MISMATCH")

    shape = str(repeated["admitted_shape"])
    origin_cycle_id = str(identity["origin_cycle_id"])
    factory_run_id = identity.get("factory_run_id")
    if shape == "PRE_ADMISSION":
        reconciliation = reconcile_campaign_terminal(
            path,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=origin_cycle_id,
            terminal_cause=RECOVERY_CAUSE,
            run_status="FAILED",
            factory_run_id=(None if not factory_run_id else str(factory_run_id)),
            lifecycle_started=bool(factory_run_id),
            now=_utc(now).isoformat(),
        )
    elif shape in {"CYCLE_1_ADMITTED", "TWO_CYCLES_ADMITTED"}:
        reconciliation = reconcile_admitted_campaign_terminal(
            path,
            campaign_id=campaign_id,
            run_id=run_id,
            primary_cycle_id=origin_cycle_id,
            terminal_cause=RECOVERY_CAUSE,
            run_status="FAILED",
            factory_run_id=(None if not factory_run_id else str(factory_run_id)),
            lifecycle_started=bool(factory_run_id),
            now=_utc(now).isoformat(),
        )
    else:  # defensive: inspection owns admitted-shape validity
        raise ExpiredOrphanReconciliationError("ORPHAN_ADMITTED_SHAPE_INVALID")

    cleanup = cleanup_campaign_supervision(
        path,
        supervision_id=str(identity["supervision_id"]),
        campaign_id=campaign_id,
        configuration_id=str(identity["configuration_id"]),
        run_id=run_id,
        owner_id=str(identity["owner_id"]),
        terminal_status="FAILED",
        first_terminal_cause=RECOVERY_CAUSE,
        now=_utc(now),
    )

    post = _post_terminal_evidence(
        path,
        campaign_id=campaign_id,
        run_id=run_id,
        inspection=repeated,
    )
    if post.get("terminal_proven") is not True:
        raise ExpiredOrphanReconciliationError("ORPHAN_TERMINAL_POSTCONDITION_FAILED")
    if post.get("row_counts") != before_counts:
        raise ExpiredOrphanReconciliationError("ORPHAN_FORBIDDEN_ROW_CREATION_DETECTED")

    after_memory = _jsonable(post.get("memory") or {})
    before_episodes = before_memory.get("episodes", [])
    before_fingerprints = before_memory.get("fingerprints", [])
    if after_memory.get("episodes", []) != before_episodes:
        raise ExpiredOrphanReconciliationError("ORPHAN_MEMORY_EPISODE_CHANGED")
    if after_memory.get("fingerprints", []) != before_fingerprints:
        raise ExpiredOrphanReconciliationError("ORPHAN_MEMORY_FINGERPRINT_CHANGED")

    artifact_payload = {
        "schema_version": RECOVERY_SCHEMA_VERSION,
        "status": "RECOVERED_TERMINAL_FAILED",
        "approved_inspection_sha256": approved_sha,
        "target": identity,
        "admitted_shape": shape,
        "first_terminal_cause": RECOVERY_CAUSE,
        "backup": backup,
        "reconciliation": _jsonable(reconciliation),
        "cleanup": _jsonable(cleanup),
        "postconditions": _jsonable(post),
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "restart_created": False,
        "rerun_created": False,
        "resume_created": False,
        "successor_created": False,
        "new_clean_memory_created": False,
    }
    artifact_path = recovery_root / "terminal-only-recovery.json"
    artifact_error: str | None = None
    try:
        with artifact_path.open("x", encoding="utf-8") as handle:
            handle.write(_canonical_bytes(artifact_payload).decode("utf-8"))
    except OSError as exc:
        artifact_error = f"{type(exc).__name__}:{exc}"

    return {
        "status": "RECOVERED_TERMINAL_FAILED",
        "first_terminal_cause": RECOVERY_CAUSE,
        "inspection_sha256": approved_sha,
        "admitted_shape": shape,
        "backup": backup,
        "reconciliation": _jsonable(reconciliation),
        "cleanup": _jsonable(cleanup),
        "postconditions": _jsonable(post),
        "recovery_artifact_path": str(artifact_path),
        "recovery_artifact_written": artifact_error is None,
        "recovery_artifact_error": artifact_error,
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "restart_created": False,
        "rerun_created": False,
        "resume_created": False,
        "successor_created": False,
    }


__all__ = [
    "AUTHORIZED_MODE",
    "ExpiredOrphanReconciliationError",
    "INSPECTION_SCHEMA_VERSION",
    "RECOVERY_CAUSE",
    "RECOVERY_SCHEMA_VERSION",
    "inspect_expired_orphan",
    "terminalize_expired_orphan",
]

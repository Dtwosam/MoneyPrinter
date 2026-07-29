"""Public V2-9.8 bounded persistent 15-minute Memory Factory command.

This is the only public operational entry point. It fixes the authoritative
database target, generates artifact identities internally, preserves the
Source Governor/Central Scheduler owners, and exposes zero-source auxiliary
modes. The legacy V2-9.7E pilot launcher is neither imported nor promoted.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
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

from printer_v1.db.migrate import (
    canonical_migration_count,
    canonical_migration_names,
    describe_migration_ledger_mismatch,
    validate_migration_ledger,
)
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
    persist_campaign_heartbeat_failure,
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
from printer_v1.operator_cli.candidate_acquisition_integration import (
    CLI_MODE_N2,
    CLI_MODE_N7,
    MODE_N2,
    MODE_N7,
    AcquisitionTransportOwner,
    CandidateAcquisitionIntegrationError,
    replay_candidate_acquisition_integration_report,
    run_candidate_acquisition_integration,
)
from printer_v1.operator_cli.live_candidate_acquisition_transport import (
    CandidateAcquisitionOneShotTransport,
    build_live_candidate_acquisition_transport_owner,
)
from printer_v1.operator_cli.cursor_continuity_recovery import (
    CLI_MODE_CURSOR_RECOVERY_N2,
    CursorRecoveryTransportOwner,
    build_live_cursor_recovery_transport_owner,
    run_cursor_continuity_recovery,
)


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
SELECTIVE_1H_MODE = "selective-1h-proof"
SELECTIVE_1H_PREFLIGHT_MODE = "selective-1h-preflight"
SELECTIVE_1H_REQUIRED_MIGRATION = "047_campaign_oneshot_linkage_binds.sql"
SELECTIVE_1H_TOTAL_DURATION_SECONDS = 3_900
SELECTIVE_1H_GOVERNED_REQUEST_CEILING = 92
SELECTIVE_1H_GOVERNED_REQUESTS_PER_TOKEN = 45
SELECTIVE_1H_SCHEDULER_ROW_CEILING = 82
SELECTIVE_1H_CONTINUATION_SECONDS = 2_700
LEASE_SECONDS = 90
HEARTBEAT_SECONDS = 30
FREE_PUBLIC_SOLANA_RPC = "https://api.mainnet-beta.solana.com"
ARTIFACT_ROOT = Path.home() / "PrinterOperations" / "v2-9-8"
AUTHORITATIVE_DB = Path(CANONICAL_PERSISTENT_DB).resolve()
# Live-derived from the single ordered migrations/*.sql source. Never hard-code.
EXPECTED_MIGRATION_COUNT = canonical_migration_count()
LOCKED_WINDOWS = ("WINDOW_1H", "WINDOW_4H", "WINDOW_12H", "WINDOW_24H")


def _selective_1h_terminal_projection(
    db_path: str | Path, *, campaign_id: str, run_id: str
) -> Mapping[str, Any] | None:
    """Return selective truth only for an authorized/reached selective run."""
    try:
        from printer_v1.operator_cli.operational_selective_1h import (
            load_selective_1h_reporting,
        )

        projection = load_selective_1h_reporting(
            str(db_path), campaign_id=campaign_id, run_id=run_id
        )
    except Exception:
        return None
    if (
        projection.get("selective_1h_authorized")
        or projection.get("continuation_objects")
    ):
        return projection
    return None


AUTHORITATIVE_SQLITE_RUNTIME_SIDECARS = (
    "data/printer_v1.sqlite3-journal",
    "data/printer_v1.sqlite3-wal",
    "data/printer_v1.sqlite3-shm",
)
# Action-local run identity for blocked-command source accounting. Never inherit
# a previous campaign's holder-ledger totals into a different public action.
_ACTION_RUN_CONTEXT: dict[str, str | None] = {"run_id": None}


@dataclass(frozen=True)
class _OperationalCampaignPolicy:
    mode: str
    duration_seconds: int
    selective_1h_continuation: bool
    governed_request_ceiling: int
    governed_requests_per_token: int
    scheduler_row_ceiling: int
    locked_windows: tuple[str, ...]


_NORMAL_CAMPAIGN_POLICY = _OperationalCampaignPolicy(
    mode="run",
    duration_seconds=TOTAL_DURATION_SECONDS,
    selective_1h_continuation=False,
    governed_request_ceiling=GOVERNED_15M_REQUEST_CEILING,
    governed_requests_per_token=GOVERNED_REQUESTS_PER_TOKEN,
    scheduler_row_ceiling=SCHEDULER_ROW_CEILING,
    locked_windows=LOCKED_WINDOWS,
)
_SELECTIVE_1H_PROOF_POLICY = _OperationalCampaignPolicy(
    mode=SELECTIVE_1H_MODE,
    duration_seconds=SELECTIVE_1H_TOTAL_DURATION_SECONDS,
    selective_1h_continuation=True,
    governed_request_ceiling=SELECTIVE_1H_GOVERNED_REQUEST_CEILING,
    governed_requests_per_token=SELECTIVE_1H_GOVERNED_REQUESTS_PER_TOKEN,
    scheduler_row_ceiling=SELECTIVE_1H_SCHEDULER_ROW_CEILING,
    locked_windows=("WINDOW_4H", "WINDOW_12H", "WINDOW_24H"),
)

# V2-9.8B.22 discovery-only qualification mode.
DISCOVERY_ONLY_MODE = "discovery-only"
DISCOVERY_ONLY_DURATION_SECONDS = 900
DISCOVERY_ONLY_OPERATION_BUDGET = 30
DISCOVERY_ONLY_REPORT_FILENAME = "discovery-only-qualification-report.json"
DISCOVERY_ONLY_CAPACITY_READY = "DISCOVERY_ONLY_CAPACITY_READY"
DISCOVERY_ONLY_HONEST_EXHAUSTION = "DISCOVERY_ONLY_HONEST_EXHAUSTION"
DISCOVERY_ONLY_SOURCE_UNAVAILABLE = "DISCOVERY_ONLY_SOURCE_UNAVAILABLE"
DISCOVERY_ONLY_BUDGET_EXHAUSTED = "DISCOVERY_ONLY_BUDGET_EXHAUSTED"
DISCOVERY_ONLY_DURATION_EXHAUSTED = "DISCOVERY_ONLY_DURATION_EXHAUSTED"
DISCOVERY_ONLY_FAILED = "DISCOVERY_ONLY_FAILED"
DISCOVERY_ONLY_TERMINAL_STATUSES = (
    DISCOVERY_ONLY_CAPACITY_READY,
    DISCOVERY_ONLY_HONEST_EXHAUSTION,
    DISCOVERY_ONLY_SOURCE_UNAVAILABLE,
    DISCOVERY_ONLY_BUDGET_EXHAUSTED,
    DISCOVERY_ONLY_DURATION_EXHAUSTED,
    DISCOVERY_ONLY_FAILED,
)
# Tables the discovery-only mode may write (discovery-owned evidence only).
DISCOVERY_ONLY_MUTATION_ALLOWLIST = (
    "printer_source_requests",
    "printer_source_responses",
    "printer_source_failures",
    "printer_source_health",
    "printer_source_rate_limits",
    "printer_external_source_operations",
    "printer_pumpswap_graduated_candidate_registry",
    "printer_discovery_batches",
    "printer_discovery_work",
    "printer_discovery_work_source_links",
    "printer_discovery_candidates",
    "printer_discovery_merged_candidates",
    "printer_discovery_candidate_contributions",
    "printer_discovery_provider_observations",
    "printer_discovery_provider_report_links",
    "printer_discovery_origin_verifications",
    "printer_discovery_pumpswap_confirmations",
    "printer_discovery_selection_links",
    "printer_discovery_selected_item_links",
    "printer_graduated_market_floor_state",
    "printer_eligible_token_reserve",
    "printer_discovery_exhaustion_certificates",
    "printer_pumpfun_finalized_origin_registry",
    "printer_pumpfun_origin_cursor",
    "printer_tokens",
    "printer_pairs",
)
# Production / financial / scheduler surfaces that must show zero row deltas.
DISCOVERY_ONLY_PROTECTED_ZERO_DELTA_TABLES = (
    "printer_memory_factory_campaigns",
    "printer_memory_factory_campaign_runs",
    "printer_memory_factory_campaign_cycles",
    "printer_memory_factory_campaign_token_slots",
    "printer_memory_factory_campaign_supervision",
    "printer_memory_factory_campaign_configurations",
    "printer_memory_factory_campaign_reports",
    "printer_memory_factory_campaign_report_objects",
    "printer_memory_factory_campaign_objects",
    "printer_memory_factory_campaign_scheduler_work",
    "printer_memory_factory_campaign_windows",
    "printer_memory_factory_campaign_heartbeat_failures",
    "printer_memory_factory_runs",
    "printer_memory_factory_run_steps",
    "printer_scheduler_jobs",
    "printer_tracking_queue",
    "printer_memory_windows",
    "printer_episodes",
    "printer_episode_outcomes",
    "printer_episode_snapshots",
    "printer_memory_fingerprints",
    "printer_memory_audit_reports",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_decision_audits",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
    "printer_paper_quote_evidence",
    "printer_proof_run_supervision",
    "printer_token_snapshots",
    "printer_snapshot_window_coverage",
    "printer_snapshot_gap_audits",
    "printer_micro_events",
    "printer_trading_flow_snapshots",
    "printer_safety_rug_snapshots",
    "printer_liquidity_exit_snapshots",
    "printer_market_regime_snapshots",
    "printer_solana_chain_heat_snapshots",
    "printer_holder_campaign_operation_ledgers",
    "printer_holder_evidence_attempts",
    "printer_holder_maturation_work",
    "printer_selection_batches",
    "printer_selection_batch_items",
    "printer_selection_rotation_state",
    "printer_token_lifecycle_events",
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


def _read_only(path: Path | None = None) -> sqlite3.Connection:
    # Resolve against the live module constant so tests can patch AUTHORITATIVE_DB
    # without being defeated by a function-default binding at import time.
    target = Path(path).resolve() if path is not None else AUTHORITATIVE_DB.resolve()
    expected = AUTHORITATIVE_DB.resolve()
    if target != expected or not target.is_file():
        raise OperationalMemoryFactoryError("authoritative database target mismatch")
    connection = sqlite3.connect(
        f"file:{target.as_posix()}?mode=ro", uri=True, timeout=0.0
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
                f"locked capability baseline drift: gate=locked_capability "
                f"table={table} actual={count} expected={allowed.get(table, 0)}"
            )


def _preflight_fail(gate: str, detail: str) -> None:
    """Fail closed with the exact preflight gate that blocked readiness."""
    raise OperationalMemoryFactoryError(
        f"operational preflight blocked: gate={gate}: {detail}"
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
        _preflight_fail(
            "database_target",
            "only data/printer_v1.sqlite3 is allowed "
            f"(resolved={path} expected={AUTHORITATIVE_DB})",
        )
    sidecars = [
        str(Path(f"{path}{suffix}"))
        for suffix in ("-wal", "-shm", "-journal")
        if Path(f"{path}{suffix}").exists()
    ]
    if sidecars:
        _preflight_fail(
            "sqlite_sidecar_quiescence",
            "SQLite sidecar state is not quiescent: " + ", ".join(sidecars),
        )
    root = (
        Path(repository_root).resolve()
        if repository_root is not None
        else AUTHORITATIVE_DB.parent.parent
    )
    try:
        provenance = _capture_operational_git_provenance(root)
    except GitProvenanceError as exc:
        _preflight_fail("git_provenance", str(exc))
    source = build_readiness_source_contract_preflight()
    dependency = assert_runtime_dependency_preflight(repository_root=root)
    budget = build_operational_budget_preflight(
        admission_operation_ceiling=ADMISSION_OPERATION_CEILING,
        discovery_request_ceiling=DISCOVERY_REQUEST_CEILING,
        governed_15m_request_ceiling=GOVERNED_15M_REQUEST_CEILING,
        governed_requests_per_token=GOVERNED_REQUESTS_PER_TOKEN,
    )
    if source["status"] != "READY":
        _preflight_fail(
            "source_contract",
            f"status={source.get('status')!r} detail={source!r}",
        )
    if dependency.status != "READY":
        _preflight_fail(
            "runtime_dependency",
            f"status={dependency.status!r} detail={dependency.to_dict()!r}",
        )
    if budget["status"] != "READY":
        _preflight_fail(
            "holder_budget",
            ";".join(budget["issues"]) or f"status={budget['status']!r}",
        )

    connection = _read_only(path)
    try:
        migrations = tuple(
            str(row[0]) for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY version"
            ).fetchall()
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

    ledger = validate_migration_ledger(migrations)
    if not ledger["matches"]:
        issues = describe_migration_ledger_mismatch(migrations)
        _preflight_fail(
            "migration_ledger",
            "; ".join(issues)
            or (
                f"applied_count={ledger['applied_count']} "
                f"canonical_count={ledger['canonical_count']}"
            ),
        )
    # Defensive equality: count is always derived from the same canonical source.
    if int(ledger["canonical_count"]) != canonical_migration_count():
        _preflight_fail(
            "migration_ledger",
            "canonical migration count derivation drifted",
        )
    if integrity != ("ok",):
        _preflight_fail(
            "database_integrity",
            f"PRAGMA integrity_check returned {integrity!r}",
        )
    if foreign_keys:
        sample = ", ".join(
            f"{row[0]}->{row[2]}" for row in foreign_keys[:5]
        )
        _preflight_fail(
            "foreign_keys",
            f"{len(foreign_keys)} violation(s); sample={sample}",
        )
    if any(active.values()):
        _preflight_fail(
            "active_operational_state",
            f"active counts={dict(active)}",
        )
    try:
        _validate_locked_baseline(locked)
    except OperationalMemoryFactoryError as exc:
        # Re-raise with gate prefix if not already structured.
        message = str(exc)
        if message.startswith("operational preflight blocked:"):
            raise
        _preflight_fail("locked_capability_baseline", message)
    if historical_audit != 1:
        _preflight_fail(
            "historical_paper_audit",
            f"expected exactly 1 null-position paper audit row, found {historical_audit}",
        )

    expected_names = canonical_migration_names()
    return {
        "status": "V2_9_8_OPERATIONAL_PREFLIGHT_READY",
        "database_path": str(path),
        "database_sha256": _sha256(path),
        "migration_count": len(migrations),
        "canonical_migration_count": len(expected_names),
        "latest_migration": migrations[-1],
        "latest_canonical_migration": expected_names[-1],
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


def build_selective_1h_preflight(
    *,
    db_path: str | Path = AUTHORITATIVE_DB,
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    """Fail-closed, read-only preflight for one selective WINDOW_1H proof."""
    path = Path(db_path).resolve()
    if path != AUTHORITATIVE_DB or not path.is_file():
        _preflight_fail(
            "database_target",
            "selective 1h proof requires the authoritative database identity",
        )
    connection = _read_only(path)
    try:
        applied_047 = connection.execute(
            "SELECT 1 FROM printer_schema_migrations WHERE version=?",
            (SELECTIVE_1H_REQUIRED_MIGRATION,),
        ).fetchone()
    except sqlite3.Error as exc:
        _preflight_fail("migration_047", str(exc))
    finally:
        connection.close()
    if applied_047 is None:
        _preflight_fail(
            "migration_047",
            f"required migration is not applied: {SELECTIVE_1H_REQUIRED_MIGRATION}",
        )

    base = build_activation_preflight(
        db_path=path,
        repository_root=repository_root,
    )
    try:
        from printer_v1.operator_cli.one_command_15m_factory import (
            run_one_command_15m_factory,
        )
        from printer_v1.operator_cli.operational_selective_1h import (
            evaluate_token_local_continuations,
        )
    except ImportError as exc:
        _preflight_fail("selective_1h_implementation", str(exc))
    if not callable(run_one_command_15m_factory) or not callable(
        evaluate_token_local_continuations
    ):
        _preflight_fail(
            "selective_1h_implementation",
            "canonical factory or continuation owner is unavailable",
        )
    required_locks = {"WINDOW_4H", "WINDOW_12H", "WINDOW_24H"}
    if set(_SELECTIVE_1H_PROOF_POLICY.locked_windows) != required_locks:
        _preflight_fail(
            "later_window_locks",
            "WINDOW_4H, WINDOW_12H and WINDOW_24H must remain locked",
        )
    if AUTOMATIC_RETRIES != 0:
        _preflight_fail("retry_policy", "automatic retries must remain zero")
    selective_budget = build_operational_budget_preflight(
        admission_operation_ceiling=ADMISSION_OPERATION_CEILING,
        discovery_request_ceiling=DISCOVERY_REQUEST_CEILING,
        governed_15m_request_ceiling=SELECTIVE_1H_GOVERNED_REQUEST_CEILING,
        governed_requests_per_token=SELECTIVE_1H_GOVERNED_REQUESTS_PER_TOKEN,
    )
    if selective_budget["status"] != "READY":
        _preflight_fail(
            "selective_1h_budget",
            ";".join(selective_budget["issues"]),
        )

    return {
        **base,
        "mode": SELECTIVE_1H_PREFLIGHT_MODE,
        "status": "V2_9_8B_SELECTIVE_1H_PREFLIGHT_READY",
        "migration_requirement": {
            "required": SELECTIVE_1H_REQUIRED_MIGRATION,
            "applied": True,
        },
        "selective_1h_implementation_available": True,
        "selective_1h_budget_preflight": selective_budget,
        "proof_policy": {
            "campaigns": 1,
            "cycles": 1,
            "starting_token_maximum": TOKEN_CAPACITY,
            "main_window": MAIN_WINDOW,
            "main_window_seconds": MAIN_WINDOW_SECONDS,
            "selective_1h_continuation": True,
            "continuation_seconds": SELECTIVE_1H_CONTINUATION_SECONDS,
            "continuous_four_hour": False,
            "locked_windows": _SELECTIVE_1H_PROOF_POLICY.locked_windows,
            "categorical_continue_only": True,
            "authoritative_clean_15m_episode_required": True,
            "automatic_retries": 0,
            "restart_created": False,
            "successor_created": False,
        },
        "proof_ceilings": {
            "duration_seconds": SELECTIVE_1H_TOTAL_DURATION_SECONDS,
            "discovery_requests": DISCOVERY_REQUEST_CEILING,
            "governed_requests": SELECTIVE_1H_GOVERNED_REQUEST_CEILING,
            "governed_requests_per_token": (
                SELECTIVE_1H_GOVERNED_REQUESTS_PER_TOKEN
            ),
            "scheduler_rows": SELECTIVE_1H_SCHEDULER_ROW_CEILING,
            "admission_operations": ADMISSION_OPERATION_CEILING,
            "reserved_mandatory_close_steps": TOKEN_CAPACITY * 2,
        },
        "host_awake_requirement": {
            "required": True,
            "operator_approval_affirms_host_awake": True,
            "recommended_guard": "caffeinate",
            "lease_expiry_behavior": "terminal_fail_closed_no_restart",
        },
        "backup_restore_requirement": {
            "required_before_campaign_creation": True,
            "owner": "operational_backup_restore_preflight",
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
        "summary": root / "terminal-summary.json",
    }


def _create_campaign_command(
    *,
    execution_id: str,
    paths: Mapping[str, Path],
    preflight: Mapping[str, Any],
    backup: Mapping[str, Any],
    now: str,
    policy: _OperationalCampaignPolicy = _NORMAL_CAMPAIGN_POLICY,
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
        duration_seconds=policy.duration_seconds,
        source_calls=ADMISSION_OPERATION_CEILING,
        scheduler_work=policy.scheduler_row_ceiling,
        storage_bytes=STORAGE_BYTE_CEILING,
        failures=FAILURE_CEILING,
    )
    configuration = {
        "token_capacity": TOKEN_CAPACITY,
        "ceilings": asdict(ceilings),
        "main_window": MAIN_WINDOW,
        "main_window_seconds": MAIN_WINDOW_SECONDS,
        "continuous_first_hour": bool(policy.selective_1h_continuation),
        "continuous_four_hour": False,
        "selective_1h_continuation": bool(policy.selective_1h_continuation),
        "command_mode": policy.mode,
        "locked_windows": policy.locked_windows,
        "support_5m_only": True,
        "automatic_retries": AUTOMATIC_RETRIES,
        "report_directory_identity": report_identity,
        "backup_preflight_references": {
            "preflight_status": "READY",
            "source_identity": backup["source_identity"],
            "backup_sha256": backup["backup_hash"],
            "required_migration": (
                SELECTIVE_1H_REQUIRED_MIGRATION
                if policy.selective_1h_continuation
                else "032_campaign_ownership_schema.sql"
            ),
            "latest_migration": backup["latest_rehearsed_migration"],
        },
        "inner_15m_ceilings": {
            "discovery_requests": DISCOVERY_REQUEST_CEILING,
            "governed_requests": policy.governed_request_ceiling,
            "governed_requests_per_token": policy.governed_requests_per_token,
            "scheduler_rows": policy.scheduler_row_ceiling,
            "reserved_mandatory_close_steps": (
                TOKEN_CAPACITY * 2 if policy.selective_1h_continuation else TOKEN_CAPACITY
            ),
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
    # Publish the exact run identity so blocked-command counters stay action-local.
    _ACTION_RUN_CONTEXT["run_id"] = run_id
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
                    evidence = {
                        "safe_error_type": "HeartbeatThreadError",
                        "safe_error_category": "LEASE_RENEWAL_ERROR",
                        "safe_message": (
                            "The heartbeat renewal thread did not confirm lease renewal."
                        ),
                        "sqlite_locked": False,
                        "attempted_at": _iso(),
                        "prior_heartbeat_at": None,
                        "prior_lease_expires_at": None,
                        "renewal_confirmed": False,
                        "terminal_cause": "LEASE_RENEWAL_UNCONFIRMED",
                    }
                    with self._failure_lock:
                        self._failure = {
                            "renewal_confirmed": False,
                            "renewal_error": evidence["safe_message"],
                            "renewal_error_type": evidence["safe_error_type"],
                            "renewal_error_category": evidence[
                                "safe_error_category"
                            ],
                            "sqlite_locked": False,
                            "failure_evidence": evidence,
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


def _latest_campaign_source_total(
    db_path: Path | str | None = None,
    *,
    run_id: str | None = None,
) -> int | None:
    """Best-effort durable campaign source total from the holder ledger.

    When ``run_id`` is provided, only that exact campaign run is considered so
    blocked-command counters stay action-local. Without a run filter this still
    prefers the latest supervision ledger row for recovery/diagnostics, but the
    public ``main`` blocked path must pass the current action's run identity.
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
            if run_id is not None:
                row = connection.execute(
                    """SELECT governed_requests
                       FROM printer_holder_campaign_operation_ledgers
                       WHERE run_id=?
                       ORDER BY created_at DESC
                       LIMIT 1""",
                    (run_id,),
                ).fetchone()
            else:
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
    factory_run_id: str | None = None,
    heartbeat_failure: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Attempt every canonical terminal owner without replacing the first fault."""
    heartbeat_evidence = dict(
        (heartbeat_failure or {}).get("failure_evidence") or {}
    )
    supplied_cause = str(
        heartbeat_evidence.get("terminal_cause")
        or getattr(original_exception, "terminal_cause", "")
    ).strip()
    original_cause = supplied_cause or (
        f"OPERATIONAL_CAMPAIGN_FAILED:{type(original_exception).__name__}"
    )
    cause = _existing_first_terminal_cause(command) or original_cause
    closure_errors: list[str] = []
    reconciliation: Mapping[str, Any] = {
        "reconciled": False,
        "restart_created": False,
        "successor_created": False,
    }
    cleanup: Mapping[str, Any] = {"cleanup_completed": False}
    if heartbeat_evidence:
        try:
            _with_sqlite_busy_retry(
                "heartbeat-evidence",
                lambda: persist_campaign_heartbeat_failure(
                    command.db_path,
                    supervision_id=command.supervision_id,
                    campaign_id=command.campaign_id,
                    configuration_id=command.configuration_id,
                    run_id=command.run_id,
                    owner_id=command.owner_id,
                    evidence=heartbeat_evidence,
                ),
            )
        except BaseException as exc:
            closure_errors.append(
                f"heartbeat-evidence:{type(exc).__name__}:{exc}"
            )
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
                factory_run_id=factory_run_id,
                lifecycle_started=bool(factory_run_id),
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
        factory_run_id=factory_run_id,
        execution_id=execution_id,
        terminal_status="FAILED",
        terminal_cause=cause,
        run_status="FAILED",
        lifecycle_started=bool(factory_run_id),
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
        fault_details=(
            {"heartbeat_failure": heartbeat_evidence}
            if heartbeat_evidence else None
        ),
        selective_1h=_selective_1h_terminal_projection(
            command.db_path,
            campaign_id=command.campaign_id,
            run_id=command.run_id,
        ),
        pre_lifecycle_admission=reporting.get("pre_lifecycle_admission"),
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


def _run_operational_campaign(
    *,
    policy: _OperationalCampaignPolicy,
    operator_approved: bool,
    owner: Any | None = None,
    pump_transport: Any | None = None,
    secondary_transport: Any | None = None,
    migration_transport: Any | None = None,
) -> dict[str, Any]:
    """Run one fixed-policy campaign through the canonical V2-9.8B owner."""
    if not operator_approved:
        raise OperationalMemoryFactoryError("explicit operator approval is required")
    preflight = (
        build_selective_1h_preflight()
        if policy.selective_1h_continuation
        else build_activation_preflight()
    )
    execution_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid.uuid4().hex[:12]
    )
    paths = _artifact_paths(execution_id)
    paths["root"].mkdir(parents=True, exist_ok=False)
    paths["reports"].mkdir()
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
        backup=backup, now=now, policy=policy,
    )
    heartbeat: _CampaignHeartbeat | None = None
    initialized_factory_run_id: str | None = None
    observed_heartbeat_failure: Mapping[str, Any] | None = None
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

        def retain_factory_run_id(factory_run_id: str) -> None:
            nonlocal initialized_factory_run_id
            candidate = str(factory_run_id).strip()
            if not candidate:
                raise OperationalMemoryFactoryError(
                    "initialized factory-run identity is empty"
                )
            if initialized_factory_run_id not in (None, candidate):
                raise OperationalMemoryFactoryError(
                    "initialized factory-run identity changed"
                )
            initialized_factory_run_id = candidate
            # Best-effort one-shot authoritative bind if factory path did not
            # already bind (idempotent). Never enables selective 1h production.
            try:
                bind_conn = sqlite3.connect(AUTHORITATIVE_DB)
                bind_conn.execute("PRAGMA foreign_keys=ON")
                try:
                    from printer_v1.operator_cli.operational_selective_1h import (
                        ensure_authoritative_factory_link,
                    )
                    ensure_authoritative_factory_link(
                        bind_conn,
                        campaign_run_id=str(command.run_id),
                        factory_run_id=candidate,
                    )
                    bind_conn.commit()
                finally:
                    bind_conn.close()
            except Exception:
                # Factory already binds when campaign_run_id is present; this
                # path is a redundant safety net and must not abort production.
                pass

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
                "total_duration_seconds": policy.duration_seconds,
                "launch_provenance": preflight["git_provenance"],
                "cancellation_probe": cancellation_probe,
                "factory_run_initialized": retain_factory_run_id,
                # Fixed by the public mode; normal run can never opt into 1h.
                "selective_1h_continuation": policy.selective_1h_continuation,
                "configuration_id": command.configuration_id,
            },
            migration_transport=migration_transport,
            graduated_supply_kwargs=dict(OPERATIONAL_GRADUATED_SUPPLY_KWARGS),
            fifteen_minute_only=True,
        )
        # Heartbeat never terminalizes. Main coordinator observes failure signal.
        heartbeat_failure = heartbeat.poll_failure() if heartbeat is not None else None
        observed_heartbeat_failure = heartbeat_failure
        if heartbeat is not None:
            heartbeat.stop()
            heartbeat = None
        lifecycle = dict(result.lifecycle)
        returned_factory_run_id = str(lifecycle.get("run_id") or "").strip() or None
        if returned_factory_run_id is not None:
            retain_factory_run_id(returned_factory_run_id)
        cause = str(
            lifecycle.get("first_terminal_cause")
            or lifecycle.get("stop_reason")
            or "PRE_LIFECYCLE_GOVERNED_SAFE_STOP"
        )
        if heartbeat_failure is not None:
            heartbeat_evidence = dict(
                heartbeat_failure.get("failure_evidence") or {}
            )
            if heartbeat_evidence:
                persist_campaign_heartbeat_failure(
                    command.db_path,
                    supervision_id=command.supervision_id,
                    campaign_id=command.campaign_id,
                    configuration_id=command.configuration_id,
                    run_id=command.run_id,
                    owner_id=command.owner_id,
                    evidence=heartbeat_evidence,
                )
            # Prefer an existing lifecycle terminal cause; otherwise surface the
            # heartbeat signal so the main path can cleanup once.
            if cause in {"PRE_LIFECYCLE_GOVERNED_SAFE_STOP", ""} or cause.startswith(
                "LEASE_RENEWAL_"
            ):
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
            factory_run_id=initialized_factory_run_id,
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
            factory_run_id=initialized_factory_run_id,
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
            fault_details=lifecycle.get("fault_details"),
            selective_1h=_selective_1h_terminal_projection(
                command.db_path,
                campaign_id=command.campaign_id,
                run_id=command.run_id,
            ),
            pre_lifecycle_admission=reporting.get("pre_lifecycle_admission"),
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
            "fault_details": dict(lifecycle.get("fault_details") or {}),
            "token_capacity": TOKEN_CAPACITY,
            "main_window": MAIN_WINDOW,
            "selective_1h_continuation": policy.selective_1h_continuation,
            "continuous_four_hour": False,
            "locked_windows": policy.locked_windows,
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
                factory_run_id=initialized_factory_run_id,
                heartbeat_failure=(
                    heartbeat.poll_failure()
                    if heartbeat is not None else observed_heartbeat_failure
                ),
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


def run_operational_campaign(
    *,
    operator_approved: bool,
    owner: Any | None = None,
    pump_transport: Any | None = None,
    secondary_transport: Any | None = None,
    migration_transport: Any | None = None,
) -> dict[str, Any]:
    """Run one bounded persistent 15m-only production campaign."""
    return _run_operational_campaign(
        policy=_NORMAL_CAMPAIGN_POLICY,
        operator_approved=operator_approved,
        owner=owner,
        pump_transport=pump_transport,
        secondary_transport=secondary_transport,
        migration_transport=migration_transport,
    )


def run_selective_1h_proof(
    *,
    operator_approved: bool,
    owner: Any | None = None,
    pump_transport: Any | None = None,
    secondary_transport: Any | None = None,
    migration_transport: Any | None = None,
) -> dict[str, Any]:
    """Run exactly one operator-approved bounded selective WINDOW_1H proof."""
    return _run_operational_campaign(
        policy=_SELECTIVE_1H_PROOF_POLICY,
        operator_approved=operator_approved,
        owner=owner,
        pump_transport=pump_transport,
        secondary_transport=secondary_transport,
        migration_transport=migration_transport,
    )


def _latest_supervision(connection: sqlite3.Connection) -> sqlite3.Row:
    row = connection.execute(
        """SELECT * FROM printer_memory_factory_campaign_supervision
           ORDER BY created_at DESC, supervision_id DESC LIMIT 1"""
    ).fetchone()
    if row is None:
        raise OperationalMemoryFactoryError("no operational campaign supervision exists")
    return row


def _table_row_counts(connection: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for (name,) in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'printer_%'"
    ).fetchall():
        table = str(name)
        try:
            counts[table] = int(
                connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            )
        except sqlite3.Error:
            counts[table] = -1
    return counts


def _count_deltas(
    before: Mapping[str, int], after: Mapping[str, int]
) -> dict[str, int]:
    keys = set(before) | set(after)
    deltas: dict[str, int] = {}
    for key in sorted(keys):
        delta = int(after.get(key, 0)) - int(before.get(key, 0))
        if delta != 0:
            deltas[key] = delta
    return deltas


def _protected_nonzero_deltas(deltas: Mapping[str, int]) -> dict[str, int]:
    return {
        table: int(deltas[table])
        for table in DISCOVERY_ONLY_PROTECTED_ZERO_DELTA_TABLES
        if int(deltas.get(table, 0)) != 0
    }


def _allowlist_write_total(deltas: Mapping[str, int]) -> int:
    total = 0
    for table in DISCOVERY_ONLY_MUTATION_ALLOWLIST:
        delta = int(deltas.get(table, 0))
        if delta > 0:
            total += delta
    return total


def _discovery_only_report_path(execution_id: str) -> Path:
    return (ARTIFACT_ROOT / execution_id / DISCOVERY_ONLY_REPORT_FILENAME).resolve()


def _load_latest_discovery_only_report() -> dict[str, Any] | None:
    """Load the newest discovery-only qualification report from the artifact root."""
    root = ARTIFACT_ROOT
    if not root.is_dir():
        return None
    newest: tuple[float, Path] | None = None
    for path in root.glob(f"*/{DISCOVERY_ONLY_REPORT_FILENAME}"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if newest is None or mtime > newest[0]:
            newest = (mtime, path)
    if newest is None:
        return None
    try:
        payload = json.loads(newest[1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get("mode") or "") != DISCOVERY_ONLY_MODE:
        return None
    payload = dict(payload)
    payload.setdefault("report_path", str(newest[1]))
    return payload


def _map_discovery_only_status(
    *,
    ready: bool,
    shortage_classification: str | None,
    last_stop_reason: str | None,
) -> str:
    from printer_v1.discovery.eligible_token_supply import (
        BUDGET_EXHAUSTION,
        DURATION_EXHAUSTION,
        SOURCE_AVAILABILITY_FAILURE,
        SOURCE_VISIBILITY_SHORTAGE,
        TRUE_MARKET_SUPPLY_SHORTAGE,
    )

    if ready:
        return DISCOVERY_ONLY_CAPACITY_READY
    classification = str(shortage_classification or "")
    stop = str(last_stop_reason or "")
    if classification == SOURCE_AVAILABILITY_FAILURE or stop in {
        "PROVIDER_FAILURE",
        "SOURCE_UNAVAILABLE",
    }:
        return DISCOVERY_ONLY_SOURCE_UNAVAILABLE
    if classification == BUDGET_EXHAUSTION or stop == "DISCOVERY_OPERATION_BUDGET_EXHAUSTED":
        return DISCOVERY_ONLY_BUDGET_EXHAUSTED
    if classification == DURATION_EXHAUSTION or stop == "CAMPAIGN_DURATION_EXHAUSTED":
        return DISCOVERY_ONLY_DURATION_EXHAUSTED
    if classification in {
        TRUE_MARKET_SUPPLY_SHORTAGE,
        SOURCE_VISIBILITY_SHORTAGE,
    }:
        return DISCOVERY_ONLY_HONEST_EXHAUSTION
    if classification:
        return DISCOVERY_ONLY_FAILED
    return DISCOVERY_ONLY_FAILED


def _write_discovery_only_report(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(dict(payload), indent=2, sort_keys=True, default=str) + "\n"
    path.write_text(text, encoding="utf-8")
    summary = path.parent / "terminal-summary.json"
    summary.write_text(text, encoding="utf-8")
    return path


def run_discovery_only_qualification(
    *,
    operator_approved: bool,
    migration_transport: Any | None = None,
    dexscreener_transport_factory: Any | None = None,
    verifier_transport_factory: Any | None = None,
    locator_transport: Any | None = None,
    now: str | None = None,
    discovery_operation_budget: int | None = None,
    duration_seconds: int | None = None,
    collection_rounds: int | None = None,
    max_candidates: int | None = None,
    settle_seconds: float | None = None,
    reverify_on_transient: bool | None = None,
    reverify_settle_seconds: float | None = None,
    front_door_max_candidates: int | None = None,
    run_locator: bool | None = None,
) -> dict[str, Any]:
    """Run one bounded discovery-only live qualification (no production campaign).

    Fixture transports may be injected for disposable proof. Default transports
    are live free sources through Source Governor. This mode never calls Central
    Scheduler runtime, never creates production campaign/supervision, and never
    unlocks retrieval or financial capabilities.
    """
    if not operator_approved:
        raise OperationalMemoryFactoryError("explicit operator approval is required")

    # Resolve against the live module constant so disposable tests can patch
    # AUTHORITATIVE_DB (function defaults bind the import-time path).
    preflight = build_activation_preflight(db_path=AUTHORITATIVE_DB)
    started = datetime.now(timezone.utc)
    now_iso = now or _iso(started)
    execution_id = (
        started.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
    )
    qualification_id = f"{execution_id}-discovery-only"
    run_id = f"{qualification_id}-run"
    cycle_id = f"{qualification_id}-cycle"
    _ACTION_RUN_CONTEXT["run_id"] = run_id

    paths = _artifact_paths(execution_id)
    paths["root"].mkdir(parents=True, exist_ok=False)
    paths["reports"].mkdir()
    report_path = paths["root"] / DISCOVERY_ONLY_REPORT_FILENAME

    duration = (
        DISCOVERY_ONLY_DURATION_SECONDS
        if duration_seconds is None
        else int(duration_seconds)
    )
    budget = (
        DISCOVERY_ONLY_OPERATION_BUDGET
        if discovery_operation_budget is None
        else int(discovery_operation_budget)
    )
    deadline_dt = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
    if deadline_dt.tzinfo is None:
        deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)
    deadline_at = (deadline_dt + timedelta(seconds=duration)).isoformat()

    supply_kwargs = dict(OPERATIONAL_GRADUATED_SUPPLY_KWARGS)
    if collection_rounds is not None:
        supply_kwargs["collection_rounds"] = int(collection_rounds)
    if max_candidates is not None:
        supply_kwargs["max_candidates"] = int(max_candidates)
    if settle_seconds is not None:
        supply_kwargs["settle_seconds"] = float(settle_seconds)
    if reverify_on_transient is not None:
        supply_kwargs["reverify_on_transient"] = bool(reverify_on_transient)
    if reverify_settle_seconds is not None:
        supply_kwargs["reverify_settle_seconds"] = float(reverify_settle_seconds)
    if front_door_max_candidates is not None:
        supply_kwargs["front_door_max_candidates"] = int(front_door_max_candidates)
    if run_locator is not None:
        supply_kwargs["run_locator"] = bool(run_locator)

    if migration_transport is None:
        from printer_v1.sources.pumpportal import build_pumpportal_migration_transport

        migration_transport = build_pumpportal_migration_transport(
            max_events=4, duration_seconds=120.0, connect_timeout_seconds=10.0,
        )

    connection = sqlite3.connect(AUTHORITATIVE_DB)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        before_counts = _table_row_counts(connection)
    finally:
        connection.close()

    from printer_v1.discovery.eligible_token_supply import (
        run_persistent_eligible_token_supply,
    )

    terminal_status = DISCOVERY_ONLY_FAILED
    supply_result: Any | None = None
    failure_message: str | None = None
    try:
        supply_result = run_persistent_eligible_token_supply(
            AUTHORITATIVE_DB,
            cycle_seed=execution_id,
            migration_transport=migration_transport,
            verifier_transport_factory=verifier_transport_factory,
            dexscreener_transport_factory=dexscreener_transport_factory,
            locator_transport=locator_transport,
            now=now_iso,
            collection_rounds=int(supply_kwargs["collection_rounds"]),
            max_candidates=int(supply_kwargs["max_candidates"]),
            settle_seconds=float(supply_kwargs["settle_seconds"]),
            reverify_on_transient=bool(supply_kwargs["reverify_on_transient"]),
            reverify_settle_seconds=float(supply_kwargs["reverify_settle_seconds"]),
            front_door_max_candidates=int(supply_kwargs["front_door_max_candidates"]),
            discovery_request_key_prefix=f"v2-9-8b-22-{execution_id}",
            front_door_request_key_prefix=f"v2-9-8b-22-{execution_id}",
            run_locator=bool(supply_kwargs["run_locator"]),
            required_token_capacity=TOKEN_CAPACITY,
            discovery_operation_budget=budget,
            deadline_at=deadline_at,
            campaign_id=qualification_id,
            execution_id=execution_id,
            run_id=run_id,
            cycle_id=cycle_id,
        )
    except BaseException as exc:
        failure_message = f"{type(exc).__name__}:{exc}"
        supply_result = None

    connection = sqlite3.connect(AUTHORITATIVE_DB)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        after_counts = _table_row_counts(connection)
        active = _active_counts(connection)
        integrity = tuple(
            str(row[0])
            for row in connection.execute("PRAGMA integrity_check").fetchall()
        )
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        connection.close()

    deltas = _count_deltas(before_counts, after_counts)
    protected_deltas = _protected_nonzero_deltas(deltas)
    unexpected_writes = {
        table: delta
        for table, delta in deltas.items()
        if delta > 0 and table not in DISCOVERY_ONLY_MUTATION_ALLOWLIST
    }
    database_writes = _allowlist_write_total(deltas) + sum(
        max(0, int(v)) for v in unexpected_writes.values()
    )

    diagnostics: dict[str, Any] = {}
    eligible_reserve: list[dict[str, Any]] = []
    exhaustion_certificate: dict[str, Any] | None = None
    shortage_classification: str | None = None
    discovery_rounds = 0
    candidates_observed = 0
    unique_candidates_observed = 0
    duplicate_candidates_removed = 0
    candidates_validated = 0
    source_operations_used = 0
    source_operations_remaining = budget
    selected_candidate_mints: list[str] = []
    ready = False

    if supply_result is not None:
        diagnostics = dict(supply_result.diagnostics or {})
        eligible_reserve = list(supply_result.eligible_reserve or [])
        ready = bool(supply_result.ready)
        discovery_rounds = int(supply_result.discovery_rounds or 0)
        shortage_classification = supply_result.shortage_classification
        if supply_result.exhaustion_certificate is not None:
            exhaustion_certificate = supply_result.exhaustion_certificate.to_dict()
        all_candidates = list(supply_result.all_candidates or [])
        candidates_observed = len(all_candidates)
        unique_candidates_observed = int(
            diagnostics.get("evaluated_unique_mints") or len(all_candidates)
        )
        duplicate_candidates_removed = int(
            diagnostics.get("duplicate_observations_removed") or 0
        )
        candidates_validated = candidates_observed
        source_operations_used = int(
            diagnostics.get("discovery_operations_used")
            or diagnostics.get("stage_local_source_requests")
            or 0
        )
        source_operations_remaining = int(
            diagnostics.get("discovery_operations_remaining")
            if diagnostics.get("discovery_operations_remaining") is not None
            else max(0, budget - source_operations_used)
        )
        selected_candidate_mints = [
            str(c["mint"]) for c in eligible_reserve[:TOKEN_CAPACITY] if c.get("mint")
        ]
        terminal_status = _map_discovery_only_status(
            ready=ready,
            shortage_classification=shortage_classification,
            last_stop_reason=str(diagnostics.get("last_stop_reason") or ""),
        )
        if ready and len(selected_candidate_mints) < TOKEN_CAPACITY:
            terminal_status = DISCOVERY_ONLY_FAILED
            failure_message = "capacity-ready without two selected mints"
    else:
        terminal_status = DISCOVERY_ONLY_FAILED

    if protected_deltas or unexpected_writes:
        terminal_status = DISCOVERY_ONLY_FAILED
        failure_message = (
            (failure_message + "; " if failure_message else "")
            + f"mutation_boundary protected={protected_deltas} unexpected={unexpected_writes}"
        )
    if any(active.values()):
        terminal_status = DISCOVERY_ONLY_FAILED
        failure_message = (
            (failure_message + "; " if failure_message else "")
            + f"active_residue={dict(active)}"
        )
    if integrity != ("ok",):
        terminal_status = DISCOVERY_ONLY_FAILED
        failure_message = (
            (failure_message + "; " if failure_message else "")
            + f"integrity={integrity!r}"
        )
    if foreign_keys:
        terminal_status = DISCOVERY_ONLY_FAILED
        failure_message = (
            (failure_message + "; " if failure_message else "")
            + f"foreign_keys={len(foreign_keys)}"
        )

    if (
        terminal_status == DISCOVERY_ONLY_HONEST_EXHAUSTION
        and exhaustion_certificate is None
    ):
        terminal_status = DISCOVERY_ONLY_FAILED
        failure_message = (
            (failure_message + "; " if failure_message else "")
            + "honest exhaustion missing certificate"
        )

    payload: dict[str, Any] = {
        "mode": DISCOVERY_ONLY_MODE,
        "execution_id": execution_id,
        "qualification_id": qualification_id,
        "status": terminal_status,
        "discovery_rounds": discovery_rounds,
        "candidates_observed": candidates_observed,
        "unique_candidates_observed": unique_candidates_observed,
        "duplicate_candidates_removed": duplicate_candidates_removed,
        "candidates_validated": candidates_validated,
        "eligible_reserve_count": len(eligible_reserve),
        "required_token_capacity": TOKEN_CAPACITY,
        "selected_candidate_mints": selected_candidate_mints,
        "source_operations_used": source_operations_used,
        "source_operations_remaining": source_operations_remaining,
        "scheduler_runtime_calls": 0,
        "database_writes": database_writes,
        "shortage_classification": shortage_classification,
        "exhaustion_certificate": exhaustion_certificate,
        "report_path": str(report_path),
        "restart_created": False,
        "successor_created": False,
        "automatic_retry_created": False,
        "source_calls": source_operations_used,
        "source_accounting": {
            "source_operations_used": source_operations_used,
            "source_operations_remaining": source_operations_remaining,
            "discovery_operation_budget": budget,
            "admission_operation_ceiling": ADMISSION_OPERATION_CEILING,
            "scheduler_runtime_calls": 0,
        },
        "mutation_allowlist": list(DISCOVERY_ONLY_MUTATION_ALLOWLIST),
        "protected_table_deltas": protected_deltas,
        "unexpected_table_deltas": unexpected_writes,
        "table_deltas": deltas,
        "active_residue": dict(active),
        "integrity": "ok" if integrity == ("ok",) else list(integrity),
        "foreign_key_violations": len(foreign_keys),
        "git_provenance": preflight.get("git_provenance"),
        "duration_seconds": duration,
        "deadline_at": deadline_at,
        "diagnostics": diagnostics,
        "failure_message": failure_message,
        "policy": {
            "token_capacity": TOKEN_CAPACITY,
            "main_window": MAIN_WINDOW,
            "support_5m_only": True,
            "automatic_retries": AUTOMATIC_RETRIES,
            "selection_floor_usd": 3000.0,
            "evaluation_batch_size": int(supply_kwargs["front_door_max_candidates"]),
            "no_central_scheduler_runtime": True,
            "no_production_campaign": True,
            "no_tracking_handoff": True,
            "no_retrieval_or_financial_unlock": True,
        },
    }
    _write_discovery_only_report(report_path, payload)
    return payload


def run_candidate_acquisition_only(
    *,
    mode: str,
    operator_approved: bool,
    transport_owner: AcquisitionTransportOwner | None = None,
    preflight_override: Mapping[str, Any] | None = None,
    execution_id: str | None = None,
    owner_id: str | None = None,
    now: str | None = None,
    db_path: str | Path | None = None,
    renewal_hook: Any | None = None,
    cancellation_probe: Any | None = None,
) -> dict[str, Any]:
    """Run one bounded foundation-backed acquisition-only command mode.

    Live execution requires an explicitly constructed approved transport owner.
    Offline integration proof injects frozen adapters through this same public
    command seam; no alternate runner exists.
    """
    if transport_owner is None:
        raise CandidateAcquisitionIntegrationError(
            "APPROVED_ACQUISITION_TRANSPORT_OWNER_REQUIRED"
        )
    target = Path(db_path or AUTHORITATIVE_DB).resolve()
    preflight = dict(preflight_override or build_activation_preflight(db_path=target))
    instant = now or _iso()
    action_execution_id = execution_id or (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-acq-"
        + uuid.uuid4().hex[:12]
    )
    action_owner_id = owner_id or f"candidate-acquisition-owner:{action_execution_id}"
    _ACTION_RUN_CONTEXT["run_id"] = action_execution_id
    return run_candidate_acquisition_integration(
        target,
        mode=mode,
        operator_approved=operator_approved,
        transport_owner=transport_owner,
        preflight=preflight,
        execution_id=action_execution_id,
        owner_id=action_owner_id,
        now=instant,
        renewal_hook=renewal_hook,
        cancellation_probe=cancellation_probe,
    )


def run_cursor_recovery_only(
    *,
    operator_approved: bool,
    transport_owner: CursorRecoveryTransportOwner | None = None,
    preflight_override: Mapping[str, Any] | None = None,
    execution_id: str | None = None,
    owner_id: str | None = None,
    now: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run one explicit finite cursor-recovery execution."""
    if transport_owner is None:
        raise CandidateAcquisitionIntegrationError(
            "APPROVED_CURSOR_RECOVERY_TRANSPORT_OWNER_REQUIRED"
        )
    target = Path(db_path or AUTHORITATIVE_DB).resolve()
    preflight = dict(preflight_override or build_activation_preflight(db_path=target))
    instant = now or _iso()
    action_execution_id = execution_id or (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-recovery-"
        + uuid.uuid4().hex[:12]
    )
    action_owner_id = owner_id or f"cursor-recovery-owner:{action_execution_id}"
    _ACTION_RUN_CONTEXT["run_id"] = action_execution_id
    return run_cursor_continuity_recovery(
        target,
        operator_approved=operator_approved,
        transport_owner=transport_owner,
        preflight=preflight,
        execution_id=action_execution_id,
        owner_id=action_owner_id,
        now=instant,
    )


def operational_status() -> dict[str, Any]:
    discovery_only = _load_latest_discovery_only_report()
    discovery_summary = None
    if discovery_only is not None:
        discovery_summary = {
            "mode": discovery_only.get("mode"),
            "execution_id": discovery_only.get("execution_id"),
            "qualification_id": discovery_only.get("qualification_id"),
            "status": discovery_only.get("status"),
            "eligible_reserve_count": discovery_only.get("eligible_reserve_count"),
            "required_token_capacity": discovery_only.get("required_token_capacity"),
            "selected_candidate_mints": discovery_only.get("selected_candidate_mints"),
            "shortage_classification": discovery_only.get("shortage_classification"),
            "report_path": discovery_only.get("report_path"),
            "source_operations_used": discovery_only.get("source_operations_used"),
            "scheduler_runtime_calls": discovery_only.get("scheduler_runtime_calls"),
            "restart_created": discovery_only.get("restart_created"),
            "successor_created": discovery_only.get("successor_created"),
        }
    campaign_status: Any | None = None
    supervision_error: str | None = None
    row = None
    connection = _read_only()
    try:
        try:
            row = _latest_supervision(connection)
        except OperationalMemoryFactoryError as exc:
            supervision_error = str(exc)
            row = None
    finally:
        connection.close()
    if row is not None:
        campaign_status = inspect_campaign_supervision(
            AUTHORITATIVE_DB,
            supervision_id=row["supervision_id"],
            campaign_id=row["campaign_id"],
            configuration_id=row["configuration_id"],
            run_id=row["run_id"],
            owner_id=row["owner_id"],
        )
    elif discovery_summary is None:
        raise OperationalMemoryFactoryError(
            supervision_error or "no operational campaign supervision exists"
        )
    return {
        "mode": "STATUS",
        "status": campaign_status,
        "discovery_only_qualification": discovery_summary,
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
    discovery_only = _load_latest_discovery_only_report()
    connection = _read_only()
    try:
        row = connection.execute(
            """SELECT r.report_id,r.campaign_id,r.configuration_id,
                      c.configuration_json, r.created_at
               FROM printer_memory_factory_campaign_reports AS r
               JOIN printer_memory_factory_campaign_configurations AS c
                 ON c.configuration_id=r.configuration_id
               WHERE r.report_state='REPORT_TERMINAL'
               ORDER BY r.created_at DESC,r.report_id DESC LIMIT 1"""
        ).fetchone()
    finally:
        connection.close()

    # Prefer discovery-only when it is the only report or newer than the latest
    # campaign terminal report.
    prefer_discovery = False
    if discovery_only is not None:
        if row is None:
            prefer_discovery = True
        else:
            try:
                discovery_path = Path(str(discovery_only.get("report_path") or ""))
                if discovery_path.is_file():
                    discovery_mtime = discovery_path.stat().st_mtime
                    # Campaign report created_at is ISO; compare via path mtime
                    # of matching report dir when available, else prefer discovery
                    # when its execution_id is newer lexicographically.
                    campaign_created = str(row["created_at"] or "")
                    discovery_exec = str(discovery_only.get("execution_id") or "")
                    prefer_discovery = bool(
                        discovery_exec
                        and (
                            discovery_exec >= campaign_created.replace(":", "").replace(
                                "+", ""
                            )[:15]
                            or discovery_mtime > 0
                        )
                    )
                    # Strong rule: if discovery-only report exists and was written
                    # after the campaign report timestamp, prefer it.
                    try:
                        campaign_dt = datetime.fromisoformat(
                            campaign_created.replace("Z", "+00:00")
                        )
                        prefer_discovery = discovery_mtime >= campaign_dt.timestamp()
                    except ValueError:
                        prefer_discovery = True
            except OSError:
                prefer_discovery = True

    if prefer_discovery and discovery_only is not None:
        return {
            "mode": "REPORT_ONLY",
            "report_kind": DISCOVERY_ONLY_MODE,
            "qualification": discovery_only,
            "execution_id": discovery_only.get("execution_id"),
            "qualification_id": discovery_only.get("qualification_id"),
            "status": discovery_only.get("status"),
            "discovery_rounds": discovery_only.get("discovery_rounds"),
            "candidates_observed": discovery_only.get("candidates_observed"),
            "candidates_validated": discovery_only.get("candidates_validated"),
            "eligible_candidates": discovery_only.get("eligible_reserve_count"),
            "required_token_capacity": discovery_only.get("required_token_capacity"),
            "selected_candidate_mints": discovery_only.get("selected_candidate_mints"),
            "shortage_classification": discovery_only.get("shortage_classification"),
            "exhaustion_certificate": discovery_only.get("exhaustion_certificate"),
            "report_path": discovery_only.get("report_path"),
            "restart_created": False,
            "successor_created": False,
            "replay_new_source_calls": 0,
            "replay_new_scheduler_calls": 0,
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        }

    if row is None:
        if discovery_only is not None:
            return {
                "mode": "REPORT_ONLY",
                "report_kind": DISCOVERY_ONLY_MODE,
                "qualification": discovery_only,
                "execution_id": discovery_only.get("execution_id"),
                "qualification_id": discovery_only.get("qualification_id"),
                "status": discovery_only.get("status"),
                "report_path": discovery_only.get("report_path"),
                "restart_created": False,
                "successor_created": False,
                "replay_new_source_calls": 0,
                "replay_new_scheduler_calls": 0,
                "source_calls": 0,
                "scheduler_runtime_calls": 0,
                "database_writes": 0,
            }
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
        "report_kind": "campaign",
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
        "discovery_only_qualification": (
            None
            if discovery_only is None
            else {
                "execution_id": discovery_only.get("execution_id"),
                "qualification_id": discovery_only.get("qualification_id"),
                "status": discovery_only.get("status"),
                "report_path": discovery_only.get("report_path"),
            }
        ),
        # Report-only itself performs no new Source Governor / Scheduler work.
        "replay_new_source_calls": 0,
        "replay_new_scheduler_calls": 0,
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "database_writes": 0,
    }


def main(
    argv: Iterable[str] | None = None,
    *,
    acquisition_transport_owner: AcquisitionTransportOwner | None = None,
    acquisition_preflight: Mapping[str, Any] | None = None,
    acquisition_execution_id: str | None = None,
    acquisition_now: str | None = None,
    acquisition_db_path: str | Path | None = None,
    acquisition_environment: Mapping[str, str] | None = None,
    acquisition_one_shot_transport: CandidateAcquisitionOneShotTransport | None = None,
    cursor_recovery_transport_owner: CursorRecoveryTransportOwner | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Printer V1 bounded persistent 15m Memory Factory command. "
            "Modes: preflight-only, run, selective-1h-preflight, "
            "selective-1h-proof, status, cooperative-stop, recover-orphan, "
            "report-only, discovery-only, acquisition-only-n2, acquisition-only-n7, "
            "cursor-recovery-n2."
        )
    )
    parser.add_argument(
        "mode",
        choices=(
            "preflight-only", "run", SELECTIVE_1H_PREFLIGHT_MODE,
            SELECTIVE_1H_MODE, "status", "cooperative-stop", "recover-orphan",
            "report-only", "discovery-only",
            CLI_MODE_N2, CLI_MODE_N7, CLI_MODE_CURSOR_RECOVERY_N2,
        ),
    )
    parser.add_argument("--operator-approved", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    # Reset action-local identity at the start of every public invocation so a
    # blocked preflight/status/report never inherits a previous campaign total.
    _ACTION_RUN_CONTEXT["run_id"] = None
    try:
        if args.mode == "preflight-only":
            result = build_activation_preflight()
        elif args.mode == SELECTIVE_1H_PREFLIGHT_MODE:
            result = build_selective_1h_preflight()
        elif args.mode == "run":
            result = run_operational_campaign(operator_approved=args.operator_approved)
        elif args.mode == SELECTIVE_1H_MODE:
            result = run_selective_1h_proof(
                operator_approved=args.operator_approved
            )
        elif args.mode == "discovery-only":
            result = run_discovery_only_qualification(
                operator_approved=args.operator_approved
            )
        elif args.mode in {CLI_MODE_N2, CLI_MODE_N7}:
            resolved_transport_owner = acquisition_transport_owner
            if resolved_transport_owner is None:
                if not args.operator_approved:
                    raise CandidateAcquisitionIntegrationError(
                        "EXPLICIT_OPERATOR_APPROVAL_REQUIRED"
                    )
                resolved_transport_owner = build_live_candidate_acquisition_transport_owner(
                    environment=acquisition_environment,
                    transport=acquisition_one_shot_transport,
                )
            result = run_candidate_acquisition_only(
                mode=MODE_N2 if args.mode == CLI_MODE_N2 else MODE_N7,
                operator_approved=args.operator_approved,
                transport_owner=resolved_transport_owner,
                preflight_override=acquisition_preflight,
                execution_id=acquisition_execution_id,
                now=acquisition_now,
                db_path=acquisition_db_path,
            )
        elif args.mode == CLI_MODE_CURSOR_RECOVERY_N2:
            resolved_recovery_owner = cursor_recovery_transport_owner
            if resolved_recovery_owner is None:
                if not args.operator_approved:
                    raise CandidateAcquisitionIntegrationError(
                        "EXPLICIT_OPERATOR_APPROVAL_REQUIRED"
                    )
                resolved_recovery_owner = build_live_cursor_recovery_transport_owner(
                    environment=acquisition_environment,
                    transport=acquisition_one_shot_transport,
                )
            result = run_cursor_recovery_only(
                operator_approved=args.operator_approved,
                transport_owner=resolved_recovery_owner,
                preflight_override=acquisition_preflight,
                execution_id=acquisition_execution_id,
                now=acquisition_now,
                db_path=acquisition_db_path,
            )
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
        # V2-9.8B.10 / V2-9.8B.19: surface a durable total only for the exact
        # run identity created by this action. Never copy a previous campaign's
        # holder-ledger counters into preflight/status/report-only failures.
        action_run_id = _ACTION_RUN_CONTEXT.get("run_id")
        campaign_source_calls: int | None = None
        campaign_modes = {"run", SELECTIVE_1H_MODE}
        if args.mode in campaign_modes and action_run_id:
            campaign_source_calls = _latest_campaign_source_total(run_id=str(action_run_id))
        elif args.mode in campaign_modes:
            # Run failed before campaign creation (e.g. preflight). Action-local
            # total remains zero; do not inherit historical ledgers.
            campaign_source_calls = None
        elif args.mode in {
            "discovery-only", CLI_MODE_N2, CLI_MODE_N7,
            CLI_MODE_CURSOR_RECOVERY_N2,
        }:
            # Discovery-only never inherits campaign holder ledgers.
            campaign_source_calls = None
        source_calls = (
            int(campaign_source_calls) if campaign_source_calls is not None else 0
        )
        print(
            json.dumps(
                {
                    "status": "OPERATIONAL_COMMAND_BLOCKED",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "mode": args.mode,
                    "action_run_id": action_run_id,
                    "campaign_source_calls": campaign_source_calls,
                    "source_calls": source_calls,
                    "scheduler_runtime_calls": 0,
                    "database_writes": 0,
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
    "DISCOVERY_ONLY_MODE",
    "DISCOVERY_ONLY_MUTATION_ALLOWLIST",
    "DISCOVERY_ONLY_PROTECTED_ZERO_DELTA_TABLES",
    "DISCOVERY_ONLY_TERMINAL_STATUSES",
    "EXPECTED_MIGRATION_COUNT",
    "LOCKED_WINDOWS",
    "MAIN_WINDOW",
    "OPERATIONAL_GRADUATED_SUPPLY_KWARGS",
    "SELECTIVE_1H_GOVERNED_REQUEST_CEILING",
    "SELECTIVE_1H_GOVERNED_REQUESTS_PER_TOKEN",
    "SELECTIVE_1H_MODE",
    "SELECTIVE_1H_PREFLIGHT_MODE",
    "SELECTIVE_1H_REQUIRED_MIGRATION",
    "SELECTIVE_1H_SCHEDULER_ROW_CEILING",
    "SELECTIVE_1H_TOTAL_DURATION_SECONDS",
    "TOKEN_CAPACITY",
    "_ACTION_RUN_CONTEXT",
    "_latest_campaign_source_total",
    "_terminalize_initialized_failure",
    "_with_sqlite_busy_retry",
    "build_activation_preflight",
    "build_selective_1h_preflight",
    "canonical_migration_count",
    "canonical_migration_names",
    "cooperative_stop",
    "main",
    "operational_status",
    "recover_orphan",
    "report_only",
    "run_discovery_only_qualification",
    "run_operational_campaign",
    "run_selective_1h_proof",
    "validate_migration_ledger",
]

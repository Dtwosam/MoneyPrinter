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
import re
from pathlib import Path
import sqlite3
import sys
import threading
import time
from typing import Any, Callable, Iterable, Mapping, Sequence
import uuid

from printer_v1.db.migrate import (
    canonical_migration_count,
    canonical_migration_names,
    describe_migration_ledger_mismatch,
    validate_migration_ledger,
)
from printer_v1.db.sqlite_write_contracts import DEFAULT_OPERATIONAL_BUSY_TIMEOUT_MS
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS,
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
    LiveOperationalError,
    LiveTransportError,
    OneShotUrllibPumpTransport,
    OneShotUrllibSecondaryTransport,
)
from printer_v1.operator_cli.graduated_supply_front_door import (
    OPERATIONAL_GRADUATED_SUPPLY_KWARGS,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_OPERATIONAL_PERSISTENT,
    build_authorization_marker_payload,
    campaign_evidence_sha256,
    create_operational_campaign_graph,
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
from printer_v1.operator_cli.git_provenance_authorization_manifest import (
    GitProvenanceAuthorizationError,
    STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
    ValidatedGitProvenanceAuthorization,
    validate_git_provenance_authorization,
)
from printer_v1.operator_cli.operational_backup_restore_preflight import (
    operational_backup_restore_preflight,
)
from printer_v1.operator_cli.operational_campaign_recovery import (
    production_recovery_paths,
    recover_exact_orphan,
)
from printer_v1.operator_cli.operational_standard_4h import (
    standard_four_hour_capacity_contract,
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
from printer_v1.sources.operational_source_contracts import (
    OFFICIAL_SOLANA_PUBLIC_RPC_URL,
    resolve_solana_rpc_configuration,
)


POLICY_VERSION = "V2-9.8-15M-OPERATIONAL-V1"
ACTIVE_INTAKE_PATH = "PROVEN_TWO_TOKEN_OPERATIONAL_DISCOVERY_SELECTION"
CANDIDATE_ACQUISITION_STATE = "DEFERRED_EXPERIMENTAL_NOT_OPERATIONAL_AUTHORITY"
DEFERRED_CANDIDATE_ACQUISITION_MODES = (
    "acquisition-only-n2",
    "acquisition-only-n7",
    "cursor-recovery-n2",
)
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
STANDARD_FOUR_HOUR_MODE = "standard-four-hour-run"
STANDARD_FOUR_HOUR_PREFLIGHT_MODE = "standard-four-hour-preflight"
STANDARD_FOUR_HOUR_POLICY_VERSION = "V2-9.8-STANDARD-4H-OPERATIONAL-V1"
STANDARD_FOUR_HOUR_TOTAL_DURATION_SECONDS = 14_700
# Standard-four-hour capacity is projected from the one derived public contract
# in ``operational_standard_4h``, which in turn derives from the canonical
# ``one_token_4h_runtime`` lifecycle arithmetic. This command owns no
# independent standard-four-hour numeric capacity.
_STANDARD_FOUR_HOUR_CAPACITY = standard_four_hour_capacity_contract()
STANDARD_FOUR_HOUR_GOVERNED_REQUEST_CEILING = int(
    _STANDARD_FOUR_HOUR_CAPACITY["lifecycle_request_outer_ceiling"]
)
STANDARD_FOUR_HOUR_GOVERNED_REQUESTS_PER_TOKEN = int(
    _STANDARD_FOUR_HOUR_CAPACITY["lifecycle_requests_per_token"]
)
STANDARD_FOUR_HOUR_SCHEDULER_ROW_CEILING = int(
    _STANDARD_FOUR_HOUR_CAPACITY["lifecycle_scheduler_outer_ceiling"]
)
LEASE_SECONDS = 90
HEARTBEAT_SECONDS = 30
CANCELLATION_PROBE_SQLITE_BUSY_TIMEOUT_SECONDS = (
    DEFAULT_OPERATIONAL_BUSY_TIMEOUT_MS / 1000.0
)
CANCELLATION_PROBE_SQLITE_LOCKED = "CANCELLATION_PROBE_SQLITE_LOCKED"
FREE_PUBLIC_SOLANA_RPC = OFFICIAL_SOLANA_PUBLIC_RPC_URL
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
# Bounded, authorization-bound Git-provenance manifest/marker compatibility. The
# four values are supplied by the external one-shot wrapper only to the single
# authorized child process. They are accepted together or not at all, and only
# for the exact ordinary preflight/run boundary.
GIT_PROVENANCE_MANIFEST_ENV_VARS = (
    "PRINTER_V1_GIT_PROVENANCE_MANIFEST_PATH",
    "PRINTER_V1_GIT_PROVENANCE_MANIFEST_SHA256",
    "PRINTER_V1_APPLICATION_MARKER_PATH",
    "PRINTER_V1_APPLICATION_MARKER_SHA256",
)
GIT_PROVENANCE_MANIFEST_SUPPORTED_MODES = (
    "preflight-only", "run", STANDARD_FOUR_HOUR_MODE
)
# Action-local run identity for blocked-command source accounting. Never inherit
# a previous campaign's holder-ledger totals into a different public action.
_ACTION_RUN_CONTEXT: dict[str, Any] = {
    "run_id": None,
    "campaign_id": None,
    "cycle_id": None,
    "execution_id": None,
    "action_local_baseline": None,
    "mutation_recorder": None,
}


@dataclass(frozen=True)
class _OperationalCampaignPolicy:
    mode: str
    policy_version: str
    duration_seconds: int
    selective_1h_continuation: bool
    governed_request_ceiling: int
    governed_requests_per_token: int
    scheduler_row_ceiling: int
    locked_windows: tuple[str, ...]
    # V2-9.8B Post-DTW98: bounded pre-lifecycle acquisition horizon. It is
    # separate from ``duration_seconds`` (the post-supply operational/lifecycle
    # envelope) and from the 900s WINDOW_15M evidence window. It raises no
    # source-operation or financial ceiling; it only makes the total one-shot
    # wall-time envelope explicit instead of hidden.
    pre_lifecycle_acquisition_duration_seconds: int = (
        PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS
    )
    continuous_four_hour: bool = False
    standard_four_hour_campaign: bool = False


_NORMAL_CAMPAIGN_POLICY = _OperationalCampaignPolicy(
    mode="run",
    policy_version=POLICY_VERSION,
    duration_seconds=TOTAL_DURATION_SECONDS,
    selective_1h_continuation=False,
    governed_request_ceiling=GOVERNED_15M_REQUEST_CEILING,
    governed_requests_per_token=GOVERNED_REQUESTS_PER_TOKEN,
    scheduler_row_ceiling=SCHEDULER_ROW_CEILING,
    locked_windows=LOCKED_WINDOWS,
)
_SELECTIVE_1H_PROOF_POLICY = _OperationalCampaignPolicy(
    mode=SELECTIVE_1H_MODE,
    policy_version=POLICY_VERSION,
    duration_seconds=SELECTIVE_1H_TOTAL_DURATION_SECONDS,
    selective_1h_continuation=True,
    governed_request_ceiling=SELECTIVE_1H_GOVERNED_REQUEST_CEILING,
    governed_requests_per_token=SELECTIVE_1H_GOVERNED_REQUESTS_PER_TOKEN,
    scheduler_row_ceiling=SELECTIVE_1H_SCHEDULER_ROW_CEILING,
    locked_windows=("WINDOW_4H", "WINDOW_12H", "WINDOW_24H"),
)
STANDARD_FOUR_HOUR_POLICY = _OperationalCampaignPolicy(
    mode=STANDARD_FOUR_HOUR_MODE,
    policy_version=STANDARD_FOUR_HOUR_POLICY_VERSION,
    duration_seconds=STANDARD_FOUR_HOUR_TOTAL_DURATION_SECONDS,
    selective_1h_continuation=True,
    governed_request_ceiling=STANDARD_FOUR_HOUR_GOVERNED_REQUEST_CEILING,
    governed_requests_per_token=STANDARD_FOUR_HOUR_GOVERNED_REQUESTS_PER_TOKEN,
    scheduler_row_ceiling=STANDARD_FOUR_HOUR_SCHEDULER_ROW_CEILING,
    locked_windows=("WINDOW_12H", "WINDOW_24H"),
    pre_lifecycle_acquisition_duration_seconds=(
        PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS
    ),
    continuous_four_hour=True,
    standard_four_hour_campaign=True,
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


@dataclass(frozen=True)
class _PreparedDisposablePublicCompositionExecution:
    db_path: Path
    artifact_root: Path
    materialized: Any


@dataclass(frozen=True)
class _DisposablePublicCompositionOwnerBridge:
    proof_binding: Any
    pump_transport: Any
    secondary_transport: Any
    migration_transport: Any
    graduated_supply_kwargs: dict[str, Any]
    lifecycle_kwargs: dict[str, Any]
    operational_database_target_binding: Any | None
    disposable_public_composition_proof_binding: Any
    db_path: Path
    artifact_root: Path
    provider_fallback_allowed: bool = False
    # Approved-owner transports for the pre-lifecycle temporal refresh stage.
    # Production leaves them None so the governed adapters build their own real
    # free/public transports; disposable composition proofs inject fixtures here
    # to exercise the real production refresh boundary without network access.
    geckoterminal_nomination_transport: Any | None = None
    protocol_account_batch_transport: Any | None = None


def _is_campaign_run_identity(candidate: str, *, campaign_run_id: str | None = None) -> bool:
    """True when a candidate identity is campaign-run shaped, not factory UUID."""
    value = str(candidate or "").strip()
    if not value:
        return False
    campaign = str(campaign_run_id or "").strip()
    if campaign and value == campaign:
        return True
    return value.endswith("-campaign-run")


def _extract_returned_factory_run_id(
    lifecycle: Mapping[str, Any],
    *,
    campaign_run_id: str | None = None,
) -> str | None:
    """Return factory-run identity only; never adopt campaign-run as factory.

    Prefer explicit ``factory_run_id``. Historical lifecycle reports place the
    factory UUID in ``run_id`` after genuine lifecycle entry; that path is kept
    only when the value is not campaign-run shaped.
    """
    explicit = str(lifecycle.get("factory_run_id") or "").strip()
    if explicit:
        if _is_campaign_run_identity(explicit, campaign_run_id=campaign_run_id):
            return None
        return explicit
    candidate = str(lifecycle.get("run_id") or "").strip()
    if not candidate:
        return None
    lifecycle_campaign = (
        str(lifecycle.get("campaign_run_id") or "").strip() or campaign_run_id
    )
    if _is_campaign_run_identity(candidate, campaign_run_id=lifecycle_campaign):
        return None
    return candidate


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


def _read_only(
    path: str | Path | None = None,
    *,
    expected_path: str | Path | None = None,
    timeout_seconds: float = 0.0,
) -> sqlite3.Connection:
    # Production defaults to AUTHORITATIVE_DB. C8 may supply one exact already-
    # validated disposable target; arbitrary mismatched paths still fail closed.
    expected = (
        Path(expected_path).resolve()
        if expected_path is not None
        else AUTHORITATIVE_DB.resolve()
    )
    target = Path(path).resolve() if path is not None else expected
    if target != expected or not target.is_file():
        raise OperationalMemoryFactoryError("database target mismatch")
    connection = sqlite3.connect(
        f"file:{target.as_posix()}?mode=ro",
        uri=True,
        timeout=max(0.0, float(timeout_seconds)),
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def _sqlite_busy_or_locked(exc: sqlite3.OperationalError) -> bool:
    raw = str(exc).lower()
    return "locked" in raw or "busy" in raw


def _read_campaign_supervision_cancellation_reason(
    path: str | Path,
    *,
    expected_path: str | Path,
    supervision_id: str,
    campaign_id: str,
    run_id: str,
    busy_timeout_seconds: float = CANCELLATION_PROBE_SQLITE_BUSY_TIMEOUT_SECONDS,
) -> str | None:
    """Read cancellation state with bounded tolerance for a legitimate writer."""
    try:
        connection = _read_only(
            path,
            expected_path=expected_path,
            timeout_seconds=busy_timeout_seconds,
        )
        try:
            row = connection.execute(
                """SELECT supervision_state,cancellation_reason
                   FROM printer_memory_factory_campaign_supervision
                   WHERE supervision_id=? AND campaign_id=? AND run_id=?""",
                (supervision_id, campaign_id, run_id),
            ).fetchone()
        finally:
            connection.close()
    except sqlite3.OperationalError as exc:
        if _sqlite_busy_or_locked(exc):
            return CANCELLATION_PROBE_SQLITE_LOCKED
        raise
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


def _capture_operational_git_provenance(
    root: Path,
    *,
    additional_allowed_untracked_paths: Iterable[str] = (),
) -> dict[str, Any]:
    # The fixed SQLite runtime sidecars are always allowed. Any additional exact
    # repository-relative path comes only from a fully validated authorization
    # manifest; the canonical six-field payload from capture_git_provenance()
    # remains unchanged.
    allowed = (
        tuple(AUTHORITATIVE_SQLITE_RUNTIME_SIDECARS)
        + tuple(additional_allowed_untracked_paths)
    )
    provenance = capture_git_provenance(root, allowed_untracked_paths=allowed)
    if provenance["git_untracked_present"]:
        raise GitProvenanceError(
            "launch Git tree contains an arbitrary untracked file"
        )
    return provenance


def _resolve_git_provenance_authorization(
    mode: str,
    *,
    environ: Mapping[str, str] | None = None,
    repository_root: str | Path | None = None,
) -> ValidatedGitProvenanceAuthorization | None:
    """Resolve the optional external manifest/marker authorization.

    The four environment variables are accepted only all-together and only for
    the exact ordinary ``preflight-only``/``run`` boundary. Any partial set, or
    any presence under an unsupported mode, fails closed. When none are present
    the operational command behaves exactly as before.
    """
    env = os.environ if environ is None else environ
    present = {name: env.get(name) for name in GIT_PROVENANCE_MANIFEST_ENV_VARS}
    supplied = [name for name, value in present.items() if value not in (None, "")]
    if not supplied:
        return None
    if len(supplied) != len(GIT_PROVENANCE_MANIFEST_ENV_VARS):
        missing = [name for name in GIT_PROVENANCE_MANIFEST_ENV_VARS if name not in supplied]
        raise OperationalMemoryFactoryError(
            "git provenance manifest environment variables must all be set "
            "together or all be unset: missing=" + ", ".join(missing)
        )
    if mode not in GIT_PROVENANCE_MANIFEST_SUPPORTED_MODES:
        raise OperationalMemoryFactoryError(
            "git provenance manifest integration is not accepted for "
            f"mode={mode!r}"
        )
    root = (
        Path(repository_root).resolve()
        if repository_root is not None
        else AUTHORITATIVE_DB.parent.parent
    )
    try:
        validation_kwargs = {
            "repository_root": root,
            "manifest_path": present["PRINTER_V1_GIT_PROVENANCE_MANIFEST_PATH"],
            "manifest_sha256": present["PRINTER_V1_GIT_PROVENANCE_MANIFEST_SHA256"],
            "marker_path": present["PRINTER_V1_APPLICATION_MARKER_PATH"],
            "marker_sha256": present["PRINTER_V1_APPLICATION_MARKER_SHA256"],
            "sidecar_untracked_paths": AUTHORITATIVE_SQLITE_RUNTIME_SIDECARS,
        }
        if mode == STANDARD_FOUR_HOUR_MODE:
            validation_kwargs["profile"] = STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        return validate_git_provenance_authorization(**validation_kwargs)
    except GitProvenanceAuthorizationError as exc:
        raise OperationalMemoryFactoryError(
            f"git provenance manifest authorization rejected: {exc}"
        ) from exc


def _resolve_disposable_public_composition_targets(
    disposable_proof: Any,
) -> dict[str, Any]:
    # Resolve only a fully validated C8 runtime capability.
    from printer_v1.operator_cli.window_15m_disposable_public_composition_proof import (
        DisposablePublicCompositionProofRuntime,
        build_disposable_public_composition_proof_runtime,
    )

    if not isinstance(disposable_proof, DisposablePublicCompositionProofRuntime):
        raise OperationalMemoryFactoryError(
            "DISPOSABLE_PUBLIC_COMPOSITION_PROOF_RUNTIME_REQUIRED"
        )
    validated = build_disposable_public_composition_proof_runtime(
        disposable_proof.plan,
        disposable_proof.fixture_composition,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
    )
    if (
        validated.fixture_composition_manifest_sha256
        != disposable_proof.fixture_composition_manifest_sha256
    ):
        raise OperationalMemoryFactoryError(
            "FIXTURE_COMPOSITION_MANIFEST_MISMATCH"
        )
    db_path = Path(validated.plan.resolved_db_path).resolve()
    artifact_root = Path(validated.plan.resolved_artifact_root).resolve()
    if db_path == Path(CANONICAL_PERSISTENT_DB).resolve():
        raise OperationalMemoryFactoryError(
            "CANONICAL_PRODUCTION_DB_FORBIDDEN"
        )
    return {
        "db_path": str(db_path),
        "artifact_root": str(artifact_root),
        "fixture_composition_manifest_sha256": (
            validated.fixture_composition_manifest_sha256
        ),
    }


def _prepare_disposable_public_composition_execution(
    disposable_proof: Any,
) -> _PreparedDisposablePublicCompositionExecution:
    # Materialize only after the proof plan/registry boundary is validated.
    from printer_v1.operator_cli.window_15m_disposable_public_composition_proof import (
        materialize_disposable_public_composition_execution,
    )

    targets = _resolve_disposable_public_composition_targets(disposable_proof)
    materialized = materialize_disposable_public_composition_execution(
        disposable_proof
    )
    if materialized.provider_fallback_allowed is not False:
        raise OperationalMemoryFactoryError(
            "FIXTURE_PROVIDER_FALLBACK_FORBIDDEN"
        )
    if (
        materialized.fixture_composition_manifest_sha256
        != targets["fixture_composition_manifest_sha256"]
    ):
        raise OperationalMemoryFactoryError(
            "FIXTURE_COMPOSITION_MANIFEST_MISMATCH"
        )
    return _PreparedDisposablePublicCompositionExecution(
        db_path=Path(targets["db_path"]).resolve(),
        artifact_root=Path(targets["artifact_root"]).resolve(),
        materialized=materialized,
    )


def _build_disposable_public_composition_owner_bridge(
    *,
    disposable_proof: Any,
    prepared_proof: _PreparedDisposablePublicCompositionExecution,
    execution_id: str,
) -> _DisposablePublicCompositionOwnerBridge:
    # Build invocation-bound C8 owner inputs from the already validated,
    # materialized proof capability. This helper cannot run a campaign.
    from printer_v1.operator_cli.window_15m_disposable_public_composition_proof import (
        DisposablePublicCompositionProofRuntime,
        build_disposable_public_composition_proof_binding,
    )

    if not isinstance(disposable_proof, DisposablePublicCompositionProofRuntime):
        raise OperationalMemoryFactoryError(
            "DISPOSABLE_PUBLIC_COMPOSITION_PROOF_RUNTIME_REQUIRED"
        )
    execution = str(execution_id or "").strip()
    if not execution:
        raise OperationalMemoryFactoryError(
            "DISPOSABLE_PROOF_EXECUTION_ID_REQUIRED"
        )

    plan = disposable_proof.plan
    materialized = prepared_proof.materialized
    db_path = Path(prepared_proof.db_path).resolve()
    artifact_root = Path(prepared_proof.artifact_root).resolve()

    if db_path != Path(plan.resolved_db_path).resolve():
        raise OperationalMemoryFactoryError(
            "DISPOSABLE_PROOF_DB_PATH_MISMATCH"
        )
    if artifact_root != Path(plan.resolved_artifact_root).resolve():
        raise OperationalMemoryFactoryError(
            "DISPOSABLE_PROOF_ARTIFACT_ROOT_MISMATCH"
        )
    if (
        materialized.fixture_composition_manifest_sha256
        != disposable_proof.fixture_composition_manifest_sha256
    ):
        raise OperationalMemoryFactoryError(
            "FIXTURE_COMPOSITION_MANIFEST_MISMATCH"
        )
    if materialized.provider_fallback_allowed is not False:
        raise OperationalMemoryFactoryError(
            "FIXTURE_PROVIDER_FALLBACK_FORBIDDEN"
        )

    campaign_id = f"{execution}-campaign"
    campaign_run_id = f"{execution}-campaign-run"
    cycle_id = f"{execution}-cycle"
    configuration_id = f"{execution}-configuration"
    db_target_identity = f"sha256:{plan.pre_mutation_db_sha256}"

    binding = build_disposable_public_composition_proof_binding(
        plan,
        execution_id=execution,
        campaign_id=campaign_id,
        campaign_run_id=campaign_run_id,
        cycle_id=cycle_id,
        configuration_id=configuration_id,
        db_target_identity=db_target_identity,
        fixture_composition_manifest_sha256=(
            disposable_proof.fixture_composition_manifest_sha256
        ),
    )

    top_level = dict(materialized.top_level_transports)
    required_top_level = {
        "pump_transport",
        "secondary_transport",
        "migration_transport",
    }
    if set(top_level) != required_top_level:
        raise OperationalMemoryFactoryError(
            "FIXTURE_TOP_LEVEL_TRANSPORT_IDENTITY_MISMATCH"
        )

    lifecycle_kwargs = dict(materialized.lifecycle_kwargs)
    lifecycle_kwargs["context_adapter_factories"] = dict(
        lifecycle_kwargs["context_adapter_factories"]
    )

    return _DisposablePublicCompositionOwnerBridge(
        proof_binding=binding,
        pump_transport=top_level["pump_transport"],
        secondary_transport=top_level["secondary_transport"],
        migration_transport=top_level["migration_transport"],
        graduated_supply_kwargs=dict(materialized.graduated_supply_kwargs),
        lifecycle_kwargs=lifecycle_kwargs,
        operational_database_target_binding=None,
        disposable_public_composition_proof_binding=binding,
        db_path=db_path,
        artifact_root=artifact_root,
        provider_fallback_allowed=False,
    )


def build_disposable_public_composition_preflight(
    disposable_proof: Any,
    *,
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    # Read-only C8 proof preflight. It never executes fixture builders.
    targets = _resolve_disposable_public_composition_targets(disposable_proof)
    plan = disposable_proof.plan
    path = Path(targets["db_path"]).resolve()
    if not path.is_file():
        _preflight_fail("disposable_database_target", "proof DB is missing")
    if _sha256(path) != str(plan.pre_mutation_db_sha256):
        _preflight_fail("disposable_database_target", "proof DB SHA-256 drifted")
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
        else Path(__file__).resolve().parents[3]
    )
    try:
        provenance = _capture_operational_git_provenance(root)
    except GitProvenanceError as exc:
        _preflight_fail("git_provenance", str(exc))
    try:
        connection = sqlite3.connect(
            f"file:{path.as_posix()}?mode=ro", uri=True, timeout=0.0
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        migrations = tuple(
            str(row[0])
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY version"
            ).fetchall()
        )
        integrity = tuple(
            str(row[0])
            for row in connection.execute("PRAGMA integrity_check").fetchall()
        )
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        active = _active_counts(connection)
        locked = _locked_capability_counts(connection)
    except sqlite3.Error as exc:
        _preflight_fail("disposable_database", str(exc))
    finally:
        try:
            connection.close()
        except Exception:
            pass
    ledger = validate_migration_ledger(migrations)
    if not ledger["matches"]:
        _preflight_fail(
            "migration_ledger",
            "; ".join(describe_migration_ledger_mismatch(migrations)),
        )
    if len(migrations) != int(plan.migration_count) or migrations[-1] != str(
        plan.migration_head
    ):
        _preflight_fail("migration_ledger", "proof migration identity drifted")
    if integrity != ("ok",):
        _preflight_fail("database_integrity", repr(integrity))
    if foreign_keys:
        _preflight_fail("foreign_keys", f"{len(foreign_keys)} violation(s)")
    if any(active.values()):
        _preflight_fail("active_operational_state", f"active counts={dict(active)}")
    if any(locked.values()):
        _preflight_fail("locked_capability_baseline", f"locked counts={dict(locked)}")
    return {
        "status": "V2_9_8B_DISPOSABLE_PUBLIC_COMPOSITION_PREFLIGHT_READY",
        "database_path": str(path),
        "database_sha256": str(plan.pre_mutation_db_sha256),
        "migration_count": len(migrations),
        "canonical_migration_count": canonical_migration_count(),
        "latest_migration": migrations[-1],
        "latest_canonical_migration": canonical_migration_names()[-1],
        "integrity": "ok",
        "foreign_key_violations": 0,
        "active_counts": active,
        "locked_capability_counts": locked,
        "git_provenance": provenance,
        "git_provenance_authorization": None,
        "fixture_composition_preflight": {
            "status": "READY",
            "labels": list(disposable_proof.fixture_composition.labels),
            "builder_count": len(disposable_proof.fixture_composition.labels),
            "fixture_composition_manifest_sha256": (
                disposable_proof.fixture_composition_manifest_sha256
            ),
            "provider_fallback_allowed": False,
            "external_requests": 0,
        },
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "database_writes": 0,
    }


def build_activation_preflight(
    *,
    db_path: str | Path | None = None,
    repository_root: str | Path | None = None,
    git_provenance_authorization: ValidatedGitProvenanceAuthorization | None = None,
) -> dict[str, Any]:
    """Run the complete read-only, zero-source activation preflight."""
    # Resolve the live module constant at call time so disposable proof patches
    # to AUTHORITATIVE_DB are observed (function defaults would freeze import-time path).
    expected = Path(AUTHORITATIVE_DB).resolve()
    path = Path(db_path).resolve() if db_path is not None else expected
    if path != expected or not path.is_file():
        _preflight_fail(
            "database_target",
            "only the configured authoritative operational database is allowed "
            f"(resolved={path} expected={expected})",
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
    additional_allowed = (
        git_provenance_authorization.allowed_untracked_paths
        if git_provenance_authorization is not None
        else ()
    )
    try:
        provenance = _capture_operational_git_provenance(
            root, additional_allowed_untracked_paths=additional_allowed
        )
    except GitProvenanceError as exc:
        _preflight_fail("git_provenance", str(exc))
    source = build_readiness_source_contract_preflight()
    from printer_v1.operator_cli.window_15m_concrete_composition import (
        ConcreteCompositionError,
        run_window_15m_concrete_composition_preflight,
        window_15m_preflight_builders,
    )

    # Final child defense: full concrete composition before campaign identity,
    # artifacts, supervision, heartbeat, source work or DB mutation (B1/B5).
    try:
        concrete_composition = run_window_15m_concrete_composition_preflight(
            repository_root=str(root),
            timeout_seconds=5.0,
        )
    except ConcreteCompositionError as exc:
        _preflight_fail("concrete_composition", str(exc))
    dependency = assert_runtime_dependency_preflight(
        repository_root=root,
        adapter_builders=window_15m_preflight_builders(timeout_seconds=5.0),
    )
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
        "concrete_composition_preflight": concrete_composition,
        "git_provenance": provenance,
        "git_provenance_authorization": (
            git_provenance_authorization.summary()
            if git_provenance_authorization is not None
            else None
        ),
        "policy": {
            "active_intake_path": ACTIVE_INTAKE_PATH,
            "token_capacity": TOKEN_CAPACITY,
            "main_window": MAIN_WINDOW,
            "main_window_seconds": MAIN_WINDOW_SECONDS,
            "locked_windows": LOCKED_WINDOWS,
            "support_5m_only": True,
            "automatic_retries": AUTOMATIC_RETRIES,
            "restart_created": False,
            "successor_created": False,
            "candidate_acquisition": {
                "state": CANDIDATE_ACQUISITION_STATE,
                "operational_prerequisite": False,
                "public_operational_modes": False,
                "cursor_authority": False,
                "deferred_modes": DEFERRED_CANDIDATE_ACQUISITION_MODES,
            },
        },
        "ceilings": {
            "campaigns": 1,
            "cycles": 1,
            "duration_seconds": TOTAL_DURATION_SECONDS,
            "pre_lifecycle_acquisition_duration_seconds": (
                PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS
            ),
            "total_wall_time_envelope_seconds": (
                PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS + TOTAL_DURATION_SECONDS
            ),
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


def build_standard_four_hour_preflight(
    *,
    db_path: str | Path | None = None,
    repository_root: str | Path | None = None,
    git_provenance_authorization: ValidatedGitProvenanceAuthorization | None = None,
) -> dict[str, Any]:
    """Read-only preflight projection for one standard 15m -> 1h -> 4h campaign."""
    base = build_activation_preflight(
        db_path=db_path,
        repository_root=repository_root,
        git_provenance_authorization=git_provenance_authorization,
    )
    policy = STANDARD_FOUR_HOUR_POLICY
    if AUTOMATIC_RETRIES != 0:
        _preflight_fail("retry_policy", "automatic retries must remain zero")
    if set(policy.locked_windows) != {"WINDOW_12H", "WINDOW_24H"}:
        _preflight_fail(
            "later_window_locks",
            "standard four-hour operation must keep WINDOW_12H and WINDOW_24H locked",
        )
    return {
        **base,
        "mode": STANDARD_FOUR_HOUR_PREFLIGHT_MODE,
        "status": "V2_9_8B_STANDARD_FOUR_HOUR_PREFLIGHT_READY",
        "standard_four_hour_policy": {
            "policy_version": policy.policy_version,
            "campaigns": 1,
            "cycles": 1,
            "starting_token_maximum": TOKEN_CAPACITY,
            "main_window": MAIN_WINDOW,
            "main_window_seconds": MAIN_WINDOW_SECONDS,
            "continuous_first_hour": True,
            "continuous_four_hour": True,
            "standard_four_hour_campaign": True,
            "locked_windows": policy.locked_windows,
            "automatic_retries": 0,
            "restart_created": False,
            "successor_created": False,
        },
        "standard_four_hour_ceilings": {
            "duration_seconds": policy.duration_seconds,
            "pre_lifecycle_acquisition_duration_seconds": (
                policy.pre_lifecycle_acquisition_duration_seconds
            ),
            "governed_requests": policy.governed_request_ceiling,
            "governed_requests_per_token": policy.governed_requests_per_token,
            "scheduler_rows": policy.scheduler_row_ceiling,
        },
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "database_writes": 0,
    }


def _artifact_paths(
    execution_id: str,
    *,
    artifact_root: str | Path | None = None,
) -> dict[str, Path]:
    base = (
        Path(artifact_root).resolve()
        if artifact_root is not None
        else ARTIFACT_ROOT.resolve()
    )
    root = (base / execution_id).resolve()
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
    operator_approved: bool,
    policy: _OperationalCampaignPolicy = _NORMAL_CAMPAIGN_POLICY,
    authorization_runtime_facts: Mapping[str, Any] | None = None,
    disposable_proof_binding: Any | None = None,
    four_token_proof_controller: Any | None = None,
    db_path: str | Path | None = None,
) -> tuple[AbstractCampaignCommand, str]:
    target_db = (
        Path(db_path).resolve() if db_path is not None else AUTHORITATIVE_DB
    )
    if authorization_runtime_facts is not None and disposable_proof_binding is not None:
        raise OperationalMemoryFactoryError(
            "DISPOSABLE_PROOF_EXTERNAL_AUTHORIZATION_CONFLICT"
        )
    if (
        disposable_proof_binding is None
        and db_path is not None
        and target_db != AUTHORITATIVE_DB
    ):
        raise OperationalMemoryFactoryError(
            "NON_PROOF_DATABASE_TARGET_OVERRIDE_FORBIDDEN"
        )

    four_token_policy = None
    four_token_multi_cycle_capacity = None
    if four_token_proof_controller is not None:
        if not policy.standard_four_hour_campaign:
            raise OperationalMemoryFactoryError(
                "FOUR_TOKEN_PROOF_CONTROLLER_REQUIRES_STANDARD_FOUR_HOUR_POLICY"
            )
        from printer_v1.operator_cli.four_token_proof_integration import (
            build_four_token_proof_policy,
        )
        from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
            multi_cycle_configuration_contract,
        )

        four_token_policy = build_four_token_proof_policy()
        four_token_multi_cycle_capacity = multi_cycle_configuration_contract(
            four_token_policy,
            intake_started_at=datetime.fromisoformat(
                now.replace("Z", "+00:00")
            ),
        )

    campaign_id = f"{execution_id}-campaign"
    configuration_id = f"{execution_id}-configuration"
    run_id = f"{execution_id}-campaign-run"
    cycle_id = f"{execution_id}-cycle"
    report_id = f"{execution_id}-report"
    report_identity = report_path_identity(paths["reports"])
    ceilings = CampaignCeilings(
        campaign_count=1,
        cycle_count=(
            four_token_policy.total_cycle_admission_ceiling
            if four_token_policy is not None
            else 1
        ),
        duration_seconds=policy.duration_seconds,
        source_calls=ADMISSION_OPERATION_CEILING,
        scheduler_work=policy.scheduler_row_ceiling,
        storage_bytes=STORAGE_BYTE_CEILING,
        failures=FAILURE_CEILING,
    )
    target_identity = f"sha256:{preflight['database_sha256']}"
    configuration = {
        "execution_id": execution_id,
        "campaign_id": campaign_id,
        "configuration_id": configuration_id,
        "run_id": run_id,
        "policy_version": policy.policy_version,
        "db_target_identity": target_identity,
        "operator_approved": operator_approved is True,
        "token_capacity": TOKEN_CAPACITY,
        "ceilings": asdict(ceilings),
        # Explicit bounded pre-lifecycle acquisition horizon (design §1). The
        # lifecycle deadline still starts from the real post-acquisition time
        # and keeps its own envelope; this value only makes the longer possible
        # total wall time visible in the immutable campaign configuration.
        "pre_lifecycle_acquisition_duration_seconds": (
            policy.pre_lifecycle_acquisition_duration_seconds
        ),
        "total_wall_time_envelope_seconds": (
            policy.pre_lifecycle_acquisition_duration_seconds
            + policy.duration_seconds
        ),
        "main_window": MAIN_WINDOW,
        "main_window_seconds": MAIN_WINDOW_SECONDS,
        "continuous_first_hour": bool(policy.selective_1h_continuation),
        "continuous_four_hour": bool(policy.continuous_four_hour),
        "standard_four_hour_campaign": bool(policy.standard_four_hour_campaign),
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
                TOKEN_CAPACITY * 2
                if policy.selective_1h_continuation
                else TOKEN_CAPACITY
            ),
        },
    }
    if four_token_multi_cycle_capacity is not None:
        configuration["multi_cycle_capacity"] = four_token_multi_cycle_capacity
    if disposable_proof_binding is None:
        authorization_marker = build_authorization_marker_payload(
            marker_id=f"{execution_id}-authorization-marker",
            execution_id=execution_id,
            campaign_id=campaign_id,
            configuration_id=configuration_id,
            run_id=run_id,
            policy_version=policy.policy_version,
            db_target_identity=target_identity,
            launch_git_provenance=preflight["git_provenance"],
            operator_approved=operator_approved,
        )
        configuration["authorization_marker"] = authorization_marker
        configuration["authorization_marker_sha256"] = campaign_evidence_sha256(
            authorization_marker
        )
    if disposable_proof_binding is not None:
        from printer_v1.operator_cli.operational_database_target_binding import (
            build_disposable_public_composition_proof_expectation,
            validate_disposable_public_composition_proof_invocation,
        )

        if target_db == Path(CANONICAL_PERSISTENT_DB).resolve():
            raise OperationalMemoryFactoryError(
                "DISPOSABLE_PROOF_CANONICAL_DB_FORBIDDEN"
            )
        expectation = build_disposable_public_composition_proof_expectation(
            disposable_proof_binding
        )
        reason = validate_disposable_public_composition_proof_invocation(
            disposable_proof_binding,
            expectation=expectation,
            actual_db_path=target_db,
            canonical_authoritative_db_path=CANONICAL_PERSISTENT_DB,
            execution_id=execution_id,
            campaign_id=campaign_id,
            campaign_run_id=run_id,
            cycle_id=cycle_id,
            configuration_id=configuration_id,
            durable_db_target_identity=target_identity,
            fixture_composition_manifest_sha256=str(
                disposable_proof_binding.fixture_composition_manifest_sha256
            ),
        )
        if reason is not None:
            raise OperationalMemoryFactoryError(reason)
        if str(preflight.get("database_sha256") or "") != str(
            disposable_proof_binding.pre_mutation_db_sha256
        ):
            raise OperationalMemoryFactoryError(
                "DISPOSABLE_PROOF_DB_SHA256_MISMATCH"
            )
        configuration["cycle_id"] = cycle_id
        configuration["operational_database_target_expectation"] = expectation
    elif authorization_runtime_facts is not None:
        from printer_v1.operator_cli.operational_database_target_binding import (
            AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF,
            PRODUCTION_AUTHORITATIVE,
            build_durable_operational_database_target_expectation,
        )

        target_kind = (
            PRODUCTION_AUTHORITATIVE
            if target_db == Path(CANONICAL_PERSISTENT_DB).resolve()
            else AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF
        )
        configuration["cycle_id"] = cycle_id
        configuration["operational_database_target_expectation"] = (
            build_durable_operational_database_target_expectation(
                target_kind=target_kind,
                resolved_db_path=str(
                    authorization_runtime_facts["authorized_db_path"]
                ),
                durable_db_target_identity=target_identity,
                execution_id=execution_id,
                campaign_id=campaign_id,
                campaign_run_id=run_id,
                cycle_id=cycle_id,
                configuration_id=configuration_id,
                **dict(authorization_runtime_facts),
            )
        )
    if disposable_proof_binding is not None:
        expected_database_path = disposable_proof_binding.resolved_db_path
        expected_database_sha256 = disposable_proof_binding.pre_mutation_db_sha256
        expected_migration_count = disposable_proof_binding.migration_count
        expected_migration_head = disposable_proof_binding.migration_head
    elif authorization_runtime_facts is not None:
        expected_database_path = authorization_runtime_facts["authorized_db_path"]
        expected_database_sha256 = authorization_runtime_facts[
            "authorized_pre_mutation_sha256"
        ]
        expected_migration_count = authorization_runtime_facts["migration_count"]
        expected_migration_head = authorization_runtime_facts["migration_head"]
    else:
        expected_database_path = preflight["database_path"]
        expected_database_sha256 = preflight["database_sha256"]
        expected_migration_count = preflight["migration_count"]
        expected_migration_head = preflight["latest_migration"]
    created = create_operational_campaign_graph(
        target_db,
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        run_id=run_id,
        cycle_id=cycle_id,
        configuration=configuration,
        launch_provenance=preflight["git_provenance"],
        db_target_identity=target_identity,
        policy_version=policy.policy_version,
        expected_database_path=expected_database_path,
        expected_database_sha256=str(expected_database_sha256),
        expected_migration_count=int(expected_migration_count),
        expected_migration_head=str(expected_migration_head),
        run_ordinal=1,
        now=now,
    )
    _ACTION_RUN_CONTEXT["run_id"] = run_id
    _ACTION_RUN_CONTEXT["campaign_id"] = campaign_id
    _ACTION_RUN_CONTEXT["cycle_id"] = cycle_id
    _ACTION_RUN_CONTEXT["execution_id"] = execution_id
    return (
        AbstractCampaignCommand(
            mode=CAMPAIGN_MODE,
            db_path=target_db,
            db_target_identity=target_identity,
            campaign_id=campaign_id,
            configuration_id=configuration_id,
            configuration_hash=str(created["configuration_hash"]),
            policy_version=policy.policy_version,
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


def _build_pre_lifecycle_temporal_refresh_owner(
    *,
    command: AbstractCampaignCommand,
    cycle_id: str,
    cycle_cutoff: str,
    evaluated_at: str,
    execution_id: str,
    acquisition_seconds: int,
    lifecycle_duration_seconds: int,
    heartbeat: "_CampaignHeartbeat | None",
    cancellation_probe: Callable[[], str | None],
    stage_evidence_sink: Callable[[Mapping[str, Any]], None] | None = None,
    transport_identity_observer: Callable[[Any], None] | None = None,
    local_validation_identity_observer: Callable[[Any], None] | None = None,
    geckoterminal_nomination_transport: Any | None = None,
    protocol_account_batch_transport: Any | None = None,
) -> "PreLifecycleTemporalRefreshOwner":
    """Compose the ordinary WINDOW_15M pre-lifecycle temporal refresh owner.

    Everything it needs already exists and is reused verbatim:

    * the exact authorized campaign/run/cycle/supervision identities;
    * the canonical Source Governor and Central Scheduler owner ports;
    * the existing heartbeat failure event as the prompt abort boundary, and
      the existing cancellation probe as the supervision/safe-stop probe;
    * the existing approved discovery/source owners as the refresh stage;
    * the one canonical per-cycle discovery batch derivation.

    No second discovery engine, provider, adapter, gate or selector is created,
    and no retry/restart/resume/successor path is introduced.
    """
    from printer_v1.discovery.pre_lifecycle_refresh_composition import (
        build_cycle_discovery_batch_resolver,
        build_pre_lifecycle_refresh_stage,
    )
    from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
        acquisition_deadline_at,
    )
    from printer_v1.operator_cli.authoritative_live_operational_campaign import (
        operational_discovery_batch_identity_inputs,
    )
    from printer_v1.operator_cli.pre_lifecycle_temporal_refresh_owner import (
        PreLifecycleTemporalRefreshOwner,
        bounded_interruptible_wait,
    )

    contract_versions, git_identity = (
        operational_discovery_batch_identity_inputs()
    )
    failure_event = heartbeat.failure_event if heartbeat is not None else None

    def supervision_probe() -> dict[str, Any]:
        """Map the existing heartbeat/cancellation boundary onto the contract."""
        heartbeat_failed = bool(
            failure_event is not None and failure_event.is_set()
        )
        cause = cancellation_probe()
        return {
            # A failed lease is a supervision failure, not a cancellation.
            "supervision_active": not heartbeat_failed,
            "cancellation_requested": bool(cause) and not heartbeat_failed,
            "observed_cause": cause,
        }

    def waiter(seconds: float) -> bool:
        # One bounded interruptible suspension of this already-authorized
        # child. The heartbeat's own failure event aborts it immediately; the
        # cooperative cancellation flag is re-read at wake, bounded by the
        # canonical 600s refresh interval. No polling loop is introduced.
        return bounded_interruptible_wait(seconds, failure_event)

    return PreLifecycleTemporalRefreshOwner(
        command.db_path,
        campaign_id=command.campaign_id,
        run_id=command.run_id,
        cycle_id=cycle_id,
        supervision_id=command.supervision_id,
        source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, True),
        central_scheduler=OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
        acquisition_deadline_at=acquisition_deadline_at(
            evaluated_at, acquisition_duration_seconds=int(acquisition_seconds)
        ),
        # Refresh discovery work is bounded by the campaign's own lifecycle
        # envelope, measured from the real post-acquisition instant.
        work_deadline_at=_iso(
            datetime.fromisoformat(evaluated_at.replace("Z", "+00:00"))
            + timedelta(
                seconds=int(acquisition_seconds) + int(lifecycle_duration_seconds)
            )
        ),
        refresh_stage=build_pre_lifecycle_refresh_stage(
            request_key_prefix=execution_id,
            geckoterminal_nomination_transport=(
                geckoterminal_nomination_transport
            ),
            protocol_account_batch_transport=protocol_account_batch_transport,
            stage_evidence_sink=stage_evidence_sink,
            transport_identity_observer=transport_identity_observer,
            local_validation_identity_observer=(
                local_validation_identity_observer
            ),
        ),
        discovery_batch_resolver=build_cycle_discovery_batch_resolver(
            campaign_id=command.campaign_id,
            configuration_id=command.configuration_id,
            run_id=command.run_id,
            cycle_id=cycle_id,
            cycle_cutoff=cycle_cutoff,
            policy_version=command.policy_version,
            provider_contract_versions=contract_versions,
            git_provenance_identity=git_identity,
            campaign_selection_seed=execution_id,
        ),
        supervision_probe=supervision_probe,
        waiter=waiter,
        abort_event=failure_event,
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


def build_current_run_clean_memory_outcome(
    db_path: Path | str,
    *,
    campaign_id: str | None,
    run_id: str | None,
    factory_run_id: str | None = None,
) -> dict[str, Any]:
    """Independent current-run clean-memory outcome (E3).

    Lifecycle CAMPAIGN_PASS remains separate. This reports exact current-run
    WINDOW_15M quality, episodes and fingerprint linkage only.
    """
    path = Path(db_path).resolve()
    outcome: dict[str, Any] = {
        "expected_window_ids": [],
        "e2q_clean_candidate_window_ids": [],
        "dirty_or_audit_only_window_ids": [],
        "blocked_window_ids": [],
        "windows": [],
        "episode_ids": [],
        "fingerprint_ids": [],
        "unrelated_promotion_count": 0,
        "blocker_categories": [],
        "clean_memory_outcome_pass": False,
    }
    if not path.is_file():
        outcome["blocker_categories"].append("DATABASE_MISSING")
        return outcome
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        window_ids: list[int] = []
        # Prefer campaign-registered windows for this run.
        if run_id and _table_exists_ro(connection, "printer_memory_factory_campaign_windows"):
            rows = connection.execute(
                """SELECT memory_window_row_id
                   FROM printer_memory_factory_campaign_windows
                   WHERE run_id=? AND memory_window_row_id IS NOT NULL
                   ORDER BY window_id""",
                (run_id,),
            ).fetchall()
            window_ids = [
                int(row["memory_window_row_id"])
                for row in rows
                if row["memory_window_row_id"] is not None
            ]
        if not window_ids and factory_run_id:
            rows = connection.execute(
                """SELECT memory_window_id FROM printer_memory_factory_run_steps
                   WHERE run_id=? AND step_kind='WINDOW_CLOSE'
                     AND step_status='SUCCEEDED' AND memory_window_id IS NOT NULL
                   ORDER BY id""",
                (factory_run_id,),
            ).fetchall()
            window_ids = [int(row["memory_window_id"]) for row in rows]
        outcome["expected_window_ids"] = window_ids
        if not window_ids:
            outcome["blocker_categories"].append("NO_CURRENT_RUN_WINDOWS")
            return outcome

        placeholders = ",".join("?" for _ in window_ids)
        windows = connection.execute(
            f"""SELECT id, window_kind, window_status, memory_status,
                       memory_quality_label, data_quality_label, do_not_train,
                       token_id, pair_id, supporting_context_json
                FROM printer_memory_windows
                WHERE id IN ({placeholders})
                ORDER BY id""",
            window_ids,
        ).fetchall()
        clean_candidate_ids: list[int] = []
        dirty_ids: list[int] = []
        blocked_ids: list[int] = []
        episode_ids: list[int] = []
        fingerprint_ids: list[int] = []
        window_details: list[dict[str, Any]] = []
        for win in windows:
            wid = int(win["id"])
            detail = {
                "window_id": wid,
                "window_status": win["window_status"],
                "memory_status": win["memory_status"],
                "memory_quality_label": win["memory_quality_label"],
                "data_quality_label": win["data_quality_label"],
                "do_not_train": int(win["do_not_train"] or 0),
                "token_id": win["token_id"],
                "pair_id": win["pair_id"],
                "episode_id": None,
                "fingerprint_id": None,
            }
            is_closed = str(win["window_status"] or "") in {
                "WINDOW_CLOSED",
                "CLOSED",
            }
            is_partial = str(win["memory_status"] or "") == "PARTIAL_MEMORY"
            is_clean_data = str(win["data_quality_label"] or "") == "CLEAN_DATA"
            no_dnt = int(win["do_not_train"] or 0) == 0
            if is_closed and is_partial and is_clean_data and no_dnt:
                clean_candidate_ids.append(wid)
            elif str(win["memory_status"] or "") in {
                "DIRTY_MEMORY",
                "AUDIT_ONLY",
                "AUDIT_ONLY_MEMORY",
            }:
                dirty_ids.append(wid)
            else:
                blocked_ids.append(wid)

            episode = connection.execute(
                """SELECT id FROM printer_episodes
                   WHERE memory_window_id=? AND memory_status='CLEAN_MEMORY'
                   ORDER BY id LIMIT 1""",
                (wid,),
            ).fetchone()
            if episode is not None:
                eid = int(episode["id"])
                detail["episode_id"] = eid
                episode_ids.append(eid)
                fp = connection.execute(
                    """SELECT id FROM printer_memory_fingerprints
                       WHERE episode_id=? ORDER BY id LIMIT 1""",
                    (eid,),
                ).fetchone()
                if fp is not None:
                    fid = int(fp["id"])
                    detail["fingerprint_id"] = fid
                    fingerprint_ids.append(fid)
            window_details.append(detail)

        outcome["windows"] = window_details
        outcome["e2q_clean_candidate_window_ids"] = clean_candidate_ids
        outcome["dirty_or_audit_only_window_ids"] = dirty_ids
        outcome["blocked_window_ids"] = blocked_ids
        outcome["episode_ids"] = episode_ids
        outcome["fingerprint_ids"] = fingerprint_ids

        # Unrelated promotions: CLEAN_MEMORY episodes for windows outside this run.
        if window_ids:
            unrelated = connection.execute(
                f"""SELECT COUNT(*) FROM printer_episodes
                    WHERE memory_status='CLEAN_MEMORY'
                      AND memory_window_id NOT IN ({placeholders})
                      AND created_at >= (
                          SELECT COALESCE(MIN(created_at), '9999-01-01')
                          FROM printer_memory_factory_campaign_runs
                          WHERE run_id=?
                      )""",
                (*window_ids, run_id or ""),
            ).fetchone()
            # Simpler unrelated check: any clean episode not in expected windows
            # created while this run's windows exist is reported only when we can
            # attribute; default to 0 when unprovable.
            try:
                outcome["unrelated_promotion_count"] = int(unrelated[0]) if unrelated else 0
            except Exception:
                outcome["unrelated_promotion_count"] = 0

        expected_count = len(window_ids)
        all_have_episodes = (
            expected_count > 0
            and len(episode_ids) == expected_count
            and len(set(episode_ids)) == expected_count
        )
        all_have_fingerprints = (
            all_have_episodes
            and len(fingerprint_ids) == expected_count
        )
        all_clean_candidates = (
            expected_count > 0
            and set(clean_candidate_ids) == set(window_ids)
        )
        if not all_clean_candidates:
            outcome["blocker_categories"].append("NOT_ALL_WINDOWS_E2Q_CLEAN_CANDIDATES")
        if not all_have_episodes:
            outcome["blocker_categories"].append("MISSING_CLEAN_MEMORY_EPISODES")
        if not all_have_fingerprints:
            outcome["blocker_categories"].append("MISSING_FINGERPRINT_LINKAGE")
        if int(outcome["unrelated_promotion_count"] or 0) != 0:
            outcome["blocker_categories"].append("UNRELATED_PROMOTION_DETECTED")
        outcome["clean_memory_outcome_pass"] = (
            all_clean_candidates
            and all_have_episodes
            and all_have_fingerprints
            and int(outcome["unrelated_promotion_count"] or 0) == 0
        )
        return outcome
    finally:
        connection.close()


def _table_exists_ro(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


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


_SAFE_INITIALIZED_TERMINAL_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")


def _safe_initialized_exception_terminal_cause(
    exc: BaseException,
) -> str | None:
    """Return only a bounded categorical code from owned live exceptions."""
    if not isinstance(exc, (LiveOperationalError, LiveTransportError)):
        return None
    code = getattr(exc, "code", None)
    if not isinstance(code, str):
        return None
    candidate = code.strip()
    if _SAFE_INITIALIZED_TERMINAL_CODE.fullmatch(candidate) is None:
        return None
    return candidate


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
    accounting_owner: Any | None = None,
    accounting_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Attempt every canonical terminal owner without replacing the first fault."""
    heartbeat_evidence = dict(
        (heartbeat_failure or {}).get("failure_evidence") or {}
    )
    supplied_cause = str(
        heartbeat_evidence.get("terminal_cause")
        or getattr(original_exception, "terminal_cause", "")
        or _safe_initialized_exception_terminal_cause(original_exception)
        or ""
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
    cleanup_identity_exact = all(
        str(cleanup.get(field) or "") == str(getattr(command, field))
        for field in (
            "supervision_id",
            "campaign_id",
            "configuration_id",
            "run_id",
            "owner_id",
        )
    )
    cleanup_proven = bool(
        cleanup_identity_exact
        and cleanup.get("cleanup_completed") is True
        and cleanup.get("lease_released") is True
        and type(cleanup.get("active_owned_work_after")) is int
        and int(cleanup.get("active_owned_work_after")) == 0
    )
    if not cleanup_proven:
        terminal = {
            "status": "OPERATIONAL_CAMPAIGN_TERMINAL_FAILURE",
            "execution_id": execution_id,
            "campaign_id": command.campaign_id,
            "run_id": command.run_id,
            "first_terminal_cause": cause,
            "original_exception_type": type(original_exception).__name__,
            "reconciliation": dict(reconciliation),
            "cleanup": dict(cleanup),
            "accounting_status": "NOT_FINALIZED_CLEANUP_UNPROVEN",
            "report_written": False,
            "report_block_reason": "TERMINAL_CLEANUP_UNPROVEN",
            "closure_errors": tuple(closure_errors),
            "restart_created": False,
            "successor_created": False,
            "campaign_source_calls": reporting.get("campaign_source_calls"),
            "campaign_scheduler_calls": reporting.get("campaign_scheduler_calls"),
        }
        try:
            paths["summary"].write_text(
                json.dumps(terminal, indent=2, sort_keys=True, default=str) + "\n",
                encoding="utf-8",
            )
        except BaseException as exc:
            closure_errors.append(f"summary:{type(exc).__name__}:{exc}")
        return terminal
    stage_evidence = accounting_evidence or reporting.get("six_unit_evidence")
    owner_has_evidence = bool(
        accounting_owner is not None
        and int(getattr(accounting_owner, "stage_evidence_count", 0)) > 0
    )
    evidence_available = owner_has_evidence or (
        isinstance(stage_evidence, Mapping) and bool(stage_evidence)
    )
    accounting_blocked_exception = (
        "SIX_UNIT_ACCOUNTING_BLOCKED" in str(original_exception)
        or bool(getattr(accounting_owner, "accounting_block_reason", None))
    )
    accounted_totals: Mapping[str, Any] | None = None
    durable_evidence: Mapping[str, Any] | None = None
    if evidence_available:
        try:
            if accounting_owner is not None:
                if not owner_has_evidence:
                    accounting_owner.ingest_stage_evidence(stage_evidence)
                accounting_owner.close()
                accounted_totals = accounting_owner.six_unit_totals()
                durable_evidence = accounting_owner.durable_evidence()
            else:
                from printer_v1.sources.campaign_six_unit_accounting import (
                    aggregate_campaign_six_unit_owner,
                )
                rebuilt_owner = aggregate_campaign_six_unit_owner(
                    campaign_id=command.campaign_id,
                    run_id=command.run_id,
                    cycle_id=cycle_id,
                    stage_evidences=[stage_evidence],
                )
                accounted_totals = rebuilt_owner.six_unit_totals()
                durable_evidence = rebuilt_owner.durable_evidence()
        except BaseException as exc:
            closure_errors.append(
                f"accounting:{type(exc).__name__}:{exc}"
            )
            evidence_available = False
    if (
        evidence_available
        and isinstance(durable_evidence, Mapping)
        and bool(durable_evidence.get("pre_operation_no_work"))
        and (
            factory_run_id is not None
            or int(reporting.get("campaign_source_calls") or 0) != 0
            or int(reporting.get("campaign_scheduler_calls") or 0) != 0
            or any(int(value) for value in (accounted_totals or {}).values())
            or not str(
                durable_evidence.get("pre_operation_no_work_reason") or ""
            ).strip()
        )
    ):
        closure_errors.append("accounting:PRE_OPERATION_NO_WORK_NOT_PROVEN")
        evidence_available = False

    if not evidence_available or accounting_blocked_exception:
        partial_evidence = None
        if owner_has_evidence:
            accounting_owner.close()
            partial_evidence = accounting_owner.durable_evidence()
        block_reason = "SIX_UNIT_EVIDENCE_MISSING"
        owner_block = str(
            getattr(accounting_owner, "accounting_block_reason", None) or ""
        )
        original_text = str(original_exception)
        if (
            "ACTION_LOCAL_TRANSPORT_IDENTITY_DESIGN_BLOCKED" in original_text
            or "ACTION_LOCAL_TRANSPORT_IDENTITY_DESIGN_BLOCKED" in owner_block
        ):
            block_reason = "ACTION_LOCAL_TRANSPORT_IDENTITY_DESIGN_BLOCKED"
        elif (
            "CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH" in original_text
            or "CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH" in owner_block
        ):
            block_reason = "CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH"
        terminal = {
            "status": "OPERATIONAL_CAMPAIGN_TERMINAL_FAILURE",
            "execution_id": execution_id,
            "campaign_id": command.campaign_id,
            "run_id": command.run_id,
            "first_terminal_cause": cause,
            "original_exception_type": type(original_exception).__name__,
            "reconciliation": dict(reconciliation),
            "cleanup": dict(cleanup),
            "accounting_status": "SIX_UNIT_ACCOUNTING_BLOCKED",
            "report_written": False,
            "report_block_reason": block_reason,
            "partial_six_unit_evidence": partial_evidence,
            "accounting_diagnostics": (
                accounting_owner.accounting_diagnostics()
                if hasattr(accounting_owner, "accounting_diagnostics")
                else None
            ),
            "closure_errors": tuple(closure_errors),
            "restart_created": False,
            "successor_created": False,
            "campaign_source_calls": reporting.get("campaign_source_calls"),
            "campaign_scheduler_calls": reporting.get(
                "campaign_scheduler_calls"
            ),
        }
        try:
            paths["summary"].write_text(
                json.dumps(terminal, indent=2, sort_keys=True, default=str) + "\n",
                encoding="utf-8",
            )
        except BaseException as exc:
            closure_errors.append(f"summary:{type(exc).__name__}:{exc}")
        return terminal

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
        six_unit_totals=accounted_totals,
        six_unit_evidence=durable_evidence,
        require_six_unit_evidence=True,
        elapsed_seconds=reporting.get("elapsed_seconds"),
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
                require_six_unit_evidence=True,
            ),
        )
    except BaseException as exc:
        closure_errors.append(f"report:{type(exc).__name__}:{exc}")
    terminal = {
        "status": "OPERATIONAL_CAMPAIGN_TERMINAL_FAILURE",
        "execution_id": execution_id,
        "campaign_id": command.campaign_id,
        "run_id": command.run_id,
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


def _finalize_operational_six_unit_accounting(
    accounting_owner: Any,
    stage_evidences: Sequence[Mapping[str, Any] | None] | None,
    *,
    action_local_source_operations: int | None = None,
    action_local_transport_identities: Sequence[Mapping[str, Any]] | None = None,
) -> Any:
    """Coordinator boundary: complete stage ingestion and reconciliation gate.

    When stages already sealed into the owner via the campaign sink during
    operational work, empty/null post-return lifecycle evidence is not
    re-ingested (prevents double ingestion). Additional sealed stages that are
    not yet present may still be ingested once. Action-local transport
    identities must be measured independently at record_transport time (not
    mirrored from sealed-stage handoff) and never manufacture missing stage
    evidence. Count-only action-local surfaces fail closed with
    ``ACTION_LOCAL_TRANSPORT_IDENTITY_DESIGN_BLOCKED``.
    """
    from printer_v1.sources.campaign_six_unit_accounting import (
        reconcile_owner_to_action_local,
    )

    owner_has_stages = int(getattr(accounting_owner, "stage_evidence_count", 0) or 0) > 0
    if owner_has_stages:
        if (
            stage_evidences is not None
            and isinstance(stage_evidences, Sequence)
            and not isinstance(stage_evidences, (str, bytes))
        ):
            already = set(getattr(accounting_owner, "ingested_stage_ids", ()) or ())
            for evidence in stage_evidences:
                if not isinstance(evidence, Mapping) or not evidence:
                    continue
                stage_id = evidence.get("stage_id")
                if stage_id is not None and str(stage_id) in already:
                    continue
                # Unsealed legacy post-return aggregates must not double-count
                # transports already ingested through the operational sink.
                if stage_id is None:
                    continue
                try:
                    accounting_owner.ingest_stage_evidence(evidence)
                except BaseException as exc:
                    raise OperationalMemoryFactoryError(
                        f"SIX_UNIT_ACCOUNTING_BLOCKED:{type(exc).__name__}:{exc}"
                    ) from exc
    else:
        if (
            stage_evidences is None
            or not isinstance(stage_evidences, Sequence)
            or isinstance(stage_evidences, (str, bytes))
            or len(stage_evidences) == 0
        ):
            raise OperationalMemoryFactoryError("SIX_UNIT_ACCOUNTING_BLOCKED")
        for evidence in stage_evidences:
            if not isinstance(evidence, Mapping) or not evidence:
                raise OperationalMemoryFactoryError("SIX_UNIT_ACCOUNTING_BLOCKED")
            try:
                accounting_owner.ingest_stage_evidence(evidence)
            except BaseException as exc:
                raise OperationalMemoryFactoryError(
                    f"SIX_UNIT_ACCOUNTING_BLOCKED:{type(exc).__name__}:{exc}"
                ) from exc

    accounting_owner.close()
    reconciliation = reconcile_owner_to_action_local(
        accounting_owner,
        action_local_source_operations=action_local_source_operations,
        action_local_transport_identities=action_local_transport_identities,
    )
    if not reconciliation["equal"]:
        reason = str(
            reconciliation.get("mismatch_reason")
            or "CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH"
        )
        if hasattr(accounting_owner, "block"):
            accounting_owner.block(reason)
        raise OperationalMemoryFactoryError(
            f"SIX_UNIT_ACCOUNTING_BLOCKED:{reason}"
        )
    return accounting_owner


from printer_v1.operator_cli.campaign_full_run_accounting import (  # noqa: E402
    VERDICT_BLOCKED_UNSAFE as FULL_RUN_VERDICT_BLOCKED_UNSAFE,
    VERDICT_HONEST_BLOCKED as FULL_RUN_VERDICT_HONEST_BLOCKED,
    VERDICT_PASS as FULL_RUN_VERDICT_PASS,
)


def _apply_full_run_campaign_acceptance(
    *,
    db_path: Any,
    campaign_id: str,
    campaign_run_id: str,
    cycle_id: str,
    configuration_id: str,
    factory_run_id: str | None,
    execution_id: str,
    supervision_id: Any,
    launch_git_provenance: Mapping[str, Any],
    db_target_identity: str,
    lifecycle_started: bool,
    lifecycle_operation_records: Sequence[Mapping[str, Any]],
    forbidden_deltas: Mapping[str, int],
    accounting_owner: Any | None = None,
    action_local_ledger: Any | None = None,
    runtime_terminal_status: str | None = None,
    runtime_first_terminal_cause: str | None = None,
    cleanup_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Register ownership, reconcile, and gate Campaign PASS for the full run.

    Campaign acceptance is evaluated only after unified terminal cleanup has
    produced the durable authorization/runtime/lease/active-work facts, which are
    threaded in (never assumed). A pre-lifecycle terminal is ``HONEST_BLOCKED``
    with no ownership work. Any fault registering ownership or reconciling
    accounting is ``BLOCKED_UNSAFE`` — never a silent PASS.

    Authorization/invocation counts come only from the immutable configuration
    marker and supervision acquisition row. ``cleanup_result`` must be the real
    ``cleanup_campaign_supervision()`` result; omission or malformed truth blocks.
    """
    from printer_v1.operator_cli.campaign_full_run_accounting import (
        OperationalLifecycleOwnershipContext,
        finalize_full_run_ownership_and_report,
    )

    if not lifecycle_started or not str(factory_run_id or "").strip():
        return {
            "verdict": FULL_RUN_VERDICT_HONEST_BLOCKED,
            "campaign_acceptance": {"pass": False},
            "lifecycle_started": bool(lifecycle_started),
            "reason": "PRE_LIFECYCLE_NO_OWNED_LIFECYCLE",
        }
    if accounting_owner is None or action_local_ledger is None:
        return {
            "verdict": FULL_RUN_VERDICT_BLOCKED_UNSAFE,
            "campaign_acceptance": {"pass": False},
            "lifecycle_started": True,
            "reason": "FULL_RUN_OWNER_CONTINUITY_MISSING",
        }
    try:
        context = OperationalLifecycleOwnershipContext(
            campaign_id=campaign_id,
            campaign_run_id=campaign_run_id,
            cycle_id=cycle_id,
            configuration_id=configuration_id,
            factory_run_id=str(factory_run_id),
        )
        connection = sqlite3.connect(str(db_path))
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            if runtime_terminal_status is None:
                row = connection.execute(
                    "SELECT run_status FROM printer_memory_factory_runs WHERE run_id=?",
                    (str(factory_run_id),),
                ).fetchone()
                raw_status = str(row[0]) if row and row[0] is not None else ""
                runtime_terminal_status = (
                    "COMPLETED" if raw_status == "COMPLETED"
                    else (raw_status or "UNKNOWN")
                )
            outcome = finalize_full_run_ownership_and_report(
                connection,
                context=context,
                owner=accounting_owner,
                action_local=action_local_ledger,
                execution_id=execution_id,
                supervision_id=supervision_id,
                launch_git_provenance=dict(launch_git_provenance or {}),
                db_target_identity=db_target_identity,
                runtime_terminal_status=str(runtime_terminal_status),
                runtime_first_terminal_cause=runtime_first_terminal_cause,
                cleanup_result=cleanup_result,
                forbidden_capability_deltas=dict(forbidden_deltas or {}),
            )
        finally:
            connection.close()
        return outcome
    except Exception as exc:  # fail closed: an ownership/accounting fault blocks
        return {
            "verdict": FULL_RUN_VERDICT_BLOCKED_UNSAFE,
            "campaign_acceptance": {"pass": False},
            "lifecycle_started": True,
            "reason": f"FULL_RUN_FINALIZATION_FAULT:{type(exc).__name__}:{exc}",
        }


def _finalize_returned_pre_lifecycle_result(
    *,
    result: Any,
    lifecycle: Mapping[str, Any],
    command: AbstractCampaignCommand,
    cycle_id: str,
    execution_id: str,
    paths: Mapping[str, Path],
    launch_git_provenance: Mapping[str, Any],
    campaign_units: Any,
    action_local_transport_identities: Sequence[Mapping[str, Any]],
    stage_observer_state: Mapping[str, Any],
) -> dict[str, Any]:
    """Finalize a returned pre-lifecycle terminal without replacing its cause.

    The decision to account is made from truthful stage ownership before any
    evidence sequence is constructed.  No-stage terminals never call the
    accounting owner.  Claimed stages remain strictly fail-closed when real
    evidence is absent or malformed.
    """
    activation = result.activation
    lifecycle_map = dict(lifecycle or {})
    first_cause = str(
        activation.first_terminal_cause
        or lifecycle_map.get("first_terminal_cause")
        or lifecycle_map.get("stop_reason")
        or "PRE_LIFECYCLE_GOVERNED_SAFE_STOP"
    )
    cancellation_reason = (
        activation.cancellation_reason
        or lifecycle_map.get("cancellation_reason")
    )
    fault_details = dict(
        activation.fault_details
        or lifecycle_map.get("fault_details")
        or {}
    )
    secondary: list[dict[str, Any]] = list(
        fault_details.get("propagation_failures") or []
    )
    cleanup: Mapping[str, Any] = {"cleanup_completed": False}
    reconciliation: Mapping[str, Any] = {
        "reconciled": False,
        "restart_created": False,
        "successor_created": False,
    }
    try:
        cleanup = cleanup_campaign_supervision(
            command.db_path,
            supervision_id=command.supervision_id,
            campaign_id=command.campaign_id,
            configuration_id=command.configuration_id,
            run_id=command.run_id,
            owner_id=command.owner_id,
            terminal_status="FAILED",
            first_terminal_cause=first_cause,
        )
    except BaseException as exc:
        secondary.append(
            {
                "stage": "PRE_LIFECYCLE_CLEANUP",
                "exception_class": type(exc).__name__,
                "message": str(exc),
            }
        )
    try:
        reconciliation = reconcile_campaign_terminal(
            command.db_path,
            campaign_id=command.campaign_id,
            run_id=command.run_id,
            cycle_id=cycle_id,
            terminal_cause=first_cause,
            run_status=str(lifecycle_map.get("run_status") or "NOT_STARTED"),
            factory_run_id=None,
            lifecycle_started=False,
            now=_iso(),
        )
    except BaseException as exc:
        secondary.append(
            {
                "stage": "PRE_LIFECYCLE_RECONCILIATION",
                "exception_class": type(exc).__name__,
                "message": str(exc),
            }
        )

    raw_stage_evidences = lifecycle_map.get("six_unit_stage_evidences")
    real_stage_evidences: list[Mapping[str, Any]] = []
    malformed_collection = False
    if raw_stage_evidences is not None:
        if isinstance(raw_stage_evidences, Sequence) and not isinstance(
            raw_stage_evidences, (str, bytes)
        ):
            for evidence in raw_stage_evidences:
                if isinstance(evidence, Mapping) and bool(evidence):
                    real_stage_evidences.append(evidence)
                else:
                    malformed_collection = True
        else:
            malformed_collection = True

    accountable_stage_started = bool(
        getattr(activation, "accountable_stage_started", False)
        or stage_observer_state.get("invoked")
        or int(getattr(campaign_units, "stage_evidence_count", 0) or 0) > 0
        or action_local_transport_identities
        or raw_stage_evidences is not None
        or real_stage_evidences
    )
    accounting_required = accountable_stage_started
    accounting_status = "NOT_REQUIRED_NO_ACCOUNTABLE_STAGE"
    accounting_error: str | None = None
    if accounting_required:
        try:
            if malformed_collection:
                raise OperationalMemoryFactoryError(
                    "SIX_UNIT_ACCOUNTING_BLOCKED:MALFORMED_STAGE_EVIDENCE_COLLECTION"
                )
            _finalize_operational_six_unit_accounting(
                campaign_units,
                real_stage_evidences,
                action_local_transport_identities=list(
                    action_local_transport_identities
                ),
            )
            accounting_status = "SIX_UNIT_ACCOUNTING_COMPLETE"
        except BaseException as exc:
            accounting_status = "SIX_UNIT_ACCOUNTING_BLOCKED"
            accounting_error = f"{type(exc).__name__}:{exc}"
            if hasattr(campaign_units, "block"):
                try:
                    campaign_units.block(str(exc))
                except BaseException:
                    pass
            secondary.append(
                {
                    "stage": "PRE_LIFECYCLE_SIX_UNIT_FINALIZATION",
                    "exception_class": type(exc).__name__,
                    "message": str(exc),
                }
            )

    reporting: Mapping[str, Any] = {}
    try:
        reporting = assemble_campaign_terminal_reporting(
            command.db_path,
            run_id=command.run_id,
            cycle_id=cycle_id,
            terminal_cause=first_cause,
            lifecycle=lifecycle_map,
            required_token_capacity=TOKEN_CAPACITY,
        )
    except BaseException as exc:
        secondary.append(
            {
                "stage": "PRE_LIFECYCLE_REPORT_ASSEMBLY",
                "exception_class": type(exc).__name__,
                "message": str(exc),
            }
        )

    report: Mapping[str, Any] | None = None
    if accounting_status == "SIX_UNIT_ACCOUNTING_COMPLETE":
        try:
            totals = campaign_units.six_unit_totals()
            evidence = campaign_units.durable_evidence()
            payload = build_campaign_terminal_report(
                campaign_id=command.campaign_id,
                configuration_id=command.configuration_id,
                run_id=command.run_id,
                cycle_id=cycle_id,
                report_id=command.report_id,
                factory_run_id=None,
                execution_id=execution_id,
                terminal_status=str(activation.terminal_status),
                terminal_cause=first_cause,
                run_status=str(lifecycle_map.get("run_status") or "NOT_STARTED"),
                lifecycle_started=False,
                reconciliation=reconciliation,
                forbidden_deltas=dict(lifecycle_map.get("forbidden_deltas") or {}),
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
                fault_details=fault_details or None,
                pre_lifecycle_admission=reporting.get("pre_lifecycle_admission"),
                six_unit_totals=totals,
                six_unit_evidence=evidence,
                require_six_unit_evidence=True,
                elapsed_seconds=reporting.get("elapsed_seconds"),
            )
            report = write_campaign_terminal_report(
                command.db_path,
                paths["reports"],
                report_id=command.report_id,
                campaign_id=command.campaign_id,
                configuration_id=command.configuration_id,
                report=payload,
                require_six_unit_evidence=True,
            )
        except BaseException as exc:
            secondary.append(
                {
                    "stage": "PRE_LIFECYCLE_REPORT_WRITE",
                    "exception_class": type(exc).__name__,
                    "message": str(exc),
                }
            )

    if secondary:
        fault_details["propagation_failures"] = secondary
    terminal = {
        "status": "OPERATIONAL_CAMPAIGN_PRE_LIFECYCLE_TERMINAL",
        "execution_id": execution_id,
        "campaign_id": command.campaign_id,
        "run_id": command.run_id,
        "run_status": str(lifecycle_map.get("run_status") or "NOT_STARTED"),
        "activation_terminal_status": str(activation.terminal_status),
        "first_terminal_cause": first_cause,
        "cancellation_reason": cancellation_reason,
        "fault_details": fault_details,
        "lifecycle_started": False,
        "accountable_stage_started": accountable_stage_started,
        "stage_observer_state": dict(stage_observer_state),
        "stage_evidence_count": int(
            getattr(campaign_units, "stage_evidence_count", 0) or 0
        ),
        "stage_evidences": tuple(real_stage_evidences),
        "accounting_required": accounting_required,
        "accounting_status": accounting_status,
        "accounting_error": accounting_error,
        "cleanup": dict(cleanup),
        "reconciliation": dict(reconciliation),
        "report": None if report is None else dict(report),
        "campaign_acceptance_verdict": FULL_RUN_VERDICT_HONEST_BLOCKED,
        "campaign_pass": False,
        "failure_evidence_required": True,
        "restart_created": bool(getattr(activation, "restart_created", False)),
        "successor_created": bool(getattr(activation, "successor_created", False)),
        "campaign_source_calls": reporting.get("campaign_source_calls"),
        "campaign_scheduler_calls": reporting.get("campaign_scheduler_calls"),
        "required_token_capacity": reporting.get("required_token_capacity")
        or TOKEN_CAPACITY,
        "blocked_supply_reason": reporting.get("blocked_supply_reason"),
    }
    try:
        paths["summary"].write_text(
            json.dumps(terminal, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
    except BaseException as exc:
        terminal["fault_details"].setdefault("propagation_failures", []).append(
            {
                "stage": "PRE_LIFECYCLE_SUMMARY_WRITE",
                "exception_class": type(exc).__name__,
                "message": str(exc),
            }
        )
    return terminal


def build_pre_holder_accounting_projection(
    *,
    campaign_units: Any,
    action_local_transport_identities: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Read an immutable pre-holder view from existing accounting owners."""
    campaign_identities = [
        item.as_dict() if hasattr(item, "as_dict") else dict(item)
        for item in campaign_units.ledger.transports
    ]
    action_local_identities = [
        dict(item) for item in action_local_transport_identities
    ]
    return {
        "campaign_transport_identities": campaign_identities,
        "action_local_transport_identities": action_local_identities,
        "campaign_transport_count": len(campaign_identities),
        "action_local_transport_count": len(action_local_identities),
    }


def _holder_stage_evidence_sealer_required(
    *,
    git_provenance_authorization: ValidatedGitProvenanceAuthorization | None,
    disposable_proof: Any | None,
) -> bool:
    """True when accountable holder work must be sealed into campaign ownership."""
    return bool(
        git_provenance_authorization is not None
        or disposable_proof is not None
    )


def _merge_disposable_graduated_supply_kwargs(
    fixture_overrides: Mapping[str, Any],
) -> dict[str, Any]:
    """Overlay proof dependencies without replacing canonical operational policy."""
    overrides = dict(fixture_overrides)
    policy_collisions = sorted(
        set(overrides).intersection(OPERATIONAL_GRADUATED_SUPPLY_KWARGS)
    )
    if policy_collisions:
        raise OperationalMemoryFactoryError(
            "DISPOSABLE_PROOF_OPERATIONAL_SUPPLY_POLICY_OVERRIDE_FORBIDDEN:"
            + ",".join(policy_collisions)
        )
    merged = dict(OPERATIONAL_GRADUATED_SUPPLY_KWARGS)
    merged.update(overrides)
    return merged


def _run_operational_campaign(
    *,
    policy: _OperationalCampaignPolicy,
    operator_approved: bool,
    owner: Any | None = None,
    pump_transport: Any | None = None,
    secondary_transport: Any | None = None,
    migration_transport: Any | None = None,
    git_provenance_authorization: ValidatedGitProvenanceAuthorization | None = None,
    disposable_proof: Any | None = None,
    four_token_proof_controller: Any | None = None,
) -> dict[str, Any]:
    """Run one fixed-policy campaign through the canonical V2-9.8B owner."""
    if not operator_approved:
        raise OperationalMemoryFactoryError("explicit operator approval is required")
    if (
        four_token_proof_controller is not None
        and not policy.standard_four_hour_campaign
    ):
        raise OperationalMemoryFactoryError(
            "FOUR_TOKEN_PROOF_CONTROLLER_REQUIRES_STANDARD_FOUR_HOUR_POLICY"
        )
    if disposable_proof is not None and git_provenance_authorization is not None:
        raise OperationalMemoryFactoryError(
            "DISPOSABLE_PROOF_EXTERNAL_AUTHORIZATION_CONFLICT"
        )
    if disposable_proof is not None and any(
        value is not None
        for value in (
            pump_transport,
            secondary_transport,
            migration_transport,
        )
    ):
        raise OperationalMemoryFactoryError(
            "DISPOSABLE_PROOF_EXTERNAL_TRANSPORT_OVERRIDE_FORBIDDEN"
        )
    if disposable_proof is not None and owner is not None:
        raise OperationalMemoryFactoryError(
            "DISPOSABLE_PROOF_EXTERNAL_OWNER_OVERRIDE_FORBIDDEN"
        )
    # The manifest/marker compatibility exception applies only to the ordinary
    # WINDOW_15M run. Selective-1h never receives the C8 proof capability.
    if policy.selective_1h_continuation and disposable_proof is not None:
        raise OperationalMemoryFactoryError(
            "DISPOSABLE_PROOF_POLICY_UNSUPPORTED"
        )
    if policy.standard_four_hour_campaign:
        preflight = build_standard_four_hour_preflight(
            git_provenance_authorization=git_provenance_authorization
        )
    elif policy.selective_1h_continuation:
        preflight = build_selective_1h_preflight()
    elif disposable_proof is not None:
        preflight = build_disposable_public_composition_preflight(
            disposable_proof
        )
    else:
        preflight = build_activation_preflight(
            git_provenance_authorization=git_provenance_authorization
        )
    prepared_proof = (
        _prepare_disposable_public_composition_execution(disposable_proof)
        if disposable_proof is not None
        else None
    )
    active_db = (
        prepared_proof.db_path
        if prepared_proof is not None
        else AUTHORITATIVE_DB
    )
    active_artifact_root = (
        prepared_proof.artifact_root
        if prepared_proof is not None
        else ARTIFACT_ROOT
    )

    from printer_v1.operator_cli.operational_database_target_binding import (
        validate_authorized_database_preflight,
        validated_authorization_runtime_facts,
    )
    authorization_runtime_facts = (
        None
        if (
            disposable_proof is not None
            or (
                policy.selective_1h_continuation
                and not policy.standard_four_hour_campaign
            )
        )
        else validated_authorization_runtime_facts(
            git_provenance_authorization
        )
    )
    if authorization_runtime_facts is not None:
        validate_authorized_database_preflight(
            authorization_runtime_facts,
            actual_db_path=active_db,
            preflight=preflight,
        )
    execution_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid.uuid4().hex[:12]
    )
    # Capture pre-mutation baseline before artifacts or campaign identity so
    # exception envelopes can report exact action-local DB deltas (B7).
    from printer_v1.operator_cli.action_local_terminal_truth import (
        capture_action_local_baseline,
    )
    from printer_v1.operator_cli.action_local_mutation_recorder import (
        install_action_local_mutation_recorder,
    )

    _ACTION_RUN_CONTEXT["execution_id"] = execution_id
    _ACTION_RUN_CONTEXT["action_local_baseline"] = capture_action_local_baseline(
        active_db
    )
    _ACTION_RUN_CONTEXT["mutation_recorder"] = install_action_local_mutation_recorder()
    owner_bridge = (
        _build_disposable_public_composition_owner_bridge(
            disposable_proof=disposable_proof,
            prepared_proof=prepared_proof,
            execution_id=execution_id,
        )
        if disposable_proof is not None and prepared_proof is not None
        else None
    )
    paths = _artifact_paths(
        execution_id,
        artifact_root=active_artifact_root,
    )
    paths["root"].mkdir(parents=True, exist_ok=False)
    paths["reports"].mkdir()
    backup = operational_backup_restore_preflight(
        active_db,
        expected_source_path=active_db,
        expected_source_identity=f"sha256:{preflight['database_sha256']}",
        backup_path=paths["backup"],
        disposable_restore_root=paths["root"],
        restore_path=paths["restore"],
    )
    now = _iso()
    command, cycle_id = _create_campaign_command(
        execution_id=execution_id,
        paths=paths,
        preflight=preflight,
        backup=backup,
        now=now,
        operator_approved=operator_approved,
        policy=policy,
        authorization_runtime_facts=authorization_runtime_facts,
        disposable_proof_binding=(
            owner_bridge.proof_binding
            if owner_bridge is not None
            else None
        ),
        db_path=active_db,
    )
    from printer_v1.operator_cli.operational_database_target_binding import (
        AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF,
        PRODUCTION_AUTHORITATIVE,
        build_operational_database_target_binding,
    )
    from printer_v1.operator_cli.proof_db_schema_readiness import (
        CANONICAL_PERSISTENT_DB,
    )
    authorization = dict(authorization_runtime_facts or {})
    if owner_bridge is None:
        target_kind = (
            PRODUCTION_AUTHORITATIVE
            if Path(AUTHORITATIVE_DB).resolve()
            == Path(CANONICAL_PERSISTENT_DB).resolve()
            else AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF
        )
        operational_database_target_binding = (
            None
            if not authorization
            else build_operational_database_target_binding(
                target_kind=target_kind,
                resolved_db_path=AUTHORITATIVE_DB,
                authorized_pre_mutation_sha256=str(
                    authorization["authorized_pre_mutation_sha256"]
                ),
                migration_count=int(authorization["migration_count"]),
                migration_head=str(authorization["migration_head"]),
                authorization_id=str(authorization["authorization_id"]),
                authorization_marker_sha256=str(
                    authorization["manifest_sha256"]
                ),
                application_marker_sha256=str(
                    authorization["application_marker_sha256"]
                ),
                execution_id=execution_id,
                campaign_id=command.campaign_id,
                campaign_run_id=command.run_id,
                cycle_id=cycle_id,
                configuration_id=command.configuration_id,
                authorization_consumed_once=authorization[
                    "authorization_consumed_once"
                ],
                invocation_count=int(authorization["invocation_count"]),
                allowed_invocation_count=int(
                    authorization["allowed_invocation_count"]
                ),
                automatic_retry_allowed=authorization[
                    "automatic_retry_allowed"
                ],
                manual_rerun_allowed=authorization[
                    "manual_rerun_allowed"
                ],
                resume_allowed=authorization["resume_allowed"],
                restart_allowed=authorization["restart_allowed"],
                successor_allowed=authorization["successor_allowed"],
            )
        )
    else:
        operational_database_target_binding = (
            owner_bridge.operational_database_target_binding
        )
    heartbeat: _CampaignHeartbeat | None = None
    initialized_factory_run_id: str | None = str(uuid.uuid4())
    factory_identity_retained = False
    observed_heartbeat_failure: Mapping[str, Any] | None = None
    # The public coordinator owns accounting before the first accounted stage.
    from printer_v1.sources.campaign_six_unit_accounting import (
        CampaignActionLocalLedger,
        CampaignSixUnitOwner,
    )
    campaign_units = CampaignSixUnitOwner(
        campaign_id=command.campaign_id,
        run_id=command.run_id,
        cycle_id=cycle_id,
        started_at=now,
    )
    action_local_ledger = CampaignActionLocalLedger(
        campaign_id=command.campaign_id,
        run_id=command.run_id,
        cycle_id=cycle_id,
    )
    from printer_v1.operator_cli.campaign_full_run_accounting import (
        OperationalLifecycleOwnershipContext,
        build_lifecycle_action_local_observer,
    )
    lifecycle_ownership_context = OperationalLifecycleOwnershipContext(
        campaign_id=command.campaign_id,
        campaign_run_id=command.run_id,
        cycle_id=cycle_id,
        configuration_id=command.configuration_id,
        factory_run_id=initialized_factory_run_id,
    )
    observe_lifecycle_action = build_lifecycle_action_local_observer(
        lifecycle_ownership_context, action_local_ledger
    )
    # Action-local transport identities observed at MeasuredTransportLedger
    # record_transport time — before and separate from stage sealing. Never
    # copied from sealed-stage handoff (self-comparison) and never rebuilt
    # from source-request row counts.
    action_local_transport_identities: list[dict[str, Any]] = []
    stage_observer_state: dict[str, Any] = {
        "invoked": False,
        "completed": False,
        "returned_none": False,
        "failure": None,
    }

    # V2-9.8B full-run wiring: capture every real Scheduler-enqueue boundary the
    # factory reports, at execution time, for independent action-local lifecycle
    # evidence. Identities are minted after the factory-run id is known.
    lifecycle_operation_records: list[dict[str, Any]] = []
    scheduler_runtime_records: list[dict[str, Any]] = []

    def _observe_lifecycle_operation(record: Mapping[str, Any]) -> None:
        lifecycle_operation_records.append(dict(record))
        observe_lifecycle_action(record)

    def _observe_transport_identity(identity: Any) -> None:
        action_local_ledger.observe_transport(identity)
        if hasattr(identity, "as_dict"):
            action_local_transport_identities.append(identity.as_dict())
        elif isinstance(identity, Mapping):
            action_local_transport_identities.append(dict(identity))

    def _observe_local_validation_identity(identity: Any) -> None:
        action_local_ledger.observe_local_validation(identity)

    def _campaign_stage_evidence_sink(evidence: Mapping[str, Any]) -> None:
        # Owner side only. Action-local identities arrive via the measurement
        # observer, not by mirroring this sealed evidence block.
        campaign_units.ingest_stage_evidence(evidence)

    def _seal_holder_stage(ledger, status: str, cause: str | None):
        from printer_v1.sources.campaign_six_unit_accounting import (
            build_campaign_stage_id,
            seal_campaign_stage_evidence,
        )
        sequence = campaign_units.sealed_stage_count + 1
        stage_id = build_campaign_stage_id(
            campaign_id=command.campaign_id,
            run_id=command.run_id,
            cycle_id=cycle_id,
            stage_kind="HOLDER_SAFETY",
            stage_sequence=sequence,
        )
        zero_operation_evidence = None
        ledger_for_seal = ledger
        if not ledger.transports:
            ledger_for_seal = None
            zero_operation_evidence = {
                "evidence_kind": "CAMPAIGN_SIX_UNIT_EVIDENCE_V1",
                "phase": "PRE_OPERATION_NO_WORK",
                "source_transport_attempted": False,
                "source_governor_requests": 0,
                "scheduler_work_exists": False,
                "lifecycle_began": False,
                "no_work_reason": cause or "HOLDER_STAGE_NO_ELIGIBLE_WORK",
                "transport_operations": [],
                "local_validations": 0,
                "scheduler_work_items": 0,
                "lifecycle_reservations": 0,
            }
        evidence = seal_campaign_stage_evidence(
            stage_id=stage_id,
            stage_kind="HOLDER_SAFETY",
            stage_sequence=sequence,
            stage_terminal_status=status,
            stage_first_terminal_cause=cause,
            campaign_id=command.campaign_id,
            run_id=command.run_id,
            cycle_id=cycle_id,
            ledger=ledger_for_seal,
            evidence=zero_operation_evidence,
        )
        _campaign_stage_evidence_sink(evidence)
        return evidence

    def _observe_full_run_stage(record: Mapping[str, Any]) -> None:
        from printer_v1.sources.campaign_six_unit_accounting import (
            seal_campaign_stage_evidence,
        )
        from printer_v1.sources.measured_transport import (
            LocalValidationIdentity,
            SchedulerWorkIdentity,
        )
        stage_observer_state["invoked"] = True
        stage_id = str(record["stage_id"])
        schedulers = [
            SchedulerWorkIdentity(
                stage_id=stage_id,
                scheduler_job_id=int(item["scheduler_job_id"]),
                job_kind=str(item["job_kind"]),
                target_category=str(item["target_category"]),
                target_identity=str(item["target_identity"]),
            )
            for item in record.get("scheduler_work_identities", ())
        ]
        validations = [
            LocalValidationIdentity(
                stage_id=stage_id,
                subject_identity=str(slot["token_slot_id"]),
                validation_kind="SELECTION_HANDOFF_VALIDATED",
                validation_ordinal=index,
            )
            for index, slot in enumerate(record.get("slots", ()), start=1)
        ]
        for identity in schedulers:
            action_local_ledger.observe_scheduler_work(identity)
        for identity in validations:
            action_local_ledger.observe_local_validation(identity)
        try:
            campaign_units.ingest_stage_evidence(
                seal_campaign_stage_evidence(
                    stage_id=stage_id,
                    stage_kind="DISCOVERY_SELECTION_SCHEDULER",
                    stage_sequence=1,
                    stage_terminal_status=str(
                        record.get("stage_terminal_status") or "COMPLETED"
                    ),
                    stage_first_terminal_cause=record.get(
                        "stage_first_terminal_cause"
                    ),
                    campaign_id=command.campaign_id,
                    run_id=command.run_id,
                    cycle_id=cycle_id,
                    evidence={
                        "evidence_kind": "CAMPAIGN_SIX_UNIT_EVIDENCE_V1",
                        "transport_operations": [],
                        "local_validations": 0,
                        "scheduler_work_items": 0,
                        "lifecycle_reservations": 0,
                    },
                    scheduler_work_identities=schedulers,
                    local_validation_identities=validations,
                )
            )
        except BaseException as exc:
            stage_observer_state["failure"] = {
                "exception_class": type(exc).__name__,
                "message": str(exc),
            }
            raise
        stage_observer_state["completed"] = True
        # Observer callbacks are notification boundaries, not evidence-return
        # producers.  A normal None return must never enter stage_evidences.
        stage_observer_state["returned_none"] = True

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
        # One immutable Solana endpoint owner for preflight parity and runtime.
        # Default constructors come from the same ordinary WINDOW_15M composition
        # registry used by concrete preflight — not a parallel builder list.
        from printer_v1.operator_cli.window_15m_concrete_composition import (
            construct_ordinary_window_15m_dependency,
            production_runtime_default_constructors,
        )

        if owner_bridge is None:
            solana_rpc = resolve_solana_rpc_configuration()
            runtime_constructors = production_runtime_default_constructors(
                timeout_seconds=5.0,
                environment=os.environ,
            )
            if pump_transport is not None:
                active_pump = pump_transport
            else:
                active_pump = runtime_constructors[
                    "pump_origin_solana_rpc_transport"
                ]()
            if secondary_transport is not None:
                active_secondary = secondary_transport
            else:
                active_secondary = runtime_constructors[
                    "secondary_discovery_http_transport"
                ]()
            if migration_transport is None:
                active_migration = construct_ordinary_window_15m_dependency(
                    "direct_pump_finalized_migration_transport",
                    timeout_seconds=5.0,
                    environment=os.environ,
                )
            else:
                active_migration = migration_transport
            bridge_graduated_supply_kwargs = dict(
                OPERATIONAL_GRADUATED_SUPPLY_KWARGS
            )
            bridge_lifecycle_kwargs: dict[str, Any] = {}
        else:
            active_pump = owner_bridge.pump_transport
            active_secondary = owner_bridge.secondary_transport
            active_migration = owner_bridge.migration_transport
            bridge_graduated_supply_kwargs = (
                _merge_disposable_graduated_supply_kwargs(
                    owner_bridge.graduated_supply_kwargs
                )
            )
            bridge_lifecycle_kwargs = dict(owner_bridge.lifecycle_kwargs)
            bridge_lifecycle_kwargs["context_adapter_factories"] = dict(
                owner_bridge.lifecycle_kwargs["context_adapter_factories"]
            )

        def cancellation_probe() -> str | None:
            hb_failure = heartbeat.poll_failure() if heartbeat is not None else None
            if hb_failure is not None:
                return str(
                    hb_failure.get("suggested_terminal_cause")
                    or "LEASE_RENEWAL_UNCONFIRMED"
                )
            return _read_campaign_supervision_cancellation_reason(
                active_db,
                expected_path=active_db,
                supervision_id=command.supervision_id,
                campaign_id=command.campaign_id,
                run_id=command.run_id,
            )

        # V2-9.8B Post-DTW98 — the ordinary WINDOW_15M temporal acquisition owner.
        #
        # Exactly one owner, bound to this authorized campaign/run/cycle/
        # supervision, the same Source Governor and Central Scheduler ports the
        # campaign already uses, and the same 900s horizon recorded in the
        # immutable configuration. Without it the supply service keeps its old
        # immediate-terminal behaviour, which is precisely the DTW98 defect.
        pre_lifecycle_temporal_refresh_owner = (
            _build_pre_lifecycle_temporal_refresh_owner(
                command=command,
                cycle_id=cycle_id,
                cycle_cutoff=now,
                evaluated_at=now,
                execution_id=execution_id,
                acquisition_seconds=(
                    policy.pre_lifecycle_acquisition_duration_seconds
                ),
                lifecycle_duration_seconds=policy.duration_seconds,
                heartbeat=heartbeat,
                cancellation_probe=cancellation_probe,
                stage_evidence_sink=_campaign_stage_evidence_sink,
                transport_identity_observer=_observe_transport_identity,
                local_validation_identity_observer=(
                    _observe_local_validation_identity
                ),
                geckoterminal_nomination_transport=(
                    owner_bridge.geckoterminal_nomination_transport
                    if owner_bridge is not None
                    else None
                ),
                protocol_account_batch_transport=(
                    owner_bridge.protocol_account_batch_transport
                    if owner_bridge is not None
                    else None
                ),
            )
        )

        def retain_factory_run_id(factory_run_id: str) -> None:
            nonlocal initialized_factory_run_id, factory_identity_retained
            candidate = str(factory_run_id).strip()
            if not candidate:
                raise OperationalMemoryFactoryError(
                    "initialized factory-run identity is empty"
                )
            if initialized_factory_run_id != candidate:
                raise OperationalMemoryFactoryError(
                    "initialized factory-run identity changed"
                )
            factory_identity_retained = True

        try:
            from printer_v1.scheduler.scheduler import (
                reset_scheduler_operation_observer,
                set_scheduler_operation_observer,
            )
            scheduler_observer_token = set_scheduler_operation_observer(
                lambda record: scheduler_runtime_records.append(dict(record))
            )
            try:
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
                    **bridge_lifecycle_kwargs,
                    "factory_run_id": initialized_factory_run_id,
                    "total_duration_seconds": policy.duration_seconds,
                    "launch_provenance": preflight["git_provenance"],
                    "cancellation_probe": cancellation_probe,
                    "factory_run_initialized": retain_factory_run_id,
                    "four_token_proof_controller": four_token_proof_controller,
                    # Fixed by the public mode; normal run can never opt into 1h.
                    "selective_1h_continuation": (
                        policy.selective_1h_continuation
                    ),
                    "standard_four_hour_campaign": (
                        policy.standard_four_hour_campaign
                    ),
                    "configuration_id": command.configuration_id,
                    # Full-run ownership context + action-local operation observer
                    # propagate coordinator → owner → driver → factory.
                    "lifecycle_ownership_context": {
                        "campaign_id": command.campaign_id,
                        "campaign_run_id": command.run_id,
                        "cycle_id": cycle_id,
                        "configuration_id": command.configuration_id,
                        "factory_run_id": initialized_factory_run_id,
                        "expected_window_kind": "WINDOW_15M",
                        "expected_token_capacity": TOKEN_CAPACITY,
                    },
                    "lifecycle_operation_observer": _observe_lifecycle_operation,
                    "full_run_stage_observer": _observe_full_run_stage,
                },
                migration_transport=active_migration,
                graduated_supply_kwargs=bridge_graduated_supply_kwargs,
                fifteen_minute_only=True,
                standard_four_hour_campaign=policy.standard_four_hour_campaign,
                accounting_stage_evidence_sink=_campaign_stage_evidence_sink,
                transport_identity_observer=_observe_transport_identity,
                local_validation_identity_observer=(
                    _observe_local_validation_identity
                ),
                pre_holder_accounting_projection=lambda: (
                    build_pre_holder_accounting_projection(
                        campaign_units=campaign_units,
                        action_local_transport_identities=(
                            action_local_transport_identities
                        ),
                    )
                ),
                holder_stage_evidence_sealer=(
                    _seal_holder_stage
                    if _holder_stage_evidence_sealer_required(
                        git_provenance_authorization=git_provenance_authorization,
                        disposable_proof=disposable_proof,
                    )
                    else None
                ),
                operational_database_target_binding=(
                    operational_database_target_binding
                ),
                disposable_public_composition_proof_binding=(
                    owner_bridge.disposable_public_composition_proof_binding
                    if owner_bridge is not None
                    else None
                ),
                pre_lifecycle_acquisition_seconds=(
                    policy.pre_lifecycle_acquisition_duration_seconds
                ),
                pre_lifecycle_temporal_refresh_owner=(
                    pre_lifecycle_temporal_refresh_owner
                ),
                )
            finally:
                reset_scheduler_operation_observer(scheduler_observer_token)
        except BaseException:
            campaign_units.block(
                "OPERATIONAL_STAGE_FAILED_BEFORE_ACCOUNTING_COMPLETION"
            )
            raise
        # Heartbeat never terminalizes. Main coordinator observes failure signal.
        heartbeat_failure = heartbeat.poll_failure() if heartbeat is not None else None
        observed_heartbeat_failure = heartbeat_failure
        if heartbeat is not None:
            heartbeat.stop()
            heartbeat = None
        lifecycle = dict(result.lifecycle)
        # Never retain factory identity until lifecycle_started is proven true.
        # Campaign-run IDs in pre-lifecycle lifecycle payloads must not enter
        # retain_factory_run_id (post-rollover-2 identity-contract repair).
        if bool(result.lifecycle_started):
            returned_factory_run_id = _extract_returned_factory_run_id(
                lifecycle, campaign_run_id=command.run_id
            )
            if returned_factory_run_id is not None:
                retain_factory_run_id(returned_factory_run_id)
        factory_scheduler_ids = {
            int(record["scheduler_job_id"])
            for record in lifecycle_operation_records
            if record.get("scheduler_job_id") is not None
            and str(record.get("step_kind") or "")
            in {"SNAPSHOT", "WINDOW_CLOSE"}
        }
        accountable_scheduler_ids = {
            int(item["scheduler_job_id"])
            for item in action_local_ledger.scheduler_work_identities
        }
        for scheduler_event in scheduler_runtime_records:
            scheduler_job_id = int(scheduler_event.get("scheduler_job_id") or 0)
            if (
                scheduler_job_id in accountable_scheduler_ids
                and scheduler_job_id not in factory_scheduler_ids
            ):
                action_local_ledger.observe_scheduler_transition(scheduler_event)
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
        if not bool(result.lifecycle_started):
            # A returned activation/origin terminal is authoritative.  Decide
            # whether a real accountable stage began before invoking strict
            # accounting; never manufacture a None evidence placeholder.
            # Factory-run retention was skipped above for this branch.
            return _finalize_returned_pre_lifecycle_result(
                result=result,
                lifecycle=lifecycle,
                command=command,
                cycle_id=cycle_id,
                execution_id=execution_id,
                paths=paths,
                launch_git_provenance=preflight["git_provenance"],
                campaign_units=campaign_units,
                action_local_transport_identities=(
                    action_local_transport_identities
                ),
                stage_observer_state=stage_observer_state,
            )
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
            scheduler_operation_observer=(
                action_local_ledger.observe_scheduler_transition
            ),
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
        # Seal terminal reconciliation on the same owner at the actual cleanup
        # boundary.  Every named validation is independently mirrored into the
        # action-local ledger at execution time.
        from printer_v1.sources.campaign_six_unit_accounting import (
            build_campaign_stage_id,
            seal_campaign_stage_evidence,
        )
        from printer_v1.sources.measured_transport import LocalValidationIdentity
        terminal_stage_id = build_campaign_stage_id(
            campaign_id=command.campaign_id,
            run_id=command.run_id,
            cycle_id=cycle_id,
            stage_kind="CAMPAIGN_TERMINAL_RECONCILIATION",
            stage_sequence=4,
        )
        terminal_validation_kinds = (
            "CAMPAIGN_TERMINAL_OWNERSHIP_VALIDATED",
            "ZERO_ACTIVE_WORK_VALIDATED",
            "ZERO_LOCKED_WORK_VALIDATED",
            "LEASE_RELEASE_VALIDATED",
            "FORBIDDEN_DELTAS_VALIDATED",
            "NO_RETRY_VALIDATED",
            "NO_RESTART_VALIDATED",
            "NO_RESUME_VALIDATED",
            "NO_SUCCESSOR_VALIDATED",
        )
        terminal_validations = [
            LocalValidationIdentity(
                stage_id=terminal_stage_id,
                subject_identity=f"{cycle_id}:terminal",
                validation_kind=kind,
                validation_ordinal=index,
            )
            for index, kind in enumerate(terminal_validation_kinds, start=1)
        ]
        for validation in terminal_validations:
            action_local_ledger.observe_local_validation(validation)
        terminal_status = (
            "COMPLETED"
            if str(lifecycle.get("run_status") or "") == "COMPLETED"
            and cleanup.get("cleanup_completed") is True
            and cleanup.get("lease_released") is True
            else "FAILED"
        )
        campaign_units.ingest_stage_evidence(
            seal_campaign_stage_evidence(
                stage_id=terminal_stage_id,
                stage_kind="CAMPAIGN_TERMINAL_RECONCILIATION",
                stage_sequence=4,
                stage_terminal_status=terminal_status,
                stage_first_terminal_cause=(
                    None if terminal_status == "COMPLETED" else cause
                ),
                campaign_id=command.campaign_id,
                run_id=command.run_id,
                cycle_id=cycle_id,
                evidence={
                    "evidence_kind": "CAMPAIGN_SIX_UNIT_EVIDENCE_V1",
                    "transport_operations": [],
                    "local_validations": 0,
                    "scheduler_work_items": 0,
                    "lifecycle_reservations": 0,
                },
                local_validation_identities=terminal_validations,
            )
        )
        # Repaired lifecycle acceptance finalizes the same coordinator-created
        # owner and action-local ledger before the canonical report is persisted.
        # This is the only full-run accounting/report extension boundary.
        full_run_acceptance = _apply_full_run_campaign_acceptance(
            db_path=command.db_path,
            campaign_id=command.campaign_id,
            campaign_run_id=command.run_id,
            cycle_id=cycle_id,
            configuration_id=command.configuration_id,
            factory_run_id=initialized_factory_run_id,
            execution_id=execution_id,
            supervision_id=command.supervision_id,
            launch_git_provenance=preflight["git_provenance"],
            db_target_identity=command.db_target_identity,
            lifecycle_started=bool(result.lifecycle_started),
            lifecycle_operation_records=lifecycle_operation_records,
            forbidden_deltas=dict(lifecycle.get("forbidden_deltas") or {}),
            accounting_owner=campaign_units,
            action_local_ledger=action_local_ledger,
            runtime_terminal_status=(
                "COMPLETED"
                if str(lifecycle.get("run_status") or "") == "COMPLETED"
                else str(lifecycle.get("run_status") or "UNKNOWN")
            ),
            runtime_first_terminal_cause=cause,
            cleanup_result=cleanup,
        )
        aggregated_six_unit_totals = campaign_units.six_unit_totals()
        aggregated_six_unit_evidence = campaign_units.durable_evidence()
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
            six_unit_totals=aggregated_six_unit_totals,
            six_unit_evidence=aggregated_six_unit_evidence,
            require_six_unit_evidence=True,
            elapsed_seconds=reporting.get("elapsed_seconds")
            if reporting.get("elapsed_seconds") is not None
            else lifecycle.get("elapsed_seconds"),
        )
        payload["full_run_terminal_evidence"] = dict(
            full_run_acceptance.get("report") or {}
        )
        payload["campaign_acceptance"] = dict(
            full_run_acceptance.get("campaign_acceptance") or {}
        )
        payload["campaign_acceptance_verdict"] = full_run_acceptance.get("verdict")
        lifecycle_pass = bool(
            full_run_acceptance.get("verdict") == FULL_RUN_VERDICT_PASS
        )
        clean_memory_outcome = build_current_run_clean_memory_outcome(
            command.db_path,
            campaign_id=command.campaign_id,
            run_id=command.run_id,
            factory_run_id=initialized_factory_run_id,
        )
        payload["operational_lifecycle_pass"] = lifecycle_pass
        payload["clean_memory_outcome_pass"] = bool(
            clean_memory_outcome.get("clean_memory_outcome_pass")
        )
        payload["clean_memory_outcome"] = clean_memory_outcome
        report = write_campaign_terminal_report(
            command.db_path,
            paths["reports"],
            report_id=command.report_id,
            campaign_id=command.campaign_id,
            configuration_id=command.configuration_id,
            report=payload,
            require_six_unit_evidence=True,
        )
        terminal = {
            "status": "OPERATIONAL_CAMPAIGN_TERMINAL",
            "execution_id": execution_id,
            "campaign_id": command.campaign_id,
            "run_id": command.run_id,
            "run_status": lifecycle.get("run_status"),
            "first_terminal_cause": cause,
            "report": report,
            "campaign_acceptance_verdict": full_run_acceptance.get("verdict"),
            "campaign_pass": lifecycle_pass,
            "operational_lifecycle_pass": lifecycle_pass,
            "clean_memory_outcome_pass": bool(
                clean_memory_outcome.get("clean_memory_outcome_pass")
            ),
            "clean_memory_outcome": clean_memory_outcome,
            "full_run_campaign_acceptance": full_run_acceptance,
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
            "policy_version": policy.policy_version,
            "selective_1h_continuation": policy.selective_1h_continuation,
            "continuous_four_hour": policy.continuous_four_hour,
            "standard_four_hour_campaign": policy.standard_four_hour_campaign,
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
                # Only report factory identity after genuine lifecycle retention.
                # A pre-generated UUID alone must not inflate lifecycle_started.
                factory_run_id=(
                    initialized_factory_run_id
                    if factory_identity_retained
                    else None
                ),
                heartbeat_failure=(
                    heartbeat.poll_failure()
                    if heartbeat is not None else observed_heartbeat_failure
                ),
                accounting_owner=campaign_units,
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
    git_provenance_authorization: ValidatedGitProvenanceAuthorization | None = None,
    disposable_proof: Any | None = None,
) -> dict[str, Any]:
    """Run one bounded persistent 15m-only production campaign.

    ``disposable_proof`` is a Checkpoint-8 proof-only capability. This boundary
    slice exposes and threads its identity without weakening default production
    authorization behavior.
    """
    return _run_operational_campaign(
        policy=_NORMAL_CAMPAIGN_POLICY,
        operator_approved=operator_approved,
        owner=owner,
        pump_transport=pump_transport,
        secondary_transport=secondary_transport,
        migration_transport=migration_transport,
        git_provenance_authorization=git_provenance_authorization,
        disposable_proof=disposable_proof,
    )


def run_standard_four_hour_campaign(
    *,
    operator_approved: bool,
    git_provenance_authorization: ValidatedGitProvenanceAuthorization | None,
    owner: Any | None = None,
    pump_transport: Any | None = None,
    secondary_transport: Any | None = None,
    migration_transport: Any | None = None,
) -> dict[str, Any]:
    """Run one externally authorized production-persistent standard 4h campaign."""
    return _run_operational_campaign(
        policy=STANDARD_FOUR_HOUR_POLICY,
        operator_approved=operator_approved,
        owner=owner,
        pump_transport=pump_transport,
        secondary_transport=secondary_transport,
        migration_transport=migration_transport,
        git_provenance_authorization=git_provenance_authorization,
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
        from printer_v1.sources.direct_pump_migration import (
            build_direct_pump_migration_transport,
        )

        migration_transport = build_direct_pump_migration_transport(
            rpc_url=resolve_solana_rpc_configuration().url,  # same shared owner
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
    transport_owner: Any | None = None,
    preflight_override: Mapping[str, Any] | None = None,
    execution_id: str | None = None,
    owner_id: str | None = None,
    now: str | None = None,
    db_path: str | Path | None = None,
    renewal_hook: Any | None = None,
    cancellation_probe: Any | None = None,
) -> dict[str, Any]:
    """Retained deferred helper for frozen candidate-acquisition regressions.

    This helper is deliberately absent from the public operational CLI. Its
    imports stay lazy so the active two-token factory does not depend on the
    deferred candidate-acquisition subsystem.
    """
    from printer_v1.operator_cli.candidate_acquisition_integration import (
        CandidateAcquisitionIntegrationError,
        run_candidate_acquisition_integration,
    )

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
    transport_owner: Any | None = None,
    preflight_override: Mapping[str, Any] | None = None,
    execution_id: str | None = None,
    owner_id: str | None = None,
    now: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Retained deferred helper for frozen cursor-recovery regressions."""
    from printer_v1.operator_cli.candidate_acquisition_integration import (
        CandidateAcquisitionIntegrationError,
    )
    from printer_v1.operator_cli.cursor_continuity_recovery import (
        run_cursor_continuity_recovery,
    )

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


def run_deferred_candidate_acquisition_command(
    argv: Iterable[str] | None = None,
    *,
    acquisition_transport_owner: Any | None = None,
    acquisition_preflight: Mapping[str, Any] | None = None,
    acquisition_execution_id: str | None = None,
    acquisition_now: str | None = None,
    acquisition_db_path: str | Path | None = None,
    acquisition_environment: Mapping[str, str] | None = None,
    acquisition_one_shot_transport: Any | None = None,
) -> int:
    """Non-public command seam retained for frozen offline regression proofs.

    This function is not registered in ``pyproject.toml``, not dispatched by
    :func:`main`, and performs lazy imports only after a deferred test explicitly
    invokes it. It preserves the complete historical integration proof surface
    without making candidate acquisition an operational prerequisite.
    """
    from printer_v1.operator_cli.candidate_acquisition_integration import (
        CLI_MODE_N2,
        CLI_MODE_N7,
        MODE_N2,
        MODE_N7,
        CandidateAcquisitionIntegrationError,
    )
    from printer_v1.operator_cli.live_candidate_acquisition_transport import (
        build_live_candidate_acquisition_transport_owner,
    )

    parser = argparse.ArgumentParser(
        description="Deferred candidate-acquisition offline regression seam."
    )
    parser.add_argument("mode", choices=(CLI_MODE_N2, CLI_MODE_N7))
    parser.add_argument("--operator-approved", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    _ACTION_RUN_CONTEXT["run_id"] = None
    try:
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
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "DEFERRED_CANDIDATE_ACQUISITION_BLOCKED",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "mode": args.mode,
                    "action_run_id": _ACTION_RUN_CONTEXT.get("run_id"),
                    "campaign_source_calls": None,
                    "source_calls": 0,
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
        "active_intake_path": ACTIVE_INTAKE_PATH,
        "active_token_capacity": TOKEN_CAPACITY,
        "candidate_acquisition": {
            "state": CANDIDATE_ACQUISITION_STATE,
            "operational_prerequisite": False,
            "public_operational_modes": False,
            "cursor_authority": False,
            "deferred_modes": DEFERRED_CANDIDATE_ACQUISITION_MODES,
        },
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


def _resolve_report_only_identity(
    connection: sqlite3.Connection,
    *,
    campaign_id: str | None,
    run_id: str | None,
) -> dict[str, Any]:
    """Resolve exact campaign/run identity for report-only (read-only).

    Explicit mode requires both IDs and never falls back to another campaign.
    No-argument mode resolves the latest supervision first, then that exact
    campaign/run configuration — never the globally newest report.
    """
    explicit_campaign = None if campaign_id is None else str(campaign_id).strip()
    explicit_run = None if run_id is None else str(run_id).strip()
    if (explicit_campaign and not explicit_run) or (
        explicit_run and not explicit_campaign
    ):
        return {
            "status": "REPLAY_BLOCKED",
            "block_reason": "REPORT_ONLY_EXACT_IDENTITY_INCOMPLETE",
            "requested_identity": {
                "campaign_id": explicit_campaign,
                "run_id": explicit_run,
            },
        }

    if explicit_campaign and explicit_run:
        # Exact identity: supervision (campaign_id + run_id) owns configuration.
        # Never inspect another campaign as fallback.
        run_row = connection.execute(
            """SELECT campaign_id,run_id FROM printer_memory_factory_campaign_runs
               WHERE campaign_id=? AND run_id=?""",
            (explicit_campaign, explicit_run),
        ).fetchone()
        supervision = connection.execute(
            """SELECT campaign_id,run_id,configuration_id,supervision_state
               FROM printer_memory_factory_campaign_supervision
               WHERE campaign_id=? AND run_id=?
               ORDER BY created_at DESC, supervision_id DESC LIMIT 2""",
            (explicit_campaign, explicit_run),
        ).fetchall()
        if run_row is None and not supervision:
            return {
                "status": "REPLAY_BLOCKED",
                "block_reason": "REPORT_ONLY_IDENTITY_UNKNOWN",
                "requested_identity": {
                    "campaign_id": explicit_campaign,
                    "run_id": explicit_run,
                },
            }
        if len(supervision) > 1:
            # Distinct configuration_ids for one campaign/run is ambiguous.
            config_ids = {str(row["configuration_id"]) for row in supervision}
            if len(config_ids) > 1:
                return {
                    "status": "REPLAY_BLOCKED",
                    "block_reason": "REPORT_ONLY_IDENTITY_AMBIGUOUS",
                    "requested_identity": {
                        "campaign_id": explicit_campaign,
                        "run_id": explicit_run,
                    },
                }
        if supervision:
            configuration_id = str(supervision[0]["configuration_id"])
        else:
            # Run exists without supervision: resolve the unique configuration
            # for this campaign only when exactly one configuration row exists.
            configs = connection.execute(
                """SELECT configuration_id,campaign_id,configuration_json
                   FROM printer_memory_factory_campaign_configurations
                   WHERE campaign_id=?
                   ORDER BY created_at DESC, configuration_id DESC""",
                (explicit_campaign,),
            ).fetchall()
            if len(configs) != 1:
                return {
                    "status": "REPLAY_BLOCKED",
                    "block_reason": (
                        "REPORT_ONLY_IDENTITY_AMBIGUOUS"
                        if len(configs) > 1
                        else "REPORT_ONLY_IDENTITY_UNKNOWN"
                    ),
                    "requested_identity": {
                        "campaign_id": explicit_campaign,
                        "run_id": explicit_run,
                    },
                }
            configuration_id = str(configs[0]["configuration_id"])
        config_row = connection.execute(
            """SELECT configuration_id,campaign_id,configuration_json
               FROM printer_memory_factory_campaign_configurations
               WHERE configuration_id=? AND campaign_id=?""",
            (configuration_id, explicit_campaign),
        ).fetchone()
        if config_row is None:
            return {
                "status": "REPLAY_BLOCKED",
                "block_reason": "REPORT_ONLY_IDENTITY_UNKNOWN",
                "requested_identity": {
                    "campaign_id": explicit_campaign,
                    "run_id": explicit_run,
                },
            }
        return {
            "status": "RESOLVED",
            "campaign_id": explicit_campaign,
            "run_id": explicit_run,
            "configuration_id": str(config_row["configuration_id"]),
            "configuration_json": str(config_row["configuration_json"]),
            "requested_identity": {
                "campaign_id": explicit_campaign,
                "run_id": explicit_run,
            },
        }

    # No-argument: latest supervision first, then that exact campaign/run.
    supervision = connection.execute(
        """SELECT campaign_id,run_id,configuration_id,supervision_state
           FROM printer_memory_factory_campaign_supervision
           ORDER BY created_at DESC, supervision_id DESC LIMIT 1"""
    ).fetchone()
    if supervision is None:
        return {
            "status": "REPLAY_BLOCKED",
            "block_reason": "REPORT_ONLY_IDENTITY_UNKNOWN",
            "requested_identity": {"campaign_id": None, "run_id": None},
        }
    resolved_campaign = str(supervision["campaign_id"])
    resolved_run = str(supervision["run_id"])
    config_row = connection.execute(
        """SELECT configuration_id,campaign_id,configuration_json
           FROM printer_memory_factory_campaign_configurations
           WHERE configuration_id=? AND campaign_id=?""",
        (supervision["configuration_id"], resolved_campaign),
    ).fetchone()
    if config_row is None:
        return {
            "status": "REPLAY_BLOCKED",
            "block_reason": "REPORT_ONLY_IDENTITY_UNKNOWN",
            "requested_identity": {
                "campaign_id": resolved_campaign,
                "run_id": resolved_run,
            },
        }
    try:
        config_payload = json.loads(str(config_row["configuration_json"] or "{}"))
    except json.JSONDecodeError:
        return {
            "status": "REPLAY_BLOCKED",
            "block_reason": "REPLAY_BLOCKED",
            "requested_identity": {
                "campaign_id": resolved_campaign,
                "run_id": resolved_run,
            },
        }
    config_run = str(config_payload.get("run_id") or "")
    if config_run and config_run != resolved_run:
        return {
            "status": "REPLAY_BLOCKED",
            "block_reason": "REPLAY_BLOCKED",
            "requested_identity": {
                "campaign_id": resolved_campaign,
                "run_id": resolved_run,
            },
        }
    return {
        "status": "RESOLVED",
        "campaign_id": resolved_campaign,
        "run_id": resolved_run,
        "configuration_id": str(config_row["configuration_id"]),
        "configuration_json": str(config_row["configuration_json"]),
        "requested_identity": {
            "campaign_id": resolved_campaign,
            "run_id": resolved_run,
        },
    }


def _load_exact_terminal_summary(
    *,
    configuration: Mapping[str, Any],
    campaign_id: str,
    run_id: str,
    configuration_id: str,
    artifact_root: str | Path | None = None,
) -> dict[str, Any] | None:
    """Load terminal-summary only when all identities exactly match.

    ``campaign_id``, ``run_id``, ``configuration_id``, and ``execution_id`` must
    all be present on the summary and exactly equal the requested attempt.
    Missing or empty identity fields are a mismatch (return None).
    """
    import hashlib

    execution_id = str(configuration.get("execution_id") or "").strip()
    if not execution_id:
        return None
    summary_root = Path(artifact_root or ARTIFACT_ROOT).resolve()
    summary_path = (summary_root / execution_id / "terminal-summary.json").resolve()
    if not summary_path.is_file():
        return None
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, Mapping):
        return None
    payload_campaign = str(payload.get("campaign_id") or "").strip()
    payload_run = str(payload.get("run_id") or "").strip()
    payload_config = str(payload.get("configuration_id") or "").strip()
    payload_execution = str(payload.get("execution_id") or "").strip()
    # Missing identity is a mismatch; empty/optional fields are not accepted.
    if not payload_campaign or payload_campaign != str(campaign_id):
        return None
    if not payload_run or payload_run != str(run_id):
        return None
    if not payload_config or payload_config != str(configuration_id):
        return None
    if not payload_execution or payload_execution != execution_id:
        return None
    digest = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    return {
        "status": payload.get("status"),
        "first_terminal_cause": payload.get("first_terminal_cause"),
        "accounting_status": payload.get("accounting_status"),
        "report_written": payload.get("report_written"),
        "report_block_reason": payload.get("report_block_reason"),
        "summary_path": str(summary_path),
        "summary_sha256": digest,
    }


def _report_only_zero_work(payload: dict[str, Any]) -> dict[str, Any]:
    """Stamp the zero-source / zero-write report-only contract on every path."""
    payload.setdefault("mode", "REPORT_ONLY")
    payload["source_calls"] = 0
    payload["scheduler_runtime_calls"] = 0
    payload["database_writes"] = 0
    payload["replay_new_source_calls"] = 0
    payload["replay_new_scheduler_calls"] = 0
    payload.setdefault("fallback_used", False)
    return payload


def report_only(
    *,
    campaign_id: str | None = None,
    run_id: str | None = None,
    db_path: str | Path | None = None,
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    """Replay one exact campaign terminal report (zero-source, zero-write).

    Both ``campaign_id`` and ``run_id`` must be supplied together or neither.
    Discovery-only output is never a campaign report-only fallback.
    """
    replay_db = Path(db_path or AUTHORITATIVE_DB).resolve()
    replay_artifact_root = Path(artifact_root or ARTIFACT_ROOT).resolve()
    connection = sqlite3.connect(
        f"file:{replay_db}?mode=ro", uri=True
    )
    connection.row_factory = sqlite3.Row
    try:
        identity = _resolve_report_only_identity(
            connection, campaign_id=campaign_id, run_id=run_id
        )
        if identity.get("status") != "RESOLVED":
            return _report_only_zero_work(
                {
                    "mode": "REPORT_ONLY",
                    "status": "REPLAY_BLOCKED",
                    "requested_identity": identity.get("requested_identity")
                    or {"campaign_id": campaign_id, "run_id": run_id},
                    "report_rows": 0,
                    "fallback_used": False,
                    "block_reason": str(
                        identity.get("block_reason") or "REPLAY_BLOCKED"
                    ),
                }
            )

        resolved_campaign = str(identity["campaign_id"])
        resolved_run = str(identity["run_id"])
        resolved_configuration_id = str(identity["configuration_id"])
        try:
            configuration = json.loads(str(identity["configuration_json"]))
        except json.JSONDecodeError:
            return _report_only_zero_work({
                "mode": "REPORT_ONLY",
                "status": "REPLAY_BLOCKED",
                "requested_identity": identity["requested_identity"],
                "report_rows": 0,
                "fallback_used": False,
                "block_reason": "REPLAY_BLOCKED",
                "source_calls": 0,
                "scheduler_runtime_calls": 0,
                "database_writes": 0,
            })
        if not isinstance(configuration, dict):
            return _report_only_zero_work({
                "mode": "REPORT_ONLY",
                "status": "REPLAY_BLOCKED",
                "requested_identity": identity["requested_identity"],
                "report_rows": 0,
                "fallback_used": False,
                "block_reason": "REPLAY_BLOCKED",
                "source_calls": 0,
                "scheduler_runtime_calls": 0,
                "database_writes": 0,
            })
        config_run = str(configuration.get("run_id") or "")
        if config_run and config_run != resolved_run:
            return _report_only_zero_work({
                "mode": "REPORT_ONLY",
                "status": "REPLAY_BLOCKED",
                "requested_identity": identity["requested_identity"],
                "report_rows": 0,
                "fallback_used": False,
                "block_reason": "REPLAY_BLOCKED",
                "source_calls": 0,
                "scheduler_runtime_calls": 0,
                "database_writes": 0,
            })

        row = connection.execute(
            """SELECT r.report_id,r.campaign_id,r.configuration_id,
                      r.report_state,c.configuration_json,c.campaign_id AS config_campaign_id
               FROM printer_memory_factory_campaign_reports AS r
               JOIN printer_memory_factory_campaign_configurations AS c
                 ON c.configuration_id=r.configuration_id
               WHERE r.report_state='REPORT_TERMINAL'
                 AND r.campaign_id=?
                 AND c.campaign_id=?
                 AND r.configuration_id=?
               ORDER BY r.created_at DESC, r.report_id DESC""",
            (resolved_campaign, resolved_campaign, resolved_configuration_id),
        ).fetchall()
    finally:
        connection.close()

    if not row:
        summary = _load_exact_terminal_summary(
            configuration=configuration,
            campaign_id=resolved_campaign,
            run_id=resolved_run,
            configuration_id=resolved_configuration_id,
            artifact_root=replay_artifact_root,
        )
        if summary is None:
            # Report missing and summary absent/mismatched: primary block reason
            # is the summary defect (do not hide it as a secondary diagnostic).
            return _report_only_zero_work({
                "mode": "REPORT_ONLY",
                "status": "REPLAY_BLOCKED",
                "requested_identity": identity["requested_identity"],
                "report_rows": 0,
                "fallback_used": False,
                "block_reason": "EXACT_TERMINAL_SUMMARY_MISSING_OR_MISMATCHED",
                "source_calls": 0,
                "scheduler_runtime_calls": 0,
                "database_writes": 0,
            })
        # Exact report missing with a valid exact summary.
        return _report_only_zero_work({
            "mode": "REPORT_ONLY",
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "report_rows": 0,
            "fallback_used": False,
            "block_reason": "EXACT_TERMINAL_REPORT_MISSING",
            "terminal_summary": summary,
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        })

    if len(row) != 1:
        # Exact identity must not be ambiguous across terminal report rows.
        return _report_only_zero_work({
            "mode": "REPORT_ONLY",
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "report_rows": len(row),
            "fallback_used": False,
            "block_reason": "REPLAY_BLOCKED",
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        })

    report_row = row[0]
    if str(report_row["campaign_id"]) != resolved_campaign:
        return _report_only_zero_work({
            "mode": "REPORT_ONLY",
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "report_rows": 1,
            "fallback_used": False,
            "block_reason": "REPLAY_BLOCKED",
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        })
    if str(report_row["configuration_id"]) != resolved_configuration_id:
        return _report_only_zero_work({
            "mode": "REPORT_ONLY",
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "report_rows": 1,
            "fallback_used": False,
            "block_reason": "REPLAY_BLOCKED",
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        })
    if str(report_row["config_campaign_id"]) != resolved_campaign:
        return _report_only_zero_work({
            "mode": "REPORT_ONLY",
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "report_rows": 1,
            "fallback_used": False,
            "block_reason": "REPLAY_BLOCKED",
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        })

    report_dir = None
    report_directory_identity = configuration.get("report_directory_identity")
    if not report_directory_identity:
        return _report_only_zero_work({
            "mode": "REPORT_ONLY",
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "report_rows": 1,
            "fallback_used": False,
            "block_reason": "REPLAY_BLOCKED",
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        })
    for candidate in replay_artifact_root.glob("*/reports"):
        if report_path_identity(candidate) == report_directory_identity:
            report_dir = candidate
            break
    if report_dir is None:
        return _report_only_zero_work({
            "mode": "REPORT_ONLY",
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "report_rows": 1,
            "fallback_used": False,
            "block_reason": "REPLAY_BLOCKED",
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        })

    try:
        replay = replay_campaign_terminal_report(
            replay_db,
            report_dir,
            report_id=report_row["report_id"],
            campaign_id=report_row["campaign_id"],
            configuration_id=report_row["configuration_id"],
        )
    except Exception:
        return _report_only_zero_work({
            "mode": "REPORT_ONLY",
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "report_rows": 1,
            "fallback_used": False,
            "block_reason": "REPLAY_BLOCKED",
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        })

    if replay.get("artifact_matches") is not True:
        return _report_only_zero_work({
            "mode": "REPORT_ONLY",
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "report_rows": 1,
            "fallback_used": False,
            "block_reason": "TERMINAL_REPORT_ARTIFACT_MISMATCH",
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        })

    # Exact identity agreement across row, configuration, and report JSON.
    stored_report = replay.get("report") if isinstance(replay, Mapping) else None
    stored_identity = (
        stored_report.get("identity")
        if isinstance(stored_report, Mapping)
        else None
    )
    if not isinstance(stored_identity, Mapping):
        return _report_only_zero_work({
            "mode": "REPORT_ONLY",
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "report_rows": 1,
            "fallback_used": False,
            "block_reason": "REPLAY_BLOCKED",
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        })
    if str(stored_identity.get("campaign_id") or "") != resolved_campaign:
        return _report_only_zero_work({
            "mode": "REPORT_ONLY",
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "report_rows": 1,
            "fallback_used": False,
            "block_reason": "REPLAY_BLOCKED",
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        })
    if str(stored_identity.get("run_id") or "") != resolved_run:
        return _report_only_zero_work({
            "mode": "REPORT_ONLY",
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "report_rows": 1,
            "fallback_used": False,
            "block_reason": "REPLAY_BLOCKED",
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        })
    if str(stored_identity.get("configuration_id") or "") != resolved_configuration_id:
        return _report_only_zero_work({
            "mode": "REPORT_ONLY",
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "report_rows": 1,
            "fallback_used": False,
            "block_reason": "REPLAY_BLOCKED",
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        })
    if str(replay.get("report_id") or stored_identity.get("report_id") or "") != str(
        report_row["report_id"]
    ):
        return _report_only_zero_work({
            "mode": "REPORT_ONLY",
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "report_rows": 1,
            "fallback_used": False,
            "block_reason": "REPLAY_BLOCKED",
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        })

    full_run = stored_report.get("full_run_terminal_evidence")
    if not isinstance(full_run, Mapping):
        return _report_only_zero_work({
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "block_reason": "FULL_RUN_EVIDENCE_MISSING",
        })
    full_identity = full_run.get("identity") or {}
    accounting = full_run.get("full_run_accounting") or {}
    hashes = full_run.get("hashes") or {}
    owner_evidence = accounting.get("owner_evidence") or {}
    action_evidence = accounting.get("action_local_evidence") or {}
    if (
        str(full_run.get("report_kind") or "")
        != "V2_9_8B_FULL_RUN_WINDOW_15M_TERMINAL_EVIDENCE"
        or str(full_identity.get("campaign_id") or "") != resolved_campaign
        or str(full_identity.get("campaign_run_id") or "") != resolved_run
        or str(owner_evidence.get("evidence_kind") or "")
        != "CAMPAIGN_SIX_UNIT_EVIDENCE_V2"
        or accounting.get("owner_action_local_reconciliation", {}).get("equal")
        is not True
        or accounting.get("owner_action_local_reconciliation", {}).get(
            "equality_scoped_stage_ids"
        )
        is not None
    ):
        return _report_only_zero_work({
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "block_reason": "FULL_RUN_REPAIRED_EVIDENCE_INVALID",
        })
    import hashlib
    def _canonical(value: Any) -> bytes:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    expected_owner_hash = hashlib.sha256(_canonical(owner_evidence)).hexdigest()
    expected_action_hash = hashlib.sha256(_canonical(action_evidence)).hexdigest()
    marker_evidence = full_run.get("authorization_and_invocation") or {}
    from printer_v1.operator_cli.campaign_full_run_accounting import (
        EVIDENCE_MODE_DISPOSABLE_PUBLIC_COMPOSITION_PROOF,
    )
    evidence_mode = str(marker_evidence.get("evidence_mode") or "")
    body = dict(full_run)
    body_hashes = dict(hashes)
    body_hashes.pop("report_body_sha256", None)
    body["hashes"] = body_hashes
    expected_body_hash = hashlib.sha256(_canonical(body)).hexdigest()

    common_hash_mismatch = bool(
        hashes.get("owner_evidence_sha256") != expected_owner_hash
        or hashes.get("action_local_evidence_sha256") != expected_action_hash
        or hashes.get("report_body_sha256") != expected_body_hash
    )
    if evidence_mode == EVIDENCE_MODE_DISPOSABLE_PUBLIC_COMPOSITION_PROOF:
        proof_expectation = marker_evidence.get("proof_expectation")
        proof_invocation_evidence = marker_evidence.get(
            "proof_invocation_evidence"
        )
        expected_proof_expectation_hash = (
            campaign_evidence_sha256(proof_expectation)
            if isinstance(proof_expectation, Mapping)
            else None
        )
        expected_proof_invocation_hash = (
            campaign_evidence_sha256(proof_invocation_evidence)
            if isinstance(proof_invocation_evidence, Mapping)
            else None
        )
        mode_hash_mismatch = bool(
            hashes.get("proof_expectation_sha256")
            != expected_proof_expectation_hash
            or hashes.get("proof_invocation_evidence_sha256")
            != expected_proof_invocation_hash
            or hashes.get("authorization_marker_sha256") not in (None, "")
            or hashes.get("invocation_marker_sha256") not in (None, "")
            or hashes.get("proof_expectation_sha256")
            == full_identity.get("factory_config_hash")
            or hashes.get("proof_invocation_evidence_sha256")
            == full_identity.get("factory_config_hash")
        )
    else:
        authorization_marker = marker_evidence.get("authorization_marker")
        invocation_marker = marker_evidence.get("invocation_marker")
        expected_authorization_hash = (
            campaign_evidence_sha256(authorization_marker)
            if isinstance(authorization_marker, Mapping)
            else None
        )
        expected_invocation_hash = (
            campaign_evidence_sha256(invocation_marker)
            if isinstance(invocation_marker, Mapping)
            else None
        )
        mode_hash_mismatch = bool(
            hashes.get("authorization_marker_sha256")
            != expected_authorization_hash
            or hashes.get("invocation_marker_sha256")
            != expected_invocation_hash
            or hashes.get("authorization_marker_sha256")
            == full_identity.get("factory_config_hash")
            or hashes.get("invocation_marker_sha256")
            == full_identity.get("factory_config_hash")
        )
    if common_hash_mismatch or mode_hash_mismatch:
        return _report_only_zero_work({
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "block_reason": "FULL_RUN_EVIDENCE_HASH_MISMATCH",
        })
    from printer_v1.sources.campaign_six_unit_accounting import (
        reconstruct_six_unit_totals_from_evidence,
    )
    try:
        reconstructed_totals = reconstruct_six_unit_totals_from_evidence(
            owner_evidence
        )
    except Exception:
        reconstructed_totals = {}
    if reconstructed_totals != accounting.get("six_unit_totals"):
        return _report_only_zero_work({
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "block_reason": "FULL_RUN_TOTAL_RECONSTRUCTION_MISMATCH",
        })
    verification = sqlite3.connect(f"file:{replay_db}?mode=ro", uri=True)
    verification.row_factory = sqlite3.Row
    try:
        durable_windows = [
            dict(item)
            for item in verification.execute(
                """SELECT window_id,window_kind,window_state,token_slot_id,
                          token_row_id,pair_row_id,memory_window_row_id,cycle_id,
                          first_terminal_cause
                   FROM printer_memory_factory_campaign_windows
                   WHERE campaign_id=? AND run_id=? AND cycle_id=?
                   ORDER BY window_id""",
                (
                    resolved_campaign,
                    resolved_run,
                    str(full_identity.get("cycle_id")),
                ),
            )
        ]
        durable_scheduler = [
            dict(item)
            for item in verification.execute(
                """SELECT scheduler_work_id,scheduler_job_id,work_intent,
                          work_state,window_id,token_slot_id,first_terminal_cause,
                          terminal_at,ownership_contract_version,stage_id,
                          work_scope,target_category,target_identity,factory_run_id
                   FROM printer_memory_factory_campaign_scheduler_work
                   WHERE campaign_id=? AND run_id=? AND cycle_id=?
                     AND ownership_contract_version='V2_STAGE_SCOPED'
                   ORDER BY scheduler_work_id""",
                (
                    resolved_campaign,
                    resolved_run,
                    str(full_identity.get("cycle_id")),
                ),
            )
        ]
        active_or_locked = int(verification.execute(
            """SELECT COUNT(DISTINCT j.id)
               FROM printer_memory_factory_campaign_scheduler_work AS w
               JOIN printer_scheduler_jobs AS j ON j.id=w.scheduler_job_id
               WHERE w.campaign_id=? AND w.run_id=? AND w.cycle_id=?
                 AND w.ownership_contract_version='V2_STAGE_SCOPED'
                 AND (j.status IN ('PENDING','RUNNING','COOLDOWN')
                      OR j.locked_at IS NOT NULL OR j.lock_owner IS NOT NULL)""",
            (
                resolved_campaign,
                resolved_run,
                str(full_identity.get("cycle_id")),
            ),
        ).fetchone()[0])
        from printer_v1.operator_cli.campaign_full_run_accounting import (
            OperationalLifecycleOwnershipContext,
            durable_cleanup_release_timestamps_valid,
            load_invocation_authority_evidence,
        )
        replay_context = OperationalLifecycleOwnershipContext(
            campaign_id=resolved_campaign,
            campaign_run_id=resolved_run,
            cycle_id=str(full_identity.get("cycle_id") or ""),
            configuration_id=resolved_configuration_id,
            factory_run_id=str(full_identity.get("factory_run_id") or ""),
        )
        durable_markers = load_invocation_authority_evidence(
            verification,
            context=replay_context,
            execution_id=str(full_identity.get("execution_id") or ""),
            supervision_id=str(full_identity.get("supervision_id") or ""),
        )
        # Independently reconstruct the factory configuration hash from its exact
        # durable owner (repeat-review F3). The report-carried value is never
        # copied into the durable reconstruction before comparison; the exact
        # ``printer_memory_factory_runs`` row owns the truth.
        factory_rows = [
            dict(item)
            for item in verification.execute(
                """SELECT run_id,config_hash
                   FROM printer_memory_factory_runs
                   WHERE run_id=?""",
                (str(full_identity.get("factory_run_id") or ""),),
            ).fetchall()
        ]
        durable_cleanup = verification.execute(
            """SELECT supervision_id,campaign_id,configuration_id,run_id,owner_id,
                      supervision_state,terminal_status,cleanup_completed_at,
                      lease_released_at,lease_lock_path
               FROM printer_memory_factory_campaign_supervision
               WHERE supervision_id=? AND campaign_id=? AND configuration_id=?
                 AND run_id=?""",
            (
                str(full_identity.get("supervision_id") or ""),
                resolved_campaign,
                resolved_configuration_id,
                resolved_run,
            ),
        ).fetchone()
    finally:
        verification.close()
    selection_evidence = full_run.get("selection_and_lifecycle") or {}
    terminal_safety = full_run.get("terminal_safety") or {}
    cleanup_identity = terminal_safety.get("cleanup_identity") or {}
    # F1 parity: the public replay gate applies the exact same durable
    # cleanup/lease timestamp law as initial acceptance — non-empty, parseable,
    # timezone-aware, and release never before cleanup completion — read from the
    # exact durable supervision row (never a report-carried or invented value).
    durable_cleanup_exact = bool(
        durable_cleanup is not None
        and str(durable_cleanup["supervision_state"]) == "TERMINAL"
        and durable_cleanup["cleanup_completed_at"] is not None
        and durable_cleanup["lease_released_at"] is not None
        and durable_cleanup_release_timestamps_valid(
            durable_cleanup["cleanup_completed_at"],
            durable_cleanup["lease_released_at"],
        )
        and not Path(str(durable_cleanup["lease_lock_path"])).exists()
        and all(
            str(cleanup_identity.get(field) or "")
            == str(durable_cleanup[field])
            for field in (
                "supervision_id", "campaign_id", "configuration_id", "run_id",
                "owner_id",
            )
        )
        and terminal_safety.get("cleanup_completed") is True
        and terminal_safety.get("lease_released") is True
        and str(terminal_safety.get("durable_cleanup_completed_at") or "")
        == str(durable_cleanup["cleanup_completed_at"])
        and str(terminal_safety.get("lease_released_at") or "")
        == str(durable_cleanup["lease_released_at"])
        and terminal_safety.get("lease_lock_absent") is True
    )
    # F3: exactly one factory-run row with a non-empty durable config hash whose
    # identity matches, equal to both the report identity's factory config hash
    # and the separate marker/report factory-config field, and distinct from both
    # marker digests. The durable value is assigned only after validation.
    marker_factory_config_hash = marker_evidence.get("factory_config_hash")
    durable_factory_config_hash = (
        str(factory_rows[0]["config_hash"])
        if len(factory_rows) == 1
        and factory_rows[0].get("config_hash")
        and str(factory_rows[0].get("run_id") or "")
        == str(full_identity.get("factory_run_id") or "")
        else None
    )
    evidence_hash_keys = (
        (
            "proof_expectation_sha256",
            "proof_invocation_evidence_sha256",
        )
        if evidence_mode == EVIDENCE_MODE_DISPOSABLE_PUBLIC_COMPOSITION_PROOF
        else (
            "authorization_marker_sha256",
            "invocation_marker_sha256",
        )
    )
    factory_config_reconstruction_exact = bool(
        durable_factory_config_hash
        and durable_factory_config_hash
        == str(full_identity.get("factory_config_hash") or "")
        and durable_factory_config_hash == str(marker_factory_config_hash or "")
        and all(
            str(hashes.get(key) or "") != durable_factory_config_hash
            for key in evidence_hash_keys
        )
    )
    durable_markers["factory_config_hash"] = durable_factory_config_hash
    if (
        durable_windows
        != selection_evidence.get("campaign_window_ownership_rows")
        or durable_scheduler != accounting.get("campaign_scheduler_work_rows")
        or active_or_locked != 0
        or durable_markers != marker_evidence
        or not durable_cleanup_exact
        or not factory_config_reconstruction_exact
    ):
        return _report_only_zero_work({
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "block_reason": "FULL_RUN_DURABLE_RECONSTRUCTION_MISMATCH",
        })

    from printer_v1.operator_cli.campaign_full_run_accounting import (
        evaluate_campaign_acceptance_gate,
    )
    replay_gate = evaluate_campaign_acceptance_gate(full_run)
    if replay_gate.get("pass") is not True:
        return _report_only_zero_work({
            "status": "REPLAY_BLOCKED",
            "requested_identity": identity["requested_identity"],
            "block_reason": "FULL_RUN_ACCEPTANCE_RECONSTRUCTION_BLOCKED",
        })

    return _report_only_zero_work({
        "mode": "REPORT_ONLY",
        "report_kind": "campaign",
        "status": "REPLAYED",
        "requested_identity": identity["requested_identity"],
        "fallback_used": False,
        "replay": replay,
        "full_run_terminal_evidence": dict(full_run),
        "campaign_source_calls": replay.get("campaign_source_calls"),
        "campaign_scheduler_calls": replay.get("campaign_scheduler_calls"),
        "candidates_observed": replay.get("candidates_observed"),
        "candidates_validated": replay.get("candidates_validated"),
        "eligible_candidates": replay.get("eligible_candidates"),
        "required_token_capacity": replay.get("required_token_capacity"),
        "blocked_supply_reason": replay.get("blocked_supply_reason"),
        "blocked_supply": replay.get("blocked_supply"),
        "replay_new_source_calls": 0,
        "replay_new_scheduler_calls": 0,
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "database_writes": 0,
    })


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Printer V1 bounded persistent Memory Factory command. "
            "Modes: preflight-only, run, selective-1h-preflight, "
            "selective-1h-proof, standard-four-hour-preflight, "
            "standard-four-hour-run, status, cooperative-stop, recover-orphan, "
            "report-only, discovery-only. Candidate acquisition and cursor "
            "recovery are deferred and are not operational prerequisites."
        )
    )
    parser.add_argument(
        "mode",
        choices=(
            "preflight-only", "run", SELECTIVE_1H_PREFLIGHT_MODE,
            SELECTIVE_1H_MODE, STANDARD_FOUR_HOUR_PREFLIGHT_MODE,
            STANDARD_FOUR_HOUR_MODE, "status", "cooperative-stop", "recover-orphan",
            "report-only", "discovery-only",
        ),
    )
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument(
        "--campaign-id",
        default=None,
        help="Exact campaign identity for report-only (requires --run-id).",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Exact run identity for report-only (requires --campaign-id).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    # Reset action-local identity at the start of every public invocation so a
    # blocked preflight/status/report never inherits a previous campaign total.
    _ACTION_RUN_CONTEXT["run_id"] = None
    _ACTION_RUN_CONTEXT["campaign_id"] = None
    _ACTION_RUN_CONTEXT["cycle_id"] = None
    _ACTION_RUN_CONTEXT["execution_id"] = None
    _ACTION_RUN_CONTEXT["action_local_baseline"] = None
    _ACTION_RUN_CONTEXT["mutation_recorder"] = None
    from printer_v1.operator_cli.action_local_mutation_recorder import (
        clear_action_local_mutation_recorder,
    )

    clear_action_local_mutation_recorder()
    from printer_v1.operator_cli.window_15m_child_terminal import (
        CHILD_TERMINAL_ENV_VAR,
        resolve_child_terminal_binding,
        write_child_terminal_envelope,
    )
    child_terminal_binding = None
    try:
        if args.mode != "report-only" and (
            args.campaign_id is not None or args.run_id is not None
        ):
            raise OperationalMemoryFactoryError(
                "campaign-id/run-id are only valid for report-only"
            )
        # Preserve the original direct-run fail-closed classification when no
        # wrapper provenance bindings exist. A valid wrapper supplies all four
        # values; only then establish reporting before their deeper validation
        # so a provenance mismatch can still emit structured terminal evidence.
        provenance_binding_values = tuple(
            os.environ.get(name) for name in GIT_PROVENANCE_MANIFEST_ENV_VARS
        )
        wrapper_bound_modes = {"run", STANDARD_FOUR_HOUR_MODE}
        if args.mode in wrapper_bound_modes and not any(provenance_binding_values):
            label = "ordinary run" if args.mode == "run" else "standard four-hour run"
            raise OperationalMemoryFactoryError(
                f"{label} requires external one-shot wrapper authorization"
            )
        if args.mode in wrapper_bound_modes and all(provenance_binding_values):
            child_terminal_binding = resolve_child_terminal_binding(os.environ)
        elif args.mode not in wrapper_bound_modes and os.environ.get(CHILD_TERMINAL_ENV_VAR):
            raise OperationalMemoryFactoryError(
                "child terminal binding is accepted only for one-shot wrapper run modes"
            )
        # Read the four external manifest/marker bindings once and all-or-none.
        # Ordinary run is application-wrapper-only; auxiliary modes preserve
        # their existing no-binding behavior.
        git_provenance_authorization = _resolve_git_provenance_authorization(args.mode)
        if args.mode in wrapper_bound_modes and git_provenance_authorization is None:
            label = "ordinary run" if args.mode == "run" else "standard four-hour run"
            raise OperationalMemoryFactoryError(
                f"{label} requires external one-shot wrapper authorization"
            )
        if args.mode in wrapper_bound_modes and child_terminal_binding is None:
            label = "ordinary run" if args.mode == "run" else "standard four-hour run"
            raise OperationalMemoryFactoryError(
                f"{label} child terminal binding requires complete wrapper provenance"
            )
        if args.mode == STANDARD_FOUR_HOUR_PREFLIGHT_MODE:
            result = build_standard_four_hour_preflight(
                git_provenance_authorization=git_provenance_authorization
            )
        elif args.mode == "preflight-only":
            result = build_activation_preflight(
                git_provenance_authorization=git_provenance_authorization
            )
        elif args.mode == SELECTIVE_1H_PREFLIGHT_MODE:
            result = build_selective_1h_preflight()
        elif args.mode == "run":
            result = run_operational_campaign(
                operator_approved=args.operator_approved,
                git_provenance_authorization=git_provenance_authorization,
            )
        elif args.mode == STANDARD_FOUR_HOUR_MODE:
            result = run_standard_four_hour_campaign(
                operator_approved=args.operator_approved,
                git_provenance_authorization=git_provenance_authorization,
            )
        elif args.mode == SELECTIVE_1H_MODE:
            result = run_selective_1h_proof(
                operator_approved=args.operator_approved
            )
        elif args.mode == "discovery-only":
            result = run_discovery_only_qualification(
                operator_approved=args.operator_approved
            )
        elif args.mode == "status":
            result = operational_status()
        elif args.mode == "cooperative-stop":
            result = cooperative_stop(operator_approved=args.operator_approved)
        elif args.mode == "recover-orphan":
            result = recover_orphan(operator_approved=args.operator_approved)
        else:
            result = report_only(
                campaign_id=args.campaign_id,
                run_id=args.run_id,
            )
        if args.mode in wrapper_bound_modes and child_terminal_binding is not None:
            write_child_terminal_envelope(
                binding=child_terminal_binding,
                source=result,
                mode=args.mode,
                exit_code=0,
                success=True,
            )
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        # V2-9.8B.10 / V2-9.8B.19 / V2-9.8B readiness: action-local terminal
        # truth from durable campaign ownership and source rows. Never invent
        # source_calls=0 when attributable requests exist (B6/B7).
        action_run_id = _ACTION_RUN_CONTEXT.get("run_id")
        action_campaign_id = _ACTION_RUN_CONTEXT.get("campaign_id")
        action_cycle_id = _ACTION_RUN_CONTEXT.get("cycle_id")
        action_execution_id = _ACTION_RUN_CONTEXT.get("execution_id")
        baseline = _ACTION_RUN_CONTEXT.get("action_local_baseline")
        campaign_modes = {"run", SELECTIVE_1H_MODE, STANDARD_FOUR_HOUR_MODE}
        from printer_v1.operator_cli.action_local_terminal_truth import (
            build_action_local_terminal_truth,
            merge_action_local_into_exception_envelope,
        )

        if args.mode in campaign_modes and (
            action_run_id is not None or action_campaign_id is not None
        ):
            try:
                mutation_recorder = _ACTION_RUN_CONTEXT.get("mutation_recorder")
                inserted_ids = None
                updated_ids = None
                auth_write_count = None
                if mutation_recorder is not None:
                    inserted_ids = mutation_recorder.inserted_row_ids()
                    updated_ids = mutation_recorder.updated_row_ids()
                    auth_write_count = mutation_recorder.authoritative_write_count()
                truth = build_action_local_terminal_truth(
                    AUTHORITATIVE_DB,
                    baseline=baseline,
                    execution_id=(
                        str(action_execution_id) if action_execution_id else None
                    ),
                    campaign_id=(
                        str(action_campaign_id) if action_campaign_id else None
                    ),
                    run_id=str(action_run_id) if action_run_id else None,
                    cycle_id=str(action_cycle_id) if action_cycle_id else None,
                    first_terminal_cause=f"{type(exc).__name__}:{exc}",
                    owner_emitted_inserted_row_ids=inserted_ids,
                    owner_emitted_updated_row_ids=updated_ids,
                    authoritative_write_count=auth_write_count,
                )
                envelope = merge_action_local_into_exception_envelope(
                    {
                        "status": "OPERATIONAL_COMMAND_BLOCKED",
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                        "mode": args.mode,
                        "action_run_id": action_run_id,
                        "scheduler_runtime_calls": 0,
                        "restart_created": False,
                        "successor_created": False,
                        "terminal_truth_status": "RECONSTRUCTED",
                        "secondary_terminal_truth_error": None,
                    },
                    truth,
                )
            except Exception as truth_exc:
                # Preserve the original campaign failure as the controlling cause.
                # A secondary terminal-truth reconstruction failure must not erase
                # it or prevent the child-owned terminal artifact from being written.
                envelope = {
                    "status": "OPERATIONAL_COMMAND_BLOCKED",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "mode": args.mode,
                    "execution_id": action_execution_id,
                    "campaign_id": action_campaign_id,
                    "action_run_id": action_run_id,
                    "cycle_id": action_cycle_id,
                    "campaign_source_calls": None,
                    "source_calls": None,
                    "scheduler_runtime_calls": None,
                    "database_writes": None,
                    "database_identity_after": None,
                    "lifecycle_started": None,
                    "cleanup_complete": None,
                    "lease_released": None,
                    "active_locked_work": None,
                    "failure_phase": (
                        "CAMPAIGN_PHASE_UNKNOWN_TERMINAL_TRUTH_RECONSTRUCTION_FAILED"
                    ),
                    "database_mutation_known": False,
                    "database_mutation_status": (
                        "UNKNOWN_TERMINAL_TRUTH_RECONSTRUCTION_FAILED"
                    ),
                    "restart_created": False,
                    "successor_created": False,
                    "terminal_truth_status": "RECONSTRUCTION_FAILED",
                    "secondary_terminal_truth_error": (
                        f"{type(truth_exc).__name__}:{truth_exc}"
                    ),
                }
        elif args.mode in campaign_modes:
            envelope = {
                "status": "OPERATIONAL_COMMAND_BLOCKED",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "mode": args.mode,
                "action_run_id": None,
                "campaign_source_calls": None,
                "source_calls": 0,
                "scheduler_runtime_calls": 0,
                "database_writes": 0,
                "database_mutation_known": True,
                "database_mutation_status": "PROVEN_ZERO_NO_CAMPAIGN_ACTION_IDENTITY",
                "restart_created": False,
                "successor_created": False,
                "terminal_truth_status": (
                    "PROVEN_ZERO_NO_CAMPAIGN_ACTION_IDENTITY"
                ),
                "secondary_terminal_truth_error": None,
            }
        else:
            envelope = {
                "status": "OPERATIONAL_COMMAND_BLOCKED",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "mode": args.mode,
                "action_run_id": action_run_id,
                "campaign_source_calls": None,
                "source_calls": 0,
                "scheduler_runtime_calls": 0,
                "database_writes": 0,
                "database_mutation_known": True,
                "database_mutation_status": "PROVEN_ZERO_NO_CAMPAIGN_ACTION_IDENTITY",
                "restart_created": False,
                "successor_created": False,
                "terminal_truth_status": (
                    "PROVEN_ZERO_NO_CAMPAIGN_ACTION_IDENTITY"
                ),
                "secondary_terminal_truth_error": None,
            }
        if args.mode in {"run", STANDARD_FOUR_HOUR_MODE} and child_terminal_binding is not None:
            try:
                write_child_terminal_envelope(
                    binding=child_terminal_binding,
                    source=envelope,
                    mode=args.mode,
                    exit_code=1,
                    success=False,
                )
            except Exception as terminal_exc:
                envelope["child_terminal_write_status"] = (
                    f"FAILED:{type(terminal_exc).__name__}"
                )
        print(json.dumps(envelope, sort_keys=True, default=str), file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "ACTIVE_INTAKE_PATH",
    "AUTHORITATIVE_DB",
    "CANDIDATE_ACQUISITION_STATE",
    "DEFERRED_CANDIDATE_ACQUISITION_MODES",
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

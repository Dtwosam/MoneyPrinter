"""Canonical acquisition-only integration for the candidate foundation.

The public operational command is the only caller.  This module owns one
finite lease, Central Scheduler work, Source-Governed adapter calls, foundation
invocation, N=2-only read-only projection, canonical reporting, and safe stop.
It never starts campaign, tracking, lifecycle, memory, retrieval, or financial
work.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Callable, Mapping, Protocol, Sequence

from printer_v1.discovery.candidate_acquisition import (
    CandidateAcquisitionError,
    build_acquisition_plan,
    legacy_two_token_runtime_projection,
    replay_candidate_acquisition_report,
    run_candidate_acquisition,
)
from printer_v1.discovery.graduated_liquidity_front_door import SELECTION_FLOOR_USD
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import (
    claim_due_job,
    complete_job,
    enqueue_job,
    fail_job,
)
from printer_v1.sources.budget_accounting import count_recent_source_requests
from printer_v1.sources.contracts import SourceRequest, build_governed_source_request
from printer_v1.sources.governed_execution import execute_source_request_with_governor


MODE_N2 = "ACQUISITION_ONLY_N2"
MODE_N7 = "ACQUISITION_ONLY_N7"
CLI_MODE_N2 = "acquisition-only-n2"
CLI_MODE_N7 = "acquisition-only-n7"
RELIABILITY_STATUS = "UNPROVEN_NO_INDEPENDENT_SAMPLE"
LEASE_SECONDS = 90
ACTIVE_CAPACITY = 2

# Candidate-acquisition operation phases. See AcquisitionSourceOperation.phase.
PHASE_NOMINATION = "NOMINATION"
PHASE_ENRICHMENT = "ENRICHMENT"

CursorNamespace = tuple[str, str, str, str, str]
CursorHead = Mapping[str, Any]

MODE_POLICIES: dict[str, dict[str, Any]] = {
    MODE_N2: {
        "selection_capacity": 2,
        "candidate_limit": 4,
        "duration_seconds": 180,
        "governed_request_ceiling": 24,
        "transport_operation_ceiling": 32,
        "byte_ceiling": 16 * 1024 * 1024,
        "row_ceiling": 64,
        "scheduler_job_ceiling": 24,
        "source_budgets": {
            "dexscreener": {"candidate_nomination": 1, "candidate_market_batch": 1},
            "geckoterminal": {"candidate_nomination": 1, "candidate_market_batch": 4},
            "solana_rpc": {
                "candidate_mint_account_batch": 1,
                "pumpfun_create_index_signature_page": 1,
                "pumpfun_create_index_transaction": 4,
                "pumpfun_migration_signature_page": 1,
                "pumpfun_migration_transaction": 4,
                "pumpswap_pool_account_batch": 1,
                "candidate_pump_migration_signature_lookup": 4,
                "candidate_pump_migration_transaction": 4,
                "candidate_pumpswap_pool_verification": 1,
                "holder_concentration_reference": 4,
            },
            "goplus": {"safety_reference": 4},
        },
    },
    MODE_N7: {
        "selection_capacity": 7,
        "candidate_limit": 14,
        "duration_seconds": 360,
        "governed_request_ceiling": 64,
        "transport_operation_ceiling": 96,
        "byte_ceiling": 32 * 1024 * 1024,
        "row_ceiling": 192,
        "scheduler_job_ceiling": 64,
        "source_budgets": {
            "dexscreener": {"candidate_nomination": 1, "candidate_market_batch": 1},
            "geckoterminal": {"candidate_nomination": 1, "candidate_market_batch": 10},
            "solana_rpc": {
                "candidate_mint_account_batch": 1,
                "pumpfun_create_index_signature_page": 2,
                "pumpfun_create_index_transaction": 10,
                "pumpfun_migration_signature_page": 2,
                "pumpfun_migration_transaction": 10,
                "pumpswap_pool_account_batch": 1,
                "candidate_pump_migration_signature_lookup": 14,
                "candidate_pump_migration_transaction": 14,
                "candidate_pumpswap_pool_verification": 1,
                "holder_concentration_reference": 14,
            },
            "goplus": {"safety_reference": 14},
        },
    },
}

PROTECTED_ZERO_DELTA_TABLES = (
    "printer_memory_factory_campaigns",
    "printer_memory_factory_campaign_runs",
    "printer_memory_factory_campaign_cycles",
    "printer_memory_factory_campaign_token_slots",
    "printer_memory_factory_campaign_windows",
    "printer_memory_factory_runs",
    "printer_memory_factory_run_steps",
    "printer_tracking_queue",
    "printer_token_snapshots",
    "printer_memory_windows",
    "printer_episodes",
    "printer_episode_outcomes",
    "printer_episode_snapshots",
    "printer_memory_fingerprints",
    "printer_memory_audit_reports",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
)

REQUIRED_SOLANA_OPERATION_KINDS = frozenset({
    "candidate_mint_account_batch",
    "pumpfun_create_index_signature_page",
    "pumpswap_pool_account_batch",
})
DECOUPLED_CANDIDATE_OPERATION_KINDS = frozenset({
    "candidate_pump_migration_signature_lookup",
    "candidate_pump_migration_transaction",
    "candidate_pumpswap_pool_verification",
})


class CandidateAcquisitionIntegrationError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}: {detail}")


def _default_operation_kinds(
    source_name: str, request_kind: str, count: int
) -> tuple[str, ...]:
    """Return the ordered predeclared low-level operation-kind plan."""
    if count < 0:
        return ()
    if request_kind == "candidate_nomination":
        return ("HTTP_GET",) * count
    if request_kind in {
        "candidate_market_batch",
    }:
        return ()
    if request_kind in {
        "pumpfun_create_index_signature_page",
        "pumpfun_migration_signature_page",
    }:
        return (
            ("getTransaction", "getSignaturesForAddress")
            if count == 2
            else ("getSignaturesForAddress",)[:count]
        )
    fixed_kind = {
        "pumpfun_create_index_transaction": "getTransaction",
        "pumpfun_migration_transaction": "getTransaction",
        "candidate_mint_account_batch": "getMultipleAccounts",
        "pumpswap_pool_account_batch": "getMultipleAccounts",
        "candidate_pump_migration_signature_lookup": "getSignaturesForAddress",
        "candidate_pump_migration_transaction": "getTransaction",
        "candidate_pumpswap_pool_verification": "getMultipleAccounts",
        "safety_reference": "HTTP_GET",
    }.get(request_kind)
    if fixed_kind is not None:
        return (fixed_kind,) * count
    if request_kind == "holder_concentration_reference":
        return ("getTokenLargestAccounts", "getTokenSupply")[:count]
    return tuple(f"UNDERLYING_OPERATION_{ordinal}" for ordinal in range(1, count + 1))


@dataclass(frozen=True)
class AcquisitionSourceOperation:
    source_name: str
    request_kind: str
    adapter: Any
    required: bool = True
    round_mode: str = "FROZEN_OFFLINE"
    request_payload: Mapping[str, Any] | None = None
    expected_transport_operations: int = 1
    expected_operation_kinds: tuple[str, ...] | None = None
    cursor_range: Mapping[str, Any] | None = None
    # Optional global coverage work persists through governed work/response
    # rows but contributes no empty failure placeholder to candidate admission.
    observation_scope: str = "CANDIDATE"
    # Phase separates the two candidate-acquisition stages. NOMINATION work
    # contributes identities to the source-neutral nomination universe from which
    # the integration owner selects the M-bounded cohort. ENRICHMENT work is
    # candidate-specific and may only touch cohort identities; the owner fails
    # closed if it observes an enrichment identity outside the selected cohort.
    phase: str = "NOMINATION"

    def __post_init__(self) -> None:
        count = int(self.expected_transport_operations)
        if count < 0:
            raise ValueError("expected_transport_operations must be non-negative")
        plan = (
            _default_operation_kinds(self.source_name, self.request_kind, count)
            if self.expected_operation_kinds is None
            else tuple(str(item) for item in self.expected_operation_kinds)
        )
        if len(plan) != count or any(not item for item in plan):
            raise ValueError("expected_operation_kinds must exactly match the declared count")
        object.__setattr__(self, "expected_operation_kinds", plan)


class AcquisitionTransportOwner(Protocol):
    def cursor_namespaces(
        self, *, mode: str, policy: Mapping[str, Any], execution_id: str
    ) -> Sequence[CursorNamespace]: ...

    def operations(
        self, *, mode: str, policy: Mapping[str, Any], execution_id: str,
        cursor_heads: Mapping[CursorNamespace, CursorHead | None] | None = None,
    ) -> Sequence[AcquisitionSourceOperation]: ...


@dataclass(frozen=True)
class FrozenAcquisitionTransportOwner:
    frozen_operations: tuple[AcquisitionSourceOperation, ...]

    def cursor_namespaces(
        self, *, mode: str, policy: Mapping[str, Any], execution_id: str
    ) -> Sequence[CursorNamespace]:
        del mode, policy, execution_id
        return ()

    def operations(
        self, *, mode: str, policy: Mapping[str, Any], execution_id: str,
        cursor_heads: Mapping[CursorNamespace, CursorHead | None] | None = None,
    ) -> Sequence[AcquisitionSourceOperation]:
        del mode, policy, execution_id, cursor_heads
        return self.frozen_operations


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    text = value if isinstance(value, str) else _canonical(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def _parse(value: str) -> datetime:
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _connect(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(Path(db_path), timeout=2.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=2000")
    return connection


def _counts(connection: sqlite3.Connection) -> dict[str, int]:
    existing = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    return {
        table: (
            int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            if table in existing
            else 0
        )
        for table in PROTECTED_ZERO_DELTA_TABLES
    }


def _preflight_hash(preflight: Mapping[str, Any], db_path: str | Path) -> str:
    required = {
        "status", "database_path", "database_sha256", "latest_migration",
        "integrity", "foreign_key_violations", "git_provenance",
    }
    missing = sorted(required - set(preflight))
    if missing:
        raise CandidateAcquisitionIntegrationError(
            "PREFLIGHT_INCOMPLETE", ",".join(missing)
        )
    if preflight["integrity"] != "ok" or int(preflight["foreign_key_violations"]) != 0:
        raise CandidateAcquisitionIntegrationError("PREFLIGHT_DATABASE_INVALID")
    if str(preflight["status"]) != "V2_9_8_OPERATIONAL_PREFLIGHT_READY":
        raise CandidateAcquisitionIntegrationError("PREFLIGHT_STATUS_NOT_READY")
    if str(preflight["latest_migration"]) != "049_candidate_acquisition_integration.sql":
        raise CandidateAcquisitionIntegrationError("PREFLIGHT_MIGRATION_049_REQUIRED")
    resolved = Path(db_path).resolve()
    if Path(str(preflight["database_path"])).resolve() != resolved:
        raise CandidateAcquisitionIntegrationError("PREFLIGHT_DATABASE_PATH_MISMATCH")
    actual_hash = hashlib.sha256(resolved.read_bytes()).hexdigest()
    if str(preflight["database_sha256"]) != actual_hash:
        raise CandidateAcquisitionIntegrationError("PREFLIGHT_DATABASE_HASH_MISMATCH")
    provenance = preflight["git_provenance"]
    if not isinstance(provenance, Mapping) or not bool(
        provenance.get("git_tracked_tree_clean")
    ):
        raise CandidateAcquisitionIntegrationError("PREFLIGHT_GIT_STATE_NOT_CLEAN")
    return _sha(preflight)


def _acquire_lease(
    db_path: str | Path,
    *,
    integration_id: str,
    execution_id: str,
    owner_id: str,
    mode: str,
    now: str,
    lease_seconds: int,
) -> str:
    lease_id = f"calease-{_sha((integration_id, owner_id))[:32]}"
    connection = _connect(db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        active = connection.execute(
            """SELECT * FROM printer_candidate_acquisition_leases
               WHERE lease_state IN ('ACTIVE','STOPPING') LIMIT 1"""
        ).fetchone()
        if active is not None:
            if _parse(active["lease_expires_at"]) > _parse(now):
                raise CandidateAcquisitionIntegrationError(
                    "ACQUISITION_LEASE_ALREADY_HELD", str(active["execution_id"])
                )
            cause = "LEASE_EXPIRED_RECOVERED"
            connection.execute(
                """UPDATE printer_candidate_acquisition_leases SET
                       lease_state='TERMINAL',terminal_status='BLOCKED',
                       first_terminal_cause=?,released_at=?,updated_at=?
                   WHERE lease_id=?""",
                (cause, now, now, active["lease_id"]),
            )
            connection.execute(
                """UPDATE printer_candidate_acquisition_integrations SET
                       integration_state='TERMINAL',terminal_status='BLOCKED',
                       first_terminal_cause=?,terminal_at=?,updated_at=?
                   WHERE integration_id=? AND integration_state<>'TERMINAL'""",
                (cause, now, now, active["integration_id"]),
            )
        expires = (_parse(now) + timedelta(seconds=lease_seconds)).isoformat()
        connection.execute(
            """INSERT INTO printer_candidate_acquisition_leases(
                   lease_id,integration_id,execution_id,owner_id,mode,lease_state,
                   heartbeat_at,lease_expires_at,created_at,updated_at
               ) VALUES (?,?,?,?,?,'ACTIVE',?,?,?,?)""",
            (lease_id, integration_id, execution_id, owner_id, mode, now, expires, now, now),
        )
        connection.execute(
            "UPDATE printer_candidate_acquisition_integrations SET "
            "integration_state='RUNNING',updated_at=? WHERE integration_id=?",
            (now, integration_id),
        )
        connection.commit()
        return lease_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def renew_candidate_acquisition_lease(
    db_path: str | Path,
    *,
    lease_id: str,
    integration_id: str,
    execution_id: str,
    owner_id: str,
    now: str,
    lease_seconds: int = LEASE_SECONDS,
) -> dict[str, Any]:
    connection = _connect(db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            """SELECT * FROM printer_candidate_acquisition_leases
               WHERE lease_id=? AND integration_id=? AND execution_id=? AND owner_id=?""",
            (lease_id, integration_id, execution_id, owner_id),
        ).fetchone()
        if row is None:
            raise CandidateAcquisitionIntegrationError("LEASE_OWNERSHIP_MISMATCH")
        if row["lease_state"] == "STOPPING":
            raise CandidateAcquisitionIntegrationError(
                "ACQUISITION_CANCELLED", str(row["cancellation_reason"] or "CANCELLED")
            )
        if row["lease_state"] != "ACTIVE":
            raise CandidateAcquisitionIntegrationError("LEASE_NOT_ACTIVE")
        if _parse(row["lease_expires_at"]) <= _parse(now):
            raise CandidateAcquisitionIntegrationError("LEASE_RENEWAL_EXPIRED")
        expires = (_parse(now) + timedelta(seconds=lease_seconds)).isoformat()
        connection.execute(
            "UPDATE printer_candidate_acquisition_leases SET heartbeat_at=?,"
            "lease_expires_at=?,updated_at=? WHERE lease_id=?",
            (now, expires, now, lease_id),
        )
        connection.commit()
        return {"renewed": True, "heartbeat_at": now, "lease_expires_at": expires}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def request_candidate_acquisition_cancellation(
    db_path: str | Path,
    *,
    execution_id: str,
    reason: str,
    now: str | None = None,
) -> dict[str, Any]:
    instant = now or _iso()
    connection = _connect(db_path)
    try:
        with connection:
            row = connection.execute(
                "SELECT * FROM printer_candidate_acquisition_leases WHERE execution_id=?",
                (execution_id,),
            ).fetchone()
            if row is None:
                raise CandidateAcquisitionIntegrationError("LEASE_NOT_FOUND")
            if row["lease_state"] == "TERMINAL":
                return {"requested": False, "already_terminal": True}
            connection.execute(
                """UPDATE printer_candidate_acquisition_leases SET
                       lease_state='STOPPING',cancellation_requested_at=?,
                       cancellation_reason=?,updated_at=? WHERE execution_id=?""",
                (instant, str(reason), instant, execution_id),
            )
            connection.execute(
                "UPDATE printer_candidate_acquisition_integrations SET "
                "integration_state='STOPPING',updated_at=? WHERE execution_id=?",
                (instant, execution_id),
            )
        return {"requested": True, "reason": str(reason)}
    finally:
        connection.close()


def _release_lease(
    db_path: str | Path,
    *,
    lease_id: str,
    integration_id: str,
    terminal_status: str,
    first_terminal_cause: str,
    now: str,
) -> dict[str, Any]:
    connection = _connect(db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT lease_state FROM printer_candidate_acquisition_leases WHERE lease_id=?",
            (lease_id,),
        ).fetchone()
        if row is None:
            raise CandidateAcquisitionIntegrationError("LEASE_NOT_FOUND")
        if row["lease_state"] != "TERMINAL":
            connection.execute(
                """UPDATE printer_candidate_acquisition_leases SET
                       lease_state='TERMINAL',terminal_status=?,first_terminal_cause=?,
                       released_at=?,updated_at=? WHERE lease_id=?""",
                (terminal_status, first_terminal_cause, now, now, lease_id),
            )
        connection.execute(
            """UPDATE printer_candidate_acquisition_integrations SET
                   integration_state='TERMINAL',terminal_status=?,first_terminal_cause=?,
                   terminal_at=?,updated_at=?
               WHERE integration_id=? AND integration_state<>'TERMINAL'""",
            (terminal_status, first_terminal_cause, now, now, integration_id),
        )
        connection.commit()
        return {"released": True, "first_terminal_cause": first_terminal_cause}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _terminalize_unleased_integration(
    db_path: str | Path,
    *,
    integration_id: str,
    terminal_status: str,
    first_terminal_cause: str,
    now: str,
) -> dict[str, Any]:
    connection = _connect(db_path)
    try:
        with connection:
            connection.execute(
                """UPDATE printer_candidate_acquisition_integrations SET
                       integration_state='TERMINAL',terminal_status=?,
                       first_terminal_cause=?,terminal_at=?,updated_at=?
                   WHERE integration_id=? AND integration_state<>'TERMINAL'""",
                (terminal_status, first_terminal_cause, now, now, integration_id),
            )
        return {
            "released": False,
            "lease_acquired": False,
            "first_terminal_cause": first_terminal_cause,
        }
    finally:
        connection.close()


def _source_status(result: Any) -> str:
    status = result.source_status
    raw = status.value if hasattr(status, "value") else str(status)
    if raw == "COMPLETE":
        return "COMPLETE"
    if raw == "STALE":
        return "STALE"
    if raw == "PARTIAL":
        return "COVERAGE_INCOMPLETE"
    return "PROVIDER_FAILURE"


def _provider_observations(
    *,
    operation: AcquisitionSourceOperation,
    normalized_result: Any,
    round_ordinal: int,
    observed_at: str,
    expires_at: str,
    transport_operations: int,
    bytes_used: int,
    duration_milliseconds: int,
) -> list[dict[str, Any]]:
    payload = dict(normalized_result.normalized_payload or {})
    status = _source_status(normalized_result)
    supplied = payload.get("candidate_observations")
    rows: list[dict[str, Any]] = []
    if isinstance(supplied, list):
        rows = [dict(item) for item in supplied if isinstance(item, Mapping)]
    elif isinstance(payload.get("pairs"), list):
        for pair in payload["pairs"]:
            if not isinstance(pair, Mapping):
                continue
            mint = (
                pair.get("candidate_mint")
                or pair.get("token_mint")
                or (pair.get("baseToken") or {}).get("address")
            )
            pool = pair.get("pair_address") or pair.get("pairAddress")
            base_mint = (
                pair.get("base_mint")
                or pair.get("baseMint")
                or (pair.get("baseToken") or {}).get("address")
            )
            quote_mint = (
                pair.get("quote_mint")
                or pair.get("quoteMint")
                or (pair.get("quoteToken") or {}).get("address")
            )
            liquidity = pair.get("liquidity_usd")
            if liquidity is None and isinstance(pair.get("liquidity"), Mapping):
                liquidity = pair["liquidity"].get("usd")
            activity = next(
                (pair.get(key) for key in ("txns_5m", "txns_1h", "volume_5m", "volume_1h")
                 if pair.get(key) is not None),
                None,
            )
            if activity is None:
                for bucket_name in ("txns", "volume"):
                    bucket = pair.get(bucket_name)
                    if not isinstance(bucket, Mapping):
                        continue
                    activity = next(
                        (bucket.get(key) for key in ("m5", "h1") if bucket.get(key) is not None),
                        None,
                    )
                    if isinstance(activity, Mapping):
                        activity = sum(
                            float(value or 0) for value in activity.values()
                            if isinstance(value, (int, float))
                        )
                    if activity is not None:
                        break
            pair_created_at = (
                pair.get("pair_created_at")
                or pair.get("pairCreatedAt")
                or pair.get("captured_at")
            )
            facts = {
                "market_status": "PASS" if status == "COMPLETE" else "FAIL",
                "age_status": "PASS" if pair_created_at else "FAIL",
                "liquidity_status": (
                    "PASS" if liquidity is not None and float(liquidity) >= SELECTION_FLOOR_USD
                    else "FAIL"
                ),
                "tradeability_status": (
                    "PASS" if activity is not None and float(activity) > 0 else "FAIL"
                ),
            }
            rows.append({
                "mint": mint,
                "pool": pool,
                "base_mint": base_mint,
                "quote_mint": quote_mint,
                "venue_label": (
                    pair.get("dex_id") or pair.get("dexId") or pair.get("dex")
                    or operation.source_name
                ),
                "lineage_claim": "UNKNOWN_ORIGIN",
                "facts": {
                    **facts,
                    "market_pair_identity_status": (
                        "PASS" if mint and pool and base_mint == mint and quote_mint
                        else "FAIL"
                    ),
                    "market_observed_base_mint": base_mint,
                    "market_observed_quote_mint": quote_mint,
                    "market_pair_orientation_reason": pair.get(
                        "candidate_pair_orientation_reason"
                    ),
                },
            })
    if not rows and operation.observation_scope == "GLOBAL_OPTIONAL":
        if status != "COMPLETE":
            return []
        rows = [{
            "facts": {
                "global_pump_observer_coverage_only": True,
                "global_pump_observer_admission_authority": "NONE",
            },
        }]
    if not rows:
        rows = [{"facts": {}}]
    output: list[dict[str, Any]] = []
    for row in rows:
        merged = {
            "round_ordinal": round_ordinal,
            "round_mode": operation.round_mode,
            "source_name": operation.source_name,
            "request_kind": operation.request_kind,
            "source_status": str(row.pop("source_status", status)),
            "failure_reason": row.pop(
                "failure_reason", normalized_result.failure_type or normalized_result.failure_message
            ),
            "observed_at": str(row.pop("observed_at", observed_at)),
            "expires_at": str(row.pop("expires_at", expires_at)),
            "governed_requests_used": 1,
            "transport_operations_used": transport_operations,
            "bytes_used": bytes_used,
            "rows_used": len(rows),
            "duration_milliseconds": duration_milliseconds,
            "cursor_range": dict(payload.get("cursor_range") or operation.cursor_range)
                if (payload.get("cursor_range") or operation.cursor_range) else None,
            **row,
        }
        output.append(merged)
    return output


def _persist_work(
    db_path: str | Path,
    *,
    integration_id: str,
    execution_id: str,
    ordinal: int,
    operation: AcquisitionSourceOperation,
    job_id: int,
    source_execution: Any,
    state: str,
    transport_operations: int,
    bytes_used: int,
    rows_used: int,
    duration_milliseconds: int,
    cause: str,
    now: str,
    underlying_operations: Sequence[Mapping[str, Any]] | None = None,
) -> None:
    work_id = f"cawork-{_sha((integration_id, ordinal))[:32]}"
    connection = _connect(db_path)
    try:
        with connection:
            connection.execute(
                """INSERT INTO printer_candidate_acquisition_work(
                       work_id,integration_id,execution_id,work_ordinal,source_name,
                       request_kind,required_source,round_mode,work_state,
                       scheduler_job_id,source_request_id,source_response_id,
                       source_failure_id,governed_requests_used,
                       transport_operations_used,bytes_used,rows_used,
                       duration_milliseconds,cursor_range_json,
                       first_terminal_cause,terminal_at,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    work_id, integration_id,
                    execution_id, ordinal, operation.source_name, operation.request_kind,
                    int(operation.required), operation.round_mode, state, job_id,
                    source_execution.request_record.id,
                    getattr(source_execution.response_record, "id", None),
                    getattr(source_execution.failure_record, "id", None), 1,
                    transport_operations, bytes_used, rows_used, duration_milliseconds,
                    (
                        _canonical(dict(operation.cursor_range))
                        if operation.cursor_range is not None else None
                    ),
                    cause, now, now, now,
                ),
            )
            details = [dict(item) for item in (underlying_operations or ())]
            if details and len(details) != transport_operations:
                raise CandidateAcquisitionIntegrationError("OPERATION_ACCOUNTING_MISMATCH")
            per_operation_bytes = bytes_used // max(transport_operations, 1)
            residual_bytes = bytes_used % max(transport_operations, 1)
            for operation_ordinal in range(1, transport_operations + 1):
                detail = details[operation_ordinal - 1] if details else {}
                connection.execute(
                    """INSERT INTO printer_candidate_acquisition_transport_operations(
                           operation_id,work_id,operation_ordinal,source_name,
                           request_kind,operation_kind,operation_state,
                           redacted_endpoint_role,bytes_used,created_at
                       ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        f"catop-{_sha((work_id, operation_ordinal))[:32]}", work_id,
                        operation_ordinal, operation.source_name, operation.request_kind,
                        str(detail.get("operation_kind") or f"UNDERLYING_OPERATION_{operation_ordinal}"),
                        str(detail.get("operation_state") or (
                            "COMPLETE" if state == "SUCCEEDED" else "FAILED")),
                        str(detail.get("redacted_endpoint_role") or "APPROVED_PRIMARY"),
                        int(detail.get("bytes_used") if "bytes_used" in detail else (
                            per_operation_bytes + (
                                residual_bytes if operation_ordinal == transport_operations else 0
                            ))),
                        now,
                    ),
                )
    finally:
        connection.close()


def _measure_operation_accounting(
    *,
    operation: AcquisitionSourceOperation,
    payload: Mapping[str, Any],
    source_complete: bool,
) -> dict[str, Any]:
    """Measure and identity-check one governed result without losing evidence."""
    plan = tuple(operation.expected_operation_kinds or ())
    expected = int(operation.expected_transport_operations)
    mismatch: str | None = None
    try:
        reported_count = int(
            payload["underlying_operation_count"]
            if "underlying_operation_count" in payload
            else expected
        )
    except (TypeError, ValueError):
        reported_count = -1
        mismatch = "OPERATION_ACCOUNTING_MISMATCH"

    raw_details = payload.get("underlying_operations")
    synthesized = raw_details is None
    details: list[dict[str, Any]] = []
    if raw_details is None:
        safe_count = max(reported_count, 0)
        for ordinal in range(safe_count):
            details.append({
                "operation_kind": (
                    plan[ordinal]
                    if ordinal < len(plan)
                    else f"UNDECLARED_OPERATION_{ordinal + 1}"
                ),
                "operation_state": "COMPLETE" if source_complete else "FAILED",
                "redacted_endpoint_role": "FROZEN_PREDECLARED_PLAN",
                "bytes_used": 0,
            })
    elif not isinstance(raw_details, list) or any(
        not isinstance(item, Mapping) for item in raw_details
    ):
        mismatch = "OPERATION_ACCOUNTING_MISMATCH"
    else:
        details = [dict(item) for item in raw_details]

    actual = len(details)
    if reported_count < 0 or reported_count != actual:
        mismatch = "OPERATION_ACCOUNTING_MISMATCH"
    declared_ceiling = bool(payload.get("declared_operation_ceiling"))
    if (
        actual > expected
        or (not declared_ceiling and actual != expected)
    ):
        mismatch = "OPERATION_ACCOUNTING_MISMATCH"

    actual_kinds: list[str] = []
    for detail in details:
        operation_kind = str(detail.get("operation_kind") or "")
        operation_state = str(detail.get("operation_state") or "")
        endpoint_role = str(detail.get("redacted_endpoint_role") or "")
        if (
            not operation_kind
            or operation_state not in {"COMPLETE", "FAILED"}
            or not endpoint_role
        ):
            mismatch = "OPERATION_ACCOUNTING_MISMATCH"
        actual_kinds.append(operation_kind)
    if tuple(actual_kinds) != plan[:actual]:
        mismatch = "OPERATION_ACCOUNTING_MISMATCH"

    try:
        encoded_size = int(
            payload["response_bytes"]
            if "response_bytes" in payload
            else sum(int(item.get("bytes_used") or 0) for item in details)
        )
    except (TypeError, ValueError):
        encoded_size = sum(
            max(0, int(item.get("bytes_used") or 0))
            for item in details
            if isinstance(item.get("bytes_used") or 0, (int, float, str))
            and str(item.get("bytes_used") or 0).lstrip("-").isdigit()
        )
        mismatch = mismatch or "OPERATION_BYTE_ACCOUNTING_MISMATCH"
    if synthesized and details and encoded_size >= 0:
        per_operation_bytes = encoded_size // actual
        residual_bytes = encoded_size % actual
        for ordinal, detail in enumerate(details, 1):
            detail["bytes_used"] = per_operation_bytes + (
                residual_bytes if ordinal == actual else 0
            )
    detail_bytes: list[int] = []
    for detail in details:
        try:
            detail_bytes.append(int(detail.get("bytes_used") or 0))
        except (TypeError, ValueError):
            detail_bytes.append(-1)
    if (
        encoded_size < 0
        or any(value < 0 for value in detail_bytes)
        or sum(detail_bytes) != encoded_size
    ):
        mismatch = mismatch or "OPERATION_BYTE_ACCOUNTING_MISMATCH"

    return {
        "reported_count": reported_count,
        "actual_count": actual,
        "encoded_size": max(encoded_size, 0),
        "details": details,
        "details_synthesized": synthesized,
        "declared_ceiling": declared_ceiling,
        "expected_kinds": plan,
        "actual_kinds": tuple(actual_kinds),
        "failure": mismatch,
    }


def _terminalize_scheduler_residue(
    db_path: str | Path, *, execution_id: str, cause: str, now: str
) -> int:
    """Fail closed any job created by this finite owner that did not terminalize."""
    connection = _connect(db_path)
    try:
        rows = connection.execute(
            """SELECT id FROM printer_scheduler_jobs
               WHERE job_name LIKE ? AND status IN ('PENDING','RUNNING','COOLDOWN')
               ORDER BY id""",
            (f"candidate-acquisition:{execution_id}:%",),
        ).fetchall()
    finally:
        connection.close()
    for row in rows:
        fail_job(
            db_path, job_id=int(row["id"]), error=cause,
            now=_parse(now), max_retries=0,
        )
    return len(rows)


def _persist_integration_report(
    db_path: str | Path,
    *,
    integration_id: str,
    execution_id: str,
    mode: str,
    manifest_id: str | None,
    report: Mapping[str, Any],
    now: str,
) -> dict[str, Any]:
    payload = dict(report)
    report_hash = _sha(payload)
    replay_identity = _sha((integration_id, execution_id, mode, manifest_id, report_hash))
    connection = _connect(db_path)
    try:
        with connection:
            connection.execute(
                """INSERT INTO printer_candidate_acquisition_integration_reports(
                       integration_id,execution_id,mode,manifest_id,report_json,
                       report_hash,replay_identity,reliability_claim_status,created_at
                   ) VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    integration_id, execution_id, mode, manifest_id, _canonical(payload),
                    report_hash, replay_identity, RELIABILITY_STATUS, now,
                ),
            )
        return payload
    finally:
        connection.close()


def replay_candidate_acquisition_integration_report(
    db_path: str | Path, *, execution_id: str
) -> dict[str, Any]:
    uri = f"file:{Path(db_path).resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM printer_candidate_acquisition_integration_reports WHERE execution_id=?",
            (execution_id,),
        ).fetchone()
        if row is None:
            raise CandidateAcquisitionIntegrationError("INTEGRATION_REPORT_NOT_FOUND")
        payload = json.loads(row["report_json"])
        if _sha(payload) != row["report_hash"]:
            raise CandidateAcquisitionIntegrationError("INTEGRATION_REPORT_HASH_MISMATCH")
        integration = connection.execute(
            "SELECT mode,manifest_id,integration_state FROM printer_candidate_acquisition_integrations "
            "WHERE execution_id=?",
            (execution_id,),
        ).fetchone()
        if integration is None or integration["integration_state"] != "TERMINAL":
            raise CandidateAcquisitionIntegrationError("INTEGRATION_REPLAY_IDENTITY_MISMATCH")
        expected = _sha((
            row["integration_id"], execution_id, integration["mode"],
            integration["manifest_id"], row["report_hash"],
        ))
        if expected != row["replay_identity"]:
            raise CandidateAcquisitionIntegrationError("INTEGRATION_REPLAY_IDENTITY_MISMATCH")
    finally:
        connection.close()
    if payload.get("foundation_execution_id"):
        replay_candidate_acquisition_report(db_path, str(payload["foundation_execution_id"]))
    return payload


def _load_exact_cursor_heads(
    db_path: str | Path,
    *,
    namespaces: Sequence[CursorNamespace],
) -> dict[CursorNamespace, dict[str, Any] | None]:
    """Hydrate exact heads under the acquisition lease before transport work.

    BEGIN IMMEDIATE gives the read a stable short transaction. The separately
    held acquisition lease is the logical lock across later source I/O; the
    foundation performs the authoritative exact-head recheck before committing.
    """
    unique = tuple(dict.fromkeys(namespaces))
    heads: dict[CursorNamespace, dict[str, Any] | None] = {}
    connection = _connect(db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        for namespace in unique:
            if (
                len(namespace) != 5
                or any(not isinstance(value, str) or not value for value in namespace)
                or namespace[4] not in {"FORWARD", "BACKWARD"}
            ):
                raise CandidateAcquisitionIntegrationError(
                    "CURSOR_NAMESPACE_MALFORMED"
                )
            row = connection.execute(
                """SELECT boundary_slot,boundary_signature,last_range_id,
                          last_execution_id,cursor_version,updated_at
                   FROM printer_candidate_acquisition_cursors
                   WHERE network=? AND indexed_address=? AND contract_pin=?
                     AND decoder_version=? AND direction=?""",
                namespace,
            ).fetchone()
            if row is None:
                exact_range = connection.execute(
                    """SELECT 1 FROM printer_candidate_cursor_ranges
                       WHERE network=? AND indexed_address=? AND contract_pin=?
                         AND decoder_version=? AND direction=?
                         AND cursor_advanced=1 LIMIT 1""",
                    namespace,
                ).fetchone()
                mismatched_identity = connection.execute(
                    """SELECT 1 FROM printer_candidate_acquisition_cursors
                       WHERE indexed_address=? AND direction=?
                         AND (network<>? OR contract_pin<>? OR decoder_version<>?)
                       LIMIT 1""",
                    (
                        namespace[1], namespace[4], namespace[0], namespace[2],
                        namespace[3],
                    ),
                ).fetchone()
                if mismatched_identity is not None:
                    raise CandidateAcquisitionIntegrationError(
                        "CURSOR_NAMESPACE_MISMATCH", namespace[1]
                    )
                if exact_range is not None:
                    raise CandidateAcquisitionIntegrationError(
                        "CURSOR_DURABLE_HEAD_MISSING", namespace[1]
                    )
                heads[namespace] = None
                continue
            slot, signature = row["boundary_slot"], row["boundary_signature"]
            if (
                type(slot) is not int
                or slot < 0
                or not isinstance(signature, str)
                or not signature
            ):
                raise CandidateAcquisitionIntegrationError(
                    "CURSOR_DURABLE_HEAD_INCOMPLETE", namespace[1]
                )
            heads[namespace] = {
                "network": namespace[0],
                "indexed_address": namespace[1],
                "contract_pin": namespace[2],
                "decoder_version": namespace[3],
                "direction": namespace[4],
                "boundary_slot": slot,
                "boundary_signature": signature,
                "last_range_id": str(row["last_range_id"]),
                "last_execution_id": str(row["last_execution_id"]),
                "cursor_version": int(row["cursor_version"]),
                "updated_at": str(row["updated_at"]),
            }
        present = [namespace for namespace, head in heads.items() if head is not None]
        missing = [namespace for namespace, head in heads.items() if head is None]
        if present and missing:
            raise CandidateAcquisitionIntegrationError(
                "CURSOR_DURABLE_HEAD_MISSING", missing[0][1]
            )
        connection.commit()
    finally:
        connection.close()
    return heads


def run_candidate_acquisition_integration(
    db_path: str | Path,
    *,
    mode: str,
    operator_approved: bool,
    transport_owner: AcquisitionTransportOwner,
    preflight: Mapping[str, Any],
    execution_id: str,
    owner_id: str,
    now: str,
    lease_seconds: int = LEASE_SECONDS,
    renewal_hook: Callable[[int], None] | None = None,
    cancellation_probe: Callable[[int], str | None] | None = None,
) -> dict[str, Any]:
    """Run one canonical finite acquisition-only execution."""
    if not operator_approved:
        raise CandidateAcquisitionIntegrationError("EXPLICIT_OPERATOR_APPROVAL_REQUIRED")
    if mode not in MODE_POLICIES:
        raise CandidateAcquisitionIntegrationError("UNSUPPORTED_ACQUISITION_ONLY_MODE")
    policy = dict(MODE_POLICIES[mode])
    preflight_hash = _preflight_hash(preflight, db_path)
    integration_id = f"cain-{_sha((execution_id, mode))[:32]}"

    connection = _connect(db_path)
    try:
        prior = connection.execute(
            "SELECT 1 FROM printer_candidate_acquisition_integration_reports WHERE execution_id=?",
            (execution_id,),
        ).fetchone()
        if prior is not None:
            return replay_candidate_acquisition_integration_report(
                db_path, execution_id=execution_id
            )
        before = _counts(connection)
        with connection:
            connection.execute(
                """INSERT INTO printer_candidate_acquisition_integrations(
                       integration_id,execution_id,mode,selection_capacity,owner_id,
                       authorization_confirmed,preflight_hash,policy_json,
                       integration_state,started_at,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,'AUTHORIZED',?,?,?)""",
                (
                    integration_id, execution_id, mode, policy["selection_capacity"],
                    owner_id, 1, preflight_hash, _canonical(policy), now, now, now,
                ),
            )
    finally:
        connection.close()

    lease_id: str | None = None
    observations: list[dict[str, Any]] = []
    scheduler_jobs = governed_requests = governed_responses = governed_failures = 0
    transport_operations = bytes_used = rows_used = duration_milliseconds = 0
    operation_identity_reconciled_work_items = 0
    operation_identity_mismatch_work_items = 0
    synthesized_operation_detail_work_items = 0
    foundation: dict[str, Any] | None = None
    projection: tuple[dict[str, Any], dict[str, Any]] | None = None
    terminal_status = "FAILED"
    first_cause = "INTEGRATION_FAILED"
    failure_detail: str | None = None
    started = time.monotonic()
    candidate_limit = int(policy["candidate_limit"])
    # Source-neutral nomination universe and cohort accounting. NOMINATION-phase
    # identities compete for the M-bounded cohort; ENRICHMENT-phase identities
    # must be a subset of the selected cohort or the owner fails closed.
    nomination_source_by_mint: dict[str, set[str]] = {}
    nomination_rows_by_source: Counter[str] = Counter()
    enrichment_mints: set[str] = set()
    cohort_mints: list[str] = []
    thinned_beyond_cohort = 0
    proposed_cursor_namespaces: set[CursorNamespace] = set()
    cursor_heads: dict[CursorNamespace, dict[str, Any] | None] = {}
    global_observer_states: list[str] = []
    operations: tuple[AcquisitionSourceOperation, ...] = ()
    try:
        lease_id = _acquire_lease(
            db_path, integration_id=integration_id, execution_id=execution_id,
            owner_id=owner_id, mode=mode, now=now, lease_seconds=lease_seconds,
        )
        namespaces = tuple(
            transport_owner.cursor_namespaces(
                mode=mode, policy=policy, execution_id=execution_id
            )
        )
        cursor_heads = _load_exact_cursor_heads(
            db_path, namespaces=namespaces
        )
        operations = tuple(
            transport_owner.operations(
                mode=mode, policy=policy, execution_id=execution_id,
                cursor_heads=cursor_heads,
            )
        )
        declared = {(item.source_name, item.request_kind) for item in operations}
        if not any(
            (source, "candidate_nomination") in declared
            for source in ("dexscreener", "geckoterminal")
        ):
            raise CandidateAcquisitionIntegrationError("NOMINATION_SOURCE_GROUP_MISSING")
        missing_solana = sorted(
            kind for kind in (
                REQUIRED_SOLANA_OPERATION_KINDS
                | (
                    DECOUPLED_CANDIDATE_OPERATION_KINDS
                    if bool(getattr(
                        transport_owner,
                        "decoupled_candidate_migration_plan",
                        False,
                    ))
                    else frozenset()
                )
            )
            if ("solana_rpc", kind) not in declared
        )
        if missing_solana:
            raise CandidateAcquisitionIntegrationError(
                "REQUIRED_SOURCE_PLAN_INCOMPLETE", ",".join(missing_solana)
            )
        if len(operations) > int(policy["scheduler_job_ceiling"]):
            raise CandidateAcquisitionIntegrationError("SCHEDULER_JOB_CEILING")
        expires_at = (_parse(now) + timedelta(seconds=180)).isoformat()
        required_failures: list[str] = []
        nomination_successes = 0
        for ordinal, operation in enumerate(operations, 1):
            if renewal_hook is not None:
                renewal_hook(ordinal)
            if cancellation_probe is not None:
                reason = cancellation_probe(ordinal)
                if reason:
                    request_candidate_acquisition_cancellation(
                        db_path, execution_id=execution_id, reason=reason, now=now
                    )
            renew_candidate_acquisition_lease(
                db_path, lease_id=lease_id, integration_id=integration_id,
                execution_id=execution_id, owner_id=owner_id, now=now,
                lease_seconds=lease_seconds,
            )
            if time.monotonic() - started > float(policy["duration_seconds"]):
                raise CandidateAcquisitionIntegrationError("DURATION_CEILING")
            request_budget = policy["source_budgets"].get(operation.source_name, {}).get(
                operation.request_kind
            )
            used_kind = sum(
                1 for prior_op in operations[: ordinal - 1]
                if prior_op.source_name == operation.source_name
                and prior_op.request_kind == operation.request_kind
            )
            if not isinstance(request_budget, int) or used_kind >= request_budget:
                raise CandidateAcquisitionIntegrationError(
                    "SOURCE_REQUEST_BUDGET_EXHAUSTED",
                    f"{operation.source_name}:{operation.request_kind}",
                )
            if governed_requests + 1 > int(policy["governed_request_ceiling"]):
                raise CandidateAcquisitionIntegrationError("GOVERNED_REQUEST_CEILING")
            if transport_operations + int(operation.expected_transport_operations) > int(
                policy["transport_operation_ceiling"]
            ):
                raise CandidateAcquisitionIntegrationError("TRANSPORT_OPERATION_CEILING")
            request: SourceRequest = build_governed_source_request(
                operation.source_name,
                operation.request_kind,
                request_key=f"{execution_id}:{ordinal}",
                tracking_priority=0,
                payload=dict(operation.request_payload or {}),
                now=_parse(now),
            )
            result, job_id = enqueue_job(
                db_path,
                job_name=f"candidate-acquisition:{execution_id}:{ordinal}",
                job_kind=JobKind.DISCOVERY_REFRESH,
                target_table="printer_candidate_acquisition_integrations",
                target_id=ordinal,
                scheduled_for=_parse(now),
                source_name=operation.source_name,
                source_request_kind=operation.request_kind,
                recent_request_count=count_recent_source_requests(
                    db_path, operation.source_name, now=_parse(now)
                ),
            )
            if result is not LockResult.ACQUIRED or job_id is None:
                raise CandidateAcquisitionIntegrationError(
                    "SCHEDULER_ENQUEUE_BLOCKED", result.value
                )
            scheduler_jobs += 1
            if claim_due_job(
                db_path, job_id=job_id, lock_owner=owner_id, now=_parse(now)
            ) is not LockResult.ACQUIRED:
                raise CandidateAcquisitionIntegrationError("SCHEDULER_CLAIM_BLOCKED")
            op_started = time.monotonic()
            source_execution = execute_source_request_with_governor(
                db_path,
                request,
                operation.adapter,
                recent_request_count=count_recent_source_requests(
                    db_path, operation.source_name, now=_parse(now)
                ),
                now=_parse(now),
            )
            # Re-read cancellation/lease state immediately after the transport
            # and before accepting, recording, or composing its evidence.
            renew_candidate_acquisition_lease(
                db_path, lease_id=lease_id, integration_id=integration_id,
                execution_id=execution_id, owner_id=owner_id, now=now,
                lease_seconds=lease_seconds,
            )
            elapsed_ms = int((time.monotonic() - op_started) * 1000)
            normalized = source_execution.normalized_result
            payload = dict(normalized.normalized_payload or {})
            healthy = _source_status(normalized) == "COMPLETE"
            governed_requests += 1
            if getattr(source_execution, "response_record", None) is not None:
                governed_responses += 1
            if getattr(source_execution, "failure_record", None) is not None:
                governed_failures += 1
            accounting = _measure_operation_accounting(
                operation=operation,
                payload=payload,
                source_complete=healthy,
            )
            actual_operations = int(accounting["actual_count"])
            encoded_size = int(accounting["encoded_size"])
            underlying_details = list(accounting["details"])
            if bool(accounting["details_synthesized"]):
                synthesized_operation_detail_work_items += 1
            candidate_rows = _provider_observations(
                operation=operation, normalized_result=normalized,
                round_ordinal=ordinal, observed_at=now, expires_at=expires_at,
                transport_operations=actual_operations, bytes_used=encoded_size,
                duration_milliseconds=elapsed_ms,
            )
            boundary_failure = accounting["failure"]
            if (
                boundary_failure is None
                and transport_operations + actual_operations
                > int(policy["transport_operation_ceiling"])
            ):
                boundary_failure = "TRANSPORT_OPERATION_CEILING"
            if (
                boundary_failure is None
                and rows_used + len(candidate_rows) > int(policy["row_ceiling"])
            ):
                boundary_failure = "OBSERVATION_ROW_CEILING"
            if (
                boundary_failure is None
                and bytes_used + encoded_size > int(policy["byte_ceiling"])
            ):
                boundary_failure = "RESPONSE_BYTE_CEILING"
            if boundary_failure is not None:
                boundary_failure = str(boundary_failure)
                fail_job(
                    db_path, job_id=job_id, error=boundary_failure,
                    now=_parse(now), max_retries=0,
                )
                _persist_work(
                    db_path, integration_id=integration_id,
                    execution_id=execution_id, ordinal=ordinal,
                    operation=operation, job_id=job_id,
                    source_execution=source_execution, state="FAILED",
                    transport_operations=actual_operations,
                    bytes_used=encoded_size, rows_used=len(candidate_rows),
                    duration_milliseconds=elapsed_ms,
                    cause=boundary_failure, now=now,
                    underlying_operations=underlying_details,
                )
                transport_operations += actual_operations
                bytes_used += encoded_size
                rows_used += len(candidate_rows)
                duration_milliseconds += elapsed_ms
                if boundary_failure in {
                    "OPERATION_ACCOUNTING_MISMATCH",
                    "OPERATION_BYTE_ACCOUNTING_MISMATCH",
                }:
                    operation_identity_mismatch_work_items += 1
                else:
                    operation_identity_reconciled_work_items += 1
                raise CandidateAcquisitionIntegrationError(boundary_failure)
            operation_identity_reconciled_work_items += 1
            if operation.request_kind in {
                "pumpfun_migration_signature_page",
                "pumpfun_migration_transaction",
            }:
                if not healthy:
                    observer_failure = str(
                        normalized.failure_type or ""
                    ).lower()
                    global_observer_states.append(
                        "GLOBAL_PUMP_OBSERVER_BLOCKED_CONTRACT"
                        if "contract" in observer_failure
                        or "unsupported" in observer_failure
                        else "GLOBAL_PUMP_OBSERVER_GAPPED"
                        if "null_or_pruned" in observer_failure
                        or "coverage" in observer_failure
                        else "GLOBAL_PUMP_OBSERVER_PROVIDER_UNAVAILABLE"
                    )
                else:
                    observer_cursor_state = str(
                        (payload.get("cursor_range") or operation.cursor_range or {}).get(
                            "continuity_state"
                        ) or "UNKNOWN"
                    )
                    global_observer_states.append({
                        "CONTIGUOUS": "GLOBAL_PUMP_OBSERVER_CONTIGUOUS",
                        "GAPPED": "GLOBAL_PUMP_OBSERVER_GAPPED",
                        "BLOCKED_CONTRACT": "GLOBAL_PUMP_OBSERVER_BLOCKED_CONTRACT",
                    }.get(
                        observer_cursor_state,
                        "GLOBAL_PUMP_OBSERVER_UNKNOWN",
                    ))
            if healthy and operation.request_kind == "candidate_nomination":
                nomination_successes += 1
            cursor_state = str(
                (operation.cursor_range or {}).get("continuity_state") or ""
            )
            if operation.required and cursor_state in {
                "GAPPED", "UNKNOWN", "BLOCKED_CONTRACT",
            }:
                cursor_reason = str(
                    (operation.cursor_range or {}).get("unresolved_reason") or ""
                )
                required_failures.append(
                    "UNSUPPORTED_CONTRACT"
                    if cursor_state == "BLOCKED_CONTRACT"
                    else "CURSOR_PRIOR_BOUNDARY_UNREACHABLE"
                    if cursor_reason == "CURSOR_PRIOR_BOUNDARY_UNREACHABLE"
                    else "CURSOR_CONTINUITY_GAPPED"
                )
            if operation.required and not healthy:
                subtype = str(
                    normalized.failure_type or _source_status(normalized)
                ).lower()
                if "unsupported" in subtype or "contract" in subtype:
                    required_failures.append("UNSUPPORTED_CONTRACT")
                elif _source_status(normalized) == "STALE":
                    required_failures.append("STALE_OR_INCOMPLETE_EVIDENCE")
                else:
                    required_failures.append("REQUIRED_SOURCE_FAILURE")
            if healthy:
                complete_job(db_path, job_id=job_id, now=_parse(now))
                work_state, work_cause = "SUCCEEDED", "SOURCE_OPERATION_COMPLETE"
            else:
                fail_job(
                    db_path, job_id=job_id,
                    error=str(normalized.failure_type or _source_status(normalized)),
                    now=_parse(now), max_retries=0,
                )
                work_state, work_cause = "FAILED", str(
                    normalized.failure_type or _source_status(normalized)
                )
            _persist_work(
                db_path, integration_id=integration_id, execution_id=execution_id,
                ordinal=ordinal, operation=operation, job_id=job_id,
                source_execution=source_execution, state=work_state,
                transport_operations=actual_operations, bytes_used=encoded_size,
                rows_used=len(candidate_rows), duration_milliseconds=elapsed_ms,
                cause=work_cause, now=now,
                underlying_operations=underlying_details,
            )
            transport_operations += actual_operations
            bytes_used += encoded_size
            rows_used += len(candidate_rows)
            duration_milliseconds += elapsed_ms
            observations.extend(candidate_rows)
            is_enrichment = operation.phase == PHASE_ENRICHMENT
            for row in candidate_rows:
                mint = row.get("mint")
                if not mint:
                    continue
                if is_enrichment:
                    enrichment_mints.add(str(mint))
                else:
                    nomination_source_by_mint.setdefault(str(mint), set()).add(
                        operation.source_name
                    )
                    nomination_rows_by_source[operation.source_name] += 1
            proposed_cursor = payload.get("cursor_range") or operation.cursor_range
            if isinstance(proposed_cursor, Mapping) and bool(
                proposed_cursor.get("cursor_advanced")
            ):
                proposed_cursor_namespaces.add((
                    "solana-mainnet",
                    str(proposed_cursor.get("indexed_address") or ""),
                    str(proposed_cursor.get("contract_pin") or ""),
                    str(proposed_cursor.get("decoder_version") or ""),
                    str(proposed_cursor.get("direction") or ""),
                ))

        # Work rows retain each page's immutable intermediate cursor evidence.
        # Foundation input, however, receives exactly one terminal range per
        # namespace so UNKNOWN page snapshots cannot conflict with the final
        # bounded range or advance one head more than once.
        terminal_cursor_ranges: dict[CursorNamespace, dict[str, Any]] = {}
        for operation in operations:
            cursor = operation.cursor_range
            if not isinstance(cursor, Mapping):
                continue
            namespace = (
                "solana-mainnet", str(cursor.get("indexed_address") or ""),
                str(cursor.get("contract_pin") or ""),
                str(cursor.get("decoder_version") or ""),
                str(cursor.get("direction") or ""),
            )
            terminal_cursor_ranges[namespace] = dict(cursor)
        for row in observations:
            cursor = row.get("cursor_range")
            if not isinstance(cursor, Mapping):
                continue
            namespace = (
                "solana-mainnet", str(cursor.get("indexed_address") or ""),
                str(cursor.get("contract_pin") or ""),
                str(cursor.get("decoder_version") or ""),
                str(cursor.get("direction") or ""),
            )
            if namespace in terminal_cursor_ranges:
                row["cursor_range"] = dict(terminal_cursor_ranges[namespace])

        if nomination_successes < 1:
            raise CandidateAcquisitionIntegrationError(
                "NOMINATION_SOURCE_GROUP_FAILURE"
            )
        if required_failures:
            precedence = (
                "UNSUPPORTED_CONTRACT", "CURSOR_PRIOR_BOUNDARY_UNREACHABLE",
                "REQUIRED_SOURCE_FAILURE",
                "CURSOR_CONTINUITY_GAPPED", "STALE_OR_INCOMPLETE_EVIDENCE",
            )
            cause = next(
                item for item in precedence if item in set(required_failures)
            )
            raise CandidateAcquisitionIntegrationError(cause)
        # Source-neutral, provider-order-independent cohort selection. The raw
        # nomination universe may legitimately exceed M; that is thinned to an
        # M-bounded cohort by a deterministic identity order (never a source
        # quota, preference, score, rank, confidence, or weighting), NOT a
        # terminal failure. M bounds the candidates that enter the expensive
        # admission funnel and receive candidate-specific enrichment.
        nomination_universe = sorted(nomination_source_by_mint)
        cohort_mints = nomination_universe[:candidate_limit]
        cohort_set = set(cohort_mints)
        thinned_beyond_cohort = len(nomination_universe) - len(cohort_mints)
        # Candidate-specific enrichment may only touch cohort identities; an
        # enrichment observation for an out-of-cohort identity means the plan
        # bound expensive work before or beyond the cohort — fail closed.
        out_of_cohort = sorted(enrichment_mints - cohort_set)
        if out_of_cohort:
            raise CandidateAcquisitionIntegrationError(
                "OUT_OF_COHORT_ENRICHMENT", ",".join(out_of_cohort)[:200]
            )
        observations = [
            row for row in observations
            if not row.get("mint") or str(row.get("mint")) in cohort_set
        ]
        post_cohort_unique = {
            str(row.get("mint")) for row in observations if row.get("mint")
        }
        # Defensive: the deterministic bound must hold post-filter. Actual
        # overflow past M through the admission funnel fails closed.
        if len(post_cohort_unique) > candidate_limit:
            raise CandidateAcquisitionIntegrationError(
                "CANDIDATE_COHORT_OVERFLOW",
                f"{len(post_cohort_unique)}>{candidate_limit}",
            )
        allowed_sources = tuple(sorted({op.source_name for op in operations}))
        if not allowed_sources:
            raise CandidateAcquisitionIntegrationError("EMPTY_SOURCE_PLAN")
        plan = build_acquisition_plan(
            selection_capacity=int(policy["selection_capacity"]),
            execution_id=execution_id,
            selection_seed=f"{mode}:{execution_id}",
            window_start=now,
            window_end=now,
            cutoff_at=now,
            finalized_cutoff_slot=0,
            git_provenance=str(
                (preflight.get("git_provenance") or {}).get("git_head")
                or preflight.get("git_provenance")
            ),
            source_budgets=policy["source_budgets"],
            allowed_sources=allowed_sources,
        )
        renew_candidate_acquisition_lease(
            db_path, lease_id=lease_id, integration_id=integration_id,
            execution_id=execution_id, owner_id=owner_id, now=now,
            lease_seconds=lease_seconds,
        )
        foundation = run_candidate_acquisition(
            db_path, plan=plan, observations=observations
        )
        manifest_id = foundation.get("manifest_id")
        if mode == MODE_N2 and manifest_id:
            projection = legacy_two_token_runtime_projection(db_path, str(manifest_id))
        elif mode == MODE_N7 and manifest_id:
            projection = None
        if foundation["verdict"] == "EXACT_N_MANIFEST_READY":
            terminal_status = "COMPLETED"
            first_cause = "ACQUISITION_ONLY_COMPLETE"
        else:
            terminal_status = "BLOCKED"
            first_cause = str(foundation.get("failure_family") or "ACQUISITION_NOT_READY")
    except CandidateAcquisitionIntegrationError as exc:
        first_cause = exc.code
        failure_detail = exc.detail or str(exc)
        terminal_status = "CANCELLED" if exc.code == "ACQUISITION_CANCELLED" else "BLOCKED"
    except CandidateAcquisitionError as exc:
        first_cause = exc.code
        failure_detail = exc.detail or str(exc)
        terminal_status = "BLOCKED"
    except Exception as exc:
        first_cause = "INTEGRATION_EXCEPTION"
        failure_detail = f"{type(exc).__name__}:{exc}"
        terminal_status = "FAILED"

    scheduler_residue_terminalized = _terminalize_scheduler_residue(
        db_path, execution_id=execution_id, cause=first_cause, now=now
    )
    projection_count = len(projection or ())
    manifest_id = None if foundation is None else foundation.get("manifest_id")
    connection = _connect(db_path)
    try:
        with connection:
            connection.execute(
                """UPDATE printer_candidate_acquisition_integrations SET
                       foundation_execution_id=?,manifest_id=?,projection_count=?,
                       scheduler_jobs_created=?,governed_requests_used=?,
                       transport_operations_used=?,bytes_used=?,rows_used=?,updated_at=?
                   WHERE integration_id=?""",
                (
                    execution_id if foundation is not None else None, manifest_id,
                    projection_count, scheduler_jobs, governed_requests,
                    transport_operations, bytes_used, rows_used, now, integration_id,
                ),
            )
    finally:
        connection.close()
    connection = _connect(db_path)
    try:
        after = _counts(connection)
        integrity = tuple(str(row[0]) for row in connection.execute("PRAGMA integrity_check"))
        fk = connection.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        connection.close()
    deltas = {table: after[table] - before[table] for table in before}
    if any(deltas.values()):
        terminal_status = "FAILED"
        first_cause = "FORBIDDEN_TABLE_DELTA"
    if integrity != ("ok",) or fk:
        terminal_status = "FAILED"
        first_cause = "DATABASE_INTEGRITY_FAILURE"
    cleanup = (
        _release_lease(
            db_path, lease_id=lease_id, integration_id=integration_id,
            terminal_status=terminal_status, first_terminal_cause=first_cause, now=now,
        )
        if lease_id is not None
        else _terminalize_unleased_integration(
            db_path, integration_id=integration_id,
            terminal_status=terminal_status, first_terminal_cause=first_cause, now=now,
        )
    )
    connection = _connect(db_path)
    try:
        active_leases = int(connection.execute(
            "SELECT COUNT(*) FROM printer_candidate_acquisition_leases "
            "WHERE lease_state IN ('ACTIVE','STOPPING')"
        ).fetchone()[0])
        # Committed cursor movement is distinct from proposed movement: a durable
        # head only advances inside the foundation transaction, so a pre-foundation
        # stop can carry proposed advances with zero committed advances.
        cursor_advances_committed = (
            int(connection.execute(
                "SELECT COUNT(*) FROM printer_candidate_acquisition_cursors "
                "WHERE last_execution_id=?",
                (execution_id,),
            ).fetchone()[0])
            if foundation is not None else 0
        )
    finally:
        connection.close()
    cross_source_overlap_count = sum(
        1 for sources in nomination_source_by_mint.values() if len(sources) > 1
    )
    pre_foundation_funnel = {
        "raw_observation_rows": rows_used,
        "raw_unique_nominations": len(nomination_source_by_mint),
        "nomination_rows_by_source": dict(sorted(nomination_rows_by_source.items())),
        "nominating_source_count_by_identity": {
            mint: len(sources)
            for mint, sources in sorted(nomination_source_by_mint.items())
        },
        "cross_source_overlap_count": cross_source_overlap_count,
        "candidate_cohort_bound_m": candidate_limit,
        "candidate_cohort_size": len(cohort_mints),
        "thinned_beyond_cohort": thinned_beyond_cohort,
        "enrichment_identities": len(enrichment_mints),
        "out_of_cohort_enrichment": len(enrichment_mints - set(cohort_mints)),
    }
    observer_precedence = (
        "GLOBAL_PUMP_OBSERVER_BLOCKED_CONTRACT",
        "GLOBAL_PUMP_OBSERVER_PROVIDER_UNAVAILABLE",
        "GLOBAL_PUMP_OBSERVER_GAPPED",
        "GLOBAL_PUMP_OBSERVER_UNKNOWN",
        "GLOBAL_PUMP_OBSERVER_CONTIGUOUS",
    )
    global_observer_status = next(
        (
            status for status in observer_precedence
            if status in set(global_observer_states)
        ),
        "GLOBAL_PUMP_OBSERVER_NOT_RUN",
    )
    report = {
        "mode": mode,
        "integration_id": integration_id,
        "execution_id": execution_id,
        "status": terminal_status,
        "first_terminal_cause": first_cause,
        "failure_detail": failure_detail,
        "preflight_hash": preflight_hash,
        "policy": policy,
        "scheduler_owner": "Central Scheduler",
        "scheduler_job_kind": JobKind.DISCOVERY_REFRESH.value,
        "scheduler_jobs_created": scheduler_jobs,
        "scheduler_residue_terminalized": scheduler_residue_terminalized,
        "source_governor_owner": "Source Governor",
        "governed_requests_used": governed_requests,
        "governed_responses": governed_responses,
        "governed_failures": governed_failures,
        "transport_operations_used": transport_operations,
        "bytes_used": bytes_used,
        "rows_used": rows_used,
        "duration_milliseconds": duration_milliseconds,
        "operation_accounting": {
            "identity_key": (
                "source_name/request_kind/work_ordinal/"
                "transport_ordinal/operation_kind"
            ),
            "predeclared_work_items": scheduler_jobs,
            "identity_reconciled_work_items": (
                operation_identity_reconciled_work_items
            ),
            "identity_mismatch_work_items": (
                operation_identity_mismatch_work_items
            ),
            "frozen_synthesized_detail_work_items": (
                synthesized_operation_detail_work_items
            ),
            "predeclared_plans": [
                {
                    "work_ordinal": ordinal,
                    "source_name": operation.source_name,
                    "request_kind": operation.request_kind,
                    "declared_operation_ceiling": int(
                        operation.expected_transport_operations
                    ),
                    "operation_kinds": list(
                        operation.expected_operation_kinds or ()
                    ),
                }
                for ordinal, operation in enumerate(operations, 1)
            ],
        },
        "pre_foundation_funnel": pre_foundation_funnel,
        "cursor_namespaces_declared": len(cursor_heads),
        "cursor_heads_loaded": sum(
            1 for head in cursor_heads.values() if head is not None
        ),
        "cursor_bootstrap_namespaces": sum(
            1 for head in cursor_heads.values() if head is None
        ),
        "cursor_advances_proposed": len(proposed_cursor_namespaces),
        "cursor_advances_committed": cursor_advances_committed,
        "optional_global_pump_observer": {
            "observer_status": global_observer_status,
            "required": False,
            "admission_authority": "NONE",
            "universal_failure_contribution": False,
            "historical_gap": {
                "observer_status": "OPTIONAL_OBSERVER_GAPPED",
                "authoritative_head_slot": 435985595,
                "frozen_tip_slot": 435999023,
                "last_recovery_continuation_slot": 435998983,
                "signatures_inspected": 11000,
                "pages_inspected": 44,
                "exact_prior_boundary_reached": False,
                "terminal_reason": "CURSOR_RECOVERY_LANE_BOUND_EXHAUSTED",
                "admission_authority": "NONE",
                "cursor_mutation_performed": False,
            },
        },
        "foundation_execution_id": execution_id if foundation is not None else None,
        "foundation_report": foundation,
        "manifest_id": manifest_id,
        "manifest_hash": None if foundation is None else foundation.get("manifest_hash"),
        "selected_count": 0 if foundation is None else foundation.get("selected_count", 0),
        "projection_count": projection_count,
        "projection_hash": _sha(projection) if projection else None,
        "runtime_handoff_count": 0,
        "lifecycle_started": False,
        "active_capacity_lock": ACTIVE_CAPACITY,
        "lease_cleanup": cleanup,
        "active_lease_count": active_leases,
        "automatic_retry_created": False,
        "successor_created": False,
        "restart_created": False,
        "forbidden_table_deltas": deltas,
        "integrity": "ok" if integrity == ("ok",) else list(integrity),
        "foreign_key_violations": len(fk),
        "reliability_claim_status": RELIABILITY_STATUS,
    }
    return _persist_integration_report(
        db_path, integration_id=integration_id, execution_id=execution_id,
        mode=mode, manifest_id=manifest_id, report=report, now=now,
    )


__all__ = [
    "MODE_N2", "MODE_N7", "CLI_MODE_N2", "CLI_MODE_N7", "MODE_POLICIES",
    "AcquisitionSourceOperation", "FrozenAcquisitionTransportOwner",
    "CandidateAcquisitionIntegrationError", "run_candidate_acquisition_integration",
    "replay_candidate_acquisition_integration_report",
    "renew_candidate_acquisition_lease", "request_candidate_acquisition_cancellation",
]

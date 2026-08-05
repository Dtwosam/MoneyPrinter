"""E.22 pre-activation holder reliability and campaign budget control.

This owner performs no network I/O. It owns deterministic admission, durable
pre-slot scheduling/provenance, and exact evidence reuse around the existing
Source-Governed holder adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import sqlite3
import time
from typing import Any, Mapping, Sequence

from printer_v1.sources.registry import SOURCE_REGISTRY


OPERATION_CEILING = 45
REQUIRED_DEX_SNAPSHOT_RESERVATION = 2
REQUIRED_SNAPSHOT_COMPLETION_RESERVATION = 4
REQUIRED_READINESS_SNAPSHOT_RESERVATION = 6
COMBINED_ZERO_TRANSPORT_VALIDATION = 9
HOLDER_WORST_CASE_GOVERNED_REQUESTS = 3
HOLDER_WORST_CASE_TRANSPORT_OPERATIONS = 5
PERMANENT_HOLDER_STAGE_TRANSPORT_CEILING = 8
HOLDER_REQUEST_PURPOSE = "pre_activation_holder_eligibility"
HOLDER_POLICY_VERSION = "v2-9.7e.22"
HOLDER_PARSER_VERSION = "v2-9.7e.22"
MATURATION_THRESHOLD_SECONDS: int | None = None
MATURATION_THRESHOLD_STATE = "UNPROVEN_DISABLED"


class HolderBudgetError(RuntimeError):
    """Raised when campaign holder/admission budget is impossible or breached.

    ``code`` is the stable machine-readable cause. ``detail`` carries exact
    expected / reserved / available values for operator and test inspection.
    """

    def __init__(self, code: str, *, detail: Mapping[str, Any] | None = None) -> None:
        self.code = str(code)
        self.detail = dict(detail or {})
        if self.detail:
            parts = ",".join(f"{key}={self.detail[key]}" for key in sorted(self.detail))
            super().__init__(f"{self.code}:{parts}")
        else:
            super().__init__(self.code)


def _time(value: str | datetime) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def deterministic_spacing_seconds(source_name: str) -> int:
    """Minimum whole-second spacing derived from the committed registry rate."""
    rate = SOURCE_REGISTRY[source_name].default_rate_limit_per_minute
    return max(1, math.ceil(60 / rate))


def next_paced_time(*, source_name: str, previous_at: str | datetime | None, now: str | datetime) -> datetime:
    current = _time(now)
    if previous_at is None:
        return current
    return max(current, _time(previous_at) + timedelta(seconds=deterministic_spacing_seconds(source_name)))


class SequentialRequestPacer:
    """One-shot fixed spacing gate; it never retries or rotates an endpoint."""

    def __init__(self, *, now_fn=None, sleep_fn=None) -> None:
        self._now = now_fn or (lambda: datetime.now(timezone.utc))
        self._sleep = sleep_fn or time.sleep
        self._last_started: dict[str, datetime] = {}
        self.trace: list[tuple[str, datetime]] = []

    def pace(self, source_name: str) -> datetime:
        current = _time(self._now())
        due = next_paced_time(
            source_name=source_name,
            previous_at=self._last_started.get(source_name),
            now=current,
        )
        wait_seconds = max(0.0, (due - current).total_seconds())
        if wait_seconds:
            self._sleep(wait_seconds)
        started = _time(self._now())
        self._last_started[source_name] = started
        self.trace.append((source_name, started))
        return started


@dataclass(frozen=True)
class CampaignOperationLedger:
    operation_ceiling: int
    governed_requests: int
    underlying_transport_operations: int
    zero_transport_operations: int
    reserved_snapshot_operations: int
    reserved_snapshot_completion_operations: int
    deadline_at: datetime

    @property
    def charged_operations(self) -> int:
        return self.underlying_transport_operations + self.zero_transport_operations

    @property
    def available_before_reservation(self) -> int:
        return (
            self.operation_ceiling - self.charged_operations
            - self.reserved_snapshot_operations
            - self.reserved_snapshot_completion_operations
        )

    def candidate_cap(self) -> int:
        return max(0, self.available_before_reservation // HOLDER_WORST_CASE_TRANSPORT_OPERATIONS)

    def budget_detail(self) -> dict[str, int | str]:
        reserved = (
            self.reserved_snapshot_operations
            + self.reserved_snapshot_completion_operations
        )
        charged_plus_reserved = self.charged_operations + reserved
        return {
            "operation_ceiling": self.operation_ceiling,
            "governed_requests": self.governed_requests,
            "underlying_transport_operations": self.underlying_transport_operations,
            "zero_transport_operations": self.zero_transport_operations,
            "charged_operations": self.charged_operations,
            "reserved_snapshot_operations": self.reserved_snapshot_operations,
            "reserved_snapshot_completion_operations": (
                self.reserved_snapshot_completion_operations
            ),
            "reserved_total": reserved,
            "charged_plus_reserved": charged_plus_reserved,
            "available_before_reservation": self.available_before_reservation,
            "holder_worst_case_transport_operations": (
                HOLDER_WORST_CASE_TRANSPORT_OPERATIONS
            ),
            "candidate_cap": self.candidate_cap(),
            "deadline_at": self.deadline_at.isoformat(),
        }

    def admit_candidate(self, *, now: str | datetime) -> None:
        if _time(now) > self.deadline_at:
            raise HolderBudgetError(
                "HOLDER_CAMPAIGN_DEADLINE_EXPIRED",
                detail=self.budget_detail(),
            )
        if self.available_before_reservation < HOLDER_WORST_CASE_TRANSPORT_OPERATIONS:
            raise HolderBudgetError(
                "DEX_SNAPSHOT_RESERVATION_WOULD_BE_BREACHED",
                detail=self.budget_detail(),
            )


@dataclass(frozen=True)
class PreHolderBudgetSnapshot:
    """Immutable projection of existing campaign accounting before holder I/O."""

    governed_request_ids: tuple[int, ...]
    measured_transport_identity_keys: tuple[tuple[object, ...], ...]
    governed_request_count: int
    measured_transport_count: int
    zero_transport_operations: int
    reserved_snapshot_operations: int
    reserved_snapshot_completion_operations: int


@dataclass(frozen=True)
class HolderAttemptAdmission:
    """Non-mutating pre-attempt decision for permanent holder context."""

    allowed: bool
    reason: str | None
    available_operations: int
    required_worst_case_operations: int
    permanent_stage_operations_used: int
    permanent_stage_operations_remaining: int
    deadline_expired: bool


def holder_attempt_admission(
    ledger: CampaignOperationLedger,
    *,
    now: str | datetime,
    permanent_stage_operations_used: int,
) -> HolderAttemptAdmission:
    used = int(permanent_stage_operations_used)
    if used < 0:
        raise HolderBudgetError("PERMANENT_HOLDER_STAGE_OPERATION_COUNT_NEGATIVE")
    remaining = max(0, PERMANENT_HOLDER_STAGE_TRANSPORT_CEILING - used)
    deadline_expired = _time(now) > ledger.deadline_at
    enough_campaign_budget = (
        ledger.available_before_reservation
        >= HOLDER_WORST_CASE_TRANSPORT_OPERATIONS
    )
    enough_stage_budget = remaining >= HOLDER_WORST_CASE_TRANSPORT_OPERATIONS
    allowed = not deadline_expired and enough_campaign_budget and enough_stage_budget
    reason = None
    if deadline_expired:
        reason = "HOLDER_CONTEXT_DEADLINE_EXPIRED"
    elif not enough_campaign_budget or not enough_stage_budget:
        reason = "HOLDER_CONTEXT_BUDGET_EXHAUSTED"
    return HolderAttemptAdmission(
        allowed=allowed,
        reason=reason,
        available_operations=ledger.available_before_reservation,
        required_worst_case_operations=HOLDER_WORST_CASE_TRANSPORT_OPERATIONS,
        permanent_stage_operations_used=used,
        permanent_stage_operations_remaining=remaining,
        deadline_expired=deadline_expired,
    )


def _measured_transport_identity_key(raw: Mapping[str, Any]) -> tuple[object, ...]:
    return (
        str(raw.get("stage") or ""),
        str(raw.get("source_name") or ""),
        str(raw.get("governed_request_kind") or ""),
        str(raw.get("method_or_endpoint") or ""),
        int(raw.get("within_request_ordinal") or 0),
        str(raw.get("target_category") or ""),
        None
        if raw.get("target_identity") is None
        else str(raw.get("target_identity")),
    )


def _exact_transport_keys(
    identities: Sequence[Mapping[str, Any]],
) -> tuple[tuple[object, ...], ...]:
    keys: list[tuple[object, ...]] = []
    seen: set[tuple[object, ...]] = set()
    for raw in identities:
        if not isinstance(raw, Mapping):
            raise HolderBudgetError(
                "PRE_HOLDER_MEASURED_TRANSPORT_IDENTITY_MALFORMED"
            )
        try:
            key = _measured_transport_identity_key(raw)
        except (TypeError, ValueError) as exc:
            raise HolderBudgetError(
                "PRE_HOLDER_MEASURED_TRANSPORT_IDENTITY_MALFORMED"
            ) from exc
        if key in seen:
            raise HolderBudgetError(
                "PRE_HOLDER_DUPLICATE_MEASURED_TRANSPORT_IDENTITY"
            )
        seen.add(key)
        keys.append(key)
    return tuple(keys)


def build_pre_holder_budget_snapshot(
    *,
    campaign_id: str,
    governed_request_ids: Sequence[int],
    request_manifest: Sequence[Mapping[str, Any]],
    campaign_transport_identities: Sequence[Mapping[str, Any]],
    action_local_transport_identities: Sequence[Mapping[str, Any]],
) -> PreHolderBudgetSnapshot:
    """Project request and measured-transport truth from canonical owners.

    This function owns no accounting state. It freezes and reconciles the
    Source Governor manifest, campaign six-unit owner, and action-local
    measurement surface before holder work begins.
    """
    campaign = str(campaign_id or "").strip()
    if not campaign:
        raise HolderBudgetError("PRE_HOLDER_CAMPAIGN_IDENTITY_MISSING")
    request_ids = tuple(int(value) for value in governed_request_ids)
    if len(request_ids) != len(set(request_ids)):
        raise HolderBudgetError("PRE_HOLDER_DUPLICATE_GOVERNED_REQUEST_ID")

    manifest_ids: list[int] = []
    manifest_transport_count = 0
    for raw in request_manifest:
        if not isinstance(raw, Mapping) or raw.get("source_request_id") is None:
            raise HolderBudgetError("PRE_HOLDER_REQUEST_MANIFEST_MALFORMED")
        rid = int(raw["source_request_id"])
        manifest_ids.append(rid)
        stage_id = str(raw.get("logical_stage_id") or "")
        if not stage_id.startswith(f"{campaign}|"):
            raise HolderBudgetError(
                "PRE_HOLDER_REQUEST_CAMPAIGN_OWNERSHIP_MISSING",
                detail={"source_request_id": rid},
            )
        if "transport_identity_count" not in raw:
            raise HolderBudgetError(
                "PRE_HOLDER_TRANSPORT_COUNT_WITHOUT_IDENTITIES",
                detail={"source_request_id": rid},
            )
        try:
            count = int(raw["transport_identity_count"])
        except (TypeError, ValueError) as exc:
            raise HolderBudgetError(
                "PRE_HOLDER_TRANSPORT_COUNT_WITHOUT_IDENTITIES",
                detail={"source_request_id": rid},
            ) from exc
        if count < 0:
            raise HolderBudgetError(
                "PRE_HOLDER_TRANSPORT_COUNT_WITHOUT_IDENTITIES",
                detail={"source_request_id": rid},
            )
        manifest_transport_count += count
    if len(manifest_ids) != len(set(manifest_ids)):
        raise HolderBudgetError("PRE_HOLDER_DUPLICATE_GOVERNED_REQUEST_ID")
    if set(manifest_ids) != set(request_ids):
        raise HolderBudgetError("PRE_HOLDER_REQUEST_MANIFEST_MISMATCH")

    campaign_keys = _exact_transport_keys(campaign_transport_identities)
    action_local_keys = _exact_transport_keys(action_local_transport_identities)
    if manifest_transport_count != len(campaign_keys):
        raise HolderBudgetError(
            "PRE_HOLDER_TRANSPORT_COUNT_WITHOUT_IDENTITIES",
            detail={
                "manifest_transport_count": manifest_transport_count,
                "campaign_identity_count": len(campaign_keys),
            },
        )
    if set(campaign_keys) != set(action_local_keys):
        raise HolderBudgetError(
            "PRE_HOLDER_STAGE_CAMPAIGN_RECONCILIATION_MISMATCH"
        )
    return PreHolderBudgetSnapshot(
        governed_request_ids=tuple(sorted(request_ids)),
        measured_transport_identity_keys=tuple(sorted(campaign_keys, key=repr)),
        governed_request_count=len(request_ids),
        measured_transport_count=len(campaign_keys),
        zero_transport_operations=COMBINED_ZERO_TRANSPORT_VALIDATION,
        reserved_snapshot_operations=REQUIRED_DEX_SNAPSHOT_RESERVATION,
        reserved_snapshot_completion_operations=(
            REQUIRED_SNAPSHOT_COMPLETION_RESERVATION
        ),
    )


def budget_contract_constants() -> dict[str, int]:
    """Authoritative admission/holder budget constants shared by preflight+runtime."""
    return {
        "operation_ceiling": OPERATION_CEILING,
        "required_dex_snapshot_reservation": REQUIRED_DEX_SNAPSHOT_RESERVATION,
        "required_snapshot_completion_reservation": (
            REQUIRED_SNAPSHOT_COMPLETION_RESERVATION
        ),
        "required_readiness_snapshot_reservation": (
            REQUIRED_READINESS_SNAPSHOT_RESERVATION
        ),
        "combined_zero_transport_validation": COMBINED_ZERO_TRANSPORT_VALIDATION,
        "holder_worst_case_governed_requests": HOLDER_WORST_CASE_GOVERNED_REQUESTS,
        "holder_worst_case_transport_operations": HOLDER_WORST_CASE_TRANSPORT_OPERATIONS,
    }


def build_operational_budget_preflight(
    *,
    admission_operation_ceiling: int = OPERATION_CEILING,
    discovery_request_ceiling: int | None = None,
    governed_15m_request_ceiling: int | None = None,
    governed_requests_per_token: int | None = None,
) -> dict[str, Any]:
    """Zero-source preflight of the static admission budget contract.

    Rejects impossible static configurations before any campaign row is created.
    Does not raise approved ceilings and does not inspect live source usage.
    """
    constants = budget_contract_constants()
    reserved_total = (
        constants["required_dex_snapshot_reservation"]
        + constants["required_snapshot_completion_reservation"]
    )
    fixed_charge = constants["combined_zero_transport_validation"] + reserved_total
    available_for_base = constants["operation_ceiling"] - fixed_charge
    issues: list[str] = []
    if int(admission_operation_ceiling) != constants["operation_ceiling"]:
        issues.append(
            "ADMISSION_CEILING_MISMATCH:"
            f"configured={int(admission_operation_ceiling)}"
            f":authoritative={constants['operation_ceiling']}"
        )
    if available_for_base < 0:
        issues.append("STATIC_RESERVATIONS_EXCEED_OPERATION_CEILING")
    if constants["operation_ceiling"] != 45:
        issues.append("OPERATION_CEILING_DRIFT")
    if constants["required_dex_snapshot_reservation"] != 2:
        issues.append("DEX_SNAPSHOT_RESERVATION_DRIFT")
    if constants["required_snapshot_completion_reservation"] != 4:
        issues.append("SNAPSHOT_COMPLETION_RESERVATION_DRIFT")
    if constants["combined_zero_transport_validation"] != 9:
        issues.append("ZERO_TRANSPORT_VALIDATION_DRIFT")
    if constants["holder_worst_case_transport_operations"] != 5:
        issues.append("HOLDER_WORST_CASE_TRANSPORT_DRIFT")
    # Optional outer campaign ceilings are reported only; they must not silently
    # override the admission operation ledger.
    outer = {
        "discovery_request_ceiling": discovery_request_ceiling,
        "governed_15m_request_ceiling": governed_15m_request_ceiling,
        "governed_requests_per_token": governed_requests_per_token,
    }
    return {
        "status": "READY" if not issues else "BLOCKED",
        "issues": issues,
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "expected": {
            "operation_ceiling": constants["operation_ceiling"],
            "zero_transport_operations": constants[
                "combined_zero_transport_validation"
            ],
            "reserved_snapshot_operations": constants[
                "required_dex_snapshot_reservation"
            ],
            "reserved_snapshot_completion_operations": constants[
                "required_snapshot_completion_reservation"
            ],
            "reserved_total": reserved_total,
            "fixed_charge_before_base_work": fixed_charge,
            "available_for_base_work": available_for_base,
            "holder_worst_case_transport_operations": constants[
                "holder_worst_case_transport_operations"
            ],
        },
        "outer_ceilings": outer,
        "constants": constants,
    }


def build_ledger_from_exact_counts(
    *,
    governed_request_count: int,
    underlying_transport_operations: int,
    deadline_at: str | datetime,
) -> CampaignOperationLedger:
    """Build the ledger from independently proven request/transport counts."""
    requests = int(governed_request_count)
    transports = int(underlying_transport_operations)
    if requests < 0 or transports < 0:
        raise HolderBudgetError(
            "CAMPAIGN_BASE_WORK_COUNT_NEGATIVE",
            detail={
                "governed_request_count": requests,
                "underlying_transport_operations": transports,
            },
        )
    ledger = CampaignOperationLedger(
        operation_ceiling=OPERATION_CEILING,
        governed_requests=requests,
        underlying_transport_operations=transports,
        zero_transport_operations=COMBINED_ZERO_TRANSPORT_VALIDATION,
        reserved_snapshot_operations=REQUIRED_DEX_SNAPSHOT_RESERVATION,
        reserved_snapshot_completion_operations=REQUIRED_SNAPSHOT_COMPLETION_RESERVATION,
        deadline_at=_time(deadline_at),
    )
    charged_plus_reserved = (
        ledger.charged_operations
        + ledger.reserved_snapshot_operations
        + ledger.reserved_snapshot_completion_operations
    )
    if charged_plus_reserved > OPERATION_CEILING:
        detail = ledger.budget_detail()
        detail.update(
            {
                "governed_request_count": requests,
                "underlying_transport_operations": transports,
                "available_for_base_work": (
                    OPERATION_CEILING
                    - COMBINED_ZERO_TRANSPORT_VALIDATION
                    - REQUIRED_DEX_SNAPSHOT_RESERVATION
                    - REQUIRED_SNAPSHOT_COMPLETION_RESERVATION
                ),
            }
        )
        raise HolderBudgetError(
            "CAMPAIGN_BASE_WORK_EXCEEDS_RESERVED_BUDGET",
            detail=detail,
        )
    return ledger


def build_ledger(
    *, pump_operations: int, deadline_at: str | datetime,
    additional_governed_operations: int = 0,
) -> CampaignOperationLedger:
    """Legacy equality path where callers prove one request equals one transport."""
    base_operations = int(pump_operations) + int(additional_governed_operations)
    return build_ledger_from_exact_counts(
        governed_request_count=base_operations,
        underlying_transport_operations=base_operations,
        deadline_at=deadline_at,
    )


def persist_ledger(connection: sqlite3.Connection, *, run_id: str, cycle_id: str, ledger: CampaignOperationLedger, now: str) -> None:
    connection.execute(
        """INSERT INTO printer_holder_campaign_operation_ledgers(
            run_id,cycle_id,operation_ceiling,governed_requests,
            underlying_transport_operations,zero_transport_operations,
            reserved_snapshot_operations,reserved_snapshot_completion_operations,
            deadline_at,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(run_id,cycle_id) DO UPDATE SET
            governed_requests=excluded.governed_requests,
            underlying_transport_operations=excluded.underlying_transport_operations,
            zero_transport_operations=excluded.zero_transport_operations,
            deadline_at=excluded.deadline_at,updated_at=excluded.updated_at""",
        (run_id, cycle_id, ledger.operation_ceiling, ledger.governed_requests,
         ledger.underlying_transport_operations, ledger.zero_transport_operations,
         ledger.reserved_snapshot_operations,
         ledger.reserved_snapshot_completion_operations,
         ledger.deadline_at.isoformat(), now, now),
    )


def schedule_maturation(
    connection: sqlite3.Connection, *, run_id: str, cycle_id: str,
    mint: str, observed_at: str, now: str, deadline_at: str,
    cancelled: bool = False,
) -> Mapping[str, Any]:
    """Persist/replay one maturation decision; waiting always implies zero calls."""
    mint_key = mint.lower()
    current = _time(now)
    deadline = _time(deadline_at)
    threshold = MATURATION_THRESHOLD_SECONDS
    due = current if threshold is None else _time(observed_at) + timedelta(seconds=threshold)
    if cancelled:
        state, cause = "CANCELLED", "CAMPAIGN_CANCELLED"
    elif due > deadline or current > deadline:
        state, cause = "DEADLINE_REFUSED", "MATURATION_EXCEEDS_DEADLINE"
    elif current < due:
        state, cause = "WAITING", None
    else:
        state, cause = "DUE", None
    work_id = f"holder-maturation:{run_id}:{cycle_id}:{mint_key}"
    connection.execute(
        """INSERT INTO printer_holder_maturation_work(
            work_id,run_id,cycle_id,mint_identity,request_purpose,scheduled_for,
            deadline_at,work_state,maturation_threshold_state,first_terminal_cause,
            created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(run_id,cycle_id,mint_identity,request_purpose) DO UPDATE SET
            work_state=CASE
                WHEN printer_holder_maturation_work.work_state IN ('CANCELLED','DEADLINE_REFUSED','COMPLETED')
                THEN printer_holder_maturation_work.work_state ELSE excluded.work_state END,
            first_terminal_cause=COALESCE(printer_holder_maturation_work.first_terminal_cause,excluded.first_terminal_cause),
            updated_at=excluded.updated_at""",
        (work_id, run_id, cycle_id, mint_key, HOLDER_REQUEST_PURPOSE,
         due.isoformat(), deadline.isoformat(), state, MATURATION_THRESHOLD_STATE,
         cause, current.isoformat(), current.isoformat()),
    )
    row = connection.execute(
        "SELECT work_state,scheduled_for,deadline_at,maturation_threshold_state "
        "FROM printer_holder_maturation_work WHERE work_id=?", (work_id,),
    ).fetchone()
    return {
        "work_id": work_id, "work_state": str(row[0]),
        "scheduled_for": str(row[1]), "deadline_at": str(row[2]),
        "maturation_threshold_state": str(row[3]),
        "source_calls_while_waiting": 0,
    }


def complete_maturation(
    connection: sqlite3.Connection, *, work_id: str, cause: str, now: str,
) -> None:
    connection.execute(
        """UPDATE printer_holder_maturation_work
           SET work_state='COMPLETED',first_terminal_cause=?,updated_at=?
           WHERE work_id=? AND work_state='DUE'""",
        (cause, now, work_id),
    )


def reusable_evidence(
    connection: sqlite3.Connection, *, mint: str, purpose: str, source_name: str,
    endpoint_role: str, evaluated_at: str, parser_version: str = HOLDER_PARSER_VERSION,
    policy_version: str = HOLDER_POLICY_VERSION,
) -> sqlite3.Row | None:
    if source_name not in SOURCE_REGISTRY:
        return None
    cutoff = _time(evaluated_at) - timedelta(seconds=SOURCE_REGISTRY[source_name].stale_after_seconds)
    return connection.execute(
        """SELECT * FROM printer_holder_evidence_attempts
           WHERE mint_identity=? AND request_purpose=? AND source_name=?
             AND endpoint_role=? AND parser_version=? AND policy_version=?
             AND source_status='COMPLETE' AND data_quality_label='CLEAN_DATA'
             AND exact_target=1 AND source_response_id IS NOT NULL
             AND holder_concentration_label IS NOT NULL
             AND holder_concentration_label!='HOLDER_CONCENTRATION_UNKNOWN'
             AND captured_at IS NOT NULL AND received_at IS NOT NULL
             AND received_at>=?
           ORDER BY received_at DESC,evidence_id DESC LIMIT 1""",
        (mint.lower(), purpose, source_name, endpoint_role, parser_version,
         policy_version, cutoff.isoformat()),
    ).fetchone()


def reuse_holder_fact(
    connection: sqlite3.Connection, *, run_id: str, cycle_id: str,
    mint: str, evaluated_at: str,
) -> Mapping[str, Any] | None:
    """Reuse the first strict exact-source fact in the fixed source order."""
    for source_name, endpoint_role in (
        ("goplus", "PRIMARY"),
        ("solana_rpc", "PRIMARY"),
        ("helius_free", "BACKUP"),
    ):
        row = reusable_evidence(
            connection, mint=mint, purpose=HOLDER_REQUEST_PURPOSE,
            source_name=source_name, endpoint_role=endpoint_role,
            evaluated_at=evaluated_at,
        )
        if row is None:
            continue
        new_id = record_attempt(
            connection, run_id=run_id, cycle_id=cycle_id, mint_identity=mint,
            source_name=source_name, endpoint_role=endpoint_role,
            redacted_host=str(row["redacted_host"]),
            source_request_id=None, source_response_id=None, source_failure_id=None,
            lineage_response_id=int(row["source_response_id"]),
            reused_evidence_id=int(row["evidence_id"]),
            captured_at=str(row["captured_at"]), received_at=str(row["received_at"]),
            source_status="COMPLETE", data_quality_label="CLEAN_DATA", exact_target=1,
            holder_concentration_label=str(row["holder_concentration_label"]),
            rpc_method=row["rpc_method"], commitment=row["commitment"],
            context_slot=row["context_slot"], underlying_operation_count=0,
            failure_subtype=None, retry_after_at=None, created_at=evaluated_at,
        )
        return {
            "eligible": True,
            "reason": "VALID_EXACT_TARGET_HOLDER_EVIDENCE_REUSED",
            "source_name": source_name,
            "holder_concentration_label": str(row["holder_concentration_label"]),
            "reused_evidence_id": int(row["evidence_id"]),
            "evidence_id": new_id,
        }
    return None


def record_attempt(connection: sqlite3.Connection, **values: Any) -> int:
    columns = (
        "run_id","cycle_id","mint_identity","request_purpose","source_name",
        "endpoint_role","redacted_host","source_request_id","source_response_id",
        "source_failure_id","lineage_response_id","reused_evidence_id","captured_at",
        "received_at","parser_version","policy_version","source_status",
        "data_quality_label","exact_target","holder_concentration_label","rpc_method",
        "commitment","context_slot","underlying_operation_count","failure_subtype",
        "retry_after_at","created_at",
    )
    payload = dict(values)
    payload["mint_identity"] = str(payload["mint_identity"]).lower()
    payload.setdefault("request_purpose", HOLDER_REQUEST_PURPOSE)
    payload.setdefault("parser_version", HOLDER_PARSER_VERSION)
    payload.setdefault("policy_version", HOLDER_POLICY_VERSION)
    cursor = connection.execute(
        f"INSERT INTO printer_holder_evidence_attempts({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
        tuple(payload.get(column) for column in columns),
    )
    return int(cursor.lastrowid)


@dataclass(frozen=True)
class HolderBundlePersistResult:
    """One candidate's governed holder attempts: IDs, coverage, accounting."""

    governed_request_count: int
    measured_transport_count: int
    source_request_ids: tuple[int, ...]
    source_request_coverage: tuple[Mapping[str, Any], ...]
    accounting_blocker: bool
    accounting_blocker_reason: str | None
    transport_identities: tuple[Mapping[str, Any], ...] = ()
    holder_stage_id: str | None = None
    holder_stage_terminal_status: str | None = None
    holder_stage_first_terminal_cause: str | None = None


class HolderBundlePersistPartialError(RuntimeError):
    """Typed partial-result contract for a failed holder persistence pass.

    Raised when ``persist_bundle_attempts`` cannot complete every governed
    execution. It carries the evidence already derivable from the real
    execution records so a governed ``printer_source_requests`` row can never
    disappear from holder IDs, coverage, or campaign reconciliation.
    """

    def __init__(
        self,
        code: str,
        *,
        partial: HolderBundlePersistResult,
        failed_stage: str,
        cause: BaseException | None = None,
    ) -> None:
        self.code = str(code)
        self.partial = partial
        self.failed_stage = str(failed_stage)
        self.cause = cause
        super().__init__(f"{self.code}:stage={self.failed_stage}")


@dataclass(frozen=True)
class HolderContextResult:
    """Campaign-owned holder-stage result for reconciliation and readiness.

    Request count and transport count remain independent. Coverage entries are
    emitted only from real governed execution records (never invented IDs).
    """

    holder_facts: Mapping[str, Mapping[str, Any]]
    ledger: CampaignOperationLedger
    source_request_ids: tuple[int, ...]
    source_request_coverage: tuple[Mapping[str, Any], ...]
    accounting_blocker: bool
    accounting_blocker_reason: str | None
    governed_request_count: int
    measured_transport_count: int
    evaluated_candidate_mints: tuple[str, ...] = ()
    unattempted_candidate_mints: tuple[str, ...] = ()
    budget_exhausted: bool = False
    budget_exhaustion_reason: str | None = None
    ledger_before_holder: CampaignOperationLedger | None = None
    ledger_after_holder: CampaignOperationLedger | None = None
    holder_attempt_budget_trace: tuple[Mapping[str, Any], ...] = ()
    transport_identities: tuple[Mapping[str, Any], ...] = ()
    holder_stage_id: str | None = None
    holder_stage_terminal_status: str | None = None
    holder_stage_first_terminal_cause: str | None = None

    def as_holder_context_diagnostics(self) -> dict[str, Any]:
        return {
            "accounting_blocker": bool(self.accounting_blocker),
            "accounting_blocker_reason": self.accounting_blocker_reason,
            "source_request_ids": list(self.source_request_ids),
            "source_request_coverage": [
                dict(entry) for entry in self.source_request_coverage
            ],
            "governed_request_count": int(self.governed_request_count),
            "measured_transport_count": int(self.measured_transport_count),
            "evaluated_candidate_mints": list(self.evaluated_candidate_mints),
            "unattempted_candidate_mints": list(self.unattempted_candidate_mints),
            "budget_exhausted": bool(self.budget_exhausted),
            "budget_exhaustion_reason": self.budget_exhaustion_reason,
            "ledger_before_holder": (
                None
                if self.ledger_before_holder is None
                else self.ledger_before_holder.budget_detail()
            ),
            "ledger_after_holder": (
                None
                if self.ledger_after_holder is None
                else self.ledger_after_holder.budget_detail()
            ),
            "holder_attempt_budget_trace": [
                dict(entry) for entry in self.holder_attempt_budget_trace
            ],
            "transport_identities": [
                dict(entry) for entry in self.transport_identities
            ],
            "holder_stage_id": self.holder_stage_id,
            "holder_stage_terminal_status": self.holder_stage_terminal_status,
            "holder_stage_first_terminal_cause": self.holder_stage_first_terminal_cause,
        }


def empty_holder_context_result(
    ledger: CampaignOperationLedger,
    *,
    holder_facts: Mapping[str, Mapping[str, Any]] | None = None,
) -> HolderContextResult:
    """Build an empty holder-stage result (no governed holder attempts)."""
    return HolderContextResult(
        holder_facts=dict(holder_facts or {}),
        ledger=ledger,
        source_request_ids=(),
        source_request_coverage=(),
        accounting_blocker=False,
        accounting_blocker_reason=None,
        governed_request_count=0,
        measured_transport_count=0,
        ledger_before_holder=ledger,
        ledger_after_holder=ledger,
    )


def _holder_source_role(execution_key: str) -> str:
    key = str(execution_key or "")
    if key == "safety":
        return "SAFETY"
    if key == "holder_backup":
        return "HOLDER_BACKUP"
    if key in {"holder_primary", "holder"}:
        return "HOLDER_PRIMARY"
    return key.upper() or "HOLDER"


def _measure_holder_transport_count(
    execution: Any,
    *,
    require_exact_identities: bool = False,
) -> tuple[int, bool, str | None]:
    """Return (count, accounting_complete, reason) from proven measured evidence.

    Never invents RPC=2 / non-RPC=1 fallbacks. Accepts only:
    * transport_operation_identities (+ matching transport_operations_used)
    * explicit underlying_operation_count from the adapter/normalized payload
    * explicit transport_operations_used when identities prove the same count
    """
    normalized = execution.normalized_result
    payload = dict(getattr(normalized, "normalized_payload", None) or {})
    identities_raw = payload.get("transport_operation_identities")
    if isinstance(identities_raw, Sequence) and not isinstance(
        identities_raw, (str, bytes)
    ):
        identities = [item for item in identities_raw if isinstance(item, Mapping)]
        if len(identities) != len(identities_raw):
            return 0, False, "HOLDER_TRANSPORT_IDENTITY_MALFORMED"
        if identities:
            keys: set[tuple[object, ...]] = set()
            ordinals: set[int] = set()
            expected_source = str(getattr(normalized, "source_name", "") or "")
            expected_kind = str(getattr(normalized, "request_kind", "") or "")
            expected_target = str(payload.get("token_mint") or "")
            for raw in identities:
                try:
                    key = _measured_transport_identity_key(raw)
                    ordinal = int(raw.get("within_request_ordinal"))
                    response_bytes = int(raw.get("response_bytes"))
                    normalized_rows = int(raw.get("normalized_rows"))
                except (TypeError, ValueError) as exc:
                    return 0, False, "HOLDER_TRANSPORT_IDENTITY_MALFORMED"
                if key in keys or ordinal in ordinals:
                    return 0, False, "HOLDER_TRANSPORT_IDENTITY_DUPLICATE"
                keys.add(key)
                ordinals.add(ordinal)
                if (
                    str(raw.get("stage") or "") != "HOLDER_SAFETY"
                    or str(raw.get("source_name") or "") != expected_source
                    or str(raw.get("governed_request_kind") or "") != expected_kind
                    or str(raw.get("target_category") or "") != "TOKEN_MINT"
                    or (
                        expected_target
                        and str(raw.get("target_identity") or "").lower()
                        != expected_target.lower()
                    )
                    or not str(raw.get("endpoint_owner") or "").strip()
                ):
                    return 0, False, "HOLDER_TRANSPORT_IDENTITY_CORRESPONDENCE_MISMATCH"
                if response_bytes < 0 or normalized_rows < 0:
                    return 0, False, "HOLDER_TRANSPORT_IDENTITY_MEASURE_INVALID"
            used = payload.get("transport_operations_used")
            count = len(identities)
            if used is not None and int(used) != count:
                return 0, False, "HOLDER_TRANSPORT_IDENTITY_COUNT_MISMATCH"
            return count, True, None
        if payload.get("transport_operations_used") == 0:
            return 0, True, None
        if payload.get("transport_operations_used"):
            return 0, False, "HOLDER_TRANSPORT_IDENTITIES_MISSING"
    if require_exact_identities:
        return 0, False, "HOLDER_TRANSPORT_IDENTITIES_MISSING"
    if "underlying_operation_count" in payload and payload[
        "underlying_operation_count"
    ] is not None:
        try:
            count = int(payload["underlying_operation_count"])
        except (TypeError, ValueError):
            return 0, False, "HOLDER_TRANSPORT_COUNT_INVALID"
        if count < 0:
            return 0, False, "HOLDER_TRANSPORT_COUNT_NEGATIVE"
        return count, True, None
    if payload.get("transport_operations_used") is not None:
        try:
            used = int(payload["transport_operations_used"])
        except (TypeError, ValueError):
            return 0, False, "HOLDER_TRANSPORT_COUNT_INVALID"
        if used > 0:
            return 0, False, "HOLDER_TRANSPORT_IDENTITIES_MISSING"
        return 0, True, None
    return 0, False, "HOLDER_TRANSPORT_IDENTITY_ABSENT"


def _holder_source_failed(execution: Any) -> bool:
    normalized = execution.normalized_result
    if getattr(normalized, "failure_type", None):
        return True
    status = getattr(normalized, "source_status", None)
    value = getattr(status, "value", status)
    return str(value or "") not in {"COMPLETE", "PARTIAL"}


def _holder_logical_stage_id(
    *,
    campaign_id: str | None,
    run_id: str,
    cycle_id: str,
    mint: str,
    candidate_ordinal: int,
    source_role: str,
) -> str:
    candidate_key = str(mint or "").lower() or str(candidate_ordinal)
    camp = str(campaign_id or "campaign")
    return (
        f"{camp}|{run_id}|{cycle_id}|HOLDER|{candidate_key}|{source_role}"
    )




def _persist_one_holder_attempt(
    connection: sqlite3.Connection,
    *,
    key: str,
    execution: Any,
    run_id: str,
    cycle_id: str,
    mint: str,
    created_at: str,
    campaign_id: str | None,
    candidate_ordinal: int,
) -> tuple[dict[str, Any], int, bool, str | None]:
    """Persist one governed holder attempt.

    Returns ``(coverage_entry, measured_transport_count, accounting_ok,
    accounting_reason)``. The coverage entry is derived from the real execution
    record only; transport counts require proven measured metadata.
    """
    from printer_v1.safety.goplus_normalizer import holder_concentration_label_from_goplus

    normalized = execution.normalized_result
    payload = dict(getattr(normalized, "normalized_payload", None) or {})
    is_rpc = str(key).startswith("holder")
    role = "BACKUP" if key == "holder_backup" else "PRIMARY"
    source_role = _holder_source_role(str(key))
    source_name = str(getattr(normalized, "source_name", "") or "")
    request_kind = str(
        getattr(normalized, "request_kind", None)
        or getattr(getattr(execution, "request_record", None), "request_kind", None)
        or ("holder_concentration_reference" if is_rpc else "safety_reference")
    )
    host = str(
        payload.get("redacted_host")
        or (
            "mainnet.helius-rpc.com"
            if source_name == "helius_free"
            else "api.mainnet.solana.com"
            if is_rpc
            else "api.gopluslabs.io"
        )
    )
    request_id = int(execution.request_record.id)

    operation_count, accounting_ok, measure_reason = _measure_holder_transport_count(
        execution
    )
    accounting_reason: str | None = None
    if not accounting_ok:
        if measure_reason:
            accounting_reason = f"{measure_reason}:request={request_id}"
        operation_count = 0

    source_failed = _holder_source_failed(execution)
    terminal_status = "BLOCKED" if (not accounting_ok or source_failed) else "COMPLETED"
    member_count = 0
    if accounting_ok and not source_failed:
        # One normalized holder/safety contribution when evidence is present.
        if payload:
            member_count = 1

    coverage_entry = {
        "source_request_id": request_id,
        "source_name": source_name or ("solana_rpc" if is_rpc else "goplus"),
        "request_kind": request_kind,
        "logical_stage_id": _holder_logical_stage_id(
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            mint=mint,
            candidate_ordinal=candidate_ordinal,
            source_role=source_role,
        ),
        "terminal_status": terminal_status,
        "transport_identity_count": int(operation_count),
        "normalized_member_count": int(member_count),
    }

    returned_mint = str(payload.get("token_mint") or "")
    holder_label = (
        str(
            payload.get("holder_concentration_label")
            or "HOLDER_CONCENTRATION_UNKNOWN"
        )
        if is_rpc
        else holder_concentration_label_from_goplus(payload)
    )
    record_attempt(
        connection,
        run_id=run_id,
        cycle_id=cycle_id,
        mint_identity=mint,
        source_name=source_name or ("solana_rpc" if is_rpc else "goplus"),
        endpoint_role=role,
        redacted_host=host,
        source_request_id=request_id,
        source_response_id=(
            int(execution.response_record.id) if execution.response_record else None
        ),
        source_failure_id=(
            int(execution.failure_record.id) if execution.failure_record else None
        ),
        lineage_response_id=(
            int(execution.response_record.id) if execution.response_record else None
        ),
        reused_evidence_id=None,
        captured_at=payload.get("captured_at") or normalized.received_at,
        received_at=normalized.received_at,
        source_status=normalized.source_status.value,
        data_quality_label=normalized.data_quality_label.value,
        exact_target=int(bool(returned_mint) and returned_mint.lower() == mint.lower()),
        holder_concentration_label=holder_label,
        rpc_method=(
            payload.get("rpc_method")
            or (
                "getTokenLargestAccounts+getTokenSupply"
                if is_rpc and operation_count == 2
                else "getTokenLargestAccounts"
                if is_rpc
                else "HTTP_GET"
            )
        ),
        commitment=payload.get("commitment") or ("finalized" if is_rpc else None),
        context_slot=payload.get("context_slot"),
        underlying_operation_count=operation_count,
        failure_subtype=normalized.failure_type,
        retry_after_at=normalized.retry_after_at,
        created_at=created_at,
    )
    return coverage_entry, int(operation_count), bool(accounting_ok), accounting_reason


def _blocked_coverage_entry(
    *,
    key: str,
    request_id: int,
    execution: Any,
    run_id: str,
    cycle_id: str,
    mint: str,
    campaign_id: str | None,
    candidate_ordinal: int,
    transport_identity_count: int = 0,
) -> dict[str, Any]:
    """Coverage for a real governed request whose attempt did not complete.

    ``transport_identity_count`` carries the transport count already proven
    from authoritative measured metadata before the failing operation. A
    persistence failure may terminalize the attempt ``BLOCKED``, but it must
    not erase transport work that really happened.
    """
    normalized = getattr(execution, "normalized_result", None)
    is_rpc = str(key).startswith("holder")
    return {
        "source_request_id": int(request_id),
        "source_name": str(
            getattr(normalized, "source_name", "")
            or ("solana_rpc" if is_rpc else "goplus")
        ),
        "request_kind": str(
            getattr(normalized, "request_kind", None)
            or getattr(getattr(execution, "request_record", None), "request_kind", None)
            or ("holder_concentration_reference" if is_rpc else "safety_reference")
        ),
        "logical_stage_id": _holder_logical_stage_id(
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            mint=mint,
            candidate_ordinal=candidate_ordinal,
            source_role=_holder_source_role(str(key)),
        ),
        "terminal_status": "BLOCKED",
        "transport_identity_count": int(transport_identity_count),
        "normalized_member_count": 0,
    }


def persist_bundle_attempts(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    cycle_id: str,
    mint: str,
    executions: Mapping[str, Any],
    created_at: str,
    campaign_id: str | None = None,
    candidate_ordinal: int = 1,
    require_exact_transport_identities: bool = False,
) -> HolderBundlePersistResult:
    """Persist each distinct governed attempt; return IDs, coverage, accounting.

    Alias keys that refer to the same execution object are not double-counted.
    Request IDs always come from ``execution.request_record.id``. Transport
    counts require proven measured metadata — never RPC/non-RPC fallbacks.

    If persistence fails after one or more executions were processed, the
    evidence derivable from every real execution record is preserved and raised
    as a typed :class:`HolderBundlePersistPartialError` rather than lost.
    """
    distinct: list[tuple[str, Any]] = []
    seen: set[int] = set()
    for key, execution in executions.items():
        if key == "holder" and "holder_primary" in executions:
            continue
        if id(execution) in seen:
            continue
        seen.add(id(execution))
        distinct.append((key, execution))

    transports = 0
    request_ids: list[int] = []
    coverage: list[dict[str, Any]] = []
    accounting_blocker = False
    accounting_reasons: list[str] = []
    transport_identities: list[Mapping[str, Any]] = []
    transport_identity_keys: set[tuple[object, ...]] = set()

    for key, execution in distinct:
        # Capture the durable identity before any work that can raise, so a
        # governed request row can never vanish from IDs or coverage.
        try:
            request_id: int | None = int(execution.request_record.id)
        except Exception:  # pragma: no cover - no durable identity exists
            request_id = None
        # Measure the transport count from authoritative measured metadata
        # before any evidence-table operation that may raise, so a proven count
        # survives a later persistence failure. Zero is used only when the
        # measurement is itself absent, invalid, negative, or contradictory.
        try:
            proven_count, proven_ok, _proven_reason = _measure_holder_transport_count(
                execution,
                require_exact_identities=require_exact_transport_identities,
            )
        except Exception:  # pragma: no cover - unmeasurable execution record
            proven_count, proven_ok = 0, False
        if not proven_ok:
            proven_count = 0
        try:
            entry, operation_count, accounting_ok, reason = _persist_one_holder_attempt(
                connection,
                key=key,
                execution=execution,
                run_id=run_id,
                cycle_id=cycle_id,
                mint=mint,
                created_at=created_at,
                campaign_id=campaign_id,
                candidate_ordinal=candidate_ordinal,
            )
            if require_exact_transport_identities:
                operation_count, accounting_ok, exact_reason = (
                    _measure_holder_transport_count(
                        execution, require_exact_identities=True
                    )
                )
                if not accounting_ok:
                    reason = (
                        f"{exact_reason}:request={request_id}"
                        if exact_reason else "HOLDER_TRANSPORT_IDENTITIES_MISSING"
                    )
                    entry["terminal_status"] = "BLOCKED"
                    entry["transport_identity_count"] = 0
                else:
                    # Provider failure/rate-limit is truthful holder context;
                    # exact request accounting itself completed.
                    entry["terminal_status"] = "COMPLETED"
        except Exception as exc:
            if request_id is not None:
                if request_id not in request_ids:
                    request_ids.append(request_id)
                if not any(
                    int(item["source_request_id"]) == request_id for item in coverage
                ):
                    coverage.append(
                        _blocked_coverage_entry(
                            key=key,
                            request_id=request_id,
                            execution=execution,
                            run_id=run_id,
                            cycle_id=cycle_id,
                            mint=mint,
                            campaign_id=campaign_id,
                            candidate_ordinal=candidate_ordinal,
                            transport_identity_count=proven_count,
                        )
                    )
            accounting_reasons.append(
                f"HOLDER_BUNDLE_PERSIST_FAILED:{type(exc).__name__}"
                f":request={request_id}"
            )
            # An incomplete attempt is never a completed one, and it never
            # contributed a normalized member. The transport counts already
            # proven from the preserved real executions are kept exactly.
            blocked_coverage = []
            for item in coverage:
                blocked = dict(item)
                blocked["terminal_status"] = "BLOCKED"
                blocked["normalized_member_count"] = 0
                blocked_coverage.append(blocked)
            partial_transports = sum(
                int(item["transport_identity_count"]) for item in blocked_coverage
            )
            raise HolderBundlePersistPartialError(
                "HOLDER_BUNDLE_PERSIST_INCOMPLETE",
                partial=HolderBundlePersistResult(
                    governed_request_count=len(request_ids),
                    measured_transport_count=partial_transports,
                    source_request_ids=tuple(request_ids),
                    source_request_coverage=tuple(blocked_coverage),
                    accounting_blocker=True,
                    accounting_blocker_reason=";".join(accounting_reasons),
                ),
                failed_stage=str(key),
                cause=exc,
            ) from exc

        if request_id is not None and request_id not in request_ids:
            request_ids.append(request_id)
        coverage.append(entry)
        if accounting_ok:
            payload = dict(
                getattr(execution.normalized_result, "normalized_payload", None)
                or {}
            )
            for item in payload.get("transport_operation_identities") or ():
                raw = dict(item)
                key_identity = _measured_transport_identity_key(raw)
                if key_identity in transport_identity_keys:
                    accounting_ok = False
                    accounting_blocker = True
                    operation_count = 0
                    entry["terminal_status"] = "BLOCKED"
                    entry["transport_identity_count"] = 0
                    accounting_reasons.append(
                        f"HOLDER_TRANSPORT_IDENTITY_DUPLICATE:request={request_id}"
                    )
                    break
                if str(raw.get("target_identity") or "").lower() != mint.lower():
                    accounting_ok = False
                    accounting_blocker = True
                    operation_count = 0
                    entry["terminal_status"] = "BLOCKED"
                    entry["transport_identity_count"] = 0
                    accounting_reasons.append(
                        "HOLDER_TRANSPORT_IDENTITY_CORRESPONDENCE_MISMATCH:"
                        f"request={request_id}"
                    )
                    break
                transport_identity_keys.add(key_identity)
                transport_identities.append(raw)
        transports += int(operation_count)
        if not accounting_ok:
            accounting_blocker = True
            if reason:
                accounting_reasons.append(reason)

    reason_text = ";".join(accounting_reasons) if accounting_reasons else None
    return HolderBundlePersistResult(
        governed_request_count=len(distinct),
        measured_transport_count=transports,
        source_request_ids=tuple(request_ids),
        source_request_coverage=tuple(coverage),
        accounting_blocker=accounting_blocker,
        accounting_blocker_reason=reason_text,
        transport_identities=tuple(transport_identities),
    )

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
from typing import Any, Mapping

from printer_v1.sources.registry import SOURCE_REGISTRY


OPERATION_CEILING = 45
REQUIRED_DEX_SNAPSHOT_RESERVATION = 2
COMBINED_ZERO_TRANSPORT_VALIDATION = 9
HOLDER_WORST_CASE_GOVERNED_REQUESTS = 3
HOLDER_REQUEST_PURPOSE = "pre_activation_holder_eligibility"
HOLDER_POLICY_VERSION = "v2-9.7e.22"
HOLDER_PARSER_VERSION = "v2-9.7e.22"
MATURATION_THRESHOLD_SECONDS: int | None = None
MATURATION_THRESHOLD_STATE = "UNPROVEN_DISABLED"


class HolderBudgetError(RuntimeError):
    pass


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
    deadline_at: datetime

    @property
    def charged_operations(self) -> int:
        return self.governed_requests + self.zero_transport_operations

    @property
    def available_before_reservation(self) -> int:
        return self.operation_ceiling - self.charged_operations - self.reserved_snapshot_operations

    def candidate_cap(self) -> int:
        return max(0, self.available_before_reservation // HOLDER_WORST_CASE_GOVERNED_REQUESTS)

    def admit_candidate(self, *, now: str | datetime) -> None:
        if _time(now) > self.deadline_at:
            raise HolderBudgetError("HOLDER_CAMPAIGN_DEADLINE_EXPIRED")
        if self.available_before_reservation < HOLDER_WORST_CASE_GOVERNED_REQUESTS:
            raise HolderBudgetError("DEX_SNAPSHOT_RESERVATION_WOULD_BE_BREACHED")


def build_ledger(
    *, pump_operations: int, deadline_at: str | datetime,
    additional_governed_operations: int = 0,
) -> CampaignOperationLedger:
    base_operations = int(pump_operations) + int(additional_governed_operations)
    ledger = CampaignOperationLedger(
        operation_ceiling=OPERATION_CEILING,
        governed_requests=base_operations,
        underlying_transport_operations=base_operations,
        zero_transport_operations=COMBINED_ZERO_TRANSPORT_VALIDATION,
        reserved_snapshot_operations=REQUIRED_DEX_SNAPSHOT_RESERVATION,
        deadline_at=_time(deadline_at),
    )
    if ledger.charged_operations + ledger.reserved_snapshot_operations > OPERATION_CEILING:
        raise HolderBudgetError("CAMPAIGN_BASE_WORK_EXCEEDS_RESERVED_BUDGET")
    return ledger


def persist_ledger(connection: sqlite3.Connection, *, run_id: str, cycle_id: str, ledger: CampaignOperationLedger, now: str) -> None:
    connection.execute(
        """INSERT INTO printer_holder_campaign_operation_ledgers(
            run_id,cycle_id,operation_ceiling,governed_requests,
            underlying_transport_operations,zero_transport_operations,
            reserved_snapshot_operations,deadline_at,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(run_id,cycle_id) DO UPDATE SET
            governed_requests=excluded.governed_requests,
            underlying_transport_operations=excluded.underlying_transport_operations,
            zero_transport_operations=excluded.zero_transport_operations,
            deadline_at=excluded.deadline_at,updated_at=excluded.updated_at""",
        (run_id, cycle_id, ledger.operation_ceiling, ledger.governed_requests,
         ledger.underlying_transport_operations, ledger.zero_transport_operations,
         ledger.reserved_snapshot_operations, ledger.deadline_at.isoformat(), now, now),
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
    for source_name, endpoint_role in (("goplus", "PRIMARY"), ("solana_rpc", "PRIMARY")):
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


def persist_bundle_attempts(
    connection: sqlite3.Connection, *, run_id: str, cycle_id: str,
    mint: str, executions: Mapping[str, Any], created_at: str,
) -> tuple[int, int]:
    """Persist each distinct governed attempt and return request/transport use."""
    from printer_v1.safety.goplus_normalizer import holder_concentration_label_from_goplus

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
    for key, execution in distinct:
        normalized = execution.normalized_result
        payload = dict(normalized.normalized_payload or {})
        is_rpc = key.startswith("holder")
        role = "BACKUP" if key == "holder_backup" else "PRIMARY"
        host = (
            "solana-rpc.publicnode.com" if role == "BACKUP"
            else "api.mainnet-beta.solana.com" if is_rpc
            else "api.gopluslabs.io"
        )
        operation_count = int(payload.get("underlying_operation_count") or (
            2 if is_rpc and execution.response_record is not None else 1
        ))
        transports += operation_count
        returned_mint = str(payload.get("token_mint") or "")
        holder_label = (
            str(payload.get("holder_concentration_label") or "HOLDER_CONCENTRATION_UNKNOWN")
            if is_rpc else holder_concentration_label_from_goplus(payload)
        )
        record_attempt(
            connection, run_id=run_id, cycle_id=cycle_id, mint_identity=mint,
            source_name="solana_rpc" if is_rpc else "goplus",
            endpoint_role=role, redacted_host=host,
            source_request_id=int(execution.request_record.id),
            source_response_id=(int(execution.response_record.id) if execution.response_record else None),
            source_failure_id=(int(execution.failure_record.id) if execution.failure_record else None),
            lineage_response_id=(int(execution.response_record.id) if execution.response_record else None),
            reused_evidence_id=None,
            captured_at=payload.get("captured_at") or normalized.received_at,
            received_at=normalized.received_at,
            source_status=normalized.source_status.value,
            data_quality_label=normalized.data_quality_label.value,
            exact_target=int(bool(returned_mint) and returned_mint.lower() == mint.lower()),
            holder_concentration_label=holder_label,
            rpc_method=(payload.get("rpc_method") or (
                "getTokenLargestAccounts+getTokenSupply" if is_rpc and operation_count == 2
                else "getTokenLargestAccounts" if is_rpc else "HTTP_GET"
            )),
            commitment=payload.get("commitment") or ("finalized" if is_rpc else None),
            context_slot=payload.get("context_slot"),
            underlying_operation_count=operation_count,
            failure_subtype=normalized.failure_type,
            retry_after_at=normalized.retry_after_at,
            created_at=created_at,
        )
    return len(distinct), transports

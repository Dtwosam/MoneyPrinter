"""Bounded four-token proof integration contracts for Printer V1 V2-9.8B.

This module is deliberately non-runnable. It provides the exact 4-token / 2-cycle
proof policy, cycle-aware step namespace, durable Scheduler-owner resolution,
cycle-scoped factory-step accounting, deterministic wake ordering, and aggregate
proof acceptance used by the later canonical-factory hook.

It performs no source fetching, discovery, memory generation, provider changes,
12h/24h activation, retrieval, or financial action.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import re
import sqlite3
from typing import Any, Mapping, Sequence

from printer_v1.operator_cli.authoritative_admission_health import (
    AdmissionHealthProjection,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
    MultiCycleCampaignBinding,
    MultiCycleCampaignSnapshot,
    load_multi_cycle_campaign_snapshot,
)
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    AdmissionDecision,
    MIN_CYCLE_ADMISSION_SPACING_SECONDS,
    MultiCycleCapacityPolicy,
)


FOUR_TOKEN_PROOF_THROUGH_4H_TOKENS = 4
FOUR_TOKEN_PROOF_ACTIVE_CYCLES = 2
FOUR_TOKEN_PROOF_TOTAL_CYCLES = 2
FOUR_TOKEN_PROOF_TOKENS_PER_CYCLE = 2
FOUR_TOKEN_PROOF_MIN_SPACING_SECONDS = MIN_CYCLE_ADMISSION_SPACING_SECONDS

_STEP_KEY_RE = re.compile(
    r"^t(?P<slot>[12])_(?:(?:c(?P<cycle>[0-9]{4})_))?(?P<suffix>[A-Za-z0-9][A-Za-z0-9_.:-]*)$"
)


class FourTokenProofPolicyError(ValueError):
    """Fail-closed four-token proof configuration/identity error."""


class FourTokenAggregateError(ValueError):
    """Fail-closed four-token aggregate acceptance error."""


@dataclass(frozen=True)
class ParsedCycleStepKey:
    slot_ordinal: int
    cycle_ordinal: int
    suffix: str


@dataclass(frozen=True)
class OwnedCycleForSchedulerJob:
    scheduler_work_id: str
    campaign_id: str
    campaign_run_id: str
    cycle_id: str
    token_slot_id: str
    window_id: str
    factory_run_id: str
    stage_id: str
    work_scope: str
    target_category: str
    target_identity: str


@dataclass(frozen=True)
class FourTokenFactoryWake:
    at: datetime
    reason: str


@dataclass(frozen=True)
class FourTokenControllerReadiness:
    """One read-only persisted admission evaluation plus deterministic wake."""

    snapshot: MultiCycleCampaignSnapshot
    wake: FourTokenFactoryWake


class FourTokenAdmissionDispositionKind(StrEnum):
    BLOCKED = "BLOCKED"
    DRAIN = "DRAIN"
    COMPLETE = "COMPLETE"
    LIFECYCLE_WORK = "LIFECYCLE_WORK"
    PROOF_DEADLINE = "PROOF_DEADLINE"
    CYCLE_ADMISSION = "CYCLE_ADMISSION"
    REARM = "REARM"


@dataclass(frozen=True)
class FourTokenAdmissionDisposition:
    kind: FourTokenAdmissionDispositionKind
    reason: str
    at: datetime | None
    admission_allowed: bool


@dataclass(frozen=True)
class FourTokenProofController:
    """Proof-only read-side controller; admission and discovery remain separate."""

    policy: MultiCycleCapacityPolicy

    @classmethod
    def exact(cls) -> "FourTokenProofController":
        return cls(policy=build_four_token_proof_policy())

    def evaluate_factory_wake(
        self,
        connection: sqlite3.Connection,
        *,
        binding: MultiCycleCampaignBinding,
        now: datetime,
        next_due_work_at: datetime | None,
        proof_deadline: datetime,
        admission_health: MultiCycleAdmissionHealth,
    ) -> FourTokenControllerReadiness:
        snapshot = load_multi_cycle_campaign_snapshot(
            connection,
            binding=binding,
            policy=self.policy,
            now=now,
            health=admission_health,
        )
        evaluation = snapshot.admission_evaluation
        next_admission_at: datetime | None = None
        if evaluation.decision == AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE:
            next_admission_at = now
        elif (
            evaluation.decision == AdmissionDecision.DEFER
            and evaluation.reason == "minimum_admission_spacing_not_elapsed"
        ):
            last_admitted_at = snapshot.session.last_cycle_admitted_at
            if last_admitted_at is None:
                raise FourTokenProofPolicyError(
                    "spacing defer requires persisted last-cycle admission time"
                )
            next_admission_at = _utc(
                last_admitted_at,
                "last_cycle_admitted_at",
            ) + timedelta(seconds=self.policy.min_admission_spacing_seconds)

        return FourTokenControllerReadiness(
            snapshot=snapshot,
            wake=next_four_token_factory_wake(
                now=now,
                next_due_work_at=next_due_work_at,
                next_admission_at=next_admission_at,
                proof_deadline=proof_deadline,
            ),
        )


def decide_four_token_admission_disposition(
    *,
    readiness: FourTokenControllerReadiness,
    health_projection: AdmissionHealthProjection,
    policy: MultiCycleCapacityPolicy,
    now: datetime,
    next_due_work_at: datetime | None,
    proof_deadline: datetime,
    relevant_pending_lifecycle_work: bool,
) -> FourTokenAdmissionDisposition:
    """Choose one pure bounded action without polling, admission, or mutation."""
    if not isinstance(readiness, FourTokenControllerReadiness):
        raise FourTokenProofPolicyError("readiness must be FourTokenControllerReadiness")
    if not isinstance(health_projection, AdmissionHealthProjection):
        raise FourTokenProofPolicyError("health projection is required")
    try:
        policy.validate()
    except ValueError as exc:
        raise FourTokenProofPolicyError(str(exc)) from exc
    if type(relevant_pending_lifecycle_work) is not bool:
        raise FourTokenProofPolicyError(
            "relevant_pending_lifecycle_work must be boolean"
        )

    current = _utc(now, "now")
    deadline = _utc(proof_deadline, "proof_deadline")
    due = (
        _utc(next_due_work_at, "next_due_work_at")
        if next_due_work_at is not None
        else None
    )
    health = health_projection.health

    if health.cancellation_requested:
        return FourTokenAdmissionDisposition(
            FourTokenAdmissionDispositionKind.DRAIN,
            "CANCELLATION_REQUESTED",
            None,
            False,
        )
    stop_gates = (
        (not health.lease_healthy, "LEASE_UNHEALTHY"),
        (not health.db_healthy, "DB_UNHEALTHY"),
        (health.shared_terminal_condition, "SHARED_TERMINAL_CONDITION"),
        (not health.campaign_supervision_healthy, "CAMPAIGN_SUPERVISION_UNHEALTHY"),
    )
    for blocked, reason in stop_gates:
        if blocked:
            return FourTokenAdmissionDisposition(
                FourTokenAdmissionDispositionKind.BLOCKED,
                reason,
                None,
                False,
            )

    evaluation = readiness.snapshot.admission_evaluation
    if evaluation.decision == AdmissionDecision.BLOCKED:
        return FourTokenAdmissionDisposition(
            FourTokenAdmissionDispositionKind.BLOCKED,
            evaluation.reason,
            None,
            False,
        )
    if evaluation.decision == AdmissionDecision.DRAIN:
        return FourTokenAdmissionDisposition(
            FourTokenAdmissionDispositionKind.DRAIN,
            evaluation.reason,
            None,
            False,
        )
    if evaluation.decision == AdmissionDecision.COMPLETE:
        return FourTokenAdmissionDisposition(
            FourTokenAdmissionDispositionKind.COMPLETE,
            evaluation.reason,
            None,
            False,
        )

    if relevant_pending_lifecycle_work and due is not None and due <= current:
        return FourTokenAdmissionDisposition(
            FourTokenAdmissionDispositionKind.LIFECYCLE_WORK,
            "DUE_LIFECYCLE_WORK",
            current,
            False,
        )
    if deadline <= current:
        return FourTokenAdmissionDisposition(
            FourTokenAdmissionDispositionKind.PROOF_DEADLINE,
            "PROOF_DEADLINE_REACHED",
            current,
            False,
        )
    if evaluation.decision == AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE:
        return FourTokenAdmissionDisposition(
            FourTokenAdmissionDispositionKind.CYCLE_ADMISSION,
            "ADMISSION_READY",
            current,
            True,
        )
    if evaluation.decision != AdmissionDecision.DEFER:
        raise FourTokenProofPolicyError("unsupported admission disposition")

    rearm_at: datetime | None = None
    rearm_reason: str | None = None
    if evaluation.reason == "minimum_admission_spacing_not_elapsed":
        last_admitted_at = readiness.snapshot.session.last_cycle_admitted_at
        if last_admitted_at is None:
            return FourTokenAdmissionDisposition(
                FourTokenAdmissionDispositionKind.BLOCKED,
                "SPACING_BOUNDARY_EVIDENCE_MISSING",
                None,
                False,
            )
        rearm_at = _utc(
            last_admitted_at,
            "last_cycle_admitted_at",
        ) + timedelta(seconds=policy.min_admission_spacing_seconds)
        rearm_reason = "PERSISTED_ADMISSION_SPACING_BOUNDARY"
    elif health_projection.recheck_at is not None:
        candidate = _utc(health_projection.recheck_at, "health_recheck_at")
        if candidate > current:
            rearm_at = candidate
            rearm_reason = "AUTHORITATIVE_HEALTH_RECHECK"

    candidates: list[
        tuple[datetime, int, FourTokenAdmissionDispositionKind, str]
    ] = []
    if (
        health_projection.recheck_on_lifecycle_change
        and relevant_pending_lifecycle_work
        and due is not None
        and due > current
    ):
        candidates.append(
            (
                due,
                0,
                FourTokenAdmissionDispositionKind.LIFECYCLE_WORK,
                "LIFECYCLE_STATE_CHANGE_RECHECK",
            )
        )
    if rearm_at is not None and rearm_at > current and rearm_reason is not None:
        candidates.append(
            (
                rearm_at,
                2,
                FourTokenAdmissionDispositionKind.REARM,
                rearm_reason,
            )
        )
    if not candidates:
        return FourTokenAdmissionDisposition(
            FourTokenAdmissionDispositionKind.BLOCKED,
            "NO_AUTHORITATIVE_REARM_BOUNDARY",
            None,
            False,
        )
    candidates.append(
        (
            deadline,
            1,
            FourTokenAdmissionDispositionKind.PROOF_DEADLINE,
            "PROOF_DEADLINE_REACHED",
        )
    )
    at, _, kind, reason = min(candidates, key=lambda item: (item[0], item[1]))
    return FourTokenAdmissionDisposition(kind, reason, at, False)


def build_four_token_proof_policy(
    *,
    configured_through_4h_tokens: int = FOUR_TOKEN_PROOF_THROUGH_4H_TOKENS,
    configured_active_cycles: int = FOUR_TOKEN_PROOF_ACTIVE_CYCLES,
    total_cycle_admissions: int = FOUR_TOKEN_PROOF_TOTAL_CYCLES,
    tokens_per_cycle: int = FOUR_TOKEN_PROOF_TOKENS_PER_CYCLE,
    minimum_spacing_seconds: int = FOUR_TOKEN_PROOF_MIN_SPACING_SECONDS,
    intake_duration_seconds: int = 18_000,
) -> MultiCycleCapacityPolicy:
    """Return the exact proof policy and reject any attempt to widen it.

    The duration is only a finite implementation/readiness configuration field;
    later proof readiness must derive the exact wall-time authority needed for
    the staggered second cycle. This builder never authorizes execution.
    """
    exact = {
        "configured_through_4h_tokens": FOUR_TOKEN_PROOF_THROUGH_4H_TOKENS,
        "configured_active_cycles": FOUR_TOKEN_PROOF_ACTIVE_CYCLES,
        "total_cycle_admissions": FOUR_TOKEN_PROOF_TOTAL_CYCLES,
        "tokens_per_cycle": FOUR_TOKEN_PROOF_TOKENS_PER_CYCLE,
    }
    supplied = {
        "configured_through_4h_tokens": configured_through_4h_tokens,
        "configured_active_cycles": configured_active_cycles,
        "total_cycle_admissions": total_cycle_admissions,
        "tokens_per_cycle": tokens_per_cycle,
    }
    for key, expected in exact.items():
        if type(supplied[key]) is not int or supplied[key] != expected:
            raise FourTokenProofPolicyError(
                f"four-token proof requires {key}={expected}"
            )
    if (
        type(minimum_spacing_seconds) is not int
        or minimum_spacing_seconds < FOUR_TOKEN_PROOF_MIN_SPACING_SECONDS
    ):
        raise FourTokenProofPolicyError(
            "four-token proof admission spacing cannot be less than 300 seconds"
        )
    if type(intake_duration_seconds) is not int or intake_duration_seconds <= 0:
        raise FourTokenProofPolicyError("four-token proof duration must be positive")

    policy = MultiCycleCapacityPolicy(
        configured_through_4h_token_ceiling=configured_through_4h_tokens,
        configured_active_cycle_ceiling=configured_active_cycles,
        total_cycle_admission_ceiling=total_cycle_admissions,
        intake_duration_seconds=intake_duration_seconds,
        min_admission_spacing_seconds=minimum_spacing_seconds,
    )
    try:
        policy.validate()
    except ValueError as exc:
        raise FourTokenProofPolicyError(str(exc)) from exc
    return policy


def cycle_step_key(*, slot_ordinal: int, cycle_ordinal: int, suffix: str) -> str:
    """Return the canonical factory-step identity for one cycle-owned token slot."""
    if type(slot_ordinal) is not int or slot_ordinal not in (1, 2):
        raise FourTokenProofPolicyError("slot ordinal must be exactly 1 or 2")
    if type(cycle_ordinal) is not int or cycle_ordinal <= 0:
        raise FourTokenProofPolicyError("cycle ordinal must be positive")
    if not isinstance(suffix, str) or not suffix or suffix != suffix.strip():
        raise FourTokenProofPolicyError("step-key suffix must be a non-empty exact string")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", suffix):
        raise FourTokenProofPolicyError("step-key suffix has unsupported shape")
    if cycle_ordinal == 1:
        return f"t{slot_ordinal}_{suffix}"
    if cycle_ordinal > 9999:
        raise FourTokenProofPolicyError("cycle ordinal exceeds step-key namespace")
    return f"t{slot_ordinal}_c{cycle_ordinal:04d}_{suffix}"


def parse_cycle_step_key(value: str) -> ParsedCycleStepKey:
    """Parse canonical cycle-aware step identity while retaining t1/t2 prefix law."""
    if not isinstance(value, str):
        raise FourTokenProofPolicyError("step key must be a string")
    matched = _STEP_KEY_RE.fullmatch(value)
    if matched is None:
        raise FourTokenProofPolicyError("step key is not a canonical cycle step key")
    slot = int(matched.group("slot"))
    raw_cycle = matched.group("cycle")
    suffix = str(matched.group("suffix"))
    if raw_cycle is None:
        if re.match(r"^c[0-9]+_", suffix):
            raise FourTokenProofPolicyError(
                "step key has a malformed or ambiguous cycle namespace"
            )
        cycle = 1
    else:
        cycle = int(raw_cycle)
        if cycle < 2:
            raise FourTokenProofPolicyError(
                "namespaced cycle ordinal must be at least 2"
            )
    return ParsedCycleStepKey(slot_ordinal=slot, cycle_ordinal=cycle, suffix=suffix)


def cycle_token_usage_key(step_key: str) -> str:
    """Return a cycle+slot usage identity so later t1/t2 streams never merge."""
    parsed = parse_cycle_step_key(step_key)
    return f"c{parsed.cycle_ordinal:04d}:t{parsed.slot_ordinal}"


def _required_identity(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise FourTokenProofPolicyError(f"{label} must be a non-empty exact string")
    return value


def resolve_owned_cycle_for_scheduler_job(
    connection: sqlite3.Connection,
    *,
    scheduler_job_id: int,
    campaign_id: str,
    campaign_run_id: str,
    factory_run_id: str,
) -> OwnedCycleForSchedulerJob:
    """Resolve one exact stage-scoped campaign owner for a canonical Scheduler job."""
    if type(scheduler_job_id) is not int or scheduler_job_id <= 0:
        raise FourTokenProofPolicyError("scheduler_job_id must be positive")
    campaign = _required_identity(campaign_id, "campaign_id")
    run = _required_identity(campaign_run_id, "campaign_run_id")
    factory = _required_identity(factory_run_id, "factory_run_id")
    rows = connection.execute(
        """SELECT scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,
                  window_id,factory_run_id,stage_id,work_scope,target_category,
                  target_identity
           FROM printer_memory_factory_campaign_scheduler_work
           WHERE scheduler_job_id=?
             AND ownership_contract_version='V2_STAGE_SCOPED'
             AND campaign_id=? AND run_id=? AND factory_run_id=?
           ORDER BY scheduler_work_id""",
        (scheduler_job_id, campaign, run, factory),
    ).fetchall()
    if len(rows) != 1:
        raise FourTokenProofPolicyError(
            "canonical Scheduler job does not have exactly one proof-cycle owner"
        )
    row = rows[0]
    values = {
        "scheduler_work_id": row[0],
        "campaign_id": row[1],
        "campaign_run_id": row[2],
        "cycle_id": row[3],
        "token_slot_id": row[4],
        "window_id": row[5],
        "factory_run_id": row[6],
        "stage_id": row[7],
        "work_scope": row[8],
        "target_category": row[9],
        "target_identity": row[10],
    }
    for key, value in values.items():
        values[key] = _required_identity(value, key)
    if values["work_scope"] != "WINDOW_LIFECYCLE":
        raise FourTokenProofPolicyError("proof lifecycle job has non-lifecycle owner")
    if values["target_category"] != "CAMPAIGN_WINDOW":
        raise FourTokenProofPolicyError("proof lifecycle job target is not campaign window")
    if values["target_identity"] != values["window_id"]:
        raise FourTokenProofPolicyError("proof lifecycle job target/window identity mismatch")
    return OwnedCycleForSchedulerJob(**values)


def cycle_scoped_factory_step_ids(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
    factory_run_id: str,
    cycle_id: str,
) -> tuple[int, ...]:
    """Return only factory step ids owned by one cycle through canonical jobs."""
    campaign = _required_identity(campaign_id, "campaign_id")
    run = _required_identity(campaign_run_id, "campaign_run_id")
    factory = _required_identity(factory_run_id, "factory_run_id")
    cycle = _required_identity(cycle_id, "cycle_id")
    rows = connection.execute(
        """SELECT s.id,s.scheduler_job_id,w.scheduler_work_id
           FROM printer_memory_factory_run_steps AS s
           JOIN printer_memory_factory_campaign_scheduler_work AS w
             ON w.scheduler_job_id=s.scheduler_job_id
            AND w.ownership_contract_version='V2_STAGE_SCOPED'
           WHERE s.run_id=?
             AND w.campaign_id=? AND w.run_id=? AND w.factory_run_id=?
             AND w.cycle_id=? AND w.work_scope='WINDOW_LIFECYCLE'
           ORDER BY s.id,w.scheduler_work_id""",
        (factory, campaign, run, factory, cycle),
    ).fetchall()
    ids = [int(row[0]) for row in rows]
    if len(ids) != len(set(ids)):
        raise FourTokenProofPolicyError(
            "cycle-scoped factory step has ambiguous Scheduler ownership"
        )
    return tuple(ids)


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime):
        raise FourTokenProofPolicyError(f"{label} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise FourTokenProofPolicyError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def next_four_token_factory_wake(
    *,
    now: datetime,
    next_due_work_at: datetime | None,
    next_admission_at: datetime | None,
    proof_deadline: datetime,
) -> FourTokenFactoryWake:
    """Choose one deterministic wake boundary; lifecycle work wins equal-time ties."""
    current = _utc(now, "now")
    deadline = _utc(proof_deadline, "proof_deadline")
    if deadline < current:
        return FourTokenFactoryWake(at=current, reason="PROOF_DEADLINE")

    candidates: list[tuple[datetime, int, str]] = [(deadline, 1, "PROOF_DEADLINE")]
    if next_due_work_at is not None:
        due = max(current, _utc(next_due_work_at, "next_due_work_at"))
        candidates.append((due, 0, "LIFECYCLE_WORK"))
    if next_admission_at is not None:
        admission = max(current, _utc(next_admission_at, "next_admission_at"))
        # Deadline outranks a fresh admission at the exact same instant.
        candidates.append((admission, 2, "CYCLE_ADMISSION"))
    selected = min(candidates, key=lambda item: (item[0], item[1]))
    return FourTokenFactoryWake(at=selected[0], reason=selected[2])


def aggregate_four_token_cycle_acceptance(
    cycle_packages: Sequence[Mapping[str, Any]],
    *,
    shared: Mapping[str, Any],
) -> dict[str, Any]:
    """Combine two cycle-local two-token packages into one structural proof verdict.

    Memory quality is carried as evidence and never treated as a clean-memory quota.
    Structural/accounting/ownership failures raise instead of being diluted by a
    healthy peer cycle.
    """
    packages = [dict(item) for item in cycle_packages]
    if len(packages) != FOUR_TOKEN_PROOF_TOTAL_CYCLES:
        raise FourTokenAggregateError("four-token proof requires exactly two cycle packages")
    ordered = sorted(packages, key=lambda item: int(item.get("cycle_ordinal", 0)))
    if [int(item.get("cycle_ordinal", 0)) for item in ordered] != [1, 2]:
        raise FourTokenAggregateError("cycle package ordinals must be exactly 1 and 2")

    shared_factory = _aggregate_required(shared, "factory_run_id")
    _aggregate_required(shared, "campaign_id")
    _aggregate_required(shared, "campaign_run_id")
    targets: list[tuple[int, int]] = []
    quality: list[str] = []
    cycle_ids: list[str] = []
    for package in ordered:
        cycle_id = _aggregate_required(package, "cycle_id")
        cycle_ids.append(cycle_id)
        if _aggregate_required(package, "factory_run_id") != shared_factory:
            raise FourTokenAggregateError("cycle package factory-run identity mismatch")
        if package.get("structurally_safe") is not True:
            raise FourTokenAggregateError(f"cycle package is structurally unsafe: {cycle_id}")
        selected = package.get("selected_targets")
        if not isinstance(selected, Sequence) or isinstance(selected, (str, bytes)) or len(selected) != 2:
            raise FourTokenAggregateError("each proof cycle must carry exactly two targets")
        for target in selected:
            if not isinstance(target, Mapping):
                raise FourTokenAggregateError("selected target must be an object")
            try:
                identity = (int(target["token_id"]), int(target["pair_id"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise FourTokenAggregateError("selected target identity is invalid") from exc
            if identity[0] <= 0 or identity[1] <= 0:
                raise FourTokenAggregateError("selected target identity must be positive")
            targets.append(identity)
        raw_quality = package.get("memory_quality") or []
        if not isinstance(raw_quality, Sequence) or isinstance(raw_quality, (str, bytes)):
            raise FourTokenAggregateError("memory quality outcomes must be a sequence")
        quality.extend(str(item) for item in raw_quality)

    if len(set(cycle_ids)) != 2:
        raise FourTokenAggregateError("proof cycle identities must be distinct")
    if len(targets) != 4 or len(set(targets)) != 4:
        raise FourTokenAggregateError("four-token proof targets must be four distinct token/pair identities")

    try:
        spacing = int(shared.get("admission_spacing_seconds"))
        peak = int(shared.get("active_through_4h_peak"))
    except (TypeError, ValueError) as exc:
        raise FourTokenAggregateError("shared capacity evidence is malformed") from exc
    if spacing < FOUR_TOKEN_PROOF_MIN_SPACING_SECONDS:
        raise FourTokenAggregateError("second cycle was admitted before 300 seconds")
    if peak != FOUR_TOKEN_PROOF_THROUGH_4H_TOKENS:
        raise FourTokenAggregateError("proof did not establish exactly four-token peak concurrency")

    required_true = (
        "aggregate_budget_within_ceiling",
        "zero_active_work",
        "zero_forbidden_deltas",
    )
    for key in required_true:
        if shared.get(key) is not True:
            raise FourTokenAggregateError(f"shared proof check failed: {key}")
    for key in ("restart_created", "successor_created", "long_windows_activated"):
        if shared.get(key) is not False:
            raise FourTokenAggregateError(f"forbidden shared proof state: {key}")

    return {
        "pass": True,
        "verdict": "FOUR_TOKEN_CAPACITY_PROOF_STRUCTURAL_PASS",
        "cycle_count": 2,
        "cycle_ids": tuple(cycle_ids),
        "selected_target_count": 4,
        "selected_targets": tuple(targets),
        "active_through_4h_peak": peak,
        "admission_spacing_seconds": spacing,
        "memory_quality_outcomes": tuple(quality),
        "memory_quality_is_not_pass_quota": True,
        "factory_run_id": shared_factory,
    }


def _aggregate_required(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value or value != value.strip():
        raise FourTokenAggregateError(f"aggregate proof requires {key}")
    return value

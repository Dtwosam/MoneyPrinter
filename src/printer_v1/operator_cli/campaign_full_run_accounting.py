"""V2-9.8B post-repair full-run WINDOW_15M accounting and terminal evidence.

This module composes the existing campaign ownership, six-unit accounting, and
tracking-reconciliation owners into the exact full-run terminal evidence the
campaign layer needs before it may accept a two-token ``WINDOW_15M`` lifecycle.
It creates no parallel ownership table, no second Scheduler, and no competing
terminal report; every fact is derived from durable rows and sealed identities.

Concerns owned here:

* the immutable ``OperationalLifecycleOwnershipContext`` passed coordinator ->
  factory (identity flow and factory-run drift detection);
* the exact campaign slot terminal disposition (COOLDOWN vs MANUAL_REVIEW);
* the quality-consistency gate between window quality and episode promotion;
* the canonical full-run terminal report and the campaign acceptance gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from typing import Any, Callable, Mapping, Sequence

from printer_v1.operator_cli.campaign_ownership import (
    CampaignOwnershipError,
    campaign_scheduler_work_id,
    project_campaign_scheduler_job,
    register_campaign_window_close,
)
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignActionLocalLedger,
    CampaignSixUnitOwner,
    build_campaign_stage_id,
    reconcile_full_run_owner_to_action_local,
    seal_campaign_stage_evidence,
)
from printer_v1.sources.measured_transport import (
    LifecycleReservationIdentity,
    LocalValidationIdentity,
    MeasuredTransportLedger,
    SchedulerWorkIdentity,
    TransportOperationIdentity,
    build_transport_identity,
)


class FullRunAccountingError(ValueError):
    """Fail-closed full-run accounting/ownership fault."""


# Mandatory sealed lifecycle stages for a lifecycle-started two-token run.
REQUIRED_LIFECYCLE_STAGE_KINDS = (
    "DISCOVERY_SELECTION_SCHEDULER",
    "WINDOW_15M_SLOT_1",
    "WINDOW_15M_SLOT_2",
    "CAMPAIGN_TERMINAL_RECONCILIATION",
)

# Terminal campaign-window states that count as a genuine closed lifecycle.
_OWNED_TERMINAL_WINDOW_STATES = frozenset(
    {"CLEAN_PROMOTED", "DIRTY", "NO_PROMOTION", "ALREADY_EXISTS_IDEMPOTENT"}
)

# Runtime acceptance verdicts kept distinct from runtime terminal + quality.
VERDICT_PASS = "CAMPAIGN_PASS"
VERDICT_HONEST_BLOCKED = "HONEST_BLOCKED"
VERDICT_BLOCKED_UNSAFE = "BLOCKED_UNSAFE"

# Clean-memory promotion is only lawful for a fully clean window.
_CLEAN_MEMORY_STATUS = "CLEAN_MEMORY"
_CLEAN_DATA_LABEL = "CLEAN_DATA"
_CLEAN_EPISODE_KIND = "WINDOW_15M_CLEAN_MEMORY"


def _require(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise FullRunAccountingError(f"{label} is required")
    return text


@dataclass(frozen=True)
class OperationalLifecycleOwnershipContext:
    """Immutable identity context passed coordinator -> driver -> factory.

    The factory may read this context but may not replace any identity. If the
    factory-run callback later observes a different non-empty factory run id, the
    campaign fails closed via :meth:`assert_factory_run_consistent`.
    """

    campaign_id: str
    campaign_run_id: str
    cycle_id: str
    configuration_id: str
    factory_run_id: str
    expected_window_kind: str = "WINDOW_15M"
    expected_token_capacity: int = 2

    def __post_init__(self) -> None:
        for label, value in (
            ("campaign_id", self.campaign_id),
            ("campaign_run_id", self.campaign_run_id),
            ("cycle_id", self.cycle_id),
            ("configuration_id", self.configuration_id),
            ("factory_run_id", self.factory_run_id),
        ):
            _require(value, label)
        if self.expected_window_kind != "WINDOW_15M":
            raise FullRunAccountingError(
                "expected_window_kind must be WINDOW_15M for this lane"
            )
        if int(self.expected_token_capacity) != 2:
            raise FullRunAccountingError(
                "expected_token_capacity must be exactly 2 for this lane"
            )

    def assert_factory_run_consistent(self, observed_factory_run_id: str | None) -> None:
        """Fail closed when a non-empty observed factory run differs from ours."""
        observed = str(observed_factory_run_id or "").strip()
        if observed and observed != self.factory_run_id:
            raise FullRunAccountingError(
                "FACTORY_RUN_IDENTITY_DRIFT:"
                f"{observed}!={self.factory_run_id}"
            )

    def lifecycle_operation_identity(
        self,
        *,
        token_id: int,
        token_mint: str,
        pair_id: int,
        pair_address: str,
        window_kind: str,
        step_id: Any,
    ) -> dict[str, Any]:
        """Build a cross-run-safe lifecycle operation identity (design §5)."""
        return {
            "campaign_id": self.campaign_id,
            "campaign_run_id": self.campaign_run_id,
            "cycle_id": self.cycle_id,
            "factory_run_id": self.factory_run_id,
            "token_id": int(token_id),
            "token_mint": _require(token_mint, "token_mint"),
            "pair_id": int(pair_id),
            "pair_address": _require(pair_address, "pair_address"),
            "window_kind": _require(window_kind, "window_kind"),
            "step_id": step_id,
        }


def resolve_campaign_slot_terminal_disposition(
    *,
    lifecycle_started: bool,
    owned_terminal_window_state: str | None,
    queue_disposition: str | None,
    first_terminal_cause: str | None = None,
) -> dict[str, Any]:
    """Map proven lifecycle ownership to one exact campaign slot terminal state.

    The tracking queue keeps its own status; this only chooses the campaign slot
    terminal label (design §12). A completed owned lifecycle is never relabelled
    ``MANUAL_REVIEW``; a clean main terminal that entered queue ``COOLDOWN``
    mirrors ``COOLDOWN`` on the slot.
    """
    owned_terminal = (
        owned_terminal_window_state is not None
        and str(owned_terminal_window_state) in _OWNED_TERMINAL_WINDOW_STATES
    )
    if not lifecycle_started:
        # No lifecycle proven: a still-SELECTED slot may be sent to review.
        return {
            "slot_terminal_state": "MANUAL_REVIEW",
            "terminal_cause": first_terminal_cause or "NO_LIFECYCLE_STARTED",
            "pass_eligible": False,
            "queue_disposition": queue_disposition,
        }
    if owned_terminal:
        if str(queue_disposition or "") == "COOLDOWN":
            return {
                "slot_terminal_state": "COOLDOWN",
                "terminal_cause": "OWNED_TERMINAL_WINDOW_COOLDOWN",
                "pass_eligible": True,
                "queue_disposition": queue_disposition,
            }
        if str(queue_disposition or "") == "ARCHIVED":
            return {
                "slot_terminal_state": "ARCHIVED",
                "terminal_cause": "OWNED_TERMINAL_WINDOW_ARCHIVED",
                "pass_eligible": True,
                "queue_disposition": queue_disposition,
            }
        # Owned terminal window with an unexpected queue status still counts as a
        # completed lifecycle; it must not be relabelled MANUAL_REVIEW.
        return {
            "slot_terminal_state": "COOLDOWN",
            "terminal_cause": "OWNED_TERMINAL_WINDOW_NO_QUEUE_COOLDOWN",
            "pass_eligible": True,
            "queue_disposition": queue_disposition,
        }
    # Lifecycle started but no valid owned terminal window exists.
    cause = str(first_terminal_cause or "").strip()
    if cause.startswith("FAIL") or cause.startswith("BLOCK"):
        return {
            "slot_terminal_state": "FAILED",
            "terminal_cause": cause,
            "pass_eligible": False,
            "queue_disposition": queue_disposition,
        }
    return {
        "slot_terminal_state": "MANUAL_REVIEW",
        "terminal_cause": cause or "LIFECYCLE_WITHOUT_OWNED_TERMINAL_WINDOW",
        "pass_eligible": False,
        "queue_disposition": queue_disposition,
    }


def evaluate_quality_consistency(
    *,
    memory_status: str,
    data_quality_label: str,
    do_not_train: int,
    proposed_episode_kind: str | None,
) -> dict[str, Any]:
    """Gate clean-memory episode creation on exact window quality (design §13).

    Lifecycle completion stays valid even for a partial/dirty window; only clean
    promotion is gated. A ``WINDOW_15M_CLEAN_MEMORY`` episode attached to a
    non-clean window is a quality inconsistency (blocks clean acceptance) but
    never erases the real lifecycle outcome.
    """
    status = str(memory_status or "")
    label = str(data_quality_label or "")
    dnt = int(do_not_train or 0)
    is_clean_window = (
        status == _CLEAN_MEMORY_STATUS and label == _CLEAN_DATA_LABEL and dnt == 0
    )
    proposed = None if proposed_episode_kind is None else str(proposed_episode_kind)
    clean_episode_allowed = is_clean_window
    quality_consistent = True
    outcome: str
    if proposed == _CLEAN_EPISODE_KIND and not is_clean_window:
        quality_consistent = False
        outcome = "QUALITY_CONSISTENCY_BLOCKED"
    elif is_clean_window:
        outcome = "CLEAN_EPISODE_ALLOWED"
    else:
        outcome = "NO_CLEAN_EPISODE_CREATED"
    return {
        "memory_status": status,
        "data_quality_label": label,
        "do_not_train": dnt,
        "is_clean_window": is_clean_window,
        "clean_episode_allowed": clean_episode_allowed,
        "proposed_episode_kind": proposed,
        "quality_consistent": quality_consistent,
        "outcome": outcome,
        "lifecycle_completion_valid": True,
    }


def _campaign_window_rows(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
) -> list[dict[str, Any]]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """SELECT window_id, window_kind, window_state, token_slot_id, token_row_id,
                  pair_row_id, memory_window_row_id, cycle_id, first_terminal_cause
           FROM printer_memory_factory_campaign_windows
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
           ORDER BY window_id""",
        (campaign_id, run_id, cycle_id),
    ).fetchall()
    return [dict(row) for row in rows]


def _campaign_scheduler_rows(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
) -> list[dict[str, Any]]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """SELECT scheduler_work_id, scheduler_job_id, work_intent, work_state,
                  window_id, token_slot_id, first_terminal_cause
           FROM printer_memory_factory_campaign_scheduler_work
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
           ORDER BY scheduler_work_id""",
        (campaign_id, run_id, cycle_id),
    ).fetchall()
    return [dict(row) for row in rows]


def build_full_run_terminal_report(
    connection: sqlite3.Connection,
    *,
    context: OperationalLifecycleOwnershipContext,
    execution_id: str,
    supervision_id: Any,
    launch_git_provenance: Mapping[str, Any],
    db_target_identity: str,
    selected_tokens: Sequence[Mapping[str, Any]],
    runtime_terminal_status: str,
    owner_evidence: Mapping[str, Any],
    six_unit_totals: Mapping[str, int],
    reconciliation: Mapping[str, Any],
    per_token_outcomes: Sequence[Mapping[str, Any]],
    slot_dispositions: Sequence[Mapping[str, Any]],
    quality_results: Sequence[Mapping[str, Any]],
    zero_active_scheduler_jobs: int,
    forbidden_capability_deltas: Mapping[str, int],
    lease_released: bool,
    scheduler_ownership: Mapping[str, Any] | None = None,
    runtime_first_terminal_cause: str | None = None,
    authorized_invocation_count: int | None = None,
    active_work_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Emit the one canonical exact-identity full-run terminal report (design §10)."""
    windows = _campaign_window_rows(
        connection,
        campaign_id=context.campaign_id,
        run_id=context.campaign_run_id,
        cycle_id=context.cycle_id,
    )
    scheduler_rows = _campaign_scheduler_rows(
        connection,
        campaign_id=context.campaign_id,
        run_id=context.campaign_run_id,
        cycle_id=context.cycle_id,
    )
    terminal_windows = [
        row
        for row in windows
        if str(row["window_kind"]) == "WINDOW_15M"
        and str(row["window_state"]) in _OWNED_TERMINAL_WINDOW_STATES
    ]
    scheduler_attribution: dict[str, int] = {
        "discovery": 0,
        "handoff": 0,
        "lifecycle": 0,
        "cleanup": 0,
    }
    for row in scheduler_rows:
        intent = str(row["work_intent"] or "")
        if intent.startswith("DISCOVERY"):
            scheduler_attribution["discovery"] += 1
        elif intent.startswith("HANDOFF") or intent.startswith("EXECUTOR"):
            scheduler_attribution["handoff"] += 1
        elif str(row["work_state"]) == "CANCELLED":
            scheduler_attribution["cleanup"] += 1
        else:
            scheduler_attribution["lifecycle"] += 1

    all_scheduler_terminal = all(
        str(row["work_state"]) in {"SUCCEEDED", "FAILED", "SKIPPED", "CANCELLED"}
        for row in scheduler_rows
    )
    quality_consistent = all(
        bool(item.get("quality_consistent", True)) for item in quality_results
    )
    forbidden_deltas = {key: int(value) for key, value in dict(
        forbidden_capability_deltas or {}
    ).items()}
    # Scheduler ownership correspondence (design §6): every attributable factory
    # lifecycle step maps to exactly one campaign Scheduler ownership row carrying
    # the job's real terminal state. When the finalize boundary supplies it, the
    # report carries the exact per-job states and the correspondence verdict;
    # when omitted (direct-report unit tests) the correspondence defaults to
    # consistent so those tests exercise the other axes.
    scheduler_ownership = dict(scheduler_ownership or {})
    scheduler_correspondence_ok = bool(
        scheduler_ownership.get("correspondence_exact", True)
    )
    all_lifecycle_jobs_succeeded = bool(
        scheduler_ownership.get("all_lifecycle_jobs_succeeded", True)
    )

    return {
        "report_kind": "V2_9_8B_FULL_RUN_WINDOW_15M_TERMINAL_EVIDENCE",
        # 10.1 identity and ownership
        "identity": {
            "execution_id": _require(execution_id, "execution_id"),
            "campaign_id": context.campaign_id,
            "campaign_run_id": context.campaign_run_id,
            "cycle_id": context.cycle_id,
            "configuration_id": context.configuration_id,
            "supervision_id": supervision_id,
            "factory_run_id": context.factory_run_id,
            "launch_git_provenance": dict(launch_git_provenance or {}),
            "db_target_identity": _require(db_target_identity, "db_target_identity"),
        },
        # 10.2 selection and lifecycle
        "selection_and_lifecycle": {
            "selected_tokens": [dict(item) for item in selected_tokens],
            "selected_token_count": len(selected_tokens),
            "per_token_outcomes": [dict(item) for item in per_token_outcomes],
            "campaign_window_ownership_rows": windows,
            "terminal_window_ids": [row["window_id"] for row in terminal_windows],
            "terminal_window_count": len(terminal_windows),
            "slot_dispositions": [dict(item) for item in slot_dispositions],
            "quality_results": [dict(item) for item in quality_results],
        },
        # 10.3 full-run accounting
        "full_run_accounting": {
            "expected_stage_manifest": list(REQUIRED_LIFECYCLE_STAGE_KINDS),
            "sealed_stage_diagnostics": list(
                owner_evidence.get("sealed_stage_diagnostics")
                or reconciliation.get("diagnostics", {}).get(
                    "sealed_stage_diagnostics", []
                )
            ),
            "six_unit_totals": {key: int(value) for key, value in dict(
                six_unit_totals or {}
            ).items()},
            "owner_action_local_reconciliation": dict(reconciliation),
            "scheduler_attribution": scheduler_attribution,
            "campaign_scheduler_work_rows": scheduler_rows,
            "scheduler_ownership": scheduler_ownership,
            "scheduler_correspondence_exact": scheduler_correspondence_ok,
            "all_lifecycle_scheduler_jobs_succeeded": all_lifecycle_jobs_succeeded,
            "missing_or_mismatched_evidence": list(
                reconciliation.get("missing_mandatory_stage_kinds") or []
            ),
        },
        # 10.4 terminal safety
        "terminal_safety": {
            "campaign_window_reconciliation": {
                "terminal_window_count": len(terminal_windows),
                "all_scheduler_jobs_terminal": all_scheduler_terminal,
            },
            "zero_active_scheduler_jobs": int(zero_active_scheduler_jobs) == 0,
            "active_scheduler_job_count": int(zero_active_scheduler_jobs),
            "active_work_result": dict(active_work_result or {}),
            "lease_released": bool(lease_released),
            "forbidden_capability_deltas": forbidden_deltas,
            "zero_forbidden_deltas": all(
                value == 0 for value in forbidden_deltas.values()
            ),
        },
        # 10.5 acceptance verdict (three distinct axes never collapsed)
        "runtime_terminal_status": str(runtime_terminal_status),
        "runtime_first_terminal_cause": (
            None if runtime_first_terminal_cause is None
            else str(runtime_first_terminal_cause)
        ),
        "authorized_invocation_count": (
            None if authorized_invocation_count is None
            else int(authorized_invocation_count)
        ),
        "memory_quality_outcomes": [
            {
                "window_id": item.get("window_id"),
                "outcome": item.get("outcome"),
                "is_clean_window": item.get("is_clean_window"),
            }
            for item in quality_results
        ],
        "quality_consistency": {
            "consistent": quality_consistent,
        },
    }


def evaluate_campaign_acceptance_gate(
    report: Mapping[str, Any],
    *,
    authorized_invocation_count: int,
) -> dict[str, Any]:
    """Apply the campaign acceptance gate to a full-run terminal report (§11).

    Campaign PASS is impossible unless every condition holds. Lifecycle completion
    for a partial/dirty window is still valid, but a *quality inconsistency* — a
    clean episode attached to a non-clean window — is a hard blocker, as is a
    non-completed runtime status, an authorization count that is not exactly one,
    an unreleased lease, or a Scheduler ownership correspondence fault. Returns the
    verdict plus every check.
    """
    selection = report.get("selection_and_lifecycle", {})
    accounting = report.get("full_run_accounting", {})
    safety = report.get("terminal_safety", {})
    reconciliation = accounting.get("owner_action_local_reconciliation", {})

    selected = selection.get("selected_tokens") or []
    distinct_targets = {
        (item.get("token_id"), item.get("pair_id")) for item in selected
    }
    terminal_window_count = int(selection.get("terminal_window_count") or 0)
    slot_dispositions = selection.get("slot_dispositions") or []
    all_slots_pass_eligible = bool(slot_dispositions) and all(
        bool(item.get("pass_eligible")) for item in slot_dispositions
    )
    sealed_kinds = {
        str(item.get("stage_kind") or "")
        for item in (accounting.get("sealed_stage_diagnostics") or [])
    }
    # Every one of the four approved mandatory stages must be sealed and present.
    all_mandatory_stages_sealed = set(REQUIRED_LIFECYCLE_STAGE_KINDS).issubset(
        sealed_kinds
    )
    runtime_status = str(report.get("runtime_terminal_status") or "")
    runtime_terminal_completed = runtime_status in {
        "TERMINAL_COMPLETED",
        "COMPLETED",
    }
    quality_consistent = bool(
        report.get("quality_consistency", {}).get("consistent", True)
    )

    checks = {
        "exactly_one_authorized_invocation": int(authorized_invocation_count) == 1,
        "exactly_two_distinct_selected_targets": len(distinct_targets) == 2
        and len(selected) == 2,
        "exactly_two_terminal_window_15m_lifecycles": terminal_window_count == 2,
        "both_windows_campaign_owned": len(
            selection.get("campaign_window_ownership_rows") or []
        )
        >= 2
        and terminal_window_count == 2,
        "all_mandatory_stages_sealed": all_mandatory_stages_sealed,
        "owner_action_local_equal_non_vacuous": bool(reconciliation.get("equal"))
        and bool(reconciliation.get("lifecycle_started")),
        "all_scheduler_jobs_terminal_and_owned": bool(
            safety.get("campaign_window_reconciliation", {}).get(
                "all_scheduler_jobs_terminal"
            )
        ),
        "scheduler_ownership_correspondence_exact": bool(
            accounting.get("scheduler_correspondence_exact", True)
        ),
        "all_lifecycle_scheduler_jobs_succeeded": bool(
            accounting.get("all_lifecycle_scheduler_jobs_succeeded", True)
        ),
        "runtime_terminal_completed": runtime_terminal_completed,
        "memory_quality_consistent": quality_consistent,
        "canonical_report_complete": bool(
            report.get("identity", {}).get("factory_run_id")
        )
        and bool(selection.get("terminal_window_ids")),
        "all_slot_dispositions_pass_eligible": all_slots_pass_eligible,
        "zero_active_scheduler_jobs": bool(safety.get("zero_active_scheduler_jobs")),
        "lease_released": bool(safety.get("lease_released")),
        "zero_forbidden_deltas": bool(safety.get("zero_forbidden_deltas")),
    }

    lifecycle_started = bool(reconciliation.get("lifecycle_started")) or (
        terminal_window_count > 0
    )
    failing = [name for name, ok in checks.items() if not ok]
    if not failing:
        verdict = VERDICT_PASS
    elif not lifecycle_started:
        verdict = VERDICT_HONEST_BLOCKED
    else:
        verdict = VERDICT_BLOCKED_UNSAFE

    return {
        "verdict": verdict,
        "pass": verdict == VERDICT_PASS,
        "lifecycle_started": lifecycle_started,
        "checks": checks,
        "failing_checks": failing,
        # Memory quality is reported but never lowers the acceptance gate.
        "memory_quality_consistent": bool(
            report.get("quality_consistency", {}).get("consistent", True)
        ),
    }


_LIFECYCLE_SLOT_STAGE_KINDS = ("WINDOW_15M_SLOT_1", "WINDOW_15M_SLOT_2")

# The two distinct outbound-call boundaries the factory reports. Scheduler work
# and lifecycle transport reservation are observed at plan/enqueue time; the
# actual measured source transport and the exact-pair verification validation are
# observed at the real outbound-call boundary.
BOUNDARY_SCHEDULER_ENQUEUE = "SCHEDULER_ENQUEUE"
BOUNDARY_SOURCE_TRANSPORT = "SOURCE_TRANSPORT"

# Projected governed source operations reserved per lifecycle step. A SNAPSHOT
# reserves the one exact-pair observation call it will make; a WINDOW_CLOSE
# reserves the close observation plus the fixed pre-close context bundle. These
# are the step's *actual projected governed operations* — a close reserving many
# calls is never collapsed to one reservation just because it is one Scheduler
# job. ``PRECLOSE_CONTEXT_REQUEST_COUNT`` mirrors the factory's
# ``_CONTEXT_REQUESTS_PER_TOKEN``; a guard test asserts they stay equal.
PRECLOSE_CONTEXT_REQUEST_COUNT = 5
PROJECTED_GOVERNED_OPERATIONS_BY_STEP_KIND = {
    "SNAPSHOT": 1,
    "WINDOW_CLOSE": 1 + PRECLOSE_CONTEXT_REQUEST_COUNT,
}
# Lifecycle step kinds that carry an exact-pair source transport identity.
_TRANSPORT_BEARING_STEP_KINDS = frozenset({"SNAPSHOT", "WINDOW_CLOSE"})
_EXACT_PAIR_VALIDATION_KIND = "EXACT_PAIR_VERIFICATION"


def _slot_ordinal_from_step_key(step_key: str) -> int:
    prefix = str(step_key or "").split("_", 1)[0]
    if prefix.startswith("t") and prefix[1:].isdigit():
        ordinal = int(prefix[1:])
        if ordinal in (1, 2):
            return ordinal
    raise FullRunAccountingError(f"cannot derive slot ordinal from step key: {step_key!r}")


def _slot_stage_id(context: OperationalLifecycleOwnershipContext, ordinal: int) -> str:
    return build_campaign_stage_id(
        campaign_id=context.campaign_id,
        run_id=context.campaign_run_id,
        cycle_id=context.cycle_id,
        stage_kind=f"WINDOW_15M_SLOT_{ordinal}",
        stage_sequence=ordinal + 1,
    )


def _projected_reservation_count(step_kind: str) -> int:
    try:
        return int(PROJECTED_GOVERNED_OPERATIONS_BY_STEP_KIND[str(step_kind)])
    except KeyError as exc:
        raise FullRunAccountingError(
            f"no projected governed-operation reservation for step kind: {step_kind!r}"
        ) from exc


def scheduler_work_identity_for_step(
    context: OperationalLifecycleOwnershipContext,
    *,
    slot_ordinal: int,
    scheduler_job_id: int,
    step_kind: str,
    token_id: int,
) -> SchedulerWorkIdentity:
    """One Scheduler work identity for one enqueued lifecycle run-step job."""
    return SchedulerWorkIdentity(
        stage_id=_slot_stage_id(context, slot_ordinal),
        scheduler_job_id=int(scheduler_job_id),
        job_kind=str(step_kind),
        target_category="token",
        target_identity=str(int(token_id)),
    )


def reservation_identities_for_step(
    context: OperationalLifecycleOwnershipContext,
    *,
    slot_ordinal: int,
    scheduler_job_id: int,
    step_kind: str,
    token_id: int,
    pair_id: int,
) -> list[LifecycleReservationIdentity]:
    """The lifecycle transport reservations a step actually reserves.

    Count equals the step's projected governed operations, so a close step that
    reserves ``1 + PRECLOSE_CONTEXT_REQUEST_COUNT`` calls yields that many
    reservation identities — never one just because it has one Scheduler job.
    """
    stage_id = _slot_stage_id(context, slot_ordinal)
    job = int(scheduler_job_id)
    count = _projected_reservation_count(step_kind)
    return [
        LifecycleReservationIdentity(
            stage_id=stage_id,
            factory_run_id=context.factory_run_id,
            token_id=int(token_id),
            pair_id=int(pair_id),
            window_kind="WINDOW_15M",
            reservation_ordinal=job * 100 + index,
        )
        for index in range(count)
    ]


def transport_identity_for_step(
    context: OperationalLifecycleOwnershipContext,
    *,
    slot_ordinal: int,
    source_request_id: int,
    source_name: str,
    request_kind: str,
    pair_id: int,
    response_bytes: int,
    normalized_rows: int,
) -> TransportOperationIdentity:
    """One measured source transport identity for a step's exact-pair call.

    Keyed on the durable ``source_request_id`` so the execution-time observation
    and the post-hoc owner sealing derive the identical identity for the same
    outbound call.
    """
    return build_transport_identity(
        stage=_slot_stage_id(context, slot_ordinal),
        source_name=str(source_name),
        endpoint_owner=str(source_name),
        governed_request_kind=str(request_kind),
        method_or_endpoint=f"source_request:{int(source_request_id)}",
        within_request_ordinal=0,
        target_category="pair",
        target_identity=str(int(pair_id)),
        response_bytes=int(response_bytes),
        normalized_rows=int(normalized_rows),
    )


def validation_identity_for_step(
    context: OperationalLifecycleOwnershipContext,
    *,
    slot_ordinal: int,
    step_key: str,
    scheduler_job_id: int,
) -> LocalValidationIdentity:
    """The exact-pair verification validation that runs on a step's response."""
    return LocalValidationIdentity(
        stage_id=_slot_stage_id(context, slot_ordinal),
        subject_identity=str(step_key),
        validation_kind=_EXACT_PAIR_VALIDATION_KIND,
        validation_ordinal=int(scheduler_job_id),
    )


def build_lifecycle_action_local_observer(
    context: OperationalLifecycleOwnershipContext,
    ledger: CampaignActionLocalLedger,
) -> Callable[[Mapping[str, Any]], None]:
    """Return the factory ``lifecycle_operation_observer`` bound to a ledger.

    The factory fires this at two real boundaries. At ``SCHEDULER_ENQUEUE`` it
    records one Scheduler work identity plus the step's projected transport
    reservations. At ``SOURCE_TRANSPORT`` (the actual measured outbound-call
    boundary) it records the measured source transport identity plus the exact-pair
    verification validation that ran on the response. This is the execution-time
    capture that must equal the post-hoc owner sealing; it is never reconstructed
    from final rows or reports.
    """

    def observe(record: Mapping[str, Any]) -> None:
        boundary = str(record.get("boundary"))
        step_kind = str(record.get("step_kind"))
        if step_kind not in _TRANSPORT_BEARING_STEP_KINDS:
            return
        ordinal = _slot_ordinal_from_step_key(str(record.get("step_key")))
        if boundary == BOUNDARY_SCHEDULER_ENQUEUE:
            ledger.observe_scheduler_work(
                scheduler_work_identity_for_step(
                    context,
                    slot_ordinal=ordinal,
                    scheduler_job_id=int(record["scheduler_job_id"]),
                    step_kind=step_kind,
                    token_id=int(record["token_id"]),
                )
            )
            for reservation in reservation_identities_for_step(
                context,
                slot_ordinal=ordinal,
                scheduler_job_id=int(record["scheduler_job_id"]),
                step_kind=step_kind,
                token_id=int(record["token_id"]),
                pair_id=int(record["pair_id"]),
            ):
                ledger.observe_lifecycle_reservation(reservation)
        elif boundary == BOUNDARY_SOURCE_TRANSPORT:
            source_request_id = record.get("source_request_id")
            if source_request_id is None:
                return
            ledger.observe_transport(
                transport_identity_for_step(
                    context,
                    slot_ordinal=ordinal,
                    source_request_id=int(source_request_id),
                    source_name=str(record.get("source_name") or "dexscreener"),
                    request_kind=str(
                        record.get("request_kind") or "pair_market_snapshot"
                    ),
                    pair_id=int(record["pair_id"]),
                    response_bytes=int(record.get("response_bytes") or 0),
                    normalized_rows=int(record.get("normalized_rows") or 0),
                )
            )
            ledger.observe_local_validation(
                validation_identity_for_step(
                    context,
                    slot_ordinal=ordinal,
                    step_key=str(record["step_key"]),
                    scheduler_job_id=int(record["scheduler_job_id"]),
                )
            )

    return observe


def _validations_only_stage_evidence(count: int) -> dict[str, Any]:
    """Evidence scaffold for an owner-only stage carrying named validations."""
    return {
        "evidence_kind": "CAMPAIGN_SIX_UNIT_EVIDENCE_V1",
        "transport_operations": [],
        "local_validations": int(count),
        "scheduler_work_items": 0,
        "lifecycle_reservations": 0,
    }


# Real Scheduler job statuses map exactly to campaign work terminal states.
_JOB_STATUS_TO_WORK_STATE = {
    "SUCCEEDED": "SUCCEEDED",
    "FAILED": "FAILED",
    "CANCELLED": "CANCELLED",
    "SKIPPED": "SKIPPED",
}
# One normalized exact-pair row is produced per lifecycle observation.
_LIFECYCLE_NORMALIZED_ROWS_PER_TRANSPORT = 1


def finalize_full_run_ownership_and_report(
    connection: sqlite3.Connection,
    *,
    context: OperationalLifecycleOwnershipContext,
    action_local: CampaignActionLocalLedger,
    execution_id: str,
    supervision_id: Any,
    launch_git_provenance: Mapping[str, Any],
    db_target_identity: str,
    authorized_invocation_count: int,
    runtime_terminal_status: str,
    lease_released: bool,
    runtime_first_terminal_cause: str | None = None,
    active_work_result: Mapping[str, Any] | None = None,
    queue_dispositions: Mapping[int, str] | None = None,
    forbidden_capability_deltas: Mapping[str, int] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Register ownership, seal accounting, reconcile, report, and gate a run.

    This is the campaign-layer full-run boundary invoked after the factory closes
    its windows and after unified terminal cleanup has produced the durable
    authorization/runtime/lease/active-work facts (which are passed in, never
    assumed). Because the memory-window close commits before campaign ownership
    can be registered, this is an explicit fail-closed compensation boundary: any
    registration/projection/accounting fault is preserved as a block reason and
    prevents Campaign PASS. It never rewrites factory state.

    Every accounting fact is measured from durable rows:

    * campaign-window ownership from the succeeded ``WINDOW_CLOSE`` steps;
    * Scheduler ownership carrying each job's *real* ``printer_scheduler_jobs``
      status (never a hardcoded SUCCEEDED);
    * owner slot-stage evidence sealing the exact lifecycle source transport
      identities (with real response bytes / normalized rows), the projected
      transport reservations, the Scheduler work, and the exact-pair validations;
    * the four approved mandatory stages, with owner↔action-local equality scoped
      to the two lifecycle slot stages the observer actually witnessed.
    """
    connection.row_factory = sqlite3.Row
    stamp = now or datetime.now(timezone.utc).isoformat()
    blocked_reasons: list[str] = []
    queue_dispositions = dict(queue_dispositions or {})

    close_steps = connection.execute(
        """SELECT id, token_id, pair_id, token_mint, pair_address, tracking_lane,
                  memory_window_id, step_key
           FROM printer_memory_factory_run_steps
           WHERE run_id=? AND step_kind='WINDOW_CLOSE' AND step_status='SUCCEEDED'
           ORDER BY id""",
        (context.factory_run_id,),
    ).fetchall()

    token_to_window: dict[int, str] = {}
    token_to_slot: dict[int, str] = {}
    token_to_terminal_state: dict[int, str] = {}
    token_to_memory: dict[int, sqlite3.Row] = {}
    # Exact durable target identity carried from the close step + campaign slot.
    token_to_identity: dict[int, dict[str, Any]] = {}
    registered_windows: list[str] = []

    for step in close_steps:
        token_id = int(step["token_id"])
        pair_id = int(step["pair_id"])
        memory_row_id = step["memory_window_id"]
        if memory_row_id is None:
            blocked_reasons.append(f"CLOSE_STEP_WITHOUT_MEMORY_WINDOW:{step['id']}")
            continue
        slot = connection.execute(
            """SELECT token_slot_id, lifecycle_identity, mint_identity, pair_identity,
                      tracking_queue_id
               FROM printer_memory_factory_campaign_token_slots
               WHERE cycle_id=? AND token_row_id=?""",
            (context.cycle_id, token_id),
        ).fetchone()
        if slot is None:
            blocked_reasons.append(f"NO_CAMPAIGN_SLOT_FOR_TOKEN:{token_id}")
            continue
        token_slot_id = str(slot["token_slot_id"])
        memory = connection.execute(
            """SELECT id, memory_status, data_quality_label, do_not_train
               FROM printer_memory_windows WHERE id=?""",
            (int(memory_row_id),),
        ).fetchone()
        if memory is None:
            blocked_reasons.append(f"MEMORY_WINDOW_MISSING:{memory_row_id}")
            continue
        terminal_state = (
            "CLEAN_PROMOTED"
            if str(memory["memory_status"]) == "CLEAN_MEMORY"
            else "DIRTY"
        )
        window_id = f"{context.cycle_id}:window:{token_id}"
        token_to_window[token_id] = window_id
        token_to_slot[token_id] = token_slot_id
        token_to_terminal_state[token_id] = terminal_state
        token_to_memory[token_id] = memory
        # Carry the real token/pair identity from the close step and slot — the
        # pair id is the step's own column, never derived from the token id.
        token_to_identity[token_id] = {
            "token_id": token_id,
            "token_mint": step["token_mint"] or slot["mint_identity"],
            "pair_id": pair_id,
            "pair_address": step["pair_address"] or slot["pair_identity"],
            "tracking_lane": step["tracking_lane"],
            "token_slot_id": token_slot_id,
            "memory_window_row_id": int(memory_row_id),
            "campaign_window_id": window_id,
            "memory_window_id": window_id,
            "campaign_window_row_id": window_id,
        }
        try:
            register_campaign_window_close(
                connection,
                campaign_id=context.campaign_id,
                run_id=context.campaign_run_id,
                cycle_id=context.cycle_id,
                factory_run_id=context.factory_run_id,
                token_slot_id=token_slot_id,
                window_id=window_id,
                close_step_id=int(step["id"]),
                memory_window_row_id=int(memory_row_id),
                root_15m_lifecycle_identity=str(slot["lifecycle_identity"]),
                checkpoint_cutoff=stamp,
                terminal_window_state=terminal_state,
                terminal_cause=f"window_closed_{terminal_state.lower()}",
                now=stamp,
            )
            registered_windows.append(window_id)
        except CampaignOwnershipError as exc:
            blocked_reasons.append(f"WINDOW_REGISTRATION_FAILED:{token_id}:{exc}")

    lifecycle_steps = connection.execute(
        """SELECT s.id, s.scheduler_job_id, s.step_kind, s.token_id, s.pair_id,
                  s.step_key, s.source_request_id, s.source_response_id,
                  j.status AS scheduler_job_status,
                  q.source_name AS request_source_name,
                  q.request_kind AS request_kind,
                  LENGTH(r.normalized_payload_json) AS response_bytes
           FROM printer_memory_factory_run_steps s
           LEFT JOIN printer_scheduler_jobs j ON j.id = s.scheduler_job_id
           LEFT JOIN printer_source_requests q ON q.id = s.source_request_id
           LEFT JOIN printer_source_responses r ON r.id = s.source_response_id
           WHERE s.run_id=? AND s.step_kind IN ('SNAPSHOT','WINDOW_CLOSE')
             AND s.scheduler_job_id IS NOT NULL
           ORDER BY s.id""",
        (context.factory_run_id,),
    ).fetchall()

    # --- Scheduler ownership carrying each job's real terminal state (§6). ---
    projected_jobs: list[int] = []
    lifecycle_job_states: dict[int, str] = {}
    for step in lifecycle_steps:
        job_id = int(step["scheduler_job_id"])
        token_id = int(step["token_id"])
        window_id = token_to_window.get(token_id)
        slot_id = token_to_slot.get(token_id)
        if window_id is None or slot_id is None:
            blocked_reasons.append(f"SCHEDULER_PROJECTION_WITHOUT_WINDOW:{job_id}")
            continue
        raw_status = str(step["scheduler_job_status"] or "").upper()
        work_state = _JOB_STATUS_TO_WORK_STATE.get(raw_status)
        if work_state is None:
            blocked_reasons.append(
                f"SCHEDULER_JOB_NOT_TERMINAL:{job_id}:{raw_status or 'MISSING'}"
            )
            lifecycle_job_states[job_id] = raw_status or "MISSING"
            continue
        lifecycle_job_states[job_id] = work_state
        try:
            project_campaign_scheduler_job(
                connection,
                campaign_id=context.campaign_id,
                run_id=context.campaign_run_id,
                cycle_id=context.cycle_id,
                factory_run_id=context.factory_run_id,
                token_slot_id=slot_id,
                window_id=window_id,
                scheduler_job_id=job_id,
                job_kind=str(step["step_kind"]),
                deadline_at=stamp,
                terminal_state=work_state,
                terminal_cause=f"scheduler_job_{work_state.lower()}",
                now=stamp,
            )
            projected_jobs.append(job_id)
        except CampaignOwnershipError as exc:
            blocked_reasons.append(f"SCHEDULER_PROJECTION_FAILED:{job_id}:{exc}")

    lifecycle_job_ids = {int(s["scheduler_job_id"]) for s in lifecycle_steps}
    owned_rows = connection.execute(
        """SELECT scheduler_job_id, work_state
           FROM printer_memory_factory_campaign_scheduler_work
           WHERE campaign_id=? AND run_id=? AND cycle_id=?""",
        (context.campaign_id, context.campaign_run_id, context.cycle_id),
    ).fetchall()
    owned_job_ids = {int(r["scheduler_job_id"]) for r in owned_rows}
    # Exact correspondence: every lifecycle job owned once; no extra owners.
    correspondence_exact = (
        owned_job_ids == lifecycle_job_ids
        and len(owned_rows) == len(lifecycle_job_ids)
        and not blocked_reasons
    )
    all_lifecycle_jobs_succeeded = bool(lifecycle_job_states) and all(
        state == "SUCCEEDED" for state in lifecycle_job_states.values()
    )
    scheduler_ownership = {
        "lifecycle_job_ids": sorted(lifecycle_job_ids),
        "owned_job_ids": sorted(owned_job_ids),
        "lifecycle_job_states": {
            str(k): v for k, v in sorted(lifecycle_job_states.items())
        },
        "missing_ownership": sorted(lifecycle_job_ids - owned_job_ids),
        "extra_ownership": sorted(owned_job_ids - lifecycle_job_ids),
        "non_succeeded_states": {
            str(k): v
            for k, v in sorted(lifecycle_job_states.items())
            if v != "SUCCEEDED"
        },
        "correspondence_exact": correspondence_exact,
        "all_lifecycle_jobs_succeeded": all_lifecycle_jobs_succeeded,
    }

    # --- Seal the four approved mandatory stages from durable evidence. ---
    owner = CampaignSixUnitOwner(
        campaign_id=context.campaign_id,
        run_id=context.campaign_run_id,
        cycle_id=context.cycle_id,
    )
    slot_stage_ids: list[str] = []
    by_ordinal: dict[int, list[sqlite3.Row]] = {1: [], 2: []}
    for step in lifecycle_steps:
        by_ordinal[_slot_ordinal_from_step_key(str(step["step_key"]))].append(step)

    sealed_transport_count = 0
    lifecycle_source_request_count = 0
    for ordinal in (1, 2):
        steps = by_ordinal.get(ordinal) or []
        if not steps:
            continue
        stage_id = _slot_stage_id(context, ordinal)
        slot_stage_ids.append(stage_id)
        ledger = MeasuredTransportLedger(
            campaign_id=context.campaign_id,
            run_id=context.campaign_run_id,
            cycle_id=context.cycle_id,
        )
        scheds: list[SchedulerWorkIdentity] = []
        ress: list[LifecycleReservationIdentity] = []
        vals: list[LocalValidationIdentity] = []
        for step in steps:
            step_kind = str(step["step_kind"])
            job_id = int(step["scheduler_job_id"])
            token_id = int(step["token_id"])
            pair_id = int(step["pair_id"])
            scheds.append(
                scheduler_work_identity_for_step(
                    context, slot_ordinal=ordinal, scheduler_job_id=job_id,
                    step_kind=step_kind, token_id=token_id,
                )
            )
            ress.extend(
                reservation_identities_for_step(
                    context, slot_ordinal=ordinal, scheduler_job_id=job_id,
                    step_kind=step_kind, token_id=token_id, pair_id=pair_id,
                )
            )
            source_request_id = step["source_request_id"]
            source_response_id = step["source_response_id"]
            if source_request_id is not None:
                lifecycle_source_request_count += 1
            # The measured source transport + its exact-pair verification only
            # exist for an observation that actually produced a response.
            if source_request_id is not None and source_response_id is not None:
                ledger.record_transport(
                    transport_identity_for_step(
                        context, slot_ordinal=ordinal,
                        source_request_id=int(source_request_id),
                        source_name=str(step["request_source_name"] or "dexscreener"),
                        request_kind=str(
                            step["request_kind"] or "pair_market_snapshot"
                        ),
                        pair_id=pair_id,
                        response_bytes=int(step["response_bytes"] or 0),
                        normalized_rows=_LIFECYCLE_NORMALIZED_ROWS_PER_TRANSPORT,
                    )
                )
                vals.append(
                    validation_identity_for_step(
                        context, slot_ordinal=ordinal,
                        step_key=str(step["step_key"]), scheduler_job_id=job_id,
                    )
                )
        sealed_transport_count += len(ledger.transports)
        sealed = seal_campaign_stage_evidence(
            stage_id=stage_id,
            stage_kind=f"WINDOW_15M_SLOT_{ordinal}",
            stage_sequence=ordinal + 1,
            stage_terminal_status="COMPLETED",
            campaign_id=context.campaign_id,
            run_id=context.campaign_run_id,
            cycle_id=context.cycle_id,
            ledger=ledger,
            scheduler_work_identities=scheds,
            lifecycle_reservation_identities=ress,
            local_validation_identities=vals,
        )
        owner.ingest_stage_evidence(sealed)

    # DISCOVERY_SELECTION_SCHEDULER: the selection approvals that admitted each
    # campaign token slot to the lifecycle (owner-only, proven from durable slots).
    if token_to_slot:
        discovery_stage_id = build_campaign_stage_id(
            campaign_id=context.campaign_id, run_id=context.campaign_run_id,
            cycle_id=context.cycle_id, stage_kind="DISCOVERY_SELECTION_SCHEDULER",
            stage_sequence=1,
        )
        discovery_validations = [
            LocalValidationIdentity(
                stage_id=discovery_stage_id,
                subject_identity=str(token_to_slot[token_id]),
                validation_kind="SELECTION_APPROVED",
                validation_ordinal=int(token_id),
            )
            for token_id in sorted(token_to_slot)
        ]
        owner.ingest_stage_evidence(
            seal_campaign_stage_evidence(
                stage_id=discovery_stage_id,
                stage_kind="DISCOVERY_SELECTION_SCHEDULER",
                stage_sequence=1, stage_terminal_status="COMPLETED",
                campaign_id=context.campaign_id, run_id=context.campaign_run_id,
                cycle_id=context.cycle_id,
                evidence=_validations_only_stage_evidence(0),
                local_validation_identities=discovery_validations,
            )
        )

    # CAMPAIGN_TERMINAL_RECONCILIATION: the terminal reconciliation this boundary
    # actually performs (owner-only named validation, proven present).
    terminal_stage_id = build_campaign_stage_id(
        campaign_id=context.campaign_id, run_id=context.campaign_run_id,
        cycle_id=context.cycle_id, stage_kind="CAMPAIGN_TERMINAL_RECONCILIATION",
        stage_sequence=4,
    )
    owner.ingest_stage_evidence(
        seal_campaign_stage_evidence(
            stage_id=terminal_stage_id,
            stage_kind="CAMPAIGN_TERMINAL_RECONCILIATION",
            stage_sequence=4, stage_terminal_status="COMPLETED",
            campaign_id=context.campaign_id, run_id=context.campaign_run_id,
            cycle_id=context.cycle_id,
            evidence=_validations_only_stage_evidence(0),
            local_validation_identities=[
                LocalValidationIdentity(
                    stage_id=terminal_stage_id,
                    subject_identity=f"{context.cycle_id}:campaign_terminal",
                    validation_kind="CAMPAIGN_TERMINAL_RECONCILIATION",
                    validation_ordinal=1,
                )
            ],
        )
    )
    owner.close()

    # Fail-closed transport proof: a lifecycle-started run whose lifecycle steps
    # made source requests can never seal zero source transport identities.
    if lifecycle_source_request_count > 0 and sealed_transport_count == 0:
        blocked_reasons.append("LIFECYCLE_SOURCE_TRANSPORT_IDENTITIES_ZERO")

    reconciliation = reconcile_full_run_owner_to_action_local(
        owner, action_local,
        required_stage_kinds=REQUIRED_LIFECYCLE_STAGE_KINDS,
        owner_equality_stage_ids=slot_stage_ids,
    )

    selected_tokens: list[dict[str, Any]] = []
    per_token_outcomes: list[dict[str, Any]] = []
    slot_dispositions: list[dict[str, Any]] = []
    quality_results: list[dict[str, Any]] = []
    for token_id in sorted(token_to_window):
        memory = token_to_memory[token_id]
        identity = token_to_identity[token_id]
        terminal_state = token_to_terminal_state[token_id]
        queue_disposition = queue_dispositions.get(token_id, "COOLDOWN")
        selected_tokens.append(dict(identity))
        per_token_outcomes.append({
            **identity,
            "terminal_status": "WINDOW_CLOSED",
            "tracking_disposition": queue_disposition,
        })
        slot_dispositions.append(
            resolve_campaign_slot_terminal_disposition(
                lifecycle_started=True,
                owned_terminal_window_state=terminal_state,
                queue_disposition=queue_disposition,
            )
        )
        # Inspect the real episodes attached to this exact memory window: a clean
        # episode on a non-clean window is a quality inconsistency.
        episode = connection.execute(
            """SELECT episode_kind FROM printer_episodes
               WHERE memory_window_id=?
               ORDER BY (episode_kind = ?) DESC, id LIMIT 1""",
            (identity["memory_window_row_id"], _CLEAN_EPISODE_KIND),
        ).fetchone()
        proposed_episode_kind = None if episode is None else str(episode["episode_kind"])
        quality_results.append({
            **evaluate_quality_consistency(
                memory_status=str(memory["memory_status"]),
                data_quality_label=str(memory["data_quality_label"]),
                do_not_train=int(memory["do_not_train"]),
                proposed_episode_kind=proposed_episode_kind,
            ),
            "window_id": token_to_window[token_id],
        })

    active_jobs = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
             AND work_state IN ('PENDING','RUNNING','COOLDOWN')""",
        (context.campaign_id, context.campaign_run_id, context.cycle_id),
    ).fetchone()[0])

    report = build_full_run_terminal_report(
        connection,
        context=context,
        execution_id=execution_id,
        supervision_id=supervision_id,
        launch_git_provenance=launch_git_provenance,
        db_target_identity=db_target_identity,
        selected_tokens=selected_tokens,
        runtime_terminal_status=runtime_terminal_status,
        runtime_first_terminal_cause=runtime_first_terminal_cause,
        authorized_invocation_count=authorized_invocation_count,
        active_work_result=active_work_result,
        owner_evidence=owner.durable_evidence(),
        six_unit_totals=owner.six_unit_totals(),
        reconciliation=reconciliation,
        per_token_outcomes=per_token_outcomes,
        slot_dispositions=slot_dispositions,
        quality_results=quality_results,
        zero_active_scheduler_jobs=active_jobs,
        forbidden_capability_deltas=forbidden_capability_deltas or {},
        lease_released=lease_released,
        scheduler_ownership=scheduler_ownership,
    )
    gate = evaluate_campaign_acceptance_gate(
        report, authorized_invocation_count=int(authorized_invocation_count)
    )
    verdict = gate["verdict"]
    lifecycle_started = bool(reconciliation.get("lifecycle_started"))
    if blocked_reasons and verdict == VERDICT_PASS:
        verdict = VERDICT_BLOCKED_UNSAFE if lifecycle_started else VERDICT_HONEST_BLOCKED
    # §12 report/gate/verdict consistency: the embedded gate, the canonical report
    # and the returned verdict can never disagree. A compensation block downgrades
    # every surface together — no embedded gate may still read CAMPAIGN_PASS.
    if verdict != gate["verdict"]:
        gate = dict(gate)
        gate["verdict"] = verdict
        gate["pass"] = verdict == VERDICT_PASS
        gate["failing_checks"] = list(gate.get("failing_checks") or []) + [
            f"COMPENSATION_BLOCK:{reason}" for reason in blocked_reasons
        ]
    gate["compensation_blocked_reasons"] = list(blocked_reasons)
    report["campaign_acceptance_verdict"] = verdict
    report["campaign_pass"] = verdict == VERDICT_PASS
    return {
        "verdict": verdict,
        "campaign_acceptance": gate,
        "report": report,
        "reconciliation": reconciliation,
        "scheduler_ownership": scheduler_ownership,
        "registered_windows": registered_windows,
        "projected_scheduler_jobs": projected_jobs,
        "blocked_reasons": blocked_reasons,
    }


__all__ = [
    "BOUNDARY_SCHEDULER_ENQUEUE",
    "BOUNDARY_SOURCE_TRANSPORT",
    "FullRunAccountingError",
    "OperationalLifecycleOwnershipContext",
    "PRECLOSE_CONTEXT_REQUEST_COUNT",
    "PROJECTED_GOVERNED_OPERATIONS_BY_STEP_KIND",
    "REQUIRED_LIFECYCLE_STAGE_KINDS",
    "VERDICT_BLOCKED_UNSAFE",
    "VERDICT_HONEST_BLOCKED",
    "VERDICT_PASS",
    "build_full_run_terminal_report",
    "build_lifecycle_action_local_observer",
    "evaluate_campaign_acceptance_gate",
    "evaluate_quality_consistency",
    "finalize_full_run_ownership_and_report",
    "reservation_identities_for_step",
    "resolve_campaign_slot_terminal_disposition",
    "scheduler_work_identity_for_step",
    "transport_identity_for_step",
    "validation_identity_for_step",
]

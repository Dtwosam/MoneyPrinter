"""Operational policy and campaign barrier for standard first-four-hour collection.

The public activation contract is categorical. 4h cadence availability is not
itself execution authority; only the dedicated standard campaign barrier may
compose production 4h work after both owned first-hour closes are durably known.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping, Sequence

from printer_v1.operator_cli.campaign_authority_adapters import (
    CampaignAuthorityAdapterError,
    build_4a_authority_facts,
    load_authoritative_promotion_outcome,
    load_authoritative_window_safety,
)
from printer_v1.operator_cli.operational_selective_1h import campaign_window_id_for
from printer_v1.operator_cli.one_token_4h_runtime import (
    FourHourExecutionAuthority,
    plan_standard_campaign_4h_handoff,
    standard_campaign_lifecycle_budget,
)
from printer_v1.scheduler.token_local_continuation import (
    CampaignContinuationContext,
    ContinuationVerdict,
    ExpectedTokenContinuationIdentity,
    TokenContinuationInput,
    evaluate_token_local_continuations,
)
from printer_v1.snapshots.lifecycle_continuity import (
    CONTINUITY_BLOCKED,
    CONTINUITY_CONTINUOUS,
    CONTINUITY_DIRTY,
    CONTINUITY_UNKNOWN,
)


STANDARD_FOUR_HOUR_MODE = "standard-four-hour-run"
STANDARD_FOUR_HOUR_PREFLIGHT_MODE = "standard-four-hour-preflight"
POLICY_VERSION = "V2-9.8-STANDARD-4H-OPERATIONAL-V1"
ROOT_MAIN_WINDOW = "WINDOW_15M"
SUCCESSOR_WINDOW = "WINDOW_4H"
TOKEN_CAPACITY = 2
POST_SUPPLY_DURATION_SECONDS = 14_700
PRE_LIFECYCLE_DURATION_SECONDS = 900
AUTOMATIC_RETRIES = 0
ENDPOINT_ROTATION = False
LOCKED_WINDOWS = ("WINDOW_12H", "WINDOW_24H")
ELIGIBILITY_CONTRACT_VERSION = "STANDARD_4H_ELIGIBILITY_V1"
# Worst-case standard operational shape. Both token slots run the FAST cadence
# and both remain eligible for the WINDOW_4H suffix. This is the authorization
# envelope, not a prediction that every request will occur.
STANDARD_WORST_CASE_TRACKING_LANES = ("TRACK_FAST", "TRACK_FAST")
STANDARD_WORST_CASE_CONTINUING_MASK = (True, True)


class StandardFourHourOperationalError(ValueError):
    """Fail-closed standard-four-hour operational contract fault."""


def standard_four_hour_capacity_contract() -> dict[str, Any]:
    """Derive the standard worst-case public capacity from canonical arithmetic.

    ``one_token_4h_runtime.standard_campaign_lifecycle_budget`` remains the only
    owner of cadence/context/4h-phase summation. This helper projects that one
    truth for every public standard surface so no downstream owner may maintain
    an independent numeric capacity.

    The derivation is deterministic and source-free: it reads only committed
    cadence/runtime policy and performs no source, database, Scheduler,
    filesystem, or environment access.
    """
    if TOKEN_CAPACITY != 2:
        raise StandardFourHourOperationalError(
            "standard four-hour capacity requires exactly two token slots"
        )
    budget = standard_campaign_lifecycle_budget(
        STANDARD_WORST_CASE_TRACKING_LANES, STANDARD_WORST_CASE_CONTINUING_MASK
    )
    components = budget["request_components"]
    if "discovery" not in components:
        raise StandardFourHourOperationalError(
            "standard four-hour capacity is missing its shared discovery component"
        )
    shared = int(components["discovery"])
    outer_ceiling = int(budget["request_ceiling"])
    non_shared = outer_ceiling - shared
    if non_shared < 0 or non_shared % TOKEN_CAPACITY != 0:
        raise StandardFourHourOperationalError(
            "standard four-hour non-shared requests must divide exactly "
            "across the two worst-case token slots"
        )
    return {
        "tracking_lanes": STANDARD_WORST_CASE_TRACKING_LANES,
        "continuing_mask": STANDARD_WORST_CASE_CONTINUING_MASK,
        "token_capacity": TOKEN_CAPACITY,
        "shared_discovery_requests": shared,
        "lifecycle_request_outer_ceiling": outer_ceiling,
        "lifecycle_requests_per_token": non_shared // TOKEN_CAPACITY,
        "lifecycle_scheduler_outer_ceiling": int(budget["scheduler_ceiling"]),
    }


_STANDARD_CAPACITY = standard_four_hour_capacity_contract()
# Derived, never independently maintained. Changing cadence/runtime policy moves
# every public standard surface together instead of splitting them apart.
LIFECYCLE_REQUEST_OUTER_CEILING = int(
    _STANDARD_CAPACITY["lifecycle_request_outer_ceiling"]
)
LIFECYCLE_REQUESTS_PER_TOKEN = int(_STANDARD_CAPACITY["lifecycle_requests_per_token"])
LIFECYCLE_SCHEDULER_OUTER_CEILING = int(
    _STANDARD_CAPACITY["lifecycle_scheduler_outer_ceiling"]
)


def standard_four_hour_policy_contract() -> dict[str, object]:
    """Return the immutable public activation contract without running work."""
    return {
        "mode": STANDARD_FOUR_HOUR_MODE,
        "policy_version": POLICY_VERSION,
        "root_main_window": ROOT_MAIN_WINDOW,
        "successor_window": SUCCESSOR_WINDOW,
        "token_capacity": TOKEN_CAPACITY,
        "post_supply_duration_seconds": POST_SUPPLY_DURATION_SECONDS,
        "pre_lifecycle_duration_seconds": PRE_LIFECYCLE_DURATION_SECONDS,
        "lifecycle_request_outer_ceiling": LIFECYCLE_REQUEST_OUTER_CEILING,
        "lifecycle_requests_per_token": LIFECYCLE_REQUESTS_PER_TOKEN,
        "lifecycle_scheduler_outer_ceiling": LIFECYCLE_SCHEDULER_OUTER_CEILING,
        "automatic_retries": AUTOMATIC_RETRIES,
        "endpoint_rotation": ENDPOINT_ROTATION,
        "locked_windows": LOCKED_WINDOWS,
        "eligibility_contract_version": ELIGIBILITY_CONTRACT_VERSION,
        "requires_one_use_wrapper": True,
        "legacy_four_hour_proof_is_production_authority": False,
        "planning_barrier": "BOTH_OWNED_FIRST_HOUR_VERDICTS_TERMINAL",
    }


def evaluate_standard_four_hour_eligibility(
    *,
    campaign: CampaignContinuationContext,
    tokens: Sequence[TokenContinuationInput],
):
    """Apply the canonical token-local hard gates to the standard 1h->4h path."""
    if len(tokens) != TOKEN_CAPACITY:
        raise StandardFourHourOperationalError(
            "standard four-hour eligibility requires exactly two token slots"
        )
    for token in tokens:
        if str(token.predecessor_window_kind) != "WINDOW_1H":
            raise StandardFourHourOperationalError(
                "standard four-hour predecessor must be WINDOW_1H"
            )
        if str(token.successor_window_kind) != SUCCESSOR_WINDOW:
            raise StandardFourHourOperationalError(
                "standard four-hour successor must be WINDOW_4H"
            )
    return evaluate_token_local_continuations(campaign=campaign, tokens=tokens)


def _loads_mapping(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if value is None:
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _campaign_identity_rows(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    cycle_id: str,
    factory_run_id: str,
) -> list[sqlite3.Row]:
    campaign = connection.execute(
        """SELECT c.campaign_state,c.db_mode,c.policy_version,cfg.configuration_id
           FROM printer_memory_factory_campaigns AS c
           JOIN printer_memory_factory_campaign_configurations AS cfg
             ON cfg.campaign_id=c.campaign_id
           WHERE c.campaign_id=? AND cfg.configuration_id=?""",
        (campaign_id, configuration_id),
    ).fetchone()
    if campaign is None:
        raise StandardFourHourOperationalError(
            "standard four-hour campaign/configuration identity mismatch"
        )
    run = connection.execute(
        """SELECT run_state,authoritative_run_id
           FROM printer_memory_factory_campaign_runs
           WHERE campaign_id=? AND run_id=?""",
        (campaign_id, run_id),
    ).fetchone()
    if run is None or str(run["authoritative_run_id"] or "") != str(factory_run_id):
        raise StandardFourHourOperationalError(
            "standard four-hour campaign/factory run identity mismatch"
        )
    cycle = connection.execute(
        """SELECT cycle_state FROM printer_memory_factory_campaign_cycles
           WHERE campaign_id=? AND run_id=? AND cycle_id=?""",
        (campaign_id, run_id, cycle_id),
    ).fetchone()
    if cycle is None:
        raise StandardFourHourOperationalError(
            "standard four-hour campaign cycle identity mismatch"
        )
    slots = connection.execute(
        """SELECT token_slot_id,slot_ordinal,token_row_id,pair_row_id,
                  mint_identity,pair_identity,lifecycle_identity,token_state
           FROM printer_memory_factory_campaign_token_slots
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
           ORDER BY slot_ordinal""",
        (campaign_id, run_id, cycle_id),
    ).fetchall()
    if len(slots) != TOKEN_CAPACITY or {int(row["slot_ordinal"]) for row in slots} != {1, 2}:
        raise StandardFourHourOperationalError(
            "standard four-hour barrier requires exactly two owned token slots"
        )
    return list(slots)


def _owned_first_hour_state(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    factory_run_id: str,
    slot: sqlite3.Row,
) -> dict[str, Any]:
    slot_id = str(slot["token_slot_id"])
    windows = connection.execute(
        """SELECT window_id,window_state,root_15m_lifecycle_identity,
                  memory_window_row_id,checkpoint_cutoff
           FROM printer_memory_factory_campaign_windows
           WHERE campaign_id=? AND run_id=? AND cycle_id=? AND token_slot_id=?
             AND token_row_id=? AND pair_row_id=? AND window_kind='WINDOW_1H'
           ORDER BY window_id""",
        (
            campaign_id,
            run_id,
            cycle_id,
            slot_id,
            int(slot["token_row_id"]),
            int(slot["pair_row_id"]),
        ),
    ).fetchall()
    if len(windows) != 1:
        raise StandardFourHourOperationalError(
            f"first-hour window missing/ambiguous for {slot_id}"
        )
    window = windows[0]
    closes = connection.execute(
        """SELECT id,step_status,tracking_lane,memory_window_id,result_json
           FROM printer_memory_factory_run_steps
           WHERE run_id=? AND token_id=? AND pair_id=?
             AND step_kind IN ('CONTINUATION_CLOSE','CONTINUATION_CLOSE_AUDIT')
           ORDER BY id""",
        (factory_run_id, int(slot["token_row_id"]), int(slot["pair_row_id"])),
    ).fetchall()
    if len(closes) != 1:
        raise StandardFourHourOperationalError(
            f"first-hour close missing/ambiguous for {slot_id}"
        )
    close = closes[0]
    status = str(close["step_status"])
    if status in {"PENDING", "RUNNING"}:
        return {"terminal": False, "status": status, "window": window, "close": close}
    if status != "SUCCEEDED":
        raise StandardFourHourOperationalError(
            f"first-hour close is not successful for {slot_id}: {status}"
        )
    if window["memory_window_row_id"] is None or close["memory_window_id"] is None:
        raise StandardFourHourOperationalError(
            f"successful first-hour close is unbound for {slot_id}"
        )
    if int(window["memory_window_row_id"]) != int(close["memory_window_id"]):
        raise StandardFourHourOperationalError(
            f"first-hour close memory identity mismatch for {slot_id}"
        )
    if str(window["root_15m_lifecycle_identity"]) != str(slot["lifecycle_identity"]):
        raise StandardFourHourOperationalError(
            f"first-hour lifecycle identity mismatch for {slot_id}"
        )
    return {"terminal": True, "status": status, "window": window, "close": close}


def _continuation_input(
    connection: sqlite3.Connection,
    *,
    db_path: str | Path,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    cycle_id: str,
    slot: sqlite3.Row,
    state: Mapping[str, Any],
    token_budget_available: bool,
    tracking_lane: str,
    token_eligible: bool,
    cancelled: bool,
    terminal: bool,
) -> tuple[TokenContinuationInput, dict[str, Any]]:
    window = state["window"]
    close = state["close"]
    slot_id = str(slot["token_slot_id"])
    window_id = str(window["window_id"])
    memory_window_id = int(window["memory_window_row_id"])
    physical = connection.execute(
        """SELECT id,token_id,pair_id,window_kind,window_status,window_end_at,
                  data_quality_label,do_not_train,supporting_context_json
           FROM printer_memory_windows WHERE id=?""",
        (memory_window_id,),
    ).fetchone()
    if physical is None:
        raise StandardFourHourOperationalError(
            f"authoritative first-hour memory row missing for {slot_id}"
        )
    if (
        int(physical["token_id"]) != int(slot["token_row_id"])
        or int(physical["pair_id"]) != int(slot["pair_row_id"])
        or str(physical["window_kind"]) != "WINDOW_1H"
    ):
        raise StandardFourHourOperationalError(
            f"authoritative first-hour memory target mismatch for {slot_id}"
        )
    try:
        promotion = load_authoritative_promotion_outcome(
            db_path,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            token_slot_id=slot_id,
            window_id=window_id,
        )
        safety = load_authoritative_window_safety(
            db_path,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            token_slot_id=slot_id,
            window_id=window_id,
            memory_window_close_cutoff=str(physical["window_end_at"]),
        )
        facts = build_4a_authority_facts(promotion, safety)
    except CampaignAuthorityAdapterError as exc:
        raise StandardFourHourOperationalError(
            f"first-hour authoritative evidence mismatch for {slot_id}: {exc}"
        ) from exc
    context = _loads_mapping(physical["supporting_context_json"])
    continuity_payload = context.get("continuity")
    continuity = (
        str(continuity_payload.get("continuity_status") or "")
        if isinstance(continuity_payload, Mapping)
        else ""
    )
    if continuity not in {
        CONTINUITY_CONTINUOUS,
        CONTINUITY_DIRTY,
        CONTINUITY_BLOCKED,
        CONTINUITY_UNKNOWN,
    }:
        continuity = CONTINUITY_BLOCKED
    lane = str(tracking_lane)
    expected = ExpectedTokenContinuationIdentity(
        token_slot_id=slot_id,
        token_id=str(slot["token_row_id"]),
        mint_id=str(slot["mint_identity"]),
        pair_id=str(slot["pair_row_id"]),
        lifecycle_id=str(slot["lifecycle_identity"]),
        predecessor_window_id=window_id,
    )
    token = TokenContinuationInput(
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        token_slot_id=slot_id,
        token_id=str(slot["token_row_id"]),
        mint_id=str(slot["mint_identity"]),
        pair_id=str(slot["pair_row_id"]),
        lifecycle_id=str(slot["lifecycle_identity"]),
        predecessor_window_id=window_id,
        expected_identity=expected,
        predecessor_window_kind="WINDOW_1H",
        successor_window_kind="WINDOW_4H",
        predecessor_window_status=str(physical["window_status"]),
        predecessor_memory_quality=str(facts["predecessor_memory_quality"]),
        predecessor_data_quality=str(physical["data_quality_label"]),
        predecessor_do_not_train=bool(physical["do_not_train"]),
        predecessor_evidence_eligible=bool(facts["predecessor_evidence_eligible"]),
        predecessor_complete=(str(physical["window_status"]) == "WINDOW_CLOSED"),
        freshness_within_contract=bool(safety.get("gate_accepted")),
        governed_provenance_traceable=(
            bool(safety.get("gate_accepted"))
            and bool(safety.get("source_traces"))
        ),
        safety_context_present=bool(facts["safety_context_present"]),
        safety_context_result=str(facts["safety_context_result"]),
        continuity_status=continuity,
        learning_need=None,
        token_budget_available=bool(token_budget_available),
        token_state=lane,
        token_eligible=bool(token_eligible),
        cancelled=bool(cancelled),
        terminal=bool(terminal),
    )
    candidate = {
        "token_slot_id": slot_id,
        "token_row_id": int(slot["token_row_id"]),
        "pair_row_id": int(slot["pair_row_id"]),
        "mint_identity": str(slot["mint_identity"]),
        "pair_identity": str(slot["pair_identity"]),
        "lifecycle_identity": str(slot["lifecycle_identity"]),
        "campaign_window_1h_id": window_id,
        "memory_window_1h_id": memory_window_id,
        "campaign_window_4h_id": campaign_window_id_for(
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            token_slot_id=slot_id,
            window_kind="WINDOW_4H",
            period_key=str(memory_window_id),
        ),
        "tracking_lane": lane,
    }
    return token, candidate


def run_standard_four_hour_campaign_barrier(
    connection: sqlite3.Connection,
    *,
    db_path: str | Path,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    cycle_id: str,
    factory_run_id: str,
    operational_db_binding: Any | None,
    canonical_authoritative_db_path: str | Path,
    cancellation_probe: Any | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Evaluate and atomically hand off through the durable coordinator."""
    from printer_v1.operator_cli.standard_4h_progression import (
        commit_standard_4h_progression_handoff,
        evaluate_standard_4h_progression,
        persist_progression_primary_fault,
        progression_attempt_id_for,
    )

    try:
        evaluation = evaluate_standard_4h_progression(
            connection,
            db_path=str(db_path),
            campaign_id=campaign_id,
            configuration_id=configuration_id,
            campaign_run_id=run_id,
            cycle_id=cycle_id,
            factory_run_id=factory_run_id,
            operational_db_binding=operational_db_binding,
            canonical_authoritative_db_path=str(canonical_authoritative_db_path),
            cancellation_probe=cancellation_probe,
            now=now,
        )
        if evaluation["attempt_state"] == "WAITING_FOR_PREDECESSORS":
            return {
                "status": "AWAITING_PEER_FIRST_HOUR_CLOSE",
                "barrier_reached": False,
                "eligible_token_slot_ids": [],
                "continuation_count": 0,
                "planned_jobs": 0,
            }
        if evaluation["attempt_state"] in {
            "TERMINAL_FAILED", "TERMINAL_CANCELLED", "INTERRUPTED_REVIEW"
        }:
            from printer_v1.operator_cli.standard_4h_progression import (
                StandardFourHourProgressionError,
                load_standard_4h_progression_aggregate,
            )

            terminal = load_standard_4h_progression_aggregate(
                connection,
                campaign_id=campaign_id,
                campaign_run_id=run_id,
                cycle_id=cycle_id,
            )
            terminal_cause = (
                None if terminal is None else terminal["first_terminal_cause"]
            )
            raise StandardFourHourProgressionError(
                f"standard 4h progression terminal: {evaluation['attempt_state']}: "
                f"{terminal_cause or 'CAUSE_UNAVAILABLE'}",
                terminal_cause=terminal_cause,
                terminal_state=str(evaluation["attempt_state"]),
            )
        if evaluation["attempt_state"] not in {
            "ELIGIBILITY_COMPLETE", "HANDOFF_COMMITTED"
        }:
            raise StandardFourHourOperationalError(
                f"unsupported standard 4h progression state: "
                f"{evaluation['attempt_state']}"
            )
        plan = commit_standard_4h_progression_handoff(
            connection,
            campaign_id=campaign_id,
            campaign_run_id=run_id,
            cycle_id=cycle_id,
            factory_run_id=factory_run_id,
            db_path=str(db_path),
            configuration_id=configuration_id,
            operational_db_binding=operational_db_binding,
            canonical_authoritative_db_path=str(canonical_authoritative_db_path),
            cancellation_probe=cancellation_probe,
            now=now,
        )
    except Exception as exc:
        # The predecessor is already committed. Persist the fault only on the
        # canonical progression aggregate. If SQLite itself rejects this write,
        # the last durable non-terminal state remains the read-side truth.
        with connection:
            persist_progression_primary_fault(
                connection,
                progression_attempt_id=progression_attempt_id_for(
                    campaign_id=campaign_id,
                    campaign_run_id=run_id,
                    cycle_id=cycle_id,
                ),
                cause=str(
                    getattr(exc, "terminal_cause", None)
                    or "STANDARD_4H_PROGRESSION_OR_HANDOFF_FAILED"
                ),
                state=str(getattr(exc, "terminal_state", "TERMINAL_FAILED")),
                stage="ATOMIC_HANDOFF",
                exc=exc,
                safe_message=str(exc),
                now=now,
            )
        raise StandardFourHourOperationalError(
            f"standard four-hour campaign planning blocked: {exc}"
        ) from exc
    return {
        "status": "STANDARD_FOUR_HOUR_BARRIER_RELEASED",
        "barrier_reached": True,
        "eligible_token_slot_ids": list(evaluation["eligible_token_slot_ids"]),
        "continuation_count": len(evaluation["eligible_token_slot_ids"]),
        "verdicts": [
            {
                "token_slot_id": str(token["token_slot_id"]),
                "token_id": int(token["token_row_id"]),
                "verdict": (
                    "CONTINUE_TO_WINDOW_4H"
                    if str(token["token_slot_id"])
                    in set(evaluation["eligible_token_slot_ids"])
                    else "BLOCK_CONTINUATION"
                ),
                "reasons": list(token["disposition_reasons"]),
                "disposition": str(token["token_disposition"]),
            }
            for token in evaluation["tokens"]
        ],
        "subset_budget": plan.get("budget", {}),
        "plan": plan,
        "planned_jobs": int(plan.get("planned_jobs", 0)),
        "replay": bool(plan.get("replay")),
    }


__all__ = [
    "AUTOMATIC_RETRIES",
    "ELIGIBILITY_CONTRACT_VERSION",
    "ENDPOINT_ROTATION",
    "LIFECYCLE_REQUESTS_PER_TOKEN",
    "LIFECYCLE_REQUEST_OUTER_CEILING",
    "LIFECYCLE_SCHEDULER_OUTER_CEILING",
    "LOCKED_WINDOWS",
    "POLICY_VERSION",
    "POST_SUPPLY_DURATION_SECONDS",
    "PRE_LIFECYCLE_DURATION_SECONDS",
    "ROOT_MAIN_WINDOW",
    "STANDARD_FOUR_HOUR_MODE",
    "STANDARD_FOUR_HOUR_PREFLIGHT_MODE",
    "STANDARD_WORST_CASE_CONTINUING_MASK",
    "STANDARD_WORST_CASE_TRACKING_LANES",
    "SUCCESSOR_WINDOW",
    "StandardFourHourOperationalError",
    "TOKEN_CAPACITY",
    "evaluate_standard_four_hour_eligibility",
    "run_standard_four_hour_campaign_barrier",
    "standard_four_hour_capacity_contract",
    "standard_four_hour_policy_contract",
]

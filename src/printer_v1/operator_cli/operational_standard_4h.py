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
LIFECYCLE_REQUEST_OUTER_CEILING = 230
LIFECYCLE_SCHEDULER_OUTER_CEILING = 210
AUTOMATIC_RETRIES = 0
ENDPOINT_ROTATION = False
LOCKED_WINDOWS = ("WINDOW_12H", "WINDOW_24H")
ELIGIBILITY_CONTRACT_VERSION = "STANDARD_4H_ELIGIBILITY_V1"


class StandardFourHourOperationalError(ValueError):
    """Fail-closed standard-four-hour operational contract fault."""


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
             AND step_kind='CONTINUATION_CLOSE'
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
    lane = str(close["tracking_lane"] or context.get("tracking_lane") or "")
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
        token_budget_available=True,
        token_state=lane,
        token_eligible=True,
        cancelled=False,
        terminal=False,
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
    now: str | None = None,
) -> dict[str, Any]:
    """Release standard 4h composition exactly once after both 1h closes."""
    if connection.in_transaction:
        raise StandardFourHourOperationalError(
            "standard four-hour barrier requires committed first-hour truth"
        )
    slots = _campaign_identity_rows(
        connection,
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        run_id=run_id,
        cycle_id=cycle_id,
        factory_run_id=factory_run_id,
    )
    states = [
        _owned_first_hour_state(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            factory_run_id=factory_run_id,
            slot=slot,
        )
        for slot in slots
    ]
    terminal_count = sum(1 for state in states if state["terminal"])
    if terminal_count < TOKEN_CAPACITY:
        return {
            "status": "AWAITING_PEER_FIRST_HOUR_CLOSE",
            "barrier_reached": False,
            "successful_first_hour_close_count": terminal_count,
            "eligible_token_slot_ids": [],
            "continuation_count": 0,
            "planned_jobs": 0,
        }

    token_inputs: list[TokenContinuationInput] = []
    candidates: list[dict[str, Any]] = []
    for slot, state in zip(slots, states, strict=True):
        token, candidate = _continuation_input(
            connection,
            db_path=db_path,
            campaign_id=campaign_id,
            configuration_id=configuration_id,
            run_id=run_id,
            cycle_id=cycle_id,
            slot=slot,
            state=state,
        )
        token_inputs.append(token)
        candidates.append(candidate)

    campaign_row = connection.execute(
        "SELECT campaign_state FROM printer_memory_factory_campaigns WHERE campaign_id=?",
        (campaign_id,),
    ).fetchone()
    campaign = CampaignContinuationContext(
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        campaign_state=str(campaign_row[0]) if campaign_row is not None else "TERMINAL_FAILED",
        campaign_eligible=True,
        shared_db_healthy=True,
        shared_lease_healthy=True,
        shared_integrity_healthy=True,
        campaign_budget_available=True,
    )
    results = evaluate_standard_four_hour_eligibility(
        campaign=campaign,
        tokens=tuple(token_inputs),
    )
    eligible = [
        result.token_slot_id
        for result in results
        if result.verdict == ContinuationVerdict.CONTINUE_TO_WINDOW_4H
    ]
    verdicts = [
        {
            "token_slot_id": result.token_slot_id,
            "token_id": result.token_id,
            "verdict": result.verdict.value,
            "reasons": list(result.reasons),
        }
        for result in results
    ]
    lanes = (str(candidates[0]["tracking_lane"]), str(candidates[1]["tracking_lane"]))
    mask = (
        str(candidates[0]["token_slot_id"]) in set(eligible),
        str(candidates[1]["token_slot_id"]) in set(eligible),
    )
    subset_budget = standard_campaign_lifecycle_budget(lanes, mask)
    try:
        plan = plan_standard_campaign_4h_handoff(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            factory_run_id=factory_run_id,
            candidates=candidates,
            eligible_token_slot_ids=eligible,
            execution_authority=FourHourExecutionAuthority.STANDARD_CAMPAIGN,
            now=now,
        )
    except ValueError as exc:
        raise StandardFourHourOperationalError(
            f"standard four-hour campaign planning blocked: {exc}"
        ) from exc
    return {
        "status": "STANDARD_FOUR_HOUR_BARRIER_RELEASED",
        "barrier_reached": True,
        "successful_first_hour_close_count": TOKEN_CAPACITY,
        "eligible_token_slot_ids": list(eligible),
        "continuation_count": len(eligible),
        "verdicts": verdicts,
        "subset_budget": subset_budget,
        "plan": plan,
        "planned_jobs": int(plan.get("planned_jobs", 0)),
        "replay": bool(plan.get("replay")),
    }


__all__ = [
    "AUTOMATIC_RETRIES",
    "ELIGIBILITY_CONTRACT_VERSION",
    "ENDPOINT_ROTATION",
    "LIFECYCLE_REQUEST_OUTER_CEILING",
    "LIFECYCLE_SCHEDULER_OUTER_CEILING",
    "LOCKED_WINDOWS",
    "POLICY_VERSION",
    "POST_SUPPLY_DURATION_SECONDS",
    "PRE_LIFECYCLE_DURATION_SECONDS",
    "ROOT_MAIN_WINDOW",
    "STANDARD_FOUR_HOUR_MODE",
    "STANDARD_FOUR_HOUR_PREFLIGHT_MODE",
    "SUCCESSOR_WINDOW",
    "StandardFourHourOperationalError",
    "TOKEN_CAPACITY",
    "evaluate_standard_four_hour_eligibility",
    "run_standard_four_hour_campaign_barrier",
    "standard_four_hour_policy_contract",
]

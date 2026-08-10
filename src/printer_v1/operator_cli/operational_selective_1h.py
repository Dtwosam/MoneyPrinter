"""V2-9.8B operational selective WINDOW_1H continuation owner.

Extends the existing campaign/factory architecture. Does not create a parallel
production runner. Real operational 1h execution remains disabled unless an
explicit selective_1h_continuation flag is passed (default False). Production
public command stays 15m-only.

Continuation is categorical and token-local. It consumes B.1 authoritative
episodes (not raw PARTIAL window labels), B.2 safety facts when available,
exact lineage, and the 4A token-local continuation policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Mapping, Sequence

from printer_v1.operator_cli.campaign_authority_adapters import (
    CampaignAuthorityAdapterError,
    build_4a_authority_facts,
    load_authoritative_promotion_outcome,
    load_authoritative_window_safety,
)
from printer_v1.operator_cli.campaign_ownership import (
    CampaignOwnershipError,
    bind_authoritative_run_id,
    bind_window_memory_row_id,
    canonical_object_payload,
    persist_standard_first_hour_handoff_set,
    persist_window,
    transition_state,
)
from printer_v1.scheduler.token_local_continuation import (
    CampaignContinuationContext,
    ContinuationLearningNeed,
    ContinuationVerdict,
    ExpectedTokenContinuationIdentity,
    TokenContinuationInput,
    evaluate_token_local_continuations,
)
from printer_v1.snapshots.lifecycle_continuity import CONTINUITY_CONTINUOUS


SELECTIVE_1H_POLICY_VERSION = "V2-9.8B-SELECTIVE-1H-V1"
CONTINUATION_OBJECT_KIND = "CONTINUATION_4A"
WINDOW_15M = "WINDOW_15M"
WINDOW_1H = "WINDOW_1H"
SUCCESSOR_1H = "WINDOW_1H"

# Outcome labels that carry an unresolved 15m→1h TRANSITION learning need.
_TRANSITION_OUTCOMES = frozenset(
    {
        "SHORT_TERM_PUMP",
        "DUMP",
        "SLOW_BLEED",
        "DEAD",
        "HELD_TO_15M_MODERATE_CONTINUATION",
    }
)
# Ordinary movement: stop after 15m with no learning need.
_STOP_OUTCOMES = frozenset({"CONSOLIDATION", "NO_PUMP"})

_LOCKED_DOWNSTREAM = {
    "retrieval_activated": False,
    "paper_decisions": 0,
    "buy_sell_hold": False,
    "positions": 0,
    "trades": 0,
    "audits": 0,
    "pnl": 0,
    "window_4h_enabled": False,
    "window_12h_enabled": False,
    "window_24h_enabled": False,
}

ZERO_ELIGIBLE_CONTINUATIONS = "ZERO_ELIGIBLE_CONTINUATIONS"
ONE_CONTINUATION = "ONE_CONTINUATION"
TWO_CONTINUATIONS = "TWO_CONTINUATIONS"
ONE_CONTINUATION_ONE_BLOCK = "ONE_CONTINUATION_ONE_BLOCK"
FIRST_HOUR_CONTINUATION_BLOCKED = "FIRST_HOUR_CONTINUATION_BLOCKED"
EVALUATION_BLOCKED_SYSTEM_DEFECT = "EVALUATION_BLOCKED_SYSTEM_DEFECT"
EVALUATION_NOT_REACHED = "EVALUATION_NOT_REACHED"


def _classify_standard_first_hour_outcome(
    *,
    decision_set_complete: bool,
    persistence_consistent: bool,
    continue_count: int,
    stop_count: int,
    block_count: int,
) -> str:
    """Classify a complete standard-first-hour decision set truthfully.

    WINDOW_15M -> WINDOW_1H has no normal behavior-driven STOP path after the
    standard-first-hour policy amendment. Any STOP in a complete new-policy
    decision set is therefore an integration/system defect, not a benign
    zero-eligibility outcome.
    """
    if not decision_set_complete or not persistence_consistent:
        return EVALUATION_BLOCKED_SYSTEM_DEFECT
    if stop_count != 0:
        return EVALUATION_BLOCKED_SYSTEM_DEFECT
    if continue_count == 2 and block_count == 0:
        return TWO_CONTINUATIONS
    if continue_count == 1 and block_count == 1:
        return ONE_CONTINUATION_ONE_BLOCK
    if continue_count == 0 and block_count == 2:
        return FIRST_HOUR_CONTINUATION_BLOCKED
    return EVALUATION_BLOCKED_SYSTEM_DEFECT


class Selective1hError(ValueError):
    """Fail-closed selective 1h ownership fault."""


@dataclass(frozen=True)
class Selective1hTokenPlan:
    token_slot_id: str
    token_row_id: int
    pair_row_id: int
    mint_identity: str
    pair_identity: str
    lifecycle_identity: str
    campaign_window_15m_id: str
    memory_window_15m_id: int
    verdict: str
    reasons: tuple[str, ...]
    learning_need: str | None
    authoritative_episode_id: int | None
    campaign_window_1h_id: str | None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads(value: object) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def ensure_authoritative_factory_link(
    connection: sqlite3.Connection,
    *,
    campaign_run_id: str,
    factory_run_id: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Bind campaign run → factory run once. Idempotent on same factory id."""
    result = bind_authoritative_run_id(
        connection,
        campaign_run_id=campaign_run_id,
        factory_run_id=factory_run_id,
        now=now,
    )
    return {
        "bound": result.changed,
        "campaign_run_id": campaign_run_id,
        "authoritative_run_id": factory_run_id,
        "policy_version": SELECTIVE_1H_POLICY_VERSION,
    }


def campaign_window_id_for(
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    token_slot_id: str,
    window_kind: str,
    period_key: str,
) -> str:
    return (
        f"cw:{campaign_id}:{run_id}:{cycle_id}:{token_slot_id}:"
        f"{window_kind}:{period_key}"
    )


def persist_15m_campaign_window(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    token_slot_id: str,
    token_row_id: int,
    pair_row_id: int,
    lifecycle_identity: str,
    memory_window_row_id: int,
    checkpoint_cutoff: str,
    window_state: str = "AUDITING",
    now: str | None = None,
) -> dict[str, Any]:
    """Persist or re-bind one WINDOW_15M campaign window for a closed memory row."""
    stamp = now or _utc_now()
    period_key = str(memory_window_row_id)
    window_id = campaign_window_id_for(
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        token_slot_id=token_slot_id,
        window_kind=WINDOW_15M,
        period_key=period_key,
    )
    existing = connection.execute(
        "SELECT window_id, memory_window_row_id, window_state "
        "FROM printer_memory_factory_campaign_windows WHERE window_id=?",
        (window_id,),
    ).fetchone()
    if existing is None:
        persist_window(
            connection,
            window_id=window_id,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            token_slot_id=token_slot_id,
            token_row_id=token_row_id,
            pair_row_id=pair_row_id,
            window_kind=WINDOW_15M,
            root_15m_lifecycle_identity=lifecycle_identity,
            memory_window_row_id=memory_window_row_id,
            checkpoint_cutoff=checkpoint_cutoff,
            now=stamp,
        )
        # Advance PLANNED → COLLECTING → CLOSE_PENDING → AUDITING, then optional terminal.
        path = ("PLANNED", "COLLECTING", "CLOSE_PENDING", "AUDITING")
        target = window_state if window_state in path else "AUDITING"
        for index in range(len(path) - 1):
            expected = path[index]
            new_state = path[index + 1]
            transition_state(
                connection,
                record_kind="window",
                identity=window_id,
                expected_state=expected,
                new_state=new_state,
                now=stamp,
            )
            if new_state == target:
                break
        if window_state not in path:
            transition_state(
                connection,
                record_kind="window",
                identity=window_id,
                expected_state="AUDITING",
                new_state=window_state,
                terminal_cause=f"15M_{window_state}",
                now=stamp,
            )
    else:
        if existing[1] is None:
            bind_window_memory_row_id(
                connection,
                window_id=window_id,
                memory_window_row_id=memory_window_row_id,
                now=stamp,
            )
        elif int(existing[1]) != int(memory_window_row_id):
            raise Selective1hError(
                "15m campaign window already bound to a different memory row"
            )
    return {
        "window_id": window_id,
        "memory_window_row_id": memory_window_row_id,
        "window_kind": WINDOW_15M,
        "idempotent": existing is not None,
    }


def reconcile_15m_campaign_window(
    connection: sqlite3.Connection,
    *,
    campaign_window_id: str,
    promotion: Mapping[str, Any],
    now: str | None = None,
) -> dict[str, Any]:
    """Terminalize a completed predecessor from its authoritative B.1 truth."""
    row = connection.execute(
        """SELECT window_state, memory_window_row_id
           FROM printer_memory_factory_campaign_windows WHERE window_id=?""",
        (campaign_window_id,),
    ).fetchone()
    if row is None or row["memory_window_row_id"] is None:
        raise Selective1hError("15m campaign window lacks terminal lineage")
    memory = connection.execute(
        """SELECT window_status, memory_quality_label, data_quality_label,
                  do_not_train
           FROM printer_memory_windows WHERE id=?""",
        (int(row["memory_window_row_id"]),),
    ).fetchone()
    if memory is None or str(memory["window_status"]) != "WINDOW_CLOSED":
        raise Selective1hError("15m predecessor is not authoritatively closed")

    status = str(promotion.get("promotion_status") or "NO_PROMOTION")
    if status in {"CLEAN_PROMOTED", "ALREADY_EXISTS_IDEMPOTENT"}:
        terminal_state = "CLEAN_PROMOTED"
    elif (
        bool(memory["do_not_train"])
        or str(memory["memory_quality_label"])
        in {"DIRTY_MEMORY", "DO_NOT_TRAIN"}
        or str(memory["data_quality_label"])
        in {
            "DIRTY_DATA",
            "STALE_DATA",
            "MISSING_CRITICAL_DATA",
            "CONFLICTING_DATA",
            "DO_NOT_TRAIN",
        }
    ):
        terminal_state = "DIRTY"
    elif status == "DIRTY_OR_BLOCKED" or promotion.get("blocked_reason"):
        terminal_state = "BLOCKED"
    else:
        terminal_state = "NO_PROMOTION"

    current = str(row["window_state"])
    if current == terminal_state:
        return {
            "window_id": campaign_window_id,
            "window_state": current,
            "changed": False,
        }
    if current != "AUDITING":
        raise Selective1hError(
            f"15m campaign window terminal conflict: {current} != {terminal_state}"
        )
    transition = transition_state(
        connection,
        record_kind="window",
        identity=campaign_window_id,
        expected_state="AUDITING",
        new_state=terminal_state,
        terminal_cause=f"15M_{terminal_state}",
        now=now or _utc_now(),
    )
    return {
        "window_id": campaign_window_id,
        "window_state": transition.current_state,
        "changed": transition.changed,
    }


def _slot_rows(
    connection: sqlite3.Connection, *, campaign_id: str, run_id: str, cycle_id: str
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT * FROM printer_memory_factory_campaign_token_slots
        WHERE campaign_id=? AND run_id=? AND cycle_id=?
        ORDER BY slot_ordinal
        """,
        (campaign_id, run_id, cycle_id),
    ).fetchall()
    return [dict(row) for row in rows]


def _learning_need_from_window(
    connection: sqlite3.Connection, memory_window_id: int
) -> str | None:
    row = connection.execute(
        """SELECT outcome_label, memory_quality_label, data_quality_label,
                  do_not_train, window_status, window_kind
           FROM printer_memory_windows WHERE id=?""",
        (int(memory_window_id),),
    ).fetchone()
    if row is None:
        return None
    if str(row["window_kind"]) != WINDOW_15M:
        return None
    if str(row["window_status"]) != "WINDOW_CLOSED":
        return None
    outcome = str(row["outcome_label"] or "")
    if outcome in _STOP_OUTCOMES or outcome in {"", "OUTCOME_UNKNOWN"}:
        return None
    if outcome in _TRANSITION_OUTCOMES:
        return ContinuationLearningNeed.TRANSITION.value
    # Unknown mapped outcomes still may need coverage when clean-promoted.
    return ContinuationLearningNeed.COVERAGE.value


def _promotion_facts(
    db_path: str,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    token_slot_id: str,
    campaign_window_id: str,
) -> dict[str, Any]:
    try:
        return load_authoritative_promotion_outcome(
            db_path,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            token_slot_id=token_slot_id,
            window_id=campaign_window_id,
        )
    except CampaignAuthorityAdapterError as exc:
        return {
            "authority": "B.1_AUTHORITATIVE_PROMOTION",
            "promotion_status": "NO_PROMOTION",
            "authoritative_episode_id": None,
            "blocked_reason": str(exc),
            "campaign_id": campaign_id,
            "run_id": run_id,
            "cycle_id": cycle_id,
            "token_slot_id": token_slot_id,
            "window_id": campaign_window_id,
        }


def _continuity_for_window(
    connection: sqlite3.Connection, memory_window_id: int
) -> str:
    row = connection.execute(
        "SELECT supporting_context_json FROM printer_memory_windows WHERE id=?",
        (int(memory_window_id),),
    ).fetchone()
    if row is None:
        return "CONTINUITY_BLOCKED"
    ctx = _loads(row[0])
    continuity = ctx.get("continuity") or {}
    status = continuity.get("status") or ctx.get("continuity_status")
    if status:
        return str(status)
    return CONTINUITY_CONTINUOUS


def evaluate_selective_1h_for_cycle(
    connection: sqlite3.Connection,
    *,
    db_path: str,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    cycle_id: str,
    campaign_state: str = "RUNNING",
    campaign_budget_available: bool = True,
    shared_db_healthy: bool = True,
    shared_lease_healthy: bool = True,
    shared_integrity_healthy: bool = True,
    now: str | None = None,
) -> dict[str, Any]:
    """Evaluate exactly the cycle's token slots for selective 15m→1h.

    Requires campaign windows for WINDOW_15M already persisted with
    memory_window_row_id and bound authoritative_run_id.
    """
    stamp = now or _utc_now()
    slots = _slot_rows(connection, campaign_id=campaign_id, run_id=run_id, cycle_id=cycle_id)
    if len(slots) != 2:
        raise Selective1hError(
            f"selective 1h requires exactly two token slots; found {len(slots)}"
        )

    campaign_ctx = CampaignContinuationContext(
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        campaign_state=campaign_state,
        campaign_eligible=True,
        shared_db_healthy=shared_db_healthy,
        shared_lease_healthy=shared_lease_healthy,
        shared_integrity_healthy=shared_integrity_healthy,
        campaign_budget_available=campaign_budget_available,
    )

    token_inputs: list[TokenContinuationInput] = []
    meta: list[dict[str, Any]] = []

    for slot in slots:
        token_slot_id = str(slot["token_slot_id"])
        window_row = connection.execute(
            """
            SELECT * FROM printer_memory_factory_campaign_windows
            WHERE campaign_id=? AND run_id=? AND cycle_id=? AND token_slot_id=?
              AND window_kind=?
            ORDER BY created_at DESC LIMIT 1
            """,
            (campaign_id, run_id, cycle_id, token_slot_id, WINDOW_15M),
        ).fetchone()
        if window_row is None or window_row["memory_window_row_id"] is None:
            raise Selective1hError(
                f"missing WINDOW_15M campaign window lineage for {token_slot_id}"
            )
        campaign_window_id = str(window_row["window_id"])
        memory_window_id = int(window_row["memory_window_row_id"])
        promotion = _promotion_facts(
            db_path,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            token_slot_id=token_slot_id,
            campaign_window_id=campaign_window_id,
        )
        reconcile_15m_campaign_window(
            connection,
            campaign_window_id=campaign_window_id,
            promotion=promotion,
            now=stamp,
        )
        safety = load_authoritative_window_safety(
            db_path,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            token_slot_id=token_slot_id,
            window_id=campaign_window_id,
        )
        try:
            facts = build_4a_authority_facts(promotion, safety)
        except CampaignAuthorityAdapterError as exc:
            facts = {
                "predecessor_evidence_eligible": False,
                "predecessor_memory_quality": "DO_NOT_TRAIN",
                "safety_context_present": False,
                "safety_context_result": "SAFETY_CONTEXT_UNKNOWN",
                "blocked_reason": str(exc),
            }

        learning_need = _learning_need_from_window(connection, memory_window_id)
        continuity = _continuity_for_window(connection, memory_window_id)
        mw = connection.execute(
            """SELECT window_status, memory_quality_label, data_quality_label,
                      do_not_train FROM printer_memory_windows WHERE id=?""",
            (memory_window_id,),
        ).fetchone()
        if mw is None:
            raise Selective1hError(f"memory window missing: {memory_window_id}")

        # Authoritative quality for 4A is the promotion-derived CLEAN_MEMORY,
        # not the raw candidate PARTIAL window label.
        predecessor_quality = facts["predecessor_memory_quality"]
        expected = ExpectedTokenContinuationIdentity(
            token_slot_id=token_slot_id,
            token_id=str(slot["token_row_id"]),
            mint_id=str(slot["mint_identity"]),
            pair_id=str(slot["pair_row_id"]),
            lifecycle_id=str(slot["lifecycle_identity"]),
            predecessor_window_id=campaign_window_id,
        )
        token_inputs.append(
            TokenContinuationInput(
                campaign_id=campaign_id,
                configuration_id=configuration_id,
                token_slot_id=token_slot_id,
                token_id=str(slot["token_row_id"]),
                mint_id=str(slot["mint_identity"]),
                pair_id=str(slot["pair_row_id"]),
                lifecycle_id=str(slot["lifecycle_identity"]),
                predecessor_window_id=campaign_window_id,
                expected_identity=expected,
                predecessor_window_kind=WINDOW_15M,
                successor_window_kind=SUCCESSOR_1H,
                predecessor_window_status=str(mw["window_status"]),
                predecessor_memory_quality=str(predecessor_quality),
                predecessor_data_quality=str(mw["data_quality_label"]),
                predecessor_do_not_train=bool(mw["do_not_train"]),
                predecessor_evidence_eligible=bool(
                    facts.get("predecessor_evidence_eligible")
                ),
                predecessor_complete=True,
                freshness_within_contract=True,
                governed_provenance_traceable=True,
                safety_context_present=bool(facts.get("safety_context_present")),
                safety_context_result=str(
                    facts.get("safety_context_result") or "SAFETY_CONTEXT_UNKNOWN"
                ),
                continuity_status=continuity,
                learning_need=learning_need,
                token_budget_available=True,
                token_state="TRACK_NORMAL",
                token_eligible=True,
                cancelled=False,
                terminal=False,
            )
        )
        meta.append(
            {
                "token_slot_id": token_slot_id,
                "token_row_id": int(slot["token_row_id"]),
                "pair_row_id": int(slot["pair_row_id"]),
                "mint_identity": str(slot["mint_identity"]),
                "pair_identity": str(slot["pair_identity"]),
                "lifecycle_identity": str(slot["lifecycle_identity"]),
                "campaign_window_15m_id": campaign_window_id,
                "memory_window_15m_id": memory_window_id,
                "authoritative_episode_id": promotion.get("authoritative_episode_id"),
                "learning_need": learning_need,
                "promotion_status": promotion.get("promotion_status"),
            }
        )

    results = evaluate_token_local_continuations(
        campaign=campaign_ctx, tokens=token_inputs
    )
    candidates: list[dict[str, Any]] = []
    for result, info in zip(results, meta, strict=True):
        continue_ok = result.verdict == ContinuationVerdict.CONTINUE_TO_WINDOW_1H
        window_1h_id = None
        if continue_ok:
            window_1h_id = campaign_window_id_for(
                campaign_id=campaign_id,
                run_id=run_id,
                cycle_id=cycle_id,
                token_slot_id=info["token_slot_id"],
                window_kind=WINDOW_1H,
                period_key=str(info["memory_window_15m_id"]),
            )
        payload = {
            "policy_version": SELECTIVE_1H_POLICY_VERSION,
            "verdict": str(result.verdict),
            "reasons": list(result.reasons),
            "token_slot_id": info["token_slot_id"],
            "token_row_id": info["token_row_id"],
            "pair_row_id": info["pair_row_id"],
            "predecessor_campaign_window_id": info["campaign_window_15m_id"],
            "predecessor_memory_window_id": info["memory_window_15m_id"],
            "authoritative_episode_id": info["authoritative_episode_id"],
            "learning_need": info["learning_need"],
            "successor_window_kind": WINDOW_1H if continue_ok else None,
            "campaign_window_1h_id": window_1h_id,
            "locked_downstream": dict(_LOCKED_DOWNSTREAM),
        }
        object_id = (
            f"cont4a:{campaign_id}:{run_id}:{cycle_id}:"
            f"{info['token_slot_id']}:{info['memory_window_15m_id']}"
        )
        candidates.append(
            {
                "object_id": object_id,
                "payload": payload,
                "info": info,
                "continue_ok": continue_ok,
            }
        )

    existing_rows = connection.execute(
        """
        SELECT object_id, object_json, object_hash
        FROM printer_memory_factory_campaign_objects
        WHERE campaign_id=? AND run_id=? AND cycle_id=? AND object_kind=?
        ORDER BY object_id
        """,
        (campaign_id, run_id, cycle_id, CONTINUATION_OBJECT_KIND),
    ).fetchall()
    expected_ids = {str(item["object_id"]) for item in candidates}
    existing_by_id = {str(row["object_id"]): dict(row) for row in existing_rows}
    if existing_by_id and set(existing_by_id) != expected_ids:
        raise Selective1hError(
            "partial or foreign CONTINUATION_4A object set conflicts with evaluation"
        )

    first_evaluation = not existing_by_id
    objects: list[dict[str, Any]] = []
    for candidate in candidates:
        object_id = str(candidate["object_id"])
        payload = dict(candidate["payload"])
        if not first_evaluation:
            persisted = _loads(existing_by_id[object_id]["object_json"])
            _, candidate_hash = canonical_object_payload(payload)
            if (
                candidate_hash != str(existing_by_id[object_id]["object_hash"])
                or persisted != payload
            ):
                raise Selective1hError(
                    f"conflicting recomputation for immutable {object_id}"
                )
            payload = persisted
            candidate["payload"] = persisted
        else:
            # The complete first-evaluation set is persisted atomically below,
            # together with any WINDOW_1H successors and token-state advancement.
            pass
        objects.append(
            {
                "object_id": object_id,
                "created": first_evaluation,
                "payload": payload,
            }
        )

    # First-evaluation persistence is one canonical ownership transaction:
    # both immutable decisions, every WINDOW_1H successor, and token-slot state.
    if first_evaluation:
        try:
            persist_standard_first_hour_handoff_set(
                connection,
                campaign_id=campaign_id,
                configuration_id=configuration_id,
                run_id=run_id,
                cycle_id=cycle_id,
                object_kind=CONTINUATION_OBJECT_KIND,
                candidates=candidates,
                now=stamp,
            )
        except CampaignOwnershipError as exc:
            raise Selective1hError(str(exc)) from exc

    plans: list[Selective1hTokenPlan] = []
    for candidate in candidates:
        info = candidate["info"]
        payload = candidate["payload"]
        plans.append(
            Selective1hTokenPlan(
                token_slot_id=info["token_slot_id"],
                token_row_id=info["token_row_id"],
                pair_row_id=info["pair_row_id"],
                mint_identity=info["mint_identity"],
                pair_identity=info["pair_identity"],
                lifecycle_identity=info["lifecycle_identity"],
                campaign_window_15m_id=info["campaign_window_15m_id"],
                memory_window_15m_id=info["memory_window_15m_id"],
                verdict=str(payload["verdict"]),
                reasons=tuple(payload["reasons"]),
                learning_need=info["learning_need"],
                authoritative_episode_id=info["authoritative_episode_id"],
                campaign_window_1h_id=payload["campaign_window_1h_id"],
            )
        )

    continue_count = sum(
        1 for p in plans if p.verdict == ContinuationVerdict.CONTINUE_TO_WINDOW_1H
    )
    return {
        "policy_version": SELECTIVE_1H_POLICY_VERSION,
        "campaign_id": campaign_id,
        "run_id": run_id,
        "cycle_id": cycle_id,
        "token_plans": [
            {
                "token_slot_id": p.token_slot_id,
                "token_row_id": p.token_row_id,
                "pair_row_id": p.pair_row_id,
                "verdict": p.verdict,
                "reasons": list(p.reasons),
                "learning_need": p.learning_need,
                "authoritative_episode_id": p.authoritative_episode_id,
                "campaign_window_15m_id": p.campaign_window_15m_id,
                "memory_window_15m_id": p.memory_window_15m_id,
                "campaign_window_1h_id": p.campaign_window_1h_id,
            }
            for p in plans
        ],
        "continuation_objects": objects,
        "continue_count": continue_count,
        "stop_count": sum(
            1
            for p in plans
            if p.verdict == ContinuationVerdict.STOP_AFTER_WINDOW_15M
        ),
        "block_count": sum(
            1 for p in plans if p.verdict == ContinuationVerdict.BLOCK_CONTINUATION
        ),
        "selective_1h_enabled_path": True,
        "evaluation_created": first_evaluation,
        "idempotent": not first_evaluation,
        "locked_downstream": dict(_LOCKED_DOWNSTREAM),
        "evaluated_at": stamp,
    }


def should_continue_token(
    evaluation: Mapping[str, Any], *, token_id: int
) -> bool:
    for plan in evaluation.get("token_plans") or ():
        if int(plan["token_row_id"]) == int(token_id):
            return plan["verdict"] == ContinuationVerdict.CONTINUE_TO_WINDOW_1H.value
    return False


def bind_1h_memory_window(
    connection: sqlite3.Connection,
    *,
    campaign_window_1h_id: str,
    memory_window_row_id: int,
    terminal_state: str,
    terminal_cause: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Bind closed 1h memory row onto campaign window and terminalize state."""
    stamp = now or _utc_now()
    bind_window_memory_row_id(
        connection,
        window_id=campaign_window_1h_id,
        memory_window_row_id=memory_window_row_id,
        now=stamp,
    )
    row = connection.execute(
        "SELECT window_state FROM printer_memory_factory_campaign_windows "
        "WHERE window_id=?",
        (campaign_window_1h_id,),
    ).fetchone()
    if row is None:
        raise Selective1hError(f"1h campaign window missing: {campaign_window_1h_id}")
    current = str(row[0])
    # Walk non-terminal path then terminalize.
    sequence = ["PLANNED", "COLLECTING", "CLOSE_PENDING", "AUDITING"]
    if current in sequence:
        idx = sequence.index(current)
        for expected in sequence[idx:-1]:
            nxt = sequence[sequence.index(expected) + 1]
            transition_state(
                connection,
                record_kind="window",
                identity=campaign_window_1h_id,
                expected_state=expected,
                new_state=nxt,
                now=stamp,
            )
        current = "AUDITING"
    if current == "AUDITING":
        transition_state(
            connection,
            record_kind="window",
            identity=campaign_window_1h_id,
            expected_state="AUDITING",
            new_state=terminal_state,
            terminal_cause=terminal_cause,
            now=stamp,
        )
    return {
        "window_id": campaign_window_1h_id,
        "memory_window_row_id": memory_window_row_id,
        "window_state": terminal_state,
    }


def summarize_selective_1h_reporting(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
) -> dict[str, Any]:
    """Read-only reporting snapshot for terminal reports."""
    auth = connection.execute(
        "SELECT authoritative_run_id FROM printer_memory_factory_campaign_runs "
        "WHERE run_id=?",
        (run_id,),
    ).fetchone()
    windows = [
        dict(row)
        for row in connection.execute(
            """SELECT window_id, window_kind, window_state, token_slot_id,
                      memory_window_row_id, predecessor_window_id, support_only
               FROM printer_memory_factory_campaign_windows
               WHERE campaign_id=? AND run_id=?
               ORDER BY created_at, window_id""",
            (campaign_id, run_id),
        ).fetchall()
    ]
    objects = [
        dict(row)
        for row in connection.execute(
            """SELECT object_id, object_kind, object_json, authoritative_episode_id
               FROM printer_memory_factory_campaign_objects
               WHERE campaign_id=? AND run_id=? AND object_kind=?
               ORDER BY created_at, object_id""",
            (campaign_id, run_id, CONTINUATION_OBJECT_KIND),
        ).fetchall()
    ]
    token_plans = [_loads(row["object_json"]) for row in objects]
    continue_count = sum(
        1
        for plan in token_plans
        if plan.get("verdict") == ContinuationVerdict.CONTINUE_TO_WINDOW_1H.value
    )
    stop_count = sum(
        1
        for plan in token_plans
        if plan.get("verdict") == ContinuationVerdict.STOP_AFTER_WINDOW_15M.value
    )
    block_count = sum(
        1
        for plan in token_plans
        if plan.get("verdict") == ContinuationVerdict.BLOCK_CONTINUATION.value
    )
    factory_config: dict[str, Any] = {}
    if auth is not None and auth[0]:
        config_row = connection.execute(
            "SELECT config_json FROM printer_memory_factory_runs WHERE run_id=?",
            (auth[0],),
        ).fetchone()
        if config_row is not None:
            factory_config = _loads(config_row[0])
    if not factory_config:
        campaign_config = connection.execute(
            """SELECT c.configuration_json
               FROM printer_memory_factory_campaign_runs AS r
               JOIN printer_memory_factory_campaign_configurations AS c
                 ON c.campaign_id = r.campaign_id
               WHERE r.run_id=? AND r.campaign_id=?""",
            (run_id, campaign_id),
        ).fetchone()
        if campaign_config is not None:
            factory_config = _loads(campaign_config[0])
    selective_authorized = bool(factory_config.get("selective_1h_continuation"))
    close_counts = {str(row[0]): int(row[1]) for row in connection.execute(
        """SELECT step_status, COUNT(*)
           FROM printer_memory_factory_run_steps
           WHERE run_id=? AND step_kind='WINDOW_CLOSE'
           GROUP BY step_status""",
        (None if auth is None else auth[0],),
    ).fetchall()}
    counts_by_kind = {
        kind: sum(1 for w in windows if w["window_kind"] == kind)
        for kind in (WINDOW_15M, WINDOW_1H, "WINDOW_4H", "WINDOW_5M_MICRO_EVENT")
    }
    decision_set_complete = (
        len(token_plans) == 2
        and continue_count + stop_count + block_count == 2
    )
    persistence_consistent = counts_by_kind[WINDOW_1H] == continue_count
    if decision_set_complete and persistence_consistent:
        selective_outcome = _classify_standard_first_hour_outcome(
            decision_set_complete=decision_set_complete,
            persistence_consistent=persistence_consistent,
            continue_count=continue_count,
            stop_count=stop_count,
            block_count=block_count,
        )
    elif token_plans or (
        selective_authorized
        and close_counts.get("SUCCEEDED", 0) > 0
        and sum(close_counts.values()) == close_counts.get("SUCCEEDED", 0)
    ):
        selective_outcome = EVALUATION_BLOCKED_SYSTEM_DEFECT
    else:
        selective_outcome = EVALUATION_NOT_REACHED

    counts_by_kind_and_state: dict[str, dict[str, int]] = {}
    for window in windows:
        kind = str(window["window_kind"])
        state = str(window["window_state"])
        counts_by_kind_and_state.setdefault(kind, {})[state] = (
            counts_by_kind_and_state.setdefault(kind, {}).get(state, 0) + 1
        )
    return {
        "authoritative_run_id": None if auth is None else auth[0],
        "windows": windows,
        "continuation_objects": objects,
        "token_plans": token_plans,
        "continue_count": continue_count,
        "block_count": block_count,
        "stop_count": stop_count,
        "window_counts_by_kind": counts_by_kind,
        "window_counts_by_kind_and_state": counts_by_kind_and_state,
        "actual_persisted_window_1h_count": counts_by_kind[WINDOW_1H],
        "selective_1h_outcome": selective_outcome,
        "selective_1h_authorized": selective_authorized,
        "zero_continuation": decision_set_complete and continue_count == 0,
        "locked_downstream": dict(_LOCKED_DOWNSTREAM),
        "restart_created": False,
        "successor_created": False,
    }


def load_selective_1h_reporting(
    db_path: str,
    *,
    campaign_id: str,
    run_id: str,
) -> dict[str, Any]:
    """Load the canonical selective projection without creating writes."""
    from printer_v1.operator_cli.campaign_authority_adapters import _read_only_database

    with _read_only_database(db_path) as connection:
        return summarize_selective_1h_reporting(
            connection, campaign_id=campaign_id, run_id=run_id
        )

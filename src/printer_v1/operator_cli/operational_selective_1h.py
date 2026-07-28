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
)
from printer_v1.operator_cli.campaign_ownership import (
    CampaignOwnershipError,
    bind_authoritative_run_id,
    bind_window_memory_row_id,
    persist_immutable_object,
    persist_window,
    transition_state,
)
from printer_v1.safety.composite import (
    SAFETY_CONTEXT_ACCEPTABLE,
    SAFETY_CONTEXT_BLOCKED,
    SAFETY_CONTEXT_UNKNOWN,
    composite_row_is_acceptable,
    effective_safety_context_report,
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


def _safety_stub(graph: Mapping[str, Any], *, reason: str) -> dict[str, Any]:
    """When B.2 composite is absent, fail closed with explicit reason."""
    return {
        "authority": "B.2_EFFECTIVE_SAFETY",
        "campaign_id": graph["campaign_id"],
        "run_id": graph["run_id"],
        "cycle_id": graph["cycle_id"],
        "token_slot_id": graph["token_slot_id"],
        "window_id": graph["window_id"],
        "window_kind": graph.get("window_kind", WINDOW_15M),
        "checkpoint_object_id": "absent",
        "safety_composite_id": None,
        "gate_accepted": None,
        "effective_safety_context": {
            "effective_safety_context_result": "SAFETY_CONTEXT_UNKNOWN",
        },
        "reasons": [reason],
        "read_only": True,
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
        safety = _safety_stub(
            {
                "campaign_id": campaign_id,
                "run_id": run_id,
                "cycle_id": cycle_id,
                "token_slot_id": token_slot_id,
                "window_id": campaign_window_id,
                "window_kind": WINDOW_15M,
            },
            reason="selective_1h_uses_promotion_authority_without_required_b2_composite",
        )
        # Prefer explicit safety composite if present for this memory window.
        composite = connection.execute(
            """
            SELECT *
            FROM printer_safety_evidence_composites
            WHERE memory_window_id=?
            ORDER BY id DESC LIMIT 1
            """,
            (memory_window_id,),
        ).fetchone()
        if composite is not None:
            composite_map = dict(composite)
            accepted = composite_row_is_acceptable(composite_map)
            effective = effective_safety_context_report(
                composite_map,
                gate_accepted=accepted,
                window_kind=WINDOW_15M,
            )
            safety = {
                "authority": "B.2_EFFECTIVE_SAFETY",
                "campaign_id": campaign_id,
                "run_id": run_id,
                "cycle_id": cycle_id,
                "token_slot_id": token_slot_id,
                "window_id": campaign_window_id,
                "window_kind": WINDOW_15M,
                "checkpoint_object_id": f"composite:{composite_map['id']}",
                "safety_composite_id": int(composite_map["id"]),
                "gate_accepted": accepted,
                "effective_safety_context": effective,
                "reasons": [] if accepted else ["safety_composite_not_acceptable"],
                "read_only": True,
            }
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
    plans: list[Selective1hTokenPlan] = []
    objects: list[dict[str, Any]] = []

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
            existing_1h = connection.execute(
                "SELECT window_id FROM printer_memory_factory_campaign_windows "
                "WHERE window_id=?",
                (window_1h_id,),
            ).fetchone()
            if existing_1h is None:
                persist_window(
                    connection,
                    window_id=window_1h_id,
                    campaign_id=campaign_id,
                    run_id=run_id,
                    cycle_id=cycle_id,
                    token_slot_id=info["token_slot_id"],
                    token_row_id=info["token_row_id"],
                    pair_row_id=info["pair_row_id"],
                    window_kind=WINDOW_1H,
                    root_15m_lifecycle_identity=info["lifecycle_identity"],
                    predecessor_window_id=info["campaign_window_15m_id"],
                    checkpoint_cutoff=stamp,
                    now=stamp,
                )
            # Slot transitions toward 1h continuation (fail soft if already advanced).
            try:
                transition_state(
                    connection,
                    record_kind="token_slot",
                    identity=info["token_slot_id"],
                    expected_state="SELECTED",
                    new_state="WINDOW_15M_ACTIVE",
                    now=stamp,
                )
            except CampaignOwnershipError:
                pass
            for expected, new_state in (
                ("WINDOW_15M_ACTIVE", "WINDOW_15M_CLOSED"),
                ("WINDOW_15M_CLOSED", "WINDOW_1H_CONTINUING"),
            ):
                try:
                    transition_state(
                        connection,
                        record_kind="token_slot",
                        identity=info["token_slot_id"],
                        expected_state=expected,
                        new_state=new_state,
                        now=stamp,
                    )
                except CampaignOwnershipError:
                    continue

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
        existing_obj = connection.execute(
            "SELECT object_id FROM printer_memory_factory_campaign_objects "
            "WHERE object_id=?",
            (object_id,),
        ).fetchone()
        if existing_obj is None:
            persist_immutable_object(
                connection,
                object_id=object_id,
                object_kind=CONTINUATION_OBJECT_KIND,
                campaign_id=campaign_id,
                configuration_id=configuration_id,
                run_id=run_id,
                cycle_id=cycle_id,
                token_slot_id=info["token_slot_id"],
                window_id=info["campaign_window_15m_id"],
                payload=payload,
                authoritative_episode_id=info["authoritative_episode_id"],
                now=stamp,
            )
            created = True
        else:
            created = False
        objects.append(
            {
                "object_id": object_id,
                "created": created,
                "payload": payload,
            }
        )
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
                verdict=str(result.verdict),
                reasons=tuple(result.reasons),
                learning_need=info["learning_need"],
                authoritative_episode_id=info["authoritative_episode_id"],
                campaign_window_1h_id=window_1h_id,
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
    return {
        "authoritative_run_id": None if auth is None else auth[0],
        "windows": windows,
        "continuation_objects": objects,
        "window_counts_by_kind": {
            kind: sum(1 for w in windows if w["window_kind"] == kind)
            for kind in (WINDOW_15M, WINDOW_1H, "WINDOW_4H", "WINDOW_5M_MICRO_EVENT")
        },
        "locked_downstream": dict(_LOCKED_DOWNSTREAM),
    }

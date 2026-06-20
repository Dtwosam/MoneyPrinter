"""Paper-only action labeling from clean memory evidence."""

from typing import Any, Mapping

from printer_v1.memory.contracts import ActionLessonLabel, EpisodeOutcomeLabel
from printer_v1.paper_decision.contracts import (
    DecisionGateLabel,
    PaperDecisionActionLabel,
    PaperDecisionStatusLabel,
)
from printer_v1.paper_decision.gates import classify_decision_gate


PROFIT_OUTCOMES = {
    EpisodeOutcomeLabel.REALISTIC_PAPER_PROFIT.value,
    EpisodeOutcomeLabel.SUSTAINED_PUMP.value,
    EpisodeOutcomeLabel.EXTENDED_PUMP.value,
}

PROTECTION_OUTCOMES = {
    EpisodeOutcomeLabel.REALISTIC_CAPITAL_PROTECTION.value,
    EpisodeOutcomeLabel.DUMP.value,
    EpisodeOutcomeLabel.PUMP_AND_DUMP.value,
    EpisodeOutcomeLabel.ROUND_TRIP.value,
    EpisodeOutcomeLabel.FAKE_PUMP.value,
    EpisodeOutcomeLabel.DEAD_TOKEN.value,
    EpisodeOutcomeLabel.UNREALISTIC_PROFIT.value,
}


def clean_matches(evidence: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    retrieval = evidence.get("memory_retrieval") or {}
    return list(retrieval.get("clean_matches") or [])


def current_context_allows_realistic_entry_exit(evidence: Mapping[str, Any]) -> bool:
    context = evidence.get("current_context") or {}
    exit_label = context.get("exit_realism_label")
    entry_label = context.get("entry_realism_label")
    realism_gate = context.get("realism_gate_label")
    return (
        exit_label in {"EXIT_REALISTIC", "EXIT_POSSIBLE_WITH_SLIPPAGE"}
        and (entry_label in {None, "ENTRY_REALISTIC", "ENTRY_POSSIBLE_WITH_SLIPPAGE"})
        and realism_gate in {None, "REALISM_CONTEXT_ACCEPTABLE", "REALISM_CONTEXT_CAUTION"}
    )


def current_context_is_mixed_but_not_unsafe(evidence: Mapping[str, Any]) -> bool:
    context = evidence.get("current_context") or {}
    caution_values = {
        "SAFETY_CAUTION",
        "SAFETY_SUSPICIOUS",
        "LIQUIDITY_THIN",
        "EXIT_AT_RISK",
        "REALISM_CONTEXT_CAUTION",
        "FLOW_WASH_LIKE",
        "TREND_CHOPPY",
        "CHART_CONTEXT_CAUTION",
    }
    unsafe_values = {"SAFETY_UNSAFE", "EXIT_UNREALISTIC", "ROUTE_NOT_AVAILABLE", "REALISM_CONTEXT_BLOCKED"}
    return any(value in caution_values for value in context.values()) and not any(value in unsafe_values for value in context.values())


def classify_requested_action_from_memory_evidence(evidence: Mapping[str, Any]) -> PaperDecisionActionLabel:
    matches = clean_matches(evidence)
    if not matches:
        return PaperDecisionActionLabel.NO_ACTION
    outcomes = {match.get("outcome_label") for match in matches}
    lessons = {match.get("action_lesson_label") for match in matches}
    if outcomes & PROTECTION_OUTCOMES or ActionLessonLabel.ACTION_AVOID_WORKED.value in lessons:
        return PaperDecisionActionLabel.AVOID
    if current_context_is_mixed_but_not_unsafe(evidence):
        return PaperDecisionActionLabel.WAIT
    if outcomes & PROFIT_OUTCOMES and current_context_allows_realistic_entry_exit(evidence):
        return PaperDecisionActionLabel.BUY
    if outcomes & PROFIT_OUTCOMES:
        return PaperDecisionActionLabel.WAIT
    return PaperDecisionActionLabel.WAIT


def classify_final_paper_action(evidence: Mapping[str, Any]) -> PaperDecisionActionLabel:
    gate = classify_decision_gate(evidence)
    if gate != DecisionGateLabel.DECISION_ALLOWED:
        return PaperDecisionActionLabel.NO_ACTION
    requested = evidence.get("requested_action_label")
    if requested is not None:
        requested_label = PaperDecisionActionLabel(requested)
        if requested_label == PaperDecisionActionLabel.BUY and not current_context_allows_realistic_entry_exit(evidence):
            return PaperDecisionActionLabel.WAIT
        return requested_label
    return classify_requested_action_from_memory_evidence(evidence)


def classify_paper_decision_status(evidence: Mapping[str, Any]) -> PaperDecisionStatusLabel:
    gate = classify_decision_gate(evidence)
    if gate == DecisionGateLabel.DECISION_ALLOWED:
        return PaperDecisionStatusLabel.PAPER_DECISION_PROPOSED
    if gate == DecisionGateLabel.DECISION_AUDIT_ONLY:
        return PaperDecisionStatusLabel.PAPER_DECISION_AUDIT_ONLY
    return PaperDecisionStatusLabel.PAPER_DECISION_BLOCKED


def paper_decision_can_be_recorded(evidence: Mapping[str, Any]) -> bool:
    return bool(evidence.get("token_id"))


def paper_decision_can_open_position_later(decision_row_or_payload: Mapping[str, Any]) -> bool:
    return (
        decision_row_or_payload.get("final_action_label") == PaperDecisionActionLabel.BUY.value
        and decision_row_or_payload.get("paper_decision_status_label") == PaperDecisionStatusLabel.PAPER_DECISION_PROPOSED.value
        and decision_row_or_payload.get("decision_gate_label") == DecisionGateLabel.DECISION_ALLOWED.value
    )

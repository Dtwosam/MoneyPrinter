"""Deterministic paper decision gates."""

from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.memory_retrieval.contracts import MemoryEvidenceLabel, RetrievalResultLabel
from printer_v1.paper_decision.contracts import (
    DecisionGateLabel,
    MemoryEvidenceGateLabel,
    PaperDecisionReasonLabel,
)


def classify_memory_evidence_gate(evidence: Mapping[str, Any]) -> MemoryEvidenceGateLabel:
    retrieval = evidence.get("memory_retrieval") or {}
    query = retrieval.get("retrieval_query") or {}
    result = query.get("retrieval_result_label")
    label = query.get("memory_evidence_label")
    if result == RetrievalResultLabel.RETRIEVAL_BLOCKED_NO_CLEAN_MEMORY.value:
        return MemoryEvidenceGateLabel.MEMORY_GATE_DIRTY_ONLY
    if result in {RetrievalResultLabel.RETRIEVAL_NO_MATCHES.value, None}:
        return MemoryEvidenceGateLabel.MEMORY_GATE_NO_MATCH
    if result == RetrievalResultLabel.RETRIEVAL_HAS_AUDIT_ONLY_MATCHES.value:
        return MemoryEvidenceGateLabel.MEMORY_GATE_BLOCKED
    if label == MemoryEvidenceLabel.MEMORY_EVIDENCE_STRONG.value:
        return MemoryEvidenceGateLabel.MEMORY_GATE_CLEAN_MATCH
    if label == MemoryEvidenceLabel.MEMORY_EVIDENCE_MIXED.value:
        return MemoryEvidenceGateLabel.MEMORY_GATE_MIXED_MATCH
    if label == MemoryEvidenceLabel.MEMORY_EVIDENCE_WEAK.value:
        return MemoryEvidenceGateLabel.MEMORY_GATE_WEAK_MATCH
    return MemoryEvidenceGateLabel.MEMORY_GATE_NO_MATCH


def context_has_value(context: Mapping[str, Any], values: set[str]) -> bool:
    return any(value in values for value in context.values())


def classify_decision_gate(evidence: Mapping[str, Any]) -> DecisionGateLabel:
    context = evidence.get("current_context") or {}
    if not evidence.get("has_clean_memory_comparison"):
        return DecisionGateLabel.DECISION_BLOCKED_NO_CLEAN_MEMORY
    if context_has_value(context, {SourceStatus.FAILED.value, DataQualityLabel.DIRTY_DATA.value, DataQualityLabel.MISSING_CRITICAL_DATA.value, DataQualityLabel.DO_NOT_TRAIN.value}):
        return DecisionGateLabel.DECISION_BLOCKED_DIRTY_CURRENT_CONTEXT
    if context_has_value(context, {"SAFETY_UNSAFE", "SAFETY_DO_NOT_USE_FOR_MEMORY", "RUG_RISK_CRITICAL"}):
        return DecisionGateLabel.DECISION_BLOCKED_UNSAFE_TOKEN
    if context_has_value(context, {"EXIT_UNREALISTIC", "REALISM_CONTEXT_BLOCKED", "REALISM_CONTEXT_DO_NOT_TRAIN"}):
        return DecisionGateLabel.DECISION_BLOCKED_UNREALISTIC_EXIT
    if context_has_value(context, {"EXIT_BLOCKED_BY_ROUTE", "ROUTE_NOT_AVAILABLE", "ROUTE_FAILED"}):
        return DecisionGateLabel.DECISION_BLOCKED_NO_ROUTE
    if context_has_value(context, {SourceStatus.STALE.value, DataQualityLabel.STALE_DATA.value}) or any(str(value).endswith("_STALE") for value in context.values()):
        return DecisionGateLabel.DECISION_BLOCKED_STALE_DATA
    if context_has_value(context, {SourceStatus.CONFLICTING.value, DataQualityLabel.CONFLICTING_DATA.value}) or any("CONFLICTING" in str(value) for value in context.values()):
        return DecisionGateLabel.DECISION_BLOCKED_CONFLICTING_DATA
    memory_gate = classify_memory_evidence_gate(evidence)
    if memory_gate in {MemoryEvidenceGateLabel.MEMORY_GATE_NO_MATCH, MemoryEvidenceGateLabel.MEMORY_GATE_DIRTY_ONLY, MemoryEvidenceGateLabel.MEMORY_GATE_BLOCKED}:
        return DecisionGateLabel.DECISION_BLOCKED_INSUFFICIENT_EVIDENCE
    if memory_gate == MemoryEvidenceGateLabel.MEMORY_GATE_WEAK_MATCH:
        return DecisionGateLabel.DECISION_BLOCKED_INSUFFICIENT_EVIDENCE
    if memory_gate == MemoryEvidenceGateLabel.MEMORY_GATE_MIXED_MATCH:
        return DecisionGateLabel.DECISION_AUDIT_ONLY
    return DecisionGateLabel.DECISION_ALLOWED


def build_decision_reasons(evidence: Mapping[str, Any]) -> list[str]:
    gate = classify_decision_gate(evidence)
    reasons: list[str] = []
    if gate == DecisionGateLabel.DECISION_ALLOWED:
        reasons.extend(
            [
                PaperDecisionReasonLabel.REASON_CLEAN_MEMORY_MATCH_SUPPORTS_ACTION.value,
                PaperDecisionReasonLabel.REASON_HISTORICAL_OUTCOMES_SUPPORT_ACTION.value,
            ]
        )
    if gate == DecisionGateLabel.DECISION_AUDIT_ONLY:
        reasons.append(PaperDecisionReasonLabel.REASON_AUDIT_ONLY.value)
    for reason in build_blocking_reasons(evidence):
        if reason not in reasons:
            reasons.append(reason)
    return reasons


def build_blocking_reasons(evidence: Mapping[str, Any]) -> list[str]:
    gate = classify_decision_gate(evidence)
    mapping = {
        DecisionGateLabel.DECISION_BLOCKED_NO_CLEAN_MEMORY: PaperDecisionReasonLabel.REASON_NOT_ENOUGH_CLEAN_MEMORY,
        DecisionGateLabel.DECISION_BLOCKED_DIRTY_CURRENT_CONTEXT: PaperDecisionReasonLabel.REASON_CONTEXT_CONFLICT,
        DecisionGateLabel.DECISION_BLOCKED_UNSAFE_TOKEN: PaperDecisionReasonLabel.REASON_SAFETY_CONTEXT_BLOCKS_ACTION,
        DecisionGateLabel.DECISION_BLOCKED_UNREALISTIC_EXIT: PaperDecisionReasonLabel.REASON_LIQUIDITY_EXIT_BLOCKS_ACTION,
        DecisionGateLabel.DECISION_BLOCKED_NO_ROUTE: PaperDecisionReasonLabel.REASON_LIQUIDITY_EXIT_BLOCKS_ACTION,
        DecisionGateLabel.DECISION_BLOCKED_STALE_DATA: PaperDecisionReasonLabel.REASON_DATA_STALE,
        DecisionGateLabel.DECISION_BLOCKED_CONFLICTING_DATA: PaperDecisionReasonLabel.REASON_DATA_CONFLICTING,
        DecisionGateLabel.DECISION_BLOCKED_INSUFFICIENT_EVIDENCE: PaperDecisionReasonLabel.REASON_NOT_ENOUGH_CLEAN_MEMORY,
        DecisionGateLabel.DECISION_AUDIT_ONLY: PaperDecisionReasonLabel.REASON_AUDIT_ONLY,
    }
    reason = mapping.get(gate)
    return [reason.value] if reason else []


def decision_gate_allows_paper_action(decision_gate_label: DecisionGateLabel | str) -> bool:
    return DecisionGateLabel(decision_gate_label) == DecisionGateLabel.DECISION_ALLOWED


def decision_requires_audit_only(decision_gate_label: DecisionGateLabel | str) -> bool:
    return DecisionGateLabel(decision_gate_label) == DecisionGateLabel.DECISION_AUDIT_ONLY

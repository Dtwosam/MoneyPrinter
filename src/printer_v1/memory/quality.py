"""Clean, dirty, and audit-only gates for Printer V1 memory."""

from typing import Any, Mapping, Sequence

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.memory.contracts import EpisodeOutcomeLabel, MemoryQualityLabel, MemoryRejectionReasonLabel


def evaluate_snapshot_coverage_gate(snapshots: Sequence[Mapping[str, Any]], expected_min_count: int = 2) -> list[MemoryRejectionReasonLabel]:
    if len(snapshots) < expected_min_count:
        return [MemoryRejectionReasonLabel.REJECT_MISSING_SNAPSHOTS]
    missing_critical = [
        row for row in snapshots
        if row.get("price_usd") is None or row.get("liquidity_usd") is None
    ]
    if missing_critical:
        return [MemoryRejectionReasonLabel.REJECT_MISSING_CRITICAL_FIELDS]
    return []


def evaluate_source_quality_gate(records: Sequence[Mapping[str, Any]]) -> list[MemoryRejectionReasonLabel]:
    reasons: list[MemoryRejectionReasonLabel] = []
    for row in records:
        source_status = SourceStatus(row.get("source_status") or SourceStatus.COMPLETE)
        data_quality = DataQualityLabel(row.get("data_quality_label") or DataQualityLabel.CLEAN_DATA)
        if source_status == SourceStatus.STALE or data_quality == DataQualityLabel.STALE_DATA:
            reasons.append(MemoryRejectionReasonLabel.REJECT_STALE_SOURCE_DATA)
        if source_status == SourceStatus.CONFLICTING or data_quality == DataQualityLabel.CONFLICTING_DATA:
            reasons.append(MemoryRejectionReasonLabel.REJECT_CONFLICTING_DATA)
        if data_quality in {DataQualityLabel.DIRTY_DATA, DataQualityLabel.MISSING_CRITICAL_DATA, DataQualityLabel.DO_NOT_TRAIN}:
            reasons.append(MemoryRejectionReasonLabel.REJECT_MISSING_CRITICAL_FIELDS)
    return list(dict.fromkeys(reasons))


def evaluate_context_quality_gate(context: Mapping[str, Any]) -> list[MemoryRejectionReasonLabel]:
    reasons: list[MemoryRejectionReasonLabel] = []
    if context.get("safety_status_label") in {"SAFETY_UNSAFE", "SAFETY_DO_NOT_USE_FOR_MEMORY"}:
        reasons.append(MemoryRejectionReasonLabel.REJECT_UNSAFE_TOKEN)
    if context.get("safety_payload_quality_label") in {"SAFETY_CONTEXT_STALE", "SAFETY_CONTEXT_CONFLICTING", "SAFETY_CONTEXT_DO_NOT_USE_FOR_MEMORY"}:
        reasons.append(MemoryRejectionReasonLabel.REJECT_DIRTY_SAFETY_CONTEXT)
    if context.get("realism_gate_label") in {"REALISM_CONTEXT_BLOCKED", "REALISM_CONTEXT_DO_NOT_TRAIN"}:
        reasons.append(MemoryRejectionReasonLabel.REJECT_DIRTY_LIQUIDITY_CONTEXT)
    if context.get("flow_memory_gate_label") == "FLOW_CONTEXT_DO_NOT_TRAIN":
        reasons.append(MemoryRejectionReasonLabel.REJECT_DIRTY_FLOW_CONTEXT)
    if context.get("chart_memory_gate_label") == "CHART_CONTEXT_DO_NOT_TRAIN":
        reasons.append(MemoryRejectionReasonLabel.REJECT_DIRTY_CHART_CONTEXT)
    if context.get("market_payload_quality_label") in {"MARKET_CONTEXT_STALE", "MARKET_CONTEXT_CONFLICTING", "MARKET_CONTEXT_DO_NOT_USE_FOR_MEMORY"}:
        reasons.append(MemoryRejectionReasonLabel.REJECT_DIRTY_MARKET_CONTEXT)
    if context.get("chain_heat_payload_quality_label") in {"CHAIN_HEAT_CONTEXT_STALE", "CHAIN_HEAT_CONTEXT_CONFLICTING", "CHAIN_HEAT_CONTEXT_DO_NOT_USE_FOR_MEMORY"}:
        reasons.append(MemoryRejectionReasonLabel.REJECT_DIRTY_CHAIN_HEAT_CONTEXT)
    return reasons


def evaluate_realism_gate(outcome_label: str | EpisodeOutcomeLabel, realism_context: Mapping[str, Any]) -> list[MemoryRejectionReasonLabel]:
    outcome = EpisodeOutcomeLabel(outcome_label)
    if outcome == EpisodeOutcomeLabel.REALISTIC_PAPER_PROFIT and not (
        realism_context.get("entry_realism_label") == "ENTRY_REALISTIC"
        and realism_context.get("exit_realism_label") == "EXIT_REALISTIC"
    ):
        return [MemoryRejectionReasonLabel.REJECT_UNREALISTIC_EXIT]
    if outcome == EpisodeOutcomeLabel.UNREALISTIC_PROFIT:
        return [MemoryRejectionReasonLabel.REJECT_UNREALISTIC_EXIT]
    return []


def build_rejection_reasons(*reason_groups: Sequence[MemoryRejectionReasonLabel]) -> list[str]:
    reasons: list[str] = []
    for group in reason_groups:
        for reason in group:
            value = MemoryRejectionReasonLabel(reason).value
            if value not in reasons:
                reasons.append(value)
    return reasons


def classify_memory_quality(
    *,
    outcome_label: str | EpisodeOutcomeLabel,
    rejection_reasons: Sequence[str],
    coverage_is_complete: bool = True,
) -> MemoryQualityLabel:
    outcome = EpisodeOutcomeLabel(outcome_label)
    reasons = set(rejection_reasons)
    if not coverage_is_complete or MemoryRejectionReasonLabel.REJECT_MISSING_SNAPSHOTS.value in reasons:
        return MemoryQualityLabel.DIRTY_MEMORY
    if MemoryRejectionReasonLabel.REJECT_5M_ONLY_WINDOW.value in reasons:
        return MemoryQualityLabel.DO_NOT_TRAIN_MEMORY
    if outcome == EpisodeOutcomeLabel.OUTCOME_UNKNOWN:
        return MemoryQualityLabel.AUDIT_ONLY_MEMORY
    if MemoryRejectionReasonLabel.REJECT_UNREALISTIC_EXIT.value in reasons:
        return MemoryQualityLabel.AUDIT_ONLY_MEMORY
    if reasons:
        if any(reason in reasons for reason in {
            MemoryRejectionReasonLabel.REJECT_CONFLICTING_DATA.value,
            MemoryRejectionReasonLabel.REJECT_STALE_SOURCE_DATA.value,
        }):
            return MemoryQualityLabel.AUDIT_ONLY_MEMORY
        return MemoryQualityLabel.DIRTY_MEMORY
    return MemoryQualityLabel.CLEAN_MEMORY


def memory_can_train_decisions(memory_quality_label: str | MemoryQualityLabel) -> bool:
    return MemoryQualityLabel(memory_quality_label) == MemoryQualityLabel.CLEAN_MEMORY

"""Controlled governed fixture evidence fill path.

This module bridges already-recorded source-governed fixture execution into the
existing guarded safety and paper quote evidence insert helpers. It does not
collect live data, build memory, run retrieval, or alter paper trading state.
"""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from typing import Any, Mapping

from printer_v1.paper_quote.evidence import (
    ALLOWED_CALLER as QUOTE_ALLOWED_CALLER,
    PaperQuoteEvidenceInsertResult,
    insert_paper_quote_evidence,
    row_level_clean_eligible as quote_row_level_clean_eligible,
    validate_insert_guards as validate_quote_insert_guards,
)
from printer_v1.paper_quote.jupiter_fixture import (
    insert_jupiter_quote_fixture_evidence,
    normalize_jupiter_quote_fixture_result,
)
from printer_v1.safety.evidence import (
    ALLOWED_CALLER as SAFETY_ALLOWED_CALLER,
    SolanaSafetyEvidenceInsertResult,
    insert_solana_safety_evidence,
    row_level_clean_eligible as safety_row_level_clean_eligible,
    validate_insert_guards as validate_safety_insert_guards,
)
from printer_v1.safety.solana_rpc_fixture import (
    insert_solana_rpc_safety_evidence_from_source_response,
    normalize_solana_rpc_safety_fixture_payload,
)
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.governed_execution import (
    FIXTURE_FAILURE,
    FIXTURE_STALE,
    build_fixture_source_adapter,
    execute_source_request_with_governor,
)


SCHEDULER_BOUNDARY_LABEL = "SCHEDULER_BOUNDARY_PRESENT"
OPERATOR_APPROVAL_LABEL = "OPERATOR_APPROVED_MANUAL_PROOF"


@dataclass(frozen=True)
class ControlledEvidenceFillTarget:
    token_id: int
    snapshot_id: int
    pair_id: int | None = None
    memory_window_id: int | None = None
    evidence_window_id: int | None = None


@dataclass(frozen=True)
class ControlledEvidenceItemResult:
    evidence_type: str
    dry_run: bool
    inserted: bool
    evidence_id: int | None
    clean_eligible: bool
    audit_status: str
    rejection_reasons: tuple[str, ...]
    source_request_id: int | None
    source_response_id: int | None
    source_failure_id: int | None
    downstream_unlocks: dict[str, bool]


@dataclass(frozen=True)
class ControlledEvidenceFillResult:
    dry_run: bool
    safety_evidence_inserted: int
    quote_evidence_inserted: int
    clean_evidence_inserted: int
    audit_only_evidence_inserted: int
    rejected_or_failed: int
    item_results: tuple[ControlledEvidenceItemResult, ...]


def downstream_unlocks_false() -> dict[str, bool]:
    return {
        "clean_memory": False,
        "retrieval": False,
        "paper_decision": False,
        "buy": False,
        "paper_position": False,
        "paper_trade_event": False,
        "pnl": False,
        "lane7": False,
    }


def _source_fixture_kind(payload: Mapping[str, Any]) -> str:
    source_status = str(payload.get("source_status") or "").upper()
    freshness_label = str(payload.get("freshness_label") or "").upper()
    if source_status == "FAILED":
        return FIXTURE_FAILURE
    if source_status == "STALE" or freshness_label in {"QUOTE_STALE", "SAFETY_EVIDENCE_STALE"}:
        return FIXTURE_STALE
    return "fixture_success"


def _dry_run_item(
    *,
    evidence_type: str,
    evidence: Mapping[str, Any],
    rejection_reasons: tuple[str, ...],
    clean_eligible: bool,
) -> ControlledEvidenceItemResult:
    audit_status = "DRY_RUN_WOULD_INSERT_CLEAN_ELIGIBLE_EVIDENCE"
    if rejection_reasons:
        audit_status = "DRY_RUN_REJECTED_GUARD_FAILED"
    elif not clean_eligible:
        audit_status = "DRY_RUN_WOULD_INSERT_AUDIT_ONLY_EVIDENCE"
    return ControlledEvidenceItemResult(
        evidence_type=evidence_type,
        dry_run=True,
        inserted=False,
        evidence_id=None,
        clean_eligible=False,
        audit_status=audit_status,
        rejection_reasons=rejection_reasons,
        source_request_id=evidence.get("source_request_id"),
        source_response_id=evidence.get("source_response_id"),
        source_failure_id=evidence.get("source_failure_id"),
        downstream_unlocks=downstream_unlocks_false(),
    )


def _safety_dry_run(
    payload: Mapping[str, Any],
    target: ControlledEvidenceFillTarget,
) -> ControlledEvidenceItemResult:
    evidence = normalize_solana_rpc_safety_fixture_payload(
        payload,
        token_id=target.token_id,
        pair_id=target.pair_id,
        snapshot_id=target.snapshot_id,
        memory_window_id=target.memory_window_id,
        evidence_window_id=target.evidence_window_id,
        source_request_id=-1,
        source_response_id=-1,
    )
    rejection_reasons = validate_safety_insert_guards(
        evidence,
        scheduler_boundary_label=SCHEDULER_BOUNDARY_LABEL,
        operator_approval_label=OPERATOR_APPROVAL_LABEL,
        caller=SAFETY_ALLOWED_CALLER,
    )
    return _dry_run_item(
        evidence_type="solana_safety",
        evidence=evidence,
        rejection_reasons=rejection_reasons,
        clean_eligible=safety_row_level_clean_eligible(evidence),
    )


def _quote_dry_run(
    payload: Mapping[str, Any],
    target: ControlledEvidenceFillTarget,
    quote_direction: str,
) -> ControlledEvidenceItemResult:
    fixture_kind = _source_fixture_kind(payload)
    source_status = "COMPLETE"
    data_quality_label = str(payload.get("data_quality_label") or "CLEAN_DATA")
    source_failure_id = None
    source_response_id = -1
    if fixture_kind == FIXTURE_STALE:
        source_status = "STALE"
        data_quality_label = "STALE_DATA"
    if fixture_kind == FIXTURE_FAILURE:
        source_status = "FAILED"
        data_quality_label = "MISSING_CRITICAL_DATA"
        source_failure_id = -1
        source_response_id = None
    evidence = normalize_jupiter_quote_fixture_result(
        result=type(
            "FixtureResult",
            (),
            {
                "normalized_payload": payload,
                "received_at": payload.get("quote_captured_at") or "1970-01-01T00:00:00+00:00",
                "source_status": source_status,
                "data_quality_label": data_quality_label,
            },
        )(),
        quote_direction=quote_direction,
        token_id=target.token_id,
        pair_id=target.pair_id,
        snapshot_id=target.snapshot_id,
        memory_window_id=target.memory_window_id,
        evidence_window_id=target.evidence_window_id,
        source_request_id=-1,
        source_response_id=source_response_id,
        source_failure_id=source_failure_id,
    )
    rejection_reasons = validate_quote_insert_guards(
        evidence,
        scheduler_boundary_label=SCHEDULER_BOUNDARY_LABEL,
        operator_approval_label=OPERATOR_APPROVAL_LABEL,
        caller=QUOTE_ALLOWED_CALLER,
    )
    return _dry_run_item(
        evidence_type=f"paper_quote_{quote_direction.lower()}",
        evidence=evidence,
        rejection_reasons=rejection_reasons,
        clean_eligible=quote_row_level_clean_eligible(evidence),
    )


def _result_from_safety_insert(
    *,
    insert_result: SolanaSafetyEvidenceInsertResult,
    source_request_id: int | None,
    source_response_id: int | None,
    source_failure_id: int | None,
) -> ControlledEvidenceItemResult:
    return ControlledEvidenceItemResult(
        evidence_type="solana_safety",
        dry_run=False,
        inserted=insert_result.inserted,
        evidence_id=insert_result.evidence_id,
        clean_eligible=insert_result.clean_eligible,
        audit_status=insert_result.audit_status,
        rejection_reasons=insert_result.rejection_reasons,
        source_request_id=source_request_id,
        source_response_id=source_response_id,
        source_failure_id=source_failure_id,
        downstream_unlocks=insert_result.downstream_unlocks,
    )


def _result_from_quote_insert(
    *,
    insert_result: PaperQuoteEvidenceInsertResult,
    evidence_type: str,
    source_request_id: int | None,
    source_response_id: int | None,
    source_failure_id: int | None,
) -> ControlledEvidenceItemResult:
    return ControlledEvidenceItemResult(
        evidence_type=evidence_type,
        dry_run=False,
        inserted=insert_result.inserted,
        evidence_id=insert_result.evidence_id,
        clean_eligible=insert_result.clean_eligible,
        audit_status=insert_result.audit_status,
        rejection_reasons=insert_result.rejection_reasons,
        source_request_id=source_request_id,
        source_response_id=source_response_id,
        source_failure_id=source_failure_id,
        downstream_unlocks=insert_result.downstream_unlocks,
    )


def _execute_safety_fill(
    connection: sqlite3.Connection,
    payload: Mapping[str, Any],
    target: ControlledEvidenceFillTarget,
) -> ControlledEvidenceItemResult:
    request = build_governed_source_request(
        "solana_rpc",
        "mint_account_reference",
        request_key=f"safety-fixture-token-{target.token_id}-snapshot-{target.snapshot_id}",
        payload={"fixture_proof_only": True, "token_id": target.token_id},
    )
    governed = execute_source_request_with_governor(
        connection,
        request,
        build_fixture_source_adapter(
            "solana_rpc",
            fixture_kind=_source_fixture_kind(payload),
            fixture_payload=payload,
        ),
    )
    if governed.response_record is not None:
        insert_result = insert_solana_rpc_safety_evidence_from_source_response(
            connection,
            source_response_id=governed.response_record.id,
            token_id=target.token_id,
            pair_id=target.pair_id,
            snapshot_id=target.snapshot_id,
            memory_window_id=target.memory_window_id,
            evidence_window_id=target.evidence_window_id,
            scheduler_boundary_label=SCHEDULER_BOUNDARY_LABEL,
            operator_approval_label=OPERATOR_APPROVAL_LABEL,
            caller=SAFETY_ALLOWED_CALLER,
        )
    else:
        evidence = normalize_solana_rpc_safety_fixture_payload(
            payload,
            token_id=target.token_id,
            pair_id=target.pair_id,
            snapshot_id=target.snapshot_id,
            memory_window_id=target.memory_window_id,
            evidence_window_id=target.evidence_window_id,
            source_request_id=governed.request_record.id,
            source_failure_id=governed.failure_record.id if governed.failure_record else None,
        )
        evidence["source_status"] = "FAILED"
        evidence["data_quality_label"] = "MISSING_CRITICAL_DATA"
        insert_result = insert_solana_safety_evidence(
            connection,
            evidence,
            scheduler_boundary_label=SCHEDULER_BOUNDARY_LABEL,
            operator_approval_label=OPERATOR_APPROVAL_LABEL,
            caller=SAFETY_ALLOWED_CALLER,
        )
    return _result_from_safety_insert(
        insert_result=insert_result,
        source_request_id=governed.request_record.id,
        source_response_id=governed.response_record.id if governed.response_record else None,
        source_failure_id=governed.failure_record.id if governed.failure_record else None,
    )


def _execute_quote_fill(
    connection: sqlite3.Connection,
    payload: Mapping[str, Any],
    target: ControlledEvidenceFillTarget,
    quote_direction: str,
) -> ControlledEvidenceItemResult:
    request = build_governed_source_request(
        "jupiter_quote",
        "paper_quote_realism",
        request_key=f"quote-fixture-token-{target.token_id}-snapshot-{target.snapshot_id}-{quote_direction.lower()}",
        payload={
            "fixture_proof_only": True,
            "token_id": target.token_id,
            "quote_direction": quote_direction,
        },
    )
    governed = execute_source_request_with_governor(
        connection,
        request,
        build_fixture_source_adapter(
            "jupiter_quote",
            fixture_kind=_source_fixture_kind(payload),
            fixture_payload=payload,
        ),
    )
    insert_result = insert_jupiter_quote_fixture_evidence(
        connection,
        governed.normalized_result,
        request_record=governed.request_record,
        response_record=governed.response_record,
        failure_record=governed.failure_record,
        quote_direction=quote_direction,
        token_id=target.token_id,
        pair_id=target.pair_id,
        snapshot_id=target.snapshot_id,
        memory_window_id=target.memory_window_id,
        evidence_window_id=target.evidence_window_id,
        scheduler_boundary_label=SCHEDULER_BOUNDARY_LABEL,
        operator_approval_label=OPERATOR_APPROVAL_LABEL,
        caller=QUOTE_ALLOWED_CALLER,
    )
    return _result_from_quote_insert(
        insert_result=insert_result,
        evidence_type=f"paper_quote_{quote_direction.lower()}",
        source_request_id=governed.request_record.id,
        source_response_id=governed.response_record.id if governed.response_record else None,
        source_failure_id=governed.failure_record.id if governed.failure_record else None,
    )


def _summarize(
    *,
    dry_run: bool,
    item_results: list[ControlledEvidenceItemResult],
) -> ControlledEvidenceFillResult:
    safety_inserted = sum(
        1 for item in item_results if item.evidence_type == "solana_safety" and item.inserted
    )
    quote_inserted = sum(
        1 for item in item_results if item.evidence_type.startswith("paper_quote_") and item.inserted
    )
    clean_inserted = sum(1 for item in item_results if item.inserted and item.clean_eligible)
    audit_inserted = sum(
        1 for item in item_results if item.inserted and not item.clean_eligible
    )
    rejected_or_failed = sum(1 for item in item_results if not item.inserted)
    return ControlledEvidenceFillResult(
        dry_run=dry_run,
        safety_evidence_inserted=safety_inserted,
        quote_evidence_inserted=quote_inserted,
        clean_evidence_inserted=clean_inserted,
        audit_only_evidence_inserted=audit_inserted,
        rejected_or_failed=rejected_or_failed,
        item_results=tuple(item_results),
    )


def fill_controlled_governed_evidence(
    connection: sqlite3.Connection,
    *,
    target: ControlledEvidenceFillTarget,
    safety_payload: Mapping[str, Any] | None = None,
    entry_quote_payload: Mapping[str, Any] | None = None,
    exit_quote_payload: Mapping[str, Any] | None = None,
    dry_run: bool = False,
) -> ControlledEvidenceFillResult:
    """Fill safety and quote fixture evidence through governed trace helpers."""

    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("controlled evidence fill requires a caller-provided SQLite connection")

    item_results: list[ControlledEvidenceItemResult] = []
    if safety_payload is not None:
        item_results.append(
            _safety_dry_run(safety_payload, target)
            if dry_run
            else _execute_safety_fill(connection, safety_payload, target)
        )
    if entry_quote_payload is not None:
        item_results.append(
            _quote_dry_run(entry_quote_payload, target, "ENTRY")
            if dry_run
            else _execute_quote_fill(connection, entry_quote_payload, target, "ENTRY")
        )
    if exit_quote_payload is not None:
        item_results.append(
            _quote_dry_run(exit_quote_payload, target, "EXIT")
            if dry_run
            else _execute_quote_fill(connection, exit_quote_payload, target, "EXIT")
        )
    return _summarize(dry_run=dry_run, item_results=item_results)

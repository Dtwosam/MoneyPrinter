"""Isolated paper quote evidence insert helper.

This module stores caller-provided fixture evidence only. It never calls
Jupiter, opens the persistent operator DB by default, schedules jobs, or unlocks
memory/retrieval/paper trading behavior.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any


INSERT_FIELDS = (
    "token_id",
    "pair_id",
    "snapshot_id",
    "memory_window_id",
    "evidence_window_id",
    "quote_evidence_role",
    "quote_direction",
    "quote_purpose",
    "source_name",
    "source_status",
    "data_quality_label",
    "target_status",
    "evidence_captured_at",
    "freshness_label",
    "quote_context_label",
    "entry_realism_label",
    "exit_realism_label",
    "route_available_label",
    "slippage_context_label",
    "price_impact_context_label",
    "liquidity_context_label",
    "quote_failure_label",
    "source_request_id",
    "source_response_id",
    "source_failure_id",
    "paper_only_context",
)

REQUIRED_INPUT_FIELDS = (
    "token_id",
    "snapshot_id",
    "quote_evidence_role",
    "quote_direction",
    "quote_purpose",
    "source_name",
    "source_status",
    "data_quality_label",
    "target_status",
    "evidence_captured_at",
    "freshness_label",
    "quote_context_label",
    "entry_realism_label",
    "exit_realism_label",
    "route_available_label",
    "slippage_context_label",
    "price_impact_context_label",
    "source_request_id",
    "paper_only_context",
)

FORBIDDEN_FIELD_FRAGMENTS = (
    "score",
    "rank",
    "confidence",
    "weight",
    "weighted",
    "buy_signal",
    "sell_signal",
    "trade_signal",
    "wallet",
    "private_key",
    "signature",
    "signer",
    "live_execution",
    "buy_unlock",
    "pnl",
    "retrieval_ready",
)

FORBIDDEN_DIRECT_CALLERS = {
    "memory_engine",
    "retrieval_engine",
    "paper_decision_engine",
    "paper_position_engine",
    "pnl_engine",
}

ALLOWED_CALLER = "source_governor_scheduler_operator_flow"

CLEAN_SOURCE_STATUSES = {"COMPLETE", "PARTIAL"}
CLEAN_DATA_QUALITY_LABELS = {"CLEAN_DATA", "ACCEPTABLE_PARTIAL_DATA"}
CLEAN_FRESHNESS_LABELS = {"QUOTE_FRESH", "QUOTE_ACCEPTABLE"}
CLEAN_QUOTE_CONTEXT_LABELS = {"QUOTE_ROUTE_AVAILABLE"}
CLEAN_ROUTE_LABELS = {"ROUTE_AVAILABLE"}
CLEAN_ENTRY_LABELS = {"ENTRY_REALISTIC", "ENTRY_ROUTE_AVAILABLE"}
CLEAN_EXIT_LABELS = {"EXIT_REALISTIC", "EXIT_ROUTE_AVAILABLE"}


@dataclass(frozen=True)
class PaperQuoteEvidenceInsertResult:
    inserted: bool
    evidence_id: int | None
    audit_status: str
    clean_eligible: bool
    rejection_reasons: tuple[str, ...]
    source_trace_status: str
    scheduler_boundary_status: str
    downstream_unlocks: dict[str, bool]


@contextmanager
def connect(db_or_connection: str | Path | sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    if isinstance(db_or_connection, sqlite3.Connection):
        db_or_connection.row_factory = sqlite3.Row
        yield db_or_connection
        return

    connection = sqlite3.connect(Path(db_or_connection))
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


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


def has_source_trace(evidence: Mapping[str, Any]) -> bool:
    return evidence.get("source_request_id") is not None and (
        evidence.get("source_response_id") is not None
        or evidence.get("source_failure_id") is not None
    )


def source_trace_status(evidence: Mapping[str, Any]) -> str:
    if not has_source_trace(evidence):
        return "SOURCE_TRACE_MISSING"
    if evidence.get("source_failure_id") is not None:
        return "SOURCE_TRACE_FAILED_VISIBLE"
    return "SOURCE_TRACE_PRESENT"


def scheduler_boundary_status(
    *,
    scheduler_boundary_label: str | None,
    operator_approval_label: str | None,
) -> str:
    if scheduler_boundary_label != "SCHEDULER_BOUNDARY_PRESENT":
        return "SCHEDULER_BOUNDARY_MISSING"
    if operator_approval_label != "OPERATOR_APPROVED_MANUAL_PROOF":
        return "OPERATOR_APPROVAL_MISSING"
    return "SCHEDULER_OPERATOR_BOUNDARY_PRESENT"


def forbidden_fields_present(evidence: Mapping[str, Any]) -> tuple[str, ...]:
    keys = " ".join(str(key).lower() for key in evidence.keys())
    return tuple(fragment for fragment in FORBIDDEN_FIELD_FRAGMENTS if fragment in keys)


def validate_insert_guards(
    evidence: Mapping[str, Any],
    *,
    scheduler_boundary_label: str | None,
    operator_approval_label: str | None,
    caller: str = ALLOWED_CALLER,
) -> tuple[str, ...]:
    reasons: list[str] = []

    for field in REQUIRED_INPUT_FIELDS:
        if evidence.get(field) is None:
            reasons.append(f"MISSING_{field.upper()}")

    if not has_source_trace(evidence):
        reasons.append("SOURCE_TRACE_MISSING")
    if evidence.get("paper_only_context") is not True:
        reasons.append("PAPER_ONLY_CONTEXT_REQUIRED")
    if evidence.get("quote_purpose") != "PAPER_REALISM_ONLY":
        reasons.append("PAPER_REALISM_ONLY_REQUIRED")
    if evidence.get("target_status") != "TARGET_MATCH":
        reasons.append("TARGET_MISMATCH")

    boundary_status = scheduler_boundary_status(
        scheduler_boundary_label=scheduler_boundary_label,
        operator_approval_label=operator_approval_label,
    )
    if boundary_status == "SCHEDULER_BOUNDARY_MISSING":
        reasons.append("SCHEDULER_BOUNDARY_MISSING")
    if boundary_status == "OPERATOR_APPROVAL_MISSING":
        reasons.append("OPERATOR_APPROVAL_MISSING")

    if caller in FORBIDDEN_DIRECT_CALLERS:
        reasons.append("DIRECT_CALLER_FORBIDDEN")
    if caller != ALLOWED_CALLER:
        reasons.append("SOURCE_GOVERNOR_SCHEDULER_BOUNDARY_REQUIRED")
    if forbidden_fields_present(evidence):
        reasons.append("FORBIDDEN_FIELDS_PRESENT")
    if (
        evidence.get("source_status") != "FAILED"
        and evidence.get("data_quality_label")
        in {"DIRTY_DATA", "MISSING_CRITICAL_DATA", "CONFLICTING_DATA", "DO_NOT_TRAIN"}
    ):
        reasons.append("DATA_QUALITY_NOT_INSERTABLE")

    return tuple(dict.fromkeys(reasons))


def row_level_clean_eligible(evidence: Mapping[str, Any]) -> bool:
    direction = evidence.get("quote_direction")
    realism_label = (
        evidence.get("entry_realism_label")
        if direction == "ENTRY"
        else evidence.get("exit_realism_label")
    )
    direction_clean = (
        direction == "ENTRY"
        and realism_label in CLEAN_ENTRY_LABELS
        or direction == "EXIT"
        and realism_label in CLEAN_EXIT_LABELS
    )
    return (
        evidence.get("source_status") in CLEAN_SOURCE_STATUSES
        and evidence.get("data_quality_label") in CLEAN_DATA_QUALITY_LABELS
        and evidence.get("freshness_label") in CLEAN_FRESHNESS_LABELS
        and evidence.get("target_status") == "TARGET_MATCH"
        and evidence.get("quote_context_label") in CLEAN_QUOTE_CONTEXT_LABELS
        and evidence.get("route_available_label") in CLEAN_ROUTE_LABELS
        and direction_clean
    )


def insert_paper_quote_evidence(
    db_or_connection: str | Path | sqlite3.Connection,
    evidence: Mapping[str, Any],
    *,
    scheduler_boundary_label: str | None,
    operator_approval_label: str | None,
    caller: str = ALLOWED_CALLER,
) -> PaperQuoteEvidenceInsertResult:
    """Insert one paper quote evidence row into a caller-provided DB only."""

    normalized = dict(evidence)
    rejection_reasons = validate_insert_guards(
        normalized,
        scheduler_boundary_label=scheduler_boundary_label,
        operator_approval_label=operator_approval_label,
        caller=caller,
    )
    boundary_status = scheduler_boundary_status(
        scheduler_boundary_label=scheduler_boundary_label,
        operator_approval_label=operator_approval_label,
    )
    if rejection_reasons:
        return PaperQuoteEvidenceInsertResult(
            inserted=False,
            evidence_id=None,
            audit_status="REJECTED_GUARD_FAILED",
            clean_eligible=False,
            rejection_reasons=rejection_reasons,
            source_trace_status=source_trace_status(normalized),
            scheduler_boundary_status=boundary_status,
            downstream_unlocks=downstream_unlocks_false(),
        )

    clean_eligible = row_level_clean_eligible(normalized)
    audit_status = (
        "INSERTED_CLEAN_ELIGIBLE_EVIDENCE"
        if clean_eligible
        else "INSERTED_AUDIT_ONLY_EVIDENCE"
    )

    with connect(db_or_connection) as connection:
        cursor = connection.execute(
            f"""
            INSERT INTO printer_paper_quote_evidence (
                {", ".join(INSERT_FIELDS)}
            ) VALUES ({", ".join("?" for _ in INSERT_FIELDS)})
            """,
            tuple(normalized.get(field) for field in INSERT_FIELDS),
        )
        evidence_id = int(cursor.lastrowid)

    return PaperQuoteEvidenceInsertResult(
        inserted=True,
        evidence_id=evidence_id,
        audit_status=audit_status,
        clean_eligible=clean_eligible,
        rejection_reasons=(),
        source_trace_status=source_trace_status(normalized),
        scheduler_boundary_status=boundary_status,
        downstream_unlocks=downstream_unlocks_false(),
    )

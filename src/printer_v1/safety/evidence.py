"""Isolated Solana safety evidence insert helper.

This module is intentionally low level: callers must provide a SQLite
connection or explicit database path. It does not know the persistent operator
DB path, call sources, enqueue scheduler jobs, or unlock downstream behavior.
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
    "safety_evidence_role",
    "source_name",
    "source_status",
    "data_quality_label",
    "target_status",
    "evidence_captured_at",
    "freshness_label",
    "mint_authority_status",
    "freeze_authority_status",
    "metadata_mutability_status",
    "supply_sanity_label",
    "holder_concentration_label",
    "liquidity_lock_or_burn_label",
    "known_risk_flag_label",
    "token_program_label",
    "safety_context_label",
    "source_request_id",
    "source_response_id",
    "source_failure_id",
    "paper_only_context",
)

REQUIRED_INPUT_FIELDS = (
    "token_id",
    "snapshot_id",
    "safety_evidence_role",
    "source_name",
    "source_status",
    "data_quality_label",
    "target_status",
    "evidence_captured_at",
    "freshness_label",
    "mint_authority_status",
    "freeze_authority_status",
    "metadata_mutability_status",
    "supply_sanity_label",
    "holder_concentration_label",
    "liquidity_lock_or_burn_label",
    "known_risk_flag_label",
    "token_program_label",
    "safety_context_label",
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
    "private" + "_key",
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

SUMMARY_TO_STORAGE_SAFETY_LABEL = {
    "SAFETY_CLEAR": "SAFETY_CLEAN",
    "SAFETY_CAUTION": "SAFETY_CAUTION",
    "SAFETY_BLOCKED": "SAFETY_UNSAFE",
    "SAFETY_UNKNOWN": "SAFETY_UNKNOWN",
}

CLEAN_SOURCE_STATUSES = {"COMPLETE", "PARTIAL"}
CLEAN_DATA_QUALITY_LABELS = {"CLEAN_DATA", "ACCEPTABLE_PARTIAL_DATA"}
CLEAN_FRESHNESS_LABELS = {"SAFETY_EVIDENCE_FRESH", "SAFETY_EVIDENCE_ACCEPTABLE"}
CLEAN_SAFETY_LABELS = {"SAFETY_CLEAN"}


@dataclass(frozen=True)
class SolanaSafetyEvidenceInsertResult:
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


def normalize_safety_context_label(value: object) -> object:
    if isinstance(value, str):
        return SUMMARY_TO_STORAGE_SAFETY_LABEL.get(value, value)
    return value


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
    normalized = dict(evidence)
    normalized["safety_context_label"] = normalize_safety_context_label(
        normalized.get("safety_context_label")
    )

    for field in REQUIRED_INPUT_FIELDS:
        if normalized.get(field) is None:
            reasons.append(f"MISSING_{field.upper()}")

    if not has_source_trace(normalized):
        reasons.append("SOURCE_TRACE_MISSING")
    if normalized.get("paper_only_context") is not True:
        reasons.append("PAPER_ONLY_CONTEXT_REQUIRED")
    boundary_status = scheduler_boundary_status(
        scheduler_boundary_label=scheduler_boundary_label,
        operator_approval_label=operator_approval_label,
    )
    if boundary_status == "SCHEDULER_BOUNDARY_MISSING":
        reasons.append("SCHEDULER_BOUNDARY_MISSING")
    if boundary_status == "OPERATOR_APPROVAL_MISSING":
        reasons.append("OPERATOR_APPROVAL_MISSING")
    if normalized.get("target_status") != "TARGET_MATCH":
        reasons.append("TARGET_MISMATCH")
    if caller in FORBIDDEN_DIRECT_CALLERS:
        reasons.append("DIRECT_CALLER_FORBIDDEN")
    if caller != ALLOWED_CALLER:
        reasons.append("SOURCE_GOVERNOR_SCHEDULER_BOUNDARY_REQUIRED")
    if forbidden_fields_present(normalized):
        reasons.append("FORBIDDEN_FIELDS_PRESENT")
    if (
        normalized.get("source_status") != "FAILED"
        and normalized.get("data_quality_label")
        in {"DIRTY_DATA", "MISSING_CRITICAL_DATA", "CONFLICTING_DATA", "DO_NOT_TRAIN"}
    ):
        reasons.append("DATA_QUALITY_NOT_INSERTABLE")
    return tuple(dict.fromkeys(reasons))


def row_level_clean_eligible(evidence: Mapping[str, Any]) -> bool:
    return (
        evidence.get("source_status") in CLEAN_SOURCE_STATUSES
        and evidence.get("data_quality_label") in CLEAN_DATA_QUALITY_LABELS
        and evidence.get("freshness_label") in CLEAN_FRESHNESS_LABELS
        and evidence.get("target_status") == "TARGET_MATCH"
        and evidence.get("safety_context_label") in CLEAN_SAFETY_LABELS
    )


def insert_solana_safety_evidence(
    db_or_connection: str | Path | sqlite3.Connection,
    evidence: Mapping[str, Any],
    *,
    scheduler_boundary_label: str | None,
    operator_approval_label: str | None,
    caller: str = ALLOWED_CALLER,
) -> SolanaSafetyEvidenceInsertResult:
    """Insert one Solana safety evidence row into a caller-provided DB only."""

    normalized = dict(evidence)
    normalized["safety_context_label"] = normalize_safety_context_label(
        normalized.get("safety_context_label")
    )
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
        return SolanaSafetyEvidenceInsertResult(
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
    audit_status = "INSERTED_CLEAN_ELIGIBLE_EVIDENCE" if clean_eligible else "INSERTED_AUDIT_ONLY_EVIDENCE"

    with connect(db_or_connection) as connection:
        cursor = connection.execute(
            f"""
            INSERT INTO printer_solana_safety_evidence (
                {", ".join(INSERT_FIELDS)}
            ) VALUES ({", ".join("?" for _ in INSERT_FIELDS)})
            """,
            tuple(normalized.get(field) for field in INSERT_FIELDS),
        )
        evidence_id = int(cursor.lastrowid)

    return SolanaSafetyEvidenceInsertResult(
        inserted=True,
        evidence_id=evidence_id,
        audit_status=audit_status,
        clean_eligible=clean_eligible,
        rejection_reasons=(),
        source_trace_status=source_trace_status(normalized),
        scheduler_boundary_status=boundary_status,
        downstream_unlocks=downstream_unlocks_false(),
    )

"""SQLite-backed paper decision recorder."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.paper_decision.classifier import (
    classify_final_paper_action,
    classify_paper_decision_status,
    classify_requested_action_from_memory_evidence,
)
from printer_v1.paper_decision.contracts import (
    DecisionGateLabel,
    MemoryEvidenceGateLabel,
    PaperDecisionActionLabel,
    PaperDecisionStatusLabel,
)
from printer_v1.paper_decision.evidence import collect_paper_decision_evidence
from printer_v1.paper_decision.gates import (
    build_blocking_reasons,
    build_decision_reasons,
    classify_decision_gate,
    classify_memory_evidence_gate,
)
from printer_v1.paper_decision.reports import build_paper_decision_report
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import enqueue_job


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def build_decision_payload(
    evidence: Mapping[str, Any],
    requested_action_label: PaperDecisionActionLabel | str | None = None,
    decided_at: datetime | None = None,
) -> dict[str, Any]:
    current_time = decided_at or utc_now()
    enriched = dict(evidence)
    if requested_action_label is not None:
        enriched["requested_action_label"] = PaperDecisionActionLabel(requested_action_label).value
    requested = enriched.get("requested_action_label") or classify_requested_action_from_memory_evidence(enriched).value
    gate = classify_decision_gate(enriched)
    memory_gate = classify_memory_evidence_gate(enriched)
    status = classify_paper_decision_status(enriched)
    final_action = classify_final_paper_action(enriched)
    retrieval = enriched.get("memory_retrieval") or {}
    query = retrieval.get("retrieval_query") or {}
    clean_matches = retrieval.get("clean_matches") or []
    payload = {
        "token_id": enriched.get("token_id"),
        "pair_id": enriched.get("pair_id"),
        "token_mint": (enriched.get("current_context") or {}).get("token_mint"),
        "pair_address": (enriched.get("current_context") or {}).get("pair_address"),
        "decided_at": current_time.isoformat(),
        "requested_action_label": PaperDecisionActionLabel(requested).value,
        "final_action_label": final_action.value,
        "decision_gate_label": gate.value,
        "memory_evidence_gate_label": memory_gate.value,
        "paper_decision_status_label": status.value,
        "retrieval_query_id": query.get("id"),
        "matched_episode_ids": [match.get("episode_id") for match in clean_matches],
        "supporting_memory_match_ids": [match.get("id") for match in clean_matches],
        "decision_reasons": build_decision_reasons(enriched),
        "blocking_reasons": build_blocking_reasons(enriched),
        "current_context": enriched.get("current_context") or {},
        "memory_evidence_summary": {
            "retrieval_result_label": query.get("retrieval_result_label"),
            "memory_evidence_label": query.get("memory_evidence_label"),
            "clean_match_count": len(clean_matches),
        },
        "expires_at": (current_time + timedelta(minutes=15)).isoformat(),
        "evidence": enriched,
    }
    payload["decision_report"] = build_paper_decision_report(payload)
    return payload


def record_paper_decision(db_path_or_conn: str | Path | sqlite3.Connection, decision_payload: Mapping[str, Any]) -> int:
    final_action = PaperDecisionActionLabel(decision_payload["final_action_label"]).value
    status = PaperDecisionStatusLabel(decision_payload["paper_decision_status_label"]).value
    with connect(db_path_or_conn) as connection:
        duplicate = connection.execute(
            """
            SELECT id
            FROM printer_paper_decisions
            WHERE token_id = ?
              AND COALESCE(pair_id, -1) = COALESCE(?, -1)
              AND decided_at = ?
            LIMIT 1
            """,
            (decision_payload.get("token_id"), decision_payload.get("pair_id"), decision_payload.get("decided_at")),
        ).fetchone()
        if duplicate:
            return int(duplicate["id"])
        cursor = connection.execute(
            """
            INSERT INTO printer_paper_decisions (
                token_id, pair_id, token_mint, pair_address, decided_at,
                requested_action_label, final_action_label, decision_gate_label,
                memory_evidence_gate_label, paper_decision_status_label,
                retrieval_query_id, matched_episode_ids_json,
                supporting_memory_match_ids_json, decision_reasons_json,
                blocking_reasons_json, current_context_json,
                memory_evidence_summary_json, decision_report_json, expires_at,
                decision_action, decision_status, source_status, data_quality_label
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_payload.get("token_id"),
                decision_payload.get("pair_id"),
                decision_payload.get("token_mint"),
                decision_payload.get("pair_address"),
                decision_payload.get("decided_at"),
                PaperDecisionActionLabel(decision_payload["requested_action_label"]).value,
                final_action,
                DecisionGateLabel(decision_payload["decision_gate_label"]).value,
                MemoryEvidenceGateLabel(decision_payload["memory_evidence_gate_label"]).value,
                status,
                decision_payload.get("retrieval_query_id"),
                json.dumps(decision_payload.get("matched_episode_ids", []), sort_keys=True),
                json.dumps(decision_payload.get("supporting_memory_match_ids", []), sort_keys=True),
                json.dumps(decision_payload.get("decision_reasons", []), sort_keys=True),
                json.dumps(decision_payload.get("blocking_reasons", []), sort_keys=True),
                json.dumps(decision_payload.get("current_context", {}), sort_keys=True),
                json.dumps(decision_payload.get("memory_evidence_summary", {}), sort_keys=True),
                json.dumps(decision_payload.get("decision_report", {}), sort_keys=True),
                decision_payload.get("expires_at"),
                final_action,
                status,
                SourceStatus.COMPLETE.value,
                DataQualityLabel.CLEAN_DATA.value,
            ),
        )
        return int(cursor.lastrowid)


def record_paper_decision_audit(
    db_path_or_conn: str | Path | sqlite3.Connection,
    paper_decision_id: int,
    audit_payload: Mapping[str, Any],
) -> int:
    with connect(db_path_or_conn) as connection:
        cursor = connection.execute(
            """
            INSERT INTO printer_paper_decision_audits (
                paper_decision_id, token_id, pair_id, audit_label, audit_payload_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                paper_decision_id,
                audit_payload.get("token_id"),
                audit_payload.get("pair_id"),
                audit_payload.get("audit_label", "PAPER_DECISION_RECORDED"),
                json.dumps(dict(audit_payload), sort_keys=True),
            ),
        )
        return int(cursor.lastrowid)


def build_and_record_paper_decision(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    requested_action_label: PaperDecisionActionLabel | str | None = None,
    target_time: str | None = None,
) -> tuple[int, dict[str, Any]]:
    evidence = collect_paper_decision_evidence(db_path_or_conn, token_id, pair_id, target_time)
    payload = build_decision_payload(evidence, requested_action_label)
    decision_id = record_paper_decision(db_path_or_conn, payload)
    record_paper_decision_audit(
        db_path_or_conn,
        decision_id,
        {
            "token_id": token_id,
            "pair_id": pair_id,
            "audit_label": payload["paper_decision_status_label"],
            "decision_gate_label": payload["decision_gate_label"],
            "final_action_label": payload["final_action_label"],
        },
    )
    return decision_id, payload


def get_latest_paper_decision(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int | None = None,
    pair_id: int | None = None,
) -> sqlite3.Row | None:
    clauses: list[str] = []
    params: list[Any] = []
    if token_id is not None:
        clauses.append("token_id = ?")
        params.append(token_id)
    if pair_id is not None:
        clauses.append("COALESCE(pair_id, -1) = COALESCE(?, -1)")
        params.append(pair_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect(db_path_or_conn) as connection:
        return connection.execute(
            f"""
            SELECT *
            FROM printer_paper_decisions
            {where}
            ORDER BY decided_at DESC, id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()


def enqueue_paper_decision_job(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    scheduled_for: datetime,
    reason: str | None = None,
) -> tuple[LockResult, int | None]:
    suffix = reason or "scheduled"
    return enqueue_job(
        db_path_or_conn,
        job_name=f"paper_decision_{token_id}_{pair_id or 0}_{suffix}",
        job_kind=JobKind.MEMORY_WINDOW_CLOSE,
        target_table="printer_paper_decisions",
        target_id=token_id,
        scheduled_for=scheduled_for,
    )

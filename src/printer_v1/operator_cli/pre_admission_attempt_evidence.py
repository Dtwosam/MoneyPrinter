"""Append-only categorical evidence for one pre-admission acquisition attempt.

This ledger is reporting/provenance state only.  It owns no Scheduler claim,
source request, candidate ranking, admission decision, or retry authority.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any, Mapping


class PreAdmissionAttemptEvidenceError(RuntimeError):
    """Fail-closed attempt-evidence persistence or reduction fault."""


def _canonical_payload(payload: Mapping[str, Any] | None) -> tuple[str, str]:
    encoded = json.dumps(
        dict(payload or {}), sort_keys=True, separators=(",", ":")
    )
    return encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def append_pre_admission_attempt_evidence(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    event_key: str,
    opportunity_ordinal: int,
    claim_ordinal: int,
    evidence_kind: str,
    observed_at: str,
    payload: Mapping[str, Any] | None = None,
    mint_identity: str | None = None,
    pair_identity: str | None = None,
    categorical_reason: str | None = None,
    source_request_id: int | None = None,
    source_response_id: int | None = None,
    source_failure_id: int | None = None,
) -> bool:
    """Append one deterministic fact; exact replay is idempotent.

    Returns True for a new row and False for an exact durable replay.  A reused
    event key with any differing fact fails closed.
    """
    payload_json, payload_hash = _canonical_payload(payload)
    values = (
        str(attempt_id),
        str(event_key),
        int(opportunity_ordinal),
        int(claim_ordinal),
        str(evidence_kind),
        None if mint_identity is None else str(mint_identity),
        None if pair_identity is None else str(pair_identity),
        None if categorical_reason is None else str(categorical_reason),
        source_request_id,
        source_response_id,
        source_failure_id,
        payload_json,
        payload_hash,
        str(observed_at),
        str(observed_at),
    )
    existing = connection.execute(
        """SELECT attempt_id,event_key,opportunity_ordinal,claim_ordinal,
                  evidence_kind,mint_identity,pair_identity,categorical_reason,
                  source_request_id,source_response_id,source_failure_id,
                  payload_json,payload_hash,observed_at,created_at
             FROM printer_pre_admission_attempt_evidence
            WHERE attempt_id=? AND event_key=?""",
        (values[0], values[1]),
    ).fetchone()
    if existing is not None:
        if tuple(existing) != values:
            raise PreAdmissionAttemptEvidenceError(
                "ATTEMPT_EVIDENCE_EVENT_KEY_CONFLICT"
            )
        return False
    connection.execute(
        """INSERT INTO printer_pre_admission_attempt_evidence(
               attempt_id,event_key,opportunity_ordinal,claim_ordinal,
               evidence_kind,mint_identity,pair_identity,categorical_reason,
               source_request_id,source_response_id,source_failure_id,
               payload_json,payload_hash,observed_at,created_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        values,
    )
    return True


def reduce_pre_admission_attempt_evidence(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
) -> dict[str, Any]:
    """Deterministically reduce all durable categorical facts for an attempt."""
    previous = connection.row_factory
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """SELECT * FROM printer_pre_admission_attempt_evidence
               WHERE attempt_id=?
               ORDER BY opportunity_ordinal,claim_ordinal,event_key""",
            (str(attempt_id),),
        ).fetchall()
    finally:
        connection.row_factory = previous
    observed_mints: set[str] = set()
    rejected_events: set[str] = set()
    rejection_reasons: dict[str, int] = {}
    provider_failure_ids: set[str] = set()
    source_request_ids: set[int] = set()
    opportunities: set[int] = set()
    claims: set[tuple[int, int]] = set()
    duplicates: set[str] = set()
    reobservations: set[str] = set()
    refresh_rounds: set[int] = set()
    outcomes: dict[str, list[dict[str, Any]]] = {
        "exact_pair_results": [],
        "pumpswap_results": [],
        "liquidity_results": [],
        "safety_evidence_results": [],
        "inventory_results": [],
    }
    terminal_reason: str | None = None
    kind_to_bucket = {
        "EXACT_PAIR_RESULT": "exact_pair_results",
        "PUMPSWAP_RESULT": "pumpswap_results",
        "LIQUIDITY_RESULT": "liquidity_results",
        "SAFETY_EVIDENCE_RESULT": "safety_evidence_results",
        "INVENTORY_RESULT": "inventory_results",
    }
    for row in rows:
        payload_json = str(row["payload_json"])
        expected_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        if expected_hash != str(row["payload_hash"]):
            raise PreAdmissionAttemptEvidenceError(
                "ATTEMPT_EVIDENCE_PAYLOAD_HASH_MISMATCH"
            )
        payload = json.loads(payload_json)
        if not isinstance(payload, dict):
            raise PreAdmissionAttemptEvidenceError(
                "ATTEMPT_EVIDENCE_PAYLOAD_NOT_OBJECT"
            )
        ordinal = int(row["opportunity_ordinal"])
        claim = int(row["claim_ordinal"])
        opportunities.add(ordinal)
        claims.add((ordinal, claim))
        if ordinal > 0:
            refresh_rounds.add(ordinal)
        kind = str(row["evidence_kind"])
        mint = None if row["mint_identity"] is None else str(row["mint_identity"])
        if mint and kind in {
            "CANDIDATE_OBSERVED",
            "CANDIDATE_REOBSERVED",
            "CANDIDATE_REJECTED",
            "DUPLICATE_OR_ALREADY_USED",
            "EXACT_PAIR_RESULT",
            "PUMPSWAP_RESULT",
            "LIQUIDITY_RESULT",
            "SAFETY_EVIDENCE_RESULT",
        }:
            observed_mints.add(mint)
        if kind == "CANDIDATE_REOBSERVED" and mint:
            reobservations.add(mint)
        if kind == "DUPLICATE_OR_ALREADY_USED":
            duplicates.add(mint or str(row["event_key"]))
        if kind == "CANDIDATE_REJECTED":
            rejected_events.add(str(row["event_key"]))
            reason = str(row["categorical_reason"] or "UNKNOWN_REJECTION")
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
        if kind == "PROVIDER_FAILURE":
            identity = (
                f"failure:{int(row['source_failure_id'])}"
                if row["source_failure_id"] is not None
                else f"payload:{payload.get('provider_failure_id')}"
                if payload.get("provider_failure_id") is not None
                else f"event:{row['event_key']}"
            )
            provider_failure_ids.add(identity)
        if row["source_request_id"] is not None:
            source_request_ids.add(int(row["source_request_id"]))
        bucket = kind_to_bucket.get(kind)
        if bucket is not None:
            outcomes[bucket].append(
                {
                    "event_key": str(row["event_key"]),
                    "mint_identity": mint,
                    "pair_identity": row["pair_identity"],
                    "categorical_reason": row["categorical_reason"],
                    "payload": payload,
                }
            )
        if kind == "REFRESH_ROUND":
            refresh_rounds.add(ordinal)
        if kind == "ATTEMPT_DISPOSITION":
            terminal_reason = str(
                row["categorical_reason"] or payload.get("terminal_reason") or ""
            ) or None
    return {
        "event_count": len(rows),
        "opportunities_executed": sorted(opportunities),
        "claims_executed": len(claims),
        "refresh_rounds": len(refresh_rounds),
        "source_requests": len(source_request_ids),
        "unique_tokens_observed": len(observed_mints),
        "reobserved_tokens": len(reobservations),
        "duplicate_or_already_used_count": len(duplicates),
        "rejected_count": len(rejected_events),
        "rejection_reasons": dict(sorted(rejection_reasons.items())),
        "provider_failures": len(provider_failure_ids),
        "terminal_reason": terminal_reason,
        **outcomes,
    }


def rebuild_exhaustion_certificate_from_attempt_evidence(
    certificate: Mapping[str, Any] | None,
    reduced: Mapping[str, Any],
) -> dict[str, Any]:
    """Replace action-local zeroes with the durable attempt-wide reduction."""
    rebuilt = dict(certificate or {})
    for key in (
        "unique_tokens_observed",
        "rejected_count",
        "provider_failures",
    ):
        rebuilt[key] = max(int(rebuilt.get(key) or 0), int(reduced.get(key) or 0))
    durable_reasons = dict(reduced.get("rejection_reasons") or {})
    base_reasons = dict(rebuilt.get("rejection_reasons") or {})
    rebuilt["rejection_reasons"] = {
        reason: max(int(base_reasons.get(reason) or 0), int(count))
        for reason, count in sorted({**base_reasons, **durable_reasons}.items())
    }
    opportunities = list(reduced.get("opportunities_executed") or ())
    rebuilt["discovery_rounds"] = max(
        int(rebuilt.get("discovery_rounds") or 0), len(opportunities)
    )
    rebuilt["attempt_evidence"] = dict(reduced)
    return rebuilt


def record_later_cycle_supply_evidence(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    supply: Any,
    observed_at: str,
) -> dict[str, Any]:
    """Append one callback claim's facts and return the attempt-wide reduction."""
    diagnostics = dict(getattr(supply, "diagnostics", {}) or {})
    existing_claim = connection.execute(
        """SELECT COALESCE(MAX(claim_ordinal),0)
             FROM printer_pre_admission_attempt_evidence WHERE attempt_id=?""",
        (str(attempt_id),),
    ).fetchone()
    claim_ordinal = int(existing_claim[0] or 0) + 1
    scheduler_yield = dict(diagnostics.get("scheduler_yield") or {})
    completed_refresh = dict(diagnostics.get("completed_refresh") or {})
    opportunity_ordinal = int(
        scheduler_yield.get("refresh_ordinal")
        or completed_refresh.get("refresh_ordinal")
        or diagnostics.get("refresh_ordinal")
        or 0
    )

    def append(**kwargs: Any) -> None:
        append_pre_admission_attempt_evidence(
            connection,
            attempt_id=attempt_id,
            opportunity_ordinal=opportunity_ordinal,
            claim_ordinal=claim_ordinal,
            observed_at=observed_at,
            **kwargs,
        )

    append(
        event_key=f"claim:{claim_ordinal}:opportunity:{opportunity_ordinal}",
        evidence_kind="OPPORTUNITY_EXECUTED",
        categorical_reason=str(getattr(supply, "terminal_cause", None) or "CONTINUE"),
        payload={
            "stage_local_source_requests": int(
                diagnostics.get("stage_local_source_requests") or 0
            ),
            "cooperative_phase": diagnostics.get("cooperative_phase"),
        },
    )
    if opportunity_ordinal > 0:
        append(
            event_key=f"refresh:{opportunity_ordinal}:claim:{claim_ordinal}",
            evidence_kind="REFRESH_ROUND",
            categorical_reason="DISCOVERY_REFRESH",
            payload={"refresh_ordinal": opportunity_ordinal},
        )

    for evidence in tuple(getattr(supply, "source_evidence", ()) or ()):
        request_id = int(evidence.source_request_id)
        event_key = f"source-request:{request_id}"
        if connection.execute(
            """SELECT 1 FROM printer_pre_admission_attempt_evidence
               WHERE attempt_id=? AND event_key=?""",
            (attempt_id, event_key),
        ).fetchone() is None:
            append(
                event_key=event_key,
                evidence_kind=(
                    "PROVIDER_FAILURE"
                    if evidence.source_failure_id is not None
                    else "SOURCE_REQUEST_TERMINAL"
                ),
                categorical_reason=(
                    "SOURCE_FAILURE"
                    if evidence.source_failure_id is not None
                    else "SOURCE_RESPONSE"
                ),
                source_request_id=request_id,
                source_response_id=evidence.source_response_id,
                source_failure_id=evidence.source_failure_id,
                payload={"logical_stage": str(evidence.logical_stage)},
            )

    candidate_rows: list[Mapping[str, Any]] = []
    for source in (
        diagnostics.get("candidates"),
        diagnostics.get("front_door_candidates"),
        (diagnostics.get("exhaustion_certificate") or {}).get(
            "candidate_liquidity_lineage"
        ),
    ):
        if isinstance(source, (list, tuple)):
            candidate_rows.extend(item for item in source if isinstance(item, Mapping))
    direct = dict(diagnostics.get("direct_migration_discovery") or {})
    direct_report = dict(direct.get("source_operation_ledger") or {})
    for source in (direct.get("verifications"), direct_report.get("verifications")):
        if isinstance(source, (list, tuple)):
            candidate_rows.extend(item for item in source if isinstance(item, Mapping))
    for item in tuple(getattr(supply, "candidates", ()) or ()):
        candidate_rows.append(
            {
                "mint": getattr(item, "mint_identity", None),
                "pool": getattr(item, "pair_identity", None),
                "eligible": True,
            }
        )

    seen_candidate_events: set[str] = set()
    for index, candidate in enumerate(candidate_rows, start=1):
        mint = str(
            candidate.get("mint") or candidate.get("mint_identity") or ""
        ).strip()
        pair = str(
            candidate.get("pool")
            or candidate.get("pair")
            or candidate.get("pair_address")
            or candidate.get("pairAddress")
            or ""
        ).strip()
        identity = mint or f"anonymous-{index}"
        event_key = f"candidate:{identity}"
        if event_key not in seen_candidate_events and connection.execute(
            """SELECT 1 FROM printer_pre_admission_attempt_evidence
               WHERE attempt_id=? AND event_key=?""",
            (attempt_id, event_key),
        ).fetchone() is None:
            append(
                event_key=event_key,
                evidence_kind="CANDIDATE_OBSERVED",
                mint_identity=(mint or None),
                pair_identity=(pair or None),
                payload={"candidate": dict(candidate)},
            )
        seen_candidate_events.add(event_key)
        reason = candidate.get("rejection") or candidate.get("reason")
        eligible = candidate.get("eligible")
        if reason and eligible is not True:
            rejection_key = f"rejection:{identity}:{str(reason)}"
            if connection.execute(
                """SELECT 1 FROM printer_pre_admission_attempt_evidence
                   WHERE attempt_id=? AND event_key=?""",
                (attempt_id, rejection_key),
            ).fetchone() is None:
                append(
                    event_key=rejection_key,
                    evidence_kind="CANDIDATE_REJECTED",
                    mint_identity=(mint or None),
                    pair_identity=(pair or None),
                    categorical_reason=str(reason),
                    payload={"candidate": dict(candidate)},
                )

    certificate = dict(diagnostics.get("exhaustion_certificate") or {})
    for reason, count in dict(certificate.get("rejection_reasons") or {}).items():
        for ordinal in range(int(count)):
            event_key = f"certificate-rejection:{reason}:{ordinal + 1}"
            if connection.execute(
                """SELECT 1 FROM printer_pre_admission_attempt_evidence
                   WHERE attempt_id=? AND event_key=?""",
                (attempt_id, event_key),
            ).fetchone() is None:
                append(
                    event_key=event_key,
                    evidence_kind="CANDIDATE_REJECTED",
                    categorical_reason=str(reason),
                    payload={"certificate_aggregate_ordinal": ordinal + 1},
                )
    terminal = getattr(supply, "terminal_cause", None)
    if terminal not in (None, "WAITING_FOR_ELIGIBLE_SUPPLY", "ACQUISITION_QUANTUM_YIELDED"):
        append(
            event_key="attempt-disposition",
            evidence_kind="ATTEMPT_DISPOSITION",
            categorical_reason=str(terminal),
            payload={"terminal_reason": str(terminal)},
        )
    return reduce_pre_admission_attempt_evidence(
        connection, attempt_id=attempt_id
    )


__all__ = [
    "PreAdmissionAttemptEvidenceError",
    "append_pre_admission_attempt_evidence",
    "rebuild_exhaustion_certificate_from_attempt_evidence",
    "reduce_pre_admission_attempt_evidence",
    "record_later_cycle_supply_evidence",
]

"""Immutable retained-evidence contract for WINDOW_15M memory activation.

This module validates already governed evidence.  It never contacts a source,
creates a source request/response/failure, selects a candidate, or starts a
lifecycle.  The existing combined executor remains the activation owner.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
import sqlite3
from typing import Any, Mapping


class ActivationPurpose(str, Enum):
    MEMORY_OBSERVATION = "MEMORY_OBSERVATION"


class EvidenceRole(str, Enum):
    ORIGIN_LINEAGE = "ORIGIN_LINEAGE"
    PUMPSWAP_CONFIRMATION = "PUMPSWAP_CONFIRMATION"
    MARKET_OBSERVATION = "MARKET_OBSERVATION"


class MemoryObservationActivationError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}: {detail}")


@dataclass(frozen=True)
class RetainedEvidenceReference:
    evidence_role: EvidenceRole
    source_name: str
    request_kind: str
    source_request_id: int
    source_response_id: int
    source_failure_id: int | None
    transport_identity_keys: tuple[tuple[object, ...], ...]
    observed_at: str
    raw_payload_hash: str
    target_mint: str
    target_pool: str
    campaign_id: str
    campaign_run_id: str
    cycle_id: str


@dataclass(frozen=True)
class TrackingFeasibility:
    eligible: bool
    reason_code: str
    tracking_queue_id: int | None
    tracking_queue_status: str | None
    requalification_required: bool
    cooldown_until: str | None
    assessed_at: str


@dataclass(frozen=True)
class FrozenMemoryActivationCandidate:
    slot_ordinal: int
    mint: str
    pool: str
    market_identity: str
    lifecycle_identity: str
    activation_route: str
    provenance: str
    memory_observation_eligible: bool
    fully_eligible: bool
    holder_condition: str
    holder_evidence_status: str
    future_action_eligibility: str
    evidence_expires_at: str
    liquidity_observed_at: str
    tracking_feasibility: TrackingFeasibility
    retained_evidence_references: tuple[RetainedEvidenceReference, ...]


@dataclass(frozen=True)
class FrozenMemoryActivationSet:
    activation_purpose: ActivationPurpose
    readiness_id: str
    selection_seed: str
    selected: tuple[FrozenMemoryActivationCandidate, ...]
    alternates: tuple[FrozenMemoryActivationCandidate, ...]
    manifest_request_ids: tuple[int, ...]
    manifest_transport_identity_keys: tuple[tuple[object, ...], ...]
    frozen_at: str
    expires_at: str


def _parse_instant(value: str, *, code: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise MemoryObservationActivationError(code, str(value)) from exc
    if parsed.tzinfo is None:
        raise MemoryObservationActivationError(code, str(value))
    return parsed


def _require_identity(value: object, *, code: str) -> str:
    text = str(value or "").strip()
    if not text or text.upper() == "UNKNOWN":
        raise MemoryObservationActivationError(code)
    return text


def _payload_matches_target(
    raw: object, *, mint: str, pool: str
) -> bool:
    try:
        payload = json.loads(str(raw or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return False

    def contains(value: Any, target: str) -> bool:
        if isinstance(value, Mapping):
            return any(contains(item, target) for item in value.values())
        if isinstance(value, (list, tuple)):
            return any(contains(item, target) for item in value)
        return str(value) == target

    return contains(payload, mint) and contains(payload, pool)


def _retained_observation_time_matches(
    connection: sqlite3.Connection,
    *,
    mint: str,
    pool: str,
    request_id: int,
    response_id: int,
    observed_at: str,
    normalized_payload_json: object,
) -> bool:
    """Match exact observation time from payload or its durable reserve row."""
    try:
        payload = json.loads(str(normalized_payload_json or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {}

    def contains(value: Any, target: str) -> bool:
        if isinstance(value, Mapping):
            return any(contains(item, target) for item in value.values())
        if isinstance(value, (list, tuple)):
            return any(contains(item, target) for item in value)
        return str(value) == target

    if contains(payload, observed_at):
        return True
    rows = connection.execute(
        """SELECT observed_at,evidence_json,source_provenance_json
           FROM printer_discovery_reserve_layers
           WHERE network='solana-mainnet' AND mint_identity=? AND pool_address=?
             AND observed_at=?""",
        (mint, pool, observed_at),
    ).fetchall()
    for row in rows:
        combined = f"{row[1] or ''} {row[2] or ''}"
        if str(request_id) in combined and str(response_id) in combined:
            return True
    return False


def validate_memory_activation_set(
    connection: sqlite3.Connection,
    activation: FrozenMemoryActivationSet,
    *,
    now: str,
) -> dict[str, Any]:
    """Validate one exact frozen pair and its original governed evidence rows.

    The returned reconciliation is scoped to the referenced IDs.  No table-wide
    count is used as evidence and this function performs no INSERT/UPDATE/DELETE.
    """
    if activation.activation_purpose is not ActivationPurpose.MEMORY_OBSERVATION:
        raise MemoryObservationActivationError("ACTIVATION_PURPOSE_UNSUPPORTED")
    _require_identity(activation.readiness_id, code="READINESS_ID_MISSING")
    _require_identity(activation.selection_seed, code="SELECTION_SEED_MISSING")
    instant = _parse_instant(now, code="ACTIVATION_TIME_INVALID")
    if _parse_instant(activation.expires_at, code="ACTIVATION_EXPIRY_INVALID") <= instant:
        raise MemoryObservationActivationError("ACTIVATION_SET_EXPIRED")
    if len(activation.selected) != 2:
        raise MemoryObservationActivationError("ACTIVATION_SELECTED_PAIR_INCOMPLETE")
    if len(activation.alternates) != 2:
        raise MemoryObservationActivationError(
            "ACTIVATION_REPORT_ALTERNATES_INCOMPLETE"
        )
    if [item.slot_ordinal for item in activation.selected] != [1, 2]:
        raise MemoryObservationActivationError("ACTIVATION_SLOT_ORDER_INVALID")
    if len(set(activation.manifest_request_ids)) != len(
        activation.manifest_request_ids
    ):
        raise MemoryObservationActivationError("ACTIVATION_MANIFEST_DUPLICATE_REQUEST")

    manifest_ids = set(int(item) for item in activation.manifest_request_ids)
    transport_keys = {
        tuple(item) for item in activation.manifest_transport_identity_keys
    }
    seen_mints: set[str] = set()
    seen_pools: set[str] = set()
    reference_request_ids: list[int] = []
    reference_response_ids: list[int] = []
    campaign_scope: tuple[str, str, str] | None = None

    for candidate in activation.selected:
        mint = _require_identity(candidate.mint, code="ACTIVATION_MINT_MISSING")
        pool = _require_identity(candidate.pool, code="ACTIVATION_POOL_MISSING")
        _require_identity(candidate.market_identity, code="ACTIVATION_MARKET_IDENTITY_MISSING")
        _require_identity(candidate.lifecycle_identity, code="ACTIVATION_LIFECYCLE_IDENTITY_MISSING")
        if not candidate.market_identity.endswith(f":{pool}"):
            raise MemoryObservationActivationError("ACTIVATION_MARKET_IDENTITY_MISMATCH")
        if mint in seen_mints or pool in seen_pools:
            raise MemoryObservationActivationError("ACTIVATION_SELECTED_IDENTITY_DUPLICATE")
        seen_mints.add(mint)
        seen_pools.add(pool)
        if candidate.memory_observation_eligible is not True:
            raise MemoryObservationActivationError("MEMORY_OBSERVATION_INELIGIBLE")
        tracking = candidate.tracking_feasibility
        if not tracking.eligible or tracking.requalification_required:
            raise MemoryObservationActivationError(
                "TRACKING_FEASIBILITY_INELIGIBLE", tracking.reason_code
            )
        _parse_instant(tracking.assessed_at, code="TRACKING_ASSESSMENT_TIME_INVALID")
        if _parse_instant(
            candidate.evidence_expires_at, code="CANDIDATE_EVIDENCE_EXPIRY_INVALID"
        ) <= instant:
            raise MemoryObservationActivationError("CANDIDATE_EVIDENCE_EXPIRED", mint)
        _parse_instant(
            candidate.liquidity_observed_at, code="LIQUIDITY_OBSERVED_AT_INVALID"
        )
        holder_pass = candidate.holder_condition in {
            "HOLDER_CONCENTRATION_PASS",
            "HOLDER_CONCENTRATION_HEALTHY",
        }
        if candidate.fully_eligible and not holder_pass:
            raise MemoryObservationActivationError("FULLY_ELIGIBLE_WITHOUT_HOLDER_PASS")
        if not holder_pass and candidate.future_action_eligibility == "ELIGIBLE":
            raise MemoryObservationActivationError("FUTURE_ACTION_ELIGIBILITY_OVERSTATED")
        if not candidate.retained_evidence_references:
            raise MemoryObservationActivationError("RETAINED_EVIDENCE_MISSING", mint)

        for reference in candidate.retained_evidence_references:
            if reference.source_failure_id is not None:
                raise MemoryObservationActivationError("RETAINED_SUCCESS_HAS_FAILURE")
            if reference.target_mint != mint or reference.target_pool != pool:
                raise MemoryObservationActivationError(
                    "RETAINED_EVIDENCE_TARGET_MISMATCH"
                )
            scope = (
                _require_identity(reference.campaign_id, code="RETAINED_CAMPAIGN_ID_MISSING"),
                _require_identity(reference.campaign_run_id, code="RETAINED_RUN_ID_MISSING"),
                _require_identity(reference.cycle_id, code="RETAINED_CYCLE_ID_MISSING"),
            )
            if campaign_scope is None:
                campaign_scope = scope
            elif scope != campaign_scope:
                raise MemoryObservationActivationError("RETAINED_OWNERSHIP_MISMATCH")
            request_id = int(reference.source_request_id)
            response_id = int(reference.source_response_id)
            if request_id not in manifest_ids:
                raise MemoryObservationActivationError("RETAINED_REQUEST_NOT_IN_MANIFEST")
            for key in reference.transport_identity_keys:
                if tuple(key) not in transport_keys:
                    raise MemoryObservationActivationError(
                        "RETAINED_TRANSPORT_IDENTITY_MISSING"
                    )

            request = connection.execute(
                """SELECT id,source_name,request_kind,request_key,source_status,
                          data_quality_label
                   FROM printer_source_requests WHERE id=?""",
                (request_id,),
            ).fetchone()
            if request is None:
                raise MemoryObservationActivationError("RETAINED_REQUEST_NOT_FOUND")
            response = connection.execute(
                """SELECT id,source_request_id,source_name,source_status,
                          data_quality_label,response_hash,normalized_payload_json
                   FROM printer_source_responses WHERE id=?""",
                (response_id,),
            ).fetchone()
            if response is None:
                raise MemoryObservationActivationError("RETAINED_RESPONSE_NOT_FOUND")

            def value(row: sqlite3.Row | tuple[Any, ...], key: str, index: int) -> Any:
                return row[key] if isinstance(row, sqlite3.Row) else row[index]

            if (
                value(request, "source_name", 1) != reference.source_name
                or value(request, "request_kind", 2) != reference.request_kind
                or value(request, "source_status", 4) != "COMPLETE"
                or value(request, "data_quality_label", 5) != "CLEAN_DATA"
            ):
                raise MemoryObservationActivationError("RETAINED_REQUEST_CONTRACT_MISMATCH")
            if (
                int(value(response, "source_request_id", 1)) != request_id
                or value(response, "source_name", 2) != reference.source_name
                or value(response, "source_status", 3) != "COMPLETE"
                or value(response, "data_quality_label", 4) != "CLEAN_DATA"
                or value(response, "response_hash", 5) != reference.raw_payload_hash
            ):
                raise MemoryObservationActivationError("RETAINED_RESPONSE_CONTRACT_MISMATCH")
            if not _payload_matches_target(
                value(response, "normalized_payload_json", 6),
                mint=mint,
                pool=pool,
            ):
                raise MemoryObservationActivationError("RETAINED_RESPONSE_TARGET_MISMATCH")
            if not _retained_observation_time_matches(
                connection,
                mint=mint,
                pool=pool,
                request_id=request_id,
                response_id=response_id,
                observed_at=reference.observed_at,
                normalized_payload_json=value(
                    response, "normalized_payload_json", 6
                ),
            ):
                raise MemoryObservationActivationError(
                    "RETAINED_OBSERVATION_TIME_MISMATCH"
                )
            reference_request_ids.append(request_id)
            reference_response_ids.append(response_id)

    return {
        "manifest_request_ids": list(activation.manifest_request_ids),
        "activation_reference_request_ids": reference_request_ids,
        "activation_reference_response_ids": reference_response_ids,
        "new_source_request_ids": [],
        "new_source_response_ids": [],
        "unmanifested_reference_ids": [],
        "missing_transport_identity_keys": [],
        "reconciliation_status": "PASS",
        "evidence_reuse_kind": "RETAINED_GOVERNED_EVIDENCE_REFERENCE",
    }


__all__ = [
    "ActivationPurpose",
    "EvidenceRole",
    "FrozenMemoryActivationCandidate",
    "FrozenMemoryActivationSet",
    "MemoryObservationActivationError",
    "RetainedEvidenceReference",
    "TrackingFeasibility",
    "validate_memory_activation_set",
]

"""Proof-only adapter from permanent GraduatedSupply to frozen cycle-2 input."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Callable, Mapping

from printer_v1.db.sqlite_write_contracts import (
    connect_operational,
    short_write_transaction,
)
from printer_v1.discovery.permanent_discovery_availability import (
    build_campaign_source_request_scope,
    request_key_belongs_to_root,
)
from printer_v1.discovery.token_pair_identity import (
    ensure_neutral_token_pair_identity,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    LaterCycleCandidateSupply,
    LaterCycleDiscoveryCandidate,
    LaterCycleSourceEvidence,
)
from printer_v1.operator_cli.graduated_supply_front_door import (
    GraduatedSupply,
    build_graduated_supply,
)


class LaterCycleGraduatedSupplyError(ValueError):
    """Fail-closed permanent-supply adaptation error."""


HolderEvidenceOwner = Callable[[GraduatedSupply], Mapping[str, Mapping[str, Any]]]

FAILURE_DOMAIN_INTERNAL = "INTERNAL"
FAILURE_DOMAIN_SOURCE = "SOURCE"
FAILURE_DOMAIN_ELIGIBILITY = "ELIGIBILITY"

_SOURCE_SHORTAGE_CLASSIFICATIONS = frozenset(
    {
        "SOURCE_AVAILABILITY_FAILURE",
        "SOURCE_AVAILABILITY_FAILURE_DURING_REFRESH",
        "SOURCE_VISIBILITY_SHORTAGE",
        "BUDGET_EXHAUSTION",
        "DURATION_EXHAUSTION",
        "TRUE_MARKET_SUPPLY_SHORTAGE",
        "STALE_EVIDENCE_SHORTAGE",
        "REFRESH_SOURCE_FAILURE",
    }
)
_INTERNAL_SHORTAGE_CLASSIFICATIONS = frozenset(
    {
        "DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE",
        "INTERNAL_INVARIANT",
        "INTERNAL_RUNTIME_ERROR",
    }
)
_ELIGIBILITY_SHORTAGE_CLASSIFICATIONS = frozenset(
    {
        "TRACKING_STATE_CAPACITY_BLOCKED",
    }
)
_ELIGIBILITY_TERMINAL_CAUSES = frozenset(
    {
        "BLOCKED_INSUFFICIENT_GRADUATED_POOL",
        "BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL",
        "COOLDOWN_REOPEN_REQUIRED",
        "NO_EXACT_PAIR",
        "NO_PAIR",
    }
)


def classify_later_cycle_failure(
    *,
    exception: BaseException | None = None,
    shortage_classification: str | None = None,
    terminal_cause: str | None = None,
) -> str:
    """Classify a later-cycle failure as INTERNAL, SOURCE, or ELIGIBILITY.

    Source means a governed provider/budget/visibility/market outcome.
    Internal means wiring, identity, lineage, or architecture. Eligibility
    means a truthful non-source candidate/tracking conclusion. Unknown
    outcomes fail closed as INTERNAL so they cannot be blamed on a source.
    """
    classification = str(shortage_classification or "").strip()
    if classification in _SOURCE_SHORTAGE_CLASSIFICATIONS:
        return FAILURE_DOMAIN_SOURCE
    if classification in _INTERNAL_SHORTAGE_CLASSIFICATIONS:
        return FAILURE_DOMAIN_INTERNAL
    if classification in _ELIGIBILITY_SHORTAGE_CLASSIFICATIONS:
        return FAILURE_DOMAIN_ELIGIBILITY
    if exception is not None:
        from printer_v1.operator_cli.authoritative_live_operational_campaign import (
            LiveOperationalError,
            LiveTransportError,
        )

        if isinstance(exception, LiveTransportError):
            return FAILURE_DOMAIN_SOURCE
        if isinstance(exception, (LaterCycleGraduatedSupplyError, LiveOperationalError)):
            return FAILURE_DOMAIN_INTERNAL
    cause = str(terminal_cause or "").strip()
    if cause in _SOURCE_SHORTAGE_CLASSIFICATIONS:
        return FAILURE_DOMAIN_SOURCE
    if cause in _INTERNAL_SHORTAGE_CLASSIFICATIONS or cause.startswith(
        (
            "LATER_CYCLE_",
            "CYCLE_SOURCE_LINEAGE_",
            "HOLDER_EVIDENCE_",
            "TEMPORAL_",
            "GRADUATED_SUPPLY_",
            "INTERNAL_",
            "PRE_LIFECYCLE_REFRESH_INTERNAL_",
        )
    ):
        return FAILURE_DOMAIN_INTERNAL
    if cause in _ELIGIBILITY_TERMINAL_CAUSES or cause in _ELIGIBILITY_SHORTAGE_CLASSIFICATIONS:
        return FAILURE_DOMAIN_ELIGIBILITY
    return FAILURE_DOMAIN_INTERNAL


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise LaterCycleGraduatedSupplyError("EVALUATED_AT_INVALID")
    return value.astimezone(timezone.utc)


def _source_lineage(
    connection: sqlite3.Connection,
    *,
    request_key_root: str,
    required: bool = True,
) -> tuple[LaterCycleSourceEvidence, ...]:
    requests = [
        row
        for row in connection.execute(
            "SELECT id,request_kind,request_key FROM printer_source_requests ORDER BY id"
        ).fetchall()
        if request_key_belongs_to_root(str(row[2] or ""), request_key_root)
    ]
    if not requests:
        if required:
            raise LaterCycleGraduatedSupplyError("CYCLE_SOURCE_LINEAGE_MISSING")
        return ()
    evidence: list[LaterCycleSourceEvidence] = []
    for request_id, request_kind, _ in requests:
        responses = connection.execute(
            "SELECT id FROM printer_source_responses WHERE source_request_id=? ORDER BY id",
            (int(request_id),),
        ).fetchall()
        failures = connection.execute(
            "SELECT id FROM printer_source_failures WHERE source_request_id=? ORDER BY id",
            (int(request_id),),
        ).fetchall()
        if len(responses) + len(failures) != 1:
            raise LaterCycleGraduatedSupplyError(
                "CYCLE_SOURCE_LINEAGE_AMBIGUOUS"
            )
        evidence.append(LaterCycleSourceEvidence(
            logical_stage=str(request_kind),
            source_request_id=int(request_id),
            source_response_id=(int(responses[0][0]) if responses else None),
            source_failure_id=(int(failures[0][0]) if failures else None),
        ))
    return tuple(evidence)


def build_later_cycle_graduated_supply(
    db_path: str | Path,
    *,
    campaign_id: str,
    campaign_run_id: str,
    authoritative_factory_run_id: str,
    proposed_cycle_id: str,
    proposed_cycle_ordinal: int,
    evaluated_at: datetime,
    execution_id: str,
    selection_seed: str,
    migration_transport: Any,
    graduated_supply_kwargs: Mapping[str, Any],
    holder_evidence_owner: HolderEvidenceOwner | None = None,
    deadline_at: str | None = None,
    temporal_refresh_owner: Any | None = None,
    cooperative_resume: bool = False,
    prior_source_operations_used: int = 0,
    cooperative_quantum: bool = False,
    cooperative_phase: str | None = None,
    cooperative_stage_budget: Any | None = None,
) -> LaterCycleCandidateSupply:
    """Run the canonical permanent supply once and adapt its exact durable facts.

    ``execution_id`` is the canonical execution identity of the outer V2-9.8B
    command. It owns the governed source-request scope and the exhaustion
    certificate. ``selection_seed`` is selection input only and is passed on as
    ``cycle_seed``.

    Holder eligibility is supplied only by the existing operational holder owner;
    absence is fail-closed and never interpreted as healthy.
    """
    if proposed_cycle_ordinal != 2:
        raise LaterCycleGraduatedSupplyError("PROPOSED_CYCLE_ORDINAL_INVALID")
    canonical_execution_id = str(execution_id or "").strip()
    if not canonical_execution_id:
        raise LaterCycleGraduatedSupplyError("CANONICAL_EXECUTION_ID_REQUIRED")
    instant = _utc(evaluated_at)
    # The front door validates the scope identity against the ``execution_id``
    # kwarg and blocks any root a durable source request already owns, so one
    # canonical-execution-bound identity must serve both. The cycle qualifier
    # keeps this cycle's root and certificate id exclusive within the execution.
    cycle_execution_identity = (
        f"{canonical_execution_id}:c{int(proposed_cycle_ordinal):04d}"
    )
    scope = build_campaign_source_request_scope(
        execution_id=cycle_execution_identity,
        campaign_id=campaign_id,
        run_id=campaign_run_id,
        cycle_id=proposed_cycle_id,
    )
    kwargs = dict(graduated_supply_kwargs)
    if (deadline_at is None) != (temporal_refresh_owner is None):
        raise LaterCycleGraduatedSupplyError("TEMPORAL_ACQUISITION_BINDING_INCOMPLETE")
    if temporal_refresh_owner is not None:
        if (
            str(getattr(temporal_refresh_owner, "campaign_id", "")) != campaign_id
            or str(getattr(temporal_refresh_owner, "run_id", "")) != campaign_run_id
            or str(getattr(temporal_refresh_owner, "cycle_id", "")) != proposed_cycle_id
            or str(getattr(temporal_refresh_owner, "acquisition_deadline_at", "")) != str(deadline_at)
        ):
            raise LaterCycleGraduatedSupplyError(
                "TEMPORAL_ACQUISITION_OWNER_IDENTITY_MISMATCH"
            )
    kwargs.update({
        "permanent_availability": True,
        "tracking_precheck": True,
        "required_token_capacity": 2,
        "campaign_id": campaign_id,
        "execution_id": cycle_execution_identity,
        "run_id": campaign_run_id,
        "cycle_id": proposed_cycle_id,
        "campaign_source_request_scope": scope,
        "discovery_request_key_prefix": scope.request_key_root,
        "front_door_request_key_prefix": scope.request_key_root,
    })
    if temporal_refresh_owner is not None:
        kwargs["deadline_at"] = str(deadline_at)
        kwargs["temporal_refresh_owner"] = temporal_refresh_owner
    kwargs["cooperative_resume"] = bool(cooperative_resume)
    kwargs["prior_source_operations_used"] = int(prior_source_operations_used)
    kwargs["cooperative_quantum"] = bool(cooperative_quantum)
    kwargs["cooperative_phase"] = cooperative_phase
    kwargs["cooperative_stage_budget"] = cooperative_stage_budget
    supply = build_graduated_supply(
        db_path,
        cycle_seed=selection_seed,
        migration_transport=migration_transport,
        now=instant.isoformat(),
        **kwargs,
    )
    if not isinstance(supply, GraduatedSupply):
        raise LaterCycleGraduatedSupplyError("GRADUATED_SUPPLY_RESULT_INVALID")
    # Carry the canonical supply diagnostics across this boundary. Without them
    # the exhaustion certificate and shortage classification cannot reach the
    # existing authoritative campaign mapping and reporting.
    diagnostics = dict(supply.diagnostics)
    if supply.terminal in {
        "WAITING_FOR_ELIGIBLE_SUPPLY",
        "ACQUISITION_QUANTUM_YIELDED",
    }:
        failure_domain = None
    else:
        failure_domain = classify_later_cycle_failure(
            shortage_classification=(
                None
                if diagnostics.get("shortage_classification") is None
                else str(diagnostics.get("shortage_classification"))
            ),
            terminal_cause=supply.terminal,
        )
    if not supply.ready or len(supply.graduated_supply) != 2:
        connection = connect_operational(db_path)
        try:
            lineage = _source_lineage(
                connection,
                request_key_root=scope.request_key_root,
                required=False,
            )
        finally:
            connection.close()
        return LaterCycleCandidateSupply(
            (), lineage, supply.terminal, diagnostics, failure_domain
        )
    if holder_evidence_owner is None:
        raise LaterCycleGraduatedSupplyError("HOLDER_EVIDENCE_OWNER_REQUIRED")
    holder_facts = holder_evidence_owner(supply)
    if not isinstance(holder_facts, Mapping):
        raise LaterCycleGraduatedSupplyError("HOLDER_EVIDENCE_RESULT_INVALID")

    prepared: list[dict[str, Any]] = []
    for admission in supply.graduated_supply:
        mint = str(admission.mint)
        pool = str(admission.pool_address)
        raw = dict(supply.holder_reserve_candidates.get(mint.lower()) or {})
        fact = holder_facts.get(mint.lower()) or holder_facts.get(mint)
        if not isinstance(fact, Mapping) or fact.get("eligible") is not True:
            raise LaterCycleGraduatedSupplyError(
                f"HOLDER_EVIDENCE_INELIGIBLE:{mint}"
            )
        canonical = {
            "candidate": raw,
            "holder_evidence": dict(fact),
            "market_identity": str(admission.market_identity),
            "mint_identity": mint,
            "pair_identity": pool,
        }
        canonical_json = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        observed_raw = str(admission.temporal_context.admission_observed_at_utc)
        observed = datetime.fromisoformat(observed_raw.replace("Z", "+00:00"))
        provenance = str(raw.get("provenance") or "").strip()
        if not provenance:
            raise LaterCycleGraduatedSupplyError(
                f"CANDIDATE_PROVENANCE_MISSING:{mint}"
            )
        prepared.append({
            "admission": admission,
            "mint": mint,
            "pool": pool,
            "canonical_json": canonical_json,
            "observed": observed,
            "provenance": provenance,
        })

    connection = connect_operational(db_path)
    try:
        identities = []
        with short_write_transaction(connection):
            for item in prepared:
                identities.append(ensure_neutral_token_pair_identity(
                    connection,
                    mint_identity=str(item["mint"]),
                    pair_identity=str(item["pool"]),
                ))

        candidates: list[LaterCycleDiscoveryCandidate] = []
        for item, identity in zip(prepared, identities, strict=True):
            admission = item["admission"]
            mint = str(item["mint"])
            pool = str(item["pool"])
            canonical_json = str(item["canonical_json"])
            candidates.append(LaterCycleDiscoveryCandidate(
                token_identity=f"solana-mainnet:{mint}",
                token_row_id=identity.token_row_id,
                mint_identity=mint,
                pair_identity=pool,
                pair_row_id=identity.pair_row_id,
                lifecycle_identity="PUMPSWAP_GRADUATED_CONFIRMED",
                canonical_market_identity=str(admission.market_identity),
                canonical_pool_identity=pool,
                channels=frozenset({str(item["provenance"])}),
                holder_evidence_eligible=True,
                canonical_evidence_json=canonical_json,
                canonical_evidence_hash=hashlib.sha256(canonical_json.encode()).hexdigest(),
                evidence_version="V2_9_8B_PERMANENT_GRADUATED_SUPPLY_V1",
                observed_at=_utc(item["observed"]),
            ))
        lineage = _source_lineage(connection, request_key_root=scope.request_key_root)
        return LaterCycleCandidateSupply(
            tuple(candidates), lineage, None, diagnostics, None
        )
    finally:
        connection.close()

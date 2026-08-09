"""V2-9.8B.21 Canonical Eligible Token Supply service.

Owns:

* durable eligible reserve across campaigns (with mandatory revalidation);
* persistent multi-round discovery loop inside one authorized campaign;
* honest exhaustion certificates and shortage classification;
* completeness invariants:

  - ELIGIBLE_ONE_COMPLETENESS
  - ELIGIBLE_CAPACITY_COMPLETENESS
  - PERSISTENT_DISCOVERY_UNTIL_CAPACITY
  - HONEST_EXHAUSTION

Does **not** own migration verification, exact-pool market transport, Source
Governor, Scheduler, holder funnel, or tracking handoff. Those remain with their
existing owners. This module composes them into a complete supply loop.

Locked: no scoring/ranking/confidence/weights, no retrieval/decisions/positions/
trades/audits/PnL, no automatic retry/restart/successor, no wallet/signing, no
paid APIs, no embeddings/vectors.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from printer_v1.discovery.direct_migration_discovery import (
    run_direct_migration_discovery,
)
from printer_v1.discovery.graduated_liquidity_front_door import (
    LIQUIDITY_BELOW_SELECTION_FLOOR,
    LIQUIDITY_PROVEN,
    LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL,
    LIQUIDITY_SOURCE_RATE_LIMITED_OR_STALE,
    LIQUIDITY_SOURCE_UNAVAILABLE,
    LIQUIDITY_UNPROVEN,
    SELECTION_FLOOR_USD,
    run_graduated_liquidity_front_door,
)
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    ACQUISITION_DEADLINE_EXHAUSTED,
    CANCELLED as TEMPORAL_CANCELLED,
    CURRENT_UNIVERSE_EXHAUSTED_TERMINAL,
    CURRENT_UNIVERSE_EXHAUSTED_WAITING,
    CURRENT_UNIVERSE_EXHAUSTION_REASONS,
    NO_LAWFUL_REFRESH_WINDOW,
    PRE_LIFECYCLE_ACQUISITION_DURATION_EXHAUSTED,
    PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS,
    REFRESH_COMPLETED,
    REFRESH_SOURCE_FAILURE,
    SOURCE_BUDGET_EXHAUSTED as TEMPORAL_SOURCE_BUDGET_EXHAUSTED,
    SUPERVISION_FAILED as TEMPORAL_SUPERVISION_FAILED,
    UNSAFE_SCHEDULER_STATE,
    WAITING_FOR_ELIGIBLE_SUPPLY,
    AcquisitionLedger,
    TemporalRefreshOutcome,
)
from printer_v1.discovery.permanent_discovery_availability import (
    StageBudget,
    order_canonical_inventory_fairly,
    record_fresh_pool_nominations,
    run_dexscreener_batch_market_resolution,
    run_geckoterminal_fresh_nomination,
)
from printer_v1.sources.pumpswap_graduated_registry import (
    export_graduated_candidates,
)

REQUIRED_TOKEN_CAPACITY = 2
EVALUATION_BATCH_SIZE = 6
DEFAULT_DISCOVERY_OPERATION_BUDGET = 30
LIFECYCLE_OPERATION_CEILING = 45
CERTIFICATE_VERSION = "V2_9_8B_LIQUIDITY_EVIDENCE_EXHAUSTION_V2"

# Eligibility reserve statuses.
ELIGIBLE_FRESH = "ELIGIBLE_FRESH"
ELIGIBLE_STALE = "ELIGIBLE_STALE"
REMOVED = "REMOVED"
EXCLUDED = "EXCLUDED"

# Shortage classifications (exactly one per certificate).
TRUE_MARKET_SUPPLY_SHORTAGE = "TRUE_MARKET_SUPPLY_SHORTAGE"
SOURCE_VISIBILITY_SHORTAGE = "SOURCE_VISIBILITY_SHORTAGE"
SOURCE_AVAILABILITY_FAILURE = "SOURCE_AVAILABILITY_FAILURE"
BUDGET_EXHAUSTION = "BUDGET_EXHAUSTION"
DURATION_EXHAUSTION = "DURATION_EXHAUSTION"
STALE_EVIDENCE_SHORTAGE = "STALE_EVIDENCE_SHORTAGE"
DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE = "DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE"
TRACKING_STATE_CAPACITY_BLOCKED = "TRACKING_STATE_CAPACITY_BLOCKED"
MIGRATION_EVIDENCE_REJECTED = "MIGRATION_EVIDENCE_REJECTED"

SHORTAGE_CLASSIFICATIONS = (
    TRUE_MARKET_SUPPLY_SHORTAGE,
    SOURCE_VISIBILITY_SHORTAGE,
    SOURCE_AVAILABILITY_FAILURE,
    BUDGET_EXHAUSTION,
    DURATION_EXHAUSTION,
    STALE_EVIDENCE_SHORTAGE,
    DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE,
    TRACKING_STATE_CAPACITY_BLOCKED,
)

# Candidate-local Pump migrate validation failures. Transport completed; the
# pinned exactly-one migrate proof failed closed. These must never mark a
# shared channel unavailable or stop peer discovery work.
_CANDIDATE_LOCAL_MIGRATE_FAILURE_PREFIX = "direct_pump_migration_rejected_"


def _is_candidate_local_migrate_failure(failure_type: str | None) -> bool:
    return str(failure_type or "").startswith(_CANDIDATE_LOCAL_MIGRATE_FAILURE_PREFIX)

BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL = (
    "BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL"
)
GRADUATED_SUPPLY_READY = "GRADUATED_SUPPLY_READY"


class EligibleTokenSupplyError(RuntimeError):
    """Fail-closed eligible-token-supply fault."""


def _validate_reconciliation_stage_charge(*, offered: int, actual: int) -> int:
    if type(offered) is not int or offered < 0 or type(actual) is not int or actual < 0 or actual > offered:
        raise EligibleTokenSupplyError("RECONCILIATION_STAGE_CAPACITY_OVERRUN")
    return actual


def _apply_permanent_shortage_precedence(
    *, shortage: str, last_stop_reason: str | None,
    tracking_dispositions: Mapping[str, Mapping[str, Any]],
    provider_failures: int, channels_unavailable: Sequence[str],
    liquidity_source_unavailable: int, liquidity_stale_or_rate_limited: int,
    liquidity_malformed_or_partial: int, true_budget_exhausted: bool,
    duration_exhausted: bool,
) -> str:
    if liquidity_source_unavailable > 0: return SOURCE_AVAILABILITY_FAILURE
    if liquidity_stale_or_rate_limited > 0: return STALE_EVIDENCE_SHORTAGE
    if liquidity_malformed_or_partial > 0: return SOURCE_VISIBILITY_SHORTAGE
    if provider_failures > 0 and channels_unavailable: return SOURCE_AVAILABILITY_FAILURE
    if last_stop_reason == "DISCOVERY_OPERATION_BUDGET_EXHAUSTED" and true_budget_exhausted:
        return BUDGET_EXHAUSTION
    if duration_exhausted or last_stop_reason == "CAMPAIGN_DURATION_EXHAUSTED":
        return DURATION_EXHAUSTION
    if last_stop_reason == "LAWFUL_WORK_REMAINING_WITH_CAPACITY":
        return DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE
    if any(not bool(x.get("eligible_for_evidence")) for x in tracking_dispositions.values()):
        return TRACKING_STATE_CAPACITY_BLOCKED
    return shortage


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _connect(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


# --------------------------------------------------------------------------- #
# Reserve persistence                                                          #
# --------------------------------------------------------------------------- #

def load_eligible_reserve(
    connection: sqlite3.Connection,
    *,
    statuses: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Load durable eligible-reserve rows (empty if table absent)."""
    if not _table_exists(connection, "printer_eligible_token_reserve"):
        return []
    if statuses:
        placeholders = ",".join("?" for _ in statuses)
        rows = connection.execute(
            f"""SELECT * FROM printer_eligible_token_reserve
                WHERE eligibility_status IN ({placeholders})
                ORDER BY mint_identity""",
            tuple(statuses),
        ).fetchall()
    else:
        rows = connection.execute(
            """SELECT * FROM printer_eligible_token_reserve
               ORDER BY mint_identity"""
        ).fetchall()
    return [dict(r) for r in rows]


def upsert_eligible_reserve(
    connection: sqlite3.Connection,
    *,
    mint: str,
    pumpswap_pool: str,
    market_identity: str,
    provenance: str,
    liquidity_usd: float | None,
    liquidity_status: str,
    eligibility_status: str,
    last_validated_at: str,
    source_provenance: str | None,
    last_campaign_id: str | None,
    exclusion_reason: str | None = None,
) -> None:
    if not _table_exists(connection, "printer_eligible_token_reserve"):
        return
    now = last_validated_at
    connection.execute(
        """INSERT INTO printer_eligible_token_reserve(
            mint_identity, pumpswap_pool, market_identity, provenance,
            liquidity_usd, liquidity_status, eligibility_status,
            last_validated_at, source_provenance, last_campaign_id,
            exclusion_reason, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(mint_identity) DO UPDATE SET
            pumpswap_pool=excluded.pumpswap_pool,
            market_identity=excluded.market_identity,
            provenance=excluded.provenance,
            liquidity_usd=excluded.liquidity_usd,
            liquidity_status=excluded.liquidity_status,
            eligibility_status=excluded.eligibility_status,
            last_validated_at=excluded.last_validated_at,
            source_provenance=excluded.source_provenance,
            last_campaign_id=excluded.last_campaign_id,
            exclusion_reason=excluded.exclusion_reason,
            updated_at=excluded.updated_at""",
        (
            mint,
            pumpswap_pool,
            market_identity,
            provenance,
            liquidity_usd,
            liquidity_status,
            eligibility_status,
            last_validated_at,
            source_provenance,
            last_campaign_id,
            exclusion_reason,
            now,
            now,
        ),
    )


def mark_reserve_status(
    connection: sqlite3.Connection,
    mint: str,
    *,
    status: str,
    now: str,
    exclusion_reason: str | None = None,
) -> None:
    if not _table_exists(connection, "printer_eligible_token_reserve"):
        return
    connection.execute(
        """UPDATE printer_eligible_token_reserve
           SET eligibility_status=?, exclusion_reason=?, updated_at=?
           WHERE mint_identity=?""",
        (status, exclusion_reason, now, mint),
    )


# --------------------------------------------------------------------------- #
# Exhaustion certificate                                                       #
# --------------------------------------------------------------------------- #

@dataclass
class ExhaustionCertificate:
    """Durable honest exhaustion evidence when capacity is unmet."""

    certificate_id: str
    campaign_id: str | None
    execution_id: str | None
    run_id: str | None
    cycle_id: str | None
    required_eligible_capacity: int
    eligible_reserve_count: int
    approved_discovery_channels_attempted: list[str]
    channels_unavailable: list[str]
    unique_tokens_observed: int
    duplicate_observations_removed: int
    tokens_already_known_from_inventory: int
    pools_confirmed: int
    fresh_market_checks: int
    eligible_count: int
    rejected_count: int
    rejection_reasons: dict[str, int]
    cooldown_skips: int
    stale_evidence_exclusions: int
    provider_failures: int
    liquidity_stage_provider_failures: int
    liquidity_outcome_counts: dict[str, int]
    candidate_liquidity_lineage: list[dict[str, Any]]
    source_operations_used: int
    source_operations_remaining: int
    duration_used_seconds: float | None
    duration_remaining_seconds: float | None
    unexplored_work_prevented_by_hard_ceiling: bool
    last_reason_discovery_could_not_continue: str
    shortage_classification: str
    discovery_rounds: int
    certificate_version: str = CERTIFICATE_VERSION
    created_at: str = field(default_factory=_utc_now_iso)
    #: Present only when a bounded pre-lifecycle temporal acquisition ran. It
    #: distinguishes an instantaneous universe exhaustion inside a live horizon
    #: from a genuine terminal exhaustion after the horizon closed.
    pre_lifecycle_acquisition: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "campaign_id": self.campaign_id,
            "execution_id": self.execution_id,
            "run_id": self.run_id,
            "cycle_id": self.cycle_id,
            "required_eligible_capacity": self.required_eligible_capacity,
            "eligible_reserve_count": self.eligible_reserve_count,
            "approved_discovery_channels_attempted": list(
                self.approved_discovery_channels_attempted
            ),
            "channels_unavailable": list(self.channels_unavailable),
            "unique_tokens_observed": self.unique_tokens_observed,
            "duplicate_observations_removed": self.duplicate_observations_removed,
            "tokens_already_known_from_inventory": self.tokens_already_known_from_inventory,
            "pools_confirmed": self.pools_confirmed,
            "fresh_market_checks": self.fresh_market_checks,
            "eligible_count": self.eligible_count,
            "rejected_count": self.rejected_count,
            "rejection_reasons": dict(self.rejection_reasons),
            "cooldown_skips": self.cooldown_skips,
            "stale_evidence_exclusions": self.stale_evidence_exclusions,
            "provider_failures": self.provider_failures,
            "liquidity_stage_provider_failures": (
                self.liquidity_stage_provider_failures
            ),
            "liquidity_outcome_counts": dict(self.liquidity_outcome_counts),
            "candidate_liquidity_lineage": [
                dict(item) for item in self.candidate_liquidity_lineage
            ],
            "source_operations_used": self.source_operations_used,
            "source_operations_remaining": self.source_operations_remaining,
            "duration_used_seconds": self.duration_used_seconds,
            "duration_remaining_seconds": self.duration_remaining_seconds,
            "unexplored_work_prevented_by_hard_ceiling": (
                self.unexplored_work_prevented_by_hard_ceiling
            ),
            "last_reason_discovery_could_not_continue": (
                self.last_reason_discovery_could_not_continue
            ),
            "shortage_classification": self.shortage_classification,
            "discovery_rounds": self.discovery_rounds,
            "certificate_version": self.certificate_version,
            "created_at": self.created_at,
            "pre_lifecycle_acquisition": (
                None
                if self.pre_lifecycle_acquisition is None
                else dict(self.pre_lifecycle_acquisition)
            ),
        }


def persist_exhaustion_certificate(
    connection: sqlite3.Connection,
    certificate: ExhaustionCertificate,
) -> None:
    if not _table_exists(connection, "printer_discovery_exhaustion_certificates"):
        return
    connection.execute(
        """INSERT INTO printer_discovery_exhaustion_certificates(
            certificate_id, campaign_id, execution_id, run_id, cycle_id,
            required_eligible_capacity, eligible_reserve_count,
            shortage_classification, certificate_json, certificate_version,
            created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            certificate.certificate_id,
            certificate.campaign_id,
            certificate.execution_id,
            certificate.run_id,
            certificate.cycle_id,
            certificate.required_eligible_capacity,
            certificate.eligible_reserve_count,
            certificate.shortage_classification,
            json.dumps(certificate.to_dict(), sort_keys=True),
            certificate.certificate_version,
            certificate.created_at,
        ),
    )


def classify_shortage(
    *,
    provider_failures: int,
    channels_unavailable: Sequence[str],
    duration_remaining_seconds: float | None,
    source_operations_remaining: int,
    unexplored_unique_remaining: int,
    eligible_count: int,
    unique_tokens_observed: int,
    discovery_rounds: int,
    evaluation_batch_size: int,
    all_channels_exhausted: bool,
    liquidity_source_unavailable: int = 0,
    liquidity_stale_or_rate_limited: int = 0,
    liquidity_malformed_or_partial: int = 0,
) -> str:
    """Return exactly one shortage classification.

    Provider unavailability, budget, and duration are never reported as true
    market insufficiency. A single small batch with remaining budget and
    unexplored inventory is architecture-false shortage (must not be the normal
    post-repair path).
    """
    if liquidity_source_unavailable > 0:
        return SOURCE_AVAILABILITY_FAILURE
    if liquidity_stale_or_rate_limited > 0:
        return STALE_EVIDENCE_SHORTAGE
    if liquidity_malformed_or_partial > 0:
        return SOURCE_VISIBILITY_SHORTAGE
    if provider_failures > 0 and (
        channels_unavailable or unique_tokens_observed == 0
    ):
        return SOURCE_AVAILABILITY_FAILURE
    if duration_remaining_seconds is not None and duration_remaining_seconds <= 0:
        return DURATION_EXHAUSTION
    if source_operations_remaining <= 0:
        return BUDGET_EXHAUSTION
    if (
        unexplored_unique_remaining > 0
        and source_operations_remaining > 0
        and (duration_remaining_seconds is None or duration_remaining_seconds > 0)
    ):
        # Lawful work remained — architecture must not stop here after repair.
        return DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE
    if eligible_count == 0 and unique_tokens_observed == 0 and all_channels_exhausted:
        return SOURCE_VISIBILITY_SHORTAGE
    if all_channels_exhausted and unexplored_unique_remaining == 0:
        return TRUE_MARKET_SUPPLY_SHORTAGE
    if (
        discovery_rounds <= 1
        and unique_tokens_observed <= evaluation_batch_size
        and source_operations_remaining > 0
    ):
        return DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE
    if unexplored_unique_remaining == 0 and all_channels_exhausted:
        return TRUE_MARKET_SUPPLY_SHORTAGE
    return TRUE_MARKET_SUPPLY_SHORTAGE


# --------------------------------------------------------------------------- #
# Result                                                                       #
# --------------------------------------------------------------------------- #

@dataclass
class PersistentSupplyResult:
    """Outcome of one campaign-scoped persistent eligible-supply run."""

    ready: bool
    terminal: str
    eligible_reserve: list[dict[str, Any]]
    all_candidates: list[dict[str, Any]]
    discovery_report: Mapping[str, Any]
    front_door_report: Mapping[str, Any]
    locator_report: Mapping[str, Any]
    diagnostics: dict[str, Any]
    exhaustion_certificate: ExhaustionCertificate | None = None
    shortage_classification: str | None = None
    discovery_rounds: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "terminal": self.terminal,
            "eligible_reserve_count": len(self.eligible_reserve),
            "discovery_rounds": self.discovery_rounds,
            "shortage_classification": self.shortage_classification,
            "exhaustion_certificate": (
                None
                if self.exhaustion_certificate is None
                else self.exhaustion_certificate.to_dict()
            ),
            "diagnostics": dict(self.diagnostics),
        }


# --------------------------------------------------------------------------- #
# Candidate helpers                                                            #
# --------------------------------------------------------------------------- #

def _candidate_from_front_door_item(item: Mapping[str, Any]) -> dict[str, Any]:
    liquidity = item.get("liquidity") or {}
    if not isinstance(liquidity, Mapping):
        liquidity = {}
    mint = str(item.get("mint") or "")
    pool = str(item.get("pool") or item.get("pumpswap_pool") or "")
    liquidity_evidence = dict(liquidity)
    return {
        **dict(item),
        "mint": mint,
        "pool": pool,
        "pumpswap_pool": pool,
        "market_identity": str(item.get("market_identity") or ""),
        "provenance": str(item.get("provenance") or ""),
        "lifecycle_state": str(item.get("lifecycle_state") or ""),
        "graduation_block_time": item.get("graduation_block_time"),
        "liquidity_usd": liquidity.get("liquidity_usd"),
        "liquidity_status": str(
            liquidity.get("status") or item.get("liquidity_status") or LIQUIDITY_UNPROVEN
        ),
        "liquidity_reason": liquidity.get("reason"),
        "liquidity_detailed_reason": liquidity.get("detailed_reason"),
        "liquidity_source_status": liquidity.get("source_status"),
        "liquidity_outcome_category": liquidity.get("outcome_category"),
        "liquidity": liquidity_evidence,
        "evidence_expires_at": item.get("evidence_expires_at"),
        "eligible": bool(item.get("eligible")),
        "rejection": item.get("rejection"),
        "source_path": str(
            item.get("source_path")
            or f"candidate_admission:{item.get('provenance') or 'UNKNOWN'}"
        ),
    }


def _merge_rejection_reasons(
    bucket: dict[str, int], candidates: Sequence[Mapping[str, Any]]
) -> None:
    for c in candidates:
        if c.get("eligible"):
            continue
        reason = str(
            c.get("liquidity_reason")
            if c.get("rejection") == LIQUIDITY_UNPROVEN and c.get("liquidity_reason")
            else c.get("rejection") or "UNKNOWN_REJECTION"
        )
        bucket[reason] = bucket.get(reason, 0) + 1


def _candidate_rejection_reason(candidate: Mapping[str, Any]) -> str:
    rejection = candidate.get("rejection")
    if rejection == LIQUIDITY_UNPROVEN and candidate.get("liquidity_reason"):
        return str(candidate["liquidity_reason"])
    return str(rejection or candidate.get("liquidity_reason") or "UNKNOWN_REJECTION")


def _protocol_promotion_candidate(promo: Mapping[str, Any]) -> dict[str, Any]:
    """The one admission shape for a protocol-confirmed retained-liquidity row.

    Shared verbatim by the campaign-start early protocol pass and the bounded
    pre-lifecycle temporal refresh, so a refreshed promotion is admitted through
    exactly the existing path and no second gate can drift into existence.
    """
    return {
        **dict(promo),
        "mint": str(promo.get("mint") or ""),
        "pool": str(promo.get("pool") or ""),
        "pumpswap_pool": str(promo.get("pool") or ""),
        "market_identity": str(
            promo.get("market_identity")
            or f"solana-mainnet:pumpswap:{promo.get('pool')}"
        ),
        "provenance": "FRESH_AGGREGATOR_PROTOCOL_CONFIRMED",
        "liquidity_usd": promo.get("liquidity_usd"),
        "liquidity_status": "LIQUIDITY_PROVEN",
        "liquidity": dict(promo.get("liquidity") or {}),
        "evidence_expires_at": promo.get("evidence_expires_at"),
        "eligible": True,
        "rejection": None,
        "memory_observation_eligible": True,
        "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
        "source_path": "retained_liquidity_protocol_promotion",
    }


def _candidate_liquidity_lineage(candidate: Mapping[str, Any]) -> dict[str, Any]:
    liquidity = candidate.get("liquidity")
    evidence = dict(liquidity) if isinstance(liquidity, Mapping) else {}
    return {
        "mint": candidate.get("mint"),
        "pool": candidate.get("pumpswap_pool") or candidate.get("pool"),
        "source_request_id": evidence.get("source_request_id"),
        "source_response_id": evidence.get("source_response_id"),
        "source_failure_id": evidence.get("source_failure_id"),
        "failure_type": evidence.get("failure_type"),
        "reason": evidence.get("reason"),
        "detailed_reason": evidence.get("detailed_reason"),
        "source_status": evidence.get("source_status"),
        "outcome_category": evidence.get("outcome_category"),
    }


# --------------------------------------------------------------------------- #
# Persistent discovery loop                                                    #
# --------------------------------------------------------------------------- #

def run_persistent_eligible_token_supply(
    db_path: str | Path,
    *,
    cycle_seed: str,
    migration_transport: Callable[[Any], Mapping[str, Any]],
    verifier_transport_factory: Callable[[str, str], Callable[[Any], Mapping[str, Any]]]
    | None = None,
    dexscreener_transport_factory: Callable[[str, str], Callable[[Any], Mapping[str, Any]]]
    | None = None,
    dexscreener_batch_transport_factory: Callable[
        [Sequence[str]], Callable[[Any], Mapping[str, Any]]
    ] | None = None,
    geckoterminal_reconciliation_transport_factory: Callable[
        [str], Callable[[Any], Mapping[str, Any]]
    ] | None = None,
    locator_transport: Callable[[Any], Mapping[str, Any]] | None = None,
    geckoterminal_nomination_transport: Callable[[Any], Mapping[str, Any]] | None = None,
    now: str | None = None,
    collection_rounds: int = 1,
    max_candidates: int = 5,
    settle_seconds: float = 0.0,
    reverify_on_transient: bool = False,
    reverify_settle_seconds: float = 0.0,
    front_door_max_candidates: int = EVALUATION_BATCH_SIZE,
    discovery_request_key_prefix: str = "v2-9-8b-21",
    front_door_request_key_prefix: str = "v2-9-8b-21",
    batch_seq: int = 1,
    run_locator: bool = False,
    required_token_capacity: int = REQUIRED_TOKEN_CAPACITY,
    discovery_operation_budget: int = DEFAULT_DISCOVERY_OPERATION_BUDGET,
    deadline_at: str | None = None,
    # V2-9.8B Post-DTW98 bounded pre-lifecycle temporal acquisition. Default
    # ``None`` preserves every existing non-operational consumer's behaviour:
    # without an owner, current-universe exhaustion stays terminal exactly as
    # before. This service never calls the Scheduler itself.
    temporal_refresh_owner: Any | None = None,
    campaign_id: str | None = None,
    execution_id: str | None = None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    locator_runner: Callable[..., Mapping[str, Any]] | None = None,
    tracking_precheck: bool = False,
    stage_evidence_sink: Callable[[Mapping[str, Any]], None] | None = None,
    transport_identity_observer: Callable[[Any], None] | None = None,
    local_validation_identity_observer: Callable[[Any], None] | None = None,
    permanent_availability: bool = False,
    run_geckoterminal_nomination: bool = False,
    enable_geckoterminal_reconciliation: bool = True,
    protocol_account_batch_transport: Any | None = None,
    protocol_account_batch_transport_factory: Any | None = None,
) -> PersistentSupplyResult:
    """Run persistent multi-round eligible discovery inside one campaign.

    Continues bounded evaluation batches until ``required_token_capacity`` freshly
    eligible tokens are in the campaign reserve, or a governed exhaustion
    condition is proven. Never creates a retry, restart, or successor campaign.
    """
    if not cycle_seed or not str(cycle_seed).strip():
        raise EligibleTokenSupplyError("MISSING_CYCLE_SEED")
    if required_token_capacity < 1:
        raise EligibleTokenSupplyError("INVALID_REQUIRED_CAPACITY")
    if front_door_max_candidates < 1:
        raise EligibleTokenSupplyError("INVALID_EVALUATION_BATCH_SIZE")
    if permanent_availability:
        # Two selected plus one fully eligible alternate per slot. This is a
        # reserve capacity, never a ranking or permission to consume four slots.
        required_token_capacity = max(4, required_token_capacity)

    now = now or _utc_now_iso()
    started_at = _parse_iso(now)
    deadline_dt = _parse_iso(deadline_at) if deadline_at else None

    # --- Locator (optional, once) -------------------------------------------
    # Genuinely not-requested locators emit no stage evidence block.
    locator_stage_kwargs: dict[str, Any] = {}
    if (stage_evidence_sink is not None or transport_identity_observer is not None) and run_locator:
        locator_stage_kwargs = {
            "campaign_id": campaign_id,
            "run_id": run_id,
            "cycle_id": cycle_id,
            "stage_sequence": 1,
        }
        if stage_evidence_sink is not None:
            locator_stage_kwargs["stage_evidence_sink"] = stage_evidence_sink
        if transport_identity_observer is not None:
            locator_stage_kwargs["transport_identity_observer"] = (
                transport_identity_observer
            )
    if locator_runner is not None and run_locator:
        locator = dict(
            locator_runner(
                db_path,
                transport=locator_transport,
                request_key=f"{discovery_request_key_prefix}-locator",
                now=now,
                **locator_stage_kwargs,
            )
        )
    elif run_locator:
        from printer_v1.operator_cli.graduated_supply_front_door import (
            run_fresh_profile_locator,
        )

        locator = run_fresh_profile_locator(
            db_path,
            transport=locator_transport,
            request_key=f"{discovery_request_key_prefix}-locator",
            now=now,
            **locator_stage_kwargs,
        )
    else:
        locator = {
            "status": "NOT_REQUESTED",
            "matched_count": 0,
            "source_requests": 0,
            "request_id": None,
        }

    # --- Migration discovery (once at campaign start) -----------------------
    discovery_stage_kwargs: dict[str, Any] = {}
    if (
        stage_evidence_sink is not None
        or transport_identity_observer is not None
        or local_validation_identity_observer is not None
    ):
        discovery_stage_kwargs = {
            "campaign_id": campaign_id,
            "run_id": run_id,
            "cycle_id": cycle_id,
            "stage_sequence": 1,
        }
        if stage_evidence_sink is not None:
            discovery_stage_kwargs["stage_evidence_sink"] = stage_evidence_sink
        if transport_identity_observer is not None:
            discovery_stage_kwargs["transport_identity_observer"] = (
                transport_identity_observer
            )
        if local_validation_identity_observer is not None:
            discovery_stage_kwargs["local_validation_identity_observer"] = (
                local_validation_identity_observer
            )
    discovery = run_direct_migration_discovery(
        db_path,
        migration_transport=migration_transport,
        verifier_transport_factory=verifier_transport_factory,
        now=now,
        request_key_prefix=discovery_request_key_prefix,
        max_candidates=max_candidates,
        collection_rounds=collection_rounds,
        settle_seconds=settle_seconds,
        reverify_on_transient=reverify_on_transient,
        reverify_settle_seconds=reverify_settle_seconds,
        **discovery_stage_kwargs,
    )
    latest_mints = set(discovery.get("confirmed_this_cycle") or ())

    ops_used = int(locator.get("source_requests") or 0) + int(
        (discovery.get("source_operation_ledger") or {}).get("source_requests") or 0
    )
    # A terminal status is not an attributable failure fact. Count only exact
    # Source-Governor failure rows (or, where a stage has no durable row, a
    # separately proven transport identity). This prevents a single governed
    # failure from being counted again through the stage's summary label.
    provider_failure_facts: set[tuple[str, str, int | str]] = set()
    provider_failures = 0
    liquidity_stage_provider_failures = 0
    liquidity_outcome_counts: dict[str, int] = {}
    liquidity_failure_ids: set[int] = set()
    channels_attempted: list[str] = []
    channels_unavailable: list[str] = []
    if run_locator:
        channels_attempted.append("dexscreener_fresh_profiles_locator")
        if str(locator.get("status") or "").upper() not in {
            "OK",
            "NOT_REQUESTED",
            "SUCCESS",
        } and int(locator.get("source_requests") or 0) > 0:
            # Non-ok locator status with a request is treated as soft unavailability.
            if locator.get("status") not in (None, "ok", "OK"):
                pass
    channels_attempted.append("direct_pump_finalized_live_tail")
    channels_attempted.append("exact_pump_pumpswap_graduation_verify")
    channels_attempted.append(
        "dexscreener_mint_market_batch"
        if permanent_availability
        else "dexscreener_exact_pool_market"
    )

    evaluated_mints: set[str] = set()
    campaign_eligible: dict[str, dict[str, Any]] = {}
    all_candidates: list[dict[str, Any]] = []
    rejection_reasons: dict[str, int] = {}
    cooldown_skips = 0
    stale_exclusions = 0
    fresh_market_checks = 0
    duplicate_observations_removed = 0
    discovery_rounds = 0
    last_front_door: dict[str, Any] = {}
    last_stop_reason = "NOT_STARTED"
    inventory_known_at_start = 0
    tracking_dispositions: dict[str, dict[str, Any]] = {}
    permanent_market_reports: list[dict[str, Any]] = []
    stage_budget = StageBudget.permanent_discovery_default()
    protocol_stage_charged = False
    direct_protocol_confirmation_calls = 0
    protocol_confirmation_outcomes: list[dict[str, Any]] = []
    protocol_report: dict[str, Any] = {}
    work_queues: dict[str, list[dict[str, str]]] = {
        "MARKET_BATCHING_DUE": [],
        "RECONCILIATION_DUE": [],
        "PROTOCOL_CONFIRMATION_DUE": [],
        "HOLDER_SAFETY_DUE": [],
    }
    geckoterminal_nomination_report: dict[str, Any] = {
        "status": "NOT_REQUESTED",
        "source_requests": 0,
        "nominations": [],
        "local_exclusions": [],
    }
    liquidity_backup_report: dict[str, Any] = {
        "source_requests": 0,
        "attempts": [],
        "source_request_ids": [],
        "source_request_coverage": [],
        "outcomes": [],
    }
    live_geckoterminal_requests = 0

    def _pace_live_geckoterminal() -> None:
        nonlocal live_geckoterminal_requests
        if live_geckoterminal_requests > 0:
            import time

            time.sleep(6.0)
        live_geckoterminal_requests += 1

    connection = _connect(db_path)
    try:
        if permanent_availability:
            intake_before_gecko = int(locator.get("source_requests") or 0) + 1
            stage_budget.consume("intake", min(3, intake_before_gecko))
            locator_request_id = locator.get("request_id")
            if locator_request_id is not None:
                record_fresh_pool_nominations(
                    connection,
                    observations=locator.get("pool_observations") or (),
                    source="dexscreener",
                    request_id=int(locator_request_id),
                    now=now,
                    campaign_id=campaign_id,
                    response_id=(
                        None
                        if locator.get("response_id") is None
                        else int(locator["response_id"])
                    ),
                )
            if run_geckoterminal_nomination:
                stage_budget.consume("intake", 1)
                geckoterminal_nomination_report = run_geckoterminal_fresh_nomination(
                    connection,
                    request_key=f"{discovery_request_key_prefix}-gt-new-pools",
                    now=now,
                    campaign_id=campaign_id,
                    run_id=run_id,
                    cycle_id=cycle_id,
                    transport=geckoterminal_nomination_transport,
                    stage_evidence_sink=stage_evidence_sink,
                    transport_identity_observer=transport_identity_observer,
                )
                ops_used += int(
                    geckoterminal_nomination_report.get("source_requests") or 0
                )
                channels_attempted.append("geckoterminal_fresh_pool_nomination")
                if geckoterminal_nomination_transport is None:
                    live_geckoterminal_requests += 1

            # One bounded opposite-source backup for fresh LIQUIDITY_UNKNOWN
            # before protocol confirmation (no protocol without proven liquidity).
            if stage_budget.available("reconciliation") >= 1:
                from printer_v1.discovery.permanent_discovery_availability import (
                    run_bounded_unknown_liquidity_backup,
                )

                liquidity_backup_report = run_bounded_unknown_liquidity_backup(
                    connection,
                    stage_budget=stage_budget,
                    now=now,
                    campaign_id=campaign_id,
                    run_id=run_id,
                    cycle_id=cycle_id,
                    request_key_prefix=f"{discovery_request_key_prefix}-liq-backup",
                    geckoterminal_transport_factory=(
                        geckoterminal_reconciliation_transport_factory
                    ),
                    dexscreener_transport_factory=(
                        dexscreener_batch_transport_factory
                    ),
                    transport_identity_observer=transport_identity_observer,
                    stage_evidence_sink=stage_evidence_sink,
                )
                ops_used += int(liquidity_backup_report.get("source_requests") or 0)
            else:
                liquidity_backup_report = {
                    "source_requests": 0,
                    "attempts": [],
                    "source_request_ids": [],
                    "source_request_coverage": [],
                }

            # V2-9.8B: process above-floor protocol confirmation before market
            # batches consume residual promotion capacity. Confirmed rows promote
            # via retained unexpired liquidity without a second market request.
            if stage_budget.available("protocol_confirmation") >= 1:
                from printer_v1.discovery.permanent_discovery_availability import (
                    process_protocol_confirmation_queue as _early_protocol,
                )

                early_protocol = _early_protocol(
                    connection,
                    stage_budget=stage_budget,
                    now=now,
                    campaign_id=campaign_id,
                    run_id=run_id,
                    cycle_id=cycle_id,
                    account_batch_transport=protocol_account_batch_transport,
                    account_batch_transport_factory=(
                        protocol_account_batch_transport_factory
                    ),
                    stage_evidence_sink=stage_evidence_sink,
                    transport_identity_observer=transport_identity_observer,
                    local_validation_identity_observer=(
                        local_validation_identity_observer
                    ),
                    stage_sequence=1,
                    request_key_prefix=f"{discovery_request_key_prefix}-protocol",
                )
                protocol_report = early_protocol
                protocol_confirmation_outcomes = list(
                    early_protocol.get("outcomes") or ()
                )
                ops_used += int(early_protocol.get("source_requests") or 0)
                for promo in early_protocol.get("promoted_observation_eligible") or ():
                    mint = str(promo.get("mint") or "")
                    if not mint or mint in campaign_eligible:
                        continue
                    cand = _protocol_promotion_candidate(promo)
                    campaign_eligible[mint] = cand
                    evaluated_mints.add(mint)
                    all_candidates.append(cand)

        # Count locator and direct migration/verification failures only through
        # the exact Source-Governor request/failure lineage exposed by those
        # stages. Their terminal labels are deliberately not failure identities.
        locator_request_ids = (
            [int(locator["request_id"])]
            if locator.get("request_id") is not None
            else []
        )
        discovery_request_ids = [
            int(value)
            for value in (
                (discovery.get("source_operation_ledger") or {}).get(
                    "request_ids"
                )
                or ()
            )
        ]
        request_channels = {
            **{
                request_id: "dexscreener_fresh_profiles_locator"
                for request_id in locator_request_ids
            },
            **{
                request_id: "direct_pump_finalized_live_tail"
                for request_id in discovery_request_ids
            },
            **(
                {
                    int(geckoterminal_nomination_report["request_id"]):
                        "geckoterminal_fresh_pool_nomination"
                }
                if geckoterminal_nomination_report.get("request_id") is not None
                else {}
            ),
        }
        migration_evidence_rejections: list[dict[str, Any]] = []
        attributable_request_ids = sorted(request_channels)
        if attributable_request_ids:
            placeholders = ",".join("?" * len(attributable_request_ids))
            governed_failures = connection.execute(
                "SELECT f.id,f.failure_type,f.normalized_payload_json,"
                "r.id AS request_id,r.source_name,r.request_kind "
                "FROM printer_source_failures AS f "
                "JOIN printer_source_requests AS r ON r.id=f.source_request_id "
                f"WHERE r.id IN ({placeholders}) ORDER BY f.id",
                tuple(attributable_request_ids),
            ).fetchall()
            for failure in governed_failures:
                failure_type = str(failure["failure_type"] or "")
                if _is_candidate_local_migrate_failure(failure_type):
                    digest: dict[str, Any] = {}
                    raw_payload = failure["normalized_payload_json"]
                    if raw_payload:
                        try:
                            parsed = json.loads(raw_payload)
                        except (TypeError, ValueError, json.JSONDecodeError):
                            parsed = {}
                        if isinstance(parsed, dict):
                            candidate = parsed.get("migration_rejection_digest")
                            if isinstance(candidate, dict):
                                digest = dict(candidate)
                    migration_evidence_rejections.append(
                        {
                            "outcome": MIGRATION_EVIDENCE_REJECTED,
                            "failure_id": int(failure["id"]),
                            "request_id": int(failure["request_id"]),
                            "failure_type": failure_type,
                            "digest": digest,
                        }
                    )
                    # Candidate-local validation only — never shared channel death.
                    continue
                provider_failure_facts.add(
                    (
                        str(failure["source_name"]),
                        str(failure["request_kind"]),
                        int(failure["id"]),
                    )
                )
                channel = request_channels[int(failure["request_id"])]
                if (
                    str(failure["request_kind"])
                    == "pumpswap_signature_pool_resolution"
                ):
                    channel = "exact_pump_pumpswap_graduation_verify"
                if channel not in channels_unavailable:
                    channels_unavailable.append(channel)
        provider_failures = len(provider_failure_facts)

        inventory_rows = export_graduated_candidates(connection)
        if permanent_availability:
            inventory_rows = order_canonical_inventory_fairly(
                connection,
                inventory_rows=inventory_rows,
                latest_mints=tuple(latest_mints),
                fresh_mints=tuple(locator.get("matched_mints") or ()),
                now=now,
            )
        inventory_known_at_start = len(inventory_rows)
        inventory_mints = {str(r["mint_identity"]) for r in inventory_rows}

        # Load prior reserve and mark stale for mandatory revalidation.
        # Stale rows never count toward eligible capacity until revalidated.
        prior_reserve = load_eligible_reserve(
            connection, statuses=(ELIGIBLE_FRESH, ELIGIBLE_STALE)
        )
        for row in prior_reserve:
            mint = str(row["mint_identity"])
            mark_reserve_status(
                connection, mint, status=ELIGIBLE_STALE, now=now
            )

        # V2-9.8B selective-1h repair: do not spend exact-pool market work on
        # known identities that cannot possibly be claimed by this campaign.
        # Expired cooldown is only permission for fresh requalification, so it
        # remains in the evaluation walk and receives no stale-evidence credit.
        if tracking_precheck:
            from printer_v1.lifecycle.contracts import TokenLifecycleState
            from printer_v1.lifecycle.tracking_queue import (
                HANDOFF_COOLDOWN_REOPEN_REQUIRED,
                assess_tracking_handoff_by_identity,
            )

            prior_mints = {str(row["mint_identity"]) for row in prior_reserve}
            for inventory_row in inventory_rows:
                mint = str(inventory_row["mint_identity"])
                pool = str(inventory_row["pumpswap_pool"])
                assessment = assess_tracking_handoff_by_identity(
                    connection,
                    token_mint=mint,
                    pair_address=pool,
                    tracking_lane=TokenLifecycleState.TRACK_NORMAL,
                    assessed_at=started_at,
                )
                disposition = {
                    "category": assessment.category,
                    "eligible_for_evidence": assessment.eligible,
                    "tracking_queue_id": assessment.queue_id,
                    "tracking_queue_status": assessment.queue_status,
                    "requalification_required": (
                        assessment.requalification_eligible
                    ),
                    "cooldown_until": assessment.cooldown_until,
                    "historical_cooldown_expiry_derived": (
                        assessment.historical_cooldown_expiry_derived
                    ),
                }
                tracking_dispositions[mint] = disposition
                if assessment.eligible:
                    continue
                reason = str(assessment.reason_code or assessment.category)
                evaluated_mints.add(mint)
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                if reason == HANDOFF_COOLDOWN_REOPEN_REQUIRED:
                    cooldown_skips += 1
                all_candidates.append(
                    {
                        "mint": mint,
                        "pool": pool,
                        "pumpswap_pool": pool,
                        "market_identity": str(inventory_row["market_identity"]),
                        "provenance": str(
                            inventory_row.get("latest_channel")
                            or inventory_row.get("discovery_channel")
                            or "PERSISTED_GRADUATED"
                        ),
                        "lifecycle_state": str(inventory_row["lifecycle_state"]),
                        "graduation_block_time": inventory_row[
                            "graduation_block_time"
                        ],
                        "liquidity": {},
                        "liquidity_usd": None,
                        "liquidity_status": LIQUIDITY_UNPROVEN,
                        "eligible": False,
                        "rejection": reason,
                        "current_eligibility_status": EXCLUDED,
                        "excluded_before_market_source": True,
                        "tracking_handoff": disposition,
                        "source_path": "zero_source_tracking_precheck",
                    }
                )
                if mint in prior_mints:
                    mark_reserve_status(
                        connection,
                        mint,
                        status=EXCLUDED,
                        now=now,
                        exclusion_reason=reason,
                    )
        connection.commit()

        def _ops_remaining() -> int:
            return max(0, int(discovery_operation_budget) - ops_used)

        def _duration_remaining() -> float | None:
            # Real monotonic wall-clock deadline — never compare only to frozen start.
            if deadline_dt is None:
                return None
            return (deadline_dt - _parse_iso(_utc_now_iso())).total_seconds()

        def _unexplored() -> set[str]:
            return inventory_mints - evaluated_mints

        # Prefer revalidating prior reserve members first (freshness gate).
        revalidate_mints = {
            str(r["mint_identity"]) for r in prior_reserve
        } & inventory_mints
        revalidation_focus_pending = bool(revalidate_mints)
        # Durable last-successful evidence by mint. Seeded from the prior
        # reserve and extended with post-wait retained candidates so a retained
        # candidate that fails revalidation is removed truthfully.
        prior_by_mint: dict[str, Mapping[str, Any]] = {
            str(row["mint_identity"]): row for row in prior_reserve
        }

        max_rounds = max(
            1,
            (len(inventory_mints) // max(1, front_door_max_candidates)) + 3,
        )

        # --- bounded pre-lifecycle temporal acquisition (design §§2,6,7) ----
        acquisition_ledger: AcquisitionLedger | None = None
        if temporal_refresh_owner is not None:
            acquisition_ledger = AcquisitionLedger(
                started_at=now,
                acquisition_deadline_at=str(
                    deadline_at
                    or _utc_now_iso()
                ),
                acquisition_duration_seconds=(
                    PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS
                ),
                refresh_interval_seconds=int(
                    getattr(temporal_refresh_owner, "refresh_interval_seconds", 600)
                ),
            )

        def _temporal_stop_reason(status: str) -> str:
            """Map one owner outcome onto the fail-closed terminal precedence."""
            return {
                TEMPORAL_SUPERVISION_FAILED: "CAMPAIGN_SUPERVISION_FAILED",
                TEMPORAL_CANCELLED: "OPERATOR_SAFE_STOP_REQUESTED",
                UNSAFE_SCHEDULER_STATE: "UNSAFE_SCHEDULER_OWNERSHIP_STATE",
                REFRESH_SOURCE_FAILURE: "SOURCE_AVAILABILITY_FAILURE_DURING_REFRESH",
                TEMPORAL_SOURCE_BUDGET_EXHAUSTED: (
                    "DISCOVERY_OPERATION_BUDGET_EXHAUSTED"
                ),
                ACQUISITION_DEADLINE_EXHAUSTED: (
                    PRE_LIFECYCLE_ACQUISITION_DURATION_EXHAUSTED
                ),
                NO_LAWFUL_REFRESH_WINDOW: (
                    PRE_LIFECYCLE_ACQUISITION_DURATION_EXHAUSTED
                ),
            }.get(status, status)

        def _request_temporal_refresh(universe_state: str) -> bool:
            """Ask the orchestration owner for one lawful refresh opportunity.

            Returns ``True`` only when a claimed refresh completed and the loop
            may lawfully continue. Never calls a provider, the Scheduler, or a
            timer directly; never resets the cumulative discovery budget.
            """
            nonlocal ops_used, last_stop_reason, max_rounds
            nonlocal provider_failures, revalidation_focus_pending
            nonlocal inventory_rows, inventory_mints
            if temporal_refresh_owner is None or acquisition_ledger is None:
                last_stop_reason = universe_state
                return False
            depth_before = len(campaign_eligible)
            outcome = temporal_refresh_owner.request_temporal_refresh(
                reserve_depth=depth_before,
                required_capacity=int(required_token_capacity),
                universe_state=universe_state,
                source_operations_remaining=_ops_remaining(),
                provider_terminal_failure=bool(channels_unavailable),
                now=_utc_now_iso(),
            )
            if not isinstance(outcome, TemporalRefreshOutcome):
                last_stop_reason = UNSAFE_SCHEDULER_STATE
                return False
            acquisition_ledger.record(outcome)
            # Cumulative accounting: refresh operations are added to the same
            # invocation's usage. The budget is never reset after waiting.
            ops_used += int(outcome.source_operations)
            # Provider failures are recorded as exact facts, not as a running
            # tally: the canonical recount below is the single authority and
            # would otherwise overwrite a plain increment.
            for index in range(int(outcome.provider_failures)):
                provider_failure_facts.add(
                    (
                        "pre_lifecycle_temporal_refresh",
                        str(outcome.wait_id or "unknown-wait"),
                        f"refresh-{outcome.refresh_ordinal}-{index}",
                    )
                )
            provider_failures = len(provider_failure_facts)
            for channel in outcome.channels_unavailable:
                if channel not in channels_unavailable:
                    channels_unavailable.append(channel)

            if outcome.status == WAITING_FOR_ELIGIBLE_SUPPLY:
                # Nonterminal: the wait is durably owned and published. The
                # loop stops here without a shortage terminal.
                last_stop_reason = WAITING_FOR_ELIGIBLE_SUPPLY
                return False
            if outcome.status != REFRESH_COMPLETED:
                last_stop_reason = _temporal_stop_reason(outcome.status)
                return False

            # Design §7 — nothing retained may count until it is revalidated.
            retained = sorted(campaign_eligible)
            for mint in retained:
                prior_by_mint.setdefault(mint, dict(campaign_eligible[mint]))
                mark_reserve_status(
                    connection,
                    mint,
                    status=ELIGIBLE_STALE,
                    now=now,
                    exclusion_reason=None,
                )
                evaluated_mints.discard(mint)
                del campaign_eligible[mint]
            acquisition_ledger.revalidation_outcomes.append(
                {
                    "refresh_ordinal": outcome.refresh_ordinal,
                    "retained_candidates_marked_stale": list(retained),
                    "reserve_depth_before_revalidation": depth_before,
                }
            )
            revalidate_mints.clear()
            revalidate_mints.update(retained)
            revalidation_focus_pending = bool(retained)
            connection.commit()

            # Newly reachable identities become visible two lawful ways, both
            # owned by their existing owners: through the canonical graduated
            # inventory, and through the protocol-confirmation owner's retained
            # liquidity promotions. No old rejected candidate is relabelled as
            # new, and no new gate is applied to either route.
            for promo in outcome.promoted_observation_eligible:
                mint = str(promo.get("mint") or "")
                if not mint or mint in campaign_eligible:
                    continue
                if mint in retained:
                    # A retained candidate must revalidate through the front
                    # door; a refresh promotion never restores it silently.
                    continue
                # Admitted through exactly the campaign-start promotion path.
                # It deliberately does not write the durable eligible reserve:
                # that persistence belongs to the front-door admission owner,
                # and a protocol promotion has no graduated-registry row to
                # reference. Mirroring the existing path is what keeps a second
                # admission gate from drifting into existence here.
                cand = _protocol_promotion_candidate(promo)
                campaign_eligible[mint] = cand
                evaluated_mints.add(mint)
                all_candidates.append(cand)
            connection.commit()

            inventory_rows = export_graduated_candidates(connection)
            inventory_mints = {str(r["mint_identity"]) for r in inventory_rows}
            remaining = len(inventory_mints - evaluated_mints)
            max_rounds = discovery_rounds + max(
                1, (remaining // max(1, front_door_max_candidates)) + 3
            )
            return True

        while len(campaign_eligible) < required_token_capacity:
            if discovery_rounds >= max_rounds:
                if _request_temporal_refresh("ALL_REACHABLE_CANDIDATES_EVALUATED"):
                    continue
                break
            if _ops_remaining() <= 0:
                last_stop_reason = "DISCOVERY_OPERATION_BUDGET_EXHAUSTED"
                break
            dur_rem = _duration_remaining()
            if dur_rem is not None and dur_rem <= 0:
                last_stop_reason = "CAMPAIGN_DURATION_EXHAUSTED"
                break

            unexplored = _unexplored()
            # Build exclude set: already evaluated this campaign.
            # For the first pass after prior-reserve load, allow revalidation of
            # stale reserve mints even if not yet in evaluated set.
            if revalidation_focus_pending and revalidate_mints:
                batch_focus = revalidate_mints - evaluated_mints
            else:
                batch_focus = set()

            if not unexplored and not batch_focus:
                if _request_temporal_refresh(
                    "NO_ADDITIONAL_UNIQUE_CANDIDATES_REACHABLE"
                ):
                    continue
                break

            # Cap the evaluation batch by remaining discovery ops so a round
            # cannot overshoot the governed discovery budget (worst case every
            # candidate needs one exact-pool market call).
            batch_size = min(int(front_door_max_candidates), int(_ops_remaining()))
            if batch_size <= 0:
                last_stop_reason = "DISCOVERY_OPERATION_BUDGET_EXHAUSTED"
                break

            # exclude everything already evaluated; front door will pick up to
            # batch_size from the remainder.
            exclude = set(evaluated_mints)
            # When focusing revalidation, also exclude non-focus unexplored so the
            # batch prioritizes stale reserve first (deterministic completeness).
            if batch_focus:
                exclude |= inventory_mints - batch_focus - evaluated_mints

            discovery_rounds += 1
            round_seed = f"{cycle_seed}|ROUND_{discovery_rounds}"
            front_door_stage_kwargs: dict[str, Any] = {}
            if stage_evidence_sink is not None or transport_identity_observer is not None:
                front_door_stage_kwargs = {
                    "campaign_id": campaign_id,
                    "run_id": run_id,
                    "cycle_id": cycle_id,
                    "discovery_round": discovery_rounds,
                }
                if stage_evidence_sink is not None:
                    front_door_stage_kwargs["stage_evidence_sink"] = stage_evidence_sink
                if transport_identity_observer is not None:
                    front_door_stage_kwargs["transport_identity_observer"] = (
                        transport_identity_observer
                    )
            if permanent_availability:
                # The exact-state owner itself applies due/no-match suppression.
                # The traversal here remains the existing canonical graduated
                # inventory; rows excluded by tracking are never sent to market.
                permanent_rows = [
                    row
                    for row in inventory_rows
                    if str(row["mint_identity"]) not in evaluated_mints
                ][:30]
                if not permanent_rows:
                    if _request_temporal_refresh(
                        "ALL_REACHABLE_CANDIDATES_EVALUATED"
                    ):
                        continue
                    break
                # Charge migration protocol ops once, without sealing market.
                # Protocol and market stages may both be open; residual market
                # capacity is not stranded by protocol accounting.
                if not protocol_stage_charged:
                    coverage = discovery.get("source_request_coverage") or ()
                    protocol_calls = sum(
                        1
                        for row in coverage
                        if isinstance(row, Mapping)
                        and str(row.get("source_name") or "") == "pumpswap"
                        and str(row.get("request_kind") or "")
                        == "pumpswap_signature_pool_resolution"
                        and "DIRECT_MIGRATION_VERIFY"
                        in str(row.get("logical_stage_id") or "")
                    )
                    direct_protocol_confirmation_calls = protocol_calls
                    if protocol_calls:
                        try:
                            stage_budget.consume(
                                "protocol_confirmation", protocol_calls
                            )
                        except ValueError:
                            last_stop_reason = "DISCOVERY_OPERATION_BUDGET_EXHAUSTED"
                            break
                    protocol_stage_charged = True
                if stage_budget.available("market_batching") < 1:
                    # Seal market only when no capacity remains for another batch.
                    if not stage_budget.is_sealed("market_batching"):
                        stage_budget.seal("market_batching")
                    last_stop_reason = "DISCOVERY_OPERATION_BUDGET_EXHAUSTED"
                    break
                try:
                    stage_budget.consume("market_batching", 1)
                except ValueError:
                    last_stop_reason = "DISCOVERY_OPERATION_BUDGET_EXHAUSTED"
                    break
                from printer_v1.discovery.permanent_discovery_availability import (
                    build_mint_market_batch_request_key,
                    next_mint_market_batch_stage_sequence,
                )

                # Durable sequence at logical batch creation (request key + seal).
                market_stage_sequence = next_mint_market_batch_stage_sequence(
                    connection,
                    request_key_prefix=str(front_door_request_key_prefix),
                )
                market_request_key = build_mint_market_batch_request_key(
                    request_key_prefix=str(front_door_request_key_prefix),
                    stage_sequence=market_stage_sequence,
                    kind="round",
                )
                reconciliation_offer = stage_budget.available("reconciliation")
                permanent_report = run_dexscreener_batch_market_resolution(
                    connection,
                    inventory_rows=permanent_rows,
                    transport_factory=dexscreener_batch_transport_factory,
                    geckoterminal_transport_factory=(
                        geckoterminal_reconciliation_transport_factory
                    ),
                    enable_geckoterminal_fallback=(
                        enable_geckoterminal_reconciliation
                    ),
                    max_geckoterminal_fallbacks=reconciliation_offer,
                    before_geckoterminal_request=(
                        (lambda: _pace_live_geckoterminal())
                        if geckoterminal_reconciliation_transport_factory is None
                        else None
                    ),
                    request_key=market_request_key,
                    now=now,
                    campaign_id=campaign_id,
                    recent_request_count=fresh_market_checks,
                    run_id=run_id,
                    cycle_id=cycle_id,
                    stage_evidence_sink=stage_evidence_sink,
                    transport_identity_observer=transport_identity_observer,
                    stage_sequence=market_stage_sequence,
                )
                permanent_market_reports.append(permanent_report)
                reconciliation_calls = _validate_reconciliation_stage_charge(
                    offered=reconciliation_offer,
                    actual=int(permanent_report.get("calls_by_stage", {}).get("reconciliation", 0)),
                )
                if reconciliation_calls:
                    stage_budget.consume("reconciliation", reconciliation_calls)
                front_door = {
                    "candidates": permanent_report["candidates"],
                    "market_calls": int(
                        permanent_report.get("source_request_count")
                        or len(permanent_report["source_request_ids"])
                    ),
                    "cooldown_skip_count": 0,
                }
            else:
                front_door = run_graduated_liquidity_front_door(
                    db_path,
                    cycle_seed=round_seed,
                    latest_mints=latest_mints,
                    dexscreener_transport_factory=dexscreener_transport_factory,
                    now=now,
                    batch_seq=batch_seq,
                    request_key_prefix=(
                        f"{front_door_request_key_prefix}-r{discovery_rounds}"
                    ),
                    max_candidates=batch_size,
                    exclude_mints=exclude,
                    **front_door_stage_kwargs,
                )
            last_front_door = front_door
            market_calls = int(front_door.get("market_calls") or 0)
            fresh_market_checks += market_calls
            ops_used += market_calls
            cooldown_skips += int(front_door.get("cooldown_skip_count") or 0)

            batch_candidates = [
                _candidate_from_front_door_item(c)
                for c in (front_door.get("candidates") or [])
            ]
            direct_by_mint = {
                str(item.get("mint") or ""): dict(item)
                for item in (discovery.get("candidate_mix") or ())
                if isinstance(item, Mapping)
            }
            for candidate in batch_candidates:
                direct = direct_by_mint.get(str(candidate.get("mint") or ""))
                if direct is None:
                    continue
                candidate["retained_evidence"] = dict(
                    direct.get("retained_evidence") or {}
                )
                carried_direct = direct.get("direct_pump_evidence")
                if isinstance(carried_direct, Mapping):
                    candidate["direct_pump_evidence"] = dict(carried_direct)
                candidate["admission_authority"] = "DIRECT_PUMP_PUMPSWAP"
                candidate["nomination_source"] = "direct_pump_migration"
                candidate["lineage_state"] = "PUMP_GRADUATION_CONFIRMED"
                candidate["exact_present_pool_confirmed"] = True
            for candidate in batch_candidates:
                disposition = tracking_dispositions.get(str(candidate["mint"]))
                if disposition is not None:
                    candidate["tracking_handoff"] = dict(disposition)
                    candidate["tracking_requalification_required"] = bool(
                        disposition.get("requalification_required")
                    )
            for candidate in batch_candidates:
                liquidity = candidate.get("liquidity")
                if not isinstance(liquidity, Mapping):
                    continue
                category = str(liquidity.get("outcome_category") or "UNKNOWN")
                liquidity_outcome_counts[category] = (
                    liquidity_outcome_counts.get(category, 0) + 1
                )
                failure_id = liquidity.get("source_failure_id")
                if failure_id is not None:
                    exact_failure_id = int(failure_id)
                    liquidity_failure_ids.add(exact_failure_id)
                    failure_owner = connection.execute(
                        "SELECT r.source_name,r.request_kind "
                        "FROM printer_source_failures AS f "
                        "JOIN printer_source_requests AS r "
                        "ON r.id=f.source_request_id WHERE f.id=?",
                        (exact_failure_id,),
                    ).fetchone()
                    if failure_owner is None:
                        raise EligibleTokenSupplyError(
                            "SOURCE_FAILURE_LINEAGE_MISSING:"
                            f"{exact_failure_id}"
                        )
                    provider_failure_facts.add(
                        (
                            str(failure_owner["source_name"]),
                            str(failure_owner["request_kind"]),
                            exact_failure_id,
                        )
                    )
            liquidity_stage_provider_failures = len(liquidity_failure_ids)
            provider_failures = len(provider_failure_facts)
            if any(
                liquidity_outcome_counts.get(category, 0) > 0
                for category in (
                    LIQUIDITY_SOURCE_UNAVAILABLE,
                    LIQUIDITY_SOURCE_RATE_LIMITED_OR_STALE,
                    LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL,
                )
            ):
                market_channel = (
                    "dexscreener_mint_market_batch"
                    if permanent_availability
                    else "dexscreener_exact_pool_market"
                )
                if market_channel not in channels_unavailable:
                    channels_unavailable.append(market_channel)
            if not batch_candidates and not unexplored:
                if _request_temporal_refresh(
                    "NO_ADDITIONAL_UNIQUE_CANDIDATES_REACHABLE"
                ):
                    continue
                break
            if not batch_candidates:
                # Exclude set may have over-constrained revalidation focus; clear
                # focus and continue with pure unexplored walk.
                if batch_focus:
                    revalidate_mints.clear()
                    revalidation_focus_pending = False
                    continue
                if _request_temporal_refresh(
                    "NO_ADDITIONAL_UNIQUE_CANDIDATES_REACHABLE"
                ):
                    continue
                break

            round_seen: set[str] = set()
            for cand in batch_candidates:
                mint = cand["mint"]
                if not mint:
                    continue
                if mint in evaluated_mints:
                    duplicate_observations_removed += 1
                    continue
                if mint in round_seen:
                    duplicate_observations_removed += 1
                    continue
                round_seen.add(mint)
                evaluated_mints.add(mint)
                all_candidates.append(cand)

                if cand.get("eligible"):
                    campaign_eligible[mint] = cand
                    upsert_eligible_reserve(
                        connection,
                        mint=mint,
                        pumpswap_pool=str(cand["pumpswap_pool"]),
                        market_identity=str(cand["market_identity"]),
                        provenance=str(cand["provenance"]),
                        liquidity_usd=(
                            None
                            if cand.get("liquidity_usd") is None
                            else float(cand["liquidity_usd"])
                        ),
                        liquidity_status=str(cand["liquidity_status"]),
                        eligibility_status=ELIGIBLE_FRESH,
                        last_validated_at=now,
                        source_provenance=str(cand.get("source_path") or ""),
                        last_campaign_id=campaign_id,
                    )
                else:
                    reason = _candidate_rejection_reason(cand)
                    rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                    # If a previously eligible reserve mint fails revalidation,
                    # remove it from capacity and durable fresh status.
                    if mint in campaign_eligible:
                        del campaign_eligible[mint]
                    prior = prior_by_mint.get(mint)
                    if prior is not None:
                        cand["historical_reserve_evidence"] = {
                            "liquidity_usd": prior.get("liquidity_usd"),
                            "liquidity_status": prior.get("liquidity_status"),
                            "last_validated_at": prior.get("last_validated_at"),
                            "source_provenance": prior.get("source_provenance"),
                            "last_campaign_id": prior.get("last_campaign_id"),
                            "evidence_role": "HISTORICAL_LAST_SUCCESSFUL_ONLY",
                            "admitted_as_current": False,
                        }
                        cand["current_eligibility_status"] = REMOVED
                        mark_reserve_status(
                            connection,
                            mint,
                            status=REMOVED,
                            now=now,
                            exclusion_reason=reason,
                        )
                        stale_exclusions += 1

            connection.commit()

            if len(campaign_eligible) >= required_token_capacity:
                last_stop_reason = "ELIGIBLE_CAPACITY_MET"
                break

            # After first revalidation pass, clear focus so remaining unexplored
            # inventory is walked in subsequent rounds.
            revalidate_mints.clear()
            revalidation_focus_pending = False

            # If batch returned only already-evaluated or empty net progress and
            # no unexplored left, stop — unless a lawful future refresh remains.
            if not _unexplored():
                if _request_temporal_refresh("ALL_REACHABLE_CANDIDATES_EVALUATED"):
                    continue
                break

        # Refresh inventory size after discovery (new confirms).
        inventory_rows = export_graduated_candidates(connection)
        inventory_mints = {str(r["mint_identity"]) for r in inventory_rows}
        pools_confirmed = len(inventory_mints)
        unexplored_remaining = len(inventory_mints - evaluated_mints)

        if permanent_availability:
            from printer_v1.discovery.permanent_discovery_availability import (
                process_protocol_confirmation_queue,
            )

            # Seal market/recon when no further batch capacity remains so any
            # residual may flow into protocol processing only after seal.
            if stage_budget.available("market_batching") < 1 and not stage_budget.is_sealed(
                "market_batching"
            ):
                stage_budget.seal("market_batching")
            if stage_budget.available("reconciliation") < 1 and not stage_budget.is_sealed(
                "reconciliation"
            ):
                stage_budget.seal("reconciliation")
            # Residual protocol due only (early pass may have already run).
            residual_protocol = process_protocol_confirmation_queue(
                connection,
                stage_budget=stage_budget,
                now=now,
                campaign_id=campaign_id,
                run_id=run_id,
                cycle_id=cycle_id,
                account_batch_transport=protocol_account_batch_transport,
                account_batch_transport_factory=(
                    protocol_account_batch_transport_factory
                ),
                stage_evidence_sink=stage_evidence_sink,
                transport_identity_observer=transport_identity_observer,
                local_validation_identity_observer=(
                    local_validation_identity_observer
                ),
                stage_sequence=2,
                request_key_prefix=f"{discovery_request_key_prefix}-protocol-residual",
            )
            # Deterministic merge of protocol sequence 1 and 2.
            from printer_v1.discovery.permanent_discovery_availability import (
                merge_protocol_confirmation_reports,
                union_market_revalidation_candidates,
            )

            protocol_report = merge_protocol_confirmation_reports(
                protocol_report, residual_protocol
            )
            protocol_confirmation_outcomes = list(
                protocol_report.get("outcomes") or ()
            )
            work_queues["PROTOCOL_CONFIRMATION_DUE"] = list(
                protocol_report.get("remaining_due") or ()
            )
            ops_used += int(residual_protocol.get("source_requests") or 0)
            for promo in residual_protocol.get("promoted_observation_eligible") or ():
                mint = str(promo.get("mint") or "")
                if not mint or mint in campaign_eligible:
                    continue
                cand = {
                    **dict(promo),
                    "mint": mint,
                    "pool": str(promo.get("pool") or ""),
                    "pumpswap_pool": str(promo.get("pool") or ""),
                    "market_identity": str(
                        promo.get("market_identity")
                        or f"solana-mainnet:pumpswap:{promo.get('pool')}"
                    ),
                    "provenance": "FRESH_AGGREGATOR_PROTOCOL_CONFIRMED",
                    "liquidity_usd": promo.get("liquidity_usd"),
                    "liquidity_status": "LIQUIDITY_PROVEN",
                    "liquidity": dict(promo.get("liquidity") or {}),
                    "evidence_expires_at": promo.get("evidence_expires_at"),
                    "eligible": True,
                    "rejection": None,
                    "memory_observation_eligible": True,
                    "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
                    "source_path": "retained_liquidity_protocol_promotion",
                }
                campaign_eligible[mint] = cand
                evaluated_mints.add(mint)
                all_candidates.append(cand)
            # Only rows that could not promote via retained evidence re-enter
            # market validation when capacity remains (never invent liquidity).
            # Preserve both early and residual revalidation candidates.
            confirmed_for_market = union_market_revalidation_candidates(
                protocol_report.get("requires_market_revalidation"),
            )
            if (
                confirmed_for_market
                and stage_budget.available("market_batching") >= 1
                and dexscreener_batch_transport_factory is not None
            ):
                from printer_v1.sources.pumpswap import PUMPSWAP_AMM_PROGRAM_ID as _PAM

                resume_rows = [
                    {
                        "mint_identity": str(item["mint"]),
                        "pumpswap_pool": str(item["pool"]),
                        "market_identity": (
                            f"solana-mainnet:pumpswap:{item['pool']}"
                        ),
                        "lifecycle_state": "PUMPSWAP_PROTOCOL_CONFIRMED",
                        "graduation_block_time": None,
                        "pumpswap_program_id": _PAM,
                        "latest_channel": "PROTOCOL_CONFIRMED",
                    }
                    for item in confirmed_for_market
                ]
                try:
                    stage_budget.consume("market_batching", 1)
                except ValueError:
                    resume_rows = []
                if resume_rows:
                    from printer_v1.discovery.permanent_discovery_availability import (
                        build_mint_market_batch_request_key,
                        next_mint_market_batch_stage_sequence,
                    )

                    # Continue monotonic market-batch sequence after protocol work.
                    resume_stage_sequence = next_mint_market_batch_stage_sequence(
                        connection,
                        request_key_prefix=str(front_door_request_key_prefix),
                    )
                    resume_request_key = build_mint_market_batch_request_key(
                        request_key_prefix=str(front_door_request_key_prefix),
                        stage_sequence=resume_stage_sequence,
                        kind="protocol_resume",
                    )
                    resume_report = run_dexscreener_batch_market_resolution(
                        connection,
                        inventory_rows=resume_rows,
                        transport_factory=dexscreener_batch_transport_factory,
                        geckoterminal_transport_factory=None,
                        enable_geckoterminal_fallback=False,
                        request_key=resume_request_key,
                        now=now,
                        campaign_id=campaign_id,
                        recent_request_count=fresh_market_checks,
                        run_id=run_id,
                        cycle_id=cycle_id,
                        stage_evidence_sink=stage_evidence_sink,
                        transport_identity_observer=transport_identity_observer,
                        stage_sequence=resume_stage_sequence,
                    )
                    permanent_market_reports.append(resume_report)
                    market_calls = int(
                        resume_report.get("source_request_count")
                        or len(resume_report.get("source_request_ids") or ())
                    )
                    fresh_market_checks += market_calls
                    ops_used += market_calls
                    for cand in resume_report.get("candidates") or ():
                        if not cand.get("eligible"):
                            continue
                        mint = str(cand.get("mint") or "")
                        if not mint or mint in campaign_eligible:
                            continue
                        campaign_eligible[mint] = _candidate_from_front_door_item(
                            cand
                        )
                        evaluated_mints.add(mint)
                        all_candidates.append(campaign_eligible[mint])
                        upsert_eligible_reserve(
                            connection,
                            mint=mint,
                            pumpswap_pool=str(
                                cand.get("pumpswap_pool") or cand.get("pool") or ""
                            ),
                            market_identity=str(cand.get("market_identity") or ""),
                            provenance=str(
                                cand.get("provenance") or "PROTOCOL_CONFIRMED"
                            ),
                            liquidity_usd=(
                                None
                                if cand.get("liquidity_usd") is None
                                else float(cand["liquidity_usd"])
                            ),
                            liquidity_status=str(
                                cand.get("liquidity_status") or LIQUIDITY_PROVEN
                            ),
                            eligibility_status=ELIGIBLE_FRESH,
                            last_validated_at=now,
                            source_provenance="protocol_confirmed_market_resume",
                            last_campaign_id=campaign_id,
                        )
                    connection.commit()
            if not stage_budget.is_sealed("protocol_confirmation"):
                if stage_budget.available("protocol_confirmation") < 1 or not (
                    protocol_report.get("remaining_due")
                ):
                    stage_budget.seal("protocol_confirmation")

        eligible_list = list(campaign_eligible.values())
        # Deterministic non-ranked order by mint identity for handoff stability.
        eligible_list.sort(key=lambda c: str(c["mint"]))
        if permanent_availability:
            work_queues["HOLDER_SAFETY_DUE"] = [
                {
                    "mint": str(item.get("mint") or ""),
                    "pool": str(
                        item.get("pumpswap_pool") or item.get("pool") or ""
                    ),
                }
                for item in eligible_list
            ]
            work_queues["MARKET_BATCHING_DUE"] = [
                {"mint": mint, "pool": ""}
                for mint in sorted(inventory_mints - evaluated_mints)
            ]

        ready = len(eligible_list) >= required_token_capacity
        certificate: ExhaustionCertificate | None = None
        shortage: str | None = None

        duration_used = (_parse_iso(now) - started_at).total_seconds()
        duration_remaining = _duration_remaining()

        if ready:
            terminal = GRADUATED_SUPPLY_READY
            last_stop_reason = "ELIGIBLE_CAPACITY_MET"
        elif last_stop_reason == WAITING_FOR_ELIGIBLE_SUPPLY:
            # Design §8.6 — current-universe exhaustion with a lawful, durably
            # owned future refresh is a nonterminal acquisition state. No
            # shortage classification and no exhaustion certificate is emitted,
            # because no shortage has been proven.
            terminal = WAITING_FOR_ELIGIBLE_SUPPLY
        else:
            terminal = BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL
            all_channels_exhausted = (
                unexplored_remaining == 0
                and last_stop_reason
                in {
                    "ALL_REACHABLE_CANDIDATES_EVALUATED",
                    "NO_ADDITIONAL_UNIQUE_CANDIDATES_REACHABLE",
                }
            )
            # Budget exhaustion is legal only when flat or stage capacity that
            # could execute remaining queued work is actually gone.
            executable_stage_capacity = 0
            if permanent_availability:
                for stage_name in (
                    "market_batching",
                    "reconciliation",
                    "protocol_confirmation",
                ):
                    if not stage_budget.is_sealed(stage_name):
                        executable_stage_capacity += stage_budget.available(
                            stage_name
                        )
            true_flat_exhausted = _ops_remaining() <= 0
            true_stage_exhausted = (
                permanent_availability
                and executable_stage_capacity <= 0
                and last_stop_reason == "DISCOVERY_OPERATION_BUDGET_EXHAUSTED"
            )
            if (
                last_stop_reason == "DISCOVERY_OPERATION_BUDGET_EXHAUSTED"
                and not true_flat_exhausted
                and not true_stage_exhausted
                and unexplored_remaining > 0
            ):
                # Do not emit false budget exhaustion while capacity remains.
                last_stop_reason = "LAWFUL_WORK_REMAINING_WITH_CAPACITY"
            unexplored_prevented = last_stop_reason in {
                "DISCOVERY_OPERATION_BUDGET_EXHAUSTED",
                "CAMPAIGN_DURATION_EXHAUSTED",
            } and unexplored_remaining > 0
            shortage = classify_shortage(
                provider_failures=provider_failures,
                channels_unavailable=sorted(set(channels_unavailable)),
                duration_remaining_seconds=duration_remaining,
                source_operations_remaining=_ops_remaining(),
                unexplored_unique_remaining=unexplored_remaining,
                eligible_count=len(eligible_list),
                unique_tokens_observed=len(evaluated_mints),
                discovery_rounds=discovery_rounds,
                evaluation_batch_size=front_door_max_candidates,
                all_channels_exhausted=all_channels_exhausted,
                liquidity_source_unavailable=liquidity_outcome_counts.get(
                    LIQUIDITY_SOURCE_UNAVAILABLE, 0
                ),
                liquidity_stale_or_rate_limited=liquidity_outcome_counts.get(
                    LIQUIDITY_SOURCE_RATE_LIMITED_OR_STALE, 0
                ),
                liquidity_malformed_or_partial=liquidity_outcome_counts.get(
                    LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL, 0
                ),
            )
            shortage = _apply_permanent_shortage_precedence(
                shortage=shortage,
                last_stop_reason=last_stop_reason,
                tracking_dispositions=tracking_dispositions,
                provider_failures=provider_failures,
                channels_unavailable=sorted(set(channels_unavailable)),
                liquidity_source_unavailable=liquidity_outcome_counts.get(LIQUIDITY_SOURCE_UNAVAILABLE, 0),
                liquidity_stale_or_rate_limited=liquidity_outcome_counts.get(LIQUIDITY_SOURCE_RATE_LIMITED_OR_STALE, 0),
                liquidity_malformed_or_partial=liquidity_outcome_counts.get(LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL, 0),
                true_budget_exhausted=bool(true_flat_exhausted or true_stage_exhausted),
                duration_exhausted=bool(
                    last_stop_reason == "CAMPAIGN_DURATION_EXHAUSTED"
                    or (duration_remaining is not None and duration_remaining <= 0)
                ),
            )
            if acquisition_ledger is not None:
                # Design §8 — controlling temporal terminals override the
                # instantaneous-universe classification, fail-closed and in
                # order. A closed acquisition horizon is duration exhaustion,
                # never "true market supply shortage".
                if last_stop_reason == PRE_LIFECYCLE_ACQUISITION_DURATION_EXHAUSTED:
                    shortage = DURATION_EXHAUSTION
                elif last_stop_reason == "SOURCE_AVAILABILITY_FAILURE_DURING_REFRESH":
                    shortage = SOURCE_AVAILABILITY_FAILURE
                elif (
                    shortage == TRUE_MARKET_SUPPLY_SHORTAGE
                    and acquisition_ledger.remaining_seconds(_utc_now_iso()) > 0
                    and acquisition_ledger.opportunities_scheduled > 0
                ):
                    # One instantaneous universe exhaustion inside a live
                    # horizon is never a proven true market shortage.
                    shortage = DURATION_EXHAUSTION
                acquisition_ledger.controlling_shortage_classification = shortage
            certificate = ExhaustionCertificate(
                certificate_id=(
                    f"exh-{execution_id or campaign_id or uuid.uuid4().hex[:12]}"
                ),
                campaign_id=campaign_id,
                execution_id=execution_id,
                run_id=run_id,
                cycle_id=cycle_id,
                required_eligible_capacity=required_token_capacity,
                eligible_reserve_count=len(eligible_list),
                approved_discovery_channels_attempted=channels_attempted,
                channels_unavailable=channels_unavailable,
                unique_tokens_observed=len(evaluated_mints),
                duplicate_observations_removed=duplicate_observations_removed,
                tokens_already_known_from_inventory=inventory_known_at_start,
                pools_confirmed=pools_confirmed,
                fresh_market_checks=fresh_market_checks,
                eligible_count=len(eligible_list),
                rejected_count=sum(1 for c in all_candidates if not c.get("eligible")),
                rejection_reasons=dict(rejection_reasons),
                cooldown_skips=cooldown_skips,
                stale_evidence_exclusions=stale_exclusions,
                provider_failures=provider_failures,
                liquidity_stage_provider_failures=(
                    liquidity_stage_provider_failures
                ),
                liquidity_outcome_counts=dict(liquidity_outcome_counts),
                candidate_liquidity_lineage=[
                    _candidate_liquidity_lineage(candidate)
                    for candidate in all_candidates
                ],
                source_operations_used=ops_used,
                source_operations_remaining=_ops_remaining(),
                duration_used_seconds=duration_used,
                duration_remaining_seconds=duration_remaining,
                unexplored_work_prevented_by_hard_ceiling=unexplored_prevented,
                last_reason_discovery_could_not_continue=last_stop_reason,
                shortage_classification=shortage,
                discovery_rounds=discovery_rounds,
                created_at=now,
                pre_lifecycle_acquisition=(
                    None
                    if acquisition_ledger is None
                    else acquisition_ledger.to_dict(now=_utc_now_iso())
                ),
            )
            persist_exhaustion_certificate(connection, certificate)
            connection.commit()

        # Build a synthetic front-door report compatible with existing consumers.
        combined_reserve = eligible_list[: max(required_token_capacity, len(eligible_list))]
        synthetic_front_door = dict(last_front_door) if last_front_door else {}
        synthetic_front_door.update(
            {
                "candidates": [
                    {
                        "mint": c["mint"],
                        "pool": c["pumpswap_pool"],
                        "market_identity": c["market_identity"],
                        "provenance": c["provenance"],
                        "lifecycle_state": c.get("lifecycle_state"),
                        "graduation_block_time": c.get("graduation_block_time"),
                        "liquidity": dict(c.get("liquidity") or {}),
                        "evidence_expires_at": c.get("evidence_expires_at"),
                        "historical_reserve_evidence": c.get(
                            "historical_reserve_evidence"
                        ),
                        "current_eligibility_status": c.get(
                            "current_eligibility_status",
                            ELIGIBLE_FRESH if c.get("eligible") else EXCLUDED,
                        ),
                        "excluded_before_market_source": bool(
                            c.get("excluded_before_market_source")
                        ),
                        "tracking_handoff": dict(c.get("tracking_handoff") or {}),
                        "tracking_requalification_required": bool(
                            c.get("tracking_requalification_required")
                            or (c.get("tracking_handoff") or {}).get(
                                "requalification_required"
                            )
                        ),
                        "eligible": bool(c.get("eligible")),
                        "rejection": (
                            None if c.get("eligible") else _candidate_rejection_reason(c)
                        ),
                    }
                    for c in all_candidates
                ],
                "candidate_count": len(all_candidates),
                "combined_reserve_order": [
                    {
                        "mint": c["mint"],
                        "pool": c["pumpswap_pool"],
                        "market_identity": c["market_identity"],
                        "provenance": c["provenance"],
                        "lifecycle_state": c.get("lifecycle_state"),
                        "graduation_block_time": c.get("graduation_block_time"),
                        "liquidity": dict(c.get("liquidity") or {}),
                        "evidence_expires_at": c.get("evidence_expires_at"),
                        "tracking_handoff": dict(c.get("tracking_handoff") or {}),
                        "tracking_requalification_required": bool(
                            c.get("tracking_requalification_required")
                        ),
                        "eligible": True,
                        "rejection": None,
                    }
                    for c in combined_reserve
                ],
                "holder_reserve_order": [
                    {
                        "mint": c["mint"],
                        "pool": c["pumpswap_pool"],
                        "market_identity": c["market_identity"],
                        "provenance": c["provenance"],
                        "eligible": True,
                    }
                    for c in combined_reserve
                ],
                "latest_eligible_count": sum(
                    1
                    for c in eligible_list
                    if "LATEST" in str(c.get("provenance") or "")
                ),
                "persisted_eligible_count": sum(
                    1
                    for c in eligible_list
                    if "LATEST" not in str(c.get("provenance") or "")
                ),
                "market_calls": fresh_market_checks,
                "cooldown_skip_count": cooldown_skips,
                "selection_floor_usd": SELECTION_FLOOR_USD,
                "discovery_rounds": discovery_rounds,
                "evaluated_unique_mints": len(evaluated_mints),
                "eligible_reserve_count": len(eligible_list),
                "permanent_market_reports": permanent_market_reports,
            }
        )

        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        fk = connection.execute("PRAGMA foreign_key_check").fetchall()

        diagnostics = {
            "confirmed_this_cycle": int(discovery.get("confirmed_count") or 0),
            "latest_graduated_count": int(discovery.get("latest_graduated_count") or 0),
            "persisted_graduated_count": int(
                discovery.get("persisted_graduated_count") or 0
            ),
            "front_door_candidate_count": len(all_candidates),
            "latest_eligible_count": synthetic_front_door["latest_eligible_count"],
            "persisted_eligible_count": synthetic_front_door["persisted_eligible_count"],
            "combined_reserve_count": len(eligible_list),
            "below_floor_count": int(rejection_reasons.get(LIQUIDITY_BELOW_SELECTION_FLOOR, 0)),
            "unproven_count": int(rejection_reasons.get(LIQUIDITY_UNPROVEN, 0)),
            "selection_floor_usd": SELECTION_FLOOR_USD,
            "discovery_forbidden_delta_total": int(
                discovery.get("forbidden_delta_total") or 0
            ),
            "front_door_forbidden_delta_total": int(
                (last_front_door or {}).get("forbidden_delta_total") or 0
            ),
            "locator_status": locator.get("status"),
            "locator_matched_count": int(locator.get("matched_count") or 0),
            "locator_source_requests": int(locator.get("source_requests") or 0),
            "dexscreener_locator": {
                "request_id": locator.get("request_id"),
                "source_request_ids": list(
                    locator.get("source_request_ids")
                    or (
                        [int(locator["request_id"])]
                        if locator.get("request_id") is not None
                        else []
                    )
                ),
                "source_request_coverage": list(
                    locator.get("source_request_coverage") or ()
                ),
                "status": locator.get("status"),
                "source_requests": int(locator.get("source_requests") or 0),
                "accounting_blocker": bool(locator.get("accounting_blocker")),
                "accounting_blocker_reason": locator.get(
                    "accounting_blocker_reason"
                ),
            },
            "direct_migration_discovery": {
                "source_request_ids": list(
                    discovery.get("source_request_ids")
                    or (discovery.get("source_operation_ledger") or {}).get(
                        "source_request_ids"
                    )
                    or (discovery.get("source_operation_ledger") or {}).get(
                        "request_ids"
                    )
                    or ()
                ),
                "source_request_coverage": list(
                    discovery.get("source_request_coverage")
                    or (discovery.get("source_operation_ledger") or {}).get(
                        "source_request_coverage"
                    )
                    or ()
                ),
                "status": discovery.get("status"),
                "source_operation_ledger": dict(
                    discovery.get("source_operation_ledger") or {}
                ),
                "campaign_safe_stop": bool(discovery.get("campaign_safe_stop")),
                "accounting_block_reason": discovery.get("accounting_block_reason"),
                "accounting_blocker": bool(
                    discovery.get("campaign_safe_stop")
                    or discovery.get("accounting_blocker")
                ),
                "accounting_blocker_reason": discovery.get(
                    "accounting_blocker_reason"
                )
                or discovery.get("accounting_block_reason"),
            },
            "geckoterminal_nomination": geckoterminal_nomination_report,
            "discovery_source_requests": int(
                (discovery.get("source_operation_ledger") or {}).get("source_requests")
                or 0
            ),
            "direct_migration_protocol_confirmation_requests": (
                direct_protocol_confirmation_calls
            ),
            "front_door_liquidity_requests": fresh_market_checks,
            "stage_local_source_requests": ops_used,
            "integrity_check": integrity,
            "foreign_key_violations": len(fk),
            "discovery_rounds": discovery_rounds,
            "evaluated_unique_mints": len(evaluated_mints),
            "unexplored_unique_remaining": unexplored_remaining,
            "discovery_operation_budget": discovery_operation_budget,
            "discovery_operations_used": ops_used,
            "discovery_operations_remaining": _ops_remaining(),
            "last_stop_reason": last_stop_reason,
            "shortage_classification": shortage,
            "pre_lifecycle_acquisition": (
                None
                if acquisition_ledger is None
                else acquisition_ledger.to_dict(now=_utc_now_iso())
            ),
            "required_token_capacity": required_token_capacity,
            "eligible_reserve_count": len(eligible_list),
            "cooldown_skips": cooldown_skips,
            "tracking_precheck_enabled": bool(tracking_precheck),
            "tracking_dispositions": dict(tracking_dispositions),
            "tracking_terminal_cause": next(
                (
                    str(item.get("category"))
                    for _, item in sorted(tracking_dispositions.items())
                    if not bool(item.get("eligible_for_evidence"))
                ),
                None,
            ),
            "pre_source_tracking_exclusions": sum(
                1
                for candidate in all_candidates
                if candidate.get("excluded_before_market_source")
            ),
            "stale_evidence_exclusions": stale_exclusions,
            "provider_failures": provider_failures,
            "liquidity_stage_provider_failures": (
                liquidity_stage_provider_failures
            ),
            "channels_unavailable": sorted(set(channels_unavailable)),
            "liquidity_outcome_counts": dict(liquidity_outcome_counts),
            "candidate_liquidity_lineage": [
                _candidate_liquidity_lineage(candidate)
                for candidate in all_candidates
            ],
            "duplicate_observations_removed": duplicate_observations_removed,
            "evaluation_batch_size": front_door_max_candidates,
            "permanent_availability": bool(permanent_availability),
            "protocol_confirmation": {
                "source_request_ids": list(
                    (protocol_report or {}).get("source_request_ids") or ()
                ),
                "source_request_coverage": list(
                    (protocol_report or {}).get("source_request_coverage") or ()
                ),
                "promoted_observation_eligible_count": len(
                    (protocol_report or {}).get("promoted_observation_eligible")
                    or ()
                ),
                "requires_market_revalidation_count": len(
                    (protocol_report or {}).get("requires_market_revalidation")
                    or ()
                ),
                "outcome_counts": dict(
                    (protocol_report or {}).get("outcome_counts") or {}
                ),
                "sealed_stage_present": bool(
                    (protocol_report or {}).get("sealed_stage_evidence")
                ),
                "sealed_stage_evidence_blocks": list(
                    (protocol_report or {}).get("sealed_stage_evidence_blocks")
                    or ()
                ),
                "accounting_blocker": bool(
                    (protocol_report or {}).get("accounting_blocker")
                ),
                "accounting_blocker_reason": (
                    protocol_report or {}
                ).get("accounting_blocker_reason"),
            },
            "liquidity_backup": {
                "source_requests": int(
                    liquidity_backup_report.get("source_requests") or 0
                ),
                "source_request_ids": list(
                    liquidity_backup_report.get("source_request_ids") or ()
                ),
                "source_request_coverage": list(
                    liquidity_backup_report.get("source_request_coverage") or ()
                ),
                "transport_operations": int(
                    liquidity_backup_report.get("transport_operations") or 0
                ),
                "accounting_blocker": bool(
                    liquidity_backup_report.get("accounting_blocker")
                ),
                "accounting_blocker_reason": liquidity_backup_report.get(
                    "accounting_blocker_reason"
                ),
                "attempts": list(liquidity_backup_report.get("attempts") or ()),
                "above_floor_promoted_to_protocol_due": int(
                    liquidity_backup_report.get(
                        "above_floor_promoted_to_protocol_due"
                    )
                    or 0
                ),
                "below_floor": int(liquidity_backup_report.get("below_floor") or 0),
                "exact_pool_no_match": int(
                    liquidity_backup_report.get("exact_pool_no_match") or 0
                ),
                "still_unknown": int(
                    liquidity_backup_report.get("still_unknown") or 0
                ),
            },
            "geckoterminal_nomination": dict(geckoterminal_nomination_report),
            "permanent_market_reports": list(permanent_market_reports),
            "campaign_source_request_coverage": list(
                list(locator.get("source_request_coverage") or ())
                + list(
                    discovery.get("source_request_coverage")
                    or (discovery.get("source_operation_ledger") or {}).get(
                        "source_request_coverage"
                    )
                    or ()
                )
                + list(
                    geckoterminal_nomination_report.get("source_request_coverage")
                    or ()
                )
                + list(
                    liquidity_backup_report.get("source_request_coverage") or ()
                )
                + list(
                    (protocol_report or {}).get("source_request_coverage") or ()
                )
                + [
                    entry
                    for report in permanent_market_reports
                    for entry in (report.get("source_request_coverage") or ())
                ]
            ),
            "discovery_request_key_prefix": discovery_request_key_prefix,
            "memory_observation_eligible_count": sum(
                1
                for item in eligible_list
                if item.get("memory_observation_eligible") is True
            ),
            "nominations_by_source": {
                "direct_pump_migration": int(
                    discovery.get("confirmed_count") or 0
                ),
                "dexscreener_fresh_profiles": int(
                    locator.get("surfaced_count") or 0
                ),
                "geckoterminal_new_pools": len(
                    geckoterminal_nomination_report.get("nominations") or ()
                ),
                "due_persisted_graduated": int(inventory_known_at_start),
            },
            "unique_mints_by_source": {
                "direct_pump_migration": sorted(latest_mints),
                "dexscreener_fresh_profiles": sorted(
                    {
                        str(item.get("mint") or "")
                        for item in locator.get("pool_observations") or ()
                        if item.get("mint")
                    }
                ),
                "geckoterminal_new_pools": sorted(
                    {
                        str(item.get("mint") or "")
                        for item in geckoterminal_nomination_report.get(
                            "nominations"
                        )
                        or ()
                        if item.get("mint")
                    }
                ),
            },
            "permanent_batch_sizes": [
                size
                for report in permanent_market_reports
                for size in report.get("batch_sizes", ())
            ],
            "exact_pools_by_mint": {
                mint: pools
                for report in permanent_market_reports
                for mint, pools in report.get("exact_pools_by_mint", {}).items()
            },
            "market_ready_count": len(eligible_list),
            "reconciliation_outcomes": [
                outcome
                for report in permanent_market_reports
                for outcome in report.get("reconciliation_outcomes", ())
            ],
            "state_transition_ids": [
                transition_id
                for report in permanent_market_reports
                for transition_id in report.get("state_transition_ids", ())
            ],
            "suppressed_exact_pool_count": sum(
                int(report.get("suppressed_exact_pool_count") or 0)
                for report in permanent_market_reports
            ),
            "local_zero_source_exclusions": [
                exclusion
                for report in permanent_market_reports
                for exclusion in report.get("local_zero_source_exclusions", ())
            ],
            "stage_reservations": {
                name: reserved for name, reserved in stage_budget.reservations
            },
            "stage_operations_used": dict(stage_budget.used_by_stage),
            "stage_total_ceiling": stage_budget.total_ceiling,
            "stage_capacity": stage_budget.snapshot(),
            "sealed_stages": sorted(stage_budget.sealed),
            "unsealed_stages": [
                name
                for name in stage_budget.stage_names
                if name not in stage_budget.sealed
            ],
            "pending_work_by_queue": {
                name: list(items) for name, items in work_queues.items()
            },
            "market_batch_rounds": discovery_rounds if permanent_availability else discovery_rounds,
            "protocol_confirmation_attempts": len(protocol_confirmation_outcomes),
            "protocol_confirmation_outcomes": list(protocol_confirmation_outcomes),
            "protocol_batch_count": int(protocol_report.get("batch_count") or 0),
            "protocol_source_request_ids": list(
                protocol_report.get("source_request_ids") or ()
            ),
            "protocol_confirmed_for_market": list(
                protocol_report.get("confirmed_for_market") or ()
            ),
            "protocol_local_validation_steps": int(
                protocol_report.get("local_validation_steps") or 0
            ),
            "protocol_transport_operations": int(
                protocol_report.get("transport_operations") or 0
            ),
            "migration_evidence_rejections": list(migration_evidence_rejections),
            "shared_source_failures": provider_failures,
            "holder_safety_due_count": len(work_queues.get("HOLDER_SAFETY_DUE") or ()),
            "market_ready_reserve_depth": len(eligible_list),
            "fully_eligible_reserve_depth": 0,
            "lawful_work_remaining_at_terminal": bool(
                unexplored_remaining > 0
                or any(work_queues.get(name) for name in work_queues)
            ),
            "lifecycle_operation_ceiling": LIFECYCLE_OPERATION_CEILING,
            "restart_created": False,
            "successor_created": False,
            "automatic_retry_created": False,
        }

        return PersistentSupplyResult(
            ready=ready,
            terminal=terminal,
            eligible_reserve=eligible_list,
            all_candidates=all_candidates,
            discovery_report=discovery,
            front_door_report=synthetic_front_door,
            locator_report=locator,
            diagnostics=diagnostics,
            exhaustion_certificate=certificate,
            shortage_classification=shortage,
            discovery_rounds=discovery_rounds,
        )
    finally:
        connection.close()


__all__ = [
    "REQUIRED_TOKEN_CAPACITY",
    "EVALUATION_BATCH_SIZE",
    "DEFAULT_DISCOVERY_OPERATION_BUDGET",
    "LIFECYCLE_OPERATION_CEILING",
    "ELIGIBLE_FRESH",
    "ELIGIBLE_STALE",
    "REMOVED",
    "EXCLUDED",
    "TRUE_MARKET_SUPPLY_SHORTAGE",
    "SOURCE_VISIBILITY_SHORTAGE",
    "SOURCE_AVAILABILITY_FAILURE",
    "BUDGET_EXHAUSTION",
    "DURATION_EXHAUSTION",
    "STALE_EVIDENCE_SHORTAGE",
    "DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE",
    "TRACKING_STATE_CAPACITY_BLOCKED",
    "MIGRATION_EVIDENCE_REJECTED",
    "SHORTAGE_CLASSIFICATIONS",
    "BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL",
    "GRADUATED_SUPPLY_READY",
    "EligibleTokenSupplyError",
    "ExhaustionCertificate",
    "PersistentSupplyResult",
    "load_eligible_reserve",
    "upsert_eligible_reserve",
    "mark_reserve_status",
    "persist_exhaustion_certificate",
    "classify_shortage",
    "run_persistent_eligible_token_supply",
    "_is_candidate_local_migrate_failure",
]

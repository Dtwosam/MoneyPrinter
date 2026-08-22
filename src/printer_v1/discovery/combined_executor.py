"""Fixture-backed combined Pump.fun discovery execution owner (V2-9.7D.7B.4D).

Binds approved discovery adapters, migration-034 persistence, fixed gates,
uniform selection, and first WINDOW_15M tracking handoff.

No real network calls, secrets, retrieval, paper decisions, or financial
capability. Dependency-injected for 7A as:

    CombinedPumpfunCampaignExecutor(...).execute(
        command=..., source_governor=..., central_scheduler=...
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.discovery.persistence import (
    FORBIDDEN_FACTUAL_FIELDS,
    LOCKED_FINANCIAL_TABLES,
    DiscoveryPersistenceError,
    candidate_identity_key,
    insert_discovery_batch,
    insert_discovery_work,
    insert_merged_candidate,
    insert_origin_verification,
    insert_provider_observation,
    insert_provider_report_link,
    insert_pumpswap_confirmation,
    link_candidate_contribution,
    link_discovery_work_source,
    link_selected_item,
    link_selection_batch,
    list_provider_observations,
)
from printer_v1.discovery.selection_batch import (
    check_pair_selection_cooldown,
    check_token_selection_cooldown,
)
from printer_v1.lifecycle.contracts import LifecycleEvent, TokenLifecycleState
from printer_v1.lifecycle.tracking_queue import (
    HANDOFF_ACTIVE_CONFLICT,
    HANDOFF_COOLDOWN_REOPEN_REQUIRED,
    HANDOFF_TERMINAL_REOPEN_REQUIRED,
    HANDOFF_UNSUPPORTED_STATE,
    assess_tracking_handoff,
    assess_tracking_handoff_by_identity,
    claim_tracking_item,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    AbstractCampaignCommand,
    CampaignExecutionResult,
    CENTRAL_SCHEDULER_OWNER,
    OwnerPort,
    SOURCE_GOVERNOR_OWNER,
)
from printer_v1.operator_cli.campaign_ownership import cycle_scoped_token_slot_id
from printer_v1.discovery.scheduler_parity import (
    reconcile_discovery_work_jobs,
    terminalize_scheduler_job_for_work,
)
from printer_v1.scheduler.contracts import JobKind, JobStatus, LockResult
from printer_v1.scheduler.scheduler import cancel_job, claim_due_job, enqueue_job
from printer_v1.sources.governor import can_request_source
from printer_v1.discovery.memory_observation_activation import (
    EvidenceRole,
    FrozenMemoryActivationSet,
    MEMORY_OBSERVATION_SELECTION_REASON,
    MemoryObservationActivationError,
    measure_source_row_ids,
    reconcile_activation_source_rows,
    role_reference_for_candidate,
    validate_memory_activation_set,
)
from printer_v1.discovery.token_pair_identity import (
    TokenPairIdentityError,
    ensure_neutral_token_pair_identity,
)
from printer_v1.sources.secondary_discovery import (
    DISCARDED_NON_AUTHORITATIVE_FIELDS,
    GECKO_ACTIVE_REQUEST,
    GECKO_SOURCE_NAME,
    GECKO_TRENDING_REQUEST,
    GECKO_WORK_TYPE,
    PUMPFUN_ORIGIN_STATUS,
    TRACKER_SOURCE_NAME,
    TRACKER_TOP_REQUEST,
    TRACKER_TRENDING_REQUEST,
    TRACKER_WORK_TYPE,
    SecondaryDiscoveryError,
    SolanaTrackerAuthConfig,
    normalize_gecko_active,
    normalize_gecko_trending,
    normalize_tracker_list,
)
from printer_v1.sources.pumpfun_direct import PumpCreateObservation
from printer_v1.sources.pumpfun_origin import (
    ACQUISITION_MODE_PROSPECTIVE,
    PUMP_CREATE_INDEX_ADDRESS,
    ContinuityState,
    FinalizedOriginCursor,
    OriginRegistryError,
    load_origin_cursor,
    lookup_confirmed_origin,
    record_confirmed_origin,
    run_acquisition_cycle,
    save_origin_cursor,
)


# ---------------------------------------------------------------------------
# Ceilings (7B.2 design-frozen maxima)
# ---------------------------------------------------------------------------

INTAKE_SOURCE_CALLS = 45
INTAKE_UNDERLYING_RPC = 45
INTAKE_SCHEDULER_WORK = 11
INTAKE_OBSERVATIONS = 96
INTAKE_UNIQUE_MINTS = 64
ORIGIN_VERIFY_ADMISSIONS = 8
PUMPSWAP_ADMISSIONS = 4
TRACKING_HANDOFFS = 2
INTAKE_STORAGE_BYTES = 8 * 1024 * 1024
INTAKE_DEADLINE_SECONDS = 360
PROVIDER_LANE_FAILURES_MAX = 5

WORK_TYPES_ORDER = (
    "DISCOVERY_PUMPFUN_LATEST",
    "DISCOVERY_DEXSCREENER_ACTIVE",
    "DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE",
    "DISCOVERY_SOLANA_TRACKER_TRENDING_TOP",
    "DISCOVERY_IDENTITY_MERGE",
    "DISCOVERY_ORIGIN_VERIFICATION",
    "DISCOVERY_PUMPSWAP_CONFIRMATION",
    "DISCOVERY_FIXED_ELIGIBILITY_GATES",
    "DISCOVERY_UNIFORM_SELECTION",
    "DISCOVERY_TRACKING_HANDOFF_SLOT_1",
    "DISCOVERY_TRACKING_HANDOFF_SLOT_2",
)

GATE_ORDER = (
    "OWNERSHIP",
    "SOURCE_PROVENANCE",
    "SOLANA_IDENTITY",
    "PUMPFUN_ORIGIN",
    "LIFECYCLE_MARKET",
    "TRACKING_HANDOFF",
    "FRESHNESS_CUTOFF",
    "EVIDENCE_QUALITY",
    "CANDIDATE_ROLE",
    "INFRASTRUCTURE_EXCLUSION",
    "DUPLICATE_CONFLICT",
    "B3_RECONCILIATION",
    "COOLDOWN",
    "VACANCY",
    "BUDGET",
)

DEXSCREENER_SOURCE = "dexscreener"
DEXSCREENER_WORK_TYPE = "DISCOVERY_DEXSCREENER_ACTIVE"
DIRECT_WORK_TYPE = "DISCOVERY_PUMPFUN_LATEST"
SEED_DOMAIN = "PrinterV1|combined-pumpfun-v1|"

# V2-9.7E.41 graduation-only tracking law.
#
# The single selectable lifecycle state. Every other intake lifecycle state is
# discovery-only and permanently ineligible for active selection.
GRADUATED_LIFECYCLE = "PUMPSWAP_GRADUATED_CONFIRMED"
PUMPSWAP_PROGRAM_ID = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
PUMPSWAP_VENUE = "pumpswap"
PUMPSWAP_MARKET_PREFIX = f"solana-mainnet:{PUMPSWAP_VENUE}:"

# Channel -> distribution category. `LATEST_GRADUATED` is the newly-graduated
# latest channel; every other category is "non-latest". Categories are provenance
# labels only and never a comparative rank, score or popularity signal.
_LATEST_CHANNELS = frozenset({"LATEST_PUMPFUN", "LATEST_GRADUATED"})
_CHANNEL_CATEGORY = MappingProxyType(
    {
        "LATEST_PUMPFUN": "LATEST_GRADUATED",
        "LATEST_GRADUATED": "LATEST_GRADUATED",
        "ACTIVE_PUMPFUN": "ACTIVE",
        "TRENDING_PUMPFUN": "TRENDING",
        "TOP_PUMPFUN": "TOP",
        # V2-9.7E.43: the truthful persisted graduated category. The former
        # "PERSISTED_ACTIVE" label is kept as a deprecated alias mapping to it.
        "PERSISTED_GRADUATED": "PERSISTED_GRADUATED",
        "PERSISTED_ACTIVE": "PERSISTED_GRADUATED",
        "REVIVAL_PUMPFUN": "REVIVAL",
        "DUMP_PUMPFUN": "DUMP",
        "CONSOLIDATION_PUMPFUN": "CONSOLIDATION",
        "DECAY_PUMPFUN": "DECAY",
    }
)


def _candidate_categories(channels: "set[str]") -> set[str]:
    """Distribution categories a candidate belongs to (identity-deduped set)."""
    return {_CHANNEL_CATEGORY.get(channel, "TOP") for channel in channels}


def _non_latest_categories(channels: "set[str]") -> set[str]:
    return {cat for cat in _candidate_categories(channels) if cat != "LATEST_GRADUATED"}


class CombinedDiscoveryError(RuntimeError):
    """Fail-closed combined discovery execution fault."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}: {detail}")


@dataclass(frozen=True)
class FixtureSourceFact:
    """One governed synthetic source fact for a provider lane."""

    request_kind: str
    source_name: str
    body: Any
    receipt_time: str
    status_code: int = 200
    fixture_status: str = "success"
    failure_type: str | None = None
    params: Mapping[str, Any] | None = None
    requested_pool: str | None = None


@dataclass(frozen=True)
class FixtureOriginProof:
    mint: str
    signature: str
    slot: int
    block_time: int
    bonding_curve: str = "curve"
    associated_bonding_curve: str = "ata"
    creator_address: str = "creator"
    confirmed: bool = True
    create_layout: str = "PUMP_CREATE_V1"
    # V2-9.7E.45 typed activation route. "PUMP_CREATE" is the create-native origin
    # (Route A): ``signature``/``slot``/``block_time`` are the Pump *create*
    # transaction fields written to the create origin registry. "GRADUATION_NATIVE"
    # (Route B) is a migration-discovered candidate whose ``signature`` is the
    # migration (graduation-lineage) signature and ``slot``/``block_time`` are the
    # graduation slot/block time. A graduation-native proof is NEVER written to the
    # create origin registry and its migration signature is NEVER persisted into a
    # create-signature field.
    origin_route: str = "PUMP_CREATE"


@dataclass(frozen=True)
class FixturePumpSwapProof:
    mint: str
    pool_address: str
    program_id: str = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
    confirmed: bool = True
    ambiguous: bool = False


@dataclass(frozen=True)
class CombinedDiscoveryFixtures:
    """Synthetic plan for one fixture-backed discovery cycle."""

    cycle_id: str
    cycle_cutoff: str
    campaign_selection_seed: str
    provider_contract_versions: Mapping[str, str]
    git_provenance_identity: str
    evaluated_at: str
    mode: str = "INITIAL"  # INITIAL | REPLACEMENT
    vacant_slot_ordinals: tuple[int, ...] = (1, 2)
    healthy_slot_ids: tuple[str, ...] = ()
    gecko_ops: tuple[FixtureSourceFact, ...] = ()
    tracker_ops: tuple[FixtureSourceFact, ...] = ()
    dexscreener_ops: tuple[FixtureSourceFact, ...] = ()
    direct_observations: tuple[FixtureOriginProof, ...] = ()
    # V2-9.7E.5: ordered pumpfun_origin.FixtureOperation plan for one bounded
    # signature-anchored acquisition cycle on the create index address.
    direct_operations: tuple[Any, ...] = ()
    prior_cursor: FinalizedOriginCursor | None = None
    origin_proofs: Mapping[str, FixtureOriginProof] = field(default_factory=dict)
    origin_cutoff_slot: int | None = None
    pumpswap_proofs: Mapping[str, FixturePumpSwapProof] = field(default_factory=dict)
    tracker_auth: SolanaTrackerAuthConfig | None = None
    batch_seq: int = 1
    force_shared_fault: str | None = None
    provider_failures_injected: Mapping[str, str] = field(default_factory=dict)
    # V2-9.7E.19 operational-only pre-activation holder-evidence facts.
    holder_evidence_eligibility: Mapping[str, Mapping[str, Any]] = field(
        default_factory=dict
    )
    # Atomic handoff injection points for focused repair proofs only.
    # BEFORE_FIRST | DURING_SECOND | SECOND_SCHEDULER_JOB | DUPLICATE_ACTIVE | CONFLICTING_SLOT
    force_handoff_failure: str | None = None
    # Exact post-freeze authority for the operational memory-observation path.
    # When present, no provider lane or selector may run.
    memory_activation_set: FrozenMemoryActivationSet | None = None


@dataclass
class _Usage:
    source_calls: int = 0
    underlying_rpc: int = 0
    scheduler_work: int = 0
    storage_bytes: int = 0
    failures: int = 0
    provider_lane_failures: int = 0
    observations: int = 0
    unique_mints: set[str] = field(default_factory=set)
    handoffs: int = 0

    def bump_source(self, n: int = 1) -> None:
        if self.source_calls + n > INTAKE_SOURCE_CALLS:
            raise CombinedDiscoveryError("SOURCE_CEILING")
        self.source_calls += n

    def bump_scheduler(self, n: int = 1) -> None:
        if self.scheduler_work + n > INTAKE_SCHEDULER_WORK:
            raise CombinedDiscoveryError("SCHEDULER_WORK_CEILING")
        self.scheduler_work += n

    def bump_storage(self, n: int) -> None:
        if self.storage_bytes + n > INTAKE_STORAGE_BYTES:
            raise CombinedDiscoveryError("STORAGE_CEILING")
        self.storage_bytes += n

    def bump_failure(self) -> None:
        self.failures += 1
        self.provider_lane_failures += 1
        if self.provider_lane_failures > PROVIDER_LANE_FAILURES_MAX:
            raise CombinedDiscoveryError("PROVIDER_LANE_FAILURE_CEILING")


@dataclass
class _Observation:
    observation_id: str
    provider: str
    request_kind: str
    channel: str
    mint: str
    pool: str
    quote_mint: str
    venue: str
    observed_at: str
    raw_payload_hash: str
    source_request_id: int | None
    source_response_id: int | None
    source_failure_id: int | None
    work_id: str
    pumpfun_origin_status: str = PUMPFUN_ORIGIN_STATUS
    lifecycle: str = "PUMP_LIFECYCLE_UNKNOWN"
    activity_count: int | None = None
    origin_route: str = "PUMP_CREATE"


@dataclass
class _Merged:
    merged_candidate_id: str
    mint: str
    market_identity: str
    lifecycle: str
    channels: set[str]
    observation_ids: list[str]
    conflicts: list[dict[str, str]]
    gaps: list[dict[str, str]]
    origin_state: str = "PENDING"
    pumpswap_state: str = "NOT_REQUIRED"
    first_failed_gate: str | None = None
    eligible: bool = False
    origin_route: str = "PUMP_CREATE"


# Public owner-local candidate shape. The existing executor and pre-admission
# seam intentionally share this exact mutable gate carrier; there is no second
# eligibility or selection model.
DiscoverySelectionCandidate = _Merged


@dataclass(frozen=True)
class DiscoveryGateSelectionOutcome:
    eligible: tuple[DiscoverySelectionCandidate, ...]
    selected: tuple[DiscoverySelectionCandidate, ...]
    rejection_causes: tuple[tuple[str, str], ...]


def _apply_existing_discovery_gates(
    connection: sqlite3.Connection,
    *,
    candidates: Sequence[DiscoverySelectionCandidate],
    discovery_batch_id: str,
    evaluated_at: datetime,
    mode: str,
    vacant_slot_ordinals: Sequence[int],
    batch_seq: int,
    handoffs_used: int,
    market_authority_mints: frozenset[str] = frozenset(),
) -> list[DiscoverySelectionCandidate]:
    eligible: list[DiscoverySelectionCandidate] = []
    for candidate in candidates:
        market_authority = candidate.mint in market_authority_mints
        failed = None
        for gate in GATE_ORDER:
            if gate == "OWNERSHIP":
                if not discovery_batch_id:
                    failed = gate
            elif gate == "SOURCE_PROVENANCE":
                if not candidate.observation_ids:
                    failed = gate
            elif gate == "SOLANA_IDENTITY":
                if not candidate.mint or not candidate.market_identity:
                    failed = gate
            elif gate == "PUMPFUN_ORIGIN":
                if not market_authority and candidate.origin_state != "CONFIRMED":
                    failed = gate
            elif gate == "LIFECYCLE_MARKET":
                if market_authority:
                    if (
                        candidate.lifecycle != "PRESENT_POOL_CONFIRMED"
                        or not candidate.market_identity
                    ):
                        failed = gate
                elif (
                    candidate.lifecycle != GRADUATED_LIFECYCLE
                    or candidate.pumpswap_state != "CONFIRMED"
                    or not candidate.market_identity.startswith(PUMPSWAP_MARKET_PREFIX)
                ):
                    failed = gate
            elif gate == "TRACKING_HANDOFF":
                pool = candidate.market_identity.rsplit(":", 1)[-1]
                handoff = assess_tracking_handoff_by_identity(
                    connection,
                    token_mint=candidate.mint,
                    pair_address=pool,
                    tracking_lane=TokenLifecycleState.TRACK_NORMAL,
                    assessed_at=evaluated_at,
                )
                if not handoff.eligible:
                    failed = handoff.reason_code or HANDOFF_UNSUPPORTED_STATE
            elif gate == "FRESHNESS_CUTOFF":
                pass
            elif gate == "EVIDENCE_QUALITY":
                if any(
                    gap.get("kind") in {"DIRTY", "HOLDER_EVIDENCE_INELIGIBLE"}
                    for gap in candidate.gaps
                ):
                    failed = gate
            elif gate == "CANDIDATE_ROLE":
                if not candidate.channels:
                    failed = gate
            elif gate == "INFRASTRUCTURE_EXCLUSION":
                if candidate.mint in {
                    "So11111111111111111111111111111111111111112",
                    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                }:
                    failed = gate
            elif gate == "DUPLICATE_CONFLICT":
                if candidate.conflicts:
                    failed = gate
            elif gate == "B3_RECONCILIATION":
                if mode == "REPLACEMENT" and not vacant_slot_ordinals:
                    failed = gate
            elif gate == "COOLDOWN":
                pool = candidate.market_identity.rsplit(":", 1)[-1]
                ok_token, _ = check_token_selection_cooldown(
                    connection, candidate.mint, batch_seq
                )
                ok_pair, _ = check_pair_selection_cooldown(
                    connection, pool, batch_seq
                )
                if not ok_token or not ok_pair:
                    failed = gate
            elif gate == "VACANCY":
                if mode == "INITIAL" and len(vacant_slot_ordinals) < 2:
                    pass
            elif gate == "BUDGET":
                if handoffs_used >= TRACKING_HANDOFFS:
                    failed = gate
            if failed:
                break
        candidate.first_failed_gate = failed
        candidate.eligible = failed is None
        if candidate.eligible:
            eligible.append(candidate)
    return eligible


def _uniform_pick_existing(
    candidates: Sequence[DiscoverySelectionCandidate],
    cycle_seed: str,
    domain: str,
    count: int,
) -> list[DiscoverySelectionCandidate]:
    if count <= 0 or not candidates:
        return []
    ordered = sorted(
        candidates,
        key=lambda item: (
            _token_identity(item.mint), item.market_identity, item.lifecycle
        ),
    )
    return _fisher_yates(ordered, f"{cycle_seed}|{domain}")[:count]


def _round_robin_non_latest_existing(
    candidates: Sequence[DiscoverySelectionCandidate],
    cycle_seed: str,
    batch_seq: int,
) -> str:
    categories: set[str] = set()
    for candidate in candidates:
        categories |= _non_latest_categories(candidate.channels)
    ordered = sorted(
        categories,
        key=lambda category: (
            _sha256_text(f"{cycle_seed}|category|{category}"), category
        ),
    )
    if not ordered:
        return ""
    return ordered[(max(int(batch_seq), 1) - 1) % len(ordered)]


def _selectable_existing_discovery_candidate(
    candidate: DiscoverySelectionCandidate,
    *,
    market_authority_mints: frozenset[str],
) -> bool:
    """Keep the post-gate selectable pool aligned with both admission authorities.

    The categorical gate already ran. This filter only prevents a MARKET
    candidate from disappearing because the historical selector required
    PUMPSWAP_GRADUATED_CONFIRMED. It does not re-check exact-pool admission.
    """
    if candidate.conflicts or not candidate.market_identity:
        return False
    if candidate.mint in market_authority_mints:
        return candidate.lifecycle == "PRESENT_POOL_CONFIRMED"
    return (
        candidate.lifecycle == GRADUATED_LIFECYCLE
        and candidate.market_identity.startswith(PUMPSWAP_MARKET_PREFIX)
    )


def _select_existing_discovery_candidates(
    eligible: Sequence[DiscoverySelectionCandidate],
    cycle_seed: str,
    *,
    vacancy_count: int,
    batch_seq: int,
    market_authority_mints: frozenset[str] = frozenset(),
) -> list[DiscoverySelectionCandidate]:
    if vacancy_count <= 0:
        return []
    selectable = [
        candidate
        for candidate in eligible
        if _selectable_existing_discovery_candidate(
            candidate, market_authority_mints=market_authority_mints
        )
    ]
    by_mint: dict[str, list[DiscoverySelectionCandidate]] = {}
    for candidate in selectable:
        by_mint.setdefault(candidate.mint, []).append(candidate)
    collapsed: list[DiscoverySelectionCandidate] = []
    for group in by_mint.values():
        channels: set[str] = set()
        for item in group:
            channels |= item.channels
        chosen = sorted(
            group, key=lambda item: (-len(item.channels), item.market_identity)
        )[0]
        chosen.channels = channels
        collapsed.append(chosen)
    if not collapsed:
        return []
    latest_only = [
        candidate
        for candidate in collapsed
        if not _non_latest_categories(candidate.channels)
    ]
    non_latest = [
        candidate
        for candidate in collapsed
        if _non_latest_categories(candidate.channels)
    ]
    if vacancy_count == 1:
        return _uniform_pick_existing(collapsed, cycle_seed, "single", 1)
    if latest_only and non_latest and vacancy_count >= 2:
        first = _uniform_pick_existing(
            latest_only, cycle_seed, "LATEST_GRADUATED", 1
        )
        category = _round_robin_non_latest_existing(
            non_latest, cycle_seed, batch_seq
        )
        members = [
            item
            for item in non_latest
            if category in _non_latest_categories(item.channels)
        ]
        return first + _uniform_pick_existing(members, cycle_seed, category, 1)
    return _uniform_pick_existing(
        non_latest or latest_only,
        cycle_seed,
        "SINGLE_CATEGORY",
        vacancy_count,
    )


def apply_existing_discovery_gate_and_selection(
    connection: sqlite3.Connection,
    *,
    candidates: Sequence[DiscoverySelectionCandidate],
    discovery_batch_id: str,
    evaluated_at: datetime,
    mode: str,
    vacant_slot_ordinals: Sequence[int],
    batch_seq: int,
    cycle_seed: str,
    handoffs_used: int,
    market_authority_mints: frozenset[str] = frozenset(),
) -> DiscoveryGateSelectionOutcome:
    """Apply the existing categorical gate and uniform selection authority."""
    eligible = _apply_existing_discovery_gates(
        connection,
        candidates=candidates,
        discovery_batch_id=discovery_batch_id,
        evaluated_at=evaluated_at,
        mode=mode,
        vacant_slot_ordinals=vacant_slot_ordinals,
        batch_seq=batch_seq,
        handoffs_used=handoffs_used,
        market_authority_mints=market_authority_mints,
    )
    selected = _select_existing_discovery_candidates(
        eligible,
        cycle_seed,
        vacancy_count=len(vacant_slot_ordinals),
        batch_seq=batch_seq,
        market_authority_mints=market_authority_mints,
    )
    rejected = tuple(
        (candidate.merged_candidate_id, str(candidate.first_failed_gate))
        for candidate in sorted(
            candidates, key=lambda item: item.merged_candidate_id
        )
        if candidate.first_failed_gate is not None
    )
    return DiscoveryGateSelectionOutcome(
        eligible=tuple(eligible), selected=tuple(selected), rejection_causes=rejected
    )


def persist_cycle_rooted_selection_batch(
    connection: sqlite3.Connection,
    *,
    discovery_batch_id: str,
    selection_batch_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    selected_count: int,
    now: str,
) -> None:
    """Persist the existing cycle-rooted selection-batch ownership shape."""
    connection.execute(
        """INSERT INTO printer_selection_batches(
               batch_id,batch_status,window_kind,selected_count,created_at
           ) VALUES (?,'ASSEMBLED','WINDOW_15M',?,?)""",
        (selection_batch_id, int(selected_count), now),
    )
    link_selection_batch(
        connection,
        discovery_batch_id=discovery_batch_id,
        selection_batch_id=selection_batch_id,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        now=now,
    )


def persist_cycle_rooted_selected_item(
    connection: sqlite3.Connection,
    *,
    discovery_batch_id: str,
    selection_batch_id: str,
    merged_candidate_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    token_slot_id: str,
    token_id: int,
    pair_id: int,
    token_mint: str,
    pair_address: str,
    selection_reason: str,
    tracking_handoff_state: str,
    first_window_15m_scheduler_job_id: int | None,
    now: str,
) -> int:
    """Persist one selected item and its existing cycle/handoff junction."""
    item_cursor = connection.execute(
        """INSERT INTO printer_selection_batch_items(
               batch_id,item_status,token_id,pair_id,token_mint,pair_address,
               chain,tracking_lane,selection_reason,selected_at,created_at
           ) VALUES (?,'SELECTED',?,?,?,?,'solana','TRACK_NORMAL',?,?,?)""",
        (
            selection_batch_id,
            int(token_id),
            int(pair_id),
            token_mint,
            pair_address,
            selection_reason,
            now,
            now,
        ),
    )
    item_id = int(item_cursor.lastrowid)
    link_selected_item(
        connection,
        discovery_batch_id=discovery_batch_id,
        selection_batch_id=selection_batch_id,
        selection_item_id=item_id,
        merged_candidate_id=merged_candidate_id,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        token_slot_id=token_slot_id,
        tracking_handoff_state=tracking_handoff_state,
        first_window_15m_scheduler_job_id=first_window_15m_scheduler_job_id,
        now=now,
    )
    return item_id


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _batch_scoped_object_id(
    object_kind: str,
    discovery_batch_id: str,
    *semantic_parts: object,
) -> str:
    """Return a deterministic immutable ID owned by one discovery batch."""
    kind = str(object_kind).strip()
    batch = str(discovery_batch_id).strip()
    parts = tuple(str(part) for part in semantic_parts)
    if not kind or not batch or not parts or any(not part for part in parts):
        raise CombinedDiscoveryError("MISSING_BATCH_SCOPED_IDENTITY")
    semantic = "".join(f"{len(part)}:{part}" for part in (kind, *parts))
    return (
        f"{kind}:{_sha256_text(batch)[:24]}:"
        f"{_sha256_text('PrinterV1|batch-object-v1|' + semantic)[:24]}"
    )


_SAFE_PERSISTENCE_MESSAGES = frozenset(
    {
        "conflicting provider observation repeat rejected",
        "identical observation content already owned by another id",
        "conflicting merged candidate repeat rejected",
        "duplicate candidate authority rejected for batch identity",
        "conflicting origin verification repeat rejected",
        "conflicting pumpswap confirmation repeat rejected",
    }
)

_SENSITIVE_ENV_NAME = re.compile(
    r"(?:API|AUTH|BEARER|CREDENTIAL|KEY|PASSWORD|RPC|SECRET|TOKEN|URL)", re.IGNORECASE
)
_URL_VALUE = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)
_BEARER_VALUE = re.compile(r"\bBearer\s+[^\s,;]+", re.IGNORECASE)
_SECRET_ASSIGNMENT = re.compile(
    r"\b(api[_-]?key|authorization|credential|password|secret|token)\s*[:=]\s*[^\s,;]+",
    re.IGNORECASE,
)
_MAX_SAFE_EXCEPTION_MESSAGE = 500


def _safe_exception_message(exc: BaseException) -> str:
    """Return a bounded useful message without runtime secrets or URLs."""
    message = str(exc).strip() or "exception message unavailable"
    for name, value in os.environ.items():
        if _SENSITIVE_ENV_NAME.search(name) and len(value) >= 4:
            message = message.replace(value, "[REDACTED_CONFIG]")
    message = _URL_VALUE.sub("[REDACTED_URL]", message)
    message = _BEARER_VALUE.sub("Bearer [REDACTED]", message)
    message = _SECRET_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}=[REDACTED]", message
    )
    message = " ".join(message.split())
    return message[:_MAX_SAFE_EXCEPTION_MESSAGE]


def _safe_persistence_message(exc: DiscoveryPersistenceError) -> str:
    message = str(exc).strip()
    if message in _SAFE_PERSISTENCE_MESSAGES:
        return message
    return "discovery persistence contract rejected"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def derive_cycle_selection_seed(
    *,
    campaign_selection_seed: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    discovery_batch_id: str,
) -> str:
    seed = str(campaign_selection_seed or "").strip()
    if not seed:
        raise CombinedDiscoveryError("MISSING_SELECTION_SEED")
    material = (
        f"{SEED_DOMAIN}{seed}|{campaign_id}|{run_id}|{cycle_id}|{discovery_batch_id}"
    )
    return _sha256_text(material)


def resolve_campaign_selection_seed(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    configuration_id: str,
    fallback: str,
) -> str:
    """The campaign selection seed, resolved exactly once for every writer.

    The persisted immutable configuration wins when it carries a seed; the
    invocation's own selection seed is the fallback. Both the combined discovery
    executor and the pre-lifecycle temporal refresh resolve through here so the
    canonical discovery-batch payload cannot diverge between them.
    """
    row = connection.execute(
        "SELECT configuration_json FROM "
        "printer_memory_factory_campaign_configurations "
        "WHERE campaign_id = ? AND configuration_id = ?",
        (campaign_id, configuration_id),
    ).fetchone()
    configured = ""
    if row is not None:
        try:
            configured = str(
                (json.loads(row["configuration_json"]) or {}).get(
                    "campaign_selection_seed"
                )
                or ""
            ).strip()
        except (json.JSONDecodeError, AttributeError, TypeError):
            configured = ""
    seed = configured or str(fallback or "").strip()
    if not seed:
        raise CombinedDiscoveryError("MISSING_SELECTION_SEED")
    return seed


def canonical_cycle_discovery_batch_id(
    *, campaign_id: str, run_id: str, cycle_id: str
) -> str:
    """The one canonical discovery-batch identity for an exact cycle.

    ``printer_discovery_batches`` is UNIQUE on ``cycle_id``: a cycle owns exactly
    one batch. Every writer must therefore derive the identity here rather than
    inventing its own, or the second writer collides instead of reusing.
    """
    return f"discovery-batch:{campaign_id}:{run_id}:{cycle_id}"


def ensure_cycle_discovery_batch(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    cycle_id: str,
    cycle_cutoff: str,
    policy_version: str,
    provider_contract_versions: Mapping[str, Any],
    git_provenance_identity: str,
    campaign_selection_seed: str,
    pump_continuity_state: str = "UNKNOWN",
    batch_state: str = "DISCOVERING",
    now: str | None = None,
) -> str:
    """Create-or-reuse the exact cycle's discovery batch, and return its id.

    ``insert_discovery_batch`` is idempotent for a byte-identical canonical
    payload, so whichever lawful owner reaches the cycle first creates the batch
    and every later owner reuses it. ``batch_state`` is deliberately outside the
    canonical hash, so a pre-lifecycle writer and the combined executor agree.

    This is the single derivation shared by the combined discovery executor and
    the pre-lifecycle temporal refresh. Duplicating it would reintroduce the
    ``UNIQUE (cycle_id)`` collision the shared helper exists to prevent.
    """
    discovery_batch_id = canonical_cycle_discovery_batch_id(
        campaign_id=campaign_id, run_id=run_id, cycle_id=cycle_id
    )
    cycle_seed = derive_cycle_selection_seed(
        campaign_selection_seed=campaign_selection_seed,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        discovery_batch_id=discovery_batch_id,
    )
    insert_discovery_batch(
        connection,
        discovery_batch_id=discovery_batch_id,
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        run_id=run_id,
        cycle_id=cycle_id,
        cycle_cutoff=cycle_cutoff,
        policy_version=policy_version,
        provider_contract_versions=dict(provider_contract_versions),
        git_provenance_identity=git_provenance_identity,
        campaign_selection_seed_identity=_sha256_text(campaign_selection_seed),
        cycle_seed_hash=_sha256_text(cycle_seed),
        pump_continuity_state=pump_continuity_state,
        batch_state=batch_state,
        now=now,
    )
    return discovery_batch_id


def _fisher_yates(items: Sequence[Any], seed_hex: str) -> list[Any]:
    ordered = list(items)
    counter = 0
    for index in range(len(ordered) - 1, 0, -1):
        digest = hashlib.sha256(f"{seed_hex}|fy|{counter}".encode("utf-8")).digest()
        choice = int.from_bytes(digest[:8], "big") % (index + 1)
        ordered[index], ordered[choice] = ordered[choice], ordered[index]
        counter += 1
    return ordered


def _verification_key(cycle_seed: str, domain: str, token_identity: str) -> str:
    return _sha256_text(f"{cycle_seed}|{domain}|{token_identity}")


def _market_identity(venue: str, pool: str) -> str:
    return f"solana-mainnet:{venue}:{pool}"


def _token_identity(mint: str) -> str:
    return f"solana-mainnet:{mint}"


class CombinedPumpfunCampaignExecutor:
    """Fixture-backed combined discovery execution owner for 7A injection."""

    def __init__(
        self,
        fixtures: CombinedDiscoveryFixtures,
        *,
        diagnostic_fault_injector: Callable[[str], None] | None = None,
        rollback: Callable[[sqlite3.Connection], None] | None = None,
    ) -> None:
        self.fixtures = fixtures
        self._last_canonical: tuple[object, ...] | None = None
        self._persistence_stage = "DISCOVERY_CYCLE_INITIALIZATION"
        self._persistence_object_kind = "discovery_batch"
        self._diagnostic_fault_injector = diagnostic_fault_injector
        self._rollback = rollback or (lambda connection: connection.rollback())
        self._diagnostic_context: dict[str, Any] = {}

    def _reset_diagnostic_context(self) -> None:
        self._diagnostic_context = {
            "discovery_stage": "DISCOVERY_CYCLE_INITIALIZATION",
            "work_type": None,
            "discovery_batch_id": None,
            "discovery_work_id": None,
            "scheduler_job_id": None,
            "enqueue_completed": False,
            "scheduler_job_created_this_attempt": False,
            "claim_returned": False,
            "claim_result": None,
            "claim_status": None,
            "expected_lock_owner": None,
            "observed_lock_owner": None,
            "discovery_work_insertion_completed": False,
            "observed_scheduler_transitions": [],
        }

    def _set_diagnostic_stage(self, stage: str, **updates: Any) -> None:
        self._diagnostic_context["discovery_stage"] = stage
        self._diagnostic_context.update(updates)

    def _inject_diagnostic_fault(self, stage: str) -> None:
        if self._diagnostic_fault_injector is not None:
            self._diagnostic_fault_injector(stage)

    def _mark_persistence(self, stage: str, object_kind: str) -> None:
        self._persistence_stage = stage
        self._persistence_object_kind = object_kind
        self._diagnostic_context["discovery_stage"] = stage

    @staticmethod
    def _allowlisted_row(
        row: sqlite3.Row | None, fields: Sequence[str]
    ) -> dict[str, Any] | None:
        if row is None:
            return None
        return {field: row[field] for field in fields}

    def _pre_rollback_snapshot(
        self, connection: sqlite3.Connection
    ) -> dict[str, Any]:
        context = self._diagnostic_context
        job_id = context.get("scheduler_job_id")
        work_id = context.get("discovery_work_id")
        batch_id = context.get("discovery_batch_id")
        scheduler_row = None
        if job_id is not None:
            scheduler_row = connection.execute(
                """
                SELECT id, job_name, job_kind, target_table, target_id, status,
                       scheduled_for, started_at, finished_at, locked_at,
                       lock_owner, retry_count, created_at, updated_at
                FROM printer_scheduler_jobs WHERE id = ?
                """,
                (int(job_id),),
            ).fetchone()
        work_row = None
        if work_id:
            work_row = connection.execute(
                """
                SELECT discovery_work_id, discovery_batch_id, campaign_id, run_id,
                       cycle_id, scheduler_job_id, work_type, work_state,
                       deadline_at, first_terminal_cause, terminal_at,
                       created_at, updated_at
                FROM printer_discovery_work WHERE discovery_work_id = ?
                """,
                (str(work_id),),
            ).fetchone()
        batch_row = None
        if batch_id:
            batch_row = connection.execute(
                """
                SELECT discovery_batch_id, campaign_id, configuration_id, run_id,
                       cycle_id, batch_state, first_terminal_cause, terminal_at,
                       created_at
                FROM printer_discovery_batches WHERE discovery_batch_id = ?
                """,
                (str(batch_id),),
            ).fetchone()
        expected_to_disappear = []
        if batch_row is not None:
            expected_to_disappear.append("discovery_batch_attempt_changes")
        if work_row is not None:
            expected_to_disappear.append("discovery_work_attempt_changes")
        if scheduler_row is not None and context.get(
            "scheduler_job_created_this_attempt"
        ):
            expected_to_disappear.append("scheduler_job_attempt_row")
        return {
            "captured_before_rollback": True,
            "connection_in_transaction": bool(connection.in_transaction),
            "visibility": "ACTIVE_TRANSACTION_MAY_INCLUDE_UNCOMMITTED_STATE",
            "durable_committed_outside_transaction": {
                "new_attempt_rows_proven_durable": False,
                "scheduler_job_preexisting": bool(
                    scheduler_row is not None
                    and not context.get("scheduler_job_created_this_attempt")
                ),
            },
            "expected_to_disappear_after_successful_rollback": expected_to_disappear,
            "scheduler_job": self._allowlisted_row(
                scheduler_row,
                (
                    "id",
                    "job_name",
                    "job_kind",
                    "target_table",
                    "target_id",
                    "status",
                    "scheduled_for",
                    "started_at",
                    "finished_at",
                    "locked_at",
                    "lock_owner",
                    "retry_count",
                    "created_at",
                    "updated_at",
                ),
            ),
            "discovery_work": self._allowlisted_row(
                work_row,
                (
                    "discovery_work_id",
                    "discovery_batch_id",
                    "campaign_id",
                    "run_id",
                    "cycle_id",
                    "scheduler_job_id",
                    "work_type",
                    "work_state",
                    "deadline_at",
                    "first_terminal_cause",
                    "terminal_at",
                    "created_at",
                    "updated_at",
                ),
            ),
            "discovery_batch": self._allowlisted_row(
                batch_row,
                (
                    "discovery_batch_id",
                    "campaign_id",
                    "configuration_id",
                    "run_id",
                    "cycle_id",
                    "batch_state",
                    "first_terminal_cause",
                    "terminal_at",
                    "created_at",
                ),
            ),
            "observed_scheduler_transitions": list(
                context.get("observed_scheduler_transitions") or []
            ),
            "accountable_identity_projection": {
                "discovery_batch_id": batch_id,
                "discovery_work_id": work_id,
                "scheduler_job_id": job_id,
                "work_type": context.get("work_type"),
            },
        }

    @staticmethod
    def _secondary_failure(exc: BaseException, *, stage: str) -> dict[str, str]:
        return {
            "stage": stage,
            "exception_class": type(exc).__name__,
            "sanitized_message": _safe_exception_message(exc),
        }

    def _build_shared_failure_diagnostics(
        self, connection: sqlite3.Connection, exc: BaseException
    ) -> dict[str, Any]:
        context = dict(self._diagnostic_context)
        context["observed_scheduler_transitions"] = list(
            context.get("observed_scheduler_transitions") or []
        )
        details: dict[str, Any] = {
            "schema_version": "DISCOVERY_SHARED_FAILURE_DIAGNOSTIC_V1",
            "first_terminal_cause": "SHARED_FAILURE",
            "first_failure": {
                "classification": "SHARED_FAILURE",
                "exception_class": type(exc).__name__,
                "sanitized_message": _safe_exception_message(exc),
            },
            "discovery": context,
            "pre_rollback_state": None,
            "rollback": {
                "started": False,
                "completed": False,
            },
            "secondary_failures": [],
        }
        try:
            details["pre_rollback_state"] = self._pre_rollback_snapshot(connection)
        except Exception as snapshot_exc:
            details["secondary_failures"].append(
                self._secondary_failure(
                    snapshot_exc, stage="PRE_ROLLBACK_SNAPSHOT"
                )
            )
        return details

    def _rollback_with_diagnostics(
        self, connection: sqlite3.Connection, details: dict[str, Any]
    ) -> None:
        details["rollback"]["started"] = True
        try:
            self._rollback(connection)
        except Exception as rollback_exc:
            details["secondary_failures"].append(
                self._secondary_failure(rollback_exc, stage="ROLLBACK")
            )
        else:
            details["rollback"]["completed"] = True

    def execute(
        self,
        *,
        command: AbstractCampaignCommand,
        source_governor: OwnerPort,
        central_scheduler: OwnerPort,
    ) -> CampaignExecutionResult:
        if source_governor.owner_kind != SOURCE_GOVERNOR_OWNER or not source_governor.available:
            raise CombinedDiscoveryError("SOURCE_GOVERNOR_UNAVAILABLE")
        if (
            central_scheduler.owner_kind != CENTRAL_SCHEDULER_OWNER
            or not central_scheduler.available
        ):
            raise CombinedDiscoveryError("CENTRAL_SCHEDULER_UNAVAILABLE")

        started = datetime.now(timezone.utc)
        self._reset_diagnostic_context()
        self._persistence_stage = "DISCOVERY_CYCLE_INITIALIZATION"
        self._persistence_object_kind = "discovery_batch"
        usage = _Usage()
        from printer_v1.db.sqlite_write_contracts import connect_operational

        connection = connect_operational(command.db_path)
        terminal = "COMPLETED"
        cause = "DISCOVERY_CYCLE_COMPLETED"
        cancellation: str | None = None
        fault_details: dict[str, Any] | None = None
        try:
            if self.fixtures.force_shared_fault:
                raise CombinedDiscoveryError(self.fixtures.force_shared_fault)
            result_meta = self._run_cycle(connection, command, usage)
            if result_meta.get("terminal_status"):
                terminal = str(result_meta["terminal_status"])
                cause = str(result_meta["first_terminal_cause"])
                cancellation = result_meta.get("cancellation_reason")
            connection.commit()
        except CombinedDiscoveryError as exc:
            connection.rollback()
            terminal = "FAILED"
            cause = exc.code
            cancellation = "SHARED_FAILURE" if exc.code.startswith("SHARED") else None
            usage.failures = max(usage.failures, 1)
        except DiscoveryPersistenceError as exc:
            connection.rollback()
            terminal = "FAILED"
            cause = "PERSISTENCE_FAULT"
            cancellation = "SHARED_FAILURE"
            usage.failures = max(usage.failures, 1)
            fault_details = {
                "exception_type": type(exc).__name__,
                "safe_message": _safe_persistence_message(exc),
                "persistence_stage": self._persistence_stage,
                "object_kind": self._persistence_object_kind,
                "first_terminal_cause": cause,
                "lifecycle_started": False,
            }
        except Exception as exc:
            fault_details = self._build_shared_failure_diagnostics(connection, exc)
            self._rollback_with_diagnostics(connection, fault_details)
            terminal = "FAILED"
            cause = "SHARED_FAILURE"
            cancellation = "SHARED_FAILURE"
            usage.failures = max(usage.failures, 1)
        finally:
            connection.close()

        elapsed = int((datetime.now(timezone.utc) - started).total_seconds())
        accountable_stage_started = bool(
            self._diagnostic_context.get("claim_result")
            == LockResult.ACQUIRED.value
            or self._diagnostic_context.get("discovery_work_insertion_completed")
            or "SCHEDULER_CLAIM"
            in tuple(
                self._diagnostic_context.get("observed_scheduler_transitions")
                or ()
            )
            or usage.scheduler_work > 1
        )
        return CampaignExecutionResult(
            terminal_status=terminal,
            first_terminal_cause=cause,
            cancellation_reason=cancellation,
            cycles=1,
            duration_seconds=min(elapsed, command.ceilings.duration_seconds),
            source_calls=usage.source_calls,
            scheduler_work=usage.scheduler_work,
            storage_bytes=usage.storage_bytes,
            failures=usage.failures,
            source_governor_used=True,
            central_scheduler_used=True,
            selective_continuation_preserved=True,
            support_5m_only=True,
            successor_created=False,
            restart_created=False,
            fault_details=fault_details,
            accountable_stage_started=accountable_stage_started,
        )

    def _run_cycle(
        self,
        connection: sqlite3.Connection,
        command: AbstractCampaignCommand,
        usage: _Usage,
    ) -> dict[str, Any]:
        fixtures = self.fixtures
        campaign_id = command.campaign_id
        configuration_id = command.configuration_id
        run_id = command.run_id
        cycle_id = fixtures.cycle_id
        now = fixtures.evaluated_at

        # 1-2. Load identities and validate immutable intake inputs.
        row = connection.execute(
            """
            SELECT c.campaign_state, c.policy_version, cfg.configuration_json,
                   cfg.configuration_hash, r.run_state
            FROM printer_memory_factory_campaigns AS c
            JOIN printer_memory_factory_campaign_configurations AS cfg
              ON cfg.campaign_id = c.campaign_id AND cfg.configuration_id = ?
            JOIN printer_memory_factory_campaign_runs AS r
              ON r.campaign_id = c.campaign_id AND r.run_id = ?
            WHERE c.campaign_id = ?
            """,
            (configuration_id, run_id, campaign_id),
        ).fetchone()
        if row is None:
            raise CombinedDiscoveryError("OWNERSHIP_MISMATCH")
        if row["configuration_hash"] != command.configuration_hash:
            raise CombinedDiscoveryError("SHARED_CONFIGURATION_MISMATCH")
        if row["policy_version"] != command.policy_version:
            raise CombinedDiscoveryError("SHARED_POLICY_MISMATCH")
        try:
            configuration = json.loads(row["configuration_json"])
        except json.JSONDecodeError as exc:
            raise CombinedDiscoveryError("SHARED_CONFIGURATION_MISMATCH") from exc
        # Resolved through the shared owner so the pre-lifecycle temporal
        # refresh derives byte-identical batch identity for this cycle.
        seed = str(
            configuration.get("campaign_selection_seed")
            or fixtures.campaign_selection_seed
            or ""
        ).strip()
        _shared_seed = resolve_campaign_selection_seed(
            connection,
            campaign_id=campaign_id,
            configuration_id=configuration_id,
            fallback=str(fixtures.campaign_selection_seed or ""),
        )
        if seed and _shared_seed != seed:
            raise CombinedDiscoveryError("SHARED_SELECTION_SEED_MISMATCH")
        if not seed:
            raise CombinedDiscoveryError("MISSING_SELECTION_SEED")

        cycle = connection.execute(
            """
            SELECT cycle_id, cycle_state FROM printer_memory_factory_campaign_cycles
            WHERE cycle_id = ? AND run_id = ? AND campaign_id = ?
            """,
            (cycle_id, run_id, campaign_id),
        ).fetchone()
        if cycle is None:
            raise CombinedDiscoveryError("OWNERSHIP_MISMATCH")

        discovery_batch_id = canonical_cycle_discovery_batch_id(
            campaign_id=campaign_id, run_id=run_id, cycle_id=cycle_id
        )
        self._set_diagnostic_stage(
            "DISCOVERY_BATCH_CREATE",
            discovery_batch_id=discovery_batch_id,
        )
        cycle_seed = derive_cycle_selection_seed(
            campaign_selection_seed=seed,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            discovery_batch_id=discovery_batch_id,
        )
        cycle_seed_hash = _sha256_text(cycle_seed)

        # Discovery batch. Create-or-reuse through the one shared derivation: a
        # lawful pre-lifecycle temporal refresh may already own this cycle's
        # batch, and the canonical payload is identical either way.
        self._mark_persistence("DISCOVERY_BATCH_CREATE", "discovery_batch")
        ensure_cycle_discovery_batch(
            connection,
            campaign_id=campaign_id,
            configuration_id=configuration_id,
            run_id=run_id,
            cycle_id=cycle_id,
            cycle_cutoff=fixtures.cycle_cutoff,
            policy_version=command.policy_version,
            provider_contract_versions=dict(fixtures.provider_contract_versions),
            git_provenance_identity=fixtures.git_provenance_identity,
            campaign_selection_seed=seed,
            pump_continuity_state="UNKNOWN",
            batch_state="DISCOVERING",
            now=now,
        )
        usage.bump_storage(512)

        observations: list[_Observation] = []
        provider_reports: list[dict[str, Any]] = []

        # 3-5. Provider work through Central Scheduler + Source Governor.
        retained_source_ids_before: dict[str, set[int]] | None = None
        retained_reconciliation: dict[str, Any] | None = None
        if fixtures.memory_activation_set is not None:
            try:
                validate_memory_activation_set(
                    connection,
                    fixtures.memory_activation_set,
                    now=now,
                    expected_ownership=(
                        command.campaign_id,
                        command.run_id,
                        fixtures.cycle_id,
                    ),
                )
            except MemoryObservationActivationError as exc:
                raise CombinedDiscoveryError(exc.code, exc.detail) from exc
            # Capture exact source-row identity sets before retained projection.
            retained_source_ids_before = measure_source_row_ids(connection)
            observations.extend(
                self._run_retained_evidence_lane(
                    connection,
                    command,
                    usage,
                    discovery_batch_id,
                    fixtures.memory_activation_set,
                    now,
                )
            )
        else:
            observations.extend(
                self._run_direct_lane(
                    connection, command, usage, discovery_batch_id, observations
                )
            )
            observations.extend(
                self._run_secondary_lane(
                    connection,
                    command,
                    usage,
                    discovery_batch_id,
                    work_type=GECKO_WORK_TYPE,
                    ops=fixtures.gecko_ops,
                    lane_name="geckoterminal",
                )
            )
            observations.extend(
                self._run_secondary_lane(
                    connection,
                    command,
                    usage,
                    discovery_batch_id,
                    work_type=TRACKER_WORK_TYPE,
                    ops=fixtures.tracker_ops,
                    lane_name="solana_tracker",
                )
            )
            observations.extend(
                self._run_secondary_lane(
                    connection,
                    command,
                    usage,
                    discovery_batch_id,
                    work_type=DEXSCREENER_WORK_TYPE,
                    ops=fixtures.dexscreener_ops,
                    lane_name="dexscreener",
                )
            )

        if usage.observations > INTAKE_OBSERVATIONS:
            raise CombinedDiscoveryError("OBSERVATION_CEILING")
        if len(usage.unique_mints) > INTAKE_UNIQUE_MINTS:
            raise CombinedDiscoveryError("UNIQUE_MINT_CEILING")

        # 6. Merge by exact mint/market/lifecycle.
        merge_work = self._create_work(
            connection,
            command,
            usage,
            discovery_batch_id,
            "DISCOVERY_IDENTITY_MERGE",
            now,
        )
        merged = self._merge(observations, discovery_batch_id)
        for candidate in merged.values():
            if (
                fixtures.holder_evidence_eligibility
                and fixtures.memory_activation_set is None
            ):
                holder_fact = fixtures.holder_evidence_eligibility.get(
                    candidate.mint.lower()
                )
                if holder_fact is None or holder_fact.get("eligible") is not True:
                    candidate.gaps.append(
                        {
                            "kind": "HOLDER_EVIDENCE_INELIGIBLE",
                            "detail": str(
                                (holder_fact or {}).get(
                                    "reason", "HOLDER_EVIDENCE_NOT_EVALUATED"
                                )
                            ),
                            "source_name": (holder_fact or {}).get("source_name"),
                        }
                    )
            self._mark_persistence("DISCOVERY_CANDIDATE_MERGE", "merged_candidate")
            insert_merged_candidate(
                connection,
                merged_candidate_id=candidate.merged_candidate_id,
                discovery_batch_id=discovery_batch_id,
                campaign_id=campaign_id,
                run_id=run_id,
                cycle_id=cycle_id,
                mint_identity=candidate.mint,
                market_identity=candidate.market_identity,
                lifecycle_identity=candidate.lifecycle,
                channel_labels=tuple(sorted(candidate.channels)),
                identity_conflicts=candidate.conflicts,
                evidence_gaps=candidate.gaps,
                origin_verification_state=candidate.origin_state,
                pumpswap_confirmation_state=candidate.pumpswap_state,
                now=now,
            )
            for ordinal, obs_id in enumerate(candidate.observation_ids, start=1):
                self._mark_persistence(
                    "DISCOVERY_CANDIDATE_CONTRIBUTION", "candidate_contribution"
                )
                link_candidate_contribution(
                    connection,
                    merged_candidate_id=candidate.merged_candidate_id,
                    observation_id=obs_id,
                    contribution_ordinal=ordinal,
                    now=now,
                )
        self._terminalize_work(connection, merge_work, "SUCCEEDED", "MERGE_COMPLETE", now)

        # 7-9. Origin verification admission + direct proof + PumpSwap.
        self._origin_and_pumpswap(
            connection, command, usage, discovery_batch_id, cycle_seed, merged, now
        )

        # 10-12. Gates, cooldown, uniform selection.
        gates_work = self._create_work(
            connection,
            command,
            usage,
            discovery_batch_id,
            "DISCOVERY_FIXED_ELIGIBILITY_GATES",
            now,
        )
        eligible = self._apply_gates(
            connection, command, fixtures, discovery_batch_id, merged, usage
        )
        self._terminalize_work(connection, gates_work, "SUCCEEDED", "GATES_COMPLETE", now)

        select_work = self._create_work(
            connection,
            command,
            usage,
            discovery_batch_id,
            "DISCOVERY_UNIFORM_SELECTION",
            now,
        )
        vacancies = list(fixtures.vacant_slot_ordinals)
        if fixtures.mode == "INITIAL":
            vacancies = [1, 2]
        if fixtures.memory_activation_set is not None:
            eligible_by_identity = {
                (candidate.mint, candidate.market_identity.rsplit(":", 1)[-1]): candidate
                for candidate in eligible
            }
            selected = []
            for frozen in fixtures.memory_activation_set.selected:
                candidate = eligible_by_identity.get((frozen.mint, frozen.pool))
                if candidate is None:
                    raise CombinedDiscoveryError(
                        "FROZEN_SELECTED_CANDIDATE_GATE_FAILED", frozen.mint
                    )
                selected.append(candidate)
        else:
            selected = self._select(
                eligible, cycle_seed, vacancy_count=len(vacancies)
            )
        if fixtures.mode == "INITIAL" and len(selected) < 2:
            tracking_causes = {
                HANDOFF_ACTIVE_CONFLICT,
                HANDOFF_COOLDOWN_REOPEN_REQUIRED,
                HANDOFF_TERMINAL_REOPEN_REQUIRED,
                HANDOFF_UNSUPPORTED_STATE,
            }
            shortfall_cause = next(
                (
                    candidate.first_failed_gate
                    for candidate in sorted(
                        merged.values(), key=lambda item: item.merged_candidate_id
                    )
                    if candidate.first_failed_gate in tracking_causes
                ),
                "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL",
            )
            self._terminalize_work(
                connection,
                select_work,
                "FAILED",
                shortfall_cause,
                now,
            )
            # Terminalize any still-open discovery work rows for this batch so
            # supervision cleanup does not leave RUNNING discovery work.
            connection.execute(
                """
                UPDATE printer_discovery_work
                SET work_state = 'FAILED',
                    first_terminal_cause = COALESCE(first_terminal_cause, ?),
                    terminal_at = COALESCE(terminal_at, ?),
                    updated_at = ?
                WHERE discovery_batch_id = ?
                  AND work_state IN ('PENDING', 'RUNNING', 'COOLDOWN')
                """,
                (
                    shortfall_cause,
                    now,
                    now,
                    discovery_batch_id,
                ),
            )
            # V2-9.7E.47 A2: every linked Scheduler job follows its work row
            # terminally, through the committed Scheduler owner.
            reconcile_discovery_work_jobs(
                connection,
                discovery_batch_id=discovery_batch_id,
                abandoned_cause=shortfall_cause,
            )
            self._mark_discovery_batch_failed(
                connection,
                discovery_batch_id,
                shortfall_cause,
                now,
            )
            self._persist_reports(
                connection, command, discovery_batch_id, provider_reports, usage, now
            )
            return {
                "terminal_status": "FAILED",
                "first_terminal_cause": shortfall_cause,
                "cancellation_reason": None,
            }
        self._terminalize_work(
            connection, select_work, "SUCCEEDED", "SELECTION_COMPLETE", now
        )

        # 13-15. Persist selection + transactional handoff + first 15m jobs.
        selection_batch_id = f"selection:{discovery_batch_id}"
        try:
            self._persist_selection_and_handoff(
                connection,
                command,
                usage,
                discovery_batch_id,
                selection_batch_id,
                selected,
                vacancies,
                cycle_seed,
                now,
            )
        except CombinedDiscoveryError as exc:
            # Initial activation failures keep discovery facts but must not leave
            # partial slots/queue/15m jobs (savepoint already rolled those back).
            if fixtures.mode == "INITIAL" and exc.code in {
                "HANDOFF_PREFLIGHT_FAILED",
                "HANDOFF_BEFORE_FIRST",
                "HANDOFF_DURING_SECOND",
                "FIRST_15M_JOB_FAILED",
                "DUPLICATE_ACTIVE_TRACKING",
                "COOLDOWN_REOPEN_REQUIRED",
                "TERMINAL_TRACKING_STATE",
                "UNSUPPORTED_TRACKING_QUEUE_STATE",
                "CONFLICTING_SLOT",
                "HEALTHY_SLOT_MUTATION",
                "HANDOFF_CEILING",
                "FORBIDDEN_WINDOW_ACTIVATION",
                "INITIAL_HANDOFF_INCOMPLETE",
            }:
                self._mark_discovery_batch_failed(
                    connection, discovery_batch_id, exc.code, now
                )
                self._persist_reports(
                    connection, command, discovery_batch_id, provider_reports, usage, now
                )
                return {
                    "terminal_status": "FAILED",
                    "first_terminal_cause": exc.code,
                    "cancellation_reason": None,
                    "selected_mints": [],
                    "cycle_seed": cycle_seed,
                }
            raise

        self._persist_reports(
            connection, command, discovery_batch_id, provider_reports, usage, now
        )

        if (
            fixtures.memory_activation_set is not None
            and retained_source_ids_before is not None
        ):
            retained_source_ids_after = measure_source_row_ids(connection)
            retained_reconciliation = reconcile_activation_source_rows(
                before=retained_source_ids_before,
                after=retained_source_ids_after,
                activation=fixtures.memory_activation_set,
            )
            if retained_reconciliation.get("reconciliation_status") != "PASS":
                raise CombinedDiscoveryError(
                    "RETAINED_ACTIVATION_SOURCE_ROW_RECONCILIATION_BLOCKED",
                    str(
                        retained_reconciliation.get("newly_created_source_request_ids")
                        or retained_reconciliation.get(
                            "newly_created_source_response_ids"
                        )
                        or retained_reconciliation.get(
                            "newly_created_source_failure_ids"
                        )
                        or "measured non-zero source-row delta"
                    ),
                )

        canonical = (
            discovery_batch_id,
            tuple(sorted(m.mint for m in selected)),
            tuple(sorted(usage.unique_mints)),
            usage.source_calls,
            usage.scheduler_work,
            usage.handoffs,
        )
        if self._last_canonical is not None and self._last_canonical != canonical:
            # Conflicting replay against a prior successful identical-owner run.
            raise CombinedDiscoveryError("CONFLICTING_REPLAY")
        self._last_canonical = canonical
        result_payload: dict[str, Any] = {
            "terminal_status": "COMPLETED",
            "first_terminal_cause": "DISCOVERY_CYCLE_COMPLETED",
            "cancellation_reason": None,
            "selected_mints": [m.mint for m in selected],
            "cycle_seed": cycle_seed,
        }
        if retained_reconciliation is not None:
            result_payload["retained_evidence_reconciliation"] = retained_reconciliation
            result_payload["selection_reason"] = MEMORY_OBSERVATION_SELECTION_REASON
        return result_payload

    def _create_work(
        self,
        connection: sqlite3.Connection,
        command: AbstractCampaignCommand,
        usage: _Usage,
        discovery_batch_id: str,
        work_type: str,
        now: str,
    ) -> str:
        """Enqueue, exactly claim, then mark discovery work RUNNING.

        Approved order (claim-at-work-start):
        enqueue -> claim_due_job(exact linked id) -> equality checks ->
        insert discovery work RUNNING -> governed work later.
        """
        usage.bump_scheduler()
        job_name = f"{work_type}:{discovery_batch_id}"
        work_id = f"work:{work_type}:{discovery_batch_id}"
        lock_owner = f"discovery-work:{work_id}"
        self._set_diagnostic_stage(
            "DISCOVERY_WORK_BEFORE_ENQUEUE",
            work_type=work_type,
            discovery_batch_id=discovery_batch_id,
            discovery_work_id=work_id,
            scheduler_job_id=None,
            enqueue_completed=False,
            scheduler_job_created_this_attempt=False,
            claim_returned=False,
            claim_result=None,
            claim_status=None,
            expected_lock_owner=lock_owner,
            observed_lock_owner=None,
            discovery_work_insertion_completed=False,
            observed_scheduler_transitions=[],
        )
        self._inject_diagnostic_fault("DISCOVERY_WORK_BEFORE_ENQUEUE")
        discovery_now = datetime.fromisoformat(now.replace("Z", "+00:00"))
        result, job_id = enqueue_job(
            connection,
            job_name=job_name,
            job_kind=JobKind.DISCOVERY_REFRESH,
            target_table="printer_discovery_batches",
            scheduled_for=discovery_now,
        )
        created_this_attempt = job_id is not None
        if job_id is None:
            # Lawful rebind only for the exact same name/kind active row.
            row = connection.execute(
                """
                SELECT id, job_name, job_kind, status, lock_owner, locked_at,
                       scheduled_for
                FROM printer_scheduler_jobs
                WHERE job_name = ? AND job_kind = ?
                ORDER BY id DESC LIMIT 1
                """,
                (job_name, JobKind.DISCOVERY_REFRESH.value),
            ).fetchone()
            if row is None:
                raise CombinedDiscoveryError("SCHEDULER_JOB_CREATE_FAILED", str(result))
            if (
                str(row["job_name"]) != job_name
                or str(row["job_kind"]) != JobKind.DISCOVERY_REFRESH.value
            ):
                raise CombinedDiscoveryError(
                    "SCHEDULER_JOB_CREATE_FAILED", "rebind identity mismatch"
                )
            status = str(row["status"])
            if row["locked_at"] is not None or row["lock_owner"] is not None:
                raise CombinedDiscoveryError(
                    "DISCOVERY_SCHEDULER_CLAIM_ALREADY_OWNED",
                    str(row["lock_owner"] or "locked"),
                )
            if status == JobStatus.RUNNING.value:
                # Active without visible owner fields is still not stealable.
                raise CombinedDiscoveryError(
                    "DISCOVERY_SCHEDULER_CLAIM_ALREADY_OWNED",
                    f"rebind status not claimable:{status}",
                )
            if status not in {
                JobStatus.PENDING.value,
                JobStatus.COOLDOWN.value,
            }:
                raise CombinedDiscoveryError(
                    "DISCOVERY_SCHEDULER_CLAIM_NOT_ACQUIRED",
                    f"rebind status not claimable:{status}",
                )
            job_id = int(row["id"])
        self._set_diagnostic_stage(
            "DISCOVERY_WORK_AFTER_ENQUEUE_BEFORE_CLAIM",
            scheduler_job_id=int(job_id),
            enqueue_completed=True,
            scheduler_job_created_this_attempt=created_this_attempt,
        )
        if created_this_attempt:
            self._diagnostic_context["observed_scheduler_transitions"].append(
                "SCHEDULER_ENQUEUE"
            )
        self._inject_diagnostic_fault("DISCOVERY_WORK_AFTER_ENQUEUE_BEFORE_CLAIM")
        claimed = False
        claim_result = claim_due_job(
            connection,
            job_id=int(job_id),
            lock_owner=lock_owner,
            now=discovery_now,
        )
        self._diagnostic_context["claim_returned"] = True
        self._diagnostic_context["claim_result"] = claim_result.value
        if claim_result != LockResult.ACQUIRED:
            cause = {
                LockResult.NOT_FOUND: "DISCOVERY_SCHEDULER_CLAIM_NOT_FOUND",
                LockResult.NOT_DUE: "DISCOVERY_SCHEDULER_CLAIM_NOT_DUE",
                LockResult.ALREADY_LOCKED: "DISCOVERY_SCHEDULER_CLAIM_ALREADY_OWNED",
            }.get(claim_result, "DISCOVERY_SCHEDULER_CLAIM_NOT_ACQUIRED")
            self._terminalize_unstarted_discovery_scheduler_job(
                connection,
                job_id=int(job_id),
                expected_lock_owner=lock_owner,
                claimed=False,
            )
            raise CombinedDiscoveryError(cause, str(claim_result))
        claimed = True
        try:
            self._require_claimed_discovery_scheduler_identity(
                connection,
                job_id=int(job_id),
                job_name=job_name,
                lock_owner=lock_owner,
            )
        except CombinedDiscoveryError:
            self._terminalize_unstarted_discovery_scheduler_job(
                connection,
                job_id=int(job_id),
                expected_lock_owner=lock_owner,
                claimed=claimed,
            )
            raise
        self._diagnostic_context["claim_status"] = JobStatus.RUNNING.value
        self._diagnostic_context["observed_lock_owner"] = lock_owner
        self._diagnostic_context["observed_scheduler_transitions"].append(
            "SCHEDULER_CLAIM"
        )
        self._set_diagnostic_stage(
            "DISCOVERY_WORK_AFTER_CLAIM_BEFORE_INSERT"
        )
        self._inject_diagnostic_fault("DISCOVERY_WORK_AFTER_CLAIM_BEFORE_INSERT")
        try:
            self._mark_persistence("DISCOVERY_WORK_CREATE", "discovery_work")
            insert_discovery_work(
                connection,
                discovery_work_id=work_id,
                discovery_batch_id=discovery_batch_id,
                campaign_id=command.campaign_id,
                run_id=command.run_id,
                cycle_id=self.fixtures.cycle_id,
                scheduler_job_id=int(job_id),
                work_type=work_type,
                deadline_at=self.fixtures.cycle_cutoff,
                work_state="RUNNING",
                now=now,
            )
            self._diagnostic_context["discovery_work_insertion_completed"] = True
            self._require_discovery_work_link(
                connection,
                work_id=work_id,
                job_id=int(job_id),
                discovery_batch_id=discovery_batch_id,
                command=command,
                work_type=work_type,
            )
        except CombinedDiscoveryError:
            self._terminalize_unstarted_discovery_scheduler_job(
                connection,
                job_id=int(job_id),
                expected_lock_owner=lock_owner,
                claimed=claimed,
            )
            raise
        except Exception as exc:
            self._terminalize_unstarted_discovery_scheduler_job(
                connection,
                job_id=int(job_id),
                expected_lock_owner=lock_owner,
                claimed=claimed,
            )
            raise CombinedDiscoveryError(
                "DISCOVERY_SCHEDULER_JOB_LINK_MISMATCH", str(exc)
            ) from exc
        self._set_diagnostic_stage("DISCOVERY_WORK_RUNNING")
        return work_id

    def _require_claimed_discovery_scheduler_identity(
        self,
        connection: sqlite3.Connection,
        *,
        job_id: int,
        job_name: str,
        lock_owner: str,
    ) -> None:
        row = connection.execute(
            """
            SELECT id, job_name, job_kind, status, lock_owner, locked_at, started_at
            FROM printer_scheduler_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        if row is None:
            raise CombinedDiscoveryError(
                "DISCOVERY_SCHEDULER_CLAIM_IDENTITY_MISMATCH", "missing claimed job"
            )
        if (
            int(row["id"]) != int(job_id)
            or str(row["job_kind"]) != JobKind.DISCOVERY_REFRESH.value
            or str(row["job_name"]) != job_name
            or str(row["status"]) != JobStatus.RUNNING.value
            or str(row["lock_owner"] or "") != lock_owner
            or row["locked_at"] is None
            or row["started_at"] is None
        ):
            raise CombinedDiscoveryError(
                "DISCOVERY_SCHEDULER_CLAIM_IDENTITY_MISMATCH",
                (
                    f"id={row['id']} kind={row['job_kind']} name={row['job_name']} "
                    f"status={row['status']} lock_owner={row['lock_owner']}"
                ),
            )

    def _require_discovery_work_link(
        self,
        connection: sqlite3.Connection,
        *,
        work_id: str,
        job_id: int,
        discovery_batch_id: str,
        command: AbstractCampaignCommand,
        work_type: str,
    ) -> None:
        row = connection.execute(
            """
            SELECT discovery_work_id, discovery_batch_id, campaign_id, run_id,
                   cycle_id, scheduler_job_id, work_type, work_state
            FROM printer_discovery_work
            WHERE discovery_work_id = ?
            """,
            (work_id,),
        ).fetchone()
        if row is None:
            raise CombinedDiscoveryError(
                "DISCOVERY_SCHEDULER_JOB_LINK_MISMATCH", "missing discovery work"
            )
        if (
            str(row["discovery_work_id"]) != work_id
            or str(row["discovery_batch_id"]) != discovery_batch_id
            or str(row["campaign_id"]) != command.campaign_id
            or str(row["run_id"]) != command.run_id
            or str(row["cycle_id"]) != self.fixtures.cycle_id
            or int(row["scheduler_job_id"]) != int(job_id)
            or str(row["work_type"]) != work_type
            or str(row["work_state"]) != "RUNNING"
        ):
            raise CombinedDiscoveryError(
                "DISCOVERY_SCHEDULER_JOB_LINK_MISMATCH",
                (
                    f"work={row['discovery_work_id']} job={row['scheduler_job_id']} "
                    f"state={row['work_state']}"
                ),
            )

    def _terminalize_unstarted_discovery_scheduler_job(
        self,
        connection: sqlite3.Connection,
        *,
        job_id: int,
        expected_lock_owner: str,
        claimed: bool,
    ) -> None:
        """Terminalize only unstarted residue owned by this unit; never steal.

        Uses the committed Central Scheduler cancel owner. Leaves another
        worker's locked job untouched.
        """
        row = connection.execute(
            """
            SELECT id, status, lock_owner, locked_at
            FROM printer_scheduler_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        if row is None:
            return
        status = str(row["status"])
        if status not in {
            JobStatus.PENDING.value,
            JobStatus.RUNNING.value,
            JobStatus.COOLDOWN.value,
        }:
            return
        owner = None if row["lock_owner"] is None else str(row["lock_owner"])
        if claimed or owner == expected_lock_owner:
            cancel_job(connection, job_id=int(job_id))
            return
        if owner is None and status in {
            JobStatus.PENDING.value,
            JobStatus.COOLDOWN.value,
        }:
            # Unclaimed job created for this unit but never successfully claimed.
            cancel_job(connection, job_id=int(job_id))
            return
        # Another owner holds the lock — do not cancel or overwrite.

    def _terminalize_work(
        self,
        connection: sqlite3.Connection,
        work_id: str,
        state: str,
        cause: str,
        now: str,
    ) -> None:
        connection.execute(
            """
            UPDATE printer_discovery_work
            SET work_state = ?, first_terminal_cause = ?, terminal_at = ?, updated_at = ?
            WHERE discovery_work_id = ?
            """,
            (state, cause, now, now, work_id),
        )
        # V2-9.7E.47 A2: discovery work and its linked Scheduler job must agree
        # terminally. Before this repair the work row went terminal while the
        # DISCOVERY_REFRESH job it owns stayed PENDING for the whole lifecycle
        # (E.46 §10.2: 8 PENDING jobs against 8 SUCCEEDED work rows). The
        # transition always goes through the committed Scheduler owner; no
        # status is written by an unowned UPDATE.
        row = connection.execute(
            "SELECT scheduler_job_id FROM printer_discovery_work "
            "WHERE discovery_work_id = ?",
            (work_id,),
        ).fetchone()
        if row is None or row["scheduler_job_id"] is None:
            return
        terminal_status = terminalize_scheduler_job_for_work(
            connection,
            job_id=int(row["scheduler_job_id"]),
            work_state=state,
            cause=cause,
        )
        if work_id == self._diagnostic_context.get("discovery_work_id"):
            self._set_diagnostic_stage(
                "DISCOVERY_WORK_TERMINALIZED",
                observed_lock_owner=None,
            )
            transitions = self._diagnostic_context.get(
                "observed_scheduler_transitions"
            )
            if (
                terminal_status is not None
                and isinstance(transitions, list)
                and "SCHEDULER_TERMINAL" not in transitions
            ):
                transitions.append("SCHEDULER_TERMINAL")

    def _governed_request(
        self,
        connection: sqlite3.Connection,
        usage: _Usage,
        *,
        source_name: str,
        request_kind: str,
        now: str,
    ) -> int:
        decision = can_request_source(source_name, request_kind, usage.source_calls)
        if not decision.allowed:
            raise CombinedDiscoveryError("SOURCE_GOVERNOR_BYPASS", decision.reason)
        usage.bump_source()
        cursor = connection.execute(
            """
            INSERT INTO printer_source_requests(
                source_name, request_kind, requested_at, source_status, data_quality_label
            ) VALUES (?, ?, ?, 'COMPLETE', 'CLEAN_DATA')
            """,
            (source_name, request_kind, now),
        )
        return int(cursor.lastrowid)

    def _store_response(
        self,
        connection: sqlite3.Connection,
        usage: _Usage,
        *,
        request_id: int,
        source_name: str,
        now: str,
        payload: Any,
        status_code: int = 200,
    ) -> int:
        body = _canonical(payload)
        usage.bump_storage(len(body.encode("utf-8")))
        digest = _sha256_text(body)
        cursor = connection.execute(
            """
            INSERT INTO printer_source_responses(
                source_request_id, source_name, received_at, status_code,
                source_status, data_quality_label, response_hash, normalized_payload_json
            ) VALUES (?, ?, ?, ?, 'COMPLETE', 'CLEAN_DATA', ?, ?)
            """,
            (request_id, source_name, now, status_code, digest, body),
        )
        return int(cursor.lastrowid)

    def _store_failure(
        self,
        connection: sqlite3.Connection,
        usage: _Usage,
        *,
        source_name: str,
        request_kind: str,
        failure_type: str,
        now: str,
    ) -> int:
        usage.bump_failure()
        cursor = connection.execute(
            """
            INSERT INTO printer_source_failures(
                source_name, request_kind, failed_at, failure_type,
                source_status, data_quality_label
            ) VALUES (?, ?, ?, ?, 'FAILED', 'MISSING_CRITICAL_DATA')
            """,
            (source_name, request_kind, now, failure_type),
        )
        return int(cursor.lastrowid)

    def _run_retained_evidence_lane(
        self,
        connection: sqlite3.Connection,
        command: AbstractCampaignCommand,
        usage: _Usage,
        discovery_batch_id: str,
        activation: FrozenMemoryActivationSet,
        now: str,
    ) -> list[_Observation]:
        """Project already governed evidence without creating a source operation."""
        work_id = self._create_work(
            connection,
            command,
            usage,
            discovery_batch_id,
            DIRECT_WORK_TYPE,
            now,
        )
        observations: list[_Observation] = []
        linked: set[tuple[int, int]] = set()
        link_ordinal = 0
        for candidate in activation.selected:
            market_authority = (
                candidate.admission_authority.value == "MARKET_PRESENT_POOL"
            )
            retained_venue = (
                candidate.market_identity.rsplit(":", 2)[-2]
                if market_authority and candidate.market_identity.count(":") >= 2
                else PUMPSWAP_VENUE
            )
            for reference_ordinal, reference in enumerate(
                candidate.retained_evidence_references, start=1
            ):
                link_key = (
                    int(reference.source_request_id),
                    int(reference.source_response_id),
                )
                if link_key not in linked:
                    linked.add(link_key)
                    link_ordinal += 1
                    link_discovery_work_source(
                        connection,
                        discovery_work_id=work_id,
                        link_ordinal=link_ordinal,
                        source_request_id=link_key[0],
                        source_response_id=link_key[1],
                        now=now,
                    )
                observation_id = _batch_scoped_object_id(
                    "obs",
                    discovery_batch_id,
                    "retained",
                    candidate.slot_ordinal,
                    reference_ordinal,
                    candidate.mint,
                    candidate.pool,
                )
                # Provenance authority is the candidate's true provenance —
                # never derived from slot ordinal. Observation channel labels
                # remain the lawful CHANNELS vocabulary; mapping is provenance
                # based, not slot based.
                true_provenance = str(candidate.provenance or "")
                if true_provenance in {"LATEST_GRADUATED", "LATEST_PUMPFUN"}:
                    channel = "LATEST_PUMPFUN"
                elif true_provenance in {
                    "PERSISTED_GRADUATED",
                    "PERSISTED_ACTIVE",
                }:
                    channel = "ACTIVE_PUMPFUN"
                elif true_provenance in {"TRENDING_PUMPFUN", "TOP_PUMPFUN"}:
                    channel = true_provenance
                else:
                    # Migration 034 constrains the historical channel column to
                    # four legacy labels. ACTIVE_PUMPFUN is storage vocabulary
                    # only; factual provenance below remains UNKNOWN_ORIGIN and
                    # carries no Pump/PumpSwap claim.
                    channel = "ACTIVE_PUMPFUN" if market_authority else "TOP_PUMPFUN"
                factual = {
                    "network": "solana",
                    "mint": candidate.mint,
                    "pool": candidate.pool,
                    "venue": retained_venue,
                    "observed_at": reference.observed_at,
                    "evidence_role": reference.evidence_role.value,
                    "evidence_reuse_kind": (
                        "RETAINED_GOVERNED_EVIDENCE_REFERENCE"
                    ),
                    "slot_ordinal": candidate.slot_ordinal,
                    "true_provenance": true_provenance,
                    "channel_authority": true_provenance,
                    "readiness_id": activation.readiness_id,
                    "selection_seed": activation.selection_seed,
                    "selection_reason": MEMORY_OBSERVATION_SELECTION_REASON,
                    "legacy_role_field": "POSITIONAL_COMPATIBILITY_ONLY",
                }
                insert_provider_observation(
                    connection,
                    observation_id=observation_id,
                    discovery_batch_id=discovery_batch_id,
                    discovery_work_id=work_id,
                    campaign_id=command.campaign_id,
                    run_id=command.run_id,
                    cycle_id=self.fixtures.cycle_id,
                    source_name=reference.source_name,
                    request_kind=reference.request_kind,
                    channel=channel,
                    mint_identity=candidate.mint,
                    market_identity=candidate.market_identity,
                    lifecycle_identity=candidate.lifecycle_identity,
                    observed_at=reference.observed_at,
                    captured_at=now,
                    raw_payload_hash=reference.raw_payload_hash,
                    factual_payload=factual,
                    source_request_id=int(reference.source_request_id),
                    source_response_id=int(reference.source_response_id),
                    now=now,
                )
                observations.append(
                    _Observation(
                        observation_id=observation_id,
                        provider=reference.source_name,
                        request_kind=reference.request_kind,
                        channel=channel,
                        mint=candidate.mint,
                        pool=candidate.pool,
                        quote_mint="",
                        venue=retained_venue,
                        observed_at=reference.observed_at,
                        raw_payload_hash=reference.raw_payload_hash,
                        source_request_id=int(reference.source_request_id),
                        source_response_id=int(reference.source_response_id),
                        source_failure_id=None,
                        work_id=work_id,
                        pumpfun_origin_status=(
                            "UNKNOWN_ORIGIN"
                            if market_authority
                            else "PUMPFUN_ORIGIN_CONFIRMED"
                        ),
                        lifecycle=candidate.lifecycle_identity,
                        origin_route=candidate.activation_route,
                    )
                )
                usage.observations += 1
                usage.unique_mints.add(candidate.mint)
                usage.bump_storage(256)
        self._terminalize_work(
            connection,
            work_id,
            "SUCCEEDED",
            "RETAINED_GOVERNED_EVIDENCE_REFERENCE",
            now,
        )
        return observations

    def _run_direct_lane(
        self,
        connection: sqlite3.Connection,
        command: AbstractCampaignCommand,
        usage: _Usage,
        discovery_batch_id: str,
        existing: list[_Observation],
    ) -> list[_Observation]:
        del existing
        fixtures = self.fixtures
        now = fixtures.evaluated_at
        work_id = self._create_work(
            connection, command, usage, discovery_batch_id, DIRECT_WORK_TYPE, now
        )
        self._set_diagnostic_stage("DISCOVERY_WORK_GOVERNED_EXECUTION")
        self._inject_diagnostic_fault("DISCOVERY_WORK_GOVERNED_EXECUTION")
        if "direct" in fixtures.provider_failures_injected:
            # Checkpoint 3: persist the governed request identity before the
            # linked provider failure so request/failure causality is durable.
            req = self._governed_request(
                connection,
                usage,
                source_name="solana_rpc",
                request_kind="pumpfun_create_event_subscription",
                now=now,
            )
            fail_id = self._store_failure(
                connection,
                usage,
                source_name="solana_rpc",
                request_kind="pumpfun_create_event_subscription",
                failure_type=fixtures.provider_failures_injected["direct"],
                now=now,
            )
            link_discovery_work_source(
                connection,
                discovery_work_id=work_id,
                link_ordinal=1,
                source_request_id=req,
                source_failure_id=fail_id,
                now=now,
            )
            self._terminalize_work(connection, work_id, "FAILED", "DIRECT_PROVIDER_FAILED", now)
            return []

        observations: list[_Observation] = []
        # V2-9.7E.45: migration-discovered graduation-native proofs never enter the
        # create-origin registry and are activated through Route B below.
        grad_native_proofs: tuple[FixtureOriginProof, ...] = ()
        # Prefer explicit origin proofs for fixture simplicity; optional full cycle.
        if fixtures.direct_operations:
            # V2-9.7E.5 primary: signature-anchored finalized acquisition on the
            # create-exclusive index address. No getSlot cutoff, no live session.
            prior = fixtures.prior_cursor or load_origin_cursor(connection)
            result = run_acquisition_cycle(
                fixtures.direct_operations, prior_cursor=prior
            )
            usage.underlying_rpc += result.accounting.underlying_rpc_operations
            if usage.underlying_rpc > INTAKE_UNDERLYING_RPC:
                raise CombinedDiscoveryError("UNDERLYING_RPC_CEILING")
            usage.bump_source(sum(result.accounting.governed_requests.values()) or 1)
            creates = result.observations
            save_origin_cursor(connection, result.cursor, now=now)
            grad_native_proofs = tuple(
                item
                for item in fixtures.direct_observations
                if item.confirmed
                and getattr(item, "origin_route", "PUMP_CREATE") == "GRADUATION_NATIVE"
            )
        else:
            # V2-9.7E.45 typed route split. Only create-native proofs become
            # PumpCreateObservations written to the create origin registry; the
            # migration signature of a graduation-native proof is NEVER persisted
            # into a create-signature field.
            create_proofs = tuple(
                item
                for item in fixtures.direct_observations
                if item.confirmed
                and getattr(item, "origin_route", "PUMP_CREATE") == "PUMP_CREATE"
            )
            grad_native_proofs = tuple(
                item
                for item in fixtures.direct_observations
                if item.confirmed
                and getattr(item, "origin_route", "PUMP_CREATE") == "GRADUATION_NATIVE"
            )
            creates = tuple(
                PumpCreateObservation(
                    mint=item.mint,
                    bonding_curve=item.bonding_curve,
                    associated_bonding_curve=item.associated_bonding_curve,
                    creator_address=item.creator_address,
                    signature=item.signature,
                    slot=item.slot,
                    block_time=item.block_time,
                    create_layout=getattr(item, "create_layout", "PUMP_CREATE_V1"),
                )
                for item in create_proofs
            )
            if creates:
                usage.bump_source()

        # Durable prospective evidence: confirmed creates outlive this cycle and
        # are what later cycles read instead of rediscovering an aged create.
        try:
            for create in creates:
                record_confirmed_origin(
                    connection,
                    create,
                    now=now,
                    acquisition_mode=ACQUISITION_MODE_PROSPECTIVE,
                    index_address=PUMP_CREATE_INDEX_ADDRESS,
                )
        except OriginRegistryError as exc:
            raise CombinedDiscoveryError(exc.code, exc.detail) from exc

        for index, create in enumerate(creates, start=1):
            req = self._governed_request(
                connection,
                usage,
                source_name="solana_rpc",
                request_kind="pumpfun_create_transaction_reference",
                now=now,
            )
            payload = {
                "mint": create.mint,
                "signature": create.signature,
                "slot": create.slot,
                "block_time": create.block_time,
                "origin": "PUMPFUN_ORIGIN_CONFIRMED",
            }
            resp = self._store_response(
                connection,
                usage,
                request_id=req,
                source_name="solana_rpc",
                now=now,
                payload=payload,
            )
            link_discovery_work_source(
                connection,
                discovery_work_id=work_id,
                link_ordinal=index,
                source_request_id=req,
                source_response_id=resp,
                now=now,
            )
            obs_id = _batch_scoped_object_id(
                "obs", discovery_batch_id, "direct", create.mint, create.signature
            )
            factual = {
                "provider": "solana_rpc",
                "channel": "LATEST_PUMPFUN",
                "network": "solana",
                "mint": create.mint,
                "pool": create.bonding_curve,
                "quote_mint": "So11111111111111111111111111111111111111112",
                "venue": "pumpfun",
                "observed_at": now,
                "pumpfun_origin_status": "PUMPFUN_ORIGIN_CONFIRMED",
            }
            raw_hash = _sha256_text(_canonical(payload))
            self._mark_persistence(
                "DISCOVERY_PROVIDER_OBSERVATION", "provider_observation"
            )
            insert_provider_observation(
                connection,
                observation_id=obs_id,
                discovery_batch_id=discovery_batch_id,
                discovery_work_id=work_id,
                campaign_id=command.campaign_id,
                run_id=command.run_id,
                cycle_id=fixtures.cycle_id,
                source_name="solana_rpc",
                request_kind="pumpfun_create_transaction_reference",
                channel="LATEST_PUMPFUN",
                mint_identity=create.mint,
                market_identity=_market_identity("pumpfun", create.bonding_curve),
                lifecycle_identity="PUMP_CREATED_UNPAIRED",
                observed_at=now,
                captured_at=now,
                raw_payload_hash=raw_hash,
                factual_payload=factual,
                source_request_id=req,
                source_response_id=resp,
                now=now,
            )
            observations.append(
                _Observation(
                    observation_id=obs_id,
                    provider="solana_rpc",
                    request_kind="pumpfun_create_transaction_reference",
                    channel="LATEST_PUMPFUN",
                    mint=create.mint,
                    pool=create.bonding_curve,
                    quote_mint="So11111111111111111111111111111111111111112",
                    venue="pumpfun",
                    observed_at=now,
                    raw_payload_hash=raw_hash,
                    source_request_id=req,
                    source_response_id=resp,
                    source_failure_id=None,
                    work_id=work_id,
                    pumpfun_origin_status="PUMPFUN_ORIGIN_CONFIRMED",
                    lifecycle="PUMP_CREATED_UNPAIRED",
                )
            )
            usage.observations += 1
            usage.unique_mints.add(create.mint)

        # V2-9.7E.45 Route B — graduation-native activation. A migration-discovered
        # candidate is origin-confirmed by its Pump migration lineage (exact Pump
        # migration signature + graduation slot/block time), NOT by a create
        # transaction. It is never written to the create origin registry and no
        # create signature/slot/block-time/creator/layout is fabricated. Its exact
        # PumpSwap pool comes from the confirmed graduation proof; the observation
        # carries the confirmed-origin status so the merge/origin/PumpSwap gates
        # graduate it and rebind the tracking market identity to the exact pool —
        # producing token/pair/queue/scheduler identities identical to Route A.
        gn_ordinal = len(creates)
        for proof in grad_native_proofs:
            graduation = fixtures.pumpswap_proofs.get(proof.mint)
            if graduation is None or not getattr(graduation, "pool_address", ""):
                # No confirmed graduation proof: not selectable (two-or-none).
                continue
            pool = str(graduation.pool_address)
            gn_ordinal += 1
            req = self._governed_request(
                connection,
                usage,
                source_name="solana_rpc",
                request_kind="pumpfun_origin_transaction_reference",
                now=now,
            )
            payload = {
                "mint": proof.mint,
                "migration_signature": proof.signature,
                "graduation_slot": int(proof.slot),
                "graduation_block_time": int(proof.block_time),
                "pumpswap_pool": pool,
                "origin": "PUMPFUN_MIGRATION_GRADUATION_CONFIRMED",
                "origin_route": "GRADUATION_NATIVE",
            }
            resp = self._store_response(
                connection,
                usage,
                request_id=req,
                source_name="solana_rpc",
                now=now,
                payload=payload,
            )
            link_discovery_work_source(
                connection,
                discovery_work_id=work_id,
                link_ordinal=gn_ordinal,
                source_request_id=req,
                source_response_id=resp,
                now=now,
            )
            obs_id = _batch_scoped_object_id(
                "obs",
                discovery_batch_id,
                "graduation_native",
                proof.mint,
                proof.signature,
            )
            # The executor observation ``channel`` is the provider-lane label — the
            # direct Pump / graduation-lineage lane (LATEST_PUMPFUN). The truthful
            # LATEST_GRADUATED vs PERSISTED_GRADUATED provenance is owned separately
            # by the front door + graduated registry, not the provider-lane label.
            factual = {
                "provider": "solana_rpc",
                "channel": "LATEST_PUMPFUN",
                "network": "solana",
                "mint": proof.mint,
                "pool": pool,
                "quote_mint": "So11111111111111111111111111111111111111112",
                "venue": PUMPSWAP_VENUE,
                "observed_at": now,
                "pumpfun_origin_status": "PUMPFUN_ORIGIN_CONFIRMED",
            }
            raw_hash = _sha256_text(_canonical(payload))
            self._mark_persistence(
                "DISCOVERY_PROVIDER_OBSERVATION", "provider_observation"
            )
            insert_provider_observation(
                connection,
                observation_id=obs_id,
                discovery_batch_id=discovery_batch_id,
                discovery_work_id=work_id,
                campaign_id=command.campaign_id,
                run_id=command.run_id,
                cycle_id=fixtures.cycle_id,
                source_name="solana_rpc",
                request_kind="pumpfun_origin_transaction_reference",
                channel="LATEST_PUMPFUN",
                mint_identity=proof.mint,
                market_identity=_market_identity(PUMPSWAP_VENUE, pool),
                lifecycle_identity="PUMP_MIGRATION_CONFIRMED",
                observed_at=now,
                captured_at=now,
                raw_payload_hash=raw_hash,
                factual_payload=factual,
                source_request_id=req,
                source_response_id=resp,
                now=now,
            )
            observations.append(
                _Observation(
                    observation_id=obs_id,
                    provider="solana_rpc",
                    request_kind="pumpfun_origin_transaction_reference",
                    channel="LATEST_PUMPFUN",
                    mint=proof.mint,
                    pool=pool,
                    quote_mint="So11111111111111111111111111111111111111112",
                    venue=PUMPSWAP_VENUE,
                    observed_at=now,
                    raw_payload_hash=raw_hash,
                    source_request_id=req,
                    source_response_id=resp,
                    source_failure_id=None,
                    work_id=work_id,
                    pumpfun_origin_status="PUMPFUN_ORIGIN_CONFIRMED",
                    lifecycle="PUMP_MIGRATION_CONFIRMED",
                    origin_route="GRADUATION_NATIVE",
                )
            )
            usage.observations += 1
            usage.unique_mints.add(proof.mint)

        self._terminalize_work(connection, work_id, "SUCCEEDED", "DIRECT_COMPLETE", now)
        return observations

    def _run_secondary_lane(
        self,
        connection: sqlite3.Connection,
        command: AbstractCampaignCommand,
        usage: _Usage,
        discovery_batch_id: str,
        *,
        work_type: str,
        ops: Sequence[FixtureSourceFact],
        lane_name: str,
    ) -> list[_Observation]:
        fixtures = self.fixtures
        now = fixtures.evaluated_at
        if not ops and lane_name not in fixtures.provider_failures_injected:
            # Provider not planned this cycle: SKIPPED_BLOCKED_CONTRACT equivalent.
            return []
        work_id = self._create_work(
            connection, command, usage, discovery_batch_id, work_type, now
        )
        if lane_name in fixtures.provider_failures_injected:
            fail_type = fixtures.provider_failures_injected[lane_name]
            source_name = {
                "geckoterminal": GECKO_SOURCE_NAME,
                "solana_tracker": TRACKER_SOURCE_NAME,
                "dexscreener": DEXSCREENER_SOURCE,
            }[lane_name]
            kind = {
                "geckoterminal": GECKO_TRENDING_REQUEST,
                "solana_tracker": TRACKER_TRENDING_REQUEST,
                "dexscreener": "dexscreener_fresh_profiles",
            }[lane_name]
            req = self._governed_request(
                connection, usage, source_name=source_name, request_kind=kind, now=now
            )
            fail_id = self._store_failure(
                connection,
                usage,
                source_name=source_name,
                request_kind=kind,
                failure_type=fail_type,
                now=now,
            )
            link_discovery_work_source(
                connection,
                discovery_work_id=work_id,
                link_ordinal=1,
                source_request_id=req,
                source_failure_id=fail_id,
                now=now,
            )
            self._terminalize_work(
                connection, work_id, "FAILED", f"{lane_name.upper()}_FAILED", now
            )
            return []

        observations: list[_Observation] = []
        lane_failures = 0
        for ordinal, op in enumerate(ops, start=1):
            if op.fixture_status in {"failure", "rate_limited", "error"} or (
                op.status_code not in (200, None) and op.status_code >= 400
            ):
                req = self._governed_request(
                    connection,
                    usage,
                    source_name=op.source_name,
                    request_kind=op.request_kind,
                    now=now,
                )
                fail_id = self._store_failure(
                    connection,
                    usage,
                    source_name=op.source_name,
                    request_kind=op.request_kind,
                    failure_type=op.failure_type or "provider_error",
                    now=now,
                )
                link_discovery_work_source(
                    connection,
                    discovery_work_id=work_id,
                    link_ordinal=ordinal,
                    source_request_id=req,
                    source_failure_id=fail_id,
                    now=now,
                )
                lane_failures += 1
                continue

            req = self._governed_request(
                connection,
                usage,
                source_name=op.source_name,
                request_kind=op.request_kind,
                now=now,
            )
            try:
                normalized_rows = self._normalize_op(op)
            except SecondaryDiscoveryError as exc:
                # Adopted secondary-contract failures are provider-local.  Do
                # not label a malformed decoded body as a clean response and do
                # not translate it into a shared campaign rollback.  Database,
                # ownership and ceiling faults remain outside this narrow catch.
                fail_id = self._store_failure(
                    connection,
                    usage,
                    source_name=op.source_name,
                    request_kind=op.request_kind,
                    failure_type=exc.code,
                    now=now,
                )
                link_discovery_work_source(
                    connection,
                    discovery_work_id=work_id,
                    link_ordinal=ordinal,
                    source_request_id=req,
                    source_failure_id=fail_id,
                    now=now,
                )
                lane_failures += 1
                continue
            resp = self._store_response(
                connection,
                usage,
                request_id=req,
                source_name=op.source_name,
                now=now,
                payload=op.body,
                status_code=op.status_code,
            )
            link_discovery_work_source(
                connection,
                discovery_work_id=work_id,
                link_ordinal=ordinal,
                source_request_id=req,
                source_response_id=resp,
                now=now,
            )
            for row in normalized_rows:
                for banned in FORBIDDEN_FACTUAL_FIELDS:
                    if banned in row:
                        raise CombinedDiscoveryError("NON_AUTHORITATIVE_FIELD_LEAK", banned)
                mint = str(row["mint"])
                pool = str(row["pool"])
                venue = str(row["venue"])
                channel = str(row["channel"])
                obs_id = _batch_scoped_object_id(
                    "obs",
                    discovery_batch_id,
                    "secondary",
                    op.source_name,
                    channel,
                    mint,
                    pool,
                    ordinal,
                )
                raw_hash = _sha256_text(_canonical(op.body) + "|" + obs_id)
                factual = {
                    "provider": op.source_name,
                    "channel": channel,
                    "network": "solana",
                    "mint": mint,
                    "pool": pool,
                    "quote_mint": row.get("quote_mint"),
                    "venue": venue,
                    "observed_at": row.get("observed_at") or op.receipt_time,
                    "pumpfun_origin_status": PUMPFUN_ORIGIN_STATUS,
                }
                self._mark_persistence(
                    "DISCOVERY_PROVIDER_OBSERVATION", "provider_observation"
                )
                insert_provider_observation(
                    connection,
                    observation_id=obs_id,
                    discovery_batch_id=discovery_batch_id,
                    discovery_work_id=work_id,
                    campaign_id=command.campaign_id,
                    run_id=command.run_id,
                    cycle_id=fixtures.cycle_id,
                    source_name=op.source_name,
                    request_kind=op.request_kind,
                    channel=channel,
                    mint_identity=mint,
                    market_identity=_market_identity(venue, pool),
                    lifecycle_identity="PUMP_LIFECYCLE_UNKNOWN",
                    observed_at=str(factual["observed_at"]),
                    captured_at=now,
                    raw_payload_hash=raw_hash,
                    factual_payload=factual,
                    source_request_id=req,
                    source_response_id=resp,
                    now=now,
                )
                observations.append(
                    _Observation(
                        observation_id=obs_id,
                        provider=op.source_name,
                        request_kind=op.request_kind,
                        channel=channel,
                        mint=mint,
                        pool=pool,
                        quote_mint=str(row.get("quote_mint") or ""),
                        venue=venue,
                        observed_at=str(factual["observed_at"]),
                        raw_payload_hash=raw_hash,
                        source_request_id=req,
                        source_response_id=resp,
                        source_failure_id=None,
                        work_id=work_id,
                        pumpfun_origin_status=PUMPFUN_ORIGIN_STATUS,
                        activity_count=row.get("activity_count"),
                    )
                )
                usage.observations += 1
                usage.unique_mints.add(mint)
        if lane_failures:
            self._terminalize_work(
                connection,
                work_id,
                "FAILED",
                f"{lane_name.upper()}_FAILED",
                now,
            )
        else:
            self._terminalize_work(
                connection,
                work_id,
                "SUCCEEDED",
                f"{lane_name.upper()}_COMPLETE",
                now,
            )
        return observations

    def _normalize_op(self, op: FixtureSourceFact) -> list[dict[str, Any]]:
        fixtures = self.fixtures
        if op.request_kind == GECKO_TRENDING_REQUEST:
            rows = normalize_gecko_trending(
                op.body,
                receipt_time=op.receipt_time,
                evaluated_at=fixtures.evaluated_at,
                params=op.params,
            )
            return [row.identity_dict() for row in rows]
        if op.request_kind == GECKO_ACTIVE_REQUEST:
            row = normalize_gecko_active(
                op.body,
                receipt_time=op.receipt_time,
                evaluated_at=fixtures.evaluated_at,
                requested_pool=str(op.requested_pool or ""),
            )
            return [row.identity_dict()]
        if op.request_kind == TRACKER_TRENDING_REQUEST:
            if fixtures.tracker_auth is not None:
                fixtures.tracker_auth.validate()
            rows = normalize_tracker_list(
                op.body,
                channel="TRENDING_PUMPFUN",
                receipt_time=op.receipt_time,
                evaluated_at=fixtures.evaluated_at,
            )
            return [row.identity_dict() for row in rows]
        if op.request_kind == TRACKER_TOP_REQUEST:
            if fixtures.tracker_auth is not None:
                fixtures.tracker_auth.validate()
            rows = normalize_tracker_list(
                op.body,
                channel="TOP_PUMPFUN",
                receipt_time=op.receipt_time,
                evaluated_at=fixtures.evaluated_at,
            )
            return [row.identity_dict() for row in rows]
        if op.request_kind in {"dexscreener_fresh_profiles", "token_discovery"}:
            # Minimal DexScreener active observation fixture shape.
            rows = []
            body = op.body if isinstance(op.body, list) else op.body.get("pairs") or []
            for item in body:
                if not isinstance(item, Mapping):
                    continue
                mint = str(item.get("baseToken", {}).get("address") or item.get("mint") or "")
                pool = str(item.get("pairAddress") or item.get("pool") or "")
                if not mint or not pool:
                    continue
                txns = item.get("txns") or {}
                m5 = txns.get("m5") if isinstance(txns, Mapping) else None
                count = 0
                if isinstance(m5, Mapping):
                    count = int(m5.get("buys") or 0) + int(m5.get("sells") or 0)
                elif isinstance(m5, (int, float)):
                    count = int(m5)
                if count <= 0:
                    continue
                rows.append(
                    {
                        "provider": DEXSCREENER_SOURCE,
                        "channel": "ACTIVE_PUMPFUN",
                        "network": "solana",
                        "mint": mint,
                        "pool": pool,
                        "quote_mint": str(
                            item.get("quoteToken", {}).get("address")
                            or "So11111111111111111111111111111111111111112"
                        ),
                        "venue": str(item.get("dexId") or "pumpfun"),
                        "observed_at": op.receipt_time,
                        "activity_count": count,
                        "pumpfun_origin_status": PUMPFUN_ORIGIN_STATUS,
                    }
                )
            return rows
        return []

    def _merge(
        self,
        observations: Sequence[_Observation],
        discovery_batch_id: str,
    ) -> dict[str, _Merged]:
        confirmed_mints = {
            obs.mint
            for obs in observations
            if obs.pumpfun_origin_status == "PUMPFUN_ORIGIN_CONFIRMED"
        }
        merged: dict[str, _Merged] = {}
        for obs in observations:
            key = candidate_identity_key(
                mint_identity=obs.mint,
                market_identity=_market_identity(obs.venue, obs.pool),
                lifecycle_identity=obs.lifecycle,
            )
            if key not in merged:
                merged[key] = _Merged(
                    merged_candidate_id=_batch_scoped_object_id(
                        "candidate", discovery_batch_id, key
                    ),
                    mint=obs.mint,
                    market_identity=_market_identity(obs.venue, obs.pool),
                    lifecycle=obs.lifecycle,
                    channels=set(),
                    observation_ids=[],
                    conflicts=[],
                    gaps=[],
                )
            candidate = merged[key]
            if obs.observation_id not in candidate.observation_ids:
                candidate.observation_ids.append(obs.observation_id)
            candidate.channels.add(obs.channel)
            if getattr(obs, "origin_route", "PUMP_CREATE") == "GRADUATION_NATIVE":
                candidate.origin_route = "GRADUATION_NATIVE"
            if (
                obs.pumpfun_origin_status == "PUMPFUN_ORIGIN_CONFIRMED"
                or obs.mint in confirmed_mints
            ):
                # Direct finalized origin is mint-scoped authority, not market-scoped.
                candidate.origin_state = "CONFIRMED"
            elif candidate.origin_state != "CONFIRMED":
                candidate.gaps.append(
                    {
                        "kind": "ORIGIN_UNVERIFIED",
                        "detail": "provider_label_only",
                    }
                )
        return merged

    def _origin_and_pumpswap(
        self,
        connection: sqlite3.Connection,
        command: AbstractCampaignCommand,
        usage: _Usage,
        discovery_batch_id: str,
        cycle_seed: str,
        merged: dict[str, _Merged],
        now: str,
    ) -> None:
        fixtures = self.fixtures
        work_id = self._create_work(
            connection,
            command,
            usage,
            discovery_batch_id,
            "DISCOVERY_ORIGIN_VERIFICATION",
            now,
        )
        already_confirmed = [
            candidate
            for candidate in merged.values()
            if candidate.origin_state == "CONFIRMED"
        ]
        memory_by_mint: dict[str, Any] = {}
        if fixtures.memory_activation_set is not None:
            memory_by_mint = {
                item.mint: item for item in fixtures.memory_activation_set.selected
            }
        market_authority_mints = {
            mint
            for mint, item in memory_by_mint.items()
            if item.admission_authority.value == "MARKET_PRESENT_POOL"
        }
        for candidate in merged.values():
            if candidate.mint in market_authority_mints:
                candidate.origin_state = "NOT_REQUIRED"
                candidate.pumpswap_state = "NOT_REQUIRED"

        for candidate in already_confirmed:
            # V2-9.7E.45: label the confirmed-origin evidence source by activation
            # route. A graduation-native candidate is origin-confirmed by its Pump
            # migration lineage, not by a create transaction.
            evidence_source = (
                "migration_graduation_lineage"
                if candidate.origin_route == "GRADUATION_NATIVE"
                else "direct_finalized_create"
            )
            origin_request_id = None
            origin_response_id = None
            evidence_detail: dict[str, Any] = {"source": evidence_source}
            frozen = memory_by_mint.get(candidate.mint)
            if frozen is not None:
                origin_ref = role_reference_for_candidate(
                    frozen, EvidenceRole.ORIGIN_LINEAGE
                )
                origin_request_id = int(origin_ref.source_request_id)
                origin_response_id = int(origin_ref.source_response_id)
                evidence_detail.update(
                    {
                        "evidence_reuse_kind": "RETAINED_GOVERNED_EVIDENCE_REFERENCE",
                        "retained_evidence_role": EvidenceRole.ORIGIN_LINEAGE.value,
                        "retained_source_request_id": origin_request_id,
                        "retained_source_response_id": origin_response_id,
                        "retained_response_hash": origin_ref.raw_payload_hash,
                        "retained_transport_identity_keys": [
                            list(key) for key in origin_ref.transport_identity_keys
                        ],
                        "retained_source_name": origin_ref.source_name,
                        "retained_request_kind": origin_ref.request_kind,
                        "retained_observed_at": origin_ref.observed_at,
                        "retained_campaign_id": origin_ref.campaign_id,
                        "retained_run_id": origin_ref.campaign_run_id,
                        "retained_cycle_id": origin_ref.cycle_id,
                    }
                )
            self._mark_persistence(
                "DISCOVERY_ORIGIN_VERIFICATION", "origin_verification"
            )
            insert_origin_verification(
                connection,
                origin_verification_id=_batch_scoped_object_id(
                    "origin", discovery_batch_id, candidate.merged_candidate_id
                ),
                discovery_batch_id=discovery_batch_id,
                merged_candidate_id=candidate.merged_candidate_id,
                mint_identity=candidate.mint,
                admission_state="NOT_REQUIRED",
                verification_state="CONFIRMED",
                source_request_id=origin_request_id,
                source_response_id=origin_response_id,
                evidence_detail=evidence_detail,
                now=now,
            )

        secondary = [
            candidate
            for candidate in merged.values()
            if candidate.origin_state != "CONFIRMED"
            and candidate.mint not in market_authority_mints
        ]
        secondary.sort(key=lambda item: _token_identity(item.mint))
        ranked = sorted(
            secondary,
            key=lambda item: (
                _verification_key(cycle_seed, "origin", _token_identity(item.mint)),
                _token_identity(item.mint),
            ),
        )
        admitted = ranked[:ORIGIN_VERIFY_ADMISSIONS]
        admitted_ids = {item.merged_candidate_id for item in admitted}
        resolved_proofs: dict[str, FixtureOriginProof] = dict(fixtures.origin_proofs)
        for candidate in secondary:
            if candidate.merged_candidate_id in admitted_ids:
                proof = resolved_proofs.get(candidate.mint)
                origin_source = "cycle_direct_create"
                if proof is None or not proof.confirmed:
                    # V2-9.7E.5: exact-mint origin comes from the durable
                    # prospective registry. Zero RPC, zero historical
                    # rediscovery of an aged creation transaction.
                    registered = lookup_confirmed_origin(connection, candidate.mint)
                    if registered is not None:
                        origin_source = "durable_origin_registry"
                        proof = FixtureOriginProof(
                            mint=str(registered["mint_identity"]),
                            signature=str(registered["transaction_signature"]),
                            slot=int(registered["slot"]),
                            block_time=int(registered["block_time"]),
                            bonding_curve=str(registered["bonding_curve"]),
                            associated_bonding_curve=str(
                                registered["associated_bonding_curve"]
                            ),
                            creator_address=str(registered["creator_address"]),
                            confirmed=True,
                        )
                        resolved_proofs[candidate.mint] = proof
                if proof is not None and proof.confirmed and proof.mint == candidate.mint:
                    candidate.origin_state = "CONFIRMED"
                    verification_state = "CONFIRMED"
                    # Registry hits consume no source budget and no admission.
                    admission_state = (
                        "NOT_REQUIRED"
                        if origin_source == "durable_origin_registry"
                        else "ADMITTED"
                    )
                else:
                    candidate.origin_state = "FAILED"
                    verification_state = "FAILED"
                    admission_state = "ADMITTED"
                    origin_source = "none"
                    candidate.gaps.append(
                        {
                            "kind": "ORIGIN_VERIFICATION_FAILED",
                            "detail": "ORIGIN_NOT_IN_REGISTRY",
                        }
                    )
            else:
                admission_state = "NOT_ADMITTED_CEILING"
                verification_state = "NOT_ATTEMPTED"
                origin_source = "none"
                candidate.origin_state = "NOT_ADMITTED_CEILING"
                candidate.gaps.append(
                    {
                        "kind": "ORIGIN_VERIFICATION_NOT_ADMITTED_CEILING",
                        "detail": "budget",
                    }
                )
            self._mark_persistence(
                "DISCOVERY_ORIGIN_VERIFICATION", "origin_verification"
            )
            insert_origin_verification(
                connection,
                origin_verification_id=_batch_scoped_object_id(
                    "origin", discovery_batch_id, candidate.merged_candidate_id
                ),
                discovery_batch_id=discovery_batch_id,
                merged_candidate_id=candidate.merged_candidate_id,
                mint_identity=candidate.mint,
                admission_state=admission_state,
                verification_state=verification_state,
                transaction_signature=(
                    resolved_proofs[candidate.mint].signature
                    if candidate.mint in resolved_proofs
                    and resolved_proofs[candidate.mint].confirmed
                    else None
                ),
                evidence_detail={
                    "provider_label_unverified_until_direct": True,
                    "state": verification_state,
                    "source": origin_source,
                },
                now=now,
            )
        self._terminalize_work(connection, work_id, "SUCCEEDED", "ORIGIN_COMPLETE", now)

        ps_work = self._create_work(
            connection,
            command,
            usage,
            discovery_batch_id,
            "DISCOVERY_PUMPSWAP_CONFIRMATION",
            now,
        )
        claimed = [
            candidate
            for candidate in merged.values()
            if candidate.mint in fixtures.pumpswap_proofs
            and candidate.mint not in market_authority_mints
        ]
        claimed.sort(key=lambda item: _token_identity(item.mint))
        # V2-9.7E.41: graduation is a per-MINT fact (one migration claim per mint,
        # confirmed unique-or-fail). Admit up to PUMPSWAP_ADMISSIONS unique mints
        # ranked by seeded verification key, then confirm every candidate-market of
        # an admitted mint. This prevents a mint appearing under several
        # candidate-markets from starving the per-cycle confirmation ceiling.
        claimed_mints = sorted(
            {candidate.mint for candidate in claimed},
            key=lambda mint: (
                _verification_key(cycle_seed, "pumpswap", _token_identity(mint)),
                _token_identity(mint),
            ),
        )
        admitted_mints = set(claimed_mints[:PUMPSWAP_ADMISSIONS])
        for candidate in claimed:
            proof = fixtures.pumpswap_proofs[candidate.mint]
            if candidate.mint not in admitted_mints:
                admission_state = "NOT_ADMITTED_CEILING"
                confirmation_state = "NOT_ATTEMPTED"
                candidate.pumpswap_state = "NOT_ADMITTED_CEILING"
            elif proof.ambiguous:
                admission_state = "ADMITTED"
                confirmation_state = "AMBIGUOUS"
                candidate.pumpswap_state = "AMBIGUOUS"
            elif (
                proof.confirmed
                and proof.program_id == PUMPSWAP_PROGRAM_ID
                and proof.mint == candidate.mint
                and bool(proof.pool_address)
            ):
                # V2-9.7E.41 graduation-only law: an exact, unambiguous PumpSwap
                # confirmation (owner == adopted program, base_mint == candidate
                # mint, exactly one pool) graduates the candidate and rebinds its
                # tracking market identity to the confirmed post-graduation
                # PumpSwap pool. Migration/pool creation time is never stamped as
                # token_created_at.
                admission_state = "ADMITTED"
                confirmation_state = "CONFIRMED"
                candidate.pumpswap_state = "CONFIRMED"
                candidate.lifecycle = GRADUATED_LIFECYCLE
                candidate.market_identity = _market_identity(
                    PUMPSWAP_VENUE, proof.pool_address
                )
            else:
                # Wrong owner, mint mismatch, missing pool, or an unconfirmed
                # claim: the market identity fails closed (never graduated).
                admission_state = "ADMITTED"
                confirmation_state = "FAILED"
                candidate.pumpswap_state = "FAILED"
            pumpswap_request_id = None
            pumpswap_response_id = None
            pumpswap_detail: dict[str, Any] = {}
            frozen = memory_by_mint.get(candidate.mint)
            if frozen is not None:
                pumpswap_ref = role_reference_for_candidate(
                    frozen, EvidenceRole.PUMPSWAP_CONFIRMATION
                )
                pumpswap_request_id = int(pumpswap_ref.source_request_id)
                pumpswap_response_id = int(pumpswap_ref.source_response_id)
                pumpswap_detail = {
                    "evidence_reuse_kind": "RETAINED_GOVERNED_EVIDENCE_REFERENCE",
                    "retained_evidence_role": (
                        EvidenceRole.PUMPSWAP_CONFIRMATION.value
                    ),
                    "retained_source_request_id": pumpswap_request_id,
                    "retained_source_response_id": pumpswap_response_id,
                    "retained_response_hash": pumpswap_ref.raw_payload_hash,
                    "retained_transport_identity_keys": [
                        list(key) for key in pumpswap_ref.transport_identity_keys
                    ],
                    "retained_source_name": pumpswap_ref.source_name,
                    "retained_request_kind": pumpswap_ref.request_kind,
                    "retained_observed_at": pumpswap_ref.observed_at,
                    "retained_campaign_id": pumpswap_ref.campaign_id,
                    "retained_run_id": pumpswap_ref.campaign_run_id,
                    "retained_cycle_id": pumpswap_ref.cycle_id,
                }
            self._mark_persistence(
                "DISCOVERY_PUMPSWAP_CONFIRMATION", "pumpswap_confirmation"
            )
            insert_pumpswap_confirmation(
                connection,
                pumpswap_confirmation_id=_batch_scoped_object_id(
                    "pumpswap", discovery_batch_id, candidate.merged_candidate_id
                ),
                discovery_batch_id=discovery_batch_id,
                merged_candidate_id=candidate.merged_candidate_id,
                mint_identity=candidate.mint,
                market_identity=candidate.market_identity,
                admission_state=admission_state,
                confirmation_state=confirmation_state,
                source_request_id=pumpswap_request_id,
                source_response_id=pumpswap_response_id,
                pool_address=proof.pool_address,
                program_id=proof.program_id,
                evidence_detail=pumpswap_detail or None,
                now=now,
            )
        self._terminalize_work(connection, ps_work, "SUCCEEDED", "PUMPSWAP_COMPLETE", now)

    def _apply_gates(
        self,
        connection: sqlite3.Connection,
        command: AbstractCampaignCommand,
        fixtures: CombinedDiscoveryFixtures,
        discovery_batch_id: str,
        merged: dict[str, _Merged],
        usage: _Usage,
    ) -> list[_Merged]:
        del command
        market_authority_mints = frozenset(
            item.mint
            for item in (
                fixtures.memory_activation_set.selected
                if fixtures.memory_activation_set is not None
                else ()
            )
            if item.admission_authority.value == "MARKET_PRESENT_POOL"
        )
        return _apply_existing_discovery_gates(
            connection,
            candidates=tuple(merged.values()),
            discovery_batch_id=discovery_batch_id,
            evaluated_at=datetime.fromisoformat(
                fixtures.evaluated_at.replace("Z", "+00:00")
            ),
            mode=fixtures.mode,
            vacant_slot_ordinals=fixtures.vacant_slot_ordinals,
            batch_seq=fixtures.batch_seq,
            handoffs_used=usage.handoffs,
            market_authority_mints=market_authority_mints,
        )
        # Historical implementation retained below temporarily for source
        # parity review; it is unreachable and the shared owner above is the
        # sole executed gate law.
        eligible: list[_Merged] = []
        for candidate in merged.values():
            frozen_authority = None
            if fixtures.memory_activation_set is not None:
                frozen_authority = next(
                    (
                        item.admission_authority.value
                        for item in fixtures.memory_activation_set.selected
                        if item.mint == candidate.mint
                    ),
                    None,
                )
            market_authority = frozen_authority == "MARKET_PRESENT_POOL"
            failed = None
            for gate in GATE_ORDER:
                if gate == "OWNERSHIP":
                    if not discovery_batch_id:
                        failed = gate
                elif gate == "SOURCE_PROVENANCE":
                    if not candidate.observation_ids:
                        failed = gate
                elif gate == "SOLANA_IDENTITY":
                    if not candidate.mint or not candidate.market_identity:
                        failed = gate
                elif gate == "PUMPFUN_ORIGIN":
                    if not market_authority and candidate.origin_state != "CONFIRMED":
                        failed = gate
                elif gate == "LIFECYCLE_MARKET":
                    # V2-9.7E.41 graduation-only tracking law. A candidate is
                    # selection-eligible ONLY when exact PumpSwap graduation is
                    # confirmed and bound to a valid post-graduation PumpSwap
                    # market identity. Every discovery-only lifecycle state
                    # (PUMP_CREATED_UNPAIRED, PUMP_BONDING_CURVE_ACTIVE,
                    # PUMP_MIGRATION_OBSERVED without confirmation,
                    # PUMP_LIFECYCLE_UNKNOWN, DISCOVERED_UNPAIRED) fails closed and
                    # remains discovery-only. Age is never a substitute.
                    if market_authority:
                        if (
                            candidate.lifecycle != "PRESENT_POOL_CONFIRMED"
                            or not candidate.market_identity
                        ):
                            failed = gate
                    elif (
                        candidate.lifecycle != GRADUATED_LIFECYCLE
                        or candidate.pumpswap_state != "CONFIRMED"
                        or not candidate.market_identity.startswith(PUMPSWAP_MARKET_PREFIX)
                    ):
                        failed = gate
                elif gate == "TRACKING_HANDOFF":
                    pool = candidate.market_identity.rsplit(":", 1)[-1]
                    handoff = assess_tracking_handoff_by_identity(
                        connection,
                        token_mint=candidate.mint,
                        pair_address=pool,
                        tracking_lane=TokenLifecycleState.TRACK_NORMAL,
                        assessed_at=datetime.fromisoformat(
                            fixtures.evaluated_at.replace("Z", "+00:00")
                        ),
                    )
                    if not handoff.eligible:
                        failed = handoff.reason_code or HANDOFF_UNSUPPORTED_STATE
                elif gate == "FRESHNESS_CUTOFF":
                    pass
                elif gate == "EVIDENCE_QUALITY":
                    if any(
                        gap.get("kind") in {
                            "DIRTY", "HOLDER_EVIDENCE_INELIGIBLE"
                        }
                        for gap in candidate.gaps
                    ):
                        failed = gate
                elif gate == "CANDIDATE_ROLE":
                    if not candidate.channels:
                        failed = gate
                elif gate == "INFRASTRUCTURE_EXCLUSION":
                    if candidate.mint in {
                        "So11111111111111111111111111111111111111112",
                        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                    }:
                        failed = gate
                elif gate == "DUPLICATE_CONFLICT":
                    if candidate.conflicts:
                        failed = gate
                elif gate == "B3_RECONCILIATION":
                    if fixtures.mode == "REPLACEMENT" and not fixtures.vacant_slot_ordinals:
                        failed = gate
                elif gate == "COOLDOWN":
                    pool = candidate.market_identity.rsplit(":", 1)[-1]
                    ok_token, _ = check_token_selection_cooldown(
                        connection, candidate.mint, fixtures.batch_seq
                    )
                    ok_pair, _ = check_pair_selection_cooldown(
                        connection, pool, fixtures.batch_seq
                    )
                    if not ok_token or not ok_pair:
                        failed = gate
                elif gate == "VACANCY":
                    if fixtures.mode == "INITIAL" and len(fixtures.vacant_slot_ordinals) < 2:
                        # vacancies default to two for initial
                        pass
                elif gate == "BUDGET":
                    if usage.handoffs >= TRACKING_HANDOFFS:
                        failed = gate
                if failed:
                    break
            candidate.first_failed_gate = failed
            candidate.eligible = failed is None
            if candidate.eligible:
                eligible.append(candidate)
        return eligible

    def _select(
        self,
        eligible: Sequence[_Merged],
        cycle_seed: str,
        *,
        vacancy_count: int,
    ) -> list[_Merged]:
        market_authority_mints = frozenset(
            item.mint
            for item in (
                self.fixtures.memory_activation_set.selected
                if self.fixtures.memory_activation_set is not None
                else ()
            )
            if item.admission_authority.value == "MARKET_PRESENT_POOL"
        )
        return _select_existing_discovery_candidates(
            eligible,
            cycle_seed,
            vacancy_count=vacancy_count,
            batch_seq=self.fixtures.batch_seq,
            market_authority_mints=market_authority_mints,
        )
        # Historical implementation retained below temporarily for source
        # parity review; it is unreachable and the shared owner above is the
        # sole executed selection law.
        if vacancy_count <= 0:
            return []
        # V2-9.7E.41 graduation-only law: only graduation-confirmed candidates are
        # ever selectable. Defense in depth — the LIFECYCLE_MARKET gate already
        # excludes non-graduated candidates, but selection re-drops anything that
        # is not GRADUATED with a valid PumpSwap market identity.
        graduated = [
            candidate
            for candidate in eligible
            if not candidate.conflicts
            and candidate.lifecycle == GRADUATED_LIFECYCLE
            and candidate.market_identity.startswith(PUMPSWAP_MARKET_PREFIX)
        ]
        # Collapse to one market per mint (identity dedup; a mint appearing in
        # multiple channels is one candidate and gets no probability boost). The
        # collapsed candidate keeps the union of its channel labels for category
        # classification.
        by_mint: dict[str, list[_Merged]] = {}
        for candidate in graduated:
            by_mint.setdefault(candidate.mint, []).append(candidate)
        collapsed: list[_Merged] = []
        for _mint, group in by_mint.items():
            channels: set[str] = set()
            for item in group:
                channels |= item.channels
            group_sorted = sorted(
                group, key=lambda item: (-len(item.channels), item.market_identity)
            )
            chosen = group_sorted[0]
            chosen.channels = channels
            collapsed.append(chosen)
        return self._categorical_two_slot(collapsed, cycle_seed, vacancy_count)

    @staticmethod
    def _uniform_pick(
        candidates: Sequence[_Merged], cycle_seed: str, domain: str, count: int
    ) -> list[_Merged]:
        """Deterministic, seeded, uniform selection within one category."""
        if count <= 0 or not candidates:
            return []
        ordered = sorted(
            candidates,
            key=lambda item: (
                _token_identity(item.mint),
                item.market_identity,
                item.lifecycle,
            ),
        )
        shuffled = _fisher_yates(ordered, f"{cycle_seed}|{domain}")
        return shuffled[:count]

    def _categorical_two_slot(
        self, candidates: Sequence[_Merged], cycle_seed: str, vacancy_count: int
    ) -> list[_Merged]:
        """Frozen smallest categorical distribution rule (no scoring/ranking).

        When at least one latest-only graduated candidate and at least one
        non-latest graduated candidate exist, the two selected slots must not both
        be latest-only. Selection within each category is deterministic, seeded
        and uniform; several non-latest categories are picked by durable
        categorical round-robin, never by weight/rank/popularity.
        """
        if not candidates:
            return []
        latest_only = [
            c for c in candidates if not _non_latest_categories(c.channels)
        ]
        non_latest = [c for c in candidates if _non_latest_categories(c.channels)]

        if vacancy_count == 1:
            return self._uniform_pick(candidates, cycle_seed, "single", 1)

        # Two vacancies. Enforce the anti-concentration rule only when both a
        # latest-only and a non-latest candidate are genuinely available.
        if latest_only and non_latest and vacancy_count >= 2:
            first = self._uniform_pick(
                latest_only, cycle_seed, "LATEST_GRADUATED", 1
            )
            category = self._round_robin_non_latest(non_latest, cycle_seed)
            members = [
                c for c in non_latest if category in _non_latest_categories(c.channels)
            ]
            second = self._uniform_pick(members, cycle_seed, category, 1)
            return first + second

        # Only one partition is genuinely available: degrade honestly to a uniform
        # pick within it (no fabricated category diversity).
        pool = non_latest or latest_only
        return self._uniform_pick(pool, cycle_seed, "SINGLE_CATEGORY", vacancy_count)

    def _round_robin_non_latest(
        self, non_latest: Sequence[_Merged], cycle_seed: str
    ) -> str:
        """Pick one non-latest category by durable seeded categorical round-robin.

        Categories are ordered by a seeded key (not by count, rank or popularity)
        and advanced by the persisted selection batch sequence, so repeated cycles
        rotate fairly across the available non-latest categories.
        """
        categories: set[str] = set()
        for candidate in non_latest:
            categories |= _non_latest_categories(candidate.channels)
        ordered = sorted(
            categories,
            key=lambda category: (
                _sha256_text(f"{cycle_seed}|category|{category}"),
                category,
            ),
        )
        if not ordered:
            return ""
        cursor = max(int(getattr(self.fixtures, "batch_seq", 1)), 1) - 1
        return ordered[cursor % len(ordered)]

    def _mark_discovery_batch_failed(
        self,
        connection: sqlite3.Connection,
        discovery_batch_id: str,
        cause: str,
        now: str,
    ) -> None:
        connection.execute(
            """
            UPDATE printer_discovery_batches
            SET batch_state = 'TERMINAL_FAILED',
                first_terminal_cause = ?,
                terminal_at = ?
            WHERE discovery_batch_id = ?
              AND batch_state NOT LIKE 'TERMINAL_%'
            """,
            (cause, now, discovery_batch_id),
        )
        # V2-9.7E.47 A2: a failed discovery batch leaves no active work row and
        # no active Scheduler job behind. Still-open work is cancelled (the work
        # is terminally unnecessary) and its job follows through the Scheduler
        # owner; already-terminal rows and jobs are never rewritten.
        reconcile_discovery_work_jobs(
            connection,
            discovery_batch_id=discovery_batch_id,
            abandoned_cause=cause,
        )

    def _validate_initial_handoff_preflight(
        self,
        connection: sqlite3.Connection,
        *,
        selected: Sequence[_Merged],
        vacancies: Sequence[int],
        usage: _Usage,
    ) -> None:
        if len(selected) != 2 or list(vacancies) != [1, 2]:
            raise CombinedDiscoveryError(
                "HANDOFF_PREFLIGHT_FAILED", "initial activation requires exactly two vacancies"
            )
        if usage.handoffs + 2 > TRACKING_HANDOFFS:
            raise CombinedDiscoveryError("HANDOFF_CEILING")
        if usage.scheduler_work + 2 > INTAKE_SCHEDULER_WORK:
            raise CombinedDiscoveryError("SCHEDULER_WORK_CEILING")
        authority_by_mint = {
            item.mint: item.admission_authority.value
            for item in (
                self.fixtures.memory_activation_set.selected
                if self.fixtures.memory_activation_set is not None
                else ()
            )
        }
        for candidate in selected:
            if not candidate.mint or not candidate.market_identity:
                raise CombinedDiscoveryError(
                    "HANDOFF_PREFLIGHT_FAILED", "selected candidate missing market identity"
                )
            if (
                authority_by_mint.get(candidate.mint) != "MARKET_PRESENT_POOL"
                and candidate.origin_state != "CONFIRMED"
            ):
                raise CombinedDiscoveryError(
                    "HANDOFF_PREFLIGHT_FAILED", "selected candidate lacks confirmed origin"
                )
        for ordinal in (1, 2):
            existing = connection.execute(
                """
                SELECT token_slot_id, mint_identity, token_state
                FROM printer_memory_factory_campaign_token_slots
                WHERE cycle_id = ? AND slot_ordinal = ?
                """,
                (self.fixtures.cycle_id, ordinal),
            ).fetchone()
            if existing is None:
                continue
            if existing["token_state"] not in {
                "FAILED",
                "COOLDOWN",
                "ARCHIVED",
                "MANUAL_REVIEW",
            }:
                raise CombinedDiscoveryError(
                    "CONFLICTING_SLOT",
                    f"slot ordinal {ordinal} is not vacant for initial activation",
                )

    def _handoff_one_slot(
        self,
        connection: sqlite3.Connection,
        command: AbstractCampaignCommand,
        usage: _Usage,
        *,
        discovery_batch_id: str,
        selection_batch_id: str,
        candidate: _Merged,
        ordinal: int,
        cycle_seed: str,
        now: str,
        handoff_work: str,
        force_scheduler_failure: bool = False,
        force_duplicate_active: bool = False,
    ) -> None:
        fixtures = self.fixtures
        mint = candidate.mint
        pool = candidate.market_identity.rsplit(":", 1)[-1]

        try:
            identity = ensure_neutral_token_pair_identity(
                connection,
                mint_identity=mint,
                pair_identity=pool,
            )
        except TokenPairIdentityError as exc:
            raise CombinedDiscoveryError(str(exc)) from exc
        token_id = identity.token_row_id
        pair_id = identity.pair_row_id
        # Identity projection is deliberately neutral.  This existing handoff
        # remains the lifecycle owner and applies TRACK_NORMAL only immediately
        # before assessing/claiming tracking activation in this transaction.
        connection.execute(
            "UPDATE printer_tokens SET token_status='TRACK_NORMAL',updated_at=? WHERE id=?",
            (now, token_id),
        )

        if force_duplicate_active:
            # Pre-create an active tracking row so the handoff duplicate check fails.
            connection.execute(
                """
                INSERT INTO printer_tracking_queue(
                    token_id, pair_id, tracking_lane, tracking_action, priority_reason,
                    next_check_at, queue_status, source_status, data_quality_label
                ) VALUES (?, ?, 'TRACK_NORMAL', 'PROMOTE_TO_TRACK_NORMAL', 'inject',
                          ?, 'ACTIVE', 'COMPLETE', 'CLEAN_DATA')
                """,
                (token_id, pair_id, now),
            )

        handoff = assess_tracking_handoff(
            connection,
            token_id=token_id,
            pair_id=pair_id,
            tracking_lane=TokenLifecycleState.TRACK_NORMAL,
            assessed_at=datetime.fromisoformat(now.replace("Z", "+00:00")),
        )
        if not handoff.eligible:
            raise CombinedDiscoveryError(
                handoff.reason_code or HANDOFF_UNSUPPORTED_STATE
            )
        holder_fact = dict(
            fixtures.holder_evidence_eligibility.get(mint.lower()) or {}
        )
        fresh_requalification = bool(
            handoff.requalification_eligible
            and holder_fact.get("eligible") is True
            and holder_fact.get("tracking_requalification_required") is True
        )
        if (
            fixtures.memory_activation_set is not None
            and handoff.requalification_eligible
        ):
            raise CombinedDiscoveryError(
                handoff.reason_code or handoff.category
            )
        if handoff.requalification_eligible and not fresh_requalification:
            raise CombinedDiscoveryError(handoff.category)

        slot_id = cycle_scoped_token_slot_id(
            cycle_id=fixtures.cycle_id,
            slot_ordinal=ordinal,
        )
        existing_slot = connection.execute(
            """
            SELECT token_slot_id, mint_identity, token_state, tracking_queue_id
            FROM printer_memory_factory_campaign_token_slots
            WHERE cycle_id = ? AND slot_ordinal = ?
            """,
            (fixtures.cycle_id, ordinal),
        ).fetchone()

        from printer_v1.operator_cli.cadence_authority import (
            CadenceAuthorityError,
            validate_existing_slot_tracking_queue_for_handoff,
        )

        if existing_slot is None:
            created, queue_id = claim_tracking_item(
                connection,
                token_id=token_id,
                pair_id=pair_id,
                tracking_lane=TokenLifecycleState.TRACK_NORMAL,
                tracking_action=LifecycleEvent.PROMOTE_TO_TRACK_NORMAL,
                priority_reason="combined_discovery_handoff",
                next_check_at=datetime.fromisoformat(now.replace("Z", "+00:00")),
                source_status=SourceStatus.COMPLETE,
                data_quality_label=DataQualityLabel.CLEAN_DATA,
                assessed_at=datetime.fromisoformat(now.replace("Z", "+00:00")),
                fresh_evidence_requalification=fresh_requalification,
                requalification_lineage={
                    "campaign_id": command.campaign_id,
                    "run_id": command.run_id,
                    "cycle_id": fixtures.cycle_id,
                    "discovery_batch_id": discovery_batch_id,
                    "selection_batch_id": selection_batch_id,
                    "fresh_evidence_evaluated_at": now,
                    "holder_source_name": holder_fact.get("source_name"),
                    "holder_evidence_reason": holder_fact.get("reason"),
                },
            )
            if not created or queue_id is None:
                handoff = assess_tracking_handoff(
                    connection,
                    token_id=token_id,
                    pair_id=pair_id,
                    tracking_lane=TokenLifecycleState.TRACK_NORMAL,
                    assessed_at=datetime.fromisoformat(now.replace("Z", "+00:00")),
                )
                raise CombinedDiscoveryError(
                    handoff.reason_code or HANDOFF_UNSUPPORTED_STATE
                )
            connection.execute(
                """
                INSERT INTO printer_memory_factory_campaign_token_slots(
                    token_slot_id, campaign_id, run_id, cycle_id, slot_ordinal,
                    token_identity, token_row_id, mint_identity, pair_identity,
                    pair_row_id, lifecycle_identity, tracking_queue_id,
                    token_state, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'SELECTED',?,?)
                """,
                (
                    slot_id,
                    command.campaign_id,
                    command.run_id,
                    fixtures.cycle_id,
                    ordinal,
                    _token_identity(mint),
                    token_id,
                    mint,
                    pool,
                    pair_id,
                    candidate.lifecycle,
                    queue_id,
                    now,
                    now,
                ),
            )
        else:
            if existing_slot["token_state"] not in {
                "FAILED",
                "COOLDOWN",
                "ARCHIVED",
                "MANUAL_REVIEW",
            }:
                if existing_slot["mint_identity"] != mint:
                    raise CombinedDiscoveryError("HEALTHY_SLOT_MUTATION")
                if fixtures.mode == "INITIAL":
                    raise CombinedDiscoveryError("CONFLICTING_SLOT")
            slot_id = existing_slot["token_slot_id"]
            # Immutable tracking_queue_id cannot be rebound. Existing slots may
            # proceed only with a lawful already-bound queue; otherwise fail
            # closed before FIRST_15M enqueue / WINDOW_15M_ACTIVE.
            try:
                queue_id = validate_existing_slot_tracking_queue_for_handoff(
                    connection,
                    token_slot_id=str(slot_id),
                    cycle_id=fixtures.cycle_id,
                    token_row_id=token_id,
                    pair_row_id=pair_id,
                )
            except CadenceAuthorityError as exc:
                raise CombinedDiscoveryError(
                    "EXISTING_SLOT_TRACKING_AUTHORITY_INVALID",
                    str(exc),
                ) from exc

        if force_scheduler_failure:
            raise CombinedDiscoveryError("FIRST_15M_JOB_FAILED", "injected scheduler failure")

        job_result, job_id = enqueue_job(
            connection,
            job_name=f"window15m:{mint}:{pool}",
            job_kind=JobKind.TRACK_NORMAL_FIRST_15M,
            target_table="printer_tracking_queue",
            target_id=queue_id,
            scheduled_for=datetime.fromisoformat(now.replace("Z", "+00:00")),
        )
        if job_id is None:
            raise CombinedDiscoveryError("FIRST_15M_JOB_FAILED", str(job_result))

        banned_kinds = {
            JobKind.TRACK_NORMAL_1H.value,
            JobKind.TRACK_NORMAL_4H.value,
            JobKind.TRACK_FAST_1H.value,
            JobKind.TRACK_FAST_4H.value,
            JobKind.TRACK_FAST_MICRO_EVENT.value,
        }
        if any(
            row[0] in banned_kinds
            for row in connection.execute(
                "SELECT job_kind FROM printer_scheduler_jobs WHERE id = ?",
                (job_id,),
            )
        ):
            raise CombinedDiscoveryError("FORBIDDEN_WINDOW_ACTIVATION")

        if fixtures.memory_activation_set is not None:
            selection_reason = MEMORY_OBSERVATION_SELECTION_REASON
        else:
            selection_reason = f"uniform:{cycle_seed[:12]}"
        persist_cycle_rooted_selected_item(
            connection,
            discovery_batch_id=discovery_batch_id,
            selection_batch_id=selection_batch_id,
            merged_candidate_id=candidate.merged_candidate_id,
            campaign_id=command.campaign_id,
            run_id=command.run_id,
            cycle_id=fixtures.cycle_id,
            token_slot_id=slot_id,
            token_id=token_id,
            pair_id=pair_id,
            token_mint=mint,
            pair_address=pool,
            selection_reason=selection_reason,
            tracking_handoff_state="HANDOFF_RECORDED",
            first_window_15m_scheduler_job_id=int(job_id),
            now=now,
        )
        usage.handoffs += 1
        if usage.handoffs > TRACKING_HANDOFFS:
            raise CombinedDiscoveryError("HANDOFF_CEILING")
        self._terminalize_work(
            connection, handoff_work, "SUCCEEDED", "HANDOFF_COMPLETE", now
        )

    def _persist_selection_and_handoff(
        self,
        connection: sqlite3.Connection,
        command: AbstractCampaignCommand,
        usage: _Usage,
        discovery_batch_id: str,
        selection_batch_id: str,
        selected: Sequence[_Merged],
        vacancies: Sequence[int],
        cycle_seed: str,
        now: str,
    ) -> None:
        fixtures = self.fixtures
        if fixtures.mode == "INITIAL":
            self._atomic_initial_two_slot_handoff(
                connection,
                command,
                usage,
                discovery_batch_id=discovery_batch_id,
                selection_batch_id=selection_batch_id,
                selected=selected,
                vacancies=vacancies,
                cycle_seed=cycle_seed,
                now=now,
            )
            return

        # Replacement: token-local single vacancy; healthy occupied slot untouched.
        persist_cycle_rooted_selection_batch(
            connection,
            discovery_batch_id=discovery_batch_id,
            selection_batch_id=selection_batch_id,
            campaign_id=command.campaign_id,
            run_id=command.run_id,
            cycle_id=fixtures.cycle_id,
            selected_count=len(selected),
            now=now,
        )
        for index, candidate in enumerate(selected):
            ordinal = vacancies[index] if index < len(vacancies) else index + 1
            # Never mutate healthy non-vacant ordinals during replacement.
            if fixtures.healthy_slot_ids:
                healthy = connection.execute(
                    """
                    SELECT token_slot_id, mint_identity, token_state, slot_ordinal
                    FROM printer_memory_factory_campaign_token_slots
                    WHERE cycle_id = ? AND token_slot_id = ?
                    """,
                    (fixtures.cycle_id, fixtures.healthy_slot_ids[0]),
                ).fetchone()
                if healthy is not None and int(healthy["slot_ordinal"]) == int(ordinal):
                    raise CombinedDiscoveryError("HEALTHY_SLOT_MUTATION")
            work_type = (
                "DISCOVERY_TRACKING_HANDOFF_SLOT_1"
                if ordinal == 1
                else "DISCOVERY_TRACKING_HANDOFF_SLOT_2"
            )
            handoff_work = self._create_work(
                connection, command, usage, discovery_batch_id, work_type, now
            )
            try:
                if fixtures.force_handoff_failure:
                    raise CombinedDiscoveryError(
                        "DUPLICATE_ACTIVE_TRACKING",
                        "injected replacement vacancy failure",
                    )
                self._handoff_one_slot(
                    connection,
                    command,
                    usage,
                    discovery_batch_id=discovery_batch_id,
                    selection_batch_id=selection_batch_id,
                    candidate=candidate,
                    ordinal=int(ordinal),
                    cycle_seed=cycle_seed,
                    now=now,
                    handoff_work=handoff_work,
                )
            except CombinedDiscoveryError:
                self._terminalize_work(
                    connection, handoff_work, "FAILED", "HANDOFF_ROLLED_BACK", now
                )
                raise

    def _atomic_initial_two_slot_handoff(
        self,
        connection: sqlite3.Connection,
        command: AbstractCampaignCommand,
        usage: _Usage,
        *,
        discovery_batch_id: str,
        selection_batch_id: str,
        selected: Sequence[_Merged],
        vacancies: Sequence[int],
        cycle_seed: str,
        now: str,
    ) -> None:
        """Commit both initial handoffs or neither (SAVEPOINT boundary)."""
        fixtures = self.fixtures
        self._validate_initial_handoff_preflight(
            connection, selected=selected, vacancies=vacancies, usage=usage
        )
        if fixtures.force_handoff_failure == "BEFORE_FIRST":
            raise CombinedDiscoveryError("HANDOFF_BEFORE_FIRST", "injected pre-mutation fault")
        if fixtures.force_handoff_failure == "CONFLICTING_SLOT":
            raise CombinedDiscoveryError(
                "CONFLICTING_SLOT", "injected conflicting slot preflight"
            )

        # Pre-create both handoff work rows outside the mutation savepoint so
        # first-fault work identity remains visible after activation rollback.
        handoff_works: list[str] = []
        for ordinal in (1, 2):
            work_type = (
                "DISCOVERY_TRACKING_HANDOFF_SLOT_1"
                if ordinal == 1
                else "DISCOVERY_TRACKING_HANDOFF_SLOT_2"
            )
            handoff_works.append(
                self._create_work(
                    connection, command, usage, discovery_batch_id, work_type, now
                )
            )

        usage_handoffs_before = usage.handoffs
        connection.execute("SAVEPOINT initial_two_slot_handoff")
        try:
            persist_cycle_rooted_selection_batch(
                connection,
                discovery_batch_id=discovery_batch_id,
                selection_batch_id=selection_batch_id,
                campaign_id=command.campaign_id,
                run_id=command.run_id,
                cycle_id=fixtures.cycle_id,
                selected_count=len(selected),
                now=now,
            )
            for index, candidate in enumerate(selected):
                ordinal = int(vacancies[index])
                if index == 1 and fixtures.force_handoff_failure == "DURING_SECOND":
                    raise CombinedDiscoveryError(
                        "HANDOFF_DURING_SECOND", "injected failure after first handoff"
                    )
                self._handoff_one_slot(
                    connection,
                    command,
                    usage,
                    discovery_batch_id=discovery_batch_id,
                    selection_batch_id=selection_batch_id,
                    candidate=candidate,
                    ordinal=ordinal,
                    cycle_seed=cycle_seed,
                    now=now,
                    handoff_work=handoff_works[index],
                    force_scheduler_failure=(
                        index == 1
                        and fixtures.force_handoff_failure == "SECOND_SCHEDULER_JOB"
                    ),
                    force_duplicate_active=(
                        index == 1
                        and fixtures.force_handoff_failure == "DUPLICATE_ACTIVE"
                    ),
                )

            if usage.handoffs != usage_handoffs_before + 2:
                raise CombinedDiscoveryError("INITIAL_HANDOFF_INCOMPLETE")
            connection.execute("RELEASE SAVEPOINT initial_two_slot_handoff")
        except Exception as exc:
            connection.execute("ROLLBACK TO SAVEPOINT initial_two_slot_handoff")
            connection.execute("RELEASE SAVEPOINT initial_two_slot_handoff")
            usage.handoffs = usage_handoffs_before
            cause = (
                exc.code
                if isinstance(exc, CombinedDiscoveryError)
                else "HANDOFF_ROLLED_BACK"
            )
            for work_id in handoff_works:
                self._terminalize_work(
                    connection,
                    work_id,
                    "FAILED",
                    cause,
                    now,
                )
            if isinstance(exc, CombinedDiscoveryError):
                raise
            raise CombinedDiscoveryError("HANDOFF_DURING_SECOND", str(exc)) from exc

    def _persist_reports(
        self,
        connection: sqlite3.Connection,
        command: AbstractCampaignCommand,
        discovery_batch_id: str,
        provider_reports: Sequence[Mapping[str, Any]],
        usage: _Usage,
        now: str,
    ) -> None:
        del provider_reports
        payload = {
            "planned": list(WORK_TYPES_ORDER),
            "source_calls": usage.source_calls,
            "scheduler_work": usage.scheduler_work,
            "storage_bytes": usage.storage_bytes,
            "failures": usage.failures,
            "observations": usage.observations,
            "unique_mints": sorted(usage.unique_mints),
            "handoffs": usage.handoffs,
            "discarded_non_authoritative_fields": list(DISCARDED_NON_AUTHORITATIVE_FIELDS),
            "locked_financial_tables": list(LOCKED_FINANCIAL_TABLES),
        }
        insert_provider_report_link(
            connection,
            report_link_id=f"report:{discovery_batch_id}",
            discovery_batch_id=discovery_batch_id,
            campaign_id=command.campaign_id,
            configuration_id=command.configuration_id,
            report_payload=payload,
            now=now,
        )


def build_combined_executor(
    fixtures: CombinedDiscoveryFixtures,
) -> CombinedPumpfunCampaignExecutor:
    return CombinedPumpfunCampaignExecutor(fixtures)

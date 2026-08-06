"""Permanent mint-first discovery availability policy and persistence helpers.

This module is not a discovery engine. The canonical runtime owner remains
``eligible_token_supply.run_persistent_eligible_token_supply``. These helpers
provide its exact mint+pool state, reserve layers, categorical fair traversal,
immutable stage budget and neutral frozen-reserve contracts.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
import json
import math
import re
import sqlite3
from typing import Any, Mapping, Sequence


NETWORK = "solana-mainnet"

CURRENT_VISIBLE = "CURRENT_VISIBLE"
BELOW_LIQUIDITY_FLOOR = "BELOW_LIQUIDITY_FLOOR"
EXACT_POOL_NO_MATCH = "EXACT_POOL_NO_MATCH"
POOL_RECONCILIATION_DUE = "POOL_RECONCILIATION_DUE"
SAME_POOL_REOBSERVED = "SAME_POOL_REOBSERVED"
NEW_POOL_PENDING_PROOF = "NEW_POOL_PENDING_PROOF"
CURRENT_POOL_CONFIRMED = "CURRENT_POOL_CONFIRMED"
NO_SUPPORTED_CURRENT_POOL = "NO_SUPPORTED_CURRENT_POOL"
SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
UNSUPPORTED_VENUE = "UNSUPPORTED_VENUE"
CONTRACT_BLOCKED = "CONTRACT_BLOCKED"

EXACT_MARKET_STATES = frozenset(
    {
        CURRENT_VISIBLE,
        BELOW_LIQUIDITY_FLOOR,
        EXACT_POOL_NO_MATCH,
        POOL_RECONCILIATION_DUE,
        SAME_POOL_REOBSERVED,
        NEW_POOL_PENDING_PROOF,
        CURRENT_POOL_CONFIRMED,
        NO_SUPPORTED_CURRENT_POOL,
        SOURCE_UNAVAILABLE,
        IDENTITY_CONFLICT,
        UNSUPPORTED_VENUE,
        CONTRACT_BLOCKED,
    }
)

BROAD_NOMINATED = "BROAD_NOMINATED"
ABOVE_FLOOR_NOMINATED = "ABOVE_FLOOR_NOMINATED"
MARKET_READY = "MARKET_READY"
MEMORY_OBSERVATION_ELIGIBLE = "MEMORY_OBSERVATION_ELIGIBLE"
FULLY_ELIGIBLE = "FULLY_ELIGIBLE"
RESERVE_LAYERS = frozenset(
    {
        BROAD_NOMINATED,
        ABOVE_FLOOR_NOMINATED,
        MARKET_READY,
        MEMORY_OBSERVATION_ELIGIBLE,
        FULLY_ELIGIBLE,
    }
)

# Categorical prefilter / protocol-due reason codes (state remains existing enum).
REASON_ABOVE_FLOOR_NOMINATION = "ABOVE_FLOOR_NOMINATION_REQUIRES_PROTOCOL_CONFIRMATION"
REASON_LIQUIDITY_UNKNOWN = "LIQUIDITY_UNKNOWN"
REASON_FRESH_AGGREGATOR_LEGACY = "FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF"
REASON_BELOW_FLOOR = "BELOW_3000_FLOOR"
PROTOCOL_DUE_REASONS = frozenset(
    {
        REASON_ABOVE_FLOOR_NOMINATION,
        REASON_FRESH_AGGREGATOR_LEGACY,
    }
)

MINIMUM_FREEZE_DEPTH = 4
OBSERVATION_SURPLUS_TARGET = 8
SELECTION_FLOOR_USD = 3000.0

TRAVERSAL_CATEGORIES = (
    "FRESH_NOMINATION",
    "DIRECT_MIGRATION",
    "DUE_PERSISTED",
    "POOL_RECONCILIATION",
    "REVIVAL_OR_DISTINCT_EVIDENCE",
)

STAGE_RESERVATIONS = (
    ("intake", 3),
    ("market_batching", 2),
    ("reconciliation", 6),
    ("protocol_confirmation", 7),
    ("holder_safety", 8),
    ("final_refresh_handoff", 4),
)

SOLANA_INFRASTRUCTURE_MINTS = frozenset(
    {
        "So11111111111111111111111111111111111111112",
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    }
)

SPL_TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
EXACT_POOL_RECONCILIATION_SECONDS = 1_800
SUPPORTED_PUMPSWAP_PROVIDER_VENUES = frozenset(
    {"pumpswap", "pumpfun", "pump-amm"}
)


def _liquidity_evidence_expiry(observed_at: str) -> str:
    return (
        _parse_iso(observed_at) + timedelta(seconds=EXACT_POOL_RECONCILIATION_SECONDS)
    ).isoformat()


def _coerce_liquidity_usd(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        raw = raw.get("usd") if "usd" in raw else raw.get("liquidity_usd")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    # Reject NaN, ±infinity, and negative liquidity.
    if not math.isfinite(value) or value < 0:
        return None
    return value


def resolve_liquidity_evidence_expiry(
    *,
    observed_at: str,
    explicit_expiry: str | None,
    ingestion_now: str | None = None,
) -> str | None:
    """Return observation-based evidence expiry or None when contradictory.

    Default: observed_at + EXACT_POOL_RECONCILIATION_SECONDS.
    Explicit expiry must be timezone-aware, strictly after observed_at, and must
    not exceed the observation-based maximum. Ingestion time never extends
    freshness when observed_at is older.
    """
    del ingestion_now  # freshness is never extended from ingestion time
    try:
        observed = _parse_iso(observed_at)
    except (TypeError, ValueError):
        return None
    max_expiry = observed + timedelta(seconds=EXACT_POOL_RECONCILIATION_SECONDS)
    if explicit_expiry is None or str(explicit_expiry).strip() == "":
        return max_expiry.isoformat()
    raw = str(explicit_expiry).strip()
    # Require explicit timezone awareness (Z or offset); bare local times fail closed.
    if "Z" not in raw and "+" not in raw[1:] and raw.count("-") < 3:
        # Allow ISO with trailing offset via fromisoformat; reject naive results.
        pass
    try:
        explicit = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if explicit.tzinfo is None:
        return None
    if explicit.tzinfo is not None and observed.tzinfo is not None:
        explicit = explicit.astimezone(observed.tzinfo)
    if explicit <= observed:
        return None
    if explicit > max_expiry:
        return None
    return explicit.isoformat()


def classify_exact_pool_liquidity_prefilter(
    *,
    liquidity_usd: float | None,
) -> tuple[str, str]:
    """Return (exact_market_state, reason) for one exact-pool liquidity prefilter.

    Floor is unchanged at $3,000. Liquidity belongs only to the exact nominated
    pool; callers must never pass token-wide or alternate-pool values.
    """
    if liquidity_usd is None:
        return CONTRACT_BLOCKED, REASON_LIQUIDITY_UNKNOWN
    if float(liquidity_usd) < SELECTION_FLOOR_USD:
        return BELOW_LIQUIDITY_FLOOR, REASON_BELOW_FLOOR
    return CONTRACT_BLOCKED, REASON_ABOVE_FLOOR_NOMINATION


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class ExactMarketObservation:
    network: str
    mint: str
    pool: str
    token_program: str
    pool_program: str
    base_mint: str
    quote_mint: str
    venue: str
    state: str
    reason: str
    observed_at: str
    next_lawful_action_at: str | None
    source_provenance: Mapping[str, Any]
    contract_version: str


def record_exact_market_transition(
    connection: sqlite3.Connection,
    observation: ExactMarketObservation,
    *,
    now: str,
) -> int:
    """Update one exact projection and append its categorical transition."""
    if observation.network != NETWORK:
        raise ValueError("UNSUPPORTED_NETWORK")
    if observation.state not in EXACT_MARKET_STATES:
        raise ValueError("UNSUPPORTED_EXACT_MARKET_STATE")
    required = (
        observation.mint,
        observation.pool,
        observation.token_program,
        observation.pool_program,
        observation.base_mint,
        observation.quote_mint,
        observation.venue,
        observation.reason,
        observation.contract_version,
    )
    if not all(str(item).strip() for item in required):
        raise ValueError("INCOMPLETE_EXACT_MARKET_IDENTITY")
    _parse_iso(observation.observed_at)
    if observation.next_lawful_action_at is not None:
        _parse_iso(observation.next_lawful_action_at)

    prior = connection.execute(
        """SELECT * FROM printer_exact_market_states
           WHERE network=? AND mint_identity=? AND pool_address=?""",
        (observation.network, observation.mint, observation.pool),
    ).fetchone()
    prior_map = None if prior is None else dict(prior)
    if prior_map is not None:
        identity_fields = (
            ("token_program", "token_program_id"),
            ("pool_program", "pool_program_id"),
            ("base_mint", "base_mint"),
            ("quote_mint", "quote_mint"),
            ("venue", "venue"),
        )
        conflicts: dict[str, dict[str, str]] = {}
        for attribute, column in identity_fields:
            old = str(prior_map[column])
            new = str(getattr(observation, attribute))
            unresolved = old.startswith("UNRESOLVED_") or old.startswith("UNKNOWN_")
            if old != new and not unresolved:
                conflicts[attribute] = {"preserved": old, "observed": new}
        if conflicts:
            observation = replace(
                observation,
                token_program=str(prior_map["token_program_id"]),
                pool_program=str(prior_map["pool_program_id"]),
                base_mint=str(prior_map["base_mint"]),
                quote_mint=str(prior_map["quote_mint"]),
                venue=str(prior_map["venue"]),
                state=IDENTITY_CONFLICT,
                reason="EXACT_MARKET_RESOLVED_IDENTITY_CONFLICT",
                source_provenance={
                    **dict(observation.source_provenance),
                    "identity_conflicts": conflicts,
                },
            )
    prior_state = None if prior_map is None else str(prior_map["current_state"])
    no_match_count = 0 if prior_map is None else int(prior_map["no_match_count"])
    no_match_streak = 0 if prior_map is None else int(prior_map["no_match_streak"])
    last_visible_at = None if prior_map is None else prior_map["last_visible_at"]
    last_no_match_at = None if prior_map is None else prior_map["last_no_match_at"]
    if observation.state == EXACT_POOL_NO_MATCH:
        no_match_count += 1
        no_match_streak += 1
        last_no_match_at = observation.observed_at
    elif observation.state in {
        CURRENT_VISIBLE,
        SAME_POOL_REOBSERVED,
        CURRENT_POOL_CONFIRMED,
        BELOW_LIQUIDITY_FLOOR,
    }:
        no_match_streak = 0
        last_visible_at = observation.observed_at

    provenance_json = _canonical_json(observation.source_provenance)
    connection.execute(
        """INSERT INTO printer_exact_market_states(
            network,mint_identity,pool_address,token_program_id,pool_program_id,
            base_mint,quote_mint,venue,current_state,current_reason,
            last_observed_at,last_visible_at,last_no_match_at,no_match_count,
            no_match_streak,next_lawful_action_at,latest_source_provenance_json,
            contract_version,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(network,mint_identity,pool_address) DO UPDATE SET
            token_program_id=excluded.token_program_id,
            pool_program_id=excluded.pool_program_id,
            base_mint=excluded.base_mint,
            quote_mint=excluded.quote_mint,
            venue=excluded.venue,
            current_state=excluded.current_state,
            current_reason=excluded.current_reason,
            last_observed_at=excluded.last_observed_at,
            last_visible_at=excluded.last_visible_at,
            last_no_match_at=excluded.last_no_match_at,
            no_match_count=excluded.no_match_count,
            no_match_streak=excluded.no_match_streak,
            next_lawful_action_at=excluded.next_lawful_action_at,
            latest_source_provenance_json=excluded.latest_source_provenance_json,
            contract_version=excluded.contract_version,
            updated_at=excluded.updated_at""",
        (
            observation.network,
            observation.mint,
            observation.pool,
            observation.token_program,
            observation.pool_program,
            observation.base_mint,
            observation.quote_mint,
            observation.venue,
            observation.state,
            observation.reason,
            observation.observed_at,
            last_visible_at,
            last_no_match_at,
            no_match_count,
            no_match_streak,
            observation.next_lawful_action_at,
            provenance_json,
            observation.contract_version,
            now,
            now,
        ),
    )
    cursor = connection.execute(
        """INSERT INTO printer_exact_market_state_transitions(
            network,mint_identity,pool_address,prior_state,new_state,reason_code,
            observed_at,next_lawful_action_at,source_provenance_json,
            contract_version,recorded_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            observation.network,
            observation.mint,
            observation.pool,
            prior_state,
            observation.state,
            observation.reason,
            observation.observed_at,
            observation.next_lawful_action_at,
            provenance_json,
            observation.contract_version,
            now,
        ),
    )
    return int(cursor.lastrowid)


def load_exact_market_states(
    connection: sqlite3.Connection,
    *,
    mint: str | None = None,
) -> list[dict[str, Any]]:
    connection.row_factory = sqlite3.Row
    if mint is None:
        rows = connection.execute(
            """SELECT * FROM printer_exact_market_states
               ORDER BY mint_identity,pool_address"""
        ).fetchall()
    else:
        rows = connection.execute(
            """SELECT * FROM printer_exact_market_states
               WHERE network=? AND mint_identity=? ORDER BY pool_address""",
            (NETWORK, mint),
        ).fetchall()
    return [dict(row) for row in rows]


def should_poll_exact_pool(state: Mapping[str, Any], *, at: str) -> bool:
    """Suppress exact-pair repeats after a lawful no-match until its boundary."""
    if str(state.get("current_state")) != EXACT_POOL_NO_MATCH:
        return True
    due = state.get("next_lawful_action_at")
    if not due:
        return False
    return _parse_iso(at) >= _parse_iso(str(due))


def upsert_reserve_layer(
    connection: sqlite3.Connection,
    *,
    network: str,
    mint: str,
    pool: str,
    layer: str,
    reserve_state: str,
    reason: str,
    observed_at: str,
    next_lawful_action_at: str | None,
    evidence_expires_at: str | None,
    source_provenance: Mapping[str, Any],
    evidence: Mapping[str, Any],
    campaign_id: str | None,
) -> None:
    if layer not in RESERVE_LAYERS:
        raise ValueError("UNSUPPORTED_RESERVE_LAYER")
    prior = connection.execute(
        """SELECT source_provenance_json
           FROM printer_discovery_reserve_layers
           WHERE network=? AND mint_identity=? AND pool_address=?
             AND reserve_layer=?""",
        (network, mint, pool, layer),
    ).fetchone()
    accumulated: list[dict[str, Any]] = []
    if prior is not None:
        try:
            decoded = json.loads(str(prior[0]))
        except (TypeError, ValueError, json.JSONDecodeError):
            decoded = {}
        if isinstance(decoded, Mapping) and isinstance(
            decoded.get("observations"), list
        ):
            accumulated.extend(
                dict(item)
                for item in decoded["observations"]
                if isinstance(item, Mapping)
            )
        elif isinstance(decoded, Mapping) and decoded:
            accumulated.append(dict(decoded))
    accumulated.append(dict(source_provenance))
    unique_provenance = {
        _canonical_json(item): item for item in accumulated
    }
    provenance_envelope = {
        "observations": [
            unique_provenance[key] for key in sorted(unique_provenance)
        ]
    }
    connection.execute(
        """INSERT INTO printer_discovery_reserve_layers(
            network,mint_identity,pool_address,reserve_layer,reserve_state,
            categorical_reason,observed_at,next_lawful_action_at,
            evidence_expires_at,source_provenance_json,evidence_json,
            last_campaign_id,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(network,mint_identity,pool_address,reserve_layer) DO UPDATE SET
            reserve_state=excluded.reserve_state,
            categorical_reason=excluded.categorical_reason,
            observed_at=excluded.observed_at,
            next_lawful_action_at=excluded.next_lawful_action_at,
            evidence_expires_at=excluded.evidence_expires_at,
            source_provenance_json=excluded.source_provenance_json,
            evidence_json=excluded.evidence_json,
            last_campaign_id=excluded.last_campaign_id,
            updated_at=excluded.updated_at""",
        (
            network,
            mint,
            pool,
            layer,
            reserve_state,
            reason,
            observed_at,
            next_lawful_action_at,
            evidence_expires_at,
            _canonical_json(provenance_envelope),
            _canonical_json(evidence),
            campaign_id,
            observed_at,
            observed_at,
        ),
    )


@dataclass(frozen=True)
class CandidateObservation:
    category: str
    mint: str
    pool: str
    source: str
    due_at: str
    provenance: Mapping[str, Any] = field(default_factory=dict)


def interleave_candidate_observations(
    observations: Sequence[CandidateObservation],
) -> list[CandidateObservation]:
    """Round-robin categories; oldest due then stable identity within each."""
    buckets: dict[str, deque[CandidateObservation]] = {}
    for category in TRAVERSAL_CATEGORIES:
        materialized = sorted(
            (item for item in observations if item.category == category),
            key=lambda item: (
                _parse_iso(item.due_at),
                item.mint,
                item.pool,
                item.source,
            ),
        )
        buckets[category] = deque(materialized)
    unsupported = sorted(
        {item.category for item in observations} - set(TRAVERSAL_CATEGORIES)
    )
    if unsupported:
        raise ValueError(f"UNSUPPORTED_TRAVERSAL_CATEGORY:{','.join(unsupported)}")
    result: list[CandidateObservation] = []
    while any(buckets.values()):
        for category in TRAVERSAL_CATEGORIES:
            if buckets[category]:
                result.append(buckets[category].popleft())
    return result


@dataclass(frozen=True)
class MergedMintObservations:
    mint: str
    pools: tuple[str, ...]
    sources: tuple[str, ...]
    observations: tuple[CandidateObservation, ...]
    identity_disagreement: bool


def merge_candidate_observations(
    observations: Sequence[CandidateObservation],
) -> dict[str, MergedMintObservations]:
    grouped: dict[str, list[CandidateObservation]] = defaultdict(list)
    for item in observations:
        if not item.mint or not item.pool or not item.source:
            raise ValueError("INCOMPLETE_CANDIDATE_OBSERVATION")
        grouped[item.mint].append(item)
    result: dict[str, MergedMintObservations] = {}
    for mint in sorted(grouped):
        items = tuple(
            sorted(
                grouped[mint],
                key=lambda item: (item.pool, item.source, item.due_at, item.category),
            )
        )
        pools = tuple(sorted({item.pool for item in items}))
        sources = tuple(sorted({item.source for item in items}))
        result[mint] = MergedMintObservations(
            mint=mint,
            pools=pools,
            sources=sources,
            observations=items,
            identity_disagreement=len(pools) > 1,
        )
    return result


def order_canonical_inventory_fairly(
    connection: sqlite3.Connection,
    *,
    inventory_rows: Sequence[Mapping[str, Any]],
    latest_mints: Sequence[str],
    fresh_mints: Sequence[str],
    now: str,
) -> list[Mapping[str, Any]]:
    """Build the canonical categorical traversal over exact graduated rows."""
    latest = {str(item) for item in latest_mints}
    fresh = {str(item) for item in fresh_mints}
    observations: list[CandidateObservation] = []
    rows_by_identity: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in inventory_rows:
        mint = str(row.get("mint_identity") or "")
        pool = str(row.get("pumpswap_pool") or "")
        if not mint or not pool:
            continue
        rows_by_identity[(mint, pool)] = row
        due_at = str(
            row.get("latest_observed_at")
            or row.get("first_observed_at")
            or now
        )
        category = "DUE_PERSISTED"
        source = "graduated_registry"
        state = connection.execute(
            """SELECT current_state,next_lawful_action_at,last_observed_at
               FROM printer_exact_market_states
               WHERE network=? AND mint_identity=? AND pool_address=?""",
            (NETWORK, mint, pool),
        ).fetchone()
        if state is not None:
            state_map = dict(state)
            next_action = str(state_map.get("next_lawful_action_at") or due_at)
            if str(state_map.get("current_state")) in {
                EXACT_POOL_NO_MATCH,
                POOL_RECONCILIATION_DUE,
                NEW_POOL_PENDING_PROOF,
            } and _parse_iso(next_action) <= _parse_iso(now):
                category = "POOL_RECONCILIATION"
                source = "exact_market_state"
                due_at = next_action
            elif str(state_map.get("current_state")) in {
                SAME_POOL_REOBSERVED,
                CURRENT_VISIBLE,
            }:
                category = "REVIVAL_OR_DISTINCT_EVIDENCE"
                source = "exact_market_state"
                due_at = str(state_map.get("last_observed_at") or due_at)
        # Current-cycle evidence has precedence only for categorical placement;
        # round-robin traversal remains neutral within and across categories.
        if mint in latest:
            category = "DIRECT_MIGRATION"
            source = "direct_pump_migration"
        if mint in fresh:
            category = "FRESH_NOMINATION"
            source = "dexscreener_fresh_profiles"
        observations.append(
            CandidateObservation(
                category=category,
                mint=mint,
                pool=pool,
                source=source,
                due_at=due_at,
            )
        )
    ordered: list[Mapping[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for observation in interleave_candidate_observations(observations):
        identity = (observation.mint, observation.pool)
        if identity in seen:
            continue
        seen.add(identity)
        ordered.append(rows_by_identity[identity])
    return ordered


@dataclass
class StageBudget:
    """Seal-gated permanent conversion capacity.

    Stages may run concurrently while unsealed. Unused capacity from a stage
    flows forward only after that stage is explicitly sealed. Later stages never
    lend capacity backward. There is no global rewind exception path.
    """

    reservations: tuple[tuple[str, int], ...]
    current_index: int = 0
    used_by_stage: dict[str, int] = field(default_factory=dict)
    sealed: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not self.reservations or any(value < 0 for _, value in self.reservations):
            raise ValueError("INVALID_STAGE_RESERVATIONS")
        if len({name for name, _ in self.reservations}) != len(self.reservations):
            raise ValueError("DUPLICATE_STAGE_RESERVATION")
        for name, _ in self.reservations:
            self.used_by_stage.setdefault(name, 0)
        if not isinstance(self.sealed, set):
            self.sealed = set(self.sealed)

    @classmethod
    def permanent_discovery_default(cls) -> "StageBudget":
        return cls(STAGE_RESERVATIONS)

    @property
    def total_ceiling(self) -> int:
        return sum(value for _, value in self.reservations)

    @property
    def stage_names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.reservations)

    def _index(self, stage: str) -> int:
        try:
            return self.stage_names.index(stage)
        except ValueError as exc:
            raise ValueError("UNKNOWN_BUDGET_STAGE") from exc

    def advance(self, stage: str) -> None:
        """Seal every earlier stage so residual capacity may flow to ``stage``.

        Retained for call-site compatibility. Prefer explicit :meth:`seal` for
        permanent conversion loops.
        """
        index = self._index(stage)
        for name, _ in self.reservations[:index]:
            self.sealed.add(name)
        self.current_index = max(self.current_index, index)

    def seal(self, stage: str) -> None:
        index = self._index(stage)
        self.sealed.add(stage)
        self.current_index = max(self.current_index, index)

    def is_sealed(self, stage: str) -> bool:
        return stage in self.sealed

    def available(self, stage: str) -> int:
        """Own remaining capacity plus unused capacity from sealed earlier stages."""
        index = self._index(stage)
        available = 0
        for i, (name, reserved) in enumerate(self.reservations[: index + 1]):
            remaining = max(0, int(reserved) - int(self.used_by_stage.get(name, 0)))
            if i == index:
                available += remaining
            elif name in self.sealed:
                available += remaining
        return available

    def _available_at(self, index: int) -> int:
        return self.available(self.stage_names[index])

    def consume(self, stage: str, count: int = 1) -> None:
        if type(count) is not int or count < 0:
            raise ValueError("INVALID_STAGE_OPERATION_COUNT")
        index = self._index(stage)
        if stage in self.sealed:
            raise ValueError("STAGE_ALREADY_SEALED")
        if count > self.available(stage):
            raise ValueError("STAGE_RESERVATION_EXCEEDED")
        self.used_by_stage[stage] += count
        self.current_index = max(self.current_index, index)

    def protected_remaining(self, stage: str) -> int:
        index = self._index(stage)
        reserved = self.reservations[index][1]
        return max(0, reserved - self.used_by_stage[stage])

    def remaining_by_stage(self) -> dict[str, int]:
        return {
            name: max(0, reserved - self.used_by_stage.get(name, 0))
            for name, reserved in self.reservations
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "reservations": {name: reserved for name, reserved in self.reservations},
            "used_by_stage": dict(self.used_by_stage),
            "remaining_by_stage": self.remaining_by_stage(),
            "sealed_stages": sorted(self.sealed),
            "unsealed_stages": [
                name for name in self.stage_names if name not in self.sealed
            ],
            "total_ceiling": self.total_ceiling,
            "total_used": sum(self.used_by_stage.values()),
            "total_remaining": self.total_ceiling - sum(self.used_by_stage.values()),
        }


@dataclass(frozen=True)
class BatchPoolRow:
    mint: str
    pool: str
    base_mint: str
    quote_mint: str
    venue: str
    liquidity_usd: float | None
    observed_at: str
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class MintBatchResolution:
    batch_size: int
    by_mint: Mapping[str, tuple[BatchPoolRow, ...]]
    current_pool_by_mint: Mapping[str, str]
    local_exclusions: tuple[Mapping[str, str], ...]
    unresolved_mints: tuple[str, ...]


def resolve_dexscreener_mint_batch(
    due_mints: Sequence[str],
    normalized_pairs: Sequence[Mapping[str, Any]],
    *,
    observed_at: str,
) -> MintBatchResolution:
    """Preserve every exact returned pool; never choose by provider order/size."""
    distinct = tuple(sorted({str(mint).strip() for mint in due_mints if str(mint).strip()}))
    if not 1 <= len(distinct) <= 30:
        raise ValueError("DEXSCREENER_BATCH_SIZE_OUT_OF_CONTRACT")
    requested = set(distinct)
    grouped: dict[str, list[BatchPoolRow]] = defaultdict(list)
    exclusions: list[dict[str, str]] = []
    for raw in normalized_pairs:
        base_token = raw.get("baseToken") if isinstance(raw.get("baseToken"), Mapping) else {}
        quote_token = raw.get("quoteToken") if isinstance(raw.get("quoteToken"), Mapping) else {}
        mint = str(
            raw.get("candidate_mint")
            or raw.get("token_mint")
            or raw.get("base_mint")
            or base_token.get("address")
            or ""
        )
        pool = str(raw.get("pair_address") or raw.get("pairAddress") or "")
        chain = str(
            raw.get("chain") or raw.get("chain_id") or raw.get("chainId") or ""
        ).lower()
        base = str(raw.get("base_mint") or mint)
        quote = str(raw.get("quote_mint") or quote_token.get("address") or "")
        venue = str(raw.get("dex_id") or raw.get("dex") or raw.get("venue") or "")
        reason = None
        if mint not in requested:
            reason = "MINT_NOT_REQUESTED"
        elif chain != "solana":
            reason = "NON_SOLANA_POOL"
        elif not pool or base != mint or not quote:
            reason = "INCOMPLETE_ORIENTATION"
        elif mint in SOLANA_INFRASTRUCTURE_MINTS:
            reason = "INFRASTRUCTURE_MINT"
        if reason:
            exclusions.append({"mint": mint, "pool": pool, "reason": reason})
            continue
        liquidity = raw.get("liquidity_usd")
        if liquidity is None and isinstance(raw.get("liquidity"), Mapping):
            liquidity = raw["liquidity"].get("usd")
        grouped[mint].append(
            BatchPoolRow(
                mint=mint,
                pool=pool,
                base_mint=base,
                quote_mint=quote,
                venue=venue,
                liquidity_usd=None if liquidity is None else float(liquidity),
                observed_at=observed_at,
                raw=dict(raw),
            )
        )
    stable = {
        mint: tuple(sorted(rows, key=lambda row: (row.pool, row.venue, row.quote_mint)))
        for mint, rows in sorted(grouped.items())
    }
    return MintBatchResolution(
        batch_size=len(distinct),
        by_mint=stable,
        current_pool_by_mint={},
        local_exclusions=tuple(exclusions),
        unresolved_mints=tuple(mint for mint in distinct if mint not in stable),
    )


@dataclass(frozen=True)
class PoolReconciliation:
    mint: str
    historical_pool: str
    observed_pool: str
    state: str
    reason: str


def reconcile_pool_identity(
    *,
    mint: str,
    historical_pool: str,
    observed_pool: str,
    exact_identity: bool,
    supported_contract: bool,
    protocol_confirmed: bool,
) -> PoolReconciliation:
    if not exact_identity:
        return PoolReconciliation(
            mint, historical_pool, observed_pool, IDENTITY_CONFLICT,
            "EXACT_MINT_OR_ORIENTATION_FAILED",
        )
    if not supported_contract:
        return PoolReconciliation(
            mint, historical_pool, observed_pool, CONTRACT_BLOCKED,
            "POOL_CONTRACT_UNSUPPORTED",
        )
    if observed_pool == historical_pool:
        return PoolReconciliation(
            mint, historical_pool, observed_pool, SAME_POOL_REOBSERVED,
            "SAME_EXACT_POOL_VISIBLE_AGAIN",
        )
    if not protocol_confirmed:
        return PoolReconciliation(
            mint, historical_pool, observed_pool, NEW_POOL_PENDING_PROOF,
            "DIFFERENT_POOL_REQUIRES_EXACT_PROOF",
        )
    return PoolReconciliation(
        mint, historical_pool, observed_pool, CURRENT_POOL_CONFIRMED,
        "DIFFERENT_POOL_EXACTLY_CONFIRMED",
    )


def mint_set_digest(mints: Sequence[str]) -> str:
    """Stable content fingerprint for an ordered mint set (not sole identity)."""
    import hashlib

    ordered = sorted({str(m).strip() for m in mints if str(m).strip()})
    payload = "\n".join(ordered).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def parse_mint_market_batch_stage_sequence(request_key: str) -> int | None:
    """Reconstruct stage sequence embedded in a durable market-batch request key."""
    import re

    text = str(request_key or "")
    match = re.search(r"(?:mint-batch-r|protocol-resume-mb)(\d+)$", text)
    if match is None:
        return None
    sequence = int(match.group(1))
    return sequence if sequence >= 1 else None


def next_mint_market_batch_stage_sequence(
    connection: sqlite3.Connection | None,
    *,
    request_key_prefix: str,
) -> int:
    """Allocate the next monotonic MINT_MARKET_BATCH sequence for a cycle prefix.

    Durable reconstruction uses existing ``printer_source_requests.request_key``
    values that embed the sequence. When no prior keys exist, returns 1.
    """
    prefix = str(request_key_prefix or "").strip()
    highest = 0
    if connection is not None and prefix:
        rows = connection.execute(
            """
            SELECT request_key FROM printer_source_requests
            WHERE request_key LIKE ?
            ORDER BY id ASC
            """,
            (f"{prefix}-%",),
        ).fetchall()
        for row in rows:
            key = row[0] if not isinstance(row, Mapping) else row["request_key"]
            parsed = parse_mint_market_batch_stage_sequence(str(key))
            if parsed is not None and parsed > highest:
                highest = parsed
    return highest + 1


def build_mint_market_batch_request_key(
    *,
    request_key_prefix: str,
    stage_sequence: int,
    kind: str = "round",
) -> str:
    """Build durable request key carrying the allocated stage sequence."""
    sequence = int(stage_sequence)
    if sequence < 1:
        raise ValueError("INVALID_MINT_MARKET_BATCH_STAGE_SEQUENCE")
    prefix = str(request_key_prefix or "").strip() or "mint-market"
    if kind == "protocol_resume":
        return f"{prefix}-protocol-resume-mb{sequence}"
    return f"{prefix}-mint-batch-r{sequence}"


def build_mint_market_batch_logical_identity(
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    stage_sequence: int,
    ordered_mints: Sequence[str],
) -> dict[str, Any]:
    """Immutable logical identity for one mint-market batch (sequence + digest)."""
    from printer_v1.sources.campaign_six_unit_accounting import build_campaign_stage_id

    sequence = int(stage_sequence)
    if sequence < 1:
        raise ValueError("INVALID_MINT_MARKET_BATCH_STAGE_SEQUENCE")
    digest = mint_set_digest(ordered_mints)
    stage_id = build_campaign_stage_id(
        campaign_id=str(campaign_id),
        run_id=str(run_id),
        cycle_id=str(cycle_id),
        stage_kind="MINT_MARKET_BATCH",
        stage_sequence=sequence,
    )
    return {
        "logical_batch_id": f"{stage_id}|{digest[:16]}",
        "stage_id": stage_id,
        "stage_kind": "MINT_MARKET_BATCH",
        "stage_sequence": sequence,
        "mint_set_digest": digest,
        "ordered_mint_count": len(sorted({str(m).strip() for m in ordered_mints if str(m).strip()})),
    }


def run_dexscreener_batch_market_resolution(
    connection: sqlite3.Connection,
    *,
    inventory_rows: Sequence[Mapping[str, Any]],
    request_key: str,
    now: str,
    campaign_id: str | None,
    transport: Any | None = None,
    transport_factory: Any | None = None,
    geckoterminal_transport_factory: Any | None = None,
    enable_geckoterminal_fallback: bool = False,
    before_geckoterminal_request: Any | None = None,
    recent_request_count: int = 0,
    run_id: str | None = None,
    cycle_id: str | None = None,
    stage_evidence_sink: Any | None = None,
    transport_identity_observer: Any | None = None,
    stage_sequence: int | None = None,
) -> dict[str, Any]:
    """Resolve due graduated inventory by exact mint in governed batches.

    This is the canonical owner's market stage, not another discovery engine.
    Provider order and liquidity magnitude never choose a pool. A historical
    exact pool is admitted only when that exact identity is visible and clears
    the existing categorical $3,000 floor. Other returned pools are preserved as
    pending reconciliation and can never silently replace it.

    ``stage_sequence`` is the durable monotonic logical-batch sequence for
    six-unit sealing (``MINT_MARKET_BATCH|N``). When omitted, sequence is
    reconstructed from ``request_key`` or defaults to 1 only for a first batch
    key that carries no embedded sequence.
    """
    from printer_v1.contracts.enums import SourceStatus
    from printer_v1.discovery.graduated_liquidity_front_door import (
        LIQUIDITY_BELOW_SELECTION_FLOOR,
        LIQUIDITY_PROVEN,
        LIQUIDITY_UNPROVEN,
        _cooldown_ok,
        _extract_exact_pair_liquidity,
        classify_liquidity,
        record_market_floor_state,
    )
    from printer_v1.sources.contracts import build_governed_source_request
    from printer_v1.sources.dexscreener import (
        DEXSCREENER_SOURCE_NAME,
        build_dexscreener_adapter,
    )
    from printer_v1.sources.governed_execution import (
        execute_source_request_with_governor,
    )
    from printer_v1.sources.pumpswap_graduated_registry import (
        GRADUATED_LIFECYCLE,
        PUMPSWAP_AMM_PROGRAM_ID,
        PUMPSWAP_VENUE,
    )
    from printer_v1.sources.measured_transport import (
        MeasuredTransportLedger,
        record_payload_transports,
    )

    measured_ledger = MeasuredTransportLedger(
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        on_transport_recorded=transport_identity_observer,
    )

    due: list[Mapping[str, Any]] = []
    suppressed: list[Mapping[str, Any]] = []
    preflight_transition_ids: list[int] = []
    reconciliation_mints: set[str] = set()
    for row in sorted(
        inventory_rows,
        key=lambda item: (
            str(item.get("latest_observed_at") or item.get("first_observed_at") or now),
            str(item.get("mint_identity") or ""),
            str(item.get("pumpswap_pool") or ""),
        ),
    ):
        mint = str(row.get("mint_identity") or "")
        pool = str(row.get("pumpswap_pool") or "")
        prior = connection.execute(
            """SELECT * FROM printer_exact_market_states
               WHERE network=? AND mint_identity=? AND pool_address=?""",
            (NETWORK, mint, pool),
        ).fetchone()
        if prior is not None:
            prior_map = dict(prior)
            if not should_poll_exact_pool(prior_map, at=now):
                suppressed.append(row)
                continue
            if str(prior_map.get("current_state")) == EXACT_POOL_NO_MATCH:
                preflight_transition_ids.append(
                    record_exact_market_transition(
                        connection,
                        ExactMarketObservation(
                            network=NETWORK,
                            mint=mint,
                            pool=pool,
                            token_program=str(prior_map["token_program_id"]),
                            pool_program=str(prior_map["pool_program_id"]),
                            base_mint=str(prior_map["base_mint"]),
                            quote_mint=str(prior_map["quote_mint"]),
                            venue=str(prior_map["venue"]),
                            state=POOL_RECONCILIATION_DUE,
                            reason="NEXT_LAWFUL_RECONCILIATION_BOUNDARY_REACHED",
                            observed_at=now,
                            next_lawful_action_at=None,
                            source_provenance={"source": "exact_market_state"},
                            contract_version=str(prior_map["contract_version"]),
                        ),
                        now=now,
                    )
                )
                reconciliation_mints.add(mint)
        due.append(row)

    report: dict[str, Any] = {
        "batch_sizes": [],
        "source_request_ids": [],
        "source_response_ids": [],
        "source_failure_ids": [],
        "source_request_coverage": [],
        "calls_by_stage": {"market_batching": 0, "reconciliation": 0},
        "provider_failures": 0,
        "accounting_blocker": False,
        "accounting_blocker_reason": None,
        "local_zero_source_exclusions": [],
        "suppressed_exact_pool_count": len(suppressed),
        "reconciliation_due_count": 0,
        "reconciliation_outcomes": [],
        "state_transition_ids": preflight_transition_ids,
        "candidates": [],
        "market_ready_count": 0,
        "exact_pools_by_mint": {},
    }
    due_boundary = (_parse_iso(now) + timedelta(seconds=EXACT_POOL_RECONCILIATION_SECONDS)).isoformat()

    for batch_index in range(0, len(due), 30):
        batch = due[batch_index : batch_index + 30]
        mints = tuple(sorted({str(row["mint_identity"]) for row in batch}))
        if not mints:
            continue
        batch_transport = transport
        if transport_factory is not None:
            batch_transport = transport_factory(mints)
        if batch_transport is None:
            from printer_v1.sources.dexscreener import (
                build_dexscreener_mint_batch_transport,
            )

            batch_transport = build_dexscreener_mint_batch_transport(mints)
        adapter = build_dexscreener_adapter(
            enabled=True, fixture_transport=batch_transport
        )
        request = build_governed_source_request(
            DEXSCREENER_SOURCE_NAME,
            "candidate_market_batch",
            request_key=f"{request_key}-{batch_index // 30 + 1}" if len(due) > 30 else request_key,
            tracking_priority=0,
            payload={
                "request_kind": "candidate_market_batch",
                "chain": "solana",
                "token_mints": list(mints),
            },
        )
        execution = execute_source_request_with_governor(
            connection,
            request,
            adapter,
            recent_request_count=recent_request_count + len(report["batch_sizes"]),
        )
        result = execution.normalized_result
        report["calls_by_stage"]["market_batching"] += 1
        report["batch_sizes"].append(len(mints))
        batch_request_id = int(execution.request_record.id)
        report["source_request_ids"].append(batch_request_id)
        if execution.response_record is not None:
            report["source_response_ids"].append(int(execution.response_record.id))
        if execution.failure_record is not None:
            report["source_failure_ids"].append(int(execution.failure_record.id))

        payload = result.normalized_payload or {}
        transport_identity_count = 0
        transport_identity_keys: list[list[object]] = []
        measurement_failed = False
        if isinstance(payload, Mapping):
            try:
                before = measured_ledger.source_transport_operations
                before_len = len(list(getattr(measured_ledger, "transports", ()) or ()))
                record_payload_transports(
                    measured_ledger,
                    payload,
                    default_stage="MINT_MARKET_BATCH",
                )
                transport_identity_count = int(
                    measured_ledger.source_transport_operations - before
                )
                transport_identity_keys = _transport_identity_keys_from_ledger_delta(
                    measured_ledger, before_count=before_len
                )
            except Exception as exc:
                # Declared transport identities only; never invent transports.
                # Zero is lawful only when measurement succeeds with zero
                # declared identities; measurement failure is recorded as
                # BLOCKED coverage with transport 0 (not a fabricated COMPLETED).
                measurement_failed = True
                transport_identity_count = 0
                transport_identity_keys = []
                report["accounting_blocker"] = True
                report["accounting_blocker_reason"] = (
                    f"TRANSPORT_IDENTITY_MEASUREMENT_FAILED:{exc}"
                )
        pairs = list(payload.get("pairs") or ()) if isinstance(payload, Mapping) else []
        failed = result.source_status != SourceStatus.COMPLETE or bool(result.failure_type)
        batch_seq = batch_index // 30 + 1
        report["source_request_coverage"].append(
            {
                "source_request_id": batch_request_id,
                "source_name": DEXSCREENER_SOURCE_NAME,
                "request_kind": "candidate_market_batch",
                "logical_stage_id": (
                    f"{campaign_id}|{run_id}|{cycle_id}|MINT_MARKET_BATCH|{batch_seq}"
                    if campaign_id and run_id and cycle_id
                    else f"MINT_MARKET_BATCH|{batch_seq}"
                ),
                "transport_identity_count": transport_identity_count,
                "transport_identity_keys": transport_identity_keys,
                "normalized_member_count": len(pairs),
                "terminal_status": (
                    "BLOCKED" if failed or measurement_failed else "COMPLETED"
                ),
            }
        )
        resolution = resolve_dexscreener_mint_batch(mints, pairs, observed_at=now)
        for mint, pool_rows in resolution.by_mint.items():
            report["exact_pools_by_mint"][mint] = [row.pool for row in pool_rows]
        report["local_zero_source_exclusions"].extend(resolution.local_exclusions)
        if failed:
            report["provider_failures"] += 1

        # Only unresolved/changed identities enter the stricter one-mint
        # GeckoTerminal fallback. Six is the immutable reconciliation reserve;
        # there is no retry and no attempt for already exact-resolved mints.
        inventory_by_mint = {str(item["mint_identity"]): item for item in batch}
        unresolved_for_fallback = []
        for mint in mints:
            historical_pool = str(inventory_by_mint[mint]["pumpswap_pool"])
            if failed or not any(
                item.pool == historical_pool
                for item in resolution.by_mint.get(mint, ())
            ):
                unresolved_for_fallback.append(mint)
        fallback: dict[str, dict[str, Any]] = {}
        if unresolved_for_fallback and enable_geckoterminal_fallback:
            from printer_v1.sources.geckoterminal import (
                GECKOTERMINAL_SOURCE_NAME,
                build_geckoterminal_adapter,
                build_geckoterminal_token_pools_transport,
            )

            for fallback_index, mint in enumerate(unresolved_for_fallback[:6], 1):
                if before_geckoterminal_request is not None:
                    before_geckoterminal_request()
                gt_transport = (
                    geckoterminal_transport_factory(mint)
                    if geckoterminal_transport_factory is not None
                    else build_geckoterminal_token_pools_transport(mint)
                )
                gt_request = build_governed_source_request(
                    GECKOTERMINAL_SOURCE_NAME,
                    "candidate_market_batch",
                    request_key=f"{request_key}-gt-{fallback_index}-{mint}",
                    tracking_priority=0,
                    payload={
                        "request_kind": "candidate_market_batch",
                        "chain": "solana",
                        "token_mint": mint,
                    },
                )
                gt_adapter = build_geckoterminal_adapter(
                    enabled=True, fixture_transport=gt_transport
                )
                gt_execution = execute_source_request_with_governor(
                    connection,
                    gt_request,
                    gt_adapter,
                    recent_request_count=fallback_index - 1,
                )
                gt_result = gt_execution.normalized_result
                report["calls_by_stage"]["reconciliation"] += 1
                gt_request_id = int(gt_execution.request_record.id)
                report["source_request_ids"].append(gt_request_id)
                if gt_execution.response_record is not None:
                    report["source_response_ids"].append(int(gt_execution.response_record.id))
                if gt_execution.failure_record is not None:
                    report["source_failure_ids"].append(int(gt_execution.failure_record.id))
                gt_payload = gt_result.normalized_payload or {}
                gt_transport_count = 0
                gt_transport_keys: list[list[object]] = []
                gt_measurement_failed = False
                if isinstance(gt_payload, Mapping):
                    try:
                        before_gt = measured_ledger.source_transport_operations
                        before_gt_len = len(
                            list(getattr(measured_ledger, "transports", ()) or ())
                        )
                        record_payload_transports(
                            measured_ledger,
                            gt_payload,
                            default_stage="MINT_MARKET_BATCH",
                        )
                        gt_transport_count = int(
                            measured_ledger.source_transport_operations - before_gt
                        )
                        gt_transport_keys = _transport_identity_keys_from_ledger_delta(
                            measured_ledger, before_count=before_gt_len
                        )
                    except Exception as gt_exc:
                        gt_measurement_failed = True
                        gt_transport_count = 0
                        report["accounting_blocker"] = True
                        report["accounting_blocker_reason"] = (
                            f"TRANSPORT_IDENTITY_MEASUREMENT_FAILED:{gt_exc}"
                        )
                gt_failed = (
                    gt_result.source_status != SourceStatus.COMPLETE
                    or bool(gt_result.failure_type)
                )
                if gt_failed:
                    report["provider_failures"] += 1
                gt_pairs = (
                    list(gt_payload.get("pairs") or ())
                    if isinstance(gt_payload, Mapping)
                    else []
                )
                report["source_request_coverage"].append(
                    {
                        "source_request_id": gt_request_id,
                        "source_name": GECKOTERMINAL_SOURCE_NAME,
                        "request_kind": "candidate_market_batch",
                        "logical_stage_id": (
                            f"{campaign_id}|{run_id}|{cycle_id}|"
                            f"GECKOTERMINAL_RECONCILIATION|{fallback_index}"
                            if campaign_id and run_id and cycle_id
                            else f"GECKOTERMINAL_RECONCILIATION|{fallback_index}"
                        ),
                        "transport_identity_count": gt_transport_count,
                        "transport_identity_keys": gt_transport_keys,
                        "normalized_member_count": len(gt_pairs),
                        "terminal_status": (
                            "BLOCKED"
                            if gt_failed or gt_measurement_failed
                            else "COMPLETED"
                        ),
                    }
                )
                gt_resolution = resolve_dexscreener_mint_batch(
                    [mint], gt_pairs, observed_at=now
                )
                fallback[mint] = {
                    "failed": gt_failed,
                    "failure_type": gt_result.failure_type,
                    "rows": gt_resolution.by_mint.get(mint, ()),
                    "request_id": gt_request_id,
                    "response_id": (
                        None
                        if gt_execution.response_record is None
                        else int(gt_execution.response_record.id)
                    ),
                    "failure_id": (
                        None
                        if gt_execution.failure_record is None
                        else int(gt_execution.failure_record.id)
                    ),
                }

        for row in batch:
            mint = str(row["mint_identity"])
            historical_pool = str(row["pumpswap_pool"])
            pool_program = str(row.get("pumpswap_program_id") or PUMPSWAP_AMM_PROGRAM_ID)
            gt_entry = fallback.get(mint)
            effective_failed = failed and (
                gt_entry is None or bool(gt_entry.get("failed"))
            )
            provenance = {
                "source": DEXSCREENER_SOURCE_NAME,
                "request_id": int(execution.request_record.id),
                "response_id": (
                    None if execution.response_record is None else int(execution.response_record.id)
                ),
                "failure_id": (
                    None if execution.failure_record is None else int(execution.failure_record.id)
                ),
            }
            common = dict(
                network=NETWORK,
                mint=mint,
                token_program=SPL_TOKEN_PROGRAM_ID,
                pool_program=pool_program,
                base_mint=mint,
                quote_mint="So11111111111111111111111111111111111111112",
                venue=PUMPSWAP_VENUE,
                observed_at=now,
                source_provenance=provenance,
                contract_version="DEXSCREENER_TOKENS_V1_2026_08_04",
            )
            upsert_state = lambda pool, state, reason, next_action=None: record_exact_market_transition(
                connection,
                ExactMarketObservation(
                    pool=pool,
                    state=state,
                    reason=reason,
                    next_lawful_action_at=next_action,
                    **common,
                ),
                now=now,
            )

            if effective_failed:
                report["state_transition_ids"].append(
                    upsert_state(
                        historical_pool,
                        SOURCE_UNAVAILABLE,
                        str(result.failure_type or "DEXSCREENER_SOURCE_UNAVAILABLE"),
                    )
                )
                evidence = classify_liquidity(
                    None,
                    mint=mint,
                    pool=historical_pool,
                    reason="LIQUIDITY_SOURCE_UNAVAILABLE",
                    source_status=getattr(result.source_status, "name", str(result.source_status)),
                    source_request_id=int(execution.request_record.id),
                    source_response_id=(None if execution.response_record is None else int(execution.response_record.id)),
                    source_failure_id=(None if execution.failure_record is None else int(execution.failure_record.id)),
                    failure_type=result.failure_type,
                )
                rejection = LIQUIDITY_UNPROVEN
            else:
                primary_rows = tuple(resolution.by_mint.get(mint, ()))
                fallback_rows = (
                    () if gt_entry is None or gt_entry.get("failed") else tuple(gt_entry["rows"])
                )
                mint_rows = primary_rows + tuple(
                    item for item in fallback_rows if item.pool not in {row.pool for row in primary_rows}
                )
                exact_rows = [item for item in mint_rows if item.pool == historical_pool]
                for observed in mint_rows:
                    if observed.pool == historical_pool:
                        continue
                    outcome = reconcile_pool_identity(
                        mint=mint,
                        historical_pool=historical_pool,
                        observed_pool=observed.pool,
                        exact_identity=(observed.base_mint == mint),
                        supported_contract=observed.venue.casefold() in SUPPORTED_PUMPSWAP_PROVIDER_VENUES,
                        protocol_confirmed=False,
                    )
                    report["reconciliation_outcomes"].append(outcome.__dict__)
                    changed_common = dict(common)
                    changed_common["quote_mint"] = observed.quote_mint
                    changed_common["venue"] = observed.venue or PUMPSWAP_VENUE
                    report["state_transition_ids"].append(
                        record_exact_market_transition(
                            connection,
                            ExactMarketObservation(
                                pool=observed.pool,
                                state=outcome.state,
                                reason=outcome.reason,
                                next_lawful_action_at=due_boundary,
                                **changed_common,
                            ),
                            now=now,
                        )
                    )
                if not exact_rows:
                    report["state_transition_ids"].append(
                        upsert_state(
                            historical_pool,
                            EXACT_POOL_NO_MATCH,
                            "LAWFUL_BATCH_EXACT_POOL_NO_MATCH",
                            due_boundary,
                        )
                    )
                    report["reconciliation_due_count"] += 1
                    evidence = classify_liquidity(
                        None,
                        mint=mint,
                        pool=historical_pool,
                        reason="LIQUIDITY_NO_EXACT_PAIR",
                        source_status="COMPLETE",
                        source_request_id=int(execution.request_record.id),
                        source_response_id=(None if execution.response_record is None else int(execution.response_record.id)),
                    )
                    rejection = LIQUIDITY_UNPROVEN
                else:
                    if all(item.pool != historical_pool for item in primary_rows) and gt_entry is not None:
                        provenance = {
                            "source": "geckoterminal",
                            "request_id": gt_entry["request_id"],
                            "response_id": gt_entry["response_id"],
                            "failure_id": gt_entry["failure_id"],
                        }
                    provenance["observed_quote_mints"] = sorted(
                        {item.quote_mint for item in exact_rows}
                    )
                    provenance["observed_venues"] = sorted(
                        {item.venue for item in exact_rows}
                    )
                    common["source_provenance"] = provenance
                    exact_contract_state = None
                    exact_contract_reason = None
                    if any(
                        item.venue.casefold() not in SUPPORTED_PUMPSWAP_PROVIDER_VENUES
                        for item in exact_rows
                    ):
                        exact_contract_state = UNSUPPORTED_VENUE
                        exact_contract_reason = "EXACT_POOL_PROVIDER_VENUE_UNSUPPORTED"
                    elif any(
                        item.quote_mint
                        != "So11111111111111111111111111111111111111112"
                        for item in exact_rows
                    ):
                        exact_contract_state = CONTRACT_BLOCKED
                        exact_contract_reason = "EXACT_POOL_QUOTE_CONTRACT_UNSUPPORTED"
                    if exact_contract_state is not None:
                        evidence = classify_liquidity(
                            None,
                            mint=mint,
                            pool=historical_pool,
                            reason=str(exact_contract_reason),
                            source_status="COMPLETE",
                            source_request_id=int(execution.request_record.id),
                            source_response_id=(None if execution.response_record is None else int(execution.response_record.id)),
                        )
                        report["state_transition_ids"].append(
                            upsert_state(
                                historical_pool,
                                exact_contract_state,
                                str(exact_contract_reason),
                            )
                        )
                        rejection = LIQUIDITY_UNPROVEN
                    else:
                        if mint in reconciliation_mints:
                            report["state_transition_ids"].append(
                                upsert_state(
                                    historical_pool,
                                    SAME_POOL_REOBSERVED,
                                    "SAME_EXACT_POOL_VISIBLE_AGAIN",
                                )
                            )
                        normalized = [
                            {
                                "chain": "solana",
                                "pair_address": item.pool,
                                "token_mint": item.mint,
                                "liquidity_usd": item.liquidity_usd,
                            }
                            for item in exact_rows
                        ]
                        value, reason = _extract_exact_pair_liquidity(
                            normalized,
                            mint=mint,
                            pool=historical_pool,
                        )
                        evidence = classify_liquidity(
                            value,
                            mint=mint,
                            pool=historical_pool,
                            reason=reason,
                            source_status="COMPLETE",
                            source_request_id=int(execution.request_record.id),
                            source_response_id=(None if execution.response_record is None else int(execution.response_record.id)),
                        )
                        state = (
                            CURRENT_POOL_CONFIRMED
                            if evidence.status == LIQUIDITY_PROVEN
                            else BELOW_LIQUIDITY_FLOOR
                            if evidence.status == LIQUIDITY_BELOW_SELECTION_FLOOR
                            else CONTRACT_BLOCKED
                        )
                        report["state_transition_ids"].append(
                            upsert_state(historical_pool, state, evidence.reason)
                        )
                        record_market_floor_state(
                            connection,
                            mint=mint,
                            pool=historical_pool,
                            liquidity=evidence,
                            now=now,
                        )
                        cooldown_ok, cooldown_reason = _cooldown_ok(
                            connection, mint, historical_pool, 1
                        )
                        rejection = None if evidence.status == LIQUIDITY_PROVEN and cooldown_ok else (
                            cooldown_reason if evidence.status == LIQUIDITY_PROVEN else evidence.status
                        )

            candidate = {
                "mint": mint,
                "pool": historical_pool,
                "pumpswap_pool": historical_pool,
                "market_identity": str(row.get("market_identity") or f"solana-mainnet:{PUMPSWAP_VENUE}:{historical_pool}"),
                "provenance": str(row.get("latest_channel") or "PERSISTED_GRADUATED"),
                "lifecycle_state": str(row.get("lifecycle_state") or GRADUATED_LIFECYCLE),
                "graduation_block_time": row.get("graduation_block_time"),
                "liquidity": evidence.to_dict(),
                "evidence_expires_at": due_boundary,
                "eligible": rejection is None,
                "rejection": rejection,
            }
            report["candidates"].append(candidate)
            upsert_reserve_layer(
                connection,
                network=NETWORK,
                mint=mint,
                pool=historical_pool,
                layer=BROAD_NOMINATED,
                reserve_state="ACTIVE",
                reason="CANONICAL_GRADUATED_INVENTORY",
                observed_at=now,
                next_lawful_action_at=(due_boundary if rejection is not None else None),
                evidence_expires_at=None,
                source_provenance=provenance,
                evidence={"lifecycle_state": candidate["lifecycle_state"]},
                campaign_id=campaign_id,
            )
            if candidate["eligible"]:
                upsert_reserve_layer(
                    connection,
                    network=NETWORK,
                    mint=mint,
                    pool=historical_pool,
                    layer=MARKET_READY,
                    reserve_state="ACTIVE",
                    reason="EXACT_POOL_CURRENT_AND_LIQUIDITY_FLOOR_PASS",
                    observed_at=now,
                    next_lawful_action_at=None,
                    evidence_expires_at=due_boundary,
                    source_provenance=provenance,
                    evidence={"liquidity": evidence.to_dict()},
                    campaign_id=campaign_id,
                )
                report["market_ready_count"] += 1
        connection.commit()

    ordered_mints = sorted(
        {
            str(row.get("mint_identity") or row.get("mint") or "").strip()
            for row in inventory_rows
            if str(row.get("mint_identity") or row.get("mint") or "").strip()
        }
    )
    resolved_sequence = stage_sequence
    if resolved_sequence is None:
        resolved_sequence = parse_mint_market_batch_stage_sequence(request_key)
    if resolved_sequence is None:
        resolved_sequence = 1
    if int(resolved_sequence) < 1:
        raise ValueError("INVALID_MINT_MARKET_BATCH_STAGE_SEQUENCE")
    report["stage_sequence"] = int(resolved_sequence)
    report["request_key"] = str(request_key)
    if campaign_id and run_id and cycle_id:
        logical = build_mint_market_batch_logical_identity(
            campaign_id=str(campaign_id),
            run_id=str(run_id),
            cycle_id=str(cycle_id),
            stage_sequence=int(resolved_sequence),
            ordered_mints=ordered_mints,
        )
        report["logical_batch_identity"] = logical
    else:
        report["logical_batch_identity"] = {
            "stage_sequence": int(resolved_sequence),
            "mint_set_digest": mint_set_digest(ordered_mints),
            "ordered_mint_count": len(ordered_mints),
        }

    if stage_evidence_sink is not None and report["source_request_ids"]:
        from printer_v1.sources.campaign_six_unit_accounting import (
            build_campaign_stage_id,
            seal_campaign_stage_evidence,
        )

        if not all(str(value or "").strip() for value in (campaign_id, run_id, cycle_id)):
            raise ValueError("MINT_MARKET_BATCH_STAGE_REQUIRES_CAMPAIGN_RUN_CYCLE")
        sealed = seal_campaign_stage_evidence(
            ledger=measured_ledger,
            stage_id=build_campaign_stage_id(
                campaign_id=str(campaign_id),
                run_id=str(run_id),
                cycle_id=str(cycle_id),
                stage_kind="MINT_MARKET_BATCH",
                stage_sequence=int(resolved_sequence),
            ),
            stage_kind="MINT_MARKET_BATCH",
            stage_sequence=int(resolved_sequence),
            stage_terminal_status=(
                "BLOCKED" if report["provider_failures"] else "COMPLETED"
            ),
            stage_first_terminal_cause=(
                "DEXSCREENER_SOURCE_UNAVAILABLE"
                if report["provider_failures"]
                else None
            ),
            campaign_id=str(campaign_id),
            run_id=str(run_id),
            cycle_id=str(cycle_id),
            sealed_at=now,
        )
        # Attach durable logical identity to sealed evidence for reconciliation.
        sealed = dict(sealed)
        sealed["logical_batch_identity"] = dict(report["logical_batch_identity"])
        sealed["request_key"] = str(request_key)
        sealed["source_request_ids"] = list(report["source_request_ids"])
        stage_evidence_sink(sealed)
        report["sealed_stage_evidence"] = sealed
    report["source_request_count"] = len(report["source_request_ids"])
    return report


def record_fresh_pool_nominations(
    connection: sqlite3.Connection,
    *,
    observations: Sequence[Mapping[str, Any]],
    source: str,
    request_id: int,
    now: str,
    campaign_id: str | None,
    response_id: int | None = None,
) -> dict[str, Any]:
    """Merge fresh aggregator pools, preserve exact-pool liquidity, prefilter floor.

    Fresh DexScreener/GeckoTerminal nominations retain exact mint, pool, base and
    quote mints, provider venue, liquidity_usd, observation time, evidence expiry,
    request/response provenance, and provider contract version. The $3,000 floor
    is applied to the exact nominated pool before protocol confirmation whenever
    liquidity is already present. No graduation-registry re-proof is required.
    """
    accepted: list[dict[str, Any]] = []
    exclusions: list[dict[str, str]] = []
    prefilter_counts = {
        "ABOVE_FLOOR_NOMINATION": 0,
        "BELOW_LIQUIDITY_FLOOR": 0,
        "LIQUIDITY_UNKNOWN": 0,
        "IDENTITY_CONFLICT": 0,
        "EXACT_POOL_NO_MATCH": 0,
    }
    contract_version = (
        "GECKOTERMINAL_KEYLESS_V2_2026_08_04"
        if source == "geckoterminal"
        else "DEXSCREENER_TOKENS_V1_2026_08_04"
    )
    for raw in observations:
        mint = str(raw.get("mint") or raw.get("base_mint") or "")
        pool = str(raw.get("pool") or raw.get("pair_address") or raw.get("pairAddress") or "")
        base = str(raw.get("base_mint") or mint)
        quote = str(raw.get("quote_mint") or "")
        venue = str(raw.get("venue") or raw.get("dex_id") or raw.get("dex") or "")
        canonical_venue = (
            "pumpswap"
            if venue.casefold() in SUPPORTED_PUMPSWAP_PROVIDER_VENUES
            else venue
        )
        if not mint or not pool or base != mint:
            exclusions.append(
                {"mint": mint, "pool": pool, "reason": "INCOMPLETE_ORIENTATION"}
            )
            prefilter_counts["IDENTITY_CONFLICT"] += 1
            continue
        if mint in SOLANA_INFRASTRUCTURE_MINTS:
            exclusions.append(
                {"mint": mint, "pool": pool, "reason": "INFRASTRUCTURE_MINT"}
            )
            continue
        liquidity_usd = _coerce_liquidity_usd(
            raw.get("liquidity_usd")
            if raw.get("liquidity_usd") is not None
            else raw.get("liquidity")
        )
        observed_at = str(raw.get("observed_at") or raw.get("liquidity_observed_at") or now)
        explicit_expiry = raw.get("liquidity_evidence_expires_at") or raw.get(
            "evidence_expires_at"
        )
        item_expires = resolve_liquidity_evidence_expiry(
            observed_at=observed_at,
            explicit_expiry=(
                None if explicit_expiry is None else str(explicit_expiry)
            ),
            ingestion_now=now,
        )
        if item_expires is None:
            exclusions.append(
                {
                    "mint": mint,
                    "pool": pool,
                    "reason": "EVIDENCE_FRESHNESS_CONTRADICTION",
                }
            )
            prefilter_counts["IDENTITY_CONFLICT"] += 1
            continue
        # Unsupported venues are candidate-local and never enter protocol.
        if venue and not _protocol_supported_venue(venue):
            state, reason = UNSUPPORTED_VENUE, "PROTOCOL_UNSUPPORTED_VENUE"
            prefilter_label = "UNSUPPORTED_VENUE"
        else:
            state, reason = classify_exact_pool_liquidity_prefilter(
                liquidity_usd=liquidity_usd
            )
            if reason == REASON_ABOVE_FLOOR_NOMINATION:
                prefilter_counts["ABOVE_FLOOR_NOMINATION"] += 1
                prefilter_label = "ABOVE_FLOOR_NOMINATION"
            elif reason == REASON_BELOW_FLOOR:
                prefilter_counts["BELOW_LIQUIDITY_FLOOR"] += 1
                prefilter_label = "BELOW_LIQUIDITY_FLOOR"
            else:
                prefilter_counts["LIQUIDITY_UNKNOWN"] += 1
                prefilter_label = "LIQUIDITY_UNKNOWN"
        provenance = {
            "source": source,
            "request_id": int(request_id),
            "response_id": None if response_id is None else int(response_id),
            "provider_venue": venue or canonical_venue,
            "liquidity_usd": liquidity_usd,
            "liquidity_observed_at": observed_at,
            "liquidity_evidence_expires_at": item_expires,
            "market_evidence_contract_version": contract_version,
            "prefilter_outcome": prefilter_label,
            # Market-source provenance only — never claimed as migration proof.
            "provenance_kind": "MARKET_SOURCE_OBSERVATION",
            "liquidity_backup_attempted": bool(
                raw.get("liquidity_backup_attempted")
            ),
        }
        evidence = {
            "base_mint": base,
            "quote_mint": quote,
            "venue": venue,
            "provider_venue": venue or canonical_venue,
            "liquidity_usd": liquidity_usd,
            "liquidity_observed_at": observed_at,
            "liquidity_evidence_expires_at": item_expires,
            "market_evidence_contract_version": contract_version,
            "prefilter_outcome": prefilter_label,
            "source": source,
            "request_id": int(request_id),
            "response_id": None if response_id is None else int(response_id),
            "liquidity_backup_attempted": bool(
                raw.get("liquidity_backup_attempted")
            ),
        }
        record_exact_market_transition(
            connection,
            ExactMarketObservation(
                network=NETWORK,
                mint=mint,
                pool=pool,
                token_program="UNRESOLVED_TOKEN_PROGRAM",
                pool_program="UNRESOLVED_POOL_PROGRAM",
                base_mint=base,
                quote_mint=quote or "UNKNOWN_QUOTE_MINT",
                venue=canonical_venue or "UNKNOWN_VENUE",
                state=state,
                reason=reason,
                observed_at=observed_at,
                next_lawful_action_at=(
                    now if reason == REASON_ABOVE_FLOOR_NOMINATION else now
                ),
                source_provenance=provenance,
                contract_version=contract_version,
            ),
            now=now,
        )
        upsert_reserve_layer(
            connection,
            network=NETWORK,
            mint=mint,
            pool=pool,
            layer=BROAD_NOMINATED,
            reserve_state="ACTIVE",
            reason=reason,
            observed_at=observed_at,
            next_lawful_action_at=now,
            evidence_expires_at=item_expires if liquidity_usd is not None else None,
            source_provenance=provenance,
            evidence=evidence,
            campaign_id=campaign_id,
        )
        if reason == REASON_ABOVE_FLOOR_NOMINATION:
            upsert_reserve_layer(
                connection,
                network=NETWORK,
                mint=mint,
                pool=pool,
                layer=ABOVE_FLOOR_NOMINATED,
                reserve_state="ACTIVE",
                reason=reason,
                observed_at=observed_at,
                next_lawful_action_at=now,
                evidence_expires_at=item_expires,
                source_provenance=provenance,
                evidence=evidence,
                campaign_id=campaign_id,
            )
        accepted.append(
            {
                "mint": mint,
                "pool": pool,
                "source": source,
                "liquidity_usd": liquidity_usd,
                "prefilter_outcome": prefilter_label,
                "liquidity_evidence_expires_at": item_expires,
                "protocol_confirmation_due": reason == REASON_ABOVE_FLOOR_NOMINATION,
            }
        )
    connection.commit()
    return {
        "accepted": accepted,
        "exclusions": exclusions,
        "prefilter_counts": prefilter_counts,
    }


def run_geckoterminal_fresh_nomination(
    connection: sqlite3.Connection,
    *,
    request_key: str,
    now: str,
    campaign_id: str | None,
    run_id: str | None,
    cycle_id: str | None,
    transport: Any | None = None,
    stage_evidence_sink: Any | None = None,
    transport_identity_observer: Any | None = None,
) -> dict[str, Any]:
    """Run one governed current GeckoTerminal new-pool nomination request."""
    from printer_v1.contracts.enums import SourceStatus
    from printer_v1.sources.campaign_six_unit_accounting import (
        build_campaign_stage_id,
        seal_campaign_stage_evidence,
    )
    from printer_v1.sources.contracts import build_governed_source_request
    from printer_v1.sources.geckoterminal import (
        GECKOTERMINAL_SOURCE_NAME,
        build_geckoterminal_adapter,
        build_geckoterminal_pools_transport,
    )
    from printer_v1.sources.governed_execution import execute_source_request_with_governor
    from printer_v1.sources.measured_transport import (
        MeasuredTransportError,
        MeasuredTransportLedger,
        record_payload_transports,
    )

    actual_transport = transport or build_geckoterminal_pools_transport()
    adapter = build_geckoterminal_adapter(
        enabled=True, fixture_transport=actual_transport
    )
    request = build_governed_source_request(
        GECKOTERMINAL_SOURCE_NAME,
        "geckoterminal_new_pool_discovery",
        request_key=request_key,
        tracking_priority=0,
        payload={
            "request_kind": "geckoterminal_new_pool_discovery",
            "chain": "solana",
        },
    )
    ledger = MeasuredTransportLedger(
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        on_transport_recorded=transport_identity_observer,
    )
    execution = execute_source_request_with_governor(connection, request, adapter)
    result = execution.normalized_result
    payload = result.normalized_payload or {}
    request_id = int(execution.request_record.id)
    accounting_blocker = False
    accounting_blocker_reason: str | None = None
    transport_identity_count = 0
    if isinstance(payload, Mapping):
        try:
            before = ledger.source_transport_operations
            record_payload_transports(
                ledger, payload, default_stage="FRESH_POOL_NOMINATION"
            )
            transport_identity_count = int(
                ledger.source_transport_operations - before
            )
        except MeasuredTransportError as exc:
            accounting_blocker = True
            accounting_blocker_reason = (
                f"TRANSPORT_IDENTITY_MEASUREMENT_FAILED:{exc}"
            )
            transport_identity_count = 0
    observations = []
    for item in payload.get("pairs", ()) if isinstance(payload, Mapping) else ():
        if not isinstance(item, Mapping):
            continue
        base = item.get("baseToken") if isinstance(item.get("baseToken"), Mapping) else {}
        quote = item.get("quoteToken") if isinstance(item.get("quoteToken"), Mapping) else {}
        liquidity_raw = item.get("liquidity")
        liquidity_usd = _coerce_liquidity_usd(
            item.get("liquidity_usd")
            if item.get("liquidity_usd") is not None
            else liquidity_raw
        )
        observations.append(
            {
                "mint": item.get("base_mint") or base.get("address"),
                "pool": item.get("pairAddress") or item.get("pair_address"),
                "base_mint": item.get("base_mint") or base.get("address"),
                "quote_mint": item.get("quote_mint") or quote.get("address"),
                "venue": item.get("dex_id") or item.get("dex"),
                "liquidity_usd": liquidity_usd,
                "observed_at": item.get("captured_at") or now,
            }
        )
    merge = record_fresh_pool_nominations(
        connection,
        observations=observations,
        source=GECKOTERMINAL_SOURCE_NAME,
        request_id=request_id,
        now=now,
        campaign_id=campaign_id,
        response_id=(
            None
            if execution.response_record is None
            else int(execution.response_record.id)
        ),
    ) if (
        result.source_status == SourceStatus.COMPLETE
        and not result.failure_type
        and not accounting_blocker
    ) else {
        "accepted": [], "exclusions": [], "prefilter_counts": {}
    }
    sealed = None
    stage_terminal = (
        "COMPLETED"
        if (
            result.source_status == SourceStatus.COMPLETE
            and not result.failure_type
            and not accounting_blocker
        )
        else "BLOCKED"
    )
    stage_first_cause = (
        accounting_blocker_reason
        if accounting_blocker
        else result.failure_type
    )
    gecko_transport_keys: list[list[object]] = []
    gecko_payload = (
        execution.normalized_result.normalized_payload
        if getattr(execution, "normalized_result", None) is not None
        else None
    )
    if transport_identity_count and isinstance(gecko_payload, Mapping):
        from printer_v1.discovery.memory_observation_activation import (
            transport_identity_keys_from_payload,
        )

        gecko_transport_keys = [
            list(key) for key in transport_identity_keys_from_payload(gecko_payload)
        ]
    coverage_entry = {
        "source_request_id": request_id,
        "source_name": GECKOTERMINAL_SOURCE_NAME,
        "request_kind": "geckoterminal_new_pool_discovery",
        "logical_stage_id": (
            f"{campaign_id}|{run_id}|{cycle_id}|FRESH_POOL_NOMINATION|1"
            if campaign_id and run_id and cycle_id
            else f"FRESH_POOL_NOMINATION|1|{request_key}"
        ),
        "transport_identity_count": transport_identity_count,
        "transport_identity_keys": gecko_transport_keys,
        "normalized_member_count": len(observations),
        "terminal_status": stage_terminal,
    }
    if stage_evidence_sink is not None:
        if not all(str(value or "").strip() for value in (campaign_id, run_id, cycle_id)):
            raise ValueError("FRESH_POOL_NOMINATION_STAGE_REQUIRES_CAMPAIGN_RUN_CYCLE")
        if accounting_blocker:
            # Do not claim successful stage accounting after measurement failure.
            sealed = None
        else:
            sealed = seal_campaign_stage_evidence(
                ledger=ledger,
                stage_id=build_campaign_stage_id(
                    campaign_id=str(campaign_id), run_id=str(run_id), cycle_id=str(cycle_id),
                    stage_kind="FRESH_POOL_NOMINATION", stage_sequence=1,
                ),
                stage_kind="FRESH_POOL_NOMINATION",
                stage_sequence=1,
                stage_terminal_status=stage_terminal,
                stage_first_terminal_cause=stage_first_cause,
                campaign_id=str(campaign_id), run_id=str(run_id), cycle_id=str(cycle_id),
                sealed_at=now,
            )
            sealed = dict(sealed)
            sealed["source_request_coverage"] = [coverage_entry]
            stage_evidence_sink(sealed)
    return {
        "status": getattr(result.source_status, "name", str(result.source_status)),
        "failure_type": result.failure_type,
        "request_id": request_id,
        "response_id": None if execution.response_record is None else int(execution.response_record.id),
        "failure_id": None if execution.failure_record is None else int(execution.failure_record.id),
        "source_requests": 1,
        "source_request_ids": [request_id],
        "source_request_coverage": [coverage_entry],
        "transport_operations": transport_identity_count,
        "nominations": merge["accepted"],
        "local_exclusions": merge["exclusions"],
        "sealed_stage_evidence": sealed,
        "accounting_blocker": accounting_blocker,
        "accounting_blocker_reason": accounting_blocker_reason,
    }


@dataclass(frozen=True)
class FrozenEligibleReserve:
    selected: tuple[Mapping[str, Any], ...]
    alternates: tuple[Mapping[str, Any], ...]
    rejected_stale: tuple[Mapping[str, Any], ...]
    frozen_at: str
    selection_authority: Mapping[str, Any]


def freeze_eligible_reserve(
    candidates: Sequence[Mapping[str, Any]],
    *,
    cycle_seed: str,
    at: str,
) -> FrozenEligibleReserve:
    """Freeze MEMORY_OBSERVATION_ELIGIBLE rows; select two neutrally, retain spares.

    Admission is observation eligibility only. Holder concentration, manipulation
    context, liquidity magnitude, source order, and provider popularity never
    influence ordering or selection. FULLY_ELIGIBLE is not the memory input.

    Post-filter valid depth in selection_authority is the sole freeze-depth
    authority for campaign admission (never raw input count).
    """
    from printer_v1.discovery.selection_authority import (
        candidate_from_front_door_mapping,
        deterministic_candidate_order,
        select_two_candidates,
    )

    instant = _parse_iso(at)
    fresh: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    seen_mints: set[str] = set()
    seen_pools: set[str] = set()
    input_count = 0
    malformed_count = 0
    not_observation_eligible_count = 0
    duplicate_mint_count = 0
    duplicate_pool_count = 0
    tracking_ineligible_count = 0
    tracking_requalification_required_count = 0
    for raw in candidates:
        input_count += 1
        item = dict(raw)
        mint = str(item.get("mint") or item.get("mint_identity") or "")
        pool = str(item.get("pool") or item.get("pair_address") or "")
        expiry = item.get("evidence_expires_at")
        # Admission gate: MEMORY_OBSERVATION_ELIGIBLE only. fully_eligible is
        # never a compatibility admission fallback for the memory path.
        if item.get("memory_observation_eligible") is not True:
            not_observation_eligible_count += 1
            continue
        # Current exact tracking feasibility is a pre-freeze input.  Older
        # callers that do not yet project this field retain their legacy path;
        # the MEMORY_OBSERVATION owner always supplies it explicitly.
        if "tracking_handoff_eligible" in item and not bool(
            item.get("tracking_handoff_eligible")
        ):
            tracking_ineligible_count += 1
            continue
        if bool(item.get("tracking_requalification_required")):
            tracking_requalification_required_count += 1
            continue
        if not mint or not pool:
            malformed_count += 1
            continue
        if expiry is None or _parse_iso(str(expiry)) <= instant:
            stale.append(item)
            continue
        if mint in seen_mints:
            duplicate_mint_count += 1
            continue
        if pool in seen_pools:
            duplicate_pool_count += 1
            continue
        seen_mints.add(mint)
        seen_pools.add(pool)
        item.setdefault("market_identity", f"solana-mainnet:eligible:{pool}")
        item.setdefault("provenance", "PERSISTED_GRADUATED")
        # Explicit separation: memory observation vs future action eligibility.
        item["memory_observation_eligible"] = True
        item.setdefault(
            "future_action_eligibility",
            item.get("future_action_eligibility") or "BLOCKED_OR_UNKNOWN",
        )
        fresh.append(item)

    valid_depth = len(fresh)
    depth_status = observation_reserve_depth_status(valid_depth)
    filter_authority = {
        "input_count": input_count,
        "valid_fresh_unique_observation_depth": valid_depth,
        "observation_eligible_count": valid_depth,
        "stale_count": len(stale),
        "duplicate_mint_count": duplicate_mint_count,
        "duplicate_pool_count": duplicate_pool_count,
        "tracking_ineligible_count": tracking_ineligible_count,
        "tracking_requalification_required_count": (
            tracking_requalification_required_count
        ),
        "malformed_count": malformed_count,
        "not_observation_eligible_count": not_observation_eligible_count,
        "minimum_freeze_depth": MINIMUM_FREEZE_DEPTH,
        "observation_surplus_target": OBSERVATION_SURPLUS_TARGET,
        "freeze_depth_met": bool(depth_status["freeze_depth_met"]),
        "surplus_target_met": bool(depth_status["surplus_target_met"]),
        "coverage_blocker": bool(depth_status["coverage_blocker"]),
        "surplus_status": depth_status["surplus_status"],
    }

    # MINIMUM_FREEZE_DEPTH is an admission gate, not only a diagnostic.
    if valid_depth < MINIMUM_FREEZE_DEPTH:
        return FrozenEligibleReserve(
            selected=(),
            alternates=(),
            rejected_stale=tuple(
                sorted(stale, key=lambda item: str(item.get("mint") or ""))
            ),
            frozen_at=at,
            selection_authority={
                **filter_authority,
                "selected": [],
                "reason": "INSUFFICIENT_OBSERVATION_COVERAGE",
            },
        )

    selection_candidates = [candidate_from_front_door_mapping(item) for item in fresh]
    authority = select_two_candidates(selection_candidates, cycle_seed=cycle_seed)
    selected_mints = {item.mint for item in authority.selected}
    ordered = deterministic_candidate_order(selection_candidates, cycle_seed=cycle_seed)
    by_mint = {str(item["mint"]): item for item in fresh}
    selected = tuple(by_mint[item.mint] for item in authority.selected)
    # Exactly two alternates when depth permits; remainder stays standby inventory.
    alternate_items = [
        by_mint[item.mint] for item in ordered if item.mint not in selected_mints
    ]
    alternates = tuple(alternate_items[:2])
    selection_dict = dict(authority.as_dict())
    selection_dict.update(filter_authority)
    return FrozenEligibleReserve(
        selected=selected,
        alternates=alternates,
        rejected_stale=tuple(sorted(stale, key=lambda item: str(item.get("mint") or ""))),
        frozen_at=at,
        selection_authority=selection_dict,
    )


def load_retained_market_evidence(
    connection: sqlite3.Connection,
    *,
    mint: str,
    pool: str,
    at: str,
) -> dict[str, Any] | None:
    """Load unexpired exact-pool market evidence retained at nomination time."""
    row = connection.execute(
        """SELECT evidence_json, evidence_expires_at, source_provenance_json,
                  categorical_reason, observed_at
           FROM printer_discovery_reserve_layers
           WHERE network=? AND mint_identity=? AND pool_address=?
             AND reserve_layer IN (?, ?)
           ORDER BY CASE reserve_layer
             WHEN ? THEN 0
             WHEN ? THEN 1
             ELSE 2 END""",
        (
            NETWORK,
            mint,
            pool,
            ABOVE_FLOOR_NOMINATED,
            BROAD_NOMINATED,
            ABOVE_FLOOR_NOMINATED,
            BROAD_NOMINATED,
        ),
    ).fetchone()
    if row is None:
        return None
    try:
        evidence = json.loads(str(row["evidence_json"] or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        evidence = {}
    if not isinstance(evidence, dict):
        evidence = {}
    try:
        provenance = json.loads(str(row["source_provenance_json"] or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        provenance = {}
    if isinstance(provenance, Mapping):
        # Preserve the exact governed market owner alongside the factual payload;
        # retained activation must not rediscover or guess this lineage.
        for key in ("source", "source_name", "request_id", "response_id"):
            if evidence.get(key) is None and provenance.get(key) is not None:
                evidence[key] = provenance.get(key)
    expiry = row["evidence_expires_at"] or evidence.get("liquidity_evidence_expires_at")
    liquidity_usd = _coerce_liquidity_usd(evidence.get("liquidity_usd"))
    if liquidity_usd is None and isinstance(provenance, Mapping):
        # Fall back to accumulated observations envelope.
        observations = provenance.get("observations") if isinstance(provenance, Mapping) else None
        if isinstance(observations, list):
            for obs in observations:
                if not isinstance(obs, Mapping):
                    continue
                liquidity_usd = _coerce_liquidity_usd(obs.get("liquidity_usd"))
                if liquidity_usd is not None:
                    if expiry is None:
                        expiry = obs.get("liquidity_evidence_expires_at")
                    break
    if liquidity_usd is None:
        return None
    if expiry is None:
        return None
    if _parse_iso(str(expiry)) <= _parse_iso(at):
        return {
            "liquidity_usd": liquidity_usd,
            "evidence_expires_at": str(expiry),
            "fresh": False,
            "evidence": evidence,
            "observed_at": str(row["observed_at"] or ""),
        }
    return {
        "liquidity_usd": liquidity_usd,
        "evidence_expires_at": str(expiry),
        "fresh": True,
        "evidence": evidence,
        "observed_at": str(row["observed_at"] or ""),
        "passes_floor": float(liquidity_usd) >= SELECTION_FLOOR_USD,
    }


def promote_confirmed_with_retained_liquidity(
    connection: sqlite3.Connection,
    *,
    mint: str,
    pool: str,
    venue: str,
    now: str,
    campaign_id: str | None,
    protocol_request_id: int | None,
) -> dict[str, Any]:
    """Promote CURRENT_POOL_CONFIRMED via retained unexpired liquidity evidence.

    No second DexScreener market request. Expired/incomplete evidence requires
    revalidation rather than silent promotion.
    """
    retained = load_retained_market_evidence(
        connection, mint=mint, pool=pool, at=now
    )
    if retained is None or not retained.get("fresh") or not retained.get("passes_floor"):
        return {
            "mint": mint,
            "pool": pool,
            "promoted": False,
            "reason": (
                "RETAINED_LIQUIDITY_EXPIRED_OR_MISSING"
                if retained is None or not retained.get("fresh")
                else "RETAINED_LIQUIDITY_BELOW_FLOOR"
            ),
            "requires_market_revalidation": True,
            "memory_observation_eligible": False,
        }
    from printer_v1.sources.pumpswap import PUMPSWAP_AMM_PROGRAM_ID

    evidence = dict(retained.get("evidence") or {})
    evidence_expires_at = str(retained["evidence_expires_at"])
    liquidity_usd = float(retained["liquidity_usd"])
    retained_base = str(evidence.get("base_mint") or mint)
    retained_quote = str(evidence.get("quote_mint") or "")
    retained_venue = str(evidence.get("venue") or evidence.get("provider_venue") or venue or "")
    retained_pool = str(evidence.get("pool") or pool)
    contract_version = str(
        evidence.get("market_evidence_contract_version")
        or "RETAINED_MARKET_EVIDENCE_V1"
    )
    # Exact identity continuity: base must equal candidate mint; quote/pool
    # must be present and non-conflicting. Never hardcode WSOL or substitute.
    if retained_base != mint:
        return {
            "mint": mint,
            "pool": pool,
            "promoted": False,
            "reason": "RETAINED_BASE_MINT_CONFLICT",
            "requires_market_revalidation": True,
            "memory_observation_eligible": False,
        }
    if not retained_quote or retained_quote in {"", "UNKNOWN_QUOTE_MINT"}:
        return {
            "mint": mint,
            "pool": pool,
            "promoted": False,
            "reason": "RETAINED_QUOTE_MINT_MISSING",
            "requires_market_revalidation": True,
            "memory_observation_eligible": False,
        }
    if retained_pool and retained_pool != pool:
        return {
            "mint": mint,
            "pool": pool,
            "promoted": False,
            "reason": "RETAINED_POOL_IDENTITY_CONFLICT",
            "requires_market_revalidation": True,
            "memory_observation_eligible": False,
        }
    promotion_venue = retained_venue or venue or "pumpswap"
    provenance = {
        "stage": "protocol_confirmation_direct_promotion",
        "campaign_id": campaign_id,
        "protocol_request_id": protocol_request_id,
        "liquidity_usd": liquidity_usd,
        "liquidity_evidence_expires_at": evidence_expires_at,
        "promotion_path": "RETAINED_FRESH_EXACT_POOL_LIQUIDITY",
        "base_mint": retained_base,
        "quote_mint": retained_quote,
        "venue": promotion_venue,
        "pool": pool,
        "market_evidence_contract_version": contract_version,
        "source": evidence.get("source"),
        "request_id": evidence.get("request_id"),
        "response_id": evidence.get("response_id"),
    }
    # Liquidity floor already proven via retained exact-pool evidence.
    record_exact_market_transition(
        connection,
        ExactMarketObservation(
            network=NETWORK,
            mint=mint,
            pool=pool,
            token_program=SPL_TOKEN_PROGRAM_ID,
            pool_program=PUMPSWAP_AMM_PROGRAM_ID,
            base_mint=retained_base,
            quote_mint=retained_quote,
            venue=promotion_venue,
            state=CURRENT_VISIBLE,
            reason="AT_OR_ABOVE_3000_FLOOR_RETAINED",
            observed_at=now,
            next_lawful_action_at=None,
            source_provenance=provenance,
            contract_version=contract_version,
        ),
        now=now,
    )
    liquidity_evidence = {
        "status": "LIQUIDITY_PROVEN",
        "liquidity_usd": liquidity_usd,
        "mint": mint,
        "pool": pool,
        "base_mint": retained_base,
        "quote_mint": retained_quote,
        "reason": "AT_OR_ABOVE_3000_FLOOR",
        "source_status": "COMPLETE",
        "outcome_category": "LIQUIDITY_EXACT_ABOVE_FLOOR",
        "detailed_reason": "AT_OR_ABOVE_3000_FLOOR_RETAINED",
        "source_name": str(
            evidence.get("source_name") or evidence.get("source") or ""
        ),
        "source_request_id": evidence.get("request_id"),
        "source_response_id": evidence.get("response_id"),
        "liquidity_observed_at": str(
            evidence.get("observed_at") or retained.get("observed_at") or now
        ),
    }
    for layer, reason in (
        (MARKET_READY, "EXACT_POOL_CURRENT_AND_LIQUIDITY_FLOOR_PASS"),
        (
            MEMORY_OBSERVATION_ELIGIBLE,
            "IDENTITY_POOL_LIQUIDITY_MEMORY_OBSERVATION_PASS",
        ),
    ):
        upsert_reserve_layer(
            connection,
            network=NETWORK,
            mint=mint,
            pool=pool,
            layer=layer,
            reserve_state="ACTIVE",
            reason=reason,
            observed_at=now,
            next_lawful_action_at=None,
            evidence_expires_at=evidence_expires_at,
            source_provenance=provenance,
            evidence={
                "liquidity": liquidity_evidence,
                "base_mint": retained_base,
                "quote_mint": retained_quote,
                "venue": promotion_venue,
                "pool": pool,
                "market_evidence_contract_version": contract_version,
                "memory_observation_eligible": True,
                "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
                "holder_condition": "UNKNOWN",
                "holder_evidence_status": "NOT_YET_ENRICHED",
            },
            campaign_id=campaign_id,
        )
    return {
        "mint": mint,
        "pool": pool,
        "promoted": True,
        "reason": "PROMOTED_WITH_RETAINED_LIQUIDITY",
        "requires_market_revalidation": False,
        "memory_observation_eligible": True,
        "liquidity_usd": liquidity_usd,
        "evidence_expires_at": evidence_expires_at,
        "liquidity": liquidity_evidence,
        "base_mint": retained_base,
        "quote_mint": retained_quote,
        "venue": promotion_venue,
        "market_identity": f"solana-mainnet:pumpswap:{pool}",
        "eligible": True,
        "rejection": None,
        "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
        "admission_authority": "MARKET_PRESENT_POOL",
        "nomination_source": str(
            evidence.get("source_name") or evidence.get("source") or ""
        ),
        "lineage_state": "UNKNOWN_ORIGIN",
        "exact_present_pool_confirmed": True,
    }



def _protocol_supported_venue(venue: str) -> bool:
    venue_key = str(venue or "").casefold()
    return venue_key in SUPPORTED_PUMPSWAP_PROVIDER_VENUES or venue_key in {
        "pump-fun",
        "pumpswap",
        "pumpfun",
        "pump-amm",
    }


def _outcome_to_exact_state(outcome: str) -> tuple[str, str]:
    """Map protocol outcome codes into exact-market (state, reason)."""
    if outcome == "CURRENT_POOL_CONFIRMED":
        return CURRENT_POOL_CONFIRMED, "EXACT_PUMPSWAP_OWNER_AND_BASE_MINT"
    if outcome == "ACCOUNT_NOT_FOUND":
        return EXACT_POOL_NO_MATCH, "ACCOUNT_NOT_FOUND"
    if outcome == "BASE_MINT_MISMATCH":
        return IDENTITY_CONFLICT, "BASE_MINT_MISMATCH"
    if outcome == "SOURCE_UNAVAILABLE":
        return SOURCE_UNAVAILABLE, "PROTOCOL_ACCOUNT_BATCH_SOURCE_UNAVAILABLE"
    if outcome == "UNSUPPORTED_VENUE":
        return UNSUPPORTED_VENUE, "PROTOCOL_UNSUPPORTED_VENUE"
    if outcome == "POOL_OWNER_MISMATCH":
        return CONTRACT_BLOCKED, "POOL_OWNER_MISMATCH"
    if outcome == "POOL_DATA_UNDECODABLE":
        return CONTRACT_BLOCKED, "POOL_DATA_UNDECODABLE"
    return CONTRACT_BLOCKED, str(outcome or "CONTRACT_BLOCKED")


def process_protocol_confirmation_queue(
    connection: sqlite3.Connection,
    *,
    stage_budget: StageBudget,
    now: str,
    campaign_id: str | None = None,
    max_confirmations: int | None = None,
    account_batch_transport: Any | None = None,
    account_batch_transport_factory: Any | None = None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    request_key_prefix: str = "protocol-account-batch",
    stage_evidence_sink: Any | None = None,
    transport_identity_observer: Any | None = None,
    stage_sequence: int = 1,
) -> dict[str, Any]:
    """Process ABOVE_FLOOR protocol-due rows via governed getMultipleAccounts.

    Production path:
      above-floor nominations only
      → filter unsupported venues / invalid pools (zero transport)
      → Source-Governed solana_rpc/pumpswap_pool_account_batch
      → per-member PumpSwap owner + base_mint@43 confirmation
      → exact-market transitions
      → direct MEMORY_OBSERVATION_ELIGIBLE promotion when retained liquidity is fresh

    Below-floor and liquidity-unknown rows never enter this queue. One governed
    request per address batch (≤100). Stage budget charges one
    protocol_confirmation operation per batch, not per candidate. Seals one
    PROTOCOL_CONFIRMATION stage through stage_evidence_sink when provided.
    """
    from printer_v1.contracts.enums import SourceStatus
    from printer_v1.sources.campaign_six_unit_accounting import (
        CampaignSixUnitError,
        build_campaign_stage_id,
        seal_campaign_stage_evidence,
    )
    from printer_v1.sources.contracts import build_governed_source_request
    from printer_v1.sources.governed_execution import execute_source_request_with_governor
    from printer_v1.sources.measured_transport import (
        LocalValidationIdentity,
        MeasuredTransportError,
        MeasuredTransportLedger,
        record_payload_transports,
    )
    from printer_v1.sources.pumpswap import PUMPSWAP_AMM_PROGRAM_ID
    from printer_v1.sources.pumpswap_pool_account_batch import (
        CONTRACT_VERSION as BATCH_CONTRACT_VERSION,
        MAX_BATCH_ADDRESSES,
        REQUEST_KIND as BATCH_REQUEST_KIND,
        SOURCE_NAME as BATCH_SOURCE_NAME,
        build_ordered_unique_addresses,
        build_pumpswap_pool_account_batch_adapter,
        build_pumpswap_pool_account_batch_transport,
    )

    outcomes: list[dict[str, Any]] = []
    remaining_due: list[dict[str, str]] = []
    confirmed_for_market: list[dict[str, str]] = []
    promoted_observation_eligible: list[dict[str, Any]] = []
    requires_market_revalidation: list[dict[str, str]] = []
    source_request_ids: list[int] = []
    source_response_ids: list[int] = []
    source_failure_ids: list[int] = []
    source_requests = 0
    transport_operations = 0
    local_validation_steps = 0
    shared_source_failures = 0
    batch_count = 0
    outcome_counts: dict[str, int] = {}
    stage_ledger = MeasuredTransportLedger(
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        on_transport_recorded=transport_identity_observer,
    )
    local_validation_identities: list[LocalValidationIdentity] = []
    source_request_coverage: list[dict[str, Any]] = []
    accounting_blocker = False
    accounting_blocker_reason: str | None = None

    reason_placeholders = ",".join("?" * len(PROTOCOL_DUE_REASONS))
    rows = connection.execute(
        f"""
        SELECT network, mint_identity, pool_address, venue, base_mint, quote_mint,
               pool_program_id, token_program_id, current_reason, last_observed_at,
               latest_source_provenance_json
        FROM printer_exact_market_states
        WHERE current_state=? AND current_reason IN ({reason_placeholders})
        ORDER BY last_observed_at ASC, mint_identity ASC, pool_address ASC
        """,
        (CONTRACT_BLOCKED, *sorted(PROTOCOL_DUE_REASONS)),
    ).fetchall()

    pending: list[dict[str, Any]] = []
    for row in rows:
        mint = str(row["mint_identity"])
        pool = str(row["pool_address"])
        venue = str(row["venue"] or "")
        base = {
            "network": str(row["network"] or NETWORK),
            "mint": mint,
            "pool": pool,
            "venue": venue,
            "base_mint": str(row["base_mint"] or mint),
            "quote_mint": str(row["quote_mint"] or "UNKNOWN_QUOTE_MINT"),
            "token_program": str(row["token_program_id"] or "UNRESOLVED_TOKEN_PROGRAM"),
            "pool_program": str(row["pool_program_id"] or "UNRESOLVED_POOL_PROGRAM"),
        }
        if not mint or not pool:
            outcomes.append(
                {
                    "mint": mint,
                    "pool": pool,
                    "venue": venue,
                    "outcome": "CONTRACT_BLOCKED",
                    "reason": "MISSING_POOL_OR_MINT",
                    "transport": False,
                }
            )
            outcome_counts["CONTRACT_BLOCKED"] = (
                outcome_counts.get("CONTRACT_BLOCKED", 0) + 1
            )
            continue
        if not _protocol_supported_venue(venue):
            record_exact_market_transition(
                connection,
                ExactMarketObservation(
                    network=base["network"],
                    mint=mint,
                    pool=pool,
                    token_program=base["token_program"],
                    pool_program=base["pool_program"],
                    base_mint=base["base_mint"],
                    quote_mint=base["quote_mint"],
                    venue=venue or "UNKNOWN_VENUE",
                    state=UNSUPPORTED_VENUE,
                    reason="PROTOCOL_UNSUPPORTED_VENUE",
                    observed_at=now,
                    next_lawful_action_at=None,
                    source_provenance={
                        "stage": "protocol_confirmation",
                        "campaign_id": campaign_id,
                        "transport": False,
                    },
                    contract_version=BATCH_CONTRACT_VERSION,
                ),
                now=now,
            )
            outcomes.append(
                {
                    "mint": mint,
                    "pool": pool,
                    "venue": venue,
                    "outcome": "UNSUPPORTED_VENUE",
                    "reason": "PROTOCOL_UNSUPPORTED_VENUE",
                    "transport": False,
                }
            )
            outcome_counts["UNSUPPORTED_VENUE"] = (
                outcome_counts.get("UNSUPPORTED_VENUE", 0) + 1
            )
            continue
        pending.append(base)

    def _finalize_report(
        *,
        remaining: list[dict[str, str]],
        seal: bool,
    ) -> dict[str, Any]:
        nonlocal accounting_blocker, accounting_blocker_reason
        sealed = None
        stage_id = None
        if (
            seal
            and stage_evidence_sink is not None
            and (source_request_ids or outcomes)
            and all(str(value or "").strip() for value in (campaign_id, run_id, cycle_id))
        ):
            stage_id = build_campaign_stage_id(
                campaign_id=str(campaign_id),
                run_id=str(run_id),
                cycle_id=str(cycle_id),
                stage_kind="PROTOCOL_CONFIRMATION",
                stage_sequence=int(stage_sequence),
            )
            # Bind validation identities to the sealed stage_id.
            bound_validations = [
                LocalValidationIdentity(
                    stage_id=stage_id,
                    subject_identity=item.subject_identity,
                    validation_kind=item.validation_kind,
                    validation_ordinal=item.validation_ordinal,
                )
                for item in local_validation_identities
            ]
            first_cause = None
            terminal_status = "COMPLETED"
            if shared_source_failures:
                terminal_status = "BLOCKED"
                first_cause = "PROTOCOL_ACCOUNT_BATCH_SOURCE_UNAVAILABLE"
            elif not source_request_ids and outcomes:
                # Local-only outcomes (unsupported venue etc.) with zero transport.
                terminal_status = "COMPLETED"
            seal_error: Exception | None = None
            try:
                if stage_ledger.source_transport_operations > 0 or bound_validations:
                    sealed = seal_campaign_stage_evidence(
                        ledger=stage_ledger,
                        stage_id=stage_id,
                        stage_kind="PROTOCOL_CONFIRMATION",
                        stage_sequence=int(stage_sequence),
                        stage_terminal_status=terminal_status,
                        stage_first_terminal_cause=first_cause,
                        campaign_id=str(campaign_id),
                        run_id=str(run_id),
                        cycle_id=str(cycle_id),
                        sealed_at=now,
                        local_validation_identities=bound_validations or None,
                    )
                else:
                    # Expected zero-work: no transport and no validations.
                    # Explicit non-seal; never fabricate successful stage evidence.
                    sealed = None
            except (CampaignSixUnitError, MeasuredTransportError, ValueError, TypeError) as exc:
                seal_error = exc
                sealed = None
                accounting_blocker = True
                accounting_blocker_reason = (
                    f"PROTOCOL_STAGE_SEAL_FAILURE:{type(exc).__name__}:{exc}"
                )
            if seal_error is not None:
                # Fail closed: do not fabricate sealed success; surface typed blocker.
                pass
            elif sealed is not None:
                sealed = dict(sealed)
                sealed["source_request_ids"] = list(source_request_ids)
                sealed["source_response_ids"] = list(source_response_ids)
                sealed["source_failure_ids"] = list(source_failure_ids)
                sealed["outcome_counts"] = dict(outcome_counts)
                sealed["normalized_member_count"] = int(local_validation_steps)
                sealed["source_request_coverage"] = list(source_request_coverage)
                stage_evidence_sink(sealed)
        connection.commit()
        report_out: dict[str, Any] = {
            "outcomes": outcomes,
            "remaining_due": remaining,
            "confirmed_for_market": confirmed_for_market,
            "promoted_observation_eligible": promoted_observation_eligible,
            "requires_market_revalidation": requires_market_revalidation,
            "source_requests": source_requests,
            # Transport count is measured only; never fall back to request count.
            "transport_operations": transport_operations,
            "local_validation_steps": local_validation_steps,
            "attempts": source_requests,
            "batch_count": batch_count,
            "source_request_ids": source_request_ids,
            "source_response_ids": source_response_ids,
            "source_failure_ids": source_failure_ids,
            "shared_source_failures": shared_source_failures,
            "contract_version": BATCH_CONTRACT_VERSION,
            "requested_address_cap": MAX_BATCH_ADDRESSES,
            "outcome_counts": dict(outcome_counts),
            "source_request_coverage": list(source_request_coverage),
            "sealed_stage_evidence": sealed,
            "sealed_stage_evidence_blocks": (
                [sealed] if sealed is not None else []
            ),
            "stage_id": stage_id,
            "stage_sequence": int(stage_sequence),
            "accounting_blocker": accounting_blocker,
            "accounting_blocker_reason": accounting_blocker_reason,
        }
        return report_out

    if (
        not pending
        or stage_budget.is_sealed("protocol_confirmation")
        or stage_budget.available("protocol_confirmation") < 1
    ):
        return _finalize_report(
            remaining=[
                {"mint": p["mint"], "pool": p["pool"], "venue": p["venue"]}
                for p in pending
            ],
            seal=bool(outcomes),
        )

    cursor = 0
    max_batches = (
        stage_budget.available("protocol_confirmation")
        if max_confirmations is None
        else min(int(max_confirmations), stage_budget.available("protocol_confirmation"))
    )

    while cursor < len(pending) and batch_count < max_batches:
        slice_rows = pending[cursor:]
        addresses, address_map, skipped = build_ordered_unique_addresses(
            slice_rows, max_addresses=MAX_BATCH_ADDRESSES
        )
        # Advance cursor past every candidate belonging to this batch's pools,
        # and past invalid skips; stop before pure BATCH_CAP_EXCEEDED remainder.
        batch_pools = set(addresses)
        advanced = 0
        for item in slice_rows:
            if item["pool"] in batch_pools:
                advanced += 1
                continue
            # Cap exceeded — leave for next loop iteration after cursor advance
            break
        if advanced == 0 and not addresses:
            # Nothing transportable in remaining work
            for item in slice_rows:
                remaining_due.append(
                    {"mint": item["mint"], "pool": item["pool"], "venue": item["venue"]}
                )
            break
        cursor += advanced
        if not addresses:
            continue

        stage_budget.consume("protocol_confirmation", 1)
        batch_count += 1

        transport = account_batch_transport
        if account_batch_transport_factory is not None:
            transport = account_batch_transport_factory(tuple(addresses))
        if transport is None:
            transport = build_pumpswap_pool_account_batch_transport(addresses=addresses)

        adapter = build_pumpswap_pool_account_batch_adapter(
            enabled=True, transport=transport
        )
        serializable_map = {
            pool: [dict(c) for c in cands] for pool, cands in address_map.items()
        }
        request = build_governed_source_request(
            BATCH_SOURCE_NAME,
            BATCH_REQUEST_KIND,
            request_key=f"{request_key_prefix}-{batch_count}",
            tracking_priority=0,
            payload={
                "request_kind": BATCH_REQUEST_KIND,
                "chain": "solana",
                "addresses": list(addresses),
                "address_to_candidates": serializable_map,
                "commitment": "finalized",
                "encoding": "base64",
                "contract_version": BATCH_CONTRACT_VERSION,
                "campaign_id": campaign_id,
            },
        )
        execution = execute_source_request_with_governor(
            connection,
            request,
            adapter,
            recent_request_count=source_requests,
        )
        source_requests += 1
        source_request_ids.append(int(execution.request_record.id))
        if execution.response_record is not None:
            source_response_ids.append(int(execution.response_record.id))
        if execution.failure_record is not None:
            source_failure_ids.append(int(execution.failure_record.id))

        result = execution.normalized_result
        payload = result.normalized_payload or {}
        coverage_entry = {
            "source_request_id": int(execution.request_record.id),
            "source_name": BATCH_SOURCE_NAME,
            "request_kind": BATCH_REQUEST_KIND,
            "logical_stage_id": (
                f"{campaign_id}|{run_id}|{cycle_id}|PROTOCOL_CONFIRMATION|{int(stage_sequence)}"
                if campaign_id and run_id and cycle_id
                else f"PROTOCOL_CONFIRMATION|{int(stage_sequence)}|{batch_count}"
            ),
            "transport_identity_count": 0,
            "transport_identity_keys": [],
            "normalized_member_count": 0,
            "terminal_status": "COMPLETED",
        }
        if isinstance(payload, Mapping):
            try:
                before = stage_ledger.source_transport_operations
                before_len = len(list(getattr(stage_ledger, "transports", ()) or ()))
                record_payload_transports(
                    stage_ledger, payload, default_stage="PROTOCOL_CONFIRMATION"
                )
                delta = stage_ledger.source_transport_operations - before
                # Transport counts come only from successfully accepted measured
                # identities. Never invent a count when measurement yields zero
                # or fails.
                transport_operations += int(delta)
                coverage_entry["transport_identity_count"] = int(delta)
                coverage_entry["transport_identity_keys"] = (
                    _transport_identity_keys_from_ledger_delta(
                        stage_ledger, before_count=before_len
                    )
                )
            except MeasuredTransportError as exc:
                accounting_blocker = True
                accounting_blocker_reason = (
                    f"TRANSPORT_IDENTITY_MEASUREMENT_FAILED:{exc}"
                )
                coverage_entry["transport_identity_count"] = 0
                coverage_entry["transport_identity_keys"] = []
                coverage_entry["terminal_status"] = "BLOCKED"
                coverage_entry["measurement_error"] = str(exc)

        shared_fail = bool(
            result.failure_type or result.source_status != SourceStatus.COMPLETE
        )
        if shared_fail:
            shared_source_failures += 1
            coverage_entry["terminal_status"] = "BLOCKED"
            source_request_coverage.append(coverage_entry)
            for pool in addresses:
                for cand in address_map.get(pool, ()):
                    mint = str(cand["mint"])
                    state, reason = _outcome_to_exact_state("SOURCE_UNAVAILABLE")
                    record_exact_market_transition(
                        connection,
                        ExactMarketObservation(
                            network=NETWORK,
                            mint=mint,
                            pool=pool,
                            token_program="UNRESOLVED_TOKEN_PROGRAM",
                            pool_program=PUMPSWAP_AMM_PROGRAM_ID,
                            base_mint=mint,
                            quote_mint="UNKNOWN_QUOTE_MINT",
                            venue=str(cand.get("venue") or "pumpswap"),
                            state=state,
                            reason=reason,
                            observed_at=now,
                            next_lawful_action_at=now,
                            source_provenance={
                                "stage": "protocol_confirmation",
                                "campaign_id": campaign_id,
                                "request_id": int(execution.request_record.id),
                                "failure_id": (
                                    None
                                    if execution.failure_record is None
                                    else int(execution.failure_record.id)
                                ),
                                "failure_type": result.failure_type,
                                "shared_source_failure": True,
                            },
                            contract_version=BATCH_CONTRACT_VERSION,
                        ),
                        now=now,
                    )
                    outcomes.append(
                        {
                            "mint": mint,
                            "pool": pool,
                            "venue": cand.get("venue"),
                            "outcome": "SOURCE_UNAVAILABLE",
                            "reason": str(result.failure_type or reason),
                            "transport": True,
                            "shared_source_failure": True,
                        }
                    )
                    outcome_counts["SOURCE_UNAVAILABLE"] = (
                        outcome_counts.get("SOURCE_UNAVAILABLE", 0) + 1
                    )
            continue

        members = list(payload.get("members") or ()) if isinstance(payload, Mapping) else []
        member_count = int(
            (payload.get("local_validation_steps") if isinstance(payload, Mapping) else 0)
            or len(members)
        )
        local_validation_steps += member_count
        coverage_entry["normalized_member_count"] = member_count
        source_request_coverage.append(coverage_entry)
        for member in members:
            if not isinstance(member, Mapping):
                continue
            mint = str(member.get("mint") or "")
            pool = str(member.get("pool") or "")
            outcome = str(member.get("outcome") or "CONTRACT_BLOCKED")
            state, reason = _outcome_to_exact_state(outcome)
            venue = ""
            for cand in address_map.get(pool, ()):
                if cand.get("mint") == mint:
                    venue = str(cand.get("venue") or "")
                    break
            record_exact_market_transition(
                connection,
                ExactMarketObservation(
                    network=NETWORK,
                    mint=mint,
                    pool=pool,
                    token_program="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                    pool_program=(
                        PUMPSWAP_AMM_PROGRAM_ID
                        if outcome == "CURRENT_POOL_CONFIRMED"
                        else str(member.get("owner") or "UNRESOLVED_POOL_PROGRAM")
                    ),
                    base_mint=mint,
                    quote_mint="So11111111111111111111111111111111111111112",
                    venue=venue or "pumpswap",
                    state=state,
                    reason=reason,
                    observed_at=now,
                    next_lawful_action_at=(
                        None if outcome == "CURRENT_POOL_CONFIRMED" else now
                    ),
                    source_provenance={
                        "stage": "protocol_confirmation",
                        "campaign_id": campaign_id,
                        "request_id": int(execution.request_record.id),
                        "response_id": (
                            None
                            if execution.response_record is None
                            else int(execution.response_record.id)
                        ),
                        "batch_index": member.get("batch_index"),
                        "context_slot": (
                            payload.get("context_slot")
                            if isinstance(payload, Mapping)
                            else None
                        ),
                        "owner": member.get("owner"),
                        "data_length": member.get("data_length"),
                        "confirm_reason": member.get("confirm_reason"),
                        "contract_version": BATCH_CONTRACT_VERSION,
                        "shared_source_failure": False,
                    },
                    contract_version=BATCH_CONTRACT_VERSION,
                ),
                now=now,
            )
            outcomes.append(
                {
                    "mint": mint,
                    "pool": pool,
                    "venue": venue,
                    "outcome": outcome,
                    "reason": reason,
                    "transport": True,
                    "shared_source_failure": False,
                    "batch_index": member.get("batch_index"),
                }
            )
            outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
            local_validation_identities.append(
                LocalValidationIdentity(
                    stage_id="PROTOCOL_CONFIRMATION_PENDING",
                    subject_identity=f"{mint}:{pool}",
                    validation_kind=f"PUMPSWAP_ACCOUNT_{outcome}",
                    validation_ordinal=len(local_validation_identities) + 1,
                )
            )
            if outcome == "CURRENT_POOL_CONFIRMED":
                confirmed_for_market.append(
                    {"mint": mint, "pool": pool, "venue": venue or "pumpswap"}
                )
                promotion = promote_confirmed_with_retained_liquidity(
                    connection,
                    mint=mint,
                    pool=pool,
                    venue=venue or "pumpswap",
                    now=now,
                    campaign_id=campaign_id,
                    protocol_request_id=int(execution.request_record.id),
                )
                if promotion.get("promoted"):
                    promoted_observation_eligible.append(promotion)
                else:
                    requires_market_revalidation.append(
                        {
                            "mint": mint,
                            "pool": pool,
                            "venue": venue or "pumpswap",
                            "reason": str(promotion.get("reason") or ""),
                        }
                    )

    # Unprocessed remainder stays due.
    for item in pending[cursor:]:
        remaining_due.append(
            {"mint": item["mint"], "pool": item["pool"], "venue": item["venue"]}
        )

    return _finalize_report(remaining=remaining_due, seal=True)



def _transport_identity_keys_from_ledger_delta(
    ledger: Any,
    *,
    before_count: int,
) -> list[list[object]]:
    """Serialize one request's newly measured identities using the canonical key."""
    from printer_v1.sources.measured_transport import (
        MeasuredTransportError,
        canonical_transport_identity_key,
    )

    transports = list(getattr(ledger, "transports", ()) or ())
    keys: list[list[object]] = []
    for identity in transports[before_count:]:
        try:
            keys.append(list(canonical_transport_identity_key(identity)))
        except MeasuredTransportError:
            raise
    return keys


def build_source_request_coverage_manifest(
    entries: Sequence[Mapping[str, Any]],
    *,
    fail_closed_on_duplicate: bool = False,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Normalize durable Source Governor request coverage entries.

    Request count and transport count remain independent surfaces. Each durable
    request_id appears exactly once. When fail_closed_on_duplicate is True,
    duplicate request IDs return a blocker payload instead of silent skip.
    """
    seen: dict[int, dict[str, Any]] = {}
    duplicates: list[int] = []
    for raw in entries:
        if not isinstance(raw, Mapping):
            continue
        request_id = raw.get("source_request_id")
        if request_id is None:
            continue
        rid = int(request_id)
        if rid in seen:
            duplicates.append(rid)
            if fail_closed_on_duplicate:
                continue
            continue
        transport_keys_raw = raw.get("transport_identity_keys")
        transport_keys: list[Any] = []
        if isinstance(transport_keys_raw, (list, tuple)):
            for item in transport_keys_raw:
                if isinstance(item, Mapping):
                    transport_keys.append(dict(item))
                elif isinstance(item, (list, tuple)):
                    transport_keys.append(list(item))
        seen[rid] = {
            "source_request_id": rid,
            "source_name": str(raw.get("source_name") or ""),
            "request_kind": str(raw.get("request_kind") or ""),
            "logical_stage_id": str(raw.get("logical_stage_id") or ""),
            "transport_identity_count": int(raw.get("transport_identity_count") or 0),
            "normalized_member_count": int(raw.get("normalized_member_count") or 0),
            "terminal_status": str(raw.get("terminal_status") or "COMPLETED"),
            "transport_identity_keys": transport_keys,
        }
    if fail_closed_on_duplicate and duplicates:
        return {
            "status": "BLOCKED",
            "blocker": "CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH",
            "reason": "DUPLICATE_SOURCE_REQUEST_ID",
            "duplicate_request_ids": sorted(set(duplicates)),
            "manifest": [seen[key] for key in sorted(seen)],
        }
    return [seen[key] for key in sorted(seen)]


def union_market_revalidation_candidates(
    *groups: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, str]]:
    """Deterministic deduplicated union keyed by (mint, pool, venue).

    Preserves first-seen order across groups (early then residual). Never uses
    truthy A-or-B selection that can discard an early list.
    """
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for group in groups:
        if not group:
            continue
        for raw in group:
            if not isinstance(raw, Mapping):
                continue
            mint = str(raw.get("mint") or "")
            pool = str(raw.get("pool") or "")
            venue = str(raw.get("venue") or "")
            key = (mint, pool, venue)
            if not mint or not pool or key in seen:
                continue
            seen.add(key)
            entry = {
                "mint": mint,
                "pool": pool,
                "venue": venue,
            }
            reason = raw.get("reason")
            if reason is not None:
                entry["reason"] = str(reason)
            out.append(entry)
    return out


def merge_protocol_confirmation_reports(
    early: Mapping[str, Any] | None,
    residual: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Deterministic merge of protocol sequence 1 and sequence 2 reports.

    Preserves both sealed stage sequences as an ordered collection. Legacy
    single sealed_stage_evidence is a compatibility view only (last sealed).
    Duplicate durable request IDs fail closed.
    """
    left = dict(early or {})
    right = dict(residual or {})
    if not left and not right:
        return {
            "outcomes": [],
            "remaining_due": [],
            "promoted_observation_eligible": [],
            "requires_market_revalidation": [],
            "source_request_ids": [],
            "source_response_ids": [],
            "source_failure_ids": [],
            "source_requests": 0,
            "transport_operations": 0,
            "local_validation_steps": 0,
            "batch_count": 0,
            "shared_source_failures": 0,
            "outcome_counts": {},
            "source_request_coverage": [],
            "sealed_stage_evidence_blocks": [],
            "sealed_stage_evidence": None,
            "accounting_blocker": False,
            "accounting_blocker_reason": None,
        }
    if left and not right:
        blocks = list(left.get("sealed_stage_evidence_blocks") or ())
        if not blocks and left.get("sealed_stage_evidence") is not None:
            blocks = [left["sealed_stage_evidence"]]
        out = dict(left)
        out["sealed_stage_evidence_blocks"] = blocks
        out.setdefault("accounting_blocker", False)
        out.setdefault("accounting_blocker_reason", None)
        return out
    if right and not left:
        blocks = list(right.get("sealed_stage_evidence_blocks") or ())
        if not blocks and right.get("sealed_stage_evidence") is not None:
            blocks = [right["sealed_stage_evidence"]]
        out = dict(right)
        out["sealed_stage_evidence_blocks"] = blocks
        out.setdefault("accounting_blocker", False)
        out.setdefault("accounting_blocker_reason", None)
        return out

    def _list(key: str) -> list[Any]:
        return list(left.get(key) or ()) + list(right.get(key) or ())

    merged_request_ids = _list("source_request_ids")
    if len(merged_request_ids) != len(set(int(x) for x in merged_request_ids)):
        return {
            "outcomes": _list("outcomes"),
            "remaining_due": list(right.get("remaining_due") or ()),
            "promoted_observation_eligible": _list("promoted_observation_eligible"),
            "requires_market_revalidation": union_market_revalidation_candidates(
                left.get("requires_market_revalidation"),
                right.get("requires_market_revalidation"),
            ),
            "source_request_ids": merged_request_ids,
            "source_response_ids": _list("source_response_ids"),
            "source_failure_ids": _list("source_failure_ids"),
            "source_requests": int(left.get("source_requests") or 0)
            + int(right.get("source_requests") or 0),
            "transport_operations": int(left.get("transport_operations") or 0)
            + int(right.get("transport_operations") or 0),
            "local_validation_steps": int(left.get("local_validation_steps") or 0)
            + int(right.get("local_validation_steps") or 0),
            "batch_count": int(left.get("batch_count") or 0)
            + int(right.get("batch_count") or 0),
            "shared_source_failures": int(left.get("shared_source_failures") or 0)
            + int(right.get("shared_source_failures") or 0),
            "outcome_counts": {},
            "source_request_coverage": _list("source_request_coverage"),
            "sealed_stage_evidence_blocks": [],
            "sealed_stage_evidence": None,
            "accounting_blocker": True,
            "accounting_blocker_reason": (
                "CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH:"
                "DUPLICATE_PROTOCOL_REQUEST_ID"
            ),
            "merge_status": "BLOCKED",
        }

    outcome_counts: dict[str, int] = {}
    for source in (left.get("outcome_counts") or {}, right.get("outcome_counts") or {}):
        if not isinstance(source, Mapping):
            continue
        for key, value in source.items():
            outcome_counts[str(key)] = outcome_counts.get(str(key), 0) + int(value or 0)

    coverage_entries = _list("source_request_coverage")
    coverage_result = build_source_request_coverage_manifest(
        coverage_entries, fail_closed_on_duplicate=True
    )
    accounting_blocker = bool(
        left.get("accounting_blocker") or right.get("accounting_blocker")
    )
    accounting_blocker_reason = (
        left.get("accounting_blocker_reason")
        or right.get("accounting_blocker_reason")
    )
    if isinstance(coverage_result, dict) and coverage_result.get("status") == "BLOCKED":
        accounting_blocker = True
        accounting_blocker_reason = str(
            coverage_result.get("blocker")
            or "CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH"
        )
        coverage_manifest = list(coverage_result.get("manifest") or ())
    else:
        coverage_manifest = list(coverage_result)  # type: ignore[arg-type]

    sealed_blocks: list[Any] = []
    for report in (left, right):
        blocks = list(report.get("sealed_stage_evidence_blocks") or ())
        if blocks:
            sealed_blocks.extend(blocks)
        elif report.get("sealed_stage_evidence") is not None:
            sealed_blocks.append(report["sealed_stage_evidence"])

    # Dedupe promoted by (mint, pool) preserving order.
    promoted: list[dict[str, Any]] = []
    seen_promo: set[tuple[str, str]] = set()
    for raw in _list("promoted_observation_eligible"):
        if not isinstance(raw, Mapping):
            continue
        key = (str(raw.get("mint") or ""), str(raw.get("pool") or ""))
        if key in seen_promo:
            continue
        seen_promo.add(key)
        promoted.append(dict(raw))

    return {
        "outcomes": _list("outcomes"),
        "remaining_due": list(right.get("remaining_due") or ()),
        "confirmed_for_market": union_market_revalidation_candidates(
            left.get("confirmed_for_market"),
            right.get("confirmed_for_market"),
        ),
        "promoted_observation_eligible": promoted,
        "requires_market_revalidation": union_market_revalidation_candidates(
            left.get("requires_market_revalidation"),
            right.get("requires_market_revalidation"),
        ),
        "source_request_ids": [int(x) for x in merged_request_ids],
        "source_response_ids": [int(x) for x in _list("source_response_ids")],
        "source_failure_ids": [int(x) for x in _list("source_failure_ids")],
        "source_requests": int(left.get("source_requests") or 0)
        + int(right.get("source_requests") or 0),
        "transport_operations": int(left.get("transport_operations") or 0)
        + int(right.get("transport_operations") or 0),
        "local_validation_steps": int(left.get("local_validation_steps") or 0)
        + int(right.get("local_validation_steps") or 0),
        "batch_count": int(left.get("batch_count") or 0)
        + int(right.get("batch_count") or 0),
        "shared_source_failures": int(left.get("shared_source_failures") or 0)
        + int(right.get("shared_source_failures") or 0),
        "outcome_counts": outcome_counts,
        "source_request_coverage": coverage_manifest,
        "sealed_stage_evidence_blocks": sealed_blocks,
        # Compatibility view only — never the authoritative multi-stage owner.
        "sealed_stage_evidence": sealed_blocks[-1] if sealed_blocks else None,
        "accounting_blocker": accounting_blocker,
        "accounting_blocker_reason": accounting_blocker_reason,
        "merge_status": "BLOCKED" if accounting_blocker else "MERGED",
        "stage_sequences": sorted(
            {
                int(b.get("stage_sequence"))
                for b in sealed_blocks
                if isinstance(b, Mapping) and b.get("stage_sequence") is not None
            }
        ),
    }


CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH = (
    "CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH"
)

# ---------------------------------------------------------------------------
# Invocation-scoped source-request ownership (V2-9.8B WINDOW_15M scope repair)
# ---------------------------------------------------------------------------

PRINTER_V1_CAMPAIGN_SOURCE_REQUEST_SCOPE_V1 = (
    "PRINTER_V1_CAMPAIGN_SOURCE_REQUEST_SCOPE_V1"
)
LEGACY_STATIC_REQUEST_KEY_ROOT = "v2-9-7e-44"
CAMPAIGN_SOURCE_REQUEST_KEY_ROOT_TEMPLATE_PREFIX = "v2-9-8b-window15m-"
MAX_CAMPAIGN_SOURCE_REQUEST_KEY_ROOT_LENGTH = 180
MAX_RECONCILIATION_DETAIL_IDS = 20

CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED = (
    "CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED"
)
CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID = (
    "CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID"
)
CAMPAIGN_SOURCE_REQUEST_SCOPE_IDENTITY_MISMATCH = (
    "CAMPAIGN_SOURCE_REQUEST_SCOPE_IDENTITY_MISMATCH"
)
CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH = (
    "CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH"
)
LEGACY_STATIC_REQUEST_SCOPE_BLOCKED_OPERATIONALLY = (
    "LEGACY_STATIC_REQUEST_SCOPE_BLOCKED_OPERATIONALLY"
)
CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS = (
    "CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS"
)

# Exact reconciliation failure categories (stable terminal detail tokens).
DURABLE_REQUEST_NOT_STAGE_REPORTED = "DURABLE_REQUEST_NOT_STAGE_REPORTED"
DURABLE_REQUEST_NOT_MANIFESTED = "DURABLE_REQUEST_NOT_MANIFESTED"
STAGE_REQUEST_NOT_DURABLE = "STAGE_REQUEST_NOT_DURABLE"
STAGE_REQUEST_NOT_MANIFESTED = "STAGE_REQUEST_NOT_MANIFESTED"
MANIFEST_REQUEST_NOT_DURABLE = "MANIFEST_REQUEST_NOT_DURABLE"
DUPLICATE_COVERAGE_REQUEST_ID = "DUPLICATE_COVERAGE_REQUEST_ID"
DUPLICATE_DURABLE_REQUEST_ID = "DUPLICATE_DURABLE_REQUEST_ID"
STAGE_OWNERSHIP_GAP = "STAGE_OWNERSHIP_GAP"
STAGE_ACCOUNTING_BLOCKER = "STAGE_ACCOUNTING_BLOCKER"
CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE = (
    "CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE"
)
MULTIPLE_SOURCE_REQUEST_RECONCILIATION_DEFECTS = (
    "MULTIPLE_SOURCE_REQUEST_RECONCILIATION_DEFECTS"
)
SOURCE_REQUEST_TRANSPORT_IDENTITIES_MISSING = "SOURCE_REQUEST_TRANSPORT_IDENTITIES_MISSING"
SOURCE_REQUEST_TRANSPORT_IDENTITY_COUNT_MISMATCH = "SOURCE_REQUEST_TRANSPORT_IDENTITY_COUNT_MISMATCH"
SOURCE_REQUEST_TRANSPORT_IDENTITY_MALFORMED = "SOURCE_REQUEST_TRANSPORT_IDENTITY_MALFORMED"
SOURCE_REQUEST_DUPLICATE_TRANSPORT_IDENTITY = "SOURCE_REQUEST_DUPLICATE_TRANSPORT_IDENTITY"
CAMPAIGN_DUPLICATE_TRANSPORT_IDENTITY_OWNERSHIP = (
    "CAMPAIGN_DUPLICATE_TRANSPORT_IDENTITY_OWNERSHIP"
)

_PRINTABLE_ASCII_ROOT_RE = re.compile(r"^[\x21-\x7E]+$")


@dataclass(frozen=True)
class CampaignSourceRequestScope:
    """Immutable invocation-local durable source-request ownership contract."""

    scope_version: str
    request_key_root: str
    execution_id: str
    campaign_id: str
    run_id: str
    cycle_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            "scope_version": self.scope_version,
            "request_key_root": self.request_key_root,
            "execution_id": self.execution_id,
            "campaign_id": self.campaign_id,
            "run_id": self.run_id,
            "cycle_id": self.cycle_id,
        }


def derive_campaign_source_request_key_root(execution_id: str) -> str:
    """Canonical root: ``v2-9-8b-window15m-<execution_id>``."""
    return (
        f"{CAMPAIGN_SOURCE_REQUEST_KEY_ROOT_TEMPLATE_PREFIX}"
        f"{str(execution_id).strip()}"
    )


def build_campaign_source_request_scope(
    *,
    execution_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    scope_version: str = PRINTER_V1_CAMPAIGN_SOURCE_REQUEST_SCOPE_V1,
) -> CampaignSourceRequestScope:
    """Construct the typed scope from exact invocation identities."""
    return CampaignSourceRequestScope(
        scope_version=str(scope_version),
        request_key_root=derive_campaign_source_request_key_root(execution_id),
        execution_id=str(execution_id).strip(),
        campaign_id=str(campaign_id).strip(),
        run_id=str(run_id).strip(),
        cycle_id=str(cycle_id).strip(),
    )


def _coerce_campaign_source_request_scope(
    scope: CampaignSourceRequestScope | Mapping[str, Any] | None,
) -> CampaignSourceRequestScope | None:
    if scope is None:
        return None
    if isinstance(scope, CampaignSourceRequestScope):
        return scope
    if not isinstance(scope, Mapping):
        raise ValueError(CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID)
    try:
        return CampaignSourceRequestScope(
            scope_version=str(scope.get("scope_version") or "").strip(),
            request_key_root=str(scope.get("request_key_root") or "").strip(),
            execution_id=str(scope.get("execution_id") or "").strip(),
            campaign_id=str(scope.get("campaign_id") or "").strip(),
            run_id=str(scope.get("run_id") or "").strip(),
            cycle_id=str(scope.get("cycle_id") or "").strip(),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID) from exc


def _is_valid_request_key_root_token(root: str) -> bool:
    if not root:
        return False
    if len(root) > MAX_CAMPAIGN_SOURCE_REQUEST_KEY_ROOT_LENGTH:
        return False
    if any(ch.isspace() for ch in root):
        return False
    if "/" in root or "\\" in root:
        return False
    if not _PRINTABLE_ASCII_ROOT_RE.match(root):
        return False
    return True


def request_key_belongs_to_root(request_key: str, request_key_root: str) -> bool:
    """True when ``request_key`` equals or is derived under ``request_key_root``."""
    key = str(request_key or "")
    root = str(request_key_root or "")
    if not key or not root:
        return False
    return key == root or key.startswith(f"{root}")


def validate_campaign_source_request_scope(
    scope: CampaignSourceRequestScope | Mapping[str, Any] | None,
    *,
    execution_id: str | None = None,
    campaign_id: str | None = None,
    run_id: str | None = None,
    cycle_id: str | None = None,
) -> CampaignSourceRequestScope:
    """Validate typed scope; raise ValueError with a stable blocker code."""
    coerced = _coerce_campaign_source_request_scope(scope)
    if coerced is None:
        raise ValueError(CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED)

    if coerced.scope_version != PRINTER_V1_CAMPAIGN_SOURCE_REQUEST_SCOPE_V1:
        raise ValueError(CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID)

    identities = (
        coerced.execution_id,
        coerced.campaign_id,
        coerced.run_id,
        coerced.cycle_id,
    )
    if any(not value for value in identities):
        raise ValueError(CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID)

    if not _is_valid_request_key_root_token(coerced.request_key_root):
        raise ValueError(CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID)

    expected_root = derive_campaign_source_request_key_root(coerced.execution_id)
    if coerced.request_key_root != expected_root:
        raise ValueError(CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID)

    if (
        coerced.request_key_root == LEGACY_STATIC_REQUEST_KEY_ROOT
        or coerced.request_key_root.startswith(LEGACY_STATIC_REQUEST_KEY_ROOT)
    ):
        raise ValueError(LEGACY_STATIC_REQUEST_SCOPE_BLOCKED_OPERATIONALLY)

    expected = {
        "execution_id": execution_id,
        "campaign_id": campaign_id,
        "run_id": run_id,
        "cycle_id": cycle_id,
    }
    actual = {
        "execution_id": coerced.execution_id,
        "campaign_id": coerced.campaign_id,
        "run_id": coerced.run_id,
        "cycle_id": coerced.cycle_id,
    }
    for key, expected_value in expected.items():
        if expected_value is None:
            continue
        if str(expected_value).strip() != actual[key]:
            raise ValueError(CAMPAIGN_SOURCE_REQUEST_SCOPE_IDENTITY_MISMATCH)

    return coerced


def validate_permanent_operational_request_prefixes(
    *,
    request_key_root: str,
    discovery_request_key_prefix: str,
    front_door_request_key_prefix: str,
) -> None:
    """Permanent operational mode may only use the typed root as both prefixes."""
    discovery = str(discovery_request_key_prefix or "").strip()
    front_door = str(front_door_request_key_prefix or "").strip()
    root = str(request_key_root or "").strip()
    for prefix in (discovery, front_door):
        if (
            prefix == LEGACY_STATIC_REQUEST_KEY_ROOT
            or prefix.startswith(f"{LEGACY_STATIC_REQUEST_KEY_ROOT}")
        ):
            raise ValueError(LEGACY_STATIC_REQUEST_SCOPE_BLOCKED_OPERATIONALLY)
    if discovery != root or front_door != root:
        raise ValueError(CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH)


def inspect_preexisting_source_request_scope_collision(
    connection: sqlite3.Connection,
    *,
    request_key_root: str,
    max_ids: int = MAX_RECONCILIATION_DETAIL_IDS,
) -> dict[str, Any]:
    """Block when any durable row already owns the invocation root."""
    root = str(request_key_root or "").strip()
    if not root:
        raise ValueError(CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID)
    try:
        rows = connection.execute(
            """
            SELECT id, request_key
            FROM printer_source_requests
            WHERE request_key = ? OR request_key LIKE ?
            ORDER BY id ASC
            """,
            (root, f"{root}%"),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        # Ephemeral fixture DBs (for example bare ``:memory:`` without
        # migrations) have no source-request table. Treat as zero collision;
        # production authoritative DBs always carry the table.
        if "no such table" not in str(exc).lower():
            raise
        rows = []
    ids: list[int] = []
    for row in rows:
        ids.append(int(row[0] if not hasattr(row, "keys") else row["id"]))
    truncated = len(ids) > int(max_ids)
    bounded = ids[: int(max_ids)]
    if ids:
        return {
            "status": "BLOCKED",
            "blocker": CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS,
            "count": len(ids),
            "request_ids": bounded,
            "truncated": truncated,
            "request_key_root": root,
            "detail": (
                f"{CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS}"
                f":count={len(ids)}"
                f":ids={','.join(str(x) for x in bounded)}"
                + (":truncated=1" if truncated else ":truncated=0")
            ),
        }
    return {
        "status": "OK",
        "blocker": None,
        "count": 0,
        "request_ids": [],
        "truncated": False,
        "request_key_root": root,
        "detail": None,
    }


def _bounded_id_token(ids: Sequence[int], *, max_ids: int = MAX_RECONCILIATION_DETAIL_IDS) -> str:
    ordered = sorted({int(x) for x in ids})
    truncated = len(ordered) > max_ids
    shown = ordered[:max_ids]
    ids_part = ",".join(str(x) for x in shown)
    return (
        f"count={len(ordered)}:ids={ids_part}"
        f":truncated={'1' if truncated else '0'}"
    )


def format_source_request_reconciliation_detail(
    reconciliation: Mapping[str, Any],
    *,
    max_ids: int = MAX_RECONCILIATION_DETAIL_IDS,
) -> str:
    """Deterministic compact terminal detail for reconciliation failures."""
    categories = list(reconciliation.get("mismatch_categories") or ())
    if not categories:
        single = str(
            reconciliation.get("categorical_detail")
            or reconciliation.get("blocker")
            or CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH
        )
        categories = [single]
    category_id_map: dict[str, Sequence[int]] = {
        DURABLE_REQUEST_NOT_STAGE_REPORTED: list(
            reconciliation.get("durable_only_not_stage")
            or reconciliation.get("durable_not_stage_reported")
            or ()
        ),
        DURABLE_REQUEST_NOT_MANIFESTED: list(
            reconciliation.get("missing_from_manifest") or ()
        ),
        STAGE_REQUEST_NOT_DURABLE: list(
            reconciliation.get("stage_only_not_durable")
            or reconciliation.get("stage_reported_not_durable")
            or ()
        ),
        STAGE_REQUEST_NOT_MANIFESTED: list(
            reconciliation.get("missing_stage_reported_coverage") or ()
        ),
        MANIFEST_REQUEST_NOT_DURABLE: list(
            reconciliation.get("extra_in_manifest") or ()
        ),
        DUPLICATE_COVERAGE_REQUEST_ID: list(
            reconciliation.get("duplicate_coverage_request_ids")
            or reconciliation.get("duplicate_request_ids")
            or ()
        ),
        DUPLICATE_DURABLE_REQUEST_ID: list(
            reconciliation.get("duplicate_durable_request_ids") or ()
        ),
        STAGE_OWNERSHIP_GAP: list(
            reconciliation.get("stage_ownership_gaps") or ()
        ),
        CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE: list(
            reconciliation.get("out_of_scope_stage_request_ids") or ()
        ),
    }
    parts: list[str] = []
    for category in categories:
        if category == MULTIPLE_SOURCE_REQUEST_RECONCILIATION_DEFECTS:
            continue
        if category == STAGE_ACCOUNTING_BLOCKER:
            blockers = reconciliation.get("stage_accounting_blockers") or ()
            parts.append(
                f"{STAGE_ACCOUNTING_BLOCKER}:count={len(list(blockers))}"
            )
            continue
        transport_blockers = [
            item for item in reconciliation.get("transport_identity_blockers") or ()
            if isinstance(item, Mapping) and str(item.get("code") or "") == str(category)
        ]
        if transport_blockers:
            ids = [
                int(item.get("source_request_id") or 0)
                for item in transport_blockers
                if int(item.get("source_request_id") or 0) > 0
            ]
            parts.append(
                f"{category}:{_bounded_id_token(ids, max_ids=max_ids)}"
                if ids else f"{category}:count={len(transport_blockers)}"
            )
            continue
        ids = category_id_map.get(str(category)) or ()
        if ids:
            parts.append(f"{category}:{_bounded_id_token(ids, max_ids=max_ids)}")
        else:
            parts.append(str(category))
    if not parts:
        return str(
            reconciliation.get("blocker")
            or CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH
        )
    if len(parts) == 1:
        return parts[0]
    return (
        f"{MULTIPLE_SOURCE_REQUEST_RECONCILIATION_DEFECTS}|"
        + ";".join(parts)
    )


def classify_campaign_source_request_reconciliation_defects(
    reconciliation: Mapping[str, Any],
) -> list[str]:
    """Ordered exact categories for every failed reconciliation relation."""
    categories: list[str] = []
    if reconciliation.get("out_of_scope_stage_request_ids"):
        categories.append(CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE)
    if reconciliation.get("durable_only_not_stage") or reconciliation.get(
        "durable_not_stage_reported"
    ):
        categories.append(DURABLE_REQUEST_NOT_STAGE_REPORTED)
    if reconciliation.get("missing_from_manifest"):
        categories.append(DURABLE_REQUEST_NOT_MANIFESTED)
    if reconciliation.get("stage_only_not_durable") or reconciliation.get(
        "stage_reported_not_durable"
    ):
        categories.append(STAGE_REQUEST_NOT_DURABLE)
    if reconciliation.get("missing_stage_reported_coverage"):
        categories.append(STAGE_REQUEST_NOT_MANIFESTED)
    if reconciliation.get("extra_in_manifest"):
        categories.append(MANIFEST_REQUEST_NOT_DURABLE)
    if reconciliation.get("duplicate_coverage_request_ids"):
        categories.append(DUPLICATE_COVERAGE_REQUEST_ID)
    elif reconciliation.get("duplicate_request_ids") and not reconciliation.get(
        "duplicate_durable_request_ids"
    ):
        categories.append(DUPLICATE_COVERAGE_REQUEST_ID)
    if reconciliation.get("duplicate_durable_request_ids"):
        categories.append(DUPLICATE_DURABLE_REQUEST_ID)
    if reconciliation.get("stage_ownership_gaps"):
        categories.append(STAGE_OWNERSHIP_GAP)
    if reconciliation.get("stage_accounting_blockers"):
        categories.append(STAGE_ACCOUNTING_BLOCKER)
    for blocker in reconciliation.get("transport_identity_blockers") or ():
        if isinstance(blocker, Mapping) and blocker.get("code"):
            categories.append(str(blocker["code"]))
    # Preserve order uniqueness.
    seen: set[str] = set()
    ordered: list[str] = []
    for item in categories:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def load_scoped_stage_request_membership(
    connection: sqlite3.Connection,
    *,
    request_key_root: str,
    stage_request_ids: Sequence[int],
) -> dict[str, list[int]]:
    """Classify stage-reported IDs relative to the invocation root."""
    root = str(request_key_root or "").strip()
    proven: list[int] = []
    out_of_scope: list[int] = []
    not_durable: list[int] = []
    for rid in sorted({int(x) for x in stage_request_ids}):
        row = connection.execute(
            """
            SELECT id, request_key FROM printer_source_requests
            WHERE id = ?
            """,
            (rid,),
        ).fetchone()
        if row is None:
            not_durable.append(rid)
            continue
        key = str(row[1] if not hasattr(row, "keys") else row["request_key"])
        if request_key_belongs_to_root(key, root):
            proven.append(rid)
        else:
            out_of_scope.append(rid)
    return {
        "known_stage_request_ids_proven_durable": proven,
        "out_of_scope_stage_request_ids": out_of_scope,
        "stage_request_ids_not_durable": not_durable,
    }


def validate_campaign_transport_identity_manifest(
    entries: Sequence[Mapping[str, Any]],
    *,
    require_exact: bool,
) -> dict[str, Any]:
    """Validate and canonicalize exact per-request transport identity ownership."""
    from printer_v1.sources.measured_transport import (
        MeasuredTransportError,
        canonical_transport_identity_key,
    )

    manifest: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    owners_by_key: dict[tuple[object, ...], dict[str, Any]] = {}
    ordered_keys: list[tuple[object, ...]] = []
    declared_total = 0

    def _block(code: str, owner: Mapping[str, Any], **detail: Any) -> None:
        blockers.append({
            "code": code,
            "source_request_id": int(owner.get("source_request_id") or 0),
            "logical_stage_id": str(owner.get("logical_stage_id") or ""),
            **detail,
        })

    for raw in entries:
        if not isinstance(raw, Mapping) or raw.get("source_request_id") is None:
            continue
        entry = dict(raw)
        owner = {
            "source_request_id": int(entry["source_request_id"]),
            "logical_stage_id": str(entry.get("logical_stage_id") or ""),
            "source_name": str(entry.get("source_name") or ""),
            "request_kind": str(entry.get("request_kind") or ""),
        }
        try:
            declared = int(entry.get("transport_identity_count") or 0)
        except (TypeError, ValueError):
            declared = 0
            if require_exact:
                _block(SOURCE_REQUEST_TRANSPORT_IDENTITY_COUNT_MISMATCH, owner)
        declared_total += declared
        present = bool(
            entry.get(
                "_transport_identity_keys_present",
                "transport_identity_keys" in entry,
            )
        )
        raw_keys = entry.get("transport_identity_keys")
        canonical: list[tuple[object, ...]] = []
        within: set[tuple[object, ...]] = set()
        if raw_keys is None:
            raw_keys = ()
        if not isinstance(raw_keys, (list, tuple)) or isinstance(raw_keys, (str, bytes)):
            if require_exact:
                _block(SOURCE_REQUEST_TRANSPORT_IDENTITY_MALFORMED, owner)
            raw_keys = ()
        for raw_key in raw_keys:
            try:
                key = canonical_transport_identity_key(raw_key)
            except (MeasuredTransportError, TypeError, ValueError):
                if require_exact:
                    _block(SOURCE_REQUEST_TRANSPORT_IDENTITY_MALFORMED, owner)
                continue
            if key in within:
                if require_exact:
                    _block(
                        SOURCE_REQUEST_DUPLICATE_TRANSPORT_IDENTITY,
                        owner,
                        transport_identity_key=list(key),
                    )
                continue
            within.add(key)
            canonical.append(key)
        if require_exact and not present:
            _block(SOURCE_REQUEST_TRANSPORT_IDENTITIES_MISSING, owner)
        if require_exact and declared != len(canonical):
            _block(
                SOURCE_REQUEST_TRANSPORT_IDENTITY_COUNT_MISMATCH,
                owner,
                declared_count=declared,
                exact_key_count=len(canonical),
            )
        for key in canonical:
            prior = owners_by_key.get(key)
            if prior is not None:
                if require_exact:
                    _block(
                        CAMPAIGN_DUPLICATE_TRANSPORT_IDENTITY_OWNERSHIP,
                        owner,
                        transport_identity_key=list(key),
                        first_owner=dict(prior),
                        duplicate_owner=dict(owner),
                    )
                continue
            owners_by_key[key] = dict(owner)
            ordered_keys.append(key)
        entry["transport_identity_keys"] = [list(key) for key in canonical]
        entry.pop("_transport_identity_keys_present", None)
        manifest.append(entry)

    owners = [
        {"transport_identity_key": list(key), **owners_by_key[key]}
        for key in sorted(owners_by_key, key=repr)
    ]
    status = "BLOCKED" if require_exact and blockers else "OK"
    return {
        "status": status,
        "transport_identity_completeness_status": (
            status if require_exact else "LEGACY_UNCHECKED"
        ),
        "transport_identity_count_total": declared_total,
        "transport_identity_keys": [list(key) for key in sorted(ordered_keys, key=repr)],
        "transport_identity_owners": owners,
        "transport_identity_blockers": blockers,
        "manifest": manifest,
    }


def build_campaign_source_request_manifest(
    entries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the authoritative campaign-wide source-request manifest.

    Each durable request ID appears exactly once and owns one logical stage.
    Duplicate IDs fail closed (never silently deduplicated as success).
    """
    ordered: list[dict[str, Any]] = []
    by_id: dict[int, dict[str, Any]] = {}
    duplicates: list[int] = []
    missing_stage: list[int] = []
    for raw in entries:
        if not isinstance(raw, Mapping):
            continue
        if raw.get("source_request_id") is None:
            continue
        rid = int(raw["source_request_id"])
        if rid in by_id:
            duplicates.append(rid)
            continue
        stage = str(raw.get("logical_stage_id") or "").strip()
        transport_keys_raw = raw.get("transport_identity_keys")
        transport_keys: list[Any] = []
        if isinstance(transport_keys_raw, (list, tuple)):
            for item in transport_keys_raw:
                if isinstance(item, Mapping):
                    transport_keys.append(dict(item))
                elif isinstance(item, (list, tuple)):
                    transport_keys.append(list(item))
        entry = {
            "source_request_id": rid,
            "source_name": str(raw.get("source_name") or ""),
            "request_kind": str(raw.get("request_kind") or ""),
            "logical_stage_id": stage,
            "terminal_status": str(raw.get("terminal_status") or "COMPLETED"),
            "transport_identity_count": int(raw.get("transport_identity_count") or 0),
            "normalized_member_count": int(raw.get("normalized_member_count") or 0),
            "transport_identity_keys": transport_keys,
        }
        if not stage:
            missing_stage.append(rid)
        by_id[rid] = entry
        ordered.append(entry)
    status = "OK"
    blocker = None
    if duplicates:
        status = "BLOCKED"
        blocker = CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH
    elif missing_stage:
        status = "BLOCKED"
        blocker = CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH
    return {
        "status": status,
        "blocker": blocker,
        "manifest": ordered,
        "request_ids": [item["source_request_id"] for item in ordered],
        "duplicate_request_ids": sorted(set(duplicates)),
        "unowned_or_missing_stage_ids": sorted(set(missing_stage)),
        "request_count": len(ordered),
        "transport_identity_count_total": sum(
            int(item["transport_identity_count"]) for item in ordered
        ),
    }


def _normalize_stage_coverage_entry(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    """Accept only stage-produced coverage rows with required ownership fields.

    Never invents missing fields into a successful COMPLETED zero-transport entry.
    """
    if raw.get("source_request_id") is None:
        return None
    stage = str(raw.get("logical_stage_id") or "").strip()
    source_name = str(raw.get("source_name") or "").strip()
    request_kind = str(raw.get("request_kind") or "").strip()
    terminal = str(raw.get("terminal_status") or "").strip()
    if not stage or not source_name or not request_kind or not terminal:
        return None
    # transport/member counts must be explicitly present (including lawful zero).
    if "transport_identity_count" not in raw or "normalized_member_count" not in raw:
        return None
    try:
        transport_count = int(raw["transport_identity_count"])
        member_count = int(raw["normalized_member_count"])
    except (TypeError, ValueError):
        return None
    if transport_count < 0 or member_count < 0:
        return None
    transport_keys_raw = raw.get("transport_identity_keys")
    transport_keys: list[Any] = []
    if isinstance(transport_keys_raw, (list, tuple)):
        for item in transport_keys_raw:
            if isinstance(item, Mapping):
                transport_keys.append(dict(item))
            elif isinstance(item, (list, tuple)):
                transport_keys.append(list(item))
    return {
        "source_request_id": int(raw["source_request_id"]),
        "source_name": source_name,
        "request_kind": request_kind,
        "logical_stage_id": stage,
        "terminal_status": terminal,
        "transport_identity_count": transport_count,
        "normalized_member_count": member_count,
        "transport_identity_keys": transport_keys,
        "_transport_identity_keys_present": "transport_identity_keys" in raw,
    }


def collect_stage_source_request_coverage(
    diagnostics: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Collect real stage-produced coverage entries only.

    Never synthesizes COMPLETED/zero-transport coverage from bare request IDs.
    A request ID without stage-produced coverage remains missing and must fail
    reconciliation.
    """
    diag = dict(diagnostics or {})
    entries: list[dict[str, Any]] = []

    def _extend_coverage(raw: Any) -> None:
        if not raw:
            return
        if isinstance(raw, Mapping):
            # Prefer explicit list fields over recursive map walks that can
            # re-enter request-id-only surfaces.
            if "source_request_coverage" in raw and raw is not diag:
                _extend_coverage(raw.get("source_request_coverage"))
                return
            normalized = _normalize_stage_coverage_entry(raw)
            if normalized is not None:
                entries.append(normalized)
            return
        if isinstance(raw, (list, tuple)):
            for item in raw:
                _extend_coverage(item)

    # Explicit campaign-assembled list (must already be stage-produced rows).
    _extend_coverage(diag.get("campaign_source_request_coverage"))
    _extend_coverage(diag.get("source_request_coverage"))

    # Per-stage real coverage surfaces only — never request-id fallbacks.
    protocol = diag.get("protocol_confirmation") or {}
    if isinstance(protocol, Mapping):
        _extend_coverage(protocol.get("source_request_coverage"))

    backup = diag.get("liquidity_backup") or {}
    if isinstance(backup, Mapping):
        _extend_coverage(backup.get("source_request_coverage"))

    gecko = diag.get("geckoterminal_nomination") or diag.get(
        "geckoterminal_fresh_nomination"
    ) or {}
    if isinstance(gecko, Mapping):
        _extend_coverage(gecko.get("source_request_coverage"))

    locator = diag.get("dexscreener_locator") or diag.get("locator") or {}
    if isinstance(locator, Mapping):
        _extend_coverage(locator.get("source_request_coverage"))

    discovery = diag.get("direct_migration_discovery") or diag.get("discovery") or {}
    if isinstance(discovery, Mapping):
        _extend_coverage(discovery.get("source_request_coverage"))
        ledger = discovery.get("source_operation_ledger") or {}
        if isinstance(ledger, Mapping):
            _extend_coverage(ledger.get("source_request_coverage"))

    for report in diag.get("permanent_market_reports") or ():
        if isinstance(report, Mapping):
            _extend_coverage(report.get("source_request_coverage"))

    _extend_coverage(diag.get("holder_source_request_coverage"))
    _extend_coverage(diag.get("final_refresh_source_request_coverage"))

    # Collapse exact duplicate rows collected from multiple diagnostic surfaces
    # that re-export the same stage-produced coverage entry. Distinct stage
    # owners for one request ID are preserved so reconciliation can fail closed.
    deduped: list[dict[str, Any]] = []
    seen_exact: set[tuple[Any, ...]] = set()
    for entry in entries:
        key = (
            entry["source_request_id"],
            entry["logical_stage_id"],
            entry["source_name"],
            entry["request_kind"],
            entry["terminal_status"],
            entry["transport_identity_count"],
            entry["normalized_member_count"],
        )
        if key in seen_exact:
            continue
        seen_exact.add(key)
        deduped.append(entry)
    return deduped


def collect_stage_reported_request_ids(
    diagnostics: Mapping[str, Any] | None,
) -> list[int]:
    """Collect stage-reported durable request IDs without inventing coverage."""
    diag = dict(diagnostics or {})
    ids: list[int] = []

    def _add(raw: Any) -> None:
        if raw is None:
            return
        if isinstance(raw, (list, tuple)):
            for item in raw:
                _add(item)
            return
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            return

    for key in (
        "source_request_ids",
        "protocol_source_request_ids",
        "holder_source_request_ids",
        "stage_reported_request_ids",
    ):
        _add(diag.get(key))

    protocol = diag.get("protocol_confirmation") or {}
    if isinstance(protocol, Mapping):
        _add(protocol.get("source_request_ids"))

    backup = diag.get("liquidity_backup") or {}
    if isinstance(backup, Mapping):
        _add(backup.get("source_request_ids"))

    gecko = diag.get("geckoterminal_nomination") or diag.get(
        "geckoterminal_fresh_nomination"
    ) or {}
    if isinstance(gecko, Mapping):
        if gecko.get("request_id") is not None:
            _add(gecko.get("request_id"))
        _add(gecko.get("source_request_ids"))

    locator = diag.get("dexscreener_locator") or diag.get("locator") or {}
    if isinstance(locator, Mapping):
        if locator.get("request_id") is not None:
            _add(locator.get("request_id"))
        _add(locator.get("source_request_ids"))

    discovery = diag.get("direct_migration_discovery") or diag.get("discovery") or {}
    if isinstance(discovery, Mapping):
        _add(discovery.get("source_request_ids"))
        ledger = discovery.get("source_operation_ledger") or {}
        if isinstance(ledger, Mapping):
            _add(ledger.get("request_ids"))
            _add(ledger.get("source_request_ids"))

    for report in diag.get("permanent_market_reports") or ():
        if isinstance(report, Mapping):
            _add(report.get("source_request_ids"))

    _add(diag.get("final_refresh_source_request_ids"))
    return ids


def load_durable_campaign_source_request_ids(
    connection: sqlite3.Connection,
    *,
    request_key_prefixes: Sequence[str],
    known_request_ids: Sequence[int] | None = None,
    request_key_root: str | None = None,
    enforce_request_key_root: bool = False,
) -> list[int]:
    """Load database-proven durable Source Governor request IDs.

    Stage-reported IDs are never copied into the durable set. Each candidate
    ID must exist as a row in ``printer_source_requests``. Request-key prefix
    lookup may add other genuine durable IDs for the invocation.

    When ``enforce_request_key_root`` is True (permanent operational scope),
    only rows whose ``request_key`` belongs to ``request_key_root`` enter ``D``.
    The root filter applies to **both** known-ID lookup and prefix lookup so no
    foreign-root row can enter ``D`` through any path.
    """
    ids: set[int] = set()
    root = str(request_key_root or "").strip() or None
    prefixes = list(request_key_prefixes or ())
    if root and root not in prefixes:
        prefixes = [root, *prefixes]

    def _accept(rid: int, key: str) -> None:
        if enforce_request_key_root and root:
            if request_key_belongs_to_root(key, root):
                ids.add(rid)
            return
        ids.add(rid)

    candidates = sorted({int(rid) for rid in (known_request_ids or ())})
    if candidates:
        placeholders = ",".join("?" * len(candidates))
        rows = connection.execute(
            f"""
            SELECT id, request_key FROM printer_source_requests
            WHERE id IN ({placeholders})
            ORDER BY id ASC
            """,
            tuple(candidates),
        ).fetchall()
        for row in rows:
            rid = int(row[0] if not hasattr(row, "keys") else row["id"])
            key = str(
                row[1] if not hasattr(row, "keys") else row["request_key"]
            )
            _accept(rid, key)
    for prefix in prefixes:
        if not prefix:
            continue
        rows = connection.execute(
            """
            SELECT id, request_key FROM printer_source_requests
            WHERE request_key = ? OR request_key LIKE ?
            ORDER BY id ASC
            """,
            (str(prefix), f"{prefix}%"),
        ).fetchall()
        for row in rows:
            rid = int(row[0] if not hasattr(row, "keys") else row["id"])
            key = str(
                row[1] if not hasattr(row, "keys") else row["request_key"]
            )
            _accept(rid, key)
    return sorted(ids)


def load_prefix_lookup_request_ids(
    connection: sqlite3.Connection,
    *,
    request_key_prefixes: Sequence[str],
    request_key_root: str | None = None,
    enforce_request_key_root: bool = False,
) -> list[int]:
    """Durable IDs discovered solely by request-key prefix lookup.

    When ``enforce_request_key_root`` is True, only rows belonging to
    ``request_key_root`` are returned (never foreign-root contamination).
    """
    ids: set[int] = set()
    root = str(request_key_root or "").strip() or None
    for prefix in request_key_prefixes:
        if not prefix:
            continue
        rows = connection.execute(
            """
            SELECT id, request_key FROM printer_source_requests
            WHERE request_key = ? OR request_key LIKE ?
            ORDER BY id ASC
            """,
            (str(prefix), f"{prefix}%"),
        ).fetchall()
        for row in rows:
            rid = int(row[0] if not hasattr(row, "keys") else row["id"])
            key = str(
                row[1] if not hasattr(row, "keys") else row["request_key"]
            )
            if enforce_request_key_root and root:
                if request_key_belongs_to_root(key, root):
                    ids.add(rid)
            else:
                ids.add(rid)
    return sorted(ids)


def collect_stage_accounting_blockers(
    diagnostics: Mapping[str, Any] | None,
) -> list[dict[str, str]]:
    """Collect accounting blockers from every governed stage surface present.

    Ordinary candidate-local rejections are not accounting blockers. Only
    explicit ``accounting_blocker`` / stage-safe-stop surfaces qualify.
    """
    diag = dict(diagnostics or {})
    blockers: list[dict[str, str]] = []

    def _maybe_add(stage_name: str, surface: Any) -> None:
        if not isinstance(surface, Mapping):
            return
        if surface.get("accounting_blocker") is True:
            reason = str(
                surface.get("accounting_blocker_reason")
                or f"{stage_name.upper()}_ACCOUNTING_BLOCKER"
            )
            blockers.append({"stage": stage_name, "reason": reason})
            return
        # Direct-migration / six-unit safe-stop surfaces.
        if surface.get("campaign_safe_stop") is True:
            reason = str(
                surface.get("accounting_block_reason")
                or surface.get("accounting_blocker_reason")
                or f"{stage_name.upper()}_CAMPAIGN_SAFE_STOP"
            )
            blockers.append({"stage": stage_name, "reason": reason})
            return
        if surface.get("accounting_block_reason"):
            blockers.append(
                {
                    "stage": stage_name,
                    "reason": str(surface.get("accounting_block_reason")),
                }
            )

    # Named stage surfaces.
    named = (
        ("protocol_confirmation", diag.get("protocol_confirmation")),
        ("liquidity_backup", diag.get("liquidity_backup")),
        (
            "geckoterminal_nomination",
            diag.get("geckoterminal_nomination")
            or diag.get("geckoterminal_fresh_nomination"),
        ),
        (
            "dexscreener_locator",
            diag.get("dexscreener_locator") or diag.get("locator"),
        ),
        (
            "direct_migration_discovery",
            diag.get("direct_migration_discovery") or diag.get("discovery"),
        ),
        ("holder_context", diag.get("holder_context")),
        ("final_refresh", diag.get("final_refresh")),
    )
    for name, surface in named:
        _maybe_add(name, surface)
        if isinstance(surface, Mapping):
            ledger = surface.get("source_operation_ledger")
            if isinstance(ledger, Mapping):
                _maybe_add(f"{name}.source_operation_ledger", ledger)

    # Market batch / reconciliation reports.
    for index, report in enumerate(diag.get("permanent_market_reports") or ()):
        if isinstance(report, Mapping):
            _maybe_add(f"permanent_market_reports[{index}]", report)

    # Generic scan of remaining mapping children that carry accounting flags
    # without hardcoding only three stage names.
    for key, value in diag.items():
        if key in {
            "protocol_confirmation",
            "liquidity_backup",
            "geckoterminal_nomination",
            "geckoterminal_fresh_nomination",
            "dexscreener_locator",
            "locator",
            "direct_migration_discovery",
            "discovery",
            "holder_context",
            "final_refresh",
            "permanent_market_reports",
            "campaign_source_request_coverage",
            "source_request_coverage",
            "stage_reported_request_ids",
            "source_request_ids",
            "holder_source_request_ids",
            "protocol_source_request_ids",
            "observation_reserve",
            "freeze_depth_enforcement",
            "campaign_source_request_reconciliation",
        }:
            continue
        if isinstance(value, Mapping) and (
            value.get("accounting_blocker") is True
            or value.get("campaign_safe_stop") is True
            or value.get("accounting_block_reason")
        ):
            _maybe_add(str(key), value)

    # Deduplicate by (stage, reason).
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for item in blockers:
        key = (item["stage"], item["reason"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def assemble_and_reconcile_campaign_source_requests(
    connection: sqlite3.Connection,
    *,
    diagnostics: Mapping[str, Any] | None,
    request_key_prefixes: Sequence[str] | None = None,
    extra_manifest_entries: Sequence[Mapping[str, Any]] | None = None,
    stage_accounting_blockers: Sequence[str] | None = None,
    request_key_root: str | None = None,
    request_scope_version: str | None = None,
    campaign_source_request_scope: (
        CampaignSourceRequestScope | Mapping[str, Any] | None
    ) = None,
) -> dict[str, Any]:
    """Build durable IDs + stage-reported IDs + real coverage and reconcile.

    PASS invariant (database-proven):
      set(durable request IDs)
      == set(stage-reported request IDs)
      == set(coverage manifest request IDs)

    Stage-reported IDs are never treated as durable until a
    ``printer_source_requests`` row is proven.

    When either ``campaign_source_request_scope`` or ``request_key_root`` is
    supplied (argument or diagnostics), scoped enforcement is active: a valid
    typed scope is required, prefix lookup uses exactly
    ``[scope.request_key_root]``, and foreign prefixes/roots fail closed with a
    stable scope blocker before set reconciliation.
    """
    diag = dict(diagnostics or {})
    scope_input = (
        campaign_source_request_scope
        if campaign_source_request_scope is not None
        else diag.get("campaign_source_request_scope")
    )
    explicit_root_param = (
        str(request_key_root).strip() if request_key_root is not None else ""
    ) or None
    diagnostic_root = str(diag.get("request_key_root") or "").strip() or None
    scoped_enforcement = (
        scope_input is not None
        or explicit_root_param is not None
        or diagnostic_root is not None
    )

    scope_obj: CampaignSourceRequestScope | None = None
    root: str | None = None
    scope_version: str | None = None
    prefixes: list[str]
    enforce_root: bool

    if scoped_enforcement:
        # Fail closed: do not catch invalid scope and continue unscoped.
        if scope_input is None:
            raise ValueError(CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED)
        scope_obj = validate_campaign_source_request_scope(scope_input)
        root = scope_obj.request_key_root
        scope_version = scope_obj.scope_version
        if explicit_root_param is not None and explicit_root_param != root:
            raise ValueError(CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH)
        if diagnostic_root is not None and diagnostic_root != root:
            raise ValueError(CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH)
        if (
            request_scope_version is not None
            and str(request_scope_version).strip()
            and str(request_scope_version).strip() != scope_version
        ):
            raise ValueError(CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID)
        caller_prefixes = [
            str(p).strip()
            for p in (request_key_prefixes or ())
            if str(p).strip()
        ]
        for prefix in caller_prefixes:
            if prefix != root:
                raise ValueError(CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH)
        # Canonical prefix set only — never merge foreign caller prefixes.
        prefixes = [root]
        enforce_root = True
    else:
        # Legacy unscoped fixture path: multi-prefix behavior retained.
        prefixes = [
            str(p).strip()
            for p in (request_key_prefixes or ())
            if str(p).strip()
        ]
        enforce_root = False

    coverage = collect_stage_source_request_coverage(diag)
    if extra_manifest_entries:
        for item in extra_manifest_entries:
            normalized = _normalize_stage_coverage_entry(dict(item))
            if normalized is not None:
                coverage.append(normalized)
    transport_identity_validation = validate_campaign_transport_identity_manifest(
        coverage,
        require_exact=enforce_root,
    )
    if enforce_root:
        coverage = list(transport_identity_validation["manifest"])
    stage_reported_raw = collect_stage_reported_request_ids(diag)
    stage_reported = sorted({int(x) for x in stage_reported_raw})

    membership: dict[str, list[int]] = {
        "known_stage_request_ids_proven_durable": [],
        "out_of_scope_stage_request_ids": [],
        "stage_request_ids_not_durable": [],
    }
    if enforce_root and root is not None:
        membership = load_scoped_stage_request_membership(
            connection,
            request_key_root=root,
            stage_request_ids=stage_reported,
        )
    # Independent durable set: only database-proven IDs (plus prefix lookup).
    durable = load_durable_campaign_source_request_ids(
        connection,
        request_key_prefixes=prefixes,
        known_request_ids=stage_reported,
        request_key_root=root,
        enforce_request_key_root=enforce_root,
    )
    prefix_lookup_ids = load_prefix_lookup_request_ids(
        connection,
        request_key_prefixes=prefixes if prefixes else (),
        request_key_root=root,
        enforce_request_key_root=enforce_root,
    )
    recon = reconcile_campaign_source_requests(
        durable_request_ids=durable,
        manifest_entries=coverage,
        stage_reported_request_ids=stage_reported,
        stage_reported_request_ids_raw=stage_reported_raw,
        out_of_scope_stage_request_ids=membership.get(
            "out_of_scope_stage_request_ids"
        ),
    )
    recon["transport_identity_completeness_status"] = (
        transport_identity_validation["transport_identity_completeness_status"]
    )
    recon["transport_identity_keys"] = list(
        transport_identity_validation["transport_identity_keys"]
    )
    recon["transport_identity_owners"] = list(
        transport_identity_validation["transport_identity_owners"]
    )
    recon["transport_identity_blockers"] = list(
        transport_identity_validation["transport_identity_blockers"]
    )
    if transport_identity_validation["status"] != "OK":
        recon["status"] = "BLOCKED"
        recon["blocker"] = CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH
    # Generic all-stage accounting-blocker collector.
    stage_blockers = collect_stage_accounting_blockers(diag)
    if stage_accounting_blockers:
        for raw in stage_accounting_blockers:
            if not raw:
                continue
            stage_blockers.append(
                {"stage": "caller_supplied", "reason": str(raw)}
            )
    # BLOCKED coverage caused by accounting failure must not pass as a
    # harmless present row when the stage also flagged an accounting blocker.
    coverage_ids = sorted({int(e["source_request_id"]) for e in coverage})
    recon["coverage_request_ids"] = coverage_ids
    recon["stage_reported_not_durable"] = list(
        recon.get("stage_only_not_durable") or ()
    )
    recon["durable_not_stage_reported"] = list(
        recon.get("durable_only_not_stage") or ()
    )
    recon["request_scope_version"] = scope_version
    recon["request_key_root"] = root
    recon["prefix_lookup_request_ids"] = list(prefix_lookup_ids)
    recon["known_stage_request_ids_proven_durable"] = list(
        membership.get("known_stage_request_ids_proven_durable") or ()
    )
    recon["out_of_scope_stage_request_ids"] = list(
        membership.get("out_of_scope_stage_request_ids") or ()
    )
    if recon.get("out_of_scope_stage_request_ids"):
        recon = dict(recon)
        recon["status"] = "BLOCKED"
        recon["blocker"] = CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH
    if recon.get("stage_only_not_durable"):
        recon = dict(recon)
        recon["status"] = "BLOCKED"
        recon["blocker"] = CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH
    if stage_blockers:
        recon = dict(recon)
        recon["status"] = "BLOCKED"
        recon["blocker"] = CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH
        recon["stage_accounting_blockers"] = stage_blockers
    categories = classify_campaign_source_request_reconciliation_defects(recon)
    if recon.get("status") != "OK":
        if len(categories) > 1:
            recon["categorical_detail"] = (
                MULTIPLE_SOURCE_REQUEST_RECONCILIATION_DEFECTS
            )
        elif len(categories) == 1:
            recon["categorical_detail"] = categories[0]
        else:
            recon["categorical_detail"] = (
                CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH
            )
    else:
        recon["categorical_detail"] = None
    recon["mismatch_categories"] = categories
    recon["terminal_detail"] = (
        None
        if recon.get("status") == "OK"
        else format_source_request_reconciliation_detail(recon)
    )
    recon["campaign_source_request_count"] = int(recon.get("request_count") or 0)
    recon["campaign_transport_operation_count"] = int(
        recon.get("transport_identity_count_total") or 0
    )
    recon["durable_campaign_request_ids"] = list(recon.get("durable_request_ids") or ())
    recon["stage_reported_request_ids"] = list(
        recon.get("stage_reported_request_ids") or stage_reported
    )
    recon["stage_produced_coverage_entries"] = list(coverage)
    recon["campaign_source_request_manifest"] = list(recon.get("manifest") or ())
    recon["campaign_source_request_reconciliation"] = {
        "status": recon.get("status"),
        "blocker": recon.get("blocker"),
        "categorical_detail": recon.get("categorical_detail"),
        "mismatch_categories": list(categories),
        "terminal_detail": recon.get("terminal_detail"),
        "request_scope_version": scope_version,
        "request_key_root": root,
        "prefix_lookup_request_ids": list(prefix_lookup_ids),
        "known_stage_request_ids_proven_durable": list(
            recon.get("known_stage_request_ids_proven_durable") or ()
        ),
        "out_of_scope_stage_request_ids": list(
            recon.get("out_of_scope_stage_request_ids") or ()
        ),
        "missing_from_manifest": recon.get("missing_from_manifest"),
        "extra_in_manifest": recon.get("extra_in_manifest"),
        "duplicate_request_ids": recon.get("duplicate_request_ids"),
        "duplicate_coverage_request_ids": recon.get(
            "duplicate_coverage_request_ids"
        ),
        "duplicate_durable_request_ids": recon.get(
            "duplicate_durable_request_ids"
        ),
        "missing_stage_reported_coverage": recon.get(
            "missing_stage_reported_coverage"
        ),
        "stage_ownership_gaps": recon.get("stage_ownership_gaps"),
        "stage_reported_not_durable": recon.get("stage_reported_not_durable"),
        "durable_not_stage_reported": recon.get("durable_not_stage_reported"),
        "stage_accounting_blockers": recon.get("stage_accounting_blockers") or [],
        "transport_identity_completeness_status": recon.get(
            "transport_identity_completeness_status"
        ),
        "transport_identity_keys": list(recon.get("transport_identity_keys") or ()),
        "transport_identity_owners": list(recon.get("transport_identity_owners") or ()),
        "transport_identity_blockers": list(recon.get("transport_identity_blockers") or ()),
        "coverage_request_ids": coverage_ids,
        "durable_campaign_request_ids": list(
            recon.get("durable_campaign_request_ids") or ()
        ),
        "stage_reported_request_ids": list(
            recon.get("stage_reported_request_ids") or ()
        ),
    }
    return recon


def reconcile_campaign_source_requests(
    *,
    durable_request_ids: Sequence[int],
    manifest_entries: Sequence[Mapping[str, Any]],
    stage_reported_request_ids: Sequence[int] | None = None,
    stage_reported_request_ids_raw: Sequence[int] | None = None,
    out_of_scope_stage_request_ids: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Require durable IDs == stage-reported IDs == coverage manifest IDs."""
    durable = sorted({int(x) for x in durable_request_ids})
    stage_reported = sorted(
        {
            int(x)
            for x in (
                stage_reported_request_ids
                if stage_reported_request_ids is not None
                else durable_request_ids
            )
        }
    )
    built = build_campaign_source_request_manifest(manifest_entries)
    manifest_ids = sorted({int(x) for x in built["request_ids"]})
    durable_set = set(durable)
    stage_set = set(stage_reported)
    manifest_set = set(manifest_ids)
    missing_from_manifest = sorted(durable_set - manifest_set)
    extra_in_manifest = sorted(manifest_set - durable_set)
    out_of_scope = sorted(
        {int(x) for x in (out_of_scope_stage_request_ids or ())}
    )
    out_of_scope_set = set(out_of_scope)
    missing_stage_reported_coverage = sorted(stage_set - manifest_set)
    # Out-of-scope stage IDs are durable rows under a foreign root — they are
    # not "non-durable". Categorize them separately and exclude from
    # STAGE_REQUEST_NOT_DURABLE.
    stage_only_not_durable = sorted(stage_set - durable_set - out_of_scope_set)
    durable_only_not_stage = sorted(durable_set - stage_set)
    stage_ownership_gaps = [
        entry["source_request_id"]
        for entry in built.get("manifest") or ()
        if not str(entry.get("logical_stage_id") or "").strip()
    ]
    ok = (
        built["status"] == "OK"
        and not missing_from_manifest
        and not extra_in_manifest
        and not missing_stage_reported_coverage
        and not stage_only_not_durable
        and not durable_only_not_stage
        and not stage_ownership_gaps
        and not out_of_scope
        and len(list(durable_request_ids)) == len(set(int(x) for x in durable_request_ids))
    )
    duplicate_durable: list[int] = []
    if len(list(durable_request_ids)) != len(set(int(x) for x in durable_request_ids)):
        ok = False
        seen: dict[int, int] = {}
        for x in durable_request_ids:
            rid = int(x)
            seen[rid] = seen.get(rid, 0) + 1
        duplicate_durable = sorted(rid for rid, count in seen.items() if count > 1)
    raw_stage = (
        list(stage_reported_request_ids_raw)
        if stage_reported_request_ids_raw is not None
        else list(stage_reported_request_ids or stage_reported)
    )
    # Multi-surface re-reporting of the same ID is allowed; only true duplicate
    # durable IDs and duplicate coverage rows (different stages) fail closed.
    if (
        missing_from_manifest
        or extra_in_manifest
        or missing_stage_reported_coverage
        or stage_only_not_durable
        or durable_only_not_stage
        or stage_ownership_gaps
        or out_of_scope
    ):
        ok = False
    duplicate_coverage = list(built.get("duplicate_request_ids") or ())
    return {
        "status": "OK" if ok else "BLOCKED",
        "blocker": None if ok else CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH,
        "durable_request_ids": durable,
        "stage_reported_request_ids": stage_reported,
        "manifest_request_ids": manifest_ids,
        "missing_from_manifest": missing_from_manifest,
        "extra_in_manifest": extra_in_manifest,
        "missing_stage_reported_coverage": missing_stage_reported_coverage,
        "stage_only_not_durable": stage_only_not_durable,
        "durable_only_not_stage": durable_only_not_stage,
        "stage_ownership_gaps": stage_ownership_gaps,
        "out_of_scope_stage_request_ids": out_of_scope,
        "manifest": built["manifest"],
        "request_count": len(manifest_ids),
        "transport_identity_count_total": built.get("transport_identity_count_total", 0),
        "duplicate_request_ids": list(duplicate_coverage) + list(duplicate_durable),
        "duplicate_coverage_request_ids": list(duplicate_coverage),
        "duplicate_durable_request_ids": list(duplicate_durable),
        "invariant": (
            "set(durable request IDs) == set(stage-reported request IDs) == "
            "set(coverage manifest request IDs)"
        ),
    }


def load_liquidity_unknown_candidates(
    connection: sqlite3.Connection,
) -> list[dict[str, Any]]:
    """Load exact-pool rows still in LIQUIDITY_UNKNOWN after fresh nomination."""
    rows = connection.execute(
        """
        SELECT mint_identity, pool_address, venue, base_mint, quote_mint,
               last_observed_at, latest_source_provenance_json
        FROM printer_exact_market_states
        WHERE current_state=? AND current_reason=?
        ORDER BY last_observed_at ASC, mint_identity ASC, pool_address ASC
        """,
        (CONTRACT_BLOCKED, REASON_LIQUIDITY_UNKNOWN),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            provenance = json.loads(str(row["latest_source_provenance_json"] or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            provenance = {}
        if not isinstance(provenance, dict):
            provenance = {}
        out.append(
            {
                "mint": str(row["mint_identity"]),
                "pool": str(row["pool_address"]),
                "venue": str(row["venue"] or ""),
                "base_mint": str(row["base_mint"] or row["mint_identity"]),
                "quote_mint": str(row["quote_mint"] or ""),
                "observed_at": str(row["last_observed_at"] or ""),
                "source": str(provenance.get("source") or ""),
                "liquidity_backup_attempted": bool(
                    provenance.get("liquidity_backup_attempted")
                ),
                "provenance": provenance,
            }
        )
    return out


def run_bounded_unknown_liquidity_backup(
    connection: sqlite3.Connection,
    *,
    stage_budget: StageBudget,
    now: str,
    campaign_id: str | None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    request_key_prefix: str = "unknown-liq-backup",
    dexscreener_transport_factory: Any | None = None,
    geckoterminal_transport_factory: Any | None = None,
    max_backups: int | None = None,
) -> dict[str, Any]:
    """One lawful opposite-source exact-pool backup for LIQUIDITY_UNKNOWN rows.

    DexScreener nomination → one GeckoTerminal exact-pool backup.
    GeckoTerminal nomination → one DexScreener exact-pool backup.

    Uses Source Governor + existing stage budget (reconciliation). No direct
    provider bypass, no additional campaign ceiling, no repeated backup loop.
    """
    from printer_v1.contracts.enums import SourceStatus
    from printer_v1.sources.contracts import build_governed_source_request
    from printer_v1.sources.dexscreener import (
        DEXSCREENER_SOURCE_NAME,
        build_dexscreener_adapter,
    )
    from printer_v1.sources.geckoterminal import (
        GECKOTERMINAL_SOURCE_NAME,
        build_geckoterminal_adapter,
    )
    from printer_v1.sources.governed_execution import execute_source_request_with_governor
    from printer_v1.sources.measured_transport import (
        MeasuredTransportError,
        MeasuredTransportLedger,
        record_payload_transports,
    )

    candidates = load_liquidity_unknown_candidates(connection)
    report: dict[str, Any] = {
        "attempts": [],
        "source_request_ids": [],
        "source_response_ids": [],
        "source_failure_ids": [],
        "source_request_coverage": [],
        "source_requests": 0,
        "transport_operations": 0,
        "outcomes": [],
        "above_floor_promoted_to_protocol_due": 0,
        "below_floor": 0,
        "exact_pool_no_match": 0,
        "identity_conflict": 0,
        "still_unknown": 0,
        "skipped_already_attempted": 0,
        "accounting_blocker": False,
        "accounting_blocker_reason": None,
    }
    budget_cap = stage_budget.available("reconciliation")
    limit = budget_cap if max_backups is None else min(int(max_backups), budget_cap)
    attempted = 0
    for cand in candidates:
        if attempted >= limit:
            break
        if cand.get("liquidity_backup_attempted"):
            report["skipped_already_attempted"] += 1
            continue
        mint = cand["mint"]
        pool = cand["pool"]
        source = str(cand.get("source") or "").casefold()
        # Opposite-source backup only. Defaults always supply an explicit
        # transport so ordinary production cannot construct a transportless
        # adapter after campaign mutation (V2-9.8B B2/B3).
        from printer_v1.operator_cli.window_15m_concrete_composition import (
            ConcreteCompositionError,
            require_concrete_adapter,
            require_concrete_transport,
        )
        from printer_v1.sources.dexscreener import (
            build_dexscreener_mint_batch_transport,
        )
        from printer_v1.sources.geckoterminal import (
            build_geckoterminal_token_pools_transport,
        )

        try:
            if source in {"dexscreener", "dex"}:
                backup_source = "geckoterminal"
                request_kind = "candidate_market_batch"
                source_name = GECKOTERMINAL_SOURCE_NAME
                if geckoterminal_transport_factory is not None:
                    transport = require_concrete_transport(
                        f"unknown_liq_backup.gt_factory:{mint[:8]}",
                        geckoterminal_transport_factory(mint),
                    )
                else:
                    transport = require_concrete_transport(
                        f"unknown_liq_backup.gt_default:{mint[:8]}",
                        build_geckoterminal_token_pools_transport(mint),
                    )
                adapter = require_concrete_adapter(
                    f"unknown_liq_backup.gt_adapter:{mint[:8]}",
                    build_geckoterminal_adapter(
                        enabled=True, fixture_transport=transport
                    ),
                    expected_source_name=GECKOTERMINAL_SOURCE_NAME,
                )
                payload = {
                    "request_kind": request_kind,
                    "chain": "solana",
                    "token_mint": mint,
                    "exact_pool": pool,
                }
            else:
                backup_source = "dexscreener"
                request_kind = "candidate_market_batch"
                source_name = DEXSCREENER_SOURCE_NAME
                if dexscreener_transport_factory is not None:
                    transport = require_concrete_transport(
                        f"unknown_liq_backup.dex_factory:{mint[:8]}",
                        dexscreener_transport_factory(mint),
                    )
                else:
                    transport = require_concrete_transport(
                        f"unknown_liq_backup.dex_default:{mint[:8]}",
                        build_dexscreener_mint_batch_transport([mint]),
                    )
                adapter = require_concrete_adapter(
                    f"unknown_liq_backup.dex_adapter:{mint[:8]}",
                    build_dexscreener_adapter(
                        enabled=True, fixture_transport=transport
                    ),
                    expected_source_name=DEXSCREENER_SOURCE_NAME,
                )
                payload = {
                    "request_kind": request_kind,
                    "chain": "solana",
                    "token_mints": [mint],
                    "exact_pool": pool,
                }
        except ConcreteCompositionError as exc:
            report["accounting_blocker"] = True
            report["accounting_blocker_reason"] = (
                f"UNKNOWN_LIQUIDITY_BACKUP_COMPOSITION_BLOCKED:{exc}"
            )
            report["outcomes"].append(
                {
                    "mint": mint,
                    "pool": pool,
                    "outcome": "COMPOSITION_BLOCKED",
                    "reason": str(exc),
                }
            )
            break
        if not stage_budget.available("reconciliation"):
            break
        stage_budget.consume("reconciliation", 1)
        attempted += 1
        request = build_governed_source_request(
            source_name,
            request_kind,
            request_key=f"{request_key_prefix}-{backup_source}-{mint[:8]}-{pool[:8]}",
            tracking_priority=0,
            payload=payload,
        )
        stage_ledger = MeasuredTransportLedger(
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
        )
        execution = execute_source_request_with_governor(
            connection,
            request,
            adapter,
            recent_request_count=report["source_requests"],
        )
        report["source_requests"] += 1
        rid = int(execution.request_record.id)
        report["source_request_ids"].append(rid)
        if execution.response_record is not None:
            report["source_response_ids"].append(int(execution.response_record.id))
        if execution.failure_record is not None:
            report["source_failure_ids"].append(int(execution.failure_record.id))
        result = execution.normalized_result
        payload_norm = result.normalized_payload or {}
        transport_identity_count = 0
        measurement_failed = False
        if isinstance(payload_norm, Mapping):
            try:
                before = stage_ledger.source_transport_operations
                record_payload_transports(
                    stage_ledger,
                    payload_norm,
                    default_stage="UNKNOWN_LIQUIDITY_BACKUP",
                )
                transport_identity_count = int(
                    stage_ledger.source_transport_operations - before
                )
                report["transport_operations"] += transport_identity_count
            except MeasuredTransportError as exc:
                measurement_failed = True
                report["accounting_blocker"] = True
                report["accounting_blocker_reason"] = (
                    f"TRANSPORT_IDENTITY_MEASUREMENT_FAILED:{exc}"
                )
                transport_identity_count = 0
        pairs = (
            list(payload_norm.get("pairs") or ())
            if isinstance(payload_norm, Mapping)
            else []
        )
        backup_keys = _transport_identity_keys_from_ledger_delta(
            stage_ledger,
            before_count=max(
                0, len(list(getattr(stage_ledger, "transports", ()) or ()))
                - int(transport_identity_count)
            ),
        )
        coverage = {
            "source_request_id": rid,
            "source_name": source_name,
            "request_kind": request_kind,
            "logical_stage_id": (
                f"{campaign_id}|{run_id}|{cycle_id}|UNKNOWN_LIQUIDITY_BACKUP|{attempted}"
                if campaign_id and run_id and cycle_id
                else f"UNKNOWN_LIQUIDITY_BACKUP|{attempted}"
            ),
            "transport_identity_count": transport_identity_count,
            "transport_identity_keys": backup_keys,
            "normalized_member_count": len(pairs),
            "terminal_status": "COMPLETED",
        }
        resolution = resolve_dexscreener_mint_batch([mint], pairs, observed_at=now)
        exact_rows = [
            row for row in resolution.by_mint.get(mint, ()) if row.pool == pool
        ]
        shared_fail = bool(
            result.failure_type
            or result.source_status != SourceStatus.COMPLETE
            or measurement_failed
        )
        outcome_label = "LIQUIDITY_UNKNOWN"
        liquidity_usd = None
        quote_mint = str(cand.get("quote_mint") or "")
        venue = str(cand.get("venue") or "")
        base_mint = str(cand.get("base_mint") or mint)
        if shared_fail:
            coverage["terminal_status"] = "BLOCKED"
            outcome_label = "LIQUIDITY_UNKNOWN"
            report["still_unknown"] += 1
            # Measurement failure: preserve request ID, do not invent transport,
            # do not promote to protocol-due liquidity.
            if measurement_failed:
                exact_rows = []
        elif not exact_rows:
            outcome_label = "EXACT_POOL_NO_MATCH"
            report["exact_pool_no_match"] += 1
            record_exact_market_transition(
                connection,
                ExactMarketObservation(
                    network=NETWORK,
                    mint=mint,
                    pool=pool,
                    token_program="UNRESOLVED_TOKEN_PROGRAM",
                    pool_program="UNRESOLVED_POOL_PROGRAM",
                    base_mint=base_mint,
                    quote_mint=quote_mint or "UNKNOWN_QUOTE_MINT",
                    venue=venue or "UNKNOWN_VENUE",
                    state=EXACT_POOL_NO_MATCH,
                    reason="LAWFUL_BACKUP_EXACT_POOL_NO_MATCH",
                    observed_at=now,
                    next_lawful_action_at=now,
                    source_provenance={
                        "source": backup_source,
                        "request_id": rid,
                        "liquidity_backup_attempted": True,
                        "backup_of_source": source,
                        "stage": "unknown_liquidity_backup",
                    },
                    contract_version="UNKNOWN_LIQUIDITY_BACKUP_V1",
                ),
                now=now,
            )
        else:
            row = exact_rows[0]
            if row.base_mint and row.base_mint != mint:
                outcome_label = "IDENTITY_CONFLICT"
                report["identity_conflict"] += 1
                record_exact_market_transition(
                    connection,
                    ExactMarketObservation(
                        network=NETWORK,
                        mint=mint,
                        pool=pool,
                        token_program="UNRESOLVED_TOKEN_PROGRAM",
                        pool_program="UNRESOLVED_POOL_PROGRAM",
                        base_mint=mint,
                        quote_mint=str(row.quote_mint or quote_mint or "UNKNOWN_QUOTE_MINT"),
                        venue=str(row.venue or venue or "UNKNOWN_VENUE"),
                        state=IDENTITY_CONFLICT,
                        reason="BACKUP_BASE_MINT_MISMATCH",
                        observed_at=now,
                        next_lawful_action_at=now,
                        source_provenance={
                            "source": backup_source,
                            "request_id": rid,
                            "liquidity_backup_attempted": True,
                            "backup_of_source": source,
                            "stage": "unknown_liquidity_backup",
                        },
                        contract_version="UNKNOWN_LIQUIDITY_BACKUP_V1",
                    ),
                    now=now,
                )
            else:
                liquidity_usd = _coerce_liquidity_usd(row.liquidity_usd)
                quote_mint = str(row.quote_mint or quote_mint or "")
                venue = str(row.venue or venue or "")
                state, reason = classify_exact_pool_liquidity_prefilter(
                    liquidity_usd=liquidity_usd
                )
                if reason == REASON_ABOVE_FLOOR_NOMINATION:
                    outcome_label = "ABOVE_FLOOR_NOMINATION"
                    report["above_floor_promoted_to_protocol_due"] += 1
                elif reason == REASON_BELOW_FLOOR:
                    outcome_label = "BELOW_LIQUIDITY_FLOOR"
                    report["below_floor"] += 1
                else:
                    outcome_label = "LIQUIDITY_UNKNOWN"
                    report["still_unknown"] += 1
                observed_at = now
                item_expires = resolve_liquidity_evidence_expiry(
                    observed_at=observed_at,
                    explicit_expiry=None,
                    ingestion_now=now,
                )
                provenance = {
                    "source": backup_source,
                    "request_id": rid,
                    "response_id": (
                        None
                        if execution.response_record is None
                        else int(execution.response_record.id)
                    ),
                    "liquidity_usd": liquidity_usd,
                    "liquidity_observed_at": observed_at,
                    "liquidity_evidence_expires_at": item_expires,
                    "liquidity_backup_attempted": True,
                    "backup_of_source": source,
                    "stage": "unknown_liquidity_backup",
                    "prefilter_outcome": outcome_label,
                    "provenance_kind": "MARKET_SOURCE_OBSERVATION",
                    "market_evidence_contract_version": "UNKNOWN_LIQUIDITY_BACKUP_V1",
                }
                evidence = {
                    "base_mint": mint,
                    "quote_mint": quote_mint,
                    "venue": venue,
                    "pool": pool,
                    "liquidity_usd": liquidity_usd,
                    "liquidity_observed_at": observed_at,
                    "liquidity_evidence_expires_at": item_expires,
                    "market_evidence_contract_version": "UNKNOWN_LIQUIDITY_BACKUP_V1",
                    "prefilter_outcome": outcome_label,
                    "source": backup_source,
                    "request_id": rid,
                    "liquidity_backup_attempted": True,
                    "backup_of_source": source,
                }
                record_exact_market_transition(
                    connection,
                    ExactMarketObservation(
                        network=NETWORK,
                        mint=mint,
                        pool=pool,
                        token_program="UNRESOLVED_TOKEN_PROGRAM",
                        pool_program="UNRESOLVED_POOL_PROGRAM",
                        base_mint=mint,
                        quote_mint=quote_mint or "UNKNOWN_QUOTE_MINT",
                        venue=venue or "UNKNOWN_VENUE",
                        state=state,
                        reason=reason,
                        observed_at=observed_at,
                        next_lawful_action_at=now,
                        source_provenance=provenance,
                        contract_version="UNKNOWN_LIQUIDITY_BACKUP_V1",
                    ),
                    now=now,
                )
                upsert_reserve_layer(
                    connection,
                    network=NETWORK,
                    mint=mint,
                    pool=pool,
                    layer=BROAD_NOMINATED,
                    reserve_state="ACTIVE",
                    reason=reason,
                    observed_at=observed_at,
                    next_lawful_action_at=now,
                    evidence_expires_at=item_expires if liquidity_usd is not None else None,
                    source_provenance=provenance,
                    evidence=evidence,
                    campaign_id=campaign_id,
                )
                if reason == REASON_ABOVE_FLOOR_NOMINATION:
                    upsert_reserve_layer(
                        connection,
                        network=NETWORK,
                        mint=mint,
                        pool=pool,
                        layer=ABOVE_FLOOR_NOMINATED,
                        reserve_state="ACTIVE",
                        reason=reason,
                        observed_at=observed_at,
                        next_lawful_action_at=now,
                        evidence_expires_at=item_expires,
                        source_provenance=provenance,
                        evidence=evidence,
                        campaign_id=campaign_id,
                    )
                if outcome_label == "LIQUIDITY_UNKNOWN":
                    # Still unknown after one backup: mark attempted so no loop.
                    # State already LIQUIDITY_UNKNOWN via classify.
                    pass
        # Mark backup attempted even when still unknown / shared fail so a
        # second attempt cannot loop.
        if outcome_label == "LIQUIDITY_UNKNOWN" and (
            shared_fail or not exact_rows or liquidity_usd is None
        ):
            # Refresh provenance flag on existing state when no transition above
            # already wrote liquidity_backup_attempted (shared_fail path).
            if shared_fail:
                record_exact_market_transition(
                    connection,
                    ExactMarketObservation(
                        network=NETWORK,
                        mint=mint,
                        pool=pool,
                        token_program="UNRESOLVED_TOKEN_PROGRAM",
                        pool_program="UNRESOLVED_POOL_PROGRAM",
                        base_mint=base_mint,
                        quote_mint=quote_mint or "UNKNOWN_QUOTE_MINT",
                        venue=venue or "UNKNOWN_VENUE",
                        state=CONTRACT_BLOCKED,
                        reason=REASON_LIQUIDITY_UNKNOWN,
                        observed_at=now,
                        next_lawful_action_at=now,
                        source_provenance={
                            "source": backup_source,
                            "request_id": rid,
                            "liquidity_backup_attempted": True,
                            "backup_of_source": source,
                            "stage": "unknown_liquidity_backup",
                            "backup_result": "STILL_UNKNOWN_AFTER_BACKUP",
                        },
                        contract_version="UNKNOWN_LIQUIDITY_BACKUP_V1",
                    ),
                    now=now,
                )
        report["source_request_coverage"].append(coverage)
        report["attempts"].append(
            {
                "mint": mint,
                "pool": pool,
                "original_source": source,
                "backup_source": backup_source,
                "outcome": outcome_label,
                "liquidity_usd": liquidity_usd,
                "source_request_id": rid,
            }
        )
        report["outcomes"].append(
            {
                "mint": mint,
                "pool": pool,
                "outcome": outcome_label,
                "liquidity_backup_attempted": True,
            }
        )
    connection.commit()
    return report


def observation_reserve_depth_status(observation_eligible_count: int) -> dict[str, Any]:
    """Report freeze-depth and surplus-target coverage without expanding budgets."""
    count = int(observation_eligible_count)
    return {
        "observation_eligible_count": count,
        "minimum_freeze_depth": MINIMUM_FREEZE_DEPTH,
        "observation_surplus_target": OBSERVATION_SURPLUS_TARGET,
        "freeze_depth_met": count >= MINIMUM_FREEZE_DEPTH,
        "surplus_target_met": count >= OBSERVATION_SURPLUS_TARGET,
        "coverage_blocker": count < MINIMUM_FREEZE_DEPTH,
        "surplus_status": (
            "SURPLUS_TARGET_MET"
            if count >= OBSERVATION_SURPLUS_TARGET
            else "SURPLUS_TARGET_NOT_MET"
            if count >= MINIMUM_FREEZE_DEPTH
            else "INSUFFICIENT_OBSERVATION_COVERAGE"
        ),
    }


__all__ = [
    "ABOVE_FLOOR_NOMINATED",
    "BROAD_NOMINATED",
    "MARKET_READY",
    "MEMORY_OBSERVATION_ELIGIBLE",
    "FULLY_ELIGIBLE",
    "CURRENT_VISIBLE",
    "BELOW_LIQUIDITY_FLOOR",
    "EXACT_POOL_NO_MATCH",
    "POOL_RECONCILIATION_DUE",
    "SAME_POOL_REOBSERVED",
    "NEW_POOL_PENDING_PROOF",
    "CURRENT_POOL_CONFIRMED",
    "NO_SUPPORTED_CURRENT_POOL",
    "SOURCE_UNAVAILABLE",
    "IDENTITY_CONFLICT",
    "UNSUPPORTED_VENUE",
    "CONTRACT_BLOCKED",
    "MINIMUM_FREEZE_DEPTH",
    "OBSERVATION_SURPLUS_TARGET",
    "SELECTION_FLOOR_USD",
    "REASON_ABOVE_FLOOR_NOMINATION",
    "REASON_LIQUIDITY_UNKNOWN",
    "REASON_BELOW_FLOOR",
    "PROTOCOL_DUE_REASONS",
    "CandidateObservation",
    "ExactMarketObservation",
    "FrozenEligibleReserve",
    "MergedMintObservations",
    "MintBatchResolution",
    "PoolReconciliation",
    "StageBudget",
    "CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH",
    "PRINTER_V1_CAMPAIGN_SOURCE_REQUEST_SCOPE_V1",
    "LEGACY_STATIC_REQUEST_KEY_ROOT",
    "CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED",
    "CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID",
    "CAMPAIGN_SOURCE_REQUEST_SCOPE_IDENTITY_MISMATCH",
    "CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH",
    "LEGACY_STATIC_REQUEST_SCOPE_BLOCKED_OPERATIONALLY",
    "CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS",
    "DURABLE_REQUEST_NOT_STAGE_REPORTED",
    "DURABLE_REQUEST_NOT_MANIFESTED",
    "STAGE_REQUEST_NOT_DURABLE",
    "STAGE_REQUEST_NOT_MANIFESTED",
    "MANIFEST_REQUEST_NOT_DURABLE",
    "DUPLICATE_COVERAGE_REQUEST_ID",
    "DUPLICATE_DURABLE_REQUEST_ID",
    "STAGE_OWNERSHIP_GAP",
    "STAGE_ACCOUNTING_BLOCKER",
    "CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE",
    "MULTIPLE_SOURCE_REQUEST_RECONCILIATION_DEFECTS",
    "CampaignSourceRequestScope",
    "assemble_and_reconcile_campaign_source_requests",
    "build_campaign_source_request_manifest",
    "build_campaign_source_request_scope",
    "build_source_request_coverage_manifest",
    "classify_campaign_source_request_reconciliation_defects",
    "classify_exact_pool_liquidity_prefilter",
    "collect_stage_accounting_blockers",
    "collect_stage_reported_request_ids",
    "collect_stage_source_request_coverage",
    "derive_campaign_source_request_key_root",
    "format_source_request_reconciliation_detail",
    "freeze_eligible_reserve",
    "inspect_preexisting_source_request_scope_collision",
    "interleave_candidate_observations",
    "load_durable_campaign_source_request_ids",
    "load_exact_market_states",
    "load_liquidity_unknown_candidates",
    "load_prefix_lookup_request_ids",
    "load_retained_market_evidence",
    "load_scoped_stage_request_membership",
    "merge_candidate_observations",
    "merge_protocol_confirmation_reports",
    "observation_reserve_depth_status",
    "order_canonical_inventory_fairly",
    "process_protocol_confirmation_queue",
    "promote_confirmed_with_retained_liquidity",
    "record_exact_market_transition",
    "record_fresh_pool_nominations",
    "reconcile_campaign_source_requests",
    "request_key_belongs_to_root",
    "validate_campaign_source_request_scope",
    "validate_permanent_operational_request_prefixes",
    "reconcile_pool_identity",
    "resolve_dexscreener_mint_batch",
    "resolve_liquidity_evidence_expiry",
    "run_bounded_unknown_liquidity_backup",
    "run_dexscreener_batch_market_resolution",
    "run_geckoterminal_fresh_nomination",
    "should_poll_exact_pool",
    "union_market_revalidation_candidates",
    "upsert_reserve_layer",
    "mint_set_digest",
    "parse_mint_market_batch_stage_sequence",
    "next_mint_market_batch_stage_sequence",
    "build_mint_market_batch_request_key",
    "build_mint_market_batch_logical_identity",
]

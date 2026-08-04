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
MARKET_READY = "MARKET_READY"
FULLY_ELIGIBLE = "FULLY_ELIGIBLE"
RESERVE_LAYERS = frozenset({BROAD_NOMINATED, MARKET_READY, FULLY_ELIGIBLE})

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
) -> dict[str, Any]:
    """Resolve due graduated inventory by exact mint in governed batches.

    This is the canonical owner's market stage, not another discovery engine.
    Provider order and liquidity magnitude never choose a pool. A historical
    exact pool is admitted only when that exact identity is visible and clears
    the existing categorical $3,000 floor. Other returned pools are preserved as
    pending reconciliation and can never silently replace it.
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
        "calls_by_stage": {"market_batching": 0, "reconciliation": 0},
        "provider_failures": 0,
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
        report["source_request_ids"].append(int(execution.request_record.id))
        if execution.response_record is not None:
            report["source_response_ids"].append(int(execution.response_record.id))
        if execution.failure_record is not None:
            report["source_failure_ids"].append(int(execution.failure_record.id))

        payload = result.normalized_payload or {}
        if isinstance(payload, Mapping):
            try:
                record_payload_transports(
                    measured_ledger,
                    payload,
                    default_stage="MINT_MARKET_BATCH",
                )
            except Exception:
                # Declared transport identities only; never infer them from a
                # request row or fabricate them for fixtures.
                pass
        pairs = list(payload.get("pairs") or ()) if isinstance(payload, Mapping) else []
        resolution = resolve_dexscreener_mint_batch(mints, pairs, observed_at=now)
        for mint, pool_rows in resolution.by_mint.items():
            report["exact_pools_by_mint"][mint] = [row.pool for row in pool_rows]
        report["local_zero_source_exclusions"].extend(resolution.local_exclusions)
        failed = result.source_status != SourceStatus.COMPLETE or bool(result.failure_type)
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
                report["source_request_ids"].append(int(gt_execution.request_record.id))
                if gt_execution.response_record is not None:
                    report["source_response_ids"].append(int(gt_execution.response_record.id))
                if gt_execution.failure_record is not None:
                    report["source_failure_ids"].append(int(gt_execution.failure_record.id))
                gt_payload = gt_result.normalized_payload or {}
                if isinstance(gt_payload, Mapping):
                    try:
                        record_payload_transports(
                            measured_ledger,
                            gt_payload,
                            default_stage="MINT_MARKET_BATCH",
                        )
                    except Exception:
                        pass
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
                gt_resolution = resolve_dexscreener_mint_batch(
                    [mint], gt_pairs, observed_at=now
                )
                fallback[mint] = {
                    "failed": gt_failed,
                    "failure_type": gt_result.failure_type,
                    "rows": gt_resolution.by_mint.get(mint, ()),
                    "request_id": int(gt_execution.request_record.id),
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
                stage_sequence=1,
            ),
            stage_kind="MINT_MARKET_BATCH",
            stage_sequence=1,
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
) -> dict[str, Any]:
    """Merge fresh aggregator pools into the canonical broad reserve only."""
    accepted: list[dict[str, str]] = []
    exclusions: list[dict[str, str]] = []
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
            exclusions.append({"mint": mint, "pool": pool, "reason": "INCOMPLETE_ORIENTATION"})
            continue
        if mint in SOLANA_INFRASTRUCTURE_MINTS:
            exclusions.append({"mint": mint, "pool": pool, "reason": "INFRASTRUCTURE_MINT"})
            continue
        provenance = {"source": source, "request_id": int(request_id)}
        reason = "FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF"
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
                state=CONTRACT_BLOCKED,
                reason=reason,
                observed_at=now,
                next_lawful_action_at=now,
                source_provenance=provenance,
                contract_version=(
                    "GECKOTERMINAL_KEYLESS_V2_2026_08_04"
                    if source == "geckoterminal"
                    else "DEXSCREENER_TOKENS_V1_2026_08_04"
                ),
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
            observed_at=now,
            next_lawful_action_at=now,
            evidence_expires_at=None,
            source_provenance=provenance,
            evidence={"base_mint": base, "quote_mint": quote, "venue": venue},
            campaign_id=campaign_id,
        )
        accepted.append({"mint": mint, "pool": pool, "source": source})
    connection.commit()
    return {"accepted": accepted, "exclusions": exclusions}


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
    if isinstance(payload, Mapping):
        try:
            record_payload_transports(ledger, payload, default_stage="FRESH_POOL_NOMINATION")
        except Exception:
            pass
    observations = []
    for item in payload.get("pairs", ()) if isinstance(payload, Mapping) else ():
        if not isinstance(item, Mapping):
            continue
        base = item.get("baseToken") if isinstance(item.get("baseToken"), Mapping) else {}
        quote = item.get("quoteToken") if isinstance(item.get("quoteToken"), Mapping) else {}
        observations.append(
            {
                "mint": item.get("base_mint") or base.get("address"),
                "pool": item.get("pairAddress") or item.get("pair_address"),
                "base_mint": item.get("base_mint") or base.get("address"),
                "quote_mint": item.get("quote_mint") or quote.get("address"),
                "venue": item.get("dex_id") or item.get("dex"),
            }
        )
    merge = record_fresh_pool_nominations(
        connection,
        observations=observations,
        source=GECKOTERMINAL_SOURCE_NAME,
        request_id=int(execution.request_record.id),
        now=now,
        campaign_id=campaign_id,
    ) if result.source_status == SourceStatus.COMPLETE and not result.failure_type else {
        "accepted": [], "exclusions": []
    }
    sealed = None
    if stage_evidence_sink is not None:
        if not all(str(value or "").strip() for value in (campaign_id, run_id, cycle_id)):
            raise ValueError("FRESH_POOL_NOMINATION_STAGE_REQUIRES_CAMPAIGN_RUN_CYCLE")
        sealed = seal_campaign_stage_evidence(
            ledger=ledger,
            stage_id=build_campaign_stage_id(
                campaign_id=str(campaign_id), run_id=str(run_id), cycle_id=str(cycle_id),
                stage_kind="FRESH_POOL_NOMINATION", stage_sequence=1,
            ),
            stage_kind="FRESH_POOL_NOMINATION",
            stage_sequence=1,
            stage_terminal_status=(
                "COMPLETED"
                if result.source_status == SourceStatus.COMPLETE and not result.failure_type
                else "BLOCKED"
            ),
            stage_first_terminal_cause=result.failure_type,
            campaign_id=str(campaign_id), run_id=str(run_id), cycle_id=str(cycle_id),
            sealed_at=now,
        )
        stage_evidence_sink(sealed)
    return {
        "status": getattr(result.source_status, "name", str(result.source_status)),
        "failure_type": result.failure_type,
        "request_id": int(execution.request_record.id),
        "response_id": None if execution.response_record is None else int(execution.response_record.id),
        "failure_id": None if execution.failure_record is None else int(execution.failure_record.id),
        "source_requests": 1,
        "nominations": merge["accepted"],
        "local_exclusions": merge["exclusions"],
        "sealed_stage_evidence": sealed,
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
    """Freeze current fully eligible rows, select two neutrally, retain spares."""
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
    for raw in candidates:
        item = dict(raw)
        mint = str(item.get("mint") or item.get("mint_identity") or "")
        pool = str(item.get("pool") or item.get("pair_address") or "")
        expiry = item.get("evidence_expires_at")
        if not item.get("fully_eligible") or not mint or not pool:
            continue
        if expiry is None or _parse_iso(str(expiry)) <= instant:
            stale.append(item)
            continue
        if mint in seen_mints or pool in seen_pools:
            continue
        seen_mints.add(mint)
        seen_pools.add(pool)
        item.setdefault("market_identity", f"solana-mainnet:eligible:{pool}")
        item.setdefault("provenance", "PERSISTED_GRADUATED")
        fresh.append(item)

    selection_candidates = [candidate_from_front_door_mapping(item) for item in fresh]
    authority = select_two_candidates(selection_candidates, cycle_seed=cycle_seed)
    selected_mints = {item.mint for item in authority.selected}
    ordered = deterministic_candidate_order(selection_candidates, cycle_seed=cycle_seed)
    by_mint = {str(item["mint"]): item for item in fresh}
    selected = tuple(by_mint[item.mint] for item in authority.selected)
    alternates = tuple(
        by_mint[item.mint] for item in ordered if item.mint not in selected_mints
    )
    return FrozenEligibleReserve(
        selected=selected,
        alternates=alternates,
        rejected_stale=tuple(sorted(stale, key=lambda item: str(item.get("mint") or ""))),
        frozen_at=at,
        selection_authority=authority.as_dict(),
    )


def process_protocol_confirmation_queue(
    connection: sqlite3.Connection,
    *,
    stage_budget: StageBudget,
    now: str,
    campaign_id: str | None = None,
    max_confirmations: int | None = None,
) -> dict[str, Any]:
    """Process PROTOCOL_CONFIRMATION_DUE exact-market identities under stage capacity.

    Fresh aggregator nominations enter ``CONTRACT_BLOCKED`` with reason
    ``FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF``. This owner
    spends protocol_confirmation capacity deterministically (oldest observed,
    then mint+pool) and:

    * leaves unsupported venues (e.g. Meteora) blocked as ``UNSUPPORTED_VENUE``;
    * never auto-accepts alternate ``pump-fun`` label pools as historical substitutes;
    * for supported Pump-family venues without an account transport, records a
      bounded confirmation attempt and retains protocol-due state (fail-closed).

    Does not contact providers. Account-batch confirmation uses only already
    governed local projection facts in this offline-safe path.
    """
    outcomes: list[dict[str, Any]] = []
    remaining_due: list[dict[str, str]] = []
    source_requests = 0
    limit = (
        stage_budget.available("protocol_confirmation")
        if max_confirmations is None
        else min(int(max_confirmations), stage_budget.available("protocol_confirmation"))
    )
    if limit <= 0 or stage_budget.is_sealed("protocol_confirmation"):
        rows = connection.execute(
            """
            SELECT mint_identity, pool_address, venue, current_reason, last_observed_at
            FROM printer_exact_market_states
            WHERE current_state=? AND current_reason=?
            ORDER BY last_observed_at ASC, mint_identity ASC, pool_address ASC
            """,
            (CONTRACT_BLOCKED, "FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF"),
        ).fetchall()
        for row in rows:
            remaining_due.append(
                {
                    "mint": str(row["mint_identity"]),
                    "pool": str(row["pool_address"]),
                    "venue": str(row["venue"] or ""),
                }
            )
        return {
            "outcomes": outcomes,
            "remaining_due": remaining_due,
            "source_requests": 0,
            "attempts": 0,
        }

    rows = connection.execute(
        """
        SELECT network, mint_identity, pool_address, venue, base_mint, quote_mint,
               pool_program_id, token_program_id, current_reason, last_observed_at,
               latest_source_provenance_json
        FROM printer_exact_market_states
        WHERE current_state=? AND current_reason=?
        ORDER BY last_observed_at ASC, mint_identity ASC, pool_address ASC
        """,
        (CONTRACT_BLOCKED, "FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF"),
    ).fetchall()
    attempts = 0
    for row in rows:
        mint = str(row["mint_identity"])
        pool = str(row["pool_address"])
        venue = str(row["venue"] or "")
        venue_key = venue.casefold()
        if attempts >= limit:
            remaining_due.append({"mint": mint, "pool": pool, "venue": venue})
            continue
        if stage_budget.available("protocol_confirmation") < 1:
            remaining_due.append({"mint": mint, "pool": pool, "venue": venue})
            continue
        stage_budget.consume("protocol_confirmation", 1)
        attempts += 1
        source_requests += 1
        # Unsupported venues never enter Pump protocol paths.
        if venue_key not in SUPPORTED_PUMPSWAP_PROVIDER_VENUES and venue_key not in {
            "pump-fun",
            "pumpswap",
            "pumpfun",
            "pump-amm",
        }:
            record_exact_market_transition(
                connection,
                ExactMarketObservation(
                    network=str(row["network"] or NETWORK),
                    mint=mint,
                    pool=pool,
                    token_program=str(row["token_program_id"] or "UNRESOLVED_TOKEN_PROGRAM"),
                    pool_program=str(row["pool_program_id"] or "UNRESOLVED_POOL_PROGRAM"),
                    base_mint=str(row["base_mint"] or mint),
                    quote_mint=str(row["quote_mint"] or "UNKNOWN_QUOTE_MINT"),
                    venue=venue or "UNKNOWN_VENUE",
                    state=UNSUPPORTED_VENUE,
                    reason="PROTOCOL_UNSUPPORTED_VENUE",
                    observed_at=now,
                    next_lawful_action_at=None,
                    source_provenance={
                        "stage": "protocol_confirmation",
                        "campaign_id": campaign_id,
                    },
                    contract_version="PROTOCOL_CONFIRMATION_V1_2026_08_04",
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
                }
            )
            continue
        # Supported Pump-family: without a governed account batch transport in
        # this offline path, retain protocol-due state after a counted attempt.
        # Never invent CURRENT_POOL_CONFIRMED from aggregator labels alone.
        outcomes.append(
            {
                "mint": mint,
                "pool": pool,
                "venue": venue,
                "outcome": "PROTOCOL_CONFIRMATION_ATTEMPTED_STILL_DUE",
                "reason": "FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF",
            }
        )
        remaining_due.append({"mint": mint, "pool": pool, "venue": venue})
    connection.commit()
    return {
        "outcomes": outcomes,
        "remaining_due": remaining_due,
        "source_requests": source_requests,
        "attempts": attempts,
    }


__all__ = [
    "BROAD_NOMINATED",
    "MARKET_READY",
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
    "CandidateObservation",
    "ExactMarketObservation",
    "FrozenEligibleReserve",
    "MergedMintObservations",
    "MintBatchResolution",
    "PoolReconciliation",
    "StageBudget",
    "freeze_eligible_reserve",
    "interleave_candidate_observations",
    "load_exact_market_states",
    "merge_candidate_observations",
    "order_canonical_inventory_fairly",
    "process_protocol_confirmation_queue",
    "record_exact_market_transition",
    "record_fresh_pool_nominations",
    "reconcile_pool_identity",
    "resolve_dexscreener_mint_batch",
    "run_dexscreener_batch_market_resolution",
    "run_geckoterminal_fresh_nomination",
    "should_poll_exact_pool",
    "upsert_reserve_layer",
]

"""V2-9.7E.43 $3K graduated discovery and selection front door.

Adds the market-performance front door on top of the E.41 graduation-only law and
the E.42 direct-migration graduated supply. A confirmed graduated Pump.fun
candidate may enter **active selection** only once a governed, fresh, exact-pool
DexScreener observation proves ``liquidity_usd >= 3000`` for the exact Solana mint
and the exact confirmed PumpSwap pool. Below-floor and unproven-liquidity
candidates remain durable discovery evidence but never consume a tracking slot.

``$3,000`` is the only numeric market-performance threshold. No volume,
transaction, age, holder, trend, boost, score, confidence or weighting gate is
introduced. The floor is a categorical pass/fail; liquidity magnitude above the
floor never affects selection order.

This module composes existing owners and adds no duplicate discovery, verifier,
registry, selector or handoff:

    export_graduated_candidates (registry, migration 040)
      -> exact-pool DexScreener liquidity enrichment (governed pair_market_snapshot)
      -> $3,000 floor + identity/source-quality/STNP/cooldown gates
      -> truthful LATEST_GRADUATED / PERSISTED_GRADUATED provenance
      -> frozen categorical two-slot selection (one latest + one persisted)
      -> deterministic selected-pair readiness (atomic-handoff compatibility only)

No FULL_PILOT, scheduler, snapshot, lifecycle, memory, retrieval, decision,
position, trade, audit or PnL work is performed. No tracking is enqueued.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from printer_v1.contracts.enums import SourceStatus
from printer_v1.discovery.combined_executor import (
    PUMPSWAP_MARKET_PREFIX,
    _fisher_yates,
    _token_identity,
)

# V2-9.7E.46B combined-pool (partition-flexible) selection domain and terminals.
# A single deterministic seeded-uniform order is taken over the *union* of both
# provenance partitions so any lawful two-token composition (LATEST+LATEST,
# LATEST+PERSISTED, PERSISTED+PERSISTED) can be selected. Provenance stays a
# truthful attribute of each candidate; it is never a compulsory pair quota and
# never a score/rank/weight.
COMBINED_TWO_TOKEN_CHANNEL = "COMBINED_TWO_TOKEN"

# Selection terminals distinguishing healthy exhaustion from source outage.
SELECTION_TWO_TOKEN_READY = "SELECTION_TWO_TOKEN_READY"
SELECTION_HOLDER_SOURCE_BLOCKED = "SELECTION_HOLDER_SOURCE_BLOCKED"
SELECTION_CAPACITY_EXHAUSTED = "DISCOVERY_SELECTION_CAPACITY_EXHAUSTED"
SELECTION_COVERAGE_INSUFFICIENT = "DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT"

# Holder-fact reasons that mean the source/network could not deliver evidence
# (transport/auth/rate-limit/stale/collection failure) rather than a truthful
# holder disqualification (concentration/target-mismatch/conflict). A source
# outage must never be silently attributed to insufficient market coverage.
HOLDER_SOURCE_UNAVAILABLE_PREFIXES = (
    "HOLDER_EVIDENCE_UNAVAILABLE",
    "HOLDER_EVIDENCE_FAILED",
    "HOLDER_EVIDENCE_STALE",
    "HOLDER_EVIDENCE_COLLECTION_FAILED",
    "MISSING_CRITICAL_DATA",
)
from printer_v1.discovery.selection_batch import (
    check_pair_selection_cooldown,
    check_token_selection_cooldown,
)
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.dexscreener import (
    DEXSCREENER_SOURCE_NAME,
    build_dexscreener_adapter,
    build_dexscreener_pair_snapshot_transport,
)
from printer_v1.sources.governed_execution import execute_source_request_with_governor
from printer_v1.sources.pumpswap_graduated_registry import (
    GRADUATED_LIFECYCLE,
    LATEST_GRADUATED_CHANNEL,
    PERSISTED_GRADUATED_CHANNEL,
    PUMPSWAP_VENUE,
    export_graduated_candidates,
)

# The single numeric market-performance threshold. USD.
SELECTION_FLOOR_USD = 3000.0

# Governed exact-pair market snapshot request kind (adopted; not token-level).
LIQUIDITY_REQUEST_KIND = "pair_market_snapshot"

# Liquidity classification statuses.
LIQUIDITY_PROVEN = "LIQUIDITY_PROVEN"
LIQUIDITY_BELOW_SELECTION_FLOOR = "LIQUIDITY_BELOW_SELECTION_FLOOR"
LIQUIDITY_UNPROVEN = "LIQUIDITY_UNPROVEN"

# Candidate-local evidence outcome categories. They explain why a current
# exact-pool attempt passed or failed without changing the adopted three-state
# liquidity admission contract above.
LIQUIDITY_EXACT_ABOVE_FLOOR = "LIQUIDITY_EXACT_ABOVE_FLOOR"
LIQUIDITY_EXACT_BELOW_FLOOR = "LIQUIDITY_EXACT_BELOW_FLOOR"
LIQUIDITY_SOURCE_UNAVAILABLE = "LIQUIDITY_SOURCE_UNAVAILABLE"
LIQUIDITY_SOURCE_RATE_LIMITED_OR_STALE = "LIQUIDITY_SOURCE_RATE_LIMITED_OR_STALE"
LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL = "LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL"
LIQUIDITY_EXACT_PAIR_UNAVAILABLE_OR_MISMATCH = (
    "LIQUIDITY_EXACT_PAIR_UNAVAILABLE_OR_MISMATCH"
)
LIQUIDITY_HISTORICAL_BELOW_FLOOR_COOLDOWN = (
    "LIQUIDITY_HISTORICAL_BELOW_FLOOR_COOLDOWN"
)
LIQUIDITY_IDENTITY_UNCONFIRMED = "LIQUIDITY_IDENTITY_UNCONFIRMED"
# Front-door skip reason when durable below-floor cooldown is still active.
# No DexScreener call is made; last measured liquidity is retained for reporting.
LIQUIDITY_BELOW_SELECTION_FLOOR_COOLDOWN = "LIQUIDITY_BELOW_SELECTION_FLOOR_COOLDOWN"
# V2-9.8B.6: one hour categorical below-floor market revalidation cooldown.
# Not a rank/score. Fresh exact-pool evidence is still required after expiry.
BELOW_FLOOR_MARKET_COOLDOWN_SECONDS = 3600

# Forbidden-capability tables. This lane must never write any of these; the report
# proves each stayed at zero (integrity guard, not just an assertion of intent).
_FORBIDDEN_TABLES = (
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trades",
    "printer_paper_trade_audit",
    "printer_episode_memory",
    "printer_memory_retrieval",
    "printer_memory_factory_runs",
)


class GraduatedFrontDoorError(RuntimeError):
    """Fail-closed graduated selection front-door fault."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}: {detail}")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class LiquidityEvidence:
    """Result of one governed exact-pool liquidity enrichment.

    ``status`` is one of LIQUIDITY_PROVEN / LIQUIDITY_BELOW_SELECTION_FLOOR /
    LIQUIDITY_UNPROVEN. ``liquidity_usd`` is the exact-pool USD liquidity when it
    was present, finite, non-negative and exact-linked; otherwise ``None`` (never
    coerced to zero).
    """

    status: str
    liquidity_usd: float | None
    mint: str
    pool: str
    reason: str
    source_status: str
    outcome_category: str | None = None
    detailed_reason: str | None = None
    source_request_id: int | None = None
    source_response_id: int | None = None
    source_failure_id: int | None = None
    failure_type: str | None = None

    @property
    def passes_floor(self) -> bool:
        return self.status == LIQUIDITY_PROVEN

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "liquidity_usd": self.liquidity_usd,
            "mint": self.mint,
            "pool": self.pool,
            "reason": self.reason,
            "detailed_reason": self.detailed_reason or self.reason,
            "source_status": self.source_status,
            "outcome_category": (
                self.outcome_category or _category_from_liquidity_fact(
                    status=self.status,
                    reason=self.reason,
                    source_status=self.source_status,
                    failure_type=self.failure_type,
                )
            ),
            "source_channel": "dexscreener_exact_pool_market",
            "source_request_id": self.source_request_id,
            "source_response_id": self.source_response_id,
            "source_failure_id": self.source_failure_id,
            "failure_type": self.failure_type,
        }


@dataclass(frozen=True)
class FrontDoorCandidate:
    mint: str
    pumpswap_pool: str
    market_identity: str
    provenance: str
    lifecycle_state: str
    graduation_block_time: int
    liquidity: LiquidityEvidence
    eligible: bool
    rejection: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mint": self.mint,
            "pool": self.pumpswap_pool,
            "market_identity": self.market_identity,
            "provenance": self.provenance,
            "lifecycle_state": self.lifecycle_state,
            "graduation_block_time": self.graduation_block_time,
            "liquidity": self.liquidity.to_dict(),
            "eligible": self.eligible,
            "rejection": self.rejection,
        }


# --------------------------------------------------------------------------- #
# Exact-pool liquidity enrichment                                             #
# --------------------------------------------------------------------------- #

def _extract_exact_pair_liquidity(
    pairs: Sequence[Mapping[str, Any]], *, mint: str, pool: str
) -> tuple[float | None, str]:
    """Read the liquidity of the single exact Solana mint+pool pair, fail-closed.

    Requires exactly one pair whose ``chain == solana`` AND ``pair_address`` equals
    the confirmed PumpSwap pool AND ``token_mint`` equals the exact mint. A
    token-level payload (the mint on some *other* pool) can never substitute. A
    missing / null / malformed / non-finite / negative ``liquidity_usd`` fails
    closed and is never coerced to zero.
    """
    exact = [
        p
        for p in pairs
        if isinstance(p, Mapping)
        and p.get("chain") == "solana"
        and p.get("pair_address") == pool
        and p.get("token_mint") == mint
    ]
    if not exact:
        pool_present = any(
            isinstance(p, Mapping) and p.get("pair_address") == pool for p in pairs
        )
        mint_present = any(
            isinstance(p, Mapping) and p.get("token_mint") == mint for p in pairs
        )
        if pool_present and not mint_present:
            return None, "LIQUIDITY_MINT_MISMATCH"
        if mint_present and not pool_present:
            # The mint exists only on a different pool: token-level liquidity can
            # never replace the exact confirmed PumpSwap pool.
            return None, "LIQUIDITY_POOL_MISMATCH_TOKEN_LEVEL"
        return None, "LIQUIDITY_NO_EXACT_PAIR"
    if len(exact) > 1:
        return None, "LIQUIDITY_AMBIGUOUS_EXACT_PAIR"

    raw = exact[0].get("liquidity_usd")
    if raw is None:
        return None, "LIQUIDITY_MISSING"
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None, "LIQUIDITY_MALFORMED"
    if not math.isfinite(value):
        return None, "LIQUIDITY_NON_FINITE"
    if value < 0:
        return None, "LIQUIDITY_NEGATIVE"
    return value, "LIQUIDITY_EXACT_POOL"


_EXACT_PAIR_IDENTITY_REASONS = frozenset({
    "LIQUIDITY_NO_EXACT_PAIR",
    "LIQUIDITY_AMBIGUOUS_EXACT_PAIR",
    "LIQUIDITY_MINT_MISMATCH",
    "LIQUIDITY_POOL_MISMATCH_TOKEN_LEVEL",
})
_MALFORMED_LIQUIDITY_REASONS = frozenset({
    "LIQUIDITY_MISSING",
    "LIQUIDITY_MALFORMED",
    "LIQUIDITY_NON_FINITE",
    "LIQUIDITY_NEGATIVE",
})


def _category_from_liquidity_fact(
    *, status: str, reason: str, source_status: str, failure_type: str | None
) -> str:
    """Map evidence to one truthful category without changing admission."""
    if status == LIQUIDITY_PROVEN:
        return LIQUIDITY_EXACT_ABOVE_FLOOR
    if status == LIQUIDITY_BELOW_SELECTION_FLOOR:
        if reason == LIQUIDITY_BELOW_SELECTION_FLOOR_COOLDOWN:
            return LIQUIDITY_HISTORICAL_BELOW_FLOOR_COOLDOWN
        return LIQUIDITY_EXACT_BELOW_FLOOR
    if reason == "IDENTITY_OR_GRADUATION_UNCONFIRMED":
        return LIQUIDITY_IDENTITY_UNCONFIRMED
    if reason in _EXACT_PAIR_IDENTITY_REASONS:
        return LIQUIDITY_EXACT_PAIR_UNAVAILABLE_OR_MISMATCH
    lowered_failure = str(failure_type or "").lower()
    lowered_reason = str(reason or "").lower()
    status_upper = str(source_status or "").upper()
    if (
        status_upper == "STALE"
        or "rate_limit" in lowered_failure
        or "rate_limit" in lowered_reason
        or "stale" in lowered_failure
        or "stale" in lowered_reason
    ):
        return LIQUIDITY_SOURCE_RATE_LIMITED_OR_STALE
    if (
        status_upper == "PARTIAL"
        or reason in _MALFORMED_LIQUIDITY_REASONS
        or any(
            marker in lowered_failure
            for marker in ("malformed", "missing_critical", "parse", "decode")
        )
    ):
        return LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL
    return LIQUIDITY_SOURCE_UNAVAILABLE


def classify_liquidity(
    value: float | None,
    *,
    mint: str,
    pool: str,
    reason: str,
    source_status: str,
    detailed_reason: str | None = None,
    source_request_id: int | None = None,
    source_response_id: int | None = None,
    source_failure_id: int | None = None,
    failure_type: str | None = None,
) -> LiquidityEvidence:
    """Apply the $3,000 floor to an exact-pool liquidity value (categorical)."""
    if value is None:
        return LiquidityEvidence(
            LIQUIDITY_UNPROVEN, None, mint, pool, reason, source_status,
            _category_from_liquidity_fact(
                status=LIQUIDITY_UNPROVEN,
                reason=reason,
                source_status=source_status,
                failure_type=failure_type,
            ),
            detailed_reason or reason,
            source_request_id,
            source_response_id,
            source_failure_id,
            failure_type,
        )
    if value < SELECTION_FLOOR_USD:
        return LiquidityEvidence(
            LIQUIDITY_BELOW_SELECTION_FLOOR, value, mint, pool,
            "BELOW_3000_FLOOR", source_status,
            LIQUIDITY_EXACT_BELOW_FLOOR,
            detailed_reason or "BELOW_3000_FLOOR",
            source_request_id,
            source_response_id,
            source_failure_id,
            failure_type,
        )
    return LiquidityEvidence(
        LIQUIDITY_PROVEN, value, mint, pool, "AT_OR_ABOVE_3000_FLOOR", source_status,
        LIQUIDITY_EXACT_ABOVE_FLOOR,
        detailed_reason or "AT_OR_ABOVE_3000_FLOOR",
        source_request_id,
        source_response_id,
        source_failure_id,
        failure_type,
    )


def enrich_pool_liquidity(
    connection: sqlite3.Connection,
    *,
    mint: str,
    pumpswap_pool: str,
    dexscreener_transport: Callable[[Any], Mapping[str, Any]],
    request_key: str,
    recent_request_count: int = 0,
    on_request: Callable[[int], None] | None = None,
    measured_ledger: Any | None = None,
) -> LiquidityEvidence:
    """Run one governed exact-pair DexScreener request and classify its liquidity.

    The request is executed through the Source Governor and recorded in the source
    ledger. Freshness contract (adopted, E.26/E.30): the request is made fresh in
    the current cycle, one transport is one charged operation; a STALE / FAILED /
    rate-limited governed result is LIQUIDITY_UNPROVEN (no retry / rotation /
    reconnect / fallback). DexScreener supplies market evidence only — never Pump
    origin or graduation.

    When ``measured_ledger`` is supplied, every declared transport identity on the
    governed normalized payload is recorded for success, below-floor, malformed,
    stale, rate-limited, and failed attempts alike.
    """
    adapter = build_dexscreener_adapter(
        enabled=True, fixture_transport=dexscreener_transport
    )
    request = build_governed_source_request(
        DEXSCREENER_SOURCE_NAME,
        LIQUIDITY_REQUEST_KIND,
        request_key=request_key,
        tracking_priority=0,
        payload={
            "request_kind": LIQUIDITY_REQUEST_KIND,
            "chain": "solana",
            "pair_address": pumpswap_pool,
            "mint": mint,
        },
    )
    execution = execute_source_request_with_governor(
        connection, request, adapter, recent_request_count=recent_request_count
    )
    # V2-9.7E.46B.2: report the exact durable request identity this invocation
    # created, before any status branching, so a failed pair snapshot is charged
    # exactly once and stage-local accounting never re-counts another stage's row.
    if on_request is not None:
        on_request(int(execution.request_record.id))
    result = execution.normalized_result
    if measured_ledger is not None:
        from printer_v1.sources.measured_transport import record_payload_transports

        payload_for_measure = result.normalized_payload or {}
        if isinstance(payload_for_measure, Mapping):
            try:
                record_payload_transports(
                    measured_ledger,
                    payload_for_measure,
                    default_stage="DEXSCREENER_DISCOVERY",
                )
            except Exception:
                # Declared identities only; never invent from request rows.
                pass
    source_status = getattr(result.source_status, "name", str(result.source_status))
    request_id = int(execution.request_record.id)
    response_id = (
        None if execution.response_record is None else int(execution.response_record.id)
    )
    failure_id = (
        None if execution.failure_record is None else int(execution.failure_record.id)
    )
    failure_type = result.failure_type
    detailed_reason = result.failure_message

    if result.source_status == SourceStatus.STALE:
        return LiquidityEvidence(
            LIQUIDITY_UNPROVEN, None, mint, pumpswap_pool,
            "LIQUIDITY_STALE_SOURCE", source_status,
            LIQUIDITY_SOURCE_RATE_LIMITED_OR_STALE,
            detailed_reason or "LIQUIDITY_STALE_SOURCE",
            request_id,
            response_id,
            failure_id,
            failure_type,
        )

    payload = result.normalized_payload or {}
    # Lawful exact-pair no-match (pairs:[], pairs:null, or envelope-missing pairs)
    # is PARTIAL/ACCEPTABLE_PARTIAL_DATA with no failure_type. It must become
    # LIQUIDITY_NO_EXACT_PAIR — never a fabricated liquidity row and never a
    # malformed-provider outage.
    if (
        result.source_status == SourceStatus.PARTIAL
        and not result.failure_type
        and isinstance(payload, Mapping)
        and (
            bool(payload.get("no_matching_pairs"))
            or payload.get("pairs") == []
            or (
                payload.get("pairs") is None
                and payload.get("pairs_field_type") in {"NULL", "MISSING", "LIST"}
            )
        )
    ):
        no_match_reason = str(
            payload.get("no_matching_pairs_reason") or "LIQUIDITY_NO_EXACT_PAIR"
        )
        return classify_liquidity(
            None,
            mint=mint,
            pool=pumpswap_pool,
            reason="LIQUIDITY_NO_EXACT_PAIR",
            source_status=source_status,
            detailed_reason=no_match_reason,
            source_request_id=request_id,
            source_response_id=response_id,
            source_failure_id=failure_id,
            failure_type=None,
        )

    if result.source_status != SourceStatus.COMPLETE or result.failure_type:
        reason = f"LIQUIDITY_SOURCE_{result.failure_type or source_status}"
        return LiquidityEvidence(
            LIQUIDITY_UNPROVEN, None, mint, pumpswap_pool,
            reason, source_status,
            _category_from_liquidity_fact(
                status=LIQUIDITY_UNPROVEN,
                reason=reason,
                source_status=source_status,
                failure_type=failure_type,
            ),
            detailed_reason or reason,
            request_id,
            response_id,
            failure_id,
            failure_type,
        )

    pairs = payload.get("pairs") or []
    value, reason = _extract_exact_pair_liquidity(pairs, mint=mint, pool=pumpswap_pool)
    return classify_liquidity(
        value,
        mint=mint,
        pool=pumpswap_pool,
        reason=reason,
        source_status=source_status,
        detailed_reason=reason,
        source_request_id=request_id,
        source_response_id=response_id,
        source_failure_id=failure_id,
        failure_type=failure_type,
    )


# --------------------------------------------------------------------------- #
# Provenance                                                                   #
# --------------------------------------------------------------------------- #

def provenance_for(mint: str, latest_mints: "set[str]") -> str:
    """Truthful provenance derived ONLY from the current-cycle confirmed set.

    LATEST_GRADUATED  — confirmed through a migration event in the current cycle.
    PERSISTED_GRADUATED — confirmed before the current cycle and not rediscovered
    as a current-cycle migration. Never derived from caller labels, timestamps or
    provider ordering.
    """
    return LATEST_GRADUATED_CHANNEL if mint in latest_mints else PERSISTED_GRADUATED_CHANNEL


# --------------------------------------------------------------------------- #
# Selection (frozen categorical two-slot, reusing the shared seeded primitive)  #
# --------------------------------------------------------------------------- #

def _seeded_uniform(
    candidates: Sequence[FrontDoorCandidate], cycle_seed: str, domain: str, count: int
) -> list[FrontDoorCandidate]:
    """Deterministic, seeded, uniform pick within one partition.

    Byte-identical to combined_executor._uniform_pick: identity-sorted by
    (_token_identity(mint), market_identity, lifecycle) then shuffled with the
    shared _fisher_yates primitive under a seeded domain. No score/rank/weight.
    """
    if count <= 0 or not candidates:
        return []
    ordered = sorted(
        candidates,
        key=lambda c: (_token_identity(c.mint), c.market_identity, c.lifecycle_state),
    )
    shuffled = _fisher_yates(ordered, f"{cycle_seed}|{domain}")
    return shuffled[:count]


def _mixed_two_slot(
    latest_eligible: Sequence[FrontDoorCandidate],
    persisted_eligible: Sequence[FrontDoorCandidate],
    cycle_seed: str,
) -> tuple[list[FrontDoorCandidate], str]:
    """Frozen mixed two-slot rule: one LATEST + one PERSISTED when both exist.

    This is the E.41 categorical two-slot anti-concentration rule with the single
    non-latest category PERSISTED_GRADUATED. When only one partition is available
    it degrades honestly to a uniform pick within it (no fabricated diversity).
    """
    if latest_eligible and persisted_eligible:
        slot1 = _seeded_uniform(latest_eligible, cycle_seed, LATEST_GRADUATED_CHANNEL, 1)
        slot2 = _seeded_uniform(
            persisted_eligible, cycle_seed, PERSISTED_GRADUATED_CHANNEL, 1
        )
        return slot1 + slot2, "MIXED_TWO_SLOT"
    pool = list(persisted_eligible or latest_eligible)
    selected = _seeded_uniform(pool, cycle_seed, "SINGLE_CATEGORY", min(2, len(pool)))
    return selected, "SINGLE_CATEGORY_DEGRADED"


def _seeded_order(
    candidates: Sequence[FrontDoorCandidate], cycle_seed: str, domain: str
) -> list[FrontDoorCandidate]:
    """The full deterministic seeded-uniform queue for a partition (not just a pick)."""
    return _seeded_uniform(candidates, cycle_seed, domain, len(candidates))


def holder_reserve_order(
    latest_eligible: Sequence[FrontDoorCandidate],
    persisted_eligible: Sequence[FrontDoorCandidate],
    *,
    cycle_seed: str,
) -> list[FrontDoorCandidate]:
    """Return the deterministic round-robin holder reserve evaluation order."""
    latest_queue = _seeded_order(
        latest_eligible, cycle_seed, LATEST_GRADUATED_CHANNEL
    )
    persisted_queue = _seeded_order(
        persisted_eligible, cycle_seed, PERSISTED_GRADUATED_CHANNEL
    )
    ordered: list[FrontDoorCandidate] = []
    for ordinal in range(max(len(latest_queue), len(persisted_queue))):
        if ordinal < len(latest_queue):
            ordered.append(latest_queue[ordinal])
        if ordinal < len(persisted_queue):
            ordered.append(persisted_queue[ordinal])
    return ordered


def combined_reserve_order(
    eligible: Sequence[FrontDoorCandidate],
    *,
    cycle_seed: str,
) -> list[FrontDoorCandidate]:
    """One deterministic seeded-uniform order over the *combined* eligible pool.

    Unlike ``holder_reserve_order`` (which round-robins the two partitions), this
    is a single-pool order: LATEST and PERSISTED candidates are drawn from one
    identity-sorted, seeded-shuffled queue. This is what makes any lawful two-token
    composition reachable without a compulsory one-per-partition quota. Ordering is
    seeded-uniform only; provenance, liquidity magnitude, recency and provider order
    never affect it.
    """
    return _seeded_uniform(
        list(eligible), cycle_seed, COMBINED_TWO_TOKEN_CHANNEL, len(list(eligible))
    )


def _composition_label(selected: Sequence[FrontDoorCandidate]) -> str:
    """Truthful composition label from the *actual* provenances of the two slots."""
    latest = sum(1 for c in selected if c.provenance == LATEST_GRADUATED_CHANNEL)
    persisted = sum(
        1 for c in selected if c.provenance == PERSISTED_GRADUATED_CHANNEL
    )
    if len(selected) < 2:
        return "SINGLE"
    if latest == 2:
        return "LATEST+LATEST"
    if persisted == 2:
        return "PERSISTED+PERSISTED"
    return "LATEST+PERSISTED"


def select_two_eligible_tokens(
    eligible: Sequence[FrontDoorCandidate],
    *,
    cycle_seed: str,
    holder_evaluator: "Callable[[FrontDoorCandidate], tuple[bool, str]]",
    candidate_cap: int,
    source_unavailable_reasons: "frozenset[str] | set[str] | None" = None,
) -> dict[str, Any]:
    """V2-9.7E.46B partition-flexible two-token selection from one combined pool.

    Walks the single deterministic ``combined_reserve_order`` and runs the injected
    holder gate in that order within a frozen total holder-operation ``candidate_cap``.
    On a holder failure/unknown it continues immediately to the next lawful candidate.
    It stops as soon as **two distinct** holder-eligible tokens exist — of *any* lawful
    provenance composition — or the pool is exhausted or the cap is reached. A rejected
    identity gets no second chance; no holder result becomes a score/rank/confidence/
    weight.

    Terminal classification (item 8):
      * ``SELECTION_TWO_TOKEN_READY`` — two distinct eligible tokens found;
      * ``SELECTION_HOLDER_SOURCE_BLOCKED`` — a holder source/network was unavailable
        for at least one evaluated candidate and fewer than two are eligible;
      * ``DISCOVERY_SELECTION_CAPACITY_EXHAUSTED`` — the approved candidate-search cap
        was reached before the pool was fully covered and healthy sources answered;
      * ``DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT`` — the whole bounded pool was
        covered by healthy sources and fewer than two tokens are eligible.
    """
    if candidate_cap < 0:
        raise GraduatedFrontDoorError("INVALID_CANDIDATE_CAP", str(candidate_cap))
    source_prefixes = tuple(
        source_unavailable_reasons
        if source_unavailable_reasons is not None
        else HOLDER_SOURCE_UNAVAILABLE_PREFIXES
    )
    order = combined_reserve_order(eligible, cycle_seed=cycle_seed)
    selected: list[FrontDoorCandidate] = []
    funnel: list[dict[str, Any]] = []
    ops = 0
    cap_reached = False
    saw_source_outage = False
    for candidate in order:
        if len(selected) == 2:
            break
        if ops >= candidate_cap:
            cap_reached = True
            break
        ops += 1
        eligible_flag, reason = holder_evaluator(candidate)
        if not eligible_flag and str(reason).startswith(source_prefixes):
            saw_source_outage = True
        funnel.append(
            {
                "mint": candidate.mint,
                "pool": candidate.pumpswap_pool,
                "provenance": candidate.provenance,
                "holder_eligible": bool(eligible_flag),
                "reason": reason,
                "operation_ordinal": ops,
            }
        )
        if eligible_flag:
            selected.append(candidate)

    fully_covered = ops >= len(order) and not cap_reached
    if len(selected) == 2:
        terminal = SELECTION_TWO_TOKEN_READY
    elif saw_source_outage:
        terminal = SELECTION_HOLDER_SOURCE_BLOCKED
    elif not fully_covered:
        terminal = SELECTION_CAPACITY_EXHAUSTED
    else:
        terminal = SELECTION_COVERAGE_INSUFFICIENT

    return {
        "selected": selected,
        "terminal": terminal,
        "composition": _composition_label(selected),
        "funnel": funnel,
        "holder_operations": ops,
        "candidate_cap": candidate_cap,
        "cap_reached": cap_reached,
        "pool_size": len(order),
        "fully_covered": fully_covered,
        "eligible_count": len(selected),
    }


def select_holder_eligible_pair(
    latest_eligible: Sequence[FrontDoorCandidate],
    persisted_eligible: Sequence[FrontDoorCandidate],
    *,
    cycle_seed: str,
    holder_evaluator: "Callable[[FrontDoorCandidate], tuple[bool, str]]",
    candidate_cap: int,
) -> dict[str, Any]:
    """OFFLINE-ONLY historical helper — not ordinary-run selection authority.

    Ordinary selection uses ``selection_authority.select_two_candidates`` only.
    This partitioned latest/persisted helper remains for historical offline tests
    and must not be re-wired onto the ordinary public ``run`` path.
    """
    if candidate_cap < 0:
        raise GraduatedFrontDoorError("INVALID_CANDIDATE_CAP", str(candidate_cap))
    latest_queue = _seeded_order(latest_eligible, cycle_seed, LATEST_GRADUATED_CHANNEL)
    persisted_queue = _seeded_order(
        persisted_eligible, cycle_seed, PERSISTED_GRADUATED_CHANNEL
    )
    li = pi = 0
    selected_latest: FrontDoorCandidate | None = None
    selected_persisted: FrontDoorCandidate | None = None
    funnel: list[dict[str, Any]] = []
    ops = 0
    cap_reached = False

    def _try(partition: str, candidate: FrontDoorCandidate) -> bool:
        nonlocal ops
        ops += 1
        eligible, reason = holder_evaluator(candidate)
        funnel.append(
            {
                "partition": partition,
                "mint": candidate.mint,
                "pool": candidate.pumpswap_pool,
                "holder_eligible": bool(eligible),
                "reason": reason,
                "operation_ordinal": ops,
            }
        )
        return bool(eligible)

    # Round-robin advance within each partition's own deterministic order.
    while (selected_latest is None and li < len(latest_queue)) or (
        selected_persisted is None and pi < len(persisted_queue)
    ):
        if ops >= candidate_cap:
            cap_reached = True
            break
        if selected_latest is None and li < len(latest_queue):
            candidate = latest_queue[li]
            li += 1
            if _try("LATEST_GRADUATED", candidate):
                selected_latest = candidate
            if ops >= candidate_cap and (
                selected_persisted is None and pi < len(persisted_queue)
            ):
                cap_reached = True
                break
        if selected_persisted is None and pi < len(persisted_queue):
            candidate = persisted_queue[pi]
            pi += 1
            if _try("PERSISTED_GRADUATED", candidate):
                selected_persisted = candidate

    return {
        "selected_latest": selected_latest,
        "selected_persisted": selected_persisted,
        "funnel": funnel,
        "holder_operations": ops,
        "candidate_cap": candidate_cap,
        "cap_reached": cap_reached,
        "latest_queue_len": len(latest_queue),
        "persisted_queue_len": len(persisted_queue),
    }


# --------------------------------------------------------------------------- #
# Atomic-handoff compatibility (proved, never enqueued)                        #
# --------------------------------------------------------------------------- #

def _handoff_compatibility(selected: Sequence[FrontDoorCandidate]) -> dict[str, Any]:
    """Prove the selected pair is compatible with the canonical atomic two-slot
    handoff contract WITHOUT enqueuing tracking, scheduler, snapshot or lifecycle.

    Each selected candidate must have a non-empty exact mint, a
    ``solana-mainnet:pumpswap:{pool}`` market identity, and the two selected slots
    must be distinct in both mint and pool. This is the deterministic selected-pair
    readiness boundary; snapshots/memory own everything after it.
    """
    checks: list[dict[str, Any]] = []
    seen_mints: set[str] = set()
    seen_pools: set[str] = set()
    all_ok = True
    for ordinal, candidate in enumerate(selected, start=1):
        expected_identity = f"solana-mainnet:{PUMPSWAP_VENUE}:{candidate.pumpswap_pool}"
        mint_ok = bool(candidate.mint)
        identity_ok = (
            candidate.market_identity == expected_identity
            and candidate.market_identity.startswith(PUMPSWAP_MARKET_PREFIX)
        )
        distinct_ok = (
            candidate.mint not in seen_mints and candidate.pumpswap_pool not in seen_pools
        )
        graduated_ok = candidate.lifecycle_state == GRADUATED_LIFECYCLE
        floor_ok = candidate.liquidity.passes_floor
        seen_mints.add(candidate.mint)
        seen_pools.add(candidate.pumpswap_pool)
        candidate_ok = mint_ok and identity_ok and distinct_ok and graduated_ok and floor_ok
        all_ok = all_ok and candidate_ok
        checks.append(
            {
                "slot_ordinal": ordinal,
                "mint": candidate.mint,
                "pool": candidate.pumpswap_pool,
                "market_identity": candidate.market_identity,
                "mint_ok": mint_ok,
                "market_identity_ok": identity_ok,
                "distinct_slot_ok": distinct_ok,
                "graduated_ok": graduated_ok,
                "liquidity_floor_ok": floor_ok,
                "compatible": candidate_ok,
            }
        )
    return {
        "atomic_two_slot_ready": all_ok and len(selected) == 2,
        "selected_slot_count": len(selected),
        "checks": checks,
        "tracking_enqueued": False,
        "scheduler_started": False,
        "lifecycle_started": False,
        "snapshot_started": False,
    }


# --------------------------------------------------------------------------- #
# Ledger / integrity                                                           #
# --------------------------------------------------------------------------- #

def _dexscreener_ledger(
    connection: sqlite3.Connection, *, request_ids: "Sequence[int]"
) -> dict[str, int]:
    """Stage-local liquidity accounting over this invocation's exact identities.

    V2-9.7E.46B.2. This deliberately does NOT count whole-table totals such as
    ``WHERE source_name='dexscreener'``: that form also counted requests owned by
    other stages (the discovery fresh-profile locator), and the campaign — which
    adds the discovery and front-door totals — then charged that locator twice.
    Only the exact ``pair_market_snapshot`` request rows created by this
    invocation are charged, each exactly once, whether it succeeded or failed.
    """
    identities = sorted({int(value) for value in request_ids})
    if not identities:
        return {
            "liquidity_requests": 0,
            "liquidity_responses": 0,
            "liquidity_failures": 0,
        }
    placeholders = ",".join("?" * len(identities))

    def _count(sql: str) -> int:
        try:
            return int(connection.execute(sql, identities).fetchone()[0])
        except sqlite3.Error:
            return 0

    return {
        "liquidity_requests": len(identities),
        "liquidity_responses": _count(
            "SELECT COUNT(*) FROM printer_source_responses "
            f"WHERE source_request_id IN ({placeholders})"
        ),
        "liquidity_failures": _count(
            "SELECT COUNT(*) FROM printer_source_failures "
            f"WHERE source_request_id IN ({placeholders})"
        ),
    }


def _forbidden_deltas(connection: sqlite3.Connection) -> dict[str, int]:
    deltas: dict[str, int] = {}
    for table in _FORBIDDEN_TABLES:
        exists = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if exists is None:
            deltas[table] = 0
            continue
        deltas[table] = int(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        )
    return deltas


def _cooldown_ok(
    connection: sqlite3.Connection, mint: str, pool: str, batch_seq: int
) -> tuple[bool, str]:
    """Existing STNP / cooldown / rotation gate.

    Fail-closed on database/state errors. A fresh DB with the required rotation
    table present and empty still passes (no prior selection). Missing schema is
    no longer treated as a silent pass on ordinary migrated databases.
    """
    try:
        ok_token, reason_token = check_token_selection_cooldown(connection, mint, batch_seq)
        ok_pair, reason_pair = check_pair_selection_cooldown(connection, pool, batch_seq)
    except sqlite3.OperationalError as exc:
        return False, f"COOLDOWN_STATE_UNAVAILABLE:{exc.__class__.__name__}"
    except sqlite3.Error as exc:
        return False, f"COOLDOWN_STATE_ERROR:{exc.__class__.__name__}"
    if not ok_token:
        return False, reason_token or "REJECTION_TOKEN_SELECTION_COOLDOWN"
    if not ok_pair:
        return False, reason_pair or "REJECTION_PAIR_SELECTION_COOLDOWN"
    return True, ""


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_market_floor_state(
    connection: sqlite3.Connection, mint: str
) -> dict[str, Any] | None:
    """Read durable market-floor revalidation state for one graduated mint."""
    try:
        row = connection.execute(
            """SELECT mint_identity, pumpswap_pool, liquidity_status, liquidity_usd,
                      last_checked_at, cooldown_until, updated_at
               FROM printer_graduated_market_floor_state
               WHERE mint_identity=?""",
            (mint,),
        ).fetchone()
    except sqlite3.OperationalError as exc:
        raise GraduatedFrontDoorError(
            "MARKET_FLOOR_STATE_UNAVAILABLE", str(exc)
        ) from exc
    if row is None:
        return None
    return dict(row)


def market_floor_cooldown_active(
    state: Mapping[str, Any] | None, *, now: str
) -> bool:
    """True when a below-floor cooldown is present and has not expired."""
    if state is None:
        return False
    if str(state.get("liquidity_status") or "") != LIQUIDITY_BELOW_SELECTION_FLOOR:
        return False
    cooldown_until = state.get("cooldown_until")
    if not cooldown_until:
        return False
    return _parse_iso(str(now)) < _parse_iso(str(cooldown_until))


def record_market_floor_state(
    connection: sqlite3.Connection,
    *,
    mint: str,
    pool: str,
    liquidity: LiquidityEvidence,
    now: str,
    cooldown_seconds: int = BELOW_FLOOR_MARKET_COOLDOWN_SECONDS,
) -> None:
    """Persist last exact-pool liquidity classification and below-floor cooldown."""
    cooldown_until = None
    if liquidity.status == LIQUIDITY_BELOW_SELECTION_FLOOR:
        cooldown_until = (
            _parse_iso(now) + timedelta(seconds=int(cooldown_seconds))
        ).isoformat()
    try:
        connection.execute(
            """INSERT INTO printer_graduated_market_floor_state(
                mint_identity, pumpswap_pool, liquidity_status, liquidity_usd,
                last_checked_at, cooldown_until, updated_at
            ) VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(mint_identity) DO UPDATE SET
                pumpswap_pool=excluded.pumpswap_pool,
                liquidity_status=excluded.liquidity_status,
                liquidity_usd=excluded.liquidity_usd,
                last_checked_at=excluded.last_checked_at,
                cooldown_until=excluded.cooldown_until,
                updated_at=excluded.updated_at""",
            (
                mint,
                pool,
                liquidity.status,
                liquidity.liquidity_usd,
                now,
                cooldown_until,
                now,
            ),
        )
    except sqlite3.OperationalError as exc:
        raise GraduatedFrontDoorError(
            "MARKET_FLOOR_STATE_UNAVAILABLE", str(exc)
        ) from exc


def _bounded_refresh_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    latest_mints: set[str],
    cycle_seed: str,
    max_candidates: int,
    exclude_mints: "set[str] | None" = None,
) -> list[Mapping[str, Any]]:
    """Choose a bounded categorical refresh batch without provider ordering.

    ``max_candidates`` is the size of **one evaluation batch**, not the entire
    discovery universe. Callers that need multi-round completeness must loop with
    ``exclude_mints`` covering earlier rounds (V2-9.8B.21).
    """
    if max_candidates <= 0:
        return []
    excluded = {str(m) for m in (exclude_mints or set())}
    filtered = [
        row for row in rows if str(row["mint_identity"]) not in excluded
    ]
    latest = sorted(
        (row for row in filtered if str(row["mint_identity"]) in latest_mints),
        key=lambda row: str(row["mint_identity"]),
    )
    persisted = sorted(
        (row for row in filtered if str(row["mint_identity"]) not in latest_mints),
        key=lambda row: str(row["mint_identity"]),
    )
    latest = _fisher_yates(latest, f"{cycle_seed}|REFRESH_LATEST")
    persisted = _fisher_yates(persisted, f"{cycle_seed}|REFRESH_PERSISTED")
    if not latest or not persisted:
        return list((latest or persisted)[:max_candidates])

    latest_cap = max(1, max_candidates // 2)
    persisted_cap = max(1, max_candidates - latest_cap)
    selected = list(latest[:latest_cap]) + list(persisted[:persisted_cap])
    remaining = max_candidates - len(selected)
    if remaining > 0:
        selected.extend(latest[latest_cap:latest_cap + remaining])
        remaining = max_candidates - len(selected)
    if remaining > 0:
        selected.extend(persisted[persisted_cap:persisted_cap + remaining])
    return selected


# --------------------------------------------------------------------------- #
# Front door                                                                   #
# --------------------------------------------------------------------------- #

STAGE_KIND_EXACT_LIQUIDITY = "EXACT_LIQUIDITY"


def run_graduated_liquidity_front_door(
    db_path: str | Path,
    *,
    cycle_seed: str,
    latest_mints: "set[str] | Sequence[str]",
    dexscreener_transport_factory: Callable[[str, str], Callable[[Any], Mapping[str, Any]]] | None = None,
    now: str | None = None,
    batch_seq: int = 1,
    request_key_prefix: str = "v2-9-7e-43",
    max_candidates: int = 64,
    exclude_mints: "set[str] | Sequence[str] | None" = None,
    stage_evidence_sink: Callable[[Mapping[str, Any]], None] | None = None,
    transport_identity_observer: Callable[[Any], None] | None = None,
    campaign_id: str | None = None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    discovery_round: int = 1,
) -> dict[str, Any]:
    """Enrich, floor, gate, and select graduated candidates from the registry.

    Reads confirmed graduated candidates from the durable registry, enriches a
    bounded evaluation batch with governed exact-pool liquidity, applies the
    $3,000 floor and the existing identity / source-quality / STNP / cooldown
    gates, assigns truthful LATEST/PERSISTED provenance, and selects at most one
    candidate from each partition via the frozen categorical two-slot rule.
    Stops at deterministic selected-pair readiness (atomic-handoff compatibility
    proved, never enqueued).

    ``max_candidates`` bounds **one evaluation batch**. Multi-round discovery
    (V2-9.8B.21) must call this repeatedly with ``exclude_mints`` covering earlier
    rounds; it must not treat a single batch as the entire governed market.

    ``dexscreener_transport_factory(mint, pool)`` returns the governed exact-pair
    transport for one candidate; when omitted the live
    ``build_dexscreener_pair_snapshot_transport(pool)`` is used. Never raises on an
    ordinary market/liquidity failure — every rejection is recorded honestly.

    When ``stage_evidence_sink`` is supplied, each invocation seals exactly one
    EXACT_LIQUIDITY stage evidence block with a distinct round stage_id before
    returning or propagating an exception.

    ``transport_identity_observer`` is notified at measurement time before seal.
    """
    now = now or _utc_now_iso()
    latest_set = set(latest_mints)
    excluded_set = {str(m) for m in (exclude_mints or ())}
    if not cycle_seed or not str(cycle_seed).strip():
        raise GraduatedFrontDoorError("MISSING_SELECTION_SEED")
    if dexscreener_transport_factory is None:
        def dexscreener_transport_factory(mint: str, pool: str):  # type: ignore[misc]
            return build_dexscreener_pair_snapshot_transport(pool)

    from printer_v1.db.sqlite_write_contracts import connect_operational
    from printer_v1.sources.campaign_six_unit_accounting import (
        build_campaign_stage_id,
        seal_campaign_stage_evidence,
    )
    from printer_v1.sources.measured_transport import MeasuredTransportLedger

    measured_ledger = MeasuredTransportLedger(
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        on_transport_recorded=transport_identity_observer,
    )
    stage_terminal_status = "COMPLETED"
    stage_first_terminal_cause: str | None = None
    stage_opened = False
    unexpected_exception: BaseException | None = None

    connection = connect_operational(db_path)
    dex_request_count = 0
    # V2-9.7E.46B.2: the exact durable request identities this invocation creates.
    # Stage-local accounting is derived from these, never from a whole-table total.
    stage_request_ids: list[int] = []
    selected: list[FrontDoorCandidate] = []
    latest_eligible: list[FrontDoorCandidate] = []
    persisted_eligible: list[FrontDoorCandidate] = []
    candidates: list[FrontDoorCandidate] = []
    below_floor = 0
    unproven = 0
    cooldown_skips = 0
    mix_state = "NONE"
    two_candidate: dict[str, Any] = {
        "ready": False,
        "terminal": "SELECTION_NONE",
        "candidate_a": None,
        "candidate_b": None,
        "selected": [],
        "selected_count": 0,
        "composition_label": "NONE",
        "funnel": [],
        "evaluated_count": 0,
        "pool_size": 0,
    }
    handoff: dict[str, Any] = {}
    ledger: dict[str, Any] = {}
    forbidden: dict[str, int] = {}
    integrity = "ok"
    fk_violations: list[Any] = []
    authority = None
    try:
        rows = _bounded_refresh_rows(
            export_graduated_candidates(connection),
            latest_mints=latest_set,
            cycle_seed=cycle_seed,
            max_candidates=max_candidates,
            exclude_mints=excluded_set,
        )

        for row in rows:
            mint = str(row["mint_identity"])
            pool = str(row["pumpswap_pool"])
            market_identity = str(row["market_identity"])
            lifecycle_state = str(row["lifecycle_state"])
            graduation_block_time = int(row["graduation_block_time"])
            provenance = provenance_for(mint, latest_set)

            rejection: str | None = None
            # Identity + graduation gate (defense in depth; registry guarantees it).
            expected_identity = f"solana-mainnet:{PUMPSWAP_VENUE}:{pool}"
            if (
                lifecycle_state != GRADUATED_LIFECYCLE
                or market_identity != expected_identity
                or not market_identity.startswith(PUMPSWAP_MARKET_PREFIX)
            ):
                rejection = "IDENTITY_OR_GRADUATION_UNCONFIRMED"
                liquidity = LiquidityEvidence(
                    LIQUIDITY_UNPROVEN,
                    None,
                    mint,
                    pool,
                    "IDENTITY_OR_GRADUATION_UNCONFIRMED",
                    "SKIPPED",
                    LIQUIDITY_IDENTITY_UNCONFIRMED,
                )
            else:
                floor_state = load_market_floor_state(connection, mint)
                if market_floor_cooldown_active(floor_state, now=now):
                    # V2-9.8B.6: skip DexScreener while below-floor cooldown is
                    # active. Retain last measured liquidity for honest reporting.
                    cooldown_skips += 1
                    below_floor += 1
                    prior_usd = (
                        None
                        if floor_state is None
                        else floor_state.get("liquidity_usd")
                    )
                    prior_value = (
                        None if prior_usd is None else float(prior_usd)
                    )
                    liquidity = LiquidityEvidence(
                        LIQUIDITY_BELOW_SELECTION_FLOOR,
                        prior_value,
                        mint,
                        pool,
                        LIQUIDITY_BELOW_SELECTION_FLOOR_COOLDOWN,
                        "COOLDOWN_SKIP",
                        LIQUIDITY_HISTORICAL_BELOW_FLOOR_COOLDOWN,
                    )
                    rejection = LIQUIDITY_BELOW_SELECTION_FLOOR_COOLDOWN
                else:
                    stage_opened = True
                    transport = dexscreener_transport_factory(mint, pool)
                    liquidity = enrich_pool_liquidity(
                        connection,
                        mint=mint,
                        pumpswap_pool=pool,
                        dexscreener_transport=transport,
                        request_key=f"{request_key_prefix}-liq-{mint}",
                        recent_request_count=dex_request_count,
                        on_request=stage_request_ids.append,
                        measured_ledger=measured_ledger,
                    )
                    dex_request_count += 1
                    record_market_floor_state(
                        connection,
                        mint=mint,
                        pool=pool,
                        liquidity=liquidity,
                        now=now,
                    )
                    if liquidity.status == LIQUIDITY_BELOW_SELECTION_FLOOR:
                        rejection = LIQUIDITY_BELOW_SELECTION_FLOOR
                        below_floor += 1
                    elif liquidity.status != LIQUIDITY_PROVEN:
                        rejection = LIQUIDITY_UNPROVEN
                        unproven += 1
                        if liquidity.outcome_category in {
                            LIQUIDITY_SOURCE_UNAVAILABLE,
                            LIQUIDITY_SOURCE_RATE_LIMITED_OR_STALE,
                            LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL,
                        }:
                            stage_terminal_status = "BLOCKED"
                            stage_first_terminal_cause = str(
                                liquidity.outcome_category
                            )
                    else:
                        # STNP / cooldown / rotation gate.
                        ok, reason = _cooldown_ok(connection, mint, pool, batch_seq)
                        if not ok:
                            rejection = reason

            eligible = rejection is None
            candidate = FrontDoorCandidate(
                mint=mint,
                pumpswap_pool=pool,
                market_identity=market_identity,
                provenance=provenance,
                lifecycle_state=lifecycle_state,
                graduation_block_time=graduation_block_time,
                liquidity=liquidity,
                eligible=eligible,
                rejection=rejection,
            )
            candidates.append(candidate)
            if eligible:
                if provenance == LATEST_GRADUATED_CHANNEL:
                    latest_eligible.append(candidate)
                else:
                    persisted_eligible.append(candidate)

        # Canonical selection authority: one combined deterministic selector.
        # Provenance remains an attribute; latest/persisted are not readiness columns.
        from printer_v1.discovery.selection_authority import (
            SelectionCandidate,
            select_two_candidates,
        )

        authority_pool = [
            SelectionCandidate(
                mint=c.mint,
                pair_address=c.pumpswap_pool,
                market_identity=c.market_identity,
                provenance=c.provenance,
                lifecycle_state=c.lifecycle_state,
                graduation_block_time=c.graduation_block_time,
                liquidity_usd=c.liquidity.liquidity_usd,
            )
            for c in (list(latest_eligible) + list(persisted_eligible))
        ]
        authority = select_two_candidates(
            authority_pool, cycle_seed=cycle_seed
        )
        by_key = {
            (c.mint, c.pumpswap_pool): c
            for c in (list(latest_eligible) + list(persisted_eligible))
        }
        selected = [
            by_key[(item.mint, item.pair_address)]
            for item in authority.selected
            if (item.mint, item.pair_address) in by_key
        ]
        mix_state = authority.composition_label
        connection.commit()

        handoff = _handoff_compatibility(selected)
        ledger = _dexscreener_ledger(connection, request_ids=stage_request_ids)
        forbidden = _forbidden_deltas(connection)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        fk_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    except BaseException as exc:
        stage_terminal_status = "FAILED"
        stage_first_terminal_cause = f"{type(exc).__name__}:{exc}"
        unexpected_exception = exc
        raise
    finally:
        connection.close()
        if stage_evidence_sink is not None and (
            stage_opened or measured_ledger.source_transport_operations > 0
        ):
            sink_error: BaseException | None = None
            try:
                if not all(
                    str(value or "").strip()
                    for value in (campaign_id, run_id, cycle_id)
                ):
                    raise GraduatedFrontDoorError(
                        "EXACT_LIQUIDITY_STAGE_SINK_REQUIRES_CAMPAIGN_RUN_CYCLE_IDENTITY"
                    )
                sealed = seal_campaign_stage_evidence(
                    ledger=measured_ledger,
                    stage_id=build_campaign_stage_id(
                        campaign_id=str(campaign_id),
                        run_id=str(run_id),
                        cycle_id=str(cycle_id),
                        stage_kind=STAGE_KIND_EXACT_LIQUIDITY,
                        stage_sequence=int(discovery_round),
                    ),
                    stage_kind=STAGE_KIND_EXACT_LIQUIDITY,
                    stage_sequence=int(discovery_round),
                    stage_terminal_status=stage_terminal_status,
                    stage_first_terminal_cause=stage_first_terminal_cause,
                    campaign_id=str(campaign_id),
                    run_id=str(run_id),
                    cycle_id=str(cycle_id),
                    sealed_at=now,
                )
                stage_evidence_sink(sealed)
            except BaseException as sink_exc:
                sink_error = sink_exc
            if unexpected_exception is not None:
                if sink_error is not None:
                    try:
                        unexpected_exception.add_note(
                            f"stage_evidence_sink_failure:{type(sink_error).__name__}:{sink_error}"
                        )
                    except (AttributeError, TypeError):
                        pass
            elif sink_error is not None:
                raise sink_error

    rejected = [c.to_dict() for c in candidates if not c.eligible]
    selected_pair_identity = tuple(
        f"{c.mint}|{c.pumpswap_pool}" for c in selected
    )
    two_candidate = (
        authority.as_dict()
        if authority is not None
        else two_candidate
    )
    return {
        "generated_at": now,
        "selection_floor_usd": SELECTION_FLOOR_USD,
        "cycle_seed": cycle_seed,
        "candidate_count": len(candidates),
        "candidates": [c.to_dict() for c in candidates],
        "latest_eligible_count": len(latest_eligible),
        "persisted_eligible_count": len(persisted_eligible),
        "below_floor_count": below_floor,
        "unproven_count": unproven,
        "cooldown_skip_count": cooldown_skips,
        "market_calls": dex_request_count,
        "rejected_count": len(rejected),
        "rejected": rejected,
        "mix_state": mix_state,
        "excluded_mint_count": len(excluded_set),
        "evaluation_batch_size": int(max_candidates),
        "selected": [
            {
                "mint": c.mint,
                "pool": c.pumpswap_pool,
                "market_identity": c.market_identity,
                "provenance": c.provenance,
                "liquidity_usd": c.liquidity.liquidity_usd,
                "graduation_block_time": c.graduation_block_time,
            }
            for c in selected
        ],
        # Neutral two-candidate contract is the only selection product.
        "two_candidate_selection": two_candidate,
        "candidate_a": two_candidate.get("candidate_a"),
        "candidate_b": two_candidate.get("candidate_b"),
        "selected_count": len(selected),
        # Provenance diagnostics only (never readiness / authority columns).
        "provenance_diagnostics": {
            "composition_label": two_candidate.get("composition_label"),
            "provenance_summary": two_candidate.get("provenance_summary"),
        },
        "selected_pair_identity": selected_pair_identity,
        "holder_reserve_order": [
            candidate.to_dict()
            for candidate in holder_reserve_order(
                latest_eligible, persisted_eligible, cycle_seed=cycle_seed
            )
        ],
        # V2-9.7E.46B: the single combined-pool order that feeds the partition-
        # flexible holder funnel (any lawful composition). This supersedes the
        # round-robin reserve order for downstream two-token selection.
        "combined_reserve_order": [
            candidate.to_dict()
            for candidate in combined_reserve_order(
                list(latest_eligible) + list(persisted_eligible),
                cycle_seed=cycle_seed,
            )
        ],
        "handoff_readiness": handoff,
        "source_operation_ledger": ledger,
        "forbidden_capability_deltas": forbidden,
        "forbidden_delta_total": sum(forbidden.values()),
        "integrity_check": integrity,
        "foreign_key_violations": len(fk_violations),
        "discovery_round": int(discovery_round),
    }

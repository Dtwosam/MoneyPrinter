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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from printer_v1.contracts.enums import SourceStatus
from printer_v1.discovery.combined_executor import (
    PUMPSWAP_MARKET_PREFIX,
    _fisher_yates,
    _token_identity,
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
            "source_status": self.source_status,
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


def classify_liquidity(value: float | None, *, mint: str, pool: str, reason: str,
                       source_status: str) -> LiquidityEvidence:
    """Apply the $3,000 floor to an exact-pool liquidity value (categorical)."""
    if value is None:
        return LiquidityEvidence(
            LIQUIDITY_UNPROVEN, None, mint, pool, reason, source_status
        )
    if value < SELECTION_FLOOR_USD:
        return LiquidityEvidence(
            LIQUIDITY_BELOW_SELECTION_FLOOR, value, mint, pool,
            "BELOW_3000_FLOOR", source_status,
        )
    return LiquidityEvidence(
        LIQUIDITY_PROVEN, value, mint, pool, "AT_OR_ABOVE_3000_FLOOR", source_status
    )


def enrich_pool_liquidity(
    connection: sqlite3.Connection,
    *,
    mint: str,
    pumpswap_pool: str,
    dexscreener_transport: Callable[[Any], Mapping[str, Any]],
    request_key: str,
    recent_request_count: int = 0,
) -> LiquidityEvidence:
    """Run one governed exact-pair DexScreener request and classify its liquidity.

    The request is executed through the Source Governor and recorded in the source
    ledger. Freshness contract (adopted, E.26/E.30): the request is made fresh in
    the current cycle, one transport is one charged operation; a STALE / FAILED /
    rate-limited governed result is LIQUIDITY_UNPROVEN (no retry / rotation /
    reconnect / fallback). DexScreener supplies market evidence only — never Pump
    origin or graduation.
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
    result = execution.normalized_result
    source_status = getattr(result.source_status, "name", str(result.source_status))

    if result.source_status == SourceStatus.STALE:
        return LiquidityEvidence(
            LIQUIDITY_UNPROVEN, None, mint, pumpswap_pool,
            "LIQUIDITY_STALE_SOURCE", source_status,
        )
    if result.source_status != SourceStatus.COMPLETE or result.failure_type:
        return LiquidityEvidence(
            LIQUIDITY_UNPROVEN, None, mint, pumpswap_pool,
            f"LIQUIDITY_SOURCE_{result.failure_type or source_status}",
            source_status,
        )

    payload = result.normalized_payload or {}
    pairs = payload.get("pairs") or []
    value, reason = _extract_exact_pair_liquidity(pairs, mint=mint, pool=pumpswap_pool)
    return classify_liquidity(
        value, mint=mint, pool=pumpswap_pool, reason=reason, source_status=source_status
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

def _dexscreener_ledger(connection: sqlite3.Connection) -> dict[str, int]:
    def _count(sql: str) -> int:
        try:
            return int(connection.execute(sql).fetchone()[0])
        except sqlite3.Error:
            return 0

    return {
        "liquidity_requests": _count(
            "SELECT COUNT(*) FROM printer_source_requests WHERE source_name='dexscreener'"
        ),
        "liquidity_responses": _count(
            "SELECT COUNT(*) FROM printer_source_responses WHERE source_name='dexscreener'"
        ),
        "liquidity_failures": _count(
            "SELECT COUNT(*) FROM printer_source_failures WHERE source_name='dexscreener'"
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
    """Existing STNP / cooldown / rotation gate (fail-closed on a real cooldown).

    In a fresh proof DB with no prior selection there is no rotation state, so both
    gates pass. If the rotation-state table is absent the gate degrades to pass
    (there can be no prior selection to cool down from).
    """
    try:
        ok_token, reason_token = check_token_selection_cooldown(connection, mint, batch_seq)
        ok_pair, reason_pair = check_pair_selection_cooldown(connection, pool, batch_seq)
    except sqlite3.OperationalError:
        return True, ""
    if not ok_token:
        return False, reason_token or "REJECTION_TOKEN_SELECTION_COOLDOWN"
    if not ok_pair:
        return False, reason_pair or "REJECTION_PAIR_SELECTION_COOLDOWN"
    return True, ""


# --------------------------------------------------------------------------- #
# Front door                                                                   #
# --------------------------------------------------------------------------- #

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
) -> dict[str, Any]:
    """Enrich, floor, gate, and select graduated candidates from the registry.

    Reads all confirmed graduated candidates from the durable registry, enriches
    each with governed exact-pool liquidity, applies the $3,000 floor and the
    existing identity / source-quality / STNP / cooldown gates, assigns truthful
    LATEST/PERSISTED provenance, and selects at most one candidate from each
    partition via the frozen categorical two-slot rule. Stops at deterministic
    selected-pair readiness (atomic-handoff compatibility proved, never enqueued).

    ``dexscreener_transport_factory(mint, pool)`` returns the governed exact-pair
    transport for one candidate; when omitted the live
    ``build_dexscreener_pair_snapshot_transport(pool)`` is used. Never raises on an
    ordinary market/liquidity failure — every rejection is recorded honestly.
    """
    now = now or _utc_now_iso()
    latest_set = set(latest_mints)
    if not cycle_seed or not str(cycle_seed).strip():
        raise GraduatedFrontDoorError("MISSING_SELECTION_SEED")
    if dexscreener_transport_factory is None:
        def dexscreener_transport_factory(mint: str, pool: str):  # type: ignore[misc]
            return build_dexscreener_pair_snapshot_transport(pool)

    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    dex_request_count = 0
    try:
        rows = export_graduated_candidates(connection)
        candidates: list[FrontDoorCandidate] = []
        latest_eligible: list[FrontDoorCandidate] = []
        persisted_eligible: list[FrontDoorCandidate] = []
        below_floor = 0
        unproven = 0

        for row in rows[:max_candidates]:
            mint = str(row["mint_identity"])
            pool = str(row["pumpswap_pool"])
            market_identity = str(row["market_identity"])
            lifecycle_state = str(row["lifecycle_state"])
            graduation_block_time = int(row["graduation_block_time"])
            provenance = provenance_for(mint, latest_set)

            transport = dexscreener_transport_factory(mint, pool)
            liquidity = enrich_pool_liquidity(
                connection,
                mint=mint,
                pumpswap_pool=pool,
                dexscreener_transport=transport,
                request_key=f"{request_key_prefix}-liq-{mint}",
                recent_request_count=dex_request_count,
            )
            dex_request_count += 1

            rejection: str | None = None
            # Identity + graduation gate (defense in depth; registry guarantees it).
            expected_identity = f"solana-mainnet:{PUMPSWAP_VENUE}:{pool}"
            if (
                lifecycle_state != GRADUATED_LIFECYCLE
                or market_identity != expected_identity
                or not market_identity.startswith(PUMPSWAP_MARKET_PREFIX)
            ):
                rejection = "IDENTITY_OR_GRADUATION_UNCONFIRMED"
            # Liquidity floor gate.
            elif liquidity.status == LIQUIDITY_BELOW_SELECTION_FLOOR:
                rejection = LIQUIDITY_BELOW_SELECTION_FLOOR
                below_floor += 1
            elif liquidity.status != LIQUIDITY_PROVEN:
                rejection = LIQUIDITY_UNPROVEN
                unproven += 1
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

        selected, mix_state = _mixed_two_slot(
            latest_eligible, persisted_eligible, cycle_seed
        )
        connection.commit()

        selected_latest = next(
            (c for c in selected if c.provenance == LATEST_GRADUATED_CHANNEL), None
        )
        selected_persisted = next(
            (c for c in selected if c.provenance == PERSISTED_GRADUATED_CHANNEL), None
        )
        handoff = _handoff_compatibility(selected)
        ledger = _dexscreener_ledger(connection)
        forbidden = _forbidden_deltas(connection)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        fk_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        connection.close()

    rejected = [c.to_dict() for c in candidates if not c.eligible]
    selected_pair_identity = tuple(sorted(f"{c.mint}|{c.pumpswap_pool}" for c in selected))
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
        "rejected_count": len(rejected),
        "rejected": rejected,
        "mix_state": mix_state,
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
        "selected_latest": (
            None if selected_latest is None else selected_latest.to_dict()
        ),
        "selected_persisted": (
            None if selected_persisted is None else selected_persisted.to_dict()
        ),
        "selected_count": len(selected),
        "selected_pair_identity": selected_pair_identity,
        "handoff_readiness": handoff,
        "source_operation_ledger": ledger,
        "forbidden_capability_deltas": forbidden,
        "forbidden_delta_total": sum(forbidden.values()),
        "integrity_check": integrity,
        "foreign_key_violations": len(fk_violations),
    }

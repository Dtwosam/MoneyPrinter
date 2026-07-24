"""V2-9.7E.44 FULL_PILOT graduated candidate-supply composition (glue only).

Wires the already-adopted E.42 direct-migration discovery and E.43 ``$3,000``
exact-pool front door into the canonical ``FULL_PILOT`` (``run_operational``)
candidate-supply path. This module is pure composition of existing owners: it
adds no source call, gate, score, ranking, provider, selector or lifecycle of its
own. Discovery, on-chain graduation verification, the durable graduated registry,
exact-pool liquidity enrichment, the ``$3,000`` floor and the frozen mixed
two-slot selection remain owned entirely by the E.42/E.43 owners.

Design: ``docs/printer-v1-v2-9-7e-44-full-pilot-supply-integration-design.md``.

For each front-door-*selected* graduated candidate it builds the two carriers the
existing ``run_operational`` admission path consumes:

* a ``FixtureOriginProof`` carrying ``origin_route="GRADUATION_NATIVE"`` — the
  V2-9.7E.45 typed graduation-native carrier (Route B). ``signature`` is the real
  on-chain migration signature (the graduation-lineage proof under the E.41
  graduation-only law), ``slot``/``block_time`` the graduation slot/block time, and
  ``bonding_curve`` the **real** Pump bonding-curve PDA derived deterministically
  from the mint (no fabricated address). The historical Pump create transaction is
  never re-fetched and is never fabricated; the migration signature is never
  persisted into a create-signature field; graduation, not the create, is the
  eligibility and activation event.
* a ``FixturePumpSwapProof`` — the exact PumpSwap graduation confirmation bound to
  the confirmed pool.

The composition stops at deterministic selected-pair readiness plus atomic
two-slot handoff readiness. It never enqueues tracking, scheduler, snapshot,
lifecycle or memory work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sqlite3
from typing import Any, Callable, Mapping, Sequence

from printer_v1.discovery.combined_executor import (
    FixtureOriginProof,
    FixturePumpSwapProof,
    PUMPSWAP_PROGRAM_ID,
)
from printer_v1.discovery.direct_migration_discovery import (
    run_direct_migration_discovery,
)
from printer_v1.discovery.graduated_liquidity_front_door import (
    run_graduated_liquidity_front_door,
)
from printer_v1.sources.pumpfun_direct import (
    PUMP_PROGRAM_ID,
    _b58decode,
    derive_program_address,
)
from printer_v1.sources.pumpswap_graduated_registry import (
    lookup_graduated_candidate,
)
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.dexscreener import (
    DEXSCREENER_SOURCE_NAME,
    build_dexscreener_adapter,
    build_dexscreener_fresh_profiles_transport,
)
from printer_v1.sources.governed_execution import (
    execute_source_request_with_governor,
)

# Repair 2C locator dispositions.
LOCATOR_MATCHED_REGISTRY = "LOCATOR_MATCHED_REGISTRY"
LOCATOR_ONLY_NO_GRADUATION_PROOF = "LOCATOR_ONLY_NO_GRADUATION_PROOF"

# Bounded terminal used when the lawful mixed pair is unavailable at the ceiling.
BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL = (
    "BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL"
)


class GraduatedSupplyError(RuntimeError):
    """Fail-closed graduated-supply composition fault."""


def derive_bonding_curve(mint: str) -> str:
    """Derive the real Pump bonding-curve PDA for ``mint`` (no fabrication)."""
    return derive_program_address((b"bonding-curve", _b58decode(mint)), PUMP_PROGRAM_ID)


@dataclass(frozen=True)
class GraduatedSupply:
    """The graduated candidate supply produced for one FULL_PILOT cycle."""

    ready: bool
    terminal: str
    graduated_supply: tuple[FixtureOriginProof, ...]
    graduation_proofs: Mapping[str, FixturePumpSwapProof]
    selected_latest: Mapping[str, Any] | None
    selected_persisted: Mapping[str, Any] | None
    handoff_readiness: Mapping[str, Any]
    discovery_report: Mapping[str, Any]
    front_door_report: Mapping[str, Any]
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    holder_reserve_supply: tuple[FixtureOriginProof, ...] = ()
    holder_reserve_candidates: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "terminal": self.terminal,
            "selected_mints": sorted(self.graduation_proofs),
            "holder_reserve_mints": [
                proof.mint for proof in self.holder_reserve_supply
            ],
            "selected_latest": (
                None if self.selected_latest is None else dict(self.selected_latest)
            ),
            "selected_persisted": (
                None
                if self.selected_persisted is None
                else dict(self.selected_persisted)
            ),
            "handoff_readiness": dict(self.handoff_readiness),
            "diagnostics": dict(self.diagnostics),
        }


def _origin_proof_for(row: Mapping[str, Any]) -> FixtureOriginProof:
    """Build the confirmed-origin carrier from a durable graduated-registry row."""
    mint = str(row["mint_identity"])
    signature = str(row["migration_signature"])
    slot_raw = row["graduation_slot"]
    slot = 0 if slot_raw is None else int(slot_raw)
    if slot < 0:
        slot = 0
    return FixtureOriginProof(
        mint=mint,
        signature=signature,
        slot=slot,
        block_time=int(row["graduation_block_time"]),
        bonding_curve=derive_bonding_curve(mint),
        confirmed=True,
        # V2-9.7E.45: a migration-discovered candidate activates through the typed
        # graduation-native route (Route B). ``signature`` is the migration
        # (graduation-lineage) signature, ``slot``/``block_time`` are the graduation
        # slot/block time. It is never written to the create origin registry.
        origin_route="GRADUATION_NATIVE",
    )


def _graduation_proof_for(row: Mapping[str, Any]) -> FixturePumpSwapProof:
    return FixturePumpSwapProof(
        mint=str(row["mint_identity"]),
        pool_address=str(row["pumpswap_pool"]),
        program_id=PUMPSWAP_PROGRAM_ID,
        confirmed=True,
        ambiguous=False,
    )


def _fresh_profile_mints(payload: Mapping[str, Any]) -> list[str]:
    """Distinct Solana mints from a fresh-profiles payload. Ordering discarded."""
    pairs = payload.get("pairs") if isinstance(payload, Mapping) else None
    if not isinstance(pairs, list):
        return []
    seen: set[str] = set()
    mints: list[str] = []
    for item in pairs:
        if not isinstance(item, Mapping):
            continue
        base = item.get("baseToken")
        addr = None
        if isinstance(base, Mapping):
            addr = base.get("address")
        addr = addr or item.get("mint") or item.get("token_mint")
        if isinstance(addr, str) and addr and addr not in seen:
            seen.add(addr)
            mints.append(addr)
    # Sort to canonical identity order so provider response order confers no
    # advantage whatsoever (recency/rank/boost/popularity are never consulted).
    return sorted(mints)


def run_fresh_profile_locator(
    db_path: str | Path,
    *,
    transport: Callable[[Any], Mapping[str, Any]] | None = None,
    request_key: str = "v2-9-7e-45-locator",
    now: str | None = None,
) -> dict[str, Any]:
    """Run one governed DexScreener fresh-profile locator-only request."""
    del now
    transport = transport or build_dexscreener_fresh_profiles_transport()
    adapter = build_dexscreener_adapter(
        enabled=True,
        fixture_transport=transport,
    )
    request = build_governed_source_request(
        DEXSCREENER_SOURCE_NAME,
        "dexscreener_fresh_profiles",
        request_key=request_key,
        tracking_priority=0,
        payload={"request_kind": "dexscreener_fresh_profiles", "chain": "solana"},
    )
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        execution = execute_source_request_with_governor(
            connection,
            request,
            adapter,
            recent_request_count=0,
        )
        result = execution.normalized_result
        if result.failure_type:
            connection.commit()
            return {
                "request_key": request_key,
                "status": (
                    "rate_limited"
                    if result.failure_type == "dexscreener_rate_limited_fixture"
                    else str(result.failure_type)
                ),
                "surfaced_count": 0,
                "matched_count": 0,
                "locator_only_count": 0,
                "matched_mints": [],
                "dispositions": [],
            }

        payload = result.normalized_payload or {}
        mints = _fresh_profile_mints(payload)
        matched: list[str] = []
        dispositions: list[dict[str, str]] = []
        for mint in mints:
            row = lookup_graduated_candidate(connection, mint)
            if row is not None:
                matched.append(mint)
                dispositions.append(
                    {"mint": mint, "disposition": LOCATOR_MATCHED_REGISTRY}
                )
            else:
                dispositions.append(
                    {"mint": mint, "disposition": LOCATOR_ONLY_NO_GRADUATION_PROOF}
                )
        connection.commit()
        return {
            "request_key": request_key,
            "status": "ok",
            "surfaced_count": len(mints),
            "matched_count": len(matched),
            "locator_only_count": len(mints) - len(matched),
            "matched_mints": matched,
            "dispositions": dispositions,
        }
    finally:
        connection.close()


def build_graduated_supply(
    db_path: str | Path,
    *,
    cycle_seed: str,
    migration_transport: Callable[[Any], Mapping[str, Any]],
    verifier_transport_factory: Callable[[str, str], Callable[[Any], Mapping[str, Any]]]
    | None = None,
    dexscreener_transport_factory: Callable[[str, str], Callable[[Any], Mapping[str, Any]]]
    | None = None,
    now: str | None = None,
    collection_rounds: int = 1,
    max_candidates: int = 5,
    settle_seconds: float = 0.0,
    reverify_on_transient: bool = False,
    reverify_settle_seconds: float = 0.0,
    front_door_max_candidates: int = 64,
    discovery_request_key_prefix: str = "v2-9-7e-44",
    front_door_request_key_prefix: str = "v2-9-7e-44",
    batch_seq: int = 1,
    run_locator: bool = False,
    locator_transport: Callable[[Any], Mapping[str, Any]] | None = None,
) -> GraduatedSupply:
    """Compose E.42 discovery + E.43 front door into FULL_PILOT graduated supply.

    Bounded and fail-closed. ``migration_transport`` supplies the PumpPortal
    ``subscribeMigration`` events (live or fixture); the verifier and DexScreener
    factories default to the live governed transports. Returns a ``GraduatedSupply``
    whose ``graduation_proofs``/``graduated_supply`` carry exactly the front-door
    selected candidates (``<= 1 LATEST`` + ``<= 1 PERSISTED``). When fewer than two
    eligible ``$3K+`` candidates exist, ``ready`` is False and ``terminal`` is
    ``BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL`` — market supply is not a code
    defect.
    """
    if not cycle_seed or not str(cycle_seed).strip():
        raise GraduatedSupplyError("MISSING_CYCLE_SEED")

    locator = (
        run_fresh_profile_locator(
            db_path,
            transport=locator_transport,
            request_key=f"{discovery_request_key_prefix}-locator",
            now=now,
        )
        if run_locator
        else {"status": "NOT_REQUESTED", "matched_count": 0}
    )

    # --- E.42 direct-migration discovery (governed, bounded) ----------------
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
    )
    latest_mints = set(discovery.get("confirmed_this_cycle") or ())

    # --- E.43 exact-pool $3K front door + mixed two-slot selection ----------
    front_door = run_graduated_liquidity_front_door(
        db_path,
        cycle_seed=cycle_seed,
        latest_mints=latest_mints,
        dexscreener_transport_factory=dexscreener_transport_factory,
        now=now,
        batch_seq=batch_seq,
        request_key_prefix=front_door_request_key_prefix,
        max_candidates=front_door_max_candidates,
    )

    selected_latest = front_door.get("selected_latest")
    selected_persisted = front_door.get("selected_persisted")
    selected = front_door.get("selected") or ()
    # V2-9.7E.46B: feed the holder funnel from the single combined-pool order so
    # any lawful two-token composition is reachable (no compulsory LATEST+PERSISTED
    # quota). Fall back to the legacy round-robin order only if a caller supplies an
    # older front-door report without the combined key.
    reserve = (
        front_door.get("combined_reserve_order")
        or front_door.get("holder_reserve_order")
        or ()
    )

    # --- Build the confirmed-origin + graduation carriers -------------------
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    supply: list[FixtureOriginProof] = []
    reserve_supply: list[FixtureOriginProof] = []
    reserve_candidates: dict[str, Mapping[str, Any]] = {}
    proofs: dict[str, FixturePumpSwapProof] = {}
    try:
        for item in reserve:
            mint = str(item["mint"])
            row = lookup_graduated_candidate(connection, mint)
            if row is None:  # pragma: no cover - registry guarantees the row
                raise GraduatedSupplyError(f"SELECTED_MINT_NOT_IN_REGISTRY:{mint}")
            proof = _origin_proof_for(row)
            reserve_supply.append(proof)
            reserve_candidates[mint.lower()] = dict(item)
            proofs[mint] = _graduation_proof_for(row)
        selected_mints = {str(item["mint"]).lower() for item in selected}
        supply = [
            proof for proof in reserve_supply
            if proof.mint.lower() in selected_mints
        ]
    finally:
        connection.close()

    # V2-9.7E.46B: readiness is the availability of at least two lawful eligible
    # graduated candidates in the combined reserve pool — of ANY lawful provenance
    # composition — not a compulsory one-LATEST-plus-one-PERSISTED pair. The holder
    # funnel then selects two distinct holder-eligible tokens from this pool. Fewer
    # than two eligible $3K+ candidates is honest market supply, not a code defect.
    ready = len(reserve_supply) >= 2
    terminal = (
        "GRADUATED_SUPPLY_READY"
        if ready
        else BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL
    )
    diagnostics = {
        "confirmed_this_cycle": int(discovery.get("confirmed_count") or 0),
        "latest_graduated_count": int(discovery.get("latest_graduated_count") or 0),
        "persisted_graduated_count": int(
            discovery.get("persisted_graduated_count") or 0
        ),
        "front_door_candidate_count": int(front_door.get("candidate_count") or 0),
        "latest_eligible_count": int(front_door.get("latest_eligible_count") or 0),
        "persisted_eligible_count": int(front_door.get("persisted_eligible_count") or 0),
        "combined_reserve_count": len(reserve_supply),
        "below_floor_count": int(front_door.get("below_floor_count") or 0),
        "unproven_count": int(front_door.get("unproven_count") or 0),
        "selection_floor_usd": front_door.get("selection_floor_usd"),
        "discovery_forbidden_delta_total": int(
            discovery.get("forbidden_delta_total") or 0
        ),
        "front_door_forbidden_delta_total": int(
            front_door.get("forbidden_delta_total") or 0
        ),
        "locator_status": locator.get("status"),
        "locator_matched_count": int(locator.get("matched_count") or 0),
        "integrity_check": front_door.get("integrity_check"),
        "foreign_key_violations": int(front_door.get("foreign_key_violations") or 0),
    }
    return GraduatedSupply(
        ready=ready,
        terminal=terminal,
        graduated_supply=tuple(supply),
        holder_reserve_supply=tuple(reserve_supply),
        holder_reserve_candidates=reserve_candidates,
        graduation_proofs=proofs,
        selected_latest=selected_latest,
        selected_persisted=selected_persisted,
        handoff_readiness=dict(front_door.get("handoff_readiness") or {}),
        discovery_report=discovery,
        front_door_report=front_door,
        diagnostics=diagnostics,
    )

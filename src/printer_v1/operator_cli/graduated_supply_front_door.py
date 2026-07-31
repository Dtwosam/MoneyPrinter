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

# V2-9.7E.46B / V2-9.8B.6 shared production+pilot graduated-supply depth.
# Candidate-supply transport ceilings follow the measured budget architecture.
# Do not raise ceilings or lower floors here.
OPERATIONAL_GRADUATED_SUPPLY_KWARGS: dict[str, object] = {
    "collection_rounds": 1,
    "max_candidates": 5,
    "settle_seconds": 0.0,
    "reverify_on_transient": False,
    "reverify_settle_seconds": 0.0,
    "front_door_max_candidates": 6,
    "run_locator": True,
}


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
    candidate_a: Mapping[str, Any] | None
    candidate_b: Mapping[str, Any] | None
    two_candidate_selection: Mapping[str, Any]
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
            "candidate_a": None if self.candidate_a is None else dict(self.candidate_a),
            "candidate_b": None if self.candidate_b is None else dict(self.candidate_b),
            "two_candidate_selection": dict(self.two_candidate_selection),
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
    # Preserve first-seen order after within-response dedup only. Provider order
    # never becomes a score; lexicographic mint preference is forbidden.
    return mints


STAGE_KIND_LOCATOR = "LOCATOR"


def run_fresh_profile_locator(
    db_path: str | Path,
    *,
    transport: Callable[[Any], Mapping[str, Any]] | None = None,
    request_key: str = "v2-9-7e-45-locator",
    now: str | None = None,
    stage_evidence_sink: Callable[[Mapping[str, Any]], None] | None = None,
    campaign_id: str | None = None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    stage_sequence: int = 1,
) -> dict[str, Any]:
    """Run one governed DexScreener fresh-profile locator-only request.

    When a governed request is attempted and ``stage_evidence_sink`` is supplied,
    exactly one sealed stage evidence block is emitted before return. When the
    locator is genuinely not requested, callers must not invoke this function.
    """
    from printer_v1.sources.campaign_six_unit_accounting import (
        build_campaign_stage_id,
        seal_campaign_stage_evidence,
    )
    from printer_v1.sources.measured_transport import (
        MeasuredTransportLedger,
        record_payload_transports,
    )

    sealed_at = now
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
    from printer_v1.db.sqlite_write_contracts import connect_operational

    measured_ledger = MeasuredTransportLedger(
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
    )
    terminal_status = "COMPLETED"
    terminal_cause: str | None = None
    stage_started = False
    unexpected_exception: BaseException | None = None
    sealed = None
    report: dict[str, Any] = {
        "request_key": request_key,
        "request_id": None,
        "source_requests": 0,
        "status": "not_started",
        "surfaced_count": 0,
        "matched_count": 0,
        "locator_only_count": 0,
        "matched_mints": [],
        "dispositions": [],
    }
    connection = connect_operational(db_path)
    try:
        stage_started = True
        execution = execute_source_request_with_governor(
            connection,
            request,
            adapter,
            recent_request_count=0,
        )
        request_id = int(execution.request_record.id)
        result = execution.normalized_result
        payload = result.normalized_payload or {}
        if isinstance(payload, Mapping):
            try:
                record_payload_transports(
                    measured_ledger,
                    payload,
                    default_stage="DEXSCREENER_DISCOVERY",
                )
            except Exception:
                # Declared identities only; never invent transports from DB rows.
                pass

        if result.failure_type:
            connection.commit()
            report = {
                "request_key": request_key,
                "request_id": request_id,
                "source_requests": 1,
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
            terminal_status = "BLOCKED"
            terminal_cause = str(result.failure_type)
        else:
            mints = _fresh_profile_mints(payload if isinstance(payload, Mapping) else {})
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
                        {
                            "mint": mint,
                            "disposition": LOCATOR_ONLY_NO_GRADUATION_PROOF,
                        }
                    )
            connection.commit()
            usable = bool(mints)
            report = {
                "request_key": request_key,
                "request_id": request_id,
                "source_requests": 1,
                "status": "ok" if usable else "empty",
                "surfaced_count": len(mints),
                "matched_count": len(matched),
                "locator_only_count": len(mints) - len(matched),
                "matched_mints": matched,
                "dispositions": dispositions,
            }
            if usable:
                terminal_status = "COMPLETED"
                terminal_cause = None
            else:
                terminal_status = "BLOCKED"
                terminal_cause = "LOCATOR_NO_USABLE_DATA"
    except BaseException as exc:
        unexpected_exception = exc
        terminal_status = "FAILED"
        terminal_cause = f"{type(exc).__name__}:{exc}"
        raise
    finally:
        connection.close()
        # Seal started stages exactly once before an unexpected exception escapes.
        if stage_evidence_sink is not None and (
            stage_started or measured_ledger.source_transport_operations > 0
        ):
            sink_error: BaseException | None = None
            try:
                if not all(
                    str(value or "").strip()
                    for value in (campaign_id, run_id, cycle_id)
                ):
                    raise GraduatedSupplyError(
                        "LOCATOR_STAGE_SINK_REQUIRES_CAMPAIGN_RUN_CYCLE_IDENTITY"
                    )
                sealed = seal_campaign_stage_evidence(
                    ledger=measured_ledger,
                    stage_id=build_campaign_stage_id(
                        campaign_id=str(campaign_id),
                        run_id=str(run_id),
                        cycle_id=str(cycle_id),
                        stage_kind=STAGE_KIND_LOCATOR,
                        stage_sequence=int(stage_sequence),
                    ),
                    stage_kind=STAGE_KIND_LOCATOR,
                    stage_sequence=int(stage_sequence),
                    stage_terminal_status=terminal_status,
                    stage_first_terminal_cause=terminal_cause,
                    campaign_id=str(campaign_id),
                    run_id=str(run_id),
                    cycle_id=str(cycle_id),
                    sealed_at=sealed_at,
                )
                stage_evidence_sink(sealed)
                report["sealed_stage_evidence"] = sealed
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
    return report


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
    discovery_operation_budget: int | None = None,
    deadline_at: str | None = None,
    campaign_id: str | None = None,
    execution_id: str | None = None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    required_token_capacity: int = 2,
    tracking_precheck: bool = False,
    stage_evidence_sink: Callable[[Mapping[str, Any]], None] | None = None,
) -> GraduatedSupply:
    """Compose discovery + front door via persistent multi-round supply loop.

    V2-9.8B.21: ``front_door_max_candidates`` bounds **one evaluation batch**, not
    the entire discovery universe. The canonical Eligible Token Supply service
    continues bounded batches inside this campaign until two distinct freshly
    eligible tokens are reserved or honest exhaustion is proven.

    ``migration_transport`` supplies one frozen/live Solana RPC response for
    each separately governed direct Pump live-tail operation. When fewer than
    two eligible ``$3K+`` candidates exist
    after governed exhaustion, ``ready`` is False and ``terminal`` is
    ``BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL`` with an exhaustion certificate.
    """
    if not cycle_seed or not str(cycle_seed).strip():
        raise GraduatedSupplyError("MISSING_CYCLE_SEED")

    from printer_v1.discovery.eligible_token_supply import (
        DEFAULT_DISCOVERY_OPERATION_BUDGET,
        run_persistent_eligible_token_supply,
    )

    persistent = run_persistent_eligible_token_supply(
        db_path,
        cycle_seed=cycle_seed,
        migration_transport=migration_transport,
        verifier_transport_factory=verifier_transport_factory,
        dexscreener_transport_factory=dexscreener_transport_factory,
        locator_transport=locator_transport,
        now=now,
        collection_rounds=collection_rounds,
        max_candidates=max_candidates,
        settle_seconds=settle_seconds,
        reverify_on_transient=reverify_on_transient,
        reverify_settle_seconds=reverify_settle_seconds,
        front_door_max_candidates=front_door_max_candidates,
        discovery_request_key_prefix=discovery_request_key_prefix,
        front_door_request_key_prefix=front_door_request_key_prefix,
        batch_seq=batch_seq,
        run_locator=run_locator,
        required_token_capacity=required_token_capacity,
        discovery_operation_budget=(
            DEFAULT_DISCOVERY_OPERATION_BUDGET
            if discovery_operation_budget is None
            else int(discovery_operation_budget)
        ),
        deadline_at=deadline_at,
        campaign_id=campaign_id,
        execution_id=execution_id,
        run_id=run_id,
        cycle_id=cycle_id,
        locator_runner=run_fresh_profile_locator if run_locator else None,
        tracking_precheck=tracking_precheck,
        # Pass the campaign sink unchanged; child stages emit once each.
        # Do not re-emit evidence already sealed by child stages.
        stage_evidence_sink=stage_evidence_sink,
    )

    discovery = dict(persistent.discovery_report)
    front_door = dict(persistent.front_door_report)
    locator = dict(persistent.locator_report)
    reserve = (
        front_door.get("combined_reserve_order")
        or front_door.get("holder_reserve_order")
        or ()
    )
    # Prefer the campaign eligible reserve (fresh) when available.
    if persistent.eligible_reserve:
        reserve = [
            {
                "mint": c["mint"],
                "pool": c.get("pumpswap_pool") or c.get("pool"),
                "market_identity": c.get("market_identity"),
                "provenance": c.get("provenance"),
                "lifecycle_state": c.get("lifecycle_state"),
                "graduation_block_time": c.get("graduation_block_time"),
                "liquidity": dict(c.get("liquidity") or {
                    "status": c.get("liquidity_status"),
                    "liquidity_usd": c.get("liquidity_usd"),
                }),
                "historical_reserve_evidence": c.get(
                    "historical_reserve_evidence"
                ),
                "tracking_handoff": dict(c.get("tracking_handoff") or {}),
                "tracking_requalification_required": bool(
                    c.get("tracking_requalification_required")
                ),
                "eligible": True,
                "rejection": None,
            }
            for c in persistent.eligible_reserve
        ]

    from printer_v1.discovery.selection_authority import (
        candidate_from_front_door_mapping,
        select_two_candidates,
    )

    # Canonical neutral two-candidate contract over the eligible reserve.
    authority = select_two_candidates(
        [candidate_from_front_door_mapping(item) for item in reserve],
        cycle_seed=cycle_seed,
    )
    selected = [item.as_dict() for item in authority.selected]
    authority_dict = authority.as_dict()
    candidate_a = authority_dict.get("candidate_a")
    candidate_b = authority_dict.get("candidate_b")

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
        if authority.ready and len(supply) >= required_token_capacity:
            # Preserve authority order for the two selected mints.
            ordered: list[FixtureOriginProof] = []
            for item in selected:
                mint = str(item["mint"]).lower()
                for proof in supply:
                    if proof.mint.lower() == mint and proof not in ordered:
                        ordered.append(proof)
                        break
            supply = ordered[:required_token_capacity]
    finally:
        connection.close()

    ready = bool(authority.ready) and len(supply) == required_token_capacity
    terminal = (
        "GRADUATED_SUPPLY_READY"
        if ready
        else BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL
    )
    diagnostics = dict(persistent.diagnostics)
    diagnostics.update(
        {
            "combined_reserve_count": len(reserve_supply),
            "locator_status": locator.get("status"),
            "locator_matched_count": int(locator.get("matched_count") or 0),
            "locator_source_requests": int(locator.get("source_requests") or 0),
            "two_candidate_selection": authority_dict,
            "provenance_diagnostics": {
                "composition_label": authority_dict.get("composition_label"),
                "provenance_summary": authority_dict.get("provenance_summary"),
            },
            "exhaustion_certificate": (
                None
                if persistent.exhaustion_certificate is None
                else persistent.exhaustion_certificate.to_dict()
            ),
            "shortage_classification": persistent.shortage_classification,
            "discovery_rounds": persistent.discovery_rounds,
        }
    )
    return GraduatedSupply(
        ready=ready,
        terminal=terminal,
        graduated_supply=tuple(supply),
        holder_reserve_supply=tuple(reserve_supply),
        holder_reserve_candidates=reserve_candidates,
        graduation_proofs=proofs,
        candidate_a=None if candidate_a is None else dict(candidate_a),
        candidate_b=None if candidate_b is None else dict(candidate_b),
        two_candidate_selection=authority_dict,
        handoff_readiness=dict(front_door.get("handoff_readiness") or {}),
        discovery_report=discovery,
        front_door_report=front_door,
        diagnostics=diagnostics,
    )

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
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import sqlite3
from typing import Any, Callable, Mapping, Sequence

from printer_v1.discovery.combined_executor import (
    FixtureOriginProof,
    FixturePumpSwapProof,
    PUMPSWAP_PROGRAM_ID,
)
from printer_v1.discovery.memory_observation_activation import AdmissionAuthority
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
CANDIDATE_SUPPLY_READY = "CANDIDATE_SUPPLY_READY"
BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL = (
    "BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL"
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
    "permanent_availability": True,
    "run_geckoterminal_nomination": True,
}


class GraduatedSupplyError(RuntimeError):
    """Fail-closed graduated-supply composition fault."""


class CandidateTemporalAuthority(str, Enum):
    """Source-honest temporal authority for one admitted candidate."""

    DIRECT_PUMP_GRADUATION_TIME = "DIRECT_PUMP_GRADUATION_TIME"
    RETAINED_MARKET_OBSERVATION_TIME = "RETAINED_MARKET_OBSERVATION_TIME"


@dataclass(frozen=True)
class CandidateTemporalContext:
    """Immutable, validated temporal context owned by one candidate admission."""

    temporal_authority: CandidateTemporalAuthority
    admission_observed_at_utc: str
    pump_origin_block_time_epoch: int | None


def _epoch_to_utc_iso(epoch: int) -> str:
    """Convert a positive Unix epoch seconds value to timezone-aware UTC ISO."""
    return datetime.fromtimestamp(int(epoch), tz=timezone.utc).isoformat()


def _require_positive_graduation_epoch(raw: object, *, mint: str) -> int:
    """Fail closed unless ``raw`` is an exact positive integer Unix epoch.

    Accepts only ``type(raw) is int`` and ``raw > 0``. Booleans, floats
    (including ``1.0``), strings, Decimal, null, zero and negative values fail
    closed. Does not coerce via ``int(raw)``. Before return, proves the epoch is
    convertible with ``datetime.fromtimestamp(raw, tz=timezone.utc)``.
    """
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        raise GraduatedSupplyError(
            f"DIRECT_CANDIDATE_GRADUATION_TIME_MISSING:{mint}"
        )
    if type(raw) is not int or raw <= 0:
        raise GraduatedSupplyError(
            f"DIRECT_CANDIDATE_GRADUATION_TIME_INVALID:{mint}"
        )
    try:
        datetime.fromtimestamp(raw, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise GraduatedSupplyError(
            f"DIRECT_CANDIDATE_GRADUATION_TIME_INVALID:{mint}"
        ) from exc
    return raw


def _market_observation_time_utc(item: Mapping[str, Any], *, mint: str) -> str:
    """Source market observation time only from retained market evidence fields.

    Accepts top-level ``liquidity_observed_at`` or nested
    ``liquidity.liquidity_observed_at``. Never falls back to now, evaluation
    time, request time, evidence expiry, or DB/file timestamps.
    """
    raw = item.get("liquidity_observed_at")
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        liquidity = item.get("liquidity")
        if isinstance(liquidity, Mapping):
            raw = liquidity.get("liquidity_observed_at")
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        raise GraduatedSupplyError(
            f"MARKET_CANDIDATE_OBSERVATION_TIME_MISSING:{mint}"
        )
    text = str(raw).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GraduatedSupplyError(
            f"MARKET_CANDIDATE_OBSERVATION_TIME_INVALID:{mint}"
        ) from exc
    if parsed.tzinfo is None:
        raise GraduatedSupplyError(
            f"MARKET_CANDIDATE_OBSERVATION_TIME_INVALID:{mint}"
        )
    return parsed.astimezone(timezone.utc).isoformat()


def _direct_temporal_context(*, graduation_epoch: int) -> CandidateTemporalContext:
    return CandidateTemporalContext(
        temporal_authority=CandidateTemporalAuthority.DIRECT_PUMP_GRADUATION_TIME,
        admission_observed_at_utc=_epoch_to_utc_iso(graduation_epoch),
        pump_origin_block_time_epoch=int(graduation_epoch),
    )


def _market_temporal_context(
    item: Mapping[str, Any], *, mint: str
) -> CandidateTemporalContext:
    return CandidateTemporalContext(
        temporal_authority=(
            CandidateTemporalAuthority.RETAINED_MARKET_OBSERVATION_TIME
        ),
        admission_observed_at_utc=_market_observation_time_utc(item, mint=mint),
        pump_origin_block_time_epoch=None,
    )


@dataclass(frozen=True)
class SourceSpecificCandidateAdmission:
    """One selected candidate with its carried, source-specific authority."""

    mint: str
    pool_address: str
    market_identity: str
    admission_authority: AdmissionAuthority
    nomination_source: str
    lineage_state: str
    present_pool_confirmed: bool
    temporal_context: CandidateTemporalContext
    origin_proof: FixtureOriginProof | None = None
    pumpswap_proof: FixturePumpSwapProof | None = None

    @property
    def confirmed(self) -> bool:
        return bool(self.present_pool_confirmed)

    @property
    def origin_route(self) -> str:
        if self.origin_proof is not None:
            return str(self.origin_proof.origin_route)
        return self.admission_authority.value

    @property
    def bonding_curve(self) -> str:
        """Legacy direct-Pump curve; market candidates carry the present pool."""
        if self.origin_proof is not None:
            return str(self.origin_proof.bonding_curve)
        return self.pool_address

    @property
    def signature(self) -> str:
        return "" if self.origin_proof is None else str(self.origin_proof.signature)

    @property
    def slot(self) -> int:
        return 0 if self.origin_proof is None else int(self.origin_proof.slot)


def _source_specific_admission_for(
    item: Mapping[str, Any],
) -> SourceSpecificCandidateAdmission:
    """Validate carried authority without consulting the migration registry."""
    mint = str(item.get("mint") or "").strip()
    pool = str(item.get("pool") or item.get("pumpswap_pool") or "").strip()
    market_identity = str(item.get("market_identity") or "").strip()
    if not mint or not pool:
        raise GraduatedSupplyError("CANDIDATE_PRESENT_POOL_IDENTITY_MISSING")
    if not market_identity or not market_identity.endswith(f":{pool}"):
        raise GraduatedSupplyError(
            f"CANDIDATE_PRESENT_POOL_IDENTITY_MISMATCH:{mint}"
        )
    try:
        authority = AdmissionAuthority(
            str(item.get("admission_authority") or "DIRECT_PUMP_PUMPSWAP")
        )
    except ValueError as exc:
        raise GraduatedSupplyError(
            f"CANDIDATE_ADMISSION_AUTHORITY_UNSUPPORTED:{mint}"
        ) from exc
    nomination_source = str(
        item.get("nomination_source") or item.get("provenance") or ""
    ).strip()
    lineage_state = str(item.get("lineage_state") or "UNKNOWN_ORIGIN")
    present_pool_confirmed = item.get("exact_present_pool_confirmed") is True
    if authority is AdmissionAuthority.MARKET_PRESENT_POOL:
        if nomination_source not in {"dexscreener", "geckoterminal"}:
            raise GraduatedSupplyError(
                f"MARKET_CANDIDATE_NOMINATION_SOURCE_UNSUPPORTED:{mint}"
            )
        if not present_pool_confirmed:
            raise GraduatedSupplyError(
                f"MARKET_CANDIDATE_PRESENT_POOL_UNCONFIRMED:{mint}"
            )
        if lineage_state not in {"UNKNOWN_ORIGIN", "NON_PUMP_POOL_CONFIRMED"}:
            raise GraduatedSupplyError(
                f"MARKET_CANDIDATE_UNSUPPORTED_LINEAGE_CLAIM:{mint}"
            )
        temporal = _market_temporal_context(item, mint=mint)
        return SourceSpecificCandidateAdmission(
            mint=mint,
            pool_address=pool,
            market_identity=market_identity,
            admission_authority=authority,
            nomination_source=nomination_source,
            lineage_state=lineage_state,
            present_pool_confirmed=True,
            temporal_context=temporal,
        )

    carried = item.get("direct_pump_evidence")
    if not isinstance(carried, Mapping):
        raise GraduatedSupplyError(f"DIRECT_PUMP_EVIDENCE_MISSING:{mint}")
    if (
        str(carried.get("mint") or "") != mint
        or str(carried.get("pool") or "") != pool
        or str(carried.get("pumpswap_program_id") or "") != PUMPSWAP_PROGRAM_ID
        or carried.get("confirmed") is not True
        or not str(carried.get("migration_signature") or "").strip()
    ):
        raise GraduatedSupplyError(f"DIRECT_PUMP_EVIDENCE_MISMATCH:{mint}")
    graduation_epoch = _require_positive_graduation_epoch(
        carried.get("graduation_block_time"), mint=mint
    )
    temporal = _direct_temporal_context(graduation_epoch=graduation_epoch)
    row = {
        "mint_identity": mint,
        "migration_signature": carried["migration_signature"],
        "graduation_slot": carried.get("graduation_slot"),
        "graduation_block_time": graduation_epoch,
        "pumpswap_pool": pool,
    }
    origin = _origin_proof_for(row)
    pumpswap = _graduation_proof_for(row)
    return SourceSpecificCandidateAdmission(
        mint=mint,
        pool_address=pool,
        market_identity=market_identity,
        admission_authority=authority,
        nomination_source=nomination_source or "direct_pump_migration",
        lineage_state="PUMP_GRADUATION_CONFIRMED",
        present_pool_confirmed=True,
        temporal_context=temporal,
        origin_proof=origin,
        pumpswap_proof=pumpswap,
    )


def derive_bonding_curve(mint: str) -> str:
    """Derive the real Pump bonding-curve PDA for ``mint`` (no fabrication)."""
    return derive_program_address((b"bonding-curve", _b58decode(mint)), PUMP_PROGRAM_ID)


@dataclass(frozen=True)
class GraduatedSupply:
    """The graduated candidate supply produced for one FULL_PILOT cycle."""

    ready: bool
    terminal: str
    graduated_supply: tuple[Any, ...]
    graduation_proofs: Mapping[str, FixturePumpSwapProof]
    candidate_a: Mapping[str, Any] | None
    candidate_b: Mapping[str, Any] | None
    two_candidate_selection: Mapping[str, Any]
    handoff_readiness: Mapping[str, Any]
    discovery_report: Mapping[str, Any]
    front_door_report: Mapping[str, Any]
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    holder_reserve_supply: tuple[Any, ...] = ()
    holder_reserve_candidates: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "terminal": self.terminal,
            "selected_mints": [proof.mint for proof in self.graduated_supply],
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
    transport_identity_observer: Callable[[Any], None] | None = None,
    campaign_id: str | None = None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    stage_sequence: int = 1,
) -> dict[str, Any]:
    """Run one governed DexScreener fresh-profile locator-only request.

    When a governed request is attempted and ``stage_evidence_sink`` is supplied,
    exactly one sealed stage evidence block is emitted before return. When the
    locator is genuinely not requested, callers must not invoke this function.

    ``transport_identity_observer`` is notified at measurement time before seal.
    """
    from printer_v1.sources.campaign_six_unit_accounting import (
        build_campaign_stage_id,
        seal_campaign_stage_evidence,
    )
    from printer_v1.sources.measured_transport import (
        MeasuredTransportError,
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
        on_transport_recorded=transport_identity_observer,
    )
    terminal_status = "COMPLETED"
    terminal_cause: str | None = None
    stage_started = False
    unexpected_exception: BaseException | None = None
    sealed = None
    report: dict[str, Any] = {
        "request_key": request_key,
        "request_id": None,
        "response_id": None,
        "source_requests": 0,
        "source_request_ids": [],
        "source_request_coverage": [],
        "status": "not_started",
        "surfaced_count": 0,
        "matched_count": 0,
        "locator_only_count": 0,
        "matched_mints": [],
        "pool_observations": [],
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
        response_id = (
            None
            if execution.response_record is None
            else int(execution.response_record.id)
        )
        result = execution.normalized_result
        payload = result.normalized_payload or {}
        transport_identity_count = 0
        measurement_failed = False
        measurement_error: str | None = None
        if isinstance(payload, Mapping):
            try:
                before = measured_ledger.source_transport_operations
                record_payload_transports(
                    measured_ledger,
                    payload,
                    default_stage="DEXSCREENER_DISCOVERY",
                )
                transport_identity_count = int(
                    measured_ledger.source_transport_operations - before
                )
            except MeasuredTransportError as exc:
                # Typed measured-transport failure only — never invent transports.
                measurement_failed = True
                measurement_error = (
                    f"TRANSPORT_IDENTITY_MEASUREMENT_FAILED:{exc}"
                )
                transport_identity_count = 0
        from printer_v1.discovery.memory_observation_activation import (
            transport_identity_key_from_mapping,
        )
        transport_identity_keys = []
        for identity in tuple(measured_ledger.transports):
            raw = identity.as_dict() if hasattr(identity, "as_dict") else identity
            if isinstance(raw, Mapping):
                transport_identity_keys.append(
                    list(transport_identity_key_from_mapping(raw))
                )
        pairs = (
            list(payload.get("pairs") or ())
            if isinstance(payload, Mapping)
            else []
        )
        coverage_entry = {
            "source_request_id": request_id,
            "source_name": "dexscreener",
            "request_kind": "dexscreener_fresh_profiles",
            "logical_stage_id": (
                f"{campaign_id}|{run_id}|{cycle_id}|DEXSCREENER_FRESH_LOCATOR|1"
                if campaign_id and run_id and cycle_id
                else f"DEXSCREENER_FRESH_LOCATOR|{request_key}"
            ),
            "transport_identity_count": transport_identity_count,
            "transport_identity_keys": transport_identity_keys,
            "normalized_member_count": len(pairs),
            "terminal_status": "COMPLETED",
        }

        # Transport measurement failure: fail closed for the whole locator.
        # Preserve durable request ID, block coverage, contribute no candidates.
        if measurement_failed:
            connection.commit()
            coverage_entry["terminal_status"] = "BLOCKED"
            coverage_entry["normalized_member_count"] = 0
            report = {
                "request_key": request_key,
                "request_id": request_id,
                "response_id": response_id,
                "source_requests": 1,
                "source_request_ids": [request_id],
                "source_request_coverage": [coverage_entry],
                "status": "accounting_blocked",
                "surfaced_count": 0,
                "matched_count": 0,
                "locator_only_count": 0,
                "matched_mints": [],
                "pool_observations": [],
                "dispositions": [],
                "accounting_blocker": True,
                "accounting_blocker_reason": measurement_error,
            }
            terminal_status = "BLOCKED"
            terminal_cause = measurement_error
        elif result.failure_type:
            connection.commit()
            coverage_entry["terminal_status"] = "BLOCKED"
            report = {
                "request_key": request_key,
                "request_id": request_id,
                "response_id": response_id,
                "source_requests": 1,
                "source_request_ids": [request_id],
                "source_request_coverage": [coverage_entry],
                "status": (
                    "rate_limited"
                    if result.failure_type == "dexscreener_rate_limited_fixture"
                    else str(result.failure_type)
                ),
                "surfaced_count": 0,
                "matched_count": 0,
                "locator_only_count": 0,
                "matched_mints": [],
                "pool_observations": [],
                "dispositions": [],
                "accounting_blocker": False,
                "accounting_blocker_reason": None,
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
                "response_id": response_id,
                "source_requests": 1,
                "source_request_ids": [request_id],
                "source_request_coverage": [coverage_entry],
                "status": "ok" if usable else "empty",
                "surfaced_count": len(mints),
                "matched_count": len(matched),
                "locator_only_count": len(mints) - len(matched),
                "matched_mints": matched,
                "dispositions": dispositions,
                "accounting_blocker": False,
                "accounting_blocker_reason": None,
                "pool_observations": [
                    {
                        "mint": str(
                            item.get("candidate_mint")
                            or item.get("token_mint")
                            or item.get("base_mint")
                            or ""
                        ),
                        "pool": str(item.get("pair_address") or ""),
                        "base_mint": str(item.get("base_mint") or ""),
                        "quote_mint": str(item.get("quote_mint") or ""),
                        "venue": str(item.get("dex_id") or ""),
                        # Preserve exact-pool liquidity at discovery; never
                        # discard available market evidence for the nominated pool.
                        "liquidity_usd": (
                            None
                            if item.get("liquidity_usd") is None
                            and not isinstance(item.get("liquidity"), Mapping)
                            else (
                                item.get("liquidity_usd")
                                if item.get("liquidity_usd") is not None
                                else (
                                    (item.get("liquidity") or {}).get("usd")
                                    if isinstance(item.get("liquidity"), Mapping)
                                    else None
                                )
                            )
                        ),
                    }
                    for item in (
                        payload.get("pairs") or ()
                        if isinstance(payload, Mapping)
                        else ()
                    )
                    if isinstance(item, Mapping)
                    and item.get("pair_address")
                    and (
                        item.get("candidate_mint")
                        or item.get("token_mint")
                        or item.get("base_mint")
                    )
                ],
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


def _compose_graduated_supply_ready(
    *, persistent_ready: bool, authority_ready: bool, supply_count: int,
    required_token_capacity: int, permanent_availability: bool,
) -> bool:
    selection_ready = bool(authority_ready) and int(supply_count) == int(required_token_capacity)
    return selection_ready and (not permanent_availability or bool(persistent_ready))


def build_graduated_supply(
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
    geckoterminal_nomination_transport: Callable[[Any], Mapping[str, Any]] | None = None,
    discovery_operation_budget: int | None = None,
    deadline_at: str | None = None,
    campaign_id: str | None = None,
    execution_id: str | None = None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    required_token_capacity: int = 2,
    tracking_precheck: bool = False,
    stage_evidence_sink: Callable[[Mapping[str, Any]], None] | None = None,
    transport_identity_observer: Callable[[Any], None] | None = None,
    local_validation_identity_observer: Callable[[Any], None] | None = None,
    permanent_availability: bool = False,
    run_geckoterminal_nomination: bool = False,
    enable_geckoterminal_reconciliation: bool = True,
    campaign_source_request_scope: Any | None = None,
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

    Permanent operational mode requires a typed
    ``campaign_source_request_scope`` and refuses legacy static request-key
    defaults before any provider I/O.
    """
    if not cycle_seed or not str(cycle_seed).strip():
        raise GraduatedSupplyError("MISSING_CYCLE_SEED")

    from printer_v1.discovery.eligible_token_supply import (
        DEFAULT_DISCOVERY_OPERATION_BUDGET,
        run_persistent_eligible_token_supply,
    )
    from printer_v1.discovery.permanent_discovery_availability import (
        CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED,
        inspect_preexisting_source_request_scope_collision,
        validate_campaign_source_request_scope,
        validate_permanent_operational_request_prefixes,
    )

    scope_obj = None
    active_discovery_prefix = str(discovery_request_key_prefix)
    active_front_door_prefix = str(front_door_request_key_prefix)
    if permanent_availability:
        if campaign_source_request_scope is None:
            raise GraduatedSupplyError(CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED)
        try:
            scope_obj = validate_campaign_source_request_scope(
                campaign_source_request_scope,
                execution_id=execution_id,
                campaign_id=campaign_id,
                run_id=run_id,
                cycle_id=cycle_id,
            )
            validate_permanent_operational_request_prefixes(
                request_key_root=scope_obj.request_key_root,
                discovery_request_key_prefix=active_discovery_prefix,
                front_door_request_key_prefix=active_front_door_prefix,
            )
        except ValueError as exc:
            raise GraduatedSupplyError(str(exc)) from exc
        # Collision gate: any pre-existing durable row under this root blocks
        # before the first supply provider request.
        import sqlite3

        collision_connection = sqlite3.connect(str(db_path))
        try:
            collision = inspect_preexisting_source_request_scope_collision(
                collision_connection,
                request_key_root=scope_obj.request_key_root,
            )
        finally:
            collision_connection.close()
        if collision.get("status") != "OK":
            raise GraduatedSupplyError(
                str(collision.get("detail") or collision.get("blocker"))
            )
        active_discovery_prefix = scope_obj.request_key_root
        active_front_door_prefix = scope_obj.request_key_root

    persistent = run_persistent_eligible_token_supply(
        db_path,
        cycle_seed=cycle_seed,
        migration_transport=migration_transport,
        verifier_transport_factory=verifier_transport_factory,
        dexscreener_transport_factory=dexscreener_transport_factory,
        dexscreener_batch_transport_factory=dexscreener_batch_transport_factory,
        geckoterminal_reconciliation_transport_factory=(
            geckoterminal_reconciliation_transport_factory
        ),
        locator_transport=locator_transport,
        geckoterminal_nomination_transport=geckoterminal_nomination_transport,
        now=now,
        collection_rounds=collection_rounds,
        max_candidates=max_candidates,
        settle_seconds=settle_seconds,
        reverify_on_transient=reverify_on_transient,
        reverify_settle_seconds=reverify_settle_seconds,
        front_door_max_candidates=front_door_max_candidates,
        discovery_request_key_prefix=active_discovery_prefix,
        front_door_request_key_prefix=active_front_door_prefix,
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
        # Pre-seal verification observer (independent of sealed-stage handoff).
        transport_identity_observer=transport_identity_observer,
        local_validation_identity_observer=local_validation_identity_observer,
        permanent_availability=permanent_availability,
        run_geckoterminal_nomination=run_geckoterminal_nomination,
        enable_geckoterminal_reconciliation=(
            enable_geckoterminal_reconciliation
        ),
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
                **dict(c),
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
                "evidence_expires_at": c.get("evidence_expires_at"),
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

    supply: list[SourceSpecificCandidateAdmission] = []
    reserve_supply: list[SourceSpecificCandidateAdmission] = []
    reserve_candidates: dict[str, Mapping[str, Any]] = {}
    proofs: dict[str, FixturePumpSwapProof] = {}
    for item in reserve:
        admission = _source_specific_admission_for(item)
        reserve_supply.append(admission)
        reserve_candidates[admission.mint.lower()] = dict(item)
        if admission.pumpswap_proof is not None:
            proofs[admission.mint] = admission.pumpswap_proof
    selected_mints = {str(item["mint"]).lower() for item in selected}
    supply = [
        proof for proof in reserve_supply
        if proof.mint.lower() in selected_mints
    ]
    if authority.ready and len(supply) >= required_token_capacity:
        # Preserve authority order for the two selected mints.
        ordered: list[SourceSpecificCandidateAdmission] = []
        for item in selected:
            mint = str(item["mint"]).lower()
            for proof in supply:
                if proof.mint.lower() == mint and proof not in ordered:
                    ordered.append(proof)
                    break
        supply = ordered[:required_token_capacity]

    ready = _compose_graduated_supply_ready(
        persistent_ready=bool(persistent.ready),
        authority_ready=bool(authority.ready),
        supply_count=len(supply),
        required_token_capacity=required_token_capacity,
        permanent_availability=permanent_availability,
    )
    terminal = (
        (CANDIDATE_SUPPLY_READY if permanent_availability else "GRADUATED_SUPPLY_READY")
        if ready
        else (
            BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL
            if permanent_availability
            else BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL
        )
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
            "discovery_request_key_prefix": active_discovery_prefix,
            "front_door_request_key_prefix": active_front_door_prefix,
            "request_key_prefix": active_front_door_prefix,
        }
    )
    if scope_obj is not None:
        diagnostics["campaign_source_request_scope"] = scope_obj.as_dict()
        diagnostics["request_scope_version"] = scope_obj.scope_version
        diagnostics["request_key_root"] = scope_obj.request_key_root
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

"""Immutable retained-evidence contract for WINDOW_15M memory activation.

This module validates already governed evidence.  It never contacts a source,
creates a source request/response/failure, selects a candidate, or starts a
lifecycle.  The existing combined executor remains the activation owner.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
import sqlite3
from typing import Any, Mapping, Sequence

from printer_v1.discovery.permanent_discovery_availability import (
    SOLANA_INFRASTRUCTURE_MINTS,
)
from printer_v1.sources.measured_transport import canonical_transport_identity_key


class ActivationPurpose(str, Enum):
    MEMORY_OBSERVATION = "MEMORY_OBSERVATION"


class AdmissionAuthority(str, Enum):
    """The exact source-specific authority admitting one frozen candidate."""

    MARKET_PRESENT_POOL = "MARKET_PRESENT_POOL"
    DIRECT_PUMP_PUMPSWAP = "DIRECT_PUMP_PUMPSWAP"


class EvidenceRole(str, Enum):
    ORIGIN_LINEAGE = "ORIGIN_LINEAGE"
    PUMPSWAP_CONFIRMATION = "PUMPSWAP_CONFIRMATION"
    MARKET_OBSERVATION = "MARKET_OBSERVATION"


REQUIRED_EVIDENCE_ROLES: tuple[EvidenceRole, ...] = (
    EvidenceRole.ORIGIN_LINEAGE,
    EvidenceRole.PUMPSWAP_CONFIRMATION,
    EvidenceRole.MARKET_OBSERVATION,
)

MEMORY_OBSERVATION_SELECTION_REASON = "memory_observation_frozen_selection"


class MemoryObservationActivationError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}: {detail}")


@dataclass(frozen=True)
class RetainedEvidenceReference:
    evidence_role: EvidenceRole
    source_name: str
    request_kind: str
    source_request_id: int
    source_response_id: int
    source_failure_id: int | None
    transport_identity_keys: tuple[tuple[object, ...], ...]
    observed_at: str
    raw_payload_hash: str
    target_mint: str
    target_pool: str
    campaign_id: str
    campaign_run_id: str
    cycle_id: str


@dataclass(frozen=True)
class ManifestRequestEntry:
    """One durable request ownership row with exact transport binding."""

    source_request_id: int
    source_name: str
    request_kind: str
    logical_stage_id: str
    transport_identity_count: int
    transport_identity_keys: tuple[tuple[object, ...], ...]
    terminal_status: str = "COMPLETED"


@dataclass(frozen=True)
class TrackingFeasibility:
    eligible: bool
    reason_code: str
    tracking_queue_id: int | None
    tracking_queue_status: str | None
    requalification_required: bool
    cooldown_until: str | None
    assessed_at: str


@dataclass(frozen=True)
class FrozenMemoryActivationCandidate:
    slot_ordinal: int
    mint: str
    pool: str
    market_identity: str
    lifecycle_identity: str
    activation_route: str
    provenance: str
    memory_observation_eligible: bool
    fully_eligible: bool
    holder_condition: str
    holder_evidence_status: str
    future_action_eligibility: str
    evidence_expires_at: str
    liquidity_observed_at: str
    tracking_feasibility: TrackingFeasibility
    retained_evidence_references: tuple[RetainedEvidenceReference, ...]
    # Compatibility defaults preserve the historical direct-Pump fixtures while
    # production projection now supplies these fields explicitly per slot.
    admission_authority: AdmissionAuthority = AdmissionAuthority.DIRECT_PUMP_PUMPSWAP
    claims_pump_origin: bool = True
    claims_pumpswap_graduation: bool = True


RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE = (
    "RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE"
)


def required_evidence_roles_for_claims(
    *,
    claims_pump_origin: bool,
    claims_pumpswap_graduation: bool,
) -> tuple[EvidenceRole, ...]:
    """Canonical retained-role matrix from explicit origin/graduation claims."""
    roles: list[EvidenceRole] = []
    if claims_pump_origin:
        roles.append(EvidenceRole.ORIGIN_LINEAGE)
    if claims_pumpswap_graduation:
        roles.append(EvidenceRole.PUMPSWAP_CONFIRMATION)
    roles.append(EvidenceRole.MARKET_OBSERVATION)
    return tuple(roles)


def required_evidence_roles_for_admission_authority(
    admission_authority: AdmissionAuthority,
) -> tuple[EvidenceRole, ...]:
    """Canonical retained-role matrix from one admission authority."""
    claims_pump = admission_authority is AdmissionAuthority.DIRECT_PUMP_PUMPSWAP
    return required_evidence_roles_for_claims(
        claims_pump_origin=claims_pump,
        claims_pumpswap_graduation=claims_pump,
    )


def claims_consistent_with_admission_authority(
    admission_authority: AdmissionAuthority,
    *,
    claims_pump_origin: bool,
    claims_pumpswap_graduation: bool,
) -> bool:
    """Legacy claims may report provenance only when they match authority."""
    expected = admission_authority is AdmissionAuthority.DIRECT_PUMP_PUMPSWAP
    return (
        bool(claims_pump_origin) is expected
        and bool(claims_pumpswap_graduation) is expected
    )


def required_evidence_roles_for_candidate(
    candidate: FrozenMemoryActivationCandidate,
) -> tuple[EvidenceRole, ...]:
    """Return the retained role matrix owned by admission_authority.

    Legacy claims fields must remain consistent with admission_authority. They
    never independently weaken or expand the required-role set.
    """
    if not claims_consistent_with_admission_authority(
        candidate.admission_authority,
        claims_pump_origin=bool(candidate.claims_pump_origin),
        claims_pumpswap_graduation=bool(candidate.claims_pumpswap_graduation),
    ):
        raise MemoryObservationActivationError(
            "ADMISSION_AUTHORITY_CLAIMS_INCONSISTENT",
            f"{candidate.mint}:{candidate.admission_authority.value}",
        )
    return required_evidence_roles_for_admission_authority(candidate.admission_authority)


def qualify_candidate_local_retained_role(
    connection: sqlite3.Connection,
    *,
    role: EvidenceRole,
    mint: str,
    pool: str,
    request_id_raw: object,
    response_id_raw: object,
    failure_id_raw: object = None,
    admission_authority: AdmissionAuthority,
    now: str,
    evidence_expires_at: str | None = None,
) -> tuple[bool, str | None]:
    """Establish qualifying governed candidate-local evidence for one role.

    Reuses the existing retained-response truth contract available before freeze.
    Manifest/transport-set ownership remains final-validator owned when not yet
    assembled at this production stage.
    """
    if request_id_raw is None or response_id_raw is None:
        return False, "RETAINED_EVIDENCE_ROLE_MISSING"
    if failure_id_raw is not None:
        return False, "RETAINED_SUCCESS_HAS_FAILURE"
    if evidence_expires_at:
        try:
            if _parse_instant(
                str(evidence_expires_at), code="CANDIDATE_EVIDENCE_EXPIRY_INVALID"
            ) <= _parse_instant(now, code="ACTIVATION_TIME_INVALID"):
                return False, "CANDIDATE_EVIDENCE_EXPIRED"
        except MemoryObservationActivationError as exc:
            return False, exc.code
    try:
        request_id = int(request_id_raw)
        response_id = int(response_id_raw)
    except (TypeError, ValueError):
        return False, "RETAINED_EVIDENCE_ROLE_MISSING"

    request = connection.execute(
        """SELECT id,source_name,request_kind,request_key,source_status,
                  data_quality_label
           FROM printer_source_requests WHERE id=?""",
        (request_id,),
    ).fetchone()
    if request is None:
        return False, "RETAINED_REQUEST_NOT_FOUND"
    response = connection.execute(
        """SELECT id,source_request_id,source_name,source_status,
                  data_quality_label,response_hash,normalized_payload_json
           FROM printer_source_responses WHERE id=?""",
        (response_id,),
    ).fetchone()
    if response is None:
        return False, "RETAINED_RESPONSE_NOT_FOUND"

    def value(row: sqlite3.Row | tuple[Any, ...], key: str, index: int) -> Any:
        return row[key] if isinstance(row, sqlite3.Row) else row[index]

    if int(value(response, "source_request_id", 1)) != request_id:
        return False, "RETAINED_RESPONSE_CONTRACT_MISMATCH"
    if (
        value(request, "source_status", 4) != "COMPLETE"
        or value(request, "data_quality_label", 5) != "CLEAN_DATA"
    ):
        return False, "RETAINED_REQUEST_CONTRACT_MISMATCH"
    if (
        value(response, "source_status", 3) != "COMPLETE"
        or value(response, "data_quality_label", 4) != "CLEAN_DATA"
    ):
        return False, "RETAINED_RESPONSE_CONTRACT_MISMATCH"
    if value(response, "source_name", 2) != value(request, "source_name", 1):
        return False, "RETAINED_RESPONSE_CONTRACT_MISMATCH"

    source_name = str(value(request, "source_name", 1) or "")
    payload_json = value(response, "normalized_payload_json", 6)
    try:
        if role is EvidenceRole.MARKET_OBSERVATION:
            if source_name in {"dexscreener", "geckoterminal"}:
                _require_market_response_member_binding(
                    payload_json,
                    mint=mint,
                    pool=pool,
                    source_name=source_name,
                    require_solana=(
                        admission_authority is AdmissionAuthority.MARKET_PRESENT_POOL
                    ),
                )
            elif not _payload_matches_target(payload_json, mint=mint, pool=pool):
                return False, "RETAINED_RESPONSE_TARGET_MISMATCH"
        elif not _payload_matches_target(payload_json, mint=mint, pool=pool):
            return False, "RETAINED_RESPONSE_TARGET_MISMATCH"
    except MemoryObservationActivationError as exc:
        return False, exc.code
    return True, None


def assess_retained_evidence_role_completeness(
    *,
    admission_authority: AdmissionAuthority,
    qualifying_roles: Sequence[EvidenceRole] | set[EvidenceRole] | frozenset[EvidenceRole],
    mint: str = "",
    qualification_failures: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Binary pre-freeze completeness against qualifying governed roles."""
    required = required_evidence_roles_for_admission_authority(admission_authority)
    present_set: set[EvidenceRole] = set()
    for role in qualifying_roles:
        if isinstance(role, EvidenceRole):
            present_set.add(role)
        else:
            present_set.add(EvidenceRole(str(role)))
    missing = tuple(role for role in required if role not in present_set)
    return {
        "complete": len(missing) == 0,
        "mint": mint,
        "admission_authority": admission_authority.value,
        "required_roles": tuple(role.value for role in required),
        "present_roles": tuple(
            role.value for role in required if role in present_set
        ),
        "missing_roles": tuple(role.value for role in missing),
        "qualification_failures": dict(qualification_failures or {}),
        "disposition": (
            None
            if not missing
            else RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE
        ),
    }


@dataclass(frozen=True)
class FrozenMemoryActivationSet:
    activation_purpose: ActivationPurpose
    readiness_id: str
    selection_seed: str
    selected: tuple[FrozenMemoryActivationCandidate, ...]
    alternates: tuple[FrozenMemoryActivationCandidate, ...]
    manifest_request_ids: tuple[int, ...]
    manifest_transport_identity_keys: tuple[tuple[object, ...], ...]
    frozen_at: str
    expires_at: str
    manifest_entries: tuple[ManifestRequestEntry, ...] = ()


def transport_identity_key_from_mapping(
    raw: Mapping[str, Any],
) -> tuple[object, ...]:
    """Delegate durable transport identity serialization to the canonical owner."""
    return canonical_transport_identity_key(raw)


def transport_identity_keys_from_payload(
    payload: Mapping[str, Any] | None,
) -> tuple[tuple[object, ...], ...]:
    """Extract exact serialized keys from a measured payload."""
    if not isinstance(payload, Mapping):
        return ()
    identities = payload.get("transport_operation_identities") or ()
    keys: list[tuple[object, ...]] = []
    seen: set[tuple[object, ...]] = set()
    for raw in identities:
        if not isinstance(raw, Mapping):
            continue
        key = transport_identity_key_from_mapping(raw)
        if key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return tuple(keys)


def measure_source_row_ids(connection: sqlite3.Connection) -> dict[str, set[int]]:
    """Capture exact durable source-row ID sets for measured reconciliation."""
    return {
        "source_request_ids": {
            int(row[0])
            for row in connection.execute(
                "SELECT id FROM printer_source_requests"
            ).fetchall()
        },
        "source_response_ids": {
            int(row[0])
            for row in connection.execute(
                "SELECT id FROM printer_source_responses"
            ).fetchall()
        },
        "source_failure_ids": {
            int(row[0])
            for row in connection.execute(
                "SELECT id FROM printer_source_failures"
            ).fetchall()
        },
    }


def reconcile_activation_source_rows(
    *,
    before: Mapping[str, set[int]] | Mapping[str, Sequence[int]],
    after: Mapping[str, set[int]] | Mapping[str, Sequence[int]],
    activation: FrozenMemoryActivationSet,
    request_to_transport_bindings: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Measure pre/post source-row deltas. Never hard-codes empty success."""

    def _as_set(value: object) -> set[int]:
        if value is None:
            return set()
        return {int(item) for item in value}

    before_requests = _as_set(before.get("source_request_ids"))
    before_responses = _as_set(before.get("source_response_ids"))
    before_failures = _as_set(before.get("source_failure_ids"))
    after_requests = _as_set(after.get("source_request_ids"))
    after_responses = _as_set(after.get("source_response_ids"))
    after_failures = _as_set(after.get("source_failure_ids"))

    new_requests = sorted(after_requests - before_requests)
    new_responses = sorted(after_responses - before_responses)
    new_failures = sorted(after_failures - before_failures)

    role_request_ids: dict[str, list[int]] = {
        role.value: [] for role in REQUIRED_EVIDENCE_ROLES
    }
    referenced_manifest_ids: list[int] = []
    for candidate in activation.selected:
        for reference in candidate.retained_evidence_references:
            role_request_ids[reference.evidence_role.value].append(
                int(reference.source_request_id)
            )
            referenced_manifest_ids.append(int(reference.source_request_id))

    manifest_ids = set(int(item) for item in activation.manifest_request_ids)
    unmanifested = sorted(
        rid for rid in referenced_manifest_ids if rid not in manifest_ids
    )
    missing_manifest = sorted(
        rid for rid in manifest_ids if rid not in set(referenced_manifest_ids)
        and rid
        in {
            int(ref.source_request_id)
            for cand in activation.selected
            for ref in cand.retained_evidence_references
        }
    )
    # Referenced IDs not present in the after set are not newly created; they
    # must already have existed before projection.
    missing_or_unmanifested = sorted(set(unmanifested) | set(missing_manifest))

    bindings = list(request_to_transport_bindings or ())
    status = "PASS"
    if new_requests or new_responses or new_failures or unmanifested:
        status = "BLOCKED"

    return {
        "before_source_request_ids": sorted(before_requests),
        "before_source_response_ids": sorted(before_responses),
        "before_source_failure_ids": sorted(before_failures),
        "after_source_request_ids": sorted(after_requests),
        "after_source_response_ids": sorted(after_responses),
        "after_source_failure_ids": sorted(after_failures),
        "newly_created_source_request_ids": new_requests,
        "newly_created_source_response_ids": new_responses,
        "newly_created_source_failure_ids": new_failures,
        # Compatibility aliases used by earlier validators/reports.
        "new_source_request_ids": new_requests,
        "new_source_response_ids": new_responses,
        "new_source_failure_ids": new_failures,
        "referenced_manifest_ids": referenced_manifest_ids,
        "manifest_request_ids": list(activation.manifest_request_ids),
        "per_role_request_ids": role_request_ids,
        "missing_or_unmanifested_ids": missing_or_unmanifested,
        "request_to_transport_binding_results": bindings,
        "reconciliation_status": status,
        "evidence_reuse_kind": "RETAINED_GOVERNED_EVIDENCE_REFERENCE",
    }


def _parse_instant(value: str, *, code: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise MemoryObservationActivationError(code, str(value)) from exc
    if parsed.tzinfo is None:
        raise MemoryObservationActivationError(code, str(value))
    return parsed


def _require_identity(value: object, *, code: str) -> str:
    text = str(value or "").strip()
    if not text or text.upper() == "UNKNOWN":
        raise MemoryObservationActivationError(code)
    return text


def _payload_matches_target(
    raw: object, *, mint: str, pool: str
) -> bool:
    """Whole-payload recursive membership for non-market retained roles only.

    MARKET_OBSERVATION must use exact same-member binding via
    ``_require_market_response_member_binding`` instead.
    """
    try:
        payload = json.loads(str(raw or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return False

    def contains(value: Any, target: str) -> bool:
        if isinstance(value, Mapping):
            return any(contains(item, target) for item in value.values())
        if isinstance(value, (list, tuple)):
            return any(contains(item, target) for item in value)
        return str(value) == target

    return contains(payload, mint) and contains(payload, pool)


_SOLANA_CHAIN_VALUES = frozenset({"solana", "solana-mainnet", "sol"})
_CHAIN_IDENTITY_KEYS = frozenset({"chain", "chainid", "network"})


def _text(value: object) -> str:
    return str(value or "").strip()


def _mapping_identity(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _member_pool_identities(member: Mapping[str, Any]) -> set[str]:
    """Accepted pool/pair fields on one normalized market member."""
    pools: set[str] = set()
    for key in ("pair_address", "pairAddress", "pool", "pool_address", "address"):
        text = _text(member.get(key))
        if text:
            pools.add(text)
    attrs = _mapping_identity(member.get("attributes"))
    if attrs is not None:
        for key in ("address", "pair_address", "pairAddress", "pool_address"):
            text = _text(attrs.get(key))
            if text:
                pools.add(text)
    return pools


def _member_explicit_base_mint_identities(member: Mapping[str, Any]) -> set[str]:
    """Explicit base/target mint fields only (never candidate_mint / quote).

    ``candidate_mint`` is orientation-gated for DexScreener and is resolved by
    ``_classify_dexscreener_member_target``, not by this collector.
    """
    mints: set[str] = set()
    for key in ("base_mint", "token_mint", "mint"):
        text = _text(member.get(key))
        if text:
            mints.add(text)
    base = _mapping_identity(member.get("baseToken"))
    if base is not None:
        text = _text(base.get("address"))
        if text:
            mints.add(text)
    attrs = _mapping_identity(member.get("attributes"))
    if attrs is not None:
        for key in (
            "base_token_address",
            "baseTokenAddress",
            "token_mint",
            "base_mint",
        ):
            text = _text(attrs.get(key))
            if text:
                mints.add(text)
    rels = _mapping_identity(member.get("relationships"))
    if rels is not None:
        base_rel = _mapping_identity(rels.get("base_token"))
        base_data = (
            _mapping_identity(base_rel.get("data")) if base_rel is not None else None
        )
        if base_data is not None:
            raw_id = _text(base_data.get("id"))
            if raw_id:
                # GeckoTerminal relationship ids are often ``solana_<mint>``.
                if raw_id.startswith("solana_"):
                    raw_id = raw_id[len("solana_") :]
                mints.add(raw_id)
    return mints


def _member_base_mint_identities(member: Mapping[str, Any]) -> set[str]:
    """Accepted base/target mint fields on non-DexScreener market members."""
    return set(_member_explicit_base_mint_identities(member))


def _member_quote_mint_identities(member: Mapping[str, Any]) -> set[str]:
    """Accepted quote/infrastructure mint fields on one market member."""
    mints: set[str] = set()
    for key in ("quote_mint", "quoteMint"):
        text = _text(member.get(key))
        if text:
            mints.add(text)
    quote = _mapping_identity(member.get("quoteToken"))
    if quote is not None:
        text = _text(quote.get("address"))
        if text:
            mints.add(text)
    attrs = _mapping_identity(member.get("attributes"))
    if attrs is not None:
        for key in ("quote_token_address", "quoteTokenAddress", "quote_mint"):
            text = _text(attrs.get(key))
            if text:
                mints.add(text)
    rels = _mapping_identity(member.get("relationships"))
    if rels is not None:
        quote_rel = _mapping_identity(rels.get("quote_token"))
        quote_data = (
            _mapping_identity(quote_rel.get("data")) if quote_rel is not None else None
        )
        if quote_data is not None:
            raw_id = _text(quote_data.get("id"))
            if raw_id:
                if raw_id.startswith("solana_"):
                    raw_id = raw_id[len("solana_") :]
                mints.add(raw_id)
    return mints


def _classify_dexscreener_member_target(
    member: Mapping[str, Any], *, mint: str
) -> str:
    """Classify target mint side on one DexScreener normalized pair member.

    Returns one of:
    - ``base``: target is an accepted base identity on this member
    - ``quote_only``: target appears only as quote (including FAIL orientation
      candidate_mint that mirrors the quote side)
    - ``orientation_conflict``: contradictory orientation / base fields
    - ``none``: target not bound as base or quote on this member

    ``candidate_mint`` is accepted as base only when orientation status is
    ``PASS``, the candidate is non-empty, and it agrees with the explicit base
    identity. FAIL/missing/contradictory orientation never promotes quote-side
    ``candidate_mint`` into base identities.
    """
    explicit_bases = _member_explicit_base_mint_identities(member)
    if len(explicit_bases) > 1:
        return "orientation_conflict"

    explicit_base = next(iter(explicit_bases)) if explicit_bases else ""
    quote_mints = _member_quote_mint_identities(member)
    candidate = _text(member.get("candidate_mint"))
    status = _text(member.get("candidate_pair_orientation_status")).upper()
    reason = _text(member.get("candidate_pair_orientation_reason")).upper()

    # PASS while reason claims mismatch is contradictory metadata.
    if status == "PASS" and reason and "MISMATCH" in reason:
        return "orientation_conflict"

    accepted_base: set[str] = set(explicit_bases)

    if status == "PASS":
        if not candidate:
            # Orientation claims PASS without a candidate mint identity.
            return "orientation_conflict"
        if candidate in quote_mints and candidate not in explicit_bases:
            # PASS must never promote a quote-only candidate to base.
            return "orientation_conflict"
        if explicit_base:
            if candidate != explicit_base:
                return "orientation_conflict"
            accepted_base.add(candidate)
        else:
            # PASS candidate requires an agreeing explicit base field.
            return "orientation_conflict"
    # FAIL, missing, empty, or any non-PASS status: never add candidate_mint
    # to base identities. Explicit base fields remain authoritative alone.

    if mint in accepted_base and mint in quote_mints:
        return "orientation_conflict"
    if mint in accepted_base:
        return "base"
    if mint in quote_mints:
        return "quote_only"
    return "none"


def _member_confirms_solana(member: Mapping[str, Any]) -> bool:
    """True only when this exact member carries Solana chain/network identity."""
    for key, item in member.items():
        if str(key).casefold() in _CHAIN_IDENTITY_KEYS:
            if str(item).casefold() in _SOLANA_CHAIN_VALUES:
                return True
    attrs = _mapping_identity(member.get("attributes"))
    if attrs is not None:
        for key, item in attrs.items():
            if str(key).casefold() in _CHAIN_IDENTITY_KEYS:
                if str(item).casefold() in _SOLANA_CHAIN_VALUES:
                    return True
    rels = _mapping_identity(member.get("relationships"))
    if rels is not None:
        network_rel = _mapping_identity(rels.get("network"))
        network_data = (
            _mapping_identity(network_rel.get("data"))
            if network_rel is not None
            else None
        )
        if network_data is not None:
            if str(network_data.get("id") or "").casefold() in _SOLANA_CHAIN_VALUES:
                return True
    resource_id = _text(member.get("id"))
    if resource_id.startswith("solana_"):
        return True
    return False


def _member_looks_like_identity_carrier(member: Mapping[str, Any]) -> bool:
    """Detect a single-member retained envelope carrying pool + mint identity."""
    return bool(_member_pool_identities(member) and (
        _member_base_mint_identities(member) or _member_quote_mint_identities(member)
    ))


def _extract_market_members(
    payload: Mapping[str, Any], *, source_name: str
) -> tuple[list[Mapping[str, Any]] | None, str | None]:
    """Return source-contract members or an unsupported-shape blocker code."""
    pairs = payload.get("pairs")
    if isinstance(pairs, list):
        members = [item for item in pairs if isinstance(item, Mapping)]
        # Empty list is a lawful no-match shape, not an unsupported contract.
        return members, None

    if source_name == "geckoterminal":
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, Mapping)], None
        if isinstance(data, Mapping):
            return [data], None

    # Single-member retained envelope used by historical fixtures and direct
    # Pump market rows that store one bound identity object without a pairs key.
    if "pairs" not in payload and _member_looks_like_identity_carrier(payload):
        return [payload], None

    return None, "MARKET_RESPONSE_UNSUPPORTED_SHAPE"


def _require_market_response_member_binding(
    raw: object,
    *,
    mint: str,
    pool: str,
    source_name: str,
    require_solana: bool,
) -> None:
    """Fail-closed exact same-member mint/pool/(Solana) binding for market evidence.

    Whole-payload recursive membership is intentionally not used: mint, pool,
    and Solana identity must belong to one supported normalized response member.
    """
    if source_name not in {"dexscreener", "geckoterminal"}:
        raise MemoryObservationActivationError(
            "MARKET_ADMISSION_SOURCE_UNSUPPORTED", source_name
        )
    try:
        payload = json.loads(str(raw or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MemoryObservationActivationError(
            "MARKET_RESPONSE_UNSUPPORTED_SHAPE"
        ) from exc
    if not isinstance(payload, Mapping):
        raise MemoryObservationActivationError("MARKET_RESPONSE_UNSUPPORTED_SHAPE")

    members, shape_blocker = _extract_market_members(
        payload, source_name=source_name
    )
    if shape_blocker is not None or members is None:
        raise MemoryObservationActivationError(
            shape_blocker or "MARKET_RESPONSE_UNSUPPORTED_SHAPE"
        )

    exact_matches: list[Mapping[str, Any]] = []
    mint_pool_without_solana: list[Mapping[str, Any]] = []
    quote_only_pool_hits = 0
    orientation_conflict_hits = 0

    for member in members:
        member_pools = _member_pool_identities(member)
        if pool not in member_pools:
            continue

        if source_name == "dexscreener":
            side = _classify_dexscreener_member_target(member, mint=mint)
            if side == "orientation_conflict":
                orientation_conflict_hits += 1
                continue
            if side == "base":
                if _member_confirms_solana(member):
                    exact_matches.append(member)
                else:
                    mint_pool_without_solana.append(member)
            elif side == "quote_only":
                quote_only_pool_hits += 1
            continue

        base_mints = _member_base_mint_identities(member)
        quote_mints = _member_quote_mint_identities(member)
        if mint in base_mints and mint in quote_mints:
            orientation_conflict_hits += 1
            continue
        if mint in base_mints:
            if _member_confirms_solana(member):
                exact_matches.append(member)
            else:
                mint_pool_without_solana.append(member)
        elif mint in quote_mints:
            quote_only_pool_hits += 1

    # Orientation conflicts are fail-closed and take precedence over weaker
    # no-match / quote-only outcomes for the same pool-matching member set.
    if orientation_conflict_hits:
        raise MemoryObservationActivationError(
            "MARKET_RESPONSE_ORIENTATION_CONFLICT", f"{mint}:{pool}"
        )
    if len(exact_matches) > 1:
        raise MemoryObservationActivationError(
            "MARKET_RESPONSE_CONFLICTING_MEMBER_MATCHES",
            f"{mint}:{pool}:{len(exact_matches)}",
        )
    if len(exact_matches) == 1:
        return
    if mint_pool_without_solana:
        if require_solana:
            raise MemoryObservationActivationError(
                "MARKET_ADMISSION_SOLANA_CONFIRMATION_MISSING"
            )
        # Direct Pump market rows may omit chain when exact mint+pool already
        # bind on one member; still reject ambiguous multi-member hits above.
        if len(mint_pool_without_solana) == 1:
            return
        raise MemoryObservationActivationError(
            "MARKET_RESPONSE_CONFLICTING_MEMBER_MATCHES",
            f"{mint}:{pool}:{len(mint_pool_without_solana)}",
        )
    if quote_only_pool_hits:
        raise MemoryObservationActivationError(
            "MARKET_RESPONSE_TARGET_IS_QUOTE_ONLY", mint
        )
    raise MemoryObservationActivationError(
        "MARKET_RESPONSE_NO_EXACT_MEMBER_MATCH", f"{mint}:{pool}"
    )


def _retained_observation_time_matches(
    connection: sqlite3.Connection,
    *,
    mint: str,
    pool: str,
    request_id: int,
    response_id: int,
    observed_at: str,
    normalized_payload_json: object,
) -> bool:
    """Match exact observation time from payload or its durable reserve row."""
    try:
        payload = json.loads(str(normalized_payload_json or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {}

    def contains(value: Any, target: str) -> bool:
        if isinstance(value, Mapping):
            return any(contains(item, target) for item in value.values())
        if isinstance(value, (list, tuple)):
            return any(contains(item, target) for item in value)
        return str(value) == target

    if contains(payload, observed_at):
        return True
    rows = connection.execute(
        """SELECT observed_at,evidence_json,source_provenance_json
           FROM printer_discovery_reserve_layers
           WHERE network='solana-mainnet' AND mint_identity=? AND pool_address=?
             AND observed_at=?""",
        (mint, pool, observed_at),
    ).fetchall()
    for row in rows:
        combined = f"{row[1] or ''} {row[2] or ''}"
        if str(request_id) in combined and str(response_id) in combined:
            return True
    return False


def _manifest_entries_for_activation(
    activation: FrozenMemoryActivationSet,
) -> tuple[dict[int, ManifestRequestEntry], bool]:
    """Index exact request ownership.

    Returns ``(by_id, exact_binding)`` where ``exact_binding`` is True only when
    typed per-request transport ownership entries were supplied.
    """
    by_id: dict[int, ManifestRequestEntry] = {}
    if activation.manifest_entries:
        for entry in activation.manifest_entries:
            rid = int(entry.source_request_id)
            if rid in by_id:
                raise MemoryObservationActivationError(
                    "ACTIVATION_MANIFEST_DUPLICATE_REQUEST", str(rid)
                )
            by_id[rid] = entry
        return by_id, True

    # Compatibility path for fixtures that still pass flat keys only. Exact
    # request ownership is not claimed; per-reference keys must still be
    # non-empty and present in the flat measured key set.
    for rid in activation.manifest_request_ids:
        by_id[int(rid)] = ManifestRequestEntry(
            source_request_id=int(rid),
            source_name="",
            request_kind="",
            logical_stage_id="",
            transport_identity_count=0,
            transport_identity_keys=(),
            terminal_status="COMPLETED",
        )
    return by_id, False


def _validate_request_transport_binding(
    *,
    reference: RetainedEvidenceReference,
    manifest_entry: ManifestRequestEntry | None,
    all_request_owned_keys: Mapping[int, set[tuple[object, ...]]],
    expected_ownership: tuple[str, str, str] | None,
    flat_transport_keys: set[tuple[object, ...]],
    exact_binding: bool,
) -> dict[str, Any]:
    """Fail-closed exact request-to-transport binding for one retained reference."""
    request_id = int(reference.source_request_id)
    keys = tuple(tuple(item) for item in reference.transport_identity_keys)
    result: dict[str, Any] = {
        "source_request_id": request_id,
        "evidence_role": reference.evidence_role.value,
        "transport_identity_keys": [list(item) for item in keys],
        "status": "PASS",
        "blocker": None,
    }

    if not keys:
        result["status"] = "BLOCKED"
        result["blocker"] = "RETAINED_REQUEST_TRANSPORT_IDENTITY_MISSING"
        raise MemoryObservationActivationError(
            "RETAINED_REQUEST_TRANSPORT_IDENTITY_MISSING",
            f"request={request_id}",
        )

    if manifest_entry is None:
        result["status"] = "BLOCKED"
        result["blocker"] = "RETAINED_REQUEST_NOT_IN_MANIFEST"
        raise MemoryObservationActivationError(
            "RETAINED_REQUEST_NOT_IN_MANIFEST", str(request_id)
        )

    if not exact_binding:
        # Flat-key compatibility: membership only, no source-name/kind fallback.
        # An empty measured key set cannot accept any retained transport key.
        if not flat_transport_keys:
            result["status"] = "BLOCKED"
            result["blocker"] = "RETAINED_TRANSPORT_IDENTITY_MISSING"
            raise MemoryObservationActivationError(
                "RETAINED_TRANSPORT_IDENTITY_MISSING",
                f"request={request_id}",
            )
        for key in keys:
            if tuple(key) not in flat_transport_keys:
                result["status"] = "BLOCKED"
                result["blocker"] = "RETAINED_TRANSPORT_IDENTITY_MISSING"
                raise MemoryObservationActivationError(
                    "RETAINED_TRANSPORT_IDENTITY_MISSING",
                    f"request={request_id}",
                )
        if expected_ownership is not None:
            campaign_id, run_id, cycle_id = expected_ownership
            if (
                reference.campaign_id != campaign_id
                or reference.campaign_run_id != run_id
                or reference.cycle_id != cycle_id
            ):
                result["status"] = "BLOCKED"
                result["blocker"] = "RETAINED_OWNERSHIP_MISMATCH"
                raise MemoryObservationActivationError(
                    "RETAINED_OWNERSHIP_MISMATCH",
                    f"request={request_id}",
                )
        result["logical_stage_id"] = ""
        result["declared_transport_identity_count"] = len(keys)
        return result

    owned_keys = tuple(
        tuple(item) for item in manifest_entry.transport_identity_keys
    )
    owned_set = {tuple(item) for item in owned_keys}
    for key in keys:
        if tuple(key) not in owned_set:
            foreign_owners = [
                rid
                for rid, key_set in all_request_owned_keys.items()
                if rid != request_id and tuple(key) in key_set
            ]
            if foreign_owners:
                result["status"] = "BLOCKED"
                result["blocker"] = "RETAINED_TRANSPORT_IDENTITY_FOREIGN_REQUEST"
                raise MemoryObservationActivationError(
                    "RETAINED_TRANSPORT_IDENTITY_FOREIGN_REQUEST",
                    f"request={request_id}:foreign={foreign_owners[0]}",
                )
            result["status"] = "BLOCKED"
            result["blocker"] = "RETAINED_TRANSPORT_IDENTITY_MISSING"
            raise MemoryObservationActivationError(
                "RETAINED_TRANSPORT_IDENTITY_MISSING",
                f"request={request_id}",
            )

    declared_count = int(manifest_entry.transport_identity_count)
    if declared_count != len(owned_keys):
        result["status"] = "BLOCKED"
        result["blocker"] = "RETAINED_TRANSPORT_IDENTITY_COUNT_MISMATCH"
        raise MemoryObservationActivationError(
            "RETAINED_TRANSPORT_IDENTITY_COUNT_MISMATCH",
            f"request={request_id}:declared={declared_count}:keys={len(owned_keys)}",
        )
    if set(keys) != owned_set or len(keys) != declared_count:
        result["status"] = "BLOCKED"
        result["blocker"] = "RETAINED_TRANSPORT_IDENTITY_COUNT_MISMATCH"
        raise MemoryObservationActivationError(
            "RETAINED_TRANSPORT_IDENTITY_COUNT_MISMATCH",
            f"request={request_id}:ref={len(keys)}:declared={declared_count}",
        )

    if manifest_entry.source_name and manifest_entry.source_name != reference.source_name:
        result["status"] = "BLOCKED"
        result["blocker"] = "RETAINED_REQUEST_CONTRACT_MISMATCH"
        raise MemoryObservationActivationError(
            "RETAINED_REQUEST_CONTRACT_MISMATCH",
            f"source_name request={request_id}",
        )
    if (
        manifest_entry.request_kind
        and manifest_entry.request_kind != reference.request_kind
    ):
        result["status"] = "BLOCKED"
        result["blocker"] = "RETAINED_REQUEST_CONTRACT_MISMATCH"
        raise MemoryObservationActivationError(
            "RETAINED_REQUEST_CONTRACT_MISMATCH",
            f"request_kind request={request_id}",
        )

    stage = str(manifest_entry.logical_stage_id or "").strip()
    if not stage:
        result["status"] = "BLOCKED"
        result["blocker"] = "RETAINED_LOGICAL_STAGE_MISSING"
        raise MemoryObservationActivationError(
            "RETAINED_LOGICAL_STAGE_MISSING", str(request_id)
        )

    if expected_ownership is not None:
        campaign_id, run_id, cycle_id = expected_ownership
        # Stage ownership must match the current activation command, not values
        # copied only from the reference payload.
        expected_prefix = f"{campaign_id}|{run_id}|{cycle_id}|"
        if not stage.startswith(expected_prefix):
            result["status"] = "BLOCKED"
            result["blocker"] = "RETAINED_LOGICAL_STAGE_OWNERSHIP_MISMATCH"
            raise MemoryObservationActivationError(
                "RETAINED_LOGICAL_STAGE_OWNERSHIP_MISMATCH",
                f"request={request_id}:stage={stage}",
            )
        if (
            reference.campaign_id != campaign_id
            or reference.campaign_run_id != run_id
            or reference.cycle_id != cycle_id
        ):
            result["status"] = "BLOCKED"
            result["blocker"] = "RETAINED_OWNERSHIP_MISMATCH"
            raise MemoryObservationActivationError(
                "RETAINED_OWNERSHIP_MISMATCH",
                f"request={request_id}",
            )

    if manifest_entry.terminal_status == "COMPLETED" and declared_count == 0:
        result["status"] = "BLOCKED"
        result["blocker"] = "RETAINED_REQUEST_TRANSPORT_IDENTITY_MISSING"
        raise MemoryObservationActivationError(
            "RETAINED_REQUEST_TRANSPORT_IDENTITY_MISSING",
            f"request={request_id}",
        )

    result["logical_stage_id"] = stage
    result["declared_transport_identity_count"] = declared_count
    return result


def validate_memory_activation_set(
    connection: sqlite3.Connection,
    activation: FrozenMemoryActivationSet,
    *,
    now: str,
    expected_ownership: tuple[str, str, str] | None = None,
    source_ids_before: Mapping[str, set[int] | Sequence[int]] | None = None,
    source_ids_after: Mapping[str, set[int] | Sequence[int]] | None = None,
) -> dict[str, Any]:
    """Validate one exact frozen pair and its original governed evidence rows.

    The returned reconciliation is scoped to the referenced IDs.  No table-wide
    count is used as evidence and this function performs no INSERT/UPDATE/DELETE.
    """
    if activation.activation_purpose is not ActivationPurpose.MEMORY_OBSERVATION:
        raise MemoryObservationActivationError("ACTIVATION_PURPOSE_UNSUPPORTED")
    _require_identity(activation.readiness_id, code="READINESS_ID_MISSING")
    _require_identity(activation.selection_seed, code="SELECTION_SEED_MISSING")
    instant = _parse_instant(now, code="ACTIVATION_TIME_INVALID")
    if _parse_instant(activation.expires_at, code="ACTIVATION_EXPIRY_INVALID") <= instant:
        raise MemoryObservationActivationError("ACTIVATION_SET_EXPIRED")
    if len(activation.selected) != 2:
        raise MemoryObservationActivationError("ACTIVATION_SELECTED_PAIR_INCOMPLETE")
    if len(activation.alternates) != 2:
        raise MemoryObservationActivationError(
            "ACTIVATION_REPORT_ALTERNATES_INCOMPLETE"
        )
    if [item.slot_ordinal for item in activation.selected] != [1, 2]:
        raise MemoryObservationActivationError("ACTIVATION_SLOT_ORDER_INVALID")
    if len(set(activation.manifest_request_ids)) != len(
        activation.manifest_request_ids
    ):
        raise MemoryObservationActivationError("ACTIVATION_MANIFEST_DUPLICATE_REQUEST")

    manifest_by_id, exact_binding = _manifest_entries_for_activation(activation)
    manifest_ids = set(manifest_by_id)
    if set(int(item) for item in activation.manifest_request_ids) != manifest_ids:
        # Flat id list must agree with typed entries when both are supplied.
        if exact_binding:
            raise MemoryObservationActivationError(
                "ACTIVATION_MANIFEST_ID_SET_MISMATCH"
            )

    # Build exact ownership index: each transport key may belong to one request.
    all_request_owned_keys: dict[int, set[tuple[object, ...]]] = {}
    key_owners: dict[tuple[object, ...], int] = {}
    if exact_binding:
        for rid, entry in manifest_by_id.items():
            owned = {tuple(item) for item in entry.transport_identity_keys}
            all_request_owned_keys[rid] = owned
            for key in owned:
                prior = key_owners.get(key)
                if prior is not None and prior != rid:
                    raise MemoryObservationActivationError(
                        "RETAINED_TRANSPORT_IDENTITY_SHARED_ACROSS_REQUESTS",
                        f"key_owner={prior}:other={rid}",
                    )
                key_owners[key] = rid

    transport_keys = {
        tuple(item) for item in activation.manifest_transport_identity_keys
    }
    if exact_binding:
        # When exact entries exist, the flat set must equal the union of owned keys.
        owned_union: set[tuple[object, ...]] = set()
        for owned in all_request_owned_keys.values():
            owned_union |= owned
        if transport_keys and transport_keys != owned_union:
            raise MemoryObservationActivationError(
                "ACTIVATION_MANIFEST_TRANSPORT_SET_MISMATCH"
            )
        transport_keys = owned_union

    seen_mints: set[str] = set()
    seen_pools: set[str] = set()
    reference_request_ids: list[int] = []
    reference_response_ids: list[int] = []
    binding_results: list[dict[str, Any]] = []
    role_request_ids: dict[str, list[int]] = {
        role.value: [] for role in REQUIRED_EVIDENCE_ROLES
    }

    ownership_scope = expected_ownership
    if ownership_scope is None and activation.selected:
        first_ref = activation.selected[0].retained_evidence_references[0]
        ownership_scope = (
            first_ref.campaign_id,
            first_ref.campaign_run_id,
            first_ref.cycle_id,
        )

    for candidate in activation.selected:
        mint = _require_identity(candidate.mint, code="ACTIVATION_MINT_MISSING")
        pool = _require_identity(candidate.pool, code="ACTIVATION_POOL_MISSING")
        if mint in SOLANA_INFRASTRUCTURE_MINTS:
            raise MemoryObservationActivationError("INFRASTRUCTURE_MINT_EXCLUDED")
        if candidate.admission_authority is AdmissionAuthority.MARKET_PRESENT_POOL:
            if candidate.claims_pump_origin or candidate.claims_pumpswap_graduation:
                raise MemoryObservationActivationError(
                    "MARKET_ADMISSION_PUMP_CLAIM_WITHOUT_DIRECT_AUTHORITY"
                )
        elif candidate.admission_authority is AdmissionAuthority.DIRECT_PUMP_PUMPSWAP:
            if not candidate.claims_pump_origin or not candidate.claims_pumpswap_graduation:
                raise MemoryObservationActivationError(
                    "DIRECT_PUMP_ADMISSION_CLAIMS_INCOMPLETE"
                )
        else:  # pragma: no cover - enum construction normally prevents this
            raise MemoryObservationActivationError("ADMISSION_AUTHORITY_UNSUPPORTED")
        _require_identity(candidate.market_identity, code="ACTIVATION_MARKET_IDENTITY_MISSING")
        _require_identity(candidate.lifecycle_identity, code="ACTIVATION_LIFECYCLE_IDENTITY_MISSING")
        if not candidate.market_identity.endswith(f":{pool}"):
            raise MemoryObservationActivationError("ACTIVATION_MARKET_IDENTITY_MISMATCH")
        if mint in seen_mints or pool in seen_pools:
            raise MemoryObservationActivationError("ACTIVATION_SELECTED_IDENTITY_DUPLICATE")
        seen_mints.add(mint)
        seen_pools.add(pool)
        if candidate.memory_observation_eligible is not True:
            raise MemoryObservationActivationError("MEMORY_OBSERVATION_INELIGIBLE")
        tracking = candidate.tracking_feasibility
        if not tracking.eligible or tracking.requalification_required:
            raise MemoryObservationActivationError(
                "TRACKING_FEASIBILITY_INELIGIBLE", tracking.reason_code
            )
        _parse_instant(tracking.assessed_at, code="TRACKING_ASSESSMENT_TIME_INVALID")
        if _parse_instant(
            candidate.evidence_expires_at, code="CANDIDATE_EVIDENCE_EXPIRY_INVALID"
        ) <= instant:
            raise MemoryObservationActivationError("CANDIDATE_EVIDENCE_EXPIRED", mint)
        _parse_instant(
            candidate.liquidity_observed_at, code="LIQUIDITY_OBSERVED_AT_INVALID"
        )
        holder_pass = candidate.holder_condition in {
            "HOLDER_CONCENTRATION_PASS",
            "HOLDER_CONCENTRATION_HEALTHY",
        }
        if candidate.fully_eligible and not holder_pass:
            raise MemoryObservationActivationError("FULLY_ELIGIBLE_WITHOUT_HOLDER_PASS")
        if not holder_pass and candidate.future_action_eligibility == "ELIGIBLE":
            raise MemoryObservationActivationError("FUTURE_ACTION_ELIGIBILITY_OVERSTATED")
        if not candidate.retained_evidence_references:
            raise MemoryObservationActivationError("RETAINED_EVIDENCE_MISSING", mint)

        roles_present = {
            reference.evidence_role
            for reference in candidate.retained_evidence_references
        }
        required_roles = required_evidence_roles_for_candidate(candidate)
        for required_role in required_roles:
            if required_role not in roles_present:
                raise MemoryObservationActivationError(
                    "RETAINED_EVIDENCE_ROLE_MISSING",
                    f"{mint}:{required_role.value}",
                )
        if roles_present != set(required_roles):
            raise MemoryObservationActivationError(
                "RETAINED_EVIDENCE_ROLE_NOT_ASSERTED", mint
            )
        if len(roles_present) != len(candidate.retained_evidence_references):
            raise MemoryObservationActivationError(
                "RETAINED_EVIDENCE_ROLE_DUPLICATE", mint
            )

        for reference in candidate.retained_evidence_references:
            if reference.source_failure_id is not None:
                raise MemoryObservationActivationError("RETAINED_SUCCESS_HAS_FAILURE")
            if reference.target_mint != mint or reference.target_pool != pool:
                raise MemoryObservationActivationError(
                    "RETAINED_EVIDENCE_TARGET_MISMATCH"
                )
            scope = (
                _require_identity(reference.campaign_id, code="RETAINED_CAMPAIGN_ID_MISSING"),
                _require_identity(reference.campaign_run_id, code="RETAINED_RUN_ID_MISSING"),
                _require_identity(reference.cycle_id, code="RETAINED_CYCLE_ID_MISSING"),
            )
            if ownership_scope is not None and scope != ownership_scope:
                raise MemoryObservationActivationError("RETAINED_OWNERSHIP_MISMATCH")
            request_id = int(reference.source_request_id)
            response_id = int(reference.source_response_id)
            if request_id not in manifest_ids:
                raise MemoryObservationActivationError("RETAINED_REQUEST_NOT_IN_MANIFEST")

            binding = _validate_request_transport_binding(
                reference=reference,
                manifest_entry=manifest_by_id.get(request_id),
                all_request_owned_keys=all_request_owned_keys,
                expected_ownership=ownership_scope,
                flat_transport_keys=transport_keys,
                exact_binding=exact_binding,
            )
            binding_results.append(binding)

            for key in reference.transport_identity_keys:
                if transport_keys and tuple(key) not in transport_keys:
                    raise MemoryObservationActivationError(
                        "RETAINED_TRANSPORT_IDENTITY_MISSING"
                    )

            request = connection.execute(
                """SELECT id,source_name,request_kind,request_key,source_status,
                          data_quality_label
                   FROM printer_source_requests WHERE id=?""",
                (request_id,),
            ).fetchone()
            if request is None:
                raise MemoryObservationActivationError("RETAINED_REQUEST_NOT_FOUND")
            response = connection.execute(
                """SELECT id,source_request_id,source_name,source_status,
                          data_quality_label,response_hash,normalized_payload_json
                   FROM printer_source_responses WHERE id=?""",
                (response_id,),
            ).fetchone()
            if response is None:
                raise MemoryObservationActivationError("RETAINED_RESPONSE_NOT_FOUND")

            def value(row: sqlite3.Row | tuple[Any, ...], key: str, index: int) -> Any:
                return row[key] if isinstance(row, sqlite3.Row) else row[index]

            if (
                value(request, "source_name", 1) != reference.source_name
                or value(request, "request_kind", 2) != reference.request_kind
                or value(request, "source_status", 4) != "COMPLETE"
                or value(request, "data_quality_label", 5) != "CLEAN_DATA"
            ):
                raise MemoryObservationActivationError("RETAINED_REQUEST_CONTRACT_MISMATCH")
            if (
                int(value(response, "source_request_id", 1)) != request_id
                or value(response, "source_name", 2) != reference.source_name
                or value(response, "source_status", 3) != "COMPLETE"
                or value(response, "data_quality_label", 4) != "CLEAN_DATA"
                or value(response, "response_hash", 5) != reference.raw_payload_hash
            ):
                raise MemoryObservationActivationError("RETAINED_RESPONSE_CONTRACT_MISMATCH")
            if reference.evidence_role is EvidenceRole.MARKET_OBSERVATION:
                _require_market_response_member_binding(
                    value(response, "normalized_payload_json", 6),
                    mint=mint,
                    pool=pool,
                    source_name=reference.source_name,
                    require_solana=(
                        candidate.admission_authority
                        is AdmissionAuthority.MARKET_PRESENT_POOL
                    ),
                )
            elif not _payload_matches_target(
                value(response, "normalized_payload_json", 6),
                mint=mint,
                pool=pool,
            ):
                raise MemoryObservationActivationError("RETAINED_RESPONSE_TARGET_MISMATCH")
            if not _retained_observation_time_matches(
                connection,
                mint=mint,
                pool=pool,
                request_id=request_id,
                response_id=response_id,
                observed_at=reference.observed_at,
                normalized_payload_json=value(
                    response, "normalized_payload_json", 6
                ),
            ):
                raise MemoryObservationActivationError(
                    "RETAINED_OBSERVATION_TIME_MISMATCH"
                )
            reference_request_ids.append(request_id)
            reference_response_ids.append(response_id)
            role_request_ids[reference.evidence_role.value].append(request_id)

    # Measured reconciliation: when pre/post snapshots are supplied, use them.
    # Validation itself must not create rows; when snapshots are omitted, measure
    # the live connection once so the report is never a hard-coded empty pass.
    measured_before = (
        dict(source_ids_before)
        if source_ids_before is not None
        else measure_source_row_ids(connection)
    )
    measured_after = (
        dict(source_ids_after)
        if source_ids_after is not None
        else measure_source_row_ids(connection)
    )
    reconciliation = reconcile_activation_source_rows(
        before=measured_before,
        after=measured_after,
        activation=activation,
        request_to_transport_bindings=binding_results,
    )
    reconciliation.update(
        {
            "activation_reference_request_ids": reference_request_ids,
            "activation_reference_response_ids": reference_response_ids,
            "per_role_request_ids": role_request_ids,
            "missing_transport_identity_keys": [],
            "unmanifested_reference_ids": reconciliation.get(
                "missing_or_unmanifested_ids", []
            ),
        }
    )
    return reconciliation


def role_reference_for_candidate(
    candidate: FrozenMemoryActivationCandidate,
    role: EvidenceRole,
) -> RetainedEvidenceReference:
    for reference in candidate.retained_evidence_references:
        if reference.evidence_role is role:
            return reference
    raise MemoryObservationActivationError(
        "RETAINED_EVIDENCE_ROLE_MISSING", f"{candidate.mint}:{role.value}"
    )


__all__ = [
    "AdmissionAuthority",
    "ActivationPurpose",
    "EvidenceRole",
    "FrozenMemoryActivationCandidate",
    "FrozenMemoryActivationSet",
    "MEMORY_OBSERVATION_SELECTION_REASON",
    "ManifestRequestEntry",
    "MemoryObservationActivationError",
    "REQUIRED_EVIDENCE_ROLES",
    "RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE",
    "RetainedEvidenceReference",
    "TrackingFeasibility",
    "assess_retained_evidence_role_completeness",
    "claims_consistent_with_admission_authority",
    "measure_source_row_ids",
    "qualify_candidate_local_retained_role",
    "reconcile_activation_source_rows",
    "required_evidence_roles_for_admission_authority",
    "required_evidence_roles_for_candidate",
    "required_evidence_roles_for_claims",
    "role_reference_for_candidate",
    "transport_identity_key_from_mapping",
    "transport_identity_keys_from_payload",
    "validate_memory_activation_set",
]

"""V2-9.7E.45 / V2-9.8B — explicit pilot-input readiness boundary.

Writes one immutable ``PILOT_INPUT_READY`` bundle (migration 041) when all
required gates for the selected readiness purpose are satisfied.

Readiness purposes (V2-9.8B remaining runtime repair):

* ``FUTURE_ACTION`` (default / legacy) — requires holder eligibility.
* ``MEMORY_OBSERVATION`` — memory freeze handoff; does **not** require holder
  eligibility; requires ``memory_observation_eligible=True`` plus market floor,
  exact pool, lawful activation route, and valid evidence context.

The owner enqueues no snapshot/lifecycle/memory work and consumes no campaign
authorization. It fails closed if any gate is unmet. The bundle is immutable; when
mandatory evidence expires, the caller builds a NEW readiness identity rather than
mutating the old bundle.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Mapping

SELECTION_FLOOR_USD = 3000.0
LAWFUL_ROUTES = frozenset({"GRADUATION_NATIVE", "PUMP_CREATE"})

READINESS_PURPOSE_FUTURE_ACTION = "FUTURE_ACTION"
READINESS_PURPOSE_MEMORY_OBSERVATION = "MEMORY_OBSERVATION"
LAWFUL_READINESS_PURPOSES = frozenset(
    {
        READINESS_PURPOSE_FUTURE_ACTION,
        READINESS_PURPOSE_MEMORY_OBSERVATION,
    }
)

READINESS_READY = "PILOT_INPUT_READY"
BLOCKED_DISCOVERY = "PILOT_INPUT_BLOCKED_DISCOVERY"
BLOCKED_SELECTION = "PILOT_INPUT_BLOCKED_SELECTION"
BLOCKED_MARKET = "PILOT_INPUT_BLOCKED_MARKET"
BLOCKED_HOLDER = "PILOT_INPUT_BLOCKED_HOLDER"
BLOCKED_ACTIVATION = "PILOT_INPUT_BLOCKED_ACTIVATION"
BLOCKED_MEMORY_OBSERVATION = "PILOT_INPUT_BLOCKED_MEMORY_OBSERVATION"


class PilotInputReadinessError(RuntimeError):
    """Fail-closed readiness-boundary fault."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}: {detail}")


@dataclass(frozen=True)
class ReadinessCandidate:
    mint: str
    pool: str
    market_identity: str
    liquidity_usd: float
    liquidity_observed_at: str
    activation_route: str
    holder_eligible: bool
    provenance: str  # LATEST_GRADUATED | PERSISTED_GRADUATED
    # Memory-observation context (optional; required True for MEMORY_OBSERVATION).
    memory_observation_eligible: bool = False
    holder_condition: str = "UNKNOWN"
    future_action_eligibility: str = "BLOCKED_OR_UNKNOWN"
    admission_authority: str | None = None
    slot_ordinal: int | None = None
    tracking_eligible: bool | None = None
    tracking_reason: str | None = None
    tracking_requalification_required: bool = False
    retained_source_request_ids: tuple[int, ...] = ()
    retained_source_response_ids: tuple[int, ...] = ()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def evaluate_readiness_gates(
    latest: ReadinessCandidate | None,
    persisted: ReadinessCandidate | None,
    *,
    discovery_universe_evaluated: bool,
    readiness_purpose: str = READINESS_PURPOSE_FUTURE_ACTION,
) -> str:
    """Return ``PILOT_INPUT_READY`` or the first failed gate terminal (fail-closed).

    Default purpose ``FUTURE_ACTION`` preserves legacy holder-gated semantics.
    ``MEMORY_OBSERVATION`` admits observation-eligible candidates without holder pass.
    """
    purpose = str(readiness_purpose or READINESS_PURPOSE_FUTURE_ACTION).strip()
    if purpose not in LAWFUL_READINESS_PURPOSES:
        return BLOCKED_SELECTION
    if not discovery_universe_evaluated:
        return BLOCKED_DISCOVERY
    if latest is None or persisted is None:
        return BLOCKED_SELECTION
    for candidate in (latest, persisted):
        if (
            candidate.liquidity_usd < SELECTION_FLOOR_USD
            or not candidate.pool
            or not candidate.mint
        ):
            return BLOCKED_MARKET
    if purpose == READINESS_PURPOSE_MEMORY_OBSERVATION:
        for candidate in (latest, persisted):
            if candidate.memory_observation_eligible is not True:
                return BLOCKED_MEMORY_OBSERVATION
        # Holder eligibility is context only for memory observation readiness.
    else:
        for candidate in (latest, persisted):
            if not candidate.holder_eligible:
                return BLOCKED_HOLDER
    for candidate in (latest, persisted):
        if candidate.activation_route not in LAWFUL_ROUTES:
            return BLOCKED_ACTIVATION
    return READINESS_READY


def _candidate_surface(candidate: ReadinessCandidate) -> dict[str, Any]:
    return {
        "mint": candidate.mint,
        "pool": candidate.pool,
        "market_identity": candidate.market_identity,
        "liquidity_usd": candidate.liquidity_usd,
        "liquidity_observed_at": candidate.liquidity_observed_at,
        "activation_route": candidate.activation_route,
        "admission_authority": candidate.admission_authority,
        "provenance": candidate.provenance,
        "holder_eligible": bool(candidate.holder_eligible),
        "memory_observation_eligible": bool(candidate.memory_observation_eligible),
        "holder_condition": str(candidate.holder_condition or "UNKNOWN"),
        "future_action_eligibility": str(
            candidate.future_action_eligibility or "BLOCKED_OR_UNKNOWN"
        ),
        "slot_ordinal": candidate.slot_ordinal,
        "tracking_feasibility": {
            "eligible": candidate.tracking_eligible,
            "reason": candidate.tracking_reason,
            "requalification_required": bool(
                candidate.tracking_requalification_required
            ),
        },
        "retained_source_request_ids": list(
            candidate.retained_source_request_ids
        ),
        "retained_source_response_ids": list(
            candidate.retained_source_response_ids
        ),
    }


def _bundle_payload(
    *,
    readiness_id: str,
    latest: ReadinessCandidate,
    persisted: ReadinessCandidate,
    holder_evidence: Mapping[str, Any],
    source_ledger: Mapping[str, Any],
    selection_seed: str,
    git_provenance_identity: str,
    configuration_hash: str,
    expires_at: str,
    readiness_purpose: str,
) -> dict[str, Any]:
    return {
        "readiness_id": readiness_id,
        "readiness_state": READINESS_READY,
        "readiness_purpose": readiness_purpose,
        # ``latest`` and ``persisted`` are frozen migration-041 column names.
        # They are positional compatibility fields, never selection/provenance
        # authority.  The ordered surface below is the truthful contract.
        "latest": _candidate_surface(latest),
        "persisted": _candidate_surface(persisted),
        "legacy_candidate_fields": "POSITIONAL_COMPATIBILITY_ONLY",
        "ordered_selected_candidates": [
            _candidate_surface(latest),
            _candidate_surface(persisted),
        ],
        "holder_evidence": dict(holder_evidence),
        "source_ledger": dict(source_ledger),
        "selection_seed": selection_seed,
        "git_provenance_identity": git_provenance_identity,
        "configuration_hash": configuration_hash,
        "expires_at": expires_at,
    }


def build_pilot_input_ready_bundle(
    connection: sqlite3.Connection,
    *,
    readiness_id: str,
    latest: ReadinessCandidate,
    persisted: ReadinessCandidate,
    holder_evidence: Mapping[str, Any],
    source_ledger: Mapping[str, Any],
    selection_seed: str,
    git_provenance_identity: str,
    configuration_hash: str,
    expires_at: str,
    now: str,
    discovery_universe_evaluated: bool = True,
    readiness_purpose: str = READINESS_PURPOSE_FUTURE_ACTION,
) -> dict[str, Any]:
    """Persist one immutable PILOT_INPUT_READY bundle. Fail-closed if a gate is unmet.

    Idempotent for a byte-identical re-write (same ``readiness_id`` + same
    ``bundle_hash``); a conflicting re-write for a known id fails closed as
    ``READINESS_BUNDLE_CONFLICT`` (the bundle is immutable).
    """
    purpose = str(readiness_purpose or READINESS_PURPOSE_FUTURE_ACTION).strip()
    if purpose not in LAWFUL_READINESS_PURPOSES:
        raise PilotInputReadinessError("READINESS_PURPOSE_UNSUPPORTED", purpose)
    gate = evaluate_readiness_gates(
        latest,
        persisted,
        discovery_universe_evaluated=discovery_universe_evaluated,
        readiness_purpose=purpose,
    )
    if gate != READINESS_READY:
        raise PilotInputReadinessError("READINESS_GATE_UNMET", gate)
    if latest.mint == persisted.mint:
        raise PilotInputReadinessError("READINESS_DUPLICATE_MINT", latest.mint)

    # Durable purpose + memory/action context live in source_ledger JSON so
    # existing schema preserves them without migration 053.
    durable_ledger = dict(source_ledger)
    durable_ledger["readiness_purpose"] = purpose
    durable_ledger["memory_observation_context"] = {
        "latest": {
            "memory_observation_eligible": latest.memory_observation_eligible,
            "holder_eligible": latest.holder_eligible,
            "holder_condition": latest.holder_condition,
            "future_action_eligibility": latest.future_action_eligibility,
        },
        "persisted": {
            "memory_observation_eligible": persisted.memory_observation_eligible,
            "holder_eligible": persisted.holder_eligible,
            "holder_condition": persisted.holder_condition,
            "future_action_eligibility": persisted.future_action_eligibility,
        },
    }
    durable_ledger["legacy_candidate_fields"] = "POSITIONAL_COMPATIBILITY_ONLY"
    durable_ledger["ordered_selected_candidates"] = [
        _candidate_surface(latest),
        _candidate_surface(persisted),
    ]

    payload = _bundle_payload(
        readiness_id=readiness_id,
        latest=latest,
        persisted=persisted,
        holder_evidence=holder_evidence,
        source_ledger=durable_ledger,
        selection_seed=selection_seed,
        git_provenance_identity=git_provenance_identity,
        configuration_hash=configuration_hash,
        expires_at=expires_at,
        readiness_purpose=purpose,
    )
    bundle_hash = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()

    existing = connection.execute(
        "SELECT bundle_hash FROM printer_pilot_input_readiness_bundle "
        "WHERE readiness_id = ?",
        (readiness_id,),
    ).fetchone()
    if existing is not None:
        if str(existing[0]) == bundle_hash:
            return {**payload, "bundle_hash": bundle_hash, "created_at": None}
        raise PilotInputReadinessError("READINESS_BUNDLE_CONFLICT", readiness_id)

    provenance = {
        "latest": latest.provenance,
        "persisted": persisted.provenance,
        "legacy_candidate_fields": "POSITIONAL_COMPATIBILITY_ONLY",
        "ordered_provenance": [latest.provenance, persisted.provenance],
        "readiness_purpose": purpose,
    }
    connection.execute(
        """
        INSERT INTO printer_pilot_input_readiness_bundle(
            readiness_id, readiness_state,
            latest_mint, latest_pool, latest_market_identity, latest_liquidity_usd,
            latest_liquidity_observed_at, latest_activation_route,
            persisted_mint, persisted_pool, persisted_market_identity,
            persisted_liquidity_usd, persisted_liquidity_observed_at,
            persisted_activation_route,
            holder_evidence_json, source_ledger_json,
            latest_persisted_provenance_json,
            selection_seed, git_provenance_identity, configuration_hash,
            expires_at, bundle_hash, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            readiness_id,
            READINESS_READY,
            latest.mint,
            latest.pool,
            latest.market_identity,
            float(latest.liquidity_usd),
            latest.liquidity_observed_at,
            latest.activation_route,
            persisted.mint,
            persisted.pool,
            persisted.market_identity,
            float(persisted.liquidity_usd),
            persisted.liquidity_observed_at,
            persisted.activation_route,
            _canonical(dict(holder_evidence)),
            _canonical(durable_ledger),
            _canonical(provenance),
            selection_seed,
            git_provenance_identity,
            configuration_hash,
            expires_at,
            bundle_hash,
            now,
        ),
    )
    connection.commit()
    return {**payload, "bundle_hash": bundle_hash, "created_at": now}


def load_pilot_input_ready_bundle(
    connection: sqlite3.Connection, readiness_id: str
) -> Mapping[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM printer_pilot_input_readiness_bundle WHERE readiness_id = ?",
        (readiness_id,),
    ).fetchone()
    if row is None:
        return None
    keys = [c[0] for c in connection.execute(
        "SELECT name FROM pragma_table_info('printer_pilot_input_readiness_bundle')"
    ).fetchall()]
    return dict(zip(keys, row))

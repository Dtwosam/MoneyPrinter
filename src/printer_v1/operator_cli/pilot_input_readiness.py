"""V2-9.7E.45 Repair 6 — explicit pilot-input readiness boundary.

Writes one immutable ``PILOT_INPUT_READY`` bundle (migration 041) only when all
five readiness gates are simultaneously satisfied for one lawful LATEST + one
lawful PERSISTED graduated candidate:

    DISCOVERY_READY  - durable candidate universe evaluated
    SELECTION_READY  - one lawful LATEST and one lawful PERSISTED identified
    MARKET_READY     - both pass fresh exact-pool $3K front door + categorical gates
    HOLDER_READY     - both pass the existing holder-evidence contract
    ACTIVATION_READY - both pass graduation-native / create-native activation validation

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

READINESS_READY = "PILOT_INPUT_READY"
BLOCKED_DISCOVERY = "PILOT_INPUT_BLOCKED_DISCOVERY"
BLOCKED_SELECTION = "PILOT_INPUT_BLOCKED_SELECTION"
BLOCKED_MARKET = "PILOT_INPUT_BLOCKED_MARKET"
BLOCKED_HOLDER = "PILOT_INPUT_BLOCKED_HOLDER"
BLOCKED_ACTIVATION = "PILOT_INPUT_BLOCKED_ACTIVATION"


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


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def evaluate_readiness_gates(
    latest: ReadinessCandidate | None,
    persisted: ReadinessCandidate | None,
    *,
    discovery_universe_evaluated: bool,
) -> str:
    """Return ``PILOT_INPUT_READY`` or the first failed gate terminal (fail-closed)."""
    if not discovery_universe_evaluated:
        return BLOCKED_DISCOVERY
    if latest is None or persisted is None:
        return BLOCKED_SELECTION
    for candidate in (latest, persisted):
        if candidate.liquidity_usd < SELECTION_FLOOR_USD or not candidate.pool:
            return BLOCKED_MARKET
    for candidate in (latest, persisted):
        if not candidate.holder_eligible:
            return BLOCKED_HOLDER
    for candidate in (latest, persisted):
        if candidate.activation_route not in LAWFUL_ROUTES:
            return BLOCKED_ACTIVATION
    return READINESS_READY


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
) -> dict[str, Any]:
    return {
        "readiness_id": readiness_id,
        "readiness_state": READINESS_READY,
        "latest": {
            "mint": latest.mint,
            "pool": latest.pool,
            "market_identity": latest.market_identity,
            "liquidity_usd": latest.liquidity_usd,
            "liquidity_observed_at": latest.liquidity_observed_at,
            "activation_route": latest.activation_route,
            "provenance": latest.provenance,
        },
        "persisted": {
            "mint": persisted.mint,
            "pool": persisted.pool,
            "market_identity": persisted.market_identity,
            "liquidity_usd": persisted.liquidity_usd,
            "liquidity_observed_at": persisted.liquidity_observed_at,
            "activation_route": persisted.activation_route,
            "provenance": persisted.provenance,
        },
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
) -> dict[str, Any]:
    """Persist one immutable PILOT_INPUT_READY bundle. Fail-closed if a gate is unmet.

    Idempotent for a byte-identical re-write (same ``readiness_id`` + same
    ``bundle_hash``); a conflicting re-write for a known id fails closed as
    ``READINESS_BUNDLE_CONFLICT`` (the bundle is immutable).
    """
    gate = evaluate_readiness_gates(
        latest, persisted, discovery_universe_evaluated=discovery_universe_evaluated
    )
    if gate != READINESS_READY:
        raise PilotInputReadinessError("READINESS_GATE_UNMET", gate)
    if latest.mint == persisted.mint:
        raise PilotInputReadinessError("READINESS_DUPLICATE_MINT", latest.mint)

    payload = _bundle_payload(
        readiness_id=readiness_id,
        latest=latest,
        persisted=persisted,
        holder_evidence=holder_evidence,
        source_ledger=source_ledger,
        selection_seed=selection_seed,
        git_provenance_identity=git_provenance_identity,
        configuration_hash=configuration_hash,
        expires_at=expires_at,
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

    provenance = {"latest": latest.provenance, "persisted": persisted.provenance}
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
            _canonical(dict(source_ledger)),
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

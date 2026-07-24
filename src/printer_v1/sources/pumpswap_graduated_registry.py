"""V2-9.7E.42 durable PumpSwap graduated-candidate registry persistence.

Persists only end-to-end confirmed graduated Pump.fun candidates
(``PUMPSWAP_GRADUATED_CONFIRMED``) into
``printer_pumpswap_graduated_candidate_registry`` (migration 040). Graduation
evidence is immutable; only the cross-cycle observation fields
(``latest_observed_at``, ``latest_channel``, ``observation_count``) may change.

Migration block time is stored as graduation evidence ONLY. There is no
``token_created_at`` column: migration/pool time may never become token creation
time. This module never reads or writes pilot authorizations, campaign/run/cycle
identities, Scheduler jobs, lifecycle state, memory, retrieval, decisions, terminal
causes, positions, trades, audits, or PnL.
"""

from __future__ import annotations

import hashlib
import json
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from printer_v1.sources.pumpfun_direct import PUMP_PROGRAM_ID
from printer_v1.sources.pumpswap import (
    PUMPSWAP_AMM_PROGRAM_ID,
    _PUMPSWAP_POOL_BASE_MINT_OFFSET,
)

CONTRACT_VERSION = "V2-9.7E.42"
GRADUATED_LIFECYCLE = "PUMPSWAP_GRADUATED_CONFIRMED"
PUMPSWAP_VENUE = "pumpswap"

LATEST_GRADUATED_CHANNEL = "LATEST_GRADUATED"
# V2-9.7E.43: the persisted graduated candidate label. The former
# "PERSISTED_ACTIVE" label claimed post-selection *activity* that no snapshot has
# ever proved in the discovery lane; it is replaced by the truthful
# PERSISTED_GRADUATED (confirmed graduated before the current cycle, not
# rediscovered as a current-cycle migration). Behavioral categories
# (DUMP/DECAY/REVIVAL/CONSOLIDATION) are never derived in discovery.
PERSISTED_GRADUATED_CHANNEL = "PERSISTED_GRADUATED"
# Deprecated E.42 name kept for import compatibility; it now resolves to the
# truthful PERSISTED_GRADUATED value.
PERSISTED_ACTIVE_CHANNEL = PERSISTED_GRADUATED_CHANNEL


class GraduatedCandidateError(RuntimeError):
    """Fail-closed durable graduated-candidate registry fault."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}: {detail}")


_EXPORT_COLUMNS = (
    "mint_identity", "migration_signature", "migration_provenance", "pumpswap_pool",
    "pumpswap_program_id", "pump_program_id", "base_mint_offset",
    "graduation_block_time", "graduation_slot", "lifecycle_state", "market_identity",
    "discovery_channel", "confirmation_evidence_hash", "contract_version",
    "first_observed_at", "latest_observed_at", "latest_channel", "observation_count",
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def market_identity_for_pool(pool: str) -> str:
    return f"solana-mainnet:{PUMPSWAP_VENUE}:{pool}"


def graduation_evidence_hash(
    *,
    mint: str,
    migration_signature: str,
    pumpswap_pool: str,
    graduation_block_time: int,
    graduation_slot: int | None,
    base_mint_offset: int,
) -> str:
    """sha256 of the canonical graduation-evidence payload. Never a raw response."""
    payload = {
        "mint": mint,
        "migration_signature": migration_signature,
        "pumpswap_pool": pumpswap_pool,
        "pumpswap_program_id": PUMPSWAP_AMM_PROGRAM_ID,
        "pump_program_id": PUMP_PROGRAM_ID,
        "graduation_block_time": int(graduation_block_time),
        "graduation_slot": None if graduation_slot is None else int(graduation_slot),
        "base_mint_offset": int(base_mint_offset),
        "lifecycle_state": GRADUATED_LIFECYCLE,
        "contract_version": CONTRACT_VERSION,
    }
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def record_graduated_candidate(
    connection: Any,
    *,
    mint: str,
    migration_signature: str,
    pumpswap_pool: str,
    graduation_block_time: int,
    graduation_slot: int | None,
    now: str,
    discovery_channel: str = LATEST_GRADUATED_CHANNEL,
    migration_provenance: str = "PUMPPORTAL_SUBSCRIBE_MIGRATION",
    base_mint_offset: int = _PUMPSWAP_POOL_BASE_MINT_OFFSET,
) -> bool:
    """Insert one confirmed graduated candidate. Returns True when newly written.

    Idempotent for a byte-identical re-confirmation: a re-observed known candidate
    updates only its observation fields and returns False. A conflicting signature
    or pool for a known mint fails closed as ``GRADUATED_REGISTRY_CONFLICT``.
    """
    if not isinstance(mint, str) or not mint.strip():
        raise GraduatedCandidateError("GRADUATED_REGISTRY_INVALID_MINT")
    if not isinstance(migration_signature, str) or not migration_signature.strip():
        raise GraduatedCandidateError("GRADUATED_REGISTRY_INVALID_SIGNATURE")
    if not isinstance(pumpswap_pool, str) or not pumpswap_pool.strip():
        raise GraduatedCandidateError("GRADUATED_REGISTRY_INVALID_POOL")

    market_identity = market_identity_for_pool(pumpswap_pool)
    evidence_hash = graduation_evidence_hash(
        mint=mint,
        migration_signature=migration_signature,
        pumpswap_pool=pumpswap_pool,
        graduation_block_time=graduation_block_time,
        graduation_slot=graduation_slot,
        base_mint_offset=base_mint_offset,
    )

    existing = connection.execute(
        """
        SELECT migration_signature, pumpswap_pool, confirmation_evidence_hash
        FROM printer_pumpswap_graduated_candidate_registry
        WHERE mint_identity = ?
        """,
        (mint,),
    ).fetchone()
    if existing is not None:
        if (
            existing["migration_signature"] == migration_signature
            and existing["pumpswap_pool"] == pumpswap_pool
            and existing["confirmation_evidence_hash"] == evidence_hash
        ):
            touch_graduated_observation(connection, mint, channel=discovery_channel, now=now)
            return False
        raise GraduatedCandidateError(
            "GRADUATED_REGISTRY_CONFLICT",
            f"conflicting graduation evidence for mint {mint}",
        )

    # A migration signature is globally unique to one graduation; guard the mint
    # cross-check so a re-used signature for a different mint fails closed clearly.
    sig_owner = connection.execute(
        "SELECT mint_identity FROM printer_pumpswap_graduated_candidate_registry "
        "WHERE migration_signature = ?",
        (migration_signature,),
    ).fetchone()
    if sig_owner is not None and sig_owner["mint_identity"] != mint:
        raise GraduatedCandidateError(
            "GRADUATED_REGISTRY_SIGNATURE_CONFLICT",
            f"migration signature already bound to mint {sig_owner['mint_identity']}",
        )

    connection.execute(
        f"""
        INSERT INTO printer_pumpswap_graduated_candidate_registry(
            {",".join(_EXPORT_COLUMNS)}
        ) VALUES ({",".join("?" * len(_EXPORT_COLUMNS))})
        """,
        (
            mint,
            migration_signature,
            migration_provenance,
            pumpswap_pool,
            PUMPSWAP_AMM_PROGRAM_ID,
            PUMP_PROGRAM_ID,
            int(base_mint_offset),
            int(graduation_block_time),
            None if graduation_slot is None else int(graduation_slot),
            GRADUATED_LIFECYCLE,
            market_identity,
            discovery_channel,
            evidence_hash,
            CONTRACT_VERSION,
            now,
            now,
            discovery_channel,
            1,
        ),
    )
    return True


def touch_graduated_observation(
    connection: Any, mint: str, *, channel: str, now: str
) -> bool:
    """Record a fresh clean observation of a known graduated candidate.

    Updates only ``latest_observed_at``, ``latest_channel`` and
    ``observation_count`` (immutable graduation evidence is untouched). Returns True
    when a row was updated.
    """
    cursor = connection.execute(
        """
        UPDATE printer_pumpswap_graduated_candidate_registry
        SET latest_observed_at = ?,
            latest_channel = ?,
            observation_count = observation_count + 1
        WHERE mint_identity = ?
        """,
        (now, channel, mint),
    )
    return cursor.rowcount > 0


def lookup_graduated_candidate(connection: Any, mint: str) -> Mapping[str, Any] | None:
    if not isinstance(mint, str) or not mint:
        return None
    row = connection.execute(
        f"SELECT {','.join(_EXPORT_COLUMNS)} FROM "
        "printer_pumpswap_graduated_candidate_registry WHERE mint_identity = ?",
        (mint,),
    ).fetchone()
    if row is None:
        return None
    return MappingProxyType({col: row[col] for col in _EXPORT_COLUMNS})


def export_graduated_candidates(
    connection: Any,
    *,
    exclude_market_identities: Iterable[str] = (),
) -> list[Mapping[str, Any]]:
    """Export all confirmed graduated candidates in canonical order.

    Deduplicated by exact mint (primary key) and market identity. Zero source
    calls; canonical ``(graduation_block_time, mint_identity)`` order.
    """
    excluded = {str(m) for m in exclude_market_identities}
    rows = connection.execute(
        f"SELECT {','.join(_EXPORT_COLUMNS)} FROM "
        "printer_pumpswap_graduated_candidate_registry "
        "WHERE lifecycle_state = 'PUMPSWAP_GRADUATED_CONFIRMED' "
        "ORDER BY graduation_block_time, mint_identity"
    ).fetchall()
    export: list[Mapping[str, Any]] = []
    for row in rows:
        if str(row["market_identity"]) in excluded:
            continue
        export.append(MappingProxyType({col: row[col] for col in _EXPORT_COLUMNS}))
    return export


def import_graduated_candidate_row(connection: Any, row: Mapping[str, Any]) -> bool:
    """Insert one exported graduated-candidate row verbatim into a fresh registry.

    Idempotent for a byte-identical re-import; fail-closed as
    ``GRADUATED_REGISTRY_CONFLICT`` for conflicting evidence for a known mint.
    """
    existing = connection.execute(
        "SELECT migration_signature, pumpswap_pool, confirmation_evidence_hash FROM "
        "printer_pumpswap_graduated_candidate_registry WHERE mint_identity = ?",
        (row["mint_identity"],),
    ).fetchone()
    if existing is not None:
        if (
            existing[0] == row["migration_signature"]
            and existing[1] == row["pumpswap_pool"]
            and existing[2] == row["confirmation_evidence_hash"]
        ):
            return False
        raise GraduatedCandidateError(
            "GRADUATED_REGISTRY_CONFLICT", str(row["mint_identity"])
        )
    connection.execute(
        f"INSERT INTO printer_pumpswap_graduated_candidate_registry("
        f"{','.join(_EXPORT_COLUMNS)}) VALUES ({','.join('?' * len(_EXPORT_COLUMNS))})",
        tuple(row[col] for col in _EXPORT_COLUMNS),
    )
    return True


def graduated_registry_exists(connection: Any) -> bool:
    """True when migration 040 has created the graduated registry table."""
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND "
        "name='printer_pumpswap_graduated_candidate_registry'"
    ).fetchone()
    return row is not None

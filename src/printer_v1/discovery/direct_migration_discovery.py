"""V2-9.7E.42 direct Pump migration discovery orchestrator.

Turns the keyless PumpPortal ``subscribeMigration`` free stream into operational
graduated Pump.fun candidate supply:

    subscribeMigration -> (mint, migration signature)
      -> governed finalized transaction verification (exact Pump migration proof)
      -> resolve unique PumpSwap pool from the signature
      -> confirm PumpSwap owner + exact base_mint
      -> persist PUMPSWAP_GRADUATED_CONFIRMED candidate

PumpPortal is locator evidence only. Every candidate is verified on-chain through
the Source Governor before it is persisted. No wallet, authentication, payment,
trade subscription, execution, lifecycle, pilot authorization, or memory work is
performed here. Migration block time is graduation evidence only and never becomes
token creation time.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

from printer_v1.contracts.enums import SourceStatus
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.governed_execution import execute_source_request_with_governor
from printer_v1.sources.pump_migration import (
    MIGRATION_PROVENANCE,
    build_graduation_verifier_transport,
)
from printer_v1.sources.pumpportal import build_pumpportal_adapter
from printer_v1.sources.pumpswap import build_pumpswap_adapter
from printer_v1.sources.pumpswap_graduated_registry import (
    LATEST_GRADUATED_CHANNEL,
    PERSISTED_ACTIVE_CHANNEL,
    export_graduated_candidates,
    record_graduated_candidate,
)

MIGRATION_SOURCE = "pumpportal"
MIGRATION_REQUEST_KIND = "pumpfun_migration_stream"
VERIFY_SOURCE = "pumpswap"
VERIFY_REQUEST_KIND = "pumpswap_signature_pool_resolution"

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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def intake_migration_events(
    normalized_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Extract deduplicated valid (mint, signature) pairs from a migration result.

    Skips acknowledgment / non-event frames, requires a valid exact mint AND
    signature, deduplicates by mint and by signature, and records malformed,
    missing and conflicting events honestly. A conflicting pair (same mint with a
    different signature, or same signature with a different mint) is recorded and
    never used.
    """
    tokens: list[Mapping[str, Any]] = []
    if isinstance(normalized_payload, Mapping):
        raw = normalized_payload.get("tokens")
        if isinstance(raw, list):
            tokens = [t for t in raw if isinstance(t, Mapping)]

    valid_pairs: list[dict[str, str]] = []
    by_mint: dict[str, str] = {}
    by_sig: dict[str, str] = {}
    conflicting: list[dict[str, str]] = []
    missing_mint = 0
    missing_signature = 0
    duplicate = 0

    for token in tokens:
        mint = token.get("mint")
        sig = token.get("migration_signature")
        if not isinstance(mint, str) or not mint.strip():
            missing_mint += 1
            continue
        if not isinstance(sig, str) or not sig.strip():
            missing_signature += 1
            continue
        mint = mint.strip()
        sig = sig.strip()
        prior_sig = by_mint.get(mint)
        prior_mint = by_sig.get(sig)
        if prior_sig is not None and prior_sig != sig:
            conflicting.append({"kind": "MINT_TO_MULTIPLE_SIGNATURES", "mint": mint, "signature": sig})
            continue
        if prior_mint is not None and prior_mint != mint:
            conflicting.append({"kind": "SIGNATURE_TO_MULTIPLE_MINTS", "mint": mint, "signature": sig})
            continue
        if prior_sig == sig or prior_mint == mint:
            duplicate += 1
            continue
        by_mint[mint] = sig
        by_sig[sig] = mint
        valid_pairs.append({"mint": mint, "signature": sig})

    return {
        "events_received": len(tokens),
        "valid_pairs": valid_pairs,
        "valid_pair_count": len(valid_pairs),
        "missing_mint": missing_mint,
        "missing_signature": missing_signature,
        "duplicate": duplicate,
        "conflicting": conflicting,
        "conflicting_count": len(conflicting),
    }


def _ledger_counts(connection: sqlite3.Connection) -> dict[str, int]:
    def _count(table: str) -> int:
        try:
            return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        except sqlite3.Error:
            return 0

    return {
        "source_requests": _count("printer_source_requests"),
        "source_responses": _count("printer_source_responses"),
        "source_failures": _count("printer_source_failures"),
        "graduated_candidates": _count("printer_pumpswap_graduated_candidate_registry"),
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
        deltas[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    return deltas


def run_direct_migration_discovery(
    db_path: str | Path,
    *,
    migration_transport: Callable[[Any], Mapping[str, Any]],
    verifier_transport_factory: Callable[[str, str], Callable[[Any], Mapping[str, Any]]] | None = None,
    now: str | None = None,
    request_key_prefix: str = "v2-9-7e-42",
    max_candidates: int = 5,
) -> dict[str, Any]:
    """Run one bounded direct-migration discovery cycle (governed, fail-closed).

    ``migration_transport`` supplies the bounded PumpPortal ``subscribeMigration``
    events (live or fixture). ``verifier_transport_factory(mint, signature)`` returns
    the governed PumpSwap graduation-verifier transport for one candidate; when
    omitted, the live ``build_graduation_verifier_transport`` is used. All source
    execution goes through the Source Governor and is recorded in the source ledger.
    Returns a full discovery report; raises nothing on ordinary market/verification
    failures (they are recorded honestly).
    """
    now = now or _utc_now_iso()
    if verifier_transport_factory is None:
        def verifier_transport_factory(mint: str, signature: str):  # type: ignore[misc]
            return build_graduation_verifier_transport(
                migration_signature=signature, expected_mint=mint
            )

    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        # --- Migration intake (governed) ------------------------------------
        migration_adapter = build_pumpportal_adapter(
            enabled=True, fixture_transport=migration_transport
        )
        migration_request = build_governed_source_request(
            MIGRATION_SOURCE,
            MIGRATION_REQUEST_KIND,
            request_key=f"{request_key_prefix}-migration",
            tracking_priority=0,
            payload={"request_kind": MIGRATION_REQUEST_KIND, "chain": "solana"},
        )
        migration_exec = execute_source_request_with_governor(
            connection, migration_request, migration_adapter, recent_request_count=0
        )
        migration_result = migration_exec.normalized_result
        migration_ok = (
            migration_result.source_status in {SourceStatus.COMPLETE, SourceStatus.PARTIAL}
            and not migration_result.failure_type
        )
        intake = intake_migration_events(
            migration_result.normalized_payload if migration_ok else None
        )
        if not migration_ok:
            intake["migration_stream_failure"] = migration_result.failure_type

        # --- Per-candidate governed on-chain verification -------------------
        verifications: list[dict[str, Any]] = []
        confirmed_this_cycle: list[str] = []
        pumpswap_request_count = 0
        for pair in intake["valid_pairs"][:max_candidates]:
            mint = pair["mint"]
            signature = pair["signature"]
            verifier_transport = verifier_transport_factory(mint, signature)
            verify_adapter = build_pumpswap_adapter(
                enabled=True, fixture_transport=verifier_transport
            )
            verify_request = build_governed_source_request(
                VERIFY_SOURCE,
                VERIFY_REQUEST_KIND,
                request_key=f"{request_key_prefix}-verify-{mint}",
                tracking_priority=0,
                payload={
                    "request_kind": VERIFY_REQUEST_KIND,
                    "mint": mint,
                    "migration_signature": signature,
                    "chain": "solana",
                },
            )
            verify_exec = execute_source_request_with_governor(
                connection,
                verify_request,
                verify_adapter,
                recent_request_count=pumpswap_request_count,
            )
            pumpswap_request_count += 1
            vres = verify_exec.normalized_result
            verified = (
                vres.source_status in {SourceStatus.COMPLETE, SourceStatus.PARTIAL}
                and not vres.failure_type
            )
            record: dict[str, Any] = {
                "mint": mint,
                "signature": signature,
                "verified": verified,
            }
            if not verified:
                record["failure_type"] = vres.failure_type
                verifications.append(record)
                continue

            payload = vres.normalized_payload or {}
            token_entries = payload.get("tokens") or []
            token = token_entries[0] if token_entries else {}
            pool = token.get("pairAddress")
            block_time = token.get("pumpswap_migration_block_time")
            slot = token.get("pumpswap_migration_slot")
            confirmation = payload.get("pumpswap_confirmation") or {}
            if (
                not pool
                or block_time is None
                or token.get("mint") != mint
                or not confirmation.get("confirmed")
            ):
                record["verified"] = False
                record["failure_type"] = "verification_payload_incomplete"
                verifications.append(record)
                continue

            newly = record_graduated_candidate(
                connection,
                mint=mint,
                migration_signature=signature,
                pumpswap_pool=str(pool),
                graduation_block_time=int(block_time),
                graduation_slot=None if slot is None else int(slot),
                now=now,
                discovery_channel=LATEST_GRADUATED_CHANNEL,
                migration_provenance=MIGRATION_PROVENANCE,
            )
            confirmed_this_cycle.append(mint)
            record["pool"] = str(pool)
            record["graduation_block_time"] = int(block_time)
            record["graduation_slot"] = None if slot is None else int(slot)
            record["market_identity"] = f"solana-mainnet:pumpswap:{pool}"
            record["newly_persisted"] = newly
            record["discovery_channel"] = LATEST_GRADUATED_CHANNEL
            verifications.append(record)

        connection.commit()

        # --- Candidate mix (fresh vs previously confirmed) ------------------
        fresh = set(confirmed_this_cycle)
        persisted = export_graduated_candidates(connection)
        mix: list[dict[str, Any]] = []
        latest_count = 0
        persisted_count = 0
        for row in persisted:
            mint = str(row["mint_identity"])
            if mint in fresh:
                category = LATEST_GRADUATED_CHANNEL
                latest_count += 1
            else:
                # Richer DUMP/CONSOLIDATION/DECAY/REVIVAL categories require adopted
                # DexScreener exact-market delta evidence not computed in this lane;
                # degrade honestly to PERSISTED_ACTIVE (never fabricated).
                category = PERSISTED_ACTIVE_CHANNEL
                persisted_count += 1
            mix.append(
                {
                    "mint": mint,
                    "market_identity": str(row["market_identity"]),
                    "pool": str(row["pumpswap_pool"]),
                    "category": category,
                    "lifecycle_state": str(row["lifecycle_state"]),
                    "graduation_block_time": int(row["graduation_block_time"]),
                }
            )

        ledger = _ledger_counts(connection)
        forbidden = _forbidden_deltas(connection)
    finally:
        connection.close()

    return {
        "generated_at": now,
        "migration_intake": intake,
        "verifications": verifications,
        "confirmed_this_cycle": confirmed_this_cycle,
        "confirmed_count": len(confirmed_this_cycle),
        "candidate_mix": mix,
        "latest_graduated_count": latest_count,
        "persisted_active_count": persisted_count,
        "total_persisted_graduated": len(mix),
        "source_operation_ledger": ledger,
        "forbidden_capability_deltas": forbidden,
        "forbidden_delta_total": sum(forbidden.values()),
    }

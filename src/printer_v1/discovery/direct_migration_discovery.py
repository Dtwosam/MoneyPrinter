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
import time
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
    PERSISTED_GRADUATED_CHANNEL,
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


# V2-9.7E.42 (BL-42-01): a migration NOTIFICATION arrives before its finalized
# transaction is queryable on the public multi-backend RPC. A verification that
# fails with one of these transient reasons is not a graduation failure — the
# transaction is simply not yet retrievable — so it is eligible for exactly one
# bounded governed re-verification after a settle window. Non-transient failures
# (wrong owner, mint mismatch, zero/ambiguous pool, failed tx) are never retried.
_TRANSIENT_VERIFY_MARKERS = (
    "pumpswap_rpc_transport_error",
    "pumpswap_rpc_http_error",
    "pumpswap_rpc_malformed",
    "migration_transaction_not_found",
    "transaction_not_found",
)


def _is_transient_verify_failure(failure_type: str | None) -> bool:
    if not failure_type:
        return False
    return any(marker in failure_type for marker in _TRANSIENT_VERIFY_MARKERS)


def _merge_intakes(intakes: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge per-round intakes into one deduplicated intake across the attempt."""
    merged_pairs: list[dict[str, str]] = []
    by_mint: dict[str, str] = {}
    by_sig: dict[str, str] = {}
    conflicting: list[dict[str, str]] = []
    events_received = 0
    missing_mint = 0
    missing_signature = 0
    duplicate = 0
    for intake in intakes:
        events_received += intake["events_received"]
        missing_mint += intake["missing_mint"]
        missing_signature += intake["missing_signature"]
        duplicate += intake["duplicate"]
        conflicting.extend(intake["conflicting"])
        for pair in intake["valid_pairs"]:
            mint, sig = pair["mint"], pair["signature"]
            prior_sig = by_mint.get(mint)
            prior_mint = by_sig.get(sig)
            if (prior_sig is not None and prior_sig != sig) or (
                prior_mint is not None and prior_mint != mint
            ):
                conflicting.append({"kind": "CROSS_ROUND_CONFLICT", "mint": mint, "signature": sig})
                continue
            if prior_sig == sig or prior_mint == mint:
                duplicate += 1
                continue
            by_mint[mint] = sig
            by_sig[sig] = mint
            merged_pairs.append({"mint": mint, "signature": sig})
    return {
        "events_received": events_received,
        "valid_pairs": merged_pairs,
        "valid_pair_count": len(merged_pairs),
        "missing_mint": missing_mint,
        "missing_signature": missing_signature,
        "duplicate": duplicate,
        "conflicting": conflicting,
        "conflicting_count": len(conflicting),
        "collection_rounds": len(intakes),
    }


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
    collection_rounds: int = 1,
    settle_seconds: float = 0.0,
    reverify_on_transient: bool = False,
    reverify_settle_seconds: float = 0.0,
) -> dict[str, Any]:
    """Run one bounded direct-migration discovery cycle (governed, fail-closed).

    ``migration_transport`` supplies the bounded PumpPortal ``subscribeMigration``
    events (live or fixture). ``verifier_transport_factory(mint, signature)`` returns
    the governed PumpSwap graduation-verifier transport for one candidate; when
    omitted, the live ``build_graduation_verifier_transport`` is used. All source
    execution goes through the Source Governor and is recorded in the source ledger.

    BL-42-01 robustness (live discovery): ``collection_rounds`` issues that many
    bounded governed migration requests, accumulating deduplicated locator pairs;
    ``settle_seconds`` is a single bounded wait before verification so freshly
    migrated transactions finalize; ``reverify_on_transient`` allows exactly one
    additional bounded governed verification per candidate whose first attempt
    failed with a transient RPC/not-found reason (never a graduation failure).
    Defaults preserve the original single-round, no-wait behaviour for fixtures.

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
    migration_request_count = 0
    pumpswap_request_count = 0

    def _governed_migration(round_index: int) -> dict[str, Any]:
        nonlocal migration_request_count
        adapter = build_pumpportal_adapter(enabled=True, fixture_transport=migration_transport)
        request = build_governed_source_request(
            MIGRATION_SOURCE,
            MIGRATION_REQUEST_KIND,
            request_key=f"{request_key_prefix}-migration-r{round_index}",
            tracking_priority=0,
            payload={"request_kind": MIGRATION_REQUEST_KIND, "chain": "solana"},
        )
        execution = execute_source_request_with_governor(
            connection, request, adapter, recent_request_count=migration_request_count
        )
        migration_request_count += 1
        result = execution.normalized_result
        ok = (
            result.source_status in {SourceStatus.COMPLETE, SourceStatus.PARTIAL}
            and not result.failure_type
        )
        one = intake_migration_events(result.normalized_payload if ok else None)
        if not ok:
            one["migration_stream_failure"] = result.failure_type
        return one

    def _governed_verify(mint: str, signature: str, attempt: int):
        nonlocal pumpswap_request_count
        verifier_transport = verifier_transport_factory(mint, signature)
        adapter = build_pumpswap_adapter(enabled=True, fixture_transport=verifier_transport)
        request = build_governed_source_request(
            VERIFY_SOURCE,
            VERIFY_REQUEST_KIND,
            request_key=f"{request_key_prefix}-verify-{mint}-a{attempt}",
            tracking_priority=0,
            payload={
                "request_kind": VERIFY_REQUEST_KIND,
                "mint": mint,
                "migration_signature": signature,
                "chain": "solana",
            },
        )
        execution = execute_source_request_with_governor(
            connection, request, adapter, recent_request_count=pumpswap_request_count
        )
        pumpswap_request_count += 1
        return execution.normalized_result

    try:
        # --- Migration intake (governed, multi-round) -----------------------
        round_intakes = [_governed_migration(r) for r in range(max(1, collection_rounds))]
        intake = _merge_intakes(round_intakes)

        # --- Bounded settle so freshly migrated transactions finalize -------
        if settle_seconds > 0 and intake["valid_pair_count"] > 0:
            time.sleep(settle_seconds)

        # --- Per-candidate governed on-chain verification -------------------
        verifications: list[dict[str, Any]] = []
        confirmed_this_cycle: list[str] = []
        for pair in intake["valid_pairs"][:max_candidates]:
            mint = pair["mint"]
            signature = pair["signature"]
            vres = _governed_verify(mint, signature, attempt=1)
            verified = (
                vres.source_status in {SourceStatus.COMPLETE, SourceStatus.PARTIAL}
                and not vres.failure_type
            )
            attempts = 1
            if (
                not verified
                and reverify_on_transient
                and _is_transient_verify_failure(vres.failure_type)
            ):
                if reverify_settle_seconds > 0:
                    time.sleep(reverify_settle_seconds)
                vres = _governed_verify(mint, signature, attempt=2)
                verified = (
                    vres.source_status in {SourceStatus.COMPLETE, SourceStatus.PARTIAL}
                    and not vres.failure_type
                )
                attempts = 2
            record: dict[str, Any] = {
                "mint": mint,
                "signature": signature,
                "verified": verified,
                "verify_attempts": attempts,
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
                # V2-9.7E.43: truthful provenance. A candidate confirmed before the
                # current cycle and not rediscovered as a current-cycle migration is
                # PERSISTED_GRADUATED. Behavioral categories
                # (DUMP/CONSOLIDATION/DECAY/REVIVAL) are never derived in discovery.
                category = PERSISTED_GRADUATED_CHANNEL
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
        "persisted_graduated_count": persisted_count,
        "total_persisted_graduated": len(mix),
        "source_operation_ledger": ledger,
        "forbidden_capability_deltas": forbidden,
        "forbidden_delta_total": sum(forbidden.values()),
    }

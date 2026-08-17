"""V2-9.8B direct Pump migration discovery orchestrator.

Turns one bounded finalized **migration-targeted** signature page into
operational graduated Pump.fun candidate supply:

    governed getSignaturesForAddress(Pump migration withdraw authority, finalized)
      -> governed getTransaction(signature, finalized)
      -> exact pinned Pump migrate/migrate_v2 instruction/account verification
      -> resolve unique PumpSwap pool from the signature
      -> confirm PumpSwap owner + exact base_mint
      -> persist PUMPSWAP_GRADUATED_CONFIRMED candidate

Slice B adds exactly two categorical acquisition modes over the same bounded
transport shape — ``LIVE_TAIL`` (no cursor) and ``BACKFILL`` (strictly
``before`` a durable cursor position) — plus ownership of the restart-safe
cursor in ``printer_direct_pump_migration_cursor``.

The cursor may advance only through a CONTIGUOUS prefix of signatures that were
fully resolved: a definitive non-migration, or a supported migration whose
canonical PumpSwap confirmation AND canonical registry persistence both
succeeded. A transaction source failure, an unsupported migration-like contract
observation, or an unverified genuine migration all stop the walk and are never
skipped. Cursor reads/writes are local state: they create zero source requests
and zero transports.

Every RPC operation is separately Source-Governed and recorded before any
candidate is persisted. No wallet, authentication, payment, subscription,
execution, lifecycle, pilot authorization or memory work is performed here.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

from printer_v1.contracts.enums import SourceStatus
from printer_v1.db.sqlite_write_contracts import connect_operational
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.governed_execution import execute_source_request_with_governor
from printer_v1.sources.pump_migration import (
    MIGRATION_PROVENANCE,
    build_graduation_verifier_transport,
)
from printer_v1.sources.direct_pump_migration import (
    DIRECT_MIGRATION_INDEXED_ADDRESS,
    DIRECT_PUMP_MIGRATION_CONTRACT_HASH,
    DIRECT_PUMP_MIGRATION_DECODER_VERSION,
    MAX_TRANSACTION_LOOKUPS,
    SIGNATURE_PAGE_REQUEST_KIND,
    SOURCE_NAME as MIGRATION_SOURCE,
    TRANSACTION_REQUEST_KIND,
    build_direct_pump_migration_adapter,
)
from printer_v1.sources.pumpswap import build_pumpswap_adapter
from printer_v1.sources.pumpswap_graduated_registry import (
    LATEST_GRADUATED_CHANNEL,
    PERSISTED_GRADUATED_CHANNEL,
    export_graduated_candidates,
    record_graduated_candidate,
)
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignSixUnitOwner,
    build_campaign_stage_id,
    seal_campaign_stage_evidence,
)
from printer_v1.sources.measured_transport import (
    LocalValidationIdentity,
    MeasuredTransportError,
    empty_six_unit_totals,
    merge_transport_payload_metadata,
    record_payload_transports,
)

STAGE_KIND_DIRECT_MIGRATION = "DIRECT_MIGRATION"

MIGRATION_REQUEST_KIND = SIGNATURE_PAGE_REQUEST_KIND
VERIFY_SOURCE = "pumpswap"
VERIFY_REQUEST_KIND = "pumpswap_signature_pool_resolution"

# --- Slice B: bounded migration-targeted acquisition modes -------------------
LIVE_TAIL_MODE = "LIVE_TAIL"
BACKFILL_MODE = "BACKFILL"
DIRECT_ACQUISITION_MODES = (LIVE_TAIL_MODE, BACKFILL_MODE)

#: One later-cycle attempt performs at most one LIVE_TAIL page and at most one
#: BACKFILL page, in separate Scheduler claims but inside the SAME campaign /
#: run / cycle. Both claims seal DIRECT_MIGRATION stage evidence, so their stage
#: sequence — not their cycle identity — is what keeps the two stage IDs
#: distinct. A fixed mapping is sufficient and is never a dynamic counter.
DIRECT_MIGRATION_STAGE_SEQUENCE_BY_MODE = {
    LIVE_TAIL_MODE: 1,
    BACKFILL_MODE: 2,
}


def direct_migration_stage_sequence(mode: str) -> int:
    """Return the canonical DIRECT_MIGRATION stage sequence for one mode."""
    try:
        return DIRECT_MIGRATION_STAGE_SEQUENCE_BY_MODE[str(mode)]
    except KeyError as exc:
        raise ValueError("DIRECT_PUMP_ACQUISITION_MODE_INVALID") from exc


#: Fixed cooperative transaction-lookup allowance per direct acquisition mode.
#:
#: Both claims of one attempt emit DIRECT_PUMP_NOMINATION transports into the
#: SAME CampaignSixUnitOwner, whose pre-existing stage ceiling is 13. One page
#: plus its lookups is the whole cost of a claim, so the attempt's worst case is
#:
#:     LIVE_TAIL  1 page + 6 lookups = 7
#:     BACKFILL   1 page + 5 lookups = 6
#:                                   ---
#:                                     13
#:
#: exactly the existing ceiling. This is a reduction of the previously reachable
#: 14, never an increase: no budget, ceiling or schema changes with it.
#:
#: The live tail keeps the larger allowance on purpose — newest migration
#: observation has priority over historical backfill. Static per-mode caps are
#: sufficient because B permits at most one LIVE_TAIL and one BACKFILL page per
#: attempt, so no dynamic budget reconstruction or extra counter is needed.
COOPERATIVE_DIRECT_TRANSACTION_LOOKUPS_BY_MODE = {
    LIVE_TAIL_MODE: 6,
    BACKFILL_MODE: 5,
}

#: Worst-case DIRECT_PUMP_NOMINATION transports one cooperative attempt can
#: emit: one signature page per claim plus that claim's lookup allowance.
COOPERATIVE_DIRECT_NOMINATION_TRANSPORT_CEILING = sum(
    1 + lookups
    for lookups in COOPERATIVE_DIRECT_TRANSACTION_LOOKUPS_BY_MODE.values()
)


def cooperative_direct_transaction_lookup_cap(mode: str) -> int:
    """Return the cooperative transaction-lookup cap for one direct mode.

    Fails closed on an unknown mode: cooperative production never supplies an
    arbitrary cap.
    """
    try:
        return COOPERATIVE_DIRECT_TRANSACTION_LOOKUPS_BY_MODE[str(mode)]
    except KeyError as exc:
        raise ValueError("DIRECT_PUMP_ACQUISITION_MODE_INVALID") from exc


DIRECT_MIGRATION_NETWORK = "solana-mainnet"
DIRECT_MIGRATION_CURSOR_TABLE = "printer_direct_pump_migration_cursor"

CONTINUITY_UNINITIALIZED = "UNINITIALIZED"
CONTINUITY_CONTIGUOUS = "CONTIGUOUS"
CONTINUITY_EXHAUSTED = "EXHAUSTED"
CONTINUITY_BLOCKED_CONTRACT = "BLOCKED_CONTRACT"

# Ordered page-walk outcomes. Only the first two may ever advance the cursor.
COVERED_NON_MIGRATION = "COVERED_NON_MIGRATION"
MIGRATION_LOCATED = "MIGRATION_LOCATED"
TRANSACTION_SOURCE_FAILURE = "TRANSACTION_SOURCE_FAILURE"
CONTRACT_BLOCKED = "CONTRACT_BLOCKED"
UNRESOLVED_CANDIDATE_LOCAL = "UNRESOLVED_CANDIDATE_LOCAL"
NOT_INSPECTED = "NOT_INSPECTED"

#: Outcomes that stop the ordered page walk. None of them may be crossed.
_WALK_STOPPING_OUTCOMES = frozenset(
    {TRANSACTION_SOURCE_FAILURE, CONTRACT_BLOCKED, UNRESOLVED_CANDIDATE_LOCAL}
)

_MIGRATION_REJECTION_PREFIX = "direct_pump_migration_rejected_"

#: Decoder reasons that positively prove no supported Pump migrate instruction
#: was present. Only these may be treated as a definitive non-migration and
#: allowed to advance the contiguous cursor.
_DEFINITIVE_NON_MIGRATION_REASONS = frozenset(
    {
        # The finalized transaction failed on chain; it cannot carry a
        # successful migration.
        "transaction_failed_or_meta_missing",
        # Zero matching pinned migrate/migrate_v2 instructions were decoded.
        "exactly_one_migrate_instruction_required",
    }
)

#: Decoder reasons that describe migration-like evidence the currently adopted
#: contract/decoder cannot validate. These are never generic non-migrations:
#: they block the cursor until a new contract/decoder identity restarts a fresh
#: bounded traversal.
_CONTRACT_BLOCKING_REASONS = frozenset(
    {
        "unsupported_transaction_version",
        "malformed_account_index",
        "migrate_account_layout_mismatch",
        "migrate_v2_account_layout_mismatch",
    }
)


class DirectMigrationCursorError(RuntimeError):
    """Fail-closed direct Pump migration cursor fault."""


@dataclass(frozen=True)
class DirectMigrationCursorState:
    """Immutable snapshot of the durable direct-migration traversal position."""

    network: str
    indexed_address: str
    pump_contract_hash: str
    decoder_version: str
    next_before_signature: str | None
    next_before_slot: int | None
    continuity_state: str
    pages_advanced: int
    signatures_covered: int
    last_live_tail_at: str | None
    last_backfill_at: str | None
    last_block_reason: str | None

    @property
    def backfill_permitted(self) -> bool:
        """BACKFILL is legal only from a CONTIGUOUS cursor with a position."""
        return (
            self.continuity_state == CONTINUITY_CONTIGUOUS
            and bool(self.next_before_signature)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "network": self.network,
            "indexed_address": self.indexed_address,
            "pump_contract_hash": self.pump_contract_hash,
            "decoder_version": self.decoder_version,
            "next_before_signature": self.next_before_signature,
            "next_before_slot": self.next_before_slot,
            "continuity_state": self.continuity_state,
            "pages_advanced": self.pages_advanced,
            "signatures_covered": self.signatures_covered,
            "last_live_tail_at": self.last_live_tail_at,
            "last_backfill_at": self.last_backfill_at,
            "last_block_reason": self.last_block_reason,
        }


def direct_migration_cursor_identity() -> tuple[str, str, str, str]:
    """The one cursor identity this feeder owns. Never caller-supplied."""
    return (
        DIRECT_MIGRATION_NETWORK,
        DIRECT_MIGRATION_INDEXED_ADDRESS,
        DIRECT_PUMP_MIGRATION_CONTRACT_HASH,
        DIRECT_PUMP_MIGRATION_DECODER_VERSION,
    )


_CURSOR_COLUMNS = (
    "network",
    "indexed_address",
    "pump_contract_hash",
    "decoder_version",
    "next_before_signature",
    "next_before_slot",
    "continuity_state",
    "pages_advanced",
    "signatures_covered",
    "last_live_tail_at",
    "last_backfill_at",
    "last_block_reason",
)


def load_direct_migration_cursor(
    connection: sqlite3.Connection,
) -> DirectMigrationCursorState | None:
    """Read the durable cursor for the exact current contract/decoder identity.

    Local state only: zero source requests, zero transports.
    """
    identity = direct_migration_cursor_identity()
    try:
        row = connection.execute(
            f"SELECT {', '.join(_CURSOR_COLUMNS)} FROM {DIRECT_MIGRATION_CURSOR_TABLE} "
            "WHERE network=? AND indexed_address=? AND pump_contract_hash=? "
            "AND decoder_version=?",
            identity,
        ).fetchone()
    except sqlite3.OperationalError as exc:
        raise DirectMigrationCursorError(
            f"DIRECT_PUMP_MIGRATION_CURSOR_TABLE_UNAVAILABLE:{exc}"
        ) from exc
    if row is None:
        return None
    values = dict(zip(_CURSOR_COLUMNS, tuple(row)))
    return DirectMigrationCursorState(
        network=str(values["network"]),
        indexed_address=str(values["indexed_address"]),
        pump_contract_hash=str(values["pump_contract_hash"]),
        decoder_version=str(values["decoder_version"]),
        next_before_signature=(
            None
            if values["next_before_signature"] is None
            else str(values["next_before_signature"])
        ),
        next_before_slot=(
            None if values["next_before_slot"] is None else int(values["next_before_slot"])
        ),
        continuity_state=str(values["continuity_state"]),
        pages_advanced=int(values["pages_advanced"] or 0),
        signatures_covered=int(values["signatures_covered"] or 0),
        last_live_tail_at=(
            None if values["last_live_tail_at"] is None else str(values["last_live_tail_at"])
        ),
        last_backfill_at=(
            None if values["last_backfill_at"] is None else str(values["last_backfill_at"])
        ),
        last_block_reason=(
            None if values["last_block_reason"] is None else str(values["last_block_reason"])
        ),
    )


def ensure_direct_migration_cursor(
    connection: sqlite3.Connection, *, now: str
) -> DirectMigrationCursorState:
    """Return the cursor for this contract identity, creating it UNINITIALIZED.

    A new Pump contract hash or decoder version always produces a NEW row. An
    older contract's cursor is never mutated into a new contract identity.
    """
    existing = load_direct_migration_cursor(connection)
    if existing is not None:
        return existing
    network, indexed_address, contract_hash, decoder_version = (
        direct_migration_cursor_identity()
    )
    try:
        connection.execute(
            f"INSERT INTO {DIRECT_MIGRATION_CURSOR_TABLE}("
            "network,indexed_address,pump_contract_hash,decoder_version,"
            "next_before_signature,next_before_slot,continuity_state,"
            "pages_advanced,signatures_covered,created_at,updated_at) "
            "VALUES (?,?,?,?,NULL,NULL,?,0,0,?,?)",
            (
                network,
                indexed_address,
                contract_hash,
                decoder_version,
                CONTINUITY_UNINITIALIZED,
                str(now),
                str(now),
            ),
        )
    except sqlite3.Error as exc:
        raise DirectMigrationCursorError(
            f"DIRECT_PUMP_MIGRATION_CURSOR_BOOTSTRAP_FAILED:{exc}"
        ) from exc
    created = load_direct_migration_cursor(connection)
    if created is None:
        raise DirectMigrationCursorError(
            "DIRECT_PUMP_MIGRATION_CURSOR_BOOTSTRAP_MISSING"
        )
    return created


def _update_direct_migration_cursor(
    connection: sqlite3.Connection,
    *,
    assignments: Mapping[str, Any],
    now: str,
) -> DirectMigrationCursorState:
    if not assignments:
        raise DirectMigrationCursorError("DIRECT_PUMP_MIGRATION_CURSOR_NO_ASSIGNMENT")
    columns = list(assignments)
    clause = ", ".join(f"{name}=?" for name in columns)
    parameters = [assignments[name] for name in columns]
    parameters.append(str(now))
    parameters.extend(direct_migration_cursor_identity())
    try:
        connection.execute(
            f"UPDATE {DIRECT_MIGRATION_CURSOR_TABLE} SET {clause}, updated_at=? "
            "WHERE network=? AND indexed_address=? AND pump_contract_hash=? "
            "AND decoder_version=?",
            tuple(parameters),
        )
    except sqlite3.Error as exc:
        raise DirectMigrationCursorError(
            f"DIRECT_PUMP_MIGRATION_CURSOR_UPDATE_REJECTED:{exc}"
        ) from exc
    updated = load_direct_migration_cursor(connection)
    if updated is None:
        raise DirectMigrationCursorError("DIRECT_PUMP_MIGRATION_CURSOR_LOST")
    return updated


def advance_direct_migration_cursor(
    connection: sqlite3.Connection,
    *,
    signature: str,
    slot: int,
    covered_count: int,
    now: str,
    mode: str = BACKFILL_MODE,
) -> DirectMigrationCursorState:
    """Move the traversal position to the OLDEST fully covered signature.

    The caller must already have proven a contiguous covered prefix ending at
    ``signature``. This never advances past an uncovered page member.
    """
    if mode not in DIRECT_ACQUISITION_MODES:
        raise DirectMigrationCursorError("DIRECT_PUMP_MIGRATION_CURSOR_MODE_INVALID")
    if not isinstance(signature, str) or not signature.strip():
        raise DirectMigrationCursorError("DIRECT_PUMP_MIGRATION_CURSOR_SIGNATURE_INVALID")
    if type(slot) is not int or slot < 0:
        raise DirectMigrationCursorError("DIRECT_PUMP_MIGRATION_CURSOR_SLOT_INVALID")
    if type(covered_count) is not int or covered_count < 0:
        raise DirectMigrationCursorError("DIRECT_PUMP_MIGRATION_CURSOR_COVERAGE_INVALID")
    current = ensure_direct_migration_cursor(connection, now=now)
    assignments: dict[str, Any] = {
        "next_before_signature": signature,
        "next_before_slot": int(slot),
        "continuity_state": CONTINUITY_CONTIGUOUS,
        "pages_advanced": int(current.pages_advanced) + 1,
        "signatures_covered": int(current.signatures_covered) + int(covered_count),
        "last_block_reason": None,
    }
    if mode == BACKFILL_MODE:
        assignments["last_backfill_at"] = str(now)
    else:
        assignments["last_live_tail_at"] = str(now)
    return _update_direct_migration_cursor(connection, assignments=assignments, now=now)


def mark_direct_migration_cursor_exhausted(
    connection: sqlite3.Connection, *, now: str
) -> DirectMigrationCursorState:
    """A successful finalized BACKFILL page returned zero rows.

    Backward traversal for this contract identity has reached its end. Live tail
    stays active; the historical walk is never restarted from the top.
    """
    ensure_direct_migration_cursor(connection, now=now)
    return _update_direct_migration_cursor(
        connection,
        assignments={
            "continuity_state": CONTINUITY_EXHAUSTED,
            "last_backfill_at": str(now),
        },
        now=now,
    )


def mark_direct_migration_cursor_contract_blocked(
    connection: sqlite3.Connection,
    *,
    reason: str,
    now: str,
    signature: str | None = None,
    slot: int | None = None,
    covered_count: int = 0,
) -> DirectMigrationCursorState:
    """Record migration-like evidence the adopted contract cannot validate.

    The blocked signature is never crossed. While BLOCKED_CONTRACT, automatic
    BACKFILL under the same contract hash + decoder version issues zero source
    requests. A later contract/decoder revision creates a new cursor identity.
    """
    categorical = str(reason or "").strip() or "UNSUPPORTED_MIGRATION_CONTRACT_EVIDENCE"
    # Bounded: a block reason is a category, never a raw transaction body.
    categorical = categorical[:120]
    current = ensure_direct_migration_cursor(connection, now=now)
    assignments: dict[str, Any] = {
        "continuity_state": CONTINUITY_BLOCKED_CONTRACT,
        "last_block_reason": categorical,
    }
    if signature is not None and slot is not None:
        assignments["next_before_signature"] = str(signature)
        assignments["next_before_slot"] = int(slot)
        assignments["pages_advanced"] = int(current.pages_advanced) + 1
        assignments["signatures_covered"] = (
            int(current.signatures_covered) + int(covered_count)
        )
    return _update_direct_migration_cursor(connection, assignments=assignments, now=now)


def touch_direct_migration_cursor_live_tail(
    connection: sqlite3.Connection, *, now: str
) -> DirectMigrationCursorState:
    """Record a live-tail observation WITHOUT moving the historical position.

    LIVE_TAIL and BACKFILL are separate concerns: live tail is newest activity,
    the cursor is historical progress. An established CONTIGUOUS position must
    never be dragged back to the top of the chain by a later live tail.
    """
    ensure_direct_migration_cursor(connection, now=now)
    return _update_direct_migration_cursor(
        connection, assignments={"last_live_tail_at": str(now)}, now=now
    )


def classify_direct_migration_transaction_failure(
    failure_type: str | None,
    migration_rejection_digest: Mapping[str, Any] | None,
) -> tuple[str, str]:
    """Classify one failed transaction lookup for the contiguous cursor law.

    Returns ``(outcome, reason)``. Uncertainty always fails closed to a
    non-advancing outcome; only positively proven absence of a supported Pump
    migrate instruction may ever be treated as covered.
    """
    failure = str(failure_type or "")
    if not failure.startswith(_MIGRATION_REJECTION_PREFIX):
        # Transport/provider level: never a statement about migration content.
        return TRANSACTION_SOURCE_FAILURE, failure or "direct_pump_transaction_failed"
    reason = failure[len(_MIGRATION_REJECTION_PREFIX) :] or "unknown"
    digest = (
        migration_rejection_digest
        if isinstance(migration_rejection_digest, Mapping)
        else {}
    )
    try:
        match_count = int(digest.get("pump_migrate_match_count") or 0)
    except (TypeError, ValueError):
        match_count = 0
    if match_count > 0 or reason in _CONTRACT_BLOCKING_REASONS:
        return CONTRACT_BLOCKED, reason
    if reason in _DEFINITIVE_NON_MIGRATION_REASONS:
        return COVERED_NON_MIGRATION, reason
    # Candidate-local, but not a proof that no supported migration was present.
    # It stops the walk without ever being reported as a provider outage: F's
    # failure-domain truth is preserved exactly.
    return UNRESOLVED_CANDIDATE_LOCAL, reason


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
    transport_operation_count = 0
    cursor_used = False
    transaction_rejections: list[str] = []
    transaction_source_failures: list[str] = []
    live_tail_failures: list[str] = []
    for intake in intakes:
        events_received += intake["events_received"]
        missing_mint += intake["missing_mint"]
        missing_signature += intake["missing_signature"]
        duplicate += intake["duplicate"]
        transport_operation_count += int(intake.get("transport_operation_count") or 0)
        cursor_used = cursor_used or bool(intake.get("cursor_used"))
        transaction_rejections.extend(
            str(value) for value in intake.get("transaction_rejections") or ()
        )
        transaction_source_failures.extend(
            str(value)
            for value in intake.get("transaction_source_failures") or ()
        )
        if intake.get("direct_pump_live_tail_failure"):
            live_tail_failures.append(
                str(intake["direct_pump_live_tail_failure"])
            )
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
        "transport_operation_count": transport_operation_count,
        "cursor_used": cursor_used,
        "transaction_rejections": transaction_rejections,
        "transaction_source_failures": transaction_source_failures,
        "direct_pump_live_tail_failures": live_tail_failures,
        # One bounded page per Scheduler claim, so the ordered walk of the last
        # (and only) round is the attempt's walk.
        "page_walk": list((intakes[-1].get("page_walk") if intakes else None) or ()),
        "page_requested": bool(intakes[-1].get("page_requested")) if intakes else False,
        "page_empty": bool(intakes[-1].get("page_empty")) if intakes else False,
        "page_ok": bool(intakes[-1].get("page_ok")) if intakes else False,
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


def _ledger_counts(
    connection: sqlite3.Connection,
    *,
    request_ids: list[int] | tuple[int, ...] = (),
) -> dict[str, int]:
    """Stage-local discovery accounting over this invocation's exact identities.

    V2-9.8B.2: whole-table ``COUNT(*)`` on ``printer_source_requests`` charged every
    historical durable row on the operational persistent DB into the holder
    campaign ledger (1121+ base ops against a 45-op admission ceiling). Only the
    exact migration/verify request rows created by this discovery invocation may
    be charged, each exactly once, whether it succeeded or failed.
    """
    identities = sorted({int(value) for value in request_ids})

    def _registry_count() -> int:
        try:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_pumpswap_graduated_candidate_registry"
                ).fetchone()[0]
            )
        except sqlite3.Error:
            return 0

    if not identities:
        return {
            "source_requests": 0,
            "source_responses": 0,
            "source_failures": 0,
            "graduated_candidates": _registry_count(),
            "request_ids": [],
        }

    placeholders = ",".join("?" * len(identities))

    def _count(sql: str) -> int:
        try:
            return int(connection.execute(sql, identities).fetchone()[0])
        except sqlite3.Error:
            return 0

    return {
        "source_requests": len(identities),
        "source_responses": _count(
            "SELECT COUNT(*) FROM printer_source_responses "
            f"WHERE source_request_id IN ({placeholders})"
        ),
        "source_failures": _count(
            "SELECT COUNT(*) FROM printer_source_failures "
            f"WHERE source_request_id IN ({placeholders})"
        ),
        "graduated_candidates": _registry_count(),
        "request_ids": identities,
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


def coerce_migration_transport(
    migration_transport: Any,
) -> Callable[[Any], Mapping[str, Any]]:
    """Accept either a transport callable or a preflight adapter shell.

    Shared WINDOW_15M composition returns a concrete
    ``DirectPumpMigrationAdapter`` so preflight can validate request-kind
    contracts. Discovery always needs the inner transport callable that emits
    one Solana JSON-RPC response per governed live-tail operation.
    """
    if callable(migration_transport):
        return migration_transport
    inner = getattr(migration_transport, "transport", None)
    if callable(inner):
        return inner
    raise TypeError(
        "DIRECT_PUMP_MIGRATION_TRANSPORT_NOT_CALLABLE:"
        f"{type(migration_transport).__name__}"
    )


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
    stage_evidence_sink: Callable[[Mapping[str, Any]], None] | None = None,
    transport_identity_observer: Callable[[Any], None] | None = None,
    local_validation_identity_observer: Callable[[Any], None] | None = None,
    campaign_id: str | None = None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    stage_sequence: int | None = None,
    max_transaction_lookups: int = MAX_TRANSACTION_LOOKUPS,
    acquisition_mode: str = LIVE_TAIL_MODE,
) -> dict[str, Any]:
    """Run one bounded direct-migration discovery cycle (governed, fail-closed).

    ``migration_transport`` supplies exactly one Solana JSON-RPC response per
    governed live-tail page/transaction request. A preflight adapter shell is
    also accepted and coerced to its inner transport. ``verifier_transport_factory``
    returns
    the governed PumpSwap graduation-verifier transport for one candidate; when
    omitted, the live ``build_graduation_verifier_transport`` is used. All source
    execution goes through the Source Governor and is recorded in the source ledger.

    The restored path requires one finalized stateless page, no settle wait and
    no re-verification. The legacy arguments remain present for call-shape
    compatibility but any non-restored value fails before a source request.

    When ``stage_evidence_sink`` is supplied, exactly one sealed stage evidence
    block is emitted before every normal return. The campaign owner remains the
    only campaign-wide accounting authority.

    ``transport_identity_observer`` is verification-only: it is notified when a
    transport identity is measured on this stage ledger, before sealing. It must
    not replace the campaign owner.

    Returns a full discovery report; raises nothing on ordinary market/verification
    failures (they are recorded honestly).
    """
    now = now or _utc_now_iso()
    migration_transport = coerce_migration_transport(migration_transport)
    if collection_rounds != 1:
        raise ValueError("DIRECT_PUMP_LIVE_TAIL_REQUIRES_ONE_COLLECTION_ROUND")
    if settle_seconds != 0.0:
        raise ValueError("FINALIZED_DIRECT_PUMP_LIVE_TAIL_FORBIDS_SETTLE_SLEEP")
    if reverify_on_transient or reverify_settle_seconds != 0.0:
        raise ValueError("DIRECT_PUMP_LIVE_TAIL_FORBIDS_AUTOMATIC_REVERIFY")
    if (
        type(max_transaction_lookups) is not int
        or max_transaction_lookups < 1
        or max_transaction_lookups > MAX_TRANSACTION_LOOKUPS
    ):
        raise ValueError("DIRECT_PUMP_TRANSACTION_LOOKUP_CAP_INVALID")
    if acquisition_mode not in DIRECT_ACQUISITION_MODES:
        raise ValueError("DIRECT_PUMP_ACQUISITION_MODE_INVALID")
    # LIVE_TAIL and BACKFILL are two claims of the SAME campaign/run/cycle, so
    # every identity they emit must be separated by the direct stage sequence,
    # never by a different cycle identity.
    direct_stage_sequence = direct_migration_stage_sequence(acquisition_mode)
    direct_mode_slug = str(acquisition_mode).lower().replace("_", "-")
    if stage_sequence is None:
        # Cooperative production never supplies one: the mode is authoritative.
        stage_sequence = direct_stage_sequence
    elif (
        acquisition_mode == BACKFILL_MODE
        and int(stage_sequence)
        == DIRECT_MIGRATION_STAGE_SEQUENCE_BY_MODE[LIVE_TAIL_MODE]
    ):
        # Sealing a backfill claim at the live-tail sequence would recreate the
        # duplicate DIRECT_MIGRATION stage ID inside one campaign/run/cycle.
        raise ValueError("DIRECT_PUMP_BACKFILL_STAGE_SEQUENCE_COLLIDES_WITH_LIVE_TAIL")
    if verifier_transport_factory is None:
        verified_now_epoch = int(
            datetime.fromisoformat(now.replace("Z", "+00:00")).timestamp()
        )

        def verifier_transport_factory(mint: str, signature: str):  # type: ignore[misc]
            return build_graduation_verifier_transport(
                migration_signature=signature,
                expected_mint=mint,
                now_epoch=verified_now_epoch,
            )

    connection = connect_operational(db_path)
    # Cursor reads/writes are local state: zero source requests, zero transports.
    try:
        cursor_state_before = ensure_direct_migration_cursor(connection, now=now)
        connection.commit()
    except BaseException:
        connection.close()
        raise
    cursor_state_after = cursor_state_before
    cursor_before: str | None = None
    cursor_skip_reason: str | None = None
    cursor_advanced = False
    covered_prefix: list[dict[str, Any]] = []
    migration_request_count = 0
    pumpswap_request_count = 0
    stage_request_ids: list[int] = []
    stage_request_coverage: list[dict[str, Any]] = []
    campaign_units = CampaignSixUnitOwner(
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        started_at=now,
    )
    measured_ledger = campaign_units.ledger
    # Independent action-local observation at measurement time (pre-seal).
    if transport_identity_observer is not None:
        measured_ledger.on_transport_recorded = transport_identity_observer
    local_validations = 0
    started_mono = datetime.now(timezone.utc)
    accounting_block_reason: str | None = None
    elapsed_seconds = 0.0
    confirmed_this_cycle: list[str] = []
    canonically_persisted_signatures: set[str] = set()
    verifications: list[dict[str, Any]] = []
    migration_validation_identities: list[LocalValidationIdentity] = []
    mix: list[dict[str, Any]] = []
    latest_count = 0
    persisted_count = 0
    registry_candidates_withheld = 0
    ledger: dict[str, Any] = {}
    forbidden: dict[str, int] = {}
    intake: dict[str, Any] = {}
    stage_started = False
    last_direct_evidence: dict[str, int | None] = {}
    origin_evidence_by_signature: dict[str, dict[str, int | None]] = {}
    pumpswap_evidence_by_mint: dict[str, dict[str, int | None]] = {}

    def _execute_direct_request(
        *,
        request_kind: str,
        request_key: str,
        payload: Mapping[str, Any],
    ):
        nonlocal migration_request_count, stage_started, last_direct_evidence
        stage_started = True
        adapter = build_direct_pump_migration_adapter(
            enabled=True,
            transport=migration_transport,
        )
        request = build_governed_source_request(
            MIGRATION_SOURCE,
            request_kind,
            request_key=request_key,
            tracking_priority=0,
            payload=payload,
        )
        execution = execute_source_request_with_governor(
            connection, request, adapter, recent_request_count=migration_request_count
        )
        rid = int(execution.request_record.id)
        stage_request_ids.append(rid)
        migration_request_count += 1
        transport_count = 0
        transport_keys: list[list[object]] = []
        measurement_failed = False
        payload = execution.normalized_result.normalized_payload or {}
        if isinstance(payload, Mapping):
            try:
                before = measured_ledger.source_transport_operations
                before_len = len(tuple(measured_ledger.transports))
                record_payload_transports(
                    measured_ledger,
                    payload,
                    default_stage="DIRECT_PUMP_NOMINATION",
                )
                transport_count = int(
                    measured_ledger.source_transport_operations - before
                )
                from printer_v1.discovery.memory_observation_activation import (
                    transport_identity_key_from_mapping,
                )
                for identity in tuple(measured_ledger.transports)[before_len:]:
                    raw = identity.as_dict() if hasattr(identity, "as_dict") else identity
                    if isinstance(raw, Mapping):
                        transport_keys.append(
                            list(transport_identity_key_from_mapping(raw))
                        )
            except MeasuredTransportError:
                measurement_failed = True
                transport_count = 0
        failed = bool(
            execution.normalized_result.failure_type
            or execution.normalized_result.source_status
            not in {SourceStatus.COMPLETE, SourceStatus.PARTIAL}
        )
        members = 0
        if isinstance(payload, Mapping):
            for key in ("signatures", "transactions", "members", "rows"):
                value = payload.get(key)
                if isinstance(value, (list, tuple)):
                    members = len(value)
                    break
        stage_request_coverage.append(
            {
                "source_request_id": rid,
                "source_name": MIGRATION_SOURCE,
                "request_kind": request_kind,
                # The direct stage sequence separates the LIVE_TAIL claim from
                # the BACKFILL claim inside one campaign/run/cycle. Without it
                # both claims would report the same logical intake identity.
                "logical_stage_id": (
                    f"{campaign_id}|{run_id}|{cycle_id}|DIRECT_MIGRATION_INTAKE|"
                    f"{direct_stage_sequence}|{migration_request_count}"
                    if campaign_id and run_id and cycle_id
                    else (
                        f"DIRECT_MIGRATION_INTAKE|{direct_stage_sequence}|"
                        f"{migration_request_count}"
                    )
                ),
                "transport_identity_count": transport_count,
                "transport_identity_keys": transport_keys,
                "normalized_member_count": members,
                "terminal_status": (
                    "BLOCKED" if failed or measurement_failed else "COMPLETED"
                ),
            }
        )
        last_direct_evidence = {
            "source_request_id": rid,
            "source_response_id": (
                None
                if execution.response_record is None
                else int(execution.response_record.id)
            ),
            "source_failure_id": (
                None
                if execution.failure_record is None
                else int(execution.failure_record.id)
            ),
        }
        return execution.normalized_result

    def _governed_migration() -> dict[str, Any]:
        """Execute exactly one bounded migration-targeted signature page.

        One Scheduler claim performs at most one page: LIVE_TAIL (no cursor) or
        BACKFILL (strictly ``before`` the durable position), never both.
        """
        nonlocal cursor_before, cursor_skip_reason
        if acquisition_mode == BACKFILL_MODE and not (
            cursor_state_before is not None and cursor_state_before.backfill_permitted
        ):
            # UNINITIALIZED / EXHAUSTED / BLOCKED_CONTRACT: zero source requests.
            observed = (
                CONTINUITY_UNINITIALIZED
                if cursor_state_before is None
                else cursor_state_before.continuity_state
            )
            cursor_skip_reason = f"BACKFILL_NOT_PERMITTED_{observed}"
            one = intake_migration_events(None)
            one["transaction_rejections"] = []
            one["transaction_source_failures"] = []
            one["transport_operation_count"] = 0
            one["cursor_used"] = False
            one["page_walk"] = []
            one["page_requested"] = False
            one["page_empty"] = False
            one["page_ok"] = True
            return one
        if acquisition_mode == BACKFILL_MODE:
            cursor_before = cursor_state_before.next_before_signature

        page = _execute_direct_request(
            request_kind=SIGNATURE_PAGE_REQUEST_KIND,
            request_key=(
                f"{request_key_prefix}-migration-page-{direct_mode_slug}"
            ),
            payload={
                "request_kind": SIGNATURE_PAGE_REQUEST_KIND,
                "chain": "solana",
                "commitment": "finalized",
                "indexed_address": DIRECT_MIGRATION_INDEXED_ADDRESS,
                # Solana ``until`` semantics are never used.
                "cursor_before": cursor_before,
                # The page may never be larger than this quantum's transaction
                # lookup allowance, or the cursor could advance past signatures
                # that were returned but never inspected.
                "signature_limit": int(max_transaction_lookups),
            },
        )
        page_ok = (
            page.source_status in {SourceStatus.COMPLETE, SourceStatus.PARTIAL}
            and not page.failure_type
        )
        if not page_ok:
            # Transports already measured in _execute_direct_request coverage path.
            # There is no generic Pump-program fallback and no alternate source.
            one = intake_migration_events(None)
            one["direct_pump_live_tail_failure"] = page.failure_type
            one["transport_operation_count"] = 1
            one["cursor_used"] = cursor_before is not None
            one["page_walk"] = []
            one["page_requested"] = True
            one["page_empty"] = False
            one["page_ok"] = False
            return one

        # Transports for the page request are measured in _execute_direct_request.
        # If that measurement failed, coverage is already BLOCKED; continue parsing
        # for candidate-local diagnostics without re-recording transports.
        signatures = list((page.normalized_payload or {}).get("signatures") or ())
        tokens: list[Mapping[str, Any]] = []
        failures: list[str] = []
        source_failures: list[str] = []
        page_walk: list[dict[str, Any]] = []
        operation_count = 1
        stopped = False
        for index, row in enumerate(signatures[:max_transaction_lookups]):
            if not isinstance(row, Mapping):
                failures.append("direct_pump_signature_row_malformed")
                page_walk.append(
                    {
                        "signature": None,
                        "slot": None,
                        "outcome": TRANSACTION_SOURCE_FAILURE,
                        "reason": "direct_pump_signature_row_malformed",
                    }
                )
                stopped = True
                continue
            signature = row.get("signature")
            slot = row.get("slot")
            if not isinstance(signature, str) or not signature:
                failures.append("direct_pump_signature_identity_missing")
                page_walk.append(
                    {
                        "signature": None,
                        "slot": None,
                        "outcome": TRANSACTION_SOURCE_FAILURE,
                        "reason": "direct_pump_signature_identity_missing",
                    }
                )
                stopped = True
                continue
            if stopped:
                # Never inspected: strictly older than an unresolved member.
                page_walk.append(
                    {
                        "signature": signature,
                        "slot": None if not isinstance(slot, int) else slot,
                        "outcome": NOT_INSPECTED,
                        "reason": None,
                    }
                )
                continue
            if row.get("err_present"):
                # A finalized transaction that failed on chain cannot carry a
                # successful migration. Definitive, and costs no lookup.
                page_walk.append(
                    {
                        "signature": signature,
                        "slot": None if not isinstance(slot, int) else slot,
                        "outcome": COVERED_NON_MIGRATION,
                        "reason": "finalized_transaction_error",
                    }
                )
                continue
            tx = _execute_direct_request(
                request_kind=TRANSACTION_REQUEST_KIND,
                request_key=(
                    f"{request_key_prefix}-{direct_mode_slug}"
                    f"-migration-tx-{index + 1}"
                ),
                payload={
                    "request_kind": TRANSACTION_REQUEST_KIND,
                    "chain": "solana",
                    "commitment": "finalized",
                    "signature": signature,
                },
            )
            operation_count += 1
            origin_evidence_by_signature[signature] = dict(last_direct_evidence)
            # Transports already measured in _execute_direct_request coverage path.
            if (
                tx.source_status not in {SourceStatus.COMPLETE, SourceStatus.PARTIAL}
                or tx.failure_type
            ):
                # Most transactions touching the withdraw authority still are not
                # supported migrations. Rejections are recorded fail-closed and
                # never admitted.
                failure = str(
                    tx.failure_type or "direct_pump_transaction_rejected"
                )
                failures.append(failure)
                if not failure.startswith("direct_pump_migration_rejected_"):
                    source_failures.append(failure)
                outcome, reason = classify_direct_migration_transaction_failure(
                    failure,
                    (tx.normalized_payload or {}).get("migration_rejection_digest"),
                )
                page_walk.append(
                    {
                        "signature": signature,
                        "slot": None if not isinstance(slot, int) else slot,
                        "outcome": outcome,
                        "reason": reason,
                    }
                )
                if outcome in _WALK_STOPPING_OUTCOMES:
                    stopped = True
                continue
            tokens.extend(
                item
                for item in (tx.normalized_payload or {}).get("tokens") or ()
                if isinstance(item, Mapping)
            )
            page_walk.append(
                {
                    "signature": signature,
                    "slot": None if not isinstance(slot, int) else slot,
                    "outcome": MIGRATION_LOCATED,
                    "reason": "supported_pump_migration",
                }
            )
            if len(tokens) >= max_candidates:
                # Quantum candidate cap reached. Older page members stay
                # reachable: the next BACKFILL starts strictly before the last
                # covered signature.
                stopped = True
        one = intake_migration_events({"tokens": tokens})
        one["transaction_rejections"] = failures
        one["transaction_source_failures"] = source_failures
        one["transport_operation_count"] = operation_count
        one["cursor_used"] = cursor_before is not None
        one["page_walk"] = page_walk
        one["page_requested"] = True
        one["page_empty"] = not signatures
        one["page_ok"] = True
        return one

    def _governed_verify(mint: str, signature: str, attempt: int):
        nonlocal pumpswap_request_count, stage_started
        stage_started = True
        verifier_transport = verifier_transport_factory(mint, signature)
        adapter = build_pumpswap_adapter(enabled=True, fixture_transport=verifier_transport)
        request = build_governed_source_request(
            VERIFY_SOURCE,
            VERIFY_REQUEST_KIND,
            request_key=(
                f"{request_key_prefix}-{direct_mode_slug}"
                f"-verify-{mint}-a{attempt}"
            ),
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
        rid = int(execution.request_record.id)
        stage_request_ids.append(rid)
        pumpswap_request_count += 1
        transport_count = 0
        transport_keys: list[list[object]] = []
        measurement_failed = False
        payload = execution.normalized_result.normalized_payload or {}
        if isinstance(payload, Mapping):
            try:
                before = measured_ledger.source_transport_operations
                before_len = len(tuple(measured_ledger.transports))
                record_payload_transports(
                    measured_ledger,
                    payload,
                    default_stage="DIRECT_PUMP_NOMINATION",
                )
                transport_count = int(
                    measured_ledger.source_transport_operations - before
                )
                from printer_v1.discovery.memory_observation_activation import (
                    transport_identity_key_from_mapping,
                )
                for identity in tuple(measured_ledger.transports)[before_len:]:
                    raw = identity.as_dict() if hasattr(identity, "as_dict") else identity
                    if isinstance(raw, Mapping):
                        transport_keys.append(
                            list(transport_identity_key_from_mapping(raw))
                        )
            except MeasuredTransportError:
                measurement_failed = True
                transport_count = 0
        failed = bool(
            execution.normalized_result.failure_type
            or execution.normalized_result.source_status
            not in {SourceStatus.COMPLETE, SourceStatus.PARTIAL}
        )
        stage_request_coverage.append(
            {
                "source_request_id": rid,
                "source_name": VERIFY_SOURCE,
                "request_kind": VERIFY_REQUEST_KIND,
                "logical_stage_id": (
                    f"{campaign_id}|{run_id}|{cycle_id}|DIRECT_MIGRATION_VERIFY|"
                    f"{direct_stage_sequence}|{pumpswap_request_count}"
                    if campaign_id and run_id and cycle_id
                    else (
                        f"DIRECT_MIGRATION_VERIFY|{direct_stage_sequence}|"
                        f"{pumpswap_request_count}"
                    )
                ),
                "transport_identity_count": transport_count,
                "transport_identity_keys": transport_keys,
                "normalized_member_count": 1 if not failed else 0,
                "terminal_status": (
                    "BLOCKED" if failed or measurement_failed else "COMPLETED"
                ),
            }
        )
        pumpswap_evidence_by_mint[mint] = {
            "source_request_id": rid,
            "source_response_id": (
                None
                if execution.response_record is None
                else int(execution.response_record.id)
            ),
            "source_failure_id": (
                None
                if execution.failure_record is None
                else int(execution.failure_record.id)
            ),
        }
        return execution.normalized_result

    stage_terminal_status = "COMPLETED"
    stage_first_terminal_cause: str | None = None
    unexpected_exception: BaseException | None = None
    sealed_stage_evidence = None
    try:
        # --- One stateless finalized migration live-tail page ---------------
        round_intakes = [_governed_migration()]
        intake = _merge_intakes(round_intakes)

        # --- Per-candidate governed on-chain verification -------------------
        # Candidates are never persisted until full identity/totals reconcile.
        verifications = []
        pending_persist: list[dict[str, Any]] = []
        confirmed_this_cycle = []
        accounting_block_reason = None
        for pair in intake["valid_pairs"][:max_candidates]:
            mint = pair["mint"]
            signature = pair["signature"]
            vres = _governed_verify(mint, signature, attempt=1)
            verified = (
                vres.source_status in {SourceStatus.COMPLETE, SourceStatus.PARTIAL}
                and not vres.failure_type
            )
            attempts = 1
            payload = vres.normalized_payload or {}
            if not isinstance(payload, Mapping):
                payload = {}
            # Prefer explicit measured metadata; never invent a fixed batch count.
            meta = merge_transport_payload_metadata(payload)
            measured_ops = meta["transport_operations_used"]
            if not measured_ops:
                measured_ops = int(
                    (payload.get("pumpswap_resolution") or {}).get(
                        "transport_operations_used"
                    )
                    or (payload.get("pump_migration_proof") or {}).get(
                        "transport_operations_used"
                    )
                    or 0
                )
            # Transports for the verify request are measured in _governed_verify.
            # Claimed transports without identities still fail closed when the
            # coverage path recorded measurement failure.
            try:
                if not meta["transport_operation_identities"] and measured_ops:
                    raise MeasuredTransportError("TRANSPORT_IDENTITIES_MISSING")
            except MeasuredTransportError as exc:
                accounting_block_reason = f"measured_transport:{exc}"
                record = {
                    "mint": mint,
                    "signature": signature,
                    "verified": False,
                    "verify_attempts": attempts,
                    "transport_operations_used": 0,
                    "failure_type": accounting_block_reason,
                }
                verifications.append(record)
                continue
            record: dict[str, Any] = {
                "mint": mint,
                "signature": signature,
                "verified": verified,
                "verify_attempts": attempts,
                "transport_operations_used": int(measured_ops),
                "response_bytes": int(meta["response_bytes"] or 0),
                "normalized_rows": int(meta["normalized_rows"] or 0),
                "retained_evidence": {
                    "ORIGIN_LINEAGE": dict(
                        origin_evidence_by_signature.get(signature) or {}
                    ),
                    "PUMPSWAP_CONFIRMATION": dict(
                        pumpswap_evidence_by_mint.get(mint) or {}
                    ),
                },
            }
            if not verified:
                record["failure_type"] = vres.failure_type
                verifications.append(record)
                continue

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
                # Fall back to resolution/proof fields for pure offline verifiers.
                resolution = payload.get("pumpswap_resolution") or {}
                proof = payload.get("pump_migration_proof") or {}
                pool = pool or resolution.get("pool_address") or proof.get("pool_address")
                block_time = (
                    block_time
                    if block_time is not None
                    else proof.get("migration_block_time")
                    or resolution.get("migration_block_time")
                )
                slot = (
                    slot
                    if slot is not None
                    else proof.get("migration_slot")
                    or resolution.get("migration_slot")
                )
            if (
                not pool
                or block_time is None
                or not (
                    confirmation.get("confirmed")
                    or (payload.get("pumpswap_confirmation") or {}).get("confirmed")
                    or (payload.get("pump_migration_proof") or {}).get("verified")
                )
            ):
                record["verified"] = False
                record["failure_type"] = "verification_payload_incomplete"
                verifications.append(record)
                continue
            if token and token.get("mint") not in (None, mint):
                record["verified"] = False
                record["failure_type"] = "verification_payload_incomplete"
                verifications.append(record)
                continue

            record["pool"] = str(pool)
            record["graduation_block_time"] = int(block_time)
            record["graduation_slot"] = None if slot is None else int(slot)
            record["market_identity"] = f"solana-mainnet:pumpswap:{pool}"
            record["discovery_channel"] = LATEST_GRADUATED_CHANNEL
            record["newly_persisted"] = False
            verifications.append(record)
            pending_persist.append(record)

        # --- Six-unit identity reconcile BEFORE any candidate persistence ---
        # Emit one LocalValidationIdentity per verification so campaign V2
        # aggregation can derive LOCAL_VALIDATION_STEP from identities only.
        migration_validation_identities = []
        stage_id_for_validations = (
            build_campaign_stage_id(
                campaign_id=str(campaign_id),
                run_id=str(run_id),
                cycle_id=str(cycle_id),
                stage_kind=STAGE_KIND_DIRECT_MIGRATION,
                stage_sequence=int(stage_sequence),
            )
            if all(str(value or "").strip() for value in (campaign_id, run_id, cycle_id))
            else f"{STAGE_KIND_DIRECT_MIGRATION}|{int(stage_sequence)}"
        )
        for index, record in enumerate(verifications, start=1):
            subject = str(
                record.get("mint")
                or record.get("signature")
                or record.get("pool")
                or f"verification-{index}"
            )
            kind = (
                "PUMPSWAP_GRADUATION_VERIFIED"
                if record.get("verified")
                else f"PUMPSWAP_GRADUATION_{str(record.get('failure_type') or 'FAILED').upper()}"
            )
            validation_identity = LocalValidationIdentity(
                stage_id=stage_id_for_validations,
                subject_identity=subject,
                validation_kind=kind,
                validation_ordinal=index,
            )
            migration_validation_identities.append(validation_identity)
            if local_validation_identity_observer is not None:
                local_validation_identity_observer(validation_identity)
        measured_ledger.record_local_validation(
            local_validations + len(migration_validation_identities)
        )
        pumpswap_transport_operations = sum(
            int(record.get("transport_operations_used") or 0) for record in verifications
        )
        migration_transport_operations = int(
            intake.get("transport_operation_count") or 0
        )
        expected_transport_operations = (
            migration_transport_operations + pumpswap_transport_operations
        )
        identity_transport_count = len(measured_ledger.transports)
        pre_persist_reconciled = (
            identity_transport_count == expected_transport_operations
            and migration_transport_operations == migration_request_count
            and accounting_block_reason is None
        )
        if not pre_persist_reconciled:
            accounting_block_reason = (
                accounting_block_reason
                or "TRANSPORT_IDENTITY_TOTALS_MISMATCH_BEFORE_PERSISTENCE"
            )
            pending_persist = []
        else:
            for record in pending_persist:
                newly = record_graduated_candidate(
                    connection,
                    mint=str(record["mint"]),
                    migration_signature=str(record["signature"]),
                    pumpswap_pool=str(record["pool"]),
                    graduation_block_time=int(record["graduation_block_time"]),
                    graduation_slot=(
                        None
                        if record.get("graduation_slot") is None
                        else int(record["graduation_slot"])
                    ),
                    now=now,
                    discovery_channel=LATEST_GRADUATED_CHANNEL,
                    migration_provenance=MIGRATION_PROVENANCE,
                )
                record["newly_persisted"] = newly
                record["verified"] = True
                confirmed_this_cycle.append(str(record["mint"]))
                canonically_persisted_signatures.add(str(record["signature"]))

        connection.commit()

        # --- Contiguous cursor advancement (local state only) ---------------
        # Walk the page in returned RPC order (newest -> oldest) and stop at the
        # first member that is not fully resolved. Partial advancement through a
        # safe prefix is required; all-or-nothing page advancement is forbidden.
        block_reason: str | None = None
        for entry in intake.get("page_walk") or ():
            outcome = str(entry.get("outcome") or "")
            if outcome == COVERED_NON_MIGRATION:
                covered_prefix.append(dict(entry))
                continue
            if outcome == MIGRATION_LOCATED:
                if str(entry.get("signature") or "") in canonically_persisted_signatures:
                    # Covered only AFTER canonical persistence succeeded.
                    covered_prefix.append(dict(entry))
                    continue
                # A genuine migration whose PumpSwap/canonical confirmation did
                # not complete is never skipped.
                break
            if outcome == CONTRACT_BLOCKED:
                block_reason = str(entry.get("reason") or "") or None
                break
            # TRANSACTION_SOURCE_FAILURE / UNRESOLVED_CANDIDATE_LOCAL /
            # NOT_INSPECTED: stop, never advance over it.
            break

        anchor = next(
            (
                item
                for item in reversed(covered_prefix)
                if isinstance(item.get("signature"), str)
                and isinstance(item.get("slot"), int)
            ),
            None,
        )
        covered_count = len(covered_prefix)
        if block_reason is not None:
            # BLOCKED_CONTRACT stops automatic backfill under this exact
            # contract hash + decoder version. A revision creates a new row.
            position_signature = None
            position_slot = None
            if anchor is not None and (
                acquisition_mode == BACKFILL_MODE
                or cursor_state_before.continuity_state == CONTINUITY_UNINITIALIZED
            ):
                position_signature = str(anchor["signature"])
                position_slot = int(anchor["slot"])
            cursor_state_after = mark_direct_migration_cursor_contract_blocked(
                connection,
                reason=block_reason,
                now=now,
                signature=position_signature,
                slot=position_slot,
                covered_count=covered_count,
            )
            cursor_advanced = position_signature is not None
        elif (
            acquisition_mode == BACKFILL_MODE
            and intake.get("page_requested")
            and intake.get("page_ok")
            and intake.get("page_empty")
        ):
            # A successful finalized empty backfill page ends backward traversal
            # for this contract identity. Live tail stays active.
            cursor_state_after = mark_direct_migration_cursor_exhausted(
                connection, now=now
            )
        elif anchor is not None and (
            acquisition_mode == BACKFILL_MODE
            or cursor_state_before.continuity_state == CONTINUITY_UNINITIALIZED
        ):
            # BACKFILL always advances through its covered prefix. LIVE_TAIL may
            # only *bootstrap* a cursor that has no position yet; an established
            # CONTIGUOUS position is historical progress and is never dragged
            # back to the top of the chain by newer live-tail activity.
            cursor_state_after = advance_direct_migration_cursor(
                connection,
                signature=str(anchor["signature"]),
                slot=int(anchor["slot"]),
                covered_count=covered_count,
                now=now,
                mode=acquisition_mode,
            )
            cursor_advanced = True
        elif acquisition_mode == LIVE_TAIL_MODE and intake.get("page_requested"):
            cursor_state_after = touch_direct_migration_cursor_live_tail(
                connection, now=now
            )
        else:
            cursor_state_after = load_direct_migration_cursor(connection) or (
                cursor_state_before
            )
        connection.commit()

        # --- Candidate mix (fresh vs previously confirmed) ------------------
        # ACCOUNTING_BLOCKED is an immediate campaign safe stop: existing
        # registry candidates must not continue toward selection during this
        # attempt. Withhold the entire mix (registry rows are read-only and are
        # left untouched) so a blocked attempt hands nothing forward.
        fresh = set(confirmed_this_cycle)
        mix: list[dict[str, Any]] = []
        latest_count = 0
        persisted_count = 0
        if accounting_block_reason is not None:
            registry_candidates_withheld = len(export_graduated_candidates(connection))
            persisted = []
        else:
            persisted = export_graduated_candidates(connection)
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
            current_verification = next(
                (
                    record
                    for record in verifications
                    if str(record.get("mint") or "") == mint
                    and record.get("verified") is True
                ),
                None,
            )
            mix.append(
                {
                    "mint": mint,
                    "market_identity": str(row["market_identity"]),
                    "pool": str(row["pumpswap_pool"]),
                    "category": category,
                    "lifecycle_state": str(row["lifecycle_state"]),
                    "graduation_block_time": int(row["graduation_block_time"]),
                    "admission_authority": "DIRECT_PUMP_PUMPSWAP",
                    "nomination_source": "direct_pump_migration",
                    "lineage_state": "PUMP_GRADUATION_CONFIRMED",
                    "exact_present_pool_confirmed": True,
                    "direct_pump_evidence": {
                        "mint": mint,
                        "pool": str(row["pumpswap_pool"]),
                        "migration_signature": str(row["migration_signature"]),
                        "graduation_slot": row["graduation_slot"],
                        "graduation_block_time": int(row["graduation_block_time"]),
                        "pumpswap_program_id": str(row["pumpswap_program_id"]),
                        "confirmed": True,
                    },
                    "retained_evidence": dict(
                        (current_verification or {}).get("retained_evidence") or {}
                    ),
                }
            )

        ledger = _ledger_counts(connection, request_ids=stage_request_ids)
        ledger["source_request_ids"] = list(stage_request_ids)
        ledger["source_request_coverage"] = list(stage_request_coverage)
        expected_governed_requests = (
            migration_request_count + pumpswap_request_count
        )
        # Recompute claimed ops for final ledger (already used pre-persist gate).
        pumpswap_transport_operations = sum(
            int(record.get("transport_operations_used") or 0) for record in verifications
        )
        migration_transport_operations = int(
            intake.get("transport_operation_count") or 0
        )
        expected_transport_operations = (
            migration_transport_operations + pumpswap_transport_operations
        )
        campaign_units.close()
        six_units = campaign_units.six_unit_totals()
        six_unit_evidence = campaign_units.durable_evidence()
        identity_transport_count = six_units["SOURCE_TRANSPORT_OPERATION"]
        ledger["transport_operations"] = expected_transport_operations
        ledger["migration_transport_operations"] = migration_transport_operations
        ledger["pumpswap_transport_operations"] = pumpswap_transport_operations
        ledger["governed_requests"] = expected_governed_requests
        ledger["identity_transport_operations"] = identity_transport_count
        ledger["six_unit_totals"] = six_units
        ledger["six_unit_evidence"] = six_unit_evidence
        ledger["measured_transport_ledger"] = measured_ledger.as_dict()
        ledger["pre_persist_accounting_block_reason"] = accounting_block_reason
        ledger["operation_accounting_reconciled"] = (
            int(ledger["source_requests"]) == expected_governed_requests
            and ledger["transport_operations"] == expected_transport_operations
            and migration_transport_operations == migration_request_count
            and identity_transport_count == expected_transport_operations
            and accounting_block_reason is None
            and six_units["SOURCE_RESPONSE_BYTES"] >= 0
            and six_units["NORMALIZED_SOURCE_ROWS"] >= 0
            and six_units["LOCAL_VALIDATION_STEP"] >= 0
        )
        forbidden = _forbidden_deltas(connection)
        elapsed_seconds = max(
            0.0,
            (datetime.now(timezone.utc) - started_mono).total_seconds(),
        )
    except BaseException as exc:
        # Unexpected failure after partial work: seal FAILED before re-raise.
        unexpected_exception = exc
        stage_terminal_status = "FAILED"
        stage_first_terminal_cause = f"{type(exc).__name__}:{exc}"
        if accounting_block_reason is None:
            accounting_block_reason = stage_first_terminal_cause
        elapsed_seconds = max(
            0.0,
            (datetime.now(timezone.utc) - started_mono).total_seconds(),
        )
        raise
    finally:
        connection.close()
        # Seal and ingest exactly once for every started stage before any
        # unexpected exception escapes. Sink failures must not replace the
        # original source/market terminal cause.
        if stage_evidence_sink is not None and stage_started:
            sink_error: BaseException | None = None
            try:
                if not all(
                    str(value or "").strip()
                    for value in (campaign_id, run_id, cycle_id)
                ):
                    raise ValueError(
                        "DIRECT_MIGRATION_STAGE_SINK_REQUIRES_CAMPAIGN_RUN_CYCLE_IDENTITY"
                    )
                if unexpected_exception is not None:
                    terminal_status = "FAILED"
                    terminal_cause = stage_first_terminal_cause
                elif accounting_block_reason is not None:
                    terminal_status = "FAILED"
                    terminal_cause = str(accounting_block_reason)
                elif intake.get("direct_pump_live_tail_failures") or intake.get(
                    "transaction_source_failures"
                ):
                    terminal_status = "BLOCKED"
                    terminal_cause = "PROVIDER_FAILURE"
                else:
                    terminal_status = stage_terminal_status
                    terminal_cause = stage_first_terminal_cause
                sealed_stage_evidence = seal_campaign_stage_evidence(
                    ledger=measured_ledger,
                    stage_id=build_campaign_stage_id(
                        campaign_id=str(campaign_id),
                        run_id=str(run_id),
                        cycle_id=str(cycle_id),
                        stage_kind=STAGE_KIND_DIRECT_MIGRATION,
                        stage_sequence=int(stage_sequence),
                    ),
                    stage_kind=STAGE_KIND_DIRECT_MIGRATION,
                    stage_sequence=int(stage_sequence),
                    stage_terminal_status=terminal_status,
                    stage_first_terminal_cause=terminal_cause,
                    campaign_id=str(campaign_id),
                    run_id=str(run_id),
                    cycle_id=str(cycle_id),
                    sealed_at=now,
                    local_validation_identities=(
                        migration_validation_identities or None
                    ),
                )
                stage_evidence_sink(sealed_stage_evidence)
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
                # Original exception already re-raised from except; finally continues.
            elif sink_error is not None:
                raise sink_error

    if unexpected_exception is not None:
        # Defensive: except already re-raised; keep control-flow honest.
        raise unexpected_exception

    status = "COMPLETE"
    if accounting_block_reason is not None:
        status = "ACCOUNTING_BLOCKED"
    elif intake.get("direct_pump_live_tail_failures") or intake.get(
        "transaction_source_failures"
    ):
        status = "PROVIDER_FAILURE"

    report = {
        "status": status,
        "generated_at": now,
        "elapsed_seconds": round(elapsed_seconds, 6),
        "migration_intake": intake,
        "verifications": verifications,
        "confirmed_this_cycle": confirmed_this_cycle,
        "confirmed_count": len(confirmed_this_cycle),
        "candidate_mix": mix,
        "latest_graduated_count": latest_count,
        "persisted_graduated_count": persisted_count,
        "total_persisted_graduated": len(mix),
        "campaign_safe_stop": accounting_block_reason is not None,
        "registry_candidates_withheld": registry_candidates_withheld,
        "source_operation_ledger": ledger,
        "source_request_ids": list(stage_request_ids),
        "source_request_coverage": list(stage_request_coverage),
        "six_unit_totals": ledger.get("six_unit_totals") or empty_six_unit_totals(),
        "six_unit_evidence": ledger.get("six_unit_evidence"),
        "sealed_stage_evidence": sealed_stage_evidence,
        "accounting_block_reason": accounting_block_reason,
        "forbidden_capability_deltas": forbidden,
        "forbidden_delta_total": sum(forbidden.values()),
        # --- Slice B bounded migration-targeted acquisition facts ------------
        "direct_acquisition_mode": acquisition_mode,
        "indexed_address": DIRECT_MIGRATION_INDEXED_ADDRESS,
        "cursor_before": cursor_before,
        "cursor_used": cursor_before is not None,
        "cursor_skip_reason": cursor_skip_reason,
        "signature_page_limit": int(max_transaction_lookups),
        "signature_pages_requested": 1 if intake.get("page_requested") else 0,
        "page_walk": list(intake.get("page_walk") or ()),
        "cursor_advanced": cursor_advanced,
        "cursor_covered_signatures": len(covered_prefix),
        "cursor_state_before": cursor_state_before.as_dict(),
        "cursor_state_after": cursor_state_after.as_dict(),
        "canonically_persisted_signatures": sorted(canonically_persisted_signatures),
    }
    return report

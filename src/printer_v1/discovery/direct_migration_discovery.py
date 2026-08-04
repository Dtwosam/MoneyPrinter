"""V2-9.8B restored direct Pump migration discovery orchestrator.

Turns one bounded, cursor-free finalized Pump-program live-tail page into
operational graduated Pump.fun candidate supply:

    governed getSignaturesForAddress(Pump program, finalized)
      -> governed getTransaction(signature, finalized)
      -> exact pinned Pump migrate instruction/account verification
      -> resolve unique PumpSwap pool from the signature
      -> confirm PumpSwap owner + exact base_mint
      -> persist PUMPSWAP_GRADUATED_CONFIRMED candidate

The live tail owns no cursor, backfill, recovery or historical completeness
claim. Every RPC operation is separately Source-Governed and recorded before any
candidate is persisted. No wallet, authentication, payment, subscription,
execution, lifecycle, pilot authorization or memory work is performed here.
"""

from __future__ import annotations

import sqlite3
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
    MeasuredTransportError,
    empty_six_unit_totals,
    merge_transport_payload_metadata,
    record_payload_transports,
)

STAGE_KIND_DIRECT_MIGRATION = "DIRECT_MIGRATION"

MIGRATION_REQUEST_KIND = SIGNATURE_PAGE_REQUEST_KIND
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
    campaign_id: str | None = None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    stage_sequence: int = 1,
) -> dict[str, Any]:
    """Run one bounded direct-migration discovery cycle (governed, fail-closed).

    ``migration_transport`` supplies exactly one Solana JSON-RPC response per
    governed live-tail page/transaction request. ``verifier_transport_factory``
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
    if collection_rounds != 1:
        raise ValueError("DIRECT_PUMP_LIVE_TAIL_REQUIRES_ONE_COLLECTION_ROUND")
    if settle_seconds != 0.0:
        raise ValueError("FINALIZED_DIRECT_PUMP_LIVE_TAIL_FORBIDS_SETTLE_SLEEP")
    if reverify_on_transient or reverify_settle_seconds != 0.0:
        raise ValueError("DIRECT_PUMP_LIVE_TAIL_FORBIDS_AUTOMATIC_REVERIFY")
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
    verifications: list[dict[str, Any]] = []
    mix: list[dict[str, Any]] = []
    latest_count = 0
    persisted_count = 0
    registry_candidates_withheld = 0
    ledger: dict[str, Any] = {}
    forbidden: dict[str, int] = {}
    intake: dict[str, Any] = {}
    stage_started = False

    def _execute_direct_request(
        *,
        request_kind: str,
        request_key: str,
        payload: Mapping[str, Any],
    ):
        nonlocal migration_request_count, stage_started
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
        measurement_failed = False
        payload = execution.normalized_result.normalized_payload or {}
        if isinstance(payload, Mapping):
            try:
                before = measured_ledger.source_transport_operations
                record_payload_transports(
                    measured_ledger,
                    payload,
                    default_stage="DIRECT_PUMP_NOMINATION",
                )
                transport_count = int(
                    measured_ledger.source_transport_operations - before
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
                "logical_stage_id": (
                    f"{campaign_id}|{run_id}|{cycle_id}|DIRECT_MIGRATION_INTAKE|"
                    f"{migration_request_count}"
                    if campaign_id and run_id and cycle_id
                    else f"DIRECT_MIGRATION_INTAKE|{migration_request_count}"
                ),
                "transport_identity_count": transport_count,
                "normalized_member_count": members,
                "terminal_status": (
                    "BLOCKED" if failed or measurement_failed else "COMPLETED"
                ),
            }
        )
        return execution.normalized_result

    def _governed_migration() -> dict[str, Any]:
        page = _execute_direct_request(
            request_kind=SIGNATURE_PAGE_REQUEST_KIND,
            request_key=f"{request_key_prefix}-migration-page",
            payload={
                "request_kind": SIGNATURE_PAGE_REQUEST_KIND,
                "chain": "solana",
                "commitment": "finalized",
                "cursor": None,
            },
        )
        page_ok = (
            page.source_status in {SourceStatus.COMPLETE, SourceStatus.PARTIAL}
            and not page.failure_type
        )
        if not page_ok:
            # Transports already measured in _execute_direct_request coverage path.
            one = intake_migration_events(None)
            one["direct_pump_live_tail_failure"] = page.failure_type
            one["transport_operation_count"] = 1
            return one

        # Transports for the page request are measured in _execute_direct_request.
        # If that measurement failed, coverage is already BLOCKED; continue parsing
        # for candidate-local diagnostics without re-recording transports.
        signatures = list((page.normalized_payload or {}).get("signatures") or ())
        tokens: list[Mapping[str, Any]] = []
        failures: list[str] = []
        source_failures: list[str] = []
        operation_count = 1
        for index, row in enumerate(signatures[:MAX_TRANSACTION_LOOKUPS]):
            if not isinstance(row, Mapping):
                failures.append("direct_pump_signature_row_malformed")
                continue
            signature = row.get("signature")
            if not isinstance(signature, str) or not signature:
                failures.append("direct_pump_signature_identity_missing")
                continue
            tx = _execute_direct_request(
                request_kind=TRANSACTION_REQUEST_KIND,
                request_key=f"{request_key_prefix}-migration-tx-{index + 1}",
                payload={
                    "request_kind": TRANSACTION_REQUEST_KIND,
                    "chain": "solana",
                    "commitment": "finalized",
                    "signature": signature,
                },
            )
            operation_count += 1
            # Transports already measured in _execute_direct_request coverage path.
            if (
                tx.source_status not in {SourceStatus.COMPLETE, SourceStatus.PARTIAL}
                or tx.failure_type
            ):
                # Most finalized Pump-program transactions are not migrations.
                # Rejections are recorded fail-closed and never admitted.
                failure = str(
                    tx.failure_type or "direct_pump_transaction_rejected"
                )
                failures.append(failure)
                if not failure.startswith("direct_pump_migration_rejected_"):
                    source_failures.append(failure)
                continue
            tokens.extend(
                item
                for item in (tx.normalized_payload or {}).get("tokens") or ()
                if isinstance(item, Mapping)
            )
            if len(tokens) >= max_candidates:
                break
        one = intake_migration_events({"tokens": tokens})
        one["transaction_rejections"] = failures
        one["transaction_source_failures"] = source_failures
        one["transport_operation_count"] = operation_count
        one["cursor_used"] = False
        return one

    def _governed_verify(mint: str, signature: str, attempt: int):
        nonlocal pumpswap_request_count, stage_started
        stage_started = True
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
        rid = int(execution.request_record.id)
        stage_request_ids.append(rid)
        pumpswap_request_count += 1
        transport_count = 0
        measurement_failed = False
        payload = execution.normalized_result.normalized_payload or {}
        if isinstance(payload, Mapping):
            try:
                before = measured_ledger.source_transport_operations
                record_payload_transports(
                    measured_ledger,
                    payload,
                    default_stage="DIRECT_PUMP_NOMINATION",
                )
                transport_count = int(
                    measured_ledger.source_transport_operations - before
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
                    f"{pumpswap_request_count}"
                    if campaign_id and run_id and cycle_id
                    else f"DIRECT_MIGRATION_VERIFY|{pumpswap_request_count}"
                ),
                "transport_identity_count": transport_count,
                "normalized_member_count": 1 if not failed else 0,
                "terminal_status": (
                    "BLOCKED" if failed or measurement_failed else "COMPLETED"
                ),
            }
        )
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
        measured_ledger.record_local_validation(local_validations + len(verifications))
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
    }
    return report

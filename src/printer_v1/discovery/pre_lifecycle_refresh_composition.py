"""V2-9.8B persistent multi-source pre-lifecycle refresh composition.

This module composes one bounded delayed fresh-acquisition opportunity from the
already-approved source owners. It is not a second discovery engine. The same
Source Governor evidence owners used by permanent eligible supply are reopened:

* direct Pump finalized live-tail + exact Pump/PumpSwap verification;
* DexScreener fresh-profile nomination;
* GeckoTerminal fresh-pool nomination;
* bounded opposite-source unknown-liquidity backup; and
* PumpSwap protocol confirmation/promotion.

Fresh-source order is categorical and rotates by refresh ordinal only. Candidate
values never affect source order. Existing durable candidate stores remain the
only candidate/evidence authorities; this composition merely records exact
identities observed during the refresh for the acquisition ledger.

Locked: no scoring/ranking/confidence/weights, no retrieval/decisions/positions/
trades/audits/PnL, no retry/restart/resume/successor, no paid API.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from printer_v1.discovery.combined_executor import ensure_cycle_discovery_batch
from printer_v1.discovery.permanent_discovery_availability import (
    StageBudget,
    next_protocol_confirmation_stage_sequence,
    process_protocol_confirmation_queue,
    record_fresh_pool_nominations,
    run_bounded_unknown_liquidity_backup,
    run_geckoterminal_fresh_nomination,
)
from printer_v1.sources.direct_pump_migration import MAX_TRANSACTION_LOOKUPS

PUMP_FRESH_CHANNEL = "direct_pump_finalized_live_tail"
DEXSCREENER_FRESH_CHANNEL = "dexscreener_fresh_profiles"
GECKOTERMINAL_NOMINATION_CHANNEL = "geckoterminal_fresh_pool_nomination"
UNKNOWN_LIQUIDITY_BACKUP_CHANNEL = "unknown_liquidity_opposite_source_backup"
PROTOCOL_CONFIRMATION_CHANNEL = "exact_pump_pumpswap_graduation_verify"

_FRESH_CHANNEL_ORDER = (
    PUMP_FRESH_CHANNEL,
    DEXSCREENER_FRESH_CHANNEL,
    GECKOTERMINAL_NOMINATION_CHANNEL,
)
# One signature page + at most MAX_TRANSACTION_LOOKUPS transaction reads + one
# exact PumpSwap verification. max_candidates is intentionally one per refresh;
# later ordinals provide additional bounded opportunities without resetting the
# campaign budget.
_PUMP_MAX_CANDIDATES_PER_REFRESH = 1
_PUMP_WORST_CASE_SOURCE_OPERATIONS = (
    1 + int(MAX_TRANSACTION_LOOKUPS) + _PUMP_MAX_CANDIDATES_PER_REFRESH
)


class PreLifecycleRefreshCompositionError(RuntimeError):
    """Fail-closed pre-lifecycle refresh composition fault."""


def build_cycle_discovery_batch_resolver(
    *,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    cycle_id: str,
    cycle_cutoff: str,
    policy_version: str,
    provider_contract_versions: Mapping[str, Any],
    git_provenance_identity: str,
    campaign_selection_seed: str,
) -> Callable[[sqlite3.Connection, str, int], str]:
    """Create or reuse the exact cycle's canonical discovery batch."""
    contract_versions = dict(provider_contract_versions)

    def resolve(
        connection: sqlite3.Connection, now: str, refresh_ordinal: int
    ) -> str:
        del refresh_ordinal
        return ensure_cycle_discovery_batch(
            connection,
            campaign_id=campaign_id,
            configuration_id=configuration_id,
            run_id=run_id,
            cycle_id=cycle_id,
            cycle_cutoff=cycle_cutoff,
            policy_version=policy_version,
            provider_contract_versions=contract_versions,
            git_provenance_identity=git_provenance_identity,
            campaign_selection_seed=campaign_selection_seed,
            now=now,
        )

    return resolve


def _rotated_fresh_channels(refresh_ordinal: int) -> tuple[str, ...]:
    ordinal = int(refresh_ordinal)
    if ordinal < 1:
        raise PreLifecycleRefreshCompositionError("INVALID_REFRESH_ORDINAL")
    offset = (ordinal - 1) % len(_FRESH_CHANNEL_ORDER)
    return _FRESH_CHANNEL_ORDER[offset:] + _FRESH_CHANNEL_ORDER[:offset]


def _exact_identity(raw: Mapping[str, Any]) -> dict[str, str] | None:
    mint = str(raw.get("mint") or raw.get("mint_identity") or "").strip()
    pool = str(
        raw.get("pool")
        or raw.get("pair_address")
        or raw.get("pairAddress")
        or raw.get("market_identity")
        or ""
    ).strip()
    if not mint or not pool:
        return None
    return {"mint": mint, "pool": pool}


def _dedup_exact_identities(items: list[Mapping[str, Any]]) -> tuple[dict[str, str], ...]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for raw in items:
        identity = _exact_identity(raw)
        if identity is None:
            continue
        key = (identity["mint"], identity["pool"])
        if key in seen:
            continue
        seen.add(key)
        result.append(identity)
    return tuple(result)


def _cooperative_checkpointed_request(
    connection: sqlite3.Connection,
    *,
    request_key: str,
    prefix: bool = False,
    allow_many: bool = False,
) -> bool:
    """True only for terminal source work already sealed into attempt evidence.

    A durable source row without attempt evidence means the previous claim did
    not cross its cooperative checkpoint. Repeating that provider call would be
    unsafe, so the refresh fails closed instead.
    """
    comparator = "LIKE" if prefix else "="
    value = f"{request_key}%" if prefix else request_key
    rows = connection.execute(
        f"SELECT id FROM printer_source_requests WHERE request_key {comparator} ? ORDER BY id",
        (value,),
    ).fetchall()
    if not rows:
        return False
    if not allow_many and len(rows) != 1:
        raise PreLifecycleRefreshCompositionError(
            "COOPERATIVE_REFRESH_REQUEST_IDENTITY_AMBIGUOUS"
        )
    table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='printer_pre_admission_attempt_evidence'"
    ).fetchone()
    if table is None:
        raise PreLifecycleRefreshCompositionError(
            "COOPERATIVE_REFRESH_ATTEMPT_EVIDENCE_MISSING"
        )
    for (request_id,) in rows:
        responses = int(connection.execute(
            "SELECT COUNT(*) FROM printer_source_responses WHERE source_request_id=?",
            (int(request_id),),
        ).fetchone()[0])
        failures = int(connection.execute(
            "SELECT COUNT(*) FROM printer_source_failures WHERE source_request_id=?",
            (int(request_id),),
        ).fetchone()[0])
        if responses + failures != 1:
            raise PreLifecycleRefreshCompositionError(
                "COOPERATIVE_REFRESH_REQUEST_TERMINAL_AMBIGUOUS"
            )
        checkpointed = int(connection.execute(
            """SELECT COUNT(*) FROM printer_pre_admission_attempt_evidence
               WHERE source_request_id=?
                 AND evidence_kind IN ('SOURCE_REQUEST_TERMINAL','PROVIDER_FAILURE')""",
            (int(request_id),),
        ).fetchone()[0])
        if checkpointed != 1:
            raise PreLifecycleRefreshCompositionError(
                "COOPERATIVE_REFRESH_REQUEST_NOT_CHECKPOINTED"
            )
    return True


def cycle_pump_live_tail_head_already_completed(
    connection: sqlite3.Connection,
    *,
    request_key_root: str,
) -> bool:
    """True when this cycle already sealed Pump live-tail address|before=HEAD.

    Refresh re-entry may not re-issue that canonical transport merely because
    the refresh request-key prefix is new. Failures, partial/dirty responses,
    foreign roots, different cursors, and malformed identities do not count.
    """
    from printer_v1.discovery.permanent_discovery_availability import (
        request_key_belongs_to_root,
    )
    from printer_v1.sources.direct_pump_migration import (
        DIRECT_MIGRATION_INDEXED_ADDRESS,
        SIGNATURE_PAGE_REQUEST_KIND,
        SIGNATURE_PAGE_TARGET_CATEGORY,
        direct_migration_signature_page_target_identity,
    )
    from printer_v1.sources.measured_transport import (
        MeasuredTransportError,
        canonical_transport_identity_key,
    )

    root = str(request_key_root or "").strip()
    if not root:
        return False
    tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('printer_source_requests','printer_source_responses')"
        ).fetchall()
    }
    if tables != {"printer_source_requests", "printer_source_responses"}:
        return False
    try:
        expected_identity = canonical_transport_identity_key(
            {
                "stage": "DIRECT_PUMP_NOMINATION",
                "source_name": "solana_rpc",
                "governed_request_kind": SIGNATURE_PAGE_REQUEST_KIND,
                "method_or_endpoint": "getSignaturesForAddress",
                "within_request_ordinal": 1,
                "target_category": SIGNATURE_PAGE_TARGET_CATEGORY,
                "target_identity": direct_migration_signature_page_target_identity(
                    indexed_address=DIRECT_MIGRATION_INDEXED_ADDRESS,
                    cursor_before=None,
                ),
            }
        )
    except (MeasuredTransportError, TypeError, ValueError):
        return False

    rows = connection.execute(
        """
        SELECT r.request_key,s.normalized_payload_json
        FROM printer_source_requests AS r
        JOIN printer_source_responses AS s ON s.source_request_id=r.id
        WHERE (r.request_key=? OR r.request_key LIKE ?)
          AND r.source_name='solana_rpc'
          AND r.request_kind=?
          AND s.source_status='COMPLETE'
          AND s.data_quality_label='CLEAN_DATA'
        ORDER BY r.id ASC
        """,
        (root, f"{root}%", SIGNATURE_PAGE_REQUEST_KIND),
    ).fetchall()
    for row in rows:
        values = dict(row) if hasattr(row, "keys") else {
            "request_key": row[0],
            "normalized_payload_json": row[1],
        }
        request_key = str(values.get("request_key") or "")
        if not request_key_belongs_to_root(request_key, root):
            continue
        raw_payload = values.get("normalized_payload_json")
        if not raw_payload:
            continue
        try:
            payload = json.loads(str(raw_payload))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(payload, Mapping):
            continue
        identities = payload.get("transport_operation_identities") or ()
        if isinstance(identities, (str, bytes)) or not isinstance(identities, Sequence):
            continue
        for raw_identity in identities:
            if not isinstance(raw_identity, Mapping):
                continue
            try:
                identity_key = canonical_transport_identity_key(raw_identity)
            except (MeasuredTransportError, TypeError, ValueError):
                continue
            if identity_key == expected_identity:
                return True
    return False


def _cooperative_next_request_bound_seconds() -> float:
    from printer_v1.discovery.eligible_token_supply import (
        AcquisitionQuantumKind,
        acquisition_governed_request_bound,
    )
    return float(
        acquisition_governed_request_bound(
            AcquisitionQuantumKind.DIRECT_MIGRATION,
            request_kind="PUMPSWAP_EXACT_VERIFICATION",
            checkpoint_reserve_seconds=5.0,
        ).worst_case_seconds
    )


def build_pre_lifecycle_refresh_stage(
    *,
    db_path: str | Path,
    request_key_prefix: str,
    migration_transport: Any | None = None,
    verifier_transport_factory: Any | None = None,
    locator_transport: Any | None = None,
    geckoterminal_nomination_transport: Any | None = None,
    dexscreener_backup_transport_factory: Any | None = None,
    geckoterminal_backup_transport_factory: Any | None = None,
    protocol_account_batch_transport: Any | None = None,
    protocol_account_batch_transport_factory: Any | None = None,
    stage_evidence_sink: Callable[[Mapping[str, Any]], None] | None = None,
    transport_identity_observer: Callable[[Any], None] | None = None,
    local_validation_identity_observer: Callable[[Any], None] | None = None,
) -> Callable[..., Mapping[str, Any]]:
    """Build one bounded, ordinal-rotated, Source-Governed refresh stage."""
    refresh_db_path = Path(db_path)

    def refresh_stage(
        connection: sqlite3.Connection,
        *,
        campaign_id: str,
        run_id: str,
        cycle_id: str,
        discovery_work_id: str,
        scheduler_job_id: int,
        refresh_ordinal: int,
        source_operations_remaining: int,
        now: str,
        cooperative_yield: bool = False,
        cooperative_stage_budget: StageBudget | None = None,
        **_ignored: Any,
    ) -> Mapping[str, Any]:
        del discovery_work_id, scheduler_job_id
        remaining = int(source_operations_remaining)
        if remaining < 0:
            raise PreLifecycleRefreshCompositionError("NEGATIVE_SOURCE_OPERATIONS_REMAINING")

        refresh_stage_sequence = int(refresh_ordinal) + 1
        source_operations = 0
        provider_failures = 0
        channels_unavailable: list[str] = []
        channels_attempted: list[str] = []
        channels_skipped: list[dict[str, str]] = []
        observed_identities: list[Mapping[str, Any]] = []
        promoted: list[dict[str, Any]] = []
        stage_reports: dict[str, Any] = {}

        if remaining == 0:
            return {
                "source_operations": 0,
                "provider_failures": 0,
                "channels_unavailable": (),
                "channels_attempted": (),
                "channels_skipped": tuple(
                    {"channel": channel, "reason": "SOURCE_BUDGET_EXHAUSTED"}
                    for channel in (
                        *_FRESH_CHANNEL_ORDER,
                        UNKNOWN_LIQUIDITY_BACKUP_CHANNEL,
                        PROTOCOL_CONFIRMATION_CHANNEL,
                    )
                ),
                "newly_observed_exact_identities": (),
                "promoted_observation_eligible": (),
                "stage_reports": {},
                "budget_exhausted_before_refresh": True,
            }

        if cooperative_yield and cooperative_stage_budget is None:
            raise PreLifecycleRefreshCompositionError(
                "COOPERATIVE_STAGE_BUDGET_REQUIRED"
            )
        stage_budget = (
            cooperative_stage_budget
            if cooperative_yield
            else StageBudget.permanent_discovery_default()
        )
        if not isinstance(stage_budget, StageBudget):
            raise PreLifecycleRefreshCompositionError(
                "COOPERATIVE_STAGE_BUDGET_INVALID"
            )
        fresh_budget_stage = (
            "final_refresh_handoff" if cooperative_yield else "intake"
        )

        def budget_left() -> int:
            return remaining - source_operations

        def charge(report: Mapping[str, Any], *, channel: str) -> int:
            nonlocal source_operations
            used = int(report.get("source_requests") or 0)
            if used < 0 or used > budget_left():
                raise PreLifecycleRefreshCompositionError(
                    f"REFRESH_SOURCE_OPERATION_BUDGET_MISMATCH:{channel}:{used}:{budget_left()}"
                )
            source_operations += used
            return used

        def cooperative_result(next_kind: str) -> Mapping[str, Any]:
            return {
                "source_operations": source_operations,
                "provider_failures": provider_failures,
                "channels_unavailable": tuple(dict.fromkeys(channels_unavailable)),
                "channels_attempted": tuple(channels_attempted),
                "channels_skipped": tuple(channels_skipped),
                "newly_observed_exact_identities": _dedup_exact_identities(
                    observed_identities
                ),
                "promoted_observation_eligible": tuple(promoted),
                "stage_reports": stage_reports,
                "budget_exhausted_before_refresh": False,
                "cooperative_incomplete": True,
                "next_governed_request_kind": str(next_kind),
                "next_governed_request_worst_case_seconds": (
                    _cooperative_next_request_bound_seconds()
                ),
            }

        rotated_channels = _rotated_fresh_channels(refresh_ordinal)
        selected_channels = (
            rotated_channels[:1] if cooperative_yield else rotated_channels
        )
        for channel in selected_channels:
            if channel == PUMP_FRESH_CHANNEL:
                if migration_transport is None:
                    channels_skipped.append(
                        {"channel": channel, "reason": "MIGRATION_TRANSPORT_NOT_CONFIGURED"}
                    )
                    continue
                if budget_left() < _PUMP_WORST_CASE_SOURCE_OPERATIONS:
                    channels_skipped.append(
                        {"channel": channel, "reason": "INSUFFICIENT_WORST_CASE_SOURCE_BUDGET"}
                    )
                    continue
                if cycle_pump_live_tail_head_already_completed(
                    connection, request_key_root=request_key_prefix
                ):
                    from printer_v1.sources.direct_pump_migration import (
                        DIRECT_MIGRATION_INDEXED_ADDRESS,
                        direct_migration_signature_page_target_identity,
                    )

                    channels_skipped.append(
                        {
                            "channel": channel,
                            "reason": (
                                "CANONICAL_PUMP_LIVE_TAIL_HEAD_ALREADY_COMPLETED"
                            ),
                        }
                    )
                    stage_reports[channel] = {
                        "status": "CANONICAL_TRANSPORT_ALREADY_COMPLETED",
                        "source_requests": 0,
                        "target_identity": (
                            direct_migration_signature_page_target_identity(
                                indexed_address=DIRECT_MIGRATION_INDEXED_ADDRESS,
                                cursor_before=None,
                            )
                        ),
                    }
                    continue
                channels_attempted.append(channel)
                from printer_v1.discovery.direct_migration_discovery import (
                    run_direct_migration_discovery,
                )

                report = dict(
                    run_direct_migration_discovery(
                        refresh_db_path,
                        migration_transport=migration_transport,
                        verifier_transport_factory=verifier_transport_factory,
                        now=now,
                        request_key_prefix=(
                            f"{request_key_prefix}-refresh-{refresh_ordinal}-pump"
                        ),
                        max_candidates=_PUMP_MAX_CANDIDATES_PER_REFRESH,
                        max_transaction_lookups=(
                            6 if cooperative_yield else MAX_TRANSACTION_LOOKUPS
                        ),
                        collection_rounds=1,
                        settle_seconds=0.0,
                        reverify_on_transient=False,
                        reverify_settle_seconds=0.0,
                        stage_evidence_sink=stage_evidence_sink,
                        transport_identity_observer=transport_identity_observer,
                        local_validation_identity_observer=(
                            local_validation_identity_observer
                        ),
                        campaign_id=campaign_id,
                        run_id=run_id,
                        cycle_id=cycle_id,
                        stage_sequence=refresh_stage_sequence,
                        cooperative_request_limit=(1 if cooperative_yield else None),
                        cooperative_checkpoint_reserve_seconds=5.0,
                    )
                )
                report["source_requests"] = int(
                    report.get("new_governed_request_count")
                    if report.get("new_governed_request_count") is not None
                    else len(report.get("source_request_ids") or ())
                )
                charge(report, channel=channel)
                stage_reports[channel] = report
                if report.get("status") == "ACQUISITION_QUANTUM_YIELDED":
                    return {
                        "source_operations": source_operations,
                        "provider_failures": provider_failures,
                        "channels_unavailable": tuple(channels_unavailable),
                        "channels_attempted": tuple(channels_attempted),
                        "channels_skipped": tuple(channels_skipped),
                        "newly_observed_exact_identities": (),
                        "promoted_observation_eligible": (),
                        "stage_reports": stage_reports,
                        "budget_exhausted_before_refresh": False,
                        "cooperative_incomplete": True,
                        "next_governed_request_kind": report.get(
                            "next_governed_request_kind"
                        ),
                        "next_governed_request_worst_case_seconds": report.get(
                            "next_governed_request_worst_case_seconds"
                        ),
                    }
                stage_budget.consume(fresh_budget_stage, 1)
                if report.get("status") == "ACCOUNTING_BLOCKED":
                    raise PreLifecycleRefreshCompositionError(
                        "DIRECT_PUMP_REFRESH_ACCOUNTING_BLOCKED"
                    )
                if report.get("status") == "PROVIDER_FAILURE":
                    provider_failures += 1
                    channels_unavailable.append(channel)
                for item in report.get("verifications") or ():
                    if isinstance(item, Mapping) and item.get("verified") is True:
                        observed_identities.append(item)

            elif channel == DEXSCREENER_FRESH_CHANNEL:
                if budget_left() < 1:
                    channels_skipped.append(
                        {"channel": channel, "reason": "SOURCE_BUDGET_EXHAUSTED"}
                    )
                    continue
                dex_request_key = (
                    f"{request_key_prefix}-refresh-{refresh_ordinal}-dex-fresh"
                )
                if cooperative_yield and _cooperative_checkpointed_request(
                    connection, request_key=dex_request_key
                ):
                    channels_attempted.append(channel)
                    stage_reports[channel] = {
                        "status": "COOPERATIVE_CHECKPOINT_REPLAY",
                        "source_requests": 0,
                        "request_key": dex_request_key,
                    }
                    continue
                stage_budget.consume(fresh_budget_stage, 1)
                channels_attempted.append(channel)
                from printer_v1.operator_cli.graduated_supply_front_door import (
                    run_fresh_profile_locator,
                )

                report = dict(
                    run_fresh_profile_locator(
                        refresh_db_path,
                        transport=locator_transport,
                        request_key=dex_request_key,
                        now=now,
                        stage_evidence_sink=stage_evidence_sink,
                        transport_identity_observer=transport_identity_observer,
                        campaign_id=campaign_id,
                        run_id=run_id,
                        cycle_id=cycle_id,
                        stage_sequence=refresh_stage_sequence,
                    )
                )
                charge(report, channel=channel)
                stage_reports[channel] = report
                if report.get("accounting_blocker"):
                    raise PreLifecycleRefreshCompositionError(
                        "DEXSCREENER_REFRESH_ACCOUNTING_BLOCKED"
                    )
                if report.get("status") not in {"ok", "empty"}:
                    provider_failures += 1
                    channels_unavailable.append(channel)
                observations = [
                    dict(item)
                    for item in report.get("pool_observations") or ()
                    if isinstance(item, Mapping)
                ]
                if observations:
                    merge = record_fresh_pool_nominations(
                        connection,
                        observations=observations,
                        source="dexscreener",
                        request_id=int(report["request_id"]),
                        response_id=(
                            None
                            if report.get("response_id") is None
                            else int(report["response_id"])
                        ),
                        now=now,
                        campaign_id=campaign_id,
                    )
                    report["nomination_merge"] = merge
                    observed_identities.extend(observations)

            elif channel == GECKOTERMINAL_NOMINATION_CHANNEL:
                if budget_left() < 1:
                    channels_skipped.append(
                        {"channel": channel, "reason": "SOURCE_BUDGET_EXHAUSTED"}
                    )
                    continue
                gt_request_key = (
                    f"{request_key_prefix}-refresh-{refresh_ordinal}-gt-new-pools"
                )
                if cooperative_yield and _cooperative_checkpointed_request(
                    connection, request_key=gt_request_key
                ):
                    channels_attempted.append(channel)
                    stage_reports[channel] = {
                        "status": "COOPERATIVE_CHECKPOINT_REPLAY",
                        "source_requests": 0,
                        "request_key": gt_request_key,
                    }
                    continue
                stage_budget.consume(fresh_budget_stage, 1)
                channels_attempted.append(channel)
                report = dict(
                    run_geckoterminal_fresh_nomination(
                        connection,
                        request_key=gt_request_key,
                        now=now,
                        campaign_id=campaign_id,
                        run_id=run_id,
                        cycle_id=cycle_id,
                        transport=geckoterminal_nomination_transport,
                        stage_evidence_sink=stage_evidence_sink,
                        transport_identity_observer=transport_identity_observer,
                        stage_sequence=refresh_stage_sequence,
                    )
                )
                charge(report, channel=channel)
                stage_reports[channel] = report
                if report.get("accounting_blocker"):
                    raise PreLifecycleRefreshCompositionError(
                        "GECKOTERMINAL_REFRESH_ACCOUNTING_BLOCKED"
                    )
                if report.get("failure_type"):
                    provider_failures += 1
                    channels_unavailable.append(channel)
                observed_identities.extend(
                    dict(item)
                    for item in report.get("nominations") or ()
                    if isinstance(item, Mapping)
                )

        if cooperative_yield and source_operations > 0:
            connection.commit()
            return cooperative_result(UNKNOWN_LIQUIDITY_BACKUP_CHANNEL)

        # Conversion/reconciliation owners run after all fresh source channels.
        # Candidate-local absence/failure in one source never suppresses peers.
        conversion_allowed = not (
            cooperative_yield and selected_channels == (PUMP_FRESH_CHANNEL,)
        )
        backup_request_prefix = (
            f"{request_key_prefix}-refresh-{refresh_ordinal}-liq-backup"
        )
        backup_checkpointed = bool(
            cooperative_yield
            and _cooperative_checkpointed_request(
                connection, request_key=backup_request_prefix, prefix=True
            )
        )
        if backup_checkpointed:
            channels_attempted.append(UNKNOWN_LIQUIDITY_BACKUP_CHANNEL)
            stage_reports[UNKNOWN_LIQUIDITY_BACKUP_CHANNEL] = {
                "status": "COOPERATIVE_CHECKPOINT_REPLAY",
                "source_requests": 0,
                "request_key_prefix": backup_request_prefix,
            }
        elif (
            conversion_allowed
            and budget_left() >= 1
            and stage_budget.available("reconciliation") >= 1
        ):
            channels_attempted.append(UNKNOWN_LIQUIDITY_BACKUP_CHANNEL)
            report = dict(
                run_bounded_unknown_liquidity_backup(
                    connection,
                    stage_budget=stage_budget,
                    now=now,
                    campaign_id=campaign_id,
                    run_id=run_id,
                    cycle_id=cycle_id,
                    request_key_prefix=backup_request_prefix,
                    dexscreener_transport_factory=(
                        dexscreener_backup_transport_factory
                    ),
                    geckoterminal_transport_factory=(
                        geckoterminal_backup_transport_factory
                    ),
                    transport_identity_observer=transport_identity_observer,
                    stage_evidence_sink=stage_evidence_sink,
                    max_backups=1,
                    stage_sequence_base=int(refresh_ordinal),
                )
            )
            charge(report, channel=UNKNOWN_LIQUIDITY_BACKUP_CHANNEL)
            stage_reports[UNKNOWN_LIQUIDITY_BACKUP_CHANNEL] = report
            if report.get("accounting_blocker"):
                raise PreLifecycleRefreshCompositionError(
                    "UNKNOWN_LIQUIDITY_REFRESH_ACCOUNTING_BLOCKED"
                )
        else:
            channels_skipped.append(
                {
                    "channel": UNKNOWN_LIQUIDITY_BACKUP_CHANNEL,
                    "reason": "SOURCE_BUDGET_EXHAUSTED",
                }
            )

        if cooperative_yield and source_operations > 0:
            connection.commit()
            return cooperative_result(PROTOCOL_CONFIRMATION_CHANNEL)

        protocol_request_prefix = (
            f"{request_key_prefix}-refresh-{refresh_ordinal}-protocol"
        )
        if cooperative_yield:
            _cooperative_checkpointed_request(
                connection,
                request_key=protocol_request_prefix,
                prefix=True,
                allow_many=True,
            )
        if (
            conversion_allowed
            and budget_left() >= 1
            and stage_budget.available("protocol_confirmation") >= 1
        ):
            channels_attempted.append(PROTOCOL_CONFIRMATION_CHANNEL)
            protocol_stage_sequence = (
                next_protocol_confirmation_stage_sequence(
                    connection,
                    request_key_prefix=request_key_prefix,
                )
                if cooperative_yield
                else refresh_stage_sequence
            )
            report = dict(
                process_protocol_confirmation_queue(
                    connection,
                    stage_budget=stage_budget,
                    now=now,
                    campaign_id=campaign_id,
                    run_id=run_id,
                    cycle_id=cycle_id,
                    max_confirmations=1,
                    account_batch_transport=protocol_account_batch_transport,
                    account_batch_transport_factory=(
                        protocol_account_batch_transport_factory
                    ),
                    stage_evidence_sink=stage_evidence_sink,
                    transport_identity_observer=transport_identity_observer,
                    local_validation_identity_observer=(
                        local_validation_identity_observer
                    ),
                    stage_sequence=protocol_stage_sequence,
                    request_key_prefix=(
                        protocol_request_prefix
                        + (
                            f"-q{protocol_stage_sequence}"
                            if cooperative_yield
                            else ""
                        )
                    ),
                )
            )
            charge(report, channel=PROTOCOL_CONFIRMATION_CHANNEL)
            stage_reports[PROTOCOL_CONFIRMATION_CHANNEL] = report
            promoted = [
                dict(item)
                for item in report.get("promoted_observation_eligible") or ()
                if isinstance(item, Mapping)
            ]
            if int(report.get("shared_source_failures") or 0) > 0:
                provider_failures += int(report.get("shared_source_failures") or 0)
                channels_unavailable.append(PROTOCOL_CONFIRMATION_CHANNEL)
        else:
            channels_skipped.append(
                {
                    "channel": PROTOCOL_CONFIRMATION_CHANNEL,
                    "reason": "SOURCE_BUDGET_EXHAUSTED",
                }
            )

        if source_operations > remaining:
            raise PreLifecycleRefreshCompositionError(
                "REFRESH_SOURCE_OPERATION_BUDGET_OVERRUN"
            )
        if cooperative_yield and source_operations > 0:
            connection.commit()
            return cooperative_result(PROTOCOL_CONFIRMATION_CHANNEL)

        return {
            "source_operations": source_operations,
            "provider_failures": provider_failures,
            "channels_unavailable": tuple(dict.fromkeys(channels_unavailable)),
            "channels_attempted": tuple(channels_attempted),
            "channels_skipped": tuple(channels_skipped),
            "newly_observed_exact_identities": _dedup_exact_identities(
                observed_identities
            ),
            "promoted_observation_eligible": tuple(promoted),
            "stage_reports": stage_reports,
            "budget_exhausted_before_refresh": False,
        }

    return refresh_stage


__all__ = [
    "PUMP_FRESH_CHANNEL",
    "DEXSCREENER_FRESH_CHANNEL",
    "GECKOTERMINAL_NOMINATION_CHANNEL",
    "UNKNOWN_LIQUIDITY_BACKUP_CHANNEL",
    "PROTOCOL_CONFIRMATION_CHANNEL",
    "PreLifecycleRefreshCompositionError",
    "build_cycle_discovery_batch_resolver",
    "build_pre_lifecycle_refresh_stage",
    "cycle_pump_live_tail_head_already_completed",
]

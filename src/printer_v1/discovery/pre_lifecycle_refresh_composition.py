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

import sqlite3
from pathlib import Path
from typing import Any, Callable, Mapping

from printer_v1.discovery.combined_executor import ensure_cycle_discovery_batch
from printer_v1.discovery.permanent_discovery_availability import (
    StageBudget,
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

        stage_budget = StageBudget.permanent_discovery_default()

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

        for channel in _rotated_fresh_channels(refresh_ordinal):
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
                stage_budget.consume("intake", 1)
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
                    )
                )
                report["source_requests"] = len(report.get("source_request_ids") or ())
                charge(report, channel=channel)
                stage_reports[channel] = report
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
                stage_budget.consume("intake", 1)
                channels_attempted.append(channel)
                from printer_v1.operator_cli.graduated_supply_front_door import (
                    run_fresh_profile_locator,
                )

                report = dict(
                    run_fresh_profile_locator(
                        refresh_db_path,
                        transport=locator_transport,
                        request_key=(
                            f"{request_key_prefix}-refresh-{refresh_ordinal}-dex-fresh"
                        ),
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
                stage_budget.consume("intake", 1)
                channels_attempted.append(channel)
                report = dict(
                    run_geckoterminal_fresh_nomination(
                        connection,
                        request_key=(
                            f"{request_key_prefix}-refresh-{refresh_ordinal}-gt-new-pools"
                        ),
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

        # Conversion/reconciliation owners run after all fresh source channels.
        # Candidate-local absence/failure in one source never suppresses peers.
        if budget_left() >= 1 and stage_budget.available("reconciliation") >= 1:
            channels_attempted.append(UNKNOWN_LIQUIDITY_BACKUP_CHANNEL)
            report = dict(
                run_bounded_unknown_liquidity_backup(
                    connection,
                    stage_budget=stage_budget,
                    now=now,
                    campaign_id=campaign_id,
                    run_id=run_id,
                    cycle_id=cycle_id,
                    request_key_prefix=(
                        f"{request_key_prefix}-refresh-{refresh_ordinal}-liq-backup"
                    ),
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

        if budget_left() >= 1 and stage_budget.available("protocol_confirmation") >= 1:
            channels_attempted.append(PROTOCOL_CONFIRMATION_CHANNEL)
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
                    stage_sequence=refresh_stage_sequence,
                    request_key_prefix=(
                        f"{request_key_prefix}-refresh-{refresh_ordinal}-protocol"
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
]

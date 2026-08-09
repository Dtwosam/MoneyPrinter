"""V2-9.8B Post-DTW98 production pre-lifecycle refresh composition.

Builds the two production callables the temporal refresh owner needs:

* ``build_pre_lifecycle_refresh_stage`` — one bounded Source-Governed refresh
  stage;
* ``build_cycle_discovery_batch_resolver`` — create-or-reuse of the exact
  cycle's one canonical discovery batch.

**This is composition, not a second discovery engine.** The refresh stage calls
exactly the two already-approved owners the ordinary permanent-availability
supply already runs at campaign start, in the same order, with the same
arguments and the same stage accounting:

1. ``run_geckoterminal_fresh_nomination`` — one governed free/public
   GeckoTerminal new-pool request (the stage that
   ``DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE`` names);
2. ``process_protocol_confirmation_queue`` — the existing governed
   PumpSwap account-batch confirmation/promotion owner.

No new provider, adapter, gate, selector, scorer, rank, weight or eligibility
rule is introduced here. Promotion decisions stay with
``process_protocol_confirmation_queue``; admission, revalidation, the front
door and the four-deep freeze stay with ``eligible_token_supply``. Nominations
whose liquidity is still unknown after the refresh simply do not promote — that
is fail-closed and honest, not a gap to paper over with a third owner.

Locked: no scoring/ranking/confidence/weights, no retrieval/decisions/positions/
trades/audits/PnL, no retry/restart/resume/successor, no paid API.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Callable, Mapping

from printer_v1.discovery.combined_executor import ensure_cycle_discovery_batch
from printer_v1.discovery.permanent_discovery_availability import (
    StageBudget,
    process_protocol_confirmation_queue,
    run_geckoterminal_fresh_nomination,
)

#: Channel labels reported as unavailable when a refresh sub-stage fails. These
#: reuse the existing channel vocabulary; no new channel is invented.
GECKOTERMINAL_NOMINATION_CHANNEL = "geckoterminal_fresh_pool_nomination"
PROTOCOL_CONFIRMATION_CHANNEL = "exact_pump_pumpswap_graduation_verify"


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
    """Resolver that create-or-reuses the exact cycle's one discovery batch.

    It derives the batch identity and canonical payload through the single
    shared helper the combined discovery executor also uses, so whichever lawful
    owner reaches the cycle first creates the batch and the other reuses it
    idempotently. That is what keeps the ``UNIQUE (cycle_id)`` constraint from
    turning a lawful temporal refresh into a campaign-killing collision.
    """
    contract_versions = dict(provider_contract_versions)

    def resolve(
        connection: sqlite3.Connection, now: str, refresh_ordinal: int
    ) -> str:
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


def build_pre_lifecycle_refresh_stage(
    *,
    request_key_prefix: str,
    geckoterminal_nomination_transport: Any | None = None,
    protocol_account_batch_transport: Any | None = None,
    protocol_account_batch_transport_factory: Any | None = None,
    stage_evidence_sink: Callable[[Mapping[str, Any]], None] | None = None,
    transport_identity_observer: Callable[[Any], None] | None = None,
    local_validation_identity_observer: Callable[[Any], None] | None = None,
) -> Callable[..., Mapping[str, Any]]:
    """One bounded Source-Governed refresh stage from existing owners only.

    The returned callable matches the temporal refresh owner's stage contract
    and reports exact cumulative source accounting. It never resets a budget,
    never exceeds ``source_operations_remaining``, and performs no provider work
    at all when no lawful operation remains.
    """

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
        remaining = int(source_operations_remaining)
        source_operations = 0
        provider_failures = 0
        channels_unavailable: list[str] = []
        promoted: list[dict[str, Any]] = []
        nomination_report: dict[str, Any] = {"status": "NOT_RUN"}
        protocol_report: dict[str, Any] = {"status": "NOT_RUN"}

        if remaining <= 0:
            return {
                "source_operations": 0,
                "provider_failures": 0,
                "channels_unavailable": (),
                "promoted_observation_eligible": (),
                "nomination_report": nomination_report,
                "protocol_report": protocol_report,
                "budget_exhausted_before_refresh": True,
            }

        # A refresh-local stage budget. It bounds this stage's own conversion
        # capacity; the campaign's cumulative 30-operation discovery budget is
        # enforced separately by the supply service and never reset here.
        stage_budget = StageBudget.permanent_discovery_default()

        # 1. Bounded governed fresh nomination — one request.
        stage_budget.consume("intake", 1)
        nomination_report = dict(
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
            )
        )
        source_operations += int(nomination_report.get("source_requests") or 0)
        if nomination_report.get("failure_type") or nomination_report.get(
            "accounting_blocker"
        ):
            provider_failures += 1
            channels_unavailable.append(GECKOTERMINAL_NOMINATION_CHANNEL)

        # 2. Bounded governed protocol confirmation of any above-floor row the
        #    nomination exposed. Skipped entirely when no lawful operation
        #    remains, so the cumulative budget can never be overrun.
        if (
            source_operations < remaining
            and stage_budget.available("protocol_confirmation") >= 1
            and not provider_failures
        ):
            protocol_report = dict(
                process_protocol_confirmation_queue(
                    connection,
                    stage_budget=stage_budget,
                    now=now,
                    campaign_id=campaign_id,
                    run_id=run_id,
                    cycle_id=cycle_id,
                    account_batch_transport=protocol_account_batch_transport,
                    account_batch_transport_factory=(
                        protocol_account_batch_transport_factory
                    ),
                    stage_evidence_sink=stage_evidence_sink,
                    transport_identity_observer=transport_identity_observer,
                    local_validation_identity_observer=(
                        local_validation_identity_observer
                    ),
                    stage_sequence=1,
                    request_key_prefix=(
                        f"{request_key_prefix}-refresh-{refresh_ordinal}-protocol"
                    ),
                )
            )
            source_operations += int(protocol_report.get("source_requests") or 0)
            promoted = [
                dict(item)
                for item in (
                    protocol_report.get("promoted_observation_eligible") or ()
                )
            ]
            if protocol_report.get("shared_source_failure"):
                provider_failures += 1
                channels_unavailable.append(PROTOCOL_CONFIRMATION_CHANNEL)

        return {
            "source_operations": min(source_operations, remaining),
            "provider_failures": provider_failures,
            "channels_unavailable": tuple(channels_unavailable),
            "promoted_observation_eligible": tuple(promoted),
            "nomination_report": nomination_report,
            "protocol_report": protocol_report,
            "budget_exhausted_before_refresh": False,
        }

    return refresh_stage


__all__ = [
    "GECKOTERMINAL_NOMINATION_CHANNEL",
    "PROTOCOL_CONFIRMATION_CHANNEL",
    "PreLifecycleRefreshCompositionError",
    "build_cycle_discovery_batch_resolver",
    "build_pre_lifecycle_refresh_stage",
]

"""Categorical completeness accounting for optional wallet/flow evidence.

Collection attempts are required product behavior; the evidence itself remains
optional for E2Q/E2Z under the current V1 contract.  This module never invents
missing values and contains no score, rank, confidence or paid-provider path.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

NOT_NEEDED_ALREADY_RESOLVED = "NOT_NEEDED_ALREADY_RESOLVED"
ATTEMPTED_RESOLVED = "ATTEMPTED_RESOLVED"
ATTEMPTED_PARTIAL = "ATTEMPTED_PARTIAL"
ATTEMPTED_SOURCE_UNAVAILABLE = "ATTEMPTED_SOURCE_UNAVAILABLE"
ATTEMPTED_BUDGET_EXHAUSTED = "ATTEMPTED_BUDGET_EXHAUSTED"
NOT_SUPPORTED_BY_APPROVED_FREE_SOURCE = "NOT_SUPPORTED_BY_APPROVED_FREE_SOURCE"

OPTIONAL_FLOW_FIELDS = (
    "unique_wallets_5m",
    "buy_volume_5m",
    "sell_volume_5m",
)


@dataclass(frozen=True)
class EvidenceCompletenessDecision:
    status: str
    missing_fields: tuple[str, ...]
    resolved_fields: tuple[str, ...]
    external_attempt_required: bool
    clean_memory_blocker: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "missing_fields": list(self.missing_fields),
            "resolved_fields": list(self.resolved_fields),
            "external_attempt_required": self.external_attempt_required,
            "clean_memory_blocker": self.clean_memory_blocker,
        }


def plan_optional_wallet_flow_enrichment(
    payload: Mapping[str, Any],
    *,
    approved_free_enricher_available: bool,
    source_budget_available: bool,
) -> EvidenceCompletenessDecision:
    """Plan the mandatory enrichment attempt without fabricating evidence."""
    missing = tuple(field for field in OPTIONAL_FLOW_FIELDS if payload.get(field) is None)
    resolved = tuple(field for field in OPTIONAL_FLOW_FIELDS if payload.get(field) is not None)
    if not missing:
        return EvidenceCompletenessDecision(
            NOT_NEEDED_ALREADY_RESOLVED, (), resolved, False
        )
    if not approved_free_enricher_available:
        return EvidenceCompletenessDecision(
            NOT_SUPPORTED_BY_APPROVED_FREE_SOURCE, missing, resolved, False
        )
    if not source_budget_available:
        return EvidenceCompletenessDecision(
            ATTEMPTED_BUDGET_EXHAUSTED, missing, resolved, False
        )
    return EvidenceCompletenessDecision(
        ATTEMPTED_PARTIAL, missing, resolved, True
    )


def settle_optional_wallet_flow_enrichment(
    before: Mapping[str, Any],
    after: Mapping[str, Any] | None,
    *,
    source_available: bool = True,
) -> EvidenceCompletenessDecision:
    """Categorically settle one attempted approved-free enrichment."""
    if not source_available:
        initial = plan_optional_wallet_flow_enrichment(
            before,
            approved_free_enricher_available=True,
            source_budget_available=True,
        )
        return EvidenceCompletenessDecision(
            ATTEMPTED_SOURCE_UNAVAILABLE,
            initial.missing_fields,
            initial.resolved_fields,
            False,
        )
    merged = dict(before)
    if after:
        for field in OPTIONAL_FLOW_FIELDS:
            value = after.get(field)
            if value is not None:
                merged[field] = value
    final = plan_optional_wallet_flow_enrichment(
        merged,
        approved_free_enricher_available=True,
        source_budget_available=True,
    )
    return EvidenceCompletenessDecision(
        ATTEMPTED_RESOLVED if not final.missing_fields else ATTEMPTED_PARTIAL,
        final.missing_fields,
        final.resolved_fields,
        False,
    )

"""Pure exact-two-token discovery-attempt manifest for V2-9.8B proofs.

The records in this module project existing execution-owner request facts.  No
function here accepts a database, source, Scheduler, callback, or runtime port.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    HOLDER_ELIGIBILITY_CANDIDATE_MAX,
)
from printer_v1.operator_cli.holder_reliability_budget_control import (
    HOLDER_WORST_CASE_GOVERNED_REQUESTS,
    HOLDER_WORST_CASE_TRANSPORT_OPERATIONS,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    holder_safety_request_plan,
)
from printer_v1.sources import pumpfun_origin, secondary_discovery
from printer_v1.sources.registry import SOURCE_REGISTRY


SOURCE_FREE_DISCOVERY_ATTEMPT_CONTRACT_VERSION = (
    "V2_9_8B_SOURCE_FREE_DISCOVERY_ATTEMPT_MANIFEST_V1"
)
EXACT_TARGET_COUNT = 2


class SourceFreeDiscoveryCapacityError(RuntimeError):
    """Fail-closed source-free manifest contract violation."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = str(code)
        self.detail = str(detail)
        super().__init__(self.code if not detail else f"{self.code}:{self.detail}")


@dataclass(frozen=True)
class DiscoveryAttemptRequirement:
    stage: str
    source_name: str
    request_kind: str
    governed_request_ceiling: int
    underlying_transport_ceiling: int
    condition: str
    condition_evidence: str
    rate_limit_owner: str
    execution_owner: str


@dataclass(frozen=True)
class LaterCycleDiscoveryAttemptManifest:
    contract_version: str
    target_count: int
    candidate_evaluation_ceiling: int
    requirements: tuple[DiscoveryAttemptRequirement, ...]
    provider_governed_request_totals: Mapping[str, int]
    provider_transport_operation_totals: Mapping[str, int]
    optional_paths: tuple[str, ...]
    source_free: bool = True


def _provider_totals(
    requirements: tuple[DiscoveryAttemptRequirement, ...],
    field: str,
) -> Mapping[str, int]:
    totals: dict[str, int] = {}
    for requirement in requirements:
        totals[requirement.source_name] = totals.get(requirement.source_name, 0) + int(
            getattr(requirement, field)
        )
    return MappingProxyType(dict(sorted(totals.items())))


def _pump_requirements() -> tuple[DiscoveryAttemptRequirement, ...]:
    return tuple(
        DiscoveryAttemptRequirement(
            stage="PUMP_ORIGIN",
            source_name=pumpfun_origin.SOURCE_NAME,
            request_kind=request_kind,
            governed_request_ceiling=request_ceiling,
            underlying_transport_ceiling=request_ceiling,
            condition="ALWAYS",
            condition_evidence="PUMPFUN_ORIGIN_ACQUISITION_ENABLED",
            rate_limit_owner=f"SOURCE_REGISTRY[{pumpfun_origin.SOURCE_NAME}]",
            execution_owner="pumpfun_origin.run_acquisition_from_source",
        )
        for request_kind, request_ceiling in pumpfun_origin.REQUEST_CEILINGS.items()
    )


def _secondary_requirements(
    *, tracker_auth: secondary_discovery.SolanaTrackerAuthConfig | None
) -> tuple[DiscoveryAttemptRequirement, ...]:
    active_request_plan = [
        (
            secondary_discovery.GECKO_TRENDING_REQUEST,
            "ALWAYS",
            "LIVE_SECONDARY_PATH_ENABLED",
        ),
        (
            secondary_discovery.GECKO_ACTIVE_REQUEST,
            "ACQUIRED_ACTIVE_POOL_AVAILABLE",
            "LIVE_ADAPTER_ACTIVE_POOLS_NONEMPTY",
        ),
        (
            secondary_discovery.DEXSCREENER_FRESH_REQUEST,
            "ALWAYS",
            "LIVE_SECONDARY_PATH_ENABLED",
        ),
    ]
    if tracker_auth is not None:
        tracker_auth.validate()
        active_request_plan.append(
            (
                secondary_discovery.TRACKER_TRENDING_REQUEST,
                "TRACKER_FREE_CONFIGURATION_ENABLED",
                "VALIDATED_SOLANA_TRACKER_FREE_AUTH_CONFIGURATION",
            )
        )
    return tuple(
        DiscoveryAttemptRequirement(
            stage="SECONDARY_DISCOVERY",
            source_name=secondary_discovery.REQUEST_TO_SOURCE[request_kind],
            request_kind=request_kind,
            governed_request_ceiling=secondary_discovery.REQUEST_CEILINGS[
                request_kind
            ],
            underlying_transport_ceiling=secondary_discovery.REQUEST_CEILINGS[
                request_kind
            ],
            condition=condition,
            condition_evidence=condition_evidence,
            rate_limit_owner=(
                f"SOURCE_REGISTRY["
                f"{secondary_discovery.REQUEST_TO_SOURCE[request_kind]}]"
            ),
            execution_owner="LiveSecondaryDiscoveryAdapter.enrich",
        )
        for request_kind, condition, condition_evidence in active_request_plan
    )


def _holder_requirements() -> tuple[DiscoveryAttemptRequirement, ...]:
    return tuple(
        DiscoveryAttemptRequirement(
            stage="HOLDER_SAFETY",
            source_name=row.source_name,
            request_kind=row.request_kind,
            governed_request_ceiling=row.governed_request_ceiling,
            underlying_transport_ceiling=row.underlying_transport_ceiling,
            condition=row.condition,
            condition_evidence=row.condition_evidence,
            rate_limit_owner=row.rate_limit_owner,
            execution_owner=row.execution_owner,
        )
        for row in holder_safety_request_plan()
    )


def _require_registered_free_source(
    requirement: DiscoveryAttemptRequirement,
) -> None:
    definition = SOURCE_REGISTRY.get(requirement.source_name)
    if definition is None:
        raise SourceFreeDiscoveryCapacityError(
            "SOURCE_NOT_REGISTERED", requirement.source_name
        )
    restriction = str(definition.restriction or "").lower()
    dependency_type = str(definition.dependency_type).lower()
    if (
        definition.requires_paid_plan
        or "prohibited" in restriction
        or "unavailable" in dependency_type
    ):
        raise SourceFreeDiscoveryCapacityError(
            "PROHIBITED_SOURCE_REQUIREMENT", requirement.source_name
        )
    if not (
        definition.supports_solana is True
        or definition.supports_solana == "where_available"
    ):
        raise SourceFreeDiscoveryCapacityError(
            "NON_SOLANA_SOURCE_REQUIREMENT", requirement.source_name
        )
    if requirement.request_kind not in definition.allowed_request_kinds:
        raise SourceFreeDiscoveryCapacityError(
            "REQUEST_KIND_NOT_REGISTERED",
            f"{requirement.source_name}:{requirement.request_kind}",
        )


def validate_source_free_discovery_attempt_manifest(
    manifest: LaterCycleDiscoveryAttemptManifest,
) -> LaterCycleDiscoveryAttemptManifest:
    """Validate owner parity without executing any operational capability."""
    if manifest.target_count != EXACT_TARGET_COUNT:
        raise SourceFreeDiscoveryCapacityError("EXACT_TWO_TOKEN_TARGET_REQUIRED")
    if manifest.contract_version != SOURCE_FREE_DISCOVERY_ATTEMPT_CONTRACT_VERSION:
        raise SourceFreeDiscoveryCapacityError("MANIFEST_CONTRACT_VERSION_MISMATCH")
    if manifest.source_free is not True:
        raise SourceFreeDiscoveryCapacityError("SOURCE_FREE_CONTRACT_REQUIRED")
    if manifest.candidate_evaluation_ceiling != HOLDER_ELIGIBILITY_CANDIDATE_MAX:
        raise SourceFreeDiscoveryCapacityError("CANDIDATE_EVALUATION_CEILING_DRIFT")

    identities: set[tuple[str, str, str]] = set()
    for requirement in manifest.requirements:
        identity = (
            requirement.stage,
            requirement.source_name,
            requirement.request_kind,
        )
        if identity in identities:
            raise SourceFreeDiscoveryCapacityError(
                "DUPLICATE_ATTEMPT_REQUIREMENT", ":".join(identity)
            )
        identities.add(identity)
        if (
            type(requirement.governed_request_ceiling) is not int
            or requirement.governed_request_ceiling <= 0
            or type(requirement.underlying_transport_ceiling) is not int
            or requirement.underlying_transport_ceiling <= 0
        ):
            raise SourceFreeDiscoveryCapacityError(
                "INVALID_REQUEST_CEILING", ":".join(identity)
            )
        _require_registered_free_source(requirement)

    pump_rows = tuple(
        row for row in manifest.requirements if row.stage == "PUMP_ORIGIN"
    )
    if {
        row.request_kind: row.governed_request_ceiling for row in pump_rows
    } != dict(pumpfun_origin.REQUEST_CEILINGS):
        raise SourceFreeDiscoveryCapacityError("PUMP_REQUEST_PLAN_DRIFT")

    holder_rows = tuple(
        row for row in manifest.requirements if row.stage == "HOLDER_SAFETY"
    )
    if sum(row.governed_request_ceiling for row in holder_rows) != (
        HOLDER_WORST_CASE_GOVERNED_REQUESTS
    ):
        raise SourceFreeDiscoveryCapacityError("HOLDER_GOVERNED_REQUEST_PLAN_DRIFT")
    if sum(row.underlying_transport_ceiling for row in holder_rows) != (
        HOLDER_WORST_CASE_TRANSPORT_OPERATIONS
    ):
        raise SourceFreeDiscoveryCapacityError("HOLDER_TRANSPORT_REQUEST_PLAN_DRIFT")

    governed_totals = _provider_totals(
        manifest.requirements, "governed_request_ceiling"
    )
    transport_totals = _provider_totals(
        manifest.requirements, "underlying_transport_ceiling"
    )
    if dict(manifest.provider_governed_request_totals) != dict(governed_totals):
        raise SourceFreeDiscoveryCapacityError("PROVIDER_GOVERNED_TOTALS_DRIFT")
    if dict(manifest.provider_transport_operation_totals) != dict(transport_totals):
        raise SourceFreeDiscoveryCapacityError("PROVIDER_TRANSPORT_TOTALS_DRIFT")
    return manifest


def build_source_free_discovery_attempt_manifest(
    *,
    target_count: int = EXACT_TARGET_COUNT,
    tracker_auth: secondary_discovery.SolanaTrackerAuthConfig | None = None,
) -> LaterCycleDiscoveryAttemptManifest:
    """Build one deterministic, source-free later-cycle attempt manifest."""
    if target_count != EXACT_TARGET_COUNT:
        raise SourceFreeDiscoveryCapacityError("EXACT_TWO_TOKEN_TARGET_REQUIRED")
    requirements = (
        *_pump_requirements(),
        *_secondary_requirements(tracker_auth=tracker_auth),
        *_holder_requirements(),
    )
    optional_paths = tuple(
        row.condition for row in requirements if row.condition != "ALWAYS"
    )
    manifest = LaterCycleDiscoveryAttemptManifest(
        contract_version=SOURCE_FREE_DISCOVERY_ATTEMPT_CONTRACT_VERSION,
        target_count=target_count,
        candidate_evaluation_ceiling=HOLDER_ELIGIBILITY_CANDIDATE_MAX,
        requirements=requirements,
        provider_governed_request_totals=_provider_totals(
            requirements, "governed_request_ceiling"
        ),
        provider_transport_operation_totals=_provider_totals(
            requirements, "underlying_transport_ceiling"
        ),
        optional_paths=optional_paths,
    )
    return validate_source_free_discovery_attempt_manifest(manifest)


__all__ = [
    "DiscoveryAttemptRequirement",
    "LaterCycleDiscoveryAttemptManifest",
    "SOURCE_FREE_DISCOVERY_ATTEMPT_CONTRACT_VERSION",
    "SourceFreeDiscoveryCapacityError",
    "build_source_free_discovery_attempt_manifest",
    "validate_source_free_discovery_attempt_manifest",
]

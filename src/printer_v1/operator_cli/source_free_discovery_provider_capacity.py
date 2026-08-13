"""Read-only provider capacity composition for one source-free discovery package.

This module composes the pure exact-two-token manifest with the existing
provider-reaching attempt projection and registry rate ceilings.  It does not
execute discovery, reserve capacity, mutate SQLite, or authorize later work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from printer_v1.operator_cli.source_free_discovery_capacity import (
    LaterCycleDiscoveryAttemptManifest,
    SourceFreeDiscoveryCapacityError,
    validate_source_free_discovery_attempt_manifest,
)
from printer_v1.sources.budget_accounting import (
    DEFAULT_WINDOW_SECONDS,
    ConsumedProviderAttempt,
    SourceBudgetAccountingEvidenceError,
    recent_consumed_provider_attempts,
)
from printer_v1.sources.registry import SOURCE_REGISTRY


@dataclass(frozen=True)
class ProviderCapacitySnapshot:
    source_name: str
    window_seconds: int
    rate_ceiling: int
    consumed_attempts: tuple[ConsumedProviderAttempt, ...]
    consumed_attempt_count: int | None
    package_required_attempts: int
    package_fits_now: bool
    package_ready_at: datetime | None
    evidence_complete: bool
    reason: str


@dataclass(frozen=True)
class LaterCycleDiscoveryCapacity:
    manifest: LaterCycleDiscoveryAttemptManifest
    manifest_valid: bool
    provider_snapshots: tuple[ProviderCapacitySnapshot, ...]
    provider_budgets_available: bool
    discovery_capacity_available: bool
    recheck_at: datetime | None
    reasons: tuple[str, ...]


def _provider_capacity_snapshot(
    db: str | Path | sqlite3.Connection,
    *,
    source_name: str,
    package_required_attempts: int,
    now: datetime,
) -> ProviderCapacitySnapshot:
    rate_ceiling = SOURCE_REGISTRY[
        source_name
    ].default_rate_limit_per_minute
    try:
        attempts = recent_consumed_provider_attempts(
            db,
            source_name,
            window_seconds=DEFAULT_WINDOW_SECONDS,
            now=now,
        )
    except SourceBudgetAccountingEvidenceError as exc:
        return ProviderCapacitySnapshot(
            source_name=source_name,
            window_seconds=DEFAULT_WINDOW_SECONDS,
            rate_ceiling=rate_ceiling,
            consumed_attempts=(),
            consumed_attempt_count=None,
            package_required_attempts=package_required_attempts,
            package_fits_now=False,
            package_ready_at=None,
            evidence_complete=False,
            reason=f"PROVIDER_ATTEMPT_EVIDENCE_INCOMPLETE:{exc}",
        )

    ordered_attempts = tuple(
        sorted(
            attempts,
            key=lambda item: (item.requested_at, item.source_request_id),
        )
    )
    consumed_attempt_count = len(ordered_attempts)
    if package_required_attempts > rate_ceiling:
        return ProviderCapacitySnapshot(
            source_name=source_name,
            window_seconds=DEFAULT_WINDOW_SECONDS,
            rate_ceiling=rate_ceiling,
            consumed_attempts=ordered_attempts,
            consumed_attempt_count=consumed_attempt_count,
            package_required_attempts=package_required_attempts,
            package_fits_now=False,
            package_ready_at=None,
            evidence_complete=True,
            reason="PACKAGE_REQUIREMENT_EXCEEDS_PROVIDER_RATE_CEILING",
        )

    if consumed_attempt_count + package_required_attempts <= rate_ceiling:
        return ProviderCapacitySnapshot(
            source_name=source_name,
            window_seconds=DEFAULT_WINDOW_SECONDS,
            rate_ceiling=rate_ceiling,
            consumed_attempts=ordered_attempts,
            consumed_attempt_count=consumed_attempt_count,
            package_required_attempts=package_required_attempts,
            package_fits_now=True,
            package_ready_at=None,
            evidence_complete=True,
            reason="PACKAGE_FITS_CURRENT_PROVIDER_WINDOW",
        )

    needed_expirations = (
        consumed_attempt_count + package_required_attempts - rate_ceiling
    )
    expiry_attempt = ordered_attempts[needed_expirations - 1]
    package_ready_at = (
        expiry_attempt.requested_at
        + timedelta(seconds=DEFAULT_WINDOW_SECONDS)
        + datetime.resolution
    )
    return ProviderCapacitySnapshot(
        source_name=source_name,
        window_seconds=DEFAULT_WINDOW_SECONDS,
        rate_ceiling=rate_ceiling,
        consumed_attempts=ordered_attempts,
        consumed_attempt_count=consumed_attempt_count,
        package_required_attempts=package_required_attempts,
        package_fits_now=False,
        package_ready_at=package_ready_at,
        evidence_complete=True,
        reason="PACKAGE_BLOCKED_BY_CURRENT_PROVIDER_CONSUMPTION",
    )


def compose_later_cycle_discovery_capacity(
    db: str | Path | sqlite3.Connection,
    *,
    manifest: LaterCycleDiscoveryAttemptManifest,
    now: datetime | None = None,
) -> LaterCycleDiscoveryCapacity:
    """Compose immutable readiness evidence without reserving or executing work."""
    try:
        validate_source_free_discovery_attempt_manifest(manifest)
    except SourceFreeDiscoveryCapacityError as exc:
        return LaterCycleDiscoveryCapacity(
            manifest=manifest,
            manifest_valid=False,
            provider_snapshots=(),
            provider_budgets_available=False,
            discovery_capacity_available=False,
            recheck_at=None,
            reasons=(f"DISCOVERY_ATTEMPT_MANIFEST_INVALID:{exc}",),
        )

    current_time = now or datetime.now(timezone.utc)
    snapshots = tuple(
        _provider_capacity_snapshot(
            db,
            source_name=source_name,
            package_required_attempts=package_required_attempts,
            now=current_time,
        )
        for source_name, package_required_attempts in sorted(
            manifest.provider_governed_request_totals.items()
        )
    )
    provider_budgets_available = all(
        snapshot.evidence_complete and snapshot.package_fits_now
        for snapshot in snapshots
    )
    blocked_snapshots = tuple(
        snapshot for snapshot in snapshots if not snapshot.package_fits_now
    )
    recheck_at = None
    if blocked_snapshots and all(
        snapshot.package_ready_at is not None for snapshot in blocked_snapshots
    ):
        recheck_at = max(
            snapshot.package_ready_at
            for snapshot in blocked_snapshots
            if snapshot.package_ready_at is not None
        )

    return LaterCycleDiscoveryCapacity(
        manifest=manifest,
        manifest_valid=True,
        provider_snapshots=snapshots,
        provider_budgets_available=provider_budgets_available,
        discovery_capacity_available=True,
        recheck_at=recheck_at,
        reasons=tuple(
            f"{snapshot.source_name}:{snapshot.reason}" for snapshot in snapshots
        ),
    )


__all__ = [
    "LaterCycleDiscoveryCapacity",
    "ProviderCapacitySnapshot",
    "compose_later_cycle_discovery_capacity",
]

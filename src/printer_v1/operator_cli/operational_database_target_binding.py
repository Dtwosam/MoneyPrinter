"""Immutable operational database authorization passed through the live stack."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


PRODUCTION_AUTHORITATIVE = "PRODUCTION_AUTHORITATIVE"
AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF = (
    "AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF"
)
ALLOWED_OPERATIONAL_DATABASE_TARGET_KINDS = frozenset(
    {PRODUCTION_AUTHORITATIVE, AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF}
)


@dataclass(frozen=True)
class OperationalDatabaseTargetBinding:
    binding_version: str
    target_kind: str
    resolved_db_path: str
    authorized_pre_mutation_sha256: str
    migration_count: int
    migration_head: str
    db_target_identity: str
    authorization_id: str
    authorization_marker_sha256: str
    application_marker_sha256: str
    execution_id: str
    campaign_id: str
    campaign_run_id: str
    cycle_id: str
    configuration_id: str


def build_operational_database_target_binding(
    *,
    target_kind: str,
    resolved_db_path: str | Path,
    authorized_pre_mutation_sha256: str,
    migration_count: int,
    migration_head: str,
    authorization_id: str,
    authorization_marker_sha256: str,
    application_marker_sha256: str,
    execution_id: str,
    campaign_id: str,
    campaign_run_id: str,
    cycle_id: str,
    configuration_id: str,
) -> OperationalDatabaseTargetBinding:
    """Coordinator-only constructor for the immutable downstream capability."""
    return OperationalDatabaseTargetBinding(
        binding_version="OPERATIONAL_DATABASE_TARGET_BINDING_V1",
        target_kind=target_kind,
        resolved_db_path=str(Path(resolved_db_path).resolve()),
        authorized_pre_mutation_sha256=str(authorized_pre_mutation_sha256),
        migration_count=int(migration_count),
        migration_head=str(migration_head),
        db_target_identity=f"sha256:{authorized_pre_mutation_sha256}",
        authorization_id=str(authorization_id),
        authorization_marker_sha256=str(authorization_marker_sha256),
        application_marker_sha256=str(application_marker_sha256),
        execution_id=str(execution_id),
        campaign_id=str(campaign_id),
        campaign_run_id=str(campaign_run_id),
        cycle_id=str(cycle_id),
        configuration_id=str(configuration_id),
    )


def validate_operational_database_target_binding(
    binding: OperationalDatabaseTargetBinding | None,
    *,
    actual_db_path: str | Path,
    canonical_authoritative_db_path: str | Path,
    expected: Mapping[str, Any],
) -> str | None:
    """Return the first categorical mismatch without reading mutable DB bytes."""
    if binding is None:
        return "OPERATIONAL_DB_BINDING_MISSING"
    if binding.target_kind not in ALLOWED_OPERATIONAL_DATABASE_TARGET_KINDS:
        return "OPERATIONAL_DB_BINDING_KIND_INVALID"
    actual = Path(actual_db_path).resolve()
    bound = Path(binding.resolved_db_path).resolve()
    canonical = Path(canonical_authoritative_db_path).resolve()
    if actual != bound:
        return "OPERATIONAL_DB_BINDING_PATH_MISMATCH"
    if binding.target_kind == PRODUCTION_AUTHORITATIVE and bound != canonical:
        return "OPERATIONAL_DB_BINDING_PRODUCTION_PATH_MISMATCH"
    if (
        binding.target_kind == AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF
        and bound == canonical
    ):
        return "OPERATIONAL_DB_BINDING_PRODUCTION_PATH_MISMATCH"

    expected_baseline = str(
        expected.get("authorized_pre_mutation_sha256") or ""
    )
    if expected_baseline and binding.authorized_pre_mutation_sha256 != expected_baseline:
        return "OPERATIONAL_DB_BINDING_BASELINE_SHA_MISMATCH"
    if binding.db_target_identity != f"sha256:{binding.authorized_pre_mutation_sha256}":
        return "OPERATIONAL_DB_BINDING_BASELINE_SHA_MISMATCH"

    if (
        expected.get("migration_count") is not None
        and int(binding.migration_count) != int(expected["migration_count"])
    ) or (
        expected.get("migration_head") is not None
        and binding.migration_head != str(expected["migration_head"])
    ):
        return "OPERATIONAL_DB_BINDING_MIGRATION_MISMATCH"

    if (
        expected.get("authorization_id") is not None
        and binding.authorization_id != str(expected["authorization_id"])
    ) or (
        expected.get("authorization_marker_sha256") is not None
        and binding.authorization_marker_sha256
        != str(expected["authorization_marker_sha256"])
    ):
        return "OPERATIONAL_DB_BINDING_AUTHORIZATION_MISMATCH"
    if (
        expected.get("application_marker_sha256") is not None
        and binding.application_marker_sha256
        != str(expected["application_marker_sha256"])
    ):
        return "OPERATIONAL_DB_BINDING_APPLICATION_MARKER_MISMATCH"

    ownership_fields = (
        "execution_id",
        "campaign_id",
        "campaign_run_id",
        "cycle_id",
        "configuration_id",
    )
    if any(
        expected.get(field) is not None
        and getattr(binding, field) != str(expected[field])
        for field in ownership_fields
    ):
        return "OPERATIONAL_DB_BINDING_OWNERSHIP_MISMATCH"
    if (
        expected.get("durable_db_target_identity") is not None
        and binding.db_target_identity
        != str(expected["durable_db_target_identity"])
    ):
        return "OPERATIONAL_DB_BINDING_OWNERSHIP_MISMATCH"

    if binding.target_kind == AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF:
        fixture = expected.get("fixture_authorization")
        if not isinstance(fixture, Mapping):
            return "OPERATIONAL_DB_BINDING_AUTHORIZATION_MISMATCH"
        fixture_path = fixture.get("resolved_db_path")
        if fixture_path is None or Path(str(fixture_path)).resolve() != bound:
            return "OPERATIONAL_DB_BINDING_AUTHORIZATION_MISMATCH"
        fixture_authorization_fields = (
            "authorized_pre_mutation_sha256",
            "authorization_id",
            "authorization_marker_sha256",
            "execution_id",
            "campaign_id",
            "campaign_run_id",
            "cycle_id",
            "configuration_id",
        )
        if any(
            fixture.get(field) is None
            or str(fixture[field]) != str(getattr(binding, field))
            for field in fixture_authorization_fields
        ):
            return "OPERATIONAL_DB_BINDING_AUTHORIZATION_MISMATCH"
        if (
            fixture.get("application_marker_sha256") is None
            or str(fixture["application_marker_sha256"])
            != binding.application_marker_sha256
        ):
            return "OPERATIONAL_DB_BINDING_APPLICATION_MARKER_MISMATCH"
        if (
            int(fixture.get("migration_count", -1)) != binding.migration_count
            or str(fixture.get("migration_head") or "") != binding.migration_head
        ):
            return "OPERATIONAL_DB_BINDING_MIGRATION_MISMATCH"
    elif expected.get("disposable_proof_identity") not in (None, ""):
        return "OPERATIONAL_DB_BINDING_AUTHORIZATION_MISMATCH"

    retry_flags = (
        "automatic_retry_allowed",
        "manual_rerun_allowed",
        "resume_allowed",
        "restart_allowed",
        "successor_allowed",
    )
    reuse_source = (
        expected.get("fixture_authorization")
        if binding.target_kind == AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF
        else expected
    )
    if (
        expected.get("authorization_consumed_once") is not True
        or int(expected.get("invocation_count", 0)) != 1
        or not isinstance(reuse_source, Mapping)
        or any(reuse_source.get(flag) is not False for flag in retry_flags)
        or (
            binding.target_kind == AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF
            and int(reuse_source.get("allowed_invocation_count", 0)) != 1
        )
    ):
        return "OPERATIONAL_DB_BINDING_REUSE_OR_HISTORY_MISMATCH"
    return None


def validate_bound_operational_invocation(
    binding: OperationalDatabaseTargetBinding | None,
    *,
    actual_db_path: str | Path,
    canonical_authoritative_db_path: str | Path,
    migration_count: int,
    migration_head: str,
    execution_id: str,
    campaign_id: str,
    campaign_run_id: str,
    cycle_id: str,
    configuration_id: str,
    durable_db_target_identity: str,
) -> str | None:
    """Validate the capability against independent invocation ownership."""
    expected: dict[str, Any] = {
        "authorized_pre_mutation_sha256": (
            None if binding is None else binding.authorized_pre_mutation_sha256
        ),
        "migration_count": migration_count,
        "migration_head": migration_head,
        "durable_db_target_identity": durable_db_target_identity,
        "execution_id": execution_id,
        "campaign_id": campaign_id,
        "campaign_run_id": campaign_run_id,
        "cycle_id": cycle_id,
        "configuration_id": configuration_id,
        "authorization_consumed_once": True,
        "invocation_count": 1,
        "automatic_retry_allowed": False,
        "manual_rerun_allowed": False,
        "resume_allowed": False,
        "restart_allowed": False,
        "successor_allowed": False,
    }
    if binding is not None:
        expected.update({
            "authorization_id": binding.authorization_id,
            "authorization_marker_sha256": binding.authorization_marker_sha256,
            "application_marker_sha256": binding.application_marker_sha256,
        })
        if binding.target_kind == AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF:
            expected["fixture_authorization"] = {
                "resolved_db_path": binding.resolved_db_path,
                "authorized_pre_mutation_sha256": binding.authorized_pre_mutation_sha256,
                "authorization_id": binding.authorization_id,
                "authorization_marker_sha256": binding.authorization_marker_sha256,
                "application_marker_sha256": binding.application_marker_sha256,
                "execution_id": execution_id,
                "campaign_id": campaign_id,
                "campaign_run_id": campaign_run_id,
                "cycle_id": cycle_id,
                "configuration_id": configuration_id,
                "migration_count": migration_count,
                "migration_head": migration_head,
                "allowed_invocation_count": 1,
                "automatic_retry_allowed": False,
                "manual_rerun_allowed": False,
                "resume_allowed": False,
                "restart_allowed": False,
                "successor_allowed": False,
            }
    return validate_operational_database_target_binding(
        binding,
        actual_db_path=actual_db_path,
        canonical_authoritative_db_path=canonical_authoritative_db_path,
        expected=expected,
    )


__all__ = [
    "ALLOWED_OPERATIONAL_DATABASE_TARGET_KINDS",
    "AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF",
    "OperationalDatabaseTargetBinding",
    "PRODUCTION_AUTHORITATIVE",
    "build_operational_database_target_binding",
    "validate_operational_database_target_binding",
    "validate_bound_operational_invocation",
]

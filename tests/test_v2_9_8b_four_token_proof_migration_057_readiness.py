"""Focused migration-057 re-readiness contract for the four-token terminal proof.

Offline only. This file creates no authorization, consumes no authorization,
starts no Printer runtime, performs no source request, and mutates no
authoritative database.
"""

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli import four_token_proof_zero_state_gate as zero_state


def test_four_token_current_migration_evidence_is_exactly_057() -> None:
    profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
    assert profile.migration_package_root == git_auth.MIGRATION_057_PACKAGE_ROOT
    assert profile.migration_package_kind == git_auth.MIGRATION_057_PACKAGE_KIND
    assert profile.migration_package_root == (
        "operator-runs/v2-9-8b-migration-057-application"
    )
    assert profile.migration_package_kind == "MIGRATION_057_EVIDENCE"


def test_four_token_zero_state_is_explicitly_pinned_to_057() -> None:
    assert zero_state.REQUIRED_MIGRATION_COUNT == 57
    assert zero_state.REQUIRED_MIGRATION_HEAD == (
        "057_pre_lifecycle_discovery_refresh_work.sql"
    )
    assert "active_pre_lifecycle_discovery_refresh_work" in (
        zero_state.REQUIRED_ZERO_STATE_DOMAINS
    )


def test_migration_050_remains_the_only_required_historical_migration() -> None:
    profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
    assert len(profile.historical_migration_packages) == 1
    package = profile.historical_migration_packages[0]
    assert package.package_root == git_auth.MIGRATION_PACKAGE_ROOT
    assert package.execution_id == git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_EXECUTION_ID
    assert package.evidence_class == git_auth.HISTORICAL_MIGRATION_EVIDENCE_CLASS
    assert package.package_root not in {
        git_auth.MIGRATION_055_PACKAGE_ROOT,
        git_auth.MIGRATION_056_PACKAGE_ROOT,
        git_auth.MIGRATION_057_PACKAGE_ROOT,
    }

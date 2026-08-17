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


def test_four_token_zero_state_is_explicitly_pinned_to_the_current_head() -> None:
    """Slice B advanced the canonical head to 058 (direct migration cursor).

    The 057 pre-lifecycle refresh-work zero-state domain is still required;
    only the schema pin moved, so the gate and the canonical migration-ledger
    drift guard keep describing the same database.
    """
    assert zero_state.REQUIRED_MIGRATION_COUNT == 58
    assert zero_state.REQUIRED_MIGRATION_HEAD == (
        "058_direct_pump_migration_cursor.sql"
    )
    assert "active_pre_lifecycle_discovery_refresh_work" in (
        zero_state.REQUIRED_ZERO_STATE_DOMAINS
    )


def test_migrations_050_055_056_are_the_required_historical_migrations() -> None:
    """050, 055 and 056 are all required, immutable historical packages.

    The earlier "050 only" contract is superseded: 055 and 056 were promoted so
    their untracked evidence is explained without publishing SQLite database
    images into the public Git remote. 057 remains the sole current transition.
    """
    profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
    assert len(profile.historical_migration_packages) == 3
    by_root = {item.package_root: item for item in profile.historical_migration_packages}
    assert set(by_root) == {
        git_auth.MIGRATION_PACKAGE_ROOT,
        git_auth.MIGRATION_055_PACKAGE_ROOT,
        git_auth.MIGRATION_056_PACKAGE_ROOT,
    }

    mig050 = by_root[git_auth.MIGRATION_PACKAGE_ROOT]
    assert mig050.execution_id == git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_EXECUTION_ID
    assert mig050.evidence_class == git_auth.HISTORICAL_MIGRATION_EVIDENCE_CLASS
    assert mig050.expected_file_count == 12

    mig055 = by_root[git_auth.MIGRATION_055_PACKAGE_ROOT]
    assert mig055.execution_id == (
        git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_055_EXECUTION_ID
    )
    assert mig055.evidence_class == git_auth.HISTORICAL_MIGRATION_055_EVIDENCE_CLASS
    assert mig055.expected_file_count == 5

    mig056 = by_root[git_auth.MIGRATION_056_PACKAGE_ROOT]
    assert mig056.execution_id == (
        git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_056_EXECUTION_ID
    )
    assert mig056.evidence_class == git_auth.HISTORICAL_MIGRATION_056_EVIDENCE_CLASS
    assert mig056.expected_file_count == 6

    # No historical package may be the current schema transition.
    assert git_auth.MIGRATION_057_PACKAGE_ROOT not in by_root
    assert profile.migration_package_root == git_auth.MIGRATION_057_PACKAGE_ROOT

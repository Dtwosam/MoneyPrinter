"""Focused migration-058 re-readiness contract for the four-token terminal proof.

Offline only. This file creates no authorization, consumes no authorization,
starts no Printer runtime, performs no source request, and mutates no
authoritative database.
"""

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli import four_token_proof_zero_state_gate as zero_state


def test_four_token_current_migration_evidence_is_exactly_058() -> None:
    """058 took over current authority when the runtime pin advanced to 058.

    Migration 057 is no longer current four-token schema-transition evidence.
    """
    profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
    assert profile.migration_package_root == git_auth.MIGRATION_058_PACKAGE_ROOT
    assert profile.migration_package_kind == git_auth.MIGRATION_058_PACKAGE_KIND
    assert profile.migration_package_root == (
        "operator-runs/v2-9-8b-migration-058-application"
    )
    assert profile.migration_package_kind == "MIGRATION_058_EVIDENCE"
    assert profile.migration_package_root != git_auth.MIGRATION_057_PACKAGE_ROOT
    assert profile.migration_package_kind != git_auth.MIGRATION_057_PACKAGE_KIND


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


def test_migrations_050_055_056_057_are_the_required_historical_migrations() -> None:
    """050, 055, 056 and 057 are all required, immutable historical packages.

    The earlier "050, 055, 056" contract is superseded: 057 was demoted when 058
    took over current schema-transition authority, exactly as 055 and 056 were
    demoted before it. 058 is now the sole current transition.
    """
    profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
    assert len(profile.historical_migration_packages) == 4
    by_root = {item.package_root: item for item in profile.historical_migration_packages}
    assert set(by_root) == {
        git_auth.MIGRATION_PACKAGE_ROOT,
        git_auth.MIGRATION_055_PACKAGE_ROOT,
        git_auth.MIGRATION_056_PACKAGE_ROOT,
        git_auth.MIGRATION_057_PACKAGE_ROOT,
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

    mig057 = by_root[git_auth.MIGRATION_057_PACKAGE_ROOT]
    assert mig057.execution_id == (
        git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_057_EXECUTION_ID
    )
    assert mig057.evidence_class == git_auth.HISTORICAL_MIGRATION_057_EVIDENCE_CLASS
    assert mig057.expected_file_count == 6

    # No historical package may be the current schema transition.
    assert git_auth.MIGRATION_058_PACKAGE_ROOT not in by_root
    assert profile.migration_package_root == git_auth.MIGRATION_058_PACKAGE_ROOT

"""V2-9.8B pre-lifecycle schema / gate coherence.

The bounded four-token zero-state gate must admit exactly migration 56 with head
``056_four_token_pre_lifecycle_terminal_provenance.sql``, so the already
implemented ``ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT`` terminalization is reachable
instead of raising on a missing provenance table.

The authorized head/count are explicit literals on purpose. They are never
derived from the migrations directory, so a future migration must be reviewed and
re-pinned deliberately rather than silently widening bounded-proof admission.
"""
from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli import four_token_proof_zero_state_gate as gate
from printer_v1.operator_cli import operational_campaign_recovery as recovery

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_SOURCE = REPO_ROOT / "src/printer_v1/operator_cli/four_token_proof_zero_state_gate.py"
MIGRATION_056_NAME = "056_four_token_pre_lifecycle_terminal_provenance.sql"
MIGRATION_055_NAME = "055_pre_admission_discovery_attempt_ownership.sql"


def _apply(db_path: Path, names: list[str]) -> list[str]:
    """Apply the named migrations to a disposable DB and record the ledger.

    Mirrors ``printer_v1.db.migrate.apply_migrations`` ledger bookkeeping so a
    partial (schema-55) catalogue can be built for the rejection case.
    """
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS printer_schema_migrations ("
            "version TEXT PRIMARY KEY, "
            "applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        for name in names:
            connection.executescript(
                (REPO_ROOT / "migrations" / name).read_text(encoding="utf-8")
            )
            connection.execute(
                "INSERT INTO printer_schema_migrations (version) VALUES (?)",
                (name,),
            )
        connection.commit()
        return [
            str(row[0])
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY version"
            )
        ]
    finally:
        connection.close()


def _canonical_names() -> list[str]:
    return sorted(p.name for p in (REPO_ROOT / "migrations").glob("*.sql"))


# --------------------------------------------------------------------------
# 1. Gate re-pin
# --------------------------------------------------------------------------


def test_zero_state_gate_admits_migration_056_only() -> None:
    assert gate.REQUIRED_MIGRATION_COUNT == 56
    assert gate.REQUIRED_MIGRATION_HEAD == MIGRATION_056_NAME


def test_zero_state_gate_rejects_the_superseded_055_pin() -> None:
    assert gate.REQUIRED_MIGRATION_COUNT != 55
    assert gate.REQUIRED_MIGRATION_HEAD != MIGRATION_055_NAME


def test_gate_migration_pins_are_explicit_literals_not_derived() -> None:
    """The pins must be static constants, reviewable in the diff.

    Deriving them from the migrations directory would let any future migration
    silently re-authorize bounded-proof admission without gate review.
    """
    tree = ast.parse(GATE_SOURCE.read_text())
    found: dict[str, ast.expr] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in {
                "REQUIRED_MIGRATION_COUNT",
                "REQUIRED_MIGRATION_HEAD",
            }:
                found[target.id] = node.value
    assert set(found) == {"REQUIRED_MIGRATION_COUNT", "REQUIRED_MIGRATION_HEAD"}
    for name, value in found.items():
        assert isinstance(value, ast.Constant), f"{name} must be a literal constant"
    assert found["REQUIRED_MIGRATION_COUNT"].value == 56
    assert found["REQUIRED_MIGRATION_HEAD"].value == MIGRATION_056_NAME
    source = GATE_SOURCE.read_text()
    assert "canonical_migration_count" not in source
    assert "canonical_migration_names" not in source


def test_canonical_ledger_drift_guard_is_still_wired_into_the_gate() -> None:
    """Re-pinning must not replace the canonical drift guard."""
    source = GATE_SOURCE.read_text()
    assert "assert_migration_ledger_ready" in source
    assert "migration_ledger_drift" in source


# --------------------------------------------------------------------------
# 2. Schema admission on disposable databases
# --------------------------------------------------------------------------


def test_disposable_schema_56_satisfies_the_gate_migration_pins(tmp_path) -> None:
    applied = _apply(tmp_path / "migrated.sqlite3", _canonical_names())
    assert len(applied) == gate.REQUIRED_MIGRATION_COUNT
    assert applied[-1] == gate.REQUIRED_MIGRATION_HEAD


def test_disposable_schema_55_does_not_satisfy_the_gate_migration_pins(
    tmp_path,
) -> None:
    names = [n for n in _canonical_names() if n != MIGRATION_056_NAME]
    applied = _apply(tmp_path / "stale.sqlite3", names)
    assert len(applied) == 55
    assert applied[-1] == MIGRATION_055_NAME
    assert len(applied) != gate.REQUIRED_MIGRATION_COUNT
    assert applied[-1] != gate.REQUIRED_MIGRATION_HEAD


def test_migration_056_provenance_objects_exist_on_disposable_schema(
    tmp_path,
) -> None:
    db = tmp_path / "provenance.sqlite3"
    _apply(db, _canonical_names())
    connection = sqlite3.connect(db)
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        triggers = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            )
        }
    finally:
        connection.close()
    assert "printer_four_token_pre_lifecycle_terminal_provenance" in tables
    for trigger in (
        "printer_four_token_pre_lifecycle_provenance_exact_shape",
        "printer_four_token_pre_lifecycle_provenance_immutable_update",
        "printer_four_token_pre_lifecycle_provenance_immutable_delete",
        "printer_pre_admission_attempt_forbids_pre_lifecycle_provenance",
        "printer_pre_admission_attempt_immutable_delete",
    ):
        assert trigger in triggers


# --------------------------------------------------------------------------
# 3. Evidence profile: 056 current, 050 still the required historical package,
#    055 constants preserved but deliberately not promoted
# --------------------------------------------------------------------------


def test_profile_current_migration_evidence_is_056() -> None:
    profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
    assert git_auth.MIGRATION_056_PACKAGE_ROOT == (
        "operator-runs/v2-9-8b-migration-056-application"
    )
    assert git_auth.MIGRATION_056_PACKAGE_KIND == "MIGRATION_056_EVIDENCE"
    assert profile.migration_package_root == git_auth.MIGRATION_056_PACKAGE_ROOT
    assert profile.migration_package_kind == git_auth.MIGRATION_056_PACKAGE_KIND


def test_profile_keeps_050_as_the_declared_required_historical_package() -> None:
    profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
    roots = {
        package.package_root: package
        for package in profile.historical_migration_packages
    }
    assert set(roots) == {git_auth.MIGRATION_PACKAGE_ROOT}
    mig050 = roots[git_auth.MIGRATION_PACKAGE_ROOT]
    assert mig050.execution_id == git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_EXECUTION_ID
    assert mig050.evidence_class == git_auth.HISTORICAL_MIGRATION_EVIDENCE_CLASS


def test_055_is_not_newly_promoted_to_a_required_historical_package() -> None:
    """Declaring 055 here would make its evidence mandatory forever.

    Every declared historical package is required for every manifest build, so
    promoting 055 is a broader contract change than the approved 056 admission
    repair. It is deferred, not silently adopted.
    """
    profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
    declared = {p.package_root for p in profile.historical_migration_packages}
    assert git_auth.MIGRATION_055_PACKAGE_ROOT not in declared


def test_055_constants_are_preserved_and_not_repurposed() -> None:
    """055 keeps its own identity; it is never renamed into the 056 contract."""
    assert git_auth.MIGRATION_055_PACKAGE_ROOT == (
        "operator-runs/v2-9-8b-migration-055-application"
    )
    assert git_auth.MIGRATION_055_PACKAGE_KIND == "MIGRATION_055_EVIDENCE"
    assert git_auth.MIGRATION_055_PACKAGE_ROOT != git_auth.MIGRATION_056_PACKAGE_ROOT
    assert git_auth.MIGRATION_055_PACKAGE_KIND != git_auth.MIGRATION_056_PACKAGE_KIND
    # 055 keeps a usable historical identity for a future deferred lane.
    assert git_auth.HISTORICAL_MIGRATION_055_EVIDENCE_CLASS == (
        "HISTORICAL_MIGRATION_055_EVIDENCE"
    )
    assert git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_055_EXECUTION_ID == (
        "MIGRATION_055_20260813T220109Z"
    )


# --------------------------------------------------------------------------
# 4. Historical reconciliation must stay pinned to 55/055
# --------------------------------------------------------------------------


def test_historical_reconciliation_contract_remains_pinned_to_55() -> None:
    """The completed historical reconciliation describes a past state.

    Advancing its pins would falsify its own provenance.
    """
    source = Path(recovery.__file__).read_text()
    assert "len(migrations) != 55" in source
    assert MIGRATION_055_NAME in source
    assert "!= 56" not in source

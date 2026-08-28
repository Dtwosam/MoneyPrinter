"""V2-9.8B pre-lifecycle schema / gate coherence.

The bounded four-token zero-state gate must admit exactly the current canonical
head, so the already implemented ``ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT``
terminalization is reachable instead of raising on a missing provenance table,
and so the pin and the canonical migration-ledger drift guard keep describing
the same database.

The authorized head/count are explicit literals on purpose. They are never
derived from the migrations directory, so a future migration must be reviewed and
re-pinned deliberately rather than silently widening bounded-proof admission.
"""
from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

from printer_v1.db.migrate import canonical_migration_names
from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli import four_token_proof_zero_state_gate as gate
from printer_v1.operator_cli import operational_campaign_recovery as recovery
from printer_v1.operator_cli import schema_admission_coherence as coherence

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_SOURCE = REPO_ROOT / "src/printer_v1/operator_cli/four_token_proof_zero_state_gate.py"
HELPER_SOURCE = REPO_ROOT / "src/printer_v1/operator_cli/schema_admission_coherence.py"
MIGRATION_061_NAME = "061_standard_4h_progression_fault_preservation.sql"
MIGRATION_062_NAME = "062_pre_admission_attempt_evidence.sql"
MIGRATION_059_NAME = "059_pair_ready_parent_terminal_cancellation_transition.sql"
MIGRATION_058_NAME = "058_direct_pump_migration_cursor.sql"
MIGRATION_057_NAME = "057_pre_lifecycle_discovery_refresh_work.sql"
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
    return list(canonical_migration_names())


def _names_through(ordinal: int) -> list[str]:
    return [name for name in _canonical_names() if int(name[:3]) <= ordinal]


# --------------------------------------------------------------------------
# 1. Gate re-pin
# --------------------------------------------------------------------------


def test_zero_state_gate_reexports_helper_pin_62() -> None:
    assert gate.REQUIRED_MIGRATION_COUNT == 62
    assert gate.REQUIRED_MIGRATION_HEAD == MIGRATION_062_NAME
    assert gate.REQUIRED_MIGRATION_COUNT == coherence.REQUIRED_MIGRATION_COUNT
    assert gate.REQUIRED_MIGRATION_HEAD == coherence.REQUIRED_MIGRATION_HEAD


def test_zero_state_gate_rejects_the_superseded_055_through_059_pins() -> None:
    assert gate.REQUIRED_MIGRATION_COUNT not in (55, 56, 57, 58, 59)
    assert gate.REQUIRED_MIGRATION_HEAD != MIGRATION_055_NAME
    assert gate.REQUIRED_MIGRATION_HEAD != MIGRATION_056_NAME
    assert gate.REQUIRED_MIGRATION_HEAD != MIGRATION_057_NAME
    assert gate.REQUIRED_MIGRATION_HEAD != MIGRATION_058_NAME
    assert gate.REQUIRED_MIGRATION_HEAD != MIGRATION_059_NAME


def test_helper_migration_pins_are_explicit_literals_not_derived() -> None:
    """The pins must be static constants on the helper, reviewable in the diff."""
    tree = ast.parse(HELPER_SOURCE.read_text())
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
    assert found["REQUIRED_MIGRATION_COUNT"].value == 62
    assert found["REQUIRED_MIGRATION_HEAD"].value == MIGRATION_062_NAME
    source = HELPER_SOURCE.read_text()
    assert "REQUIRED_MIGRATION_COUNT = canonical_migration_count()" not in source
    assert gate.REQUIRED_MIGRATION_COUNT == len(_canonical_names())
    assert gate.REQUIRED_MIGRATION_HEAD == _canonical_names()[-1]


def test_gate_reexports_pins_without_local_literals() -> None:
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
    assert found == {}
    source = GATE_SOURCE.read_text()
    assert "canonical_migration_count" not in source
    assert "canonical_migration_names" not in source
    assert "evaluate_schema_admission_coherence" in source


def test_canonical_ledger_drift_guard_is_still_wired_into_the_gate() -> None:
    """Re-pinning must not replace the canonical drift guard."""
    source = GATE_SOURCE.read_text()
    assert "assert_migration_ledger_ready" in source
    assert "migration_ledger_drift" in source


# --------------------------------------------------------------------------
# 2. Schema admission on disposable databases
# --------------------------------------------------------------------------


def test_disposable_schema_59_does_not_satisfy_the_gate_migration_pins(
    tmp_path,
) -> None:
    applied = _apply(tmp_path / "schema59.sqlite3", _names_through(59))
    assert len(applied) == 59
    assert applied[-1] == MIGRATION_059_NAME
    assert len(applied) != gate.REQUIRED_MIGRATION_COUNT
    assert applied[-1] != gate.REQUIRED_MIGRATION_HEAD


def test_disposable_schema_58_does_not_satisfy_the_gate_migration_pins(
    tmp_path,
) -> None:
    applied = _apply(tmp_path / "stale.sqlite3", _names_through(58))
    assert len(applied) == 58
    assert applied[-1] == MIGRATION_058_NAME
    assert len(applied) != gate.REQUIRED_MIGRATION_COUNT
    assert applied[-1] != gate.REQUIRED_MIGRATION_HEAD


def test_migration_056_provenance_objects_exist_on_disposable_schema(
    tmp_path,
) -> None:
    db = tmp_path / "provenance.sqlite3"
    _apply(db, _names_through(56))
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
# 3. Evidence profile: 062 current; 050, 055, 056, 057, 058, 059 and 061 are
#    required immutable historical packages; each keeps its own identity
# --------------------------------------------------------------------------


def test_profile_current_migration_evidence_is_062() -> None:
    profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
    assert git_auth.MIGRATION_062_PACKAGE_ROOT == (
        "operator-runs/v2-9-8b-migration-062-application"
    )
    assert git_auth.MIGRATION_062_PACKAGE_KIND == "MIGRATION_062_EVIDENCE"
    assert profile.migration_package_root == git_auth.MIGRATION_062_PACKAGE_ROOT
    assert profile.migration_package_kind == git_auth.MIGRATION_062_PACKAGE_KIND
    assert profile.current_migration_execution_id == (
        git_auth.FOUR_TOKEN_CURRENT_MIGRATION_062_EXECUTION_ID
    )
    # 056 and 057 are no longer current; each kept its own constants as a
    # historical identity when its successor took over.
    assert profile.migration_package_root != git_auth.MIGRATION_056_PACKAGE_ROOT
    assert profile.migration_package_root != git_auth.MIGRATION_057_PACKAGE_ROOT


def test_profile_declares_050_through_061_as_required_historical_packages() -> None:
    profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
    roots = {
        package.package_root: package
        for package in profile.historical_migration_packages
    }
    assert set(roots) == {
        git_auth.MIGRATION_PACKAGE_ROOT,
        git_auth.MIGRATION_055_PACKAGE_ROOT,
        git_auth.MIGRATION_056_PACKAGE_ROOT,
        git_auth.MIGRATION_057_PACKAGE_ROOT,
        git_auth.MIGRATION_058_PACKAGE_ROOT,
        git_auth.MIGRATION_059_PACKAGE_ROOT,
        git_auth.MIGRATION_061_PACKAGE_ROOT,
    }
    mig050 = roots[git_auth.MIGRATION_PACKAGE_ROOT]
    assert mig050.execution_id == git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_EXECUTION_ID
    assert mig050.evidence_class == git_auth.HISTORICAL_MIGRATION_EVIDENCE_CLASS
    assert mig050.expected_file_count == 12
    assert mig050.expected_inventory_sha256 == (
        git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_EXPECTED_INVENTORY_SHA256
    )


def test_055_through_061_are_promoted_required_historical_packages() -> None:
    """Declaring 055/056/057/058/059/061 makes evidence mandatory forever.

    That obligation is accepted deliberately: it is the only way to explain
    their untracked bytes without publishing SQLite database images into the
    public Git remote. Each carries its own immutable completeness identity, so
    partial erosion cannot silently redefine the package.
    """
    profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
    declared = {p.package_root: p for p in profile.historical_migration_packages}
    assert git_auth.MIGRATION_055_PACKAGE_ROOT in declared
    assert git_auth.MIGRATION_056_PACKAGE_ROOT in declared
    assert git_auth.MIGRATION_057_PACKAGE_ROOT in declared
    assert git_auth.MIGRATION_058_PACKAGE_ROOT in declared
    assert git_auth.MIGRATION_059_PACKAGE_ROOT in declared
    assert git_auth.MIGRATION_061_PACKAGE_ROOT in declared

    mig055 = declared[git_auth.MIGRATION_055_PACKAGE_ROOT]
    assert mig055.execution_id == (
        git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_055_EXECUTION_ID
    )
    assert mig055.evidence_class == git_auth.HISTORICAL_MIGRATION_055_EVIDENCE_CLASS
    assert mig055.expected_file_count == 5

    mig056 = declared[git_auth.MIGRATION_056_PACKAGE_ROOT]
    assert mig056.execution_id == (
        git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_056_EXECUTION_ID
    )
    assert mig056.evidence_class == git_auth.HISTORICAL_MIGRATION_056_EVIDENCE_CLASS
    assert mig056.expected_file_count == 6

    mig057 = declared[git_auth.MIGRATION_057_PACKAGE_ROOT]
    assert mig057.execution_id == (
        git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_057_EXECUTION_ID
    )
    assert mig057.evidence_class == git_auth.HISTORICAL_MIGRATION_057_EVIDENCE_CLASS
    assert mig057.expected_file_count == 6

    mig058 = declared[git_auth.MIGRATION_058_PACKAGE_ROOT]
    assert mig058.execution_id == (
        git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_058_EXECUTION_ID
    )
    assert mig058.evidence_class == git_auth.HISTORICAL_MIGRATION_058_EVIDENCE_CLASS
    assert mig058.expected_file_count == 11

    mig059 = declared[git_auth.MIGRATION_059_PACKAGE_ROOT]
    assert mig059.execution_id == (
        git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_059_EXECUTION_ID
    )
    assert mig059.evidence_class == git_auth.HISTORICAL_MIGRATION_059_EVIDENCE_CLASS
    assert mig059.expected_file_count == 5

    mig061 = declared[git_auth.MIGRATION_061_PACKAGE_ROOT]
    assert mig061.execution_id == (
        git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_061_EXECUTION_ID
    )
    assert mig061.evidence_class == git_auth.HISTORICAL_MIGRATION_061_EVIDENCE_CLASS
    assert mig061.expected_file_count == 5

    # Historical promotion never makes a package the current schema transition.
    assert git_auth.MIGRATION_062_PACKAGE_ROOT not in declared


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

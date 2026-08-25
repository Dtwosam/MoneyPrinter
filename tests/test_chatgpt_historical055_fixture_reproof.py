from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import tempfile

import printer_v1.db.migrate as migration_runner


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "tests/test_v2_9_8b_historical_four_token_reconciliation.py"


def _load_original():
    spec = importlib.util.spec_from_file_location("historical_reconciliation_original", ORIGINAL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _apply_migrations_through_055(db: Path) -> None:
    canonical = migration_runner.canonical_migration_names()
    assert len(canonical) >= 55
    assert canonical[54] == "055_pre_admission_discovery_attempt_ownership.sql"
    with tempfile.TemporaryDirectory() as tmp:
        subset = Path(tmp) / "migrations-055"
        subset.mkdir()
        for name in canonical[:55]:
            shutil.copy2(migration_runner.MIGRATIONS_DIR / name, subset / name)
        original = migration_runner.MIGRATIONS_DIR
        migration_runner.MIGRATIONS_DIR = subset
        try:
            migration_runner.apply_migrations(db)
        finally:
            migration_runner.MIGRATIONS_DIR = original


def _module_with_true_055_fixture():
    module = _load_original()
    module.apply_migrations = _apply_migrations_through_055
    module._downgrade_fixture_to_055 = lambda _db: None
    return module


def test_exact_historical_reconciliation_closes_only_approved_residue(tmp_path: Path) -> None:
    _module_with_true_055_fixture().test_exact_historical_reconciliation_closes_only_approved_residue(tmp_path)


def test_exact_historical_reconciliation_rejects_queue_drift_and_live_process(tmp_path: Path) -> None:
    _module_with_true_055_fixture().test_exact_historical_reconciliation_rejects_queue_drift_and_live_process(tmp_path)


def test_exact_historical_reconciliation_is_idempotent_without_second_mutation(tmp_path: Path) -> None:
    _module_with_true_055_fixture().test_exact_historical_reconciliation_is_idempotent_without_second_mutation(tmp_path)

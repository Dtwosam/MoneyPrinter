from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
import sqlite3

from printer_v1.db.migrate import canonical_migration_count, canonical_migration_names
from printer_v1.operator_cli.proof_db_schema_readiness import CANONICAL_PERSISTENT_DB
from printer_v1.operator_cli import window_15m_disposable_public_composition_proof as proof
from printer_v1.operator_cli.window_15m_concrete_composition import (
    ordinary_window_15m_builder_identities,
)


ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = ROOT / "scripts" / "v2_9_8b_checkpoint8_controlling_public_composition_proof.py"


def _load_harness(module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, HARNESS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_success_fixture_composition_covers_exact_canonical_twenty_labels() -> None:
    harness = _load_harness("checkpoint8_fixture_entry_exact_registry")
    composition = harness.build_checkpoint8_deterministic_success_fixture_composition()
    expected = tuple(ordinary_window_15m_builder_identities())
    assert len(expected) == 20
    assert composition.labels == expected
    assert tuple(composition.builders) == expected
    assert composition.provider_fallback_allowed is False


def test_success_fixture_materializes_every_label_with_zero_fallback(tmp_path: Path) -> None:
    harness = _load_harness("checkpoint8_fixture_entry_materialization")
    prepared = harness.prepare_checkpoint8_controlling_entry(
        tmp_path,
        proof_id="checkpoint8-entry-materialization",
        git_head="a" * 40,
    )
    materialized = proof.materialize_disposable_public_composition_execution(
        prepared.runtime
    )
    expected = tuple(ordinary_window_15m_builder_identities())
    assert tuple(materialized.outputs_by_label) == expected
    assert materialized.provider_fallback_allowed is False
    assert materialized.fixture_composition_manifest_sha256 == (
        prepared.runtime.fixture_composition_manifest_sha256
    )
    for label, output in materialized.outputs_by_label.items():
        assert getattr(output, "_printer_checkpoint8_fixture_output", False) is True
        assert label in getattr(
            output,
            "_printer_checkpoint8_fixture_output_labels",
            (),
        )


def test_entry_preparation_creates_fresh_canonically_migrated_disposable_target(
    tmp_path: Path,
) -> None:
    harness = _load_harness("checkpoint8_fixture_entry_disposable_target")
    prepared = harness.prepare_checkpoint8_controlling_entry(
        tmp_path,
        proof_id="checkpoint8-entry-db",
        git_head="b" * 40,
    )
    db_path = Path(prepared.runtime.plan.resolved_db_path).resolve()
    artifact_root = Path(prepared.runtime.plan.resolved_artifact_root).resolve()
    assert db_path.is_file()
    assert db_path != Path(CANONICAL_PERSISTENT_DB).resolve()
    assert artifact_root.is_dir()
    assert prepared.runtime.plan.migration_count == canonical_migration_count()
    assert prepared.runtime.plan.migration_head == canonical_migration_names()[-1]
    assert prepared.runtime.plan.provider_execution_allowed is False
    assert prepared.runtime.plan.automatic_retry_allowed is False
    assert prepared.runtime.plan.manual_rerun_allowed is False
    assert prepared.runtime.plan.resume_allowed is False
    assert prepared.runtime.plan.restart_allowed is False
    assert prepared.runtime.plan.successor_allowed is False

    connection = sqlite3.connect(db_path)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()


def test_entry_preparation_captures_pre_run_evidence_and_zero_network(tmp_path: Path) -> None:
    harness = _load_harness("checkpoint8_fixture_entry_pre_run_evidence")
    tripwire = harness.Checkpoint8NetworkTripwire()
    with tripwire:
        prepared = harness.prepare_checkpoint8_controlling_entry(
            tmp_path,
            proof_id="checkpoint8-entry-evidence",
            git_head="c" * 40,
        )
    assert tripwire.attempt_count == 0
    evidence = prepared.pre_run_evidence
    assert evidence["db_sha256"] == prepared.runtime.plan.pre_mutation_db_sha256
    assert evidence["migration_count"] == canonical_migration_count()
    assert evidence["migration_head"] == canonical_migration_names()[-1]
    assert evidence["integrity_check"] == "ok"
    assert evidence["foreign_key_violations"] == 0
    assert evidence["protected_capability_counts"]
    assert all(value == 0 for value in evidence["protected_capability_counts"].values())


def test_entry_preparation_does_not_consume_controlling_attempt(tmp_path: Path) -> None:
    harness = _load_harness("checkpoint8_fixture_entry_sentinel_order")
    prepared = harness.prepare_checkpoint8_controlling_entry(
        tmp_path,
        proof_id="checkpoint8-entry-sentinel-order",
        git_head="d" * 40,
    )
    assert prepared.proof_root == tmp_path.resolve()
    assert not (tmp_path / "checkpoint8-controlling-attempt.json").exists()


def test_fixture_entry_preparation_itself_cannot_start_controlling_campaign() -> None:
    harness = _load_harness("checkpoint8_fixture_entry_import_safe")
    preparation_source = inspect.getsource(
        harness.prepare_checkpoint8_controlling_entry
    )
    assert "run_operational_campaign(" not in preparation_source
    assert "report_only(" not in preparation_source
    signature = inspect.signature(harness.main)
    assert "argv" in signature.parameters

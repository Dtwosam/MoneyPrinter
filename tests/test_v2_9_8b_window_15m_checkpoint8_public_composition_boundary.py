from __future__ import annotations

import hashlib
import importlib
import inspect
from pathlib import Path

import pytest

from printer_v1.db.migrate import canonical_migration_count, canonical_migration_names
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli.proof_db_schema_readiness import CANONICAL_PERSISTENT_DB
from printer_v1.operator_cli.window_15m_concrete_composition import (
    ordinary_window_15m_builder_identities,
)


def _proof_module():
    return importlib.import_module(
        "printer_v1.operator_cli.window_15m_disposable_public_composition_proof"
    )


def _build_plan(tmp_path: Path):
    proof = _proof_module()
    db_path = tmp_path / "checkpoint8.sqlite3"
    db_path.write_bytes(b"checkpoint8-disposable-db")
    artifact_root = tmp_path / "artifacts"
    labels = ordinary_window_15m_builder_identities()
    return proof.build_disposable_public_composition_proof_plan(
        proof_id="checkpoint8-boundary-red",
        db_path=db_path,
        db_sha256=hashlib.sha256(db_path.read_bytes()).hexdigest(),
        migration_count=canonical_migration_count(),
        migration_head=canonical_migration_names()[-1],
        artifact_root=artifact_root,
        composition_labels=labels,
        provider_execution_allowed=False,
        automatic_retry_allowed=False,
        manual_rerun_allowed=False,
        resume_allowed=False,
        restart_allowed=False,
        successor_allowed=False,
    )


def test_public_run_exposes_disposable_proof_capability() -> None:
    signature = inspect.signature(command.run_operational_campaign)
    assert "disposable_proof" in signature.parameters


def test_disposable_plan_requires_exact_offline_registry_contract(tmp_path: Path) -> None:
    proof = _proof_module()
    plan = _build_plan(tmp_path)
    validated = proof.validate_disposable_public_composition_proof_plan(
        plan,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
        expected_composition_labels=ordinary_window_15m_builder_identities(),
    )
    assert validated == plan
    assert plan.provider_execution_allowed is False

    with pytest.raises(Exception):
        proof.build_disposable_public_composition_proof_plan(
            proof_id="checkpoint8-missing-label",
            db_path=plan.resolved_db_path,
            db_sha256=plan.pre_mutation_db_sha256,
            migration_count=plan.migration_count,
            migration_head=plan.migration_head,
            artifact_root=plan.resolved_artifact_root,
            composition_labels=ordinary_window_15m_builder_identities()[:-1],
            provider_execution_allowed=False,
            automatic_retry_allowed=False,
            manual_rerun_allowed=False,
            resume_allowed=False,
            restart_allowed=False,
            successor_allowed=False,
        )


def test_disposable_binding_has_no_fabricated_authorization_facts(tmp_path: Path) -> None:
    proof = _proof_module()
    plan = _build_plan(tmp_path)
    binding = proof.build_disposable_public_composition_proof_binding(
        plan,
        execution_id="exec-c8",
        campaign_id="campaign-c8",
        campaign_run_id="run-c8",
        cycle_id="cycle-c8",
        configuration_id="config-c8",
        db_target_identity=f"sha256:{plan.pre_mutation_db_sha256}",
        fixture_composition_manifest_sha256="a" * 64,
    )
    fields = set(vars(binding))
    assert not any(name.startswith("authorization") for name in fields)
    assert "application_marker_sha256" not in fields
    assert proof.validate_disposable_public_composition_proof_binding(
        binding,
        actual_db_path=plan.resolved_db_path,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
        expected_plan=plan,
    ) is None


def test_holder_stage_evidence_is_required_for_disposable_proof_without_auth(
    tmp_path: Path,
) -> None:
    plan = _build_plan(tmp_path)
    assert command._holder_stage_evidence_sealer_required(
        git_provenance_authorization=None,
        disposable_proof=plan,
    ) is True
    assert command._holder_stage_evidence_sealer_required(
        git_provenance_authorization=None,
        disposable_proof=None,
    ) is False

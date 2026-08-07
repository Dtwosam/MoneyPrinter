from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from printer_v1.db.migrate import canonical_migration_count, canonical_migration_names
from printer_v1.operator_cli import operational_database_target_binding as db_binding
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli import window_15m_disposable_public_composition_proof as proof
from printer_v1.operator_cli.proof_db_schema_readiness import CANONICAL_PERSISTENT_DB
from printer_v1.operator_cli.window_15m_concrete_composition import (
    ordinary_window_15m_builder_identities,
)


def _plan(tmp_path: Path) -> proof.DisposablePublicCompositionProofPlan:
    db_path = tmp_path / "checkpoint8.sqlite3"
    db_path.write_bytes(b"checkpoint8-fail-closed")
    return proof.build_disposable_public_composition_proof_plan(
        proof_id="checkpoint8-fail-closed",
        db_path=db_path,
        db_sha256=hashlib.sha256(db_path.read_bytes()).hexdigest(),
        migration_count=canonical_migration_count(),
        migration_head=canonical_migration_names()[-1],
        artifact_root=tmp_path / "artifacts",
        composition_labels=ordinary_window_15m_builder_identities(),
        provider_execution_allowed=False,
        automatic_retry_allowed=False,
        manual_rerun_allowed=False,
        resume_allowed=False,
        restart_allowed=False,
        successor_allowed=False,
    )


def _fixture_builder(label: str):
    return proof.mark_checkpoint8_fixture_builder(
        lambda: {"fixture_label": label},
        label=label,
    )


def test_proof_plus_external_authorization_blocks_before_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan(tmp_path)

    def preflight_must_not_run(*args, **kwargs):
        raise AssertionError("preflight reached before proof/auth conflict gate")

    monkeypatch.setattr(command, "build_activation_preflight", preflight_must_not_run)

    with pytest.raises(command.OperationalMemoryFactoryError) as excinfo:
        command.run_operational_campaign(
            operator_approved=True,
            git_provenance_authorization=object(),
            disposable_proof=plan,
        )
    assert str(excinfo.value) == "DISPOSABLE_PROOF_EXTERNAL_AUTHORIZATION_CONFLICT"


def test_fixture_composition_requires_exact_registry_and_fixture_markers() -> None:
    labels = ordinary_window_15m_builder_identities()
    builders = {label: _fixture_builder(label) for label in labels}
    composition = proof.build_window_15m_fixture_composition(builders)
    validated = proof.validate_window_15m_fixture_composition(
        composition,
        expected_labels=labels,
    )
    assert validated == composition
    assert composition.labels == labels
    assert composition.provider_fallback_allowed is False


def test_fixture_composition_missing_label_blocks() -> None:
    labels = ordinary_window_15m_builder_identities()
    builders = {label: _fixture_builder(label) for label in labels[:-1]}
    with pytest.raises(proof.DisposablePublicCompositionProofError) as excinfo:
        proof.build_window_15m_fixture_composition(builders)
    assert str(excinfo.value) == "FIXTURE_COMPOSITION_REGISTRY_IDENTITY_MISMATCH"


def test_fixture_composition_extra_label_blocks() -> None:
    labels = ordinary_window_15m_builder_identities()
    builders = {label: _fixture_builder(label) for label in labels}
    builders["not-an-ordinary-window15m-dependency"] = _fixture_builder(
        "not-an-ordinary-window15m-dependency"
    )
    with pytest.raises(proof.DisposablePublicCompositionProofError) as excinfo:
        proof.build_window_15m_fixture_composition(builders)
    assert str(excinfo.value) == "FIXTURE_COMPOSITION_REGISTRY_IDENTITY_MISMATCH"


def test_fixture_composition_unmarked_live_builder_blocks() -> None:
    labels = ordinary_window_15m_builder_identities()
    builders = {label: _fixture_builder(label) for label in labels}
    builders[labels[0]] = lambda: object()
    with pytest.raises(proof.DisposablePublicCompositionProofError) as excinfo:
        proof.build_window_15m_fixture_composition(builders)
    assert str(excinfo.value) == f"FIXTURE_BUILDER_NOT_EXPLICIT:{labels[0]}"


def test_dedicated_no_auth_db_expectation_contains_only_proof_truth(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    binding = proof.build_disposable_public_composition_proof_binding(
        plan,
        execution_id="exec-c8",
        campaign_id="campaign-c8",
        campaign_run_id="run-c8",
        cycle_id="cycle-c8",
        configuration_id="config-c8",
        db_target_identity=f"sha256:{plan.pre_mutation_db_sha256}",
        fixture_composition_manifest_sha256="b" * 64,
    )
    expectation = db_binding.build_disposable_public_composition_proof_expectation(
        binding
    )
    assert expectation["target_kind"] == db_binding.DISPOSABLE_PUBLIC_COMPOSITION_PROOF
    assert expectation["expectation_version"] == (
        "DISPOSABLE_PUBLIC_COMPOSITION_PROOF_EXPECTATION_V1"
    )
    assert not any(key.startswith("authorization") for key in expectation)
    assert "application_marker_sha256" not in expectation
    assert db_binding.validate_disposable_public_composition_proof_invocation(
        binding,
        expectation=expectation,
        actual_db_path=plan.resolved_db_path,
        canonical_authoritative_db_path=CANONICAL_PERSISTENT_DB,
        execution_id="exec-c8",
        campaign_id="campaign-c8",
        campaign_run_id="run-c8",
        cycle_id="cycle-c8",
        configuration_id="config-c8",
        durable_db_target_identity=f"sha256:{plan.pre_mutation_db_sha256}",
        fixture_composition_manifest_sha256="b" * 64,
    ) is None


def test_existing_proof_guards_stay_fail_closed(tmp_path: Path) -> None:
    plan = _plan(tmp_path)

    with pytest.raises(proof.DisposablePublicCompositionProofError) as excinfo:
        proof.validate_disposable_public_composition_proof_plan(
            plan,
            canonical_db_path=plan.resolved_db_path,
            expected_composition_labels=ordinary_window_15m_builder_identities(),
        )
    assert str(excinfo.value) == "CANONICAL_PRODUCTION_DB_FORBIDDEN"

    with pytest.raises(proof.DisposablePublicCompositionProofError):
        replace(plan, automatic_retry_allowed=True)
        proof.validate_disposable_public_composition_proof_plan(
            replace(plan, automatic_retry_allowed=True),
            canonical_db_path=CANONICAL_PERSISTENT_DB,
            expected_composition_labels=ordinary_window_15m_builder_identities(),
        )

    binding = proof.build_disposable_public_composition_proof_binding(
        plan,
        execution_id="exec-c8",
        campaign_id="campaign-c8",
        campaign_run_id="run-c8",
        cycle_id="cycle-c8",
        configuration_id="config-c8",
        db_target_identity=f"sha256:{plan.pre_mutation_db_sha256}",
        fixture_composition_manifest_sha256="c" * 64,
    )
    Path(plan.resolved_db_path).write_bytes(b"drifted-after-binding")
    assert proof.validate_disposable_public_composition_proof_binding(
        binding,
        actual_db_path=plan.resolved_db_path,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
        expected_plan=plan,
    ) == "DISPOSABLE_PROOF_DB_SHA256_MISMATCH"

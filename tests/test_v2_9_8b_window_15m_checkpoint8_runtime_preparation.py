from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from printer_v1.db.migrate import canonical_migration_count, canonical_migration_names
from printer_v1.operator_cli import authoritative_live_operational_campaign as live_owner
from printer_v1.operator_cli import operational_database_target_binding as db_binding
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli import window_15m_disposable_public_composition_proof as proof
from printer_v1.operator_cli.proof_db_schema_readiness import CANONICAL_PERSISTENT_DB
from printer_v1.operator_cli.window_15m_concrete_composition import (
    ordinary_window_15m_builder_identities,
)


def _plan(tmp_path: Path) -> proof.DisposablePublicCompositionProofPlan:
    db_path = tmp_path / "checkpoint8-runtime.sqlite3"
    db_path.write_bytes(b"checkpoint8-runtime-preparation")
    return proof.build_disposable_public_composition_proof_plan(
        proof_id="checkpoint8-runtime-preparation",
        db_path=db_path,
        db_sha256=hashlib.sha256(db_path.read_bytes()).hexdigest(),
        migration_count=canonical_migration_count(),
        migration_head=canonical_migration_names()[-1],
        artifact_root=tmp_path / "proof-artifacts",
        composition_labels=ordinary_window_15m_builder_identities(),
        provider_execution_allowed=False,
        automatic_retry_allowed=False,
        manual_rerun_allowed=False,
        resume_allowed=False,
        restart_allowed=False,
        successor_allowed=False,
    )


def _composition() -> proof.Window15MFixtureComposition:
    labels = ordinary_window_15m_builder_identities()
    builders = {}
    for label in labels:
        builders[label] = proof.mark_checkpoint8_fixture_builder(
            lambda label=label: {"fixture_label": label},
            label=label,
        )
    return proof.build_window_15m_fixture_composition(builders)


def _runtime_for_red(tmp_path: Path):
    plan = _plan(tmp_path)
    composition = _composition()
    builder = getattr(
        proof,
        "build_disposable_public_composition_proof_runtime",
        None,
    )
    if callable(builder):
        return builder(
            plan,
            composition,
            canonical_db_path=CANONICAL_PERSISTENT_DB,
        )
    return SimpleNamespace(
        plan=plan,
        fixture_composition=composition,
        fixture_composition_manifest_sha256=(
            composition.fixture_composition_manifest_sha256
        ),
    )


def test_runtime_capability_binds_plan_and_exact_fixture_manifest(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    composition = _composition()
    runtime = proof.build_disposable_public_composition_proof_runtime(
        plan,
        composition,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
    )
    assert runtime.plan == plan
    assert runtime.fixture_composition == composition
    assert runtime.fixture_composition_manifest_sha256 == (
        composition.fixture_composition_manifest_sha256
    )
    fields = set(vars(runtime))
    assert not any(name.startswith("authorization") for name in fields)
    assert "application_marker_sha256" not in fields


def test_runtime_targets_are_exact_disposable_plan_locations(tmp_path: Path) -> None:
    runtime = _runtime_for_red(tmp_path)
    targets = command._resolve_disposable_public_composition_targets(runtime)
    assert Path(targets["db_path"]).resolve() == Path(
        runtime.plan.resolved_db_path
    ).resolve()
    assert Path(targets["artifact_root"]).resolve() == Path(
        runtime.plan.resolved_artifact_root
    ).resolve()
    assert Path(targets["db_path"]).resolve() != Path(
        CANONICAL_PERSISTENT_DB
    ).resolve()
    assert targets["fixture_composition_manifest_sha256"] == (
        runtime.fixture_composition_manifest_sha256
    )


def test_campaign_command_can_persist_proof_expectation_without_auth_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan(tmp_path)
    composition = _composition()
    binding = proof.build_disposable_public_composition_proof_binding(
        plan,
        execution_id="exec-c8",
        campaign_id="exec-c8-campaign",
        campaign_run_id="exec-c8-campaign-run",
        cycle_id="exec-c8-cycle",
        configuration_id="exec-c8-configuration",
        db_target_identity=f"sha256:{plan.pre_mutation_db_sha256}",
        fixture_composition_manifest_sha256=(
            composition.fixture_composition_manifest_sha256
        ),
    )
    captured: dict[str, object] = {}

    def fake_create_graph(db_path, **kwargs):
        captured["db_path"] = str(Path(db_path).resolve())
        captured["configuration"] = dict(kwargs["configuration"])
        return {"configuration_hash": "fixture-configuration-hash"}

    monkeypatch.setattr(command, "create_operational_campaign_graph", fake_create_graph)

    paths = {
        "reports": tmp_path / "reports",
        "lock": tmp_path / "campaign.lease.lock",
    }
    preflight = {
        "database_sha256": plan.pre_mutation_db_sha256,
        "database_path": plan.resolved_db_path,
        "migration_count": plan.migration_count,
        "latest_migration": plan.migration_head,
        "git_provenance": {
            "git_commit": "fixture",
            "git_branch": "fixture",
            "git_dirty": False,
            "git_untracked_present": False,
            "git_repo_root": str(tmp_path),
            "git_status_porcelain": [],
        },
    }
    backup = {
        "source_identity": f"sha256:{plan.pre_mutation_db_sha256}",
        "backup_hash": "a" * 64,
        "latest_rehearsed_migration": plan.migration_head,
    }

    built_command, cycle_id = command._create_campaign_command(
        execution_id="exec-c8",
        paths=paths,
        preflight=preflight,
        backup=backup,
        now="2026-08-07T00:00:00+00:00",
        operator_approved=True,
        policy=command._NORMAL_CAMPAIGN_POLICY,
        authorization_runtime_facts=None,
        disposable_proof_binding=binding,
        db_path=plan.resolved_db_path,
    )

    assert cycle_id == "exec-c8-cycle"
    assert Path(built_command.db_path).resolve() == Path(plan.resolved_db_path).resolve()
    assert captured["db_path"] == str(Path(plan.resolved_db_path).resolve())
    configuration = captured["configuration"]
    assert isinstance(configuration, dict)
    assert "authorization_marker" not in configuration
    assert "authorization_marker_sha256" not in configuration
    expectation = configuration["operational_database_target_expectation"]
    assert expectation["target_kind"] == db_binding.DISPOSABLE_PUBLIC_COMPOSITION_PROOF
    assert not any(key.startswith("authorization") for key in expectation)
    assert "application_marker_sha256" not in expectation


def test_owner_dispatches_dedicated_proof_binding_law_before_source_work(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    composition = _composition()
    binding = proof.build_disposable_public_composition_proof_binding(
        plan,
        execution_id="exec-c8",
        campaign_id="campaign-c8",
        campaign_run_id="run-c8",
        cycle_id="cycle-c8",
        configuration_id="config-c8",
        db_target_identity=f"sha256:{plan.pre_mutation_db_sha256}",
        fixture_composition_manifest_sha256=(
            composition.fixture_composition_manifest_sha256
        ),
    )
    expectation = db_binding.build_disposable_public_composition_proof_expectation(
        binding
    )
    fake_command = SimpleNamespace(
        db_path=plan.resolved_db_path,
        campaign_id="campaign-c8",
        run_id="run-c8",
        configuration_id="config-c8",
        db_target_identity=f"sha256:{plan.pre_mutation_db_sha256}",
    )

    reason = live_owner._validate_fifteen_minute_database_target_binding(
        command=fake_command,
        cycle_id="cycle-c8",
        selection_seed="exec-c8",
        operational_database_target_binding=None,
        disposable_public_composition_proof_binding=binding,
        durable_expectation=expectation,
        canonical_authoritative_db_path=CANONICAL_PERSISTENT_DB,
    )
    assert reason is None


def test_public_runtime_proof_selects_proof_preflight_before_production_auth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _runtime_for_red(tmp_path)

    class ProofPreflightReached(RuntimeError):
        pass

    def production_preflight_must_not_run(*args, **kwargs):
        raise AssertionError("production activation preflight used for C8 proof")

    def proof_preflight_stop(*args, **kwargs):
        raise ProofPreflightReached("proof preflight selected")

    monkeypatch.setattr(
        command,
        "build_activation_preflight",
        production_preflight_must_not_run,
    )
    monkeypatch.setattr(
        command,
        "build_disposable_public_composition_preflight",
        proof_preflight_stop,
        raising=False,
    )

    with pytest.raises(ProofPreflightReached, match="proof preflight selected"):
        command.run_operational_campaign(
            operator_approved=True,
            git_provenance_authorization=None,
            disposable_proof=runtime,
        )

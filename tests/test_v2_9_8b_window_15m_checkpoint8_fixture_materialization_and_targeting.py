from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import hashlib
import sqlite3

import pytest

from printer_v1.db.migrate import canonical_migration_count, canonical_migration_names
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli import window_15m_disposable_public_composition_proof as proof
from printer_v1.operator_cli.proof_db_schema_readiness import CANONICAL_PERSISTENT_DB
from printer_v1.operator_cli.window_15m_concrete_composition import (
    ordinary_window_15m_builder_identities,
)


class _FixtureSentinel:
    pass


def _runtime(
    tmp_path: Path,
    *,
    mark_outputs: bool,
    conflicting_route: str | None = None,
    calls: list[str] | None = None,
):
    db_path = tmp_path / "checkpoint8-materialization.sqlite3"
    db_path.write_bytes(b"checkpoint8-fixture-materialization")
    labels = ordinary_window_15m_builder_identities()
    route_plan = proof.build_disposable_public_composition_execution_bindings

    plan = proof.build_disposable_public_composition_proof_plan(
        proof_id="checkpoint8-fixture-materialization",
        db_path=db_path,
        db_sha256=hashlib.sha256(db_path.read_bytes()).hexdigest(),
        migration_count=canonical_migration_count(),
        migration_head=canonical_migration_names()[-1],
        artifact_root=tmp_path / "proof-artifacts",
        composition_labels=labels,
        provider_execution_allowed=False,
        automatic_retry_allowed=False,
        manual_rerun_allowed=False,
        resume_allowed=False,
        restart_allowed=False,
        successor_allowed=False,
    )

    # Build a temporary builder registry first so the already-GREEN execution
    # plan can tell this test which labels intentionally share an existing DI seam.
    temporary_builders = {}
    for label in labels:
        temporary_builders[label] = proof.mark_checkpoint8_fixture_builder(
            lambda label=label: {"fixture_label": label},
            label=label,
        )
    temporary_composition = proof.build_window_15m_fixture_composition(
        temporary_builders
    )
    temporary_runtime = proof.build_disposable_public_composition_proof_runtime(
        plan,
        temporary_composition,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
    )
    routes = route_plan(temporary_runtime).route_by_label

    sentinel_by_route: dict[str, _FixtureSentinel] = {}
    builders = {}
    conflict_used = False
    for label in labels:
        route = routes[label]
        sentinel = sentinel_by_route.setdefault(route, _FixtureSentinel())
        if conflicting_route == route and route in sentinel_by_route and not conflict_used:
            # First label keeps the canonical route sentinel; a later label sharing
            # the same route will get a conflicting object.
            same_route_seen = any(routes[prior] == route for prior in builders)
            if same_route_seen:
                sentinel = _FixtureSentinel()
                conflict_used = True

        def builder(label=label, sentinel=sentinel):
            if calls is not None:
                calls.append(label)
            if mark_outputs:
                return proof.mark_checkpoint8_fixture_output(
                    sentinel,
                    label=label,
                )
            return sentinel

        builders[label] = proof.mark_checkpoint8_fixture_builder(builder, label=label)

    composition = proof.build_window_15m_fixture_composition(builders)
    runtime = proof.build_disposable_public_composition_proof_runtime(
        plan,
        composition,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
    )
    return runtime, sentinel_by_route


def _raw_runtime(tmp_path: Path):
    """Runtime that does not depend on the new output-marker API."""
    db_path = tmp_path / "checkpoint8-coordinator-target.sqlite3"
    db_path.write_bytes(b"checkpoint8-coordinator-target")
    labels = ordinary_window_15m_builder_identities()
    builders = {
        label: proof.mark_checkpoint8_fixture_builder(
            lambda label=label: {"fixture_label": label},
            label=label,
        )
        for label in labels
    }
    plan = proof.build_disposable_public_composition_proof_plan(
        proof_id="checkpoint8-coordinator-target",
        db_path=db_path,
        db_sha256=hashlib.sha256(db_path.read_bytes()).hexdigest(),
        migration_count=canonical_migration_count(),
        migration_head=canonical_migration_names()[-1],
        artifact_root=tmp_path / "coordinator-artifacts",
        composition_labels=labels,
        provider_execution_allowed=False,
        automatic_retry_allowed=False,
        manual_rerun_allowed=False,
        resume_allowed=False,
        restart_allowed=False,
        successor_allowed=False,
    )
    composition = proof.build_window_15m_fixture_composition(builders)
    return proof.build_disposable_public_composition_proof_runtime(
        plan,
        composition,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
    )


def test_materialization_executes_every_builder_once_and_exposes_existing_di(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    runtime, sentinels = _runtime(
        tmp_path,
        mark_outputs=True,
        calls=calls,
    )
    materialized = proof.materialize_disposable_public_composition_execution(
        runtime
    )
    labels = ordinary_window_15m_builder_identities()
    assert calls == list(labels)
    assert tuple(materialized.outputs_by_label) == labels
    assert materialized.provider_fallback_allowed is False
    assert materialized.fixture_composition_manifest_sha256 == (
        runtime.fixture_composition_manifest_sha256
    )

    assert materialized.top_level_transports["pump_transport"] is sentinels[
        "top_level.pump_transport"
    ]
    assert materialized.top_level_transports["secondary_transport"] is sentinels[
        "top_level.secondary_transport"
    ]
    assert materialized.top_level_transports["migration_transport"] is sentinels[
        "top_level.migration_transport"
    ]

    graduated = materialized.graduated_supply_kwargs
    assert graduated["verifier_transport_factory"] is sentinels[
        "graduated_supply.verifier_transport_factory"
    ]
    assert graduated["locator_transport"] is sentinels[
        "graduated_supply.locator_transport"
    ]
    assert graduated["dexscreener_batch_transport_factory"] is sentinels[
        "graduated_supply.dexscreener_batch_transport_factory"
    ]
    assert graduated["geckoterminal_nomination_transport"] is sentinels[
        "graduated_supply.geckoterminal_nomination_transport"
    ]
    assert graduated["geckoterminal_reconciliation_transport_factory"] is sentinels[
        "graduated_supply.geckoterminal_reconciliation_transport_factory"
    ]

    lifecycle = materialized.lifecycle_kwargs
    assert lifecycle["snapshot_adapter_factory"] is sentinels[
        "lifecycle.snapshot_adapter_factory"
    ]
    assert lifecycle["fallback_snapshot_adapter_factory"] is sentinels[
        "lifecycle.fallback_snapshot_adapter_factory"
    ]
    context = lifecycle["context_adapter_factories"]
    assert context["coingecko"] is sentinels[
        "lifecycle.context_adapter_factories.coingecko"
    ]
    assert context["goplus"] is sentinels[
        "lifecycle.context_adapter_factories.goplus"
    ]
    assert context["jupiter_quote"] is sentinels[
        "lifecycle.context_adapter_factories.jupiter_quote"
    ]
    assert context["solana_rpc_holder"] is sentinels[
        "lifecycle.context_adapter_factories.solana_rpc_holder"
    ]
    assert context["helius_holder_backup"] is sentinels[
        "lifecycle.context_adapter_factories.helius_holder_backup"
    ]


def test_materialization_rejects_unmarked_fixture_output(tmp_path: Path) -> None:
    runtime, _ = _runtime(tmp_path, mark_outputs=False)
    with pytest.raises(
        proof.DisposablePublicCompositionProofError,
        match="FIXTURE_OUTPUT_NOT_EXPLICIT",
    ):
        proof.materialize_disposable_public_composition_execution(runtime)


def test_materialization_rejects_conflicting_outputs_for_shared_existing_seam(
    tmp_path: Path,
) -> None:
    runtime, _ = _runtime(
        tmp_path,
        mark_outputs=True,
        conflicting_route="lifecycle.context_adapter_factories.jupiter_quote",
    )
    with pytest.raises(
        proof.DisposablePublicCompositionProofError,
        match="FIXTURE_ROUTE_OUTPUT_CONFLICT",
    ):
        proof.materialize_disposable_public_composition_execution(runtime)


def test_prepared_execution_binds_disposable_targets_and_materialized_di(
    tmp_path: Path,
) -> None:
    runtime, _ = _runtime(tmp_path, mark_outputs=True)
    prepared = command._prepare_disposable_public_composition_execution(runtime)
    assert prepared.db_path == Path(runtime.plan.resolved_db_path).resolve()
    assert prepared.artifact_root == Path(
        runtime.plan.resolved_artifact_root
    ).resolve()
    assert prepared.materialized.provider_fallback_allowed is False
    assert prepared.materialized.fixture_composition_manifest_sha256 == (
        runtime.fixture_composition_manifest_sha256
    )


def test_artifact_paths_accept_exact_disposable_root(tmp_path: Path) -> None:
    root = (tmp_path / "c8-artifacts").resolve()
    paths = command._artifact_paths("exec-c8", artifact_root=root)
    assert paths["root"] == root / "exec-c8"
    assert paths["reports"] == root / "exec-c8" / "reports"
    assert paths["backup"].parent == root / "exec-c8"
    assert paths["lock"].parent == root / "exec-c8"


def test_read_only_accepts_exact_explicit_proof_target(tmp_path: Path) -> None:
    db_path = tmp_path / "read-only-proof.sqlite3"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("CREATE TABLE proof_row(id INTEGER PRIMARY KEY)")
        connection.commit()
    finally:
        connection.close()

    reader = command._read_only(db_path, expected_path=db_path)
    try:
        assert reader.execute("SELECT COUNT(*) FROM proof_row").fetchone()[0] == 0
        with pytest.raises(sqlite3.OperationalError):
            reader.execute("INSERT INTO proof_row DEFAULT VALUES")
    finally:
        reader.close()


def test_public_proof_skips_authorization_projection_and_uses_disposable_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _raw_runtime(tmp_path)
    proof_db = Path(runtime.plan.resolved_db_path).resolve()
    prepared = SimpleNamespace(
        db_path=proof_db,
        artifact_root=Path(runtime.plan.resolved_artifact_root).resolve(),
        materialized=SimpleNamespace(provider_fallback_allowed=False),
    )
    monkeypatch.setattr(
        command,
        "_prepare_disposable_public_composition_execution",
        lambda candidate: prepared,
        raising=False,
    )
    monkeypatch.setattr(
        command,
        "build_disposable_public_composition_preflight",
        lambda candidate: {
            "database_path": str(proof_db),
            "database_sha256": runtime.plan.pre_mutation_db_sha256,
            "migration_count": runtime.plan.migration_count,
            "latest_migration": runtime.plan.migration_head,
            "git_provenance": {},
        },
    )

    from printer_v1.operator_cli import action_local_terminal_truth
    from printer_v1.operator_cli import operational_database_target_binding as db_binding

    def authorization_projection_must_not_run(value):
        raise AssertionError("production authorization projection reached in C8 proof mode")

    monkeypatch.setattr(
        db_binding,
        "validated_authorization_runtime_facts",
        authorization_projection_must_not_run,
    )

    class _StopAtBaseline(RuntimeError):
        pass

    observed: dict[str, Path] = {}

    def stop_at_baseline(path):
        observed["path"] = Path(path).resolve()
        raise _StopAtBaseline

    monkeypatch.setattr(
        action_local_terminal_truth,
        "capture_action_local_baseline",
        stop_at_baseline,
    )

    with pytest.raises(_StopAtBaseline):
        command.run_operational_campaign(
            operator_approved=True,
            disposable_proof=runtime,
        )
    assert observed["path"] == proof_db

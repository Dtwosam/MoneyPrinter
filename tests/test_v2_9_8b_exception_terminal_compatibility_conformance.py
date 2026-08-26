from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import threading

from printer_v1.operator_cli import operational_memory_factory_command as command_module


def _command(tmp_path):
    return SimpleNamespace(
        db_path=tmp_path / "unused.sqlite3",
        campaign_id="campaign-1",
        run_id="run-1",
        supervision_id="supervision-1",
        configuration_id="configuration-1",
        policy_version="policy-1",
    )


def _patch_temporal_owner_dependencies(monkeypatch):
    from printer_v1.discovery import pre_lifecycle_refresh_composition as composition
    from printer_v1.operator_cli import authoritative_live_operational_campaign as live

    monkeypatch.setattr(
        live,
        "operational_discovery_batch_identity_inputs",
        lambda: ({"source": "v1"}, "git-identity"),
    )
    monkeypatch.setattr(
        composition,
        "build_pre_lifecycle_refresh_stage",
        lambda **_kwargs: (lambda **_stage_kwargs: {}),
    )
    monkeypatch.setattr(
        composition,
        "build_cycle_discovery_batch_resolver",
        lambda **_kwargs: (lambda _connection, _cutoff, _ordinal: "batch-1"),
    )


def test_pre_lifecycle_owner_accepts_heartbeat_without_optional_failure_event(
    tmp_path, monkeypatch
) -> None:
    _patch_temporal_owner_dependencies(monkeypatch)
    heartbeat_without_abort_event = SimpleNamespace()

    owner = command_module._build_pre_lifecycle_temporal_refresh_owner(
        command=_command(tmp_path),
        cycle_id="cycle-1",
        cycle_cutoff="2026-08-25T12:15:00+00:00",
        evaluated_at="2026-08-25T12:00:00+00:00",
        execution_id="execution-1",
        acquisition_seconds=60,
        lifecycle_duration_seconds=900,
        heartbeat=heartbeat_without_abort_event,
        cancellation_probe=lambda: None,
    )

    assert owner._abort_event is None
    assert owner._supervision() == (True, False)


def test_pre_lifecycle_owner_preserves_real_heartbeat_failure_event(
    tmp_path, monkeypatch
) -> None:
    _patch_temporal_owner_dependencies(monkeypatch)
    event = threading.Event()

    owner = command_module._build_pre_lifecycle_temporal_refresh_owner(
        command=_command(tmp_path),
        cycle_id="cycle-1",
        cycle_cutoff="2026-08-25T12:15:00+00:00",
        evaluated_at="2026-08-25T12:00:00+00:00",
        execution_id="execution-1",
        acquisition_seconds=60,
        lifecycle_duration_seconds=900,
        heartbeat=SimpleNamespace(failure_event=event),
        cancellation_probe=lambda: None,
    )

    assert owner._abort_event is event
    event.set()
    assert owner._supervision() == (False, False)


def test_factory_proof_cycle_identity_is_initialized_before_outer_exception_owner() -> None:
    path = Path("src/printer_v1/operator_cli/one_command_15m_factory.py")
    module = ast.parse(path.read_text(encoding="utf-8"))
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "run_one_command_15m_factory"
    )

    assignments = []
    reads_in_handlers = []
    for node in ast.walk(function):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(
                isinstance(target, ast.Name) and target.id == "owned_proof_cycle_id"
                for target in targets
            ):
                assignments.append(node.lineno)
        if isinstance(node, ast.ExceptHandler):
            if any(
                isinstance(child, ast.Name)
                and child.id == "owned_proof_cycle_id"
                and isinstance(child.ctx, ast.Load)
                for child in ast.walk(node)
            ):
                reads_in_handlers.append(node.lineno)

    opening_calls = [
        node.lineno
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_plan_opening_jobs"
    ]

    assert assignments, "factory must initialize owned_proof_cycle_id"
    assert opening_calls, "regression must cover opening planning"
    assert reads_in_handlers, "regression must cover the exception owner that reads it"
    assert min(assignments) < min(opening_calls) < min(reads_in_handlers)

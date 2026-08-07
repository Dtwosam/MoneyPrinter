from __future__ import annotations

import inspect

import pytest

from printer_v1.operator_cli import operational_memory_factory_command as command


def test_proof_rejects_external_transport_overrides_before_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def preflight_must_not_run(*args, **kwargs):
        raise AssertionError("proof preflight reached before external transport gate")

    monkeypatch.setattr(
        command,
        "build_disposable_public_composition_preflight",
        preflight_must_not_run,
    )

    with pytest.raises(
        command.OperationalMemoryFactoryError,
        match="DISPOSABLE_PROOF_EXTERNAL_TRANSPORT_OVERRIDE_FORBIDDEN",
    ):
        command.run_operational_campaign(
            operator_approved=True,
            disposable_proof=object(),
            pump_transport=object(),
        )


def test_public_coordinator_has_no_owner_invocation_stop() -> None:
    source = inspect.getsource(command._run_operational_campaign)
    assert "DISPOSABLE_PROOF_OWNER_INVOCATION_NOT_YET_PROVEN" not in source


def test_proof_path_backs_up_exact_active_disposable_db() -> None:
    source = inspect.getsource(command._run_operational_campaign)
    assert "operational_backup_restore_preflight(\n        active_db," in source
    assert "expected_source_path=active_db" in source


def test_proof_path_creates_campaign_with_proof_binding_and_active_db() -> None:
    source = inspect.getsource(command._run_operational_campaign)
    assert "disposable_proof_binding=(" in source
    assert "owner_bridge.proof_binding" in source
    assert "db_path=active_db" in source


def test_proof_path_cannot_fall_back_to_production_runtime_constructors() -> None:
    source = inspect.getsource(command._run_operational_campaign)
    assert "if owner_bridge is None:" in source
    assert "active_pump = owner_bridge.pump_transport" in source
    assert "active_secondary = owner_bridge.secondary_transport" in source
    assert "active_migration = owner_bridge.migration_transport" in source
    assert "resolve_solana_rpc_configuration()" in source
    assert "production_runtime_default_constructors(" in source


def test_authoritative_owner_call_consumes_exact_proof_bridge_inputs() -> None:
    source = inspect.getsource(command._run_operational_campaign)
    assert "bridge_lifecycle_kwargs" in source
    assert "bridge_graduated_supply_kwargs" in source
    assert "graduated_supply_kwargs=bridge_graduated_supply_kwargs" in source
    assert "migration_transport=active_migration" in source
    assert "disposable_public_composition_proof_binding=(" in source
    assert "owner_bridge.disposable_public_composition_proof_binding" in source
    assert "operational_database_target_binding=(" in source

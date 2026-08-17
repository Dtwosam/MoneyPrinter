from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import inspect

import pytest

import printer_v1.discovery.pre_lifecycle_refresh_composition as refresh_composition
import printer_v1.operator_cli.authoritative_live_operational_campaign as live_campaign
import printer_v1.operator_cli.operational_memory_factory_command as operational
from printer_v1.operator_cli.later_cycle_graduated_supply import (
    LaterCycleGraduatedSupplyError,
    build_later_cycle_graduated_supply,
)
from printer_v1.operator_cli.pre_lifecycle_persistent_refresh_owner import (
    PreLifecycleTemporalRefreshError,
    PreLifecycleTemporalRefreshOwner,
)


class Port:
    def __init__(self, kind):
        self.owner_kind = kind
        self.available = True


def _raw_owner(tmp_path: Path, *, rebinder=None, acquisition_deadline='2026-08-17T00:40:00+00:00', work_deadline='2026-08-17T04:45:00+00:00'):
    return PreLifecycleTemporalRefreshOwner(
        tmp_path / 'db.sqlite3',
        campaign_id='campaign-a', run_id='run-a', cycle_id='cycle-1',
        supervision_id='supervision-a',
        source_governor=Port('SOURCE_GOVERNOR'),
        central_scheduler=Port('CENTRAL_SCHEDULER'),
        acquisition_deadline_at=acquisition_deadline,
        work_deadline_at=work_deadline,
        refresh_stage=lambda *a, **k: {},
        discovery_batch_resolver=lambda *a, **k: 'batch-1',
        refresh_interval_seconds=600,
        cycle_rebinder=rebinder,
    )


def test_cycle_rebind_fails_closed_without_canonical_rebuilder(tmp_path):
    owner = _raw_owner(tmp_path)
    with pytest.raises(
        PreLifecycleTemporalRefreshError,
        match='TEMPORAL_CYCLE_REBINDER_NOT_CONFIGURED',
    ):
        owner.for_cycle(
            cycle_id='cycle-2',
            cycle_cutoff='2026-08-17T00:05:00+00:00',
            evaluated_at='2026-08-17T00:05:01+00:00',
            request_key_prefix='cycle-2-request-root',
        )


def test_canonical_builder_rebinds_cycle_scope_but_preserves_campaign_seed(monkeypatch, tmp_path):
    stage_calls = []
    resolver_calls = []

    def fake_stage(**kwargs):
        stage_calls.append(dict(kwargs))
        return lambda *a, **k: {}

    def fake_resolver(**kwargs):
        resolver_calls.append(dict(kwargs))
        return lambda *a, **k: 'batch'

    monkeypatch.setattr(
        refresh_composition, 'build_pre_lifecycle_refresh_stage', fake_stage
    )
    monkeypatch.setattr(
        refresh_composition, 'build_cycle_discovery_batch_resolver', fake_resolver
    )
    monkeypatch.setattr(
        live_campaign,
        'operational_discovery_batch_identity_inputs',
        lambda: ({'direct': 'v1'}, 'git-id'),
    )

    command = SimpleNamespace(
        db_path=tmp_path / 'db.sqlite3',
        campaign_id='campaign-a',
        run_id='run-a',
        supervision_id='supervision-a',
        configuration_id='configuration-a',
        policy_version='policy-a',
    )
    owner = operational._build_pre_lifecycle_temporal_refresh_owner(
        command=command,
        cycle_id='cycle-1',
        cycle_cutoff='2026-08-17T00:00:00+00:00',
        evaluated_at='2026-08-17T00:00:00+00:00',
        execution_id='campaign-selection-seed',
        acquisition_seconds=2400,
        lifecycle_duration_seconds=14700,
        heartbeat=None,
        cancellation_probe=lambda: None,
    )
    initial_work_deadline = owner.work_deadline_at
    assert stage_calls[-1]['request_key_prefix'] == 'campaign-selection-seed'
    assert resolver_calls[-1]['campaign_selection_seed'] == 'campaign-selection-seed'
    assert resolver_calls[-1]['cycle_id'] == 'cycle-1'

    rebound = owner.for_cycle(
        cycle_id='cycle-2',
        cycle_cutoff='2026-08-17T00:05:00+00:00',
        evaluated_at='2026-08-17T00:05:01+00:00',
        request_key_prefix='cycle-2-source-request-root',
    )
    assert rebound.cycle_id == 'cycle-2'
    assert rebound.work_deadline_at == initial_work_deadline
    assert rebound.refresh_interval_seconds == owner.refresh_interval_seconds
    assert stage_calls[-1]['request_key_prefix'] == 'cycle-2-source-request-root'
    assert resolver_calls[-1]['cycle_id'] == 'cycle-2'
    assert resolver_calls[-1]['cycle_cutoff'] == '2026-08-17T00:05:00+00:00'
    # Selection identity stays campaign-owned. Cycle uniqueness comes from
    # cycle_id in the canonical resolver, not from the source child id.
    assert resolver_calls[-1]['campaign_selection_seed'] == 'campaign-selection-seed'


def test_cycle_rebind_rejects_deadline_beyond_original_work_envelope(tmp_path):
    original = None

    def rebind(**kwargs):
        return PreLifecycleTemporalRefreshOwner(
            original.db_path,
            campaign_id=original.campaign_id,
            run_id=original.run_id,
            cycle_id=kwargs['cycle_id'],
            supervision_id=original.supervision_id,
            source_governor=original.source_governor,
            central_scheduler=original.central_scheduler,
            acquisition_deadline_at='2026-08-17T05:00:00+00:00',
            work_deadline_at=original.work_deadline_at,
            refresh_stage=lambda *a, **k: {},
            discovery_batch_resolver=lambda *a, **k: 'batch-2',
            refresh_interval_seconds=original.refresh_interval_seconds,
            cycle_rebinder=rebind,
        )

    original = _raw_owner(tmp_path, rebinder=rebind)
    with pytest.raises(
        PreLifecycleTemporalRefreshError,
        match='TEMPORAL_CYCLE_REBINDER_DEADLINE_DRIFT',
    ):
        original.for_cycle(
            cycle_id='cycle-2',
            cycle_cutoff='2026-08-17T00:05:00+00:00',
            evaluated_at='2026-08-17T00:05:01+00:00',
            request_key_prefix='cycle-2-source-request-root',
        )


def test_later_cycle_supply_requires_complete_temporal_binding(tmp_path):
    with pytest.raises(
        LaterCycleGraduatedSupplyError,
        match='TEMPORAL_ACQUISITION_BINDING_INCOMPLETE',
    ):
        build_later_cycle_graduated_supply(
            tmp_path / 'db.sqlite3',
            campaign_id='campaign-a',
            campaign_run_id='run-a',
            authoritative_factory_run_id='factory-a',
            proposed_cycle_id='cycle-2',
            proposed_cycle_ordinal=2,
            evaluated_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
            execution_id='outer-execution',
            selection_seed='cycle-selection-seed',
            migration_transport=None,
            graduated_supply_kwargs={},
            deadline_at='2026-08-17T00:40:00+00:00',
            temporal_refresh_owner=None,
        )


def test_later_cycle_supply_rejects_temporal_owner_identity_drift(tmp_path):
    owner = _raw_owner(tmp_path)
    with pytest.raises(
        LaterCycleGraduatedSupplyError,
        match='TEMPORAL_ACQUISITION_OWNER_IDENTITY_MISMATCH',
    ):
        build_later_cycle_graduated_supply(
            tmp_path / 'db.sqlite3',
            campaign_id='campaign-a',
            campaign_run_id='run-a',
            authoritative_factory_run_id='factory-a',
            proposed_cycle_id='cycle-2',
            proposed_cycle_ordinal=2,
            evaluated_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
            execution_id='outer-execution',
            selection_seed='cycle-selection-seed',
            migration_transport=None,
            graduated_supply_kwargs={},
            deadline_at=owner.acquisition_deadline_at,
            temporal_refresh_owner=owner,
        )


def test_live_owner_uses_exact_cycle_child_source_scope_for_rebind():
    source = inspect.getsource(
        live_campaign.AuthoritativeLiveOperationalCampaignOwner.run_operational
    )
    assert 'cycle_source_execution_identity' in source
    assert 'build_campaign_source_request_scope' in source
    assert 'request_key_prefix=cycle_scope.request_key_root' in source
    assert 'deadline_at=later_cycle_deadline' in source
    assert 'temporal_refresh_owner=later_cycle_refresh_owner' in source


def test_no_safety_or_terminal_policy_is_part_of_this_implementation():
    source = inspect.getsource(
        live_campaign.AuthoritativeLiveOperationalCampaignOwner.run_operational
    )
    assert 'build_4a_authority_facts' not in source

from __future__ import annotations

from dataclasses import replace
import sqlite3

import pytest

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.four_token_factory_adapter import (
    record_started_lifecycle_zero_attempt_terminal_provenance,
)
from printer_v1.operator_cli.unified_terminal_closure import reconcile_campaign_terminal
from printer_v1.sources.governed_execution import build_fixture_source_adapter
from tests.test_v2_9_8b_four_token_factory_terminal_integration import (
    _ReadyController,
    _discovery,
)
from tests.test_v2_9_8b_four_token_factory_wake_ordering import (
    CAMPAIGN_ID,
    CAMPAIGN_RUN_ID,
    CONFIGURATION_ID,
    CYCLE_ID,
    FACTORY_RUN_ID,
    START,
    _healthy_projection,
    _prepare,
)
from tests.test_v2_9_8b_callback_consume_materialize_integration import (
    GOVERNOR,
    SCHEDULER,
)


PLANNED_ZERO_ATTEMPT_PHASE = "CYCLE1_LIFECYCLE_PLANNED_PRE_CYCLE2_ATTEMPT"
STARTED_ZERO_ATTEMPT_PHASE = "CYCLE1_LIFECYCLE_STARTED_PRE_CYCLE2_ATTEMPT"


def _lease_blocked_projection():
    projection = _healthy_projection()
    return replace(
        projection,
        health=replace(projection.health, lease_healthy=False),
        reasons=("LEASE_UNHEALTHY",),
    )


def _block_after_first_lifecycle_step(connection: sqlite3.Connection):
    """Keep admission healthy until real Cycle-1 lifecycle work has started."""
    started = int(connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
        "WHERE run_id=? AND started_at IS NOT NULL",
        (FACTORY_RUN_ID,),
    ).fetchone()[0])
    return _lease_blocked_projection() if started else _healthy_projection()


def test_started_lifecycle_provenance_rejects_unstarted_and_wrong_identity(
    tmp_path,
) -> None:
    """The new owner cannot capture a pre-lifecycle or mismatched record."""
    db, _backup, _disposable_binding = _prepare(tmp_path)
    connection = sqlite3.connect(db)
    try:
        for campaign_id in (CAMPAIGN_ID, "wrong-campaign"):
            assert not record_started_lifecycle_zero_attempt_terminal_provenance(
                connection,
                campaign_id=campaign_id,
                campaign_run_id=CAMPAIGN_RUN_ID,
                factory_run_id=FACTORY_RUN_ID,
                cycle_id=CYCLE_ID,
                cause="LEASE_UNHEALTHY",
                now=START,
            )
        assert connection.execute(
            "SELECT COUNT(*) FROM "
            "printer_four_token_started_lifecycle_zero_attempt_terminal_provenance"
        ).fetchone()[0] == 0
    finally:
        connection.close()


def test_cycle1_opening_planned_pre_attempt_health_block_terminalizes_truthfully(
    tmp_path,
) -> None:
    """A pre-attempt health stop after Cycle-1 planning is not pre-lifecycle."""
    db, backup, disposable_binding = _prepare(tmp_path)
    shared_calls: list[str] = []

    def forbidden_later_cycle_callback(**_kwargs):
        raise AssertionError("pre-attempt health block must not run Cycle-2 discovery")

    def shared_terminalizer(*, terminal_cause, run_status):
        shared_calls.append(str(terminal_cause))
        reconciled = reconcile_campaign_terminal(
  db,
  campaign_id=CAMPAIGN_ID,
  run_id=CAMPAIGN_RUN_ID,
  cycle_id=CYCLE_ID,
  terminal_cause=str(terminal_cause),
  run_status=run_status,
  factory_run_id=FACTORY_RUN_ID,
  lifecycle_started=True,
  now=START.isoformat(),
        )
        return {**reconciled, "clean_terminal": True, "lease_released": True}

    report = factory.run_one_command_15m_factory(
        db,
        backup,
        operator_approved=True,
        proof_mode=False,
        operational_persistent_mode=True,
        disposable_public_composition_proof_binding=disposable_binding,
        discovery_runner=_discovery(db),
        launch_provenance={
  "git_head": "c" * 40,
  "git_tracked_tree_clean": True,
  "git_staged_changes_present": False,
  "git_unstaged_changes_present": False,
  "git_untracked_present": True,
  "git_provenance_captured_at": START.isoformat(),
        },
        standard_four_hour_campaign=True,
        selective_1h_continuation=True,
        continuous_first_hour=True,
        continuous_four_hour=True,
        total_duration_seconds=20_000,
        _window_seconds=900,
        _continuation_seconds=3_600,
        max_selected_tokens=2,
        campaign_id=CAMPAIGN_ID,
        campaign_run_id=CAMPAIGN_RUN_ID,
        cycle_id=CYCLE_ID,
        configuration_id=CONFIGURATION_ID,
        factory_run_id=FACTORY_RUN_ID,
        four_token_proof_controller=_ReadyController(),
        later_cycle_discovery_callback=forbidden_later_cycle_callback,
        four_token_health_projector=lambda _connection, _now: _lease_blocked_projection(),
        four_token_shared_terminalizer=shared_terminalizer,
        source_governor_owner=GOVERNOR,
        central_scheduler_owner=SCHEDULER,
        _sleep=lambda _seconds: None,
        _monotonic=lambda: 0.0,
    )

    connection = sqlite3.connect(db)
    try:
        assert connection.execute(
  "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts "
  "WHERE campaign_id=? AND campaign_run_id=? "
  "AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=2",
  (CAMPAIGN_ID, CAMPAIGN_RUN_ID, FACTORY_RUN_ID),
        ).fetchone()[0] == 0
        provenance = connection.execute(
  "SELECT terminal_phase,first_terminal_cause "
  "FROM printer_four_token_zero_attempt_terminal_provenance "
  "WHERE campaign_id=? AND campaign_run_id=? "
  "AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=2",
  (CAMPAIGN_ID, CAMPAIGN_RUN_ID, FACTORY_RUN_ID),
        ).fetchone()
        assert provenance == (PLANNED_ZERO_ATTEMPT_PHASE, "LEASE_UNHEALTHY")
        assert connection.execute(
  "SELECT COUNT(*) FROM printer_four_token_started_lifecycle_zero_attempt_terminal_provenance "
  "WHERE campaign_id=? AND campaign_run_id=? "
  "AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=2",
  (CAMPAIGN_ID, CAMPAIGN_RUN_ID, FACTORY_RUN_ID),
        ).fetchone()[0] == 0
        windows = connection.execute(
  "SELECT window_kind,window_state,first_terminal_cause "
  "FROM printer_memory_factory_campaign_windows "
  "WHERE campaign_id=? AND run_id=? AND cycle_id=? ORDER BY window_id",
  (CAMPAIGN_ID, CAMPAIGN_RUN_ID, CYCLE_ID),
        ).fetchall()
        assert windows == [
  ("WINDOW_15M", "CANCELLED", "LEASE_UNHEALTHY"),
  ("WINDOW_15M", "CANCELLED", "LEASE_UNHEALTHY"),
        ]
        steps = connection.execute(
  "SELECT step_status,started_at FROM printer_memory_factory_run_steps "
  "WHERE run_id=? ORDER BY id",
  (FACTORY_RUN_ID,),
        ).fetchall()
        assert steps == [("CANCELLED", None), ("CANCELLED", None)]
        assert connection.execute(
  "SELECT COUNT(*) FROM printer_source_requests WHERE request_key LIKE ?",
  (f"{FACTORY_RUN_ID}:%",),
        ).fetchone()[0] == 0
    finally:
        connection.close()

    assert shared_calls == ["LEASE_UNHEALTHY"]
    assert report["stop_reason"] == "LEASE_UNHEALTHY"
    assert report["four_token_terminal"]["admitted_shape"] == (
        "ONE_CYCLE_LIFECYCLE_PLANNED_ZERO_ATTEMPT"
    )
    assert report["four_token_terminal"]["shared_cleanup_count"] == 1


def test_external_stop_during_opening_transaction_releases_it_before_planned_provenance(
    tmp_path, monkeypatch
) -> None:
    """An interrupted opening write cannot leak into planned terminal provenance."""
    db, backup, disposable_binding = _prepare(tmp_path)

    def interrupted_health(connection, _now):
        # Cycle-1 opening ownership has already committed. The admission
        # boundary then owns this update when the cooperative stop arrives.
        connection.execute(
            "UPDATE printer_memory_factory_runs SET updated_at=updated_at WHERE run_id=?",
            (FACTORY_RUN_ID,),
        )
        assert connection.in_transaction
        raise factory._ExternalStop("LEASE_RENEWAL_SQLITE_LOCKED")

    def shared_terminalizer(*, terminal_cause, run_status):
        reconciled = reconcile_campaign_terminal(
            db,
            campaign_id=CAMPAIGN_ID,
            run_id=CAMPAIGN_RUN_ID,
            cycle_id=CYCLE_ID,
            terminal_cause=str(terminal_cause),
            run_status=run_status,
            factory_run_id=FACTORY_RUN_ID,
            lifecycle_started=False,
            now=START.isoformat(),
        )
        return {**reconciled, "clean_terminal": True, "lease_released": True}

    report = factory.run_one_command_15m_factory(
        db, backup, operator_approved=True, proof_mode=False,
        operational_persistent_mode=True,
        disposable_public_composition_proof_binding=disposable_binding,
        discovery_runner=_discovery(db),
        launch_provenance={
            "git_head": "c" * 40, "git_tracked_tree_clean": True,
            "git_staged_changes_present": False, "git_unstaged_changes_present": False,
            "git_untracked_present": True, "git_provenance_captured_at": START.isoformat(),
        },
        standard_four_hour_campaign=True, selective_1h_continuation=True,
        continuous_first_hour=True, continuous_four_hour=True,
        total_duration_seconds=20_000, _window_seconds=900, _continuation_seconds=3_600,
        max_selected_tokens=2, campaign_id=CAMPAIGN_ID,
        campaign_run_id=CAMPAIGN_RUN_ID, cycle_id=CYCLE_ID,
        configuration_id=CONFIGURATION_ID, factory_run_id=FACTORY_RUN_ID,
        four_token_proof_controller=_ReadyController(),
        later_cycle_discovery_callback=lambda **_kwargs: None,
        four_token_health_projector=interrupted_health,
        four_token_shared_terminalizer=shared_terminalizer,
        source_governor_owner=GOVERNOR, central_scheduler_owner=SCHEDULER,
        _sleep=lambda _seconds: None, _monotonic=lambda: 0.0,
    )

    connection = sqlite3.connect(db)
    try:
        assert connection.execute(
            "SELECT terminal_phase,first_terminal_cause FROM "
            "printer_four_token_zero_attempt_terminal_provenance "
            "WHERE campaign_id=? AND campaign_run_id=? "
            "AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=2",
            (CAMPAIGN_ID, CAMPAIGN_RUN_ID, FACTORY_RUN_ID),
        ).fetchone() == (
            PLANNED_ZERO_ATTEMPT_PHASE, "LEASE_RENEWAL_SQLITE_LOCKED"
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_four_token_started_lifecycle_zero_attempt_terminal_provenance"
        ).fetchone()[0] == 0
    finally:
        connection.close()

    assert report["stop_reason"] == "LEASE_RENEWAL_SQLITE_LOCKED"


def test_started_cycle1_lifecycle_block_has_its_own_zero_attempt_terminal_truth(
    tmp_path,
) -> None:
    """A started Cycle-1 lifecycle cannot be misclassified as unstarted or pre-lifecycle."""
    db, backup, disposable_binding = _prepare(tmp_path)
    shared_calls: list[str] = []

    def forbidden_later_cycle_callback(**_kwargs):
        raise AssertionError("started Cycle-1 block must not run Cycle-2 discovery")

    def shared_terminalizer(*, terminal_cause, run_status):
        shared_calls.append(str(terminal_cause))
        reconciled = reconcile_campaign_terminal(
            db,
            campaign_id=CAMPAIGN_ID,
            run_id=CAMPAIGN_RUN_ID,
            cycle_id=CYCLE_ID,
            terminal_cause=str(terminal_cause),
            run_status=run_status,
            factory_run_id=FACTORY_RUN_ID,
            lifecycle_started=True,
            now=START.isoformat(),
        )
        return {**reconciled, "clean_terminal": True, "lease_released": True}

    def snapshot_factory(*, token_mint, timeout_seconds):
        del timeout_seconds
        pool = "pool-1" if token_mint == "mint-1" else "pool-2"
        return build_fixture_source_adapter(
            "dexscreener",
            fixture_payload={"pairs": [{
                "chain": "solana",
                "token_mint": token_mint,
                "pair_address": pool,
                "price_usd": 1.0,
                "liquidity_usd": 10_000.0,
                "volume_5m": 10.0,
                "volume_1h": 20.0,
                "volume_24h": 30.0,
                "txns_5m": 2,
                "txns_1h": 4,
                "txns_24h": 6,
                "buys_5m": 1,
                "sells_5m": 1,
                "buys_1h": 2,
                "sells_1h": 2,
                "buys_24h": 3,
                "sells_24h": 3,
                "price_change_5m": 0.0,
                "price_change_1h": 0.0,
                "price_change_24h": 0.0,
            }]},
        )

    report = factory.run_one_command_15m_factory(
        db,
        backup,
        operator_approved=True,
        proof_mode=False,
        operational_persistent_mode=True,
        disposable_public_composition_proof_binding=disposable_binding,
        discovery_runner=_discovery(db),
        launch_provenance={
            "git_head": "c" * 40,
            "git_tracked_tree_clean": True,
            "git_staged_changes_present": False,
            "git_unstaged_changes_present": False,
            "git_untracked_present": True,
            "git_provenance_captured_at": START.isoformat(),
        },
        standard_four_hour_campaign=True,
        selective_1h_continuation=True,
        continuous_first_hour=True,
        continuous_four_hour=True,
        total_duration_seconds=20_000,
        _window_seconds=900,
        _continuation_seconds=3_600,
        max_selected_tokens=2,
        campaign_id=CAMPAIGN_ID,
        campaign_run_id=CAMPAIGN_RUN_ID,
        cycle_id=CYCLE_ID,
        configuration_id=CONFIGURATION_ID,
        factory_run_id=FACTORY_RUN_ID,
        four_token_proof_controller=_ReadyController(),
        later_cycle_discovery_callback=forbidden_later_cycle_callback,
        four_token_health_projector=lambda connection, _now: (
            _block_after_first_lifecycle_step(connection)
        ),
        four_token_shared_terminalizer=shared_terminalizer,
        source_governor_owner=GOVERNOR,
        central_scheduler_owner=SCHEDULER,
        snapshot_adapter_factory=snapshot_factory,
        _sleep=lambda _seconds: None,
        _monotonic=lambda: 0.0,
    )

    connection = sqlite3.connect(db)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND started_at IS NOT NULL",
            (FACTORY_RUN_ID,),
        ).fetchone()[0] >= 1
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts "
            "WHERE campaign_id=? AND campaign_run_id=? "
            "AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=2",
            (CAMPAIGN_ID, CAMPAIGN_RUN_ID, FACTORY_RUN_ID),
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_four_token_zero_attempt_terminal_provenance "
            "WHERE campaign_id=? AND campaign_run_id=? "
            "AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=2",
            (CAMPAIGN_ID, CAMPAIGN_RUN_ID, FACTORY_RUN_ID),
        ).fetchone()[0] == 0
        provenance = connection.execute(
            "SELECT terminal_phase,first_terminal_cause "
            "FROM printer_four_token_started_lifecycle_zero_attempt_terminal_provenance "
            "WHERE campaign_id=? AND campaign_run_id=? "
            "AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=2",
            (CAMPAIGN_ID, CAMPAIGN_RUN_ID, FACTORY_RUN_ID),
        ).fetchone()
        assert provenance == (STARTED_ZERO_ATTEMPT_PHASE, "LEASE_UNHEALTHY")
        with pytest.raises(sqlite3.IntegrityError, match="provenance is immutable"):
            connection.execute(
                "UPDATE printer_four_token_started_lifecycle_zero_attempt_terminal_provenance "
                "SET first_terminal_cause='OTHER' WHERE campaign_id=?",
                (CAMPAIGN_ID,),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="provenance is immutable"):
            connection.execute(
                "DELETE FROM printer_four_token_started_lifecycle_zero_attempt_terminal_provenance "
                "WHERE campaign_id=?",
                (CAMPAIGN_ID,),
            )
        connection.rollback()
    finally:
        connection.close()

    assert shared_calls == ["LEASE_UNHEALTHY"]
    assert report["four_token_terminal"]["admitted_shape"] == (
        "ONE_CYCLE_LIFECYCLE_STARTED_ZERO_ATTEMPT"
    )
    assert report["four_token_terminal"]["shared_cleanup_count"] == 1

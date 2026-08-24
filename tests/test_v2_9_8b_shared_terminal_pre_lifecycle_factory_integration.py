from __future__ import annotations

import json
import sqlite3

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    LaterCycleCandidateSupply,
    LaterCycleSourceEvidence,
)
from printer_v1.operator_cli.unified_terminal_closure import reconcile_campaign_terminal
from tests.test_v2_9_8b_callback_consume_materialize_integration import (
    GOVERNOR,
    SCHEDULER,
)
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


def test_real_factory_opening_failure_records_pre_lifecycle_zero_attempt_shape(
    tmp_path, monkeypatch
) -> None:
    db, backup, disposable_binding = _prepare(tmp_path)

    def fail_opening(*_args, **_kwargs):
        raise RuntimeError("injected pre-lifecycle opening failure")

    monkeypatch.setattr(factory, "_plan_opening_jobs", fail_opening)
    shared_calls: list[tuple[str, str | None]] = []

    def shared_terminalizer(*, terminal_cause, run_status):
        shared_calls.append((str(terminal_cause), run_status))
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
        later_cycle_discovery_callback=lambda **_: None,
        four_token_health_projector=lambda _connection, _now: _healthy_projection(),
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
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_four_token_pre_lifecycle_terminal_provenance "
            "WHERE campaign_id=? AND campaign_run_id=? "
            "AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=2",
            (CAMPAIGN_ID, CAMPAIGN_RUN_ID, FACTORY_RUN_ID),
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT cycle_state FROM printer_memory_factory_campaign_cycles "
            "WHERE campaign_id=? AND run_id=? AND cycle_id=?",
            (CAMPAIGN_ID, CAMPAIGN_RUN_ID, CYCLE_ID),
        ).fetchone()[0].startswith("TERMINAL_")
    finally:
        connection.close()

    assert report["four_token_terminal"]["admitted_shape"] == (
        "ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT"
    )
    assert report["four_token_terminal"]["phase_a"][0][
        "pre_lifecycle_zero_attempt_provenance_recorded"
    ] is True
    assert len(shared_calls) == 1


def test_real_cycle2_pre_admission_persistence_failure_terminalizes_once(
    tmp_path, monkeypatch
) -> None:
    db, backup, disposable_binding = _prepare(tmp_path)
    monkeypatch.setattr(factory, "_plan_opening_jobs", lambda *args, **kwargs: None)

    valid_evidence = LaterCycleSourceEvidence(
        logical_stage="ELIGIBLE_SUPPLY",
        source_request_id=1,
        source_response_id=1,
    )
    invalid_evidence = LaterCycleSourceEvidence(
        logical_stage="ELIGIBLE_SUPPLY",
        source_request_id=1,
        source_response_id=999_999,
    )
    later_callback = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=lambda **_: LaterCycleCandidateSupply(
            candidates=(),
            source_evidence=(valid_evidence, invalid_evidence),
            terminal_cause="NO_EXACT_PAIR",
        )
    )._build_later_cycle_discovery_callback(
        db_path=db,
        configuration_id=CONFIGURATION_ID,
    )
    shared_calls: list[tuple[str, str | None]] = []

    def shared_terminalizer(*, terminal_cause, run_status):
        shared_calls.append((str(terminal_cause), run_status))
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
        later_cycle_discovery_callback=later_callback,
        four_token_health_projector=lambda _connection, _now: _healthy_projection(),
        four_token_shared_terminalizer=shared_terminalizer,
        source_governor_owner=GOVERNOR,
        central_scheduler_owner=SCHEDULER,
        _sleep=lambda _seconds: None,
        _monotonic=lambda: 0.0,
    )

    connection = sqlite3.connect(db)
    try:
        assert connection.execute(
            "SELECT attempt_state,first_terminal_cause,consumed_cycle_id "
            "FROM printer_pre_admission_discovery_attempts"
        ).fetchall() == [
            ("FAILED", "LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED", None)
        ]
        assert connection.execute(
            "SELECT cycle_ordinal,cycle_state,first_terminal_cause "
            "FROM printer_memory_factory_campaign_cycles ORDER BY cycle_ordinal"
        ).fetchall() == [
            (1, "TERMINAL_BLOCKED", "LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED")
        ]
        assert connection.execute(
            "SELECT run_state,first_terminal_cause "
            "FROM printer_memory_factory_campaign_runs"
        ).fetchone() == (
            "TERMINAL_BLOCKED",
            "LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED",
        )
        assert connection.execute(
            "SELECT run_status,stop_reason FROM printer_memory_factory_runs"
        ).fetchone() == (
            "SAFE_STOPPED",
            "LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED",
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_runs"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs "
            "WHERE status IN ('PENDING','RUNNING','COOLDOWN') "
            "OR locked_at IS NOT NULL OR lock_owner IS NOT NULL"
        ).fetchone()[0] == 0
        diagnostic = json.loads(
            connection.execute(
                "SELECT last_error FROM printer_scheduler_jobs"
            ).fetchone()[0]
        )
        assert diagnostic == {
            "diagnostic_schema": "PRE_ADMISSION_PERSISTENCE_DIAGNOSTIC_V1",
            "exception_type": "IntegrityError",
            "failure_category": "CONSTRAINT_OR_INTEGRITY",
            "failure_code": "LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED",
            "operation_phase": "SOURCE_LINK",
            "producer_code": "SOURCE_EVIDENCE_LINK_INSERT",
            "reason_code": "SQLITE_CONSTRAINT_TRIGGER",
        }
    finally:
        connection.close()

    terminal = report["four_token_terminal"]
    assert terminal["admitted_shape"] == "ONE_CYCLE_HONEST_NO_ADMISSION"
    assert len(terminal["phase_a"]) == 1
    assert terminal["terminal_accounting"] is None
    assert terminal["shared_cleanup_count"] == 1
    assert terminal["shared_evidence"]["clean_terminal"] is True
    assert terminal["shared_evidence"]["lease_released"] is True
    assert shared_calls == [
        ("LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED", "SAFE_STOPPED")
    ]

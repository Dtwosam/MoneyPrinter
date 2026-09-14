"""Factory connection ownership regressions; disposable DBs and no transport."""
from __future__ import annotations

from contextlib import closing
import json
import sqlite3

import pytest

from printer_v1.db import sqlite_write_contracts
from printer_v1.operator_cli import four_token_factory_adapter as terminal
from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.unified_terminal_closure import reconcile_campaign_terminal
from tests.test_v2_9_8b_callback_consume_materialize_integration import GOVERNOR, SCHEDULER
from tests.test_v2_9_8b_four_token_factory_terminal_integration import _ReadyController, _discovery
from tests.test_v2_9_8b_four_token_factory_wake_ordering import (
    CAMPAIGN_ID, CAMPAIGN_RUN_ID, CONFIGURATION_ID, CYCLE_ID,
    FACTORY_RUN_ID, START, _prepare,
)


class ObservedConnection(sqlite3.Connection):
    close_count = 0
    rollback_count = 0

    def rollback(self):
        self.rollback_count += 1
        return super().rollback()

    def close(self):
        self.close_count += 1
        return super().close()


@pytest.fixture
def factory_case(tmp_path, monkeypatch):
    db, backup, binding = _prepare(tmp_path)
    opened = []
    original_connect = sqlite_write_contracts.connect_attributed

    def connect(path, **kwargs):
        if kwargs.get("connection_role") != "FACTORY_MAIN":
            return original_connect(path, **kwargs)
        assert path.resolve() == db.resolve()
        connection = sqlite3.connect(path, factory=ObservedConnection)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite_write_contracts, "connect_attributed", connect)

    def shared_terminalizer(*, terminal_cause, run_status):
        result = reconcile_campaign_terminal(
            db, campaign_id=CAMPAIGN_ID, run_id=CAMPAIGN_RUN_ID,
            cycle_id=CYCLE_ID, terminal_cause=str(terminal_cause),
            run_status=run_status, factory_run_id=FACTORY_RUN_ID,
            lifecycle_started=False, now=START.isoformat(),
        )
        return {**result, "clean_terminal": True, "lease_released": True}

    def run(interruption):
        def interrupt_open_write(connection, _now):
            connection.execute(
                "UPDATE printer_memory_factory_runs SET updated_at=? WHERE run_id=?",
                ("INTERRUPTED_UNCOMMITTED_WRITE", FACTORY_RUN_ID),
            )
            assert connection.in_transaction
            raise interruption

        return factory.run_one_command_15m_factory(
            db, backup, operator_approved=True, proof_mode=False,
            operational_persistent_mode=True,
            disposable_public_composition_proof_binding=binding,
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
            four_token_health_projector=interrupt_open_write,
            four_token_shared_terminalizer=shared_terminalizer,
            source_governor_owner=GOVERNOR, central_scheduler_owner=SCHEDULER,
            _sleep=lambda _seconds: None, _monotonic=lambda: 0.0,
        )

    yield db, opened, run
    # A failing pre-fix test must not itself strand a disposable write handle.
    for connection in opened:
        sqlite3.Connection.close(connection)


def assert_released(db, opened):
    assert len(opened) == 1
    connection = opened[0]
    # Test actual lock release before the bookkeeping assertion.
    second = sqlite3.connect(db, timeout=0.05)
    try:
        second.execute("BEGIN IMMEDIATE")
        second.rollback()
    finally:
        second.close()
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connection.execute("SELECT 1")
    assert connection.close_count == 1


def test_keyboard_interrupt_rolls_back_before_terminalization(factory_case, monkeypatch):
    db, opened, run = factory_case
    observed = []
    original = terminal.record_planned_lifecycle_zero_attempt_terminal_provenance

    def inspect_entry(connection, **kwargs):
        observed.append(connection.in_transaction)
        assert not connection.in_transaction, "interrupted write entered terminalization"
        assert connection.execute(
            "SELECT updated_at FROM printer_memory_factory_runs WHERE run_id=?",
            (FACTORY_RUN_ID,),
        ).fetchone()[0] != "INTERRUPTED_UNCOMMITTED_WRITE"
        return original(connection, **kwargs)

    monkeypatch.setattr(terminal, "record_planned_lifecycle_zero_attempt_terminal_provenance", inspect_entry)
    report = run(KeyboardInterrupt())
    assert observed == [False]
    assert report["stop_reason"] == "SAFE_STOP_OPERATOR_INTERRUPTED"
    assert opened[0].rollback_count >= 1
    assert_released(db, opened)


@pytest.mark.parametrize("cleanup_failure", [None, "rollback", "close"])
@pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt])
@pytest.mark.parametrize("point", ["_final_report", "_apply_post_report_integrity"])
def test_finalizer_failure_releases_writer_and_preserves_exception(
    factory_case, monkeypatch, error_type, point, cleanup_failure,
):
    db, opened, run = factory_case
    fault = error_type("injected finalizer fault")

    def fail(*_args, **_kwargs):
        connection = opened[0]
        connection.execute(
            "UPDATE printer_memory_factory_runs SET updated_at=? WHERE run_id=?",
            ("FAILED_FINALIZER_WRITE", FACTORY_RUN_ID),
        )
        assert connection.in_transaction
        if cleanup_failure == "rollback":
            def fail_rollback(self):
                self.rollback_count += 1
                raise sqlite3.OperationalError("injected rollback failure")
            monkeypatch.setattr(ObservedConnection, "rollback", fail_rollback)
        elif cleanup_failure == "close":
            original_close = ObservedConnection.close

            def fail_close(self):
                original_close(self)
                raise sqlite3.OperationalError("injected close failure")
            monkeypatch.setattr(ObservedConnection, "close", fail_close)
        raise fault

    monkeypatch.setattr(factory, point, fail)
    with pytest.raises(error_type) as raised:
        run(factory._ExternalStop("LEASE_RENEWAL_SQLITE_LOCKED"))
    assert raised.value is fault
    if cleanup_failure is not None:
        assert any(f"factory {cleanup_failure} failed" in note for note in fault.__notes__)
    assert_released(db, opened)
    with closing(sqlite3.connect(db)) as reader:
        assert reader.execute(
            "SELECT updated_at FROM printer_memory_factory_runs WHERE run_id=?",
            (FACTORY_RUN_ID,),
        ).fetchone()[0] != "FAILED_FINALIZER_WRITE"


def test_successful_finalization_commits_report_and_closes_once(factory_case):
    db, opened, run = factory_case
    report = run(factory._ExternalStop("LEASE_RENEWAL_SQLITE_LOCKED"))
    assert_released(db, opened)
    with closing(sqlite3.connect(db)) as reader:
        row = reader.execute(
            "SELECT run_status,stop_reason,final_report_json FROM printer_memory_factory_runs "
            "WHERE run_id=?", (FACTORY_RUN_ID,),
        ).fetchone()
        assert row[0] == report["run_status"]
        assert row[1] == report["stop_reason"] == "LEASE_RENEWAL_SQLITE_LOCKED"
        durable_report = json.loads(row[2])
        assert durable_report["stop_reason"] == report["stop_reason"]
        assert durable_report["four_token_terminal"]["shared_cleanup_count"] == 1
        assert report["four_token_terminal"]["shared_cleanup_count"] == 1
        assert reader.execute(
            "SELECT first_terminal_cause FROM printer_four_token_zero_attempt_terminal_provenance"
        ).fetchone()[0] == "LEASE_RENEWAL_SQLITE_LOCKED"


@pytest.mark.parametrize("point", ["_require_schema", "set_writer_attribution_context"])
def test_initialization_failure_also_closes_once(factory_case, monkeypatch, point):
    db, opened, run = factory_case
    fault = RuntimeError("injected initialization failure")

    def fail(connection, *_args, **_kwargs):
        connection.execute(
            "UPDATE printer_memory_factory_campaigns SET updated_at=? WHERE campaign_id=?",
            ("FAILED_INITIALIZATION_WRITE", CAMPAIGN_ID),
        )
        raise fault

    owner = factory if point == "_require_schema" else sqlite_write_contracts
    monkeypatch.setattr(owner, point, fail)
    with pytest.raises(RuntimeError) as raised:
        run(factory._ExternalStop("UNREACHED"))
    assert raised.value is fault
    assert_released(db, opened)
    with closing(sqlite3.connect(db)) as reader:
        assert reader.execute(
            "SELECT updated_at FROM printer_memory_factory_campaigns WHERE campaign_id=?",
            (CAMPAIGN_ID,),
        ).fetchone()[0] != "FAILED_INITIALIZATION_WRITE"

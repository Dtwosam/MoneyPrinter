from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    SOURCE_GOVERNOR_OWNER,
    OwnerPort,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
    LiveOperationalError,
)
from printer_v1.operator_cli.four_token_factory_adapter import (
    FourTokenFactoryAdapterError,
    reconcile_four_token_cycle_terminal,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    LaterCycleCandidateSupply,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
)
from tests.test_v2_9_8b_four_token_gate_g_two_phase_terminal import _terminal_db


NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
GOVERNOR = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCHEDULER = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)
HEALTH = MultiCycleAdmissionHealth(
    source_budget_available=True,
    provider_budgets_available=True,
    scheduler_budget_available=True,
    scheduler_due_work_healthy=True,
    close_reserve_available=True,
    campaign_supervision_healthy=True,
    lease_healthy=True,
    db_healthy=True,
    shared_terminal_condition=False,
    cancellation_requested=False,
    discovery_capacity_available=True,
    protected_work_capacity_available=True,
)


def _callback_database(tmp_path):
    path = tmp_path / "consumed-proof-blocker-tdd.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES ('campaign-1','RUNNING','OPERATIONAL_PERSISTENT','db-1','policy-1')"
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json) VALUES (?,?,?,?,?)",
        ("configuration-1", "campaign-1", "a" * 64, "{}", "{}"),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "factory-1",
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            "{}",
            NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "campaign-run-1",
            "campaign-1",
            1,
            "RUNNING",
            "factory-1",
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    connection.commit()
    connection.close()
    return path


def _invoke(callback):
    return callback(
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        authoritative_factory_run_id="factory-1",
        cycle_id="cycle-2",
        cycle_ordinal=2,
        cycle_cutoff=NOW.isoformat(),
        evaluated_at=NOW.isoformat(),
        selection_seed="seed-2",
        source_governor=GOVERNOR,
        central_scheduler=SCHEDULER,
        admission_health=HEALTH,
    )


def _insert_terminal_scope_row(connection, *, job_id: int, scope: str) -> None:
    connection.execute(
        "INSERT INTO printer_scheduler_jobs VALUES (?,?,?,'SUCCEEDED','t0',NULL,NULL,'t0','t0')",
        (job_id, f"job-{job_id}", "WINDOW_CLOSE"),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_scheduler_work VALUES "
        "(?,?,?,?,?,?,'SUCCEEDED',?,'factory-1','V2_STAGE_SCOPED',?,"
        "'WINDOW_CLOSED','t0','t0')",
        (
            f"work-{job_id}",
            "campaign-1",
            "campaign-run-1",
            "cycle-1",
            "cycle-1-slot-1",
            "cycle-1-window-1",
            job_id,
            scope,
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_run_steps VALUES "
        "(?, 'factory-1', ?, 'SUCCEEDED',NULL,'t0','t0')",
        (job_id, job_id),
    )


def test_reconcile_accepts_all_canonical_stage_scopes_together() -> None:
    connection = _terminal_db()
    connection.execute(
        "UPDATE printer_memory_factory_campaign_scheduler_work "
        "SET work_scope='DISCOVERY_SELECTION' WHERE scheduler_work_id='work-11'"
    )
    connection.execute(
        "UPDATE printer_memory_factory_campaign_scheduler_work "
        "SET work_scope='FIRST_15M_HANDOFF' WHERE scheduler_work_id='work-12'"
    )
    _insert_terminal_scope_row(connection, job_id=13, scope="WINDOW_LIFECYCLE")
    _insert_terminal_scope_row(connection, job_id=14, scope="TERMINAL_CLEANUP")
    connection.commit()

    result = reconcile_four_token_cycle_terminal(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        cycle_id="cycle-1",
        cause="COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
        run_status="COMPLETED",
        now=datetime(2026, 8, 13, 16, 0, tzinfo=timezone.utc),
    )
    assert result["cycle_state"] == "TERMINAL_COMPLETED"
    connection.close()


@pytest.mark.parametrize(
    ("column", "value"),
    (
        ("work_scope", "UNKNOWN_SCOPE"),
        ("ownership_contract_version", "WRONG_VERSION"),
    ),
)
def test_reconcile_still_rejects_noncanonical_ownership(column, value) -> None:
    connection = _terminal_db()
    connection.execute(
        f"UPDATE printer_memory_factory_campaign_scheduler_work SET {column}=? "
        "WHERE scheduler_work_id='work-11'",
        (value,),
    )
    connection.commit()
    with pytest.raises(FourTokenFactoryAdapterError):
        reconcile_four_token_cycle_terminal(
            connection,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            cycle_id="cycle-1",
            cause="COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
            run_status="COMPLETED",
            now=datetime(2026, 8, 13, 16, 0, tzinfo=timezone.utc),
        )
    connection.close()


def test_reconcile_still_rejects_missing_scheduler_job_identity() -> None:
    connection = _terminal_db()
    connection.execute(
        "UPDATE printer_memory_factory_campaign_scheduler_work SET scheduler_job_id=NULL "
        "WHERE scheduler_work_id='work-11'"
    )
    connection.commit()
    with pytest.raises(FourTokenFactoryAdapterError):
        reconcile_four_token_cycle_terminal(
            connection,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            factory_run_id="factory-1",
            cycle_id="cycle-1",
            cause="COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
            run_status="COMPLETED",
            now=datetime(2026, 8, 13, 16, 0, tzinfo=timezone.utc),
        )
    connection.close()


def test_later_cycle_supply_runs_after_durable_authority_and_without_outer_write_lock(tmp_path) -> None:
    path = _callback_database(tmp_path)
    observed = []

    def supply(**_):
        probe = sqlite3.connect(path, timeout=0.0)
        try:
            authority = probe.execute(
                "SELECT a.attempt_state,j.status,j.locked_at,j.lock_owner "
                "FROM printer_pre_admission_discovery_attempts AS a "
                "JOIN printer_scheduler_jobs AS j ON j.id=a.scheduler_job_id"
            ).fetchone()
            acquired = True
            try:
                probe.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError:
                acquired = False
            finally:
                if probe.in_transaction:
                    probe.rollback()
            observed.append((authority, acquired))
        finally:
            probe.close()
        return LaterCycleCandidateSupply((), (), "NO_EXACT_PAIR")

    callback = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=supply
    )._build_later_cycle_discovery_callback(
        db_path=path, configuration_id="configuration-1"
    )
    result = _invoke(callback)

    assert result.state == "NO_PAIR"
    assert len(observed) == 1
    authority, acquired = observed[0]
    assert authority is not None
    assert authority[0] == "RUNNING"
    assert authority[1] == "RUNNING"
    assert authority[2] is not None
    assert authority[3] is not None
    assert acquired is True


def test_known_safe_supply_exception_persists_stable_code(tmp_path) -> None:
    path = _callback_database(tmp_path)

    def failed_supply(**_):
        raise LiveOperationalError("KNOWN_SAFE_SUPPLY_CODE", "secret provider detail")

    callback = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=failed_supply
    )._build_later_cycle_discovery_callback(
        db_path=path, configuration_id="configuration-1"
    )
    result = _invoke(callback)

    assert result.state == "FAILED"
    assert result.first_terminal_cause == "KNOWN_SAFE_SUPPLY_CODE"
    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT status,retry_count,last_error FROM printer_scheduler_jobs"
        ).fetchone() == ("FAILED", 1, "KNOWN_SAFE_SUPPLY_CODE")
    finally:
        connection.close()


def test_unknown_supply_exception_persists_bounded_class_only(tmp_path) -> None:
    path = _callback_database(tmp_path)
    secret = "https://provider.invalid/?api_key=DO_NOT_PERSIST"

    def failed_supply(**_):
        raise RuntimeError(secret)

    callback = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=failed_supply
    )._build_later_cycle_discovery_callback(
        db_path=path, configuration_id="configuration-1"
    )
    result = _invoke(callback)

    expected = "LATER_CYCLE_SUPPLY_EXCEPTION_RUNTIMEERROR"
    assert result.state == "FAILED"
    assert result.first_terminal_cause == expected
    assert len(result.first_terminal_cause) <= 128
    assert secret not in result.first_terminal_cause
    connection = sqlite3.connect(path)
    try:
        row = connection.execute(
            "SELECT status,retry_count,last_error FROM printer_scheduler_jobs"
        ).fetchone()
        assert row == ("FAILED", 1, expected)
        stored = connection.execute(
            "SELECT first_terminal_cause FROM printer_pre_admission_discovery_attempts"
        ).fetchone()[0]
        assert stored == expected
        assert secret not in stored
    finally:
        connection.close()


@pytest.mark.parametrize("raise_after_drift", (False, True))
def test_phase_c_authority_drift_fails_closed_without_overwrite_or_admission(
    tmp_path, raise_after_drift
) -> None:
    path = _callback_database(tmp_path)

    def supply(**_):
        probe = sqlite3.connect(path)
        try:
            cursor = probe.execute(
                "UPDATE printer_scheduler_jobs "
                "SET status='CANCELLED', locked_at=NULL, lock_owner=NULL "
                "WHERE job_kind='PRE_ADMISSION_DISCOVERY_SELECTION'"
            )
            assert cursor.rowcount == 1
            probe.commit()
        finally:
            probe.close()

        if raise_after_drift:
            raise RuntimeError("provider detail must not overwrite drifted authority")
        return LaterCycleCandidateSupply((), (), "NO_EXACT_PAIR")

    callback = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=supply
    )._build_later_cycle_discovery_callback(
        db_path=path, configuration_id="configuration-1"
    )

    with pytest.raises(
        LiveOperationalError,
        match="LATER_CYCLE_PRE_ADMISSION_AUTHORITY_DRIFT",
    ):
        _invoke(callback)

    connection = sqlite3.connect(path)
    try:
        attempt = connection.execute(
            "SELECT attempt_state,first_terminal_cause "
            "FROM printer_pre_admission_discovery_attempts"
        ).fetchone()
        job = connection.execute(
            "SELECT status,retry_count,last_error,locked_at,lock_owner "
            "FROM printer_scheduler_jobs"
        ).fetchone()
        admitted = connection.execute(
            "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempt_items"
        ).fetchone()[0]

        assert attempt == ("RUNNING", None)
        assert job == ("CANCELLED", 0, None, None, None)
        assert admitted == 0
    finally:
        connection.close()

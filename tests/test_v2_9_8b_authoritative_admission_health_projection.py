from __future__ import annotations

import importlib
import json
import sqlite3

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleCampaignBinding,
)
from printer_v1.operator_cli.operational_standard_4h import (
    standard_four_hour_capacity_contract,
)


def _budget_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE printer_source_requests(
            id INTEGER PRIMARY KEY,
            request_key TEXT
        );
        CREATE TABLE printer_memory_factory_runs(
            run_id TEXT PRIMARY KEY,
            config_json TEXT NOT NULL
        );
        CREATE TABLE printer_memory_factory_run_steps(
            id INTEGER PRIMARY KEY,
            run_id TEXT NOT NULL,
            step_key TEXT NOT NULL,
            step_kind TEXT NOT NULL,
            step_status TEXT NOT NULL,
            scheduler_job_id INTEGER,
            token_id INTEGER,
            pair_id INTEGER,
            tracking_lane TEXT
        );
        """
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs(run_id,config_json) VALUES (?,?)",
        ("factory-1", json.dumps({"operational_natural_disposition": True})),
    )
    connection.commit()
    return connection


def _projection_owner():
    return importlib.import_module(
        "printer_v1.operator_cli.authoritative_admission_health"
    )


def _insert_run_requests(connection: sqlite3.Connection, count: int) -> None:
    connection.executemany(
        "INSERT INTO printer_source_requests(request_key) VALUES (?)",
        ((f"factory-1:request-{index}",) for index in range(count)),
    )
    connection.commit()


def _insert_pending_step(
    connection: sqlite3.Connection,
    *,
    step_kind: str,
    scheduler_job_id: int | None = 1,
) -> sqlite3.Row:
    step_key = (
        "t1_window_close" if step_kind == "WINDOW_CLOSE" else "t1_snapshot_001"
    )
    connection.execute(
        """
        INSERT INTO printer_memory_factory_run_steps(
            run_id,step_key,step_kind,step_status,scheduler_job_id,
            token_id,pair_id,tracking_lane
        ) VALUES ('factory-1',?,?, 'PENDING',?,1,11,'TRACK_FAST')
        """,
        (step_key, step_kind, scheduler_job_id),
    )
    connection.commit()
    return connection.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE step_key=?",
        (step_key,),
    ).fetchone()


def test_budget_forecast_preserves_cycle_one_and_uses_canonical_owner_arithmetic() -> None:
    owner = _projection_owner()
    connection = _budget_connection()
    try:
        base = standard_four_hour_capacity_contract()
        result = owner.project_lifecycle_budget_reserve(
            connection,
            factory_run_id="factory-1",
        )

        assert result.source_budget_available is True
        assert result.close_reserve_available is True
        assert result.protected_work_capacity_available is True
        assert result.cycle_one_request_ceiling == base[
            "lifecycle_request_outer_ceiling"
        ]
        assert result.cycle_one_consumed_requests == base[
            "shared_discovery_requests"
        ]
        assert result.second_cycle_request_envelope == base[
            "lifecycle_request_outer_ceiling"
        ]
        assert result.four_token_request_ceiling == 2 * base[
            "lifecycle_request_outer_ceiling"
        ]
        assert result.recheck_on_lifecycle_change is False

        over_cycle_one = (
            base["lifecycle_request_outer_ceiling"]
            - base["shared_discovery_requests"]
            + 1
        )
        _insert_run_requests(connection, over_cycle_one)
        blocked = owner.project_lifecycle_budget_reserve(
            connection,
            factory_run_id="factory-1",
        )
        assert blocked.source_budget_available is False
        assert "CYCLE_ONE_SOURCE_ENVELOPE_EXCEEDED" in blocked.reasons
    finally:
        connection.close()


def test_close_and_protected_work_reserves_use_factory_step_projection() -> None:
    owner = _projection_owner()
    base = standard_four_hour_capacity_contract()

    close_connection = _budget_connection()
    try:
        close = _insert_pending_step(close_connection, step_kind="WINDOW_CLOSE")
        close_projection = factory._projected_requests_for_step(close)
        _insert_run_requests(
            close_connection,
            base["lifecycle_request_outer_ceiling"]
            - base["shared_discovery_requests"]
            - close_projection
            + 1,
        )
        result = owner.project_lifecycle_budget_reserve(
            close_connection,
            factory_run_id="factory-1",
        )
        assert result.source_budget_available is True
        assert result.close_reserved_requests == close_projection
        assert result.close_reserve_available is False
        assert result.protected_work_capacity_available is False
        assert result.recheck_on_lifecycle_change is True
    finally:
        close_connection.close()

    protected_connection = _budget_connection()
    try:
        pending = _insert_pending_step(protected_connection, step_kind="SNAPSHOT")
        projected = factory._projected_requests_for_step(pending)
        _insert_run_requests(
            protected_connection,
            base["lifecycle_request_outer_ceiling"]
            - base["shared_discovery_requests"],
        )
        result = owner.project_lifecycle_budget_reserve(
            protected_connection,
            factory_run_id="factory-1",
        )
        assert result.source_budget_available is True
        assert result.close_reserve_available is True
        assert result.protected_reserved_requests == projected
        assert result.protected_work_capacity_available is False
        assert result.recheck_on_lifecycle_change is True
    finally:
        protected_connection.close()


def test_missing_reservation_identity_fails_closed_without_writing() -> None:
    owner = _projection_owner()
    connection = _budget_connection()
    try:
        _insert_pending_step(
            connection,
            step_kind="WINDOW_CLOSE",
            scheduler_job_id=None,
        )
        changes_before = connection.total_changes

        result = owner.project_lifecycle_budget_reserve(
            connection,
            factory_run_id="factory-1",
        )

        assert result.close_reserve_available is False
        assert result.protected_work_capacity_available is False
        assert "LIFECYCLE_RESERVATION_EVIDENCE_INCOMPLETE" in result.reasons
        assert connection.total_changes == changes_before
        assert connection.in_transaction is False
    finally:
        connection.close()


def _scheduler_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE printer_scheduler_jobs(
            id INTEGER PRIMARY KEY,
            job_name TEXT NOT NULL,
            job_kind TEXT NOT NULL,
            status TEXT NOT NULL,
            scheduled_for TEXT NOT NULL,
            locked_at TEXT,
            lock_owner TEXT
        );
        CREATE TABLE printer_memory_factory_run_steps(
            id INTEGER PRIMARY KEY,
            run_id TEXT NOT NULL,
            step_key TEXT NOT NULL,
            step_kind TEXT NOT NULL,
            step_status TEXT NOT NULL,
            scheduler_job_id INTEGER
        );
        CREATE TABLE printer_memory_factory_campaign_scheduler_work(
            scheduler_work_id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            cycle_id TEXT NOT NULL,
            work_state TEXT NOT NULL,
            scheduler_job_id INTEGER,
            ownership_contract_version TEXT NOT NULL
        );
        """
    )
    return connection


def _binding() -> MultiCycleCampaignBinding:
    return MultiCycleCampaignBinding(
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        configuration_id="configuration-1",
        authoritative_factory_run_id="factory-1",
    )


def _insert_scheduler_owner(
    connection: sqlite3.Connection,
    *,
    job_id: int,
    status: str = "PENDING",
    locked_at: str | None = None,
    lock_owner: str | None = None,
    work_state: str = "PENDING",
) -> None:
    connection.execute(
        """
        INSERT INTO printer_scheduler_jobs(
            id,job_name,job_kind,status,scheduled_for,locked_at,lock_owner
        ) VALUES (?,?, 'MEMORY_WINDOW_CLOSE',?,'2026-08-13T11:59:00+00:00',?,?)
        """,
        (job_id, f"v2_4_factory-1_job-{job_id}", status, locked_at, lock_owner),
    )
    connection.execute(
        """
        INSERT INTO printer_memory_factory_run_steps(
            run_id,step_key,step_kind,step_status,scheduler_job_id
        ) VALUES ('factory-1',?,'WINDOW_CLOSE','PENDING',?)
        """,
        (f"t1_close_{job_id}", job_id),
    )
    connection.execute(
        """
        INSERT INTO printer_memory_factory_campaign_scheduler_work(
            scheduler_work_id,campaign_id,run_id,cycle_id,work_state,
            scheduler_job_id,ownership_contract_version
        ) VALUES (?,'campaign-1','campaign-run-1','cycle-1',?,?,
                  'V2_STAGE_SCOPED')
        """,
        (f"work-{job_id}", work_state, job_id),
    )
    connection.commit()


def test_due_and_claimed_scheduler_work_is_healthy_and_capacity_is_derived() -> None:
    owner = _projection_owner()
    connection = _scheduler_connection()
    try:
        _insert_scheduler_owner(connection, job_id=1)
        _insert_scheduler_owner(
            connection,
            job_id=2,
            status="RUNNING",
            locked_at="2026-08-13T11:59:30+00:00",
            lock_owner="factory-owner",
            work_state="RUNNING",
        )
        changes_before = connection.total_changes

        result = owner.project_scheduler_health(
            connection,
            binding=_binding(),
            first_cycle_id="cycle-1",
        )

        base = standard_four_hour_capacity_contract()
        assert result.scheduler_budget_available is True
        assert result.scheduler_due_work_healthy is True
        assert result.attributable_job_count == 2
        assert result.cycle_one_scheduler_ceiling == base[
            "lifecycle_scheduler_outer_ceiling"
        ]
        assert result.second_cycle_scheduler_envelope == base[
            "lifecycle_scheduler_outer_ceiling"
        ]
        assert result.four_token_scheduler_ceiling == 2 * base[
            "lifecycle_scheduler_outer_ceiling"
        ]
        assert result.recheck_on_lifecycle_change is False
        assert connection.total_changes == changes_before
    finally:
        connection.close()


def test_scheduler_integrity_defects_fail_closed_but_due_work_does_not() -> None:
    owner = _projection_owner()

    contradictory = _scheduler_connection()
    try:
        _insert_scheduler_owner(
            contradictory,
            job_id=1,
            status="PENDING",
            locked_at="2026-08-13T11:59:30+00:00",
            lock_owner="factory-owner",
        )
        result = owner.project_scheduler_health(
            contradictory,
            binding=_binding(),
            first_cycle_id="cycle-1",
        )
        assert result.scheduler_due_work_healthy is False
        assert "SCHEDULER_LOCK_STATUS_CONTRADICTION" in result.reasons
        assert result.recheck_on_lifecycle_change is True
    finally:
        contradictory.close()

    orphan = _scheduler_connection()
    try:
        orphan.execute(
            """
            INSERT INTO printer_memory_factory_run_steps(
                run_id,step_key,step_kind,step_status,scheduler_job_id
            ) VALUES ('factory-1','t1_close','WINDOW_CLOSE','PENDING',99)
            """
        )
        orphan.commit()
        result = owner.project_scheduler_health(
            orphan,
            binding=_binding(),
            first_cycle_id="cycle-1",
        )
        assert result.scheduler_due_work_healthy is False
        assert "ORPHAN_FACTORY_RUN_STEP_SCHEDULER_JOB" in result.reasons
    finally:
        orphan.close()

    terminal_drift = _scheduler_connection()
    try:
        _insert_scheduler_owner(
            terminal_drift,
            job_id=1,
            status="PENDING",
            work_state="SUCCEEDED",
        )
        result = owner.project_scheduler_health(
            terminal_drift,
            binding=_binding(),
            first_cycle_id="cycle-1",
        )
        assert result.scheduler_due_work_healthy is False
        assert "TERMINAL_WORK_ACTIVE_SCHEDULER_JOB" in result.reasons
    finally:
        terminal_drift.close()


def test_scheduler_cycle_one_overconsumption_is_not_hidden_by_four_token_headroom() -> None:
    owner = _projection_owner()
    connection = _scheduler_connection()
    try:
        ceiling = standard_four_hour_capacity_contract()[
            "lifecycle_scheduler_outer_ceiling"
        ]
        for job_id in range(1, ceiling + 2):
            _insert_scheduler_owner(
                connection,
                job_id=job_id,
                status="SUCCEEDED",
                work_state="SUCCEEDED",
            )

        result = owner.project_scheduler_health(
            connection,
            binding=_binding(),
            first_cycle_id="cycle-1",
        )

        assert result.attributable_job_count == ceiling + 1
        assert result.attributable_job_count < result.four_token_scheduler_ceiling
        assert result.scheduler_budget_available is False
        assert "CYCLE_ONE_SCHEDULER_ENVELOPE_EXCEEDED" in result.reasons
    finally:
        connection.close()

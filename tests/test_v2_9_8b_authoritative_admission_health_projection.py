from __future__ import annotations

import importlib
import json
import sqlite3

from printer_v1.operator_cli import one_command_15m_factory as factory
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

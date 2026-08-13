from __future__ import annotations

import importlib
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.db.migrate import canonical_migration_count, canonical_migration_names
from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.campaign_supervision import (
    acquire_campaign_supervision,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleCampaignBinding,
)
from printer_v1.operator_cli.operational_standard_4h import (
    standard_four_hour_capacity_contract,
)
from printer_v1.operator_cli.operational_database_target_binding import (
    PRODUCTION_AUTHORITATIVE,
    OperationalDatabaseTargetBinding,
    build_operational_database_target_binding,
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


NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _operational_fixture(
    tmp_path: Path,
) -> tuple[
    Path,
    sqlite3.Connection,
    OperationalDatabaseTargetBinding,
    dict[str, object],
]:
    db_path = tmp_path / "authoritative-admission-health.sqlite3"
    lock_path = tmp_path / "authoritative-admission-health.lease.json"
    apply_migrations(db_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    stamp = NOW.isoformat()
    baseline_sha = "a" * 64
    connection.execute(
        """
        INSERT INTO printer_memory_factory_campaigns(
            campaign_id,campaign_state,db_mode,db_target_identity,
            policy_version,created_at,updated_at
        ) VALUES ('campaign-1','RUNNING','OPERATIONAL_PERSISTENT',?,
                  'policy-v1',?,?)
        """,
        (f"sha256:{baseline_sha}", stamp, stamp),
    )
    connection.execute(
        """
        INSERT INTO printer_memory_factory_campaign_configurations(
            configuration_id,campaign_id,configuration_hash,
            configuration_json,launch_provenance_json,created_at
        ) VALUES ('configuration-1','campaign-1',?,'{}','{}',?)
        """,
        ("b" * 64, stamp),
    )
    connection.execute(
        """
        INSERT INTO printer_memory_factory_runs(
            run_id,run_status,window_kind,db_mode,config_hash,config_json,
            selected_token_count,started_at,created_at,updated_at
        ) VALUES ('factory-1','RUNNING','WINDOW_15M','OPERATIONAL_PERSISTENT',
                  ?,'{}',0,?,?,?)
        """,
        ("c" * 64, stamp, stamp, stamp),
    )
    connection.execute(
        """
        INSERT INTO printer_memory_factory_campaign_runs(
            run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,
            created_at,updated_at
        ) VALUES ('campaign-run-1','campaign-1',1,'RUNNING','factory-1',?,?)
        """,
        (stamp, stamp),
    )
    connection.execute(
        """
        INSERT INTO printer_memory_factory_campaign_cycles(
            cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,
            created_at,updated_at
        ) VALUES ('cycle-1','campaign-1','campaign-run-1',1,'TRACKING',?,?)
        """,
        (stamp, stamp),
    )
    connection.commit()
    connection.close()

    acquire_campaign_supervision(
        db_path,
        lock_path=lock_path,
        supervision_id="supervision-1",
        campaign_id="campaign-1",
        configuration_id="configuration-1",
        run_id="campaign-run-1",
        owner_id="owner-1",
        lease_seconds=120,
        now=NOW,
    )
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")

    migration_count = canonical_migration_count()
    migration_head = canonical_migration_names()[-1]
    binding = build_operational_database_target_binding(
        target_kind=PRODUCTION_AUTHORITATIVE,
        resolved_db_path=db_path,
        authorized_pre_mutation_sha256=baseline_sha,
        migration_count=migration_count,
        migration_head=migration_head,
        authorization_id="authorization-1",
        authorization_marker_sha256="d" * 64,
        application_marker_sha256="e" * 64,
        execution_id="execution-1",
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        cycle_id="cycle-1",
        configuration_id="configuration-1",
        authorization_consumed_once=True,
        invocation_count=1,
        allowed_invocation_count=1,
        automatic_retry_allowed=False,
        manual_rerun_allowed=False,
        resume_allowed=False,
        restart_allowed=False,
        successor_allowed=False,
    )
    expected: dict[str, object] = {
        "target_kind": PRODUCTION_AUTHORITATIVE,
        "resolved_db_path": str(db_path.resolve()),
        "authorized_pre_mutation_sha256": baseline_sha,
        "migration_count": migration_count,
        "migration_head": migration_head,
        "authorization_id": "authorization-1",
        "authorization_marker_sha256": "d" * 64,
        "application_marker_sha256": "e" * 64,
        "execution_id": "execution-1",
        "campaign_id": "campaign-1",
        "campaign_run_id": "campaign-run-1",
        "cycle_id": "cycle-1",
        "configuration_id": "configuration-1",
        "durable_db_target_identity": f"sha256:{baseline_sha}",
        "authorization_consumed_once": True,
        "invocation_count": 1,
        "allowed_invocation_count": 1,
        "automatic_retry_allowed": False,
        "manual_rerun_allowed": False,
        "resume_allowed": False,
        "restart_allowed": False,
        "successor_allowed": False,
    }
    return db_path, connection, binding, expected


def _operational_projection(owner, db_path, connection, binding, expected, *, now=NOW):
    return owner.project_operational_health(
        connection,
        db_path=db_path,
        binding=_binding(),
        first_cycle_id="cycle-1",
        operational_db_binding=binding,
        operational_db_expected=expected,
        canonical_authoritative_db_path=db_path,
        supervision_id="supervision-1",
        supervision_owner_id="owner-1",
        now=now,
    )


def test_supervision_lease_db_and_nonterminal_state_project_read_only(tmp_path: Path) -> None:
    owner = _projection_owner()
    db_path, connection, db_binding, expected = _operational_fixture(tmp_path)
    try:
        sha_before = _sha256(db_path)
        changes_before = connection.total_changes

        result = _operational_projection(
            owner, db_path, connection, db_binding, expected
        )

        assert result.campaign_supervision_healthy is True
        assert result.lease_healthy is True
        assert result.db_healthy is True
        assert result.shared_terminal_condition is False
        assert result.cancellation_requested is False
        assert result.lease_expires_at == datetime(
            2026, 8, 13, 12, 2, tzinfo=timezone.utc
        )
        assert result.recheck_on_lifecycle_change is False
        assert connection.total_changes == changes_before
        assert _sha256(db_path) == sha_before
    finally:
        connection.close()


def test_cancellation_is_drain_evidence_not_shared_terminal(tmp_path: Path) -> None:
    owner = _projection_owner()
    db_path, connection, db_binding, expected = _operational_fixture(tmp_path)
    try:
        connection.execute(
            """UPDATE printer_memory_factory_campaign_supervision
               SET supervision_state='STOPPING',cancellation_requested_at=?,
                   cancellation_reason='operator stop',updated_at=?""",
            (NOW.isoformat(), NOW.isoformat()),
        )
        connection.execute(
            "UPDATE printer_memory_factory_campaigns SET campaign_state='STOP_REQUESTED'"
        )
        connection.execute(
            "UPDATE printer_memory_factory_campaign_runs SET run_state='STOP_REQUESTED'"
        )
        connection.commit()

        result = _operational_projection(
            owner, db_path, connection, db_binding, expected
        )

        assert result.campaign_supervision_healthy is True
        assert result.lease_healthy is True
        assert result.cancellation_requested is True
        assert result.shared_terminal_condition is False
    finally:
        connection.close()


def test_db_binding_lease_and_terminal_evidence_fail_closed_independently(
    tmp_path: Path,
) -> None:
    owner = _projection_owner()
    db_path, connection, db_binding, expected = _operational_fixture(tmp_path)
    try:
        wrong_expected = dict(expected)
        wrong_expected["application_marker_sha256"] = "f" * 64
        db_blocked = _operational_projection(
            owner, db_path, connection, db_binding, wrong_expected
        )
        assert db_blocked.db_healthy is False
        assert "OPERATIONAL_DB_BINDING_APPLICATION_MARKER_MISMATCH" in (
            db_blocked.reasons
        )

        lease_blocked = _operational_projection(
            owner,
            db_path,
            connection,
            db_binding,
            expected,
            now=datetime(2026, 8, 13, 12, 2, tzinfo=timezone.utc),
        )
        assert lease_blocked.campaign_supervision_healthy is True
        assert lease_blocked.lease_healthy is False
        assert "CAMPAIGN_LEASE_EXPIRED" in lease_blocked.reasons

        connection.execute(
            "UPDATE printer_memory_factory_runs SET run_status='SAFE_STOPPED'"
        )
        connection.commit()
        terminal = _operational_projection(
            owner, db_path, connection, db_binding, expected
        )
        assert terminal.shared_terminal_condition is True
        assert terminal.cancellation_requested is False
        assert "PERSISTED_SHARED_TERMINAL_STATE" in terminal.reasons
    finally:
        connection.close()

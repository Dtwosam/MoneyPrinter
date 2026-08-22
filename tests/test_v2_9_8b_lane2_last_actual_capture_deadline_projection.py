"""Focused offline proof for Lane-2 last-ACTUAL-capture deadlines."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.cadence_authority import (
    claim_tracking_authority_for_slot_insert,
)
from printer_v1.scheduler.contracts import JOB_PRIORITY_VALUE, JobKind
from printer_v1.scheduler.evidence_deadline import (
    project_last_actual_capture_deadline,
    project_scheduler_job_evidence_deadline,
)


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


def test_fast_prior_actual_capture_projects_dirty_and_separate_block_boundaries() -> None:
    actual = NOW - timedelta(minutes=2)

    projection = project_last_actual_capture_deadline(
        last_actual_snapshot_captured_at=actual,
        window_kind="WINDOW_15M",
        tracking_lane="TRACK_FAST",
    )

    assert projection.status == "RESOLVED"
    assert projection.deadline_at == actual + timedelta(seconds=90)
    assert projection.block_boundary_at == actual + timedelta(seconds=120)
    assert projection.deadline_at != projection.block_boundary_at


def test_normal_prior_actual_capture_projects_dirty_and_separate_block_boundaries() -> None:
    actual = NOW - timedelta(minutes=4)

    projection = project_last_actual_capture_deadline(
        last_actual_snapshot_captured_at=actual,
        window_kind="WINDOW_15M",
        tracking_lane="TRACK_NORMAL",
    )

    assert projection.status == "RESOLVED"
    assert projection.deadline_at == actual + timedelta(seconds=180)
    assert projection.block_boundary_at == actual + timedelta(seconds=240)


def test_actual_capture_drift_moves_deadline_from_actual_not_nominal_schedule() -> None:
    nominal = NOW - timedelta(minutes=3)
    drifted_actual = nominal + timedelta(seconds=37)

    projection = project_last_actual_capture_deadline(
        last_actual_snapshot_captured_at=drifted_actual,
        window_kind="WINDOW_15M",
        tracking_lane="TRACK_FAST",
    )

    assert projection.deadline_at == drifted_actual + timedelta(seconds=90)
    assert projection.deadline_at != nominal + timedelta(seconds=90)


@pytest.mark.parametrize(
    ("actual", "window_end", "expected"),
    (
        (
            NOW - timedelta(seconds=10),
            NOW,
            NOW + timedelta(seconds=60),
        ),
        (
            NOW - timedelta(seconds=80),
            NOW,
            NOW + timedelta(seconds=10),
        ),
    ),
)
def test_forced_close_uses_earlier_dirty_or_closing_freshness_deadline(
    actual: datetime,
    window_end: datetime,
    expected: datetime,
) -> None:
    projection = project_last_actual_capture_deadline(
        last_actual_snapshot_captured_at=actual,
        window_kind="WINDOW_15M",
        tracking_lane="TRACK_FAST",
        forced_close=True,
        window_end_at=window_end,
    )

    assert projection.deadline_at == expected
    assert projection.block_boundary_at == actual + timedelta(seconds=120)


def test_missing_prior_actual_capture_fails_closed_unknown_without_deadline() -> None:
    projection = project_last_actual_capture_deadline(
        last_actual_snapshot_captured_at=None,
        window_kind="WINDOW_15M",
        tracking_lane="TRACK_FAST",
    )

    assert projection.status == "UNKNOWN"
    assert projection.reason_code == "MISSING_PRIOR_ACTUAL_CAPTURE"
    assert projection.last_actual_snapshot_captured_at is None
    assert projection.deadline_at is None
    assert projection.block_boundary_at is None
    assert projection.status != "CLEAN"


@pytest.fixture
def connection(tmp_path):
    database = tmp_path / "lane2-deadline.sqlite3"
    apply_migrations(database)
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """INSERT INTO printer_memory_factory_runs(
               run_id,run_status,window_kind,db_mode,config_hash,config_json,
               selected_token_count,started_at,created_at,updated_at
           ) VALUES ('factory-run','RUNNING','WINDOW_15M','PROOF_ONLY','hash','{}',3,?,?,?)""",
        (NOW.isoformat(), NOW.isoformat(), NOW.isoformat()),
    )
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()


def _add_step(
    conn: sqlite3.Connection,
    *,
    key: str,
    kind: JobKind,
    token_id: int,
    tracking_lane: str,
    scheduled_for: datetime,
    step_kind: str = "SNAPSHOT",
    captured_at: datetime | None = None,
) -> sqlite3.Row:
    conn.execute(
        "INSERT OR IGNORE INTO printer_tokens(id,token_mint) VALUES (?,?)",
        (token_id, f"mint-{token_id}"),
    )
    conn.execute(
        """INSERT OR IGNORE INTO printer_pairs(id,token_id,pair_address)
           VALUES (?,?,?)""",
        (token_id + 1000, token_id, f"pair-{token_id}"),
    )
    terminal = captured_at is not None
    status = "SUCCEEDED" if terminal else "PENDING"
    stamp = captured_at.isoformat() if captured_at is not None else None
    cursor = conn.execute(
        """INSERT INTO printer_scheduler_jobs(
               job_name,job_kind,target_table,priority,status,scheduled_for,
               started_at,finished_at,created_at,updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            f"job-{key}",
            kind.value,
            "printer_tracking_queue",
            JOB_PRIORITY_VALUE[kind],
            status,
            scheduled_for.isoformat(),
            stamp,
            stamp,
            scheduled_for.isoformat(),
            scheduled_for.isoformat(),
        ),
    )
    job_id = int(cursor.lastrowid)
    snapshot_id = None
    if captured_at is not None:
        cursor = conn.execute(
            """INSERT INTO printer_token_snapshots(
                   token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                   source_status,data_quality_label
               ) VALUES (?,?,?,?,?,'COMPLETE','CLEAN_DATA')""",
            (
                token_id,
                token_id + 1000,
                captured_at.isoformat(),
                tracking_lane,
                "TOKEN_SNAPSHOT",
            ),
        )
        snapshot_id = int(cursor.lastrowid)
    cursor = conn.execute(
        """INSERT INTO printer_memory_factory_run_steps(
               run_id,step_key,step_kind,step_status,token_id,pair_id,
               token_mint,pair_address,tracking_lane,scheduled_for,
               scheduler_job_id,snapshot_id,started_at,finished_at,created_at,updated_at
           ) VALUES ('factory-run',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            key,
            step_kind,
            status,
            token_id,
            token_id + 1000,
            f"mint-{token_id}",
            f"pair-{token_id}",
            tracking_lane,
            scheduled_for.isoformat(),
            job_id,
            snapshot_id,
            stamp,
            stamp,
            scheduled_for.isoformat(),
            scheduled_for.isoformat(),
        ),
    )
    conn.commit()
    return conn.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
        (int(cursor.lastrowid),),
    ).fetchone()


def _attach_exact_owner(
    conn: sqlite3.Connection,
    *,
    step: sqlite3.Row,
    window_kind: str,
    canonical_tracking_lane: str | None = None,
    bind_tracking_queue: bool = True,
) -> None:
    token_id = int(step["token_id"])
    slot_id = f"slot-{token_id}"
    window_id = f"window-{token_id}-{window_kind}"
    existing_slot = conn.execute(
        "SELECT tracking_queue_id FROM printer_memory_factory_campaign_token_slots "
        "WHERE token_slot_id=?",
        (slot_id,),
    ).fetchone()
    tracking_queue_id = None
    if existing_slot is not None:
        tracking_queue_id = existing_slot["tracking_queue_id"]
    elif bind_tracking_queue:
        queue_lane = canonical_tracking_lane or str(step["tracking_lane"] or "")
        tracking_queue_id = claim_tracking_authority_for_slot_insert(
            conn,
            token_row_id=token_id,
            pair_row_id=token_id + 1000,
            tracking_lane=queue_lane,
            now=NOW,
        )
    conn.execute(
        """INSERT OR IGNORE INTO printer_memory_factory_campaign_token_slots(
               token_slot_id,campaign_id,run_id,cycle_id,slot_ordinal,
               token_identity,token_row_id,mint_identity,pair_identity,pair_row_id,
               lifecycle_identity,tracking_queue_id,token_state,created_at,updated_at
           ) VALUES (?,'campaign','campaign-run','cycle',?,?,?,?,?,?,?,?,
                     'SELECTED',?,?)""",
        (
            slot_id,
            token_id,
            f"token-{token_id}",
            token_id,
            f"mint-{token_id}",
            f"pair-{token_id}",
            token_id + 1000,
            f"lifecycle-{token_id}",
            tracking_queue_id,
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    conn.execute(
        """INSERT OR IGNORE INTO printer_memory_factory_campaign_windows(
               window_id,campaign_id,run_id,cycle_id,token_slot_id,
               token_row_id,pair_row_id,window_kind,window_state,
               root_15m_lifecycle_identity,checkpoint_cutoff,support_only,
               created_at,updated_at
           ) VALUES (?,'campaign','campaign-run','cycle',?,?,?,?,'COLLECTING',?,?,0,?,?)""",
        (
            window_id,
            slot_id,
            token_id,
            token_id + 1000,
            window_kind,
            f"lifecycle-{token_id}",
            NOW.isoformat(),
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    conn.execute(
        """INSERT INTO printer_memory_factory_campaign_scheduler_work(
               scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,
               window_id,work_intent,deadline_at,work_state,scheduler_job_id,
               ownership_contract_version,stage_id,work_scope,target_category,
               target_identity,factory_run_id,first_terminal_cause,terminal_at,
               created_at,updated_at
           ) VALUES (?,'campaign','campaign-run','cycle',?,?,?,? ,?,? ,
                     'V2_STAGE_SCOPED',?,'WINDOW_LIFECYCLE','CAMPAIGN_WINDOW',?,
                     'factory-run',?,?,?,?)""",
        (
            f"owner-{int(step['scheduler_job_id'])}",
            slot_id,
            window_id,
            str(step["step_kind"]),
            str(step["scheduled_for"]),
            str(step["step_status"]),
            int(step["scheduler_job_id"]),
            window_kind,
            window_id,
            "TEST_CAPTURE_SUCCEEDED" if str(step["step_status"]) == "SUCCEEDED" else None,
            NOW.isoformat() if str(step["step_status"]) == "SUCCEEDED" else None,
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    conn.commit()


def _add_candidate_with_prior_actual(
    conn: sqlite3.Connection,
    *,
    token_id: int,
    kind: JobKind,
    tracking_lane: str,
    prior_actual: datetime,
    candidate_due: datetime,
    candidate_kind: str = "SNAPSHOT",
    window_kind: str = "WINDOW_15M",
    canonical_tracking_lane: str | None = None,
    bind_tracking_queue: bool = True,
) -> sqlite3.Row:
    prior = _add_step(
        conn,
        key=f"prior-{token_id}",
        kind=kind,
        token_id=token_id,
        tracking_lane=tracking_lane,
        scheduled_for=candidate_due - timedelta(minutes=2),
        captured_at=prior_actual,
    )
    candidate = _add_step(
        conn,
        key=f"candidate-{token_id}",
        kind=kind,
        token_id=token_id,
        tracking_lane=tracking_lane,
        scheduled_for=candidate_due,
        step_kind=candidate_kind,
    )
    owner_args = {
        "canonical_tracking_lane": canonical_tracking_lane,
        "bind_tracking_queue": bind_tracking_queue,
    }
    _attach_exact_owner(conn, step=prior, window_kind=window_kind, **owner_args)
    _attach_exact_owner(conn, step=candidate, window_kind=window_kind, **owner_args)
    return candidate


def _selected_key(conn: sqlite3.Connection) -> str:
    selected = factory._select_next_pending_step(conn, run_id="factory-run", now=NOW)
    assert selected is not None
    return str(selected["step_key"])


def test_deadline_orders_due_work_only_inside_selected_agents_category(
    connection: sqlite3.Connection,
) -> None:
    _add_candidate_with_prior_actual(
        connection,
        token_id=1,
        kind=JobKind.TRACK_FAST_FIRST_15M,
        tracking_lane="TRACK_FAST",
        prior_actual=NOW - timedelta(seconds=20),
        candidate_due=NOW - timedelta(minutes=2),
    )
    _add_candidate_with_prior_actual(
        connection,
        token_id=2,
        kind=JobKind.TRACK_FAST_1H,
        tracking_lane="TRACK_FAST",
        prior_actual=NOW - timedelta(seconds=80),
        candidate_due=NOW - timedelta(minutes=1),
    )

    assert _selected_key(connection) == "candidate-2"


@pytest.mark.parametrize(
    ("track_kind", "tracking_lane"),
    (
        (JobKind.TRACK_FAST_FIRST_15M, "TRACK_FAST"),
        (JobKind.TRACK_NORMAL_FIRST_15M, "TRACK_NORMAL"),
    ),
)
def test_track_category_outranks_tighter_memory_close_deadline(
    connection: sqlite3.Connection,
    track_kind: JobKind,
    tracking_lane: str,
) -> None:
    _add_candidate_with_prior_actual(
        connection,
        token_id=1,
        kind=track_kind,
        tracking_lane=tracking_lane,
        prior_actual=NOW - timedelta(seconds=1),
        candidate_due=NOW - timedelta(seconds=1),
    )
    _add_candidate_with_prior_actual(
        connection,
        token_id=2,
        kind=JobKind.MEMORY_WINDOW_CLOSE,
        tracking_lane="TRACK_FAST",
        prior_actual=NOW - timedelta(seconds=89),
        candidate_due=NOW - timedelta(seconds=1),
        candidate_kind="WINDOW_CLOSE_EVIDENCE",
    )

    assert _selected_key(connection) == "candidate-1"


def test_exact_resolver_missing_prior_actual_never_uses_persisted_nominal_deadline(
    connection: sqlite3.Connection,
) -> None:
    candidate = _add_step(
        connection,
        key="missing-prior",
        kind=JobKind.TRACK_FAST_FIRST_15M,
        token_id=1,
        tracking_lane="TRACK_FAST",
        scheduled_for=NOW - timedelta(seconds=1),
    )
    _attach_exact_owner(connection, step=candidate, window_kind="WINDOW_15M")

    projection = project_scheduler_job_evidence_deadline(
        connection,
        factory_run_id="factory-run",
        scheduler_job_id=int(candidate["scheduler_job_id"]),
    )

    assert projection.status == "UNKNOWN"
    assert projection.reason_code == "MISSING_PRIOR_ACTUAL_CAPTURE"
    assert projection.deadline_at is None
    assert projection.block_boundary_at is None


@pytest.mark.parametrize(
    ("canonical_lane", "expected_gap_seconds", "expected_block_seconds"),
    (
        ("TRACK_FAST", 90, 120),
        ("TRACK_NORMAL", 180, 240),
    ),
)
def test_exact_bound_queue_lane_is_canonical_deadline_authority(
    connection: sqlite3.Connection,
    canonical_lane: str,
    expected_gap_seconds: int,
    expected_block_seconds: int,
) -> None:
    prior_actual = NOW - timedelta(seconds=45)
    candidate = _add_candidate_with_prior_actual(
        connection,
        token_id=1,
        kind=(
            JobKind.TRACK_FAST_FIRST_15M
            if canonical_lane == "TRACK_FAST"
            else JobKind.TRACK_NORMAL_FIRST_15M
        ),
        tracking_lane=canonical_lane,
        canonical_tracking_lane=canonical_lane,
        prior_actual=prior_actual,
        candidate_due=NOW - timedelta(seconds=1),
    )

    projection = project_scheduler_job_evidence_deadline(
        connection,
        factory_run_id="factory-run",
        scheduler_job_id=int(candidate["scheduler_job_id"]),
    )

    assert projection.status == "RESOLVED"
    assert projection.deadline_at == prior_actual + timedelta(
        seconds=expected_gap_seconds
    )
    assert projection.block_boundary_at == prior_actual + timedelta(
        seconds=expected_block_seconds
    )


def test_null_slot_tracking_queue_binding_fails_closed_unknown(
    connection: sqlite3.Connection,
) -> None:
    candidate = _add_candidate_with_prior_actual(
        connection,
        token_id=1,
        kind=JobKind.TRACK_FAST_FIRST_15M,
        tracking_lane="TRACK_FAST",
        bind_tracking_queue=False,
        prior_actual=NOW - timedelta(seconds=45),
        candidate_due=NOW - timedelta(seconds=1),
    )

    projection = project_scheduler_job_evidence_deadline(
        connection,
        factory_run_id="factory-run",
        scheduler_job_id=int(candidate["scheduler_job_id"]),
    )

    assert projection.status == "UNKNOWN"
    assert projection.reason_code == "TRACKING_QUEUE_BINDING_MISSING"
    assert projection.deadline_at is None


@pytest.mark.parametrize(
    ("carrier_lane", "canonical_lane"),
    (
        ("TRACK_FAST", "TRACK_NORMAL"),
        ("TRACK_NORMAL", "TRACK_FAST"),
    ),
)
def test_opposite_valid_carrier_and_canonical_queue_lane_fail_closed(
    connection: sqlite3.Connection,
    carrier_lane: str,
    canonical_lane: str,
) -> None:
    candidate = _add_candidate_with_prior_actual(
        connection,
        token_id=1,
        kind=JobKind.TRACK_FAST_FIRST_15M,
        tracking_lane=carrier_lane,
        canonical_tracking_lane=canonical_lane,
        prior_actual=NOW - timedelta(seconds=45),
        candidate_due=NOW - timedelta(seconds=1),
    )

    projection = project_scheduler_job_evidence_deadline(
        connection,
        factory_run_id="factory-run",
        scheduler_job_id=int(candidate["scheduler_job_id"]),
    )

    assert projection.status == "UNKNOWN"
    assert projection.reason_code == "CADENCE_EVIDENCE_CONFLICT"
    assert projection.deadline_at is None


def test_campaign_window_token_pair_mismatch_fails_closed(
    connection: sqlite3.Connection,
) -> None:
    candidate = _add_candidate_with_prior_actual(
        connection,
        token_id=1,
        kind=JobKind.TRACK_FAST_FIRST_15M,
        tracking_lane="TRACK_FAST",
        canonical_tracking_lane="TRACK_FAST",
        prior_actual=NOW - timedelta(seconds=45),
        candidate_due=NOW - timedelta(seconds=1),
    )
    # The production schema prevents this corruption. Drop only the disposable
    # fixture's immutability trigger so the consumer-level fail-closed check is
    # independently exercised against a pre-existing malformed row.
    connection.execute(
        "INSERT INTO printer_pairs(id,token_id,pair_address) "
        "VALUES (2001,1,'other-pair-1')"
    )
    connection.execute("DROP TRIGGER printer_campaign_window_identity_immutable")
    connection.execute(
        "UPDATE printer_memory_factory_campaign_windows SET pair_row_id=2001 "
        "WHERE window_id='window-1-WINDOW_15M'"
    )
    connection.commit()

    projection = project_scheduler_job_evidence_deadline(
        connection,
        factory_run_id="factory-run",
        scheduler_job_id=int(candidate["scheduler_job_id"]),
    )

    assert projection.status == "UNKNOWN"
    assert projection.reason_code == "CAMPAIGN_WINDOW_SLOT_IDENTITY_MISMATCH"
    assert projection.deadline_at is None


def test_missing_current_carrier_uses_sufficient_persisted_queue_authority(
    connection: sqlite3.Connection,
) -> None:
    prior_actual = NOW - timedelta(seconds=45)
    candidate = _add_candidate_with_prior_actual(
        connection,
        token_id=1,
        kind=JobKind.TRACK_NORMAL_FIRST_15M,
        tracking_lane="TRACK_NORMAL",
        canonical_tracking_lane="TRACK_NORMAL",
        prior_actual=prior_actual,
        candidate_due=NOW - timedelta(seconds=1),
    )
    connection.execute(
        "UPDATE printer_memory_factory_run_steps SET tracking_lane=NULL WHERE id=?",
        (int(candidate["id"]),),
    )
    connection.commit()

    projection = project_scheduler_job_evidence_deadline(
        connection,
        factory_run_id="factory-run",
        scheduler_job_id=int(candidate["scheduler_job_id"]),
    )

    assert projection.status == "RESOLVED"
    assert projection.deadline_at == prior_actual + timedelta(seconds=180)


def test_exact_resolver_uses_actual_capture_even_if_later_step_work_failed(
    connection: sqlite3.Connection,
) -> None:
    candidate = _add_candidate_with_prior_actual(
        connection,
        token_id=1,
        kind=JobKind.TRACK_FAST_FIRST_15M,
        tracking_lane="TRACK_FAST",
        prior_actual=NOW - timedelta(seconds=45),
        candidate_due=NOW - timedelta(seconds=1),
    )
    connection.execute(
        """UPDATE printer_memory_factory_run_steps
           SET step_status='FAILED' WHERE step_key='prior-1'"""
    )
    connection.commit()

    projection = project_scheduler_job_evidence_deadline(
        connection,
        factory_run_id="factory-run",
        scheduler_job_id=int(candidate["scheduler_job_id"]),
    )

    assert projection.status == "RESOLVED"
    assert projection.last_actual_snapshot_captured_at == NOW - timedelta(seconds=45)
    assert projection.deadline_at == NOW + timedelta(seconds=45)

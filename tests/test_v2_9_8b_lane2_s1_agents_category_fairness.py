"""Focused offline proof for Lane-2 implementation slice S1."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.one_command_15m_factory import (
    _select_next_pending_step,
)
from printer_v1.scheduler.contracts import JOB_PRIORITY_VALUE, JobKind
from printer_v1.scheduler.scheduler import LockResult, claim_due_job


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def connection(tmp_path):
    database = tmp_path / "lane2-s1.sqlite3"
    apply_migrations(database)
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """INSERT INTO printer_memory_factory_runs(
               run_id,run_status,window_kind,db_mode,config_hash,config_json,
               selected_token_count,started_at,created_at,updated_at
           ) VALUES ('run-s1','RUNNING','WINDOW_15M','PROOF_ONLY','hash','{}',3,?,?,?)""",
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
    scheduled_for: datetime,
    created_at: datetime | None = None,
    started: bool = False,
    step_kind: str = "SNAPSHOT",
) -> sqlite3.Row:
    created = (created_at or scheduled_for).isoformat()
    status = "SUCCEEDED" if started else "PENDING"
    started_at = NOW.isoformat() if started else None
    cursor = conn.execute(
        """INSERT INTO printer_scheduler_jobs(
               job_name,job_kind,target_table,target_id,priority,status,
               scheduled_for,started_at,finished_at,created_at,updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            f"job-{key}",
            kind.value,
            "printer_tracking_queue",
            None,
            JOB_PRIORITY_VALUE[kind],
            status,
            scheduled_for.isoformat(),
            started_at,
            started_at,
            created,
            created,
        ),
    )
    job_id = int(cursor.lastrowid)
    cursor = conn.execute(
        """INSERT INTO printer_memory_factory_run_steps(
               run_id,step_key,step_kind,step_status,token_id,pair_id,
               token_mint,pair_address,tracking_lane,scheduled_for,
               scheduler_job_id,started_at,finished_at,created_at,updated_at
           ) VALUES ('run-s1',?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            key,
            step_kind,
            status,
            token_id,
            token_id + 1000,
            f"mint-{token_id}",
            f"pair-{token_id}",
            "TRACK_FAST" if "TRACK_FAST" in kind.value else "TRACK_NORMAL",
            scheduled_for.isoformat(),
            job_id,
            started_at,
            started_at,
            created,
            created,
        ),
    )
    conn.commit()
    return conn.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
        (int(cursor.lastrowid),),
    ).fetchone()


def _attach_historical_owner(
    conn: sqlite3.Connection,
    *,
    step: sqlite3.Row,
    cycle_id: str,
    deadline_at: datetime,
) -> None:
    conn.execute(
        """INSERT INTO printer_memory_factory_campaign_scheduler_work(
               scheduler_work_id,campaign_id,run_id,cycle_id,token_slot_id,
               window_id,work_intent,
               deadline_at,work_state,scheduler_job_id,
               ownership_contract_version,created_at,updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            f"owner-{int(step['scheduler_job_id'])}",
            "campaign-s1",
            "campaign-run-s1",
            cycle_id,
            f"slot-{int(step['token_id'])}",
            f"window-{int(step['token_id'])}",
            "fixture",
            deadline_at.isoformat(),
            "PENDING",
            int(step["scheduler_job_id"]),
            "V1_WINDOW_BOUND",
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    conn.commit()


def _selected_key(conn: sqlite3.Connection) -> str | None:
    selected = _select_next_pending_step(conn, run_id="run-s1", now=NOW)
    return None if selected is None else str(selected["step_key"])


def _mark_step_served(conn: sqlite3.Connection, key: str) -> None:
    row = conn.execute(
        """SELECT id,scheduler_job_id FROM printer_memory_factory_run_steps
           WHERE run_id='run-s1' AND step_key=?""",
        (key,),
    ).fetchone()
    conn.execute(
        """UPDATE printer_scheduler_jobs
           SET status='SUCCEEDED',started_at=?,finished_at=?,updated_at=?
           WHERE id=?""",
        (NOW.isoformat(), NOW.isoformat(), NOW.isoformat(), int(row["scheduler_job_id"])),
    )
    conn.execute(
        """UPDATE printer_memory_factory_run_steps
           SET step_status='SUCCEEDED',started_at=?,finished_at=?,updated_at=?
           WHERE id=?""",
        (NOW.isoformat(), NOW.isoformat(), NOW.isoformat(), int(row["id"])),
    )
    conn.commit()


@pytest.mark.parametrize(
    ("higher", "lower"),
    (
        (JobKind.TRACK_FAST_FIRST_15M, JobKind.MEMORY_WINDOW_CLOSE),
        (JobKind.TRACK_NORMAL_FIRST_15M, JobKind.MEMORY_WINDOW_CLOSE),
        (JobKind.TRACK_FAST_FIRST_15M, JobKind.TRACK_NORMAL_FIRST_15M),
        (JobKind.TRACK_FAST_4H, JobKind.MEMORY_WINDOW_CLOSE),
        (JobKind.TRACK_NORMAL_4H, JobKind.MEMORY_WINDOW_CLOSE),
    ),
)
def test_canonical_agents_category_precedes_fifo_age(
    connection: sqlite3.Connection,
    higher: JobKind,
    lower: JobKind,
) -> None:
    _add_step(
        connection,
        key="lower-older",
        kind=lower,
        token_id=1,
        scheduled_for=NOW - timedelta(minutes=20),
        step_kind="WINDOW_CLOSE" if lower is JobKind.MEMORY_WINDOW_CLOSE else "SNAPSHOT",
    )
    _add_step(
        connection,
        key="higher-newer",
        kind=higher,
        token_id=2,
        scheduled_for=NOW - timedelta(minutes=1),
    )

    assert _selected_key(connection) == "higher-newer"


def test_same_category_token_fairness_prevents_permanent_monopoly(
    connection: sqlite3.Connection,
) -> None:
    _add_step(
        connection,
        key="token-a-served",
        kind=JobKind.TRACK_FAST_FIRST_15M,
        token_id=1,
        scheduled_for=NOW - timedelta(minutes=40),
        started=True,
    )
    _add_step(
        connection,
        key="token-a-second",
        kind=JobKind.TRACK_FAST_FIRST_15M,
        token_id=1,
        scheduled_for=NOW - timedelta(minutes=30),
    )
    _add_step(
        connection,
        key="token-b-first",
        kind=JobKind.TRACK_FAST_1H,
        token_id=2,
        scheduled_for=NOW - timedelta(minutes=1),
    )

    assert _selected_key(connection) == "token-b-first"
    assert _selected_key(connection) == "token-b-first"


def test_cycle_one_two_three_do_not_have_permanent_ordinal_priority(
    connection: sqlite3.Connection,
) -> None:
    _add_step(
        connection,
        key="cycle-1-served",
        kind=JobKind.TRACK_NORMAL_FIRST_15M,
        token_id=1,
        scheduled_for=NOW - timedelta(minutes=50),
        started=True,
    )
    cycle_1 = _add_step(
        connection,
        key="cycle-1-next",
        kind=JobKind.TRACK_NORMAL_FIRST_15M,
        token_id=1,
        scheduled_for=NOW - timedelta(minutes=40),
    )
    cycle_2 = _add_step(
        connection,
        key="cycle-2-first",
        kind=JobKind.TRACK_NORMAL_1H,
        token_id=2,
        scheduled_for=NOW - timedelta(minutes=2),
    )
    cycle_3 = _add_step(
        connection,
        key="cycle-3-first",
        kind=JobKind.TRACK_NORMAL_4H,
        token_id=3,
        scheduled_for=NOW - timedelta(minutes=1),
    )
    _attach_historical_owner(
        connection,
        step=cycle_1,
        cycle_id="cycle-1",
        deadline_at=NOW - timedelta(days=3),
    )
    _attach_historical_owner(
        connection,
        step=cycle_2,
        cycle_id="cycle-2",
        deadline_at=NOW + timedelta(days=3),
    )
    _attach_historical_owner(
        connection,
        step=cycle_3,
        cycle_id="cycle-3",
        deadline_at=NOW - timedelta(days=30),
    )

    assert _selected_key(connection) == "cycle-2-first"
    _mark_step_served(connection, "cycle-2-first")
    assert _selected_key(connection) == "cycle-3-first"
    _mark_step_served(connection, "cycle-3-first")
    assert _selected_key(connection) == "cycle-1-next"


@pytest.mark.parametrize(
    "lower_kind",
    (
        JobKind.DISCOVERY_REFRESH,
        JobKind.PRE_ADMISSION_DISCOVERY_SELECTION,
        JobKind.MARKET_REGIME_CONTEXT,
        JobKind.SOLANA_CHAIN_HEAT_CONTEXT,
        JobKind.BACKUP_SOURCE_CHECK,
    ),
)
def test_discovery_and_context_cannot_leapfrog_track_work(
    connection: sqlite3.Connection,
    lower_kind: JobKind,
) -> None:
    _add_step(
        connection,
        key="lower-category",
        kind=lower_kind,
        token_id=1,
        scheduled_for=NOW - timedelta(hours=2),
    )
    _add_step(
        connection,
        key="track",
        kind=JobKind.TRACK_NORMAL_FIRST_15M,
        token_id=2,
        scheduled_for=NOW - timedelta(seconds=1),
    )

    assert _selected_key(connection) == "track"


def test_locked_paper_monitor_is_not_activated(
    connection: sqlite3.Connection,
) -> None:
    _add_step(
        connection,
        key="locked-paper-monitor",
        kind=JobKind.OPEN_PAPER_TRADE_MONITOR,
        token_id=1,
        scheduled_for=NOW - timedelta(hours=4),
    )
    _add_step(
        connection,
        key="lawful-track",
        kind=JobKind.TRACK_FAST_FIRST_15M,
        token_id=2,
        scheduled_for=NOW - timedelta(seconds=1),
    )

    assert _selected_key(connection) == "lawful-track"


@pytest.mark.parametrize(
    ("first_deadline", "second_deadline"),
    (
        (NOW + timedelta(days=90), NOW - timedelta(days=90)),
        (NOW - timedelta(days=90), NOW + timedelta(days=90)),
    ),
)
def test_selection_does_not_use_campaign_deadline_at(
    connection: sqlite3.Connection,
    first_deadline: datetime,
    second_deadline: datetime,
) -> None:
    first = _add_step(
        connection,
        key="first-by-truthful-due-state",
        kind=JobKind.TRACK_FAST_FIRST_15M,
        token_id=1,
        scheduled_for=NOW - timedelta(minutes=2),
    )
    second = _add_step(
        connection,
        key="second-by-truthful-due-state",
        kind=JobKind.TRACK_FAST_1H,
        token_id=2,
        scheduled_for=NOW - timedelta(minutes=1),
    )
    _attach_historical_owner(
        connection,
        step=first,
        cycle_id="cycle-1",
        deadline_at=first_deadline,
    )
    _attach_historical_owner(
        connection,
        step=second,
        cycle_id="cycle-2",
        deadline_at=second_deadline,
    )

    assert _selected_key(connection) == "first-by-truthful-due-state"


def test_single_token_selection_remains_scheduler_claim_led(
    connection: sqlite3.Connection,
) -> None:
    only = _add_step(
        connection,
        key="single-token",
        kind=JobKind.TRACK_NORMAL_FIRST_15M,
        token_id=1,
        scheduled_for=NOW - timedelta(seconds=1),
    )

    selected = _select_next_pending_step(connection, run_id="run-s1", now=NOW)
    assert int(selected["id"]) == int(only["id"])
    scheduler_row = connection.execute(
        "SELECT status FROM printer_scheduler_jobs WHERE id=?",
        (int(selected["scheduler_job_id"]),),
    ).fetchone()
    assert scheduler_row["status"] == "PENDING"
    assert claim_due_job(
        connection,
        job_id=int(selected["scheduler_job_id"]),
        lock_owner="lane2-s1-test",
        now=NOW,
    ) is LockResult.ACQUIRED

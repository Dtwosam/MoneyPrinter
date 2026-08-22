"""Focused offline proof for Lane-2 close evidence/context/audit separation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.close_phases import (
    CLOSE_PHASE_STEP_KINDS,
    close_phase_metadata,
)
from printer_v1.scheduler.contracts import JOB_PRIORITY_VALUE, JobKind
from printer_v1.snapshots.lifecycle_continuity import (
    resolve_current_run_long_predecessor,
)


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def connection(tmp_path):
    database = tmp_path / "lane2-close-phases.sqlite3"
    apply_migrations(database)
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """INSERT INTO printer_memory_factory_runs(
               run_id,run_status,window_kind,db_mode,config_hash,config_json,
               selected_token_count,started_at,created_at,updated_at
           ) VALUES ('phase-run','RUNNING','WINDOW_15M','PROOF_ONLY','hash','{}',2,?,?,?)""",
        (NOW.isoformat(), NOW.isoformat(), NOW.isoformat()),
    )
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()


def _add_phase(
    conn: sqlite3.Connection,
    *,
    token_id: int,
    step_kind: str,
    scheduled_for: datetime,
    status: str = "PENDING",
    snapshot_id: int | None = None,
    cycle: int = 1,
) -> sqlite3.Row:
    family, phase = CLOSE_PHASE_STEP_KINDS[step_kind]
    prefix = f"t{token_id}_c{cycle:04d}_{family.lower()}"
    phase_keys = {
        "EVIDENCE": f"{prefix}_evidence",
        "CONTEXT": f"{prefix}_context",
        "AUDIT": f"{prefix}_audit",
    }
    metadata = close_phase_metadata(
        family=family,
        phase=phase,
        evidence_step_key=phase_keys["EVIDENCE"],
        context_step_key=phase_keys["CONTEXT"],
    )
    cursor = conn.execute(
        """INSERT INTO printer_scheduler_jobs(
               job_name,job_kind,target_table,priority,status,scheduled_for,
               created_at,updated_at
           ) VALUES (?,?, 'printer_tracking_queue',?,?,?,?,?)""",
        (
            f"job-{phase_keys[phase]}",
            JobKind.MEMORY_WINDOW_CLOSE.value,
            JOB_PRIORITY_VALUE[JobKind.MEMORY_WINDOW_CLOSE],
            "SUCCEEDED" if status == "SUCCEEDED" else "PENDING",
            scheduled_for.isoformat(),
            scheduled_for.isoformat(),
            scheduled_for.isoformat(),
        ),
    )
    job_id = int(cursor.lastrowid)
    cursor = conn.execute(
        """INSERT INTO printer_memory_factory_run_steps(
               run_id,step_key,step_kind,step_status,token_id,pair_id,
               token_mint,pair_address,tracking_lane,scheduled_for,
               scheduler_job_id,snapshot_id,result_json,created_at,updated_at
           ) VALUES ('phase-run',?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            phase_keys[phase],
            step_kind,
            status,
            token_id,
            token_id + 1000,
            f"mint-{token_id}",
            f"pair-{token_id}",
            "TRACK_FAST",
            scheduled_for.isoformat(),
            job_id,
            snapshot_id,
            json.dumps(metadata, sort_keys=True),
            scheduled_for.isoformat(),
            scheduled_for.isoformat(),
        ),
    )
    conn.commit()
    return conn.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
        (int(cursor.lastrowid),),
    ).fetchone()


def _snapshot(conn: sqlite3.Connection, *, token_id: int, captured_at: datetime) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO printer_tokens(id,token_mint) VALUES (?,?)",
        (token_id, f"mint-{token_id}"),
    )
    conn.execute(
        """INSERT OR IGNORE INTO printer_pairs(id,token_id,pair_address)
           VALUES (?,?,?)""",
        (token_id + 1000, token_id, f"pair-{token_id}"),
    )
    cursor = conn.execute(
        """INSERT INTO printer_token_snapshots(
               token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
               source_status,data_quality_label
           ) VALUES (?,?,?,?,?,'COMPLETE','CLEAN_DATA')""",
        (
            token_id,
            token_id + 1000,
            captured_at.isoformat(),
            "TRACK_FAST",
            "TOKEN_SNAPSHOT",
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def _selected_kind(conn: sqlite3.Connection) -> tuple[int, str]:
    selected = factory._select_next_pending_step(
        conn, run_id="phase-run", now=NOW
    )
    assert selected is not None
    return int(selected["token_id"]), str(selected["step_kind"])


def test_two_sibling_evidence_phases_are_selected_before_context_or_audit(
    connection: sqlite3.Connection,
) -> None:
    first_sid = _snapshot(connection, token_id=1, captured_at=NOW)
    _add_phase(
        connection,
        token_id=1,
        step_kind="WINDOW_CLOSE_EVIDENCE",
        scheduled_for=NOW - timedelta(seconds=2),
        status="SUCCEEDED",
        snapshot_id=first_sid,
    )
    _add_phase(
        connection,
        token_id=1,
        step_kind="WINDOW_CLOSE_CONTEXT",
        scheduled_for=NOW - timedelta(seconds=2),
    )
    _add_phase(
        connection,
        token_id=1,
        step_kind="WINDOW_CLOSE_AUDIT",
        scheduled_for=NOW - timedelta(seconds=2),
    )
    _add_phase(
        connection,
        token_id=2,
        step_kind="WINDOW_CLOSE_EVIDENCE",
        scheduled_for=NOW - timedelta(seconds=1),
    )

    assert _selected_kind(connection) == (2, "WINDOW_CLOSE_EVIDENCE")


def test_audit_is_ineligible_until_exact_context_and_evidence_are_terminal(
    connection: sqlite3.Connection,
) -> None:
    sid = _snapshot(connection, token_id=1, captured_at=NOW)
    evidence = _add_phase(
        connection,
        token_id=1,
        step_kind="WINDOW_CLOSE_EVIDENCE",
        scheduled_for=NOW - timedelta(seconds=1),
        status="SUCCEEDED",
        snapshot_id=sid,
    )
    context = _add_phase(
        connection,
        token_id=1,
        step_kind="WINDOW_CLOSE_CONTEXT",
        scheduled_for=NOW - timedelta(seconds=1),
    )
    _add_phase(
        connection,
        token_id=1,
        step_kind="WINDOW_CLOSE_AUDIT",
        scheduled_for=NOW - timedelta(seconds=1),
    )

    assert _selected_kind(connection) == (1, "WINDOW_CLOSE_CONTEXT")
    connection.execute(
        "UPDATE printer_memory_factory_run_steps SET step_status='SUCCEEDED' WHERE id=?",
        (int(context["id"]),),
    )
    connection.execute(
        "UPDATE printer_scheduler_jobs SET status='SUCCEEDED' WHERE id=?",
        (int(context["scheduler_job_id"]),),
    )
    connection.commit()

    assert _selected_kind(connection) == (1, "WINDOW_CLOSE_AUDIT")
    assert int(evidence["snapshot_id"]) == sid


def test_audit_cannot_claim_without_exact_persisted_closing_snapshot(
    connection: sqlite3.Connection,
) -> None:
    _add_phase(
        connection,
        token_id=1,
        step_kind="WINDOW_CLOSE_EVIDENCE",
        scheduled_for=NOW,
        status="SUCCEEDED",
        snapshot_id=None,
    )
    _add_phase(
        connection,
        token_id=1,
        step_kind="WINDOW_CLOSE_CONTEXT",
        scheduled_for=NOW,
    )
    _add_phase(
        connection,
        token_id=1,
        step_kind="WINDOW_CLOSE_AUDIT",
        scheduled_for=NOW,
    )

    assert factory._select_next_pending_step(
        connection, run_id="phase-run", now=NOW
    ) is None


def test_context_dependency_fails_closed_on_exact_pair_provenance_mismatch(
    connection: sqlite3.Connection,
) -> None:
    sid = _snapshot(connection, token_id=1, captured_at=NOW)
    _add_phase(
        connection,
        token_id=1,
        step_kind="WINDOW_CLOSE_EVIDENCE",
        scheduled_for=NOW,
        status="SUCCEEDED",
        snapshot_id=sid,
    )
    context = _add_phase(
        connection,
        token_id=1,
        step_kind="WINDOW_CLOSE_CONTEXT",
        scheduled_for=NOW,
    )
    connection.execute(
        """UPDATE printer_memory_factory_run_steps
           SET pair_address='different-pair' WHERE id=?""",
        (int(context["id"]),),
    )
    connection.commit()

    assert factory._select_next_pending_step(
        connection, run_id="phase-run", now=NOW
    ) is None


def test_evidence_executor_captures_only_and_context_cannot_rewrite_capture_time(
    connection: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = _add_phase(
        connection,
        token_id=1,
        step_kind="WINDOW_CLOSE_EVIDENCE",
        scheduled_for=NOW,
    )
    connection.execute(
        "UPDATE printer_memory_factory_run_steps SET step_status='RUNNING' WHERE id=?",
        (int(evidence["id"]),),
    )
    evidence = connection.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
        (int(evidence["id"]),),
    ).fetchone()
    sid = _snapshot(connection, token_id=1, captured_at=NOW + timedelta(seconds=7))
    calls: list[str] = []

    def fake_snapshot(*args, **kwargs):
        calls.append("capture")
        return {"ok": True, "snapshot_id": sid}

    def forbidden_context(*args, **kwargs):
        raise AssertionError("context ran inside evidence claim")

    monkeypatch.setattr(factory, "_execute_snapshot", fake_snapshot)
    monkeypatch.setattr(factory, "_collect_preclose_context", forbidden_context)

    result = factory._execute_close_evidence_phase(
        connection,
        evidence,
        adapter_factory=lambda **kwargs: None,
        timeout_seconds=1.0,
    )

    assert result["ok"] is True
    assert result["snapshot_id"] == sid
    assert result["evidence_captured_at"] == (NOW + timedelta(seconds=7)).isoformat()
    assert calls == ["capture"]


def test_partial_context_preserves_durable_evidence_timestamp(
    connection: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sid = _snapshot(connection, token_id=1, captured_at=NOW)
    _add_phase(
        connection,
        token_id=1,
        step_kind="WINDOW_CLOSE_EVIDENCE",
        scheduled_for=NOW,
        status="SUCCEEDED",
        snapshot_id=sid,
    )
    context = _add_phase(
        connection,
        token_id=1,
        step_kind="WINDOW_CLOSE_CONTEXT",
        scheduled_for=NOW,
    )
    partial = {
        "report": {"status": "PARTIAL", "timed_out": ["safety"]},
        "responses": {},
    }
    monkeypatch.setattr(
        factory, "_collect_preclose_context", lambda *args, **kwargs: partial
    )
    monkeypatch.setattr(
        factory,
        "_persist_preclose_context",
        lambda *args, **kwargs: {"status": "PARTIAL", "persisted": True},
    )

    result = factory._execute_close_context_phase(
        connection,
        context,
        timeout_seconds=1.0,
    )
    captured = connection.execute(
        "SELECT captured_at FROM printer_token_snapshots WHERE id=?", (sid,)
    ).fetchone()[0]

    assert result["ok"] is True
    assert result["closing_snapshot_id"] == sid
    assert result["governed_context_collection"]["status"] == "PARTIAL"
    assert captured == NOW.isoformat()
    assert result.get("snapshot_id") is None


@pytest.mark.parametrize(
    ("track_kind", "lane"),
    (
        (JobKind.TRACK_FAST_FIRST_15M, "TRACK_FAST"),
        (JobKind.TRACK_NORMAL_FIRST_15M, "TRACK_NORMAL"),
    ),
)
def test_track_category_still_outranks_close_evidence(
    connection: sqlite3.Connection,
    track_kind: JobKind,
    lane: str,
) -> None:
    _add_phase(
        connection,
        token_id=1,
        step_kind="WINDOW_CLOSE_EVIDENCE",
        scheduled_for=NOW - timedelta(hours=1),
    )
    cursor = connection.execute(
        """INSERT INTO printer_scheduler_jobs(
               job_name,job_kind,target_table,priority,status,scheduled_for,
               created_at,updated_at
           ) VALUES ('track',?,'printer_tracking_queue',?,'PENDING',?,?,?)""",
        (
            track_kind.value,
            JOB_PRIORITY_VALUE[track_kind],
            (NOW - timedelta(seconds=1)).isoformat(),
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    connection.execute(
        """INSERT INTO printer_memory_factory_run_steps(
               run_id,step_key,step_kind,step_status,token_id,pair_id,
               token_mint,pair_address,tracking_lane,scheduled_for,
               scheduler_job_id,created_at,updated_at
           ) VALUES ('phase-run','track','SNAPSHOT','PENDING',2,1002,
                     'mint-2','pair-2',?,?,?,?,?)""",
        (
            lane,
            (NOW - timedelta(seconds=1)).isoformat(),
            int(cursor.lastrowid),
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    connection.commit()

    assert _selected_kind(connection) == (2, "SNAPSHOT")


def test_all_existing_close_families_have_three_explicit_phases() -> None:
    assert CLOSE_PHASE_STEP_KINDS == {
        "WINDOW_CLOSE_EVIDENCE": ("WINDOW_CLOSE", "EVIDENCE"),
        "WINDOW_CLOSE_CONTEXT": ("WINDOW_CLOSE", "CONTEXT"),
        "WINDOW_CLOSE_AUDIT": ("WINDOW_CLOSE", "AUDIT"),
        "CONTINUATION_CLOSE_EVIDENCE": ("CONTINUATION_CLOSE", "EVIDENCE"),
        "CONTINUATION_CLOSE_CONTEXT": ("CONTINUATION_CLOSE", "CONTEXT"),
        "CONTINUATION_CLOSE_AUDIT": ("CONTINUATION_CLOSE", "AUDIT"),
        "LONG_CONTINUATION_CLOSE_EVIDENCE": (
            "LONG_CONTINUATION_CLOSE",
            "EVIDENCE",
        ),
        "LONG_CONTINUATION_CLOSE_CONTEXT": (
            "LONG_CONTINUATION_CLOSE",
            "CONTEXT",
        ),
        "LONG_CONTINUATION_CLOSE_AUDIT": (
            "LONG_CONTINUATION_CLOSE",
            "AUDIT",
        ),
    }


def test_15m_planner_enqueues_three_scheduler_owned_close_phases(
    connection: sqlite3.Connection,
) -> None:
    opening = {
        "step_key": "t1_snapshot_00",
        "token_id": 1,
        "pair_id": 1001,
        "token_mint": "mint-1",
        "pair_address": "pair-1",
        "tracking_lane": "TRACK_FAST",
    }

    factory._plan_anchored_jobs(
        connection,
        run_id="phase-run",
        opening_step=opening,
        first_snapshot_captured_at=NOW.isoformat(),
        window_seconds=900.0,
    )
    rows = connection.execute(
        """SELECT s.step_kind,s.result_json,j.job_kind,j.status
           FROM printer_memory_factory_run_steps AS s
           JOIN printer_scheduler_jobs AS j ON j.id=s.scheduler_job_id
           WHERE s.run_id='phase-run' AND s.step_kind LIKE 'WINDOW_CLOSE_%'
           ORDER BY s.id"""
    ).fetchall()

    assert [str(row["step_kind"]) for row in rows] == [
        "WINDOW_CLOSE_EVIDENCE",
        "WINDOW_CLOSE_CONTEXT",
        "WINDOW_CLOSE_AUDIT",
    ]
    assert all(
        str(row["job_kind"]) == JobKind.MEMORY_WINDOW_CLOSE.value
        and str(row["status"]) == "PENDING"
        for row in rows
    )
    assert [json.loads(str(row["result_json"]))["close_phase"] for row in rows] == [
        "EVIDENCE",
        "CONTEXT",
        "AUDIT",
    ]


def test_failure_between_phases_cancels_later_phase_without_orphan_running_job(
    connection: sqlite3.Connection,
) -> None:
    sid = _snapshot(connection, token_id=1, captured_at=NOW)
    _add_phase(
        connection,
        token_id=1,
        step_kind="WINDOW_CLOSE_EVIDENCE",
        scheduled_for=NOW,
        status="SUCCEEDED",
        snapshot_id=sid,
    )
    context = _add_phase(
        connection,
        token_id=1,
        step_kind="WINDOW_CLOSE_CONTEXT",
        scheduled_for=NOW,
    )
    audit = _add_phase(
        connection,
        token_id=1,
        step_kind="WINDOW_CLOSE_AUDIT",
        scheduled_for=NOW,
    )
    connection.execute(
        """UPDATE printer_memory_factory_run_steps
           SET step_status='FAILED',error_or_skip_reason='CONTEXT_TIMEOUT'
           WHERE id=?""",
        (int(context["id"]),),
    )
    connection.execute(
        "UPDATE printer_scheduler_jobs SET status='FAILED' WHERE id=?",
        (int(context["scheduler_job_id"]),),
    )

    cancelled = factory._cancel_pending_for_token(
        connection, "phase-run", 1, factory.TOKEN_LOCAL_CANCELLED
    )
    connection.commit()
    audit_state = connection.execute(
        """SELECT s.step_status,j.status
           FROM printer_memory_factory_run_steps AS s
           JOIN printer_scheduler_jobs AS j ON j.id=s.scheduler_job_id
           WHERE s.id=?""",
        (int(audit["id"]),),
    ).fetchone()

    assert cancelled == 1
    assert tuple(audit_state) == ("CANCELLED", "CANCELLED")
    assert connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_run_steps
           WHERE run_id='phase-run' AND step_status='RUNNING'"""
    ).fetchone()[0] == 0


def test_terminal_audit_resolves_exact_evidence_as_existing_long_predecessor(
    connection: sqlite3.Connection,
) -> None:
    sid = _snapshot(connection, token_id=1, captured_at=NOW)
    window_id = int(
        connection.execute(
            """INSERT INTO printer_memory_windows(
                   token_id,pair_id,window_kind,opened_at,closed_at,
                   window_start_at,window_end_at,snapshot_start_id,snapshot_end_id,
                   window_status,memory_status,memory_quality_label,
                   data_quality_label,do_not_train,supporting_context_json
               ) VALUES (1,1001,'WINDOW_1H',?,?,?,?,?,?,'WINDOW_CLOSED',
                         'PARTIAL_MEMORY','PARTIAL_MEMORY','CLEAN_DATA',0,'{}')""",
            (
                (NOW - timedelta(hours=1)).isoformat(),
                NOW.isoformat(),
                (NOW - timedelta(hours=1)).isoformat(),
                NOW.isoformat(),
                sid,
                sid,
            ),
        ).lastrowid
    )
    _add_phase(
        connection,
        token_id=1,
        step_kind="CONTINUATION_CLOSE_EVIDENCE",
        scheduled_for=NOW,
        status="SUCCEEDED",
        snapshot_id=sid,
    )
    _add_phase(
        connection,
        token_id=1,
        step_kind="CONTINUATION_CLOSE_CONTEXT",
        scheduled_for=NOW,
        status="SUCCEEDED",
    )
    audit = _add_phase(
        connection,
        token_id=1,
        step_kind="CONTINUATION_CLOSE_AUDIT",
        scheduled_for=NOW,
        status="SUCCEEDED",
    )
    connection.execute(
        """UPDATE printer_memory_factory_run_steps
           SET memory_window_id=? WHERE id=?""",
        (window_id, int(audit["id"])),
    )
    connection.commit()

    resolved = resolve_current_run_long_predecessor(
        connection,
        run_id="phase-run",
        token_id=1,
        pair_id=1001,
        tracking_lane="TRACK_FAST",
        successor_kind="WINDOW_4H",
        allow_enabled_successor_planning=True,
    )

    assert resolved["resolved"] is True
    assert int(resolved["window"]["snapshot_end_id"]) == sid
    assert int(resolved["window"]["step_snapshot_id"]) == sid

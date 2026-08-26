"""Focused real-executor proof for resumable timely pre-close acquisition."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import replace
import json
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.close_phases import PRE_CLOSE_STEP_KINDS
from printer_v1.scheduler.contracts import JOB_PRIORITY_VALUE, JobKind, LockResult
from printer_v1.scheduler.scheduler import claim_due_job, release_stale_locks
from printer_v1.sources.governed_execution import build_fixture_source_adapter
from printer_v1.sources.governed_execution import FIXTURE_FAILURE


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def connection(tmp_path):
    database = tmp_path / "timely-preclose.sqlite3"
    apply_migrations(database)
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """INSERT INTO printer_memory_factory_runs(
               run_id,run_status,window_kind,db_mode,config_hash,config_json,
               selected_token_count,started_at,created_at,updated_at
           ) VALUES ('preclose-run','RUNNING','WINDOW_15M','PROOF_ONLY','hash',
                     '{"timeout_seconds": 1.0}',2,?,?,?)""",
        (NOW.isoformat(), NOW.isoformat(), NOW.isoformat()),
    )
    for token_id in (1, 2):
        conn.execute(
            "INSERT INTO printer_tokens(id,token_mint) VALUES (?,?)",
            (token_id, f"mint-{token_id}"),
        )
        conn.execute(
            """INSERT INTO printer_pairs(id,token_id,pair_address)
               VALUES (?,?,?)""",
            (token_id + 1000, token_id, f"pair-{token_id}"),
        )
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()


def _target(token_id: int) -> dict[str, object]:
    return {
        "token_id": token_id,
        "pair_id": token_id + 1000,
        "token_mint": f"mint-{token_id}",
        "pair_address": f"pair-{token_id}",
        "tracking_lane": "TRACK_FAST",
    }


def _add_preclose(
    conn: sqlite3.Connection,
    *,
    token_id: int = 1,
    family: str = "WINDOW_CLOSE",
    close_at: datetime | None = None,
    earliest_at: datetime | None = None,
    cycle_id: str | None = None,
) -> sqlite3.Row:
    close_at = close_at or NOW + timedelta(minutes=15)
    earliest_at = earliest_at or NOW
    key, kind, scheduled_for, projection = factory._preclose_phase_plan(
        family=family,
        prefix=f"t{token_id}{'-' + cycle_id if cycle_id else ''}",
        run_id="preclose-run",
        target=_target(token_id),
        window_end_at=close_at,
        earliest_preclose_schedulable_at=earliest_at,
        timeout_seconds=1.0,
    )
    if cycle_id is not None:
        projection.update(
            campaign_run_id="campaign-run",
            cycle_id=cycle_id,
            token_slot_id=f"{cycle_id}-slot",
            campaign_window_id=f"{cycle_id}-window",
        )
    factory._insert_step_and_job(
        conn,
        run_id="preclose-run",
        target=_target(token_id),
        step_key=key,
        step_kind=kind,
        scheduled_for=scheduled_for,
        result_projection=projection,
    )
    conn.commit()
    return conn.execute(
        """SELECT * FROM printer_memory_factory_run_steps
           WHERE run_id='preclose-run' AND step_key=?""",
        (key,),
    ).fetchone()


def _only_pending(conn: sqlite3.Connection, step: sqlite3.Row, role: str) -> sqlite3.Row:
    payload = json.loads(str(step["result_json"]))
    for unit in payload["source_unit_manifest"]:
        if unit["source_unit_identity"] == role:
            unit["state"] = "PENDING"
        else:
            unit["state"] = "NOT_REQUIRED"
            unit["terminal_reason"] = "TEST_NOT_REQUIRED"
    payload["terminal_unit_count"] = len(payload["source_unit_manifest"]) - 1
    conn.execute(
        "UPDATE printer_memory_factory_run_steps SET result_json=? WHERE id=?",
        (json.dumps(payload, sort_keys=True), int(step["id"])),
    )
    conn.commit()
    return conn.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
        (int(step["id"]),),
    ).fetchone()


def _claim(conn: sqlite3.Connection, step: sqlite3.Row) -> sqlite3.Row:
    conn.execute(
        "UPDATE printer_scheduler_jobs SET scheduled_for=? WHERE id=?",
        (NOW.isoformat(), int(step["scheduler_job_id"])),
    )
    conn.commit()
    assert claim_due_job(
        conn,
        job_id=int(step["scheduler_job_id"]),
        lock_owner="test-worker",
        now=NOW,
    ) == LockResult.ACQUIRED
    conn.execute(
        """UPDATE printer_memory_factory_run_steps
           SET step_status='RUNNING',started_at=? WHERE id=?""",
        (NOW.isoformat(), int(step["id"])),
    )
    factory._bind_preclose_source_unit_for_claim(conn, step_id=int(step["id"]))
    conn.commit()
    return conn.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
        (int(step["id"]),),
    ).fetchone()


def test_scheduler_claim_binds_exactly_one_projected_source_unit(
    connection: sqlite3.Connection,
) -> None:
    step = _claim(connection, _add_preclose(connection))
    payload = json.loads(str(step["result_json"]))
    ready = [
        unit
        for unit in payload["source_unit_manifest"]
        if unit["state"] == "PENDING"
    ]
    expected = min(
        ready,
        key=lambda unit: (
            unit["latest_safe_claim_at"],
            unit["deterministic_tie_ordinal"],
            unit["source_unit_identity"],
        ),
    )

    assert payload["active_claim_source_unit_identity"] == expected[
        "source_unit_identity"
    ]
    assert payload["active_claim_scheduler_job_id"] == int(
        step["scheduler_job_id"]
    )


def _goplus_factories(call_log: list[str]):
    adapter = build_fixture_source_adapter(
        "goplus",
        fixture_payload={
            "token_mint": "mint-1",
            "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
        },
    )

    def goplus(**_kwargs):
        original = adapter.execute

        def recorded(context):
            call_log.append("goplus")
            return original(context)

        adapter.execute = recorded
        return adapter

    return {"goplus": goplus}


def _timed_factory(
    source_name: str,
    observed_at: datetime,
    call_log: list[str],
    *,
    payload: dict[str, object] | None = None,
):
    def build(**_kwargs):
        adapter = build_fixture_source_adapter(
            source_name, fixture_payload=payload or {"token_mint": "mint-1"}
        )
        original = adapter.execute

        def execute(context):
            call_log.append(source_name)
            return replace(original(context), received_at=observed_at.isoformat())

        adapter.execute = execute
        return adapter

    return build


def _all_success_factories(call_log: list[str], *, token_mint: str = "mint-1"):
    def simple(source_name: str, payload_builder):
        def build(**kwargs):
            adapter = build_fixture_source_adapter(
                source_name, fixture_payload=payload_builder(kwargs)
            )
            original = adapter.execute

            def execute(context):
                call_log.append(source_name)
                return original(context)

            adapter.execute = execute
            return adapter

        return build

    return {
        "coingecko": simple("coingecko", lambda _: {}),
        "goplus": simple(
            "goplus",
            lambda _: {
                "token_mint": token_mint,
                "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
            },
        ),
        "solana_rpc_core_safety": simple(
            "solana_rpc", lambda _: {"token_mint": token_mint}
        ),
        "solana_rpc_holder": simple(
            "solana_rpc",
            lambda _: {
                "token_mint": token_mint,
                "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
            },
        ),
        "jupiter_quote": simple(
            "jupiter_quote",
            lambda kwargs: {
                "input_mint": kwargs["input_mint"],
                "output_mint": kwargs["output_mint"],
            },
        ),
    }


def test_one_claim_executes_one_governed_unit_then_checkpoints_and_yields(
    connection: sqlite3.Connection,
) -> None:
    calls: list[str] = []
    step = _only_pending(connection, _add_preclose(connection), "SAFETY_PRIMARY")
    payload = json.loads(str(step["result_json"]))
    safety_deadline = next(
        unit["latest_safe_claim_at"] for unit in payload["source_unit_manifest"]
        if unit["source_unit_identity"] == "SAFETY_PRIMARY"
    )
    market = next(
        unit for unit in payload["source_unit_manifest"]
        if unit["source_unit_identity"] == "MARKET_CHAIN"
    )
    market["state"] = "PENDING"
    market["latest_safe_claim_at"] = (
        datetime.fromisoformat(safety_deadline) + timedelta(seconds=1)
    ).isoformat()
    payload["terminal_unit_count"] -= 1
    connection.execute(
        "UPDATE printer_memory_factory_run_steps SET result_json=? WHERE id=?",
        (json.dumps(payload, sort_keys=True), int(step["id"])),
    )
    connection.commit()
    step = _claim(connection, step)

    result = factory._execute_preclose_critical_phase(
        connection,
        step,
        timeout_seconds=1.0,
        context_adapter_factories=_goplus_factories(calls),
        claimed_at=NOW,
    )
    factory._checkpoint_and_yield_preclose_claim(
        connection, step=step, result=result, now=NOW
    )

    persisted = connection.execute(
        """SELECT s.step_status,s.result_json,j.status,j.started_at,j.locked_at
           FROM printer_memory_factory_run_steps s
           JOIN printer_scheduler_jobs j ON j.id=s.scheduler_job_id
           WHERE s.id=?""",
        (int(step["id"]),),
    ).fetchone()
    payload = json.loads(str(persisted["result_json"]))
    assert calls == ["goplus"]
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_source_requests"
    ).fetchone()[0] == 1
    assert payload["last_claim_source_unit_identity"] == "SAFETY_PRIMARY"
    assert payload["terminal_unit_count"] == len(payload["source_unit_manifest"]) - 1
    assert persisted["step_status"] == "PENDING"
    assert persisted["status"] == "PENDING"
    assert persisted["started_at"] is None
    assert persisted["locked_at"] is None


def test_request_response_rehydrates_without_second_provider_call(
    connection: sqlite3.Connection,
) -> None:
    calls: list[str] = []
    step = _claim(connection, _only_pending(connection, _add_preclose(connection), "SAFETY_PRIMARY"))
    first = factory._execute_preclose_critical_phase(
        connection,
        step,
        timeout_seconds=1.0,
        context_adapter_factories=_goplus_factories(calls),
        claimed_at=NOW,
    )
    request_id = first["last_claim_source_request_id"]
    original = json.loads(str(step["result_json"]))
    connection.execute(
        "UPDATE printer_memory_factory_run_steps SET result_json=? WHERE id=?",
        (json.dumps(original, sort_keys=True), int(step["id"])),
    )
    connection.commit()

    second = factory._execute_preclose_critical_phase(
        connection,
        step,
        timeout_seconds=1.0,
        context_adapter_factories=_goplus_factories(calls),
        claimed_at=NOW,
    )

    assert calls == ["goplus"]
    assert second["last_claim_source_request_id"] == request_id
    assert second["last_claim_reconciliation"] == "REHYDRATED_TERMINAL_SOURCE_RESULT"
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_source_requests"
    ).fetchone()[0] == 1


def test_stale_claim_release_rehydrates_response_without_duplicate_call(
    connection: sqlite3.Connection,
) -> None:
    calls: list[str] = []
    step = _claim(
        connection,
        _only_pending(connection, _add_preclose(connection), "SAFETY_PRIMARY"),
    )
    first = factory._execute_preclose_critical_phase(
        connection,
        step,
        timeout_seconds=1.0,
        context_adapter_factories=_goplus_factories(calls),
        claimed_at=NOW,
    )
    assert first["last_claim_reconciliation"] == "FIRST_GOVERNED_ATTEMPT"
    # Simulate process loss after governed response persistence but before the
    # aggregate manifest checkpoint/yield.
    assert release_stale_locks(
        connection,
        now=NOW + timedelta(seconds=301),
        lock_timeout_seconds=300,
    ) == 1
    recovered = connection.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
        (int(step["id"]),),
    ).fetchone()
    assert recovered["step_status"] == "PENDING"
    connection.execute(
        "UPDATE printer_scheduler_jobs SET scheduled_for=? WHERE id=?",
        ((NOW + timedelta(seconds=301)).isoformat(), int(step["scheduler_job_id"])),
    )
    connection.commit()
    assert claim_due_job(
        connection,
        job_id=int(step["scheduler_job_id"]),
        lock_owner="recovery-worker",
        now=NOW + timedelta(seconds=301),
    ) == LockResult.ACQUIRED
    factory._bind_preclose_source_unit_for_claim(
        connection, step_id=int(step["id"])
    )
    connection.execute(
        "UPDATE printer_memory_factory_run_steps SET step_status='RUNNING' WHERE id=?",
        (int(step["id"]),),
    )
    connection.commit()
    recovered = connection.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
        (int(step["id"]),),
    ).fetchone()
    assert factory._projected_requests_for_step(connection, recovered) == 0
    assert factory._lifecycle_reservation_records_for_step(
        run_id="preclose-run", pending=recovered, projected_requests=0
    ) == []

    second = factory._execute_preclose_critical_phase(
        connection,
        recovered,
        timeout_seconds=1.0,
        context_adapter_factories=_goplus_factories(calls),
        claimed_at=NOW,
    )

    assert calls == ["goplus"]
    assert second["last_claim_reconciliation"] == "REHYDRATED_TERMINAL_SOURCE_RESULT"
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_source_requests"
    ).fetchone()[0] == 1


def test_request_without_terminal_result_is_unknown_and_never_retried(
    connection: sqlite3.Connection,
) -> None:
    calls: list[str] = []
    step = _only_pending(connection, _add_preclose(connection), "SAFETY_PRIMARY")
    payload = json.loads(str(step["result_json"]))
    unit = next(
        item for item in payload["source_unit_manifest"]
        if item["source_unit_identity"] == "SAFETY_PRIMARY"
    )
    connection.execute(
        """INSERT INTO printer_source_requests(
               source_name,request_kind,requested_at,request_key,
               source_status,data_quality_label)
           VALUES (?,?,?,?, 'COMPLETE','CLEAN_DATA')""",
        (
            unit["source_name"], unit["request_kind"], NOW.isoformat(),
            unit["request_key"],
        ),
    )
    connection.commit()
    step = _claim(connection, step)

    result = factory._execute_preclose_critical_phase(
        connection,
        step,
        timeout_seconds=1.0,
        context_adapter_factories=_goplus_factories(calls),
        claimed_at=NOW,
    )
    terminal = next(
        item for item in result["source_unit_manifest"]
        if item["source_unit_identity"] == "SAFETY_PRIMARY"
    )

    assert calls == []
    assert terminal["state"] == "UNKNOWN_INTERRUPTED_AFTER_REQUEST"
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_source_requests"
    ).fetchone()[0] == 1


def test_failure_row_is_durable_typed_and_rehydrates_without_retry(
    connection: sqlite3.Connection,
) -> None:
    calls: list[str] = []
    adapter = build_fixture_source_adapter("goplus", fixture_kind=FIXTURE_FAILURE)
    original_execute = adapter.execute

    def execute(context):
        calls.append("goplus")
        return original_execute(context)

    adapter.execute = execute
    factories = {"goplus": lambda **_kwargs: adapter}
    step = _claim(
        connection,
        _only_pending(connection, _add_preclose(connection), "SAFETY_PRIMARY"),
    )
    first = factory._execute_preclose_critical_phase(
        connection,
        step,
        timeout_seconds=1.0,
        context_adapter_factories=factories,
        claimed_at=NOW,
    )
    second = factory._execute_preclose_critical_phase(
        connection,
        step,
        timeout_seconds=1.0,
        context_adapter_factories=factories,
        claimed_at=NOW,
    )
    first_unit = next(
        unit
        for unit in first["source_unit_manifest"]
        if unit["source_unit_identity"] == "SAFETY_PRIMARY"
    )
    second_unit = next(
        unit
        for unit in second["source_unit_manifest"]
        if unit["source_unit_identity"] == "SAFETY_PRIMARY"
    )

    assert calls == ["goplus"]
    assert first_unit["state"] == second_unit["state"] == "FAILED"
    assert first_unit["source_failure_id"] == second_unit["source_failure_id"]
    assert second["last_claim_reconciliation"] == "REHYDRATED_TERMINAL_SOURCE_RESULT"
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_source_failures"
    ).fetchone()[0] == 1


def test_duplicate_exact_request_identity_integrity_blocks_without_call(
    connection: sqlite3.Connection,
) -> None:
    calls: list[str] = []
    step = _only_pending(connection, _add_preclose(connection), "SAFETY_PRIMARY")
    payload = json.loads(str(step["result_json"]))
    unit = next(
        item for item in payload["source_unit_manifest"]
        if item["source_unit_identity"] == "SAFETY_PRIMARY"
    )
    connection.executemany(
        """INSERT INTO printer_source_requests(
               source_name,request_kind,requested_at,request_key,
               source_status,data_quality_label)
           VALUES (?,?,?,?, 'COMPLETE','CLEAN_DATA')""",
        [
            (unit["source_name"], unit["request_kind"], NOW.isoformat(), unit["request_key"]),
            (unit["source_name"], unit["request_kind"], NOW.isoformat(), unit["request_key"]),
        ],
    )
    connection.commit()
    step = _claim(connection, step)

    result = factory._execute_preclose_critical_phase(
        connection,
        step,
        timeout_seconds=1.0,
        context_adapter_factories=_goplus_factories(calls),
        claimed_at=NOW,
    )

    assert calls == []
    assert result["ok"] is False
    assert result["blocked_reason"] == "CONTEXT_INTEGRITY_BLOCKED"


def test_foreign_source_request_identity_blocks_without_call(
    connection: sqlite3.Connection,
) -> None:
    calls: list[str] = []
    step = _only_pending(connection, _add_preclose(connection), "SAFETY_PRIMARY")
    payload = json.loads(str(step["result_json"]))
    unit = next(
        item
        for item in payload["source_unit_manifest"]
        if item["source_unit_identity"] == "SAFETY_PRIMARY"
    )
    connection.execute(
        """INSERT INTO printer_source_requests(
               source_name,request_kind,requested_at,request_key,
               source_status,data_quality_label)
           VALUES ('coingecko',?,?,?,'COMPLETE','CLEAN_DATA')""",
        (unit["request_kind"], NOW.isoformat(), unit["request_key"]),
    )
    connection.commit()

    result = factory._execute_preclose_critical_phase(
        connection,
        _claim(connection, step),
        timeout_seconds=1.0,
        context_adapter_factories=_goplus_factories(calls),
        claimed_at=NOW,
    )

    assert calls == []
    assert result["ok"] is False
    assert result["blocked_reason"] == "CONTEXT_INTEGRITY_BLOCKED"


def test_terminal_checkpoint_is_never_executed_again(
    connection: sqlite3.Connection,
) -> None:
    calls: list[str] = []
    step = _claim(
        connection,
        _only_pending(connection, _add_preclose(connection), "SAFETY_PRIMARY"),
    )
    result = factory._execute_preclose_critical_phase(
        connection,
        step,
        timeout_seconds=1.0,
        context_adapter_factories=_goplus_factories(calls),
        claimed_at=NOW,
    )
    assert result["yield_required"] is False
    connection.execute(
        """UPDATE printer_memory_factory_run_steps
           SET step_status='SUCCEEDED',result_json=? WHERE id=?""",
        (json.dumps(result, sort_keys=True), int(step["id"])),
    )
    connection.commit()
    terminal = connection.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
        (int(step["id"]),),
    ).fetchone()

    replay = factory._execute_preclose_critical_phase(
        connection,
        terminal,
        timeout_seconds=1.0,
        context_adapter_factories=_goplus_factories(calls),
        claimed_at=NOW,
    )

    assert replay["ok"] is True
    assert replay["yield_required"] is False
    assert calls == ["goplus"]
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_source_requests"
    ).fetchone()[0] == 1


def test_positive_preclose_reservation_requires_bound_unit_identity(
    connection: sqlite3.Connection,
) -> None:
    step = _add_preclose(connection)
    with pytest.raises(ValueError, match="PRE_CLOSE_RESERVATION_UNIT_IDENTITY_INVALID"):
        factory._lifecycle_reservation_records_for_step(
            run_id="preclose-run", pending=step, projected_requests=1
        )


def test_impossible_lead_is_typed_unschedulable_with_zero_provider_calls(
    connection: sqlite3.Connection,
) -> None:
    step = _add_preclose(
        connection,
        close_at=NOW + timedelta(seconds=1),
        earliest_at=NOW,
    )
    payload = json.loads(str(step["result_json"]))

    assert payload["preclose_plan_state"] == "TIMELY_ACQUISITION_NOT_PRODUCIBLE"
    assert datetime.fromisoformat(str(step["scheduled_for"])) == NOW
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_source_requests"
    ).fetchone()[0] == 0
    calls: list[str] = []
    claimed = _claim(connection, step)
    assert factory._projected_requests_for_step(connection, claimed) == 0
    assert factory._lifecycle_reservation_records_for_step(
        run_id="preclose-run", pending=claimed, projected_requests=0
    ) == []
    result = factory._execute_preclose_critical_phase(
        connection,
        claimed,
        timeout_seconds=1.0,
        context_adapter_factories=_goplus_factories(calls),
        claimed_at=NOW,
    )
    assert result["terminal_job_status"] == "SKIPPED"
    assert result["blocked_reason"] == "TIMELY_ACQUISITION_NOT_PRODUCIBLE"
    assert calls == []
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_source_requests"
    ).fetchone()[0] == 0


def test_terminal_unit_service_count_survives_yield_and_drives_token_fairness(
    connection: sqlite3.Connection,
) -> None:
    first = _add_preclose(connection, token_id=1)
    second = _add_preclose(connection, token_id=2)
    payload = json.loads(str(first["result_json"]))
    payload["terminal_unit_count"] = 1
    connection.execute(
        "UPDATE printer_memory_factory_run_steps SET result_json=? WHERE id=?",
        (json.dumps(payload, sort_keys=True), int(first["id"])),
    )
    connection.execute(
        "UPDATE printer_scheduler_jobs SET scheduled_for=? WHERE id IN (?,?)",
        (NOW.isoformat(), int(first["scheduler_job_id"]), int(second["scheduler_job_id"])),
    )
    connection.commit()

    selected = factory._select_next_pending_step(
        connection, run_id="preclose-run", now=NOW
    )

    assert selected is not None
    assert int(selected["token_id"]) == 2
    assert str(selected["step_kind"]) in PRE_CLOSE_STEP_KINDS


def test_overlapping_two_token_lead_is_one_frozen_contention_cohort(
    connection: sqlite3.Connection,
) -> None:
    first = _add_preclose(connection, token_id=1)
    first_before = json.loads(str(first["result_json"]))
    second = _add_preclose(connection, token_id=2)
    rows = connection.execute(
        """SELECT result_json,scheduled_for
           FROM printer_memory_factory_run_steps
           WHERE run_id='preclose-run'
             AND step_kind='WINDOW_CLOSE_PRE_CLOSE_CRITICAL'
           ORDER BY token_id"""
    ).fetchall()
    payloads = [json.loads(str(row["result_json"])) for row in rows]

    assert len(payloads) == 2
    assert len({item["contention_cohort_identity"] for item in payloads}) == 1
    assert all(item["contention_cohort_unit_count"] == 14 for item in payloads)
    assert len({item["desired_preclose_scheduled_for"] for item in payloads}) == 1
    assert datetime.fromisoformat(
        payloads[0]["desired_preclose_scheduled_for"]
    ) < datetime.fromisoformat(
        first_before["standalone_desired_preclose_scheduled_for"]
    )
    assert {str(row["scheduled_for"]) for row in rows} == {
        payloads[0]["effective_preclose_scheduled_for"]
    }


def test_multi_cycle_preclose_service_has_no_permanent_cycle_preference(
    connection: sqlite3.Connection,
) -> None:
    cycle_1 = _add_preclose(connection, cycle_id="cycle-1")
    cycle_2 = _add_preclose(connection, cycle_id="cycle-2")
    cycle_3 = _add_preclose(connection, cycle_id="cycle-3")
    for step, count in ((cycle_1, 1), (cycle_2, 0), (cycle_3, 0)):
        payload = json.loads(str(step["result_json"]))
        payload["terminal_unit_count"] = count
        connection.execute(
            "UPDATE printer_memory_factory_run_steps SET result_json=? WHERE id=?",
            (json.dumps(payload, sort_keys=True), int(step["id"])),
        )
        connection.execute(
            "UPDATE printer_scheduler_jobs SET scheduled_for=? WHERE id=?",
            (NOW.isoformat(), int(step["scheduler_job_id"])),
        )
    connection.commit()

    selected = factory._select_next_pending_step(
        connection, run_id="preclose-run", now=NOW
    )
    assert selected is not None
    selected_payload = json.loads(str(selected["result_json"]))
    assert selected_payload["cycle_id"] == "cycle-2"

    selected_payload["terminal_unit_count"] = 1
    connection.execute(
        "UPDATE printer_memory_factory_run_steps SET result_json=? WHERE id=?",
        (json.dumps(selected_payload, sort_keys=True), int(selected["id"])),
    )
    connection.commit()
    selected = factory._select_next_pending_step(
        connection, run_id="preclose-run", now=NOW
    )
    assert selected is not None
    assert json.loads(str(selected["result_json"]))["cycle_id"] == "cycle-3"


@pytest.mark.parametrize(
    "track_kind",
    (JobKind.TRACK_FAST_FIRST_15M, JobKind.TRACK_NORMAL_FIRST_15M),
)
def test_track_work_due_after_yield_gets_global_reselection_before_next_unit(
    connection: sqlite3.Connection,
    track_kind: JobKind,
) -> None:
    step = _add_preclose(connection)
    connection.execute(
        "UPDATE printer_scheduler_jobs SET scheduled_for=? WHERE id=?",
        (NOW.isoformat(), int(step["scheduler_job_id"])),
    )
    cursor = connection.execute(
        """INSERT INTO printer_scheduler_jobs(
               job_name,job_kind,priority,status,scheduled_for,created_at,updated_at)
           VALUES ('track',? ,?,'PENDING',?,?,?)""",
        (
            track_kind.value,
            JOB_PRIORITY_VALUE[track_kind],
            NOW.isoformat(),
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    connection.execute(
        """INSERT INTO printer_memory_factory_run_steps(
               run_id,step_key,step_kind,step_status,token_id,pair_id,
               token_mint,pair_address,tracking_lane,scheduled_for,
               scheduler_job_id,created_at,updated_at)
               VALUES ('preclose-run','track','SNAPSHOT','PENDING',2,1002,
                       'mint-2','pair-2','TRACK_FAST',?,?,?,?)""",
        (
            NOW.isoformat(), int(cursor.lastrowid), NOW.isoformat(), NOW.isoformat()
        ),
    )
    connection.commit()

    selected = factory._select_next_pending_step(
        connection, run_id="preclose-run", now=NOW
    )

    assert selected is not None
    assert str(selected["step_key"]) == "track"


@pytest.mark.parametrize(
    ("family", "role", "offset_seconds", "expected_state"),
    (
        ("WINDOW_CLOSE", "SAFETY_PRIMARY", 0, "TIMELY"),
        ("WINDOW_CLOSE", "SAFETY_PRIMARY", 1, "LATE"),
        ("CONTINUATION_CLOSE", "SAFETY_PRIMARY", 1, "LATE"),
        ("LONG_CONTINUATION_CLOSE", "SAFETY_PRIMARY", 60, "TIMELY"),
        ("LONG_CONTINUATION_CLOSE", "SAFETY_PRIMARY", 61, "LATE"),
        ("LONG_CONTINUATION_CLOSE", "EXIT_QUOTE", 60, "TIMELY"),
        ("LONG_CONTINUATION_CLOSE", "EXIT_QUOTE", 61, "LATE"),
        ("LONG_CONTINUATION_CLOSE", "MARKET_CHAIN", 1, "LATE"),
    ),
)
def test_real_provider_observation_uses_only_family_specific_cutoff(
    connection: sqlite3.Connection,
    family: str,
    role: str,
    offset_seconds: int,
    expected_state: str,
) -> None:
    close_at = NOW + timedelta(minutes=15)
    step = _only_pending(
        connection,
        _add_preclose(connection, family=family, close_at=close_at),
        role,
    )
    calls: list[str] = []
    source_name = (
        "coingecko"
        if role == "MARKET_CHAIN"
        else "jupiter_quote"
        if role == "EXIT_QUOTE"
        else "goplus"
    )
    factories = {
        source_name: _timed_factory(
            source_name,
            close_at + timedelta(seconds=offset_seconds),
            calls,
            payload={
                "token_mint": "mint-1",
                "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
            },
        )
    }
    result = factory._execute_preclose_critical_phase(
        connection,
        _claim(connection, step),
        timeout_seconds=1.0,
        context_adapter_factories=factories,
        claimed_at=NOW,
    )
    terminal = next(
        unit
        for unit in result["source_unit_manifest"]
        if unit["source_unit_identity"] == role
    )

    assert calls == [source_name]
    assert terminal["state"] == expected_state
    assert terminal["observed_at"] == (
        close_at + timedelta(seconds=offset_seconds)
    ).isoformat()
    if family in {"WINDOW_CLOSE", "CONTINUATION_CLOSE"} or role == "MARKET_CHAIN":
        assert terminal["acquisition_cutoff_at"] == close_at.isoformat()
    else:
        assert terminal["acquisition_cutoff_at"] == (
            close_at + timedelta(seconds=60)
        ).isoformat()


def test_15m_zero_allowance_is_frozen_in_real_preclose_manifest(
    connection: sqlite3.Connection,
) -> None:
    close_at = NOW + timedelta(minutes=15)
    payload = json.loads(str(_add_preclose(connection, close_at=close_at)["result_json"]))

    assert payload["window_end_at"] == close_at.isoformat()
    assert {
        unit["acquisition_cutoff_at"]
        for unit in payload["source_unit_manifest"]
    } == {close_at.isoformat()}


def test_real_observation_is_bound_after_snapshot_without_timestamp_rewrite(
    connection: sqlite3.Connection,
) -> None:
    observed_at = NOW + timedelta(seconds=5)
    step = _only_pending(
        connection, _add_preclose(connection), "SAFETY_PRIMARY"
    )
    calls: list[str] = []
    result = factory._execute_preclose_critical_phase(
        connection,
        _claim(connection, step),
        timeout_seconds=1.0,
        context_adapter_factories={
            "goplus": _timed_factory(
                "goplus",
                observed_at,
                calls,
                payload={
                    "token_mint": "mint-1",
                    "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
                },
            )
        },
        claimed_at=NOW,
    )
    snapshot_at = NOW + timedelta(seconds=10)
    snapshot_id = int(
        connection.execute(
            """INSERT INTO printer_token_snapshots(
                   token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                   source_status,data_quality_label)
               VALUES (1,1001,?,'TRACK_FAST','TOKEN_SNAPSHOT',
                       'COMPLETE','CLEAN_DATA')""",
            (snapshot_at.isoformat(),),
        ).lastrowid
    )
    connection.commit()
    persisted_step = connection.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
        (int(step["id"]),),
    ).fetchone()
    bundle = factory._rehydrate_preclose_context_bundle(connection, result)
    request_count = connection.execute(
        "SELECT COUNT(*) FROM printer_source_requests"
    ).fetchone()[0]
    persistence = factory._persist_preclose_context(
        connection,
        step=persisted_step,
        snapshot_id=snapshot_id,
        context_bundle=bundle,
    )
    composite_id = int(persistence["safety_composite"]["composite_id"])
    composite = connection.execute(
        """SELECT snapshot_id,evidence_captured_at
           FROM printer_safety_evidence_composites WHERE id=?""",
        (composite_id,),
    ).fetchone()
    contribution = connection.execute(
        """SELECT captured_at FROM printer_safety_evidence_contributions
           WHERE composite_id=? ORDER BY id LIMIT 1""",
        (composite_id,),
    ).fetchone()

    assert calls == ["goplus"]
    assert int(composite["snapshot_id"]) == snapshot_id
    assert composite["evidence_captured_at"] == observed_at.isoformat()
    assert contribution["captured_at"] == observed_at.isoformat()
    assert persistence["safety_composite"]["evidence_observed_at"] == (
        observed_at.isoformat()
    )
    assert persistence["safety_composite"]["evidence_evaluated_at"] not in {
        observed_at.isoformat(),
        snapshot_at.isoformat(),
    }
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_source_requests"
    ).fetchone()[0] == request_count


def test_split_claims_preserve_old_success_branch_provider_call_count(
    connection: sqlite3.Connection,
) -> None:
    old_calls: list[str] = []
    old_step = _add_preclose(connection, token_id=1)
    old_bundle = factory._collect_preclose_context(
        connection,
        old_step,
        timeout_seconds=1.0,
        adapter_factories=_all_success_factories(old_calls),
    )
    assert old_bundle["report"]["source_requests_attempted"] == 6

    new_calls: list[str] = []
    new_step = _add_preclose(connection, token_id=2)
    # The success-path payload must target token 2 while preserving the same
    # source set; build factories afresh for each bounded claim.
    factories = _all_success_factories(new_calls, token_mint="mint-2")
    while True:
        current = connection.execute(
            "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
            (int(new_step["id"]),),
        ).fetchone()
        claimed = _claim(connection, current)
        result = factory._execute_preclose_critical_phase(
            connection,
            claimed,
            timeout_seconds=1.0,
            context_adapter_factories=factories,
            claimed_at=NOW,
        )
        if result.get("yield_required"):
            factory._checkpoint_and_yield_preclose_claim(
                connection, step=claimed, result=result, now=NOW
            )
            continue
        break

    assert len(new_calls) == len(old_calls) == 6
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_source_requests WHERE request_key LIKE '%preclose:%'"
    ).fetchone()[0] == 6

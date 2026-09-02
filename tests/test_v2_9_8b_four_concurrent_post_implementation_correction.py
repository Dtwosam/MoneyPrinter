"""Post-implementation corrections: txn cleanup, campaign-wide waits, overlap."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from printer_v1.db import apply_migrations
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    ACQUISITION_DEADLINE_EXHAUSTED,
    WAITING_FOR_ELIGIBLE_SUPPLY,
    insert_refresh_wait,
    mark_refresh_wait_claimed,
)
from printer_v1.discovery.pre_lifecycle_refresh_work import insert_refresh_work
from printer_v1.operator_cli.cadence_authority import (
    claim_tracking_authority_for_slot_insert,
)
from printer_v1.operator_cli.campaign_ownership import (
    create_cycle_with_two_slots,
    cycle_scoped_token_slot_id,
    persist_window,
    transition_state,
)
from printer_v1.operator_cli.four_token_factory_adapter import (
    parent_interrupted_attempt_cause,
    reconcile_parent_interrupted_open_pre_admission_attempts,
)
from printer_v1.operator_cli.four_token_operational_composition import (
    exact_operational_policy,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    FourTokenAdmissionDisposition,
    FourTokenAdmissionDispositionKind,
    cycle_step_key,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
    MultiCycleCampaignBinding,
    admit_two_token_cycle,
    load_multi_cycle_campaign_snapshot,
    multi_cycle_configuration_contract,
)
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    AdmissionDecision,
    MultiCycleCapacityPolicy,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    _classify_owned_1h_terminal_state,
    _insert_step_and_job,
    _later_cycle_attempt_is_terminal,
    _run_four_token_admission_boundary,
    _select_next_pending_step,
)
from printer_v1.operator_cli.operational_selective_1h import campaign_window_id_for
from printer_v1.operator_cli.pre_admission_discovery_attempt import (
    PreAdmissionAttemptState,
    create_scheduled_pre_admission_attempt,
    mark_pre_admission_attempt_running,
    pre_admission_attempt_lock_owner,
    terminalize_pre_admission_attempt,
)
from printer_v1.operator_cli.pre_lifecycle_persistent_refresh_owner import (
    PreLifecycleTemporalRefreshOwner,
)
from printer_v1.operator_cli.unified_terminal_closure import reconcile_campaign_terminal
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import (
    cancel_job,
    claim_due_job,
    complete_job,
    enqueue_job,
    fail_job,
)


NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
PARENT_CAUSE = "LEASE_RENEWAL_SQLITE_LOCKED"
EXPECTED_CAUSE = parent_interrupted_attempt_cause(PARENT_CAUSE)
POLICY = MultiCycleCapacityPolicy(
    configured_through_4h_token_ceiling=4,
    configured_active_cycle_ceiling=2,
    total_cycle_admission_ceiling=2,
    intake_duration_seconds=18_000,
)
BINDING = MultiCycleCampaignBinding(
    campaign_id="campaign-1",
    campaign_run_id="campaign-run-1",
    configuration_id="configuration-1",
    authoritative_factory_run_id="factory-1",
)
HEALTH = MultiCycleAdmissionHealth()
LIFECYCLE = "PUMPSWAP_GRADUATED_CONFIRMED"


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _prepare(tmp_path: Path, *, cycle1_terminal: bool = True) -> Path:
    path = tmp_path / "correction.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    stamp = _iso(NOW)
    configuration = {
        "token_capacity": 2,
        "ceilings": {"cycle_count": 2},
        "multi_cycle_capacity": multi_cycle_configuration_contract(
            POLICY, intake_started_at=NOW
        ),
    }
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        (
            "campaign-1",
            "RUNNING",
            "OPERATIONAL_PERSISTENT",
            "db-1",
            "policy-1",
            stamp,
            stamp,
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json,created_at) VALUES (?,?,?,?,?,?)",
        (
            "configuration-1",
            "campaign-1",
            "a" * 64,
            json.dumps(configuration, sort_keys=True),
            "{}",
            stamp,
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "factory-1",
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            json.dumps(
                {
                    "four_token_proof": True,
                    "campaign_id": "campaign-1",
                    "campaign_run_id": "campaign-run-1",
                    "configuration_id": "configuration-1",
                },
                sort_keys=True,
            ),
            stamp,
            stamp,
            stamp,
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        (
            "campaign-run-1",
            "campaign-1",
            1,
            "RUNNING",
            "factory-1",
            stamp,
            stamp,
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_cycles("
        "cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,first_terminal_cause,"
        "terminal_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "cycle-1",
            "campaign-1",
            "campaign-run-1",
            1,
            "TERMINAL_BLOCKED" if cycle1_terminal else "TRACKING",
            PARENT_CAUSE if cycle1_terminal else None,
            stamp if cycle1_terminal else None,
            stamp,
            stamp,
        ),
    )
    connection.commit()
    connection.close()
    return path


def _open(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _insert_token_pair(
    connection: sqlite3.Connection, *, token_id: int, pair_id: int
) -> None:
    connection.execute(
        "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?, 'solana')",
        (token_id, f"mint-{token_id}"),
    )
    connection.execute(
        "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
        "VALUES (?,?,?,?)",
        (pair_id, token_id, f"pool-{token_id}", f"mint-{token_id}"),
    )


def _cycle1_untouched_job(connection: sqlite3.Connection) -> int:
    _insert_token_pair(connection, token_id=11, pair_id=111)
    result, job_id = enqueue_job(
        connection,
        job_name="cycle1-untouched",
        job_kind=JobKind.TRACK_FAST_1H,
        scheduled_for=NOW,
    )
    assert result is LockResult.ACQUIRED
    assert job_id is not None
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_token_slots("
        "token_slot_id,campaign_id,run_id,cycle_id,slot_ordinal,token_identity,"
        "token_row_id,mint_identity,pair_identity,pair_row_id,lifecycle_identity,"
        "token_state,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "slot-cycle-1-1",
            "campaign-1",
            "campaign-run-1",
            "cycle-1",
            1,
            "solana-mainnet:mint-11",
            11,
            "mint-11",
            "pool-11",
            111,
            LIFECYCLE,
            "WINDOW_1H_CONTINUING",
            _iso(NOW),
            _iso(NOW),
        ),
    )
    connection.commit()
    return int(job_id)


def _make_attempt(
    connection: sqlite3.Connection,
    *,
    running: bool,
    proposed_cycle_id: str = "cycle-2",
) -> tuple[str, int]:
    attempt = create_scheduled_pre_admission_attempt(
        connection,
        attempt_id="attempt-c2",
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        configuration_id="configuration-1",
        authoritative_factory_run_id="factory-1",
        proposed_cycle_ordinal=2,
        proposed_cycle_id=proposed_cycle_id,
        cycle_cutoff=NOW,
        evaluated_at=NOW,
        selection_seed_identity="seed-2",
        scheduled_for=NOW,
        now=NOW,
    )
    if running:
        claimed = claim_due_job(
            connection,
            job_id=attempt.scheduler_job_id,
            lock_owner=pre_admission_attempt_lock_owner(attempt.attempt_id),
            now=NOW,
        )
        assert claimed is LockResult.ACQUIRED
        mark_pre_admission_attempt_running(
            connection, attempt_id=attempt.attempt_id, now=NOW
        )
    connection.commit()
    return attempt.attempt_id, int(attempt.scheduler_job_id)


def _insert_refresh(
    connection: sqlite3.Connection,
    *,
    wait_state: str,
    cycle_id: str = "cycle-2",
    campaign_id: str = "campaign-1",
    run_id: str = "campaign-run-1",
    with_work: bool = False,
) -> tuple[str, int]:
    result, job_id = enqueue_job(
        connection,
        job_name=f"PRE_LIFECYCLE_DISCOVERY_REFRESH:{campaign_id}:{run_id}:{cycle_id}:1",
        job_kind=JobKind.DISCOVERY_REFRESH,
        scheduled_for=NOW,
    )
    assert job_id is not None
    wait_id = f"prelifecycle-refresh-wait:{campaign_id}:{run_id}:{cycle_id}:1"
    insert_refresh_wait(
        connection,
        wait_id=wait_id,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        supervision_id="supervision-1",
        scheduler_job_id=int(job_id),
        refresh_ordinal=1,
        scheduled_for=_iso(NOW),
        acquisition_deadline_at=_iso(NOW + timedelta(seconds=2400)),
        now=_iso(NOW),
    )
    if wait_state == "CLAIMED":
        mark_refresh_wait_claimed(connection, wait_id=wait_id, now=_iso(NOW))
        if with_work:
            insert_refresh_work(
                connection,
                refresh_work_id=(
                    f"prelifecycle-refresh-work:{campaign_id}:{run_id}:{cycle_id}:1"
                ),
                wait_id=wait_id,
                campaign_id=campaign_id,
                run_id=run_id,
                cycle_id=cycle_id,
                supervision_id="supervision-1",
                scheduler_job_id=int(job_id),
                refresh_ordinal=1,
                work_deadline_at=_iso(NOW + timedelta(seconds=18000)),
                now=_iso(NOW),
            )
    connection.commit()
    return wait_id, int(job_id)


def _integrity(connection: sqlite3.Connection) -> None:
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def _assert_interrupt_durable(
    path: Path,
    *,
    attempt_id: str,
    attempt_job_id: int,
    wait_id: str,
    refresh_job_id: int,
    cycle1_job_id: int,
    expect_work: bool,
) -> None:
    connection = _open(path)
    try:
        attempt = connection.execute(
            "SELECT attempt_state,first_terminal_cause FROM "
            "printer_pre_admission_discovery_attempts WHERE attempt_id=?",
            (attempt_id,),
        ).fetchone()
        attempt_job = connection.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id=?",
            (attempt_job_id,),
        ).fetchone()
        wait = connection.execute(
            "SELECT wait_state,first_terminal_cause FROM "
            "printer_pre_lifecycle_discovery_refresh_waits WHERE wait_id=?",
            (wait_id,),
        ).fetchone()
        refresh_job = connection.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id=?",
            (refresh_job_id,),
        ).fetchone()
        cycle1_job = connection.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id=?",
            (cycle1_job_id,),
        ).fetchone()
        slot = connection.execute(
            "SELECT token_state FROM printer_memory_factory_campaign_token_slots "
            "WHERE token_slot_id='slot-cycle-1-1'"
        ).fetchone()
        assert attempt["attempt_state"] == "CANCELLED"
        assert attempt["first_terminal_cause"] == EXPECTED_CAUSE
        assert attempt_job["status"] == "CANCELLED"
        assert wait["wait_state"] == "CANCELLED"
        assert wait["first_terminal_cause"] == EXPECTED_CAUSE
        assert refresh_job["status"] == "CANCELLED"
        assert cycle1_job["status"] == "PENDING"
        assert slot["token_state"] == "WINDOW_1H_CONTINUING"
        if expect_work:
            work = connection.execute(
                "SELECT work_state,first_terminal_cause FROM "
                "printer_pre_lifecycle_discovery_refresh_work WHERE wait_id=?",
                (wait_id,),
            ).fetchone()
            assert work["work_state"] in {"FAILED", "CANCELLED"}
            assert work["first_terminal_cause"] == EXPECTED_CAUSE
        _integrity(connection)
    finally:
        connection.close()


def test_parent_interrupt_running_attempt_waiting_wait_persists(tmp_path: Path) -> None:
    path = _prepare(tmp_path)
    connection = _open(path)
    cycle1_job = _cycle1_untouched_job(connection)
    attempt_id, attempt_job = _make_attempt(connection, running=True)
    wait_id, refresh_job = _insert_refresh(connection, wait_state="WAITING")
    report = reconcile_parent_interrupted_open_pre_admission_attempts(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        now=NOW,
    )
    connection.close()
    assert report["replay_state"] == "A"
    _assert_interrupt_durable(
        path,
        attempt_id=attempt_id,
        attempt_job_id=attempt_job,
        wait_id=wait_id,
        refresh_job_id=refresh_job,
        cycle1_job_id=cycle1_job,
        expect_work=False,
    )


def test_parent_interrupt_running_attempt_claimed_wait_persists(tmp_path: Path) -> None:
    path = _prepare(tmp_path)
    connection = _open(path)
    cycle1_job = _cycle1_untouched_job(connection)
    attempt_id, attempt_job = _make_attempt(connection, running=True)
    wait_id, refresh_job = _insert_refresh(
        connection, wait_state="CLAIMED", with_work=True
    )
    report = reconcile_parent_interrupted_open_pre_admission_attempts(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        now=NOW,
    )
    connection.close()
    assert report["replay_state"] == "A"
    _assert_interrupt_durable(
        path,
        attempt_id=attempt_id,
        attempt_job_id=attempt_job,
        wait_id=wait_id,
        refresh_job_id=refresh_job,
        cycle1_job_id=cycle1_job,
        expect_work=True,
    )


def test_parent_interrupt_job_already_cancelled_plus_wait(tmp_path: Path) -> None:
    path = _prepare(tmp_path)
    connection = _open(path)
    cycle1_job = _cycle1_untouched_job(connection)
    attempt_id, attempt_job = _make_attempt(connection, running=True)
    cancel_job(connection, job_id=attempt_job, now=NOW)
    wait_id, refresh_job = _insert_refresh(connection, wait_state="WAITING")
    connection.commit()
    report = reconcile_parent_interrupted_open_pre_admission_attempts(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        now=NOW,
    )
    connection.close()
    assert report["replay_state"] == "C"
    _assert_interrupt_durable(
        path,
        attempt_id=attempt_id,
        attempt_job_id=attempt_job,
        wait_id=wait_id,
        refresh_job_id=refresh_job,
        cycle1_job_id=cycle1_job,
        expect_work=False,
    )


def test_parent_interrupt_replay_after_success(tmp_path: Path) -> None:
    path = _prepare(tmp_path)
    connection = _open(path)
    cycle1_job = _cycle1_untouched_job(connection)
    attempt_id, attempt_job = _make_attempt(connection, running=True)
    wait_id, refresh_job = _insert_refresh(connection, wait_state="WAITING")
    first = reconcile_parent_interrupted_open_pre_admission_attempts(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        now=NOW,
    )
    second = reconcile_parent_interrupted_open_pre_admission_attempts(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        now=NOW,
    )
    connection.close()
    assert first["replay_state"] == "A"
    assert second["replay_state"] == "D"
    assert second["idempotent_replay"] is True
    _assert_interrupt_durable(
        path,
        attempt_id=attempt_id,
        attempt_job_id=attempt_job,
        wait_id=wait_id,
        refresh_job_id=refresh_job,
        cycle1_job_id=cycle1_job,
        expect_work=False,
    )


def test_campaign_terminal_with_cycle1_id_catches_cycle2_waiting_wait(
    tmp_path: Path,
) -> None:
    path = _prepare(tmp_path)
    connection = _open(path)
    _insert_token_pair(connection, token_id=11, pair_id=111)
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_token_slots("
        "token_slot_id,campaign_id,run_id,cycle_id,slot_ordinal,token_identity,"
        "token_row_id,mint_identity,pair_identity,pair_row_id,lifecycle_identity,"
        "token_state,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "slot-cycle-1-1",
            "campaign-1",
            "campaign-run-1",
            "cycle-1",
            1,
            "solana-mainnet:mint-11",
            11,
            "mint-11",
            "pool-11",
            111,
            LIFECYCLE,
            "SELECTED",
            _iso(NOW),
            _iso(NOW),
        ),
    )
    connection.commit()
    wait_id, refresh_job = _insert_refresh(connection, wait_state="WAITING")
    other_wait, other_job = _insert_refresh(
        connection,
        wait_state="WAITING",
        cycle_id="other-cycle",
        campaign_id="other-campaign",
        run_id="other-run",
    )
    connection.close()
    reconcile_campaign_terminal(
        path,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        terminal_cause=PARENT_CAUSE,
        run_status="SAFE_STOPPED",
        factory_run_id="factory-1",
        lifecycle_started=True,
        now=_iso(NOW),
    )
    connection = _open(path)
    try:
        wait = connection.execute(
            "SELECT wait_state FROM printer_pre_lifecycle_discovery_refresh_waits "
            "WHERE wait_id=?",
            (wait_id,),
        ).fetchone()
        job = connection.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id=?",
            (refresh_job,),
        ).fetchone()
        other = connection.execute(
            "SELECT wait_state FROM printer_pre_lifecycle_discovery_refresh_waits "
            "WHERE wait_id=?",
            (other_wait,),
        ).fetchone()
        other_status = connection.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id=?",
            (other_job,),
        ).fetchone()
        assert wait["wait_state"] == "CANCELLED"
        assert job["status"] == "CANCELLED"
        assert other["wait_state"] == "WAITING"
        assert other_status["status"] == "PENDING"
        slot = connection.execute(
            "SELECT token_state FROM printer_memory_factory_campaign_token_slots "
            "WHERE token_slot_id='slot-cycle-1-1'"
        ).fetchone()
        assert slot["token_state"] in {"MANUAL_REVIEW", "COOLDOWN", "FAILED", "SELECTED"}
        _integrity(connection)
    finally:
        connection.close()


def test_campaign_terminal_with_cycle1_id_catches_cycle2_claimed_wait(
    tmp_path: Path,
) -> None:
    path = _prepare(tmp_path)
    connection = _open(path)
    wait_id, refresh_job = _insert_refresh(
        connection, wait_state="CLAIMED", with_work=True
    )
    connection.close()
    reconcile_campaign_terminal(
        path,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        terminal_cause=PARENT_CAUSE,
        run_status="SAFE_STOPPED",
        factory_run_id="factory-1",
        lifecycle_started=True,
        now=_iso(NOW),
    )
    connection = _open(path)
    try:
        wait = connection.execute(
            "SELECT wait_state FROM printer_pre_lifecycle_discovery_refresh_waits "
            "WHERE wait_id=?",
            (wait_id,),
        ).fetchone()
        work = connection.execute(
            "SELECT work_state FROM printer_pre_lifecycle_discovery_refresh_work "
            "WHERE wait_id=?",
            (wait_id,),
        ).fetchone()
        job = connection.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id=?",
            (refresh_job,),
        ).fetchone()
        assert wait["wait_state"] == "CANCELLED"
        assert work["work_state"] in {"FAILED", "CANCELLED"}
        assert job["status"] == "CANCELLED"
        _integrity(connection)
    finally:
        connection.close()


def _window_id(cycle_id: str, slot_id: str, kind: str) -> str:
    return campaign_window_id_for(
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id=cycle_id,
        token_slot_id=slot_id,
        window_kind=kind,
        period_key="factory-root",
    )


def _slot_payloads(
    cycle_id: str, token_ids: tuple[int, int], queue_ids: tuple[int, int]
) -> tuple[dict[str, object], dict[str, object]]:
    return tuple(
        {
            "token_slot_id": cycle_scoped_token_slot_id(
                cycle_id=cycle_id, slot_ordinal=slot
            ),
            "slot_ordinal": slot,
            "token_identity": f"solana-mainnet:mint-{token_id}",
            "token_row_id": token_id,
            "mint_identity": f"mint-{token_id}",
            "pair_identity": f"pool-{token_id}",
            "pair_row_id": 100 + token_id,
            "lifecycle_identity": LIFECYCLE,
            "tracking_queue_id": queue_id,
            "replacement_predecessor_slot_id": None,
        }
        for slot, token_id, queue_id in zip((1, 2), token_ids, queue_ids)
    )


def _advance_slot(
    connection: sqlite3.Connection, slot_id: str, states: tuple[str, ...]
) -> None:
    current = connection.execute(
        "SELECT token_state FROM printer_memory_factory_campaign_token_slots "
        "WHERE token_slot_id=?",
        (slot_id,),
    ).fetchone()["token_state"]
    for new_state in states:
        transition_state(
            connection,
            record_kind="token_slot",
            identity=slot_id,
            expected_state=current,
            new_state=new_state,
            now=_iso(NOW),
        )
        current = new_state


def _plan_step(
    connection: sqlite3.Connection,
    *,
    token_id: int,
    cycle_ordinal: int,
    slot_ordinal: int,
    suffix: str,
    step_kind: str,
    when: datetime,
) -> str:
    key = cycle_step_key(
        slot_ordinal=slot_ordinal, cycle_ordinal=cycle_ordinal, suffix=suffix
    )
    _insert_step_and_job(
        connection,
        run_id="factory-1",
        target={
            "token_id": token_id,
            "pair_id": 100 + token_id,
            "token_mint": f"mint-{token_id}",
            "pair_address": f"pool-{token_id}",
            "tracking_lane": "TRACK_NORMAL",
        },
        step_key=key,
        step_kind=step_kind,
        scheduled_for=when,
    )
    return key


def _slot_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            "SELECT token_slot_id,cycle_id,slot_ordinal,token_row_id,lifecycle_identity,"
            "token_state FROM printer_memory_factory_campaign_token_slots "
            "WHERE campaign_id='campaign-1' ORDER BY cycle_id,slot_ordinal"
        )
    )


def test_four_token_lifecycle_overlap_is_durable_state(tmp_path: Path) -> None:
    path = tmp_path / "overlap.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    stamp = _iso(NOW)
    configuration = {
        "token_capacity": 2,
        "ceilings": {"cycle_count": 2},
        "multi_cycle_capacity": multi_cycle_configuration_contract(
            POLICY, intake_started_at=NOW
        ),
    }
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        ("campaign-1", "RUNNING", "OPERATIONAL_PERSISTENT", "db-1", "policy-1", stamp, stamp),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json,created_at) VALUES (?,?,?,?,?,?)",
        (
            "configuration-1",
            "campaign-1",
            "a" * 64,
            json.dumps(configuration, sort_keys=True),
            "{}",
            stamp,
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "factory-1",
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            json.dumps(
                {
                    "four_token_proof": True,
                    "campaign_id": "campaign-1",
                    "campaign_run_id": "campaign-run-1",
                    "configuration_id": "configuration-1",
                },
                sort_keys=True,
            ),
            stamp,
            stamp,
            stamp,
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        ("campaign-run-1", "campaign-1", 1, "RUNNING", "factory-1", stamp, stamp),
    )
    queues: list[int] = []
    for token_id in (1, 2, 3, 4):
        _insert_token_pair(connection, token_id=token_id, pair_id=100 + token_id)
        queues.append(
            claim_tracking_authority_for_slot_insert(
                connection,
                token_row_id=token_id,
                pair_row_id=100 + token_id,
                tracking_lane="TRACK_NORMAL",
                now=NOW,
            )
        )
    connection.commit()
    create_cycle_with_two_slots(
        connection,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        cycle_ordinal=1,
        slots=_slot_payloads("cycle-1", (1, 2), (queues[0], queues[1])),
        now=_iso(NOW),
        commit_transaction=True,
    )
    transition_state(
        connection,
        record_kind="cycle",
        identity="cycle-1",
        expected_state="PLANNED",
        new_state="DISCOVERING",
        now=_iso(NOW),
    )
    for expected, nxt in (
        ("DISCOVERING", "SELECTING"),
        ("SELECTING", "TRACKING"),
    ):
        transition_state(
            connection,
            record_kind="cycle",
            identity="cycle-1",
            expected_state=expected,
            new_state=nxt,
            now=_iso(NOW),
        )
    t15 = NOW
    keys_15m: list[str] = []
    for slot_ordinal, token_id in ((1, 1), (2, 2)):
        slot_id = cycle_scoped_token_slot_id(
            cycle_id="cycle-1", slot_ordinal=slot_ordinal
        )
        persist_window(
            connection,
            window_id=_window_id("cycle-1", slot_id, "WINDOW_15M"),
            campaign_id="campaign-1",
            run_id="campaign-run-1",
            cycle_id="cycle-1",
            token_slot_id=slot_id,
            token_row_id=token_id,
            pair_row_id=100 + token_id,
            window_kind="WINDOW_15M",
            root_15m_lifecycle_identity=LIFECYCLE,
            checkpoint_cutoff=_iso(t15),
            now=_iso(t15),
        )
        keys_15m.append(
            _plan_step(
                connection,
                token_id=token_id,
                cycle_ordinal=1,
                slot_ordinal=slot_ordinal,
                suffix="snapshot_00",
                step_kind="SNAPSHOT",
                when=t15,
            )
        )
        _advance_slot(connection, slot_id, ("WINDOW_15M_ACTIVE",))
    connection.commit()
    snap = load_multi_cycle_campaign_snapshot(
        connection, binding=BINDING, policy=POLICY, now=t15 + timedelta(seconds=60)
    )
    assert snap.session.active_through_4h_tokens == 2
    assert snap.session.active_cycles == 1

    t2 = NOW + timedelta(seconds=300)
    admitted = admit_two_token_cycle(
        connection,
        binding=BINDING,
        policy=POLICY,
        now=t2,
        slots=_slot_payloads("unused", (3, 4), (queues[2], queues[3])),
        health=HEALTH,
    )
    assert admitted.mutation_performed is True
    assert admitted.cycle_id == "cycle-1-2"
    transition_state(
        connection,
        record_kind="cycle",
        identity="cycle-1-2",
        expected_state="PLANNED",
        new_state="DISCOVERING",
        now=_iso(t2),
    )
    for expected, nxt in (
        ("DISCOVERING", "SELECTING"),
        ("SELECTING", "TRACKING"),
    ):
        transition_state(
            connection,
            record_kind="cycle",
            identity="cycle-1-2",
            expected_state=expected,
            new_state=nxt,
            now=_iso(t2),
        )
    for slot_ordinal, token_id in ((1, 3), (2, 4)):
        slot_id = cycle_scoped_token_slot_id(
            cycle_id="cycle-1-2", slot_ordinal=slot_ordinal
        )
        persist_window(
            connection,
            window_id=_window_id("cycle-1-2", slot_id, "WINDOW_15M"),
            campaign_id="campaign-1",
            run_id="campaign-run-1",
            cycle_id="cycle-1-2",
            token_slot_id=slot_id,
            token_row_id=token_id,
            pair_row_id=100 + token_id,
            window_kind="WINDOW_15M",
            root_15m_lifecycle_identity=LIFECYCLE,
            checkpoint_cutoff=_iso(t2),
            now=_iso(t2),
        )
        keys_15m.append(
            _plan_step(
                connection,
                token_id=token_id,
                cycle_ordinal=2,
                slot_ordinal=slot_ordinal,
                suffix="snapshot_00",
                step_kind="SNAPSHOT",
                when=t2,
            )
        )
        _advance_slot(connection, slot_id, ("WINDOW_15M_ACTIVE",))
    connection.commit()
    slots = _slot_rows(connection)
    assert len(slots) == 4
    assert {row["token_state"] for row in slots} == {"WINDOW_15M_ACTIVE"}
    assert len(set(keys_15m)) == 4
    snap = load_multi_cycle_campaign_snapshot(
        connection, binding=BINDING, policy=POLICY, now=t2 + timedelta(seconds=60)
    )
    assert snap.session.active_through_4h_tokens == 4
    assert snap.session.active_cycles == 2
    assert set(snap.active_cycle_ids) == {"cycle-1", "cycle-1-2"}
    cycle1_active = [
        row for row in slots if row["cycle_id"] == "cycle-1"
    ]
    cycle2_active = [
        row for row in slots if row["cycle_id"] == "cycle-1-2"
    ]
    assert len(cycle1_active) == 2
    assert len(cycle2_active) == 2
    pending_15m = list(
        connection.execute(
            "SELECT step_key FROM printer_memory_factory_run_steps "
            "WHERE step_status='PENDING' AND step_kind='SNAPSHOT'"
        )
    )
    assert {row["step_key"] for row in pending_15m} == set(keys_15m)

    t1h = NOW + timedelta(minutes=20)
    keys_1h: list[str] = []
    for row in slots:
        cycle_ordinal = 1 if row["cycle_id"] == "cycle-1" else 2
        persist_window(
            connection,
            window_id=_window_id(str(row["cycle_id"]), str(row["token_slot_id"]), "WINDOW_1H"),
            campaign_id="campaign-1",
            run_id="campaign-run-1",
            cycle_id=str(row["cycle_id"]),
            token_slot_id=str(row["token_slot_id"]),
            token_row_id=int(row["token_row_id"]),
            pair_row_id=100 + int(row["token_row_id"]),
            window_kind="WINDOW_1H",
            root_15m_lifecycle_identity=str(row["lifecycle_identity"]),
            checkpoint_cutoff=_iso(t1h),
            predecessor_window_id=_window_id(
                str(row["cycle_id"]), str(row["token_slot_id"]), "WINDOW_15M"
            ),
            now=_iso(t1h),
        )
        keys_1h.append(
            _plan_step(
                connection,
                token_id=int(row["token_row_id"]),
                cycle_ordinal=cycle_ordinal,
                slot_ordinal=int(row["slot_ordinal"]),
                suffix="continuation_snapshot_00",
                step_kind="CONTINUATION_SNAPSHOT",
                when=t1h,
            )
        )
        _advance_slot(
            connection,
            str(row["token_slot_id"]),
            ("WINDOW_15M_CLOSED", "WINDOW_1H_CONTINUING"),
        )
    connection.commit()
    snap = load_multi_cycle_campaign_snapshot(
        connection, binding=BINDING, policy=POLICY, now=t1h + timedelta(minutes=1)
    )
    assert snap.session.active_through_4h_tokens == 4
    assert {row["token_state"] for row in _slot_rows(connection)} == {
        "WINDOW_1H_CONTINUING"
    }
    assert len(set(keys_1h)) == 4
    assert set(keys_1h).isdisjoint(keys_15m)

    t4h = NOW + timedelta(hours=1, minutes=5)
    keys_4h: list[str] = []
    for row in _slot_rows(connection):
        cycle_ordinal = 1 if row["cycle_id"] == "cycle-1" else 2
        persist_window(
            connection,
            window_id=_window_id(str(row["cycle_id"]), str(row["token_slot_id"]), "WINDOW_4H"),
            campaign_id="campaign-1",
            run_id="campaign-run-1",
            cycle_id=str(row["cycle_id"]),
            token_slot_id=str(row["token_slot_id"]),
            token_row_id=int(row["token_row_id"]),
            pair_row_id=100 + int(row["token_row_id"]),
            window_kind="WINDOW_4H",
            root_15m_lifecycle_identity=str(row["lifecycle_identity"]),
            checkpoint_cutoff=_iso(t4h),
            predecessor_window_id=_window_id(
                str(row["cycle_id"]), str(row["token_slot_id"]), "WINDOW_1H"
            ),
            now=_iso(t4h),
        )
        keys_4h.append(
            _plan_step(
                connection,
                token_id=int(row["token_row_id"]),
                cycle_ordinal=cycle_ordinal,
                slot_ordinal=int(row["slot_ordinal"]),
                suffix="long_continuation_snapshot_00",
                step_kind="LONG_CONTINUATION_SNAPSHOT",
                when=t4h,
            )
        )
        _advance_slot(
            connection,
            str(row["token_slot_id"]),
            ("WINDOW_1H_CLOSED", "WINDOW_4H_CONTINUING"),
        )
    connection.commit()
    snap = load_multi_cycle_campaign_snapshot(
        connection, binding=BINDING, policy=POLICY, now=t4h + timedelta(minutes=1)
    )
    assert snap.session.active_through_4h_tokens == 4
    assert {row["token_state"] for row in _slot_rows(connection)} == {
        "WINDOW_4H_CONTINUING"
    }
    assert len(set(keys_4h)) == 4
    all_keys = keys_15m + keys_1h + keys_4h
    assert len(set(all_keys)) == 12
    kinds = {
        str(item["window_kind"])
        for item in connection.execute(
            "SELECT window_kind FROM printer_memory_factory_campaign_windows "
            "WHERE campaign_id='campaign-1'"
        )
    }
    assert kinds == {"WINDOW_15M", "WINDOW_1H", "WINDOW_4H"}
    fifth = admit_two_token_cycle(
        connection,
        binding=BINDING,
        policy=POLICY,
        now=t4h + timedelta(minutes=10),
        slots=_slot_payloads("cycle-x", (5, 6), (1, 2)),
        health=HEALTH,
    )
    assert fifth.mutation_performed is False
    assert fifth.evaluation.decision != AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE

    for row in _slot_rows(connection):
        _advance_slot(connection, str(row["token_slot_id"]), ("WINDOW_4H_CLOSED",))
    for cycle_id in ("cycle-1", "cycle-1-2"):
        current = "TRACKING"
        for nxt in ("CLOSING", "AUDITING", "ROTATING"):
            transition_state(
                connection,
                record_kind="cycle",
                identity=cycle_id,
                expected_state=current,
                new_state=nxt,
                now=_iso(NOW + timedelta(hours=4)),
            )
            current = nxt
        transition_state(
            connection,
            record_kind="cycle",
            identity=cycle_id,
            expected_state="ROTATING",
            new_state="TERMINAL_COMPLETED",
            terminal_cause="FOUR_HOUR_COMPLETE",
            now=_iso(NOW + timedelta(hours=4)),
        )
    snap = load_multi_cycle_campaign_snapshot(
        connection, binding=BINDING, policy=POLICY, now=NOW + timedelta(hours=4, minutes=1)
    )
    assert snap.session.active_through_4h_tokens == 0
    assert snap.session.active_cycles == 0
    assert {row["token_state"] for row in _slot_rows(connection)} == {"WINDOW_4H_CLOSED"}
    policy = exact_operational_policy()
    assert policy["lifecycle_request_outer_ceiling"] == 476
    assert policy["lifecycle_requests_per_token"] == 118
    assert policy["lifecycle_scheduler_outer_ceiling"] == 444
    assert policy["automatic_retries"] == 0
    assert policy["endpoint_rotation"] is False
    assert policy["configured_through_4h_tokens"] == 4
    assert policy["configured_active_cycles"] == 2
    assert policy["tokens_per_cycle"] == 2
    assert int(connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]) == 0
    jobs = int(connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0])
    assert jobs <= 444
    assert int(connection.execute("SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles").fetchone()[0]) == 2
    locked = int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
            "WHERE step_key LIKE '%12h%' OR step_key LIKE '%24h%'"
        ).fetchone()[0]
    )
    assert locked == 0
    _integrity(connection)
    connection.close()


def test_cycle2_deadline_does_not_stop_cycle1_lifecycle(tmp_path: Path) -> None:
    path = _prepare(tmp_path, cycle1_terminal=False)
    connection = _open(path)
    started = NOW
    deadline = started + timedelta(seconds=2400)
    owner = PreLifecycleTemporalRefreshOwner(
        path,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1-2",
        supervision_id="supervision-1",
        source_governor=True,
        central_scheduler=True,
        acquisition_deadline_at=_iso(deadline),
        work_deadline_at=_iso(started + timedelta(seconds=18000)),
        refresh_stage=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("deadline must not run refresh stage")
        ),
        acquisition_started_at=_iso(started),
        supervision_probe=lambda: {
            "supervision_active": True,
            "cancellation_requested": False,
        },
        waiter=None,
        refresh_interval_seconds=600,
    )
    waiting = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=4,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=9,
        now=_iso(started + timedelta(seconds=10)),
    )
    assert waiting.status == WAITING_FOR_ELIGIBLE_SUPPLY
    attempt_id, _attempt_job = _make_attempt(
        connection, running=True, proposed_cycle_id="cycle-1-2"
    )
    cycle1_job = _cycle1_untouched_job(connection)
    cycle1_key = cycle_step_key(
        slot_ordinal=1, cycle_ordinal=1, suffix="continuation_snapshot_00"
    )
    _insert_step_and_job(
        connection,
        run_id="factory-1",
        target={
            "token_id": 11,
            "pair_id": 111,
            "token_mint": "mint-11",
            "pair_address": "pool-11",
            "tracking_lane": "TRACK_FAST",
        },
        step_key=cycle1_key,
        step_kind="CONTINUATION_SNAPSHOT",
        scheduled_for=deadline,
    )
    connection.commit()
    calls: list[str] = []

    def callback(**kwargs):
        calls.append("callback")
        outcome = owner.request_temporal_refresh(
            reserve_depth=0,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=9,
            now=str(kwargs["evaluated_at"]),
        )
        if outcome.status == ACQUISITION_DEADLINE_EXHAUSTED:
            terminalize_pre_admission_attempt(
                connection,
                attempt_id=attempt_id,
                state=PreAdmissionAttemptState.CANCELLED,
                cause=ACQUISITION_DEADLINE_EXHAUSTED,
                now=deadline,
            )
        return SimpleNamespace(
            attempt_id=attempt_id,
            state="CANCELLED",
            first_terminal_cause=outcome.status,
        )

    disposition = FourTokenAdmissionDisposition(
        FourTokenAdmissionDispositionKind.CYCLE_ADMISSION,
        "ADMISSION_READY",
        deadline,
        True,
    )
    result = _run_four_token_admission_boundary(
        connection=connection,
        controller=SimpleNamespace(policy=POLICY),
        binding=BINDING,
        first_cycle_id="cycle-1",
        now=deadline,
        next_due_work_at=deadline + timedelta(seconds=87),
        proof_deadline=deadline + timedelta(hours=4),
        project_health=lambda: SimpleNamespace(health=SimpleNamespace()),
        evaluate=lambda projection: disposition,
        later_cycle_callback=callback,
        admit=lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not admit")),
        materialize=lambda **kwargs: None,
        plan_opening=lambda **kwargs: None,
        acquisition_quantum_worst_case_seconds=115.0,
    )
    connection.commit()
    assert calls == ["callback"]
    assert result.admitted is False
    assert result.attempt_state == "CANCELLED"
    assert result.attempt_terminal_cause == ACQUISITION_DEADLINE_EXHAUSTED
    assert result.disposition.kind is FourTokenAdmissionDispositionKind.CYCLE_ADMISSION
    assert result.disposition.kind is not FourTokenAdmissionDispositionKind.PROOF_DEADLINE
    assert _later_cycle_attempt_is_terminal(result.attempt_state)
    wait = connection.execute(
        "SELECT wait_state,first_terminal_cause FROM "
        "printer_pre_lifecycle_discovery_refresh_waits WHERE cycle_id='cycle-1-2'"
    ).fetchone()
    assert wait["wait_state"] == "CANCELLED"
    assert "DEADLINE" in str(wait["first_terminal_cause"])
    factory = connection.execute(
        "SELECT run_status,stop_reason FROM printer_memory_factory_runs "
        "WHERE run_id='factory-1'"
    ).fetchone()
    assert factory["run_status"] == "RUNNING"
    assert factory["stop_reason"] is None
    cycle1 = connection.execute(
        "SELECT token_state FROM printer_memory_factory_campaign_token_slots "
        "WHERE token_slot_id='slot-cycle-1-1'"
    ).fetchone()
    assert cycle1["token_state"] == "WINDOW_1H_CONTINUING"
    job = connection.execute(
        "SELECT status FROM printer_scheduler_jobs WHERE id=?",
        (cycle1_job,),
    ).fetchone()
    assert job["status"] == "PENDING"
    pending = _select_next_pending_step(connection, run_id="factory-1", now=deadline)
    assert pending is not None
    assert str(pending["step_key"]) == cycle1_key
    claimed = claim_due_job(
        connection,
        job_id=int(pending["scheduler_job_id"]),
        lock_owner="v2_4:factory-1",
        now=deadline,
    )
    assert claimed is LockResult.ACQUIRED
    connection.close()
    reopened = _open(path)
    try:
        attempt = reopened.execute(
            "SELECT attempt_state,first_terminal_cause FROM "
            "printer_pre_admission_discovery_attempts WHERE attempt_id=?",
            (attempt_id,),
        ).fetchone()
        assert attempt["attempt_state"] == "CANCELLED"
        assert attempt["first_terminal_cause"] == ACQUISITION_DEADLINE_EXHAUSTED
        step = reopened.execute(
            "SELECT step_status FROM printer_memory_factory_run_steps "
            "WHERE step_key=?",
            (cycle1_key,),
        ).fetchone()
        assert step["step_status"] == "PENDING"
        _integrity(reopened)
    finally:
        reopened.close()


def test_cycle2_claimed_deadline_leaves_cycle1_running(tmp_path: Path) -> None:
    path = _prepare(tmp_path, cycle1_terminal=False)
    connection = _open(path)
    started = NOW
    deadline = started + timedelta(seconds=2400)
    stage_calls: list[int] = []

    def refresh_stage(connection, **kwargs):
        del connection
        stage_calls.append(int(kwargs["refresh_ordinal"]))
        return {
            "source_operations": 1,
            "provider_failures": 0,
            "channels_unavailable": (),
            "channels_attempted": ("fixture-source-1",),
            "channels_skipped": (),
            "cooperative_incomplete": True,
            "next_governed_request_kind": "PERSISTED_REFRESH",
            "next_governed_request_worst_case_seconds": 8.0,
            "newly_observed_exact_identities": (),
            "promoted_observation_eligible": (),
        }

    owner = PreLifecycleTemporalRefreshOwner(
        path,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1-2",
        supervision_id="supervision-1",
        source_governor=True,
        central_scheduler=True,
        acquisition_deadline_at=_iso(deadline),
        work_deadline_at=_iso(started + timedelta(seconds=18000)),
        refresh_stage=refresh_stage,
        acquisition_started_at=_iso(started),
        supervision_probe=lambda: {
            "supervision_active": True,
            "cancellation_requested": False,
        },
        waiter=None,
        refresh_interval_seconds=600,
    )
    waiting = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=4,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=9,
        now=_iso(started + timedelta(seconds=10)),
    )
    assert waiting.status == WAITING_FOR_ELIGIBLE_SUPPLY
    claimed = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=4,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=9,
        now=_iso(started + timedelta(seconds=600)),
    )
    assert claimed.status == WAITING_FOR_ELIGIBLE_SUPPLY
    assert claimed.claimed is True
    _cycle1_untouched_job(connection)
    expired = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=4,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=9,
        now=_iso(deadline),
    )
    assert expired.status == ACQUISITION_DEADLINE_EXHAUSTED
    wait = connection.execute(
        "SELECT wait_state FROM printer_pre_lifecycle_discovery_refresh_waits "
        "WHERE cycle_id='cycle-1-2'"
    ).fetchone()
    assert wait["wait_state"] == "CANCELLED"
    cycle1 = connection.execute(
        "SELECT token_state FROM printer_memory_factory_campaign_token_slots "
        "WHERE token_slot_id='slot-cycle-1-1'"
    ).fetchone()
    assert cycle1["token_state"] == "WINDOW_1H_CONTINUING"
    factory = connection.execute(
        "SELECT run_status FROM printer_memory_factory_runs WHERE run_id='factory-1'"
    ).fetchone()
    assert factory["run_status"] == "RUNNING"
    connection.close()


def test_serial_close_contention_does_not_drop_either_cycle(tmp_path: Path) -> None:
    path = tmp_path / "closes.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    stamp = _iso(NOW)
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            "factory-1",
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            json.dumps({"four_token_proof": True}, sort_keys=True),
            stamp,
            stamp,
            stamp,
        ),
    )
    due = NOW + timedelta(seconds=1)
    keys = []
    for cycle, token in ((1, 1), (1, 2), (2, 1), (2, 2)):
        token_id = cycle * 10 + token
        pair_id = cycle * 100 + token
        _insert_token_pair(connection, token_id=token_id, pair_id=pair_id)
        key = cycle_step_key(
            slot_ordinal=token,
            cycle_ordinal=cycle,
            suffix="window_close_evidence",
        )
        keys.append(key)
        result, job_id = enqueue_job(
            connection,
            job_name=f"close-{key}",
            job_kind=JobKind.MEMORY_WINDOW_CLOSE,
            scheduled_for=due,
        )
        assert job_id is not None
        connection.execute(
            """INSERT INTO printer_memory_factory_run_steps(
                   run_id,step_key,step_kind,step_status,token_id,pair_id,
                   token_mint,pair_address,tracking_lane,scheduled_for,
                   scheduler_job_id,created_at,updated_at
               ) VALUES ('factory-1',?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                key,
                "WINDOW_CLOSE_EVIDENCE",
                "PENDING",
                cycle * 10 + token,
                cycle * 100 + token,
                f"mint-{cycle}-{token}",
                f"pair-{cycle}-{token}",
                "TRACK_FAST",
                _iso(due),
                int(job_id),
                stamp,
                stamp,
            ),
        )
    connection.commit()
    served: list[str] = []
    now = due + timedelta(seconds=1)
    for index in range(4):
        pending = _select_next_pending_step(connection, run_id="factory-1", now=now)
        assert pending is not None
        served.append(str(pending["step_key"]))
        claimed = claim_due_job(
            connection,
            job_id=int(pending["scheduler_job_id"]),
            lock_owner="v2_4:factory-1",
            now=now,
        )
        assert claimed is LockResult.ACQUIRED
        if index == 3:
            fail_job(
                connection,
                job_id=int(pending["scheduler_job_id"]),
                error="WINDOW_CLOSE_EVIDENCE_DEADLINE_MISSED",
                max_retries=0,
                now=now,
            )
            connection.execute(
                "UPDATE printer_memory_factory_run_steps SET step_status='FAILED',"
                "finished_at=?,updated_at=? WHERE id=?",
                (_iso(now), _iso(now), int(pending["id"])),
            )
        else:
            connection.execute(
                "UPDATE printer_memory_factory_run_steps SET step_status='SUCCEEDED',"
                "finished_at=?,updated_at=? WHERE id=?",
                (_iso(now), _iso(now), int(pending["id"])),
            )
            complete_job(connection, job_id=int(pending["scheduler_job_id"]), now=now)
        connection.commit()
    assert sorted(served) == sorted(keys)
    leftover = _select_next_pending_step(connection, run_id="factory-1", now=now)
    assert leftover is None
    statuses = {
        str(row["step_key"]): str(row["step_status"])
        for row in connection.execute(
            "SELECT step_key,step_status FROM printer_memory_factory_run_steps"
        )
    }
    assert statuses[served[3]] == "FAILED"
    assert {statuses[key] for key in served[:3]} == {"SUCCEEDED"}
    _insert_token_pair(connection, token_id=31, pair_id=301)
    cursor = connection.execute(
        "INSERT INTO printer_memory_windows("
        "token_id,pair_id,window_kind,opened_at,memory_status,data_quality_label,"
        "do_not_train) VALUES (31,301,'WINDOW_1H',?,'DIRTY_MEMORY','DIRTY_DATA',1)",
        (_iso(NOW),),
    )
    dirty_id = int(cursor.lastrowid)
    connection.commit()
    assert _classify_owned_1h_terminal_state(connection, memory_window_row_id=dirty_id) == "DIRTY"
    _integrity(connection)
    connection.close()


def test_cooperative_resume_does_not_duplicate_source_request(tmp_path: Path) -> None:
    path = tmp_path / "resume.sqlite3"
    apply_migrations(path)
    started = NOW
    stage_ids: list[tuple[str, int, int]] = []

    def refresh_stage(connection, **kwargs):
        del connection
        stage_ids.append(
            (
                str(kwargs["refresh_work_id"]),
                int(kwargs["scheduler_job_id"]),
                int(kwargs["refresh_ordinal"]),
            )
        )
        if len(stage_ids) == 1:
            return {
                "source_operations": 1,
                "provider_failures": 0,
                "channels_unavailable": (),
                "channels_attempted": ("fixture-source-1",),
                "channels_skipped": (),
                "cooperative_incomplete": True,
                "next_governed_request_kind": "PERSISTED_REFRESH",
                "next_governed_request_worst_case_seconds": 8.0,
                "newly_observed_exact_identities": (),
                "promoted_observation_eligible": (),
            }
        return {
            "source_operations": 1,
            "provider_failures": 0,
            "channels_unavailable": (),
            "channels_attempted": ("fixture-source-1",),
            "channels_skipped": (),
            "newly_observed_exact_identities": (),
            "promoted_observation_eligible": (),
        }

    owner = PreLifecycleTemporalRefreshOwner(
        path,
        campaign_id="campaign-resume",
        run_id="run-resume",
        cycle_id="cycle-2",
        supervision_id="supervision-resume",
        source_governor=True,
        central_scheduler=True,
        acquisition_deadline_at=_iso(started + timedelta(seconds=2400)),
        work_deadline_at=_iso(started + timedelta(seconds=18000)),
        refresh_stage=refresh_stage,
        acquisition_started_at=_iso(started),
        supervision_probe=lambda: {
            "supervision_active": True,
            "cancellation_requested": False,
        },
        waiter=None,
        refresh_interval_seconds=600,
    )
    waiting = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=4,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=9,
        now=_iso(started + timedelta(seconds=10)),
    )
    assert waiting.status == WAITING_FOR_ELIGIBLE_SUPPLY
    first = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=4,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=9,
        now=_iso(started + timedelta(seconds=600)),
    )
    assert first.status == WAITING_FOR_ELIGIBLE_SUPPLY
    assert first.claimed is True
    second = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=4,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=8,
        now=_iso(started + timedelta(seconds=608)),
    )
    assert second.status != WAITING_FOR_ELIGIBLE_SUPPLY
    assert len(stage_ids) == 2
    assert stage_ids[0] == stage_ids[1]
    connection = sqlite3.connect(path)
    try:
        requests = int(
            connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]
        )
        waits = list(
            connection.execute(
                "SELECT wait_id,scheduler_job_id,refresh_ordinal FROM "
                "printer_pre_lifecycle_discovery_refresh_waits"
            )
        )
        assert requests == 0
        assert len(waits) == 1
    finally:
        connection.close()


def test_campaign_ceilings_and_locks_unchanged() -> None:
    policy = exact_operational_policy()
    assert policy["lifecycle_request_outer_ceiling"] == 476
    assert policy["lifecycle_requests_per_token"] == 118
    assert policy["lifecycle_scheduler_outer_ceiling"] == 444
    assert policy["automatic_retries"] == 0
    assert policy["endpoint_rotation"] is False
    assert policy["configured_through_4h_tokens"] == 4
    assert policy["configured_active_cycles"] == 2
    assert policy["tokens_per_cycle"] == 2
    assert policy["total_cycle_admission_ceiling"] == 2
    assert policy["long_windows_activated"] is False
    assert policy["locked_windows"] == ["WINDOW_12H", "WINDOW_24H"]

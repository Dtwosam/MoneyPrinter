"""Focused regression for token-local Standard-4H subset budgeting.

Disposable/in-memory SQLite only. No providers, operational execution, authorization,
Scheduler runtime, authoritative DB mutation, retrieval, decisions, positions, or PnL.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli import one_token_4h_runtime as four_hour_runtime
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    AdmissionDecision,
    MultiCycleAdmissionState,
    MultiCycleCapacityPolicy,
    evaluate_cycle_admission,
)


RUN_ID = "factory-run"
CAMPAIGN_ID = "campaign"
CAMPAIGN_RUN_ID = "campaign-run"
CYCLE_ID = "cycle-1"
SLOT_1 = "cycle-1-slot-1"
SLOT_2 = "cycle-1-slot-2"
CYCLE_2_ID = "cycle-2"
CYCLE_2_SLOT_1 = "cycle-2-slot-1"
CYCLE_2_SLOT_2 = "cycle-2-slot-2"


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE printer_tracking_queue(
            id INTEGER PRIMARY KEY,
            token_id INTEGER NOT NULL,
            pair_id INTEGER,
            tracking_lane TEXT NOT NULL
        );
        CREATE TABLE printer_memory_factory_campaign_token_slots(
            token_slot_id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            cycle_id TEXT NOT NULL,
            slot_ordinal INTEGER NOT NULL,
            token_row_id INTEGER NOT NULL,
            pair_row_id INTEGER NOT NULL,
            tracking_queue_id INTEGER
        );
        CREATE TABLE printer_memory_factory_run_steps(
            id INTEGER PRIMARY KEY,
            run_id TEXT NOT NULL,
            token_id INTEGER NOT NULL,
            pair_id INTEGER NOT NULL,
            tracking_lane TEXT NOT NULL,
            step_kind TEXT NOT NULL,
            step_status TEXT NOT NULL,
            step_key TEXT,
            scheduler_job_id INTEGER
        );
        CREATE TABLE printer_source_requests(
            id INTEGER PRIMARY KEY,
            request_key TEXT
        );
        """
    )
    connection.executemany(
        "INSERT INTO printer_tracking_queue(id,token_id,pair_id,tracking_lane) "
        "VALUES (?,?,?,?)",
        (
            (11, 101, 201, "TRACK_FAST"),
            (12, 102, 202, "TRACK_NORMAL"),
        ),
    )
    connection.executemany(
        """
        INSERT INTO printer_memory_factory_campaign_token_slots(
            token_slot_id,campaign_id,run_id,cycle_id,slot_ordinal,
            token_row_id,pair_row_id,tracking_queue_id
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            (SLOT_1, CAMPAIGN_ID, CAMPAIGN_RUN_ID, CYCLE_ID, 1, 101, 201, 11),
            (SLOT_2, CAMPAIGN_ID, CAMPAIGN_RUN_ID, CYCLE_ID, 2, 102, 202, 12),
        ),
    )
    return connection


def _add_cycle2_slots(connection: sqlite3.Connection) -> None:
    connection.executemany(
        "INSERT INTO printer_tracking_queue(id,token_id,pair_id,tracking_lane) "
        "VALUES (?,?,?,?)",
        (
            (13, 103, 203, "TRACK_FAST"),
            (14, 104, 204, "TRACK_NORMAL"),
        ),
    )
    connection.executemany(
        """
        INSERT INTO printer_memory_factory_campaign_token_slots(
            token_slot_id,campaign_id,run_id,cycle_id,slot_ordinal,
            token_row_id,pair_row_id,tracking_queue_id
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            (
                CYCLE_2_SLOT_1,
                CAMPAIGN_ID,
                CAMPAIGN_RUN_ID,
                CYCLE_2_ID,
                1,
                103,
                203,
                13,
            ),
            (
                CYCLE_2_SLOT_2,
                CAMPAIGN_ID,
                CAMPAIGN_RUN_ID,
                CYCLE_2_ID,
                2,
                104,
                204,
                14,
            ),
        ),
    )


def _run_config() -> dict[str, object]:
    return {
        "campaign_id": CAMPAIGN_ID,
        "campaign_run_id": CAMPAIGN_RUN_ID,
        "cycle_id": CYCLE_ID,
        "standard_four_hour_campaign": True,
        "four_token_proof": True,
    }


def _manifest(*, slot_1: bool, slot_2: bool) -> dict[str, dict[str, object]]:
    return {
        SLOT_1: {"eligible": slot_1},
        SLOT_2: {"eligible": slot_2},
    }


def _insert_close(
    connection: sqlite3.Connection,
    *,
    step_id: int,
    token_id: int,
    pair_id: int,
    lane: str,
) -> None:
    connection.execute(
        """
        INSERT INTO printer_memory_factory_run_steps(
            id,run_id,token_id,pair_id,tracking_lane,step_kind,step_status
        ) VALUES (?,?,?,?,?,'CONTINUATION_CLOSE','SUCCEEDED')
        """,
        (step_id, RUN_ID, token_id, pair_id, lane),
    )


def _budget(
    connection: sqlite3.Connection,
    *,
    manifests: dict[str, dict[str, object]],
    scoped_step_ids: tuple[int, ...],
) -> dict[str, object]:
    with (
        patch.object(factory, "_load_run_config", return_value=_run_config()),
        patch(
            "printer_v1.operator_cli.one_token_4h_runtime."
            "load_standard_four_hour_eligibility_manifests",
            return_value=manifests,
        ),
        patch(
            "printer_v1.operator_cli.four_token_proof_integration."
            "cycle_scoped_factory_step_ids",
            return_value=scoped_step_ids,
        ),
    ):
        return factory._standard_four_hour_cumulative_budget_for_run(
            connection,
            RUN_ID,
            cycle_id=CYCLE_ID,
        )


def test_dirty_15m_slot_without_1h_close_does_not_poison_eligible_peer_budget() -> None:
    connection = _connection()
    try:
        _insert_close(
            connection,
            step_id=1,
            token_id=101,
            pair_id=201,
            lane="TRACK_FAST",
        )
        budget = _budget(
            connection,
            manifests=_manifest(slot_1=True, slot_2=False),
            scoped_step_ids=(1,),
        )
    finally:
        connection.close()

    assert budget["tracking_lanes"] == ("TRACK_FAST", "TRACK_NORMAL")
    assert budget["continuing_mask"] == (True, False)
    assert budget["continuation_count"] == 1


def test_ineligible_after_1h_close_keeps_canonical_lane_without_4h_budget() -> None:
    connection = _connection()
    try:
        _insert_close(
            connection,
            step_id=1,
            token_id=101,
            pair_id=201,
            lane="TRACK_FAST",
        )
        _insert_close(
            connection,
            step_id=2,
            token_id=102,
            pair_id=202,
            lane="TRACK_NORMAL",
        )
        budget = _budget(
            connection,
            manifests=_manifest(slot_1=True, slot_2=False),
            scoped_step_ids=(1, 2),
        )
    finally:
        connection.close()

    assert budget["tracking_lanes"] == ("TRACK_FAST", "TRACK_NORMAL")
    assert budget["continuing_mask"] == (True, False)
    assert "token_2_window_4h_phase" not in budget["request_components"]


def test_eligible_slot_still_requires_exact_successful_1h_close() -> None:
    connection = _connection()
    try:
        _insert_close(
            connection,
            step_id=1,
            token_id=101,
            pair_id=201,
            lane="TRACK_FAST",
        )
        with pytest.raises(
            ValueError,
            match="close identity missing/ambiguous",
        ):
            _budget(
                connection,
                manifests=_manifest(slot_1=True, slot_2=True),
                scoped_step_ids=(1,),
            )
    finally:
        connection.close()


def test_close_lane_must_match_canonical_tracking_authority() -> None:
    connection = _connection()
    try:
        _insert_close(
            connection,
            step_id=1,
            token_id=101,
            pair_id=201,
            lane="TRACK_NORMAL",
        )
        with pytest.raises(ValueError, match="tracking lane mismatch"):
            _budget(
                connection,
                manifests=_manifest(slot_1=True, slot_2=False),
                scoped_step_ids=(1,),
            )
    finally:
        connection.close()


def test_subset_integrity_fault_is_not_misreported_as_numeric_budget_breach() -> None:
    step = {
        "step_kind": "LONG_CONTINUATION_SNAPSHOT",
        "step_key": "t1_4h_snapshot_001",
        "tracking_lane": "TRACK_FAST",
        "scheduler_job_id": None,
    }
    config = {
        "standard_four_hour_campaign": True,
        "four_token_proof": False,
    }
    with (
        patch.object(factory, "_load_run_config", return_value=config),
        patch.object(
            factory,
            "_standard_four_hour_cumulative_budget_for_run",
            side_effect=ValueError("subset ownership mismatch"),
        ),
    ):
        with pytest.raises(factory._GlobalStop) as raised:
            factory._enforce_budgets_before_step(
                object(),
                RUN_ID,
                step,
                projected_requests=0,
            )

    assert raised.value.reason == factory.STOP_PREFLIGHT
    assert raised.value.scope == "STANDARD_FOUR_HOUR_SUBSET_INTEGRITY"
    assert "subset ownership mismatch" in str(raised.value.detail)


def test_true_four_hour_numeric_ceiling_still_safe_stops_as_budget() -> None:
    connection = _connection()
    step = {
        "step_kind": "LONG_CONTINUATION_SNAPSHOT",
        "step_key": "t1_4h_snapshot_001",
        "tracking_lane": "TRACK_FAST",
        "scheduler_job_id": None,
    }
    config = {
        "standard_four_hour_campaign": True,
        "four_token_proof": False,
    }
    budget = {
        "phase_request_ceiling": 0,
        "request_components": {"discovery": 0},
        "request_ceiling": 100,
    }
    try:
        with (
            patch.object(factory, "_load_run_config", return_value=config),
            patch.object(
                factory,
                "_standard_four_hour_cumulative_budget_for_run",
                return_value=budget,
            ),
            patch.object(factory, "_run_request_count", return_value=0),
        ):
            with pytest.raises(factory._GlobalStop) as raised:
                factory._enforce_budgets_before_step(
                    connection,
                    RUN_ID,
                    step,
                    projected_requests=1,
                )
    finally:
        connection.close()

    assert raised.value.reason == factory.STOP_BUDGET
    assert raised.value.scope == "FOUR_HOUR_PHASE"


def test_both_eligible_slots_keep_the_existing_two_token_subset_budget() -> None:
    connection = _connection()
    try:
        _insert_close(
            connection,
            step_id=1,
            token_id=101,
            pair_id=201,
            lane="TRACK_FAST",
        )
        _insert_close(
            connection,
            step_id=2,
            token_id=102,
            pair_id=202,
            lane="TRACK_NORMAL",
        )
        budget = _budget(
            connection,
            manifests=_manifest(slot_1=True, slot_2=True),
            scoped_step_ids=(1, 2),
        )
    finally:
        connection.close()

    assert budget["tracking_lanes"] == ("TRACK_FAST", "TRACK_NORMAL")
    assert budget["continuing_mask"] == (True, True)
    assert budget["continuation_count"] == 2
    assert "token_1_window_4h_phase" in budget["request_components"]
    assert "token_2_window_4h_phase" in budget["request_components"]


def test_cycle2_capacity_remains_available_after_one_cycle1_token_stops_locally() -> None:
    started = datetime(2026, 9, 4, 13, 0, tzinfo=timezone.utc)
    policy = MultiCycleCapacityPolicy(
        configured_through_4h_token_ceiling=4,
        configured_active_cycle_ceiling=2,
        total_cycle_admission_ceiling=2,
        intake_duration_seconds=18_000,
    )
    state = MultiCycleAdmissionState(
        now=started + timedelta(minutes=10),
        intake_started_at=started,
        active_through_4h_tokens=1,
        active_cycles=1,
        admissions_completed=1,
        last_cycle_admitted_at=started,
    )

    result = evaluate_cycle_admission(policy, state)

    assert result.decision == AdmissionDecision.ADMIT_TWO_TOKEN_CYCLE


def test_cycle_scoped_4h_counts_ignore_peer_cycle_but_keep_current_orphans() -> None:
    connection = _connection()
    try:
        _add_cycle2_slots(connection)
        connection.executemany(
            """
            INSERT INTO printer_memory_factory_run_steps(
                id,run_id,token_id,pair_id,tracking_lane,step_kind,step_status,
                step_key,scheduler_job_id
            ) VALUES (?,?,?,?,?,'LONG_CONTINUATION_SNAPSHOT','SUCCEEDED',?,?)
            """,
            (
                (10, RUN_ID, 101, 201, "TRACK_FAST", "t101_p201_4h_snapshot_000", 1010),
                (20, RUN_ID, 103, 203, "TRACK_FAST", "t103_p203_4h_snapshot_000", 2020),
            ),
        )
        connection.executemany(
            "INSERT INTO printer_source_requests(id,request_key) VALUES (?,?)",
            (
                (100, f"{RUN_ID}:t101_p201_4h_snapshot_000"),
                (101, f"{RUN_ID}:t101_p201_4h_snapshot_000:fallback"),
                (200, f"{RUN_ID}:t103_p203_4h_snapshot_000"),
            ),
        )

        assert four_hour_runtime._standard_campaign_cycle_long_step_count(
            connection,
            campaign_id=CAMPAIGN_ID,
            campaign_run_id=CAMPAIGN_RUN_ID,
            cycle_id=CYCLE_ID,
            factory_run_id=RUN_ID,
        ) == 1
        assert four_hour_runtime._standard_campaign_cycle_long_step_count(
            connection,
            campaign_id=CAMPAIGN_ID,
            campaign_run_id=CAMPAIGN_RUN_ID,
            cycle_id=CYCLE_2_ID,
            factory_run_id=RUN_ID,
        ) == 1
        assert four_hour_runtime._standard_campaign_cycle_scheduler_step_count(
            connection,
            campaign_id=CAMPAIGN_ID,
            campaign_run_id=CAMPAIGN_RUN_ID,
            cycle_id=CYCLE_ID,
            factory_run_id=RUN_ID,
        ) == 1
        assert four_hour_runtime._standard_campaign_cycle_scheduler_step_count(
            connection,
            campaign_id=CAMPAIGN_ID,
            campaign_run_id=CAMPAIGN_RUN_ID,
            cycle_id=CYCLE_2_ID,
            factory_run_id=RUN_ID,
        ) == 1
        assert factory._standard_campaign_cycle_request_count(
            connection,
            factory_run_id=RUN_ID,
            campaign_id=CAMPAIGN_ID,
            campaign_run_id=CAMPAIGN_RUN_ID,
            cycle_id=CYCLE_ID,
            long_only=True,
        ) == 2
        assert factory._standard_campaign_cycle_request_count(
            connection,
            factory_run_id=RUN_ID,
            campaign_id=CAMPAIGN_ID,
            campaign_run_id=CAMPAIGN_RUN_ID,
            cycle_id=CYCLE_2_ID,
            long_only=True,
        ) == 1

        connection.execute(
            """
            INSERT INTO printer_memory_factory_run_steps(
                id,run_id,token_id,pair_id,tracking_lane,step_kind,step_status,
                step_key,scheduler_job_id
            ) VALUES (11,?,?,?,?, 'SUCCEEDED',?,NULL)
            """,
            (
                RUN_ID,
                102,
                202,
                "TRACK_NORMAL",
                "LONG_CONTINUATION_SNAPSHOT",
                "t102_p202_4h_orphan",
            ),
        )
        assert four_hour_runtime._standard_campaign_cycle_long_step_count(
            connection,
            campaign_id=CAMPAIGN_ID,
            campaign_run_id=CAMPAIGN_RUN_ID,
            cycle_id=CYCLE_ID,
            factory_run_id=RUN_ID,
        ) == 2
    finally:
        connection.close()


def test_cycle2_4h_budget_does_not_charge_cycle1_requests() -> None:
    connection = _connection()
    try:
        _add_cycle2_slots(connection)
        connection.execute(
            """
            INSERT INTO printer_memory_factory_run_steps(
                id,run_id,token_id,pair_id,tracking_lane,step_kind,step_status,
                step_key,scheduler_job_id
            ) VALUES (10,?,?,?,?, 'SUCCEEDED',?,?)
            """,
            (
                RUN_ID,
                101,
                201,
                "TRACK_FAST",
                "LONG_CONTINUATION_SNAPSHOT",
                "t101_p201_4h_snapshot_000",
                1010,
            ),
        )
        connection.executemany(
            "INSERT INTO printer_source_requests(id,request_key) VALUES (?,?)",
            tuple(
                (
                    1000 + index,
                    f"{RUN_ID}:t101_p201_4h_snapshot_000:peer-{index}",
                )
                for index in range(20)
            ),
        )
        step = {
            "step_kind": "LONG_CONTINUATION_SNAPSHOT",
            "step_key": "t103_p203_4h_snapshot_000",
            "tracking_lane": "TRACK_FAST",
            "scheduler_job_id": 2020,
        }
        config = {
            "campaign_id": CAMPAIGN_ID,
            "campaign_run_id": CAMPAIGN_RUN_ID,
            "standard_four_hour_campaign": True,
            "four_token_proof": True,
        }
        budget = {
            "phase_request_ceiling": 1,
            "request_components": {"discovery": 2},
            "request_ceiling": 3,
        }
        with (
            patch.object(factory, "_load_run_config", return_value=config),
            patch.object(
                factory,
                "_standard_four_hour_cumulative_budget_for_run",
                return_value=budget,
            ),
            patch(
                "printer_v1.operator_cli.four_token_proof_integration."
                "resolve_owned_cycle_for_scheduler_job",
                return_value=SimpleNamespace(cycle_id=CYCLE_2_ID),
            ),
        ):
            factory._enforce_budgets_before_step(
                connection,
                RUN_ID,
                step,
                projected_requests=1,
            )
    finally:
        connection.close()

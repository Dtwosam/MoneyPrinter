"""Focused regression for token-local Standard-4H subset budgeting.

Disposable/in-memory SQLite only. No providers, operational execution, authorization,
Scheduler runtime, authoritative DB mutation, retrieval, decisions, positions, or PnL.
"""
from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

from printer_v1.operator_cli import one_command_15m_factory as factory


RUN_ID = "factory-run"
CAMPAIGN_ID = "campaign"
CAMPAIGN_RUN_ID = "campaign-run"
CYCLE_ID = "cycle-1"
SLOT_1 = "cycle-1-slot-1"
SLOT_2 = "cycle-1-slot-2"


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
            step_status TEXT NOT NULL
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

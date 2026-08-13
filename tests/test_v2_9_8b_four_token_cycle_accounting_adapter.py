from __future__ import annotations

import json
import sqlite3
from datetime import timedelta

import pytest

from printer_v1.operator_cli import four_token_factory_adapter as adapter
from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli import one_token_4h_runtime
from printer_v1.operator_cli.campaign_ownership import (
    campaign_scheduler_work_id,
    project_campaign_scheduler_job,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    _plan_anchored_jobs,
    _plan_opening_jobs,
)
from tests.test_v2_9_8b_callback_consume_materialize_integration import (
    BINDING,
    NOW,
    _prepare_database,
)
from tests.test_v2_9_8b_post_dtw100_standard_four_hour_campaign_planning import (
    StandardFourHourCampaignPlanningTests,
)


def _planned_cycle(tmp_path):
    path, _request_id, _response_id = _prepare_database(tmp_path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute(
        "UPDATE printer_memory_factory_runs SET config_json=? WHERE run_id=?",
        (json.dumps({
            "four_token_proof": True,
            "campaign_id": BINDING.campaign_id,
            "campaign_run_id": BINDING.campaign_run_id,
            "configuration_id": BINDING.configuration_id,
        }, sort_keys=True), BINDING.authoritative_factory_run_id),
    )
    targets = [dict(row) for row in connection.execute(
        "SELECT token_row_id AS token_id,pair_row_id AS pair_id,"
        "mint_identity AS token_mint,pair_identity AS pair_address,"
        "'TRACK_NORMAL' AS tracking_lane "
        "FROM printer_memory_factory_campaign_token_slots "
        "WHERE cycle_id='cycle-1' ORDER BY slot_ordinal"
    ).fetchall()]
    _plan_opening_jobs(
        connection,
        BINDING.authoritative_factory_run_id,
        targets,
        NOW,
        cycle_ordinal=1,
        four_token_proof=True,
    )
    step = connection.execute(
        "SELECT step_key FROM printer_memory_factory_run_steps "
        "WHERE run_id=? ORDER BY id LIMIT 1",
        (BINDING.authoritative_factory_run_id,),
    ).fetchone()
    request_id = int(connection.execute(
        "INSERT INTO printer_source_requests("
        "source_name,request_kind,requested_at,request_key,source_status,"
        "data_quality_label) VALUES "
        "('dexscreener','pair',?,?, 'COMPLETE','CLEAN_DATA')",
        (NOW.isoformat(), f"{BINDING.authoritative_factory_run_id}:{step[0]}:proof"),
    ).lastrowid)
    connection.execute(
        "INSERT INTO printer_source_responses("
        "source_request_id,source_name,received_at,source_status,data_quality_label) "
        "VALUES (?,'dexscreener',?,'COMPLETE','CLEAN_DATA')",
        (request_id, NOW.isoformat()),
    )
    connection.commit()
    return connection, request_id


def _build(connection):
    return adapter.build_four_token_cycle_accounting_package(
        connection,
        campaign_id=BINDING.campaign_id,
        campaign_run_id=BINDING.campaign_run_id,
        factory_run_id=BINDING.authoritative_factory_run_id,
        cycle_id="cycle-1",
    )


def _succeed_owned_steps(connection, *, step_kinds, snapshot_seed: int) -> None:
    rows = connection.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE run_id='factory-run-1' "
        f"AND step_kind IN ({','.join('?' for _ in step_kinds)}) "
        "AND scheduler_job_id IS NOT NULL ORDER BY scheduled_for,id",
        tuple(step_kinds),
    ).fetchall()
    for index, row in enumerate(rows, start=1):
        snapshot_id = row["snapshot_id"]
        if snapshot_id is None:
            snapshot_id = snapshot_seed + index
            connection.execute(
                "INSERT INTO printer_token_snapshots("
                "id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,"
                "source_status,data_quality_label) VALUES "
                "(?,?,?,?,?,'TOKEN','COMPLETE','CLEAN_DATA')",
                (
                    int(snapshot_id),
                    int(row["token_id"]),
                    int(row["pair_id"]),
                    str(row["scheduled_for"]),
                    str(row["tracking_lane"]),
                ),
            )
        connection.execute(
            "UPDATE printer_memory_factory_run_steps SET step_status='SUCCEEDED',"
            "snapshot_id=?,started_at=scheduled_for,finished_at=scheduled_for,"
            "updated_at=scheduled_for WHERE id=?",
            (int(snapshot_id), int(row["id"])),
        )
        connection.execute(
            "UPDATE printer_scheduler_jobs SET status='SUCCEEDED',"
            "started_at=scheduled_for,finished_at=scheduled_for,updated_at=scheduled_for,"
            "locked_at=NULL,lock_owner=NULL WHERE id=?",
            (int(row["scheduler_job_id"]),),
        )
        factory._sync_owned_campaign_scheduler_job(
            connection, scheduler_job_id=int(row["scheduler_job_id"])
        )


def _completed_cycle():
    helper = StandardFourHourCampaignPlanningTests()
    fx, candidates = helper._prepared()
    connection = fx.connection
    candidates[0]["tracking_lane"] = "TRACK_NORMAL"

    targets = [
        {
            "token_id": int(candidate["token_row_id"]),
            "pair_id": int(candidate["pair_row_id"]),
            "token_mint": str(candidate["mint_identity"]),
            "pair_address": str(candidate["pair_identity"]),
            "tracking_lane": str(candidate["tracking_lane"]),
        }
        for candidate in candidates
    ]
    before_ids = {
        int(row[0])
        for row in connection.execute(
            "SELECT id FROM printer_memory_factory_run_steps"
        ).fetchall()
    }
    _plan_opening_jobs(connection, "factory-run-1", targets, NOW)
    for opening in connection.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE run_id='factory-run-1' "
        "AND step_kind='SNAPSHOT' ORDER BY id"
    ).fetchall():
        _plan_anchored_jobs(
            connection,
            run_id="factory-run-1",
            opening_step=opening,
            first_snapshot_captured_at=str(opening["scheduled_for"]),
            window_seconds=900.0,
        )
    new_15m = connection.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE run_id='factory-run-1' "
        "AND step_kind IN ('SNAPSHOT','WINDOW_CLOSE') "
        "AND scheduler_job_id IS NOT NULL ORDER BY id"
    ).fetchall()
    assert all(int(row["id"]) not in before_ids for row in new_15m)
    for row in new_15m:
        slot = connection.execute(
            "SELECT token_slot_id FROM printer_memory_factory_campaign_token_slots "
            "WHERE campaign_id='campaign-1h' AND run_id='run-1h' "
            "AND cycle_id='cycle-1h' AND token_row_id=? AND pair_row_id=?",
            (int(row["token_id"]), int(row["pair_id"])),
        ).fetchone()
        window = connection.execute(
            "SELECT window_id FROM printer_memory_factory_campaign_windows "
            "WHERE campaign_id='campaign-1h' AND run_id='run-1h' "
            "AND cycle_id='cycle-1h' AND token_slot_id=? AND window_kind='WINDOW_15M'",
            (str(slot[0]),),
        ).fetchone()
        project_campaign_scheduler_job(
            connection,
            scheduler_work_id=campaign_scheduler_work_id(
                "campaign-1h", int(row["scheduler_job_id"])
            ),
            campaign_id="campaign-1h",
            run_id="run-1h",
            cycle_id="cycle-1h",
            token_slot_id=str(slot[0]),
            window_id=str(window[0]),
            factory_run_id="factory-run-1",
            work_intent=f"WINDOW_15M_{row['step_kind']}",
            deadline_at=str(row["scheduled_for"]),
            scheduler_job_id=int(row["scheduler_job_id"]),
            stage_id="WINDOW_15M",
        )
    _succeed_owned_steps(
        connection,
        step_kinds=("SNAPSHOT", "WINDOW_CLOSE"),
        snapshot_seed=30000,
    )
    _succeed_owned_steps(
        connection,
        step_kinds=("CONTINUATION_SNAPSHOT", "CONTINUATION_CLOSE"),
        snapshot_seed=40000,
    )
    # The inherited handoff fixture intentionally makes only token 1's close a
    # mixed-lane row.  Normalize that fixture artifact to the canonical
    # TRACK_NORMAL plan shared by its other twelve 1h observations.
    connection.execute(
        "UPDATE printer_memory_factory_run_steps SET tracking_lane='TRACK_NORMAL' "
        "WHERE run_id='factory-run-1' AND token_id=1 AND pair_id=1 "
        "AND step_kind LIKE 'CONTINUATION_%'"
    )
    connection.commit()

    planned = one_token_4h_runtime.plan_standard_campaign_4h_handoff(
        connection,
        campaign_id="campaign-1h",
        run_id="run-1h",
        cycle_id="cycle-1h",
        factory_run_id="factory-run-1",
        candidates=candidates,
        execution_authority=(
            one_token_4h_runtime.FourHourExecutionAuthority.STANDARD_CAMPAIGN
        ),
        now=(NOW + timedelta(hours=1)).isoformat(),
    )
    assert planned["planned"] is True and planned["replay"] is False
    _succeed_owned_steps(
        connection,
        step_kinds=("LONG_CONTINUATION_SNAPSHOT", "LONG_CONTINUATION_CLOSE"),
        snapshot_seed=50000,
    )
    for candidate in candidates:
        token_id = int(candidate["token_row_id"])
        pair_id = int(candidate["pair_row_id"])
        steps = connection.execute(
            "SELECT * FROM printer_memory_factory_run_steps WHERE run_id='factory-run-1' "
            "AND token_id=? AND pair_id=? AND step_kind LIKE 'LONG_CONTINUATION_%' "
            "ORDER BY scheduled_for,id",
            (token_id, pair_id),
        ).fetchall()
        close = next(
            row for row in steps if str(row["step_kind"]) == "LONG_CONTINUATION_CLOSE"
        )
        window = connection.execute(
            "SELECT window_id FROM printer_memory_factory_campaign_windows "
            "WHERE campaign_id='campaign-1h' AND run_id='run-1h' "
            "AND cycle_id='cycle-1h' AND token_slot_id=? AND window_kind='WINDOW_4H'",
            (str(candidate["token_slot_id"]),),
        ).fetchone()
        connection.execute(
            "UPDATE printer_memory_factory_campaign_windows SET window_state='CLOSE_PENDING' "
            "WHERE window_id=?",
            (str(window[0]),),
        )
        memory_id = int(
            connection.execute(
                "INSERT INTO printer_memory_windows("
                "token_id,pair_id,window_kind,opened_at,closed_at,window_start_at,"
                "window_end_at,snapshot_start_id,snapshot_end_id,memory_status,"
                "data_quality_label,window_status,memory_quality_label,outcome_label,"
                "do_not_train,supporting_context_json) VALUES "
                "(?,?,'WINDOW_4H',?,?,?,?,?,?,'DIRTY_MEMORY','DIRTY_DATA',"
                "'WINDOW_CLOSED','DIRTY_MEMORY','CONSOLIDATION',1,'{}')",
                (
                    token_id,
                    pair_id,
                    str(steps[0]["scheduled_for"]),
                    str(steps[-1]["scheduled_for"]),
                    str(steps[0]["scheduled_for"]),
                    str(steps[-1]["scheduled_for"]),
                    int(steps[0]["snapshot_id"]),
                    int(steps[-1]["snapshot_id"]),
                ),
            ).lastrowid
        )
        binding = factory._bind_owned_long_memory_window_at_close(
            connection,
            scheduler_job_id=int(close["scheduler_job_id"]),
            memory_window_row_id=memory_id,
            result={"memory_pipeline": {"lane_k_status": "LANE_K_BLOCKED", "memory": None}},
        )
        assert binding is not None and binding["window_state"] == "DIRTY"

    first_step = connection.execute(
        "SELECT step_key FROM printer_memory_factory_run_steps "
        "WHERE run_id='factory-run-1' AND scheduler_job_id IS NOT NULL ORDER BY id LIMIT 1"
    ).fetchone()
    request_id = int(
        connection.execute(
            "INSERT INTO printer_source_requests("
            "source_name,request_kind,requested_at,request_key,source_status,"
            "data_quality_label) VALUES "
            "('dexscreener','pair',?,?,'COMPLETE','CLEAN_DATA')",
            (NOW.isoformat(), f"factory-run-1:{first_step[0]}:proof"),
        ).lastrowid
    )
    connection.execute(
        "INSERT INTO printer_source_responses("
        "source_request_id,source_name,received_at,source_status,data_quality_label) "
        "VALUES (?,'dexscreener',?,'COMPLETE','CLEAN_DATA')",
        (request_id, NOW.isoformat()),
    )
    connection.commit()
    return fx, request_id


def test_opening_only_cycle_cannot_project_structurally_safe_through_4h(
    tmp_path,
) -> None:
    connection, _request_id = _planned_cycle(tmp_path)
    writes_before = connection.total_changes
    with pytest.raises(
        adapter.FourTokenFactoryAdapterError,
        match="canonical lifecycle accounting is incomplete",
    ):
        _build(connection)
    assert connection.total_changes == writes_before
    connection.close()


def test_cycle_accounting_projects_exact_durable_scheduler_and_source_ownership(
) -> None:
    fx, request_id = _completed_cycle()
    connection = fx.connection
    writes_before = connection.total_changes
    package = adapter.build_four_token_cycle_accounting_package(
        connection,
        campaign_id="campaign-1h",
        campaign_run_id="run-1h",
        factory_run_id="factory-run-1",
        cycle_id="cycle-1h",
    )
    assert connection.total_changes == writes_before
    assert package["cycle_id"] == "cycle-1h"
    assert package["cycle_ordinal"] == 1
    assert package["factory_run_id"] == "factory-run-1"
    assert package["structurally_safe"] is True
    assert len(package["selected_targets"]) == 2
    assert package["memory_quality"] == ("PARTIAL_MEMORY", "PARTIAL_MEMORY")
    accounting = package["accounting_package"]
    assert accounting["expected_token_capacity"] == 2
    assert len(accounting["factory_step_ids"]) == 106
    assert accounting["scheduler_jobs"] == 106
    assert accounting["source_requests"] == 1
    assert accounting["source_request_ids"] == (request_id,)
    assert len(accounting["scheduler_job_ids"]) == 106
    assert len(accounting["scheduler_work_ids"]) == 106
    assert accounting["lifecycle_completeness"]["complete"] is True
    assert accounting["lifecycle_completeness"]["terminal_reconciliation_ready"] is True
    fx.close()


def test_cycle_accounting_fails_closed_on_missing_or_extra_ownership(tmp_path) -> None:
    connection, _ = _planned_cycle(tmp_path)
    connection.execute(
        "DELETE FROM printer_memory_factory_campaign_scheduler_work "
        "WHERE scheduler_work_id=("
        "SELECT scheduler_work_id FROM printer_memory_factory_campaign_scheduler_work "
        "ORDER BY scheduler_work_id LIMIT 1)"
    )
    with pytest.raises(adapter.FourTokenFactoryAdapterError, match="ownership"):
        _build(connection)

    connection.rollback()
    connection.execute(
        "INSERT INTO printer_source_requests("
        "source_name,request_kind,requested_at,request_key,source_status,"
        "data_quality_label) VALUES "
        "('dexscreener','pair',?,?, 'COMPLETE','CLEAN_DATA')",
        (NOW.isoformat(), f"{BINDING.authoritative_factory_run_id}:unowned:proof"),
    )
    connection.commit()
    with pytest.raises(adapter.FourTokenFactoryAdapterError, match="ownership"):
        _build(connection)
    connection.close()

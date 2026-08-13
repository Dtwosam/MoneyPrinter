from __future__ import annotations

import json
import sqlite3
from unittest.mock import patch

from printer_v1.operator_cli.four_token_proof_integration import (
    aggregate_four_token_cycle_acceptance,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    _standard_four_hour_cumulative_budget_for_run,
)


def _db() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE printer_memory_factory_runs(run_id TEXT PRIMARY KEY,config_json TEXT);
        CREATE TABLE printer_memory_factory_campaign_token_slots(
            campaign_id TEXT,run_id TEXT,cycle_id TEXT,token_slot_id TEXT,
            token_row_id INTEGER,pair_row_id INTEGER,slot_ordinal INTEGER
        );
        CREATE TABLE printer_memory_factory_run_steps(
            id INTEGER PRIMARY KEY,run_id TEXT,token_id INTEGER,pair_id INTEGER,
            step_kind TEXT,step_status TEXT,tracking_lane TEXT
        );
        """
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs VALUES (?,?)",
        ("factory-1", json.dumps({
            "campaign_id": "campaign-1",
            "campaign_run_id": "campaign-run-1",
            "cycle_id": "cycle-1",
            "four_token_proof": True,
        })),
    )
    for ordinal, cycle in enumerate(("cycle-1", "cycle-2"), start=1):
        for slot in (1, 2):
            token_id = ordinal * 10 + slot
            pair_id = ordinal * 100 + slot
            connection.execute(
                "INSERT INTO printer_memory_factory_campaign_token_slots VALUES (?,?,?,?,?,?,?)",
                ("campaign-1", "campaign-run-1", cycle, f"{cycle}-slot-{slot}",
                 token_id, pair_id, slot),
            )
            connection.execute(
                "INSERT INTO printer_memory_factory_run_steps VALUES (?,?,?,?,?,?,?)",
                (ordinal * 10 + slot, "factory-1", token_id, pair_id,
                 "CONTINUATION_CLOSE", "SUCCEEDED", "TRACK_NORMAL"),
            )
    return connection


def test_standard_accounting_package_is_scoped_to_requested_cycle() -> None:
    connection = _db()
    manifests = {
        "cycle-2-slot-1": {"eligible": True},
        "cycle-2-slot-2": {"eligible": False},
    }
    with (
        patch(
            "printer_v1.operator_cli.four_token_proof_integration."
            "cycle_scoped_factory_step_ids",
            return_value=(21, 22),
        ) as scoped,
        patch(
            "printer_v1.operator_cli.one_token_4h_runtime."
            "load_standard_four_hour_eligibility_manifests",
            return_value=manifests,
        ),
    ):
        package = _standard_four_hour_cumulative_budget_for_run(
            connection, "factory-1", cycle_id="cycle-2"
        )
    scoped.assert_called_once_with(
        connection,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        factory_run_id="factory-1",
        cycle_id="cycle-2",
    )
    assert package["continuing_mask"] == (True, False)


def _cycle(ordinal: int) -> dict:
    base = ordinal * 10
    return {
        "cycle_id": f"cycle-{ordinal}",
        "cycle_ordinal": ordinal,
        "factory_run_id": "factory-1",
        "structurally_safe": True,
        "selected_targets": [
            {"token_id": base + 1, "pair_id": base + 101},
            {"token_id": base + 2, "pair_id": base + 102},
        ],
        "memory_quality": ["CLEAN_MEMORY", "DIRTY_MEMORY"],
        "accounting_package": {
            "expected_token_capacity": 2,
            "factory_step_ids": (base + 1, base + 2),
            "source_requests": 200,
            "scheduler_jobs": 200,
        },
    }


def test_aggregate_acceptance_requires_two_cycle_local_packages_within_derived_capacity() -> None:
    result = aggregate_four_token_cycle_acceptance(
        [_cycle(1), _cycle(2)],
        shared={
            "campaign_id": "campaign-1",
            "campaign_run_id": "campaign-run-1",
            "factory_run_id": "factory-1",
            "admission_spacing_seconds": 300,
            "active_through_4h_peak": 4,
            "aggregate_budget_within_ceiling": True,
            "zero_active_work": True,
            "zero_forbidden_deltas": True,
            "restart_created": False,
            "successor_created": False,
            "long_windows_activated": False,
        },
    )
    assert result["accounting_package_count"] == 2
    assert result["aggregate_source_requests"] == 400
    assert result["aggregate_scheduler_jobs"] == 400


from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from printer_v1.operator_cli import four_token_proof_integration as proof
from printer_v1.operator_cli import multi_cycle_memory_growth as growth
from printer_v1.operator_cli import one_command_15m_factory as factory


RUN_ID = "budget-factory"
CAMPAIGN_ID = "budget-campaign"
CAMPAIGN_RUN_ID = "budget-run"
CYCLE_2 = "budget-cycle-2"


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE printer_source_requests("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,request_key TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE printer_memory_factory_run_steps("
        "id INTEGER PRIMARY KEY,run_id TEXT NOT NULL,step_key TEXT NOT NULL,"
        "step_kind TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO printer_memory_factory_run_steps"
        "(id,run_id,step_key,step_kind) VALUES "
        "(1,?,'t1_c0001_4h_snapshot_001','LONG_CONTINUATION_SNAPSHOT'),"
        "(2,?,'t1_c0002_4h_snapshot_001','LONG_CONTINUATION_SNAPSHOT')",
        (RUN_ID, RUN_ID),
    )
    return conn


def _config() -> dict[str, object]:
    return {
        "standard_four_hour_campaign": True,
        "four_token_proof": True,
        "campaign_id": CAMPAIGN_ID,
        "campaign_run_id": CAMPAIGN_RUN_ID,
    }


def _cycle_budget() -> dict[str, object]:
    return {
        "phase_request_ceiling": 3,
        "request_ceiling": 10,
        "request_components": {"discovery": 2},
    }


def _step() -> dict[str, object]:
    return {
        "step_kind": "LONG_CONTINUATION_SNAPSHOT",
        "tracking_lane": "TRACK_NORMAL",
        "scheduler_job_id": 202,
    }


def _patch_cycle2(monkeypatch, *, global_ceiling: int = 100) -> None:
    monkeypatch.setattr(factory, "_load_run_config", lambda *_: _config())
    monkeypatch.setattr(
        factory,
        "_standard_four_hour_cumulative_budget_for_run",
        lambda *_args, **_kwargs: _cycle_budget(),
    )
    monkeypatch.setattr(
        proof,
        "resolve_owned_cycle_for_scheduler_job",
        lambda *_args, **_kwargs: SimpleNamespace(cycle_id=CYCLE_2),
    )
    monkeypatch.setattr(
        proof,
        "cycle_scoped_factory_step_ids",
        lambda *_args, **_kwargs: (2,),
    )
    monkeypatch.setattr(
        growth,
        "scaled_standard_four_hour_capacity_contract",
        lambda configured: {
            "configured_through_4h_tokens": configured,
            "shared_discovery_requests": 4,
            "lifecycle_request_outer_ceiling": global_ceiling,
        },
    )


def test_cycle2_budget_ignores_cycle1_spend_but_keeps_its_own_ceiling(
    monkeypatch,
) -> None:
    conn = _db()
    try:
        # Cycle 1 has already spent its complete 3-request toy phase allowance.
        # Cycle 2 has spent only one request, so its next projected request is
        # lawful: 2/3 phase and 4/10 cumulative including its discovery reserve.
        conn.executemany(
            "INSERT INTO printer_source_requests(request_key) VALUES (?)",
            [
                (f"{RUN_ID}:t1_c0001_4h_snapshot_001:attempt-{i}",)
                for i in range(1, 4)
            ]
            + [(f"{RUN_ID}:t1_c0002_4h_snapshot_001:attempt-1",)],
        )
        _patch_cycle2(monkeypatch)

        # RED before repair: run-wide phase_used is 4, so projected 1 is
        # incorrectly compared to Cycle-2's ceiling 3 and raises _GlobalStop.
        factory._enforce_budgets_before_step(
            conn,
            RUN_ID,
            _step(),
            projected_requests=1,
        )
    finally:
        conn.close()


def test_cycle2_budget_still_enforces_scaled_four_token_outer_ceiling(
    monkeypatch,
) -> None:
    conn = _db()
    try:
        conn.executemany(
            "INSERT INTO printer_source_requests(request_key) VALUES (?)",
            [
                (f"{RUN_ID}:t1_c0001_4h_snapshot_001:attempt-{i}",)
                for i in range(1, 4)
            ]
            + [(f"{RUN_ID}:t1_c0002_4h_snapshot_001:attempt-1",)],
        )
        # 4 shared discovery reserve + 4 existing runtime + 1 projected = 9.
        _patch_cycle2(monkeypatch, global_ceiling=8)

        with pytest.raises(factory._GlobalStop) as caught:
            factory._enforce_budgets_before_step(
                conn,
                RUN_ID,
                _step(),
                projected_requests=1,
            )
        assert caught.value.scope == "CUMULATIVE_LIFECYCLE"
    finally:
        conn.close()

from __future__ import annotations

import sqlite3

from printer_v1.operator_cli import one_command_15m_factory as factory


RUN_ID = "report-factory"
CAMPAIGN_ID = "report-campaign"
CAMPAIGN_RUN_ID = "report-run"
CYCLE_1 = "report-cycle-1"
CYCLE_2 = "report-cycle-2"


def _budget(*, cycle_id: str, request: int, scheduler: int, phase_request: int,
            phase_scheduler: int, holder: int) -> dict[str, object]:
    discovery = 2
    return {
        "cycle_id": cycle_id,
        "expected_token_capacity": 2,
        "factory_step_ids": (1, 2),
        "phase_request_ceiling": phase_request,
        "phase_scheduler_ceiling": phase_scheduler,
        "phase_holder_fallback_ceiling": holder,
        "request_components": {
            "discovery": discovery,
            "lifecycle": request - discovery,
        },
        "request_ceiling": request,
        "scheduler_components": {"lifecycle": scheduler},
        "scheduler_ceiling": scheduler,
        "automatic_retries": 0,
        "endpoint_rotation": False,
        "real_collection_enabled": True,
    }


def test_four_token_reporting_aggregates_each_admitted_cycle_budget(
    monkeypatch,
) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE printer_memory_factory_campaign_cycles("
        "cycle_id TEXT PRIMARY KEY,campaign_id TEXT NOT NULL,run_id TEXT NOT NULL,"
        "cycle_ordinal INTEGER NOT NULL)"
    )
    conn.executemany(
        "INSERT INTO printer_memory_factory_campaign_cycles"
        "(cycle_id,campaign_id,run_id,cycle_ordinal) VALUES (?,?,?,?)",
        [
            (CYCLE_1, CAMPAIGN_ID, CAMPAIGN_RUN_ID, 1),
            (CYCLE_2, CAMPAIGN_ID, CAMPAIGN_RUN_ID, 2),
        ],
    )
    monkeypatch.setattr(
        factory,
        "_load_run_config",
        lambda *_: {
            "standard_four_hour_campaign": True,
            "four_token_proof": True,
            "campaign_id": CAMPAIGN_ID,
            "campaign_run_id": CAMPAIGN_RUN_ID,
            "cycle_id": CYCLE_1,
        },
    )
    calls: list[str | None] = []

    def derive(_conn, _run_id, *, cycle_id=None):
        calls.append(cycle_id)
        if cycle_id == CYCLE_1:
            return _budget(
                cycle_id=CYCLE_1,
                request=10,
                scheduler=20,
                phase_request=3,
                phase_scheduler=4,
                holder=1,
            )
        if cycle_id == CYCLE_2:
            return _budget(
                cycle_id=CYCLE_2,
                request=12,
                scheduler=24,
                phase_request=5,
                phase_scheduler=6,
                holder=2,
            )
        raise AssertionError(f"unexpected cycle {cycle_id}")

    monkeypatch.setattr(
        factory, "_standard_four_hour_cumulative_budget_for_run", derive
    )

    report = factory._standard_four_hour_reporting_budget_for_run(conn, RUN_ID)

    assert calls == [CYCLE_1, CYCLE_2]
    assert report["available"] is True
    budget = report["budget"]
    assert budget["request_ceiling"] == 22
    assert budget["scheduler_ceiling"] == 44
    assert budget["phase_request_ceiling"] == 8
    assert budget["phase_scheduler_ceiling"] == 10
    assert budget["phase_holder_fallback_ceiling"] == 3
    assert set(budget["per_cycle"]) == {CYCLE_1, CYCLE_2}
    assert sum(budget["request_components"].values()) == 22
    assert sum(budget["scheduler_components"].values()) == 44
    conn.close()


def test_non_four_token_reporting_preserves_single_budget_owner(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:")
    expected = _budget(
        cycle_id=CYCLE_1,
        request=10,
        scheduler=20,
        phase_request=3,
        phase_scheduler=4,
        holder=1,
    )
    monkeypatch.setattr(
        factory,
        "_load_run_config",
        lambda *_: {
            "standard_four_hour_campaign": True,
            "four_token_proof": False,
        },
    )
    calls = []

    def derive(_conn, _run_id, *, cycle_id=None):
        calls.append(cycle_id)
        return expected

    monkeypatch.setattr(
        factory, "_standard_four_hour_cumulative_budget_for_run", derive
    )

    report = factory._standard_four_hour_reporting_budget_for_run(conn, RUN_ID)
    assert calls == [None]
    assert report == {"available": True, "reason": None, "budget": expected}
    conn.close()

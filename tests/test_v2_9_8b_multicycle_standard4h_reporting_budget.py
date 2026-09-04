from __future__ import annotations

import sqlite3

from printer_v1.operator_cli import one_command_15m_factory as factory


RUN_ID = "report-budget-factory"
CAMPAIGN_ID = "report-budget-campaign"
CAMPAIGN_RUN_ID = "report-budget-run"
CYCLE_1 = "report-budget-cycle-1"
CYCLE_2 = "report-budget-cycle-2"


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE printer_memory_factory_campaign_cycles("
        "cycle_id TEXT PRIMARY KEY,campaign_id TEXT NOT NULL,run_id TEXT NOT NULL,"
        "cycle_ordinal INTEGER NOT NULL)"
    )
    conn.executemany(
        "INSERT INTO printer_memory_factory_campaign_cycles("
        "cycle_id,campaign_id,run_id,cycle_ordinal) VALUES (?,?,?,?)",
        [
            (CYCLE_1, CAMPAIGN_ID, CAMPAIGN_RUN_ID, 1),
            (CYCLE_2, CAMPAIGN_ID, CAMPAIGN_RUN_ID, 2),
        ],
    )
    return conn


def _cycle_budget(cycle_id: str) -> dict[str, object]:
    ordinal = 1 if cycle_id == CYCLE_1 else 2
    return {
        "cycle_id": cycle_id,
        "phase_request_ceiling": 10 * ordinal,
        "phase_scheduler_ceiling": 20 * ordinal,
        "phase_holder_fallback_ceiling": 2 * ordinal,
        "request_ceiling": 30 * ordinal,
        "scheduler_ceiling": 40 * ordinal,
        "request_components": {
            "discovery": 2 * ordinal,
            "window_15m": 3 * ordinal,
            "window_1h": 4 * ordinal,
            "window_4h": 5 * ordinal,
        },
        "scheduler_components": {
            "window_15m": 6 * ordinal,
            "window_1h": 7 * ordinal,
            "window_4h": 8 * ordinal,
        },
    }


def test_four_token_reporting_budget_aggregates_both_admitted_cycles(
    monkeypatch,
) -> None:
    conn = _db()
    calls: list[str | None] = []
    monkeypatch.setattr(
        factory,
        "_load_run_config",
        lambda *_: {
            "campaign_id": CAMPAIGN_ID,
            "campaign_run_id": CAMPAIGN_RUN_ID,
            "cycle_id": CYCLE_1,
            "four_token_proof": True,
            "standard_four_hour_campaign": True,
        },
    )

    def cycle_budget(_conn, _run_id, *, cycle_id=None):
        calls.append(cycle_id)
        if cycle_id is None:
            return _cycle_budget(CYCLE_1)
        return _cycle_budget(str(cycle_id))

    monkeypatch.setattr(
        factory,
        "_standard_four_hour_cumulative_budget_for_run",
        cycle_budget,
    )

    report = factory._standard_four_hour_reporting_budget_for_run(conn, RUN_ID)

    assert calls == [CYCLE_1, CYCLE_2]
    assert report["available"] is True
    budget = report["budget"]
    assert budget["cycle_count"] == 2
    assert budget["cycle_ids"] == [CYCLE_1, CYCLE_2]
    assert budget["phase_request_ceiling"] == 30
    assert budget["phase_scheduler_ceiling"] == 60
    assert budget["phase_holder_fallback_ceiling"] == 6
    assert budget["request_ceiling"] == 90
    assert budget["scheduler_ceiling"] == 120
    assert budget["request_components"] == {
        "discovery": 6,
        "window_15m": 9,
        "window_1h": 12,
        "window_4h": 15,
    }
    assert budget["scheduler_components"] == {
        "window_15m": 18,
        "window_1h": 21,
        "window_4h": 24,
    }
    conn.close()


def test_single_cycle_reporting_budget_keeps_historical_shape(monkeypatch) -> None:
    conn = _db()
    conn.execute(
        "DELETE FROM printer_memory_factory_campaign_cycles WHERE cycle_id=?",
        (CYCLE_2,),
    )
    monkeypatch.setattr(
        factory,
        "_load_run_config",
        lambda *_: {
            "campaign_id": CAMPAIGN_ID,
            "campaign_run_id": CAMPAIGN_RUN_ID,
            "cycle_id": CYCLE_1,
            "four_token_proof": False,
            "standard_four_hour_campaign": True,
        },
    )
    expected = _cycle_budget(CYCLE_1)
    monkeypatch.setattr(
        factory,
        "_standard_four_hour_cumulative_budget_for_run",
        lambda *_args, **_kwargs: expected,
    )

    report = factory._standard_four_hour_reporting_budget_for_run(conn, RUN_ID)

    assert report == {"available": True, "reason": None, "budget": expected}
    conn.close()

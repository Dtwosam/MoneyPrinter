from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from printer_v1.operator_cli import four_token_proof_integration as proof
from printer_v1.operator_cli import multi_cycle_memory_growth as growth
from printer_v1.operator_cli import one_command_15m_factory as factory


RUN_ID = "pre4h-factory"
CAMPAIGN_ID = "pre4h-campaign"
CAMPAIGN_RUN_ID = "pre4h-run"
CYCLE_2 = "pre4h-cycle-2"


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
        "step_kind TEXT NOT NULL,scheduler_job_id INTEGER,tracking_lane TEXT)"
    )
    conn.execute(
        "INSERT INTO printer_memory_factory_run_steps"
        "(id,run_id,step_key,step_kind,scheduler_job_id,tracking_lane) VALUES "
        "(1,?,'t1_c0001_snapshot_00','SNAPSHOT',101,'TRACK_NORMAL'),"
        "(2,?,'t1_c0002_snapshot_00','SNAPSHOT',202,'TRACK_NORMAL')",
        (RUN_ID, RUN_ID),
    )
    return conn


def _config() -> dict[str, object]:
    return {
        "standard_four_hour_campaign": True,
        "four_token_proof": True,
        "selective_1h_continuation": True,
        "continuous_first_hour": True,
        "campaign_id": CAMPAIGN_ID,
        "campaign_run_id": CAMPAIGN_RUN_ID,
    }


def _step(conn: sqlite3.Connection) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE id=2"
    ).fetchone()
    assert row is not None
    return row


def _patch_cycle2(monkeypatch, *, global_ceiling: int) -> None:
    monkeypatch.setattr(factory, "_load_run_config", lambda *_: _config())
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


def test_cycle2_pre4h_request_ignores_cycle1_local_spend(monkeypatch) -> None:
    conn = _db()
    try:
        local_ceiling = int(factory._SELECTIVE_1H_MAX_REQUESTS_RUN)
        # Saturate the historical two-token run ceiling entirely with Cycle-1
        # request keys. Cycle 2 itself has spent zero requests.
        conn.executemany(
            "INSERT INTO printer_source_requests(request_key) VALUES (?)",
            [
                (f"{RUN_ID}:t1_c0001_snapshot_00:attempt-{i}",)
                for i in range(local_ceiling)
            ],
        )
        _patch_cycle2(monkeypatch, global_ceiling=10_000)

        # RED before repair: the run-wide two-token ceiling sees Cycle-1 spend
        # and rejects Cycle-2 despite Cycle-2 owning a fresh local allowance.
        factory._enforce_budgets_before_step(
            conn,
            RUN_ID,
            _step(conn),
            projected_requests=1,
        )
    finally:
        conn.close()


def test_cycle2_pre4h_request_keeps_scaled_campaign_ceiling(monkeypatch) -> None:
    conn = _db()
    try:
        conn.execute(
            "INSERT INTO printer_source_requests(request_key) VALUES (?)",
            (f"{RUN_ID}:t1_c0002_snapshot_00:attempt-1",),
        )
        # 4 reserved shared discovery + 1 runtime + 1 projected = 6.
        _patch_cycle2(monkeypatch, global_ceiling=5)

        with pytest.raises(factory._GlobalStop) as caught:
            factory._enforce_budgets_before_step(
                conn,
                RUN_ID,
                _step(conn),
                projected_requests=1,
            )
        assert caught.value.scope == "CUMULATIVE_LIFECYCLE"
    finally:
        conn.close()

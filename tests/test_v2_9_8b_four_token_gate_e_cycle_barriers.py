from __future__ import annotations

import sqlite3

from printer_v1.operator_cli.one_command_15m_factory import (
    _authoritative_terminal_15m_closes,
    _operational_activated_token_count,
)


def test_cycle_barriers_do_not_merge_peer_cycle_steps() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE printer_memory_factory_run_steps(
            id INTEGER PRIMARY KEY,run_id TEXT,step_kind TEXT,step_status TEXT,
            memory_window_id INTEGER,scheduler_job_id INTEGER,token_id INTEGER,pair_id INTEGER
        );
        CREATE TABLE printer_memory_factory_campaign_scheduler_work(
            scheduler_work_id TEXT PRIMARY KEY,scheduler_job_id INTEGER,
            cycle_id TEXT,ownership_contract_version TEXT,work_scope TEXT
        );
        """
    )
    for ordinal, cycle in enumerate(("cycle-1", "cycle-2"), start=1):
        for slot in (1, 2):
            step_id = ordinal * 10 + slot
            connection.execute(
                "INSERT INTO printer_memory_factory_run_steps VALUES "
                "(?, 'factory-1','WINDOW_CLOSE','SUCCEEDED',?,?,?,?)",
                (step_id, 1000 + step_id, 2000 + step_id, step_id, 100 + step_id),
            )
            connection.execute(
                "INSERT INTO printer_memory_factory_campaign_scheduler_work VALUES "
                "(?,?,?,?, 'WINDOW_LIFECYCLE')",
                (f"work-{step_id}", 2000 + step_id, cycle, "V2_STAGE_SCOPED"),
            )
    assert _operational_activated_token_count(
        connection, "factory-1", cycle_id="cycle-1"
    ) == 2
    assert len(_authoritative_terminal_15m_closes(
        connection, "factory-1", cycle_id="cycle-1"
    )) == 2
    assert _operational_activated_token_count(
        connection, "factory-1", cycle_id="cycle-2"
    ) == 2
    assert len(_authoritative_terminal_15m_closes(
        connection, "factory-1", cycle_id="cycle-2"
    )) == 2

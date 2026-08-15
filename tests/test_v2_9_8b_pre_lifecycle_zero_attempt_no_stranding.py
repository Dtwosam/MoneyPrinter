"""V2-9.8B early-Cycle-1 terminal must not strand ownership.

The existing zero-attempt suite proves the shape terminalizes and is admitted.
This module proves the property the whole residue programme cares about: after an
early Cycle-1 pre-lifecycle terminal, no campaign, run, cycle, supervision,
tracking-queue, or factory-run ownership is left non-terminal, and the
eleven-domain zero-state projection returns to all zero.

It also proves the migration-55 counterfactual: without the migration-056
provenance table the same path fails closed *before* terminalizing, which is
exactly the stranding this repair removes.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from printer_v1.operator_cli.four_token_factory_adapter import (
    FourTokenFactoryAdapterError,
    finalize_four_token_shared_terminal,
    reconcile_four_token_cycle_terminal,
)
from printer_v1.operator_cli.four_token_proof_zero_state_gate import (
    project_four_token_proof_zero_state,
)
from tests.test_v2_9_8b_four_token_factory_wake_ordering import (
    CAMPAIGN_ID,
    CAMPAIGN_RUN_ID,
    CYCLE_ID,
    FACTORY_RUN_ID,
    START,
    _prepare,
)
from tests.test_v2_9_8b_shared_terminal_pre_lifecycle_zero_attempt import (
    _bind_factory_run,
    _shared_terminalizer,
)

MIGRATION_056_NAME = "056_four_token_pre_lifecycle_terminal_provenance.sql"


def _drop_migration_056(db: Path) -> None:
    """Return the disposable DB to the migration-55 counterfactual."""
    connection = sqlite3.connect(db)
    try:
        connection.executescript(
            "DROP TRIGGER IF EXISTS printer_pre_admission_attempt_immutable_delete;"
            "DROP TRIGGER IF EXISTS "
            "printer_pre_admission_attempt_forbids_pre_lifecycle_provenance;"
            "DROP TRIGGER IF EXISTS "
            "printer_four_token_pre_lifecycle_provenance_immutable_delete;"
            "DROP TRIGGER IF EXISTS "
            "printer_four_token_pre_lifecycle_provenance_immutable_update;"
            "DROP TRIGGER IF EXISTS "
            "printer_four_token_pre_lifecycle_provenance_exact_shape;"
            "DROP TABLE IF EXISTS "
            "printer_four_token_pre_lifecycle_terminal_provenance;"
        )
        connection.execute(
            "DELETE FROM printer_schema_migrations WHERE version=?",
            (MIGRATION_056_NAME,),
        )
        connection.commit()
    finally:
        connection.close()


def _owner_states(connection: sqlite3.Connection) -> dict[str, object]:
    one = lambda q, p=(): connection.execute(q, p).fetchone()
    return {
        "campaign": one(
            "SELECT campaign_state FROM printer_memory_factory_campaigns "
            "WHERE campaign_id=?",
            (CAMPAIGN_ID,),
        )[0],
        "run": one(
            "SELECT run_state FROM printer_memory_factory_campaign_runs "
            "WHERE run_id=?",
            (CAMPAIGN_RUN_ID,),
        )[0],
        "cycle": one(
            "SELECT cycle_state FROM printer_memory_factory_campaign_cycles "
            "WHERE cycle_id=?",
            (CYCLE_ID,),
        )[0],
        "factory_run": one(
            "SELECT run_status FROM printer_memory_factory_runs WHERE run_id=?",
            (FACTORY_RUN_ID,),
        )[0],
    }


def test_early_cycle1_terminal_leaves_no_stranded_ownership(tmp_path) -> None:
    db, _, _ = _prepare(tmp_path)
    connection = _bind_factory_run(db)

    before = _owner_states(connection)
    assert not str(before["campaign"]).startswith("TERMINAL_")
    assert not str(before["run"]).startswith("TERMINAL_")
    assert not str(before["cycle"]).startswith("TERMINAL_")

    phase_a = reconcile_four_token_cycle_terminal(
        connection,
        campaign_id=CAMPAIGN_ID,
        campaign_run_id=CAMPAIGN_RUN_ID,
        factory_run_id=FACTORY_RUN_ID,
        cycle_id=CYCLE_ID,
        cause="RUNNER_EXCEPTION",
        run_status="SAFE_STOPPED",
        terminal_phase="CAMPAIGN_PRE_LIFECYCLE",
        now=START,
    )
    assert phase_a["pre_lifecycle_zero_attempt_provenance_recorded"] is True

    result = finalize_four_token_shared_terminal(
        connection,
        campaign_id=CAMPAIGN_ID,
        campaign_run_id=CAMPAIGN_RUN_ID,
        factory_run_id=FACTORY_RUN_ID,
        shared_terminalizer=_shared_terminalizer(db),
    )
    assert result["admitted_shape"] == "ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT"
    assert result["shared_terminalized"] is True

    after = _owner_states(connection)
    assert str(after["campaign"]).startswith("TERMINAL_"), after
    assert str(after["run"]).startswith("TERMINAL_"), after
    assert str(after["cycle"]).startswith("TERMINAL_"), after
    assert after["factory_run"] != "RUNNING", after

    # No supervision or tracking-queue ownership left claimed.
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_supervision "
        "WHERE campaign_id=? AND supervision_state IN ('ACTIVE','STOPPING')",
        (CAMPAIGN_ID,),
    ).fetchone()[0] == 0
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_tracking_queue "
        "WHERE queue_status IN ('PENDING','ACTIVE','TRACK_FAST','TRACK_NORMAL')"
    ).fetchone()[0] == 0

    projection = project_four_token_proof_zero_state(connection)
    assert len(projection) == 11
    assert all(value == 0 for value in projection.values()), projection
    connection.close()


def test_without_migration_056_the_same_path_strands_ownership(tmp_path) -> None:
    """The migration-55 counterfactual this repair removes."""
    db, _, _ = _prepare(tmp_path)
    _drop_migration_056(db)
    connection = _bind_factory_run(db)

    with pytest.raises(FourTokenFactoryAdapterError) as excinfo:
        reconcile_four_token_cycle_terminal(
            connection,
            campaign_id=CAMPAIGN_ID,
            campaign_run_id=CAMPAIGN_RUN_ID,
            factory_run_id=FACTORY_RUN_ID,
            cycle_id=CYCLE_ID,
            cause="RUNNER_EXCEPTION",
            run_status="SAFE_STOPPED",
            terminal_phase="CAMPAIGN_PRE_LIFECYCLE",
            now=START,
        )
    assert "provenance table is missing" in str(excinfo.value)

    stranded = _owner_states(connection)
    assert not str(stranded["campaign"]).startswith("TERMINAL_")
    assert not str(stranded["run"]).startswith("TERMINAL_")
    assert not str(stranded["cycle"]).startswith("TERMINAL_")
    assert stranded["factory_run"] == "RUNNING"

    projection = project_four_token_proof_zero_state(connection)
    assert any(value != 0 for value in projection.values()), projection
    connection.close()

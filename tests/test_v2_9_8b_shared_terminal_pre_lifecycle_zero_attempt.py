from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import sqlite3

import pytest

from printer_v1.operator_cli.four_token_factory_adapter import (
    FourTokenFactoryAdapterError,
    finalize_four_token_shared_terminal,
    reconcile_four_token_cycle_terminal,
)
from printer_v1.operator_cli.unified_terminal_closure import reconcile_campaign_terminal
from tests.test_v2_9_8b_four_token_factory_wake_ordering import (
    CAMPAIGN_ID,
    CAMPAIGN_RUN_ID,
    CYCLE_ID,
    FACTORY_RUN_ID,
    START,
    _prepare,
)


MIGRATION_056 = Path("migrations/056_four_token_pre_lifecycle_terminal_provenance.sql")


def _bind_factory_run(db: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            FACTORY_RUN_ID,
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            "{}",
            START.isoformat(),
        ),
    )
    connection.execute(
        "UPDATE printer_memory_factory_campaign_runs "
        "SET authoritative_run_id=? WHERE campaign_id=? AND run_id=?",
        (FACTORY_RUN_ID, CAMPAIGN_ID, CAMPAIGN_RUN_ID),
    )
    connection.commit()
    return connection


def _shared_terminalizer(db: Path):
    def run():
        reconciled = reconcile_campaign_terminal(
            db,
            campaign_id=CAMPAIGN_ID,
            run_id=CAMPAIGN_RUN_ID,
            cycle_id=CYCLE_ID,
            terminal_cause="RUNNER_EXCEPTION",
            run_status="SAFE_STOPPED",
            factory_run_id=FACTORY_RUN_ID,
            lifecycle_started=False,
            now=(START + timedelta(seconds=1)).isoformat(),
        )
        return {**reconciled, "clean_terminal": True, "lease_released": True}

    return run


def _marker_count(connection: sqlite3.Connection) -> int:
    return int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_four_token_pre_lifecycle_terminal_provenance "
            "WHERE campaign_id=? AND campaign_run_id=? "
            "AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=2",
            (CAMPAIGN_ID, CAMPAIGN_RUN_ID, FACTORY_RUN_ID),
        ).fetchone()[0]
    )


def test_exact_pre_lifecycle_zero_attempt_shape_terminalizes_with_provenance(
    tmp_path,
) -> None:
    db, _, _ = _prepare(tmp_path)
    connection = _bind_factory_run(db)

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
    assert phase_a["cycle_state"].startswith("TERMINAL_")
    assert phase_a["pre_lifecycle_zero_attempt_provenance_recorded"] is True
    assert _marker_count(connection) == 1
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts "
        "WHERE campaign_id=? AND campaign_run_id=? "
        "AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=2",
        (CAMPAIGN_ID, CAMPAIGN_RUN_ID, FACTORY_RUN_ID),
    ).fetchone()[0] == 0
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
        "WHERE campaign_id=? AND run_id=? AND cycle_id=?",
        (CAMPAIGN_ID, CAMPAIGN_RUN_ID, CYCLE_ID),
    ).fetchone()[0] == 0

    result = finalize_four_token_shared_terminal(
        connection,
        campaign_id=CAMPAIGN_ID,
        campaign_run_id=CAMPAIGN_RUN_ID,
        factory_run_id=FACTORY_RUN_ID,
        shared_terminalizer=_shared_terminalizer(db),
    )
    assert result["shared_terminalized"] is True
    assert result["admitted_shape"] == "ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT"
    connection.close()


def test_zero_attempt_without_explicit_phase_does_not_gain_provenance(
    tmp_path,
) -> None:
    db, _, _ = _prepare(tmp_path)
    connection = _bind_factory_run(db)

    phase_a = reconcile_four_token_cycle_terminal(
        connection,
        campaign_id=CAMPAIGN_ID,
        campaign_run_id=CAMPAIGN_RUN_ID,
        factory_run_id=FACTORY_RUN_ID,
        cycle_id=CYCLE_ID,
        cause="RUNNER_EXCEPTION",
        run_status="SAFE_STOPPED",
        now=START,
    )
    assert phase_a["cycle_state"].startswith("TERMINAL_")
    assert phase_a["pre_lifecycle_zero_attempt_provenance_recorded"] is False
    assert _marker_count(connection) == 0

    with pytest.raises(
        FourTokenFactoryAdapterError,
        match="exact terminal no-admission evidence|pre-lifecycle zero-attempt",
    ):
        finalize_four_token_shared_terminal(
            connection,
            campaign_id=CAMPAIGN_ID,
            campaign_run_id=CAMPAIGN_RUN_ID,
            factory_run_id=FACTORY_RUN_ID,
            shared_terminalizer=lambda: {},
        )
    connection.close()


def test_zero_attempt_without_provenance_still_fails_closed(tmp_path) -> None:
    db, _, _ = _prepare(tmp_path)
    connection = _bind_factory_run(db)
    connection.execute(
        "UPDATE printer_memory_factory_campaign_cycles "
        "SET cycle_state='TERMINAL_BLOCKED',first_terminal_cause='RUNNER_EXCEPTION',"
        "terminal_at=?,updated_at=? WHERE campaign_id=? AND run_id=? AND cycle_id=?",
        (
            START.isoformat(),
            START.isoformat(),
            CAMPAIGN_ID,
            CAMPAIGN_RUN_ID,
            CYCLE_ID,
        ),
    )
    connection.commit()

    with pytest.raises(
        FourTokenFactoryAdapterError,
        match="exact terminal no-admission evidence|pre-lifecycle zero-attempt",
    ):
        finalize_four_token_shared_terminal(
            connection,
            campaign_id=CAMPAIGN_ID,
            campaign_run_id=CAMPAIGN_RUN_ID,
            factory_run_id=FACTORY_RUN_ID,
            shared_terminalizer=lambda: {},
        )
    connection.close()


def test_pre_lifecycle_provenance_is_immutable(tmp_path) -> None:
    db, _, _ = _prepare(tmp_path)
    connection = _bind_factory_run(db)
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
    assert _marker_count(connection) == 1

    with pytest.raises(sqlite3.IntegrityError, match="provenance is immutable"):
        connection.execute(
            "UPDATE printer_four_token_pre_lifecycle_terminal_provenance "
            "SET first_terminal_cause='OTHER' WHERE campaign_id=?",
            (CAMPAIGN_ID,),
        )
    connection.rollback()
    with pytest.raises(sqlite3.IntegrityError, match="provenance is immutable"):
        connection.execute(
            "DELETE FROM printer_four_token_pre_lifecycle_terminal_provenance "
            "WHERE campaign_id=?",
            (CAMPAIGN_ID,),
        )
    connection.rollback()
    connection.close()


def test_migration_056_and_attempt_delete_guard_are_present(tmp_path) -> None:
    assert MIGRATION_056.is_file()
    db, _, _ = _prepare(tmp_path)
    connection = sqlite3.connect(db)
    try:
        triggers = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            ).fetchall()
        }
        assert "printer_four_token_pre_lifecycle_provenance_exact_shape" in triggers
        assert "printer_four_token_pre_lifecycle_provenance_immutable_update" in triggers
        assert "printer_four_token_pre_lifecycle_provenance_immutable_delete" in triggers
        assert "printer_pre_admission_attempt_immutable_delete" in triggers
    finally:
        connection.close()

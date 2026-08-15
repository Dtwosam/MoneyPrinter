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


def _ensure_red_provenance_table(connection: sqlite3.Connection) -> None:
    # RED isolates the missing Python classification even before migration 056
    # exists. Once 056 lands this is a no-op because the real table already exists.
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS printer_four_token_pre_lifecycle_terminal_provenance(
            campaign_id TEXT NOT NULL,
            campaign_run_id TEXT NOT NULL,
            authoritative_factory_run_id TEXT NOT NULL,
            cycle_id TEXT NOT NULL,
            cycle_ordinal INTEGER NOT NULL,
            proposed_cycle_ordinal INTEGER NOT NULL,
            terminal_phase TEXT NOT NULL,
            first_terminal_cause TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            PRIMARY KEY(
                campaign_id,campaign_run_id,authoritative_factory_run_id,
                proposed_cycle_ordinal
            )
        )
        """
    )
    connection.commit()


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


def test_exact_pre_lifecycle_zero_attempt_shape_terminalizes_with_provenance(
    tmp_path,
) -> None:
    db, _, _ = _prepare(tmp_path)
    connection = _bind_factory_run(db)
    _ensure_red_provenance_table(connection)

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

    # Current RED code does not record the marker. Insert it only when Phase A
    # did not; after the repair the real migration forbids post-terminal inserts,
    # so this branch must not execute on GREEN.
    marker_count = connection.execute(
        "SELECT COUNT(*) FROM printer_four_token_pre_lifecycle_terminal_provenance "
        "WHERE campaign_id=? AND campaign_run_id=? "
        "AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=2",
        (CAMPAIGN_ID, CAMPAIGN_RUN_ID, FACTORY_RUN_ID),
    ).fetchone()[0]
    if marker_count == 0:
        connection.execute(
            """
            INSERT INTO printer_four_token_pre_lifecycle_terminal_provenance(
                campaign_id,campaign_run_id,authoritative_factory_run_id,
                cycle_id,cycle_ordinal,proposed_cycle_ordinal,terminal_phase,
                first_terminal_cause,recorded_at
            ) VALUES (?,?,?,?,1,2,'CAMPAIGN_PRE_LIFECYCLE',?,?)
            """,
            (
                CAMPAIGN_ID,
                CAMPAIGN_RUN_ID,
                FACTORY_RUN_ID,
                CYCLE_ID,
                "RUNNER_EXCEPTION",
                START.isoformat(),
            ),
        )
        connection.commit()

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


def test_zero_attempt_without_provenance_still_fails_closed(tmp_path) -> None:
    db, _, _ = _prepare(tmp_path)
    connection = _bind_factory_run(db)
    _ensure_red_provenance_table(connection)
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


def test_forward_only_migration_056_is_present() -> None:
    assert MIGRATION_056.is_file()

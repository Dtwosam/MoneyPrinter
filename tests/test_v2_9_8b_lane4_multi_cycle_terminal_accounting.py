"""Focused implementation checks for Lane-4 terminal accounting/reporting.

These checks use disposable identity rows and filesystem artifacts only.  They
do not run a campaign, provider, Scheduler, or authoritative database.
"""

from __future__ import annotations

from datetime import datetime, timezone
import inspect
import json
from pathlib import Path
import sqlite3

import pytest

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.campaign_full_run_accounting import (
    FullRunAccountingError,
    OperationalLifecycleOwnershipContext,
    derive_cycle_terminal_accounting_result,
    derive_two_cycle_campaign_terminal_accounting,
    build_lifecycle_action_local_observer,
)
from printer_v1.operator_cli.unified_terminal_closure import (
    TerminalClosureError,
    build_campaign_terminal_report,
    build_campaign_terminal_summary,
    write_campaign_terminal_summary,
)
from printer_v1.operator_cli.four_token_factory_adapter import (
    CAMPAIGN_STOPPED_AFTER_PEER_CYCLE_TERMINAL,
    FourTokenFactoryAdapterError,
    derive_peer_cycle_stop_effect,
    reconcile_four_token_cycle_terminal,
    resolve_peer_stop_origin_cycle_id,
)
from printer_v1.operator_cli.operational_memory_factory_command import (
    _validate_lane4_report_only_payload,
)
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignActionLocalLedger,
)


CAMPAIGN = "campaign-lane4"
CAMPAIGN_RUN = "campaign-run-lane4"
CONFIGURATION = "configuration-lane4"
FACTORY_RUN = "factory-run-lane4"


def _identity_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE printer_memory_factory_campaign_runs(
            campaign_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            authoritative_run_id TEXT,
            run_state TEXT,
            first_terminal_cause TEXT,
            terminal_at TEXT,
            PRIMARY KEY(campaign_id, run_id)
        );
        CREATE TABLE printer_memory_factory_campaign_configurations(
            campaign_id TEXT NOT NULL,
            configuration_id TEXT NOT NULL,
            PRIMARY KEY(campaign_id, configuration_id)
        );
        CREATE TABLE printer_memory_factory_campaign_cycles(
            campaign_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            cycle_id TEXT NOT NULL,
            cycle_ordinal INTEGER NOT NULL,
            cycle_state TEXT NOT NULL,
            first_terminal_cause TEXT,
            terminal_at TEXT,
            PRIMARY KEY(campaign_id, run_id, cycle_id)
        );
        CREATE TABLE printer_memory_factory_campaign_token_slots(
            campaign_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            cycle_id TEXT NOT NULL,
            token_slot_id TEXT NOT NULL,
            slot_ordinal INTEGER NOT NULL,
            token_row_id INTEGER NOT NULL,
            pair_row_id INTEGER NOT NULL,
            token_state TEXT NOT NULL,
            first_terminal_cause TEXT,
            terminal_at TEXT,
            lifecycle_identity TEXT NOT NULL DEFAULT 'lifecycle',
            mint_identity TEXT NOT NULL DEFAULT 'mint',
            pair_identity TEXT NOT NULL DEFAULT 'pair',
            tracking_queue_id INTEGER,
            PRIMARY KEY(token_slot_id)
        );
        CREATE TABLE printer_tracking_queue(
            id INTEGER PRIMARY KEY,
            tracking_lane TEXT,
            token_id INTEGER,
            pair_id INTEGER
        );
        CREATE TABLE printer_memory_factory_campaign_supervision(
            supervision_id TEXT,
            campaign_id TEXT,
            configuration_id TEXT,
            run_id TEXT,
            supervision_state TEXT,
            terminal_status TEXT,
            first_terminal_cause TEXT,
            cancellation_requested_at TEXT,
            cancellation_reason TEXT,
            cleanup_completed_at TEXT,
            lease_released_at TEXT
        );
        """
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs VALUES (?,?,?,?,?,?)",
        (CAMPAIGN, CAMPAIGN_RUN, FACTORY_RUN, "RUNNING", None, None),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations VALUES (?,?)",
        (CAMPAIGN, CONFIGURATION),
    )
    return connection


def _insert_cycle(
    connection: sqlite3.Connection,
    *,
    cycle_id: str,
    ordinal: int,
    state: str = "RUNNING",
    cause: str | None = None,
) -> None:
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_cycles VALUES (?,?,?,?,?,?,?)",
        (
            CAMPAIGN,
            CAMPAIGN_RUN,
            cycle_id,
            ordinal,
            state,
            cause,
            "2026-08-23T00:00:00+00:00" if state.startswith("TERMINAL_") else None,
        ),
    )


def _context(cycle_id: str) -> OperationalLifecycleOwnershipContext:
    return OperationalLifecycleOwnershipContext(
        campaign_id=CAMPAIGN,
        campaign_run_id=CAMPAIGN_RUN,
        cycle_id=cycle_id,
        configuration_id=CONFIGURATION,
        factory_run_id=FACTORY_RUN,
    )


def _insert_active_owned_slots(
    connection: sqlite3.Connection,
    *,
    cycle_id: str,
    token_base: int,
) -> None:
    for ordinal in (1, 2):
        token_row_id = token_base + ordinal
        pair_row_id = 200 + token_base + ordinal
        queue_id = token_base * 10 + ordinal
        connection.execute(
            "INSERT INTO printer_tracking_queue(id, tracking_lane, token_id, pair_id) "
            "VALUES (?,?,?,?)",
            (queue_id, "TRACK_FAST", token_row_id, pair_row_id),
        )
        connection.execute(
            """
            INSERT INTO printer_memory_factory_campaign_token_slots(
                campaign_id, run_id, cycle_id, token_slot_id, slot_ordinal,
                token_row_id, pair_row_id, token_state, first_terminal_cause,
                terminal_at, lifecycle_identity, mint_identity, pair_identity,
                tracking_queue_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                CAMPAIGN,
                CAMPAIGN_RUN,
                cycle_id,
                f"{cycle_id}-slot-{ordinal}",
                ordinal,
                token_row_id,
                pair_row_id,
                "WINDOW_15M_ACTIVE",
                None,
                None,
                f"lifecycle-{cycle_id}-{ordinal}",
                f"mint-{cycle_id}-{ordinal}",
                f"pair-{cycle_id}-{ordinal}",
                queue_id,
            ),
        )


def _derive_cycle(connection: sqlite3.Connection, cycle_id: str) -> dict:
    return derive_cycle_terminal_accounting_result(
        connection,
        context=_context(cycle_id),
    )


def _peer_origin_for_target(
    connection: sqlite3.Connection,
    target_cycle_id: str,
) -> str | None:
    return resolve_peer_stop_origin_cycle_id(
        connection,
        campaign_id=CAMPAIGN,
        campaign_run_id=CAMPAIGN_RUN,
        configuration_id=CONFIGURATION,
        factory_run_id=FACTORY_RUN,
        target_cycle_id=target_cycle_id,
        admitted_cycle_ids=("cycle-1", "cycle-2"),
    )


def _peer_stop_kwargs() -> dict[str, str]:
    return {
        "campaign_id": CAMPAIGN,
        "campaign_run_id": CAMPAIGN_RUN,
        "configuration_id": CONFIGURATION,
        "factory_run_id": FACTORY_RUN,
        "target_cycle_id": "cycle-2",
        "origin_cycle_id": "cycle-1",
    }


def test_cycle_derivation_rejects_ordinal_three_before_lifecycle_reads() -> None:
    connection = _identity_database()
    _insert_cycle(connection, cycle_id="cycle-3", ordinal=3)

    with pytest.raises(FullRunAccountingError, match="authorized ordinals"):
        derive_cycle_terminal_accounting_result(
            connection,
            context=_context("cycle-3"),
        )


def test_two_cycle_aggregate_fails_closed_when_both_cycles_lack_slots() -> None:
    connection = _identity_database()
    _insert_cycle(connection, cycle_id="cycle-1", ordinal=1)
    _insert_cycle(connection, cycle_id="cycle-2", ordinal=2)

    result = derive_two_cycle_campaign_terminal_accounting(
        connection,
        campaign_id=CAMPAIGN,
        campaign_run_id=CAMPAIGN_RUN,
        configuration_id=CONFIGURATION,
        factory_run_id=FACTORY_RUN,
    )

    assert result["required_cycle_ordinals"] == [1, 2]
    assert result["execution_outcome"] == "INTERRUPTED_AMBIGUOUS"
    assert result["accounting_complete"] is False
    assert [cycle["cycle_ordinal"] for cycle in result["cycles"]] == [1, 2]
    assert all(cycle["requires_review"] is True for cycle in result["cycles"])


def test_two_cycle_aggregate_rejects_duplicate_ordinal() -> None:
    connection = _identity_database()
    _insert_cycle(connection, cycle_id="cycle-a", ordinal=1)
    _insert_cycle(connection, cycle_id="cycle-b", ordinal=1)

    with pytest.raises(FullRunAccountingError, match="duplicate cycle ordinal"):
        derive_two_cycle_campaign_terminal_accounting(
            connection,
            campaign_id=CAMPAIGN,
            campaign_run_id=CAMPAIGN_RUN,
            configuration_id=CONFIGURATION,
            factory_run_id=FACTORY_RUN,
        )


def test_lawful_peer_stop_applies_only_to_active_incomplete_target() -> None:
    connection = _identity_database()
    _insert_cycle(
        connection,
        cycle_id="cycle-1",
        ordinal=1,
        state="TERMINAL_FAILED",
        cause="CYCLE_ONE_EXACT_FAILURE",
    )
    _insert_cycle(connection, cycle_id="cycle-2", ordinal=2)
    _insert_active_owned_slots(connection, cycle_id="cycle-2", token_base=20)
    connection.commit()

    origin = _derive_cycle(connection, "cycle-1")
    target = _derive_cycle(connection, "cycle-2")
    assert origin["execution_outcome"] == "CYCLE_FAILED"
    assert target["execution_outcome"] == "ACTIVE_INCOMPLETE"
    assert target["activity_state"] == "ACTIVE_INCOMPLETE"

    effect = derive_peer_cycle_stop_effect(connection, **_peer_stop_kwargs())

    assert effect["cause"] == CAMPAIGN_STOPPED_AFTER_PEER_CYCLE_TERMINAL
    assert effect["origin_scope"] == "CYCLE"
    assert effect["effect_scope"] == "CAMPAIGN"
    assert effect["origin_cycle_id"] == "cycle-1"
    assert effect["target_cycle_id"] == "cycle-2"
    assert effect["origin_fault"]["cause"] == "CYCLE_ONE_EXACT_FAILURE"
    assert effect["cause"] != effect["origin_fault"]["cause"]
    assert _peer_origin_for_target(connection, "cycle-2") == "cycle-1"
    assert _peer_origin_for_target(connection, "cycle-1") is None


def test_ambiguous_peer_target_is_rejected_and_not_rewritten() -> None:
    connection = _identity_database()
    _insert_cycle(
        connection,
        cycle_id="cycle-1",
        ordinal=1,
        state="TERMINAL_FAILED",
        cause="CYCLE_ONE_EXACT_FAILURE",
    )
    _insert_cycle(connection, cycle_id="cycle-2", ordinal=2)
    connection.commit()

    origin = _derive_cycle(connection, "cycle-1")
    target = _derive_cycle(connection, "cycle-2")
    assert origin["execution_outcome"] == "CYCLE_FAILED"
    assert target["execution_outcome"] == "INTERRUPTED_AMBIGUOUS"
    assert target["requires_review"] is True
    assert _peer_origin_for_target(connection, "cycle-2") is None

    with pytest.raises(
        FourTokenFactoryAdapterError,
        match="peer-stop target is interrupted or ambiguous",
    ):
        derive_peer_cycle_stop_effect(connection, **_peer_stop_kwargs())
    with pytest.raises(
        FourTokenFactoryAdapterError,
        match="peer-stop target is interrupted or ambiguous",
    ):
        reconcile_four_token_cycle_terminal(
            connection,
            campaign_id=CAMPAIGN,
            campaign_run_id=CAMPAIGN_RUN,
            factory_run_id=FACTORY_RUN,
            cycle_id="cycle-2",
            configuration_id=CONFIGURATION,
            peer_stop_origin_cycle_id="cycle-1",
            now=datetime(2026, 8, 23, tzinfo=timezone.utc),
        )

    target_row = connection.execute(
        "SELECT cycle_state, first_terminal_cause "
        "FROM printer_memory_factory_campaign_cycles "
        "WHERE cycle_id=?",
        ("cycle-2",),
    ).fetchone()
    persisted_causes = [
        row[0]
        for row in connection.execute(
            "SELECT first_terminal_cause "
            "FROM printer_memory_factory_campaign_cycles"
        ).fetchall()
    ]
    aggregate = derive_two_cycle_campaign_terminal_accounting(
        connection,
        campaign_id=CAMPAIGN,
        campaign_run_id=CAMPAIGN_RUN,
        configuration_id=CONFIGURATION,
        factory_run_id=FACTORY_RUN,
    )

    assert target_row["cycle_state"] == "RUNNING"
    assert target_row["first_terminal_cause"] is None
    assert CAMPAIGN_STOPPED_AFTER_PEER_CYCLE_TERMINAL not in persisted_causes
    assert aggregate["execution_outcome"] == "INTERRUPTED_AMBIGUOUS"
    assert aggregate["requires_review"] is True
    assert aggregate["accounting_complete"] is False
    assert 2 in aggregate["interrupted_cycle_ordinals"]


def test_nonfailed_origin_cannot_peer_stop_active_cycle() -> None:
    connection = _identity_database()
    _insert_cycle(connection, cycle_id="cycle-1", ordinal=1)
    _insert_cycle(connection, cycle_id="cycle-2", ordinal=2)
    _insert_active_owned_slots(connection, cycle_id="cycle-1", token_base=10)
    _insert_active_owned_slots(connection, cycle_id="cycle-2", token_base=20)
    connection.commit()

    origin = _derive_cycle(connection, "cycle-1")
    target = _derive_cycle(connection, "cycle-2")
    assert origin["execution_outcome"] == "ACTIVE_INCOMPLETE"
    assert target["execution_outcome"] == "ACTIVE_INCOMPLETE"
    assert _peer_origin_for_target(connection, "cycle-2") is None

    with pytest.raises(
        FourTokenFactoryAdapterError,
        match="peer-stop origin is not an exact failed cycle",
    ):
        derive_peer_cycle_stop_effect(connection, **_peer_stop_kwargs())


def test_factory_loop_peer_origin_uses_active_incomplete_allowlist() -> None:
    source = inspect.getsource(factory.run_one_command_15m_factory)
    start = source.index("four-token terminal found no admitted cycle")
    end = source.index('four_token_terminal = {"phase_a": tuple(phase_a)}')
    region = source[start:end]
    helper = inspect.getsource(resolve_peer_stop_origin_cycle_id)
    effect = inspect.getsource(derive_peer_cycle_stop_effect)

    assert "resolve_peer_stop_origin_cycle_id(" in region
    assert "peer_stop_origin_cycle_id=peer_origin" in region
    assert "failed_cycle_ids" not in region
    assert '"TERMINAL_SUCCESS"' not in region
    assert '"CANCELLED_STOPPED"' not in region
    assert '!= "ACTIVE_INCOMPLETE"' in helper
    assert '== "CYCLE_FAILED"' in helper
    assert "INTERRUPTED_AMBIGUOUS" in effect
    assert '!= "ACTIVE_INCOMPLETE"' in effect


def _terminal_accounting() -> dict:
    cycles = [
        {
            "cycle_id": f"cycle-{ordinal}",
            "cycle_ordinal": ordinal,
            "activity_state": "TERMINAL",
            "execution_outcome": "TERMINAL_SUCCESS",
            "quality_outcome": "NON_CLEAN" if ordinal == 2 else "CLEAN",
            "accounting_complete": True,
            "requires_review": False,
            "primary_fault": None,
            "secondary_faults": [],
            "tokens": [],
        }
        for ordinal in (1, 2)
    ]
    return {
        "campaign_id": CAMPAIGN,
        "campaign_run_id": CAMPAIGN_RUN,
        "configuration_id": CONFIGURATION,
        "factory_run_id": FACTORY_RUN,
        "required_cycle_ordinals": [1, 2],
        "execution_outcome": "TERMINAL_SUCCESS",
        "quality_outcome": "MIXED",
        "accounting_complete": True,
        "first_cause": None,
        "secondary_faults": [],
        "cleanup": {"cleanup_complete": True, "active_work": 0},
        "cycles": cycles,
    }


def test_lane4_report_identity_and_terminal_are_derived_from_accounting() -> None:
    accounting = _terminal_accounting()
    report = build_campaign_terminal_report(
        campaign_id=CAMPAIGN,
        configuration_id=CONFIGURATION,
        campaign_run_id=CAMPAIGN_RUN,
        report_id="report-lane4",
        factory_run_id=FACTORY_RUN,
        execution_id="execution-lane4",
        terminal_accounting=accounting,
        lifecycle_started=True,
        reconciliation={"cleanup_complete": True},
    )

    assert report["policy_version"] == "V2_9_8B_LANE4_MULTI_CYCLE_TERMINAL"
    assert report["identity"]["campaign_run_id"] == CAMPAIGN_RUN
    assert "cycle_id" not in report["identity"]
    assert report["terminal_accounting"] == accounting
    assert report["cycles"] == accounting["cycles"]
    assert report["terminal"]["first_terminal_cause"] is None

    with pytest.raises(
        TerminalClosureError,
        match="REJECTS_LEGACY_SHARED_TERMINAL_INPUTS",
    ):
        build_campaign_terminal_report(
            campaign_id=CAMPAIGN,
            configuration_id=CONFIGURATION,
            campaign_run_id=CAMPAIGN_RUN,
            cycle_id="cycle-1",
            report_id="report-lane4",
            factory_run_id=FACTORY_RUN,
            execution_id="execution-lane4",
            terminal_accounting=accounting,
            terminal_status="COMPLETED",
            terminal_cause="SHARED",
            run_status="COMPLETED",
            lifecycle_started=True,
            reconciliation={"cleanup_complete": True},
        )


def test_summary_is_canonical_report_projection_and_differing_replay_blocks(
    tmp_path: Path,
) -> None:
    accounting = _terminal_accounting()
    report_result = {
        "report_id": "report-lane4",
        "report_hash": "a" * 64,
        "artifact_path": str(tmp_path / "reports" / "report-lane4.json"),
        "report_rows": 1,
    }
    summary = build_campaign_terminal_summary(
        campaign_id=CAMPAIGN,
        configuration_id=CONFIGURATION,
        campaign_run_id=CAMPAIGN_RUN,
        factory_run_id=FACTORY_RUN,
        execution_id="execution-lane4",
        report_id="report-lane4",
        terminal_accounting=accounting,
        report_result=report_result,
        cleanup={"cleanup_complete": True, "lease_released": True, "active_work": 0},
    )
    destination = tmp_path / "terminal-summary.json"

    first = write_campaign_terminal_summary(destination, summary=summary)
    second = write_campaign_terminal_summary(destination, summary=summary)

    assert first["artifact_created"] is True
    assert second["artifact_created"] is False
    persisted = json.loads(destination.read_text(encoding="utf-8"))
    assert persisted["configuration_id"] == CONFIGURATION
    assert [cycle["cycle_ordinal"] for cycle in persisted["cycles"]] == [1, 2]
    assert persisted["restart_created"] is False
    assert persisted["successor_created"] is False

    changed = dict(summary)
    changed["campaign_execution_outcome"] = "CYCLE_FAILED"
    with pytest.raises(TerminalClosureError, match="already differs"):
        write_campaign_terminal_summary(destination, summary=changed)


def test_report_only_lane4_validation_uses_persisted_report_not_lifecycle_rows() -> None:
    accounting = _terminal_accounting()
    report = {
        "policy_version": "V2_9_8B_LANE4_MULTI_CYCLE_TERMINAL",
        "identity": {
            "campaign_id": CAMPAIGN,
            "configuration_id": CONFIGURATION,
            "campaign_run_id": CAMPAIGN_RUN,
            "factory_run_id": FACTORY_RUN,
            "execution_id": "execution-lane4",
            "report_id": "report-lane4",
        },
        "terminal_accounting": accounting,
        "cycles": accounting["cycles"],
    }
    summary = {
        "campaign_id": CAMPAIGN,
        "configuration_id": CONFIGURATION,
        "campaign_run_id": CAMPAIGN_RUN,
        "factory_run_id": FACTORY_RUN,
        "execution_id": "execution-lane4",
        "report_id": "report-lane4",
        "report_hash": "a" * 64,
        "campaign_execution_outcome": "TERMINAL_SUCCESS",
        "campaign_quality_outcome": "MIXED",
        "campaign_accounting_complete": True,
        "cycles": [
            {
                "cycle_id": item["cycle_id"],
                "cycle_ordinal": item["cycle_ordinal"],
                "execution_outcome": item["execution_outcome"],
                "quality_outcome": item["quality_outcome"],
            }
            for item in accounting["cycles"]
        ],
    }

    validated = _validate_lane4_report_only_payload(
        report=report,
        report_hash="a" * 64,
        campaign_id=CAMPAIGN,
        campaign_run_id=CAMPAIGN_RUN,
        configuration_id=CONFIGURATION,
        execution_id="execution-lane4",
        factory_run_id=FACTORY_RUN,
        report_id="report-lane4",
        summary=summary,
    )
    assert validated["terminal_accounting"] == accounting

    summary["cycles"][1]["execution_outcome"] = "CYCLE_FAILED"
    with pytest.raises(ValueError, match="SUMMARY_CYCLE_MISMATCH"):
        _validate_lane4_report_only_payload(
            report=report,
            report_hash="a" * 64,
            campaign_id=CAMPAIGN,
            campaign_run_id=CAMPAIGN_RUN,
            configuration_id=CONFIGURATION,
            execution_id="execution-lane4",
            factory_run_id=FACTORY_RUN,
            report_id="report-lane4",
            summary=summary,
        )


def test_action_local_cycle_slice_uses_cycle_bearing_stage_identity() -> None:
    ledger = CampaignActionLocalLedger(
        campaign_id=CAMPAIGN,
        run_id=CAMPAIGN_RUN,
    )
    for ordinal in (1, 2):
        ledger.observe_local_validation(
            {
                "stage_id": (
                    f"{CAMPAIGN}|{CAMPAIGN_RUN}|cycle-{ordinal}|"
                    f"CAMPAIGN_TERMINAL_RECONCILIATION|4"
                ),
                "subject_identity": f"cycle-{ordinal}:terminal",
                "validation_kind": "ZERO_ACTIVE_WORK_VALIDATED",
                "validation_ordinal": 1,
            }
        )

    cycle_two = ledger.slice_for_cycle("cycle-2")

    assert cycle_two.cycle_id == "cycle-2"
    assert len(cycle_two.local_validation_identities) == 1
    assert "|cycle-2|" in cycle_two.local_validation_identities[0]["stage_id"]


def test_action_local_observer_uses_exact_cycle_identity_from_production_record() -> None:
    ledger = CampaignActionLocalLedger(
        campaign_id=CAMPAIGN,
        run_id=CAMPAIGN_RUN,
    )
    observer = build_lifecycle_action_local_observer(_context("cycle-1"), ledger)

    observer(
        {
            "boundary": "SCHEDULER_ENQUEUE",
            "campaign_id": CAMPAIGN,
            "campaign_run_id": CAMPAIGN_RUN,
            "cycle_id": "cycle-2",
            "factory_run_id": FACTORY_RUN,
            "scheduler_job_id": 42,
            "step_key": "t1_snapshot_00",
            "step_kind": "SNAPSHOT",
            "token_id": 21,
            "pair_id": 201,
        }
    )

    assert not ledger.slice_for_cycle("cycle-1").scheduler_work_identities
    assert len(ledger.slice_for_cycle("cycle-2").scheduler_work_identities) == 1

from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli.unified_terminal_closure import TerminalClosureError
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignActionLocalLedger,
    CampaignCycleAccountingRegistry,
    CampaignSixUnitProjection,
)

CAMPAIGN = "campaign-durable-scope"
RUN = "run-durable-scope"
CYCLE_1 = "cycle-1-durable-scope"
CYCLE_2 = "cycle-2-durable-scope"
NOW = "2026-08-25T11:31:55+00:00"


def _scope_resolver():
    resolver = getattr(command, "_resolve_durable_terminal_accounting_scope", None)
    assert callable(resolver), "durable-admission accounting scope resolver missing"
    return resolver


def _db(tmp_path: Path, *, admitted_ordinals: tuple[int, ...]) -> Path:
    db = tmp_path / "durable-scope.sqlite3"
    connection = sqlite3.connect(db)
    try:
        connection.executescript(
            """
            CREATE TABLE printer_memory_factory_campaign_cycles(
                cycle_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                cycle_ordinal INTEGER NOT NULL,
                cycle_state TEXT NOT NULL
            );
            CREATE TABLE printer_pre_admission_discovery_attempts(
                attempt_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                campaign_run_id TEXT NOT NULL,
                proposed_cycle_id TEXT NOT NULL,
                proposed_cycle_ordinal INTEGER NOT NULL,
                attempt_state TEXT NOT NULL,
                consumed_cycle_id TEXT,
                terminal_at TEXT
            );
            """
        )
        for ordinal in admitted_ordinals:
            cycle_id = CYCLE_1 if ordinal == 1 else CYCLE_2
            connection.execute(
                "INSERT INTO printer_memory_factory_campaign_cycles "
                "VALUES (?,?,?,?,?)",
                (cycle_id, CAMPAIGN, RUN, ordinal, "TERMINAL_BLOCKED"),
            )
        connection.commit()
    finally:
        connection.close()
    return db


def _registry(*, with_cycle_2: bool = True) -> CampaignCycleAccountingRegistry:
    registry = CampaignCycleAccountingRegistry(
        campaign_id=CAMPAIGN,
        run_id=RUN,
        initial_cycle_id=CYCLE_1,
        started_at=NOW,
    )
    if with_cycle_2:
        registry.register_authoritative_cycle(
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE_2,
            started_at=NOW,
        )
    return registry


def _ledger() -> CampaignActionLocalLedger:
    return CampaignActionLocalLedger(campaign_id=CAMPAIGN, run_id=RUN)


def _seed_terminal_unconsumed_attempt(db: Path) -> None:
    connection = sqlite3.connect(db)
    try:
        connection.execute(
            """INSERT INTO printer_pre_admission_discovery_attempts(
                   attempt_id,campaign_id,campaign_run_id,proposed_cycle_id,
                   proposed_cycle_ordinal,attempt_state,consumed_cycle_id,terminal_at
               ) VALUES (?,?,?,?,?,'FAILED',NULL,?)""",
            ("attempt-cycle-2", CAMPAIGN, RUN, CYCLE_2, 2, NOW),
        )
        connection.commit()
    finally:
        connection.close()


def test_terminal_closure_error_is_imported_by_operational_command() -> None:
    assert getattr(command, "TerminalClosureError", None) is TerminalClosureError


def test_one_durable_cycle_ignores_only_proven_terminal_unconsumed_provisional_owner(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path, admitted_ordinals=(1,))
    _seed_terminal_unconsumed_attempt(db)
    registry = _registry(with_cycle_2=True)
    ledger = _ledger()

    scope = _scope_resolver()(
        db,
        campaign_id=CAMPAIGN,
        campaign_run_id=RUN,
        primary_cycle_id=CYCLE_1,
        cycle_accounting_registry=registry,
        action_local_ledger=ledger,
    )

    assert scope.admitted_cycle_ids == (CYCLE_1,)
    assert scope.multi_cycle is False
    assert scope.accounting_owner is registry.owner_for_cycle(CYCLE_1)
    assert scope.accounting_projection_factory is None
    assert scope.action_local_ledger.cycle_id == CYCLE_1


def test_unmatched_extra_registered_owner_fails_closed(tmp_path: Path) -> None:
    db = _db(tmp_path, admitted_ordinals=(1,))
    registry = _registry(with_cycle_2=True)

    with pytest.raises(TerminalClosureError, match="PROVISIONAL_ACCOUNTING_OWNER_NOT_PROVEN"):
        _scope_resolver()(
            db,
            campaign_id=CAMPAIGN,
            campaign_run_id=RUN,
            primary_cycle_id=CYCLE_1,
            cycle_accounting_registry=registry,
            action_local_ledger=_ledger(),
        )


def test_nonterminal_provisional_attempt_fails_closed(tmp_path: Path) -> None:
    db = _db(tmp_path, admitted_ordinals=(1,))
    connection = sqlite3.connect(db)
    try:
        connection.execute(
            """INSERT INTO printer_pre_admission_discovery_attempts(
                   attempt_id,campaign_id,campaign_run_id,proposed_cycle_id,
                   proposed_cycle_ordinal,attempt_state,consumed_cycle_id,terminal_at
               ) VALUES (?,?,?,?,?,'RUNNING',NULL,NULL)""",
            ("attempt-cycle-2", CAMPAIGN, RUN, CYCLE_2, 2),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(TerminalClosureError, match="PROVISIONAL_ACCOUNTING_OWNER_NOT_PROVEN"):
        _scope_resolver()(
            db,
            campaign_id=CAMPAIGN,
            campaign_run_id=RUN,
            primary_cycle_id=CYCLE_1,
            cycle_accounting_registry=_registry(with_cycle_2=True),
            action_local_ledger=_ledger(),
        )


def test_two_durable_cycles_require_exact_registered_identity_and_use_projection(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path, admitted_ordinals=(1, 2))
    registry = _registry(with_cycle_2=True)
    ledger = _ledger()

    scope = _scope_resolver()(
        db,
        campaign_id=CAMPAIGN,
        campaign_run_id=RUN,
        primary_cycle_id=CYCLE_1,
        cycle_accounting_registry=registry,
        action_local_ledger=ledger,
    )

    assert scope.admitted_cycle_ids == (CYCLE_1, CYCLE_2)
    assert scope.multi_cycle is True
    assert isinstance(scope.accounting_owner, CampaignSixUnitProjection)
    assert scope.accounting_owner.registered_cycle_ids == (CYCLE_1, CYCLE_2)
    assert callable(scope.accounting_projection_factory)
    assert scope.action_local_ledger is ledger


def test_two_durable_cycles_with_missing_registered_owner_fail_closed(tmp_path: Path) -> None:
    db = _db(tmp_path, admitted_ordinals=(1, 2))

    with pytest.raises(TerminalClosureError, match="DURABLE_ADMISSION_ACCOUNTING_OWNER_MISMATCH"):
        _scope_resolver()(
            db,
            campaign_id=CAMPAIGN,
            campaign_run_id=RUN,
            primary_cycle_id=CYCLE_1,
            cycle_accounting_registry=_registry(with_cycle_2=False),
            action_local_ledger=_ledger(),
        )


def test_normal_and_exception_paths_delegate_projection_scope_to_durable_resolver() -> None:
    source = Path(command.__file__).read_text(encoding="utf-8")
    assert source.count("_resolve_durable_terminal_accounting_scope(") >= 3
    assert source.count("cycle_accounting_registry.campaign_projection()") == 1
    assert "for terminal_cycle_id in durable_terminal_cycle_ids:" in source
    assert "and terminal_accounting_scope.multi_cycle" in source

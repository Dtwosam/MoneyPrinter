from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.eligible_token_supply import (
    ACQUISITION_QUANTUM_YIELDED,
    AcquisitionQuantumKind,
    acquisition_quantum_bound,
    run_persistent_eligible_token_supply,
)
from printer_v1.discovery.permanent_discovery_availability import (
    CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS,
    StageBudget,
    build_campaign_source_request_scope,
    validate_cooperative_resume_source_request_scope,
)
from printer_v1.operator_cli.window_15m_concrete_composition import (
    ORDINARY_WINDOW_15M_TRANSPORT_TIMEOUT_SECONDS,
)
from printer_v1.sources.dexscreener import DEXSCREENER_SMOKE_TIMEOUT_SECONDS
from printer_v1.sources.geckoterminal import GECKOTERMINAL_TIMEOUT_SECONDS
from printer_v1.sources.pump_migration import GRADUATION_VERIFIER_TIMEOUT_SECONDS
from printer_v1.sources.pumpswap_pool_account_batch import RPC_TIMEOUT_SECONDS


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc).isoformat()


def test_quantum_bounds_are_derived_from_canonical_transport_contracts() -> None:
    pump = ORDINARY_WINDOW_15M_TRANSPORT_TIMEOUT_SECONDS
    verifier = GRADUATION_VERIFIER_TIMEOUT_SECONDS
    dex = DEXSCREENER_SMOKE_TIMEOUT_SECONDS
    gecko = GECKOTERMINAL_TIMEOUT_SECONDS
    protocol = RPC_TIMEOUT_SECONDS

    expected = {
        AcquisitionQuantumKind.AUXILIARY_FRESH_INTAKE: 2 * dex + gecko,
        AcquisitionQuantumKind.AUXILIARY_LIQUIDITY_BACKUP: max(dex, gecko),
        AcquisitionQuantumKind.AUXILIARY_PROTOCOL_CONFIRMATION: protocol,
        AcquisitionQuantumKind.DIRECT_MIGRATION: 7 * pump + 4 * verifier,
        AcquisitionQuantumKind.MARKET_DISCOVERY: dex + 6 * gecko + 5 * 6.0,
        AcquisitionQuantumKind.PROTOCOL_CONFIRMATION: protocol,
        AcquisitionQuantumKind.PROTOCOL_RESUME_MARKET: dex,
        AcquisitionQuantumKind.PERSISTED_REFRESH: 7 * pump + 4 * verifier,
        AcquisitionQuantumKind.PERSISTED_REFRESH_DEXSCREENER: (
            2 * dex + max(dex, gecko) + protocol
        ),
        AcquisitionQuantumKind.PERSISTED_REFRESH_GECKOTERMINAL: (
            gecko + max(dex, gecko) + protocol
        ),
    }
    assert {
        kind: acquisition_quantum_bound(kind).worst_case_seconds
        for kind in expected
    } == expected
    assert expected == {
        AcquisitionQuantumKind.AUXILIARY_FRESH_INTAKE: 18.0,
        AcquisitionQuantumKind.AUXILIARY_LIQUIDITY_BACKUP: 8.0,
        AcquisitionQuantumKind.AUXILIARY_PROTOCOL_CONFIRMATION: 20.0,
        AcquisitionQuantumKind.DIRECT_MIGRATION: 115.0,
        AcquisitionQuantumKind.MARKET_DISCOVERY: 83.0,
        AcquisitionQuantumKind.PROTOCOL_CONFIRMATION: 20.0,
        AcquisitionQuantumKind.PROTOCOL_RESUME_MARKET: 5.0,
        AcquisitionQuantumKind.PERSISTED_REFRESH: 115.0,
        AcquisitionQuantumKind.PERSISTED_REFRESH_DEXSCREENER: 38.0,
        AcquisitionQuantumKind.PERSISTED_REFRESH_GECKOTERMINAL: 36.0,
    }


def test_one_stage_budget_remains_monotonic_across_cooperative_yields() -> None:
    budget = StageBudget.permanent_discovery_default()
    same_budget_after_yield = budget
    before = budget.snapshot()

    budget.consume("intake", 3)
    budget.consume("reconciliation", 1)
    budget.consume("protocol_confirmation", 2)
    budget.consume("market_batching", 1)
    middle = same_budget_after_yield.snapshot()
    same_budget_after_yield.consume("market_batching", 1)
    after = budget.snapshot()

    assert same_budget_after_yield is budget
    assert middle["remaining_by_stage"]["market_batching"] == 1
    assert after["remaining_by_stage"]["market_batching"] == 0
    assert after["remaining_by_stage"]["reconciliation"] <= 5
    assert after["remaining_by_stage"]["protocol_confirmation"] <= 5
    assert all(
        after["remaining_by_stage"][name]
        <= before["remaining_by_stage"][name]
        for name in before["remaining_by_stage"]
    )
    with pytest.raises(ValueError, match="STAGE_RESERVATION_EXCEEDED"):
        budget.consume("market_batching", 1)


def test_direct_verifier_charge_is_retained_before_yield_and_not_recharged(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "direct-charge.sqlite3"
    apply_migrations(path)
    budget = StageBudget.permanent_discovery_default()
    direct_calls = 0

    def direct_report(*_args, **_kwargs):
        nonlocal direct_calls
        direct_calls += 1
        return {
            "status": "COMPLETE",
            "confirmed_this_cycle": (),
            "candidate_mix": (),
            "source_request_coverage": (
                {
                    "source_name": "pumpswap",
                    "request_kind": "pumpswap_signature_pool_resolution",
                    "logical_stage_id": "DIRECT_MIGRATION_VERIFY|1",
                },
                {
                    "source_name": "pumpswap",
                    "request_kind": "pumpswap_signature_pool_resolution",
                    "logical_stage_id": "DIRECT_MIGRATION_VERIFY|2",
                },
            ),
            "source_operation_ledger": {
                "source_requests": 3,
                "request_ids": (),
                "source_request_coverage": (),
            },
            "campaign_safe_stop": False,
            "accounting_blocker": False,
        }

    monkeypatch.setattr(
        "printer_v1.discovery.eligible_token_supply.run_direct_migration_discovery",
        direct_report,
    )
    direct = run_persistent_eligible_token_supply(
        path,
        cycle_seed="direct-charge",
        migration_transport=object(),
        permanent_availability=True,
        cooperative_quantum=True,
        cooperative_phase="DIRECT_MIGRATION",
        cooperative_stage_budget=budget,
    )
    assert direct.terminal == ACQUISITION_QUANTUM_YIELDED
    assert direct_calls == 1
    assert budget.used_by_stage["protocol_confirmation"] == 2
    assert direct.diagnostics[
        "direct_migration_protocol_confirmation_requests"
    ] == 2

    run_persistent_eligible_token_supply(
        path,
        cycle_seed="direct-charge",
        migration_transport=object(),
        permanent_availability=True,
        cooperative_resume=True,
        cooperative_quantum=True,
        cooperative_phase="MARKET_DISCOVERY",
        cooperative_stage_budget=budget,
        prior_source_operations_used=3,
    )
    assert direct_calls == 1
    assert budget.used_by_stage["protocol_confirmation"] == 2


def _insert_terminal_request(
    connection: sqlite3.Connection,
    *,
    key: str,
    source: str,
    kind: str,
) -> int:
    request_id = int(
        connection.execute(
            "INSERT INTO printer_source_requests("
            "source_name,request_kind,request_key,requested_at,source_status,data_quality_label) "
            "VALUES (?,?,?,?, 'COMPLETE','CLEAN_DATA')",
            (source, kind, key, NOW),
        ).lastrowid
    )
    connection.execute(
        "INSERT INTO printer_source_responses("
        "source_request_id,source_name,received_at,source_status,data_quality_label) "
        "VALUES (?,?,?,'COMPLETE','CLEAN_DATA')",
        (request_id, source, NOW),
    )
    connection.commit()
    return request_id


@pytest.mark.parametrize(
    ("suffix", "source", "kind"),
    [
        ("-foreign", "arbitrary_source", "arbitrary_kind"),
        ("-foreign", "dexscreener", "dexscreener_fresh_profiles"),
        ("-locator", "dexscreener", "candidate_market_batch"),
        ("-mint-batch-rXYZ", "dexscreener", "candidate_market_batch"),
    ],
)
def test_cooperative_resume_rejects_foreign_source_contract_or_stage_grammar(
    tmp_path, suffix: str, source: str, kind: str
) -> None:
    path = tmp_path / "resume.sqlite3"
    apply_migrations(path)
    scope = build_campaign_source_request_scope(
        execution_id="exec-final-g",
        campaign_id="campaign-final-g",
        run_id="run-final-g",
        cycle_id="cycle-final-g",
    )
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    _insert_terminal_request(
        connection,
        key=f"{scope.request_key_root}{suffix}",
        source=source,
        kind=kind,
    )
    with pytest.raises(ValueError, match=CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS):
        validate_cooperative_resume_source_request_scope(
            connection,
            scope=scope,
            execution_id=scope.execution_id,
            campaign_id=scope.campaign_id,
            run_id=scope.run_id,
            cycle_id=scope.cycle_id,
        )
    connection.close()


def test_cooperative_resume_accepts_exact_lawful_source_stage_pair(tmp_path) -> None:
    path = tmp_path / "resume-lawful.sqlite3"
    apply_migrations(path)
    scope = build_campaign_source_request_scope(
        execution_id="exec-final-g",
        campaign_id="campaign-final-g",
        run_id="run-final-g",
        cycle_id="cycle-final-g",
    )
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    request_id = _insert_terminal_request(
        connection,
        key=f"{scope.request_key_root}-locator",
        source="dexscreener",
        kind="dexscreener_fresh_profiles",
    )
    result = validate_cooperative_resume_source_request_scope(
        connection,
        scope=scope,
        execution_id=scope.execution_id,
        campaign_id=scope.campaign_id,
        run_id=scope.run_id,
        cycle_id=scope.cycle_id,
    )
    assert result["request_ids"] == [request_id]
    connection.close()

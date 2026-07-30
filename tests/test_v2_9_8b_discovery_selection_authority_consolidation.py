"""Frozen offline proof: V2-9.8B discovery/selection authority consolidation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import inspect
from pathlib import Path
import sqlite3
import time

import pytest

from printer_v1.db.migrate import apply_migrations, canonical_migration_names
from printer_v1.discovery.direct_migration_discovery import (
    run_direct_migration_discovery,
)
from printer_v1.discovery.selection_authority import (
    SELECTION_AUTHORITY_VERSION,
    SelectionCandidate,
    select_two_candidates,
)
from printer_v1.sources.measured_transport import (
    SIX_UNITS,
    MeasuredTransportLedger,
    TransportOperationIdentity,
    empty_six_unit_totals,
    pumpswap_account_batch_count,
    pumpswap_verification_transport_count,
    reconcile_six_unit_totals,
)
from printer_v1.sources.operational_source_contracts import (
    ORDINARY_OPERATIONAL_SOURCE_CONTRACTS,
    resolve_solana_rpc_configuration,
    validate_active_ordinary_source_contracts,
)
from printer_v1.sources.pump_contracts import (
    MIGRATE_ACCOUNT_ROLES,
    validate_migrate_account_roles,
    verify_pinned_pump_migration,
)
from printer_v1.sources.pump_migration import MIGRATION_PROVENANCE, verify_graduation_from_transaction
from printer_v1.sources.direct_pump_migration import (
    SIGNATURE_PAGE_REQUEST_KIND,
    TRANSACTION_REQUEST_KIND,
)
from printer_v1.operator_cli import operational_memory_factory_command as command
from test_v2_9_8b_candidate_acquisition_foundation import _pinned_migration_fixture
from test_v2_9_8b_restored_factory_source_compatibility_reset import (
    _verifier_factory,
)


_SIGNATURE = (
    "5NarrowDirectPumpMigrationFinalizedSignature"
    "111111111111111111111111111111111111111111111111"
)
_NOW = "2026-07-30T20:00:00+00:00"


def test_public_command_composition_has_no_pumpportal_or_cursor_authority() -> None:
    source = inspect.getsource(command)
    assert "build_direct_pump_migration_transport" in source
    assert "build_pumpportal_migration_transport" not in source
    run_src = inspect.getsource(command._run_operational_campaign)
    assert "run_candidate_acquisition" not in run_src
    assert "candidate_acquisition_integration" not in run_src
    ordinary = ORDINARY_OPERATIONAL_SOURCE_CONTRACTS["pumpportal"]
    assert ordinary.active_runtime is False
    assert ordinary.classification == "DEFERRED"
    assert validate_active_ordinary_source_contracts()["ok"] is True


def test_one_solana_endpoint_owner_shared() -> None:
    cfg_a = resolve_solana_rpc_configuration({})
    cfg_b = resolve_solana_rpc_configuration({})
    assert cfg_a.url == cfg_b.url
    assert cfg_a.redacted_identity == cfg_b.redacted_identity


@pytest.mark.parametrize("account_keys", [1, 100, 101, 200, 256])
def test_pumpswap_account_batch_counts(account_keys: int) -> None:
    batches = pumpswap_account_batch_count(account_keys)
    assert 1 <= batches <= 3
    assert pumpswap_verification_transport_count(account_keys) == 1 + batches
    if account_keys <= 100:
        assert batches == 1
    elif account_keys <= 200:
        assert batches == 2
    else:
        assert batches == 3


def test_complete_25_role_rejection_coverage() -> None:
    tx, infos, mint, pool = _pinned_migration_fixture()
    ok = verify_pinned_pump_migration(tx, infos, expected_mint=mint, finalized=True)
    assert ok["verified"] is True
    accounts = list(tx["transaction"]["message"]["accountKeys"])
    assert len(MIGRATE_ACCOUNT_ROLES) == 25
    valid = validate_migrate_account_roles(accounts)
    assert valid["valid"] is True
    # Distinct rejection coverage for every role position.
    reasons: set[str] = set()
    invalid = "not-a-valid-pubkey!!!"
    for index in range(25):
        broken = list(accounts)
        broken[index] = invalid
        result = validate_migrate_account_roles(broken)
        assert result["valid"] is False, index
        assert result["reason"]
        reasons.add(str(result["reason"]))
    assert len(reasons) == 25


def test_canonical_two_candidate_selection_and_provenance() -> None:
    candidates = [
        SelectionCandidate(
            mint=f"Mint{'A' if i % 2 == 0 else 'B'}{i:02d}pump",
            pair_address=f"Pool{i:02d}",
            market_identity=f"solana-mainnet:pumpswap:Pool{i:02d}",
            provenance="LATEST_GRADUATED" if i % 2 == 0 else "PERSISTED_GRADUATED",
        )
        for i in range(4)
    ]
    first = select_two_candidates(candidates, cycle_seed="seed-alpha")
    second = select_two_candidates(candidates, cycle_seed="seed-alpha")
    assert first.as_dict() == second.as_dict()
    assert first.ready is True
    assert first.candidate_a is not None and first.candidate_b is not None
    assert first.candidate_a.mint != first.candidate_b.mint
    assert first.candidate_a.pair_address != first.candidate_b.pair_address
    assert first.authority_version == SELECTION_AUTHORITY_VERSION
    # Insufficient supply
    none = select_two_candidates(candidates[:1], cycle_seed="seed-alpha")
    assert none.ready is False
    assert none.selected == ()


def test_six_unit_report_replay_equality() -> None:
    ledger = MeasuredTransportLedger(campaign_id="c1", run_id="r1", cycle_id="y1")
    ledger.record_transport(
        TransportOperationIdentity(
            stage="DIRECT_PUMP_NOMINATION",
            source_name="solana_rpc",
            endpoint_owner="solana",
            governed_request_kind="restored_pump_migration_signature_page",
            method_or_endpoint="getSignaturesForAddress",
            within_request_ordinal=1,
            target_category="pump_program",
            response_bytes=128,
            normalized_rows=1,
            result="OK",
        )
    )
    ledger.record_local_validation(9)
    ledger.reserve_lifecycle_transports(80)
    report = {"six_unit_totals": ledger.six_unit_totals()}
    replay = {"six_unit_totals": dict(report["six_unit_totals"])}
    assert reconcile_six_unit_totals(report, replay)["equal"] is True
    assert set(report["six_unit_totals"]) == set(SIX_UNITS)
    assert empty_six_unit_totals()[SIX_UNITS[0]] == 0


def test_real_deadline_exhaustion_uses_wall_clock() -> None:
    from printer_v1.discovery import eligible_token_supply as ets

    # The duration helper must re-read wall clock, not frozen start.
    started = datetime.now(timezone.utc)
    deadline = (started - timedelta(seconds=1)).isoformat()
    deadline_dt = ets._parse_iso(deadline)
    remaining = (deadline_dt - ets._parse_iso(ets._utc_now_iso())).total_seconds()
    assert remaining <= 0


def test_fail_closed_cooldown_state_unavailable(tmp_path: Path) -> None:
    from printer_v1.discovery.graduated_liquidity_front_door import _cooldown_ok

    db = tmp_path / "no-rotation.sqlite3"
    connection = sqlite3.connect(db)
    try:
        ok, reason = _cooldown_ok(connection, "mint", "pool", 1)
        assert ok is False
        assert reason.startswith("COOLDOWN_STATE_UNAVAILABLE")
    finally:
        connection.close()


def test_direct_migration_measured_ops_and_zero_locked_deltas(tmp_path: Path) -> None:
    tx, infos, mint, pool = _pinned_migration_fixture()
    db = tmp_path / "frozen-migration-049.sqlite3"
    apply_migrations(db)

    def transport(context):
        if context.request.request_kind == SIGNATURE_PAGE_REQUEST_KIND:
            return {
                "result": [
                    {
                        "signature": _SIGNATURE,
                        "slot": tx["slot"],
                        "err": None,
                        "confirmationStatus": "finalized",
                    }
                ]
            }
        if context.request.request_kind == TRANSACTION_REQUEST_KIND:
            return {"result": tx}
        raise AssertionError(context.request.request_kind)

    report = run_direct_migration_discovery(
        db,
        migration_transport=transport,
        verifier_transport_factory=_verifier_factory(tx, infos),
        now=_NOW,
        collection_rounds=1,
        settle_seconds=0.0,
        reverify_on_transient=False,
        reverify_settle_seconds=0.0,
    )
    ledger = report["source_operation_ledger"]
    assert report["confirmed_count"] == 1
    assert ledger["source_requests"] == 3
    assert ledger["migration_transport_operations"] == 2
    assert ledger["pumpswap_transport_operations"] == 2
    assert ledger["transport_operations"] == 4
    assert ledger["operation_accounting_reconciled"] is True
    assert report["forbidden_delta_total"] == 0

    connection = sqlite3.connect(db)
    try:
        for table in (
            "printer_candidate_acquisition_runs",
            "printer_candidate_acquisition_cursors",
            "printer_candidate_recovery_attempts",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trades",
            "printer_paper_trade_audit",
            "printer_memory_retrieval",
        ):
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if exists:
                assert connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] == 0
        assert [
            row[0]
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY version"
            )
        ] == list(canonical_migration_names())
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()


def test_typed_prohibitions_reject_wallet_profile() -> None:
    from printer_v1.sources.operational_source_contracts import OperationalSourceContract

    bad = OperationalSourceContract(
        "evil",
        "MANDATORY",
        ("evil",),
        "WALLET",
        ("https://example.invalid",),
        False,
        (),
        (),
        "EVIL",
        0,
        "none",
        "block",
        wallet_required=True,
        private_key_required=True,
        signing_required=True,
        funding_required=True,
        paid_dependency=True,
        metered_account_or_trade_stream=True,
        transaction_submission=True,
        execution_endpoint=True,
    )
    violations = bad.prohibited_capability_violations()
    assert "WALLET_REQUIRED" in violations
    assert "PRIVATE_KEY_REQUIRED" in violations
    assert "SIGNING_REQUIRED" in violations
    assert "PAID_DEPENDENCY" in violations

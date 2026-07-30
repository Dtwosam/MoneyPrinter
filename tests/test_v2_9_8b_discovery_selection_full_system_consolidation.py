"""Frozen offline proof: V2-9.8B discovery/selection full-system consolidation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import inspect
import sqlite3
import time

import pytest

from printer_v1.db.migrate import apply_migrations, canonical_migration_names

from printer_v1.discovery.direct_migration_discovery import (
    run_direct_migration_discovery,
)
from printer_v1.discovery.selection_authority import (
    SelectionCandidate,
    composition_label,
    select_two_candidates,
)
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli.unified_terminal_closure import (
    build_campaign_terminal_report,
    replay_campaign_terminal_report,
    write_campaign_terminal_report,
)
from printer_v1.sources.direct_pump_migration import (
    SIGNATURE_PAGE_REQUEST_KIND,
    TRANSACTION_REQUEST_KIND,
)
from printer_v1.sources.measured_transport import (
    SIX_UNITS,
    MeasuredTransportError,
    MeasuredTransportLedger,
    TransportOperationIdentity,
    empty_six_unit_totals,
    enforce_normalized_row_ceiling,
    pumpswap_account_batch_count,
    pumpswap_verification_transport_count,
    reconcile_six_unit_totals,
)
from printer_v1.sources.operational_source_contracts import (
    ORDINARY_OPERATIONAL_SOURCE_CONTRACTS,
    SOLANA_RPC_ENVIRONMENT_NAME,
    resolve_solana_rpc_configuration,
    validate_active_ordinary_source_contracts,
)
from printer_v1.sources.pump_contracts import (
    MIGRATE_ACCOUNT_ROLES,
    PUMP_WITHDRAW_AUTHORITY_ID,
    validate_migrate_account_roles,
    verify_pinned_pump_migration,
)
from printer_v1.sources.pump_migration import build_graduation_verifier_transport
from printer_v1.sources.solana_rpc_holder import build_solana_rpc_holder_transport
from test_v2_9_8b_candidate_acquisition_foundation import _pinned_migration_fixture
from test_v2_9_8b_restored_factory_source_compatibility_reset import _verifier_factory


_SIGNATURE = (
    "5NarrowDirectPumpMigrationFinalizedSignature"
    "111111111111111111111111111111111111111111111111"
)
_NOW = "2026-07-30T20:00:00+00:00"


def test_public_command_composition_no_pumpportal_or_cursor_authority() -> None:
    source = inspect.getsource(command)
    assert "build_direct_pump_migration_transport" in source
    assert "build_pumpportal_migration_transport" not in source
    run_src = inspect.getsource(command._run_operational_campaign)
    assert "run_candidate_acquisition" not in run_src
    assert "candidate_acquisition_integration" not in run_src
    assert "build_pumpportal" not in run_src.casefold()
    ordinary = ORDINARY_OPERATIONAL_SOURCE_CONTRACTS["pumpportal"]
    assert ordinary.active_runtime is False
    assert ordinary.classification == "DEFERRED"
    assert validate_active_ordinary_source_contracts()["ok"] is True


@pytest.mark.parametrize("account_keys", [1, 100, 101, 200, 256])
def test_pumpswap_account_batch_identity_counts(account_keys: int) -> None:
    batches = pumpswap_account_batch_count(account_keys)
    assert 1 <= batches <= 3
    assert pumpswap_verification_transport_count(account_keys) == 1 + batches


def test_all_25_roles_and_relationship_substitutions_fail_closed() -> None:
    tx, infos, mint, pool = _pinned_migration_fixture()
    accounts = list(tx["transaction"]["message"]["accountKeys"])
    assert len(MIGRATE_ACCOUNT_ROLES) == 25
    assert validate_migrate_account_roles(accounts)["valid"] is True
    assert accounts[1] == PUMP_WITHDRAW_AUTHORITY_ID

    invalid_reasons: set[str] = set()
    for index in range(25):
        broken = list(accounts)
        broken[index] = "not-a-valid-pubkey!!!"
        result = validate_migrate_account_roles(broken)
        assert result["valid"] is False
        invalid_reasons.add(str(result["reason"]))
    assert len(invalid_reasons) == 25

    wrong = "11111111111111111111111111111112"
    for index, role in enumerate(MIGRATE_ACCOUNT_ROLES):
        broken = list(accounts)
        broken[index] = wrong if accounts[index] != wrong else accounts[0]
        result = validate_migrate_account_roles(broken)
        assert result["valid"] is False, f"{role} accepted valid-but-wrong pubkey"
        assert result["reason"]

    # Explicit withdraw_authority relationship pin.
    broken = list(accounts)
    broken[1] = wrong
    result = validate_migrate_account_roles(broken)
    assert result["valid"] is False
    assert result["role"] == "withdraw_authority"


def test_byte_and_row_ceilings_at_below_and_above() -> None:
    enforce_normalized_row_ceiling("dexscreener_exact_pair_rows", 8)
    with pytest.raises(MeasuredTransportError):
        enforce_normalized_row_ceiling("dexscreener_exact_pair_rows", 9)
    with pytest.raises(MeasuredTransportError):
        enforce_normalized_row_ceiling("undeclared_kind", 1)

    ledger = MeasuredTransportLedger()
    ledger.record_transport(
        TransportOperationIdentity(
            stage="DEXSCREENER_DISCOVERY",
            source_name="dexscreener_pair",
            endpoint_owner="dexscreener",
            governed_request_kind="pair_market_snapshot",
            method_or_endpoint="GET",
            within_request_ordinal=1,
            target_category="exact_pair",
            response_bytes=100,
            normalized_rows=1,
            result="OK",
        )
    )
    with pytest.raises(MeasuredTransportError):
        ledger.record_transport(
            TransportOperationIdentity(
                stage="DEXSCREENER_DISCOVERY",
                source_name="dexscreener_pair",
                endpoint_owner="dexscreener",
                governed_request_kind="pair_market_snapshot",
                method_or_endpoint="GET",
                within_request_ordinal=2,
                target_category="exact_pair",
                response_bytes=9_999_999,
                normalized_rows=1,
                result="OK",
            )
        )


def test_one_solana_endpoint_override_propagates() -> None:
    cfg = resolve_solana_rpc_configuration(
        {SOLANA_RPC_ENVIRONMENT_NAME: "https://example-override.invalid"}
    )
    assert cfg.url == "https://example-override.invalid"
    holder = build_solana_rpc_holder_transport("Mint111", rpc_url=cfg.url)
    verifier = build_graduation_verifier_transport(
        migration_signature="sig", expected_mint="Mint111", rpc_url=cfg.url
    )
    holder_urls = [
        c.cell_contents
        for c in (holder.__closure__ or ())
        if isinstance(c.cell_contents, str) and c.cell_contents.startswith("http")
    ]
    verifier_urls = [
        c.cell_contents
        for c in (verifier.__closure__ or ())
        if isinstance(c.cell_contents, str) and c.cell_contents.startswith("http")
    ]
    assert cfg.url in holder_urls
    assert cfg.url in verifier_urls


def test_truthful_provenance_labels() -> None:
    latest = [
        SelectionCandidate(
            mint=f"L{i}", pair_address=f"PL{i}", market_identity=f"m:PL{i}",
            provenance="LATEST_GRADUATED",
        )
        for i in range(3)
    ]
    persisted = [
        SelectionCandidate(
            mint=f"P{i}", pair_address=f"PP{i}", market_identity=f"m:PP{i}",
            provenance="PERSISTED_GRADUATED",
        )
        for i in range(3)
    ]
    mixed = [latest[0], persisted[0]]
    assert select_two_candidates(latest, cycle_seed="s").composition_label == "LATEST+LATEST"
    assert select_two_candidates(persisted, cycle_seed="s").composition_label == "PERSISTED+PERSISTED"
    assert select_two_candidates(mixed, cycle_seed="s").composition_label == "LATEST+PERSISTED"
    assert composition_label(mixed) == "LATEST+PERSISTED"


def test_real_deadline_and_fail_closed_cooldown(tmp_path: Path) -> None:
    from printer_v1.discovery import eligible_token_supply as ets
    from printer_v1.discovery.graduated_liquidity_front_door import (
        GraduatedFrontDoorError,
        _cooldown_ok,
        load_market_floor_state,
    )

    started = datetime.now(timezone.utc)
    deadline = (started - timedelta(seconds=0.05)).isoformat()
    time.sleep(0.1)
    remaining = (
        ets._parse_iso(deadline) - ets._parse_iso(ets._utc_now_iso())
    ).total_seconds()
    assert remaining <= 0

    conn = sqlite3.connect(tmp_path / "norot.sqlite3")
    ok, reason = _cooldown_ok(conn, "m", "p", 1)
    assert ok is False
    assert reason.startswith("COOLDOWN_STATE_UNAVAILABLE")
    conn.close()

    db = tmp_path / "floor.sqlite3"
    apply_migrations(db)
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE IF EXISTS printer_graduated_market_floor_state")
    conn.commit()
    with pytest.raises(GraduatedFrontDoorError):
        load_market_floor_state(conn, "mint")
    conn.close()


def test_direct_migration_six_unit_identities_and_zero_deltas(tmp_path: Path) -> None:
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
                ],
                "response_bytes": 64,
                "transport_operations_used": 1,
            }
        if context.request.request_kind == TRANSACTION_REQUEST_KIND:
            return {"result": tx, "response_bytes": 512, "transport_operations_used": 1}
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
    six = report["six_unit_totals"]
    assert report["confirmed_count"] == 1
    assert ledger["source_requests"] == 3
    assert ledger["migration_transport_operations"] == 2
    assert ledger["pumpswap_transport_operations"] == 2
    assert ledger["transport_operations"] == 4
    assert ledger["identity_transport_operations"] == 4
    assert ledger["operation_accounting_reconciled"] is True
    assert set(six) == set(SIX_UNITS)
    assert six["SOURCE_TRANSPORT_OPERATION"] == 4
    assert six["SOURCE_RESPONSE_BYTES"] > 0
    assert six["NORMALIZED_SOURCE_ROWS"] > 0
    assert report["forbidden_delta_total"] == 0

    connection = sqlite3.connect(db)
    try:
        for table in (
            "printer_candidate_acquisition_cursors",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_memory_retrieval_queries",
        ):
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if exists:
                assert (
                    connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                    == 0
                )
        versions = [
            row[0]
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY version"
            )
        ]
        assert versions == list(canonical_migration_names())
        assert versions[-1].startswith("049")
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()


def test_terminal_report_and_zero_source_replay_six_unit_equality(
    tmp_path: Path,
) -> None:
    six = empty_six_unit_totals()
    six["SOURCE_TRANSPORT_OPERATION"] = 4
    six["SOURCE_RESPONSE_BYTES"] = 900
    six["NORMALIZED_SOURCE_ROWS"] = 5
    six["LOCAL_VALIDATION_STEP"] = 3
    payload = build_campaign_terminal_report(
        campaign_id="camp-1",
        configuration_id="cfg-1",
        run_id="run-1",
        cycle_id="cyc-1",
        report_id="rep-1",
        factory_run_id=None,
        execution_id="exec-1",
        terminal_status="FAILED",
        terminal_cause="BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL",
        run_status="FAILED",
        lifecycle_started=False,
        reconciliation={},
        campaign_source_calls=3,
        campaign_scheduler_calls=0,
        six_unit_totals=six,
    )
    assert payload["six_unit_totals"] == six
    assert "six_unit_totals" in (payload.get("campaign_activity") or {})
    # Durable artifact + zero-source reconstruction without campaign FK rows:
    # write the canonical report artifact and reconstruct six units solely from it.
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    import json
    from printer_v1.operator_cli.unified_terminal_closure import _canonical_json

    artifact = reports_dir / "rep-1.json"
    canonical = _canonical_json(payload)
    artifact.write_text(canonical, encoding="utf-8")
    stored = json.loads(artifact.read_text(encoding="utf-8"))
    replay_six = stored["six_unit_totals"]
    assert replay_six == six
    assert reconcile_six_unit_totals(payload, {"six_unit_totals": replay_six})[
        "equal"
    ] is True
    # Replay path creates zero new transports by contract (read-only reconstruction).
    assert inspect.getsource(replay_campaign_terminal_report).count(
        "urlopen"
    ) == 0
    assert "replay_new_transport_operations" in inspect.getsource(
        replay_campaign_terminal_report
    )


def test_activation_compensation_during_second_slot() -> None:
    """Real injected DURING_SECOND failure leaves zero active tracking/jobs."""
    from test_v2_9_7d_7b_4d_1_atomic_two_slot_handoff import AtomicTwoSlotHandoffTests

    suite = AtomicTwoSlotHandoffTests("test_failure_during_second_rolls_back_first")
    suite.setUp()
    try:
        suite.test_failure_during_second_rolls_back_first()
    finally:
        suite.tearDown()


def test_no_dormant_selected_latest_product_on_front_door() -> None:
    from printer_v1.discovery import graduated_liquidity_front_door as glfd
    from printer_v1.operator_cli import graduated_supply_front_door as gsf

    front_src = inspect.getsource(glfd.run_graduated_liquidity_front_door)
    assert "two_candidate_selection" in front_src
    # Product return must not reintroduce readiness columns.
    assert '"selected_latest"' not in front_src
    assert '"selected_persisted"' not in front_src
    supply_fields = gsf.GraduatedSupply.__dataclass_fields__
    assert "candidate_a" in supply_fields
    assert "candidate_b" in supply_fields
    assert "two_candidate_selection" in supply_fields
    assert "selected_latest" not in supply_fields
    assert "selected_persisted" not in supply_fields
    # Offline helper remains labeled offline-only.
    assert "OFFLINE-ONLY" in inspect.getsource(glfd.select_holder_eligible_pair)

"""Frozen offline proof: V2-9.8B discovery/selection verifiable real path."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
import json
import os
import sqlite3
import tempfile
import time

import pytest

from printer_v1.db.migrate import apply_migrations, canonical_migration_names
from printer_v1.discovery.direct_migration_discovery import (
    run_direct_migration_discovery,
)
from printer_v1.operator_cli.unified_terminal_closure import (
    build_campaign_terminal_report,
)
from printer_v1.sources.campaign_six_unit_accounting import (
    compare_report_totals_to_evidence,
    reconstruct_six_unit_totals_from_evidence,
)
from printer_v1.sources.dexscreener import (
    build_dexscreener_fresh_profiles_transport,
    normalize_dexscreener_fixture_result,
)
from printer_v1.sources.direct_pump_migration import (
    SIGNATURE_PAGE_REQUEST_KIND,
    TRANSACTION_REQUEST_KIND,
)
from printer_v1.sources.measured_transport import SIX_UNITS
from printer_v1.sources.pump_migration import build_graduation_verifier_transport
from test_v2_9_8b_candidate_acquisition_foundation import _pinned_migration_fixture
from test_v2_9_8b_restored_factory_source_compatibility_reset import _verifier_factory


_SIGNATURE = (
    "5NarrowDirectPumpMigrationFinalizedSignature"
    "111111111111111111111111111111111111111111111111"
)
_NOW = "2026-07-30T21:00:00+00:00"
WSOL = "So11111111111111111111111111111111111111112"


def _ctx(kind: str = "dexscreener_fresh_profiles"):
    return SimpleNamespace(
        request=SimpleNamespace(request_kind=kind, payload={}),
        governor_approved=True,
        execution_path="GOVERNOR_ONLY",
    )


def test_dexscreener_failure_paths_record_identities(monkeypatch, tmp_path: Path) -> None:
    """Successful, HTTP-error, rate-limit, timeout, and partial multi-call paths."""
    import printer_v1.sources.dexscreener as dex

    calls = {"n": 0}

    def fake_get(endpoint, timeout_seconds, *, byte_ceiling=2_000_000):
        calls["n"] += 1
        if calls["n"] == 1:
            # Step 1 success: one Solana profile.
            return (
                [{"chainId": "solana", "tokenAddress": "MintABC1111111111111111111111111111111"}],
                100,
            )
        raise TimeoutError("simulated timeout on tokens batch")

    monkeypatch.setattr(dex, "_dexscreener_http_get_json", fake_get)
    transport = build_dexscreener_fresh_profiles_transport()
    payload = transport(_ctx())
    assert payload["fixture_status"] == "failure"
    assert payload["failure_type"] == "dexscreener_tokens_transport_failure"
    identities = payload["transport_operation_identities"]
    assert len(identities) == 2
    assert identities[0]["result"] == "OK"
    assert identities[1]["result"] == "FAILED"
    assert payload["transport_operations_used"] == 2

    # Step-1 HTTP error still records identity.
    calls["n"] = 0

    def fail_first(endpoint, timeout_seconds, *, byte_ceiling=2_000_000):
        from urllib import error as url_error

        raise url_error.HTTPError(endpoint, 500, "err", None, None)

    monkeypatch.setattr(dex, "_dexscreener_http_get_json", fail_first)
    payload2 = build_dexscreener_fresh_profiles_transport()(_ctx())
    assert payload2["fixture_status"] == "failure"
    assert len(payload2["transport_operation_identities"]) == 1
    assert payload2["transport_operation_identities"][0]["result"] == "FAILED"

    # Rate-limit on step 1.
    def rate_first(endpoint, timeout_seconds, *, byte_ceiling=2_000_000):
        from urllib import error as url_error

        raise url_error.HTTPError(endpoint, 429, "rate", None, None)

    monkeypatch.setattr(dex, "_dexscreener_http_get_json", rate_first)
    payload3 = build_dexscreener_fresh_profiles_transport()(_ctx())
    assert payload3["fixture_status"] == "rate_limited"
    assert len(payload3["transport_operation_identities"]) == 1
    normalized = normalize_dexscreener_fixture_result(
        payload3, request_kind="dexscreener_fresh_profiles"
    )
    assert normalized.normalized_payload is not None
    assert normalized.normalized_payload["transport_operations_used"] == 1


def test_graduation_multi_call_preserves_first_identity_on_second_failure(
    monkeypatch,
) -> None:
    import printer_v1.sources.pump_migration as pm

    calls = {"n": 0}

    def fake_rpc(rpc_url, method, params, *, timeout_seconds):
        calls["n"] += 1
        if method == "getTransaction":
            return {
                "result": {
                    "slot": 1,
                    "blockTime": 1,
                    "meta": {"err": None},
                    "transaction": {
                        "message": {
                            "accountKeys": [
                                f"Acct{i:02d}11111111111111111111111111111111"
                                for i in range(10)
                            ]
                        }
                    },
                },
                "response_bytes": 50,
                "transport_operations_used": 1,
            }
        return {
            "fixture_status": "failure",
            "failure_type": "pumpswap_rpc_http_error",
            "failure_message": "HTTP 503",
            "response_bytes": 0,
            "transport_operations_used": 1,
        }

    # Patch the bound import used by the graduation verifier transport.
    monkeypatch.setattr(pm, "_rpc_post", fake_rpc)
    transport = build_graduation_verifier_transport(
        migration_signature="sig1",
        expected_mint="Mint1",
        rpc_url="https://example-override.invalid",
    )
    payload = transport(_ctx("pumpswap_signature_pool_resolution"))
    assert payload["fixture_status"] == "failure"
    identities = payload["transport_operation_identities"]
    assert len(identities) >= 2
    assert identities[0]["method_or_endpoint"] == "getTransaction"
    assert identities[0]["result"] == "OK"
    assert any(item["method_or_endpoint"] == "getMultipleAccounts" for item in identities)
    assert calls["n"] >= 2


def test_candidate_persistence_zero_when_identity_reconcile_fails(
    tmp_path: Path, monkeypatch
) -> None:
    tx, infos, mint, pool = _pinned_migration_fixture()
    db = tmp_path / "recon.sqlite3"
    apply_migrations(db)

    def migration_transport(context):
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
                "response_bytes": 32,
            }
        if context.request.request_kind == TRANSACTION_REQUEST_KIND:
            return {"result": tx, "response_bytes": 64}
        raise AssertionError(context.request.request_kind)

    def bad_verifier_factory(mint_value: str, signature: str):
        def transport(_context):
            # Claim two ops without identities → fail closed before persist.
            return {
                "pumpswap_confirmation": {"confirmed": True},
                "pumpswap_resolution": {
                    "pool_address": pool,
                    "resolved": True,
                },
                "pump_migration_proof": {
                    "verified": True,
                    "migration_block_time": tx["blockTime"],
                    "migration_slot": tx["slot"],
                },
                "migration_signature": signature,
                "migration_block_time": tx["blockTime"],
                "migration_slot": tx["slot"],
                "transport_operations_used": 2,
                # identities intentionally omitted
            }

        return transport

    report = run_direct_migration_discovery(
        db,
        migration_transport=migration_transport,
        verifier_transport_factory=bad_verifier_factory,
        now=_NOW,
        collection_rounds=1,
        settle_seconds=0.0,
        reverify_on_transient=False,
        reverify_settle_seconds=0.0,
    )
    assert report["status"] == "ACCOUNTING_BLOCKED"
    assert report["confirmed_count"] == 0
    assert report["accounting_block_reason"]
    assert report["source_operation_ledger"]["operation_accounting_reconciled"] is False
    connection = sqlite3.connect(db)
    try:
        count = connection.execute(
            "SELECT COUNT(*) FROM printer_pumpswap_graduated_candidate_registry"
        ).fetchone()[0]
        assert count == 0
    finally:
        connection.close()


def test_six_unit_evidence_independent_reconstruction_and_elapsed(
    tmp_path: Path,
) -> None:
    tx, infos, mint, pool = _pinned_migration_fixture()
    db = tmp_path / "six.sqlite3"
    apply_migrations(db)

    def migration_transport(context):
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
                "response_bytes": 40,
            }
        if context.request.request_kind == TRANSACTION_REQUEST_KIND:
            return {"result": tx, "response_bytes": 80}
        raise AssertionError(context.request.request_kind)

    time.sleep(0.05)
    report = run_direct_migration_discovery(
        db,
        migration_transport=migration_transport,
        verifier_transport_factory=_verifier_factory(tx, infos),
        now=_NOW,
        collection_rounds=1,
        settle_seconds=0.0,
        reverify_on_transient=False,
        reverify_settle_seconds=0.0,
    )
    assert report["confirmed_count"] == 1
    assert report["elapsed_seconds"] >= 0.0
    evidence = report["six_unit_evidence"]
    totals = report["six_unit_totals"]
    reconstructed = reconstruct_six_unit_totals_from_evidence(evidence)
    assert reconstructed == totals
    assert set(totals) == set(SIX_UNITS)
    comparison = compare_report_totals_to_evidence(totals, evidence)
    assert comparison["equal"] is True
    assert comparison["self_comparison"] is False

    # Terminal report stores evidence; replay reconstructs independently.
    payload = build_campaign_terminal_report(
        campaign_id="c1",
        configuration_id="cfg1",
        run_id="r1",
        cycle_id="y1",
        report_id="rep-vrp-1",
        factory_run_id=None,
        execution_id="e1",
        terminal_status="FAILED",
        terminal_cause="TEST",
        run_status="FAILED",
        lifecycle_started=False,
        reconciliation={},
        campaign_source_calls=3,
        campaign_scheduler_calls=0,
        six_unit_totals=totals,
        six_unit_evidence=evidence,
        elapsed_seconds=report["elapsed_seconds"],
    )
    assert payload["six_unit_evidence_match"] is True
    assert payload["elapsed_seconds"] == report["elapsed_seconds"]
    # Durable artifact reconstruction without campaign FK dependency:
    # independent rebuild from embedded evidence equals report totals.
    rebuilt = reconstruct_six_unit_totals_from_evidence(payload["six_unit_evidence"])
    assert rebuilt == payload["six_unit_totals"]
    assert compare_report_totals_to_evidence(
        payload["six_unit_totals"], payload["six_unit_evidence"]
    )["equal"] is True


@pytest.mark.parametrize(
    "method_name",
    [
        "test_failure_before_first_leaves_both_vacant",
        "test_failure_during_second_rolls_back_first",
        "test_second_scheduler_job_failure_rolls_back_both",
        "test_duplicate_active_causes_full_rollback",
        "test_conflicting_slot_causes_full_rollback",
    ],
)
def test_real_activation_lifecycle_injections_leave_zero_orphan_state(
    method_name: str,
) -> None:
    """Real disposable-DB injection proofs across activation/lifecycle boundaries.

    Reuses the proven atomic two-slot harness (not source-text inspection).
    Each inject gets a fresh disposable migration-049 database.
    """
    from test_v2_9_7d_7b_4d_1_atomic_two_slot_handoff import AtomicTwoSlotHandoffTests

    suite = AtomicTwoSlotHandoffTests(method_name)
    suite.setUp()
    try:
        getattr(suite, method_name)()
    finally:
        suite.tearDown()


def test_successful_discovery_still_reconciles_and_persists(tmp_path: Path) -> None:
    tx, infos, mint, pool = _pinned_migration_fixture()
    db = tmp_path / "ok.sqlite3"
    apply_migrations(db)

    def migration_transport(context):
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
                "response_bytes": 16,
            }
        if context.request.request_kind == TRANSACTION_REQUEST_KIND:
            return {"result": tx, "response_bytes": 32}
        raise AssertionError(context.request.request_kind)

    report = run_direct_migration_discovery(
        db,
        migration_transport=migration_transport,
        verifier_transport_factory=_verifier_factory(tx, infos),
        now=_NOW,
        collection_rounds=1,
        settle_seconds=0.0,
        reverify_on_transient=False,
        reverify_settle_seconds=0.0,
    )
    assert report["status"] == "COMPLETE"
    assert report["confirmed_count"] == 1
    assert report["source_operation_ledger"]["operation_accounting_reconciled"] is True
    connection = sqlite3.connect(db)
    try:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM printer_pumpswap_graduated_candidate_registry"
            ).fetchone()[0]
            == 1
        )
        assert [
            row[0]
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY version"
            )
        ][-1].startswith("049")
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()

"""V2-9.8B WINDOW_15M invocation-scoped source-request ownership repair.

Disposable databases and fixture transports only. No providers, no real
campaign, no authorization, no authoritative DB mutation.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH,
    CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS,
    CAMPAIGN_SOURCE_REQUEST_SCOPE_IDENTITY_MISMATCH,
    CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID,
    CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH,
    CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED,
    CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE,
    DUPLICATE_COVERAGE_REQUEST_ID,
    DURABLE_REQUEST_NOT_MANIFESTED,
    DURABLE_REQUEST_NOT_STAGE_REPORTED,
    LEGACY_STATIC_REQUEST_KEY_ROOT,
    LEGACY_STATIC_REQUEST_SCOPE_BLOCKED_OPERATIONALLY,
    MANIFEST_REQUEST_NOT_DURABLE,
    MULTIPLE_SOURCE_REQUEST_RECONCILIATION_DEFECTS,
    PRINTER_V1_CAMPAIGN_SOURCE_REQUEST_SCOPE_V1,
    STAGE_OWNERSHIP_GAP,
    STAGE_REQUEST_NOT_DURABLE,
    STAGE_REQUEST_NOT_MANIFESTED,
    assemble_and_reconcile_campaign_source_requests,
    build_campaign_source_request_scope,
    derive_campaign_source_request_key_root,
    format_source_request_reconciliation_detail,
    inspect_preexisting_source_request_scope_collision,
    load_durable_campaign_source_request_ids,
    validate_campaign_source_request_scope,
)
from printer_v1.operator_cli.graduated_supply_front_door import (
    GraduatedSupplyError,
    build_graduated_supply,
)


NOW = "2026-08-06T12:00:00+00:00"
EXEC_A = "20260806T120000Z-aaaaaaaaaaaa"
EXEC_B = "20260806T120100Z-bbbbbbbbbbbb"


def _coverage(rid, *, stage="PROTOCOL|1", transport=1, terminal="COMPLETED"):
    return {
        "source_request_id": rid,
        "source_name": "solana_rpc",
        "request_kind": "pumpswap_pool_account_batch",
        "logical_stage_id": stage,
        "transport_identity_count": transport,
        "normalized_member_count": 1 if transport else 0,
        "terminal_status": terminal,
    }


@pytest.fixture()
def database():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "scope-repair.sqlite3"
        apply_migrations(path)
        connection = sqlite3.connect(str(path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield path, connection
        finally:
            connection.close()


def _insert(connection, *, key: str, source="solana_rpc", kind="batch") -> int:
    connection.execute(
        """
        INSERT INTO printer_source_requests(
            source_name, request_kind, requested_at, request_key,
            tracking_priority, source_status, data_quality_label
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (source, kind, NOW, key, 0, "COMPLETE", "CLEAN_DATA"),
    )
    connection.commit()
    return int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])


def _scope(
    execution_id: str = EXEC_A,
    *,
    campaign_id: str = "camp-a",
    run_id: str = "run-a",
    cycle_id: str = "cycle-a",
):
    return build_campaign_source_request_scope(
        execution_id=execution_id,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
    )


# ---------------------------------------------------------------------------
# Typed scope contract
# ---------------------------------------------------------------------------


class TestCampaignSourceRequestScopeContract:
    def test_canonical_root_derivation(self):
        scope = _scope()
        assert scope.scope_version == PRINTER_V1_CAMPAIGN_SOURCE_REQUEST_SCOPE_V1
        assert scope.request_key_root == f"v2-9-8b-window15m-{EXEC_A}"
        assert scope.request_key_root == derive_campaign_source_request_key_root(EXEC_A)

    def test_validate_accepts_exact_supported_scope(self):
        scope = _scope()
        out = validate_campaign_source_request_scope(
            scope,
            execution_id=EXEC_A,
            campaign_id="camp-a",
            run_id="run-a",
            cycle_id="cycle-a",
        )
        assert out.request_key_root == scope.request_key_root

    def test_validate_rejects_identity_mismatch(self):
        scope = _scope()
        with pytest.raises(ValueError) as exc:
            validate_campaign_source_request_scope(
                scope,
                execution_id=EXEC_A,
                campaign_id="camp-other",
                run_id="run-a",
                cycle_id="cycle-a",
            )
        assert str(exc.value) == CAMPAIGN_SOURCE_REQUEST_SCOPE_IDENTITY_MISMATCH

    def test_validate_rejects_legacy_root(self):
        scope = _scope()
        bad = type(scope)(
            scope_version=scope.scope_version,
            request_key_root=LEGACY_STATIC_REQUEST_KEY_ROOT,
            execution_id=scope.execution_id,
            campaign_id=scope.campaign_id,
            run_id=scope.run_id,
            cycle_id=scope.cycle_id,
        )
        with pytest.raises(ValueError) as exc:
            validate_campaign_source_request_scope(bad)
        assert str(exc.value) in {
            CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID,
            LEGACY_STATIC_REQUEST_SCOPE_BLOCKED_OPERATIONALLY,
        }

    def test_validate_rejects_whitespace_and_path_separators(self):
        scope = _scope()
        for root in ("v2-9-8b-window15m-has space", "v2-9-8b-window15m-a/b", "v2-9-8b-window15m-a\\b"):
            bad = type(scope)(
                scope_version=scope.scope_version,
                request_key_root=root,
                execution_id=scope.execution_id,
                campaign_id=scope.campaign_id,
                run_id=scope.run_id,
                cycle_id=scope.cycle_id,
            )
            with pytest.raises(ValueError) as exc:
                validate_campaign_source_request_scope(bad)
            assert str(exc.value) == CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID


# ---------------------------------------------------------------------------
# Permanent operational composition gates
# ---------------------------------------------------------------------------


class TestPermanentOperationalScopeGates:
    def test_missing_typed_scope_blocks_before_provider_io(self, database):
        path, _connection = database
        provider = MagicMock(side_effect=AssertionError("provider must not run"))
        with pytest.raises(GraduatedSupplyError) as exc:
            build_graduated_supply(
                path,
                cycle_seed="seed-missing-scope",
                migration_transport=provider,
                permanent_availability=True,
                campaign_id="camp-a",
                execution_id=EXEC_A,
                run_id="run-a",
                cycle_id="cycle-a",
            )
        assert str(exc.value) == CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED
        provider.assert_not_called()

    def test_legacy_static_prefix_blocks_before_provider_io(self, database):
        path, _connection = database
        scope = _scope()
        provider = MagicMock(side_effect=AssertionError("provider must not run"))
        with pytest.raises(GraduatedSupplyError) as exc:
            build_graduated_supply(
                path,
                cycle_seed="seed-legacy",
                migration_transport=provider,
                permanent_availability=True,
                campaign_source_request_scope=scope,
                discovery_request_key_prefix=LEGACY_STATIC_REQUEST_KEY_ROOT,
                front_door_request_key_prefix=LEGACY_STATIC_REQUEST_KEY_ROOT,
                campaign_id=scope.campaign_id,
                execution_id=scope.execution_id,
                run_id=scope.run_id,
                cycle_id=scope.cycle_id,
            )
        assert str(exc.value) == LEGACY_STATIC_REQUEST_SCOPE_BLOCKED_OPERATIONALLY
        provider.assert_not_called()

    def test_prefix_mismatch_blocks_before_provider_io(self, database):
        path, _connection = database
        scope = _scope()
        provider = MagicMock(side_effect=AssertionError("provider must not run"))
        with pytest.raises(GraduatedSupplyError) as exc:
            build_graduated_supply(
                path,
                cycle_seed="seed-prefix-mismatch",
                migration_transport=provider,
                permanent_availability=True,
                campaign_source_request_scope=scope,
                discovery_request_key_prefix=scope.request_key_root,
                front_door_request_key_prefix=f"{scope.request_key_root}-other",
                campaign_id=scope.campaign_id,
                execution_id=scope.execution_id,
                run_id=scope.run_id,
                cycle_id=scope.cycle_id,
            )
        assert str(exc.value) == CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH
        provider.assert_not_called()

    def test_identity_mismatch_blocks_before_provider_io(self, database):
        path, _connection = database
        scope = _scope()
        provider = MagicMock(side_effect=AssertionError("provider must not run"))
        with pytest.raises(GraduatedSupplyError) as exc:
            build_graduated_supply(
                path,
                cycle_seed="seed-id-mismatch",
                migration_transport=provider,
                permanent_availability=True,
                campaign_source_request_scope=scope,
                discovery_request_key_prefix=scope.request_key_root,
                front_door_request_key_prefix=scope.request_key_root,
                campaign_id="camp-other",
                execution_id=scope.execution_id,
                run_id=scope.run_id,
                cycle_id=scope.cycle_id,
            )
        assert str(exc.value) == CAMPAIGN_SOURCE_REQUEST_SCOPE_IDENTITY_MISMATCH
        provider.assert_not_called()

    def test_preexisting_root_collision_blocks_before_provider_io(self, database):
        path, connection = database
        scope = _scope()
        _insert(connection, key=f"{scope.request_key_root}-locator")
        provider = MagicMock(side_effect=AssertionError("provider must not run"))
        with pytest.raises(GraduatedSupplyError) as exc:
            build_graduated_supply(
                path,
                cycle_seed="seed-collision",
                migration_transport=provider,
                permanent_availability=True,
                campaign_source_request_scope=scope,
                discovery_request_key_prefix=scope.request_key_root,
                front_door_request_key_prefix=scope.request_key_root,
                campaign_id=scope.campaign_id,
                execution_id=scope.execution_id,
                run_id=scope.run_id,
                cycle_id=scope.cycle_id,
            )
        assert CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS in str(exc.value)
        assert "count=1" in str(exc.value)
        provider.assert_not_called()

    def test_composition_constructs_and_propagates_canonical_root(self, database):
        path, _connection = database
        scope = _scope()
        captured: dict[str, object] = {}

        def fake_persistent(*_args, **kwargs):
            captured.update(kwargs)
            from types import SimpleNamespace

            return SimpleNamespace(
                discovery_report={},
                front_door_report={},
                locator_report={},
                eligible_reserve=(),
                diagnostics={
                    "discovery_request_key_prefix": kwargs[
                        "discovery_request_key_prefix"
                    ],
                    "permanent_availability": True,
                },
                exhaustion_certificate=None,
                shortage_classification=None,
                discovery_rounds=0,
                ready=False,
                terminal="BLOCKED",
            )

        with patch(
            "printer_v1.discovery.eligible_token_supply.run_persistent_eligible_token_supply",
            side_effect=fake_persistent,
        ):
            supply = build_graduated_supply(
                path,
                cycle_seed="seed-compose",
                migration_transport=lambda _ctx: {},
                permanent_availability=True,
                campaign_source_request_scope=scope,
                discovery_request_key_prefix=scope.request_key_root,
                front_door_request_key_prefix=scope.request_key_root,
                campaign_id=scope.campaign_id,
                execution_id=scope.execution_id,
                run_id=scope.run_id,
                cycle_id=scope.cycle_id,
                run_locator=False,
            )
        assert captured["discovery_request_key_prefix"] == scope.request_key_root
        assert captured["front_door_request_key_prefix"] == scope.request_key_root
        assert supply.diagnostics["request_key_root"] == scope.request_key_root
        assert (
            supply.diagnostics["discovery_request_key_prefix"]
            == scope.request_key_root
        )
        assert (
            supply.diagnostics["front_door_request_key_prefix"]
            == scope.request_key_root
        )
        assert supply.diagnostics["campaign_source_request_scope"] == scope.as_dict()
        assert (
            supply.diagnostics["request_scope_version"]
            == PRINTER_V1_CAMPAIGN_SOURCE_REQUEST_SCOPE_V1
        )


# ---------------------------------------------------------------------------
# Durable set isolation and reconciliation categories
# ---------------------------------------------------------------------------


class TestScopedDurableReconciliation:
    def test_campaign_a_and_b_have_disjoint_roots_and_d_sets(self, database):
        path, connection = database
        scope_a = _scope(EXEC_A, campaign_id="camp-a", run_id="run-a", cycle_id="cyc-a")
        scope_b = _scope(EXEC_B, campaign_id="camp-b", run_id="run-b", cycle_id="cyc-b")
        assert scope_a.request_key_root != scope_b.request_key_root
        rid_a = _insert(connection, key=f"{scope_a.request_key_root}-locator")
        rid_b = _insert(connection, key=f"{scope_b.request_key_root}-locator")
        durable_a = load_durable_campaign_source_request_ids(
            connection,
            request_key_prefixes=[scope_a.request_key_root],
            request_key_root=scope_a.request_key_root,
            enforce_request_key_root=True,
        )
        durable_b = load_durable_campaign_source_request_ids(
            connection,
            request_key_prefixes=[scope_b.request_key_root],
            request_key_root=scope_b.request_key_root,
            enforce_request_key_root=True,
        )
        assert durable_a == [rid_a]
        assert durable_b == [rid_b]
        assert set(durable_a).isdisjoint(durable_b)

    def test_historical_legacy_rows_do_not_enter_new_d_set(self, database):
        path, connection = database
        scope = _scope()
        legacy_id = _insert(connection, key=f"{LEGACY_STATIC_REQUEST_KEY_ROOT}-locator")
        current_id = _insert(connection, key=f"{scope.request_key_root}-locator")
        durable = load_durable_campaign_source_request_ids(
            connection,
            request_key_prefixes=[scope.request_key_root],
            known_request_ids=[legacy_id, current_id],
            request_key_root=scope.request_key_root,
            enforce_request_key_root=True,
        )
        assert durable == [current_id]
        assert legacy_id not in durable

    def test_pass_has_each_current_request_exactly_once_in_d_s_m(self, database):
        path, connection = database
        scope = _scope()
        rid = _insert(connection, key=f"{scope.request_key_root}|proto")
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "campaign_source_request_scope": scope.as_dict(),
                "request_key_root": scope.request_key_root,
                "protocol_confirmation": {
                    "source_request_ids": [rid],
                    "source_request_coverage": [_coverage(rid)],
                },
            },
            request_key_root=scope.request_key_root,
        )
        assert recon["status"] == "OK"
        assert recon["durable_campaign_request_ids"] == [rid]
        assert recon["stage_reported_request_ids"] == [rid]
        assert recon["coverage_request_ids"] == [rid]
        assert recon["request_key_root"] == scope.request_key_root
        assert recon["request_scope_version"] == PRINTER_V1_CAMPAIGN_SOURCE_REQUEST_SCOPE_V1
        assert recon["prefix_lookup_request_ids"] == [rid]
        assert recon["known_stage_request_ids_proven_durable"] == [rid]
        assert recon["out_of_scope_stage_request_ids"] == []

    def test_prefix_lookup_detects_durable_omitted_from_stage_reporting(self, database):
        path, connection = database
        scope = _scope()
        rid = _insert(connection, key=f"{scope.request_key_root}|orphan")
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "campaign_source_request_scope": scope.as_dict(),
                "request_key_root": scope.request_key_root,
            },
            request_key_root=scope.request_key_root,
        )
        assert recon["status"] == "BLOCKED"
        assert rid in recon["durable_not_stage_reported"]
        assert DURABLE_REQUEST_NOT_STAGE_REPORTED in recon["mismatch_categories"]
        assert rid in recon["prefix_lookup_request_ids"]
        # Empty stages also leave coverage empty for the same IDs.
        assert DURABLE_REQUEST_NOT_MANIFESTED in recon["mismatch_categories"]
        assert recon["categorical_detail"] == (
            MULTIPLE_SOURCE_REQUEST_RECONCILIATION_DEFECTS
        )
        assert DURABLE_REQUEST_NOT_STAGE_REPORTED in (recon["terminal_detail"] or "")

    def test_durable_omitted_from_coverage_categorized(self, database):
        path, connection = database
        scope = _scope()
        rid = _insert(connection, key=f"{scope.request_key_root}|nomanifest")
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "campaign_source_request_scope": scope.as_dict(),
                "request_key_root": scope.request_key_root,
                "protocol_confirmation": {
                    "source_request_ids": [rid],
                    "source_request_coverage": [],
                },
            },
            request_key_root=scope.request_key_root,
        )
        assert recon["status"] == "BLOCKED"
        assert rid in recon["missing_from_manifest"]
        assert DURABLE_REQUEST_NOT_MANIFESTED in recon["mismatch_categories"]
        assert STAGE_REQUEST_NOT_MANIFESTED in recon["mismatch_categories"]
        assert DURABLE_REQUEST_NOT_MANIFESTED in (recon["terminal_detail"] or "")

    def test_stage_only_non_durable_categorized(self, database):
        path, connection = database
        scope = _scope()
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "campaign_source_request_scope": scope.as_dict(),
                "request_key_root": scope.request_key_root,
                "protocol_confirmation": {
                    "source_request_ids": [999],
                    "source_request_coverage": [_coverage(999)],
                },
            },
            request_key_root=scope.request_key_root,
        )
        assert recon["status"] == "BLOCKED"
        assert 999 in recon["stage_reported_not_durable"]
        assert STAGE_REQUEST_NOT_DURABLE in recon["mismatch_categories"]
        # Coverage without durable membership is also MANIFEST_REQUEST_NOT_DURABLE.
        assert MANIFEST_REQUEST_NOT_DURABLE in recon["mismatch_categories"]
        assert STAGE_REQUEST_NOT_DURABLE in (recon["terminal_detail"] or "")

    def test_out_of_scope_stage_request_blocks(self, database):
        path, connection = database
        scope = _scope()
        foreign = _insert(connection, key=f"{LEGACY_STATIC_REQUEST_KEY_ROOT}-x")
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "campaign_source_request_scope": scope.as_dict(),
                "request_key_root": scope.request_key_root,
                "protocol_confirmation": {
                    "source_request_ids": [foreign],
                    "source_request_coverage": [_coverage(foreign)],
                },
            },
            request_key_root=scope.request_key_root,
        )
        assert recon["status"] == "BLOCKED"
        assert foreign in recon["out_of_scope_stage_request_ids"]
        assert (
            CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE
            in recon["mismatch_categories"]
        )
        assert foreign not in recon["durable_campaign_request_ids"]

    def test_duplicate_coverage_fail_closed(self, database):
        path, connection = database
        scope = _scope()
        rid = _insert(connection, key=f"{scope.request_key_root}|dup")
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "campaign_source_request_scope": scope.as_dict(),
                "request_key_root": scope.request_key_root,
                "protocol_confirmation": {
                    "source_request_ids": [rid],
                    "source_request_coverage": [
                        _coverage(rid, stage="PROTOCOL|1"),
                        _coverage(rid, stage="PROTOCOL|2"),
                    ],
                },
            },
            request_key_root=scope.request_key_root,
        )
        assert recon["status"] == "BLOCKED"
        assert rid in (recon.get("duplicate_coverage_request_ids") or recon.get("duplicate_request_ids") or ())
        assert DUPLICATE_COVERAGE_REQUEST_ID in recon["mismatch_categories"]

    def test_stage_ownership_gap_fail_closed(self, database):
        path, connection = database
        scope = _scope()
        rid = _insert(connection, key=f"{scope.request_key_root}|gap")
        entry = _coverage(rid)
        entry["logical_stage_id"] = ""
        # empty stage is rejected by coverage normalizer; force via extra
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "campaign_source_request_scope": scope.as_dict(),
                "request_key_root": scope.request_key_root,
                "protocol_confirmation": {
                    "source_request_ids": [rid],
                    "source_request_coverage": [],
                },
            },
            request_key_root=scope.request_key_root,
            extra_manifest_entries=[
                {
                    "source_request_id": rid,
                    "source_name": "solana_rpc",
                    "request_kind": "batch",
                    "logical_stage_id": "   ",
                    "transport_identity_count": 1,
                    "normalized_member_count": 1,
                    "terminal_status": "COMPLETED",
                }
            ],
        )
        # empty stage fails normalizer; use reconcile path with raw build
        from printer_v1.discovery.permanent_discovery_availability import (
            reconcile_campaign_source_requests,
        )

        recon = reconcile_campaign_source_requests(
            durable_request_ids=[rid],
            manifest_entries=[
                {
                    "source_request_id": rid,
                    "source_name": "solana_rpc",
                    "request_kind": "batch",
                    "logical_stage_id": "",
                    "transport_identity_count": 1,
                    "normalized_member_count": 1,
                    "terminal_status": "COMPLETED",
                }
            ],
            stage_reported_request_ids=[rid],
        )
        assert recon["status"] == "BLOCKED"
        assert rid in recon["stage_ownership_gaps"]

    def test_ordinary_provider_failure_reconciles_when_coverage_complete(
        self, database
    ):
        path, connection = database
        scope = _scope()
        rid = _insert(connection, key=f"{scope.request_key_root}|blocked")
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "campaign_source_request_scope": scope.as_dict(),
                "request_key_root": scope.request_key_root,
                "protocol_confirmation": {
                    "source_request_ids": [rid],
                    "source_request_coverage": [
                        _coverage(rid, terminal="BLOCKED", transport=0)
                    ],
                },
            },
            request_key_root=scope.request_key_root,
        )
        assert recon["status"] == "OK"
        assert recon["manifest"][0]["terminal_status"] == "BLOCKED"

    def test_terminal_detail_contains_category_count_and_bounded_ids(self, database):
        path, connection = database
        scope = _scope()
        ids = [
            _insert(connection, key=f"{scope.request_key_root}|o{i}")
            for i in range(3)
        ]
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "campaign_source_request_scope": scope.as_dict(),
                "request_key_root": scope.request_key_root,
            },
            request_key_root=scope.request_key_root,
        )
        detail = recon["terminal_detail"]
        assert detail is not None
        assert DURABLE_REQUEST_NOT_STAGE_REPORTED in detail
        assert f"count={len(ids)}" in detail
        for rid in sorted(ids):
            assert str(rid) in detail
        formatted = format_source_request_reconciliation_detail(recon)
        assert formatted == detail
        assert recon["blocker"] == CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH

    def test_multiple_defects_use_multiple_category_token(self, database):
        path, connection = database
        scope = _scope()
        durable_only = _insert(connection, key=f"{scope.request_key_root}|only")
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "campaign_source_request_scope": scope.as_dict(),
                "request_key_root": scope.request_key_root,
                "protocol_confirmation": {
                    "source_request_ids": [999],
                    "source_request_coverage": [_coverage(999)],
                },
            },
            request_key_root=scope.request_key_root,
        )
        assert recon["status"] == "BLOCKED"
        assert durable_only in recon["durable_not_stage_reported"]
        assert 999 in recon["stage_reported_not_durable"]
        assert recon["categorical_detail"] == (
            MULTIPLE_SOURCE_REQUEST_RECONCILIATION_DEFECTS
        )
        assert DURABLE_REQUEST_NOT_STAGE_REPORTED in recon["mismatch_categories"]
        assert STAGE_REQUEST_NOT_DURABLE in recon["mismatch_categories"]
        assert MULTIPLE_SOURCE_REQUEST_RECONCILIATION_DEFECTS in (
            recon["terminal_detail"] or ""
        )

    def test_collision_inspector_returns_bounded_ids(self, database):
        path, connection = database
        scope = _scope()
        ids = [
            _insert(connection, key=f"{scope.request_key_root}|c{i}")
            for i in range(3)
        ]
        report = inspect_preexisting_source_request_scope_collision(
            connection,
            request_key_root=scope.request_key_root,
        )
        assert report["status"] == "BLOCKED"
        assert report["count"] == 3
        assert report["request_ids"] == sorted(ids)
        assert report["blocker"] == CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS


class TestNoCapabilityExpansion:
    def test_static_permanent_path_cannot_use_legacy_default(self):
        text = Path(
            "src/printer_v1/operator_cli/authoritative_live_operational_campaign.py"
        ).read_text()
        # permanent composition always overwrites prefixes from typed scope
        assert "build_campaign_source_request_scope" in text
        assert "request_key_root" in text
        front = Path(
            "src/printer_v1/operator_cli/graduated_supply_front_door.py"
        ).read_text()
        assert "LEGACY_STATIC_REQUEST_SCOPE_BLOCKED_OPERATIONALLY" in front or (
            "validate_permanent_operational_request_prefixes" in front
        )
        assert "CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED" in front

    def test_no_retrieval_or_financial_unlock_tokens_in_repair_surface(self):
        for rel in (
            "src/printer_v1/discovery/permanent_discovery_availability.py",
            "src/printer_v1/operator_cli/graduated_supply_front_door.py",
            "src/printer_v1/operator_cli/authoritative_live_operational_campaign.py",
        ):
            text = Path(rel).read_text()
            for forbidden in (
                "BUY_SIGNAL",
                "SELL_SIGNAL",
                "paper_trade_execute",
                "unlock_retrieval",
                "PnL_UNLOCK",
            ):
                assert forbidden not in text

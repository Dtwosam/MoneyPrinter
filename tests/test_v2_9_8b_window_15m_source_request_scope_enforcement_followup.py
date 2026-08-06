"""V2-9.8B WINDOW_15M source-request scope enforcement follow-up.

Disposable migrated DBs only. No providers, authorization, or runtime.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH,
    CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID,
    CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH,
    CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED,
    CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE,
    LEGACY_STATIC_REQUEST_KEY_ROOT,
    PRINTER_V1_CAMPAIGN_SOURCE_REQUEST_SCOPE_V1,
    STAGE_REQUEST_NOT_DURABLE,
    assemble_and_reconcile_campaign_source_requests,
    build_campaign_source_request_scope,
    load_durable_campaign_source_request_ids,
    load_prefix_lookup_request_ids,
)


NOW = "2026-08-06T12:00:00+00:00"
EXEC_A = "20260806T120000Z-aaaaaaaaaaaa"
EXEC_B = "20260806T120100Z-bbbbbbbbbbbb"


def _coverage(rid, *, stage="PROTOCOL|1", transport=1, terminal="COMPLETED"):
    keys = [
        [
            "PROTOCOL_CONFIRMATION",
            "solana_rpc",
            "pumpswap_pool_account_batch",
            "getMultipleAccounts",
            index + 1,
            "source_request",
            str(rid),
        ]
        for index in range(transport)
    ]
    return {
        "source_request_id": rid,
        "source_name": "solana_rpc",
        "request_kind": "pumpswap_pool_account_batch",
        "logical_stage_id": stage,
        "transport_identity_count": transport,
        "transport_identity_keys": keys,
        "normalized_member_count": 1 if transport else 0,
        "terminal_status": terminal,
    }


@pytest.fixture()
def database():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "scope-enforcement.sqlite3"
        apply_migrations(path)
        connection = sqlite3.connect(str(path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield path, connection
        finally:
            connection.close()


def _insert(connection, *, key: str) -> int:
    connection.execute(
        """
        INSERT INTO printer_source_requests(
            source_name, request_kind, requested_at, request_key,
            tracking_priority, source_status, data_quality_label
        ) VALUES (?,?,?,?,?,?,?)
        """,
        ("solana_rpc", "batch", NOW, key, 0, "COMPLETE", "CLEAN_DATA"),
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


class TestRowLevelRootFilter:
    def test_enforce_with_foreign_prefix_cannot_add_foreign_row_to_d(self, database):
        _path, connection = database
        scope = _scope()
        foreign = _scope(EXEC_B, campaign_id="camp-b", run_id="run-b", cycle_id="cyc-b")
        current_id = _insert(connection, key=f"{scope.request_key_root}|cur")
        foreign_id = _insert(connection, key=f"{foreign.request_key_root}|for")
        durable = load_durable_campaign_source_request_ids(
            connection,
            request_key_prefixes=[scope.request_key_root, foreign.request_key_root],
            known_request_ids=[current_id, foreign_id],
            request_key_root=scope.request_key_root,
            enforce_request_key_root=True,
        )
        assert durable == [current_id]
        assert foreign_id not in durable

        prefix_ids = load_prefix_lookup_request_ids(
            connection,
            request_key_prefixes=[scope.request_key_root, foreign.request_key_root],
            request_key_root=scope.request_key_root,
            enforce_request_key_root=True,
        )
        assert prefix_ids == [current_id]
        assert foreign_id not in prefix_ids


class TestScopedReconciliationFailClosed:
    def test_foreign_supplied_prefix_blocks(self, database):
        _path, connection = database
        scope = _scope()
        with pytest.raises(ValueError) as exc:
            assemble_and_reconcile_campaign_source_requests(
                connection,
                diagnostics={
                    "campaign_source_request_scope": scope.as_dict(),
                    "request_key_root": scope.request_key_root,
                },
                request_key_root=scope.request_key_root,
                request_key_prefixes=[
                    scope.request_key_root,
                    LEGACY_STATIC_REQUEST_KEY_ROOT,
                ],
                campaign_source_request_scope=scope,
            )
        assert str(exc.value) == CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH

    def test_invalid_scope_version_blocks(self, database):
        _path, connection = database
        scope = _scope()
        bad = {
            **scope.as_dict(),
            "scope_version": "PRINTER_V1_CAMPAIGN_SOURCE_REQUEST_SCOPE_V0",
        }
        with pytest.raises(ValueError) as exc:
            assemble_and_reconcile_campaign_source_requests(
                connection,
                diagnostics={"campaign_source_request_scope": bad},
                campaign_source_request_scope=bad,
                request_key_root=scope.request_key_root,
            )
        assert str(exc.value) == CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID

    def test_malformed_canonical_root_blocks(self, database):
        _path, connection = database
        scope = _scope()
        bad = {
            **scope.as_dict(),
            "request_key_root": "v2-9-8b-window15m-has space",
        }
        with pytest.raises(ValueError) as exc:
            assemble_and_reconcile_campaign_source_requests(
                connection,
                diagnostics={"campaign_source_request_scope": bad},
                campaign_source_request_scope=bad,
            )
        assert str(exc.value) == CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID

    def test_explicit_root_differing_from_scope_blocks(self, database):
        _path, connection = database
        scope = _scope()
        other = _scope(EXEC_B, campaign_id="camp-b", run_id="run-b", cycle_id="cyc-b")
        with pytest.raises(ValueError) as exc:
            assemble_and_reconcile_campaign_source_requests(
                connection,
                diagnostics={
                    "campaign_source_request_scope": scope.as_dict(),
                    "request_key_root": scope.request_key_root,
                },
                campaign_source_request_scope=scope,
                request_key_root=other.request_key_root,
            )
        assert str(exc.value) == CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH

    def test_diagnostic_root_differing_from_scope_blocks(self, database):
        _path, connection = database
        scope = _scope()
        other = _scope(EXEC_B, campaign_id="camp-b", run_id="run-b", cycle_id="cyc-b")
        with pytest.raises(ValueError) as exc:
            assemble_and_reconcile_campaign_source_requests(
                connection,
                diagnostics={
                    "campaign_source_request_scope": scope.as_dict(),
                    "request_key_root": other.request_key_root,
                },
                campaign_source_request_scope=scope,
            )
        assert str(exc.value) == CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH

    def test_root_without_typed_scope_requires_scope(self, database):
        _path, connection = database
        scope = _scope()
        with pytest.raises(ValueError) as exc:
            assemble_and_reconcile_campaign_source_requests(
                connection,
                diagnostics={},
                request_key_root=scope.request_key_root,
            )
        assert str(exc.value) == CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED

    def test_current_root_known_and_prefix_reconcile_d_s_m(self, database):
        _path, connection = database
        scope = _scope()
        rid_known = _insert(connection, key=f"{scope.request_key_root}|proto")
        rid_prefix = _insert(connection, key=f"{scope.request_key_root}|orphan")
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "campaign_source_request_scope": scope.as_dict(),
                "request_key_root": scope.request_key_root,
                "protocol_confirmation": {
                    "source_request_ids": [rid_known, rid_prefix],
                    "source_request_coverage": [
                        _coverage(rid_known),
                        _coverage(rid_prefix, stage="LOCATOR|1"),
                    ],
                },
            },
            request_key_root=scope.request_key_root,
            request_key_prefixes=[scope.request_key_root],
            campaign_source_request_scope=scope,
        )
        assert recon["status"] == "OK"
        assert recon["durable_campaign_request_ids"] == sorted(
            [rid_known, rid_prefix]
        )
        assert recon["stage_reported_request_ids"] == sorted(
            [rid_known, rid_prefix]
        )
        assert recon["coverage_request_ids"] == sorted([rid_known, rid_prefix])
        assert recon["request_key_root"] == scope.request_key_root
        assert recon["request_scope_version"] == PRINTER_V1_CAMPAIGN_SOURCE_REQUEST_SCOPE_V1
        assert set(recon["prefix_lookup_request_ids"]) == {rid_known, rid_prefix}

    def test_foreign_durable_stage_ids_remain_out_of_scope(self, database):
        _path, connection = database
        scope = _scope()
        foreign = _insert(
            connection, key=f"{LEGACY_STATIC_REQUEST_KEY_ROOT}-legacy"
        )
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
            campaign_source_request_scope=scope,
        )
        assert recon["status"] == "BLOCKED"
        assert recon["blocker"] == CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH
        assert foreign in recon["out_of_scope_stage_request_ids"]
        assert foreign not in recon["durable_campaign_request_ids"]
        assert foreign not in recon["stage_reported_not_durable"]
        assert (
            CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE
            in recon["mismatch_categories"]
        )
        assert STAGE_REQUEST_NOT_DURABLE not in recon["mismatch_categories"]
        assert CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE in (
            recon["terminal_detail"] or ""
        )
        assert "count=1" in (recon["terminal_detail"] or "")
        assert str(foreign) in (recon["terminal_detail"] or "")


class TestUnscopedLegacyPreserved:
    def test_unscoped_multi_prefix_still_loads_both(self, database):
        _path, connection = database
        a = _insert(connection, key="prefix-a|1")
        b = _insert(connection, key="prefix-b|1")
        durable = load_durable_campaign_source_request_ids(
            connection,
            request_key_prefixes=["prefix-a", "prefix-b"],
            enforce_request_key_root=False,
        )
        assert durable == sorted([a, b])
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "protocol_confirmation": {
                    "source_request_ids": [a, b],
                    "source_request_coverage": [
                        _coverage(a),
                        _coverage(b, stage="LOCATOR|1"),
                    ],
                }
            },
            request_key_prefixes=["prefix-a", "prefix-b"],
        )
        assert recon["status"] == "OK"
        assert recon["durable_campaign_request_ids"] == sorted([a, b])
        assert recon["request_key_root"] is None

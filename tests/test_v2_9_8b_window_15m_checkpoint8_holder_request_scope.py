from __future__ import annotations

import inspect
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    assemble_and_reconcile_campaign_source_requests,
    build_campaign_source_request_scope,
)
from printer_v1.operator_cli import holder_reliability_budget_control as budget
from printer_v1.operator_cli.holder_reliability_budget_control import (
    persist_bundle_attempts,
)
from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli import safety_context_source_redundancy as redundancy
from printer_v1.sources.goplus import build_goplus_adapter
from printer_v1.sources.measured_transport import TransportOperationIdentity


MINT = "5aNJBy3n3AjsGZ2qvQFKfV6BhKSTQU6MXxN2sjGu8nei"
PAIR = "9cYjsG3zN83FAKeBYEPVwqZwM4vGQe7VwrAA5TjAi6qW"
NOW = "2026-08-07T20:30:18+00:00"
NOW_DT = datetime(2026, 8, 7, 20, 30, 18, tzinfo=timezone.utc)
EXECUTION_ID = "dtw50-scope-execution"
CAMPAIGN_ID = "dtw50-campaign"
RUN_ID = "dtw50-run"
CYCLE_ID = "dtw50-cycle"


def _fixture_transport(_context):
    payload = {
        "token_mint": MINT,
        "mint_authority": None,
        "freeze_authority": None,
        "metadata_mutable": False,
        "total_supply": "1000000000",
        "top_10_holders": [{"percent": "3"} for _ in range(10)],
        "lp_info": [{"locked": True}],
        "risk_flags": [],
    }
    identity = TransportOperationIdentity(
        stage="HOLDER_SAFETY",
        source_name="goplus",
        endpoint_owner="api.gopluslabs.io",
        governed_request_kind="safety_reference",
        method_or_endpoint="GET_TOKEN_SECURITY",
        within_request_ordinal=1,
        target_category="TOKEN_MINT",
        target_identity=MINT,
        response_bytes=128,
        normalized_rows=1,
        result="COMPLETED",
    )
    return {
        **payload,
        "transport_operation_identities": [identity.as_dict()],
        "transport_operations_used": 1,
        "underlying_operation_count": 1,
    }


def _db(tmp_path: Path):
    path = tmp_path / "dtw50.sqlite3"
    apply_migrations(path)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES (?,?,?,?,?)",
        (CAMPAIGN_ID, "RUNNING", "OPERATIONAL_PERSISTENT", "proof", "v2-9-8b"),
    )
    con.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?)",
        (RUN_ID, CAMPAIGN_ID, 1, "RUNNING", NOW, NOW),
    )
    budget.persist_ledger(
        con,
        run_id=RUN_ID,
        cycle_id=CYCLE_ID,
        ledger=budget.build_ledger(
            pump_operations=0, deadline_at=NOW_DT + timedelta(minutes=30)
        ),
        now=NOW,
    )
    con.commit()
    return con


def _scope():
    return build_campaign_source_request_scope(
        execution_id=EXECUTION_ID,
        campaign_id=CAMPAIGN_ID,
        run_id=RUN_ID,
        cycle_id=CYCLE_ID,
    )


def _collect_holder(con, *, rooted: bool):
    scope = _scope()
    kwargs = {
        "timeout_seconds": 1.0,
        "adapter_factories": {
            "goplus": lambda **_kwargs: build_goplus_adapter(
                enabled=True, fixture_transport=_fixture_transport
            ),
        },
        "include": frozenset({"safety"}),
        "preserve_partial_executions": True,
    }
    if (
        rooted
        and "request_key_prefix"
        in inspect.signature(factory._collect_preclose_context).parameters
    ):
        kwargs["request_key_prefix"] = (
            f"{scope.request_key_root}-holder-1-context"
        )
    bundle = factory._collect_preclose_context(
        con,
        {
            "run_id": RUN_ID,
            "step_key": "holder_eligibility_1",
            "token_mint": MINT,
            "pair_address": PAIR,
        },
        **kwargs,
    )
    persisted = persist_bundle_attempts(
        con,
        run_id=RUN_ID,
        cycle_id=CYCLE_ID,
        mint=MINT,
        executions=bundle["executions"],
        created_at=NOW,
        campaign_id=CAMPAIGN_ID,
        candidate_ordinal=1,
        require_exact_transport_identities=True,
    )
    con.commit()
    request_id = int(persisted.source_request_ids[0])
    row = con.execute(
        "SELECT request_key FROM printer_source_requests WHERE id=?",
        (request_id,),
    ).fetchone()
    assert row is not None
    return scope, persisted, str(row["request_key"])


def test_dtw50_rooted_holder_request_is_in_exact_campaign_scope(tmp_path):
    con = _db(tmp_path)
    try:
        scope, persisted, request_key = _collect_holder(con, rooted=True)
        diagnostics = {
            "holder_context": {
                "source_request_ids": list(persisted.source_request_ids),
                "source_request_coverage": [
                    dict(x) for x in persisted.source_request_coverage
                ],
                "governed_request_count": persisted.governed_request_count,
                "measured_transport_count": persisted.measured_transport_count,
                "accounting_blocker": persisted.accounting_blocker,
            },
            "holder_source_request_ids": list(persisted.source_request_ids),
            "holder_source_request_coverage": [
                dict(x) for x in persisted.source_request_coverage
            ],
        }
        recon = assemble_and_reconcile_campaign_source_requests(
            con,
            diagnostics=diagnostics,
            request_key_prefixes=[scope.request_key_root],
            request_key_root=scope.request_key_root,
            campaign_source_request_scope=scope,
        )
    finally:
        con.close()

    assert request_key.startswith(scope.request_key_root + "-")
    assert recon["status"] == "OK"
    assert recon["durable_campaign_request_ids"] == list(
        persisted.source_request_ids
    )
    assert recon["stage_reported_request_ids"] == list(
        persisted.source_request_ids
    )
    assert recon["transport_identity_completeness_status"] == "OK"
    assert recon["transport_identity_blockers"] == []


def test_dtw50_default_preclose_key_contract_is_unchanged(tmp_path):
    con = _db(tmp_path)
    try:
        _scope_value, _persisted, request_key = _collect_holder(
            con, rooted=False
        )
    finally:
        con.close()
    assert request_key == f"{RUN_ID}:holder_eligibility_1:context:safety"


def test_dtw50_backup_uses_explicit_rooted_holder_prefix(monkeypatch):
    captured = {}

    def fake_request(source_name, request_kind, *, request_key, payload):
        captured["request_key"] = request_key
        return object()

    monkeypatch.setattr(
        redundancy, "build_governed_source_request", fake_request
    )
    monkeypatch.setattr(
        redundancy, "count_recent_source_requests", lambda *_args, **_kwargs: 0
    )
    monkeypatch.setattr(
        redundancy,
        "execute_source_request_with_governor",
        lambda _con, _request, _adapter, recent_request_count: object(),
    )

    root = _scope().request_key_root
    prefix = f"{root}-holder-1-context"
    kwargs = dict(
        run_id=RUN_ID,
        step_key="holder_eligibility_1",
        token_mint=MINT,
        pair_address=PAIR,
        backup_adapter_factory=lambda **_kwargs: object(),
        timeout_seconds=1.0,
    )
    if (
        "request_key_prefix"
        in inspect.signature(
            redundancy.execute_solana_rpc_holder_backup
        ).parameters
    ):
        kwargs["request_key_prefix"] = prefix

    redundancy.execute_solana_rpc_holder_backup(
        object(),
        **kwargs,
    )
    assert captured["request_key"] == f"{prefix}:holder_backup"

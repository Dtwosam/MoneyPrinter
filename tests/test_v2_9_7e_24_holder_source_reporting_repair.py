from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    _holder_execution_fact,
)
from printer_v1.operator_cli.bounded_readiness_report import (
    build_bounded_readiness_report,
    canonical_report_bytes,
)
from printer_v1.operator_cli.durable_external_operation_log import (
    DurablePumpRpcTransport,
)
import printer_v1.operator_cli.holder_reliability_budget_control as budget
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.governed_execution import execute_source_request_with_governor
import printer_v1.sources.helius_holder as helius


NOW = datetime(2026, 7, 22, 20, 0, tzinfo=timezone.utc)
MINT = "mint-exact"


def _payload(**overrides):
    value = {
        "token_mint": MINT,
        "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
        "captured_at": NOW.isoformat(),
        "rpc_method": "getTokenLargestAccounts+getTokenSupply",
        "commitment": "finalized",
        "context_slot": 123,
        "underlying_operation_count": 2,
    }
    value.update(overrides)
    return value


def _db(tmp_path: Path) -> tuple[Path, sqlite3.Connection]:
    path = tmp_path / "e24-proof.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES ('campaign','RUNNING','OPERATIONAL_PERSISTENT','proof','e24')"
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,created_at,updated_at) "
        "VALUES ('run','campaign',1,'RUNNING',?,?)",
        (NOW.isoformat(), NOW.isoformat()),
    )
    ledger = budget.build_ledger(
        pump_operations=12, deadline_at=NOW + timedelta(minutes=6)
    )
    budget.persist_ledger(
        connection, run_id="run", cycle_id="cycle", ledger=ledger,
        now=NOW.isoformat(),
    )
    connection.commit()
    return path, connection


def test_helius_exact_target_success_mismatch_stale_malformed_and_failure() -> None:
    success = helius.normalize_helius_holder_response(
        _payload(), request_kind="holder_concentration_reference"
    )
    assert success.source_name == "helius_free"
    assert success.normalized_payload["redacted_host"] == "mainnet.helius-rpc.com"
    assert success.normalized_payload["token_mint"] == MINT
    assert success.normalized_payload["underlying_operation_count"] == 2

    execution = SimpleNamespace(
        response_record=SimpleNamespace(id=1), failure_record=None,
        normalized_result=success,
    )
    assert _holder_execution_fact(
        execution, token_mint=MINT, source_name="helius_free"
    )["eligible"] is True
    mismatch = _holder_execution_fact(
        execution, token_mint="different", source_name="helius_free"
    )
    assert mismatch["reason"] == "HOLDER_EVIDENCE_TARGET_MISMATCH"

    stale = helius.normalize_helius_holder_response(
        _payload(fixture_stale=True), request_kind="holder_concentration_reference"
    )
    stale_execution = SimpleNamespace(
        response_record=SimpleNamespace(id=2), failure_record=None,
        normalized_result=stale,
    )
    assert _holder_execution_fact(
        stale_execution, token_mint=MINT, source_name="helius_free"
    )["reason"] == "HOLDER_EVIDENCE_STALE"

    malformed = helius.normalize_helius_holder_response(
        {"token_mint": MINT}, request_kind="holder_concentration_reference"
    )
    assert malformed.source_status.value == "FAILED"
    failed = helius.normalize_helius_holder_response(
        {"fixture_status": "failure", "failure_type": "solana_rpc_rate_limited",
         "failure_message": "429", "underlying_operation_count": 1},
        request_kind="holder_concentration_reference",
    )
    assert failed.failure_type == "helius_rate_limited"


def test_conflicting_clean_facts_fail_closed() -> None:
    fact_a = {"eligible": True, "source_name": "solana_rpc",
              "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY"}
    fact_b = {"eligible": True, "source_name": "helius_free",
              "holder_concentration_label": "HOLDER_CONCENTRATION_EXTREME"}
    conflict = helius.resolve_holder_concentration_facts((fact_a, fact_b))
    assert conflict == {
        "eligible": False, "reason": "HOLDER_EVIDENCE_CONFLICT",
        "source_name": None,
    }


def test_fixed_endpoint_zero_retry_governor_and_operation_accounting(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[str] = []

    def fake_fetch(token_mint, *, rpc_url, timeout_seconds):
        calls.append(rpc_url)
        assert token_mint == MINT and timeout_seconds == 3
        return _payload()

    monkeypatch.setattr(helius, "_fetch_holder_data", fake_fetch)
    transport = helius.build_helius_holder_transport(
        MINT, api_key="fixture-secret", timeout_seconds=3
    )
    adapter = helius.build_helius_holder_adapter(
        enabled=True, fixture_transport=transport
    )
    path, connection = _db(tmp_path)
    del path
    request = build_governed_source_request(
        "helius_free", "holder_concentration_reference",
        request_key="e24:once", payload={"token_mint": MINT},
    )
    execution = execute_source_request_with_governor(
        connection, request, adapter, recent_request_count=0
    )
    persist_result = budget.persist_bundle_attempts(
        connection, run_id="run", cycle_id="cycle", mint=MINT,
        executions={"holder_backup": execution}, created_at=NOW.isoformat(),
    )
    governed = persist_result.governed_request_count
    transports = persist_result.measured_transport_count
    assert governed == 1 and transports == 2
    assert adapter.call_count == 1 and len(calls) == 1
    assert calls[0].startswith("https://mainnet.helius-rpc.com/?api-key=")
    attempt = connection.execute(
        "SELECT source_name,endpoint_role,redacted_host,underlying_operation_count "
        "FROM printer_holder_evidence_attempts"
    ).fetchone()
    assert tuple(attempt) == ("helius_free", "BACKUP", "mainnet.helius-rpc.com", 2)
    assert "fixture-secret" not in str(dict(execution.normalized_result.normalized_payload))
    assert budget.build_ledger(
        pump_operations=12, deadline_at=NOW + timedelta(minutes=6)
    ).candidate_cap() == 3


def test_helius_failure_message_cannot_persist_api_key(monkeypatch) -> None:
    monkeypatch.setattr(
        helius, "_fetch_holder_data",
        lambda *_args, **_kwargs: {
            "fixture_status": "failure",
            "failure_type": "solana_rpc_transport_failure",
            "failure_message": "request fixture-secret failed",
        },
    )
    transport = helius.build_helius_holder_transport(MINT, api_key="fixture-secret")
    result = transport(None)
    assert "fixture-secret" not in str(dict(result))
    assert "[REDACTED]" in result["failure_message"]


class _PumpSuccess:
    calls = 0

    def json_rpc(self, method, params, *, timeout_seconds, byte_ceiling):
        self.calls += 1
        return {"method": method, "count": len(params)}


class _PumpFailure:
    calls = 0

    def json_rpc(self, method, params, *, timeout_seconds, byte_ceiling):
        self.calls += 1
        raise TimeoutError("offline fixture timeout")


def test_durable_pump_timing_report_replay_cleanup_and_integrity(tmp_path: Path) -> None:
    path, connection = _db(tmp_path)
    connection.close()
    success = _PumpSuccess()
    wrapped = DurablePumpRpcTransport(
        success, db_path=path, run_id="run", cycle_id="cycle"
    )
    assert wrapped.json_rpc(
        "getSignaturesForAddress", ["redacted-target", {"commitment": "finalized"}],
        timeout_seconds=1, byte_ceiling=1024,
    )["count"] == 2
    failure = _PumpFailure()
    failing = DurablePumpRpcTransport(
        failure, db_path=path, run_id="run", cycle_id="cycle"
    )
    with pytest.raises(TimeoutError):
        failing.json_rpc(
            "getTransaction", ["redacted-signature"],
            timeout_seconds=1, byte_ceiling=1024,
        )
    first = build_bounded_readiness_report(path, run_id="run", cycle_id="cycle")
    second = build_bounded_readiness_report(path, run_id="run", cycle_id="cycle")
    assert canonical_report_bytes(first) == canonical_report_bytes(second)
    assert [row["operation_state"] for row in first["external_pump_operations"]] == [
        "COMPLETE", "FAILED"
    ]
    assert all(row["finished_at"] for row in first["external_pump_operations"])
    assert first["cleanup"] == {
        "active_tracking_queue": 0, "active_scheduler_jobs": 0
    }
    assert first["integrity"] == "ok"
    assert first["foreign_key_violations"] == 0
    assert set(first["forbidden_capability_counts"].values()) == {0}
    assert first["source_requests_made_by_replay"] == 0
    assert success.calls == 1 and failure.calls == 1

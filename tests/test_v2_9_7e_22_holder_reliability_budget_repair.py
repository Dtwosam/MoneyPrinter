from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import sqlite3

import pytest

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    _holder_execution_fact,
)
import printer_v1.operator_cli.holder_reliability_budget_control as control
from printer_v1.sources.contracts import NormalizedSourceResult, SourceRequest
from printer_v1.sources.recording import (
    record_source_failure,
    record_source_request,
    record_source_response,
)
from printer_v1.sources.solana_rpc_holder import normalize_solana_rpc_holder_response


NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def _db(tmp_path) -> sqlite3.Connection:
    path = tmp_path / "e22.sqlite3"
    apply_migrations(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES ('campaign','RUNNING','OPERATIONAL_PERSISTENT','proof-db','e22')"
    )
    conn.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,created_at,updated_at) "
        "VALUES ('run','campaign',1,'RUNNING',?,?)",
        (NOW.isoformat(), NOW.isoformat()),
    )
    ledger = control.build_ledger(pump_operations=12, deadline_at=NOW + timedelta(minutes=6))
    control.persist_ledger(
        conn, run_id="run", cycle_id="cycle", ledger=ledger, now=NOW.isoformat()
    )
    conn.commit()
    return conn


def test_budget_derives_four_candidates_and_preserves_two_snapshots() -> None:
    ledger = control.build_ledger(
        pump_operations=12, deadline_at=NOW + timedelta(minutes=6)
    )
    assert ledger.candidate_cap() == 4
    before_fourth = control.CampaignOperationLedger(
        **{**ledger.__dict__, "underlying_transport_operations": 27}
    )
    before_fourth.admit_candidate(now=NOW)
    after_fourth = control.CampaignOperationLedger(
        **{**ledger.__dict__, "underlying_transport_operations": 32}
    )
    assert after_fourth.charged_operations + after_fourth.reserved_snapshot_operations == 43
    with pytest.raises(control.HolderBudgetError, match="RESERVATION"):
        after_fourth.admit_candidate(now=NOW)


def test_fake_clock_pacing_is_fixed_sequential_and_has_no_retry_shape() -> None:
    assert control.deterministic_spacing_seconds("goplus") == 3
    assert control.deterministic_spacing_seconds("solana_rpc") == 2
    first = control.next_paced_time(source_name="goplus", previous_at=None, now=NOW)
    second = control.next_paced_time(source_name="goplus", previous_at=first, now=NOW)
    third = control.next_paced_time(source_name="solana_rpc", previous_at=second, now=second)
    assert (second - first).total_seconds() == 3
    assert (third - second).total_seconds() == 2
    assert first < second < third
    clock = [NOW]
    sleeps: list[float] = []
    def advance(seconds: float) -> None:
        sleeps.append(seconds)
        clock[0] += timedelta(seconds=seconds)
    pacer = control.SequentialRequestPacer(now_fn=lambda: clock[0], sleep_fn=advance)
    pacer.pace("goplus")
    pacer.pace("goplus")
    pacer.pace("solana_rpc")
    pacer.pace("solana_rpc")
    assert sleeps == [3.0, 2.0]
    assert [source for source, _ in pacer.trace] == [
        "goplus", "goplus", "solana_rpc", "solana_rpc"
    ]
    assert control.MATURATION_THRESHOLD_SECONDS is None
    assert control.MATURATION_THRESHOLD_STATE == "UNPROVEN_DISABLED"


def test_rpc_rate_limit_preserves_method_operation_and_retry_after() -> None:
    result = normalize_solana_rpc_holder_response(
        {
            "fixture_status": "failure",
            "failure_type": "solana_rpc_rate_limited",
            "failure_message": "429",
            "status_code": 429,
            "retry_after": "60",
            "rpc_method": "getTokenLargestAccounts",
            "underlying_operation_count": 1,
            "commitment": "finalized",
        },
        request_kind="holder_concentration_reference",
    )
    assert result.failure_type == "solana_rpc_rate_limited"
    assert result.status_code == 429
    assert result.retry_after_at is not None
    assert result.normalized_payload["rpc_method"] == "getTokenLargestAccounts"
    assert result.normalized_payload["underlying_operation_count"] == 1


def test_maturation_wait_deadline_cancel_and_replay_are_zero_call(tmp_path, monkeypatch) -> None:
    conn = _db(tmp_path)
    monkeypatch.setattr(control, "MATURATION_THRESHOLD_SECONDS", 30)
    monkeypatch.setattr(control, "MATURATION_THRESHOLD_STATE", "EVIDENCE_BACKED")
    waiting = control.schedule_maturation(
        conn, run_id="run", cycle_id="cycle", mint="MintA",
        observed_at=NOW.isoformat(), now=(NOW + timedelta(seconds=10)).isoformat(),
        deadline_at=(NOW + timedelta(minutes=1)).isoformat(),
    )
    replay = control.schedule_maturation(
        conn, run_id="run", cycle_id="cycle", mint="MintA",
        observed_at=NOW.isoformat(), now=(NOW + timedelta(seconds=10)).isoformat(),
        deadline_at=(NOW + timedelta(minutes=1)).isoformat(),
    )
    assert waiting == replay
    assert waiting["work_state"] == "WAITING"
    assert waiting["source_calls_while_waiting"] == 0
    deadline = control.schedule_maturation(
        conn, run_id="run", cycle_id="cycle", mint="MintB",
        observed_at=NOW.isoformat(), now=NOW.isoformat(),
        deadline_at=(NOW + timedelta(seconds=20)).isoformat(),
    )
    cancelled = control.schedule_maturation(
        conn, run_id="run", cycle_id="cycle", mint="MintC",
        observed_at=NOW.isoformat(), now=NOW.isoformat(),
        deadline_at=(NOW + timedelta(minutes=1)).isoformat(), cancelled=True,
    )
    assert deadline["work_state"] == "DEADLINE_REFUSED"
    assert cancelled["work_state"] == "CANCELLED"
    assert conn.execute("SELECT COUNT(*) FROM printer_holder_maturation_work").fetchone()[0] == 3


def _clean_evidence(conn: sqlite3.Connection, *, received_at: datetime = NOW) -> int:
    request = record_source_request(
        conn, SourceRequest("goplus", "safety_reference", request_key="holder")
    )
    result = NormalizedSourceResult(
        source_name="goplus", request_kind="safety_reference",
        source_status=SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.CLEAN_DATA,
        normalized_payload={"token_mint": "minta"}, received_at=received_at.isoformat(),
    )
    response = record_source_response(conn, request, result)
    return control.record_attempt(
        conn, run_id="run", cycle_id="cycle", mint_identity="minta",
        source_name="goplus", endpoint_role="PRIMARY",
        redacted_host="api.gopluslabs.io", source_request_id=request.id,
        source_response_id=response.id, source_failure_id=None,
        lineage_response_id=response.id, reused_evidence_id=None,
        captured_at=received_at.isoformat(), received_at=received_at.isoformat(),
        source_status="COMPLETE", data_quality_label="CLEAN_DATA", exact_target=1,
        holder_concentration_label="HOLDER_CONCENTRATION_HEALTHY",
        rpc_method="HTTP_GET", commitment=None, context_slot=None,
        underlying_operation_count=1, failure_subtype=None, retry_after_at=None,
        created_at=received_at.isoformat(),
    )


def test_exact_reuse_accepts_only_exact_fresh_source_and_versions(tmp_path) -> None:
    conn = _db(tmp_path)
    original = _clean_evidence(conn)
    row = control.reusable_evidence(
        conn, mint="MINTA", purpose=control.HOLDER_REQUEST_PURPOSE,
        source_name="goplus", endpoint_role="PRIMARY", evaluated_at=NOW.isoformat(),
    )
    assert row is not None and row["evidence_id"] == original
    assert control.reusable_evidence(
        conn, mint="other", purpose=control.HOLDER_REQUEST_PURPOSE,
        source_name="goplus", endpoint_role="PRIMARY", evaluated_at=NOW.isoformat(),
    ) is None
    assert control.reusable_evidence(
        conn, mint="minta", purpose=control.HOLDER_REQUEST_PURPOSE,
        source_name="solana_rpc", endpoint_role="PRIMARY", evaluated_at=NOW.isoformat(),
    ) is None
    assert control.reusable_evidence(
        conn, mint="minta", purpose=control.HOLDER_REQUEST_PURPOSE,
        source_name="goplus", endpoint_role="PRIMARY", evaluated_at=NOW.isoformat(),
        parser_version="different",
    ) is None
    assert control.reusable_evidence(
        conn, mint="minta", purpose=control.HOLDER_REQUEST_PURPOSE,
        source_name="goplus", endpoint_role="PRIMARY", evaluated_at=NOW.isoformat(),
        policy_version="different",
    ) is None
    assert control.reusable_evidence(
        conn, mint="minta", purpose=control.HOLDER_REQUEST_PURPOSE,
        source_name="goplus", endpoint_role="PRIMARY",
        evaluated_at=(NOW + timedelta(seconds=301)).isoformat(),
    ) is None
    reused = control.reuse_holder_fact(
        conn, run_id="run", cycle_id="cycle", mint="minta",
        evaluated_at=NOW.isoformat(),
    )
    assert reused and reused["reused_evidence_id"] == original
    assert conn.execute(
        "SELECT underlying_operation_count FROM printer_holder_evidence_attempts "
        "WHERE evidence_id=?", (reused["evidence_id"],)
    ).fetchone()[0] == 0


def test_failure_linkage_provenance_retry_after_and_precedence(tmp_path) -> None:
    conn = _db(tmp_path)
    request = record_source_request(
        conn, SourceRequest("solana_rpc", "holder_concentration_reference")
    )
    retry_at = (NOW + timedelta(seconds=60)).isoformat()
    failure = record_source_failure(
        conn, request, failure_type="solana_rpc_rate_limited",
        retry_after_at=retry_at,
    )
    assert failure.source_request_id == request.id
    control.record_attempt(
        conn, run_id="run", cycle_id="cycle", mint_identity="minta",
        source_name="solana_rpc", endpoint_role="PRIMARY",
        redacted_host="api.mainnet-beta.solana.com", source_request_id=request.id,
        source_response_id=None, source_failure_id=failure.id,
        lineage_response_id=None, reused_evidence_id=None,
        captured_at=None, received_at=NOW.isoformat(), source_status="FAILED",
        data_quality_label="MISSING_CRITICAL_DATA", exact_target=0,
        holder_concentration_label=None, rpc_method="getTokenLargestAccounts",
        commitment="finalized", context_slot=None, underlying_operation_count=1,
        failure_subtype="solana_rpc_rate_limited", retry_after_at=retry_at,
        created_at=NOW.isoformat(),
    )
    row = conn.execute("SELECT * FROM printer_holder_evidence_attempts").fetchone()
    assert row["source_failure_id"] == failure.id
    assert row["rpc_method"] == "getTokenLargestAccounts"
    assert row["commitment"] == "finalized"
    assert row["underlying_operation_count"] == 1
    assert row["failure_subtype"] == "solana_rpc_rate_limited"
    assert row["retry_after_at"] == retry_at
    failed_execution = SimpleNamespace(
        response_record=None, failure_record=SimpleNamespace(id=failure.id),
        normalized_result=SimpleNamespace(
            source_status=SimpleNamespace(value="FAILED"),
            data_quality_label=SimpleNamespace(value="MISSING_CRITICAL_DATA"),
            normalized_payload={}, failure_type="solana_rpc_rate_limited",
        ),
    )
    assert _holder_execution_fact(
        failed_execution, token_mint="minta", source_name="solana_rpc"
    )["reason"] == "HOLDER_EVIDENCE_FAILED:solana_rpc_rate_limited"
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

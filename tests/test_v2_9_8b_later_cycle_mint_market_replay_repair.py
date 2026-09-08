"""Focused regression for V2-9.8B later-cycle cooperative mint-market replay.

Disposable SQLite only. No live providers, Scheduler work, Printer execution,
authorization, retrieval, decisions, positions, trades, audits, or PnL.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.discovery.eligible_token_supply import (
    ACQUISITION_QUANTUM_YIELDED,
    AcquisitionQuantumKind,
    BUDGET_EXHAUSTION,
    acquisition_quantum_bound,
    load_completed_cooperative_mint_market_batch_mints,
    run_persistent_eligible_token_supply,
)
from printer_v1.discovery.permanent_discovery_availability import (
    StageBudget,
    build_campaign_source_request_scope,
)
from printer_v1.sources.dexscreener import fixture_success_transport
from printer_v1.sources.pumpswap_graduated_registry import (
    PERSISTED_GRADUATED_CHANNEL,
    record_graduated_candidate,
)

NOW = "2026-09-02T09:00:00+00:00"
EXECUTION_ID = "replay-regression-execution:c0002"
CAMPAIGN_ID = "replay-regression-campaign"
RUN_ID = "replay-regression-run"
CYCLE_ID = "replay-regression-cycle-2"
MINT = "6wtZueu89AGwQkGUki3HcerjCDFxLA9PyVUBWQbMpump"
OTHER_MINT = "71pkkHscUWYPjLb6ZgU7X7iLh6Pkk86EbbgTWrPcAN3G"
SIGNATURE = "ijqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usESaaaaaaa"
POOL = "6TJuebvz9hqJaybCWpKm7ygmFqcxHxJ3Azi5BJhmHak"


def _scope():
    return build_campaign_source_request_scope(
        execution_id=EXECUTION_ID,
        campaign_id=CAMPAIGN_ID,
        run_id=RUN_ID,
        cycle_id=CYCLE_ID,
    )


def _db(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "replay.sqlite3"
    apply_migrations(db_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def _identity(target: str, *, category: str = "due_mints") -> dict[str, object]:
    return {
        "stage": "MINT_MARKET_BATCH",
        "source_name": "dexscreener_pair",
        "endpoint_owner": "dexscreener",
        "governed_request_kind": "candidate_market_batch",
        "method_or_endpoint": "GET /tokens/v1/solana/{mints}",
        "within_request_ordinal": 1,
        "target_category": category,
        "target_identity": target,
        "response_bytes": 100,
        "normalized_rows": 1,
        "result": "COMPLETE",
        "reserved_from": None,
    }


def _record_request(
    connection: sqlite3.Connection,
    *,
    request_key: str,
    response_status: str | None,
    identity: dict[str, object] | None,
) -> int:
    request_id = int(
        connection.execute(
            """
            INSERT INTO printer_source_requests(
                source_name,request_kind,requested_at,request_key,
                tracking_priority,source_status,data_quality_label
            ) VALUES ('dexscreener','candidate_market_batch',?,?,0,'COMPLETE','CLEAN_DATA')
            """,
            (NOW, request_key),
        ).lastrowid
    )
    if response_status is None:
        connection.execute(
            """
            INSERT INTO printer_source_failures(
                source_request_id,source_name,request_kind,failed_at,failure_type,
                failure_message,source_status,data_quality_label
            ) VALUES (?,'dexscreener','candidate_market_batch',?,
                      'dexscreener_rate_limited','fixture rate limit','STALE','STALE_DATA')
            """,
            (request_id, NOW),
        )
    else:
        payload = {
            "transport_operation_identities": [] if identity is None else [identity],
            "pairs": [],
        }
        connection.execute(
            """
            INSERT INTO printer_source_responses(
                source_request_id,source_name,received_at,status_code,source_status,
                data_quality_label,response_hash,normalized_payload_json
            ) VALUES (?,'dexscreener',?,200,?,'CLEAN_DATA','fixture-hash',?)
            """,
            (request_id, NOW, response_status, json.dumps(payload, sort_keys=True)),
        )
    connection.commit()
    return request_id


def _load(connection: sqlite3.Connection) -> frozenset[str]:
    return load_completed_cooperative_mint_market_batch_mints(
        connection,
        campaign_source_request_scope=_scope(),
        execution_id=EXECUTION_ID,
        campaign_id=CAMPAIGN_ID,
        run_id=RUN_ID,
        cycle_id=CYCLE_ID,
    )


def test_complete_current_cycle_round_batch_is_rehydrated(tmp_path: Path) -> None:
    connection = _db(tmp_path)
    try:
        scope = _scope()
        _record_request(
            connection,
            request_key=f"{scope.request_key_root}-mint-batch-r1",
            response_status="COMPLETE",
            identity=_identity(MINT),
        )
        assert _load(connection) == frozenset({MINT})
    finally:
        connection.close()


def test_failed_rate_limited_batch_remains_retryable(tmp_path: Path) -> None:
    connection = _db(tmp_path)
    try:
        scope = _scope()
        _record_request(
            connection,
            request_key=f"{scope.request_key_root}-mint-batch-r1",
            response_status=None,
            identity=None,
        )
        assert _load(connection) == frozenset()
    finally:
        connection.close()


def test_partial_or_malformed_response_does_not_suppress(tmp_path: Path) -> None:
    connection = _db(tmp_path)
    try:
        scope = _scope()
        _record_request(
            connection,
            request_key=f"{scope.request_key_root}-mint-batch-r1",
            response_status="PARTIAL",
            identity=_identity(MINT),
        )
        _record_request(
            connection,
            request_key=f"{scope.request_key_root}-mint-batch-r2",
            response_status="COMPLETE",
            identity=None,
        )
        _record_request(
            connection,
            request_key=f"{scope.request_key_root}-mint-batch-r3",
            response_status="COMPLETE",
            identity=_identity(MINT, category="not_due_mints"),
        )
        assert _load(connection) == frozenset()
    finally:
        connection.close()


def test_foreign_scope_cannot_suppress_current_cycle(tmp_path: Path) -> None:
    connection = _db(tmp_path)
    try:
        foreign = build_campaign_source_request_scope(
            execution_id="foreign-execution:c0002",
            campaign_id="foreign-campaign",
            run_id="foreign-run",
            cycle_id="foreign-cycle",
        )
        _record_request(
            connection,
            request_key=f"{foreign.request_key_root}-mint-batch-r1",
            response_status="COMPLETE",
            identity=_identity(MINT),
        )
        # A lawful current-scope terminal artifact exists so resume validation is
        # allowed to inspect the current root; it must not import foreign evidence.
        current = _scope()
        _record_request(
            connection,
            request_key=f"{current.request_key_root}-mint-batch-r1",
            response_status="COMPLETE",
            identity=_identity(OTHER_MINT, category="not_due_mints"),
        )
        assert _load(connection) == frozenset()
    finally:
        connection.close()


def test_non_round_market_transport_does_not_suppress_round_due_mints(tmp_path: Path) -> None:
    connection = _db(tmp_path)
    try:
        scope = _scope()
        _record_request(
            connection,
            request_key=f"{scope.request_key_root}-protocol-resume-mb1",
            response_status="COMPLETE",
            identity=_identity(MINT),
        )
        assert _load(connection) == frozenset()
    finally:
        connection.close()


def test_market_discovery_resume_uses_rehydrated_mints_before_due_batch(
    tmp_path: Path, monkeypatch,
) -> None:
    db_path = tmp_path / "integration.sqlite3"
    apply_migrations(db_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    record_graduated_candidate(
        connection,
        mint=MINT,
        migration_signature=SIGNATURE,
        pumpswap_pool=POOL,
        graduation_block_time=1_784_000_000,
        graduation_slot=1,
        now=NOW,
        discovery_channel=PERSISTED_GRADUATED_CHANNEL,
    )
    connection.commit()
    connection.close()

    called: list[dict[str, object]] = []

    def fake_rehydrate(_connection, **kwargs):
        called.append(dict(kwargs))
        return frozenset({MINT})

    monkeypatch.setattr(
        "printer_v1.discovery.eligible_token_supply."
        "load_completed_cooperative_mint_market_batch_mints",
        fake_rehydrate,
    )

    def unexpected_market_factory(_mints):
        raise AssertionError("completed cooperative mint transport was replayed")

    result = run_persistent_eligible_token_supply(
        db_path,
        cycle_seed="replay-integration-seed",
        migration_transport=lambda _context: {"result": []},
        dexscreener_batch_transport_factory=unexpected_market_factory,
        now=NOW,
        discovery_request_key_prefix=_scope().request_key_root,
        front_door_request_key_prefix=_scope().request_key_root,
        execution_id=EXECUTION_ID,
        # Deliberately omit campaign/run/cycle only from this composition probe so
        # freeze-ready reconciliation stays out of scope; helper unit tests above
        # independently prove exact typed-scope durable evidence validation.
        campaign_id=None,
        run_id=None,
        cycle_id=None,
        campaign_source_request_scope=_scope(),
        permanent_availability=True,
        cooperative_resume=True,
        cooperative_quantum=True,
        cooperative_phase="MARKET_DISCOVERY",
        cooperative_stage_budget=StageBudget.permanent_discovery_default(),
        enable_geckoterminal_reconciliation=False,
        persist_terminal_certificate=False,
    )

    assert len(called) == 1
    assert result.diagnostics["cooperative_completed_market_mint_count"] == 1
    assert result.diagnostics["cooperative_completed_market_mints"] == [MINT]
    check = sqlite3.connect(db_path)
    try:
        assert int(check.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]) == 0
    finally:
        check.close()

def test_market_feeder_exhaustion_is_honest_budget_terminal_with_downstream_capacity(
    tmp_path: Path,
) -> None:
    """Unused downstream reservations cannot make exhausted market work executable."""
    db_path = tmp_path / "market-feeder-exhaustion.sqlite3"
    apply_migrations(db_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    record_graduated_candidate(
        connection,
        mint=MINT,
        migration_signature=SIGNATURE,
        pumpswap_pool=POOL,
        graduation_block_time=1_784_000_000,
        graduation_slot=1,
        now=NOW,
        discovery_channel=PERSISTED_GRADUATED_CHANNEL,
    )
    # Cooperative resume must own at least one lawful completed request in the
    # exact typed Cycle-2 scope.  Use another mint so the candidate under test
    # remains unexplored when market-batching capacity is already exhausted.
    scope = _scope()
    _record_request(
        connection,
        request_key=f"{scope.request_key_root}-mint-batch-r1",
        response_status="COMPLETE",
        identity=_identity(OTHER_MINT),
    )
    connection.commit()
    connection.close()

    stage_budget = StageBudget.permanent_discovery_default()
    stage_budget.consume("market_batching", 2)
    assert stage_budget.available("market_batching") == 0
    # These later reservations remain unused but cannot feed market batching.
    assert stage_budget.available("reconciliation") > 0
    assert stage_budget.available("protocol_confirmation") > 0

    def unexpected_market_factory(_mints):
        raise AssertionError("exhausted market feeder attempted another transport")

    result = run_persistent_eligible_token_supply(
        db_path,
        cycle_seed="market-feeder-exhaustion-seed",
        migration_transport=lambda _context: {"result": []},
        dexscreener_batch_transport_factory=unexpected_market_factory,
        now=NOW,
        discovery_request_key_prefix=_scope().request_key_root,
        front_door_request_key_prefix=_scope().request_key_root,
        execution_id=EXECUTION_ID,
        campaign_id=None,
        run_id=None,
        cycle_id=None,
        campaign_source_request_scope=_scope(),
        permanent_availability=True,
        cooperative_resume=True,
        cooperative_quantum=True,
        cooperative_phase="MARKET_DISCOVERY",
        cooperative_stage_budget=stage_budget,
        enable_geckoterminal_reconciliation=False,
        persist_terminal_certificate=False,
    )

    assert result.ready is False
    assert result.shortage_classification == BUDGET_EXHAUSTION
    assert result.shortage_classification != "DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE"
    assert result.diagnostics["last_stop_reason"] == "DISCOVERY_OPERATION_BUDGET_EXHAUSTED"
    assert result.diagnostics["unexplored_unique_remaining"] > 0
    assert result.diagnostics["discovery_operations_remaining"] > 0
    assert (
        result.diagnostics["stage_capacity"]["remaining_by_stage"]["reconciliation"]
        > 0
    )
    assert (
        result.diagnostics["stage_capacity"]["remaining_by_stage"][
            "protocol_confirmation"
        ]
        > 0
    )

def test_cooperative_market_batch_defers_reconciliation_to_fast_safe_quantum(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "market-split.sqlite3"
    apply_migrations(db_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    record_graduated_candidate(
        connection,
        mint=MINT,
        migration_signature=SIGNATURE,
        pumpswap_pool=POOL,
        graduation_block_time=1_784_000_000,
        graduation_slot=1,
        now=NOW,
        discovery_channel=PERSISTED_GRADUATED_CHANNEL,
    )
    scope = _scope()
    _record_request(
        connection,
        request_key=f"{scope.request_key_root}-mint-batch-r1",
        response_status="COMPLETE",
        identity=_identity(OTHER_MINT),
    )
    connection.commit()
    connection.close()

    dex_calls = 0
    gecko_calls = 0

    def dex_factory(_mints):
        nonlocal dex_calls
        dex_calls += 1
        return fixture_success_transport({"pairs": []})

    def forbidden_gecko(_mint):
        nonlocal gecko_calls
        gecko_calls += 1
        raise AssertionError(
            "Gecko reconciliation must be a later cooperative claim"
        )

    result = run_persistent_eligible_token_supply(
        db_path,
        cycle_seed="market-split-seed",
        migration_transport=lambda _context: {"result": []},
        dexscreener_batch_transport_factory=dex_factory,
        geckoterminal_reconciliation_transport_factory=forbidden_gecko,
        now=NOW,
        discovery_request_key_prefix=scope.request_key_root,
        front_door_request_key_prefix=scope.request_key_root,
        execution_id=EXECUTION_ID,
        campaign_id=CAMPAIGN_ID,
        run_id=RUN_ID,
        cycle_id=CYCLE_ID,
        campaign_source_request_scope=scope,
        permanent_availability=True,
        cooperative_resume=True,
        cooperative_quantum=True,
        cooperative_phase="MARKET_DISCOVERY",
        cooperative_stage_budget=StageBudget.permanent_discovery_default(),
        enable_geckoterminal_reconciliation=True,
        persist_terminal_certificate=False,
    )

    assert dex_calls == 1
    assert gecko_calls == 0
    assert result.terminal_cause == ACQUISITION_QUANTUM_YIELDED
    assert result.diagnostics["next_cooperative_phase"] == (
        "AUXILIARY_LIQUIDITY_BACKUP"
    )
    stage = result.diagnostics["stage_capacity"]
    assert stage["used_by_stage"]["market_batching"] == 1
    assert stage["used_by_stage"]["reconciliation"] == 0
    assert len(result.diagnostics["work_queues"]["RECONCILIATION_DUE"]) == 1
    assert (
        acquisition_quantum_bound(
            AcquisitionQuantumKind.MARKET_DISCOVERY
        ).worst_case_seconds
        == 5.0
    )
    check = sqlite3.connect(db_path)
    try:
        row = check.execute(
            "SELECT current_state,current_reason FROM printer_exact_market_states "
            "WHERE mint_identity=? AND pool_address=?",
            (MINT, POOL),
        ).fetchone()
        assert tuple(row) == ("CONTRACT_BLOCKED", "LIQUIDITY_UNKNOWN")
    finally:
        check.close()

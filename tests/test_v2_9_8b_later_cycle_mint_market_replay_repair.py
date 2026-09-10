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
    DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE,
    _lawful_pending_acquisition_work,
    acquisition_quantum_bound,
    load_completed_cooperative_mint_market_batch_mints,
    run_persistent_eligible_token_supply,
)
from printer_v1.discovery.permanent_discovery_availability import (
    CURRENT_POOL_CONFIRMED,
    MEMORY_OBSERVATION_ELIGIBLE,
    ExactMarketObservation,
    StageBudget,
    build_campaign_source_request_scope,
    load_protocol_resume_market_due,
    record_exact_market_transition,
)
from printer_v1.sources.dexscreener import fixture_success_transport
from printer_v1.sources.generic_present_pool_account_batch import TOKEN_PROGRAM_ID
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
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
GENERIC_VENUE = "raydium"
GENERIC_POOL_PROGRAM = "GenericAmmProgramResume1111111111111111111111111"


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
    assert result.terminal == ACQUISITION_QUANTUM_YIELDED
    assert result.diagnostics["next_cooperative_phase"] == (
        "AUXILIARY_LIQUIDITY_BACKUP"
    )
    stage = result.diagnostics["stage_capacity"]
    assert stage["used_by_stage"]["market_batching"] == 1
    assert stage["used_by_stage"]["reconciliation"] == 0
    assert len(result.diagnostics["pending_work_by_queue"]["RECONCILIATION_DUE"]) == 1
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


def _record_generic_protocol_confirmed(
    connection: sqlite3.Connection,
    *,
    mint: str,
    pool: str,
    protocol_request_id: int,
    pool_program: str = GENERIC_POOL_PROGRAM,
) -> None:
    record_exact_market_transition(
        connection,
        ExactMarketObservation(
            network="solana-mainnet",
            mint=mint,
            pool=pool,
            token_program=TOKEN_PROGRAM_ID,
            pool_program=pool_program,
            base_mint=mint,
            quote_mint=USDC,
            venue=GENERIC_VENUE,
            state=CURRENT_POOL_CONFIRMED,
            reason="GENERIC_POOL_CONFIRMED",
            observed_at=NOW,
            next_lawful_action_at=None,
            source_provenance={
                "stage": "protocol_confirmation",
                "request_id": int(protocol_request_id),
                "verification_kind": "GENERIC",
            },
            contract_version="GENERIC_PROTOCOL_RESUME_TEST_V1",
        ),
        now=NOW,
    )


def _generic_dex_pair(*, mint: str, pool: str) -> dict[str, object]:
    return {
        "chainId": "solana",
        "pairAddress": pool,
        "dexId": GENERIC_VENUE,
        "baseToken": {"address": mint, "symbol": "GEN"},
        "quoteToken": {"address": USDC, "symbol": "USDC"},
        "liquidity": {"usd": 7_500.0},
        "priceUsd": "0.001",
    }


def test_protocol_resume_uses_canonical_default_dex_transport_and_preserves_generic_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "generic-protocol-resume-default.sqlite3"
    apply_migrations(db_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    _record_generic_protocol_confirmed(
        connection,
        mint=MINT,
        pool=POOL,
        protocol_request_id=701,
    )
    connection.commit()
    due_before = load_protocol_resume_market_due(connection)
    assert due_before == [
        {
            "mint": MINT,
            "pool": POOL,
            "venue": GENERIC_VENUE,
            "token_program": TOKEN_PROGRAM_ID,
            "pool_program": GENERIC_POOL_PROGRAM,
            "base_mint": MINT,
            "quote_mint": USDC,
            "protocol_request_id": 701,
        }
    ]
    connection.close()

    default_transport_calls: list[tuple[str, ...]] = []

    def default_transport(mints):
        ordered = tuple(sorted(str(mint) for mint in mints))
        default_transport_calls.append(ordered)
        assert ordered == (MINT,)
        return fixture_success_transport(
            {"pairs": [_generic_dex_pair(mint=MINT, pool=POOL)]}
        )

    monkeypatch.setattr(
        "printer_v1.sources.dexscreener.build_dexscreener_mint_batch_transport",
        default_transport,
    )

    result = run_persistent_eligible_token_supply(
        db_path,
        cycle_seed="generic-protocol-resume-default-seed",
        migration_transport=lambda _context: {"result": []},
        now=NOW,
        permanent_availability=True,
        enable_geckoterminal_reconciliation=False,
        persist_terminal_certificate=False,
    )

    assert default_transport_calls == [(MINT,)]
    assert (
        result.diagnostics["stage_capacity"]["used_by_stage"]["market_batching"]
        == 1
    )

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    try:
        state = check.execute(
            """
            SELECT token_program_id,pool_program_id,base_mint,quote_mint,venue
            FROM printer_exact_market_states
            WHERE mint_identity=? AND pool_address=?
            """,
            (MINT, POOL),
        ).fetchone()
        assert dict(state) == {
            "token_program_id": TOKEN_PROGRAM_ID,
            "pool_program_id": GENERIC_POOL_PROGRAM,
            "base_mint": MINT,
            "quote_mint": USDC,
            "venue": GENERIC_VENUE,
        }
        assert (
            check.execute(
                """
                SELECT COUNT(*) FROM printer_discovery_reserve_layers
                WHERE mint_identity=? AND pool_address=?
                  AND reserve_layer=? AND reserve_state='ACTIVE'
                """,
                (MINT, POOL, MEMORY_OBSERVATION_ELIGIBLE),
            ).fetchone()[0]
            == 1
        )
        assert load_protocol_resume_market_due(check) == []
        assert (
            check.execute(
                "SELECT COUNT(*) FROM printer_graduated_market_floor_state "
                "WHERE mint_identity=?",
                (MINT,),
            ).fetchone()[0]
            == 0
        )
        assert (
            check.execute(
                "SELECT COUNT(*) FROM printer_eligible_token_reserve "
                "WHERE mint_identity=?",
                (MINT,),
            ).fetchone()[0]
            == 0
        )
    finally:
        check.close()


def test_protocol_resume_charges_exact_two_batches_and_leaves_overflow_durable(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "generic-protocol-resume-batching.sqlite3"
    apply_migrations(db_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    expected_pool_by_mint: dict[str, str] = {}
    for index in range(61):
        mint = f"GenericResumeMint{index:03d}"
        pool = f"GenericResumePool{index:03d}"
        expected_pool_by_mint[mint] = pool
        _record_generic_protocol_confirmed(
            connection,
            mint=mint,
            pool=pool,
            protocol_request_id=800 + index,
            pool_program=f"GenericAmmProgram{index:03d}",
        )
    connection.commit()
    connection.close()

    batch_calls: list[tuple[str, ...]] = []

    def batch_factory(mints):
        ordered = tuple(sorted(str(mint) for mint in mints))
        batch_calls.append(ordered)
        return fixture_success_transport(
            {
                "pairs": [
                    _generic_dex_pair(
                        mint=mint,
                        pool=expected_pool_by_mint[mint],
                    )
                    for mint in ordered
                ]
            }
        )

    result = run_persistent_eligible_token_supply(
        db_path,
        cycle_seed="generic-protocol-resume-batching-seed",
        migration_transport=lambda _context: {"result": []},
        dexscreener_batch_transport_factory=batch_factory,
        now=NOW,
        permanent_availability=True,
        enable_geckoterminal_reconciliation=False,
        persist_terminal_certificate=False,
    )

    assert [len(batch) for batch in batch_calls] == [30, 30]
    stage = result.diagnostics["stage_capacity"]
    assert stage["used_by_stage"]["market_batching"] == 2
    assert stage["remaining_by_stage"]["market_batching"] == 0
    assert result.shortage_classification == BUDGET_EXHAUSTION

    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    try:
        remaining = load_protocol_resume_market_due(check)
        assert len(remaining) == 1
        remaining_mint = remaining[0]["mint"]
        assert remaining_mint in expected_pool_by_mint
        assert remaining[0]["pool"] == expected_pool_by_mint[remaining_mint]
        assert remaining[0]["venue"] == GENERIC_VENUE
        assert remaining[0]["quote_mint"] == USDC
        moe_count = int(
            check.execute(
                """
                SELECT COUNT(*) FROM printer_discovery_reserve_layers
                WHERE reserve_layer=? AND reserve_state='ACTIVE'
                """,
                (MEMORY_OBSERVATION_ELIGIBLE,),
            ).fetchone()[0]
        )
        assert moe_count == 60
        assert (
            check.execute(
                "SELECT COUNT(*) FROM printer_graduated_market_floor_state"
            ).fetchone()[0]
            == 0
        )
        assert (
            check.execute(
                "SELECT COUNT(*) FROM printer_eligible_token_reserve"
            ).fetchone()[0]
            == 0
        )
    finally:
        check.close()

    pending = result.diagnostics["pending_work_by_queue"][
        "PROTOCOL_RESUME_MARKET_DUE"
    ]
    assert len(pending) == 1
    assert pending[0]["mint"] == remaining_mint



def test_lawful_acquisition_queue_guard_uses_exact_owner_capacity() -> None:
    budget = StageBudget.permanent_discovery_default()
    work_queues = {
        "MARKET_BATCHING_DUE": [{"mint": "MarketMint", "pool": "MarketPool"}],
        "RECONCILIATION_DUE": [],
        "PROTOCOL_CONFIRMATION_DUE": [
            {"mint": "ProtocolMint", "pool": "ProtocolPool"}
        ],
        "PROTOCOL_RESUME_MARKET_DUE": [],
        "HOLDER_SAFETY_DUE": [{"mint": "HolderMint", "pool": "HolderPool"}],
    }

    lawful = _lawful_pending_acquisition_work(
        work_queues=work_queues,
        stage_budget=budget,
        source_operations_remaining=5,
        duration_remaining_seconds=60.0,
    )
    assert set(lawful) == {
        "MARKET_BATCHING_DUE",
        "PROTOCOL_CONFIRMATION_DUE",
    }

    budget.consume("market_batching", 2)
    lawful_after_market_exhaustion = _lawful_pending_acquisition_work(
        work_queues=work_queues,
        stage_budget=budget,
        source_operations_remaining=5,
        duration_remaining_seconds=60.0,
    )
    assert set(lawful_after_market_exhaustion) == {
        "PROTOCOL_CONFIRMATION_DUE"
    }

    budget.seal("protocol_confirmation")
    assert (
        _lawful_pending_acquisition_work(
            work_queues=work_queues,
            stage_budget=budget,
            source_operations_remaining=5,
            duration_remaining_seconds=60.0,
        )
        == {}
    )
    assert (
        _lawful_pending_acquisition_work(
            work_queues=work_queues,
            stage_budget=StageBudget.permanent_discovery_default(),
            source_operations_remaining=0,
            duration_remaining_seconds=60.0,
        )
        == {}
    )
    assert (
        _lawful_pending_acquisition_work(
            work_queues=work_queues,
            stage_budget=StageBudget.permanent_discovery_default(),
            source_operations_remaining=5,
            duration_remaining_seconds=0.0,
        )
        == {}
    )


def test_generic_insufficient_terminal_is_replaced_by_architecture_fault_when_work_is_lawful(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "lawful-work-terminal-invariant.sqlite3"
    apply_migrations(db_path)

    monkeypatch.setattr(
        "printer_v1.discovery.eligible_token_supply._lawful_pending_acquisition_work",
        lambda **_kwargs: {
            "PROTOCOL_CONFIRMATION_DUE": {
                "stage": "protocol_confirmation",
                "pending_count": 1,
                "stage_operations_available": 1,
                "flat_source_operations_remaining": 1,
            }
        },
    )

    result = run_persistent_eligible_token_supply(
        db_path,
        cycle_seed="lawful-work-terminal-invariant-seed",
        migration_transport=lambda _context: {"result": []},
        now=NOW,
        permanent_availability=True,
        enable_geckoterminal_reconciliation=False,
        persist_terminal_certificate=False,
    )

    assert result.terminal == DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE
    assert result.shortage_classification == DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE
    assert (
        result.exhaustion_certificate.last_reason_discovery_could_not_continue
        == "LAWFUL_WORK_REMAINING_WITH_CAPACITY"
    )


def test_permanent_market_stage_charges_only_measured_market_calls() -> None:
    import inspect

    source = inspect.getsource(run_persistent_eligible_token_supply)
    resolver = source.index("permanent_report = run_dexscreener_batch_market_resolution(")
    measured = source.index("market_calls = int(front_door.get(\"market_calls\") or 0)")
    charge = source.index('stage_budget.consume("market_batching", market_calls)')
    assert resolver < measured < charge
    assert 'stage_budget.consume("market_batching", 1)' not in source[:resolver]

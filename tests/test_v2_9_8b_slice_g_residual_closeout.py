from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery import permanent_discovery_availability as availability
from printer_v1.discovery import pre_lifecycle_refresh_composition as refresh_composition
from printer_v1.discovery.eligible_token_supply import (
    ACQUISITION_QUANTUM_YIELDED,
    AcquisitionQuantumKind,
    acquisition_quantum_bound,
    run_persistent_eligible_token_supply,
)
from printer_v1.discovery.permanent_discovery_availability import (
    CONTRACT_BLOCKED,
    CURRENT_POOL_CONFIRMED,
    ExactMarketObservation,
    MEMORY_OBSERVATION_ELIGIBLE,
    REASON_ABOVE_FLOOR_NOMINATION,
    SPL_TOKEN_PROGRAM_ID,
    StageBudget,
    build_campaign_source_request_scope,
    record_exact_market_transition,
    record_fresh_pool_nominations,
    upsert_reserve_layer,
    validate_cooperative_resume_source_request_scope,
)
from printer_v1.sources.dexscreener import DEXSCREENER_SMOKE_TIMEOUT_SECONDS
from printer_v1.sources.pumpswap import PUMPSWAP_AMM_PROGRAM_ID
from printer_v1.operator_cli.one_command_15m_factory import (
    _later_cycle_acquisition_deadline_conflict,
)


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc).isoformat()
WSOL = "So11111111111111111111111111111111111111112"
ROOT = "v2-9-8b-window15m-exec-g-residual"


def _kwargs(path, budget: StageBudget, phase: str) -> dict[str, object]:
    return {
        "cycle_seed": "slice-g-residual",
        "migration_transport": object(),
        "now": NOW,
        "permanent_availability": True,
        "run_locator": False,
        "enable_geckoterminal_reconciliation": False,
        "campaign_id": "campaign-g-residual",
        "run_id": "run-g-residual",
        "cycle_id": "cycle-g-residual",
        "discovery_request_key_prefix": ROOT,
        "front_door_request_key_prefix": ROOT,
        "cooperative_resume": True,
        "cooperative_quantum": True,
        "cooperative_phase": phase,
        "cooperative_stage_budget": budget,
    }


def _inventory() -> list[dict[str, object]]:
    return [
        {
            "mint_identity": "MintResidual",
            "pumpswap_pool": "PoolResidual",
            "market_identity": "solana-mainnet:pumpswap:PoolResidual",
            "lifecycle_state": "PUMPSWAP_PROTOCOL_CONFIRMED",
            "graduation_block_time": None,
            "pumpswap_program_id": PUMPSWAP_AMM_PROGRAM_ID,
            "latest_channel": "PROTOCOL_CONFIRMED",
        }
    ]


def _empty_market_report() -> dict[str, object]:
    return {
        "candidates": [],
        "source_request_count": 1,
        "source_request_ids": [1],
        "calls_by_stage": {"market_batching": 1, "reconciliation": 0},
    }


def test_market_quantum_yields_before_residual_protocol(monkeypatch, tmp_path) -> None:
    path = tmp_path / "market-preemption.sqlite3"
    apply_migrations(path)
    budget = StageBudget.permanent_discovery_default()
    source_calls: list[str] = []

    monkeypatch.setattr(
        "printer_v1.discovery.eligible_token_supply.export_graduated_candidates",
        lambda *_args, **_kwargs: _inventory(),
    )

    def market(connection, **_kwargs):
        source_calls.append("dexscreener_market_batch_http")
        record_fresh_pool_nominations(
            connection,
            observations=[{
                "mint": "MintResidual",
                "pool": "PoolResidual",
                "base_mint": "MintResidual",
                "quote_mint": WSOL,
                "venue": "pumpswap",
                "liquidity_usd": 5_000.0,
            }],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="campaign-g-residual",
        )
        return _empty_market_report()

    monkeypatch.setattr(
        "printer_v1.discovery.eligible_token_supply.run_dexscreener_batch_market_resolution",
        market,
    )
    monkeypatch.setattr(
        availability,
        "process_protocol_confirmation_queue",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("protocol must wait for a later Scheduler claim")
        ),
    )

    result = run_persistent_eligible_token_supply(
        path, **_kwargs(path, budget, "MARKET_DISCOVERY")
    )

    assert result.terminal == ACQUISITION_QUANTUM_YIELDED
    assert source_calls == ["dexscreener_market_batch_http"]
    assert result.diagnostics["next_cooperative_phase"] == "PROTOCOL_CONFIRMATION"
    assert result.diagnostics["pending_work_by_queue"]["PROTOCOL_CONFIRMATION_DUE"] == [
        {"mint": "MintResidual", "pool": "PoolResidual", "venue": "pumpswap"}
    ]


def test_market_quantum_yields_even_when_it_fills_the_reserve(
    monkeypatch, tmp_path
) -> None:
    path = tmp_path / "market-ready-still-yields.sqlite3"
    apply_migrations(path)
    budget = StageBudget.permanent_discovery_default()
    inventory = [
        {
            **_inventory()[0],
            "mint_identity": f"MintReady{index}",
            "pumpswap_pool": f"PoolReady{index}",
            "market_identity": f"solana-mainnet:pumpswap:PoolReady{index}",
        }
        for index in range(4)
    ]
    monkeypatch.setattr(
        "printer_v1.discovery.eligible_token_supply.export_graduated_candidates",
        lambda *_args, **_kwargs: inventory,
    )

    def market(_connection, **_kwargs):
        candidates = []
        for index in range(4):
            candidates.append({
                "mint": f"MintReady{index}",
                "pool": f"PoolReady{index}",
                "pumpswap_pool": f"PoolReady{index}",
                "market_identity": f"solana-mainnet:pumpswap:PoolReady{index}",
                "provenance": "FIXTURE_MARKET",
                "lifecycle_state": "PUMPSWAP_PROTOCOL_CONFIRMED",
                "graduation_block_time": None,
                "liquidity": {
                    "status": "LIQUIDITY_PROVEN",
                    "liquidity_usd": 5_000.0,
                    "reason": "AT_OR_ABOVE_3000_FLOOR",
                },
                "liquidity_status": "LIQUIDITY_PROVEN",
                "evidence_expires_at": (
                    datetime.fromisoformat(NOW) + timedelta(minutes=30)
                ).isoformat(),
                "eligible": True,
                "rejection": None,
                "memory_observation_eligible": True,
            })
        return {
            **_empty_market_report(),
            "candidates": candidates,
        }

    monkeypatch.setattr(
        "printer_v1.discovery.eligible_token_supply.run_dexscreener_batch_market_resolution",
        market,
    )
    monkeypatch.setattr(
        "printer_v1.discovery.eligible_token_supply.upsert_eligible_reserve",
        lambda *_args, **_kwargs: None,
    )

    result = run_persistent_eligible_token_supply(
        path, **_kwargs(path, budget, "MARKET_DISCOVERY")
    )

    assert result.ready is False
    assert result.terminal == ACQUISITION_QUANTUM_YIELDED
    assert result.diagnostics["eligible_reserve_count"] == 4


def test_protocol_quantum_yields_before_resume_market(monkeypatch, tmp_path) -> None:
    path = tmp_path / "protocol-preemption.sqlite3"
    apply_migrations(path)
    budget = StageBudget.permanent_discovery_default()
    calls: list[tuple[str, int, int]] = []

    def protocol(_connection, *, stage_budget, stage_sequence, max_confirmations, **_kwargs):
        calls.append(("protocol_confirmation_rpc", stage_sequence, max_confirmations))
        stage_budget.consume("protocol_confirmation", 1)
        return {
            "outcomes": [],
            "remaining_due": [
                {"mint": "MintLater", "pool": "PoolLater", "venue": "pumpswap"}
            ],
            "confirmed_for_market": [],
            "promoted_observation_eligible": [],
            "requires_market_revalidation": [
                {"mint": "MintResidual", "pool": "PoolResidual", "venue": "pumpswap"}
            ],
            "source_requests": 1,
            "source_request_ids": [1],
            "source_request_coverage": [],
            "outcome_counts": {},
            "sealed_stage_evidence_blocks": [],
        }

    monkeypatch.setattr(availability, "process_protocol_confirmation_queue", protocol)
    monkeypatch.setattr(
        "printer_v1.discovery.eligible_token_supply.run_dexscreener_batch_market_resolution",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("resume market must wait for a later Scheduler claim")
        ),
    )

    result = run_persistent_eligible_token_supply(
        path, **_kwargs(path, budget, "PROTOCOL_CONFIRMATION")
    )

    assert result.terminal == ACQUISITION_QUANTUM_YIELDED
    assert calls == [("protocol_confirmation_rpc", 1, 1)]
    assert result.diagnostics["next_cooperative_phase"] == "PROTOCOL_RESUME_MARKET"
    assert result.diagnostics["pending_work_by_queue"]["PROTOCOL_RESUME_MARKET_DUE"] == [
        {"mint": "MintResidual", "pool": "PoolResidual", "venue": "pumpswap"}
    ]


def test_protocol_resume_market_is_one_dex_quantum_and_charges_shared_budget(
    monkeypatch, tmp_path
) -> None:
    path = tmp_path / "protocol-resume-market.sqlite3"
    apply_migrations(path)
    budget = StageBudget.permanent_discovery_default()
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    record_exact_market_transition(
        connection,
        ExactMarketObservation(
            network="solana-mainnet",
            mint="MintResidual",
            pool="PoolResidual",
            token_program=SPL_TOKEN_PROGRAM_ID,
            pool_program=PUMPSWAP_AMM_PROGRAM_ID,
            base_mint="MintResidual",
            quote_mint=WSOL,
            venue="pumpswap",
            state=CURRENT_POOL_CONFIRMED,
            reason="EXACT_PUMPSWAP_OWNER_AND_BASE_MINT",
            observed_at=NOW,
            next_lawful_action_at=None,
            source_provenance={"stage": "protocol_confirmation"},
            contract_version="TEST_V1",
        ),
        now=NOW,
    )
    record_fresh_pool_nominations(
        connection,
        observations=[{
            "mint": "MintLater",
            "pool": "PoolLater",
            "base_mint": "MintLater",
            "quote_mint": WSOL,
            "venue": "pumpswap",
            "liquidity_usd": 5_000.0,
        }],
        source="dexscreener",
        request_id=2,
        now=NOW,
        campaign_id="campaign-g-residual",
    )
    connection.commit()
    connection.close()
    calls: list[dict[str, object]] = []

    def market(market_connection, **kwargs):
        calls.append(kwargs)
        upsert_reserve_layer(
            market_connection,
            network="solana-mainnet",
            mint="MintResidual",
            pool="PoolResidual",
            layer=MEMORY_OBSERVATION_ELIGIBLE,
            reserve_state="ACTIVE",
            reason="EXACT_MARKET_REVALIDATED",
            observed_at=NOW,
            next_lawful_action_at=None,
            evidence_expires_at=(
                datetime.fromisoformat(NOW) + timedelta(minutes=30)
            ).isoformat(),
            source_provenance={"stage": "protocol_resume_market"},
            evidence={"liquidity_usd": 5_000.0},
            campaign_id="campaign-g-residual",
        )
        return _empty_market_report()

    monkeypatch.setattr(
        "printer_v1.discovery.eligible_token_supply.run_dexscreener_batch_market_resolution",
        market,
    )

    result = run_persistent_eligible_token_supply(
        path, **_kwargs(path, budget, "PROTOCOL_RESUME_MARKET")
    )

    assert result.terminal == ACQUISITION_QUANTUM_YIELDED
    assert len(calls) == 1
    assert calls[0]["geckoterminal_transport_factory"] is None
    assert calls[0]["enable_geckoterminal_fallback"] is False
    assert "protocol-resume-mb" in str(calls[0]["request_key"])
    assert budget.used_by_stage["market_batching"] == 1
    assert result.diagnostics["next_cooperative_phase"] == "PROTOCOL_CONFIRMATION"
    bound = acquisition_quantum_bound(AcquisitionQuantumKind.PROTOCOL_RESUME_MARKET)
    assert bound.worst_case_seconds == DEXSCREENER_SMOKE_TIMEOUT_SECONDS == 5.0
    assert [item.name for item in bound.components] == [
        "dexscreener_protocol_resume_market_http"
    ]


def test_completed_market_evidence_is_not_requeued_for_protocol_resume(
    tmp_path,
) -> None:
    path = tmp_path / "protocol-resume-complete.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    record_exact_market_transition(
        connection,
        ExactMarketObservation(
            network="solana-mainnet",
            mint="MintComplete",
            pool="PoolComplete",
            token_program=SPL_TOKEN_PROGRAM_ID,
            pool_program=PUMPSWAP_AMM_PROGRAM_ID,
            base_mint="MintComplete",
            quote_mint=WSOL,
            venue="pumpswap",
            state=CURRENT_POOL_CONFIRMED,
            reason="EXACT_PUMPSWAP_OWNER_AND_BASE_MINT",
            observed_at=NOW,
            next_lawful_action_at=None,
            source_provenance={"stage": "protocol_confirmation"},
            contract_version="TEST_V1",
        ),
        now=NOW,
    )
    upsert_reserve_layer(
        connection,
        network="solana-mainnet",
        mint="MintComplete",
        pool="PoolComplete",
        layer=MEMORY_OBSERVATION_ELIGIBLE,
        reserve_state="ACTIVE",
        reason="EXACT_MARKET_REVALIDATED",
        observed_at=NOW,
        next_lawful_action_at=None,
        evidence_expires_at=(datetime.fromisoformat(NOW) + timedelta(minutes=30)).isoformat(),
        source_provenance={"stage": "protocol_resume_market"},
        evidence={"liquidity_usd": 5_000.0},
        campaign_id="campaign-g-residual",
    )
    connection.commit()

    assert availability.load_protocol_resume_market_due(connection) == []
    connection.close()


def test_market_deadline_guard_never_assumes_hidden_residual_protocol() -> None:
    now = datetime.fromisoformat(NOW)
    market = acquisition_quantum_bound(
        AcquisitionQuantumKind.MARKET_DISCOVERY
    ).worst_case_seconds
    protocol = acquisition_quantum_bound(
        AcquisitionQuantumKind.PROTOCOL_CONFIRMATION
    ).worst_case_seconds
    deadline = now + timedelta(seconds=market + 1)

    assert market == 83.0
    assert market + protocol == 103.0
    assert _later_cycle_acquisition_deadline_conflict(
        now=now,
        earliest_lifecycle_deadline=deadline,
        worst_case_quantum_seconds=market,
    ) is False
    assert _later_cycle_acquisition_deadline_conflict(
        now=now,
        earliest_lifecycle_deadline=deadline,
        worst_case_quantum_seconds=market + protocol,
    ) is True
    assert _later_cycle_acquisition_deadline_conflict(
        now=now + timedelta(seconds=market),
        earliest_lifecycle_deadline=deadline,
        worst_case_quantum_seconds=protocol,
    ) is True


def test_market_protocol_resume_and_refresh_never_replenish_stage_budget() -> None:
    budget = StageBudget.permanent_discovery_default()
    snapshots = [budget.snapshot()]
    for stage, count in (
        ("market_batching", 1),
        ("protocol_confirmation", 1),
        ("market_batching", 1),
        ("final_refresh_handoff", 1),
    ):
        budget.consume(stage, count)
        snapshots.append(budget.snapshot())

    assert all(
        later["remaining_by_stage"][stage]
        <= earlier["remaining_by_stage"][stage]
        for earlier, later in zip(snapshots, snapshots[1:], strict=False)
        for stage in earlier["remaining_by_stage"]
    )
    assert budget.used_by_stage == {
        "intake": 0,
        "market_batching": 2,
        "reconciliation": 0,
        "protocol_confirmation": 1,
        "holder_safety": 0,
        "final_refresh_handoff": 1,
    }
    with pytest.raises(ValueError, match="STAGE_RESERVATION_EXCEEDED"):
        budget.consume("market_batching", 1)


def test_protocol_stage_sequence_allocator_is_monotonic_for_every_producer(
    tmp_path,
) -> None:
    path = tmp_path / "protocol-stage-sequence.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    allocated: list[int] = []
    producer_keys = (
        lambda sequence: f"{ROOT}-protocol-q{sequence}-1",
        lambda sequence: f"{ROOT}-protocol-q{sequence}-1",
        lambda sequence: f"{ROOT}-protocol-residual-q{sequence}-1",
        lambda sequence: f"{ROOT}-refresh-2-protocol-q{sequence}-1",
    )
    for build_key in producer_keys:
        sequence = availability.next_protocol_confirmation_stage_sequence(
            connection, request_key_prefix=ROOT
        )
        allocated.append(sequence)
        request_id = int(
            connection.execute(
                "INSERT INTO printer_source_requests("
                "source_name,request_kind,request_key,requested_at,source_status,data_quality_label) "
                "VALUES ('solana_rpc','pumpswap_pool_account_batch',?,?, 'COMPLETE','CLEAN_DATA')",
                (build_key(sequence), NOW),
            ).lastrowid
        )
        connection.execute(
            "INSERT INTO printer_source_responses("
            "source_request_id,source_name,received_at,source_status,data_quality_label) "
            "VALUES (?,'solana_rpc',?,'COMPLETE','CLEAN_DATA')",
            (request_id, NOW),
        )
        connection.commit()

    assert allocated == [1, 2, 3, 4]
    assert len(set(allocated)) == 4
    scope = build_campaign_source_request_scope(
        execution_id="exec-g-residual",
        campaign_id="campaign-g-residual",
        run_id="run-g-residual",
        cycle_id="cycle-g-residual",
    )
    assert scope.request_key_root == ROOT
    validated = validate_cooperative_resume_source_request_scope(
        connection,
        scope=scope,
        execution_id=scope.execution_id,
        campaign_id=scope.campaign_id,
        run_id=scope.run_id,
        cycle_id=scope.cycle_id,
    )
    assert validated["count"] == 4
    connection.close()


def test_real_protocol_stage_seals_are_unique_across_cooperative_producers(
    tmp_path,
) -> None:
    from printer_v1.sources.pumpswap_pool_account_batch import (
        fixture_account_batch_transport,
    )

    path = tmp_path / "protocol-stage-seals.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    budget = StageBudget.permanent_discovery_default()
    sealed: list[dict[str, object]] = []
    prefix_builders = (
        lambda sequence: f"{ROOT}-protocol-q{sequence}",
        lambda sequence: f"{ROOT}-protocol-q{sequence}",
        lambda sequence: f"{ROOT}-protocol-residual-q{sequence}",
        lambda sequence: f"{ROOT}-refresh-2-protocol-q{sequence}",
    )

    for index, build_prefix in enumerate(prefix_builders, start=1):
        mint = f"MintProtocol{index}{'z' * 30}"
        pool = f"PoolProtocol{index}{'z' * 30}"
        record_fresh_pool_nominations(
            connection,
            observations=[{
                "mint": mint,
                "pool": pool,
                "base_mint": mint,
                "quote_mint": WSOL,
                "venue": "pumpswap",
                "liquidity_usd": 5_000.0,
            }],
            source="dexscreener",
            request_id=100 + index,
            now=NOW,
            campaign_id="campaign-g-residual",
        )
        sequence = availability.next_protocol_confirmation_stage_sequence(
            connection,
            request_key_prefix=ROOT,
        )
        report = availability.process_protocol_confirmation_queue(
            connection,
            stage_budget=budget,
            now=NOW,
            campaign_id="campaign-g-residual",
            run_id="run-g-residual",
            cycle_id="cycle-g-residual",
            max_confirmations=1,
            account_batch_transport=fixture_account_batch_transport({pool: None}),
            stage_evidence_sink=sealed.append,
            stage_sequence=sequence,
            request_key_prefix=build_prefix(sequence),
        )
        assert report["accounting_blocker"] is False

    stage_ids = [str(item["stage_id"]) for item in sealed]
    assert stage_ids == [
        f"campaign-g-residual|run-g-residual|cycle-g-residual|PROTOCOL_CONFIRMATION|{sequence}"
        for sequence in (1, 2, 3, 4)
    ]
    assert len(set(stage_ids)) == 4
    assert budget.used_by_stage["protocol_confirmation"] == 4
    connection.close()


def test_cooperative_refresh_uses_shared_protocol_sequence_allocator(
    monkeypatch, tmp_path
) -> None:
    path = tmp_path / "refresh-protocol-sequence.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    captured: list[tuple[int, str]] = []

    monkeypatch.setattr(
        refresh_composition,
        "run_fresh_profile_locator",
        None,
        raising=False,
    )
    monkeypatch.setattr(
        "printer_v1.operator_cli.graduated_supply_front_door.run_fresh_profile_locator",
        lambda *_args, **_kwargs: {
            "source_requests": 1,
            "status": "empty",
            "pool_observations": [],
            "request_id": 1,
            "response_id": 1,
        },
    )
    monkeypatch.setattr(
        refresh_composition,
        "run_bounded_unknown_liquidity_backup",
        lambda *_args, **_kwargs: {"source_requests": 0},
    )

    def protocol(_connection, *, stage_sequence, request_key_prefix, **_kwargs):
        captured.append((stage_sequence, request_key_prefix))
        return {
            "source_requests": 0,
            "promoted_observation_eligible": [],
            "shared_source_failures": 0,
        }

    monkeypatch.setattr(refresh_composition, "process_protocol_confirmation_queue", protocol)
    monkeypatch.setattr(
        refresh_composition,
        "next_protocol_confirmation_stage_sequence",
        lambda *_args, **_kwargs: 9,
    )
    stage = refresh_composition.build_pre_lifecycle_refresh_stage(
        db_path=path,
        request_key_prefix=ROOT,
        locator_transport=object(),
    )
    budget = StageBudget.permanent_discovery_default()

    stage(
        connection,
        campaign_id="campaign-g-residual",
        run_id="run-g-residual",
        cycle_id="cycle-g-residual",
        discovery_work_id="work-g-residual",
        scheduler_job_id=1,
        refresh_ordinal=2,
        source_operations_remaining=4,
        now=NOW,
        cooperative_yield=True,
        cooperative_stage_budget=budget,
    )

    assert captured == [(9, f"{ROOT}-refresh-2-protocol-q9")]
    connection.close()

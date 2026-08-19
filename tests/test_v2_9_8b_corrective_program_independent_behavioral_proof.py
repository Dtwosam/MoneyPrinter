from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sqlite3

import pytest

import printer_v1.discovery.eligible_token_supply as eligible_supply
import printer_v1.lifecycle.tracking_queue as tracking_queue
from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    CURRENT_VISIBLE,
    ExactMarketObservation,
    StageBudget,
    load_exact_market_states,
    record_exact_market_transition,
    upsert_reserve_layer,
)
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    NO_LAWFUL_REFRESH_WINDOW,
    TemporalRefreshOutcome,
    WAITING_FOR_ELIGIBLE_SUPPLY,
)
from printer_v1.sources.pumpswap_graduated_registry import record_graduated_candidate
from printer_v1.trading_flow.recorder import record_trading_flow_snapshot


NOW = "2026-08-19T12:40:00+00:00"
CAMPAIGN = "campaign-independent-proof"
MINT = "FreshMintIndependentProof"
POOL = "FreshPoolIndependentProof"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
POOL_PROGRAM = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
WSOL = "So11111111111111111111111111111111111111112"


def _never_source(*_args, **_kwargs):
    raise AssertionError("independent behavioral proof must not call a provider")


def _tracking_assessment(*, eligible: bool) -> SimpleNamespace:
    return SimpleNamespace(
        category="TRACKING_ELIGIBLE" if eligible else "ACTIVE_CONFLICT",
        eligible=eligible,
        queue_id=None,
        queue_status=None,
        requalification_eligible=False,
        cooldown_until=None,
        historical_cooldown_expiry_derived=False,
        reason_code=None if eligible else "ACTIVE_CONFLICT",
    )


def _seed_fresh_protocol_confirmed_moe(db_path: Path, *, campaign_id: str = CAMPAIGN) -> None:
    apply_migrations(db_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        record_exact_market_transition(
            connection,
            ExactMarketObservation(
                network="solana-mainnet",
                mint=MINT,
                pool=POOL,
                token_program=TOKEN_PROGRAM,
                pool_program=POOL_PROGRAM,
                base_mint=MINT,
                quote_mint=WSOL,
                venue="pumpswap",
                state=CURRENT_VISIBLE,
                reason="INDEPENDENT_PROTOCOL_CONFIRMED",
                observed_at=NOW,
                next_lawful_action_at=None,
                source_provenance={"source": "geckoterminal", "request_id": 1},
                contract_version="INDEPENDENT_PROOF_V1",
            ),
            now=NOW,
        )
        upsert_reserve_layer(
            connection,
            network="solana-mainnet",
            mint=MINT,
            pool=POOL,
            layer="MEMORY_OBSERVATION_ELIGIBLE",
            reserve_state="ACTIVE",
            reason="PROTOCOL_CONFIRMED_MOE",
            observed_at=NOW,
            next_lawful_action_at=None,
            evidence_expires_at="2026-08-20T12:40:00+00:00",
            source_provenance={"source": "geckoterminal", "request_id": 1},
            evidence={
                "base_mint": MINT,
                "quote_mint": WSOL,
                "liquidity": {
                    "liquidity_usd": 12_106.0,
                    "liquidity_observed_at": NOW,
                },
            },
            campaign_id=campaign_id,
        )
        connection.commit()
    finally:
        connection.close()


def _run_cooperative_supply(
    db_path: Path,
    *,
    monkeypatch: pytest.MonkeyPatch,
    tracking_eligible: bool,
):
    monkeypatch.setattr(
        tracking_queue,
        "assess_tracking_handoff_by_identity",
        lambda *_args, **_kwargs: _tracking_assessment(eligible=tracking_eligible),
    )
    monkeypatch.setattr(eligible_supply, "_utc_now_iso", lambda: NOW)
    return eligible_supply.run_persistent_eligible_token_supply(
        db_path,
        cycle_seed="independent-cycle-seed",
        migration_transport=_never_source,
        now=NOW,
        campaign_id=CAMPAIGN,
        execution_id="independent-execution:c0002",
        run_id="independent-run",
        cycle_id="independent-cycle-2",
        permanent_availability=True,
        tracking_precheck=True,
        cooperative_resume=True,
        cooperative_quantum=True,
        cooperative_phase="PROTOCOL_CONFIRMATION",
        cooperative_stage_budget=StageBudget.permanent_discovery_default(),
    )


def test_cycle2_fresh_moe_rehydrates_into_real_supply_without_bypassing_tracking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eligible_db = tmp_path / "eligible.sqlite3"
    _seed_fresh_protocol_confirmed_moe(eligible_db)
    accepted = _run_cooperative_supply(
        eligible_db,
        monkeypatch=monkeypatch,
        tracking_eligible=True,
    )
    accepted_rows = [row for row in accepted.all_candidates if row.get("mint") == MINT]
    assert accepted_rows
    assert any(row.get("eligible") is True for row in accepted_rows)
    assert any(row.get("mint") == MINT for row in accepted.eligible_reserve)
    # Permanent mode still needs freeze-depth inventory; one fresh carrier is not
    # itself an admission or a ready four-deep supply.
    assert accepted.ready is False

    blocked_db = tmp_path / "blocked.sqlite3"
    _seed_fresh_protocol_confirmed_moe(blocked_db)
    blocked = _run_cooperative_supply(
        blocked_db,
        monkeypatch=monkeypatch,
        tracking_eligible=False,
    )
    blocked_rows = [row for row in blocked.all_candidates if row.get("mint") == MINT]
    assert blocked_rows
    assert all(row.get("eligible") is False for row in blocked_rows)
    assert not any(row.get("mint") == MINT for row in blocked.eligible_reserve)


class _TemporalOwner:
    refresh_interval_seconds = 600

    def __init__(self, outcome_status: str):
        self.outcome_status = outcome_status
        self.calls: list[dict] = []

    def request_temporal_refresh(self, **kwargs):
        self.calls.append(dict(kwargs))
        if self.outcome_status == WAITING_FOR_ELIGIBLE_SUPPLY:
            return TemporalRefreshOutcome(
                status=WAITING_FOR_ELIGIBLE_SUPPLY,
                wait_id="wait-independent-proof",
                scheduler_job_id=77,
                refresh_ordinal=1,
                scheduled_for="2026-08-19T12:50:00+00:00",
                claimed=False,
                source_operations=0,
                reserve_depth_before=int(kwargs["reserve_depth"]),
                reserve_depth_after=int(kwargs["reserve_depth"]),
            )
        return TemporalRefreshOutcome(
            status=NO_LAWFUL_REFRESH_WINDOW,
            refresh_ordinal=0,
            reserve_depth_before=int(kwargs["reserve_depth"]),
            reserve_depth_after=int(kwargs["reserve_depth"]),
        )


def _seed_historical_inventory(db_path: Path) -> None:
    apply_migrations(db_path)
    connection = sqlite3.connect(db_path)
    try:
        record_graduated_candidate(
            connection,
            mint="HistoricalMintIndependentProof",
            migration_signature="HistoricalSignatureIndependentProof",
            pumpswap_pool="HistoricalPoolIndependentProof",
            graduation_block_time=1_784_000_000,
            graduation_slot=1,
            now=NOW,
        )
        connection.commit()
    finally:
        connection.close()


def _market_stage_exhausted_budget() -> StageBudget:
    # Flat discovery budget remains available, but this cooperative market
    # quantum has no remaining market-stage capacity. This is the exact shape
    # that previously could terminalize despite a lawful temporal refresh.
    return StageBudget(
        (
            ("intake", 3),
            ("market_batching", 0),
            ("reconciliation", 6),
            ("protocol_confirmation", 7),
            ("holder_safety", 8),
            ("final_refresh_handoff", 4),
        )
    )


def _run_refresh_boundary_supply(
    db_path: Path,
    *,
    monkeypatch: pytest.MonkeyPatch,
    owner: _TemporalOwner,
    deadline_at: str,
):
    monkeypatch.setattr(
        tracking_queue,
        "assess_tracking_handoff_by_identity",
        lambda *_args, **_kwargs: _tracking_assessment(eligible=True),
    )
    monkeypatch.setattr(eligible_supply, "_utc_now_iso", lambda: NOW)
    return eligible_supply.run_persistent_eligible_token_supply(
        db_path,
        cycle_seed="independent-refresh-seed",
        migration_transport=_never_source,
        now=NOW,
        campaign_id=CAMPAIGN,
        execution_id="independent-execution:c0002",
        run_id="independent-run",
        cycle_id="independent-cycle-2",
        permanent_availability=True,
        tracking_precheck=True,
        cooperative_resume=True,
        cooperative_quantum=True,
        cooperative_phase="MARKET_DISCOVERY",
        cooperative_stage_budget=_market_stage_exhausted_budget(),
        temporal_refresh_owner=owner,
        deadline_at=deadline_at,
    )


def test_cycle2_remaining_refresh_window_yields_to_scheduler_instead_of_terminalizing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "refresh.sqlite3"
    _seed_historical_inventory(db_path)
    owner = _TemporalOwner(WAITING_FOR_ELIGIBLE_SUPPLY)
    result = _run_refresh_boundary_supply(
        db_path,
        monkeypatch=monkeypatch,
        owner=owner,
        deadline_at="2026-08-19T13:00:00+00:00",
    )
    assert len(owner.calls) == 1
    assert owner.calls[0]["source_operations_remaining"] > 0
    assert result.terminal == WAITING_FOR_ELIGIBLE_SUPPLY
    assert result.exhaustion_certificate is None
    assert result.diagnostics["pre_lifecycle_acquisition"]["acquisition_started_at"] == (
        "2026-08-19T12:20:00+00:00"
    )


def test_cycle2_closed_refresh_window_does_not_fake_a_wait(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "closed-refresh.sqlite3"
    _seed_historical_inventory(db_path)
    owner = _TemporalOwner(NO_LAWFUL_REFRESH_WINDOW)
    result = _run_refresh_boundary_supply(
        db_path,
        monkeypatch=monkeypatch,
        owner=owner,
        # Exactly one interval remains; strict due < deadline means no new wait.
        deadline_at="2026-08-19T12:50:00+00:00",
    )
    assert owner.calls == []
    assert result.terminal != WAITING_FOR_ELIGIBLE_SUPPLY
    assert result.ready is False


def _market_observation(
    *,
    mint: str,
    pool: str,
    token_program: str,
    pool_program: str,
    observed_at: str,
) -> ExactMarketObservation:
    return ExactMarketObservation(
        network="solana-mainnet",
        mint=mint,
        pool=pool,
        token_program=token_program,
        pool_program=pool_program,
        base_mint=mint,
        quote_mint=WSOL,
        venue="pumpswap",
        state=CURRENT_VISIBLE,
        reason="INDEPENDENT_IDENTITY_PROOF",
        observed_at=observed_at,
        next_lawful_action_at=None,
        source_provenance={"source": "dexscreener"},
        contract_version="INDEPENDENT_PROOF_V1",
    )


def test_identity_merge_preserves_resolved_against_unresolved_and_upgrades_unresolved(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "identity.sqlite3"
    apply_migrations(db_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        record_exact_market_transition(
            connection,
            _market_observation(
                mint="MintResolved",
                pool="PoolResolved",
                token_program=TOKEN_PROGRAM,
                pool_program=POOL_PROGRAM,
                observed_at="2026-08-19T12:00:00+00:00",
            ),
            now="2026-08-19T12:00:00+00:00",
        )
        record_exact_market_transition(
            connection,
            _market_observation(
                mint="MintResolved",
                pool="PoolResolved",
                token_program="UNRESOLVED_TOKEN_PROGRAM",
                pool_program="UNRESOLVED_POOL_PROGRAM",
                observed_at="2026-08-19T12:05:00+00:00",
            ),
            now="2026-08-19T12:05:00+00:00",
        )
        preserved = load_exact_market_states(connection, mint="MintResolved")[0]
        assert preserved["token_program_id"] == TOKEN_PROGRAM
        assert preserved["pool_program_id"] == POOL_PROGRAM
        assert preserved["current_state"] != "IDENTITY_CONFLICT"

        record_exact_market_transition(
            connection,
            _market_observation(
                mint="MintUpgrade",
                pool="PoolUpgrade",
                token_program="UNRESOLVED_TOKEN_PROGRAM",
                pool_program="UNRESOLVED_POOL_PROGRAM",
                observed_at="2026-08-19T12:00:00+00:00",
            ),
            now="2026-08-19T12:00:00+00:00",
        )
        record_exact_market_transition(
            connection,
            _market_observation(
                mint="MintUpgrade",
                pool="PoolUpgrade",
                token_program=TOKEN_PROGRAM,
                pool_program=POOL_PROGRAM,
                observed_at="2026-08-19T12:05:00+00:00",
            ),
            now="2026-08-19T12:05:00+00:00",
        )
        upgraded = load_exact_market_states(connection, mint="MintUpgrade")[0]
        assert upgraded["token_program_id"] == TOKEN_PROGRAM
        assert upgraded["pool_program_id"] == POOL_PROGRAM
        assert upgraded["current_state"] != "IDENTITY_CONFLICT"
    finally:
        connection.close()


def _load_existing_4h_test_module():
    path = Path(__file__).with_name("test_v2_8_1_one_token_4h_runtime.py")
    spec = importlib.util.spec_from_file_location("_printer_existing_4h_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_4h_quality_gate_persists_real_u2_coverage_row() -> None:
    module = _load_existing_4h_test_module()
    case = module.OneToken4hRuntimeTests(
        methodName="test_clean_close_runs_e2q_lane_q_lane_k_and_is_idempotent"
    )
    case.setUp()
    try:
        case.test_clean_close_runs_e2q_lane_q_lane_k_and_is_idempotent()
        coverage = case.conn.execute(
            """SELECT actual_snapshot_count,expected_snapshot_count,
                      missing_snapshot_count,do_not_train
               FROM printer_snapshot_window_coverage
               WHERE window_kind='WINDOW_4H'
               ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        assert coverage is not None
        assert int(coverage["actual_snapshot_count"]) == 61
        assert int(coverage["expected_snapshot_count"]) == 61
        assert int(coverage["missing_snapshot_count"]) == 0
        assert int(coverage["do_not_train"]) == 0
        window = case.conn.execute(
            """SELECT coverage_state,memory_quality_label,do_not_train
               FROM printer_memory_windows
               WHERE window_kind='WINDOW_4H'
               ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        assert window is not None
        assert window["coverage_state"] == "COVERAGE_PASS"
        # E2Q candidate semantics remain unchanged by U2 persistence.
        assert window["memory_quality_label"] == "PARTIAL_MEMORY"
        assert int(window["do_not_train"]) == 0
    finally:
        case.tearDown()


def test_optional_wallet_flow_completeness_is_durably_persisted(tmp_path: Path) -> None:
    db_path = tmp_path / "flow.sqlite3"
    apply_migrations(db_path)
    connection = sqlite3.connect(db_path)
    try:
        token_id = int(
            connection.execute(
                "INSERT INTO printer_tokens(token_mint,chain) VALUES ('flow-proof-mint','solana')"
            ).lastrowid
        )
        pair_id = int(
            connection.execute(
                """INSERT INTO printer_pairs(token_id,pair_address,dex,pool_source)
                   VALUES (?,'flow-proof-pair','pumpswap','local')""",
                (token_id,),
            ).lastrowid
        )
        connection.commit()
    finally:
        connection.close()

    payload = {
        "token": {"token_id": token_id, "mint": "flow-proof-mint"},
        "pair": {"pair_id": pair_id, "pair_address": "flow-proof-pair"},
        "captured_at": NOW,
        "price_usd": 0.01,
        "liquidity_usd": 12_000,
        "volume": {"m5": 125_000, "m15": 260_000, "h1": 600_000, "h4": 900_000, "h24": 1_800_000},
        "txns": {"m5": 150, "m15": 320, "h1": 900, "h4": 1200, "h24": 3000, "m5_buys": 110, "m5_sells": 35},
        "wallets": {},
        "source_status": SourceStatus.COMPLETE.value,
        "data_quality_label": DataQualityLabel.CLEAN_DATA.value,
    }
    created, row_id = record_trading_flow_snapshot(db_path, payload)
    assert created is True
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT normalized_trading_flow_payload_json FROM printer_trading_flow_snapshots WHERE id=?",
            (row_id,),
        ).fetchone()
        assert row is not None
        normalized = json.loads(row["normalized_trading_flow_payload_json"])
    finally:
        connection.close()
    decision = normalized["optional_wallet_flow_enrichment"]
    assert decision["status"] == "NOT_SUPPORTED_BY_APPROVED_FREE_SOURCE"
    assert set(decision["missing_fields"]) == {
        "unique_wallets_5m",
        "buy_volume_5m",
        "sell_volume_5m",
    }
    assert decision["external_attempt_required"] is False
    assert decision["clean_memory_blocker"] is False

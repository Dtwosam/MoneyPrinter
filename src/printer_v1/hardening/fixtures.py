"""Deterministic synthetic fixtures for local validation only."""

from __future__ import annotations

from copy import deepcopy


BASE_TIME = "2026-01-01T00:00:00Z"
TOKEN_MINT = "synthetic-solana-meme-mint"
PAIR_ADDRESS = "synthetic-solana-pair-address"


def build_synthetic_solana_token_fixture() -> dict:
    return {
        "token_id": 1,
        "token_mint": TOKEN_MINT,
        "chain": "solana",
        "symbol": "SYNMEME",
        "name": "Synthetic Solana Meme",
        "first_seen_at": BASE_TIME,
        "last_seen_at": "2026-01-01T00:15:00Z",
        "token_status": "TRACKING",
    }


def build_synthetic_pair_fixture() -> dict:
    return {
        "pair_id": 1,
        "token_id": 1,
        "pair_address": PAIR_ADDRESS,
        "dex": "synthetic-dex",
        "pool_source": "synthetic-local",
        "base_token_mint": TOKEN_MINT,
        "quote_token_mint": "So11111111111111111111111111111111111111112",
        "first_seen_at": BASE_TIME,
        "last_seen_at": "2026-01-01T00:15:00Z",
    }


def build_synthetic_discovery_payload() -> dict:
    return {
        "token": build_synthetic_solana_token_fixture(),
        "pair": build_synthetic_pair_fixture(),
        "discovery_label": "DISCOVERY_ACCEPTED",
        "tracking_lane": "TRACK_FAST",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
    }


def build_synthetic_token_snapshots_for_15m_pump() -> list[dict]:
    points = [
        ("2026-01-01T00:00:00Z", 0.0010, 120000.0, 0.0),
        ("2026-01-01T00:05:00Z", 0.0014, 126000.0, 40.0),
        ("2026-01-01T00:10:00Z", 0.0017, 132000.0, 70.0),
        ("2026-01-01T00:15:00Z", 0.0020, 140000.0, 100.0),
    ]
    return [
        {
            "token_id": 1,
            "pair_id": 1,
            "captured_at": captured_at,
            "tracking_lane": "TRACK_FAST",
            "snapshot_mode": "TOKEN_LEVEL",
            "price_usd": price,
            "liquidity_usd": liquidity,
            "volume_5m": 20000.0 + index * 5000,
            "volume_15m": 85000.0,
            "txns_5m": 60 + index * 10,
            "txns_15m": 260,
            "price_change_5m": change,
            "price_change_15m": 100.0,
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
        }
        for index, (captured_at, price, liquidity, change) in enumerate(points)
    ]


def build_synthetic_token_snapshots_for_fake_pump() -> list[dict]:
    snapshots = build_synthetic_token_snapshots_for_15m_pump()
    snapshots[-1]["price_usd"] = snapshots[0]["price_usd"]
    snapshots[-1]["price_change_15m"] = 0.0
    snapshots[-1]["price_change_5m"] = -40.0
    return snapshots


def build_synthetic_safety_context() -> dict:
    return {
        "safety_status_label": "SAFETY_CLEAN",
        "rug_risk_label": "RUG_RISK_LOW",
        "safety_payload_quality_label": "SAFETY_CONTEXT_CLEAN",
        "safety_memory_gate_label": "SAFETY_CONTEXT_ACCEPTABLE",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
    }


def build_synthetic_liquidity_exit_context(realistic_exit: bool = True) -> dict:
    return {
        "liquidity_state_label": "LIQUIDITY_USABLE",
        "entry_realism_label": "ENTRY_REALISTIC",
        "exit_realism_label": "EXIT_REALISTIC" if realistic_exit else "EXIT_UNREALISTIC",
        "slippage_label": "SLIPPAGE_LOW" if realistic_exit else "SLIPPAGE_EXTREME",
        "price_impact_label": "PRICE_IMPACT_LOW" if realistic_exit else "PRICE_IMPACT_EXTREME",
        "route_label": "ROUTE_AVAILABLE" if realistic_exit else "ROUTE_NOT_AVAILABLE",
        "quote_age_label": "QUOTE_FRESH",
        "liquidity_drain_label": "NO_LIQUIDITY_DRAIN",
        "realism_gate_label": "REALISM_CONTEXT_ACCEPTABLE" if realistic_exit else "REALISM_CONTEXT_BLOCKED",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
    }


def build_synthetic_trading_flow_context() -> dict:
    return {
        "flow_direction_label": "FLOW_ACCUMULATION",
        "flow_pressure_label": "PRESSURE_STRONG_INFLOW",
        "imbalance_label": "IMBALANCE_BUY_HEAVY",
        "volume_activity_label": "VOLUME_SURGING",
        "tx_activity_label": "TX_ACTIVITY_ELEVATED",
        "wallet_participation_label": "WALLETS_BROAD_PARTICIPATION",
        "flow_memory_gate_label": "FLOW_CONTEXT_ACCEPTABLE",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
    }


def build_synthetic_chart_volatility_context() -> dict:
    return {
        "trend_structure_label": "TREND_UP",
        "volatility_label": "VOLATILITY_ELEVATED",
        "range_behavior_label": "RANGE_BREAKOUT",
        "momentum_label": "MOMENTUM_ACCELERATING_UP",
        "drawdown_recovery_label": "DRAWDOWN_MINOR",
        "candle_path_label": "PATH_STEADY_CLIMB",
        "chart_memory_gate_label": "CHART_CONTEXT_ACCEPTABLE",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
    }


def build_synthetic_micro_event_context() -> dict:
    return {
        "micro_event_state_label": "TRADABLE_MICRO_PUMP",
        "micro_event_move_label": "MOVE_SPIKE_AND_HOLD",
        "micro_exit_realism_label": "MICRO_EXIT_REALISTIC",
        "late_buy_trap_label": "NO_LATE_BUY_TRAP",
        "held_to_15m_result_label": "HELD_TO_15M_CONTINUED",
        "micro_event_payload_quality_label": "MICRO_EVENT_CONTEXT_CLEAN",
        "micro_event_memory_gate_label": "MICRO_EVENT_SUPPORT_EVIDENCE",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
    }


def build_synthetic_market_regime_context() -> dict:
    return {
        "market_regime_label": "RISK_ON",
        "market_payload_quality_label": "MARKET_CONTEXT_CLEAN",
        "market_memory_gate_label": "MARKET_CONTEXT_ACCEPTABLE",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
    }


def build_synthetic_chain_heat_context() -> dict:
    return {
        "chain_heat_label": "SOLANA_WARM",
        "chain_heat_payload_quality_label": "CHAIN_HEAT_CONTEXT_CLEAN",
        "chain_heat_memory_gate_label": "CHAIN_HEAT_CONTEXT_ACCEPTABLE",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
    }


def build_synthetic_clean_memory_episode_payload() -> dict:
    return {
        "window_kind": "WINDOW_15M",
        "outcome_label": "REALISTIC_PAPER_PROFIT",
        "memory_quality_label": "CLEAN_MEMORY",
        "action_lesson_label": "ACTION_BUY_WORKED",
        "fingerprint": {
            "window_kind": "WINDOW_15M",
            "outcome_label": "REALISTIC_PAPER_PROFIT",
            "memory_quality_label": "CLEAN_MEMORY",
            "market_regime_label": "RISK_ON",
            "chain_heat_label": "SOLANA_WARM",
            "safety_status_label": "SAFETY_CLEAN",
            "rug_risk_label": "RUG_RISK_LOW",
            "liquidity_state_label": "LIQUIDITY_USABLE",
            "exit_realism_label": "EXIT_REALISTIC",
            "realism_gate_label": "REALISM_CONTEXT_ACCEPTABLE",
            "flow_direction_label": "FLOW_ACCUMULATION",
            "flow_pressure_label": "PRESSURE_STRONG_INFLOW",
            "trend_structure_label": "TREND_UP",
            "volatility_label": "VOLATILITY_ELEVATED",
            "candle_path_label": "PATH_STEADY_CLIMB",
            "micro_event_state_label": "TRADABLE_MICRO_PUMP",
            "held_to_15m_result_label": "HELD_TO_15M_CONTINUED",
            "token_age_bucket": "NEW_TOKEN",
            "pair_age_bucket": "NEW_PAIR",
            "discovery_label": "DISCOVERY_ACCEPTED",
            "tracking_lane": "TRACK_FAST",
        },
    }


def build_synthetic_paper_decision_payload() -> dict:
    return {
        "token_id": 1,
        "pair_id": 1,
        "token_mint": TOKEN_MINT,
        "pair_address": PAIR_ADDRESS,
        "requested_action_label": "BUY",
        "final_action_label": "BUY",
        "decision_gate_label": "DECISION_ALLOWED",
        "memory_evidence_gate_label": "MEMORY_GATE_CLEAN_MATCH",
        "paper_decision_status_label": "PAPER_DECISION_PROPOSED",
        "paper_only": True,
    }


def clone_fixture(payload: dict | list) -> dict | list:
    return deepcopy(payload)

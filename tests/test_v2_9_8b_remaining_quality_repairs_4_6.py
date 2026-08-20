from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from printer_v1.operator_cli.quality_reporting import (
    build_memory_authority_summary,
    build_window_blocker_summary,
)
from printer_v1.safety.composite import optional_safety_unknown_reasons
from printer_v1.sources.geckoterminal_15m import (
    TRADE_HISTORY_COMPLETE,
    TRADE_HISTORY_TRUNCATED,
    enrich_candidate_15m_trades,
)
from printer_v1.trading_flow.classifier import classify_wallet_participation
from printer_v1.trading_flow.parser import normalize_trading_flow_payload


NOW = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
POOL = "QualityPool111111111111111111111111111111111"
MINT = "QualityMint111111111111111111111111111111111"
ENDPOINT = f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{POOL}/trades"


def _trade(*, seconds_ago: int, kind: str, volume: str, address: str | None) -> dict:
    attrs = {
        "block_timestamp": (NOW - timedelta(seconds=seconds_ago)).isoformat(),
        "kind": kind,
        "volume_in_usd": volume,
        "tx_hash": f"tx-{seconds_ago}-{kind}",
    }
    if address is not None:
        attrs["tx_from_address"] = address
    return {"type": "trade", "attributes": attrs}


def _enrich(trades: list[dict]) -> dict:
    return enrich_candidate_15m_trades(
        {"data": trades},
        pool_address=POOL,
        network="solana",
        endpoint_url=ENDPOINT,
        now=NOW,
    )


def test_complete_gecko_trade_window_adds_observed_wallet_and_split_flow_without_addresses():
    address_a = "ObservedAddressA111111111111111111111111111111"
    address_b = "ObservedAddressB111111111111111111111111111111"
    result = _enrich(
        [
            _trade(seconds_ago=100, kind="buy", volume="12.5", address=address_a),
            _trade(seconds_ago=200, kind="buy", volume="7.5", address=address_a),
            _trade(seconds_ago=300, kind="sell", volume="5", address=address_b),
        ]
    )

    assert result["txns_15m_completeness"] == TRADE_HISTORY_COMPLETE
    assert result["txns_15m"] == 3
    assert result["unique_wallets_15m"] == 2
    assert result["buys_15m"] == 2
    assert result["sells_15m"] == 1
    assert result["buy_volume_15m"] == 20.0
    assert result["sell_volume_15m"] == 5.0
    assert (
        result["wallet_identity_semantics_15m"]
        == "OBSERVED_TX_FROM_ADDRESS_NOT_BENEFICIAL_OWNER"
    )
    assert result["wallet_flow_provenance_15m"]["raw_addresses_persisted"] is False
    serialized = json.dumps(result, sort_keys=True)
    assert address_a not in serialized
    assert address_b not in serialized


def test_wallet_participation_becomes_observed_from_existing_15m_trade_payload_without_claiming_new_wallet_history():
    result = _enrich(
        [
            _trade(seconds_ago=100, kind="buy", volume="12.5", address="A"),
            _trade(seconds_ago=200, kind="buy", volume="7.5", address="A"),
            _trade(seconds_ago=300, kind="sell", volume="5", address="B"),
        ]
    )
    normalized = normalize_trading_flow_payload(
        {
            "token_mint": MINT,
            "pair_address": POOL,
            "captured_at": NOW.isoformat(),
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
            **result,
        },
        NOW,
    )
    assert normalized["unique_wallets_15m"] == 2
    assert normalized["new_wallets_15m"] is None
    assert normalized["repeat_wallets_15m"] is None
    assert classify_wallet_participation(normalized).value != "WALLETS_UNKNOWN"


def test_truncated_or_addressless_trade_history_never_fabricates_wallet_completeness():
    truncated = _enrich(
        [
            _trade(seconds_ago=60 + i, kind="buy", volume="1", address=f"A{i}")
            for i in range(300)
        ]
    )
    assert truncated["txns_15m_completeness"] == TRADE_HISTORY_TRUNCATED
    assert truncated["txns_15m"] is None
    assert truncated["unique_wallets_15m"] is None
    assert truncated["buys_15m"] is None
    assert truncated["sells_15m"] is None
    assert truncated["buy_volume_15m"] is None
    assert truncated["sell_volume_15m"] is None

    addressless = _enrich(
        [
            _trade(seconds_ago=100, kind="buy", volume="10", address=None),
            _trade(seconds_ago=200, kind="sell", volume="4", address=None),
        ]
    )
    assert addressless["txns_15m_completeness"] == TRADE_HISTORY_COMPLETE
    assert addressless["unique_wallets_15m"] is None
    assert addressless["buys_15m"] == 1
    assert addressless["sells_15m"] == 1


def test_optional_safety_unknowns_have_exact_truthful_nonblocking_reasons():
    reasons = optional_safety_unknown_reasons(
        [
            "metadata_mutability_status",
            "liquidity_lock_or_burn_label",
            "known_risk_flag_label",
            "HOLDER_CONDITION_UNAVAILABLE",
        ]
    )
    assert reasons == {
        "metadata_mutability_status": "METADATA_MUTABILITY_SOURCE_UNAVAILABLE",
        "liquidity_lock_or_burn_label": "EXACT_PAIR_LIQUIDITY_LOCK_OR_BURN_UNPROVEN",
        "known_risk_flag_label": "PROVIDER_RISK_FLAGS_UNAVAILABLE",
        "holder_concentration_label": "HOLDER_CONDITION_UNAVAILABLE",
    }


def test_window_blocker_summary_exposes_exact_reasons_without_fabricating_malformed_context():
    windows = [
        {
            "id": 101,
            "window_kind": "WINDOW_15M",
            "memory_status": "PARTIAL_MEMORY",
            "memory_quality_label": "PARTIAL_MEMORY",
            "data_quality_label": "CLEAN_DATA",
            "do_not_train": 0,
            "supporting_context_json": json.dumps(
                {"remaining_blockers": ["MISSING_SAFETY_CONTEXT", "EXIT_QUOTE_UNKNOWN"]}
            ),
        },
        {
            "id": 102,
            "window_kind": "WINDOW_15M",
            "memory_status": "DIRTY_MEMORY",
            "memory_quality_label": "DIRTY_MEMORY",
            "data_quality_label": "DIRTY_DATA",
            "do_not_train": 1,
            "supporting_context_json": "{malformed",
        },
    ]
    summary = build_window_blocker_summary(windows)
    assert summary["blocking_reasons"] == ["MISSING_SAFETY_CONTEXT", "EXIT_QUOTE_UNKNOWN"]
    assert summary["per_window"][0]["remaining_blockers"] == [
        "MISSING_SAFETY_CONTEXT",
        "EXIT_QUOTE_UNKNOWN",
    ]
    assert summary["per_window"][0]["supporting_context_status"] == "PARSED"
    assert summary["per_window"][1]["supporting_context_status"] == "MALFORMED"
    assert summary["per_window"][1]["remaining_blockers"] == []


def test_memory_authority_summary_keeps_parent_partial_and_clean_episode_fingerprint_authoritative_with_retrieval_locked():
    windows = [
        {
            "id": 101,
            "window_kind": "WINDOW_15M",
            "memory_status": "PARTIAL_MEMORY",
            "memory_quality_label": "PARTIAL_MEMORY",
            "data_quality_label": "CLEAN_DATA",
            "do_not_train": 0,
            "supporting_context_json": "{}",
        }
    ]
    promotions = {
        101: {
            "id": 9001,
            "fingerprint_id": 9002,
            "memory_status": "CLEAN_MEMORY",
            "memory_quality_label": "CLEAN_MEMORY",
            "data_quality_label": "CLEAN_DATA",
            "do_not_train": 0,
        }
    }
    summary = build_memory_authority_summary(windows, promotions)
    assert summary["retrieval_status"] == "LOCKED"
    assert summary["authority_rule"] == (
        "PARENT_WINDOW_PROVENANCE_ONLY;CLEAN_EPISODE_AND_FINGERPRINT_AUTHORITATIVE_WHEN_PROMOTED"
    )
    assert summary["authoritative_clean_artifact_count"] == 1
    row = summary["per_window"][0]
    assert row["parent_memory_status"] == "PARTIAL_MEMORY"
    assert row["parent_memory_quality_label"] == "PARTIAL_MEMORY"
    assert row["parent_status_is_authoritative_clean_object"] is False
    assert row["authoritative_clean_artifact"] == "EPISODE_AND_FINGERPRINT"
    assert row["episode_id"] == 9001
    assert row["fingerprint_id"] == 9002

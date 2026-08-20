from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.discovery.selection_batch import build_batch_item
from printer_v1.operator_cli.commands import enrich_eligible_geckoterminal_candidate_15m
from printer_v1.operator_cli.e2m_snapshot_persistence import _insert_snapshot
from printer_v1.operator_cli.quality_reporting import (
    build_memory_authority_summary,
    build_window_blocker_summary,
)
from printer_v1.safety.composite import optional_safety_unknown_reasons
from printer_v1.sources.geckoterminal_15m import (
    GECKOTERMINAL_OHLCV_REQUEST_KIND,
    GECKOTERMINAL_POOL_TRADES_REQUEST_KIND,
    GT15M_CANDLE_SECONDS,
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
ADDR_A = "DISTINCTIVE_TX_FROM_ADDRESS_REPAIR4_AAA_111111111111"
ADDR_B = "DISTINCTIVE_TX_FROM_ADDRESS_REPAIR4_BBB_222222222222"


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


def _transport(payload: dict):
    def transport(context):
        del context
        return payload

    return transport


def _aligned_ohlcv_and_trades(*, trades: list[dict]) -> tuple[dict, dict]:
    """Build OHLCV + trades sharing one completed 15m candle window."""
    now = datetime.now(timezone.utc)
    start = int(now.timestamp() // GT15M_CANDLE_SECONDS) * GT15M_CANDLE_SECONDS
    start -= GT15M_CANDLE_SECONDS
    candle_end = start + GT15M_CANDLE_SECONDS
    ohlcv = {
        "data": {
            "attributes": {
                "ohlcv_list": [[start, 2.0, 3.2, 1.8, 3.0, 12000.0]],
            }
        }
    }
    trade_rows = []
    for index, trade in enumerate(trades):
        attrs = dict(trade)
        seconds_before_end = int(attrs.pop("seconds_before_end"))
        trade_rows.append(
            {
                "type": "trade",
                "attributes": {
                    "block_timestamp": datetime.fromtimestamp(
                        candle_end - seconds_before_end, timezone.utc
                    ).isoformat(),
                    **attrs,
                },
            }
        )
    return ohlcv, {"data": trade_rows}


def _base_candidate() -> dict:
    return {
        "token_mint": MINT,
        "pair_address": POOL,
        "chain": "solana",
        "source_name": "geckoterminal",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "price_usd": 3.0,
        "liquidity_usd": 10000.0,
        "volume_5m": 3000.0,
        "txns_5m": 20,
    }


def _assert_no_raw_addresses(*blobs: str) -> None:
    joined = "\n".join(blobs)
    assert ADDR_A not in joined
    assert ADDR_B not in joined
    # Exact JSON key only; allow the durable marker tx_from_address_redacted.
    assert '"tx_from_address":' not in joined


def test_governed_db_persistence_redacts_tx_from_address_while_keeping_aggregates(
    tmp_path: Path,
):
    db_path = tmp_path / "repair4-address-redaction.sqlite3"
    apply_migrations(db_path)
    candidate = _base_candidate()
    ohlcv, trades = _aligned_ohlcv_and_trades(
        trades=[
            {
                "seconds_before_end": 100,
                "kind": "buy",
                "volume_in_usd": "12.5",
                "tx_from_address": ADDR_A,
                "tx_hash": "tx-a1",
            },
            {
                "seconds_before_end": 200,
                "kind": "buy",
                "volume_in_usd": "7.5",
                "tx_from_address": ADDR_A,
                "tx_hash": "tx-a2",
            },
            {
                "seconds_before_end": 300,
                "kind": "sell",
                "volume_in_usd": "5",
                "tx_from_address": ADDR_B,
                "tx_hash": "tx-b1",
            },
        ]
    )
    report = enrich_eligible_geckoterminal_candidate_15m(
        db_path,
        candidate,
        timeout_seconds=5.0,
        request_key_prefix="repair4-complete",
        transports={
            GECKOTERMINAL_OHLCV_REQUEST_KIND: _transport(ohlcv),
            GECKOTERMINAL_POOL_TRADES_REQUEST_KIND: _transport(trades),
        },
    )
    assert report["status"] == "EVIDENCE_APPLIED"
    assert report["requests_attempted"] == 2
    assert candidate["txns_15m_completeness"] == TRADE_HISTORY_COMPLETE
    assert candidate["txns_15m"] == 3
    assert candidate["unique_wallets_15m"] == 2
    assert candidate["buys_15m"] == 2
    assert candidate["sells_15m"] == 1
    assert candidate["buy_volume_15m"] == 20.0
    assert candidate["sell_volume_15m"] == 5.0
    assert candidate.get("new_wallets_15m") is None
    assert candidate.get("repeat_wallets_15m") is None
    assert (
        candidate["wallet_identity_semantics_15m"]
        == "OBSERVED_TX_FROM_ADDRESS_NOT_BENEFICIAL_OWNER"
    )
    assert candidate["wallet_flow_provenance_15m"]["raw_addresses_persisted"] is False
    assert candidate["wallet_flow_provenance_15m"]["new_wallet_history_claimed"] is False
    assert candidate["wallet_flow_provenance_15m"]["beneficial_owner_claimed"] is False

    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_source_requests"
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_source_responses"
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs"
        ).fetchone()[0] == 0
        response_blobs = [
            str(row[0] or "")
            for row in connection.execute(
                "SELECT normalized_payload_json FROM printer_source_responses"
            ).fetchall()
        ]
        assert any("tx_from_address_redacted" in blob for blob in response_blobs)
        _assert_no_raw_addresses(*response_blobs)

        connection.execute(
            "INSERT INTO printer_tokens "
            "(token_mint, chain, symbol, name, first_seen_at, created_at) "
            "VALUES (?, 'solana', 'Q', 'Quality', ?, ?)",
            (MINT, candidate["captured_at"], candidate["captured_at"]),
        )
        token_id = int(connection.execute("SELECT id FROM printer_tokens").fetchone()[0])
        connection.execute(
            "INSERT INTO printer_pairs "
            "(token_id, pair_address, dex, quote_token_mint, first_seen_at, created_at) "
            "VALUES (?, ?, 'geckoterminal', 'So11111111111111111111111111111111111111112', ?, ?)",
            (token_id, POOL, candidate["captured_at"], candidate["captured_at"]),
        )
        pair_id = int(connection.execute("SELECT id FROM printer_pairs").fetchone()[0])
        response_id = int(
            connection.execute(
                "SELECT id FROM printer_source_responses ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]
        )
        request_id = int(
            connection.execute(
                "SELECT source_request_id FROM printer_source_responses WHERE id=?",
                (response_id,),
            ).fetchone()[0]
        )
        snapshot_id = _insert_snapshot(
            connection,
            token_id,
            pair_id,
            candidate,
            request_id,
            response_id,
            candidate["captured_at"],
            candidate["captured_at"],
            "TRACK_NORMAL",
        )
        snapshot_blob = str(
            connection.execute(
                "SELECT normalized_snapshot_payload_json "
                "FROM printer_token_snapshots WHERE id=?",
                (snapshot_id,),
            ).fetchone()[0]
        )
        snapshot_payload = json.loads(snapshot_blob)
        assert snapshot_payload["unique_wallets_15m"] == 2
        assert snapshot_payload["buys_15m"] == 2
        assert snapshot_payload["sells_15m"] == 1
        assert snapshot_payload["buy_volume_15m"] == 20.0
        assert snapshot_payload["sell_volume_15m"] == 5.0
        _assert_no_raw_addresses(snapshot_blob)

    batch_item = build_batch_item(candidate, item_status="SELECTED")
    metadata_blob = str(batch_item["candidate_metadata_json"])
    metadata = json.loads(metadata_blob)
    assert metadata["unique_wallets_15m"] == 2
    assert metadata["buys_15m"] == 2
    _assert_no_raw_addresses(metadata_blob, json.dumps(candidate, sort_keys=True))

    report_artifact = {
        "candidate": candidate,
        "evidence": report["evidence"],
        "window_blocker_summary": build_window_blocker_summary(
            [
                {
                    "id": 1,
                    "window_kind": "WINDOW_15M",
                    "memory_status": "PARTIAL_MEMORY",
                    "memory_quality_label": "PARTIAL_MEMORY",
                    "data_quality_label": "CLEAN_DATA",
                    "do_not_train": 0,
                    "supporting_context_json": json.dumps(
                        {"remaining_blockers": ["EXIT_QUOTE_UNKNOWN"]}
                    ),
                }
            ]
        ),
        "memory_authority": build_memory_authority_summary(
            [
                {
                    "id": 1,
                    "window_kind": "WINDOW_15M",
                    "memory_status": "PARTIAL_MEMORY",
                    "memory_quality_label": "PARTIAL_MEMORY",
                    "data_quality_label": "CLEAN_DATA",
                    "do_not_train": 0,
                    "supporting_context_json": "{}",
                }
            ],
            {},
        ),
    }
    report_blob = json.dumps(report_artifact, sort_keys=True)
    assert report_artifact["memory_authority"]["retrieval_status"] == "LOCKED"
    _assert_no_raw_addresses(report_blob)

    # Truncated history remains honest and still redacts addresses.
    truncated_candidate = _base_candidate()
    truncated_trades = {
        "data": [
            {
                "attributes": {
                    "block_timestamp": (
                        datetime.now(timezone.utc) - timedelta(seconds=60 + i)
                    ).isoformat(),
                    "kind": "buy",
                    "volume_in_usd": "1",
                    "tx_from_address": ADDR_A if i % 2 == 0 else ADDR_B,
                    "tx_hash": f"tx-trunc-{i}",
                }
            }
            for i in range(300)
        ]
    }
    truncated_report = enrich_eligible_geckoterminal_candidate_15m(
        db_path,
        truncated_candidate,
        timeout_seconds=5.0,
        request_key_prefix="repair4-truncated",
        transports={
            GECKOTERMINAL_OHLCV_REQUEST_KIND: _transport(ohlcv),
            GECKOTERMINAL_POOL_TRADES_REQUEST_KIND: _transport(truncated_trades),
        },
    )
    assert truncated_report["requests_attempted"] == 2
    assert truncated_candidate["txns_15m_completeness"] == TRADE_HISTORY_TRUNCATED
    assert truncated_candidate["txns_15m"] is None
    assert truncated_candidate["unique_wallets_15m"] is None
    assert truncated_candidate["buys_15m"] is None
    assert truncated_candidate["sells_15m"] is None
    assert truncated_candidate["buy_volume_15m"] is None
    assert truncated_candidate["sell_volume_15m"] is None

    # Address-incomplete complete windows keep buy/sell counts, not wallet completeness.
    addressless_candidate = _base_candidate()
    addressless_ohlcv, addressless_trades = _aligned_ohlcv_and_trades(
        trades=[
            {
                "seconds_before_end": 100,
                "kind": "buy",
                "volume_in_usd": "10",
                "tx_hash": "tx-none-1",
            },
            {
                "seconds_before_end": 200,
                "kind": "sell",
                "volume_in_usd": "4",
                "tx_hash": "tx-none-2",
            },
        ]
    )
    addressless_report = enrich_eligible_geckoterminal_candidate_15m(
        db_path,
        addressless_candidate,
        timeout_seconds=5.0,
        request_key_prefix="repair4-addressless",
        transports={
            GECKOTERMINAL_OHLCV_REQUEST_KIND: _transport(addressless_ohlcv),
            GECKOTERMINAL_POOL_TRADES_REQUEST_KIND: _transport(addressless_trades),
        },
    )
    assert addressless_report["requests_attempted"] == 2
    assert addressless_candidate["txns_15m_completeness"] == TRADE_HISTORY_COMPLETE
    assert addressless_candidate["unique_wallets_15m"] is None
    assert addressless_candidate["buys_15m"] == 1
    assert addressless_candidate["sells_15m"] == 1

    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_source_requests"
        ).fetchone()[0] == 6
        all_response_blobs = [
            str(row[0] or "")
            for row in connection.execute(
                "SELECT normalized_payload_json FROM printer_source_responses"
            ).fetchall()
        ]
        _assert_no_raw_addresses(*all_response_blobs)
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs"
        ).fetchone()[0] == 0

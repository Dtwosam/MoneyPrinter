"""Production-path proof for classifier-generated Group A quota composition."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import pathlib
import sqlite3
import tempfile

from printer_v1.db.migrate import apply_migrations
from printer_v1.discovery.selection_batch import (
    BUCKET_A1,
    BUCKET_A3,
    BUCKET_B1,
    BUCKET_B2,
    BUCKET_D1,
    build_classifier_quota_view,
    validate_batch_quota,
)
from printer_v1.operator_cli.commands import build_discover_candidates_once_payload
from printer_v1.sources.solana_rpc_token_age import fixture_t3_success_transport


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
A3_MINT = "GroupA3Mint111111111111111111111111111111111"


def _pair(index: int, *, kind: str) -> dict:
    mint = A3_MINT if kind == "a3" else f"GroupMint{index}11111111111111111111111111111111"
    liquidity = 8_000 if kind in {"a3", "a1"} else 3_000
    volume_5m = 2_500 if kind in {"a3", "a1"} else 100
    txns_5m = {"buys": 8, "sells": 6} if kind in {"a3", "a1"} else {"buys": 1, "sells": 1}
    volume_1h = 500
    txns_1h = {"buys": 12, "sells": 8}
    price_change_1h = {
        "a3": -5,
        "a1": 8,
        "b2": -5,
        "b1": 5,
        "b3": 0,
    }.get(kind, 0)
    if kind == "b3":
        txns_5m = {"buys": 7, "sells": 5}
    if kind == "dead":
        liquidity = 100
        volume_5m = 0
        volume_1h = 0
        txns_5m = {"buys": 0, "sells": 0}
        txns_1h = {"buys": 0, "sells": 0}

    return {
        "chainId": "solana",
        "pairAddress": f"GroupPair{index}11111111111111111111111111111111",
        "baseToken": {"address": mint, "symbol": f"G{index}", "name": f"Group {index}"},
        "quoteToken": {"address": "So11111111111111111111111111111111111111112"},
        "dexId": "raydium",
        "priceUsd": "0.001",
        "liquidity": {"usd": liquidity},
        "volume": {
            "m5": volume_5m,
            "h1": volume_1h,
            "h24": 0 if kind == "dead" else 10_000,
        },
        "txns": {
            "m5": txns_5m,
            "h1": txns_1h,
            "h24": {"buys": 0, "sells": 0} if kind == "dead" else {"buys": 60, "sells": 40},
        },
        "priceChange": {"m5": 2, "h1": price_change_1h},
    }


def _discovery_transport(_context):
    return {
        "pairs": [
            _pair(1, kind="a3"),
            _pair(2, kind="a1"),
            _pair(3, kind="b2"),
            _pair(4, kind="b1"),
            _pair(5, kind="b3"),
            _pair(6, kind="dead"),
        ]
    }


def _t3_payload() -> dict:
    captured = datetime.now(timezone.utc)
    created = captured - timedelta(hours=2)
    return {
        "t3_status": "success",
        "token_mint": A3_MINT,
        "captured_at": captured.isoformat(),
        "token_created_at": created.isoformat(),
        "token_age_seconds": 7_200,
        "token_age_evidence_tier": "T3",
        "t3_requested_mint": A3_MINT,
        "t3_rpc_host_redacted": "api.mainnet-beta.solana.com",
        "t3_rpc_methods_attempted": ["getAccountInfo", "getSignaturesForAddress", "getTransaction"],
        "t3_request_ids": [1, 2, 3],
        "t3_pages_fetched": 1,
        "t3_signatures_inspected": 1,
        "t3_accepted_signature": "group-a-init-signature",
        "t3_accepted_slot": 123,
        "t3_block_time_raw": int(created.timestamp()),
        "t3_block_time_source": "getTransaction",
        "t3_instruction_type": "initializeMint2",
        "t3_token_program": "token_2022",
        "t3_derived_token_created_at": created.isoformat(),
        "t3_derived_token_age_seconds": 7_200,
        "t3_captured_at": captured.isoformat(),
        "t3_commitment": "finalized",
        "t3_finality_status": "finalized",
    }


def _args(db_path: pathlib.Path) -> argparse.Namespace:
    return argparse.Namespace(
        db_path=str(db_path),
        project_root=str(PROJECT_ROOT),
        format="json",
        no_color=True,
        operator_approved=True,
        chain="solana",
        max_candidates=10,
        max_source_requests=1,
        query="group-a-proof",
        timeout_seconds=5.0,
        source_name="dexscreener",
        request_kind="token_discovery",
        request_key="group-a-quota-proof",
        enrich_15m_market_evidence=False,
        enrich_t3_token_age=True,
        t3_solana_rpc_url=None,
    )


def test_manual_primary_bucket_marker_is_ignored():
    candidate = {
        "token_mint": "ManualMint",
        "pair_address": "ManualPair",
        "source_response_id": 1,
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "tracking_lane": "TRACK_NORMAL",
        "primary_bucket": BUCKET_A3,
        "liquidity_usd": 3_000,
        "volume_5m": 100,
        "txns_5m": 2,
        "volume_1h": 500,
        "txns_1h": 20,
        "volume_24h": 10_000,
        "txns_24h": 100,
        "price_change_1h": 5,
    }
    report = build_classifier_quota_view([candidate], [], max_items=1)
    assert report["selected_candidates"][0]["primary_bucket"] == BUCKET_B1


def test_group_a_total_and_winner_caps_remain_enforced():
    items = [
        {"token_mint": f"M{i}", "pair_address": f"P{i}", "tracking_lane": "TRACK_FAST", "primary_bucket": bucket}
        for i, bucket in enumerate((BUCKET_A1, BUCKET_A1, BUCKET_A1, BUCKET_A3, BUCKET_A3), 1)
    ]
    items.append({"token_mint": "MD", "pair_address": "PD", "tracking_lane": "WATCH_ONLY", "primary_bucket": BUCKET_D1})
    ok, violations = validate_batch_quota(items)
    assert not ok
    assert "WINNER_CAP_EXCEEDED_A1_MAX_2" in violations
    assert "GROUP_A_TOTAL_CAP_EXCEEDED_MAX_4" in violations
    assert "GROUP_A_SHARE_EXCEEDED_MAX_40_PERCENT" in violations


def test_six_plus_group_a_group_b_and_decay_minimums_remain_enforced():
    no_group_a = [
        {"token_mint": f"B{i}", "pair_address": f"BP{i}", "tracking_lane": "TRACK_NORMAL", "primary_bucket": BUCKET_B1}
        for i in range(5)
    ]
    no_group_a.append({"token_mint": "D", "pair_address": "DP", "tracking_lane": "WATCH_ONLY", "primary_bucket": BUCKET_D1})
    ok, violations = validate_batch_quota(no_group_a)
    assert not ok
    assert "MISSING_GROUP_A_REQUIRED_FOR_5PLUS_BATCH" in violations
    assert "MISSING_GROUP_B_DECAY_REQUIRED_FOR_6PLUS_BATCH" in violations

    too_little_group_b = [
        {"token_mint": "A", "pair_address": "AP", "tracking_lane": "TRACK_FAST", "primary_bucket": BUCKET_A3},
        {"token_mint": "B", "pair_address": "BP", "tracking_lane": "TRACK_NORMAL", "primary_bucket": BUCKET_B2},
    ]
    too_little_group_b.extend(
        {"token_mint": f"C{i}", "pair_address": f"CP{i}", "tracking_lane": "TRACK_NORMAL", "primary_bucket": "C1"}
        for i in range(3)
    )
    too_little_group_b.append(
        {"token_mint": "D", "pair_address": "DP", "tracking_lane": "WATCH_ONLY", "primary_bucket": BUCKET_D1}
    )
    ok, violations = validate_batch_quota(too_little_group_b)
    assert not ok
    assert "GROUP_B_SHARE_BELOW_MIN_30_PERCENT" in violations


def test_six_candidate_production_path_builds_quota_valid_classifier_batch():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = pathlib.Path(tmp) / "group-a-proof.sqlite3"
        apply_migrations(db_path)
        payload = build_discover_candidates_once_payload(
            _args(db_path),
            transport=_discovery_transport,
            enrichment_transports={"t3_token_age": fixture_t3_success_transport(_t3_payload())},
        )

        report = payload["group_a_quota_report"]
        assert payload["t3_token_age_enrichment_report"]["bucket_after_enrichment"] == BUCKET_A3
        assert report["quota_ok"] is True
        assert report["quota_violations"] == []
        assert report["selected_count"] == 6
        assert report["selected_active_tracking_count"] == 5
        assert report["selected_audit_only_count"] == 1
        assert report["selected_by_bucket"] == {
            "A1": 1,
            "A3": 1,
            "B1": 1,
            "B2": 1,
            "B3": 1,
            "D1": 1,
        }

        selected_a3 = next(item for item in report["selected_candidates"] if item["primary_bucket"] == BUCKET_A3)
        assert selected_a3["token_age_evidence_tier"] == "T3"
        assert selected_a3["t3_source_response_id"] is not None
        selected_d1 = next(item for item in report["selected_candidates"] if item["primary_bucket"] == BUCKET_D1)
        assert selected_d1["candidate_kind"] == "AUDIT_ONLY"
        assert selected_d1["tracking_lane"] == "WATCH_ONLY"

        connection = sqlite3.connect(db_path)
        dead_mint = _pair(6, kind="dead")["baseToken"]["address"]
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_tokens WHERE token_mint = ?", (dead_mint,)
        ).fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM printer_selection_rotation_state").fetchone()[0] == 0
        for table in (
            "printer_memory_windows",
            "printer_memory_retrieval_queries",
            "printer_memory_retrieval_matches",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
            "printer_paper_trade_audits",
        ):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
        connection.close()

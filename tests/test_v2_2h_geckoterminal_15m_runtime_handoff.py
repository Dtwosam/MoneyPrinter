from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.discovery.selection_batch import build_batch_item
from printer_v1.operator_cli.commands import (
    build_discover_candidates_once_payload,
    enrich_eligible_geckoterminal_candidate_15m,
)
from printer_v1.snapshots.recorder import record_token_snapshot
from printer_v1.sources.geckoterminal import (
    build_geckoterminal_15m_transport,
    normalize_geckoterminal_payload,
)
from printer_v1.sources.geckoterminal_15m import (
    GECKOTERMINAL_OHLCV_REQUEST_KIND,
    GECKOTERMINAL_POOL_TRADES_REQUEST_KIND,
    TRADE_HISTORY_COMPLETE,
    TRADE_HISTORY_TRUNCATED,
)


POOL = "RuntimePool1111111111111111111111111111111111"
MINT = "RuntimeMint1111111111111111111111111111111111"


def _ohlcv_payload() -> dict:
    now = datetime.now(timezone.utc)
    start = int((now - timedelta(minutes=30)).timestamp())
    return {"data": {"attributes": {"ohlcv_list": [[start, 2.0, 3.2, 1.8, 3.0, 12000.0]]}}}


def _trades_payload(count: int = 2) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "data": [
            {"attributes": {"block_timestamp": (
                now - timedelta(minutes=16, seconds=i)
            ).isoformat()}}
            for i in range(count)
        ]
    }


def _transport(payload: dict):
    def transport(context):
        del context
        return payload
    return transport


def _candidate() -> dict:
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


def _pool_discovery_payload() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "data": [{
            "id": f"solana_{POOL}",
            "attributes": {
                "address": POOL,
                "name": "Runtime / SOL",
                "pool_created_at": now,
                "base_token_price_usd": "3.0",
                "reserve_in_usd": 10000.0,
                "volume_usd": {"m5": 3000.0, "h1": 9000.0, "h24": 25000.0},
                "transactions": {"m5": {"buys": 12, "sells": 8}},
                "price_change_percentage": {"m5": 10.0, "h1": 20.0, "h24": 30.0},
            },
            "relationships": {
                "base_token": {"data": {"id": f"solana_{MINT}"}},
                "network": {"data": {"id": "solana"}},
            },
        }]
    }


def test_pool_bound_endpoint_construction_never_falls_back():
    ohlcv_url, _ = build_geckoterminal_15m_transport(
        request_kind=GECKOTERMINAL_OHLCV_REQUEST_KIND,
        pool_address=POOL,
    )
    trades_url, _ = build_geckoterminal_15m_transport(
        request_kind=GECKOTERMINAL_POOL_TRADES_REQUEST_KIND,
        pool_address=POOL,
    )
    assert f"/pools/{POOL}/ohlcv/minute" in ohlcv_url
    assert f"/pools/{POOL}/trades" in trades_url
    assert "new_pools" not in ohlcv_url + trades_url
    assert "trending" not in ohlcv_url + trades_url


def test_request_specific_normalizers_and_pool_match():
    payload = {
        **_ohlcv_payload(),
        "_requested_pool_address": POOL,
        "_requested_network": "solana",
        "_requested_endpoint": f"https://example.test/pools/{POOL}/ohlcv/minute",
    }
    result = normalize_geckoterminal_payload(
        payload,
        request_kind=GECKOTERMINAL_OHLCV_REQUEST_KIND,
        expected_pool_address=POOL,
    )
    assert result.source_status.value == "COMPLETE"
    assert result.normalized_payload["pool_address"] == POOL
    assert "provider_payload" in result.normalized_payload

    mismatch = normalize_geckoterminal_payload(
        payload,
        request_kind=GECKOTERMINAL_OHLCV_REQUEST_KIND,
        expected_pool_address="DifferentPool",
    )
    assert mismatch.source_status.value == "FAILED"
    assert mismatch.failure_type == "geckoterminal_15m_pool_mismatch"


def test_malformed_stale_and_failed_responses_fail_closed(tmp_path):
    malformed = normalize_geckoterminal_payload(
        {
            "data": {},
            "_requested_pool_address": POOL,
            "_requested_network": "solana",
            "_requested_endpoint": f"https://example.test/pools/{POOL}/ohlcv/minute",
        },
        request_kind=GECKOTERMINAL_OHLCV_REQUEST_KIND,
        expected_pool_address=POOL,
    )
    assert malformed.source_status.value == "FAILED"

    db_path = tmp_path / "fail-closed.sqlite3"
    apply_migrations(db_path)
    candidate = _candidate()
    report = enrich_eligible_geckoterminal_candidate_15m(
        db_path,
        candidate,
        timeout_seconds=5.0,
        request_key_prefix="fail-closed",
        transports={
            GECKOTERMINAL_OHLCV_REQUEST_KIND: _transport({**_ohlcv_payload(), "fixture_stale": True}),
            GECKOTERMINAL_POOL_TRADES_REQUEST_KIND: _transport({
                "fixture_status": "failure",
                "failure_type": "fixture_failure",
                "failure_message": "bounded fixture failure",
            }),
        },
    )
    assert report["status"] == "NO_VALID_EVIDENCE"
    assert report["requests_attempted"] == 2
    assert "price_change_15m" not in candidate
    assert "volume_15m" not in candidate
    assert "txns_15m" not in candidate


def test_governed_helper_merges_evidence_and_records_exactly_two_requests(tmp_path):
    db_path = tmp_path / "handoff.sqlite3"
    apply_migrations(db_path)
    candidate = _candidate()
    report = enrich_eligible_geckoterminal_candidate_15m(
        db_path,
        candidate,
        timeout_seconds=5.0,
        request_key_prefix="runtime-handoff-test",
        transports={
            GECKOTERMINAL_OHLCV_REQUEST_KIND: _transport(_ohlcv_payload()),
            GECKOTERMINAL_POOL_TRADES_REQUEST_KIND: _transport(_trades_payload()),
        },
    )
    assert report["status"] == "EVIDENCE_APPLIED"
    assert report["requests_attempted"] == 2
    assert candidate["price_change_15m"] == 50.0
    assert candidate["volume_15m"] == 12000.0
    assert candidate["txns_15m"] == 2
    assert candidate["txns_15m_completeness"] == TRADE_HISTORY_COMPLETE
    for key in ("price_change_15m_provenance", "volume_15m_provenance", "txns_15m_provenance"):
        assert candidate[key]["pool_address"] == POOL
        assert candidate[key]["source_request_id"] is not None
        assert candidate[key]["source_response_id"] is not None
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM printer_source_responses").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM printer_source_failures").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0] == 0


def test_capped_trades_remain_null_and_ineligible_candidate_makes_no_request(tmp_path):
    db_path = tmp_path / "closed.sqlite3"
    apply_migrations(db_path)
    ineligible = {**_candidate(), "chain": "ethereum"}
    report = enrich_eligible_geckoterminal_candidate_15m(
        db_path,
        ineligible,
        timeout_seconds=5.0,
        request_key_prefix="ineligible",
    )
    assert report["requests_attempted"] == 0

    recent = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    capped = {"data": [{"attributes": {"block_timestamp": recent}} for _ in range(300)]}
    candidate = _candidate()
    report = enrich_eligible_geckoterminal_candidate_15m(
        db_path,
        candidate,
        timeout_seconds=5.0,
        request_key_prefix="capped",
        transports={
            GECKOTERMINAL_OHLCV_REQUEST_KIND: _transport(_ohlcv_payload()),
            GECKOTERMINAL_POOL_TRADES_REQUEST_KIND: _transport(capped),
        },
    )
    assert report["requests_attempted"] == 2
    assert candidate["txns_15m"] is None
    assert candidate["txns_15m_completeness"] == TRADE_HISTORY_TRUNCATED


def test_runtime_discovery_handoff_selection_metadata_and_snapshot(tmp_path):
    db_path = tmp_path / "production-flow.sqlite3"
    apply_migrations(db_path)
    args = argparse.Namespace(
        project_root=str(Path(__file__).resolve().parents[1]),
        format="json",
        no_color=True,
        operator_approved=True,
        chain="solana",
        max_candidates=1,
        query="pump",
        timeout_seconds=5.0,
        source_name="geckoterminal",
        request_kind="geckoterminal_new_pool_discovery",
        request_key="production-flow",
        db_path=str(db_path),
        max_source_requests=1,
        enrich_15m_market_evidence=True,
    )
    payload = build_discover_candidates_once_payload(
        args,
        transport=_transport(_pool_discovery_payload()),
        enrichment_transports={
            GECKOTERMINAL_OHLCV_REQUEST_KIND: _transport(_ohlcv_payload()),
            GECKOTERMINAL_POOL_TRADES_REQUEST_KIND: _transport(_trades_payload()),
        },
    )
    assert payload["market_15m_enrichment_report"]["requests_attempted"] == 2
    assert payload["accepted_candidates"][0]["price_change_15m"] == 50.0
    assert payload["accepted_candidates"][0]["volume_15m"] == 12000.0

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT token_id,pair_id,normalized_candidate_payload_json "
            "FROM printer_discovery_candidates ORDER BY id DESC LIMIT 1"
        ).fetchone()
        stored = json.loads(row["normalized_candidate_payload_json"])
        assert stored["price_change_15m"] == 50.0
        assert stored["volume_15m"] == 12000.0
        assert stored["txns_15m"] == 2
        batch_item = build_batch_item(stored, item_status="SELECTED")
        metadata = json.loads(batch_item["candidate_metadata_json"])
        assert metadata["price_change_15m_provenance"]["pool_address"] == POOL
        snapshot_payload = {
            **stored,
            "token_id": row["token_id"],
            "pair_id": row["pair_id"],
            "tracking_lane": "TRACK_FAST",
            "snapshot_mode": "NORMAL_MODE",
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
        }
        created, snapshot_id = record_token_snapshot(connection, snapshot_payload)
        assert created is True
        snapshot = connection.execute(
            "SELECT price_change_15m,volume_15m,txns_15m,normalized_snapshot_payload_json "
            "FROM printer_token_snapshots WHERE id=?",
            (snapshot_id,),
        ).fetchone()
        assert tuple(snapshot[:3]) == (50.0, 12000.0, 2)
        normalized_snapshot = json.loads(snapshot["normalized_snapshot_payload_json"])
        assert normalized_snapshot["txns_15m_completeness"] == TRADE_HISTORY_COMPLETE
        assert connection.execute("SELECT COUNT(*) FROM printer_memory_windows").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM printer_memory_retrieval_matches").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM printer_paper_positions").fetchone()[0] == 0

"""Focused A4 FAILED_PUMP prior/current evidence handoff proof."""

from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys
import tempfile

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from printer_v1.db import apply_migrations
from printer_v1.discovery.selection_batch import (
    A4_EVIDENCE_VALID,
    BUCKET_A1,
    BUCKET_A4,
    ITEM_STATUS_SELECTED,
    assign_bucket,
    build_batch_item,
    derive_asset_class,
    evaluate_failed_pump_evidence,
    persist_selection_batch,
)
from printer_v1.operator_cli.commands import (
    _select_discovery_candidates,
    build_discover_candidates_once_payload,
)


MINT = "A4FixtureMint111111111111111111111111111111"
PAIR = "A4FixturePair111111111111111111111111111111"


def _evidence_pair() -> tuple[dict, dict]:
    prior = {
        "token_mint": MINT,
        "pair_address": PAIR,
        "primary_bucket": BUCKET_A1,
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "source_request_id": 10,
        "source_response_id": 20,
        "discovery_candidate_id": 30,
        "observed_at": "2026-07-12T10:00:00+00:00",
    }
    current = {
        "token_mint": MINT,
        "pair_address": PAIR,
        "liquidity_usd": 2_000.0,
        "volume_5m": 50.0,
        "txns_5m": 2,
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "source_request_id": 11,
        "source_response_id": 21,
        "observed_at": "2026-07-12T10:15:00+00:00",
    }
    return current, prior


def _transport(*, fast: bool):
    def transport(context):
        del context
        return {
            "pairs": [{
                "chainId": "solana",
                "pairAddress": PAIR,
                "baseToken": {"address": MINT, "symbol": "A4F", "name": "A4 Fixture"},
                "quoteToken": {"address": "So11111111111111111111111111111111111111112"},
                "dexId": "raydium",
                "priceUsd": "0.001",
                "liquidity": {"usd": 8_000 if fast else 2_000},
                "volume": {
                    "m5": 2_500 if fast else 50,
                    "h1": 12_000 if fast else 500,
                    "h24": 50_000 if fast else 10_000,
                },
                "txns": {
                    "m5": {"buys": 8, "sells": 6} if fast else {"buys": 1, "sells": 1},
                    "h1": {"buys": 40, "sells": 25} if fast else {"buys": 12, "sells": 8},
                    "h24": {"buys": 200, "sells": 150} if fast else {"buys": 60, "sells": 40},
                },
                "priceChange": {"m5": 12 if fast else -4, "h1": 25 if fast else -18},
            }]
        }
    return transport


def _args(db_path: pathlib.Path, request_key: str) -> argparse.Namespace:
    return argparse.Namespace(
        db_path=str(db_path),
        project_root=str(PROJECT_ROOT),
        format="json",
        no_color=True,
        operator_approved=True,
        chain="solana",
        max_candidates=1,
        max_source_requests=1,
        query="a4-fixture",
        timeout_seconds=5.0,
        source_name="dexscreener",
        request_kind="token_discovery",
        request_key=request_key,
        enrich_t3_token_age=False,
        enrich_15m_market_evidence=False,
    )


def test_valid_prior_current_evidence_qualifies_categorically():
    current, prior = _evidence_pair()
    result = evaluate_failed_pump_evidence(current, prior)
    assert result == {
        "qualifies": True,
        "reason": "prior_a_tier_current_not_fast_liquidity_retained",
        "bucket_id": BUCKET_A4,
        "bucket_name": "FAILED_PUMP",
    }


def test_missing_stale_mismatched_or_incomplete_evidence_fails_closed():
    current, prior = _evidence_pair()
    assert evaluate_failed_pump_evidence(current, None)["reason"] == "prior_evidence_missing"

    stale = {**prior, "source_status": "STALE"}
    assert evaluate_failed_pump_evidence(current, stale)["reason"] == "prior_source_not_complete"

    failed_current = {**current, "source_status": "FAILED"}
    assert evaluate_failed_pump_evidence(failed_current, prior)["reason"] == "current_source_not_complete"

    dirty = {**prior, "data_quality_label": "DIRTY_DATA"}
    assert evaluate_failed_pump_evidence(current, dirty)["reason"] == "prior_data_not_clean"

    wrong_mint = {**prior, "token_mint": "DifferentMint"}
    assert evaluate_failed_pump_evidence(current, wrong_mint)["reason"] == "token_mint_mismatch"

    wrong_pair = {**prior, "pair_address": "DifferentPair"}
    assert evaluate_failed_pump_evidence(current, wrong_pair)["reason"] == "pair_address_mismatch"

    incomplete = {**prior, "source_response_id": None}
    assert evaluate_failed_pump_evidence(current, incomplete)["reason"] == "prior_source_provenance_incomplete"


def test_same_response_or_non_newer_evidence_fails_closed():
    current, prior = _evidence_pair()
    assert evaluate_failed_pump_evidence(
        {**current, "source_response_id": prior["source_response_id"]}, prior
    )["reason"] == "same_source_response_not_prior_evidence"
    assert evaluate_failed_pump_evidence(
        {**current, "observed_at": prior["observed_at"]}, prior
    )["reason"] == "current_evidence_not_newer"


def test_still_fast_liquidity_removed_and_non_a_prior_do_not_qualify():
    current, prior = _evidence_pair()
    assert not evaluate_failed_pump_evidence(
        {**current, "liquidity_usd": 8_000, "volume_5m": 2_000}, prior
    )["qualifies"]
    assert not evaluate_failed_pump_evidence(
        {**current, "liquidity_usd": 300}, prior
    )["qualifies"]
    assert not evaluate_failed_pump_evidence(current, {**prior, "primary_bucket": "B5"})["qualifies"]


def test_incomplete_a4_marker_cannot_force_bucket():
    current, _ = _evidence_pair()
    current["a4_evidence_status"] = A4_EVIDENCE_VALID
    assert assign_bucket(current)[0] != BUCKET_A4


def test_source_supplied_a4_marker_is_stripped_before_selection():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = pathlib.Path(tmp) / "a4-forged-marker.sqlite3"
        apply_migrations(db_path)
        current, prior = _evidence_pair()
        forged = {
            **current,
            "liquidity_usd": 8_000,
            "volume_5m": 2_500,
            "txns_5m": 14,
            "chain": "solana",
            "source_name": "dexscreener",
            "source_channel": "DEXSCREENER_SEARCH",
            "captured_at": current["observed_at"],
            "price_usd": 0.001,
            "volume_1h": 500,
            "volume_24h": 10_000,
            "txns_1h": 20,
            "txns_24h": 100,
            "a4_evidence_status": A4_EVIDENCE_VALID,
            "a4_prior_bucket": BUCKET_A1,
            "a4_prior_discovery_candidate_id": 30,
            "a4_prior_source_request_id": 10,
            "a4_prior_source_response_id": 20,
            "a4_prior_source_status": "COMPLETE",
            "a4_prior_data_quality_label": "CLEAN_DATA",
            "a4_prior_observed_at": prior["observed_at"],
            "a4_current_source_request_id": 11,
            "a4_current_source_response_id": 21,
            "a4_current_source_status": "COMPLETE",
            "a4_current_data_quality_label": "CLEAN_DATA",
            "a4_current_observed_at": current["observed_at"],
        }
        accepted, _, _, _ = _select_discovery_candidates(
            [forged],
            existing_token_mints=set(),
            existing_pair_addresses=set(),
            max_candidates=1,
            db_path_or_conn=db_path,
        )
        assert accepted
        assert accepted[0].get("a4_evidence_status") is None
        assert assign_bucket(accepted[0])[0] != BUCKET_A4


def test_two_governed_cycles_persist_a4_and_selection_metadata_without_downstream_unlocks():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = pathlib.Path(tmp) / "a4-proof.sqlite3"
        apply_migrations(db_path)

        first = build_discover_candidates_once_payload(
            _args(db_path, "a4-prior"), transport=_transport(fast=True)
        )
        assert first["accepted_candidates"] == []
        assert first["selection_handoff_report"]["batch_status"] == "REJECTED"

        connection = sqlite3.connect(db_path)
        prior_row = connection.execute(
            "SELECT normalized_candidate_payload_json FROM printer_discovery_candidates "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert assign_bucket(json.loads(prior_row[0]))[0] == BUCKET_A1
        connection.close()

        second = build_discover_candidates_once_payload(
            _args(db_path, "a4-current"), transport=_transport(fast=False)
        )
        assert second["accepted_candidates"] == []
        assert second["selection_handoff_report"]["batch_status"] == "REJECTED"

        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT id, token_id, pair_id, source_response_id, normalized_candidate_payload_json "
            "FROM printer_discovery_candidates ORDER BY id DESC LIMIT 1"
        ).fetchone()
        candidate = json.loads(row["normalized_candidate_payload_json"])
        candidate.update({
            "discovery_candidate_id": row["id"],
            "token_id": row["token_id"],
            "pair_id": row["pair_id"],
            "source_response_id": row["source_response_id"],
            "source_request_id": candidate["a4_current_source_request_id"],
        })
        assert assign_bucket(candidate)[0] == BUCKET_A4
        assert candidate["a4_evidence_status"] == A4_EVIDENCE_VALID
        assert candidate["a4_prior_discovery_candidate_id"] is not None
        assert candidate["a4_prior_source_response_id"] != candidate["a4_current_source_response_id"]

        item = build_batch_item(
            candidate,
            item_status=ITEM_STATUS_SELECTED,
            primary_bucket=BUCKET_A4,
            bucket_name="FAILED_PUMP",
            asset_class=derive_asset_class(BUCKET_A4),
            selection_reason="FAILED_PUMP_EVIDENCE",
            operator_approved=True,
        )
        persist_selection_batch(connection, "A4_FIXTURE_PROOF", [item], operator_approved=True)
        stored = connection.execute(
            "SELECT primary_bucket, candidate_metadata_json FROM printer_selection_batch_items "
            "WHERE batch_id = 'A4_FIXTURE_PROOF'"
        ).fetchone()
        metadata = json.loads(stored["candidate_metadata_json"])
        assert stored["primary_bucket"] == BUCKET_A4
        assert metadata["a4_evidence_status"] == A4_EVIDENCE_VALID
        assert metadata["a4_prior_source_response_id"] != metadata["a4_current_source_response_id"]

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

from datetime import datetime, timezone
import hashlib
import json
import sqlite3

import pytest

from printer_v1.operator_cli.pre_admission_discovery_attempt import (
    PreAdmissionAttemptError,
    PreAdmissionAttemptItem,
    attach_frozen_tracking_lane,
)

NOW = datetime(2026, 8, 25, 14, 10, tzinfo=timezone.utc)
MINT = "Mint111111111111111111111111111111111111111"
POOL = "Pool111111111111111111111111111111111111111"


def _thin_item() -> PreAdmissionAttemptItem:
    canonical = json.dumps(
        {
            "candidate": {
                "mint": MINT,
                "pool": POOL,
                "provenance": "PERSISTED_GRADUATED",
                "liquidity": {"liquidity_usd": 6000.0},
            }
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return PreAdmissionAttemptItem(
        attempt_id="attempt-cycle2",
        slot_ordinal=1,
        token_identity=f"solana-mainnet:{MINT}",
        token_row_id=1,
        mint_identity=MINT,
        pair_identity=POOL,
        pair_row_id=2,
        lifecycle_identity="PUMPSWAP_GRADUATED_CONFIRMED",
        canonical_market_identity=f"solana-mainnet:pumpswap:{POOL}",
        canonical_pool_identity=POOL,
        canonical_evidence_json=canonical,
        canonical_evidence_hash=hashlib.sha256(canonical.encode()).hexdigest(),
        evidence_version="V2_9_8B_PERMANENT_GRADUATED_SUPPLY_V1",
        observed_at=NOW,
        channel_labels=("PERSISTED_GRADUATED",),
    )


def _linked_market_connection(*, pair: str = POOL) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE printer_source_requests(
            id INTEGER PRIMARY KEY,
            source_name TEXT NOT NULL,
            request_kind TEXT NOT NULL
        );
        CREATE TABLE printer_source_responses(
            id INTEGER PRIMARY KEY,
            source_request_id INTEGER NOT NULL,
            source_status TEXT NOT NULL,
            normalized_payload_json TEXT NOT NULL,
            received_at TEXT NOT NULL
        );
        CREATE TABLE printer_pre_admission_discovery_attempt_source_links(
            attempt_id TEXT NOT NULL,
            link_ordinal INTEGER NOT NULL,
            logical_stage TEXT NOT NULL,
            source_request_id INTEGER NOT NULL,
            source_response_id INTEGER,
            source_failure_id INTEGER
        );
        """
    )
    payload = json.dumps(
        {
            "pairs": [
                {
                    "token_mint": MINT,
                    "candidate_mint": MINT,
                    "base_mint": MINT,
                    "quote_mint": "So11111111111111111111111111111111111111112",
                    "pair_address": pair,
                    "chain": "solana",
                    "dex_id": "pumpswap",
                    "liquidity_usd": 6000.0,
                    "price_usd": 0.00042,
                    "volume_5m": 2200.0,
                    "volume_1h": 7000.0,
                    "volume_24h": 22000.0,
                    "txns_5m": 21,
                    "txns_1h": 55,
                    "txns_24h": 140,
                    "captured_at": NOW.isoformat(),
                }
            ]
        },
        sort_keys=True,
    )
    conn.execute(
        "INSERT INTO printer_source_requests VALUES (1,'dexscreener','candidate_market_batch')"
    )
    conn.execute(
        "INSERT INTO printer_source_responses VALUES (10,1,'COMPLETE',?,?)",
        (payload, NOW.isoformat()),
    )
    conn.execute(
        "INSERT INTO printer_pre_admission_discovery_attempt_source_links "
        "VALUES ('attempt-cycle2',1,'candidate_market_batch',1,10,NULL)"
    )
    return conn


def _attach_with_optional_connection(item: PreAdmissionAttemptItem, conn: sqlite3.Connection):
    try:
        return attach_frozen_tracking_lane(item, now=NOW, connection=conn)
    except TypeError as exc:
        if "connection" not in str(exc):
            raise
        return None


def test_linked_exact_market_response_supplies_only_missing_classifier_evidence() -> None:
    conn = _linked_market_connection()
    try:
        frozen = _attach_with_optional_connection(_thin_item(), conn)
    finally:
        conn.close()
    assert frozen is not None
    assert frozen.frozen_tracking_lane == "TRACK_FAST"
    assert frozen.frozen_discovery_action == "TRACK_FAST"


def test_linked_different_pool_never_substitutes_for_exact_selected_pool() -> None:
    conn = _linked_market_connection(pair="DifferentPool111111111111111111111111111111")
    try:
        try:
            result = attach_frozen_tracking_lane(_thin_item(), now=NOW, connection=conn)
        except TypeError as exc:
            if "connection" in str(exc):
                result = None
            else:
                raise
        except PreAdmissionAttemptError as exc:
            assert "FROZEN_TRACKING_LANE_UNAVAILABLE" in str(exc)
            return
    finally:
        conn.close()
    assert result is None, "different-pool evidence must not create a frozen lane"


def test_thin_carrier_without_linked_market_evidence_still_fails_closed() -> None:
    with pytest.raises(PreAdmissionAttemptError, match="FROZEN_TRACKING_LANE_UNAVAILABLE"):
        attach_frozen_tracking_lane(_thin_item(), now=NOW)

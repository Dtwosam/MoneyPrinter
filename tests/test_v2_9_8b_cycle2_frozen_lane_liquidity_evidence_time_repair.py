"""V2-9.8B Cycle-2 frozen-lane liquidity evidence-time repair regressions.

Offline disposable-DB only. No providers, Scheduler runtime, Printer run,
authorization, retrieval, or financial unlock.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    BROAD_NOMINATED,
    MARKET_READY,
    promote_confirmed_with_retained_liquidity,
    record_fresh_pool_nominations,
    resolve_source_derived_liquidity_observed_at,
)
from printer_v1.operator_cli.pre_admission_discovery_attempt import (
    PreAdmissionAttemptError,
    PreAdmissionAttemptItem,
    attach_frozen_tracking_lane,
)

CLAIM_AT = "2026-08-26T12:11:06.507126+00:00"
RECEIVED_AT = "2026-08-26T12:11:12.125895+00:00"
LATER_SOURCE_OBS = "2026-08-26T12:11:20.000000+00:00"
LAWFUL_CUTOFF = "2026-08-26T12:12:00.000000+00:00"
GENUINELY_LATE = "2026-08-26T12:12:30.000000+00:00"

# Aug-26 Cycle-2 holder-2 / selectee shape (offline replay only).
MINT = "CsVBNQijeDY28yG4GLkeGE5p3Nic1BPv5M4mX6wTpump"
POOL = "88wJf9FYZ1CZgZg7KE3GFbQe2wGUacjmK14CGBsdC2Ww"
OTHER_MINT = "GkUnjBvGx9sXf5jEpXWSucgNoT8G1xUo2Dq9vryApump"
OTHER_POOL = "D1n2af8QrDpMY1VCgNPEBUXP83uhJZoqq4b7CURbLNvz"
WSOL = "So11111111111111111111111111111111111111112"


def _qualifying_pair(
    *,
    mint: str = MINT,
    pool: str = POOL,
    liquidity_usd: float = 36910.59,
    price_usd: float = 0.0002106,
    volume_5m: float = 36305.94,
    volume_1h: float = 288080.42,
    volume_24h: float = 288080.42,
    txns_5m: int = 1182,
    txns_1h: int = 7273,
    txns_24h: int = 7273,
) -> dict:
    return {
        "token_mint": mint,
        "candidate_mint": mint,
        "base_mint": mint,
        "quote_mint": WSOL,
        "pair_address": pool,
        "chain": "solana",
        "dex_id": "pumpswap",
        "liquidity_usd": liquidity_usd,
        "price_usd": price_usd,
        "volume_5m": volume_5m,
        "volume_1h": volume_1h,
        "volume_24h": volume_24h,
        "txns_5m": txns_5m,
        "txns_1h": txns_1h,
        "txns_24h": txns_24h,
    }


def _thin_pair(
    *,
    mint: str = MINT,
    pool: str = POOL,
    liquidity_usd: float = 36910.59,
) -> dict:
    return {
        "token_mint": mint,
        "candidate_mint": mint,
        "base_mint": mint,
        "quote_mint": WSOL,
        "pair_address": pool,
        "chain": "solana",
        "dex_id": "pumpswap",
        "liquidity_usd": liquidity_usd,
    }


@pytest.fixture()
def database():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "liquidity-evidence-time.sqlite3"
        apply_migrations(path)
        connection = sqlite3.connect(str(path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield path, connection
        finally:
            connection.close()


def _insert_complete_response(
    connection: sqlite3.Connection,
    *,
    received_at: str,
    pairs: list[dict],
    request_kind: str = "dexscreener_fresh_profiles",
) -> tuple[int, int]:
    connection.execute(
        """
        INSERT INTO printer_source_requests(
            source_name, request_kind, requested_at, source_status, data_quality_label
        ) VALUES (?, ?, ?, 'COMPLETE', 'CLEAN_DATA')
        """,
        ("dexscreener", request_kind, CLAIM_AT),
    )
    request_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
    payload = json.dumps({"pairs": pairs}, sort_keys=True)
    connection.execute(
        """
        INSERT INTO printer_source_responses(
            source_request_id, source_name, received_at, source_status,
            data_quality_label, normalized_payload_json
        ) VALUES (?, 'dexscreener', ?, 'COMPLETE', 'CLEAN_DATA', ?)
        """,
        (request_id, received_at, payload),
    )
    response_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
    return request_id, response_id


def _nominate(
    connection: sqlite3.Connection,
    *,
    request_id: int,
    response_id: int,
    now: str = CLAIM_AT,
    observed_at: str | None = None,
    liquidity_usd: float = 36910.59,
    mint: str = MINT,
    pool: str = POOL,
) -> None:
    observation = {
        "mint": mint,
        "pool": pool,
        "base_mint": mint,
        "quote_mint": WSOL,
        "venue": "pumpswap",
        "liquidity_usd": liquidity_usd,
    }
    if observed_at is not None:
        observation["observed_at"] = observed_at
    record_fresh_pool_nominations(
        connection,
        observations=[observation],
        source="dexscreener",
        request_id=request_id,
        now=now,
        campaign_id="camp-evidence-time",
        response_id=response_id,
    )


def _market_ready_liquidity(connection: sqlite3.Connection) -> dict:
    promo = promote_confirmed_with_retained_liquidity(
        connection,
        mint=MINT,
        pool=POOL,
        venue="pumpswap",
        now=CLAIM_AT,
        campaign_id="camp-evidence-time",
        protocol_request_id=99,
    )
    assert promo.get("promoted") is True, promo
    row = connection.execute(
        """
        SELECT evidence_json FROM printer_discovery_reserve_layers
         WHERE mint_identity=? AND pool_address=? AND reserve_layer=?
        """,
        (MINT, POOL, MARKET_READY),
    ).fetchone()
    assert row is not None
    return dict(json.loads(str(row["evidence_json"]))["liquidity"])


def _linked_attach_connection(
    *,
    pairs: list[dict],
    received_at: str,
    attempt_id: str = "attempt-evidence-time",
) -> tuple[sqlite3.Connection, int, int]:
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
            source_name TEXT NOT NULL,
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
    conn.execute(
        "INSERT INTO printer_source_requests VALUES (1,'dexscreener','dexscreener_fresh_profiles')"
    )
    payload = json.dumps({"pairs": pairs}, sort_keys=True)
    conn.execute(
        "INSERT INTO printer_source_responses VALUES (10,1,'dexscreener','COMPLETE',?,?)",
        (payload, received_at),
    )
    conn.execute(
        """
        INSERT INTO printer_pre_admission_discovery_attempt_source_links
        VALUES (?,1,'dexscreener_fresh_profiles',1,10,NULL)
        """,
        (attempt_id,),
    )
    return conn, 1, 10


def _item_from_liquidity(
    liquidity: dict,
    *,
    observed_at: str,
    attempt_id: str = "attempt-evidence-time",
    mint: str = MINT,
    pool: str = POOL,
) -> PreAdmissionAttemptItem:
    candidate = {
        "provenance": "FRESH_AGGREGATOR_PROTOCOL_CONFIRMED",
        "liquidity": liquidity,
        "chain": "solana",
        "token_mint": mint,
        "pair_address": pool,
    }
    canonical = json.dumps(
        {
            "candidate": candidate,
            "mint_identity": mint,
            "pair_identity": pool,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return PreAdmissionAttemptItem(
        attempt_id=attempt_id,
        slot_ordinal=1,
        token_identity=f"solana-mainnet:{mint}",
        token_row_id=1,
        mint_identity=mint,
        pair_identity=pool,
        pair_row_id=2,
        lifecycle_identity="PRESENT_POOL_CONFIRMED",
        canonical_market_identity=f"solana-mainnet:pumpswap:{pool}",
        canonical_pool_identity=pool,
        canonical_evidence_json=canonical,
        canonical_evidence_hash=hashlib.sha256(canonical.encode()).hexdigest(),
        evidence_version="V2_9_8B_PERMANENT_GRADUATED_SUPPLY_V1",
        observed_at=datetime.fromisoformat(observed_at),
        channel_labels=("FRESH_AGGREGATOR_PROTOCOL_CONFIRMED",),
    )


def _resolve_claimed(
    connection: sqlite3.Connection,
    *,
    request_id: int,
    response_id: int,
    candidate_observed_at: str | None = CLAIM_AT,
    source_name: str = "dexscreener",
    mint: str = MINT,
    pool: str = POOL,
) -> str:
    return resolve_source_derived_liquidity_observed_at(
        connection,
        candidate_observed_at=candidate_observed_at,
        fallback_now=CLAIM_AT,
        source_response_id=response_id,
        source_request_id=request_id,
        source_name=source_name,
        mint_identity=mint,
        pair_identity=pool,
    )


def _claimed_liquidity(
    *,
    source_response_id: int = 10,
    source_request_id: int = 1,
    source_name: str = "dexscreener",
    liquidity_observed_at: str = RECEIVED_AT,
    mint: str = MINT,
    pool: str = POOL,
    liquidity_usd: float = 36910.59,
) -> dict:
    return {
        "status": "LIQUIDITY_PROVEN",
        "liquidity_usd": liquidity_usd,
        "mint": mint,
        "pool": pool,
        "base_mint": mint,
        "quote_mint": WSOL,
        "reason": "AT_OR_ABOVE_3000_FLOOR",
        "source_status": "COMPLETE",
        "outcome_category": "LIQUIDITY_EXACT_ABOVE_FLOOR",
        "detailed_reason": "AT_OR_ABOVE_3000_FLOOR_RETAINED",
        "source_name": source_name,
        "source_request_id": source_request_id,
        "source_response_id": source_response_id,
        "liquidity_observed_at": liquidity_observed_at,
    }


class TestClaimedProvingResponseFailClosed:
    def test_claimed_response_id_absent_fails_closed(self, database) -> None:
        _, connection = database
        with pytest.raises(ValueError, match="LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID"):
            _resolve_claimed(connection, request_id=11, response_id=999999)
        with pytest.raises(ValueError, match="LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID"):
            record_fresh_pool_nominations(
                connection,
                observations=[
                    {
                        "mint": MINT,
                        "pool": POOL,
                        "base_mint": MINT,
                        "quote_mint": WSOL,
                        "venue": "pumpswap",
                        "liquidity_usd": 4500.0,
                    }
                ],
                source="dexscreener",
                request_id=11,
                now=CLAIM_AT,
                campaign_id="camp-absent-response",
                response_id=999999,
            )

    def test_claimed_response_non_complete_fails_closed(self, database) -> None:
        _, connection = database
        request_id, response_id = _insert_complete_response(
            connection,
            received_at=RECEIVED_AT,
            pairs=[_qualifying_pair()],
        )
        connection.execute(
            "UPDATE printer_source_responses SET source_status='STALE' WHERE id=?",
            (response_id,),
        )
        with pytest.raises(ValueError, match="LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID"):
            _resolve_claimed(
                connection, request_id=request_id, response_id=response_id
            )

    def test_claimed_response_missing_received_at_fails_closed(self, database) -> None:
        _, connection = database
        request_id, response_id = _insert_complete_response(
            connection,
            received_at=RECEIVED_AT,
            pairs=[_qualifying_pair()],
        )
        connection.execute(
            "UPDATE printer_source_responses SET received_at='' WHERE id=?",
            (response_id,),
        )
        with pytest.raises(ValueError, match="LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID"):
            _resolve_claimed(
                connection, request_id=request_id, response_id=response_id
            )

    def test_malformed_claimed_response_timestamp_fails_closed(self, database) -> None:
        _, connection = database
        request_id, response_id = _insert_complete_response(
            connection,
            received_at=RECEIVED_AT,
            pairs=[_qualifying_pair()],
        )
        connection.execute(
            "UPDATE printer_source_responses SET received_at='not-a-timestamp' WHERE id=?",
            (response_id,),
        )
        with pytest.raises(ValueError, match="LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID"):
            _resolve_claimed(
                connection, request_id=request_id, response_id=response_id
            )

    def test_invalid_claimed_response_id_type_fails_closed(self, database) -> None:
        _, connection = database
        with pytest.raises(ValueError, match="LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID"):
            resolve_source_derived_liquidity_observed_at(
                connection,
                candidate_observed_at=CLAIM_AT,
                fallback_now=CLAIM_AT,
                source_response_id=True,  # bool must not coerce to 1
                source_request_id=1,
                source_name="dexscreener",
                mint_identity=MINT,
                pair_identity=POOL,
            )

    def test_complete_response_from_wrong_request_fails_closed(self, database) -> None:
        _, connection = database
        request_id, response_id = _insert_complete_response(
            connection,
            received_at=RECEIVED_AT,
            pairs=[_qualifying_pair()],
        )
        connection.execute(
            """
            INSERT INTO printer_source_requests(
                source_name, request_kind, requested_at, source_status, data_quality_label
            ) VALUES ('dexscreener', 'dexscreener_fresh_profiles', ?, 'COMPLETE', 'CLEAN_DATA')
            """,
            (CLAIM_AT,),
        )
        other_request_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
        with pytest.raises(ValueError, match="LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID"):
            _resolve_claimed(
                connection,
                request_id=other_request_id,
                response_id=response_id,
            )
        del request_id

    def test_complete_response_from_wrong_source_fails_closed(self, database) -> None:
        _, connection = database
        request_id, response_id = _insert_complete_response(
            connection,
            received_at=RECEIVED_AT,
            pairs=[_qualifying_pair()],
        )
        with pytest.raises(ValueError, match="LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID"):
            _resolve_claimed(
                connection,
                request_id=request_id,
                response_id=response_id,
                source_name="geckoterminal",
            )

    def test_response_request_name_mismatch_fails_closed(self, database) -> None:
        _, connection = database
        request_id, response_id = _insert_complete_response(
            connection,
            received_at=RECEIVED_AT,
            pairs=[_qualifying_pair()],
        )
        connection.execute(
            "UPDATE printer_source_responses SET source_name='geckoterminal' WHERE id=?",
            (response_id,),
        )
        with pytest.raises(ValueError, match="LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID"):
            _resolve_claimed(
                connection,
                request_id=request_id,
                response_id=response_id,
                source_name="dexscreener",
            )

    def test_wrong_exact_mint_pair_fails_closed(self, database) -> None:
        _, connection = database
        request_id, response_id = _insert_complete_response(
            connection,
            received_at=RECEIVED_AT,
            pairs=[_qualifying_pair()],
        )
        with pytest.raises(ValueError, match="LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID"):
            _resolve_claimed(
                connection,
                request_id=request_id,
                response_id=response_id,
                mint=OTHER_MINT,
                pool=OTHER_POOL,
            )

    def test_empty_payload_is_not_exact_liquidity_proof(self, database) -> None:
        _, connection = database
        request_id, response_id = _insert_complete_response(
            connection,
            received_at=RECEIVED_AT,
            pairs=[_qualifying_pair()],
        )
        connection.execute(
            "UPDATE printer_source_responses SET normalized_payload_json='{}' WHERE id=?",
            (response_id,),
        )
        with pytest.raises(ValueError, match="LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID"):
            _resolve_claimed(
                connection, request_id=request_id, response_id=response_id
            )

    def test_no_source_response_id_preserves_legacy_callback_time(
        self, database
    ) -> None:
        _, connection = database
        observed = resolve_source_derived_liquidity_observed_at(
            connection,
            candidate_observed_at=None,
            fallback_now=CLAIM_AT,
            source_response_id=None,
        )
        assert observed == CLAIM_AT
        record_fresh_pool_nominations(
            connection,
            observations=[
                {
                    "mint": MINT,
                    "pool": POOL,
                    "base_mint": MINT,
                    "quote_mint": WSOL,
                    "venue": "pumpswap",
                    "liquidity_usd": 4500.0,
                }
            ],
            source="dexscreener",
            request_id=11,
            now=CLAIM_AT,
            campaign_id="camp-no-response",
            response_id=None,
        )
        row = connection.execute(
            """
            SELECT observed_at, evidence_json FROM printer_discovery_reserve_layers
             WHERE mint_identity=? AND reserve_layer=?
            """,
            (MINT, BROAD_NOMINATED),
        ).fetchone()
        evidence = json.loads(str(row["evidence_json"]))
        assert row["observed_at"] == CLAIM_AT
        assert evidence["liquidity_observed_at"] == CLAIM_AT
        assert evidence.get("response_id") is None

    def test_resolver_returns_only_timestamp_not_liquidity_proven_status(
        self, database
    ) -> None:
        _, connection = database
        request_id, response_id = _insert_complete_response(
            connection,
            received_at=RECEIVED_AT,
            pairs=[_qualifying_pair()],
        )
        resolved = _resolve_claimed(
            connection, request_id=request_id, response_id=response_id
        )
        assert isinstance(resolved, str)
        assert resolved == RECEIVED_AT
        assert "LIQUIDITY_PROVEN" not in resolved


class TestProducerEvidenceTimeTruthfulness:
    def test_callback_earlier_than_received_at_does_not_stamp_earlier(
        self, database
    ) -> None:
        _, connection = database
        request_id, response_id = _insert_complete_response(
            connection,
            received_at=RECEIVED_AT,
            pairs=[_qualifying_pair()],
        )
        _nominate(connection, request_id=request_id, response_id=response_id, now=CLAIM_AT)
        row = connection.execute(
            """
            SELECT observed_at, evidence_json FROM printer_discovery_reserve_layers
             WHERE mint_identity=? AND reserve_layer=?
            """,
            (MINT, BROAD_NOMINATED),
        ).fetchone()
        evidence = json.loads(str(row["evidence_json"]))
        assert row["observed_at"] >= RECEIVED_AT
        assert evidence["liquidity_observed_at"] >= RECEIVED_AT
        assert evidence["response_id"] == response_id
        assert evidence["request_id"] == request_id

        liquidity = _market_ready_liquidity(connection)
        assert liquidity["source_response_id"] == response_id
        assert liquidity["source_request_id"] == request_id
        assert liquidity["liquidity_observed_at"] >= RECEIVED_AT
        assert liquidity["liquidity_observed_at"] >= CLAIM_AT

    def test_truthful_later_source_observation_is_preserved(self, database) -> None:
        _, connection = database
        request_id, response_id = _insert_complete_response(
            connection,
            received_at=RECEIVED_AT,
            pairs=[_qualifying_pair()],
        )
        _nominate(
            connection,
            request_id=request_id,
            response_id=response_id,
            now=CLAIM_AT,
            observed_at=LATER_SOURCE_OBS,
        )
        row = connection.execute(
            """
            SELECT observed_at, evidence_json FROM printer_discovery_reserve_layers
             WHERE mint_identity=? AND reserve_layer=?
            """,
            (MINT, BROAD_NOMINATED),
        ).fetchone()
        evidence = json.loads(str(row["evidence_json"]))
        assert row["observed_at"] == LATER_SOURCE_OBS
        assert evidence["liquidity_observed_at"] == LATER_SOURCE_OBS

        liquidity = _market_ready_liquidity(connection)
        assert liquidity["liquidity_observed_at"] == LATER_SOURCE_OBS


class TestAug26IncidentFrozenLaneReplay:
    def test_exact_incident_shape_becomes_supplement_eligible_and_track_fast(
        self, database
    ) -> None:
        _, connection = database
        request_id, response_id = _insert_complete_response(
            connection,
            received_at=RECEIVED_AT,
            pairs=[_qualifying_pair()],
        )
        _nominate(connection, request_id=request_id, response_id=response_id, now=CLAIM_AT)
        liquidity = _market_ready_liquidity(connection)
        assert liquidity["liquidity_observed_at"] >= RECEIVED_AT
        # Isolated attach DB uses fixed response id 10; keep the claimed proving
        # identity coherent with the linked COMPLETE body under validation.
        liquidity = dict(liquidity)
        liquidity["source_name"] = "dexscreener"
        liquidity["source_response_id"] = 10
        liquidity["source_request_id"] = 1

        link_conn, _, _ = _linked_attach_connection(
            pairs=[_qualifying_pair()],
            received_at=RECEIVED_AT,
        )
        try:
            frozen = attach_frozen_tracking_lane(
                _item_from_liquidity(
                    liquidity,
                    observed_at=str(liquidity["liquidity_observed_at"]),
                ),
                now=datetime.fromisoformat(CLAIM_AT),
                connection=link_conn,
            )
        finally:
            link_conn.close()
        assert frozen.frozen_tracking_lane == "TRACK_FAST"
        assert frozen.frozen_discovery_action == "TRACK_FAST"

    def test_baseline_inversion_shape_is_no_longer_watch_only_silent(
        self, database
    ) -> None:
        """Producer must not emit inverted chronology for a COMPLETE proving response."""
        _, connection = database
        request_id, response_id = _insert_complete_response(
            connection,
            received_at=RECEIVED_AT,
            pairs=[_qualifying_pair()],
        )
        _nominate(connection, request_id=request_id, response_id=response_id, now=CLAIM_AT)
        liquidity = _market_ready_liquidity(connection)
        # The historical defect stamped CLAIM_AT; repaired producer must not.
        assert liquidity["liquidity_observed_at"] != CLAIM_AT
        assert liquidity["liquidity_observed_at"] >= RECEIVED_AT


class TestLinkedSupplementStrictness:
    def test_exact_linked_response_becomes_supplement_eligible(self) -> None:
        liquidity = _claimed_liquidity()
        conn, _, _ = _linked_attach_connection(
            pairs=[_qualifying_pair()],
            received_at=RECEIVED_AT,
        )
        try:
            frozen = attach_frozen_tracking_lane(
                _item_from_liquidity(liquidity, observed_at=RECEIVED_AT),
                now=datetime.fromisoformat(LAWFUL_CUTOFF),
                connection=conn,
            )
        finally:
            conn.close()
        assert frozen.frozen_tracking_lane == "TRACK_FAST"

    def test_wrong_pair_remains_excluded(self) -> None:
        # Claimed provenance mint/pair does not appear in the proving payload.
        liquidity = _claimed_liquidity()
        conn, _, _ = _linked_attach_connection(
            pairs=[_qualifying_pair(pool=OTHER_POOL)],
            received_at=RECEIVED_AT,
        )
        try:
            with pytest.raises(
                PreAdmissionAttemptError,
                match="LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID",
            ):
                attach_frozen_tracking_lane(
                    _item_from_liquidity(liquidity, observed_at=RECEIVED_AT),
                    now=datetime.fromisoformat(LAWFUL_CUTOFF),
                    connection=conn,
                )
        finally:
            conn.close()

    def test_wrong_mint_remains_excluded(self) -> None:
        liquidity = _claimed_liquidity()
        conn, _, _ = _linked_attach_connection(
            pairs=[_qualifying_pair(mint=OTHER_MINT)],
            received_at=RECEIVED_AT,
        )
        try:
            with pytest.raises(
                PreAdmissionAttemptError,
                match="LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID",
            ):
                attach_frozen_tracking_lane(
                    _item_from_liquidity(liquidity, observed_at=RECEIVED_AT),
                    now=datetime.fromisoformat(LAWFUL_CUTOFF),
                    connection=conn,
                )
        finally:
            conn.close()

    def test_unrelated_response_remains_excluded(self) -> None:
        liquidity = _claimed_liquidity()
        conn, _, _ = _linked_attach_connection(
            pairs=[_qualifying_pair(mint=OTHER_MINT, pool=OTHER_POOL)],
            received_at=RECEIVED_AT,
        )
        try:
            with pytest.raises(
                PreAdmissionAttemptError,
                match="LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID",
            ):
                attach_frozen_tracking_lane(
                    _item_from_liquidity(liquidity, observed_at=RECEIVED_AT),
                    now=datetime.fromisoformat(LAWFUL_CUTOFF),
                    connection=conn,
                )
        finally:
            conn.close()

    def test_genuinely_late_response_relative_to_lawful_cutoff_remains_excluded(
        self,
    ) -> None:
        # Do not claim the late linked row as the proving liquidity response; this
        # isolates the existing consumer gate (received_at <= observed_at).
        liquidity = {
            "liquidity_usd": 36910.59,
            "liquidity_observed_at": LAWFUL_CUTOFF,
        }
        conn, _, _ = _linked_attach_connection(
            pairs=[_qualifying_pair()],
            received_at=GENUINELY_LATE,
        )
        try:
            with pytest.raises(
                PreAdmissionAttemptError, match="FROZEN_TRACKING_LANE_UNAVAILABLE"
            ):
                attach_frozen_tracking_lane(
                    _item_from_liquidity(liquidity, observed_at=LAWFUL_CUTOFF),
                    now=datetime.fromisoformat(LAWFUL_CUTOFF),
                    connection=conn,
                )
        finally:
            conn.close()


class TestFrozenCarrierChronologyInvariant:
    def test_inverted_retained_liquidity_time_fails_closed_explicitly(self) -> None:
        liquidity = _claimed_liquidity(liquidity_observed_at=CLAIM_AT)
        conn, _, _ = _linked_attach_connection(
            pairs=[_qualifying_pair()],
            received_at=RECEIVED_AT,
        )
        try:
            with pytest.raises(
                PreAdmissionAttemptError,
                match="LIQUIDITY_EVIDENCE_TIME_PRECEDES_SOURCE_RESPONSE",
            ):
                attach_frozen_tracking_lane(
                    _item_from_liquidity(liquidity, observed_at=CLAIM_AT),
                    now=datetime.fromisoformat(LAWFUL_CUTOFF),
                    connection=conn,
                )
        finally:
            conn.close()

    def test_claimed_absent_proving_response_fails_closed_on_carrier(self) -> None:
        liquidity = _claimed_liquidity(source_response_id=404)
        conn, _, _ = _linked_attach_connection(
            pairs=[_qualifying_pair()],
            received_at=RECEIVED_AT,
        )
        try:
            with pytest.raises(
                PreAdmissionAttemptError,
                match="LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID",
            ):
                attach_frozen_tracking_lane(
                    _item_from_liquidity(liquidity, observed_at=RECEIVED_AT),
                    now=datetime.fromisoformat(LAWFUL_CUTOFF),
                    connection=conn,
                )
        finally:
            conn.close()

    def test_claimed_non_complete_proving_response_fails_closed_on_carrier(self) -> None:
        liquidity = _claimed_liquidity()
        conn, _, _ = _linked_attach_connection(
            pairs=[_qualifying_pair()],
            received_at=RECEIVED_AT,
        )
        try:
            conn.execute(
                "UPDATE printer_source_responses SET source_status='STALE' WHERE id=10"
            )
            with pytest.raises(
                PreAdmissionAttemptError,
                match="LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID",
            ):
                attach_frozen_tracking_lane(
                    _item_from_liquidity(liquidity, observed_at=RECEIVED_AT),
                    now=datetime.fromisoformat(LAWFUL_CUTOFF),
                    connection=conn,
                )
        finally:
            conn.close()

    def test_claimed_wrong_request_provenance_fails_closed_on_carrier(self) -> None:
        liquidity = _claimed_liquidity(source_request_id=999)
        conn, _, _ = _linked_attach_connection(
            pairs=[_qualifying_pair()],
            received_at=RECEIVED_AT,
        )
        try:
            with pytest.raises(
                PreAdmissionAttemptError,
                match="LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID",
            ):
                attach_frozen_tracking_lane(
                    _item_from_liquidity(liquidity, observed_at=RECEIVED_AT),
                    now=datetime.fromisoformat(LAWFUL_CUTOFF),
                    connection=conn,
                )
        finally:
            conn.close()


class TestClassifierUnchanged:
    def test_genuine_thin_market_evidence_remains_watch_only(self) -> None:
        liquidity = {
            "liquidity_usd": 36910.59,
            "liquidity_observed_at": RECEIVED_AT,
        }
        with pytest.raises(
            PreAdmissionAttemptError, match="FROZEN_TRACKING_LANE_UNAVAILABLE"
        ):
            attach_frozen_tracking_lane(
                _item_from_liquidity(liquidity, observed_at=RECEIVED_AT),
                now=datetime.fromisoformat(LAWFUL_CUTOFF),
            )

    def test_genuine_weak_activity_remains_watch_only(self) -> None:
        liquidity = _claimed_liquidity()
        weak = _qualifying_pair(
            volume_5m=0.0,
            volume_1h=0.0,
            volume_24h=5.0,
            txns_5m=0,
            txns_1h=0,
            txns_24h=1,
        )
        # price present but activity dead/near-zero → WATCH_ONLY under existing law
        weak["price_usd"] = 0.0002106
        conn, _, _ = _linked_attach_connection(pairs=[weak], received_at=RECEIVED_AT)
        try:
            with pytest.raises(
                PreAdmissionAttemptError, match="FROZEN_TRACKING_LANE_UNAVAILABLE"
            ):
                attach_frozen_tracking_lane(
                    _item_from_liquidity(liquidity, observed_at=RECEIVED_AT),
                    now=datetime.fromisoformat(LAWFUL_CUTOFF),
                    connection=conn,
                )
        finally:
            conn.close()

    def test_qualifying_complete_evidence_can_produce_existing_track_lane(self) -> None:
        liquidity = _claimed_liquidity(liquidity_usd=6000.0)
        conn, _, _ = _linked_attach_connection(
            pairs=[
                _qualifying_pair(
                    liquidity_usd=6000.0,
                    volume_5m=2200.0,
                    volume_1h=7000.0,
                    volume_24h=22000.0,
                    txns_5m=21,
                    txns_1h=55,
                    txns_24h=140,
                )
            ],
            received_at=RECEIVED_AT,
        )
        try:
            frozen = attach_frozen_tracking_lane(
                _item_from_liquidity(liquidity, observed_at=RECEIVED_AT),
                now=datetime.fromisoformat(LAWFUL_CUTOFF),
                connection=conn,
            )
        finally:
            conn.close()
        assert frozen.frozen_tracking_lane in {"TRACK_FAST", "TRACK_NORMAL"}

    def test_idempotent_projection_keeps_provenance(self, database) -> None:
        _, connection = database
        request_id, response_id = _insert_complete_response(
            connection,
            received_at=RECEIVED_AT,
            pairs=[_qualifying_pair()],
        )
        _nominate(connection, request_id=request_id, response_id=response_id, now=CLAIM_AT)
        first = _market_ready_liquidity(connection)
        second = promote_confirmed_with_retained_liquidity(
            connection,
            mint=MINT,
            pool=POOL,
            venue="pumpswap",
            now=CLAIM_AT,
            campaign_id="camp-evidence-time",
            protocol_request_id=99,
        )["liquidity"]
        assert first["source_response_id"] == second["source_response_id"] == response_id
        assert first["source_request_id"] == second["source_request_id"] == request_id
        assert first["liquidity_observed_at"] == second["liquidity_observed_at"]
        assert first["liquidity_usd"] == second["liquidity_usd"]

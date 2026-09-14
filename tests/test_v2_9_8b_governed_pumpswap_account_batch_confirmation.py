"""Focused proofs for governed PumpSwap getMultipleAccounts protocol confirmation."""

from __future__ import annotations

import base64
import sqlite3
import tempfile
from pathlib import Path

import pytest

from printer_v1.contracts.enums import SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    CONTRACT_BLOCKED,
    CURRENT_POOL_CONFIRMED,
    IDENTITY_CONFLICT,
    StageBudget,
    process_protocol_confirmation_queue,
    record_fresh_pool_nominations,
)
from printer_v1.sources.pumpswap import (
    PUMPSWAP_AMM_PROGRAM_ID,
    _PUMPSWAP_POOL_BASE_MINT_OFFSET,
    _b58decode,
)
from printer_v1.sources.pumpswap_pool_account_batch import (
    MAX_BATCH_ADDRESSES,
    REQUEST_KIND,
    SOURCE_NAME,
    build_ordered_unique_addresses,
    build_pumpswap_pool_account_batch_adapter,
    fixture_account_batch_transport,
    normalize_pumpswap_pool_account_batch_payload,
    protocol_outcome_from_confirm,
)
from printer_v1.sources.pumpswap import confirm_pumpswap_pool_from_account
from printer_v1.sources.contracts import build_governed_source_request, GOVERNOR_ONLY_EXECUTION_PATH
from tests.test_v2_9_8b_generic_present_pool_conversion import _generic_transport
from printer_v1.sources.governed_execution import execute_source_request_with_governor

NOW = "2026-08-04T16:00:00+00:00"
WSOL = "So11111111111111111111111111111111111111112"
_MINT_A = "6wtZueu89AGwQkGUki3HcerjCDFxLA9PyVUBWQbMpump"
_MINT_B = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
_POOL_A = "DfxsEZga7jwVhwo6JUfWnDD8tg9aSLcv32UYzLQ3SwqD"
_POOL_B = "ECobcS1MSzzAnnzz89xjwRSEYsHAChB7DMbd3G25gwgc"
_OTHER = "So11111111111111111111111111111111111111112"


def _pool_account(owner=PUMPSWAP_AMM_PROGRAM_ID, mint=_MINT_A, total_len=301):
    mb = _b58decode(mint)
    off = _PUMPSWAP_POOL_BASE_MINT_OFFSET
    data = b"\x01" * off + mb + b"\x02" * (total_len - off - len(mb))
    return {"owner": owner, "data": [base64.b64encode(data).decode(), "base64"]}


@pytest.fixture()
def database():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "batch.sqlite3"
        apply_migrations(path)
        con = sqlite3.connect(str(path))
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            yield path, con
        finally:
            con.close()


class TestBatchConstruction:
    def test_batch_cap_100_enforced(self):
        cands = [
            {"mint": f"M{i}", "pool": f"P{i}"} for i in range(105)
        ]
        addrs, mapping, skipped = build_ordered_unique_addresses(cands)
        assert len(addrs) == MAX_BATCH_ADDRESSES == 100
        assert len(skipped) == 5
        assert all(s["reason"] == "BATCH_CAP_EXCEEDED" for s in skipped)

    def test_duplicate_address_mapping(self):
        addrs, mapping, skipped = build_ordered_unique_addresses(
            [
                {"mint": "M1", "pool": "P1", "venue": "pumpswap"},
                {"mint": "M2", "pool": "P1", "venue": "pumpswap"},
                {"mint": "M3", "pool": "P2", "venue": "pumpswap"},
            ]
        )
        assert addrs == ["P1", "P2"]
        assert len(mapping["P1"]) == 2
        assert skipped == []


class TestNormalizeMemberOutcomes:
    def test_valid_owner_and_mint_pass(self):
        payload = {
            "result": {
                "context": {"slot": 42},
                "value": [_pool_account(mint=_MINT_A)],
            },
            "response_bytes": 900,
        }
        result = normalize_pumpswap_pool_account_batch_payload(
            payload,
            request_kind=REQUEST_KIND,
            requested_addresses=[_POOL_A],
            address_to_candidates={_POOL_A: [{"mint": _MINT_A, "pool": _POOL_A}]},
        )
        assert result.source_status == SourceStatus.COMPLETE
        members = result.normalized_payload["members"]
        assert members[0]["outcome"] == "CURRENT_POOL_CONFIRMED"
        # Forbidden fields must be null
        assert members[0]["reserves"] is None
        assert members[0]["virtual_quote_reserves"] is None
        assert members[0]["eligibility"] is None
        assert result.normalized_payload["liquidity"] is None

    def test_null_account_candidate_local(self):
        payload = {
            "result": {"context": {"slot": 1}, "value": [None]},
            "response_bytes": 100,
        }
        result = normalize_pumpswap_pool_account_batch_payload(
            payload,
            request_kind=REQUEST_KIND,
            requested_addresses=[_POOL_A],
            address_to_candidates={_POOL_A: [{"mint": _MINT_A, "pool": _POOL_A}]},
        )
        assert result.source_status == SourceStatus.COMPLETE
        assert result.normalized_payload["members"][0]["outcome"] == "ACCOUNT_NOT_FOUND"

    def test_wrong_owner_candidate_local(self):
        payload = {
            "result": {
                "context": {"slot": 1},
                "value": [_pool_account(owner="Raydium1111111111111111111111111111111111111")],
            },
            "response_bytes": 100,
        }
        result = normalize_pumpswap_pool_account_batch_payload(
            payload,
            request_kind=REQUEST_KIND,
            requested_addresses=[_POOL_A],
            address_to_candidates={_POOL_A: [{"mint": _MINT_A, "pool": _POOL_A}]},
        )
        assert result.normalized_payload["members"][0]["outcome"] == "POOL_OWNER_MISMATCH"

    def test_short_data_candidate_local(self):
        acct = {
            "owner": PUMPSWAP_AMM_PROGRAM_ID,
            "data": [base64.b64encode(b"\x00" * 10).decode(), "base64"],
        }
        payload = {
            "result": {"context": {"slot": 1}, "value": [acct]},
            "response_bytes": 50,
        }
        result = normalize_pumpswap_pool_account_batch_payload(
            payload,
            request_kind=REQUEST_KIND,
            requested_addresses=[_POOL_A],
            address_to_candidates={_POOL_A: [{"mint": _MINT_A, "pool": _POOL_A}]},
        )
        assert result.normalized_payload["members"][0]["outcome"] == "POOL_DATA_UNDECODABLE"

    def test_wrong_base_mint_identity_mismatch(self):
        payload = {
            "result": {
                "context": {"slot": 1},
                "value": [_pool_account(mint=_MINT_A)],
            },
            "response_bytes": 100,
        }
        result = normalize_pumpswap_pool_account_batch_payload(
            payload,
            request_kind=REQUEST_KIND,
            requested_addresses=[_POOL_A],
            address_to_candidates={_POOL_A: [{"mint": _OTHER, "pool": _POOL_A}]},
        )
        assert result.normalized_payload["members"][0]["outcome"] == "BASE_MINT_MISMATCH"

    def test_mixed_batch_preserves_valid_siblings(self):
        payload = {
            "result": {
                "context": {"slot": 7},
                "value": [
                    _pool_account(mint=_MINT_A),
                    None,
                    _pool_account(owner="WrongOwner1111111111111111111111111111111", mint=_MINT_B),
                ],
            },
            "response_bytes": 1500,
        }
        result = normalize_pumpswap_pool_account_batch_payload(
            payload,
            request_kind=REQUEST_KIND,
            requested_addresses=[_POOL_A, _POOL_B, "PoolC"],
            address_to_candidates={
                _POOL_A: [{"mint": _MINT_A, "pool": _POOL_A}],
                _POOL_B: [{"mint": _MINT_B, "pool": _POOL_B}],
                "PoolC": [{"mint": _MINT_B, "pool": "PoolC"}],
            },
        )
        outcomes = {m["pool"]: m["outcome"] for m in result.normalized_payload["members"]}
        assert outcomes[_POOL_A] == "CURRENT_POOL_CONFIRMED"
        assert outcomes[_POOL_B] == "ACCOUNT_NOT_FOUND"
        assert outcomes["PoolC"] == "POOL_OWNER_MISMATCH"

    def test_count_mismatch_shared_source_failure(self):
        payload = {
            "result": {"context": {"slot": 1}, "value": [None]},
            "response_bytes": 10,
        }
        result = normalize_pumpswap_pool_account_batch_payload(
            payload,
            request_kind=REQUEST_KIND,
            requested_addresses=[_POOL_A, _POOL_B],
            address_to_candidates={},
        )
        assert result.source_status == SourceStatus.FAILED
        assert "count_mismatch" in str(result.failure_type)

    def test_rpc_error_shared_source_failure(self):
        result = normalize_pumpswap_pool_account_batch_payload(
            {"error": {"code": -32000, "message": "boom"}, "response_bytes": 0},
            request_kind=REQUEST_KIND,
            requested_addresses=[_POOL_A],
            address_to_candidates={},
        )
        assert result.source_status == SourceStatus.FAILED
        assert result.normalized_payload.get("shared_source_failure") is True


class TestProductionQueueComposition:
    def _seed_due(self, connection, items):
        record_fresh_pool_nominations(
            connection,
            observations=items,
            source="geckoterminal",
            request_id=1,
            now=NOW,
            campaign_id="camp-batch",
        )

    def test_production_queue_calls_governed_transport(self, database):
        _, connection = database
        self._seed_due(
            connection,
            [
                {
                    "mint": _MINT_A,
                    "pool": _POOL_A,
                    "base_mint": _MINT_A,
                    "quote_mint": WSOL,
                    "venue": "pumpswap",
                    "liquidity_usd": 5000.0,
                },
                {
                    "mint": _MINT_B,
                    "pool": _POOL_B,
                    "base_mint": _MINT_B,
                    "quote_mint": WSOL,
                    "venue": "pumpswap",
                    "liquidity_usd": 5000.0,
                },
                {
                    "mint": "MintMeteora" + "z" * 20,
                    "pool": "PoolMeteora" + "z" * 20,
                    "base_mint": "MintMeteora" + "z" * 20,
                    "quote_mint": WSOL,
                    "venue": "meteora-damm-v2",
                    "liquidity_usd": 5000.0,
                },
            ],
        )
        transport = fixture_account_batch_transport(
            {
                _POOL_A: _pool_account(mint=_MINT_A),
                _POOL_B: _pool_account(mint=_MINT_B),
            }
        )
        calls = []
        generic = _generic_transport([{
            "mint": "MintMeteora" + "z" * 20,
            "pool": "PoolMeteora" + "z" * 20,
        }])

        def governed(kind, fixture):
            def invoke(context):
                assert context.governor_approved is True
                assert context.execution_path == GOVERNOR_ONLY_EXECUTION_PATH
                assert context.request.request_kind == kind
                calls.append(kind)
                return fixture(context)
            return invoke

        budget = StageBudget.permanent_discovery_default()
        budget.consume("intake", 3)
        budget.seal("intake")
        report = process_protocol_confirmation_queue(
            connection,
            stage_budget=budget,
            now=NOW,
            campaign_id="camp-batch",
            account_batch_transport=governed(REQUEST_KIND, transport),
            generic_account_batch_transport=governed("generic_present_pool_account_batch", generic),
        )
        assert report["batch_count"] == 2
        assert report["source_requests"] == 2
        assert report["transport_operations"] == 3
        assert report["local_validation_steps"] == 3
        assert len(report["source_request_ids"]) == 2
        assert calls == [REQUEST_KIND, "generic_present_pool_account_batch"]
        assert budget.used_by_stage["protocol_confirmation"] == 2
        assert len(report["source_response_ids"]) == 2
        assert report["source_failure_ids"] == []
        # Meteora uses exact generic mint/pool/program verification, not its label.
        meteora_state = connection.execute(
            """SELECT current_state FROM printer_exact_market_states
               WHERE mint_identity=?""",
            ("MintMeteora" + "z" * 20,),
        ).fetchone()
        assert meteora_state["current_state"] in {CURRENT_POOL_CONFIRMED, "CURRENT_VISIBLE"}
        assert report["outcome_counts"]["GENERIC_POOL_CONFIRMED"] == 1
        # Valid PumpSwap confirms
        assert any(o["outcome"] == "CURRENT_POOL_CONFIRMED" for o in report["outcomes"])
        assert len(report["confirmed_for_market"]) >= 1
        # DB transitions — direct promotion may advance confirmed rows to CURRENT_VISIBLE
        states = {
            (r["mint_identity"], r["current_state"])
            for r in connection.execute(
                "SELECT mint_identity, current_state FROM printer_exact_market_states"
            )
        }
        assert (_MINT_A, CURRENT_POOL_CONFIRMED) in states or (
            _MINT_A,
            "CURRENT_VISIBLE",
        ) in states
        # Governed request persisted
        kind = connection.execute(
            "SELECT request_kind, source_name FROM printer_source_requests WHERE id=?",
            (report["source_request_ids"][0],),
        ).fetchone()
        assert kind["source_name"] == SOURCE_NAME
        assert kind["request_kind"] == REQUEST_KIND
        assert [tuple(row) for row in connection.execute(
            "SELECT source_name,request_kind FROM printer_source_requests ORDER BY id"
        )] == [(SOURCE_NAME, REQUEST_KIND), (SOURCE_NAME, "generic_present_pool_account_batch")]
        assert connection.execute("SELECT COUNT(*) FROM printer_source_responses").fetchone()[0] == 2
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

    @pytest.mark.parametrize("venue,kind", [
        ("pumpswap", REQUEST_KIND),
        ("pumpfun", REQUEST_KIND),
        ("pump-fun", REQUEST_KIND),
        ("pump-amm", REQUEST_KIND),
        ("PUMPSWAP", REQUEST_KIND),
        ("PUMP", "generic_present_pool_account_batch"),
        ("METEORA", "generic_present_pool_account_batch"),
        ("meteora-damm-v2", "generic_present_pool_account_batch"),
        ("unrecognized-offline-venue", "generic_present_pool_account_batch"),
    ])
    def test_provider_venue_labels_route_to_governed_confirmation(self, database, venue, kind):
        _, connection = database
        observation = {"mint": _MINT_A, "pool": _POOL_A, "base_mint": _MINT_A,
                       "quote_mint": WSOL, "venue": venue, "liquidity_usd": 5000.0}
        self._seed_due(connection, [observation])
        calls = []
        pump = fixture_account_batch_transport({_POOL_A: _pool_account(mint=_MINT_A)})
        generic = _generic_transport([observation])

        def transport(context):
            assert context.governor_approved is True
            assert context.execution_path == GOVERNOR_ONLY_EXECUTION_PATH
            assert context.request.request_kind == kind
            calls.append(kind)
            return (pump if kind == REQUEST_KIND else generic)(context)

        # Even unknown venue names require account verification. There is no
        # venue-name exclusion branch in the current queue owner.
        report = process_protocol_confirmation_queue(
            connection, stage_budget=StageBudget.permanent_discovery_default(),
            now=NOW, account_batch_transport=transport,
            generic_account_batch_transport=transport,
        )
        assert calls == [kind]
        assert report["source_requests"] == 1
        assert report["source_failure_ids"] == []
        assert connection.execute("SELECT request_kind FROM printer_source_requests").fetchone()[0] == kind
        assert connection.execute("SELECT COUNT(*) FROM printer_source_responses").fetchone()[0] == 1
        assert report["transport_operations"] == (1 if kind == REQUEST_KIND else 2)
        # Routing is distinct from downstream identity/provenance eligibility.
        # The transport choice alone must never assert final admission authority.

    def test_shared_failure_marks_all_members_source_unavailable(self, database):
        _, connection = database
        self._seed_due(
            connection,
            [
                {
                    "mint": _MINT_A,
                    "pool": _POOL_A,
                    "base_mint": _MINT_A,
                    "quote_mint": WSOL,
                    "venue": "pumpswap",
                    "liquidity_usd": 5000.0,
                },
                {
                    "mint": _MINT_B,
                    "pool": _POOL_B,
                    "base_mint": _MINT_B,
                    "quote_mint": WSOL,
                    "venue": "pumpswap",
                    "liquidity_usd": 5000.0,
                },
            ],
        )
        transport = fixture_account_batch_transport(
            {}, force_error={"error": {"message": "down"}, "response_bytes": 0}
        )
        budget = StageBudget.permanent_discovery_default()
        report = process_protocol_confirmation_queue(
            connection,
            stage_budget=budget,
            now=NOW,
            account_batch_transport=transport,
        )
        assert report["shared_source_failures"] == 1
        assert all(
            o["outcome"] == "SOURCE_UNAVAILABLE"
            for o in report["outcomes"]
            if o.get("transport")
        )

    def test_one_batch_confirms_multiple_candidates(self, database):
        _, connection = database
        self._seed_due(
            connection,
            [
                {
                    "mint": _MINT_A,
                    "pool": _POOL_A,
                    "base_mint": _MINT_A,
                    "quote_mint": WSOL,
                    "venue": "pumpswap",
                    "liquidity_usd": 5000.0,
                },
                {
                    "mint": _MINT_B,
                    "pool": _POOL_B,
                    "base_mint": _MINT_B,
                    "quote_mint": WSOL,
                    "venue": "pump-fun",
                    "liquidity_usd": 5000.0,
                },
            ],
        )
        transport = fixture_account_batch_transport(
            {
                _POOL_A: _pool_account(mint=_MINT_A),
                _POOL_B: _pool_account(mint=_MINT_B),
            }
        )
        budget = StageBudget.permanent_discovery_default()
        report = process_protocol_confirmation_queue(
            connection,
            stage_budget=budget,
            now=NOW,
            account_batch_transport=transport,
        )
        assert report["source_requests"] == 1
        assert sum(
            1 for o in report["outcomes"] if o["outcome"] == "CURRENT_POOL_CONFIRMED"
        ) == 2
        assert budget.used_by_stage["protocol_confirmation"] == 1


class TestReuseHelper:
    def test_confirm_helper_still_authoritative(self):
        conf = confirm_pumpswap_pool_from_account(
            _pool_account(), expected_mint=_MINT_A, pool_address=_POOL_A
        )
        assert protocol_outcome_from_confirm(conf) == "CURRENT_POOL_CONFIRMED"

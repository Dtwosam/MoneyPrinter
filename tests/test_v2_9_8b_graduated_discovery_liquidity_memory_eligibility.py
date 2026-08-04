"""V2-9.8B graduated discovery, early liquidity, memory-eligibility focused proofs.

Offline fixture-only. No providers, runtime, authorization, WINDOW_15M, memory,
retrieval, decisions, positions, trades, audits, or PnL.
"""

from __future__ import annotations

import base64
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    ABOVE_FLOOR_NOMINATED,
    BELOW_LIQUIDITY_FLOOR,
    BROAD_NOMINATED,
    CONTRACT_BLOCKED,
    CURRENT_POOL_CONFIRMED,
    CURRENT_VISIBLE,
    IDENTITY_CONFLICT,
    MEMORY_OBSERVATION_ELIGIBLE,
    MINIMUM_FREEZE_DEPTH,
    OBSERVATION_SURPLUS_TARGET,
    REASON_ABOVE_FLOOR_NOMINATION,
    REASON_BELOW_FLOOR,
    REASON_LIQUIDITY_UNKNOWN,
    SELECTION_FLOOR_USD,
    STAGE_RESERVATIONS,
    StageBudget,
    build_source_request_coverage_manifest,
    freeze_eligible_reserve,
    load_exact_market_states,
    load_retained_market_evidence,
    observation_reserve_depth_status,
    process_protocol_confirmation_queue,
    promote_confirmed_with_retained_liquidity,
    record_fresh_pool_nominations,
    run_geckoterminal_fresh_nomination,
)
from printer_v1.sources.pumpswap import (
    PUMPSWAP_AMM_PROGRAM_ID,
    _PUMPSWAP_POOL_BASE_MINT_OFFSET,
    _b58decode,
)
from printer_v1.sources.pumpswap_pool_account_batch import (
    fixture_account_batch_transport,
)

NOW = "2026-08-04T17:00:00+00:00"
LATER = "2026-08-04T17:10:00+00:00"
EXPIRED_AT = "2026-08-04T18:00:00+00:00"
WSOL = "So11111111111111111111111111111111111111112"
_MINT_A = "6wtZueu89AGwQkGUki3HcerjCDFxLA9PyVUBWQbMpump"
_MINT_B = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
_POOL_A = "DfxsEZga7jwVhwo6JUfWnDD8tg9aSLcv32UYzLQ3SwqD"
_POOL_B = "ECobcS1MSzzAnnzz89xjwRSEYsHAChB7DMbd3G25gwgc"


def _pool_account(owner=PUMPSWAP_AMM_PROGRAM_ID, mint=_MINT_A, total_len=301):
    mb = _b58decode(mint)
    off = _PUMPSWAP_POOL_BASE_MINT_OFFSET
    data = b"\x01" * off + mb + b"\x02" * (total_len - off - len(mb))
    return {"owner": owner, "data": [base64.b64encode(data).decode(), "base64"]}


@pytest.fixture()
def database():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "memory-elig.sqlite3"
        apply_migrations(path)
        connection = sqlite3.connect(str(path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield path, connection
        finally:
            connection.close()


def _obs(
    mint: str,
    pool: str,
    *,
    liquidity_usd: float | None,
    venue: str = "pumpswap",
    quote: str = WSOL,
):
    return {
        "mint": mint,
        "pool": pool,
        "base_mint": mint,
        "quote_mint": quote,
        "venue": venue,
        "liquidity_usd": liquidity_usd,
    }


class TestLiquidityPreservation:
    def test_dexscreener_fresh_nomination_preserves_exact_pool_liquidity(self, database):
        _, connection = database
        report = record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_A, _POOL_A, liquidity_usd=4500.0)],
            source="dexscreener",
            request_id=11,
            now=NOW,
            campaign_id="camp-liq",
            response_id=21,
        )
        assert report["accepted"][0]["liquidity_usd"] == 4500.0
        assert report["accepted"][0]["prefilter_outcome"] == "ABOVE_FLOOR_NOMINATION"
        row = connection.execute(
            """SELECT evidence_json, source_provenance_json, evidence_expires_at
               FROM printer_discovery_reserve_layers
               WHERE mint_identity=? AND pool_address=? AND reserve_layer=?""",
            (_MINT_A, _POOL_A, BROAD_NOMINATED),
        ).fetchone()
        evidence = json.loads(row["evidence_json"])
        assert evidence["liquidity_usd"] == 4500.0
        assert evidence["request_id"] == 11
        assert evidence["response_id"] == 21
        assert evidence["market_evidence_contract_version"]
        assert row["evidence_expires_at"] is not None
        state = load_exact_market_states(connection, mint=_MINT_A)[0]
        assert state["current_reason"] == REASON_ABOVE_FLOOR_NOMINATION
        assert state["current_state"] == CONTRACT_BLOCKED
        above = connection.execute(
            """SELECT 1 FROM printer_discovery_reserve_layers
               WHERE reserve_layer=? AND mint_identity=?""",
            (ABOVE_FLOOR_NOMINATED, _MINT_A),
        ).fetchone()
        assert above is not None

    def test_geckoterminal_fresh_nomination_preserves_liquidity(self, database):
        _, connection = database

        def transport(context):
            return {
                "data": [
                    {
                        "id": "solana_" + _POOL_B,
                        "attributes": {
                            "address": _POOL_B,
                            "base_token_address": _MINT_B,
                            "quote_token_address": WSOL,
                            "dex": "pumpswap",
                            "reserve_in_usd": "6200.5",
                        },
                        "relationships": {
                            "base_token": {
                                "data": {"id": "solana_" + _MINT_B}
                            },
                            "quote_token": {
                                "data": {"id": "solana_" + WSOL}
                            },
                            "dex": {"data": {"id": "pumpswap"}},
                        },
                    }
                ],
                "response_bytes": 400,
            }

        report = run_geckoterminal_fresh_nomination(
            connection,
            request_key="gt-fresh-1",
            now=NOW,
            campaign_id="camp-gt",
            run_id="run-gt",
            cycle_id="cycle-gt",
            transport=transport,
        )
        assert report["nominations"]
        accepted = report["nominations"][0]
        assert accepted["liquidity_usd"] == 6200.5
        assert accepted["prefilter_outcome"] == "ABOVE_FLOOR_NOMINATION"
        evidence = json.loads(
            connection.execute(
                """SELECT evidence_json FROM printer_discovery_reserve_layers
                   WHERE mint_identity=? AND reserve_layer=?""",
                (_MINT_B, BROAD_NOMINATED),
            ).fetchone()[0]
        )
        assert evidence["liquidity_usd"] == 6200.5
        assert evidence["source"] == "geckoterminal"


class TestEarlyLiquidityPrefilter:
    def test_below_floor_consumes_zero_protocol_confirmations(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_A, _POOL_A, liquidity_usd=2999.99)],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-below",
        )
        state = load_exact_market_states(connection, mint=_MINT_A)[0]
        assert state["current_state"] == BELOW_LIQUIDITY_FLOOR
        assert state["current_reason"] == REASON_BELOW_FLOOR
        calls = {"n": 0}

        def transport(context):
            calls["n"] += 1
            raise AssertionError("below-floor must not protocol-confirm")

        budget = StageBudget.permanent_discovery_default()
        report = process_protocol_confirmation_queue(
            connection,
            stage_budget=budget,
            now=NOW,
            account_batch_transport=transport,
        )
        assert calls["n"] == 0
        assert report["source_requests"] == 0
        assert report["batch_count"] == 0
        assert budget.used_by_stage["protocol_confirmation"] == 0

    def test_liquidity_unknown_does_not_enter_protocol_queue(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_A, _POOL_A, liquidity_usd=None)],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-unknown",
        )
        state = load_exact_market_states(connection, mint=_MINT_A)[0]
        assert state["current_reason"] == REASON_LIQUIDITY_UNKNOWN
        budget = StageBudget.permanent_discovery_default()
        report = process_protocol_confirmation_queue(
            connection,
            stage_budget=budget,
            now=NOW,
            account_batch_transport=lambda context: (_ for _ in ()).throw(
                AssertionError("no protocol")
            ),
        )
        assert report["source_requests"] == 0

    def test_above_floor_enters_protocol_confirmation(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_A, _POOL_A, liquidity_usd=SELECTION_FLOOR_USD)],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-above",
        )
        transport = fixture_account_batch_transport(
            {_POOL_A: _pool_account(mint=_MINT_A)}
        )
        budget = StageBudget.permanent_discovery_default()
        report = process_protocol_confirmation_queue(
            connection,
            stage_budget=budget,
            now=NOW,
            campaign_id="camp-above",
            account_batch_transport=transport,
        )
        assert report["source_requests"] == 1
        assert any(
            o["outcome"] == "CURRENT_POOL_CONFIRMED" for o in report["outcomes"]
        )
        assert report["promoted_observation_eligible"]


class TestDirectPromotion:
    def test_confirmed_promotes_with_retained_liquidity_no_second_market(
        self, database
    ):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_A, _POOL_A, liquidity_usd=8000.0)],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-promo",
        )
        transport = fixture_account_batch_transport(
            {_POOL_A: _pool_account(mint=_MINT_A)}
        )
        budget = StageBudget.permanent_discovery_default()
        report = process_protocol_confirmation_queue(
            connection,
            stage_budget=budget,
            now=NOW,
            campaign_id="camp-promo",
            account_batch_transport=transport,
        )
        assert report["promoted_observation_eligible"]
        promo = report["promoted_observation_eligible"][0]
        assert promo["promoted"] is True
        assert promo["requires_market_revalidation"] is False
        assert promo["liquidity_usd"] == 8000.0
        assert report["requires_market_revalidation"] == []
        layer = connection.execute(
            """SELECT categorical_reason, evidence_json FROM printer_discovery_reserve_layers
               WHERE mint_identity=? AND reserve_layer=?""",
            (_MINT_A, MEMORY_OBSERVATION_ELIGIBLE),
        ).fetchone()
        assert layer is not None
        evidence = json.loads(layer["evidence_json"])
        assert evidence["memory_observation_eligible"] is True
        assert evidence["future_action_eligibility"] == "BLOCKED_OR_UNKNOWN"
        state = load_exact_market_states(connection, mint=_MINT_A)[0]
        assert state["current_state"] == CURRENT_VISIBLE

    def test_expired_evidence_requires_revalidation(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[
                {
                    **_obs(_MINT_A, _POOL_A, liquidity_usd=9000.0),
                    "liquidity_evidence_expires_at": "2026-08-04T16:30:00+00:00",
                }
            ],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-exp",
        )
        # Force protocol confirm without auto-promotion path by direct promote call.
        retained = load_retained_market_evidence(
            connection, mint=_MINT_A, pool=_POOL_A, at=EXPIRED_AT
        )
        assert retained is not None
        assert retained["fresh"] is False
        promotion = promote_confirmed_with_retained_liquidity(
            connection,
            mint=_MINT_A,
            pool=_POOL_A,
            venue="pumpswap",
            now=EXPIRED_AT,
            campaign_id="camp-exp",
            protocol_request_id=99,
        )
        assert promotion["promoted"] is False
        assert promotion["requires_market_revalidation"] is True


class TestExactPoolSafety:
    def test_owner_mismatch_is_candidate_local(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[
                _obs(_MINT_A, _POOL_A, liquidity_usd=5000.0),
                _obs(_MINT_B, _POOL_B, liquidity_usd=5000.0),
            ],
            source="geckoterminal",
            request_id=1,
            now=NOW,
            campaign_id="camp-own",
        )
        other_owner = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
        transport = fixture_account_batch_transport(
            {
                _POOL_A: _pool_account(owner=other_owner, mint=_MINT_A),
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
        by_pool = {o["pool"]: o["outcome"] for o in report["outcomes"] if o.get("transport")}
        assert by_pool[_POOL_A] == "POOL_OWNER_MISMATCH"
        assert by_pool[_POOL_B] == "CURRENT_POOL_CONFIRMED"
        # B still promotes; A does not poison the batch.
        assert any(p["pool"] == _POOL_B for p in report["promoted_observation_eligible"])

    def test_base_mint_mismatch_is_candidate_local(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_A, _POOL_A, liquidity_usd=5000.0)],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-mint",
        )
        transport = fixture_account_batch_transport(
            {_POOL_A: _pool_account(mint=_MINT_B)}  # wrong mint at base_mint@43
        )
        budget = StageBudget.permanent_discovery_default()
        report = process_protocol_confirmation_queue(
            connection,
            stage_budget=budget,
            now=NOW,
            account_batch_transport=transport,
        )
        assert report["outcomes"][0]["outcome"] == "BASE_MINT_MISMATCH"
        assert report["promoted_observation_eligible"] == []

    def test_dex_gecko_require_no_separate_graduation_proof(self, database):
        _, connection = database
        # No graduated registry row seeded.
        report = record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_A, _POOL_A, liquidity_usd=7000.0)],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-no-grad",
        )
        assert report["accepted"][0]["protocol_confirmation_due"] is True
        reg = connection.execute(
            "SELECT count(*) AS c FROM printer_pumpswap_graduated_candidate_registry"
        ).fetchone()["c"]
        assert reg == 0


class TestMemoryObservationEligibility:
    def test_holder_concentration_extreme_remains_observation_eligible(self):
        candidates = [
            {
                "mint": f"Mint{i}",
                "pool": f"Pool{i}",
                "memory_observation_eligible": True,
                "evidence_expires_at": "2026-08-04T18:00:00+00:00",
                "holder_condition": "HOLDER_CONCENTRATION_EXTREME",
                "holder_evidence_status": "COMPLETE",
                "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
                "liquidity_usd": 10_000.0 + i * 1000,
            }
            for i in range(4)
        ]
        frozen = freeze_eligible_reserve(
            candidates, cycle_seed="neutral-seed", at=NOW
        )
        assert len(frozen.selected) == 2
        assert len(frozen.alternates) == 2
        for item in list(frozen.selected) + list(frozen.alternates):
            assert item["memory_observation_eligible"] is True
            assert item["holder_condition"] == "HOLDER_CONCENTRATION_EXTREME"
            assert item["future_action_eligibility"] == "BLOCKED_OR_UNKNOWN"

    def test_future_action_eligibility_remains_blocked_or_unknown(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_A, _POOL_A, liquidity_usd=5000.0)],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-action",
        )
        transport = fixture_account_batch_transport(
            {_POOL_A: _pool_account(mint=_MINT_A)}
        )
        report = process_protocol_confirmation_queue(
            connection,
            stage_budget=StageBudget.permanent_discovery_default(),
            now=NOW,
            campaign_id="camp-action",
            account_batch_transport=transport,
        )
        promo = report["promoted_observation_eligible"][0]
        assert promo["future_action_eligibility"] == "BLOCKED_OR_UNKNOWN"
        evidence = json.loads(
            connection.execute(
                """SELECT evidence_json FROM printer_discovery_reserve_layers
                   WHERE reserve_layer=? AND mint_identity=?""",
                (MEMORY_OBSERVATION_ELIGIBLE, _MINT_A),
            ).fetchone()[0]
        )
        assert evidence["future_action_eligibility"] == "BLOCKED_OR_UNKNOWN"


class TestNeutralFreeze:
    def test_freeze_two_selected_two_alternates_from_four(self):
        candidates = [
            {
                "mint": f"Mint{i:02d}",
                "pool": f"Pool{i:02d}",
                "memory_observation_eligible": True,
                "evidence_expires_at": "2026-08-04T19:00:00+00:00",
            }
            for i in range(4)
        ]
        frozen = freeze_eligible_reserve(
            candidates, cycle_seed="freeze-seed-a", at=NOW
        )
        assert len(frozen.selected) == 2
        assert len(frozen.alternates) == 2
        selected_mints = {item["mint"] for item in frozen.selected}
        alternate_mints = {item["mint"] for item in frozen.alternates}
        assert selected_mints.isdisjoint(alternate_mints)
        assert len(selected_mints | alternate_mints) == 4

    def test_selection_ignores_liquidity_source_order_holder_and_provider(self):
        # Same identities, swapped liquidity magnitudes and holder labels.
        base = [
            {
                "mint": "Mint00",
                "pool": "Pool00",
                "memory_observation_eligible": True,
                "evidence_expires_at": "2026-08-04T19:00:00+00:00",
                "liquidity_usd": 3_000.0,
                "holder_condition": "HOLDER_CONCENTRATION_HEALTHY",
                "source": "dexscreener",
            },
            {
                "mint": "Mint01",
                "pool": "Pool01",
                "memory_observation_eligible": True,
                "evidence_expires_at": "2026-08-04T19:00:00+00:00",
                "liquidity_usd": 9_999_999.0,
                "holder_condition": "HOLDER_CONCENTRATION_EXTREME",
                "source": "geckoterminal",
            },
            {
                "mint": "Mint02",
                "pool": "Pool02",
                "memory_observation_eligible": True,
                "evidence_expires_at": "2026-08-04T19:00:00+00:00",
                "liquidity_usd": 3_001.0,
                "holder_condition": "UNKNOWN",
                "source": "dexscreener",
            },
            {
                "mint": "Mint03",
                "pool": "Pool03",
                "memory_observation_eligible": True,
                "evidence_expires_at": "2026-08-04T19:00:00+00:00",
                "liquidity_usd": 50_000.0,
                "holder_condition": "HOLDER_CONCENTRATION_CONCENTRATED",
                "source": "geckoterminal",
            },
        ]
        a = freeze_eligible_reserve(base, cycle_seed="same-seed", at=NOW)
        b = freeze_eligible_reserve(
            list(reversed(base)), cycle_seed="same-seed", at=NOW
        )
        assert [x["mint"] for x in a.selected] == [x["mint"] for x in b.selected]
        assert [x["mint"] for x in a.alternates] == [x["mint"] for x in b.alternates]
        # Depth status semantics.
        status = observation_reserve_depth_status(4)
        assert status["freeze_depth_met"] is True
        assert status["surplus_target_met"] is False
        assert status["surplus_status"] == "SURPLUS_TARGET_NOT_MET"
        assert observation_reserve_depth_status(8)["surplus_target_met"] is True
        assert observation_reserve_depth_status(3)["coverage_blocker"] is True
        assert MINIMUM_FREEZE_DEPTH == 4
        assert OBSERVATION_SURPLUS_TARGET == 8


class TestProtocolStageAccounting:
    def test_protocol_emits_one_sealed_stage_with_identities(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[
                _obs(_MINT_A, _POOL_A, liquidity_usd=5000.0),
                _obs(_MINT_B, _POOL_B, liquidity_usd=5000.0),
            ],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-seal",
        )
        sealed_blocks: list[dict] = []
        transport = fixture_account_batch_transport(
            {
                _POOL_A: _pool_account(mint=_MINT_A),
                _POOL_B: _pool_account(mint=_MINT_B),
            }
        )
        report = process_protocol_confirmation_queue(
            connection,
            stage_budget=StageBudget.permanent_discovery_default(),
            now=NOW,
            campaign_id="camp-seal",
            run_id="run-seal",
            cycle_id="cycle-seal",
            account_batch_transport=transport,
            stage_evidence_sink=sealed_blocks.append,
        )
        assert report["sealed_stage_evidence"] is not None
        assert len(sealed_blocks) == 1
        sealed = sealed_blocks[0]
        assert sealed["stage_kind"] == "PROTOCOL_CONFIRMATION"
        assert sealed["stage_sequence"] == 1
        transports = sealed.get("transport_operations") or []
        assert len(transports) >= 1
        validations = sealed.get("local_validation_identities") or []
        assert len(validations) == report["local_validation_steps"]
        assert report["source_request_coverage"]
        coverage = build_source_request_coverage_manifest(
            report["source_request_coverage"]
        )
        assert len(coverage) == len(report["source_request_ids"])
        for entry in coverage:
            assert entry["logical_stage_id"]
            assert entry["source_name"]
            assert entry["request_kind"]

    def test_request_and_transport_counts_remain_separate(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_A, _POOL_A, liquidity_usd=5000.0)],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-sep",
        )
        report = process_protocol_confirmation_queue(
            connection,
            stage_budget=StageBudget.permanent_discovery_default(),
            now=NOW,
            campaign_id="camp-sep",
            run_id="run-sep",
            cycle_id="cycle-sep",
            account_batch_transport=fixture_account_batch_transport(
                {_POOL_A: _pool_account(mint=_MINT_A)}
            ),
            stage_evidence_sink=lambda _s: None,
        )
        # Separate surfaces — never equate request count with transport count
        # as an equality invariant (transport may be 1 per request here).
        assert "source_requests" in report
        assert "transport_operations" in report
        assert report["source_requests"] == 1
        assert report["transport_operations"] >= 1
        coverage = report["source_request_coverage"][0]
        assert coverage["transport_identity_count"] >= 1
        assert coverage["normalized_member_count"] >= 1

    def test_honest_insufficient_coverage_depth_status(self):
        status = observation_reserve_depth_status(1)
        assert status["coverage_blocker"] is True
        assert status["surplus_status"] == "INSUFFICIENT_OBSERVATION_COVERAGE"
        # Durable terminal report surface is the status itself (honest blocker).
        assert status["observation_eligible_count"] == 1

    def test_stage_ceilings_and_flat_30_unchanged(self):
        total = sum(cap for _, cap in STAGE_RESERVATIONS)
        assert total == 30
        by_stage = dict(STAGE_RESERVATIONS)
        assert by_stage == {
            "intake": 3,
            "market_batching": 2,
            "reconciliation": 6,
            "protocol_confirmation": 7,
            "holder_safety": 8,
            "final_refresh_handoff": 4,
        }
        budget = StageBudget.permanent_discovery_default()
        assert budget.available("protocol_confirmation") == 7
        assert budget.available("market_batching") == 2

    def test_market_batch_stage_sequencing_helpers_remain_monotonic(self):
        from printer_v1.discovery.permanent_discovery_availability import (
            build_mint_market_batch_request_key,
            parse_mint_market_batch_stage_sequence,
        )

        key1 = build_mint_market_batch_request_key(
            request_key_prefix="camp", stage_sequence=1, kind="primary"
        )
        key2 = build_mint_market_batch_request_key(
            request_key_prefix="camp", stage_sequence=2, kind="primary"
        )
        assert parse_mint_market_batch_stage_sequence(key1) == 1
        assert parse_mint_market_batch_stage_sequence(key2) == 2
        assert parse_mint_market_batch_stage_sequence(key2) > (
            parse_mint_market_batch_stage_sequence(key1) or 0
        )

    def test_no_source_governor_bypass_protocol_uses_governed_requests(
        self, database
    ):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_A, _POOL_A, liquidity_usd=5000.0)],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-gov",
        )
        report = process_protocol_confirmation_queue(
            connection,
            stage_budget=StageBudget.permanent_discovery_default(),
            now=NOW,
            campaign_id="camp-gov",
            account_batch_transport=fixture_account_batch_transport(
                {_POOL_A: _pool_account(mint=_MINT_A)}
            ),
        )
        assert report["source_request_ids"]
        rid = report["source_request_ids"][0]
        row = connection.execute(
            "SELECT source_name, request_kind FROM printer_source_requests WHERE id=?",
            (rid,),
        ).fetchone()
        assert row is not None
        assert row["source_name"]
        assert row["request_kind"]


class TestSchemaMigration052:
    def test_fresh_database_applies_memory_observation_layer(self, database):
        path, connection = database
        # apply_migrations already applied 052 via fixture.
        layers = connection.execute(
            """SELECT sql FROM sqlite_master
               WHERE type='table' AND name='printer_discovery_reserve_layers'"""
        ).fetchone()[0]
        assert "MEMORY_OBSERVATION_ELIGIBLE" in layers
        assert "ABOVE_FLOOR_NOMINATED" in layers
        # Row can be written for the new layer after a market identity exists.
        record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_A, _POOL_A, liquidity_usd=5000.0)],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-mig",
        )
        transport = fixture_account_batch_transport(
            {_POOL_A: _pool_account(mint=_MINT_A)}
        )
        process_protocol_confirmation_queue(
            connection,
            stage_budget=StageBudget.permanent_discovery_default(),
            now=NOW,
            campaign_id="camp-mig",
            account_batch_transport=transport,
        )
        count = connection.execute(
            """SELECT count(*) AS c FROM printer_discovery_reserve_layers
               WHERE reserve_layer=?""",
            (MEMORY_OBSERVATION_ELIGIBLE,),
        ).fetchone()["c"]
        assert count == 1
        # Integrity
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        # Migration ledger includes 052
        applied = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations"
            ).fetchall()
        }
        assert "052_memory_observation_eligibility_layers.sql" in applied

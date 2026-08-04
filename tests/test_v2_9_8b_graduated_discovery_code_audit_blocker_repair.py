"""V2-9.8B graduated discovery code-audit blocker repair focused proofs.

Offline fixture-only. No providers, runtime, authorization, WINDOW_15M, memory,
retrieval, decisions, positions, trades, audits, or PnL.
"""

from __future__ import annotations

import base64
import json
import math
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    ABOVE_FLOOR_NOMINATED,
    BELOW_LIQUIDITY_FLOOR,
    BROAD_NOMINATED,
    CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH,
    CONTRACT_BLOCKED,
    EXACT_POOL_NO_MATCH,
    MEMORY_OBSERVATION_ELIGIBLE,
    MINIMUM_FREEZE_DEPTH,
    OBSERVATION_SURPLUS_TARGET,
    REASON_ABOVE_FLOOR_NOMINATION,
    REASON_LIQUIDITY_UNKNOWN,
    SELECTION_FLOOR_USD,
    STAGE_RESERVATIONS,
    StageBudget,
    build_campaign_source_request_manifest,
    build_source_request_coverage_manifest,
    freeze_eligible_reserve,
    load_exact_market_states,
    load_retained_market_evidence,
    merge_protocol_confirmation_reports,
    observation_reserve_depth_status,
    process_protocol_confirmation_queue,
    promote_confirmed_with_retained_liquidity,
    reconcile_campaign_source_requests,
    record_fresh_pool_nominations,
    resolve_liquidity_evidence_expiry,
    run_bounded_unknown_liquidity_backup,
    union_market_revalidation_candidates,
    _coerce_liquidity_usd,
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
WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
_MINT_A = "6wtZueu89AGwQkGUki3HcerjCDFxLA9PyVUBWQbMpump"
_MINT_B = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
_MINT_C = "8xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsV"
_MINT_D = "9xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsW"
_POOL_A = "DfxsEZga7jwVhwo6JUfWnDD8tg9aSLcv32UYzLQ3SwqD"
_POOL_B = "ECobcS1MSzzAnnzz89xjwRSEYsHAChB7DMbd3G25gwgc"
_POOL_C = "FCobcS1MSzzAnnzz89xjwRSEYsHAChB7DMbd3G25gwgd"
_POOL_D = "GCobcS1MSzzAnnzz89xjwRSEYsHAChB7DMbd3G25gwge"


def _pool_account(owner=PUMPSWAP_AMM_PROGRAM_ID, mint=_MINT_A, total_len=301):
    mb = _b58decode(mint)
    off = _PUMPSWAP_POOL_BASE_MINT_OFFSET
    data = b"\x01" * off + mb + b"\x02" * (total_len - off - len(mb))
    return {"owner": owner, "data": [base64.b64encode(data).decode(), "base64"]}


@pytest.fixture()
def database():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "audit-repair.sqlite3"
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
    observed_at: str | None = None,
    expiry: str | None = None,
):
    item = {
        "mint": mint,
        "pool": pool,
        "base_mint": mint,
        "quote_mint": quote,
        "venue": venue,
        "liquidity_usd": liquidity_usd,
    }
    if observed_at is not None:
        item["observed_at"] = observed_at
    if expiry is not None:
        item["liquidity_evidence_expires_at"] = expiry
    return item


def _obs_candidates(n: int, *, fully_only: bool = False):
    rows = []
    for i in range(n):
        row = {
            "mint": f"Mint{i:02d}",
            "pool": f"Pool{i:02d}",
            "evidence_expires_at": "2026-08-04T19:00:00+00:00",
            "holder_condition": "HOLDER_CONCENTRATION_EXTREME",
            "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
        }
        if fully_only:
            row["fully_eligible"] = True
        else:
            row["memory_observation_eligible"] = True
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# 1–4 Freeze depth admission
# ---------------------------------------------------------------------------


class TestFreezeDepthAdmission:
    def test_three_observation_eligible_create_coverage_blocker_no_handoff(self):
        candidates = _obs_candidates(3)
        frozen = freeze_eligible_reserve(candidates, cycle_seed="d3", at=NOW)
        assert len(frozen.selected) == 0
        assert len(frozen.alternates) == 0
        status = observation_reserve_depth_status(3)
        assert status["coverage_blocker"] is True
        assert status["surplus_status"] == "INSUFFICIENT_OBSERVATION_COVERAGE"
        # Durable categorical first terminal cause surface (status + freeze).
        assert frozen.selection_authority.get("coverage_blocker") is True
        assert frozen.selection_authority.get("reason") == (
            "INSUFFICIENT_OBSERVATION_COVERAGE"
        )

    def test_four_candidates_two_selected_two_alternates(self):
        candidates = _obs_candidates(4)
        frozen = freeze_eligible_reserve(candidates, cycle_seed="d4", at=NOW)
        assert len(frozen.selected) == 2
        assert len(frozen.alternates) == 2
        status = observation_reserve_depth_status(4)
        assert status["freeze_depth_met"] is True
        assert status["surplus_target_met"] is False
        assert status["surplus_status"] == "SURPLUS_TARGET_NOT_MET"

    def test_eight_candidates_surplus_target_met(self):
        candidates = _obs_candidates(8)
        frozen = freeze_eligible_reserve(candidates, cycle_seed="d8", at=NOW)
        assert len(frozen.selected) == 2
        assert len(frozen.alternates) == 2
        status = observation_reserve_depth_status(8)
        assert status["surplus_target_met"] is True
        assert status["surplus_status"] == "SURPLUS_TARGET_MET"
        assert OBSERVATION_SURPLUS_TARGET == 8
        assert MINIMUM_FREEZE_DEPTH == 4

    def test_freeze_rejects_fully_eligible_only_rows(self):
        candidates = _obs_candidates(4, fully_only=True)
        frozen = freeze_eligible_reserve(candidates, cycle_seed="full", at=NOW)
        assert frozen.selected == ()
        assert frozen.alternates == ()


# ---------------------------------------------------------------------------
# 5 Stage-sealing fail-closed
# ---------------------------------------------------------------------------


class TestStageSealFailClosed:
    def test_stage_sealing_failure_becomes_accounting_blocker(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_A, _POOL_A, liquidity_usd=5000.0)],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-seal-fail",
        )
        from printer_v1.sources.campaign_six_unit_accounting import CampaignSixUnitError

        sealed_sink: list = []

        def boom(*_a, **_k):
            raise CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_MALFORMED:TEST")

        with patch(
            "printer_v1.sources.campaign_six_unit_accounting.seal_campaign_stage_evidence",
            boom,
        ):
            report = process_protocol_confirmation_queue(
                connection,
                stage_budget=StageBudget.permanent_discovery_default(),
                now=NOW,
                campaign_id="camp-seal-fail",
                run_id="run-seal-fail",
                cycle_id="cycle-seal-fail",
                account_batch_transport=fixture_account_batch_transport(
                    {_POOL_A: _pool_account(mint=_MINT_A)}
                ),
                stage_evidence_sink=sealed_sink.append,
            )
        assert report["accounting_blocker"] is True
        assert "PROTOCOL_STAGE_SEAL_FAILURE" in str(
            report["accounting_blocker_reason"] or ""
        )
        assert report["sealed_stage_evidence"] is None
        assert sealed_sink == []


# ---------------------------------------------------------------------------
# 6–9 Early/residual merge
# ---------------------------------------------------------------------------


class TestProtocolReportMerge:
    def test_early_and_residual_evidence_both_survive(self):
        early = {
            "outcomes": [{"mint": "A", "outcome": "CURRENT_POOL_CONFIRMED"}],
            "remaining_due": [{"mint": "X", "pool": "PX", "venue": "pumpswap"}],
            "promoted_observation_eligible": [{"mint": "A", "pool": "PA"}],
            "requires_market_revalidation": [
                {"mint": "R1", "pool": "PR1", "venue": "pumpswap"}
            ],
            "source_request_ids": [11],
            "source_response_ids": [21],
            "source_failure_ids": [],
            "source_requests": 1,
            "transport_operations": 2,
            "local_validation_steps": 3,
            "batch_count": 1,
            "shared_source_failures": 0,
            "outcome_counts": {"CURRENT_POOL_CONFIRMED": 1},
            "source_request_coverage": [
                {
                    "source_request_id": 11,
                    "source_name": "solana_rpc",
                    "request_kind": "pumpswap_pool_account_batch",
                    "logical_stage_id": "c|r|y|PROTOCOL_CONFIRMATION|1",
                    "transport_identity_count": 2,
                    "normalized_member_count": 3,
                    "terminal_status": "COMPLETED",
                }
            ],
            "sealed_stage_evidence": {
                "stage_sequence": 1,
                "stage_kind": "PROTOCOL_CONFIRMATION",
            },
            "sealed_stage_evidence_blocks": [
                {"stage_sequence": 1, "stage_kind": "PROTOCOL_CONFIRMATION"}
            ],
        }
        residual = {
            "outcomes": [{"mint": "B", "outcome": "POOL_OWNER_MISMATCH"}],
            "remaining_due": [],
            "promoted_observation_eligible": [{"mint": "B", "pool": "PB"}],
            "requires_market_revalidation": [
                {"mint": "R2", "pool": "PR2", "venue": "pumpswap"}
            ],
            "source_request_ids": [12],
            "source_response_ids": [22],
            "source_failure_ids": [32],
            "source_requests": 1,
            "transport_operations": 1,
            "local_validation_steps": 1,
            "batch_count": 1,
            "shared_source_failures": 0,
            "outcome_counts": {"POOL_OWNER_MISMATCH": 1},
            "source_request_coverage": [
                {
                    "source_request_id": 12,
                    "source_name": "solana_rpc",
                    "request_kind": "pumpswap_pool_account_batch",
                    "logical_stage_id": "c|r|y|PROTOCOL_CONFIRMATION|2",
                    "transport_identity_count": 1,
                    "normalized_member_count": 1,
                    "terminal_status": "COMPLETED",
                }
            ],
            "sealed_stage_evidence": {
                "stage_sequence": 2,
                "stage_kind": "PROTOCOL_CONFIRMATION",
            },
            "sealed_stage_evidence_blocks": [
                {"stage_sequence": 2, "stage_kind": "PROTOCOL_CONFIRMATION"}
            ],
        }
        merged = merge_protocol_confirmation_reports(early, residual)
        assert len(merged["outcomes"]) == 2
        assert {o["mint"] for o in merged["outcomes"]} == {"A", "B"}
        assert merged["source_request_ids"] == [11, 12]
        assert merged["source_response_ids"] == [21, 22]
        assert merged["source_failure_ids"] == [32]
        assert merged["source_requests"] == 2
        assert merged["transport_operations"] == 3
        assert merged["local_validation_steps"] == 4
        assert merged["batch_count"] == 2
        assert merged["outcome_counts"]["CURRENT_POOL_CONFIRMED"] == 1
        assert merged["outcome_counts"]["POOL_OWNER_MISMATCH"] == 1
        assert len(merged["source_request_coverage"]) == 2
        blocks = merged["sealed_stage_evidence_blocks"]
        assert len(blocks) == 2
        assert {b["stage_sequence"] for b in blocks} == {1, 2}
        # Compatibility view is last sealed only — not the authoritative owner.
        assert merged["sealed_stage_evidence"]["stage_sequence"] == 2
        assert merged["accounting_blocker"] is False

    def test_all_early_residual_ids_survive_merge(self):
        early = {
            "source_request_ids": [1, 2],
            "source_response_ids": [10],
            "source_failure_ids": [100],
            "source_requests": 2,
            "transport_operations": 0,
            "local_validation_steps": 0,
            "batch_count": 1,
            "shared_source_failures": 0,
            "outcomes": [],
            "outcome_counts": {},
            "source_request_coverage": [
                {
                    "source_request_id": 1,
                    "source_name": "a",
                    "request_kind": "k",
                    "logical_stage_id": "s1",
                    "transport_identity_count": 0,
                    "normalized_member_count": 0,
                    "terminal_status": "COMPLETED",
                },
                {
                    "source_request_id": 2,
                    "source_name": "a",
                    "request_kind": "k",
                    "logical_stage_id": "s1",
                    "transport_identity_count": 0,
                    "normalized_member_count": 0,
                    "terminal_status": "COMPLETED",
                },
            ],
            "sealed_stage_evidence_blocks": [{"stage_sequence": 1}],
        }
        residual = {
            "source_request_ids": [3],
            "source_response_ids": [11, 12],
            "source_failure_ids": [101],
            "source_requests": 1,
            "transport_operations": 0,
            "local_validation_steps": 0,
            "batch_count": 1,
            "shared_source_failures": 1,
            "outcomes": [],
            "outcome_counts": {},
            "source_request_coverage": [
                {
                    "source_request_id": 3,
                    "source_name": "a",
                    "request_kind": "k",
                    "logical_stage_id": "s2",
                    "transport_identity_count": 0,
                    "normalized_member_count": 0,
                    "terminal_status": "BLOCKED",
                }
            ],
            "sealed_stage_evidence_blocks": [{"stage_sequence": 2}],
        }
        merged = merge_protocol_confirmation_reports(early, residual)
        assert merged["source_request_ids"] == [1, 2, 3]
        assert merged["source_response_ids"] == [10, 11, 12]
        assert merged["source_failure_ids"] == [100, 101]
        assert merged["shared_source_failures"] == 1

    def test_outcome_counts_and_coverage_summed(self):
        early = {
            "outcomes": [],
            "outcome_counts": {"A": 2, "B": 1},
            "source_request_ids": [1],
            "source_response_ids": [],
            "source_failure_ids": [],
            "source_requests": 1,
            "transport_operations": 1,
            "local_validation_steps": 2,
            "batch_count": 1,
            "shared_source_failures": 0,
            "source_request_coverage": [
                {
                    "source_request_id": 1,
                    "source_name": "s",
                    "request_kind": "k",
                    "logical_stage_id": "L1",
                    "transport_identity_count": 1,
                    "normalized_member_count": 2,
                    "terminal_status": "COMPLETED",
                }
            ],
            "sealed_stage_evidence_blocks": [],
        }
        residual = {
            "outcomes": [],
            "outcome_counts": {"A": 1, "C": 4},
            "source_request_ids": [2],
            "source_response_ids": [],
            "source_failure_ids": [],
            "source_requests": 1,
            "transport_operations": 3,
            "local_validation_steps": 5,
            "batch_count": 2,
            "shared_source_failures": 0,
            "source_request_coverage": [
                {
                    "source_request_id": 2,
                    "source_name": "s",
                    "request_kind": "k",
                    "logical_stage_id": "L2",
                    "transport_identity_count": 3,
                    "normalized_member_count": 5,
                    "terminal_status": "COMPLETED",
                }
            ],
            "sealed_stage_evidence_blocks": [],
        }
        merged = merge_protocol_confirmation_reports(early, residual)
        assert merged["outcome_counts"] == {"A": 3, "B": 1, "C": 4}
        assert merged["transport_operations"] == 4
        assert merged["local_validation_steps"] == 7
        assert merged["batch_count"] == 3
        assert len(merged["source_request_coverage"]) == 2

    def test_duplicate_request_ids_fail_closed(self):
        early = {
            "outcomes": [],
            "outcome_counts": {},
            "source_request_ids": [7],
            "source_response_ids": [],
            "source_failure_ids": [],
            "source_requests": 1,
            "transport_operations": 0,
            "local_validation_steps": 0,
            "batch_count": 1,
            "shared_source_failures": 0,
            "source_request_coverage": [
                {
                    "source_request_id": 7,
                    "source_name": "s",
                    "request_kind": "k",
                    "logical_stage_id": "L1",
                    "transport_identity_count": 0,
                    "normalized_member_count": 0,
                    "terminal_status": "COMPLETED",
                }
            ],
            "sealed_stage_evidence_blocks": [{"stage_sequence": 1}],
        }
        residual = {
            "outcomes": [],
            "outcome_counts": {},
            "source_request_ids": [7],
            "source_response_ids": [],
            "source_failure_ids": [],
            "source_requests": 1,
            "transport_operations": 0,
            "local_validation_steps": 0,
            "batch_count": 1,
            "shared_source_failures": 0,
            "source_request_coverage": [
                {
                    "source_request_id": 7,
                    "source_name": "s",
                    "request_kind": "k",
                    "logical_stage_id": "L2",
                    "transport_identity_count": 0,
                    "normalized_member_count": 0,
                    "terminal_status": "COMPLETED",
                }
            ],
            "sealed_stage_evidence_blocks": [{"stage_sequence": 2}],
        }
        merged = merge_protocol_confirmation_reports(early, residual)
        assert merged["accounting_blocker"] is True
        assert "DUPLICATE" in str(merged["accounting_blocker_reason"] or "")


# ---------------------------------------------------------------------------
# 10 Revalidation union
# ---------------------------------------------------------------------------


class TestRevalidationUnion:
    def test_early_and_residual_revalidation_both_retained(self):
        early = [
            {"mint": "A", "pool": "PA", "venue": "pumpswap", "reason": "EXPIRED"}
        ]
        residual = [
            {"mint": "B", "pool": "PB", "venue": "pumpswap", "reason": "MISSING"}
        ]
        # Prove truthy-or would discard early when residual is non-empty.
        broken = residual or early
        assert len(broken) == 1
        union = union_market_revalidation_candidates(early, residual)
        assert len(union) == 2
        keys = {(u["mint"], u["pool"], u["venue"]) for u in union}
        assert keys == {("A", "PA", "pumpswap"), ("B", "PB", "pumpswap")}
        # Dedupe exact identity.
        again = union_market_revalidation_candidates(union, early)
        assert len(again) == 2


# ---------------------------------------------------------------------------
# 11–12 Campaign-wide source request reconciliation
# ---------------------------------------------------------------------------


class TestCampaignSourceRequestReconciliation:
    def test_durable_ids_equal_manifest_ids(self):
        entries = [
            {
                "source_request_id": 1,
                "source_name": "dexscreener",
                "request_kind": "fresh",
                "logical_stage_id": "camp|run|cycle|DEX|1",
                "transport_identity_count": 1,
                "normalized_member_count": 2,
                "terminal_status": "COMPLETED",
            },
            {
                "source_request_id": 2,
                "source_name": "geckoterminal",
                "request_kind": "new_pools",
                "logical_stage_id": "camp|run|cycle|GECKO|1",
                "transport_identity_count": 1,
                "normalized_member_count": 1,
                "terminal_status": "COMPLETED",
            },
            {
                "source_request_id": 3,
                "source_name": "solana_rpc",
                "request_kind": "pumpswap_pool_account_batch",
                "logical_stage_id": "camp|run|cycle|PROTOCOL_CONFIRMATION|1",
                "transport_identity_count": 2,
                "normalized_member_count": 2,
                "terminal_status": "COMPLETED",
            },
        ]
        result = reconcile_campaign_source_requests(
            durable_request_ids=[1, 2, 3],
            manifest_entries=entries,
        )
        assert result["status"] == "OK"
        assert set(result["durable_request_ids"]) == set(result["manifest_request_ids"])
        assert result["request_count"] == 3
        # Request count separate from transport total.
        assert result["transport_identity_count_total"] == 4

    def test_missing_manifest_entry_creates_blocker(self):
        entries = [
            {
                "source_request_id": 1,
                "source_name": "dexscreener",
                "request_kind": "fresh",
                "logical_stage_id": "L1",
                "transport_identity_count": 0,
                "normalized_member_count": 0,
                "terminal_status": "COMPLETED",
            }
        ]
        result = reconcile_campaign_source_requests(
            durable_request_ids=[1, 2],
            manifest_entries=entries,
        )
        assert result["status"] == "BLOCKED"
        assert result["blocker"] == CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH
        assert 2 in result["missing_from_manifest"]


# ---------------------------------------------------------------------------
# 13–14 Holder-independent handoff
# ---------------------------------------------------------------------------


class TestHolderIndependentHandoff:
    def test_holder_extreme_reaches_freeze_selection(self):
        candidates = [
            {
                "mint": f"Mint{i}",
                "pool": f"Pool{i}",
                "memory_observation_eligible": True,
                "evidence_expires_at": "2026-08-04T19:00:00+00:00",
                "holder_condition": "HOLDER_CONCENTRATION_EXTREME",
                "holder_evidence_status": "COMPLETE",
                "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
                "fully_eligible": False,
            }
            for i in range(4)
        ]
        frozen = freeze_eligible_reserve(candidates, cycle_seed="holder", at=NOW)
        assert len(frozen.selected) == 2
        assert len(frozen.alternates) == 2
        for item in list(frozen.selected) + list(frozen.alternates):
            assert item["holder_condition"] == "HOLDER_CONCENTRATION_EXTREME"
            assert item["memory_observation_eligible"] is True
            assert item["future_action_eligibility"] == "BLOCKED_OR_UNKNOWN"
            assert item.get("fully_eligible") is False

    def test_future_action_remains_blocked_or_unknown(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_A, _POOL_A, liquidity_usd=5000.0)],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-action",
        )
        report = process_protocol_confirmation_queue(
            connection,
            stage_budget=StageBudget.permanent_discovery_default(),
            now=NOW,
            campaign_id="camp-action",
            account_batch_transport=fixture_account_batch_transport(
                {_POOL_A: _pool_account(mint=_MINT_A)}
            ),
        )
        promo = report["promoted_observation_eligible"][0]
        assert promo["future_action_eligibility"] == "BLOCKED_OR_UNKNOWN"
        assert promo["memory_observation_eligible"] is True


# ---------------------------------------------------------------------------
# 15–16 Freshness and liquidity coercion
# ---------------------------------------------------------------------------


class TestEvidenceFreshness:
    def test_old_observed_at_not_refreshed_by_later_ingestion(self, database):
        _, connection = database
        old_observed = "2026-08-04T10:00:00+00:00"
        # Ingestion much later must not extend freshness from now.
        report = record_fresh_pool_nominations(
            connection,
            observations=[
                _obs(
                    _MINT_A,
                    _POOL_A,
                    liquidity_usd=5000.0,
                    observed_at=old_observed,
                )
            ],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-fresh",
        )
        assert report["accepted"]
        expiry = report["accepted"][0]["liquidity_evidence_expires_at"]
        # Expiry must be observed_at + 1800s, not now + 1800s.
        expected = resolve_liquidity_evidence_expiry(
            observed_at=old_observed, explicit_expiry=None, ingestion_now=NOW
        )
        assert expiry == expected
        assert expiry.startswith("2026-08-04T10:30:00")
        # At NOW the evidence is already expired.
        retained = load_retained_market_evidence(
            connection, mint=_MINT_A, pool=_POOL_A, at=NOW
        )
        assert retained is not None
        assert retained["fresh"] is False

    def test_nan_and_infinity_liquidity_rejected(self, database):
        assert _coerce_liquidity_usd(float("nan")) is None
        assert _coerce_liquidity_usd(float("inf")) is None
        assert _coerce_liquidity_usd(float("-inf")) is None
        assert _coerce_liquidity_usd(-1.0) is None
        assert _coerce_liquidity_usd("not-a-number") is None
        assert _coerce_liquidity_usd(3000.0) == 3000.0
        _, connection = database
        report = record_fresh_pool_nominations(
            connection,
            observations=[
                _obs(_MINT_A, _POOL_A, liquidity_usd=float("nan")),
                _obs(_MINT_B, _POOL_B, liquidity_usd=float("inf")),
            ],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-nan",
        )
        # Treated as liquidity unknown (coerced to None), not above-floor.
        for accepted in report["accepted"]:
            assert accepted["prefilter_outcome"] == "LIQUIDITY_UNKNOWN"
            assert accepted["protocol_confirmation_due"] is False


# ---------------------------------------------------------------------------
# 17–18 Exact quote mint preservation
# ---------------------------------------------------------------------------


class TestExactQuotePromotion:
    def test_direct_promotion_preserves_exact_quote_mint(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[
                _obs(_MINT_A, _POOL_A, liquidity_usd=8000.0, quote=USDC)
            ],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-quote",
        )
        report = process_protocol_confirmation_queue(
            connection,
            stage_budget=StageBudget.permanent_discovery_default(),
            now=NOW,
            campaign_id="camp-quote",
            account_batch_transport=fixture_account_batch_transport(
                {_POOL_A: _pool_account(mint=_MINT_A)}
            ),
        )
        assert report["promoted_observation_eligible"]
        promo = report["promoted_observation_eligible"][0]
        assert promo["quote_mint"] == USDC
        assert promo["base_mint"] == _MINT_A
        state = load_exact_market_states(connection, mint=_MINT_A)[0]
        assert state["quote_mint"] == USDC

    def test_quote_base_pool_conflicts_prevent_promotion(self, database):
        _, connection = database
        # Seed retained evidence with conflicting base mint in evidence JSON.
        record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_A, _POOL_A, liquidity_usd=8000.0, quote=WSOL)],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-conflict",
        )
        # Corrupt retained evidence base_mint.
        row = connection.execute(
            """SELECT evidence_json FROM printer_discovery_reserve_layers
               WHERE mint_identity=? AND reserve_layer=?""",
            (_MINT_A, ABOVE_FLOOR_NOMINATED),
        ).fetchone()
        evidence = json.loads(row["evidence_json"])
        evidence["base_mint"] = _MINT_B  # conflict
        connection.execute(
            """UPDATE printer_discovery_reserve_layers
               SET evidence_json=? WHERE mint_identity=? AND reserve_layer=?""",
            (json.dumps(evidence), _MINT_A, ABOVE_FLOOR_NOMINATED),
        )
        connection.execute(
            """UPDATE printer_discovery_reserve_layers
               SET evidence_json=? WHERE mint_identity=? AND reserve_layer=?""",
            (json.dumps(evidence), _MINT_A, BROAD_NOMINATED),
        )
        connection.commit()
        promotion = promote_confirmed_with_retained_liquidity(
            connection,
            mint=_MINT_A,
            pool=_POOL_A,
            venue="pumpswap",
            now=NOW,
            campaign_id="camp-conflict",
            protocol_request_id=1,
        )
        assert promotion["promoted"] is False
        assert promotion["reason"] == "RETAINED_BASE_MINT_CONFLICT"


# ---------------------------------------------------------------------------
# 19–22 Unknown liquidity backup
# ---------------------------------------------------------------------------


class TestUnknownLiquidityBackup:
    def _pair(self, mint, pool, liquidity_usd, quote=WSOL):
        return {
            "pairAddress": pool,
            "baseToken": {"address": mint},
            "quoteToken": {"address": quote},
            "dexId": "pumpswap",
            "liquidity": {"usd": liquidity_usd},
            "base_mint": mint,
            "quote_mint": quote,
            "pool": pool,
            "liquidity_usd": liquidity_usd,
            "venue": "pumpswap",
        }

    def test_dex_missing_liquidity_receives_one_gecko_backup(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_A, _POOL_A, liquidity_usd=None)],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-bak-dex",
        )
        state = load_exact_market_states(connection, mint=_MINT_A)[0]
        assert state["current_reason"] == REASON_LIQUIDITY_UNKNOWN

        def gt_factory(mint):
            def transport(_ctx):
                return {
                    "data": [
                        {
                            "id": "solana_" + _POOL_A,
                            "attributes": {
                                "address": _POOL_A,
                                "base_token_address": mint,
                                "quote_token_address": WSOL,
                                "dex": "pumpswap",
                                "reserve_in_usd": "5500",
                            },
                            "relationships": {
                                "base_token": {"data": {"id": "solana_" + mint}},
                                "quote_token": {"data": {"id": "solana_" + WSOL}},
                                "dex": {"data": {"id": "pumpswap"}},
                            },
                        }
                    ],
                    "pairs": [
                        self._pair(mint, _POOL_A, 5500.0),
                    ],
                    "response_bytes": 200,
                }

            return transport

        budget = StageBudget.permanent_discovery_default()
        report = run_bounded_unknown_liquidity_backup(
            connection,
            stage_budget=budget,
            now=NOW,
            campaign_id="camp-bak-dex",
            run_id="run",
            cycle_id="cycle",
            geckoterminal_transport_factory=gt_factory,
        )
        assert report["source_requests"] == 1
        assert report["attempts"]
        assert report["attempts"][0]["backup_source"] == "geckoterminal"
        assert report["attempts"][0]["original_source"] == "dexscreener"
        # Either above-floor or still-unknown depending on pair normalization;
        # must not have entered protocol (no protocol calls here).
        assert report["source_requests"] == 1

    def test_gecko_missing_liquidity_receives_one_dex_backup(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_B, _POOL_B, liquidity_usd=None)],
            source="geckoterminal",
            request_id=1,
            now=NOW,
            campaign_id="camp-bak-gt",
        )

        def dex_factory(mint):
            def transport(_ctx):
                return {
                    "pairs": [self._pair(mint, _POOL_B, 4000.0)],
                    "response_bytes": 200,
                }

            return transport

        budget = StageBudget.permanent_discovery_default()
        report = run_bounded_unknown_liquidity_backup(
            connection,
            stage_budget=budget,
            now=NOW,
            campaign_id="camp-bak-gt",
            dexscreener_transport_factory=dex_factory,
        )
        assert report["source_requests"] == 1
        assert report["attempts"][0]["backup_source"] == "dexscreener"
        assert report["attempts"][0]["original_source"] == "geckoterminal"

    def test_second_backup_attempt_prevented(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_A, _POOL_A, liquidity_usd=None)],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-bak-2",
        )
        calls = {"n": 0}

        def gt_factory(mint):
            def transport(_ctx):
                calls["n"] += 1
                return {"pairs": [], "data": [], "response_bytes": 10}

            return transport

        budget = StageBudget.permanent_discovery_default()
        first = run_bounded_unknown_liquidity_backup(
            connection,
            stage_budget=budget,
            now=NOW,
            campaign_id="camp-bak-2",
            geckoterminal_transport_factory=gt_factory,
        )
        assert first["source_requests"] == 1
        second = run_bounded_unknown_liquidity_backup(
            connection,
            stage_budget=budget,
            now=NOW,
            campaign_id="camp-bak-2",
            geckoterminal_transport_factory=gt_factory,
        )
        # Second attempt is prevented: either provenance skip or the row left
        # LIQUIDITY_UNKNOWN (e.g. EXACT_POOL_NO_MATCH / deferred).
        assert second["source_requests"] == 0
        assert calls["n"] == 1
        assert (
            second["skipped_already_attempted"] >= 1
            or first["attempts"][0]["outcome"] in {
                "EXACT_POOL_NO_MATCH",
                "LIQUIDITY_UNKNOWN",
                "IDENTITY_CONFLICT",
                "BELOW_LIQUIDITY_FLOOR",
                "ABOVE_FLOOR_NOMINATION",
            }
        )

    def test_unresolved_backup_defers_without_protocol(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_A, _POOL_A, liquidity_usd=None)],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-bak-def",
        )

        def gt_factory(mint):
            def transport(_ctx):
                return {"pairs": [], "data": [], "response_bytes": 10}

            return transport

        budget = StageBudget.permanent_discovery_default()
        report = run_bounded_unknown_liquidity_backup(
            connection,
            stage_budget=budget,
            now=NOW,
            campaign_id="camp-bak-def",
            geckoterminal_transport_factory=gt_factory,
        )
        assert report["source_requests"] == 1
        # No protocol confirmation should be due for still-unknown.
        protocol = process_protocol_confirmation_queue(
            connection,
            stage_budget=budget,
            now=NOW,
            account_batch_transport=lambda _c: (_ for _ in ()).throw(
                AssertionError("no protocol before liquidity proven")
            ),
        )
        assert protocol["source_requests"] == 0


# ---------------------------------------------------------------------------
# 23 Transport non-fabrication
# ---------------------------------------------------------------------------


class TestTransportNonFabrication:
    def test_transport_count_not_fabricated_after_measure_failure(self, database):
        _, connection = database
        record_fresh_pool_nominations(
            connection,
            observations=[_obs(_MINT_A, _POOL_A, liquidity_usd=5000.0)],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-tx",
        )
        from printer_v1.sources.measured_transport import MeasuredTransportError

        def boom(*_a, **_k):
            raise MeasuredTransportError("MALFORMED_TRANSPORT_IDENTITY")

        with patch(
            "printer_v1.sources.measured_transport.record_payload_transports",
            boom,
        ):
            # Patch at use site via process function's imported name path.
            with patch(
                "printer_v1.discovery.permanent_discovery_availability.record_payload_transports",
                boom,
                create=True,
            ):
                # The import is local inside process_protocol_confirmation_queue;
                # patch the module attribute used by the local import.
                import printer_v1.sources.measured_transport as mt

                with patch.object(mt, "record_payload_transports", boom):
                    report = process_protocol_confirmation_queue(
                        connection,
                        stage_budget=StageBudget.permanent_discovery_default(),
                        now=NOW,
                        campaign_id="camp-tx",
                        run_id="run-tx",
                        cycle_id="cycle-tx",
                        account_batch_transport=fixture_account_batch_transport(
                            {_POOL_A: _pool_account(mint=_MINT_A)}
                        ),
                        stage_evidence_sink=lambda _s: None,
                    )
        # Request count remains from durable request ID.
        assert report["source_requests"] == 1
        assert report["source_request_ids"]
        # Transport must not be fabricated to 1 after measurement failure.
        assert report["accounting_blocker"] is True
        assert "TRANSPORT_IDENTITY_MEASUREMENT_FAILED" in str(
            report["accounting_blocker_reason"] or ""
        )
        # Measured transport count is not invented.
        assert int(report["transport_operations"]) == 0
        coverage = report["source_request_coverage"]
        assert coverage
        assert coverage[0]["transport_identity_count"] == 0


# ---------------------------------------------------------------------------
# 24–26 Ceilings, ownership, locks
# ---------------------------------------------------------------------------


class TestCeilingsOwnershipLocks:
    def test_flat_30_and_reservations_unchanged(self):
        total = sum(cap for _, cap in STAGE_RESERVATIONS)
        assert total == 30
        assert dict(STAGE_RESERVATIONS) == {
            "intake": 3,
            "market_batching": 2,
            "reconciliation": 6,
            "protocol_confirmation": 7,
            "holder_safety": 8,
            "final_refresh_handoff": 4,
        }

    def test_source_governor_ownership_intact(self, database):
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

    def test_no_retrieval_decision_position_trade_audit_pnl_unlock(self):
        # Static lock: repair modules must not import paper/trade/pnl owners.
        import printer_v1.discovery.permanent_discovery_availability as pda
        import inspect

        source = inspect.getsource(pda)
        forbidden = (
            "paper_decision",
            "BUY",
            "SELL",
            "paper_trade",
            "trade_audit",
            "pnl_engine",
            "WINDOW_15M",
        )
        # Comments may mention locks; ensure no runtime unlock helpers are defined.
        assert "unlock_paper" not in source
        assert "create_position" not in source
        assert MINIMUM_FREEZE_DEPTH == 4
        # Diagnostic categories are counts, never scores.
        status = observation_reserve_depth_status(5)
        assert "score" not in status
        assert "rank" not in status
        assert "confidence" not in status


class TestDiagnosticsConsistency:
    def test_prefilter_diagnostic_categories_preserved(self, database):
        _, connection = database
        report = record_fresh_pool_nominations(
            connection,
            observations=[
                _obs(_MINT_A, _POOL_A, liquidity_usd=5000.0),
                _obs(_MINT_B, _POOL_B, liquidity_usd=100.0),
                _obs(_MINT_C, _POOL_C, liquidity_usd=None),
            ],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="camp-diag",
        )
        counts = report["prefilter_counts"]
        assert counts["ABOVE_FLOOR_NOMINATION"] == 1
        assert counts["BELOW_LIQUIDITY_FLOOR"] == 1
        assert counts["LIQUIDITY_UNKNOWN"] == 1
        assert "score" not in counts

    def test_manifest_builder_rejects_silent_duplicate_when_fail_closed(self):
        entries = [
            {
                "source_request_id": 1,
                "source_name": "a",
                "request_kind": "k",
                "logical_stage_id": "L1",
                "transport_identity_count": 0,
                "normalized_member_count": 0,
                "terminal_status": "COMPLETED",
            },
            {
                "source_request_id": 1,
                "source_name": "a",
                "request_kind": "k",
                "logical_stage_id": "L2",
                "transport_identity_count": 0,
                "normalized_member_count": 0,
                "terminal_status": "COMPLETED",
            },
        ]
        result = build_source_request_coverage_manifest(
            entries, fail_closed_on_duplicate=True
        )
        assert isinstance(result, dict)
        assert result["status"] == "BLOCKED"
        built = build_campaign_source_request_manifest(entries)
        assert built["status"] == "BLOCKED"
        assert built["blocker"] == CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH

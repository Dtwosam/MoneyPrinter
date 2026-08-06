"""Disposable proof for source-specific candidate temporal contract repair.

Proves explicit temporal authority on SourceSpecificCandidateAdmission, source-
honest holder maturation resolution, source-honest admission reporting, and
preservation of direct-only snapshot maturity. Disposable DBs and fixture
transports only — no provider, authorization, or authoritative DB work.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.combined_executor import (
    FixtureOriginProof,
    FixturePumpSwapProof,
    PUMPSWAP_PROGRAM_ID,
)
from printer_v1.discovery.memory_observation_activation import (
    AdmissionAuthority,
    ActivationPurpose,
    EvidenceRole,
    FrozenMemoryActivationCandidate,
    FrozenMemoryActivationSet,
    ManifestRequestEntry,
    RetainedEvidenceReference,
    TrackingFeasibility,
    validate_memory_activation_set,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
    LiveOperationalError,
)
from printer_v1.operator_cli.graduated_supply_front_door import (
    CandidateTemporalAuthority,
    GraduatedSupplyError,
    SourceSpecificCandidateAdmission,
    _source_specific_admission_for,
    build_graduated_supply,
)
from printer_v1.scheduler.snapshot_maturity import evaluate_snapshot_maturity
from test_v2_9_8b_window_15m_memory_activation_clean_object_integrity_repair import (
    _BatchScopedDiscoveryPersistenceProof,
)
from test_v2_9_8b_window_15m_source_specific_admission_retained_evidence_repair import (
    _candidate as _activation_candidate,
    _market as _activation_market,
    _persist_reference,
)


NOW = "2026-08-06T10:54:03+00:00"
MARKET_OBS_A = "2026-08-06T10:50:00+00:00"
MARKET_OBS_B = "2026-08-06T10:51:30.500000+00:00"
EXPIRES = "2026-08-06T11:24:03+00:00"
EVALUATED = "2026-08-06T10:54:03+00:00"
DEADLINE = "2026-08-06T11:09:03+00:00"
REQUEST_TIME = "2026-08-06T10:49:00+00:00"

# Failed-run shaped mint/pool (DexScreener market nominee).
FAILED_MINT = "6a4TCQoCFXXNK8jUtjCMPqvoaLGx1oNLrciBiRafpump"
FAILED_POOL = "GzDaX3zHxDd5KUGKo5fHHg93arcPArrseAoEfP685JGQ"
DEX_MINT = FAILED_MINT
DEX_POOL = FAILED_POOL
GECKO_MINT = "Gecko11111111111111111111111111111111111111"
GECKO_POOL = "GeckoPool11111111111111111111111111111111111"
PUMP_MINT = "Pump111111111111111111111111111111111111111"
PUMP_POOL = "PumpPool111111111111111111111111111111111111"
PUMP_MINT_B = "Pump222222222222222222222222222222222222222"
PUMP_POOL_B = "PumpPool222222222222222222222222222222222222"
DIRECT_EPOCH_A = 1_701_000_000
DIRECT_EPOCH_B = 1_702_000_000


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "temporal-contract.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def _market_item(
    mint: str,
    pool: str,
    *,
    source: str = "dexscreener",
    observed_at: str | None = MARKET_OBS_A,
    nested_only: bool = False,
    top_level_only: bool = False,
    extra_liquidity: dict | None = None,
) -> dict:
    liquidity = {
        "status": "LIQUIDITY_PROVEN",
        "liquidity_usd": 21_054.68,
        "mint": mint,
        "pool": pool,
        "source_request_id": 1940,
        "source_response_id": 1730,
    }
    if extra_liquidity:
        liquidity.update(extra_liquidity)
    item = {
        "mint": mint,
        "pool": pool,
        "market_identity": f"solana-mainnet:present-pool:{pool}",
        "provenance": source,
        "admission_authority": "MARKET_PRESENT_POOL",
        "lineage_state": "UNKNOWN_ORIGIN",
        "nomination_source": source,
        "exact_present_pool_confirmed": True,
        "memory_observation_eligible": True,
        "eligible": True,
        "evidence_expires_at": EXPIRES,
        "liquidity": liquidity,
        "request_time": REQUEST_TIME,
        "evaluated_at": EVALUATED,
    }
    if observed_at is not None:
        if nested_only:
            liquidity["liquidity_observed_at"] = observed_at
        elif top_level_only:
            item["liquidity_observed_at"] = observed_at
        else:
            item["liquidity_observed_at"] = observed_at
            liquidity["liquidity_observed_at"] = observed_at
    return item


def _direct_item(
    mint: str,
    pool: str,
    *,
    graduation_block_time: object = DIRECT_EPOCH_A,
    slot: int = 10,
) -> dict:
    return {
        "mint": mint,
        "pool": pool,
        "market_identity": f"solana-mainnet:present-pool:{pool}",
        "provenance": "direct_pump_migration",
        "admission_authority": "DIRECT_PUMP_PUMPSWAP",
        "lineage_state": "PUMP_GRADUATION_CONFIRMED",
        "nomination_source": "direct_pump_migration",
        "exact_present_pool_confirmed": True,
        "memory_observation_eligible": True,
        "eligible": True,
        "evidence_expires_at": EXPIRES,
        "liquidity": {
            "status": "LIQUIDITY_PROVEN",
            "liquidity_usd": 12_000.0,
            "mint": mint,
            "pool": pool,
        },
        "direct_pump_evidence": {
            "mint": mint,
            "pool": pool,
            "migration_signature": f"migration:{mint}",
            "graduation_slot": slot,
            "graduation_block_time": graduation_block_time,
            "pumpswap_program_id": PUMPSWAP_PROGRAM_ID,
            "confirmed": True,
        },
    }


def _legacy_origin(
    mint: str = PUMP_MINT,
    *,
    block_time: int = DIRECT_EPOCH_A,
) -> FixtureOriginProof:
    return FixtureOriginProof(
        mint=mint,
        signature=f"sig:{mint}",
        slot=42,
        block_time=block_time,
        bonding_curve=f"curve:{mint}",
        confirmed=True,
        origin_route="GRADUATION_NATIVE",
    )


# ---------------------------------------------------------------------------
# 1–9 Construction / validation
# ---------------------------------------------------------------------------


def test_failed_run_shaped_market_candidate_builds_retained_market_temporal_context():
    admission = _source_specific_admission_for(
        _market_item(FAILED_MINT, FAILED_POOL, observed_at=MARKET_OBS_A)
    )
    assert admission.admission_authority is AdmissionAuthority.MARKET_PRESENT_POOL
    ctx = admission.temporal_context
    assert (
        ctx.temporal_authority
        is CandidateTemporalAuthority.RETAINED_MARKET_OBSERVATION_TIME
    )
    assert ctx.admission_observed_at_utc == MARKET_OBS_A
    assert ctx.pump_origin_block_time_epoch is None


def test_market_candidate_has_no_block_time_attribute():
    admission = _source_specific_admission_for(
        _market_item(FAILED_MINT, FAILED_POOL)
    )
    assert not hasattr(admission, "block_time")
    with pytest.raises(AttributeError):
        _ = admission.block_time  # type: ignore[attr-defined]


def test_market_missing_observation_time_blocks():
    item = _market_item(FAILED_MINT, FAILED_POOL, observed_at=None)
    with pytest.raises(GraduatedSupplyError) as exc:
        _source_specific_admission_for(item)
    assert "MARKET_CANDIDATE_OBSERVATION_TIME_MISSING" in str(exc.value)


def test_market_malformed_observation_time_blocks():
    item = _market_item(FAILED_MINT, FAILED_POOL, observed_at="not-a-timestamp")
    with pytest.raises(GraduatedSupplyError) as exc:
        _source_specific_admission_for(item)
    assert "MARKET_CANDIDATE_OBSERVATION_TIME_INVALID" in str(exc.value)


def test_market_naive_observation_time_blocks():
    item = _market_item(
        FAILED_MINT, FAILED_POOL, observed_at="2026-08-06T10:50:00"
    )
    with pytest.raises(GraduatedSupplyError) as exc:
        _source_specific_admission_for(item)
    assert "MARKET_CANDIDATE_OBSERVATION_TIME_INVALID" in str(exc.value)


def test_market_uses_nested_liquidity_observed_at_only():
    admission = _source_specific_admission_for(
        _market_item(
            FAILED_MINT,
            FAILED_POOL,
            observed_at=MARKET_OBS_B,
            nested_only=True,
        )
    )
    assert admission.temporal_context.admission_observed_at_utc == MARKET_OBS_B


def test_market_does_not_fallback_to_now_evaluated_request_or_expiry():
    item = _market_item(FAILED_MINT, FAILED_POOL, observed_at=None)
    # Explicit non-source timestamps present; still must fail closed.
    item["now"] = NOW
    item["evaluated_at"] = EVALUATED
    item["request_time"] = REQUEST_TIME
    item["evidence_expires_at"] = EXPIRES
    item["liquidity"]["evidence_expires_at"] = EXPIRES
    with pytest.raises(GraduatedSupplyError) as exc:
        _source_specific_admission_for(item)
    assert "MARKET_CANDIDATE_OBSERVATION_TIME_MISSING" in str(exc.value)


def test_direct_candidate_preserves_exact_positive_graduation_epoch():
    admission = _source_specific_admission_for(
        _direct_item(PUMP_MINT, PUMP_POOL, graduation_block_time=DIRECT_EPOCH_A)
    )
    ctx = admission.temporal_context
    assert (
        ctx.temporal_authority
        is CandidateTemporalAuthority.DIRECT_PUMP_GRADUATION_TIME
    )
    assert ctx.pump_origin_block_time_epoch == DIRECT_EPOCH_A
    expected = datetime.fromtimestamp(
        DIRECT_EPOCH_A, tz=timezone.utc
    ).isoformat()
    assert ctx.admission_observed_at_utc == expected
    assert admission.origin_proof is not None
    assert admission.origin_proof.block_time == DIRECT_EPOCH_A


@pytest.mark.parametrize("bad", (None, 0, -1, "", "not-int", True, False))
def test_direct_missing_zero_negative_or_invalid_time_blocks(bad):
    item = _direct_item(PUMP_MINT, PUMP_POOL, graduation_block_time=bad)
    with pytest.raises(GraduatedSupplyError) as exc:
        _source_specific_admission_for(item)
    message = str(exc.value)
    assert (
        "DIRECT_CANDIDATE_GRADUATION_TIME_MISSING" in message
        or "DIRECT_CANDIDATE_GRADUATION_TIME_INVALID" in message
    )


@pytest.mark.parametrize(
    "bad",
    (
        1.5,
        1.0,
        "1700000000",
        float("inf"),
        float("-inf"),
        float("nan"),
        10**100,
    ),
)
def test_direct_non_integer_and_nonconvertible_epochs_fail_closed(bad):
    """No coercion: floats, digit-strings, inf/nan, and oversized ints are invalid."""
    item = _direct_item(PUMP_MINT, PUMP_POOL, graduation_block_time=bad)
    with pytest.raises(GraduatedSupplyError) as exc:
        _source_specific_admission_for(item)
    assert str(exc.value) == (
        f"DIRECT_CANDIDATE_GRADUATION_TIME_INVALID:{PUMP_MINT}"
    )


def test_direct_positive_integer_epoch_remains_exact_no_truncation():
    exact = 1_700_000_001
    admission = _source_specific_admission_for(
        _direct_item(PUMP_MINT, PUMP_POOL, graduation_block_time=exact)
    )
    assert admission.temporal_context.pump_origin_block_time_epoch == exact
    assert admission.temporal_context.pump_origin_block_time_epoch is exact or (
        admission.temporal_context.pump_origin_block_time_epoch == exact
        and type(admission.temporal_context.pump_origin_block_time_epoch) is int
    )
    assert admission.origin_proof is not None
    assert admission.origin_proof.block_time == exact
    # Prove no float truncation path: nearby float would have been rejected.
    with pytest.raises(GraduatedSupplyError) as exc:
        _source_specific_admission_for(
            _direct_item(
                PUMP_MINT, PUMP_POOL, graduation_block_time=float(exact)
            )
        )
    assert "DIRECT_CANDIDATE_GRADUATION_TIME_INVALID" in str(exc.value)


def test_invalid_direct_time_blocks_before_holder_transport(monkeypatch):
    provider_calls: list[object] = []

    def boom(*args, **kwargs):
        provider_calls.append(1)
        raise AssertionError("holder provider must not run")

    monkeypatch.setattr(
        "printer_v1.operator_cli.one_command_15m_factory._collect_preclose_context",
        boom,
    )
    with pytest.raises(GraduatedSupplyError) as exc:
        _source_specific_admission_for(
            _direct_item(PUMP_MINT, PUMP_POOL, graduation_block_time=1.0)
        )
    assert "DIRECT_CANDIDATE_GRADUATION_TIME_INVALID" in str(exc.value)
    assert provider_calls == []


@pytest.mark.parametrize(
    "bad_block_time",
    (10**100, 1.5, "1700000000", 0, -5),
)
def test_legacy_holder_resolver_stable_typed_blocker_for_invalid_block_time(
    bad_block_time,
):
    """Legacy FixtureOriginProof path exposes stable LiveOperationalError codes."""
    from dataclasses import replace

    base = _legacy_origin(block_time=DIRECT_EPOCH_A)
    # Dataclass does not runtime-type-check; inject untrusted values deliberately.
    proof = replace(base, block_time=bad_block_time)  # type: ignore[arg-type]
    with pytest.raises(LiveOperationalError) as exc:
        AuthoritativeLiveOperationalCampaignOwner._resolve_holder_maturation_observed_at(
            proof
        )
    assert exc.value.code in {
        "DIRECT_CANDIDATE_GRADUATION_TIME_INVALID",
        "DIRECT_CANDIDATE_GRADUATION_TIME_MISSING",
    }
    assert exc.value.detail == PUMP_MINT


def test_market_temporal_behavior_unchanged_after_direct_validation_harden():
    admission = _source_specific_admission_for(
        _market_item(FAILED_MINT, FAILED_POOL, observed_at=MARKET_OBS_A)
    )
    assert (
        admission.temporal_context.temporal_authority
        is CandidateTemporalAuthority.RETAINED_MARKET_OBSERVATION_TIME
    )
    assert admission.temporal_context.admission_observed_at_utc == MARKET_OBS_A
    assert admission.temporal_context.pump_origin_block_time_epoch is None
    assert not hasattr(admission, "block_time")


def test_mixed_market_direct_behavior_unchanged_after_direct_validation_harden():
    market = _source_specific_admission_for(
        _market_item(DEX_MINT, DEX_POOL, observed_at=MARKET_OBS_A)
    )
    direct = _source_specific_admission_for(
        _direct_item(PUMP_MINT, PUMP_POOL, graduation_block_time=DIRECT_EPOCH_A)
    )
    assert (
        market.temporal_context.temporal_authority
        is CandidateTemporalAuthority.RETAINED_MARKET_OBSERVATION_TIME
    )
    assert (
        direct.temporal_context.temporal_authority
        is CandidateTemporalAuthority.DIRECT_PUMP_GRADUATION_TIME
    )
    assert market.temporal_context.pump_origin_block_time_epoch is None
    assert direct.temporal_context.pump_origin_block_time_epoch == DIRECT_EPOCH_A
    assert market.temporal_context.admission_observed_at_utc == MARKET_OBS_A


# ---------------------------------------------------------------------------
# 10–12 Shared holder maturation resolver
# ---------------------------------------------------------------------------


def _run_holder_with_captured_maturation(
    db,
    monkeypatch,
    *,
    candidates,
    run_id: str,
):
    """Drive the shared holder funnel with WAITING maturation (no provider I/O)."""
    from printer_v1.lifecycle.tracking_queue import TrackingHandoffAssessment
    from printer_v1.operator_cli.holder_reliability_budget_control import (
        CampaignOperationLedger,
    )

    captured: list[dict[str, object]] = []
    provider_calls: list[object] = []

    def schedule_waiting(connection, **kwargs):
        captured.append(dict(kwargs))
        return {
            "work_id": f"work-{kwargs.get('mint')}",
            "work_state": "WAITING",
            "scheduled_for": EVALUATED,
            "deadline_at": DEADLINE,
            "maturation_threshold_state": "UNPROVEN_DISABLED",
            "source_calls_while_waiting": 0,
        }

    def boom_provider(*args, **kwargs):
        provider_calls.append(1)
        raise AssertionError("holder provider must not run when maturation waits")

    monkeypatch.setattr(
        "printer_v1.operator_cli.holder_reliability_budget_control.schedule_maturation",
        schedule_waiting,
    )
    monkeypatch.setattr(
        "printer_v1.operator_cli.holder_reliability_budget_control.persist_ledger",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "printer_v1.db.sqlite_write_contracts.release_write_transaction",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "printer_v1.lifecycle.tracking_queue.assess_tracking_handoff_by_identity",
        lambda *a, **k: TrackingHandoffAssessment(
            eligible=True,
            reason_code="TRACKING_HANDOFF_ELIGIBLE",
            category="ELIGIBLE",
            queue_id=None,
            queue_status=None,
            requalification_eligible=False,
            cooldown_until=None,
            historical_cooldown_expiry_derived=False,
        ),
    )
    monkeypatch.setattr(
        "printer_v1.operator_cli.one_command_15m_factory._collect_preclose_context",
        boom_provider,
    )
    owner = AuthoritativeLiveOperationalCampaignOwner()
    command = SimpleNamespace(
        run_id=run_id,
        campaign_id="campaign-temporal",
        db_path=":memory:",
    )
    evaluated = datetime.fromisoformat(EVALUATED)
    deadline = datetime.fromisoformat(DEADLINE)
    ledger = CampaignOperationLedger(
        operation_ceiling=64,
        governed_requests=0,
        underlying_transport_operations=0,
        zero_transport_operations=0,
        deadline_at=deadline,
        reserved_snapshot_operations=0,
        reserved_snapshot_completion_operations=0,
    )
    result = owner._evaluate_holder_eligibility(
        db,
        command=command,
        cycle_id="cycle-temporal",
        bounded_candidates=tuple(candidates),
        evaluated=evaluated,
        deadline=deadline,
        ledger=ledger,
        timeout_seconds=1.0,
        context_factories=None,
        request_pacer=None,
        eligible_target=1,
        permanent_memory_observation=False,
    )
    return captured, provider_calls, result


def test_holder_funnel_passes_market_observation_time_to_schedule_maturation(
    db, monkeypatch
):
    admission = _source_specific_admission_for(
        _market_item(FAILED_MINT, FAILED_POOL, observed_at=MARKET_OBS_A)
    )
    # Resolver unit proof.
    assert (
        AuthoritativeLiveOperationalCampaignOwner._resolve_holder_maturation_observed_at(
            admission
        )
        == MARKET_OBS_A
    )
    captured, provider_calls, _result = _run_holder_with_captured_maturation(
        db,
        monkeypatch,
        candidates=(admission,),
        run_id="run-temporal-market",
    )
    assert len(captured) == 1
    assert captured[0].get("observed_at") == MARKET_OBS_A
    assert captured[0].get("mint") == FAILED_MINT
    assert provider_calls == []


def test_holder_funnel_passes_direct_utc_iso_to_schedule_maturation(db, monkeypatch):
    admission = _source_specific_admission_for(
        _direct_item(PUMP_MINT, PUMP_POOL, graduation_block_time=DIRECT_EPOCH_A)
    )
    expected = datetime.fromtimestamp(
        DIRECT_EPOCH_A, tz=timezone.utc
    ).isoformat()
    assert (
        AuthoritativeLiveOperationalCampaignOwner._resolve_holder_maturation_observed_at(
            admission
        )
        == expected
    )
    captured, provider_calls, _result = _run_holder_with_captured_maturation(
        db,
        monkeypatch,
        candidates=(admission,),
        run_id="run-temporal-direct",
    )
    assert len(captured) == 1
    assert captured[0].get("observed_at") == expected
    assert provider_calls == []


def test_legacy_fixture_origin_proof_resolves_to_utc_iso():
    proof = _legacy_origin(block_time=DIRECT_EPOCH_B)
    resolved = AuthoritativeLiveOperationalCampaignOwner._resolve_holder_maturation_observed_at(
        proof
    )
    assert resolved == datetime.fromtimestamp(
        DIRECT_EPOCH_B, tz=timezone.utc
    ).isoformat()


def test_unsupported_candidate_temporal_authority_fails_closed():
    with pytest.raises(LiveOperationalError) as exc:
        AuthoritativeLiveOperationalCampaignOwner._resolve_holder_maturation_observed_at(
            SimpleNamespace(mint="x")
        )
    assert exc.value.code == "UNSUPPORTED_CANDIDATE_TEMPORAL_AUTHORITY"


def test_no_holder_provider_when_temporal_validation_blocks(monkeypatch):
    """Invalid market timestamp blocks at admission before holder transport."""
    provider_calls: list[object] = []

    def boom(*args, **kwargs):
        provider_calls.append(1)
        raise AssertionError("provider must not be called")

    monkeypatch.setattr(
        "printer_v1.operator_cli.one_command_15m_factory._collect_preclose_context",
        boom,
    )
    item = _market_item(FAILED_MINT, FAILED_POOL, observed_at=None)
    with pytest.raises(GraduatedSupplyError):
        _source_specific_admission_for(item)
    assert provider_calls == []


# ---------------------------------------------------------------------------
# 13–15 Mixed candidate independence
# ---------------------------------------------------------------------------


def test_market_market_retains_independent_timestamps():
    a = _source_specific_admission_for(
        _market_item(DEX_MINT, DEX_POOL, observed_at=MARKET_OBS_A)
    )
    b = _source_specific_admission_for(
        _market_item(
            GECKO_MINT,
            GECKO_POOL,
            source="geckoterminal",
            observed_at=MARKET_OBS_B,
        )
    )
    assert a.temporal_context.admission_observed_at_utc == MARKET_OBS_A
    assert b.temporal_context.admission_observed_at_utc == MARKET_OBS_B
    assert a.temporal_context.pump_origin_block_time_epoch is None
    assert b.temporal_context.pump_origin_block_time_epoch is None


def test_direct_direct_retains_independent_epochs():
    a = _source_specific_admission_for(
        _direct_item(PUMP_MINT, PUMP_POOL, graduation_block_time=DIRECT_EPOCH_A)
    )
    b = _source_specific_admission_for(
        _direct_item(
            PUMP_MINT_B, PUMP_POOL_B, graduation_block_time=DIRECT_EPOCH_B
        )
    )
    assert a.temporal_context.pump_origin_block_time_epoch == DIRECT_EPOCH_A
    assert b.temporal_context.pump_origin_block_time_epoch == DIRECT_EPOCH_B


@pytest.mark.parametrize("order", ("market_first", "direct_first"))
def test_mixed_pairs_retain_independent_authorities(order):
    market = _source_specific_admission_for(
        _market_item(DEX_MINT, DEX_POOL, observed_at=MARKET_OBS_A)
    )
    direct = _source_specific_admission_for(
        _direct_item(PUMP_MINT, PUMP_POOL, graduation_block_time=DIRECT_EPOCH_A)
    )
    pair = (market, direct) if order == "market_first" else (direct, market)
    # Slot ordinal must not rewrite meaning.
    for ordinal, candidate in enumerate(pair, start=1):
        if candidate.admission_authority is AdmissionAuthority.MARKET_PRESENT_POOL:
            assert (
                candidate.temporal_context.temporal_authority
                is CandidateTemporalAuthority.RETAINED_MARKET_OBSERVATION_TIME
            )
            assert (
                candidate.temporal_context.admission_observed_at_utc
                == MARKET_OBS_A
            )
            assert candidate.temporal_context.pump_origin_block_time_epoch is None
        else:
            assert (
                candidate.temporal_context.temporal_authority
                is CandidateTemporalAuthority.DIRECT_PUMP_GRADUATION_TIME
            )
            assert (
                candidate.temporal_context.pump_origin_block_time_epoch
                == DIRECT_EPOCH_A
            )
        assert ordinal in {1, 2}


# ---------------------------------------------------------------------------
# 16–18 Reporting
# ---------------------------------------------------------------------------


def test_reporting_marks_both_lawful_admission_states_selectable():
    market = _source_specific_admission_for(
        _market_item(DEX_MINT, DEX_POOL, observed_at=MARKET_OBS_A)
    )
    direct = _source_specific_admission_for(
        _direct_item(PUMP_MINT, PUMP_POOL, graduation_block_time=DIRECT_EPOCH_A)
    )
    decisions = (
        (market, "CANDIDATE_PRESENT_POOL_ELIGIBLE"),
        (direct, "CANDIDATE_PRESENT_POOL_ELIGIBLE"),
    )
    report = AuthoritativeLiveOperationalCampaignOwner._full_pilot_graduation_diagnostics(
        graduation_decisions=decisions,
        acquisition=SimpleNamespace(origin_proofs=()),
        enrichment=SimpleNamespace(
            gecko_ops=(), tracker_ops=(), dexscreener_ops=()
        ),
        fixtures=SimpleNamespace(pumpswap_proofs={}),
        staged_now=0,
        admitted=2,
        candidate_cap=4,
    )
    assert (
        report["eligibility_rule"]
        == "SOURCE_SPECIFIC_PRESENT_POOL_OR_DIRECT_PUMP"
    )
    assert report["candidate_admitted_count"] == 2
    assert report["market_present_pool_count"] == 1
    assert report["direct_pump_pumpswap_count"] == 1
    by_mint = {row["mint_identity"]: row for row in report["candidates"]}
    market_row = by_mint[DEX_MINT.lower()]
    direct_row = by_mint[PUMP_MINT.lower()]
    assert market_row["selectable"] is True
    assert direct_row["selectable"] is True
    assert market_row["admission_state"] == "CANDIDATE_PRESENT_POOL_ELIGIBLE"
    assert direct_row["admission_state"] == "GRADUATION_ELIGIBLE"
    assert market_row["admission_authority"] == "MARKET_PRESENT_POOL"
    assert direct_row["admission_authority"] == "DIRECT_PUMP_PUMPSWAP"


def test_market_reporting_has_no_pump_origin_claim():
    market = _source_specific_admission_for(
        _market_item(DEX_MINT, DEX_POOL, observed_at=MARKET_OBS_A)
    )
    report = AuthoritativeLiveOperationalCampaignOwner._full_pilot_graduation_diagnostics(
        graduation_decisions=((market, "CANDIDATE_PRESENT_POOL_ELIGIBLE"),),
        acquisition=SimpleNamespace(origin_proofs=()),
        enrichment=SimpleNamespace(
            gecko_ops=(), tracker_ops=(), dexscreener_ops=()
        ),
        fixtures=SimpleNamespace(pumpswap_proofs={}),
        staged_now=0,
        admitted=1,
        candidate_cap=4,
    )
    row = report["candidates"][0]
    assert row["pump_origin_claimed"] is False
    assert row["pump_origin_block_time_epoch"] is None
    assert row["origin_block_time_epoch"] is None
    assert row["token_age_context"] == "UNKNOWN_NOT_CLAIMED"
    assert (
        row["temporal_authority"]
        == CandidateTemporalAuthority.RETAINED_MARKET_OBSERVATION_TIME.value
    )
    assert row["admission_observed_at_utc"] == MARKET_OBS_A
    assert "LATEST_GRADUATED" not in str(row)


def test_direct_reporting_retains_exact_pump_temporal_evidence():
    direct = _source_specific_admission_for(
        _direct_item(PUMP_MINT, PUMP_POOL, graduation_block_time=DIRECT_EPOCH_A)
    )
    report = AuthoritativeLiveOperationalCampaignOwner._full_pilot_graduation_diagnostics(
        graduation_decisions=((direct, "CANDIDATE_PRESENT_POOL_ELIGIBLE"),),
        acquisition=SimpleNamespace(origin_proofs=()),
        enrichment=SimpleNamespace(
            gecko_ops=(), tracker_ops=(), dexscreener_ops=()
        ),
        fixtures=SimpleNamespace(pumpswap_proofs={}),
        staged_now=0,
        admitted=1,
        candidate_cap=4,
    )
    row = report["candidates"][0]
    assert row["pump_origin_claimed"] is True
    assert row["pump_origin_block_time_epoch"] == DIRECT_EPOCH_A
    assert (
        row["temporal_authority"]
        == CandidateTemporalAuthority.DIRECT_PUMP_GRADUATION_TIME.value
    )
    assert row["admission_observed_at_utc"] == datetime.fromtimestamp(
        DIRECT_EPOCH_A, tz=timezone.utc
    ).isoformat()


# ---------------------------------------------------------------------------
# 19–20 Snapshot maturity preservation
# ---------------------------------------------------------------------------


def test_permanent_market_candidates_never_call_evaluate_snapshot_maturity(
    monkeypatch,
):
    calls: list[object] = []

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("market must not enter snapshot maturity")

    monkeypatch.setattr(
        "printer_v1.scheduler.snapshot_maturity.evaluate_snapshot_maturity",
        spy,
    )
    # Permanent path builds SourceSpecificCandidateAdmission; reporting and
    # holder resolution never invoke evaluate_snapshot_maturity.
    market = _source_specific_admission_for(
        _market_item(DEX_MINT, DEX_POOL, observed_at=MARKET_OBS_A)
    )
    AuthoritativeLiveOperationalCampaignOwner._full_pilot_graduation_diagnostics(
        graduation_decisions=((market, "CANDIDATE_PRESENT_POOL_ELIGIBLE"),),
        acquisition=SimpleNamespace(origin_proofs=()),
        enrichment=SimpleNamespace(
            gecko_ops=(), tracker_ops=(), dexscreener_ops=()
        ),
        fixtures=SimpleNamespace(pumpswap_proofs={}),
        staged_now=0,
        admitted=1,
        candidate_cap=4,
    )
    observed = (
        AuthoritativeLiveOperationalCampaignOwner._resolve_holder_maturation_observed_at(
            market
        )
    )
    assert observed == MARKET_OBS_A
    assert calls == []


def test_direct_snapshot_readiness_behavior_unchanged():
    evaluated = datetime.fromisoformat(EVALUATED)
    decision = evaluate_snapshot_maturity(
        pump_block_time=DIRECT_EPOCH_A,
        evaluated_at=evaluated,
        cancelled=False,
    )
    assert decision.origin_block_time_utc == datetime.fromtimestamp(
        DIRECT_EPOCH_A, tz=timezone.utc
    )
    # Source-specific market candidate is not a valid pump_block_time input.
    market = _source_specific_admission_for(
        _market_item(DEX_MINT, DEX_POOL, observed_at=MARKET_OBS_A)
    )
    bad = evaluate_snapshot_maturity(
        pump_block_time=getattr(market, "block_time", None),
        evaluated_at=evaluated,
        cancelled=False,
    )
    # Missing/invalid block time remains non-due (direct-only contract).
    assert bad.origin_block_time_utc is None


# ---------------------------------------------------------------------------
# 21 Frozen retained-evidence activation creates no new source rows
# ---------------------------------------------------------------------------


def test_frozen_retained_evidence_activation_creates_no_new_source_rows(db):
    from test_v2_9_8b_window_15m_source_specific_admission_retained_evidence_repair import (
        NOW as ACTIVATION_NOW,
        _activation,
        _market as build_market_activation,
    )

    first, first_entries = build_market_activation(
        db, ordinal=1, source="dexscreener", mint=DEX_MINT, pool=DEX_POOL
    )
    second, second_entries = build_market_activation(
        db,
        ordinal=2,
        source="geckoterminal",
        mint=GECKO_MINT,
        pool=GECKO_POOL,
    )
    activation = _activation(
        (first, second),
        (first_entries, second_entries),
    )
    validate_memory_activation_set(db, activation, now=ACTIVATION_NOW)
    source_before = tuple(
        db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "printer_source_requests",
            "printer_source_responses",
            "printer_source_failures",
        )
    )
    # Re-validate only — no new source rows from retained-evidence activation.
    validate_memory_activation_set(db, activation, now=ACTIVATION_NOW)
    assert activation.selected[0].liquidity_observed_at
    source_after = tuple(
        db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "printer_source_requests",
            "printer_source_responses",
            "printer_source_failures",
        )
    )
    assert source_after == source_before
    # Alternates exist but must not create rows either.
    assert len(activation.alternates) == 2


# ---------------------------------------------------------------------------
# 22 No reachable generic source-specific proof.block_time access
# ---------------------------------------------------------------------------


def test_no_reachable_generic_source_specific_proof_block_time_access():
    import ast
    from pathlib import Path

    campaign = Path(
        "src/printer_v1/operator_cli/authoritative_live_operational_campaign.py"
    ).read_text()
    # The two previously reachable sites must no longer dereference
    # proof.block_time for the shared holder or source-specific diagnostics
    # paths. Snapshot readiness may still use proof.block_time on
    # FixtureOriginProof only.
    assert "observed_at=str(proof.block_time)" not in campaign
    assert "int(proof.block_time)" not in campaign or (
        "isinstance(proof, FixtureOriginProof)" in campaign
    )
    # SourceSpecificCandidateAdmission must not expose block_time.
    front = Path(
        "src/printer_v1/operator_cli/graduated_supply_front_door.py"
    ).read_text()
    tree = ast.parse(front)
    for node in tree.body:
        if (
            isinstance(node, ast.ClassDef)
            and node.name == "SourceSpecificCandidateAdmission"
        ):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "block_time":
                    pytest.fail("block_time property must not exist")
                if isinstance(item, ast.AnnAssign):
                    target = item.target
                    if isinstance(target, ast.Name) and target.id == "block_time":
                        pytest.fail("block_time field must not exist")


# ---------------------------------------------------------------------------
# Supply composition with temporal contexts (mixed slots)
# ---------------------------------------------------------------------------


def test_build_graduated_supply_mixed_slots_preserve_temporal_authority(
    monkeypatch,
):
    import printer_v1.discovery.eligible_token_supply as eligible_supply
    import printer_v1.operator_cli.graduated_supply_front_door as front_door

    candidates = (
        _market_item(DEX_MINT, DEX_POOL, observed_at=MARKET_OBS_A),
        _direct_item(
            PUMP_MINT, PUMP_POOL, graduation_block_time=DIRECT_EPOCH_A
        ),
    )
    persistent = SimpleNamespace(
        discovery_report={},
        front_door_report={},
        locator_report={},
        eligible_reserve=candidates,
        diagnostics={"permanent_availability": True},
        exhaustion_certificate=None,
        shortage_classification=None,
        discovery_rounds=1,
    )
    monkeypatch.setattr(
        eligible_supply,
        "run_persistent_eligible_token_supply",
        lambda *args, **kwargs: persistent,
    )
    monkeypatch.setattr(
        front_door,
        "lookup_graduated_candidate",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("post-selection registry lookup")
        ),
    )
    from printer_v1.discovery.permanent_discovery_availability import (
        build_campaign_source_request_scope,
    )

    execution_id = "20260806T000000Z-temporal-mixed"
    scope = build_campaign_source_request_scope(
        execution_id=execution_id,
        campaign_id="camp-temporal-mixed",
        run_id="run-temporal-mixed",
        cycle_id="cycle-temporal-mixed",
    )
    result = build_graduated_supply(
        ":memory:",
        cycle_seed="temporal-mixed-seed",
        migration_transport=lambda _: {},
        permanent_availability=True,
        required_token_capacity=2,
        campaign_source_request_scope=scope,
        discovery_request_key_prefix=scope.request_key_root,
        front_door_request_key_prefix=scope.request_key_root,
        campaign_id=scope.campaign_id,
        execution_id=scope.execution_id,
        run_id=scope.run_id,
        cycle_id=scope.cycle_id,
    )
    assert result.ready is True
    by_authority = {
        proof.admission_authority: proof for proof in result.graduated_supply
    }
    market = by_authority[AdmissionAuthority.MARKET_PRESENT_POOL]
    direct = by_authority[AdmissionAuthority.DIRECT_PUMP_PUMPSWAP]
    assert (
        market.temporal_context.temporal_authority
        is CandidateTemporalAuthority.RETAINED_MARKET_OBSERVATION_TIME
    )
    assert market.temporal_context.admission_observed_at_utc == MARKET_OBS_A
    assert market.temporal_context.pump_origin_block_time_epoch is None
    assert (
        direct.temporal_context.temporal_authority
        is CandidateTemporalAuthority.DIRECT_PUMP_GRADUATION_TIME
    )
    assert direct.temporal_context.pump_origin_block_time_epoch == DIRECT_EPOCH_A


def test_selected_mint_not_in_registry_remains_absent_from_front_door():
    import pathlib

    text = pathlib.Path(
        "src/printer_v1/operator_cli/graduated_supply_front_door.py"
    ).read_text()
    assert "SELECTED_MINT_NOT_IN_REGISTRY" not in text


def test_no_score_rank_confidence_weighting_added():
    import pathlib

    for rel in (
        "src/printer_v1/operator_cli/graduated_supply_front_door.py",
        "src/printer_v1/operator_cli/authoritative_live_operational_campaign.py",
    ):
        text = pathlib.Path(rel).read_text()
        # Guard against new preference/scoring vocabulary in this repair.
        for banned in (
            "confidence_score",
            "rank_weight",
            "source_preference",
            "weighted_score",
        ):
            assert banned not in text

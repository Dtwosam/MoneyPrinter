from __future__ import annotations

from pathlib import Path
import sqlite3

from printer_v1.discovery.later_cycle_fresh_inventory import load_campaign_fresh_moe_candidates
from printer_v1.memory.clean_object_authority import (
    E2Q_CLEAN_CANDIDATE,
    E2Z_CLEAN_OBJECT,
    classify_clean_memory_authority,
)
from printer_v1.trading_flow.evidence_completeness import (
    NOT_NEEDED_ALREADY_RESOLVED,
    NOT_SUPPORTED_BY_APPROVED_FREE_SOURCE,
    plan_optional_wallet_flow_enrichment,
)

ROOT = Path(__file__).resolve().parents[1]


def test_fresh_moe_rehydration_is_campaign_scoped_and_exact() -> None:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE printer_discovery_reserve_layers(
          network TEXT,mint_identity TEXT,pool_address TEXT,reserve_layer TEXT,
          reserve_state TEXT,observed_at TEXT,evidence_expires_at TEXT,
          source_provenance_json TEXT,evidence_json TEXT,last_campaign_id TEXT
        );
        CREATE TABLE printer_exact_market_states(
          network TEXT,mint_identity TEXT,pool_address TEXT,token_program_id TEXT,
          pool_program_id TEXT,base_mint TEXT,quote_mint TEXT,venue TEXT,
          current_state TEXT,last_observed_at TEXT
        );
        """
    )
    provenance = '{"observations":[{"source":"geckoterminal"}]}'
    evidence = '{"liquidity":{"liquidity_usd":12106,"liquidity_observed_at":"2026-08-18T23:27:00+00:00"}}'
    c.execute(
        "INSERT INTO printer_discovery_reserve_layers VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("solana-mainnet","SOLBULL","POOL","MEMORY_OBSERVATION_ELIGIBLE","ACTIVE",
         "2026-08-18T23:27:59+00:00","2026-08-19T00:27:59+00:00",provenance,evidence,"campaign-1"),
    )
    c.execute(
        "INSERT INTO printer_exact_market_states VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("solana-mainnet","SOLBULL","POOL","Tokenkeg","PumpSwapProgram","SOLBULL","So111","pumpswap","CURRENT_VISIBLE","2026-08-18T23:27:59+00:00"),
    )
    rows = load_campaign_fresh_moe_candidates(c, campaign_id="campaign-1", at="2026-08-18T23:40:00+00:00")
    assert len(rows) == 1
    assert rows[0]["mint"] == "SOLBULL"
    assert rows[0]["admission_authority"] == "MARKET_PRESENT_POOL"
    assert rows[0]["memory_observation_eligible"] is True
    assert rows[0]["source_path"] == "campaign_fresh_protocol_confirmed_moe_rehydration"
    assert load_campaign_fresh_moe_candidates(c, campaign_id="campaign-2", at="2026-08-18T23:40:00+00:00") == []


def test_clean_object_authority_preserves_parent_candidate_semantics() -> None:
    window = {
        "memory_quality_label": "PARTIAL_MEMORY",
        "memory_status": "PARTIAL_MEMORY",
        "data_quality_label": "CLEAN_DATA",
        "do_not_train": 0,
        "e2q_audited": True,
    }
    candidate = classify_clean_memory_authority(window=window)
    assert candidate.authority == E2Q_CLEAN_CANDIDATE
    clean = classify_clean_memory_authority(
        window=window,
        episode={"memory_quality_label":"CLEAN_MEMORY","memory_status":"CLEAN_MEMORY","do_not_train":0},
        fingerprint={"memory_status":"CLEAN_MEMORY"},
    )
    assert clean.authority == E2Z_CLEAN_OBJECT
    assert clean.future_retrieval_candidate is True
    assert clean.retrieval_enabled is False


def test_optional_wallet_flow_collection_is_accounted_without_becoming_clean_blocker() -> None:
    partial = plan_optional_wallet_flow_enrichment(
        {"unique_wallets_5m":None,"buy_volume_5m":None,"sell_volume_5m":None},
        approved_free_enricher_available=False,
        source_budget_available=True,
    )
    assert partial.status == NOT_SUPPORTED_BY_APPROVED_FREE_SOURCE
    assert partial.clean_memory_blocker is False
    full = plan_optional_wallet_flow_enrichment(
        {"unique_wallets_5m":10,"buy_volume_5m":1.0,"sell_volume_5m":2.0},
        approved_free_enricher_available=False,
        source_budget_available=True,
    )
    assert full.status == NOT_NEEDED_ALREADY_RESOLVED


def test_cycle2_fresh_moe_is_wired_into_persistent_supply() -> None:
    text = (ROOT / "src/printer_v1/discovery/eligible_token_supply.py").read_text()
    assert "load_campaign_fresh_moe_candidates" in text
    assert "for candidate in load_campaign_fresh_moe_candidates(" in text
    assert 'endswith(":c0002")' in text
    assert "assess_tracking_handoff_by_identity" in text
    assert "campaign_eligible[mint] = accepted" in text


def test_cycle2_temporal_ledger_uses_full_attempt_horizon_and_yields_refresh() -> None:
    text = (ROOT / "src/printer_v1/discovery/eligible_token_supply.py").read_text()
    assert "deadline_dt - timedelta(" in text
    assert "seconds=PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS" in text
    assert "remaining_refresh_window" in text
    assert '_request_temporal_refresh(' in text


def test_weaker_unresolved_identity_cannot_demote_resolved_programs() -> None:
    text = (ROOT / "src/printer_v1/discovery/permanent_discovery_availability.py").read_text()
    assert "new_unresolved" in text
    assert "preserved_identity_values" in text


def test_4h_quality_path_persists_u2_before_clean_object_creation() -> None:
    text = (ROOT / "src/printer_v1/operator_cli/one_token_4h_runtime.py").read_text()
    u2 = text.index("persist_coverage_for_windows")
    e2z = text.index("create_clean_memory_from_window", u2)
    assert u2 < e2z
    assert '"lane_u2"' in text


def test_trading_flow_recorder_persists_optional_completeness_accounting() -> None:
    text = (ROOT / "src/printer_v1/trading_flow/recorder.py").read_text()
    assert "plan_optional_wallet_flow_enrichment" in text
    assert "optional_wallet_flow_enrichment" in text

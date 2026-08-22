"""Cycle-1 pre-handoff persistence wiring proofs (real combined path)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery import combined_executor as executor_mod
from printer_v1.operator_cli import cadence_authority as authority
from printer_v1.operator_cli.cadence_authority import (
    persist_cycle1_current_batch_discovery_lane,
    resolve_cycle1_handoff_tracking_lane,
)

NOW = datetime(2026, 8, 22, 17, 0, tzinfo=timezone.utc)
BATCH = "discovery-batch:campaign-1:run-1:cycle-1"


def test_prepare_is_outside_handoff_and_resolve_is_consumer_only() -> None:
    handoff_src = Path(executor_mod.__file__).read_text(encoding="utf-8")
    auth_src = Path(authority.__file__).read_text(encoding="utf-8")

    assert "def _prepare_cycle1_persisted_lane_before_handoff(" in handoff_src
    assert "persist_cycle1_current_batch_discovery_lane" in handoff_src
    # Both INITIAL and replacement paths prepare before consuming handoff.
    for owner in (
        "def _atomic_initial_two_slot_handoff(",
        "def _persist_selection_and_handoff(",
    ):
        start = handoff_src.index(owner)
        end = handoff_src.index("\n    def ", start + 1)
        body = handoff_src[start:end]
        if "self._handoff_one_slot(" in body:
            assert "self._prepare_cycle1_persisted_lane_before_handoff(" in body
            assert body.index("self._prepare_cycle1_persisted_lane_before_handoff(") < body.index(
                "self._handoff_one_slot("
            )

    start = handoff_src.index("def _handoff_one_slot(")
    end = handoff_src.index("\n    def ", start + 1)
    body = handoff_src[start:end]
    assert "resolve_cycle1_handoff_tracking_lane" in body
    assert "persist_cycle1_current_batch_discovery_lane" not in body
    assert "record_discovery_candidate" not in body
    assert "classify_discovery_candidate" not in body

    resolve_start = auth_src.index("def resolve_cycle1_handoff_tracking_lane(")
    resolve_end = auth_src.index("\ndef ", resolve_start + 1)
    resolve_body = auth_src[resolve_start:resolve_end]
    assert "record_discovery_candidate" not in resolve_body
    assert "classify_discovery_candidate" not in resolve_body
    assert 'candidate["source_channel"] = "PUMPSWAP_GRADUATED"' not in auth_src


def test_persist_owner_uses_existing_classifier_and_record_helper() -> None:
    auth_src = Path(authority.__file__).read_text(encoding="utf-8")
    start = auth_src.index("def persist_cycle1_current_batch_discovery_lane(")
    end = auth_src.index("\ndef ", start + 1)
    body = auth_src[start:end]
    assert "classify_discovery_candidate" in body
    assert "choose_tracking_lane" in body
    assert "record_discovery_candidate" in body
    assert "lookup_discovery_candidate_tracking_lane" in body
    assert 'source_channel = "PUMPSWAP_GRADUATED"' not in body
    assert 'candidate["source_channel"] = "PUMPSWAP_GRADUATED"' not in body


@pytest.fixture()
def conn(tmp_path: Path):
    path = tmp_path / "cycle1_persist.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES ('campaign-1','RUNNING','OPERATIONAL_PERSISTENT','db-1','policy-1')"
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json) VALUES (?,?,?,?,?)",
        ("configuration-1", "campaign-1", "a" * 64, "{}", "{}"),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "factory-1",
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            "{}",
            NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "campaign-run-1",
            "campaign-1",
            1,
            "RUNNING",
            "factory-1",
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_cycles("
        "cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "cycle-1",
            "campaign-1",
            "campaign-run-1",
            1,
            "SELECTING",
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    yield connection
    connection.close()


def _seed_batch_market_observation(
    connection: sqlite3.Connection,
    *,
    mint: str,
    pair: str,
    liquidity_usd: float,
    volume_5m: float,
    txns_5m: int,
) -> None:
    connection.execute(
        """
        INSERT INTO printer_discovery_batches(
            discovery_batch_id, campaign_id, configuration_id, run_id, cycle_id,
            cycle_cutoff, policy_version, provider_contract_versions_json,
            git_provenance_identity, campaign_selection_seed_identity,
            cycle_seed_hash, pump_continuity_state, batch_state, canonical_hash,
            created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'NONE','SELECTING',?,?)
        """,
        (
            BATCH,
            "campaign-1",
            "configuration-1",
            "campaign-run-1",
            "cycle-1",
            NOW.isoformat(),
            "policy-1",
            "{}",
            "git-test",
            "seed-1",
            "b" * 64,
            "c" * 64,
            NOW.isoformat(),
        ),
    )
    req = connection.execute(
        "INSERT INTO printer_source_requests("
        "source_name,request_kind,requested_at,source_status,data_quality_label) "
        "VALUES ('dexscreener','token_discovery',?,'COMPLETE','CLEAN_DATA')",
        (NOW.isoformat(),),
    )
    req_id = int(req.lastrowid)
    payload = (
        '[{"chainId":"solana","baseToken":{"address":"%s"},"pairAddress":"%s",'
        '"priceUsd":0.01,"liquidity":{"usd":%s},"volume":{"m5":%s,"h1":200},'
        '"txns":{"m5":%s,"h1":5}}]'
        % (mint, pair, liquidity_usd, volume_5m, txns_5m)
    )
    resp = connection.execute(
        "INSERT INTO printer_source_responses("
        "source_request_id,source_name,received_at,source_status,data_quality_label,"
        "normalized_payload_json) VALUES (?,'dexscreener',?,'COMPLETE','CLEAN_DATA',?)",
        (req_id, NOW.isoformat(), payload),
    )
    response_id = int(resp.lastrowid)
    job = connection.execute(
        "INSERT INTO printer_scheduler_jobs("
        "job_name,job_kind,target_table,priority,status,scheduled_for) "
        "VALUES ('w','DISCOVERY_REFRESH','printer_discovery_work',10,'SUCCEEDED',?)",
        (NOW.isoformat(),),
    )
    work_id = "work:batch-dex"
    connection.execute(
        """
        INSERT INTO printer_discovery_work(
            discovery_work_id, discovery_batch_id, campaign_id, run_id, cycle_id,
            scheduler_job_id, work_type, work_state, deadline_at,
            first_terminal_cause, terminal_at, created_at, updated_at
        ) VALUES (?,?,?,?,?,?, 'DISCOVERY_DEXSCREENER_ACTIVE', 'SUCCEEDED', ?,
                  'COMPLETE', ?, ?, ?)
        """,
        (
            work_id,
            BATCH,
            "campaign-1",
            "campaign-run-1",
            "cycle-1",
            int(job.lastrowid),
            NOW.isoformat(),
            NOW.isoformat(),
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    connection.execute(
        """
        INSERT INTO printer_discovery_work_source_links(
            discovery_work_id, link_ordinal, source_request_id, source_response_id, created_at
        ) VALUES (?,1,?,?,?)
        """,
        (work_id, req_id, response_id, NOW.isoformat()),
    )
    connection.execute(
        """
        INSERT INTO printer_discovery_provider_observations(
            observation_id, discovery_batch_id, discovery_work_id, campaign_id, run_id,
            cycle_id, source_name, request_kind, channel, mint_identity, market_identity,
            lifecycle_identity, observed_at, captured_at, raw_payload_hash,
            source_request_id, source_response_id, factual_payload_json, observation_hash,
            created_at
        ) VALUES (?,?,?,?,?,?, 'dexscreener','token_discovery','ACTIVE_PUMPFUN',
                  ?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "obs-1",
            BATCH,
            work_id,
            "campaign-1",
            "campaign-run-1",
            "cycle-1",
            mint,
            f"solana:pumpswap:{pair}",
            "PUMP_LIFECYCLE_UNKNOWN",
            NOW.isoformat(),
            NOW.isoformat(),
            "e" * 64,
            req_id,
            response_id,
            f'{{"mint":"{mint}","pool":"{pair}"}}',
            "d" * 64,
            NOW.isoformat(),
        ),
    )


def test_persist_normal_then_resolve_consumer_no_extra_row(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (1,'mint-n','solana')"
    )
    conn.execute(
        "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
        "VALUES (101,1,'pair-n','mint-n')"
    )
    _seed_batch_market_observation(
        conn,
        mint="mint-n",
        pair="pair-n",
        liquidity_usd=1500,
        volume_5m=50,
        txns_5m=2,
    )
    conn.commit()
    lane = persist_cycle1_current_batch_discovery_lane(
        conn,
        discovery_batch_id=BATCH,
        token_id=1,
        pair_id=101,
        token_mint="mint-n",
        pair_address="pair-n",
        now=NOW.isoformat(),
    )
    assert lane == "TRACK_NORMAL"
    count = conn.execute("SELECT COUNT(*) FROM printer_discovery_candidates").fetchone()[0]
    assert count == 1
    resolved = resolve_cycle1_handoff_tracking_lane(
        conn,
        token_id=1,
        pair_id=101,
        token_mint="mint-n",
        pair_address="pair-n",
        discovery_batch_id=BATCH,
        candidate_tracking_lane="TRACK_NORMAL",
    )
    assert resolved == "TRACK_NORMAL"
    assert (
        conn.execute("SELECT COUNT(*) FROM printer_discovery_candidates").fetchone()[0]
        == count
    )


def test_persist_fast_then_resolve_consumer_no_extra_row(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (1,'mint-f','solana')"
    )
    conn.execute(
        "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
        "VALUES (101,1,'pair-f','mint-f')"
    )
    _seed_batch_market_observation(
        conn,
        mint="mint-f",
        pair="pair-f",
        liquidity_usd=6000,
        volume_5m=2000,
        txns_5m=20,
    )
    conn.commit()
    lane = persist_cycle1_current_batch_discovery_lane(
        conn,
        discovery_batch_id=BATCH,
        token_id=1,
        pair_id=101,
        token_mint="mint-f",
        pair_address="pair-f",
        now=NOW.isoformat(),
    )
    assert lane == "TRACK_FAST"
    count = conn.execute("SELECT COUNT(*) FROM printer_discovery_candidates").fetchone()[0]
    assert count == 1
    assert (
        resolve_cycle1_handoff_tracking_lane(
            conn,
            token_id=1,
            pair_id=101,
            token_mint="mint-f",
            pair_address="pair-f",
            discovery_batch_id=BATCH,
            candidate_tracking_lane="TRACK_FAST",
        )
        == "TRACK_FAST"
    )
    assert (
        conn.execute("SELECT COUNT(*) FROM printer_discovery_candidates").fetchone()[0]
        == count
    )

"""Lane 1 final provenance: Cycle-1 consumes persisted current-batch lane only."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.cadence_authority import (
    CadenceAuthorityError,
    lookup_discovery_candidate_tracking_lane,
    resolve_cycle1_handoff_tracking_lane,
)


NOW = datetime(2026, 8, 22, 16, 0, tzinfo=timezone.utc)
BATCH_CURRENT = "discovery-batch:campaign-1:run-1:cycle-1"
BATCH_OLD = "discovery-batch:campaign-1:run-1:cycle-legacy"


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "lane1_persisted.sqlite3"
    apply_migrations(path)
    return path


@pytest.fixture()
def conn(db_path: Path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    yield connection
    connection.close()


def _seed(connection: sqlite3.Connection) -> None:
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


def _ensure_cycle(connection: sqlite3.Connection, *, cycle_id: str, ordinal: int) -> None:
    if connection.execute(
        "SELECT 1 FROM printer_memory_factory_campaign_cycles WHERE cycle_id=?",
        (cycle_id,),
    ).fetchone():
        return
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_cycles("
        "cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            cycle_id,
            "campaign-1",
            "campaign-run-1",
            ordinal,
            "SELECTING",
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )


def _insert_token_pair(connection, *, token_id: int, pair_id: int) -> None:
    connection.execute(
        "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?, 'solana')",
        (token_id, f"mint-{token_id}"),
    )
    connection.execute(
        "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) VALUES (?,?,?,?)",
        (pair_id, token_id, f"pair-{pair_id}", f"mint-{token_id}"),
    )


def _insert_persisted_lane(
    connection,
    *,
    discovery_batch_id: str,
    cycle_id: str,
    cycle_ordinal: int,
    token_id: int,
    pair_id: int,
    tracking_lane: str,
    link_suffix: str,
) -> None:
    _ensure_cycle(connection, cycle_id=cycle_id, ordinal=cycle_ordinal)
    if connection.execute(
        "SELECT 1 FROM printer_discovery_batches WHERE discovery_batch_id=?",
        (discovery_batch_id,),
    ).fetchone() is None:
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
                discovery_batch_id,
                "campaign-1",
                "configuration-1",
                "campaign-run-1",
                cycle_id,
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
    work_id = f"work:{discovery_batch_id}:dex"
    if connection.execute(
        "SELECT 1 FROM printer_discovery_work WHERE discovery_work_id=?", (work_id,)
    ).fetchone() is None:
        job = connection.execute(
            "INSERT INTO printer_scheduler_jobs("
            "job_name,job_kind,target_table,priority,status,scheduled_for) "
            "VALUES (?,?,?,?, 'SUCCEEDED',?)",
            (
                f"discovery-work:{discovery_batch_id}",
                "DISCOVERY_REFRESH",
                "printer_discovery_work",
                10,
                NOW.isoformat(),
            ),
        )
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
                discovery_batch_id,
                "campaign-1",
                "campaign-run-1",
                cycle_id,
                int(job.lastrowid),
                NOW.isoformat(),
                NOW.isoformat(),
                NOW.isoformat(),
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
    resp = connection.execute(
        "INSERT INTO printer_source_responses("
        "source_request_id,source_name,received_at,source_status,data_quality_label,"
        "normalized_payload_json) VALUES (?,'dexscreener',?,'COMPLETE','CLEAN_DATA',?)",
        (
            req_id,
            NOW.isoformat(),
            '{"pairs":[{"chainId":"solana","baseToken":{"address":"x"},'
            '"pairAddress":"y","priceUsd":0.01,"liquidity":{"usd":1500},'
            '"volume":{"h1":200},"txns":{"h1":5}}]}',
        ),
    )
    response_id = int(resp.lastrowid)
    ordinal = int(
        connection.execute(
            "SELECT COALESCE(MAX(link_ordinal),0)+1 FROM printer_discovery_work_source_links "
            "WHERE discovery_work_id=?",
            (work_id,),
        ).fetchone()[0]
    )
    connection.execute(
        """
        INSERT INTO printer_discovery_work_source_links(
            discovery_work_id, link_ordinal, source_request_id, source_response_id, created_at
        ) VALUES (?,?,?,?,?)
        """,
        (work_id, ordinal, req_id, response_id, NOW.isoformat()),
    )
    connection.execute(
        """
        INSERT INTO printer_discovery_candidates(
            source_response_id, token_id, pair_id, source_name,
            discovery_label, discovery_action, source_status, data_quality_label,
            raw_candidate_payload_json, normalized_candidate_payload_json,
            lifecycle_state, tracking_lane, priority_reason
        ) VALUES (?,?,?,'dexscreener',?,?, 'COMPLETE','CLEAN_DATA','{}','{}',?,?,?)
        """,
        (
            response_id,
            token_id,
            pair_id,
            f"{tracking_lane}_CANDIDATE",
            tracking_lane,
            tracking_lane,
            tracking_lane,
            f"test:{link_suffix}",
        ),
    )


def test_a_current_batch_persisted_normal(conn: sqlite3.Connection) -> None:
    _seed(conn)
    _insert_token_pair(conn, token_id=1, pair_id=101)
    _insert_persisted_lane(
        conn,
        discovery_batch_id=BATCH_CURRENT,
        cycle_id="cycle-1",
        cycle_ordinal=1,
        token_id=1,
        pair_id=101,
        tracking_lane="TRACK_NORMAL",
        link_suffix="a",
    )
    conn.commit()
    assert (
        resolve_cycle1_handoff_tracking_lane(
            conn,
            token_id=1,
            pair_id=101,
            token_mint="mint-1",
            pair_address="pair-101",
            discovery_batch_id=BATCH_CURRENT,
        )
        == "TRACK_NORMAL"
    )


def test_b_current_batch_persisted_fast(conn: sqlite3.Connection) -> None:
    _seed(conn)
    _insert_token_pair(conn, token_id=1, pair_id=101)
    _insert_persisted_lane(
        conn,
        discovery_batch_id=BATCH_CURRENT,
        cycle_id="cycle-1",
        cycle_ordinal=1,
        token_id=1,
        pair_id=101,
        tracking_lane="TRACK_FAST",
        link_suffix="b",
    )
    conn.commit()
    assert (
        resolve_cycle1_handoff_tracking_lane(
            conn,
            token_id=1,
            pair_id=101,
            token_mint="mint-1",
            pair_address="pair-101",
            discovery_batch_id=BATCH_CURRENT,
        )
        == "TRACK_FAST"
    )


def test_c_classifiable_payload_without_persisted_row_fails_closed_no_write(
    conn: sqlite3.Connection,
) -> None:
    _seed(conn)
    _insert_token_pair(conn, token_id=1, pair_id=101)
    _ensure_cycle(conn, cycle_id="cycle-1", ordinal=1)
    # Batch + source payload exist, but no printer_discovery_candidates row.
    connection = conn
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
            BATCH_CURRENT,
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
        '[{"chainId":"solana","baseToken":{"address":"mint-1"},'
        '"pairAddress":"pair-101","priceUsd":0.01,"liquidity":{"usd":1500},'
        '"volume":{"h1":200},"txns":{"h1":5}}]'
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
    work_id = "work:payload-only"
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
            BATCH_CURRENT,
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
                  'mint-1','solana:pumpswap:pair-101','PUMP_LIFECYCLE_UNKNOWN',?,?,?,
                  ?,?,?,?,?)
        """,
        (
            "obs-1",
            BATCH_CURRENT,
            work_id,
            "campaign-1",
            "campaign-run-1",
            "cycle-1",
            NOW.isoformat(),
            NOW.isoformat(),
            "e" * 64,
            req_id,
            response_id,
            '{"mint":"mint-1","pool":"pair-101"}',
            "d" * 64,
            NOW.isoformat(),
        ),
    )
    conn.commit()
    before = conn.execute("SELECT COUNT(*) FROM printer_discovery_candidates").fetchone()[0]
    with pytest.raises(CadenceAuthorityError, match="DISCOVERY_TRACKING_LANE_MISSING"):
        resolve_cycle1_handoff_tracking_lane(
            conn,
            token_id=1,
            pair_id=101,
            token_mint="mint-1",
            pair_address="pair-101",
            discovery_batch_id=BATCH_CURRENT,
            candidate_tracking_lane=None,
            now=NOW.isoformat(),
        )
    after = conn.execute("SELECT COUNT(*) FROM printer_discovery_candidates").fetchone()[0]
    assert after == before == 0


def test_d_carrier_fast_persisted_normal_conflicts(conn: sqlite3.Connection) -> None:
    _seed(conn)
    _insert_token_pair(conn, token_id=1, pair_id=101)
    _insert_persisted_lane(
        conn,
        discovery_batch_id=BATCH_CURRENT,
        cycle_id="cycle-1",
        cycle_ordinal=1,
        token_id=1,
        pair_id=101,
        tracking_lane="TRACK_NORMAL",
        link_suffix="d",
    )
    conn.commit()
    with pytest.raises(CadenceAuthorityError, match="DISCOVERY_TRACKING_LANE_CONFLICT"):
        resolve_cycle1_handoff_tracking_lane(
            conn,
            token_id=1,
            pair_id=101,
            token_mint="mint-1",
            pair_address="pair-101",
            discovery_batch_id=BATCH_CURRENT,
            candidate_tracking_lane="TRACK_FAST",
        )


def test_e_carrier_normal_persisted_fast_conflicts(conn: sqlite3.Connection) -> None:
    _seed(conn)
    _insert_token_pair(conn, token_id=1, pair_id=101)
    _insert_persisted_lane(
        conn,
        discovery_batch_id=BATCH_CURRENT,
        cycle_id="cycle-1",
        cycle_ordinal=1,
        token_id=1,
        pair_id=101,
        tracking_lane="TRACK_FAST",
        link_suffix="e",
    )
    conn.commit()
    with pytest.raises(CadenceAuthorityError, match="DISCOVERY_TRACKING_LANE_CONFLICT"):
        resolve_cycle1_handoff_tracking_lane(
            conn,
            token_id=1,
            pair_id=101,
            token_mint="mint-1",
            pair_address="pair-101",
            discovery_batch_id=BATCH_CURRENT,
            candidate_tracking_lane="TRACK_NORMAL",
        )


def test_f_multiple_current_batch_rows_all_normal(conn: sqlite3.Connection) -> None:
    _seed(conn)
    _insert_token_pair(conn, token_id=1, pair_id=101)
    _insert_persisted_lane(
        conn,
        discovery_batch_id=BATCH_CURRENT,
        cycle_id="cycle-1",
        cycle_ordinal=1,
        token_id=1,
        pair_id=101,
        tracking_lane="TRACK_NORMAL",
        link_suffix="f1",
    )
    _insert_persisted_lane(
        conn,
        discovery_batch_id=BATCH_CURRENT,
        cycle_id="cycle-1",
        cycle_ordinal=1,
        token_id=1,
        pair_id=101,
        tracking_lane="TRACK_NORMAL",
        link_suffix="f2",
    )
    conn.commit()
    assert (
        lookup_discovery_candidate_tracking_lane(
            conn, token_id=1, pair_id=101, discovery_batch_id=BATCH_CURRENT
        )
        == "TRACK_NORMAL"
    )


def test_g_current_batch_fast_and_normal_conflict(conn: sqlite3.Connection) -> None:
    _seed(conn)
    _insert_token_pair(conn, token_id=1, pair_id=101)
    _insert_persisted_lane(
        conn,
        discovery_batch_id=BATCH_CURRENT,
        cycle_id="cycle-1",
        cycle_ordinal=1,
        token_id=1,
        pair_id=101,
        tracking_lane="TRACK_FAST",
        link_suffix="g-fast",
    )
    _insert_persisted_lane(
        conn,
        discovery_batch_id=BATCH_CURRENT,
        cycle_id="cycle-1",
        cycle_ordinal=1,
        token_id=1,
        pair_id=101,
        tracking_lane="TRACK_NORMAL",
        link_suffix="g-normal",
    )
    conn.commit()
    with pytest.raises(CadenceAuthorityError, match="DISCOVERY_TRACKING_LANE_CONFLICT"):
        lookup_discovery_candidate_tracking_lane(
            conn, token_id=1, pair_id=101, discovery_batch_id=BATCH_CURRENT
        )


def test_h_historical_present_current_absent_missing(conn: sqlite3.Connection) -> None:
    _seed(conn)
    _insert_token_pair(conn, token_id=1, pair_id=101)
    _insert_persisted_lane(
        conn,
        discovery_batch_id=BATCH_OLD,
        cycle_id="cycle-legacy",
        cycle_ordinal=9,
        token_id=1,
        pair_id=101,
        tracking_lane="TRACK_FAST",
        link_suffix="h-old",
    )
    conn.commit()
    with pytest.raises(CadenceAuthorityError, match="DISCOVERY_TRACKING_LANE_MISSING"):
        resolve_cycle1_handoff_tracking_lane(
            conn,
            token_id=1,
            pair_id=101,
            token_mint="mint-1",
            pair_address="pair-101",
            discovery_batch_id=BATCH_CURRENT,
        )


def test_resolve_does_not_call_classify_or_persist_helpers() -> None:
    auth = Path("src/printer_v1/operator_cli/cadence_authority.py").read_text(
        encoding="utf-8"
    )
    start = auth.index("def resolve_cycle1_handoff_tracking_lane(")
    end = auth.index("\ndef ", start + 1)
    body = auth[start:end]
    assert "lookup_discovery_candidate_tracking_lane" in body
    assert "candidate_tracking_lane" in body
    assert "DISCOVERY_TRACKING_LANE_CONFLICT" in body
    # Consumer-only: no classify/persist inside resolve.
    assert "classify_discovery_candidate" not in body
    assert "record_discovery_candidate" not in body
    assert "persist_cycle1_current_batch_discovery_lane" not in body
    # Upstream persist owner exists separately.
    assert "def persist_cycle1_current_batch_discovery_lane(" in auth

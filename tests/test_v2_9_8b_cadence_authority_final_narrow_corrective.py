"""V2-9.8B Design Lane 1 — final narrow corrective proofs (3 remaining holes)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.cadence_authority import (
    CadenceAuthorityError,
    claim_tracking_authority_for_slot_insert,
    lookup_discovery_candidate_tracking_lane,
    resolve_cycle1_handoff_tracking_lane,
    validate_existing_slot_tracking_queue_for_handoff,
)
from printer_v1.operator_cli.campaign_ownership import (
    CampaignOwnershipError,
    create_cycle_with_two_slots,
    transition_state,
)


NOW = datetime(2026, 8, 22, 15, 0, tzinfo=timezone.utc)
BATCH_CURRENT = "discovery-batch:campaign-1:run-1:cycle-1"
BATCH_OLD = "discovery-batch:campaign-1:run-1:cycle-0"


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "narrow_corrective.sqlite3"
    apply_migrations(path)
    return path


@pytest.fixture()
def conn(db_path: Path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    yield connection
    connection.close()


def _seed_campaign(connection: sqlite3.Connection) -> None:
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


def _ensure_cycle(connection: sqlite3.Connection, *, cycle_id: str = "cycle-1") -> None:
    if (
        connection.execute(
            "SELECT 1 FROM printer_memory_factory_campaign_cycles WHERE cycle_id=?",
            (cycle_id,),
        ).fetchone()
        is not None
    ):
        return
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_cycles("
        "cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            cycle_id,
            "campaign-1",
            "campaign-run-1",
            {"cycle-legacy": 9, "cycle-1": 1}.get(cycle_id, 2),
            "SELECTING",
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )


def _insert_token_pair(connection, *, token_id: int, pair_id: int, token_status=None) -> None:
    connection.execute(
        "INSERT INTO printer_tokens(id,token_mint,chain,token_status) VALUES (?,?, 'solana',?)",
        (token_id, f"mint-{token_id}", token_status),
    )
    connection.execute(
        "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) VALUES (?,?,?,?)",
        (pair_id, token_id, f"pair-{pair_id}", f"mint-{token_id}"),
    )


def _insert_source_response(
    connection, *, source_name: str = "dexscreener"
) -> tuple[int, int]:
    req = connection.execute(
        """
        INSERT INTO printer_source_requests(
            source_name, request_kind, requested_at, source_status, data_quality_label
        ) VALUES (?, 'token_discovery', ?, 'COMPLETE', 'CLEAN_DATA')
        """,
        (source_name, NOW.isoformat()),
    )
    req_id = int(req.lastrowid)
    resp = connection.execute(
        """
        INSERT INTO printer_source_responses(
            source_request_id, source_name, received_at, status_code,
            source_status, data_quality_label, response_hash, normalized_payload_json
        ) VALUES (?, ?, ?, 200, 'COMPLETE', 'CLEAN_DATA', ?, '{}')
        """,
        (req_id, source_name, NOW.isoformat(), "a" * 64),
    )
    return req_id, int(resp.lastrowid)


def _cycle_id_for_batch(discovery_batch_id: str) -> str:
    # One discovery batch per cycle (schema UNIQUE on cycle_id).
    if discovery_batch_id == BATCH_OLD:
        return "cycle-legacy"
    return "cycle-1"


def _link_response_to_batch(
    connection,
    *,
    discovery_batch_id: str,
    source_request_id: int,
    source_response_id: int,
    work_suffix: str,
) -> None:
    del work_suffix  # one reusable dex work row per batch
    cycle_id = _cycle_id_for_batch(discovery_batch_id)
    existing = connection.execute(
        "SELECT 1 FROM printer_discovery_batches WHERE discovery_batch_id=?",
        (discovery_batch_id,),
    ).fetchone()
    if existing is None:
        _ensure_cycle(connection, cycle_id=cycle_id)
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
    if (
        connection.execute(
            "SELECT 1 FROM printer_discovery_work WHERE discovery_work_id=?",
            (work_id,),
        ).fetchone()
        is None
    ):
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
            ) VALUES (?,?,?,?,?,?,?, 'SUCCEEDED', ?, 'COMPLETE', ?, ?, ?)
            """,
            (
                work_id,
                discovery_batch_id,
                "campaign-1",
                "campaign-run-1",
                cycle_id,
                int(job.lastrowid),
                "DISCOVERY_DEXSCREENER_ACTIVE",
                NOW.isoformat(),
                NOW.isoformat(),
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
    link_ordinal = int(
        connection.execute(
            "SELECT COALESCE(MAX(link_ordinal), 0) + 1 "
            "FROM printer_discovery_work_source_links WHERE discovery_work_id=?",
            (work_id,),
        ).fetchone()[0]
    )
    connection.execute(
        """
        INSERT INTO printer_discovery_work_source_links(
            discovery_work_id, link_ordinal, source_request_id, source_response_id,
            created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (work_id, link_ordinal, source_request_id, source_response_id, NOW.isoformat()),
    )

def _insert_batch_discovery_candidate(
    connection,
    *,
    discovery_batch_id: str,
    token_id: int,
    pair_id: int,
    tracking_lane: str,
    work_suffix: str,
) -> int:
    request_id, response_id = _insert_source_response(connection)
    _link_response_to_batch(
        connection,
        discovery_batch_id=discovery_batch_id,
        source_request_id=request_id,
        source_response_id=response_id,
        work_suffix=work_suffix,
    )
    cur = connection.execute(
        """
        INSERT INTO printer_discovery_candidates(
            source_response_id, token_id, pair_id, source_name,
            discovery_label, discovery_action, source_status, data_quality_label,
            raw_candidate_payload_json, normalized_candidate_payload_json,
            lifecycle_state, tracking_lane, priority_reason
        ) VALUES (
            ?, ?, ?, 'dexscreener',
            ?, ?, 'COMPLETE', 'CLEAN_DATA',
            '{}', '{}',
            ?, ?, 'test'
        )
        """,
        (
            response_id,
            token_id,
            pair_id,
            f"{tracking_lane}_CANDIDATE",
            tracking_lane,
            tracking_lane,
            tracking_lane,
        ),
    )
    return int(cur.lastrowid)


# --- 1/2 existing-slot NULL binding ---


def test_existing_slot_null_queue_fails_closed_no_claim_no_first_15m(
    conn: sqlite3.Connection,
) -> None:
    _seed_campaign(conn)
    _insert_token_pair(conn, token_id=1, pair_id=101)
    _insert_token_pair(conn, token_id=2, pair_id=102)
    create_cycle_with_two_slots(
        conn,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        cycle_ordinal=1,
        slots=(
            {
                "token_slot_id": "cycle-1-1",
                "slot_ordinal": 1,
                "token_identity": "t1",
                "token_row_id": 1,
                "mint_identity": "mint-1",
                "pair_identity": "pair-101",
                "pair_row_id": 101,
                "lifecycle_identity": "L1",
                "tracking_queue_id": None,
            },
            {
                "token_slot_id": "cycle-1-2",
                "slot_ordinal": 2,
                "token_identity": "t2",
                "token_row_id": 2,
                "mint_identity": "mint-2",
                "pair_identity": "pair-102",
                "pair_row_id": 102,
                "lifecycle_identity": "L2",
                "tracking_queue_id": None,
            },
        ),
        now=NOW.isoformat(),
    )
    conn.commit()
    queues_before = conn.execute("SELECT COUNT(*) FROM printer_tracking_queue").fetchone()[0]
    jobs_before = conn.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0]

    with pytest.raises(CadenceAuthorityError, match="TRACKING_QUEUE_BINDING_MISSING"):
        validate_existing_slot_tracking_queue_for_handoff(
            conn,
            token_slot_id="cycle-1-1",
            cycle_id="cycle-1",
            token_row_id=1,
            pair_row_id=101,
        )
    # Source scan: operational path must raise unbound, not claim.
    handoff_src = Path(
        "src/printer_v1/discovery/combined_executor.py"
    ).read_text(encoding="utf-8")
    start = handoff_src.index("def _handoff_one_slot(")
    end = handoff_src.index("\n    def ", start + 1)
    body = handoff_src[start:end]
    assert "EXISTING_SLOT_TRACKING_QUEUE_UNBOUND" in body
    assert "existing slot tracking_queue_id is NULL" in body
    # No silent claim branch for NULL binding remains.
    assert "terminal vacant slot with NULL binding cannot be rebound" not in body
    assert "Historical replacement claims a fresh exact-lane queue" not in body

    with pytest.raises(CampaignOwnershipError):
        transition_state(
            conn,
            record_kind="token_slot",
            identity="cycle-1-1",
            expected_state="SELECTED",
            new_state="WINDOW_15M_ACTIVE",
        )
    assert conn.execute("SELECT COUNT(*) FROM printer_tracking_queue").fetchone()[0] == queues_before
    assert conn.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0] == jobs_before
    state = conn.execute(
        "SELECT token_state FROM printer_memory_factory_campaign_token_slots "
        "WHERE token_slot_id='cycle-1-1'"
    ).fetchone()[0]
    assert state == "SELECTED"


def test_existing_slot_valid_bound_queue_still_validates(conn: sqlite3.Connection) -> None:
    _seed_campaign(conn)
    _insert_token_pair(conn, token_id=1, pair_id=101, token_status="TRACK_NORMAL")
    _insert_token_pair(conn, token_id=2, pair_id=102, token_status="TRACK_NORMAL")
    q1 = claim_tracking_authority_for_slot_insert(
        conn, token_row_id=1, pair_row_id=101, tracking_lane="TRACK_NORMAL", now=NOW
    )
    q2 = claim_tracking_authority_for_slot_insert(
        conn, token_row_id=2, pair_row_id=102, tracking_lane="TRACK_NORMAL", now=NOW
    )
    create_cycle_with_two_slots(
        conn,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-1",
        cycle_ordinal=1,
        slots=(
            {
                "token_slot_id": "cycle-1-1",
                "slot_ordinal": 1,
                "token_identity": "t1",
                "token_row_id": 1,
                "mint_identity": "mint-1",
                "pair_identity": "pair-101",
                "pair_row_id": 101,
                "lifecycle_identity": "L1",
                "tracking_queue_id": q1,
            },
            {
                "token_slot_id": "cycle-1-2",
                "slot_ordinal": 2,
                "token_identity": "t2",
                "token_row_id": 2,
                "mint_identity": "mint-2",
                "pair_identity": "pair-102",
                "pair_row_id": 102,
                "lifecycle_identity": "L2",
                "tracking_queue_id": q2,
            },
        ),
        now=NOW.isoformat(),
    )
    conn.commit()
    assert (
        validate_existing_slot_tracking_queue_for_handoff(
            conn,
            token_slot_id="cycle-1-1",
            cycle_id="cycle-1",
            token_row_id=1,
            pair_row_id=101,
        )
        == q1
    )
    transition_state(
        conn,
        record_kind="token_slot",
        identity="cycle-1-1",
        expected_state="SELECTED",
        new_state="WINDOW_15M_ACTIVE",
    )
    assert (
        conn.execute(
            "SELECT token_state FROM printer_memory_factory_campaign_token_slots "
            "WHERE token_slot_id='cycle-1-1'"
        ).fetchone()[0]
        == "WINDOW_15M_ACTIVE"
    )


# --- 3/4/5 current-batch discovery lane lookup ---


def test_current_batch_normal_wins_over_historical_fast(conn: sqlite3.Connection) -> None:
    _seed_campaign(conn)
    _insert_token_pair(conn, token_id=1, pair_id=101)
    _insert_batch_discovery_candidate(
        conn,
        discovery_batch_id=BATCH_OLD,
        token_id=1,
        pair_id=101,
        tracking_lane="TRACK_FAST",
        work_suffix="old-fast",
    )
    _insert_batch_discovery_candidate(
        conn,
        discovery_batch_id=BATCH_CURRENT,
        token_id=1,
        pair_id=101,
        tracking_lane="TRACK_NORMAL",
        work_suffix="cur-normal",
    )
    conn.commit()
    assert (
        lookup_discovery_candidate_tracking_lane(
            conn,
            token_id=1,
            pair_id=101,
            discovery_batch_id=BATCH_CURRENT,
        )
        == "TRACK_NORMAL"
    )
    assert (
        resolve_cycle1_handoff_tracking_lane(
            conn,
            token_id=1,
            pair_id=101,
            token_mint="mint-1",
            pair_address="pair-101",
            discovery_batch_id=BATCH_CURRENT,
            now=NOW.isoformat(),
        )
        == "TRACK_NORMAL"
    )


def test_current_batch_fast_wins_over_historical_normal(conn: sqlite3.Connection) -> None:
    _seed_campaign(conn)
    _insert_token_pair(conn, token_id=1, pair_id=101)
    _insert_batch_discovery_candidate(
        conn,
        discovery_batch_id=BATCH_OLD,
        token_id=1,
        pair_id=101,
        tracking_lane="TRACK_NORMAL",
        work_suffix="old-normal",
    )
    _insert_batch_discovery_candidate(
        conn,
        discovery_batch_id=BATCH_CURRENT,
        token_id=1,
        pair_id=101,
        tracking_lane="TRACK_FAST",
        work_suffix="cur-fast",
    )
    conn.commit()
    assert (
        lookup_discovery_candidate_tracking_lane(
            conn,
            token_id=1,
            pair_id=101,
            discovery_batch_id=BATCH_CURRENT,
        )
        == "TRACK_FAST"
    )


def test_historical_only_lane_never_used_without_current_batch(
    conn: sqlite3.Connection,
) -> None:
    _seed_campaign(conn)
    _insert_token_pair(conn, token_id=1, pair_id=101)
    _insert_batch_discovery_candidate(
        conn,
        discovery_batch_id=BATCH_OLD,
        token_id=1,
        pair_id=101,
        tracking_lane="TRACK_FAST",
        work_suffix="old-only",
    )
    conn.commit()
    with pytest.raises(CadenceAuthorityError, match="DISCOVERY_TRACKING_LANE_MISSING"):
        lookup_discovery_candidate_tracking_lane(
            conn,
            token_id=1,
            pair_id=101,
            discovery_batch_id=BATCH_CURRENT,
        )
    with pytest.raises(CadenceAuthorityError, match="DISCOVERY_TRACKING_LANE_MISSING"):
        resolve_cycle1_handoff_tracking_lane(
            conn,
            token_id=1,
            pair_id=101,
            token_mint="mint-1",
            pair_address="pair-101",
            discovery_batch_id=BATCH_CURRENT,
            now=NOW.isoformat(),
        )


# --- 6/7 no fabricated channel / fail closed ---


def test_missing_source_channel_never_becomes_pumpswap_graduated() -> None:
    auth_src = Path("src/printer_v1/operator_cli/cadence_authority.py").read_text(
        encoding="utf-8"
    )
    assert 'candidate["source_channel"] = "PUMPSWAP_GRADUATED"' not in auth_src
    assert 'source_channel = "PUMPSWAP_GRADUATED"' not in auth_src
    resolve_start = auth_src.index("def resolve_cycle1_handoff_tracking_lane(")
    resolve_end = auth_src.index("\ndef ", resolve_start + 1)
    resolve_body = auth_src[resolve_start:resolve_end]
    assert "record_discovery_candidate" not in resolve_body


def test_missing_truthful_lane_provenance_fails_closed(conn: sqlite3.Connection) -> None:
    _insert_token_pair(conn, token_id=1, pair_id=101)
    conn.commit()
    with pytest.raises(CadenceAuthorityError, match="DISCOVERY_TRACKING_LANE_MISSING"):
        resolve_cycle1_handoff_tracking_lane(
            conn,
            token_id=1,
            pair_id=101,
            token_mint="mint-1",
            pair_address="pair-101",
            discovery_batch_id=None,
            now=NOW.isoformat(),
        )
    with pytest.raises(CadenceAuthorityError, match="DISCOVERY_TRACKING_LANE_MISSING"):
        resolve_cycle1_handoff_tracking_lane(
            conn,
            token_id=1,
            pair_id=101,
            token_mint="mint-1",
            pair_address="pair-101",
            discovery_batch_id="",
            now=NOW.isoformat(),
        )


def test_cycle1_fast_and_normal_current_batch_remain_green(conn: sqlite3.Connection) -> None:
    _seed_campaign(conn)
    _insert_token_pair(conn, token_id=1, pair_id=101)
    _insert_token_pair(conn, token_id=2, pair_id=102)
    _insert_batch_discovery_candidate(
        conn,
        discovery_batch_id=BATCH_CURRENT,
        token_id=1,
        pair_id=101,
        tracking_lane="TRACK_NORMAL",
        work_suffix="n1",
    )
    _insert_batch_discovery_candidate(
        conn,
        discovery_batch_id=BATCH_CURRENT,
        token_id=2,
        pair_id=102,
        tracking_lane="TRACK_FAST",
        work_suffix="f2",
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
            now=NOW.isoformat(),
        )
        == "TRACK_NORMAL"
    )
    assert (
        resolve_cycle1_handoff_tracking_lane(
            conn,
            token_id=2,
            pair_id=102,
            token_mint="mint-2",
            pair_address="pair-102",
            discovery_batch_id=BATCH_CURRENT,
            now=NOW.isoformat(),
        )
        == "TRACK_FAST"
    )

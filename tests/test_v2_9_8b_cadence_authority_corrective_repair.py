"""V2-9.8B Design Lane 1 corrective repair — frozen-lane provenance + authority holes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from printer_v1.db import apply_migrations
from printer_v1.lifecycle.contracts import QueueStatus
from printer_v1.lifecycle.tracking_queue import set_queue_status
from printer_v1.operator_cli.cadence_authority import (
    CADENCE_AUTHORITY_CONFLICT,
    CADENCE_AUTHORITY_RESOLVED,
    CadenceAuthorityError,
    assert_slot_bound_tracking_authority_for_window_15m_active,
    claim_tracking_authority_for_slot_insert,
    require_campaign_slot_tracking_authority,
    resolve_campaign_slot_cadence_authority,
    terminalize_unstarted_cycle_tracking_claims,
    validate_existing_slot_tracking_queue_for_handoff,
)
from printer_v1.operator_cli.campaign_ownership import (
    CampaignOwnershipError,
    create_cycle_with_two_slots,
    transition_state,
)
from printer_v1.operator_cli.pre_admission_discovery_attempt import (
    FROZEN_LANE_DECISION_OWNER,
    PreAdmissionAttemptError,
    PreAdmissionAttemptItem,
    attach_frozen_tracking_lane,
    project_classifier_candidate_from_pre_admission_evidence,
)
from printer_v1.snapshots.cadence_policy import (
    CADENCE_POLICY_BLOCKED,
    CADENCE_POLICY_PASS,
    evaluate_cadence_policy,
    get_policy,
)


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
WIN_START = NOW
WIN_END = NOW + timedelta(seconds=900)


def _evidence(
    *,
    liquidity_usd: float,
    price_usd: float = 0.01,
    volume_5m: float = 0.0,
    txns_5m: int = 0,
    volume_1h: float = 200.0,
    txns_1h: int = 5,
    volume_24h: float = 200.0,
    txns_24h: int = 10,
    provenance: str = "PUMPSWAP_GRADUATED",
) -> str:
    return json.dumps(
        {
            "candidate": {
                "liquidity_usd": liquidity_usd,
                "price_usd": price_usd,
                "volume_5m": volume_5m,
                "txns_5m": txns_5m,
                "volume_1h": volume_1h,
                "txns_1h": txns_1h,
                "volume_24h": volume_24h,
                "txns_24h": txns_24h,
                "provenance": provenance,
                "source_channel": provenance,
            }
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _base_item(
    slot: int,
    *,
    evidence_json: str,
    attempt_id: str = "attempt-1",
) -> PreAdmissionAttemptItem:
    digest = hashlib.sha256(evidence_json.encode()).hexdigest()
    return PreAdmissionAttemptItem(
        attempt_id=attempt_id,
        slot_ordinal=slot,
        token_identity=f"solana-mainnet:mint-{slot}",
        token_row_id=slot,
        mint_identity=f"mint-{slot}",
        pair_identity=f"pair-{slot}",
        pair_row_id=100 + slot,
        lifecycle_identity="PUMPSWAP_GRADUATED_CONFIRMED",
        canonical_market_identity=f"solana-mainnet:pumpswap:pair-{slot}",
        canonical_pool_identity=f"pair-{slot}",
        canonical_evidence_json=evidence_json,
        canonical_evidence_hash=digest,
        evidence_version="v1",
        observed_at=NOW,
        channel_labels=("PUMPSWAP_GRADUATED",),
    )


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "corrective.sqlite3"
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
        ("factory-1", "RUNNING", "WINDOW_15M", "OPERATIONAL_PERSISTENT", "a" * 64, "{}", NOW.isoformat()),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("campaign-run-1", "campaign-1", 1, "RUNNING", "factory-1", NOW.isoformat(), NOW.isoformat()),
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


def test_attach_frozen_lane_normal_and_fast(conn: sqlite3.Connection) -> None:
    normal = attach_frozen_tracking_lane(
        _base_item(1, evidence_json=_evidence(liquidity_usd=1500.0)),
        now=NOW,
    )
    assert normal.frozen_tracking_lane == "TRACK_NORMAL"
    assert normal.frozen_discovery_action == "TRACK_NORMAL"
    assert normal.frozen_lane_decision_owner == FROZEN_LANE_DECISION_OWNER

    fast = attach_frozen_tracking_lane(
        _base_item(
            2,
            evidence_json=_evidence(
                liquidity_usd=6000.0, volume_5m=2000.0, txns_5m=20
            ),
        ),
        now=NOW,
    )
    assert fast.frozen_tracking_lane == "TRACK_FAST"
    assert fast.frozen_discovery_action == "TRACK_FAST"


def test_missing_truthful_lane_never_defaults(conn: sqlite3.Connection) -> None:
    # Insufficient market fields → classifier cannot produce TRACK_* .
    weak = _base_item(1, evidence_json=json.dumps({"candidate": {"liquidity_usd": 10}}))
    with pytest.raises(PreAdmissionAttemptError, match="FROZEN_TRACKING_LANE_UNAVAILABLE"):
        attach_frozen_tracking_lane(weak, now=NOW)
    with pytest.raises(CadenceAuthorityError, match="TRACKING_LANE_INVALID"):
        claim_tracking_authority_for_slot_insert(
            conn, token_row_id=1, pair_row_id=1, tracking_lane="TRACKING"
        )


def test_claim_uses_explicit_frozen_lane_no_default(conn: sqlite3.Connection) -> None:
    _insert_token_pair(conn, token_id=1, pair_id=101, token_status=None)
    conn.commit()
    queue_id = claim_tracking_authority_for_slot_insert(
        conn, token_row_id=1, pair_row_id=101, tracking_lane="TRACK_FAST", now=NOW
    )
    row = conn.execute(
        "SELECT tracking_lane, pair_id FROM printer_tracking_queue WHERE id=?",
        (queue_id,),
    ).fetchone()
    assert row[0] == "TRACK_FAST"
    assert int(row[1]) == 101
    status = conn.execute("SELECT token_status FROM printer_tokens WHERE id=1").fetchone()[0]
    assert status == "TRACK_FAST"


def test_token_status_conflict_zero_mutation(conn: sqlite3.Connection) -> None:
    _seed_campaign(conn)
    _insert_token_pair(conn, token_id=1, pair_id=101, token_status="TRACK_FAST")
    _insert_token_pair(conn, token_id=2, pair_id=102, token_status="TRACK_NORMAL")
    q1 = claim_tracking_authority_for_slot_insert(
        conn, token_row_id=1, pair_row_id=101, tracking_lane="TRACK_NORMAL", now=NOW
    )
    # Force conflict: queue NORMAL but leave token_status FAST by rewriting after claim.
    conn.execute("UPDATE printer_tokens SET token_status='TRACK_FAST' WHERE id=1")
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
                "tracking_queue_id": claim_tracking_authority_for_slot_insert(
                    conn, token_row_id=2, pair_row_id=102, tracking_lane="TRACK_NORMAL", now=NOW
                ),
            },
        ),
        now=NOW.isoformat(),
    )
    conn.commit()
    before = conn.execute("SELECT token_status FROM printer_tokens WHERE id=1").fetchone()[0]
    with pytest.raises(CadenceAuthorityError, match="TOKEN_STATUS_CADENCE_CONFLICT"):
        require_campaign_slot_tracking_authority(
            conn,
            campaign_id="campaign-1",
            run_id="campaign-run-1",
            cycle_id="cycle-1",
            token_slot_id="cycle-1-1",
            now=NOW,
        )
    after = conn.execute("SELECT token_status FROM printer_tokens WHERE id=1").fetchone()[0]
    assert before == after == "TRACK_FAST"


def test_existing_slot_null_queue_blocks_handoff_validation(conn: sqlite3.Connection) -> None:
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
    with pytest.raises(CadenceAuthorityError, match="TRACKING_QUEUE_BINDING_MISSING"):
        validate_existing_slot_tracking_queue_for_handoff(
            conn,
            token_slot_id="cycle-1-1",
            cycle_id="cycle-1",
            token_row_id=1,
            pair_row_id=101,
        )
    with pytest.raises(CampaignOwnershipError, match="WINDOW_15M_ACTIVE requires"):
        transition_state(
            conn,
            record_kind="token_slot",
            identity="cycle-1-1",
            expected_state="SELECTED",
            new_state="WINDOW_15M_ACTIVE",
        )


def _bound_cycle(conn, *, lane: str = "TRACK_NORMAL", token_status=None, pair_id_null: bool = False):
    _seed_campaign(conn)
    _insert_token_pair(conn, token_id=1, pair_id=101, token_status=token_status or lane)
    _insert_token_pair(conn, token_id=2, pair_id=102, token_status=lane)
    q1 = claim_tracking_authority_for_slot_insert(
        conn, token_row_id=1, pair_row_id=101, tracking_lane=lane, now=NOW
    )
    q2 = claim_tracking_authority_for_slot_insert(
        conn, token_row_id=2, pair_row_id=102, tracking_lane=lane, now=NOW
    )
    if pair_id_null:
        conn.execute("UPDATE printer_tracking_queue SET pair_id=NULL WHERE id=?", (q1,))
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
    return q1, q2


def test_null_pair_blocked(conn: sqlite3.Connection) -> None:
    q1, _ = _bound_cycle(conn)
    conn.execute("UPDATE printer_tracking_queue SET pair_id=NULL WHERE id=?", (q1,))
    conn.commit()
    with pytest.raises(CadenceAuthorityError, match="TRACKING_QUEUE_PAIR_NULL"):
        require_campaign_slot_tracking_authority(
            conn,
            campaign_id="campaign-1",
            run_id="campaign-run-1",
            cycle_id="cycle-1",
            token_slot_id="cycle-1-1",
        )


def test_stale_terminal_queue_blocked(conn: sqlite3.Connection) -> None:
    q1, _ = _bound_cycle(conn)
    set_queue_status(conn, queue_id=q1, queue_status=QueueStatus.ARCHIVED)
    with pytest.raises(CadenceAuthorityError, match="TRACKING_QUEUE_LIFECYCLE_INELIGIBLE"):
        require_campaign_slot_tracking_authority(
            conn,
            campaign_id="campaign-1",
            run_id="campaign-run-1",
            cycle_id="cycle-1",
            token_slot_id="cycle-1-1",
            project_missing_token_status=False,
        )


def test_selected_to_active_requires_authority(conn: sqlite3.Connection) -> None:
    _bound_cycle(conn)
    # valid path succeeds
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


def test_materialization_failure_archives_claims(conn: sqlite3.Connection) -> None:
    q1, q2 = _bound_cycle(conn)
    archived = terminalize_unstarted_cycle_tracking_claims(conn, cycle_id="cycle-1", now=NOW)
    assert set(archived) == {q1, q2}
    for qid in (q1, q2):
        status = conn.execute(
            "SELECT queue_status FROM printer_tracking_queue WHERE id=?", (qid,)
        ).fetchone()[0]
        assert status == "ARCHIVED"
    assert conn.execute("SELECT token_status FROM printer_tokens WHERE id=1").fetchone()[0] is None


def test_forensic_gaps_normal_pass_fast_block() -> None:
    max_gap = 134.774
    times = [
        WIN_START + timedelta(seconds=offset)
        for offset in (0, 120, 240, 360, 480, 600, 720, 900 - max_gap, 900)
    ]
    snaps = [{"captured_at": ts.isoformat()} for ts in times]
    normal = evaluate_cadence_policy(
        snaps, WIN_START.isoformat(), WIN_END.isoformat(),
        get_policy("WINDOW_15M", "TRACK_NORMAL"),
    )
    fast = evaluate_cadence_policy(
        snaps, WIN_START.isoformat(), WIN_END.isoformat(),
        get_policy("WINDOW_15M", "TRACK_FAST"),
    )
    assert normal.cadence_policy_status == CADENCE_POLICY_PASS
    assert fast.cadence_policy_status == CADENCE_POLICY_BLOCKED
    assert get_policy("WINDOW_15M", None) is None


def test_hard_lock_assertions_are_real() -> None:
    from printer_v1.operator_cli import cadence_authority as authority
    from printer_v1.operator_cli import lane_q_15m_window_integrity_guard as lane_q

    auth_source = Path(authority.__file__).read_text(encoding="utf-8")
    lane_source = Path(lane_q.__file__).read_text(encoding="utf-8")
    for banned in ("private_key", "embedding", "httpx", "aiohttp"):
        assert banned not in auth_source
    assert "no_retrieval_activation" in lane_source
    assert "no_paper_decisions" in lane_source
    assert "no_buy_sell_hold" in lane_source
    assert "no_positions" in lane_source
    assert "no_pnl" in lane_source
    assert "or True" not in auth_source

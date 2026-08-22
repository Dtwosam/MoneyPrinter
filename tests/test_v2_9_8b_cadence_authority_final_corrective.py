"""V2-9.8B Design Lane 1 — final cadence-authority corrective proofs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from printer_v1.db import apply_migrations
from printer_v1.lifecycle.contracts import QueueStatus
from printer_v1.lifecycle.tracking_queue import (
    assess_possible_tracking_claim_by_identity,
    assess_tracking_handoff_by_identity,
    set_queue_status,
)
from printer_v1.operator_cli.cadence_authority import (
    CADENCE_AUTHORITY_RESOLVED,
    CadenceAuthorityError,
    claim_tracking_authority_for_slot_insert,
    lookup_discovery_candidate_tracking_lane,
    require_campaign_slot_tracking_authority,
    resolve_campaign_slot_cadence_authority,
    resolve_cycle1_handoff_tracking_lane,
)
from printer_v1.operator_cli.campaign_ownership import create_cycle_with_two_slots
from printer_v1.operator_cli.pre_admission_discovery_attempt import (
    FROZEN_LANE_DECISION_OWNER,
    PreAdmissionAttemptItem,
    attach_frozen_tracking_lane,
)
from printer_v1.snapshots.cadence_policy import get_policy


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
WIN_START = NOW
WIN_END = NOW + timedelta(seconds=900)


def _evidence(
    *,
    liquidity_usd: float,
    volume_5m: float = 0.0,
    txns_5m: int = 0,
    volume_1h: float = 200.0,
    txns_1h: int = 5,
) -> str:
    return json.dumps(
        {
            "candidate": {
                "liquidity_usd": liquidity_usd,
                "price_usd": 0.01,
                "volume_5m": volume_5m,
                "txns_5m": txns_5m,
                "volume_1h": volume_1h,
                "txns_1h": txns_1h,
                "volume_24h": 200.0,
                "txns_24h": 10,
                "provenance": "PUMPSWAP_GRADUATED",
                "source_channel": "PUMPSWAP_GRADUATED",
            }
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _base_item(slot: int, *, evidence_json: str) -> PreAdmissionAttemptItem:
    digest = hashlib.sha256(evidence_json.encode()).hexdigest()
    return PreAdmissionAttemptItem(
        attempt_id="attempt-1",
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
    path = tmp_path / "final_corrective.sqlite3"
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


def _insert_token_pair(connection, *, token_id: int, pair_id: int, token_status=None) -> None:
    connection.execute(
        "INSERT INTO printer_tokens(id,token_mint,chain,token_status) VALUES (?,?, 'solana',?)",
        (token_id, f"mint-{token_id}", token_status),
    )
    connection.execute(
        "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) VALUES (?,?,?,?)",
        (pair_id, token_id, f"pair-{pair_id}", f"mint-{token_id}"),
    )


def _insert_discovery_candidate(
    connection,
    *,
    token_id: int,
    pair_id: int,
    tracking_lane: str,
) -> None:
    connection.execute(
        """
        INSERT INTO printer_discovery_candidates(
            source_response_id, token_id, pair_id, source_name,
            discovery_label, discovery_action, source_status, data_quality_label,
            raw_candidate_payload_json, normalized_candidate_payload_json,
            lifecycle_state, tracking_lane, priority_reason
        ) VALUES (
            NULL, ?, ?, 'dexscreener',
            ?, ?, 'COMPLETE', 'CLEAN_DATA',
            '{}', '{}',
            ?, ?, 'test'
        )
        """,
        (
            token_id,
            pair_id,
            f"{tracking_lane}_CANDIDATE",
            tracking_lane,
            tracking_lane,
            tracking_lane,
        ),
    )


def _bound_cycle_with_window(
    conn: sqlite3.Connection,
    *,
    lane: str,
    queue_status: str = "ACTIVE",
) -> tuple[int, int]:
    """Return (memory_window_row_id, tracking_queue_id) for slot 1."""
    _seed_campaign(conn)
    _insert_token_pair(conn, token_id=1, pair_id=101, token_status=lane)
    _insert_token_pair(conn, token_id=2, pair_id=102, token_status=lane)
    q1 = claim_tracking_authority_for_slot_insert(
        conn, token_row_id=1, pair_row_id=101, tracking_lane=lane, now=NOW
    )
    q2 = claim_tracking_authority_for_slot_insert(
        conn, token_row_id=2, pair_row_id=102, tracking_lane=lane, now=NOW
    )
    if queue_status != "ACTIVE":
        set_queue_status(conn, queue_id=q1, queue_status=QueueStatus(queue_status))
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
    # Snapshots for cadence evaluate (even coverage).
    snap_ids = []
    for offset in (0, 120, 240, 360, 480, 600, 720, 840, 900):
        cur = conn.execute(
            """
            INSERT INTO printer_token_snapshots(
                token_id, pair_id, captured_at, tracking_lane, snapshot_mode,
                price_usd, liquidity_usd, source_status, data_quality_label, created_at
            ) VALUES (?,?,?,?,'SCHEDULED', 0.01, 1500, 'COMPLETE', 'CLEAN_DATA', ?)
            """,
            (
                1,
                101,
                (WIN_START + timedelta(seconds=offset)).isoformat(),
                lane,
                NOW.isoformat(),
            ),
        )
        snap_ids.append(int(cur.lastrowid))
    win = conn.execute(
        """
        INSERT INTO printer_memory_windows(
            token_id, pair_id, window_kind, opened_at, closed_at,
            memory_status, data_quality_label, do_not_train,
            window_status, memory_quality_label,
            supporting_context_json, created_by_phase, created_at, updated_at,
            window_start_at, window_end_at, snapshot_start_id, snapshot_end_id
        ) VALUES (
            1, 101, 'WINDOW_15M', ?, ?, 'PARTIAL_MEMORY', 'CLEAN_DATA', 0,
            'WINDOW_CLOSED', 'PARTIAL_MEMORY', ?, 'test', ?, ?, ?, ?, ?, ?
        )
        """,
        (
            WIN_START.isoformat(),
            WIN_END.isoformat(),
            json.dumps({"tracking_lane": lane}),
            NOW.isoformat(),
            NOW.isoformat(),
            WIN_START.isoformat(),
            WIN_END.isoformat(),
            snap_ids[0],
            snap_ids[-1],
        ),
    )
    memory_id = int(win.lastrowid)
    conn.execute(
        """
        INSERT INTO printer_memory_factory_campaign_windows(
            window_id, campaign_id, run_id, cycle_id, token_slot_id,
            token_row_id, pair_row_id, window_kind, window_state,
            root_15m_lifecycle_identity, memory_window_row_id,
            checkpoint_cutoff, support_only, created_at, updated_at
        ) VALUES (
            'window-1', 'campaign-1', 'campaign-run-1', 'cycle-1', 'cycle-1-1',
            1, 101, 'WINDOW_15M', 'AUDITING',
            'lifecycle-1', ?, ?, 0, ?, ?
        )
        """,
        (memory_id, WIN_END.isoformat(), NOW.isoformat(), NOW.isoformat()),
    )
    conn.commit()
    return memory_id, q1


# --- 1/2/3 Cycle-1 truthful lane ---


def test_cycle1_truthful_track_normal_queue_and_opening_job_kind(conn: sqlite3.Connection) -> None:
    _insert_token_pair(conn, token_id=1, pair_id=101)
    _insert_discovery_candidate(conn, token_id=1, pair_id=101, tracking_lane="TRACK_NORMAL")
    conn.commit()
    lane = resolve_cycle1_handoff_tracking_lane(
        conn,
        token_id=1,
        pair_id=101,
        token_mint="mint-1",
        pair_address="pair-101",
        discovery_batch_id="batch-missing",
        now=NOW.isoformat(),
    )
    assert lane == "TRACK_NORMAL"
    queue_id = claim_tracking_authority_for_slot_insert(
        conn, token_row_id=1, pair_row_id=101, tracking_lane=lane, now=NOW
    )
    row = conn.execute(
        "SELECT tracking_lane FROM printer_tracking_queue WHERE id=?", (queue_id,)
    ).fetchone()
    assert row[0] == "TRACK_NORMAL"
    from printer_v1.scheduler.contracts import JobKind
    from printer_v1.lifecycle.contracts import TokenLifecycleState

    assert TokenLifecycleState(lane) is TokenLifecycleState.TRACK_NORMAL
    assert JobKind.TRACK_NORMAL_FIRST_15M.value == "TRACK_NORMAL_FIRST_15M"


def test_cycle1_truthful_track_fast_queue_and_opening_job_kind(conn: sqlite3.Connection) -> None:
    _insert_token_pair(conn, token_id=1, pair_id=101)
    _insert_discovery_candidate(conn, token_id=1, pair_id=101, tracking_lane="TRACK_FAST")
    conn.commit()
    lane = resolve_cycle1_handoff_tracking_lane(
        conn,
        token_id=1,
        pair_id=101,
        token_mint="mint-1",
        pair_address="pair-101",
        now=NOW.isoformat(),
    )
    assert lane == "TRACK_FAST"
    queue_id = claim_tracking_authority_for_slot_insert(
        conn, token_row_id=1, pair_row_id=101, tracking_lane=lane, now=NOW
    )
    assert (
        conn.execute(
            "SELECT tracking_lane FROM printer_tracking_queue WHERE id=?", (queue_id,)
        ).fetchone()[0]
        == "TRACK_FAST"
    )
    from printer_v1.scheduler.contracts import JobKind

    assert JobKind.TRACK_FAST_FIRST_15M.value == "TRACK_FAST_FIRST_15M"


def test_cycle1_operational_path_has_no_hardcoded_normal() -> None:
    from printer_v1.discovery import combined_executor as executor_mod
    from printer_v1.operator_cli import cadence_authority as authority

    handoff_src = Path(executor_mod.__file__).read_text(encoding="utf-8")
    # Narrow: the Cycle-1 handoff body must not hardcode TRACK_NORMAL claim/job.
    start = handoff_src.index("def _handoff_one_slot(")
    end = handoff_src.index("\n    def ", start + 1)
    body = handoff_src[start:end]
    assert "tracking_lane=TokenLifecycleState.TRACK_NORMAL" not in body
    assert "JobKind.TRACK_NORMAL_FIRST_15M," not in body.replace(" ", "")
    assert "resolve_cycle1_handoff_tracking_lane" in body
    auth_src = Path(authority.__file__).read_text(encoding="utf-8")
    assert "choose_tracking_lane" in auth_src
    assert "classify_discovery_candidate" in auth_src


# --- 4/5/6 later-cycle pre-freeze consistency ---


def test_later_cycle_pre_freeze_fast_remains_fast_through_freeze() -> None:
    fast = attach_frozen_tracking_lane(
        _base_item(
            1,
            evidence_json=_evidence(liquidity_usd=6000.0, volume_5m=2000.0, txns_5m=20),
        ),
        now=NOW,
    )
    assert fast.frozen_tracking_lane == "TRACK_FAST"
    assert fast.frozen_discovery_action == "TRACK_FAST"


def test_later_cycle_pre_freeze_normal_remains_normal() -> None:
    normal = attach_frozen_tracking_lane(
        _base_item(1, evidence_json=_evidence(liquidity_usd=1500.0)),
        now=NOW,
    )
    assert normal.frozen_tracking_lane == "TRACK_NORMAL"
    assert normal.frozen_discovery_action == "TRACK_NORMAL"


def test_normal_only_probe_cannot_deny_valid_fast_candidate(conn: sqlite3.Connection) -> None:
    _insert_token_pair(conn, token_id=1, pair_id=101, token_status="TRACK_FAST")
    # Active NORMAL conflict only — FAST lane remains fresh/claimable.
    conn.execute(
        """
        INSERT INTO printer_tracking_queue(
            token_id, pair_id, tracking_lane, tracking_action, priority_reason,
            next_check_at, queue_status, source_status, data_quality_label
        ) VALUES (1, 101, 'TRACK_NORMAL', 'PROMOTE_TO_TRACK_NORMAL', 'probe',
                  ?, 'ACTIVE', 'COMPLETE', 'CLEAN_DATA')
        """,
        (NOW.isoformat(),),
    )
    conn.commit()
    normal_only = assess_tracking_handoff_by_identity(
        conn,
        token_mint="mint-1",
        pair_address="pair-101",
        tracking_lane="TRACK_NORMAL",
        assessed_at=NOW,
    )
    assert not normal_only.eligible
    possible = assess_possible_tracking_claim_by_identity(
        conn,
        token_mint="mint-1",
        pair_address="pair-101",
        assessed_at=NOW,
    )
    assert possible.eligible
    # Explicit FAST assessment still eligible.
    fast = assess_possible_tracking_claim_by_identity(
        conn,
        token_mint="mint-1",
        pair_address="pair-101",
        tracking_lane="TRACK_FAST",
        assessed_at=NOW,
    )
    assert fast.eligible


# --- 7/8/9/10 historical cadence vs opening eligibility ---


def test_lane_q_resolves_track_normal_when_queue_archived(conn: sqlite3.Connection) -> None:
    memory_id, q1 = _bound_cycle_with_window(conn, lane="TRACK_NORMAL", queue_status="ARCHIVED")
    resolution = resolve_campaign_slot_cadence_authority(
        conn, memory_window_row_id=memory_id
    )
    assert resolution.status == CADENCE_AUTHORITY_RESOLVED
    assert resolution.tracking_lane == "TRACK_NORMAL"
    assert resolution.tracking_queue_id == q1


def test_lane_q_resolves_track_fast_when_queue_cooldown(conn: sqlite3.Connection) -> None:
    memory_id, q1 = _bound_cycle_with_window(conn, lane="TRACK_FAST", queue_status="COOLDOWN")
    resolution = resolve_campaign_slot_cadence_authority(
        conn, memory_window_row_id=memory_id
    )
    assert resolution.status == CADENCE_AUTHORITY_RESOLVED
    assert resolution.tracking_lane == "TRACK_FAST"
    assert resolution.tracking_queue_id == q1


def test_opening_new_window_rejects_terminal_queue(conn: sqlite3.Connection) -> None:
    _bound_cycle_with_window(conn, lane="TRACK_NORMAL", queue_status="ARCHIVED")
    with pytest.raises(CadenceAuthorityError, match="TRACKING_QUEUE_LIFECYCLE_INELIGIBLE"):
        require_campaign_slot_tracking_authority(
            conn,
            campaign_id="campaign-1",
            run_id="campaign-run-1",
            cycle_id="cycle-1",
            token_slot_id="cycle-1-1",
            project_missing_token_status=False,
        )


def test_historical_cadence_and_opening_eligibility_are_separate(conn: sqlite3.Connection) -> None:
    memory_id, _ = _bound_cycle_with_window(conn, lane="TRACK_FAST", queue_status="SKIPPED")
    # Historical Lane Q still resolves.
    resolution = resolve_campaign_slot_cadence_authority(
        conn, memory_window_row_id=memory_id
    )
    assert resolution.status == CADENCE_AUTHORITY_RESOLVED
    assert resolution.tracking_lane == "TRACK_FAST"
    # Opening eligibility still rejects.
    with pytest.raises(CadenceAuthorityError, match="TRACKING_QUEUE_LIFECYCLE_INELIGIBLE"):
        require_campaign_slot_tracking_authority(
            conn,
            campaign_id="campaign-1",
            run_id="campaign-run-1",
            cycle_id="cycle-1",
            token_slot_id="cycle-1-1",
            project_missing_token_status=False,
        )


# --- 11 frozen provenance immutability ---


def test_frozen_provenance_immutable_after_pair_ready_insert(conn: sqlite3.Connection) -> None:
    # Migration 055: entire pre-admission attempt item row is immutable on UPDATE.
    # Migration 060: INSERT requires complete frozen provenance.
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
    evidence = _evidence(liquidity_usd=1500.0)
    digest = hashlib.sha256(evidence.encode()).hexdigest()
    job = conn.execute(
        "INSERT INTO printer_scheduler_jobs("
        "job_name,job_kind,target_table,priority,status,scheduled_for) "
        "VALUES ('pre-admission:attempt-1','PRE_ADMISSION_DISCOVERY_SELECTION',"
        "'printer_pre_admission_discovery_attempts',13,'SUCCEEDED',?)",
        (NOW.isoformat(),),
    )
    job_id = int(job.lastrowid)
    conn.execute(
        """
        INSERT INTO printer_pre_admission_discovery_attempts(
            attempt_id, campaign_id, campaign_run_id, configuration_id,
            authoritative_factory_run_id, proposed_cycle_ordinal, proposed_cycle_id,
            scheduler_job_id, cycle_cutoff, evaluated_at, selection_seed_identity,
            attempt_state, first_terminal_cause, terminal_at, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "attempt-1",
            "campaign-1",
            "campaign-run-1",
            "configuration-1",
            "factory-1",
            2,
            "cycle-1-2",
            job_id,
            WIN_END.isoformat(),
            NOW.isoformat(),
            "seed-1",
            "PAIR_READY",
            "EXACT_PAIR_FROZEN",
            NOW.isoformat(),
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    frozen_fields = {
        "frozen_tracking_lane": "TRACK_NORMAL",
        "frozen_discovery_action": "TRACK_NORMAL",
        "frozen_discovery_label": "TRACK_NORMAL_CANDIDATE",
        "frozen_classification_reason": "clean_solana_candidate_with_basic_market_fields",
        "frozen_lane_evidence_hash": "a" * 64,
        "frozen_lane_decided_at": NOW.isoformat(),
        "frozen_lane_decision_owner": FROZEN_LANE_DECISION_OWNER,
    }
    conn.execute(
        """
        INSERT INTO printer_pre_admission_discovery_attempt_items(
            attempt_id, slot_ordinal, token_identity, token_row_id, mint_identity,
            pair_identity, pair_row_id, lifecycle_identity,
            canonical_market_identity, canonical_pool_identity,
            canonical_evidence_json, canonical_evidence_hash, evidence_version,
            observed_at, channel_labels_json, created_at,
            frozen_tracking_lane, frozen_discovery_action, frozen_discovery_label,
            frozen_classification_reason, frozen_lane_evidence_hash,
            frozen_lane_decided_at, frozen_lane_decision_owner
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "attempt-1",
            1,
            "solana-mainnet:mint-1",
            1,
            "mint-1",
            "pair-101",
            101,
            "PUMPSWAP_GRADUATED_CONFIRMED",
            "solana-mainnet:pumpswap:pair-101",
            "pair-101",
            evidence,
            digest,
            "v1",
            NOW.isoformat(),
            json.dumps(["PUMPSWAP_GRADUATED"]),
            NOW.isoformat(),
            frozen_fields["frozen_tracking_lane"],
            frozen_fields["frozen_discovery_action"],
            frozen_fields["frozen_discovery_label"],
            frozen_fields["frozen_classification_reason"],
            frozen_fields["frozen_lane_evidence_hash"],
            frozen_fields["frozen_lane_decided_at"],
            frozen_fields["frozen_lane_decision_owner"],
        ),
    )
    conn.commit()
    for column, evil in (
        ("frozen_tracking_lane", "TRACK_FAST"),
        ("frozen_discovery_action", "TRACK_FAST"),
        ("frozen_discovery_label", "TRACK_FAST_CANDIDATE"),
        ("frozen_classification_reason", "tampered"),
        ("frozen_lane_evidence_hash", "b" * 64),
        ("frozen_lane_decided_at", (NOW + timedelta(seconds=1)).isoformat()),
        ("frozen_lane_decision_owner", "tampered-owner"),
    ):
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute(
                f"UPDATE printer_pre_admission_discovery_attempt_items "
                f"SET {column}=? WHERE attempt_id='attempt-1' AND slot_ordinal=1",
                (evil,),
            )
        conn.rollback()


# --- 14 policy None + 15 hard locks ---


def test_get_policy_window_15m_none_remains_none() -> None:
    assert get_policy("WINDOW_15M", None) is None


def test_hard_lock_assertions_remain() -> None:
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


def test_lookup_discovery_lane_fail_closed_without_row(conn: sqlite3.Connection) -> None:
    _insert_token_pair(conn, token_id=1, pair_id=101)
    conn.commit()
    with pytest.raises(CadenceAuthorityError, match="DISCOVERY_TRACKING_LANE_MISSING"):
        lookup_discovery_candidate_tracking_lane(conn, token_id=1, pair_id=101)
    with pytest.raises(CadenceAuthorityError, match="DISCOVERY_TRACKING_LANE_MISSING"):
        resolve_cycle1_handoff_tracking_lane(
            conn,
            token_id=1,
            pair_id=101,
            token_mint="mint-1",
            pair_address="pair-101",
            discovery_batch_id="missing-batch",
            now=NOW.isoformat(),
        )

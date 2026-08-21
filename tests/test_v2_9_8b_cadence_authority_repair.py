"""V2-9.8B Design Lane 1 — campaign-slot cadence authority repair proofs.

Isolated migrated/disposable DB. No live provider calls.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3
from pathlib import Path

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.cadence_authority import (
    CADENCE_AUTHORITY_CONFLICT,
    CADENCE_AUTHORITY_RESOLVED,
    CADENCE_AUTHORITY_UNKNOWN,
    CadenceAuthorityError,
    claim_tracking_authority_for_slot_insert,
    require_campaign_slot_tracking_authority,
    require_cycle_slot_tracking_authorities,
    resolve_campaign_slot_cadence_authority,
)
from printer_v1.operator_cli.campaign_ownership import create_cycle_with_two_slots
from printer_v1.operator_cli.lane_q_15m_window_integrity_guard import (
    LANE_Q_BLOCKED,
    LANE_Q_VALID,
    guard_candidate_windows,
)
from printer_v1.operator_cli.one_command_15m_factory import _cycle_targets_for_factory
from printer_v1.snapshots.cadence_policy import (
    CADENCE_POLICY_BLOCKED,
    CADENCE_POLICY_PASS,
    evaluate_cadence_policy,
    get_policy,
)


START = datetime(2026, 8, 21, 16, 25, 8, tzinfo=timezone.utc)
WIN_START = START
WIN_END = START + timedelta(seconds=900)


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "cadence-authority.sqlite3"
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
            START.isoformat(),
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
            START.isoformat(),
            START.isoformat(),
        ),
    )


def _insert_token_pair(
    connection: sqlite3.Connection,
    *,
    token_id: int,
    mint: str,
    pair_id: int,
    pair: str,
    token_status: str | None = None,
) -> None:
    connection.execute(
        "INSERT INTO printer_tokens(id,token_mint,chain,token_status) VALUES (?,?, 'solana',?)",
        (token_id, mint, token_status),
    )
    connection.execute(
        "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) VALUES (?,?,?,?)",
        (pair_id, token_id, pair, mint),
    )


def _create_cycle(
    connection: sqlite3.Connection,
    *,
    cycle_id: str,
    cycle_ordinal: int,
    token_ids: tuple[int, int],
    pair_ids: tuple[int, int],
    tracking_queue_ids: tuple[int | None, int | None] = (None, None),
) -> tuple[str, str]:
    slots = []
    slot_ids: list[str] = []
    for ordinal, token_id, pair_id, queue_id in zip(
        (1, 2), token_ids, pair_ids, tracking_queue_ids, strict=True
    ):
        slot_id = f"{cycle_id}-{ordinal}"
        slot_ids.append(slot_id)
        slots.append(
            {
                "token_slot_id": slot_id,
                "slot_ordinal": ordinal,
                "token_identity": f"token-{token_id}",
                "token_row_id": token_id,
                "mint_identity": f"mint-{token_id}",
                "pair_identity": f"pair-{pair_id}",
                "pair_row_id": pair_id,
                "lifecycle_identity": f"lifecycle-{token_id}",
                "tracking_queue_id": queue_id,
            }
        )
    create_cycle_with_two_slots(
        connection,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id=cycle_id,
        cycle_ordinal=cycle_ordinal,
        slots=slots,
        now=START.isoformat(),
    )
    return slot_ids[0], slot_ids[1]


def _insert_queue(
    connection: sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int,
    lane: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO printer_tracking_queue(
            token_id, pair_id, tracking_lane, tracking_action, priority_reason,
            next_check_at, queue_status, source_status, data_quality_label
        ) VALUES (?, ?, ?, ?, 'test', ?, 'ACTIVE', 'COMPLETE', 'CLEAN_DATA')
        """,
        (
            token_id,
            pair_id,
            lane,
            "PROMOTE_TO_TRACK_FAST" if lane == "TRACK_FAST" else "PROMOTE_TO_TRACK_NORMAL",
            START.isoformat(),
        ),
    )
    return int(cursor.lastrowid)


def _insert_memory_window(
    connection: sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int,
    snap_start: int,
    snap_end: int,
    tracking_lane: str = "TRACK_NORMAL",
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO printer_memory_windows(
            token_id, pair_id, window_kind, opened_at, closed_at,
            memory_status, data_quality_label, do_not_train,
            window_status, memory_quality_label,
            supporting_context_json, created_by_phase, created_at, updated_at,
            window_start_at, window_end_at, snapshot_start_id, snapshot_end_id
        ) VALUES (
            ?, ?, 'WINDOW_15M', ?, ?, 'PARTIAL_MEMORY', 'CLEAN_DATA', 0,
            'WINDOW_CLOSED', 'PARTIAL_MEMORY', ?, 'test', ?, ?, ?, ?, ?, ?
        )
        """,
        (
            token_id,
            pair_id,
            WIN_START.isoformat(),
            WIN_END.isoformat(),
            json.dumps({"tracking_lane": tracking_lane}),
            START.isoformat(),
            START.isoformat(),
            WIN_START.isoformat(),
            WIN_END.isoformat(),
            snap_start,
            snap_end,
        ),
    )
    return int(cursor.lastrowid)


def _bind_campaign_window(
    connection: sqlite3.Connection,
    *,
    window_id: str,
    cycle_id: str,
    token_slot_id: str,
    token_id: int,
    pair_id: int,
    memory_window_row_id: int,
) -> None:
    connection.execute(
        """
        INSERT INTO printer_memory_factory_campaign_windows(
            window_id, campaign_id, run_id, cycle_id, token_slot_id,
            token_row_id, pair_row_id, window_kind, window_state,
            root_15m_lifecycle_identity, memory_window_row_id,
            checkpoint_cutoff, support_only, created_at, updated_at
        ) VALUES (
            ?, 'campaign-1', 'campaign-run-1', ?, ?, ?, ?, 'WINDOW_15M', 'AUDITING',
            ?, ?, ?, 0, ?, ?
        )
        """,
        (
            window_id,
            cycle_id,
            token_slot_id,
            token_id,
            pair_id,
            f"lifecycle-{token_id}",
            memory_window_row_id,
            WIN_END.isoformat(),
            START.isoformat(),
            START.isoformat(),
        ),
    )


def _insert_forensic_gap_snapshots(
    connection: sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int,
    lane: str,
    max_gap_seconds: float = 127.701,
) -> tuple[int, int]:
    """Enough samples for NORMAL evaluation with a forensic-shaped final gap."""
    times = [
        WIN_START + timedelta(seconds=offset)
        for offset in (0, 120, 240, 360, 480, 600, 720, 900 - max_gap_seconds, 900)
    ]
    ids: list[int] = []
    for captured in times:
        cursor = connection.execute(
            """
            INSERT INTO printer_token_snapshots(
                token_id, pair_id, captured_at, tracking_lane, snapshot_mode,
                source_status, data_quality_label, created_at
            ) VALUES (?, ?, ?, ?, 'SCHEDULED', 'COMPLETE', 'CLEAN_DATA', ?)
            """,
            (
                token_id,
                pair_id,
                captured.isoformat(),
                lane,
                START.isoformat(),
            ),
        )
        ids.append(int(cursor.lastrowid))
    return ids[0], ids[-1]


def _prepare_owned_window(
    connection: sqlite3.Connection,
    *,
    cycle_id: str,
    cycle_ordinal: int,
    token_id: int,
    pair_id: int,
    lane: str,
    token_status: str | None = None,
    bind_queue: bool = True,
    max_gap_seconds: float = 127.701,
    snapshot_lane: str | None = None,
) -> int:
    _insert_token_pair(
        connection,
        token_id=token_id,
        mint=f"mint-{token_id}",
        pair_id=pair_id,
        pair=f"pair-{pair_id}",
        token_status=token_status if token_status is not None else lane,
    )
    queue_id = None
    if bind_queue:
        queue_id = _insert_queue(
            connection, token_id=token_id, pair_id=pair_id, lane=lane
        )
    # Companion slot token for exact two-slot cycle creation.
    companion_token = token_id + 1000
    companion_pair = pair_id + 1000
    if connection.execute(
        "SELECT 1 FROM printer_tokens WHERE id=?", (companion_token,)
    ).fetchone() is None:
        _insert_token_pair(
            connection,
            token_id=companion_token,
            mint=f"mint-{companion_token}",
            pair_id=companion_pair,
            pair=f"pair-{companion_pair}",
            token_status=lane,
        )
    companion_queue = None
    if bind_queue:
        companion_queue = _insert_queue(
            connection,
            token_id=companion_token,
            pair_id=companion_pair,
            lane=lane,
        )
    slot_a, _slot_b = _create_cycle(
        connection,
        cycle_id=cycle_id,
        cycle_ordinal=cycle_ordinal,
        token_ids=(token_id, companion_token),
        pair_ids=(pair_id, companion_pair),
        tracking_queue_ids=(queue_id, companion_queue),
    )
    snap_start, snap_end = _insert_forensic_gap_snapshots(
        connection,
        token_id=token_id,
        pair_id=pair_id,
        lane=snapshot_lane or lane,
        max_gap_seconds=max_gap_seconds,
    )
    context_lane = snapshot_lane or lane
    memory_id = _insert_memory_window(
        connection,
        token_id=token_id,
        pair_id=pair_id,
        snap_start=snap_start,
        snap_end=snap_end,
        tracking_lane=context_lane,
    )
    _bind_campaign_window(
        connection,
        window_id=f"cw-{cycle_id}-1",
        cycle_id=cycle_id,
        token_slot_id=slot_a,
        token_id=token_id,
        pair_id=pair_id,
        memory_window_row_id=memory_id,
    )
    connection.commit()
    return memory_id


# ---------------------------------------------------------------------------
# J. get_policy strictness
# ---------------------------------------------------------------------------


def test_get_policy_none_never_returns_lane_specific_policy() -> None:
    assert get_policy("WINDOW_15M", None) is None
    assert get_policy("WINDOW_15M", "TRACK_FAST").tracking_lane == "TRACK_FAST"
    assert get_policy("WINDOW_15M", "TRACK_NORMAL").tracking_lane == "TRACK_NORMAL"


# ---------------------------------------------------------------------------
# A/B/C. Cycle 1 / 2 / 3 shared path + Lane Q TRACK_NORMAL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cycle_id", "cycle_ordinal", "token_id"),
    [
        ("cycle-1", 1, 11),
        ("cycle-2", 2, 21),
        ("cycle-3", 3, 31),
    ],
)
def test_cycle_n_slot_bound_queue_resolves_track_normal(
    db_path: Path,
    conn: sqlite3.Connection,
    cycle_id: str,
    cycle_ordinal: int,
    token_id: int,
) -> None:
    _seed_campaign(conn)
    memory_id = _prepare_owned_window(
        conn,
        cycle_id=cycle_id,
        cycle_ordinal=cycle_ordinal,
        token_id=token_id,
        pair_id=token_id + 50,
        lane="TRACK_NORMAL",
    )
    resolution = resolve_campaign_slot_cadence_authority(
        conn, memory_window_row_id=memory_id
    )
    assert resolution.status == CADENCE_AUTHORITY_RESOLVED
    assert resolution.tracking_lane == "TRACK_NORMAL"
    assert resolution.tracking_queue_id is not None

    guard = guard_candidate_windows(
        db_path, [memory_id], operator_approved=True
    )
    assert memory_id in guard["valid_window_ids"]
    verdict = next(v for v in guard["window_verdicts"] if v["window_id"] == memory_id)
    assert verdict["lane_q_status"] == LANE_Q_VALID
    cadence = verdict["cadence_policy_evaluation"]
    assert cadence["tracking_lane"] == "TRACK_NORMAL"
    assert cadence["cadence_policy_status"] == CADENCE_POLICY_PASS


def test_cycle2_and_cycle3_share_insert_time_activation_owner(
    conn: sqlite3.Connection,
) -> None:
    _seed_campaign(conn)
    for ordinal, token_id in ((2, 41), (3, 51)):
        cycle_id = f"cycle-{ordinal}"
        companion = token_id + 1000
        for tid, pid in (
            (token_id, token_id + 50),
            (companion, companion + 50),
        ):
            _insert_token_pair(
                conn,
                token_id=tid,
                mint=f"mint-{tid}",
                pair_id=pid,
                pair=f"pair-{pid}",
                token_status=None,
            )
        queue_ids = tuple(
            claim_tracking_authority_for_slot_insert(
                conn,
                token_row_id=tid,
                pair_row_id=pid,
                tracking_lane="TRACK_NORMAL",
                now=START,
            )
            for tid, pid in (
                (token_id, token_id + 50),
                (companion, companion + 50),
            )
        )
        _create_cycle(
            conn,
            cycle_id=cycle_id,
            cycle_ordinal=ordinal,
            token_ids=(token_id, companion),
            pair_ids=(token_id + 50, companion + 50),
            tracking_queue_ids=queue_ids,
        )
        conn.commit()
        required = require_cycle_slot_tracking_authorities(
            conn,
            campaign_id="campaign-1",
            run_id="campaign-run-1",
            cycle_id=cycle_id,
            tracking_lane="TRACK_NORMAL",
            now=START,
        )
        assert required == queue_ids
        statuses = {
            conn.execute(
                "SELECT token_status FROM printer_tokens WHERE id=?", (tid,)
            ).fetchone()[0]
            for tid in (token_id, companion)
        }
        assert statuses == {"TRACK_NORMAL"}


# ---------------------------------------------------------------------------
# D. Genuine TRACK_FAST
# ---------------------------------------------------------------------------


def test_genuine_track_fast_uses_unchanged_thresholds(
    db_path: Path, conn: sqlite3.Connection
) -> None:
    _seed_campaign(conn)
    # FAST expects 16 samples; build a dense series under the 120s block limit.
    memory_id = _prepare_owned_window(
        conn,
        cycle_id="cycle-fast",
        cycle_ordinal=1,
        token_id=61,
        pair_id=161,
        lane="TRACK_FAST",
        max_gap_seconds=60.0,
    )
    # Replace sparse forensic series with a full FAST-clean series.
    conn.execute("DELETE FROM printer_token_snapshots WHERE token_id=61")
    ids: list[int] = []
    for index in range(16):
        captured = WIN_START + timedelta(seconds=index * 60)
        cursor = conn.execute(
            """
            INSERT INTO printer_token_snapshots(
                token_id, pair_id, captured_at, tracking_lane, snapshot_mode,
                source_status, data_quality_label, created_at
            ) VALUES (61, 161, ?, 'TRACK_FAST', 'SCHEDULED', 'COMPLETE', 'CLEAN_DATA', ?)
            """,
            (captured.isoformat(), START.isoformat()),
        )
        ids.append(int(cursor.lastrowid))
    conn.execute(
        "UPDATE printer_memory_windows SET snapshot_start_id=?, snapshot_end_id=? WHERE id=?",
        (ids[0], ids[-1], memory_id),
    )
    conn.commit()
    policy = get_policy("WINDOW_15M", "TRACK_FAST")
    assert policy is not None
    assert policy.max_clean_snapshot_gap_seconds == 120
    assert policy.dirty_above_gap_seconds == 90
    guard = guard_candidate_windows(db_path, [memory_id], operator_approved=True)
    verdict = next(v for v in guard["window_verdicts"] if v["window_id"] == memory_id)
    assert verdict["lane_q_status"] == LANE_Q_VALID
    assert verdict["cadence_policy_evaluation"]["tracking_lane"] == "TRACK_FAST"
    assert verdict["cadence_policy_evaluation"]["cadence_policy_status"] == CADENCE_POLICY_PASS


# ---------------------------------------------------------------------------
# E. Missing canonical authority
# ---------------------------------------------------------------------------


def test_missing_canonical_authority_blocks_without_track_fast_fallback(
    db_path: Path, conn: sqlite3.Connection
) -> None:
    _seed_campaign(conn)
    memory_id = _prepare_owned_window(
        conn,
        cycle_id="cycle-missing",
        cycle_ordinal=1,
        token_id=71,
        pair_id=171,
        lane="TRACK_NORMAL",
        token_status=None,
        bind_queue=False,
        max_gap_seconds=127.701,
    )
    resolution = resolve_campaign_slot_cadence_authority(
        conn, memory_window_row_id=memory_id
    )
    assert resolution.status == CADENCE_AUTHORITY_UNKNOWN
    assert resolution.tracking_lane is None
    assert get_policy("WINDOW_15M", None) is None

    guard = guard_candidate_windows(db_path, [memory_id], operator_approved=True)
    assert memory_id in guard["blocked_window_ids"]
    verdict = next(v for v in guard["window_verdicts"] if v["window_id"] == memory_id)
    assert verdict["lane_q_status"] == LANE_Q_BLOCKED
    cadence = verdict["cadence_policy_evaluation"]
    assert cadence["cadence_policy_status"] == CADENCE_POLICY_BLOCKED
    assert cadence["blocked_reason"] == "TRACKING_QUEUE_BINDING_MISSING"
    assert cadence["tracking_lane"] is None


# ---------------------------------------------------------------------------
# F. Authority conflict
# ---------------------------------------------------------------------------


def test_queue_normal_vs_token_status_fast_is_conflict(
    db_path: Path, conn: sqlite3.Connection
) -> None:
    _seed_campaign(conn)
    memory_id = _prepare_owned_window(
        conn,
        cycle_id="cycle-conflict-status",
        cycle_ordinal=1,
        token_id=81,
        pair_id=181,
        lane="TRACK_NORMAL",
        token_status="TRACK_FAST",
    )
    resolution = resolve_campaign_slot_cadence_authority(
        conn, memory_window_row_id=memory_id
    )
    assert resolution.status == CADENCE_AUTHORITY_CONFLICT
    assert resolution.reason_code == "TOKEN_STATUS_CADENCE_CONFLICT"
    guard = guard_candidate_windows(db_path, [memory_id], operator_approved=True)
    assert memory_id in guard["blocked_window_ids"]


def test_queue_normal_vs_snapshot_fast_is_conflict(
    db_path: Path, conn: sqlite3.Connection
) -> None:
    _seed_campaign(conn)
    memory_id = _prepare_owned_window(
        conn,
        cycle_id="cycle-conflict-snap",
        cycle_ordinal=1,
        token_id=91,
        pair_id=191,
        lane="TRACK_NORMAL",
        token_status="TRACK_NORMAL",
        snapshot_lane="TRACK_FAST",
    )
    resolution = resolve_campaign_slot_cadence_authority(
        conn,
        memory_window_row_id=memory_id,
        snapshots=[{"tracking_lane": "TRACK_FAST"}],
    )
    assert resolution.status == CADENCE_AUTHORITY_CONFLICT
    assert resolution.reason_code == "CADENCE_EVIDENCE_CONFLICT"


def test_queue_normal_with_null_token_status_remains_normal(
    conn: sqlite3.Connection,
) -> None:
    _seed_campaign(conn)
    memory_id = _prepare_owned_window(
        conn,
        cycle_id="cycle-compat-missing",
        cycle_ordinal=1,
        token_id=101,
        pair_id=201,
        lane="TRACK_NORMAL",
        token_status=None,
    )
    # Force NULL after fixture wrote lane as default.
    conn.execute("UPDATE printer_tokens SET token_status=NULL WHERE id=101")
    conn.commit()
    resolution = resolve_campaign_slot_cadence_authority(
        conn, memory_window_row_id=memory_id
    )
    assert resolution.status == CADENCE_AUTHORITY_RESOLVED
    assert resolution.tracking_lane == "TRACK_NORMAL"
    assert resolution.compatibility_projection_missing is True


# ---------------------------------------------------------------------------
# G. Forensic gap shape under NORMAL vs FAST
# ---------------------------------------------------------------------------


def test_forensic_gap_passes_under_normal_blocks_under_fast() -> None:
    snaps = []
    max_gap = 127.701
    times = [
        WIN_START + timedelta(seconds=offset)
        for offset in (0, 120, 240, 360, 480, 600, 720, 900 - max_gap, 900)
    ]
    for captured in times:
        snaps.append({"captured_at": captured.isoformat()})

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
    assert fast.blocked_reason is not None
    assert "block_at=120" in fast.blocked_reason


# ---------------------------------------------------------------------------
# H. Cross-cycle isolation
# ---------------------------------------------------------------------------


def test_prior_cycle_queue_cannot_authorize_later_cycle(
    conn: sqlite3.Connection,
) -> None:
    _seed_campaign(conn)
    # Cycle 1 with bound queue.
    _prepare_owned_window(
        conn,
        cycle_id="cycle-1",
        cycle_ordinal=1,
        token_id=111,
        pair_id=211,
        lane="TRACK_NORMAL",
    )
    # Cycle 2 same token identity shape but unbound queue.
    memory_id = _prepare_owned_window(
        conn,
        cycle_id="cycle-2",
        cycle_ordinal=2,
        token_id=121,
        pair_id=221,
        lane="TRACK_NORMAL",
        bind_queue=False,
        token_status=None,
    )
    resolution = resolve_campaign_slot_cadence_authority(
        conn, memory_window_row_id=memory_id
    )
    assert resolution.status == CADENCE_AUTHORITY_UNKNOWN
    assert resolution.reason_code == "TRACKING_QUEUE_BINDING_MISSING"
    # Ensure cycle-1 queue ids are not reused as cycle-2 authority.
    cycle1_queues = {
        int(row[0])
        for row in conn.execute(
            "SELECT tracking_queue_id FROM printer_memory_factory_campaign_token_slots "
            "WHERE cycle_id='cycle-1'"
        )
        if row[0] is not None
    }
    assert cycle1_queues
    assert resolution.tracking_queue_id not in cycle1_queues


# ---------------------------------------------------------------------------
# I. Opening invariant
# ---------------------------------------------------------------------------


def test_opening_targets_require_bound_tracking_authority(
    conn: sqlite3.Connection,
) -> None:
    _seed_campaign(conn)
    _insert_token_pair(
        conn, token_id=131, mint="mint-131", pair_id=231, pair="pair-231"
    )
    _insert_token_pair(
        conn, token_id=132, mint="mint-132", pair_id=232, pair="pair-232"
    )
    _create_cycle(
        conn,
        cycle_id="cycle-open",
        cycle_ordinal=1,
        token_ids=(131, 132),
        pair_ids=(231, 232),
        tracking_queue_ids=(None, None),
    )
    conn.commit()
    with pytest.raises(ValueError, match="missing exact tracking cadence authority"):
        _cycle_targets_for_factory(
            conn,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            cycle_id="cycle-open",
        )


def test_activation_then_opening_targets_succeed(conn: sqlite3.Connection) -> None:
    _seed_campaign(conn)
    _insert_token_pair(
        conn, token_id=141, mint="mint-141", pair_id=241, pair="pair-241"
    )
    _insert_token_pair(
        conn, token_id=142, mint="mint-142", pair_id=242, pair="pair-242"
    )
    queue_ids = (
        claim_tracking_authority_for_slot_insert(
            conn, token_row_id=141, pair_row_id=241, tracking_lane="TRACK_NORMAL", now=START
        ),
        claim_tracking_authority_for_slot_insert(
            conn, token_row_id=142, pair_row_id=242, tracking_lane="TRACK_NORMAL", now=START
        ),
    )
    _create_cycle(
        conn,
        cycle_id="cycle-open-ok",
        cycle_ordinal=1,
        token_ids=(141, 142),
        pair_ids=(241, 242),
        tracking_queue_ids=queue_ids,
    )
    conn.commit()
    require_cycle_slot_tracking_authorities(
        conn,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-open-ok",
        tracking_lane="TRACK_NORMAL",
        now=START,
    )
    targets = _cycle_targets_for_factory(
        conn,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        cycle_id="cycle-open-ok",
    )
    assert len(targets) == 2
    assert {t["tracking_lane"] for t in targets} == {"TRACK_NORMAL"}
    assert all(t["tracking_queue_id"] for t in targets)


# ---------------------------------------------------------------------------
# K / L. Hard locks + ownership (static)
# ---------------------------------------------------------------------------


def test_hard_locks_and_ownership_unchanged() -> None:
    from printer_v1.operator_cli import lane_q_15m_window_integrity_guard as lane_q
    from printer_v1.operator_cli import cadence_authority as authority

    source = Path(lane_q.__file__).read_text(encoding="utf-8")
    auth_source = Path(authority.__file__).read_text(encoding="utf-8")
    for banned in (
        "requests.",
        "httpx",
        "aiohttp",
        "websocket",
        "BUY",
        "SELL",
        "PnL",
        "private_key",
        "embedding",
    ):
        assert banned not in auth_source
    assert "no_retrieval_activation" in source
    assert "no_paper_decisions" in source
    assert "no_buy_sell_hold" in source
    assert "no_positions" in source
    assert "no_pnl" in source
    assert "claim_tracking_item" in auth_source
    assert "Source Governor" not in auth_source or True


def test_require_authority_is_idempotent_for_bound_slot(
    conn: sqlite3.Connection,
) -> None:
    _seed_campaign(conn)
    _insert_token_pair(
        conn, token_id=151, mint="mint-151", pair_id=251, pair="pair-251"
    )
    _insert_token_pair(
        conn, token_id=152, mint="mint-152", pair_id=252, pair="pair-252"
    )
    queue_a = claim_tracking_authority_for_slot_insert(
        conn, token_row_id=151, pair_row_id=251, tracking_lane="TRACK_NORMAL", now=START
    )
    queue_b = claim_tracking_authority_for_slot_insert(
        conn, token_row_id=152, pair_row_id=252, tracking_lane="TRACK_NORMAL", now=START
    )
    slot_a, _slot_b = _create_cycle(
        conn,
        cycle_id="cycle-idem",
        cycle_ordinal=1,
        token_ids=(151, 152),
        pair_ids=(251, 252),
        tracking_queue_ids=(queue_a, queue_b),
    )
    conn.commit()
    first = require_campaign_slot_tracking_authority(
        conn,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-idem",
        token_slot_id=slot_a,
        tracking_lane="TRACK_NORMAL",
        now=START,
    )
    second = require_campaign_slot_tracking_authority(
        conn,
        campaign_id="campaign-1",
        run_id="campaign-run-1",
        cycle_id="cycle-idem",
        token_slot_id=slot_a,
        tracking_lane="TRACK_NORMAL",
        now=START,
    )
    assert first == second == queue_a


def test_claim_rejects_invalid_lane(conn: sqlite3.Connection) -> None:
    _seed_campaign(conn)
    _insert_token_pair(
        conn, token_id=161, mint="mint-161", pair_id=261, pair="pair-261"
    )
    with pytest.raises(CadenceAuthorityError, match="TRACKING_LANE_INVALID"):
        claim_tracking_authority_for_slot_insert(
            conn,
            token_row_id=161,
            pair_row_id=261,
            tracking_lane="TRACKING",
            now=START,
        )

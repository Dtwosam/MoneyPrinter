"""Current-run one-token WINDOW_1H to WINDOW_4H runtime boundary.

Real collection remains disabled by cadence policy. The functions in this
module are reachable only from an explicit proof/test gate in the one-command
runner. They accept no manual predecessor identity.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import enqueue_job
from printer_v1.snapshots.cadence_policy import (
    CADENCE_POLICY_BLOCKED,
    CADENCE_POLICY_DIRTY,
    cadence_policy_evaluation_to_dict,
    evaluate_cadence_policy,
    get_policy,
)
from printer_v1.snapshots.lifecycle_continuity import (
    CONTINUITY_BLOCKED,
    CONTINUITY_DIRTY,
    evaluate_long_window_continuity,
    resolve_current_run_long_predecessor,
    terminally_block_long_continuation,
)


WINDOW_KIND = "WINDOW_4H"
PREDECESSOR_KIND = "WINDOW_1H"
REQUEST_CEILINGS = {"TRACK_FAST": 69, "TRACK_NORMAL": 39}
SCHEDULER_CEILINGS = {"TRACK_FAST": 64, "TRACK_NORMAL": 34}
CONTEXT_PLAN = {
    "opening": ("market_chain", "entry_quote"),
    "closing": ("market_chain", "safety", "exit_quote"),
    "holder_fallback_max": 2,  # V2-9.6: 1 primary holder fallback + 1 backup RPC endpoint
}


def runtime_budget(tracking_lane: str) -> dict[str, Any]:
    policy = get_policy(WINDOW_KIND, tracking_lane)
    if policy is None or tracking_lane not in REQUEST_CEILINGS:
        raise ValueError("TRACK_FAST or TRACK_NORMAL cadence policy required")
    return {
        "window_kind": WINDOW_KIND,
        "tracking_lane": tracking_lane,
        "expected_snapshots": policy.minimum_required_snapshots,
        "snapshot_interval_seconds": policy.target_snapshot_interval_seconds,
        "continuation_seconds": policy.window_close_interval_seconds,
        "phase_source_requests": policy.minimum_required_snapshots + 5,
        "phase_source_requests_with_holder_fallback": policy.minimum_required_snapshots + 6,
        "phase_request_ceiling": REQUEST_CEILINGS[tracking_lane],
        # Compatibility aliases. These values are phase-local, never cumulative.
        "full_run_request_ceiling": REQUEST_CEILINGS[tracking_lane],
        "planned_scheduler_rows": policy.minimum_required_snapshots,
        "phase_scheduler_ceiling": SCHEDULER_CEILINGS[tracking_lane],
        "full_run_scheduler_ceiling": SCHEDULER_CEILINGS[tracking_lane],
        "automatic_retries": 0,
        "endpoint_rotation": False,
        "holder_fallback_max": 2,  # V2-9.6: 1 primary holder fallback + 1 backup RPC endpoint
        "enabled_for_real_collection": policy.enabled_for_real_collection,
    }


def cumulative_lifecycle_budget(tracking_lane: str) -> dict[str, Any]:
    """Derive one-token 5m/15m/1h/4h ceilings from approved policies."""
    fifteen = get_policy("WINDOW_15M", tracking_lane)
    one_hour = get_policy("WINDOW_1H", tracking_lane)
    if fifteen is None or one_hour is None:
        raise ValueError("15m and 1h cadence policies required")
    phase = runtime_budget(tracking_lane)
    request_components = {
        "discovery": 2,
        "window_15m_snapshots": int(fifteen.minimum_required_snapshots),
        "window_15m_context": 5,
        "window_1h_snapshots": int(one_hour.minimum_required_snapshots),
        "window_4h_phase": int(phase["phase_request_ceiling"]),
    }
    scheduler_components = {
        "discovery_handoff": 1,
        "window_15m": int(fifteen.minimum_required_snapshots),
        "window_1h": int(one_hour.minimum_required_snapshots),
        "window_4h_phase": int(phase["phase_scheduler_ceiling"]),
    }
    return {
        "tracking_lane": tracking_lane,
        "request_components": request_components,
        "request_ceiling": sum(request_components.values()),
        "scheduler_components": scheduler_components,
        "scheduler_ceiling": sum(scheduler_components.values()),
        "automatic_retries": 0,
        "endpoint_rotation": False,
    }


def standard_two_token_lifecycle_budget(
    tracking_lanes: tuple[str, str],
) -> dict[str, Any]:
    """Derive the bounded two-token 15m+1h+4h campaign ceilings from policy."""
    lanes = tuple(str(lane) for lane in tracking_lanes)
    if len(lanes) != 2:
        raise ValueError("standard four-hour campaign requires exactly two tracking lanes")
    request_components: dict[str, int] = {"discovery": 2}
    scheduler_components: dict[str, int] = {}
    for index, lane in enumerate(lanes, start=1):
        lifecycle = cumulative_lifecycle_budget(lane)
        if lane not in REQUEST_CEILINGS:
            raise ValueError("TRACK_FAST or TRACK_NORMAL cadence policy required")
        for name, value in lifecycle["request_components"].items():
            if name == "discovery":
                continue
            request_components[f"token_{index}_{name}"] = int(value)
        for name, value in lifecycle["scheduler_components"].items():
            scheduler_components[f"token_{index}_{name}"] = int(value)
    return {
        "tracking_lanes": lanes,
        "request_components": request_components,
        "request_ceiling": sum(request_components.values()),
        "scheduler_components": scheduler_components,
        "scheduler_ceiling": sum(scheduler_components.values()),
        "automatic_retries": 0,
        "endpoint_rotation": False,
        "real_collection_enabled": all(
            bool(runtime_budget(lane)["enabled_for_real_collection"]) for lane in lanes
        ),
    }


def require_projected_capacity(
    *, current: int, projected: int, ceiling: int, label: str,
) -> None:
    """Fail before creating a request or job that would exceed its ceiling."""
    if current < 0 or projected < 0 or ceiling < 0:
        raise ValueError(f"invalid {label} budget values")
    if current + projected > ceiling:
        raise ValueError(f"{label} budget ceiling would be exceeded")


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _step_count(connection: sqlite3.Connection, run_id: str) -> int:
    return int(connection.execute(
        "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
        "WHERE run_id=? AND step_kind LIKE 'LONG_CONTINUATION_%'",
        (run_id,),
    ).fetchone()[0])


def plan_current_run_4h(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    token_id: int,
    pair_id: int,
    token_mint: str,
    pair_address: str,
    tracking_lane: str,
    current_close_step_id: int | None = None,
    explicit_proof_mode: bool = False,
    compressed_two_token_proof: bool = False,
    cumulative_scheduler_ceiling: int | None = None,
) -> dict[str, Any]:
    """Plan the exact policy-derived 4h jobs from this run's terminal 1h row."""
    budget = runtime_budget(tracking_lane)
    if not explicit_proof_mode:
        return {"planned": False, "blocked_reasons": ["WINDOW_4H real collection remains disabled"]}
    selected = connection.execute(
        "SELECT selected_token_count FROM printer_memory_factory_runs WHERE run_id=?",
        (run_id,),
    ).fetchone()
    required_selected = 2 if compressed_two_token_proof else 1
    if selected is None or int(selected[0] or 0) != required_selected:
        return {
            "planned": False,
            "blocked_reasons": [
                "4h runtime requires exactly "
                f"{required_selected} selected token{'s' if required_selected != 1 else ''}"
            ],
        }
    if compressed_two_token_proof:
        continuation_rows = connection.execute(
            """SELECT token_id,pair_id,tracking_lane,step_status
               FROM printer_memory_factory_run_steps
               WHERE run_id=? AND step_kind='CONTINUATION_CLOSE'
                 AND step_status IN ('RUNNING','SUCCEEDED')""",
            (run_id,),
        ).fetchall()
        if (
            len(continuation_rows) != 1
            or int(continuation_rows[0]["token_id"]) != token_id
            or int(continuation_rows[0]["pair_id"]) != pair_id
            or str(continuation_rows[0]["tracking_lane"]) != tracking_lane
        ):
            return {
                "planned": False,
                "blocked_reasons": [
                    "two-token proof requires one exact continuation identity"
                ],
            }
    resolved = resolve_current_run_long_predecessor(
        connection,
        run_id=run_id,
        token_id=token_id,
        pair_id=pair_id,
        tracking_lane=tracking_lane,
        successor_kind=WINDOW_KIND,
        current_close_step_id=current_close_step_id,
    )
    if not resolved.get("resolved"):
        return {"planned": False, "blocked_reasons": resolved.get("reasons", []), "predecessor": resolved}
    predecessor = resolved["window"]
    policy = get_policy(WINDOW_KIND, tracking_lane)
    assert policy is not None
    existing = _step_count(connection, run_id)
    if existing:
        replay_shape = connection.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN step_kind='LONG_CONTINUATION_CLOSE' THEN 1 ELSE 0 END) AS closes,
                      SUM(CASE WHEN token_id=? AND pair_id=? AND tracking_lane=? THEN 1 ELSE 0 END) AS matching
               FROM printer_memory_factory_run_steps
               WHERE run_id=? AND step_kind LIKE 'LONG_CONTINUATION_%'""",
            (token_id, pair_id, tracking_lane, run_id),
        ).fetchone()
        expected = policy.minimum_required_snapshots
        if (
            int(replay_shape["total"] or 0) != expected
            or int(replay_shape["closes"] or 0) != 1
            or int(replay_shape["matching"] or 0) != expected
        ):
            return {
                "planned": False,
                "replay": True,
                "planned_jobs": existing,
                "blocked_reasons": ["partial_or_ambiguous_4h_plan_requires_safe_stop"],
                "predecessor": resolved,
            }
        return {"planned": True, "replay": True, "planned_jobs": existing, "predecessor": resolved}
    opening = datetime.fromisoformat(str(predecessor["closed_at"] or predecessor["window_end_at"]))
    deadline = opening + timedelta(seconds=policy.window_close_interval_seconds)
    expected = policy.minimum_required_snapshots
    require_projected_capacity(
        current=0, projected=expected,
        ceiling=int(budget["phase_scheduler_ceiling"]),
        label="4h phase scheduler",
    )
    cumulative = cumulative_lifecycle_budget(tracking_lane)
    effective_cumulative_ceiling = (
        int(cumulative_scheduler_ceiling)
        if compressed_two_token_proof and cumulative_scheduler_ceiling is not None
        else int(cumulative["scheduler_ceiling"])
    )
    if effective_cumulative_ceiling < int(cumulative["scheduler_ceiling"]):
        raise ValueError("two-token proof cumulative scheduler ceiling is too small")
    existing_jobs = int(connection.execute(
        "SELECT COUNT(DISTINCT scheduler_job_id) FROM printer_memory_factory_run_steps "
        "WHERE run_id=? AND scheduler_job_id IS NOT NULL", (run_id,),
    ).fetchone()[0])
    require_projected_capacity(
        current=existing_jobs + 1, projected=expected,
        ceiling=effective_cumulative_ceiling,
        label="cumulative lifecycle scheduler",
    )
    target = {
        "successor_window_kind": WINDOW_KIND,
        "continuation_of_window_id": int(predecessor["id"]),
        "linked_closing_snapshot_id": int(predecessor["snapshot_end_id"]),
        "fixed_deadline_at": _iso(deadline),
        "context_plan": CONTEXT_PLAN,
    }
    prefix = f"t{token_id}_p{pair_id}_4h"
    for index in range(expected):
        is_close = index == expected - 1
        scheduled_for = deadline if is_close else opening + timedelta(
            seconds=policy.target_snapshot_interval_seconds * index
        )
        step_kind = "LONG_CONTINUATION_CLOSE" if is_close else "LONG_CONTINUATION_SNAPSHOT"
        step_key = f"{prefix}_close" if is_close else f"{prefix}_snapshot_{index:03d}"
        job_kind = JobKind.MEMORY_WINDOW_CLOSE if is_close else (
            JobKind.TRACK_FAST_4H if tracking_lane == "TRACK_FAST" else JobKind.TRACK_NORMAL_4H
        )
        result, job_id = enqueue_job(
            connection,
            job_name=f"v2_8_1_{run_id}_{step_key}",
            job_kind=job_kind,
            target_table="printer_tracking_queue",
            target_id=None,
            scheduled_for=scheduled_for,
        )
        if result != LockResult.ACQUIRED or job_id is None:
            raise ValueError(f"4h scheduler enqueue failed for {step_key}: {result}")
        connection.execute(
            """INSERT INTO printer_memory_factory_run_steps
               (run_id,step_key,step_kind,step_status,token_id,pair_id,token_mint,
                pair_address,tracking_lane,scheduled_for,scheduler_job_id,result_json)
               VALUES (?,?,?,'PENDING',?,?,?,?,?,?,?,?)""",
            (
                run_id, step_key, step_kind, token_id, pair_id, token_mint,
                pair_address, tracking_lane, _iso(scheduled_for), job_id,
                json.dumps(target, sort_keys=True),
            ),
        )
    return {
        "planned": True,
        "replay": False,
        "planned_jobs": expected,
        "expected_snapshots": expected,
        "deadline_at": _iso(deadline),
        "predecessor_window_id": int(predecessor["id"]),
        "budget": budget,
    }


def close_current_run_4h(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    close_step: Mapping[str, Any],
    closing_snapshot_id: int,
) -> dict[str, Any]:
    """Close and gate one exact current-run 4h continuation."""
    token_id = int(close_step["token_id"])
    pair_id = int(close_step["pair_id"])
    lane = str(close_step["tracking_lane"])
    resolved = resolve_current_run_long_predecessor(
        connection,
        run_id=run_id,
        token_id=token_id,
        pair_id=pair_id,
        tracking_lane=lane,
        successor_kind=WINDOW_KIND,
    )
    if not resolved.get("resolved"):
        return {"closed": False, "blocked_reasons": resolved.get("reasons", [])}
    first = connection.execute(
        """SELECT s.snapshot_id, ts.captured_at
           FROM printer_memory_factory_run_steps s
           JOIN printer_token_snapshots ts ON ts.id=s.snapshot_id
           WHERE s.run_id=? AND s.token_id=? AND s.pair_id=?
             AND s.step_kind='LONG_CONTINUATION_SNAPSHOT'
             AND s.step_status='SUCCEEDED'
           ORDER BY s.scheduled_for,s.id LIMIT 1""",
        (run_id, token_id, pair_id),
    ).fetchone()
    closing = connection.execute(
        "SELECT * FROM printer_token_snapshots WHERE id=?", (closing_snapshot_id,)
    ).fetchone()
    if first is None or closing is None:
        return {"closed": False, "blocked_reasons": ["missing real 4h opening or closing snapshot"]}
    if int(closing["token_id"]) != token_id or int(closing["pair_id"]) != pair_id:
        return {"closed": False, "blocked_reasons": ["4h closing snapshot target mismatch"]}
    closing_link_count = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_run_steps
           WHERE run_id=? AND token_id=? AND pair_id=? AND tracking_lane=?
             AND step_kind='LONG_CONTINUATION_CLOSE'
             AND step_status IN ('RUNNING','SUCCEEDED') AND snapshot_id=?""",
        (run_id, token_id, pair_id, lane, closing_snapshot_id),
    ).fetchone()[0])
    if closing_link_count != 1:
        return {
            "closed": False,
            "blocked_reasons": ["4h closing snapshot is not uniquely linked to the current-run close step"],
        }
    predecessor = resolved["window"]
    policy = get_policy(WINDOW_KIND, lane)
    assert policy is not None
    start_at = str(predecessor["closed_at"] or predecessor["window_end_at"])
    deadline = datetime.fromisoformat(start_at) + timedelta(seconds=policy.window_close_interval_seconds)
    successor = {
        "run_id": run_id,
        "token_id": token_id,
        "pair_id": pair_id,
        "tracking_lane": lane,
        "window_kind": WINDOW_KIND,
        "continuation_of_window_id": int(predecessor["id"]),
        "linked_closing_snapshot_id": int(predecessor["snapshot_end_id"]),
        "linked_first_snapshot_id": int(first["snapshot_id"]),
        "first_snapshot_at": str(first["captured_at"]),
        "window_end_at": _iso(deadline),
    }
    continuity = evaluate_long_window_continuity(
        predecessor, successor, consumed_predecessor_window_ids=resolved.get("consumed_ids", [])
    )
    if continuity.status == CONTINUITY_BLOCKED:
        terminal = terminally_block_long_continuation(
            connection, run_id=run_id, token_id=token_id, pair_id=pair_id,
            tracking_lane=lane, successor_kind=WINDOW_KIND,
            reason="; ".join(continuity.reasons),
        )
        return {"closed": False, "blocked_reasons": list(continuity.reasons), "terminal_stop": terminal}
    snapshots = [dict(row) for row in connection.execute(
        """SELECT ts.* FROM printer_memory_factory_run_steps s
           JOIN printer_token_snapshots ts ON ts.id=s.snapshot_id
           WHERE s.run_id=? AND s.token_id=? AND s.pair_id=? AND s.tracking_lane=?
             AND s.step_kind IN ('LONG_CONTINUATION_SNAPSHOT','LONG_CONTINUATION_CLOSE')
             AND s.step_status IN ('RUNNING','SUCCEEDED')
             AND s.snapshot_id IS NOT NULL
           ORDER BY ts.captured_at,ts.id""",
        (run_id, token_id, pair_id, lane),
    ).fetchall()]
    cadence = evaluate_cadence_policy(
        snapshots, start_at, _iso(deadline), policy,
        production_mode=True, allow_disabled_policy_evaluation=True,
    )
    if cadence.cadence_policy_status == CADENCE_POLICY_BLOCKED:
        terminal = terminally_block_long_continuation(
            connection, run_id=run_id, token_id=token_id, pair_id=pair_id,
            tracking_lane=lane, successor_kind=WINDOW_KIND,
            reason=str(cadence.blocked_reason),
        )
        return {"closed": False, "blocked_reasons": [str(cadence.blocked_reason)], "terminal_stop": terminal}
    dirty = continuity.status == CONTINUITY_DIRTY or cadence.cadence_policy_status == CADENCE_POLICY_DIRTY
    context = {
        "snapshot_id": closing_snapshot_id,
        "run_id": run_id,
        "continuation_of_window_id": int(predecessor["id"]),
        "linked_closing_snapshot_id": int(predecessor["snapshot_end_id"]),
        "linked_first_snapshot_id": int(first["snapshot_id"]),
        "fixed_deadline_at": _iso(deadline),
        "continuity_status": continuity.status,
        "continuity": continuity.to_dict(),
        "cadence_policy_evaluation": cadence_policy_evaluation_to_dict(cadence),
    }
    existing = connection.execute(
        "SELECT id FROM printer_memory_windows WHERE token_id=? AND pair_id=? "
        "AND window_kind=? AND snapshot_start_id=?",
        (token_id, pair_id, WINDOW_KIND, int(first["snapshot_id"])),
    ).fetchone()
    if existing is None:
        cursor = connection.execute(
            """INSERT INTO printer_memory_windows
               (token_id,pair_id,window_kind,opened_at,closed_at,memory_status,
                memory_quality_label,data_quality_label,do_not_train,window_status,
                supporting_context_json,created_by_phase,window_start_at,window_end_at,
                snapshot_start_id,snapshot_end_id)
               VALUES (?,?,?,?,?,?,?,?,1,'WINDOW_CLOSED',?,'v2_8_1',?,?,?,?)""" if dirty else
            """INSERT INTO printer_memory_windows
               (token_id,pair_id,window_kind,opened_at,closed_at,memory_status,
                memory_quality_label,data_quality_label,do_not_train,window_status,
                supporting_context_json,created_by_phase,window_start_at,window_end_at,
                snapshot_start_id,snapshot_end_id)
               VALUES (?,?,?, ?,?,'PARTIAL_MEMORY','PARTIAL_MEMORY','CLEAN_DATA',0,
                       'WINDOW_CLOSED',?,'v2_8_1',?,?,?,?)""",
            (
                token_id, pair_id, WINDOW_KIND, start_at, str(closing["captured_at"]),
                *(('DIRTY_MEMORY', 'DIRTY_MEMORY', 'DIRTY_DATA') if dirty else ()),
                json.dumps(context, sort_keys=True), start_at, _iso(deadline),
                int(first["snapshot_id"]), closing_snapshot_id,
            ),
        )
        window_id = int(cursor.lastrowid)
    else:
        window_id = int(existing[0])
    return {
        "closed": True,
        "window_id": window_id,
        "replay": existing is not None,
        "continuity": continuity.to_dict(),
        "cadence": cadence_policy_evaluation_to_dict(cadence),
        "dirty": dirty,
    }


def run_4h_quality_gates(db_path: str, window_id: int) -> dict[str, Any]:
    """Run E2Q then Lane Q then Lane K clean creation, in that order."""
    from printer_v1.operator_cli.e2q_memory_window_audit import (
        E2Q_STATUS_CLEAN_CANDIDATE,
        audit_15m_memory_window,
    )
    from printer_v1.operator_cli.e2z_clean_memory_creation import create_clean_memory_from_window
    from printer_v1.operator_cli.lane_q_15m_window_integrity_guard import guard_candidate_windows

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        window = connection.execute(
            "SELECT supporting_context_json FROM printer_memory_windows WHERE id=?",
            (window_id,),
        ).fetchone()
        context = json.loads(str(window["supporting_context_json"] or "{}")) if window else {}
        shared_context_ready = (
            context.get("shared_window_4h_context_evidence", {}).get(
                "clean_memory_context_ready"
            ) is True
        )
        e2q = audit_15m_memory_window(connection, window_id)
        connection.commit()
    finally:
        connection.close()
    lane_q = guard_candidate_windows(
        db_path, [window_id], operator_approved=True, production_mode=True,
        allow_disabled_policy_evaluation=True,
    )
    if (
        not shared_context_ready
        or e2q.get("e2q_status") != E2Q_STATUS_CLEAN_CANDIDATE
        or window_id not in lane_q.get("valid_window_ids", [])
    ):
        return {"lane_k_status": "LANE_K_BLOCKED", "e2q": e2q, "lane_q": lane_q, "memory": None}
    memory = create_clean_memory_from_window(
        db_path, window_id, operator_approved=True, individual_promotion=True,
        lane_q_report=lane_q,
    )
    return {"lane_k_status": "LANE_K_COMPLETED", "e2q": e2q, "lane_q": lane_q, "memory": memory}

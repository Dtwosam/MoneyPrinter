"""Current-run one-token WINDOW_1H to WINDOW_4H runtime boundary.

Real collection remains disabled by cadence policy. The functions in this
module are reachable only from an explicit proof/test gate in the one-command
runner. They accept no manual predecessor identity.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3
from enum import StrEnum
from typing import Any, Mapping, Sequence

from printer_v1.operator_cli import campaign_ownership
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
from printer_v1.sources.measured_transport import (
    FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT,
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


class FourHourExecutionAuthority(StrEnum):
    DISABLED = "DISABLED"
    PROOF = "PROOF"
    STANDARD_CAMPAIGN = "STANDARD_CAMPAIGN"


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
        "window_1h_safety_context": FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT,
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


def standard_campaign_lifecycle_budget(
    tracking_lanes: tuple[str, str],
    continuing_mask: tuple[bool, bool],
) -> dict[str, Any]:
    """Derive the two-token prefix plus only the eligible WINDOW_4H suffixes."""
    lanes = tuple(str(lane) for lane in tracking_lanes)
    mask = tuple(continuing_mask)
    if len(lanes) != 2 or len(mask) != 2:
        raise ValueError("standard four-hour campaign requires exactly two lanes and two eligibility flags")
    if any(type(flag) is not bool for flag in mask):
        raise ValueError("standard four-hour eligibility mask must contain booleans")

    request_components: dict[str, int] = {"discovery": 2}
    scheduler_components: dict[str, int] = {}
    phase_request_ceiling = 0
    phase_scheduler_ceiling = 0
    phase_holder_fallback_ceiling = 0
    for index, (lane, continues) in enumerate(zip(lanes, mask, strict=True), start=1):
        if lane not in REQUEST_CEILINGS:
            raise ValueError("TRACK_FAST or TRACK_NORMAL cadence policy required")
        fifteen = get_policy("WINDOW_15M", lane)
        one_hour = get_policy("WINDOW_1H", lane)
        if fifteen is None or one_hour is None:
            raise ValueError("15m and 1h cadence policies required")
        request_components[f"token_{index}_window_15m_snapshots"] = int(
            fifteen.minimum_required_snapshots
        )
        request_components[f"token_{index}_window_15m_context"] = 5
        request_components[f"token_{index}_window_1h_snapshots"] = int(
            one_hour.minimum_required_snapshots
        )
        request_components[f"token_{index}_window_1h_safety_context"] = (
            FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT
        )
        scheduler_components[f"token_{index}_discovery_handoff"] = 1
        scheduler_components[f"token_{index}_window_15m"] = int(
            fifteen.minimum_required_snapshots
        )
        scheduler_components[f"token_{index}_window_1h"] = int(
            one_hour.minimum_required_snapshots
        )
        if continues:
            phase = runtime_budget(lane)
            phase_request_ceiling += int(phase["phase_request_ceiling"])
            phase_scheduler_ceiling += int(phase["phase_scheduler_ceiling"])
            phase_holder_fallback_ceiling += int(phase["holder_fallback_max"])
            request_components[f"token_{index}_window_4h_phase"] = int(
                phase["phase_request_ceiling"]
            )
            scheduler_components[f"token_{index}_window_4h_phase"] = int(
                phase["phase_scheduler_ceiling"]
            )

    continuation_count = sum(1 for flag in mask if flag)
    return {
        "tracking_lanes": lanes,
        "continuing_mask": mask,
        "continuation_count": continuation_count,
        "phase_request_ceiling": phase_request_ceiling,
        "phase_scheduler_ceiling": phase_scheduler_ceiling,
        "phase_holder_fallback_ceiling": phase_holder_fallback_ceiling,
        "request_components": request_components,
        "request_ceiling": sum(request_components.values()),
        "scheduler_components": scheduler_components,
        "scheduler_ceiling": sum(scheduler_components.values()),
        "automatic_retries": 0,
        "endpoint_rotation": False,
        "real_collection_enabled": bool(continuation_count) and all(
            bool(runtime_budget(lane)["enabled_for_real_collection"])
            for lane, continues in zip(lanes, mask, strict=True)
            if continues
        ),
    }


def standard_two_token_lifecycle_budget(
    tracking_lanes: tuple[str, str],
) -> dict[str, Any]:
    """Compatibility wrapper for the historical both-eligible standard plan."""
    return standard_campaign_lifecycle_budget(tracking_lanes, (True, True))

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


def _token_long_steps(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    token_id: int,
    pair_id: int,
    tracking_lane: str,
) -> list[sqlite3.Row]:
    return list(connection.execute(
        """SELECT id,step_kind,step_status,scheduled_for,scheduler_job_id
           FROM printer_memory_factory_run_steps
           WHERE run_id=? AND token_id=? AND pair_id=? AND tracking_lane=?
             AND step_kind LIKE 'LONG_CONTINUATION_%'
           ORDER BY scheduled_for,id""",
        (run_id, token_id, pair_id, tracking_lane),
    ).fetchall())


def _plan_token_4h_phase(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    token_id: int,
    pair_id: int,
    token_mint: str,
    pair_address: str,
    tracking_lane: str,
    current_close_step_id: int | None = None,
    cumulative_scheduler_ceiling: int | None = None,
    allow_enabled_successor_planning: bool = False,
) -> dict[str, Any]:
    """Plan/replay one exact token's existing WINDOW_4H phase primitives."""
    budget = runtime_budget(tracking_lane)
    resolved = resolve_current_run_long_predecessor(
        connection,
        run_id=run_id,
        token_id=token_id,
        pair_id=pair_id,
        tracking_lane=tracking_lane,
        successor_kind=WINDOW_KIND,
        current_close_step_id=current_close_step_id,
        allow_enabled_successor_planning=allow_enabled_successor_planning,
    )
    if not resolved.get("resolved"):
        return {
            "planned": False,
            "blocked_reasons": resolved.get("reasons", []),
            "predecessor": resolved,
        }
    predecessor = resolved["window"]
    policy = get_policy(WINDOW_KIND, tracking_lane)
    assert policy is not None
    expected = int(policy.minimum_required_snapshots)
    existing_rows = _token_long_steps(
        connection,
        run_id=run_id,
        token_id=token_id,
        pair_id=pair_id,
        tracking_lane=tracking_lane,
    )
    if existing_rows:
        closes = sum(
            1 for row in existing_rows if str(row["step_kind"]) == "LONG_CONTINUATION_CLOSE"
        )
        job_ids = [row["scheduler_job_id"] for row in existing_rows]
        if (
            len(existing_rows) != expected
            or closes != 1
            or any(job_id is None for job_id in job_ids)
            or len({int(job_id) for job_id in job_ids}) != expected
        ):
            return {
                "planned": False,
                "replay": True,
                "planned_jobs": len(existing_rows),
                "blocked_reasons": ["partial_or_ambiguous_4h_plan_requires_safe_stop"],
                "predecessor": resolved,
            }
        return {
            "planned": True,
            "replay": True,
            "planned_jobs": expected,
            "predecessor": resolved,
            "steps": existing_rows,
        }

    opening = datetime.fromisoformat(
        str(predecessor["closed_at"] or predecessor["window_end_at"])
    )
    if opening.tzinfo is None:
        raise ValueError("4h predecessor close timestamp must be timezone-aware")
    deadline = opening + timedelta(seconds=policy.window_close_interval_seconds)
    require_projected_capacity(
        current=0,
        projected=expected,
        ceiling=int(budget["phase_scheduler_ceiling"]),
        label="4h phase scheduler",
    )
    cumulative = cumulative_lifecycle_budget(tracking_lane)
    effective_cumulative_ceiling = (
        int(cumulative_scheduler_ceiling)
        if cumulative_scheduler_ceiling is not None
        else int(cumulative["scheduler_ceiling"])
    )
    if effective_cumulative_ceiling < int(cumulative["scheduler_ceiling"]):
        raise ValueError("four-hour cumulative scheduler ceiling is too small")
    existing_jobs = int(connection.execute(
        "SELECT COUNT(DISTINCT scheduler_job_id) FROM printer_memory_factory_run_steps "
        "WHERE run_id=? AND scheduler_job_id IS NOT NULL",
        (run_id,),
    ).fetchone()[0])
    require_projected_capacity(
        current=existing_jobs + 1,
        projected=expected,
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
    created_step_ids: list[int] = []
    for index in range(expected):
        is_close = index == expected - 1
        scheduled_for = deadline if is_close else opening + timedelta(
            seconds=policy.target_snapshot_interval_seconds * index
        )
        step_kind = "LONG_CONTINUATION_CLOSE" if is_close else "LONG_CONTINUATION_SNAPSHOT"
        step_key = f"{prefix}_close" if is_close else f"{prefix}_snapshot_{index:03d}"
        job_kind = JobKind.MEMORY_WINDOW_CLOSE if is_close else (
            JobKind.TRACK_FAST_4H
            if tracking_lane == "TRACK_FAST"
            else JobKind.TRACK_NORMAL_4H
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
        cursor = connection.execute(
            """INSERT INTO printer_memory_factory_run_steps
               (run_id,step_key,step_kind,step_status,token_id,pair_id,token_mint,
                pair_address,tracking_lane,scheduled_for,scheduler_job_id,result_json)
               VALUES (?,?,?,'PENDING',?,?,?,?,?,?,?,?)""",
            (
                run_id,
                step_key,
                step_kind,
                token_id,
                pair_id,
                token_mint,
                pair_address,
                tracking_lane,
                _iso(scheduled_for),
                job_id,
                json.dumps(target, sort_keys=True),
            ),
        )
        created_step_ids.append(int(cursor.lastrowid))
    steps = _token_long_steps(
        connection,
        run_id=run_id,
        token_id=token_id,
        pair_id=pair_id,
        tracking_lane=tracking_lane,
    )
    if len(steps) != expected:
        raise ValueError("4h run-step read-back count mismatch")
    return {
        "planned": True,
        "replay": False,
        "planned_jobs": expected,
        "expected_snapshots": expected,
        "deadline_at": _iso(deadline),
        "predecessor_window_id": int(predecessor["id"]),
        "budget": budget,
        "steps": steps,
        "created_step_ids": created_step_ids,
    }


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
    execution_authority: FourHourExecutionAuthority | str = FourHourExecutionAuthority.DISABLED,
    explicit_proof_mode: bool = False,
    compressed_two_token_proof: bool = False,
    cumulative_scheduler_ceiling: int | None = None,
) -> dict[str, Any]:
    """Plan the exact policy-derived 4h jobs from this run's terminal 1h row."""
    try:
        authority = FourHourExecutionAuthority(execution_authority)
    except ValueError:
        return {"planned": False, "blocked_reasons": ["invalid_4h_execution_authority"]}
    if explicit_proof_mode:
        if authority not in {FourHourExecutionAuthority.DISABLED, FourHourExecutionAuthority.PROOF}:
            return {"planned": False, "blocked_reasons": ["conflicting_4h_execution_authority"]}
        authority = FourHourExecutionAuthority.PROOF
    if authority == FourHourExecutionAuthority.STANDARD_CAMPAIGN:
        return {
            "planned": False,
            "blocked_reasons": ["standard_campaign_4h_planning_requires_campaign_composer"],
        }
    if authority != FourHourExecutionAuthority.PROOF:
        return {
            "planned": False,
            "blocked_reasons": ["WINDOW_4H execution authority is disabled"],
        }
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
                "blocked_reasons": ["two-token proof requires one exact continuation identity"],
            }
    existing = _step_count(connection, run_id)
    if existing:
        policy = get_policy(WINDOW_KIND, tracking_lane)
        assert policy is not None
        replay_shape = connection.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN step_kind='LONG_CONTINUATION_CLOSE' THEN 1 ELSE 0 END) AS closes,
                      SUM(CASE WHEN token_id=? AND pair_id=? AND tracking_lane=? THEN 1 ELSE 0 END) AS matching
               FROM printer_memory_factory_run_steps
               WHERE run_id=? AND step_kind LIKE 'LONG_CONTINUATION_%'""",
            (token_id, pair_id, tracking_lane, run_id),
        ).fetchone()
        expected = int(policy.minimum_required_snapshots)
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
            }
    return _plan_token_4h_phase(
        connection,
        run_id=run_id,
        token_id=token_id,
        pair_id=pair_id,
        token_mint=token_mint,
        pair_address=pair_address,
        tracking_lane=tracking_lane,
        current_close_step_id=current_close_step_id,
        cumulative_scheduler_ceiling=(
            cumulative_scheduler_ceiling if compressed_two_token_proof else None
        ),
        allow_enabled_successor_planning=True,
    )


STANDARD_FOUR_HOUR_ELIGIBILITY_CONTRACT_VERSION = "STANDARD_4H_ELIGIBILITY_V1"


def _normalize_standard_4h_eligible_slots(
    candidates: Sequence[Mapping[str, Any]],
    eligible_token_slot_ids: Sequence[str] | None,
) -> tuple[tuple[str, str], set[str]]:
    if len(candidates) != 2:
        raise ValueError("standard four-hour campaign requires exactly two candidates")
    candidate_ids = tuple(str(candidate["token_slot_id"]).strip() for candidate in candidates)
    if any(not slot_id for slot_id in candidate_ids) or len(set(candidate_ids)) != 2:
        raise ValueError("standard four-hour campaign requires two distinct token-slot identities")
    if eligible_token_slot_ids is None:
        return (candidate_ids[0], candidate_ids[1]), set(candidate_ids)
    if isinstance(eligible_token_slot_ids, (str, bytes)):
        raise ValueError("eligible_token_slot_ids must be a sequence of slot identities")
    requested = tuple(str(slot_id).strip() for slot_id in eligible_token_slot_ids)
    if any(not slot_id for slot_id in requested) or len(requested) != len(set(requested)):
        raise ValueError("eligible token-slot identities must be distinct and non-empty")
    if not set(requested).issubset(set(candidate_ids)):
        raise ValueError("eligible token-slot identity is not owned by this campaign")
    return (candidate_ids[0], candidate_ids[1]), set(requested)


def _campaign_slot_identity_rows(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
) -> list[sqlite3.Row]:
    rows = connection.execute(
        """SELECT token_slot_id,token_row_id,pair_row_id,mint_identity,pair_identity,
                  lifecycle_identity,slot_ordinal
           FROM printer_memory_factory_campaign_token_slots
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
           ORDER BY slot_ordinal""",
        (campaign_id, run_id, cycle_id),
    ).fetchall()
    if len(rows) != 2 or {int(row["slot_ordinal"]) for row in rows} != {1, 2}:
        raise ValueError("standard four-hour eligibility requires the exact two campaign slots")
    return list(rows)


def load_standard_four_hour_eligibility_manifests(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    factory_run_id: str,
) -> dict[str, dict[str, Any]] | None:
    """Return the exact durable two-slot standard-4h manifest, or None if absent."""
    slot_rows = _campaign_slot_identity_rows(
        connection,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
    )
    close_by_slot: dict[str, sqlite3.Row] = {}
    present: dict[str, dict[str, Any]] = {}
    for slot in slot_rows:
        slot_id = str(slot["token_slot_id"])
        closes = connection.execute(
            """SELECT id,token_id,pair_id,tracking_lane,memory_window_id,result_json
               FROM printer_memory_factory_run_steps
               WHERE run_id=? AND token_id=? AND pair_id=?
                 AND step_kind='CONTINUATION_CLOSE' AND step_status='SUCCEEDED'
               ORDER BY id""",
            (factory_run_id, int(slot["token_row_id"]), int(slot["pair_row_id"])),
        ).fetchall()
        if len(closes) > 1:
            raise ValueError(f"ambiguous successful first-hour close for {slot_id}")
        if not closes:
            continue
        close = closes[0]
        close_by_slot[slot_id] = close
        try:
            payload = json.loads(str(close["result_json"] or "{}"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid first-hour close result JSON for {slot_id}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"invalid first-hour close result payload for {slot_id}")
        manifest = payload.get("standard_four_hour_eligibility")
        if manifest is not None:
            if not isinstance(manifest, dict):
                raise ValueError(f"invalid standard four-hour eligibility manifest for {slot_id}")
            present[slot_id] = dict(manifest)

    if not present:
        return None
    if len(present) != 2 or set(present) != {str(row["token_slot_id"]) for row in slot_rows}:
        raise ValueError("partial standard four-hour eligibility manifest")

    for slot in slot_rows:
        slot_id = str(slot["token_slot_id"])
        if slot_id not in close_by_slot:
            raise ValueError(f"missing successful first-hour close for manifest slot {slot_id}")
        manifest = present[slot_id]
        eligible = manifest.get("eligible")
        expected_verdict = "CONTINUE_TO_WINDOW_4H" if eligible is True else "BLOCK_CONTINUATION"
        if type(eligible) is not bool:
            raise ValueError(f"invalid eligibility boolean for {slot_id}")
        if (
            str(manifest.get("contract_version"))
            != STANDARD_FOUR_HOUR_ELIGIBILITY_CONTRACT_VERSION
            or str(manifest.get("campaign_id")) != str(campaign_id)
            or str(manifest.get("campaign_run_id")) != str(run_id)
            or str(manifest.get("cycle_id")) != str(cycle_id)
            or str(manifest.get("token_slot_id")) != slot_id
            or int(manifest.get("token_id", -1)) != int(slot["token_row_id"])
            or int(manifest.get("pair_id", -1)) != int(slot["pair_row_id"])
            or str(manifest.get("verdict")) != expected_verdict
        ):
            raise ValueError(f"standard four-hour eligibility manifest identity mismatch for {slot_id}")
    return present


def _persist_standard_four_hour_eligibility_manifests(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    factory_run_id: str,
    candidates: Sequence[Mapping[str, Any]],
    eligible_ids: set[str],
) -> dict[str, dict[str, Any]]:
    slot_rows = _campaign_slot_identity_rows(
        connection,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
    )
    slot_by_id = {str(row["token_slot_id"]): row for row in slot_rows}
    candidate_ids = {str(candidate["token_slot_id"]) for candidate in candidates}
    if candidate_ids != set(slot_by_id):
        raise ValueError("standard four-hour manifest candidates do not cover exact campaign slots")

    for candidate in candidates:
        slot_id = str(candidate["token_slot_id"])
        slot = slot_by_id[slot_id]
        token_id = int(candidate["token_row_id"])
        pair_id = int(candidate["pair_row_id"])
        lane = str(candidate["tracking_lane"])
        memory_window_id = int(candidate["memory_window_1h_id"])
        if (
            int(slot["token_row_id"]) != token_id
            or int(slot["pair_row_id"]) != pair_id
            or str(slot["mint_identity"]) != str(candidate["mint_identity"])
            or str(slot["pair_identity"]) != str(candidate["pair_identity"])
            or str(slot["lifecycle_identity"]) != str(candidate["lifecycle_identity"])
        ):
            raise ValueError(f"standard four-hour manifest slot identity mismatch for {slot_id}")
        closes = connection.execute(
            """SELECT id,token_id,pair_id,tracking_lane,memory_window_id,result_json
               FROM printer_memory_factory_run_steps
               WHERE run_id=? AND token_id=? AND pair_id=? AND tracking_lane=?
                 AND step_kind='CONTINUATION_CLOSE' AND step_status='SUCCEEDED'
               ORDER BY id""",
            (factory_run_id, token_id, pair_id, lane),
        ).fetchall()
        if len(closes) != 1:
            raise ValueError(f"exact successful first-hour close missing/ambiguous for {slot_id}")
        close = closes[0]
        if close["memory_window_id"] is None or int(close["memory_window_id"]) != memory_window_id:
            raise ValueError(f"first-hour close memory identity mismatch for {slot_id}")
        try:
            payload = json.loads(str(close["result_json"] or "{}"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid first-hour close result JSON for {slot_id}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"invalid first-hour close result payload for {slot_id}")
        eligible = slot_id in eligible_ids
        manifest = {
            "contract_version": STANDARD_FOUR_HOUR_ELIGIBILITY_CONTRACT_VERSION,
            "campaign_id": str(campaign_id),
            "campaign_run_id": str(run_id),
            "cycle_id": str(cycle_id),
            "token_slot_id": slot_id,
            "token_id": token_id,
            "pair_id": pair_id,
            "verdict": "CONTINUE_TO_WINDOW_4H" if eligible else "BLOCK_CONTINUATION",
            "eligible": eligible,
        }
        existing = payload.get("standard_four_hour_eligibility")
        if existing is not None and existing != manifest:
            raise ValueError(f"standard four-hour eligibility manifest conflict for {slot_id}")
        if existing is None:
            payload["standard_four_hour_eligibility"] = manifest
            connection.execute(
                "UPDATE printer_memory_factory_run_steps SET result_json=?,updated_at=? WHERE id=?",
                (json.dumps(payload, sort_keys=True), datetime.now(timezone.utc).isoformat(), int(close["id"])),
            )

    loaded = load_standard_four_hour_eligibility_manifests(
        connection,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        factory_run_id=factory_run_id,
    )
    if loaded is None:
        raise ValueError("standard four-hour eligibility manifest write disappeared")
    actual_eligible = {slot_id for slot_id, manifest in loaded.items() if manifest["eligible"] is True}
    if actual_eligible != eligible_ids:
        raise ValueError("standard four-hour eligibility manifest subset mismatch")
    return loaded


def _standard_campaign_4h_plan_state(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    factory_run_id: str,
    candidates: Sequence[Mapping[str, Any]],
    eligible_token_slot_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    candidate_order, eligible_ids = _normalize_standard_4h_eligible_slots(
        candidates, eligible_token_slot_ids
    )
    manifests = load_standard_four_hour_eligibility_manifests(
        connection,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        factory_run_id=factory_run_id,
    )
    if manifests is None:
        raise ValueError("standard four-hour plan is missing durable eligibility manifest")
    manifest_eligible = {slot_id for slot_id, manifest in manifests.items() if manifest["eligible"] is True}
    if manifest_eligible != eligible_ids:
        raise ValueError("standard four-hour requested subset differs from durable manifest")

    planned_by_slot: dict[str, int] = {}
    total_expected = 0
    for candidate in candidates:
        slot_id = str(candidate["token_slot_id"])
        token_id = int(candidate["token_row_id"])
        pair_id = int(candidate["pair_row_id"])
        lane = str(candidate["tracking_lane"])
        window_id = str(candidate["campaign_window_4h_id"])
        if slot_id not in eligible_ids:
            window_count = int(connection.execute(
                """SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
                   WHERE campaign_id=? AND run_id=? AND cycle_id=? AND token_slot_id=?
                     AND window_kind='WINDOW_4H'""",
                (campaign_id, run_id, cycle_id, slot_id),
            ).fetchone()[0])
            step_count = int(connection.execute(
                """SELECT COUNT(*) FROM printer_memory_factory_run_steps
                   WHERE run_id=? AND token_id=? AND pair_id=? AND tracking_lane=?
                     AND step_kind LIKE 'LONG_CONTINUATION_%'""",
                (factory_run_id, token_id, pair_id, lane),
            ).fetchone()[0])
            owned_count = int(connection.execute(
                """SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
                   WHERE campaign_id=? AND run_id=? AND cycle_id=? AND token_slot_id=?
                     AND factory_run_id=? AND ownership_contract_version='V2_STAGE_SCOPED'
                     AND work_scope='WINDOW_LIFECYCLE' AND stage_id='WINDOW_4H'""",
                (campaign_id, run_id, cycle_id, slot_id, factory_run_id),
            ).fetchone()[0])
            slot = connection.execute(
                """SELECT token_state FROM printer_memory_factory_campaign_token_slots
                   WHERE campaign_id=? AND run_id=? AND cycle_id=? AND token_slot_id=?""",
                (campaign_id, run_id, cycle_id, slot_id),
            ).fetchone()
            if (
                window_count != 0
                or step_count != 0
                or owned_count != 0
                or slot is None
                or str(slot[0]) == "WINDOW_4H_CONTINUING"
            ):
                raise ValueError(f"ineligible slot has partial four-hour state: {slot_id}")
            continue

        policy = get_policy(WINDOW_KIND, lane)
        if policy is None:
            raise ValueError(f"missing WINDOW_4H policy for {lane}")
        expected = int(policy.minimum_required_snapshots)
        total_expected += expected
        planned_by_slot[slot_id] = expected
        window = connection.execute(
            """SELECT window_state,memory_window_row_id
               FROM printer_memory_factory_campaign_windows
               WHERE campaign_id=? AND run_id=? AND cycle_id=? AND token_slot_id=?
                 AND window_id=? AND window_kind='WINDOW_4H'""",
            (campaign_id, run_id, cycle_id, slot_id, window_id),
        ).fetchone()
        if window is None or str(window[0]) != "PLANNED" or window[1] is not None:
            raise ValueError(f"incomplete four-hour campaign window for {slot_id}")
        slot = connection.execute(
            """SELECT token_state FROM printer_memory_factory_campaign_token_slots
               WHERE campaign_id=? AND run_id=? AND cycle_id=? AND token_slot_id=?""",
            (campaign_id, run_id, cycle_id, slot_id),
        ).fetchone()
        if slot is None or str(slot[0]) != "WINDOW_4H_CONTINUING":
            raise ValueError(f"incomplete four-hour slot state for {slot_id}")
        step_rows = connection.execute(
            """SELECT step_kind,scheduler_job_id
               FROM printer_memory_factory_run_steps
               WHERE run_id=? AND token_id=? AND pair_id=? AND tracking_lane=?
                 AND step_kind LIKE 'LONG_CONTINUATION_%'""",
            (factory_run_id, token_id, pair_id, lane),
        ).fetchall()
        if (
            len(step_rows) != expected
            or sum(1 for row in step_rows if str(row[0]) == "LONG_CONTINUATION_CLOSE") != 1
            or any(row[1] is None for row in step_rows)
            or len({int(row[1]) for row in step_rows}) != expected
        ):
            raise ValueError(f"incomplete four-hour run-step plan for {slot_id}")
        ownership_count = int(connection.execute(
            """SELECT COUNT(*)
               FROM printer_memory_factory_campaign_scheduler_work AS cw
               JOIN printer_memory_factory_run_steps AS rs
                 ON rs.scheduler_job_id=cw.scheduler_job_id
               WHERE cw.campaign_id=? AND cw.run_id=? AND cw.cycle_id=?
                 AND cw.token_slot_id=? AND cw.window_id=?
                 AND cw.ownership_contract_version='V2_STAGE_SCOPED'
                 AND cw.work_scope='WINDOW_LIFECYCLE' AND cw.stage_id='WINDOW_4H'
                 AND cw.target_category='CAMPAIGN_WINDOW'
                 AND cw.target_identity=cw.window_id AND cw.factory_run_id=?
                 AND rs.run_id=? AND rs.token_id=? AND rs.pair_id=?
                 AND rs.tracking_lane=? AND cw.work_intent=rs.step_kind
                 AND rs.step_kind LIKE 'LONG_CONTINUATION_%'""",
            (
                campaign_id, run_id, cycle_id, slot_id, window_id, factory_run_id,
                factory_run_id, token_id, pair_id, lane,
            ),
        ).fetchone()[0])
        if ownership_count != expected:
            raise ValueError(f"incomplete four-hour Scheduler ownership for {slot_id}")

    total_windows = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
           WHERE campaign_id=? AND run_id=? AND cycle_id=? AND window_kind='WINDOW_4H'""",
        (campaign_id, run_id, cycle_id),
    ).fetchone()[0])
    total_steps = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_run_steps
           WHERE run_id=? AND step_kind LIKE 'LONG_CONTINUATION_%'""",
        (factory_run_id,),
    ).fetchone()[0])
    total_owned = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
           WHERE campaign_id=? AND run_id=? AND cycle_id=? AND factory_run_id=?
             AND ownership_contract_version='V2_STAGE_SCOPED'
             AND work_scope='WINDOW_LIFECYCLE' AND stage_id='WINDOW_4H'""",
        (campaign_id, run_id, cycle_id, factory_run_id),
    ).fetchone()[0])
    if (
        total_windows != len(eligible_ids)
        or total_steps != total_expected
        or total_owned != total_expected
    ):
        raise ValueError("partial_or_ambiguous_standard_four_hour_plan")
    later = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
             AND window_kind IN ('WINDOW_12H','WINDOW_24H')""",
        (campaign_id, run_id, cycle_id),
    ).fetchone()[0])
    if later:
        raise ValueError("standard four-hour plan must not create 12h/24h windows")
    return {
        "planned_by_slot": planned_by_slot,
        "planned_jobs": total_expected,
        "continuation_count": len(eligible_ids),
        "no_op": len(eligible_ids) == 0,
        "eligible_token_slot_ids": [slot for slot in candidate_order if slot in eligible_ids],
    }


def plan_standard_campaign_4h_handoff(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    factory_run_id: str,
    candidates: Sequence[Mapping[str, Any]],
    eligible_token_slot_ids: Sequence[str] | None = None,
    execution_authority: FourHourExecutionAuthority | str = FourHourExecutionAuthority.DISABLED,
    now: str | None = None,
) -> dict[str, Any]:
    """Compose the exact eligible subset of the standard two-slot 4h campaign."""
    try:
        authority = FourHourExecutionAuthority(execution_authority)
    except ValueError as exc:
        raise ValueError("invalid standard four-hour execution authority") from exc
    if authority != FourHourExecutionAuthority.STANDARD_CAMPAIGN:
        raise ValueError(
            "standard four-hour campaign planning requires explicit STANDARD_CAMPAIGN authority"
        )
    candidate_order, eligible_ids = _normalize_standard_4h_eligible_slots(
        candidates, eligible_token_slot_ids
    )
    campaign_run = connection.execute(
        """SELECT authoritative_run_id FROM printer_memory_factory_campaign_runs
           WHERE campaign_id=? AND run_id=?""",
        (campaign_id, run_id),
    ).fetchone()
    if (
        campaign_run is None
        or campaign_run[0] is None
        or str(campaign_run[0]) != str(factory_run_id)
    ):
        raise ValueError("campaign run/factory run identity mismatch")

    lanes = tuple(str(candidate["tracking_lane"]) for candidate in candidates)
    mask = tuple(slot_id in eligible_ids for slot_id in candidate_order)
    budget = standard_campaign_lifecycle_budget(
        (lanes[0], lanes[1]), (bool(mask[0]), bool(mask[1]))
    )
    existing_manifests = load_standard_four_hour_eligibility_manifests(
        connection,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        factory_run_id=factory_run_id,
    )
    existing_windows = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
           WHERE campaign_id=? AND run_id=? AND cycle_id=? AND window_kind='WINDOW_4H'""",
        (campaign_id, run_id, cycle_id),
    ).fetchone()[0])
    existing_steps = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_run_steps
           WHERE run_id=? AND step_kind LIKE 'LONG_CONTINUATION_%'""",
        (factory_run_id,),
    ).fetchone()[0])
    existing_owned = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
           WHERE campaign_id=? AND run_id=? AND cycle_id=? AND factory_run_id=?
             AND stage_id='WINDOW_4H' AND work_scope='WINDOW_LIFECYCLE'""",
        (campaign_id, run_id, cycle_id, factory_run_id),
    ).fetchone()[0])

    if existing_manifests is not None:
        manifest_eligible = {
            slot_id for slot_id, manifest in existing_manifests.items()
            if manifest["eligible"] is True
        }
        if manifest_eligible != eligible_ids:
            raise ValueError("requested standard four-hour subset differs from durable manifest")
        verified = _standard_campaign_4h_plan_state(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            factory_run_id=factory_run_id,
            candidates=candidates,
            eligible_token_slot_ids=tuple(eligible_ids),
        )
        return {"planned": True, "replay": True, **verified, "budget": budget}

    if existing_windows or existing_steps or existing_owned:
        raise ValueError("partial_or_ambiguous_standard_four_hour_plan_without_manifest")
    if connection.in_transaction:
        raise ValueError(
            "standard four-hour campaign planning requires a clean transaction boundary"
        )

    planned_by_slot: dict[str, int] = {}
    timestamp = now or datetime.now(timezone.utc).isoformat()
    connection.execute("BEGIN")
    try:
        _persist_standard_four_hour_eligibility_manifests(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            factory_run_id=factory_run_id,
            candidates=candidates,
            eligible_ids=eligible_ids,
        )
        handoff = campaign_ownership.persist_standard_four_hour_handoff_set(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            candidates=candidates,
            eligible_token_slot_ids=tuple(eligible_ids),
            now=timestamp,
        )
        if not handoff.get("persisted") or handoff.get("replay"):
            raise ValueError("fresh subset composition requires a fresh B1 handoff")

        for candidate in candidates:
            slot_id = str(candidate["token_slot_id"])
            if slot_id not in eligible_ids:
                continue
            window_id = str(candidate["campaign_window_4h_id"])
            token_id = int(candidate["token_row_id"])
            pair_id = int(candidate["pair_row_id"])
            lane = str(candidate["tracking_lane"])
            plan = _plan_token_4h_phase(
                connection,
                run_id=factory_run_id,
                token_id=token_id,
                pair_id=pair_id,
                token_mint=str(candidate["mint_identity"]),
                pair_address=str(candidate["pair_identity"]),
                tracking_lane=lane,
                cumulative_scheduler_ceiling=int(budget["scheduler_ceiling"]),
                allow_enabled_successor_planning=True,
            )
            if not plan.get("planned") or plan.get("replay"):
                raise ValueError(
                    "standard four-hour token plan failed: "
                    + ";".join(str(item) for item in plan.get("blocked_reasons", []))
                )
            planned_by_slot[slot_id] = int(plan["planned_jobs"])
            for step in plan["steps"]:
                job_id = int(step["scheduler_job_id"])
                campaign_ownership.project_campaign_scheduler_job(
                    connection,
                    scheduler_work_id=(
                        f"campaign4h:{campaign_id}:{run_id}:{cycle_id}:"
                        f"{slot_id}:{job_id}"
                    ),
                    campaign_id=campaign_id,
                    run_id=run_id,
                    cycle_id=cycle_id,
                    token_slot_id=slot_id,
                    window_id=window_id,
                    factory_run_id=factory_run_id,
                    work_intent=str(step["step_kind"]),
                    deadline_at=str(step["scheduled_for"]),
                    scheduler_job_id=job_id,
                    stage_id="WINDOW_4H",
                    target_category="CAMPAIGN_WINDOW",
                    target_identity=window_id,
                    now=timestamp,
                )
        verified = _standard_campaign_4h_plan_state(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            factory_run_id=factory_run_id,
            candidates=candidates,
            eligible_token_slot_ids=tuple(eligible_ids),
        )
        if verified["planned_by_slot"] != planned_by_slot:
            raise ValueError("standard four-hour planned-slot read-back mismatch")
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
    return {"planned": True, "replay": False, **verified, "budget": budget}

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


def reconcile_4h_terminal_lifecycle(
    connection: sqlite3.Connection,
    *,
    campaign_window_4h_id: str,
    terminal_state: str,
    terminal_cause: str,
    memory_window_row_id: int,
    now: str | None = None,
) -> dict[str, Any]:
    """Bind and terminalize one successful campaign WINDOW_4H without committing its caller."""
    desired = str(terminal_state)
    allowed = {
        "CLEAN_PROMOTED", "DIRTY", "NO_PROMOTION", "ALREADY_EXISTS_IDEMPOTENT"
    }
    if desired not in allowed:
        raise ValueError(f"unsupported successful WINDOW_4H terminal state: {desired}")
    cause = str(terminal_cause).strip()
    if not cause:
        raise ValueError("WINDOW_4H successful terminal cause must be non-empty")
    timestamp = str(now or _iso(datetime.now(timezone.utc)))
    memory_id = int(memory_window_row_id)
    started_outer = False
    if not connection.in_transaction:
        connection.execute("BEGIN")
        started_outer = True
    savepoint = "printer_window_4h_success_terminal"
    connection.execute(f"SAVEPOINT {savepoint}")
    try:
        window = connection.execute(
            """SELECT * FROM printer_memory_factory_campaign_windows
               WHERE window_id=? AND window_kind='WINDOW_4H'""",
            (str(campaign_window_4h_id),),
        ).fetchone()
        if window is None:
            raise ValueError("WINDOW_4H successful campaign window missing")
        slot = connection.execute(
            """SELECT * FROM printer_memory_factory_campaign_token_slots
               WHERE token_slot_id=? AND campaign_id=? AND run_id=? AND cycle_id=?""",
            (
                str(window["token_slot_id"]), str(window["campaign_id"]),
                str(window["run_id"]), str(window["cycle_id"]),
            ),
        ).fetchone()
        if slot is None:
            raise ValueError("WINDOW_4H successful token slot missing")
        if (
            int(slot["token_row_id"]) != int(window["token_row_id"])
            or int(slot["pair_row_id"]) != int(window["pair_row_id"])
        ):
            raise ValueError("WINDOW_4H successful slot token/pair mismatch")
        memory = connection.execute(
            """SELECT token_id,pair_id,window_kind FROM printer_memory_windows WHERE id=?""",
            (memory_id,),
        ).fetchone()
        if (
            memory is None
            or int(memory["token_id"]) != int(window["token_row_id"])
            or int(memory["pair_id"]) != int(window["pair_row_id"])
            or str(memory["window_kind"]) != "WINDOW_4H"
        ):
            raise ValueError("WINDOW_4H successful physical memory identity mismatch")

        window_state = str(window["window_state"])
        slot_state = str(slot["token_state"])
        existing_memory = window["memory_window_row_id"]
        if window_state in allowed:
            if not (
                window_state == desired
                and existing_memory is not None
                and int(existing_memory) == memory_id
                and str(window["first_terminal_cause"] or "") == cause
                and window["terminal_at"] is not None
                and slot_state == "WINDOW_4H_CLOSED"
                and slot["first_terminal_cause"] is None
                and slot["terminal_at"] is None
            ):
                raise ValueError("conflicting successful WINDOW_4H terminal replay")
            connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            return {
                "window_id": str(window["window_id"]),
                "window_state": desired,
                "token_state": "WINDOW_4H_CLOSED",
                "memory_window_row_id": memory_id,
                "terminal_cause": cause,
                "idempotent": True,
            }
        if window_state != "CLOSE_PENDING":
            raise ValueError(
                f"successful WINDOW_4H requires CLOSE_PENDING, found {window_state}"
            )
        if slot_state != "WINDOW_4H_CONTINUING":
            raise ValueError(
                f"successful WINDOW_4H requires WINDOW_4H_CONTINUING, found {slot_state}"
            )
        if window["first_terminal_cause"] is not None or slot["first_terminal_cause"] is not None:
            raise ValueError("successful WINDOW_4H has conflicting first terminal cause")
        if existing_memory is not None and int(existing_memory) != memory_id:
            raise ValueError("successful WINDOW_4H memory row already bound differently")

        auditing = connection.execute(
            """UPDATE printer_memory_factory_campaign_windows
               SET memory_window_row_id=?,window_state='AUDITING',updated_at=?
               WHERE window_id=? AND window_state='CLOSE_PENDING'
                 AND first_terminal_cause IS NULL
                 AND (memory_window_row_id IS NULL OR memory_window_row_id=?)""",
            (memory_id, timestamp, str(window["window_id"]), memory_id),
        )
        if auditing.rowcount != 1:
            raise ValueError("WINDOW_4H successful bind/auditing compare-and-update failed")
        terminal = connection.execute(
            """UPDATE printer_memory_factory_campaign_windows
               SET window_state=?,first_terminal_cause=?,terminal_at=?,updated_at=?
               WHERE window_id=? AND window_state='AUDITING'
                 AND memory_window_row_id=? AND first_terminal_cause IS NULL""",
            (desired, cause, timestamp, timestamp, str(window["window_id"]), memory_id),
        )
        if terminal.rowcount != 1:
            raise ValueError("WINDOW_4H successful terminal compare-and-update failed")
        slot_update = connection.execute(
            """UPDATE printer_memory_factory_campaign_token_slots
               SET token_state='WINDOW_4H_CLOSED',updated_at=?
               WHERE token_slot_id=? AND campaign_id=? AND run_id=? AND cycle_id=?
                 AND token_state='WINDOW_4H_CONTINUING'
                 AND first_terminal_cause IS NULL AND terminal_at IS NULL""",
            (
                timestamp, str(window["token_slot_id"]), str(window["campaign_id"]),
                str(window["run_id"]), str(window["cycle_id"]),
            ),
        )
        if slot_update.rowcount != 1:
            raise ValueError("WINDOW_4H successful slot compare-and-update failed")
        verify = connection.execute(
            """SELECT w.window_state,w.memory_window_row_id,w.first_terminal_cause,
                      w.terminal_at,s.token_state,s.first_terminal_cause,s.terminal_at
               FROM printer_memory_factory_campaign_windows AS w
               JOIN printer_memory_factory_campaign_token_slots AS s
                 ON s.token_slot_id=w.token_slot_id
                AND s.campaign_id=w.campaign_id
                AND s.run_id=w.run_id
                AND s.cycle_id=w.cycle_id
               WHERE w.window_id=?""",
            (str(window["window_id"]),),
        ).fetchone()
        if not (
            verify is not None
            and str(verify[0]) == desired
            and int(verify[1]) == memory_id
            and str(verify[2]) == cause
            and verify[3] is not None
            and str(verify[4]) == "WINDOW_4H_CLOSED"
            and verify[5] is None
            and verify[6] is None
        ):
            raise ValueError("WINDOW_4H successful terminal read-back mismatch")
        connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        return {
            "window_id": str(window["window_id"]),
            "window_state": desired,
            "token_state": "WINDOW_4H_CLOSED",
            "memory_window_row_id": memory_id,
            "terminal_cause": cause,
            "idempotent": False,
        }
    except Exception:
        connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        if started_outer and connection.in_transaction:
            connection.rollback()
        raise

from pathlib import Path


campaign_path = Path('src/printer_v1/operator_cli/campaign_ownership.py')
campaign = campaign_path.read_text()
if 'from contextlib import nullcontext\n' not in campaign:
    campaign = campaign.replace(
        'from __future__ import annotations\n\n',
        'from __future__ import annotations\n\nfrom contextlib import nullcontext\n',
        1,
    )
old_transaction = '''    try:\n        with connection:\n            existing = connection.execute(\n'''
new_transaction = '''    try:\n        transaction_context = (\n            connection if not connection.in_transaction else nullcontext(connection)\n        )\n        with transaction_context:\n            existing = connection.execute(\n'''
if old_transaction not in campaign:
    raise SystemExit('campaign projection transaction marker missing')
campaign = campaign.replace(old_transaction, new_transaction, 1)
campaign_path.write_text(campaign)


runtime_path = Path('src/printer_v1/operator_cli/one_token_4h_runtime.py')
runtime = runtime_path.read_text()
runtime = runtime.replace(
    'from typing import Any, Mapping\n',
    'from typing import Any, Mapping, Sequence\n',
    1,
)
if 'from printer_v1.operator_cli import campaign_ownership\n' not in runtime:
    runtime = runtime.replace(
        'from printer_v1.scheduler.contracts import JobKind, LockResult\n',
        'from printer_v1.operator_cli import campaign_ownership\n'
        'from printer_v1.scheduler.contracts import JobKind, LockResult\n',
        1,
    )
start = runtime.index('def _step_count(')
end = runtime.index('\ndef close_current_run_4h(', start)
replacement = r'''def _step_count(connection: sqlite3.Connection, run_id: str) -> int:
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
    explicit_proof_mode: bool = False,
    compressed_two_token_proof: bool = False,
    cumulative_scheduler_ceiling: int | None = None,
) -> dict[str, Any]:
    """Plan the exact policy-derived 4h jobs from this run's terminal 1h row."""
    if not explicit_proof_mode:
        return {
            "planned": False,
            "blocked_reasons": ["WINDOW_4H real collection remains disabled"],
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
    )


def _standard_campaign_4h_plan_state(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    factory_run_id: str,
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    planned_by_slot: dict[str, int] = {}
    total_expected = 0
    for candidate in candidates:
        slot_id = str(candidate["token_slot_id"])
        token_id = int(candidate["token_row_id"])
        pair_id = int(candidate["pair_row_id"])
        lane = str(candidate["tracking_lane"])
        window_id = str(candidate["campaign_window_4h_id"])
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
        if (
            window is None
            or str(window[0]) != "PLANNED"
            or window[1] is not None
        ):
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
                 AND cw.work_scope='WINDOW_LIFECYCLE'
                 AND cw.stage_id='WINDOW_4H'
                 AND cw.target_category='CAMPAIGN_WINDOW'
                 AND cw.target_identity=cw.window_id
                 AND cw.factory_run_id=?
                 AND rs.run_id=? AND rs.token_id=? AND rs.pair_id=?
                 AND rs.tracking_lane=? AND cw.work_intent=rs.step_kind
                 AND rs.step_kind LIKE 'LONG_CONTINUATION_%'""",
            (
                campaign_id,
                run_id,
                cycle_id,
                slot_id,
                window_id,
                factory_run_id,
                factory_run_id,
                token_id,
                pair_id,
                lane,
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
    if total_windows != 2 or total_steps != total_expected or total_owned != total_expected:
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
    }


def plan_standard_campaign_4h_handoff(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    factory_run_id: str,
    candidates: Sequence[Mapping[str, Any]],
    now: str | None = None,
) -> dict[str, Any]:
    """Atomically compose B1 ownership, two-token 4h planning and Scheduler ownership.

    This is offline campaign integration only. It does not enable real 4h
    collection, perform source work, or create any 12h/24h successor.
    """
    if len(candidates) != 2:
        raise ValueError("standard four-hour campaign requires exactly two candidates")
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
    budget = standard_two_token_lifecycle_budget((lanes[0], lanes[1]))
    if bool(budget["real_collection_enabled"]):
        raise ValueError("B2 must not enable real WINDOW_4H collection")

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
    if existing_windows or existing_steps or existing_owned:
        verified = _standard_campaign_4h_plan_state(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            factory_run_id=factory_run_id,
            candidates=candidates,
        )
        return {
            "planned": True,
            "replay": True,
            **verified,
            "budget": budget,
        }

    planned_by_slot: dict[str, int] = {}
    timestamp = now or datetime.now(timezone.utc).isoformat()
    with connection:
        handoff = campaign_ownership.persist_standard_four_hour_handoff_set(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            candidates=candidates,
            now=timestamp,
        )
        if not handoff.get("persisted") or handoff.get("replay"):
            raise ValueError("fresh B2 composition requires a fresh B1 handoff")
        for candidate in candidates:
            slot_id = str(candidate["token_slot_id"])
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
        )
        if verified["planned_by_slot"] != planned_by_slot:
            raise ValueError("standard four-hour planned-slot read-back mismatch")
    return {
        "planned": True,
        "replay": False,
        **verified,
        "budget": budget,
    }

'''
runtime = runtime[:start] + replacement + runtime[end:]
runtime_path.write_text(runtime)

from pathlib import Path

path = Path("src/printer_v1/operator_cli/one_command_15m_factory.py")
text = path.read_text(encoding="utf-8")

plan_start = text.index("def _plan_continuation_jobs(\n")
plan_end = text.index("\ndef _evidence_duration_seconds(", plan_start)
plan_function = '''def _plan_continuation_jobs(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    close_step: sqlite3.Row,
    fifteen_m: dict[str, Any],
    continuation_seconds: float,
    ownership_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Enqueue one exact-target 45m continuation from a current-run 15m close.

    When the current V2-9.8B campaign supplies ``ownership_context``, every
    created continuation Scheduler job is immediately projected onto the exact
    Checkpoint-1 WINDOW_1H campaign successor through the canonical campaign
    Scheduler-ownership owner. Historical fixture-only callers may omit it.
    """
    from printer_v1.snapshots.lifecycle_continuity import build_1h_continuation_plan

    plan = build_1h_continuation_plan(fifteen_m)
    if not plan.get("enqueue_ok"):
        return {**plan, "planned_jobs": 0}
    close_at = datetime.fromisoformat(str(plan["enqueue_at"]))
    target = {
        "token_id": int(close_step["token_id"]),
        "pair_id": int(close_step["pair_id"]),
        "token_mint": str(close_step["token_mint"]),
        "pair_address": str(close_step["pair_address"]),
        "tracking_lane": str(close_step["tracking_lane"]),
    }
    prefix = _token_prefix(str(close_step["step_key"]))
    expected = _continuation_expected_snapshots(target["tracking_lane"])

    ownership: dict[str, str] | None = None
    if ownership_context is not None:
        required = (
            "campaign_id",
            "campaign_run_id",
            "cycle_id",
            "token_slot_id",
            "campaign_window_1h_id",
            "factory_run_id",
        )
        ownership = {
            key: str(ownership_context.get(key) or "")
            for key in required
        }
        missing = [key for key, value in ownership.items() if not value]
        if missing:
            raise ValueError(
                "continuation Scheduler ownership context missing: "
                + ",".join(missing)
            )
        if ownership["factory_run_id"] != str(run_id):
            raise ValueError("continuation Scheduler ownership factory-run mismatch")

    def insert_owned_job(*, step_key: str, step_kind: str, scheduled_for: datetime) -> int:
        job_id = _insert_step_and_job(
            conn,
            run_id=run_id,
            target=target,
            step_key=step_key,
            step_kind=step_kind,
            scheduled_for=scheduled_for,
        )
        if ownership is not None:
            from printer_v1.operator_cli.campaign_ownership import (
                project_campaign_scheduler_job,
            )

            project_campaign_scheduler_job(
                conn,
                scheduler_work_id=(
                    f"cw1h:{ownership['campaign_id']}:{ownership['campaign_run_id']}:"
                    f"{ownership['cycle_id']}:{ownership['token_slot_id']}:"
                    f"{ownership['campaign_window_1h_id']}:{job_id}"
                ),
                campaign_id=ownership["campaign_id"],
                run_id=ownership["campaign_run_id"],
                cycle_id=ownership["cycle_id"],
                token_slot_id=ownership["token_slot_id"],
                window_id=ownership["campaign_window_1h_id"],
                factory_run_id=ownership["factory_run_id"],
                work_intent=f"WINDOW_1H_{step_kind}",
                deadline_at=_iso(scheduled_for),
                scheduler_job_id=int(job_id),
                stage_id="WINDOW_1H",
                target_category="CAMPAIGN_WINDOW",
                target_identity=ownership["campaign_window_1h_id"],
                work_state="PENDING",
            )
        return int(job_id)

    for index in range(expected - 1):
        offset = continuation_seconds * index / (expected - 1)
        insert_owned_job(
            step_key=f"{prefix}_continuation_snapshot_{index:02d}",
            step_kind="CONTINUATION_SNAPSHOT",
            scheduled_for=close_at + timedelta(seconds=offset),
        )
    insert_owned_job(
        step_key=f"{prefix}_continuation_close",
        step_kind="CONTINUATION_CLOSE",
        scheduled_for=close_at + timedelta(seconds=continuation_seconds),
    )
    return {**plan, "planned_jobs": expected, "expected_snapshots": expected}
'''
text = text[:plan_start] + plan_function + text[plan_end:]

select_start = text.index("def _selective_1h_schedule_for_close(\n")
select_end = text.index("\ndef _natural_disposition_schedule(", select_start)
select_function = '''def _selective_1h_schedule_for_close(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    close_step: sqlite3.Row,
    window_id: int,
    continuation_seconds: float,
    evaluation: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Enqueue first-hour work only from an exact Checkpoint-1 successor."""
    from printer_v1.operator_cli.operational_selective_1h import should_continue_token

    token_id = int(close_step["token_id"])
    plan = next(
        (
            p
            for p in evaluation.get("token_plans") or ()
            if int(p["token_row_id"]) == token_id
        ),
        None,
    )
    if plan is None:
        raise ValueError(f"missing standard-first-hour token plan for token {token_id}")
    if not should_continue_token(evaluation, token_id=token_id):
        return (
            {
                "captured": False,
                "verdict": "VALID_NO_CAPTURE",
                "reason": plan.get("verdict", "STOP_OR_BLOCK"),
                "window_5m_id": None,
            },
            {
                "enqueue_ok": False,
                "planned_jobs": 0,
                "verdict": plan.get("verdict", "STOP_AFTER_WINDOW_15M"),
                "reason": ";".join(plan.get("reasons") or ["selective_stop"]),
            },
        )

    campaign_window_1h_id = str(plan.get("campaign_window_1h_id") or "")
    token_slot_id = str(plan.get("token_slot_id") or "")
    campaign_id = str(evaluation.get("campaign_id") or "")
    campaign_run_id = str(evaluation.get("run_id") or "")
    cycle_id = str(evaluation.get("cycle_id") or "")
    predecessor_window_id = str(plan.get("campaign_window_15m_id") or "")
    if not all(
        (
            campaign_window_1h_id,
            token_slot_id,
            campaign_id,
            campaign_run_id,
            cycle_id,
            predecessor_window_id,
        )
    ):
        raise ValueError("continuing token lacks exact WINDOW_1H ownership identity")

    successor = conn.execute(
        """SELECT w.campaign_id,w.run_id,w.cycle_id,w.token_slot_id,
                  w.token_row_id,w.pair_row_id,w.window_kind,w.window_state,
                  w.predecessor_window_id,w.memory_window_row_id,s.token_state
           FROM printer_memory_factory_campaign_windows AS w
           JOIN printer_memory_factory_campaign_token_slots AS s
             ON s.token_slot_id=w.token_slot_id
            AND s.campaign_id=w.campaign_id
            AND s.run_id=w.run_id
            AND s.cycle_id=w.cycle_id
           WHERE w.window_id=?""",
        (campaign_window_1h_id,),
    ).fetchone()
    expected_successor = (
        campaign_id,
        campaign_run_id,
        cycle_id,
        token_slot_id,
        token_id,
        int(close_step["pair_id"]),
        "WINDOW_1H",
        "PLANNED",
        predecessor_window_id,
    )
    if successor is None or tuple(successor[:9]) != expected_successor:
        raise ValueError("exact WINDOW_1H campaign successor identity mismatch")
    if successor[9] is not None:
        raise ValueError("WINDOW_1H successor already bound to a memory row before collection")
    if str(successor[10]) != "WINDOW_1H_CONTINUING":
        raise ValueError("token slot is not in WINDOW_1H_CONTINUING at initialization")

    support = _capture_same_stream_5m_support(
        conn,
        run_id=run_id,
        close_step=close_step,
        parent_window_id=int(window_id),
    )
    source = _resolve_current_run_15m_source(
        conn,
        run_id=run_id,
        token_id=token_id,
        pair_id=int(close_step["pair_id"]),
        tracking_lane=str(close_step["tracking_lane"]),
        current_close_step_id=int(close_step["id"]),
    )
    if not source.get("resolved"):
        raise ValueError(
            "current-run 15m continuation source blocked: "
            + "; ".join(source.get("reasons", []))
        )
    continuation_plan = _plan_continuation_jobs(
        conn,
        run_id=run_id,
        close_step=close_step,
        fifteen_m=source["window"],
        continuation_seconds=continuation_seconds,
        ownership_context={
            "campaign_id": campaign_id,
            "campaign_run_id": campaign_run_id,
            "cycle_id": cycle_id,
            "token_slot_id": token_slot_id,
            "campaign_window_1h_id": campaign_window_1h_id,
            "factory_run_id": str(run_id),
        },
    )
    if not continuation_plan.get("enqueue_ok"):
        raise ValueError(
            "continuation planning blocked: "
            + "; ".join(continuation_plan.get("reasons", []))
        )
    continuation_plan["verdict"] = "CONTINUE_TO_WINDOW_1H"
    continuation_plan["selective_1h"] = True
    continuation_plan["campaign_window_1h_id"] = campaign_window_1h_id
    continuation_plan["token_slot_id"] = token_slot_id
    return support, continuation_plan
'''
text = text[:select_start] + select_function + text[select_end:]

path.write_text(text, encoding="utf-8")

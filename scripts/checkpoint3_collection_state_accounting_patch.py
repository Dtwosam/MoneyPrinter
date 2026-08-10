from pathlib import Path

path = Path("src/printer_v1/operator_cli/one_command_15m_factory.py")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one patch anchor, found {count}: {old[:100]!r}")
    text = text.replace(old, new, 1)


helper_anchor = "\ndef _observe_scheduler_terminal(\n"
helpers = r'''

def _owned_campaign_scheduler_row(
    conn: sqlite3.Connection, *, scheduler_job_id: int,
) -> sqlite3.Row | None:
    """Resolve at most one V2 stage-scoped campaign owner for a Scheduler job."""
    rows = conn.execute(
        """SELECT * FROM printer_memory_factory_campaign_scheduler_work
           WHERE scheduler_job_id=?
             AND ownership_contract_version='V2_STAGE_SCOPED'
           ORDER BY scheduler_work_id""",
        (int(scheduler_job_id),),
    ).fetchall()
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError(
            f"campaign Scheduler ownership is ambiguous for job {scheduler_job_id}"
        )
    return rows[0]


def _sync_owned_campaign_scheduler_job(
    conn: sqlite3.Connection, *, scheduler_job_id: int,
) -> str | None:
    """Synchronize an existing campaign projection from canonical Scheduler truth."""
    row = _owned_campaign_scheduler_row(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if row is None:
        # Historical/non-campaign lifecycle callers have no V2 projection.
        return None
    if (
        str(row["work_scope"]) != "WINDOW_LIFECYCLE"
        or str(row["target_category"]) != "CAMPAIGN_WINDOW"
        or row["token_slot_id"] is None
        or row["window_id"] is None
        or row["factory_run_id"] is None
    ):
        raise ValueError("owned lifecycle Scheduler row has invalid immutable scope")
    from printer_v1.operator_cli.campaign_ownership import (
        project_campaign_scheduler_job,
    )

    projected = project_campaign_scheduler_job(
        conn,
        scheduler_work_id=str(row["scheduler_work_id"]),
        campaign_id=str(row["campaign_id"]),
        run_id=str(row["run_id"]),
        cycle_id=str(row["cycle_id"]),
        token_slot_id=str(row["token_slot_id"]),
        window_id=str(row["window_id"]),
        factory_run_id=str(row["factory_run_id"]),
        work_intent=str(row["work_intent"]),
        deadline_at=str(row["deadline_at"]),
        scheduler_job_id=int(scheduler_job_id),
        stage_id=str(row["stage_id"]),
        target_category=str(row["target_category"]),
        target_identity=str(row["target_identity"]),
        source_request_id=(
            int(row["source_request_id"])
            if row["source_request_id"] is not None else None
        ),
        source_response_id=(
            int(row["source_response_id"])
            if row["source_response_id"] is not None else None
        ),
        source_failure_id=(
            int(row["source_failure_id"])
            if row["source_failure_id"] is not None else None
        ),
    )
    return str(projected.work_state)


def _owned_continuation_window_for_job(
    conn: sqlite3.Connection, *, scheduler_job_id: int,
) -> sqlite3.Row | None:
    """Resolve the exact WINDOW_1H campaign window owned by one continuation job."""
    owner = _owned_campaign_scheduler_row(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if owner is None:
        return None
    if (
        str(owner["work_scope"]) != "WINDOW_LIFECYCLE"
        or str(owner["stage_id"]) != "WINDOW_1H"
        or str(owner["target_category"]) != "CAMPAIGN_WINDOW"
        or owner["window_id"] is None
        or str(owner["target_identity"]) != str(owner["window_id"])
    ):
        raise ValueError("continuation Scheduler ownership is not exact WINDOW_1H")
    rows = conn.execute(
        """SELECT * FROM printer_memory_factory_campaign_windows
           WHERE window_id=? AND campaign_id=? AND run_id=? AND cycle_id=?
             AND token_slot_id=? AND window_kind='WINDOW_1H'""",
        (
            str(owner["window_id"]), str(owner["campaign_id"]),
            str(owner["run_id"]), str(owner["cycle_id"]),
            str(owner["token_slot_id"]),
        ),
    ).fetchall()
    if len(rows) != 1:
        raise ValueError("owned continuation job has no unique exact WINDOW_1H")
    return rows[0]


def _mark_owned_continuation_window_collecting(
    conn: sqlite3.Connection, *, scheduler_job_id: int, step_kind: str,
) -> str | None:
    """Advance the exact first-hour window when real continuation collection starts."""
    if str(step_kind) != "CONTINUATION_SNAPSHOT":
        return None
    window = _owned_continuation_window_for_job(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if window is None:
        return None
    state = str(window["window_state"])
    if state == "COLLECTING":
        return state
    if state != "PLANNED":
        raise ValueError(
            f"WINDOW_1H collection state conflict: expected PLANNED/COLLECTING, found {state}"
        )
    from printer_v1.operator_cli.campaign_ownership import transition_state

    transitioned = transition_state(
        conn,
        record_kind="window",
        identity=str(window["window_id"]),
        expected_state="PLANNED",
        new_state="COLLECTING",
    )
    return str(transitioned.current_state)


def _terminalize_owned_continuation_window(
    conn: sqlite3.Connection,
    *,
    scheduler_job_id: int,
    terminal_state: str,
    terminal_cause: str,
) -> str | None:
    """Fail closed one exact first-hour campaign window without touching its peer."""
    window = _owned_continuation_window_for_job(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if window is None:
        return None
    from printer_v1.operator_cli.campaign_ownership import transition_state

    transitioned = transition_state(
        conn,
        record_kind="window",
        identity=str(window["window_id"]),
        expected_state=str(window["window_state"]),
        new_state=str(terminal_state),
        terminal_cause=str(terminal_cause),
    )
    return str(transitioned.current_state)


def _cancel_owned_continuation_windows_for_run(
    conn: sqlite3.Connection, *, factory_run_id: str, terminal_cause: str,
) -> int:
    """Cancel only nonterminal owned WINDOW_1H windows after a run-wide stop."""
    rows = conn.execute(
        """SELECT DISTINCT w.window_id, w.window_state
           FROM printer_memory_factory_campaign_scheduler_work AS sw
           JOIN printer_memory_factory_campaign_windows AS w
             ON w.window_id=sw.window_id
           WHERE sw.factory_run_id=?
             AND sw.ownership_contract_version='V2_STAGE_SCOPED'
             AND sw.work_scope='WINDOW_LIFECYCLE'
             AND sw.stage_id='WINDOW_1H'
             AND w.window_kind='WINDOW_1H'
           ORDER BY w.window_id""",
        (str(factory_run_id),),
    ).fetchall()
    active_states = {"PLANNED", "COLLECTING", "CLOSE_PENDING", "AUDITING"}
    changed = 0
    if not rows:
        return changed
    from printer_v1.operator_cli.campaign_ownership import transition_state

    for row in rows:
        state = str(row["window_state"])
        if state not in active_states:
            continue
        transition_state(
            conn,
            record_kind="window",
            identity=str(row["window_id"]),
            expected_state=state,
            new_state="CANCELLED",
            terminal_cause=str(terminal_cause),
        )
        changed += 1
    return changed


def _lifecycle_reservation_records_for_step(
    *, run_id: str, pending: sqlite3.Row, projected_requests: int,
) -> list[dict[str, Any]]:
    """Build verification-only reservation identities for lifecycle source work."""
    step_kind = str(pending["step_kind"])
    if step_kind not in {
        "SNAPSHOT", "WINDOW_CLOSE", "CONTINUATION_SNAPSHOT", "CONTINUATION_CLOSE"
    }:
        return []
    records: list[dict[str, Any]] = []
    for reservation_index in range(int(projected_requests)):
        if step_kind == "WINDOW_CLOSE":
            family = (
                "CLOSE_OBSERVATION"
                if reservation_index == 0 else "PRECLOSE_CONTEXT"
            )
        elif step_kind == "SNAPSHOT":
            family = "SNAPSHOT_OBSERVATION"
        elif step_kind == "CONTINUATION_SNAPSHOT":
            family = "CONTINUATION_SNAPSHOT_OBSERVATION"
        else:
            family = "CONTINUATION_CLOSE_OBSERVATION"
        records.append(
            {
                "boundary": "LIFECYCLE_RESERVATION",
                "run_id": str(run_id),
                "scheduler_job_id": int(pending["scheduler_job_id"]),
                "step_key": str(pending["step_key"]),
                "step_kind": step_kind,
                "token_id": int(pending["token_id"]),
                "pair_id": int(pending["pair_id"]),
                "reservation_ordinal": (
                    int(pending["scheduler_job_id"]) * 100 + reservation_index
                ),
                "operation_family": family,
            }
        )
    return records
'''
if helper_anchor not in text:
    raise SystemExit("helper insertion anchor missing")
text = text.replace(helper_anchor, helpers + helper_anchor, 1)

replace_once(
'''        if row["scheduler_job_id"] is not None:
            cancel_job(conn, job_id=int(row["scheduler_job_id"]))
        conn.execute(
            "UPDATE printer_memory_factory_run_steps SET step_status='CANCELLED', error_or_skip_reason=?, finished_at=?, updated_at=? WHERE id=?",
            (reason, _iso(), _iso(), int(row["id"])),
        )
''',
'''        if row["scheduler_job_id"] is not None:
            cancel_job(conn, job_id=int(row["scheduler_job_id"]))
            _sync_owned_campaign_scheduler_job(
                conn, scheduler_job_id=int(row["scheduler_job_id"])
            )
        conn.execute(
            "UPDATE printer_memory_factory_run_steps SET step_status='CANCELLED', error_or_skip_reason=?, finished_at=?, updated_at=? WHERE id=?",
            (reason, _iso(), _iso(), int(row["id"])),
        )
'''
)

replace_once(
'''        if row["scheduler_job_id"] is not None:
            cancel_job(conn, job_id=int(row["scheduler_job_id"]))
        conn.execute(
            "UPDATE printer_memory_factory_run_steps SET step_status='CANCELLED', error_or_skip_reason=?, finished_at=?, updated_at=? WHERE id=?",
            (reason, _iso(), _iso(), int(row["id"])),
        )
    return len(rows)
''',
'''        if row["scheduler_job_id"] is not None:
            cancel_job(conn, job_id=int(row["scheduler_job_id"]))
            _sync_owned_campaign_scheduler_job(
                conn, scheduler_job_id=int(row["scheduler_job_id"])
            )
        conn.execute(
            "UPDATE printer_memory_factory_run_steps SET step_status='CANCELLED', error_or_skip_reason=?, finished_at=?, updated_at=? WHERE id=?",
            (reason, _iso(), _iso(), int(row["id"])),
        )
    return len(rows)
'''
)

replace_once(
'''            conn.execute(
                "UPDATE printer_memory_factory_run_steps SET step_status='RUNNING',started_at=?,updated_at=? WHERE id=?",
                (_iso(), _iso(), int(pending["id"])),
            )
            conn.commit()
''',
'''            conn.execute(
                "UPDATE printer_memory_factory_run_steps SET step_status='RUNNING',started_at=?,updated_at=? WHERE id=?",
                (_iso(), _iso(), int(pending["id"])),
            )
            _sync_owned_campaign_scheduler_job(
                conn, scheduler_job_id=job_id
            )
            _mark_owned_continuation_window_collecting(
                conn,
                scheduler_job_id=job_id,
                step_kind=str(pending["step_kind"]),
            )
            conn.commit()
'''
)

start = text.index("                reservation_records: list[dict[str, Any]] = []\n")
end = text.index('                if pending["step_kind"] == "WINDOW_CLOSE":\n', start)
reservation_block = '''                reservation_records = _lifecycle_reservation_records_for_step(
                    run_id=run_id,
                    pending=pending,
                    projected_requests=_projected_requests_for_step(pending),
                )
                if lifecycle_operation_observer is not None:
                    for reservation_record in reservation_records:
                        lifecycle_operation_observer(reservation_record)
'''
text = text[:start] + reservation_block + text[end:]

replace_once(
'''                    complete_job(conn, job_id=job_id)
                    _observe_scheduler_terminal(
''',
'''                    complete_job(conn, job_id=job_id)
                    _sync_owned_campaign_scheduler_job(
                        conn, scheduler_job_id=job_id
                    )
                    _observe_scheduler_terminal(
'''
)

replace_once(
'''                    fail_job(conn, job_id=job_id, error=error, max_retries=0)
                    _observe_scheduler_terminal(
                        conn, observer=lifecycle_operation_observer,
                        run_id=run_id, step=pending,
                    )
                    _cancel_pending_for_token(conn, run_id, token_id, TOKEN_LOCAL_CANCELLED)
                    conn.commit()
''',
'''                    fail_job(conn, job_id=job_id, error=error, max_retries=0)
                    _sync_owned_campaign_scheduler_job(
                        conn, scheduler_job_id=job_id
                    )
                    _observe_scheduler_terminal(
                        conn, observer=lifecycle_operation_observer,
                        run_id=run_id, step=pending,
                    )
                    _cancel_pending_for_token(conn, run_id, token_id, TOKEN_LOCAL_CANCELLED)
                    if str(pending["step_kind"]) == "CONTINUATION_SNAPSHOT":
                        _terminalize_owned_continuation_window(
                            conn,
                            scheduler_job_id=job_id,
                            terminal_state="BLOCKED",
                            terminal_cause=error,
                        )
                    conn.commit()
'''
)

replace_once(
'''                fail_job(conn, job_id=job_id, error=gstop.reason, max_retries=0)
                _observe_scheduler_terminal(
''',
'''                fail_job(conn, job_id=job_id, error=gstop.reason, max_retries=0)
                _sync_owned_campaign_scheduler_job(
                    conn, scheduler_job_id=job_id
                )
                _observe_scheduler_terminal(
'''
)

replace_once(
'''                fail_job(conn, job_id=job_id, error=result["exception"], max_retries=0)
                _observe_scheduler_terminal(
                    conn, observer=lifecycle_operation_observer,
                    run_id=run_id, step=pending,
                )
                _cancel_pending_for_token(conn, run_id, token_id, TOKEN_LOCAL_CANCELLED)
                conn.commit()
''',
'''                fail_job(conn, job_id=job_id, error=result["exception"], max_retries=0)
                _sync_owned_campaign_scheduler_job(
                    conn, scheduler_job_id=job_id
                )
                _observe_scheduler_terminal(
                    conn, observer=lifecycle_operation_observer,
                    run_id=run_id, step=pending,
                )
                _cancel_pending_for_token(conn, run_id, token_id, TOKEN_LOCAL_CANCELLED)
                if str(pending["step_kind"]) == "CONTINUATION_SNAPSHOT":
                    _terminalize_owned_continuation_window(
                        conn,
                        scheduler_job_id=job_id,
                        terminal_state="BLOCKED",
                        terminal_cause=result["exception"],
                    )
                conn.commit()
'''
)

replace_once(
'''        _cancel_pending(conn, run_id, stop_reason)
        discovery_cleanup = _cancel_campaign_discovery_jobs(
''',
'''        _cancel_pending(conn, run_id, stop_reason)
        if stop_reason != STOP_COMPLETED:
            _cancel_owned_continuation_windows_for_run(
                conn,
                factory_run_id=run_id,
                terminal_cause=stop_reason,
            )
        discovery_cleanup = _cancel_campaign_discovery_jobs(
'''
)

path.write_text(text, encoding="utf-8")

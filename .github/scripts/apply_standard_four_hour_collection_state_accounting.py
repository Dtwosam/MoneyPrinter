from pathlib import Path

path = Path('src/printer_v1/operator_cli/one_command_15m_factory.py')
text = path.read_text()

# 1. Generalize exact lifecycle-window resolution while preserving first-hour wrapper.
start = text.index('def _owned_continuation_window_for_job(')
end = text.index('\ndef _mark_owned_continuation_window_collecting(', start)
resolver = r'''def _owned_lifecycle_window_for_job(
    conn: sqlite3.Connection,
    *,
    scheduler_job_id: int,
    expected_stage: str,
    expected_window_kind: str,
) -> sqlite3.Row | None:
    """Resolve one exact campaign lifecycle window for a V2 stage-scoped job."""
    owner = _owned_campaign_scheduler_row(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if owner is None:
        return None
    if (
        str(owner["work_scope"]) != "WINDOW_LIFECYCLE"
        or str(owner["stage_id"]) != str(expected_stage)
        or str(owner["target_category"]) != "CAMPAIGN_WINDOW"
        or owner["token_slot_id"] is None
        or owner["window_id"] is None
        or owner["factory_run_id"] is None
        or str(owner["target_identity"]) != str(owner["window_id"])
    ):
        raise ValueError(
            f"lifecycle Scheduler ownership is not exact {expected_stage}"
        )
    rows = conn.execute(
        """SELECT * FROM printer_memory_factory_campaign_windows
           WHERE window_id=? AND campaign_id=? AND run_id=? AND cycle_id=?
             AND token_slot_id=? AND window_kind=?""",
        (
            str(owner["window_id"]),
            str(owner["campaign_id"]),
            str(owner["run_id"]),
            str(owner["cycle_id"]),
            str(owner["token_slot_id"]),
            str(expected_window_kind),
        ),
    ).fetchall()
    if len(rows) != 1:
        raise ValueError(
            f"owned lifecycle job has no unique exact {expected_window_kind}"
        )
    return rows[0]


def _owned_continuation_window_for_job(
    conn: sqlite3.Connection, *, scheduler_job_id: int,
) -> sqlite3.Row | None:
    """Resolve the exact WINDOW_1H campaign window owned by one continuation job."""
    return _owned_lifecycle_window_for_job(
        conn,
        scheduler_job_id=int(scheduler_job_id),
        expected_stage="WINDOW_1H",
        expected_window_kind="WINDOW_1H",
    )


def _owned_long_window_for_job(
    conn: sqlite3.Connection, *, scheduler_job_id: int,
) -> sqlite3.Row | None:
    """Resolve the exact WINDOW_4H campaign window owned by one long job."""
    return _owned_lifecycle_window_for_job(
        conn,
        scheduler_job_id=int(scheduler_job_id),
        expected_stage="WINDOW_4H",
        expected_window_kind="WINDOW_4H",
    )

'''
text = text[:start] + resolver + text[end:]

# 2. Add exact 4h claim-state helpers before first-hour terminal classification.
marker = '\ndef _classify_owned_1h_terminal_state('
long_state_helpers = r'''

def _mark_owned_long_window_collecting(
    conn: sqlite3.Connection, *, scheduler_job_id: int, step_kind: str,
) -> str | None:
    """Advance the exact four-hour window when long collection actually starts."""
    if str(step_kind) != "LONG_CONTINUATION_SNAPSHOT":
        return None
    window = _owned_long_window_for_job(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if window is None:
        return None
    state = str(window["window_state"])
    if state == "COLLECTING":
        return state
    if state != "PLANNED":
        raise ValueError(
            f"WINDOW_4H collection state conflict: expected PLANNED/COLLECTING, found {state}"
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


def _mark_owned_long_window_close_pending(
    conn: sqlite3.Connection, *, scheduler_job_id: int, step_kind: str,
) -> str | None:
    """Advance the exact four-hour window when its long close job is claimed."""
    if str(step_kind) != "LONG_CONTINUATION_CLOSE":
        return None
    window = _owned_long_window_for_job(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if window is None:
        return None
    state = str(window["window_state"])
    if state == "CLOSE_PENDING":
        return state
    if state != "COLLECTING":
        raise ValueError(
            "WINDOW_4H close state conflict: expected COLLECTING/CLOSE_PENDING, "
            f"found {state}"
        )
    from printer_v1.operator_cli.campaign_ownership import transition_state

    transitioned = transition_state(
        conn,
        record_kind="window",
        identity=str(window["window_id"]),
        expected_state="COLLECTING",
        new_state="CLOSE_PENDING",
    )
    return str(transitioned.current_state)

'''
if marker not in text:
    raise SystemExit('first-hour terminal classification marker missing')
text = text.replace(marker, long_state_helpers + marker, 1)

# 3. Add 4h failure/cancel lifecycle terminal owner before shared cleanup.
marker = '\ndef _cancel_owned_continuation_windows_for_run('
long_terminal = r'''

def _terminalize_owned_long_window(
    conn: sqlite3.Connection,
    *,
    scheduler_job_id: int,
    terminal_state: str,
    terminal_cause: str,
) -> str | None:
    """Fail/cancel one exact four-hour lifecycle without touching its peer."""
    desired_window = str(terminal_state)
    desired_slot = {
        "BLOCKED": "FAILED",
        "CANCELLED": "MANUAL_REVIEW",
    }.get(desired_window)
    if desired_slot is None:
        raise ValueError(f"unsupported WINDOW_4H collection terminal state: {desired_window}")
    cause = str(terminal_cause).strip()
    if not cause:
        raise ValueError("WINDOW_4H terminal cause must be non-empty")
    window = _owned_long_window_for_job(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if window is None:
        return None
    timestamp = _iso()
    savepoint = "printer_window_4h_collection_terminal"
    conn.execute(f"SAVEPOINT {savepoint}")
    try:
        current_window = conn.execute(
            """SELECT campaign_id,run_id,cycle_id,token_slot_id,token_row_id,
                      pair_row_id,window_state,first_terminal_cause,terminal_at
               FROM printer_memory_factory_campaign_windows WHERE window_id=?""",
            (str(window["window_id"]),),
        ).fetchone()
        if current_window is None:
            raise ValueError("WINDOW_4H terminal window disappeared")
        slot = conn.execute(
            """SELECT token_state,first_terminal_cause,terminal_at,token_row_id,pair_row_id
               FROM printer_memory_factory_campaign_token_slots
               WHERE token_slot_id=? AND campaign_id=? AND run_id=? AND cycle_id=?""",
            (
                str(current_window["token_slot_id"]),
                str(current_window["campaign_id"]),
                str(current_window["run_id"]),
                str(current_window["cycle_id"]),
            ),
        ).fetchone()
        if slot is None:
            raise ValueError("WINDOW_4H terminal token slot missing")
        if (
            int(slot["token_row_id"]) != int(current_window["token_row_id"])
            or int(slot["pair_row_id"]) != int(current_window["pair_row_id"])
        ):
            raise ValueError("WINDOW_4H terminal token/pair identity mismatch")
        window_state = str(current_window["window_state"])
        slot_state = str(slot["token_state"])
        if window_state == desired_window or slot_state == desired_slot:
            if not (
                window_state == desired_window
                and slot_state == desired_slot
                and str(current_window["first_terminal_cause"] or "") == cause
                and str(slot["first_terminal_cause"] or "") == cause
                and current_window["terminal_at"] is not None
                and slot["terminal_at"] is not None
            ):
                raise ValueError("conflicting WINDOW_4H terminal replay")
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
            return desired_window
        if window_state not in {"PLANNED", "COLLECTING", "CLOSE_PENDING", "AUDITING"}:
            raise ValueError(f"WINDOW_4H cannot terminalize from {window_state}")
        if slot_state != "WINDOW_4H_CONTINUING":
            raise ValueError(f"WINDOW_4H slot cannot terminalize from {slot_state}")
        window_update = conn.execute(
            """UPDATE printer_memory_factory_campaign_windows
               SET window_state=?,first_terminal_cause=?,terminal_at=?,updated_at=?
               WHERE window_id=? AND window_state=? AND first_terminal_cause IS NULL""",
            (
                desired_window,
                cause,
                timestamp,
                timestamp,
                str(window["window_id"]),
                window_state,
            ),
        )
        if window_update.rowcount != 1:
            raise ValueError("WINDOW_4H terminal compare-and-update failed")
        slot_update = conn.execute(
            """UPDATE printer_memory_factory_campaign_token_slots
               SET token_state=?,first_terminal_cause=?,terminal_at=?,updated_at=?
               WHERE token_slot_id=? AND token_state='WINDOW_4H_CONTINUING'
                 AND first_terminal_cause IS NULL""",
            (
                desired_slot,
                cause,
                timestamp,
                timestamp,
                str(current_window["token_slot_id"]),
            ),
        )
        if slot_update.rowcount != 1:
            raise ValueError("WINDOW_4H slot terminal compare-and-update failed")
        verify = conn.execute(
            """SELECT w.window_state,w.first_terminal_cause,s.token_state,s.first_terminal_cause
               FROM printer_memory_factory_campaign_windows AS w
               JOIN printer_memory_factory_campaign_token_slots AS s
                 ON s.token_slot_id=w.token_slot_id
               WHERE w.window_id=?""",
            (str(window["window_id"]),),
        ).fetchone()
        if (
            verify is None
            or str(verify[0]) != desired_window
            or str(verify[1]) != cause
            or str(verify[2]) != desired_slot
            or str(verify[3]) != cause
        ):
            raise ValueError("WINDOW_4H terminal read-back mismatch")
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        return desired_window
    except Exception:
        conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise

'''
if marker not in text:
    raise SystemExit('shared cleanup marker missing')
text = text.replace(marker, long_terminal + marker, 1)

# 4. Generalize shared cleanup across the proven 1h stage plus 4h collection stage.
start = text.index('def _cancel_owned_continuation_windows_for_run(')
end = text.index('\ndef _lifecycle_reservation_records_for_step(', start)
cleanup = r'''def _cancel_owned_continuation_windows_for_run(
    conn: sqlite3.Connection, *, factory_run_id: str, terminal_cause: str,
) -> int:
    """Cancel nonterminal owned WINDOW_1H and WINDOW_4H lifecycles after shared stop."""
    rows = conn.execute(
        """SELECT w.window_id,w.window_state,w.window_kind,sw.stage_id,
                  MIN(sw.scheduler_job_id) AS scheduler_job_id
           FROM printer_memory_factory_campaign_scheduler_work AS sw
           JOIN printer_memory_factory_campaign_windows AS w
             ON w.window_id=sw.window_id
           WHERE sw.factory_run_id=?
             AND sw.ownership_contract_version='V2_STAGE_SCOPED'
             AND sw.work_scope='WINDOW_LIFECYCLE'
             AND (
                 (sw.stage_id='WINDOW_1H' AND w.window_kind='WINDOW_1H')
                 OR
                 (sw.stage_id='WINDOW_4H' AND w.window_kind='WINDOW_4H')
             )
           GROUP BY w.window_id,w.window_state,w.window_kind,sw.stage_id
           ORDER BY w.window_id""",
        (str(factory_run_id),),
    ).fetchall()
    active_states = {"PLANNED", "COLLECTING", "CLOSE_PENDING", "AUDITING"}
    changed = 0
    if not rows:
        return changed
    from printer_v1.operator_cli.operational_selective_1h import (
        reconcile_1h_terminal_lifecycle,
    )

    for row in rows:
        state = str(row["window_state"])
        if state not in active_states:
            continue
        if str(row["window_kind"]) == "WINDOW_1H":
            reconcile_1h_terminal_lifecycle(
                conn,
                campaign_window_1h_id=str(row["window_id"]),
                terminal_state="CANCELLED",
                terminal_cause=str(terminal_cause),
            )
        elif str(row["window_kind"]) == "WINDOW_4H":
            if row["scheduler_job_id"] is None:
                raise ValueError("WINDOW_4H shared cleanup has no Scheduler owner")
            _terminalize_owned_long_window(
                conn,
                scheduler_job_id=int(row["scheduler_job_id"]),
                terminal_state="CANCELLED",
                terminal_cause=str(terminal_cause),
            )
        else:
            raise ValueError("unsupported owned lifecycle window in shared cleanup")
        changed += 1
    return changed

'''
text = text[:start] + cleanup + text[end:]

# 5. Extend reservation observations to the existing long-step projected request counts.
start = text.index('def _lifecycle_reservation_records_for_step(')
end = text.index('\ndef _observe_scheduler_terminal(', start)
reservations = r'''def _lifecycle_reservation_records_for_step(
    *, run_id: str, pending: sqlite3.Row, projected_requests: int,
) -> list[dict[str, Any]]:
    """Build verification-only reservation identities for lifecycle source work."""
    step_kind = str(pending["step_kind"])
    supported = {
        "SNAPSHOT",
        "WINDOW_CLOSE",
        "CONTINUATION_SNAPSHOT",
        "CONTINUATION_CLOSE",
        "LONG_CONTINUATION_SNAPSHOT",
        "LONG_CONTINUATION_CLOSE",
    }
    if step_kind not in supported:
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
        elif step_kind == "CONTINUATION_CLOSE":
            family = "CONTINUATION_CLOSE_OBSERVATION"
        elif step_kind == "LONG_CONTINUATION_CLOSE":
            family = "LONG_CONTINUATION_CLOSE_OBSERVATION"
        elif str(pending["step_key"]).endswith("_snapshot_000"):
            family = "LONG_CONTINUATION_OPENING_OBSERVATION"
        else:
            family = "LONG_CONTINUATION_SNAPSHOT_OBSERVATION"
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
text = text[:start] + reservations + text[end:]

# 6. Add categorical exact-WINDOW_4H fairness selector before the factory entry point.
entry = text.index('def run_one_command_15m_factory(')
selector = r'''def _select_next_pending_step(
    conn: sqlite3.Connection, *, run_id: str, now: datetime,
) -> sqlite3.Row | None:
    """Select the next step, adding categorical fairness only for exact owned 4h work."""
    fallback = conn.execute(
        """SELECT s.* FROM printer_memory_factory_run_steps AS s
           WHERE s.run_id=? AND s.step_status='PENDING'
           ORDER BY s.scheduled_for,s.id LIMIT 1""",
        (str(run_id),),
    ).fetchone()
    if fallback is None:
        return None
    due_at = datetime.fromisoformat(str(fallback["scheduled_for"]))
    if due_at > now:
        return fallback
    owner = _owned_campaign_scheduler_row(
        conn, scheduler_job_id=int(fallback["scheduler_job_id"])
    )
    if owner is None or not (
        str(owner["work_scope"]) == "WINDOW_LIFECYCLE"
        and str(owner["stage_id"]) == "WINDOW_4H"
        and str(owner["target_category"]) == "CAMPAIGN_WINDOW"
        and owner["window_id"] is not None
        and owner["token_slot_id"] is not None
        and owner["factory_run_id"] is not None
        and str(owner["factory_run_id"]) == str(run_id)
        and str(owner["target_identity"]) == str(owner["window_id"])
        and str(fallback["step_kind"]).startswith("LONG_CONTINUATION_")
    ):
        return fallback

    due_rows = conn.execute(
        """SELECT s.*,sw.window_id,sw.token_slot_id,slot.slot_ordinal,
                  j.id AS canonical_scheduler_job_id
           FROM printer_memory_factory_run_steps AS s
           JOIN printer_scheduler_jobs AS j ON j.id=s.scheduler_job_id
           JOIN printer_memory_factory_campaign_scheduler_work AS sw
             ON sw.scheduler_job_id=j.id
           JOIN printer_memory_factory_campaign_windows AS w
             ON w.window_id=sw.window_id
            AND w.campaign_id=sw.campaign_id
            AND w.run_id=sw.run_id
            AND w.cycle_id=sw.cycle_id
            AND w.token_slot_id=sw.token_slot_id
           JOIN printer_memory_factory_campaign_token_slots AS slot
             ON slot.token_slot_id=sw.token_slot_id
            AND slot.campaign_id=sw.campaign_id
            AND slot.run_id=sw.run_id
            AND slot.cycle_id=sw.cycle_id
           WHERE s.run_id=? AND s.step_status='PENDING'
             AND s.step_kind IN ('LONG_CONTINUATION_SNAPSHOT','LONG_CONTINUATION_CLOSE')
             AND j.status='PENDING' AND j.scheduled_for<=?
             AND sw.ownership_contract_version='V2_STAGE_SCOPED'
             AND sw.work_scope='WINDOW_LIFECYCLE'
             AND sw.stage_id='WINDOW_4H'
             AND sw.target_category='CAMPAIGN_WINDOW'
             AND sw.target_identity=sw.window_id
             AND sw.factory_run_id=s.run_id
             AND w.window_kind='WINDOW_4H'
           ORDER BY j.scheduled_for,j.id,slot.slot_ordinal""",
        (str(run_id), now.isoformat()),
    ).fetchall()
    if not due_rows:
        return fallback
    closes = [
        row for row in due_rows
        if str(row["step_kind"]) == "LONG_CONTINUATION_CLOSE"
    ]
    if closes:
        selected = min(
            closes,
            key=lambda row: (
                str(row["scheduled_for"]),
                int(row["canonical_scheduler_job_id"]),
                int(row["slot_ordinal"]),
            ),
        )
    else:
        service_counts: dict[str, int] = {}
        for row in due_rows:
            window_id = str(row["window_id"])
            if window_id not in service_counts:
                service_counts[window_id] = int(conn.execute(
                    """SELECT COUNT(DISTINCT j2.id)
                       FROM printer_memory_factory_campaign_scheduler_work AS sw2
                       JOIN printer_scheduler_jobs AS j2
                         ON j2.id=sw2.scheduler_job_id
                       JOIN printer_memory_factory_run_steps AS s2
                         ON s2.scheduler_job_id=j2.id
                       WHERE sw2.window_id=?
                         AND sw2.ownership_contract_version='V2_STAGE_SCOPED'
                         AND sw2.work_scope='WINDOW_LIFECYCLE'
                         AND sw2.stage_id='WINDOW_4H'
                         AND s2.run_id=?
                         AND s2.step_kind='LONG_CONTINUATION_SNAPSHOT'
                         AND j2.started_at IS NOT NULL""",
                    (window_id, str(run_id)),
                ).fetchone()[0])
        selected = min(
            due_rows,
            key=lambda row: (
                service_counts[str(row["window_id"])],
                int(row["canonical_scheduler_job_id"]),
                int(row["slot_ordinal"]),
            ),
        )
    selected_id = int(selected["id"])
    return conn.execute(
        "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
        (selected_id,),
    ).fetchone()


'''
text = text[:entry] + selector + text[entry:]

# 7. Route the main loop through the fairness-aware selector.
old_pending = '''            pending = conn.execute(
                "SELECT s.* FROM printer_memory_factory_run_steps s WHERE s.run_id=? AND s.step_status='PENDING' ORDER BY s.scheduled_for,s.id LIMIT 1",
                (run_id,),
            ).fetchone()
'''
new_pending = '''            pending = _select_next_pending_step(
                conn, run_id=run_id, now=_now()
            )
'''
if text.count(old_pending) != 1:
    raise SystemExit(f'pending selector marker count={text.count(old_pending)}')
text = text.replace(old_pending, new_pending, 1)

# 8. Wire long claim-state transitions alongside the already-proven first-hour hooks.
old_claim_hooks = '''            _mark_owned_continuation_window_close_pending(
                conn,
                scheduler_job_id=job_id,
                step_kind=str(pending["step_kind"]),
            )
            conn.commit()
'''
new_claim_hooks = '''            _mark_owned_continuation_window_close_pending(
                conn,
                scheduler_job_id=job_id,
                step_kind=str(pending["step_kind"]),
            )
            _mark_owned_long_window_collecting(
                conn,
                scheduler_job_id=job_id,
                step_kind=str(pending["step_kind"]),
            )
            _mark_owned_long_window_close_pending(
                conn,
                scheduler_job_id=job_id,
                step_kind=str(pending["step_kind"]),
            )
            conn.commit()
'''
if text.count(old_claim_hooks) != 1:
    raise SystemExit('claim hook marker missing/ambiguous')
text = text.replace(old_claim_hooks, new_claim_hooks, 1)

# 9. Extend both token-local failure branches to reconcile exact long lifecycle only.
old_terminal_block = '''                    if str(pending["step_kind"]) in {
                        "CONTINUATION_SNAPSHOT", "CONTINUATION_CLOSE"
                    }:
                        _terminalize_owned_continuation_window(
                            conn,
                            scheduler_job_id=job_id,
                            terminal_state="BLOCKED",
                            terminal_cause='''
# Patch each occurrence separately while preserving the existing terminal_cause expression.
occurrences = []
pos = 0
while True:
    pos = text.find(old_terminal_block, pos)
    if pos < 0:
        break
    occurrences.append(pos)
    pos += len(old_terminal_block)
if len(occurrences) != 2:
    raise SystemExit(f'expected 2 token-local terminal blocks, found {len(occurrences)}')
# Work from the end so offsets stay stable; insert an elif after each existing call block.
for pos in reversed(occurrences):
    call_start = pos
    # Locate the end of the existing _terminalize call by finding the next line with 24 spaces + ')' after terminal_cause.
    search_from = pos + len(old_terminal_block)
    call_end = text.find('\n                        )', search_from)
    if call_end < 0:
        raise SystemExit('terminalize call closing marker missing')
    call_end += len('\n                        )')
    existing = text[call_start:call_end]
    # Extract the terminal cause expression from the existing block after 'terminal_cause=' through before final close.
    cause_part = existing.split('terminal_cause=', 1)[1]
    cause_expr = cause_part.rsplit('\n                        )', 1)[0].strip()
    addition = (
        existing
        + '\n                    elif str(pending["step_kind"]).startswith("LONG_CONTINUATION_"):\n'
        + '                        _terminalize_owned_long_window(\n'
        + '                            conn,\n'
        + '                            scheduler_job_id=job_id,\n'
        + '                            terminal_state="BLOCKED",\n'
        + f'                            terminal_cause={cause_expr},\n'
        + '                        )'
    )
    text = text[:call_start] + addition + text[call_end:]

path.write_text(text)

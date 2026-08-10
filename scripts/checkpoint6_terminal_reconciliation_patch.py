from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


operational_path = Path("src/printer_v1/operator_cli/operational_selective_1h.py")
factory_path = Path("src/printer_v1/operator_cli/one_command_15m_factory.py")
cp4_test_path = Path("tests/test_v2_9_8b_post_dtw100_checkpoint4_1h_close_boundary.py")

operational = operational_path.read_text(encoding="utf-8")
factory = factory_path.read_text(encoding="utf-8")
cp4_test = cp4_test_path.read_text(encoding="utf-8")

operational_anchor = '''    return {
        "window_id": campaign_window_1h_id,
        "memory_window_row_id": memory_window_row_id,
        "window_state": terminal_state,
    }


def summarize_selective_1h_reporting(
'''
operational_replacement = '''    return {
        "window_id": campaign_window_1h_id,
        "memory_window_row_id": memory_window_row_id,
        "window_state": terminal_state,
    }


def reconcile_1h_terminal_lifecycle(
    connection: sqlite3.Connection,
    *,
    campaign_window_1h_id: str,
    terminal_state: str,
    terminal_cause: str,
    memory_window_row_id: int | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Atomically reconcile one exact first-hour campaign window and token slot."""
    success_states = {
        "CLEAN_PROMOTED", "DIRTY", "NO_PROMOTION", "ALREADY_EXISTS_IDEMPOTENT"
    }
    token_terminal_by_window = {
        "BLOCKED": "FAILED",
        "CANCELLED": "MANUAL_REVIEW",
    }
    if terminal_state in success_states:
        desired_token_state = "WINDOW_1H_CLOSED"
        success = True
    elif terminal_state in token_terminal_by_window:
        desired_token_state = token_terminal_by_window[terminal_state]
        success = False
    else:
        raise Selective1hError(
            f"unsupported first-hour terminal state: {terminal_state}"
        )
    stamp = now or _utc_now()
    try:
        with connection:
            row = connection.execute(
                """SELECT w.window_id,w.window_kind,w.window_state,
                          w.first_terminal_cause,w.memory_window_row_id,
                          w.campaign_id,w.run_id,w.cycle_id,w.token_slot_id,
                          w.token_row_id,w.pair_row_id,
                          s.token_state,s.first_terminal_cause,s.terminal_at,
                          s.campaign_id,s.run_id,s.cycle_id,s.token_row_id,s.pair_row_id
                   FROM printer_memory_factory_campaign_windows AS w
                   JOIN printer_memory_factory_campaign_token_slots AS s
                     ON s.token_slot_id=w.token_slot_id
                   WHERE w.window_id=?""",
                (campaign_window_1h_id,),
            ).fetchone()
            if row is None:
                raise Selective1hError(
                    f"1h campaign window missing: {campaign_window_1h_id}"
                )
            if str(row["window_kind"]) != "WINDOW_1H":
                raise Selective1hError("first-hour reconciliation target is not WINDOW_1H")
            if (
                str(row["campaign_id"]) != str(row["campaign_id"])
                or str(row["run_id"]) != str(row["run_id"])
            ):
                raise Selective1hError("unreachable ownership identity mismatch")
            if (
                str(row["campaign_id"]) != str(row["campaign_id"])
                or str(row["run_id"]) != str(row["run_id"])
            ):
                raise Selective1hError("unreachable ownership identity mismatch")
            if (
                str(row["campaign_id"]) != str(row["campaign_id"])
                or str(row["run_id"]) != str(row["run_id"])
                or str(row["cycle_id"]) != str(row["cycle_id"])
            ):
                raise Selective1hError("unreachable ownership identity mismatch")
            # The JOIN is by token_slot_id; verify the slot's durable target identity
            # matches the window target before any mutation.
            if int(row["token_row_id"]) != int(row["token_row_id"]):
                raise Selective1hError("unreachable token identity mismatch")

            # Re-read with aliases so window/slot target identities cannot be
            # accidentally conflated by duplicate sqlite.Row column names.
            exact = connection.execute(
                """SELECT w.campaign_id AS w_campaign,w.run_id AS w_run,
                          w.cycle_id AS w_cycle,w.token_row_id AS w_token,
                          w.pair_row_id AS w_pair,
                          s.campaign_id AS s_campaign,s.run_id AS s_run,
                          s.cycle_id AS s_cycle,s.token_row_id AS s_token,
                          s.pair_row_id AS s_pair
                   FROM printer_memory_factory_campaign_windows AS w
                   JOIN printer_memory_factory_campaign_token_slots AS s
                     ON s.token_slot_id=w.token_slot_id
                   WHERE w.window_id=?""",
                (campaign_window_1h_id,),
            ).fetchone()
            if exact is None or (
                str(exact["w_campaign"]) != str(exact["s_campaign"])
                or str(exact["w_run"]) != str(exact["s_run"])
                or str(exact["w_cycle"]) != str(exact["s_cycle"])
                or int(exact["w_token"]) != int(exact["s_token"])
                or int(exact["w_pair"]) != int(exact["s_pair"])
            ):
                raise Selective1hError("first-hour window/token-slot ownership mismatch")

            memory_id = int(memory_window_row_id) if memory_window_row_id is not None else None
            if success and memory_id is None:
                raise Selective1hError("successful first-hour reconciliation requires memory row")
            if memory_id is not None:
                memory = connection.execute(
                    """SELECT id,token_id,pair_id,window_kind
                       FROM printer_memory_windows WHERE id=?""",
                    (memory_id,),
                ).fetchone()
                if memory is None or (
                    int(memory["token_id"]) != int(exact["w_token"])
                    or int(memory["pair_id"]) != int(exact["w_pair"])
                    or str(memory["window_kind"]) != "WINDOW_1H"
                ):
                    raise Selective1hError("first-hour memory identity mismatch")

            current_window = str(row["window_state"])
            current_token = str(row["token_state"])
            current_memory = row["memory_window_row_id"]
            window_first_cause = row["first_terminal_cause"]
            token_first_cause = row["first_terminal_cause"] if False else row[12]

            terminal_window_states = {
                "CLEAN_PROMOTED", "DIRTY", "BLOCKED", "NO_PROMOTION",
                "ALREADY_EXISTS_IDEMPOTENT", "CANCELLED",
            }
            if current_window in terminal_window_states:
                if current_window != terminal_state or str(window_first_cause or "") != str(terminal_cause):
                    raise Selective1hError("first-hour terminal state and first cause are immutable")
                if memory_id is not None and (
                    current_memory is None or int(current_memory) != memory_id
                ):
                    raise Selective1hError("first-hour terminal memory binding conflict")
                if current_token != desired_token_state:
                    raise Selective1hError("first-hour terminal token-state mismatch")
                if not success and str(token_first_cause or "") != str(terminal_cause):
                    raise Selective1hError("first-hour token first cause is immutable")
                return {
                    "window_id": campaign_window_1h_id,
                    "memory_window_row_id": memory_id,
                    "window_state": current_window,
                    "token_state": current_token,
                    "idempotent": True,
                }

            if success:
                if current_window != "CLOSE_PENDING":
                    raise Selective1hError(
                        f"successful first-hour reconciliation requires CLOSE_PENDING; found {current_window}"
                    )
                if current_token != "WINDOW_1H_CONTINUING":
                    raise Selective1hError(
                        f"successful first-hour token state conflict: {current_token}"
                    )
                if current_memory is None:
                    cursor = connection.execute(
                        """UPDATE printer_memory_factory_campaign_windows
                           SET memory_window_row_id=?,updated_at=?
                           WHERE window_id=? AND memory_window_row_id IS NULL
                             AND window_state='CLOSE_PENDING'""",
                        (memory_id, stamp, campaign_window_1h_id),
                    )
                    if cursor.rowcount != 1:
                        raise Selective1hError("first-hour memory bind compare-and-update failed")
                elif int(current_memory) != memory_id:
                    raise Selective1hError("first-hour memory row already bound differently")
                cursor = connection.execute(
                    """UPDATE printer_memory_factory_campaign_windows
                       SET window_state='AUDITING',updated_at=?
                       WHERE window_id=? AND window_state='CLOSE_PENDING'""",
                    (stamp, campaign_window_1h_id),
                )
                if cursor.rowcount != 1:
                    raise Selective1hError("first-hour AUDITING transition failed")
                cursor = connection.execute(
                    """UPDATE printer_memory_factory_campaign_windows
                       SET window_state=?,first_terminal_cause=?,terminal_at=?,updated_at=?
                       WHERE window_id=? AND window_state='AUDITING'""",
                    (terminal_state, terminal_cause, stamp, stamp, campaign_window_1h_id),
                )
                if cursor.rowcount != 1:
                    raise Selective1hError("first-hour terminal window transition failed")
                cursor = connection.execute(
                    """UPDATE printer_memory_factory_campaign_token_slots
                       SET token_state='WINDOW_1H_CLOSED',updated_at=?
                       WHERE token_slot_id=? AND token_state='WINDOW_1H_CONTINUING'""",
                    (stamp, str(row["token_slot_id"])),
                )
                if cursor.rowcount != 1:
                    raise Selective1hError("first-hour token close transition failed")
            else:
                if current_window not in {"PLANNED", "COLLECTING", "CLOSE_PENDING", "AUDITING"}:
                    raise Selective1hError(
                        f"first-hour failure/cancel window state conflict: {current_window}"
                    )
                if current_token != "WINDOW_1H_CONTINUING":
                    raise Selective1hError(
                        f"first-hour failure/cancel token state conflict: {current_token}"
                    )
                cursor = connection.execute(
                    """UPDATE printer_memory_factory_campaign_windows
                       SET window_state=?,first_terminal_cause=?,terminal_at=?,updated_at=?
                       WHERE window_id=? AND window_state=?""",
                    (terminal_state, terminal_cause, stamp, stamp,
                     campaign_window_1h_id, current_window),
                )
                if cursor.rowcount != 1:
                    raise Selective1hError("first-hour failure/cancel window transition failed")
                cursor = connection.execute(
                    """UPDATE printer_memory_factory_campaign_token_slots
                       SET token_state=?,first_terminal_cause=?,terminal_at=?,updated_at=?
                       WHERE token_slot_id=? AND token_state='WINDOW_1H_CONTINUING'""",
                    (desired_token_state, terminal_cause, stamp, stamp,
                     str(row["token_slot_id"])),
                )
                if cursor.rowcount != 1:
                    raise Selective1hError("first-hour failure/cancel token transition failed")

            verify = connection.execute(
                """SELECT w.window_state,w.first_terminal_cause,w.memory_window_row_id,
                          s.token_state,s.first_terminal_cause
                   FROM printer_memory_factory_campaign_windows AS w
                   JOIN printer_memory_factory_campaign_token_slots AS s
                     ON s.token_slot_id=w.token_slot_id
                   WHERE w.window_id=?""",
                (campaign_window_1h_id,),
            ).fetchone()
            if verify is None or str(verify["window_state"]) != terminal_state:
                raise Selective1hError("first-hour terminal read-back mismatch")
            if str(verify["first_terminal_cause"] or "") != str(terminal_cause):
                raise Selective1hError("first-hour terminal cause read-back mismatch")
            if str(verify["token_state"]) != desired_token_state:
                raise Selective1hError("first-hour token read-back mismatch")
            if success and (
                verify["memory_window_row_id"] is None
                or int(verify["memory_window_row_id"]) != memory_id
            ):
                raise Selective1hError("first-hour memory bind read-back mismatch")
            return {
                "window_id": campaign_window_1h_id,
                "memory_window_row_id": memory_id,
                "window_state": terminal_state,
                "token_state": desired_token_state,
                "idempotent": False,
            }
    except sqlite3.Error as exc:
        raise Selective1hError(str(exc)) from exc


def summarize_selective_1h_reporting(
'''
operational = replace_once(
    operational, operational_anchor, operational_replacement,
    "insert atomic first-hour lifecycle reconciler",
)

old_factory_block = '''def _bind_owned_continuation_memory_window_at_close(
    conn: sqlite3.Connection,
    *,
    scheduler_job_id: int,
    memory_window_row_id: int,
) -> int | None:
    """Bind the genuine 1h row to its exact campaign window before Scheduler success."""
    window = _owned_continuation_window_for_job(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if window is None:
        return None
    state = str(window["window_state"])
    if state != "CLOSE_PENDING":
        raise ValueError(
            f"WINDOW_1H close bind requires CLOSE_PENDING; found {state}"
        )
    from printer_v1.operator_cli.campaign_ownership import bind_window_memory_row_id

    bind_window_memory_row_id(
        conn,
        window_id=str(window["window_id"]),
        memory_window_row_id=int(memory_window_row_id),
    )
    return int(memory_window_row_id)


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
'''
new_factory_block = '''def _classify_owned_1h_terminal_state(
    conn: sqlite3.Connection, *, memory_window_row_id: int,
) -> str:
    """Classify campaign terminal state from authoritative first-hour memory truth."""
    memory = conn.execute(
        """SELECT id,window_kind,data_quality_label,do_not_train
           FROM printer_memory_windows WHERE id=?""",
        (int(memory_window_row_id),),
    ).fetchone()
    if memory is None or str(memory["window_kind"]) != "WINDOW_1H":
        raise ValueError("WINDOW_1H terminal classification target mismatch")
    clean_episode = conn.execute(
        """SELECT id FROM printer_episodes
           WHERE memory_window_id=?
             AND episode_kind='WINDOW_1H_CLEAN_MEMORY'
             AND memory_status='CLEAN_MEMORY'
             AND data_quality_label='CLEAN_DATA'
             AND do_not_train=0
           ORDER BY id LIMIT 1""",
        (int(memory_window_row_id),),
    ).fetchone()
    if clean_episode is not None:
        return "CLEAN_PROMOTED"
    if int(memory["do_not_train"] or 0) != 0 or str(
        memory["data_quality_label"] or ""
    ) != "CLEAN_DATA":
        return "DIRTY"
    return "NO_PROMOTION"


def _bind_owned_continuation_memory_window_at_close(
    conn: sqlite3.Connection,
    *,
    scheduler_job_id: int,
    memory_window_row_id: int,
) -> int | None:
    """Atomically bind and terminally reconcile one successful first-hour close."""
    window = _owned_continuation_window_for_job(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if window is None:
        return None
    terminal_state = _classify_owned_1h_terminal_state(
        conn, memory_window_row_id=int(memory_window_row_id)
    )
    from printer_v1.operator_cli.operational_selective_1h import (
        reconcile_1h_terminal_lifecycle,
    )

    reconcile_1h_terminal_lifecycle(
        conn,
        campaign_window_1h_id=str(window["window_id"]),
        memory_window_row_id=int(memory_window_row_id),
        terminal_state=terminal_state,
        terminal_cause=f"window_1h_closed_{terminal_state.lower()}",
    )
    return int(memory_window_row_id)


def _terminalize_owned_continuation_window(
    conn: sqlite3.Connection,
    *,
    scheduler_job_id: int,
    terminal_state: str,
    terminal_cause: str,
) -> str | None:
    """Fail/cancel one exact first-hour lifecycle without touching its peer."""
    window = _owned_continuation_window_for_job(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if window is None:
        return None
    from printer_v1.operator_cli.operational_selective_1h import (
        reconcile_1h_terminal_lifecycle,
    )

    reconciled = reconcile_1h_terminal_lifecycle(
        conn,
        campaign_window_1h_id=str(window["window_id"]),
        terminal_state=str(terminal_state),
        terminal_cause=str(terminal_cause),
    )
    return str(reconciled["window_state"])
'''
factory = replace_once(
    factory, old_factory_block, new_factory_block,
    "replace first-hour bind/failure helpers",
)

old_cancel_loop = '''    from printer_v1.operator_cli.campaign_ownership import transition_state

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
'''
new_cancel_loop = '''    from printer_v1.operator_cli.operational_selective_1h import (
        reconcile_1h_terminal_lifecycle,
    )

    for row in rows:
        state = str(row["window_state"])
        if state not in active_states:
            continue
        reconcile_1h_terminal_lifecycle(
            conn,
            campaign_window_1h_id=str(row["window_id"]),
            terminal_state="CANCELLED",
            terminal_cause=str(terminal_cause),
        )
        changed += 1
    return changed
'''
factory = replace_once(
    factory, old_cancel_loop, new_cancel_loop,
    "reconcile run-wide first-hour cancellation",
)

old_cp4 = '''            campaign = self._campaign_window(fx, 1)
            self.assertEqual(int(campaign["memory_window_row_id"]), memory_window_id)
            self.assertEqual(str(campaign["window_state"]), "CLOSE_PENDING")
'''
new_cp4 = '''            campaign = self._campaign_window(fx, 1)
            self.assertEqual(int(campaign["memory_window_row_id"]), memory_window_id)
            self.assertEqual(str(campaign["window_state"]), "NO_PROMOTION")
            slot_state = fx.connection.execute(
                """SELECT token_state FROM printer_memory_factory_campaign_token_slots
                   WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                     AND cycle_id='cycle-1h' AND token_row_id=1"""
            ).fetchone()[0]
            self.assertEqual(str(slot_state), "WINDOW_1H_CLOSED")
'''
cp4_test = replace_once(cp4_test, old_cp4, new_cp4, "modernize CP4 bind assertion")

operational_path.write_text(operational, encoding="utf-8")
factory_path.write_text(factory, encoding="utf-8")
cp4_test_path.write_text(cp4_test, encoding="utf-8")

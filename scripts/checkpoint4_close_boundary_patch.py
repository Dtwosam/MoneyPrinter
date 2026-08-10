from pathlib import Path

factory_path = Path("src/printer_v1/operator_cli/one_command_15m_factory.py")
writer_path = Path("src/printer_v1/operator_cli/lane_e2o_1h_window_close.py")
cadence_path = Path("src/printer_v1/snapshots/cadence_policy.py")
factory = factory_path.read_text(encoding="utf-8")
writer = writer_path.read_text(encoding="utf-8")
cadence = cadence_path.read_text(encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Factory: exact close-state transition + exact row binding + close failure.
# ---------------------------------------------------------------------------
collecting_anchor = '''def _terminalize_owned_continuation_window(
'''
close_helpers = '''def _mark_owned_continuation_window_close_pending(
    conn: sqlite3.Connection, *, scheduler_job_id: int, step_kind: str,
) -> str | None:
    """Advance the exact first-hour window when its real close job is claimed."""
    if str(step_kind) != "CONTINUATION_CLOSE":
        return None
    window = _owned_continuation_window_for_job(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if window is None:
        return None
    state = str(window["window_state"])
    if state == "CLOSE_PENDING":
        return state
    if state != "COLLECTING":
        raise ValueError(
            "WINDOW_1H close state conflict: expected COLLECTING/CLOSE_PENDING, "
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


def _bind_owned_continuation_memory_window_at_close(
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


'''
if collecting_anchor not in factory:
    raise SystemExit("factory helper insertion anchor missing")
factory = factory.replace(collecting_anchor, close_helpers + collecting_anchor, 1)

factory = replace_once(
    factory,
'''            _mark_owned_continuation_window_collecting(
                conn,
                scheduler_job_id=job_id,
                step_kind=str(pending["step_kind"]),
            )
            conn.commit()
''',
'''            _mark_owned_continuation_window_collecting(
                conn,
                scheduler_job_id=job_id,
                step_kind=str(pending["step_kind"]),
            )
            _mark_owned_continuation_window_close_pending(
                conn,
                scheduler_job_id=job_id,
                step_kind=str(pending["step_kind"]),
            )
            conn.commit()
''',
    "claim close-pending wiring",
)

factory = replace_once(
    factory,
'''                    # Re-persist enriched close-step result_json (includes
                    # campaign_window_registration) before Scheduler terminalization.
                    # Registration remains inside the same open transaction; a
                    # registration fault still rolls back the SUCCEEDED update.
                    if result.get("campaign_window_registration") is not None:
                        _update_step(conn, int(pending["id"]), "SUCCEEDED", result)
                    complete_job(conn, job_id=job_id)
''',
'''                    # Re-persist enriched close-step result_json (includes
                    # campaign_window_registration) before Scheduler terminalization.
                    # Registration remains inside the same open transaction; a
                    # registration fault still rolls back the SUCCEEDED update.
                    if result.get("campaign_window_registration") is not None:
                        _update_step(conn, int(pending["id"]), "SUCCEEDED", result)
                    if str(pending["step_kind"]) == "CONTINUATION_CLOSE":
                        memory_window_id = result.get("memory_window_id")
                        if memory_window_id is None:
                            raise ValueError(
                                "CONTINUATION_CLOSE_SUCCEEDED_WITHOUT_MEMORY_WINDOW"
                            )
                        result["campaign_window_1h_binding"] = (
                            _bind_owned_continuation_memory_window_at_close(
                                conn,
                                scheduler_job_id=job_id,
                                memory_window_row_id=int(memory_window_id),
                            )
                        )
                        _update_step(conn, int(pending["id"]), "SUCCEEDED", result)
                    complete_job(conn, job_id=job_id)
''',
    "successful 1h row bind wiring",
)

factory = factory.replace(
'''                    if str(pending["step_kind"]) == "CONTINUATION_SNAPSHOT":
                        _terminalize_owned_continuation_window(
''',
'''                    if str(pending["step_kind"]) in {
                        "CONTINUATION_SNAPSHOT", "CONTINUATION_CLOSE"
                    }:
                        _terminalize_owned_continuation_window(
''',
)
if factory.count('"CONTINUATION_SNAPSHOT", "CONTINUATION_CLOSE"') < 2:
    raise SystemExit("expected both token-local close failure branches to be patched")

# ---------------------------------------------------------------------------
# 1h writer: observed closing snapshot must reach the fixed deadline.
# ---------------------------------------------------------------------------
writer = replace_once(
    writer,
'''    continuity_dict: dict[str, Any] | None = None
    if continuation_of_15m is not None:
''',
'''    continuity_dict: dict[str, Any] | None = None
    closing_snapshot_lateness_seconds: float | None = None
    if continuation_of_15m is not None:
''',
    "writer lateness variable",
)

writer = replace_once(
    writer,
'''        deadline = compute_1h_continuation_deadline(fifteen_close_at)
        one_h_link = {
''',
'''        deadline = compute_1h_continuation_deadline(fifteen_close_at)
        if deadline is not None:
            close_captured_at = str(row["captured_at"])
            closing_snapshot_lateness_seconds = _compute_elapsed_seconds(
                deadline.isoformat(), close_captured_at
            )
            if closing_snapshot_lateness_seconds is None:
                return {
                    "e2o_1h_status": E2O_1H_STATUS_BLOCKED,
                    "created": False,
                    "blocked_reasons": ["closing_snapshot_timestamp_unparseable"],
                    "approved_mint": approved_mint,
                    "snapshot_id": snapshot_id,
                    "hard_locks": dict(_HARD_LOCKS),
                    "paper_decisions_created": 0,
                    "positions_created": 0,
                    "pnl_created": 0,
                    "memories_created": 0,
                    "memory_windows_created": 0,
                }
            if closing_snapshot_lateness_seconds < -0.001:
                return {
                    "e2o_1h_status": E2O_1H_STATUS_BLOCKED,
                    "created": False,
                    "blocked_reasons": [
                        "closing_snapshot_precedes_fixed_deadline: "
                        f"offset={closing_snapshot_lateness_seconds:.3f}s"
                    ],
                    "closing_snapshot_lateness_seconds": round(
                        closing_snapshot_lateness_seconds, 3
                    ),
                    "approved_mint": approved_mint,
                    "snapshot_id": snapshot_id,
                    "hard_locks": dict(_HARD_LOCKS),
                    "paper_decisions_created": 0,
                    "positions_created": 0,
                    "pnl_created": 0,
                    "memories_created": 0,
                    "memory_windows_created": 0,
                }
            if closing_snapshot_lateness_seconds < 0:
                closing_snapshot_lateness_seconds = 0.0
        one_h_link = {
''',
    "writer fixed-deadline close proof",
)

writer = replace_once(
    writer,
'''                "interpolated_first_snapshot": False,
            }
''',
'''                "interpolated_first_snapshot": False,
                "observed_closing_snapshot_at": str(row["captured_at"]),
                "closing_snapshot_lateness_seconds": closing_snapshot_lateness_seconds,
            }
''',
    "writer supporting close context",
)

writer = replace_once(
    writer,
'''        "elapsed_seconds": elapsed_seconds,
        "lane_q_integrity_eligible": lane_q_integrity_eligible,
''',
'''        "elapsed_seconds": elapsed_seconds,
        "closing_snapshot_lateness_seconds": closing_snapshot_lateness_seconds,
        "lane_q_integrity_eligible": lane_q_integrity_eligible,
''',
    "writer result lateness",
)

# Keep the module contract accurate for the new predecessor-linked behavior.
writer = writer.replace(
'''  The writer does NOT block when elapsed < 2700s; it reports
  lane_q_integrity_eligible=False so callers can see why Lane Q will block.
''',
'''  For predecessor-linked first-hour continuation, the actual closing snapshot
  must reach the fixed 15m-close + 2700s deadline; an early closing observation
  fails closed and creates no WINDOW_1H row. Legacy unlinked fixture behavior
  remains separately reported through lane_q_integrity_eligible.
''',
1,
)

# ---------------------------------------------------------------------------
# Cadence: turn on already-existing fixed-duration/forced-close controls for 1h.
# ---------------------------------------------------------------------------
cadence = replace_once(
    cadence,
'''        minimum_required_snapshots=24, support_only=False,
        enabled_for_real_collection=True,
    ),
''',
'''        minimum_required_snapshots=24, support_only=False,
        enabled_for_real_collection=True,
        require_full_anchored_duration=True,
        require_forced_closing_snapshot=True,
    ),
''',
    "1h FAST forced close flags",
)
cadence = replace_once(
    cadence,
'''        minimum_required_snapshots=13, support_only=False,
        enabled_for_real_collection=True,
    ),
''',
'''        minimum_required_snapshots=13, support_only=False,
        enabled_for_real_collection=True,
        require_full_anchored_duration=True,
        require_forced_closing_snapshot=True,
    ),
''',
    "1h NORMAL forced close flags",
)

factory_path.write_text(factory, encoding="utf-8")
writer_path.write_text(writer, encoding="utf-8")
cadence_path.write_text(cadence, encoding="utf-8")

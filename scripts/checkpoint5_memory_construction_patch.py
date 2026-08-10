from pathlib import Path

factory_path = Path("src/printer_v1/operator_cli/one_command_15m_factory.py")
lane_q_path = Path("src/printer_v1/operator_cli/lane_q_15m_window_integrity_guard.py")
lane_k_path = Path("src/printer_v1/operator_cli/lane_k_e2z_pipeline_wiring.py")
e2z_path = Path("src/printer_v1/operator_cli/e2z_clean_memory_creation.py")

factory = factory_path.read_text(encoding="utf-8")
lane_q = lane_q_path.read_text(encoding="utf-8")
lane_k = lane_k_path.read_text(encoding="utf-8")
e2z = e2z_path.read_text(encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Factory: derive the semantic first-hour outcome from exact current-run evidence.
# ---------------------------------------------------------------------------
helper_anchor = "\ndef _execute_continuation_close(\n"
helper = r'''

def _derive_and_persist_first_hour_outcome(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    token_id: int,
    pair_id: int,
    window_id: int,
    current_close_snapshot_id: int,
) -> dict[str, Any]:
    """Classify the complete first-hour path from exact current-run evidence only."""
    target = conn.execute(
        """SELECT id,token_id,pair_id,window_kind,supporting_context_json
           FROM printer_memory_windows WHERE id=?""",
        (int(window_id),),
    ).fetchone()
    if target is None:
        raise ValueError("WINDOW_1H_OUTCOME_TARGET_MISSING")
    if (
        int(target["token_id"]) != int(token_id)
        or int(target["pair_id"]) != int(pair_id)
        or str(target["window_kind"]) != "WINDOW_1H"
    ):
        raise ValueError("WINDOW_1H_OUTCOME_TARGET_IDENTITY_MISMATCH")

    ledger_rows = conn.execute(
        """SELECT snapshot_id
           FROM printer_memory_factory_run_steps
           WHERE run_id=? AND token_id=? AND pair_id=?
             AND step_kind IN ('SNAPSHOT','WINDOW_CLOSE','CONTINUATION_SNAPSHOT')
             AND step_status='SUCCEEDED' AND snapshot_id IS NOT NULL
           ORDER BY scheduled_for,id""",
        (str(run_id), int(token_id), int(pair_id)),
    ).fetchall()
    snapshot_ids: list[int] = []
    seen: set[int] = set()
    for row in ledger_rows:
        sid = int(row["snapshot_id"])
        if sid not in seen:
            seen.add(sid)
            snapshot_ids.append(sid)
    close_sid = int(current_close_snapshot_id)
    if close_sid not in seen:
        snapshot_ids.append(close_sid)
        seen.add(close_sid)
    if len(snapshot_ids) < 2:
        raise ValueError("WINDOW_1H_OUTCOME_INSUFFICIENT_CURRENT_RUN_SNAPSHOTS")

    placeholders = ",".join("?" for _ in snapshot_ids)
    snapshots = conn.execute(
        f"""SELECT * FROM printer_token_snapshots
            WHERE id IN ({placeholders})
            ORDER BY captured_at,id""",
        tuple(snapshot_ids),
    ).fetchall()
    if len(snapshots) != len(snapshot_ids):
        raise ValueError("WINDOW_1H_OUTCOME_SNAPSHOT_IDENTITY_INCOMPLETE")
    ordered: list[dict[str, Any]] = []
    ordered_ids: list[int] = []
    for row in snapshots:
        if int(row["token_id"]) != int(token_id) or int(row["pair_id"]) != int(pair_id):
            raise ValueError("WINDOW_1H_OUTCOME_SNAPSHOT_IDENTITY_MISMATCH")
        ordered.append(dict(row))
        ordered_ids.append(int(row["id"]))
    if close_sid not in ordered_ids:
        raise ValueError("WINDOW_1H_OUTCOME_CURRENT_CLOSE_SNAPSHOT_MISSING")

    from printer_v1.memory.outcomes import classify_episode_outcome

    outcome = classify_episode_outcome("WINDOW_1H", ordered)
    outcome_label = str(outcome.value)
    try:
        context = json.loads(str(target["supporting_context_json"] or "{}"))
    except json.JSONDecodeError as exc:
        raise ValueError("WINDOW_1H_OUTCOME_SUPPORTING_CONTEXT_MALFORMED") from exc
    context.update(
        {
            "full_first_hour_outcome_snapshot_ids": ordered_ids,
            "full_first_hour_outcome_snapshot_count": len(ordered_ids),
            "full_first_hour_outcome_path_start_at": str(ordered[0]["captured_at"]),
            "full_first_hour_outcome_path_end_at": str(ordered[-1]["captured_at"]),
            "full_first_hour_outcome_source": "EXACT_CURRENT_RUN_MAIN_LIFECYCLE",
        }
    )
    updated = conn.execute(
        """UPDATE printer_memory_windows
           SET outcome_label=?,supporting_context_json=?,updated_at=?
           WHERE id=? AND token_id=? AND pair_id=? AND window_kind='WINDOW_1H'""",
        (
            outcome_label,
            _json(context),
            _iso(),
            int(window_id),
            int(token_id),
            int(pair_id),
        ),
    )
    if int(updated.rowcount or 0) != 1:
        raise ValueError("WINDOW_1H_OUTCOME_TARGET_UPDATE_FAILED")
    return {
        "outcome_label": outcome_label,
        "snapshot_ids": ordered_ids,
        "snapshot_count": len(ordered_ids),
        "path_start_at": str(ordered[0]["captured_at"]),
        "path_end_at": str(ordered[-1]["captured_at"]),
    }
'''
if helper_anchor not in factory:
    raise SystemExit("factory first-hour outcome helper anchor missing")
factory = factory.replace(helper_anchor, helper + helper_anchor, 1)

factory = replace_once(
    factory,
'''    if window_id is None:
        result.update(ok=False, blocked_reason="1h close produced no window")
        return result
    result["window_audit"] = audit_15m_memory_window(conn, int(window_id))
''',
'''    if window_id is None:
        result.update(ok=False, blocked_reason="1h close produced no window")
        return result
    result["full_first_hour_outcome"] = _derive_and_persist_first_hour_outcome(
        conn,
        run_id=str(step["run_id"]),
        token_id=int(step["token_id"]),
        pair_id=int(step["pair_id"]),
        window_id=int(window_id),
        current_close_snapshot_id=int(result["snapshot_id"]),
    )
    result["window_audit"] = audit_15m_memory_window(conn, int(window_id))
''',
    "factory first-hour outcome wiring",
)

# ---------------------------------------------------------------------------
# Lane Q: the physical 1h continuation segment is exactly 2700 seconds.
# ---------------------------------------------------------------------------
lane_q = replace_once(
    lane_q,
'''_MIN_ELAPSED_BY_WINDOW: dict[str, float] = {
    "WINDOW_15M": 900.0,
    "WINDOW_4H": 10_800.0,
}
''',
'''_MIN_ELAPSED_BY_WINDOW: dict[str, float] = {
    "WINDOW_15M": 900.0,
    "WINDOW_1H": 2_700.0,
    "WINDOW_4H": 10_800.0,
}
''',
    "Lane Q WINDOW_1H duration",
)

# ---------------------------------------------------------------------------
# Lane K: explicit operational scope enters Lane Q directly; global E2X stays 15m.
# ---------------------------------------------------------------------------
lane_k = replace_once(
    lane_k,
'''    # Step 1: E2X eligibility — all WINDOW_15M candidates, then optional scope.
    e2x_report = build_e2x_15m_clean_memory_eligibility_report(
        db_path, operator_approved=True
    )
    e2x_status = e2x_report.get("e2x_status", _E2X_STATUS_BLOCKED)
    all_eligible_ids: list[int] = list(e2x_report.get("review_candidate_ids", []))
    if explicit_scope is not None:
        scope_set = set(explicit_scope)
        all_eligible_ids = [wid for wid in all_eligible_ids if wid in scope_set]
''',
'''    # Step 1: global/backlog mode remains E2X-owned and WINDOW_15M-specific.
    # Explicit operational scope already names the exact windows; those ids enter
    # the individual Lane Q/U2/E2Z integrity path directly rather than being
    # silently dropped by E2X's intentionally 15m-only population query.
    if explicit_scope is None:
        e2x_report = build_e2x_15m_clean_memory_eligibility_report(
            db_path, operator_approved=True
        )
        e2x_status = e2x_report.get("e2x_status", _E2X_STATUS_BLOCKED)
        all_eligible_ids: list[int] = list(
            e2x_report.get("review_candidate_ids", [])
        )
    else:
        e2x_status = "NOT_APPLICABLE_EXPLICIT_WINDOW_SCOPE"
        e2x_report = {
            "e2x_status": e2x_status,
            "review_candidate_ids": list(explicit_scope),
            "explicit_window_scope": True,
        }
        all_eligible_ids = list(explicit_scope)
''',
    "Lane K explicit scope entry",
)

lane_k = replace_once(
    lane_k,
'''        result = create_clean_memory_from_window(
            db_path,
            wid,
            operator_approved=True,
            individual_promotion=True,
        )
''',
'''        result = create_clean_memory_from_window(
            db_path,
            wid,
            operator_approved=True,
            individual_promotion=True,
            lane_q_report=lane_q_guard,
        )
''',
    "Lane K passes Lane Q proof to E2Z",
)

# ---------------------------------------------------------------------------
# E2Z: WINDOW_1H and WINDOW_4H share exact passed Lane-Q proof requirement.
# ---------------------------------------------------------------------------
e2z = replace_once(
    e2z,
'''        gate_failures = _gate_window(win_row)
        if win_row["window_kind"] == "WINDOW_4H":
            valid_ids = (lane_q_report or {}).get("valid_window_ids", [])
            if window_id not in valid_ids:
                gate_failures.append(
                    "WINDOW_4H requires an explicit passed Lane Q report"
                )
''',
'''        gate_failures = _gate_window(win_row)
        if win_row["window_kind"] in {"WINDOW_1H", "WINDOW_4H"}:
            lane_q = lane_q_report or {}
            valid_ids = list(lane_q.get("valid_window_ids", []))
            blocked_ids = list(lane_q.get("blocked_window_ids", []))
            lane_q_passed = (
                lane_q.get("lane_q_guard_status") == "LANE_Q_GUARD_COMPLETED"
                and window_id in valid_ids
                and window_id not in blocked_ids
            )
            if not lane_q_passed:
                gate_failures.append(
                    f"{win_row['window_kind']} requires an explicit passed Lane Q report"
                )
''',
    "E2Z first-hour Lane Q gate",
)

factory_path.write_text(factory, encoding="utf-8")
lane_q_path.write_text(lane_q, encoding="utf-8")
lane_k_path.write_text(lane_k, encoding="utf-8")
e2z_path.write_text(e2z, encoding="utf-8")

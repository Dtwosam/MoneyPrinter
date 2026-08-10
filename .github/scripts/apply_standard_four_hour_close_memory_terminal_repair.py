from pathlib import Path

factory_path = Path('src/printer_v1/operator_cli/one_command_15m_factory.py')
runtime_path = Path('src/printer_v1/operator_cli/one_token_4h_runtime.py')
factory = factory_path.read_text()
runtime = runtime_path.read_text()

# 1. Full current-run WINDOW_4H outcome derivation before quality/promotion.
marker = '\ndef _execute_long_4h_step(\n'
if factory.count(marker) != 1:
    raise SystemExit(f'execute-long marker count={factory.count(marker)}')
outcome_owner = r'''

def _derive_and_persist_four_hour_outcome(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    token_id: int,
    pair_id: int,
    window_id: int,
    current_close_snapshot_id: int,
) -> dict[str, Any]:
    """Classify the complete 4h path from exact current-run main-lifecycle evidence."""
    target = conn.execute(
        """SELECT id,token_id,pair_id,window_kind,supporting_context_json
           FROM printer_memory_windows WHERE id=?""",
        (int(window_id),),
    ).fetchone()
    if target is None:
        raise ValueError("WINDOW_4H_OUTCOME_TARGET_MISSING")
    if (
        int(target["token_id"]) != int(token_id)
        or int(target["pair_id"]) != int(pair_id)
        or str(target["window_kind"]) != "WINDOW_4H"
    ):
        raise ValueError("WINDOW_4H_OUTCOME_TARGET_IDENTITY_MISMATCH")

    ledger_rows = conn.execute(
        """SELECT snapshot_id
           FROM printer_memory_factory_run_steps
           WHERE run_id=? AND token_id=? AND pair_id=?
             AND step_kind IN (
                 'SNAPSHOT','WINDOW_CLOSE','CONTINUATION_SNAPSHOT',
                 'CONTINUATION_CLOSE','LONG_CONTINUATION_SNAPSHOT'
             )
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
        raise ValueError("WINDOW_4H_OUTCOME_INSUFFICIENT_CURRENT_RUN_SNAPSHOTS")

    placeholders = ",".join("?" for _ in snapshot_ids)
    snapshots = conn.execute(
        f"""SELECT * FROM printer_token_snapshots
            WHERE id IN ({placeholders}) ORDER BY captured_at,id""",
        tuple(snapshot_ids),
    ).fetchall()
    if len(snapshots) != len(snapshot_ids):
        raise ValueError("WINDOW_4H_OUTCOME_SNAPSHOT_IDENTITY_INCOMPLETE")
    ordered: list[dict[str, Any]] = []
    ordered_ids: list[int] = []
    for row in snapshots:
        if int(row["token_id"]) != int(token_id) or int(row["pair_id"]) != int(pair_id):
            raise ValueError("WINDOW_4H_OUTCOME_SNAPSHOT_IDENTITY_MISMATCH")
        ordered.append(dict(row))
        ordered_ids.append(int(row["id"]))
    if close_sid not in ordered_ids:
        raise ValueError("WINDOW_4H_OUTCOME_CURRENT_CLOSE_SNAPSHOT_MISSING")

    from printer_v1.memory.outcomes import classify_episode_outcome

    outcome_label = str(classify_episode_outcome("WINDOW_4H", ordered).value)
    try:
        context = json.loads(str(target["supporting_context_json"] or "{}"))
    except json.JSONDecodeError as exc:
        raise ValueError("WINDOW_4H_OUTCOME_SUPPORTING_CONTEXT_MALFORMED") from exc
    context.update(
        {
            "full_four_hour_outcome_snapshot_ids": ordered_ids,
            "full_four_hour_outcome_snapshot_count": len(ordered_ids),
            "full_four_hour_outcome_path_start_at": str(ordered[0]["captured_at"]),
            "full_four_hour_outcome_path_end_at": str(ordered[-1]["captured_at"]),
            "full_four_hour_outcome_source": "EXACT_CURRENT_RUN_MAIN_LIFECYCLE",
        }
    )
    updated = conn.execute(
        """UPDATE printer_memory_windows
           SET outcome_label=?,supporting_context_json=?,updated_at=?
           WHERE id=? AND token_id=? AND pair_id=? AND window_kind='WINDOW_4H'""",
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
        raise ValueError("WINDOW_4H_OUTCOME_TARGET_UPDATE_FAILED")
    return {
        "outcome_label": outcome_label,
        "snapshot_ids": ordered_ids,
        "snapshot_count": len(ordered_ids),
        "path_start_at": str(ordered[0]["captured_at"]),
        "path_end_at": str(ordered[-1]["captured_at"]),
    }

'''
factory = factory.replace(marker, outcome_owner + marker, 1)

old_quality_boundary = '''    conn.commit()\n    quality = run_4h_quality_gates(\n        str(conn.execute("PRAGMA database_list").fetchone()[2]), window_id\n    )\n'''
new_quality_boundary = '''    result["full_four_hour_outcome"] = _derive_and_persist_four_hour_outcome(\n        conn,\n        run_id=str(step["run_id"]),\n        token_id=int(step["token_id"]),\n        pair_id=int(step["pair_id"]),\n        window_id=window_id,\n        current_close_snapshot_id=int(result["snapshot_id"]),\n    )\n    # E2Q/Lane-Q/E2Z use separate DB connections. Commit only the physical,\n    # shared-context, and truthful outcome prerequisites before those owners run.\n    conn.commit()\n    quality = run_4h_quality_gates(\n        str(conn.execute("PRAGMA database_list").fetchone()[2]), window_id\n    )\n'''
if factory.count(old_quality_boundary) != 1:
    raise SystemExit(f'4h quality boundary count={factory.count(old_quality_boundary)}')
factory = factory.replace(old_quality_boundary, new_quality_boundary, 1)

# 2. Authoritative clean-object classification and successful campaign binding.
marker = '\ndef _terminalize_owned_long_window(\n'
if factory.count(marker) != 1:
    raise SystemExit(f'long terminal marker count={factory.count(marker)}')
success_helpers = r'''

def _exact_complete_clean_4h_object(
    conn: sqlite3.Connection, *, memory_window_row_id: int,
) -> dict[str, Any] | None:
    rows = conn.execute(
        """SELECT e.id AS episode_id,f.id AS fingerprint_id,e.token_id,e.pair_id,
                  e.window_kind,e.memory_window_id
           FROM printer_episodes AS e
           JOIN printer_memory_fingerprints AS f
             ON f.episode_id=e.id
            AND f.fingerprint_kind='STATIC_CONDITION_SUMMARY'
            AND f.memory_status='CLEAN_MEMORY'
            AND f.data_quality_label='CLEAN_DATA'
            AND f.do_not_train=0
           WHERE e.memory_window_id=?
             AND e.episode_kind='WINDOW_4H_CLEAN_MEMORY'
             AND e.window_kind='WINDOW_4H'
             AND e.episode_status='COMPLETE'
             AND e.memory_status='CLEAN_MEMORY'
             AND e.data_quality_label='CLEAN_DATA'
             AND e.do_not_train=0
             AND e.memory_quality_label='CLEAN_MEMORY'
             AND json_extract(f.fingerprint_payload_json,'$.episode_id')=e.id
             AND json_extract(f.fingerprint_payload_json,'$.window_id')=e.memory_window_id
             AND json_extract(f.fingerprint_payload_json,'$.token_id')=e.token_id
             AND json_extract(f.fingerprint_payload_json,'$.pair_id')=e.pair_id
             AND json_extract(f.fingerprint_payload_json,'$.window_kind')=e.window_kind
           ORDER BY e.id,f.id""",
        (int(memory_window_row_id),),
    ).fetchall()
    if not rows:
        return None
    identities = {
        (int(row["episode_id"]), int(row["fingerprint_id"])) for row in rows
    }
    if len(identities) != 1:
        raise ValueError("WINDOW_4H_CLEAN_OBJECT_IDENTITY_AMBIGUOUS")
    return dict(rows[0])


def _classify_owned_4h_terminal_state(
    conn: sqlite3.Connection,
    *,
    memory_window_row_id: int,
    result: Mapping[str, Any],
) -> str:
    """Classify campaign terminal truth from the exact physical 4h result."""
    memory = conn.execute(
        """SELECT id,token_id,pair_id,window_kind,window_status,memory_status,
                  memory_quality_label,data_quality_label,do_not_train,outcome_label
           FROM printer_memory_windows WHERE id=?""",
        (int(memory_window_row_id),),
    ).fetchone()
    if (
        memory is None
        or str(memory["window_kind"]) != "WINDOW_4H"
        or str(memory["window_status"] or "") != "WINDOW_CLOSED"
    ):
        raise ValueError("WINDOW_4H terminal classification target mismatch")
    clean_object = _exact_complete_clean_4h_object(
        conn, memory_window_row_id=int(memory_window_row_id)
    )
    pipeline = result.get("memory_pipeline") if isinstance(result, Mapping) else None
    memory_event = pipeline.get("memory") if isinstance(pipeline, Mapping) else None
    e2z_status = (
        str(memory_event.get("e2z_status"))
        if isinstance(memory_event, Mapping) and memory_event.get("e2z_status") is not None
        else None
    )
    if clean_object is not None:
        if e2z_status == "E2Z_MEMORY_CREATED":
            return "CLEAN_PROMOTED"
        if e2z_status == "E2Z_ALREADY_EXISTS":
            return "ALREADY_EXISTS_IDEMPOTENT"
        raise ValueError("WINDOW_4H_CLEAN_OBJECT_WITHOUT_EXACT_E2Z_EVENT")
    if (
        int(memory["do_not_train"] or 0) != 0
        or str(memory["data_quality_label"] or "") != "CLEAN_DATA"
        or str(memory["memory_status"] or "") in {
            "DIRTY_MEMORY", "AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN"
        }
        or str(memory["memory_quality_label"] or "") in {
            "DIRTY_MEMORY", "AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN"
        }
    ):
        return "DIRTY"
    return "NO_PROMOTION"


def _bind_owned_long_memory_window_at_close(
    conn: sqlite3.Connection,
    *,
    scheduler_job_id: int,
    memory_window_row_id: int,
    result: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Bind one successful physical 4h close to its exact campaign lifecycle."""
    window = _owned_long_window_for_job(
        conn, scheduler_job_id=int(scheduler_job_id)
    )
    if window is None:
        return None
    memory = conn.execute(
        """SELECT token_id,pair_id,window_kind FROM printer_memory_windows WHERE id=?""",
        (int(memory_window_row_id),),
    ).fetchone()
    if (
        memory is None
        or int(memory["token_id"]) != int(window["token_row_id"])
        or int(memory["pair_id"]) != int(window["pair_row_id"])
        or str(memory["window_kind"]) != "WINDOW_4H"
    ):
        raise ValueError("WINDOW_4H_CAMPAIGN_PHYSICAL_IDENTITY_MISMATCH")
    terminal_state = _classify_owned_4h_terminal_state(
        conn,
        memory_window_row_id=int(memory_window_row_id),
        result=result,
    )
    from printer_v1.operator_cli.one_token_4h_runtime import (
        reconcile_4h_terminal_lifecycle,
    )

    return reconcile_4h_terminal_lifecycle(
        conn,
        campaign_window_4h_id=str(window["window_id"]),
        terminal_state=terminal_state,
        terminal_cause=f"window_4h_closed_{terminal_state.lower()}",
        memory_window_row_id=int(memory_window_row_id),
    )

'''
factory = factory.replace(marker, success_helpers + marker, 1)

# 3. Separate standard two-window campaign terminal validator.
marker = '\ndef _two_token_continuous_proof_validation(\n'
if factory.count(marker) != 1:
    raise SystemExit(f'two-token validator marker count={factory.count(marker)}')
standard_validator = r'''

def _standard_campaign_four_hour_terminal_validation(
    conn: sqlite3.Connection,
    *,
    factory_run_id: str,
    campaign_id: str | None,
    run_id: str | None,
    cycle_id: str | None,
) -> dict[str, Any]:
    """Validate the exact B2 two-window WINDOW_4H campaign set categorically."""
    if not all((campaign_id, run_id, cycle_id, factory_run_id)):
        return {"enabled": False, "complete": True, "reasons": [], "per_token": []}
    windows = conn.execute(
        """SELECT w.*,s.slot_ordinal,s.token_state,s.token_row_id AS slot_token_row_id,
                  s.pair_row_id AS slot_pair_row_id
           FROM printer_memory_factory_campaign_windows AS w
           JOIN printer_memory_factory_campaign_token_slots AS s
             ON s.token_slot_id=w.token_slot_id
            AND s.campaign_id=w.campaign_id
            AND s.run_id=w.run_id
            AND s.cycle_id=w.cycle_id
           WHERE w.campaign_id=? AND w.run_id=? AND w.cycle_id=?
             AND w.window_kind='WINDOW_4H'
           ORDER BY s.slot_ordinal,w.window_id""",
        (str(campaign_id), str(run_id), str(cycle_id)),
    ).fetchall()
    if not windows:
        return {"enabled": False, "complete": True, "reasons": [], "per_token": []}

    reasons: list[str] = []
    if len(windows) != 2:
        reasons.append(f"standard_window_4h_count:{len(windows)} expected=2")
    if len({str(row["token_slot_id"]) for row in windows}) != len(windows):
        reasons.append("duplicate_standard_window_4h_slot_identity")
    if len({int(row["token_row_id"]) for row in windows}) != len(windows):
        reasons.append("duplicate_standard_window_4h_token_identity")

    success_states = {
        "CLEAN_PROMOTED", "DIRTY", "NO_PROMOTION", "ALREADY_EXISTS_IDEMPOTENT"
    }
    per_token: list[dict[str, Any]] = []
    for window in windows:
        window_reasons: list[str] = []
        token_id = int(window["token_row_id"])
        pair_id = int(window["pair_row_id"])
        if (
            int(window["slot_token_row_id"]) != token_id
            or int(window["slot_pair_row_id"]) != pair_id
        ):
            window_reasons.append("slot_token_pair_identity_mismatch")
        owned = conn.execute(
            """SELECT s.*,j.status AS scheduler_status,sw.work_state,
                      sw.scheduler_work_id
               FROM printer_memory_factory_campaign_scheduler_work AS sw
               JOIN printer_memory_factory_run_steps AS s
                 ON s.scheduler_job_id=sw.scheduler_job_id
               JOIN printer_scheduler_jobs AS j ON j.id=sw.scheduler_job_id
               WHERE sw.campaign_id=? AND sw.run_id=? AND sw.cycle_id=?
                 AND sw.factory_run_id=? AND sw.window_id=?
                 AND sw.token_slot_id=?
                 AND sw.ownership_contract_version='V2_STAGE_SCOPED'
                 AND sw.work_scope='WINDOW_LIFECYCLE'
                 AND sw.stage_id='WINDOW_4H'
                 AND sw.target_category='CAMPAIGN_WINDOW'
                 AND sw.target_identity=sw.window_id
                 AND s.run_id=? AND s.token_id=? AND s.pair_id=?
                 AND s.step_kind IN ('LONG_CONTINUATION_SNAPSHOT','LONG_CONTINUATION_CLOSE')
               ORDER BY s.scheduled_for,s.id""",
            (
                str(campaign_id), str(run_id), str(cycle_id), str(factory_run_id),
                str(window["window_id"]), str(window["token_slot_id"]),
                str(factory_run_id), token_id, pair_id,
            ),
        ).fetchall()
        lanes = {str(row["tracking_lane"]) for row in owned}
        lane = next(iter(lanes)) if len(lanes) == 1 else None
        if lane is None:
            window_reasons.append("missing_or_ambiguous_4h_tracking_lane")
            expected = 0
        else:
            try:
                expected = int(
                    _cadence_get_policy("WINDOW_4H", lane).minimum_required_snapshots
                )
            except Exception:
                expected = 0
                window_reasons.append("missing_4h_cadence_policy")
        actual = sum(1 for row in owned if row["snapshot_id"] is not None)
        if expected and actual != expected:
            window_reasons.append(f"incomplete_4h_collection:{actual}/{expected}")
        closes = [row for row in owned if str(row["step_kind"]) == "LONG_CONTINUATION_CLOSE"]
        if len(closes) != 1:
            window_reasons.append(f"owned_4h_close_count:{len(closes)} expected=1")
            close = None
        else:
            close = closes[0]
            if str(close["step_status"]) != "SUCCEEDED":
                window_reasons.append(f"owned_4h_close_not_succeeded:{close['step_status']}")
            if str(close["scheduler_status"]) != "SUCCEEDED":
                window_reasons.append(
                    f"owned_4h_close_scheduler_not_succeeded:{close['scheduler_status']}"
                )
            if str(close["work_state"]) != "SUCCEEDED":
                window_reasons.append(
                    f"owned_4h_close_campaign_work_not_succeeded:{close['work_state']}"
                )
        memory_id = int(window["memory_window_row_id"]) if window["memory_window_row_id"] is not None else None
        if memory_id is None:
            window_reasons.append("missing_bound_4h_memory_window")
            physical = None
            clean_object = None
        else:
            physical = conn.execute(
                """SELECT id,token_id,pair_id,window_kind,data_quality_label,
                          memory_status,memory_quality_label,do_not_train
                   FROM printer_memory_windows WHERE id=?""",
                (memory_id,),
            ).fetchone()
            if (
                physical is None
                or int(physical["token_id"]) != token_id
                or int(physical["pair_id"]) != pair_id
                or str(physical["window_kind"]) != "WINDOW_4H"
            ):
                window_reasons.append("bound_4h_memory_identity_mismatch")
                clean_object = None
            else:
                clean_object = _exact_complete_clean_4h_object(
                    conn, memory_window_row_id=memory_id
                )
        window_state = str(window["window_state"])
        if window_state not in success_states:
            window_reasons.append(f"nonterminal_or_failed_4h_window_state:{window_state}")
        if str(window["token_state"]) != "WINDOW_4H_CLOSED":
            window_reasons.append(f"token_slot_not_window_4h_closed:{window['token_state']}")
        if window_state in {"CLEAN_PROMOTED", "ALREADY_EXISTS_IDEMPOTENT"}:
            if clean_object is None:
                window_reasons.append("clean_campaign_state_without_complete_clean_object")
        elif window_state == "DIRTY" and physical is not None:
            dirty = (
                int(physical["do_not_train"] or 0) != 0
                or str(physical["data_quality_label"] or "") != "CLEAN_DATA"
                or str(physical["memory_status"] or "") in {
                    "DIRTY_MEMORY", "AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN"
                }
                or str(physical["memory_quality_label"] or "") in {
                    "DIRTY_MEMORY", "AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN"
                }
            )
            if not dirty:
                window_reasons.append("dirty_campaign_state_without_dirty_physical_memory")
        elif window_state == "NO_PROMOTION" and clean_object is not None:
            window_reasons.append("no_promotion_campaign_state_with_clean_object")

        per_token.append(
            {
                "token_id": token_id,
                "pair_id": pair_id,
                "token_slot_id": str(window["token_slot_id"]),
                "window_id": str(window["window_id"]),
                "tracking_lane": lane,
                "expected_snapshots": expected,
                "actual_snapshots": actual,
                "window_state": window_state,
                "token_state": str(window["token_state"]),
                "memory_window_row_id": memory_id,
                "complete_clean_object": clean_object is not None,
                "reasons": window_reasons,
            }
        )
        reasons.extend(f"{window['window_id']}:{reason}" for reason in window_reasons)

    active_owned = int(conn.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
           WHERE campaign_id=? AND run_id=? AND cycle_id=? AND factory_run_id=?
             AND ownership_contract_version='V2_STAGE_SCOPED'
             AND work_scope='WINDOW_LIFECYCLE' AND stage_id='WINDOW_4H'
             AND work_state IN ('PENDING','RUNNING','COOLDOWN')""",
        (str(campaign_id), str(run_id), str(cycle_id), str(factory_run_id)),
    ).fetchone()[0])
    nonterminal_windows = int(conn.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
           WHERE campaign_id=? AND run_id=? AND cycle_id=? AND window_kind='WINDOW_4H'
             AND window_state IN ('PLANNED','COLLECTING','CLOSE_PENDING','AUDITING')""",
        (str(campaign_id), str(run_id), str(cycle_id)),
    ).fetchone()[0])
    if active_owned:
        reasons.append(f"active_owned_four_hour_work:{active_owned}")
    if nonterminal_windows:
        reasons.append(f"nonterminal_owned_four_hour_windows:{nonterminal_windows}")
    return {
        "enabled": True,
        "complete": not reasons,
        "reasons": reasons,
        "per_token": per_token,
        "active_owned_four_hour_work": active_owned,
        "nonterminal_owned_four_hour_windows": nonterminal_windows,
        "window_count": len(windows),
    }

'''
factory = factory.replace(marker, standard_validator + marker, 1)

# 4. Route final report through standard validator only when B2 ownership exists.
old_terminal = '''    terminal_validation = _four_hour_terminal_validation(\n        config=config, steps=steps, windows_by_id=windows_by_id,\n        budgets=budgets, pending_steps=pending_run_steps, running_jobs=running,\n        primary_cause=primary_cause,\n        complete_clean_objects_by_window_id=promotions_by_window_id,\n    )\n    two_token_validation = _two_token_continuous_proof_validation(\n'''
new_terminal = '''    historical_terminal_validation = _four_hour_terminal_validation(\n        config=config, steps=steps, windows_by_id=windows_by_id,\n        budgets=budgets, pending_steps=pending_run_steps, running_jobs=running,\n        primary_cause=primary_cause,\n        complete_clean_objects_by_window_id=promotions_by_window_id,\n    )\n    standard_four_hour_validation = _standard_campaign_four_hour_terminal_validation(\n        conn,\n        factory_run_id=run_id,\n        campaign_id=config.get("campaign_id"),\n        run_id=config.get("campaign_run_id"),\n        cycle_id=config.get("cycle_id"),\n    )\n    if standard_four_hour_validation.get("enabled"):\n        terminal_validation = {\n            **standard_four_hour_validation,\n            "run_status": (\n                "COMPLETED" if standard_four_hour_validation.get("complete")\n                else "SAFE_STOPPED"\n            ),\n            "stop_reason": (\n                STOP_COMPLETED if standard_four_hour_validation.get("complete")\n                else STOP_TERMINAL_4H\n            ),\n            "primary_cause": primary_cause,\n            "historical_one_token_validator_applicable": False,\n        }\n    else:\n        terminal_validation = historical_terminal_validation\n    two_token_validation = _two_token_continuous_proof_validation(\n'''
if factory.count(old_terminal) != 1:
    raise SystemExit(f'final terminal routing marker count={factory.count(old_terminal)}')
factory = factory.replace(old_terminal, new_terminal, 1)

old_report_key = '''        "four_hour_terminal_validation": terminal_validation,\n        "two_token_continuous_proof": two_token_validation,\n'''
new_report_key = '''        "four_hour_terminal_validation": terminal_validation,\n        "standard_four_hour_terminal_validation": standard_four_hour_validation,\n        "historical_one_token_four_hour_terminal_validation": (\n            historical_terminal_validation\n            if standard_four_hour_validation.get("enabled") else None\n        ),\n        "two_token_continuous_proof": two_token_validation,\n'''
if factory.count(old_report_key) != 1:
    raise SystemExit(f'final report key marker count={factory.count(old_report_key)}')
factory = factory.replace(old_report_key, new_report_key, 1)

# 5. Bind successful long close before Scheduler success terminalization.
old_success_binding = '''                    if str(pending["step_kind"]) == "CONTINUATION_CLOSE":\n                        memory_window_id = result.get("memory_window_id")\n                        if memory_window_id is None:\n                            raise ValueError(\n                                "CONTINUATION_CLOSE_SUCCEEDED_WITHOUT_MEMORY_WINDOW"\n                            )\n                        result["campaign_window_1h_binding"] = (\n                            _bind_owned_continuation_memory_window_at_close(\n                                conn,\n                                scheduler_job_id=job_id,\n                                memory_window_row_id=int(memory_window_id),\n                            )\n                        )\n                        _update_step(conn, int(pending["id"]), "SUCCEEDED", result)\n                    complete_job(conn, job_id=job_id)\n'''
new_success_binding = '''                    if str(pending["step_kind"]) == "CONTINUATION_CLOSE":\n                        memory_window_id = result.get("memory_window_id")\n                        if memory_window_id is None:\n                            raise ValueError(\n                                "CONTINUATION_CLOSE_SUCCEEDED_WITHOUT_MEMORY_WINDOW"\n                            )\n                        result["campaign_window_1h_binding"] = (\n                            _bind_owned_continuation_memory_window_at_close(\n                                conn,\n                                scheduler_job_id=job_id,\n                                memory_window_row_id=int(memory_window_id),\n                            )\n                        )\n                        _update_step(conn, int(pending["id"]), "SUCCEEDED", result)\n                    elif str(pending["step_kind"]) == "LONG_CONTINUATION_CLOSE":\n                        memory_window_id = result.get("memory_window_id")\n                        if memory_window_id is None:\n                            raise ValueError(\n                                "LONG_CONTINUATION_CLOSE_SUCCEEDED_WITHOUT_MEMORY_WINDOW"\n                            )\n                        result["campaign_window_4h_binding"] = (\n                            _bind_owned_long_memory_window_at_close(\n                                conn,\n                                scheduler_job_id=job_id,\n                                memory_window_row_id=int(memory_window_id),\n                                result=result,\n                            )\n                        )\n                        _update_step(conn, int(pending["id"]), "SUCCEEDED", result)\n                    complete_job(conn, job_id=job_id)\n'''
if factory.count(old_success_binding) != 1:
    raise SystemExit(f'success binding marker count={factory.count(old_success_binding)}')
factory = factory.replace(old_success_binding, new_success_binding, 1)

# 6. Successful WINDOW_4H campaign lifecycle reconciler. Never commits caller transaction.
if 'def reconcile_4h_terminal_lifecycle(' in runtime:
    raise SystemExit('reconcile_4h_terminal_lifecycle already exists')
reconciler = r'''


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
'''
runtime = runtime.rstrip() + reconciler + '\n'

factory_path.write_text(factory)
runtime_path.write_text(runtime)

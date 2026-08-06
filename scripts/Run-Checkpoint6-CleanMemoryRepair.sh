#!/usr/bin/env bash
set -euo pipefail

BRANCH='agent/v2-9-8b-window-15m-checkpoint-6-collection-clean-memory-closeout'
RED_COMMIT='dc00cbc6c9e56691377c279728a9c915c700bbe2'
REPO_ROOT="$(git rev-parse --show-toplevel)"
PYTHON="$REPO_ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "CHECKPOINT6_BLOCKED: missing $PYTHON" >&2
  exit 1
fi

git -C "$REPO_ROOT" fetch origin "$BRANCH"
REMOTE_HEAD="$(git -C "$REPO_ROOT" rev-parse "origin/$BRANCH")"
RED_WT="$(mktemp -d -t printer-cp6-red.XXXXXX)"
GREEN_WT="$(mktemp -d -t printer-cp6-green.XXXXXX)"
cleanup() {
  git -C "$REPO_ROOT" worktree remove --force "$RED_WT" >/dev/null 2>&1 || true
  git -C "$REPO_ROOT" worktree remove --force "$GREEN_WT" >/dev/null 2>&1 || true
  rm -rf "$RED_WT" "$GREEN_WT"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# 1. Prove the committed fail-first tests really fail on the pinned RED commit.
# ---------------------------------------------------------------------------
git -C "$REPO_ROOT" worktree add --detach "$RED_WT" "$RED_COMMIT" >/dev/null
set +e
(
  cd "$RED_WT"
  PYTHONPATH="$RED_WT/src" "$PYTHON" -m pytest \
    tests/test_v2_9_8b_window_15m_checkpoint_6_collection_clean_memory_closeout.py \
    -q
) >"$RED_WT/red.log" 2>&1
RED_RC=$?
set -e
cat "$RED_WT/red.log"
if [[ "$RED_RC" -eq 0 ]]; then
  echo "CHECKPOINT6_RED_BLOCKED: fail-first suite unexpectedly passed" >&2
  exit 1
fi
if ! grep -Eq '4 failed' "$RED_WT/red.log"; then
  echo "CHECKPOINT6_RED_BLOCKED: expected exactly four fail-first failures" >&2
  exit 1
fi
for marker in \
  test_red_a_clean_episode_preserves_exact_window_outcome \
  test_red_b_fingerprint_preserves_rich_window_conditions \
  test_red_c_final_15m_disposition_no_longer_backfills_5m_support \
  test_red_d_materialized_support_persists_exact_ownership_and_provenance
do
  grep -q "$marker" "$RED_WT/red.log" || {
    echo "CHECKPOINT6_RED_BLOCKED: missing expected failure $marker" >&2
    exit 1
  }
done
echo 'CHECKPOINT6_FOUR_REDS_CONFIRMED'
git -C "$REPO_ROOT" worktree remove --force "$RED_WT" >/dev/null

# ---------------------------------------------------------------------------
# 2. Apply only the approved owner-level repair in an isolated worktree.
# ---------------------------------------------------------------------------
git -C "$REPO_ROOT" worktree add --detach "$GREEN_WT" "$REMOTE_HEAD" >/dev/null
cd "$GREEN_WT"

PYTHONPATH="$GREEN_WT/src" "$PYTHON" - <<'PY'
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"CHECKPOINT6_EDIT_BLOCKED:{path}:expected_once:found={count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# ------------------------------------------------------------------
# A+B. Atomic clean object: exact outcome + real categorical context.
# ------------------------------------------------------------------
clean = "src/printer_v1/memory/clean_object_promotion.py"
replace_once(
    clean,
    '''def _exact_identity(value: object, *, code: str) -> int:\n    if value in (None, "", "UNKNOWN"):\n        raise CleanObjectIntegrityError(code)\n    try:\n        resolved = int(value)\n    except (TypeError, ValueError) as exc:\n        raise CleanObjectIntegrityError(code, str(value)) from exc\n    if resolved <= 0:\n        raise CleanObjectIntegrityError(code, str(value))\n    return resolved\n\n\ndef _fingerprint_payload(''',
    '''def _exact_identity(value: object, *, code: str) -> int:\n    if value in (None, "", "UNKNOWN"):\n        raise CleanObjectIntegrityError(code)\n    try:\n        resolved = int(value)\n    except (TypeError, ValueError) as exc:\n        raise CleanObjectIntegrityError(code, str(value)) from exc\n    if resolved <= 0:\n        raise CleanObjectIntegrityError(code, str(value))\n    return resolved\n\n\ndef _fingerprint_context(\n    window_context: Mapping[str, Any], episode_context: Mapping[str, Any]\n) -> dict[str, Any]:\n    """Resolve the real categorical window context without inventing facts."""\n    merged = dict(window_context)\n    shared = window_context.get("shared_window_15m_context_evidence")\n    if not isinstance(shared, Mapping):\n        shared = window_context.get("shared_window_4h_context_evidence")\n    sections = shared.get("sections", {}) if isinstance(shared, Mapping) else {}\n    section_map = {\n        "market_regime": "market",\n        "solana_chain_heat": "chain_heat",\n        "safety_rug": "safety",\n        "liquidity_exit_realism": "liquidity_exit",\n        "trading_flow": "trading_flow",\n        "chart_volatility": "chart_volatility",\n    }\n    if isinstance(sections, Mapping):\n        for source_name, destination in section_map.items():\n            section = sections.get(source_name)\n            if not isinstance(section, Mapping):\n                continue\n            labels = section.get("labels")\n            if not isinstance(labels, Mapping):\n                continue\n            destination_payload = merged.get(destination)\n            destination_payload = (\n                dict(destination_payload)\n                if isinstance(destination_payload, Mapping)\n                else {}\n            )\n            destination_payload.update(dict(labels))\n            merged[destination] = destination_payload\n\n    labels = window_context.get("context_labels")\n    if isinstance(labels, Mapping):\n        categorical_targets = {\n            "market_regime_label": "market",\n            "chain_heat_label": "chain_heat",\n            "safety_status_label": "safety",\n            "rug_risk_label": "safety",\n            "liquidity_state_label": "liquidity_exit",\n            "exit_realism_label": "liquidity_exit",\n            "realism_gate_label": "liquidity_exit",\n            "flow_direction_label": "trading_flow",\n            "flow_pressure_label": "trading_flow",\n            "trend_structure_label": "chart_volatility",\n            "volatility_label": "chart_volatility",\n            "candle_path_label": "chart_volatility",\n        }\n        for field, destination in categorical_targets.items():\n            value = labels.get(field)\n            if value is None:\n                continue\n            destination_payload = merged.get(destination)\n            destination_payload = (\n                dict(destination_payload)\n                if isinstance(destination_payload, Mapping)\n                else {}\n            )\n            destination_payload[field] = value\n            merged[destination] = destination_payload\n        micro = {\n            field: labels.get(field)\n            for field in ("micro_event_state_label", "held_to_15m_result_label")\n            if labels.get(field) is not None\n        }\n        if micro and not merged.get("micro_events"):\n            merged["micro_events"] = [micro]\n        for field in ("token_age_bucket", "pair_age_bucket", "discovery_label"):\n            if merged.get(field) is None and labels.get(field) is not None:\n                merged[field] = labels[field]\n\n    # Episode context is provenance metadata. Overlay it without discarding the\n    # richer source-window condition context.\n    merged.update(\n        {key: value for key, value in episode_context.items() if value is not None}\n    )\n    return merged\n\n\ndef _fingerprint_payload(''',
)
replace_once(
    clean,
    '''    window_context = _load_json(window["supporting_context_json"])\n    episode_context = _load_json(episode["supporting_context_json"])\n    tracking_lane = window_context.get("tracking_lane")\n''',
    '''    window_context = _load_json(window["supporting_context_json"])\n    episode_context = _load_json(episode["supporting_context_json"])\n    fingerprint_context = _fingerprint_context(window_context, episode_context)\n    tracking_lane = fingerprint_context.get("tracking_lane")\n''',
)
replace_once(
    clean,
    '''            "supporting_context": episode_context or window_context,\n            "token_age_bucket": (episode_context or window_context).get("token_age_bucket"),\n            "pair_age_bucket": (episode_context or window_context).get("pair_age_bucket"),\n            "discovery_label": (episode_context or window_context).get("discovery_label"),\n''',
    '''            "supporting_context": fingerprint_context,\n            "token_age_bucket": fingerprint_context.get("token_age_bucket"),\n            "pair_age_bucket": fingerprint_context.get("pair_age_bucket"),\n            "discovery_label": fingerprint_context.get("discovery_label"),\n''',
)
replace_once(
    clean,
    '''    payload = _load_json(fingerprint["fingerprint_payload_json"])\n    expected = {\n''',
    '''    expected_outcome = str(window["outcome_label"] or "").strip()\n    if not expected_outcome or expected_outcome == "OUTCOME_UNKNOWN":\n        raise CleanObjectIntegrityError("CLEAN_OBJECT_OUTCOME_UNKNOWN")\n    if str(episode["episode_outcome_label"] or "").strip() != expected_outcome:\n        raise CleanObjectIntegrityError("CLEAN_OBJECT_OUTCOME_MISMATCH")\n    payload = _load_json(fingerprint["fingerprint_payload_json"])\n    expected = {\n''',
)
replace_once(
    clean,
    '''    if str(payload.get("window_kind")) != str(window["window_kind"]):\n        raise CleanObjectIntegrityError("FINGERPRINT_IDENTITY_MISMATCH", "window_kind")\n''',
    '''    if str(payload.get("window_kind")) != str(window["window_kind"]):\n        raise CleanObjectIntegrityError("FINGERPRINT_IDENTITY_MISMATCH", "window_kind")\n    if str(payload.get("outcome_label") or "").strip() != expected_outcome:\n        raise CleanObjectIntegrityError("FINGERPRINT_OUTCOME_MISMATCH")\n''',
)
replace_once(
    clean,
    '''        gate_failures = _gate_window(window)\n        if gate_failures:\n            raise CleanObjectIntegrityError("WINDOW_NOT_CLEAN_PROMOTION_ELIGIBLE", "; ".join(gate_failures))\n\n        episodes = connection.execute(\n''',
    '''        gate_failures = _gate_window(window)\n        if gate_failures:\n            raise CleanObjectIntegrityError("WINDOW_NOT_CLEAN_PROMOTION_ELIGIBLE", "; ".join(gate_failures))\n        outcome_label = str(window["outcome_label"] or "").strip()\n        if not outcome_label or outcome_label == "OUTCOME_UNKNOWN":\n            raise CleanObjectIntegrityError(\n                "WINDOW_OUTCOME_NOT_CLEAN_PROMOTION_ELIGIBLE"\n            )\n\n        episodes = connection.execute(\n''',
)
replace_once(
    clean,
    '''                   memory_status,data_quality_label,do_not_train,window_kind,\n                   memory_quality_label,supporting_context_json,created_at,updated_at\n               ) VALUES (?,?,?,?,'COMPLETE','CLEAN_MEMORY','CLEAN_DATA',0,?,\n                         'CLEAN_MEMORY',?,?,?)""",\n            (\n                int(window_id),\n                int(window["token_id"]),\n                int(window["pair_id"]),\n                f"{window['window_kind']}_CLEAN_MEMORY",\n                str(window["window_kind"]),\n                episode_context,\n                now,\n                now,\n            ),\n''',
    '''                   memory_status,data_quality_label,do_not_train,window_kind,\n                   memory_quality_label,episode_outcome_label,supporting_context_json,\n                   created_at,updated_at\n               ) VALUES (?,?,?,?,'COMPLETE','CLEAN_MEMORY','CLEAN_DATA',0,?,\n                         'CLEAN_MEMORY',?,?,?,?)""",\n            (\n                int(window_id),\n                int(window["token_id"]),\n                int(window["pair_id"]),\n                f"{window['window_kind']}_CLEAN_MEMORY",\n                str(window["window_kind"]),\n                outcome_label,\n                episode_context,\n                now,\n                now,\n            ),\n''',
)

# Modernize the canonical E2Z clean-candidate fixture to the already-required
# truthful outcome contract; no production exception is added for old fixtures.
e2z_test = "tests/test_post_rc_lane_e2z_clean_memory_creation.py"
replace_once(
    e2z_test,
    '''                window_status, memory_quality_label,\n                supporting_context_json, created_by_phase, created_at, updated_at\n            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'lane_e2o', ?, ?)\n''',
    '''                window_status, memory_quality_label, outcome_label,\n                supporting_context_json, created_by_phase, created_at, updated_at\n            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'NO_PUMP', ?, 'lane_e2o', ?, ?)\n''',
)

# -----------------------------------------------------------
# D. Lane X8: validate and persist frozen event-time support.
# -----------------------------------------------------------
x8 = "src/printer_v1/operator_cli/lane_x8_5m_support_integration.py"
replace_once(x8, "from typing import Any\n", "from typing import Any, Mapping\n")
marker = '''# ---------------------------------------------------------------------------\n# Core operations\n# ---------------------------------------------------------------------------\n'''
helper = '''# ---------------------------------------------------------------------------\n# Frozen event-time support validation\n# ---------------------------------------------------------------------------\n\ndef _validate_support_capture(\n    support_capture: Mapping[str, Any] | None,\n    *,\n    token_id: int,\n    pair_id: int,\n    run_id: str | None,\n    snapshot_start_id: int | None,\n    snapshot_end_id: int | None,\n) -> tuple[dict[str, Any] | None, list[str]]:\n    if support_capture is None:\n        return None, []\n    frozen = dict(support_capture)\n    reasons: list[str] = []\n    if frozen.get("verdict") != "CAPTURE_SUPPORT":\n        reasons.append("support_capture verdict must be CAPTURE_SUPPORT")\n    if str(frozen.get("token_id") or "") != str(token_id):\n        reasons.append("support_capture token_id mismatch")\n    if str(frozen.get("pair_id") or "") != str(pair_id):\n        reasons.append("support_capture pair_id mismatch")\n    if run_id is not None and str(frozen.get("factory_run_id") or "") != str(run_id):\n        reasons.append("support_capture factory_run_id mismatch")\n    if frozen.get("containing_main_window_kind") != _WINDOW_15M:\n        reasons.append("support_capture containing main window must be WINDOW_15M")\n    trigger_time = str(frozen.get("trigger_time") or "")\n    evidence_cutoff = str(frozen.get("evidence_cutoff") or "")\n    if not trigger_time or evidence_cutoff != trigger_time:\n        reasons.append("support_capture evidence cutoff must equal trigger time")\n    try:\n        from printer_v1.scheduler.support_only_5m_capture import SupportTriggerFamily\n\n        SupportTriggerFamily(str(frozen.get("trigger_family") or ""))\n    except (TypeError, ValueError):\n        reasons.append("support_capture trigger family is not adopted")\n    scheduler_work_id = str(frozen.get("scheduler_work_id") or "")\n    try:\n        scheduler_job_id = int(frozen.get("scheduler_job_id"))\n    except (TypeError, ValueError):\n        scheduler_job_id = 0\n    if not scheduler_work_id or scheduler_job_id <= 0:\n        reasons.append("support_capture Scheduler identity missing")\n    try:\n        ids = [int(value) for value in (frozen.get("triggering_snapshot_ids") or ())]\n    except (TypeError, ValueError):\n        ids = []\n    if len(ids) < 2 or len(set(ids)) != len(ids):\n        reasons.append("support_capture requires at least two exact triggering snapshots")\n    if snapshot_start_id is not None and ids and ids[0] != int(snapshot_start_id):\n        reasons.append("support_capture snapshot_start_id mismatch")\n    if snapshot_end_id is not None and ids and ids[-1] != int(snapshot_end_id):\n        reasons.append("support_capture snapshot_end_id mismatch")\n    provenance = frozen.get("source_provenance")\n    if not isinstance(provenance, list) or len(provenance) < 2:\n        reasons.append("support_capture source provenance incomplete")\n    else:\n        for item in provenance:\n            if not isinstance(item, Mapping):\n                reasons.append("support_capture source provenance malformed")\n                continue\n            if (\n                not item.get("source_name")\n                or int(item.get("source_request_id") or 0) <= 0\n                or int(item.get("source_response_id") or 0) <= 0\n                or item.get("source_status") != "COMPLETE"\n                or item.get("data_quality_label") != "CLEAN_DATA"\n                or item.get("governor_approved") is not True\n                or item.get("traceable") is not True\n                or str(item.get("scheduler_work_id") or "") != scheduler_work_id\n            ):\n                reasons.append("support_capture source provenance is not clean/traceable")\n                break\n    for field in (\n        "campaign_id", "campaign_run_id", "cycle_id", "token_slot_id",\n        "mint_id", "pair_address", "root_15m_lifecycle_id",\n        "containing_main_window_id",\n    ):\n        if not str(frozen.get(field) or ""):\n            reasons.append(f"support_capture {field} missing")\n    return frozen, list(dict.fromkeys(reasons))\n\n\n''' + marker
replace_once(x8, marker, helper)
replace_once(
    x8,
    '''        resolved_start_at = opened_at_val\n        resolved_end_at = closed_at_val\n''',
    '''        frozen_support, frozen_support_reasons = _validate_support_capture(\n            support_capture,\n            token_id=token_id,\n            pair_id=pair_id,\n            run_id=run_id,\n            snapshot_start_id=snapshot_start_id,\n            snapshot_end_id=snapshot_end_id,\n        )\n        if frozen_support_reasons:\n            return {\n                "lane_x8_capture_status": LANE_X8_STATUS_BLOCKED,\n                "captured": False,\n                "blocked_reasons": frozen_support_reasons,\n                "window_5m_id": None,\n                "parent_window_id": parent_window_id,\n                "token_id": token_id,\n                "pair_id": pair_id,\n                "do_not_train": True,\n                "5m_clean_memory_blocked": True,\n                "retrieval_from_5m_blocked": True,\n                "hard_locks": dict(_HARD_LOCKS),\n            }\n\n        resolved_start_at = opened_at_val\n        resolved_end_at = closed_at_val\n''',
)
replace_once(
    x8,
    '''    tracking_lane: str | None = None,\n) -> dict[str, Any]:\n''',
    '''    tracking_lane: str | None = None,\n    support_capture: Mapping[str, Any] | None = None,\n) -> dict[str, Any]:\n''',
)
replace_once(
    x8,
    '''        ctx: dict[str, Any] = {\n            "created_by": _CREATED_BY,\n            "parent_window_id": parent_window_id,\n            "parent_window_kind": _WINDOW_15M,\n            "run_id": run_id,\n            "tracking_lane": tracking_lane,\n            "same_opening_stream": snapshot_start_id is not None,\n        }\n\n        cur = conn.execute(\n''',
    '''        ctx: dict[str, Any] = {\n            "created_by": _CREATED_BY,\n            "parent_window_id": parent_window_id,\n            "parent_window_kind": _WINDOW_15M,\n            "run_id": run_id,\n            "factory_run_id": run_id,\n            "tracking_lane": tracking_lane,\n            "same_opening_stream": snapshot_start_id is not None,\n            "support_only": True,\n            "continuation_authority": False,\n            "retrieval_authority": False,\n            "decision_authority": False,\n            "financial_authority": False,\n        }\n        if frozen_support is not None:\n            for key in (\n                "campaign_id", "campaign_run_id", "cycle_id", "factory_run_id",\n                "token_slot_id", "token_id", "mint_id", "pair_id",\n                "pair_address", "root_15m_lifecycle_id",\n                "containing_main_window_id", "containing_main_window_kind",\n                "scheduler_work_id", "scheduler_job_id", "trigger_family",\n                "trigger_time", "evidence_cutoff", "triggering_snapshot_ids",\n                "source_provenance",\n            ):\n                ctx[key] = frozen_support.get(key)\n\n        cur = conn.execute(\n''',
)

# -----------------------------------------------------------
# C. Real factory wiring: freeze at snapshot time, materialize later.
# -----------------------------------------------------------
factory_path = "src/printer_v1/operator_cli/one_command_15m_factory.py"
replace_once(
    factory_path,
    '''def _capture_same_stream_5m_support(\n''',
    '''def _evaluate_event_time_5m_support_for_snapshot(\n    conn: sqlite3.Connection,\n    *,\n    run_id: str,\n    step: sqlite3.Row,\n    result: Mapping[str, Any],\n) -> dict[str, Any]:\n    from printer_v1.operator_cli.checkpoint6_event_time_5m import (\n        evaluate_event_time_5m_support_for_snapshot,\n    )\n\n    return evaluate_event_time_5m_support_for_snapshot(\n        conn, factory_run_id=run_id, step=step, result=result\n    )\n\n\ndef _materialize_frozen_5m_support(\n    conn: sqlite3.Connection,\n    *,\n    run_id: str,\n    close_step: sqlite3.Row,\n    parent_window_id: int,\n) -> dict[str, Any]:\n    from printer_v1.operator_cli.checkpoint6_event_time_5m import (\n        materialize_frozen_5m_support,\n    )\n\n    return materialize_frozen_5m_support(\n        conn,\n        factory_run_id=run_id,\n        close_step=close_step,\n        parent_window_id=parent_window_id,\n    )\n\n\ndef _capture_same_stream_5m_support(\n''',
)
old_natural = '''def _natural_disposition_schedule(\n    conn: sqlite3.Connection,\n    *,\n    run_id: str,\n    close_step: sqlite3.Row,\n    window_id: int,\n    continuation_seconds: float,\n) -> tuple[dict[str, Any], dict[str, Any]]:\n    """Derive one token's operational-natural disposition from its own governed\n    15m evidence and enqueue only the permitted continuation / support-only 5m.\n\n    Token-local: every query is scoped to ``close_step``'s token, pair and lane\n    and to its own 15m memory window, so the outcome is identical regardless of\n    which token closed first.\n    """\n    from printer_v1.operator_cli.authoritative_live_operational_campaign import (\n        derive_natural_disposition,\n    )\n\n    disposition = derive_natural_disposition(conn, int(window_id))\n    if disposition.should_continue:\n        support = _capture_same_stream_5m_support(\n            conn,\n            run_id=run_id,\n            close_step=close_step,\n            parent_window_id=int(window_id),\n        )\n        if support.get("window_5m_id") is None:\n            raise ValueError(\n                "same-stream 5m support capture blocked: "\n                + "; ".join(support.get("blocked_reasons", []))\n            )\n        # Support-only 5m trigger derived from observed micro-event evidence.\n        support["trigger_family"] = disposition.trigger_family\n        support["proof_evidence"] = disposition.evidence_label\n        source = _resolve_current_run_15m_source(\n            conn,\n            run_id=run_id,\n            token_id=int(close_step["token_id"]),\n            pair_id=int(close_step["pair_id"]),\n            tracking_lane=str(close_step["tracking_lane"]),\n            current_close_step_id=int(close_step["id"]),\n        )\n        if not source.get("resolved"):\n            raise ValueError(\n                "current-run 15m continuation source blocked: "\n                + "; ".join(source.get("reasons", []))\n            )\n        continuation_plan = _plan_continuation_jobs(\n            conn,\n            run_id=run_id,\n            close_step=close_step,\n            fifteen_m=source["window"],\n            continuation_seconds=continuation_seconds,\n        )\n        if not continuation_plan.get("enqueue_ok"):\n            raise ValueError(\n                "continuation planning blocked: "\n                + "; ".join(continuation_plan.get("reasons", []))\n            )\n        return support, continuation_plan\n    reason = disposition.evidence_label\n    support = {\n        "captured": False,\n        "verdict": "VALID_NO_CAPTURE",\n        "reason": reason,\n        "window_5m_id": None,\n    }\n    continuation_plan = {\n        "enqueue_ok": False,\n        "planned_jobs": 0,\n        "verdict": "STOP_AFTER_15M",\n        "reason": reason,\n    }\n    return support, continuation_plan\n'''
new_natural = '''def _natural_disposition_schedule(\n    conn: sqlite3.Connection,\n    *,\n    run_id: str,\n    close_step: sqlite3.Row,\n    window_id: int,\n    continuation_seconds: float,\n) -> tuple[dict[str, Any], dict[str, Any]]:\n    """Derive final-15m continuation without creating retrospective 5m support.\n\n    Event-time support is evaluated and frozen by Scheduler-owned SNAPSHOT work.\n    This final-window owner remains the independent continuation authority only.\n    """\n    from printer_v1.operator_cli.authoritative_live_operational_campaign import (\n        derive_natural_disposition,\n    )\n\n    disposition = derive_natural_disposition(conn, int(window_id))\n    support = {\n        "captured": False,\n        "verdict": "EVENT_TIME_SUPPORT_HANDLED_SEPARATELY",\n        "reason": "FINAL_15M_OUTCOME_NOT_SUPPORT_TRIGGER_AUTHORITY",\n        "window_5m_id": None,\n    }\n    if disposition.should_continue:\n        source = _resolve_current_run_15m_source(\n            conn,\n            run_id=run_id,\n            token_id=int(close_step["token_id"]),\n            pair_id=int(close_step["pair_id"]),\n            tracking_lane=str(close_step["tracking_lane"]),\n            current_close_step_id=int(close_step["id"]),\n        )\n        if not source.get("resolved"):\n            raise ValueError(\n                "current-run 15m continuation source blocked: "\n                + "; ".join(source.get("reasons", []))\n            )\n        continuation_plan = _plan_continuation_jobs(\n            conn,\n            run_id=run_id,\n            close_step=close_step,\n            fifteen_m=source["window"],\n            continuation_seconds=continuation_seconds,\n        )\n        if not continuation_plan.get("enqueue_ok"):\n            raise ValueError(\n                "continuation planning blocked: "\n                + "; ".join(continuation_plan.get("reasons", []))\n            )\n        return support, continuation_plan\n    reason = disposition.evidence_label\n    continuation_plan = {\n        "enqueue_ok": False,\n        "planned_jobs": 0,\n        "verdict": "STOP_AFTER_15M",\n        "reason": reason,\n    }\n    return support, continuation_plan\n'''
replace_once(factory_path, old_natural, new_natural)
replace_once(
    factory_path,
    '''                if result.get("ok"):\n                    if pending["step_kind"] == "SNAPSHOT" and str(pending["step_key"]).endswith("_snapshot_00"):\n''',
    '''                if result.get("ok"):\n                    if pending["step_kind"] == "SNAPSHOT" and _operational_natural(config):\n                        result["support_5m_event_time"] = (\n                            _evaluate_event_time_5m_support_for_snapshot(\n                                conn, run_id=run_id, step=pending, result=result\n                            )\n                        )\n                    if pending["step_kind"] == "SNAPSHOT" and str(pending["step_key"]).endswith("_snapshot_00"):\n''',
)
replace_once(
    factory_path,
    '''                                    support, continuation_plan = (\n                                        _natural_disposition_schedule(\n                                            conn,\n                                            run_id=run_id,\n                                            close_step=close_row,\n                                            window_id=row_window_id,\n                                            continuation_seconds=_continuation_seconds,\n                                        )\n                                    )\n''',
    '''                                    support = _materialize_frozen_5m_support(\n                                        conn,\n                                        run_id=run_id,\n                                        close_step=close_row,\n                                        parent_window_id=row_window_id,\n                                    )\n                                    _, continuation_plan = (\n                                        _natural_disposition_schedule(\n                                            conn,\n                                            run_id=run_id,\n                                            close_step=close_row,\n                                            window_id=row_window_id,\n                                            continuation_seconds=_continuation_seconds,\n                                        )\n                                    )\n''',
)

print("CHECKPOINT6_EXACT_REPAIR_EDIT_PASS")
PY

# Runner is disposable and must not remain in the repair commit.
rm -f scripts/Run-Checkpoint6-CleanMemoryRepair.sh

# ---------------------------------------------------------------------------
# 3. Static + focused GREEN verification.
# ---------------------------------------------------------------------------
PYTHONPATH="$GREEN_WT/src" "$PYTHON" -m py_compile \
  src/printer_v1/memory/clean_object_promotion.py \
  src/printer_v1/operator_cli/checkpoint6_event_time_5m.py \
  src/printer_v1/operator_cli/lane_x8_5m_support_integration.py \
  src/printer_v1/operator_cli/one_command_15m_factory.py \
  tests/test_v2_9_8b_window_15m_checkpoint_6_collection_clean_memory_closeout.py

git diff --check

PYTHONPATH="$GREEN_WT/src" "$PYTHON" -m pytest \
  tests/test_v2_9_8b_window_15m_checkpoint_6_collection_clean_memory_closeout.py \
  tests/test_v2_9_7d_4b_conditional_support_only_5m_capture.py \
  tests/test_post_rc_lane_e2z_clean_memory_creation.py \
  tests/test_post_lane10_lane_x8_5m_support_integration.py \
  tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py \
  -q

echo 'CHECKPOINT6_FOCUSED_GREEN_PASS'

# Static invariant: natural final-15m disposition must not invoke retrospective
# 5m capture; event-time hooks must exist; locked capability vocabulary unchanged.
PYTHONPATH="$GREEN_WT/src" "$PYTHON" - <<'PY'
import inspect
from printer_v1.operator_cli import one_command_15m_factory as f
src = inspect.getsource(f._natural_disposition_schedule)
assert "_capture_same_stream_5m_support(" not in src
assert "derive_natural_disposition" in src
module = inspect.getsource(f)
assert "_evaluate_event_time_5m_support_for_snapshot" in module
assert "_materialize_frozen_5m_support" in module
print("CHECKPOINT6_ANTI_LOOKAHEAD_STATIC_PASS")
PY

EXPECTED=$'M\tsrc/printer_v1/memory/clean_object_promotion.py\nM\tsrc/printer_v1/operator_cli/lane_x8_5m_support_integration.py\nM\tsrc/printer_v1/operator_cli/one_command_15m_factory.py\nD\tscripts/Run-Checkpoint6-CleanMemoryRepair.sh\nM\ttests/test_post_rc_lane_e2z_clean_memory_creation.py'
ACTUAL="$(git status --short | sed -E 's/^(.)(.) /\1\2\t/' | sed $'s/^M \t/M\t/; s/^D \t/D\t/' | LC_ALL=C sort)"
EXPECTED_SORTED="$(printf '%s\n' "$EXPECTED" | LC_ALL=C sort)"
if [[ "$ACTUAL" != "$EXPECTED_SORTED" ]]; then
  echo 'CHECKPOINT6_MANIFEST_BLOCKED' >&2
  printf 'Expected:\n%s\nActual:\n%s\n' "$EXPECTED_SORTED" "$ACTUAL" >&2
  exit 1
fi

echo 'CHECKPOINT6_EXACT_MANIFEST_PASS'

git add \
  src/printer_v1/memory/clean_object_promotion.py \
  src/printer_v1/operator_cli/lane_x8_5m_support_integration.py \
  src/printer_v1/operator_cli/one_command_15m_factory.py \
  tests/test_post_rc_lane_e2z_clean_memory_creation.py \
  scripts/Run-Checkpoint6-CleanMemoryRepair.sh

git commit -m 'Repair Checkpoint 6 clean memory closeout'
REPAIR_COMMIT="$(git rev-parse HEAD)"
git push origin "HEAD:$BRANCH"

echo "CHECKPOINT6_REPAIR_COMMIT=$REPAIR_COMMIT"
echo 'CHECKPOINT6_CLEAN_MEMORY_REPAIR_GREEN_PASS'
echo 'CHECKPOINT6_CHECKPOINT7_NOT_STARTED'

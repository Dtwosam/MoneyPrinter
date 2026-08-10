from __future__ import annotations

from pathlib import Path

STANDARD = "src/printer_v1/operator_cli/operational_standard_4h.py"
FACTORY = "src/printer_v1/operator_cli/one_command_15m_factory.py"


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected Slice C hard-gate anchor missing in {path}: {old[:140]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# Continuity must come from the exact persisted 1h close result. Missing or
# malformed continuity is never allowed to default to CONTINUOUS.
replace_once(
    STANDARD,
    '''from printer_v1.snapshots.lifecycle_continuity import CONTINUITY_CONTINUOUS\n''',
    '''from printer_v1.snapshots.lifecycle_continuity import (\n    CONTINUITY_BLOCKED,\n    CONTINUITY_CONTINUOUS,\n    CONTINUITY_DIRTY,\n    CONTINUITY_UNKNOWN,\n)\n''',
)
replace_once(
    STANDARD,
    '''    context = _loads_mapping(physical["supporting_context_json"])\n    continuity = str(context.get("continuity_status") or CONTINUITY_CONTINUOUS)\n    lane = str(close["tracking_lane"] or context.get("tracking_lane") or "")\n''',
    '''    context = _loads_mapping(physical["supporting_context_json"])\n    continuity_payload = context.get("continuity")\n    continuity = (\n        str(continuity_payload.get("continuity_status") or "")\n        if isinstance(continuity_payload, Mapping)\n        else ""\n    )\n    if continuity not in {\n        CONTINUITY_CONTINUOUS,\n        CONTINUITY_DIRTY,\n        CONTINUITY_BLOCKED,\n        CONTINUITY_UNKNOWN,\n    }:\n        continuity = CONTINUITY_BLOCKED\n    lane = str(close["tracking_lane"] or context.get("tracking_lane") or "")\n''',
)

# B.2 already validates exact target/window/closing snapshot, evidence age, and
# source trace identity. Feed those authoritative facts into the continuation
# evaluator rather than manufacturing freshness/provenance booleans.
replace_once(
    STANDARD,
    '''        predecessor_complete=(str(physical["window_status"]) == "WINDOW_CLOSED"),\n        freshness_within_contract=True,\n        governed_provenance_traceable=True,\n        safety_context_present=bool(facts["safety_context_present"]),\n''',
    '''        predecessor_complete=(str(physical["window_status"]) == "WINDOW_CLOSED"),\n        freshness_within_contract=bool(safety.get("gate_accepted")),\n        governed_provenance_traceable=(\n            bool(safety.get("gate_accepted"))\n            and bool(safety.get("source_traces"))\n        ),\n        safety_context_present=bool(facts["safety_context_present"]),\n''',
)

# The standard planner persists the exact 0/1/2 eligible subset before any long
# work executes. Execution must consume that same durable subset budget, not the
# historical one-token cumulative budget helper.
anchor = '''def _enforce_budgets_before_step(conn: sqlite3.Connection, run_id: str, step: sqlite3.Row) -> None:\n'''
helper = '''def _standard_four_hour_cumulative_budget_for_run(\n    conn: sqlite3.Connection, run_id: str,\n) -> dict[str, Any]:\n    """Resolve the exact standard 4h subset budget from durable campaign truth."""\n    config = _load_run_config(conn, run_id)\n    campaign_id = str(config.get("campaign_id") or "").strip()\n    campaign_run_id = str(config.get("campaign_run_id") or "").strip()\n    cycle_id = str(config.get("cycle_id") or "").strip()\n    if not all((campaign_id, campaign_run_id, cycle_id, run_id)):\n        raise ValueError("standard four-hour execution budget identity is incomplete")\n\n    from printer_v1.operator_cli.one_token_4h_runtime import (\n        load_standard_four_hour_eligibility_manifests,\n        standard_campaign_lifecycle_budget,\n    )\n\n    slots = conn.execute(\n        """SELECT token_slot_id,token_row_id,pair_row_id,slot_ordinal\n           FROM printer_memory_factory_campaign_token_slots\n           WHERE campaign_id=? AND run_id=? AND cycle_id=?\n           ORDER BY slot_ordinal""",\n        (campaign_id, campaign_run_id, cycle_id),\n    ).fetchall()\n    if len(slots) != 2 or {int(row["slot_ordinal"]) for row in slots} != {1, 2}:\n        raise ValueError("standard four-hour execution budget requires exact two campaign slots")\n\n    manifests = load_standard_four_hour_eligibility_manifests(\n        conn,\n        campaign_id=campaign_id,\n        run_id=campaign_run_id,\n        cycle_id=cycle_id,\n        factory_run_id=run_id,\n    )\n    if manifests is None:\n        raise ValueError("standard four-hour execution budget requires durable eligibility manifest")\n\n    lanes: list[str] = []\n    mask: list[bool] = []\n    for slot in slots:\n        slot_id = str(slot["token_slot_id"])\n        closes = conn.execute(\n            """SELECT tracking_lane FROM printer_memory_factory_run_steps\n               WHERE run_id=? AND token_id=? AND pair_id=?\n                 AND step_kind='CONTINUATION_CLOSE' AND step_status='SUCCEEDED'\n               ORDER BY id""",\n            (run_id, int(slot["token_row_id"]), int(slot["pair_row_id"])),\n        ).fetchall()\n        if len(closes) != 1:\n            raise ValueError(\n                f"standard four-hour execution budget close identity missing/ambiguous for {slot_id}"\n            )\n        manifest = manifests.get(slot_id)\n        if manifest is None or type(manifest.get("eligible")) is not bool:\n            raise ValueError(\n                f"standard four-hour execution budget manifest invalid for {slot_id}"\n            )\n        lanes.append(str(closes[0]["tracking_lane"]))\n        mask.append(bool(manifest["eligible"]))\n\n    return standard_campaign_lifecycle_budget(\n        (lanes[0], lanes[1]), (mask[0], mask[1])\n    )\n\n\n'''
replace_once(FACTORY, anchor, helper + anchor)

replace_once(
    FACTORY,
    '''        cumulative = _cumulative_lifecycle_budget_for_run(conn, run_id, lane)\n        phase_used = int(conn.execute(\n''',
    '''        if bool(config.get("standard_four_hour_campaign")):\n            try:\n                cumulative = _standard_four_hour_cumulative_budget_for_run(\n                    conn, run_id\n                )\n            except ValueError as exc:\n                raise _GlobalStop(\n                    STOP_BUDGET, scope="STANDARD_FOUR_HOUR_SUBSET", detail=str(exc),\n                ) from exc\n        else:\n            cumulative = _cumulative_lifecycle_budget_for_run(conn, run_id, lane)\n        phase_used = int(conn.execute(\n''',
)

# The operational caller owns lease/DB/integrity health. Re-check cooperative
# cancellation immediately before releasing a committed two-slot 1h barrier so
# an unconfirmed lease cannot create WINDOW_4H work.
replace_once(
    FACTORY,
    '''                        barrier = run_standard_four_hour_campaign_barrier(\n''',
    '''                        _check_cancellation(cancellation_probe)\n                        barrier = run_standard_four_hour_campaign_barrier(\n''',
)

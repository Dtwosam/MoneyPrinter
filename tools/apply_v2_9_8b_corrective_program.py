#!/usr/bin/env python3
"""Apply the approved V2-9.8B corrective program with exact-text guards.

This script is branch-scoped implementation tooling.  Every replacement is
fail-closed: if the audited baseline text is absent or already differs, abort
instead of guessing.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text()
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"PATCH_GUARD_FAILED:{path}:expected-one-found-{count}")
    target.write_text(text.replace(old, new, 1))


# A1/A2 — later-cycle fresh MOE carry-forward + honest temporal refresh.
replace_once(
    "src/printer_v1/discovery/eligible_token_supply.py",
    "from datetime import datetime, timezone\n",
    "from datetime import datetime, timedelta, timezone\n",
)

replace_once(
    "src/printer_v1/discovery/eligible_token_supply.py",
    """    connection = _connect(db_path)\n    try:\n        if permanent_availability and (\n""",
    """    connection = _connect(db_path)\n    try:\n        # V2-9.8B corrective program: a later cooperative quantum must not\n        # forget fresh protocol-confirmed MOE persisted by an earlier quantum.\n        # Rehydrate only this exact Cycle-2 campaign and still apply the existing\n        # tracking precheck. Freeze/selection remain downstream authorities.\n        if (\n            permanent_availability\n            and cooperative_resume\n            and str(execution_id or \"\").endswith(\":c0002\")\n            and str(campaign_id or \"\").strip()\n        ):\n            from printer_v1.discovery.later_cycle_fresh_inventory import (\n                load_campaign_fresh_moe_candidates,\n            )\n            from printer_v1.lifecycle.contracts import TokenLifecycleState\n            from printer_v1.lifecycle.tracking_queue import (\n                HANDOFF_COOLDOWN_REOPEN_REQUIRED,\n                assess_tracking_handoff_by_identity,\n            )\n\n            for candidate in load_campaign_fresh_moe_candidates(\n                connection, campaign_id=str(campaign_id), at=now\n            ):\n                mint = str(candidate[\"mint\"])\n                pool = str(candidate[\"pumpswap_pool\"])\n                if mint in campaign_eligible:\n                    continue\n                assessment = assess_tracking_handoff_by_identity(\n                    connection,\n                    token_mint=mint,\n                    pair_address=pool,\n                    tracking_lane=TokenLifecycleState.TRACK_NORMAL,\n                    assessed_at=started_at,\n                )\n                disposition = {\n                    \"category\": assessment.category,\n                    \"eligible_for_evidence\": assessment.eligible,\n                    \"tracking_queue_id\": assessment.queue_id,\n                    \"tracking_queue_status\": assessment.queue_status,\n                    \"requalification_required\": assessment.requalification_eligible,\n                    \"cooldown_until\": assessment.cooldown_until,\n                    \"historical_cooldown_expiry_derived\": (\n                        assessment.historical_cooldown_expiry_derived\n                    ),\n                }\n                tracking_dispositions[mint] = disposition\n                evaluated_mints.add(mint)\n                if not assessment.eligible:\n                    reason = str(assessment.reason_code or assessment.category)\n                    rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1\n                    if reason == HANDOFF_COOLDOWN_REOPEN_REQUIRED:\n                        cooldown_skips += 1\n                    rejected = dict(candidate)\n                    rejected.update(\n                        eligible=False,\n                        rejection=reason,\n                        tracking_handoff=disposition,\n                    )\n                    all_candidates.append(rejected)\n                    continue\n                accepted = dict(candidate)\n                accepted[\"tracking_handoff\"] = disposition\n                campaign_eligible[mint] = accepted\n                all_candidates.append(accepted)\n\n        if permanent_availability and (\n""",
)

replace_once(
    "src/printer_v1/discovery/eligible_token_supply.py",
    """            acquisition_ledger = AcquisitionLedger(\n                started_at=now,\n                acquisition_deadline_at=str(\n""",
    """            acquisition_ledger = AcquisitionLedger(\n                # Preserve the original bounded attempt clock across cooperative\n                # quanta. The deadline is authoritative and the duration is fixed.\n                started_at=(\n                    (deadline_dt - timedelta(\n                        seconds=PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS\n                    )).isoformat()\n                    if deadline_dt is not None\n                    else now\n                ),\n                acquisition_deadline_at=str(\n""",
)

replace_once(
    "src/printer_v1/discovery/eligible_token_supply.py",
    """        eligible_list = list(campaign_eligible.values())\n        # Deterministic non-ranked order by mint identity for handoff stability.\n""",
    """        # Before certifying a shortage in cooperative later-cycle mode,\n        # give the durable temporal owner one chance to own the next lawful\n        # 600-second refresh. This is a Scheduler yield, not a retry.\n        remaining_refresh_window = False\n        if (\n            cooperative_quantum\n            and temporal_refresh_owner is not None\n            and acquisition_ledger is not None\n            and len(campaign_eligible) < required_token_capacity\n            and last_stop_reason not in {\n                WAITING_FOR_ELIGIBLE_SUPPLY,\n                ACQUISITION_QUANTUM_YIELDED,\n            }\n            and _ops_remaining() > 0\n        ):\n            remaining = _duration_remaining()\n            interval = int(\n                getattr(temporal_refresh_owner, \"refresh_interval_seconds\", 600)\n            )\n            remaining_refresh_window = bool(\n                remaining is not None and remaining > float(interval)\n            )\n            if remaining_refresh_window:\n                _request_temporal_refresh(\n                    \"NO_ADDITIONAL_UNIQUE_CANDIDATES_REACHABLE\"\n                )\n\n        eligible_list = list(campaign_eligible.values())\n        # Deterministic non-ranked order by mint identity for handoff stability.\n""",
)

# A3 — weaker unresolved observations may never demote resolved identity.
replace_once(
    "src/printer_v1/discovery/permanent_discovery_availability.py",
    """        conflicts: dict[str, dict[str, str]] = {}\n        for attribute, column in identity_fields:\n            old = str(prior_map[column])\n            new = str(getattr(observation, attribute))\n            unresolved = old.startswith(\"UNRESOLVED_\") or old.startswith(\"UNKNOWN_\")\n            if old != new and not unresolved:\n                conflicts[attribute] = {\"preserved\": old, \"observed\": new}\n        if conflicts:\n""",
    """        conflicts: dict[str, dict[str, str]] = {}\n        preserved_identity_values: dict[str, str] = {}\n        for attribute, column in identity_fields:\n            old = str(prior_map[column])\n            new = str(getattr(observation, attribute))\n            old_unresolved = old.startswith(\"UNRESOLVED_\") or old.startswith(\"UNKNOWN_\")\n            new_unresolved = new.startswith(\"UNRESOLVED_\") or new.startswith(\"UNKNOWN_\")\n            if old == new:\n                continue\n            if not old_unresolved and new_unresolved:\n                # A weaker observation cannot erase a stronger resolved fact.\n                preserved_identity_values[attribute] = old\n                continue\n            if old_unresolved and not new_unresolved:\n                # Stronger exact evidence upgrades the unresolved value.\n                continue\n            if not old_unresolved and not new_unresolved:\n                conflicts[attribute] = {\"preserved\": old, \"observed\": new}\n        if preserved_identity_values and not conflicts:\n            observation = replace(observation, **preserved_identity_values)\n        if conflicts:\n""",
)

# B3 — persist real WINDOW_4H cadence through the same U2 owner as 15m/1h.
replace_once(
    "src/printer_v1/operator_cli/one_token_4h_runtime.py",
    """def run_4h_quality_gates(db_path: str, window_id: int) -> dict[str, Any]:\n    \"\"\"Run E2Q then Lane Q then Lane K clean creation, in that order.\"\"\"\n    from printer_v1.operator_cli.e2q_memory_window_audit import (\n""",
    """def run_4h_quality_gates(db_path: str, window_id: int) -> dict[str, Any]:\n    \"\"\"Persist U2 coverage, then run E2Q, Lane Q and E2Z clean creation.\"\"\"\n    from printer_v1.operator_cli.lane_u2_coverage_audit_persistence import (\n        LANE_U2_STATUS_COMPLETED,\n        persist_coverage_for_windows,\n    )\n    from printer_v1.operator_cli.e2q_memory_window_audit import (\n""",
)

replace_once(
    "src/printer_v1/operator_cli/one_token_4h_runtime.py",
    """    connection = sqlite3.connect(db_path)\n    connection.row_factory = sqlite3.Row\n    try:\n""",
    """    lane_u2 = persist_coverage_for_windows(\n        db_path,\n        [window_id],\n        operator_approved=True,\n        production_mode=True,\n        allow_disabled_policy_evaluation=True,\n    )\n    if (\n        lane_u2.get(\"lane_u2_status\") != LANE_U2_STATUS_COMPLETED\n        or window_id not in lane_u2.get(\"coverage_pass_ids\", [])\n    ):\n        return {\n            \"lane_k_status\": \"LANE_K_BLOCKED\",\n            \"lane_u2\": lane_u2,\n            \"e2q\": None,\n            \"lane_q\": None,\n            \"memory\": None,\n        }\n\n    connection = sqlite3.connect(db_path)\n    connection.row_factory = sqlite3.Row\n    try:\n""",
)

replace_once(
    "src/printer_v1/operator_cli/one_token_4h_runtime.py",
    """        return {\"lane_k_status\": \"LANE_K_BLOCKED\", \"e2q\": e2q, \"lane_q\": lane_q, \"memory\": None}\n""",
    """        return {\"lane_k_status\": \"LANE_K_BLOCKED\", \"lane_u2\": lane_u2, \"e2q\": e2q, \"lane_q\": lane_q, \"memory\": None}\n""",
)
replace_once(
    "src/printer_v1/operator_cli/one_token_4h_runtime.py",
    """    return {\"lane_k_status\": \"LANE_K_COMPLETED\", \"e2q\": e2q, \"lane_q\": lane_q, \"memory\": memory}\n""",
    """    return {\"lane_k_status\": \"LANE_K_COMPLETED\", \"lane_u2\": lane_u2, \"e2q\": e2q, \"lane_q\": lane_q, \"memory\": memory}\n""",
)

# C — persist categorical completeness accounting with every flow snapshot.
replace_once(
    "src/printer_v1/trading_flow/recorder.py",
    """from printer_v1.trading_flow.parser import normalize_trading_flow_payload, to_timestamp\n""",
    """from printer_v1.trading_flow.parser import normalize_trading_flow_payload, to_timestamp\nfrom printer_v1.trading_flow.evidence_completeness import (\n    plan_optional_wallet_flow_enrichment,\n)\n""",
)
replace_once(
    "src/printer_v1/trading_flow/recorder.py",
    """    normalized[\"flow_memory_gate_label\"] = classify_flow_memory_gate(normalized, current_time).value\n\n    with connect(db_path_or_conn) as connection:\n""",
    """    normalized[\"flow_memory_gate_label\"] = classify_flow_memory_gate(normalized, current_time).value\n    # Current approved pair-snapshot sources do not deterministically expose\n    # unique wallets or split buy/sell volume. Record that the optional gap was\n    # evaluated rather than silently ignoring it. A future approved free\n    # enricher can flip the availability input without changing clean-memory\n    # eligibility or inventing values.\n    normalized[\"optional_wallet_flow_enrichment\"] = (\n        plan_optional_wallet_flow_enrichment(\n            normalized,\n            approved_free_enricher_available=False,\n            source_budget_available=True,\n        ).to_dict()\n    )\n\n    with connect(db_path_or_conn) as connection:\n""",
)

print("V2_9_8B_CORRECTIVE_PATCH_APPLIED")

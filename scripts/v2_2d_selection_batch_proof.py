"""V2-2D Bounded discovery/selection proof script.

Reads existing discovery candidates from the LIVE DB (read-only) and
persists a selection batch to the PROOF DB only.

Constraints:
  - No source fetching, scheduler calls, or runtime commands.
  - No memory generation, retrieval, or paper decisions.
  - No BUY/SELL/HOLD, positions, trades, audits, PnL.
  - No scoring/ranking/confidence/weighted logic.
  - ANSEM (token_id 13) excluded per V2-2D STNP preflight.
  - Pairs 16, 17 (BONK extra) and pair 18 (FARM extra) excluded.
  - All operations on isolated PROOF DB only.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import uuid
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from printer_v1.discovery.selection_batch import (
    BUCKET_A1,
    GROUP_A_BUCKETS,
    ITEM_STATUS_REJECTED,
    ITEM_STATUS_SELECTED,
    REJECTION_BATCH_QUOTA_EXCEEDED,
    REJECTION_MANUAL_EXCLUSION,
    assign_bucket,
    build_batch_item,
    build_candidate_universe_summary,
    check_cooldown_archive_gate,
    check_watch_only_promotion_gate,
    classify_same_token_new_pair,
    derive_asset_class,
    persist_selection_batch,
    validate_batch_quota,
)

LIVE_DB = "data/printer_v1.sqlite3"
PROOF_DB = "data/printer_v1_v2_2d_proof.sqlite3"

# STNP exclusions per V2-2D preflight:
# token_id 13 (ANSEM): excluded entirely
# Pairs 16, 17 (BONK extra) and 18 (FARM extra): no discovery candidates anyway
EXCLUDED_TOKEN_IDS = frozenset({13})
EXCLUDED_PAIR_IDS = frozenset({16, 17, 18})


def read_locked_row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    locked_tables = [
        "printer_memory_windows",
        "printer_paper_decisions",
        "printer_paper_positions",
        "printer_paper_trade_audits",
    ]
    counts: dict[str, int] = {}
    for tbl in locked_tables:
        try:
            counts[tbl] = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        except Exception:
            counts[tbl] = -1
    return counts


def load_candidates(live_conn: sqlite3.Connection) -> list[dict]:
    rows = live_conn.execute("""
        SELECT
            dc.id AS discovery_candidate_id,
            dc.token_id,
            dc.pair_id,
            dc.discovery_action,
            dc.source_name,
            dc.source_channel,
            dc.source_response_id,
            dc.lifecycle_state,
            dc.tracking_lane,
            dc.normalized_candidate_payload_json,
            t.token_mint,
            t.symbol,
            p.pair_address
        FROM printer_discovery_candidates dc
        JOIN printer_tokens t ON dc.token_id = t.id
        JOIN printer_pairs p ON dc.pair_id = p.id
        ORDER BY dc.id
    """).fetchall()

    candidates = []
    for r in rows:
        payload = json.loads(r["normalized_candidate_payload_json"] or "{}")
        c = dict(payload)
        c["discovery_candidate_id"] = r["discovery_candidate_id"]
        c["token_id"] = r["token_id"]
        c["pair_id"] = r["pair_id"]
        c["discovery_action"] = r["discovery_action"]
        c["source_name"] = c.get("source_name") or r["source_name"]
        c["source_channel"] = c.get("source_channel") or r["source_channel"]
        c["source_response_id"] = r["source_response_id"]
        c["lifecycle_state"] = r["lifecycle_state"]
        c["tracking_lane"] = r["tracking_lane"]
        c["token_mint"] = r["token_mint"]
        c["pair_address"] = r["pair_address"]
        c["symbol"] = r["symbol"]
        c["chain"] = "solana"
        candidates.append(c)
    return candidates


def run_proof() -> dict:
    print("=" * 70)
    print("V2-2D Bounded Discovery/Selection Proof")
    print("=" * 70)
    print(f"Live DB (read-only): {LIVE_DB}")
    print(f"Proof DB (write):    {PROOF_DB}")
    print()

    live_conn = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    live_conn.row_factory = sqlite3.Row
    live_conn.execute("PRAGMA query_only = ON")

    proof_conn = sqlite3.connect(PROOF_DB)
    proof_conn.row_factory = sqlite3.Row
    proof_conn.execute("PRAGMA foreign_keys = ON")

    # --- Row counts BEFORE ---
    before = read_locked_row_counts(live_conn)
    print("=== LOCKED TABLE ROW COUNTS (BEFORE) ===")
    for tbl, n in before.items():
        print(f"  {tbl}: {n}")
    batch_before = proof_conn.execute(
        "SELECT COUNT(*) FROM printer_selection_batches"
    ).fetchone()[0]
    items_before = proof_conn.execute(
        "SELECT COUNT(*) FROM printer_selection_batch_items"
    ).fetchone()[0]
    print(f"  printer_selection_batches (proof): {batch_before}")
    print(f"  printer_selection_batch_items (proof): {items_before}")
    print()

    # --- Load candidates ---
    all_candidates = load_candidates(live_conn)
    print(f"=== CANDIDATE UNIVERSE: {len(all_candidates)} discovery candidates ===")

    selected_items = []
    rejected_items = []

    for c in all_candidates:
        tok_id = c["token_id"]
        pair_id = c["pair_id"]
        sym = c.get("symbol") or "?"
        action = c.get("discovery_action") or "?"
        tracking_lane = c.get("tracking_lane") or action

        # 1. STNP exclusion gate (per V2-2D preflight)
        if tok_id in EXCLUDED_TOKEN_IDS:
            item = build_batch_item(
                c,
                item_status=ITEM_STATUS_REJECTED,
                rejection_reason=REJECTION_MANUAL_EXCLUSION,
                tracking_lane=tracking_lane,
                lane_rationale="STNP_PREFLIGHT_EXCLUDE_TOKEN_13_ANSEM",
            )
            rejected_items.append(item)
            print(
                f"  REJECTED  tok={tok_id} pair={pair_id} sym={sym} "
                f"reason=MANUAL_EXCLUSION(ANSEM_TOKEN_13)"
            )
            continue

        if pair_id in EXCLUDED_PAIR_IDS:
            item = build_batch_item(
                c,
                item_status=ITEM_STATUS_REJECTED,
                rejection_reason=REJECTION_MANUAL_EXCLUSION,
                tracking_lane=tracking_lane,
                lane_rationale="STNP_PREFLIGHT_EXCLUDE_UNRESOLVED_PAIR",
            )
            rejected_items.append(item)
            print(
                f"  REJECTED  tok={tok_id} pair={pair_id} sym={sym} "
                f"reason=MANUAL_EXCLUSION(UNRESOLVED_PAIR)"
            )
            continue

        # 2. Cooldown/archive gate
        lifecycle_state = c.get("lifecycle_state")
        cooldown_ok, cooldown_rejection = check_cooldown_archive_gate(
            lifecycle_state,
            cooldown_reopened=False,
            cooldown_reopen_reason=None,
        )
        if not cooldown_ok:
            item = build_batch_item(
                c,
                item_status=ITEM_STATUS_REJECTED,
                rejection_reason=cooldown_rejection,
                tracking_lane=tracking_lane,
            )
            rejected_items.append(item)
            print(
                f"  REJECTED  tok={tok_id} pair={pair_id} sym={sym} "
                f"reason={cooldown_rejection}"
            )
            continue

        # 3. WATCH_ONLY promotion gate
        discovery_action = c.get("discovery_action")
        watch_ok, watch_rejection = check_watch_only_promotion_gate(
            tracking_lane, discovery_action
        )
        if not watch_ok:
            item = build_batch_item(
                c,
                item_status=ITEM_STATUS_REJECTED,
                rejection_reason=watch_rejection,
                tracking_lane=tracking_lane,
            )
            rejected_items.append(item)
            print(
                f"  REJECTED  tok={tok_id} pair={pair_id} sym={sym} "
                f"reason={watch_rejection}"
            )
            continue

        # 4. Bucket assignment
        bucket_id, bucket_name = assign_bucket(c)
        asset_class = derive_asset_class(bucket_id)

        # 5. A1 pre-screening: if bucket is A1, hold for quota check
        # (A1 can only be included if A2/A3/A4 counterpart exists in pool)
        # We will resolve this after scanning the full pool.
        c["_assigned_bucket"] = bucket_id
        c["_assigned_bucket_name"] = bucket_name
        c["_assigned_asset_class"] = asset_class
        c["_tracking_lane"] = tracking_lane

        print(
            f"  GATE_PASS tok={tok_id} pair={pair_id} sym={sym} "
            f"bucket={bucket_id}/{bucket_name} lane={tracking_lane}"
        )

    # Separate gate-passing candidates from rejected
    gate_passing = [c for c in all_candidates if "_assigned_bucket" in c]
    print(f"\n  Gate-passing candidates: {len(gate_passing)}")
    print(f"  Already rejected: {len(rejected_items)}")

    # --- A1 quota screening ---
    print()
    print("=== QUOTA SCREENING ===")

    a1_candidates = [c for c in gate_passing if c["_assigned_bucket"] == BUCKET_A1]
    non_a1_candidates = [
        c for c in gate_passing if c["_assigned_bucket"] != BUCKET_A1
    ]
    non_a1_buckets = [c["_assigned_bucket"] for c in non_a1_candidates]
    has_trap_in_non_a1 = any(b in {"A2", "A3", "A4"} for b in non_a1_buckets)

    print(f"  A1 (FAST_PUMP_FOLLOW) candidates: {len(a1_candidates)}")
    print(f"  Non-A1 candidates: {len(non_a1_candidates)}")
    print(f"  Trap/failure buckets (A2/A3/A4) in non-A1 pool: {has_trap_in_non_a1}")

    # If no trap/failure exists anywhere in the pool, A1s cannot be selected
    # because the batch would violate GROUP_A_PRESENT_BUT_NO_TRAP_FAILURE_BUCKET.
    if a1_candidates and not has_trap_in_non_a1:
        print(
            "  QUOTA RULING: A1 candidates cannot be selected — "
            "no A2/A3/A4 counterpart exists in the pool. "
            "All A1 candidates rejected with BATCH_QUOTA_EXCEEDED."
        )
        for c in a1_candidates:
            item = build_batch_item(
                c,
                item_status=ITEM_STATUS_REJECTED,
                primary_bucket=c["_assigned_bucket"],
                bucket_name=c["_assigned_bucket_name"],
                asset_class=c["_assigned_asset_class"],
                rejection_reason=REJECTION_BATCH_QUOTA_EXCEEDED,
                tracking_lane=c["_tracking_lane"],
                lane_rationale=(
                    "A1_NO_TRAP_COUNTERPART: pool has no A2/A3/A4 to satisfy "
                    "GROUP_A_PRESENT_BUT_NO_TRAP_FAILURE_BUCKET quota rule"
                ),
            )
            rejected_items.append(item)
    else:
        # If trap exists, A1s are eligible (up to cap of 2)
        for c in a1_candidates:
            c["_selected"] = True

    # Build selected items from non-A1 gate-passing candidates
    for c in non_a1_candidates:
        item = build_batch_item(
            c,
            item_status=ITEM_STATUS_SELECTED,
            primary_bucket=c["_assigned_bucket"],
            bucket_name=c["_assigned_bucket_name"],
            asset_class=c["_assigned_asset_class"],
            selection_reason=_selection_reason(c["_assigned_bucket"]),
            tracking_lane=c["_tracking_lane"],
            lane_rationale=_lane_rationale(c),
        )
        selected_items.append(item)

    # Add A1 selected (if any survived the quota screening above)
    for c in [x for x in a1_candidates if x.get("_selected")]:
        item = build_batch_item(
            c,
            item_status=ITEM_STATUS_SELECTED,
            primary_bucket=c["_assigned_bucket"],
            bucket_name=c["_assigned_bucket_name"],
            asset_class=c["_assigned_asset_class"],
            selection_reason="FAST_ACTIVITY_CONFIRMED",
            tracking_lane=c["_tracking_lane"],
            lane_rationale=_lane_rationale(c),
        )
        selected_items.append(item)

    print(f"\n  Proposed selected count: {len(selected_items)}")
    print(f"  Proposed rejected count: {len(rejected_items)}")

    # --- Final quota validation ---
    print()
    print("=== QUOTA VALIDATION ===")
    corpus_episodes = 30  # from V2-0 audit: 30 clean WINDOW_15M episodes exist

    quota_ok, violations = validate_batch_quota(
        selected_items, min_corpus_episodes=corpus_episodes
    )
    if quota_ok:
        print(f"  PASS — batch satisfies all quota rules")
    else:
        print(f"  VIOLATIONS: {violations}")

    # --- Universe summary ---
    # Add bucket info to all_candidates for summary
    for c in all_candidates:
        if "_assigned_bucket" in c:
            c["primary_bucket"] = c["_assigned_bucket"]
            c["asset_class"] = c["_assigned_asset_class"]

    universe_summary = build_candidate_universe_summary(
        all_candidates, selected_items, rejected_items
    )

    # --- Persist to proof DB ---
    print()
    print("=== PERSISTING TO PROOF DB ===")
    batch_id = f"v2_2d_proof_{uuid.uuid4().hex[:12]}"
    result = persist_selection_batch(
        proof_conn,
        batch_id=batch_id,
        items=selected_items + rejected_items,
        universe_summary=universe_summary,
        operator_approved=False,
        window_kind="WINDOW_15M",
        pool_diversity_notes=json.dumps(universe_summary.get("pool_diversity_notes", [])),
        pool_quality_notes=json.dumps(universe_summary.get("pool_quality_notes", [])),
    )
    proof_conn.commit()
    print(f"  batch_id: {batch_id}")
    print(f"  selected: {result['selected_count']}")
    print(f"  rejected: {result['rejected_count']}")
    print(f"  total:    {result['total_items']}")

    # --- Row counts AFTER ---
    print()
    print("=== LOCKED TABLE ROW COUNTS (AFTER) ===")
    after = read_locked_row_counts(live_conn)
    for tbl in before:
        b = before[tbl]
        a = after.get(tbl, b)
        delta = a - b if b >= 0 and a >= 0 else "?"
        flag = " DELTA_VIOLATION" if delta not in (0, "?") else ""
        print(f"  {tbl}: {a} (delta={delta}){flag}")

    batch_after = proof_conn.execute(
        "SELECT COUNT(*) FROM printer_selection_batches"
    ).fetchone()[0]
    items_after = proof_conn.execute(
        "SELECT COUNT(*) FROM printer_selection_batch_items"
    ).fetchone()[0]
    print(f"  printer_selection_batches (proof): {batch_after} (delta={batch_after - batch_before})")
    print(f"  printer_selection_batch_items (proof): {items_after} (delta={items_after - items_before})")

    # --- Print selected/rejected detail ---
    print()
    print("=== SELECTED ITEMS ===")
    for item in selected_items:
        print(
            f"  tok={item['token_id']} pair={item['pair_id']} "
            f"bucket={item['primary_bucket']} "
            f"asset={item['asset_class']} "
            f"lane={item['tracking_lane']} "
            f"reason={item['selection_reason']}"
        )

    print()
    print("=== REJECTED ITEMS ===")
    for item in rejected_items:
        print(
            f"  tok={item['token_id']} pair={item['pair_id']} "
            f"bucket={item.get('primary_bucket') or 'pre-gate'} "
            f"lane={item.get('tracking_lane') or '?'} "
            f"reason={item['rejection_reason']}"
        )

    live_conn.close()
    proof_conn.close()

    return {
        "batch_id": batch_id,
        "quota_ok": quota_ok,
        "violations": violations,
        "selected_count": len(selected_items),
        "rejected_count": len(rejected_items),
        "universe_summary": universe_summary,
        "before_locked": before,
        "after_locked": after,
    }


def _selection_reason(bucket_id: str) -> str:
    mapping = {
        "D1": "DEAD_TOKEN_PROTECTION_SAMPLE",
        "D2": "REVIVAL_DETECTED",
        "D3": "MIGRATION_DETECTED",
        "D4": "SUSPICIOUS_SAFETY_SIGNAL",
        "B1": "VOLUME_RISING_TREND",
        "B2": "VOLUME_DECAY_PATTERN",
        "B3": "TRANSACTION_SPIKE_DETECTED",
        "B4": "VOLUME_DECAY_PATTERN",
        "B5": "CONSOLIDATION_PATTERN",
        "C1": "LIQUIDITY_ABOVE_THRESHOLD",
        "C2": "LIQUIDITY_BELOW_THRESHOLD",
        "C3": "LIQUIDITY_REMOVED_SIGNAL",
        "E1": "EXIT_REALISM_SAMPLE",
        "E2": "UNREALISTIC_EXIT_EVIDENCE",
        "A1": "FAST_ACTIVITY_CONFIRMED",
        "A2": "WICK_ONLY_EVIDENCE",
        "A3": "LATE_ENTRY_RISK",
        "A4": "FAILED_PUMP_EVIDENCE",
    }
    return mapping.get(bucket_id, "NORMAL_ACTIVITY_BASELINE")


def _lane_rationale(c: dict) -> str:
    lane = c.get("_tracking_lane") or c.get("tracking_lane") or "?"
    bucket = c.get("_assigned_bucket") or "?"
    ch = c.get("source_channel") or c.get("source_name") or "unknown"
    return f"lane={lane} bucket={bucket} source={ch}"


if __name__ == "__main__":
    result = run_proof()
    print()
    print("=== PROOF COMPLETE ===")
    print(f"  quota_ok:      {result['quota_ok']}")
    print(f"  selected:      {result['selected_count']}")
    print(f"  rejected:      {result['rejected_count']}")
    print(f"  batch_id:      {result['batch_id']}")
    if result["violations"]:
        print(f"  violations:    {result['violations']}")
    print()
    print("Locked table deltas:")
    for tbl, b in result["before_locked"].items():
        a = result["after_locked"].get(tbl, b)
        d = a - b if b >= 0 and a >= 0 else "?"
        print(f"  {tbl}: {d}")

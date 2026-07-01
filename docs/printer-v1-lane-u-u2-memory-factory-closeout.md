# Printer V1 Lane U / U2 Memory Factory Closeout

## Anchor

- Current HEAD: ef9c5fe Add Lane U2 E2Y group selection
- Current tag on HEAD: printer-v1-lane-u2-e2y-group-selection

## Scope

This checkpoint closes the current governed Memory Factory proof path after Lane U and Lane U2.

It records that Printer V1 can now move from an operator-approved token through real 15m evidence windows into clean memory episodes while preserving all V1 financial and retrieval locks.

## Confirmed path

- Operator-approved token list used.
- Real WINDOW_15M collection used.
- WINDOW_5M_MICRO_EVENT remained support-only.
- Longer windows remained disabled for real collection.
- Source path remained governed.
- No live wallet.
- No private keys.
- No real funds.
- No live trading.
- No paid API dependency.
- No scoring, ranking, confidence, or weighted decision system.
- No BUY / SELL / HOLD unlock.
- No paper decisions.
- No paper positions.
- No trade events.
- No PnL.
- No retrieval activation.

## Committed checkpoints

- c50a059 — Add Lane U2 coverage audit persistence
  - Tag: printer-v1-lane-u2-coverage-audit-persistence

- ef9c5fe — Add Lane U2 E2Y group selection
  - Tag: printer-v1-lane-u2-e2y-group-selection

## Proof summary

The isolated proof DB showed the following final safe path:

1. Lane U created real WINDOW_15M memory windows from governed snapshots.
2. Lane U2 persisted coverage and gap audits.
3. Coverage-blocked windows were downgraded to dirty/audit-only.
4. E2Y selected the qualifying same-token/same-pair candidate group.
5. E2Z created clean memory episodes.
6. A second replay was idempotent and created no duplicate episodes.
7. Financial/retrieval/paper-trading locks remained zero.

## DB audit

`	ext
integrity_check=ok
counts={"printer_episodes": 6, "printer_memory_retrieval_matches": 0, "printer_memory_retrieval_queries": 0, "printer_memory_windows": 9, "printer_pairs": 2, "printer_paper_audit_reports": 0, "printer_paper_decisions": 0, "printer_paper_pl_calculations": "TABLE_MISSING", "printer_paper_positions": 0, "printer_paper_trade_audits": 0, "printer_paper_trade_events": 0, "printer_snapshot_gap_audits": 94, "printer_snapshot_window_coverage": 9, "printer_source_requests": 129, "printer_source_responses": 125, "printer_token_snapshots": 125, "printer_tokens": 1}

pair_window_map:
{"coverage_blocked_windows": 1, "coverage_pass_windows": 6, "first_window_id": 1, "last_window_id": 9, "pair_address": "FnzKY6x7entQ1eR3D225dQyT7ybfka4PskBMQhb8L3CC", "pair_id": 1, "token_id": 1, "total_windows": 7}
{"coverage_blocked_windows": 1, "coverage_pass_windows": 1, "first_window_id": 5, "last_window_id": 6, "pair_address": "eVEfwEGHf7REoV3wtHjdxgx3oWAbuA7wEHEhCUhpB1H", "pair_id": 2, "token_id": 1, "total_windows": 2}

memory_window_summary:
{"actual_snapshot_count": 12, "count": 6, "coverage_state": "COVERAGE_PASS", "data_quality_label": "CLEAN_DATA", "do_not_train": 0, "expected_snapshot_count": 10, "memory_status": "PARTIAL_MEMORY", "missing_snapshot_count": 0, "window_kind": "WINDOW_15M"}
{"actual_snapshot_count": 10, "count": 2, "coverage_state": "COVERAGE_BLOCKED", "data_quality_label": "MISSING_CRITICAL_DATA", "do_not_train": 1, "expected_snapshot_count": 10, "memory_status": "DIRTY_MEMORY", "missing_snapshot_count": 0, "window_kind": "WINDOW_15M"}
{"actual_snapshot_count": 11, "count": 1, "coverage_state": "COVERAGE_PASS", "data_quality_label": "CLEAN_DATA", "do_not_train": 0, "expected_snapshot_count": 10, "memory_status": "PARTIAL_MEMORY", "missing_snapshot_count": 0, "window_kind": "WINDOW_15M"}

episode_summary:
{"count": 6, "data_quality_label": "CLEAN_DATA", "do_not_train": 0, "episode_kind": "WINDOW_15M_CLEAN_MEMORY", "episode_status": "COMPLETE", "memory_quality_label": "CLEAN_MEMORY", "memory_status": "CLEAN_MEMORY", "window_kind": "WINDOW_15M"}
verdict=PASS_LANE_U_U2_CLEAN_MEMORY_FACTORY_CLOSEOUT
`

## Closeout verdict

PASS_LANE_U_U2_CLEAN_MEMORY_FACTORY_CLOSEOUT

## Important interpretation

This checkpoint proves clean memory creation for the governed operator-approved-token path only.

It does not unlock:

- autonomous discovery
- retrieval
- paper decisions
- BUY / SELL / HOLD
- positions
- PnL
- live execution

The next roadmap-safe step should remain bounded and explicit.

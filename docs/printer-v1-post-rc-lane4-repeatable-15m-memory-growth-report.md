# Post-RC Lane 4 — Repeatable 15m Memory Growth Cycles Report

Status: PASS

## Anchor before Lane 4
- Latest guard fix commit: a59fb63 Block source-reference-only duplicate memory windows
- Tag: printer-v1-post-rc-lane4-source-reference-duplicate-guard

## What was validated

Lane 4 validated repeatable 15m memory growth after Lane 2 repeatable evidence windows and Lane 3 context freshness/window targeting.

Validation covered:
- source-reference-only duplicate guard
- fresh DexScreener snapshot collection
- full 15m spaced evidence windows
- repeatable WINDOW_15M memory creation
- clean-only retrieval blocking
- paper decision blocking
- paper position blocking

## Duplicate guard validation

A source-reference-only duplicate build was attempted against the old snapshot range 7–12.

Result:
- duplicate_guard_status: DUPLICATE_SAME_EVIDENCE_NOOP
- duplicate_block_reason: source_reference_only_difference_blocked
- skipped_reason: duplicate_same_evidence_noop
- memory_table_deltas all stayed 0
- printer_memory_windows stayed 3
- printer_episodes stayed 3
- printer_memory_fingerprints stayed 3

PASS: source_reference alone can no longer create a new memory window.

## Snapshot source probe

A fresh snapshot probe created snapshot 13.

Result:
- snapshot_created: true
- snapshot_id: 13
- data_quality_label: CLEAN_DATA
- source_status: COMPLETE
- source_failure_delta: 0
- printer_token_snapshots increased from 12 to 13

PASS: source collection was no longer blocked by prior DexScreener transport failures.

## Full 15m Cycle 1

Cycle time:
- Start: 2026-06-23 13:35:32 +01:00
- End: 2026-06-23 13:50:42 +01:00
- Span: about 15m 10s

Snapshots collected:
- 19, 20, 21, 22, 23, 24

All snapshots:
- snapshot_created: true
- data_quality_label: CLEAN_DATA
- source_status: COMPLETE
- source_failure_delta: 0

Memory build result:
- memory_window_id: 4
- window_kind: WINDOW_15M
- snapshot_ids: 20, 21, 22, 23, 24
- snapshot_start_id: 20
- snapshot_end_id: 24
- coverage_state: COMPLETE_WINDOW_COVERAGE
- duplicate_guard_status: NEW_DISTINCT_EVIDENCE_WINDOW
- evidence_difference_reason: distinct_snapshot_range
- memory_quality_label: AUDIT_ONLY_MEMORY
- retrieval_ready: false
- rejection_reasons: MISSING_OR_UNKNOWN_CONTEXT

Safety:
- paper_decision_delta: 0
- paper_position_delta: 0
- paper positions stayed 0

## Full 15m Cycle 2

Cycle time:
- Start: 2026-06-23 13:55:41 +01:00
- End: 2026-06-23 14:10:53 +01:00
- Span: about 15m 11s

Snapshots collected:
- 25, 26, 27, 28, 29, 30

All snapshots:
- snapshot_created: true
- data_quality_label: CLEAN_DATA
- source_status: COMPLETE
- source_failure_delta: 0

Memory build result:
- memory_window_id: 5
- window_kind: WINDOW_15M
- snapshot_ids: 26, 27, 28, 29, 30
- snapshot_start_id: 26
- snapshot_end_id: 30
- coverage_state: COMPLETE_WINDOW_COVERAGE
- duplicate_guard_status: NEW_DISTINCT_EVIDENCE_WINDOW
- evidence_difference_reason: distinct_snapshot_range
- memory_quality_label: AUDIT_ONLY_MEMORY
- retrieval_ready: false
- rejection_reasons: MISSING_OR_UNKNOWN_CONTEXT

Safety:
- paper_decision_delta: 0
- paper_position_delta: 0
- paper positions stayed 0
- paper trade events stayed 0

## Retrieval result

Clean-only retrieval was tested after both memory builds.

Result:
- clean_memory_count: 0
- clean_eligible_memory_count: 0
- clean_matches_returned: 0
- dirty_or_audit_only_matches_returned_as_clean: 0
- retrieval_result_label: RETRIEVAL_BLOCKED_NO_CLEAN_MEMORY
- paper_decision_allowed: false
- retrieval_allowed: false

PASS: dirty/audit-only memory was not used for retrieval or paper decisions.

## Current final DB state after Lane 4

Observed final counts:
- printer_token_snapshots: 30
- printer_memory_windows: 5
- printer_episodes: 5
- printer_episode_outcomes: 5
- printer_memory_fingerprints: 5
- printer_memory_audit_reports: 4
- printer_memory_retrieval_queries: 5
- printer_memory_retrieval_matches: 0
- printer_paper_positions: 0
- printer_paper_trade_events: 0

## Lane 4 verdict

PASS.

Printer can now create repeatable 15m memory windows from fresh evidence cycles without relying on token/pair singleton behavior and without allowing source-reference-only duplicates.

The system still correctly blocks clean memory, retrieval, paper decisions, paper positions, and PnL when context remains unknown or audit-only.

## Not unlocked

Lane 4 did not unlock:
- BUY
- paper positions
- PnL
- live trading
- wallet/private key/signing
- paid APIs
- scoring/ranking/confidence/weighted decisions
- dirty memory retrieval
- 5m micro-event main-outcome memory
- autonomous runtime

## Next recommended lane

Proceed to the next Post-RC lane only after this report is committed and tagged.

# Post-RC Lane 5 — 5m Micro-Event Support Evidence Hardening Report

Status: PASS

## Anchor before Lane 5

- Latest Lane 4 report commit: e1ab24b Add Lane 4 repeatable 15m memory growth report
- Tag: printer-v1-post-rc-lane4-repeatable-15m-memory-growth
- Working tree before Lane 5 manual probes: clean

## Lane 5 goal

Validate that WINDOW_5M_MICRO_EVENT can exist as repeatable support evidence without becoming a main outcome memory window.

Lane 5 must preserve the locked 5m rule:

- 5m is support-only
- 5m is not a main outcome memory
- 5m must not unlock retrieval by itself
- 5m must not unlock paper decisions
- 5m must not unlock BUY
- 5m must not create paper positions
- 5m must not create PnL

## Manual probe 1 — 5m support-only creation

Command tested:

- Build WINDOW_5M_MICRO_EVENT against snapshot 30

Result:

- memory_window_id: 6
- window_kind: WINDOW_5M_MICRO_EVENT
- snapshot_ids: 29, 30
- snapshot_start_id: 29
- snapshot_end_id: 30
- duplicate_guard_status: NEW_DISTINCT_EVIDENCE_WINDOW
- evidence_difference_reason: distinct_window_kind
- evidence_role: SUPPORT_MICRO_EVENT
- memory_quality_label: AUDIT_ONLY_MEMORY
- memory_status: AUDIT_ONLY
- do_not_train: 1
- retrieval_ready: false
- rejection_reasons:
  - REJECT_5M_ONLY_WINDOW
  - MISSING_OR_UNKNOWN_CONTEXT

Safety result:

- paper_decision_delta: 0
- paper_position_delta: 0
- retrieval_delta: 0
- paper positions stayed 0
- paper trade events stayed 0

Verdict: PASS.

## Manual probe 2 — source-reference-only duplicate 5m no-op

Command tested:

- Build WINDOW_5M_MICRO_EVENT again against snapshot 30 with a different source_reference only

Result:

- memory_window_id: 6
- duplicate_guard_status: DUPLICATE_SAME_EVIDENCE_NOOP
- duplicate_block_reason: source_reference_only_difference_blocked
- evidence_difference_reason: source_reference_only_difference_blocked
- skipped_reason: duplicate_same_evidence_noop
- evidence_role: SUPPORT_MICRO_EVENT
- retrieval_ready: false
- rejection_reasons:
  - REJECT_5M_ONLY_WINDOW
  - MISSING_OR_UNKNOWN_CONTEXT

Memory deltas:

- printer_memory_windows: 0
- printer_episodes: 0
- printer_episode_outcomes: 0
- printer_episode_snapshots: 0
- printer_memory_fingerprints: 0

Safety result:

- paper_decision_delta: 0
- paper_position_delta: 0
- retrieval_delta: 0

Verdict: PASS.

## Manual probe 3 — standalone 5m retrieval block

Command tested:

- Retrieve clean memory after standalone 5m support evidence

Result:

- clean_memory_count: 0
- clean_eligible_memory_count: 0
- clean_matches_returned: 0
- dirty_or_audit_only_matches_returned_as_clean: 0
- retrieval_result_label: RETRIEVAL_BLOCKED_NO_CLEAN_MEMORY
- retrieval_allowed: false
- paper_decision_allowed: false
- similar_clean_memories_found: 0

Verdict: PASS.

## Manual probe 4 — repeatable distinct 5m support evidence

Command tested:

- Build WINDOW_5M_MICRO_EVENT against snapshot 24

Result:

- memory_window_id: 7
- window_kind: WINDOW_5M_MICRO_EVENT
- snapshot_ids: 23, 24
- snapshot_start_id: 23
- snapshot_end_id: 24
- duplicate_guard_status: NEW_DISTINCT_EVIDENCE_WINDOW
- evidence_difference_reason: distinct_snapshot_range
- evidence_role: SUPPORT_MICRO_EVENT
- memory_quality_label: AUDIT_ONLY_MEMORY
- memory_status: AUDIT_ONLY
- do_not_train: 1
- retrieval_ready: false
- rejection_reasons:
  - REJECT_5M_ONLY_WINDOW
  - MISSING_OR_UNKNOWN_CONTEXT

Safety result:

- paper_decision_delta: 0
- paper_position_delta: 0
- retrieval_delta: 0
- paper positions stayed 0
- paper trade events stayed 0

Verdict: PASS.

## Final observed DB state after Lane 5 manual probes

Observed final counts:

- printer_token_snapshots: 30
- printer_memory_windows: 7
- printer_episodes: 7
- printer_episode_outcomes: 7
- printer_episode_snapshots: 22
- printer_memory_fingerprints: 7
- printer_memory_audit_reports: 4
- printer_memory_retrieval_queries: 7
- printer_memory_retrieval_matches: 0
- printer_paper_decisions: 1
- printer_paper_positions: 0
- printer_paper_trade_events: 0

## Files changed

- docs/printer-v1-post-rc-lane5-5m-micro-event-support-evidence-report.md

No source code changes were required for this manual lane because existing Lane 2, Lane 3, and Lane 4 architecture already enforced the required 5m support-only behavior.

## What was built / validated

Validated through bounded operator-approved manual probes:

- WINDOW_5M_MICRO_EVENT can be created as support evidence
- 5m evidence uses evidence_role SUPPORT_MICRO_EVENT
- 5m evidence stays AUDIT_ONLY_MEMORY
- 5m evidence stays do_not_train
- standalone 5m evidence is rejected as main outcome using REJECT_5M_ONLY_WINDOW
- source-reference-only duplicate 5m evidence is blocked/no-op
- genuinely distinct 5m evidence over time is allowed
- standalone 5m evidence does not unlock retrieval
- standalone 5m evidence does not unlock paper decisions
- standalone 5m evidence does not create paper positions or trade events

## What was not touched

- BUY unlock
- paper position creation
- PnL
- live trading
- wallet/private key/signing logic
- paid APIs
- scoring/ranking/confidence/weighted decisions
- source governor bypass
- scheduler bypass
- autonomous runtime
- dirty memory retrieval
- 5m as main outcome memory

## Tests/checks run

Manual operator-approved checks:

- printer-build-memory-window-once with WINDOW_5M_MICRO_EVENT against snapshot 30
- printer-build-memory-window-once duplicate 5m source-reference-only probe against snapshot 30
- printer-retrieve-clean-memory-once after standalone 5m support evidence
- printer-build-memory-window-once with WINDOW_5M_MICRO_EVENT against snapshot 24
- printer-retrieve-clean-memory-once after distinct 5m support evidence
- printer-db-counts
- printer-operator-report

No new automated code tests were added because this lane was completed as a manual post-RC evidence validation, not a source-code patch.

## Pass/fail status

PASS.

Lane 5 exit gate is satisfied for manual post-RC validation:

- 5m support evidence can repeat over time
- dirty/unknown 5m evidence stays audit-only
- 5m support evidence does not replace main 15m outcome memory
- 5m support evidence does not unlock retrieval, paper decisions, BUY, positions, or PnL by itself

## Risks or concerns

- 5m support evidence is currently still audit-only because context remains unknown/partial.
- Clean memory count remains 0.
- Retrieval remains blocked due no clean memory.
- Paper decisions remain blocked.
- Scheduler backlog attention remains visible from earlier pending job state.
- Source failures from earlier DexScreener transport failures remain visible in reports, though no new source failures were created during Lane 5 manual probes.

## Next recommended lane

Proceed to Post-RC Lane 6 — Longer Window Activation Readiness.

Lane 6 should remain architecture/fixture-readiness only. It must not run real 1h/4h/12h/24h windows and must not expand runtime.

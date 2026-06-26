# Printer V1 Lane B Conservative 15m Memory Factory Readiness Review

## 1. Status

This is Post-Lane 10 Proposed Lane B - Conservative 15m Memory Factory Readiness Review.

Lane B is documentation/readiness review only.

Lane B does not implement Memory Factory.

Lane B does not run runtime, scheduler jobs, source fetching, snapshot collection, memory creation, retrieval, paper decisions, BUY, SELL, HOLD, paper positions, trade events, paper audits, or PnL.

Lane B does not authorize wallet logic, private keys, signing, live trading, real funds, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, or vectors.

## 2. Source-of-Truth Documents Checked

This readiness review is subordinate to:

- `AGENTS.md`
- `docs/printer-v1-post-lane10-proposed-next-build-order.md`
- `docs/printer-v1-post-lane10-lane-a-adoption-checkpoint.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-buy-unlock-preconditions.md`
- `docs/printer-v1-paper-position-reactivation-review.md`

The current active roadmap extension is:

- `docs/printer-v1-post-lane10-proposed-next-build-order.md`

## 3. Purpose of Lane B

Lane B asks whether Printer is ready for a later bounded, operator-approved, source-governed 15m Memory Factory implementation.

Lane B must answer readiness questions before implementation starts.

The first Memory Factory implementation must keep paper decisions off.

The 5m window remains support-only.

15m is the first main Memory Factory target.

A Memory Factory cycle may validly produce zero clean memories if evidence is dirty, stale, incomplete, failed, mismatched, missing critical fields, conflicting, or audit-only.

Clean memory must never be forced.

## 4. Current Locked Capabilities

The following remain locked:

- BUY
- SELL
- HOLD
- paper positions
- trade events
- paper audits
- PnL
- runtime expansion
- source fetching
- snapshot creation
- memory creation
- retrieval activation
- paper decision creation
- wallet logic
- private keys
- signing
- live trading
- real funds
- paid API dependencies
- scoring systems
- ranking systems
- confidence percentage systems
- weighted decision logic
- embeddings
- vectors

WAIT, AVOID, and NO_ACTION remain conservative non-position outcomes only under existing approved gates. Lane B does not create them.

## 5. Conservative 15m Memory Factory Readiness Questions

Before implementation, the operator should be able to answer:

- Which command or future lane will open a bounded 15m Memory Factory cycle?
- How will the cycle prove operator approval?
- How will the cycle stay bounded by max tokens, max jobs, max seconds, or an equivalent stop gate?
- How will the cycle report zero clean memories without treating that as failure?
- How will the cycle avoid forcing CLEAN_MEMORY?
- How will old dirty or audit-only memory remain stored but non-retrievable?
- How will new evidence avoid duplicate flooding?
- How will same-token concentration remain visible?
- How will 5m support evidence remain support-only?
- How will the cycle prove paper decisions stayed off?

## 6. Source Budget Readiness Questions

Before implementation, source-budget readiness should answer:

- Which free/public sources are required for a conservative 15m cycle?
- What is the maximum source request count per cycle?
- What is the maximum source failure rate before stopping or degrading?
- How are stale responses counted?
- How are partial responses counted?
- How are source failures kept visible?
- How are token-level snapshots prioritized over broad context?
- How are safety and liquidity refreshes prioritized after snapshots?
- How are source budgets enforced without paid APIs?
- What operator report field will show source budget use?

## 7. Source Governor Readiness Questions

Before implementation, Source Governor readiness should answer:

- Does every external evidence request go through Source Governor?
- Are source requests recorded?
- Are source responses recorded?
- Are source failures recorded?
- Are source_status and data_quality_label present on critical evidence?
- Are stale, failed, missing, or conflicting source rows prevented from clean memory use?
- Is there any direct engine API call that would bypass Source Governor?
- Can the cycle stop if Source Governor detects stale data or source budget exhaustion?
- Can the report show request, response, and failure counts?

## 8. Central Scheduler Readiness Questions

Before implementation, Central Scheduler readiness should answer:

- Which scheduler job kinds are allowed for a bounded 15m Memory Factory cycle?
- How is operator approval represented?
- How is max job count enforced?
- How is max seconds or equivalent runtime boundary enforced?
- How are job locks claimed and released?
- How are failed jobs recorded honestly?
- How does the cycle leave zero running jobs after exit?
- How does the cycle avoid daemon, background worker, cron, or unbounded runtime behavior?
- How does the scheduler keep paper decisions off?

## 9. Tracking Queue Readiness Questions

Before implementation, tracking queue readiness should answer:

- Which tracking lanes are allowed for first 15m Memory Factory work?
- What are the maximum active TRACK_FAST and TRACK_NORMAL counts?
- How are WATCH_ONLY and rejected tokens excluded from full tracking?
- How are duplicate token/pair candidates handled?
- How are same-token repeat windows allowed without flooding?
- How are tokens archived after useful windows close?
- How are source failures or safety blockers reflected in tracking status?
- How are token-level snapshots kept ahead of broad context work?

## 10. Snapshot and Window-Close Readiness Questions

Before implementation, snapshot/window-close readiness should answer:

- What snapshot cadence is required for TRACK_FAST and TRACK_NORMAL 15m windows?
- How is the forced close snapshot scheduled near the 15m close?
- What snapshot gap rate stops or degrades the cycle?
- How are stale snapshots identified?
- How are failed snapshots recorded?
- How are incomplete windows marked dirty or audit-only?
- How is window_start_at/window_end_at or equivalent evidence identity recorded?
- How are snapshot_start_id and snapshot_end_id tied to the memory window?
- How does the cycle avoid using 5m support evidence as the main outcome window?

## 11. Clean and Dirty Memory Gate Readiness Questions

Before implementation, clean/dirty gate readiness should answer:

- Which critical fields are required for CLEAN_MEMORY?
- Which missing fields create AUDIT_ONLY or DIRTY_MEMORY?
- How are stale, failed, conflicting, mismatched, or missing-critical rows blocked?
- How are source_status and data_quality_label checked?
- How are context freshness and target matching checked?
- How are safety, liquidity, entry realism, exit realism, flow, chart, market, and chain context checked?
- How are outcome labels assigned?
- How is do_not_train enforced?
- How does the cycle prove dirty and audit-only memory did not enter retrieval or paper decisions?
- How does the cycle report zero clean memories honestly?

## 12. Operator Report Requirements

A future 15m Memory Factory implementation report should include:

- cycle_id or output-only run id
- started_at and ended_at
- operator approval status
- bounded limits used
- tokens discovered
- tokens accepted for tracking
- tokens rejected or watch-only
- windows attempted
- windows completed
- clean memories created
- dirty or audit-only memories created
- zero-clean-memory reason when applicable
- source request count
- source response count
- source failure count
- source failure labels
- snapshot count
- missed close snapshots
- context rows created or reused
- safety, liquidity, entry realism, exit realism, flow, chart, market, and chain labels
- job count and stop reason if scheduler is used
- proof paper decisions stayed off
- proof BUY, SELL, HOLD, positions, trade events, paper audits, and PnL stayed locked

## 13. Stop Conditions

A future implementation lane must stop or require operator review if:

- source failure rate exceeds the configured threshold
- snapshot gap rate exceeds the configured threshold
- Source Governor detects repeated stale data
- source budget is exhausted
- Central Scheduler queue falls behind
- job locks remain active after exit
- any job remains running after exit
- window-close snapshots are repeatedly missed
- critical data quality labels are missing
- clean memory would be created from incomplete evidence
- dirty or audit-only memory appears in retrieval or decision support
- any path tries to create paper decisions unexpectedly
- any path tries to create BUY, SELL, or HOLD unexpectedly
- any path tries to create paper positions unexpectedly
- any path tries to create trade events, paper audits, or PnL unexpectedly
- any engine bypasses Source Governor
- any engine bypasses Central Scheduler
- unbounded runtime appears

A stopped cycle is acceptable if it prevents memory pollution.

## 14. Risks and Gaps Before Implementation

Risks to resolve before implementation:

- source budgets may not support enough 15m windows
- snapshot cadence may miss window-close evidence
- context collection may lag behind token snapshots
- safety, liquidity, or quote evidence may remain unknown for some candidates
- duplicate evidence handling may need dry-run proof
- tracking queue limits may need operator-selected caps
- reports may need to distinguish zero clean memories from failed execution
- first implementation may accidentally drift into paper decisions unless explicitly blocked

## 15. What Must Not Be Built Yet

Do not build in Lane B:

- Memory Factory implementation
- source fetching
- snapshot collection
- runtime or scheduler execution
- new commands
- migrations
- tests
- retrieval
- paper decisions
- BUY, SELL, or HOLD
- paper positions
- trade events
- paper audits
- PnL
- wallet logic
- private-key logic
- signing or transaction logic
- paid API dependencies
- scoring, ranking, confidence percentages, or weighted logic
- embeddings or vectors

## 16. Lane B Acceptance Checklist

Lane B is accepted when:

- source-of-truth documents checked are listed
- active roadmap extension is identified
- Lane B is confirmed as readiness/review only
- 15m is confirmed as the first main Memory Factory target
- 5m is confirmed as support-only
- zero-clean-memory cycles are accepted as valid when evidence fails
- clean memory is explicitly never forced
- first Memory Factory implementation is confirmed paper-decisions-off
- readiness questions are documented for source budget, Source Governor, Central Scheduler, tracking queue, snapshots, window close, and clean/dirty gates
- operator report requirements are documented
- stop conditions are documented
- BUY, SELL, HOLD, positions, trade events, paper audits, and PnL remain locked

## 17. Next Recommended Lane

The next recommended lane after Lane B is:

Proposed Lane C - Source Budget and Source Governor Verification.

Lane C should remain verification-focused unless the operator explicitly authorizes a narrower implementation task.

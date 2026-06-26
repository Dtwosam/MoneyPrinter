# Printer V1 Post-Lane 10 Architecture Review

## 1. Status

This is a documentation and planning review after Post-RC Lane 10.

This document does not activate a new build order. It does not replace `AGENTS.md`, the Clean Master Spec, the Post-RC Build Order, the Memory Factory Guide, Lane 9 BUY policy, or Lane 10 paper-position policy.

This document does not authorize source fetching, scheduler runtime, memory creation, retrieval activation, paper decisions, BUY, SELL, HOLD, paper positions, trade events, paper trade audits, PnL, wallet logic, private keys, signing, live trading, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, or vectors.

## 2. Current Source-of-Truth Stack

Active source-of-truth documents remain:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-buy-unlock-preconditions.md`
- `docs/printer-v1-paper-position-reactivation-review.md`

The Post-RC Build Order remains the active post-Phase-38 roadmap until the operator explicitly adopts a replacement or extension.

## 3. Completed Post-RC Lanes

The completed post-RC work has established guardrails and readiness around:

- source-of-truth post-RC anchoring
- repeatable evidence windows
- clean context freshness and window targeting
- repeatable 15m memory growth investigation
- 5m support-only compatibility
- longer-window readiness review
- clean-memory retrieval expansion planning
- conservative paper decision audit review
- Lane 9 BUY unlock preconditions policy
- Lane 10 paper position reactivation review policy

Some prior lanes included implementation. Lanes 9 and 10 are documentation-only policies and do not unlock behavior.

## 4. Implemented vs Documentation-Only

Implemented or partially implemented architecture includes:

- Source Governor and source trace concepts
- Central Scheduler and bounded operator-runtime concepts
- token/pair intake and tracking structures
- token snapshot collection structures
- repeatable evidence-window identity
- context freshness and window targeting rules
- safety evidence storage and controlled evidence insertion support
- paper quote evidence storage and controlled evidence insertion support
- flow, chain heat, and market context classification paths
- memory audit gates that keep dirty, stale, incomplete, failed, or audit-only evidence out of clean decision support

Documentation-only policy includes:

- Lane 9 BUY unlock preconditions
- Lane 10 paper position reactivation review
- this architecture review
- any proposed next build order until explicitly adopted by the operator

## 5. Current Locked Capabilities

The following remain locked:

- BUY
- SELL
- HOLD
- paper positions
- trade events
- paper trade audits
- PnL
- live trading
- wallet and private-key logic
- signing and transaction execution
- paid API dependencies
- scoring, ranking, confidence percentages, and weighted logic
- embeddings and vectors unless separately approved as out-of-scope for V1

WAIT, AVOID, and NO_ACTION remain conservative non-position actions, subject to the active paper decision gates.

## 6. Memory Architecture Readiness

Memory architecture is ready for more disciplined Memory Factory work because:

- main memory windows are defined as 15m, 1h, 4h, 12h, and 24h
- WINDOW_5M_MICRO_EVENT is support-only
- repeatable evidence windows can distinguish new evidence from indistinguishable duplicates
- old audit-only memory can remain stored without becoming retrievable
- clean eligibility is tied to completed evidence, target matching, context, source status, and audit results
- dirty, stale, incomplete, failed, or do_not_train memory remains blocked from decisions

Important correction: a Memory Factory cycle is not required to create clean memory. A valid cycle may produce zero clean memories if evidence is dirty, stale, incomplete, failed, mismatched, or otherwise unsafe. Printer must never force CLEAN_MEMORY to satisfy a target.

## 7. Scheduler and Source-Governor Readiness

The architecture has Source Governor and Central Scheduler boundaries that future Memory Factory work must use.

Future collection must remain:

- operator-approved where required
- bounded by max jobs, max seconds, source budgets, and lane-specific stop gates
- source-governed
- scheduler-controlled
- free/public-source only
- visible through source request, response, and failure rows

No engine may call external sources directly or create an independent API loop.

## 8. Tracking Queue, Snapshot, and Window Readiness

Tracking and snapshot concepts are ready for a conservative 15m Memory Factory review because:

- token-level snapshots are the core evidence for memory windows
- TRACK_FAST and TRACK_NORMAL lanes exist conceptually
- memory-window close snapshots are required
- stale, incomplete, delayed, or broken snapshots must block clean memory
- context must target the specific window or evidence identity

Any DB proof that references active token_id, pair_id, snapshot_id, or memory_window_id must be freshly verified by command output before relying on it. This review does not hardcode active persistent DB identifiers.

## 9. Clean-Memory Retrieval Readiness

Retrieval architecture is clean-only by rule.

Retrieval remains unsafe unless:

- clean eligible memory exists
- dirty and audit-only memory are excluded
- 5m support-only evidence does not unlock retrieval by itself
- duplicate evidence does not inflate support
- token concentration and limited diversity remain visible
- no score, rank, confidence percentage, or weighted result is introduced

Retrieval work must not be combined with first Memory Factory implementation unless explicitly approved by a future lane.

## 10. Conservative Paper-Decision Readiness

Conservative paper-decision review has been documented, with WAIT, AVOID, and NO_ACTION as the earliest protective actions.

However, the first Memory Factory implementation should keep paper decisions off. It should not create WAIT, AVOID, NO_ACTION, BUY, SELL, or HOLD while proving the memory growth loop. Paper decisions can be reviewed only after the Memory Factory has produced audited clean memory and the operator activates a separate decision lane.

## 11. BUY, Positions, and PnL Locked Status

BUY remains locked.

SELL and HOLD remain locked because no paper position exists.

Paper positions remain locked.

Trade events, paper trade audits, and PnL remain locked.

Lane 9 defines future BUY review preconditions only. Lane 10 defines future paper-position review preconditions only. Neither lane is executable approval.

## 12. Risks and Gaps Before Memory Factory Work

Key risks before Memory Factory work:

- treating a proposed build order as active without operator adoption
- combining first Memory Factory implementation with paper decisions
- forcing clean memory when evidence is incomplete or unsafe
- allowing 5m support evidence to act as a main outcome memory
- exceeding source budgets during repeated snapshot cycles
- losing source failure visibility
- relying on stale DB identifiers without fresh verification
- treating broad context as a direct trade signal
- creating retrieval support from dirty or audit-only memory
- moving toward BUY or positions before clean-memory gates justify review

## 13. What Must Not Be Built Yet

Do not build:

- BUY unlock
- SELL/HOLD unlock
- paper position opening
- trade events
- paper trade audits
- PnL
- live trading
- wallet or private-key logic
- transaction building, signing, or sending
- paid API dependencies
- scoring, ranking, confidence percentages, or weighted logic
- embeddings or vectors
- unbounded runtime
- direct engine source calls
- dirty-memory retrieval
- first Memory Factory implementation that also creates paper decisions

## 14. Architecture Review Conclusion

Printer is ready for an operator decision about the next post-Lane-10 build order.

The safest next direction is a conservative, bounded, operator-approved 15m Memory Factory readiness sequence that keeps paper decisions, BUY, positions, and PnL locked.

That direction should remain proposed only until explicitly adopted by the operator.

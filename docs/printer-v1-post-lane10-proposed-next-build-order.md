# Printer V1 Post-Lane 10 Proposed Next Build Order

## 1. Status

PROPOSED ONLY. NOT ACTIVE.

This document is a planning proposal after Post-RC Lane 10. It does not replace the active Post-RC Build Order and does not become active unless the operator explicitly adopts it.

This proposal is subordinate to:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-buy-unlock-preconditions.md`
- `docs/printer-v1-paper-position-reactivation-review.md`

This proposal does not authorize source fetching, scheduler runtime, memory creation, retrieval activation, paper decisions, BUY, SELL, HOLD, paper positions, trade events, paper trade audits, PnL, wallet logic, private keys, signing, live trading, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, or vectors.

Every future lane below requires explicit operator approval before it becomes active.

## 2. Proposed Direction

The safest post-Lane-10 direction is to restart implementation with conservative 15m Memory Factory readiness, not BUY, positions, or PnL.

The first implementation lane should prove bounded, source-governed, scheduler-controlled 15m memory growth while paper decisions stay off.

Important correction: a Memory Factory cycle may validly produce zero clean memories. Clean memory must only be created when evidence truly passes. Dirty, stale, incomplete, failed, mismatched, or audit-only evidence must remain blocked.

## 3. Proposed Lane A - Architecture and Document Adoption Checkpoint

Goal:

Confirm whether the operator adopts this proposed build order or requests edits.

Allowed:

- documentation review
- source-of-truth comparison
- operator acceptance checklist

Not allowed:

- code
- migrations
- source fetching
- scheduler runtime
- memory creation
- retrieval
- paper decisions
- BUY, SELL, HOLD
- paper positions
- trade events, paper trade audits, or PnL

Acceptance gate:

- operator explicitly marks a next build order active, or explicitly asks for revision
- proposed status remains visible until adoption

## 4. Proposed Lane B - Conservative 15m Memory Factory Readiness Review

Goal:

Review whether the current architecture can safely run bounded 15m Memory Factory cycles.

Allowed:

- read-only schema and command inspection
- source budget review
- scheduler boundary review
- tracking queue review
- 15m window close requirements
- evidence completeness checklist

Not allowed:

- source fetching
- persistent DB mutation
- memory creation
- paper decisions
- BUY, SELL, HOLD
- paper positions
- PnL

Acceptance gate:

- 15m readiness checklist exists
- zero-clean-memory outcome is accepted as valid when evidence fails
- paper decisions are explicitly off for the first implementation

## 5. Proposed Lane C - Source Budget and Source Governor Verification

Goal:

Verify free/public source capacity and Source Governor limits before repeated 15m cycles.

Allowed:

- inspect source registry
- inspect governor budgets
- inspect source request/response/failure recording
- define dry-run budget checks

Not allowed:

- live collection unless separately approved in a later implementation lane
- source adapter expansion
- paid APIs
- source loops
- direct engine source calls
- memory creation
- paper decisions

Acceptance gate:

- source budgets and stop gates are explicit
- source failures remain visible
- token-level snapshots stay higher priority than broad context

## 6. Proposed Lane D - Scheduler, Tracking Queue, and Window-Close Readiness

Goal:

Verify Central Scheduler, tracking queue, and window-close mechanics for bounded 15m memory cycles.

Allowed:

- review scheduler job kinds
- review queue states
- review TRACK_FAST and TRACK_NORMAL behavior
- review forced window-close snapshot requirements
- review duplicate and idempotency handling

Not allowed:

- unbounded runtime
- background worker
- source fetching without explicit approval
- memory creation
- retrieval
- paper decisions
- BUY, SELL, HOLD
- paper positions

Acceptance gate:

- 15m cycle jobs can be described as bounded and operator-approved
- old dirty or audit-only memory cannot block newer distinct evidence
- indistinguishable duplicate evidence remains idempotent

## 7. Proposed Lane E - Conservative 15m Memory Factory Implementation

Goal:

Run the first bounded, operator-approved 15m Memory Factory implementation with paper decisions off.

Allowed:

- controlled discovery or selection if approved
- bounded source-governed snapshot collection
- fresh targeted context collection
- 15m memory window build attempt
- memory audit
- clean/dirty/audit-only classification
- report of zero or more clean memories

Not allowed:

- requiring every cycle to create clean memory
- forcing CLEAN_MEMORY
- retrieval activation
- paper decisions, including WAIT, AVOID, or NO_ACTION creation
- BUY, SELL, HOLD
- paper positions
- trade events, paper trade audits, or PnL
- live trading or wallet logic

Acceptance gate:

- every mutation is source-governed and scheduler-controlled
- each 15m cycle reports whether it created CLEAN_MEMORY, AUDIT_ONLY, DIRTY_MEMORY, or no memory
- zero clean memories is accepted if evidence does not pass
- paper decision row counts remain unchanged unless a later lane explicitly allows decisions

## 8. Proposed Lane F - 5m Support Evidence Integration, Support-Only

Goal:

Integrate 5m support evidence into 15m memory explanation without making 5m a main outcome window.

Allowed:

- 5m micro-event support capture if approved
- linkage into 15m main memory
- late-buy trap, fast dump, wick-only, micro-exit realism labels
- audit visibility

Not allowed:

- 5m as main outcome memory
- 5m-only retrieval unlock
- 5m-only paper decision unlock
- 5m-only BUY or position unlock
- PnL from 5m alone

Acceptance gate:

- 5m remains support-only
- 15m remains the first main Memory Factory target
- dirty 5m evidence remains audit-only

## 9. Proposed Lane G - 1h Activation Readiness

Goal:

Prepare 1h memory only after 15m behavior is stable and clean-memory rules hold.

Allowed:

- readiness review
- fixture tests
- scheduler capacity review
- source budget review
- 1h window-close requirements

Not allowed:

- real 1h operation without separate approval
- fake 1h evidence from 15m snapshots
- paper decisions
- BUY, SELL, HOLD
- paper positions
- PnL

Acceptance gate:

- 1h requirements are documented
- 15m Memory Factory has proven honest clean/dirty behavior first

## 10. Proposed Lane H - 1h Bounded Memory Factory

Goal:

Run bounded 1h Memory Factory cycles after readiness approval.

Allowed:

- operator-approved bounded 1h tracking
- source-governed snapshots and context
- 1h memory build attempts
- honest clean/dirty/audit-only outcomes

Not allowed:

- unbounded runtime
- fake long-window data
- paper decisions unless separately approved
- BUY, SELL, HOLD
- paper positions
- PnL

Acceptance gate:

- 1h clean memory grows only when full evidence passes
- zero clean memories remains valid if evidence fails
- 15m and 5m support rules remain intact

## 11. Proposed Lane I - Later 4h, 12h, and 24h Staged Activation

Goal:

Stage longer windows only after 15m and 1h behavior are stable.

Allowed:

- readiness review per window kind
- bounded operator-approved collection per window kind
- honest memory audit
- staged activation in order: 4h, then 12h, then 24h

Not allowed:

- fake long-window evidence
- skipping directly to 24h
- paper decisions unless separately approved
- BUY, SELL, HOLD
- paper positions
- PnL

Acceptance gate:

- each longer window has its own readiness and implementation gate
- clean memory is never forced
- source budgets remain safe

## 12. Proposed Lane J - BUY, Positions, and PnL Remain Locked

Goal:

Keep financial action gates locked until separate future operator-approved lanes explicitly review them.

Allowed:

- status reporting
- audit review
- readiness policy comparison

Not allowed:

- BUY unlock
- SELL/HOLD unlock
- paper position creation
- trade events
- paper trade audits
- PnL
- live trading

Acceptance gate:

- Lane 9 BUY policy still controls BUY review
- Lane 10 position policy still controls position review
- BUY, positions, and PnL remain locked until later explicit approved lanes

## 13. Global Forbidden Actions for This Proposed Order

Unless a future adopted lane explicitly allows a narrower action, do not build:

- live trading
- wallet connection
- private keys
- real fund movement
- transaction building, signing, or sending
- paid API dependency
- source adapter expansion
- direct engine source calls
- unbounded runtime
- scoring, ranking, confidence percentages, or weighted logic
- embeddings or vectors
- dirty-memory retrieval
- forced clean memory
- paper decisions during first Memory Factory implementation
- BUY, SELL, HOLD
- paper positions
- trade events, paper trade audits, or PnL

## 14. Proposed Adoption Checklist

Before this proposed build order becomes active, the operator should confirm:

- this document is accepted as proposed next order
- `AGENTS.md` should or should not be updated in a separate task
- first implementation remains 15m Memory Factory only
- paper decisions stay off during first Memory Factory implementation
- zero clean memories is an acceptable cycle outcome
- 5m remains support-only
- 1h, 4h, 12h, and 24h remain staged later
- BUY, positions, and PnL remain locked

Until that adoption happens, this document is planning only.
